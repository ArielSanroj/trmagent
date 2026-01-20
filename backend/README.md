# TRM Agent - Backend API

Backend en Python para el agente de trading USD/COP con predicciones ML.

## Stack Tecnologico

- **Framework**: FastAPI
- **Database**: PostgreSQL + SQLAlchemy
- **Cache/Queue**: Redis + Celery
- **ML**: Prophet, TensorFlow/LSTM, Ensemble
- **Auth**: JWT

## Configuracion

1. **Copiar archivo de entorno**:
```bash
cp .env.example .env
```

2. **Configurar variables** en `.env`:
- `DATABASE_URL`: URL de PostgreSQL
- `REDIS_URL`: URL de Redis
- `JWT_SECRET`: Clave secreta para JWT
- `TELEGRAM_BOT_TOKEN`: Token del bot de Telegram
- `SLACK_WEBHOOK_URL`: URL del webhook de Slack

## Instalacion

### Con Docker (Recomendado)

```bash
# Iniciar todos los servicios
docker-compose up -d

# Ver logs
docker-compose logs -f api
```

### Manual

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
.\venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt

# Iniciar PostgreSQL y Redis (localmente o en Docker)
docker-compose up -d postgres redis

# Crear tablas
python -c "from app.core.database import Base, engine; Base.metadata.create_all(bind=engine)"

# Iniciar servidor
uvicorn app.main:app --reload --port 8000
```

## Endpoints API

### Autenticacion
- `POST /api/v1/auth/register` - Registrar usuario
- `POST /api/v1/auth/login` - Login
- `GET /api/v1/auth/me` - Usuario actual

### Datos de Mercado
- `GET /api/v1/market/trm/current` - TRM actual
- `GET /api/v1/market/trm/history` - Historico TRM
- `GET /api/v1/market/indicators` - Indicadores macro

### Predicciones
- `GET /api/v1/predictions/current` - Prediccion actual
- `GET /api/v1/predictions/forecast` - Pronostico X dias
- `POST /api/v1/predictions/generate` - Generar predicciones

### Trading
- `GET /api/v1/trading/signals/current` - Senal actual
- `POST /api/v1/trading/signals/evaluate` - Evaluar y alertar
- `POST /api/v1/trading/orders/create` - Crear orden
- `GET /api/v1/trading/portfolio/summary` - Resumen portafolio

### Backtesting
- `POST /api/v1/backtesting/run` - Ejecutar backtest
- `GET /api/v1/backtesting/history` - Historial
- `GET /api/v1/backtesting/compare` - Comparar estrategias

## Configuracion de Trading

El sistema usa los siguientes parametros por defecto:

| Parametro | Valor | Descripcion |
|-----------|-------|-------------|
| `MIN_CONFIDENCE` | **0.90 (90%)** | Confianza minima para aprobar senal |
| `MIN_EXPECTED_RETURN` | 0.02 (2%) | Retorno minimo esperado |
| `MAX_DAILY_LOSS` | 0.02 (2%) | Perdida maxima diaria |
| `MAX_POSITION_SIZE` | 0.10 (10%) | Tamano maximo de posicion |

## Scheduler (Tareas Programadas)

Las siguientes tareas se ejecutan automaticamente:

| Tarea | Frecuencia | Descripcion |
|-------|------------|-------------|
| `fetch_trm_data` | Cada hora (6am-6pm) | Actualiza TRM |
| `generate_daily_prediction` | 6:30 AM | Genera prediccion diaria |
| `evaluate_trading_signals` | Cada 15 min | Evalua mercado |
| `cleanup_old_data` | Domingo 2am | Limpia datos antiguos |

## Paper Trading

El sistema tiene paper trading habilitado por defecto. Cada empresa tiene un portafolio simulado con:
- 100,000,000 COP de capital inicial
- Ejecucion simulada de ordenes
- Tracking de PnL

## Documentacion API

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Desarrollo

```bash
# Ejecutar tests
pytest

# Formatear codigo
black app/
isort app/

# Crear migracion
alembic revision --autogenerate -m "descripcion"

# Aplicar migraciones
alembic upgrade head
```

## Estructura del Proyecto

```
backend/
├── app/
│   ├── api/v1/           # Endpoints REST
│   ├── core/             # Config, DB, Security
│   ├── integrations/     # APIs externas
│   ├── ml/               # Modelos ML
│   ├── models/           # SQLAlchemy models
│   └── services/         # Logica de negocio
├── alembic/              # Migraciones
├── tests/                # Tests
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Licencia

Propietario - Todos los derechos reservados
