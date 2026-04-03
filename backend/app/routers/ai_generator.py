from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.ai_page import AIPage
from app.schemas.ai_page import AIPageCreate, AIPageResponse
from app.services.ai_service import ai_service
import uuid

router = APIRouter(prefix="/ai", tags=["ai"])

@router.post("/generate", response_model=AIPageResponse)
async def generate_ai_page(page_data: AIPageCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    html_content = await ai_service.generate_page(page_data.prompt)
    
    if not html_content:
        raise HTTPException(status_code=500, detail="Failed to generate page. Check Claude API key.")
    
    title = page_data.prompt[:100]
    
    ai_page = AIPage(
        prompt=page_data.prompt,
        generated_html=html_content,
        title=title,
        campaign_id=page_data.campaign_id
    )
    
    db.add(ai_page)
    db.commit()
    db.refresh(ai_page)
    
    return ai_page

@router.get("/pages", response_model=List[AIPageResponse])
def get_ai_pages(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    pages = db.query(AIPage).order_by(AIPage.created_at.desc()).all()
    return pages

@router.get("/pages/{page_id}", response_model=AIPageResponse)
def get_ai_page(page_id: uuid.UUID, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    page = db.query(AIPage).filter(AIPage.id == page_id).first()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page

@router.delete("/pages/{page_id}")
def delete_ai_page(page_id: uuid.UUID, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    page = db.query(AIPage).filter(AIPage.id == page_id).first()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    db.delete(page)
    db.commit()
    return {"message": "Page deleted successfully"}