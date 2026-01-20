"""
Integracion con datos.gov.co para obtener TRM oficial
"""
import httpx
from datetime import datetime, date, timedelta
from typing import List, Optional
from decimal import Decimal
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class DatosGovClient:
    """Cliente para API de datos.gov.co - TRM Colombia"""

    BASE_URL = "https://www.datos.gov.co/resource/32sa-8pi3.json"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def get_trm_history(
        self,
        days: int = 365,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[dict]:
        """
        Obtener historico de TRM

        Args:
            days: Numero de dias de historia (default 365)
            start_date: Fecha inicial (opcional)
            end_date: Fecha final (opcional)

        Returns:
            Lista de diccionarios con fecha y valor TRM
        """
        try:
            params = {
                "$limit": days,
                "$order": "vigenciahasta DESC"
            }

            if start_date:
                params["$where"] = f"vigenciahasta >= '{start_date.isoformat()}'"
            if end_date:
                if "$where" in params:
                    params["$where"] += f" AND vigenciahasta <= '{end_date.isoformat()}'"
                else:
                    params["$where"] = f"vigenciahasta <= '{end_date.isoformat()}'"

            response = await self.client.get(self.BASE_URL, params=params)
            response.raise_for_status()

            data = response.json()

            # Transformar datos
            result = []
            for item in data:
                try:
                    result.append({
                        "date": datetime.fromisoformat(
                            item["vigenciahasta"].replace("T00:00:00.000", "")
                        ).date(),
                        "value": Decimal(item["valor"]),
                        "source": "datos.gov.co"
                    })
                except (KeyError, ValueError) as e:
                    logger.warning(f"Error parsing TRM item: {e}")
                    continue

            return result

        except httpx.HTTPError as e:
            logger.error(f"Error fetching TRM from datos.gov.co: {e}")
            return []

    async def get_current_trm(self) -> Optional[dict]:
        """Obtener TRM actual (mas reciente)"""
        history = await self.get_trm_history(days=1)
        return history[0] if history else None

    async def get_trm_range(self, start_date: date, end_date: date) -> List[dict]:
        """Obtener TRM en un rango de fechas especifico"""
        days_diff = (end_date - start_date).days + 1
        return await self.get_trm_history(
            days=days_diff,
            start_date=start_date,
            end_date=end_date
        )


# Instancia singleton
datos_gov_client = DatosGovClient()
