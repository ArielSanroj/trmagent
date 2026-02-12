"""
ATLAS - Modelos SQLAlchemy para Gestion de Riesgo Cambiario

Entidades:
- Counterparty: Proveedores/clientes
- Exposure: Exposicion cambiaria (payable/receivable)
- HedgePolicy: Politicas de cobertura
- HedgeRecommendation: Recomendaciones generadas por motor
- HedgeOrder: Ordenes de cobertura
- Quote: Cotizaciones de banco/IMC
- Trade: Operaciones confirmadas
- Settlement: Liquidaciones
"""
import uuid
import enum
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import (
    Column, String, Float, Boolean, DateTime, Date,
    ForeignKey, Text, JSON, Integer, Numeric, Enum, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


# ============================================================================
# ENUMS
# ============================================================================

class ExposureType(str, enum.Enum):
    """Tipo de exposicion cambiaria"""
    PAYABLE = "payable"      # Cuenta por pagar (compra USD)
    RECEIVABLE = "receivable"  # Cuenta por cobrar (venta USD)


class ExposureStatus(str, enum.Enum):
    """Estado de la exposicion"""
    OPEN = "open"              # Abierta, sin cubrir totalmente
    PARTIALLY_HEDGED = "partially_hedged"  # Parcialmente cubierta
    FULLY_HEDGED = "fully_hedged"  # Totalmente cubierta
    SETTLED = "settled"        # Liquidada
    CANCELLED = "cancelled"    # Cancelada


class HedgeAction(str, enum.Enum):
    """Acciones de cobertura recomendadas"""
    HEDGE_NOW = "hedge_now"         # Cubrir inmediatamente
    HEDGE_PARTIAL = "hedge_partial"  # Cobertura parcial
    WAIT = "wait"                    # Esperar mejor tasa
    REVIEW = "review"                # Requiere revision manual


class RecommendationStatus(str, enum.Enum):
    """Estado de la recomendacion"""
    PENDING = "pending"      # Pendiente de decision
    ACCEPTED = "accepted"    # Aceptada
    REJECTED = "rejected"    # Rechazada
    EXPIRED = "expired"      # Expirada sin accion


class OrderStatus(str, enum.Enum):
    """Estado de la orden de cobertura"""
    DRAFT = "draft"          # Borrador
    PENDING_APPROVAL = "pending_approval"  # Esperando aprobacion
    APPROVED = "approved"    # Aprobada
    SENT_TO_BANK = "sent_to_bank"  # Enviada al banco
    QUOTED = "quoted"        # Cotizada
    EXECUTED = "executed"    # Ejecutada
    CANCELLED = "cancelled"  # Cancelada
    REJECTED = "rejected"    # Rechazada


class TradeStatus(str, enum.Enum):
    """Estado del trade"""
    CONFIRMED = "confirmed"       # Confirmado
    PENDING_SETTLEMENT = "pending_settlement"  # Pendiente de liquidacion
    SETTLED = "settled"           # Liquidado
    FAILED = "failed"             # Fallido


class SettlementStatus(str, enum.Enum):
    """Estado de liquidacion"""
    PENDING = "pending"      # Pendiente
    PROCESSING = "processing"  # En proceso
    COMPLETED = "completed"  # Completada
    FAILED = "failed"        # Fallida


# ============================================================================
# MODELOS
# ============================================================================

class Counterparty(Base):
    """
    Proveedores y clientes con los que se tienen exposiciones cambiarias.
    """
    __tablename__ = "atlas_counterparties"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)

    # Identificacion
    name = Column(String(255), nullable=False)
    tax_id = Column(String(50))  # NIT o ID fiscal
    country = Column(String(3), default="USA")  # ISO 3166-1 alpha-3

    # Tipo y categoria
    counterparty_type = Column(String(50), default="supplier")  # supplier, customer, bank
    category = Column(String(100))  # e.g., "raw_materials", "technology", "services"

    # Contacto
    contact_name = Column(String(255))
    contact_email = Column(String(255))
    contact_phone = Column(String(50))

    # Configuracion
    default_payment_terms = Column(Integer, default=30)  # Dias por defecto
    default_currency = Column(String(3), default="USD")
    credit_limit = Column(Numeric(15, 2))

    # Metadata
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    exposures = relationship("Exposure", back_populates="counterparty")

    __table_args__ = (
        Index('ix_atlas_counterparties_company_name', 'company_id', 'name'),
    )


