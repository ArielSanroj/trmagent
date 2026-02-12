"""CSV helpers para exposiciones."""
import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, Any, BinaryIO
from uuid import UUID

from sqlalchemy.orm import Session

from app.atlas.models.atlas_models import (
    Exposure,
    Counterparty,
    ExposureType,
    ExposureStatus,
)
from app.atlas.models.schemas import ExposureUploadResult


def upload_csv_exposures(
    db: Session,
    company_id: UUID,
    file_content: BinaryIO,
    logger,
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
        content = file_content.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8-sig')

        reader = csv.DictReader(io.StringIO(content))

        for row_num, row in enumerate(reader, start=2):
            result.total_rows += 1
            try:
                exposure = parse_csv_row(
                    db=db,
                    company_id=company_id,
                    row=row,
                    row_num=row_num,
                    created_by=created_by
                )

                if exposure:
                    existing = find_existing(
                        db,
                        company_id,
                        row.get('reference', '').strip(),
                        row.get('external_id', '').strip() if row.get('external_id') else None
                    )

                    if existing:
                        update_from_row(existing, row)
                        result.updated += 1
                    else:
                        db.add(exposure)
                        result.created += 1

            except Exception as exc:
                result.errors += 1
                result.error_details.append({
                    "row": row_num,
                    "error": str(exc),
                    "data": dict(row) if row else None
                })
                logger.warning(f"Error parsing row {row_num}: {exc}")

        db.commit()
        logger.info(
            f"CSV upload completed for company {company_id}: "
            f"{result.created} created, {result.updated} updated, {result.errors} errors"
        )

    except Exception as exc:
        db.rollback()
        logger.error(f"CSV upload failed: {exc}")
        result.errors = result.total_rows
        result.error_details.append({
            "row": 0,
            "error": f"Failed to process file: {str(exc)}",
            "data": None
        })

    return result


def parse_csv_row(
    db: Session,
    company_id: UUID,
    row: Dict[str, str],
    row_num: int,
    created_by: Optional[UUID] = None
) -> Optional[Exposure]:
    """Parsear una fila del CSV"""
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
        due_date = parse_date(due_date_str)
    except Exception:
        raise ValueError(f"Invalid due_date: {due_date_str}")

    currency = row.get('currency', 'USD').strip().upper() or 'USD'
    description = row.get('description', '').strip() or None

    invoice_date = None
    if row.get('invoice_date'):
        try:
            invoice_date = parse_date(row.get('invoice_date', '').strip())
        except Exception:
            pass

    counterparty_id = None
    counterparty_name = row.get('counterparty', '').strip()
    if counterparty_name:
        counterparty = db.query(Counterparty).filter(
            Counterparty.company_id == company_id,
            Counterparty.name.ilike(counterparty_name)
        ).first()
        if counterparty:
            counterparty_id = counterparty.id

    original_rate = parse_decimal(row.get('original_rate', ''))
    budget_rate = parse_decimal(row.get('budget_rate', ''))
    target_rate = parse_decimal(row.get('target_rate', ''))

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


def parse_date(date_str: str) -> date:
    """Parsear fecha en varios formatos"""
    formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str}")


def parse_decimal(value_str: str) -> Optional[Decimal]:
    """Parsear decimal opcional"""
    if not value_str:
        return None
    try:
        return Decimal(value_str.strip().replace(',', ''))
    except Exception:
        return None


def find_existing(
    db: Session,
    company_id: UUID,
    reference: str,
    external_id: Optional[str]
) -> Optional[Exposure]:
    """Buscar exposicion existente"""
    query = db.query(Exposure).filter(
        Exposure.company_id == company_id
    )

    if external_id:
        existing = query.filter(Exposure.external_id == external_id).first()
        if existing:
            return existing

    return query.filter(Exposure.reference == reference).first()


def update_from_row(exposure: Exposure, row: Dict[str, str]) -> None:
    """Actualizar exposicion existente desde fila CSV"""
    if row.get('amount'):
        try:
            exposure.amount = Decimal(row['amount'].strip().replace(',', ''))
        except Exception:
            pass

    if row.get('due_date'):
        try:
            exposure.due_date = parse_date(row['due_date'].strip())
        except Exception:
            pass

    if row.get('description'):
        exposure.description = row['description'].strip()

    exposure.updated_at = datetime.utcnow()
