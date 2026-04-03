from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.ai_page import AIPage
from app.models.campaign import Campaign
from app.models.click import Click
from app.services.traffic_inspector import inspector
from app.services.fingerprint import generate_fingerprint
from app.utils.ip_detection import get_country_from_ip, is_private_ip
import uuid

router = APIRouter(prefix="/p", tags=["public_pages"])

# Safe page HTML when bot/blocked traffic is detected
SAFE_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page Not Found</title>
    <meta name="robots" content="noindex, nofollow">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .container {
            text-align: center;
            padding: 2rem;
        }
        h1 {
            font-size: 4rem;
            margin: 0;
        }
        p {
            font-size: 1.5rem;
            margin-top: 1rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>404</h1>
        <p>Page not found</p>
    </div>
</body>
</html>"""

def get_client_ip(request: Request) -> str:
    """Extract real client IP from request"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "0.0.0.0"


@router.get("/{page_id}")
async def serve_public_page(page_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    """
    Serve AI-generated landing page with full antibot tracking.
    
    - If bot/Meta crawler detected → Shows safe page (404)
    - If blocked by campaign rules → Shows safe page
    - If legitimate user → Shows the AI-generated landing
    
    All visits are logged with full tracking data.
    """
    
    # Get the AI page
    ai_page = db.query(AIPage).filter(AIPage.id == page_id).first()
    
    if not ai_page:
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=404)
    
    # Get associated campaign (if any) for tracking rules
    campaign = None
    if ai_page.campaign_id:
        campaign = db.query(Campaign).filter(Campaign.id == ai_page.campaign_id).first()
    
    # If campaign exists and is inactive, show safe page
    if campaign and not campaign.is_active:
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=404)
    
    # Check daily limit if campaign exists
    if campaign and campaign.clicks_today >= campaign.daily_click_limit:
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=429)
    
    # Extract request info
    ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    referrer = request.headers.get("referer", "")
    headers_dict = dict(request.headers)
    
    # Parse device info
    device, os, browser = inspector.parse_device_info(user_agent)
    country = get_country_from_ip(ip) if not is_private_ip(ip) else "XX"
    
    # Run all detection checks
    is_bot = inspector.is_bot(user_agent)
    is_meta = inspector.is_meta_crawler(user_agent)
    is_vpn = inspector.detect_vpn(headers_dict)
    is_datacenter = inspector.is_datacenter_ip(ip)
    
    # Generate fingerprint
    fingerprint = generate_fingerprint(ip, user_agent, headers_dict)
    
    # Calculate behavioral score
    behavioral_score = inspector.calculate_behavioral_score(
        is_bot=is_bot,
        is_vpn=is_vpn,
        is_datacenter=is_datacenter,
        has_referrer=bool(referrer),
        user_agent=user_agent
    )
    
    # Determine if should block based on campaign rules
    should_block = False
    block_reason = None
    
    if campaign:
        campaign_config = {
            'allowed_countries': campaign.allowed_countries or [],
            'allowed_devices': campaign.allowed_devices or [],
            'allowed_os': campaign.allowed_os or [],
            'block_empty_referrer': campaign.block_empty_referrer,
            'blacklist_ips': campaign.blacklist_ips or [],
            'whitelist_ips': campaign.whitelist_ips or []
        }
        
        should_block, block_reason = inspector.should_block(
            campaign_config=campaign_config,
            ip=ip,
            country=country,
            device=device,
            os=os,
            referrer=referrer,
            is_bot=is_bot,
            is_vpn=is_vpn
        )
    else:
        # No campaign - just check for bots
        if is_bot:
            should_block = True
            block_reason = "Bot detected"
    
    # Log the click/visit
    click = Click(
        campaign_id=ai_page.campaign_id,
        ip=ip,
        country=country,
        user_agent=user_agent,
        device=device,
        os=os,
        browser=browser,
        referrer=referrer,
        is_bot=is_bot,
        is_vpn=is_vpn,
        is_datacenter=is_datacenter,
        is_blocked=should_block or is_meta,
        block_reason=block_reason if should_block else ("Meta crawler" if is_meta else None),
        fingerprint_hash=fingerprint,
        behavioral_score=behavioral_score
    )
    
    db.add(click)
    
    # Update campaign counters if exists
    if campaign:
        campaign.clicks_today += 1
        campaign.total_clicks += 1
    
    db.commit()
    
    # Decision: Show safe page or real landing
    if is_meta:
        # Meta/Facebook crawler - show safe page
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=200)
    
    if should_block:
        # Blocked traffic - show safe page
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=200)
    
    # Legitimate user - show the AI-generated landing page
    return HTMLResponse(content=ai_page.generated_html, status_code=200)
