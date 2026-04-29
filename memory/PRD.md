# AdPhantom - Product Requirements Document

## Original Problem Statement
Aplicacion AdPhantom - CRM de WhatsApp con tracking de conversiones para Meta Pixel.

### Cambios Requeridos (Implementados)
1. **Gestion de usuarios desde UI admin**: Admin puede crear usuarios (admin/cajero), seleccionar lineas y configurar mensajes personalizados de bienvenida/usuario
2. **Fix de eventos Meta**: Quitado el fallback a variables de entorno (META_ACCESS_TOKEN, META_PIXEL_ID), solo se usa token/pixel de cada linea
3. **Rebranding a AdPhantom**: Logo, titulo, favicon actualizados
4. **Filtros de fecha en embudo**: Diario, semanal, mensual, o fecha especifica para cajeros y admins
5. **Trackeo de anuncios (utm_content)**: Asociar leads al anuncio de origen
6. **AI Tools en menu admin**: Generador de landing pages con IA (sin generacion de imagenes)
7. **Toggle de tema claro/oscuro**: Disponible para admin y cajero
8. **Audio messages**: Reproduccion de mensajes de audio de WhatsApp en el CRM
9. **CTWA Ad Tracking**: Tracking de Click-to-WhatsApp ads via referral y extraccion de texto (AD:xxxxx)
10. **External Landing Tracking**: Landing pages externas con tracking via URL params

## Architecture
- **Frontend**: React.js + Tailwind CSS
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **External APIs**: Meta Graph API (WhatsApp Business), Meta Pixel (Conversions API), Claude AI

## User Personas
1. **Admin**: Gestiona campanias, usuarios, lineas de WhatsApp, analytics, landing pages con IA
2. **Cajero**: Atiende leads de CRM, ve embudos filtrados por fecha, usa mensajes personalizados

## Core Requirements
- [x] Multi-linea WhatsApp con tracking independiente por linea
- [x] CRM tipo Kanban con estados (nuevo, spam, consultas, valido)
- [x] Envio de eventos de conversion a Meta Pixel por linea
- [x] Landing pages dinamicas con deteccion de bots
- [x] Gestion de usuarios con roles
- [x] Mensajes personalizados por usuario (bienvenida/usuario)
- [x] Audio message playback en CRM
- [x] CTWA ad tracking
- [x] Meta CAPI Purchase events con value/currency/content_type/event_id

## Key DB Schema
- `users`: {email, role, line_ids, welcome_message, user_message}
- `crm_lines`: {name, whatsapp_number, meta_pixel_id, meta_access_token}
- `crm_leads`: {phone, name, line_id, ad_source, referral, status, charge_amount, meta_events_sent}
- `wa_clicks`: {ip, user_agent, fbp, fbc, utm_content, click_id, landing_code}

## Key API Endpoints
- `POST /api/crm/leads/{lead_id}/classify`: Classify lead + send Meta event (Purchase/LowQualityLead)
- `POST /api/crm/leads/{lead_id}/send-conversion`: Manual Purchase event to Meta
- `POST /api/wa-landings/track-wa`: Landing page WA click → Lead/Contact CAPI events
- `GET /api/crm/funnel/stats`: Funnel statistics with date filters

## Critical Technical Notes
- NO trailing slashes on endpoints (causes 307 redirect on Railway)
- CRM statuses: nuevo, spam, consultas, valido (NOT cliente_real)
- Meta CAPI: Graph API v21.0, events include event_id for deduplication
- Purchase events MUST include: value (float), currency, content_type:"product"

## What's Been Implemented

### Date: 2026-04-19
- **Marketing Dashboard** (admin-only `/dashboard` reemplazado completo):
  - 7 endpoints nuevos (`/api/dashboard/*`): overview, ad-performance, demographics,
    geography, timeline, hourly-heatmap, device-stats.
  - Filtros: selector de línea (todas o específica) + preset fechas (hoy/7/30/90d).
  - Auto-refresh cada 60s.
  - KPI cards (Leads, Conversiones, Tasa, Ingresos, Ticket) con delta vs período anterior.
  - Insights automáticos (mejor género convertidor, mejor provincia).
  - Gráficos recharts: timeline de área, pie de género, bar de edad, bars horizontales
    top provincias/ciudades, heatmap día×hora, pie de dispositivos.
  - Tabla de anuncios con thumbnail del CTWA (si hay `referral.image_url`),
    headline, conversión, ingresos, ticket promedio.
