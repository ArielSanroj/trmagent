"""
Broker Integration Service
Integracion con Interactive Brokers y Alpaca para ejecucion de ordenes
"""
import logging
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod

from app.core.config import settings

logger = logging.getLogger(__name__)

# Intentar importar librerias de brokers
try:
    from ib_insync import IB, Forex, MarketOrder, LimitOrder
    IBKR_AVAILABLE = True
except ImportError:
    IBKR_AVAILABLE = False
    logger.warning("ib_insync not installed. Install with: pip install ib_insync")

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    logger.warning("alpaca-py not installed. Install with: pip install alpaca-py")


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderSideEnum(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class BrokerOrder:
    """Orden de broker estandarizada"""
    order_id: str
    broker: str
    symbol: str
    side: OrderSideEnum
    quantity: Decimal
    order_type: OrderType
    limit_price: Optional[Decimal] = None
    filled_quantity: Decimal = Decimal("0")
    filled_price: Optional[Decimal] = None
    status: str = "pending"
    created_at: datetime = None
    executed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class BaseBroker(ABC):
    """Clase base abstracta para brokers"""

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def get_account_balance(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: OrderSideEnum,
        quantity: Decimal,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[Decimal] = None
    ) -> BrokerOrder:
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> BrokerOrder:
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass


class IBKRBroker(BaseBroker):
    """Interactive Brokers integration"""

    def __init__(self):
        self.host = settings.IBKR_HOST
        self.port = settings.IBKR_PORT
        self.client_id = 1
        self.ib = None
        self.connected = False

    def connect(self) -> bool:
        if not IBKR_AVAILABLE:
            logger.error("IBKR library not available")
            return False

        try:
            self.ib = IB()
            self.ib.connect(self.host, self.port, clientId=self.client_id)
            self.connected = True
            logger.info(f"Connected to IBKR at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            return False

    def disconnect(self) -> None:
        if self.ib and self.connected:
            self.ib.disconnect()
            self.connected = False
            logger.info("Disconnected from IBKR")

    def get_account_balance(self) -> Dict[str, Any]:
        if not self.connected:
            return {"error": "Not connected"}

        try:
            account_values = self.ib.accountSummary()
            balances = {}
            for av in account_values:
                if av.tag in ["TotalCashValue", "NetLiquidation", "BuyingPower"]:
                    balances[av.tag] = float(av.value)
            return balances
        except Exception as e:
            logger.error(f"Error getting IBKR balance: {e}")
            return {"error": str(e)}

    def place_order(
        self,
        symbol: str,
        side: OrderSideEnum,
        quantity: Decimal,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[Decimal] = None
    ) -> BrokerOrder:
        if not self.connected:
            return BrokerOrder(
                order_id="",
                broker="ibkr",
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                status="error",
                error_message="Not connected to IBKR"
            )

        try:
            # Crear contrato forex
            contract = Forex(symbol)  # e.g., "USDCOP"

            # Crear orden
            action = "BUY" if side == OrderSideEnum.BUY else "SELL"

            if order_type == OrderType.MARKET:
                order = MarketOrder(action, float(quantity))
            else:
                order = LimitOrder(action, float(quantity), float(limit_price))

            # Enviar orden
            trade = self.ib.placeOrder(contract, order)
            self.ib.sleep(1)  # Esperar confirmacion

            return BrokerOrder(
                order_id=str(trade.order.orderId),
                broker="ibkr",
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                status=trade.orderStatus.status,
                filled_quantity=Decimal(str(trade.orderStatus.filled)),
                filled_price=Decimal(str(trade.orderStatus.avgFillPrice)) if trade.orderStatus.avgFillPrice else None,
                created_at=datetime.now()
            )

        except Exception as e:
            logger.error(f"Error placing IBKR order: {e}")
            return BrokerOrder(
                order_id="",
                broker="ibkr",
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                status="error",
                error_message=str(e)
            )

    def get_order_status(self, order_id: str) -> BrokerOrder:
        # Implementar obtencion de estado de orden
        pass

    def cancel_order(self, order_id: str) -> bool:
        # Implementar cancelacion de orden
        pass


class AlpacaBroker(BaseBroker):
    """Alpaca Markets integration (Paper Trading compatible)"""

    def __init__(self, paper: bool = True):
        self.api_key = settings.ALPACA_API_KEY
        self.secret_key = settings.ALPACA_SECRET_KEY
        self.paper = paper if settings.ALPACA_PAPER else paper
        self.client = None
        self.connected = False

    def connect(self) -> bool:
        if not ALPACA_AVAILABLE:
            logger.error("Alpaca library not available")
            return False

        if not self.api_key or not self.secret_key:
            logger.error("Alpaca API keys not configured")
            return False

        try:
            self.client = TradingClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=self.paper
            )
            # Verificar conexion
            account = self.client.get_account()
            self.connected = True
            logger.info(f"Connected to Alpaca ({'Paper' if self.paper else 'Live'})")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            return False

    def disconnect(self) -> None:
        self.client = None
        self.connected = False
        logger.info("Disconnected from Alpaca")

    def get_account_balance(self) -> Dict[str, Any]:
        if not self.connected:
            return {"error": "Not connected"}

        try:
            account = self.client.get_account()
            return {
                "equity": float(account.equity),
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "portfolio_value": float(account.portfolio_value)
            }
        except Exception as e:
            logger.error(f"Error getting Alpaca balance: {e}")
            return {"error": str(e)}

    def place_order(
        self,
        symbol: str,
        side: OrderSideEnum,
        quantity: Decimal,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[Decimal] = None
    ) -> BrokerOrder:
        if not self.connected:
            return BrokerOrder(
                order_id="",
                broker="alpaca",
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                status="error",
                error_message="Not connected to Alpaca"
            )

        try:
            order_side = OrderSide.BUY if side == OrderSideEnum.BUY else OrderSide.SELL

            if order_type == OrderType.MARKET:
                request = MarketOrderRequest(
                    symbol=symbol,
                    qty=float(quantity),
                    side=order_side,
                    time_in_force=TimeInForce.DAY
                )
            else:
                request = LimitOrderRequest(
                    symbol=symbol,
                    qty=float(quantity),
                    side=order_side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=float(limit_price)
                )

            order = self.client.submit_order(request)

            return BrokerOrder(
                order_id=str(order.id),
                broker="alpaca",
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                status=order.status,
                filled_quantity=Decimal(str(order.filled_qty)) if order.filled_qty else Decimal("0"),
                filled_price=Decimal(str(order.filled_avg_price)) if order.filled_avg_price else None,
                created_at=order.created_at
            )

        except Exception as e:
            logger.error(f"Error placing Alpaca order: {e}")
            return BrokerOrder(
                order_id="",
                broker="alpaca",
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                status="error",
                error_message=str(e)
            )

    def get_order_status(self, order_id: str) -> BrokerOrder:
        try:
            order = self.client.get_order_by_id(order_id)
            return BrokerOrder(
                order_id=str(order.id),
                broker="alpaca",
                symbol=order.symbol,
                side=OrderSideEnum.BUY if order.side == "buy" else OrderSideEnum.SELL,
                quantity=Decimal(str(order.qty)),
                order_type=OrderType.MARKET if order.type == "market" else OrderType.LIMIT,
                status=order.status,
                filled_quantity=Decimal(str(order.filled_qty)) if order.filled_qty else Decimal("0"),
                filled_price=Decimal(str(order.filled_avg_price)) if order.filled_avg_price else None
            )
        except Exception as e:
            logger.error(f"Error getting order status: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        try:
            self.client.cancel_order_by_id(order_id)
            return True
        except Exception as e:
            logger.error(f"Error canceling order: {e}")
            return False


class BrokerService:
    """
    Servicio unificado de brokers
    Abstrae la logica de conexion y ejecucion
    """

    def __init__(self):
        self.brokers: Dict[str, BaseBroker] = {}

    def register_broker(self, name: str, broker: BaseBroker) -> None:
        """Registrar un broker"""
        self.brokers[name] = broker

    def get_broker(self, name: str) -> Optional[BaseBroker]:
        """Obtener broker por nombre"""
        return self.brokers.get(name)

    def connect_all(self) -> Dict[str, bool]:
        """Conectar todos los brokers registrados"""
        results = {}
        for name, broker in self.brokers.items():
            results[name] = broker.connect()
        return results

    def disconnect_all(self) -> None:
        """Desconectar todos los brokers"""
        for broker in self.brokers.values():
            broker.disconnect()

    def execute_trade(
        self,
        broker_name: str,
        symbol: str,
        side: OrderSideEnum,
        quantity: Decimal,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[Decimal] = None
    ) -> BrokerOrder:
        """
        Ejecutar trade en un broker especifico
        """
        broker = self.get_broker(broker_name)
        if not broker:
            return BrokerOrder(
                order_id="",
                broker=broker_name,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                status="error",
                error_message=f"Broker {broker_name} not found"
            )

        return broker.place_order(symbol, side, quantity, order_type, limit_price)


# Instancia singleton
broker_service = BrokerService()

# Registrar brokers disponibles
if IBKR_AVAILABLE:
    broker_service.register_broker("ibkr", IBKRBroker())
if ALPACA_AVAILABLE:
    broker_service.register_broker("alpaca", AlpacaBroker(paper=True))