class Exposure(Base):
    """
    Exposicion cambiaria individual - una factura o compromiso en moneda extranjera.
    """
    __tablename__ = "atlas_exposures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    counterparty_id = Column(UUID(as_uuid=True), ForeignKey("atlas_counterparties.id"), index=True)

    # Tipo de exposicion
    exposure_type = Column(Enum(ExposureType), nullable=False)

    # Identificacion
    reference = Column(String(100), nullable=False)  # Numero de factura/PO
    description = Column(String(500))

    # Montos
    currency = Column(String(3), default="USD", nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)  # Monto en moneda extranjera
    amount_hedged = Column(Numeric(15, 2), default=0)  # Monto ya cubierto

    # Tasas
    original_rate = Column(Numeric(10, 4))  # Tasa al momento de creacion
    target_rate = Column(Numeric(10, 4))    # Tasa objetivo (opcional)
    budget_rate = Column(Numeric(10, 4))    # Tasa presupuestada

    # Fechas
    invoice_date = Column(Date)
    due_date = Column(Date, nullable=False, index=True)  # Fecha de vencimiento

    # Estado
    status = Column(Enum(ExposureStatus), default=ExposureStatus.OPEN)

    # Cobertura
    hedge_percentage = Column(Numeric(5, 2), default=0)  # % cubierto

    # Metadata
    tags = Column(JSON, default=list)  # Etiquetas para categorizar
    source = Column(String(50), default="manual")  # manual, csv_upload, erp_sync
    external_id = Column(String(100))  # ID en sistema externo
    notes = Column(Text)

    # Auditoria
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    counterparty = relationship("Counterparty", back_populates="exposures")
    recommendations = relationship("HedgeRecommendation", back_populates="exposure")
    orders = relationship("HedgeOrder", back_populates="exposure")

    __table_args__ = (
        Index('ix_atlas_exposures_company_due_date', 'company_id', 'due_date'),
        Index('ix_atlas_exposures_company_status', 'company_id', 'status'),
    )

    @property
    def amount_open(self) -> Decimal:
        """Monto sin cubrir"""
        return self.amount - (self.amount_hedged or Decimal(0))

    @property
    def days_to_maturity(self) -> int:
        """Dias hasta el vencimiento"""
        if not self.due_date:
            return 0
        delta = self.due_date - date.today()
        return max(0, delta.days)


class HedgePolicy(Base):
    """
    Politica de cobertura - reglas para cuando y cuanto cubrir.
    Ejemplo: 0-30 dias = 100%, 31-60 dias = 75%, etc.
    """
    __tablename__ = "atlas_hedge_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)

    # Identificacion
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Aplicacion
    exposure_type = Column(Enum(ExposureType))  # NULL = aplica a ambos
    currency = Column(String(3), default="USD")
    counterparty_category = Column(String(100))  # NULL = todas las categorias

    # Reglas de cobertura por horizonte
    # Estructura: {"0-30": 100, "31-60": 75, "61-90": 50, "91+": 25}
    coverage_rules = Column(JSON, nullable=False, default={
        "0-30": 100,
        "31-60": 75,
        "61-90": 50,
        "91+": 25
    })

    # Limites
    min_amount = Column(Numeric(15, 2), default=0)  # Monto minimo para aplicar
    max_single_exposure = Column(Numeric(15, 2))  # Maximo por exposicion

    # Condiciones de mercado
    rate_tolerance_up = Column(Numeric(5, 2), default=2.0)    # % sobre TRM actual
    rate_tolerance_down = Column(Numeric(5, 2), default=2.0)  # % bajo TRM actual

    # Configuracion
    auto_generate_recommendations = Column(Boolean, default=True)
    require_approval_above = Column(Numeric(15, 2))  # Monto que requiere aprobacion

    # Estado
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # Politica por defecto
    priority = Column(Integer, default=100)  # Menor = mayor prioridad

    # Auditoria
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('ix_atlas_hedge_policies_company_active', 'company_id', 'is_active'),
    )


