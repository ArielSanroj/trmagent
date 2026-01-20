"""
Unit of Work Pattern
Maneja transacciones y provee acceso a repositories
"""
from typing import Callable

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.infrastructure.persistence.repositories.prediction_repository import PredictionRepository
from app.infrastructure.persistence.repositories.signal_repository import SignalRepository
from app.infrastructure.persistence.repositories.trm_history_repository import TRMHistoryRepository
from app.infrastructure.persistence.repositories.company_config_repository import CompanyConfigRepository


class UnitOfWork:
    """
    Unit of Work - Maneja transacciones y repositories

    Uso como context manager:
        with UnitOfWork() as uow:
            config = uow.company_config.get_or_default(company_id)
            signal = uow.signals.save(new_signal)
            uow.commit()

    Beneficios:
    - Transacciones atomicas
    - Acceso centralizado a repositories
    - Rollback automatico en errores
    - Resuelve violacion DIP: no hay imports directos de SessionLocal
    """

    def __init__(self, session_factory: Callable[[], Session] = SessionLocal):
        self._session_factory = session_factory
        self._session: Session = None

        # Repositories - se inicializan en __enter__
        self.predictions: PredictionRepository = None
        self.signals: SignalRepository = None
        self.trm_history: TRMHistoryRepository = None
        self.company_config: CompanyConfigRepository = None

    def __enter__(self) -> "UnitOfWork":
        """Iniciar transaccion y crear repositories"""
        self._session = self._session_factory()

        # Inicializar repositories con la sesion
        self.predictions = PredictionRepository(self._session)
        self.signals = SignalRepository(self._session)
        self.trm_history = TRMHistoryRepository(self._session)
        self.company_config = CompanyConfigRepository(self._session)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cerrar sesion (rollback automatico si hay error)"""
        if exc_type:
            self.rollback()
        self._session.close()

    def commit(self):
        """Confirmar transaccion"""
        self._session.commit()

    def rollback(self):
        """Revertir transaccion"""
        self._session.rollback()

    @property
    def session(self) -> Session:
        """Acceso directo a la sesion (para casos especiales)"""
        return self._session


class AsyncUnitOfWork:
    """
    Unit of Work asincrono para endpoints async

    Uso:
        async with AsyncUnitOfWork() as uow:
            ...
    """

    def __init__(self, session_factory=None):
        # TODO: Implementar version asincrona con AsyncSession
        # Por ahora, el UoW sincrono es suficiente para la mayoria de casos
        raise NotImplementedError(
            "AsyncUnitOfWork no implementado aun. "
            "Usar UnitOfWork sincrono en un thread pool."
        )
