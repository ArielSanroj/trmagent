"""
Integracion para obtener precios del petroleo (WTI, Brent)
"""
import httpx
from datetime import datetime, date, timedelta
from typing import List, Optional
from decimal import Decimal
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class OilPricesClient:
    """Cliente para obtener precios del petroleo"""

    # Usamos Alpha Vantage o Yahoo Finance como fuentes
    ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"

    # Simbolos
    SYMBOLS = {
        "wti": "WTI",   # West Texas Intermediate
        "brent": "BRENT"  # Brent Crude
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ALPHA_VANTAGE_KEY
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def get_wti_price(self) -> Optional[dict]:
        """Obtener precio actual de WTI"""
        try:
            if self.api_key:
                # Usar Alpha Vantage si hay API key
                params = {
                    "function": "WTI",
                    "interval": "daily",
                    "apikey": self.api_key
                }
                response = await self.client.get(self.ALPHA_VANTAGE_URL, params=params)
                response.raise_for_status()
                data = response.json()

                if "data" in data and len(data["data"]) > 0:
                    latest = data["data"][0]
                    return {
                        "date": datetime.strptime(latest["date"], "%Y-%m-%d").date(),
                        "value": Decimal(latest["value"]),
                        "indicator": "oil_wti",
                        "source": "alpha_vantage"
                    }

            # Fallback: valor aproximado (en produccion usar API real)
            return {
                "date": date.today(),
                "value": Decimal("75.50"),  # Precio aproximado
                "indicator": "oil_wti",
                "source": "fallback"
            }

        except Exception as e:
            logger.error(f"Error fetching WTI price: {e}")
            return None

    async def get_brent_price(self) -> Optional[dict]:
        """Obtener precio actual de Brent"""
        try:
            if self.api_key:
                params = {
                    "function": "BRENT",
                    "interval": "daily",
                    "apikey": self.api_key
                }
                response = await self.client.get(self.ALPHA_VANTAGE_URL, params=params)
                response.raise_for_status()
                data = response.json()

                if "data" in data and len(data["data"]) > 0:
                    latest = data["data"][0]
                    return {
                        "date": datetime.strptime(latest["date"], "%Y-%m-%d").date(),
                        "value": Decimal(latest["value"]),
                        "indicator": "oil_brent",
                        "source": "alpha_vantage"
                    }

            # Fallback
            return {
                "date": date.today(),
                "value": Decimal("79.50"),  # Precio aproximado
                "indicator": "oil_brent",
                "source": "fallback"
            }

        except Exception as e:
            logger.error(f"Error fetching Brent price: {e}")
            return None

    async def get_oil_history(
        self,
        oil_type: str = "wti",
        days: int = 365
    ) -> List[dict]:
        """Obtener historico de precios del petroleo"""
        try:
            if not self.api_key:
                logger.warning("Alpha Vantage API key not configured")
                return []

            function = "WTI" if oil_type == "wti" else "BRENT"
            params = {
                "function": function,
                "interval": "daily",
                "apikey": self.api_key
            }

            response = await self.client.get(self.ALPHA_VANTAGE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            result = []
            if "data" in data:
                for item in data["data"][:days]:
                    try:
                        result.append({
                            "date": datetime.strptime(item["date"], "%Y-%m-%d").date(),
                            "value": Decimal(item["value"]),
                            "indicator": f"oil_{oil_type}",
                            "source": "alpha_vantage"
                        })
                    except (KeyError, ValueError) as e:
                        continue

            return result

        except Exception as e:
            logger.error(f"Error fetching oil history: {e}")
            return []


# Instancia singleton
oil_client = OilPricesClient()
