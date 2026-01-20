"""
Tenant Management API Endpoints
Gestion de empresas y usuarios
"""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.core.security import get_current_user, require_role
from app.services.tenant_service import tenant_service

router = APIRouter(prefix="/tenants", tags=["tenants"])


# Schemas
class CreateTenantRequest(BaseModel):
    name: str
    tax_id: str
    admin_email: EmailStr
    admin_password: str
    plan: str = "basic"
    settings: Optional[dict] = None


class UpdateConfigRequest(BaseModel):
    min_confidence: Optional[float] = None
    max_position_size: Optional[float] = None
    max_daily_loss: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    enable_auto_trading: Optional[bool] = None
    preferred_broker: Optional[str] = None
    notification_channels: Optional[List[str]] = None


class AddUserRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = "trader"


class UpgradePlanRequest(BaseModel):
    new_plan: str


# Endpoints

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_tenant(request: CreateTenantRequest):
    """
    Crear nuevo tenant (empresa)

    Solo para administradores del sistema
    """
    result = tenant_service.create_tenant(
        name=request.name,
        tax_id=request.tax_id,
        admin_email=request.admin_email,
        admin_password=request.admin_password,
        plan=request.plan,
        settings=request.settings
    )

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )

    return result


@router.get("/{company_id}")
async def get_tenant(
    company_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Obtener informacion de un tenant"""
    # Verificar acceso
    if str(current_user.get("company_id")) != str(company_id) and current_user.get("role") != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene acceso a este tenant"
        )

    result = tenant_service.get_tenant(company_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant no encontrado"
        )

    return result


@router.put("/{company_id}/config")
async def update_tenant_config(
    company_id: UUID,
    request: UpdateConfigRequest,
    current_user: dict = Depends(get_current_user)
):
    """Actualizar configuracion de un tenant"""
    # Solo admin de la empresa o superadmin
    if str(current_user.get("company_id")) != str(company_id) or current_user.get("role") not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden modificar configuracion"
        )

    config_updates = {k: v for k, v in request.dict().items() if v is not None}

    success = tenant_service.update_tenant_config(company_id, config_updates)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error actualizando configuracion"
        )

    return {"message": "Configuracion actualizada"}


@router.post("/{company_id}/users")
async def add_user_to_tenant(
    company_id: UUID,
    request: AddUserRequest,
    current_user: dict = Depends(get_current_user)
):
    """Agregar usuario a un tenant"""
    # Solo admin de la empresa
    if str(current_user.get("company_id")) != str(company_id) or current_user.get("role") not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden agregar usuarios"
        )

    result = tenant_service.add_user_to_tenant(
        company_id=company_id,
        email=request.email,
        password=request.password,
        full_name=request.full_name,
        role=request.role
    )

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )

    return result


@router.get("/{company_id}/users")
async def get_tenant_users(
    company_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Obtener usuarios de un tenant"""
    if str(current_user.get("company_id")) != str(company_id) and current_user.get("role") != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene acceso a este tenant"
        )

    return tenant_service.get_tenant_users(company_id)


@router.get("/{company_id}/metrics")
async def get_tenant_metrics(
    company_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Obtener metricas de un tenant"""
    if str(current_user.get("company_id")) != str(company_id) and current_user.get("role") != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene acceso a este tenant"
        )

    return tenant_service.get_tenant_metrics(company_id)


@router.post("/{company_id}/suspend")
async def suspend_tenant(
    company_id: UUID,
    reason: str = "",
    current_user: dict = Depends(require_role("superadmin"))
):
    """Suspender un tenant (solo superadmin)"""
    success = tenant_service.suspend_tenant(company_id, reason)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant no encontrado"
        )

    return {"message": "Tenant suspendido"}


@router.post("/{company_id}/reactivate")
async def reactivate_tenant(
    company_id: UUID,
    current_user: dict = Depends(require_role("superadmin"))
):
    """Reactivar un tenant (solo superadmin)"""
    success = tenant_service.reactivate_tenant(company_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant no encontrado"
        )

    return {"message": "Tenant reactivado"}


@router.put("/{company_id}/plan")
async def upgrade_plan(
    company_id: UUID,
    request: UpgradePlanRequest,
    current_user: dict = Depends(require_role("superadmin"))
):
    """Actualizar plan de suscripcion (solo superadmin)"""
    success = tenant_service.upgrade_plan(company_id, request.new_plan)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan invalido o tenant no encontrado"
        )

    return {"message": f"Plan actualizado a {request.new_plan}"}


@router.post("/{company_id}/regenerate-api-key")
async def regenerate_api_key(
    company_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Regenerar API key para una empresa"""
    if str(current_user.get("company_id")) != str(company_id) or current_user.get("role") not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden regenerar API key"
        )

    new_key = tenant_service.regenerate_api_key(company_id)

    if not new_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant no encontrado"
        )

    return {"api_key": new_key}


@router.get("/")
async def list_tenants(
    active_only: bool = True,
    plan: Optional[str] = None,
    limit: int = 100,
    current_user: dict = Depends(require_role("superadmin"))
):
    """Listar todos los tenants (solo superadmin)"""
    return tenant_service.list_tenants(
        active_only=active_only,
        plan=plan,
        limit=limit
    )
