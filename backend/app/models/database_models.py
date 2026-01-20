"""
Modelos SQLAlchemy para la base de datos
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Boolean, DateTime, Date,
    ForeignKey, Text, JSON, Integer, Numeric, Enum
)
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class PlanType(str, enum.Enum):
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    TRADER = "trader"
    VIEWER = "viewer"


class SignalAction(str, enum.Enum):
    BUY_USD = "BUY_USD"
    SELL_USD = "SELL_USD"
    HOLD = "HOLD"


class SignalStatus(str, enum.Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


# Empresas clientes
class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    tax_id = Column(String(20), unique=True)  # NIT
    plan = Column(Enum(PlanType), default=PlanType.BASIC)
    subscription_plan = Column(String(50), default="basic")  # basic, professional, enterprise
    api_key = Column(String(100), unique=True, index=True)
    settings = Column(JSON, default={})  # Configuracion adicional
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    users = relationship("User", back_populates="company")
    signals = relationship("TradingSignal", back_populates="company")
    orders = relationship("Order", back_populates="company")
    config = relationship("CompanyConfig", back_populates="company", uselist=False)
    predictions = relationship("Prediction", back_populates="company")


# Usuarios
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"))
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(Enum(UserRole), default=UserRole.VIEWER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    # Relaciones
    company = relationship("Company", back_populates="users")


# Historico TRM
class TRMHistory(Base):
    __tablename__ = "trm_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    value = Column(Numeric(10, 2), nullable=False)
    source = Column(String(100), default="datos.gov.co")
    created_at = Column(DateTime, default=datetime.utcnow)


# Indicadores macroeconomicos
class MacroIndicator(Base):
    __tablename__ = "macro_indicators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    indicator_type = Column(String(50), nullable=False)  # oil_wti, fed_rate, etc.
    value = Column(Numeric(15, 4), nullable=False)
    source = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)


# Predicciones
class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), index=True)
    target_date = Column(Date, nullable=False, index=True)
    predicted_value = Column(Numeric(10, 2), nullable=False)
    lower_bound = Column(Numeric(10, 2))  # Intervalo de confianza
    upper_bound = Column(Numeric(10, 2))
    confidence = Column(Numeric(5, 4))
    model_version = Column(String(50))
    model_type = Column(String(50))  # prophet, lstm, ensemble
    features = Column(JSON)  # Features usadas para la prediccion
    actual_value = Column(Numeric(10, 2))  # Se llena despues para validacion
    error_pct = Column(Numeric(8, 6))  # Error porcentual (se calcula despues)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    company = relationship("Company", back_populates="predictions")


# Senales de trading
class TradingSignal(Base):
    __tablename__ = "trading_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), index=True)
    action = Column(Enum(SignalAction), nullable=False)
    confidence = Column(Numeric(5, 4), nullable=False)
    predicted_trm = Column(Numeric(10, 2), nullable=False)
    current_trm = Column(Numeric(10, 2), nullable=False)
    expected_return = Column(Numeric(8, 6))
    risk_score = Column(Numeric(5, 4))
    reasoning = Column(Text)
    status = Column(Enum(SignalStatus), default=SignalStatus.PENDING)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    company = relationship("Company", back_populates="signals")
    orders = relationship("Order", back_populates="signal")


# Ordenes ejecutadas
class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), index=True)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("trading_signals.id"))
    broker = Column(String(50))
    order_type = Column(String(20))  # market, limit
    side = Column(String(10))  # buy, sell
    amount = Column(Numeric(15, 2))
    currency = Column(String(3), default="USD")
    requested_rate = Column(Numeric(10, 2))
    executed_rate = Column(Numeric(10, 2))
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING)
    broker_order_id = Column(String(100))
    is_paper_trade = Column(Boolean, default=True)  # Paper trading por defecto
    created_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime)
    error_message = Column(Text)

    # Relaciones
    company = relationship("Company", back_populates="orders")
    signal = relationship("TradingSignal", back_populates="orders")


# Auditoria
class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(UUID(as_uuid=True))
    user_id = Column(UUID(as_uuid=True))
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50))
    entity_id = Column(UUID(as_uuid=True))
    old_value = Column(JSON)
    new_value = Column(JSON)
    ip_address = Column(INET)
    created_at = Column(DateTime, default=datetime.utcnow)


# Configuracion por empresa
class CompanyConfig(Base):
    __tablename__ = "company_config"

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), primary_key=True)
    min_confidence = Column(Numeric(5, 4), default=0.90)  # 90% confianza
    min_expected_return = Column(Numeric(8, 6), default=0.02)
    max_daily_loss = Column(Numeric(8, 6), default=0.02)
    max_position_size = Column(Numeric(8, 6), default=0.10)
    stop_loss_pct = Column(Numeric(8, 6), default=0.01)
    take_profit_pct = Column(Numeric(8, 6), default=0.03)
    auto_execute = Column(Boolean, default=False)
    enable_auto_trading = Column(Boolean, default=False)
    paper_trading = Column(Boolean, default=True)  # Paper trading por defecto
    preferred_broker = Column(String(50), default="alpaca")
    notification_channels = Column(JSON, default=["email"])
    model_settings = Column(JSON)  # Configuracion de modelos ML personalizados
    webhook_url = Column(String(500))
    telegram_chat_id = Column(String(50))
    slack_channel = Column(String(100))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    company = relationship("Company", back_populates="config")


# Resultados de backtesting
class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_name = Column(String(100), nullable=False)
    model_type = Column(String(50))
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    initial_capital = Column(Numeric(15, 2))
    final_capital = Column(Numeric(15, 2))
    total_return_pct = Column(Numeric(8, 4))
    sharpe_ratio = Column(Numeric(8, 4))
    max_drawdown_pct = Column(Numeric(8, 4))
    win_rate = Column(Numeric(5, 4))
    total_trades = Column(Integer)
    profitable_trades = Column(Integer)
    avg_trade_return = Column(Numeric(8, 6))
    parameters = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
