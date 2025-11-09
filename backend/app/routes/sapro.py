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
from backend.app.modules import get_sapro_handler


router = APIRouter(prefix="/api", tags=["sapro"])


@router.post("/simulators", response_model=SimulatorResponse, status_code=status.HTTP_201_CREATED)
def create_simulator(
    payload: SimulatorCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    sapro_handler=Depends(get_sapro_handler),
) -> SimulatorResponse:
    """Create a new simulator both in Sapro and the DB.

    Calls the Sapro handler to create the device, then persists the simulator
    record on success. Returns 400/409/500 for various failure modes.
    """
    # Conflict if already exists in DB
    existing = db.get(Simulator, payload.ip_address)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Simulator with this IP already exists")

    # Call Sapro to create device
    success, message = sapro_handler.create_device(payload.ip_address, payload.type or "")
    if not success:
        # Sapro reported failure
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    # Persist to DB
    sim = Simulator(
        ip_address=payload.ip_address,
        type=payload.type,
        map=payload.map,
        cc_ip=payload.cc_ip,
        status=payload.status or "running",
    )
    try:
        db.add(sim)
        db.commit()
        db.refresh(sim)
    except IntegrityError:
        db.rollback()
        # Shouldn't happen since we checked earlier, but handle race
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Simulator with this IP already exists")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Use Pydantic v2 `model_validate` with `from_attributes=True` (schemas already configure this)
    return SimulatorResponse.model_validate(sim)


@router.get("/simulators/{simulator_ip}", response_model=SimulatorResponse)
def get_simulator(simulator_ip: str, db: Session = Depends(get_db)) -> SimulatorResponse:
    """Retrieve a simulator by IP address."""
    sim = db.get(Simulator, simulator_ip)
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulator not found")
    return SimulatorResponse.model_validate(sim)


@router.get("/simulators", response_model=List[SimulatorResponse])
def list_simulators(db: Session = Depends(get_db)) -> List[SimulatorResponse]:
    """List all simulators."""
    sims = db.query(Simulator).all()
    return [SimulatorResponse.model_validate(s) for s in sims]


@router.put("/simulators/{simulator_ip}", response_model=SimulatorResponse)
def update_simulator(
    simulator_ip: str,
    payload: SimulatorUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> SimulatorResponse:
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

    return SimulatorResponse.model_validate(sim)


@router.delete("/simulators/{simulator_ip}", response_model=SuccessResponse)
def delete_simulator(
    simulator_ip: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    sapro_handler=Depends(get_sapro_handler),
) -> SuccessResponse:
    """Delete a simulator both from Sapro and the DB."""
    sim = db.get(Simulator, simulator_ip)
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulator not found")

    # Attempt to delete from Sapro first
    map_name = sim.map or ""
    success, message = sapro_handler.delete_device(map_name, simulator_ip)
    if not success:
        # Sapro deletion failed
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    try:
        db.delete(sim)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return SuccessResponse(message="Simulator deleted successfully", data={"ip_address": simulator_ip})
