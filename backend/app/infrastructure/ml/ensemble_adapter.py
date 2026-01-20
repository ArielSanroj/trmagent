"""
Adapter para EnsembleModel que implementa IMLModel
"""
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Check if dependencies are available
try:
    from app.ml.ensemble_model import EnsembleModel
    ENSEMBLE_AVAILABLE = True
except (ImportError, NameError) as e:
    ENSEMBLE_AVAILABLE = False
    EnsembleModel = None
    logger.warning(f"EnsembleModel not available: {e}")


class EnsembleModelAdapter:
    """
    Adapter para Ensemble

    Ensemble ya tiene la firma correcta en predict,
    pero save_model/load_model tienen nombres diferentes
    """

    def __init__(self):
        if not ENSEMBLE_AVAILABLE:
            raise ImportError(
                "EnsembleModel requires Prophet and/or TensorFlow. "
                "Install dependencies: pip install prophet tensorflow"
            )
        self._model = EnsembleModel()

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
        """Entrenar Ensemble - delegacion directa"""
        return self._model.train(trm_history, indicators, **kwargs)

    def predict(
        self,
        trm_history: List[dict],
        days_ahead: int = 30,
        indicators: Optional[dict] = None
    ) -> List[dict]:
        """Predict - delegacion directa"""
        return self._model.predict(trm_history, days_ahead, indicators)

    def save_model(self, path: str) -> bool:
        """
        Guardar modelos del ensemble

        Nota: Ensemble usa save_models() en plural,
        este adapter normaliza a save_model()
        """
        return self._model.save_models(path)

    def load_model(self, path: str) -> bool:
        """
        Cargar modelos del ensemble

        Nota: Ensemble usa load_models() en plural,
        este adapter normaliza a load_model()
        """
        return self._model.load_models(path)
