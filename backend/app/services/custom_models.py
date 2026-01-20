"""
Custom Models Service
Modelos ML personalizados por cliente
"""
import logging
import pickle
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID
from pathlib import Path
import hashlib

from sqlalchemy.orm import Session
from sqlalchemy import func
import numpy as np
import pandas as pd

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.database_models import Company, CompanyConfig, TRMHistory, Prediction

logger = logging.getLogger(__name__)

# Directorio para guardar modelos
MODELS_DIR = Path("models")
MODELS_DIR.mkdir(exist_ok=True)


class ModelConfig:
    """Configuracion de modelo personalizado"""

    def __init__(
        self,
        model_type: str = "ensemble",
        prophet_weight: float = 0.4,
        lstm_weight: float = 0.4,
        arima_weight: float = 0.2,
        lookback_days: int = 365,
        forecast_horizon: int = 7,
        confidence_threshold: float = 0.90,
        features: Optional[List[str]] = None,
        hyperparameters: Optional[Dict] = None
    ):
        self.model_type = model_type
        self.prophet_weight = prophet_weight
        self.lstm_weight = lstm_weight
        self.arima_weight = arima_weight
        self.lookback_days = lookback_days
        self.forecast_horizon = forecast_horizon
        self.confidence_threshold = confidence_threshold
        self.features = features or ["trm", "oil_price", "dxy_index"]
        self.hyperparameters = hyperparameters or {}

    def to_dict(self) -> Dict:
        return {
            "model_type": self.model_type,
            "prophet_weight": self.prophet_weight,
            "lstm_weight": self.lstm_weight,
            "arima_weight": self.arima_weight,
            "lookback_days": self.lookback_days,
            "forecast_horizon": self.forecast_horizon,
            "confidence_threshold": self.confidence_threshold,
            "features": self.features,
            "hyperparameters": self.hyperparameters
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ModelConfig":
        return cls(**data)


class CustomModelService:
    """
    Servicio de modelos personalizados por cliente

    Funcionalidades:
    - Configuracion de pesos del ensemble por cliente
    - Entrenamiento de modelos personalizados
    - Almacenamiento y versionado de modelos
    - Metricas de performance por cliente
    """

    def __init__(self):
        self.default_config = ModelConfig()
        self._model_cache: Dict[str, Any] = {}

    def get_model_config(self, company_id: UUID) -> ModelConfig:
        """Obtener configuracion de modelo para una empresa"""
        db = SessionLocal()
        try:
            config = db.query(CompanyConfig).filter(
                CompanyConfig.company_id == company_id
            ).first()

            if config and config.model_settings:
                return ModelConfig.from_dict(config.model_settings)
            return self.default_config

        finally:
            db.close()

    def update_model_config(
        self,
        company_id: UUID,
        config: ModelConfig
    ) -> bool:
        """Actualizar configuracion de modelo para una empresa"""
        db = SessionLocal()
        try:
            company_config = db.query(CompanyConfig).filter(
                CompanyConfig.company_id == company_id
            ).first()

            if not company_config:
                company_config = CompanyConfig(company_id=company_id)
                db.add(company_config)

            company_config.model_settings = config.to_dict()
            db.commit()

            # Invalidar cache
            cache_key = str(company_id)
            if cache_key in self._model_cache:
                del self._model_cache[cache_key]

            logger.info(f"Model config updated for company {company_id}")
            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Error updating model config: {e}")
            return False
        finally:
            db.close()

    def train_custom_model(
        self,
        company_id: UUID,
        force_retrain: bool = False
    ) -> Dict[str, Any]:
        """
        Entrenar modelo personalizado para una empresa

        Args:
            company_id: ID de la empresa
            force_retrain: Forzar reentrenamiento

        Returns:
            Dict con metricas de entrenamiento
        """
        config = self.get_model_config(company_id)
        model_path = MODELS_DIR / f"{company_id}_model.pkl"
        meta_path = MODELS_DIR / f"{company_id}_meta.json"

        # Verificar si necesita reentrenamiento
        if model_path.exists() and not force_retrain:
            if meta_path.exists():
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                    last_trained = datetime.fromisoformat(meta.get("trained_at", "2000-01-01"))
                    if datetime.utcnow() - last_trained < timedelta(days=1):
                        logger.info(f"Model for {company_id} is up to date")
                        return {"status": "up_to_date", "metrics": meta.get("metrics", {})}

        # Obtener datos historicos
        db = SessionLocal()
        try:
            # Obtener datos de TRM
            lookback_date = datetime.utcnow() - timedelta(days=config.lookback_days)
            trm_data = db.query(TRMHistory).filter(
                TRMHistory.date >= lookback_date.date()
            ).order_by(TRMHistory.date).all()

            if len(trm_data) < 30:
                return {"status": "error", "message": "Insufficient data for training"}

            # Preparar datos
            df = pd.DataFrame([
                {"ds": t.date, "y": float(t.value)}
                for t in trm_data
            ])

            # Entrenar modelos segun configuracion
            models = {}
            metrics = {}

            if config.model_type in ["ensemble", "prophet"]:
                prophet_model, prophet_metrics = self._train_prophet(df, config)
                if prophet_model:
                    models["prophet"] = prophet_model
                    metrics["prophet"] = prophet_metrics

            if config.model_type in ["ensemble", "lstm"]:
                lstm_model, lstm_metrics = self._train_lstm(df, config)
                if lstm_model:
                    models["lstm"] = lstm_model
                    metrics["lstm"] = lstm_metrics

            if config.model_type in ["ensemble", "arima"]:
                arima_model, arima_metrics = self._train_arima(df, config)
                if arima_model:
                    models["arima"] = arima_model
                    metrics["arima"] = arima_metrics

            # Guardar modelos
            model_bundle = {
                "models": models,
                "config": config.to_dict(),
                "trained_at": datetime.utcnow().isoformat()
            }

            with open(model_path, "wb") as f:
                pickle.dump(model_bundle, f)

            # Guardar metadata
            meta = {
                "company_id": str(company_id),
                "trained_at": datetime.utcnow().isoformat(),
                "config": config.to_dict(),
                "metrics": metrics,
                "data_points": len(trm_data)
            }

            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)

            # Actualizar cache
            self._model_cache[str(company_id)] = model_bundle

            logger.info(f"Model trained for company {company_id}")

            return {
                "status": "trained",
                "metrics": metrics,
                "data_points": len(trm_data)
            }

        except Exception as e:
            logger.error(f"Error training model: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            db.close()

    def _train_prophet(self, df: pd.DataFrame, config: ModelConfig) -> tuple:
        """Entrenar modelo Prophet"""
        try:
            from prophet import Prophet

            model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                **config.hyperparameters.get("prophet", {})
            )

            # Entrenar
            model.fit(df)

            # Calcular metricas con validacion cruzada simple
            train_size = int(len(df) * 0.8)
            train_df = df[:train_size]
            test_df = df[train_size:]

            model_cv = Prophet()
            model_cv.fit(train_df)

            future = model_cv.make_future_dataframe(periods=len(test_df))
            forecast = model_cv.predict(future)

            # Calcular RMSE
            test_predictions = forecast.tail(len(test_df))["yhat"].values
            test_actual = test_df["y"].values
            rmse = np.sqrt(np.mean((test_predictions - test_actual) ** 2))
            mape = np.mean(np.abs((test_actual - test_predictions) / test_actual)) * 100

            return model, {"rmse": rmse, "mape": mape}

        except Exception as e:
            logger.error(f"Prophet training error: {e}")
            return None, {}

    def _train_lstm(self, df: pd.DataFrame, config: ModelConfig) -> tuple:
        """Entrenar modelo LSTM"""
        try:
            from tensorflow.keras.models import Sequential
            from tensorflow.keras.layers import LSTM, Dense, Dropout
            from sklearn.preprocessing import MinMaxScaler

            # Preparar datos
            scaler = MinMaxScaler()
            scaled_data = scaler.fit_transform(df[["y"]].values)

            # Crear secuencias
            lookback = config.hyperparameters.get("lstm", {}).get("lookback", 60)
            X, y = [], []
            for i in range(lookback, len(scaled_data)):
                X.append(scaled_data[i-lookback:i, 0])
                y.append(scaled_data[i, 0])

            X, y = np.array(X), np.array(y)
            X = X.reshape((X.shape[0], X.shape[1], 1))

            # Split
            train_size = int(len(X) * 0.8)
            X_train, X_test = X[:train_size], X[train_size:]
            y_train, y_test = y[:train_size], y[train_size:]

            # Modelo
            model = Sequential([
                LSTM(50, return_sequences=True, input_shape=(lookback, 1)),
                Dropout(0.2),
                LSTM(50, return_sequences=False),
                Dropout(0.2),
                Dense(25),
                Dense(1)
            ])

            model.compile(optimizer="adam", loss="mean_squared_error")
            model.fit(
                X_train, y_train,
                batch_size=32,
                epochs=config.hyperparameters.get("lstm", {}).get("epochs", 50),
                validation_split=0.1,
                verbose=0
            )

            # Calcular metricas
            predictions = model.predict(X_test)
            predictions = scaler.inverse_transform(predictions)
            y_test_actual = scaler.inverse_transform(y_test.reshape(-1, 1))

            rmse = np.sqrt(np.mean((predictions - y_test_actual) ** 2))
            mape = np.mean(np.abs((y_test_actual - predictions) / y_test_actual)) * 100

            # Guardar scaler con el modelo
            model_bundle = {"model": model, "scaler": scaler, "lookback": lookback}

            return model_bundle, {"rmse": float(rmse), "mape": float(mape[0])}

        except Exception as e:
            logger.error(f"LSTM training error: {e}")
            return None, {}

    def _train_arima(self, df: pd.DataFrame, config: ModelConfig) -> tuple:
        """Entrenar modelo ARIMA"""
        try:
            from statsmodels.tsa.arima.model import ARIMA

            # Split
            train_size = int(len(df) * 0.8)
            train_data = df["y"].values[:train_size]
            test_data = df["y"].values[train_size:]

            # Entrenar ARIMA
            order = config.hyperparameters.get("arima", {}).get("order", (5, 1, 0))
            model = ARIMA(train_data, order=order)
            model_fit = model.fit()

            # Predicciones
            predictions = model_fit.forecast(steps=len(test_data))

            # Metricas
            rmse = np.sqrt(np.mean((predictions - test_data) ** 2))
            mape = np.mean(np.abs((test_data - predictions) / test_data)) * 100

            # Entrenar modelo final con todos los datos
            final_model = ARIMA(df["y"].values, order=order)
            final_fit = final_model.fit()

            return final_fit, {"rmse": float(rmse), "mape": float(mape)}

        except Exception as e:
            logger.error(f"ARIMA training error: {e}")
            return None, {}

    def predict(
        self,
        company_id: UUID,
        horizon_days: int = 7
    ) -> List[Dict]:
        """
        Generar predicciones usando modelo personalizado

        Args:
            company_id: ID de la empresa
            horizon_days: Dias a predecir

        Returns:
            Lista de predicciones
        """
        config = self.get_model_config(company_id)
        model_bundle = self._load_model(company_id)

        if not model_bundle:
            # Entrenar si no existe
            result = self.train_custom_model(company_id)
            if result["status"] == "error":
                return []
            model_bundle = self._load_model(company_id)

        if not model_bundle:
            return []

        models = model_bundle.get("models", {})
        predictions = []

        # Generar predicciones por modelo
        prophet_preds = self._predict_prophet(models.get("prophet"), horizon_days)
        lstm_preds = self._predict_lstm(models.get("lstm"), horizon_days, company_id)
        arima_preds = self._predict_arima(models.get("arima"), horizon_days)

        # Combinar predicciones con pesos
        for i in range(horizon_days):
            target_date = datetime.utcnow().date() + timedelta(days=i+1)
            values = []
            weights = []

            if prophet_preds and i < len(prophet_preds):
                values.append(prophet_preds[i])
                weights.append(config.prophet_weight)

            if lstm_preds and i < len(lstm_preds):
                values.append(lstm_preds[i])
                weights.append(config.lstm_weight)

            if arima_preds and i < len(arima_preds):
                values.append(arima_preds[i])
                weights.append(config.arima_weight)

            if values:
                # Promedio ponderado
                total_weight = sum(weights)
                weighted_value = sum(v * w for v, w in zip(values, weights)) / total_weight

                # Calcular confianza basada en concordancia
                if len(values) > 1:
                    std_dev = np.std(values)
                    max_dev = max(values) - min(values)
                    confidence = max(0.5, 1 - (max_dev / weighted_value * 10))
                else:
                    confidence = 0.75

                predictions.append({
                    "target_date": target_date.isoformat(),
                    "predicted_value": round(weighted_value, 2),
                    "confidence": round(confidence, 4),
                    "model_predictions": {
                        "prophet": prophet_preds[i] if prophet_preds and i < len(prophet_preds) else None,
                        "lstm": lstm_preds[i] if lstm_preds and i < len(lstm_preds) else None,
                        "arima": arima_preds[i] if arima_preds and i < len(arima_preds) else None
                    }
                })

        return predictions

    def _load_model(self, company_id: UUID) -> Optional[Dict]:
        """Cargar modelo del cache o disco"""
        cache_key = str(company_id)

        if cache_key in self._model_cache:
            return self._model_cache[cache_key]

        model_path = MODELS_DIR / f"{company_id}_model.pkl"
        if model_path.exists():
            try:
                with open(model_path, "rb") as f:
                    model_bundle = pickle.load(f)
                    self._model_cache[cache_key] = model_bundle
                    return model_bundle
            except Exception as e:
                logger.error(f"Error loading model: {e}")

        return None

    def _predict_prophet(self, model, horizon: int) -> Optional[List[float]]:
        """Predicciones con Prophet"""
        if not model:
            return None
        try:
            future = model.make_future_dataframe(periods=horizon)
            forecast = model.predict(future)
            return forecast.tail(horizon)["yhat"].tolist()
        except Exception as e:
            logger.error(f"Prophet prediction error: {e}")
            return None

    def _predict_lstm(self, model_bundle, horizon: int, company_id: UUID) -> Optional[List[float]]:
        """Predicciones con LSTM"""
        if not model_bundle:
            return None
        try:
            model = model_bundle["model"]
            scaler = model_bundle["scaler"]
            lookback = model_bundle["lookback"]

            # Obtener ultimos datos
            db = SessionLocal()
            try:
                recent_data = db.query(TRMHistory).order_by(
                    TRMHistory.date.desc()
                ).limit(lookback).all()

                if len(recent_data) < lookback:
                    return None

                values = [float(t.value) for t in reversed(recent_data)]
                scaled = scaler.transform(np.array(values).reshape(-1, 1))

                predictions = []
                current_batch = scaled[-lookback:].reshape(1, lookback, 1)

                for _ in range(horizon):
                    pred = model.predict(current_batch, verbose=0)[0, 0]
                    predictions.append(pred)
                    current_batch = np.append(current_batch[:, 1:, :], [[[pred]]], axis=1)

                # Inverse transform
                predictions = scaler.inverse_transform(
                    np.array(predictions).reshape(-1, 1)
                ).flatten().tolist()

                return predictions

            finally:
                db.close()

        except Exception as e:
            logger.error(f"LSTM prediction error: {e}")
            return None

    def _predict_arima(self, model, horizon: int) -> Optional[List[float]]:
        """Predicciones con ARIMA"""
        if not model:
            return None
        try:
            forecast = model.forecast(steps=horizon)
            return forecast.tolist()
        except Exception as e:
            logger.error(f"ARIMA prediction error: {e}")
            return None

    def get_model_performance(self, company_id: UUID) -> Dict[str, Any]:
        """Obtener metricas de performance del modelo"""
        meta_path = MODELS_DIR / f"{company_id}_meta.json"

        if not meta_path.exists():
            return {"status": "no_model"}

        with open(meta_path, "r") as f:
            meta = json.load(f)

        # Calcular accuracy reciente
        db = SessionLocal()
        try:
            # Obtener predicciones recientes
            week_ago = datetime.utcnow() - timedelta(days=7)
            predictions = db.query(Prediction).filter(
                Prediction.company_id == company_id,
                Prediction.target_date <= datetime.utcnow().date(),
                Prediction.created_at >= week_ago
            ).all()

            # Obtener valores reales
            actual_values = {}
            trm_data = db.query(TRMHistory).filter(
                TRMHistory.date >= week_ago.date()
            ).all()

            for t in trm_data:
                actual_values[t.date] = float(t.value)

            # Calcular accuracy
            if predictions and actual_values:
                errors = []
                for p in predictions:
                    if p.target_date in actual_values:
                        error = abs(float(p.predicted_value) - actual_values[p.target_date])
                        errors.append(error / actual_values[p.target_date])

                if errors:
                    mape = np.mean(errors) * 100
                    accuracy = 100 - mape
                else:
                    accuracy = None
            else:
                accuracy = None

            return {
                "status": "active",
                "trained_at": meta.get("trained_at"),
                "training_metrics": meta.get("metrics", {}),
                "recent_accuracy": round(accuracy, 2) if accuracy else None,
                "data_points": meta.get("data_points"),
                "config": meta.get("config")
            }

        finally:
            db.close()

    def delete_model(self, company_id: UUID) -> bool:
        """Eliminar modelo personalizado"""
        try:
            model_path = MODELS_DIR / f"{company_id}_model.pkl"
            meta_path = MODELS_DIR / f"{company_id}_meta.json"

            if model_path.exists():
                model_path.unlink()
            if meta_path.exists():
                meta_path.unlink()

            # Limpiar cache
            cache_key = str(company_id)
            if cache_key in self._model_cache:
                del self._model_cache[cache_key]

            logger.info(f"Model deleted for company {company_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting model: {e}")
            return False


# Instancia singleton
custom_model_service = CustomModelService()
