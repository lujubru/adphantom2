"""
AI Agent — auto-classification of client intent + auto-response flow.

This module implements the 5-phase AI cashier assistant:

    Phase 1: Intent classifier
        Reads incoming messages + last N of context, classifies into
        {carga, retiro, nuevo, otro}, and auto-tags the lead. Cashier
        gets a categorized queue in the sidebar.

    Phase 2/3/4: Scripted+humanized auto-response flow per intent
        - carga: give CBU, wait for receipt, OCR validate, tag as pending
        - retiro: collect user + amount + destination CBU + holder
        - nuevo:  collect name + DNI + preferred platform

    Phase 5: Multi-intent + handoff
        - Re-classify on every inbound; switch flow if topic changes.
        - Escalate to human on confusion / "hablar con humano" / N failures.

Design decisions:
  * Claude Sonnet 3.5 for classification + free-form understanding.
  * Response templates rotate deterministically to avoid Meta's
    "identical message spam" flag on principal lines.
  * Per-cajero configuration in `user.ai_config`. Each cajero decides
    tone, brand name, opening hours, min/max amounts, and can pause AI
    on any specific lead from the chat UI.
  * State machine lives in `crm_leads.ai_state`:
        { active_intent, flow_step, collected, last_ai_reply_at }
  * Tags used as the shared vocabulary between AI and cashier — see the
    TAG_KEY_* constants below. Removing a tag from the cashier UI
    effectively closes the AI-managed transaction.
"""
from __future__ import annotations
import json
import logging
import random
import re
import uuid
from datetime import datetime, timezone, time as dtime
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# ── Tag identifiers (canonical names auto-created per line) ────────
TAG_KEY_CARGA   = "🟢 pendiente-carga"
TAG_KEY_RETIRO  = "🟡 pendiente-retiro"
TAG_KEY_NUEVO   = "🔵 nuevo-usuario"
TAG_KEY_REVISAR = "🔴 revisar"
AI_TAG_KEYS     = [TAG_KEY_CARGA, TAG_KEY_RETIRO, TAG_KEY_NUEVO, TAG_KEY_REVISAR]

# ── Default configuration when the cajero hasn't set one ───────────
DEFAULT_AI_CONFIG: Dict[str, Any] = {
    "enabled": False,           # master toggle per cashier
    "brand_name": "",           # e.g. "TataNET"
    "brand_tone": "casual",     # formal | casual | amistoso
    "opening_time": "09:00",    # HH:MM local AR time
    "closing_time": "01:00",    # HH:MM local AR time (crosses midnight if closing < opening)
    "off_hours_message": (
        "¡Hola! Nuestro horario de atención es de {opening} a {closing}. "
        "En breve un cajero te va a responder. 🙌"
    ),
    "min_deposit": 1000.0,
    "max_deposit": 500000.0,
    "min_withdrawal": 1000.0,
    "max_withdrawal": 500000.0,
    "context_msgs": 15,         # how many recent messages to feed to Claude
    "confidence_threshold": 0.40,  # if classifier is unsure, tag as revisar
    "signature": "",            # optional signature appended by AI
    "platforms": [],            # list of platform names offered to new users
}


def merged_ai_config(user_doc: Optional[Dict]) -> Dict[str, Any]:
    """Merge cashier's stored ai_config over defaults."""
    cfg = dict(DEFAULT_AI_CONFIG)
    if user_doc and isinstance(user_doc.get("ai_config"), dict):
        for k, v in user_doc["ai_config"].items():
            if k in cfg:
                cfg[k] = v
    # Normalise platforms → list of trimmed non-empty strings. Accept both
    # comma-separated strings and lists that may still contain commas.
    raw_plats = cfg.get("platforms") or []
    if isinstance(raw_plats, str):
        raw_plats = [raw_plats]
    if not isinstance(raw_plats, list):
        raw_plats = []
    _norm: List[str] = []
    for item in raw_plats:
        for piece in str(item).split(","):
            piece = piece.strip()
            if piece:
                _norm.append(piece)
    cfg["platforms"] = _norm
    return cfg


def within_opening_hours(cfg: Dict[str, Any], now_ar: datetime) -> bool:
    """Return True if `now_ar` (in AR local time) is within the cashier's opening window.

    Handles windows that cross midnight (e.g. 09:00 → 01:00 next day).
    """
    try:
        oh, om = [int(x) for x in cfg.get("opening_time", "09:00").split(":")]
        ch, cm = [int(x) for x in cfg.get("closing_time", "01:00").split(":")]
        now_t = dtime(now_ar.hour, now_ar.minute)
        open_t = dtime(oh, om)
        close_t = dtime(ch, cm)
        if open_t <= close_t:
            return open_t <= now_t <= close_t
        # Window crosses midnight
        return now_t >= open_t or now_t <= close_t
    except Exception:
        return True


# ─────────────────────────────────────────────────────────────────
#  Intent classifier
# ─────────────────────────────────────────────────────────────────

