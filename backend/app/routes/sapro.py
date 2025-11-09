"""
Simulator management endpoints (CRUD).

Implements DB-only CRUD for Simulator model:
- POST /api/simulators
- GET  /api/simulators/{simulator_ip}
- GET  /api/simulators
- PUT  /api/simulators/{simulator_ip}
- DELETE /api/simulators/{simulator_ip}

Protected endpoints (create/update/delete) require authentication via
`get_current_user`. No Sapro/CyberController integrations are performed
here; this is basic DB CRUD only.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.app.schemas.simulator import SimulatorCreate, SimulatorUpdate, SimulatorResponse
from backend.app.schemas.common import SuccessResponse
from backend.app.models.simulator import Simulator
from backend.app.utils.database import get_db
from backend.app.utils.auth import get_current_user

router = APIRouter(prefix="/api", tags=["sapro"])


@router.post("/simulators", response_model=SimulatorResponse, status_code=status.HTTP_201_CREATED)
def create_simulator(payload: SimulatorCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> SimulatorResponse:
    """Create a new simulator in the database.

    Returns the created SimulatorResponse. Raises 409 if ip_address already exists,
    400 for other DB errors.
    """
    # Check for existing simulator to provide a clear 409 response
    existing = db.get(Simulator, payload.ip_address)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Simulator with this IP already exists")

    sim = Simulator(
        ip_address=payload.ip_address,
        type=payload.type,
        map=payload.map,
        cc_ip=payload.cc_ip,
        status=payload.status or "unknown",
    )
    try:
        db.add(sim)
        db.commit()
        db.refresh(sim)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Simulator with this IP already exists")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return SimulatorResponse(
        ip_address=sim.ip_address,
        type=sim.type,
        map=sim.map,
        cc_ip=sim.cc_ip,
        status=sim.status,
        created_at=sim.created_at,
    )


@router.get("/simulators/{simulator_ip}", response_model=SimulatorResponse)
def get_simulator(simulator_ip: str, db: Session = Depends(get_db)) -> SimulatorResponse:
    """Retrieve a simulator by IP address."""
    sim = db.get(Simulator, simulator_ip)
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulator not found")
    return SimulatorResponse(
        ip_address=sim.ip_address,
        type=sim.type,
        map=sim.map,
        cc_ip=sim.cc_ip,
        status=sim.status,
        created_at=sim.created_at,
    )


@router.get("/simulators", response_model=List[SimulatorResponse])
def list_simulators(db: Session = Depends(get_db)) -> List[SimulatorResponse]:
    """List all simulators."""
    sims = db.query(Simulator).all()
    return [
        SimulatorResponse(
            ip_address=s.ip_address,
            type=s.type,
            map=s.map,
            cc_ip=s.cc_ip,
            status=s.status,
            created_at=s.created_at,
        )
        for s in sims
    ]


@router.put("/simulators/{simulator_ip}", response_model=SimulatorResponse)
def update_simulator(simulator_ip: str, payload: SimulatorUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> SimulatorResponse:
    """Update fields of an existing simulator."""
    sim = db.get(Simulator, simulator_ip)
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulator not found")

    # Apply provided updates (only non-None values)
    if payload.type is not None:
        sim.type = payload.type
    if payload.map is not None:
        sim.map = payload.map
    if payload.status is not None:
        sim.status = payload.status

    try:
        db.add(sim)
        db.commit()
        db.refresh(sim)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Simulator conflict on update")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return SimulatorResponse(
        ip_address=sim.ip_address,
        type=sim.type,
        map=sim.map,
        cc_ip=sim.cc_ip,
        status=sim.status,
        created_at=sim.created_at,
    )


@router.delete("/simulators/{simulator_ip}", response_model=SuccessResponse)
def delete_simulator(simulator_ip: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)) -> SuccessResponse:
    """Delete a simulator by IP and return a success message."""
    sim = db.get(Simulator, simulator_ip)
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulator not found")
    try:
        db.delete(sim)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return SuccessResponse(message="Simulator deleted successfully", data={"ip_address": simulator_ip})
