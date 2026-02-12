"""
ATLAS - Policy Engine (Core Logic)
Motor de evaluacion de politicas de cobertura.
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.atlas.models.atlas_models import HedgePolicy, HedgeRecommendation
from app.atlas.services.policy_engine_core import evaluate_policy, simulate_policy

logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    Motor de politicas de cobertura.

    Evalua exposiciones contra politicas y genera recomendaciones
    de cobertura optimizadas.
    """

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
        """
        if policy_id:
            policy = self.get_policy(policy_id, company_id)
        else:
            policy = self.get_default_policy(company_id)

        if not policy:
            logger.warning(f"No policy found for company {company_id}")
            return []

        return evaluate_policy(
            db=self.db,
            company_id=company_id,
            policy=policy,
            exposure_ids=exposure_ids,
            current_rate=current_rate,
            horizons=self.DEFAULT_HORIZONS,
            logger=logger,
        )

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
        """
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

        return simulate_policy(
            db=self.db,
            company_id=company_id,
            rules=rules,
            horizons=self.DEFAULT_HORIZONS,
        )
