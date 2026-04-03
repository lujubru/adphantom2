from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid
from datetime import datetime, timezone

class Click(Base):
    __tablename__ = "clicks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False, index=True)
    
    ip = Column(String(45), nullable=False, index=True)
    country = Column(String(10))
    user_agent = Column(Text)
    device = Column(String(50))
    os = Column(String(50))
    browser = Column(String(50))
    referrer = Column(Text)
    
    is_bot = Column(Boolean, default=False)
    is_vpn = Column(Boolean, default=False)
    is_datacenter = Column(Boolean, default=False)
    is_blocked = Column(Boolean, default=False)
    block_reason = Column(String(255))
    
    fingerprint_hash = Column(String(64), index=True)
    behavioral_score = Column(Float, default=0.0)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)