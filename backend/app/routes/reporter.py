"""
Reporter routes for CyberController simulators.

## SNMP Endpoints:
- POST   /api/cc/{cc_ip}/simulators/{simulator_ip}/reporter/snmp         -> Send SNMP trap to simulator
- POST   /api/cc/{cc_ip}/simulators/{simulator_ip}/reporter/snmp/stream  -> Stream SNMP traps to simulator
- POST   /api/reporter/snmp/import-from-pcap                             -> Import SNMP traps from PCAP file

## IRP Endpoints:
- POST   /api/cc/{cc_ip}/simulators/{simulator_ip}/reporter/irp          -> Send IRP message to simulator
- POST   /api/cc/{cc_ip}/simulators/{simulator_ip}/q
   -> Stream IRP messages to simulator
- POST   /api/cc/{cc_ip}/irp/template                                    -> Generate IRP template from schema
- POST   /api/reporter/irp/test-message                                  -> Test IRP message parsing
- POST   /api/reporter/irp/analyze-pcap                                  -> Analyze IRP messages in PCAP file

## IRP Template Management:
- POST   /api/cc/{cc_ip}/irp/templates                   -> Create IRP template
- GET    /api/cc/{cc_ip}/irp/templates                   -> List all IRP templates
- GET    /api/cc/{cc_ip}/irp/templates/{template_id}     -> Get specific IRP template
- DELETE /api/cc/{cc_ip}/irp/templates/{template_id}     -> Delete IRP template

## Polling Configuration:
- GET    /api/cc/{cc_ip}/reporter/polling/structures                           -> List all polling structure templates
- GET    /api/cc/{cc_ip}/reporter/polling/structures/{structure_id}            -> Get specific polling structure
- POST   /api/cc/{cc_ip}/reporter/polling/save-xmf                             -> Save XMF file only (no load)
- POST   /api/cc/{cc_ip}/simulators/{simulator_ip}/reporter/polling            -> Save XMF and load to simulator (supports comma-separated IPs)

## Polling Template Management:
- POST   /api/cc/{cc_ip}/polling/templates                 -> Create polling template
- GET    /api/cc/{cc_ip}/polling/templates                 -> List all polling templates
- GET    /api/cc/{cc_ip}/polling/templates/{template_id}   -> Get specific polling template
- DELETE /api/cc/{cc_ip}/polling/templates/{template_id}   -> Delete polling template

All endpoints require 'cc_admin' or 'admin' role (enforced via require_cc_access).
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import os
import queue
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from backend.app.models.polling import PollingTemplateCreate, EndpointConfig
from backend.app.models.snmp_loop import SNMPLoopConfig, SNMPLoopStatus, SNMPLoopStartRequest
from backend.app.models.irp_loop import IRPLoopConfig, IRPLoopStatus, IRPLoopStartRequest
from backend.app.models.user import User
from backend.app.modules.reporter.irp.core.message_testing_coordinator import (
    MessageTestingCoordinator,
)
from backend.app.modules.reporter.irp.irp_module import (
    load_schema_from_mongo,
    send_irp_messages,
)
from backend.app.modules.reporter.irp.irp_module import send_irp_messages_with_progress
from backend.app.modules.reporter.irp.tools.irp_pcap_analyzer import (
    analyze_irp_pcap_file,
)
from backend.app.modules.reporter.irp.tools.template_generator import TemplateGenerator
from backend.app.modules.reporter.polling.polling_service import PollingService
from backend.app.modules.reporter.snmp import attack_traps
from backend.app.modules.reporter.snmp.attack_traps import (
    send_attack_traps_with_progress,
)
from backend.app.modules.sapro.sapro_client import (
    get_sapro_handler,
    SaproCommunicationHandler,
)
from backend.app.schemas.reporter import (
    ReporterSNMPPayload,
    ReporterPollingPayload,
    ReporterResponse,
    IRPPcapAnalysisResponse,
    IRPSendPayload,
    IRPTemplatePayload,
)
from backend.app.modules.reporter.snmp.snmp_loop_manager import get_loop_manager
from backend.app.modules.reporter.map_resolver import get_simulator_map
from backend.app.utils.auth import require_cc_access, get_current_user
from backend.app.utils.database import get_db, get_mongo_db
from backend.app.utils.pcap_converter import pcap_to_traps, PcapParseError

router = APIRouter(prefix="/api", tags=["reporter"])
logger = logging.getLogger("sim-tools.reporter")

# Module-level executor for blocking PCAP parsing
_executor = ThreadPoolExecutor(max_workers=2)


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
    sapro_handler: SaproCommunicationHandler = Depends(get_sapro_handler),
    db=Depends(get_db),
) -> ReporterResponse:
    """Send SNMP trap to simulator(s) via CyberController.

    Requires cc_admin or admin role.

    Args:
        cc_ip: CyberController IP address
        simulator_ip: Target simulator IP address(es) - single IP or comma-separated list
        payload: SNMP trap configuration (with 'traps' array and 'map')
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
        if not trap_data or "traps" not in trap_data:
            logger.error("Invalid trap_data: missing 'traps' key")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid trap data: 'traps' key is required",
            )

        if not isinstance(trap_data["traps"], list) or not trap_data["traps"]:
            logger.error("Invalid trap_data: 'traps' must be a non-empty list")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid trap data: 'traps' must be a non-empty list",
            )

        # Resolve map names to full paths
        # Admin users have workspace='*'; convert to 'default' to avoid
        # find_map_workspace misidentifying the /opt/sapro/map/ directory as a workspace.
        workspace = _current_user.workspace
        if workspace == "*":
            workspace = "default"

        # Check if multiple simulators (comma-separated)
        if "," in simulator_ip:
            simulator_ips = [ip.strip() for ip in simulator_ip.split(",")]
            logger.info(f"Processing multiple simulators: {simulator_ips}")

            # Handle map field - convert to dict if needed
            map_dict = {}
            map_value = trap_data.get("map")
            if isinstance(map_value, dict):
                map_dict = map_value
            else:
                # Single map string or empty - resolve per simulator
                for sim_ip in simulator_ips:
                    map_dict[sim_ip] = map_value

            # Resolve map names - look up from DB if not provided
            for sim_ip in simulator_ips:
                map_name = get_simulator_map(db, sim_ip, map_dict.get(sim_ip))
                map_dict[sim_ip] = sapro_handler.get_full_map_path(map_name, workspace)

            # Extract per-simulator traps (different attack IDs per simulator)
            per_simulator_traps = trap_data.pop("per_simulator_traps", None)

            # Process all simulators in parallel
            async def send_to_simulator(sim_ip: str):
                sim_trap_data = trap_data.copy()
                sim_trap_data["map"] = map_dict.get(sim_ip)
                if per_simulator_traps and sim_ip in per_simulator_traps:
                    sim_trap_data["traps"] = per_simulator_traps[sim_ip]
                return attack_traps.send_attack_traps(cc_ip, sim_ip, sim_trap_data)

            # Execute in parallel
            results = await asyncio.gather(
                *[send_to_simulator(sim_ip) for sim_ip in simulator_ips],
                return_exceptions=True,
            )

            # Aggregate results
            total_success = 0
            total_failed = 0
            total_count = 0
            errors = []

            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Simulator {simulator_ips[idx]} failed: {result}")
                    errors.append(f"{simulator_ips[idx]}: {str(result)}")
                    total_failed += len(trap_data["traps"])
                    total_count += len(trap_data["traps"])
                else:
                    success_count, failed_count, count = result
                    total_success += success_count
                    total_failed += failed_count
                    total_count += count

            # Report aggregated results
            if total_success > 0 and total_failed == 0:
                message = f"Successfully sent all {total_success} trap(s) to {len(simulator_ips)} simulator(s)"
                logger.info(message)
                return ReporterResponse(success=True, message=message)
            elif total_success > 0 and total_failed > 0:
                message = f"Partially successful: {total_success} succeeded, {total_failed} failed across {len(simulator_ips)} simulator(s)"
                if errors:
                    message += f". Errors: {'; '.join(errors)}"
                logger.warning(message)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message
                )
            else:
                message = f"Failed to send all {total_count} trap(s) to {len(simulator_ips)} simulator(s)"
                if errors:
                    message += f". Errors: {'; '.join(errors)}"
                logger.error(message)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message
                )
        else:
            # Single simulator (backward compatible)
            # Handle map field
            map_value = trap_data.get("map")
            if isinstance(map_value, dict):
                # Dict provided but only one simulator - extract map for this simulator
                map_name = map_value.get(simulator_ip)
            else:
                map_name = map_value

            # Get map from DB if not provided
            map_name = get_simulator_map(db, simulator_ip, map_name)
            # Resolve map name to full path
            trap_data["map"] = sapro_handler.get_full_map_path(map_name, workspace)

            # Use per-simulator traps if provided
            per_simulator_traps = trap_data.pop("per_simulator_traps", None)
            if per_simulator_traps and simulator_ip in per_simulator_traps:
                trap_data["traps"] = per_simulator_traps[simulator_ip]

            # Call attack_traps module directly
            logger.info(
                f"Sending {len(trap_data['traps'])} trap(s) from {simulator_ip} to {cc_ip}"
            )
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
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message
                )
            else:
                message = f"Failed to send all {total_count} trap(s)"
                logger.error(message)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message
                )

    except HTTPException:
        raise
    except KeyError as exc:
        logger.error(f"Invalid trap configuration: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid trap configuration: missing key {exc!s}",
        )
    except Exception as exc:
        logger.exception(f"Failed to send SNMP traps: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send SNMP trap: {exc!s}",
        )


