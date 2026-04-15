from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Query, Response
from fastapi.responses import RedirectResponse, HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
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
import httpx
import bcrypt

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
    }
class UserCreate(BaseModel):
    email: str
    password: str
    role: str = "cajero"
    line_ids: List[str] = []
    welcome_message: Optional[str] = ""
    user_message: Optional[str] = ""

class UserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    line_ids: Optional[List[str]] = None
    welcome_message: Optional[str] = None
    user_message: Optional[str] = None
    is_active: Optional[bool] = None

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
        elif v is not None:
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
                            {"$inc": {"messages_count": 1}}
                        )
                    
                    # ═══════════════════════════════════════════════════════════════

                    # Try to correlate click_id from message text
                    import re as re_mod
                    id_match = re_mod.search(r'\(ID:\s*([A-Z0-9]{5})\)', text)
                    id_match = re_mod.search(r'\(ID:\s*([A-Z0-9]{5})\)', text)
                    if id_match:
                        click_id = id_match.group(1)
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
                        custom_data={"currency": "ARS", "value": charge, "content_type": "product"},
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
        pixel_script = f'''<!-- Meta Pixel Code -->
<script>
!function(f,b,e,v,n,t,s)
{{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)}};
if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];
s.parentNode.insertBefore(t,s)}}(window, document,'script',
'https://connect.facebook.net/en_US/fbevents.js');
fbq('init', '{pixel_id}');
</script>
<noscript><img height="1" width="1" style="display:none"
src="https://www.facebook.com/tr?id={pixel_id}&ev=PageView&noscript=1"/></noscript>
<!-- End Meta Pixel Code -->'''
        
        # PageView event (fires on page load)
        if "PageView" in pixel_events:
            pixel_pageview = f"fbq('track', 'PageView');"
        
        # Lead/Contact event (fires on WhatsApp click)
        pixel_wa_click_events = []
        if "Lead" in pixel_events:
            pixel_wa_click_events.append("fbq('track', 'Lead');")
        if "Contact" in pixel_events:
            pixel_wa_click_events.append("fbq('track', 'Contact');")
        if "InitiateCheckout" in pixel_events:
            pixel_wa_click_events.append("fbq('track', 'InitiateCheckout');")
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

var clickId=localStorage.getItem("ck_"+LANDING_CODE)||gID();
localStorage.setItem("ck_"+LANDING_CODE,clickId);

// Meta Pixel - PageView event
if(typeof fbq !== 'undefined') {{ {pixel_pageview} }}

// Track page view
fetch(BASE_URL+"/api/wa-landings/track",{{method:"POST",headers:{{"Content-Type":"application/json"}},
body:JSON.stringify({{landing_code:LANDING_CODE,click_id:clickId,fbp:getFBP(),fbc:getFBC(),
utm_content:new URLSearchParams(window.location.search).get("utm_content")||"",
utm_campaign:new URLSearchParams(window.location.search).get("utm_campaign")||"",
user_agent:navigator.userAgent,referrer:document.referrer}})
}}).catch(function(){{}});

