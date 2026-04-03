from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class AIPageCreate(BaseModel):
    prompt: str
    campaign_id: Optional[uuid.UUID] = None

class AIPageResponse(BaseModel):
    id: uuid.UUID
    campaign_id: Optional[uuid.UUID] = None
    prompt: str
    generated_html: str
    title: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True