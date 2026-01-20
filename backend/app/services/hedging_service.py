
"""
Hedging Service
Servicio de recomendaciones de cobertura y analisis de riesgo de mercado
"""
import logging
from typing import Optional, Dict, List
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import UUID
from enum import Enum
from dataclasses import dataclass

from app.core.database import SessionLocal
from app.models.database_models import CompanyConfig, Company, Prediction
from app.services.risk_management import risk_manager, RiskLevel
from app.services.notification_service import notification_service
from app.services.compliance import compliance_service, AuditEventType
from app.ml.ensemble_model import ensemble_model

logger = logging.getLogger(__name__)

class HedgingAction(str, Enum):
    IMMEDIATE_HEDGE = "IMMEDIATE_HEDGE"  # Cubrir ya
    PARTIAL_HEDGE = "PARTIAL_HEDGE"      # Cubrir parcialmente (50%)
    WAIT = "WAIT"                        # Esperar mejor tasa
    NO_ACTION = "NO_ACTION"              # Mercado estable

@dataclass
class MarketRiskScore:
    """Puntaje de riesgo de mercado (0-100)"""
    total_score: float
    volatility_score: float      # Basado en varianza de modelos
    trend_risk: float            # Basado en tendencia (si va en contra)
    macro_risk: float            # Basado en eventos macro (TODO)
    risk_level: str              # LOW, MEDIUM, HIGH, CRITICAL
    recommendation: str

@dataclass
class HedgingRecommendation:
    """Recomendacion de cobertura"""
    action: HedgingAction
    amount_to_hedge: Decimal
    suggested_rate: Decimal
    urgency: str                 # HIGH, MEDIUM, LOW
    reasoning: List[str]
    currency_pair: str = "USD/COP"
    expires_in_minutes: int = 60