class HedgeRecommendation(Base):
    """
    Recomendacion de cobertura generada por el Policy Engine.
    """
    __tablename__ = "atlas_hedge_recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    exposure_id = Column(UUID(as_uuid=True), ForeignKey("atlas_exposures.id"), index=True)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("atlas_hedge_policies.id"))

    # Recomendacion
    action = Column(Enum(HedgeAction), nullable=False)

    # Montos
    currency = Column(String(3), default="USD")
    amount_to_hedge = Column(Numeric(15, 2), nullable=False)
    current_coverage = Column(Numeric(5, 2))  # % actual
    target_coverage = Column(Numeric(5, 2))   # % objetivo

    # Tasas
    current_rate = Column(Numeric(10, 4))    # TRM al generar
    suggested_rate = Column(Numeric(10, 4))  # Tasa sugerida

    # Prioridad y urgencia
    priority = Column(Integer, default=50)  # 0-100, mayor = mas urgente
    urgency = Column(String(20), default="normal")  # low, normal, high, critical
    days_to_maturity = Column(Integer)

    # Justificacion
    reasoning = Column(Text)
    factors = Column(JSON)  # Factores considerados
    confidence = Column(Numeric(5, 2))  # Confianza 0-100

    # Estado
    status = Column(Enum(RecommendationStatus), default=RecommendationStatus.PENDING)

    # Fechas
    valid_until = Column(DateTime)
    decided_at = Column(DateTime)
    decided_by = Column(UUID(as_uuid=True))

    # Metadata
    rejection_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    exposure = relationship("Exposure", back_populates="recommendations")
    orders = relationship("HedgeOrder", back_populates="recommendation")

    __table_args__ = (
        Index('ix_atlas_recommendations_company_status', 'company_id', 'status'),
        Index('ix_atlas_recommendations_company_created', 'company_id', 'created_at'),
    )


class HedgeOrder(Base):
    """
    Orden de cobertura - instruccion para ejecutar una operacion FX.
    """
    __tablename__ = "atlas_hedge_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    exposure_id = Column(UUID(as_uuid=True), ForeignKey("atlas_exposures.id"), index=True)
    recommendation_id = Column(UUID(as_uuid=True), ForeignKey("atlas_hedge_recommendations.id"))

    # Tipo de operacion
    order_type = Column(String(20), default="spot")  # spot, forward, ndf
    side = Column(String(10), nullable=False)  # buy, sell

    # Montos
    currency = Column(String(3), default="USD")
    amount = Column(Numeric(15, 2), nullable=False)

    # Tasas
    target_rate = Column(Numeric(10, 4))       # Tasa objetivo
    limit_rate = Column(Numeric(10, 4))        # Tasa limite
    market_rate_at_creation = Column(Numeric(10, 4))  # TRM al crear

    # Para forwards
    settlement_date = Column(Date)  # Fecha de liquidacion

    # Estado
    status = Column(Enum(OrderStatus), default=OrderStatus.DRAFT)

    # Aprobacion
    requires_approval = Column(Boolean, default=False)
    approved_by = Column(UUID(as_uuid=True))
    approved_at = Column(DateTime)

    # Ejecucion
    bank_reference = Column(String(100))  # Referencia del banco
    executed_at = Column(DateTime)

    # Metadata
    notes = Column(Text)
    internal_reference = Column(String(100))

    # Auditoria
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    exposure = relationship("Exposure", back_populates="orders")
    recommendation = relationship("HedgeRecommendation", back_populates="orders")
    quotes = relationship("Quote", back_populates="order")
    trades = relationship("Trade", back_populates="order")

    __table_args__ = (
        Index('ix_atlas_orders_company_status', 'company_id', 'status'),
    )


