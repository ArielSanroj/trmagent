"""
API de Datos de Mercado
TRM, indicadores macroeconomicos
"""
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.data_ingestion import data_ingestion_service
from app.models.schemas import TRMCurrent, TRMHistoryResponse, MarketIndicators
from app.api.v1.auth import get_current_user
from app.models.database_models import User

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get("/trm/current", response_model=TRMCurrent)
async def get_current_trm():
    """Obtener TRM actual"""
    trm = await data_ingestion_service.get_current_trm()

    if not trm:
        raise HTTPException(
            status_code=503,
            detail="Could not fetch current TRM"
        )

    # Obtener TRM de ayer para calcular cambio
    history = await data_ingestion_service.get_trm_history(days=2)
    change_pct = None

    if len(history) >= 2:
        yesterday = float(history[1]["value"])
        today = float(trm["value"])
        change_pct = ((today - yesterday) / yesterday) * 100

    return TRMCurrent(
        date=trm["date"],
        value=trm["value"],
        change_pct=change_pct,
        source=trm["source"]
    )


@router.get("/trm/history", response_model=TRMHistoryResponse)
async def get_trm_history(
    days: int = Query(default=30, ge=1, le=365 * 5),
    from_date: Optional[date] = None,
    to_date: Optional[date] = None
):
    """
    Obtener historico de TRM

    - **days**: Numero de dias (default 30, max 1825)
    - **from_date**: Fecha inicial (opcional)
    - **to_date**: Fecha final (opcional)
    """
    history = await data_ingestion_service.get_trm_history(days=days)

    if not history:
        raise HTTPException(
            status_code=503,
            detail="Could not fetch TRM history"
        )

    # Filtrar por fechas si se especifican
    if from_date:
        history = [h for h in history if h["date"] >= from_date]
    if to_date:
        history = [h for h in history if h["date"] <= to_date]

    return TRMHistoryResponse(
        data=history,
        count=len(history),
        from_date=history[-1]["date"] if history else date.today(),
        to_date=history[0]["date"] if history else date.today()
    )


@router.get("/indicators", response_model=MarketIndicators)
async def get_market_indicators():
    """Obtener indicadores macroeconomicos actuales"""
    # Obtener TRM actual
    trm = await data_ingestion_service.get_current_trm()

    # Obtener indicadores
    indicators = await data_ingestion_service.get_latest_indicators()

    return MarketIndicators(
        trm_current=trm["value"] if trm else None,
        oil_wti=indicators.get("oil_wti", {}).get("value") if indicators.get("oil_wti") else None,
        oil_brent=indicators.get("oil_brent", {}).get("value") if indicators.get("oil_brent") else None,
        fed_rate=indicators.get("fed_rate", {}).get("value") if indicators.get("fed_rate") else None,
        banrep_rate=indicators.get("banrep_rate", {}).get("value") if indicators.get("banrep_rate") else None,
        inflation_col=indicators.get("inflation_col", {}).get("value") if indicators.get("inflation_col") else None,
        inflation_usa=indicators.get("inflation_usa", {}).get("value") if indicators.get("inflation_usa") else None,
        updated_at=__import__('datetime').datetime.utcnow()
    )


@router.post("/trm/refresh")
async def refresh_trm_data(
    days: int = Query(default=30, ge=1, le=365 * 5),
    current_user: User = Depends(get_current_user)
):
    """
    Refrescar datos de TRM desde fuentes externas
    Requiere autenticacion
    """
    inserted = await data_ingestion_service.fetch_and_store_trm(days=days)
    indicators = await data_ingestion_service.fetch_and_store_indicators()

    return {
        "trm_records_inserted": inserted,
        "indicators_updated": indicators,
        "timestamp": __import__('datetime').datetime.utcnow().isoformat()
    }
