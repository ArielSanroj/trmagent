"""
Configuracion central de la aplicacion TRM Agent
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "TRM Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/trm_agent"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # JWT Auth
    JWT_SECRET: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # AI/ML
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # Data Sources
    DATOS_GOV_URL: str = "https://www.datos.gov.co/resource/32sa-8pi3.json"
    BANREP_API_URL: str = "https://www.banrep.gov.co/estadisticas-economicas"
    FRED_API_KEY: Optional[str] = None
    ALPHA_VANTAGE_KEY: Optional[str] = None
    SETICAP_BASE_URL: str = "https://proxy.set-icap.com/seticap/api/graficos/"
    SETICAP_MONEDA_USD_COP: int = 1
    SETICAP_MARKET_ID: int = 71
    SETICAP_DELAY: str = "15"

    # Trading Configuration - CONFIANZA 90%
    MIN_CONFIDENCE: float = 0.90  # 90% de confianza minima
    MIN_EXPECTED_RETURN: float = 0.02  # 2% retorno minimo esperado
    MAX_DAILY_LOSS: float = 0.02  # 2% perdida maxima diaria
    MAX_POSITION_SIZE: float = 0.10  # 10% del portafolio maximo
    STOP_LOSS_PCT: float = 0.01  # 1% stop loss
    TAKE_PROFIT_PCT: float = 0.03  # 3% take profit

    # Brokers
    IBKR_HOST: str = "127.0.0.1"
    IBKR_PORT: int = 7497
    ALPACA_API_KEY: Optional[str] = None
    ALPACA_SECRET_KEY: Optional[str] = None
    ALPACA_PAPER: bool = True  # Paper trading por defecto

    # Notifications
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    SLACK_WEBHOOK_URL: Optional[str] = None
    SENDGRID_API_KEY: Optional[str] = None

    # Scheduler
    PREDICTION_CRON_HOUR: int = 6  # Ejecutar prediccion a las 6 AM
    PREDICTION_CRON_MINUTE: int = 0

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