@router.get(
    "/cc/{cc_ip}/reporter/polling/structures",
    status_code=status.HTTP_200_OK,
)
async def list_polling_structures(
    cc_ip: str,
    _current_user: User = Depends(require_cc_access),
    mongo_db=Depends(get_mongo_db),
) -> list:
    """List all available polling structure templates.

    Requires cc_admin or admin role.

    Args:
        cc_ip: CyberController IP address
        _current_user: Authenticated user with cc_admin or admin role
        mongo_db: MongoDB database instance

    Returns:
        List of all polling structure templates
    """
    try:
        collection = mongo_db["polling_structures"]
        structures = list(collection.find({}))

        # Convert ObjectId to string
        for structure in structures:
            structure["_id"] = str(structure["_id"])

        logger.info(f"Retrieved {len(structures)} polling structure templates")
        return structures

    except Exception as exc:
        logger.exception(f"Failed to list polling structures: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list polling structures: {exc!s}",
        )


@router.get(
    "/cc/{cc_ip}/reporter/polling/structures/{structure_id}",
    status_code=status.HTTP_200_OK,
)
async def get_polling_structure(
    cc_ip: str,
    structure_id: str,
    _current_user: User = Depends(require_cc_access),
    mongo_db=Depends(get_mongo_db),
) -> dict:
    """Get a specific polling structure template by structure_id.

    Requires cc_admin or admin role.

    Args:
        cc_ip: CyberController IP address
        structure_id: Structure identifier (e.g., 'attack_data')
        _current_user: Authenticated user with cc_admin or admin role
        mongo_db: MongoDB database instance

    Returns:
        Polling structure template
    """
    try:
        collection = mongo_db["polling_structures"]
        structure = collection.find_one({"structure_id": structure_id})

        if not structure:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Polling structure not found: {structure_id}",
            )

        # Convert ObjectId to string
        structure["_id"] = str(structure["_id"])

        logger.info(f"Retrieved polling structure: {structure_id}")
        return structure

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to get polling structure: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get polling structure: {exc!s}",
        )


@router.post(
    "/cc/{cc_ip}/polling/templates",
    status_code=status.HTTP_200_OK,
)
async def create_polling_template(
    cc_ip: str,
    template: dict,
    _current_user: User = Depends(require_cc_access),
    mongo_db=Depends(get_mongo_db),
    sapro_handler: SaproCommunicationHandler = Depends(get_sapro_handler),
):
    """Create a new polling template.

    Requires cc_admin or admin role.

    Args:
        cc_ip: CyberController IP address
        template: Template data (name, description, endpoint config)
        _current_user: Authenticated user with cc_admin or admin role
        mongo_db: MongoDB database instance
        sapro_handler: Sapro communication handler instance

    Returns:
        Success response with template ID
    """
    try:

        service = PollingService(mongo_db, sapro_handler)
        template_obj = PollingTemplateCreate(**template)

        template_id = await service.create_template(template_obj)

        return {
            "success": True,
            "template_id": template_id,
            "message": "Template created successfully",
        }

    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        logger.exception(f"Failed to create polling template: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create polling template: {exc!s}",
        )


@router.get(
    "/cc/{cc_ip}/polling/templates",
    status_code=status.HTTP_200_OK,
)
async def list_polling_templates(
    cc_ip: str,
    _current_user: User = Depends(require_cc_access),
    mongo_db=Depends(get_mongo_db),
    sapro_handler: SaproCommunicationHandler = Depends(get_sapro_handler),
):
    """List all polling templates.

    Requires cc_admin or admin role.

    Args:
        cc_ip: CyberController IP address
        _current_user: Authenticated user with cc_admin or admin role
        mongo_db: MongoDB database instance
        sapro_handler: Sapro communication handler instance

    Returns:
        List of template summaries
    """
    try:

        service = PollingService(mongo_db, sapro_handler)
        templates = await service.list_templates()

        return {"success": True, "templates": templates}

    except Exception as exc:
        logger.exception(f"Failed to list polling templates: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list polling templates: {exc!s}",
        )


@router.get(
    "/cc/{cc_ip}/polling/templates/{template_id}",
    status_code=status.HTTP_200_OK,
)
async def get_polling_template(
    cc_ip: str,
    template_id: str,
    _current_user: User = Depends(require_cc_access),
    mongo_db=Depends(get_mongo_db),
    sapro_handler: SaproCommunicationHandler = Depends(get_sapro_handler),
):
    """Get polling template details by ID.

    Requires cc_admin or admin role.

    Args:
        cc_ip: CyberController IP address
        template_id: MongoDB template ID
        _current_user: Authenticated user with cc_admin or admin role
        mongo_db: MongoDB database instance
        sapro_handler: Sapro communication handler instance

    Returns:
        Full template details
    """
    try:

        service = PollingService(mongo_db, sapro_handler)
        template = await service.get_template(template_id)

        # Convert ObjectId to string
        template["_id"] = str(template["_id"])

        return {"success": True, "template": template}

    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as exc:
        logger.exception(f"Failed to get polling template: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get polling template: {exc!s}",
        )


@router.delete(
    "/cc/{cc_ip}/polling/templates/{template_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_polling_template(
    cc_ip: str,
    template_id: str,
    _current_user: User = Depends(require_cc_access),
    mongo_db=Depends(get_mongo_db),
    sapro_handler: SaproCommunicationHandler = Depends(get_sapro_handler),
):
    """Delete a polling template.

    Requires cc_admin or admin role.

    Args:
        cc_ip: CyberController IP address
        template_id: MongoDB template ID
        _current_user: Authenticated user with cc_admin or admin role
        mongo_db: MongoDB database instance
        sapro_handler: Sapro communication handler instance

    Returns:
        Success response
    """
    try:

        service = PollingService(mongo_db, sapro_handler)
        deleted = await service.delete_template(template_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )

        return {"success": True, "message": "Template deleted successfully"}

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to delete polling template: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete polling template: {exc!s}",
        )