class HedgingService:
    """
    Servicio B2B para recomendaciones de cobertura
    """
    
    def calculate_market_risk(self, predictions: List[dict]) -> MarketRiskScore:
        """
        Calcular score de riesgo de mercado (0-100)
        Usado para decidir si es momento de cubrirse
        """
        if not predictions:
            return MarketRiskScore(0, 0, 0, 0, "UNKNOWN", "Insufficient Data")
            
        # 1. Volatilidad de Modelos (Discrepancia entre Prophet/LSTM)
        # Si los modelos no estan de acuerdo, hay incertidumbre -> Riesgo Alto
        volatility_sum = sum(float(p.get("model_volatility", 0)) for p in predictions)
        avg_volatility = volatility_sum / len(predictions)
        
        # Normalizar volatilidad (ej. 50 pesos de std dev = 100 score)
        vol_score = min(100, (avg_volatility / 50.0) * 100)
        
        # 2. Riesgo de Tendencia
        # Si la tendencia es ALCISTA fuerte (USD sube), el riesgo para importadores es ALTO
        trend = ensemble_model.get_trend(predictions)
        trend_score = 0
        if trend == "ALCISTA":
            trend_score = 80
        elif trend == "BAJISTA":
            trend_score = 20 # Bueno para importadores
        else:
            trend_score = 40
            
        # 3. Score Total
        # 60% Tendencia, 40% Incertidumbre
        total_score = (trend_score * 0.6) + (vol_score * 0.4)
        
        # Nivel
        level = "LOW"
        if total_score > 80: level = "CRITICAL"
        elif total_score > 60: level = "HIGH"
        elif total_score > 40: level = "MEDIUM"
        
        return MarketRiskScore(
            total_score=total_score,
            volatility_score=vol_score,
            trend_risk=trend_score,
            macro_risk=0, # Placeholder
            risk_level=level,
            recommendation=self._get_recommendation_text(level, trend)
        )

    def get_hedging_recommendation(
        self,
        amount: Decimal,
        time_horizon_days: int,
        current_exposure: Decimal,
        company_id: Optional[UUID] = None
    ) -> HedgingRecommendation:
        """
        Generar recomendacion de cobertura B2B
        """
        # Obtener predicciones desde BD si existen
        db = SessionLocal()
        try:
            records = db.query(Prediction).filter(
                Prediction.target_date >= datetime.utcnow().date(),
                Prediction.target_date <= datetime.utcnow().date() + timedelta(days=time_horizon_days)
            ).order_by(Prediction.target_date.asc()).all()
        finally:
            db.close()

        if records:
            predictions = [{"predicted_value": float(r.predicted_value), "model_volatility": 0} for r in records]
        else:
            predictions = ensemble_model.predict([], days_ahead=time_horizon_days)
        risk_score = self.calculate_market_risk(predictions)
        
        current_trm = Decimal("4100") # TODO: Get real current TRM
        if predictions:
            predicted_trm = Decimal(str(predictions[0]["predicted_value"]))
        else:
            predicted_trm = current_trm

        reasons = []
        action = HedgingAction.WAIT
        hedge_amount = Decimal("0")
        urgency = "LOW"
        
        # Logica de decision
        if risk_score.risk_level in ["CRITICAL", "HIGH"]:
            action = HedgingAction.IMMEDIATE_HEDGE
            urgency = "HIGH"
            hedge_amount = amount # Cubrir todo
            reasons.append(f"Riesgo de mercado ALTO ({risk_score.total_score:.1f}/100).")
            reasons.append(f"Tendencia detectada: {ensemble_model.get_trend(predictions)}.")
            reasons.append("Alta volatilidad entre modelos predictivos.")
            
        elif risk_score.risk_level == "MEDIUM":
            action = HedgingAction.PARTIAL_HEDGE
            urgency = "MEDIUM"
            hedge_amount = amount * Decimal("0.5")
            reasons.append("Riesgo moderado. Se sugiere cobertura parcial.")
            
        else:
            action = HedgingAction.WAIT
            reasons.append("Mercado estable o favorable. Esperar mejor tasa.")

        # Auditoria B2B
        if company_id:
            compliance_service.log_event(
                event_type=AuditEventType.PREDICTION_GENERATED, # Reusing event type
                action=f"Hedging Recommendation: {action}",
                company_id=company_id,
                entity_type="hedging_recommendation",
                new_value={
                    "amount": str(amount),
                    "action": action,
                    "risk_score": risk_score.total_score
                }
            )

        return HedgingRecommendation(
            action=action,
            amount_to_hedge=hedge_amount,
            suggested_rate=predicted_trm, # Precio objetivo
            urgency=urgency,
            reasoning=reasons
        )

    def subscribe_webhook(self, company_id: UUID, webhook_url: str) -> bool:
        """Actualizar webhook de la empresa"""
        db = SessionLocal()
        try:
            config = db.query(CompanyConfig).filter(CompanyConfig.company_id == company_id).first()
            if not config:
                # Crear config si no existe
                config = CompanyConfig(company_id=company_id)
                db.add(config)
            
            old_url = config.webhook_url
            config.webhook_url = webhook_url
            db.commit()
            
            # Log audit
            compliance_service.log_event(
                event_type=AuditEventType.CONFIG_UPDATED,
                action="Webhook URL updated",
                company_id=company_id,
                old_value={"webhook_url": old_url},
                new_value={"webhook_url": webhook_url}
            )
            
            # Test notification
            # notification_service.send_webhook(webhook_url, {"type": "verification", "message": "Webhook verified"})
            
            return True
        except Exception as e:
            logger.error(f"Error updating webhook: {e}")
            return False
        finally:
            db.close()

    def _get_recommendation_text(self, level: str, trend: str) -> str:
        if level == "CRITICAL":
            return "ALERTA: Cobertura Inmediata Requerida"
        if trend == "ALCISTA":
            return "Tendencia desfavorable. Aumentar cobertura."
        return "Mercado estable. Mantener posiciones."

# Singleton
hedging_service = HedgingService()
