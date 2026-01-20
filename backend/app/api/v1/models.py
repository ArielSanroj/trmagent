"""
Custom Models API Endpoints
Modelos ML personalizados por cliente
"""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel

from app.core.security import get_current_user
from app.services.custom_models import custom_model_service, ModelConfig

router = APIRouter(prefix="/models", tags=["models"])


# Schemas
class ModelConfigRequest(BaseModel):
    model_type: str = "ensemble"
    prophet_weight: float = 0.4
    lstm_weight: float = 0.4
    arima_weight: float = 0.2
    lookback_days: int = 365
    forecast_horizon: int = 7
    confidence_threshold: float = 0.90
    features: Optional[List[str]] = None
    hyperparameters: Optional[dict] = None


class TrainModelRequest(BaseModel):
    force_retrain: bool = False


class PredictRequest(BaseModel):
    horizon_days: int = 7


# Endpoints

@router.get("/config")
async def get_model_config(
    current_user: dict = Depends(get_current_user)
):
    """Obtener configuracion del modelo para la empresa del usuario"""
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario no asociado a una empresa"
        )

    config = custom_model_service.get_model_config(UUID(company_id))
    return config.to_dict()


@router.put("/config")
async def update_model_config(
    request: ModelConfigRequest,
    current_user: dict = Depends(get_current_user)
):
    """Actualizar configuracion del modelo personalizado"""
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario no asociado a una empresa"
        )

    # Solo admin puede modificar
    if current_user.get("role") not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden modificar la configuracion del modelo"
        )

    config = ModelConfig(
        model_type=request.model_type,
        prophet_weight=request.prophet_weight,
        lstm_weight=request.lstm_weight,
        arima_weight=request.arima_weight,
        lookback_days=request.lookback_days,
        forecast_horizon=request.forecast_horizon,
        confidence_threshold=request.confidence_threshold,
        features=request.features,
        hyperparameters=request.hyperparameters
    )

    success = custom_model_service.update_model_config(UUID(company_id), config)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error actualizando configuracion"
        )

    return {"message": "Configuracion actualizada", "config": config.to_dict()}


@router.post("/train")
async def train_model(
    request: TrainModelRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Entrenar modelo personalizado

    El entrenamiento se ejecuta en background
    """
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario no asociado a una empresa"
        )

    # Verificar plan (solo professional y enterprise)
    # En produccion, verificar el plan de la empresa

    # Entrenar en background
    background_tasks.add_task(
        custom_model_service.train_custom_model,
        UUID(company_id),
        request.force_retrain
    )

    return {
        "message": "Entrenamiento iniciado",
        "status": "training",
        "note": "El entrenamiento puede tomar varios minutos"
    }


@router.post("/train/sync")
async def train_model_sync(
    request: TrainModelRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Entrenar modelo personalizado (sincrono)

    Espera a que el entrenamiento termine
    """
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario no asociado a una empresa"
        )

    result = custom_model_service.train_custom_model(
        UUID(company_id),
        request.force_retrain
    )

    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("message", "Error en entrenamiento")
        )

    return result


@router.post("/predict")
async def predict(
    request: PredictRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generar predicciones usando modelo personalizado"""
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario no asociado a una empresa"
        )

    predictions = custom_model_service.predict(
        UUID(company_id),
        request.horizon_days
    )

    if not predictions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se pudieron generar predicciones. Entrene el modelo primero."
        )

    return {
        "company_id": company_id,
        "predictions": predictions,
        "horizon_days": request.horizon_days
    }


@router.get("/performance")
async def get_model_performance(
    current_user: dict = Depends(get_current_user)
):
    """Obtener metricas de performance del modelo"""
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario no asociado a una empresa"
        )

    performance = custom_model_service.get_model_performance(UUID(company_id))

    return performance


@router.delete("/")
async def delete_model(
    current_user: dict = Depends(get_current_user)
):
    """Eliminar modelo personalizado"""
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario no asociado a una empresa"
        )

    # Solo admin puede eliminar
    if current_user.get("role") not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden eliminar el modelo"
        )

    success = custom_model_service.delete_model(UUID(company_id))

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error eliminando modelo"
        )

    return {"message": "Modelo eliminado"}


# Endpoints para comparar modelos (admin)
@router.get("/compare")
async def compare_models(
    current_user: dict = Depends(get_current_user)
):
    """
    Comparar predicciones de diferentes modelos

    Muestra predicciones de Prophet, LSTM y ARIMA por separado
    """
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario no asociado a una empresa"
        )

    # Obtener predicciones con detalles por modelo
    predictions = custom_model_service.predict(UUID(company_id), 7)

    if not predictions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay modelo entrenado"
        )

    # Extraer predicciones individuales
    comparison = {
        "ensemble": [p["predicted_value"] for p in predictions],
        "prophet": [p["model_predictions"]["prophet"] for p in predictions if p["model_predictions"]["prophet"]],
        "lstm": [p["model_predictions"]["lstm"] for p in predictions if p["model_predictions"]["lstm"]],
        "arima": [p["model_predictions"]["arima"] for p in predictions if p["model_predictions"]["arima"]],
        "dates": [p["target_date"] for p in predictions],
        "confidence": [p["confidence"] for p in predictions]
    }

    return comparison


# Endpoint para obtener pesos optimos (basado en backtesting)
@router.get("/optimize-weights")
async def get_optimal_weights(
    current_user: dict = Depends(get_current_user)
):
    """
    Sugerir pesos optimos para el ensemble basado en performance historica

    Analiza cual modelo ha tenido mejor precision y sugiere pesos
    """
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario no asociado a una empresa"
        )

    performance = custom_model_service.get_model_performance(UUID(company_id))

    if performance.get("status") == "no_model":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay modelo entrenado"
        )

    metrics = performance.get("training_metrics", {})

    # Calcular pesos basados en RMSE inverso
    weights = {}
    total_inverse_rmse = 0

    for model_name in ["prophet", "lstm", "arima"]:
        if model_name in metrics and metrics[model_name].get("rmse"):
            inverse_rmse = 1 / metrics[model_name]["rmse"]
            weights[model_name] = inverse_rmse
            total_inverse_rmse += inverse_rmse

    # Normalizar pesos
    if total_inverse_rmse > 0:
        for model_name in weights:
            weights[model_name] = round(weights[model_name] / total_inverse_rmse, 3)

    return {
        "suggested_weights": weights,
        "metrics": metrics,
        "note": "Los pesos se calculan basados en el RMSE inverso de cada modelo"
    }