@router.post(
    "/cc/{cc_ip}/reporter/polling/save-xmf",
    status_code=status.HTTP_200_OK,
    response_model=ReporterResponse,
)
async def save_xmf_to_simulator(
    cc_ip: str,
    payload: ReporterPollingPayload,
    current_user: User = Depends(require_cc_access),
    mongo_db=Depends(get_mongo_db),
    sapro_handler: SaproCommunicationHandler = Depends(get_sapro_handler),
) -> ReporterResponse:
    """Save XMF file to Sapro filesystem (does NOT load to simulator).

    Requires cc_admin or admin role.

    Args:
        cc_ip: CyberController IP address
        payload: Polling payload with template_id or endpoint_config and xmf_filename
        current_user: Authenticated user with cc_admin or admin role
        mongo_db: MongoDB database instance
        sapro_handler: Sapro communication handler instance

    Returns:
        ReporterResponse with success status and file path
    """
    try:

        service = PollingService(mongo_db, sapro_handler)

        # Generate XMF content
        if payload.template_id:
            xmf_content = await service.generate_xmf_from_template(payload.template_id)
        elif payload.endpoints:
            # Convert dict to EndpointConfig objects
            endpoints = [EndpointConfig(**ep) for ep in payload.endpoints]
            xmf_content = await service.generate_xmf_from_endpoints(endpoints)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either template_id or endpoints must be provided",
            )

        # Write XMF to filesystem
        workspace = current_user.workspace if (current_user.workspace and current_user.workspace != "*") else "default"
        success, result = service._write_xmf_to_filesystem(
            xmf_content, payload.xmf_filename, workspace, payload.overwrite
        )

        if not success:
            # Check if file exists and user didn't allow overwrite
            if result.startswith("FILE_EXISTS:"):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save XMF file: {result}",
            )

        return ReporterResponse(
            success=True, message=f"XMF file saved successfully: {result}"
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to save XMF file: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save XMF file: {exc!s}",
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
    current_user: User = Depends(require_cc_access),
    mongo_db=Depends(get_mongo_db),
    sapro_handler: SaproCommunicationHandler = Depends(get_sapro_handler),
    db=Depends(get_db),
) -> ReporterResponse:
    """Set polling configuration on simulator(s) (saves XMF and loads to device).

    This is the full flow that:
    1. Generates XMF from template or config
    2. Saves XMF to Sapro filesystem (once for all simulators)
    3. Creates DeviceMap XML
    4. Loads to simulator(s) via update_device()
    5. Simulator starts responding immediately

    Supports multiple simulators via comma-separated IPs (e.g., "192.168.1.1,192.168.1.2").
    When using multiple simulators, payload.map can be:
    - Dict mapping each IP to its map: {"192.168.1.1": "map1", "192.168.1.2": "map2"}
    - Single string (same map for all): "map1"

    Requires cc_admin or admin role.

    Args:
        cc_ip: CyberController IP address
        simulator_ip: Target simulator IP address (or comma-separated IPs for multiple)
        payload: Polling payload with template_id or endpoints, xmf_filename, and map (string or dict)
        current_user: Authenticated user with cc_admin or admin role
        mongo_db: MongoDB database instance
        sapro_handler: Sapro communication handler instance

    Returns:
        ReporterResponse with success status and message
    """
    try:
        service = PollingService(mongo_db, sapro_handler)

        # Generate XMF content once
        if payload.template_id:
            xmf_content = await service.generate_xmf_from_template(payload.template_id)
        elif payload.endpoints:
            # Convert dict to EndpointConfig objects
            endpoints = [EndpointConfig(**ep) for ep in payload.endpoints]
            xmf_content = await service.generate_xmf_from_endpoints(endpoints)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either template_id or endpoints must be provided",
            )

        # Check if multiple simulators (comma-separated)
        if "," in simulator_ip:
            simulator_ips = [ip.strip() for ip in simulator_ip.split(",")]
            logger.info(f"Loading polling config to multiple simulators: {simulator_ips}")

            # Handle map field - convert to dict if needed (matches SNMP pattern)
            map_dict = {}
            if isinstance(payload.map, dict):
                map_dict = payload.map
            else:
                # Single map string or empty - resolve per simulator
                for sim_ip in simulator_ips:
                    map_dict[sim_ip] = payload.map

            workspace = current_user.workspace if (current_user.workspace and current_user.workspace != "*") else "default"
            results = []
            write_xmf = payload.write_xmf if hasattr(payload, 'write_xmf') and payload.write_xmf is not None else True
            overwrite = payload.overwrite if hasattr(payload, 'overwrite') and payload.overwrite is not None else False

            # Write XMF once if needed
            if write_xmf:
                # Use first simulator's map path for writing XMF
                first_sim_ip = simulator_ips[0]
                first_map_name = get_simulator_map(db, first_sim_ip, map_dict.get(first_sim_ip))

                try:
                    first_map_path = sapro_handler.get_full_map_path(first_map_name, workspace)
                except Exception as e:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to get map path: {e}",
                    )

                # Write XMF file once
                success, message = await service.load_xmf_to_simulator(
                    device_ip=first_sim_ip,
                    xmf_content=xmf_content,
                    xmf_filename=payload.xmf_filename,
                    map_path=first_map_path,
                    workspace=workspace,
                    overwrite=overwrite,
                    write_xmf=True,
                )

                if not success:
                    # Check if file exists and user didn't allow overwrite
                    if message.startswith("FILE_EXISTS:"):
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message
                    )

            # Load XMF to each simulator
            for sim_ip in simulator_ips:
                try:
                    map_name = get_simulator_map(db, sim_ip, map_dict.get(sim_ip))
                except HTTPException as e:
                    results.append({
                        "simulator_ip": sim_ip,
                        "success": False,
                        "message": e.detail
                    })
                    continue

                try:
                    map_path = sapro_handler.get_full_map_path(map_name, workspace)
                except Exception as e:
                    results.append({
                        "simulator_ip": sim_ip,
                        "success": False,
                        "message": f"Failed to get map path: {e}"
                    })
                    continue

                success, message = await service.load_xmf_to_simulator(
                    device_ip=sim_ip,
                    xmf_content=xmf_content,
                    xmf_filename=payload.xmf_filename,
                    map_path=map_path,
                    workspace=workspace,
                    overwrite=overwrite,
                    write_xmf=False,  # XMF already written above
                )

                results.append({
                    "simulator_ip": sim_ip,
                    "success": success,
                    "message": message
                })

            # Summarize results
            successes = sum(1 for r in results if r["success"])
            failures = len(results) - successes

            if failures == 0:
                return ReporterResponse(
                    success=True,
                    message=f"Polling configuration loaded successfully to all {successes} simulator(s)"
                )
            elif successes > 0:
                return ReporterResponse(
                    success=True,
                    message=f"Loaded to {successes} simulator(s), failed for {failures} simulator(s)"
                )
            else:
                # All failed
                error_messages = [f"{r['simulator_ip']}: {r['message']}" for r in results if not r['success']]
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to load to all simulators: {'; '.join(error_messages)}"
                )

        else:
            # Single simulator (original logic)
            # Load XMF to simulator
            # Get map from payload or database
            if isinstance(payload.map, dict):
                map_name = payload.map.get(simulator_ip)
            else:
                map_name = payload.map

            map_name = get_simulator_map(db, simulator_ip, map_name)
            workspace = current_user.workspace if (current_user.workspace and current_user.workspace != "*") else "default"

            # Get full map path once at route level
            try:
                map_path = sapro_handler.get_full_map_path(map_name, workspace)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to get map path: {e}",
                )

            success, message = await service.load_xmf_to_simulator(
                device_ip=simulator_ip,
                xmf_content=xmf_content,
                xmf_filename=payload.xmf_filename,
                map_path=map_path,
                workspace=workspace,
                overwrite=payload.overwrite if hasattr(payload, 'overwrite') and payload.overwrite is not None else False,
                write_xmf=payload.write_xmf if hasattr(payload, 'write_xmf') and payload.write_xmf is not None else True,
            )

            if not success:
                # Check if file exists and user didn't allow overwrite
                if message.startswith("FILE_EXISTS:"):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message
                )

            return ReporterResponse(success=True, message=message)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to set polling configuration: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set polling configuration: {exc!s}",
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

    Supports multiple simulators via comma-separated IPs in simulator_ip parameter.
    """
    try:
        schema_obj = load_schema_from_mongo(mongo_db, payload.mongo_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except KeyError as ke:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ke))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load schema: {exc!s}",
        )

    try:
        # Check if multiple simulators (comma-separated)
        if "," in simulator_ip:
            simulator_ips = [ip.strip() for ip in simulator_ip.split(",")]
            logger.info(f"Processing multiple simulators for IRP: {simulator_ips}")

            # Process all simulators in parallel (IRP doesn't need different maps)
            async def send_to_simulator(sim_ip: str):
                try:
                    # Use per-simulator data if available, else shared message_data
                    sim_message_data = payload.per_simulator_data[sim_ip] if payload.per_simulator_data and sim_ip in payload.per_simulator_data else payload.message_data
                    return send_irp_messages(
                        schema_obj, sim_message_data, sim_ip, cc_ip
                    )
                except Exception as e:
                    logger.error(f"Error sending to {sim_ip}: {e}")
                    return {"error": f"Failed to send to {sim_ip}: {str(e)}"}

            # Execute in parallel
            results_list = await asyncio.gather(
                *[send_to_simulator(sim_ip) for sim_ip in simulator_ips],
                return_exceptions=True,
            )

            # Aggregate results
            all_success = True
            any_success = False
            aggregated_results = {}
            errors = []

            for idx, result in enumerate(results_list):
                sim_ip = simulator_ips[idx]
                if isinstance(result, Exception):
                    logger.error(f"Simulator {sim_ip} failed: {result}")
                    errors.append(f"{sim_ip}: {str(result)}")
                    all_success = False
                    aggregated_results[sim_ip] = {"error": str(result)}
                elif isinstance(result, dict):
                    # Check if this is an error dict or results dict
                    if "error" in result:
                        all_success = False
                        errors.append(f"{sim_ip}: {result['error']}")
                        aggregated_results[sim_ip] = result
                    else:
                        # Regular results dict: { message_name: [bool_success, message_or_error] }
                        sim_all_success = True
                        sim_any_success = False
                        for k, v in result.items():
                            try:
                                ok = bool(v[0])
                            except Exception:
                                ok = False
                            if ok:
                                sim_any_success = True
                                any_success = True
                            else:
                                sim_all_success = False
                                all_success = False
                        aggregated_results[sim_ip] = result
                else:
                    # Unexpected format
                    all_success = False
                    aggregated_results[sim_ip] = {"error": "Unexpected result format"}

            # Report aggregated results
            if all_success:
                message = f"All IRP messages sent successfully to {len(simulator_ips)} simulator(s)"
                logger.info(message)
                return ReporterResponse(
                    success=True, message=message, messages=aggregated_results
                )
            elif not any_success:
                # All failed - treat as server error
                message = (
                    f"All IRP messages failed for {len(simulator_ips)} simulator(s)"
                )
                if errors:
                    message += f". Errors: {'; '.join(errors)}"
                logger.error(message)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message
                )
            else:
                # Mixed results - partial success
                message = (
                    f"Partial IRP results across {len(simulator_ips)} simulator(s)"
                )
                if errors:
                    message += f". Errors: {'; '.join(errors)}"
                logger.warning(message)
                return ReporterResponse(
                    success=False, message=message, messages=aggregated_results
                )
        else:
            # Single simulator (backward compatible)
            sim_message_data = payload.per_simulator_data[simulator_ip] if payload.per_simulator_data and simulator_ip in payload.per_simulator_data else payload.message_data
            results = send_irp_messages(
                schema_obj, sim_message_data, simulator_ip, cc_ip
            )
            if isinstance(results, dict):
                # The results dict contains per-message tuples/lists like: { name: [bool_success, message_or_error] }
                all_success = True
                any_success = False
                for k, v in results.items():
                    try:
                        ok = bool(v[0])
                    except Exception:
                        ok = False
                    if ok:
                        any_success = True
                    else:
                        all_success = False

                if all_success:
                    logger.info("All IRP messages succeeded")
                    return ReporterResponse(
                        success=True,
                        message="All IRP messages sent successfully",
                        messages=results,
                    )
                if not any_success:
                    # All failed - treat as server error
                    logger.error(f"All IRP messages failed: {results}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"All IRP messages failed: {results}",
                    )

                # Mixed results - partial success
                logger.warning(f"Partial IRP results: {results}")
                return ReporterResponse(
                    success=False,
                    message="Partial failure sending IRP messages",
                    messages=results,
                )
            else:
                # Overall failure
                success, error_msg = results
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send IRP messages: {exc!s}",
        )


@router.post("/cc/{cc_ip}/simulators/{simulator_ip}/reporter/irp/stream")
async def send_irp_messages_stream_endpoint(
    cc_ip: str,
    simulator_ip: str,
    payload: IRPSendPayload,
    _current_user: User = Depends(require_cc_access),
    mongo_db=Depends(get_mongo_db),
):
    """Send IRP messages with real-time progress via Server-Sent Events.

    Supports multiple simulators via comma-separated IPs. Progress events include simulator_ip field.
    """
    try:
        schema_obj = load_schema_from_mongo(mongo_db, payload.mongo_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except KeyError as ke:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ke))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load schema: {exc!s}",
        )

    try:
        message_data = payload.message_data
        per_simulator_data = payload.per_simulator_data

        # Check if multiple simulators (comma-separated)
        if "," in simulator_ip:
            simulator_ips = [ip.strip() for ip in simulator_ip.split(",")]
            logger.info(
                f"Streaming IRP messages to multiple simulators: {simulator_ips}"
            )

            async def event_generator():
                try:
                    # Create async generators for each simulator
                    async def simulator_generator(sim_ip: str):
                        try:
                            sim_message_data = per_simulator_data[sim_ip] if per_simulator_data and sim_ip in per_simulator_data else message_data
                            for progress in send_irp_messages_with_progress(
                                schema_obj, sim_message_data, sim_ip, cc_ip
                            ):
                                # Add simulator_ip to progress event
                                progress["simulator_ip"] = sim_ip
                                yield progress
                        except Exception as exc:
                            logger.exception(f"Error streaming to {sim_ip}: {exc}")
                            yield {
                                "type": "error",
                                "simulator_ip": sim_ip,
                                "message": str(exc),
                            }

                    # Interleave events from all simulators
                    event_queue = queue.Queue()
                    completed_simulators = set()

                    # Run all generators in parallel
                    async def run_generator(sim_ip: str):
                        async for event in simulator_generator(sim_ip):
                            event_queue.put(event)
                        completed_simulators.add(sim_ip)

                    # Start all tasks
                    tasks = [
                        asyncio.create_task(run_generator(sim_ip))
                        for sim_ip in simulator_ips
                    ]

                    # Yield events as they arrive
                    while len(completed_simulators) < len(simulator_ips):
                        try:
                            event = event_queue.get(timeout=0.1)
                            yield f"data: {json.dumps(event)}\n\n"
                        except queue.Empty:
                            await asyncio.sleep(0.1)
                            continue

                    # Wait for all tasks to complete
                    await asyncio.gather(*tasks, return_exceptions=True)

                    # Drain remaining events
                    while not event_queue.empty():
                        event = event_queue.get()
                        yield f"data: {json.dumps(event)}\n\n"

                except Exception as exc:
                    logger.exception(f"Error during IRP message streaming: {exc}")
                    error_event = {"type": "error", "message": str(exc)}
                    yield f"data: {json.dumps(error_event)}\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        else:
            # Single simulator (backward compatible)
            async def event_generator():
                try:
                    sim_message_data = per_simulator_data[simulator_ip] if per_simulator_data and simulator_ip in per_simulator_data else message_data
                    for progress in send_irp_messages_with_progress(
                        schema_obj, sim_message_data, simulator_ip, cc_ip
                    ):
                        # Add simulator_ip for consistency
                        progress["simulator_ip"] = simulator_ip
                        yield f"data: {json.dumps(progress)}\n\n"
                except Exception as exc:
                    logger.exception(f"Error during IRP message streaming: {exc}")
                    error_event = {
                        "type": "error",
                        "simulator_ip": simulator_ip,
                        "message": str(exc),
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize IRP streaming: {exc!s}",
        )


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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load schema: {exc!s}",
        )

    try:
        tg = TemplateGenerator(schema_obj.schema)

        # Use new method that generates both template and metadata
        result = tg.generate_template_with_metadata(
            payload.message_id, interactive=False
        )

        # Get message name
        message_id_str = str(payload.message_id)
        message_name = "Unknown"
        if (
            hasattr(schema_obj.schema, "messages")
            and message_id_str in schema_obj.schema.messages
        ):
            msg_obj = schema_obj.schema.messages[message_id_str]
            message_name = getattr(msg_obj, "name", "Unknown")

        return {
            "success": True,
            "name": message_name,
            "template": result["template"],
            "schema": result["schema"],
        }
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message ID not found"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Template generation failed: {exc!s}",
        )


# Utility function to sanitize data for MongoDB storage
def sanitize_for_mongo(data: Any) -> Any:
    """
    Recursively sanitize data for MongoDB storage.
    Converts very large integers (> 2^53) to strings to preserve precision.
    MongoDB has limits on integer representation.
    """
    if isinstance(data, dict):
        return {k: sanitize_for_mongo(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_mongo(item) for item in data]
    elif isinstance(data, int):
        # MongoDB safely stores integers up to 2^53 (9007199254740992)
        # For larger integers, convert to string to preserve precision
        if data > 9007199254740992 or data < -9007199254740992:
            return str(data)
        return data
    else:
        return data


def deserialize_from_mongo(data: Any) -> Any:
    """
    Recursively deserialize data from MongoDB storage.
    Converts numeric strings back to integers where appropriate.
    """
    if isinstance(data, dict):
        return {k: deserialize_from_mongo(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [deserialize_from_mongo(item) for item in data]
    elif isinstance(data, str):
        # Try to convert string back to integer if it looks like a number
        try:
            # Check if string is purely numeric (including negative)
            if data.lstrip("-").isdigit():
                return int(data)
        except (ValueError, AttributeError):
            pass
        return data
    else:
        return data


# IRP Template Management
@router.post("/cc/{cc_ip}/irp/templates")
async def save_irp_template(
    cc_ip: str, template_data: dict, current_user: dict = Depends(get_current_user)
):
    """Save an IRP message template"""
    try:
        db = get_mongo_db()

        # Sanitize data to handle large integers
        sanitized_messages = sanitize_for_mongo(template_data.get("messages", {}))

        template_doc = {
            "user_id": current_user.get("sub") or current_user.get("id"),
            "cc_ip": cc_ip,
            "name": template_data["name"],
            "schema_id": template_data["schema_id"],
            "schema_name": template_data["schema_name"],
            "messages": sanitized_messages,
            "created_at": datetime.now(timezone.utc),
        }

        result = db.irp_templates.insert_one(template_doc)

        return {
            "success": True,
            "template_id": str(result.inserted_id),
            "message": "Template saved successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to save template: {str(e)}"
        )


@router.get("/cc/{cc_ip}/irp/templates")
async def list_irp_templates(
    cc_ip: str, current_user: dict = Depends(get_current_user)
):
    """List all IRP templates for current user and CC"""
    try:
        db = get_mongo_db()

        templates = list(
            db.irp_templates.find(
                {
                    "user_id": current_user.get("sub") or current_user.get("id"),
                    "cc_ip": cc_ip,
                },
                {"_id": 1, "name": 1, "schema_name": 1, "created_at": 1},
            )
        )

        # Convert ObjectId to string
        for template in templates:
            template["id"] = str(template.pop("_id"))

        return {"success": True, "templates": templates}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list templates: {str(e)}"
        )


@router.get("/cc/{cc_ip}/irp/templates/{template_id}")
async def load_irp_template(
    cc_ip: str, template_id: str, current_user: dict = Depends(get_current_user)
):
    """Load a specific IRP template"""
    try:
        db = get_mongo_db()

        template = db.irp_templates.find_one(
            {
                "_id": ObjectId(template_id),
                "user_id": current_user.get("sub") or current_user.get("id"),
                "cc_ip": cc_ip,
            }
        )

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        template["id"] = str(template.pop("_id"))

        # Deserialize numeric strings back to integers
        if "messages" in template:
            template["messages"] = deserialize_from_mongo(template["messages"])

        return {"success": True, "template": template}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load template: {str(e)}"
        )


@router.delete("/cc/{cc_ip}/irp/templates/{template_id}")
async def delete_irp_template(
    cc_ip: str, template_id: str, current_user: dict = Depends(get_current_user)
):
    """Delete an IRP template"""
    try:
        db = get_mongo_db()

        result = db.irp_templates.delete_one(
            {
                "_id": ObjectId(template_id),
                "user_id": current_user.get("sub") or current_user.get("id"),
                "cc_ip": cc_ip,
            }
        )

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Template not found")

        return {"success": True, "message": "Template deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete template: {str(e)}"
        )


@router.post("/reporter/irp/test-message")
async def test_irp_message(
    payload: dict, current_user: User = Depends(get_current_user)
):
    """Test IRP message with full e2e workflow (UDP capture + Java parser)."""
    try:

        schema_id = payload.get("schema_id")
        message_id = payload.get("message_id")
        template_data = payload.get("template")

        if not all([schema_id, message_id, template_data]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields: schema_id, message_id, template",
            )

        mongo_db = get_mongo_db()

        # Retrieve stored document to obtain xml_blob and checksum (if available)
        try:
            raw_doc = mongo_db.irp_data_formats.find_one({"_id": ObjectId(schema_id)})
        except Exception as exc:
            logger.exception("Failed to load schema document %s: %s", schema_id, exc)
            raw_doc = None

        if not raw_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schema not found: {schema_id}",
            )

        xml_blob = raw_doc.get("xml_blob")
        xml_checksum = raw_doc.get("xml_checksum")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            captures_dir = temp_path / "captures"
            results_dir = temp_path / "results"

            captures_dir.mkdir(exist_ok=True)
            results_dir.mkdir(exist_ok=True)

            # Determine XML content to use for the parser: prefer stored xml_blob
            xml_file_for_parser = temp_path / "IdsDataFormat.xml"

            used_cached_blob = False
            if xml_blob:
                try:
                    xml_bytes = base64.b64decode(xml_blob)
                    xml_content = xml_bytes.decode("utf-8")
                    xml_file_for_parser.write_text(xml_content)
                    used_cached_blob = True
                    if xml_checksum:
                        logger.debug(
                            f"Using XML blob with checksum: {xml_checksum[:16]}..."
                        )
                    else:
                        logger.debug("Using XML blob (no checksum available)")
                except Exception as exc:
                    # Base64 decode failed - log and fall back to bundled XML file
                    logger.exception(
                        "Failed to decode stored xml_blob for schema %s: %s",
                        schema_id,
                        exc,
                    )
                    used_cached_blob = False

            if not used_cached_blob:
                # Fallback: use local data_formats copy shipped with the repo
                xml_file_source = (
                    Path(__file__).parent.parent
                    / "modules"
                    / "reporter"
                    / "irp"
                    / "data_formats"
                    / "IdsDataFormat100600.xml"
                )

                if not xml_file_source.exists():
                    logger.error(
                        "No xml_blob in schema and local fallback XML not found for schema %s",
                        schema_id,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="DataFormat XML source not available for parsing",
                    )

                # Copy local source to temp parser file
                xml_file_for_parser.write_text(xml_file_source.read_text())
                logger.debug(
                    "Falling back to local data_formats copy for schema %s", schema_id
                )

            # Reconstruct schema object using existing helper
            schema_obj = load_schema_from_mongo(mongo_db, schema_id)

            if not schema_obj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Schema reconstruction failed: {schema_id}",
                )

            coordinator = MessageTestingCoordinator(
                captures_dir=captures_dir, results_dir=results_dir
            )

            result = coordinator.test_message(
                message_id=message_id,
                message_data=template_data,
                schema_obj=schema_obj,
                xml_file_for_parser=str(xml_file_for_parser),
                from_ip="127.0.0.1",
                to_ip="127.0.0.1",
                timeout=30,
            )

            # Always try to read parsed XML, even if test failed
            # This allows users to see parser errors in the XML output
            parsed_xml = None
            for step in result.get("steps", []):
                if step.get("step") == "parse_message" and step.get(
                    "parse_result_file"
                ):
                    parse_file = Path(step["parse_result_file"])
                    if parse_file.exists():
                        try:
                            with open(parse_file, "r") as f:
                                parsed_xml = f.read()
                        except Exception as read_exc:
                            logger.warning(
                                f"Could not read parse result file: {read_exc}"
                            )
                    break

            return {
                "success": result.get("status") == "completed",
                "message": f"Test {'completed' if result.get('status') == 'completed' else 'failed'} for message {message_id}",
                "result": result,
                "parsed_xml": parsed_xml,
            }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Error testing message: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error testing message: {exc!s}",
        )


@router.post("/reporter/snmp/import-from-pcap")
async def import_snmp_from_pcap(
    file: UploadFile = File(...), current_user: dict = Depends(get_current_user)
):
    """Upload a PCAP file and extract SNMP traps."""

    try:
        # Validate file extension
        if not file.filename.lower().endswith(".pcap"):
            raise ValueError("Invalid file format. Please upload a .pcap file.")

        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(suffix=".pcap", delete=False) as tmp_file:
            contents = await file.read()
            tmp_file.write(contents)
            tmp_path = tmp_file.name

        try:
            # Define a blocking wrapper that creates its own event loop in the worker thread
            def _parse_in_thread(path: str, limit: int):
                # pyshark needs an asyncio loop available in the thread where it runs.
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return pcap_to_traps(path, limit)
                finally:
                    # Clean up the loop in the thread
                    try:
                        asyncio.set_event_loop(None)
                    except Exception:
                        pass
                    try:
                        loop.close()
                    except Exception:
                        pass

            # Run PCAP parsing in thread pool to avoid event loop conflict (no trap limit)
            running_loop = asyncio.get_running_loop()
            result = await running_loop.run_in_executor(
                _executor, _parse_in_thread, tmp_path, 999999
            )

            warning = None

            response = {
                "success": True,
                "data": result,
                "message": f"Successfully extracted {result.get('total_returned')} traps from PCAP file.",
            }

            if warning:
                response["warning"] = warning

            return response

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    except PcapParseError as e:
        # Treat parsing issues as client-side bad request per latest requirement
        logger.exception("PCAP parsing failed: %s", str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except ValueError as e:
        # Validation error - bad request
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except Exception as e:
        # Unexpected error
        logger.exception("Error processing PCAP: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/reporter/irp/analyze-pcap", response_model=IRPPcapAnalysisResponse)
async def analyze_irp_pcap(
    file: UploadFile = File(...),
    schema_id: Optional[str] = Form(None),
    mongo_db=Depends(get_mongo_db),
    current_user: dict = Depends(get_current_user),
):
    """Analyze PCAP file to extract IRP message IDs and names.

    Args:
        file: PCAP file upload
        schema_id: Optional schema ID to use for name resolution

    Returns:
        Analysis results with message statistics
    """
    # Validate file extension
    if not file.filename.endswith(".pcap") and not file.filename.endswith(".pcapng"):
        raise HTTPException(400, "File must be .pcap or .pcapng")

    try:

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pcap") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = Path(temp_file.name)

        try:
            # Try to load schema - prefer provided schema_id, fallback to most recent
            schema = None
            try:
                if schema_id:
                    # Use provided schema_id
                    schema = load_schema_from_mongo(mongo_db, schema_id)
                else:
                    # Fallback to most recent schema
                    schema_doc = mongo_db.irp_schemas.find_one(
                        sort=[("downloaded_at", -1)]
                    )
                    if schema_doc:
                        schema = load_schema_from_mongo(mongo_db, schema_doc["_id"])
            except Exception as e:
                logger.warning(f"Could not load schema for PCAP analysis: {e}")
                # Continue without schema - will show message IDs only

            # Analyze PCAP
            results = analyze_irp_pcap_file(temp_path, schema)

            return results

        finally:
            # Clean up temp file
            temp_path.unlink(missing_ok=True)

    except ValueError as e:
        raise HTTPException(400, f"Invalid PCAP format: {str(e)}")
    except Exception as e:
        logger.error(f"Error analyzing IRP PCAP: {str(e)}")
        raise HTTPException(500, f"Error analyzing PCAP: {str(e)}")


@router.post(
    "/cc/{cc_ip}/simulators/{simulator_ip}/reporter/snmp/stream",
    status_code=status.HTTP_200_OK,
)
async def send_snmp_trap_stream_endpoint(
    cc_ip: str,
    simulator_ip: str,
    payload: ReporterSNMPPayload,
    _current_user: User = Depends(require_cc_access),
    sapro_handler: SaproCommunicationHandler = Depends(get_sapro_handler),
    db=Depends(get_db),
):
    """Send SNMP traps with real-time progress via Server-Sent Events.

    Supports multiple simulators via comma-separated IPs. Progress events include simulator_ip field.
    """
    try:
        # Convert Pydantic model to dict
        # exclude_none=True ensures only provided fields are included,
        # allowing defaults in attack_traps.py to work correctly
        trap_data = payload.model_dump(exclude_none=True)

        # Validate trap_data structure
        if not trap_data or "traps" not in trap_data:
            logger.error("Invalid trap_data: missing 'traps' key")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid trap data: 'traps' key is required",
            )

        if not isinstance(trap_data["traps"], list) or not trap_data["traps"]:
            logger.error("Invalid trap_data: 'traps' must be a non-empty list")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid trap data: 'traps' must be a non-empty list",
            )

        # Resolve map names to full paths
        # Admin users have workspace='*'; convert to 'default' to avoid
        # find_map_workspace misidentifying the /opt/sapro/map/ directory as a workspace.
        workspace = _current_user.workspace
        if workspace == "*":
            workspace = "default"

        # Check if multiple simulators (comma-separated)
        if "," in simulator_ip:
            simulator_ips = [ip.strip() for ip in simulator_ip.split(",")]
            logger.info(f"Streaming SNMP traps to multiple simulators: {simulator_ips}")

            # Handle map field - convert to dict if needed
            map_dict = {}
            map_value = trap_data.get("map")
            if isinstance(map_value, dict):
                map_dict = map_value
            else:
                # Single map string or empty - resolve per simulator
                for sim_ip in simulator_ips:
                    map_dict[sim_ip] = map_value

            # Resolve map names - look up from DB if not provided
            for sim_ip in simulator_ips:
                map_name = get_simulator_map(db, sim_ip, map_dict.get(sim_ip))
                map_dict[sim_ip] = sapro_handler.get_full_map_path(map_name, workspace)

            # Extract per-simulator traps (different attack IDs per simulator)
            per_simulator_traps = trap_data.pop("per_simulator_traps", None)

            async def event_generator():
                try:
                    # Create async generators for each simulator
                    async def simulator_generator(sim_ip: str):
                        try:
                            sim_trap_data = trap_data.copy()
                            sim_trap_data["map"] = map_dict.get(sim_ip)
                            if per_simulator_traps and sim_ip in per_simulator_traps:
                                sim_trap_data["traps"] = per_simulator_traps[sim_ip]

                            for progress in send_attack_traps_with_progress(
                                cc_ip, sim_ip, sim_trap_data
                            ):
                                # Add simulator_ip to progress event
                                progress["simulator_ip"] = sim_ip
                                yield progress
                        except Exception as exc:
                            logger.exception(f"Error streaming to {sim_ip}: {exc}")
                            yield {
                                "type": "error",
                                "simulator_ip": sim_ip,
                                "message": str(exc),
                            }

                    # Interleave events from all simulators
                    event_queue = queue.Queue()
                    completed_simulators = set()

                    # Run all generators in parallel
                    async def run_generator(sim_ip: str):
                        async for event in simulator_generator(sim_ip):
                            event_queue.put(event)
                        completed_simulators.add(sim_ip)

                    # Start all tasks
                    tasks = [
                        asyncio.create_task(run_generator(sim_ip))
                        for sim_ip in simulator_ips
                    ]

                    # Yield events as they arrive
                    while len(completed_simulators) < len(simulator_ips):
                        try:
                            event = event_queue.get(timeout=0.1)
                            yield f"data: {json.dumps(event)}\n\n"
                        except queue.Empty:
                            await asyncio.sleep(0.1)
                            continue

                    # Wait for all tasks to complete
                    await asyncio.gather(*tasks, return_exceptions=True)

                    # Drain remaining events
                    while not event_queue.empty():
                        event = event_queue.get()
                        yield f"data: {json.dumps(event)}\n\n"

                except Exception as exc:
                    logger.exception(f"Error during SNMP trap streaming: {exc}")
                    error_event = {"type": "error", "message": str(exc)}
                    yield f"data: {json.dumps(error_event)}\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        else:
            # Single simulator (backward compatible)
            # Handle map field
            map_value = trap_data.get("map")
            if isinstance(map_value, dict):
                # Dict provided but only one simulator - extract map for this simulator
                map_name = map_value.get(simulator_ip)
            else:
                map_name = map_value

            # Get map from DB if not provided
            map_name = get_simulator_map(db, simulator_ip, map_name)
            # Resolve map name to full path
            trap_data["map"] = sapro_handler.get_full_map_path(map_name, workspace)

            # Use per-simulator traps if provided
            per_simulator_traps = trap_data.pop("per_simulator_traps", None)
            if per_simulator_traps and simulator_ip in per_simulator_traps:
                trap_data["traps"] = per_simulator_traps[simulator_ip]

            async def event_generator():
                try:
                    for progress in send_attack_traps_with_progress(
                        cc_ip, simulator_ip, trap_data
                    ):
                        # Add simulator_ip for consistency
                        progress["simulator_ip"] = simulator_ip
                        yield f"data: {json.dumps(progress)}\n\n"
                except Exception as exc:
                    logger.exception(f"Error during SNMP trap streaming: {exc}")
                    error_event = {
                        "type": "error",
                        "simulator_ip": simulator_ip,
                        "message": str(exc),
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

    except HTTPException:
        raise
    except KeyError as exc:
        logger.error(f"Invalid trap configuration: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid trap configuration: missing key {exc!s}",
        )
    except Exception as exc:
        logger.exception(f"Failed to initialize SNMP trap streaming: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize SNMP trap streaming: {exc!s}",
        )


# ============================================================================
# SNMP Loop Management Endpoints
# ============================================================================


@router.get(
    "/reporter/snmp/loop/status",
    status_code=status.HTTP_200_OK,
    response_model=SNMPLoopStatus,
)
async def get_snmp_loop_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> SNMPLoopStatus:
    """
    Get the current SNMP loop status for the authenticated user.

    Returns loop status including:
    - is_active: Whether loop is currently running
    - loop_delay: Delay between sends in seconds
    - loop_timeout: Total loop duration in seconds
    - start_time: When loop started
    - batches_sent: Number of batches sent so far
    - elapsed_seconds: Time elapsed since loop started
    - remaining_seconds: Time remaining until loop timeout
    - simulators: Target simulator IPs
    - destination_port: Destination port IP

    Requires authentication.
    """
    try:
        loop_manager = get_loop_manager()
        user_id = current_user.get("sub")
        status_result = await loop_manager.get_status(user_id)
        return status_result
    except Exception as e:
        logger.error(f"Error getting SNMP loop status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get loop status: {str(e)}",
        )


SYSTEM_TRAP_CAPACITY_15S = 24000


def _calc_traps_per_15s(num_traps: int, num_simulators: int, loop_delay: int) -> int:
    """Calculate how many traps a loop produces in a 15-second window."""
    batches_per_15s = math.ceil(15 / loop_delay)
    return num_traps * num_simulators * batches_per_15s


@router.post(
    "/reporter/snmp/loop/start",
    status_code=status.HTTP_200_OK,
)
async def start_snmp_loop(
    request: SNMPLoopStartRequest,
    current_user: User = Depends(require_cc_access),
    sapro_handler: SaproCommunicationHandler = Depends(get_sapro_handler),
) -> Dict[str, Any]:
    """
    Start a new SNMP loop for the authenticated user.

    The loop will:
    1. Send SNMP traps immediately
    2. Continue sending at specified intervals (loop_delay)
    3. Stop automatically after timeout duration (loop_timeout)
    4. Run in background independent of client connection

    Returns:
        Success message with loop details

    Raises:
        HTTPException 400: If loop already running for user
        HTTPException 409: If system trap capacity would be exceeded
        HTTPException 500: If failed to start loop
    """
    try:
        loop_manager = get_loop_manager()
        user_id = str(current_user.user_id)
        workspace = current_user.workspace
        if workspace == "*":
            workspace = "default"

        # --- System-wide capacity check ---
        requested_per_15s = _calc_traps_per_15s(
            len(request.traps), len(request.simulators), request.loop_delay
        )

        active_loops = await asyncio.to_thread(
            lambda: list(loop_manager.collection.find({"is_active": True}))
        )

        current_usage = 0
        active_loop_info = []
        now = datetime.now(timezone.utc)

        for loop_doc in active_loops:
            loop_config = SNMPLoopConfig(**loop_doc)
            # Skip the current user's own loop (will be replaced)
            if loop_config.user_id == user_id:
                continue
            loop_traps_per_15s = _calc_traps_per_15s(
                len(loop_config.traps), len(loop_config.simulators), loop_config.loop_delay
            )
            current_usage += loop_traps_per_15s

            remaining_seconds = 0
            if loop_config.start_time:
                elapsed = (now - loop_config.start_time.replace(tzinfo=timezone.utc)).total_seconds()
                remaining_seconds = max(0, int(loop_config.loop_timeout - elapsed))

            active_loop_info.append({
                "user_id": loop_config.user_id,
                "traps_per_15s": loop_traps_per_15s,
                "remaining_seconds": remaining_seconds,
                "simulators_count": len(loop_config.simulators),
                "loop_delay": loop_config.loop_delay,
            })

        if current_usage + requested_per_15s > SYSTEM_TRAP_CAPACITY_15S:
            available = max(0, SYSTEM_TRAP_CAPACITY_15S - current_usage)
            batches_per_15s = math.ceil(15 / request.loop_delay)
            divisor = len(request.simulators) * batches_per_15s
            max_traps = available // divisor if divisor > 0 else 0

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "System trap capacity exceeded",
                    "capacity_info": {
                        "system_capacity": SYSTEM_TRAP_CAPACITY_15S,
                        "current_usage": current_usage,
                        "requested": requested_per_15s,
                        "available": available,
                        "max_traps": max_traps,
                        "active_loops": active_loop_info,
                    },
                },
            )

        # Resolve map names to full paths
        resolved_maps = {}
        for sim_ip, map_name in request.simulator_maps.items():
            resolved_maps[sim_ip] = sapro_handler.get_full_map_path(map_name, workspace)

        # Create loop config
        config = SNMPLoopConfig(
            user_id=user_id,
            cc_ip=request.cc_ip,
            loop_delay=request.loop_delay,
            loop_timeout=request.loop_timeout,
            simulators=request.simulators,
            simulator_maps=resolved_maps,
            destination_port=request.destination_port,
            traps=request.traps,
            configured_attack_ids=request.configured_attack_ids,
            regenerate_attack_id=request.regenerate_attack_id,
        )

        # Start the loop
        await loop_manager.start_loop(user_id, config)

        return {
            "success": True,
            "message": f"SNMP loop started successfully for {len(request.simulators)} simulator(s)",
            "loop_delay": request.loop_delay,
            "loop_timeout": request.loop_timeout,
            "batches_sent": 0,
        }

    except HTTPException:
        raise
    except ValueError as e:
        # Loop already running
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error starting SNMP loop: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start loop: {str(e)}",
        )


@router.post(
    "/reporter/snmp/loop/stop",
    status_code=status.HTTP_200_OK,
)
async def stop_snmp_loop(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Stop the SNMP loop for the authenticated user.

    Returns:
        Success message with final loop statistics

    Raises:
        HTTPException 400: If no loop is running for user
        HTTPException 500: If failed to stop loop
    """
    try:
        loop_manager = get_loop_manager()
        user_id = current_user.get("sub")

        # Get final status before stopping
        final_status = await loop_manager.get_status(user_id)

        # Stop the loop
        await loop_manager.stop_loop(user_id)

        return {
            "success": True,
            "message": "SNMP loop stopped successfully",
            "batches_sent": final_status.batches_sent,
            "elapsed_seconds": final_status.elapsed_seconds,
        }

    except ValueError as e:
        # No loop running
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error stopping SNMP loop: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop loop: {str(e)}",
        )


