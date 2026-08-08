# -*- coding: utf-8 -*-
import re

fp = r'C:\Users\Lucas\Desktop\adphantom-main\backend\server.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

new_serve = """@go_router.get("/l/{code}")
async def serve_wa_landing(code: str, request: Request):
    \"\"\"Serve WhatsApp landing page with strict antibot cloaking and JS fingerprinting\"\"\"
    landing = await db.wa_landings.find_one({"code": code, "is_active": True}, {"_id": 0})
    if not landing:
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=404)
    
    # Get request info
    user_agent = request.headers.get("user-agent", "")
    ip = get_client_ip(request)
    headers_dict = {k.lower(): v for k, v in request.headers.items()}
    referrer = headers_dict.get("referer", "")
    
    # Check if it's a bot, Meta crawler, VPN, or datacenter IP
    bot_flag = is_bot(user_agent)
    meta_crawler = is_meta_crawler(user_agent)
    meta_ip = is_meta_ip(ip)
    vpn = detect_vpn(headers_dict)
    
    # Strict validation for automatic bots (No accept-language usually means automated crawler)
    has_accept_lang = "accept-language" in headers_dict
    
    score = calculate_behavioral_score(bot_flag, vpn, meta_ip, bool(referrer), user_agent)
    
    # If bot, Meta crawler, Meta IP, VPN, or suspicious score -> show safe page (NO PIXEL)
    if bot_flag or meta_crawler or meta_ip or vpn or not has_accept_lang or score < 70:
        logger.warning(f"WA Landing {code}: Cloaking activated - bot={bot_flag}, meta={meta_crawler}, meta_ip={meta_ip}, vpn={vpn}, score={score}, ua={user_agent[:40]}")
        return HTMLResponse(content=SAFE_PAGE_HTML, status_code=200)
    
    # Real user -> show actual landing WITH Pixel + JS Fingerprint Shield
    base_url = str(request.base_url).rstrip("/")
    forwarded_proto = headers_dict.get("x-forwarded-proto", "")
    if forwarded_proto == "https":
        base_url = base_url.replace("http://", "https://")
        
    html = build_landing_html(landing, base_url)
    
    # Inject JS Shield at the end of the head
    # HTML inside string is escaped properly
    safe_html_escaped = SAFE_PAGE_HTML.replace('', '\\\')
    
    js_shield = f\"\"\"
<script>
(function(){{
    var isSafe = true;
    // Basic Headless checks
    if(navigator.webdriver || window.navigator.webdriver || window.document.__selenium_unwrapped || window.document.__webdriver_evaluate || window.document.__driver_evaluate) {{
        isSafe = false;
    }}
    // Meta / TikTok in-app browsers often have specific user agents, but pure headless chrome has plugins length 0
    if(navigator.plugins.length === 0 && navigator.userAgent.indexOf('Chrome') !== -1 && navigator.userAgent.indexOf('Mobile') === -1) {{
        isSafe = false;
    }}
    if(!isSafe){{
        document.documentElement.innerHTML = {safe_html_escaped};
    }}
}})();
</script>
\"\"\"
    html = html.replace('</head>', js_shield + '</head>')
    
    return HTMLResponse(content=html)
"""

# Extract current function
start_idx = -1
end_idx = -1
lines = content.splitlines()
for i, line in enumerate(lines):
    if line.startswith('@go_router.get("/l/{code}")'):
        start_idx = i
        break
for i in range(start_idx + 1, len(lines)):
    if lines[i].startswith('@go_router.get') or lines[i].startswith('@api_router'):
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    lines[start_idx:end_idx] = new_serve.splitlines()
    content = '\n'.join(lines)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Updated serve_wa_landing successfully")
else:
    print("Could not find function")

