from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from datetime import datetime, timedelta, timezone
from typing import Optional
from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.click import Click
from app.models.campaign import Campaign
import uuid

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/performance")
def performance_report(
    campaign_id: Optional[uuid.UUID] = None,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Reporte de performance por día"""
    date_from = datetime.now(timezone.utc) - timedelta(days=days)
    
    query = db.query(
        func.date(Click.created_at).label('date'),
        func.count(Click.id).label('total_clicks'),
        func.count(Click.id).filter(Click.is_blocked == True).label('blocked_clicks'),
        func.count(Click.id).filter(Click.is_blocked == False).label('allowed_clicks')
    ).filter(Click.created_at >= date_from)
    
    if campaign_id:
        query = query.filter(Click.campaign_id == campaign_id)
    
    results = query.group_by(func.date(Click.created_at)).order_by(func.date(Click.created_at)).all()
    
    return {
        "period": f"Last {days} days",
        "data": [
            {
                "date": str(r.date),
                "total_clicks": r.total_clicks,
                "blocked_clicks": r.blocked_clicks,
                "allowed_clicks": r.allowed_clicks,
                "block_rate": round((r.blocked_clicks / r.total_clicks * 100), 2) if r.total_clicks > 0 else 0
            }
            for r in results
        ]
    }

@router.get("/fraud-detection")
def fraud_detection_report(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Detectar patrones de click fraud"""
    date_from = datetime.now(timezone.utc) - timedelta(days=days)
    
    # IPs con múltiples clicks
    suspicious_ips = db.query(
        Click.ip,
        func.count(Click.id).label('click_count'),
        func.count(Click.id).filter(Click.is_blocked == True).label('blocked_count'),
        func.avg(Click.behavioral_score).label('avg_score')
    ).filter(
        Click.created_at >= date_from
    ).group_by(Click.ip).having(func.count(Click.id) > 5).order_by(desc('click_count')).limit(20).all()
    
    # Fingerprints duplicados
    duplicate_fingerprints = db.query(
        Click.fingerprint_hash,
        func.count(Click.id).label('count')
    ).filter(
        Click.created_at >= date_from,
        Click.fingerprint_hash.isnot(None)
    ).group_by(Click.fingerprint_hash).having(func.count(Click.id) > 10).order_by(desc('count')).limit(20).all()
    
    return {
        "suspicious_ips": [
            {
                "ip": ip.ip,
                "click_count": ip.click_count,
                "blocked_count": ip.blocked_count,
                "avg_score": round(float(ip.avg_score), 2) if ip.avg_score else 0,
                "fraud_probability": "HIGH" if ip.click_count > 20 else "MEDIUM"
            }
            for ip in suspicious_ips
        ],
        "duplicate_fingerprints": [
            {
                "fingerprint": fp.fingerprint_hash[:16] + "...",
                "count": fp.count
            }
            for fp in duplicate_fingerprints
        ]
    }

@router.get("/geo-analysis")
def geo_analysis_report(
    campaign_id: Optional[uuid.UUID] = None,
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Análisis geográfico detallado"""
    date_from = datetime.now(timezone.utc) - timedelta(days=days)
    
    query = db.query(
        Click.country,
        func.count(Click.id).label('total_clicks'),
        func.count(Click.id).filter(Click.is_blocked == True).label('blocked'),
        func.count(Click.id).filter(Click.is_bot == True).label('bots'),
        func.count(Click.id).filter(Click.is_vpn == True).label('vpn'),
        func.avg(Click.behavioral_score).label('avg_score')
    ).filter(Click.created_at >= date_from)
    
    if campaign_id:
        query = query.filter(Click.campaign_id == campaign_id)
    
    results = query.group_by(Click.country).order_by(desc('total_clicks')).limit(30).all()
    
    return {
        "countries": [
            {
                "country": r.country or "Unknown",
                "total_clicks": r.total_clicks,
                "blocked": r.blocked,
                "bots": r.bots,
                "vpn": r.vpn,
                "avg_score": round(float(r.avg_score), 2) if r.avg_score else 0,
                "quality": "HIGH" if r.avg_score and r.avg_score > 70 else "MEDIUM" if r.avg_score and r.avg_score > 50 else "LOW"
            }
            for r in results
        ]
    }

@router.get("/hourly-patterns")
def hourly_patterns_report(
    campaign_id: Optional[uuid.UUID] = None,
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Patrones por hora del día"""
    date_from = datetime.now(timezone.utc) - timedelta(days=days)
    
    query = db.query(
        func.extract('hour', Click.created_at).label('hour'),
        func.count(Click.id).label('clicks'),
        func.count(Click.id).filter(Click.is_blocked == False).label('allowed')
    ).filter(Click.created_at >= date_from)
    
    if campaign_id:
        query = query.filter(Click.campaign_id == campaign_id)
    
    results = query.group_by('hour').order_by('hour').all()
    
    return {
        "hourly_data": [
            {
                "hour": int(r.hour),
                "total_clicks": r.clicks,
                "allowed_clicks": r.allowed,
                "conversion_rate": round((r.allowed / r.clicks * 100), 2) if r.clicks > 0 else 0
            }
            for r in results
        ]
    }