# ============================================================================
# IRP Loop Management Endpoints
# ============================================================================


@router.get(
    "/reporter/irp/loop/status",
    status_code=status.HTTP_200_OK,
    response_model=IRPLoopStatus,
)
async def get_irp_loop_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> IRPLoopStatus:
    """Get the current IRP loop status for the authenticated user."""
    try:
        from backend.app.modules.reporter.irp.irp_loop_manager import get_irp_loop_manager

        loop_manager = get_irp_loop_manager()
        user_id = current_user.get("sub")

        status_result = await loop_manager.get_status(user_id)
        return status_result

    except Exception as e:
        logger.error(f"Error getting IRP loop status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get loop status: {str(e)}",
        )


@router.post(
    "/reporter/irp/loop/start",
    status_code=status.HTTP_200_OK,
)
async def start_irp_loop(
    request: IRPLoopStartRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Start a new IRP loop for the authenticated user."""
    try:
        from backend.app.modules.reporter.irp.irp_loop_manager import get_irp_loop_manager

        loop_manager = get_irp_loop_manager()
        user_id = current_user.get("sub")

        # Create loop config
        config = IRPLoopConfig(
            user_id=user_id,
            cc_ip=request.cc_ip,
            loop_delay=request.loop_delay,
            loop_timeout=request.loop_timeout,
            simulator=request.simulator,
            simulators=request.simulators,
            destination_port=request.destination_port,
            schema_id=request.schema_id,
            messages=request.messages,
            per_simulator_messages=request.per_simulator_messages,
        )

        # Start the loop
        await loop_manager.start_loop(user_id, config)

        # Get initial status
        initial_status = await loop_manager.get_status(user_id)

        return {
            "success": True,
            "message": "IRP loop started successfully",
            "loop_delay": request.loop_delay,
            "loop_timeout": request.loop_timeout,
            "batches_sent": initial_status.batches_sent,
        }

    except ValueError as e:
        # Loop already running
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error starting IRP loop: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start loop: {str(e)}",
        )


@router.post(
    "/reporter/irp/loop/stop",
    status_code=status.HTTP_200_OK,
)
async def stop_irp_loop(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Stop the current IRP loop for the authenticated user."""
    try:
        from backend.app.modules.reporter.irp.irp_loop_manager import get_irp_loop_manager

        loop_manager = get_irp_loop_manager()
        user_id = current_user.get("sub")

        # Stop the loop
        await loop_manager.stop_loop(user_id)

        # Get final status
        final_status = await loop_manager.get_status(user_id)

        return {
            "success": True,
            "message": "IRP loop stopped successfully",
            "batches_sent": final_status.batches_sent,
            "elapsed_seconds": final_status.elapsed_seconds,
        }

    except ValueError as e:
        # No loop running
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error stopping IRP loop: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop loop: {str(e)}",
        )


