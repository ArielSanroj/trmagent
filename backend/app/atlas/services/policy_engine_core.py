"""Core de evaluacion y simulacion de politicas."""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.atlas.models.atlas_models import (
    Exposure,
    HedgePolicy,
    HedgeRecommendation,
    ExposureStatus,
)
from app.atlas.services.policy_engine_helpers import (
    group_by_horizon,
    determine_action,
    calculate_priority,
    calculate_confidence,
    generate_reasoning,
)


def get_exposures_to_evaluate(
    db: Session,
    company_id: UUID,
    exposure_ids: Optional[List[UUID]],
    policy: HedgePolicy
) -> List[Exposure]:
    """Obtener exposiciones a evaluar"""
    query = db.query(Exposure).filter(
        Exposure.company_id == company_id,
        Exposure.status.in_([
            ExposureStatus.OPEN,
            ExposureStatus.PARTIALLY_HEDGED
        ])
    )

    if exposure_ids:
        query = query.filter(Exposure.id.in_(exposure_ids))

    if policy.exposure_type:
        query = query.filter(Exposure.exposure_type == policy.exposure_type)

    if policy.currency:
        query = query.filter(Exposure.currency == policy.currency)

    if policy.min_amount:
        query = query.filter(Exposure.amount >= policy.min_amount)

    return query.order_by(Exposure.due_date).all()


def evaluate_exposure(
    exposure: Exposure,
    policy: HedgePolicy,
    target_coverage: int,
    horizon: str,
    current_rate: Optional[Decimal],
) -> Optional[HedgeRecommendation]:
    """Evaluar una exposicion individual y generar recomendacion."""
    current_coverage = float(exposure.hedge_percentage or 0)
    target_coverage_pct = float(target_coverage)

    if current_coverage >= target_coverage_pct:
        return None

    amount_open = exposure.amount - (exposure.amount_hedged or Decimal("0"))
    target_hedged = exposure.amount * Decimal(str(target_coverage)) / 100
    amount_to_hedge = target_hedged - (exposure.amount_hedged or Decimal("0"))

    if amount_to_hedge <= 0:
        return None

    action = determine_action(
        exposure=exposure,
        policy=policy,
        horizon=horizon,
        current_coverage=current_coverage,
        target_coverage=target_coverage_pct,
        current_rate=current_rate,
    )

    priority, urgency = calculate_priority(
        horizon=horizon,
        amount_to_hedge=amount_to_hedge,
    )

    reasoning = generate_reasoning(
        exposure=exposure,
        action=action,
        horizon=horizon,
        current_coverage=current_coverage,
        target_coverage=target_coverage_pct,
        amount_to_hedge=amount_to_hedge,
    )

    factors = {
        "horizon": horizon,
        "days_to_maturity": exposure.days_to_maturity,
        "exposure_type": exposure.exposure_type.value,
        "policy_target_coverage": target_coverage,
        "current_rate": float(current_rate) if current_rate else None,
    }

    confidence = calculate_confidence(horizon)

    valid_hours = 24 if urgency in ['high', 'critical'] else 48
    valid_until = datetime.utcnow() + timedelta(hours=valid_hours)

    return HedgeRecommendation(
        company_id=exposure.company_id,
        exposure_id=exposure.id,
        policy_id=policy.id,
        action=action,
        currency=exposure.currency,
        amount_to_hedge=amount_to_hedge,
        current_coverage=Decimal(str(current_coverage)),
        target_coverage=Decimal(str(target_coverage_pct)),
        current_rate=current_rate,
        priority=priority,
        urgency=urgency,
        reasoning=reasoning,
        factors=factors,
        confidence=confidence,
        status="pending",
        valid_until=valid_until,
    )


def evaluate_policy(
    db: Session,
    company_id: UUID,
    policy: HedgePolicy,
    exposure_ids: Optional[List[UUID]],
    current_rate: Optional[Decimal],
    horizons: Dict[str, tuple],
    logger,
) -> List[HedgeRecommendation]:
    """Evaluar exposiciones y generar recomendaciones."""
    exposures = get_exposures_to_evaluate(db, company_id, exposure_ids, policy)

    if not exposures:
        logger.info(f"No exposures to evaluate for company {company_id}")
        return []

    grouped = group_by_horizon(exposures, horizons)

    recommendations: List[HedgeRecommendation] = []
    for horizon, horizon_exposures in grouped.items():
        target_coverage = policy.coverage_rules.get(horizon, 0)

        for exposure in horizon_exposures:
            recommendation = evaluate_exposure(
                exposure=exposure,
                policy=policy,
                target_coverage=target_coverage,
                horizon=horizon,
                current_rate=current_rate,
            )
            if recommendation:
                recommendations.append(recommendation)

    for rec in recommendations:
        db.add(rec)
    db.commit()

    for rec in recommendations:
        db.refresh(rec)

    logger.info(
        f"Generated {len(recommendations)} recommendations "
        f"for company {company_id}"
    )

    return recommendations


def simulate_policy(
    db: Session,
    company_id: UUID,
    rules: Dict[str, int],
    horizons: Dict[str, tuple],
) -> Dict[str, Any]:
    """Simular aplicacion de politica sin generar recomendaciones."""
    exposures = db.query(Exposure).filter(
        Exposure.company_id == company_id,
        Exposure.status.in_([
            ExposureStatus.OPEN,
            ExposureStatus.PARTIALLY_HEDGED
        ])
    ).all()

    grouped = group_by_horizon(exposures, horizons)

    total_exposure = Decimal("0")
    would_hedge = Decimal("0")
    by_horizon: Dict[str, Any] = {}
    estimated_orders = 0

    for horizon, horizon_exposures in grouped.items():
        target_pct = rules.get(horizon, 0)
        horizon_total = sum(e.amount for e in horizon_exposures)
        horizon_hedged = sum(e.amount_hedged or Decimal("0") for e in horizon_exposures)
        horizon_target = horizon_total * Decimal(str(target_pct)) / 100
        horizon_to_hedge = max(Decimal("0"), horizon_target - horizon_hedged)

        total_exposure += horizon_total
        would_hedge += horizon_to_hedge

        for exp in horizon_exposures:
            current_hedged = exp.amount_hedged or Decimal("0")
            target = exp.amount * Decimal(str(target_pct)) / 100
            if target > current_hedged:
                estimated_orders += 1

        by_horizon[horizon] = {
            "total": float(horizon_total),
            "current_hedged": float(horizon_hedged),
            "target_coverage_pct": target_pct,
            "would_hedge": float(horizon_to_hedge),
            "exposures_count": len(horizon_exposures),
        }

    coverage_pct = (
        (would_hedge / total_exposure * 100)
        if total_exposure > 0 else Decimal("0")
    )

    return {
        "total_exposure": float(total_exposure),
        "would_hedge": float(would_hedge),
        "coverage_percentage": float(coverage_pct.quantize(Decimal("0.01"))),
        "by_horizon": by_horizon,
        "estimated_orders": estimated_orders,
    }
