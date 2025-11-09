"""
CyberController integration endpoints (scaffold).

Endpoints:
- POST /api/cc/{cc_ip}/login
- GET /api/cc/{cc_ip}/simulators
- POST /api/cc/{cc_ip}/simulators
- DELETE /api/cc/{cc_ip}/simulators/{simulator_ip}
- GET /api/cc/{cc_ip}/irp/IdsDataFormat

Replace TODOs with actual CC API calls.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.schemas.cc_credentials import CCCredentialsCreate, CCCredentialsResponse
from backend.app.schemas.simulator import SimulatorCreate, SimulatorResponse
from backend.app.schemas.common import SuccessResponse
from backend.app.utils.auth import get_current_user
from backend.app.utils.database import get_db

router = APIRouter(prefix="/api", tags=["cybercontroller"])


class CCLoginIn(BaseModel):
    username: str
    password: str


class CCLoginOut(BaseModel):
    token: str


# Fake CC simulators store for scaffold
_CC_STORE: Dict[str, List[Dict[str, Any]]] = {}


@router.post("/cc/{cc_ip}/login", response_model=CCCredentialsResponse)
async def login_to_cc(cc_ip: str, payload: CCCredentialsCreate, db: Session = Depends(get_db)):
    """Authenticate to the CyberController (stub)."""
    pass


@router.get("/cc/{cc_ip}/simulators", response_model=List[SimulatorResponse])
async def list_cc_simulators(cc_ip: str, current_user=Depends(get_current_user)):
    """Return a list of simulators known to the given CC (stub)."""
    return _CC_STORE.get(cc_ip, [])


@router.post("/cc/{cc_ip}/simulators", response_model=SimulatorResponse, status_code=status.HTTP_201_CREATED)
async def add_cc_simulator(cc_ip: str, payload: SimulatorCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Add a simulator to the CyberController (stub)."""
    lst = _CC_STORE.setdefault(cc_ip, [])
    lst.append(payload)
    return {"status": "ok", "added": payload}


@router.delete("/cc/{cc_ip}/simulators/{simulator_ip}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cc_simulator(cc_ip: str, simulator_ip: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Delete a simulator from the CyberController (stub)."""
    lst = _CC_STORE.get(cc_ip, [])
    for i, s in enumerate(lst):
        if s.get("ip_address") == simulator_ip:
            del lst[i]
            return None
    raise HTTPException(status_code=404, detail="Simulator not found on CC")


@router.get("/cc/{cc_ip}/irp/IdsDataFormat", response_model=List[str])
async def list_ids_data_format(cc_ip: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """List IdsDataFormat XML files available on the CC (stub)."""
    pass
