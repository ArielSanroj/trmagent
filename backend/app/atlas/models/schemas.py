"""
ATLAS - Pydantic Schemas para API
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

from .atlas_models import (
    ExposureType,
    ExposureStatus,
    HedgeAction,
    RecommendationStatus,
    OrderStatus,
    TradeStatus,
    SettlementStatus,
)


# ============================================================================
# BASE SCHEMAS
# ============================================================================

class AtlasBaseSchema(BaseModel):
    """Schema base con configuracion comun"""
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# COUNTERPARTY SCHEMAS
# ============================================================================

class CounterpartyCreate(BaseModel):
    """Crear contraparte"""
    name: str = Field(..., min_length=1, max_length=255)
    tax_id: Optional[str] = None
    country: str = Field(default="USA", max_length=3)
    counterparty_type: str = Field(default="supplier")
    category: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    default_payment_terms: int = Field(default=30, ge=0)
    default_currency: str = Field(default="USD", max_length=3)
    credit_limit: Optional[Decimal] = None
    notes: Optional[str] = None


class CounterpartyUpdate(BaseModel):
    """Actualizar contraparte"""
    name: Optional[str] = None
    tax_id: Optional[str] = None
    country: Optional[str] = None
    counterparty_type: Optional[str] = None
    category: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    default_payment_terms: Optional[int] = None
    default_currency: Optional[str] = None
    credit_limit: Optional[Decimal] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class CounterpartyResponse(AtlasBaseSchema):
    """Respuesta de contraparte"""
    id: UUID
    company_id: UUID
    name: str
    tax_id: Optional[str]
    country: str
    counterparty_type: str
    category: Optional[str]
    contact_name: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    default_payment_terms: int
    default_currency: str
    credit_limit: Optional[Decimal]
    notes: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ============================================================================
# EXPOSURE SCHEMAS
# ============================================================================

class ExposureCreate(BaseModel):
    """Crear exposicion"""
    counterparty_id: Optional[UUID] = None
    exposure_type: ExposureType
    reference: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    currency: str = Field(default="USD", max_length=3)
    amount: Decimal = Field(..., gt=0)
    original_rate: Optional[Decimal] = None
    target_rate: Optional[Decimal] = None
    budget_rate: Optional[Decimal] = None
    invoice_date: Optional[date] = None
    due_date: date
    tags: List[str] = Field(default_factory=list)
    external_id: Optional[str] = None
    notes: Optional[str] = None


class ExposureUpdate(BaseModel):
    """Actualizar exposicion"""
    counterparty_id: Optional[UUID] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    target_rate: Optional[Decimal] = None
    budget_rate: Optional[Decimal] = None
    due_date: Optional[date] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    status: Optional[ExposureStatus] = None


class ExposureResponse(AtlasBaseSchema):
    """Respuesta de exposicion"""
    id: UUID
    company_id: UUID
    counterparty_id: Optional[UUID]
    exposure_type: ExposureType
    reference: str
    description: Optional[str]
    currency: str
    amount: Decimal
    amount_hedged: Decimal
    original_rate: Optional[Decimal]
    target_rate: Optional[Decimal]
    budget_rate: Optional[Decimal]
    invoice_date: Optional[date]
    due_date: date
    status: ExposureStatus
    hedge_percentage: Decimal
    tags: List[str]
    source: str
    external_id: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    # Computed fields
    amount_open: Optional[Decimal] = None
    days_to_maturity: Optional[int] = None


class ExposureWithCounterparty(ExposureResponse):
    """Exposicion con datos de contraparte"""
    counterparty: Optional[CounterpartyResponse] = None


class ExposureSummary(BaseModel):
    """Resumen de exposiciones"""
    total_payables: Decimal = Field(default=Decimal("0"))
    total_receivables: Decimal = Field(default=Decimal("0"))
    total_hedged_payables: Decimal = Field(default=Decimal("0"))
    total_hedged_receivables: Decimal = Field(default=Decimal("0"))
    net_exposure: Decimal = Field(default=Decimal("0"))
    coverage_percentage: Decimal = Field(default=Decimal("0"))
    exposures_count: int = 0
    by_horizon: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class ExposureUploadResult(BaseModel):
    """Resultado de carga masiva"""
    total_rows: int
    created: int
    updated: int
    errors: int
    error_details: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# HEDGE POLICY SCHEMAS
# ============================================================================

class HedgePolicyCreate(BaseModel):
    """Crear politica de cobertura"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    exposure_type: Optional[ExposureType] = None
    currency: str = Field(default="USD")
    counterparty_category: Optional[str] = None
    coverage_rules: Dict[str, int] = Field(
        default={"0-30": 100, "31-60": 75, "61-90": 50, "91+": 25}
    )
    min_amount: Decimal = Field(default=Decimal("0"))
    max_single_exposure: Optional[Decimal] = None
    rate_tolerance_up: Decimal = Field(default=Decimal("2.0"))
    rate_tolerance_down: Decimal = Field(default=Decimal("2.0"))
    auto_generate_recommendations: bool = True
    require_approval_above: Optional[Decimal] = None
    is_default: bool = False
    priority: int = Field(default=100)


