"""
Integracion con set-icap.com para obtener USD/COP
"""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import List, Optional
import logging
import re

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class SetIcapClient:
    """Cliente para datos USD/COP desde set-icap.com"""

    _PRICE_RE = re.compile(r"label:\s*'Precios de cierre'\s*,\s*data:\s*\[([^\]]+)\]")

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def _fetch_chart(
        self,
        target_date: date,
        realtime: bool = True,
        delay: Optional[str] = None
    ) -> Optional[str]:
        endpoint = "graficoMonedaRT/" if realtime else "graficoMoneda/"
        if delay is None:
            delay = settings.SETICAP_DELAY
        payload = {
            "fecha": target_date.isoformat(),
            "moneda": settings.SETICAP_MONEDA_USD_COP,
            "delay": str(delay),
            "market": settings.SETICAP_MARKET_ID,
        }

        response = await self.client.post(f"{settings.SETICAP_BASE_URL}{endpoint}", json=payload)
        response.raise_for_status()

        data = response.json()
        if data.get("status") != "success":
            return None

        result = data.get("result") or []
        if not result:
            return None

        key = "datos_grafico_moneda_mercado_rt" if realtime else "datos_grafico_moneda_mercado"
        return result[0].get(key)

    def _parse_prices(self, chart_text: str) -> List[Decimal]:
        if not chart_text:
            return []

        match = self._PRICE_RE.search(chart_text)
        if not match:
            return []

        values = []
        for raw in match.group(1).split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                values.append(Decimal(raw))
            except InvalidOperation:
                continue

        return values

    async def get_trm_for_date(
        self,
        target_date: date,
        realtime: bool = True,
        delay: Optional[str] = None
    ) -> Optional[dict]:
        try:
            chart = await self._fetch_chart(target_date, realtime=realtime, delay=delay)
        except httpx.HTTPError as e:
            logger.error(f"Error fetching Set-ICAP chart: {e}")
            return None

        prices = self._parse_prices(chart or "")
        if not prices:
            return None

        return {
            "date": target_date,
            "value": prices[-1],
            "source": "set-icap.com",
        }

    async def get_current_trm(self) -> Optional[dict]:
        today = date.today()
        current = await self.get_trm_for_date(today, realtime=True)
        if current:
            return current

        # Fallback a los dias anteriores si no hay datos del dia actual
        for offset in range(1, 4):
            previous = await self.get_trm_for_date(today - timedelta(days=offset), realtime=False)
            if previous:
                return previous

        return None

    async def get_trm_history(
        self,
        days: int = 30,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[dict]:
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=days - 1)

        total_days = (end_date - start_date).days + 1
        results: List[dict] = []

        for i in range(total_days):
            day = end_date - timedelta(days=i)
            realtime = day == end_date
            trm = await self.get_trm_for_date(day, realtime=realtime)
            if trm:
                results.append(trm)

        return results


# Instancia singleton
seticap_client = SetIcapClient()
