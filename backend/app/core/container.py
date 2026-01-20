"""
Dependency Injection Container
Resuelve violacion DIP: provee dependencias sin imports directos
"""
from functools import lru_cache
from typing import Callable

from app.infrastructure.ml.model_registry import MLModelRegistry
from app.infrastructure.persistence.unit_of_work import UnitOfWork


class Container:
    """
    Dependency Injection Container

    Centraliza la creacion de dependencias y permite:
    - Inyeccion de dependencias en routers via FastAPI Depends
    - Testing con mocks facilmente
    - Configuracion de dependencias en un solo lugar

    Uso:
        container = get_container()
        model = container.ml_registry.get_model("ensemble")

    En routers (via dependencies.py):
        @router.post("/predict")
        async def predict(model: IMLModel = Depends(get_ml_model)):
            return model.predict(...)
    """

    def __init__(self):
        self._ml_registry = MLModelRegistry()

    @property
    def ml_registry(self) -> MLModelRegistry:
        """Obtener registry de modelos ML"""
        return self._ml_registry

    def get_unit_of_work(self) -> UnitOfWork:
        """
        Factory para Unit of Work

        Retorna nueva instancia cada vez (no singleton)
        porque cada request debe tener su propia transaccion
        """
        return UnitOfWork()

    def get_uow_factory(self) -> Callable[[], UnitOfWork]:
        """
        Retorna la factory de UoW

        Util para servicios que necesitan crear
        multiples transacciones
        """
        return self.get_unit_of_work


@lru_cache()
def get_container() -> Container:
    """
    Obtener container singleton

    lru_cache asegura que siempre se retorna la misma instancia
    """
    return Container()


def reset_container():
    """
    Resetear container (para testing)

    Limpia el cache de lru_cache para obtener nueva instancia
    """
    get_container.cache_clear()