function goWA(){{
var btn=document.getElementById("waBtn");
btn.disabled=true;btn.textContent="CONECTANDO...";
var num=WA_NUMBERS[Math.floor(Math.random()*WA_NUMBERS.length)];
var msg=WA_MSG+" (ID: "+clickId+")";
// Meta Pixel - Conversion events (Lead, Contact, etc)
if(typeof fbq !== 'undefined') {{ {pixel_wa_click} }}
// Track WA click
fetch(BASE_URL+"/api/wa-landings/track-wa",{{method:"POST",headers:{{"Content-Type":"application/json"}},
body:JSON.stringify({{landing_code:LANDING_CODE,click_id:clickId}})
}}).catch(function(){{}});
window.location.href="https://wa.me/"+num+"?text="+encodeURIComponent(msg);
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
        
        # Update click record
        await db.wa_clicks.update_one(
            {"landing_code": landing_code, "click_id": click_id},
            {"$set": {"wa_clicked": True, "wa_clicked_at": datetime.now(timezone.utc).isoformat()}}
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
                
                # Send Lead event via Conversions API
                if "Lead" in pixel_events:
                    await send_meta_conversion_event(
                        event_name="Lead",
                        lead_data=lead_data,
                        custom_data=custom_data,
                        access_token=access_token,
                        pixel_id=pixel_id
                    )
                    logger.info(f"Lead event sent via Conversions API for landing {landing_code}")
                
                # Send Contact event via Conversions API
                if "Contact" in pixel_events:
                    await send_meta_conversion_event(
                        event_name="Contact",
                        lead_data=lead_data,
                        custom_data=custom_data,
                        access_token=access_token,
                        pixel_id=pixel_id
                    )
                    logger.info(f"Contact event sent via Conversions API for landing {landing_code}")
                
                # Send InitiateCheckout event via Conversions API
                if "InitiateCheckout" in pixel_events:
                    await send_meta_conversion_event(
                        event_name="InitiateCheckout",
                        lead_data=lead_data,
                        custom_data=custom_data,
                        access_token=access_token,
                        pixel_id=pixel_id
                    )
                    logger.info(f"InitiateCheckout event sent via Conversions API for landing {landing_code}")
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
    verify_token: Optional[str] = ""
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
    verify_token: Optional[str] = None
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
    currency: Optional[str] = "ARS"
    admin_notes: Optional[str] = ""

class CRMLeadClassify(BaseModel):
    status: str  # basura, curioso, interesado, potencial, cliente_real
    send_to_meta: bool = True
    conversion_value: Optional[float] = None
    currency: Optional[str] = "ARS"

# ─── Meta Conversions API Helper ───────────────────────────────────

# ── Auto-resolve geo data from IP ───────────────────────────────────

_geo_cache = {}  # Simple in-memory cache for IP geo lookups

async def resolve_geo_from_ip(ip: str) -> dict:
    """Resolve city, state, zip, country from IP using ip-api.com (free, no key needed)"""
    if not ip or ip in ("0.0.0.0", "unknown", "127.0.0.1", "::1"):
        return {}
    # Check cache first
    if ip in _geo_cache:
        return _geo_cache[ip]
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
}
_FEMALE_NAMES = {
    'maria','ana','laura','carolina','patricia','andrea','gabriela','claudia','silvia',
    'monica','cecilia','florencia','valeria','fernanda','daniela','paula','lucia',
    'romina','natalia','vanesa','vanessa','lorena','marina','soledad','julieta',
    'camila','micaela','agustina','victoria','sol','rocio','milagros','pilar',
    'sofia','martina','catalina','virginia','mariana','paola','julia','marta',
    'susana','rosa','elena','alejandra','liliana','graciela','norma','alicia',
    'beatriz','miriam','carmen','celeste','morena','luz','brenda','carina',
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
    pixel_id: str = None
):
    """
    Send conversion event to Meta Conversions API
    
    Events:
    - Purchase: Cliente válido (conversión positiva) — requires value + currency in custom_data
    - Lead: Lead interesado
    - Contact: Contacto inicial
    - Other: Eventos custom
    
    Uses line-specific token/pixel only (no env fallbacks)
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
        if name and name.strip() and not name.startswith("Lead "):
            parts = name.strip().split()
            fn = parts[0].lower()
            ln = parts[-1].lower() if len(parts) > 1 else ""
            user_data["fn"] = [hashlib.sha256(fn.encode()).hexdigest()]
            if ln:
                user_data["ln"] = [hashlib.sha256(ln.encode()).hexdigest()]
        
        # Email if available — auto-extract from chat messages if not on lead
        email = lead_data.get("email")
        if not email and lead_data.get("id"):
            email = await extract_email_from_messages(lead_data["id"])
            if email:
                # Persist it on the lead for future events
                await db.crm_leads.update_one({"id": lead_data["id"]}, {"$set": {"email": email}})
                logger.info(f"Meta CAPI: Auto-detected email '{email}' from chat for lead {lead_data.get('id')}")
        if email:
            user_data["em"] = [hashlib.sha256(email.lower().strip().encode()).hexdigest()]
        
        # External ID (lead ID for deduplication)
        if lead_data.get("id"):
            user_data["external_id"] = [hashlib.sha256(lead_data["id"].encode()).hexdigest()]
        
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
        
        # Generate unique event_id for deduplication
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
                custom_data["currency"] = custom_data.get("currency", "ARS")
                # Add content_type for better optimization
                if "content_type" not in custom_data:
                    custom_data["content_type"] = "product"
            event_data["custom_data"] = custom_data
        elif event_name == "Purchase":
            # Purchase MUST have custom_data with value/currency
            event_data["custom_data"] = {
                "value": 0.0,
                "currency": "ARS",
                "content_type": "product"
            }
        
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
    """Create a new WhatsApp line with full configuration"""
    if data.line_type not in CRM_LINE_TYPES:
        raise HTTPException(status_code=400, detail=f"Tipo de línea inválido. Opciones: {CRM_LINE_TYPES}")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Generate unique verify token if not provided
    verify_token = data.verify_token or f"verify_{uuid.uuid4().hex[:12]}"
    
    line = {
        "id": str(uuid.uuid4()),
        "name": data.name,
        "line_type": data.line_type,
        "whatsapp_number": data.whatsapp_number,
        # WhatsApp Business API
        "whatsapp_token": data.whatsapp_token or "",
        "phone_number_id": data.phone_number_id or "",
        "verify_token": verify_token,
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
    """Receive WhatsApp messages for a specific line"""
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

                    sender_name = contact_map.get(from_phone, "")
                    now = datetime.now(timezone.utc).isoformat()

                    # Extract click_id from message if present (format: "(ID: XXXXX)")
                    click_id = None
                    ad_source = None
                    utm_content = None
                    referral_data = None
                    
                    import re
                    click_match = re.search(r'\(ID:\s*([A-Z0-9]+)\)', text)
                    if click_match:
                        click_id = click_match.group(1)
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
                    if click_id and wa_click and crm_lead and not crm_lead.get("ip_address"):
                        fingerprint_data = {}
                        if wa_click.get("ip"):
                            fingerprint_data["ip_address"] = wa_click["ip"]
                        if wa_click.get("user_agent"):
                            fingerprint_data["user_agent"] = wa_click["user_agent"]
                        if wa_click.get("fbp"):
                            fingerprint_data["fbp"] = wa_click["fbp"]
                        if wa_click.get("fbc"):
                            fingerprint_data["fbc"] = wa_click["fbc"]
                        if wa_click.get("landing_code"):
                            fingerprint_data["landing_code"] = wa_click["landing_code"]
                        if wa_click.get("fingerprint_hash"):
                            fingerprint_data["fingerprint_hash"] = wa_click["fingerprint_hash"]
                        if fingerprint_data:
                            await db.crm_leads.update_one({"id": crm_lead["id"]}, {"$set": fingerprint_data})
                            logger.info(f"CRM: Propagated click fingerprint to lead {crm_lead['id']}: {list(fingerprint_data.keys())}")
                    
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
    # Calculate date range based on parameters
    now = datetime.now(timezone.utc)
    
    if start_date and end_date:
        # Custom date range
        date_from = start_date + "T00:00:00+00:00"
        date_to = end_date + "T23:59:59+00:00"
        period_label = f"{start_date} a {end_date}"
    elif filter_type:
        if filter_type == "diario":
            date_from = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            date_to = now.isoformat()
            period_label = "Hoy"
        elif filter_type == "semanal":
            start_of_week = now - timedelta(days=now.weekday())
            date_from = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            date_to = now.isoformat()
            period_label = "Esta semana"
        elif filter_type == "mensual":
            start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            date_from = start_of_month.isoformat()
            date_to = now.isoformat()
            period_label = "Este mes"
        else:
            date_from = (now - timedelta(days=days)).isoformat()
            date_to = now.isoformat()
            period_label = f"Últimos {days} días"
    else:
        date_from = (now - timedelta(days=days)).isoformat()
        date_to = now.isoformat()
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

@api_router.get("/crm/leads")
async def crm_get_all_leads(
    status: Optional[str] = None,
    line_id: Optional[str] = None,
    min_score: int = 0,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
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

    return {
        "leads": leads,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit if total > 0 else 1
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
    - consultas: Just asking, no purchase intent (sends LowQualityLead to Meta)
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
            purchase_currency = data.currency or "ARS"
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
            
        elif data.status in ["spam", "consultas"]:
            # For spam/consultas - send LowQualityLead event
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
    current_user=Depends(get_current_user)
):
    """Get all messages for a lead"""
    lead = await db.crm_leads.find_one({"id": lead_id})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    
    total = await db.crm_messages.count_documents({"lead_id": lead_id})
    skip = (page - 1) * limit
    
    messages = await db.crm_messages.find(
        {"lead_id": lead_id}, {"_id": 0}
    ).sort("created_at", 1).skip(skip).limit(limit).to_list(limit)
    
    return {
        "messages": messages,
        "total": total,
        "page": page
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
# ─── CRM Receipts Routes ───────────────────────────────────────────

from fastapi import UploadFile, File

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
    currency: str = Query("ARS", description="Currency code"),
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
    purchase_currency = currency or "ARS"
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

app.include_router(go_router)
app.include_router(api_router)

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

@app.on_event("shutdown")
async def shutdown():
    client.close()