# ============================================================
# Form State Persistence (IRP + SNMP)
# ============================================================


MAX_IRP_MESSAGES = 200
MAX_SNMP_TRAPS = 500


@router.put("/cc/{cc_ip}/reporter/irp/form-state")
async def save_irp_form_state(
    cc_ip: str,
    body: dict,
    current_user: Dict[str, Any] = Depends(get_current_user),
    mongo_db=Depends(get_mongo_db),
):
    """Save IRP form state for the authenticated user."""
    messages = body.get("messages", [])
    if len(messages) > MAX_IRP_MESSAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Too many messages ({len(messages)}). Maximum is {MAX_IRP_MESSAGES}.",
        )
    user_id = current_user.get("sub") or current_user.get("id")
    mongo_db["irp_form_state"].replace_one(
        {"user_id": user_id, "cc_ip": cc_ip},
        {
            "user_id": user_id,
            "cc_ip": cc_ip,
            "messages": sanitize_for_mongo(body.get("messages", [])),
            "expanded_messages": body.get("expanded_messages", []),
            "updated_at": datetime.now(timezone.utc),
        },
        upsert=True,
    )
    return {"success": True}


@router.get("/cc/{cc_ip}/reporter/irp/form-state")
async def load_irp_form_state(
    cc_ip: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    mongo_db=Depends(get_mongo_db),
):
    """Load IRP form state for the authenticated user."""
    user_id = current_user.get("sub") or current_user.get("id")
    doc = mongo_db["irp_form_state"].find_one(
        {"user_id": user_id, "cc_ip": cc_ip}
    )
    if not doc:
        return {"messages": None, "expanded_messages": []}
    return {
        "messages": deserialize_from_mongo(doc.get("messages")),
        "expanded_messages": doc.get("expanded_messages", []),
    }


