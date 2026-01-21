"""
Adapter para ProphetModel que implementa IMLModel
Provides a uniform interface for Prophet model usage
"""
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Check if Prophet is available
try:
    from app.ml.prophet_model import ProphetModel
    PROPHET_AVAILABLE = True
except (ImportError, NameError) as e:
    PROPHET_AVAILABLE = False
    ProphetModel = None
    logger.warning(f"ProphetModel not available: {e}")


class ProphetModelAdapter:
    """
    Adapter para que Prophet cumpla IMLModel

    Delegates to ProphetModel with the uniform predict(trm_history, days_ahead, indicators) interface
    """

    def __init__(self):
        if not PROPHET_AVAILABLE:
            raise ImportError(
                "Prophet is required for ProphetModelAdapter. "
                "Install with: pip install prophet"
            )
        self._model = ProphetModel()

    @property
    def is_fitted(self) -> bool:
        return self._model.is_fitted

    @property
    def model_version(self) -> str:
        return self._model.model_version

    @property
    def last_trained(self) -> Optional[datetime]:
        return self._model.last_trained

    def train(
        self,
        trm_history: List[dict],
        indicators: Optional[dict] = None,
        **kwargs
    ) -> bool:
        """Entrenar Prophet - delegacion directa"""
        return self._model.train(trm_history, indicators, **kwargs)

    def predict(
        self,
        trm_history: List[dict],
        days_ahead: int = 30,
        indicators: Optional[dict] = None
    ) -> List[dict]:
        """
        Predict con firma uniforme

        Prophet no necesita trm_history en predict porque ya tiene
        los datos del entrenamiento, pero lo aceptamos para uniformidad
        con LSTM y cumplir IMLModel
        """
        return self._model.predict(trm_history, days_ahead, indicators)

    def save_model(self, path: str) -> bool:
        """Guardar modelo entrenado"""
        return self._model.save_model(path)

    def load_model(self, path: str) -> bool:
        """Cargar modelo guardado"""
        return self._model.load_model(path)