- **Cajero simplificado**: sacado `AdPerformanceDashboard` del modal de embudo.
  Solo admin ve rendimiento por anuncio en `/dashboard`.
- **Currency por deployment**: `PURCHASE_CURRENCY` env var (USD/ARS) controla
  la moneda de Purchase events (override global; ignora lo que venga del frontend).
- **Audio Android fix**: transcoding webm → ogg/opus vía ffmpeg (Meta Cloud API
  rechaza webm). Requiere `ffmpeg` en el server (Dockerfile: `apt-get install ffmpeg`).
- **Audio/image endpoints públicos**: `/api/crm/chat-audio/{uuid}` y
  `/api/crm/chat-image/{uuid}` — filenames UUID son unguessables. Permite que
  `<audio>` y `<img>` nativos puedan cargar sin header Authorization.

### Date: 2026-04-18
- **PWA Mobile Layout (WhatsApp-style)**: Cajero view on mobile (`<768px`)
  now renders as a true stack-nav: full-width contact list → tap → full-screen
  chat with back arrow (⬅) → return to list. List and chat are mutually
  exclusive on mobile, whereas desktop retains the split-pane view.
  - Added `showBackButton` + `onBack` props to `ChatPanel`.
  - `LeadsCRM` toggles `display: hidden/flex` on list/chat containers based on
    `isMobile && selectedLead`.
- **Refactor of `LeadsCRM.js`** (was ~2300 lines → now ~800): extracted
  reusable components to `/app/frontend/src/pages/leads-crm/`:
  - `constants.js` (STATUS_CONFIG, BADGE_COLORS, etc.)
  - `utils.js` (formatTime, formatRelative)
  - `StatusSelector.jsx` (StatusBadge + dropdown)
  - `ImageLightbox.jsx`
  - `ChatMessage.jsx`
  - `AdPreviewCard.jsx`
  - `ChatListItem.jsx`
  - `ChatPanel.jsx` (chat view with back button support)
  - `BroadcastModal.jsx`

### Date: 2026-04-03
- User management (CRUD) with role-based access
- Personalized messages per cajero
- Date filters on funnel stats
- Ad performance dashboard (utm_content tracking)
- Theme toggle (dark/light)
- Rebranding to AdPhantom
- Audio message playback
- CTWA ad tracking
- External landing page tracking
- Marketing landing page

### Date: 2026-04-07
- **FIX P0**: Meta CAPI Purchase event payload restructured:
  - Added `event_id` for deduplication across all CAPI events
  - Added `content_type: "product"` to all Purchase events
  - Updated Graph API from v18.0 to v21.0
  - Explicit `float()` casting for `value` parameter
  - Detailed logging: value, currency, fbp, fbc, phone, pixel, event_id
- **FIX**: Manual conversion endpoint checked `cliente_real` instead of `valido` — corrected
- **FIX**: Old classify endpoint hardcoded `value: 0` — now uses `charge_amount`
- **FIX P1**: Verified Landing Page Lead/Contact CAPI events include fbp, fbc, client_ip, user_agent
- **NEW**: Panel "Diagnostico Meta" — dashboard en tiempo real de eventos CAPI con stats, config de lineas, filtros y auto-refresh

### Date: 2026-04-29 (Iteration 10 — Auto-resend Worker)

**Backend:**
- Nueva función `_csv_campaign_resend(campaign_id)` — segundo pase automático de la campaña.
- Cuando el primer pase termina, si la campaña tiene `resend_after_hours + resend_template_name`, se queue una task que:
  1. Duerme hasta `completed_at + N horas`
  2. Selecciona contactos cuyo mensaje quedó en status `sent` o `delivered` AND sin `replied_at`
  3. Re-envía con `resend_template_name`, mismas reglas anti-spam (cauta 30-90s + pausa nocturna + auto-pause on rate-limit)
  4. Marca cada nuevo mensaje con `is_resend: True` para evitar re-re-envío
  5. Stats separados: `stats.resent`, `stats.resend_failed`, `stats.resend_skipped_optout`
