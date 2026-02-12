"""
ATLAS - Recommendations API Endpoints
"""
from datetime import datetime, date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.database_models import User
from app.atlas.models.atlas_models import HedgeAction, RecommendationStatus
from app.atlas.models.schemas import (
    RecommendationGenerateRequest,
    RecommendationResponse,
    RecommendationWithExposure,
    RecommendationDecision,
    RecommendationCalendar,
)
from app.atlas.services.policy_engine import PolicyEngine
from app.atlas.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["ATLAS - Recommendations"])


def get_policy_engine(db: Session = Depends(get_db)) -> PolicyEngine:
    return PolicyEngine(db)


def get_recommendation_service(db: Session = Depends(get_db)) -> RecommendationService:
    return RecommendationService(db)


@router.post("/generate", response_model=List[RecommendationResponse])
async def generate_recommendations(
    data: RecommendationGenerateRequest,
    engine: PolicyEngine = Depends(get_policy_engine),
    current_user: User = Depends(get_current_user)
):
    """
    Generate hedge recommendations based on policy evaluation.

    Evaluates open exposures against the configured policy
    and generates actionable recommendations.
    """
    # Get current TRM rate (simplified - would come from data service)
    current_rate = None  # TODO: Get from market data

    recommendations = engine.evaluate(
        company_id=current_user.company_id,
        policy_id=data.policy_id,
        exposure_ids=data.exposure_ids,
        current_rate=current_rate,
    )
    return recommendations


@router.get("/", response_model=List[RecommendationResponse])
async def list_recommendations(
    status: Optional[RecommendationStatus] = None,
    action: Optional[HedgeAction] = None,
    exposure_id: Optional[UUID] = None,
    urgency: Optional[str] = Query(default=None, pattern="^(low|normal|high|critical)$"),
    include_expired: bool = False,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    service: RecommendationService = Depends(get_recommendation_service),
    current_user: User = Depends(get_current_user)
):
    """List recommendations with optional filters"""
    return service.list(
        company_id=current_user.company_id,
        status=status,
        action=action,
        exposure_id=exposure_id,
        urgency=urgency,
        include_expired=include_expired,
        skip=skip,
        limit=limit,
    )


@router.get("/pending", response_model=List[RecommendationResponse])
async def list_pending_recommendations(
    service: RecommendationService = Depends(get_recommendation_service),
    current_user: User = Depends(get_current_user)
):
    """List all pending recommendations that require attention"""
    return service.list_pending(current_user.company_id)


@router.get("/calendar")
async def get_recommendations_calendar(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    days: int = Query(default=30, ge=1, le=365),
    service: RecommendationService = Depends(get_recommendation_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get calendar view of recommendations grouped by exposure due date.

    Useful for planning hedging activities.
    """
    calendar = service.get_calendar(
        company_id=current_user.company_id,
        start_date=start_date,
        end_date=end_date,
        days=days,
    )

    # Convert to serializable format
    return [
        {
            "date": item.date.isoformat(),
            "total_amount": float(item.total_amount),
            "priority_breakdown": item.priority_breakdown,
            "recommendations_count": len(item.recommendations),
        }
        for item in calendar
    ]


@router.get("/summary")
async def get_recommendations_summary(
    service: RecommendationService = Depends(get_recommendation_service),
    current_user: User = Depends(get_current_user)
):
    """Get summary statistics of recommendations"""
    return service.get_summary(current_user.company_id)


@router.get("/{recommendation_id}", response_model=RecommendationResponse)
async def get_recommendation(
    recommendation_id: UUID,
    service: RecommendationService = Depends(get_recommendation_service),
    current_user: User = Depends(get_current_user)
):
    """Get recommendation by ID"""
    recommendation = service.get(recommendation_id, current_user.company_id)
    if not recommendation:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return recommendation


@router.post("/{recommendation_id}/accept", response_model=RecommendationResponse)
async def accept_recommendation(
    recommendation_id: UUID,
    service: RecommendationService = Depends(get_recommendation_service),
    current_user: User = Depends(get_current_user)
):
    """
    Accept a recommendation.

    This marks the recommendation as accepted and can trigger
    order creation via the orders endpoint.
    """
    recommendation = service.accept(
        recommendation_id=recommendation_id,
        company_id=current_user.company_id,
        decided_by=current_user.id,
    )
    if not recommendation:
        raise HTTPException(
            status_code=400,
            detail="Cannot accept recommendation (not found or not pending)"
        )
    return recommendation


@router.post("/{recommendation_id}/reject", response_model=RecommendationResponse)
async def reject_recommendation(
    recommendation_id: UUID,
    data: RecommendationDecision,
    service: RecommendationService = Depends(get_recommendation_service),
    current_user: User = Depends(get_current_user)
):
    """Reject a recommendation with optional reason"""
    recommendation = service.reject(
        recommendation_id=recommendation_id,
        company_id=current_user.company_id,
        reason=data.rejection_reason,
        decided_by=current_user.id,
    )
    if not recommendation:
        raise HTTPException(
            status_code=400,
            detail="Cannot reject recommendation (not found or not pending)"
        )
    return recommendation


@router.post("/expire-old")
async def expire_old_recommendations(
    service: RecommendationService = Depends(get_recommendation_service),
    current_user: User = Depends(get_current_user)
):
    """Expire all recommendations past their valid_until date"""
    count = service.expire_old(current_user.company_id)
    return {"expired_count": count}
