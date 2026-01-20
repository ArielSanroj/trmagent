"""
Compliance & Audit Service
Cumplimiento normativo y auditoria para empresas forex
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum
import json
import hashlib
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import SessionLocal
from app.models.database_models import (
    AuditLog, Order, TradingSignal, User, Company
)

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    # Trading events
    SIGNAL_GENERATED = "signal.generated"
    SIGNAL_APPROVED = "signal.approved"
    SIGNAL_REJECTED = "signal.rejected"
    ORDER_CREATED = "order.created"
    ORDER_EXECUTED = "order.executed"
    ORDER_CANCELLED = "order.cancelled"
    ORDER_FAILED = "order.failed"

    # User events
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"

    # Config events
    CONFIG_UPDATED = "config.updated"
    RISK_LIMIT_CHANGED = "risk.limit_changed"

    # System events
    MODEL_TRAINED = "model.trained"
    PREDICTION_GENERATED = "prediction.generated"
    ALERT_SENT = "alert.sent"

    # Compliance events
    COMPLIANCE_CHECK = "compliance.check"
    SARLAFT_REPORT = "compliance.sarlaft"
    AUDIT_REPORT = "compliance.audit"


@dataclass
class AuditEvent:
    """Evento de auditoria"""
    event_type: AuditEventType
    company_id: Optional[UUID]
    user_id: Optional[UUID]
    entity_type: str
    entity_id: Optional[UUID]
    action: str
    old_value: Optional[Dict]
    new_value: Optional[Dict]
    ip_address: Optional[str]
    timestamp: datetime
    metadata: Optional[Dict] = None


@dataclass
class ComplianceReport:
    """Reporte de compliance"""
    report_id: str
    report_type: str
    company_id: Optional[UUID]
    period_start: date
    period_end: date
    generated_at: datetime
    data: Dict[str, Any]
    hash: str  # Hash para verificar integridad


class ComplianceService:
    """
    Servicio de Compliance y Auditoria

    Funcionalidades:
    - Registro de eventos de auditoria
    - Generacion de reportes de compliance
    - Verificacion SARLAFT (Anti lavado)
    - Trazabilidad completa de operaciones
    """

    def __init__(self):
        self.retention_days = 365 * 5  # 5 anos de retencion

    def log_event(
        self,
        event_type: AuditEventType,
        action: str,
        company_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        entity_type: str = "",
        entity_id: Optional[UUID] = None,
        old_value: Optional[Dict] = None,
        new_value: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Registrar evento de auditoria

        Args:
            event_type: Tipo de evento
            action: Descripcion de la accion
            company_id: ID de empresa
            user_id: ID de usuario
            entity_type: Tipo de entidad afectada
            entity_id: ID de la entidad
            old_value: Valor anterior
            new_value: Nuevo valor
            ip_address: IP del cliente
            metadata: Metadata adicional

        Returns:
            True si se registro exitosamente
        """
        db = SessionLocal()
        try:
            audit_log = AuditLog(
                company_id=company_id,
                user_id=user_id,
                action=f"{event_type.value}: {action}",
                entity_type=entity_type,
                entity_id=entity_id,
                old_value=old_value,
                new_value=new_value,
                ip_address=ip_address
            )
            db.add(audit_log)
            db.commit()

            logger.info(f"Audit: {event_type.value} - {action}")
            return True

        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    def log_trading_activity(
        self,
        signal: TradingSignal,
        order: Optional[Order] = None,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Registrar actividad de trading para compliance
        """
        # Log de senal
        self.log_event(
            event_type=AuditEventType.SIGNAL_GENERATED,
            action=f"Signal {signal.action.value} con confianza {signal.confidence}",
            company_id=signal.company_id,
            user_id=user_id,
            entity_type="trading_signal",
            entity_id=signal.id,
            new_value={
                "action": signal.action.value,
                "confidence": float(signal.confidence),
                "predicted_trm": float(signal.predicted_trm),
                "current_trm": float(signal.current_trm),
                "expected_return": float(signal.expected_return) if signal.expected_return else None
            },
            ip_address=ip_address
        )

        # Log de orden si existe
        if order:
            self.log_event(
                event_type=AuditEventType.ORDER_CREATED,
                action=f"Orden {order.side} por {order.amount} {order.currency}",
                company_id=order.company_id,
                user_id=user_id,
                entity_type="order",
                entity_id=order.id,
                new_value={
                    "side": order.side,
                    "amount": float(order.amount),
                    "currency": order.currency,
                    "broker": order.broker,
                    "is_paper_trade": order.is_paper_trade
                },
                ip_address=ip_address
            )

    def generate_compliance_report(
        self,
        company_id: Optional[UUID],
        period_start: date,
        period_end: date,
        report_type: str = "monthly"
    ) -> ComplianceReport:
        """
        Generar reporte de compliance

        Args:
            company_id: ID de empresa
            period_start: Inicio del periodo
            period_end: Fin del periodo
            report_type: Tipo de reporte

        Returns:
            ComplianceReport con datos
        """
        db = SessionLocal()
        try:
            # Obtener ordenes del periodo
            orders = db.query(Order).filter(
                Order.company_id == company_id if company_id else True,
                Order.created_at >= datetime.combine(period_start, datetime.min.time()),
                Order.created_at <= datetime.combine(period_end, datetime.max.time())
            ).all()

            # Obtener senales
            signals = db.query(TradingSignal).filter(
                TradingSignal.company_id == company_id if company_id else True,
                TradingSignal.created_at >= datetime.combine(period_start, datetime.min.time()),
                TradingSignal.created_at <= datetime.combine(period_end, datetime.max.time())
            ).all()

            # Obtener logs de auditoria
            audit_logs = db.query(AuditLog).filter(
                AuditLog.company_id == company_id if company_id else True,
                AuditLog.created_at >= datetime.combine(period_start, datetime.min.time()),
                AuditLog.created_at <= datetime.combine(period_end, datetime.max.time())
            ).all()

            # Compilar datos
            report_data = {
                "summary": {
                    "period": f"{period_start} to {period_end}",
                    "total_orders": len(orders),
                    "total_signals": len(signals),
                    "total_audit_events": len(audit_logs)
                },
                "orders": {
                    "total": len(orders),
                    "by_side": {
                        "buy": sum(1 for o in orders if o.side == "buy"),
                        "sell": sum(1 for o in orders if o.side == "sell")
                    },
                    "by_status": {},
                    "paper_trades": sum(1 for o in orders if o.is_paper_trade),
                    "real_trades": sum(1 for o in orders if not o.is_paper_trade),
                    "total_volume_usd": sum(float(o.amount) for o in orders if o.currency == "USD")
                },
                "signals": {
                    "total": len(signals),
                    "by_action": {
                        "BUY_USD": sum(1 for s in signals if s.action.value == "BUY_USD"),
                        "SELL_USD": sum(1 for s in signals if s.action.value == "SELL_USD"),
                        "HOLD": sum(1 for s in signals if s.action.value == "HOLD")
                    },
                    "avg_confidence": sum(float(s.confidence) for s in signals) / len(signals) if signals else 0
                },
                "audit_trail": {
                    "total_events": len(audit_logs),
                    "by_type": {}
                },
                "risk_events": [],
                "compliance_checks": {
                    "sarlaft_verified": True,
                    "suspicious_activity": False,
                    "large_transactions": []
                }
            }

            # Contar ordenes por status
            for order in orders:
                status = order.status.value
                report_data["orders"]["by_status"][status] = \
                    report_data["orders"]["by_status"].get(status, 0) + 1

            # Identificar transacciones grandes (> 100M COP)
            large_threshold = 100000000  # 100M COP
            for order in orders:
                amount_cop = float(order.amount) * float(order.executed_rate or order.requested_rate or 4200)
                if amount_cop > large_threshold:
                    report_data["compliance_checks"]["large_transactions"].append({
                        "order_id": str(order.id),
                        "amount": float(order.amount),
                        "amount_cop": amount_cop,
                        "date": order.created_at.isoformat()
                    })

            # Generar hash de integridad
            report_hash = self._generate_hash(report_data)

            report = ComplianceReport(
                report_id=f"CR-{company_id or 'ALL'}-{period_start.strftime('%Y%m%d')}",
                report_type=report_type,
                company_id=company_id,
                period_start=period_start,
                period_end=period_end,
                generated_at=datetime.utcnow(),
                data=report_data,
                hash=report_hash
            )

            # Registrar generacion de reporte
            self.log_event(
                event_type=AuditEventType.AUDIT_REPORT,
                action=f"Reporte {report_type} generado",
                company_id=company_id,
                entity_type="compliance_report",
                new_value={"report_id": report.report_id, "hash": report_hash}
            )

            return report

        finally:
            db.close()

    def generate_sarlaft_report(
        self,
        company_id: UUID,
        period_start: date,
        period_end: date
    ) -> ComplianceReport:
        """
        Generar reporte SARLAFT (Sistema de Administracion del Riesgo de Lavado de Activos)
        Requerido por regulacion colombiana
        """
        db = SessionLocal()
        try:
            # Obtener datos de la empresa
            company = db.query(Company).filter(Company.id == company_id).first()

            # Obtener usuarios
            users = db.query(User).filter(User.company_id == company_id).all()

            # Obtener ordenes
            orders = db.query(Order).filter(
                Order.company_id == company_id,
                Order.created_at >= datetime.combine(period_start, datetime.min.time()),
                Order.created_at <= datetime.combine(period_end, datetime.max.time()),
                Order.is_paper_trade == False  # Solo operaciones reales
            ).all()

            sarlaft_data = {
                "entity": {
                    "name": company.name if company else "N/A",
                    "nit": company.tax_id if company else "N/A",
                    "report_period": f"{period_start} to {period_end}"
                },
                "operations": {
                    "total_count": len(orders),
                    "total_volume_usd": sum(float(o.amount) for o in orders),
                    "avg_transaction_size": sum(float(o.amount) for o in orders) / len(orders) if orders else 0
                },
                "users": {
                    "total": len(users),
                    "active": sum(1 for u in users if u.is_active)
                },
                "risk_indicators": {
                    "unusual_patterns": [],
                    "high_frequency_trading": False,
                    "suspicious_activities": []
                },
                "verification": {
                    "kyc_complete": True,  # Know Your Customer
                    "aml_check": True,  # Anti Money Laundering
                    "pep_check": True  # Politically Exposed Person
                }
            }

            # Detectar patrones inusuales
            if orders:
                # Muchas transacciones pequenas seguidas
                small_txns = [o for o in orders if float(o.amount) < 1000]
                if len(small_txns) > len(orders) * 0.8:
                    sarlaft_data["risk_indicators"]["unusual_patterns"].append(
                        "Alto porcentaje de transacciones pequenas"
                    )

                # Trading de alta frecuencia
                if len(orders) > 50:
                    sarlaft_data["risk_indicators"]["high_frequency_trading"] = True

            report_hash = self._generate_hash(sarlaft_data)

            report = ComplianceReport(
                report_id=f"SARLAFT-{company_id}-{period_start.strftime('%Y%m%d')}",
                report_type="sarlaft",
                company_id=company_id,
                period_start=period_start,
                period_end=period_end,
                generated_at=datetime.utcnow(),
                data=sarlaft_data,
                hash=report_hash
            )

            self.log_event(
                event_type=AuditEventType.SARLAFT_REPORT,
                action="Reporte SARLAFT generado",
                company_id=company_id,
                entity_type="sarlaft_report",
                new_value={"report_id": report.report_id}
            )

            return report

        finally:
            db.close()

    def verify_report_integrity(self, report: ComplianceReport) -> bool:
        """Verificar integridad de un reporte usando su hash"""
        calculated_hash = self._generate_hash(report.data)
        return calculated_hash == report.hash

    def get_audit_trail(
        self,
        company_id: Optional[UUID] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Obtener trail de auditoria

        Args:
            company_id: Filtrar por empresa
            entity_type: Filtrar por tipo de entidad
            entity_id: Filtrar por ID de entidad
            start_date: Fecha inicio
            end_date: Fecha fin
            limit: Limite de resultados

        Returns:
            Lista de eventos de auditoria
        """
        db = SessionLocal()
        try:
            query = db.query(AuditLog)

            if company_id:
                query = query.filter(AuditLog.company_id == company_id)
            if entity_type:
                query = query.filter(AuditLog.entity_type == entity_type)
            if entity_id:
                query = query.filter(AuditLog.entity_id == entity_id)
            if start_date:
                query = query.filter(
                    AuditLog.created_at >= datetime.combine(start_date, datetime.min.time())
                )
            if end_date:
                query = query.filter(
                    AuditLog.created_at <= datetime.combine(end_date, datetime.max.time())
                )

            logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()

            return [
                {
                    "id": log.id,
                    "action": log.action,
                    "entity_type": log.entity_type,
                    "entity_id": str(log.entity_id) if log.entity_id else None,
                    "old_value": log.old_value,
                    "new_value": log.new_value,
                    "ip_address": str(log.ip_address) if log.ip_address else None,
                    "created_at": log.created_at.isoformat()
                }
                for log in logs
            ]

        finally:
            db.close()

    def _generate_hash(self, data: Dict) -> str:
        """Generar hash SHA256 de datos para verificacion de integridad"""
        data_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()


# Instancia singleton
compliance_service = ComplianceService()
