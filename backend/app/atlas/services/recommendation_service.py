"""
ATLAS - Recommendation Service
Gestion de recomendaciones de cobertura.
"""
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.atlas.models.atlas_models import (
    HedgeRecommendation,
    Exposure,
    HedgePolicy,
    HedgeAction,
    RecommendationStatus,
    ExposureStatus,
)
from app.atlas.models.schemas import RecommendationCalendar

logger = logging.getLogger(__name__)


class RecommendationService:
    """Servicio para gestion de recomendaciones de cobertura"""

    def __init__(self, db: Session):
        self.db = db

    def get(
        self,
        recommendation_id: UUID,
        company_id: UUID
    ) -> Optional[HedgeRecommendation]:
        """Obtener recomendacion por ID"""
        return self.db.query(HedgeRecommendation).filter(
            HedgeRecommendation.id == recommendation_id,
            HedgeRecommendation.company_id == company_id
        ).first()

    def list(
        self,
        company_id: UUID,
        status: Optional[RecommendationStatus] = None,
        action: Optional[HedgeAction] = None,
        exposure_id: Optional[UUID] = None,
        urgency: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        include_expired: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> List[HedgeRecommendation]:
        """Listar recomendaciones con filtros"""
        query = self.db.query(HedgeRecommendation).filter(
            HedgeRecommendation.company_id == company_id
        )

        if status:
            query = query.filter(HedgeRecommendation.status == status)
        if action:
            query = query.filter(HedgeRecommendation.action == action)
        if exposure_id:
            query = query.filter(HedgeRecommendation.exposure_id == exposure_id)
        if urgency:
            query = query.filter(HedgeRecommendation.urgency == urgency)
        if from_date:
            query = query.filter(HedgeRecommendation.created_at >= from_date)
        if to_date:
            query = query.filter(HedgeRecommendation.created_at <= to_date)

        # Por defecto excluir expiradas
        if not include_expired:
            query = query.filter(
                (HedgeRecommendation.valid_until == None) |
                (HedgeRecommendation.valid_until > datetime.utcnow())
            )

        return query.order_by(
            HedgeRecommendation.priority.desc(),
            HedgeRecommendation.created_at.desc()
        ).offset(skip).limit(limit).all()

    def list_pending(self, company_id: UUID) -> List[HedgeRecommendation]:
        """Listar recomendaciones pendientes y no expiradas"""
        return self.list(
            company_id=company_id,
            status=RecommendationStatus.PENDING,
            include_expired=False
        )

    def accept(
        self,
        recommendation_id: UUID,
        company_id: UUID,
        decided_by: Optional[UUID] = None
    ) -> Optional[HedgeRecommendation]:
        """Aceptar recomendacion"""
        recommendation = self.get(recommendation_id, company_id)
        if not recommendation:
            return None

        if recommendation.status != RecommendationStatus.PENDING:
            logger.warning(
                f"Cannot accept recommendation {recommendation_id}: "
                f"status is {recommendation.status}"
            )
            return None

        recommendation.status = RecommendationStatus.ACCEPTED
        recommendation.decided_at = datetime.utcnow()
        recommendation.decided_by = decided_by

        self.db.commit()
        self.db.refresh(recommendation)
        logger.info(f"Accepted recommendation {recommendation_id}")
        return recommendation

    def reject(
        self,
        recommendation_id: UUID,
        company_id: UUID,
        reason: Optional[str] = None,
        decided_by: Optional[UUID] = None
    ) -> Optional[HedgeRecommendation]:
        """Rechazar recomendacion"""
        recommendation = self.get(recommendation_id, company_id)
        if not recommendation:
            return None

        if recommendation.status != RecommendationStatus.PENDING:
            logger.warning(
                f"Cannot reject recommendation {recommendation_id}: "
                f"status is {recommendation.status}"
            )
            return None

        recommendation.status = RecommendationStatus.REJECTED
        recommendation.rejection_reason = reason
        recommendation.decided_at = datetime.utcnow()
        recommendation.decided_by = decided_by

        self.db.commit()
        self.db.refresh(recommendation)
        logger.info(f"Rejected recommendation {recommendation_id}")
        return recommendation

    def expire_old(self, company_id: UUID) -> int:
        """Expirar recomendaciones vencidas"""
        now = datetime.utcnow()
        count = self.db.query(HedgeRecommendation).filter(
            HedgeRecommendation.company_id == company_id,
            HedgeRecommendation.status == RecommendationStatus.PENDING,
            HedgeRecommendation.valid_until < now
        ).update({"status": RecommendationStatus.EXPIRED})

        self.db.commit()
        logger.info(f"Expired {count} recommendations for company {company_id}")
        return count

    def get_calendar(
        self,
        company_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        days: int = 30,
    ) -> List[RecommendationCalendar]:
        """
        Obtener calendario de recomendaciones agrupadas por fecha de vencimiento
        de la exposicion asociada.
        """
        if not start_date:
            start_date = date.today()
        if not end_date:
            end_date = start_date + timedelta(days=days)

        # Obtener recomendaciones pendientes con exposicion
        recommendations = self.db.query(HedgeRecommendation).join(
            Exposure, HedgeRecommendation.exposure_id == Exposure.id
        ).filter(
            HedgeRecommendation.company_id == company_id,
            HedgeRecommendation.status == RecommendationStatus.PENDING,
            Exposure.due_date >= start_date,
            Exposure.due_date <= end_date,
        ).order_by(Exposure.due_date).all()

        # Agrupar por fecha
        by_date: Dict[date, List[HedgeRecommendation]] = {}
        for rec in recommendations:
            if rec.exposure:
                due = rec.exposure.due_date
                if due not in by_date:
                    by_date[due] = []
                by_date[due].append(rec)

        # Construir calendario
        calendar = []
        for dt in sorted(by_date.keys()):
            recs = by_date[dt]
            total_amount = sum(r.amount_to_hedge for r in recs)

            # Contar por prioridad
            priority_breakdown = {"critical": 0, "high": 0, "normal": 0, "low": 0}
            for r in recs:
                urgency = r.urgency or "normal"
                if urgency in priority_breakdown:
                    priority_breakdown[urgency] += 1

            calendar.append(RecommendationCalendar(
                date=dt,
                recommendations=recs,
                total_amount=total_amount,
                priority_breakdown=priority_breakdown,
            ))

        return calendar

    def get_summary(self, company_id: UUID) -> Dict[str, Any]:
        """Obtener resumen de recomendaciones"""
        pending = self.db.query(HedgeRecommendation).filter(
            HedgeRecommendation.company_id == company_id,
            HedgeRecommendation.status == RecommendationStatus.PENDING,
        )

        # Total pendientes
        pending_count = pending.count()

        # Total monto a cubrir
        total_amount = pending.with_entities(
            func.coalesce(func.sum(HedgeRecommendation.amount_to_hedge), 0)
        ).scalar()

        # Por urgencia
        by_urgency = {}
        for urgency in ['critical', 'high', 'normal', 'low']:
            count = pending.filter(
                HedgeRecommendation.urgency == urgency
            ).count()
            by_urgency[urgency] = count

        # Por accion
        by_action = {}
        for action in HedgeAction:
            count = pending.filter(
                HedgeRecommendation.action == action
            ).count()
            by_action[action.value] = count

        return {
            "pending_count": pending_count,
            "total_amount_to_hedge": float(total_amount),
            "by_urgency": by_urgency,
            "by_action": by_action,
        }
