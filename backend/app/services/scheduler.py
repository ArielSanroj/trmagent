"""
Scheduler - Tareas programadas con Celery
Cron jobs para predicciones periodicas, actualizacion de datos, alertas
"""
import logging
from datetime import datetime, date
from typing import Optional

from app.core.celery_app import celery_app
from app.services.data_ingestion import data_ingestion_service
from app.services.decision_engine import decision_engine
from app.services.notification_service import notification_service
from app.ml.ensemble_model import ensemble_model
from app.core.database import SessionLocal
from app.models.database_models import Prediction, TradingSignal, SignalStatus

logger = logging.getLogger(__name__)


@celery_app.task(name="app.services.scheduler.fetch_trm_data")
def fetch_trm_data():
    """
    Tarea: Obtener datos de TRM y almacenar en BD
    Frecuencia: Cada hora de 6am a 6pm
    """
    import asyncio

    logger.info("Starting TRM data fetch task")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Obtener TRM de los ultimos 7 dias
        inserted = loop.run_until_complete(
            data_ingestion_service.fetch_and_store_trm(days=7)
        )

        # Obtener indicadores macro
        indicators = loop.run_until_complete(
            data_ingestion_service.fetch_and_store_indicators()
        )

        logger.info(f"TRM fetch complete. Inserted {inserted} records. Indicators: {indicators}")
        return {"trm_inserted": inserted, "indicators": indicators}

    except Exception as e:
        logger.error(f"Error in TRM fetch task: {e}")
        return {"error": str(e)}


@celery_app.task(name="app.services.scheduler.generate_daily_prediction")
def generate_daily_prediction():
    """
    Tarea: Generar prediccion diaria usando modelos ML
    Frecuencia: Diaria a las 6:30 AM
    """
    import asyncio

    logger.info("Starting daily prediction task")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Obtener datos historicos
        trm_history = loop.run_until_complete(
            data_ingestion_service.get_trm_history(days=365)
        )

        if len(trm_history) < 90:
            logger.warning("Insufficient data for prediction")
            return {"error": "Insufficient data"}

        # Obtener indicadores
        indicators = loop.run_until_complete(
            data_ingestion_service.get_latest_indicators()
        )

        # Entrenar modelo si es necesario
        if not ensemble_model.is_fitted:
            logger.info("Training ensemble model...")
            ensemble_model.train(trm_history, indicators)

        # Generar predicciones
        predictions = ensemble_model.predict(trm_history, days_ahead=30, indicators=indicators)

        if not predictions:
            logger.warning("No predictions generated")
            return {"error": "No predictions generated"}

        # Guardar predicciones en BD
        db = SessionLocal()
        saved_count = 0

        try:
            for pred in predictions[:7]:  # Guardar solo proximos 7 dias
                prediction = Prediction(
                    target_date=pred["target_date"],
                    predicted_value=pred["predicted_value"],
                    lower_bound=pred.get("lower_bound"),
                    upper_bound=pred.get("upper_bound"),
                    confidence=pred["confidence"],
                    model_type=pred["model_type"],
                    model_version=pred.get("model_version", "v1")
                )
                db.add(prediction)
                saved_count += 1

            db.commit()
            logger.info(f"Saved {saved_count} predictions")

        finally:
            db.close()

        return {
            "predictions_generated": len(predictions),
            "predictions_saved": saved_count,
            "first_prediction": {
                "date": str(predictions[0]["target_date"]),
                "value": float(predictions[0]["predicted_value"]),
                "confidence": float(predictions[0]["confidence"])
            }
        }

    except Exception as e:
        logger.error(f"Error in prediction task: {e}")
        return {"error": str(e)}