_CLASSIFIER_PROMPT = """You are an intent classifier for the WhatsApp support desk of an Argentine online
gaming/betting platform. Read the conversation (oldest→newest) and the NEWEST client
message, then decide the customer's PRIMARY intent among these SIX:

  - "carga"   → the client wants to DEPOSIT / TOP-UP money into their account.
                Argentine signals: "quiero cargar", "cargar plata/guita", "depositar",
                "recargar", "voy a cargar", "cuanto es el minimo", "pasame el cbu/alias",
                "quiero jugar hoy", "quiero apostar", OR ATTACHES A TRANSFER RECEIPT IMAGE.
  - "retiro"  → the client wants to WITHDRAW money. Signals: "quiero retirar",
                "sacar la plata/guita", "cobrar", "quiero cobrar mi premio",
                "cuando me pagan", "hacer un retiro", "necesito la plata".
  - "nuevo"   → the client wants to CREATE a new account OR asks about how to get one.
                Signals: "quiero jugar", "cómo me registro", "quiero crear un usuario",
                "quiero mi usuario", "quiero un usuario", "soy nuevo", "recién empiezo",
                "cómo empiezo", "me pasas los datos para jugar", "quiero abrir cuenta",
                "quiero jugar como hago".
  - "saludo"  → the newest message is JUST a greeting with NO indication of intent yet.
                Signals: "hola", "buenas", "buen día", "hola ahi?", "hola que tal",
                "buenas tardes", "hey", "que hacés". If it's a greeting AND anything
                else (like "hola quiero cargar"), classify by the other intent, NOT
                as saludo.
  - "consulta"→ the client is ASKING A QUESTION about the service before committing.
                They want information, not to transact yet. Typical signals:
                "que plataformas tenes?", "tenes X plataforma?", "se gana?",
                "es real?", "pagan?", "cuanto se gana?", "es confiable?",
                "como funciona?", "cual es la mejor plataforma?", "que juegos hay?",
                "cual me recomendas?", "hay bono?", "tenes ruleta/tragamonedas?",
                "cuanto tardan en pagar?", "es seguro?".
  - "otro"    → any other case: complaint, insult, unrelated topic, or the client
                explicitly asks for a human ("hablar con cajero/humano").

Additional rules:
  * If the newest message ATTACHES an image labelled as "[Imagen]" or "[Recibo]",
    intent is almost certainly "carga" — unless the surrounding conversation
    clearly indicates otherwise.
  * If the conversation had a previous active intent and the newest message is
    just a short "gracias/ok/dale/oki" → return "intent_same".
  * If the client explicitly says "hablar con cajero", "quiero hablar con un
    humano", "no me sirve la IA" → return "otro" with high confidence.
  * "no quiero un humano" / "quiero que me responda la IA" → return "consulta"
    (they want to keep talking to the bot).
  * Argentines write SHORT and use lots of slang ("plata", "guita", "papu", "boludo").
    Do NOT downgrade confidence for short messages if the intent is clear.
  * BE GENEROUS with confidence. If the message clearly maps to an intent —
    even a super short "quiero cargar" (3 words) — return confidence 0.85+.
    Only drop below 0.5 if it's genuinely ambiguous.

Return STRICT JSON, no prose:

{
  "intent": "carga|retiro|nuevo|saludo|consulta|otro|intent_same",
  "confidence": 0..1,
  "reason": "one short Spanish sentence explaining your choice"
}
"""


async def classify_intent(anthropic_client, history: List[Dict], newest: Dict, prev_intent: Optional[str]) -> Dict[str, Any]:
    """Ask Claude to classify the newest message's intent.

    history: list of {sender, content, message_type} in chronological order (oldest first)
    newest: the just-arrived message dict
    prev_intent: current active_intent on the lead, if any (for continuation detection)
    """
    if anthropic_client is None:
        return {"intent": "otro", "confidence": 0.0, "reason": "AI disabled (no client)"}

    # Compact the history into a readable transcript. Never exceed ~25 lines to
    # keep the token bill sane and stay well under Sonnet's context limit.
    lines: List[str] = []
    for m in history[-25:]:
        role = "Cliente" if m.get("sender") == "lead" else "Cajero"
        content = m.get("content") or ""
        if m.get("message_type") == "image":
            content = f"[Imagen adjunta] {content}"
        elif m.get("message_type") == "audio":
            content = "[Audio de voz]"
        # Truncate very long messages
        if len(content) > 300:
            content = content[:300] + "…"
        lines.append(f"{role}: {content}")

    # Append the newest message separately so Claude knows which one to classify.
    newest_content = newest.get("content") or ""
    if newest.get("message_type") == "image":
        newest_content = f"[Imagen adjunta] {newest_content}"
    elif newest.get("message_type") == "audio":
        newest_content = "[Audio de voz]"

    user_msg = (
        "── Conversación previa ──\n" + ("\n".join(lines) if lines else "(sin historial)") +
        f"\n\n── NUEVO MENSAJE del cliente a clasificar ──\n{newest_content}\n\n"
        f"Intent activo anterior: {prev_intent or 'ninguno'}\n\n"
        "Devolvé el JSON."
    )

    try:
        resp = await anthropic_client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=200,
            system=_CLASSIFIER_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = resp.content[0].text.strip()
        # Strip ```json fences if present
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL).strip()
        parsed = json.loads(text)
        return {
            "intent": str(parsed.get("intent", "otro")),
            "confidence": max(0.0, min(1.0, float(parsed.get("confidence", 0.0) or 0.0))),
            "reason": str(parsed.get("reason", ""))[:200],
        }
    except Exception as e:
        logger.error(f"AI classifier failed: {e}")
        return {"intent": "otro", "confidence": 0.0, "reason": f"classifier_error: {e}"}


