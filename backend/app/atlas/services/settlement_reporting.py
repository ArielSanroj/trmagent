"""Reportes y calendario de liquidaciones."""
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.atlas.models.atlas_models import Settlement, Trade, SettlementStatus


def build_settlement_calendar(
    db: Session,
    company_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    days: int = 30
) -> Dict[date, Dict[str, Any]]:
    """Obtener calendario de liquidaciones."""
    if not start_date:
        start_date = date.today()
    if not end_date:
        end_date = start_date + timedelta(days=days)

    settlements = db.query(Settlement).join(
        Trade, Settlement.trade_id == Trade.id
    ).filter(
        Trade.company_id == company_id,
        Settlement.settlement_date >= start_date,
        Settlement.settlement_date <= end_date,
    ).all()

    calendar: Dict[date, Dict[str, Any]] = {}
    for settlement in settlements:
        dt = settlement.settlement_date
        if dt not in calendar:
            calendar[dt] = {
                "total_amount": Decimal("0"),
                "by_currency": {},
                "count": 0,
                "settlements": []
            }

        calendar[dt]["total_amount"] += settlement.amount
        calendar[dt]["count"] += 1
        calendar[dt]["settlements"].append({
            "id": str(settlement.id),
            "currency": settlement.currency,
            "amount": float(settlement.amount),
            "status": settlement.status.value,
        })

        currency = settlement.currency
        if currency not in calendar[dt]["by_currency"]:
            calendar[dt]["by_currency"][currency] = Decimal("0")
        calendar[dt]["by_currency"][currency] += settlement.amount

    for dt in calendar:
        calendar[dt]["total_amount"] = float(calendar[dt]["total_amount"])
        calendar[dt]["by_currency"] = {
            k: float(v) for k, v in calendar[dt]["by_currency"].items()
        }

    return calendar


def build_settlement_summary(db: Session, company_id: int) -> Dict[str, Any]:
    """Obtener resumen de liquidaciones"""
    today = date.today()

    pending_today = db.query(Settlement).join(
        Trade, Settlement.trade_id == Trade.id
    ).filter(
        Trade.company_id == company_id,
        Settlement.settlement_date == today,
        Settlement.status == SettlementStatus.PENDING
    ).all()

    next_week = today + timedelta(days=7)
    pending_week = db.query(Settlement).join(
        Trade, Settlement.trade_id == Trade.id
    ).filter(
        Trade.company_id == company_id,
        Settlement.settlement_date > today,
        Settlement.settlement_date <= next_week,
        Settlement.status == SettlementStatus.PENDING
    ).all()

    return {
        "pending_today_count": len(pending_today),
        "pending_today_amount": float(sum(s.amount for s in pending_today)),
        "pending_week_count": len(pending_week),
        "pending_week_amount": float(sum(s.amount for s in pending_week)),
        "by_status": {
            status.value: db.query(Settlement).join(
                Trade, Settlement.trade_id == Trade.id
            ).filter(
                Trade.company_id == company_id,
                Settlement.status == status
            ).count()
            for status in SettlementStatus
        }
    }
