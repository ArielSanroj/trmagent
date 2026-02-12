"""
ATLAS - Policies API Endpoints
"""
from typing import List, Optional, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.database_models import User
from app.atlas.models.schemas import (
    HedgePolicyCreate,
    HedgePolicyUpdate,
    HedgePolicyResponse,
    PolicySimulationRequest,
    PolicySimulationResult,
)
from app.atlas.services.policy_engine import PolicyEngine

router = APIRouter(prefix="/policies", tags=["ATLAS - Policies"])


def get_policy_engine(db: Session = Depends(get_db)) -> PolicyEngine:
    return PolicyEngine(db)


@router.post("/", response_model=HedgePolicyResponse)
async def create_policy(
    data: HedgePolicyCreate,
    engine: PolicyEngine = Depends(get_policy_engine),
    current_user: User = Depends(get_current_user)
):
    """Create a new hedge policy"""
    policy = engine.create_policy(
        company_id=current_user.company_id,
        name=data.name,
        coverage_rules=data.coverage_rules,
        description=data.description,
        exposure_type=data.exposure_type,
        currency=data.currency,
        counterparty_category=data.counterparty_category,
        min_amount=data.min_amount,
        max_single_exposure=data.max_single_exposure,
        rate_tolerance_up=data.rate_tolerance_up,
        rate_tolerance_down=data.rate_tolerance_down,
        auto_generate_recommendations=data.auto_generate_recommendations,
        require_approval_above=data.require_approval_above,
        is_default=data.is_default,
        priority=data.priority,
        created_by=current_user.id,
    )
    return policy


@router.get("/", response_model=List[HedgePolicyResponse])
async def list_policies(
    is_active: bool = Query(default=True),
    engine: PolicyEngine = Depends(get_policy_engine),
    current_user: User = Depends(get_current_user)
):
    """List all hedge policies"""
    return engine.list_policies(
        company_id=current_user.company_id,
        is_active=is_active
    )


@router.get("/default", response_model=HedgePolicyResponse)
async def get_default_policy(
    engine: PolicyEngine = Depends(get_policy_engine),
    current_user: User = Depends(get_current_user)
):
    """Get the default hedge policy"""
    policy = engine.get_default_policy(current_user.company_id)
    if not policy:
        raise HTTPException(
            status_code=404,
            detail="No default policy configured"
        )
    return policy


@router.get("/{policy_id}", response_model=HedgePolicyResponse)
async def get_policy(
    policy_id: UUID,
    engine: PolicyEngine = Depends(get_policy_engine),
    current_user: User = Depends(get_current_user)
):
    """Get policy by ID"""
    policy = engine.get_policy(policy_id, current_user.company_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.put("/{policy_id}", response_model=HedgePolicyResponse)
async def update_policy(
    policy_id: UUID,
    data: HedgePolicyUpdate,
    engine: PolicyEngine = Depends(get_policy_engine),
    current_user: User = Depends(get_current_user)
):
    """Update a hedge policy"""
    updates = data.model_dump(exclude_unset=True)
    policy = engine.update_policy(
        policy_id=policy_id,
        company_id=current_user.company_id,
        **updates
    )
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.post("/{policy_id}/simulate", response_model=PolicySimulationResult)
async def simulate_policy(
    policy_id: UUID,
    engine: PolicyEngine = Depends(get_policy_engine),
    current_user: User = Depends(get_current_user)
):
    """
    Simulate applying a policy without generating recommendations.

    Useful to preview impact of policy changes.
    """
    result = engine.simulate_policy(
        company_id=current_user.company_id,
        policy_id=policy_id,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/simulate", response_model=PolicySimulationResult)
async def simulate_custom_rules(
    data: PolicySimulationRequest,
    engine: PolicyEngine = Depends(get_policy_engine),
    current_user: User = Depends(get_current_user)
):
    """
    Simulate custom coverage rules without saving a policy.

    Useful for what-if analysis.
    """
    result = engine.simulate_policy(
        company_id=current_user.company_id,
        policy_id=data.policy_id,
        coverage_rules=data.coverage_rules,
    )
    return result