class HedgePolicyUpdate(BaseModel):
    """Actualizar politica"""
    name: Optional[str] = None
    description: Optional[str] = None
    exposure_type: Optional[ExposureType] = None
    counterparty_category: Optional[str] = None
    coverage_rules: Optional[Dict[str, int]] = None
    min_amount: Optional[Decimal] = None
    max_single_exposure: Optional[Decimal] = None
    rate_tolerance_up: Optional[Decimal] = None
    rate_tolerance_down: Optional[Decimal] = None
    auto_generate_recommendations: Optional[bool] = None
    require_approval_above: Optional[Decimal] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    priority: Optional[int] = None


class HedgePolicyResponse(AtlasBaseSchema):
    """Respuesta de politica"""
    id: UUID
    company_id: UUID
    name: str
    description: Optional[str]
    exposure_type: Optional[ExposureType]
    currency: str
    counterparty_category: Optional[str]
    coverage_rules: Dict[str, int]
    min_amount: Decimal
    max_single_exposure: Optional[Decimal]
    rate_tolerance_up: Decimal
    rate_tolerance_down: Decimal
    auto_generate_recommendations: bool
    require_approval_above: Optional[Decimal]
    is_active: bool
    is_default: bool
    priority: int
    created_at: datetime
    updated_at: datetime


class PolicySimulationRequest(BaseModel):
    """Solicitud de simulacion de politica"""
    policy_id: Optional[UUID] = None
    coverage_rules: Optional[Dict[str, int]] = None


class PolicySimulationResult(BaseModel):
    """Resultado de simulacion"""
    total_exposure: Decimal
    would_hedge: Decimal
    coverage_percentage: Decimal
    by_horizon: Dict[str, Dict[str, Any]]
    estimated_orders: int


# ============================================================================
# RECOMMENDATION SCHEMAS
# ============================================================================

class RecommendationGenerateRequest(BaseModel):
    """Solicitud de generacion de recomendaciones"""
    policy_id: Optional[UUID] = None
    exposure_ids: Optional[List[UUID]] = None
    include_all_open: bool = True


class RecommendationResponse(AtlasBaseSchema):
    """Respuesta de recomendacion"""
    id: UUID
    company_id: UUID
    exposure_id: Optional[UUID]
    policy_id: Optional[UUID]
    action: HedgeAction
    currency: str
    amount_to_hedge: Decimal
    current_coverage: Optional[Decimal]
    target_coverage: Optional[Decimal]
    current_rate: Optional[Decimal]
    suggested_rate: Optional[Decimal]
    priority: int
    urgency: str
    days_to_maturity: Optional[int]
    reasoning: Optional[str]
    factors: Optional[Dict[str, Any]]
    confidence: Optional[Decimal]
    status: RecommendationStatus
    valid_until: Optional[datetime]
    decided_at: Optional[datetime]
    decided_by: Optional[UUID]
    rejection_reason: Optional[str]
    created_at: datetime


