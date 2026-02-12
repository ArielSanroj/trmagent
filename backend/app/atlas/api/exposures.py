"""
ATLAS - Exposures API Endpoints
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.database_models import User
from app.atlas.models.atlas_models import ExposureType, ExposureStatus
from app.atlas.models.schemas import (
    ExposureCreate,
    ExposureUpdate,
    ExposureResponse,
    ExposureWithCounterparty,
    ExposureSummary,
    ExposureUploadResult,
    CounterpartyCreate,
    CounterpartyUpdate,
    CounterpartyResponse,
)
from app.atlas.services.exposure_service import ExposureService

router = APIRouter(prefix="/exposures", tags=["ATLAS - Exposures"])


def get_exposure_service(db: Session = Depends(get_db)) -> ExposureService:
    return ExposureService(db)


# ============================================================================
# Exposures CRUD
# ============================================================================

@router.post("/", response_model=ExposureResponse)
async def create_exposure(
    data: ExposureCreate,
    service: ExposureService = Depends(get_exposure_service),
    current_user: User = Depends(get_current_user)
):
    """Create a new exposure"""
    exposure = service.create(
        company_id=current_user.company_id,
        data=data,
        created_by=current_user.id
    )
    return exposure


@router.post("/upload", response_model=ExposureUploadResult)
async def upload_exposures(
    file: UploadFile = File(...),
    service: ExposureService = Depends(get_exposure_service),
    current_user: User = Depends(get_current_user)
):
    """
    Upload exposures from CSV file.

    Expected CSV format:
    reference,type,amount,currency,due_date,counterparty,description,invoice_date

    - type: payable or receivable
    - due_date: YYYY-MM-DD
    """
    if not file.filename.endswith(('.csv', '.CSV')):
        raise HTTPException(
            status_code=400,
            detail="File must be a CSV"
        )

    result = service.upload_csv(
        company_id=current_user.company_id,
        file_content=file.file,
        created_by=current_user.id
    )
    return result


@router.get("/", response_model=List[ExposureResponse])
async def list_exposures(
    exposure_type: Optional[ExposureType] = None,
    status: Optional[ExposureStatus] = None,
    counterparty_id: Optional[UUID] = None,
    due_date_from: Optional[date] = None,
    due_date_to: Optional[date] = None,
    min_amount: Optional[Decimal] = None,
    currency: Optional[str] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    service: ExposureService = Depends(get_exposure_service),
    current_user: User = Depends(get_current_user)
):
    """List exposures with optional filters"""
    exposures = service.list(
        company_id=current_user.company_id,
        exposure_type=exposure_type,
        status=status,
        counterparty_id=counterparty_id,
        due_date_from=due_date_from,
        due_date_to=due_date_to,
        min_amount=min_amount,
        currency=currency,
        skip=skip,
        limit=limit,
    )
    return exposures


@router.get("/summary", response_model=ExposureSummary)
async def get_exposures_summary(
    currency: str = Query(default="USD"),
    service: ExposureService = Depends(get_exposure_service),
    current_user: User = Depends(get_current_user)
):
    """Get aggregated summary of exposures"""
    return service.get_summary(
        company_id=current_user.company_id,
        currency=currency
    )


@router.get("/by-horizon")
async def get_exposures_by_horizon(
    horizon: str = Query(..., pattern="^(0-30|31-60|61-90|91\\+)$"),
    currency: str = Query(default="USD"),
    service: ExposureService = Depends(get_exposure_service),
    current_user: User = Depends(get_current_user)
):
    """Get exposures for a specific time horizon"""
    exposures = service.get_by_horizon(
        company_id=current_user.company_id,
        horizon=horizon,
        currency=currency
    )
    return exposures


@router.get("/{exposure_id}", response_model=ExposureResponse)
async def get_exposure(
    exposure_id: UUID,
    service: ExposureService = Depends(get_exposure_service),
    current_user: User = Depends(get_current_user)
):
    """Get exposure by ID"""
    exposure = service.get(exposure_id, current_user.company_id)
    if not exposure:
        raise HTTPException(status_code=404, detail="Exposure not found")
    return exposure


@router.put("/{exposure_id}", response_model=ExposureResponse)
async def update_exposure(
    exposure_id: UUID,
    data: ExposureUpdate,
    service: ExposureService = Depends(get_exposure_service),
    current_user: User = Depends(get_current_user)
):
    """Update an exposure"""
    exposure = service.update(
        exposure_id=exposure_id,
        company_id=current_user.company_id,
        data=data
    )
    if not exposure:
        raise HTTPException(status_code=404, detail="Exposure not found")
    return exposure


@router.delete("/{exposure_id}")
async def delete_exposure(
    exposure_id: UUID,
    service: ExposureService = Depends(get_exposure_service),
    current_user: User = Depends(get_current_user)
):
    """Cancel an exposure (soft delete)"""
    success = service.delete(exposure_id, current_user.company_id)
    if not success:
        raise HTTPException(status_code=404, detail="Exposure not found")
    return {"status": "cancelled", "id": str(exposure_id)}


# ============================================================================
# Counterparties
# ============================================================================

@router.get("/counterparties/", response_model=List[CounterpartyResponse])
async def list_counterparties(
    counterparty_type: Optional[str] = None,
    is_active: bool = True,
    service: ExposureService = Depends(get_exposure_service),
    current_user: User = Depends(get_current_user)
):
    """List counterparties"""
    return service.list_counterparties(
        company_id=current_user.company_id,
        counterparty_type=counterparty_type,
        is_active=is_active
    )


@router.post("/counterparties/", response_model=CounterpartyResponse)
async def create_counterparty(
    data: CounterpartyCreate,
    service: ExposureService = Depends(get_exposure_service),
    current_user: User = Depends(get_current_user)
):
    """Create a new counterparty"""
    counterparty = service.create_counterparty(
        company_id=current_user.company_id,
        **data.model_dump()
    )
    return counterparty
