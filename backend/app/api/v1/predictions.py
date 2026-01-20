"""
API de Predicciones
Generar y consultar predicciones ML

Refactorizado para Clean Architecture:
- Usa Dependency Injection via FastAPI Depends
- Elimina imports directos de singletons
- Interface uniforme IMLModel para todos los modelos
"""
from datetime import date, datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.data_ingestion import data_ingestion_service
from app.models.database_models import Prediction, User
from app.models.schemas import (
    PredictionRequest, PredictionResponse, PredictionForecast
)
from app.api.v1.auth import get_current_user

# Clean Architecture imports
from app.application.interfaces.ml_model import IMLModel
from app.api.dependencies import get_ml_registry
from app.infrastructure.ml.model_registry import MLModelRegistry

router = APIRouter(prefix="/predictions", tags=["Predictions"])


@router.get("/current", response_model=PredictionResponse)
async def get_current_prediction(db: Session = Depends(get_db)):
    """
    Obtener prediccion mas reciente
    """
    prediction = db.query(Prediction).filter(
        Prediction.target_date >= date.today()
    ).order_by(Prediction.target_date.asc()).first()

    if not prediction:
        raise HTTPException(
            status_code=404,
            detail="No prediction available. Run /predictions/generate first."
        )

    # Determinar tendencia
    current_trm = await data_ingestion_service.get_current_trm()
    if current_trm:
        trend = "ALCISTA" if float(prediction.predicted_value) > float(current_trm["value"]) else "BAJISTA"
    else:
        trend = "NEUTRAL"

    return PredictionResponse(
        id=prediction.id,
        target_date=prediction.target_date,
        predicted_value=prediction.predicted_value,
        lower_bound=prediction.lower_bound,
        upper_bound=prediction.upper_bound,
        confidence=prediction.confidence,
        model_type=prediction.model_type,
        trend=trend,
        created_at=prediction.created_at
    )


@router.get("/forecast", response_model=PredictionForecast)
async def get_forecast(
    days: int = Query(default=30, ge=1, le=90),
    db: Session = Depends(get_db)
):
    """
    Obtener predicciones para los proximos X dias
    """
    predictions = db.query(Prediction).filter(
        Prediction.target_date >= date.today(),
        Prediction.target_date <= date.today() + timedelta(days=days)
    ).order_by(Prediction.target_date.asc()).all()

    if not predictions:
        raise HTTPException(
            status_code=404,
            detail="No predictions available. Run /predictions/generate first."
        )

    # Obtener TRM actual para tendencia
    current_trm = await data_ingestion_service.get_current_trm()
    current_value = float(current_trm["value"]) if current_trm else 0

    response_preds = []
    for pred in predictions:
        trend = "NEUTRAL"
        if current_value > 0:
            if float(pred.predicted_value) > current_value * 1.01:
                trend = "ALCISTA"
            elif float(pred.predicted_value) < current_value * 0.99:
                trend = "BAJISTA"

        response_preds.append(PredictionResponse(
            id=pred.id,
            target_date=pred.target_date,
            predicted_value=pred.predicted_value,
            lower_bound=pred.lower_bound,
            upper_bound=pred.upper_bound,
            confidence=pred.confidence,
            model_type=pred.model_type,
            trend=trend,
            created_at=pred.created_at
        ))

    # Calcular resumen
    if predictions:
        avg_pred = sum(float(p.predicted_value) for p in predictions) / len(predictions)
        min_pred = min(float(p.predicted_value) for p in predictions)
        max_pred = max(float(p.predicted_value) for p in predictions)
        avg_confidence = sum(float(p.confidence) for p in predictions) / len(predictions)
    else:
        avg_pred = min_pred = max_pred = avg_confidence = 0

    summary = {
        "current_trm": current_value,
        "average_prediction": round(avg_pred, 2),
        "min_prediction": round(min_pred, 2),
        "max_prediction": round(max_pred, 2),
        "average_confidence": round(avg_confidence * 100, 1),
        "days_forecasted": len(predictions),
        "overall_trend": (
            "ALCISTA" if avg_pred > current_value * 1.01
            else "BAJISTA" if avg_pred < current_value * 0.99
            else "NEUTRAL"
        )
    }

    return PredictionForecast(
        predictions=response_preds,
        summary=summary
    )


