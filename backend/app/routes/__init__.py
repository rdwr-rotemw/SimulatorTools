"""
Package router aggregator.

What to implement here:
- Import and combine routers from individual route modules (e.g. health, simulators, admin)
- Apply common prefix or tags if desired
"""
from fastapi import APIRouter

# ...existing code...

router = APIRouter(prefix="/api")

# Import sub-routers
from .health import router as health_router

# Mount sub-routers
router.include_router(health_router, prefix="")

__all__ = ["router"]
