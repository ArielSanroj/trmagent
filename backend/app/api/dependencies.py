"""
FastAPI Dependencies para Inyeccion de Dependencias
Resuelve violacion DIP: routers reciben dependencias inyectadas
"""
from typing import Generator
from fastapi import Depends

from app.core.container import get_container, Container
from app.application.interfaces.ml_model import IMLModel
from app.infrastructure.persistence.unit_of_work import UnitOfWork
from app.infrastructure.ml.model_registry import MLModelRegistry


def get_ml_registry(
    container: Container = Depends(get_container)
) -> MLModelRegistry:
    """
    Dependency: Obtener registry de modelos ML

    Uso:
        @router.get("/models")
        def list_models(registry: MLModelRegistry = Depends(get_ml_registry)):
            return registry.available_models()
    """
    return container.ml_registry


def get_ml_model(
    model_type: str = "ensemble",
    container: Container = Depends(get_container)
) -> IMLModel:
    """
    Dependency: Obtener modelo ML especifico

    Uso:
        @router.post("/predict")
        def predict(model: IMLModel = Depends(get_ml_model)):
            return model.predict(...)

    Con tipo especifico:
        def get_prophet():
            return get_ml_model(model_type="prophet")

        @router.post("/predict/prophet")
        def predict_prophet(model: IMLModel = Depends(get_prophet)):
            ...
    """
    return container.ml_registry.get_model(model_type)


def get_uow(
    container: Container = Depends(get_container)
) -> Generator[UnitOfWork, None, None]:
    """
    Dependency: Obtener Unit of Work como context manager

    Uso:
        @router.post("/signals")
        def create_signal(uow: UnitOfWork = Depends(get_uow)):
            with uow:
                signal = uow.signals.save(new_signal)
                uow.commit()
                return signal

    Nota: Tambien se puede usar directamente sin 'with':
        uow.predictions.get_latest()
    pero se recomienda usar context manager para transacciones
    """
    uow = container.get_unit_of_work()
    try:
        yield uow
    finally:
        # Cleanup si no se uso como context manager
        if uow._session and uow._session.is_active:
            uow._session.close()


def get_uow_factory(
    container: Container = Depends(get_container)
):
    """
    Dependency: Obtener factory de UoW

    Util cuando un servicio necesita crear multiples
    transacciones durante su ejecucion

    Uso:
        @router.post("/batch")
        def batch_process(uow_factory = Depends(get_uow_factory)):
            for item in items:
                with uow_factory() as uow:
                    uow.predictions.save(item)
                    uow.commit()
    """
    return container.get_uow_factory()


# Factories para modelos especificos
def get_prophet_model(container: Container = Depends(get_container)) -> IMLModel:
    """Obtener modelo Prophet"""
    return container.ml_registry.get_model("prophet")


def get_lstm_model(container: Container = Depends(get_container)) -> IMLModel:
    """Obtener modelo LSTM"""
    return container.ml_registry.get_model("lstm")


def get_ensemble_model(container: Container = Depends(get_container)) -> IMLModel:
    """Obtener modelo Ensemble"""
    return container.ml_registry.get_model("ensemble")
