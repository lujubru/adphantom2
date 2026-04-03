import hashlib
import json
from typing import Dict

def generate_fingerprint(ip: str, user_agent: str, headers: Dict[str, str]) -> str:
    """Generate unique device fingerprint"""
    fingerprint_data = {
        "ip": ip,
        "user_agent": user_agent,
        "accept_language": headers.get("accept-language", ""),
        "accept_encoding": headers.get("accept-encoding", ""),
        "accept": headers.get("accept", "")
    }
    
    fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
    return hashlib.sha256(fingerprint_str.encode()).hexdigest()