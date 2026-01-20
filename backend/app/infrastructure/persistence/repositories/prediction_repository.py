"""
Implementacion de IPredictionRepository
Resuelve violacion SRP: separa persistencia de logica de negocio
"""
from typing import List, Optional
from uuid import UUID
from datetime import date

from sqlalchemy.orm import Session

from app.models.database_models import Prediction


class PredictionRepository:
    """
    Repository para predicciones

    Encapsula toda la logica de acceso a datos para predicciones,
    siguiendo el principio SRP.
    """

    def __init__(self, session: Session):
        self._session = session

    def get_by_date_range(
        self,
        start: date,
        end: date,
        company_id: Optional[UUID] = None
    ) -> List[Prediction]:
        """
        Obtener predicciones en un rango de fechas

        Args:
            start: Fecha inicio
            end: Fecha fin
            company_id: Filtrar por empresa (opcional)

        Returns:
            Lista de predicciones ordenadas por fecha
        """
        query = self._session.query(Prediction).filter(
            Prediction.target_date >= start,
            Prediction.target_date <= end
        )

        if company_id:
            query = query.filter(Prediction.company_id == company_id)

        return query.order_by(Prediction.target_date.asc()).all()

    def get_latest(self, company_id: Optional[UUID] = None) -> Optional[Prediction]:
        """
        Obtener prediccion mas reciente (futuro)

        Args:
            company_id: Filtrar por empresa (opcional)

        Returns:
            Prediccion mas proxima o None
        """
        query = self._session.query(Prediction).filter(
            Prediction.target_date >= date.today()
        )

        if company_id:
            query = query.filter(Prediction.company_id == company_id)

        return query.order_by(Prediction.target_date.asc()).first()

    def get_by_id(self, prediction_id: UUID) -> Optional[Prediction]:
        """Obtener prediccion por ID"""
        return self._session.query(Prediction).filter(
            Prediction.id == prediction_id
        ).first()

    def save(self, prediction_data: dict) -> Prediction:
        """
        Guardar nueva prediccion

        Args:
            prediction_data: Diccionario con datos de prediccion

        Returns:
            Prediccion guardada con ID asignado
        """
        prediction = Prediction(**prediction_data)
        self._session.add(prediction)
        self._session.flush()  # Obtener ID sin commit
        return prediction

    def save_many(self, predictions: List[dict]) -> List[Prediction]:
        """
        Guardar multiples predicciones

        Args:
            predictions: Lista de diccionarios con datos

        Returns:
            Lista de predicciones guardadas
        """
        saved = []
        for pred_data in predictions:
            prediction = Prediction(**pred_data)
            self._session.add(prediction)
            saved.append(prediction)

        self._session.flush()
        return saved

    def get_history(self, limit: int = 50) -> List[Prediction]:
        """Obtener historial de predicciones"""
        return self._session.query(Prediction).order_by(
            Prediction.target_date.desc()
        ).limit(limit).all()
