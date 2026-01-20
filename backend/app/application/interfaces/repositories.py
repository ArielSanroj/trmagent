"""
Interfaces para repositorios de datos
Resuelve violacion DIP: servicios dependen de abstracciones, no implementaciones
"""
from typing import Protocol, List, Optional, TypeVar, Generic
from uuid import UUID
from datetime import date

T = TypeVar('T')


class IRepository(Protocol[T]):
    """Interface base para repositorios genericos"""

    def get_by_id(self, id: UUID) -> Optional[T]:
        ...

    def get_all(self, limit: int = 100) -> List[T]:
        ...

    def add(self, entity: T) -> T:
        ...

    def update(self, entity: T) -> T:
        ...

    def delete(self, id: UUID) -> bool:
        ...


class IPredictionRepository(Protocol):
    """Interface para repositorio de predicciones"""

    def get_by_date_range(
        self,
        start: date,
        end: date,
        company_id: Optional[UUID] = None
    ) -> List:
        """Obtener predicciones en rango de fechas"""
        ...

    def get_latest(self, company_id: Optional[UUID] = None):
        """Obtener prediccion mas reciente"""
        ...

    def save(self, prediction: dict) -> UUID:
        """Guardar prediccion"""
        ...


class ISignalRepository(Protocol):
    """Interface para repositorio de senales de trading"""

    def get_pending(self, company_id: UUID) -> List:
        """Obtener senales pendientes de una empresa"""
        ...

    def get_current(self, company_id: Optional[UUID] = None):
        """Obtener senal mas reciente"""
        ...

    def save(self, signal) -> UUID:
        """Guardar senal"""
        ...


class ITRMHistoryRepository(Protocol):
    """Interface para repositorio de historico TRM"""

    def get_history(self, days: int = 365) -> List[dict]:
        """Obtener historico de TRM"""
        ...

    def get_current(self) -> Optional[dict]:
        """Obtener TRM mas reciente"""
        ...

    def save_many(self, records: List[dict]) -> int:
        """Guardar multiples registros"""
        ...


class ICompanyConfigRepository(Protocol):
    """Interface para configuracion de empresas"""

    def get_by_company_id(self, company_id: UUID) -> Optional[dict]:
        """Obtener configuracion de una empresa"""
        ...

    def get_default(self) -> dict:
        """Obtener configuracion por defecto"""
        ...
