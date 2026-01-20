"""
Interface unificada para modelos ML
Resuelve violacion LSP: todos los modelos tienen la misma firma
"""
from typing import Protocol, List, Optional
from datetime import datetime


class IMLModel(Protocol):
    """Interface unificada para todos los modelos ML"""

    @property
    def is_fitted(self) -> bool:
        """Indica si el modelo esta entrenado"""
        ...

    @property
    def model_version(self) -> str:
        """Version del modelo"""
        ...

    @property
    def last_trained(self) -> Optional[datetime]:
        """Fecha de ultimo entrenamiento"""
        ...

    def train(
        self,
        trm_history: List[dict],
        indicators: Optional[dict] = None,
        **kwargs
    ) -> bool:
        """
        Entrenar el modelo

        Args:
            trm_history: Lista de {date, value}
            indicators: Indicadores macroeconomicos
            **kwargs: Parametros adicionales

        Returns:
            True si entrenamiento exitoso
        """
        ...

    def predict(
        self,
        trm_history: List[dict],
        days_ahead: int = 30,
        indicators: Optional[dict] = None
    ) -> List[dict]:
        """
        Generar predicciones - FIRMA UNIFORME para todos los modelos

        Args:
            trm_history: Historico de TRM (requerido para LSTM, opcional para Prophet)
            days_ahead: Dias a predecir
            indicators: Indicadores para el futuro

        Returns:
            Lista de predicciones con estructura:
            {
                "target_date": date,
                "predicted_value": Decimal,
                "lower_bound": Decimal,
                "upper_bound": Decimal,
                "confidence": Decimal,
                "model_type": str,
                "model_version": str
            }
        """
        ...

    def save_model(self, path: str) -> bool:
        """Guardar modelo entrenado"""
        ...

    def load_model(self, path: str) -> bool:
        """Cargar modelo guardado"""
        ...