# ─────────────────────────────────────────────────────────────────
#  Free-form consulta answering (Q&A about the service)
# ─────────────────────────────────────────────────────────────────

_CONSULTA_SYSTEM_PROMPT = """Sos el asistente de WhatsApp de un cajero argentino de plataformas de
juego online (apuestas / casino). Un cliente potencial te está haciendo una
PREGUNTA GENERAL antes de decidirse (todavía NO quiere cargar ni retirar).
Tu tarea: contestarle de forma corta, natural, argentina y persuasiva, y al
final invitarlo a crear su usuario o cargar plata.

REGLAS OBLIGATORIAS:
- Máximo 3 líneas. Usá tono casual argentino ("dale", "buenísimo", "posta").
- Nunca prometas ganancias garantizadas ("vas a ganar seguro" está PROHIBIDO).
  Podés decir "muchos clientes ganan a diario", "es 100% real", "las ganancias
  se pagan al toque".
- Si el cliente pregunta por una plataforma específica, respondé usando SOLO
  las plataformas que están en la lista "PLATAFORMAS DISPONIBLES" del contexto.
  Si preguntan por una que NO está en la lista, decí que esa no la manejás
  pero ofrecé las que sí tenés.
- Si pregunta "qué plataformas tenés" y hay lista, listá las plataformas
  disponibles (viñetas cortas).
- Si NO hay plataformas configuradas, decí que "tenemos varias, decime cuál
  te interesa" y ofrecé crear usuario.
- Si pregunta "se gana / es real / pagan", contestá con confianza pero SIN
  garantías absolutas, y cerrá invitando a arrancar.
- Si pregunta algo que no podés responder (política interna, comisiones
  específicas, promociones puntuales, tiempos de pago exactos), decí
  amablemente "eso te lo confirma el cajero en un ratito" — NO INVENTES.
- SIEMPRE cerrá con una call-to-action suave: "¿te creo el usuario?" o
  "cuando quieras arrancar avisame".
- NUNCA uses el signo pesos ni des CBUs — eso lo maneja el flujo de carga.
- Respondé en español rioplatense. NO uses emojis excesivos (máximo 2).
"""


