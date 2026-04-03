from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List
from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.campaign import Campaign
from app.models.click import Click
from app.schemas.click import ClickResponse
from app.utils.export_csv import export_clicks_to_csv
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    total_clicks = db.query(func.count(Click.id)).scalar()
    blocked_clicks = db.query(func.count(Click.id)).filter(Click.is_blocked == True).scalar()
    
    clicks_by_country = db.query(
        Click.country,
        func.count(Click.id).label('count')
    ).group_by(Click.country).order_by(desc('count')).limit(10).all()
    
    clicks_by_device = db.query(
        Click.device,
        func.count(Click.id).label('count')
    ).group_by(Click.device).all()
    
    clicks_by_os = db.query(
        Click.os,
        func.count(Click.id).label('count')
    ).group_by(Click.os).order_by(desc('count')).limit(10).all()
    
    today = datetime.now(timezone.utc).date()
    clicks_today = db.query(func.count(Click.id)).filter(
        func.date(Click.created_at) == today
    ).scalar()
    
    return {
        "total_clicks": total_clicks or 0,
        "blocked_clicks": blocked_clicks or 0,
        "clicks_today": clicks_today or 0,
        "by_country": [{"country": c[0], "count": c[1]} for c in clicks_by_country],
        "by_device": [{"device": d[0], "count": d[1]} for d in clicks_by_device],
        "by_os": [{"os": o[0], "count": o[1]} for o in clicks_by_os]
    }

@router.get("/recent-clicks", response_model=List[ClickResponse])
def get_recent_clicks(limit: int = 50, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    clicks = db.query(Click).order_by(desc(Click.created_at)).limit(limit).all()
    return clicks

@router.get("/export-csv")
def export_dashboard_csv(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    clicks = db.query(Click).order_by(desc(Click.created_at)).limit(10000).all()
    
    clicks_data = [
        {
            'id': str(click.id),
            'campaign_id': str(click.campaign_id),
            'ip': click.ip,
            'country': click.country,
            'device': click.device,
            'os': click.os,
            'browser': click.browser,
            'referrer': click.referrer,
            'is_bot': click.is_bot,
            'is_vpn': click.is_vpn,
            'is_datacenter': click.is_datacenter,
            'is_blocked': click.is_blocked,
            'block_reason': click.block_reason,
            'behavioral_score': click.behavioral_score,
            'created_at': click.created_at
        }
        for click in clicks
    ]
    
    csv_content = export_clicks_to_csv(clicks_data)
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=clicks_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )