"""
Adapter para LSTMModel que implementa IMLModel
LSTM ya tiene la firma correcta, este adapter solo garantiza compatibilidad
"""
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Check if TensorFlow/LSTM is available
try:
    import tensorflow as tf
    from app.ml.lstm_model import LSTMModel
    TF_AVAILABLE = True
except (ImportError, NameError):
    TF_AVAILABLE = False
    LSTMModel = None
    logger.warning("TensorFlow not available - LSTMModelAdapter disabled")


class LSTMModelAdapter:
    """
    Adapter para LSTM

    LSTM ya tiene la firma correcta:
    predict(trm_history, days_ahead, indicators)

    Este adapter garantiza que cumple IMLModel
    """

    def __init__(self):
        if not TF_AVAILABLE:
            raise ImportError(
                "TensorFlow is required for LSTMModelAdapter. "
                "Install with: pip install tensorflow"
            )
        self._model = LSTMModel()

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
        """Entrenar LSTM - delegacion directa"""
        return self._model.train(trm_history, indicators, **kwargs)

    def predict(
        self,
        trm_history: List[dict],
        days_ahead: int = 30,
        indicators: Optional[dict] = None
    ) -> List[dict]:
        """
        Predict - delegacion directa

        LSTM necesita trm_history para crear secuencias,
        asi que la firma ya es correcta
        """
        return self._model.predict(trm_history, days_ahead, indicators)

    def save_model(self, path: str) -> bool:
        """Guardar modelo entrenado"""
        return self._model.save_model(path)

    def load_model(self, path: str) -> bool:
        """Cargar modelo guardado"""
        return self._model.load_model(path)
