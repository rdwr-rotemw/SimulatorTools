"""
Reporter sending routes for CyberController simulators.

Endpoints:
- POST /api/cc/{cc_ip}/simulators/{simulator_ip}/reporter/snmp     -> Send SNMP trap to simulator
- POST /api/cc/{cc_ip}/simulators/{simulator_ip}/reporter/irp      -> Send IRP message to simulator
- POST /api/cc/{cc_ip}/simulators/{simulator_ip}/reporter/polling  -> Send polling config to simulator

All endpoints require 'cc_admin' or 'admin' role (enforced via require_cc_access).
These endpoints integrate with the reporter module to send messages to simulators.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.modules.sapro.sapro_client import get_sapro_handler, SaproCommunicationHandler
from backend.app.modules.reporter.reporter import send_snmp_trap, send_irp_message, send_polling
from backend.app.schemas.reporter import (
    ReporterSNMPPayload,
    ReporterIRPPayload,
    ReporterPollingPayload,
    ReporterResponse,
)
from backend.app.utils.auth import require_cc_access
from backend.app.utils.database import get_db
from backend.app.models.user import User

router = APIRouter(prefix="/api", tags=["reporter"])



@router.post(
    "/cc/{cc_ip}/simulators/{simulator_ip}/reporter/snmp",
    status_code=status.HTTP_200_OK,
    response_model=ReporterResponse,
)
async def send_snmp_trap_endpoint(
    cc_ip: str,
    simulator_ip: str,
    payload: ReporterSNMPPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cc_access),
) -> ReporterResponse:
    """Send SNMP trap to simulator via CyberController.

    Requires cc_admin or admin role.

    Args:
        cc_ip: CyberController IP address
        simulator_ip: Target simulator IP address
        payload: SNMP trap configuration (with 'traps' array)
        db: Database session
        current_user: Authenticated user with cc_admin or admin role

    Returns:
        ReporterResponse with success status and message
    """
    try:
        # Convert Pydantic model to dict for the reporter module
        # exclude_none=True ensures only provided fields are included,
        # allowing defaults in attack_traps.py to work correctly
        trap_data = payload.model_dump(exclude_none=True)

        # Call the reporter module with updated signature
        success, message = send_snmp_trap(cc_ip, simulator_ip, trap_data)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=message
            )

        return ReporterResponse(success=True, message=message)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send SNMP trap: {exc!s}"
        )


@router.post(
    "/cc/{cc_ip}/simulators/{simulator_ip}/reporter/irp",
    status_code=status.HTTP_200_OK,
    response_model=ReporterResponse,
)
async def send_irp_message_endpoint(
    cc_ip: str,
    simulator_ip: str,
    payload: ReporterIRPPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cc_access),
    sapro_handler: SaproCommunicationHandler = Depends(get_sapro_handler),
) -> ReporterResponse:
    """Send IRP message to simulator via CyberController.

    Requires cc_admin or admin role.

    Args:
        cc_ip: CyberController IP address
        simulator_ip: Target simulator IP address
        payload: IRP message configuration
        db: Database session
        current_user: Authenticated user with cc_admin or admin role
        sapro_handler: Sapro communication handler instance

    Returns:
        ReporterResponse with success status and message
    """
    try:
        # Extract sapro_server from the handler
        sapro_server = sapro_handler._sapro

        if sapro_server is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sapro server connection not available"
            )

        # Convert Pydantic model to dict for the reporter module
        # exclude_none=True ensures only provided fields are included
        message_data = payload.model_dump(exclude_none=True)

        # Call the reporter module
        success, message = send_irp_message(message_data, cc_ip, simulator_ip, sapro_server)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=message
            )

        return ReporterResponse(success=True, message=message)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send IRP message: {exc!s}"
        )


@router.post(
    "/cc/{cc_ip}/simulators/{simulator_ip}/reporter/polling",
    status_code=status.HTTP_200_OK,
    response_model=ReporterResponse,
)
async def send_polling_config_endpoint(
    cc_ip: str,
    simulator_ip: str,
    payload: ReporterPollingPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cc_access),
    sapro_handler: SaproCommunicationHandler = Depends(get_sapro_handler),
) -> ReporterResponse:
    """Send polling configuration to simulator via CyberController.

    Requires cc_admin or admin role.

    Args:
        cc_ip: CyberController IP address
        simulator_ip: Target simulator IP address
        payload: Polling configuration
        db: Database session
        current_user: Authenticated user with cc_admin or admin role
        sapro_handler: Sapro communication handler instance

    Returns:
        ReporterResponse with success status and message
    """
    try:
        # Extract sapro_server from the handler
        sapro_server = sapro_handler._sapro

        if sapro_server is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sapro server connection not available"
            )

        # Convert Pydantic model to dict for the reporter module
        # exclude_none=True ensures only provided fields are included
        config_data = payload.model_dump(exclude_none=True)

        # Call the reporter module
        success, message = send_polling(config_data, cc_ip, simulator_ip, sapro_server)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=message
            )

        return ReporterResponse(success=True, message=message)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send polling configuration: {exc!s}"
        )


__all__ = ["router"]

