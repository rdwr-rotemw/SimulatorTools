"""
Package router aggregator.

What to implement here:
- Import and combine routers from individual route modules (e.g. health, simulators, admin)
- Apply common prefix or tags if desired
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api")

# Import sub-routers
from backend.app.routes.health import router as health_router
from backend.app.routes.sapro import router as sapro_router
from backend.app.routes.cybercontroller import router as cc_router
from backend.app.routes.reporter import router as reports_router

# Mount sub-routers
router.include_router(health_router, prefix="")
router.include_router(sapro_router, prefix="")
router.include_router(cc_router, prefix="")
router.include_router(reports_router, prefix="")

__all__ = ["router"]
