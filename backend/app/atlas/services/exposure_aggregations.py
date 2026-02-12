"""Agregaciones para exposiciones."""
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, Any, List
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.atlas.models.atlas_models import Exposure, ExposureType, ExposureStatus
from app.atlas.models.schemas import ExposureSummary

HORIZON_BOUNDS = {
    "0-30": (0, 30),
    "31-60": (31, 60),
    "61-90": (61, 90),
    "91+": (91, 9999),
}


def build_summary(db: Session, company_id: UUID, currency: str = "USD") -> ExposureSummary:
    """Obtener resumen agregado de exposiciones"""
    base_query = db.query(Exposure).filter(
        Exposure.company_id == company_id,
        Exposure.currency == currency,
        Exposure.status.in_([
            ExposureStatus.OPEN,
            ExposureStatus.PARTIALLY_HEDGED
        ])
    )

    payables = base_query.filter(
        Exposure.exposure_type == ExposureType.PAYABLE
    ).with_entities(
        func.coalesce(func.sum(Exposure.amount), 0).label('total'),
        func.coalesce(func.sum(Exposure.amount_hedged), 0).label('hedged'),
        func.count(Exposure.id).label('count')
    ).first()

    receivables = base_query.filter(
        Exposure.exposure_type == ExposureType.RECEIVABLE
    ).with_entities(
        func.coalesce(func.sum(Exposure.amount), 0).label('total'),
        func.coalesce(func.sum(Exposure.amount_hedged), 0).label('hedged'),
        func.count(Exposure.id).label('count')
    ).first()

    total_payables = Decimal(str(payables.total)) if payables.total else Decimal("0")
    total_receivables = Decimal(str(receivables.total)) if receivables.total else Decimal("0")
    hedged_payables = Decimal(str(payables.hedged)) if payables.hedged else Decimal("0")
    hedged_receivables = Decimal(str(receivables.hedged)) if receivables.hedged else Decimal("0")

    net_exposure = total_payables - total_receivables
    total_exposure = total_payables + total_receivables
    total_hedged = hedged_payables + hedged_receivables
    coverage_pct = (
        (total_hedged / total_exposure * 100) if total_exposure > 0 else Decimal("0")
    )

    by_horizon = build_by_horizon(db, company_id, currency)

    return ExposureSummary(
        total_payables=total_payables,
        total_receivables=total_receivables,
        total_hedged_payables=hedged_payables,
        total_hedged_receivables=hedged_receivables,
        net_exposure=net_exposure,
        coverage_percentage=coverage_pct.quantize(Decimal("0.01")),
        exposures_count=int(payables.count or 0) + int(receivables.count or 0),
        by_horizon=by_horizon,
    )


def build_by_horizon(
    db: Session,
    company_id: UUID,
    currency: str = "USD"
) -> Dict[str, Dict[str, Any]]:
    """Agrupar exposiciones por horizonte temporal"""
    today = date.today()
    result: Dict[str, Dict[str, Any]] = {}

    for horizon_name, bounds in HORIZON_BOUNDS.items():
        min_date = today + timedelta(days=bounds[0])
        max_date = today + timedelta(days=bounds[1])

        query = db.query(Exposure).filter(
            Exposure.company_id == company_id,
            Exposure.currency == currency,
            Exposure.status.in_([ExposureStatus.OPEN, ExposureStatus.PARTIALLY_HEDGED]),
            Exposure.due_date >= min_date,
            Exposure.due_date <= max_date,
        )

        agg = query.with_entities(
            func.coalesce(func.sum(Exposure.amount), 0).label('total'),
            func.coalesce(func.sum(Exposure.amount_hedged), 0).label('hedged'),
            func.count(Exposure.id).label('count')
        ).first()

        total = Decimal(str(agg.total)) if agg.total else Decimal("0")
        hedged = Decimal(str(agg.hedged)) if agg.hedged else Decimal("0")
        coverage = (hedged / total * 100) if total > 0 else Decimal("0")

        result[horizon_name] = {
            "total": float(total),
            "hedged": float(hedged),
            "open": float(total - hedged),
            "count": int(agg.count or 0),
            "coverage_pct": float(coverage.quantize(Decimal("0.01"))),
        }

    return result


def list_by_horizon(
    db: Session,
    company_id: UUID,
    horizon: str,
    currency: str = "USD"
) -> List[Exposure]:
    """Obtener exposiciones de un horizonte especifico"""
    if horizon not in HORIZON_BOUNDS:
        return []

    today = date.today()
    min_days, max_days = HORIZON_BOUNDS[horizon]
    min_date = today + timedelta(days=min_days)
    max_date = today + timedelta(days=max_days)

    return db.query(Exposure).filter(
        Exposure.company_id == company_id,
        Exposure.currency == currency,
        Exposure.status.in_([ExposureStatus.OPEN, ExposureStatus.PARTIALLY_HEDGED]),
        Exposure.due_date >= min_date,
        Exposure.due_date <= max_date,
    ).order_by(Exposure.due_date).all()
