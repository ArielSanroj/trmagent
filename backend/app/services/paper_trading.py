"""
Modulo de Paper Trading
Simula operaciones de trading sin dinero real
Para probar estrategias antes de ir a produccion
"""
from datetime import datetime, timedelta
from typing import Optional, List
from decimal import Decimal
from dataclasses import dataclass, field
from uuid import UUID, uuid4
import logging

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.config import settings
from app.models.database_models import Order, OrderStatus, TradingSignal
from app.services.decision_engine import TradingDecision
from app.models.database_models import SignalAction

logger = logging.getLogger(__name__)


@dataclass
class PaperPosition:
    """Posicion simulada en paper trading"""
    id: UUID = field(default_factory=uuid4)
    currency: str = "USD"
    amount: Decimal = Decimal("0")
    avg_entry_rate: Decimal = Decimal("0")
    current_rate: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PaperPortfolio:
    """Portafolio simulado"""
    company_id: Optional[UUID] = None
    usd_balance: Decimal = Decimal("0")
    cop_balance: Decimal = Decimal("100000000")  # 100M COP inicial
    positions: List[PaperPosition] = field(default_factory=list)
    total_trades: int = 0
    profitable_trades: int = 0
    total_pnl: Decimal = Decimal("0")
    created_at: datetime = field(default_factory=datetime.utcnow)


