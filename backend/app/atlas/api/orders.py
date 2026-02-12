"""
ATLAS - Orders API Endpoints
"""
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.database_models import User
from app.atlas.models.atlas_models import OrderStatus
from app.atlas.models.schemas import (
    HedgeOrderCreate,
    HedgeOrderUpdate,
    HedgeOrderResponse,
    HedgeOrderWithDetails,
    QuoteCreate,
    QuoteResponse,
    TradeCreate,
    TradeResponse,
)
from app.atlas.services.order_orchestrator import OrderOrchestrator

router = APIRouter(prefix="/orders", tags=["ATLAS - Orders"])


def get_order_orchestrator(db: Session = Depends(get_db)) -> OrderOrchestrator:
    return OrderOrchestrator(db)


# ============================================================================
# Orders CRUD
# ============================================================================

@router.post("/", response_model=HedgeOrderResponse)
async def create_order(
    data: HedgeOrderCreate,
    orchestrator: OrderOrchestrator = Depends(get_order_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """Create a new hedge order"""
    # Get current market rate (simplified)
    current_rate = None  # TODO: Get from market data

    order = orchestrator.create_order(
        company_id=current_user.company_id,
        data=data,
        created_by=current_user.id,
        current_rate=current_rate,
    )
    return order


@router.post("/from-recommendation/{recommendation_id}", response_model=HedgeOrderResponse)
async def create_order_from_recommendation(
    recommendation_id: UUID,
    order_type: str = Query(default="spot"),
    orchestrator: OrderOrchestrator = Depends(get_order_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """Create an order from an accepted recommendation"""
    current_rate = None  # TODO: Get from market data

    order = orchestrator.create_from_recommendation(
        recommendation_id=recommendation_id,
        company_id=current_user.company_id,
        created_by=current_user.id,
        current_rate=current_rate,
        order_type=order_type,
    )
    if not order:
        raise HTTPException(
            status_code=400,
            detail="Cannot create order from recommendation (not found or not pending)"
        )
    return order


@router.get("/", response_model=List[HedgeOrderResponse])
async def list_orders(
    status: Optional[OrderStatus] = None,
    exposure_id: Optional[UUID] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    orchestrator: OrderOrchestrator = Depends(get_order_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """List orders with optional filters"""
    return orchestrator.list_orders(
        company_id=current_user.company_id,
        status=status,
        exposure_id=exposure_id,
        from_date=from_date,
        to_date=to_date,
        skip=skip,
        limit=limit,
    )


@router.get("/summary")
async def get_orders_summary(
    orchestrator: OrderOrchestrator = Depends(get_order_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """Get summary of orders"""
    return orchestrator.get_order_summary(current_user.company_id)


@router.get("/{order_id}", response_model=HedgeOrderResponse)
async def get_order(
    order_id: UUID,
    orchestrator: OrderOrchestrator = Depends(get_order_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """Get order by ID"""
    order = orchestrator.get_order(order_id, current_user.company_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.put("/{order_id}", response_model=HedgeOrderResponse)
async def update_order(
    order_id: UUID,
    data: HedgeOrderUpdate,
    orchestrator: OrderOrchestrator = Depends(get_order_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """Update an order (only if draft or pending approval)"""
    order = orchestrator.update_order(
        order_id=order_id,
        company_id=current_user.company_id,
        data=data
    )
    if not order:
        raise HTTPException(
            status_code=400,
            detail="Cannot update order (not found or wrong status)"
        )
    return order


# ============================================================================
# Approval Workflow
# ============================================================================

@router.post("/{order_id}/approve", response_model=HedgeOrderResponse)
async def approve_order(
    order_id: UUID,
    orchestrator: OrderOrchestrator = Depends(get_order_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """Approve an order that requires approval"""
    order = orchestrator.approve_order(
        order_id=order_id,
        company_id=current_user.company_id,
        approved_by=current_user.id
    )
    if not order:
        raise HTTPException(
            status_code=400,
            detail="Cannot approve order (not found or not pending approval)"
        )
    return order


@router.post("/{order_id}/reject")
async def reject_order(
    order_id: UUID,
    reason: Optional[str] = None,
    orchestrator: OrderOrchestrator = Depends(get_order_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """Reject an order"""
    order = orchestrator.reject_order(
        order_id=order_id,
        company_id=current_user.company_id,
        reason=reason
    )
    if not order:
        raise HTTPException(
            status_code=400,
            detail="Cannot reject order"
        )
    return {"status": "rejected", "id": str(order_id)}


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: UUID,
    reason: Optional[str] = None,
    orchestrator: OrderOrchestrator = Depends(get_order_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """Cancel an order"""
    order = orchestrator.cancel_order(
        order_id=order_id,
        company_id=current_user.company_id,
        reason=reason
    )
    if not order:
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel order (not found or already executed)"
        )
    return {"status": "cancelled", "id": str(order_id)}


# ============================================================================
# Quotes
# ============================================================================

@router.post("/{order_id}/quotes/", response_model=QuoteResponse)
async def add_quote(
    order_id: UUID,
    data: QuoteCreate,
    orchestrator: OrderOrchestrator = Depends(get_order_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """Add a quote to an order"""
    quote = orchestrator.add_quote(
        order_id=order_id,
        company_id=current_user.company_id,
        data=data
    )
    if not quote:
        raise HTTPException(status_code=404, detail="Order not found")
    return quote


@router.post("/{order_id}/quotes/{quote_id}/accept", response_model=QuoteResponse)
async def accept_quote(
    order_id: UUID,
    quote_id: UUID,
    orchestrator: OrderOrchestrator = Depends(get_order_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """Accept a specific quote"""
    quote = orchestrator.accept_quote(
        quote_id=quote_id,
        order_id=order_id,
        company_id=current_user.company_id
    )
    if not quote:
        raise HTTPException(
            status_code=400,
            detail="Cannot accept quote (not found or expired)"
        )
    return quote


# ============================================================================
# Execution
# ============================================================================

@router.post("/{order_id}/execute", response_model=TradeResponse)
async def execute_order(
    order_id: UUID,
    data: TradeCreate,
    orchestrator: OrderOrchestrator = Depends(get_order_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """
    Execute an order and create a trade.

    This records the actual execution details and updates the
    associated exposure's hedge amount.
    """
    trade = orchestrator.execute_order(
        order_id=order_id,
        company_id=current_user.company_id,
        trade_data=data,
        executed_by=current_user.id
    )
    if not trade:
        raise HTTPException(
            status_code=400,
            detail="Cannot execute order (not found or wrong status)"
        )
    return trade