class RecommendationWithExposure(RecommendationResponse):
    """Recomendacion con exposicion"""
    exposure: Optional[ExposureResponse] = None


class RecommendationDecision(BaseModel):
    """Decision sobre recomendacion"""
    rejection_reason: Optional[str] = None


class RecommendationCalendar(BaseModel):
    """Calendario de recomendaciones"""
    date: date
    recommendations: List[RecommendationResponse]
    total_amount: Decimal
    priority_breakdown: Dict[str, int]


# ============================================================================
# ORDER SCHEMAS
# ============================================================================

class HedgeOrderCreate(BaseModel):
    """Crear orden de cobertura"""
    exposure_id: Optional[UUID] = None
    recommendation_id: Optional[UUID] = None
    order_type: str = Field(default="spot")
    side: str = Field(..., pattern="^(buy|sell)$")
    currency: str = Field(default="USD")
    amount: Decimal = Field(..., gt=0)
    target_rate: Optional[Decimal] = None
    limit_rate: Optional[Decimal] = None
    settlement_date: Optional[date] = None
    notes: Optional[str] = None


class HedgeOrderUpdate(BaseModel):
    """Actualizar orden"""
    target_rate: Optional[Decimal] = None
    limit_rate: Optional[Decimal] = None
    settlement_date: Optional[date] = None
    notes: Optional[str] = None


class HedgeOrderResponse(AtlasBaseSchema):
    """Respuesta de orden"""
    id: UUID
    company_id: UUID
    exposure_id: Optional[UUID]
    recommendation_id: Optional[UUID]
    order_type: str
    side: str
    currency: str
    amount: Decimal
    target_rate: Optional[Decimal]
    limit_rate: Optional[Decimal]
    market_rate_at_creation: Optional[Decimal]
    settlement_date: Optional[date]
    status: OrderStatus
    requires_approval: bool
    approved_by: Optional[UUID]
    approved_at: Optional[datetime]
    bank_reference: Optional[str]
    executed_at: Optional[datetime]
    notes: Optional[str]
    internal_reference: Optional[str]
    created_at: datetime
    updated_at: datetime


class HedgeOrderWithDetails(HedgeOrderResponse):
    """Orden con detalles completos"""
    exposure: Optional[ExposureResponse] = None
    recommendation: Optional[RecommendationResponse] = None
    quotes: List["QuoteResponse"] = Field(default_factory=list)


# ============================================================================
# QUOTE SCHEMAS
# ============================================================================

class QuoteCreate(BaseModel):
    """Crear cotizacion"""
    provider: str = Field(..., min_length=1)
    provider_reference: Optional[str] = None
    bid_rate: Optional[Decimal] = None
    ask_rate: Optional[Decimal] = None
    mid_rate: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    currency: str = Field(default="USD")
    valid_until: Optional[datetime] = None
    raw_response: Optional[Dict[str, Any]] = None


class QuoteResponse(AtlasBaseSchema):
    """Respuesta de cotizacion"""
    id: UUID
    order_id: UUID
    provider: str
    provider_reference: Optional[str]
    bid_rate: Optional[Decimal]
    ask_rate: Optional[Decimal]
    mid_rate: Optional[Decimal]
    spread: Optional[Decimal]
    amount: Optional[Decimal]
    currency: str
    valid_from: datetime
    valid_until: Optional[datetime]
    is_accepted: bool
    is_expired: bool
    created_at: datetime


# ============================================================================
# TRADE SCHEMAS
# ============================================================================