@router.get("/history")
async def get_prediction_history(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db)
):
    """
    Obtener historial de predicciones
    """
    query = db.query(Prediction)

    if from_date:
        query = query.filter(Prediction.target_date >= from_date)
    if to_date:
        query = query.filter(Prediction.target_date <= to_date)

    predictions = query.order_by(
        Prediction.target_date.desc()
    ).limit(limit).all()

    return {
        "predictions": [
            {
                "id": str(p.id),
                "target_date": p.target_date.isoformat(),
                "predicted_value": float(p.predicted_value),
                "actual_value": float(p.actual_value) if p.actual_value else None,
                "error_pct": float(p.error_pct) if p.error_pct else None,
                "confidence": float(p.confidence),
                "model_type": p.model_type,
                "created_at": p.created_at.isoformat()
            }
            for p in predictions
        ],
        "count": len(predictions)
    }


@router.post("/generate")
async def generate_predictions(
    request: PredictionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ml_registry: MLModelRegistry = Depends(get_ml_registry)
):
    """
    Generar nuevas predicciones
    Requiere autenticacion

    Refactorizado:
    - Usa MLModelRegistry en lugar de imports directos
    - Interface uniforme IMLModel - sin condicionales por tipo de modelo
    - Resuelve violaciones OCP y LSP
    """
    # Obtener datos historicos
    trm_history = await data_ingestion_service.get_trm_history(days=365)

    if len(trm_history) < 90:
        raise HTTPException(
            status_code=400,
            detail="Insufficient historical data. Need at least 90 days."
        )

    # Obtener indicadores
    indicators = await data_ingestion_service.get_latest_indicators()

    # Obtener modelo via Registry (OCP: sin if/elif)
    try:
        model: IMLModel = ml_registry.get_model(request.model_type)
    except ValueError as e:
        available = ml_registry.available_models()
        raise HTTPException(
            status_code=400,
            detail=f"Modelo invalido: {request.model_type}. "
                   f"Disponibles: {', '.join(available)}"
        )

    # Entrenar si es necesario
    if not model.is_fitted:
        success = model.train(trm_history, indicators)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to train model"
            )

    # Generar predicciones - INTERFACE UNIFORME (LSP resuelto)
    # Todos los modelos ahora tienen la misma firma:
    # predict(trm_history, days_ahead, indicators)
    predictions = model.predict(trm_history, request.days_ahead, indicators)

    if not predictions:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate predictions"
        )

    # Guardar en BD
    saved_count = 0
    for pred in predictions:
        db_pred = Prediction(
            target_date=pred["target_date"],
            predicted_value=pred["predicted_value"],
            lower_bound=pred.get("lower_bound"),
            upper_bound=pred.get("upper_bound"),
            confidence=pred["confidence"],
            model_type=pred["model_type"],
            model_version=pred.get("model_version", "v1")
        )
        db.add(db_pred)
        saved_count += 1

    db.commit()

    return {
        "generated": len(predictions),
        "saved": saved_count,
        "model_type": request.model_type,
        "days_ahead": request.days_ahead,
        "first_prediction": {
            "date": str(predictions[0]["target_date"]),
            "value": float(predictions[0]["predicted_value"]),
            "confidence": float(predictions[0]["confidence"])
        },
        "last_prediction": {
            "date": str(predictions[-1]["target_date"]),
            "value": float(predictions[-1]["predicted_value"]),
            "confidence": float(predictions[-1]["confidence"])
        }
    }


@router.get("/models")
async def list_available_models(
    ml_registry: MLModelRegistry = Depends(get_ml_registry)
):
    """
    Listar modelos ML disponibles

    Nuevo endpoint agregado como parte de la refactorizacion
    """
    models = ml_registry.available_models()
    return {
        "models": models,
        "default": "ensemble",
        "status": {
            name: {
                "is_fitted": ml_registry.is_model_fitted(name)
            }
            for name in models
        }
    }
