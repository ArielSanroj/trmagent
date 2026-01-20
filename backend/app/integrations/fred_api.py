"""
Integracion con FRED API (Federal Reserve Economic Data)
Para datos de tasas de interes USA, inflacion, etc.
"""
import httpx
from datetime import datetime, date, timedelta
from typing import List, Optional
from decimal import Decimal
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class FREDClient:
    """Cliente para FRED API - Federal Reserve Bank of St. Louis"""

    BASE_URL = "https://api.stlouisfed.org/fred"

    # Series IDs importantes
    SERIES = {
        "fed_rate": "FEDFUNDS",          # Federal Funds Rate
        "inflation_usa": "CPIAUCSL",      # Consumer Price Index
        "treasury_10y": "DGS10",          # 10-Year Treasury Rate
        "unemployment": "UNRATE",          # Unemployment Rate
        "gdp_usa": "GDP",                  # GDP
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.FRED_API_KEY
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def get_series(
        self,
        series_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100
    ) -> List[dict]:
        """
        Obtener datos de una serie FRED

        Args:
            series_id: ID de la serie (ej: FEDFUNDS)
            start_date: Fecha inicial
            end_date: Fecha final
            limit: Numero maximo de observaciones

        Returns:
            Lista de observaciones
        """
        if not self.api_key:
            logger.warning("FRED API key not configured")
            return []

        try:
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit
            }

            if start_date:
                params["observation_start"] = start_date.isoformat()
            if end_date:
                params["observation_end"] = end_date.isoformat()

            response = await self.client.get(
                f"{self.BASE_URL}/series/observations",
                params=params
            )
            response.raise_for_status()

            data = response.json()
            observations = data.get("observations", [])

            result = []
            for obs in observations:
                try:
                    if obs["value"] != ".":  # FRED usa "." para datos faltantes
                        result.append({
                            "date": datetime.strptime(obs["date"], "%Y-%m-%d").date(),
                            "value": Decimal(obs["value"]),
                            "series_id": series_id,
                            "source": "fred"
                        })
                except (KeyError, ValueError) as e:
                    logger.warning(f"Error parsing FRED observation: {e}")
                    continue

            return result

        except httpx.HTTPError as e:
            logger.error(f"Error fetching FRED series {series_id}: {e}")
            return []

    async def get_fed_rate(self) -> Optional[dict]:
        """Obtener Federal Funds Rate actual"""
        data = await self.get_series(self.SERIES["fed_rate"], limit=1)
        if data:
            return {
                "date": data[0]["date"],
                "value": data[0]["value"],
                "indicator": "fed_rate",
                "source": "fred"
            }
        return None

    async def get_inflation_usa(self) -> Optional[dict]:
        """Obtener inflacion USA (CPI)"""
        data = await self.get_series(self.SERIES["inflation_usa"], limit=1)
        if data:
            return {
                "date": data[0]["date"],
                "value": data[0]["value"],
                "indicator": "inflation_usa",
                "source": "fred"
            }
        return None

    async def get_fed_rate_history(self, days: int = 365) -> List[dict]:
        """Obtener historico de Federal Funds Rate"""
        start_date = date.today() - timedelta(days=days)
        return await self.get_series(
            self.SERIES["fed_rate"],
            start_date=start_date,
            limit=days
        )


# Instancia singleton
fred_client = FREDClient()
