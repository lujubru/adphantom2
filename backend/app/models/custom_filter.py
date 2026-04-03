from sqlalchemy import Column, String, DateTime, Boolean, Integer, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid
from datetime import datetime, timezone

class CustomFilter(Base):
    __tablename__ = "custom_filters"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Condiciones (JSON)
    conditions = Column(JSON, default=dict)
    
    # Acción
    action = Column(String(50), default="block")  # "allow" o "block"
    priority = Column(Integer, default=0)  # Orden de ejecución
    is_active = Column(Boolean, default=True)
    
    # Stats
    times_triggered = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))