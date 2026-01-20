"""
Framework de Backtesting
Validar estrategias con datos historicos (5+ anos)
"""
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Tuple
from decimal import Decimal
from dataclasses import dataclass, field
from uuid import UUID, uuid4
import logging
import numpy as np
import pandas as pd

from app.core.database import SessionLocal
from app.core.config import settings
from app.models.database_models import BacktestResult, TRMHistory
from app.ml.ensemble_model import EnsembleModel
from app.ml.prophet_model import ProphetModel
from app.ml.lstm_model import LSTMModel

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """Trade individual en backtest"""
    entry_date: date
    exit_date: date
    side: str  # 'buy' or 'sell'
    entry_rate: Decimal
    exit_rate: Decimal
    amount: Decimal
    pnl: Decimal
    pnl_pct: Decimal


@dataclass
class BacktestMetrics:
    """Metricas del backtest"""
    total_return: Decimal
    total_return_pct: Decimal
    sharpe_ratio: Decimal
    max_drawdown: Decimal
    max_drawdown_pct: Decimal
    win_rate: Decimal
    total_trades: int
    profitable_trades: int
    avg_trade_return: Decimal
    avg_win: Decimal
    avg_loss: Decimal
    profit_factor: Decimal
    calmar_ratio: Decimal


class BacktestEngine:
    """
    Motor de Backtesting para estrategias de trading
    Valida modelos ML con datos historicos
    """

    def __init__(self):
        self.min_confidence = Decimal(str(settings.MIN_CONFIDENCE))  # 0.90
        self.min_return = Decimal(str(settings.MIN_EXPECTED_RETURN))  # 0.02

    def load_historical_data(
        self,
        start_date: date,
        end_date: date
    ) -> List[dict]:
        """Cargar datos historicos de TRM"""
        db = SessionLocal()
        try:
            records = db.query(TRMHistory).filter(
                TRMHistory.date >= start_date,
                TRMHistory.date <= end_date
            ).order_by(TRMHistory.date.asc()).all()

            return [
                {"date": r.date, "value": r.value}
                for r in records
            ]
        finally:
            db.close()

    def run_backtest(
        self,
        strategy: str = "ml_signal",
        model_type: str = "ensemble",
        start_date: date = None,
        end_date: date = None,
        initial_capital: Decimal = Decimal("100000000"),
        min_confidence: Decimal = None,
        lookback_days: int = 90,
        prediction_horizon: int = 5
    ) -> Tuple[BacktestMetrics, List[BacktestTrade]]:
        """
        Ejecutar backtest de estrategia

        Args:
            strategy: Tipo de estrategia ('ml_signal', 'momentum', 'mean_reversion')
            model_type: Modelo ML a usar ('prophet', 'lstm', 'ensemble')
            start_date: Fecha inicio del backtest
            end_date: Fecha fin del backtest
            initial_capital: Capital inicial en COP
            min_confidence: Confianza minima (default 90%)
            lookback_days: Dias de historia para entrenar modelo
            prediction_horizon: Dias a predecir

        Returns:
            Tuple de (metricas, lista de trades)
        """
        # Defaults
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=365 * 5)  # 5 anos
        if min_confidence is None:
            min_confidence = self.min_confidence

        logger.info(f"Starting backtest from {start_date} to {end_date}")

        # Cargar datos
        full_data = self.load_historical_data(
            start_date - timedelta(days=lookback_days),
            end_date
        )

        if len(full_data) < lookback_days + 30:
            logger.error("Insufficient historical data for backtest")
            return self._empty_metrics(), []

        # Convertir a DataFrame
        df = pd.DataFrame(full_data)
        df['value'] = df['value'].astype(float)

        # Inicializar modelo
        model = self._get_model(model_type)

        # Variables de tracking
        capital = float(initial_capital)
        position_usd = 0.0
        trades: List[BacktestTrade] = []
        equity_curve = [capital]

        # Iterar dia por dia
        test_start_idx = lookback_days
        last_train_date = None

        for i in range(test_start_idx, len(df)):
            current_date = df.iloc[i]['date']
            current_rate = df.iloc[i]['value']

            # Re-entrenar modelo cada 30 dias
            if last_train_date is None or (current_date - last_train_date).days >= 30:
                train_data = full_data[max(0, i - lookback_days):i]
                if len(train_data) >= 30:
                    model.train(train_data)
                    last_train_date = current_date

            # Generar prediccion
            if model.is_fitted:
                recent_data = full_data[max(0, i - lookback_days):i]
                predictions = model.predict(recent_data, days_ahead=prediction_horizon)

                if predictions:
                    pred = predictions[0]
                    predicted_value = float(pred['predicted_value'])
                    confidence = float(pred.get('confidence', 0.5))

                    # Generar senal
                    expected_return = (predicted_value - current_rate) / current_rate

                    signal = self._generate_signal(
                        expected_return=expected_return,
                        confidence=confidence,
                        min_confidence=float(min_confidence)
                    )

                    # Ejecutar trade si hay senal
                    if signal == "BUY" and position_usd == 0:
                        # Comprar USD
                        position_size = capital * 0.1  # 10% del capital
                        usd_bought = position_size / current_rate
                        capital -= position_size
                        position_usd = usd_bought

                        trade = BacktestTrade(
                            entry_date=current_date,
                            exit_date=current_date,  # Se actualiza al cerrar
                            side="buy",
                            entry_rate=Decimal(str(current_rate)),
                            exit_rate=Decimal("0"),
                            amount=Decimal(str(usd_bought)),
                            pnl=Decimal("0"),
                            pnl_pct=Decimal("0")
                        )
                        trades.append(trade)

                    elif signal == "SELL" and position_usd > 0:
                        # Cerrar posicion
                        cop_received = position_usd * current_rate
                        pnl = cop_received - (position_usd * float(trades[-1].entry_rate))
                        pnl_pct = pnl / (position_usd * float(trades[-1].entry_rate))

                        capital += cop_received
                        position_usd = 0

                        # Actualizar ultimo trade
                        trades[-1].exit_date = current_date
                        trades[-1].exit_rate = Decimal(str(current_rate))
                        trades[-1].pnl = Decimal(str(pnl))
                        trades[-1].pnl_pct = Decimal(str(pnl_pct))

            # Actualizar equity curve
            total_value = capital + (position_usd * current_rate)
            equity_curve.append(total_value)

        # Cerrar posicion abierta al final
        if position_usd > 0 and trades:
            final_rate = df.iloc[-1]['value']
            cop_received = position_usd * final_rate
            pnl = cop_received - (position_usd * float(trades[-1].entry_rate))

            trades[-1].exit_date = df.iloc[-1]['date']
            trades[-1].exit_rate = Decimal(str(final_rate))
            trades[-1].pnl = Decimal(str(pnl))
            trades[-1].pnl_pct = Decimal(str(pnl / (position_usd * float(trades[-1].entry_rate))))

            capital += cop_received

        # Calcular metricas
        metrics = self._calculate_metrics(
            initial_capital=float(initial_capital),
            final_capital=capital,
            trades=trades,
            equity_curve=equity_curve
        )

        # Guardar resultado
        self._save_backtest_result(
            strategy=strategy,
            model_type=model_type,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            metrics=metrics
        )

        return metrics, trades

    def _get_model(self, model_type: str):
        """Obtener instancia de modelo"""
        if model_type == "prophet":
            return ProphetModel()
        elif model_type == "lstm":
            return LSTMModel()
        else:
            return EnsembleModel()

    def _generate_signal(
        self,
        expected_return: float,
        confidence: float,
        min_confidence: float
    ) -> str:
        """Generar senal de trading"""
        if confidence < min_confidence:
            return "HOLD"

        if expected_return > float(self.min_return):
            return "BUY"
        elif expected_return < -float(self.min_return):
            return "SELL"
        else:
            return "HOLD"

    def _calculate_metrics(
        self,
        initial_capital: float,
        final_capital: float,
        trades: List[BacktestTrade],
        equity_curve: List[float]
    ) -> BacktestMetrics:
        """Calcular metricas del backtest"""
        # Return total
        total_return = final_capital - initial_capital
        total_return_pct = (total_return / initial_capital) * 100

        # Trades
        total_trades = len(trades)
        profitable_trades = sum(1 for t in trades if float(t.pnl) > 0)
        win_rate = profitable_trades / total_trades if total_trades > 0 else 0

        # Average returns
        if trades:
            returns = [float(t.pnl_pct) for t in trades]
            avg_trade_return = np.mean(returns) if returns else 0

            wins = [float(t.pnl_pct) for t in trades if float(t.pnl) > 0]
            losses = [float(t.pnl_pct) for t in trades if float(t.pnl) < 0]

            avg_win = np.mean(wins) if wins else 0
            avg_loss = np.mean(losses) if losses else 0

            # Profit factor
            gross_profit = sum(float(t.pnl) for t in trades if float(t.pnl) > 0)
            gross_loss = abs(sum(float(t.pnl) for t in trades if float(t.pnl) < 0))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        else:
            avg_trade_return = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0

        # Sharpe ratio (asumiendo risk-free rate de 4%)
        if len(equity_curve) > 1:
            daily_returns = np.diff(equity_curve) / equity_curve[:-1]
            sharpe = (np.mean(daily_returns) - 0.04/252) / (np.std(daily_returns) + 1e-10)
            sharpe = sharpe * np.sqrt(252)  # Anualizar
        else:
            sharpe = 0

        # Max drawdown
        equity_series = np.array(equity_curve)
        peak = np.maximum.accumulate(equity_series)
        drawdown = (peak - equity_series) / peak
        max_drawdown = np.max(drawdown) * 100
        max_drawdown_abs = np.max(peak - equity_series)

        # Calmar ratio
        calmar = total_return_pct / max_drawdown if max_drawdown > 0 else 0

        return BacktestMetrics(
            total_return=Decimal(str(round(total_return, 2))),
            total_return_pct=Decimal(str(round(total_return_pct, 4))),
            sharpe_ratio=Decimal(str(round(sharpe, 4))),
            max_drawdown=Decimal(str(round(max_drawdown_abs, 2))),
            max_drawdown_pct=Decimal(str(round(max_drawdown, 4))),
            win_rate=Decimal(str(round(win_rate, 4))),
            total_trades=total_trades,
            profitable_trades=profitable_trades,
            avg_trade_return=Decimal(str(round(avg_trade_return, 6))),
            avg_win=Decimal(str(round(avg_win, 6))),
            avg_loss=Decimal(str(round(avg_loss, 6))),
            profit_factor=Decimal(str(round(profit_factor, 4))),
            calmar_ratio=Decimal(str(round(calmar, 4)))
        )

    def _empty_metrics(self) -> BacktestMetrics:
        """Retornar metricas vacias"""
        return BacktestMetrics(
            total_return=Decimal("0"),
            total_return_pct=Decimal("0"),
            sharpe_ratio=Decimal("0"),
            max_drawdown=Decimal("0"),
            max_drawdown_pct=Decimal("0"),
            win_rate=Decimal("0"),
            total_trades=0,
            profitable_trades=0,
            avg_trade_return=Decimal("0"),
            avg_win=Decimal("0"),
            avg_loss=Decimal("0"),
            profit_factor=Decimal("0"),
            calmar_ratio=Decimal("0")
        )

    def _save_backtest_result(
        self,
        strategy: str,
        model_type: str,
        start_date: date,
        end_date: date,
        initial_capital: Decimal,
        metrics: BacktestMetrics
    ) -> Optional[UUID]:
        """Guardar resultado de backtest en BD"""
        db = SessionLocal()
        try:
            result = BacktestResult(
                strategy_name=strategy,
                model_type=model_type,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                final_capital=initial_capital + metrics.total_return,
                total_return_pct=metrics.total_return_pct,
                sharpe_ratio=metrics.sharpe_ratio,
                max_drawdown_pct=metrics.max_drawdown_pct,
                win_rate=metrics.win_rate,
                total_trades=metrics.total_trades,
                profitable_trades=metrics.profitable_trades,
                avg_trade_return=metrics.avg_trade_return,
                parameters={
                    "min_confidence": float(self.min_confidence),
                    "min_return": float(self.min_return)
                }
            )
            db.add(result)
            db.commit()
            db.refresh(result)
            return result.id

        except Exception as e:
            logger.error(f"Error saving backtest result: {e}")
            db.rollback()
            return None
        finally:
            db.close()

    def get_backtest_history(self, limit: int = 20) -> List[dict]:
        """Obtener historial de backtests"""
        db = SessionLocal()
        try:
            results = db.query(BacktestResult).order_by(
                BacktestResult.created_at.desc()
            ).limit(limit).all()

            return [
                {
                    "id": str(r.id),
                    "strategy": r.strategy_name,
                    "model_type": r.model_type,
                    "start_date": r.start_date.isoformat(),
                    "end_date": r.end_date.isoformat(),
                    "total_return_pct": float(r.total_return_pct),
                    "sharpe_ratio": float(r.sharpe_ratio),
                    "max_drawdown_pct": float(r.max_drawdown_pct),
                    "win_rate": float(r.win_rate),
                    "total_trades": r.total_trades,
                    "created_at": r.created_at.isoformat()
                }
                for r in results
            ]
        finally:
            db.close()


# Instancia singleton
backtest_engine = BacktestEngine()
