"""
API de Trading
Senales, ordenes, portafolio

Refactorizado para Clean Architecture:
- Opcion de usar Dependency Injection
- Mantiene compatibilidad con singleton decision_engine
"""
from datetime import date, datetime, timedelta
from typing import Optional, List
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.decision_engine import decision_engine, DecisionEngine, create_decision_engine
from app.services.paper_trading import paper_trading_service
from app.services.notification_service import notification_service
from app.services.data_ingestion import data_ingestion_service
from app.models.database_models import (
    TradingSignal, Order, User, SignalStatus, OrderStatus
)
from app.models.schemas import (
    TradingSignalResponse, OrderCreate, OrderResponse,
    PortfolioSummary, SignalEvaluation
)
from app.api.v1.auth import get_current_user

# Clean Architecture imports
from app.api.dependencies import get_ml_registry
from app.core.container import get_container, Container

router = APIRouter(prefix="/trading", tags=["Trading"])


# Dependency para obtener DecisionEngine via DI
def get_decision_engine(
    model_type: str = "ensemble",
    container: Container = Depends(get_container)
) -> DecisionEngine:
    """
    Dependency: Obtener DecisionEngine con modelo especifico

    Uso:
        @router.get("/signals")
        def get_signals(engine: DecisionEngine = Depends(get_decision_engine)):
            return engine.generate_signal()
    """
    ml_model = container.ml_registry.get_model(model_type)
    uow_factory = container.get_uow_factory()
    return DecisionEngine(ml_model=ml_model, uow_factory=uow_factory)


# ==================== SIGNALS ====================

@router.get("/signals/current", response_model=SignalEvaluation)
async def get_current_signal(
    current_user: User = Depends(get_current_user)
):
    """
    Obtener senal de trading actual
    Genera una nueva evaluacion en tiempo real
    """
    decision = decision_engine.generate_signal(company_id=current_user.company_id)

    signal_response = TradingSignalResponse(
        id=UUID('00000000-0000-0000-0000-000000000000'),  # Temporal
        action=decision.action.value,
        confidence=decision.confidence,
        predicted_trm=decision.predicted_trm,
        current_trm=decision.current_trm,
        expected_return=decision.expected_return,
        risk_score=decision.risk_score,
        reasoning=decision.reasoning,
        status="evaluated",
        expires_at=datetime.utcnow() + timedelta(hours=4),
        created_at=datetime.utcnow()
    )

    return SignalEvaluation(
        signal=signal_response,
        recommendation=(
            f"{'EJECUTAR' if decision.approved else 'NO EJECUTAR'}: "
            f"{decision.reasoning}"
        ),
        alerts_sent=False
    )


@router.post("/signals/evaluate")
async def evaluate_and_notify(
    current_user: User = Depends(get_current_user)
):
    """
    Evaluar mercado y enviar alertas si hay oportunidad
    """
    decision = decision_engine.generate_signal(company_id=current_user.company_id)

    # Guardar senal si es relevante
    signal_id = None
    if decision.action.value != "HOLD":
        signal_id = decision_engine.save_signal_to_db(decision, current_user.company_id)

    # Enviar alertas si esta aprobada
    alerts_sent = {}
    if decision.approved:
        alerts_sent = await notification_service.send_trading_alert(decision)

    return {
        "signal_id": str(signal_id) if signal_id else None,
        "action": decision.action.value,
        "confidence": float(decision.confidence),
        "expected_return": float(decision.expected_return),
        "approved": decision.approved,
        "alerts_sent": alerts_sent,
        "reasoning": decision.reasoning
    }


