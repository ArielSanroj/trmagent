"""
API de Backtesting
Validar estrategias con datos historicos
"""
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.backtesting import backtest_engine
from app.models.database_models import User
from app.models.schemas import BacktestRequest, BacktestResponse
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/backtesting", tags=["Backtesting"])


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ejecutar backtest de estrategia

    **Parametros:**
    - strategy: 'ml_signal', 'momentum', 'mean_reversion'
    - model_type: 'prophet', 'lstm', 'ensemble'
    - start_date: Fecha inicio
    - end_date: Fecha fin
    - initial_capital: Capital inicial en COP
    - min_confidence: Confianza minima (default 0.90 = 90%)
    """
    try:
        metrics, trades = backtest_engine.run_backtest(
            strategy=request.strategy,
            model_type=request.model_type,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            min_confidence=request.min_confidence
        )

        return BacktestResponse(
            id=__import__('uuid').uuid4(),
            strategy_name=request.strategy,
            model_type=request.model_type,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            final_capital=request.initial_capital + metrics.total_return,
            total_return_pct=metrics.total_return_pct,
            sharpe_ratio=metrics.sharpe_ratio,
            max_drawdown_pct=metrics.max_drawdown_pct,
            win_rate=metrics.win_rate,
            total_trades=metrics.total_trades,
            profitable_trades=metrics.profitable_trades,
            avg_trade_return=metrics.avg_trade_return,
            created_at=__import__('datetime').datetime.utcnow()
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Backtest failed: {str(e)}"
        )


@router.get("/history")
async def get_backtest_history(
    limit: int = Query(default=20, le=100),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener historial de backtests ejecutados
    """
    history = backtest_engine.get_backtest_history(limit=limit)

    return {
        "backtests": history,
        "count": len(history)
    }


@router.get("/presets")
async def get_backtest_presets():
    """
    Obtener configuraciones predefinidas de backtest
    """
    return {
        "presets": [
            {
                "name": "quick_test",
                "description": "Test rapido - 1 ano con ensemble",
                "config": {
                    "strategy": "ml_signal",
                    "model_type": "ensemble",
                    "days": 365,
                    "min_confidence": 0.90
                }
            },
            {
                "name": "full_history",
                "description": "Test completo - 5 anos con ensemble",
                "config": {
                    "strategy": "ml_signal",
                    "model_type": "ensemble",
                    "days": 1825,
                    "min_confidence": 0.90
                }
            },
            {
                "name": "prophet_only",
                "description": "Solo modelo Prophet - 2 anos",
                "config": {
                    "strategy": "ml_signal",
                    "model_type": "prophet",
                    "days": 730,
                    "min_confidence": 0.90
                }
            },
            {
                "name": "lstm_only",
                "description": "Solo modelo LSTM - 2 anos",
                "config": {
                    "strategy": "ml_signal",
                    "model_type": "lstm",
                    "days": 730,
                    "min_confidence": 0.90
                }
            },
            {
                "name": "high_confidence",
                "description": "Alta confianza (95%) - 3 anos",
                "config": {
                    "strategy": "ml_signal",
                    "model_type": "ensemble",
                    "days": 1095,
                    "min_confidence": 0.95
                }
            }
        ]
    }


@router.get("/compare")
async def compare_strategies(
    days: int = Query(default=365, ge=90, le=1825),
    current_user: User = Depends(get_current_user)
):
    """
    Comparar rendimiento de diferentes estrategias y modelos
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    results = []

    # Probar diferentes combinaciones
    configurations = [
        ("ml_signal", "ensemble"),
        ("ml_signal", "prophet"),
        ("ml_signal", "lstm"),
    ]

    for strategy, model_type in configurations:
        try:
            metrics, _ = backtest_engine.run_backtest(
                strategy=strategy,
                model_type=model_type,
                start_date=start_date,
                end_date=end_date
            )

            results.append({
                "strategy": strategy,
                "model_type": model_type,
                "total_return_pct": float(metrics.total_return_pct),
                "sharpe_ratio": float(metrics.sharpe_ratio),
                "max_drawdown_pct": float(metrics.max_drawdown_pct),
                "win_rate": float(metrics.win_rate),
                "total_trades": metrics.total_trades
            })

        except Exception as e:
            results.append({
                "strategy": strategy,
                "model_type": model_type,
                "error": str(e)
            })

    # Ordenar por retorno
    valid_results = [r for r in results if "error" not in r]
    valid_results.sort(key=lambda x: x["total_return_pct"], reverse=True)

    return {
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": days
        },
        "results": results,
        "best_performer": valid_results[0] if valid_results else None
    }
