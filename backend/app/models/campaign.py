from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid
from datetime import datetime, timezone

class Campaign(Base):
    __tablename__ = "campaigns"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    target_url = Column(Text, nullable=False)
    safe_page_url = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    daily_click_limit = Column(Integer, default=10000)
    clicks_today = Column(Integer, default=0)
    total_clicks = Column(Integer, default=0)
    
    allowed_countries = Column(JSON, default=list)
    allowed_devices = Column(JSON, default=list)
    allowed_os = Column(JSON, default=list)
    block_empty_referrer = Column(Boolean, default=False)
    blacklist_ips = Column(JSON, default=list)
    whitelist_ips = Column(JSON, default=list)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))