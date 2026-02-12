"""Metricas y performance para modelos personalizados."""
import json
from datetime import datetime, timedelta
from typing import Dict, Any

import numpy as np

from app.core.database import SessionLocal
from app.models.database_models import TRMHistory, Prediction
from .custom_models_config import MODELS_DIR


def build_model_performance(company_id, logger) -> Dict[str, Any]:
    """Obtener metricas de performance del modelo"""
    meta_path = MODELS_DIR / f"{company_id}_meta.json"

    if not meta_path.exists():
        return {"status": "no_model"}

    with open(meta_path, "r") as f:
        meta = json.load(f)

    db = SessionLocal()
    try:
        week_ago = datetime.utcnow() - timedelta(days=7)
        predictions = db.query(Prediction).filter(
            Prediction.company_id == company_id,
            Prediction.target_date <= datetime.utcnow().date(),
            Prediction.created_at >= week_ago
        ).all()

        actual_values = {}
        trm_data = db.query(TRMHistory).filter(
            TRMHistory.date >= week_ago.date()
        ).all()

        for t in trm_data:
            actual_values[t.date] = float(t.value)

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

    except Exception as exc:
        logger.error(f"Error computing model performance: {exc}")
        return {"status": "error", "message": str(exc)}
    finally:
        db.close()
