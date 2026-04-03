import re
from typing import Dict, Tuple
from user_agents import parse

BOT_PATTERNS = [
    r'bot', r'crawl', r'spider', r'scrape', r'meta-externalagent',
    r'facebookexternalhit', r'facebot', r'twitterbot', r'linkedinbot',
    r'pinterest', r'slackbot', r'whatsapp', r'telegram', r'instagram',
    r'googlebot', r'bingbot', r'yandex', r'baidu', r'duckduck',
    r'monitoring', r'checker', r'validator', r'preview', r'fetcher'
]

META_CRAWLER_PATTERNS = [
    r'meta-externalagent', r'facebookexternalhit', r'facebot',
    r'facebook', r'instagram', r'whatsapp'
]

VPN_HEADERS = [
    'x-forwarded-for', 'x-real-ip', 'cf-connecting-ip',
    'x-cluster-client-ip', 'forwarded'
]

DATACENTER_KEYWORDS = [
    'amazon', 'aws', 'google cloud', 'azure', 'digitalocean',
    'linode', 'vultr', 'ovh', 'hetzner', 'cloudflare'
]

class TrafficInspector:
    def __init__(self):
        self.bot_pattern = re.compile('|'.join(BOT_PATTERNS), re.IGNORECASE)
        self.meta_pattern = re.compile('|'.join(META_CRAWLER_PATTERNS), re.IGNORECASE)
    
    def is_bot(self, user_agent: str) -> bool:
        """Detect if user agent is a bot"""
        if not user_agent:
            return True
        return bool(self.bot_pattern.search(user_agent))
    
    def is_meta_crawler(self, user_agent: str) -> bool:
        """Detect Meta/Facebook crawlers"""
        if not user_agent:
            return False
        return bool(self.meta_pattern.search(user_agent))
    
    def detect_vpn(self, headers: Dict[str, str]) -> bool:
        """Detect VPN/Proxy by checking forwarding headers"""
        for header in VPN_HEADERS:
            if header.lower() in headers:
                forwarded_ips = headers[header.lower()].split(',')
                if len(forwarded_ips) > 1:
                    return True
        return False
    
    def is_datacenter_ip(self, ip: str, reverse_dns: str = "") -> bool:
        """Basic datacenter IP detection"""
        reverse_dns_lower = reverse_dns.lower()
        for keyword in DATACENTER_KEYWORDS:
            if keyword in reverse_dns_lower:
                return True
        
        datacenter_ranges = [
            ('54.', '55.'),
            ('3.', '18.'),
            ('35.', '34.'),
        ]
        
        for start_range in datacenter_ranges:
            if ip.startswith(start_range):
                return True
        
        return False
    
    def parse_device_info(self, user_agent: str) -> Tuple[str, str, str]:
        """Parse device, OS, and browser from user agent"""
        if not user_agent:
            return "Unknown", "Unknown", "Unknown"
        
        ua = parse(user_agent)
        
        device = "Desktop"
        if ua.is_mobile:
            device = "Mobile"
        elif ua.is_tablet:
            device = "Tablet"
        elif ua.is_bot:
            device = "Bot"
        
        os = ua.os.family if ua.os.family else "Unknown"
        browser = ua.browser.family if ua.browser.family else "Unknown"
        
        return device, os, browser
    
    def calculate_behavioral_score(self, 
                                   is_bot: bool,
                                   is_vpn: bool,
                                   is_datacenter: bool,
                                   has_referrer: bool,
                                   user_agent: str) -> float:
        """Calculate traffic quality score (0-100, higher is better)"""
        score = 100.0
        
        if is_bot:
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
    
    def should_block(self,
                    campaign_config: Dict,
                    ip: str,
                    country: str,
                    device: str,
                    os: str,
                    referrer: str,
                    is_bot: bool,
                    is_vpn: bool) -> Tuple[bool, str]:
        """Determine if traffic should be blocked"""
        
        if campaign_config.get('whitelist_ips') and ip in campaign_config['whitelist_ips']:
            return False, ""
        
        if ip in campaign_config.get('blacklist_ips', []):
            return True, "IP blacklisted"
        
        if is_bot:
            return True, "Bot detected"
        
        if is_vpn:
            return True, "VPN/Proxy detected"
        
        if campaign_config.get('block_empty_referrer') and not referrer:
            return True, "Empty referrer blocked"
        
        allowed_countries = campaign_config.get('allowed_countries', [])
        if allowed_countries and country not in allowed_countries:
            return True, f"Country {country} not allowed"
        
        allowed_devices = campaign_config.get('allowed_devices', [])
        if allowed_devices and device not in allowed_devices:
            return True, f"Device {device} not allowed"
        
        allowed_os = campaign_config.get('allowed_os', [])
        if allowed_os and os not in allowed_os:
            return True, f"OS {os} not allowed"
        
        return False, ""

inspector = TrafficInspector()