"""
ATLAS - Policy Engine (Core Logic)
Motor de evaluacion de politicas de cobertura.

Flujo:
1. Agrupar exposiciones por horizonte (0-30, 31-60, 61-90, 91+)
2. Aplicar reglas de cobertura segun politica
3. Calcular monto a cubrir = target - ya_cubierto
4. Determinar urgencia y prioridad
5. Generar HedgeRecommendation con reasoning
"""
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.atlas.models.atlas_models import (
    Exposure,
    HedgePolicy,
    HedgeRecommendation,
    ExposureType,
    ExposureStatus,
    HedgeAction,
    RecommendationStatus,
)

logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    Motor de politicas de cobertura.

    Evalua exposiciones contra politicas y genera recomendaciones
    de cobertura optimizadas.
    """

    # Horizons por defecto (en dias)
    DEFAULT_HORIZONS = {
        "0-30": (0, 30),
        "31-60": (31, 60),
        "61-90": (61, 90),
        "91+": (91, 9999),
    }

    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # Policy CRUD
    # =========================================================================

    def create_policy(
        self,
        company_id: UUID,
        name: str,
        coverage_rules: Dict[str, int],
        **kwargs
    ) -> HedgePolicy:
        """Crear nueva politica de cobertura"""
        # Si es default, quitar default de otras
        if kwargs.get('is_default'):
            self._clear_default_policies(company_id)

        policy = HedgePolicy(
            company_id=company_id,
            name=name,
            coverage_rules=coverage_rules,
            **kwargs
        )
        self.db.add(policy)
        self.db.commit()
        self.db.refresh(policy)
        logger.info(f"Created policy {policy.id}: {name}")
        return policy

    def get_policy(self, policy_id: UUID, company_id: UUID) -> Optional[HedgePolicy]:
        """Obtener politica por ID"""
        return self.db.query(HedgePolicy).filter(
            HedgePolicy.id == policy_id,
            HedgePolicy.company_id == company_id
        ).first()

    def list_policies(
        self,
        company_id: UUID,
        is_active: bool = True
    ) -> List[HedgePolicy]:
        """Listar politicas"""
        return self.db.query(HedgePolicy).filter(
            HedgePolicy.company_id == company_id,
            HedgePolicy.is_active == is_active
        ).order_by(HedgePolicy.priority).all()

    def get_default_policy(self, company_id: UUID) -> Optional[HedgePolicy]:
        """Obtener politica por defecto"""
        return self.db.query(HedgePolicy).filter(
            HedgePolicy.company_id == company_id,
            HedgePolicy.is_default == True,
            HedgePolicy.is_active == True
        ).first()

    def update_policy(
        self,
        policy_id: UUID,
        company_id: UUID,
        **updates
    ) -> Optional[HedgePolicy]:
        """Actualizar politica"""
        policy = self.get_policy(policy_id, company_id)
        if not policy:
            return None

        # Si se esta poniendo como default
        if updates.get('is_default'):
            self._clear_default_policies(company_id, exclude_id=policy_id)

        for key, value in updates.items():
            if hasattr(policy, key):
                setattr(policy, key, value)

        policy.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def _clear_default_policies(
        self,
        company_id: UUID,
        exclude_id: Optional[UUID] = None
    ):
        """Quitar flag default de otras politicas"""
        query = self.db.query(HedgePolicy).filter(
            HedgePolicy.company_id == company_id,
            HedgePolicy.is_default == True
        )
        if exclude_id:
            query = query.filter(HedgePolicy.id != exclude_id)
        query.update({"is_default": False})

    # =========================================================================
    # Policy Evaluation
    # =========================================================================

    def evaluate(
        self,
        company_id: UUID,
        policy_id: Optional[UUID] = None,
        exposure_ids: Optional[List[UUID]] = None,
        current_rate: Optional[Decimal] = None,
    ) -> List[HedgeRecommendation]:
        """
        Evaluar exposiciones y generar recomendaciones.

        Args:
            company_id: ID de la empresa
            policy_id: ID de politica a usar (o default)
            exposure_ids: Lista especifica de exposiciones (o todas abiertas)
            current_rate: Tasa actual TRM (para calculos)

        Returns:
            Lista de recomendaciones generadas
        """
        # Obtener politica
        if policy_id:
            policy = self.get_policy(policy_id, company_id)
        else:
            policy = self.get_default_policy(company_id)

        if not policy:
            logger.warning(f"No policy found for company {company_id}")
            return []

        # Obtener exposiciones
        exposures = self._get_exposures_to_evaluate(
            company_id, exposure_ids, policy
        )

        if not exposures:
            logger.info(f"No exposures to evaluate for company {company_id}")
            return []

        # Agrupar por horizonte
        grouped = self._group_by_horizon(exposures)

        # Generar recomendaciones
        recommendations = []
        for horizon, horizon_exposures in grouped.items():
            target_coverage = policy.coverage_rules.get(horizon, 0)

            for exposure in horizon_exposures:
                recommendation = self._evaluate_exposure(
                    exposure=exposure,
                    policy=policy,
                    target_coverage=target_coverage,
                    horizon=horizon,
                    current_rate=current_rate,
                )
                if recommendation:
                    recommendations.append(recommendation)

        # Guardar recomendaciones
        for rec in recommendations:
            self.db.add(rec)
        self.db.commit()

        for rec in recommendations:
            self.db.refresh(rec)

        logger.info(
            f"Generated {len(recommendations)} recommendations "
            f"for company {company_id}"
        )
        return recommendations

    def _get_exposures_to_evaluate(
        self,
        company_id: UUID,
        exposure_ids: Optional[List[UUID]],
        policy: HedgePolicy
    ) -> List[Exposure]:
        """Obtener exposiciones a evaluar"""
        query = self.db.query(Exposure).filter(
            Exposure.company_id == company_id,
            Exposure.status.in_([
                ExposureStatus.OPEN,
                ExposureStatus.PARTIALLY_HEDGED
            ])
        )

        # Filtrar por IDs especificos
        if exposure_ids:
            query = query.filter(Exposure.id.in_(exposure_ids))

        # Filtrar por tipo de exposicion de la politica
        if policy.exposure_type:
            query = query.filter(Exposure.exposure_type == policy.exposure_type)

        # Filtrar por moneda
        if policy.currency:
            query = query.filter(Exposure.currency == policy.currency)

        # Filtrar por monto minimo
        if policy.min_amount:
            query = query.filter(Exposure.amount >= policy.min_amount)

        return query.order_by(Exposure.due_date).all()

    def _group_by_horizon(
        self,
        exposures: List[Exposure]
    ) -> Dict[str, List[Exposure]]:
        """Agrupar exposiciones por horizonte temporal"""
        today = date.today()
        grouped = {h: [] for h in self.DEFAULT_HORIZONS.keys()}

        for exposure in exposures:
            days = (exposure.due_date - today).days
            days = max(0, days)  # No permitir negativos

            for horizon, (min_days, max_days) in self.DEFAULT_HORIZONS.items():
                if min_days <= days <= max_days:
                    grouped[horizon].append(exposure)
                    break

        return grouped

    def _evaluate_exposure(
        self,
        exposure: Exposure,
        policy: HedgePolicy,
        target_coverage: int,
        horizon: str,
        current_rate: Optional[Decimal] = None,
    ) -> Optional[HedgeRecommendation]:
        """
        Evaluar una exposicion individual y generar recomendacion.
        """
        # Calcular cobertura actual
        current_coverage = float(exposure.hedge_percentage or 0)
        target_coverage_pct = float(target_coverage)

        # Si ya esta cubierto al nivel objetivo, no recomendar
        if current_coverage >= target_coverage_pct:
            return None

        # Calcular monto a cubrir
        amount_open = exposure.amount - (exposure.amount_hedged or Decimal("0"))
        target_hedged = exposure.amount * Decimal(str(target_coverage)) / 100
        amount_to_hedge = target_hedged - (exposure.amount_hedged or Decimal("0"))

        if amount_to_hedge <= 0:
            return None

        # Determinar accion
        action = self._determine_action(
            exposure=exposure,
            policy=policy,
            horizon=horizon,
            current_coverage=current_coverage,
            target_coverage=target_coverage_pct,
            current_rate=current_rate,
        )

        # Calcular prioridad y urgencia
        priority, urgency = self._calculate_priority(
            exposure=exposure,
            horizon=horizon,
            amount_to_hedge=amount_to_hedge,
        )

        # Generar reasoning
        reasoning = self._generate_reasoning(
            exposure=exposure,
            action=action,
            horizon=horizon,
            current_coverage=current_coverage,
            target_coverage=target_coverage_pct,
            amount_to_hedge=amount_to_hedge,
        )

        # Factores considerados
        factors = {
            "horizon": horizon,
            "days_to_maturity": exposure.days_to_maturity,
            "exposure_type": exposure.exposure_type.value,
            "policy_target_coverage": target_coverage,
            "current_rate": float(current_rate) if current_rate else None,
        }

        # Confianza basada en horizonte y policy match
        confidence = self._calculate_confidence(horizon, policy)

        # Validez: 24 horas para urgentes, 48 para normales
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
            days_to_maturity=exposure.days_to_maturity,
            reasoning=reasoning,
            factors=factors,
            confidence=confidence,
            status=RecommendationStatus.PENDING,
            valid_until=valid_until,
        )

    def _determine_action(
        self,
        exposure: Exposure,
        policy: HedgePolicy,
        horizon: str,
        current_coverage: float,
        target_coverage: float,
        current_rate: Optional[Decimal] = None,
    ) -> HedgeAction:
        """Determinar accion recomendada"""
        # Criterios para HEDGE_NOW
        if horizon == "0-30":
            return HedgeAction.HEDGE_NOW

        if current_coverage < 25 and target_coverage >= 50:
            return HedgeAction.HEDGE_NOW

        # Criterios para HEDGE_PARTIAL
        coverage_gap = target_coverage - current_coverage
        if coverage_gap > 25:
            return HedgeAction.HEDGE_PARTIAL

        # Verificar tolerancia de tasa
        if current_rate and exposure.target_rate:
            rate_diff_pct = abs(
                (current_rate - exposure.target_rate) / exposure.target_rate * 100
            )
            if rate_diff_pct > float(policy.rate_tolerance_up):
                return HedgeAction.WAIT

        # Si es monto grande, requiere revision
        if policy.max_single_exposure:
            if exposure.amount > policy.max_single_exposure:
                return HedgeAction.REVIEW

        # Default: cobertura parcial para horizontes medios
        if horizon in ["31-60", "61-90"]:
            return HedgeAction.HEDGE_PARTIAL

        # Para 91+, normalmente esperar
        return HedgeAction.WAIT

    def _calculate_priority(
        self,
        exposure: Exposure,
        horizon: str,
        amount_to_hedge: Decimal,
    ) -> Tuple[int, str]:
        """Calcular prioridad y urgencia"""
        # Base priority por horizonte
        horizon_priority = {
            "0-30": 90,
            "31-60": 70,
            "61-90": 50,
            "91+": 30,
        }
        base = horizon_priority.get(horizon, 50)

        # Ajustar por monto (mas grande = mas prioridad)
        if amount_to_hedge >= Decimal("1000000"):
            base += 10
        elif amount_to_hedge >= Decimal("100000"):
            base += 5

        priority = min(100, base)

        # Determinar urgencia
        if priority >= 85:
            urgency = "critical"
        elif priority >= 70:
            urgency = "high"
        elif priority >= 50:
            urgency = "normal"
        else:
            urgency = "low"

        return priority, urgency

    def _calculate_confidence(
        self,
        horizon: str,
        policy: HedgePolicy
    ) -> Decimal:
        """Calcular nivel de confianza de la recomendacion"""
        # Mayor confianza para horizontes cortos
        horizon_confidence = {
            "0-30": 95,
            "31-60": 85,
            "61-90": 75,
            "91+": 60,
        }
        return Decimal(str(horizon_confidence.get(horizon, 70)))

    def _generate_reasoning(
        self,
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

    # =========================================================================
    # Simulation
    # =========================================================================

    def simulate_policy(
        self,
        company_id: UUID,
        policy_id: Optional[UUID] = None,
        coverage_rules: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Simular aplicacion de politica sin generar recomendaciones.

        Util para preview de cambios de politica.
        """
        # Obtener politica o usar reglas custom
        if policy_id:
            policy = self.get_policy(policy_id, company_id)
            if not policy:
                return {"error": "Policy not found"}
            rules = policy.coverage_rules
        else:
            rules = coverage_rules or {
                "0-30": 100,
                "31-60": 75,
                "61-90": 50,
                "91+": 25
            }

        # Obtener exposiciones abiertas
        exposures = self.db.query(Exposure).filter(
            Exposure.company_id == company_id,
            Exposure.status.in_([
                ExposureStatus.OPEN,
                ExposureStatus.PARTIALLY_HEDGED
            ])
        ).all()

        # Agrupar
        grouped = self._group_by_horizon(exposures)

        # Calcular totales
        total_exposure = Decimal("0")
        would_hedge = Decimal("0")
        by_horizon = {}
        estimated_orders = 0

        for horizon, horizon_exposures in grouped.items():
            target_pct = rules.get(horizon, 0)
            horizon_total = sum(e.amount for e in horizon_exposures)
            horizon_hedged = sum(e.amount_hedged or Decimal("0") for e in horizon_exposures)
            horizon_target = horizon_total * Decimal(str(target_pct)) / 100
            horizon_to_hedge = max(Decimal("0"), horizon_target - horizon_hedged)

            total_exposure += horizon_total
            would_hedge += horizon_to_hedge

            # Contar ordenes
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