async def answer_consulta(
    anthropic_client,
    cfg: Dict[str, Any],
    lead: Dict,
    newest_message: Dict,
    history: List[Dict],
) -> Optional[str]:
    """Ask Claude to answer a general question about the service using the
    cashier's configured brand and platforms as context. Returns a short
    reply string, or None if the client / API is unavailable."""
    if anthropic_client is None:
        return None
    brand = (cfg.get("brand_name") or "").strip() or "la plataforma"
    platforms = cfg.get("platforms") or []
    platforms_block = (
        "\n".join(f"- {p}" for p in platforms) if platforms
        else "(sin lista configurada — decile al cliente que ofrecés varias y "
             "pedile cuál le interesa)"
    )
    # Compact recent context so Claude sees the flow.
    lines: List[str] = []
    for m in history[-10:]:
        role = "Cliente" if m.get("sender") == "lead" else "Cajero"
        content = (m.get("content") or "")[:200]
        lines.append(f"{role}: {content}")
    newest_content = (newest_message.get("content") or "").strip()[:400]

    user_msg = (
        f"CONTEXTO DEL NEGOCIO\n"
        f"- Marca / cajero: {brand}\n"
        f"- PLATAFORMAS DISPONIBLES:\n{platforms_block}\n\n"
        f"CONVERSACIÓN PREVIA\n" + ("\n".join(lines) if lines else "(sin historial)") +
        f"\n\nÚLTIMA PREGUNTA DEL CLIENTE:\n{newest_content}\n\n"
        f"Respondele en 1-3 líneas y cerrá invitándolo a arrancar."
    )
    try:
        resp = await anthropic_client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=300,
            system=_CONSULTA_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = (resp.content[0].text or "").strip()
        # Safety: strip anything that looks like a CBU or huge number
        text = re.sub(r"\b\d{20,}\b", "", text)
        return text[:800] or None
    except Exception as e:
        logger.error(f"AI consulta answering failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────
#  Response templates — humanized rotation to avoid Meta spam signals
# ─────────────────────────────────────────────────────────────────

CARGA_ASK_USER_VARIANTS = [
    "¡Hola{name_suffix}! 👋 Perfecto, ¿ya tenés usuario en la plataforma? Si sí, pasame tu **nombre de usuario** 🎮",
    "Hola{name_suffix}, para cargarte necesito tu **usuario** en la plataforma. ¿Cuál es? (si aún no tenés, decime 'no tengo')",
    "¡Buenas{name_suffix}! Decime tu **nombre de usuario** en la plataforma para cargarte. Si no tenés cuenta, avisame que te la creamos 🙌",
    "Dale{name_suffix}, ¿cuál es tu usuario en la plataforma? (si sos nuevo/a decime 'no tengo' y te doy de alta)",
]

# Sent AFTER we have the client's platform username. Split into 3 short messages
# so the CBU is easy to copy-paste alone (long-press = copy single message).
CARGA_CBU_INTRO_VARIANTS = [
    "¡Genial{name_suffix}! 🚀 Anotado. Te paso los datos para transferir 👇",
    "Perfecto{name_suffix} 👌 Copiá el CBU/alias de acá abajo:",
    "Buenísimo{name_suffix} ✨ Ahí van los datos, copiá el CBU 👇",
    "Dale{name_suffix}, para cargar transferí a este CBU/alias 👇",
]

CARGA_CBU_HOLDER_VARIANTS = [
    "👤 A nombre de: {holder}\n\nCuando termines la transferencia mandame el comprobante y te acredito al toque 🙌",
    "👤 Titular: {holder}\n\nEnviame la captura del comprobante y en un ratito quedás cargado ✨",
    "👤 Va a nombre de: {holder}\n\nMandame el comprobante cuando termines 📸",
]

RETIRO_ASK_USER_VARIANTS = [
    "¡Hola{name_suffix}! 👋 Perfecto, para gestionar tu retiro necesito primero tu **usuario** de la plataforma.",
    "Hola{name_suffix}, para procesar el retiro decime tu usuario en la plataforma 🎮",
    "¡Buenas{name_suffix}! Para retirarte, pasame tu usuario primero 🙌",
    "Vamos con el retiro{name_suffix} — ¿cuál es tu usuario en la plataforma?",
]

RETIRO_ASK_AMOUNT_VARIANTS = [
    "Genial. ¿Cuánto querés retirar? (mínimo ${min:,.0f} — máximo ${max:,.0f})",
    "Perfecto. Decime el monto a retirar 💵 (entre ${min:,.0f} y ${max:,.0f})",
    "Anotado 👌 ¿Qué monto querés que te transfiera? (mín ${min:,.0f} · máx ${max:,.0f})",
]

RETIRO_ASK_CBU_VARIANTS = [
    "Perfecto ✅ Ahora pasame el **CBU o alias** donde querés recibir el dinero.",
    "Buenísimo. Enviame el CBU/alias de destino 👇",
    "Anotado. ¿A qué CBU o alias querés que te transfiera? 🏦",
]

RETIRO_ASK_HOLDER_VARIANTS = [
    "Última cosa: el **nombre completo del titular** de esa cuenta 🙏",
    "¿A nombre de quién está la cuenta? (nombre completo del titular)",
    "Para cerrar, ¿cuál es el titular de la cuenta? 📝",
]

RETIRO_CONFIRM_VARIANTS = [
    ("¡Perfecto! Ya tengo todos los datos ✨\n\n"
     "🎮 Usuario: {user}\n💵 Monto: ${amount:,.0f}\n🏦 CBU/Alias: {cbu}\n👤 Titular: {holder}\n\n"
     "En un ratito el cajero te confirma la transferencia 🙌"),
    ("Listo{name_suffix} 👍 Recibí:\n\n"
     "🎮 Usuario: {user}\n💵 Monto: ${amount:,.0f}\n🏦 Destino: {cbu}\n👤 Titular: {holder}\n\n"
     "Un cajero lo procesa en breve ✅"),
]

NUEVO_ASK_NAME_VARIANTS = [
    "¡Hola{name_suffix}! 🙌 Para crearte el usuario decime tu **nombre** por favor 📝",
    "Bienvenido/a a bordo{name_suffix} 🎉 Contame tu nombre para arrancar.",
    "¡Hola{name_suffix}! Para darte de alta, ¿cuál es tu nombre? 📝",
    "Dale{name_suffix} 🙌 Empezamos por tu nombre.",
]

NUEVO_ASK_PLATFORM_NO_LIST_VARIANTS = [
    "Genial 👍 ¿En qué plataforma querés jugar? 🎰",
    "Perfecto. Decime en qué plataforma querés operar 🎲",
    "Buenísimo. ¿En qué plataforma te gustaría jugar? 🎮",
]

# Used when the cashier configured a list of available platforms.
NUEVO_ASK_PLATFORM_LIST_TEMPLATE = (
    "Genial 👍 Elegí una plataforma para jugar:\n\n"
    "{platform_list}\n\n"
    "Contame cuál preferís y te la creamos ✨"
)

NUEVO_CONFIRM_VARIANTS = [
    ("¡Listo{name_suffix}! 🎉 Ya recibí tus datos:\n\n"
     "📝 Nombre: {name}\n🎮 Plataforma: {platform}\n\n"
     "En breve el cajero te crea el usuario y te pasa los accesos 🙌"),
    ("Genial{name_suffix} ✨ Tomé nota de:\n\n"
     "📝 {name}\n🎮 {platform}\n\n"
     "Un cajero te va a mandar los datos de acceso en un ratito 🚀"),
    ("Perfecto{name_suffix} 👍 Registré:\n\n"
     "📝 {name}\n🎮 {platform}\n\n"
     "En unos minutos te llegan los accesos por acá 🙌"),
]

RECEIPT_ACK_VARIANTS = [
    "¡Recibí la imagen! 📸 La estoy verificando 🔍",
    "Imagen recibida ✅ Un segundo que la chequeo…",
    "Genial, ya la tengo. Le doy una revisada rápida 👀",
    "Recibida 📸 Estoy validando el comprobante…",
]

RECEIPT_INVALID_VARIANTS = [
    "🤔 La imagen que me pasaste no parece ser un comprobante de transferencia. ¿Me podés enviar la captura del comprobante real por favor? 🙏",
    "Hmm, esa imagen no me figura como un comprobante válido 📸 ¿Podés reenviarme la captura de la transferencia?",
    "Perdón, no logro identificar esa imagen como un comprobante. Enviame por favor la captura del comprobante de la transferencia 🙌",
]

SALUDO_VARIANTS = [
    ("¡Hola{name_suffix}! 👋 Bienvenido/a{brand_suffix}. ¿En qué te puedo ayudar hoy?\n\n"
     "💰 Cargar plata\n"
     "💸 Retirar\n"
     "🎮 Crear usuario nuevo\n\n"
     "Contame qué necesitás y arrancamos 🙌"),
    ("¡Buenas{name_suffix}! 🙌{brand_suffix_dot} ¿Qué necesitás?\n\n"
     "• Cargar 💰\n"
     "• Retirar 💸\n"
     "• Registrarte 🎮\n\n"
     "Decime en una palabra y seguimos ✨"),
    ("Hola{name_suffix}! 👋{brand_suffix_dot} Contame:\n\n"
     "1️⃣ ¿Querés cargar?\n"
     "2️⃣ ¿Querés retirar?\n"
     "3️⃣ ¿Querés crear usuario?\n\n"
     "Escribime 1, 2 o 3 (o contame en una línea 😉)"),
]

HANDOFF_VARIANTS = [
    "Dale, dejame que llame al cajero para que te atienda 🙋 En un ratito te responde.",
    "Un cajero te va a estar respondiendo en un momento 👍",
    "Perfecto, un humano te atiende en breve 🙌",
]


def receipt_invalid_message(lead_id: Optional[str] = None) -> str:
    """Return a rotated 'this doesn't look like a receipt' message.

    Called from the OCR pipeline when Claude reports is_receipt=false so
    we can tell the client (politely) that we couldn't validate their image
    and ask them to resend the real transfer receipt.
    """
    salt = f"invalid-{lead_id or ''}-{datetime.now(timezone.utc).minute}"
    return _pick(RECEIPT_INVALID_VARIANTS, salt)


def _pick(variants: List[str], salt: Optional[str] = None) -> str:
    """Deterministic-ish random pick — uses `salt` (e.g. lead_id + timestamp) so
    two adjacent requests don't get the same variant. Falls back to random
    if no salt provided."""
    if not variants:
        return ""
    if salt:
        idx = abs(hash(salt)) % len(variants)
        return variants[idx]
    return random.choice(variants)


# ─────────────────────────────────────────────────────────────────
#  Flow: state machine helpers
# ─────────────────────────────────────────────────────────────────

def _name_suffix(lead: Dict) -> str:
    """Try to produce a nice name suffix like ' Juan' if we know the client's
    first name. Return '' if unknown or looks like a placeholder."""
    name = (lead.get("name") or "").strip()
    if not name or name.lower().startswith(("lead ", "cliente")):
        return ""
    first = name.split()[0]
    if len(first) < 2 or first.isdigit():
        return ""
    return f" {first}"


def _format_cbu_block(cbu_list: List[Dict]) -> str:
    """Turn the cashier's cbu_list into a plain-text block for WhatsApp."""
    if not cbu_list:
        return "(el cajero no configuró sus CBUs — te van a responder en breve)"
    lines = []
    for i, cbu in enumerate(cbu_list, 1):
        num = (cbu.get("cbu") or "").strip()
        name = (cbu.get("name") or "").strip()
        if num:
            lines.append(f"CBU/Alias {i}: {num}")
            if name:
                lines.append(f"          a nombre de: {name}")
    return "\n".join(lines) if lines else "(sin CBUs configurados)"


# ─────────────────────────────────────────────────────────────────
#  Flow driver — decide what to reply based on intent + current step
# ─────────────────────────────────────────────────────────────────

async def next_reply(
    anthropic_client,
    lead: Dict,
    user_doc: Dict,
    intent: str,
    newest_message: Dict,
    context_history: List[Dict],
) -> Optional[Dict[str, Any]]:
    """Given the classified intent, produce the next reply to send to the
    lead. Returns a dict:
        {
          "reply": str | None,        # message to send via WhatsApp
          "new_state": {..},           # updated ai_state to persist on the lead
          "tag_keys_to_add": [str],   # tag names to attach (auto-created)
          "handoff": bool,             # True → also add revisar tag, stop AI
        }
    Returns None if there is nothing to say (e.g. intent 'otro' → cashier).
    """
    prev_state = lead.get("ai_state") or {}
    active = prev_state.get("active_intent")
    step = int(prev_state.get("flow_step") or 0)
    collected = dict(prev_state.get("collected") or {})
    salt = f"{lead.get('id')}-{step}-{datetime.now(timezone.utc).timestamp()}"
    name_suf = _name_suffix(lead)

    # ── New intent starting → reset flow ─────────────────────────
    if intent != active:
        active = intent
        step = 0
        collected = {}

    # ── SALUDO (client just said "hola") → offer a menu of options ──
    if intent == "saludo":
        cfg = merged_ai_config(user_doc)
        brand = (cfg.get("brand_name") or "").strip()
        brand_suffix = f" a {brand}" if brand else ""
        brand_suffix_dot = f" Somos {brand}." if brand else ""
        template = _pick(SALUDO_VARIANTS, salt)
        reply = template.format(
            name_suffix=name_suf,
            brand_suffix=brand_suffix,
            brand_suffix_dot=brand_suffix_dot,
        )
        # No tag yet — we're waiting for the client to pick an option.
        return {
            "reply": reply,
            "new_state": {"active_intent": "saludo", "flow_step": 1, "collected": {}},
            "tag_keys_to_add": [],
            "handoff": False,
        }

    # ── CONSULTA (client asks a general question) ────────────────
    # Free-form answering with Claude, using cashier's brand + platform list.
    if intent == "consulta":
        answer = await answer_consulta(
            anthropic_client, merged_ai_config(user_doc), lead, newest_message, context_history
        )
        if not answer:
            # Fall back to handoff if the model call failed.
            return {
                "reply": _pick(HANDOFF_VARIANTS, salt),
                "new_state": {"active_intent": "consulta", "flow_step": 0, "collected": collected},
                "tag_keys_to_add": [TAG_KEY_REVISAR],
                "handoff": True,
            }
        return {
            "reply": answer,
            "new_state": {"active_intent": "consulta", "flow_step": 1, "collected": collected},
            "tag_keys_to_add": [],
            "handoff": False,
        }

    # ── HANDOFF / OTRO ──────────────────────────────────────────
    if intent == "otro":
        reply = _pick(HANDOFF_VARIANTS, salt).format()
        return {
            "reply": reply,
            "new_state": {"active_intent": "otro", "flow_step": 0, "collected": {}, "handoff": True},
            "tag_keys_to_add": [TAG_KEY_REVISAR],
            "handoff": True,
        }

    # ── CARGA ────────────────────────────────────────────────────
    if intent == "carga":
        cbu_list = user_doc.get("cbu_list") or []
        text = (newest_message.get("content") or "").strip()

        # If the newest message is an image → user is sending the receipt.
        # OCR runs elsewhere; here we just ACK and tag.
        if newest_message.get("message_type") == "image":
            reply = _pick(RECEIPT_ACK_VARIANTS, salt)
            return {
                "reply": reply,
                "new_state": {"active_intent": "carga", "flow_step": 9, "collected": collected},
                "tag_keys_to_add": [TAG_KEY_CARGA],
                "handoff": False,
            }

        # Step 0: ask the client for their platform username BEFORE giving CBU.
        if step == 0:
            reply = _pick(CARGA_ASK_USER_VARIANTS, salt).format(name_suffix=name_suf)
            return {
                "reply": reply,
                "new_state": {"active_intent": "carga", "flow_step": 1, "collected": collected},
                "tag_keys_to_add": [],
                "handoff": False,
            }

        # Step 1: client should now be replying with their username OR "no tengo".
        if step == 1:
            low = text.lower().strip()
            # Detect "I don't have an account yet" → hand off to `nuevo` flow.
            no_account_signals = (
                "no tengo", "no cuenta", "no usuario", "no, no", "no aun", "no aún",
                "soy nuevo", "recien", "recién", "primera vez", "no tengo cuenta",
                "no tengo usuario", "no todavia", "no todavía", "aun no", "aún no",
                "quiero crear", "quiero uno", "quisiera crear", "hacer uno",
            )
            if any(sig in low for sig in no_account_signals) or low in {"no", "nop", "nel", "nope"}:
                # Switch to `nuevo` flow, step 0 → ask for full name.
                reply = _pick(NUEVO_ASK_NAME_VARIANTS, salt).format(name_suffix=name_suf)
                return {
                    "reply": reply,
                    "new_state": {"active_intent": "nuevo", "flow_step": 1, "collected": {}},
                    "tag_keys_to_add": [TAG_KEY_NUEVO],
                    "handoff": False,
                }
            # Otherwise assume the text IS their username. Require some minimal length.
            if len(text) < 2:
                return {
                    "reply": "Perdón, no capté tu usuario. Pasámelo de nuevo por favor 🙏",
                    "new_state": {"active_intent": "carga", "flow_step": 1, "collected": collected},
                    "tag_keys_to_add": [], "handoff": False,
                }
            collected["user"] = text[:50]

            # Now send CBU in TWO/THREE separate messages so the CBU is easy to
            # copy-paste alone (long-press on WhatsApp copies a single message).
            if not cbu_list:
                fallback = "Ahora te paso el CBU… un cajero te lo confirma en un ratito 🙌"
                return {
                    "reply": fallback,
                    "new_state": {"active_intent": "carga", "flow_step": 2, "collected": collected},
                    "tag_keys_to_add": [TAG_KEY_REVISAR],
                    "handoff": True,
                }
            # Rotate CBUs so we don't blast the same one every time — this
            # also spreads incoming volume across the cashier's configured
            # accounts and lowers per-account limits with the bank.
            # random.choice → real uniform distribution across the pool.
            cbu = random.choice(cbu_list)
            cbu_num = (cbu.get("cbu") or "").strip()
            holder = (cbu.get("name") or "").strip() or "el titular"

            msg_intro = _pick(CARGA_CBU_INTRO_VARIANTS, salt).format(name_suffix=name_suf)
            msg_cbu = cbu_num  # copy-friendly: only the CBU/alias in this message
            msg_holder = _pick(CARGA_CBU_HOLDER_VARIANTS, salt).format(holder=holder)

            return {
                # List → server sends messages one-by-one with a small delay.
                "reply": [msg_intro, msg_cbu, msg_holder],
                "new_state": {"active_intent": "carga", "flow_step": 2, "collected": collected},
                "tag_keys_to_add": [],
                "handoff": False,
            }

        # Step 2+: already sent CBU, still waiting for the receipt image → gentle nudge
        return {
            "reply": "Ya te pasé el CBU 🙂 Cuando hagas la transferencia mandame el comprobante 📸",
            "new_state": {"active_intent": "carga", "flow_step": max(step, 2), "collected": collected},
            "tag_keys_to_add": [],
            "handoff": False,
        }

    # ── RETIRO ───────────────────────────────────────────────────
    if intent == "retiro":
        cfg = merged_ai_config(user_doc)
        text = (newest_message.get("content") or "").strip()

        # Step 0: ask for user
        if step == 0:
            reply = _pick(RETIRO_ASK_USER_VARIANTS, salt).format(name_suffix=name_suf)
            return {
                "reply": reply,
                "new_state": {"active_intent": "retiro", "flow_step": 1, "collected": collected},
                "tag_keys_to_add": [],
                "handoff": False,
            }
        # Step 1: got user (any non-trivial text), ask amount
        if step == 1:
            if len(text) < 2:
                return {
                    "reply": "Perdón, no capté tu usuario. Pasámelo de nuevo por favor 🙏",
                    "new_state": {"active_intent": "retiro", "flow_step": 1, "collected": collected},
                    "tag_keys_to_add": [], "handoff": False,
                }
            collected["user"] = text[:50]
            reply = _pick(RETIRO_ASK_AMOUNT_VARIANTS, salt).format(
                min=cfg["min_withdrawal"], max=cfg["max_withdrawal"]
            )
            return {
                "reply": reply,
                "new_state": {"active_intent": "retiro", "flow_step": 2, "collected": collected},
                "tag_keys_to_add": [], "handoff": False,
            }
        # Step 2: got amount
        if step == 2:
            m = re.search(r"[\d\.\,]+", text.replace(" ", ""))
            amount = None
            if m:
                try:
                    amount = float(m.group(0).replace(".", "").replace(",", "."))
                except Exception:
                    amount = None
            if amount is None:
                return {
                    "reply": "No entendí el monto — decímelo en números por favor. Ej: 5000",
                    "new_state": {"active_intent": "retiro", "flow_step": 2, "collected": collected},
                    "tag_keys_to_add": [], "handoff": False,
                }
            if amount < cfg["min_withdrawal"]:
                return {
                    "reply": f"El mínimo de retiro es ${cfg['min_withdrawal']:,.0f}. Decíme un monto mayor 🙏",
                    "new_state": {"active_intent": "retiro", "flow_step": 2, "collected": collected},
                    "tag_keys_to_add": [], "handoff": False,
                }
            if amount > cfg["max_withdrawal"]:
                return {
                    "reply": f"El máximo por retiro es ${cfg['max_withdrawal']:,.0f}. Podés hacer varios más chicos o esperar autorización del cajero.",
                    "new_state": {"active_intent": "retiro", "flow_step": 2, "collected": collected},
                    "tag_keys_to_add": [TAG_KEY_REVISAR], "handoff": True,
                }
            collected["amount"] = amount
            reply = _pick(RETIRO_ASK_CBU_VARIANTS, salt)
            return {
                "reply": reply,
                "new_state": {"active_intent": "retiro", "flow_step": 3, "collected": collected},
                "tag_keys_to_add": [], "handoff": False,
            }
        # Step 3: got CBU/alias
        if step == 3:
            candidate = re.sub(r"\s+", "", text)
            if len(candidate) < 3:
                return {
                    "reply": "Ese CBU/alias no parece válido. Repetímelo por favor 🙏",
                    "new_state": {"active_intent": "retiro", "flow_step": 3, "collected": collected},
                    "tag_keys_to_add": [], "handoff": False,
                }
            collected["cbu"] = candidate[:40]
            reply = _pick(RETIRO_ASK_HOLDER_VARIANTS, salt)
            return {
                "reply": reply,
                "new_state": {"active_intent": "retiro", "flow_step": 4, "collected": collected},
                "tag_keys_to_add": [], "handoff": False,
            }
        # Step 4: got holder, confirm + tag
        if step == 4:
            if len(text) < 3:
                return {
                    "reply": "Necesito el nombre completo del titular 🙏",
                    "new_state": {"active_intent": "retiro", "flow_step": 4, "collected": collected},
                    "tag_keys_to_add": [], "handoff": False,
                }
            collected["holder"] = text[:60]
            template = _pick(RETIRO_CONFIRM_VARIANTS, salt)
            reply = template.format(
                name_suffix=name_suf,
                user=collected.get("user", "?"),
                amount=collected.get("amount", 0),
                cbu=collected.get("cbu", "?"),
                holder=collected.get("holder", "?"),
            )
            return {
                "reply": reply,
                "new_state": {"active_intent": "retiro", "flow_step": 5, "collected": collected},
                "tag_keys_to_add": [TAG_KEY_RETIRO],
                "handoff": False,
            }
        # Already confirmed — quiet
        return None

    # ── NUEVO USUARIO ────────────────────────────────────────────
    if intent == "nuevo":
        cfg = merged_ai_config(user_doc)
        platforms = cfg.get("platforms") or []
        text = (newest_message.get("content") or "").strip()

        # Step 0: ask for full name
        if step == 0:
            reply = _pick(NUEVO_ASK_NAME_VARIANTS, salt).format(name_suffix=name_suf)
            return {
                "reply": reply,
                "new_state": {"active_intent": "nuevo", "flow_step": 1, "collected": collected},
                "tag_keys_to_add": [], "handoff": False,
            }
        # Step 1: got name → ask for platform (list if configured)
        if step == 1:
            if len(text) < 2:
                return {
                    "reply": "Perdón, no capté tu nombre. Decímelo por favor 🙏",
                    "new_state": {"active_intent": "nuevo", "flow_step": 1, "collected": collected},
                    "tag_keys_to_add": [], "handoff": False,
                }
            collected["name"] = text[:80]
            if platforms:
                plat_list = "\n".join(f"• {p}" for p in platforms)
                reply = NUEVO_ASK_PLATFORM_LIST_TEMPLATE.format(platform_list=plat_list)
            else:
                reply = _pick(NUEVO_ASK_PLATFORM_NO_LIST_VARIANTS, salt)
            return {
                "reply": reply,
                "new_state": {"active_intent": "nuevo", "flow_step": 2, "collected": collected},
                "tag_keys_to_add": [], "handoff": False,
            }
        # Step 2: got platform → confirm + tag
        if step == 2:
            if len(text) < 2:
                return {
                    "reply": "Decime la plataforma que preferís 🙏",
                    "new_state": {"active_intent": "nuevo", "flow_step": 2, "collected": collected},
                    "tag_keys_to_add": [], "handoff": False,
                }
            chosen = text[:40].strip()
            # If we have a configured list, ONLY accept an entry that
            # actually matches one of them (exact or bidirectional substring
            # on ≥3 chars, to tolerate typos like "1x bet" ↔ "1xbet").
            if platforms:
                low = chosen.lower()
                match = None
                for p in platforms:
                    pl = p.lower()
                    if pl == low or (len(pl) >= 3 and (pl in low or low in pl)):
                        match = p
                        break
                if not match:
                    # Nudge with the list again; do NOT advance.
                    plat_list = "\n".join(f"• {p}" for p in platforms)
                    return {
                        "reply": (
                            f"Perdón, no tenemos esa plataforma 🙈 Estas son las que manejamos:\n\n"
                            f"{plat_list}\n\n"
                            f"Decime cuál preferís 🙌"
                        ),
                        "new_state": {"active_intent": "nuevo", "flow_step": 2, "collected": collected},
                        "tag_keys_to_add": [], "handoff": False,
                    }
                chosen = match
            collected["platform"] = chosen
            template = _pick(NUEVO_CONFIRM_VARIANTS, salt)
            reply = template.format(
                name_suffix=name_suf,
                name=collected.get("name", "?"),
                platform=collected.get("platform", "?"),
            )
            return {
                "reply": reply,
                "new_state": {"active_intent": "nuevo", "flow_step": 3, "collected": collected},
                "tag_keys_to_add": [TAG_KEY_NUEVO],
                "handoff": False,
            }
        return None

    return None
