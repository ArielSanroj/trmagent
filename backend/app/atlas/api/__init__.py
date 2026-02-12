"""
ATLAS API Endpoints
"""
from fastapi import APIRouter

from .exposures import router as exposures_router
from .policies import router as policies_router
from .recommendations import router as recommendations_router
from .orders import router as orders_router
from .reports import router as reports_router

# Main ATLAS router
atlas_router = APIRouter(prefix="/atlas", tags=["ATLAS - Treasury Copilot"])

# Include sub-routers
atlas_router.include_router(exposures_router)
atlas_router.include_router(policies_router)
atlas_router.include_router(recommendations_router)
atlas_router.include_router(orders_router)
atlas_router.include_router(reports_router)


@atlas_router.get("/")
async def atlas_info():
    """ATLAS module information"""
    return {
        "module": "ATLAS",
        "description": "Copiloto de Tesoreria para Riesgo Cambiario",
        "version": "1.0.0",
        "endpoints": {
            "exposures": "/api/v1/atlas/exposures",
            "policies": "/api/v1/atlas/policies",
            "recommendations": "/api/v1/atlas/recommendations",
            "orders": "/api/v1/atlas/orders",
            "reports": "/api/v1/atlas/reports",
        }
    }