@router.delete("/cc/{cc_ip}/reporter/irp/form-state")
async def clear_irp_form_state(
    cc_ip: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    mongo_db=Depends(get_mongo_db),
):
    """Clear IRP form state for the authenticated user."""
    user_id = current_user.get("sub") or current_user.get("id")
    mongo_db["irp_form_state"].delete_one(
        {"user_id": user_id, "cc_ip": cc_ip}
    )
    return {"success": True}


@router.put("/cc/{cc_ip}/reporter/snmp/form-state")
async def save_snmp_form_state(
    cc_ip: str,
    body: dict,
    current_user: Dict[str, Any] = Depends(get_current_user),
    mongo_db=Depends(get_mongo_db),
):
    """Save SNMP form state for the authenticated user."""
    traps = body.get("traps", [])
    if len(traps) > MAX_SNMP_TRAPS:
        raise HTTPException(
            status_code=400,
            detail=f"Too many traps ({len(traps)}). Maximum is {MAX_SNMP_TRAPS}.",
        )
    user_id = current_user.get("sub") or current_user.get("id")
    mongo_db["snmp_form_state"].replace_one(
        {"user_id": user_id, "cc_ip": cc_ip},
        {
            "user_id": user_id,
            "cc_ip": cc_ip,
            "traps": body.get("traps", []),
            "expanded_traps": body.get("expanded_traps", []),
            "updated_at": datetime.now(timezone.utc),
        },
        upsert=True,
    )
    return {"success": True}


@router.get("/cc/{cc_ip}/reporter/snmp/form-state")
async def load_snmp_form_state(
    cc_ip: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    mongo_db=Depends(get_mongo_db),
):
    """Load SNMP form state for the authenticated user."""
    user_id = current_user.get("sub") or current_user.get("id")
    doc = mongo_db["snmp_form_state"].find_one(
        {"user_id": user_id, "cc_ip": cc_ip}
    )
    if not doc:
        return {"traps": None, "expanded_traps": []}
    return {
        "traps": doc.get("traps"),
        "expanded_traps": doc.get("expanded_traps", []),
    }


@router.delete("/cc/{cc_ip}/reporter/snmp/form-state")
async def clear_snmp_form_state(
    cc_ip: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    mongo_db=Depends(get_mongo_db),
):
    """Clear SNMP form state for the authenticated user."""
    user_id = current_user.get("sub") or current_user.get("id")
    mongo_db["snmp_form_state"].delete_one(
        {"user_id": user_id, "cc_ip": cc_ip}
    )
    return {"success": True}