class TradeCreate(BaseModel):
    """Crear trade"""
    order_id: Optional[UUID] = None
    quote_id: Optional[UUID] = None
    trade_type: str = Field(default="spot")
    side: str = Field(..., pattern="^(buy|sell)$")
    currency_sold: str
    amount_sold: Decimal = Field(..., gt=0)
    currency_bought: str
    amount_bought: Decimal = Field(..., gt=0)
    executed_rate: Decimal = Field(..., gt=0)
    counterparty_bank: Optional[str] = None
    bank_reference: Optional[str] = None
    trade_date: date
    value_date: date
    confirmation_number: Optional[str] = None
    notes: Optional[str] = None


class TradeResponse(AtlasBaseSchema):
    """Respuesta de trade"""
    id: UUID
    company_id: UUID
    order_id: Optional[UUID]
    quote_id: Optional[UUID]
    trade_type: str
    side: str
    currency_sold: str
    amount_sold: Decimal
    currency_bought: str
    amount_bought: Decimal
    executed_rate: Decimal
    counterparty_bank: Optional[str]
    bank_reference: Optional[str]
    trade_date: date
    value_date: date
    status: TradeStatus
    confirmation_number: Optional[str]
    notes: Optional[str]
    created_at: datetime


# ============================================================================
# SETTLEMENT SCHEMAS
# ============================================================================

class SettlementCreate(BaseModel):
    """Crear liquidacion"""
    trade_id: UUID
    settlement_date: date
    currency: str
    amount: Decimal = Field(..., gt=0)
    from_account: Optional[str] = None
    to_account: Optional[str] = None
    payment_reference: Optional[str] = None
    notes: Optional[str] = None


class SettlementUpdate(BaseModel):
    """Actualizar liquidacion"""
    status: Optional[SettlementStatus] = None
    payment_reference: Optional[str] = None
    bank_confirmation: Optional[str] = None
    notes: Optional[str] = None


class SettlementResponse(AtlasBaseSchema):
    """Respuesta de liquidacion"""
    id: UUID
    trade_id: UUID
    settlement_date: date
    currency: str
    amount: Decimal
    from_account: Optional[str]
    to_account: Optional[str]
    status: SettlementStatus
    payment_reference: Optional[str]
    bank_confirmation: Optional[str]
    processed_at: Optional[datetime]
    confirmed_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime


# ============================================================================
# REPORT SCHEMAS
# ============================================================================

class CoverageReport(BaseModel):
    """Reporte de cobertura"""
    as_of_date: date
    total_payables: Decimal
    total_receivables: Decimal
    total_hedged_payables: Decimal
    total_hedged_receivables: Decimal
    net_exposure: Decimal
    payables_coverage_pct: Decimal
    receivables_coverage_pct: Decimal
    overall_coverage_pct: Decimal
    by_currency: Dict[str, Dict[str, Decimal]]
    by_counterparty: List[Dict[str, Any]]
    by_maturity: Dict[str, Dict[str, Decimal]]


class MaturityLadder(BaseModel):
    """Escalera de vencimientos"""
    buckets: List[Dict[str, Any]]
    total_exposure: Decimal
    total_hedged: Decimal
    coverage_by_bucket: Dict[str, Decimal]


class CostAnalysis(BaseModel):
    """Analisis de costos"""
    period_start: date
    period_end: date
    total_volume_traded: Decimal
    avg_rate: Decimal
    weighted_avg_rate: Decimal
    best_rate: Decimal
    worst_rate: Decimal
    benchmark_rate: Decimal  # TRM promedio del periodo
    performance_vs_benchmark: Decimal  # % mejor/peor que benchmark
    total_cost_savings: Decimal
    by_counterparty_bank: List[Dict[str, Any]]


class ReportExportRequest(BaseModel):
    """Solicitud de exportacion"""
    report_type: str = Field(..., pattern="^(coverage|maturity|cost)$")
    format: str = Field(default="xlsx", pattern="^(xlsx|csv|pdf)$")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    include_details: bool = True


# Update forward references
HedgeOrderWithDetails.model_rebuild()
