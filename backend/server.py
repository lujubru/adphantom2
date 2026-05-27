from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Query, Response, Body
from fastapi.responses import RedirectResponse, HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
import re
import hashlib
import string
import random
import base64
import json
import httpx
import bcrypt

# Meta CAPI Parameter Builder (official Facebook SDK)
# Enhances fbc/fbp with server-side appendix (+~0.7 EMQ points, removes
# "modified fbclid" warning). Used when building CAPI user_data.
try:
    from capi_param_builder import ParamBuilder as _MetaParamBuilder
    _PARAM_BUILDER_AVAILABLE = True
except ImportError:
    _MetaParamBuilder = None
    _PARAM_BUILDER_AVAILABLE = False

if not hasattr(bcrypt, '__about__'):
    bcrypt.__about__ = type('about', (), {'__version__': bcrypt.__version__})()
    
ROOT_DIR = Path(__file__).parent
env_file = ROOT_DIR / '.env'
if env_file.exists():
    load_dotenv(env_file, override=False)

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'traffic_guardian')
client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
db = client[db_name]


# Config
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-min-32-chars')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', '')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN', '')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', '')
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN', 'traffic_guardian_verify_2024')

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12, bcrypt__ident="2b")

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Traffic Guardian API", version="1.0.0", redirect_slashes=False)
api_router = APIRouter(prefix="/api")

# ─── Pydantic Models ───────────────────────────────────────────────

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class CampaignCreate(BaseModel):
    name: str
    target_url: str
    safe_page_url: Optional[str] = ""
    is_active: bool = True
    daily_click_limit: int = 10000
    allowed_countries: List[str] = []
    allowed_devices: List[str] = []
    allowed_os: List[str] = []
    block_empty_referrer: bool = False
    blacklist_ips: List[str] = []
    whitelist_ips: List[str] = []
    landing_html: Optional[str] = ""
    whatsapp_number: Optional[str] = ""
    whatsapp_message: Optional[str] = ""
    meta_verification: Optional[str] = ""

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    target_url: Optional[str] = None
    safe_page_url: Optional[str] = None
    is_active: Optional[bool] = None
    daily_click_limit: Optional[int] = None
    allowed_countries: Optional[List[str]] = None
    allowed_devices: Optional[List[str]] = None
    allowed_os: Optional[List[str]] = None
    block_empty_referrer: Optional[bool] = None
    blacklist_ips: Optional[List[str]] = None
    whitelist_ips: Optional[List[str]] = None
    landing_html: Optional[str] = None
    whatsapp_number: Optional[str] = None
    whatsapp_message: Optional[str] = None
    meta_verification: Optional[str] = None

class FilterCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    action: str = "block"
    priority: int = 0
    is_active: bool = True
    conditions: Dict = {}

class FilterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    action: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    conditions: Optional[Dict] = None

class AIPageCreate(BaseModel):
    prompt: str
    campaign_id: Optional[str] = None

class AIRuleToggle(BaseModel):
    is_active: bool

# ─── Auth Helpers ──────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

async def get_current_user(request: Request):
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ─── Traffic Inspector ─────────────────────────────────────────────

# Meta/Facebook known IP ranges (prefixes)
META_IP_PREFIXES = (
    '173.252.', '31.13.', '69.171.', '66.220.', '157.240.',
    '179.60.', '185.60.', '204.15.20.', '69.63.', '199.201.64.',
    '199.201.65.', '204.15.20.', '2a03:2880:',
)

BOT_PATTERNS = re.compile(
    r'bot|crawl|spider|scrape|meta-externalagent|facebookexternalhit|facebot|'
    r'twitterbot|linkedinbot|pinterest|slackbot|telegram|'
    r'googlebot|bingbot|yandex|baidu|duckduck|monitoring|checker|validator|preview|fetcher',
    re.IGNORECASE
)
META_PATTERNS = re.compile(
    r'meta-externalagent|facebookexternalhit|facebot',
    re.IGNORECASE
)

def is_meta_ip(ip: str) -> bool:
    """Check if IP belongs to Meta/Facebook infrastructure"""
    return any(ip.startswith(prefix) for prefix in META_IP_PREFIXES)

def is_bot(user_agent: str) -> bool:
    if not user_agent:
        return True
    return bool(BOT_PATTERNS.search(user_agent))

def is_meta_crawler(user_agent: str) -> bool:
    if not user_agent:
        return False
    return bool(META_PATTERNS.search(user_agent))

def parse_device_info(user_agent: str):
    if not user_agent:
        return "Unknown", "Unknown", "Unknown"
    try:
        from user_agents import parse as ua_parse
        ua = ua_parse(user_agent)
        device = "Mobile" if ua.is_mobile else "Tablet" if ua.is_tablet else "Bot" if ua.is_bot else "Desktop"
        os_name = ua.os.family or "Unknown"
        browser = ua.browser.family or "Unknown"
        return device, os_name, browser
    except Exception:
        return "Unknown", "Unknown", "Unknown"

def calculate_behavioral_score(is_bot_flag: bool, is_vpn: bool, is_datacenter: bool, has_referrer: bool, user_agent: str) -> float:
    score = 100.0
    if is_bot_flag:
        score -= 50
    if is_vpn:
        score -= 20
    if is_datacenter:
        score -= 15
    if not has_referrer:
        score -= 10
    if not user_agent or len(user_agent) < 20:
        score -= 15
    return max(0.0, score)

def detect_vpn(headers: dict) -> bool:
    # Disabled auto VPN detection - Railway/Cloudflare proxies cause false positives
    # Real VPN detection would require an IP intelligence API
    return False

def should_block(config: dict, ip: str, country: str, device: str, os_name: str, referrer: str, bot: bool, vpn: bool):
    if config.get('whitelist_ips') and ip in config['whitelist_ips']:
        return False, ""
    # Never block Meta/Facebook IPs - they're real users from Meta ads or crawlers
    if is_meta_ip(ip):
        return False, ""
    if ip in config.get('blacklist_ips', []):
        return True, "IP en lista negra"
    # Only block explicit bots (Googlebot, scrapers, etc.) - not mobile users
    if bot and not any(m in (device or '') for m in ('Mobile', 'Tablet', 'Desktop')):
        return True, "Bot detectado"
    if config.get('block_empty_referrer') and not referrer:
        return True, "Referrer vacío bloqueado"
    allowed_countries = config.get('allowed_countries', [])
    # Skip country check if no real GeoIP (country = "XX")
    if allowed_countries and country != "XX" and country not in allowed_countries:
        return True, f"País {country} no permitido"
    allowed_devices = config.get('allowed_devices', [])
    if allowed_devices and device not in allowed_devices:
        return True, f"Dispositivo {device} no permitido"
    allowed_os = config.get('allowed_os', [])
    if allowed_os and os_name not in allowed_os:
        return True, f"SO {os_name} no permitido"
    return False, ""

def generate_fingerprint(ip: str, user_agent: str, headers: dict) -> str:
    raw = f"{ip}|{user_agent}|{headers.get('accept-language', '')}|{headers.get('accept-encoding', '')}"
    return hashlib.sha256(raw.encode()).hexdigest()

def generate_short_code(length=7) -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # x-forwarded-for can carry multiple IPs; take the first (original client)
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    # cf-connecting-ipv6 is sent by Cloudflare when client connects over IPv6
    cf_ipv6 = request.headers.get("cf-connecting-ipv6")
    if cf_ipv6:
        return cf_ipv6
    return request.client.host if request.client else "0.0.0.0"

def normalize_ip_for_meta(ip: str) -> str:
    """
    Meta prefers IPv6. If we have a plain IPv4 address, map it to
    IPv4-mapped IPv6 notation (::ffff:x.x.x.x) so Meta can use it for
    better event matching. Pure IPv6 addresses are returned unchanged.
    """
    if not ip or ip in ("0.0.0.0", "unknown"):
        return ip
    import ipaddress
    try:
        addr = ipaddress.ip_address(ip)
        if isinstance(addr, ipaddress.IPv4Address):
            # Map to IPv4-mapped IPv6: ::ffff:x.x.x.x
            return str(ipaddress.IPv6Address(f"::ffff:{ip}"))
        # Already IPv6
        return str(addr)
    except ValueError:
        return ip


def _meta_param_builder_process(fbc: Optional[str], fbp: Optional[str], event_source_url: Optional[str] = None) -> tuple:
    """Pass fbc/fbp through Meta's official Parameter Builder SDK.

    Adds the server-side appendix (e.g. 'fb.1.<ts>.<fbclid>.AQIAAQEC') which
    Meta uses to attribute server-side events correctly. Boosts EMQ by ~0.7
    and eliminates the 'modified fbclid' warning in Events Manager.

    Returns (fbc, fbp) — either the processed values with appendix, or the
    originals unchanged if the SDK is unavailable or processing fails.
    """
    if not _PARAM_BUILDER_AVAILABLE or (not fbc and not fbp):
        return fbc, fbp
    try:
        domain = event_source_url or "https://blackguardian.tech/"
        # Feed existing values as cookies so the SDK validates+appends the suffix
        cookie_dict = {}
        if fbc:
            cookie_dict["_fbc"] = fbc
        if fbp:
            cookie_dict["_fbp"] = fbp
        pb = _MetaParamBuilder(["blackguardian.tech"])
        pb.process_request(domain, {}, cookie_dict, None)
        processed_fbc = pb.get_fbc() if fbc else None
        processed_fbp = pb.get_fbp() if fbp else None
        return processed_fbc or fbc, processed_fbp or fbp
    except Exception as e:
        # Never break CAPI because of the SDK — log and fall back to originals
        logger.warning(f"Meta ParamBuilder processing failed: {e}")
        return fbc, fbp

SAFE_PAGE_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Página No Encontrada</title>
<style>body{font-family:sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:#1e293b;color:white;}
.c{text-align:center;}h1{font-size:4rem;margin:0;}p{font-size:1.5rem;}</style></head>
<body><div class="c"><h1>404</h1><p>Página no encontrada</p></div></body></html>"""

# ─── Auth Routes ───────────────────────────────────────────────────

@api_router.post("/auth/login")
async def login(user_data: UserLogin):
    user = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    try:
        pw = user_data.password
        if len(pw.encode('utf-8')) > 72:
            pw = pw.encode('utf-8')[:72].decode('utf-8')
        if not pwd_context.verify(pw, user["hashed_password"]):
            raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    except Exception:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    token = create_access_token(data={"sub": user["email"]})
    return {"access_token": token, "token_type": "bearer"}

@api_router.get("/auth/me")
async def get_me(current_user=Depends(get_current_user)):
    return {
        "email": current_user["email"],
        "is_active": current_user.get("is_active", True),
        "role": current_user.get("role", "admin"),
        "line_ids": current_user.get("line_ids", []),
        "welcome_message": current_user.get("welcome_message", ""),
        "user_message": current_user.get("user_message", ""),
        "auto_welcome_enabled": current_user.get("auto_welcome_enabled", True),
        "derivation_message": current_user.get("derivation_message", ""),
        "derivation_numbers": current_user.get("derivation_numbers", []),
        "cbu_list": current_user.get("cbu_list", []),
        "broadcast_monthly_quota": int(current_user.get("broadcast_monthly_quota", 0) or 0),
    }


@api_router.get("/auth/me/welcome-variant")
async def get_welcome_variant(current_user=Depends(get_current_user)):
    """Return a rotated/humanized variant of the current cajero's welcome.

    Used by the "👋 Bienvenida" button in the chat panel so that each manual
    click produces a different phrasing (prevents Meta from flagging the
    exact-same-message pattern when cajeros send manually).
    """
    raw = (current_user.get("welcome_message") or "").strip()
    if not raw:
        return {"message": ""}
    return {"message": _pick_welcome_variation(raw)}
def _sanitize_cbu_list(raw) -> List[Dict]:
    """Keep only entries with a non-empty CBU; trim whitespace on cbu and name."""
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        cbu = str(item.get("cbu") or "").strip()
        name = str(item.get("name") or "").strip()
        if cbu:
            out.append({"cbu": cbu, "name": name})
    return out


class UserCreate(BaseModel):
    email: str
    password: str
    role: str = "cajero"
    line_ids: List[str] = []
    welcome_message: Optional[str] = ""
    user_message: Optional[str] = ""
    auto_welcome_enabled: Optional[bool] = True
    derivation_message: Optional[str] = ""
    derivation_numbers: Optional[List[str]] = []
    cbu_list: Optional[List[Dict]] = []  # [{cbu: "...", name: "..."}]
    broadcast_monthly_quota: Optional[int] = 0  # 0 = sin permiso de broadcasts; >0 = cupo base mensual

class UserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    line_ids: Optional[List[str]] = None
    welcome_message: Optional[str] = None
    user_message: Optional[str] = None
    is_active: Optional[bool] = None
    auto_welcome_enabled: Optional[bool] = None
    derivation_message: Optional[str] = None
    derivation_numbers: Optional[List[str]] = None
    cbu_list: Optional[List[Dict]] = None
    broadcast_monthly_quota: Optional[int] = None

@api_router.post("/auth/users")
async def create_user(data: UserCreate, current_user=Depends(get_current_user)):
    if current_user.get("role") not in (None, "admin"):
        raise HTTPException(status_code=403, detail="Sin permisos")
    existing = await db.users.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    hashed = pwd_context.hash(data.password)
    await db.users.insert_one({
        "id": str(uuid.uuid4()),
        "email": data.email,
        "hashed_password": hashed,
        "role": data.role,
        "line_ids": data.line_ids,
        "welcome_message": data.welcome_message or "",
        "user_message": data.user_message or "",
        "auto_welcome_enabled": data.auto_welcome_enabled if data.auto_welcome_enabled is not None else True,
        "derivation_message": data.derivation_message or "",
        "derivation_numbers": [n.strip() for n in (data.derivation_numbers or []) if n and n.strip()],
        "cbu_list": _sanitize_cbu_list(data.cbu_list or []),
        "broadcast_monthly_quota": int(data.broadcast_monthly_quota or 0),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"message": f"Usuario {data.email} creado con rol {data.role}", "line_ids": data.line_ids}

@api_router.get("/auth/users")
async def get_all_users(current_user=Depends(get_current_user)):
    """Get all users (admin only)"""
    if current_user.get("role") not in (None, "admin"):
        raise HTTPException(status_code=403, detail="Sin permisos")
    users = await db.users.find({}, {"_id": 0, "hashed_password": 0}).to_list(100)
    # Add line names for each user
    for user in users:
        line_names = []
        for line_id in user.get("line_ids", []):
            line = await db.crm_lines.find_one({"id": line_id}, {"_id": 0, "name": 1})
            if line:
                line_names.append(line["name"])
        user["line_names"] = line_names
    return users

@api_router.get("/auth/users/{user_id}")
async def get_user(user_id: str, current_user=Depends(get_current_user)):
    """Get a specific user (admin only)"""
    if current_user.get("role") not in (None, "admin"):
        raise HTTPException(status_code=403, detail="Sin permisos")
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "hashed_password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user

@api_router.put("/auth/users/{user_id}")
async def update_user(user_id: str, data: UserUpdate, current_user=Depends(get_current_user)):
    """Update a user (admin only)"""
    if current_user.get("role") not in (None, "admin"):
        raise HTTPException(status_code=403, detail="Sin permisos")
    existing = await db.users.find_one({"id": user_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    update_data = {}
    for k, v in data.model_dump(exclude_unset=True).items():
        if k == "password" and v:
            update_data["hashed_password"] = pwd_context.hash(v)
        elif k == "password":
            # Empty password → skip (don't overwrite existing)
            continue
        elif k == "derivation_numbers" and v is not None:
            # Sanitize list: trim and drop empties
            update_data[k] = [n.strip() for n in v if n and n.strip()]
        elif k == "cbu_list" and v is not None:
            update_data[k] = _sanitize_cbu_list(v)
        elif k == "broadcast_monthly_quota" and v is not None:
            try:
                update_data[k] = max(0, int(v))
            except (TypeError, ValueError):
                update_data[k] = 0
        else:
            # Allow False/0/"" through — only `None` means "no change".
            # exclude_unset already drops fields not present in the request.
            if v is not None or k in ("auto_welcome_enabled",):
                update_data[k] = v
    
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.users.update_one({"id": user_id}, {"$set": update_data})
    
    updated = await db.users.find_one({"id": user_id}, {"_id": 0, "hashed_password": 0})
    return updated

@api_router.delete("/auth/users/{user_id}")
async def delete_user(user_id: str, current_user=Depends(get_current_user)):
    """Delete a user (admin only)"""
    if current_user.get("role") not in (None, "admin"):
        raise HTTPException(status_code=403, detail="Sin permisos")
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"message": "Usuario eliminado"}
# ─── Campaign Routes ──────────────────────────────────────────────

@api_router.get("/campaigns")
async def get_campaigns(current_user=Depends(get_current_user)):
    campaigns = await db.campaigns.find({}, {"_id": 0}).to_list(1000)
    return campaigns

@api_router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, current_user=Depends(get_current_user)):
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    return campaign

@api_router.post("/campaigns")
async def create_campaign(data: CampaignCreate, current_user=Depends(get_current_user)):
    now = datetime.now(timezone.utc).isoformat()
    # Generate unique short code
    short_code = generate_short_code()
    while await db.campaigns.find_one({"short_code": short_code}):
        short_code = generate_short_code()
    campaign = {
        "id": str(uuid.uuid4()),
        "short_code": short_code,
        "name": data.name,
        "target_url": data.target_url,
        "safe_page_url": data.safe_page_url or "",
        "is_active": data.is_active,
        "daily_click_limit": data.daily_click_limit,
        "clicks_today": 0,
        "total_clicks": 0,
        "allowed_countries": data.allowed_countries,
        "allowed_devices": data.allowed_devices,
        "allowed_os": data.allowed_os,
        "block_empty_referrer": data.block_empty_referrer,
        "blacklist_ips": data.blacklist_ips,
        "whitelist_ips": data.whitelist_ips,
        "landing_html": data.landing_html or "",
        "whatsapp_number": data.whatsapp_number or "",
        "whatsapp_message": data.whatsapp_message or "",
        "meta_verification": data.meta_verification or "",
        "created_at": now,
        "updated_at": now,
    }
    await db.campaigns.insert_one(campaign)
    campaign.pop("_id", None)
    return campaign

@api_router.put("/campaigns/{campaign_id}")
async def update_campaign(campaign_id: str, data: CampaignUpdate, current_user=Depends(get_current_user)):
    existing = await db.campaigns.find_one({"id": campaign_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.campaigns.update_one({"id": campaign_id}, {"$set": update_data})
    updated = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    return updated

@api_router.delete("/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: str, current_user=Depends(get_current_user)):
    result = await db.campaigns.delete_one({"id": campaign_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    return {"message": "Campaña eliminada"}

@api_router.post("/campaigns/{campaign_id}/reset-clicks")
async def reset_daily_clicks(campaign_id: str, current_user=Depends(get_current_user)):
    result = await db.campaigns.update_one({"id": campaign_id}, {"$set": {"clicks_today": 0}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    return {"message": "Clicks diarios reseteados"}

# ─── WhatsApp Landing Template ─────────────────────────────────────

class WALandingRequest(BaseModel):
    whatsapp_number: str
    whatsapp_message: Optional[str] = ""
    title: Optional[str] = "Contáctanos"
    subtitle: Optional[str] = "Haz click para escribirnos por WhatsApp"
    button_text: Optional[str] = "Escribir por WhatsApp"
    color: Optional[str] = "#25D366"

def generate_wa_landing_html(wa_number: str, wa_message: str = "", title: str = "Contáctanos",
                              subtitle: str = "Haz click para escribirnos por WhatsApp",
                              button_text: str = "Escribir por WhatsApp", color: str = "#25D366",
                              meta_verification: str = "") -> str:
    wa_url = f"https://wa.me/{wa_number}"
    if wa_message:
        from urllib.parse import quote
        wa_url += f"?text={quote(wa_message)}"
    meta_tag = f'<meta name="facebook-domain-verification" content="{meta_verification}" />' if meta_verification else ""
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {meta_tag}
    <meta property="og:title" content="{title}" />
    <meta property="og:description" content="{subtitle}" />
    <meta property="og:type" content="website" />
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; min-height: 100vh;
               display: flex; align-items: center; justify-content: center;
               background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%); color: #fff; }}
        .card {{ background: rgba(30, 41, 59, 0.95); border-radius: 24px; padding: 48px 40px; max-width: 440px;
                width: 90%; text-align: center; box-shadow: 0 25px 60px rgba(0,0,0,0.4);
                border: 1px solid rgba(255,255,255,0.08); }}
        .wa-icon {{ width: 80px; height: 80px; margin: 0 auto 24px; background: {color}; border-radius: 50%;
                   display: flex; align-items: center; justify-content: center;
                   animation: pulse 2s infinite; }}
        @keyframes pulse {{ 0%,100% {{ transform: scale(1); }} 50% {{ transform: scale(1.08); }} }}
        .wa-icon svg {{ width: 44px; height: 44px; fill: white; }}
        h1 {{ font-size: 1.75rem; margin-bottom: 12px; font-weight: 700; }}
        p {{ color: #94a3b8; font-size: 1.05rem; margin-bottom: 24px; line-height: 1.6; }}
        .loading {{ color: #25D366; font-size: 0.95rem; margin-bottom: 20px; }}
        .wa-btn {{ display: inline-flex; align-items: center; gap: 12px; background: {color}; color: white;
                  padding: 16px 36px; border-radius: 60px; font-size: 1.1rem; font-weight: 600;
                  text-decoration: none; transition: all 0.3s ease;
                  box-shadow: 0 8px 24px rgba(37,211,102,0.3); }}
        .wa-btn:hover {{ transform: translateY(-2px); box-shadow: 0 12px 32px rgba(37,211,102,0.4); }}
        .wa-btn svg {{ width: 24px; height: 24px; fill: white; }}
        .trust {{ margin-top: 28px; color: #475569; font-size: 0.85rem; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="wa-icon">
            <svg viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.625.846 5.059 2.284 7.034L.789 23.492a.75.75 0 00.917.918l4.458-1.495A11.945 11.945 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 22c-2.34 0-4.507-.794-6.23-2.13l-.353-.29-3.66 1.228 1.228-3.66-.29-.353A9.96 9.96 0 012 12C2 6.477 6.477 2 12 2s10 4.477 10 10-4.477 10-10 10z"/></svg>
        </div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
        <p class="loading" id="msg">Conectando con WhatsApp...</p>
        <a href="{wa_url}" class="wa-btn" id="waBtn">
            <svg viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.625.846 5.059 2.284 7.034L.789 23.492a.75.75 0 00.917.918l4.458-1.495A11.945 11.945 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 22c-2.34 0-4.507-.794-6.23-2.13l-.353-.29-3.66 1.228 1.228-3.66-.29-.353A9.96 9.96 0 012 12C2 6.477 6.477 2 12 2s10 4.477 10 10-4.477 10-10 10z"/></svg>
            {button_text}
        </a>
        <p class="trust">Respuesta inmediata garantizada</p>
    </div>
    <script>
        // Auto-redirect to WhatsApp (bots don't execute JS, only real users)
        setTimeout(function() {{ window.location.href = "{wa_url}"; }}, 1500);
    </script>
</body>
</html>"""

@api_router.post("/campaigns/generate-wa-landing")
async def generate_wa_landing(data: WALandingRequest, current_user=Depends(get_current_user)):
    html = generate_wa_landing_html(
        wa_number=data.whatsapp_number,
        wa_message=data.whatsapp_message,
        title=data.title,
        subtitle=data.subtitle,
        button_text=data.button_text,
        color=data.color
    )
    return {"html": html}

@api_router.get("/campaigns/{campaign_id}/preview-landing")
async def preview_landing(campaign_id: str):
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    html = campaign.get("landing_html", "")
    if not html:
        raise HTTPException(status_code=404, detail="Sin landing page configurada")
    return HTMLResponse(content=html)

# ─── Tracking Route ────────────────────────────────────────────────

@api_router.get("/track/{campaign_id}")
async def track_click(campaign_id: str, request: Request):
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not campaign or not campaign.get("is_active"):
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=404)
    if campaign.get("clicks_today", 0) >= campaign.get("daily_click_limit", 10000):
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=429)

    ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    referrer = request.headers.get("referer", "")
    headers_dict = dict(request.headers)

    device, os_name, browser = parse_device_info(user_agent)
    country = "XX"  # Simplified - would use GeoIP in production

    bot = is_bot(user_agent)
    meta = is_meta_crawler(user_agent)
    vpn = detect_vpn(headers_dict)
    is_dc = False
    fingerprint = generate_fingerprint(ip, user_agent, headers_dict)
    score = calculate_behavioral_score(bot, vpn, is_dc, bool(referrer), user_agent)

    config = {
        'allowed_countries': campaign.get('allowed_countries', []),
        'allowed_devices': campaign.get('allowed_devices', []),
        'allowed_os': campaign.get('allowed_os', []),
        'block_empty_referrer': campaign.get('block_empty_referrer', False),
        'blacklist_ips': campaign.get('blacklist_ips', []),
        'whitelist_ips': campaign.get('whitelist_ips', []),
    }
    blocked, block_reason = should_block(config, ip, country, device, os_name, referrer, bot, vpn)

    # Check AI-generated rules (skip for Meta IPs - they're always allowed)
    is_real_device = device in ('Mobile', 'Tablet', 'Desktop')
    if not blocked and not is_meta_ip(ip):
        ai_rules = await db.ai_rules.find({"is_active": True}, {"_id": 0}).to_list(100)
        for rule in ai_rules:
            field_val = {"country": country, "device": device, "os": os_name, "browser": browser,
                         "ip": ip, "referrer": referrer, "bot": str(bot).lower(), "vpn": str(vpn).lower(),
                         "score": str(score)}.get(rule.get("field", ""), "")
            op = rule.get("operator", "equals")
            rule_val = str(rule.get("value", ""))
            match = False
            if op == "equals":
                match = field_val.lower() == rule_val.lower()
            elif op == "not_equals":
                match = field_val.lower() != rule_val.lower()
            elif op == "contains":
                match = rule_val.lower() in field_val.lower()
            elif op == "in_list":
                vals = [v.strip().lower() for v in rule_val.split(",")]
                match = field_val.lower() in vals
            elif op == "greater_than":
                try: match = float(field_val) > float(rule_val)
                except: pass
            elif op == "less_than":
                try: match = float(field_val) < float(rule_val)
                except: pass

            if match:
                if rule.get("type") == "block":
                    # Never let AI rules block real devices (Mobile/Tablet/Desktop)
                    if not is_real_device:
                        blocked = True
                        block_reason = f"IA: {rule.get('reason', 'Regla automática')}"
                        break
                elif rule.get("type") == "allow":
                    blocked = False
                    block_reason = ""
                    break

    click = {
        "id": str(uuid.uuid4()),
        "campaign_id": campaign_id,
        "ip": ip,
        "country": country,
        "user_agent": user_agent,
        "device": device,
        "os": os_name,
        "browser": browser,
        "referrer": referrer,
        "is_bot": bot,
        "is_vpn": vpn,
        "is_datacenter": is_dc,
        "is_blocked": blocked,
        "block_reason": block_reason if blocked else None,
        "fingerprint_hash": fingerprint,
        "behavioral_score": score,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.clicks.insert_one(click)
    await db.campaigns.update_one({"id": campaign_id}, {"$inc": {"clicks_today": 1, "total_clicks": 1}})

    safe_url = campaign.get("safe_page_url")
    if meta:
        return RedirectResponse(url=safe_url, status_code=302) if safe_url else HTMLResponse(content=SAFE_PAGE_HTML)
    if blocked:
        return RedirectResponse(url=safe_url, status_code=302) if safe_url else HTMLResponse(content=SAFE_PAGE_HTML)
    return RedirectResponse(url=campaign["target_url"], status_code=302)

# ─── Dashboard Routes ──────────────────────────────────────────────

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(current_user=Depends(get_current_user)):
    total_clicks = await db.clicks.count_documents({})
    blocked_clicks = await db.clicks.count_documents({"is_blocked": True})

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    clicks_today = await db.clicks.count_documents({"created_at": {"$regex": f"^{today_str}"}})

    # Aggregation by country
    country_pipeline = [
        {"$group": {"_id": "$country", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    by_country = [{"country": r["_id"] or "Unknown", "count": r["count"]} async for r in db.clicks.aggregate(country_pipeline)]

    # Aggregation by device
    device_pipeline = [
        {"$group": {"_id": "$device", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    by_device = [{"device": r["_id"] or "Unknown", "count": r["count"]} async for r in db.clicks.aggregate(device_pipeline)]

    # Aggregation by OS
    os_pipeline = [
        {"$group": {"_id": "$os", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    by_os = [{"os": r["_id"] or "Unknown", "count": r["count"]} async for r in db.clicks.aggregate(os_pipeline)]

    return {
        "total_clicks": total_clicks,
        "blocked_clicks": blocked_clicks,
        "clicks_today": clicks_today,
        "by_country": by_country,
        "by_device": by_device,
        "by_os": by_os,
    }

@api_router.get("/dashboard/recent-clicks")
async def get_recent_clicks(limit: int = 50, current_user=Depends(get_current_user)):
    clicks = await db.clicks.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return clicks

@api_router.get("/dashboard/export-csv")
async def export_csv(current_user=Depends(get_current_user)):
    clicks = await db.clicks.find({}, {"_id": 0}).sort("created_at", -1).limit(10000).to_list(10000)
    import io, csv
    output = io.StringIO()
    if clicks:
        writer = csv.DictWriter(output, fieldnames=clicks[0].keys())
        writer.writeheader()
        writer.writerows(clicks)
    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=clicks_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"}
    )

# ─── Custom Filters Routes ────────────────────────────────────────

@api_router.get("/filters")
async def get_filters(current_user=Depends(get_current_user)):
    filters = await db.custom_filters.find({}, {"_id": 0}).sort("priority", -1).to_list(1000)
    return filters

@api_router.get("/filters/{filter_id}")
async def get_filter(filter_id: str, current_user=Depends(get_current_user)):
    f = await db.custom_filters.find_one({"id": filter_id}, {"_id": 0})
    if not f:
        raise HTTPException(status_code=404, detail="Filtro no encontrado")
    return f

@api_router.post("/filters")
async def create_filter(data: FilterCreate, current_user=Depends(get_current_user)):
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "name": data.name,
        "description": data.description or "",
        "action": data.action,
        "priority": data.priority,
        "is_active": data.is_active,
        "conditions": data.conditions,
        "times_triggered": 0,
        "created_at": now,
        "updated_at": now,
    }
    await db.custom_filters.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.put("/filters/{filter_id}")
async def update_filter(filter_id: str, data: FilterUpdate, current_user=Depends(get_current_user)):
    existing = await db.custom_filters.find_one({"id": filter_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Filtro no encontrado")
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.custom_filters.update_one({"id": filter_id}, {"$set": update_data})
    updated = await db.custom_filters.find_one({"id": filter_id}, {"_id": 0})
    return updated

@api_router.delete("/filters/{filter_id}")
async def delete_filter(filter_id: str, current_user=Depends(get_current_user)):
    result = await db.custom_filters.delete_one({"id": filter_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Filtro no encontrado")
    return {"message": "Filtro eliminado"}

# ─── Reports Routes ───────────────────────────────────────────────

@api_router.get("/reports/performance")
async def performance_report(
    campaign_id: Optional[str] = None,
    days: int = Query(7, ge=1, le=90),
    current_user=Depends(get_current_user)
):
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    match = {"created_at": {"$gte": date_from}}
    if campaign_id:
        match["campaign_id"] = campaign_id

    pipeline = [
        {"$match": match},
        {"$addFields": {"date_str": {"$substr": ["$created_at", 0, 10]}}},
        {"$group": {
            "_id": "$date_str",
            "total_clicks": {"$sum": 1},
            "blocked_clicks": {"$sum": {"$cond": [{"$eq": ["$is_blocked", True]}, 1, 0]}},
            "allowed_clicks": {"$sum": {"$cond": [{"$eq": ["$is_blocked", False]}, 1, 0]}},
        }},
        {"$sort": {"_id": 1}},
    ]
    results = []
    async for r in db.clicks.aggregate(pipeline):
        total = r["total_clicks"]
        results.append({
            "date": r["_id"],
            "total_clicks": total,
            "blocked_clicks": r["blocked_clicks"],
            "allowed_clicks": r["allowed_clicks"],
            "block_rate": round((r["blocked_clicks"] / total * 100), 2) if total > 0 else 0,
        })
    return {"period": f"Últimos {days} días", "data": results}

@api_router.get("/reports/fraud-detection")
async def fraud_detection_report(
    days: int = Query(7, ge=1, le=30),
    current_user=Depends(get_current_user)
):
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    # Suspicious IPs
    ip_pipeline = [
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$group": {
            "_id": "$ip",
            "click_count": {"$sum": 1},
            "blocked_count": {"$sum": {"$cond": [{"$eq": ["$is_blocked", True]}, 1, 0]}},
            "avg_score": {"$avg": "$behavioral_score"},
        }},
        {"$match": {"click_count": {"$gt": 5}}},
        {"$sort": {"click_count": -1}},
        {"$limit": 20},
    ]
    suspicious_ips = []
    async for r in db.clicks.aggregate(ip_pipeline):
        suspicious_ips.append({
            "ip": r["_id"],
            "click_count": r["click_count"],
            "blocked_count": r["blocked_count"],
            "avg_score": round(r["avg_score"], 2) if r["avg_score"] else 0,
            "fraud_probability": "HIGH" if r["click_count"] > 20 else "MEDIUM",
        })

    # Duplicate fingerprints
    fp_pipeline = [
        {"$match": {"created_at": {"$gte": date_from}, "fingerprint_hash": {"$ne": None}}},
        {"$group": {"_id": "$fingerprint_hash", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 10}}},
        {"$sort": {"count": -1}},
        {"$limit": 20},
    ]
    dup_fps = []
    async for r in db.clicks.aggregate(fp_pipeline):
        dup_fps.append({"fingerprint": r["_id"][:16] + "...", "count": r["count"]})

    return {"suspicious_ips": suspicious_ips, "duplicate_fingerprints": dup_fps}

@api_router.get("/reports/geo-analysis")
async def geo_analysis_report(
    campaign_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=90),
    current_user=Depends(get_current_user)
):
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    match = {"created_at": {"$gte": date_from}}
    if campaign_id:
        match["campaign_id"] = campaign_id

    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": "$country",
            "total_clicks": {"$sum": 1},
            "blocked": {"$sum": {"$cond": [{"$eq": ["$is_blocked", True]}, 1, 0]}},
            "bots": {"$sum": {"$cond": [{"$eq": ["$is_bot", True]}, 1, 0]}},
            "vpn": {"$sum": {"$cond": [{"$eq": ["$is_vpn", True]}, 1, 0]}},
            "avg_score": {"$avg": "$behavioral_score"},
        }},
        {"$sort": {"total_clicks": -1}},
        {"$limit": 30},
    ]
    countries = []
    async for r in db.clicks.aggregate(pipeline):
        avg = r["avg_score"] or 0
        countries.append({
            "country": r["_id"] or "Unknown",
            "total_clicks": r["total_clicks"],
            "blocked": r["blocked"],
            "bots": r["bots"],
            "vpn": r["vpn"],
            "avg_score": round(avg, 2),
            "quality": "HIGH" if avg > 70 else "MEDIUM" if avg > 50 else "LOW",
        })
    return {"countries": countries}

@api_router.get("/reports/hourly-patterns")
async def hourly_patterns_report(
    campaign_id: Optional[str] = None,
    days: int = Query(7, ge=1, le=30),
    current_user=Depends(get_current_user)
):
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    match = {"created_at": {"$gte": date_from}}
    if campaign_id:
        match["campaign_id"] = campaign_id

    pipeline = [
        {"$match": match},
        {"$addFields": {"hour": {"$substr": ["$created_at", 11, 2]}}},
        {"$group": {
            "_id": "$hour",
            "clicks": {"$sum": 1},
            "allowed": {"$sum": {"$cond": [{"$eq": ["$is_blocked", False]}, 1, 0]}},
        }},
        {"$sort": {"_id": 1}},
    ]
    hourly = []
    async for r in db.clicks.aggregate(pipeline):
        total = r["clicks"]
        hourly.append({
            "hour": int(r["_id"]) if r["_id"].isdigit() else 0,
            "total_clicks": total,
            "allowed_clicks": r["allowed"],
            "conversion_rate": round((r["allowed"] / total * 100), 2) if total > 0 else 0,
        })
    return {"hourly_data": hourly}

# ─── Analytics Routes ──────────────────────────────────────────────

@api_router.get("/analytics/overview")
async def analytics_overview(
    days: int = Query(30, ge=1, le=90),
    current_user=Depends(get_current_user)
):
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    total = await db.clicks.count_documents({"created_at": {"$gte": date_from}})
    blocked = await db.clicks.count_documents({"created_at": {"$gte": date_from}, "is_blocked": True})
    bots = await db.clicks.count_documents({"created_at": {"$gte": date_from}, "is_bot": True})
    vpns = await db.clicks.count_documents({"created_at": {"$gte": date_from}, "is_vpn": True})
    campaigns = await db.campaigns.count_documents({})
    active_campaigns = await db.campaigns.count_documents({"is_active": True})

    # Average behavioral score
    score_pipeline = [
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$group": {"_id": None, "avg_score": {"$avg": "$behavioral_score"}}},
    ]
    avg_score = 0
    async for r in db.clicks.aggregate(score_pipeline):
        avg_score = round(r["avg_score"], 1) if r["avg_score"] else 0

    return {
        "total_clicks": total,
        "blocked_clicks": blocked,
        "allowed_clicks": total - blocked,
        "bot_clicks": bots,
        "vpn_clicks": vpns,
        "total_campaigns": campaigns,
        "active_campaigns": active_campaigns,
        "avg_behavioral_score": avg_score,
        "block_rate": round((blocked / total * 100), 1) if total > 0 else 0,
    }

@api_router.get("/analytics/trends")
async def analytics_trends(
    days: int = Query(14, ge=1, le=90),
    current_user=Depends(get_current_user)
):
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    pipeline = [
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$addFields": {"date_str": {"$substr": ["$created_at", 0, 10]}}},
        {"$group": {
            "_id": "$date_str",
            "total": {"$sum": 1},
            "blocked": {"$sum": {"$cond": [{"$eq": ["$is_blocked", True]}, 1, 0]}},
            "allowed": {"$sum": {"$cond": [{"$eq": ["$is_blocked", False]}, 1, 0]}},
            "bots": {"$sum": {"$cond": [{"$eq": ["$is_bot", True]}, 1, 0]}},
            "avg_score": {"$avg": "$behavioral_score"},
        }},
        {"$sort": {"_id": 1}},
    ]
    trends = []
    async for r in db.clicks.aggregate(pipeline):
        trends.append({
            "date": r["_id"],
            "total": r["total"],
            "blocked": r["blocked"],
            "allowed": r["allowed"],
            "bots": r["bots"],
            "avg_score": round(r["avg_score"], 1) if r["avg_score"] else 0,
        })
    return {"trends": trends}

@api_router.get("/analytics/top-campaigns")
async def analytics_top_campaigns(current_user=Depends(get_current_user)):
    pipeline = [
        {"$group": {
            "_id": "$campaign_id",
            "total_clicks": {"$sum": 1},
            "blocked": {"$sum": {"$cond": [{"$eq": ["$is_blocked", True]}, 1, 0]}},
        }},
        {"$sort": {"total_clicks": -1}},
        {"$limit": 10},
    ]
    top = []
    async for r in db.clicks.aggregate(pipeline):
        campaign = await db.campaigns.find_one({"id": r["_id"]}, {"_id": 0, "name": 1})
        top.append({
            "campaign_id": r["_id"],
            "campaign_name": campaign["name"] if campaign else "Desconocida",
            "total_clicks": r["total_clicks"],
            "blocked": r["blocked"],
        })
    return {"top_campaigns": top}

# ─── Advanced Analytics ────────────────────────────────────────────

@api_router.get("/analytics/devices")
async def analytics_devices(days: int = Query(30, ge=1, le=90), current_user=Depends(get_current_user)):
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    pipeline = [
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$group": {"_id": "$device", "count": {"$sum": 1}, "blocked": {"$sum": {"$cond": [{"$eq": ["$is_blocked", True]}, 1, 0]}}}},
        {"$sort": {"count": -1}},
    ]
    result = []
    async for r in db.clicks.aggregate(pipeline):
        result.append({"name": r["_id"] or "Unknown", "total": r["count"], "blocked": r["blocked"]})
    return result

@api_router.get("/analytics/os")
async def analytics_os(days: int = Query(30, ge=1, le=90), current_user=Depends(get_current_user)):
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    pipeline = [
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$group": {"_id": "$os", "count": {"$sum": 1}, "blocked": {"$sum": {"$cond": [{"$eq": ["$is_blocked", True]}, 1, 0]}}}},
        {"$sort": {"count": -1}},
    ]
    result = []
    async for r in db.clicks.aggregate(pipeline):
        result.append({"name": r["_id"] or "Unknown", "total": r["count"], "blocked": r["blocked"]})
    return result

@api_router.get("/analytics/browsers")
async def analytics_browsers(days: int = Query(30, ge=1, le=90), current_user=Depends(get_current_user)):
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    pipeline = [
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$group": {"_id": "$browser", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}, {"$limit": 10},
    ]
    result = []
    async for r in db.clicks.aggregate(pipeline):
        result.append({"name": r["_id"] or "Unknown", "total": r["count"]})
    return result

@api_router.get("/analytics/hourly")
async def analytics_hourly(days: int = Query(7, ge=1, le=30), current_user=Depends(get_current_user)):
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    pipeline = [
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$addFields": {"hour": {"$substr": ["$created_at", 11, 2]}}},
        {"$group": {"_id": "$hour", "total": {"$sum": 1},
                    "allowed": {"$sum": {"$cond": [{"$eq": ["$is_blocked", False]}, 1, 0]}},
                    "blocked": {"$sum": {"$cond": [{"$eq": ["$is_blocked", True]}, 1, 0]}}}},
        {"$sort": {"_id": 1}},
    ]
    result = []
    async for r in db.clicks.aggregate(pipeline):
        result.append({"hour": f"{r['_id']}:00", "total": r["total"], "allowed": r["allowed"], "blocked": r["blocked"]})
    return result

@api_router.get("/analytics/top-ips")
async def analytics_top_ips(days: int = Query(7, ge=1, le=30), current_user=Depends(get_current_user)):
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    pipeline = [
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$group": {"_id": "$ip", "count": {"$sum": 1},
                    "blocked": {"$sum": {"$cond": [{"$eq": ["$is_blocked", True]}, 1, 0]}},
                    "devices": {"$addToSet": "$device"}, "countries": {"$addToSet": "$country"}}},
        {"$sort": {"count": -1}}, {"$limit": 20},
    ]
    result = []
    async for r in db.clicks.aggregate(pipeline):
        result.append({
            "ip": r["_id"], "count": r["count"], "blocked": r["blocked"],
            "devices": r["devices"], "countries": r["countries"],
            "is_meta": any(r["_id"].startswith(p) for p in META_IP_PREFIXES),
        })
    return result

@api_router.get("/analytics/referrers")
async def analytics_referrers(days: int = Query(30, ge=1, le=90), current_user=Depends(get_current_user)):
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    pipeline = [
        {"$match": {"created_at": {"$gte": date_from}, "referrer": {"$ne": ""}}},
        {"$group": {"_id": "$referrer", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}, {"$limit": 15},
    ]
    result = []
    async for r in db.clicks.aggregate(pipeline):
        result.append({"referrer": r["_id"], "count": r["count"]})
    return result

# ─── Click Forensics ──────────────────────────────────────────────

@api_router.get("/clicks/search")
async def search_clicks(
    ip: str = Query(None), campaign_id: str = Query(None),
    is_blocked: bool = Query(None), device: str = Query(None),
    days: int = Query(7, ge=1, le=90), page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user)
):
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    query = {"created_at": {"$gte": date_from}}
    if ip: query["ip"] = {"$regex": ip}
    if campaign_id: query["campaign_id"] = campaign_id
    if is_blocked is not None: query["is_blocked"] = is_blocked
    if device: query["device"] = device

    total = await db.clicks.count_documents(query)
    skip = (page - 1) * limit
    clicks = await db.clicks.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    for click in clicks:
        campaign = await db.campaigns.find_one({"id": click.get("campaign_id")}, {"_id": 0, "name": 1})
        click["campaign_name"] = campaign["name"] if campaign else "Desconocida"

    return {"clicks": clicks, "total": total, "page": page, "pages": (total + limit - 1) // limit}

@api_router.get("/clicks/{click_id}")
async def get_click_detail(click_id: str, current_user=Depends(get_current_user)):
    click = await db.clicks.find_one({"id": click_id}, {"_id": 0})
    if not click:
        raise HTTPException(status_code=404, detail="Click no encontrado")
    campaign = await db.campaigns.find_one({"id": click.get("campaign_id")}, {"_id": 0, "name": 1})
    click["campaign_name"] = campaign["name"] if campaign else "Desconocida"
    click["is_meta_ip"] = any(click.get("ip", "").startswith(p) for p in META_IP_PREFIXES)
    return click

# ─── AI Generator Routes ──────────────────────────────────────────

@api_router.post("/ai/generate")
async def generate_ai_page(data: AIPageCreate, current_user=Depends(get_current_user)):
    if not CLAUDE_API_KEY:
        raise HTTPException(status_code=500, detail="Claude API key no configurada")
    try:
        import anthropic
        client_ai = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        message = client_ai.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": f"""Genera una página HTML completa y profesional basada en esta descripción:

{data.prompt}

Requisitos:
- HTML completo con DOCTYPE, head y body
- CSS inline moderno y responsive
- Diseño profesional y atractivo
- Colores y tipografía coherentes
- Responsive design
- Solo devuelve el código HTML, sin explicaciones ni markdown"""
            }]
        )
        html_content = message.content[0].text
        # Clean markdown wrappers if present
        if html_content.startswith("```"):
            lines = html_content.split("\n")
            html_content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    except Exception as e:
        logger.error(f"AI generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Error generando página: {str(e)}")

    now = datetime.now(timezone.utc).isoformat()
    page = {
        "id": str(uuid.uuid4()),
        "prompt": data.prompt,
        "generated_html": html_content,
        "title": data.prompt[:100],
        "campaign_id": data.campaign_id,
        "created_at": now,
    }
    await db.ai_pages.insert_one(page)
    page.pop("_id", None)
    return page

@api_router.get("/ai/pages")
async def get_ai_pages(current_user=Depends(get_current_user)):
    pages = await db.ai_pages.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return pages

@api_router.get("/ai/pages/{page_id}")
async def get_ai_page(page_id: str, current_user=Depends(get_current_user)):
    page = await db.ai_pages.find_one({"id": page_id}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Página no encontrada")
    return page

@api_router.delete("/ai/pages/{page_id}")
async def delete_ai_page(page_id: str, current_user=Depends(get_current_user)):
    result = await db.ai_pages.delete_one({"id": page_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Página no encontrada")
    return {"message": "Página eliminada"}

# ─── Public AI Pages Routes ───────────────────────────────────────

@api_router.get("/p/{page_id}")
async def serve_public_ai_page(page_id: str, request: Request):
    """
    Serve AI-generated landing page with full antibot tracking.
    
    - If bot/Meta crawler detected → Shows safe page (404)
    - If blocked by campaign rules → Shows safe page  
    - If legitimate user → Shows the AI-generated landing
    
    All visits are logged with full tracking data.
    """
    
    # Get the AI page
    ai_page = await db.ai_pages.find_one({"id": page_id}, {"_id": 0})
    
    if not ai_page:
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=404)
    
    # Get associated campaign (if any) for tracking rules
    campaign = None
    if ai_page.get("campaign_id"):
        campaign = await db.campaigns.find_one({"id": ai_page["campaign_id"]}, {"_id": 0})
    
    # If campaign exists and is inactive, show safe page
    if campaign and not campaign.get("is_active", True):
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=404)
    
    # Check daily limit if campaign exists
    if campaign and campaign.get("clicks_today", 0) >= campaign.get("daily_click_limit", 10000):
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=429)
    
    # Extract request info
    ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    referrer = request.headers.get("referer", "")
    headers_dict = dict(request.headers)
    
    # Parse device info
    device, os_name, browser = parse_device_info(user_agent)
    country = "XX"  # Simplified - would use GeoIP in production
    
    # Run all detection checks
    bot = is_bot(user_agent)
    meta = is_meta_crawler(user_agent)
    vpn = detect_vpn(headers_dict)
    is_dc = False
    
    # Generate fingerprint
    fingerprint = generate_fingerprint(ip, user_agent, headers_dict)
    
    # Calculate behavioral score
    score = calculate_behavioral_score(bot, vpn, is_dc, bool(referrer), user_agent)
    
    # Determine if should block based on campaign rules
    blocked = False
    block_reason = None
    
    if campaign:
        config = {
            'allowed_countries': campaign.get('allowed_countries', []),
            'allowed_devices': campaign.get('allowed_devices', []),
            'allowed_os': campaign.get('allowed_os', []),
            'block_empty_referrer': campaign.get('block_empty_referrer', False),
            'blacklist_ips': campaign.get('blacklist_ips', []),
            'whitelist_ips': campaign.get('whitelist_ips', [])
        }
        
        blocked, block_reason = should_block(
            config, ip, country, device, os_name, referrer, bot, vpn
        )
        
        # Check AI-generated rules if not meta IP
        is_real_device = device in ('Mobile', 'Tablet', 'Desktop')
        if not blocked and not is_meta_ip(ip):
            ai_rules = await db.ai_rules.find({"is_active": True}, {"_id": 0}).to_list(100)
            for rule in ai_rules:
                field_val = {"country": country, "device": device, "os": os_name, "browser": browser,
                           "ip": ip, "referrer": referrer, "bot": str(bot).lower(), "vpn": str(vpn).lower(),
                           "score": str(score)}.get(rule.get("field", ""), "")
                op = rule.get("operator", "equals")
                rule_val = str(rule.get("value", ""))
                match = False
                if op == "equals":
                    match = field_val.lower() == rule_val.lower()
                elif op == "not_equals":
                    match = field_val.lower() != rule_val.lower()
                elif op == "contains":
                    match = rule_val.lower() in field_val.lower()
                elif op == "in_list":
                    vals = [v.strip().lower() for v in rule_val.split(",")]
                    match = field_val.lower() in vals
                elif op == "greater_than":
                    try: match = float(field_val) > float(rule_val)
                    except: pass
                elif op == "less_than":
                    try: match = float(field_val) < float(rule_val)
                    except: pass

                if match:
                    if rule.get("type") == "block":
                        # Never let AI rules block real devices (Mobile/Tablet/Desktop)
                        if not is_real_device:
                            blocked = True
                            block_reason = f"IA: {rule.get('reason', 'Regla automática')}"
                            break
                    elif rule.get("type") == "allow":
                        blocked = False
                        block_reason = ""
                        break
    else:
        # No campaign - just check for bots
        if bot:
            blocked = True
            block_reason = "Bot detected"
    
    # Log the click/visit
    click = {
        "id": str(uuid.uuid4()),
        "campaign_id": ai_page.get("campaign_id"),
        "ip": ip,
        "country": country,
        "user_agent": user_agent,
        "device": device,
        "os": os_name,
        "browser": browser,
        "referrer": referrer,
        "is_bot": bot,
        "is_vpn": vpn,
        "is_datacenter": is_dc,
        "is_blocked": blocked or meta,
        "block_reason": block_reason if blocked else ("Meta crawler" if meta else None),
        "fingerprint_hash": fingerprint,
        "behavioral_score": score,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.clicks.insert_one(click)
    
    # Update campaign counters if exists
    if campaign:
        await db.campaigns.update_one(
            {"id": campaign["id"]}, 
            {"$inc": {"clicks_today": 1, "total_clicks": 1}}
        )
    
    # Decision: Show safe page or real landing
    if meta:
        # Meta/Facebook crawler - show safe page
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=200)
    
    if blocked:
        # Blocked traffic - show safe page
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=200)
    
    # Legitimate user - show the AI-generated landing page
    return HTMLResponse(content=ai_page["generated_html"], status_code=200)

# ─── AI Intelligence Routes ────────────────────────────────────────

@api_router.get("/intelligence/status")
async def intelligence_status(current_user=Depends(get_current_user)):
    total_clicks = await db.clicks.count_documents({})
    total_rules = await db.ai_rules.count_documents({})
    active_rules = await db.ai_rules.count_documents({"is_active": True})
    last_insight = await db.ai_insights.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
    return {
        "total_clicks_analyzed": total_clicks,
        "total_rules": total_rules,
        "active_rules": active_rules,
        "last_analysis": last_insight["created_at"] if last_insight else None,
        "has_enough_data": total_clicks >= 5,
    }

@api_router.post("/intelligence/analyze")
async def run_ai_analysis(current_user=Depends(get_current_user)):
    if not CLAUDE_API_KEY:
        raise HTTPException(status_code=500, detail="Claude API key no configurada")

    total_clicks = await db.clicks.count_documents({})
    if total_clicks < 5:
        raise HTTPException(status_code=400, detail="Se necesitan al menos 5 clicks para analizar. Genera más tráfico primero.")

    # Gather aggregated data
    date_from = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    # By country
    country_agg = await db.clicks.aggregate([
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$group": {"_id": "$country", "count": {"$sum": 1},
                    "blocked": {"$sum": {"$cond": [{"$eq": ["$is_blocked", True]}, 1, 0]}},
                    "avg_score": {"$avg": "$behavioral_score"}}},
        {"$sort": {"count": -1}}, {"$limit": 20}
    ]).to_list(20)

    # By device
    device_agg = await db.clicks.aggregate([
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$group": {"_id": "$device", "count": {"$sum": 1},
                    "blocked": {"$sum": {"$cond": [{"$eq": ["$is_blocked", True]}, 1, 0]}},
                    "avg_score": {"$avg": "$behavioral_score"}}},
        {"$sort": {"count": -1}}
    ]).to_list(10)

    # By OS
    os_agg = await db.clicks.aggregate([
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$group": {"_id": "$os", "count": {"$sum": 1},
                    "blocked": {"$sum": {"$cond": [{"$eq": ["$is_blocked", True]}, 1, 0]}},
                    "avg_score": {"$avg": "$behavioral_score"}}},
        {"$sort": {"count": -1}}, {"$limit": 15}
    ]).to_list(15)

    # By browser
    browser_agg = await db.clicks.aggregate([
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$group": {"_id": "$browser", "count": {"$sum": 1},
                    "avg_score": {"$avg": "$behavioral_score"}}},
        {"$sort": {"count": -1}}, {"$limit": 10}
    ]).to_list(10)

    # By hour
    hour_agg = await db.clicks.aggregate([
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$addFields": {"hour": {"$substr": ["$created_at", 11, 2]}}},
        {"$group": {"_id": "$hour", "count": {"$sum": 1},
                    "allowed": {"$sum": {"$cond": [{"$eq": ["$is_blocked", False]}, 1, 0]}},
                    "avg_score": {"$avg": "$behavioral_score"}}},
        {"$sort": {"_id": 1}}
    ]).to_list(24)

    # Top IPs
    ip_agg = await db.clicks.aggregate([
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$group": {"_id": "$ip", "count": {"$sum": 1},
                    "blocked": {"$sum": {"$cond": [{"$eq": ["$is_blocked", True]}, 1, 0]}},
                    "avg_score": {"$avg": "$behavioral_score"}}},
        {"$sort": {"count": -1}}, {"$limit": 30}
    ]).to_list(30)

    # Referrer patterns
    ref_agg = await db.clicks.aggregate([
        {"$match": {"created_at": {"$gte": date_from}, "referrer": {"$ne": ""}}},
        {"$group": {"_id": "$referrer", "count": {"$sum": 1},
                    "avg_score": {"$avg": "$behavioral_score"}}},
        {"$sort": {"count": -1}}, {"$limit": 15}
    ]).to_list(15)

    # Bot vs non-bot
    bot_stats = await db.clicks.aggregate([
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$group": {"_id": "$is_bot", "count": {"$sum": 1}, "avg_score": {"$avg": "$behavioral_score"}}}
    ]).to_list(5)

    data_summary = {
        "total_clicks": total_clicks,
        "period": "últimos 30 días",
        "by_country": [{"country": r["_id"], "clicks": r["count"], "blocked": r["blocked"], "avg_score": round(r["avg_score"] or 0, 1)} for r in country_agg],
        "by_device": [{"device": r["_id"], "clicks": r["count"], "blocked": r["blocked"], "avg_score": round(r["avg_score"] or 0, 1)} for r in device_agg],
        "by_os": [{"os": r["_id"], "clicks": r["count"], "blocked": r["blocked"], "avg_score": round(r["avg_score"] or 0, 1)} for r in os_agg],
        "by_browser": [{"browser": r["_id"], "clicks": r["count"], "avg_score": round(r["avg_score"] or 0, 1)} for r in browser_agg],
        "by_hour": [{"hour": r["_id"], "clicks": r["count"], "allowed": r["allowed"], "avg_score": round(r["avg_score"] or 0, 1)} for r in hour_agg],
        "top_ips": [{"ip": r["_id"], "clicks": r["count"], "blocked": r["blocked"], "avg_score": round(r["avg_score"] or 0, 1)} for r in ip_agg],
        "referrers": [{"referrer": r["_id"], "clicks": r["count"], "avg_score": round(r["avg_score"] or 0, 1)} for r in ref_agg],
        "bot_stats": [{"is_bot": r["_id"], "count": r["count"], "avg_score": round(r["avg_score"] or 0, 1)} for r in bot_stats],
    }

    import json as json_lib
    prompt = f"""Eres un analista experto en tráfico digital y detección de fraude publicitario. 
Analiza estos datos de tráfico y genera insights accionables y reglas automáticas para optimizar la calidad del público.

DATOS DE TRÁFICO:
{json_lib.dumps(data_summary, indent=2, ensure_ascii=False)}

Tu tarea:
1. Identifica PATRONES de tráfico de alta calidad (usuarios que "juegan más fuerte" - mayor score conductual, menor tasa de bloqueo)
2. Identifica PATRONES de tráfico de baja calidad o fraudulento  
3. Genera REGLAS AUTOMÁTICAS específicas para mejorar la calidad del tráfico

RESPONDE EN JSON EXACTO con esta estructura (sin markdown, solo JSON puro):
{{
  "audience_profile": {{
    "high_value_summary": "Descripción del perfil de usuario de alta calidad",
    "risk_summary": "Descripción de las amenazas detectadas",
    "optimization_score": 0-100
  }},
  "insights": [
    {{
      "category": "country|device|timing|fraud|referrer|general",
      "title": "Título corto del insight",
      "description": "Descripción detallada",
      "impact": "high|medium|low",
      "recommendation": "Qué hacer"
    }}
  ],
  "rules": [
    {{
      "type": "block|allow",
      "field": "country|device|os|browser|hour_range|ip|referrer|bot|vpn|score",
      "operator": "equals|not_equals|contains|greater_than|less_than|in_list",
      "value": "valor o lista",
      "confidence": 0.0-1.0,
      "reason": "Por qué esta regla"
    }}
  ]
}}"""

    try:
        import anthropic
        client_ai = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        message = client_ai.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = message.content[0].text

        # Parse JSON from response
        import json as json_mod
        # Try to extract JSON if wrapped in markdown
        if "```" in response_text:
            lines = response_text.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_json = not in_json
                    continue
                if in_json:
                    json_lines.append(line)
            response_text = "\n".join(json_lines)

        ai_result = json_mod.loads(response_text)

    except json_mod.JSONDecodeError:
        logger.error(f"Failed to parse AI response: {response_text[:500]}")
        raise HTTPException(status_code=500, detail="Error al parsear respuesta de IA")
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Error en análisis IA: {str(e)}")

    # Save insight
    now = datetime.now(timezone.utc).isoformat()
    analysis_id = str(uuid.uuid4())
    insight_doc = {
        "id": analysis_id,
        "audience_profile": ai_result.get("audience_profile", {}),
        "insights": ai_result.get("insights", []),
        "data_summary": {"total_clicks": total_clicks, "period": "30 días"},
        "created_at": now,
    }
    await db.ai_insights.insert_one(insight_doc)

    # Auto-create and apply rules
    new_rules = []
    for rule in ai_result.get("rules", []):
        rule_doc = {
            "id": str(uuid.uuid4()),
            "type": rule.get("type", "block"),
            "field": rule.get("field", ""),
            "operator": rule.get("operator", "equals"),
            "value": rule.get("value", ""),
            "confidence": rule.get("confidence", 0.5),
            "reason": rule.get("reason", ""),
            "is_active": True,
            "auto_applied": True,
            "source_analysis_id": analysis_id,
            "created_at": now,
        }
        await db.ai_rules.insert_one(rule_doc)
        rule_doc.pop("_id", None)
        new_rules.append(rule_doc)

    insight_doc.pop("_id", None)
    return {
        "analysis": insight_doc,
        "rules_created": len(new_rules),
        "rules": new_rules,
    }

@api_router.get("/intelligence/insights")
async def get_insights(current_user=Depends(get_current_user)):
    insights = await db.ai_insights.find({}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return insights

@api_router.get("/intelligence/rules")
async def get_ai_rules(current_user=Depends(get_current_user)):
    rules = await db.ai_rules.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return rules

@api_router.put("/intelligence/rules/{rule_id}/toggle")
async def toggle_ai_rule(rule_id: str, data: AIRuleToggle, current_user=Depends(get_current_user)):
    result = await db.ai_rules.update_one({"id": rule_id}, {"$set": {"is_active": data.is_active}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    updated = await db.ai_rules.find_one({"id": rule_id}, {"_id": 0})
    return updated

@api_router.delete("/intelligence/rules/{rule_id}")
async def delete_ai_rule(rule_id: str, current_user=Depends(get_current_user)):
    result = await db.ai_rules.delete_one({"id": rule_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return {"message": "Regla eliminada"}

@api_router.delete("/intelligence/rules-purge/all")
async def purge_all_ai_rules(current_user=Depends(get_current_user)):
    result = await db.ai_rules.delete_many({})
    return {"message": f"{result.deleted_count} reglas eliminadas"}

@api_router.delete("/intelligence/insights/{insight_id}")
async def delete_insight(insight_id: str, current_user=Depends(get_current_user)):
    await db.ai_insights.delete_one({"id": insight_id})
    return {"message": "Insight eliminado"}

# ─── Image Generation ──────────────────────────────────────────────

class ImageGenRequest(BaseModel):
    prompt: str
    style: Optional[str] = "vivid"
    size: Optional[str] = "1024x1024"

@api_router.post("/images/generate")
async def generate_image(data: ImageGenRequest, current_user=Depends(get_current_user)):
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY no configurada")
    try:
        from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration
        image_gen = OpenAIImageGeneration(api_key=EMERGENT_LLM_KEY)
        images = await image_gen.generate_images(
            prompt=data.prompt,
            model="gpt-image-1",
            number_of_images=1
        )
        if images and len(images) > 0:
            image_base64 = base64.b64encode(images[0]).decode('utf-8')
            return {"image_base64": image_base64, "format": "png"}
        raise HTTPException(status_code=500, detail="No se generó imagen")
    except ImportError:
        raise HTTPException(status_code=500, detail="emergentintegrations no instalado")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── Meta Ads Proxy ────────────────────────────────────────────────

META_API_BASE = "https://graph.facebook.com/v20.0"

class MetaCredentials(BaseModel):
    access_token: str
    account_id: str

class MetaAdRequest(BaseModel):
    access_token: str
    account_id: str
    endpoint: str
    payload: Dict

@api_router.post("/meta/connect")
async def meta_connect(data: MetaCredentials, current_user=Depends(get_current_user)):
    async with httpx.AsyncClient(timeout=30) as client_http:
        resp = await client_http.get(
            f"{META_API_BASE}/{data.account_id}",
            params={"fields": "name,currency,account_status", "access_token": data.access_token}
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.json().get("error", {}).get("message", "Error de Meta API"))
        return resp.json()

@api_router.post("/meta/publish")
async def meta_publish(data: MetaAdRequest, current_user=Depends(get_current_user)):
    url = f"{META_API_BASE}/{data.account_id}/{data.endpoint}"
    params = {**data.payload, "access_token": data.access_token}
    # Meta API expects JSON-encoded values for complex fields
    for key, val in params.items():
        if isinstance(val, (dict, list)):
            import json as json_lib
            params[key] = json_lib.dumps(val)
    async with httpx.AsyncClient(timeout=60) as client_http:
        resp = await client_http.post(url, data=params)
        result = resp.json()
        if resp.status_code != 200 and "error" in result:
            error = result["error"]
            blame = error.get("error_data", {}).get("blame_field_specs", [])
            msg = error.get("message", "Error")
            if blame:
                msg += f" (campo: {', '.join(str(b) for b in blame)})"
            raise HTTPException(
                status_code=resp.status_code,
                detail={"message": msg, "code": error.get("code"), "subcode": error.get("error_subcode")}
            )
        return result

@api_router.post("/meta/upload-image")
async def meta_upload_image(data: Dict, current_user=Depends(get_current_user)):
    access_token = data.get("access_token")
    account_id = data.get("account_id")
    image_base64 = data.get("image_base64")
    if not all([access_token, account_id, image_base64]):
        raise HTTPException(status_code=400, detail="Faltan campos requeridos")
    url = f"{META_API_BASE}/{account_id}/adimages"
    payload = {"bytes": image_base64, "access_token": access_token}
    async with httpx.AsyncClient(timeout=60) as client_http:
        resp = await client_http.post(url, data=payload)
        result = resp.json()
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"].get("message", "Error subiendo imagen"))
        return result

# ─── AI Page Generator (Claude) ───────────────────────────────────

class PageGenRequest(BaseModel):
    prompt: str
    page_type: Optional[str] = "landing"
    style: Optional[str] = "moderno"

# ─── WhatsApp CRM ──────────────────────────────────────────────────

WA_GRAPH_URL = "https://graph.facebook.com/v20.0"

# ─── Purchase Currency Override ────────────────────────────────────
# Single source of truth for the currency reported to Meta CAPI on
# Purchase events across this deployment. Set via env var PURCHASE_CURRENCY
# (e.g. "USD" for the USD client, "ARS" for the Argentina client).
# Defaults to "USD" for backwards compatibility.
PURCHASE_CURRENCY = (os.environ.get("PURCHASE_CURRENCY") or "USD").upper().strip()
logger.info(f"PURCHASE_CURRENCY configured as: {PURCHASE_CURRENCY}")

class WASettingsUpdate(BaseModel):
    whatsapp_token: Optional[str] = None
    phone_number_id: Optional[str] = None
    verify_token: Optional[str] = None
    auto_reply_enabled: Optional[bool] = None
    auto_reply_message: Optional[str] = None
    bot_auto_reply_enabled: Optional[bool] = None

class WASendMessage(BaseModel):
    phone: str
    message: str

class WAClassify(BaseModel):
    classification: str  # "human", "bot", "spam"

async def get_wa_settings():
    settings = await db.wa_settings.find_one({}, {"_id": 0})
    if not settings:
        settings = {
            "whatsapp_token": WHATSAPP_TOKEN,
            "phone_number_id": WHATSAPP_PHONE_NUMBER_ID,
            "verify_token": WHATSAPP_VERIFY_TOKEN,
            "auto_reply_enabled": True,
            "auto_reply_message": "Hola! Gracias por contactarnos. Un agente te atendera pronto.",
            "bot_auto_reply_enabled": False,
        }
        await db.wa_settings.insert_one(settings)
        settings.pop("_id", None)
    return settings

async def wa_send_text(phone: str, message: str, token: str = None, phone_id: str = None):
    """Send a WhatsApp text message via Cloud API"""
    settings = await get_wa_settings()
    tk = token or settings.get("whatsapp_token") or WHATSAPP_TOKEN
    pid = phone_id or settings.get("phone_number_id") or WHATSAPP_PHONE_NUMBER_ID
    if not tk or not pid:
        return {"error": "WhatsApp no configurado"}
    url = f"{WA_GRAPH_URL}/{pid}/messages"
    headers = {"Authorization": f"Bearer {tk}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post(url, json=payload, headers=headers)
            return resp.json()
    except Exception as e:
        logger.error(f"WA send error: {e}")
        return {"error": str(e)}


async def wa_upload_media(file_bytes: bytes, filename: str, mime_type: str, token: str, phone_id: str):
    """Upload a media file to WhatsApp and return the media_id"""
    if not token or not phone_id:
        return {"error": "WhatsApp no configurado"}
    url = f"{WA_GRAPH_URL}/{phone_id}/media"
    files = {
        "file": (filename, file_bytes, mime_type),
        "messaging_product": (None, "whatsapp"),
        "type": (None, mime_type),
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            resp = await c.post(url, files=files, headers=headers)
            return resp.json()
    except Exception as e:
        logger.error(f"WA upload_media error: {e}")
        return {"error": str(e)}


async def wa_send_image(phone: str, media_id: str, caption: str = "", token: str = None, phone_id: str = None):
    """Send a WhatsApp image by media_id via Cloud API"""
    if not token or not phone_id:
        return {"error": "WhatsApp no configurado"}
    url = f"{WA_GRAPH_URL}/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "image",
        "image": {"id": media_id},
    }
    if caption:
        payload["image"]["caption"] = caption
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post(url, json=payload, headers=headers)
            return resp.json()
    except Exception as e:
        logger.error(f"WA send image error: {e}")
        return {"error": str(e)}


async def wa_send_audio(phone: str, media_id: str, token: str = None, phone_id: str = None, as_voice: bool = True):
    """Send a WhatsApp audio/voice note by media_id via Cloud API."""
    if not token or not phone_id:
        return {"error": "WhatsApp no configurado"}
    url = f"{WA_GRAPH_URL}/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "audio",
        "audio": {"id": media_id, "voice": bool(as_voice)},
    }
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post(url, json=payload, headers=headers)
            return resp.json()
    except Exception as e:
        logger.error(f"WA send audio error: {e}")
        return {"error": str(e)}


# ─── WhatsApp Template Messages (mass broadcast to NEW contacts) ──
# Outside the 24h window, Meta REQUIRES sending pre-approved template
# messages. Templates live at the WABA level (not the phone number level),
# so all phone numbers in the same WhatsApp Business Account share the
# same template catalog.

async def wa_fetch_templates(waba_id: str, token: str, status_filter: str = "APPROVED") -> dict:
    """Fetch all message templates for a WABA. Returns {data: [...], paging: {...}} or {error}."""
    if not waba_id or not token:
        return {"error": "WABA id o token faltante"}
    url = f"{WA_GRAPH_URL}/{waba_id}/message_templates"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"fields": "name,status,category,language,components,rejected_reason,quality_score", "limit": 200}
    if status_filter:
        params["status"] = status_filter
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            resp = await c.get(url, headers=headers, params=params)
            return resp.json()
    except Exception as e:
        logger.error(f"WA fetch templates error: {e}")
        return {"error": str(e)}


async def wa_create_template(
    waba_id: str,
    token: str,
    name: str,
    category: str,
    language: str,
    body_text: str,
    header_text: Optional[str] = None,
    header_image_url: Optional[str] = None,
    footer_text: Optional[str] = None,
    buttons: Optional[List[Dict]] = None,
    example_body_vars: Optional[List[str]] = None,
) -> dict:
    """Submit a new template to Meta for approval. Meta validates format
    instantly and returns status=PENDING (or REJECTED) with details."""
    if not waba_id or not token:
        return {"error": "WABA id o token faltante"}

    components: List[Dict] = []
    # Header: text OR image
    if header_text:
        components.append({"type": "HEADER", "format": "TEXT", "text": header_text})
    elif header_image_url:
        components.append({
            "type": "HEADER",
            "format": "IMAGE",
            "example": {"header_handle": [header_image_url]},
        })
    # Body (required)
    body_comp: Dict = {"type": "BODY", "text": body_text}
    if example_body_vars:
        body_comp["example"] = {"body_text": [example_body_vars]}
    components.append(body_comp)
    # Footer
    if footer_text:
        components.append({"type": "FOOTER", "text": footer_text})
    # Buttons
    if buttons:
        components.append({"type": "BUTTONS", "buttons": buttons})

    payload = {
        "name": name,
        "category": category,  # MARKETING / UTILITY / AUTHENTICATION
        "language": language,
        "components": components,
    }
    url = f"{WA_GRAPH_URL}/{waba_id}/message_templates"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post(url, json=payload, headers=headers)
            out = resp.json()
            out["_http_status"] = resp.status_code
            return out
    except Exception as e:
        logger.error(f"WA create template error: {e}")
        return {"error": str(e)}


async def wa_delete_template(waba_id: str, token: str, template_name: str) -> dict:
    """Delete a template by name."""
    url = f"{WA_GRAPH_URL}/{waba_id}/message_templates"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            resp = await c.delete(url, headers=headers, params={"name": template_name})
            data = resp.json()
            # Meta returns 200 with {"success": true} on OK, or {"error": {...}} on failure
            if resp.status_code >= 400 or (isinstance(data, dict) and data.get("error")):
                err = data.get("error") if isinstance(data, dict) else {}
                msg = err.get("message") if isinstance(err, dict) else str(err)
                code = err.get("code") if isinstance(err, dict) else None
                return {"error": msg or "Error desconocido de Meta", "code": code, "raw": data}
            return data
    except Exception as e:
        logger.error(f"WA delete template error: {e}")
        return {"error": str(e)}


async def wa_send_template(
    phone: str,
    template_name: str,
    language: str = "es_AR",
    variables: Optional[List[str]] = None,
    header_image_url: Optional[str] = None,
    token: Optional[str] = None,
    phone_id: Optional[str] = None,
) -> dict:
    """Send a WhatsApp template message via Cloud API.

    `variables` populates the body BODY parameters in order ({{1}}, {{2}}, ...).
    `header_image_url` is set when the template has an IMAGE header.
    Returns Meta's response (with messages[0].id on success) or {error}.
    """
    if not token or not phone_id:
        return {"error": "WhatsApp no configurado"}
    url = f"{WA_GRAPH_URL}/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    components: List[Dict] = []
    if header_image_url:
        components.append({
            "type": "header",
            "parameters": [{"type": "image", "image": {"link": header_image_url}}],
        })
    if variables:
        components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": str(v)} for v in variables],
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
        },
    }
    if components:
        payload["template"]["components"] = components

    try:
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post(url, json=payload, headers=headers)
            return resp.json()
    except Exception as e:
        logger.error(f"WA send template error: {e}")
        return {"error": str(e)}


# ─── Opt-out keyword detection ────────────────────────────────────
# When a contact replies with any of these (case-insensitive, whole-message
# match after normalization), they are auto-added to broadcast_optouts and
# never receive another broadcast on that line.
OPTOUT_KEYWORDS = {
    "baja", "stop", "no", "cancelar", "bajar",
    "no quiero mas", "no quiero más", "remover", "unsubscribe",
}

def is_optout_message(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    if not t:
        return False
    # Strip trailing punctuation/spaces
    t = re.sub(r"[!?.\s]+$", "", t)
    return t in OPTOUT_KEYWORDS


def _pick_welcome_variation(raw_msg: str) -> str:
    """Return a humanized variant of a welcome message.

    Two-tier strategy to avoid looking like a bot to Meta Integrity:
    1. If the cajero wrote multiple variants separated by '---' (3+ dashes on
       their own line), pick one at random. Gives fine-grained control.
    2. If only one variant, apply micro-variations: rotate the opening
       greeting and swap a few cosmetic emojis. Keeps the business content
       intact while breaking the 'identical byte-for-byte message to every
       lead' pattern that Meta flags as automation.
    """
    import random
    import re

    # Tier 1 — explicit variants
    parts = [p.strip() for p in re.split(r"\n\s*-{3,}\s*\n", raw_msg) if p.strip()]
    if len(parts) > 1:
        return random.choice(parts)

    msg = parts[0] if parts else raw_msg.strip()

    # Tier 2 — micro-variations on a single template.
    # 2a. Opening greeting swap — only if the message starts with a common
    #     Spanish greeting so we don't butcher user-authored openings.
    greeting_pool = [
        "¡Hola!", "¡Buenas!", "Hola!", "Buenas!",
        "¡Hola! 👋", "¡Buenas! 👋", "Hola, ¿cómo estás?",
        "¡Hola, cómo va!", "Buen día!",
    ]
    greet_pattern = re.compile(
        r"^(¡?\s*(hola|buenas|buen día|buenos días|buenas tardes|buenas noches)[!\.,\s]*👋?)",
        re.IGNORECASE,
    )
    m = greet_pattern.match(msg)
    if m:
        original = m.group(0)
        new_greet = random.choice(greeting_pool)
        # Preserve trailing space/punctuation after greeting
        rest = msg[len(original):]
        if rest and not rest.startswith((" ", "\n", ".", ",", "!", "?")):
            new_greet = new_greet + " "
        msg = new_greet + rest

    # 2b. Rotate a handful of decorative emojis (purely cosmetic, doesn't
    #     change meaning). Only applies if the message has at least one.
    emoji_swaps = [
        ("🎁", ["🎁", "🎉", "✨"]),
        ("💟", ["💟", "💜", "💖"]),
        ("⭐", ["⭐", "🌟", "✨"]),
        ("🔥", ["🔥", "💥", "⚡"]),
    ]
    for anchor, pool in emoji_swaps:
        if anchor in msg and random.random() < 0.6:
            msg = msg.replace(anchor, random.choice(pool), 1)

    return msg


async def send_auto_welcome(crm_lead: dict, line: dict):
    """
    Auto-send welcome message when a lead sends their FIRST message.
    Takes welcome_message from the first active cajero assigned to the line.
    Falls back to any admin user's welcome_message if no cajero has one.
    Silent no-op if no welcome is configured.

    Meta-Integrity hardening:
      * Randomized 15-75 second delay before the message actually sends.
        Meta's Account Integrity classifier flags sub-second bot replies;
        humans take 10s-1min to read a message and type a response. The
        delay happens in-task so it doesn't block the webhook response.
      * Message content is rotated via _pick_welcome_variation so every
        lead doesn't receive the identical byte-for-byte payload.
    """
    try:
        import random
        import asyncio as _asyncio2

        lead_id = crm_lead.get("id")
        line_id = line.get("id")
        phone = crm_lead.get("phone")
        if not line_id or not phone:
            return

        if not line.get("whatsapp_token") or not line.get("phone_number_id"):
            return

        # Find welcome_message from cajeros assigned to this line first.
        # IMPORTANT: respect the per-cajero `auto_welcome_enabled` flag.
        # A cajero can opt-out of auto-welcome and always send manually via
        # the "👋 Bienvenida" button in the chat panel.
        welcome_msg = None
        welcome_by = None
        async for user in db.users.find({
            "line_ids": line_id,
            "is_active": True,
            "role": "cajero",
        }):
            # Default True for backwards compatibility (existing cajeros
            # without the flag keep the previous behavior).
            if not user.get("auto_welcome_enabled", True):
                continue
            msg = (user.get("welcome_message") or "").strip()
            if msg:
                welcome_msg = msg
                welcome_by = user.get("email")
                break

        # Fallback: any admin with welcome_message (also respects the flag)
        if not welcome_msg:
            async for user in db.users.find({"role": "admin", "is_active": True}):
                if not user.get("auto_welcome_enabled", True):
                    continue
                msg = (user.get("welcome_message") or "").strip()
                if msg:
                    welcome_msg = msg
                    welcome_by = user.get("email")
                    break

        if not welcome_msg:
            logger.info(f"Auto-welcome: no welcome_message configured OR disabled (line={line.get('name')}, lead={lead_id}) — skipping")
            return

        # Pick a humanized variation (rotation + micro-variations)
        welcome_msg = _pick_welcome_variation(welcome_msg)

        # Human-like typing delay: 15-75 seconds (skewed lower so urgency
        # isn't lost). Argentine cajeros typically reply in that range.
        delay_sec = random.randint(15, 75)
        logger.info(f"Auto-welcome: scheduling send in {delay_sec}s for lead {lead_id} on line {line.get('name')}")
        await _asyncio2.sleep(delay_sec)

        # Re-read the lead: if a human cajero already replied during the
        # delay window, skip the auto-welcome (avoid double-greeting).
        fresh = await db.crm_leads.find_one({"id": lead_id}, {"_id": 0})
        if fresh and fresh.get("welcome_sent_at"):
            logger.info(f"Auto-welcome: lead {lead_id} already welcomed, skipping")
            return
        # If there's an admin-authored message since the lead was created,
        # also skip (human cajero took over).
        since = crm_lead.get("created_at") or datetime.now(timezone.utc).isoformat()
        existing_admin = await db.crm_messages.count_documents({
            "lead_id": lead_id,
            "sender": "admin",
            "created_at": {"$gt": since},
        })
        if existing_admin > 0:
            logger.info(f"Auto-welcome: cajero already replied to {lead_id}, skipping")
            return

        # Send the welcome via WhatsApp
        result = await wa_send_text(
            phone=phone,
            message=welcome_msg,
            token=line["whatsapp_token"],
            phone_id=line["phone_number_id"],
        )

        # Persist in chat history so cajero sees it
        now = datetime.now(timezone.utc).isoformat()
        await db.crm_messages.insert_one({
            "id": str(uuid.uuid4()),
            "lead_id": lead_id,
            "content": welcome_msg,
            "sender": "admin",
            "message_type": "text",
            "auto_welcome": True,
            "sent_by": welcome_by,
            "created_at": now,
            "wa_result": result,
        })
        await db.crm_leads.update_one(
            {"id": lead_id},
            {
                "$set": {"last_interaction": now, "updated_at": now, "welcome_sent_at": now},
                "$inc": {"messages_count": 1},
            }
        )
        logger.info(f"Auto-welcome sent to {phone} on line {line.get('name')} (by {welcome_by}, delayed {delay_sec}s)")
    except Exception as e:
        logger.error(f"Auto-welcome failed: {e}")

# Webhook verification (PUBLIC - no auth, Meta calls this)
@api_router.get("/whatsapp/webhook")
async def wa_webhook_verify(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    settings = await get_wa_settings()
    verify = settings.get("verify_token") or WHATSAPP_VERIFY_TOKEN
    if mode == "subscribe" and token == verify:
        logger.info("WhatsApp webhook verified")
        return Response(content=challenge, media_type="text/plain")
    logger.warning(f"WA webhook verify failed: mode={mode}, token={token}")
    raise HTTPException(status_code=403, detail="Verification failed")

async def resend_enriched_landing_events(crm_lead: dict, line: dict):
    """
    Re-fire the Contact / Lead / InitiateCheckout events that were dispatched
    when the user clicked the WhatsApp button on the landing. Uses the SAME
    event_id stored in wa_clicks so Meta deduplicates within the 48h window
    and keeps the event with the highest match quality (EMQ).

    Triggered once per lead, right after the first inbound WhatsApp message,
    so we can now include phone + fn/ln + gender + enriched geo in the same
    Contact/Lead/InitiateCheckout that fired on the click.

    No-op if:
      * The line has no pixel_id/access_token (nothing to send to).
      * No wa_click with stored landing_event_ids can be linked to this lead.
      * The lead was already enriched (welcome_sent_at is a good proxy; we
        also persist `landing_events_enriched_at` to be safe).
    """
    try:
        lead_id = crm_lead.get("id")
        if not lead_id:
            return

        # Idempotency guard — don't re-fire twice for the same lead.
        if crm_lead.get("landing_events_enriched_at"):
            return

        # Pixel credentials: prefer the ones stored on the click (what was
        # originally used), fall back to the current line config.
        access_token = line.get("meta_access_token")
        pixel_id = line.get("meta_pixel_id")

        # Locate the wa_click this lead came from.
        click_doc = None
        click_id = crm_lead.get("click_id")
        if click_id:
            click_doc = await db.wa_clicks.find_one({"click_id": click_id}, {"_id": 0})
        if not click_doc and crm_lead.get("phone"):
            phone_clean = re.sub(r'\D', '', crm_lead["phone"])[-10:]
            click_doc = await db.wa_clicks.find_one(
                {"phone": {"$regex": phone_clean}, "landing_event_ids": {"$exists": True}},
                {"_id": 0},
                sort=[("created_at", -1)],
            )

        if not click_doc:
            logger.info(f"Enriched re-fire: no click associated to lead {lead_id} — skipping")
            return

        stored_ids: dict = click_doc.get("landing_event_ids") or {}
        if not stored_ids:
            return

        # Prefer pixel credentials captured at click time (line config might
        # have changed since).
        access_token = click_doc.get("meta_access_token_snapshot") or access_token
        pixel_id = click_doc.get("meta_pixel_id_snapshot") or pixel_id
        if not access_token or not pixel_id:
            logger.info(f"Enriched re-fire: no pixel for lead {lead_id} — skipping")
            return

        # Build lead_data enriched with everything we now know.
        lead_data = {
            "id": lead_id,
            "phone": crm_lead.get("phone"),
            "name": crm_lead.get("name"),
            "email": crm_lead.get("email"),
            "gender": crm_lead.get("gender"),
            "dob": crm_lead.get("dob"),
            "click_id": click_id or click_doc.get("click_id"),
            "ip_address": click_doc.get("ip") or crm_lead.get("ip_address"),
            "user_agent": click_doc.get("user_agent"),
            "fbp": click_doc.get("fbp"),
            "fbc": click_doc.get("fbc"),
            "ctwa_clid": crm_lead.get("ctwa_clid") or click_doc.get("ctwa_clid"),
            "city": crm_lead.get("city"),
            "state": crm_lead.get("state"),
            "zip_code": crm_lead.get("zip_code"),
            "country_code": crm_lead.get("country_code"),
            "landing_code": click_doc.get("landing_code"),
        }
        landing_name = None
        if click_doc.get("landing_code"):
            try:
                landing = await db.wa_landings.find_one(
                    {"code": click_doc["landing_code"]}, {"_id": 0, "name": 1}
                )
                landing_name = landing.get("name") if landing else None
            except Exception:
                landing_name = None
        custom_data = {"content_name": landing_name or "WA Landing"}

        # Re-fire each event with its original event_id.
        for evt_name, evt_id in stored_ids.items():
            try:
                result = await send_meta_conversion_event(
                    event_name=evt_name,
                    lead_data=lead_data,
                    custom_data=custom_data,
                    access_token=access_token,
                    pixel_id=pixel_id,
                    event_id=evt_id,
                )
                logger.info(
                    f"Enriched re-fire: {evt_name} for lead {lead_id} "
                    f"(event_id={evt_id}, success={result.get('success')})"
                )
            except Exception as e:
                logger.warning(f"Enriched re-fire failed for {evt_name}/{lead_id}: {e}")

        # Mark done to prevent double-firing.
        await db.crm_leads.update_one(
            {"id": lead_id},
            {"$set": {"landing_events_enriched_at": datetime.now(timezone.utc).isoformat()}},
        )
    except Exception as e:
        logger.error(f"resend_enriched_landing_events failed: {e}")


# Webhook receive messages (PUBLIC - no auth, Meta calls this)
@api_router.post("/whatsapp/webhook")
async def wa_webhook_receive(request: Request):
    body = await request.json()
    try:
        entries = body.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                contacts = value.get("contacts", [])
                
                # Get the phone number that RECEIVED this message (your business number)
                metadata = value.get("metadata", {})
                display_phone = metadata.get("display_phone_number", "")
                phone_number_id = metadata.get("phone_number_id", "")
                
                contact_map = {}
                for ct in contacts:
                    wa_id = ct.get("wa_id", "")
                    name = ct.get("profile", {}).get("name", "")
                    contact_map[wa_id] = name

                for msg in messages:
                    from_phone = msg.get("from", "")
                    msg_id = msg.get("id", "")
                    msg_type = msg.get("type", "text")
                    timestamp = msg.get("timestamp", "")
                    text = ""
                    if msg_type == "text":
                        text = msg.get("text", {}).get("body", "")
                    elif msg_type == "button":
                        text = msg.get("button", {}).get("text", "")
                    elif msg_type == "interactive":
                        text = msg.get("interactive", {}).get("button_reply", {}).get("title", "")
                    else:
                        text = f"[{msg_type}]"

                    sender_name = contact_map.get(from_phone, "")
                    now = datetime.now(timezone.utc).isoformat()

                    # Upsert contact (legacy wa_contacts)
                    existing = await db.wa_contacts.find_one({"phone": from_phone})
                    if not existing:
                        await db.wa_contacts.insert_one({
                            "phone": from_phone,
                            "name": sender_name,
                            "classification": "new",
                            "message_count": 1,
                            "first_message_at": now,
                            "last_message_at": now,
                        })
                    else:
                        update_data = {
                            "$inc": {"message_count": 1},
                            "$set": {"last_message_at": now}
                        }
                        if sender_name and not existing.get("name"):
                            update_data["$set"]["name"] = sender_name
                        await db.wa_contacts.update_one({"phone": from_phone}, update_data)

                    # Store message (legacy wa_messages) - with deduplication
                    existing_wa_msg = await db.wa_messages.find_one({"wa_message_id": msg_id})
                    if existing_wa_msg:
                        logger.info(f"WA: Duplicate message {msg_id} ignored")
                        continue
                    
                    await db.wa_messages.insert_one({
                        "id": str(uuid.uuid4()),
                        "wa_message_id": msg_id,
                        "phone": from_phone,
                        "direction": "incoming",
                        "type": msg_type,
                        "text": text,
                        "sender_name": sender_name,
                        "timestamp": timestamp,
                        "created_at": now,
                    })

                    # ═══════════════════════════════════════════════════════════════
                    # CRM INTEGRATION - Create/update lead and add message
                    # ═══════════════════════════════════════════════════════════════
                    
                    # Find the CRM line that matches this WhatsApp number
                    # Clean phone numbers for comparison (remove + and spaces)
                    clean_display = display_phone.replace("+", "").replace(" ", "").replace("-", "")
                    
                    crm_line = None
                    async for line in db.crm_lines.find({"is_active": True}):
                        line_number = line.get("whatsapp_number", "").replace("+", "").replace(" ", "").replace("-", "")
                        if line_number and (line_number in clean_display or clean_display in line_number):
                            crm_line = line
                            break
                    
                    # Find or create CRM lead — per line, so same phone can exist on multiple lines
                    target_line_id = crm_line["id"] if crm_line else None
                    
                    if target_line_id:
                        # First try to find lead already assigned to this specific line
                        crm_lead = await db.crm_leads.find_one({"phone": from_phone, "line_id": target_line_id})
                        if not crm_lead:
                            # Check for unassigned lead
                            crm_lead = await db.crm_leads.find_one({"phone": from_phone, "line_id": None})
                            if crm_lead:
                                # Assign unassigned lead to this line
                                await db.crm_leads.update_one(
                                    {"id": crm_lead["id"]},
                                    {"$set": {"line_id": target_line_id, "updated_at": now}}
                                )
                                crm_lead["line_id"] = target_line_id
                            # If lead exists on a DIFFERENT line, crm_lead stays None → new lead created below
                    else:
                        # No line matched — find any lead with this phone
                        crm_lead = await db.crm_leads.find_one({"phone": from_phone})
                    
                    if not crm_lead:
                        # Create new lead in CRM (one per line)
                        lead_id = str(uuid.uuid4())
                        crm_lead = {
                            "id": lead_id,
                            "name": sender_name or f"Lead {from_phone[-4:]}",
                            "email": None,
                            "phone": from_phone,
                            "status": "nuevo",
                            "score": 50,
                            "source": "whatsapp",
                            "line_id": target_line_id,
                            "charge_amount": 0.0,
                            "metadata": {
                                "phone_number_id": phone_number_id,
                                "display_phone": display_phone,
                            },
                            "notes": "",
                            "tags": ["webhook"],
                            "created_at": now,
                            "updated_at": now,
                            "last_interaction": now,
                            "messages_count": 0,
                            "receipts_count": 0,
                            "meta_events_sent": [],
                        }
                        await db.crm_leads.insert_one(crm_lead)
                        logger.info(f"CRM: Created new lead for {from_phone}, line: {crm_line['name'] if crm_line else 'None'}")
                        
                        # Send Contact event to Meta if line has credentials
                        if crm_line and crm_line.get("meta_access_token") and crm_line.get("meta_pixel_id"):
                            contact_result = await send_meta_conversion_event(
                                event_name="Contact",
                                lead_data=crm_lead,
                                custom_data={"content_name": "WhatsApp Contact"},
                                access_token=crm_line["meta_access_token"],
                                pixel_id=crm_line["meta_pixel_id"]
                            )
                            await db.crm_leads.update_one(
                                {"id": lead_id},
                                {"$push": {"meta_events_sent": {
                                    "event": "Contact",
                                    "timestamp": now,
                                    "event_id": contact_result.get("event_id"),
                                    "pixel_id": crm_line.get("meta_pixel_id", "")[:8] + "..." if crm_line.get("meta_pixel_id") else None,
                                    "line": crm_line.get("name"),
                                    "success": contact_result.get("success", False)
                                }}}
                            )

                        # Auto-send welcome message (fire-and-forget) if line is configured
                        if crm_line and crm_line.get("whatsapp_token") and crm_line.get("phone_number_id"):
                            import asyncio as _asyncio
                            _asyncio.create_task(send_auto_welcome(crm_lead, crm_line))
                            # Re-fire landing CAPI events with enriched data
                            # so Meta deduplicates & upgrades match quality
                            # (uses event_ids stored on the click).
                            _asyncio.create_task(resend_enriched_landing_events(crm_lead, crm_line))
                    else:
                        # Update existing lead
                        update_fields = {
                            "last_interaction": now,
                            "updated_at": now,
                        }
                        if sender_name and not crm_lead.get("name"):
                            update_fields["name"] = sender_name
                        
                        await db.crm_leads.update_one(
                            {"id": crm_lead["id"]},
                            {"$set": update_fields}
                        )
                    
                    # Add message to CRM lead chat
                    crm_message = {
                        "id": str(uuid.uuid4()),
                        "lead_id": crm_lead["id"] if crm_lead else None,
                        "content": text,
                        "sender": "lead",
                        "wa_message_id": msg_id,
                        "message_type": msg_type,
                        "created_at": now,
                    }
                    
                    if crm_lead:
                        crm_message["lead_id"] = crm_lead.get("id") or (await db.crm_leads.find_one({"phone": from_phone}))["id"]
                        await db.crm_messages.insert_one(crm_message)
                        
                        # Update message count
                        await db.crm_leads.update_one(
                            {"phone": from_phone},
                            {"$inc": {"messages_count": 1, "unread_count": 1}}
                        )

                        # Fire web push notification to every cajero assigned to this line
                        if crm_line:
                            import asyncio as _asyncio
                            fresh_lead = await db.crm_leads.find_one({"phone": from_phone}, {"_id": 0}) or crm_lead
                            preview_text = text if msg_type == "text" else f"[{msg_type}]"
                            _asyncio.create_task(notify_line_cajeros_of_new_message(fresh_lead, crm_line, preview_text))
                    
                    # ═══════════════════════════════════════════════════════════════

                    # Try to correlate click_id from message text (tolerant regex)
                    # Accepts: "(ID: ABC12)", "(id:abc12)", "ID: ABC12", "id abc12", etc.
                    import re as re_mod
                    id_match = re_mod.search(
                        r'(?i)ID[:\s]*([A-Z0-9]{5,8})', text
                    )
                    if id_match:
                        click_id = id_match.group(1).upper()
                        click_data = await db.wa_clicks.find_one({"click_id": click_id}, {"_id": 0})
                        if click_data:
                            await db.wa_contacts.update_one(
                                {"phone": from_phone},
                                {"$set": {
                                    "click_id": click_id,
                                    "landing_code": click_data.get("landing_code", ""),
                                    "fbp": click_data.get("fbp", ""),
                                    "fbc": click_data.get("fbc", ""),
                                    "click_ip": click_data.get("ip", ""),
                                    "click_device": click_data.get("device", ""),
                                    "click_os": click_data.get("os", ""),
                                    "click_browser": click_data.get("browser", ""),
                                    "utm_content": click_data.get("utm_content", ""),
                                    "utm_campaign": click_data.get("utm_campaign", ""),
                                }}
                            )
                            # Also propagate fbc/fbp/click_id to crm_lead so Purchase events can use them
                            await db.crm_leads.update_one(
                                {"phone": from_phone},
                                {"$set": {
                                    "click_id": click_id,
                                    "landing_code": click_data.get("landing_code", ""),
                                    "fbp": click_data.get("fbp", ""),
                                    "fbc": click_data.get("fbc", ""),
                                    "ip_address": click_data.get("ip", ""),
                                    "user_agent": click_data.get("user_agent", ""),
                                }}
                            )

                    # ═══ Meta Click-to-WhatsApp Ads referral capture ═══
                    # When user comes from a CTWA Ad, msg.referral contains:
                    # source_url, source_id, source_type, headline, body, ctwa_clid
                    # This data PERSISTS even if user deletes the prefilled message.
                    referral_data = msg.get("referral")
                    msg_context = msg.get("context", {}) or {}
                    ctwa_clid = None
                    ad_source = None
                    utm_content = None
                    fb_login_id = None
                    if referral_data:
                        ctwa_clid = referral_data.get("ctwa_clid")
                        ad_source = referral_data.get("source_id") or referral_data.get("headline") or "meta_ad"
                        utm_content = referral_data.get("source_id", "")
                        fb_login_id = referral_data.get("fb_login_id")
                        logger.info(
                            f"WA webhook (legacy): CTWA ad referral captured | phone={from_phone} | "
                            f"source_id={referral_data.get('source_id')} | ctwa_clid={ctwa_clid}"
                        )
                    if msg_context.get("fb_login_id") and not fb_login_id:
                        fb_login_id = msg_context.get("fb_login_id")

                    if ctwa_clid or ad_source or fb_login_id or referral_data:
                        lead_fb_update = {}
                        if ctwa_clid:
                            lead_fb_update["ctwa_clid"] = ctwa_clid
                        if ad_source:
                            lead_fb_update["ad_source"] = ad_source
                        if utm_content:
                            lead_fb_update["utm_content"] = utm_content
                        if fb_login_id:
                            lead_fb_update["fb_login_id"] = fb_login_id
                        if referral_data:
                            lead_fb_update["referral"] = referral_data
                        if lead_fb_update:
                            await db.crm_leads.update_one(
                                {"phone": from_phone},
                                {"$set": lead_fb_update}
                            )
                            await db.wa_contacts.update_one(
                                {"phone": from_phone},
                                {"$set": lead_fb_update}
                            )

                    # Auto-reply for new contacts
                    settings = await get_wa_settings()
                    is_first = not existing
                    if is_first and settings.get("auto_reply_enabled"):
                        auto_msg = settings.get("auto_reply_message", "")
                        if auto_msg:
                            result = await wa_send_text(from_phone, auto_msg)
                            if not result.get("error"):
                                await db.wa_messages.insert_one({
                                    "id": str(uuid.uuid4()),
                                    "wa_message_id": "",
                                    "phone": from_phone,
                                    "direction": "outgoing",
                                    "type": "text",
                                    "text": auto_msg,
                                    "sender_name": "Sistema",
                                    "timestamp": "",
                                    "created_at": datetime.now(timezone.utc).isoformat(),
                                })

    except Exception as e:
        logger.error(f"WA webhook error: {e}")
    return {"status": "ok"}

# CRM endpoints (with auth)
@api_router.get("/whatsapp/settings")
async def wa_get_settings(current_user=Depends(get_current_user)):
    settings = await get_wa_settings()
    # Mask token for security
    if settings.get("whatsapp_token"):
        tk = settings["whatsapp_token"]
        settings["whatsapp_token_masked"] = tk[:10] + "..." + tk[-4:] if len(tk) > 14 else "***"
    return settings

@api_router.post("/whatsapp/settings")
async def wa_update_settings(data: WASettingsUpdate, current_user=Depends(get_current_user)):
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="Nada que actualizar")
    await get_wa_settings()  # ensure exists
    await db.wa_settings.update_one({}, {"$set": update})
    return {"message": "Configuracion actualizada"}

@api_router.get("/whatsapp/conversations")
async def wa_get_conversations(
    classification: Optional[str] = None,
    search: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    query = {}
    if classification and classification != "all":
        query["classification"] = classification
    if search:
        query["$or"] = [
            {"phone": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}},
        ]
    contacts = await db.wa_contacts.find(query, {"_id": 0}).sort("last_message_at", -1).to_list(200)
    # Get last message for each contact
    for contact in contacts:
        last_msg = await db.wa_messages.find_one(
            {"phone": contact["phone"]},
            {"_id": 0, "text": 1, "direction": 1, "created_at": 1},
            sort=[("created_at", -1)]
        )
        contact["last_message"] = last_msg
    return contacts

@api_router.get("/whatsapp/conversations/{phone}")
async def wa_get_conversation(phone: str, current_user=Depends(get_current_user)):
    contact = await db.wa_contacts.find_one({"phone": phone}, {"_id": 0})
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    messages = await db.wa_messages.find(
        {"phone": phone}, {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    return {"contact": contact, "messages": messages}

@api_router.post("/whatsapp/send")
async def wa_send(data: WASendMessage, current_user=Depends(get_current_user)):
    if not data.phone or not data.message:
        raise HTTPException(status_code=400, detail="Telefono y mensaje requeridos")
    result = await wa_send_text(data.phone, data.message)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    # Store outgoing message
    await db.wa_messages.insert_one({
        "id": str(uuid.uuid4()),
        "wa_message_id": result.get("messages", [{}])[0].get("id", ""),
        "phone": data.phone,
        "direction": "outgoing",
        "type": "text",
        "text": data.message,
        "sender_name": "Agente",
        "timestamp": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"message": "Mensaje enviado", "result": result}

@api_router.post("/whatsapp/conversations/{phone}/classify")
async def wa_classify_contact(phone: str, data: WAClassify, current_user=Depends(get_current_user)):
    """Classify contact and send event to Meta if configured"""
    if data.classification not in ("human", "bot", "spam", "new"):
        raise HTTPException(status_code=400, detail="Clasificacion invalida")
    
    result = await db.wa_contacts.update_one(
        {"phone": phone},
        {"$set": {"classification": data.classification}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    
    # Also update CRM lead if exists
    crm_lead = await db.crm_leads.find_one({"phone": phone})
    meta_result = None
    event_sent = None
    
    if crm_lead:
        # Map classification to CRM status
        status_map = {
            "human": "valido",
            "bot": "spam",
            "spam": "spam",
            "new": "nuevo"
        }
        new_status = status_map.get(data.classification, "nuevo")
        
        await db.crm_leads.update_one(
            {"phone": phone},
            {"$set": {
                "status": new_status,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Send event to Meta if lead has a line with pixel configured
        if crm_lead.get("line_id"):
            line = await db.crm_lines.find_one({"id": crm_lead["line_id"]})
            if line and line.get("meta_access_token") and line.get("meta_pixel_id"):
                if data.classification == "human":
                    # Send Purchase event (value from charge_amount if available)
                    charge = float(crm_lead.get("charge_amount", 0) or 0)
                    meta_result = await send_meta_conversion_event(
                        event_name="Purchase",
                        lead_data=crm_lead,
                        custom_data={"currency": PURCHASE_CURRENCY, "value": charge, "content_type": "product"},
                        access_token=line["meta_access_token"],
                        pixel_id=line["meta_pixel_id"]
                    )
                    event_sent = "Purchase"
                elif data.classification in ["bot", "spam"]:
                    # Send LowQualityLead event
                    meta_result = await send_meta_conversion_event(
                        event_name="LowQualityLead",
                        lead_data=crm_lead,
                        custom_data={"lead_quality": data.classification},
                        access_token=line["meta_access_token"],
                        pixel_id=line["meta_pixel_id"]
                    )
                    event_sent = "LowQualityLead"
    
    return {
        "message": f"Contacto clasificado como {data.classification}",
        "event_sent": event_sent,
        "meta_result": meta_result
    }

@api_router.get("/whatsapp/stats")
async def wa_get_stats(current_user=Depends(get_current_user)):
    total = await db.wa_contacts.count_documents({})
    humans = await db.wa_contacts.count_documents({"classification": "human"})
    bots = await db.wa_contacts.count_documents({"classification": "bot"})
    spam = await db.wa_contacts.count_documents({"classification": "spam"})
    new_contacts = await db.wa_contacts.count_documents({"classification": "new"})
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    messages_today = await db.wa_messages.count_documents({"created_at": {"$gte": today}})
    total_messages = await db.wa_messages.count_documents({})
    return {
        "total_contacts": total,
        "humans": humans,
        "bots": bots,
        "spam": spam,
        "new_contacts": new_contacts,
        "messages_today": messages_today,
        "total_messages": total_messages,
    }


@api_router.post("/whatsapp/sync-to-crm")
async def wa_sync_to_crm(line_id: str = Query(..., description="CRM Line ID to assign contacts to"), current_user=Depends(get_current_user)):
    """Sync all wa_contacts to crm_leads for a specific line"""
    line = await db.crm_lines.find_one({"id": line_id})
    if not line:
        raise HTTPException(status_code=404, detail="Línea no encontrada")
    
    synced = 0
    async for contact in db.wa_contacts.find():
        phone = contact.get("phone")
        
        # Check if lead already exists
        existing = await db.crm_leads.find_one({"phone": phone})
        if existing:
            # Update line_id if not set
            if not existing.get("line_id"):
                await db.crm_leads.update_one(
                    {"phone": phone},
                    {"$set": {"line_id": line_id}}
                )
                synced += 1
            continue
        
        # Map wa classification to crm status
        status_map = {
            "human": "valido",
            "bot": "spam",
            "spam": "spam",
            "new": "nuevo"
        }
        status = status_map.get(contact.get("classification", "new"), "nuevo")
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Create new CRM lead
        lead = {
            "id": str(uuid.uuid4()),
            "name": contact.get("name") or f"Lead {phone[-4:]}",
            "email": None,
            "phone": phone,
            "status": status,
            "score": 50 if status == "nuevo" else (100 if status == "valido" else 0),
            "source": "whatsapp",
            "line_id": line_id,
            "charge_amount": 0.0,
            "metadata": {},
            "notes": "",
            "tags": ["synced"],
            "created_at": contact.get("first_message_at", now),
            "updated_at": now,
            "last_interaction": contact.get("last_message_at", now),
            "messages_count": contact.get("message_count", 0),
            "receipts_count": 0,
            "meta_events_sent": [],
        }
        await db.crm_leads.insert_one(lead)
        
        # Also sync messages
        async for msg in db.wa_messages.find({"phone": phone}):
            crm_msg = {
                "id": str(uuid.uuid4()),
                "lead_id": lead["id"],
                "content": msg.get("text", ""),
                "sender": "admin" if msg.get("direction") == "outgoing" else "lead",
                "wa_message_id": msg.get("wa_message_id"),
                "message_type": msg.get("type", "text"),
                "created_at": msg.get("created_at", now),
            }
            await db.crm_messages.insert_one(crm_msg)
        
        synced += 1
    
    return {"synced": synced, "line_name": line["name"]}



# ─── WhatsApp Landings ─────────────────────────────────────────────

class WALandingCreate(BaseModel):
    name: str
    brand_name: str = "Mi Marca"
    logo_url: Optional[str] = ""
    bg_image_url: Optional[str] = ""
    color_primary: str = "#9A3ACD"
    color_glow: str = "#611589"
    title: str = "ACCESO VIP"
    title_color: str = "#FFFFFF"
    subtitle: str = ""
    subtitle_color: str = "#FFFFFF"
    bonus_text: str = ""
    bonus_color: str = "#FFFFFF"
    button_text: str = "Ir a WhatsApp Ahora"
    button_color: str = "#FFFFFF"
    button_bg: str = "#4AD810"
    wa_numbers: List[str] = []
    wa_message: str = "Hola! Quiero mi usuario."
    show_reviews: bool = True
    show_notifications: bool = True
    is_active: bool = True
    pixel_id: Optional[str] = ""
    pixel_events: Optional[List[str]] = ["PageView", "Lead"]
    meta_access_token: Optional[str] = ""  # For Conversions API
    crm_line_id: Optional[str] = ""  # Link to CRM line

class WALandingUpdate(BaseModel):
    name: Optional[str] = None
    brand_name: Optional[str] = None
    logo_url: Optional[str] = None
    bg_image_url: Optional[str] = None
    color_primary: Optional[str] = None
    color_glow: Optional[str] = None
    title: Optional[str] = None
    title_color: Optional[str] = None
    subtitle: Optional[str] = None
    subtitle_color: Optional[str] = None
    bonus_text: Optional[str] = None
    bonus_color: Optional[str] = None
    button_text: Optional[str] = None
    button_color: Optional[str] = None
    button_bg: Optional[str] = None
    wa_numbers: Optional[List[str]] = None
    wa_message: Optional[str] = None
    show_reviews: Optional[bool] = None
    show_notifications: Optional[bool] = None
    is_active: Optional[bool] = None
    pixel_id: Optional[str] = None
    pixel_events: Optional[List[str]] = None
    meta_access_token: Optional[str] = None  # For Conversions API
    crm_line_id: Optional[str] = None  # Link to CRM line

def generate_landing_code(length=6) -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))

@api_router.get("/wa-landings")
async def get_wa_landings(current_user=Depends(get_current_user)):
    landings = await db.wa_landings.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return landings

# ─── WA Landing Forensics ──────────────────────────────────────────

@api_router.get("/wa-landings/clicks/search")
async def wa_landing_clicks_search(
    ip: str = Query(None),
    landing_code: str = Query(None),
    wa_clicked: bool = Query(None),
    device: str = Query(None),
    days: int = Query(7, ge=1, le=90),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user)
):
    """Search WA Landing clicks with filters for forensics analysis"""
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    query = {"created_at": {"$gte": date_from}}
    
    if ip:
        query["ip"] = {"$regex": ip}
    if landing_code:
        query["landing_code"] = landing_code
    if wa_clicked is not None:
        query["wa_clicked"] = wa_clicked
    if device:
        query["device"] = device

    total = await db.wa_clicks.count_documents(query)
    skip = (page - 1) * limit
    clicks = await db.wa_clicks.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    # Enrich with landing name
    for click in clicks:
        landing = await db.wa_landings.find_one({"code": click.get("landing_code")}, {"_id": 0, "name": 1})
        click["landing_name"] = landing["name"] if landing else "Desconocida"

    return {"clicks": clicks, "total": total, "page": page, "pages": (total + limit - 1) // limit}

@api_router.get("/wa-landings/clicks/{click_id}")
async def wa_landing_click_detail(click_id: str, current_user=Depends(get_current_user)):
    """Get detailed info about a specific WA Landing click"""
    click = await db.wa_clicks.find_one({"id": click_id}, {"_id": 0})
    if not click:
        raise HTTPException(status_code=404, detail="Click no encontrado")
    
    # Get landing info
    landing = await db.wa_landings.find_one({"code": click.get("landing_code")}, {"_id": 0, "name": 1, "wa_numbers": 1})
    click["landing_name"] = landing["name"] if landing else "Desconocida"
    click["landing_wa_numbers"] = landing.get("wa_numbers", []) if landing else []
    
    # Check if Meta IP
    click["is_meta_ip"] = any(click.get("ip", "").startswith(p) for p in META_IP_PREFIXES)
    
    return click

@api_router.get("/wa-landings/forensics/stats")
async def wa_landing_forensics_stats(
    days: int = Query(7, ge=1, le=90),
    current_user=Depends(get_current_user)
):
    """Get aggregated forensics stats for WA Landings"""
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    total_clicks = await db.wa_clicks.count_documents({"created_at": {"$gte": date_from}})
    wa_conversions = await db.wa_clicks.count_documents({"created_at": {"$gte": date_from}, "wa_clicked": True})
    bot_clicks = await db.wa_clicks.count_documents({"created_at": {"$gte": date_from}, "is_bot": True})
    
    # By device
    device_pipeline = [
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$group": {"_id": "$device", "count": {"$sum": 1}, "wa_clicks": {"$sum": {"$cond": [{"$eq": ["$wa_clicked", True]}, 1, 0]}}}},
        {"$sort": {"count": -1}}
    ]
    by_device = []
    async for r in db.wa_clicks.aggregate(device_pipeline):
        by_device.append({"device": r["_id"] or "Unknown", "count": r["count"], "wa_clicks": r["wa_clicks"]})
    
    # By landing
    landing_pipeline = [
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$group": {"_id": "$landing_code", "count": {"$sum": 1}, "wa_clicks": {"$sum": {"$cond": [{"$eq": ["$wa_clicked", True]}, 1, 0]}}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    by_landing = []
    async for r in db.wa_clicks.aggregate(landing_pipeline):
        landing = await db.wa_landings.find_one({"code": r["_id"]}, {"_id": 0, "name": 1})
        by_landing.append({
            "landing_code": r["_id"],
            "landing_name": landing["name"] if landing else "Desconocida",
            "count": r["count"],
            "wa_clicks": r["wa_clicks"]
        })
    
    # Score distribution
    score_pipeline = [
        {"$match": {"created_at": {"$gte": date_from}, "behavioral_score": {"$exists": True}}},
        {"$group": {"_id": None, "avg_score": {"$avg": "$behavioral_score"}}}
    ]
    avg_score = 0
    async for r in db.wa_clicks.aggregate(score_pipeline):
        avg_score = round(r["avg_score"], 1) if r["avg_score"] else 0
    
    return {
        "total_clicks": total_clicks,
        "wa_conversions": wa_conversions,
        "conversion_rate": round((wa_conversions / total_clicks * 100), 1) if total_clicks > 0 else 0,
        "bot_clicks": bot_clicks,
        "avg_behavioral_score": avg_score,
        "by_device": by_device,
        "by_landing": by_landing
    }

@api_router.get("/wa-landings/{landing_id}")
async def get_wa_landing(landing_id: str, current_user=Depends(get_current_user)):
    landing = await db.wa_landings.find_one({"id": landing_id}, {"_id": 0})
    if not landing:
        raise HTTPException(status_code=404, detail="Landing no encontrada")
    return landing

@api_router.post("/wa-landings")
async def create_wa_landing(data: WALandingCreate, current_user=Depends(get_current_user)):
    code = generate_landing_code()
    while await db.wa_landings.find_one({"code": code}):
        code = generate_landing_code()
    landing = {
        "id": str(uuid.uuid4()),
        "code": code,
        **data.model_dump(),
        "total_clicks": 0,
        "total_wa_clicks": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.wa_landings.insert_one(landing)
    landing.pop("_id", None)
    return landing

@api_router.put("/wa-landings/{landing_id}")
async def update_wa_landing(landing_id: str, data: WALandingUpdate, current_user=Depends(get_current_user)):
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="Nada que actualizar")
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await db.wa_landings.update_one({"id": landing_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Landing no encontrada")
    landing = await db.wa_landings.find_one({"id": landing_id}, {"_id": 0})
    return landing

@api_router.delete("/wa-landings/{landing_id}")
async def delete_wa_landing(landing_id: str, current_user=Depends(get_current_user)):
    result = await db.wa_landings.delete_one({"id": landing_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Landing no encontrada")
    return {"message": "Landing eliminada"}

@api_router.get("/wa-landings/{landing_id}/stats")
async def get_wa_landing_stats(landing_id: str, current_user=Depends(get_current_user)):
    landing = await db.wa_landings.find_one({"id": landing_id}, {"_id": 0, "code": 1})
    if not landing:
        raise HTTPException(status_code=404, detail="Landing no encontrada")
    code = landing["code"]
    total_clicks = await db.wa_clicks.count_documents({"landing_code": code})
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    clicks_today = await db.wa_clicks.count_documents({"landing_code": code, "created_at": {"$gte": today}})
    wa_clicks = await db.wa_clicks.count_documents({"landing_code": code, "wa_clicked": True})
    return {"total_clicks": total_clicks, "clicks_today": clicks_today, "wa_clicks": wa_clicks}

def build_landing_html(landing: dict, base_url: str = "") -> str:
    """Generate the aggressive WhatsApp landing page HTML with Meta Pixel support"""
    code = landing.get("code", "")
    brand = landing.get("brand_name", "Mi Marca")
    logo = landing.get("logo_url", "")
    bg_img = landing.get("bg_image_url", "")
    color_p = landing.get("color_primary", "#9A3ACD")
    color_g = landing.get("color_glow", "#611589")
    title = landing.get("title", "ACCESO VIP")
    title_c = landing.get("title_color", "#FFFFFF")
    subtitle = landing.get("subtitle", "")
    subtitle_c = landing.get("subtitle_color", "#FFFFFF")
    bonus = landing.get("bonus_text", "")
    bonus_c = landing.get("bonus_color", "#FFFFFF")
    btn_text = landing.get("button_text", "Ir a WhatsApp Ahora")
    btn_color = landing.get("button_color", "#FFFFFF")
    btn_bg = landing.get("button_bg", "#4AD810")
    wa_numbers = landing.get("wa_numbers", [])
    wa_message = landing.get("wa_message", "Hola!")
    show_reviews = landing.get("show_reviews", True)
    show_notif = landing.get("show_notifications", True)
    pixel_id = landing.get("pixel_id", "")
    pixel_events = landing.get("pixel_events", ["PageView", "Lead"])

    numbers_js = str(wa_numbers).replace("'", '"')
    bg_style = f'url({bg_img})' if bg_img else 'none'
    logo_html = f'<img src="{logo}" alt="Logo" style="width:120px;height:120px;border-radius:50%;margin-bottom:16px;filter:drop-shadow(0 0 7px {color_g}80) drop-shadow(0 0 15px {color_g}60);object-fit:cover;">' if logo else ''

    subtitle_html = f'<p class="subtitle">{subtitle}</p>' if subtitle else ''
    bonus_html = f'<div class="bonus-badge">{bonus}</div>' if bonus else ''

    # Meta Pixel code injection
    pixel_script = ""
    pixel_pageview = ""
    pixel_wa_click = ""
    if pixel_id:
        pixel_script = f'''<!-- Meta Pixel Code with Advanced Matching -->
<script>
!function(f,b,e,v,n,t,s)
{{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)}};
if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];
s.parentNode.insertBefore(t,s)}}(window, document,'script',
'https://connect.facebook.net/en_US/fbevents.js');
fbq('init', '{pixel_id}', {{}});
fbq('set', 'autoConfig', true, '{pixel_id}');
</script>
<noscript><img height="1" width="1" style="display:none"
src="https://www.facebook.com/tr?id={pixel_id}&ev=PageView&noscript=1"/></noscript>
<!-- End Meta Pixel Code -->'''
        
        # PageView event (fires on page load)
        if "PageView" in pixel_events:
            pixel_pageview = f"fbq('track', 'PageView');"
        
        # Lead/Contact event (fires on WhatsApp click) — with eventID for CAPI deduplication
        pixel_wa_click_events = []
        if "Lead" in pixel_events:
            pixel_wa_click_events.append("fbq('track','Lead',{},{eventID:'Lead_'+clickId+'_'+Math.floor(Date.now()/1000)});")
        if "Contact" in pixel_events:
            pixel_wa_click_events.append("fbq('track','Contact',{},{eventID:'Contact_'+clickId+'_'+Math.floor(Date.now()/1000)});")
        if "InitiateCheckout" in pixel_events:
            pixel_wa_click_events.append("fbq('track','InitiateCheckout',{},{eventID:'InitiateCheckout_'+clickId+'_'+Math.floor(Date.now()/1000)});")
        pixel_wa_click = "\n".join(pixel_wa_click_events)

    reviews_html = ""
    if show_reviews:
        reviews_html = """<div class="review-box">
<div class="stars">&#11088;&#11088;&#11088;&#11088;&#11088;</div>
<p class="review-text"></p>
<span class="reviewer"></span>
</div>"""

    notif_html = ""
    if show_notif:
        notif_html = """<div id="toast" class="toast"><div class="toast-icon">&#128176;</div>
<div><span class="toast-title">Nuevo Retiro!</span><br>
<span id="toastName"></span> retiro <strong id="toastAmount" class="toast-green"></strong></div></div>"""

    return f'''<!DOCTYPE html><html lang="es"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{brand}</title>
<meta property="og:title" content="{brand}"/>
<meta property="og:description" content="{title}"/>
<meta property="og:type" content="website"/>
{pixel_script}
<!-- Meta CAPI Parameter Builder SDK (official) — builds _fbc/_fbp with the
     required appendix so Meta credits them for +EMQ and stops the
     "modified fbclid" warning. Loaded sync from jsDelivr so it's ready
     before our tracking fetch fires. -->
<script src="https://cdn.jsdelivr.net/npm/meta-capi-param-builder-clientjs@1.3.0/dist/clientParamBuilder.bundle.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;900&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Poppins',sans-serif;background:#0a0a0a;color:#fff;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;overflow-x:hidden}}
.bg{{position:fixed;inset:0;background:linear-gradient(rgba(0,0,0,.82),rgba(0,0,0,.82)),{bg_style} center/cover no-repeat;z-index:0}}
.container{{position:relative;z-index:1;max-width:440px;width:100%;padding:24px;text-align:center;display:flex;flex-direction:column;align-items:center;gap:16px}}
.brand{{font-size:1.4rem;font-weight:900;text-transform:uppercase;letter-spacing:2px;color:{title_c};text-shadow:0 0 7px {color_g}80,0 0 15px {color_g}60,0 0 30px {color_g}40;animation:pulse 2s ease-in-out infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.8}}}}
.subtitle{{background:rgba(0,0,0,.3);border:1px solid {subtitle_c}40;border-radius:50px;padding:8px 16px;font-size:.8rem;font-weight:600;color:{subtitle_c}}}
.wa-btn{{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;max-width:360px;padding:16px 24px;border-radius:50px;border:none;font-size:1.1rem;font-weight:700;cursor:pointer;color:{btn_color};background:{btn_bg};box-shadow:0 0 15px {btn_bg}60,0 0 30px {btn_bg}30;transition:all .2s;text-decoration:none;animation:sway 2s ease-in-out infinite}}
@keyframes sway{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.03)}}}}
.wa-btn:hover{{transform:scale(1.05);box-shadow:0 0 25px {btn_bg}80}}
.wa-btn svg{{width:24px;height:24px;fill:{btn_color}}}
.bonus-badge{{background:rgba(0,0,0,.3);border:1px solid {bonus_c}40;border-radius:50px;padding:8px 16px;font-size:.75rem;font-weight:600;color:{bonus_c}}}
.review-box{{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:16px;padding:16px;max-width:360px;width:100%}}
.stars{{font-size:1.2rem;margin-bottom:6px}}
.review-text{{font-size:.8rem;color:#ccc;font-style:italic;margin-bottom:4px}}
.reviewer{{font-size:.7rem;color:#888}}
.toast{{position:fixed;bottom:20px;left:20px;background:#1a0505;border:1px solid #333;border-radius:12px;padding:12px 16px;display:flex;align-items:center;gap:10px;transform:translateY(120px);opacity:0;transition:all .4s;z-index:99;max-width:320px}}
.toast.show{{transform:translateY(0);opacity:1}}
.toast-icon{{font-size:1.4rem}}
.toast-title{{font-size:.75rem;font-weight:700;color:#fff}}
.toast-green{{color:#4AD810}}
.live-bar{{position:fixed;top:0;left:0;right:0;background:rgba(0,0,0,.8);padding:8px;text-align:center;font-size:.7rem;color:#aaa;z-index:99;display:flex;align-items:center;justify-content:center;gap:6px}}
.pulse-dot{{width:8px;height:8px;background:#4AD810;border-radius:50%;animation:blink 1.5s infinite}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.footer{{font-size:.55rem;color:#555;text-align:center;padding:16px;max-width:360px}}
</style></head><body>
<div class="bg"></div>
<div class="live-bar"><div class="pulse-dot"></div>EN VIVO: <span id="liveCount">4568</span>+ jugando</div>
<div class="container">
{logo_html}
<h1 class="brand">{title}</h1>
{subtitle_html}
{reviews_html}
<button class="wa-btn" id="waBtn" onclick="goWA()">
<svg viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.625.846 5.059 2.284 7.034L.789 23.492l4.625-1.469A11.958 11.958 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.75c-2.17 0-4.207-.68-5.893-1.834l-.422-.281-2.744.872.728-2.663-.307-.467A9.714 9.714 0 012.25 12C2.25 6.615 6.615 2.25 12 2.25S21.75 6.615 21.75 12 17.385 21.75 12 21.75z"/></svg>
{btn_text}
</button>
{bonus_html}
</div>
{notif_html}
<div class="footer">Plataforma de entretenimiento digital. Exclusivo mayores de 18+. Juegue con responsabilidad.</div>
<script>
var WA_NUMBERS={numbers_js};
var WA_MSG="{wa_message.replace('"', "&quot;")}";
var LANDING_CODE="{code}";
var BASE_URL="{base_url}";

function gID(){{var c="ABCDEFGHJKLMNPQRSTUVWXYZ23456789",r="";for(var i=0;i<5;i++)r+=c[Math.floor(Math.random()*c.length)];return r}}
function getCk(n){{var m=document.cookie.match(new RegExp("(^| )"+n+"=([^;]+)"));return m?m[2]:""}}
function setCk(n,v){{document.cookie=n+"="+v+";path=/;max-age=63072000"}}
function getFBP(){{var f=getCk("_fbp");if(!f){{f="fb.1."+Date.now()+"."+Math.floor(Math.random()*1e10);setCk("_fbp",f)}};return f}}
function getFBC(){{var p=new URLSearchParams(window.location.search),c=p.get("fbclid");if(!c)return"";var f="fb.1."+Date.now()+"."+c;setCk("_fbc",f);return f}}

// Meta CAPI Parameter Builder — initialize once, adds the server appendix
// to _fbc/_fbp. Falls back to the legacy getFBP/getFBC if the SDK failed
// to load (adblocker, CDN issue, etc).
var _PB_READY=false;
(function(){{try{{
  if(typeof clientParamBuilder!=="undefined"&&clientParamBuilder.processAndCollectAllParams){{
    var p=clientParamBuilder.processAndCollectAllParams(window.location.href);
    if(p&&typeof p.then==="function"){{p.then(function(){{_PB_READY=true}}).catch(function(){{}})}}
    else{{_PB_READY=true}}
  }}
}}catch(e){{}}}})();
function pbFBP(){{try{{if(_PB_READY&&typeof clientParamBuilder!=="undefined"){{var v=clientParamBuilder.getFbp();if(v)return v}}}}catch(e){{}};return getFBP()}}
function pbFBC(){{try{{if(_PB_READY&&typeof clientParamBuilder!=="undefined"){{var v=clientParamBuilder.getFbc();if(v)return v}}}}catch(e){{}};return getFBC()}}

// Browser fingerprint (custom, no external library, ~deterministic per device)
// Combines stable signals: canvas hash, WebGL renderer, audio context fingerprint,
// hardware concurrency, device memory, timezone, screen, language, platform.
// Result is a SHA-256 visitor_id used as extra `external_id` on Meta CAPI events.
function _fpCanvas(){{try{{var c=document.createElement("canvas");c.width=200;c.height=50;var x=c.getContext("2d");x.textBaseline="top";x.font="14px Arial";x.fillStyle="#f60";x.fillRect(0,0,100,30);x.fillStyle="#069";x.fillText("AdPhantom_FP_v1",2,2);x.fillStyle="rgba(102,204,0,0.7)";x.fillText("AdPhantom_FP_v1",4,4);return c.toDataURL()}}catch(e){{return""}}}}
function _fpWebGL(){{try{{var c=document.createElement("canvas"),g=c.getContext("webgl")||c.getContext("experimental-webgl");if(!g)return"";var d=g.getExtension("WEBGL_debug_renderer_info");return d?(g.getParameter(d.UNMASKED_VENDOR_WEBGL)+"|"+g.getParameter(d.UNMASKED_RENDERER_WEBGL)):""}}catch(e){{return""}}}}
function _fpAudio(){{try{{var Ac=window.OfflineAudioContext||window.webkitOfflineAudioContext;if(!Ac)return"";var ctx=new Ac(1,5000,44100),osc=ctx.createOscillator();osc.type="triangle";osc.frequency.setValueAtTime(10000,ctx.currentTime);var c=ctx.createDynamicsCompressor();c.threshold.setValueAtTime(-50,ctx.currentTime);osc.connect(c);c.connect(ctx.destination);osc.start(0);return String(ctx.length)+"|"+String(c.threshold.value)}}catch(e){{return""}}}}
function _sha256(s){{if(!window.crypto||!window.crypto.subtle)return Promise.resolve("");var b=new TextEncoder().encode(s);return crypto.subtle.digest("SHA-256",b).then(function(h){{var a=new Uint8Array(h),o="";for(var i=0;i<a.length;i++){{var x=a[i].toString(16);o+=(x.length<2?"0":"")+x}}return o}})}}
function getVisitorId(){{
  var cached=localStorage.getItem("ad_vid");if(cached&&cached.length===64)return Promise.resolve(cached);
  var parts=[
    _fpCanvas(),_fpWebGL(),_fpAudio(),
    navigator.userAgent||"",navigator.language||"",(navigator.languages||[]).join(","),
    navigator.platform||"",String(navigator.hardwareConcurrency||0),
    String(navigator.deviceMemory||0),String(navigator.maxTouchPoints||0),
    screen.width+"x"+screen.height+"x"+screen.colorDepth,
    String(window.devicePixelRatio||1),
    String(new Date().getTimezoneOffset()),
    Intl&&Intl.DateTimeFormat?Intl.DateTimeFormat().resolvedOptions().timeZone:"",
    String((navigator.plugins||{{length:0}}).length),String(navigator.cookieEnabled),
    String(window.indexedDB?1:0),String("ontouchstart" in window?1:0),
  ];
  return _sha256(parts.join("|||")).then(function(h){{
    if(h){{try{{localStorage.setItem("ad_vid",h)}}catch(e){{}}}}
    return h;
  }}).catch(function(){{return""}});
}}

var clickId=localStorage.getItem("ck_"+LANDING_CODE)||gID();
localStorage.setItem("ck_"+LANDING_CODE,clickId);

// Pixel ID injected from server config so we can call fbq('init') again
// with Advanced Matching once the visitor_id (browser fingerprint) is ready.
// Calling fbq('init', PIXEL_ID, {{...}}) multiple times is supported by Meta
// — the latest call updates the matching params for subsequent track calls.
var PIXEL_ID="{pixel_id}";

// Build advanced matching params for the browser Pixel.
// We have NO email/phone client-side (those come later via WhatsApp), but we
// can always send `external_id` (browser fingerprint visitor_id) and the
// derived country code from navigator.language. This satisfies Meta's
// "Configurar las coincidencias avanzadas manuales" diagnostic.
function _buildAdvancedMatching(vid){{
  var am={{}};
  if(vid&&vid.length===64) am.external_id=vid;
  try{{
    var lang=(navigator.language||"").toLowerCase();
    var cc=lang.indexOf("-")>=0?lang.split("-")[1]:(lang||"");
    if(cc&&cc.length===2) am.country=cc;
  }}catch(e){{}}
  // ct/st/zp the Pixel auto-resolves from IP server-side via Meta's geo
  return am;
}}

// Track page view (with Advanced Matching for the browser Pixel + visitor_id
// for our backend so CAPI can match on external_id).
getVisitorId().then(function(vid){{
  // 1. Re-init the Pixel with Advanced Matching so PageView and any later
  //    track call carries external_id (and country if available).
  if(typeof fbq!=="undefined"&&PIXEL_ID){{
    try{{ fbq("init",PIXEL_ID,_buildAdvancedMatching(vid)); }}catch(e){{}}
  }}
  // 2. Now fire PageView (this is the original {pixel_pageview} block that
  //    the admin configured per-landing — typically fbq('track','PageView')).
  if(typeof fbq!=="undefined") {{ {pixel_pageview} }}
  // 3. Track to our backend
  fetch(BASE_URL+"/api/wa-landings/track",{{method:"POST",headers:{{"Content-Type":"application/json"}},
  body:JSON.stringify({{landing_code:LANDING_CODE,click_id:clickId,fbp:pbFBP(),fbc:pbFBC(),
  utm_content:new URLSearchParams(window.location.search).get("utm_content")||"",
  utm_campaign:new URLSearchParams(window.location.search).get("utm_campaign")||"",
  user_agent:navigator.userAgent,referrer:document.referrer,visitor_id:vid||""}})
  }}).catch(function(){{}});
}});

function goWA(){{
var btn=document.getElementById("waBtn");
btn.disabled=true;btn.textContent="CONECTANDO...";
var num=WA_NUMBERS[Math.floor(Math.random()*WA_NUMBERS.length)];
var msg=WA_MSG+" (ID: "+clickId+")";
// Re-init Pixel with Advanced Matching (visitor_id) so the Lead/Contact event
// also satisfies "Coincidencias Avanzadas Manuales".
getVisitorId().then(function(vid){{
  if(typeof fbq!=="undefined"&&PIXEL_ID){{
    try{{ fbq("init",PIXEL_ID,_buildAdvancedMatching(vid)); }}catch(e){{}}
  }}
  // Meta Pixel - Conversion events (Lead, Contact, etc) — original admin code
  if(typeof fbq !== 'undefined') {{ {pixel_wa_click} }}
  // Track WA click (also sends visitor_id so backend updates wa_clicks even if
  // the page-view track was blocked by an adblocker)
  fetch(BASE_URL+"/api/wa-landings/track-wa",{{method:"POST",headers:{{"Content-Type":"application/json"}},
  body:JSON.stringify({{landing_code:LANDING_CODE,click_id:clickId,visitor_id:vid||""}})
  }}).catch(function(){{}});
  // Tiny delay so the Pixel image-beacon flushes BEFORE we navigate away
  setTimeout(function(){{
    window.location.href="https://wa.me/"+num+"?text="+encodeURIComponent(msg);
  }},120);
}}).catch(function(){{
  // Fallback: if fingerprint/visitor_id fails, still go to WhatsApp
  window.location.href="https://wa.me/"+num+"?text="+encodeURIComponent(msg);
}});
}}

// Live counter
setInterval(function(){{var el=document.getElementById("liveCount");if(el){{var v=parseInt(el.innerText);el.innerText=v+Math.floor(Math.random()*5)-2}}}},3500);

// Reviews
var reviews=[
["Increible, retiro en 5 minutos al MP","Carlos P."],
["Excelente atencion y los bonos son reales","Maria G."],
["Llevo 3 meses y nunca tuve problemas para retirar","Diego F."],
["Lo recomiendo 100%, muy serios","Lucia R."],
["El mejor servicio, atencion 24/7","Facundo M."]
];
var rb=document.querySelector(".review-box");
if(rb){{var ri=0;function showReview(){{var r=reviews[ri%reviews.length];rb.querySelector(".review-text").textContent='"'+r[0]+'"';rb.querySelector(".reviewer").textContent="- "+r[1]+" ✓ VERIFICADO";ri++}}showReview();setInterval(showReview,6000)}}

// Toast notifications
var names=["Gaston M.","Julieta R.","Martin F.","Lucia P.","Diego C.","Ana B.","Facundo T.","Sofia G."];
var amounts=["$15.000","$42.500","$8.000","$120.000","$35.000","$60.000","$22.500","$95.000"];
var toast=document.getElementById("toast");
if(toast){{function showToast(){{document.getElementById("toastName").textContent=names[Math.floor(Math.random()*names.length)];document.getElementById("toastAmount").textContent=amounts[Math.floor(Math.random()*amounts.length)];toast.classList.add("show");setTimeout(function(){{toast.classList.remove("show")}},4000)}}setTimeout(function(){{showToast();setInterval(showToast,12000)}},3000)}}
</script></body></html>'''

# Public tracking endpoints (no auth)
@api_router.post("/wa-landings/track")
async def wa_landing_track(request: Request):
    try:
        body = await request.json()
        ip = get_client_ip(request)
        user_agent = body.get("user_agent", "")
        referrer = body.get("referrer", "")
        headers_dict = dict(request.headers)
        
        # Parse device info
        device, os_name, browser = parse_device_info(user_agent)
        
        # Run detection checks (same as campaigns)
        bot_flag = is_bot(user_agent)
        meta_flag = is_meta_crawler(user_agent)
        vpn_flag = detect_vpn(headers_dict)
        is_dc = False
        
        # Generate fingerprint
        fingerprint = generate_fingerprint(ip, user_agent, headers_dict)
        
        # Calculate behavioral score
        score = calculate_behavioral_score(bot_flag, vpn_flag, is_dc, bool(referrer), user_agent)
        
        click_data = {
            "id": str(uuid.uuid4()),
            "landing_code": body.get("landing_code", ""),
            "click_id": body.get("click_id", ""),
            "ip": ip,
            "user_agent": user_agent,
            "fbp": body.get("fbp", ""),
            "fbc": body.get("fbc", ""),
            "utm_content": body.get("utm_content", ""),
            "utm_campaign": body.get("utm_campaign", ""),
            "referrer": referrer,
            "landing_url": body.get("landing_url", ""),
            "wa_clicked": False,
            "device": device,
            "os": os_name,
            "browser": browser,
            "is_bot": bot_flag,
            "is_meta": meta_flag,
            "is_vpn": vpn_flag,
            "is_datacenter": is_dc,
            "fingerprint_hash": fingerprint,
            "visitor_id": (body.get("visitor_id") or "").strip(),
            "behavioral_score": score,
            "country": "XX",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.wa_clicks.insert_one(click_data)
        await db.wa_landings.update_one({"code": body.get("landing_code")}, {"$inc": {"total_clicks": 1}})
    except Exception as e:
        logger.error(f"WA landing track error: {e}")
    return {"status": "ok"}

@api_router.post("/wa-landings/track-wa")
async def wa_landing_track_wa(request: Request):
    """Track WhatsApp button click and send Lead/Contact events via Conversions API"""
    try:
        body = await request.json()
        landing_code = body.get("landing_code")
        click_id = body.get("click_id")
        email = body.get("email", "").strip().lower()
        
        # Update click record — save email and visitor_id if provided
        update_set = {"wa_clicked": True, "wa_clicked_at": datetime.now(timezone.utc).isoformat()}
        if email and "@" in email:
            update_set["email"] = email
        vid_in = (body.get("visitor_id") or "").strip()
        if vid_in:
            update_set["visitor_id"] = vid_in
        await db.wa_clicks.update_one(
            {"landing_code": landing_code, "click_id": click_id},
            {"$set": update_set}
        )
        await db.wa_landings.update_one({"code": landing_code}, {"$inc": {"total_wa_clicks": 1}})
        
        # Get landing to check if Conversions API is configured
        landing = await db.wa_landings.find_one({"code": landing_code}, {"_id": 0})
        if not landing:
            return {"status": "ok"}
        
        # Try to get Meta credentials from landing first, then from associated line
        access_token = landing.get("meta_access_token")
        pixel_id = landing.get("pixel_id")
        
        # If landing doesn't have pixel config, try to get from associated line
        if not access_token or not pixel_id:
            wa_numbers = landing.get("wa_numbers", [])
            if wa_numbers:
                # Find line with this WhatsApp number
                line = await db.crm_lines.find_one(
                    {"whatsapp_number": {"$in": wa_numbers}},
                    {"_id": 0, "meta_access_token": 1, "meta_pixel_id": 1}
                )
                if line:
                    access_token = access_token or line.get("meta_access_token")
                    pixel_id = pixel_id or line.get("meta_pixel_id")
        
        if access_token and pixel_id:
            # Get click data for user info
            click = await db.wa_clicks.find_one(
                {"landing_code": landing_code, "click_id": click_id},
                {"_id": 0}
            )
            if click:
                lead_data = {
                    "id": click.get("id", ""),
                    "ip_address": click.get("ip", ""),
                    "user_agent": click.get("user_agent", ""),
                    "fbp": click.get("fbp", ""),
                    "fbc": click.get("fbc", ""),
                    "phone": "",  # No phone at this stage
                    "click_id": click_id,
                }
                custom_data = {"content_name": landing.get("name", "WA Landing")}
                
                # Get pixel_events from landing to know which events to send
                pixel_events = landing.get("pixel_events", ["PageView", "Lead"])

                # Deterministic event_ids per click so we can re-fire them
                # later (post-WhatsApp) with enriched user_data. Meta
                # deduplicates by (event_name, event_id) within 48h and keeps
                # the one with the best match quality.
                import time as _time_mod
                base_ts = int(_time_mod.time())
                fired_event_ids: dict = {}

                # Send Lead event via Conversions API
                if "Lead" in pixel_events:
                    eid = f"Lead_{click_id or click.get('id','')}_{base_ts}"
                    await send_meta_conversion_event(
                        event_name="Lead",
                        lead_data=lead_data,
                        custom_data=custom_data,
                        access_token=access_token,
                        pixel_id=pixel_id,
                        event_id=eid,
                    )
                    fired_event_ids["Lead"] = eid
                    logger.info(f"Lead event sent via Conversions API for landing {landing_code} (event_id={eid})")

                # Send Contact event via Conversions API
                if "Contact" in pixel_events:
                    eid = f"Contact_{click_id or click.get('id','')}_{base_ts}"
                    await send_meta_conversion_event(
                        event_name="Contact",
                        lead_data=lead_data,
                        custom_data=custom_data,
                        access_token=access_token,
                        pixel_id=pixel_id,
                        event_id=eid,
                    )
                    fired_event_ids["Contact"] = eid
                    logger.info(f"Contact event sent via Conversions API for landing {landing_code} (event_id={eid})")

                # Send InitiateCheckout event via Conversions API
                if "InitiateCheckout" in pixel_events:
                    eid = f"InitiateCheckout_{click_id or click.get('id','')}_{base_ts}"
                    await send_meta_conversion_event(
                        event_name="InitiateCheckout",
                        lead_data=lead_data,
                        custom_data=custom_data,
                        access_token=access_token,
                        pixel_id=pixel_id,
                        event_id=eid,
                    )
                    fired_event_ids["InitiateCheckout"] = eid
                    logger.info(f"InitiateCheckout event sent via Conversions API for landing {landing_code} (event_id={eid})")

                # Persist event_ids on the click doc so we can re-fire them
                # once the lead actually writes to WhatsApp (see auto_welcome
                # webhook path where we call resend_enriched_landing_events).
                if fired_event_ids:
                    await db.wa_clicks.update_one(
                        {"click_id": click_id} if click_id else {"id": click.get("id")},
                        {"$set": {
                            "landing_event_ids": fired_event_ids,
                            "landing_events_fired_at": datetime.now(timezone.utc).isoformat(),
                            "meta_access_token_snapshot": access_token,
                            "meta_pixel_id_snapshot": pixel_id,
                        }}
                    )
        else:
            logger.warning(f"Landing {landing_code} has no Meta Pixel configured (neither in landing nor in associated line)")
    except Exception as e:
        logger.error(f"WA landing track-wa error: {e}")
    return {"status": "ok"}

# Routes fixed for proper order

# ═══════════════════════════════════════════════════════════════════════════════
# CRM MODULE - Sistema de Gestión de Leads con Clasificación Manual
# ═══════════════════════════════════════════════════════════════════════════════

# CRM Lead Status Constants - Simplified to 3 options
CRM_LEAD_STATUSES = ["nuevo", "spam", "consultas", "valido"]

# Line Types
CRM_LINE_TYPES = ["publi", "principal", "spam"]

# Meta Conversions API Config (default, can be overridden per line)
META_ACCESS_TOKEN = os.environ.get('META_ACCESS_TOKEN', '')
META_PIXEL_ID = os.environ.get('META_PIXEL_ID', '')

# ─── CRM Lines Pydantic Models ─────────────────────────────────────

class CRMLineCreate(BaseModel):
    name: str
    line_type: str = "publi"  # publi, principal, spam
    whatsapp_number: str
    # WhatsApp Business API Config
    whatsapp_token: Optional[str] = ""
    phone_number_id: Optional[str] = ""
    whatsapp_business_account_id: Optional[str] = ""  # WABA id — required for fetching templates
    verify_token: Optional[str] = ""
    # Multi-line webhook sharing: if set, this line copies whatsapp_token,
    # verify_token and whatsapp_business_account_id from the parent line, so
    # several phone numbers under the same Meta App share one verified webhook.
    webhook_parent_line_id: Optional[str] = None
    # Meta Pixel Config
    meta_access_token: Optional[str] = ""
    meta_pixel_id: Optional[str] = ""
    description: Optional[str] = ""
    is_active: bool = True

class CRMLineUpdate(BaseModel):
    name: Optional[str] = None
    line_type: Optional[str] = None
    whatsapp_number: Optional[str] = None
    whatsapp_token: Optional[str] = None
    phone_number_id: Optional[str] = None
    whatsapp_business_account_id: Optional[str] = None
    verify_token: Optional[str] = None
    webhook_parent_line_id: Optional[str] = None
    meta_access_token: Optional[str] = None
    meta_pixel_id: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

# ─── CRM Pydantic Models ───────────────────────────────────────────

class CRMLeadCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: str
    source: str = "manual"
    line_id: Optional[str] = None  # ID de la línea asignada
    notes: Optional[str] = ""
    tags: List[str] = []
    metadata: Dict = {}

class CRMLeadUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    score: Optional[int] = None
    line_id: Optional[str] = None  # Cambiar línea asignada
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    charge_amount: Optional[float] = None  # Monto de carga
    # Meta matching fields
    city: Optional[str] = None       # ct - ciudad
    state: Optional[str] = None      # st - provincia/estado
    zip_code: Optional[str] = None   # zp - código postal
    gender: Optional[str] = None     # ge - 'm' o 'f'
    dob: Optional[str] = None        # db - fecha nacimiento YYYYMMDD
    fb_login_id: Optional[str] = None  # Facebook Login ID

class CRMMessageCreate(BaseModel):
    content: str
    sender: str = "admin"  # "admin" or "lead"

class CRMReceiptValidation(BaseModel):
    status: str  # "approved" or "rejected"
    amount: Optional[float] = None
    currency: Optional[str] = "USD"
    admin_notes: Optional[str] = ""

class CRMLeadClassify(BaseModel):
    status: str  # basura, curioso, interesado, potencial, cliente_real
    send_to_meta: bool = True
    conversion_value: Optional[float] = None
    currency: Optional[str] = "USD"

# ─── Meta Conversions API Helper ───────────────────────────────────

# ── Auto-resolve geo data from IP ───────────────────────────────────

_geo_cache = {}  # Simple in-memory cache for IP geo lookups

async def resolve_geo_from_ip(ip: str) -> dict:
    """Resolve city, state, zip, country from IP using ip-api.com (free, no key needed).
    Persistent cache lives in `geo_cache` collection so each IP is resolved once
    in its lifetime even across server restarts.
    """
    if not ip or ip in ("0.0.0.0", "unknown", "127.0.0.1", "::1"):
        return {}
    # Memory cache (per-process hot path)
    if ip in _geo_cache:
        return _geo_cache[ip]
    # Persistent cache in Mongo
    try:
        cached = await db.geo_cache.find_one({"_id": ip}, {"_id": 0, "data": 1})
        if cached and cached.get("data") is not None:
            _geo_cache[ip] = cached["data"]
            return cached["data"]
    except Exception as e:
        logger.debug(f"geo_cache mongo read failed for {ip}: {e}")
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,region,regionName,city,zip")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    result = {
                        "city": data.get("city", ""),
                        "state": data.get("regionName", ""),
                        "state_code": data.get("region", ""),
                        "zip": data.get("zip", ""),
                        "country_code": data.get("countryCode", "").lower(),
                    }
                    _geo_cache[ip] = result
                    # Persist forever (IP-to-geo mappings are extremely stable;
                    # if the user moves we'll just re-resolve a different IP).
                    try:
                        await db.geo_cache.update_one(
                            {"_id": ip},
                            {"$set": {"data": result, "cached_at": datetime.now(timezone.utc).isoformat()}},
                            upsert=True,
                        )
                    except Exception as e:
                        logger.debug(f"geo_cache mongo write failed for {ip}: {e}")
                    return result
    except Exception as e:
        logger.debug(f"Geo resolve failed for {ip}: {e}")
    return {}

# ── Auto-extract email from chat messages ───────────────────────────

async def extract_email_from_messages(lead_id: str) -> Optional[str]:
    """Scan lead's chat messages for email patterns"""
    messages = await db.crm_messages.find(
        {"lead_id": lead_id, "sender": "lead"},
        {"_id": 0, "content": 1}
    ).sort("created_at", -1).limit(50).to_list(50)
    
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            match = email_pattern.search(content)
            if match:
                return match.group(0).lower().strip()
    return None


async def extract_full_name_from_messages(lead_id: str) -> Optional[str]:
    """
    Scan the lead's own messages for full-name patterns so we can improve
    first_name + last_name coverage when WhatsApp only gave us a single word.
    Returns "Firstname Lastname" (Title-Cased) or None.
    """
    messages = await db.crm_messages.find(
        {"lead_id": lead_id, "sender": "lead"},
        {"_id": 0, "content": 1}
    ).sort("created_at", 1).limit(30).to_list(30)

    # Patterns that strongly indicate self-identification
    patterns = [
        r'(?:soy|me\s+llamo|mi\s+nombre\s+es|mi\s+nombre)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})',
        r'(?:saludos|atte\.?|atentamente)[\s,]+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})',
    ]
    blacklist = {
        'buenas','buenos','tardes','noches','hola','chau','gracias','muchas','quiero',
        'necesito','puedo','podria','podrias','quisiera','busco','pido','como','estas',
        'para','sobre','dias','tarde','tengo','soy','llamo','nombre','cliente','cuenta',
        'datos','clave','usuario','carga','retirar','depositar','jugar','info','ayuda',
    }
    for msg in messages:
        content = msg.get("content", "")
        if not isinstance(content, str) or len(content) > 500:
            continue
        for pat in patterns:
            m = re.search(pat, content)
            if m:
                fn = m.group(1).lower()
                ln = m.group(2).lower()
                if fn in blacklist or ln in blacklist:
                    continue
                return f"{m.group(1).title()} {m.group(2).title()}"
    return None


# ── Auto-infer gender from first name (Spanish common names) ────────

_MALE_NAMES = {
    'juan','carlos','jose','luis','jorge','pedro','miguel','angel','rafael','francisco',
    'daniel','mario','david','fernando','ricardo','eduardo','pablo','andres','sergio',
    'diego','alejandro','roberto','gabriel','nicolas','martin','santiago','gonzalo',
    'matias','marcos','lucas','tomas','agustin','leandro','mauro','ariel','fabian',
    'ramon','hector','alberto','oscar','hugo','gustavo','nestor','marcelo','claudio',
    'maximiliano','maxi','lautaro','enzo','thiago','valentino','bruno','leonardo',
    'sebastian','cristian','ezequiel','raul','emiliano','facundo','ignacio','nacho',
    'ivan','damian','hernan','julio','alan','kevin','brian','axel','abel',
    'franco','joaquin','federico','rodrigo','bautista','santino','benicio','ciro',
    'benjamin','tobias','gael','dylan','nahuel','braian','jonathan','walter',
    'ruben','omar','alfredo','victor','cesar','rolando','gerardo','dario',
    # Extended LATAM
    'adrian','agustin','alex','alexis','alfonso','amilcar','andy','anibal','antonio',
    'armando','arnoldo','arturo','augusto','aurelio','baltazar','basilio','bernardo',
    'camilo','carmelo','cayetano','cipriano','cirilo','constantino','cornelio','cosme',
    'cruz','danilo','demian','domingo','donato','efrain','eleuterio','eliseo',
    'emanuel','emilio','enrique','erasmo','erick','erik','ernesto','esteban','eugenio',
    'eusebio','evaristo','exequiel','fausto','felipe','felix','ferdinando','fidel',
    'filemon','fortunato','gaston','genaro','german','gilberto','ginés','godofredo',
    'guillermo','gumersindo','hilario','horacio','humberto','ian','isaac','isaias',
    'isidro','ismael','israel','jair','jairo','javier','jeronimo','jesus','joan',
    'joel','jonatan','josue','juanpa','juanpablo','julian','justo','leopoldo',
    'liam','lionel','lisandro','lorenzo','luciano','luka','manuel','marcelino','mariano',
    'marino','mateo','mauricio','maximo','maxi','mayco','mercedes','modesto','moises',
    'nehuen','nehuén','octavio','olegario','ovidio','pascual','patricio','pio','placido',
    'porfirio','prudencio','reinaldo','remigio','renzo','reynaldo','ricardo','roman',
    'rosendo','rufino','rufo','salustiano','salvador','samuel','saul','severiano',
    'sigfrido','silvano','silvio','simon','tadeo','teofilo','teobaldo','tito','ulises',
    'urbano','valentin','valerio','vicente','vidal','vinicio','virgilio','wilfredo',
    'wilmer','yago','zacarias',
}
_FEMALE_NAMES = {
    'maria','ana','laura','carolina','patricia','andrea','gabriela','claudia','silvia',
    'monica','cecilia','florencia','valeria','fernanda','daniela','paula','lucia',
    'romina','natalia','vanesa','vanessa','lorena','marina','soledad','julieta',
    'camila','micaela','agustina','victoria','sol','rocio','milagros','pilar',
    'sofia','martina','catalina','virginia','mariana','paola','julia','marta',
    'susana','rosa','elena','alejandra','liliana','graciela','norma','alicia',
    'beatriz','miriam','carmen','celeste','morena','luz','brenda','carina',
    'valentina','abril','candela','delfina','renata','emilia','alma','bianca',
    'lara','mia','isabella','josefina','guadalupe','priscila','melina','tamara',
    'silvana','viviana','noelia','gisela','yanina','karen','jessica','daiana',
    'yamila','ludmila','oriana','jazmín','jazmin','mailen','ailén','ailen',
    # Extended LATAM
    'adela','adriana','agata','aida','alba','alondra','amalia','amanda','amparo',
    'antonella','antonia','araceli','aurora','azucena','barbara','belen','belinda',
    'benita','bernarda','betina','betty','blanca','brisa','camila','cami','carla',
    'carmela','celia','celina','celine','chiara','clara','clarisa','cleo',
    'constanza','coni','consuelo','cora','cristina','debora','denise','diana',
    'dolores','doris','dulce','edith','elba','elisa','elsa','elvira','emma',
    'estefania','estela','esther','eva','evelina','evelyn','fabiana','felicia',
    'filomena','flora','francisca','genoveva','georgina','geraldine','gianna',
    'gimena','gladys','gloria','griselda','haydee','hilda','indiana','ines',
    'ingrid','iris','isabel','ivana','jacqueline','jamila','janet','jimena',
    'joana','joanna','jordana','juana','justina','lali','leila','leticia',
    'ligia','lila','lilian','linda','lola','lorena','lourdes','luciana','lucila',
    'luisa','luisina','luna','macarena','maite','malena','mar','mara','marcela',
    'margarita','mariela','marilyn','marisa','maritza','maru','melisa','mercedes',
    'mia','mila','milena','mili','mirta','nadia','nahia','nancy','naomi',
    'nayeli','nerea','nerina','nidia','nina','noemi','nora','odalis','ofelia',
    'olga','olivia','ornella','paloma','paloma','pamela','patricia','paulina',
    'perla','petra','ramona','raquel','regina','rina','rita','rosario','sabrina',
    'salome','samanta','samara','sandra','sara','sarah','selena','serena','sheila',
    'solana','stefania','stella','teresa','trinidad','ursula','valery','vera',
    'veronica','virginia','wanda','xiomara','yael','yamila','yolanda','zaira','zulma',
}

def infer_gender_from_name(name: str) -> Optional[str]:
    """Try to infer gender from first name using common Argentine/Spanish names"""
    if not name or name.startswith("Lead "):
        return None
    first_name = name.strip().split()[0].lower()
    # Remove accents for matching
    import unicodedata
    first_name = ''.join(
        c for c in unicodedata.normalize('NFD', first_name) if unicodedata.category(c) != 'Mn'
    )
    if first_name in _MALE_NAMES:
        return 'm'
    if first_name in _FEMALE_NAMES:
        return 'f'
    return None

async def send_meta_conversion_event(
    event_name: str,
    lead_data: dict,
    custom_data: dict = None,
    access_token: str = None,
    pixel_id: str = None,
    event_id: str = None,
):
    """
    Send conversion event to Meta Conversions API
    
    Events:
    - Purchase: Cliente válido (conversión positiva) — requires value + currency in custom_data
    - Lead: Lead interesado
    - Contact: Contacto inicial
    - Other: Eventos custom
    
    Uses line-specific token/pixel only (no env fallbacks).

    `event_id`: optional. When provided, Meta will deduplicate against any
    previous event with the same (event_name, event_id) within 48h and keep
    the one with the highest match quality. This is how we "re-fire" a
    landing event post-WhatsApp with enriched user_data.
    """
    token = access_token
    pixel = pixel_id
    
    if not token or not pixel:
        logger.warning("Meta Conversions API not configured (missing TOKEN or PIXEL_ID)")
        return {"success": False, "error": "Meta API not configured"}
    
    try:
        import time
        import hashlib
        
        url = f"https://graph.facebook.com/v21.0/{pixel}/events"
        
        # Try to get click data for better matching
        click_data = {}
        if lead_data.get("click_id"):
            wa_click = await db.wa_clicks.find_one({"click_id": lead_data["click_id"]}, {"_id": 0})
            if wa_click:
                click_data = wa_click
        
        # If no click_id, try to find by phone
        if not click_data and lead_data.get("phone"):
            phone_clean = re.sub(r'\D', '', lead_data["phone"])[-10:]
            wa_click = await db.wa_clicks.find_one(
                {"phone": {"$regex": phone_clean}},
                {"_id": 0},
                sort=[("created_at", -1)]
            )
            if wa_click:
                click_data = wa_click
        
        # Fallback: try wa_contacts which also stores click/fingerprint data
        if not click_data and lead_data.get("phone"):
            phone_clean = re.sub(r'\D', '', lead_data["phone"])[-10:]
            wa_contact = await db.wa_contacts.find_one(
                {"phone": {"$regex": phone_clean}},
                {"_id": 0},
                sort=[("created_at", -1)]
            )
            if wa_contact:
                # wa_contacts may have click_ip, fbp, fbc from fingerprint tracking
                click_data = {
                    "ip": wa_contact.get("click_ip") or wa_contact.get("ip"),
                    "user_agent": wa_contact.get("user_agent", ""),
                    "fbp": wa_contact.get("fbp", ""),
                    "fbc": wa_contact.get("fbc", ""),
                    "landing_code": wa_contact.get("landing_code", ""),
                }

        # ── Cross-session signal recovery ──────────────────────────
        # If the current click_data is missing IP/UA/fbp/fbc/visitor_id, try
        # to pull them from the LATEST wa_clicks doc that ever matched this
        # phone OR this visitor_id. This rescues leads that arrive directly
        # via WhatsApp (no landing visit in this session) but visited a
        # landing of ours in the past.
        try:
            current_vid = click_data.get("visitor_id") or lead_data.get("visitor_id")
            phone_for_lookup = re.sub(r'\D', '', lead_data.get("phone") or "")[-10:]
            needs = (
                not click_data.get("ip")
                or not click_data.get("user_agent")
                or not click_data.get("fbp")
                or not click_data.get("fbc")
                or not current_vid
            )
            if needs and (phone_for_lookup or current_vid):
                or_clauses = []
                if phone_for_lookup:
                    or_clauses.append({"phone": {"$regex": phone_for_lookup}})
                if current_vid:
                    or_clauses.append({"visitor_id": current_vid})
                latest = await db.wa_clicks.find_one(
                    {"$or": or_clauses} if or_clauses else {"_id": None},
                    {"_id": 0},
                    sort=[("created_at", -1)]
                )
                if latest:
                    for k in ("ip", "user_agent", "fbp", "fbc", "visitor_id", "fingerprint_hash"):
                        if not click_data.get(k) and latest.get(k):
                            click_data[k] = latest[k]
                    logger.info(
                        f"Meta CAPI: cross-session signals recovered for lead {lead_data.get('id')} "
                        f"(phone tail={phone_for_lookup or '-'}, vid={'yes' if current_vid else 'no'})"
                    )
        except Exception as _e:
            logger.debug(f"cross-session signal recovery failed: {_e}")
        
        # Build user data with all available info
        user_data = {}
        
        # IP and User Agent (required for good matching)
        ip = click_data.get("ip") or click_data.get("ip_address") or lead_data.get("ip_address") or lead_data.get("metadata", {}).get("ip_address", "")
        ua = click_data.get("user_agent") or lead_data.get("user_agent") or lead_data.get("metadata", {}).get("user_agent", "")
        
        if ip:
            user_data["client_ip_address"] = normalize_ip_for_meta(ip)
        if ua:
            user_data["client_user_agent"] = ua
        
        # Facebook cookies (critical for matching)
        fbp = click_data.get("fbp") or lead_data.get("fbp")
        fbc = click_data.get("fbc") or lead_data.get("fbc")

        # NOTE: We deliberately DO NOT synthesize fbc from ctwa_clid.
        # ctwa_clid is a Click-to-WhatsApp click identifier, NOT a fbclid —
        # they have different formats. Building "fb.1.{ts}.{ctwa_clid}"
        # produces a value Meta detects as "modified fbclid" (warning in
        # Events Manager: 'El servidor está enviando un valor fbclid
        # modificado en el parámetro fbc'). Sending NO fbc is better than
        # sending a fake one — Meta correlates ctwa_clid attribution
        # internally via the WhatsApp webhook, so we don't lose anything.
        ctwa_clid = lead_data.get("ctwa_clid") or click_data.get("ctwa_clid")

        # Validate fbc format if we have one — must look like "fb.<n>.<ts>.<fbclid>"
        # If it's malformed (e.g. someone stored just the raw fbclid),
        # drop it so Meta doesn't reject the event.
        if fbc and not (isinstance(fbc, str) and fbc.startswith("fb.") and fbc.count(".") >= 3):
            logger.warning(f"Meta CAPI: dropping malformed fbc '{fbc[:50]}' for lead {lead_data.get('id')}")
            fbc = None

        # Pass fbc/fbp through Meta Parameter Builder to add the server-side
        # appendix (+~0.7 EMQ points, removes "modified fbclid" warning).
        # See https://github.com/facebook/capi-param-builder
        fbc, fbp = _meta_param_builder_process(fbc, fbp, lead_data.get("event_source_url"))

        if fbp:
            user_data["fbp"] = fbp
        if fbc:
            user_data["fbc"] = fbc
        
        # Phone (required - hash it, normalized to E.164 for Argentina)
        phone = lead_data.get("phone")
        if phone:
            phone_clean = re.sub(r'\D', '', phone)
            # Normalize to E.164: Argentine numbers must start with 54
            if phone_clean and not phone_clean.startswith("54"):
                phone_clean = "54" + phone_clean
            user_data["ph"] = [hashlib.sha256(phone_clean.encode()).hexdigest()]
        
        # First name / Last name (improves EMQ score)
        name = lead_data.get("name", "")
        # If we only have a first name, try to extract full name from chat messages
        if name and lead_data.get("id"):
            parts_check = name.strip().split()
            if len(parts_check) == 1 and not name.startswith("Lead "):
                full_name = await extract_full_name_from_messages(lead_data["id"])
                if full_name:
                    name = full_name
                    # Persist so future events also get it
                    await db.crm_leads.update_one(
                        {"id": lead_data["id"]},
                        {"$set": {"name": full_name, "name_enriched": True}}
                    )
                    logger.info(f"Meta CAPI: Enriched name '{lead_data.get('name')}' -> '{full_name}' for lead {lead_data.get('id')}")
        if name and name.strip() and not name.startswith("Lead "):
            parts = name.strip().split()
            fn = parts[0].lower()
            ln = parts[-1].lower() if len(parts) > 1 else ""
            user_data["fn"] = [hashlib.sha256(fn.encode()).hexdigest()]
            if ln:
                user_data["ln"] = [hashlib.sha256(ln.encode()).hexdigest()]
        
        # Email — from lead, from click data, or auto-extract from chat as last resort
        email = lead_data.get("email") or click_data.get("email")
        if not email and lead_data.get("id"):
            email = await extract_email_from_messages(lead_data["id"])
        if email:
            if lead_data.get("id") and not lead_data.get("email"):
                await db.crm_leads.update_one({"id": lead_data["id"]}, {"$set": {"email": email}})
                logger.info(f"Meta CAPI: Email '{email}' resolved for lead {lead_data.get('id')}")
            user_data["em"] = [hashlib.sha256(email.lower().strip().encode()).hexdigest()]
        
        # External ID — deterministic hash of the normalized phone number.
        # Meta prefers stable identifiers shared across events (same user across
        # multiple interactions = same external_id). Using the phone hash instead
        # of a random UUID dramatically improves EMQ and reduces "synthetic
        # automation" score from Meta Integrity.
        # We also append the browser visitor_id (captured client-side via custom
        # fingerprint on landing pages) as an additional external_id so Meta has
        # *two* stable signals to match on. visitor_id is already a SHA-256 of
        # device features, so we send it as-is (no double-hash).
        ext_ids = []
        phone_for_ext = (lead_data.get("phone") or "").strip()
        # Keep only digits so "+54911..." and "54911..." produce the same hash
        phone_digits_ext = "".join(c for c in phone_for_ext if c.isdigit())
        if phone_digits_ext:
            ext_ids.append(hashlib.sha256(phone_digits_ext.encode()).hexdigest())
        elif lead_data.get("id"):
            # Last-resort fallback (e.g. lead without phone — shouldn't happen)
            ext_ids.append(hashlib.sha256(lead_data["id"].encode()).hexdigest())

        # Browser fingerprint visitor_id — already SHA-256, append if present
        vid_ext = (click_data.get("visitor_id") or lead_data.get("visitor_id") or "").strip()
        if vid_ext and len(vid_ext) == 64 and all(c in "0123456789abcdef" for c in vid_ext):
            if vid_ext not in ext_ids:
                ext_ids.append(vid_ext)

        if ext_ids:
            user_data["external_id"] = ext_ids
        
        # ── AUTO-RESOLVE GEO DATA FROM IP (city, state, zip, country) ──
        # This runs automatically so cajeros don't need to fill anything
        geo_data = {}
        if ip:
            geo_data = await resolve_geo_from_ip(ip)
        
        # Country — use geo-resolved or fallback to "ar" (Argentina)
        country_code = lead_data.get("country_code") or geo_data.get("country_code") or "ar"
        user_data["country"] = [hashlib.sha256(country_code.lower().encode()).hexdigest()]
        
        # fb_login_id — NOT hashed, sent as-is
        fb_login_id = lead_data.get("fb_login_id") or click_data.get("fb_login_id")
        if fb_login_id:
            user_data["fb_login_id"] = fb_login_id
        
        # City (ct) — from lead, or auto-resolved from IP
        city = lead_data.get("city") or geo_data.get("city")
        if city:
            user_data["ct"] = [hashlib.sha256(city.lower().strip().encode()).hexdigest()]
        
        # State (st) — from lead, or auto-resolved from IP
        state = lead_data.get("state") or geo_data.get("state")
        if state:
            user_data["st"] = [hashlib.sha256(state.lower().strip().encode()).hexdigest()]
        
        # Zip code (zp) — from lead, or auto-resolved from IP
        zip_code = lead_data.get("zip_code") or geo_data.get("zip")
        if zip_code:
            user_data["zp"] = [hashlib.sha256(str(zip_code).strip().encode()).hexdigest()]
        
        # Gender (ge) — from lead, or auto-inferred from name
        gender = lead_data.get("gender")
        if not gender:
            gender = infer_gender_from_name(lead_data.get("name", ""))
        if gender and gender.lower() in ('m', 'f', 'male', 'female'):
            ge = 'm' if gender.lower() in ('m', 'male') else 'f'
            user_data["ge"] = [hashlib.sha256(ge.encode()).hexdigest()]
        
        # Date of birth (db) — from lead only (can't auto-detect)
        dob = lead_data.get("dob")
        if dob:
            dob_clean = str(dob).replace("-", "").strip()
            if len(dob_clean) == 8 and dob_clean.isdigit():
                user_data["db"] = [hashlib.sha256(dob_clean.encode()).hexdigest()]
        
        # Persist auto-resolved data on the lead for future events
        if lead_data.get("id"):
            auto_update = {}
            if city and not lead_data.get("city"):
                auto_update["city"] = city
            if state and not lead_data.get("state"):
                auto_update["state"] = state
            if zip_code and not lead_data.get("zip_code"):
                auto_update["zip_code"] = str(zip_code)
            if gender and not lead_data.get("gender"):
                auto_update["gender"] = gender
            if auto_update:
                await db.crm_leads.update_one({"id": lead_data["id"]}, {"$set": auto_update})
                logger.info(f"Meta CAPI: Auto-resolved for lead {lead_data.get('id')}: {list(auto_update.keys())}")
        
        # Generate unique event_id for deduplication.
        # Callers can pass their own to force dedup with a prior event (e.g.
        # re-firing a landing event with enriched user_data post-WhatsApp).
        if not event_id:
            event_id = f"{event_name}_{lead_data.get('id', 'unknown')}_{int(time.time())}"

        # Resolve event_source_url BEFORE building event_data (needed for action_source)
        source_url = click_data.get("landing_url") or click_data.get("referrer")
        if not source_url and click_data.get("landing_code"):
            landing = await db.wa_landings.find_one({"code": click_data["landing_code"]}, {"_id": 0, "code": 1})
            if landing:
                app_url = os.environ.get("APP_URL", "")
                if app_url:
                    source_url = f"{app_url}/l/{landing['code']}"
        if not source_url and lead_data.get("landing_code"):
            app_url = os.environ.get("APP_URL", "")
            if app_url:
                source_url = f"{app_url}/l/{lead_data['landing_code']}"

        event_data = {
            "event_name": event_name,
            "event_time": int(time.time()),
            "event_id": event_id,
            # If we have a landing URL it's a website action; otherwise it's a WhatsApp/CRM event
            "action_source": "website" if source_url else "other",
            "user_data": user_data,
        }

        if source_url:
            event_data["event_source_url"] = source_url
        
        # Handle custom_data — ensure Purchase events have proper value/currency
        if custom_data:
            # For Purchase events, ensure value is a proper float number
            if event_name == "Purchase":
                raw_value = custom_data.get("value", 0)
                custom_data["value"] = float(raw_value) if raw_value else 0.0
                # FORCE currency to the deployment-wide PURCHASE_CURRENCY
                # (env var). This guarantees no stale frontend cache or
                # external webhook can send Purchase with the wrong currency.
                incoming_currency = custom_data.get("currency")
                if incoming_currency and incoming_currency != PURCHASE_CURRENCY:
                    logger.warning(
                        f"Meta CAPI >> Overriding Purchase currency '{incoming_currency}' -> '{PURCHASE_CURRENCY}' "
                        f"| lead={lead_data.get('id', '?')}"
                    )
                custom_data["currency"] = PURCHASE_CURRENCY
                # Add content_type for better optimization
                if "content_type" not in custom_data:
                    custom_data["content_type"] = "product"
                # ── Enriched Purchase metadata for better matching / dedupe ──
                # order_id: stable per-lead per-day identifier so the same
                # Purchase isn't double-counted if we re-fire. Format:
                # "<lead_id>-<YYYYMMDD>". Meta also uses order_id for dedupe
                # alongside event_id, which improves attribution.
                if "order_id" not in custom_data and lead_data.get("id"):
                    today = datetime.now(timezone.utc).strftime("%Y%m%d")
                    custom_data["order_id"] = f"{lead_data['id']}-{today}"
                # content_ids / content_name from line metadata so Meta can
                # attribute the conversion to the right product/campaign.
                if "content_ids" not in custom_data:
                    line_id = lead_data.get("line_id")
                    if line_id:
                        custom_data["content_ids"] = [str(line_id)]
                        if "content_name" not in custom_data:
                            try:
                                line_doc = await db.crm_lines.find_one(
                                    {"id": line_id},
                                    {"_id": 0, "name": 1, "whatsapp_number": 1}
                                )
                                if line_doc and line_doc.get("name"):
                                    custom_data["content_name"] = line_doc["name"]
                            except Exception:
                                pass
                if "content_category" not in custom_data:
                    custom_data["content_category"] = "credits"
                if "num_items" not in custom_data:
                    custom_data["num_items"] = 1
                if "delivery_category" not in custom_data:
                    # "home_delivery" is the closest standard value Meta
                    # accepts for digital credits delivered to the user.
                    custom_data["delivery_category"] = "home_delivery"
            event_data["custom_data"] = custom_data
        elif event_name == "Purchase":
            # Purchase MUST have custom_data with value/currency
            today = datetime.now(timezone.utc).strftime("%Y%m%d")
            cd = {
                "value": 0.0,
                "currency": PURCHASE_CURRENCY,
                "content_type": "product",
                "content_category": "credits",
                "num_items": 1,
                "delivery_category": "home_delivery",
            }
            if lead_data.get("id"):
                cd["order_id"] = f"{lead_data['id']}-{today}"
            if lead_data.get("line_id"):
                cd["content_ids"] = [str(lead_data["line_id"])]
            event_data["custom_data"] = cd
        
        payload = {
            "data": [event_data],
            "access_token": token,
        }
        
        # Detailed logging for debugging
        log_custom = event_data.get("custom_data", {})
        logger.info(
            f"Meta CAPI >> Sending '{event_name}' | lead={lead_data.get('id', '?')} | "
            f"value={log_custom.get('value', 'N/A')} {log_custom.get('currency', '')} | "
            f"event_id={event_id} | pixel={pixel[:10]}... | "
            f"user_data_keys={list(user_data.keys())} | "
            f"fbp={'YES' if fbp else 'NO'} fbc={'YES' if fbc else 'NO'} phone={'YES' if phone else 'NO'}"
        )
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            result = response.json()
            
            success = response.status_code == 200
            if success:
                logger.info(f"Meta CAPI << '{event_name}' OK | lead={lead_data.get('id', 'unknown')} | response={result}")
            else:
                logger.error(f"Meta CAPI << '{event_name}' ERROR {response.status_code} | response={result}")
            
            # Centralized event log — every CAPI event gets recorded
            try:
                await db.meta_events_log.insert_one({
                    "event_name": event_name,
                    "event_id": event_id,
                    "event_time": event_data["event_time"],
                    "lead_id": lead_data.get("id"),
                    "lead_name": lead_data.get("name"),
                    "lead_phone": lead_data.get("phone"),
                    "line_id": lead_data.get("line_id"),
                    "pixel_id": pixel[:12] + "..." if pixel else None,
                    "value": log_custom.get("value"),
                    "currency": log_custom.get("currency"),
                    "success": success,
                    "has_fbp": bool(fbp),
                    "has_fbc": bool(fbc),
                    "has_phone": bool(phone),
                    "has_email": bool(email),
                    "has_fb_login_id": bool(fb_login_id),
                    "matching_params_count": len(user_data),
                    "user_data_keys": list(user_data.keys()),
                    "source": lead_data.get("source", ""),
                    "landing_code": lead_data.get("landing_code") or click_data.get("landing_code"),
                    "ctwa_clid": lead_data.get("ctwa_clid") or click_data.get("ctwa_clid"),
                    "ad_source": lead_data.get("ad_source"),
                    "utm_content": lead_data.get("utm_content") or click_data.get("utm_content"),
                    "meta_response": result if not success else {"events_received": result.get("events_received")},
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as log_err:
                logger.warning(f"Failed to log CAPI event: {log_err}")
            
            return {"success": success, "result": result, "event_id": event_id} if success else {"success": False, "error": result, "event_id": event_id}
                
    except Exception as e:
        logger.error(f"Meta Conversions API error: {e}")
        return {"success": False, "error": str(e)}

# ─── CRM Lines Routes ──────────────────────────────────────────────

@api_router.get("/crm/lines")
async def crm_get_all_lines(current_user=Depends(get_current_user)):
    """Get all WhatsApp lines"""
    lines = await db.crm_lines.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    # Add stats for each line
    for line in lines:
        line["leads_count"] = await db.crm_leads.count_documents({"line_id": line["id"]})
        line["cargas_count"] = await db.crm_leads.count_documents({
            "line_id": line["id"], 
            "status": "cliente_real"
        })
    
    return lines

@api_router.post("/crm/lines")
async def crm_create_line(data: CRMLineCreate, current_user=Depends(get_current_user)):
    if data.line_type not in CRM_LINE_TYPES:
        raise HTTPException(status_code=400, detail=f"Tipo de línea inválido. Opciones: {CRM_LINE_TYPES}")
    
    now = datetime.now(timezone.utc).isoformat()

    # Pull tokens from parent line if webhook is shared (multi-line Meta App)
    parent_id = data.webhook_parent_line_id
    parent_line = None
    if parent_id:
        parent_line = await db.crm_lines.find_one({"id": parent_id}, {"_id": 0})
        if not parent_line:
            raise HTTPException(status_code=400, detail="webhook_parent_line_id no existe")

    if parent_line:
        # Inherit verify_token + WhatsApp token from parent (App-level secrets).
        # WABA ID is per-WABA: keep the explicit one from `data` if provided,
        # only fall back to parent's WABA if the child didn't set one.
        inherited_verify = parent_line.get("verify_token") or ""
        inherited_wa_token = parent_line.get("whatsapp_token") or data.whatsapp_token or ""
        inherited_waba_id = data.whatsapp_business_account_id or parent_line.get("whatsapp_business_account_id") or ""
    else:
        inherited_verify = data.verify_token or f"verify_{uuid.uuid4().hex[:12]}"
        inherited_wa_token = data.whatsapp_token or ""
        inherited_waba_id = data.whatsapp_business_account_id or ""

    line = {
        "id": str(uuid.uuid4()),
        "name": data.name,
        "line_type": data.line_type,
        "whatsapp_number": data.whatsapp_number,
        # WhatsApp Business API
        "whatsapp_token": inherited_wa_token,
        "phone_number_id": data.phone_number_id or "",
        "verify_token": inherited_verify,
        "whatsapp_business_account_id": inherited_waba_id,
        "webhook_parent_line_id": parent_id or None,
        # Meta Pixel
        "meta_access_token": data.meta_access_token or "",
        "meta_pixel_id": data.meta_pixel_id or "",
        "description": data.description or "",
        "is_active": data.is_active,
        "created_at": now,
        "updated_at": now,
        # Stats
        "total_visits": 0,
        "total_clicks": 0,
        "total_chats": 0,
        "total_cargas": 0,
        "total_monto": 0.0,
    }
    
    await db.crm_lines.insert_one(line)
    line.pop("_id", None)
    return line

@api_router.get("/crm/lines/{line_id}")
async def crm_get_line(line_id: str, current_user=Depends(get_current_user)):
    """Get a specific line with stats"""
    line = await db.crm_lines.find_one({"id": line_id}, {"_id": 0})
    if not line:
        raise HTTPException(status_code=404, detail="Línea no encontrada")
    
    # Add detailed stats
    line["leads_count"] = await db.crm_leads.count_documents({"line_id": line_id})
    line["leads_by_status"] = {}
    for status in CRM_LEAD_STATUSES:
        line["leads_by_status"][status] = await db.crm_leads.count_documents({
            "line_id": line_id, 
            "status": status
        })
    
    return line

@api_router.put("/crm/lines/{line_id}")
async def crm_update_line(line_id: str, data: CRMLineUpdate, current_user=Depends(get_current_user)):
    """Update a line"""
    existing = await db.crm_lines.find_one({"id": line_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Línea no encontrada")
    
    if data.line_type and data.line_type not in CRM_LINE_TYPES:
        raise HTTPException(status_code=400, detail=f"Tipo de línea inválido. Opciones: {CRM_LINE_TYPES}")
    
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    # If linking to a parent webhook line, re-inherit tokens from the parent
    # (only when parent changes or hasn't been resolved yet). This way the
    # admin can switch a line to "use webhook of X" later and the tokens
    # auto-update.
    new_parent_id = update_data.get("webhook_parent_line_id")
    if "webhook_parent_line_id" in update_data and new_parent_id:
        parent_line = await db.crm_lines.find_one({"id": new_parent_id}, {"_id": 0})
        if not parent_line:
            raise HTTPException(status_code=400, detail="webhook_parent_line_id no existe")
        if new_parent_id == line_id:
            raise HTTPException(status_code=400, detail="Una línea no puede ser padre de sí misma")
        update_data["verify_token"] = parent_line.get("verify_token") or ""
        update_data["whatsapp_token"] = parent_line.get("whatsapp_token") or ""
        # WABA ID is per-WABA, not per-App: only inherit if the operator didn't
        # provide an explicit one in this update payload, AND the existing line
        # also has no WABA configured.
        if "whatsapp_business_account_id" not in update_data or not update_data.get("whatsapp_business_account_id"):
            existing = await db.crm_lines.find_one({"id": line_id}, {"_id": 0, "whatsapp_business_account_id": 1})
            if not (existing or {}).get("whatsapp_business_account_id"):
                update_data["whatsapp_business_account_id"] = parent_line.get("whatsapp_business_account_id") or ""

    await db.crm_lines.update_one({"id": line_id}, {"$set": update_data})
    updated = await db.crm_lines.find_one({"id": line_id}, {"_id": 0})
    return updated

@api_router.delete("/crm/lines/{line_id}")
async def crm_delete_line(line_id: str, current_user=Depends(get_current_user)):
    """Delete a line"""
    result = await db.crm_lines.delete_one({"id": line_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Línea no encontrada")
    
    # Unassign leads from this line
    await db.crm_leads.update_many({"line_id": line_id}, {"$set": {"line_id": None}})
    
    return {"message": "Línea eliminada"}


# ─── WhatsApp Cloud API number registration ──────────────────────────
# Two-step process required by Meta to move a number from "Pending" to
# "Connected" in Business Manager:
#   1) request_code → Meta sends OTP via SMS/voice to the physical SIM.
#   2) register → using that OTP + a new PIN (set by the operator),
#      the number is bound to the API and becomes usable.
# Both calls inherit the WhatsApp token from the parent line when this
# line is a child (shared webhook).

def _wa_line_credentials(line: dict) -> tuple:
    """Return (phone_number_id, token) — token from parent if it's a child."""
    return (line.get("phone_number_id") or "", line.get("whatsapp_token") or "")


class WaRequestCodePayload(BaseModel):
    code_method: str = "SMS"  # SMS or VOICE
    language: str = "es"


@api_router.post("/crm/lines/{line_id}/wa-request-code")
async def crm_wa_request_code(
    line_id: str,
    payload: WaRequestCodePayload,
    current_user=Depends(get_current_user),
):
    """Step 1/2: ask Meta to send the 6-digit OTP to the physical SIM."""
    line = await db.crm_lines.find_one({"id": line_id}, {"_id": 0})
    if not line:
        raise HTTPException(status_code=404, detail="Línea no encontrada")
    phone_id, token = _wa_line_credentials(line)
    if not phone_id or not token:
        raise HTTPException(status_code=400, detail="La línea no tiene Phone Number ID o Token configurados")
    if payload.code_method not in ("SMS", "VOICE"):
        raise HTTPException(status_code=400, detail="code_method debe ser SMS o VOICE")

    url = f"{WA_GRAPH_URL}/{phone_id}/request_code"
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"code_method": payload.code_method, "language": payload.language},
            )
            data = r.json() if r.content else {}
            if r.status_code >= 400 or (isinstance(data, dict) and data.get("error")):
                err = (data.get("error") or {}) if isinstance(data, dict) else {}
                msg = err.get("message") or str(data)
                code = err.get("code")
                subcode = err.get("error_subcode")
                # Log full Meta body for debugging
                logger.warning(f"wa request_code Meta error: status={r.status_code} code={code} subcode={subcode} body={data}")
                hint = ""
                if code == 136025 or subcode == 2388045:
                    hint = " (El número ya está verificado — saltá directo a 'Registrar número' con un PIN nuevo, sin OTP.)"
                elif code == 133006:
                    hint = " (Acabás de pedir un código hace poco — esperá unos minutos o usá el que ya te llegó.)"
                elif code == 133010:
                    hint = " (El número no está dado de alta en la WABA. Agregalo primero en Business Manager.)"
                raise HTTPException(status_code=400, detail=f"Meta: {msg} [code={code} subcode={subcode}]{hint}")
            return {"ok": True, "method": payload.code_method, "response": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"wa request_code error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class WaRegisterPayload(BaseModel):
    pin: str  # 6-digit numeric PIN the operator wants to use (will be set on Meta)
    code: Optional[str] = None  # OTP received via SMS/VOICE (omit if number was already verified)


@api_router.post("/crm/lines/{line_id}/wa-register")
async def crm_wa_register(
    line_id: str,
    payload: WaRegisterPayload,
    current_user=Depends(get_current_user),
):
    """Step 2/2: register the number on WhatsApp Cloud API.

    Moves the number from "Pendiente" to "Conectado". From this moment the
    number can send/receive messages through the API.
    """
    line = await db.crm_lines.find_one({"id": line_id}, {"_id": 0})
    if not line:
        raise HTTPException(status_code=404, detail="Línea no encontrada")
    phone_id, token = _wa_line_credentials(line)
    if not phone_id or not token:
        raise HTTPException(status_code=400, detail="La línea no tiene Phone Number ID o Token configurados")

    pin = (payload.pin or "").strip()
    if not pin.isdigit() or len(pin) != 6:
        raise HTTPException(status_code=400, detail="El PIN debe ser de 6 dígitos numéricos")

    body = {"messaging_product": "whatsapp", "pin": pin}
    if payload.code:
        body["code"] = payload.code.strip()

    url = f"{WA_GRAPH_URL}/{phone_id}/register"
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=body,
            )
            data = r.json() if r.content else {}
            if r.status_code >= 400 or (isinstance(data, dict) and data.get("error")):
                err = (data.get("error") or {}) if isinstance(data, dict) else {}
                msg = err.get("message") or str(data)
                code = err.get("code")
                subcode = err.get("error_subcode")
                logger.warning(f"wa register Meta error: status={r.status_code} code={code} subcode={subcode} body={data}")
                hint = ""
                if code == 133005:
                    hint = " (El PIN no coincide con el que ya tenía registrado el número en Meta. Si es un número que ya estuvo en API, usá el PIN original; sino, pedí un nuevo OTP y reseteá.)"
                elif code == 133010:
                    hint = " (Número aún no verificado — primero pedí el código OTP arriba.)"
                elif code == 136025:
                    hint = " (Ya está registrado — el número debería estar funcionando. Si sigue 'Pendiente', esperá 1-2 minutos y refrescá Meta Business Manager.)"
                raise HTTPException(status_code=400, detail=f"Meta: {msg} [code={code} subcode={subcode}]{hint}")
            # Persist the PIN reference for audit (NOT the value itself)
            await db.crm_lines.update_one(
                {"id": line_id},
                {"$set": {
                    "wa_registered_at": datetime.now(timezone.utc).isoformat(),
                    "wa_registered_by": current_user.get("email"),
                }}
            )
            return {"ok": True, "response": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"wa register error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class WaListNumbersPayload(BaseModel):
    waba_id: Optional[str] = None  # explicit override
    parent_line_id: Optional[str] = None  # take waba+token from this line


@api_router.post("/crm/wa-list-numbers")
async def crm_wa_list_numbers(
    payload: WaListNumbersPayload,
    current_user=Depends(get_current_user),
):
    """List all phone numbers registered under a WABA along with their
    phone_number_id, status and quality. Used by the line form so the
    operator can pick the new number from a dropdown instead of copying
    phone_number_id from Devs by hand.

    Source of credentials: pass `parent_line_id` to inherit waba_id+token
    from an existing line, or pass `waba_id` directly (token will come
    from any line that has that WABA).
    """
    waba_id = (payload.waba_id or "").strip()
    token = ""

    if payload.parent_line_id:
        parent = await db.crm_lines.find_one({"id": payload.parent_line_id}, {"_id": 0})
        if not parent:
            raise HTTPException(status_code=404, detail="parent_line_id no existe")
        waba_id = waba_id or parent.get("whatsapp_business_account_id") or ""
        token = parent.get("whatsapp_token") or ""

    if not waba_id:
        raise HTTPException(status_code=400, detail="Falta WABA ID (o parent_line_id con WABA configurado)")
    if not token:
        # Fallback: cualquier línea con esa WABA
        any_line = await db.crm_lines.find_one(
            {"whatsapp_business_account_id": waba_id, "whatsapp_token": {"$nin": [None, ""]}},
            {"_id": 0, "whatsapp_token": 1},
        )
        token = (any_line or {}).get("whatsapp_token") or ""
    if not token:
        raise HTTPException(status_code=400, detail="No hay token disponible para consultar esta WABA")

    url = f"{WA_GRAPH_URL}/{waba_id}/phone_numbers"
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params={"fields": "id,display_phone_number,verified_name,code_verification_status,quality_rating,name_status,messaging_limit_tier"},
            )
            data = r.json() if r.content else {}
            if r.status_code >= 400 or (isinstance(data, dict) and data.get("error")):
                err = (data.get("error") or {}) if isinstance(data, dict) else {}
                msg = err.get("message") or str(data)
                code = err.get("code")
                logger.warning(f"wa list_numbers Meta error: status={r.status_code} code={code} body={data}")
                raise HTTPException(status_code=400, detail=f"Meta: {msg} [code={code}]")
            return {"ok": True, "waba_id": waba_id, "numbers": data.get("data", [])}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"wa list_numbers error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/crm/lines/{line_id}/wa-subscribe-app")
async def crm_wa_subscribe_app(
    line_id: str,
    payload: Optional[Dict] = Body(default=None),
    current_user=Depends(get_current_user),
):
    """Subscribe this line's WABA to the Meta App via Graph API.

    Required (and almost always silently missing) for Meta to actually
    deliver webhooks when a new number is added to an existing WABA.
    Calls `POST /{WABA_ID}/subscribed_apps` with the line's token.

    Accepts an optional body with `waba_id` and/or `token` to override the
    values stored in the line — useful when the operator wants to subscribe
    BEFORE saving the form.
    """
    line = await db.crm_lines.find_one({"id": line_id}, {"_id": 0})
    if not line:
        raise HTTPException(status_code=404, detail="Línea no encontrada")
    override = payload or {}
    waba_id = (override.get("waba_id") or "").strip() or line.get("whatsapp_business_account_id") or ""
    token = (override.get("token") or "").strip() or line.get("whatsapp_token") or ""
    if not waba_id:
        raise HTTPException(status_code=400, detail="La línea no tiene WhatsApp Business Account ID configurado. Pegalo en el campo WABA ID y guardá la línea antes (o pasalo en el form).")
    if not token:
        raise HTTPException(status_code=400, detail="La línea no tiene WhatsApp Token configurado")

    url = f"{WA_GRAPH_URL}/{waba_id}/subscribed_apps"
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(
                url,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            data = r.json() if r.content else {}
            if r.status_code >= 400 or (isinstance(data, dict) and data.get("error")):
                err = (data.get("error") or {}) if isinstance(data, dict) else {}
                msg = err.get("message") or str(data)
                code = err.get("code")
                subcode = err.get("error_subcode")
                logger.warning(f"wa subscribe_app Meta error: status={r.status_code} code={code} subcode={subcode} body={data}")
                hint = ""
                if code == 200:
                    hint = " (El token no tiene permiso 'whatsapp_business_management'. Usá un token de System User con ese permiso.)"
                raise HTTPException(status_code=400, detail=f"Meta: {msg} [code={code} subcode={subcode}]{hint}")
            # Confirm current subscriptions
            check = await c.get(
                f"{WA_GRAPH_URL}/{waba_id}/subscribed_apps",
                headers={"Authorization": f"Bearer {token}"},
            )
            apps_list = []
            try:
                apps_list = (check.json() or {}).get("data", []) if check.status_code < 400 else []
            except Exception:
                apps_list = []
            return {"ok": True, "response": data, "subscribed_apps": apps_list}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"wa subscribe_app error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/crm/lines/{line_id}/assign-lead/{lead_id}")
async def crm_assign_lead_to_line(
    line_id: str,
    lead_id: str,
    current_user=Depends(get_current_user)
):
    """Assign a lead to a specific line"""
    line = await db.crm_lines.find_one({"id": line_id})
    if not line:
        raise HTTPException(status_code=404, detail="Línea no encontrada")
    
    lead = await db.crm_leads.find_one({"id": lead_id})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    await db.crm_leads.update_one(
        {"id": lead_id},
        {"$set": {
            "line_id": line_id,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"message": f"Lead asignado a línea {line['name']}"}


# ─── CRM Line-specific Webhook ─────────────────────────────────────

@api_router.get("/crm/webhook/{line_id}")
async def crm_line_webhook_verify(line_id: str, request: Request):
    """Verify webhook for a specific line (Meta sends GET to verify)"""
    line = await db.crm_lines.find_one({"id": line_id}, {"_id": 0})
    if not line:
        raise HTTPException(status_code=404, detail="Línea no encontrada")
    
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    verify_token = line.get("verify_token", "")
    
    if mode == "subscribe" and token == verify_token:
        logger.info(f"CRM Line webhook verified for line {line['name']}")
        return int(challenge) if challenge else "OK"
    
    raise HTTPException(status_code=403, detail="Verification failed")

@api_router.post("/crm/webhook/{line_id}")
async def crm_line_webhook_receive(line_id: str, request: Request):
    """Receive WhatsApp messages for a specific line.

    Multi-line webhook support: when several CRM lines share the same Meta
    App (and therefore the same webhook URL), Meta keeps calling the URL of
    the "parent" line — but inside the payload the `phone_number_id` in
    metadata tells us which actual number received the message. Here we
    transparently re-route to the line that owns that phone_number_id, so
    every line (parent or child) gets its own messages without exposing a
    different URL.
    """
    line = await db.crm_lines.find_one({"id": line_id}, {"_id": 0})
    if not line:
        logger.error(f"CRM webhook: Line {line_id} not found")
        return {"status": "error", "message": "Line not found"}
    
    body = await request.json()
    try:
        entries = body.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                contacts = value.get("contacts", [])
                
                # Get metadata
                metadata = value.get("metadata", {})
                display_phone = metadata.get("display_phone_number", "")
                phone_number_id = metadata.get("phone_number_id", "")

                # ── Multi-line routing ─────────────────────────────────
                # If the incoming phone_number_id belongs to a different
                # line (i.e. this URL is shared by several lines), swap to
                # the actual owner so we store messages under the correct
                # line and respond with its WhatsApp token.
                if phone_number_id and phone_number_id != line.get("phone_number_id"):
                    real_line = await db.crm_lines.find_one(
                        {"phone_number_id": phone_number_id}, {"_id": 0}
                    )
                    if real_line:
                        if real_line.get("id") != line.get("id"):
                            logger.info(
                                f"Shared webhook: routed to line "
                                f"'{real_line.get('name')}' ({real_line.get('id')}) "
                                f"via phone_number_id={phone_number_id}"
                            )
                        line = real_line
                        # CRITICAL: also refresh `line_id` since downstream
                        # logic reads it (lead lookup, ad attribution, etc).
                        line_id = real_line.get("id")
                    else:
                        logger.warning(
                            f"Shared webhook hit URL of line {line_id} but "
                            f"phone_number_id={phone_number_id} doesn't match "
                            f"any registered line — falling back to URL line."
                        )

                # ── Broadcast message status updates (sent/delivered/read/failed) ──
                # Meta sends `statuses` events with the wa_message_id we stored when
                # the template went out. We update both broadcast_messages AND the
                # parent campaign's stats counters.
                statuses = value.get("statuses", [])
                for st in statuses:
                    wa_id = st.get("id")
                    new_status = st.get("status")  # sent, delivered, read, failed
                    if not wa_id or not new_status:
                        continue
                    bm = await db.broadcast_messages.find_one(
                        {"wa_message_id": wa_id}, {"_id": 0, "campaign_id": 1, "status": 1}
                    )
                    if not bm:
                        continue
                    prev_status = bm.get("status")
                    rank = {"failed": -1, "sent": 0, "delivered": 1, "read": 2}
                    if rank.get(new_status, -2) <= rank.get(prev_status, -2):
                        continue  # don't downgrade
                    set_fields = {"status": new_status, f"{new_status}_at": datetime.now(timezone.utc).isoformat()}
                    await db.broadcast_messages.update_one(
                        {"wa_message_id": wa_id}, {"$set": set_fields}
                    )
                    # Update campaign counters: +1 to new, but only first transition counts
                    if new_status in ("delivered", "read", "failed"):
                        await db.broadcast_campaigns.update_one(
                            {"id": bm["campaign_id"]},
                            {"$inc": {f"stats.{new_status}": 1}}
                        )
                
                contact_map = {}
                for ct in contacts:
                    wa_id = ct.get("wa_id", "")
                    name = ct.get("profile", {}).get("name", "")
                    contact_map[wa_id] = name

                for msg in messages:
                    from_phone = msg.get("from", "")
                    msg_id = msg.get("id", "")
                    msg_type = msg.get("type", "text")
                    timestamp = msg.get("timestamp", "")
                    text = ""
                    if msg_type == "text":
                        text = msg.get("text", {}).get("body", "")
                    elif msg_type == "button":
                        text = msg.get("button", {}).get("text", "")
                    elif msg_type == "interactive":
                        text = msg.get("interactive", {}).get("button_reply", {}).get("title", "")
                    elif msg_type == "image":
                        text = "[Imagen]"
                        image_data = msg.get("image", {})
                        media_id = image_data.get("id", "")
                        mime_type = image_data.get("mime_type", "image/jpeg")
                    elif msg_type == "audio":
                        text = "[Audio]"
                        audio_data = msg.get("audio", {})
                        media_id = audio_data.get("id", "")
                        mime_type = audio_data.get("mime_type", "audio/ogg")
                    elif msg_type == "video":
                        text = "[Video]"
                        video_data = msg.get("video", {})
                        media_id = video_data.get("id", "")
                        mime_type = video_data.get("mime_type", "video/mp4")
                    elif msg_type == "document":
                        doc_data = msg.get("document", {})
                        media_id = doc_data.get("id", "")
                        mime_type = doc_data.get("mime_type", "application/pdf")
                        doc_filename = doc_data.get("filename", "documento.pdf")
                        text = f"[Documento: {doc_filename}]"
                    else:
                        text = f"[{msg_type}]"

                    # ── Auto opt-out detection ──────────────────────────
                    # If the user replied with STOP/BAJA/etc., add them to
                    # the line's broadcast_optouts so future broadcasts
                    # exclude them. Only acts on text-like messages.
                    if msg_type in ("text", "button", "interactive") and is_optout_message(text):
                        try:
                            phone_norm = _norm_e164(from_phone)
                            if phone_norm:
                                await db.broadcast_optouts.update_one(
                                    {"line_id": line_id, "phone": phone_norm},
                                    {"$setOnInsert": {
                                        "id": str(uuid.uuid4()),
                                        "line_id": line_id,
                                        "phone": phone_norm,
                                        "reason": f"auto: '{text.strip()[:50]}'",
                                        "added_by": "auto",
                                        "created_at": datetime.now(timezone.utc).isoformat(),
                                    }},
                                    upsert=True,
                                )
                                logger.info(f"Optout auto-added: line={line_id} phone={phone_norm} text='{text.strip()[:30]}'")
                        except Exception as _e:
                            logger.debug(f"optout auto-add failed: {_e}")

                    # ── Track replies to broadcast campaigns ────────────
                    # Mark the most recent broadcast_messages for this phone+line as
                    # 'replied' so the campaign stats counter goes up exactly once.
                    try:
                        phone_norm_r = _norm_e164(from_phone)
                        if phone_norm_r:
                            recent_bm = await db.broadcast_messages.find_one(
                                {
                                    "line_id": line_id,
                                    "phone": phone_norm_r,
                                    "replied_at": {"$exists": False},
                                    "status": {"$in": ["sent", "delivered", "read"]},
                                },
                                {"_id": 0, "id": 1, "campaign_id": 1},
                                sort=[("created_at", -1)],
                            )
                            if recent_bm:
                                await db.broadcast_messages.update_one(
                                    {"id": recent_bm["id"]},
                                    {"$set": {"replied_at": datetime.now(timezone.utc).isoformat()}}
                                )
                                await db.broadcast_campaigns.update_one(
                                    {"id": recent_bm["campaign_id"]},
                                    {"$inc": {"stats.replied": 1}}
                                )
                    except Exception as _e:
                        logger.debug(f"broadcast reply tracking failed: {_e}")


                    sender_name = contact_map.get(from_phone, "")
                    now = datetime.now(timezone.utc).isoformat()

                    # Extract click_id from message if present (format: "(ID: XXXXX)")
                    click_id = None
                    ad_source = None
                    utm_content = None
                    referral_data = None
                    
                    import re
                    # Tolerant: "(ID: ABC12)", "ID:abc12", "id abc12", etc.
                    click_match = re.search(r'(?i)ID[:\s]*([A-Z0-9]{5,8})', text)
                    if click_match:
                        click_id = click_match.group(1).upper()
                        # Find the wa_click to get utm_content (ad source) and fingerprint data
                        wa_click = await db.wa_clicks.find_one({"click_id": click_id})
                        if wa_click:
                            utm_content = wa_click.get("utm_content", "")
                            ad_source = utm_content if utm_content else None
                    
                    # Also check for (AD:xxx) format from external landings
                    ad_match = re.search(r'\(AD:([^\)]+)\)', text, re.IGNORECASE)
                    if ad_match and not ad_source:
                        ad_source = ad_match.group(1).strip()
                        utm_content = ad_source
                        logger.info(f"CRM: Detected ad source from message: {ad_source}")
                    
                    # Also check for (REF:xxx) format
                    ref_match = re.search(r'\(REF:([^\)]+)\)', text, re.IGNORECASE)
                    if ref_match and not ad_source:
                        ad_source = ref_match.group(1).strip()
                        utm_content = ad_source
                        logger.info(f"CRM: Detected ref source from message: {ad_source}")
                    
                    # Check for Meta Ads referral data (Click-to-WhatsApp ads)
                    # Meta sends this when user clicks on a CTWA ad
                    ctwa_clid = None
                    fb_login_id = None
                    if msg.get("referral"):
                        referral_data = msg.get("referral", {})
                        # referral contains: source_url, source_id, source_type, headline, body, media_type, image_url, video_url, thumbnail_url, ctwa_clid
                        ad_source = ad_source or referral_data.get("source_id") or referral_data.get("headline") or "meta_ad"
                        utm_content = utm_content or referral_data.get("source_id", "")
                        ctwa_clid = referral_data.get("ctwa_clid")
                        # fb_login_id may come in referral or context
                        fb_login_id = referral_data.get("fb_login_id")
                        logger.info(f"CRM: Message from Meta Ad - source_id: {referral_data.get('source_id')}, headline: {referral_data.get('headline')}, ctwa_clid: {ctwa_clid}")
                    
                    # Also check context for fb_login_id and referral
                    msg_context = msg.get("context", {})
                    if msg_context.get("referred_product"):
                        referral_data = referral_data or {}
                        referral_data["referred_product"] = msg_context.get("referred_product")
                        ad_source = ad_source or "product_ad"
                    if msg_context.get("fb_login_id") and not fb_login_id:
                        fb_login_id = msg_context.get("fb_login_id")

                    # Find or create CRM lead for this SPECIFIC line
                    # Each line has its own independent lead/conversation per phone number
                    crm_lead = await db.crm_leads.find_one({"phone": from_phone, "line_id": line_id})
                    
                    if not crm_lead:
                        # Check if there's an unassigned lead (no line_id) we can claim
                        unassigned_lead = await db.crm_leads.find_one({"phone": from_phone, "line_id": None})
                        
                        if unassigned_lead:
                            # Assign existing unassigned lead to this line
                            update_fields = {"line_id": line_id, "updated_at": now}
                            if ad_source and not unassigned_lead.get("ad_source"):
                                update_fields["ad_source"] = ad_source
                                update_fields["utm_content"] = utm_content
                                update_fields["click_id"] = click_id
                            await db.crm_leads.update_one(
                                {"id": unassigned_lead["id"]},
                                {"$set": update_fields}
                            )
                            crm_lead = unassigned_lead
                            crm_lead["line_id"] = line_id
                        # NOTE: If lead exists on a DIFFERENT line, crm_lead stays None
                        # so a NEW lead will be created for THIS line below
                    
                    # Update ad_source if lead exists but doesn't have ad tracking
                    if crm_lead and ad_source and not crm_lead.get("ad_source"):
                        update_data = {"ad_source": ad_source, "utm_content": utm_content, "click_id": click_id}
                        if referral_data:
                            update_data["referral"] = referral_data
                        if ctwa_clid:
                            update_data["ctwa_clid"] = ctwa_clid
                        if fb_login_id:
                            update_data["fb_login_id"] = fb_login_id
                        await db.crm_leads.update_one(
                            {"id": crm_lead["id"]},
                            {"$set": update_data}
                        )
                    # Also update fb_login_id/ctwa_clid even if ad_source already set
                    elif crm_lead and (fb_login_id or ctwa_clid):
                        fb_update = {}
                        if fb_login_id and not crm_lead.get("fb_login_id"):
                            fb_update["fb_login_id"] = fb_login_id
                        if ctwa_clid and not crm_lead.get("ctwa_clid"):
                            fb_update["ctwa_clid"] = ctwa_clid
                        if fb_update:
                            await db.crm_leads.update_one({"id": crm_lead["id"]}, {"$set": fb_update})
                    
                    if not crm_lead:
                        # Create new lead
                        lead_id = str(uuid.uuid4())
                        crm_lead = {
                            "id": lead_id,
                            "name": sender_name or f"Lead {from_phone[-4:]}",
                            "email": None,
                            "phone": from_phone,
                            "status": "nuevo",
                            "score": 50,
                            "source": "whatsapp",
                            "line_id": line_id,
                            "charge_amount": 0.0,
                            "ad_source": ad_source,
                            "utm_content": utm_content,
                            "click_id": click_id,
                            "ctwa_clid": ctwa_clid,
                            "fb_login_id": fb_login_id,
                            "referral": referral_data,  # Store full referral data from Meta Ads
                            "metadata": {
                                "phone_number_id": phone_number_id,
                                "display_phone": display_phone,
                            },
                            "notes": "",
                            "tags": ["webhook", line["name"]],
                            "created_at": now,
                            "updated_at": now,
                            "last_interaction": now,
                            "messages_count": 0,
                            "receipts_count": 0,
                            "meta_events_sent": [],
                        }
                        await db.crm_leads.insert_one(crm_lead)
                        logger.info(f"CRM: Created new lead for {from_phone} on line {line['name']}{' from ad: ' + str(ad_source) if ad_source else ''}")
                        
                        # Send Contact event to Meta if line has credentials
                        if line.get("meta_access_token") and line.get("meta_pixel_id"):
                            contact_result = await send_meta_conversion_event(
                                event_name="Contact",
                                lead_data=crm_lead,
                                custom_data={"content_name": "WhatsApp Contact", "line": line["name"]},
                                access_token=line["meta_access_token"],
                                pixel_id=line["meta_pixel_id"]
                            )
                            await db.crm_leads.update_one(
                                {"id": lead_id},
                                {"$push": {"meta_events_sent": {
                                    "event": "Contact",
                                    "timestamp": now,
                                    "event_id": contact_result.get("event_id"),
                                    "pixel_id": line.get("meta_pixel_id", "")[:8] + "..." if line.get("meta_pixel_id") else None,
                                    "line": line["name"],
                                    "success": contact_result.get("success", False)
                                }}}
                            )

                        # Auto-send welcome message from cajero config (fire-and-forget)
                        import asyncio as _asyncio
                        _asyncio.create_task(send_auto_welcome(crm_lead, line))
                        # Re-fire landing CAPI events with enriched user_data
                        # (Meta dedups by event_id and keeps best EMQ)
                        _asyncio.create_task(resend_enriched_landing_events(crm_lead, line))
                    else:
                        # Update existing lead
                        update_fields = {
                            "last_interaction": now,
                            "updated_at": now,
                        }
                        if sender_name and (not crm_lead.get("name") or crm_lead.get("name", "").startswith("Lead ")):
                            update_fields["name"] = sender_name
                        
                        await db.crm_leads.update_one({"id": crm_lead["id"]}, {"$set": update_fields})
                    
                    # ── Propagate fingerprint/click data to lead for Meta matching ──
                    # This ensures geo-resolution works when Purchase/LowQuality events fire
                    if click_id and wa_click and crm_lead:
                        fingerprint_data = {}
                        if wa_click.get("ip") and not crm_lead.get("ip_address"):
                            fingerprint_data["ip_address"] = wa_click["ip"]
                        if wa_click.get("user_agent") and not crm_lead.get("user_agent"):
                            fingerprint_data["user_agent"] = wa_click["user_agent"]
                        if wa_click.get("fbp") and not crm_lead.get("fbp"):
                            fingerprint_data["fbp"] = wa_click["fbp"]
                        if wa_click.get("fbc") and not crm_lead.get("fbc"):
                            fingerprint_data["fbc"] = wa_click["fbc"]
                        if wa_click.get("landing_code") and not crm_lead.get("landing_code"):
                            fingerprint_data["landing_code"] = wa_click["landing_code"]
                        if wa_click.get("fingerprint_hash") and not crm_lead.get("fingerprint_hash"):
                            fingerprint_data["fingerprint_hash"] = wa_click["fingerprint_hash"]
                        if wa_click.get("email") and not crm_lead.get("email"):
                            fingerprint_data["email"] = wa_click["email"]
                        if fingerprint_data:
                            await db.crm_leads.update_one({"id": crm_lead["id"]}, {"$set": fingerprint_data})
                            logger.info(f"CRM: Propagated click data to lead {crm_lead['id']}: {list(fingerprint_data.keys())}")
                    
                    # Add message to CRM lead chat
                    # Add message to CRM lead chat (with deduplication)
                    lead_id = crm_lead.get("id") or (await db.crm_leads.find_one({"phone": from_phone}))["id"]
                    
                    # Check if message already exists (deduplication)
                    existing_msg = await db.crm_messages.find_one({"wa_message_id": msg_id})
                    if existing_msg:
                        logger.info(f"CRM: Duplicate message {msg_id} ignored")
                        continue
                    
                    crm_message = {
                        "id": str(uuid.uuid4()),
                        "lead_id": lead_id,
                        "content": text,
                        "sender": "lead",
                        "wa_message_id": msg_id,
                        "message_type": msg_type,
                        "media_id": media_id if msg_type in ("image", "document", "audio", "video") else None,
                        "mime_type": mime_type if msg_type in ("image", "document", "audio", "video") else None,
                        "doc_filename": doc_filename if msg_type == "document" else None,
                        "created_at": now,
                    }
                    await db.crm_messages.insert_one(crm_message)
                    
                    # Update message count and mark as unread
                    await db.crm_leads.update_one(
                        {"id": lead_id},
                        {"$inc": {"messages_count": 1, "unread_count": 1}}
                    )
                    
                    logger.info(f"CRM: Message from {from_phone} saved on line {line['name']}")

                    # Fire web push notification to every cajero assigned to this line
                    import asyncio as _asyncio
                    fresh_lead = await db.crm_leads.find_one({"id": lead_id}, {"_id": 0}) or crm_lead
                    preview_text = text if msg_type == "text" else f"[{msg_type}]"
                    _asyncio.create_task(notify_line_cajeros_of_new_message(fresh_lead, line, preview_text))

    except Exception as e:
        logger.error(f"CRM Line webhook error: {e}")
        import traceback
        traceback.print_exc()
    
    return {"status": "ok"}


# ─── CRM Funnel/Embudo Routes ──────────────────────────────────────

@api_router.get("/crm/funnel/stats")
async def crm_funnel_stats(
    line_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    start_date: Optional[str] = Query(None, description="Fecha inicio YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Fecha fin YYYY-MM-DD"),
    filter_type: Optional[str] = Query(None, description="diario, semanal, mensual"),
    current_user=Depends(get_current_user)
):
    # ARG timezone (UTC-3, no DST). Stats use the cajero's local day, not UTC.
    AR_OFFSET = timedelta(hours=-3)
    now_ar = datetime.now(timezone.utc) + AR_OFFSET  # naive-ish AR clock

    def _ar_iso(dt_ar: datetime) -> str:
        """Convert an AR-local moment back to a comparable UTC iso string."""
        return (dt_ar - AR_OFFSET).replace(tzinfo=timezone.utc).isoformat()

    if start_date and end_date:
        # Custom date range — interpret YYYY-MM-DD as AR local days
        try:
            sd = datetime.fromisoformat(start_date).replace(hour=0, minute=0, second=0, microsecond=0)
            ed = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59, microsecond=999999)
            date_from = _ar_iso(sd)
            date_to = _ar_iso(ed)
        except Exception:
            date_from = start_date + "T00:00:00+00:00"
            date_to = end_date + "T23:59:59+00:00"
        period_label = f"{start_date} a {end_date}"
    elif filter_type:
        # Truncate now_ar to start-of-day for AR
        ar_today_start = now_ar.replace(hour=0, minute=0, second=0, microsecond=0)
        if filter_type == "diario" or filter_type == "hoy":
            date_from = _ar_iso(ar_today_start)
            date_to = (now_ar - AR_OFFSET).replace(tzinfo=timezone.utc).isoformat()
            period_label = "Hoy (Argentina)"
        elif filter_type == "ayer":
            ayer_start = ar_today_start - timedelta(days=1)
            date_from = _ar_iso(ayer_start)
            date_to = _ar_iso(ar_today_start - timedelta(microseconds=1))
            period_label = "Ayer (Argentina)"
        elif filter_type == "ultimos_10":
            date_from = _ar_iso(ar_today_start - timedelta(days=9))  # 9 días atrás + hoy = 10
            date_to = (now_ar - AR_OFFSET).replace(tzinfo=timezone.utc).isoformat()
            period_label = "Últimos 10 días"
        elif filter_type == "semanal":
            start_of_week = ar_today_start - timedelta(days=ar_today_start.weekday())
            date_from = _ar_iso(start_of_week)
            date_to = (now_ar - AR_OFFSET).replace(tzinfo=timezone.utc).isoformat()
            period_label = "Esta semana"
        elif filter_type == "mensual" or filter_type == "este_mes":
            start_of_month = ar_today_start.replace(day=1)
            date_from = _ar_iso(start_of_month)
            date_to = (now_ar - AR_OFFSET).replace(tzinfo=timezone.utc).isoformat()
            period_label = "Este mes"
        elif filter_type == "mes_anterior":
            start_of_this_month = ar_today_start.replace(day=1)
            # Last day of prev month at 23:59:59
            end_prev = start_of_this_month - timedelta(microseconds=1)
            start_prev = end_prev.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            date_from = _ar_iso(start_prev)
            date_to = _ar_iso(end_prev)
            period_label = "Mes anterior"
        else:
            date_from = (now_ar - timedelta(days=days) - AR_OFFSET).replace(tzinfo=timezone.utc).isoformat()
            date_to = (now_ar - AR_OFFSET).replace(tzinfo=timezone.utc).isoformat()
            period_label = f"Últimos {days} días"
    else:
        date_from = (now_ar - timedelta(days=days) - AR_OFFSET).replace(tzinfo=timezone.utc).isoformat()
        date_to = (now_ar - AR_OFFSET).replace(tzinfo=timezone.utc).isoformat()
        period_label = f"Últimos {days} días"
    
    date_query = {"created_at": {"$gte": date_from, "$lte": date_to}}

    # Determinar qué líneas puede ver este usuario
    user_line_ids = current_user.get("line_ids", [])
    is_cajero = current_user.get("role") == "cajero"

    if is_cajero and not user_line_ids:
        # Cajero sin líneas — devolver todo en cero
        return {
            "period": f"Últimos {days} días",
            "line_id": line_id,
            "funnel": {"visitas": 0, "clicks": 0, "chats": 0, "cargas": 0},
            "conversion_rates": {"visitas_to_clicks": 0, "clicks_to_chats": 0, "chats_to_cargas": 0, "visitas_to_cargas": 0},
            "totals": {"leads": 0, "monto_cargas": 0, "promedio_carga": 0}
        }

    # Calcular el filtro de línea efectivo
    if is_cajero:
        # Si pide una línea específica, verificar que la tenga asignada
        if line_id and line_id in user_line_ids:
            effective_line_ids = [line_id]
        else:
            effective_line_ids = user_line_ids  # todas sus líneas
    else:
        # Admin: si pide una línea específica la usa, sino todas
        effective_line_ids = [line_id] if line_id else None

    # Construir line_query según si es una o varias líneas
    if effective_line_ids and len(effective_line_ids) == 1:
        line_query = {"line_id": effective_line_ids[0]}
    elif effective_line_ids:
        line_query = {"line_id": {"$in": effective_line_ids}}
    else:
        line_query = {}  # admin sin filtro = todas

    # Visitas y clicks desde WA landings
    if effective_line_ids:
        wa_numbers = []
        for lid in effective_line_ids:
            l = await db.crm_lines.find_one({"id": lid}, {"_id": 0, "whatsapp_number": 1})
            if l and l.get("whatsapp_number"):
                wa_numbers.append(l["whatsapp_number"])

        landing_codes = []
        if wa_numbers:
            async for landing in db.wa_landings.find({"wa_numbers": {"$in": wa_numbers}}, {"code": 1}):
                landing_codes.append(landing["code"])

        if landing_codes:
            total_visits = await db.wa_clicks.count_documents({"landing_code": {"$in": landing_codes}, **date_query})
            total_clicks = await db.wa_clicks.count_documents({"landing_code": {"$in": landing_codes}, "wa_clicked": True, **date_query})
        else:
            total_visits = 0
            total_clicks = 0
    else:
        total_visits = await db.wa_clicks.count_documents(date_query)
        total_clicks = await db.wa_clicks.count_documents({"wa_clicked": True, **date_query})

    # Chats
    chats_pipeline = [
        {"$match": {**line_query, **date_query}},
        {"$match": {"messages_count": {"$gt": 0}}},
        {"$count": "total"}
    ]
    chats_result = await db.crm_leads.aggregate(chats_pipeline).to_list(1)
    total_chats = chats_result[0]["total"] if chats_result else 0

    # Cargas (válidos)
    total_cargas = await db.crm_leads.count_documents({**line_query, **date_query, "status": "valido"})

    # Monto desde charge_amount de leads válidos
    monto_pipeline = [
        {"$match": {**line_query, **date_query, "status": "valido", "charge_amount": {"$gt": 0}}},
        {"$group": {"_id": None, "total_monto": {"$sum": "$charge_amount"}}}
    ]
    monto_result = await db.crm_leads.aggregate(monto_pipeline).to_list(1)
    total_monto = monto_result[0]["total_monto"] if monto_result else 0

    total_leads = await db.crm_leads.count_documents({**line_query, **date_query})

    return {
        "period": period_label,
        "line_id": line_id,
        "funnel": {
            "visitas": total_visits,
            "clicks": total_clicks,
            "chats": total_chats,
            "cargas": total_cargas,
        },
        "conversion_rates": {
            "visitas_to_clicks": round((total_clicks / total_visits * 100), 2) if total_visits > 0 else 0,
            "clicks_to_chats": round((total_chats / total_clicks * 100), 2) if total_clicks > 0 else 0,
            "chats_to_cargas": round((total_cargas / total_chats * 100), 2) if total_chats > 0 else 0,
            "visitas_to_cargas": round((total_cargas / total_visits * 100), 2) if total_visits > 0 else 0,
        },
        "totals": {
            "leads": total_leads,
            "monto_cargas": total_monto,
            "promedio_carga": round(total_monto / total_cargas, 2) if total_cargas > 0 else 0,
        }
    }

@api_router.get("/crm/funnel/by-line")
async def crm_funnel_by_line(
    days: int = Query(30, ge=1, le=90),
    current_user=Depends(get_current_user)
):
    """Get funnel stats grouped by line"""
    lines = await db.crm_lines.find({"is_active": True}, {"_id": 0}).to_list(100)
    
    results = []
    for line in lines:
        # Get leads count and cargas for this line
        leads_count = await db.crm_leads.count_documents({"line_id": line["id"]})
        cargas_count = await db.crm_leads.count_documents({
            "line_id": line["id"],
            "status": "cliente_real"
        })
        
        # Get monto from receipts
        monto_pipeline = [
            {"$lookup": {
                "from": "crm_leads",
                "localField": "lead_id",
                "foreignField": "id",
                "as": "lead"
            }},
            {"$unwind": "$lead"},
            {"$match": {
                "status": "approved",
                "lead.line_id": line["id"]
            }},
            {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$amount", 0]}}}}
        ]
        monto_result = await db.crm_receipts.aggregate(monto_pipeline).to_list(1)
        total_monto = monto_result[0]["total"] if monto_result else 0
        
        results.append({
            "line_id": line["id"],
            "line_name": line["name"],
            "line_type": line["line_type"],
            "whatsapp_number": line["whatsapp_number"],
            "has_pixel": bool(line.get("meta_pixel_id")),
            "leads": leads_count,
            "cargas": cargas_count,
            "conversion_rate": round((cargas_count / leads_count * 100), 2) if leads_count > 0 else 0,
            "monto_total": total_monto,
        })
    
    return results

@api_router.get("/crm/funnel/by-ad")
async def crm_funnel_by_ad(
    line_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=90),
    current_user=Depends(get_current_user)
):
    """Get conversion stats grouped by ad source (utm_content)"""
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days)).isoformat()
    date_query = {"created_at": {"$gte": start_date}}
    
    # Build line filter based on user role
    user_line_ids = current_user.get("line_ids", [])
    if current_user.get("role") == "cajero" and user_line_ids:
        if line_id and line_id in user_line_ids:
            line_query = {"line_id": line_id}
        else:
            line_query = {"line_id": {"$in": user_line_ids}}
    elif current_user.get("role") == "cajero" and not user_line_ids:
        return []
    elif line_id:
        line_query = {"line_id": line_id}
    else:
        line_query = {}
    
    # Aggregate by utm_content/ad_source
    pipeline = [
        {"$match": {**line_query, **date_query, "ad_source": {"$ne": None, "$exists": True}}},
        {"$group": {
            "_id": "$ad_source",
            "total_leads": {"$sum": 1},
            "validos": {"$sum": {"$cond": [{"$eq": ["$status", "valido"]}, 1, 0]}},
            "total_monto": {"$sum": {"$ifNull": ["$charge_amount", 0]}},
        }},
        {"$sort": {"total_leads": -1}}
    ]
    
    results = await db.crm_leads.aggregate(pipeline).to_list(100)
    
    # Format results
    formatted = []
    for r in results:
        formatted.append({
            "ad_source": r["_id"],
            "leads": r["total_leads"],
            "conversiones": r["validos"],
            "monto_total": r["total_monto"],
            "conversion_rate": round((r["validos"] / r["total_leads"] * 100), 2) if r["total_leads"] > 0 else 0,
        })
    
    return formatted

# ─── CRM Leads Routes ──────────────────────────────────────────────

@api_router.post("/crm/leads/enrich")
async def crm_enrich_leads(
    limit: int = Query(500, ge=1, le=5000),
    current_user=Depends(get_current_user)
):
    """
    Retroactively enrich existing leads with better matching data:
    - Geo (city/state/zip) resolved from stored IP
    - Full name from chat messages when WhatsApp only gave first name
    - Gender inferred from first name
    - Email extracted from chat messages
    Improves future Meta CAPI event coverage (EMQ score).
    """
    if current_user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Solo admins pueden ejecutar enrichment")

    stats = {"scanned": 0, "name_enriched": 0, "gender_enriched": 0, "geo_enriched": 0, "email_enriched": 0}

    # Process leads missing any of the valuable fields
    query = {
        "$or": [
            {"city": {"$in": [None, ""]}},
            {"state": {"$in": [None, ""]}},
            {"gender": {"$in": [None, ""]}},
            {"email": {"$in": [None, ""]}},
            {"name_enriched": {"$ne": True}},
        ]
    }
    async for lead in db.crm_leads.find(query, {"_id": 0}).limit(limit):
        stats["scanned"] += 1
        updates = {}
        lead_id = lead.get("id")
        if not lead_id:
            continue

        # 1. Enrich name from chat
        current_name = lead.get("name", "") or ""
        parts = current_name.strip().split()
        if (len(parts) <= 1 or lead.get("name_enriched") is not True) and not current_name.startswith("Lead "):
            full_name = await extract_full_name_from_messages(lead_id)
            if full_name and full_name != current_name:
                updates["name"] = full_name
                updates["name_enriched"] = True
                stats["name_enriched"] += 1

        # 2. Enrich geo from stored IP
        if not lead.get("city") or not lead.get("state"):
            ip = lead.get("ip_address")
            if ip:
                geo = await resolve_geo_from_ip(ip)
                if geo:
                    if geo.get("city") and not lead.get("city"):
                        updates["city"] = geo["city"]
                    if geo.get("state") and not lead.get("state"):
                        updates["state"] = geo["state"]
                    if geo.get("zip") and not lead.get("zip_code"):
                        updates["zip_code"] = geo["zip"]
                    if geo.get("country_code") and not lead.get("country_code"):
                        updates["country_code"] = geo["country_code"]
                    if any(k in updates for k in ("city", "state", "zip_code", "country_code")):
                        stats["geo_enriched"] += 1

        # 3. Enrich gender from name
        if not lead.get("gender"):
            effective_name = updates.get("name", current_name)
            gender = infer_gender_from_name(effective_name)
            if gender:
                updates["gender"] = gender
                stats["gender_enriched"] += 1

        # 4. Enrich email from chat
        if not lead.get("email"):
            email = await extract_email_from_messages(lead_id)
            if email:
                updates["email"] = email
                stats["email_enriched"] += 1

        if updates:
            updates["enriched_at"] = datetime.now(timezone.utc).isoformat()
            await db.crm_leads.update_one({"id": lead_id}, {"$set": updates})

    logger.info(f"Enrich leads: {stats}")
    return {"ok": True, "stats": stats}


@api_router.get("/crm/leads")
async def crm_get_all_leads(
    status: Optional[str] = None,
    line_id: Optional[str] = None,
    min_score: int = 0,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    current_user=Depends(get_current_user)
):
    """Get all CRM leads with optional filters"""
    query = {}
    if status:
        query["status"] = status
    if min_score > 0:
        query["score"] = {"$gte": min_score}

    # Filtro por líneas según rol del usuario
    user_line_ids = current_user.get("line_ids", [])
    if current_user.get("role") == "cajero" and user_line_ids:
        # Cajero solo ve sus líneas asignadas
        if line_id and line_id in user_line_ids:
            query["line_id"] = line_id  # filtro específico dentro de sus líneas
        else:
            query["line_id"] = {"$in": user_line_ids}
    elif current_user.get("role") == "cajero" and not user_line_ids:
        # Cajero sin líneas asignadas no ve nada
        return {"leads": [], "total": 0, "page": page, "pages": 1}
    elif line_id:
        query["line_id"] = line_id  # admin con filtro manual

    total = await db.crm_leads.count_documents(query)
    skip = (page - 1) * limit

    leads = await db.crm_leads.find(query, {"_id": 0}).sort("last_interaction", -1).skip(skip).limit(limit).to_list(limit)

    # Add line info and unread flag to each lead
    for lead in leads:
        if lead.get("line_id"):
            line = await db.crm_lines.find_one({"id": lead["line_id"]}, {"_id": 0, "name": 1, "line_type": 1})
            lead["line_name"] = line["name"] if line else None
            lead["line_type"] = line["line_type"] if line else None
        lead["has_unread_messages"] = lead.get("unread_count", 0) > 0
        # Attribution flags for quick display in kanban/list (Kommo-style)
        referral = lead.get("referral") or {}
        has_ctwa = bool(lead.get("ctwa_clid") or referral.get("ctwa_clid"))
        has_landing = bool(lead.get("landing_code"))
        has_utm = bool(lead.get("ad_source") or lead.get("utm_content"))
        lead["has_ad_attribution"] = has_ctwa or has_landing or has_utm
        if has_ctwa:
            lead["ad_badge"] = {"label": "Anuncio Meta", "color": "blue", "source": "ctwa"}
        elif has_landing:
            lead["ad_badge"] = {"label": f"Landing {lead.get('landing_code')}", "color": "emerald", "source": "landing"}
        elif has_utm:
            lead["ad_badge"] = {"label": lead.get("ad_source") or lead.get("utm_content"), "color": "amber", "source": "utm"}

    return {
        "leads": leads,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit if total > 0 else 1
    }


async def _enrich_lead_for_list(lead: dict) -> dict:
    """Add line_name/line_type, has_unread_messages and ad_badge to a lead dict."""
    if lead.get("line_id"):
        line = await db.crm_lines.find_one({"id": lead["line_id"]}, {"_id": 0, "name": 1, "line_type": 1})
        lead["line_name"] = line["name"] if line else None
        lead["line_type"] = line["line_type"] if line else None
    lead["has_unread_messages"] = lead.get("unread_count", 0) > 0
    referral = lead.get("referral") or {}
    has_ctwa = bool(lead.get("ctwa_clid") or referral.get("ctwa_clid"))
    has_landing = bool(lead.get("landing_code"))
    has_utm = bool(lead.get("ad_source") or lead.get("utm_content"))
    lead["has_ad_attribution"] = has_ctwa or has_landing or has_utm
    if has_ctwa:
        lead["ad_badge"] = {"label": "Anuncio Meta", "color": "blue", "source": "ctwa"}
    elif has_landing:
        lead["ad_badge"] = {"label": f"Landing {lead.get('landing_code')}", "color": "emerald", "source": "landing"}
    elif has_utm:
        lead["ad_badge"] = {"label": lead.get("ad_source") or lead.get("utm_content"), "color": "amber", "source": "utm"}
    return lead


@api_router.get("/crm/leads/changed")
async def crm_get_leads_changed(
    since: str = Query(..., description="ISO timestamp; only leads with last_interaction or updated_at > since are returned"),
    line_id: Optional[str] = None,
    limit: int = Query(200, ge=1, le=500),
    current_user=Depends(get_current_user),
):
    """Delta sync endpoint — returns ONLY leads that changed since `since`.

    Use case: frontend polling. Instead of pulling 500 leads every 10s, the
    client asks "what changed since I last synced?". Drastically reduces
    egress (~90% on idle CRMs).

    Server returns server_now so the client knows what to send as `since` next
    time (avoids client/server clock drift).
    """
    # Parse since timestamp safely
    try:
        # Accept both with and without 'Z'; we just compare as ISO strings
        # since we store them as ISO strings ourselves.
        if since.endswith("Z"):
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        else:
            since_dt = datetime.fromisoformat(since)
        if since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="`since` debe ser un timestamp ISO 8601 válido")

    since_iso = since_dt.isoformat()

    query: Dict = {
        "$or": [
            {"last_interaction": {"$gt": since_iso}},
            {"updated_at": {"$gt": since_iso}},
        ]
    }

    # Cajero scoping (idéntico al endpoint /crm/leads)
    user_line_ids = current_user.get("line_ids", [])
    if current_user.get("role") == "cajero" and user_line_ids:
        if line_id and line_id in user_line_ids:
            query["line_id"] = line_id
        else:
            query["line_id"] = {"$in": user_line_ids}
    elif current_user.get("role") == "cajero" and not user_line_ids:
        return {"leads": [], "server_now": datetime.now(timezone.utc).isoformat(), "count": 0}
    elif line_id:
        query["line_id"] = line_id

    leads = await db.crm_leads.find(query, {"_id": 0}).sort("last_interaction", -1).limit(limit).to_list(limit)
    for lead in leads:
        await _enrich_lead_for_list(lead)

    return {
        "leads": leads,
        "server_now": datetime.now(timezone.utc).isoformat(),
        "count": len(leads),
    }

@api_router.post("/crm/leads")
async def crm_create_lead(data: CRMLeadCreate, current_user=Depends(get_current_user)):
    """Create a new CRM lead manually"""
    now = datetime.now(timezone.utc).isoformat()
    
    lead = {
        "id": str(uuid.uuid4()),
        "name": data.name,
        "email": data.email,
        "phone": data.phone,
        "status": "nuevo",  # Default status
        "score": 50,  # Default score
        "source": data.source,
        "line_id": data.line_id,  # Assigned line
        "charge_amount": 0.0,  # Monto de carga
        "metadata": data.metadata or {},
        "notes": data.notes or "",
        "tags": data.tags or [],
        "created_at": now,
        "updated_at": now,
        "last_interaction": now,
        "messages_count": 0,
        "receipts_count": 0,
        "meta_events_sent": [],
    }
    
    await db.crm_leads.insert_one(lead)
    lead.pop("_id", None)
    return lead

@api_router.get("/crm/leads/{lead_id}")
async def crm_get_lead(lead_id: str, current_user=Depends(get_current_user)):
    """Get detailed info about a specific lead"""
    lead = await db.crm_leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    return lead

@api_router.get("/crm/leads/{lead_id}/ad-preview")
async def crm_get_lead_ad_preview(lead_id: str, current_user=Depends(get_current_user)):
    """
    Returns a normalized ad/landing preview for a lead so the frontend can show
    Kommo-style ad preview card above the chat.

    Sources (in priority order):
    1. Meta CTWA referral data (msg.referral from Click-to-WhatsApp Ads)
    2. Our own landing (wa_landings) matched via landing_code
    3. UTM tracking data (ad_source/utm_content) as fallback
    4. None if no attribution available
    """
    lead = await db.crm_leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")

    referral = lead.get("referral") or {}
    landing_code = lead.get("landing_code")
    ad_source = lead.get("ad_source")
    utm_content = lead.get("utm_content")
    ctwa_clid = lead.get("ctwa_clid")

    # 1. Meta CTWA Ad referral — richest source (image, headline, body, etc.)
    if referral and (referral.get("headline") or referral.get("source_id") or referral.get("image_url") or referral.get("video_url")):
        media_type = referral.get("media_type") or ("video" if referral.get("video_url") else "image")
        # Construct a clickable Meta link. Priority:
        # 1. source_url from referral (the real ad post URL Meta sends)
        # 2. Meta Ads Library link built from the ad id (source_id)
        meta_source_url = referral.get("source_url")
        meta_source_id = referral.get("source_id")
        ads_library_url = None
        if meta_source_id:
            ads_library_url = f"https://www.facebook.com/ads/library/?id={meta_source_id}"
        return {
            "has_preview": True,
            "source": "meta_ctwa_ad",
            "headline": referral.get("headline") or "Anuncio de Meta",
            "body": referral.get("body") or "",
            "image_url": referral.get("image_url") or referral.get("thumbnail_url"),
            "video_url": referral.get("video_url"),
            "thumbnail_url": referral.get("thumbnail_url"),
            "media_type": media_type,
            "source_url": meta_source_url or ads_library_url,
            "source_id": meta_source_id,
            "ads_library_url": ads_library_url,
            "ctwa_clid": ctwa_clid,
            "ad_source": ad_source or meta_source_id,
            "badge_label": "Click-to-WhatsApp Ad",
            "badge_color": "blue",
        }

    # 2. Own landing — use wa_landings config for preview
    if landing_code:
        landing = await db.wa_landings.find_one({"code": landing_code}, {"_id": 0})
        if landing:
            app_url = os.environ.get("APP_URL", "")
            preview_url = f"{app_url}/l/{landing_code}" if app_url else None
            # Pick a representative image — try logo_url, hero_image, bonus_image
            image_url = (
                landing.get("logo_url")
                or landing.get("hero_image")
                or landing.get("bonus_image")
                or landing.get("image_url")
            )
            headline = landing.get("title") or landing.get("headline") or f"Landing: {landing_code}"
            body = landing.get("subtitle") or landing.get("description") or landing.get("bonus_text") or ""
            return {
                "has_preview": True,
                "source": "own_landing",
                "headline": headline,
                "body": body,
                "image_url": image_url,
                "video_url": None,
                "thumbnail_url": image_url,
                "media_type": "image",
                "source_url": preview_url,
                "source_id": landing_code,
                "ctwa_clid": ctwa_clid,
                "ad_source": ad_source or utm_content,
                "badge_label": f"Landing · {landing_code}",
                "badge_color": "emerald",
            }

    # 3. UTM / ad_source fallback — no visual preview, just a badge
    if ad_source or utm_content or ctwa_clid:
        return {
            "has_preview": True,
            "source": "utm_tracking",
            "headline": ad_source or utm_content or "Origen de anuncio",
            "body": "",
            "image_url": None,
            "video_url": None,
            "thumbnail_url": None,
            "media_type": None,
            "source_url": None,
            "source_id": ad_source or utm_content,
            "ctwa_clid": ctwa_clid,
            "ad_source": ad_source or utm_content,
            "badge_label": "Campaña rastreada",
            "badge_color": "amber",
        }

    # 4. No attribution
    return {"has_preview": False}

@api_router.put("/crm/leads/{lead_id}")
async def crm_update_lead(lead_id: str, data: CRMLeadUpdate, current_user=Depends(get_current_user)):
    """Update lead info (manual)"""
    existing = await db.crm_leads.find_one({"id": lead_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.crm_leads.update_one({"id": lead_id}, {"$set": update_data})
    updated = await db.crm_leads.find_one({"id": lead_id}, {"_id": 0})
    return updated


class CRMLeadNameEdit(BaseModel):
    name: str
    refire_meta: Optional[bool] = True  # Re-fire latest Lead/Contact event with corrected name


@api_router.patch("/crm/leads/{lead_id}/name")
async def crm_edit_lead_name(
    lead_id: str,
    data: CRMLeadNameEdit,
    current_user=Depends(get_current_user),
):
    """Manually edit a lead's name (e.g. cajero saw the real name on a payment receipt).

    When the name is corrected:
      * Persists `name_enriched=True` so auto-enrichment doesn't overwrite it.
      * Audit fields: `name_edited_by`, `name_edited_at`, `name_previous`.
      * If `refire_meta=True` and there's a previous Lead/Contact event for this lead,
        re-fires it with the SAME event_id so Meta dedupes and KEEPS the higher-quality one.
        This recovers the EMQ score retroactively when the original name was emoji garbage.
    """
    new_name = (data.name or "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacío")
    if len(new_name) > 120:
        raise HTTPException(status_code=400, detail="Nombre demasiado largo (máx 120)")

    lead = await db.crm_leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")

    # Cajero permission check: respect line ownership
    if not _user_can_use_line(current_user, lead.get("line_id")):
        raise HTTPException(status_code=403, detail="Sin acceso a este lead")

    previous_name = lead.get("name") or ""
    if new_name == previous_name:
        return {"updated": False, "message": "El nombre no cambió", "lead": lead}

    now = datetime.now(timezone.utc).isoformat()
    await db.crm_leads.update_one(
        {"id": lead_id},
        {"$set": {
            "name": new_name,
            "name_enriched": True,
            "name_edited_by": current_user.get("email"),
            "name_edited_at": now,
            "name_previous": previous_name,
            "updated_at": now,
        }}
    )

    refired = []
    refire_error = None
    if data.refire_meta:
        # Find latest Lead/Contact event for this lead from the centralized log,
        # so we can re-fire with the SAME event_id (Meta dedupe → keeps higher EMQ).
        try:
            line = None
            if lead.get("line_id"):
                line = await db.crm_lines.find_one({"id": lead["line_id"]}, {"_id": 0})
            line_token = (line or {}).get("meta_access_token")
            line_pixel = (line or {}).get("meta_pixel_id")

            if line_token and line_pixel:
                # Get the most recent Lead and/or Contact event_ids for this lead
                events_to_refire = await db.meta_events_log.find(
                    {"lead_id": lead_id, "event_name": {"$in": ["Lead", "Contact"]}, "success": True},
                    {"_id": 0, "event_name": 1, "event_id": 1},
                    sort=[("created_at", -1)],
                ).to_list(length=10)

                # Dedupe by event_name → most recent only
                seen = set()
                latest_per_name = []
                for ev in events_to_refire:
                    if ev["event_name"] in seen:
                        continue
                    seen.add(ev["event_name"])
                    latest_per_name.append(ev)

                # Re-build lead_data with the new name
                refreshed_lead = await db.crm_leads.find_one({"id": lead_id}, {"_id": 0})
                for ev in latest_per_name:
                    res = await send_meta_conversion_event(
                        event_name=ev["event_name"],
                        lead_data=refreshed_lead,
                        access_token=line_token,
                        pixel_id=line_pixel,
                        event_id=ev["event_id"],  # SAME event_id → Meta dedupes
                    )
                    if res.get("success"):
                        refired.append(ev["event_name"])
                    else:
                        refire_error = res.get("error")
        except Exception as e:
            logger.warning(f"Refire CAPI on name edit failed: {e}")
            refire_error = str(e)

    updated = await db.crm_leads.find_one({"id": lead_id}, {"_id": 0})
    return {
        "updated": True,
        "lead": updated,
        "previous_name": previous_name,
        "refired_events": refired,
        "refire_error": refire_error,
    }

@api_router.delete("/crm/leads/{lead_id}")
async def crm_delete_lead(lead_id: str, current_user=Depends(get_current_user)):
    """Delete a lead and all associated data"""
    result = await db.crm_leads.delete_one({"id": lead_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    # Also delete associated messages and receipts
    await db.crm_messages.delete_many({"lead_id": lead_id})
    await db.crm_receipts.delete_many({"lead_id": lead_id})
    
    return {"message": "Lead eliminado"}

@api_router.post("/crm/leads/{lead_id}/classify")
async def crm_classify_lead(
    lead_id: str,
    data: CRMLeadClassify,
    current_user=Depends(get_current_user)
):
    """
    Classify lead manually and send event to Meta
    
    Status options (simplified):
    - nuevo: New lead, no classification yet (no event)
    - spam: Spam/Bot (sends LowQualityLead to Meta)
    - consultas: Just asking — STANDBY tag only, NO Meta event sent
      (prevents negative signal before a potential late Purchase)
    - valido: Valid customer who made a purchase (sends Purchase to Meta)
    
    Uses line-specific Meta credentials if the lead is assigned to a line
    """
    lead = await db.crm_leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    if data.status not in CRM_LEAD_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status inválido. Opciones: {CRM_LEAD_STATUSES}")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Get line-specific Meta credentials if lead is assigned to a line
    line_token = None
    line_pixel = None
    line_name = None
    if lead.get("line_id"):
        line = await db.crm_lines.find_one({"id": lead["line_id"]}, {"_id": 0})
        if line:
            line_token = line.get("meta_access_token") or None
            line_pixel = line.get("meta_pixel_id") or None
            line_name = line.get("name")
    
    # Update lead status
    update_data = {
        "status": data.status,
        "updated_at": now,
        "classified_at": now,
        "classified_by": current_user.get("email"),
    }
    
    # If valido and has conversion value, update charge_amount
    if data.status == "valido" and data.conversion_value:
        update_data["charge_amount"] = data.conversion_value
    
    # Adjust score based on status
    score_map = {
        "nuevo": 50,
        "spam": 0,
        "consultas": 25,
        "valido": 100
    }
    update_data["score"] = score_map.get(data.status, 50)
    
    meta_result = None
    event_sent = None
    
    # Determine which token/pixel to use (only line-specific, no fallback to env vars)
    use_token = line_token
    use_pixel = line_pixel
    
    # Send event to Meta based on classification
    if data.send_to_meta and line_token and line_pixel:
        if data.status == "valido":
            # Send Purchase event for valid customers
            purchase_value = float(data.conversion_value) if data.conversion_value else 0.0
            # Currency from deployment-wide env var (USD or ARS)
            purchase_currency = PURCHASE_CURRENCY
            custom_data = {
                "currency": purchase_currency,
                "value": purchase_value,
                "content_type": "product",
            }
            logger.info(f"Purchase event for lead {lead_id}: value={purchase_value}, currency={purchase_currency}")
            meta_result = await send_meta_conversion_event(
                event_name="Purchase",
                lead_data=lead,
                custom_data=custom_data,
                access_token=use_token,
                pixel_id=use_pixel
            )
            event_sent = "Purchase"
            
            # Log meta event
            update_data["meta_events_sent"] = lead.get("meta_events_sent", []) + [{
                "event": "Purchase",
                "timestamp": now,
                "value": purchase_value,
                "currency": purchase_currency,
                "event_id": meta_result.get("event_id"),
                "line": line_name,
                "pixel_id": use_pixel[:8] + "..." if use_pixel else None,
                "success": meta_result.get("success", False)
            }]
            
        elif data.status == "spam":
            # For spam — send LowQualityLead event to Meta (teaches algo to avoid similar profiles)
            meta_result = await send_meta_conversion_event(
                event_name="LowQualityLead",
                lead_data=lead,
                custom_data={"lead_quality": data.status},
                access_token=use_token,
                pixel_id=use_pixel
            )
            event_sent = "LowQualityLead"
            
            # Log meta event
            update_data["meta_events_sent"] = lead.get("meta_events_sent", []) + [{
                "event": "LowQualityLead",
                "timestamp": now,
                "quality": data.status,
                "line": line_name,
                "pixel_id": use_pixel[:8] + "..." if use_pixel else None,
                "success": meta_result.get("success", False)
            }]

        elif data.status == "consultas":
            # "Consultas" is a STANDBY tag — no Meta event sent.
            # Reason: many leads ask first and purchase 4+ hours later. If we send
            # LowQualityLead now, we can't override with Purchase later (Meta dedupe
            # + negative signal already sent). Keep the lead clean for future Purchase.
            event_sent = None
            logger.info(f"CRM: Lead {lead_id} marked as 'consultas' (standby, no Meta event sent)")
    
    await db.crm_leads.update_one({"id": lead_id}, {"$set": update_data})
    updated_lead = await db.crm_leads.find_one({"id": lead_id}, {"_id": 0})
    
    return {
        "lead": updated_lead,
        "event_sent": event_sent,
        "meta_result": meta_result,
        "used_line_credentials": bool(line_token and line_pixel),
        "line_name": line_name
    }

@api_router.post("/crm/leads/{lead_id}/move")
async def crm_move_lead(
    lead_id: str,
    new_status: str = Query(..., description="New status for the lead"),
    current_user=Depends(get_current_user)
):
    """Move lead to a different status (for Kanban drag & drop)"""
    if new_status not in CRM_LEAD_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status inválido. Opciones: {CRM_LEAD_STATUSES}")
    
    lead = await db.crm_leads.find_one({"id": lead_id})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    score_map = {
        "nuevo": 50,
        "spam": 0,
        "consultas": 25,
        "valido": 100
    }
    
    await db.crm_leads.update_one(
        {"id": lead_id},
        {"$set": {
            "status": new_status,
            "score": score_map.get(new_status, 50),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    updated = await db.crm_leads.find_one({"id": lead_id}, {"_id": 0})
    return updated

# ─── CRM Messages Routes ───────────────────────────────────────────

@api_router.post("/crm/leads/{lead_id}/read")
async def crm_mark_lead_read(lead_id: str, current_user=Depends(get_current_user)):
    """Reset unread_count to 0 when a user opens the chat"""
    lead = await db.crm_leads.find_one({"id": lead_id})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    await db.crm_leads.update_one(
        {"id": lead_id},
        {"$set": {"unread_count": 0}}
    )
    return {"ok": True}

@api_router.get("/crm/leads/{lead_id}/messages")
async def crm_get_lead_messages(
    lead_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    unified: bool = Query(True),
    current_user=Depends(get_current_user)
):
    """
    Get messages for a lead.

    When unified=True (default), returns the chat history aggregated across
    all leads that share BOTH the same phone AND the same line_id as the
    current lead. This preserves continuity when a returning customer comes
    back to the SAME line (brand) months later, but does NOT leak history
    from the same phone on OTHER lines (which would belong to other
    cajeros / brands and confuses the cajero — e.g. the auto-welcome of a
    different line shows up).

    Pass ?unified=false to force strictly the single lead's messages.
    """
    lead = await db.crm_leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")

    phone = lead.get("phone")
    line_id = lead.get("line_id")
    if unified and phone:
        # Scope unification to the same line_id so cajeros only see THEIR
        # brand's history with this phone. line_id may be None for legacy
        # leads — match those together too.
        related = await db.crm_leads.find(
            {"phone": phone, "line_id": line_id},
            {"id": 1, "_id": 0}
        ).to_list(100)
        related_ids = [r["id"] for r in related if r.get("id")]
        if lead_id not in related_ids:
            related_ids.append(lead_id)
        query = {"lead_id": {"$in": related_ids}}
        unified_used = len(related_ids) > 1
    else:
        query = {"lead_id": lead_id}
        unified_used = False

    total = await db.crm_messages.count_documents(query)
    skip = (page - 1) * limit

    messages = await db.crm_messages.find(
        query, {"_id": 0}
    ).sort("created_at", 1).skip(skip).limit(limit).to_list(limit)

    return {
        "messages": messages,
        "total": total,
        "page": page,
        "unified": unified_used,
    }

@api_router.get("/crm/messages/{message_id}/image")
async def crm_get_message_image(message_id: str, current_user=Depends(get_current_user)):
    """Download image from WhatsApp media and return as base64"""
    msg = await db.crm_messages.find_one({"id": message_id}, {"_id": 0})
    if not msg:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    if msg.get("message_type") != "image" or not msg.get("media_id"):
        raise HTTPException(status_code=400, detail="El mensaje no es una imagen")
    
    lead = await db.crm_leads.find_one({"id": msg["lead_id"]}, {"_id": 0})
    if not lead or not lead.get("line_id"):
        raise HTTPException(status_code=400, detail="Lead sin línea asignada")
    
    line = await db.crm_lines.find_one({"id": lead["line_id"]}, {"_id": 0})
    if not line or not line.get("whatsapp_token"):
        raise HTTPException(status_code=400, detail="Línea sin token de WhatsApp")
    
    token = line["whatsapp_token"]
    media_id = msg["media_id"]
    
    async with httpx.AsyncClient() as client:
        # Step 1: get the media URL
        url_resp = await client.get(
            f"https://graph.facebook.com/v18.0/{media_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        if url_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Error obteniendo URL de la imagen")
        media_url = url_resp.json().get("url")
        
        # Step 2: download the actual image
        img_resp = await client.get(
            media_url,
            headers={"Authorization": f"Bearer {token}"}
        )
        if img_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Error descargando imagen")
        
        img_base64 = base64.b64encode(img_resp.content).decode("utf-8")
        mime = msg.get("mime_type", "image/jpeg")
        return {"image_base64": img_base64, "mime_type": mime}

@api_router.get("/crm/messages/{message_id}/document")
async def crm_get_message_document(message_id: str, current_user=Depends(get_current_user)):
    """Download document from WhatsApp media and return as base64"""
    msg = await db.crm_messages.find_one({"id": message_id}, {"_id": 0})
    if not msg:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    if msg.get("message_type") != "document" or not msg.get("media_id"):
        raise HTTPException(status_code=400, detail="El mensaje no es un documento")

    lead = await db.crm_leads.find_one({"id": msg["lead_id"]}, {"_id": 0})
    if not lead or not lead.get("line_id"):
        raise HTTPException(status_code=400, detail="Lead sin línea asignada")

    line = await db.crm_lines.find_one({"id": lead["line_id"]}, {"_id": 0})
    if not line or not line.get("whatsapp_token"):
        raise HTTPException(status_code=400, detail="Línea sin token de WhatsApp")

    token = line["whatsapp_token"]
    media_id = msg["media_id"]

    async with httpx.AsyncClient() as client:
        url_resp = await client.get(
            f"https://graph.facebook.com/v18.0/{media_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        if url_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Error obteniendo URL del documento")
        media_url = url_resp.json().get("url")

        doc_resp = await client.get(
            media_url,
            headers={"Authorization": f"Bearer {token}"}
        )
        if doc_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Error descargando documento")

        doc_base64 = base64.b64encode(doc_resp.content).decode("utf-8")
        mime = msg.get("mime_type", "application/pdf")
        filename = msg.get("doc_filename", "documento.pdf")
        return {"image_base64": doc_base64, "mime_type": mime, "filename": filename}

@api_router.get("/crm/messages/{message_id}/audio")
async def crm_get_message_audio(message_id: str, current_user=Depends(get_current_user)):
    """Download audio from WhatsApp media and return as base64"""
    msg = await db.crm_messages.find_one({"id": message_id}, {"_id": 0})
    if not msg:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    if msg.get("message_type") != "audio" or not msg.get("media_id"):
        raise HTTPException(status_code=400, detail="El mensaje no es un audio")

    lead = await db.crm_leads.find_one({"id": msg["lead_id"]}, {"_id": 0})
    if not lead or not lead.get("line_id"):
        raise HTTPException(status_code=400, detail="Lead sin línea asignada")

    line = await db.crm_lines.find_one({"id": lead["line_id"]}, {"_id": 0})
    if not line or not line.get("whatsapp_token"):
        raise HTTPException(status_code=400, detail="Línea sin token de WhatsApp")

    token = line["whatsapp_token"]
    media_id = msg["media_id"]

    async with httpx.AsyncClient() as client:
        url_resp = await client.get(
            f"https://graph.facebook.com/v18.0/{media_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        if url_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Error obteniendo URL del audio")
        media_url = url_resp.json().get("url")

        audio_resp = await client.get(
            media_url,
            headers={"Authorization": f"Bearer {token}"}
        )
        if audio_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Error descargando audio")

        audio_base64 = base64.b64encode(audio_resp.content).decode("utf-8")
        mime = msg.get("mime_type", "audio/ogg")
        return {"audio_base64": audio_base64, "mime_type": mime}


@api_router.post("/crm/leads/{lead_id}/messages")
async def crm_send_message(
    lead_id: str,
    data: CRMMessageCreate,
    current_user=Depends(get_current_user)
):
    """Add a message to the lead's chat history. If sender is admin, sends to WhatsApp."""
    lead = await db.crm_leads.find_one({"id": lead_id})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # If admin is sending, send to WhatsApp via the line's credentials
    wa_result = None
    if data.sender == "admin" and lead.get("line_id") and lead.get("phone"):
        line = await db.crm_lines.find_one({"id": lead["line_id"]}, {"_id": 0})
        if line and line.get("whatsapp_token") and line.get("phone_number_id"):
            wa_result = await wa_send_text(
                phone=lead["phone"],
                message=data.content,
                token=line["whatsapp_token"],
                phone_id=line["phone_number_id"]
            )
            logger.info(f"CRM: Sent WhatsApp message to {lead['phone']} via line {line.get('name')}: {wa_result}")
        else:
            logger.warning(f"CRM: Line {lead.get('line_id')} missing whatsapp_token or phone_number_id")
    
    # Check if this is the first message from the lead (for Contact event)
    is_first_lead_message = False
    if data.sender == "lead":
        existing_lead_messages = await db.crm_messages.count_documents({
            "lead_id": lead_id,
            "sender": "lead"
        })
        is_first_lead_message = existing_lead_messages == 0
    
    message = {
        "id": str(uuid.uuid4()),
        "lead_id": lead_id,
        "content": data.content,
        "sender": data.sender,  # "admin" or "lead"
        "created_at": now,
        "wa_result": wa_result  # Store WhatsApp API response if sent
    }
    
    await db.crm_messages.insert_one(message)
    
    # Update lead's last interaction and message count
# Update lead's last interaction, message count, and unread flag
    update_fields = {"last_interaction": now, "updated_at": now}
    if data.sender == "lead":
        # New message from the lead → mark as unread
        await db.crm_leads.update_one(
            {"id": lead_id},
            {
                "$set": update_fields,
                "$inc": {"messages_count": 1, "unread_count": 1}
            }
        )
    else:
        # Admin sent → clear unread
        await db.crm_leads.update_one(
            {"id": lead_id},
            {
                "$set": update_fields,
                "$inc": {"messages_count": 1}
            }
        )
    
    # Send Contact event to Meta on first lead message
    meta_result = None
    if is_first_lead_message and lead.get("line_id"):
        line = await db.crm_lines.find_one({"id": lead["line_id"]}, {"_id": 0})
        if line and line.get("meta_access_token") and line.get("meta_pixel_id"):
            meta_result = await send_meta_conversion_event(
                event_name="Contact",
                lead_data=lead,
                custom_data={"content_name": "WhatsApp Contact"},
                access_token=line["meta_access_token"],
                pixel_id=line["meta_pixel_id"]
            )
            # Log the event
            await db.crm_leads.update_one(
                {"id": lead_id},
                {"$push": {
                    "meta_events_sent": {
                        "event": "Contact",
                        "timestamp": now,
                        "event_id": meta_result.get("event_id"),
                        "pixel_id": line.get("meta_pixel_id", "")[:8] + "..." if line.get("meta_pixel_id") else None,
                        "line": line.get("name"),
                        "success": meta_result.get("success", False)
                    }
                }}
            )
    
    message.pop("_id", None)
    return {
        "message": message,
        "whatsapp_sent": wa_result is not None and "error" not in wa_result,
        "whatsapp_result": wa_result,
        "contact_event_sent": meta_result is not None,
        "meta_result": meta_result
        }

# ─── CRM Send Image Message ────────────────────────────────────────

from fastapi import UploadFile, File, Form

@api_router.post("/crm/leads/{lead_id}/messages/image")
async def crm_send_image_message(
    lead_id: str,
    file: UploadFile = File(...),
    caption: str = Form(""),
    current_user=Depends(get_current_user)
):
    """Upload an image and send it via WhatsApp to the lead. Stores it in chat history."""
    lead = await db.crm_leads.find_one({"id": lead_id})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")

    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Tipo de archivo no permitido: {file.content_type}")

    if not lead.get("line_id") or not lead.get("phone"):
        raise HTTPException(status_code=400, detail="Lead sin línea o teléfono configurado")

    line = await db.crm_lines.find_one({"id": lead["line_id"]}, {"_id": 0})
    if not line or not line.get("whatsapp_token") or not line.get("phone_number_id"):
        raise HTTPException(status_code=400, detail="Línea sin credenciales de WhatsApp")

    # Read file bytes
    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:  # 10 MB limit (WA max ~5MB but leave margin)
        raise HTTPException(status_code=400, detail="Imagen muy grande (máx 10MB)")

    # Save locally for chat history preview
    os.makedirs("/app/backend/uploads/chat", exist_ok=True)
    file_ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "jpg"
    image_id = str(uuid.uuid4())
    file_name = f"{image_id}.{file_ext}"
    file_path = f"/app/backend/uploads/chat/{file_name}"
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # 1. Upload media to WhatsApp
    upload_res = await wa_upload_media(
        file_bytes=file_bytes,
        filename=file.filename or file_name,
        mime_type=file.content_type,
        token=line["whatsapp_token"],
        phone_id=line["phone_number_id"],
    )
    media_id = upload_res.get("id") if isinstance(upload_res, dict) else None
    if not media_id:
        logger.error(f"WA media upload failed for lead {lead_id}: {upload_res}")
        raise HTTPException(status_code=502, detail=f"Error subiendo imagen a WhatsApp: {upload_res}")

    # 2. Send image to the lead
    send_res = await wa_send_image(
        phone=lead["phone"],
        media_id=media_id,
        caption=caption or "",
        token=line["whatsapp_token"],
        phone_id=line["phone_number_id"],
    )
    whatsapp_ok = isinstance(send_res, dict) and "error" not in send_res and send_res.get("messages")

    # 3. Store message in chat history
    now = datetime.now(timezone.utc).isoformat()
    message = {
        "id": image_id,
        "lead_id": lead_id,
        "content": caption or "[Imagen]",
        "sender": "admin",
        "message_type": "image",
        "image_path": file_name,
        "caption": caption or "",
        "created_at": now,
        "wa_result": send_res,
    }
    await db.crm_messages.insert_one(message)
    await db.crm_leads.update_one(
        {"id": lead_id},
        {
            "$set": {"last_interaction": now, "updated_at": now},
            "$inc": {"messages_count": 1}
        }
    )

    message.pop("_id", None)
    return {
        "message": message,
        "whatsapp_sent": bool(whatsapp_ok),
        "whatsapp_result": send_res,
        "media_id": media_id,
    }


@api_router.get("/crm/chat-image/{filename}")
async def crm_get_chat_image(filename: str):
    """Serve a chat image uploaded by admin (public — UUID filenames are unguessable).

    Native <img src> cannot attach auth headers, so this endpoint must be public.
    """
    from fastapi.responses import FileResponse
    # Sanity: prevent path traversal
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Filename inválido")
    file_path = f"/app/backend/uploads/chat/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    mime = {"png": "image/png", "webp": "image/webp", "gif": "image/gif", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/jpeg")
    return FileResponse(file_path, media_type=mime)


@api_router.post("/crm/leads/{lead_id}/messages/audio")
async def crm_send_audio_message(
    lead_id: str,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    """Upload an audio (voice note) and send it via WhatsApp to the lead."""
    lead = await db.crm_leads.find_one({"id": lead_id})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    if not lead.get("line_id") or not lead.get("phone"):
        raise HTTPException(status_code=400, detail="Lead sin línea o teléfono configurado")

    line = await db.crm_lines.find_one({"id": lead["line_id"]}, {"_id": 0})
    if not line or not line.get("whatsapp_token") or not line.get("phone_number_id"):
        raise HTTPException(status_code=400, detail="Línea sin credenciales de WhatsApp")

    file_bytes = await file.read()
    if len(file_bytes) > 16 * 1024 * 1024:  # 16 MB WhatsApp limit for audio
        raise HTTPException(status_code=400, detail="Audio muy grande (máx 16MB)")

    # Accept common browser MIME types. Meta Cloud API accepts:
    # audio/aac, audio/mp4, audio/mpeg, audio/amr, audio/ogg (opus)
    # NOTE: Meta REJECTS webm container even if codec is opus, so we must
    # transcode webm → ogg/opus via ffmpeg. Android Chrome records webm.
    ctype = (file.content_type or "").lower()
    base = ctype.split(";")[0].strip()
    needs_transcode = base in ("audio/webm", "video/webm", "audio/x-matroska")

    ext_map = {
        "audio/ogg": ("ogg", "audio/ogg"),
        "audio/mpeg": ("mp3", "audio/mpeg"),
        "audio/mp3": ("mp3", "audio/mpeg"),
        "audio/mp4": ("m4a", "audio/mp4"),
        "audio/x-m4a": ("m4a", "audio/mp4"),
        "audio/aac": ("aac", "audio/aac"),
        "audio/amr": ("amr", "audio/amr"),
    }
    if needs_transcode:
        ext, meta_mime = ("ogg", "audio/ogg")
    elif base in ext_map:
        ext, meta_mime = ext_map[base]
    else:
        raise HTTPException(status_code=400, detail=f"Formato no soportado: {ctype}. Usa ogg/opus, mp3, m4a, aac o amr.")

    # Save locally for history (pre-transcode for fallback)
    os.makedirs("/app/backend/uploads/chat", exist_ok=True)
    audio_id = str(uuid.uuid4())
    file_name = f"{audio_id}.{ext}"
    file_path = f"/app/backend/uploads/chat/{file_name}"

    # Transcode webm → ogg/opus using ffmpeg (required by Meta)
    if needs_transcode:
        import subprocess
        import tempfile
        # Locate the ffmpeg binary. First try the one shipped via
        # imageio-ffmpeg (pip-installed, no apt required); fall back to
        # whatever is on $PATH.
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg_exe = "ffmpeg"
        try:
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_in:
                tmp_in.write(file_bytes)
                tmp_in_path = tmp_in.name
            proc = subprocess.run(
                [
                    ffmpeg_exe, "-y", "-i", tmp_in_path,
                    "-c:a", "libopus", "-b:a", "64k",
                    "-vn", "-f", "ogg",
                    file_path,
                ],
                capture_output=True, timeout=45,
            )
            os.unlink(tmp_in_path)
            if proc.returncode != 0:
                err = proc.stderr.decode(errors="ignore")[-500:]
                logger.error(f"ffmpeg audio transcode failed: {err}")
                raise HTTPException(status_code=502, detail=f"Error convirtiendo audio (ffmpeg): {err[:200]}")
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        except FileNotFoundError:
            raise HTTPException(status_code=500, detail="ffmpeg no está disponible. Reinstalá el container (pip install imageio-ffmpeg).")
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail="Conversión de audio tardó demasiado")
    else:
        with open(file_path, "wb") as f:
            f.write(file_bytes)

    # Upload to WhatsApp with the Meta-accepted MIME
    upload_res = await wa_upload_media(
        file_bytes=file_bytes,
        filename=file.filename or file_name,
        mime_type=meta_mime,
        token=line["whatsapp_token"],
        phone_id=line["phone_number_id"],
    )
    media_id = upload_res.get("id") if isinstance(upload_res, dict) else None
    if not media_id:
        logger.error(f"WA audio upload failed for lead {lead_id}: {upload_res}")
        raise HTTPException(status_code=502, detail=f"Error subiendo audio: {upload_res}")

    send_res = await wa_send_audio(
        phone=lead["phone"],
        media_id=media_id,
        token=line["whatsapp_token"],
        phone_id=line["phone_number_id"],
        as_voice=True,
    )
    whatsapp_ok = isinstance(send_res, dict) and "error" not in send_res and send_res.get("messages")

    now = datetime.now(timezone.utc).isoformat()
    message = {
        "id": audio_id,
        "lead_id": lead_id,
        "content": "[Audio]",
        "sender": "admin",
        "message_type": "audio",
        "audio_path": file_name,
        "audio_mime": meta_mime,
        "created_at": now,
        "wa_result": send_res,
    }
    await db.crm_messages.insert_one(message)
    await db.crm_leads.update_one(
        {"id": lead_id},
        {
            "$set": {"last_interaction": now, "updated_at": now},
            "$inc": {"messages_count": 1}
        }
    )
    message.pop("_id", None)
    return {
        "message": message,
        "whatsapp_sent": bool(whatsapp_ok),
        "whatsapp_result": send_res,
        "media_id": media_id,
    }


@api_router.get("/crm/chat-audio/{filename}")
async def crm_get_chat_audio(filename: str):
    """Serve a chat audio uploaded by admin.
    Public endpoint — filenames are UUIDs (unguessable). Native <audio src>
    cannot attach auth headers, so protecting this would break playback.
    """
    from fastapi.responses import FileResponse
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Filename inválido")
    file_path = f"/app/backend/uploads/chat/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio no encontrado")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "ogg"
    mime = {"ogg": "audio/ogg", "mp3": "audio/mpeg", "m4a": "audio/mp4", "aac": "audio/aac", "amr": "audio/amr"}.get(ext, "audio/ogg")
    return FileResponse(file_path, media_type=mime)


# ─── CRM Receipts Routes ───────────────────────────────────────────

@api_router.post("/crm/leads/{lead_id}/receipts")
async def crm_upload_receipt(
    lead_id: str,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    """Upload a payment receipt image for manual review"""
    lead = await db.crm_leads.find_one({"id": lead_id})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Solo se permiten imágenes (JPEG, PNG, WebP)")
    
    # Save file
    receipt_id = str(uuid.uuid4())
    file_ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    file_name = f"{receipt_id}.{file_ext}"
    file_path = f"/app/backend/uploads/receipts/{file_name}"
    
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    now = datetime.now(timezone.utc).isoformat()
    
    receipt = {
        "id": receipt_id,
        "lead_id": lead_id,
        "file_name": file_name,
        "file_path": file_path,
        "original_name": file.filename,
        "content_type": file.content_type,
        "status": "pending",  # pending, approved, rejected
        "amount": None,
        "currency": None,
        "admin_notes": "",
        "reviewed_by": None,
        "created_at": now,
        "validated_at": None,
    }
    
    await db.crm_receipts.insert_one(receipt)
    
    # Update lead's receipt count
    await db.crm_leads.update_one(
        {"id": lead_id},
        {
            "$inc": {"receipts_count": 1},
            "$set": {"updated_at": now}
        }
    )
    
    receipt.pop("_id", None)
    return receipt

@api_router.get("/crm/leads/{lead_id}/receipts")
async def crm_get_lead_receipts(lead_id: str, current_user=Depends(get_current_user)):
    """Get all receipts for a lead"""
    lead = await db.crm_leads.find_one({"id": lead_id})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    receipts = await db.crm_receipts.find(
        {"lead_id": lead_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return receipts

@api_router.get("/crm/receipts/{receipt_id}/image")
async def crm_get_receipt_image(receipt_id: str, current_user=Depends(get_current_user)):
    """Get receipt image file"""
    from fastapi.responses import FileResponse
    
    receipt = await db.crm_receipts.find_one({"id": receipt_id})
    if not receipt:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
    
    file_path = receipt.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    return FileResponse(file_path, media_type=receipt.get("content_type", "image/jpeg"))

@api_router.put("/crm/receipts/{receipt_id}/validate")
async def crm_validate_receipt(
    receipt_id: str,
    data: CRMReceiptValidation,
    current_user=Depends(get_current_user)
):
    """Manually validate or reject a receipt"""
    receipt = await db.crm_receipts.find_one({"id": receipt_id})
    if not receipt:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado")
    
    if data.status not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Status debe ser 'approved' o 'rejected'")
    
    now = datetime.now(timezone.utc).isoformat()
    
    update_data = {
        "status": data.status,
        "amount": data.amount,
        "currency": data.currency,
        "admin_notes": data.admin_notes or "",
        "reviewed_by": current_user.get("email"),
        "validated_at": now,
    }
    
    await db.crm_receipts.update_one({"id": receipt_id}, {"$set": update_data})
    
    # If approved, optionally update lead status to cliente_real
    if data.status == "approved":
        await db.crm_leads.update_one(
            {"id": receipt["lead_id"]},
            {"$set": {
                "status": "cliente_real",
                "score": 100,
                "updated_at": now
            }}
        )
    
    updated = await db.crm_receipts.find_one({"id": receipt_id}, {"_id": 0})
    return updated

# ─── CRM Dashboard Routes ──────────────────────────────────────────

@api_router.get("/crm/dashboard/stats")
async def crm_dashboard_stats(current_user=Depends(get_current_user)):
    """Get CRM dashboard statistics"""
    total_leads = await db.crm_leads.count_documents({})
    
    # Count by status
    status_counts = {}
    for status in CRM_LEAD_STATUSES:
        status_counts[status] = await db.crm_leads.count_documents({"status": status})
    
    # Valid leads (interesado + potencial + cliente_real)
    valid_leads = status_counts.get("interesado", 0) + status_counts.get("potencial", 0) + status_counts.get("cliente_real", 0)
    
    # Discarded leads (basura)
    discarded_leads = status_counts.get("basura", 0)
    
    # Real conversions (only cliente_real)
    conversions = status_counts.get("cliente_real", 0)
    
    # Quality percentage
    quality_percentage = round((valid_leads / total_leads * 100), 1) if total_leads > 0 else 0
    
    # Top 10 leads by score
    top_leads = await db.crm_leads.find(
        {}, {"_id": 0, "id": 1, "name": 1, "phone": 1, "score": 1, "status": 1}
    ).sort("score", -1).limit(10).to_list(10)
    
    # Recent leads
    recent_leads = await db.crm_leads.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    # Pending receipts
    pending_receipts = await db.crm_receipts.count_documents({"status": "pending"})
    
    return {
        "total_leads": total_leads,
        "by_status": status_counts,
        "valid_leads": valid_leads,
        "discarded_leads": discarded_leads,
        "conversions": conversions,
        "quality_percentage": quality_percentage,
        "top_leads": top_leads,
        "recent_leads": recent_leads,
        "pending_receipts": pending_receipts,
    }

@api_router.get("/crm/dashboard/trends")
async def crm_dashboard_trends(
    days: int = Query(30, ge=1, le=90),
    current_user=Depends(get_current_user)
):
    """Get leads trend by day"""
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    pipeline = [
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$addFields": {"date_str": {"$substr": ["$created_at", 0, 10]}}},
        {"$group": {
            "_id": "$date_str",
            "total": {"$sum": 1},
            "cliente_real": {"$sum": {"$cond": [{"$eq": ["$status", "cliente_real"]}, 1, 0]}},
            "basura": {"$sum": {"$cond": [{"$eq": ["$status", "basura"]}, 1, 0]}},
        }},
        {"$sort": {"_id": 1}},
    ]
    
    trends = []
    async for r in db.crm_leads.aggregate(pipeline):
        trends.append({
            "date": r["_id"],
            "total": r["total"],
            "conversions": r["cliente_real"],
            "discarded": r["basura"],
        })
    
    return {"trends": trends, "period": f"Últimos {days} días"}

@api_router.get("/crm/dashboard/by-source")
async def crm_leads_by_source(current_user=Depends(get_current_user)):
    """Get leads grouped by source"""
    pipeline = [
        {"$group": {
            "_id": "$source",
            "count": {"$sum": 1},
            "conversions": {"$sum": {"$cond": [{"$eq": ["$status", "cliente_real"]}, 1, 0]}},
        }},
        {"$sort": {"count": -1}},
    ]
    
    sources = []
    async for r in db.crm_leads.aggregate(pipeline):
        sources.append({
            "source": r["_id"] or "unknown",
            "count": r["count"],
            "conversions": r["conversions"],
        })
    
    return sources

# ─── CRM Meta Integration Routes ───────────────────────────────────

@api_router.post("/crm/leads/{lead_id}/send-conversion")
async def crm_send_conversion_to_meta(
    lead_id: str,
    value: float = Query(0, description="Conversion value"),
    currency: str = Query("USD", description="Currency code"),
    current_user=Depends(get_current_user)
):
    """
    Manually send a conversion event to Meta for this lead.
    Only works if lead is 'cliente_real'.
    Uses the line's Meta credentials (not global env vars).
    """
    lead = await db.crm_leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    if lead.get("status") != "valido":
        raise HTTPException(
            status_code=400,
            detail="Solo se pueden enviar conversiones para leads con status 'valido'"
        )
    
    # Get the line's Meta credentials
    line_id = lead.get("line_id")
    if not line_id:
        raise HTTPException(status_code=400, detail="Lead no tiene línea asignada")
    
    line = await db.crm_lines.find_one({"id": line_id}, {"_id": 0})
    if not line:
        raise HTTPException(status_code=400, detail="Línea no encontrada")
    
    access_token = line.get("meta_access_token")
    pixel_id = line.get("meta_pixel_id")
    
    if not access_token or not pixel_id:
        raise HTTPException(
            status_code=400,
            detail=f"La línea '{line.get('name', 'N/A')}' no tiene configurado Meta Pixel. Configura meta_access_token y meta_pixel_id en la línea."
        )
    
    purchase_value = float(value) if value else 0.0
    # Currency from deployment-wide env var (USD or ARS)
    purchase_currency = PURCHASE_CURRENCY
    custom_data = {
        "currency": purchase_currency,
        "value": purchase_value,
        "content_type": "product",
    }
    
    logger.info(f"Manual Purchase event for lead {lead_id}: value={purchase_value}, currency={purchase_currency}")
    
    result = await send_meta_conversion_event(
        event_name="Purchase",
        lead_data=lead,
        custom_data=custom_data,
        access_token=access_token,
        pixel_id=pixel_id
    )
    
    # Log the event
    now = datetime.now(timezone.utc).isoformat()
    await db.crm_leads.update_one(
        {"id": lead_id},
        {"$push": {
            "meta_events_sent": {
                "event": "Purchase",
                "timestamp": now,
                "value": purchase_value,
                "currency": purchase_currency,
                "event_id": result.get("event_id"),
                "line": line.get("name"),
                "success": result.get("success", False)
            }
        }}
    )
    
    return result

@api_router.get("/crm/meta/status")
async def crm_meta_integration_status(current_user=Depends(get_current_user)):
    """Check Meta Conversions API configuration status for all lines"""
    lines = await db.crm_lines.find({}, {"_id": 0, "id": 1, "name": 1, "meta_access_token": 1, "meta_pixel_id": 1}).to_list(100)
    
    lines_status = []
    for line in lines:
        has_token = bool(line.get("meta_access_token"))
        has_pixel = bool(line.get("meta_pixel_id"))
        lines_status.append({
            "line_id": line["id"],
            "line_name": line.get("name", "N/A"),
            "configured": has_token and has_pixel,
            "has_token": has_token,
            "has_pixel_id": has_pixel,
            "pixel_id_preview": line.get("meta_pixel_id", "")[:8] + "..." if line.get("meta_pixel_id") else None,
        })
    
    return {
        "lines": lines_status,
        "total_configured": sum(1 for l in lines_status if l["configured"]),
        "total_lines": len(lines_status),
    }


@api_router.get("/crm/meta/diagnostics")
async def crm_meta_diagnostics(
    limit: int = Query(500, ge=1, le=5000),
    line_id: str = Query(None),
    event_type: str = Query(None),
    current_user=Depends(get_current_user)
):
    """
    Full Meta CAPI diagnostics panel.
    Returns recent events, success rates, and line configuration.
    """
    # 1. Lines config
    lines = await db.crm_lines.find({}, {"_id": 0}).to_list(100)
    lines_map = {l["id"]: l for l in lines}
    lines_config = []
    for line in lines:
        has_token = bool(line.get("meta_access_token"))
        has_pixel = bool(line.get("meta_pixel_id"))
        lines_config.append({
            "line_id": line["id"],
            "line_name": line.get("name", "N/A"),
            "configured": has_token and has_pixel,
            "has_token": has_token,
            "has_pixel_id": has_pixel,
            "pixel_id_preview": line.get("meta_pixel_id", "")[:12] + "..." if line.get("meta_pixel_id") else None,
            "token_preview": line.get("meta_access_token", "")[:12] + "..." if line.get("meta_access_token") else None,
        })

    # 2. Read from centralized meta_events_log (captures ALL events including landing Lead/Contact)
    log_query = {}
    if line_id:
        log_query["line_id"] = line_id
    if event_type:
        log_query["event_name"] = event_type

    event_logs = await db.meta_events_log.find(
        log_query, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)

    all_events = []
    for ev in event_logs:
        all_events.append({
            "lead_id": ev.get("lead_id", ""),
            "lead_name": ev.get("lead_name", ""),
            "lead_phone": ev.get("lead_phone", ""),
            "lead_status": "",
            "line_id": ev.get("line_id", ""),
            "line_name": lines_map.get(ev.get("line_id", ""), {}).get("name", ""),
            "event": ev.get("event_name", ""),
            "timestamp": ev.get("created_at", ""),
            "value": ev.get("value"),
            "currency": ev.get("currency", ""),
            "event_id": ev.get("event_id"),
            "success": ev.get("success", False),
            "pixel_id": ev.get("pixel_id", ""),
            "has_fbp": ev.get("has_fbp", False),
            "has_fbc": ev.get("has_fbc", False),
            "has_phone": ev.get("has_phone", False),
            "landing_code": ev.get("landing_code"),
            "ctwa_clid": ev.get("ctwa_clid"),
            "ad_source": ev.get("ad_source"),
            "utm_content": ev.get("utm_content"),
            "source": ev.get("source", ""),
        })

    # Sort by timestamp desc
    all_events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    all_events = all_events[:limit]

    # 3. Stats — calculated from ALL events in DB, not just the limited page
    stats_query = {}
    if line_id:
        stats_query["line_id"] = line_id
    if event_type:
        stats_query["event_name"] = event_type

    total_events = await db.meta_events_log.count_documents(stats_query)
    success_count = await db.meta_events_log.count_documents({**stats_query, "success": True})
    fail_count = total_events - success_count

    # Total purchase value from ALL purchase events
    purchase_agg = await db.meta_events_log.aggregate([
        {"$match": {**stats_query, "event_name": "Purchase", "value": {"$gt": 0}}},
        {"$group": {"_id": None, "total": {"$sum": "$value"}}}
    ]).to_list(1)
    total_value = round(purchase_agg[0]["total"], 2) if purchase_agg else 0

    # Event type counts from ALL events
    type_agg = await db.meta_events_log.aggregate([
        {"$match": stats_query},
        {"$group": {"_id": "$event_name", "count": {"$sum": 1}}}
    ]).to_list(50)
    event_type_counts = {r["_id"]: r["count"] for r in type_agg if r["_id"]}

    return {
        "lines_config": lines_config,
        "total_configured_lines": sum(1 for l in lines_config if l["configured"]),
        "total_lines": len(lines_config),
        "events": all_events,
        "stats": {
            "total_events": total_events,
            "success": success_count,
            "failed": fail_count,
            "success_rate": round((success_count / total_events * 100), 1) if total_events else 0,
            "total_purchase_value": round(total_value, 2),
            "event_type_counts": event_type_counts,
        }
    }



# ─── Event Match Quality (EMQ) Dashboard ───────────────────────────

# Meta's approximate weighting for matching parameters
EMQ_WEIGHTS = {
    "fbp": 15, "fbc": 15,          # Facebook cookies — highest value
    "ph": 12,                        # Phone
    "em": 12,                        # Email
    "fb_login_id": 10,              # Facebook Login ID
    "client_ip_address": 8,         # IP address
    "client_user_agent": 5,         # User agent
    "fn": 5, "ln": 5,              # First/last name
    "external_id": 4,              # External ID
    "ct": 3, "st": 3, "zp": 3,    # City, state, zip
    "country": 2,                   # Country
    "ge": 2, "db": 2,             # Gender, DOB
}
EMQ_MAX_SCORE = sum(EMQ_WEIGHTS.values())  # 106

def calculate_emq_score(user_data_keys: list) -> dict:
    """Calculate estimated Event Match Quality score from user_data_keys"""
    score = sum(EMQ_WEIGHTS.get(k, 0) for k in user_data_keys)
    pct = round((score / EMQ_MAX_SCORE) * 100) if EMQ_MAX_SCORE > 0 else 0
    if pct >= 80:
        quality = "Excelente"
    elif pct >= 60:
        quality = "Buena"
    elif pct >= 40:
        quality = "Normal"
    else:
        quality = "Baja"
    missing = [k for k, w in sorted(EMQ_WEIGHTS.items(), key=lambda x: -x[1]) if k not in user_data_keys]
    return {"score": pct, "quality": quality, "params_sent": len(user_data_keys), "missing_params": missing[:5]}

@api_router.get("/crm/emq/dashboard")
async def crm_emq_dashboard(
    days: int = Query(30, ge=1, le=90),
    line_id: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    """Event Match Quality dashboard — shows matching quality for Meta CAPI events"""
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    query = {"created_at": {"$gte": date_from}}
    if line_id:
        query["line_id"] = line_id

    # Overall stats
    total_events = await db.meta_events_log.count_documents(query)
    success_events = await db.meta_events_log.count_documents({**query, "success": True})

    # Aggregate by event type
    type_pipeline = [
        {"$match": query},
        {"$group": {
            "_id": "$event_name",
            "count": {"$sum": 1},
            "success": {"$sum": {"$cond": [{"$eq": ["$success", True]}, 1, 0]}},
            "avg_params": {"$avg": "$matching_params_count"},
            "with_fbp": {"$sum": {"$cond": [{"$eq": ["$has_fbp", True]}, 1, 0]}},
            "with_fbc": {"$sum": {"$cond": [{"$eq": ["$has_fbc", True]}, 1, 0]}},
            "with_phone": {"$sum": {"$cond": [{"$eq": ["$has_phone", True]}, 1, 0]}},
            "with_email": {"$sum": {"$cond": [{"$eq": ["$has_email", True]}, 1, 0]}},
        }},
        {"$sort": {"count": -1}},
    ]
    by_type = []
    async for r in db.meta_events_log.aggregate(type_pipeline):
        total = r["count"]
        by_type.append({
            "event": r["_id"],
            "count": total,
            "success": r["success"],
            "success_rate": round(r["success"] / total * 100) if total > 0 else 0,
            "avg_params": round(r["avg_params"] or 0, 1),
            "fbp_rate": round(r["with_fbp"] / total * 100) if total > 0 else 0,
            "fbc_rate": round(r["with_fbc"] / total * 100) if total > 0 else 0,
            "phone_rate": round(r["with_phone"] / total * 100) if total > 0 else 0,
            "email_rate": round(r["with_email"] / total * 100) if total > 0 else 0,
        })

    # Recent events with EMQ score
    recent = await db.meta_events_log.find(query, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)
    recent_with_emq = []
    for ev in recent:
        emq = calculate_emq_score(ev.get("user_data_keys", []))
        recent_with_emq.append({
            "event": ev.get("event_name"),
            "lead_name": ev.get("lead_name"),
            "lead_phone": ev.get("lead_phone"),
            "success": ev.get("success"),
            "emq_score": emq["score"],
            "emq_quality": emq["quality"],
            "params_sent": emq["params_sent"],
            "missing": emq["missing_params"],
            "value": ev.get("value"),
            "currency": ev.get("currency"),
            "created_at": ev.get("created_at"),
        })

    # Average EMQ across all events
    all_keys_pipeline = [
        {"$match": query},
        {"$project": {"user_data_keys": 1}},
    ]
    all_scores = []
    async for ev in db.meta_events_log.aggregate(all_keys_pipeline):
        keys = ev.get("user_data_keys", [])
        if keys:
            emq = calculate_emq_score(keys)
            all_scores.append(emq["score"])
    avg_emq = round(sum(all_scores) / len(all_scores)) if all_scores else 0

    return {
        "period_days": days,
        "total_events": total_events,
        "success_events": success_events,
        "success_rate": round(success_events / total_events * 100) if total_events > 0 else 0,
        "avg_emq_score": avg_emq,
        "avg_emq_quality": "Excelente" if avg_emq >= 80 else "Buena" if avg_emq >= 60 else "Normal" if avg_emq >= 40 else "Baja",
        "by_event_type": by_type,
        "recent_events": recent_with_emq,
    }


@api_router.get("/crm/emq/by-line")
async def crm_emq_by_line(
    days: int = Query(7, ge=1, le=90),
    current_user=Depends(get_current_user)
):
    """
    EMQ Score breakdown by Meta line.
    Returns, for each line that fired any CAPI event in the last N days:
      - tier counts based on raw matching params count: 12+, 10-11, 8-9, <8
      - avg params, avg EMQ %, success rate
      - top 3 missing high-value parameters (so cajero/admin sees WHAT to fix)
      - per-event-type counts (Lead/Contact/Purchase) for context

    This is the metric Meta uses to rank Pixel quality. The frontend renders
    a colored bar (green/blue/amber/red) per line so a missing-fbp landing
    is visible at a glance.
    """
    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Build a {line_id: name} map for friendly labels
    line_docs = await db.crm_lines.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
    line_names = {ln["id"]: ln.get("name") or ln["id"] for ln in line_docs}

    # Aggregate per line
    cursor = db.meta_events_log.aggregate([
        {"$match": {"created_at": {"$gte": date_from}}},
        {"$group": {
            "_id": "$line_id",
            "total": {"$sum": 1},
            "success": {"$sum": {"$cond": [{"$eq": ["$success", True]}, 1, 0]}},
            "sum_params": {"$sum": "$matching_params_count"},
            "tier_excellent": {"$sum": {"$cond": [{"$gte": ["$matching_params_count", 12]}, 1, 0]}},
            "tier_good":      {"$sum": {"$cond": [{"$and": [{"$gte": ["$matching_params_count", 10]}, {"$lte": ["$matching_params_count", 11]}]}, 1, 0]}},
            "tier_normal":    {"$sum": {"$cond": [{"$and": [{"$gte": ["$matching_params_count", 8]},  {"$lte": ["$matching_params_count", 9]}]}, 1, 0]}},
            "tier_low":       {"$sum": {"$cond": [{"$lt":  ["$matching_params_count", 8]}, 1, 0]}},
            "with_fbp": {"$sum": {"$cond": [{"$eq": ["$has_fbp", True]}, 1, 0]}},
            "with_fbc": {"$sum": {"$cond": [{"$eq": ["$has_fbc", True]}, 1, 0]}},
            "with_email": {"$sum": {"$cond": [{"$eq": ["$has_email", True]}, 1, 0]}},
            "purchase_count": {"$sum": {"$cond": [{"$eq": ["$event_name", "Purchase"]}, 1, 0]}},
            "lead_count":     {"$sum": {"$cond": [{"$eq": ["$event_name", "Lead"]}, 1, 0]}},
            "contact_count":  {"$sum": {"$cond": [{"$eq": ["$event_name", "Contact"]}, 1, 0]}},
        }},
        {"$sort": {"total": -1}},
    ])

    rows = []
    grand_total = 0
    grand_excellent = 0
    grand_good = 0
    grand_normal = 0
    grand_low = 0
    grand_params = 0
    grand_success = 0
    async for r in cursor:
        total = r["total"] or 0
        if total == 0:
            continue
        # Compute weighted EMQ % per line by sampling user_data_keys
        keys_sample = await db.meta_events_log.find(
            {"created_at": {"$gte": date_from}, "line_id": r["_id"]},
            {"_id": 0, "user_data_keys": 1}
        ).limit(200).to_list(200)
        emq_scores = []
        missing_counter = {}
        for ev in keys_sample:
            ks = ev.get("user_data_keys") or []
            if not ks:
                continue
            emq = calculate_emq_score(ks)
            emq_scores.append(emq["score"])
            for m in emq["missing_params"]:
                missing_counter[m] = missing_counter.get(m, 0) + 1
        avg_emq = round(sum(emq_scores) / len(emq_scores)) if emq_scores else 0
        top_missing = sorted(missing_counter.items(), key=lambda x: -x[1])[:3]

        rows.append({
            "line_id": r["_id"],
            "line_name": line_names.get(r["_id"], "Sin línea"),
            "total": total,
            "success_rate": round(r["success"] / total * 100) if total else 0,
            "avg_params": round(r["sum_params"] / total, 1) if total else 0,
            "avg_emq_score": avg_emq,
            "tiers": {
                "excellent": r["tier_excellent"],   # 12+
                "good":      r["tier_good"],        # 10-11
                "normal":    r["tier_normal"],      # 8-9
                "low":       r["tier_low"],         # <8
            },
            "tier_pct": {
                "excellent": round(r["tier_excellent"] / total * 100, 1),
                "good":      round(r["tier_good"] / total * 100, 1),
                "normal":    round(r["tier_normal"] / total * 100, 1),
                "low":       round(r["tier_low"] / total * 100, 1),
            },
            "signals": {
                "fbp_rate":   round(r["with_fbp"] / total * 100),
                "fbc_rate":   round(r["with_fbc"] / total * 100),
                "email_rate": round(r["with_email"] / total * 100),
            },
            "events": {
                "Purchase": r["purchase_count"],
                "Lead":     r["lead_count"],
                "Contact":  r["contact_count"],
            },
            "top_missing": [m for m, _c in top_missing],
        })
        grand_total += total
        grand_excellent += r["tier_excellent"]
        grand_good += r["tier_good"]
        grand_normal += r["tier_normal"]
        grand_low += r["tier_low"]
        grand_params += r["sum_params"]
        grand_success += r["success"]

    return {
        "period_days": days,
        "lines": rows,
        "totals": {
            "total": grand_total,
            "success_rate": round(grand_success / grand_total * 100) if grand_total else 0,
            "avg_params": round(grand_params / grand_total, 1) if grand_total else 0,
            "tiers": {
                "excellent": grand_excellent,
                "good": grand_good,
                "normal": grand_normal,
                "low": grand_low,
            },
            "tier_pct": {
                "excellent": round(grand_excellent / grand_total * 100, 1) if grand_total else 0,
                "good":      round(grand_good / grand_total * 100, 1) if grand_total else 0,
                "normal":    round(grand_normal / grand_total * 100, 1) if grand_total else 0,
                "low":       round(grand_low / grand_total * 100, 1) if grand_total else 0,
            },
        },
    }


# ─── Web Push Notifications (VAPID) ────────────────────────────────
# Keeps cajero notified even when Chrome is closed (works via background service worker)

from pywebpush import webpush, WebPushException
from py_vapid import Vapid

_vapid_cache = {"public": None, "private_pem": None, "subject": None, "vapid_obj": None}

async def get_vapid_keys():
    """Get VAPID keys from MongoDB settings (persists across restarts).
    Generates on first call if not present."""
    if _vapid_cache["public"] and _vapid_cache["vapid_obj"]:
        return _vapid_cache
    # 1. Try env first
    env_pub = os.environ.get("VAPID_PUBLIC_KEY")
    env_priv = os.environ.get("VAPID_PRIVATE_PEM")
    env_subj = os.environ.get("VAPID_SUBJECT", "mailto:admin@crm.local")
    doc = None
    if env_pub and env_priv:
        _vapid_cache.update({"public": env_pub, "private_pem": env_priv, "subject": env_subj})
    else:
        # 2. Try DB
        doc = await db.settings.find_one({"key": "vapid_keys"})
        if doc:
            _vapid_cache.update({
                "public": doc["public"],
                "private_pem": doc["private_pem"],
                "subject": doc.get("subject", env_subj),
            })
        else:
            # 3. Generate once and persist
            from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
            v = Vapid()
            v.generate_keys()
            priv_pem = v.private_pem().decode()
            pub_bytes = v.public_key.public_bytes(
                encoding=Encoding.X962, format=PublicFormat.UncompressedPoint
            )
            pub_b64 = base64.urlsafe_b64encode(pub_bytes).decode().rstrip("=")
            await db.settings.insert_one({
                "key": "vapid_keys",
                "public": pub_b64,
                "private_pem": priv_pem,
                "subject": env_subj,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            _vapid_cache.update({"public": pub_b64, "private_pem": priv_pem, "subject": env_subj})
            logger.info("Generated and persisted new VAPID keys")

    # Build the Vapid object from the PEM so pywebpush 2.x accepts it
    # (pywebpush 2.x no longer accepts raw PEM strings — needs a Vapid instance)
    try:
        vapid_obj = Vapid.from_pem(_vapid_cache["private_pem"].encode())
        _vapid_cache["vapid_obj"] = vapid_obj
    except Exception as e:
        logger.error(f"Failed to build Vapid object from PEM: {e}")
        _vapid_cache["vapid_obj"] = None
    return _vapid_cache


@api_router.get("/push/vapid-public-key")
async def push_get_vapid_public_key(current_user=Depends(get_current_user)):
    """Return VAPID public key so the frontend can subscribe to push."""
    keys = await get_vapid_keys()
    return {"public_key": keys["public"]}


class PushSubscriptionPayload(BaseModel):
    endpoint: str
    keys: Dict[str, str]  # {p256dh, auth}
    user_agent: Optional[str] = ""


@api_router.post("/push/subscribe")
async def push_subscribe(data: PushSubscriptionPayload, current_user=Depends(get_current_user)):
    """Register/update a push subscription for the current user (one per browser)."""
    now = datetime.now(timezone.utc).isoformat()
    sub_doc = {
        "user_id": current_user["id"],
        "user_email": current_user.get("email"),
        "endpoint": data.endpoint,
        "keys": data.keys,
        "user_agent": (data.user_agent or "")[:200],
        "updated_at": now,
    }
    # Upsert by endpoint (each browser = unique endpoint)
    existing = await db.push_subscriptions.find_one({"endpoint": data.endpoint})
    if existing:
        await db.push_subscriptions.update_one(
            {"endpoint": data.endpoint},
            {"$set": sub_doc}
        )
    else:
        sub_doc["created_at"] = now
        await db.push_subscriptions.insert_one(sub_doc)
    logger.info(f"Push subscribed: user={current_user.get('email')} endpoint=...{data.endpoint[-20:]}")
    return {"ok": True}


@api_router.post("/push/unsubscribe")
async def push_unsubscribe(data: PushSubscriptionPayload, current_user=Depends(get_current_user)):
    """Remove a push subscription."""
    await db.push_subscriptions.delete_one({
        "user_id": current_user["id"],
        "endpoint": data.endpoint
    })
    return {"ok": True}


async def send_web_push(user_id: str, title: str, body: str, data: dict = None):
    """Send a push notification to ALL browsers where user_id has subscribed."""
    try:
        keys = await get_vapid_keys()
        vapid_obj = keys.get("vapid_obj")
        if not vapid_obj:
            logger.warning("Web push skipped: VAPID object not available")
            return {"sent": 0, "failed": 0, "gone": 0}
        payload = {
            "title": title,
            "body": body,
            "data": data or {},
        }
        payload_json = json.dumps(payload)
        vapid_claims = {"sub": keys["subject"]}
        sent, failed, gone = 0, 0, 0
        async for sub in db.push_subscriptions.find({"user_id": user_id}):
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub["endpoint"],
                        "keys": sub["keys"],
                    },
                    data=payload_json,
                    vapid_private_key=vapid_obj,  # pywebpush 2.x expects a Vapid instance
                    vapid_claims=vapid_claims,
                    ttl=60,  # seconds
                )
                sent += 1
            except WebPushException as e:
                # 404/410 = subscription expired, remove it.
                # pywebpush 2.x sometimes leaves `e.response` without a
                # parseable status_code, so we also check the exception
                # message text (contains "Push failed: 410 Gone" or similar).
                status = None
                resp = getattr(e, "response", None)
                if resp is not None:
                    status = getattr(resp, "status_code", None) or getattr(resp, "status", None)
                if status is None:
                    msg = str(e)
                    import re as _re
                    m = _re.search(r"Push failed:\s*(\d{3})", msg)
                    if m:
                        try:
                            status = int(m.group(1))
                        except ValueError:
                            status = None
                if status in (404, 410):
                    await db.push_subscriptions.delete_one({"endpoint": sub["endpoint"]})
                    gone += 1
                else:
                    failed += 1
                    logger.warning(f"Web push failed ({status}): {e}")
            except Exception as e:
                failed += 1
                logger.warning(f"Web push error: {e}")
        if sent or failed or gone:
            logger.info(f"Web push sent to {user_id}: sent={sent}, failed={failed}, gone={gone}")
        return {"sent": sent, "failed": failed, "gone": gone}
    except Exception as e:
        logger.error(f"send_web_push fatal: {e}")
        return {"sent": 0, "failed": 1, "gone": 0}


async def notify_line_cajeros_of_new_message(crm_lead: dict, line: dict, message_preview: str = ""):
    """Send web push to every cajero assigned to this line."""
    try:
        line_id = line.get("id")
        if not line_id:
            return
        # Find cajeros assigned to this line
        cajero_ids = []
        async for user in db.users.find({"line_ids": line_id, "is_active": True}, {"id": 1}):
            cajero_ids.append(user.get("id"))
        if not cajero_ids:
            return
        title = crm_lead.get("name") or crm_lead.get("phone") or "Nuevo mensaje"
        body_parts = []
        if line.get("name"):
            body_parts.append(f"📱 {line['name']}")
        if message_preview:
            preview = message_preview[:80] + ("…" if len(message_preview) > 80 else "")
            body_parts.append(preview)
        else:
            body_parts.append("Nuevo mensaje")
        body = " · ".join(body_parts)
        data = {
            "lead_id": crm_lead.get("id"),
            "lead_name": crm_lead.get("name"),
            "phone": crm_lead.get("phone"),
            "line_id": line_id,
            "url": "/leads",
        }
        for uid in cajero_ids:
            await send_web_push(uid, title, body, data)
    except Exception as e:
        logger.error(f"notify_line_cajeros_of_new_message error: {e}")


# ─── CRM Broadcast (Bulk Messaging with Anti-Spam) ─────────────────

class BroadcastCreate(BaseModel):
    line_id: str
    target_status: List[str] = ["valido"]
    message: str
    image_path: Optional[str] = None  # local filename from prior upload (optional)
    audio_path: Optional[str] = None  # local filename from prior upload (optional)
    audio_as_voice: bool = True  # send as PTT/voice note (Meta only PTTs ogg/opus)
    min_delay_sec: int = 4
    max_delay_sec: int = 10
    max_per_hour: int = 300

_broadcast_workers: Dict[str, "asyncio.Task"] = {}


# ════════════════════════════════════════════════════════════════════
# FINANZAS (Cajero) — Bono, Ingresos, Egresos, Balance
# ════════════════════════════════════════════════════════════════════
# Cada cajero gestiona su propia caja: ve cuánto ingresó (sacado del
# embudo: leads "valido"), cuánto egresó (carga manual), cuánto bono
# entregó (% configurable, versionado por fecha para que cambios no
# alteren históricos) y su balance.

class FinanzasBonusRateUpdate(BaseModel):
    percentage: float  # 0..100
    apply_retroactive: bool = False  # si True, aplica a TODO el histórico (borra versiones previas)


class FinanzasExpenseCreate(BaseModel):
    amount: float
    observation: str


class FinanzasExpenseUpdate(BaseModel):
    amount: float
    observation: str


def _today_utc_iso_date() -> str:
    """YYYY-MM-DD del día actual UTC."""
    return datetime.now(timezone.utc).date().isoformat()


async def _finanzas_get_bonus_rate_for_date(user_id: str, date_iso: str) -> float:
    """Busca el % de bono vigente para `user_id` en `date_iso` (YYYY-MM-DD).
    Si no hay nada configurado, retorna 0."""
    doc = await db.cajero_bonus_rates.find_one(
        {
            "user_id": user_id,
            "effective_from": {"$lte": date_iso},
            "$or": [{"effective_to": None}, {"effective_to": {"$gt": date_iso}}],
        },
        {"_id": 0, "percentage": 1},
    )
    return float(doc["percentage"]) if doc else 0.0


async def _finanzas_get_current_bonus_rate(user_id: str) -> float:
    today = _today_utc_iso_date()
    return await _finanzas_get_bonus_rate_for_date(user_id, today)


def _finanzas_resolve_date_range(
    filter_type: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
) -> tuple:
    """Resuelve un rango de fechas YYYY-MM-DD (inclusive) según el filtro.
    Usa timezone Argentina (UTC-3) para que coincida con el embudo de conversión."""
    AR_OFFSET = timedelta(hours=-3)
    today = (datetime.now(timezone.utc) + AR_OFFSET).date()
    if filter_type == "custom" and start_date and end_date:
        return start_date, end_date
    if filter_type == "diario":
        return today.isoformat(), today.isoformat()
    if filter_type == "ayer":
        y = today - timedelta(days=1)
        return y.isoformat(), y.isoformat()
    if filter_type == "ultimos_10":
        return (today - timedelta(days=9)).isoformat(), today.isoformat()
    if filter_type == "semanal":
        return (today - timedelta(days=6)).isoformat(), today.isoformat()
    if filter_type == "mensual":
        return today.replace(day=1).isoformat(), today.isoformat()
    if filter_type == "mes_anterior":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        return first_prev.isoformat(), last_prev.isoformat()
    # default: mes actual
    return today.replace(day=1).isoformat(), today.isoformat()


async def _finanzas_ingresos_by_day(user_id: str, start_iso: str, end_iso: str) -> Dict[str, float]:
    """Suma de charge_amount por día (YYYY-MM-DD) de leads marcados como `valido`
    asignados a este cajero. Si el cajero tiene `line_ids`, filtra por esas líneas.
    NOTA: usa `charge_amount` + `created_at` igual que el embudo de conversión
    (`/api/crm/funnel/stats`) para mantener consistencia con lo que el cajero ve."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "line_ids": 1, "role": 1})
    line_filter: Dict = {}
    if user and user.get("role") not in ("admin", "superadmin"):
        line_ids = user.get("line_ids") or []
        if line_ids:
            line_filter = {"line_id": {"$in": line_ids}}
        else:
            return {}  # cajero sin líneas asignadas → sin ingresos
    start_dt = f"{start_iso}T00:00:00"
    end_dt = f"{end_iso}T23:59:59.999"
    query = {
        **line_filter,
        "status": "valido",
        "created_at": {"$gte": start_dt, "$lte": end_dt},
        "charge_amount": {"$gt": 0},
    }
    by_day: Dict[str, float] = {}
    cursor = db.crm_leads.find(query, {"_id": 0, "created_at": 1, "charge_amount": 1})
    async for lead in cursor:
        d = (lead.get("created_at") or "")[:10]
        if not d:
            continue
        try:
            by_day[d] = by_day.get(d, 0.0) + float(lead.get("charge_amount") or 0)
        except Exception:
            pass
    return by_day


async def _finanzas_egresos_by_day(user_id: str, start_iso: str, end_iso: str) -> Dict[str, float]:
    start_dt = f"{start_iso}T00:00:00"
    end_dt = f"{end_iso}T23:59:59.999"
    by_day: Dict[str, float] = {}
    cursor = db.cajero_expenses.find(
        {"user_id": user_id, "created_at": {"$gte": start_dt, "$lte": end_dt}},
        {"_id": 0, "created_at": 1, "amount": 1},
    )
    async for ex in cursor:
        d = (ex.get("created_at") or "")[:10]
        if not d:
            continue
        try:
            by_day[d] = by_day.get(d, 0.0) + float(ex.get("amount") or 0)
        except Exception:
            pass
    return by_day


async def _finanzas_get_cargas_list(user_id: str, start_iso: str, end_iso: str) -> list:
    """Devuelve la lista de cargas válidas individuales con su bono calculado
    según el % vigente EL DÍA que se clasificó. Ordenadas por fecha desc."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "line_ids": 1, "role": 1})
    line_filter: Dict = {}
    if user and user.get("role") not in ("admin", "superadmin"):
        line_ids = user.get("line_ids") or []
        if line_ids:
            line_filter = {"line_id": {"$in": line_ids}}
        else:
            return []
    start_dt = f"{start_iso}T00:00:00"
    end_dt = f"{end_iso}T23:59:59.999"
    query = {
        **line_filter,
        "status": "valido",
        "created_at": {"$gte": start_dt, "$lte": end_dt},
        "charge_amount": {"$gt": 0},
    }
    # Cache de rates por día para no consultar 1 vez por carga (puede haber muchas)
    rate_cache: Dict[str, float] = {}

    async def _rate_for(day: str) -> float:
        if day not in rate_cache:
            rate_cache[day] = await _finanzas_get_bonus_rate_for_date(user_id, day)
        return rate_cache[day]

    cargas = []
    cursor = db.crm_leads.find(
        query,
        {"_id": 0, "id": 1, "name": 1, "phone": 1, "line_id": 1, "line_name": 1,
         "created_at": 1, "charge_amount": 1},
    ).sort("created_at", -1)
    async for lead in cursor:
        try:
            value = float(lead.get("charge_amount") or 0)
        except Exception:
            value = 0
        day = (lead.get("created_at") or "")[:10]
        rate = await _rate_for(day) if day else 0
        bono = round(value * rate / 100.0, 2) if rate > 0 else 0.0
        cargas.append({
            "lead_id": lead.get("id"),
            "name": lead.get("name") or "(sin nombre)",
            "phone": lead.get("phone"),
            "line_id": lead.get("line_id"),
            "line_name": lead.get("line_name"),
            "classified_at": lead.get("created_at"),
            "monto": round(value, 2),
            "bono_pct": rate,
            "bono": bono,
            "fichas_entregadas": round(value + bono, 2),
        })
    return cargas


async def _finanzas_compute_bono_by_day(user_id: str, ingresos_by_day: Dict[str, float]) -> Dict[str, float]:
    """Para cada día con ingresos, mira el % vigente ESE DÍA y calcula el bono.
    Esto preserva el histórico cuando el cajero cambia el %."""
    bono_by_day: Dict[str, float] = {}
    for day, monto in ingresos_by_day.items():
        rate = await _finanzas_get_bonus_rate_for_date(user_id, day)
        bono_by_day[day] = round(monto * rate / 100.0, 2) if rate > 0 else 0.0
    return bono_by_day


def _finanzas_get_target_user_id(current_user: dict, requested_user_id: Optional[str]) -> str:
    """Resuelve qué user_id consultar: cajero siempre el suyo; admin puede pasar otro."""
    if requested_user_id and current_user.get("role") in ("admin", "superadmin"):
        return requested_user_id
    return current_user["id"]


@api_router.get("/finanzas/currency")
async def finanzas_get_currency(current_user=Depends(get_current_user)):
    cur = (os.environ.get("PURCHASE_CURRENCY") or "USD").upper().strip()
    return {"currency": cur}


@api_router.get("/finanzas/bonus-rate")
async def finanzas_get_bonus_rate(
    user_id: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """% de bono vigente HOY para el usuario."""
    target_uid = _finanzas_get_target_user_id(current_user, user_id)
    rate = await _finanzas_get_current_bonus_rate(target_uid)
    history = []
    cursor = db.cajero_bonus_rates.find(
        {"user_id": target_uid}, {"_id": 0}
    ).sort("effective_from", -1).limit(20)
    async for h in cursor:
        history.append(h)
    return {"percentage": rate, "history": history}


@api_router.put("/finanzas/bonus-rate")
async def finanzas_update_bonus_rate(
    payload: FinanzasBonusRateUpdate,
    current_user=Depends(get_current_user),
):
    """Actualizar % de bono.
    - PRIMERA vez (no hay rates históricos): aplica desde 2020-01-01 → se proyecta
      a todo el histórico previo del cajero. Así obtiene una estimación retroactiva.
    - Cambios POSTERIORES: el nuevo % rige desde HOY (los días previos conservan
      el % que estuvo vigente en su momento — no se recalculan).
    - Si ya hubo un cambio HOY mismo, lo reemplaza in-place sin acumular versiones."""
    pct = float(payload.percentage)
    if pct < 0 or pct > 200:
        raise HTTPException(status_code=400, detail="El bono debe estar entre 0 y 200%")
    user_id = current_user["id"]
    today = _today_utc_iso_date()

    # Aplicar retroactivo: borra todo el histórico y crea uno único desde 2020.
    # El cajero lo elige explícitamente con un checkbox en el modal.
    if payload.apply_retroactive:
        await db.cajero_bonus_rates.delete_many({"user_id": user_id})
        await db.cajero_bonus_rates.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "percentage": pct,
            "effective_from": "2020-01-01",
            "effective_to": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "retroactive": True,
        })
        return {"percentage": pct, "effective_from": "2020-01-01", "retroactive": True}

    # ¿Es la primera vez? → también retro a todo el histórico previo.
    has_history = await db.cajero_bonus_rates.find_one({"user_id": user_id})
    if not has_history:
        await db.cajero_bonus_rates.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "percentage": pct,
            "effective_from": "2020-01-01",
            "effective_to": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "retroactive": True,
        })
        return {"percentage": pct, "effective_from": "2020-01-01", "retroactive": True}

    # Ya tiene historial — comportamiento estándar (rige desde HOY)
    existing_today = await db.cajero_bonus_rates.find_one(
        {"user_id": user_id, "effective_from": today, "effective_to": None}
    )
    if existing_today:
        await db.cajero_bonus_rates.update_one(
            {"_id": existing_today["_id"]},
            {"$set": {"percentage": pct, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
        return {"percentage": pct, "effective_from": today}

    await db.cajero_bonus_rates.update_many(
        {"user_id": user_id, "effective_to": None},
        {"$set": {"effective_to": today}},
    )
    await db.cajero_bonus_rates.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "percentage": pct,
        "effective_from": today,
        "effective_to": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"percentage": pct, "effective_from": today}


@api_router.get("/finanzas/summary")
async def finanzas_summary(
    filter_type: Optional[str] = "mensual",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user_id: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """Resumen agregado del rango: ingresos, egresos, bono, fichas entregadas, balance."""
    target_uid = _finanzas_get_target_user_id(current_user, user_id)
    start_iso, end_iso = _finanzas_resolve_date_range(filter_type, start_date, end_date)
    ingresos = await _finanzas_ingresos_by_day(target_uid, start_iso, end_iso)
    egresos = await _finanzas_egresos_by_day(target_uid, start_iso, end_iso)
    bono = await _finanzas_compute_bono_by_day(target_uid, ingresos)

    total_ingresos = round(sum(ingresos.values()), 2)
    total_egresos = round(sum(egresos.values()), 2)
    total_bono = round(sum(bono.values()), 2)
    # Fichas entregadas = plata ingresada (en fichas) + bono regalado al cliente.
    # Es lo que el CLIENTE recibió en fichas.
    fichas_entregadas = round(total_ingresos + total_bono, 2)
    # Balance de PLATA neta del cajero = lo que cobró - lo que gastó.
    # El bono NO se resta porque son fichas (no plata real que sale del bolsillo).
    balance = round(total_ingresos - total_egresos, 2)

    # Conteo de cargas válidas (= cuántos "valido" generaron ingreso en el período)
    user = await db.users.find_one({"id": target_uid}, {"_id": 0, "line_ids": 1, "role": 1})
    line_filter: Dict = {}
    total_cargas = 0
    if not (user and user.get("role") not in ("admin", "superadmin") and not (user.get("line_ids") or [])):
        if user and user.get("role") not in ("admin", "superadmin"):
            line_filter = {"line_id": {"$in": user.get("line_ids") or []}}
        total_cargas = await db.crm_leads.count_documents({
            **line_filter,
            "status": "valido",
            "created_at": {"$gte": f"{start_iso}T00:00:00", "$lte": f"{end_iso}T23:59:59.999"},
            "charge_amount": {"$gt": 0},
        })
    avg_por_carga = round(total_ingresos / total_cargas, 2) if total_cargas > 0 else 0.0

    current_rate = await _finanzas_get_current_bonus_rate(target_uid)
    cur = (os.environ.get("PURCHASE_CURRENCY") or "USD").upper().strip()

    return {
        "range": {"start": start_iso, "end": end_iso, "filter_type": filter_type},
        "totals": {
            "ingresos": total_ingresos,
            "egresos": total_egresos,
            "bono": total_bono,
            "fichas_entregadas": fichas_entregadas,
            "balance": balance,
            "total_cargas": total_cargas,
            "avg_por_carga": avg_por_carga,
        },
        "current_bonus_percentage": current_rate,
        "currency": cur,
    }


@api_router.get("/finanzas/cargas")
async def finanzas_list_cargas(
    filter_type: Optional[str] = "mensual",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 500,
    current_user=Depends(get_current_user),
):
    """Lista de cargas válidas individuales en el período, con bono individual
    calculado al % vigente el día que se clasificó cada una."""
    target_uid = _finanzas_get_target_user_id(current_user, user_id)
    start_iso, end_iso = _finanzas_resolve_date_range(filter_type, start_date, end_date)
    cargas = await _finanzas_get_cargas_list(target_uid, start_iso, end_iso)
    if limit and limit > 0:
        cargas = cargas[:limit]
    return {"cargas": cargas, "range": {"start": start_iso, "end": end_iso}, "count": len(cargas)}


@api_router.get("/finanzas/chart")
async def finanzas_chart(
    filter_type: Optional[str] = "mensual",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user_id: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """Breakdown diario para gráfico: [{date, ingresos, egresos, bono}]."""
    target_uid = _finanzas_get_target_user_id(current_user, user_id)
    start_iso, end_iso = _finanzas_resolve_date_range(filter_type, start_date, end_date)
    ingresos = await _finanzas_ingresos_by_day(target_uid, start_iso, end_iso)
    egresos = await _finanzas_egresos_by_day(target_uid, start_iso, end_iso)
    bono = await _finanzas_compute_bono_by_day(target_uid, ingresos)

    start = datetime.fromisoformat(start_iso).date()
    end = datetime.fromisoformat(end_iso).date()
    series = []
    cur = start
    while cur <= end:
        d = cur.isoformat()
        series.append({
            "date": d,
            "ingresos": round(ingresos.get(d, 0.0), 2),
            "egresos": round(egresos.get(d, 0.0), 2),
            "bono": round(bono.get(d, 0.0), 2),
        })
        cur = cur + timedelta(days=1)
    return {"series": series, "range": {"start": start_iso, "end": end_iso}}


@api_router.post("/finanzas/expenses")
async def finanzas_create_expense(
    payload: FinanzasExpenseCreate,
    current_user=Depends(get_current_user),
):
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")
    obs = (payload.observation or "").strip()
    if not obs:
        raise HTTPException(status_code=400, detail="La observación es obligatoria")
    if len(obs) > 300:
        raise HTTPException(status_code=400, detail="Observación muy larga (máx 300)")
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": current_user["id"],
        "user_email": current_user.get("email"),
        "amount": round(float(payload.amount), 2),
        "observation": obs,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.cajero_expenses.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api_router.get("/finanzas/expenses")
async def finanzas_list_expenses(
    filter_type: Optional[str] = "mensual",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user_id: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    target_uid = _finanzas_get_target_user_id(current_user, user_id)
    start_iso, end_iso = _finanzas_resolve_date_range(filter_type, start_date, end_date)
    start_dt = f"{start_iso}T00:00:00"
    end_dt = f"{end_iso}T23:59:59.999"
    items = []
    cursor = db.cajero_expenses.find(
        {"user_id": target_uid, "created_at": {"$gte": start_dt, "$lte": end_dt}},
        {"_id": 0},
    ).sort("created_at", -1)
    today_iso = _today_utc_iso_date()
    async for ex in cursor:
        ex_date = (ex.get("created_at") or "")[:10]
        ex["editable"] = (ex_date == today_iso)
        items.append(ex)
    return {"expenses": items, "range": {"start": start_iso, "end": end_iso}}


@api_router.put("/finanzas/expenses/{expense_id}")
async def finanzas_update_expense(
    expense_id: str,
    payload: FinanzasExpenseUpdate,
    current_user=Depends(get_current_user),
):
    ex = await db.cajero_expenses.find_one({"id": expense_id}, {"_id": 0})
    if not ex:
        raise HTTPException(status_code=404, detail="Egreso no encontrado")
    is_admin = current_user.get("role") in ("admin", "superadmin")
    if ex["user_id"] != current_user["id"] and not is_admin:
        raise HTTPException(status_code=403, detail="No es tu egreso")
    ex_date = (ex.get("created_at") or "")[:10]
    if ex_date != _today_utc_iso_date() and not is_admin:
        raise HTTPException(status_code=403, detail="Solo se puede editar el día que se creó")
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")
    obs = (payload.observation or "").strip()
    if not obs:
        raise HTTPException(status_code=400, detail="La observación es obligatoria")
    await db.cajero_expenses.update_one(
        {"id": expense_id},
        {"$set": {
            "amount": round(float(payload.amount), 2),
            "observation": obs[:300],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"ok": True}


@api_router.delete("/finanzas/expenses/{expense_id}")
async def finanzas_delete_expense(
    expense_id: str,
    current_user=Depends(get_current_user),
):
    ex = await db.cajero_expenses.find_one({"id": expense_id}, {"_id": 0})
    if not ex:
        raise HTTPException(status_code=404, detail="Egreso no encontrado")
    is_admin = current_user.get("role") in ("admin", "superadmin")
    if ex["user_id"] != current_user["id"] and not is_admin:
        raise HTTPException(status_code=403, detail="No es tu egreso")
    ex_date = (ex.get("created_at") or "")[:10]
    if ex_date != _today_utc_iso_date() and not is_admin:
        raise HTTPException(status_code=403, detail="Solo se puede borrar el día que se creó")
    await db.cajero_expenses.delete_one({"id": expense_id})
    return {"ok": True}



# ════════════════════════════════════════════════════════════════════
# CSV BROADCASTS — import audiences, fetch templates, manage opt-outs
# ════════════════════════════════════════════════════════════════════
# Phase 1 of the mass-broadcast feature: cajeros can upload a CSV with
# their own contact list (phone, name, optional vars), select an APPROVED
# Meta template, and send a staggered campaign. All endpoints are scoped
# to the cajero's `line_ids` (admins see everything).

class BroadcastAudienceCreate(BaseModel):
    line_id: str
    name: str  # display name for the audience

class BroadcastOptoutCreate(BaseModel):
    line_id: str
    phone: str
    reason: Optional[str] = "manual"


def _norm_e164(raw: str) -> Optional[str]:
    """Normalize a phone number to E.164-ish digits-only string.
    Returns the digits (with country code), or None if invalid.
    Allows 8-15 digits (E.164 max length 15 incl. country code)."""
    if not raw:
        return None
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    if len(digits) < 8 or len(digits) > 15:
        return None
    return digits


def _user_can_use_line(user: dict, line_id: str) -> bool:
    if user.get("role") == "admin":
        return True
    return line_id in (user.get("line_ids") or [])


# === Broadcast monthly quota helpers ============================================
# Period = current month in ART (Argentina is the operator timezone). Used to
# enforce per-user monthly broadcast caps. Usage is stored per (email, period)
# in `broadcast_quota_usage` so history is preserved and the counter "resets"
# automatically each month (we just look at the new period — old docs stay).

def _quota_current_period() -> str:
    """Return current period as 'YYYY-MM' in Argentina timezone (UTC-3)."""
    now_ar = datetime.now(timezone.utc) - timedelta(hours=3)
    return now_ar.strftime("%Y-%m")


async def _quota_get_state(user: dict) -> dict:
    """Return {quota, base, extra, used, remaining, period} for a user.
    extra rolls over to 0 when the period changes (we only count `extra` if
    the stored `broadcast_quota_period` matches the current one).
    """
    period = _quota_current_period()
    base = int(user.get("broadcast_monthly_quota") or 0)
    stored_period = user.get("broadcast_quota_period")
    extra = int(user.get("broadcast_quota_extra") or 0) if stored_period == period else 0

    usage_doc = await db.broadcast_quota_usage.find_one(
        {"email": user.get("email"), "period": period}, {"_id": 0, "count": 1}
    )
    used = int((usage_doc or {}).get("count") or 0)
    quota = base + extra
    remaining = max(0, quota - used)
    return {
        "period": period,
        "base": base,
        "extra": extra,
        "quota": quota,
        "used": used,
        "remaining": remaining,
    }


async def _quota_increment(email: str, by: int = 1) -> int:
    """Atomically increment usage for the user in the current period; returns new count."""
    if not email or by <= 0:
        return 0
    period = _quota_current_period()
    res = await db.broadcast_quota_usage.find_one_and_update(
        {"email": email, "period": period},
        {"$inc": {"count": by}, "$setOnInsert": {"email": email, "period": period, "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
        return_document=True,
        projection={"_id": 0, "count": 1},
    )
    return int((res or {}).get("count") or by)


async def _quota_reset_extra_if_new_period(user: dict) -> None:
    """Lazy reset: if stored period != current, zero out `broadcast_quota_extra`."""
    period = _quota_current_period()
    if user.get("broadcast_quota_period") != period:
        await db.users.update_one(
            {"id": user.get("id")},
            {"$set": {"broadcast_quota_extra": 0, "broadcast_quota_period": period}}
        )


@api_router.get("/broadcasts/quota/me")
async def broadcasts_quota_me(current_user=Depends(get_current_user)):
    """Current user's broadcast quota snapshot for the active period."""
    await _quota_reset_extra_if_new_period(current_user)
    refreshed = await db.users.find_one({"id": current_user.get("id")}, {"_id": 0})
    state = await _quota_get_state(refreshed or current_user)
    return state


class BroadcastQuotaTopup(BaseModel):
    extra: int  # additional credits to add to the current period


@api_router.post("/broadcasts/quota/{user_id}/topup")
async def broadcasts_quota_topup(
    user_id: str,
    payload: BroadcastQuotaTopup,
    current_user=Depends(get_current_user),
):
    """Admin-only: add extra broadcast credits to a user's current period.
    Extras automatically reset to 0 when a new month starts.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admins pueden recargar cupos")
    if payload.extra <= 0:
        raise HTTPException(status_code=400, detail="extra debe ser > 0")

    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    period = _quota_current_period()
    stored_period = target.get("broadcast_quota_period")
    # If the stored period is from a previous month, treat current extra as 0
    current_extra = int(target.get("broadcast_quota_extra") or 0) if stored_period == period else 0
    new_extra = current_extra + int(payload.extra)

    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "broadcast_quota_extra": new_extra,
            "broadcast_quota_period": period,
            "broadcast_quota_extra_last_topup_at": datetime.now(timezone.utc).isoformat(),
            "broadcast_quota_extra_last_topup_by": current_user.get("email"),
        }}
    )

    refreshed = await db.users.find_one({"id": user_id}, {"_id": 0})
    state = await _quota_get_state(refreshed)
    return {"ok": True, "user_id": user_id, "added_extra": int(payload.extra), "state": state}


@api_router.get("/broadcasts/quota/{user_id}")
async def broadcasts_quota_admin_get(user_id: str, current_user=Depends(get_current_user)):
    """Admin-only: read another user's quota state."""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Sólo admins")
    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return await _quota_get_state(target)


class BroadcastQuotaPreview(BaseModel):
    target_count: int


@api_router.post("/broadcasts/quota/preview")
async def broadcasts_quota_preview(
    payload: BroadcastQuotaPreview,
    current_user=Depends(get_current_user),
):
    """Preview how many of `target_count` will actually be sent given the
    user's remaining quota. Used by the UI on CSV upload to warn the user
    BEFORE creating the campaign."""
    state = await _quota_get_state(current_user)
    n = max(0, int(payload.target_count or 0))
    role_admin = current_user.get("role") == "admin"
    if role_admin:
        # Admins are unlimited
        return {"will_send": n, "excluded": 0, "limited": False, "state": state, "is_admin": True}
    if state["quota"] == 0:
        return {"will_send": 0, "excluded": n, "limited": True, "state": state, "is_admin": False, "reason": "no_quota"}
    will_send = min(n, state["remaining"])
    return {
        "will_send": will_send,
        "excluded": max(0, n - will_send),
        "limited": will_send < n,
        "state": state,
        "is_admin": False,
    }


@api_router.get("/broadcasts/templates")
async def broadcasts_list_templates(
    line_id: str,
    include_all: bool = False,
    current_user=Depends(get_current_user),
):
    """List templates for a line's WABA.
    By default only APPROVED ones; pass include_all=true to also see PENDING/REJECTED.
    """
    if not _user_can_use_line(current_user, line_id):
        raise HTTPException(status_code=403, detail="Sin acceso a esta línea")
    line = await db.crm_lines.find_one({"id": line_id}, {"_id": 0})
    if not line:
        raise HTTPException(status_code=404, detail="Línea no encontrada")

    waba_id = line.get("whatsapp_business_account_id")
    token = line.get("whatsapp_token") or WHATSAPP_TOKEN
    if not waba_id:
        raise HTTPException(status_code=400, detail="La línea no tiene WhatsApp Business Account ID configurado. Editá la línea y agregá el WABA ID.")
    if not token:
        raise HTTPException(status_code=400, detail="La línea no tiene WhatsApp token configurado.")

    status_filter = None if include_all else "APPROVED"
    result = await wa_fetch_templates(waba_id, token, status_filter=status_filter)
    if "error" in result:
        return {"templates": [], "error": result["error"]}

    templates = []
    for tpl in result.get("data", []):
        body_text = ""
        var_count = 0
        header_format = None
        for comp in tpl.get("components", []):
            if comp.get("type") == "BODY":
                body_text = comp.get("text", "") or ""
                var_count = len(re.findall(r"\{\{(\d+)\}\}", body_text))
            elif comp.get("type") == "HEADER":
                header_format = comp.get("format")
        templates.append({
            "name": tpl.get("name"),
            "language": tpl.get("language"),
            "category": tpl.get("category"),
            "status": tpl.get("status"),
            "rejected_reason": tpl.get("rejected_reason"),
            "quality_score": tpl.get("quality_score"),
            "body_text": body_text,
            "var_count": var_count,
            "header_format": header_format,
        })

    line_name_lower = (line.get("name") or "").strip().lower().split()[0] if line.get("name") else ""
    if line_name_lower:
        templates.sort(key=lambda t: (0 if t["name"].lower().startswith(line_name_lower) else 1, t["name"]))
    else:
        templates.sort(key=lambda t: t["name"])

    return {"templates": templates, "line_id": line_id, "line_name": line.get("name")}


class BroadcastTemplateCreate(BaseModel):
    line_id: str
    name: str  # snake_case, lowercase, numbers + _
    category: str = "MARKETING"  # MARKETING | UTILITY | AUTHENTICATION
    language: str = "es_AR"
    body_text: str
    header_text: Optional[str] = None
    header_image_url: Optional[str] = None
    footer_text: Optional[str] = None
    buttons: Optional[List[Dict]] = None
    example_body_vars: Optional[List[str]] = None


@api_router.post("/broadcasts/templates/create")
async def broadcasts_create_template(
    payload: BroadcastTemplateCreate,
    current_user=Depends(get_current_user),
):
    """Submit a new template to Meta for approval."""
    if not _user_can_use_line(current_user, payload.line_id):
        raise HTTPException(status_code=403, detail="Sin acceso a esta línea")
    line = await db.crm_lines.find_one({"id": payload.line_id}, {"_id": 0})
    if not line:
        raise HTTPException(status_code=404, detail="Línea no encontrada")
    waba_id = line.get("whatsapp_business_account_id")
    token = line.get("whatsapp_token") or WHATSAPP_TOKEN
    if not waba_id or not token:
        raise HTTPException(status_code=400, detail="La línea no tiene WABA id o token de WhatsApp configurados.")

    # Validate template name format (Meta requirement: lowercase snake_case)
    if not re.fullmatch(r"[a-z0-9_]+", payload.name):
        raise HTTPException(status_code=400, detail="El nombre debe ser minúsculas, números y guión bajo (snake_case)")
    if len(payload.name) > 512:
        raise HTTPException(status_code=400, detail="El nombre es demasiado largo")
    if payload.category not in ("MARKETING", "UTILITY", "AUTHENTICATION"):
        raise HTTPException(status_code=400, detail="Categoría inválida")

    # Count variables in body and ensure example vars matches
    vars_in_body = len(re.findall(r"\{\{\d+\}\}", payload.body_text))
    if vars_in_body and not payload.example_body_vars:
        raise HTTPException(status_code=400, detail=f"La plantilla usa {vars_in_body} variables — agregá ejemplos de valores para cada una (Meta los exige).")
    if payload.example_body_vars and len(payload.example_body_vars) != vars_in_body:
        raise HTTPException(status_code=400, detail=f"Cantidad de ejemplos ({len(payload.example_body_vars)}) no coincide con las variables del body ({vars_in_body}).")

    result = await wa_create_template(
        waba_id=waba_id,
        token=token,
        name=payload.name,
        category=payload.category,
        language=payload.language,
        body_text=payload.body_text,
        header_text=payload.header_text,
        header_image_url=payload.header_image_url,
        footer_text=payload.footer_text,
        buttons=payload.buttons,
        example_body_vars=payload.example_body_vars,
    )

    # Meta returns {id, status, category} on success, or {error: {...}} on failure
    if result.get("error"):
        err = result["error"]
        msg = err.get("error_user_msg") or err.get("message") or str(err)
        raise HTTPException(status_code=400, detail=f"Meta rechazó la plantilla: {msg}")
    if result.get("_http_status", 200) >= 400:
        raise HTTPException(status_code=400, detail=f"Meta devolvió error HTTP {result.get('_http_status')}: {str(result)[:300]}")

    return {
        "ok": True,
        "id": result.get("id"),
        "status": result.get("status"),
        "category": result.get("category"),
        "note": "Enviada a Meta. Llega aprobación en 1-24hs. Si llega REJECTED, vas a ver la razón en la lista de plantillas.",
    }


@api_router.delete("/broadcasts/templates")
async def broadcasts_delete_template(
    line_id: str,
    name: str,
    current_user=Depends(get_current_user),
):
    if not _user_can_use_line(current_user, line_id):
        raise HTTPException(status_code=403, detail="Sin acceso a esta línea")
    line = await db.crm_lines.find_one({"id": line_id}, {"_id": 0})
    if not line:
        raise HTTPException(status_code=404, detail="Línea no encontrada")
    waba_id = line.get("whatsapp_business_account_id")
    token = line.get("whatsapp_token") or WHATSAPP_TOKEN
    if not waba_id or not token:
        raise HTTPException(status_code=400, detail="Línea sin WABA id/token")
    result = await wa_delete_template(waba_id, token, name)
    if result.get("error"):
        err_msg = result["error"]
        code = result.get("code")
        # Helpful Spanish hint for the most common Meta error
        if code == 100 or "permission" in str(err_msg).lower() or "owner/shared" in str(err_msg).lower():
            err_msg = (
                f"Meta rechazó el borrado: el token de WhatsApp de esta línea no tiene permisos "
                f"para administrar plantillas (necesita 'whatsapp_business_management' y rol admin sobre la WABA). "
                f"Solución: en Meta Business Manager → Configuración → Usuarios del sistema, generá un token "
                f"de System User con permiso 'whatsapp_business_management' y pegalo en el campo 'WhatsApp Token' de la línea. "
                f"También podés borrar la plantilla manualmente desde Meta Business → Cuentas de WhatsApp → Plantillas. "
                f"(Detalle Meta: {err_msg})"
            )
        raise HTTPException(status_code=400, detail=err_msg)
    return {"ok": True, "result": result}


@api_router.post("/broadcasts/audiences/upload")
async def broadcasts_upload_audience(
    file: UploadFile = File(...),
    line_id: str = Form(...),
    name: str = Form(...),
    current_user=Depends(get_current_user),
):
    """Upload a CSV audience for a line.

    CSV must have a `phone` column (or `telefono`/`teléfono`/`tel`); optional
    `name` and `var1..var5` columns are used to populate template variables.
    Validates E.164, deduplicates by (line_id, phone), excludes anything
    already in the optout blacklist for that line.
    """
    if not _user_can_use_line(current_user, line_id):
        raise HTTPException(status_code=403, detail="Sin acceso a esta línea")
    line = await db.crm_lines.find_one({"id": line_id}, {"_id": 0})
    if not line:
        raise HTTPException(status_code=404, detail="Línea no encontrada")

    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="CSV demasiado grande (máx 5MB)")

    import csv as _csv
    import io as _io
    # Try utf-8 first, fall back to latin-1 (common Excel export)
    text = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise HTTPException(status_code=400, detail="No se pudo decodificar el CSV")

    # Sniff delimiter (,, ;, or \t)
    sample = text[:2048]
    try:
        dialect = _csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except _csv.Error:
        class _D: delimiter = ","
        dialect = _D()

    reader = _csv.DictReader(_io.StringIO(text), dialect=dialect)
    fieldnames = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
    if not fieldnames:
        raise HTTPException(status_code=400, detail="CSV vacío o sin encabezados")

    # Map phone column synonyms
    phone_col = None
    for cand in ("phone", "telefono", "teléfono", "tel", "celular", "movil", "móvil", "whatsapp"):
        if cand in fieldnames:
            phone_col = cand
            break
    if not phone_col:
        raise HTTPException(status_code=400, detail="El CSV debe tener una columna 'phone' (o telefono/tel/celular)")

    name_col = "name" if "name" in fieldnames else ("nombre" if "nombre" in fieldnames else None)
    var_cols = [c for c in fieldnames if re.fullmatch(r"var\d+", c)]
    var_cols.sort(key=lambda c: int(c[3:]))

    # Pre-load optout blacklist for this line
    optouts = await db.broadcast_optouts.find(
        {"line_id": line_id}, {"_id": 0, "phone": 1}
    ).to_list(100000)
    optout_phones = {o["phone"] for o in optouts}

    audience_id = str(uuid.uuid4())
    contacts: List[Dict] = []
    seen_phones: set = set()
    invalid_count = 0
    duplicate_count = 0
    optout_count = 0
    total_rows = 0

    for row in reader:
        total_rows += 1
        if total_rows > 100_000:
            break
        # Build a normalized lowercase-key version of the row
        nrow = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        phone_norm = _norm_e164(nrow.get(phone_col, ""))
        if not phone_norm:
            invalid_count += 1
            continue
        if phone_norm in seen_phones:
            duplicate_count += 1
            continue
        if phone_norm in optout_phones:
            optout_count += 1
            continue
        seen_phones.add(phone_norm)
        contacts.append({
            "id": str(uuid.uuid4()),
            "audience_id": audience_id,
            "line_id": line_id,
            "phone": phone_norm,
            "name": (nrow.get(name_col, "").strip() if name_col else "") or "",
            "vars": {f"var{i+1}": nrow.get(c, "") for i, c in enumerate(var_cols) if nrow.get(c)},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    if not contacts:
        raise HTTPException(status_code=400, detail=f"Ningún contacto válido en el CSV (filas: {total_rows}, inválidos: {invalid_count}, duplicados: {duplicate_count}, optouts: {optout_count})")

    audience_doc = {
        "id": audience_id,
        "line_id": line_id,
        "line_name": line.get("name"),
        "name": name,
        "filename": file.filename,
        "total_contacts": len(contacts),
        "stats": {
            "total_rows": total_rows,
            "valid": len(contacts),
            "invalid": invalid_count,
            "duplicates": duplicate_count,
            "excluded_optouts": optout_count,
            "var_columns": var_cols,
            "name_column": name_col,
        },
        "created_by": current_user.get("id"),
        "created_by_email": current_user.get("email"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.broadcast_audiences.insert_one(audience_doc)
    # Insert contacts in batches of 1000
    for i in range(0, len(contacts), 1000):
        await db.broadcast_contacts.insert_many(contacts[i:i + 1000])

    audience_doc.pop("_id", None)
    return {"audience": audience_doc}


@api_router.get("/broadcasts/audiences")
async def broadcasts_list_audiences(
    line_id: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """List audiences. Cajeros see audiences for their own lines; admins see all."""
    query: Dict = {}
    if current_user.get("role") != "admin":
        allowed = current_user.get("line_ids") or []
        if not allowed:
            return {"audiences": []}
        query["line_id"] = {"$in": allowed}
    if line_id:
        if not _user_can_use_line(current_user, line_id):
            raise HTTPException(status_code=403, detail="Sin acceso a esta línea")
        query["line_id"] = line_id
    items = await db.broadcast_audiences.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"audiences": items}


@api_router.get("/broadcasts/audiences/{audience_id}")
async def broadcasts_get_audience(audience_id: str, current_user=Depends(get_current_user)):
    aud = await db.broadcast_audiences.find_one({"id": audience_id}, {"_id": 0})
    if not aud:
        raise HTTPException(status_code=404, detail="Audiencia no encontrada")
    if not _user_can_use_line(current_user, aud["line_id"]):
        raise HTTPException(status_code=403, detail="Sin acceso a esta audiencia")
    sample = await db.broadcast_contacts.find(
        {"audience_id": audience_id}, {"_id": 0}
    ).limit(20).to_list(20)
    return {"audience": aud, "sample": sample}


@api_router.delete("/broadcasts/audiences/{audience_id}")
async def broadcasts_delete_audience(audience_id: str, current_user=Depends(get_current_user)):
    aud = await db.broadcast_audiences.find_one({"id": audience_id}, {"_id": 0})
    if not aud:
        raise HTTPException(status_code=404, detail="Audiencia no encontrada")
    if not _user_can_use_line(current_user, aud["line_id"]):
        raise HTTPException(status_code=403, detail="Sin acceso a esta audiencia")
    await db.broadcast_audiences.delete_one({"id": audience_id})
    await db.broadcast_contacts.delete_many({"audience_id": audience_id})
    return {"deleted": True}


@api_router.get("/broadcasts/optouts")
async def broadcasts_list_optouts(
    line_id: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    query: Dict = {}
    if current_user.get("role") != "admin":
        allowed = current_user.get("line_ids") or []
        if not allowed:
            return {"optouts": []}
        query["line_id"] = {"$in": allowed}
    if line_id:
        if not _user_can_use_line(current_user, line_id):
            raise HTTPException(status_code=403, detail="Sin acceso a esta línea")
        query["line_id"] = line_id
    items = await db.broadcast_optouts.find(query, {"_id": 0}).sort("created_at", -1).limit(2000).to_list(2000)
    return {"optouts": items}


@api_router.post("/broadcasts/optouts")
async def broadcasts_add_optout(payload: BroadcastOptoutCreate, current_user=Depends(get_current_user)):
    if not _user_can_use_line(current_user, payload.line_id):
        raise HTTPException(status_code=403, detail="Sin acceso a esta línea")
    phone = _norm_e164(payload.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Teléfono inválido")
    doc = {
        "id": str(uuid.uuid4()),
        "line_id": payload.line_id,
        "phone": phone,
        "reason": payload.reason or "manual",
        "added_by": current_user.get("id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # Upsert by (line_id, phone)
    await db.broadcast_optouts.update_one(
        {"line_id": payload.line_id, "phone": phone},
        {"$setOnInsert": doc},
        upsert=True,
    )
    return {"ok": True, "phone": phone}


@api_router.delete("/broadcasts/optouts/{optout_id}")
async def broadcasts_delete_optout(optout_id: str, current_user=Depends(get_current_user)):
    o = await db.broadcast_optouts.find_one({"id": optout_id}, {"_id": 0})
    if not o:
        raise HTTPException(status_code=404, detail="Optout no encontrado")
    if not _user_can_use_line(current_user, o["line_id"]):
        raise HTTPException(status_code=403, detail="Sin acceso")
    await db.broadcast_optouts.delete_one({"id": optout_id})
    return {"deleted": True}


# ════════════════════════════════════════════════════════════════════
# CSV BROADCASTS — campaigns engine (Phase 2)
# ════════════════════════════════════════════════════════════════════
# Segment query → list of contacts from CRM leads.
# Speed is FIXED to "cauta": 30-90s random delay between sends.
# Hours: only 09:00-23:00 ART. Outside that window the worker sleeps.
#
# Why fixed: cliente lo pidió explícitamente — "prefiero que sea fijo
# porque después el cajero voltea la línea por spam y va a decir que
# no lo hizo".

CAUTA_MIN_DELAY_S = 30
CAUTA_MAX_DELAY_S = 90
NIGHT_PAUSE_FROM_HOUR = 23  # ART
NIGHT_PAUSE_TO_HOUR   = 9   # ART
ART_TZ = timezone(timedelta(hours=-3))  # Argentina UTC-3 (no DST)


def _is_night_pause_now() -> bool:
    """True if current ART time is in the night-pause window [23:00, 09:00)."""
    now_art = datetime.now(ART_TZ)
    h = now_art.hour
    return h >= NIGHT_PAUSE_FROM_HOUR or h < NIGHT_PAUSE_TO_HOUR


def _seconds_until_morning() -> int:
    """Seconds until next 09:00 ART (when night-pause ends)."""
    now_art = datetime.now(ART_TZ)
    target = now_art.replace(hour=NIGHT_PAUSE_TO_HOUR, minute=0, second=0, microsecond=0)
    if now_art >= target:
        target = target + timedelta(days=1)
    return max(60, int((target - now_art).total_seconds()))


class BroadcastSegmentQuery(BaseModel):
    line_id: str
    statuses: Optional[List[str]] = None        # ["valido", "nuevo", ...]
    purchase_in_last_days: Optional[int] = None # leads with status=valido in last N days
    response_in_last_days: Optional[int] = None # leads who replied in last N days
    not_responded_in_last_days: Optional[int] = None  # opposite
    limit: int = 5000


async def _resolve_segment(query: BroadcastSegmentQuery) -> List[Dict]:
    """Resolve a segment query into a list of {phone, name, line_id, vars}.
    Excludes contacts already in optouts."""
    base: Dict = {"line_id": query.line_id, "phone": {"$exists": True, "$ne": ""}}
    if query.statuses:
        base["status"] = {"$in": query.statuses}

    now = datetime.now(timezone.utc)
    if query.purchase_in_last_days:
        from_dt = (now - timedelta(days=query.purchase_in_last_days)).isoformat()
        base["status"] = "valido"
        base["status_changed_at"] = {"$gte": from_dt}
    if query.response_in_last_days:
        from_dt = (now - timedelta(days=query.response_in_last_days)).isoformat()
        base["last_message_at"] = {"$gte": from_dt}
    if query.not_responded_in_last_days:
        from_dt = (now - timedelta(days=query.not_responded_in_last_days)).isoformat()
        base["last_message_at"] = {"$lt": from_dt}

    leads = await db.crm_leads.find(
        base, {"_id": 0, "phone": 1, "name": 1, "line_id": 1}
    ).limit(query.limit).to_list(query.limit)

    # Drop optouts
    optouts = await db.broadcast_optouts.find(
        {"line_id": query.line_id}, {"_id": 0, "phone": 1}
    ).to_list(100000)
    optout_phones = {o["phone"] for o in optouts}

    # Normalize + dedupe by phone
    seen = set()
    out: List[Dict] = []
    for lead in leads:
        ph = _norm_e164(lead.get("phone"))
        if not ph or ph in seen or ph in optout_phones:
            continue
        seen.add(ph)
        out.append({
            "phone": ph,
            "name": lead.get("name") or "",
            "line_id": query.line_id,
            "vars": {},
        })
    return out


@api_router.post("/broadcasts/segments/preview")
async def broadcasts_segment_preview(
    query: BroadcastSegmentQuery,
    current_user=Depends(get_current_user),
):
    """Count and sample (max 10) contacts matching a segment query."""
    if not _user_can_use_line(current_user, query.line_id):
        raise HTTPException(status_code=403, detail="Sin acceso a esta línea")
    contacts = await _resolve_segment(query)
    return {"total": len(contacts), "sample": contacts[:10]}


class BroadcastCampaignCreate(BaseModel):
    line_id: str
    name: str
    # Source — exactly ONE of these:
    audience_id: Optional[str] = None
    segment: Optional[BroadcastSegmentQuery] = None
    # Template
    template_name: str
    template_language: str = "es_AR"
    # Mapping: variables[i] is the column name in audience contact's `vars`
    # (e.g. ["name", "var1"] => template {{1}}=name, {{2}}=var1).
    # The literal string "name" maps to contact.name.
    template_var_mapping: List[str] = []
    header_image_url: Optional[str] = None
    # Schedule (optional)
    scheduled_at: Optional[str] = None  # ISO datetime UTC
    # Auto-resend (optional)
    resend_after_hours: Optional[int] = None
    resend_template_name: Optional[str] = None


@api_router.post("/broadcasts/campaigns")
async def broadcasts_create_campaign(
    payload: BroadcastCampaignCreate,
    current_user=Depends(get_current_user),
):
    """Create a campaign (status=draft, or scheduled if scheduled_at given)."""
    if not _user_can_use_line(current_user, payload.line_id):
        raise HTTPException(status_code=403, detail="Sin acceso a esta línea")
    line = await db.crm_lines.find_one({"id": payload.line_id}, {"_id": 0})
    if not line:
        raise HTTPException(status_code=404, detail="Línea no encontrada")
    if not (payload.audience_id or payload.segment):
        raise HTTPException(status_code=400, detail="Debe especificar audience_id o segment")
    if payload.audience_id and payload.segment:
        raise HTTPException(status_code=400, detail="Solo audience_id O segment, no ambos")

    # Resolve target count
    if payload.audience_id:
        aud = await db.broadcast_audiences.find_one({"id": payload.audience_id}, {"_id": 0})
        if not aud:
            raise HTTPException(status_code=404, detail="Audiencia no encontrada")
        if aud["line_id"] != payload.line_id:
            raise HTTPException(status_code=400, detail="La audiencia pertenece a otra línea")
        target_count = aud.get("total_contacts", 0)
    else:
        if payload.segment.line_id != payload.line_id:
            raise HTTPException(status_code=400, detail="El segmento debe ser de la misma línea")
        contacts = await _resolve_segment(payload.segment)
        target_count = len(contacts)

    if target_count == 0:
        raise HTTPException(status_code=400, detail="Sin contactos para esta campaña (audiencia/segmento vacío)")

    # Quota enforcement: cap target_count by the user's remaining quota for the period
    quota_state = await _quota_get_state(current_user)
    quota_truncated = False
    quota_excluded = 0
    if quota_state["quota"] > 0:
        remaining = quota_state["remaining"]
        if remaining <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Sin cupo de mensajes este mes ({quota_state['used']}/{quota_state['quota']}). Pedile a un admin que recargue créditos extras.",
            )
        if target_count > remaining:
            quota_excluded = target_count - remaining
            quota_truncated = True
            target_count = remaining
    elif quota_state["base"] == 0 and current_user.get("role") != "admin":
        # No quota assigned at all → block (admins are unlimited)
        raise HTTPException(
            status_code=403,
            detail="Tu usuario no tiene cupo de mensajes masivos asignado. Pedile a un admin que te asigne uno.",
        )

    status = "scheduled" if payload.scheduled_at else "draft"
    campaign = {
        "id": str(uuid.uuid4()),
        "line_id": payload.line_id,
        "line_name": line.get("name"),
        "name": payload.name,
        "audience_id": payload.audience_id,
        "segment": payload.segment.dict() if payload.segment else None,
        "template_name": payload.template_name,
        "template_language": payload.template_language,
        "template_var_mapping": payload.template_var_mapping or [],
        "header_image_url": payload.header_image_url,
        "scheduled_at": payload.scheduled_at,
        "resend_after_hours": payload.resend_after_hours,
        "resend_template_name": payload.resend_template_name,
        "status": status,
        "target_count": target_count,
        "quota_truncated": quota_truncated,
        "quota_excluded": quota_excluded,
        "stats": {"sent": 0, "delivered": 0, "read": 0, "failed": 0, "replied": 0, "skipped_optout": 0},
        "created_by": current_user.get("id"),
        "created_by_email": current_user.get("email"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "completed_at": None,
        "paused_reason": None,
    }
    await db.broadcast_campaigns.insert_one(campaign)
    campaign.pop("_id", None)

    if status == "scheduled":
        # Spawn a sleeper task that wakes at scheduled_at and starts the worker
        asyncio.create_task(_csv_campaign_scheduler(campaign["id"]))

    return {
        "campaign": campaign,
        "quota_truncated": quota_truncated,
        "quota_excluded": quota_excluded,
        "quota_state": quota_state,
    }


@api_router.get("/broadcasts/campaigns")
async def broadcasts_list_campaigns(
    line_id: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    query: Dict = {}
    if current_user.get("role") != "admin":
        allowed = current_user.get("line_ids") or []
        if not allowed:
            return {"campaigns": []}
        query["line_id"] = {"$in": allowed}
    if line_id:
        if not _user_can_use_line(current_user, line_id):
            raise HTTPException(status_code=403, detail="Sin acceso a esta línea")
        query["line_id"] = line_id
    items = await db.broadcast_campaigns.find(query, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
    return {"campaigns": items}


@api_router.get("/broadcasts/campaigns/{campaign_id}")
async def broadcasts_get_campaign(campaign_id: str, current_user=Depends(get_current_user)):
    c = await db.broadcast_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    if not _user_can_use_line(current_user, c["line_id"]):
        raise HTTPException(status_code=403, detail="Sin acceso")
    # Recent messages for live tail
    recent = await db.broadcast_messages.find(
        {"campaign_id": campaign_id}, {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    return {"campaign": c, "recent_messages": recent}


_csv_campaign_workers: Dict[str, "asyncio.Task"] = {}


@api_router.post("/broadcasts/campaigns/{campaign_id}/start")
async def broadcasts_start_campaign(campaign_id: str, current_user=Depends(get_current_user)):
    c = await db.broadcast_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    if not _user_can_use_line(current_user, c["line_id"]):
        raise HTTPException(status_code=403, detail="Sin acceso")
    if c["status"] in ("running", "completed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"La campaña está en estado {c['status']}")
    await db.broadcast_campaigns.update_one(
        {"id": campaign_id},
        {"$set": {"status": "running", "started_at": datetime.now(timezone.utc).isoformat(), "paused_reason": None}}
    )
    if campaign_id in _csv_campaign_workers and not _csv_campaign_workers[campaign_id].done():
        return {"started": True, "note": "ya estaba corriendo"}
    task = asyncio.create_task(_csv_campaign_worker(campaign_id))
    _csv_campaign_workers[campaign_id] = task
    return {"started": True}


@api_router.post("/broadcasts/campaigns/{campaign_id}/pause")
async def broadcasts_pause_campaign(campaign_id: str, current_user=Depends(get_current_user)):
    c = await db.broadcast_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    if not _user_can_use_line(current_user, c["line_id"]):
        raise HTTPException(status_code=403, detail="Sin acceso")
    await db.broadcast_campaigns.update_one(
        {"id": campaign_id},
        {"$set": {"status": "paused", "paused_reason": "manual"}}
    )
    return {"paused": True}


@api_router.post("/broadcasts/campaigns/{campaign_id}/cancel")
async def broadcasts_cancel_campaign(campaign_id: str, current_user=Depends(get_current_user)):
    c = await db.broadcast_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    if not _user_can_use_line(current_user, c["line_id"]):
        raise HTTPException(status_code=403, detail="Sin acceso")
    await db.broadcast_campaigns.update_one(
        {"id": campaign_id},
        {"$set": {"status": "cancelled", "completed_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"cancelled": True}


async def _csv_campaign_scheduler(campaign_id: str):
    """Sleep until scheduled_at, then start the campaign worker."""
    try:
        c = await db.broadcast_campaigns.find_one({"id": campaign_id}, {"_id": 0})
        if not c or c.get("status") != "scheduled":
            return
        scheduled_at = c.get("scheduled_at")
        if not scheduled_at:
            return
        target = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        delay = (target - datetime.now(timezone.utc)).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)
        # Re-check status (may have been cancelled while sleeping)
        c2 = await db.broadcast_campaigns.find_one({"id": campaign_id}, {"_id": 0, "status": 1})
        if not c2 or c2.get("status") != "scheduled":
            return
        await db.broadcast_campaigns.update_one(
            {"id": campaign_id},
            {"$set": {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()}}
        )
        task = asyncio.create_task(_csv_campaign_worker(campaign_id))
        _csv_campaign_workers[campaign_id] = task
    except Exception as e:
        logger.error(f"campaign scheduler {campaign_id} failed: {e}")


async def _csv_campaign_worker(campaign_id: str):
    """Send a CSV campaign — staggered template messages, night-pause aware."""
    import random
    try:
        c = await db.broadcast_campaigns.find_one({"id": campaign_id}, {"_id": 0})
        if not c:
            return
        line = await db.crm_lines.find_one({"id": c["line_id"]}, {"_id": 0})
        if not line:
            await db.broadcast_campaigns.update_one(
                {"id": campaign_id},
                {"$set": {"status": "failed", "paused_reason": "Línea no encontrada"}}
            )
            return
        token = line.get("whatsapp_token") or WHATSAPP_TOKEN
        phone_id = line.get("phone_number_id") or WHATSAPP_PHONE_NUMBER_ID
        if not token or not phone_id:
            await db.broadcast_campaigns.update_one(
                {"id": campaign_id},
                {"$set": {"status": "failed", "paused_reason": "WhatsApp no configurado en la línea"}}
            )
            return

        # Resolve contacts
        if c.get("audience_id"):
            contacts = await db.broadcast_contacts.find(
                {"audience_id": c["audience_id"]}, {"_id": 0}
            ).to_list(100000)
        else:
            seg = BroadcastSegmentQuery(**c["segment"])
            contacts = await _resolve_segment(seg)

        # Refresh optouts at runtime
        optouts = await db.broadcast_optouts.find(
            {"line_id": c["line_id"]}, {"_id": 0, "phone": 1}
        ).to_list(100000)
        optout_phones = {o["phone"] for o in optouts}

        # Skip already-sent (resume support)
        already_sent = await db.broadcast_messages.find(
            {"campaign_id": campaign_id, "status": {"$in": ["sent", "delivered", "read"]}},
            {"_id": 0, "phone": 1},
        ).to_list(100000)
        already_phones = {m["phone"] for m in already_sent}

        var_mapping = c.get("template_var_mapping") or []

        for contact in contacts:
            # Cancel/pause check
            state = await db.broadcast_campaigns.find_one(
                {"id": campaign_id}, {"_id": 0, "status": 1}
            )
            if not state or state.get("status") not in ("running",):
                logger.info(f"campaign {campaign_id} stopped: status={state.get('status') if state else 'missing'}")
                return

            phone = contact.get("phone")
            if not phone or phone in already_phones:
                continue
            if phone in optout_phones:
                await db.broadcast_campaigns.update_one(
                    {"id": campaign_id}, {"$inc": {"stats.skipped_optout": 1}}
                )
                continue

            # Night pause check
            while _is_night_pause_now():
                await db.broadcast_campaigns.update_one(
                    {"id": campaign_id},
                    {"$set": {"paused_reason": "Pausa nocturna 23:00-09:00 ART"}}
                )
                logger.info(f"campaign {campaign_id} sleeping until morning")
                await asyncio.sleep(min(_seconds_until_morning(), 300))
                # Re-check status while sleeping
                state = await db.broadcast_campaigns.find_one(
                    {"id": campaign_id}, {"_id": 0, "status": 1}
                )
                if not state or state.get("status") not in ("running",):
                    return
            await db.broadcast_campaigns.update_one(
                {"id": campaign_id}, {"$set": {"paused_reason": None}}
            )

            # Quota enforcement at send-time. Re-check on every iteration so a
            # mid-campaign month rollover or admin top-up applies live.
            owner_email = c.get("created_by_email")
            owner_user = None
            if owner_email:
                owner_user = await db.users.find_one({"email": owner_email}, {"_id": 0})
            if owner_user and owner_user.get("role") != "admin":
                qstate = await _quota_get_state(owner_user)
                if qstate["quota"] > 0 and qstate["used"] >= qstate["quota"]:
                    await db.broadcast_campaigns.update_one(
                        {"id": campaign_id},
                        {"$set": {
                            "status": "paused",
                            "paused_reason": f"Cupo mensual alcanzado ({qstate['used']}/{qstate['quota']}). Pedile a un admin que recargue.",
                        }}
                    )
                    logger.info(f"campaign {campaign_id} paused: monthly quota reached for {owner_email}")
                    return

            # Build template variables
            tpl_vars: List[str] = []
            for col in var_mapping:
                if col == "name":
                    tpl_vars.append((contact.get("name") or "").strip() or "amigo")
                else:
                    v = (contact.get("vars") or {}).get(col, "")
                    tpl_vars.append(str(v) if v is not None else "")

            msg_id = str(uuid.uuid4())
            send_result = await wa_send_template(
                phone=phone,
                template_name=c["template_name"],
                language=c.get("template_language") or "es_AR",
                variables=tpl_vars or None,
                header_image_url=c.get("header_image_url"),
                token=token,
                phone_id=phone_id,
            )

            wa_msg_id = None
            err = None
            success = False
            if isinstance(send_result, dict):
                if "error" in send_result:
                    err = str(send_result.get("error"))[:300]
                elif send_result.get("messages"):
                    wa_msg_id = send_result["messages"][0].get("id")
                    success = True
                else:
                    err = str(send_result)[:300]

            doc = {
                "id": msg_id,
                "campaign_id": campaign_id,
                "line_id": c["line_id"],
                "phone": phone,
                "name": contact.get("name", ""),
                "template_name": c["template_name"],
                "wa_message_id": wa_msg_id,
                "status": "sent" if success else "failed",
                "error": err,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.broadcast_messages.insert_one(doc)
            inc = {"stats.sent": 1} if success else {"stats.failed": 1}
            await db.broadcast_campaigns.update_one({"id": campaign_id}, {"$inc": inc})

            # Increment quota usage on successful send (skip admins — unlimited)
            if success and owner_email and owner_user and owner_user.get("role") != "admin":
                await _quota_increment(owner_email, by=1)

            # Auto-pause on Meta rate-limit (#80007 / #131056) or auth error
            if err and any(k in err for k in ("131056", "80007", "rate", "OAuthException")):
                await db.broadcast_campaigns.update_one(
                    {"id": campaign_id},
                    {"$set": {"status": "paused", "paused_reason": f"Meta error: {err[:80]}"}}
                )
                logger.warning(f"campaign {campaign_id} auto-paused: {err[:120]}")
                return

            # Cauta delay
            delay = random.uniform(CAUTA_MIN_DELAY_S, CAUTA_MAX_DELAY_S)
            await asyncio.sleep(delay)

        # Done with first pass
        await db.broadcast_campaigns.update_one(
            {"id": campaign_id},
            {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat(), "paused_reason": None}}
        )
        logger.info(f"campaign {campaign_id} completed")

        # ── Auto-resend kickoff ─────────────────────────────────────
        # If the campaign was configured with resend_after_hours +
        # resend_template_name, queue a follow-up that runs after that
        # delay and re-sends ONLY to contacts who never read/replied.
        c_final = await db.broadcast_campaigns.find_one(
            {"id": campaign_id},
            {"_id": 0, "resend_after_hours": 1, "resend_template_name": 1, "resend_done_at": 1}
        )
        if (c_final
            and c_final.get("resend_after_hours")
            and c_final.get("resend_template_name")
            and not c_final.get("resend_done_at")):
            asyncio.create_task(_csv_campaign_resend(campaign_id))
    except asyncio.CancelledError:
        await db.broadcast_campaigns.update_one(
            {"id": campaign_id}, {"$set": {"status": "cancelled"}}
        )
        raise
    except Exception as e:
        logger.exception(f"csv campaign worker {campaign_id} failed")
        await db.broadcast_campaigns.update_one(
            {"id": campaign_id},
            {"$set": {"status": "failed", "paused_reason": f"worker error: {str(e)[:200]}"}}
        )


@app.on_event("startup")
async def _resume_scheduled_campaigns():
    """On boot, re-arm schedulers for any campaigns still in 'scheduled' state."""
    try:
        scheduled = await db.broadcast_campaigns.find(
            {"status": "scheduled"}, {"_id": 0, "id": 1}
        ).to_list(500)
        for c in scheduled:
            asyncio.create_task(_csv_campaign_scheduler(c["id"]))
        if scheduled:
            logger.info(f"Re-armed {len(scheduled)} scheduled campaigns")
        # Also resume any running campaigns that were interrupted by a restart
        running = await db.broadcast_campaigns.find(
            {"status": "running"}, {"_id": 0, "id": 1}
        ).to_list(500)
        for c in running:
            task = asyncio.create_task(_csv_campaign_worker(c["id"]))
            _csv_campaign_workers[c["id"]] = task
        if running:
            logger.info(f"Resumed {len(running)} running campaigns")
        # Re-arm pending resends — campaigns that completed with a configured
        # resend but the resend task didn't finish (e.g. server restarted
        # while sleeping). Look for completed/paused campaigns with the
        # resend config set and `resend_done_at` not set.
        pending_resends = await db.broadcast_campaigns.find(
            {
                "status": {"$in": ["completed", "paused"]},
                "resend_after_hours": {"$gt": 0},
                "resend_template_name": {"$exists": True, "$ne": None, "$ne": ""},
                "resend_done_at": {"$exists": False},
                "completed_at": {"$exists": True, "$ne": None},
            },
            {"_id": 0, "id": 1}
        ).to_list(500)
        for c in pending_resends:
            asyncio.create_task(_csv_campaign_resend(c["id"]))
        if pending_resends:
            logger.info(f"Re-armed {len(pending_resends)} pending resends")
    except Exception as e:
        logger.error(f"campaign restart hook failed: {e}")


async def _csv_campaign_resend(campaign_id: str):
    """Auto-resend pass: after resend_after_hours, re-send to contacts who
    never read/replied to the first message. Uses resend_template_name.
    Same anti-spam rules as the first pass: cauta delay + night pause +
    optout exclusion at runtime + auto-pause on Meta rate-limit.
    """
    import random
    try:
        c = await db.broadcast_campaigns.find_one({"id": campaign_id}, {"_id": 0})
        if not c:
            return
        if c.get("resend_done_at"):
            logger.info(f"resend {campaign_id} already done, skipping")
            return
        hours = c.get("resend_after_hours") or 0
        tpl = c.get("resend_template_name")
        if not hours or not tpl:
            return

        # Sleep until completed_at + hours
        completed_at = c.get("completed_at")
        if completed_at:
            try:
                base = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                if base.tzinfo is None:
                    base = base.replace(tzinfo=timezone.utc)
                target = base + timedelta(hours=hours)
                delay = (target - datetime.now(timezone.utc)).total_seconds()
                if delay > 0:
                    logger.info(f"resend {campaign_id} sleeping {int(delay)}s until {target.isoformat()}")
                    await asyncio.sleep(delay)
            except Exception as _e:
                logger.debug(f"resend wakeup parse failed: {_e}")

        # Re-check: campaign still completed and not cancelled?
        c2 = await db.broadcast_campaigns.find_one({"id": campaign_id}, {"_id": 0})
        if not c2 or c2.get("status") == "cancelled" or c2.get("resend_done_at"):
            return

        line = await db.crm_lines.find_one({"id": c["line_id"]}, {"_id": 0})
        if not line:
            return
        token = line.get("whatsapp_token") or WHATSAPP_TOKEN
        phone_id = line.get("phone_number_id") or WHATSAPP_PHONE_NUMBER_ID
        if not token or not phone_id:
            await db.broadcast_campaigns.update_one(
                {"id": campaign_id},
                {"$set": {"resend_done_at": datetime.now(timezone.utc).isoformat(),
                          "resend_skipped_reason": "WhatsApp no configurado"}}
            )
            return

        # Mark resend as running
        await db.broadcast_campaigns.update_one(
            {"id": campaign_id},
            {"$set": {"resend_started_at": datetime.now(timezone.utc).isoformat(),
                      "status": "running", "paused_reason": "Auto-resend en curso"}}
        )

        # Targets: messages of THIS campaign in status sent/delivered, NOT replied,
        # and NOT already part of a previous resend (is_resend flag).
        targets = await db.broadcast_messages.find(
            {
                "campaign_id": campaign_id,
                "status": {"$in": ["sent", "delivered"]},
                "replied_at": {"$exists": False},
                "is_resend": {"$ne": True},
            },
            {"_id": 0, "phone": 1, "name": 1}
        ).to_list(100000)

        # Refresh optouts
        optouts = await db.broadcast_optouts.find(
            {"line_id": c["line_id"]}, {"_id": 0, "phone": 1}
        ).to_list(100000)
        optout_phones = {o["phone"] for o in optouts}

        # Need vars for the resend template? We don't know the var count of
        # the resend template here — keep it simple: re-use the same mapping
        # as the original. If the resend template has fewer vars Meta will
        # ignore extras, if it has more it'll fail (will be caught & logged).
        var_mapping = c.get("template_var_mapping") or []

        # Reload contacts for var values (audience or segment)
        if c.get("audience_id"):
            contacts_full = await db.broadcast_contacts.find(
                {"audience_id": c["audience_id"]}, {"_id": 0}
            ).to_list(100000)
        else:
            seg = BroadcastSegmentQuery(**c["segment"])
            contacts_full = await _resolve_segment(seg)
        contacts_by_phone = {ct["phone"]: ct for ct in contacts_full}

        for t in targets:
            # Cancel/pause check
            state = await db.broadcast_campaigns.find_one(
                {"id": campaign_id}, {"_id": 0, "status": 1}
            )
            if not state or state.get("status") not in ("running",):
                logger.info(f"resend {campaign_id} stopped: status={state.get('status') if state else 'missing'}")
                return

            phone = t["phone"]
            if phone in optout_phones:
                await db.broadcast_campaigns.update_one(
                    {"id": campaign_id}, {"$inc": {"stats.resend_skipped_optout": 1}}
                )
                continue

            # Night pause check
            while _is_night_pause_now():
                await db.broadcast_campaigns.update_one(
                    {"id": campaign_id},
                    {"$set": {"paused_reason": "Auto-resend en pausa nocturna 23:00-09:00 ART"}}
                )
                await asyncio.sleep(min(_seconds_until_morning(), 300))
                state = await db.broadcast_campaigns.find_one(
                    {"id": campaign_id}, {"_id": 0, "status": 1}
                )
                if not state or state.get("status") not in ("running",):
                    return
            await db.broadcast_campaigns.update_one(
                {"id": campaign_id}, {"$set": {"paused_reason": "Auto-resend en curso"}}
            )

            ct = contacts_by_phone.get(phone, {"name": t.get("name", ""), "vars": {}})
            tpl_vars: List[str] = []
            for col in var_mapping:
                if col == "name":
                    tpl_vars.append((ct.get("name") or "").strip() or "amigo")
                else:
                    v = (ct.get("vars") or {}).get(col, "")
                    tpl_vars.append(str(v) if v is not None else "")

            send_result = await wa_send_template(
                phone=phone,
                template_name=tpl,
                language=c.get("template_language") or "es_AR",
                variables=tpl_vars or None,
                token=token,
                phone_id=phone_id,
            )

            wa_msg_id = None
            err = None
            success = False
            if isinstance(send_result, dict):
                if "error" in send_result:
                    err = str(send_result.get("error"))[:300]
                elif send_result.get("messages"):
                    wa_msg_id = send_result["messages"][0].get("id")
                    success = True
                else:
                    err = str(send_result)[:300]

            doc = {
                "id": str(uuid.uuid4()),
                "campaign_id": campaign_id,
                "line_id": c["line_id"],
                "phone": phone,
                "name": ct.get("name", ""),
                "template_name": tpl,
                "wa_message_id": wa_msg_id,
                "status": "sent" if success else "failed",
                "error": err,
                "is_resend": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.broadcast_messages.insert_one(doc)
            inc = {"stats.resent": 1} if success else {"stats.resend_failed": 1}
            await db.broadcast_campaigns.update_one({"id": campaign_id}, {"$inc": inc})

            # Auto-pause on Meta rate-limit
            if err and any(k in err for k in ("131056", "80007", "rate", "OAuthException")):
                await db.broadcast_campaigns.update_one(
                    {"id": campaign_id},
                    {"$set": {"status": "paused", "paused_reason": f"Auto-resend pausado: {err[:80]}"}}
                )
                logger.warning(f"resend {campaign_id} auto-paused: {err[:120]}")
                return

            # Cauta delay
            delay = random.uniform(CAUTA_MIN_DELAY_S, CAUTA_MAX_DELAY_S)
            await asyncio.sleep(delay)

        # Done
        await db.broadcast_campaigns.update_one(
            {"id": campaign_id},
            {"$set": {
                "status": "completed",
                "resend_done_at": datetime.now(timezone.utc).isoformat(),
                "paused_reason": None,
            }}
        )
        logger.info(f"resend {campaign_id} completed")
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception(f"csv campaign resend {campaign_id} failed")
        await db.broadcast_campaigns.update_one(
            {"id": campaign_id},
            {"$set": {"resend_skipped_reason": f"resend error: {str(e)[:200]}"}}
        )



@api_router.post("/crm/broadcast/upload-image")
async def crm_broadcast_upload_image(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    """Upload an image for broadcast use (returns filename to pass to create)"""
    allowed = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Solo JPG/PNG/WebP")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Imagen muy grande (máx 5MB)")
    os.makedirs("/app/backend/uploads/broadcast", exist_ok=True)
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "jpg"
    name = f"{uuid.uuid4()}.{ext}"
    path = f"/app/backend/uploads/broadcast/{name}"
    with open(path, "wb") as f:
        f.write(data)
    return {"filename": name, "url": f"/api/crm/broadcast-image/{name}"}


@api_router.get("/crm/broadcast-image/{filename}")
async def crm_broadcast_get_image(filename: str, current_user=Depends(get_current_user)):
    from fastapi.responses import FileResponse
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Inválido")
    path = f"/app/backend/uploads/broadcast/{filename}"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No encontrada")
    return FileResponse(path)


@api_router.post("/crm/broadcast/upload-audio")
async def crm_broadcast_upload_audio(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    """Upload an audio for broadcast use (returns filename to pass to create).
    Accepted: ogg/opus (best — shows as PTT voice note), mp3, m4a, aac, amr, wav.
    Note: only ogg/opus is rendered as a voice-note (PTT) by WhatsApp.
    Otros formatos se envían como mensaje de audio reproducible (no PTT).
    """
    allowed_mimes = {
        "audio/ogg", "audio/opus",
        "audio/mpeg", "audio/mp3",
        "audio/mp4", "audio/m4a", "audio/x-m4a",
        "audio/aac",
        "audio/amr",
        "audio/wav", "audio/x-wav",
        "audio/webm",
    }
    if file.content_type not in allowed_mimes:
        raise HTTPException(status_code=400, detail=f"Formato no soportado ({file.content_type}). Usá ogg/opus, mp3, m4a, aac, amr, wav o webm.")
    data = await file.read()
    # WhatsApp limit: audio max 16MB. Damos 15MB de margen.
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Audio muy grande (máx 15MB)")
    os.makedirs("/app/backend/uploads/broadcast", exist_ok=True)
    # Map mime → extension
    ext_map = {
        "audio/ogg": "ogg", "audio/opus": "ogg",
        "audio/mpeg": "mp3", "audio/mp3": "mp3",
        "audio/mp4": "m4a", "audio/m4a": "m4a", "audio/x-m4a": "m4a",
        "audio/aac": "aac",
        "audio/amr": "amr",
        "audio/wav": "wav", "audio/x-wav": "wav",
        "audio/webm": "webm",
    }
    # Prefer extension from filename if present and valid, else from mime
    fname_ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    ext = fname_ext if fname_ext in {"ogg", "opus", "mp3", "m4a", "aac", "amr", "wav", "webm"} else ext_map.get(file.content_type, "mp3")
    if ext == "opus":
        ext = "ogg"  # WhatsApp espera .ogg para opus
    name = f"{uuid.uuid4()}.{ext}"
    path = f"/app/backend/uploads/broadcast/{name}"
    with open(path, "wb") as f:
        f.write(data)
    is_ptt_compatible = ext == "ogg"
    return {
        "filename": name,
        "url": f"/api/crm/broadcast-audio/{name}",
        "is_voice_note_compatible": is_ptt_compatible,
        "size_kb": round(len(data) / 1024),
    }


@api_router.get("/crm/broadcast-audio/{filename}")
async def crm_broadcast_get_audio(filename: str, current_user=Depends(get_current_user)):
    from fastapi.responses import FileResponse
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Inválido")
    path = f"/app/backend/uploads/broadcast/{filename}"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No encontrada")
    return FileResponse(path)


@api_router.post("/crm/broadcast")
async def crm_create_broadcast(data: BroadcastCreate, current_user=Depends(get_current_user)):
    """Create a broadcast job. Sends to all leads of selected line with target_status.
    - Admins can broadcast to any line.
    - Cajeros can only broadcast to lines they are assigned to (user.line_ids).
    """
    role = current_user.get("role")
    user_line_ids = current_user.get("line_ids", []) or []
    if role not in ("admin", "superadmin"):
        # Cajero: must be assigned to this line
        if data.line_id not in user_line_ids:
            raise HTTPException(status_code=403, detail="No tenés permiso para enviar masivos en esta línea")

    line = await db.crm_lines.find_one({"id": data.line_id}, {"_id": 0})
    if not line:
        raise HTTPException(status_code=404, detail="Línea no encontrada")
    if not line.get("whatsapp_token") or not line.get("phone_number_id"):
        raise HTTPException(status_code=400, detail="Línea sin credenciales de WhatsApp")
    if not data.message.strip() and not data.image_path and not data.audio_path:
        raise HTTPException(status_code=400, detail="El masivo debe tener mensaje, imagen o audio")

    # Find target leads
    target_leads = []
    cursor = db.crm_leads.find(
        {"line_id": data.line_id, "status": {"$in": data.target_status}, "phone": {"$ne": None}},
        {"_id": 0, "id": 1, "phone": 1, "name": 1}
    )
    async for lead in cursor:
        if lead.get("phone"):
            target_leads.append({"id": lead["id"], "phone": lead["phone"], "name": lead.get("name", "")})
    if not target_leads:
        raise HTTPException(status_code=400, detail="No hay leads con ese estado en la línea")

    broadcast_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": broadcast_id,
        "line_id": data.line_id,
        "line_name": line.get("name"),
        "created_by": current_user.get("email"),
        "created_at": now,
        "message": data.message,
        "image_path": data.image_path or None,
        "audio_path": data.audio_path or None,
        "audio_as_voice": bool(data.audio_as_voice),
        "target_status": data.target_status,
        "min_delay_sec": max(2, int(data.min_delay_sec)),
        "max_delay_sec": max(int(data.min_delay_sec) + 1, int(data.max_delay_sec)),
        "max_per_hour": min(max(int(data.max_per_hour), 10), 600),
        "total": len(target_leads),
        "sent": 0,
        "failed": 0,
        "skipped": 0,
        "status": "running",  # running | paused | done | cancelled
        "target_phones": [{"id": l["id"], "phone": l["phone"], "name": l["name"], "sent": False} for l in target_leads],
    }
    await db.crm_broadcasts.insert_one(doc)

    # Fire background worker (fire-and-forget)
    import asyncio
    task = asyncio.create_task(_broadcast_worker(broadcast_id, line))
    _broadcast_workers[broadcast_id] = task

    doc.pop("_id", None)
    doc.pop("target_phones", None)  # don't leak phone list in response
    return doc


async def _broadcast_worker(broadcast_id: str, line: dict):
    """Sends broadcast messages with jitter + rate-limit + cancel support."""
    import asyncio, random
    try:
        # Preload image media_id once (if image attached)
        image_media_id = None
        audio_media_id = None
        audio_as_voice = True
        bc = await db.crm_broadcasts.find_one({"id": broadcast_id})
        if not bc:
            return
        if bc.get("image_path"):
            img_path = f"/app/backend/uploads/broadcast/{bc['image_path']}"
            if os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    img_bytes = f.read()
                ext = bc["image_path"].rsplit(".", 1)[-1].lower() if "." in bc["image_path"] else "jpg"
                mime = {"png": "image/png", "webp": "image/webp", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/jpeg")
                up = await wa_upload_media(
                    file_bytes=img_bytes, filename=bc["image_path"], mime_type=mime,
                    token=line["whatsapp_token"], phone_id=line["phone_number_id"]
                )
                image_media_id = up.get("id") if isinstance(up, dict) else None

        if bc.get("audio_path"):
            audio_path = f"/app/backend/uploads/broadcast/{bc['audio_path']}"
            if os.path.exists(audio_path):
                with open(audio_path, "rb") as f:
                    audio_bytes = f.read()
                aext = bc["audio_path"].rsplit(".", 1)[-1].lower() if "." in bc["audio_path"] else "mp3"
                audio_mime = {
                    "ogg": "audio/ogg", "opus": "audio/ogg",
                    "mp3": "audio/mpeg", "mpeg": "audio/mpeg",
                    "m4a": "audio/mp4", "aac": "audio/aac",
                    "amr": "audio/amr", "wav": "audio/wav",
                    "webm": "audio/webm",
                }.get(aext, "audio/mpeg")
                up_audio = await wa_upload_media(
                    file_bytes=audio_bytes, filename=bc["audio_path"], mime_type=audio_mime,
                    token=line["whatsapp_token"], phone_id=line["phone_number_id"]
                )
                audio_media_id = up_audio.get("id") if isinstance(up_audio, dict) else None
                # Solo ogg/opus se renderiza como PTT; si no es ogg, forzamos voice=False
                audio_as_voice = bool(bc.get("audio_as_voice", True)) and (aext in ("ogg", "opus"))

        # Rate limiting: spread over time
        max_per_hour = bc["max_per_hour"]
        min_gap = 3600 / max_per_hour  # base seconds between sends

        sent = bc.get("sent", 0)
        failed = bc.get("failed", 0)
        targets = bc.get("target_phones", [])

        for idx, t in enumerate(targets):
            if t.get("sent"):
                continue
            # Check cancellation
            state = await db.crm_broadcasts.find_one({"id": broadcast_id}, {"status": 1})
            if not state or state.get("status") in ("cancelled", "paused"):
                logger.info(f"Broadcast {broadcast_id} stopped by status: {state.get('status') if state else 'missing'}")
                return

            # Personalize message with {nombre} {linea}
            first_name = (t.get("name") or "").split()[0] if t.get("name") else ""
            personalized = bc["message"].replace("{nombre}", first_name).replace("{linea}", line.get("name", ""))

            try:
                # Send logic:
                #   - Si hay imagen → imagen con caption (texto)
                #   - Si hay audio (sin imagen) → audio + texto separado (audio no soporta caption)
                #   - Si solo texto → texto plano
                res = None
                status_code = None
                if image_media_id:
                    res = await wa_send_image(
                        phone=t["phone"], media_id=image_media_id, caption=personalized,
                        token=line["whatsapp_token"], phone_id=line["phone_number_id"]
                    )
                elif audio_media_id:
                    res = await wa_send_audio(
                        phone=t["phone"], media_id=audio_media_id,
                        token=line["whatsapp_token"], phone_id=line["phone_number_id"],
                        as_voice=audio_as_voice,
                    )
                    # Si hay texto además del audio, lo mandamos como mensaje separado.
                    # WhatsApp audio NO soporta caption — por eso se envía aparte.
                    if personalized.strip():
                        await asyncio.sleep(random.uniform(0.8, 1.6))
                        await wa_send_text(
                            phone=t["phone"], message=personalized,
                            token=line["whatsapp_token"], phone_id=line["phone_number_id"]
                        )
                else:
                    res = await wa_send_text(
                        phone=t["phone"], message=personalized,
                        token=line["whatsapp_token"], phone_id=line["phone_number_id"]
                    )
                ok = isinstance(res, dict) and "error" not in res and res.get("messages")
                if isinstance(res, dict) and res.get("error"):
                    err = res.get("error")
                    if isinstance(err, dict):
                        status_code = err.get("code")

                # Log individual send
                await db.crm_broadcasts.update_one(
                    {"id": broadcast_id, "target_phones.id": t["id"]},
                    {"$set": {
                        "target_phones.$.sent": True,
                        "target_phones.$.success": bool(ok),
                        "target_phones.$.sent_at": datetime.now(timezone.utc).isoformat(),
                        "target_phones.$.result_code": status_code,
                    }}
                )
                if ok:
                    sent += 1
                    await db.crm_broadcasts.update_one({"id": broadcast_id}, {"$inc": {"sent": 1}})
                else:
                    failed += 1
                    await db.crm_broadcasts.update_one({"id": broadcast_id}, {"$inc": {"failed": 1}})
                    # If Meta returned 80007 (rate limit) or 131049 (phone quality) → pause
                    if status_code in (80007, 131049):
                        logger.warning(f"Broadcast {broadcast_id} paused by Meta (code={status_code})")
                        await db.crm_broadcasts.update_one({"id": broadcast_id}, {"$set": {"status": "paused", "paused_reason": f"Meta code {status_code}"}})
                        return
            except Exception as e:
                failed += 1
                logger.warning(f"Broadcast send error: {e}")
                await db.crm_broadcasts.update_one(
                    {"id": broadcast_id, "target_phones.id": t["id"]},
                    {"$set": {
                        "target_phones.$.sent": True,
                        "target_phones.$.success": False,
                        "target_phones.$.error": str(e)[:200],
                    }}
                )
                await db.crm_broadcasts.update_one({"id": broadcast_id}, {"$inc": {"failed": 1}})

            # Jittered delay between sends
            jitter = random.uniform(bc["min_delay_sec"], bc["max_delay_sec"])
            wait = max(jitter, min_gap)
            await asyncio.sleep(wait)

        # Mark done
        await db.crm_broadcasts.update_one(
            {"id": broadcast_id},
            {"$set": {"status": "done", "finished_at": datetime.now(timezone.utc).isoformat()}}
        )
        logger.info(f"Broadcast {broadcast_id} done: sent={sent}, failed={failed}")
    except asyncio.CancelledError:
        await db.crm_broadcasts.update_one(
            {"id": broadcast_id}, {"$set": {"status": "cancelled"}}
        )
    except Exception as e:
        logger.error(f"Broadcast worker {broadcast_id} fatal: {e}")
        await db.crm_broadcasts.update_one(
            {"id": broadcast_id}, {"$set": {"status": "error", "error": str(e)[:300]}}
        )
    finally:
        _broadcast_workers.pop(broadcast_id, None)


@api_router.get("/crm/broadcasts")
async def crm_list_broadcasts(limit: int = Query(30, le=200), current_user=Depends(get_current_user)):
    """List broadcasts. Cajero sees only their own; admin sees all."""
    role = current_user.get("role")
    query = {}
    if role not in ("admin", "superadmin"):
        query = {"created_by": current_user.get("email")}
    docs = []
    async for d in db.crm_broadcasts.find(query, {"_id": 0, "target_phones": 0}).sort("created_at", -1).limit(limit):
        docs.append(d)
    return {"broadcasts": docs}


@api_router.get("/crm/broadcast/{broadcast_id}")
async def crm_get_broadcast_detail(broadcast_id: str, current_user=Depends(get_current_user)):
    """Detail of a broadcast. Cajero can only view their own."""
    doc = await db.crm_broadcasts.find_one({"id": broadcast_id}, {"_id": 0, "target_phones": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Broadcast no encontrado")
    role = current_user.get("role")
    if role not in ("admin", "superadmin") and doc.get("created_by") != current_user.get("email"):
        raise HTTPException(status_code=403, detail="No tenés permiso para ver este masivo")
    return doc


@api_router.post("/crm/broadcast/{broadcast_id}/cancel")
async def crm_cancel_broadcast(broadcast_id: str, current_user=Depends(get_current_user)):
    """Cancel a broadcast. Creator can cancel their own, admin can cancel any."""
    bc = await db.crm_broadcasts.find_one({"id": broadcast_id}, {"_id": 0, "created_by": 1})
    if not bc:
        raise HTTPException(status_code=404, detail="Broadcast no encontrado")
    role = current_user.get("role")
    if role not in ("admin", "superadmin") and bc.get("created_by") != current_user.get("email"):
        raise HTTPException(status_code=403, detail="Solo podés cancelar tus propios masivos")
    await db.crm_broadcasts.update_one(
        {"id": broadcast_id}, {"$set": {"status": "cancelled"}}
    )
    task = _broadcast_workers.get(broadcast_id)
    if task and not task.done():
        task.cancel()
    return {"ok": True}


# ─── Health & Root ─────────────────────────────────────────────────

@api_router.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}

@api_router.get("/")
async def api_root():
    return {"message": "Traffic Guardian API", "version": "1.0.0"}

# ─── Setup ─────────────────────────────────────────────────────────

# Short URL router (must be separate, no prefix)
go_router = APIRouter()

@go_router.get("/l/{code}")
async def serve_wa_landing(code: str, request: Request):
    """Serve WhatsApp landing page with antibot cloaking"""
    landing = await db.wa_landings.find_one({"code": code, "is_active": True}, {"_id": 0})
    if not landing:
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=404)
    
    # Get request info for cloaking
    user_agent = request.headers.get("user-agent", "")
    ip = get_client_ip(request)
    headers_dict = dict(request.headers)
    
    # Check if it's a bot or Meta crawler
    bot_flag = is_bot(user_agent)
    meta_crawler = is_meta_crawler(user_agent)
    meta_ip = is_meta_ip(ip)
    vpn = detect_vpn(headers_dict)
    
    # If bot, Meta crawler, or Meta IP -> show safe page (NO PIXEL)
    if bot_flag or meta_crawler or meta_ip:
        logger.info(f"WA Landing {code}: Cloaking activated - bot={bot_flag}, meta_crawler={meta_crawler}, meta_ip={meta_ip}")
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=200)
    
    # Real user -> show actual landing WITH Pixel
    base_url = str(request.base_url).rstrip("/")
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto == "https":
        base_url = base_url.replace("http://", "https://")
    html = build_landing_html(landing, base_url)
    return HTMLResponse(content=html)

@go_router.get("/go/{short_code}")
async def track_short(short_code: str, request: Request):
    campaign = await db.campaigns.find_one({"short_code": short_code}, {"_id": 0})
    if not campaign or not campaign.get("is_active"):
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=404)
    if campaign.get("clicks_today", 0) >= campaign.get("daily_click_limit", 10000):
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=429)

    ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    referrer = request.headers.get("referer", "")
    headers_dict = dict(request.headers)

    device, os_name, browser = parse_device_info(user_agent)
    country = "XX"
    bot_flag = is_bot(user_agent)
    meta = is_meta_crawler(user_agent)
    vpn = detect_vpn(headers_dict)
    fingerprint = generate_fingerprint(ip, user_agent, headers_dict)
    score = calculate_behavioral_score(bot_flag, vpn, False, bool(referrer), user_agent)

    config = {k: campaign.get(k, [] if 'ips' in k or 'allowed' in k else False) for k in
              ['allowed_countries', 'allowed_devices', 'allowed_os', 'block_empty_referrer', 'blacklist_ips', 'whitelist_ips']}
    blocked, block_reason = should_block(config, ip, country, device, os_name, referrer, bot_flag, vpn)

    is_real_device = device in ('Mobile', 'Tablet', 'Desktop')
    if not blocked and not is_meta_ip(ip):
        ai_rules_list = await db.ai_rules.find({"is_active": True}, {"_id": 0}).to_list(100)
        for rule in ai_rules_list:
            field_map = {"country": country, "device": device, "os": os_name, "browser": browser,
                         "ip": ip, "referrer": referrer, "bot": str(bot_flag).lower(),
                         "vpn": str(vpn).lower(), "score": str(score)}
            field_val = field_map.get(rule.get("field", ""), "")
            op = rule.get("operator", "equals")
            rule_val = str(rule.get("value", ""))
            matched = False
            if op == "equals": matched = field_val.lower() == rule_val.lower()
            elif op == "not_equals": matched = field_val.lower() != rule_val.lower()
            elif op == "contains": matched = rule_val.lower() in field_val.lower()
            elif op == "in_list": matched = field_val.lower() in [v.strip().lower() for v in rule_val.split(",")]
            elif op == "greater_than":
                try: matched = float(field_val) > float(rule_val)
                except ValueError: pass
            elif op == "less_than":
                try: matched = float(field_val) < float(rule_val)
                except ValueError: pass
            if matched:
                if rule.get("type") == "block" and not is_real_device:
                    blocked, block_reason = True, f"IA: {rule.get('reason', 'Regla automática')}"
                elif rule.get("type") == "allow":
                    blocked, block_reason = False, ""
                break

    click = {
        "id": str(uuid.uuid4()), "campaign_id": campaign["id"],
        "ip": ip, "country": country, "user_agent": user_agent,
        "device": device, "os": os_name, "browser": browser,
        "referrer": referrer, "is_bot": bot_flag, "is_vpn": vpn,
        "is_datacenter": False, "is_blocked": blocked,
        "block_reason": block_reason if blocked else None,
        "fingerprint_hash": fingerprint, "behavioral_score": score,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.clicks.insert_one(click)
    await db.campaigns.update_one({"id": campaign["id"]}, {"$inc": {"clicks_today": 1, "total_clicks": 1}})

    safe_url = campaign.get("safe_page_url")
    if meta or blocked:
        if meta and campaign.get("landing_html"):
            return HTMLResponse(content=campaign["landing_html"])
        return RedirectResponse(url=safe_url, status_code=302) if safe_url else HTMLResponse(content=SAFE_PAGE_HTML)
    if campaign.get("landing_html"):
        return HTMLResponse(content=campaign["landing_html"])
    return RedirectResponse(url=campaign["target_url"], status_code=302)

@go_router.get("/")
async def root_handler(request: Request, c: str = None):
    # If ?c= parameter present, use it as short_code for tracking
    if c:
        campaign = await db.campaigns.find_one({"short_code": c}, {"_id": 0})
        if not campaign or not campaign.get("is_active"):
            return HTMLResponse(content=SAFE_PAGE_HTML, status_code=404)
        if campaign.get("clicks_today", 0) >= campaign.get("daily_click_limit", 10000):
            return HTMLResponse(content=SAFE_PAGE_HTML, status_code=429)

        ip = get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        referrer = request.headers.get("referer", "")
        headers_dict = dict(request.headers)

        device, os_name, browser = parse_device_info(user_agent)
        country = "XX"
        bot_flag = is_bot(user_agent)
        meta = is_meta_crawler(user_agent)
        vpn = detect_vpn(headers_dict)
        fingerprint = generate_fingerprint(ip, user_agent, headers_dict)
        score = calculate_behavioral_score(bot_flag, vpn, False, bool(referrer), user_agent)

        config = {k: campaign.get(k, [] if 'ips' in k or 'allowed' in k else False) for k in
                  ['allowed_countries', 'allowed_devices', 'allowed_os', 'block_empty_referrer', 'blacklist_ips', 'whitelist_ips']}
        blocked, block_reason = should_block(config, ip, country, device, os_name, referrer, bot_flag, vpn)

        is_real_device = device in ('Mobile', 'Tablet', 'Desktop')
        if not blocked and not is_meta_ip(ip):
            ai_rules_list = await db.ai_rules.find({"is_active": True}, {"_id": 0}).to_list(100)
            for rule in ai_rules_list:
                field_map = {"country": country, "device": device, "os": os_name, "browser": browser,
                             "ip": ip, "referrer": referrer, "bot": str(bot_flag).lower(),
                             "vpn": str(vpn).lower(), "score": str(score)}
                field_val = field_map.get(rule.get("field", ""), "")
                op = rule.get("operator", "equals")
                rule_val = str(rule.get("value", ""))
                matched = False
                if op == "equals": matched = field_val.lower() == rule_val.lower()
                elif op == "not_equals": matched = field_val.lower() != rule_val.lower()
                elif op == "contains": matched = rule_val.lower() in field_val.lower()
                elif op == "in_list": matched = field_val.lower() in [v.strip().lower() for v in rule_val.split(",")]
                elif op == "greater_than":
                    try: matched = float(field_val) > float(rule_val)
                    except ValueError: pass
                elif op == "less_than":
                    try: matched = float(field_val) < float(rule_val)
                    except ValueError: pass
                if matched:
                    if rule.get("type") == "block" and not is_real_device:
                        blocked, block_reason = True, f"IA: {rule.get('reason', 'Regla automática')}"
                    elif rule.get("type") == "allow":
                        blocked, block_reason = False, ""
                    break

        click = {
            "id": str(uuid.uuid4()), "campaign_id": campaign["id"],
            "ip": ip, "country": country, "user_agent": user_agent,
            "device": device, "os": os_name, "browser": browser,
            "referrer": referrer, "is_bot": bot_flag, "is_vpn": vpn,
            "is_datacenter": False, "is_blocked": blocked,
            "block_reason": block_reason if blocked else None,
            "fingerprint_hash": fingerprint, "behavioral_score": score,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.clicks.insert_one(click)
        await db.campaigns.update_one({"id": campaign["id"]}, {"$inc": {"clicks_today": 1, "total_clicks": 1}})

        safe_url = campaign.get("safe_page_url")
        if meta or blocked:
            # Meta crawler or blocked: show safe page or landing (for Meta to see real content)
            if meta and campaign.get("landing_html"):
                return HTMLResponse(content=campaign["landing_html"])
            return RedirectResponse(url=safe_url, status_code=302) if safe_url else HTMLResponse(content=SAFE_PAGE_HTML)
        # Serve landing HTML directly (no redirect = Meta approves)
        if campaign.get("landing_html"):
            return HTMLResponse(content=campaign["landing_html"])
        return RedirectResponse(url=campaign["target_url"], status_code=302)

    # No ?c= parameter: serve root with meta verification if any campaign has it
    meta_tag = ""
    camp_with_meta = await db.campaigns.find_one(
        {"meta_verification": {"$exists": True, "$type": "string", "$ne": ""}},
        {"meta_verification": 1, "_id": 0}
    )
    if camp_with_meta and camp_with_meta.get("meta_verification"):
        meta_tag = f'<meta name="facebook-domain-verification" content="{camp_with_meta["meta_verification"]}" />'
    return HTMLResponse(content=f"""<!DOCTYPE html><html><head><meta charset="UTF-8">{meta_tag}
<title>Traffic Guardian</title></head><body style="font-family:sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:#0f172a;color:white;">
<div style="text-align:center"><h1 style="font-size:2.5rem;margin-bottom:8px;">Traffic Guardian</h1><p style="color:#94a3b8;">Service is running</p></div></body></html>""")

# CORS
cors_env = os.environ.get('CORS_ORIGINS', '')
if not cors_env or cors_env.strip() == '*':
    _origins = ["*"]
    _creds = False
else:
    _origins = [o.strip() for o in cors_env.split(',') if o.strip()]
    _creds = True

# Middleware to handle proxy headers (Railway uses reverse proxy)
@app.middleware("http")
async def force_https_redirects(request: Request, call_next):
    response = await call_next(request)
    # If there's a redirect, ensure it uses HTTPS
    if response.status_code in (301, 302, 307, 308):
        location = response.headers.get("location", "")
        if location.startswith("http://") and "localhost" not in location:
            response.headers["location"] = location.replace("http://", "https://", 1)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_credentials=_creds,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression: reduces JSON payload egress by ~70% on lead lists,
# message threads, and stats endpoints. Transparent to clients (browsers
# auto-decompress via the standard Accept-Encoding header). minimum_size=1000
# avoids compressing tiny responses where overhead outweighs savings.
from starlette.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(go_router)
# Note: api_router is included at the END of the file after ALL routes
# have been registered (including the Marketing Dashboard endpoints).

@app.on_event("startup")
async def startup():
    logger.info(f"MONGO_URL: {mongo_url[:20]}...{mongo_url[-10:]}")
    logger.info(f"DB_NAME: {db_name}")
    logger.info(f"CORS_ORIGINS: {os.environ.get('CORS_ORIGINS', 'NOT SET')}")
    # Test MongoDB connection
    try:
        await client.admin.command('ping')
        logger.info("MongoDB connection: OK")
    except Exception as e:
        logger.error(f"MongoDB connection FAILED: {e}")
        return
    # Create admin user if not exists
    existing = await db.users.find_one({"email": "admin@maxi.com"})
    if not existing:
        hashed = pwd_context.hash("admin123")
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": "admin@maxi.com",
            "hashed_password": hashed,
            "role": "admin",
            "is_active": True,
            "welcome_message": "",
            "user_message": "",
            "line_ids": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("Admin user created: admin@maxi.com")
    # Create cajero user if not exists 
#    existing_cajero = await db.users.find_one({"email": "cajero@blackguardian.com"})
#    if not existing_cajero:
#        hashed_cajero = pwd_context.hash("cajero123")  # cambiá esto
#        await db.users.insert_one({
#            "id": str(uuid.uuid4()),
#            "email": "cajero@blackguardian.com",
#            "hashed_password": hashed_cajero,
#            "role": "cajero",
#            "is_active": True,
#            "created_at": datetime.now(timezone.utc).isoformat(),
#        })
#        logger.info("Cajero user created: cajero@blackguardian.com")
#    existing_ares = await db.users.find_one({"email": "ares@blackguardian.com"})
#    if not existing_ares:
#        hashed_ares = pwd_context.hash("ares123456")
#        await db.users.insert_one({
#            "id": str(uuid.uuid4()),
#            "email": "ares@blackguardian.com",
#            "hashed_password": hashed_ares,
#            "role": "cajero",
#            "line_ids": ["268bfa4d-a908-4d6b-a371-815a3d35b772"],
#            "is_active": True,
#            "created_at": datetime.now(timezone.utc).isoformat(),
#        })
#        logger.info("Cajero user created: ares@blackguardian.com")

    
    # Create indexes
    await db.clicks.create_index("campaign_id")
    await db.clicks.create_index("created_at")
    await db.clicks.create_index("ip")
    await db.campaigns.create_index("id", unique=True)
    await db.campaigns.create_index("short_code", unique=True, sparse=True)
    await db.custom_filters.create_index("id", unique=True)
    await db.ai_pages.create_index("id", unique=True)
    await db.ai_rules.create_index("id", unique=True)
    await db.ai_rules.create_index("is_active")
    await db.ai_insights.create_index("id", unique=True)
    await db.wa_contacts.create_index("phone", unique=True)
    await db.wa_contacts.create_index("classification")
    await db.wa_messages.create_index("phone")
    await db.wa_messages.create_index("created_at")
    await db.wa_landings.create_index("id", unique=True)
    await db.wa_landings.create_index("code", unique=True)
    await db.wa_clicks.create_index("landing_code")
    await db.wa_clicks.create_index("click_id")
    await db.wa_clicks.create_index("created_at")
    # CRM indexes
    await db.crm_leads.create_index("id", unique=True)
    await db.crm_leads.create_index("status")
    await db.crm_leads.create_index("created_at")
    await db.crm_leads.create_index("phone")
    await db.crm_leads.create_index([("phone", 1), ("line_id", 1)])
    await db.crm_messages.create_index("lead_id")
    await db.crm_messages.create_index("created_at")
    await db.crm_receipts.create_index("id", unique=True)
    await db.crm_receipts.create_index("lead_id")
    await db.crm_receipts.create_index("status")
    await db.crm_lines.create_index("id", unique=True)
    await db.crm_lines.create_index("line_type")
    await db.crm_lines.create_index("whatsapp_number")
    # Migrate existing campaigns without short_code
    async for camp in db.campaigns.find({"short_code": {"$exists": False}}):
        code = generate_short_code()
        while await db.campaigns.find_one({"short_code": code}):
            code = generate_short_code()
        await db.campaigns.update_one({"_id": camp["_id"]}, {"$set": {"short_code": code}})
        logger.info(f"Migrated campaign {camp.get('name', camp['id'])} -> /go/{code}")
    logger.info("Traffic Guardian API started successfully")

# ─── Marketing Dashboard (admin only) ──────────────────────────────
# Aggregate analytics endpoints powering /dashboard. All require admin.

def _dashboard_role_guard(user):
    if user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Solo administradores")


def _dashboard_date_range(days: int, start_date: Optional[str], end_date: Optional[str]):
    """Return (start_iso, end_iso) strings for Mongo range queries."""
    if start_date and end_date:
        return start_date, end_date
    now = datetime.now(timezone.utc)
    return (now - timedelta(days=days)).isoformat(), now.isoformat()


@api_router.get("/crm/contacts/history")
async def crm_contacts_history(
    fmt: str = Query("json", regex="^(json|csv)$"),
    current_user=Depends(get_current_user),
):
    """Histórico de contactos para los cajeros: teléfono + monto cargado total
    + cantidad de interacciones. Solo cajero (admin no la pidió). Filtrado
    automáticamente por las líneas asignadas al cajero.

    `fmt=csv` devuelve un archivo CSV listo para descargar.
    """
    role = current_user.get("role")
    if role not in ("cajero", "admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Sin permisos")

    user_line_ids = current_user.get("line_ids") or []
    match: dict = {}
    if role == "cajero":
        if not user_line_ids:
            return [] if fmt == "json" else _csv_response([], filename="contactos.csv")
        match["line_id"] = {"$in": user_line_ids}

    pipe = [
        {"$match": match},
        {"$group": {
            "_id": "$phone",
            "name": {"$last": "$name"},
            "total_cargado": {"$sum": {"$ifNull": ["$charge_amount", 0]}},
            "messages": {"$sum": {"$ifNull": ["$messages_count", 0]}},
            "ultima_interaccion": {"$max": "$last_interaction"},
            "primera_interaccion": {"$min": "$created_at"},
            "veces_contactado": {"$sum": 1},
        }},
        {"$sort": {"total_cargado": -1, "ultima_interaccion": -1}},
        {"$limit": 5000},
    ]
    rows = await db.crm_leads.aggregate(pipe).to_list(5000)
    out = [{
        "phone": r["_id"] or "",
        "name": r.get("name") or "",
        "total_cargado": round(float(r.get("total_cargado") or 0), 2),
        "veces_contactado": r.get("veces_contactado") or 0,
        "mensajes": r.get("messages") or 0,
        "primera_interaccion": (r.get("primera_interaccion") or "")[:10],
        "ultima_interaccion": (r.get("ultima_interaccion") or "")[:10],
    } for r in rows if r.get("_id")]

    if fmt == "csv":
        return _csv_response(out, filename="contactos.csv")
    return out


def _csv_response(rows: list, filename: str = "export.csv"):
    """Render a list of dicts as a CSV streaming response (UTF-8 BOM for Excel)."""
    import csv
    import io
    from fastapi.responses import StreamingResponse

    buf = io.StringIO()
    buf.write("\ufeff")  # BOM so Excel opens UTF-8 properly
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    else:
        buf.write("phone,name,total_cargado,veces_contactado,mensajes,primera_interaccion,ultima_interaccion\n")
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api_router.get("/dashboard/overview")
async def dashboard_overview(
    line_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """KPIs + period-over-period comparison + quick insights."""
    _dashboard_role_guard(current_user)
    s, e = _dashboard_date_range(days, start_date, end_date)
    line_q = {"line_id": line_id} if line_id else {}

    cur_match = {**line_q, "created_at": {"$gte": s, "$lte": e}}
    cur_leads = await db.crm_leads.count_documents(cur_match)
    cur_validos_match = {**cur_match, "status": "valido"}
    cur_validos = await db.crm_leads.count_documents(cur_validos_match)
    agg = await db.crm_leads.aggregate([
        {"$match": cur_validos_match},
        {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$charge_amount", 0]}}}},
    ]).to_list(1)
    total_revenue = float(agg[0]["total"]) if agg else 0.0
    avg_ticket = (total_revenue / cur_validos) if cur_validos else 0.0
    conv_rate = (cur_validos / cur_leads * 100) if cur_leads else 0.0

    # Previous period comparison
    try:
        s_dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        e_dt = datetime.fromisoformat(e.replace("Z", "+00:00"))
        span = e_dt - s_dt
        prev_e = s_dt
        prev_s = prev_e - span
        prev_match = {**line_q, "created_at": {"$gte": prev_s.isoformat(), "$lt": prev_e.isoformat()}}
        prev_leads = await db.crm_leads.count_documents(prev_match)
        prev_validos = await db.crm_leads.count_documents({**prev_match, "status": "valido"})
        prev_conv = (prev_validos / prev_leads * 100) if prev_leads else 0.0
    except Exception:
        prev_leads, prev_validos, prev_conv = 0, 0, 0.0

    def _delta_pct(cur, prev):
        if not prev:
            return None
        return round((cur - prev) / prev * 100, 1)

    # Top ad by conversions
    top_ad_pipe = [
        {"$match": {**cur_match, "ad_source": {"$nin": [None, ""]}}},
        {"$group": {
            "_id": "$ad_source",
            "leads": {"$sum": 1},
            "validos": {"$sum": {"$cond": [{"$eq": ["$status", "valido"]}, 1, 0]}},
            "revenue": {"$sum": {"$ifNull": ["$charge_amount", 0]}},
        }},
        {"$sort": {"validos": -1, "leads": -1}},
        {"$limit": 1},
    ]
    top_ad_res = await db.crm_leads.aggregate(top_ad_pipe).to_list(1)
    top_ad = None
    if top_ad_res:
        r = top_ad_res[0]
        top_ad = {
            "ad_source": r["_id"],
            "leads": r["leads"],
            "conversiones": r["validos"],
            "revenue": float(r["revenue"] or 0),
            "conversion_rate": round((r["validos"] / r["leads"] * 100), 1) if r["leads"] else 0,
        }

    # Quick insights — best converting gender + best converting location
    insights = []
    try:
        gender_pipe = [
            {"$match": {**cur_match, "gender": {"$in": ["m", "f"]}}},
            {"$group": {"_id": "$gender", "leads": {"$sum": 1},
                        "validos": {"$sum": {"$cond": [{"$eq": ["$status", "valido"]}, 1, 0]}}}},
        ]
        g_res = await db.crm_leads.aggregate(gender_pipe).to_list(2)
        if len(g_res) == 2:
            rates = {r["_id"]: (r["validos"] / r["leads"] * 100 if r["leads"] else 0) for r in g_res}
            if rates.get("m") and rates.get("f"):
                diff = abs(rates["m"] - rates["f"])
                if diff >= 5:
                    winner = "Masculino" if rates["m"] > rates["f"] else "Femenino"
                    insights.append(f"Los leads {winner.lower()}s convierten {round(diff,1)}% mejor que el promedio")

        state_pipe = [
            {"$match": {**cur_match, "state": {"$nin": [None, ""]}}},
            {"$group": {"_id": "$state", "leads": {"$sum": 1},
                        "validos": {"$sum": {"$cond": [{"$eq": ["$status", "valido"]}, 1, 0]}}}},
            {"$match": {"leads": {"$gte": 5}}},
            {"$sort": {"validos": -1}},
            {"$limit": 1},
        ]
        st_res = await db.crm_leads.aggregate(state_pipe).to_list(1)
        if st_res and st_res[0]["leads"]:
            rate = round(st_res[0]["validos"] / st_res[0]["leads"] * 100, 1)
            insights.append(f"{st_res[0]['_id']} es la provincia con mejor conversión ({rate}%)")
    except Exception:
        pass

    return {
        "period": {"start": s, "end": e},
        "kpis": {
            "total_leads": cur_leads,
            "conversiones": cur_validos,
            "conversion_rate": round(conv_rate, 2),
            "total_revenue": round(total_revenue, 2),
            "avg_ticket": round(avg_ticket, 2),
        },
        "deltas": {
            "total_leads": _delta_pct(cur_leads, prev_leads),
            "conversiones": _delta_pct(cur_validos, prev_validos),
            "conversion_rate": _delta_pct(conv_rate, prev_conv),
        },
        "top_ad": top_ad,
        "insights": insights,
    }


@api_router.get("/dashboard/ad-performance")
async def dashboard_ad_performance(
    line_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """Ad performance table with preview thumbnails and ROAS."""
    _dashboard_role_guard(current_user)
    s, e = _dashboard_date_range(days, start_date, end_date)
    line_q = {"line_id": line_id} if line_id else {}
    match = {**line_q, "created_at": {"$gte": s, "$lte": e}, "ad_source": {"$nin": [None, ""]}}

    pipe = [
        {"$match": match},
        {"$group": {
            "_id": "$ad_source",
            "leads": {"$sum": 1},
            "validos": {"$sum": {"$cond": [{"$eq": ["$status", "valido"]}, 1, 0]}},
            "spam": {"$sum": {"$cond": [{"$eq": ["$status", "spam"]}, 1, 0]}},
            "revenue": {"$sum": {"$ifNull": ["$charge_amount", 0]}},
            # Grab a sample lead id per ad so we can resolve a preview image
            "sample_lead_id": {"$first": "$id"},
            "sample_referral": {"$first": "$referral"},
            "sample_utm": {"$first": "$utm_content"},
        }},
        {"$sort": {"leads": -1}},
        {"$limit": 50},
    ]
    rows = await db.crm_leads.aggregate(pipe).to_list(50)

    out = []
    for r in rows:
        ref = r.get("sample_referral") or {}
        preview_image = ref.get("image_url") or ref.get("thumbnail_url")
        headline = ref.get("headline") or r["_id"]
        body = ref.get("body") or ""
        source_url = ref.get("source_url")
        out.append({
            "ad_source": r["_id"],
            "leads": r["leads"],
            "conversiones": r["validos"],
            "spam": r["spam"],
            "revenue": round(float(r["revenue"] or 0), 2),
            "avg_ticket": round(float(r["revenue"] or 0) / r["validos"], 2) if r["validos"] else 0.0,
            "conversion_rate": round((r["validos"] / r["leads"] * 100), 2) if r["leads"] else 0,
            "preview_image": preview_image,
            "headline": headline,
            "body": body,
            "source_url": source_url,
            "sample_lead_id": r.get("sample_lead_id"),
        })
    return out


@api_router.get("/dashboard/demographics")
async def dashboard_demographics(
    line_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """Gender and age-range breakdown."""
    _dashboard_role_guard(current_user)
    s, e = _dashboard_date_range(days, start_date, end_date)
    line_q = {"line_id": line_id} if line_id else {}
    match = {**line_q, "created_at": {"$gte": s, "$lte": e}}

    # Gender
    gender_pipe = [
        {"$match": match},
        {"$group": {
            "_id": {"$ifNull": ["$gender", "unknown"]},
            "leads": {"$sum": 1},
            "validos": {"$sum": {"$cond": [{"$eq": ["$status", "valido"]}, 1, 0]}},
            "revenue": {"$sum": {"$ifNull": ["$charge_amount", 0]}},
        }},
    ]
    g_rows = await db.crm_leads.aggregate(gender_pipe).to_list(10)
    gender_labels = {"m": "Masculino", "f": "Femenino", "unknown": "Desconocido"}
    gender = [{
        "label": gender_labels.get(r["_id"], str(r["_id"]).title() or "Desconocido"),
        "key": r["_id"] or "unknown",
        "leads": r["leads"],
        "conversiones": r["validos"],
        "revenue": round(float(r["revenue"] or 0), 2),
        "conversion_rate": round((r["validos"] / r["leads"] * 100), 1) if r["leads"] else 0,
    } for r in g_rows]

    # Age — bucket into ranges 18-24, 25-34, 35-44, 45-54, 55+
    age_buckets = [
        {"label": "18-24", "min": 18, "max": 24},
        {"label": "25-34", "min": 25, "max": 34},
        {"label": "35-44", "min": 35, "max": 44},
        {"label": "45-54", "min": 45, "max": 54},
        {"label": "55+", "min": 55, "max": 120},
    ]
    age_results = []
    for b in age_buckets:
        b_match = {**match, "inferred_age": {"$gte": b["min"], "$lte": b["max"]}}
        total = await db.crm_leads.count_documents(b_match)
        validos = await db.crm_leads.count_documents({**b_match, "status": "valido"})
        rev_agg = await db.crm_leads.aggregate([
            {"$match": {**b_match, "status": "valido"}},
            {"$group": {"_id": None, "r": {"$sum": {"$ifNull": ["$charge_amount", 0]}}}},
        ]).to_list(1)
        age_results.append({
            "range": b["label"],
            "leads": total,
            "conversiones": validos,
            "revenue": round(float(rev_agg[0]["r"]) if rev_agg else 0, 2),
            "conversion_rate": round((validos / total * 100), 1) if total else 0,
        })
    age_unknown = await db.crm_leads.count_documents({
        **match,
        "$or": [{"inferred_age": {"$exists": False}}, {"inferred_age": None}],
    })

    return {"gender": gender, "age": age_results, "age_unknown": age_unknown}


@api_router.get("/dashboard/geography")
async def dashboard_geography(
    line_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """Top provinces/cities with conversion rates."""
    _dashboard_role_guard(current_user)
    s, e = _dashboard_date_range(days, start_date, end_date)
    line_q = {"line_id": line_id} if line_id else {}
    match = {**line_q, "created_at": {"$gte": s, "$lte": e}}

    def _format(rows):
        return [{
            "name": r["_id"] or "Desconocido",
            "leads": r["leads"],
            "conversiones": r["validos"],
            "revenue": round(float(r.get("revenue", 0) or 0), 2),
            "conversion_rate": round((r["validos"] / r["leads"] * 100), 1) if r["leads"] else 0,
        } for r in rows]

    province_pipe = [
        {"$match": {**match, "state": {"$nin": [None, ""]}}},
        {"$group": {
            "_id": "$state",
            "leads": {"$sum": 1},
            "validos": {"$sum": {"$cond": [{"$eq": ["$status", "valido"]}, 1, 0]}},
            "revenue": {"$sum": {"$ifNull": ["$charge_amount", 0]}},
        }},
        {"$sort": {"leads": -1}},
        {"$limit": 15},
    ]
    city_pipe = [
        {"$match": {**match, "city": {"$nin": [None, ""]}}},
        {"$group": {
            "_id": "$city",
            "leads": {"$sum": 1},
            "validos": {"$sum": {"$cond": [{"$eq": ["$status", "valido"]}, 1, 0]}},
            "revenue": {"$sum": {"$ifNull": ["$charge_amount", 0]}},
        }},
        {"$sort": {"leads": -1}},
        {"$limit": 15},
    ]
    country_pipe = [
        {"$match": {**match, "country": {"$nin": [None, ""]}}},
        {"$group": {
            "_id": "$country",
            "leads": {"$sum": 1},
            "validos": {"$sum": {"$cond": [{"$eq": ["$status", "valido"]}, 1, 0]}},
            "revenue": {"$sum": {"$ifNull": ["$charge_amount", 0]}},
        }},
        {"$sort": {"leads": -1}},
        {"$limit": 10},
    ]

    p_rows = await db.crm_leads.aggregate(province_pipe).to_list(15)
    c_rows = await db.crm_leads.aggregate(city_pipe).to_list(15)
    cn_rows = await db.crm_leads.aggregate(country_pipe).to_list(10)
    return {
        "provinces": _format(p_rows),
        "cities": _format(c_rows),
        "countries": _format(cn_rows),
    }


@api_router.get("/dashboard/timeline")
async def dashboard_timeline(
    line_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """Per-day leads + conversions for area chart."""
    _dashboard_role_guard(current_user)
    s, e = _dashboard_date_range(days, start_date, end_date)
    line_q = {"line_id": line_id} if line_id else {}
    match = {**line_q, "created_at": {"$gte": s, "$lte": e}}

    pipe = [
        {"$match": match},
        {"$addFields": {
            "day": {"$substr": ["$created_at", 0, 10]},
        }},
        {"$group": {
            "_id": "$day",
            "leads": {"$sum": 1},
            "conversiones": {"$sum": {"$cond": [{"$eq": ["$status", "valido"]}, 1, 0]}},
            "revenue": {"$sum": {"$ifNull": ["$charge_amount", 0]}},
        }},
        {"$sort": {"_id": 1}},
    ]
    rows = await db.crm_leads.aggregate(pipe).to_list(400)
    return [{
        "date": r["_id"],
        "leads": r["leads"],
        "conversiones": r["conversiones"],
        "revenue": round(float(r["revenue"] or 0), 2),
    } for r in rows]


@api_router.get("/dashboard/hourly-heatmap")
async def dashboard_hourly_heatmap(
    line_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """Day-of-week x hour-of-day heatmap (UTC-3 / Argentina)."""
    _dashboard_role_guard(current_user)
    s, e = _dashboard_date_range(days, start_date, end_date)
    line_q = {"line_id": line_id} if line_id else {}
    match = {**line_q, "created_at": {"$gte": s, "$lte": e}}

    pipe = [
        {"$match": match},
        # Convert ISO string -> date, shift to Argentina tz (UTC-3)
        {"$addFields": {
            "ts": {"$dateFromString": {"dateString": "$created_at", "onError": None}},
        }},
        {"$match": {"ts": {"$ne": None}}},
        {"$addFields": {
            "local_ts": {"$dateAdd": {"startDate": "$ts", "unit": "hour", "amount": -3}},
        }},
        {"$group": {
            "_id": {
                "dow": {"$dayOfWeek": "$local_ts"},   # 1=Sun ... 7=Sat
                "hour": {"$hour": "$local_ts"},
            },
            "leads": {"$sum": 1},
        }},
    ]
    rows = await db.crm_leads.aggregate(pipe).to_list(7 * 24)
    # Rearrange so Monday=0 ... Sunday=6 (Spanish convention)
    matrix = [[0] * 24 for _ in range(7)]
    for r in rows:
        dow_mongo = r["_id"]["dow"]        # 1..7 (Sun..Sat)
        hour = r["_id"]["hour"]
        # Convert to Mon=0..Sun=6
        mon_based = (dow_mongo - 2) % 7
        matrix[mon_based][hour] = r["leads"]
    labels = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    return {"labels": labels, "matrix": matrix}


@api_router.get("/dashboard/device-stats")
async def dashboard_device_stats(
    line_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """Device / OS breakdown from wa_clicks."""
    _dashboard_role_guard(current_user)
    s, e = _dashboard_date_range(days, start_date, end_date)
    match: dict = {"created_at": {"$gte": s, "$lte": e}}
    if line_id:
        match["line_id"] = line_id

    async def _agg(field):
        pipe = [
            {"$match": {**match, field: {"$nin": [None, ""]}}},
            {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]
        try:
            rows = await db.wa_clicks.aggregate(pipe).to_list(10)
        except Exception:
            rows = []
        return [{"name": r["_id"] or "Desconocido", "count": r["count"]} for r in rows]

    return {
        "devices": await _agg("device"),
        "os": await _agg("os"),
        "browsers": await _agg("browser"),
    }


# ─── Router registration (MUST be after all @api_router decorators) ──
app.include_router(api_router)


@app.on_event("shutdown")
async def shutdown():
    client.close()
