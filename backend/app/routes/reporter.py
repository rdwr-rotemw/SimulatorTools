"""
Reporter route stubs.

Defines endpoint signatures only; implementations should be added later.
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.schemas.common import SuccessResponse
from backend.app.schemas.auth import LoginRequest, LoginResponse
from backend.app.schemas.simulator import SimulatorCreate, SimulatorResponse
from backend.app.schemas.user import UserResponse
from backend.app.schemas.cc_credentials import CCCredentialsResponse

from backend.app.utils.auth import get_current_user
from backend.app.utils.database import get_db

router = APIRouter(prefix="/api", tags=["reports"])


@router.post("/reports/snmp-trap", status_code=status.HTTP_200_OK, response_model=SuccessResponse)
async def generate_snmp_trap(payload: Dict[str, Any], db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Generate SNMP trap (stub)."""
    pass


@router.post("/reports/irp-message", status_code=status.HTTP_200_OK, response_model=SuccessResponse)
async def generate_irp_message(payload: Dict[str, Any], db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Generate IRP message (stub)."""
    pass


@router.post("/reports/polling", status_code=status.HTTP_200_OK, response_model=SuccessResponse)
async def generate_polling(payload: Dict[str, Any], db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Generate polling configuration (stub)."""
    pass


@router.post("/cc/{cc_ip}/simulators/{simulator_ip}/send", status_code=status.HTTP_200_OK, response_model=SuccessResponse)
async def send_to_simulator(cc_ip: str, simulator_ip: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Send data to a simulator on a given CC (stub)."""
    pass
