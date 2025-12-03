"""
Reporter sending routes for CyberController simulators.

Endpoints:
- POST /api/cc/{cc_ip}/simulators/{simulator_ip}/reporter/snmp     -> Send SNMP trap to simulator
- POST /api/cc/{cc_ip}/simulators/{simulator_ip}/reporter/irp      -> Send IRP message to simulator
- POST /api/cc/{cc_ip}/simulators/{simulator_ip}/reporter/polling  -> Send polling config to simulator

All endpoints require 'cc_admin' or 'admin' role (enforced via require_cc_access).
These endpoints integrate directly with reporter implementation modules.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Union
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.app.models.user import User
from backend.app.modules.reporter.irp.irp_module import load_schema_from_mongo, send_irp_messages
from backend.app.modules.reporter.snmp import attack_traps
from backend.app.modules.sapro.sapro_client import get_sapro_handler, SaproCommunicationHandler
from backend.app.schemas.reporter import (
    ReporterSNMPPayload,
    ReporterPollingPayload,
    ReporterResponse,
)
from backend.app.utils.auth import require_cc_access, get_current_user
from backend.app.utils.database import get_mongo_db

router = APIRouter(prefix="/api", tags=["reporter"])
logger = logging.getLogger("sim-tools.reporter")


class IRPSendPayload(BaseModel):
    mongo_id: str
    message_data: Dict[str, Any]


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
        _current_user: User = Depends(require_cc_access),
) -> ReporterResponse:
    """Send SNMP trap to simulator via CyberController.

    Requires cc_admin or admin role.

    Args:
        cc_ip: CyberController IP address
        simulator_ip: Target simulator IP address
        payload: SNMP trap configuration (with 'traps' array)
        _current_user: Authenticated user with cc_admin or admin role

    Returns:
        ReporterResponse with success status and message
    """
    try:
        # Convert Pydantic model to dict
        # exclude_none=True ensures only provided fields are included,
        # allowing defaults in attack_traps.py to work correctly
        trap_data = payload.model_dump(exclude_none=True)

        # Validate trap_data structure
        if not trap_data or 'traps' not in trap_data:
            logger.error("Invalid trap_data: missing 'traps' key")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid trap data: 'traps' key is required"
            )

        if not isinstance(trap_data['traps'], list) or not trap_data['traps']:
            logger.error("Invalid trap_data: 'traps' must be a non-empty list")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid trap data: 'traps' must be a non-empty list"
            )

        # Call attack_traps module directly
        logger.info(f"Sending {len(trap_data['traps'])} trap(s) from {simulator_ip} to {cc_ip}")
        success_count, failed_count, total_count = attack_traps.send_attack_traps(
            cc_ip, simulator_ip, trap_data
        )

        # Report accurate results
        if success_count > 0 and failed_count == 0:
            message = f"Successfully sent all {success_count} trap(s)"
            logger.info(message)
            return ReporterResponse(success=True, message=message)
        elif success_count > 0 and failed_count > 0:
            message = f"Partially successful: {success_count} succeeded, {failed_count} failed"
            logger.warning(message)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=message
            )
        else:
            message = f"Failed to send all {total_count} trap(s)"
            logger.error(message)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=message
            )

    except HTTPException:
        raise
    except KeyError as exc:
        logger.error(f"Invalid trap configuration: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid trap configuration: missing key {exc!s}"
        )
    except Exception as exc:
        logger.exception(f"Failed to send SNMP traps: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send SNMP trap: {exc!s}"
        )


@router.post(
    "/cc/{cc_ip}/simulators/{simulator_ip}/reporter/polling",
    status_code=status.HTTP_200_OK,
    response_model=ReporterResponse,
)
async def set_polling_config(
        cc_ip: str,
        simulator_ip: str,
        payload: ReporterPollingPayload,
        _current_user: User = Depends(require_cc_access),
        sapro_handler: SaproCommunicationHandler = Depends(get_sapro_handler),
) -> ReporterResponse:
    """Send polling configuration to simulator via CyberController.

    Requires cc_admin or admin role.

    Args:
        cc_ip: CyberController IP address
        simulator_ip: Target simulator IP address
        payload: Polling configuration
        _current_user: Authenticated user with cc_admin or admin role
        sapro_handler: Sapro communication handler instance

    Returns:
        ReporterResponse with success status and message
    """
    # TODO: integrate with real polling module when implemented
    logger.warning("Polling configuration functionality not yet implemented")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Polling functionality not implemented yet"
    )


@router.post(
    "/cc/{cc_ip}/simulators/{simulator_ip}/reporter/irp",
    status_code=status.HTTP_200_OK,
    response_model=ReporterResponse,
)
async def send_irp_messages_endpoint(
        cc_ip: str,
        simulator_ip: str,
        payload: IRPSendPayload,
        _current_user: User = Depends(require_cc_access),
        mongo_db=Depends(get_mongo_db),
) -> ReporterResponse:
    """Send an IRP message based on a stored IdsDataFormat schema in MongoDB.

    Body fields: mongo_id, message_id, message_data, from_ip, to_ip
    """
    try:
        schema_obj = load_schema_from_mongo(mongo_db, payload.mongo_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except KeyError as ke:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ke))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to load schema: {exc!s}")

    try:
        results = send_irp_messages(schema_obj, payload.message_data, simulator_ip, cc_ip)
        if isinstance(results, dict):
            # Success: return per-message results
            return ReporterResponse(success=True, message="IRP messages processed", messages=results)
        else:
            # Overall failure
            success, error_msg = results
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to send IRP messages: {exc!s}")


@router.post(
    "/cc/{cc_ip}/irp/template",
    status_code=status.HTTP_200_OK,
)
async def create_irp_template_endpoint(
        payload: IRPTemplatePayload,
        _current_user: User = Depends(require_cc_access),
        mongo_db=Depends(get_mongo_db),
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
        from backend.app.modules.reporter.irp.tools.template_generator import TemplateGenerator
        tg = TemplateGenerator(schema_obj.schema)

        # Use new method that generates both template and metadata
        result = tg.generate_template_with_metadata(payload.message_id, interactive=False)

        # Get message name
        message_id_str = str(payload.message_id)
        message_name = "Unknown"
        if hasattr(schema_obj.schema, 'messages') and message_id_str in schema_obj.schema.messages:
            msg_obj = schema_obj.schema.messages[message_id_str]
            message_name = getattr(msg_obj, 'name', 'Unknown')

        return {
            "success": True,
            "name": message_name,
            "template": result["template"],
            "schema": result["schema"]
        }
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message ID not found")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Template generation failed: {exc!s}")


# IRP Template Management
@router.post("/cc/{cc_ip}/irp/templates")
async def save_irp_template(
    cc_ip: str,
    template_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Save an IRP message template"""
    try:
        db = get_mongo_db()

        template_doc = {
            "user_id": current_user.get("sub") or current_user.get("id"),
            "cc_ip": cc_ip,
            "name": template_data["name"],
            "schema_id": template_data["schema_id"],
            "schema_name": template_data["schema_name"],
            "messages": template_data.get("messages", {}),
            "created_at": datetime.now(timezone.utc)
        }

        result = db.irp_templates.insert_one(template_doc)

        return {
            "success": True,
            "template_id": str(result.inserted_id),
            "message": "Template saved successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save template: {str(e)}")


