"""
ATLAS - Settlement Service
Gestion de liquidaciones de operaciones FX.
"""
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.atlas.models.atlas_models import (
    Settlement,
    Trade,
    Exposure,
    SettlementStatus,
    TradeStatus,
    ExposureStatus,
)
from app.atlas.models.schemas import SettlementCreate, SettlementUpdate
from app.atlas.services.settlement_reporting import (
    build_settlement_calendar,
    build_settlement_summary,
)

logger = logging.getLogger(__name__)


class SettlementService:
    """Servicio para gestion de liquidaciones"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        data: SettlementCreate
    ) -> Settlement:
        """Crear nueva liquidacion"""
        settlement = Settlement(
            trade_id=data.trade_id,
            settlement_date=data.settlement_date,
            currency=data.currency,
            amount=data.amount,
            from_account=data.from_account,
            to_account=data.to_account,
            payment_reference=data.payment_reference,
            notes=data.notes,
            status=SettlementStatus.PENDING,
        )
        self.db.add(settlement)
        self.db.commit()
        self.db.refresh(settlement)
        logger.info(f"Created settlement {settlement.id} for trade {data.trade_id}")
        return settlement

    def create_from_trade(self, trade: Trade) -> List[Settlement]:
        """Crear liquidaciones automaticas desde un trade"""
        settlements = []

        # Liquidacion de moneda vendida
        settlement_sold = Settlement(
            trade_id=trade.id,
            settlement_date=trade.value_date,
            currency=trade.currency_sold,
            amount=trade.amount_sold,
            status=SettlementStatus.PENDING,
        )
        settlements.append(settlement_sold)

        # Liquidacion de moneda comprada
        settlement_bought = Settlement(
            trade_id=trade.id,
            settlement_date=trade.value_date,
            currency=trade.currency_bought,
            amount=trade.amount_bought,
            status=SettlementStatus.PENDING,
        )
        settlements.append(settlement_bought)

        for s in settlements:
            self.db.add(s)

        self.db.commit()
        for s in settlements:
            self.db.refresh(s)

        logger.info(f"Created {len(settlements)} settlements for trade {trade.id}")
        return settlements

    def get(self, settlement_id: UUID) -> Optional[Settlement]:
        """Obtener liquidacion por ID"""
        return self.db.query(Settlement).filter(
            Settlement.id == settlement_id
        ).first()

    def list_for_trade(self, trade_id: UUID) -> List[Settlement]:
        """Listar liquidaciones de un trade"""
        return self.db.query(Settlement).filter(
            Settlement.trade_id == trade_id
        ).order_by(Settlement.settlement_date).all()

    def list_pending(
        self,
        company_id: UUID,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> List[Settlement]:
        """Listar liquidaciones pendientes"""
        query = self.db.query(Settlement).join(
            Trade, Settlement.trade_id == Trade.id
        ).filter(
            Trade.company_id == company_id,
            Settlement.status.in_([
                SettlementStatus.PENDING,
                SettlementStatus.PROCESSING
            ])
        )

        if from_date:
            query = query.filter(Settlement.settlement_date >= from_date)
        if to_date:
            query = query.filter(Settlement.settlement_date <= to_date)

        return query.order_by(Settlement.settlement_date).all()

    def list_by_date(
        self,
        company_id: UUID,
        settlement_date: date
    ) -> List[Settlement]:
        """Listar liquidaciones por fecha"""
        return self.db.query(Settlement).join(
            Trade, Settlement.trade_id == Trade.id
        ).filter(
            Trade.company_id == company_id,
            Settlement.settlement_date == settlement_date
        ).all()

    def update(
        self,
        settlement_id: UUID,
        data: SettlementUpdate
    ) -> Optional[Settlement]:
        """Actualizar liquidacion"""
        settlement = self.get(settlement_id)
        if not settlement:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(settlement, field, value)

        self.db.commit()
        self.db.refresh(settlement)
        return settlement

    def mark_processing(self, settlement_id: UUID) -> Optional[Settlement]:
        """Marcar liquidacion como en proceso"""
        settlement = self.get(settlement_id)
        if not settlement:
            return None

        settlement.status = SettlementStatus.PROCESSING
        settlement.processed_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(settlement)
        logger.info(f"Settlement {settlement_id} marked as processing")
        return settlement

    def mark_completed(
        self,
        settlement_id: UUID,
        bank_confirmation: Optional[str] = None
    ) -> Optional[Settlement]:
        """Marcar liquidacion como completada"""
        settlement = self.get(settlement_id)
        if not settlement:
            return None

        settlement.status = SettlementStatus.COMPLETED
        settlement.confirmed_at = datetime.utcnow()
        if bank_confirmation:
            settlement.bank_confirmation = bank_confirmation

        # Actualizar trade si todas las liquidaciones estan completas
        self._check_trade_settlement(settlement.trade_id)

        self.db.commit()
        self.db.refresh(settlement)
        logger.info(f"Settlement {settlement_id} completed")
        return settlement

    def mark_failed(
        self,
        settlement_id: UUID,
        reason: Optional[str] = None
    ) -> Optional[Settlement]:
        """Marcar liquidacion como fallida"""
        settlement = self.get(settlement_id)
        if not settlement:
            return None

        settlement.status = SettlementStatus.FAILED
        if reason:
            settlement.notes = (settlement.notes or "") + f"\nFailed: {reason}"

        self.db.commit()
        self.db.refresh(settlement)
        logger.warning(f"Settlement {settlement_id} failed: {reason}")
        return settlement

    def _check_trade_settlement(self, trade_id: UUID):
        """Verificar si el trade esta completamente liquidado"""
        settlements = self.list_for_trade(trade_id)
        all_completed = all(
            s.status == SettlementStatus.COMPLETED for s in settlements
        )

        if all_completed:
            trade = self.db.query(Trade).filter(Trade.id == trade_id).first()
            if trade:
                trade.status = TradeStatus.SETTLED
                logger.info(f"Trade {trade_id} fully settled")

                # Actualizar exposicion asociada si existe
                if trade.order and trade.order.exposure_id:
                    exposure = self.db.query(Exposure).filter(
                        Exposure.id == trade.order.exposure_id
                    ).first()
                    if exposure and exposure.amount_hedged >= exposure.amount:
                        exposure.status = ExposureStatus.SETTLED

    def get_settlement_calendar(
        self,
        company_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        days: int = 30
    ) -> Dict[date, Dict[str, Any]]:
        return build_settlement_calendar(
            db=self.db,
            company_id=company_id,
            start_date=start_date,
            end_date=end_date,
            days=days,
        )

    def get_summary(self, company_id: UUID) -> Dict[str, Any]:
        """Obtener resumen de liquidaciones"""
        return build_settlement_summary(self.db, company_id)
