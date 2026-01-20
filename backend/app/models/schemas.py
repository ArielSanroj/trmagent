"""
Schemas Pydantic para validacion de datos y API
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal


# ============ AUTH ============

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    company_id: Optional[UUID] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    company_id: Optional[UUID]
    is_active: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ============ COMPANY ============

class CompanyCreate(BaseModel):
    name: str
    tax_id: Optional[str] = None
    plan: Literal["basic", "pro", "enterprise"] = "basic"


class CompanyResponse(BaseModel):
    id: UUID
    name: str
    tax_id: Optional[str]
    plan: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============ TRM / MARKET DATA ============

class TRMCurrent(BaseModel):
    date: date
    value: Decimal
    change_pct: Optional[Decimal] = None
    source: str


class TRMHistoryItem(BaseModel):
    date: date
    value: Decimal

    class Config:
        from_attributes = True


class TRMHistoryResponse(BaseModel):
    data: List[TRMHistoryItem]
    count: int
    from_date: date
    to_date: date


class MarketIndicators(BaseModel):
    trm_current: Decimal
    oil_wti: Optional[Decimal] = None
    oil_brent: Optional[Decimal] = None
    fed_rate: Optional[Decimal] = None
    banrep_rate: Optional[Decimal] = None
    inflation_col: Optional[Decimal] = None
    inflation_usa: Optional[Decimal] = None
    updated_at: datetime


# ============ PREDICTIONS ============

class PredictionRequest(BaseModel):
    days_ahead: int = Field(default=30, ge=1, le=90)
    model_type: Literal["prophet", "lstm", "ensemble"] = "ensemble"


class PredictionResponse(BaseModel):
    id: UUID
    target_date: date
    predicted_value: Decimal
    lower_bound: Optional[Decimal]
    upper_bound: Optional[Decimal]
    confidence: Decimal
    model_type: str
    trend: Literal["ALCISTA", "BAJISTA", "NEUTRAL"]
    created_at: datetime

    class Config:
        from_attributes = True


class PredictionForecast(BaseModel):
    predictions: List[PredictionResponse]
    summary: dict


# ============ TRADING SIGNALS ============

class TradingSignalResponse(BaseModel):
    id: UUID
    action: Literal["BUY_USD", "SELL_USD", "HOLD"]
    confidence: Decimal
    predicted_trm: Decimal
    current_trm: Decimal
    expected_return: Decimal
    risk_score: Decimal
    reasoning: str
    status: str
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class SignalEvaluation(BaseModel):
    signal: TradingSignalResponse
    recommendation: str
    alerts_sent: bool


# ============ ORDERS ============

class OrderCreate(BaseModel):
    signal_id: Optional[UUID] = None
    side: Literal["buy", "sell"]
    amount: Decimal = Field(..., gt=0)
    order_type: Literal["market", "limit"] = "market"
    limit_price: Optional[Decimal] = None
    is_paper_trade: bool = True


class OrderResponse(BaseModel):
    id: UUID
    signal_id: Optional[UUID]
    broker: str
    order_type: str
    side: str
    amount: Decimal
    requested_rate: Optional[Decimal]
    executed_rate: Optional[Decimal]
    status: str
    is_paper_trade: bool
    created_at: datetime
    executed_at: Optional[datetime]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class PortfolioSummary(BaseModel):
    total_usd: Decimal
    total_cop: Decimal
    total_value_cop: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    daily_pnl: Decimal
    open_positions: int


# ============ CONFIG ============

class TradingConfigUpdate(BaseModel):
    min_confidence: Optional[Decimal] = Field(None, ge=0.5, le=1.0)
    min_expected_return: Optional[Decimal] = Field(None, ge=0.001, le=0.1)
    max_daily_loss: Optional[Decimal] = Field(None, ge=0.001, le=0.1)
    max_position_size: Optional[Decimal] = Field(None, ge=0.01, le=0.5)
    stop_loss_pct: Optional[Decimal] = Field(None, ge=0.001, le=0.05)
    take_profit_pct: Optional[Decimal] = Field(None, ge=0.01, le=0.1)
    auto_execute: Optional[bool] = None
    paper_trading: Optional[bool] = None


class TradingConfigResponse(BaseModel):
    min_confidence: Decimal
    min_expected_return: Decimal
    max_daily_loss: Decimal
    max_position_size: Decimal
    stop_loss_pct: Decimal
    take_profit_pct: Decimal
    auto_execute: bool
    paper_trading: bool

    class Config:
        from_attributes = True


class AlertConfigUpdate(BaseModel):
    webhook_url: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    slack_channel: Optional[str] = None


# ============ BACKTESTING ============

class BacktestRequest(BaseModel):
    strategy: Literal["momentum", "mean_reversion", "ml_signal"] = "ml_signal"
    model_type: Literal["prophet", "lstm", "ensemble"] = "ensemble"
    start_date: date
    end_date: date
    initial_capital: Decimal = Field(default=100000, gt=0)
    min_confidence: Decimal = Field(default=0.90, ge=0.5, le=1.0)


class BacktestResponse(BaseModel):
    id: UUID
    strategy_name: str
    model_type: str
    start_date: date
    end_date: date
    initial_capital: Decimal
    final_capital: Decimal
    total_return_pct: Decimal
    sharpe_ratio: Decimal
    max_drawdown_pct: Decimal
    win_rate: Decimal
    total_trades: int
    profitable_trades: int
    avg_trade_return: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


# ============ WEBHOOKS ============

class WebhookRegister(BaseModel):
    url: str
    events: List[Literal["signal.generated", "order.executed", "alert.triggered", "prediction.updated"]]
    secret: Optional[str] = None


class WebhookResponse(BaseModel):
    id: UUID
    url: str
    events: List[str]
    is_active: bool
    created_at: datetime
