"""
Motor de Decisiones de Trading
Genera senales BUY/SELL/HOLD basado en predicciones ML
CONFIANZA MINIMA: 90%

Refactorizado para Clean Architecture:
- Usa Dependency Injection via constructor
- UnitOfWork para acceso a datos (resuelve DIP)
- IMLModel interface para modelos (resuelve SRP)
"""
from datetime import datetime, timedelta
from typing import Optional, List, Callable
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum
import logging
from uuid import UUID

from app.core.config import settings
from app.models.database_models import (
    TradingSignal, SignalAction, SignalStatus
)
from app.services.data_ingestion import data_ingestion_service

# Clean Architecture imports
from app.application.interfaces.ml_model import IMLModel
from app.infrastructure.persistence.unit_of_work import UnitOfWork
from app.core.container import get_container

logger = logging.getLogger(__name__)


class SignalStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


@dataclass
class TradingDecision:
    """Resultado del motor de decisiones"""
    action: SignalAction
    confidence: Decimal
    predicted_trm: Decimal
    current_trm: Decimal
    expected_return: Decimal
    risk_score: Decimal
    signal_strength: SignalStrength
    reasoning: str
    approved: bool  # Si pasa todos los filtros


class DecisionEngine:
    """
    Motor de decisiones para trading de USD/COP

    Configuracion por defecto:
    - Confianza minima: 90%
    - Retorno esperado minimo: 2%
    - Risk/Reward ratio: > 2.0

    Refactorizado:
    - Recibe dependencias via constructor (DIP)
    - Usa UnitOfWork para queries a BD (SRP)
    - Usa IMLModel interface para predicciones
    """

    def __init__(
        self,
        ml_model: Optional[IMLModel] = None,
        uow_factory: Optional[Callable[[], UnitOfWork]] = None
    ):
        """
        Constructor con Dependency Injection

        Args:
            ml_model: Modelo ML a usar (si None, usa ensemble del container)
            uow_factory: Factory para crear UnitOfWork (si None, usa default)
        """
        # Configuracion por defecto (puede sobreescribirse por empresa)
        self.default_min_confidence = Decimal(str(settings.MIN_CONFIDENCE))  # 0.90
        self.default_min_return = Decimal(str(settings.MIN_EXPECTED_RETURN))  # 0.02
        self.default_max_risk = Decimal("0.30")

        # Inyeccion de dependencias
        if ml_model is None:
            container = get_container()
            self._ml_model = container.ml_registry.get_model("ensemble")
        else:
            self._ml_model = ml_model

        if uow_factory is None:
            container = get_container()
            self._uow_factory = container.get_uow_factory()
        else:
            self._uow_factory = uow_factory

    def generate_signal(
        self,
        company_id: Optional[UUID] = None,
        prediction: Optional[dict] = None
    ) -> TradingDecision:
        """
        Generar senal de trading basada en prediccion ML

        Args:
            company_id: ID de la empresa (para config personalizada)
            prediction: Prediccion a evaluar (si no se provee, genera una)

        Returns:
            TradingDecision con la recomendacion
        """
        # Obtener configuracion via UnitOfWork (DIP resuelto)
        config = self._get_company_config(company_id)

        # Obtener TRM actual
        current_trm = self._get_current_trm()
        if not current_trm:
            return self._create_hold_decision(
                current_trm=Decimal("0"),
                reason="No se pudo obtener TRM actual"
            )

        # Obtener o generar prediccion
        if prediction is None:
            prediction = self._generate_prediction()

        if not prediction:
            return self._create_hold_decision(
                current_trm=current_trm,
                reason="No se pudo generar prediccion"
            )

        # Calcular metricas
        predicted_trm = Decimal(str(prediction["predicted_value"]))
        confidence = Decimal(str(prediction.get("confidence", 0.5)))
        expected_return = (predicted_trm - current_trm) / current_trm

        # Calcular risk score
        lower_bound = Decimal(str(prediction.get("lower_bound", predicted_trm * Decimal("0.95"))))
        upper_bound = Decimal(str(prediction.get("upper_bound", predicted_trm * Decimal("1.05"))))
        risk_score = self._calculate_risk_score(
            current_trm, predicted_trm, lower_bound, upper_bound
        )

        # Determinar accion
        action, reasoning = self._determine_action(
            current_trm=current_trm,
            predicted_trm=predicted_trm,
            expected_return=expected_return,
            confidence=confidence,
            config=config
        )

        # Determinar fuerza de la senal
        signal_strength = self._calculate_signal_strength(
            expected_return=expected_return,
            confidence=confidence,
            risk_score=risk_score
        )

        # Validar si pasa todos los filtros (90% confianza)
        approved = self._validate_signal(
            action=action,
            confidence=confidence,
            expected_return=expected_return,
            risk_score=risk_score,
            config=config
        )

        return TradingDecision(
            action=action,
            confidence=confidence,
            predicted_trm=predicted_trm,
            current_trm=current_trm,
            expected_return=expected_return,
            risk_score=risk_score,
            signal_strength=signal_strength,
            reasoning=reasoning,
            approved=approved
        )

    def _get_company_config(self, company_id: Optional[UUID]) -> dict:
        """
        Obtener configuracion de empresa o usar defaults

        Refactorizado: Usa UnitOfWork en lugar de SessionLocal directo
        Resuelve violacion DIP
        """
        if company_id is None:
            return {
                "min_confidence": self.default_min_confidence,
                "min_expected_return": self.default_min_return,
                "max_risk": self.default_max_risk
            }

        # Usar UnitOfWork para obtener config
        with self._uow_factory() as uow:
            config = uow.company_config.get_by_company_id(company_id)

            if config:
                return {
                    "min_confidence": config.get("min_confidence", self.default_min_confidence),
                    "min_expected_return": config.get("min_expected_return", self.default_min_return),
                    "max_risk": Decimal("0.30")  # Fijo por ahora
                }
            else:
                return {
                    "min_confidence": self.default_min_confidence,
                    "min_expected_return": self.default_min_return,
                    "max_risk": self.default_max_risk
                }

    def _get_current_trm(self) -> Optional[Decimal]:
        """Obtener TRM actual"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        trm_data = loop.run_until_complete(data_ingestion_service.get_current_trm())
        if trm_data:
            return Decimal(str(trm_data["value"]))
        return None

    def _generate_prediction(self) -> Optional[dict]:
        """
        Generar prediccion usando modelo ML inyectado

        Refactorizado: Usa self._ml_model en lugar de import directo
        Resuelve violacion SRP
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Obtener historico
        trm_history = loop.run_until_complete(
            data_ingestion_service.get_trm_history(days=90)
        )

        if not trm_history or not self._ml_model.is_fitted:
            return None

        # Usar interface uniforme IMLModel
        predictions = self._ml_model.predict(trm_history, days_ahead=30)
        if predictions:
            return predictions[0]  # Primera prediccion (mas cercana)
        return None

    def _determine_action(
        self,
        current_trm: Decimal,
        predicted_trm: Decimal,
        expected_return: Decimal,
        confidence: Decimal,
        config: dict
    ) -> tuple:
        """Determinar accion de trading"""
        min_return = config["min_expected_return"]
        min_confidence = config["min_confidence"]

        # Logica de decision
        if confidence < min_confidence:
            return (
                SignalAction.HOLD,
                f"Confianza insuficiente ({confidence:.1%} < {min_confidence:.1%} requerido)"
            )

        if expected_return > min_return:
            # TRM subira -> Comprar USD ahora
            return (
                SignalAction.BUY_USD,
                f"Se espera que TRM suba {expected_return:.2%}. "
                f"Prediccion: ${predicted_trm:,.2f} vs actual ${current_trm:,.2f}. "
                f"Confianza: {confidence:.1%}"
            )
        elif expected_return < -min_return:
            # TRM bajara -> Vender USD / Comprar COP
            return (
                SignalAction.SELL_USD,
                f"Se espera que TRM baje {abs(expected_return):.2%}. "
                f"Prediccion: ${predicted_trm:,.2f} vs actual ${current_trm:,.2f}. "
                f"Confianza: {confidence:.1%}"
            )
        else:
            return (
                SignalAction.HOLD,
                f"Movimiento esperado muy pequeno ({expected_return:.2%}). "
                f"Se requiere minimo {min_return:.2%}"
            )

    def _calculate_risk_score(
        self,
        current_trm: Decimal,
        predicted_trm: Decimal,
        lower_bound: Decimal,
        upper_bound: Decimal
    ) -> Decimal:
        """
        Calcular score de riesgo (0 = bajo riesgo, 1 = alto riesgo)
        Basado en volatilidad del intervalo de confianza
        """
        # Rango del intervalo como % del valor predicho
        range_pct = (upper_bound - lower_bound) / predicted_trm

        # Distancia al valor actual como %
        distance_pct = abs(predicted_trm - current_trm) / current_trm

        # Risk score: mayor rango y mayor distancia = mas riesgo
        risk = min(Decimal("1.0"), (range_pct + distance_pct) / 2)

        return risk.quantize(Decimal("0.0001"))

    def _calculate_signal_strength(
        self,
        expected_return: Decimal,
        confidence: Decimal,
        risk_score: Decimal
    ) -> SignalStrength:
        """Calcular fuerza de la senal"""
        # Score compuesto
        score = (
            abs(expected_return) * Decimal("0.4") +
            confidence * Decimal("0.4") +
            (1 - risk_score) * Decimal("0.2")
        )

        if score > Decimal("0.7"):
            return SignalStrength.STRONG
        elif score > Decimal("0.4"):
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK

    def _validate_signal(
        self,
        action: SignalAction,
        confidence: Decimal,
        expected_return: Decimal,
        risk_score: Decimal,
        config: dict
    ) -> bool:
        """
        Validar si la senal cumple todos los criterios
        IMPORTANTE: Confianza minima 90%
        """
        if action == SignalAction.HOLD:
            return True  # HOLD siempre es valido

        checks = {
            "confidence": confidence >= config["min_confidence"],  # >= 90%
            "expected_return": abs(expected_return) >= config["min_expected_return"],
            "risk_reward": abs(expected_return) / max(risk_score, Decimal("0.01")) > 2,
            "risk_level": risk_score <= config["max_risk"]
        }

        all_passed = all(checks.values())

        if not all_passed:
            failed = [k for k, v in checks.items() if not v]
            logger.info(f"Signal validation failed: {failed}")

        return all_passed

    def _create_hold_decision(
        self,
        current_trm: Decimal,
        reason: str
    ) -> TradingDecision:
        """Crear decision HOLD cuando no hay datos suficientes"""
        return TradingDecision(
            action=SignalAction.HOLD,
            confidence=Decimal("0"),
            predicted_trm=current_trm,
            current_trm=current_trm,
            expected_return=Decimal("0"),
            risk_score=Decimal("1"),
            signal_strength=SignalStrength.WEAK,
            reasoning=reason,
            approved=False
        )

    def save_signal_to_db(
        self,
        decision: TradingDecision,
        company_id: Optional[UUID] = None
    ) -> Optional[UUID]:
        """
        Guardar senal en base de datos

        Refactorizado: Usa UnitOfWork en lugar de SessionLocal directo
        """
        try:
            with self._uow_factory() as uow:
                signal = TradingSignal(
                    company_id=company_id,
                    action=decision.action,
                    confidence=decision.confidence,
                    predicted_trm=decision.predicted_trm,
                    current_trm=decision.current_trm,
                    expected_return=decision.expected_return,
                    risk_score=decision.risk_score,
                    reasoning=decision.reasoning,
                    status=SignalStatus.PENDING,
                    expires_at=datetime.utcnow() + timedelta(hours=24)
                )
                saved = uow.signals.save(signal)
                uow.commit()

                return saved.id

        except Exception as e:
            logger.error(f"Error saving signal: {e}")
            return None


# Factory function para crear instancia con dependencias default
def create_decision_engine(
    model_type: str = "ensemble",
    uow_factory: Optional[Callable[[], UnitOfWork]] = None
) -> DecisionEngine:
    """
    Factory para crear DecisionEngine con modelo especifico

    Args:
        model_type: Tipo de modelo ('prophet', 'lstm', 'ensemble')
        uow_factory: Factory para UnitOfWork (opcional)

    Returns:
        DecisionEngine configurado
    """
    container = get_container()
    ml_model = container.ml_registry.get_model(model_type)

    if uow_factory is None:
        uow_factory = container.get_uow_factory()

    return DecisionEngine(ml_model=ml_model, uow_factory=uow_factory)


# Instancia singleton para compatibilidad con codigo existente
# Usa configuracion por defecto (ensemble model)
decision_engine = DecisionEngine()
