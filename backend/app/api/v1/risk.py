
from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel, HttpUrl
import uuid

from app.api.v1.auth import get_current_user
from datetime import date, timedelta
from app.core.database import get_db
from app.models.database_models import User, Prediction
from app.services.hedging_service import hedging_service, MarketRiskScore, HedgingRecommendation
from app.ml.ensemble_model import ensemble_model

router = APIRouter(prefix="/risk", tags=["risk"])

class RiskScoreResponse(BaseModel):
    total_score: float
    volatility_score: float
    trend_score: float
    risk_level: str
    recommendation: str

class HedgingRequest(BaseModel):
    amount: float
    time_horizon_days: int = 30
    current_exposure: float = 0.0

class HedgingResponse(BaseModel):
    action: str
    amount_to_hedge: float
    suggested_rate: float
    urgency: str
    reasoning: List[str]

class WebhookRequest(BaseModel):
    url: HttpUrl

@router.get("/score", response_model=RiskScoreResponse)
async def get_market_risk_score(
    db = Depends(get_db)
):
    """
    Get the current market risk score (0-100) and volatility metrics.
    Useful for quick dashboards and automated decision making.
    """
    try:
        records = db.query(Prediction).filter(
            Prediction.target_date >= date.today(),
            Prediction.target_date <= date.today() + timedelta(days=30)
        ).order_by(Prediction.target_date.asc()).all()

        predictions = [
            {
                "predicted_value": float(p.predicted_value),
                "model_volatility": 0
            }
            for p in records
        ]

        score = hedging_service.calculate_market_risk(predictions)
        
        return RiskScoreResponse(
            total_score=score.total_score,
            volatility_score=score.volatility_score,
            trend_score=score.trend_risk,
            risk_level=score.risk_level,
            recommendation=score.recommendation
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating risk score: {str(e)}")

@router.post("/analyze", response_model=HedgingResponse)
async def analyze_hedging_needs(
    request: HedgingRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Get a personalized hedging recommendation based on amount and time horizon.
    """
    # Use company_id from the authenticated user
    company_id = current_user.company_id if current_user.company_id else current_user.id # Fallback
    
    recommendation = hedging_service.get_hedging_recommendation(
        amount=Decimal(str(request.amount)),
        time_horizon_days=request.time_horizon_days,
        current_exposure=Decimal(str(request.current_exposure)),
        company_id=company_id
    )
    
    return HedgingResponse(
        action=recommendation.action.value,
        amount_to_hedge=float(recommendation.amount_to_hedge),
        suggested_rate=float(recommendation.suggested_rate),
        urgency=recommendation.urgency,
        reasoning=recommendation.reasoning
    )

@router.post("/webhooks", status_code=200)
async def register_webhook(
    webhook: WebhookRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Register a webhook URL for real-time risk alerts.
    """
    # Use company_id from user
    company_id = current_user.company_id if current_user.company_id else current_user.id

    success = hedging_service.subscribe_webhook(company_id, str(webhook.url))
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to register webhook")
        
    return {"message": "Webhook registered successfully"}
