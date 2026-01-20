"""
Configuracion de Celery para tareas asincronas y scheduler
"""
from celery import Celery
from celery.schedules import crontab
from .config import settings

celery_app = Celery(
    "trm_agent",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.services.scheduler",
    ]
)

# Configuracion de Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Bogota",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutos max por tarea
)

# Scheduler: Tareas periodicas
celery_app.conf.beat_schedule = {
    # Actualizar datos de TRM cada hora de 6am a 6pm
    "fetch-trm-hourly": {
        "task": "app.services.scheduler.fetch_trm_data",
        "schedule": crontab(minute=0, hour="6-18"),
    },
    # Generar prediccion diaria a las 6:30 AM
    "daily-prediction": {
        "task": "app.services.scheduler.generate_daily_prediction",
        "schedule": crontab(
            minute=settings.PREDICTION_CRON_MINUTE + 30,
            hour=settings.PREDICTION_CRON_HOUR
        ),
    },
    # Evaluar senales de trading cada 15 minutos en horario de mercado
    "evaluate-signals": {
        "task": "app.services.scheduler.evaluate_trading_signals",
        "schedule": crontab(minute="*/15", hour="6-18"),
    },
    # Limpiar datos antiguos semanalmente
    "weekly-cleanup": {
        "task": "app.services.scheduler.cleanup_old_data",
        "schedule": crontab(minute=0, hour=2, day_of_week=0),
    },
}
