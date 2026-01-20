"""
Modelo Ensemble que combina Prophet, LSTM y otros modelos
Para predicciones mas robustas
"""
import numpy as np
from datetime import datetime, date
from typing import List, Dict, Optional
from decimal import Decimal
import logging

from app.ml.prophet_model import ProphetModel
from app.ml.lstm_model import LSTMModel

logger = logging.getLogger(__name__)


class EnsembleModel:
    """
    Modelo Ensemble que combina multiples modelos
    Usa weighted average basado en performance historico
    """

    def __init__(self):
        self.prophet = ProphetModel()
        self.lstm = LSTMModel()

        # Pesos por defecto (ajustar basado en backtesting)
        self.weights = {
            "prophet": 0.5,
            "lstm": 0.5
        }

        self.model_version = "ensemble_v1"
        self.is_fitted = False
        self.last_trained = None

    def train(
        self,
        trm_history: List[dict],
        indicators: Optional[dict] = None,
        **kwargs
    ) -> bool:
        """
        Entrenar todos los modelos del ensemble

        Args:
            trm_history: Historico de TRM
            indicators: Indicadores macroeconomicos

        Returns:
            True si al menos un modelo se entreno exitosamente
        """
        results = {}

        # Entrenar Prophet
        try:
            results["prophet"] = self.prophet.train(trm_history, indicators, **kwargs)
        except Exception as e:
            logger.error(f"Error training Prophet: {e}")
            results["prophet"] = False

        # Entrenar LSTM
        try:
            results["lstm"] = self.lstm.train(trm_history, indicators, **kwargs)
        except Exception as e:
            logger.error(f"Error training LSTM: {e}")
            results["lstm"] = False

        self.is_fitted = any(results.values())
        self.last_trained = datetime.utcnow()

        logger.info(f"Ensemble training results: {results}")
        return self.is_fitted

    def predict(
        self,
        trm_history: List[dict],
        days_ahead: int = 30,
        indicators: Optional[dict] = None
    ) -> List[dict]:
        """
        Generar predicciones combinando todos los modelos

        Args:
            trm_history: Historico reciente de TRM
            days_ahead: Dias a predecir
            indicators: Indicadores para el futuro

        Returns:
            Lista de predicciones ensemble
        """
        if not self.is_fitted:
            logger.error("Ensemble not fitted. Call train() first")
            return []

        all_predictions = {}

        # Obtener predicciones de cada modelo
        if self.prophet.is_fitted:
            prophet_preds = self.prophet.predict(days_ahead, indicators)
            if prophet_preds:
                all_predictions["prophet"] = prophet_preds

        if self.lstm.is_fitted:
            lstm_preds = self.lstm.predict(trm_history, days_ahead, indicators)
            if lstm_preds:
                all_predictions["lstm"] = lstm_preds

        if not all_predictions:
            logger.error("No predictions from any model")
            return []

        # Combinar predicciones
        ensemble_preds = self._combine_predictions(all_predictions, days_ahead)
        return ensemble_preds

    def _combine_predictions(
        self,
        all_predictions: Dict[str, List[dict]],
        days_ahead: int
    ) -> List[dict]:
        """
        Combinar predicciones de multiples modelos usando weighted average

        Args:
            all_predictions: Diccionario de predicciones por modelo
            days_ahead: Dias predichos

        Returns:
            Lista de predicciones combinadas
        """
        ensemble_preds = []

        # Normalizar pesos segun modelos disponibles
        available_models = list(all_predictions.keys())
        total_weight = sum(self.weights[m] for m in available_models)
        normalized_weights = {
            m: self.weights[m] / total_weight
            for m in available_models
        }

        for i in range(days_ahead):
            values = []
            lower_bounds = []
            upper_bounds = []
            target_date = None

            for model_name, preds in all_predictions.items():
                if i < len(preds):
                    pred = preds[i]
                    weight = normalized_weights[model_name]

                    values.append(float(pred["predicted_value"]) * weight)
                    lower_bounds.append(float(pred["lower_bound"]) * weight)
                    upper_bounds.append(float(pred["upper_bound"]) * weight)

                    if target_date is None:
                        target_date = pred["target_date"]

            if values and target_date:
                ensemble_value = sum(values)
                ensemble_lower = sum(lower_bounds)
                ensemble_upper = sum(upper_bounds)
                
                # Calculate simple standard deviation across models for this day
                # This represents "Model Volatility" or disagreement
                if len(values) > 1:
                    mean_val = sum(values) / len(values) # Unweighted for variance check
                    variance = sum((x - mean_val) ** 2 for x in values) / len(values)
                    std_dev = float(variance ** 0.5)
                else:
                    std_dev = 0.0

                # Calcular confianza como promedio ponderado
                confidence = Decimal("0.90")  # 90% como objetivo

                ensemble_preds.append({
                    "target_date": target_date,
                    "predicted_value": Decimal(str(round(ensemble_value, 2))),
                    "lower_bound": Decimal(str(round(ensemble_lower, 2))),
                    "upper_bound": Decimal(str(round(ensemble_upper, 2))),
                    "confidence": confidence,
                    "model_type": "ensemble",
                    "model_version": self.model_version,
                    "models_used": available_models,
                    "weights": normalized_weights,
                    "model_volatility": Decimal(str(round(std_dev, 2)))
                })

        return ensemble_preds

    def update_weights(self, new_weights: Dict[str, float]) -> None:
        """
        Actualizar pesos del ensemble basado en performance

        Args:
            new_weights: Diccionario con nuevos pesos
        """
        # Validar que sumen ~1
        total = sum(new_weights.values())
        self.weights = {k: v / total for k, v in new_weights.items()}
        logger.info(f"Updated ensemble weights: {self.weights}")

    def get_trend(self, predictions: List[dict]) -> str:
        """Determinar tendencia basada en predicciones ensemble"""
        if len(predictions) < 2:
            return "NEUTRAL"

        first_value = float(predictions[0]["predicted_value"])
        last_value = float(predictions[-1]["predicted_value"])

        change_pct = (last_value - first_value) / first_value

        if change_pct > 0.01:  # > 1%
            return "ALCISTA"
        elif change_pct < -0.01:  # < -1%
            return "BAJISTA"
        else:
            return "NEUTRAL"

    def save_models(self, base_path: str) -> bool:
        """Guardar todos los modelos del ensemble"""
        try:
            prophet_saved = self.prophet.save_model(f"{base_path}/prophet")
            lstm_saved = self.lstm.save_model(f"{base_path}/lstm")

            return prophet_saved or lstm_saved
        except Exception as e:
            logger.error(f"Error saving ensemble models: {e}")
            return False

    def load_models(self, base_path: str) -> bool:
        """Cargar todos los modelos del ensemble"""
        try:
            prophet_loaded = self.prophet.load_model(f"{base_path}/prophet")
            lstm_loaded = self.lstm.load_model(f"{base_path}/lstm")

            self.is_fitted = prophet_loaded or lstm_loaded
            return self.is_fitted
        except Exception as e:
            logger.error(f"Error loading ensemble models: {e}")
            return False


# Instancia singleton
ensemble_model = EnsembleModel()
