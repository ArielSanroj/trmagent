"""
ATLAS - Order Orchestrator
Gestion del ciclo de vida de ordenes de cobertura.
"""
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID
import uuid as uuid_module

from sqlalchemy.orm import Session

from app.atlas.models.atlas_models import (
    HedgeOrder,
    HedgeRecommendation,
    Exposure,
    Quote,
    Trade,
    OrderStatus,
    RecommendationStatus,
    ExposureStatus,
    TradeStatus,
    ExposureType,
)
from app.atlas.models.schemas import (
    HedgeOrderCreate,
    HedgeOrderUpdate,
    QuoteCreate,
    TradeCreate,
)

logger = logging.getLogger(__name__)


class OrderOrchestrator:
    """
    Orquestador de ordenes de cobertura.

    Maneja el flujo completo:
    1. Creacion de orden (desde recomendacion o manual)
    2. Workflow de aprobacion
    3. Solicitud de cotizaciones
    4. Ejecucion del trade
    5. Actualizacion de exposicion
    """

    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # Order CRUD
    # =========================================================================

    def create_order(
        self,
        company_id: UUID,
        data: HedgeOrderCreate,
        created_by: Optional[UUID] = None,
        current_rate: Optional[Decimal] = None,
    ) -> HedgeOrder:
        """Crear nueva orden de cobertura"""
        # Determinar si requiere aprobacion
        requires_approval = self._check_approval_required(
            company_id, data.amount
        )

        order = HedgeOrder(
            company_id=company_id,
            exposure_id=data.exposure_id,
            recommendation_id=data.recommendation_id,
            order_type=data.order_type,
            side=data.side,
            currency=data.currency,
            amount=data.amount,
            target_rate=data.target_rate,
            limit_rate=data.limit_rate,
            market_rate_at_creation=current_rate,
            settlement_date=data.settlement_date,
            status=OrderStatus.PENDING_APPROVAL if requires_approval else OrderStatus.APPROVED,
            requires_approval=requires_approval,
            internal_reference=self._generate_reference(),
            notes=data.notes,
            created_by=created_by,
        )

        # Si viene de una recomendacion, actualizarla
        if data.recommendation_id:
            recommendation = self.db.query(HedgeRecommendation).filter(
                HedgeRecommendation.id == data.recommendation_id
            ).first()
            if recommendation:
                recommendation.status = RecommendationStatus.ACCEPTED
                recommendation.decided_at = datetime.utcnow()
                recommendation.decided_by = created_by

        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        logger.info(f"Created order {order.id} ({order.internal_reference})")
        return order

    def create_from_recommendation(
        self,
        recommendation_id: UUID,
        company_id: UUID,
        created_by: Optional[UUID] = None,
        current_rate: Optional[Decimal] = None,
        **overrides
    ) -> Optional[HedgeOrder]:
        """Crear orden desde una recomendacion"""
        recommendation = self.db.query(HedgeRecommendation).filter(
            HedgeRecommendation.id == recommendation_id,
            HedgeRecommendation.company_id == company_id
        ).first()

        if not recommendation:
            logger.warning(f"Recommendation {recommendation_id} not found")
            return None

        if recommendation.status != RecommendationStatus.PENDING:
            logger.warning(
                f"Cannot create order from recommendation {recommendation_id}: "
                f"status is {recommendation.status}"
            )
            return None

        # Determinar side basado en tipo de exposicion
        exposure = recommendation.exposure
        if exposure:
            side = "buy" if exposure.exposure_type == ExposureType.PAYABLE else "sell"
        else:
            side = overrides.get('side', 'buy')

        data = HedgeOrderCreate(
            exposure_id=recommendation.exposure_id,
            recommendation_id=recommendation_id,
            order_type=overrides.get('order_type', 'spot'),
            side=side,
            currency=recommendation.currency,
            amount=overrides.get('amount', recommendation.amount_to_hedge),
            target_rate=overrides.get('target_rate', recommendation.suggested_rate),
            settlement_date=overrides.get('settlement_date'),
        )

        return self.create_order(
            company_id=company_id,
            data=data,
            created_by=created_by,
            current_rate=current_rate,
        )

    def get_order(
        self,
        order_id: UUID,
        company_id: UUID
    ) -> Optional[HedgeOrder]:
        """Obtener orden por ID"""
        return self.db.query(HedgeOrder).filter(
            HedgeOrder.id == order_id,
            HedgeOrder.company_id == company_id
        ).first()

    def list_orders(
        self,
        company_id: UUID,
        status: Optional[OrderStatus] = None,
        exposure_id: Optional[UUID] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[HedgeOrder]:
        """Listar ordenes con filtros"""
        query = self.db.query(HedgeOrder).filter(
            HedgeOrder.company_id == company_id
        )

        if status:
            query = query.filter(HedgeOrder.status == status)
        if exposure_id:
            query = query.filter(HedgeOrder.exposure_id == exposure_id)
        if from_date:
            query = query.filter(HedgeOrder.created_at >= from_date)
        if to_date:
            query = query.filter(HedgeOrder.created_at <= to_date)

        return query.order_by(
            HedgeOrder.created_at.desc()
        ).offset(skip).limit(limit).all()

    def update_order(
        self,
        order_id: UUID,
        company_id: UUID,
        data: HedgeOrderUpdate
    ) -> Optional[HedgeOrder]:
        """Actualizar orden"""
        order = self.get_order(order_id, company_id)
        if not order:
            return None

        # Solo actualizable si esta en draft o pending_approval
        if order.status not in [OrderStatus.DRAFT, OrderStatus.PENDING_APPROVAL]:
            logger.warning(
                f"Cannot update order {order_id}: status is {order.status}"
            )
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(order, field, value)

        order.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(order)
        return order

    # =========================================================================
    # Approval Workflow
    # =========================================================================

    def approve_order(
        self,
        order_id: UUID,
        company_id: UUID,
        approved_by: UUID
    ) -> Optional[HedgeOrder]:
        """Aprobar orden"""
        order = self.get_order(order_id, company_id)
        if not order:
            return None

        if order.status != OrderStatus.PENDING_APPROVAL:
            logger.warning(
                f"Cannot approve order {order_id}: status is {order.status}"
            )
            return None

        order.status = OrderStatus.APPROVED
        order.approved_by = approved_by
        order.approved_at = datetime.utcnow()
        order.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(order)
        logger.info(f"Order {order_id} approved by {approved_by}")
        return order

    def reject_order(
        self,
        order_id: UUID,
        company_id: UUID,
        reason: Optional[str] = None
    ) -> Optional[HedgeOrder]:
        """Rechazar orden"""
        order = self.get_order(order_id, company_id)
        if not order:
            return None

        if order.status != OrderStatus.PENDING_APPROVAL:
            logger.warning(
                f"Cannot reject order {order_id}: status is {order.status}"
            )
            return None

        order.status = OrderStatus.REJECTED
        order.notes = (order.notes or "") + f"\nRejected: {reason}" if reason else order.notes
        order.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(order)
        logger.info(f"Order {order_id} rejected")
        return order

    def cancel_order(
        self,
        order_id: UUID,
        company_id: UUID,
        reason: Optional[str] = None
    ) -> Optional[HedgeOrder]:
        """Cancelar orden"""
        order = self.get_order(order_id, company_id)
        if not order:
            return None

        # Solo cancelable si no ejecutada
        if order.status in [OrderStatus.EXECUTED]:
            logger.warning(
                f"Cannot cancel order {order_id}: already executed"
            )
            return None

        order.status = OrderStatus.CANCELLED
        order.notes = (order.notes or "") + f"\nCancelled: {reason}" if reason else order.notes
        order.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(order)
        logger.info(f"Order {order_id} cancelled")
        return order

    # =========================================================================
    # Quotes
    # =========================================================================

    def add_quote(
        self,
        order_id: UUID,
        company_id: UUID,
        data: QuoteCreate
    ) -> Optional[Quote]:
        """Agregar cotizacion a una orden"""
        order = self.get_order(order_id, company_id)
        if not order:
            return None

        # Calcular spread si hay bid y ask
        spread = None
        if data.bid_rate and data.ask_rate:
            spread = data.ask_rate - data.bid_rate

        quote = Quote(
            order_id=order_id,
            provider=data.provider,
            provider_reference=data.provider_reference,
            bid_rate=data.bid_rate,
            ask_rate=data.ask_rate,
            mid_rate=data.mid_rate,
            spread=spread,
            amount=data.amount or order.amount,
            currency=data.currency,
            valid_until=data.valid_until,
            raw_response=data.raw_response,
        )

        # Actualizar estado de orden
        if order.status == OrderStatus.APPROVED:
            order.status = OrderStatus.QUOTED
            order.updated_at = datetime.utcnow()

        self.db.add(quote)
        self.db.commit()
        self.db.refresh(quote)
        logger.info(f"Added quote from {data.provider} to order {order_id}")
        return quote

    def accept_quote(
        self,
        quote_id: UUID,
        order_id: UUID,
        company_id: UUID
    ) -> Optional[Quote]:
        """Aceptar una cotizacion"""
        order = self.get_order(order_id, company_id)
        if not order:
            return None

        quote = self.db.query(Quote).filter(
            Quote.id == quote_id,
            Quote.order_id == order_id
        ).first()

        if not quote:
            return None

        # Verificar que no esta expirada
        if quote.valid_until and quote.valid_until < datetime.utcnow():
            quote.is_expired = True
            self.db.commit()
            logger.warning(f"Quote {quote_id} is expired")
            return None

        quote.is_accepted = True
        self.db.commit()
        self.db.refresh(quote)
        logger.info(f"Quote {quote_id} accepted")
        return quote

    # =========================================================================
    # Execution
    # =========================================================================

    def execute_order(
        self,
        order_id: UUID,
        company_id: UUID,
        trade_data: TradeCreate,
        executed_by: Optional[UUID] = None
    ) -> Optional[Trade]:
        """
        Ejecutar orden - crear trade y actualizar exposicion.
        """
        order = self.get_order(order_id, company_id)
        if not order:
            return None

        # Verificar estado
        if order.status not in [OrderStatus.APPROVED, OrderStatus.QUOTED]:
            logger.warning(
                f"Cannot execute order {order_id}: status is {order.status}"
            )
            return None

        # Crear trade
        trade = Trade(
            company_id=company_id,
            order_id=order_id,
            quote_id=trade_data.quote_id,
            trade_type=trade_data.trade_type,
            side=trade_data.side,
            currency_sold=trade_data.currency_sold,
            amount_sold=trade_data.amount_sold,
            currency_bought=trade_data.currency_bought,
            amount_bought=trade_data.amount_bought,
            executed_rate=trade_data.executed_rate,
            counterparty_bank=trade_data.counterparty_bank,
            bank_reference=trade_data.bank_reference,
            trade_date=trade_data.trade_date,
            value_date=trade_data.value_date,
            status=TradeStatus.CONFIRMED,
            confirmation_number=trade_data.confirmation_number,
            notes=trade_data.notes,
            created_by=executed_by,
        )

        # Actualizar orden
        order.status = OrderStatus.EXECUTED
        order.executed_at = datetime.utcnow()
        order.bank_reference = trade_data.bank_reference
        order.updated_at = datetime.utcnow()

        # Actualizar exposicion si existe
        if order.exposure_id:
            self._update_exposure_hedge(
                exposure_id=order.exposure_id,
                hedged_amount=order.amount
            )

        self.db.add(trade)
        self.db.commit()
        self.db.refresh(trade)
        logger.info(f"Executed order {order_id} -> trade {trade.id}")
        return trade

    def _update_exposure_hedge(
        self,
        exposure_id: UUID,
        hedged_amount: Decimal
    ):
        """Actualizar monto cubierto de exposicion"""
        exposure = self.db.query(Exposure).filter(
            Exposure.id == exposure_id
        ).first()

        if not exposure:
            return

        current_hedged = exposure.amount_hedged or Decimal("0")
        new_hedged = current_hedged + hedged_amount
        exposure.amount_hedged = min(new_hedged, exposure.amount)
        exposure.hedge_percentage = (
            exposure.amount_hedged / exposure.amount * 100
            if exposure.amount > 0 else Decimal("0")
        )

        # Actualizar estado
        if exposure.amount_hedged >= exposure.amount:
            exposure.status = ExposureStatus.FULLY_HEDGED
        else:
            exposure.status = ExposureStatus.PARTIALLY_HEDGED

        exposure.updated_at = datetime.utcnow()

    # =========================================================================
    # Helpers
    # =========================================================================

    def _check_approval_required(
        self,
        company_id: UUID,
        amount: Decimal
    ) -> bool:
        """Verificar si la orden requiere aprobacion"""
        # Por defecto, ordenes > 100,000 USD requieren aprobacion
        # TODO: Leer de configuracion de la empresa
        threshold = Decimal("100000")
        return amount >= threshold

    def _generate_reference(self) -> str:
        """Generar referencia interna unica"""
        now = datetime.utcnow()
        return f"ORD-{now.strftime('%Y%m%d')}-{uuid_module.uuid4().hex[:8].upper()}"

    def get_order_summary(self, company_id: UUID) -> Dict[str, Any]:
        """Obtener resumen de ordenes"""
        base_query = self.db.query(HedgeOrder).filter(
            HedgeOrder.company_id == company_id
        )

        summary = {
            "total": base_query.count(),
            "by_status": {},
            "pending_approval_amount": Decimal("0"),
            "executed_today": 0,
        }

        for status in OrderStatus:
            count = base_query.filter(
                HedgeOrder.status == status
            ).count()
            summary["by_status"][status.value] = count

        # Monto pendiente de aprobacion
        pending = base_query.filter(
            HedgeOrder.status == OrderStatus.PENDING_APPROVAL
        ).all()
        summary["pending_approval_amount"] = float(
            sum(o.amount for o in pending)
        )

        # Ejecutadas hoy
        today = date.today()
        summary["executed_today"] = base_query.filter(
            HedgeOrder.status == OrderStatus.EXECUTED,
            HedgeOrder.executed_at >= datetime.combine(today, datetime.min.time())
        ).count()

        return summary
