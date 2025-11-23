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
from pydantic import BaseModel
from typing import Any, Dict, Union
from backend.app.utils.database import get_mongo_db
from backend.app.modules.reporter.irp.irp_module import send_irp, create_irp_template, load_schema_from_mongo

router = APIRouter(prefix="/api", tags=["reporter"])


class IRPSendPayload(BaseModel):
    mongo_id: str
    message_id: Union[int, str]
    message_data: Dict[str, Any]
    from_ip: str
    to_ip: str


class IRPTemplatePayload(BaseModel):
    mongo_id: str
    message_id: Union[int, str]


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


@router.post(
    "/cc/{cc_ip}/irp/send",
    status_code=status.HTTP_200_OK,
)
async def send_irp_endpoint(
    cc_ip: str,
    payload: IRPSendPayload,
    mongo_db = Depends(get_mongo_db),
    current_user: User = Depends(require_cc_access),
) -> Dict[str, Any]:
    """Send an IRP message based on a stored IdsDataFormat schema in MongoDB.

    Body fields: mongo_id, message_id, message_data, from_ip, to_ip
    """
    try:
        ok, msg = send_irp(payload.mongo_id, payload.message_id, payload.message_data, payload.from_ip, payload.to_ip, mongo_db)
        if not ok:
            # Sending failed
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
        return {"success": True, "message": msg}
    except ValueError as ve:
        # invalid id format
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except KeyError as ke:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ke))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to send IRP: {exc!s}")


@router.post(
    "/cc/{cc_ip}/irp/template",
    status_code=status.HTTP_200_OK,
)
async def create_irp_template_endpoint(
    cc_ip: str,
    payload: IRPTemplatePayload,
    mongo_db = Depends(get_mongo_db),
    current_user: User = Depends(require_cc_access),
) -> Dict[str, Any]:
    """Generate an IRP template for a message from a stored schema in MongoDB."""
    try:
        schema_obj = load_schema_from_mongo(mongo_db, payload.mongo_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except KeyError as ke:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ke))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to load schema: {exc!s}")

    try:
        template = create_irp_template(schema_obj, payload.message_id)
        if template is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message ID not found or template generation failed")
        return template
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message ID not found")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Template generation failed: {exc!s}")


__all__ = ["router"]