- Resume automático al boot: si el server se reinicia mientras durmiendo, `_resume_scheduled_campaigns` re-arma los pendientes.
- Excluye los que ya respondieron o leyeron (esos no necesitan re-envío) y los optouts (re-chequea en runtime).

**Frontend:**
- Wizard paso 3: nueva sección "Auto re-envío (opcional)" con input de horas (1-168) + selector de plantilla (excluye la principal para forzar usar otra).
- Lista de campañas: badge cyan "Re-envío en Nh" (con "(hecho)" cuando termina) y stat-pill `re-enviados` cuando `stats.resent > 0`.
- Validación: tira warning ámbar si configurás horas pero no plantilla (o viceversa).

**Test de regresión** `test_auto_resend_only_to_unread_unanswered`:
- Setup: 4 contactos, primer pase envía a todos. Simulamos: 1 sigue `sent`, 1 `delivered`, 1 `read`, 1 `replied`.
- Verifica: el resend dispara solo a 2 (sent + delivered sin reply). Los 2 nuevos `broadcast_messages` tienen `is_resend: True`. `stats.resent = 2`. `resend_done_at` se setea.
- 4/4 grupos de tests del engine pasan.

### Date: 2026-04-29 (Iteration 9 — Templates Creator)

**Backend:**
- `wa_create_template(waba_id, token, ...)` — POSTea a `/{waba_id}/message_templates` en Meta Graph API y devuelve la respuesta (status: APPROVED/PENDING/REJECTED). Valida formato antes de enviar.
- `wa_delete_template(waba_id, token, name)` — DELETE en Graph API.
- Nuevo endpoint `POST /api/broadcasts/templates/create` (permisos per-line) — valida nombre snake_case, cantidad de example vars igual a `{{n}}` en body, categoría (MARKETING/UTILITY/AUTHENTICATION). Traduce errores de Meta a un mensaje user-friendly.
- Nuevo endpoint `DELETE /api/broadcasts/templates?line_id=X&name=Y`.
- Endpoint `GET /api/broadcasts/templates` agregó flag `include_all=true` para mostrar también PENDING/REJECTED (para que el cajero vea el status en el editor).

**Frontend:**
- Nuevo tab **Plantillas** en `/broadcasts`.
- Lista de plantillas por línea con status coloreado (Aprobada verde / Pendiente ámbar / Rechazada roja), muestra `rejected_reason` cuando falla.
- Modal "Crear plantilla": selector de línea + idioma + categoría, input de nombre con auto-slugify a snake_case, textarea con detección automática de `{{1}}`, `{{2}}`... → genera dinámicamente los inputs de ejemplo que Meta exige.
- Tips para que Meta apruebe (lenguaje no-gambling, opt-out incluido, ejemplos reales).
- Borrar plantilla con confirm.

**Limitaciones conocidas** (Meta, no nuestras):
- Category MARKETING tiene cooldown de 24hs si rechazan.
- Gambling explícito suele rechazarse → el modal incluye tips proactivos.
- Plantillas son per-WABA, no per-línea. Si varias líneas comparten WABA comparten plantillas.

### Date: 2026-04-28 (Iteration 8 — CSV Mass Broadcasts feature)

