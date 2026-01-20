"""
Implementacion de ISignalRepository
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.database_models import TradingSignal, SignalStatus


class SignalRepository:
    """
    Repository para senales de trading

    Encapsula acceso a datos para senales,
    siguiendo principio SRP.
    """

    def __init__(self, session: Session):
        self._session = session

    def get_pending(self, company_id: UUID) -> List[TradingSignal]:
        """
        Obtener senales pendientes de una empresa

        Args:
            company_id: ID de la empresa

        Returns:
            Lista de senales pendientes
        """
        return self._session.query(TradingSignal).filter(
            TradingSignal.company_id == company_id,
            TradingSignal.status == SignalStatus.PENDING
        ).order_by(TradingSignal.created_at.desc()).all()

    def get_current(self, company_id: Optional[UUID] = None) -> Optional[TradingSignal]:
        """
        Obtener senal mas reciente

        Args:
            company_id: Filtrar por empresa (opcional)

        Returns:
            Senal mas reciente o None
        """
        query = self._session.query(TradingSignal)

        if company_id:
            query = query.filter(TradingSignal.company_id == company_id)

        return query.order_by(TradingSignal.created_at.desc()).first()

    def get_by_id(self, signal_id: UUID) -> Optional[TradingSignal]:
        """Obtener senal por ID"""
        return self._session.query(TradingSignal).filter(
            TradingSignal.id == signal_id
        ).first()

    def save(self, signal: TradingSignal) -> TradingSignal:
        """
        Guardar senal

        Args:
            signal: Instancia de TradingSignal

        Returns:
            Senal guardada
        """
        self._session.add(signal)
        self._session.flush()
        return signal

    def update_status(
        self,
        signal_id: UUID,
        new_status: SignalStatus
    ) -> Optional[TradingSignal]:
        """
        Actualizar estado de senal

        Args:
            signal_id: ID de la senal
            new_status: Nuevo estado

        Returns:
            Senal actualizada o None si no existe
        """
        signal = self.get_by_id(signal_id)
        if signal:
            signal.status = new_status
            self._session.flush()
        return signal

    def get_by_status(
        self,
        status: SignalStatus,
        company_id: Optional[UUID] = None,
        limit: int = 50
    ) -> List[TradingSignal]:
        """Obtener senales por estado"""
        query = self._session.query(TradingSignal).filter(
            TradingSignal.status == status
        )

        if company_id:
            query = query.filter(TradingSignal.company_id == company_id)

        return query.order_by(TradingSignal.created_at.desc()).limit(limit).all()

    def get_history(
        self,
        company_id: Optional[UUID] = None,
        limit: int = 50
    ) -> List[TradingSignal]:
        """Obtener historial de senales"""
        query = self._session.query(TradingSignal)

        if company_id:
            query = query.filter(TradingSignal.company_id == company_id)

        return query.order_by(TradingSignal.created_at.desc()).limit(limit).all()