@router.get("/signals/history")
async def get_signal_history(
    limit: int = Query(default=50, le=200),
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtener historial de senales
    """
    query = db.query(TradingSignal)

    if current_user.company_id:
        query = query.filter(TradingSignal.company_id == current_user.company_id)

    if status:
        query = query.filter(TradingSignal.status == status)

    signals = query.order_by(
        TradingSignal.created_at.desc()
    ).limit(limit).all()

    return {
        "signals": [
            {
                "id": str(s.id),
                "action": s.action.value,
                "confidence": float(s.confidence),
                "predicted_trm": float(s.predicted_trm),
                "current_trm": float(s.current_trm),
                "expected_return": float(s.expected_return) if s.expected_return else None,
                "status": s.status.value,
                "created_at": s.created_at.isoformat()
            }
            for s in signals
        ],
        "count": len(signals)
    }


# ==================== SIGNALS CON DI ====================

@router.get("/signals/evaluate-with-model/{model_type}")
async def evaluate_with_specific_model(
    model_type: str,
    current_user: User = Depends(get_current_user),
    container: Container = Depends(get_container)
):
    """
    Evaluar mercado usando un modelo ML especifico

    Nuevo endpoint: Permite elegir el modelo (prophet, lstm, ensemble)
    Usa Dependency Injection para el DecisionEngine
    """
    try:
        ml_model = container.ml_registry.get_model(model_type)
    except ValueError:
        available = container.ml_registry.available_models()
        raise HTTPException(
            status_code=400,
            detail=f"Modelo invalido: {model_type}. Disponibles: {', '.join(available)}"
        )

    # Crear engine con modelo especifico
    engine = DecisionEngine(
        ml_model=ml_model,
        uow_factory=container.get_uow_factory()
    )

    decision = engine.generate_signal(company_id=current_user.company_id)

    return {
        "model_type": model_type,
        "action": decision.action.value,
        "confidence": float(decision.confidence),
        "predicted_trm": float(decision.predicted_trm),
        "current_trm": float(decision.current_trm),
        "expected_return": float(decision.expected_return),
        "risk_score": float(decision.risk_score),
        "signal_strength": decision.signal_strength.value,
        "approved": decision.approved,
        "reasoning": decision.reasoning
    }


# ==================== ORDERS ====================

@router.post("/orders/create", response_model=OrderResponse)
async def create_order(
    order: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Crear orden de trading (paper trading por defecto)
    """
    # Obtener TRM actual
    trm = await data_ingestion_service.get_current_trm()
    if not trm:
        raise HTTPException(status_code=503, detail="Could not get current TRM")

    current_rate = trm["value"]

    if order.is_paper_trade:
        # Ejecutar en paper trading
        decision = decision_engine.generate_signal(company_id=current_user.company_id)

        result = paper_trading_service.execute_paper_trade(
            decision=decision,
            amount_cop=order.amount * current_rate,  # Convertir a COP
            company_id=current_user.company_id
        )

        if not result["success"]:
            raise HTTPException(
                status_code=400,
                detail=result.get("reason", "Trade execution failed")
            )

        # Obtener orden creada
        db_order = db.query(Order).filter(Order.id == result["order_id"]).first()

    else:
        # Orden real (no implementado completamente)
        db_order = Order(
            company_id=current_user.company_id,
            signal_id=order.signal_id,
            broker="manual",
            order_type=order.order_type,
            side=order.side,
            amount=order.amount,
            currency="USD",
            requested_rate=current_rate,
            status=OrderStatus.PENDING,
            is_paper_trade=False
        )
        db.add(db_order)
        db.commit()
        db.refresh(db_order)

    return db_order


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtener detalle de una orden
    """
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return order


@router.delete("/orders/{order_id}")
async def cancel_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancelar orden pendiente
    """
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if order.status != OrderStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel order with status: {order.status.value}"
        )

    order.status = OrderStatus.CANCELLED
    db.commit()

    return {"message": "Order cancelled", "order_id": str(order_id)}


@router.get("/orders")
async def get_orders(
    limit: int = Query(default=50, le=200),
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtener historial de ordenes
    """
    query = db.query(Order)

    if current_user.company_id:
        query = query.filter(Order.company_id == current_user.company_id)

    if status:
        query = query.filter(Order.status == status)

    orders = query.order_by(Order.created_at.desc()).limit(limit).all()

    return {
        "orders": [
            {
                "id": str(o.id),
                "side": o.side,
                "amount": float(o.amount),
                "executed_rate": float(o.executed_rate) if o.executed_rate else None,
                "status": o.status.value,
                "is_paper_trade": o.is_paper_trade,
                "created_at": o.created_at.isoformat()
            }
            for o in orders
        ],
        "count": len(orders)
    }


# ==================== PORTFOLIO ====================

@router.get("/portfolio/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(
    current_user: User = Depends(get_current_user)
):
    """
    Obtener resumen del portafolio (paper trading)
    """
    trm = await data_ingestion_service.get_current_trm()
    current_rate = Decimal(str(trm["value"])) if trm else Decimal("4200")

    summary = paper_trading_service.get_portfolio_summary(
        company_id=current_user.company_id,
        current_trm=current_rate
    )

    return PortfolioSummary(
        total_usd=Decimal(str(summary["usd_balance"])),
        total_cop=Decimal(str(summary["cop_balance"])),
        total_value_cop=Decimal(str(summary["total_value_cop"])),
        unrealized_pnl=Decimal("0"),  # TODO: Calcular
        realized_pnl=Decimal(str(summary["total_pnl"])),
        daily_pnl=Decimal("0"),  # TODO: Calcular
        open_positions=1 if summary["usd_balance"] > 0 else 0
    )


@router.post("/portfolio/reset")
async def reset_portfolio(
    current_user: User = Depends(get_current_user)
):
    """
    Resetear portafolio de paper trading
    """
    success = paper_trading_service.reset_portfolio(current_user.company_id)

    return {
        "success": success,
        "message": "Portfolio reset successfully" if success else "Portfolio not found"
    }
