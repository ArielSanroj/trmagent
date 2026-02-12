"""Helpers para el motor de politicas."""
from datetime import date
from decimal import Decimal
from typing import List, Dict, Tuple, Optional

from app.atlas.models.atlas_models import Exposure, HedgePolicy, ExposureType, HedgeAction


def group_by_horizon(exposures: List[Exposure], horizons: Dict[str, tuple]) -> Dict[str, List[Exposure]]:
    """Agrupar exposiciones por horizonte temporal"""
    today = date.today()
    grouped = {h: [] for h in horizons.keys()}

    for exposure in exposures:
        days = (exposure.due_date - today).days
        days = max(0, days)

        for horizon, (min_days, max_days) in horizons.items():
            if min_days <= days <= max_days:
                grouped[horizon].append(exposure)
                break

    return grouped


def determine_action(
    exposure: Exposure,
    policy: HedgePolicy,
    horizon: str,
    current_coverage: float,
    target_coverage: float,
    current_rate: Optional[Decimal],
) -> HedgeAction:
    """Determinar accion recomendada"""
    days_to_maturity = max(0, (exposure.due_date - date.today()).days)

    if exposure.amount >= (policy.max_single_exposure or Decimal("999999999")):
        return HedgeAction.REVIEW

    if horizon == "0-30":
        return HedgeAction.HEDGE_NOW

    if horizon in ["31-60", "61-90"]:
        if current_coverage < target_coverage * 0.5:
            return HedgeAction.HEDGE_NOW
        return HedgeAction.HEDGE_PARTIAL

    if current_rate and exposure.target_rate:
        if exposure.exposure_type == ExposureType.PAYABLE:
            if current_rate <= exposure.target_rate:
                return HedgeAction.HEDGE_NOW
        else:
            if current_rate >= exposure.target_rate:
                return HedgeAction.HEDGE_NOW

    return HedgeAction.WAIT


def calculate_priority(
    horizon: str,
    amount_to_hedge: Decimal,
) -> Tuple[int, str]:
    """Calcular prioridad y urgencia"""
    horizon_priority = {
        "0-30": 90,
        "31-60": 70,
        "61-90": 50,
        "91+": 30,
    }
    base = horizon_priority.get(horizon, 50)

    if amount_to_hedge >= Decimal("1000000"):
        base += 10
    elif amount_to_hedge >= Decimal("100000"):
        base += 5

    priority = min(100, base)

    if priority >= 85:
        urgency = "critical"
    elif priority >= 70:
        urgency = "high"
    elif priority >= 50:
        urgency = "normal"
    else:
        urgency = "low"

    return priority, urgency


def calculate_confidence(horizon: str) -> Decimal:
    """Calcular nivel de confianza de la recomendacion"""
    horizon_confidence = {
        "0-30": 95,
        "31-60": 85,
        "61-90": 75,
        "91+": 60,
    }
    return Decimal(str(horizon_confidence.get(horizon, 70)))


def generate_reasoning(
    exposure: Exposure,
    action: HedgeAction,
    horizon: str,
    current_coverage: float,
    target_coverage: float,
    amount_to_hedge: Decimal,
) -> str:
    """Generar explicacion de la recomendacion"""
    exposure_type_es = "cuenta por pagar" if exposure.exposure_type == ExposureType.PAYABLE else "cuenta por cobrar"

    action_texts = {
        HedgeAction.HEDGE_NOW: "Cubrir inmediatamente",
        HedgeAction.HEDGE_PARTIAL: "Realizar cobertura parcial",
        HedgeAction.WAIT: "Esperar mejor oportunidad",
        HedgeAction.REVIEW: "Requiere revision manual",
    }

    reasoning = (
        f"{action_texts[action]}: La exposicion {exposure.reference} "
        f"({exposure_type_es}) por {exposure.currency} {amount_to_hedge:,.2f} "
        f"vence en {exposure.days_to_maturity} dias (horizonte {horizon}). "
        f"Cobertura actual: {current_coverage:.1f}%, objetivo: {target_coverage:.1f}%."
    )

    if action == HedgeAction.HEDGE_NOW:
        reasoning += " El vencimiento proximo requiere accion inmediata."
    elif action == HedgeAction.HEDGE_PARTIAL:
        reasoning += " Se recomienda cubrir parcialmente para reducir exposicion."
    elif action == HedgeAction.WAIT:
        reasoning += " Las condiciones actuales sugieren esperar una mejor tasa."
    elif action == HedgeAction.REVIEW:
        reasoning += " El monto significativo requiere aprobacion adicional."

    return reasoning
