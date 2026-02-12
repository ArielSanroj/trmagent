"""
ATLAS - Exposure Service
Manejo de exposiciones cambiarias: CRUD, carga CSV, agregaciones
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, BinaryIO
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.atlas.models.atlas_models import (
    Exposure,
    Counterparty,
    ExposureType,
    ExposureStatus,
)
from app.atlas.models.schemas import (
    ExposureCreate,
    ExposureUpdate,
    ExposureSummary,
    ExposureUploadResult,
)
from app.atlas.services.exposure_csv import upload_csv_exposures
from app.atlas.services.exposure_aggregations import build_summary, list_by_horizon

logger = logging.getLogger(__name__)


class ExposureService:
    """Servicio para gestion de exposiciones cambiarias"""

    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def create(
        self,
        company_id: UUID,
        data: ExposureCreate,
        created_by: Optional[UUID] = None
    ) -> Exposure:
        """Crear nueva exposicion"""
        exposure = Exposure(
            company_id=company_id,
            counterparty_id=data.counterparty_id,
            exposure_type=data.exposure_type,
            reference=data.reference,
            description=data.description,
            currency=data.currency,
            amount=data.amount,
            original_rate=data.original_rate,
            target_rate=data.target_rate,
            budget_rate=data.budget_rate,
            invoice_date=data.invoice_date,
            due_date=data.due_date,
            tags=data.tags,
            external_id=data.external_id,
            notes=data.notes,
            source="manual",
            created_by=created_by,
        )
        self.db.add(exposure)
        self.db.commit()
        self.db.refresh(exposure)
        logger.info(f"Created exposure {exposure.id} for company {company_id}")
        return exposure

    def get(self, exposure_id: UUID, company_id: UUID) -> Optional[Exposure]:
        """Obtener exposicion por ID"""
        return self.db.query(Exposure).filter(
            Exposure.id == exposure_id,
            Exposure.company_id == company_id
        ).first()

    def list(
        self,
        company_id: UUID,
        exposure_type: Optional[ExposureType] = None,
        status: Optional[ExposureStatus] = None,
        counterparty_id: Optional[UUID] = None,
        due_date_from: Optional[date] = None,
        due_date_to: Optional[date] = None,
        min_amount: Optional[Decimal] = None,
        currency: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Exposure]:
        """Listar exposiciones con filtros"""
        query = self.db.query(Exposure).filter(Exposure.company_id == company_id)

        if exposure_type:
            query = query.filter(Exposure.exposure_type == exposure_type)
        if status:
            query = query.filter(Exposure.status == status)
        if counterparty_id:
            query = query.filter(Exposure.counterparty_id == counterparty_id)
        if due_date_from:
            query = query.filter(Exposure.due_date >= due_date_from)
        if due_date_to:
            query = query.filter(Exposure.due_date <= due_date_to)
        if min_amount:
            query = query.filter(Exposure.amount >= min_amount)
        if currency:
            query = query.filter(Exposure.currency == currency)

        return query.order_by(Exposure.due_date).offset(skip).limit(limit).all()

    def update(
        self,
        exposure_id: UUID,
        company_id: UUID,
        data: ExposureUpdate
    ) -> Optional[Exposure]:
        """Actualizar exposicion"""
        exposure = self.get(exposure_id, company_id)
        if not exposure:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(exposure, field, value)

        exposure.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(exposure)
        logger.info(f"Updated exposure {exposure_id}")
        return exposure

    def delete(self, exposure_id: UUID, company_id: UUID) -> bool:
        """Eliminar exposicion (soft delete via status)"""
        exposure = self.get(exposure_id, company_id)
        if not exposure:
            return False

        exposure.status = ExposureStatus.CANCELLED
        exposure.updated_at = datetime.utcnow()
        self.db.commit()
        logger.info(f"Cancelled exposure {exposure_id}")
        return True

    # =========================================================================
    # Aggregations
    # =========================================================================

    def get_summary(
        self,
        company_id: UUID,
        currency: str = "USD"
    ) -> ExposureSummary:
        """Obtener resumen agregado de exposiciones"""
        return build_summary(self.db, company_id, currency)

    def get_by_horizon(
        self,
        company_id: UUID,
        horizon: str,
        currency: str = "USD"
    ) -> List[Exposure]:
        """Obtener exposiciones de un horizonte especifico"""
        return list_by_horizon(self.db, company_id, horizon, currency)

    # =========================================================================
    # CSV Upload
    # =========================================================================

    def upload_csv(
        self,
        company_id: UUID,
        file_content: BinaryIO,
        created_by: Optional[UUID] = None
    ) -> ExposureUploadResult:
        return upload_csv_exposures(
            db=self.db,
            company_id=company_id,
            file_content=file_content,
            created_by=created_by,
            logger=logger
        )

    # =========================================================================
    # Hedge Management
    # =========================================================================

    def update_hedge_amount(
        self,
        exposure_id: UUID,
        company_id: UUID,
        hedged_amount: Decimal
    ) -> Optional[Exposure]:
        """Actualizar monto cubierto de una exposicion"""
        exposure = self.get(exposure_id, company_id)
        if not exposure:
            return None

        exposure.amount_hedged = hedged_amount
        exposure.hedge_percentage = (
            (hedged_amount / exposure.amount * 100)
            if exposure.amount > 0 else Decimal("0")
        )

        # Actualizar estado
        if hedged_amount >= exposure.amount:
            exposure.status = ExposureStatus.FULLY_HEDGED
        elif hedged_amount > 0:
            exposure.status = ExposureStatus.PARTIALLY_HEDGED
        else:
            exposure.status = ExposureStatus.OPEN

        exposure.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(exposure)
        return exposure

    # =========================================================================
    # Counterparty Management
    # =========================================================================

    def create_counterparty(
        self,
        company_id: UUID,
        name: str,
        **kwargs
    ) -> Counterparty:
        """Crear nueva contraparte"""
        counterparty = Counterparty(
            company_id=company_id,
            name=name,
            **kwargs
        )
        self.db.add(counterparty)
        self.db.commit()
        self.db.refresh(counterparty)
        return counterparty

    def list_counterparties(
        self,
        company_id: UUID,
        counterparty_type: Optional[str] = None,
        is_active: bool = True
    ) -> List[Counterparty]:
        """Listar contrapartes"""
        query = self.db.query(Counterparty).filter(
            Counterparty.company_id == company_id,
            Counterparty.is_active == is_active
        )
        if counterparty_type:
            query = query.filter(Counterparty.counterparty_type == counterparty_type)
        return query.order_by(Counterparty.name).all()
