"""
Implementacion de ITRMHistoryRepository
"""
from typing import List, Optional
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.database_models import TRMHistory


class TRMHistoryRepository:
    """
    Repository para historico de TRM

    Encapsula acceso a datos para TRM historico,
    siguiendo principio SRP.
    """

    def __init__(self, session: Session):
        self._session = session

    def get_history(self, days: int = 365) -> List[dict]:
        """
        Obtener historico de TRM

        Args:
            days: Numero de dias hacia atras

        Returns:
            Lista de {date, value, source}
        """
        start_date = date.today() - timedelta(days=days)

        records = self._session.query(TRMHistory).filter(
            TRMHistory.date >= start_date
        ).order_by(TRMHistory.date.desc()).all()

        return [
            {
                "date": r.date,
                "value": float(r.value),
                "source": r.source
            }
            for r in records
        ]

    def get_current(self) -> Optional[dict]:
        """
        Obtener TRM mas reciente

        Returns:
            {date, value, source} o None
        """
        latest = self._session.query(TRMHistory).order_by(
            TRMHistory.date.desc()
        ).first()

        if latest:
            return {
                "date": latest.date,
                "value": float(latest.value),
                "source": latest.source
            }
        return None

    def get_by_date(self, target_date: date) -> Optional[dict]:
        """Obtener TRM de una fecha especifica"""
        record = self._session.query(TRMHistory).filter(
            TRMHistory.date == target_date
        ).first()

        if record:
            return {
                "date": record.date,
                "value": float(record.value),
                "source": record.source
            }
        return None

    def save(self, record: dict) -> Optional[TRMHistory]:
        """
        Guardar registro de TRM

        Args:
            record: {date, value, source}

        Returns:
            Registro guardado o None si ya existe
        """
        existing = self._session.query(TRMHistory).filter(
            TRMHistory.date == record["date"]
        ).first()

        if existing:
            return None  # Ya existe

        trm_record = TRMHistory(
            date=record["date"],
            value=record["value"],
            source=record.get("source", "datos.gov.co")
        )
        self._session.add(trm_record)
        self._session.flush()
        return trm_record

    def save_many(self, records: List[dict]) -> int:
        """
        Guardar multiples registros (ignora duplicados)

        Args:
            records: Lista de {date, value, source}

        Returns:
            Numero de registros nuevos insertados
        """
        count = 0
        for record in records:
            existing = self._session.query(TRMHistory).filter(
                TRMHistory.date == record["date"]
            ).first()

            if not existing:
                trm_record = TRMHistory(
                    date=record["date"],
                    value=record["value"],
                    source=record.get("source", "datos.gov.co")
                )
                self._session.add(trm_record)
                count += 1

        self._session.flush()
        return count

    def get_date_range(self, start: date, end: date) -> List[dict]:
        """Obtener TRM en rango de fechas"""
        records = self._session.query(TRMHistory).filter(
            TRMHistory.date >= start,
            TRMHistory.date <= end
        ).order_by(TRMHistory.date.asc()).all()

        return [
            {
                "date": r.date,
                "value": float(r.value),
                "source": r.source
            }
            for r in records
        ]