class PaperTradingService:
    """
    Servicio de Paper Trading
    Simula operaciones sin usar dinero real
    """

    def __init__(self):
        # Portafolios en memoria (en produccion usar Redis o BD)
        self.portfolios: dict[str, PaperPortfolio] = {}

    def get_or_create_portfolio(
        self,
        company_id: Optional[UUID] = None,
        initial_cop: Decimal = Decimal("100000000")
    ) -> PaperPortfolio:
        """Obtener o crear portafolio de paper trading"""
        key = str(company_id) if company_id else "default"

        if key not in self.portfolios:
            self.portfolios[key] = PaperPortfolio(
                company_id=company_id,
                cop_balance=initial_cop
            )

        return self.portfolios[key]

    def execute_paper_trade(
        self,
        decision: TradingDecision,
        amount_cop: Decimal,
        company_id: Optional[UUID] = None
    ) -> dict:
        """
        Ejecutar trade en paper trading

        Args:
            decision: Decision de trading
            amount_cop: Monto en COP a operar
            company_id: ID de la empresa

        Returns:
            Resultado de la operacion
        """
        portfolio = self.get_or_create_portfolio(company_id)

        if decision.action == SignalAction.HOLD:
            return {
                "success": False,
                "reason": "No action for HOLD signal",
                "order_id": None
            }

        current_trm = decision.current_trm

        if decision.action == SignalAction.BUY_USD:
            return self._buy_usd(portfolio, amount_cop, current_trm, decision)
        elif decision.action == SignalAction.SELL_USD:
            return self._sell_usd(portfolio, amount_cop, current_trm, decision)

        return {"success": False, "reason": "Invalid action"}

    def _buy_usd(
        self,
        portfolio: PaperPortfolio,
        amount_cop: Decimal,
        rate: Decimal,
        decision: TradingDecision
    ) -> dict:
        """Comprar USD con COP"""
        # Verificar fondos
        if portfolio.cop_balance < amount_cop:
            return {
                "success": False,
                "reason": f"Fondos insuficientes. Balance: ${portfolio.cop_balance:,.2f} COP",
                "order_id": None
            }

        # Calcular USD a comprar
        usd_amount = amount_cop / rate

        # Ejecutar
        portfolio.cop_balance -= amount_cop
        portfolio.usd_balance += usd_amount
        portfolio.total_trades += 1

        # Crear registro de orden
        order_id = self._save_paper_order(
            company_id=portfolio.company_id,
            decision=decision,
            side="buy",
            amount=usd_amount,
            rate=rate,
            is_paper=True
        )

        logger.info(
            f"Paper Trade: BUY {usd_amount:,.2f} USD @ {rate:,.2f} "
            f"= {amount_cop:,.2f} COP"
        )

        return {
            "success": True,
            "order_id": order_id,
            "side": "buy",
            "usd_amount": usd_amount,
            "cop_amount": amount_cop,
            "rate": rate,
            "new_usd_balance": portfolio.usd_balance,
            "new_cop_balance": portfolio.cop_balance
        }

    def _sell_usd(
        self,
        portfolio: PaperPortfolio,
        amount_cop: Decimal,
        rate: Decimal,
        decision: TradingDecision
    ) -> dict:
        """Vender USD por COP"""
        # Calcular USD a vender
        usd_to_sell = amount_cop / rate

        # Verificar fondos
        if portfolio.usd_balance < usd_to_sell:
            return {
                "success": False,
                "reason": f"USD insuficientes. Balance: ${portfolio.usd_balance:,.2f} USD",
                "order_id": None
            }

        # Ejecutar
        portfolio.usd_balance -= usd_to_sell
        portfolio.cop_balance += amount_cop
        portfolio.total_trades += 1

        # Crear registro de orden
        order_id = self._save_paper_order(
            company_id=portfolio.company_id,
            decision=decision,
            side="sell",
            amount=usd_to_sell,
            rate=rate,
            is_paper=True
        )

        logger.info(
            f"Paper Trade: SELL {usd_to_sell:,.2f} USD @ {rate:,.2f} "
            f"= {amount_cop:,.2f} COP"
        )

        return {
            "success": True,
            "order_id": order_id,
            "side": "sell",
            "usd_amount": usd_to_sell,
            "cop_amount": amount_cop,
            "rate": rate,
            "new_usd_balance": portfolio.usd_balance,
            "new_cop_balance": portfolio.cop_balance
        }

    def _save_paper_order(
        self,
        company_id: Optional[UUID],
        decision: TradingDecision,
        side: str,
        amount: Decimal,
        rate: Decimal,
        is_paper: bool = True
    ) -> Optional[UUID]:
        """Guardar orden de paper trading en BD"""
        db = SessionLocal()
        try:
            order = Order(
                company_id=company_id,
                broker="paper_trading",
                order_type="market",
                side=side,
                amount=amount,
                currency="USD",
                requested_rate=rate,
                executed_rate=rate,
                status=OrderStatus.FILLED,
                is_paper_trade=is_paper,
                executed_at=datetime.utcnow()
            )
            db.add(order)
            db.commit()
            db.refresh(order)
            return order.id

        except Exception as e:
            logger.error(f"Error saving paper order: {e}")
            db.rollback()
            return None
        finally:
            db.close()

    def get_portfolio_summary(
        self,
        company_id: Optional[UUID] = None,
        current_trm: Optional[Decimal] = None
    ) -> dict:
        """
        Obtener resumen del portafolio de paper trading

        Args:
            company_id: ID de la empresa
            current_trm: TRM actual para calcular valor

        Returns:
            Resumen del portafolio
        """
        portfolio = self.get_or_create_portfolio(company_id)

        # Si no se provee TRM, usar 4200 como default
        trm = current_trm or Decimal("4200")

        # Calcular valor total en COP
        usd_value_cop = portfolio.usd_balance * trm
        total_value_cop = portfolio.cop_balance + usd_value_cop

        # Calcular PnL (asumiendo capital inicial de 100M COP)
        initial_capital = Decimal("100000000")
        total_pnl = total_value_cop - initial_capital
        pnl_pct = (total_pnl / initial_capital) * 100

        return {
            "company_id": str(portfolio.company_id) if portfolio.company_id else None,
            "usd_balance": float(portfolio.usd_balance),
            "cop_balance": float(portfolio.cop_balance),
            "usd_value_cop": float(usd_value_cop),
            "total_value_cop": float(total_value_cop),
            "total_pnl": float(total_pnl),
            "pnl_pct": float(pnl_pct),
            "total_trades": portfolio.total_trades,
            "profitable_trades": portfolio.profitable_trades,
            "win_rate": (
                portfolio.profitable_trades / portfolio.total_trades * 100
                if portfolio.total_trades > 0 else 0
            ),
            "current_trm": float(trm),
            "created_at": portfolio.created_at.isoformat()
        }

    def reset_portfolio(self, company_id: Optional[UUID] = None) -> bool:
        """Resetear portafolio de paper trading"""
        key = str(company_id) if company_id else "default"

        if key in self.portfolios:
            del self.portfolios[key]
            logger.info(f"Paper trading portfolio reset for {key}")
            return True

        return False

    def get_trade_history(
        self,
        company_id: Optional[UUID] = None,
        limit: int = 50
    ) -> List[dict]:
        """Obtener historial de trades de paper trading"""
        db = SessionLocal()
        try:
            query = db.query(Order).filter(Order.is_paper_trade == True)

            if company_id:
                query = query.filter(Order.company_id == company_id)

            orders = query.order_by(Order.created_at.desc()).limit(limit).all()

            return [
                {
                    "id": str(o.id),
                    "side": o.side,
                    "amount": float(o.amount),
                    "rate": float(o.executed_rate) if o.executed_rate else None,
                    "status": o.status.value,
                    "created_at": o.created_at.isoformat(),
                    "executed_at": o.executed_at.isoformat() if o.executed_at else None
                }
                for o in orders
            ]

        finally:
            db.close()


# Instancia singleton
paper_trading_service = PaperTradingService()
