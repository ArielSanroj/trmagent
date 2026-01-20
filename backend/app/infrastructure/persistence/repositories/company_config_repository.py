"""
Implementacion de ICompanyConfigRepository
"""
from typing import Optional
from uuid import UUID
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.database_models import CompanyConfig
from app.core.config import settings


class CompanyConfigRepository:
    """
    Repository para configuracion de empresas

    Encapsula acceso a configuracion de trading por empresa,
    resolviendo violacion DIP en DecisionEngine.
    """

    def __init__(self, session: Session):
        self._session = session

    def get_by_company_id(self, company_id: UUID) -> Optional[dict]:
        """
        Obtener configuracion de una empresa

        Args:
            company_id: ID de la empresa

        Returns:
            Diccionario con configuracion o None
        """
        config = self._session.query(CompanyConfig).filter(
            CompanyConfig.company_id == company_id
        ).first()

        if config:
            return {
                "min_confidence": config.min_confidence,
                "min_expected_return": config.min_expected_return,
                "max_daily_loss": config.max_daily_loss,
                "max_position_size": config.max_position_size,
                "stop_loss_pct": config.stop_loss_pct,
                "take_profit_pct": config.take_profit_pct,
                "auto_execute": config.auto_execute,
                "paper_trading": config.paper_trading,
                "preferred_broker": config.preferred_broker,
            }
        return None

    def get_default(self) -> dict:
        """
        Obtener configuracion por defecto del sistema

        Lee de settings (config.py) para mantener consistencia

        Returns:
            Diccionario con configuracion por defecto
        """
        return {
            "min_confidence": Decimal(str(settings.MIN_CONFIDENCE)),
            "min_expected_return": Decimal(str(settings.MIN_EXPECTED_RETURN)),
            "max_daily_loss": Decimal(str(settings.MAX_DAILY_LOSS)),
            "max_position_size": Decimal(str(settings.MAX_POSITION_SIZE)),
            "stop_loss_pct": Decimal(str(settings.STOP_LOSS_PCT)),
            "take_profit_pct": Decimal(str(settings.TAKE_PROFIT_PCT)),
            "auto_execute": False,
            "paper_trading": True,
            "preferred_broker": "alpaca",
        }

    def get_or_default(self, company_id: Optional[UUID]) -> dict:
        """
        Obtener configuracion de empresa o defaults

        Args:
            company_id: ID de empresa o None

        Returns:
            Configuracion de empresa si existe, sino defaults
        """
        if company_id:
            config = self.get_by_company_id(company_id)
            if config:
                return config

        return self.get_default()

    def update(self, company_id: UUID, updates: dict) -> Optional[dict]:
        """
        Actualizar configuracion de empresa

        Args:
            company_id: ID de la empresa
            updates: Diccionario con campos a actualizar

        Returns:
            Configuracion actualizada o None si no existe
        """
        config = self._session.query(CompanyConfig).filter(
            CompanyConfig.company_id == company_id
        ).first()

        if not config:
            return None

        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)

        self._session.flush()
        return self.get_by_company_id(company_id)