@router.get("/cc/{cc_ip}/irp/templates")
async def list_irp_templates(
    cc_ip: str,
    current_user: dict = Depends(get_current_user)
):
    """List all IRP templates for current user and CC"""
    try:
        db = get_mongo_db()

        templates = list(db.irp_templates.find(
            {"user_id": current_user.get("sub") or current_user.get("id"), "cc_ip": cc_ip},
            {"_id": 1, "name": 1, "schema_name": 1, "created_at": 1}
        ))

        # Convert ObjectId to string
        for template in templates:
            template["id"] = str(template.pop("_id"))

        return {"success": True, "templates": templates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {str(e)}")


@router.get("/cc/{cc_ip}/irp/templates/{template_id}")
async def load_irp_template(
    cc_ip: str,
    template_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Load a specific IRP template"""
    try:
        from bson import ObjectId
        db = get_mongo_db()

        template = db.irp_templates.find_one({
            "_id": ObjectId(template_id),
            "user_id": current_user.get("sub") or current_user.get("id"),
            "cc_ip": cc_ip
        })

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        template["id"] = str(template.pop("_id"))

        return {"success": True, "template": template}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load template: {str(e)}")


@router.delete("/cc/{cc_ip}/irp/templates/{template_id}")
async def delete_irp_template(
    cc_ip: str,
    template_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete an IRP template"""
    try:
        from bson import ObjectId
        db = get_mongo_db()

        result = db.irp_templates.delete_one({
            "_id": ObjectId(template_id),
            "user_id": current_user.get("sub") or current_user.get("id"),
            "cc_ip": cc_ip
        })

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Template not found")

        return {"success": True, "message": "Template deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete template: {str(e)}")


__all__ = ["router"]
