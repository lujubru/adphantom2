from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class ClickBase(BaseModel):
    campaign_id: uuid.UUID
    ip: str
    country: Optional[str] = None
    user_agent: Optional[str] = None
    device: Optional[str] = None
    os: Optional[str] = None
    browser: Optional[str] = None
    referrer: Optional[str] = None
    is_bot: bool = False
    is_vpn: bool = False
    is_datacenter: bool = False
    is_blocked: bool = False
    block_reason: Optional[str] = None
    fingerprint_hash: Optional[str] = None
    behavioral_score: float = 0.0

class ClickCreate(ClickBase):
    pass

class ClickResponse(ClickBase):
    id: uuid.UUID
    created_at: datetime
    
    class Config:
        from_attributes = True