"""Helpers de reportes para paper trading."""
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from app.core.database import SessionLocal
from app.models.database_models import Order


def build_portfolio_summary(portfolio, current_trm: Optional[Decimal] = None) -> dict:
    """Construir resumen del portafolio de paper trading"""
    trm = current_trm or Decimal("4200")

    usd_value_cop = portfolio.usd_balance * trm
    total_value_cop = portfolio.cop_balance + usd_value_cop

    initial_capital = Decimal("100000000")
    total_pnl = total_value_cop - initial_capital
    pnl_pct = (total_pnl / initial_capital) * 100

    return {
        "company_id": str(portfolio.company_id) if portfolio.company_id else None,
        "usd_balance": float(portfolio.usd_balance),
        "cop_balance": float(portfolio.cop_balance),
        "usd_value_cop": float(usd_value_cop),
        "total_value_cop": float(total_value_cop),
        "total_pnl": float(total_pnl),
        "pnl_pct": float(pnl_pct),
        "total_trades": portfolio.total_trades,
        "profitable_trades": portfolio.profitable_trades,
        "win_rate": (
            portfolio.profitable_trades / portfolio.total_trades * 100
            if portfolio.total_trades > 0 else 0
        ),
        "current_trm": float(trm),
        "created_at": portfolio.created_at.isoformat()
    }


def list_trade_history(
    company_id: Optional[UUID] = None,
    limit: int = 50
) -> List[dict]:
    """Obtener historial de trades de paper trading"""
    db = SessionLocal()
    try:
        query = db.query(Order).filter(Order.is_paper_trade == True)

        if company_id:
            query = query.filter(Order.company_id == company_id)

        orders = query.order_by(Order.created_at.desc()).limit(limit).all()

        return [
            {
                "id": str(o.id),
                "side": o.side,
                "amount": float(o.amount),
                "rate": float(o.executed_rate) if o.executed_rate else None,
                "status": o.status.value,
                "created_at": o.created_at.isoformat(),
                "executed_at": o.executed_at.isoformat() if o.executed_at else None
            }
            for o in orders
        ]

    finally:
        db.close()
