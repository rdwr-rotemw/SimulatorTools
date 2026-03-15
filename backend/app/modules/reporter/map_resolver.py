"""
Utility for resolving simulator maps from database or payload.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.simulator import Simulator


def get_simulator_map(
    db: Session,
    simulator_ip: str,
    provided_map: str | None,
) -> str:
    """Get simulator map from provided value or database.

    Args:
        db: Database session
        simulator_ip: Simulator IP address
        provided_map: Map provided in payload (optional)

    Returns:
        Map name for the simulator

    Raises:
        HTTPException: If map not found in payload or database
    """
    if provided_map:
        return provided_map

    sim = db.query(Simulator).filter(Simulator.ip_address == simulator_ip).first()
    if not sim or not sim.map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Map not found for simulator {simulator_ip}. Provide map in payload or add simulator to database.",
        )
    return sim.map
