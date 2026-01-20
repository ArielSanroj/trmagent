"""
Servicio de ingestion de datos - Centraliza todas las fuentes
"""
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict
from decimal import Decimal
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.integrations.datos_gov import datos_gov_client
from app.integrations.banrep import banrep_client
from app.integrations.fred_api import fred_client
from app.integrations.oil_prices import oil_client
from app.models.database_models import TRMHistory, MacroIndicator
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


class DataIngestionService:
    """Servicio centralizado de ingestion de datos"""

    async def fetch_and_store_trm(self, days: int = 30) -> int:
        """
        Obtener datos de TRM y almacenar en BD

        Args:
            days: Numero de dias a obtener

        Returns:
            Numero de registros insertados
        """
        logger.info(f"Fetching TRM data for last {days} days")

        try:
            # Obtener datos de datos.gov.co
            trm_data = await datos_gov_client.get_trm_history(days=days)

            if not trm_data:
                logger.warning("No TRM data received from API")
                return 0

            # Almacenar en BD
            db = SessionLocal()
            inserted = 0

            try:
                for item in trm_data:
                    # Verificar si ya existe
                    existing = db.query(TRMHistory).filter(
                        TRMHistory.date == item["date"]
                    ).first()

                    if not existing:
                        trm_record = TRMHistory(
                            date=item["date"],
                            value=item["value"],
                            source=item["source"]
                        )
                        db.add(trm_record)
                        inserted += 1

                db.commit()
                logger.info(f"Inserted {inserted} new TRM records")

            finally:
                db.close()

            return inserted

        except Exception as e:
            logger.error(f"Error in TRM data ingestion: {e}")
            return 0

    async def fetch_and_store_indicators(self) -> Dict[str, bool]:
        """
        Obtener y almacenar indicadores macroeconomicos

        Returns:
            Diccionario con estado de cada indicador
        """
        logger.info("Fetching macro indicators")
        results = {}
        db = SessionLocal()

        try:
            # Federal Funds Rate
            fed_rate = await fred_client.get_fed_rate()
            if fed_rate:
                results["fed_rate"] = await self._store_indicator(db, fed_rate)

            # Inflacion USA
            inflation_usa = await fred_client.get_inflation_usa()
            if inflation_usa:
                results["inflation_usa"] = await self._store_indicator(db, inflation_usa)

            # Tasa BanRep
            banrep_rate = await banrep_client.get_policy_rate()
            if banrep_rate:
                results["banrep_rate"] = await self._store_indicator(db, banrep_rate)

            # Inflacion Colombia
            inflation_col = await banrep_client.get_inflation_rate()
            if inflation_col:
                results["inflation_col"] = await self._store_indicator(db, inflation_col)

            # Petroleo WTI
            oil_wti = await oil_client.get_wti_price()
            if oil_wti:
                results["oil_wti"] = await self._store_indicator(db, oil_wti)

            # Petroleo Brent
            oil_brent = await oil_client.get_brent_price()
            if oil_brent:
                results["oil_brent"] = await self._store_indicator(db, oil_brent)

            db.commit()

        except Exception as e:
            logger.error(f"Error fetching indicators: {e}")
            db.rollback()

        finally:
            db.close()

        return results

    async def _store_indicator(self, db: Session, data: dict) -> bool:
        """Almacenar un indicador en BD"""
        try:
            # Verificar si ya existe para esa fecha
            existing = db.query(MacroIndicator).filter(
                and_(
                    MacroIndicator.date == data["date"],
                    MacroIndicator.indicator_type == data["indicator"]
                )
            ).first()

            if existing:
                # Actualizar valor
                existing.value = data["value"]
            else:
                # Insertar nuevo
                indicator = MacroIndicator(
                    date=data["date"],
                    indicator_type=data["indicator"],
                    value=data["value"],
                    source=data["source"]
                )
                db.add(indicator)

            return True

        except Exception as e:
            logger.error(f"Error storing indicator {data.get('indicator')}: {e}")
            return False

    async def get_current_trm(self) -> Optional[dict]:
        """Obtener TRM actual desde BD o API"""
        db = SessionLocal()
        try:
            # Intentar desde BD primero
            latest = db.query(TRMHistory).order_by(
                TRMHistory.date.desc()
            ).first()

            if latest and latest.date >= date.today() - timedelta(days=1):
                return {
                    "date": latest.date,
                    "value": latest.value,
                    "source": latest.source
                }

            # Si no hay datos recientes, obtener de API
            trm = await datos_gov_client.get_current_trm()
            return trm

        finally:
            db.close()

    async def get_trm_history(
        self,
        days: int = 365,
        from_db: bool = True
    ) -> List[dict]:
        """
        Obtener historico de TRM

        Args:
            days: Numero de dias
            from_db: Si True, obtener de BD; si False, de API

        Returns:
            Lista de datos TRM
        """
        if from_db:
            db = SessionLocal()
            try:
                start_date = date.today() - timedelta(days=days)
                records = db.query(TRMHistory).filter(
                    TRMHistory.date >= start_date
                ).order_by(TRMHistory.date.desc()).all()

                return [
                    {"date": r.date, "value": r.value, "source": r.source}
                    for r in records
                ]
            finally:
                db.close()
        else:
            return await datos_gov_client.get_trm_history(days=days)

    async def get_latest_indicators(self) -> Dict[str, Optional[dict]]:
        """Obtener ultimos valores de todos los indicadores"""
        db = SessionLocal()
        indicators = {}

        try:
            indicator_types = [
                "fed_rate", "inflation_usa", "banrep_rate",
                "inflation_col", "oil_wti", "oil_brent"
            ]

            for ind_type in indicator_types:
                latest = db.query(MacroIndicator).filter(
                    MacroIndicator.indicator_type == ind_type
                ).order_by(MacroIndicator.date.desc()).first()

                if latest:
                    indicators[ind_type] = {
                        "date": latest.date,
                        "value": latest.value,
                        "source": latest.source
                    }
                else:
                    indicators[ind_type] = None

        finally:
            db.close()

        return indicators

    async def get_full_market_context(self) -> dict:
        """
        Obtener contexto completo del mercado para ML

        Returns:
            Diccionario con todos los datos de mercado
        """
        trm = await self.get_current_trm()
        trm_history = await self.get_trm_history(days=90)
        indicators = await self.get_latest_indicators()

        return {
            "trm_current": trm,
            "trm_history": trm_history,
            "indicators": indicators,
            "timestamp": datetime.utcnow()
        }


# Instancia singleton
data_ingestion_service = DataIngestionService()
