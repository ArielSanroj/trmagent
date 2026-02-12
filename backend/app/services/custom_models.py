"""
Custom Models Service
Modelos ML personalizados por cliente
"""
import logging
import pickle
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID

import pandas as pd

from app.core.database import SessionLocal
from app.models.database_models import CompanyConfig, TRMHistory
from .custom_models_config import ModelConfig, MODELS_DIR
from .custom_models_ml import (
    train_prophet,
    train_lstm,
    train_arima,
    predict_prophet,
    predict_lstm,
    predict_arima,
    combine_predictions
)
from .custom_models_metrics import build_model_performance

logger = logging.getLogger(__name__)


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

            cache_key = str(company_id)
            if cache_key in self._model_cache:
                del self._model_cache[cache_key]

            logger.info(f"Model config updated for company {company_id}")
            return True

        except Exception as exc:
            db.rollback()
            logger.error(f"Error updating model config: {exc}")
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

        if model_path.exists() and not force_retrain:
            if meta_path.exists():
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                    last_trained = datetime.fromisoformat(meta.get("trained_at", "2000-01-01"))
                    if datetime.utcnow() - last_trained < timedelta(days=1):
                        logger.info(f"Model for {company_id} is up to date")
                        return {"status": "up_to_date", "metrics": meta.get("metrics", {})}

        db = SessionLocal()
        try:
            lookback_date = datetime.utcnow() - timedelta(days=config.lookback_days)
            trm_data = db.query(TRMHistory).filter(
                TRMHistory.date >= lookback_date.date()
            ).order_by(TRMHistory.date).all()

            if len(trm_data) < 30:
                return {"status": "error", "message": "Insufficient data for training"}

            df = pd.DataFrame([
                {"ds": t.date, "y": float(t.value)}
                for t in trm_data
            ])

            models = {}
            metrics = {}

            if config.model_type in ["ensemble", "prophet"]:
                prophet_model, prophet_metrics = train_prophet(df, config, logger)
                if prophet_model:
                    models["prophet"] = prophet_model
                    metrics["prophet"] = prophet_metrics

            if config.model_type in ["ensemble", "lstm"]:
                lstm_model, lstm_metrics = train_lstm(df, config, logger)
                if lstm_model:
                    models["lstm"] = lstm_model
                    metrics["lstm"] = lstm_metrics

            if config.model_type in ["ensemble", "arima"]:
                arima_model, arima_metrics = train_arima(df, config, logger)
                if arima_model:
                    models["arima"] = arima_model
                    metrics["arima"] = arima_metrics

            model_bundle = {
                "models": models,
                "config": config.to_dict(),
                "trained_at": datetime.utcnow().isoformat()
            }

            with open(model_path, "wb") as f:
                pickle.dump(model_bundle, f)

            meta = {
                "company_id": str(company_id),
                "trained_at": datetime.utcnow().isoformat(),
                "config": config.to_dict(),
                "metrics": metrics,
                "data_points": len(trm_data)
            }

            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)

            self._model_cache[str(company_id)] = model_bundle

            logger.info(f"Model trained for company {company_id}")

            return {
                "status": "trained",
                "metrics": metrics,
                "data_points": len(trm_data)
            }

        except Exception as exc:
            logger.error(f"Error training model: {exc}")
            return {"status": "error", "message": str(exc)}
        finally:
            db.close()

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
            result = self.train_custom_model(company_id)
            if result["status"] == "error":
                return []
            model_bundle = self._load_model(company_id)

        if not model_bundle:
            return []

        models = model_bundle.get("models", {})

        prophet_preds = predict_prophet(models.get("prophet"), horizon_days, logger)
        lstm_preds = predict_lstm(models.get("lstm"), horizon_days, logger)
        arima_preds = predict_arima(models.get("arima"), horizon_days, logger)

        return combine_predictions(
            horizon_days,
            config,
            prophet_preds,
            lstm_preds,
            arima_preds
        )

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
            except Exception as exc:
                logger.error(f"Error loading model: {exc}")

        return None

    def get_model_performance(self, company_id: UUID) -> Dict[str, Any]:
        """Obtener metricas de performance del modelo"""
        return build_model_performance(company_id, logger)

    def delete_model(self, company_id: UUID) -> bool:
        """Eliminar modelo personalizado"""
        try:
            model_path = MODELS_DIR / f"{company_id}_model.pkl"
            meta_path = MODELS_DIR / f"{company_id}_meta.json"

            if model_path.exists():
                model_path.unlink()
            if meta_path.exists():
                meta_path.unlink()

            cache_key = str(company_id)
            if cache_key in self._model_cache:
                del self._model_cache[cache_key]

            logger.info(f"Model deleted for company {company_id}")
            return True

        except Exception as exc:
            logger.error(f"Error deleting model: {exc}")
            return False


# Instancia singleton
custom_model_service = CustomModelService()