class Quote(Base):
    """
    Cotizacion recibida de un banco o IMC para una orden.
    """
    __tablename__ = "atlas_quotes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("atlas_hedge_orders.id"), nullable=False, index=True)

    # Banco/Proveedor
    provider = Column(String(100), nullable=False)  # Nombre del banco/IMC
    provider_reference = Column(String(100))

    # Cotizacion
    bid_rate = Column(Numeric(10, 4))    # Tasa de compra
    ask_rate = Column(Numeric(10, 4))    # Tasa de venta
    mid_rate = Column(Numeric(10, 4))    # Tasa media
    spread = Column(Numeric(6, 4))       # Spread

    # Monto cotizado
    amount = Column(Numeric(15, 2))
    currency = Column(String(3), default="USD")

    # Validez
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_until = Column(DateTime)

    # Estado
    is_accepted = Column(Boolean, default=False)
    is_expired = Column(Boolean, default=False)

    # Metadata
    raw_response = Column(JSON)  # Respuesta completa del banco
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    order = relationship("HedgeOrder", back_populates="quotes")


class Trade(Base):
    """
    Operacion FX confirmada/ejecutada.
    """
    __tablename__ = "atlas_trades"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("atlas_hedge_orders.id"), index=True)
    quote_id = Column(UUID(as_uuid=True), ForeignKey("atlas_quotes.id"))

    # Tipo de operacion
    trade_type = Column(String(20), default="spot")  # spot, forward, ndf
    side = Column(String(10), nullable=False)  # buy, sell

    # Montos
    currency_sold = Column(String(3), nullable=False)
    amount_sold = Column(Numeric(15, 2), nullable=False)
    currency_bought = Column(String(3), nullable=False)
    amount_bought = Column(Numeric(15, 2), nullable=False)

    # Tasa
    executed_rate = Column(Numeric(10, 4), nullable=False)

    # Contraparte
    counterparty_bank = Column(String(100))
    bank_reference = Column(String(100))

    # Fechas
    trade_date = Column(Date, nullable=False)
    value_date = Column(Date, nullable=False)  # Fecha de liquidacion

    # Estado
    status = Column(Enum(TradeStatus), default=TradeStatus.CONFIRMED)

    # Metadata
    confirmation_number = Column(String(100))
    notes = Column(Text)

    # Auditoria
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    order = relationship("HedgeOrder", back_populates="trades")
    settlements = relationship("Settlement", back_populates="trade")

    __table_args__ = (
        Index('ix_atlas_trades_company_trade_date', 'company_id', 'trade_date'),
    )


class Settlement(Base):
    """
    Liquidacion de una operacion FX.
    """
    __tablename__ = "atlas_settlements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trade_id = Column(UUID(as_uuid=True), ForeignKey("atlas_trades.id"), nullable=False, index=True)

    # Liquidacion
    settlement_date = Column(Date, nullable=False)

    # Montos
    currency = Column(String(3), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)

    # Cuentas
    from_account = Column(String(100))
    to_account = Column(String(100))

    # Estado
    status = Column(Enum(SettlementStatus), default=SettlementStatus.PENDING)

    # Referencias
    payment_reference = Column(String(100))
    bank_confirmation = Column(String(100))

    # Fechas
    processed_at = Column(DateTime)
    confirmed_at = Column(DateTime)

    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    trade = relationship("Trade", back_populates="settlements")
