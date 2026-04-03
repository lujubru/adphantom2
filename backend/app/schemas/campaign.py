from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

class CampaignBase(BaseModel):
    name: str
    target_url: str
    safe_page_url: Optional[str] = None
    is_active: bool = True
    daily_click_limit: int = 10000
    allowed_countries: List[str] = []
    allowed_devices: List[str] = []
    allowed_os: List[str] = []
    block_empty_referrer: bool = False
    blacklist_ips: List[str] = []
    whitelist_ips: List[str] = []

class CampaignCreate(CampaignBase):
    pass

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

class CampaignResponse(CampaignBase):
    id: uuid.UUID
    clicks_today: int
    total_clicks: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True