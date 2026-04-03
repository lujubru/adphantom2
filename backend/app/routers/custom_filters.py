from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.custom_filter import CustomFilter
from app.schemas.custom_filter import CustomFilterCreate, CustomFilterUpdate, CustomFilterResponse
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/filters", tags=["filters"])

@router.get("/", response_model=List[CustomFilterResponse])
def get_filters(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    filters = db.query(CustomFilter).order_by(CustomFilter.priority.desc()).all()
    return filters

@router.get("/{filter_id}", response_model=CustomFilterResponse)
def get_filter(filter_id: uuid.UUID, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    custom_filter = db.query(CustomFilter).filter(CustomFilter.id == filter_id).first()
    if not custom_filter:
        raise HTTPException(status_code=404, detail="Filter not found")
    return custom_filter

@router.post("/", response_model=CustomFilterResponse)
def create_filter(filter_data: CustomFilterCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    custom_filter = CustomFilter(**filter_data.model_dump())
    db.add(custom_filter)
    db.commit()
    db.refresh(custom_filter)
    return custom_filter

@router.put("/{filter_id}", response_model=CustomFilterResponse)
def update_filter(
    filter_id: uuid.UUID,
    filter_data: CustomFilterUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    custom_filter = db.query(CustomFilter).filter(CustomFilter.id == filter_id).first()
    if not custom_filter:
        raise HTTPException(status_code=404, detail="Filter not found")
    
    update_data = filter_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(custom_filter, key, value)
    
    custom_filter.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(custom_filter)
    return custom_filter

@router.delete("/{filter_id}")
def delete_filter(filter_id: uuid.UUID, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    custom_filter = db.query(CustomFilter).filter(CustomFilter.id == filter_id).first()
    if not custom_filter:
        raise HTTPException(status_code=404, detail="Filter not found")
    
    db.delete(custom_filter)
    db.commit()
    return {"message": "Filter deleted successfully"}