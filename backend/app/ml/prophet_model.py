"""
Modelo Prophet para prediccion de TRM
"""
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import List, Optional, Tuple
from decimal import Decimal
import logging
import pickle
import os

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    logging.warning("Prophet not installed. Install with: pip install prophet")

logger = logging.getLogger(__name__)


class ProphetModel:
    """
    Modelo Prophet para prediccion de series temporales
    Optimizado para TRM USD/COP
    """

    def __init__(self):
        self.model = None
        self.is_fitted = False
        self.model_version = "prophet_v1"
        self.last_trained = None

    def prepare_data(
        self,
        trm_history: List[dict],
        indicators: Optional[dict] = None
    ) -> pd.DataFrame:
        """
        Preparar datos para Prophet

        Args:
            trm_history: Lista de {date, value}
            indicators: Indicadores adicionales (petroleo, tasas, etc)

        Returns:
            DataFrame con columnas ds, y y regresores
        """
        # Crear DataFrame base
        df = pd.DataFrame(trm_history)
        df = df.rename(columns={"date": "ds", "value": "y"})
        df["ds"] = pd.to_datetime(df["ds"])
        df["y"] = df["y"].astype(float)

        # Ordenar por fecha
        df = df.sort_values("ds").reset_index(drop=True)

        # Agregar regresores si estan disponibles
        if indicators:
            # Petroleo WTI (si hay datos)
            if "oil_wti" in indicators and indicators["oil_wti"]:
                # En produccion, hacer merge por fecha
                df["oil_price"] = float(indicators["oil_wti"]["value"])

            # Federal Funds Rate
            if "fed_rate" in indicators and indicators["fed_rate"]:
                df["fed_rate"] = float(indicators["fed_rate"]["value"])

        return df

    def train(
        self,
        trm_history: List[dict],
        indicators: Optional[dict] = None,
        **kwargs
    ) -> bool:
        """
        Entrenar modelo Prophet

        Args:
            trm_history: Historico de TRM
            indicators: Indicadores macroeconomicos
            **kwargs: Parametros adicionales para Prophet

        Returns:
            True si entrenamiento exitoso
        """
        if not PROPHET_AVAILABLE:
            logger.error("Prophet not available")
            return False

        try:
            # Preparar datos
            df = self.prepare_data(trm_history, indicators)

            if len(df) < 30:
                logger.error("Insufficient data for training (need at least 30 days)")
                return False

            # Crear modelo Prophet
            self.model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                changepoint_prior_scale=kwargs.get("changepoint_prior_scale", 0.05),
                seasonality_prior_scale=kwargs.get("seasonality_prior_scale", 10),
                interval_width=0.90,  # 90% intervalo de confianza
            )

            # Agregar regresores si estan en los datos
            if "oil_price" in df.columns:
                self.model.add_regressor("oil_price")
            if "fed_rate" in df.columns:
                self.model.add_regressor("fed_rate")

            # Entrenar
            self.model.fit(df)
            self.is_fitted = True
            self.last_trained = datetime.utcnow()

            logger.info(f"Prophet model trained with {len(df)} data points")
            return True

        except Exception as e:
            logger.error(f"Error training Prophet model: {e}")
            return False

    def predict(
        self,
        trm_history: List[dict],
        days_ahead: int = 30,
        indicators: Optional[dict] = None
    ) -> List[dict]:
        """
        Generar predicciones

        Args:
            trm_history: Historico reciente de TRM (for interface consistency)
            days_ahead: Dias a predecir
            indicators: Indicadores para el futuro (si hay regresores)

        Returns:
            Lista de predicciones con fecha, valor, y bounds
        """
        if not self.is_fitted or self.model is None:
            logger.error("Model not fitted. Call train() first")
            return []

        try:
            # Crear DataFrame futuro
            future = self.model.make_future_dataframe(periods=days_ahead)

            # Agregar regresores si es necesario
            if indicators:
                if "oil_wti" in indicators and indicators["oil_wti"]:
                    future["oil_price"] = float(indicators["oil_wti"]["value"])
                if "fed_rate" in indicators and indicators["fed_rate"]:
                    future["fed_rate"] = float(indicators["fed_rate"]["value"])

            # Predecir
            forecast = self.model.predict(future)

            # Extraer solo predicciones futuras
            today = pd.Timestamp(date.today())
            future_forecast = forecast[forecast["ds"] > today]

            predictions = []
            for _, row in future_forecast.iterrows():
                predictions.append({
                    "target_date": row["ds"].date(),
                    "predicted_value": Decimal(str(round(row["yhat"], 2))),
                    "lower_bound": Decimal(str(round(row["yhat_lower"], 2))),
                    "upper_bound": Decimal(str(round(row["yhat_upper"], 2))),
                    "confidence": Decimal("0.90"),  # 90% intervalo
                    "model_type": "prophet",
                    "model_version": self.model_version
                })

            return predictions

        except Exception as e:
            logger.error(f"Error generating predictions: {e}")
            return []

    def get_trend(self, predictions: List[dict]) -> str:
        """Determinar tendencia basada en predicciones"""
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

    def save_model(self, path: str) -> bool:
        """Guardar modelo entrenado"""
        if not self.is_fitted:
            return False

        try:
            with open(path, "wb") as f:
                pickle.dump({
                    "model": self.model,
                    "version": self.model_version,
                    "trained_at": self.last_trained
                }, f)
            return True
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            return False

    def load_model(self, path: str) -> bool:
        """Cargar modelo guardado"""
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
                self.model = data["model"]
                self.model_version = data["version"]
                self.last_trained = data["trained_at"]
                self.is_fitted = True
            return True
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False


# Instancia singleton
prophet_model = ProphetModel()
