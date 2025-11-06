"""
Simple health-check route module.

What to implement here:
- Provide lightweight endpoints used by orchestration and readiness/liveness probes
"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/health", tags=["meta"])
async def health_check():
    """Return a small status payload for liveness/readiness checks."""
    return {"status": "ok", "service": "backend"}
