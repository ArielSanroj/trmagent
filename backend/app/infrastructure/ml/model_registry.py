"""
Registry Pattern para modelos ML
Resuelve violacion OCP: agregar nuevos modelos sin modificar codigo existente
Similar a BrokerService que ya existe en el proyecto
"""
from typing import Dict, Type, Callable, Optional
import logging

from app.application.interfaces.ml_model import IMLModel

# Lazy imports to handle missing dependencies
ProphetModelAdapter = None
LSTMModelAdapter = None
EnsembleModelAdapter = None

try:
    from app.infrastructure.ml.prophet_adapter import ProphetModelAdapter
except (ImportError, NameError):
    pass

try:
    from app.infrastructure.ml.lstm_adapter import LSTMModelAdapter
except (ImportError, NameError):
    pass

try:
    from app.infrastructure.ml.ensemble_adapter import EnsembleModelAdapter
except (ImportError, NameError):
    pass

logger = logging.getLogger(__name__)


class MLModelRegistry:
    """
    Registry pattern para modelos ML

    Uso:
        registry = MLModelRegistry()
        model = registry.get_model("ensemble")  # Obtiene singleton
        predictions = model.predict(trm_history, 30, indicators)

    Para agregar nuevo modelo (OCP - Open for extension):
        registry.register_factory("xgboost", XGBoostModelAdapter)
    """

    def __init__(self):
        # Instancias singleton por tipo de modelo
        self._instances: Dict[str, IMLModel] = {}

        # Factories para crear nuevas instancias
        # Only register adapters that are actually usable
        self._factories: Dict[str, Callable[[], IMLModel]] = {}

        # Check each adapter by trying to instantiate it
        if ProphetModelAdapter is not None:
            try:
                test = ProphetModelAdapter()
                self._factories["prophet"] = ProphetModelAdapter
                del test
            except ImportError:
                logger.debug("Prophet adapter not usable")

        if LSTMModelAdapter is not None:
            try:
                test = LSTMModelAdapter()
                self._factories["lstm"] = LSTMModelAdapter
                del test
            except ImportError:
                logger.debug("LSTM adapter not usable")

        if EnsembleModelAdapter is not None:
            try:
                test = EnsembleModelAdapter()
                self._factories["ensemble"] = EnsembleModelAdapter
                del test
            except ImportError:
                logger.debug("Ensemble adapter not usable")

        if not self._factories:
            logger.warning(
                "No ML model adapters available. "
                "Install prophet and/or tensorflow."
            )

    def get_model(self, model_type: str = "ensemble") -> IMLModel:
        """
        Obtener modelo (singleton por tipo)

        Args:
            model_type: Tipo de modelo ('prophet', 'lstm', 'ensemble')

        Returns:
            Instancia del modelo

        Raises:
            ValueError: Si el modelo no existe
        """
        model_type = model_type.lower()

        if model_type not in self._instances:
            if model_type not in self._factories:
                available = ", ".join(self._factories.keys())
                raise ValueError(
                    f"Modelo desconocido: '{model_type}'. "
                    f"Disponibles: {available}"
                )
            logger.debug(f"Creating new instance of model: {model_type}")
            self._instances[model_type] = self._factories[model_type]()

        return self._instances[model_type]

    def register_factory(
        self,
        name: str,
        factory: Callable[[], IMLModel]
    ) -> None:
        """
        Registrar factory para nuevo tipo de modelo

        Args:
            name: Nombre del modelo
            factory: Callable que crea instancias del modelo

        Ejemplo:
            registry.register_factory("xgboost", XGBoostAdapter)
        """
        self._factories[name.lower()] = factory
        logger.info(f"Registered new model factory: {name}")

    def register_instance(self, name: str, model: IMLModel) -> None:
        """
        Registrar modelo custom ya instanciado

        Args:
            name: Nombre del modelo
            model: Instancia del modelo

        Ejemplo:
            custom_model = CustomModelAdapter(params)
            registry.register_instance("custom", custom_model)
        """
        self._instances[name.lower()] = model
        logger.info(f"Registered model instance: {name}")

    def available_models(self) -> list:
        """Listar modelos disponibles"""
        return list(self._factories.keys())

    def is_model_fitted(self, model_type: str = "ensemble") -> bool:
        """Verificar si un modelo esta entrenado"""
        model_type = model_type.lower()
        if model_type in self._instances:
            return self._instances[model_type].is_fitted
        return False

    def clear_instances(self) -> None:
        """Limpiar todas las instancias (para testing)"""
        self._instances.clear()
