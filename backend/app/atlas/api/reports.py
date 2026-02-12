"""
ATLAS - Reports API Endpoints
"""
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.database_models import User
from app.atlas.models.schemas import (
    CoverageReport,
    MaturityLadder,
    CostAnalysis,
    ReportExportRequest,
)
from app.atlas.services.reporting_service import ReportingService
from app.atlas.services.settlement_service import SettlementService

router = APIRouter(prefix="/reports", tags=["ATLAS - Reports"])


def get_reporting_service(db: Session = Depends(get_db)) -> ReportingService:
    return ReportingService(db)


def get_settlement_service(db: Session = Depends(get_db)) -> SettlementService:
    return SettlementService(db)


# ============================================================================
# Coverage Report
# ============================================================================

@router.get("/coverage", response_model=CoverageReport)
async def get_coverage_report(
    as_of_date: Optional[date] = None,
    currency: str = Query(default="USD"),
    service: ReportingService = Depends(get_reporting_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get coverage report showing hedge status across all exposures.

    Includes breakdowns by:
    - Exposure type (payables vs receivables)
    - Counterparty
    - Maturity horizon
    """
    return service.get_coverage_report(
        company_id=current_user.company_id,
        as_of_date=as_of_date,
        currency=currency
    )


# ============================================================================
# Maturity Ladder
# ============================================================================

@router.get("/maturity-ladder", response_model=MaturityLadder)
async def get_maturity_ladder(
    currency: str = Query(default="USD"),
    bucket_days: int = Query(default=7, ge=1, le=30),
    service: ReportingService = Depends(get_reporting_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get maturity ladder showing exposures grouped by time buckets.

    Useful for planning cash flow and hedging activities.
    """
    return service.get_maturity_ladder(
        company_id=current_user.company_id,
        currency=currency,
        bucket_days=bucket_days
    )


# ============================================================================
# Cost Analysis
# ============================================================================

@router.get("/cost-analysis", response_model=CostAnalysis)
async def get_cost_analysis(
    start_date: date,
    end_date: date,
    currency: str = Query(default="USD"),
    service: ReportingService = Depends(get_reporting_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get cost analysis of executed hedges for a period.

    Includes:
    - Average rates achieved
    - Performance vs benchmark
    - Breakdown by counterparty bank
    """
    if start_date >= end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before end_date"
        )

    return service.get_cost_analysis(
        company_id=current_user.company_id,
        start_date=start_date,
        end_date=end_date,
        currency=currency
    )


# ============================================================================
# Settlement Calendar
# ============================================================================

@router.get("/settlement-calendar")
async def get_settlement_calendar(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    days: int = Query(default=30, ge=1, le=365),
    service: SettlementService = Depends(get_settlement_service),
    current_user: User = Depends(get_current_user)
):
    """Get calendar of upcoming settlements"""
    calendar = service.get_settlement_calendar(
        company_id=current_user.company_id,
        start_date=start_date,
        end_date=end_date,
        days=days
    )
    # Convert date keys to strings for JSON
    return {
        dt.isoformat(): data
        for dt, data in calendar.items()
    }


@router.get("/settlement-summary")
async def get_settlement_summary(
    service: SettlementService = Depends(get_settlement_service),
    current_user: User = Depends(get_current_user)
):
    """Get summary of settlement status"""
    return service.get_summary(current_user.company_id)


# ============================================================================
# Export
# ============================================================================

@router.post("/export")
async def export_report(
    data: ReportExportRequest,
    service: ReportingService = Depends(get_reporting_service),
    current_user: User = Depends(get_current_user)
):
    """
    Export a report to file (XLSX or CSV).

    Returns a downloadable file.
    """
    try:
        file_bytes = service.export_report(
            company_id=current_user.company_id,
            report_type=data.report_type,
            format=data.format,
            start_date=data.start_date,
            end_date=data.end_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Set content type and filename
    if data.format == "xlsx":
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"atlas_{data.report_type}_{date.today().isoformat()}.xlsx"
    else:
        media_type = "text/csv"
        filename = f"atlas_{data.report_type}_{date.today().isoformat()}.csv"

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


# ============================================================================
# Dashboard Summary (combines multiple reports)
# ============================================================================

@router.get("/dashboard")
async def get_dashboard_summary(
    currency: str = Query(default="USD"),
    reporting_service: ReportingService = Depends(get_reporting_service),
    settlement_service: SettlementService = Depends(get_settlement_service),
    current_user: User = Depends(get_current_user)
):
    """
    Get combined dashboard data for ATLAS overview.

    Includes key metrics from multiple reports in one call.
    """
    coverage = reporting_service.get_coverage_report(
        company_id=current_user.company_id,
        currency=currency
    )

    settlements = settlement_service.get_summary(current_user.company_id)

    return {
        "coverage": {
            "total_exposure": float(coverage.total_payables + coverage.total_receivables),
            "net_exposure": float(coverage.net_exposure),
            "overall_coverage_pct": float(coverage.overall_coverage_pct),
            "payables_coverage_pct": float(coverage.payables_coverage_pct),
            "receivables_coverage_pct": float(coverage.receivables_coverage_pct),
        },
        "settlements": settlements,
        "currency": currency,
        "as_of": date.today().isoformat(),
    }
