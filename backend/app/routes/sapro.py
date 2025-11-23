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

from backend.app.schemas.sapro_simulator import (
    SaproSimulatorCreate,
    SaproSimulatorUpdate,
    SaproSimulatorResponse,
)
from backend.app.schemas.common import SuccessResponse
from backend.app.models.simulator import Simulator
from backend.app.utils.database import get_db
from backend.app.utils.auth import require_sapro_access
from backend.app.modules import get_sapro_handler

router = APIRouter(prefix="/api", tags=["sapro"])


@router.post("/simulators", response_model=SaproSimulatorResponse, status_code=status.HTTP_201_CREATED)
def create_simulator(
        payload: SaproSimulatorCreate,
        db: Session = Depends(get_db),
        _current_user=Depends(require_sapro_access),
        sapro_handler=Depends(get_sapro_handler),
) -> SaproSimulatorResponse:
    """Create a new simulator in Sapro and persist it to the DB.

    This endpoint integrates with the Sapro server to create or start a
    simulator device, then saves the simulator metadata in the local DB
    upon success.
    """
    # Conflict if already exists in DB
    existing = db.get(Simulator, payload.ip_address)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Simulator with this IP already exists")

    # Call Sapro to create device
    success, message = sapro_handler.create_device(payload.ip_address, payload.type, payload.template, payload.map)
    if not success:
        # Sapro reported failure
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    # Persist to DB
    sim = Simulator(
        ip_address=payload.ip_address,
        type=payload.type,
        version=payload.template,
        map=payload.map,
        status="running",
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

    return SaproSimulatorResponse.model_validate(sim)


@router.get("/simulators/{simulator_ip}", response_model=SaproSimulatorResponse)
def get_simulator(simulator_ip: str, db: Session = Depends(get_db)) -> SaproSimulatorResponse:
    """Retrieve a Sapro-managed simulator by IP address from the DB."""
    sim = db.get(Simulator, simulator_ip)
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulator not found")
    return SaproSimulatorResponse.model_validate(sim)


@router.get("/simulators", response_model=List[SaproSimulatorResponse])
def list_simulators(
        db: Session = Depends(get_db),
        _current_user=Depends(require_sapro_access),
        sapro_handler=Depends(get_sapro_handler)
) -> List[SaproSimulatorResponse]:
    """Get all devices from Sapro and sync to DB"""
    devices = sapro_handler.get_all_devices()  # List[SaproDevice]

    # Upsert to DB
    for device in devices:
        db.merge(Simulator(
            ip_address=device.ip_address,
            type=device.type,
            version=device.version,
            map=device.map,
            status=device.status
        ))
    db.commit()

    # Return from DB
    sims = db.query(Simulator).all()
    return [SaproSimulatorResponse.model_validate(s) for s in sims]


@router.put("/simulators/{simulator_ip}", response_model=SaproSimulatorResponse)
def update_simulator(
        simulator_ip: str,
        payload: SaproSimulatorUpdate,
        db: Session = Depends(get_db),
        _current_user=Depends(require_sapro_access),
) -> SaproSimulatorResponse:
    """Update metadata for a Sapro-managed simulator.

    Only provided fields are updated; Sapro side operations are not
    performed here (they could be added later if needed).
    """

    sim = db.get(Simulator, simulator_ip)
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulator not found")

    # Apply provided updates (only non-None values)
    if payload.type is not None:
        sim.type = payload.type
    if payload.version is not None:
        sim.version = payload.version
    if payload.map is not None:
        sim.map = payload.map
    if payload.status is not None:  # backward-compat: keep handling if provided in payload type
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

    return SaproSimulatorResponse.model_validate(sim)


@router.delete("/simulators/{simulator_ip}", response_model=SuccessResponse)
def delete_simulator(
        simulator_ip: str,
        db: Session = Depends(get_db),
        _current_user=Depends(require_sapro_access),
        sapro_handler=Depends(get_sapro_handler),
) -> SuccessResponse:
    """Delete a Sapro-managed simulator from Sapro and the DB.

    Calls the Sapro handler to remove the device from the map/server first,
    then removes the record from the local DB on success.
    """
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
