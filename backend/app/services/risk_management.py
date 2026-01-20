"""
Risk Management Service
Gestion avanzada de riesgo para trading
"""
import logging
from typing import Optional, List, Dict
from decimal import Decimal
from datetime import datetime, date, timedelta
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.database_models import Order, TradingSignal, CompanyConfig

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskMetrics:
    """Metricas de riesgo calculadas"""
    var_daily: Decimal  # Value at Risk diario
    var_weekly: Decimal  # VaR semanal
    max_drawdown: Decimal  # Max drawdown actual
    current_exposure: Decimal  # Exposicion actual en USD
    exposure_pct: Decimal  # % del portafolio expuesto
    daily_pnl: Decimal  # PnL del dia
    weekly_pnl: Decimal  # PnL de la semana
    win_rate: Decimal  # Tasa de exito
    sharpe_ratio: Decimal  # Sharpe ratio
    risk_level: RiskLevel
    alerts: List[str]


@dataclass
class TradeValidation:
    """Resultado de validacion de trade"""
    approved: bool
    checks: Dict[str, bool]
    recommended_size: Decimal
    risk_level: RiskLevel
    warnings: List[str]
    block_reason: Optional[str] = None


class RiskManager:
    """
    Gestor de riesgo avanzado

    Funcionalidades:
    - Validacion de trades antes de ejecucion
    - Calculo de metricas de riesgo (VaR, Drawdown, etc)
    - Limites dinamicos basados en performance
    - Alertas de riesgo
    """

    def __init__(self):
        # Limites por defecto (90% confianza)
        self.default_config = {
            "min_confidence": Decimal(str(settings.MIN_CONFIDENCE)),  # 0.90
            "max_position_size": Decimal(str(settings.MAX_POSITION_SIZE)),  # 0.10
            "max_daily_loss": Decimal(str(settings.MAX_DAILY_LOSS)),  # 0.02
            "stop_loss_pct": Decimal(str(settings.STOP_LOSS_PCT)),  # 0.01
            "take_profit_pct": Decimal(str(settings.TAKE_PROFIT_PCT)),  # 0.03
            "max_trades_per_day": 10,
            "max_exposure_pct": Decimal("0.30"),  # 30% max exposicion
            "min_risk_reward": Decimal("2.0"),  # Risk/Reward minimo
            "max_correlation": Decimal("0.7"),  # Correlacion maxima entre posiciones
        }

    def get_company_config(self, company_id: Optional[str]) -> dict:
        """Obtener configuracion de riesgo para empresa"""
        if not company_id:
            return self.default_config

        db = SessionLocal()
        try:
            config = db.query(CompanyConfig).filter(
                CompanyConfig.company_id == company_id
            ).first()

            if config:
                return {
                    "min_confidence": config.min_confidence,
                    "max_position_size": config.max_position_size,
                    "max_daily_loss": config.max_daily_loss,
                    "stop_loss_pct": config.stop_loss_pct,
                    "take_profit_pct": config.take_profit_pct,
                    **self.default_config  # Defaults para campos no configurados
                }
            return self.default_config
        finally:
            db.close()

    def validate_trade(
        self,
        company_id: Optional[str],
        signal: TradingSignal,
        trade_amount: Decimal,
        portfolio_value: Decimal
    ) -> TradeValidation:
        """
        Validar trade antes de ejecucion

        Args:
            company_id: ID de la empresa
            signal: Senal de trading
            trade_amount: Monto del trade en COP
            portfolio_value: Valor total del portafolio

        Returns:
            TradeValidation con resultado
        """
        config = self.get_company_config(company_id)
        checks = {}
        warnings = []

        # 1. Validar confianza minima (90%)
        checks["confidence"] = signal.confidence >= config["min_confidence"]
        if not checks["confidence"]:
            warnings.append(
                f"Confianza ({signal.confidence*100:.1f}%) menor al minimo ({config['min_confidence']*100:.0f}%)"
            )

        # 2. Validar tamano de posicion
        position_size_pct = trade_amount / portfolio_value
        checks["position_size"] = position_size_pct <= config["max_position_size"]
        if not checks["position_size"]:
            warnings.append(
                f"Tamano de posicion ({position_size_pct*100:.1f}%) excede maximo ({config['max_position_size']*100:.0f}%)"
            )

        # 3. Validar perdida diaria
        daily_pnl = self._get_daily_pnl(company_id)
        daily_loss_pct = abs(min(daily_pnl, Decimal("0"))) / portfolio_value
        checks["daily_loss"] = daily_loss_pct < config["max_daily_loss"]
        if not checks["daily_loss"]:
            warnings.append(
                f"Perdida diaria ({daily_loss_pct*100:.2f}%) alcanzada. Trading suspendido."
            )

        # 4. Validar numero de trades por dia
        daily_trades = self._get_daily_trade_count(company_id)
        checks["trade_count"] = daily_trades < config.get("max_trades_per_day", 10)
        if not checks["trade_count"]:
            warnings.append("Limite de trades diarios alcanzado")

        # 5. Validar exposicion total
        current_exposure = self._get_current_exposure(company_id)
        total_exposure_pct = (current_exposure + trade_amount) / portfolio_value
        checks["exposure"] = total_exposure_pct <= config.get("max_exposure_pct", Decimal("0.30"))
        if not checks["exposure"]:
            warnings.append(
                f"Exposicion total ({total_exposure_pct*100:.1f}%) excederia limite"
            )

        # 6. Validar risk/reward
        if signal.expected_return and signal.risk_score:
            risk_reward = abs(signal.expected_return) / max(signal.risk_score, Decimal("0.01"))
            checks["risk_reward"] = risk_reward >= config.get("min_risk_reward", Decimal("2.0"))
            if not checks["risk_reward"]:
                warnings.append(f"Risk/Reward ({risk_reward:.2f}) menor al minimo (2.0)")
        else:
            checks["risk_reward"] = True

        # Calcular tamano recomendado
        recommended_size = self._calculate_recommended_size(
            portfolio_value, config, signal
        )

        # Determinar nivel de riesgo
        risk_level = self._calculate_risk_level(checks, signal)

        # Aprobar si pasa todos los checks criticos
        critical_checks = ["confidence", "daily_loss", "position_size"]
        approved = all(checks.get(c, True) for c in critical_checks)

        block_reason = None
        if not approved:
            failed = [c for c in critical_checks if not checks.get(c, True)]
            block_reason = f"Checks fallidos: {', '.join(failed)}"

        return TradeValidation(
            approved=approved,
            checks=checks,
            recommended_size=recommended_size,
            risk_level=risk_level,
            warnings=warnings,
            block_reason=block_reason
        )

    def calculate_risk_metrics(
        self,
        company_id: Optional[str],
        portfolio_value: Decimal
    ) -> RiskMetrics:
        """
        Calcular metricas de riesgo completas

        Args:
            company_id: ID de la empresa
            portfolio_value: Valor del portafolio

        Returns:
            RiskMetrics con todas las metricas
        """
        db = SessionLocal()
        alerts = []

        try:
            # Obtener ordenes recientes
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            orders = db.query(Order).filter(
                Order.company_id == company_id if company_id else True,
                Order.created_at >= thirty_days_ago
            ).all()

            # Calcular PnL
            daily_pnl = self._get_daily_pnl(company_id)
            weekly_pnl = self._get_weekly_pnl(company_id)

            # Win rate
            total_trades = len(orders)
            winning_trades = sum(1 for o in orders if self._is_profitable(o))
            win_rate = Decimal(str(winning_trades / total_trades)) if total_trades > 0 else Decimal("0")

            # Exposicion actual
            current_exposure = self._get_current_exposure(company_id)
            exposure_pct = current_exposure / portfolio_value if portfolio_value > 0 else Decimal("0")

            # VaR (simplificado - 95% CI basado en volatilidad historica)
            var_daily = portfolio_value * Decimal("0.02")  # 2% VaR diario aproximado
            var_weekly = var_daily * Decimal("2.24")  # sqrt(5) para 5 dias

            # Max drawdown (simplificado)
            max_drawdown = abs(min(weekly_pnl, Decimal("0")))

            # Sharpe ratio (simplificado)
            avg_return = weekly_pnl / portfolio_value if portfolio_value > 0 else Decimal("0")
            sharpe_ratio = avg_return * Decimal("52") / Decimal("0.15")  # Anualizado / vol estimada

            # Determinar nivel de riesgo
            risk_level = self._determine_overall_risk_level(
                exposure_pct, daily_pnl, portfolio_value, max_drawdown
            )

            # Generar alertas
            if exposure_pct > Decimal("0.25"):
                alerts.append("Exposicion alta (> 25%)")
            if daily_pnl < -portfolio_value * Decimal("0.01"):
                alerts.append("Perdida diaria significativa")
            if win_rate < Decimal("0.4"):
                alerts.append("Win rate bajo (< 40%)")

            return RiskMetrics(
                var_daily=var_daily,
                var_weekly=var_weekly,
                max_drawdown=max_drawdown,
                current_exposure=current_exposure,
                exposure_pct=exposure_pct,
                daily_pnl=daily_pnl,
                weekly_pnl=weekly_pnl,
                win_rate=win_rate,
                sharpe_ratio=sharpe_ratio,
                risk_level=risk_level,
                alerts=alerts
            )

        finally:
            db.close()

    def _get_daily_pnl(self, company_id: Optional[str]) -> Decimal:
        """Obtener PnL del dia"""
        db = SessionLocal()
        try:
            today = date.today()
            orders = db.query(Order).filter(
                Order.company_id == company_id if company_id else True,
                func.date(Order.executed_at) == today
            ).all()

            # Calcular PnL simplificado
            pnl = Decimal("0")
            # En produccion, calcular PnL real basado en precios de entrada/salida
            return pnl
        finally:
            db.close()

    def _get_weekly_pnl(self, company_id: Optional[str]) -> Decimal:
        """Obtener PnL de la semana"""
        db = SessionLocal()
        try:
            week_ago = datetime.utcnow() - timedelta(days=7)
            # Similar a daily_pnl pero para 7 dias
            return Decimal("0")
        finally:
            db.close()

    def _get_daily_trade_count(self, company_id: Optional[str]) -> int:
        """Contar trades del dia"""
        db = SessionLocal()
        try:
            today = date.today()
            count = db.query(Order).filter(
                Order.company_id == company_id if company_id else True,
                func.date(Order.created_at) == today
            ).count()
            return count
        finally:
            db.close()

    def _get_current_exposure(self, company_id: Optional[str]) -> Decimal:
        """Obtener exposicion actual en USD"""
        db = SessionLocal()
        try:
            # En produccion, sumar posiciones abiertas
            return Decimal("0")
        finally:
            db.close()

    def _calculate_recommended_size(
        self,
        portfolio_value: Decimal,
        config: dict,
        signal: TradingSignal
    ) -> Decimal:
        """Calcular tamano de posicion recomendado basado en Kelly Criterion modificado"""
        # Kelly Criterion: f = (bp - q) / b
        # Donde b = odds, p = prob win, q = 1 - p

        confidence = float(signal.confidence)
        expected_return = float(signal.expected_return) if signal.expected_return else 0.02

        # Probabilidad de exito basada en confianza
        p = confidence
        q = 1 - p

        # Odds basado en retorno esperado vs riesgo
        b = expected_return / 0.01  # Asumiendo 1% stop loss

        kelly = (b * p - q) / b if b > 0 else 0

        # Usar fraccion de Kelly (50%) para ser conservador
        half_kelly = max(0, kelly * 0.5)

        # Limitar al maximo de posicion
        max_size = float(config["max_position_size"])
        recommended_pct = min(half_kelly, max_size)

        return portfolio_value * Decimal(str(recommended_pct))

    def _calculate_risk_level(self, checks: Dict[str, bool], signal) -> RiskLevel:
        """Determinar nivel de riesgo del trade"""
        passed = sum(1 for v in checks.values() if v)
        total = len(checks)
        ratio = passed / total if total > 0 else 0

        if ratio >= 0.9 and signal.confidence >= Decimal("0.90"):
            return RiskLevel.LOW
        elif ratio >= 0.7:
            return RiskLevel.MEDIUM
        elif ratio >= 0.5:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def _determine_overall_risk_level(
        self,
        exposure_pct: Decimal,
        daily_pnl: Decimal,
        portfolio_value: Decimal,
        max_drawdown: Decimal
    ) -> RiskLevel:
        """Determinar nivel de riesgo general del portafolio"""
        if exposure_pct > Decimal("0.4") or daily_pnl < -portfolio_value * Decimal("0.03"):
            return RiskLevel.CRITICAL
        elif exposure_pct > Decimal("0.25") or daily_pnl < -portfolio_value * Decimal("0.02"):
            return RiskLevel.HIGH
        elif exposure_pct > Decimal("0.15") or daily_pnl < -portfolio_value * Decimal("0.01"):
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _is_profitable(self, order: Order) -> bool:
        """Determinar si una orden fue rentable"""
        # Simplificado - en produccion calcular basado en precios reales
        return True


# Instancia singleton
risk_manager = RiskManager()
