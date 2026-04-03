import requests
from typing import Optional

def get_country_from_ip(ip: str) -> Optional[str]:
    """Get country code from IP address using free API"""
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}?fields=countryCode", timeout=2)
        if response.status_code == 200:
            data = response.json()
            return data.get('countryCode', 'XX')
    except:
        pass
    return 'XX'

def is_private_ip(ip: str) -> bool:
    """Check if IP is private/local"""
    private_ranges = [
        '127.', '10.', '192.168.', '172.16.', '172.17.', '172.18.',
        '172.19.', '172.20.', '172.21.', '172.22.', '172.23.', '172.24.',
        '172.25.', '172.26.', '172.27.', '172.28.', '172.29.', '172.30.', '172.31.'
    ]
    return any(ip.startswith(prefix) for prefix in private_ranges)