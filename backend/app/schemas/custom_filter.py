from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime
import uuid

class CustomFilterBase(BaseModel):
    name: str
    description: Optional[str] = None
    conditions: Dict = {}
    action: str = "block"
    priority: int = 0
    is_active: bool = True

class CustomFilterCreate(CustomFilterBase):
    pass

class CustomFilterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[Dict] = None
    action: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None

class CustomFilterResponse(CustomFilterBase):
    id: uuid.UUID
    times_triggered: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True