**Backend (Deliverable 1 + 2 — 7/7 + 9/9 tests pasando):**
- `wa_send_template()` y `wa_fetch_templates()` para mensajes templated Meta (OBLIGATORIO para mass a contactos nuevos fuera del 24h window).
- Campo `whatsapp_business_account_id` agregado a `crm_lines` (necesario para fetch de templates).
- Auto opt-out: si un contacto responde "BAJA / STOP / NO / CANCELAR / BAJAR / NO QUIERO MAS / REMOVER / UNSUBSCRIBE", se agrega a `broadcast_optouts` automáticamente (per-line).
- Status updates de WA webhook (sent/delivered/read) → actualizan `broadcast_messages` y los counters de `broadcast_campaigns.stats`.
- Reply tracking: cuando un contacto responde a un broadcast, `replied` counter +=1 en la campaña.
- **Endpoints**: `GET/POST/DELETE /api/broadcasts/audiences`, `GET /api/broadcasts/templates?line_id=X`, `GET/POST/DELETE /api/broadcasts/optouts`, `POST /api/broadcasts/segments/preview`, `GET/POST /api/broadcasts/campaigns`, `POST /api/broadcasts/campaigns/{id}/{start,pause,cancel}`.
- **Permisos**: cajeros solo ven/manejan SUS line_ids; admin ve todo.
- **Worker `_csv_campaign_worker`**: velocidad FIJA cauta (30-90s aleatorio entre mensajes), pausa nocturna FIJA 23:00-09:00 ART, auto-pausa si Meta rate-limit (codes 131056/80007/OAuth). Resume si reinicio: levanta running + scheduled al boot.
- **Segmentación**: filtros por status, "compraron en últimos N días" (status=valido + status_changed_at), "respondieron / no respondieron en últimos N días". Excluye optouts en runtime.
- **Auto-resend** infrastructure: campos `resend_after_hours` + `resend_template_name` en campañas (UI implementada, worker a completar en próxima iteración).

**Frontend (Deliverable 3):**
- Nueva ruta `/broadcasts` accesible para admin + cajeros.
- 3 tabs: Audiencias, Campañas, Opt-outs.
- CSV Uploader con preview de columnas válidas y stats post-upload.
- Wizard de campaña 3-pasos: (1) línea + nombre + audiencia/segmento → (2) plantilla aprobada Meta + mapeo de variables → (3) confirmar + programar opcional.
- Dashboard live de campañas: progress bar, stats (sent/delivered/read/replied/failed/optouts skipped), control Iniciar/Pausar/Reanudar/Cancelar, auto-refresh 5s cuando hay running.
- Opt-outs: lista + agregar manual + remover, con scoping per-line.
- **Bug fix crítico**: `import asyncio` faltaba a nivel módulo en `server.py` — todas las llamadas `asyncio.create_task` y `asyncio.sleep` del nuevo engine habrían fallado. Detectado y arreglado durante los tests.

### Date: 2026-04-28 (Iteration 7 — EMQ Score por Línea Dashboard)
- **NEW**: Endpoint `GET /api/crm/emq/by-line?days=7` agrupa eventos de `meta_events_log` por línea con tier breakdown (12+, 10-11, 8-9, <8 params), `signals` (fbp/fbc/email %), success_rate, avg_emq_score weighted, y los 3 parámetros que más se pierden por línea.
- **NEW**: Sección "EMQ Score por Línea" en el tab Event Match Quality de `/meta-insights`. Barra global apilada con counts + lista por línea con barra coloreada (verde/azul/ámbar/rojo) y diagnóstico (fbp%, fbc%, email%, OK%, falta: ...).
- Permite detectar al toque qué línea/landing está perdiendo señal Meta (ej: una landing donde se pierde el fbp aparece en rojo con "falta: fbp, fbc, em").

### Date: 2026-04-28 (Iteration 6 — UI fixes + EMQ enrichment A+B+C+E)

**UI fixes:**
- **FIX**: Botón "Validar venta" ahora abre modal centrado (z-60) en lugar de banner inline → resuelve el problema de que el recuadro quedaba detrás del chat y no se podía clickear "Confirmar".
- **FIX**: Refocus del textarea después de enviar mensaje. La llamada a `inputRef.current.focus()` se movió al `finally` con timeout de 60ms, después de que `setSending(false)` corre, así el browser realmente acepta el focus (antes lo descartaba porque el textarea seguía `disabled`).
- **FIX**: Hamburguesa movida de `top-[72px] left-3` a `top-[100px] left-2` (más abajo, fuera del search input). El input "Buscar..." ahora tiene `md:ml-10` para no superponerse en desktop.

