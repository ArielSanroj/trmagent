"""
TRM Agent - Backend API
Aplicacion principal FastAPI
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import settings
from app.core.database import engine, Base
from app.api.v1 import auth, market, predictions, trading, backtesting, tenants, models, risk
from app.atlas.api import atlas_router

# Import ATLAS models to ensure they are registered with SQLAlchemy
from app.atlas.models import atlas_models  # noqa: F401

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager para la aplicacion"""
    # Startup
    logger.info("Starting TRM Agent API...")

    # Crear tablas si no existen (en produccion usar Alembic)
    if settings.DEBUG:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created")

    yield

    # Shutdown
    logger.info("Shutting down TRM Agent API...")


# Crear aplicacion FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## TRM Agent API

    API para prediccion y trading de USD/COP

    ### Funcionalidades:
    * **Market Data**: TRM actual e historico, indicadores macro
    * **Predictions**: Predicciones ML con Prophet, LSTM, Ensemble
    * **Trading**: Senales, ordenes, paper trading
    * **Backtesting**: Validar estrategias con datos historicos

    ### Configuracion de Confianza
    El sistema usa un umbral de confianza del **90%** para aprobar senales.
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En produccion, especificar dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Incluir routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(market.router, prefix="/api/v1")
app.include_router(predictions.router, prefix="/api/v1")
app.include_router(trading.router, prefix="/api/v1")
app.include_router(backtesting.router, prefix="/api/v1")
app.include_router(tenants.router, prefix="/api/v1")
app.include_router(models.router, prefix="/api/v1")
app.include_router(risk.router, prefix="/api/v1")
app.include_router(atlas_router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "config": {
            "min_confidence": settings.MIN_CONFIDENCE,
            "min_expected_return": settings.MIN_EXPECTED_RETURN
        }
    }


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": __import__('datetime').datetime.utcnow().isoformat()
    }


# API Info
@app.get("/api/v1")
async def api_info():
    """API v1 information"""
    return {
        "version": "1.0.0",
        "endpoints": {
            "auth": "/api/v1/auth",
            "market": "/api/v1/market",
            "predictions": "/api/v1/predictions",
            "trading": "/api/v1/trading",
            "backtesting": "/api/v1/backtesting",
            "tenants": "/api/v1/tenants",
            "models": "/api/v1/models",
            "atlas": "/api/v1/atlas"
        },
        "trading_config": {
            "min_confidence": f"{settings.MIN_CONFIDENCE * 100}%",
            "min_expected_return": f"{settings.MIN_EXPECTED_RETURN * 100}%",
            "max_daily_loss": f"{settings.MAX_DAILY_LOSS * 100}%"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
