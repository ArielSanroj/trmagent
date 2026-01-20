"""
Multi-Tenant Service
Gestion completa de empresas y aislamiento de datos
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID
import secrets

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.database_models import (
    Company, User, CompanyConfig, TRMHistory, Prediction,
    TradingSignal, Order, BacktestResult, AuditLog
)

logger = logging.getLogger(__name__)


class TenantService:
    """
    Servicio de gestion multi-tenant

    Funcionalidades:
    - Creacion y gestion de empresas (tenants)
    - Configuracion por empresa
    - Aislamiento de datos
    - Gestion de usuarios por empresa
    - Metricas por tenant
    """

    def __init__(self):
        self.default_config = {
            "min_confidence": Decimal("0.90"),
            "max_position_size": Decimal("0.10"),
            "max_daily_loss": Decimal("0.02"),
            "stop_loss_pct": Decimal("0.01"),
            "take_profit_pct": Decimal("0.03"),
            "enable_auto_trading": False,
            "preferred_broker": "alpaca",
            "notification_channels": ["email"],
            "trading_hours_start": 8,
            "trading_hours_end": 17,
            "timezone": "America/Bogota"
        }

    def create_tenant(
        self,
        name: str,
        tax_id: str,
        admin_email: str,
        admin_password: str,
        plan: str = "basic",
        settings: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Crear nuevo tenant (empresa) con usuario administrador

        Args:
            name: Nombre de la empresa
            tax_id: NIT de la empresa
            admin_email: Email del administrador
            admin_password: Password del administrador
            plan: Plan de suscripcion (basic, professional, enterprise)
            settings: Configuracion personalizada

        Returns:
            Dict con datos de la empresa y usuario creados
        """
        db = SessionLocal()
        try:
            # Verificar que no exista
            existing = db.query(Company).filter(
                (Company.tax_id == tax_id) | (Company.name == name)
            ).first()

            if existing:
                return {"error": "Empresa ya existe con ese NIT o nombre"}

            # Crear empresa
            api_key = f"trm_{secrets.token_urlsafe(32)}"

            company = Company(
                name=name,
                tax_id=tax_id,
                subscription_plan=plan,
                api_key=api_key,
                is_active=True,
                settings=settings or {}
            )
            db.add(company)
            db.flush()  # Para obtener el ID

            # Crear configuracion por defecto
            config = CompanyConfig(
                company_id=company.id,
                min_confidence=self.default_config["min_confidence"],
                max_position_size=self.default_config["max_position_size"],
                max_daily_loss=self.default_config["max_daily_loss"],
                stop_loss_pct=self.default_config["stop_loss_pct"],
                take_profit_pct=self.default_config["take_profit_pct"],
                enable_auto_trading=self.default_config["enable_auto_trading"],
                preferred_broker=self.default_config["preferred_broker"],
                notification_channels=self.default_config["notification_channels"]
            )
            db.add(config)

            # Crear usuario administrador
            admin_user = User(
                email=admin_email,
                hashed_password=get_password_hash(admin_password),
                full_name=f"Admin {name}",
                company_id=company.id,
                role="admin",
                is_active=True
            )
            db.add(admin_user)

            db.commit()

            logger.info(f"Tenant created: {name} (ID: {company.id})")

            return {
                "company": {
                    "id": str(company.id),
                    "name": company.name,
                    "tax_id": company.tax_id,
                    "api_key": api_key,
                    "plan": plan
                },
                "admin_user": {
                    "id": str(admin_user.id),
                    "email": admin_user.email
                }
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Error creating tenant: {e}")
            return {"error": str(e)}
        finally:
            db.close()

    def get_tenant(self, company_id: UUID) -> Optional[Dict]:
        """Obtener informacion de un tenant"""
        db = SessionLocal()
        try:
            company = db.query(Company).filter(Company.id == company_id).first()
            if not company:
                return None

            config = db.query(CompanyConfig).filter(
                CompanyConfig.company_id == company_id
            ).first()

            user_count = db.query(User).filter(
                User.company_id == company_id
            ).count()

            return {
                "id": str(company.id),
                "name": company.name,
                "tax_id": company.tax_id,
                "plan": company.subscription_plan,
                "is_active": company.is_active,
                "created_at": company.created_at.isoformat(),
                "user_count": user_count,
                "config": {
                    "min_confidence": float(config.min_confidence) if config else 0.90,
                    "max_position_size": float(config.max_position_size) if config else 0.10,
                    "max_daily_loss": float(config.max_daily_loss) if config else 0.02,
                    "enable_auto_trading": config.enable_auto_trading if config else False,
                    "preferred_broker": config.preferred_broker if config else "alpaca"
                } if config else self.default_config
            }
        finally:
            db.close()

    def update_tenant_config(
        self,
        company_id: UUID,
        config_updates: Dict[str, Any]
    ) -> bool:
        """Actualizar configuracion de un tenant"""
        db = SessionLocal()
        try:
            config = db.query(CompanyConfig).filter(
                CompanyConfig.company_id == company_id
            ).first()

            if not config:
                # Crear configuracion si no existe
                config = CompanyConfig(company_id=company_id)
                db.add(config)

            # Actualizar campos
            allowed_fields = [
                "min_confidence", "max_position_size", "max_daily_loss",
                "stop_loss_pct", "take_profit_pct", "enable_auto_trading",
                "preferred_broker", "notification_channels"
            ]

            for field, value in config_updates.items():
                if field in allowed_fields:
                    setattr(config, field, value)

            db.commit()
            logger.info(f"Config updated for company {company_id}")
            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Error updating config: {e}")
            return False
        finally:
            db.close()

    def add_user_to_tenant(
        self,
        company_id: UUID,
        email: str,
        password: str,
        full_name: str,
        role: str = "trader"
    ) -> Optional[Dict]:
        """Agregar usuario a un tenant"""
        db = SessionLocal()
        try:
            # Verificar que la empresa existe
            company = db.query(Company).filter(Company.id == company_id).first()
            if not company:
                return {"error": "Empresa no encontrada"}

            # Verificar que el email no existe
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                return {"error": "Email ya registrado"}

            # Verificar limite de usuarios segun plan
            user_count = db.query(User).filter(User.company_id == company_id).count()
            plan_limits = {
                "basic": 5,
                "professional": 20,
                "enterprise": 100
            }
            max_users = plan_limits.get(company.subscription_plan, 5)

            if user_count >= max_users:
                return {"error": f"Limite de usuarios alcanzado ({max_users})"}

            user = User(
                email=email,
                hashed_password=get_password_hash(password),
                full_name=full_name,
                company_id=company_id,
                role=role,
                is_active=True
            )
            db.add(user)
            db.commit()

            return {
                "id": str(user.id),
                "email": user.email,
                "role": user.role
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Error adding user: {e}")
            return {"error": str(e)}
        finally:
            db.close()

    def get_tenant_users(self, company_id: UUID) -> List[Dict]:
        """Obtener usuarios de un tenant"""
        db = SessionLocal()
        try:
            users = db.query(User).filter(User.company_id == company_id).all()
            return [
                {
                    "id": str(u.id),
                    "email": u.email,
                    "full_name": u.full_name,
                    "role": u.role,
                    "is_active": u.is_active,
                    "created_at": u.created_at.isoformat()
                }
                for u in users
            ]
        finally:
            db.close()

    def get_tenant_metrics(self, company_id: UUID) -> Dict[str, Any]:
        """Obtener metricas de un tenant"""
        db = SessionLocal()
        try:
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)

            # Conteo de ordenes
            total_orders = db.query(Order).filter(
                Order.company_id == company_id
            ).count()

            recent_orders = db.query(Order).filter(
                Order.company_id == company_id,
                Order.created_at >= thirty_days_ago
            ).count()

            # Conteo de senales
            total_signals = db.query(TradingSignal).filter(
                TradingSignal.company_id == company_id
            ).count()

            # Conteo de predicciones
            total_predictions = db.query(Prediction).filter(
                Prediction.company_id == company_id
            ).count()

            # Conteo de usuarios
            user_count = db.query(User).filter(
                User.company_id == company_id
            ).count()

            # Volumen de trading
            volume = db.query(func.sum(Order.amount)).filter(
                Order.company_id == company_id,
                Order.created_at >= thirty_days_ago
            ).scalar() or 0

            return {
                "total_orders": total_orders,
                "recent_orders_30d": recent_orders,
                "total_signals": total_signals,
                "total_predictions": total_predictions,
                "user_count": user_count,
                "trading_volume_30d": float(volume),
                "period": "30_days"
            }

        finally:
            db.close()

    def suspend_tenant(self, company_id: UUID, reason: str = "") -> bool:
        """Suspender un tenant"""
        db = SessionLocal()
        try:
            company = db.query(Company).filter(Company.id == company_id).first()
            if company:
                company.is_active = False
                company.settings = {
                    **(company.settings or {}),
                    "suspended_at": datetime.utcnow().isoformat(),
                    "suspension_reason": reason
                }
                db.commit()
                logger.info(f"Tenant suspended: {company_id}")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Error suspending tenant: {e}")
            return False
        finally:
            db.close()

    def reactivate_tenant(self, company_id: UUID) -> bool:
        """Reactivar un tenant suspendido"""
        db = SessionLocal()
        try:
            company = db.query(Company).filter(Company.id == company_id).first()
            if company:
                company.is_active = True
                if company.settings:
                    company.settings.pop("suspended_at", None)
                    company.settings.pop("suspension_reason", None)
                db.commit()
                logger.info(f"Tenant reactivated: {company_id}")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Error reactivating tenant: {e}")
            return False
        finally:
            db.close()

    def upgrade_plan(self, company_id: UUID, new_plan: str) -> bool:
        """Actualizar plan de suscripcion"""
        db = SessionLocal()
        try:
            valid_plans = ["basic", "professional", "enterprise"]
            if new_plan not in valid_plans:
                return False

            company = db.query(Company).filter(Company.id == company_id).first()
            if company:
                old_plan = company.subscription_plan
                company.subscription_plan = new_plan
                company.settings = {
                    **(company.settings or {}),
                    "plan_history": company.settings.get("plan_history", []) + [
                        {
                            "from": old_plan,
                            "to": new_plan,
                            "date": datetime.utcnow().isoformat()
                        }
                    ]
                }
                db.commit()
                logger.info(f"Plan upgraded: {company_id} from {old_plan} to {new_plan}")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Error upgrading plan: {e}")
            return False
        finally:
            db.close()

    def list_tenants(
        self,
        active_only: bool = True,
        plan: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Listar todos los tenants (admin only)"""
        db = SessionLocal()
        try:
            query = db.query(Company)

            if active_only:
                query = query.filter(Company.is_active == True)
            if plan:
                query = query.filter(Company.subscription_plan == plan)

            companies = query.limit(limit).all()

            return [
                {
                    "id": str(c.id),
                    "name": c.name,
                    "tax_id": c.tax_id,
                    "plan": c.subscription_plan,
                    "is_active": c.is_active,
                    "created_at": c.created_at.isoformat()
                }
                for c in companies
            ]
        finally:
            db.close()

    def validate_api_key(self, api_key: str) -> Optional[UUID]:
        """Validar API key y retornar company_id"""
        db = SessionLocal()
        try:
            company = db.query(Company).filter(
                Company.api_key == api_key,
                Company.is_active == True
            ).first()

            return company.id if company else None
        finally:
            db.close()

    def regenerate_api_key(self, company_id: UUID) -> Optional[str]:
        """Regenerar API key para una empresa"""
        db = SessionLocal()
        try:
            company = db.query(Company).filter(Company.id == company_id).first()
            if company:
                new_key = f"trm_{secrets.token_urlsafe(32)}"
                company.api_key = new_key
                db.commit()
                logger.info(f"API key regenerated for {company_id}")
                return new_key
            return None
        except Exception as e:
            db.rollback()
            logger.error(f"Error regenerating API key: {e}")
            return None
        finally:
            db.close()


# Instancia singleton
tenant_service = TenantService()
