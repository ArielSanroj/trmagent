"""
ATLAS - Exposure Service
Manejo de exposiciones cambiarias: CRUD, carga CSV, agregaciones
"""
import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Dict, Any, BinaryIO
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

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
        today = date.today()

        # Query base para exposiciones abiertas
        base_query = self.db.query(Exposure).filter(
            Exposure.company_id == company_id,
            Exposure.currency == currency,
            Exposure.status.in_([
                ExposureStatus.OPEN,
                ExposureStatus.PARTIALLY_HEDGED
            ])
        )

        # Totales por tipo
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

        # Exposicion neta
        net_exposure = total_payables - total_receivables

        # Cobertura total
        total_exposure = total_payables + total_receivables
        total_hedged = hedged_payables + hedged_receivables
        coverage_pct = (
            (total_hedged / total_exposure * 100) if total_exposure > 0 else Decimal("0")
        )

        # Por horizonte
        by_horizon = self._get_by_horizon(company_id, currency)

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

    def _get_by_horizon(
        self,
        company_id: UUID,
        currency: str = "USD"
    ) -> Dict[str, Dict[str, Any]]:
        """Agrupar exposiciones por horizonte temporal"""
        today = date.today()
        horizons = {
            "0-30": {"min": 0, "max": 30},
            "31-60": {"min": 31, "max": 60},
            "61-90": {"min": 61, "max": 90},
            "91+": {"min": 91, "max": 9999},
        }

        result = {}
        for horizon_name, bounds in horizons.items():
            # Calcular fechas
            from datetime import timedelta
            min_date = today + timedelta(days=bounds["min"])
            max_date = today + timedelta(days=bounds["max"])

            # Query
            query = self.db.query(Exposure).filter(
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

    def get_by_horizon(
        self,
        company_id: UUID,
        horizon: str,
        currency: str = "USD"
    ) -> List[Exposure]:
        """Obtener exposiciones de un horizonte especifico"""
        today = date.today()
        from datetime import timedelta

        horizons = {
            "0-30": (0, 30),
            "31-60": (31, 60),
            "61-90": (61, 90),
            "91+": (91, 9999),
        }

        if horizon not in horizons:
            return []

        min_days, max_days = horizons[horizon]
        min_date = today + timedelta(days=min_days)
        max_date = today + timedelta(days=max_days)

        return self.db.query(Exposure).filter(
            Exposure.company_id == company_id,
            Exposure.currency == currency,
            Exposure.status.in_([ExposureStatus.OPEN, ExposureStatus.PARTIALLY_HEDGED]),
            Exposure.due_date >= min_date,
            Exposure.due_date <= max_date,
        ).order_by(Exposure.due_date).all()

    # =========================================================================
    # CSV Upload
    # =========================================================================

    def upload_csv(
        self,
        company_id: UUID,
        file_content: BinaryIO,
        created_by: Optional[UUID] = None
    ) -> ExposureUploadResult:
        """
        Cargar exposiciones desde archivo CSV.

        Formato esperado:
        reference,type,amount,currency,due_date,counterparty,description,invoice_date

        type: payable o receivable
        """
        result = ExposureUploadResult(
            total_rows=0,
            created=0,
            updated=0,
            errors=0,
            error_details=[]
        )

        try:
            # Decodificar contenido
            content = file_content.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8-sig')  # Handle BOM

            reader = csv.DictReader(io.StringIO(content))

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                result.total_rows += 1

                try:
                    exposure = self._parse_csv_row(
                        company_id=company_id,
                        row=row,
                        row_num=row_num,
                        created_by=created_by
                    )

                    if exposure:
                        # Check if exists by external_id or reference
                        existing = self._find_existing(
                            company_id,
                            row.get('reference', '').strip(),
                            row.get('external_id', '').strip() if row.get('external_id') else None
                        )

                        if existing:
                            # Update existing
                            self._update_from_row(existing, row)
                            result.updated += 1
                        else:
                            # Create new
                            self.db.add(exposure)
                            result.created += 1

                except Exception as e:
                    result.errors += 1
                    result.error_details.append({
                        "row": row_num,
                        "error": str(e),
                        "data": dict(row) if row else None
                    })
                    logger.warning(f"Error parsing row {row_num}: {e}")

            self.db.commit()
            logger.info(
                f"CSV upload completed for company {company_id}: "
                f"{result.created} created, {result.updated} updated, {result.errors} errors"
            )

        except Exception as e:
            self.db.rollback()
            logger.error(f"CSV upload failed: {e}")
            result.errors = result.total_rows
            result.error_details.append({
                "row": 0,
                "error": f"Failed to process file: {str(e)}",
                "data": None
            })

        return result

    def _parse_csv_row(
        self,
        company_id: UUID,
        row: Dict[str, str],
        row_num: int,
        created_by: Optional[UUID] = None
    ) -> Optional[Exposure]:
        """Parsear una fila del CSV"""
        # Campos requeridos
        reference = row.get('reference', '').strip()
        if not reference:
            raise ValueError("reference is required")

        exposure_type_str = row.get('type', '').strip().lower()
        if exposure_type_str not in ['payable', 'receivable']:
            raise ValueError(f"type must be 'payable' or 'receivable', got '{exposure_type_str}'")

        amount_str = row.get('amount', '').strip().replace(',', '')
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError("amount must be positive")
        except InvalidOperation:
            raise ValueError(f"Invalid amount: {amount_str}")

        due_date_str = row.get('due_date', '').strip()
        try:
            # Try multiple date formats
            due_date = self._parse_date(due_date_str)
        except:
            raise ValueError(f"Invalid due_date: {due_date_str}")

        # Campos opcionales
        currency = row.get('currency', 'USD').strip().upper() or 'USD'
        description = row.get('description', '').strip() or None

        invoice_date = None
        if row.get('invoice_date'):
            try:
                invoice_date = self._parse_date(row.get('invoice_date', '').strip())
            except:
                pass

        # Buscar contraparte
        counterparty_id = None
        counterparty_name = row.get('counterparty', '').strip()
        if counterparty_name:
            counterparty = self.db.query(Counterparty).filter(
                Counterparty.company_id == company_id,
                Counterparty.name.ilike(counterparty_name)
            ).first()
            if counterparty:
                counterparty_id = counterparty.id

        # Tasas opcionales
        original_rate = self._parse_decimal(row.get('original_rate', ''))
        budget_rate = self._parse_decimal(row.get('budget_rate', ''))
        target_rate = self._parse_decimal(row.get('target_rate', ''))

        return Exposure(
            company_id=company_id,
            counterparty_id=counterparty_id,
            exposure_type=ExposureType(exposure_type_str),
            reference=reference,
            description=description,
            currency=currency,
            amount=amount,
            original_rate=original_rate,
            budget_rate=budget_rate,
            target_rate=target_rate,
            invoice_date=invoice_date,
            due_date=due_date,
            external_id=row.get('external_id', '').strip() or None,
            source="csv_upload",
            created_by=created_by,
        )

    def _parse_date(self, date_str: str) -> date:
        """Parsear fecha en varios formatos"""
        formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d']
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Cannot parse date: {date_str}")

    def _parse_decimal(self, value_str: str) -> Optional[Decimal]:
        """Parsear decimal opcional"""
        if not value_str:
            return None
        try:
            return Decimal(value_str.strip().replace(',', ''))
        except:
            return None

    def _find_existing(
        self,
        company_id: UUID,
        reference: str,
        external_id: Optional[str]
    ) -> Optional[Exposure]:
        """Buscar exposicion existente"""
        query = self.db.query(Exposure).filter(
            Exposure.company_id == company_id
        )

        if external_id:
            existing = query.filter(Exposure.external_id == external_id).first()
            if existing:
                return existing

        return query.filter(Exposure.reference == reference).first()

    def _update_from_row(self, exposure: Exposure, row: Dict[str, str]) -> None:
        """Actualizar exposicion existente desde fila CSV"""
        if row.get('amount'):
            try:
                exposure.amount = Decimal(row['amount'].strip().replace(',', ''))
            except:
                pass

        if row.get('due_date'):
            try:
                exposure.due_date = self._parse_date(row['due_date'].strip())
            except:
                pass

        if row.get('description'):
            exposure.description = row['description'].strip()

        exposure.updated_at = datetime.utcnow()

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