@celery_app.task(name="app.services.scheduler.evaluate_trading_signals")
def evaluate_trading_signals():
    """
    Tarea: Evaluar condiciones de mercado y generar senales
    Frecuencia: Cada 15 minutos en horario de mercado
    """
    import asyncio

    logger.info("Starting trading signal evaluation")

    try:
        # Generar senal
        decision = asyncio.run(decision_engine.generate_signal())

        logger.info(
            f"Signal generated: {decision.action.value}, "
            f"confidence: {decision.confidence:.1%}, "
            f"approved: {decision.approved}"
        )

        # Guardar senal si es relevante
        if decision.action.value != "HOLD" and decision.approved:
            signal_id = decision_engine.save_signal_to_db(decision)

            # Enviar alertas
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            alert_results = loop.run_until_complete(
                notification_service.send_trading_alert(decision)
            )

            return {
                "signal_id": str(signal_id) if signal_id else None,
                "action": decision.action.value,
                "confidence": float(decision.confidence),
                "approved": decision.approved,
                "alerts_sent": alert_results
            }

        return {
            "action": decision.action.value,
            "confidence": float(decision.confidence),
            "approved": decision.approved,
            "reason": decision.reasoning
        }

    except Exception as e:
        logger.error(f"Error in signal evaluation: {e}")
        return {"error": str(e)}


@celery_app.task(name="app.services.scheduler.cleanup_old_data")
def cleanup_old_data():
    """
    Tarea: Limpiar datos antiguos para mantener BD optimizada
    Frecuencia: Semanal (domingo 2am)
    """
    from datetime import timedelta

    logger.info("Starting cleanup task")
    db = SessionLocal()

    try:
        # Eliminar senales expiradas (mas de 30 dias)
        cutoff_date = datetime.utcnow() - timedelta(days=30)

        expired_signals = db.query(TradingSignal).filter(
            TradingSignal.created_at < cutoff_date,
            TradingSignal.status.in_([SignalStatus.EXPIRED, SignalStatus.CANCELLED])
        ).delete(synchronize_session=False)

        # Eliminar predicciones antiguas (mas de 90 dias)
        old_predictions = db.query(Prediction).filter(
            Prediction.created_at < datetime.utcnow() - timedelta(days=90)
        ).delete(synchronize_session=False)

        db.commit()

        logger.info(
            f"Cleanup complete. Deleted {expired_signals} signals, "
            f"{old_predictions} predictions"
        )

        return {
            "deleted_signals": expired_signals,
            "deleted_predictions": old_predictions
        }

    except Exception as e:
        logger.error(f"Error in cleanup task: {e}")
        db.rollback()
        return {"error": str(e)}

    finally:
        db.close()


@celery_app.task(name="app.services.scheduler.retrain_models")
def retrain_models():
    """
    Tarea: Re-entrenar modelos ML con datos nuevos
    Frecuencia: Semanal o cuando se requiera
    """
    import asyncio

    logger.info("Starting model retraining task")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Obtener datos historicos (1 ano)
        trm_history = loop.run_until_complete(
            data_ingestion_service.get_trm_history(days=365)
        )

        if len(trm_history) < 180:
            logger.warning("Insufficient data for retraining")
            return {"error": "Insufficient data"}

        # Obtener indicadores
        indicators = loop.run_until_complete(
            data_ingestion_service.get_latest_indicators()
        )

        # Re-entrenar ensemble
        success = ensemble_model.train(trm_history, indicators)

        if success:
            logger.info("Model retraining successful")
            return {"success": True, "data_points": len(trm_history)}
        else:
            logger.warning("Model retraining failed")
            return {"success": False}

    except Exception as e:
        logger.error(f"Error in model retraining: {e}")
        return {"error": str(e)}


# Funciones auxiliares para ejecutar tareas manualmente

def run_fetch_trm():
    """Ejecutar fetch de TRM manualmente"""
    return fetch_trm_data.delay()


def run_prediction():
    """Ejecutar prediccion manualmente"""
    return generate_daily_prediction.delay()


def run_signal_evaluation():
    """Ejecutar evaluacion de senales manualmente"""
    return evaluate_trading_signals.delay()


def run_cleanup():
    """Ejecutar limpieza manualmente"""
    return cleanup_old_data.delay()


def run_retrain():
    """Ejecutar reentrenamiento manualmente"""
    return retrain_models.delay()