**Meta CAPI / EMQ enrichment (sin fricción UX, todo automático y gratis):**
- **A) Browser fingerprint visitor_id**: JS custom inline en cada landing (canvas + WebGL + audio context + screen + timezone + hardware → SHA-256). Persistido en `localStorage.ad_vid` y enviado al backend en `/wa-landings/track` y `/wa-landings/track-wa`. Almacenado en `wa_clicks.visitor_id`. Agregado al array `user_data.external_id` (Meta acepta múltiples) junto al hash del teléfono → 2 señales estables por evento.
- **B) Cross-session signal recovery**: Cuando un lead llega directo por WhatsApp y faltan IP/UA/fbp/fbc/visitor_id en su `click_data`, el backend busca el `wa_clicks` histórico más reciente que matchee phone tail (10 dígitos) o visitor_id, y rellena los huecos. Recupera EMQ de leads que antes iban con user_data incompleto.
- **C) Enriched `custom_data` en Purchase**: Agregados automáticamente `order_id` (= `{lead_id}-{YYYYMMDD}` para dedupe perfecto), `content_ids: [line_id]`, `content_name: nombre_línea` (resuelto vía `crm_lines`), `content_category: "credits"`, `num_items: 1`, `delivery_category: "home_delivery"`. Mejora attribution + dedupe de Meta.
- **E) Geo cache persistente**: `_geo_cache` ahora respaldado en colección Mongo `geo_cache` (key=IP). Cada IP se resuelve UNA sola vez en su vida, sobrevive a reinicios → ahorra requests al límite gratuito de ip-api.com (45/min).
- **NEW DB collections/fields**: `wa_clicks.visitor_id`, `geo_cache` collection ({_id: ip, data, cached_at}).
- **Tests**: `/app/backend/tests/test_emq_enrichment.py` — 4/4 passing (A, B, C, E).

### Date: 2026-04-26 (Iteration 5)
- **NEW**: Historial unificado por teléfono — `/api/crm/leads/{lead_id}/messages` ahora agrega los mensajes de TODOS los leads que comparten el mismo `phone` (parámetro `unified=true` por defecto). Cuando un cliente vuelve por otra línea, el cajero ve la conversación previa completa en orden cronológico. Param `?unified=false` para forzar el comportamiento clásico.
- **NEW**: Auto-scroll inteligente en ChatPanel — el refresh automático de 5s ya NO arrastra al cajero al fondo si está leyendo mensajes anteriores. Pill flotante `↓ N nuevos` aparece cuando llegan mensajes mientras está scrolleado arriba (cuenta solo mensajes entrantes). Click → vuelve al fondo y resetea el contador. Al enviar un mensaje propio fuerza scroll-to-bottom.
- **NEW**: Link real del anuncio en Ad Preview — cuando el referral de Meta no trae `source_url`, se construye fallback a Meta Ads Library (`https://www.facebook.com/ads/library/?id={source_id}`). Si trae ambos, se muestran como dos botones: `Ver anuncio` (URL real del post) y `Ads Library` (secundario). El `source_id` se muestra como chip `ID: {id}`.
- **FIX**: Cap de `/api/crm/leads` subido de 200 a 500 para honrar el feature "últimos 500 leads".

## Prioritized Backlog
### P1 (High)
- [ ] Verificar funcionamiento completo de tema claro (light mode) en todas las paginas

### P2 (Medium)
- [x] Notificaciones push para nuevos mensajes (Web Push / Service Worker)
- [x] Refactorizacion de LeadsCRM.js (~2300 lineas) en componentes separados
- [x] Historial unificado por teléfono
- [x] Auto-scroll inteligente
- [x] Link real del anuncio
- [ ] Exportacion de datos a CSV (pendiente para más colecciones; agenda contactos ya hecha)
- [ ] Refactorizacion de server.py (~6500 lineas) en routers/servicios separados
- [ ] Indicador "escribiendo..." en el chat

### P3 (Low)
- [ ] Configurar API key de Claude para AI Tools
- [ ] Testing completo de flujo de trackeo de anuncios E2E
