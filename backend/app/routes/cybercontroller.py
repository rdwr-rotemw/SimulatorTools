"""CyberController REST integration routes.

Endpoints:
- POST   /api/cc/{cc_ip}/login                                -> authenticate CC handler
- POST   /api/cc/{cc_ip}/logout                               -> logout from CC handler
- GET    /api/cc/{cc_ip}/simulators                           -> list devices from CC
- POST   /api/cc/{cc_ip}/simulators                           -> add device to CC
- DELETE /api/cc/{cc_ip}/simulators/{device_id}            -> delete device from CC
- GET    /api/cc/{cc_ip}/irp/IdsDataFormat                    -> get IdsDataFormat XML files

All endpoints require the caller to possess either 'admin' or 'cc_admin' role
(enforced by `require_cc_access`). Authentication to the CyberController is
handled via username/password in request body or query parameters.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Union

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.models.cc_session import CCSession
from backend.app.models.user import User
from backend.app.modules.cc.cc_client import get_cc_handler, CCHandler, CCCredentials
from backend.app.modules.mongo_models import DeviceDriverDeploy
from backend.app.modules.reporter.irp.irp_module import convert_xml
from backend.app.modules.sapro.sapro_client import get_sapro_handler
from backend.app.schemas.cybercontroller import (
    CCLoginPayload,
    CCLoginResponse,
    CCAddDevicePayload,
    CCDeviceResponse,
    CCDevicesListResponse,
    CCDeleteResponse,
    CCLogoutResponse,
    CCIdsDataFormatResponse,
    IdsDataFormatPayload,
    ManagementPort,
    ManagementPortsResponse,
    IRPSchemaListItem,
    IRPSchemaListResponse,
    CCDeviceAddResult,
    CCBatchDeviceResponse,
    IdsDownloadPayload,
)
from backend.app.utils.auth import require_cc_access
from backend.app.utils.cc_ssh import get_cc_ssh_client
from backend.app.utils.database import get_db
from backend.app.utils.database import get_mongo_db
from backend.app.utils.device_driver import (
    list_existing_drivers,
    match_driver_filename,
    parse_driver_filename,
    save_uploaded_driver,
    deploy_multiple_drivers,
)
from backend.utils.ip_utils import parse_ip_range

logger = logging.getLogger("sim-tools.cybercontroller")

router = APIRouter(prefix="/api", tags=["cybercontroller"])


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "/cc/{cc_ip}/login",
    status_code=status.HTTP_200_OK,
    response_model=CCLoginResponse,
)
async def cc_login(
        cc_ip: str,
        payload: CCLoginPayload,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_cc_access),
) -> CCLoginResponse:
    """Authenticate to a CyberController instance.

    Creates or retrieves a CC handler for the given IP and credentials,
    then attempts to log in. On success, stores the JSESSIONID in the database
    for session management.

    Args:
        cc_ip: CyberController IP address or hostname
        payload: Login credentials (username, password)
        db: Database session
        current_user: Authenticated user with cc_admin or admin role

    Returns:
        CCLoginResponse with success status and message
    """
    try:
        handler = get_cc_handler(cc_ip, payload.username, payload.password)
        ok, msg = handler.login()

        if not ok:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Login failed: {msg}")

        # Get the JSESSIONID from the handler's credentials
        if not handler._creds or not handler._creds.jsession_id:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Login succeeded but no JSESSIONID found")

        jsession_id = handler._creds.jsession_id

        # Delete any old sessions for this user and CC (force fresh login)
        db.query(CCSession).filter(
            CCSession.cc_ip == cc_ip,
            CCSession.user_id == current_user.user_id
        ).delete()

        # Create new session
        cc_session = CCSession(
            cc_ip=cc_ip,
            jsession_id=jsession_id,
            user_id=current_user.user_id,
            login_time=handler._creds.authenticated_at
        )
        db.add(cc_session)

        db.commit()

        return CCLoginResponse(success=True, message="Login successful")
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Login error: {exc!s}")


@router.get(
    "/cc/{cc_ip}/simulators",
    status_code=status.HTTP_200_OK,
    response_model=CCDevicesListResponse,
)
async def get_cc_simulators(
        cc_ip: str,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_cc_access),
) -> CCDevicesListResponse:
    """Get all dp devices (simulators) from a CyberController instance.

    Args:
        cc_ip: CyberController IP address or hostname
        db: Database session
        current_user: Authenticated user with cc_admin or admin role

    Returns:
        CCDevicesListResponse containing list of devices

    Raises:
        HTTPException: If authentication or device retrieval fails
    """
    try:
        # Query for active session for this user and CC
        cc_session = db.query(CCSession).filter(
            CCSession.cc_ip == cc_ip,
            CCSession.user_id == current_user.user_id
        ).first()

        if not cc_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active session for this CC"
            )

        # Create handler and attach stored JSESSIONID so requests use it
        handler = CCHandler(cc_ip, "", "")
        jsession_id = str(cc_session.jsession_id)
        handler._creds = CCCredentials(jsession_id=jsession_id, cc_ip=cc_ip,
                                       authenticated_at=getattr(cc_session, 'login_time', None))
        try:
            handler._session.cookies.set("JSESSIONID", jsession_id)
        except Exception:
            pass

        # Get all devices
        ok, result = handler.get_all_dps()
        if not ok:
            # If session is invalid, delete it from DB and return 401
            if "Failed to fetch devices" in str(result) or "Authentication" in str(result):
                db.delete(cc_session)
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="CC session expired. Please login again."
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve devices: {result}"
            )

        # Convert to response model - return ALL CC devices (no Sapro filtering)
        # Frontend will populate version and map from cached Sapro data
        device_responses = [
            CCDeviceResponse(
                management_ip=d.management_ip,
                name=d.name,
                device_id=d.device_id,
                device_type=d.device_type,
                status=d.status,
                version=None,  # Will be populated from Sapro by frontend
                map=None,      # Will be populated from Sapro by frontend
            )
            for d in result
        ]

        return CCDevicesListResponse(devices=device_responses)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving devices: {exc!s}"
        )


@router.get(
    "/cc/{cc_ip}/organization-parent",
    status_code=status.HTTP_200_OK,
)
async def get_organization_parent(
        cc_ip: str,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_cc_access),
) -> Dict[str, str]:
    """Get parent organization ID for adding devices.

    Looks for "Simulators" site in organization tree, falls back to "Default".

    Args:
        cc_ip: CyberController IP address or hostname
        db: Database session
        current_user: Authenticated user with cc_admin or admin role

    Returns:
        Dictionary with parent_orm_id and site_name

    Raises:
        HTTPException: If authentication or tree retrieval fails
    """
    try:
        # Query for active session
        cc_session = db.query(CCSession).filter(
            CCSession.cc_ip == cc_ip,
            CCSession.user_id == current_user.user_id
        ).first()

        if not cc_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active session for this CC"
            )

        handler = CCHandler(cc_ip, "", "")
        jsession_id = str(cc_session.jsession_id)
        handler._creds = CCCredentials(jsession_id=jsession_id, cc_ip=cc_ip,
                                       authenticated_at=getattr(cc_session, 'login_time', None))
        try:
            handler._session.cookies.set("JSESSIONID", jsession_id)
        except Exception:
            pass

        # Get organization tree
        ok, parent_orm_id = handler.get_organization_tree()

        if not ok:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get organization tree: {parent_orm_id}"
            )

        # Determine site name from the message
        site_name = "Simulators" if "Simulators" in str(parent_orm_id) else "Default"

        return {
            "parent_orm_id": parent_orm_id,
            "site_name": site_name
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting organization parent: {exc!s}"
        )


@router.post(
    "/cc/{cc_ip}/simulators",
    status_code=status.HTTP_201_CREATED,
    response_model=Union[CCDeviceResponse, CCBatchDeviceResponse],
)
async def add_cc_simulator(
        cc_ip: str,
        payload: CCAddDevicePayload,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_cc_access),
) -> Union[CCDeviceResponse, CCBatchDeviceResponse]:
    """Add a device (simulator) or range of devices to a CyberController instance.

    Supports single IP or IP range:
        - Single: management_ip = "50.50.100.1"
        - Range: management_ip = "50.50.100.1-50.50.100.25"

    For ranges:
        - Only IP and name increment
        - All other parameters (username, password, etc.) stay the same
        - Naming format: {name}_{ip} (e.g., "Sim_50.50.100.1")

    Args:
        cc_ip: CyberController IP address or hostname
        payload: Device details and CC credentials
        db: Database session
        current_user: Authenticated user with cc_admin or admin role

    Returns:
        CCDeviceResponse for single device or CCBatchDeviceResponse for ranges

    Raises:
        HTTPException: If authentication or device creation fails
    """
    try:
        # Query for active session
        cc_session = db.query(CCSession).filter(
            CCSession.cc_ip == cc_ip,
            CCSession.user_id == current_user.user_id
        ).first()

        if not cc_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active session for this CC"
            )

        handler = CCHandler(cc_ip, "", "")
        jsession_id = str(cc_session.jsession_id)
        handler._creds = CCCredentials(jsession_id=jsession_id, cc_ip=cc_ip,
                                       authenticated_at=getattr(cc_session, 'login_time', None))
        try:
            handler._session.cookies.set("JSESSIONID", jsession_id)
        except Exception:
            pass

        # Parse IP range
        ip_list = parse_ip_range(payload.management_ip)

        if len(ip_list) == 1:
            # Single device - existing logic
            ok, result = handler.add_device(
                name=payload.name,
                management_ip=payload.management_ip,
                device_type=payload.type,
                cli_username=payload.cli_username,
                cli_password=payload.cli_password,
                http_username=payload.http_username,
                https_password=payload.https_password,
                vision_mgt_port=payload.vision_mgt_port,
                register_device_events=payload.register_device_events,
            )

            if not ok:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to add device: {result}"
                )

            # Return minimal response since new API returns success message
            return CCDeviceResponse(
                management_ip=payload.management_ip,
                name=payload.name,
                device_type=payload.type,
            )
        else:
            # Batch devices
            results = []
            successful = 0
            failed = 0

            for ip in ip_list:
                device_name = f"{payload.name}_{ip}"
                try:
                    ok, result = handler.add_device(
                        name=device_name,
                        management_ip=ip,
                        device_type=payload.type,
                        cli_username=payload.cli_username,
                        cli_password=payload.cli_password,
                        http_username=payload.http_username,
                        https_password=payload.https_password,
                        vision_mgt_port=payload.vision_mgt_port,
                        register_device_events=payload.register_device_events,
                    )

                    if ok:
                        successful += 1
                        results.append(CCDeviceAddResult(
                            management_ip=ip,
                            name=device_name,
                            success=True
                        ))
                    else:
                        failed += 1
                        results.append(CCDeviceAddResult(
                            management_ip=ip,
                            name=device_name,
                            success=False,
                            error_message=result
                        ))
                except Exception as exc:
                    failed += 1
                    results.append(CCDeviceAddResult(
                        management_ip=ip,
                        name=device_name,
                        success=False,
                        error_message=str(exc)
                    ))

            return CCBatchDeviceResponse(
                total=len(ip_list),
                successful=successful,
                failed=failed,
                results=results
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding device: {exc!s}"
        )


async def wait_for_device_up(handler: CCHandler, device_ip: str, timeout_minutes: int = 5) -> bool:
    """Wait for a device to be up by polling its status.

    Polls the device status every 10 seconds until deviceStatus.status == 'OK'
    or timeout is reached.

    Args:
        handler: CCHandler instance with active session
        device_ip: IP address of the device to check
        timeout_minutes: Maximum time to wait in minutes (default: 5)

    Returns:
        True if device is up, False if timeout or error
    """
    import asyncio

    timeout_seconds = timeout_minutes * 60
    poll_interval = 10

    logger.info(f"Starting to wait for device {device_ip} to be up (timeout: {timeout_minutes} minutes)")

    for elapsed in range(0, timeout_seconds, poll_interval):
        try:
            ok, result = handler.get_device_status(device_ip)
            if not ok:
                logger.debug(f"Failed to get status for device {device_ip}: {result}")
                await asyncio.sleep(poll_interval)
                continue

            device_data = result  # type: ignore
            device_status = device_data.get('deviceStatus', {}).get('status')

            logger.debug(f"Device {device_ip} status: {device_status}")

            if device_status == 'OK':
                logger.info(f"Device {device_ip} is now up")
                return True

            await asyncio.sleep(poll_interval)

        except Exception as exc:
            logger.exception(f"Error checking device status for {device_ip}: {exc}")
            await asyncio.sleep(poll_interval)

    logger.warning(f"Timeout waiting for device {device_ip} to be up after {timeout_minutes} minutes")
    return False


@router.post(
    "/cc/{cc_ip}/simulators/stream",
    status_code=status.HTTP_200_OK,
)
async def add_cc_simulator_stream(
        cc_ip: str,
        payload: CCAddDevicePayload,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_cc_access),
):
    """Add devices to CyberController with real-time progress via Server-Sent Events (SSE).

    Supports both single IP and IP ranges with streaming progress updates.
    Frontend receives progress events for each device addition.

    Event format:
        - progress: {"type": "progress", "current": N, "total": M, "ip": "X.X.X.X", "name": "...", "status": "success"/"failed", "message": "..."}
        - complete: {"type": "complete", "success_count": N, "failed_count": M, "total_count": T}
        - error: {"type": "error", "message": "..."}
    """
    try:
        # Query for active session
        cc_session = db.query(CCSession).filter(
            CCSession.cc_ip == cc_ip,
            CCSession.user_id == current_user.user_id
        ).first()

        if not cc_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active session for this CC"
            )

        handler = CCHandler(cc_ip, "", "")
        jsession_id = str(cc_session.jsession_id)
        handler._creds = CCCredentials(jsession_id=jsession_id, cc_ip=cc_ip,
                                       authenticated_at=getattr(cc_session, 'login_time', None))
        try:
            handler._session.cookies.set("JSESSIONID", jsession_id)
        except Exception:
            pass

        # Parse IP range
        ip_list = parse_ip_range(payload.management_ip)

        # Release DB connection before long-running streaming operations
        db.close()

        async def event_generator():
            successful = 0
            failed = 0
            total = len(ip_list)

            try:
                # PHASE 1: Add ALL devices (sequential but no waiting)
                added_devices = []  # Track successfully added device IPs

                for index, ip in enumerate(ip_list, start=1):
                    device_name = f"{payload.name}_{ip}" if len(ip_list) > 1 else payload.name

                    try:
                        # Send "adding" status
                        yield f"data: {json.dumps({'type': 'progress', 'current': index, 'total': total, 'ip': ip, 'name': device_name, 'status': 'adding', 'message': 'Adding device...'})}\n\n"

                        ok, result = handler.add_device(
                            name=device_name,
                            management_ip=ip,
                            device_type=payload.type,
                            cli_username=payload.cli_username,
                            cli_password=payload.cli_password,
                            http_username=payload.http_username,
                            https_password=payload.https_password,
                            vision_mgt_port=payload.vision_mgt_port,
                            register_device_events=payload.register_device_events,
                        )

                        if ok:
                            added_devices.append((ip, device_name, index))
                            # Send "added" status (not yet checking)
                            yield f"data: {json.dumps({'type': 'progress', 'current': index, 'total': total, 'ip': ip, 'name': device_name, 'status': 'added', 'message': 'Device added, will check status after all additions complete'})}\n\n"
                        else:
                            failed += 1
                            yield f"data: {json.dumps({'type': 'progress', 'current': index, 'total': total, 'ip': ip, 'name': device_name, 'status': 'failed', 'message': f'Failed to add: {result}'})}\n\n"
                    except Exception as exc:
                        failed += 1
                        yield f"data: {json.dumps({'type': 'progress', 'current': index, 'total': total, 'ip': ip, 'name': device_name, 'status': 'failed', 'message': str(exc)})}\n\n"

                # PHASE 2: Wait for ALL added devices in parallel using asyncio.gather
                if added_devices:
                    # Send checking phase start notification
                    yield f"data: {json.dumps({'type': 'phase', 'message': f'All devices added. Now checking status for {len(added_devices)} devices in parallel...'})}\n\n"

                    # Create parallel tasks for all devices
                    import asyncio
                    tasks = [wait_for_device_up(handler, ip, 5) for ip, _, _ in added_devices]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Process results with sequential counter for waiting phase
                    waiting_total = len(added_devices)
                    for waiting_index, ((ip, device_name, original_index), is_up) in enumerate(
                            zip(added_devices, results), start=1):
                        if isinstance(is_up, Exception):
                            failed += 1
                            yield f"data: {json.dumps({'type': 'progress', 'current': waiting_index, 'total': waiting_total, 'ip': ip, 'name': device_name, 'status': 'failed', 'message': f'Status check error: {str(is_up)}'})}\n\n"
                        elif is_up:
                            successful += 1
                            yield f"data: {json.dumps({'type': 'progress', 'current': waiting_index, 'total': waiting_total, 'ip': ip, 'name': device_name, 'status': 'success', 'message': 'Device is up and ready'})}\n\n"
                        else:
                            failed += 1
                            yield f"data: {json.dumps({'type': 'progress', 'current': waiting_index, 'total': waiting_total, 'ip': ip, 'name': device_name, 'status': 'failed', 'message': 'Device added but failed to come up within 5 minutes'})}\n\n"

                # Send completion
                yield f"data: {json.dumps({'type': 'complete', 'success_count': successful, 'failed_count': failed, 'total_count': total})}\n\n"

            except Exception as exc:
                logger.exception(f"Error during CC device addition streaming with status: {exc}")
                error_event = {"type": "error", "message": str(exc)}
                yield f"data: {json.dumps(error_event)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to initialize CC device addition streaming: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize CC device addition streaming: {exc!s}"
        )


@router.post(
    "/cc/{cc_ip}/simulators/stream-with-status",
    status_code=status.HTTP_200_OK,
)
async def add_cc_simulator_stream_with_status(
        cc_ip: str,
        payload: CCAddDevicePayload,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_cc_access),
):
    """Add devices to CyberController with real-time progress and status checking via Server-Sent Events (SSE).

    Supports both single IP and IP ranges with streaming progress updates.
    After adding each device, waits for it to be "up" before proceeding.

    Event format:
        - progress: {"type": "progress", "current": N, "total": M, "ip": "X.X.X.X", "name": "...", "status": "adding|added|checking|success|failed", "message": "..."}
        - phase: {"type": "phase", "message": "..."}
        - complete: {"type": "complete", "success_count": N, "failed_count": M, "total_count": T}
        - error: {"type": "error", "message": "..."}
    """
    try:
        # Query for active session
        cc_session = db.query(CCSession).filter(
            CCSession.cc_ip == cc_ip,
            CCSession.user_id == current_user.user_id
        ).first()

        if not cc_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active session for this CC"
            )

        handler = CCHandler(cc_ip, "", "")
        jsession_id = str(cc_session.jsession_id)
        handler._creds = CCCredentials(jsession_id=jsession_id, cc_ip=cc_ip,
                                       authenticated_at=getattr(cc_session, 'login_time', None))
        try:
            handler._session.cookies.set("JSESSIONID", jsession_id)
        except Exception:
            pass

        # Parse IP range
        ip_list = parse_ip_range(payload.management_ip)

        # Release DB connection before long-running streaming operations
        db.close()

        async def event_generator():
            successful = 0
            failed = 0
            total = len(ip_list)

            try:
                # PHASE 1: Add ALL devices (sequential but no waiting)
                added_devices = []  # Track successfully added device IPs

                for index, ip in enumerate(ip_list, start=1):
                    device_name = f"{payload.name}_{ip}" if len(ip_list) > 1 else payload.name

                    try:
                        # Send "adding" status
                        yield f"data: {json.dumps({'type': 'progress', 'current': index, 'total': total, 'ip': ip, 'name': device_name, 'status': 'adding', 'message': 'Adding device...'})}\n\n"

                        ok, result = handler.add_device(
                            name=device_name,
                            management_ip=ip,
                            device_type=payload.type,
                            cli_username=payload.cli_username,
                            cli_password=payload.cli_password,
                            http_username=payload.http_username,
                            https_password=payload.https_password,
                            vision_mgt_port=payload.vision_mgt_port,
                            register_device_events=payload.register_device_events,
                        )

                        if ok:
                            added_devices.append((ip, device_name, index))
                            # Send "added" status (not yet checking)
                            yield f"data: {json.dumps({'type': 'progress', 'current': index, 'total': total, 'ip': ip, 'name': device_name, 'status': 'added', 'message': 'Device added, will check status after all additions complete'})}\n\n"
                        else:
                            failed += 1
                            yield f"data: {json.dumps({'type': 'progress', 'current': index, 'total': total, 'ip': ip, 'name': device_name, 'status': 'failed', 'message': f'Failed to add: {result}'})}\n\n"
                    except Exception as exc:
                        failed += 1
                        yield f"data: {json.dumps({'type': 'progress', 'current': index, 'total': total, 'ip': ip, 'name': device_name, 'status': 'failed', 'message': str(exc)})}\n\n"

                # PHASE 2: Wait for ALL added devices in parallel using asyncio.gather with callback
                if added_devices:
                    # Send checking phase start notification
                    yield f"data: {json.dumps({'type': 'phase', 'message': f'All devices added. Now checking status for {len(added_devices)} devices in parallel...'})}\n\n"

                    # Send immediate "checking" event to switch UI to waiting phase
                    first_device = added_devices[0]
                    yield f"data: {json.dumps({'type': 'progress', 'current': 0, 'total': len(added_devices), 'ip': first_device[0], 'name': first_device[1], 'status': 'checking', 'message': 'Checking device status...'})}\n\n"

                    # Create parallel tasks for all devices
                    import asyncio

                    # We'll use a different approach: create wrapper tasks that report completion
                    waiting_total = len(added_devices)
                    waiting_index = 0

                    async def check_and_report(ip, device_name, original_index):
                        """Wrapper that returns device info with result"""
                        is_up = await wait_for_device_up(handler, ip, 5)
                        return (ip, device_name, original_index, is_up)

                    # Create all tasks
                    tasks = [check_and_report(ip, device_name, idx) for ip, device_name, idx in added_devices]

                    # Process results as they complete
                    for coro in asyncio.as_completed(tasks):
                        waiting_index += 1
                        try:
                            ip, device_name, original_index, is_up = await coro

                            if is_up:
                                successful += 1
                                yield f"data: {json.dumps({'type': 'progress', 'current': waiting_index, 'total': waiting_total, 'ip': ip, 'name': device_name, 'status': 'success', 'message': 'Device is up and ready'})}\n\n"
                            else:
                                failed += 1
                                yield f"data: {json.dumps({'type': 'progress', 'current': waiting_index, 'total': waiting_total, 'ip': ip, 'name': device_name, 'status': 'failed', 'message': 'Device added but failed to come up within 5 minutes'})}\n\n"
                        except Exception as exc:
                            failed += 1
                            # We don't have device info if the task failed early, so use generic message
                            yield f"data: {json.dumps({'type': 'progress', 'current': waiting_index, 'total': waiting_total, 'ip': 'unknown', 'name': 'unknown', 'status': 'failed', 'message': f'Status check error: {str(exc)}'})}\n\n"

                # Send completion
                yield f"data: {json.dumps({'type': 'complete', 'success_count': successful, 'failed_count': failed, 'total_count': total})}\n\n"

            except Exception as exc:
                logger.exception(f"Error during CC device addition streaming with status: {exc}")
                error_event = {"type": "error", "message": str(exc)}
                yield f"data: {json.dumps(error_event)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to initialize CC device addition streaming with status: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize CC device addition streaming with status: {exc!s}"
        )


@router.post(
    "/cc/{cc_ip}/simulators/add-batch",
    status_code=status.HTTP_200_OK,
)
async def add_devices_batch(
        cc_ip: str,
        payload: CCAddDevicePayload,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_cc_access),
):
    """Add devices to CyberController in batch (without validation).

    Returns streaming progress for each device addition.
    Does NOT wait for devices to be up - use /validate-batch for that.

    Event format:
        - progress: {"type": "progress", "current": N, "total": M, "ip": "X.X.X.X", "name": "...", "success": bool, "message": "..."}
        - complete: {"type": "complete", "success_count": N, "failed_count": M, "total_count": T}
        - error: {"type": "error", "message": "..."}
    """
    try:
        # Query for active session
        cc_session = db.query(CCSession).filter(
            CCSession.cc_ip == cc_ip,
            CCSession.user_id == current_user.user_id
        ).first()

        if not cc_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active session for this CC"
            )

        handler = CCHandler(cc_ip, "", "")
        jsession_id = str(cc_session.jsession_id)
        handler._creds = CCCredentials(jsession_id=jsession_id, cc_ip=cc_ip,
                                       authenticated_at=getattr(cc_session, 'login_time', None))
        try:
            handler._session.cookies.set("JSESSIONID", jsession_id)
        except Exception:
            pass

        # Parse IP range
        ip_list = parse_ip_range(payload.management_ip)

        # Release DB connection before long-running streaming operations
        db.close()

        async def event_generator():
            successful = 0
            failed = 0
            total = len(ip_list)

            try:
                for index, ip in enumerate(ip_list, start=1):
                    device_name = f"{payload.name}_{ip}" if len(ip_list) > 1 else payload.name

                    try:
                        ok, result = handler.add_device(
                            name=device_name,
                            management_ip=ip,
                            device_type=payload.type,
                            cli_username=payload.cli_username,
                            cli_password=payload.cli_password,
                            http_username=payload.http_username,
                            https_password=payload.https_password,
                            vision_mgt_port=payload.vision_mgt_port,
                            register_device_events=payload.register_device_events,
                        )

                        if ok:
                            successful += 1
                            yield f"data: {json.dumps({'type': 'progress', 'current': index, 'total': total, 'ip': ip, 'name': device_name, 'success': True, 'message': 'Device added successfully'})}\n\n"
                        else:
                            failed += 1
                            yield f"data: {json.dumps({'type': 'progress', 'current': index, 'total': total, 'ip': ip, 'name': device_name, 'success': False, 'message': f'Failed: {result}'})}\n\n"
                    except Exception as exc:
                        failed += 1
                        yield f"data: {json.dumps({'type': 'progress', 'current': index, 'total': total, 'ip': ip, 'name': device_name, 'success': False, 'message': str(exc)})}\n\n"

                # Send completion
                yield f"data: {json.dumps({'type': 'complete', 'success_count': successful, 'failed_count': failed, 'total_count': total})}\n\n"

            except Exception as exc:
                logger.exception(f"Error during batch device addition: {exc}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to initialize batch device addition: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize batch device addition: {exc!s}"
        )


@router.post(
    "/cc/{cc_ip}/simulators/validate-batch",
    status_code=status.HTTP_200_OK,
)
async def validate_devices_batch(
        cc_ip: str,
        payload: CCAddDevicePayload,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_cc_access),
):
    """Validate that devices are up by checking their status.

    Checks devices in parallel for performance.
    Use this after add-batch to verify devices are ready.

    Event format:
        - progress: {"type": "progress", "current": N, "total": M, "ip": "X.X.X.X", "name": "...", "success": bool, "message": "..."}
        - complete: {"type": "complete", "success_count": N, "failed_count": M, "total_count": T}
        - error: {"type": "error", "message": "..."}
    """
    try:
        # Query for active session
        cc_session = db.query(CCSession).filter(
            CCSession.cc_ip == cc_ip,
            CCSession.user_id == current_user.user_id
        ).first()

        if not cc_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active session for this CC"
            )

        handler = CCHandler(cc_ip, "", "")
        jsession_id = str(cc_session.jsession_id)
        handler._creds = CCCredentials(jsession_id=jsession_id, cc_ip=cc_ip,
                                       authenticated_at=getattr(cc_session, 'login_time', None))
        try:
            handler._session.cookies.set("JSESSIONID", jsession_id)
        except Exception:
            pass

        # Parse IP range
        ip_list = parse_ip_range(payload.management_ip)

        # Release DB connection before long-running streaming operations
        db.close()

        async def event_generator():
            import asyncio

            successful = 0
            failed = 0
            total = len(ip_list)
            validated_count = 0

            try:
                # Create device list with names
                devices = []
                for ip in ip_list:
                    device_name = f"{payload.name}_{ip}" if len(ip_list) > 1 else payload.name
                    devices.append((ip, device_name))

                # Validate all devices in parallel
                async def check_and_report(ip, device_name):
                    """Check device status and return result"""
                    is_up = await wait_for_device_up(handler, ip, 5)
                    return (ip, device_name, is_up)

                # Create all tasks
                tasks = [check_and_report(ip, name) for ip, name in devices]

                # Process results as they complete
                for coro in asyncio.as_completed(tasks):
                    validated_count += 1
                    try:
                        ip, device_name, is_up = await coro

                        if is_up:
                            successful += 1
                            yield f"data: {json.dumps({'type': 'progress', 'current': validated_count, 'total': total, 'ip': ip, 'name': device_name, 'success': True, 'message': 'Device is up and ready'})}\n\n"
                        else:
                            failed += 1
                            yield f"data: {json.dumps({'type': 'progress', 'current': validated_count, 'total': total, 'ip': ip, 'name': device_name, 'success': False, 'message': 'Device failed to come up within 5 minutes'})}\n\n"
                    except Exception as exc:
                        failed += 1
                        yield f"data: {json.dumps({'type': 'progress', 'current': validated_count, 'total': total, 'ip': 'unknown', 'name': 'unknown', 'success': False, 'message': f'Validation error: {str(exc)}'})}\n\n"

                # Send completion
                yield f"data: {json.dumps({'type': 'complete', 'success_count': successful, 'failed_count': failed, 'total_count': total})}\n\n"

            except Exception as exc:
                logger.exception(f"Error during batch device validation: {exc}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to initialize batch device validation: {exc!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize batch device validation: {exc!s}"
        )


@router.delete(
    "/cc/{cc_ip}/simulators/{device_id}",
    status_code=status.HTTP_200_OK,
    response_model=CCDeleteResponse,
)
async def delete_cc_simulator(
        cc_ip: str,
        device_id: str,
        device_name: str,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_cc_access),
) -> CCDeleteResponse:
    """Delete a device (simulator) from a CyberController instance.

    Args:
        cc_ip: CyberController IP address or hostname
        device_id: ID of the simulator to delete (as reported by the CC)
        device_name: Name of the simulator (used for DefenseFlow removal if needed)
        db: Database session
        current_user: Authenticated user with cc_admin or admin role

    Returns:
        CCDeleteResponse with success status and message

    Raises:
        HTTPException: If authentication or device deletion fails
    """
    try:
        # Query for active session
        cc_session = db.query(CCSession).filter(
            CCSession.cc_ip == cc_ip,
            CCSession.user_id == current_user.user_id
        ).first()

        if not cc_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active session for this CC"
            )

        handler = CCHandler(cc_ip, "", "")
        jsession_id = str(cc_session.jsession_id)
        handler._creds = CCCredentials(jsession_id=jsession_id, cc_ip=cc_ip,
                                       authenticated_at=getattr(cc_session, 'login_time', None))
        try:
            handler._session.cookies.set("JSESSIONID", jsession_id)
        except Exception:
            pass

        # Delete device by device_id
        ok, msg = handler.delete_device(device_id, device_name)

        if not ok:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete device: {msg}"
            )

        return CCDeleteResponse(success=True, message=msg)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting device: {exc!s}"
        )


@router.post(
    "/cc/{cc_ip}/logout",
    status_code=status.HTTP_200_OK,
    response_model=CCLogoutResponse,
)
async def cc_logout(
        cc_ip: str,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_cc_access),
) -> CCLogoutResponse:
    """Logout from a CyberController instance.

    Disconnects the JSESSIONID session by sending a POST request to the
    CyberController logout endpoint using the stored session from the database.
    This invalidates the session on the server side and removes the session
    record from the database.

    Args:
        cc_ip: CyberController IP address or hostname
        db: Database session
        current_user: Authenticated user with cc_admin or admin role

    Returns:
        CCLogoutResponse with success status and message

    Raises:
        HTTPException: If no active session found or logout fails
    """
    try:
        # Query for active session
        cc_session = db.query(CCSession).filter(
            CCSession.cc_ip == cc_ip,
            CCSession.user_id == current_user.user_id
        ).first()

        if not cc_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active session for this CC"
            )

        # Get the jsession_id from the database
        jsession_id = str(cc_session.jsession_id)

        # Create CCHandler instance without logging in (we only need it to call logout)
        handler = CCHandler(cc_ip, "", "")
        ok, msg = handler.logout(jsession_id)

        # Delete the session record from database regardless of server logout result
        # (we want to clean up our local state even if server logout fails)
        db.delete(cc_session)
        db.commit()

        if not ok:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Logout failed on server: {msg} (local session cleaned up)"
            )

        return CCLogoutResponse(success=True, message="Logout successful")
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during logout: {exc!s}"
        )


@router.post(
    "/cc/{cc_ip}/irp/IdsDataFormat",
    status_code=status.HTTP_200_OK,
    response_model=CCIdsDataFormatResponse,
)
async def get_ids_data_format(
        cc_ip: str,
        payload: IdsDataFormatPayload,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_cc_access),
) -> CCIdsDataFormatResponse:
    """List IdsDataFormat XML files available on the CyberController via SSH.

    Requires an active CCSession stored in the database and root SSH credentials
    to connect to the CC host and enumerate files.
    """
    try:
        cc_session = db.query(CCSession).filter(
            CCSession.cc_ip == cc_ip,
            CCSession.user_id == current_user.user_id
        ).first()

        if not cc_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active session for this CC"
            )

        handler = CCHandler(cc_ip, "", "")
        # attach stored jsession so handler can use API if needed
        try:
            handler._session.cookies.set("JSESSIONID", str(cc_session.jsession_id))
        except Exception:
            pass

        ok, files = handler.get_ids_data_formats(payload.username, payload.password)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve IdsDataFormat files: {files}"
            )
        return CCIdsDataFormatResponse(files=files)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving IdsDataFormat: {exc!s}"
        )


@router.post(
    "/cc/{cc_ip}/irp/IdsDataFormat/download",
    status_code=status.HTTP_200_OK,
)
async def download_ids_data_format(
        cc_ip: str,
        payload: IdsDownloadPayload,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_cc_access),
):
    """Download IdsDataFormat file for a given simulator version.

    This endpoint now detects if a custom XML has been uploaded (by checking for .original backup).
    If backup exists:
    - Returns backup_exists: true in response
    - If revert_to_original=false: downloads current (custom) XML
    - If revert_to_original=true: restores original XML and downloads it
    """
    import hashlib
    import base64
    from datetime import datetime, timezone

    try:

        handler = CCHandler(cc_ip, "", "")

        # Get SSH client
        ssh_client = get_cc_ssh_client(cc_ip=cc_ip, username=payload.username, password=payload.password)

        # Determine filenames
        format_version = handler._version_to_data_format(payload.sim_version)
        filename = f"IdsDataFormat{format_version}.xml"
        backup_filename = f"IdsDataFormat{format_version}.xml.original"

        remote_dir = "/var/lib/docker/radware-storage/dc_config/kvision-configuration-service/config/conf"
        remote_path = f"{remote_dir}/{filename}"
        backup_path = f"{remote_dir}/{backup_filename}"

        # Check if backup exists
        check_cmd = f"test -f {backup_path} && echo 'exists' || echo 'not_exists'"
        success, output = ssh_client.execute_command(check_cmd, check_stderr=False)

        backup_exists = output.strip() == 'exists'

        # Handle revert to original
        if backup_exists and payload.revert_to_original:
            logger.info("Reverting to original XML for version %s", payload.sim_version)

            # Restore original: copy .original back to main file
            restore_cmd = f"cp {backup_path} {remote_path}"
            success, restore_output = ssh_client.execute_command(restore_cmd, check_stderr=True)

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to restore original XML: {restore_output}"
                )

            # Delete backup
            delete_cmd = f"rm {backup_path}"
            ssh_client.execute_command(delete_cmd, check_stderr=False)

            logger.info("Original XML restored for version %s", payload.sim_version)
            backup_exists = False  # No longer exists after restore

        # Download the file (current or restored)
        ok, res = handler.download_ids_data_format(payload.sim_version, payload.username, payload.password)
        if not ok:
            return {"success": False, "message": res, "local_path": "", "mongo_id": "", "note": "",
                    "backup_exists": backup_exists, "is_custom": False}

        local_path = res

        # Ensure file exists before attempting conversion
        if not os.path.exists(local_path):
            return {"success": False, "message": f"Downloaded file not found: {local_path}", "local_path": local_path,
                    "mongo_id": "", "note": "", "backup_exists": backup_exists, "is_custom": False}

        # Read file bytes and compute SHA256 checksum
        try:
            with open(local_path, 'rb') as f:
                file_bytes = f.read()
        except Exception as exc:
            logger.exception("Failed to read downloaded file %s: %s", local_path, exc)
            return {"success": False, "message": f"Failed to read downloaded file: {exc!s}", "local_path": local_path,
                    "mongo_id": "", "note": "", "backup_exists": backup_exists, "is_custom": False}

        sha256_hash = hashlib.sha256(file_bytes).hexdigest()

        # Check MongoDB for existing schema with same version + checksum
        try:
            mongo_db = get_mongo_db()
            existing = mongo_db.irp_data_formats.find_one({
                "IdsDataFormat_version": payload.sim_version,
                "xml_checksum": sha256_hash
            })
        except Exception as exc:
            logger.exception("Failed to query MongoDB for existing schema: %s", exc)
            existing = None

        if existing:
            mongo_id = str(existing.get("_id"))
            logger.info("Reusing cached XML blob for version %s (checksum %s...)", payload.sim_version,
                        sha256_hash[:16])
            return {
                "success": True,
                "message": "Reused cached XML blob",
                "local_path": local_path,
                "mongo_id": mongo_id,
                "note": "Reused cached blob",
                "backup_exists": backup_exists,
                "is_custom": backup_exists  # If backup exists, current file is custom
            }

        # No cached match - perform conversion and store new document
        try:
            converted = convert_xml(local_path)
        except FileNotFoundError:
            return {"success": False, "message": "Downloaded file disappeared before conversion",
                    "local_path": local_path, "mongo_id": "", "note": "", "backup_exists": backup_exists,
                    "is_custom": False}
        except Exception as exc:
            logger.exception("Conversion failed for %s: %s", local_path, exc)
            return {"success": False, "message": f"Conversion error: {exc!s}", "local_path": local_path, "mongo_id": "",
                    "note": "", "backup_exists": backup_exists, "is_custom": False}

        try:
            template_name = os.path.basename(local_path)
            if template_name.lower().endswith('.xml'):
                template_name = template_name[:-4]

            # Prepare document for MongoDB insertion (include blob, checksum, timestamps)
            insert_doc = {
                "template_name": template_name,
                "description": f"Downloaded from {cc_ip}",
                "xml_schema": converted,
                "IdsDataFormat_version": payload.sim_version,
                "user_id": str(current_user.user_id),
                "xml_blob": base64.b64encode(file_bytes).decode(),
                "xml_checksum": sha256_hash,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "is_public": False,
            }

            result = mongo_db.irp_data_formats.insert_one(insert_doc)
            mongo_id = str(result.inserted_id)

            logger.info("Downloaded and stored new XML schema %s (id=%s, checksum=%s...)", payload.sim_version,
                        mongo_id, sha256_hash[:16])
            return {
                "success": True,
                "message": "Downloaded and saved",
                "local_path": local_path,
                "mongo_id": mongo_id,
                "note": "Parsed new XML",
                "backup_exists": backup_exists,
                "is_custom": backup_exists  # If backup exists, current file is custom
            }
        except Exception as exc:
            logger.exception("Failed to insert converted schema into MongoDB: %s", exc)
            return {"success": False, "message": f"Mongo insert error: {exc!s}", "local_path": local_path,
                    "mongo_id": "", "note": "", "backup_exists": backup_exists, "is_custom": False}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading IdsDataFormat: {exc!s}"
        )


@router.post(
    "/cc/{cc_ip}/irp/IdsDataFormat/upload",
    status_code=status.HTTP_200_OK,
)
async def upload_custom_ids_data_format(
        cc_ip: str,
        file: UploadFile = File(...),
        sim_version: str = Form(...),  # Changed from simulator_ip
        username: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(require_cc_access),
):
    """Upload custom IdsDataFormat XML and immediately convert for use.

    DANGEROUS: This replaces the production XML file used by CyberController.
    Only use for development and testing.

    Workflow:
    1. Validate uploaded XML by parsing with convert_xml()
    2. Validate that version exists in available simulators (safety check)
    3. Create backup if doesn't exist: IdsDataFormat{version}.xml.original
    4. Upload custom XML as IdsDataFormat{version}.xml via SCP
    5. Download it back from CC
    6. Convert and store in MongoDB
    7. Return mongo_id for immediate use

    Args:
        cc_ip: CyberController IP
        file: Custom XML file to upload
        sim_version: Simulator version (e.g., "10.6.0.0")
        username: SSH username for CC
        password: SSH password for CC

    Returns:
        {"success": bool, "message": str, "version": str, "backup_created": bool, "mongo_id": str}
    """
    import tempfile
    import hashlib
    import base64
    from datetime import datetime, timezone

    try:
        # Check CC session
        cc_session = db.query(CCSession).filter(
            CCSession.cc_ip == cc_ip,
            CCSession.user_id == current_user.user_id
        ).first()

        if not cc_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active session for this CC"
            )

        # Validate file extension
        if not file.filename or not file.filename.lower().endswith('.xml'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an XML file"
            )

        # Optional: Validate that version exists in Sapro (safety check)
        try:
            sapro_handler = get_sapro_handler()
            devices = sapro_handler.get_all_devices()

            # Check if any device has this version
            version_exists = any(
                getattr(device, 'version', None) == sim_version
                for device in devices
            )

            if not version_exists:
                logger.warning("Version %s not found in Sapro devices, but continuing anyway", sim_version)
                # Don't raise error - allow upload even if version not in Sapro (for flexibility)

        except Exception as exc:
            # Non-fatal - just log and continue
            logger.warning("Could not validate version in Sapro (non-fatal): %s", exc)

        # Save uploaded file to temp location for validation
        with tempfile.NamedTemporaryFile(suffix='.xml', delete=False) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name

        try:
            # Validate XML by parsing with convert_xml
            logger.info("Validating uploaded XML for version %s", sim_version)
            try:
                converted_test = convert_xml(tmp_path)
                if not converted_test:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="XML validation failed: Invalid IdsDataFormat structure"
                    )
            except Exception as exc:
                logger.exception("XML validation failed: %s", exc)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"XML validation failed: {exc!s}"
                )

            # Get CC handler and use existing version conversion logic
            handler = CCHandler(cc_ip, "", "")
            format_version = handler._version_to_data_format(sim_version)
            filename = f"IdsDataFormat{format_version}.xml"
            backup_filename = f"IdsDataFormat{format_version}.xml.original"

            remote_dir = "/var/lib/docker/radware-storage/dc_config/kvision-configuration-service/config/conf"
            remote_path = f"{remote_dir}/{filename}"
            backup_path = f"{remote_dir}/{backup_filename}"

            # Use centralized SSH client
            ssh_client = get_cc_ssh_client(cc_ip=cc_ip, username=username, password=password)

            # Check if backup already exists
            check_cmd = f"test -f {backup_path} && echo 'exists' || echo 'not_exists'"
            success, output = ssh_client.execute_command(check_cmd, check_stderr=False)

            backup_created = False
            if output.strip() == 'not_exists':
                # Create backup
                logger.info("Creating backup: %s -> %s", remote_path, backup_path)
                backup_cmd = f"cp {remote_path} {backup_path}"
                success, backup_output = ssh_client.execute_command(backup_cmd, check_stderr=True)

                if not success:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to create backup: {backup_output}"
                    )
                backup_created = True
                logger.info("Backup created successfully")
            else:
                logger.info("Backup already exists, skipping backup creation")

            # Upload custom XML
            logger.info("Uploading custom XML to %s", remote_path)
            success, upload_msg = ssh_client.upload_file(tmp_path, remote_path)

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload XML: {upload_msg}"
                )

            logger.info("Custom XML uploaded successfully, now downloading and converting...")

            # Download back from CC and convert (reuse existing logic)
            ok, download_result = handler.download_ids_data_format(sim_version, username, password)
            if not ok:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to download uploaded XML: {download_result}"
                )

            local_path = download_result

            # Read file bytes and compute SHA256 checksum
            try:
                with open(local_path, 'rb') as f:
                    file_bytes = f.read()
            except Exception as exc:
                logger.exception("Failed to read downloaded file %s: %s", local_path, exc)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to read downloaded file: {exc!s}"
                )

            sha256_hash = hashlib.sha256(file_bytes).hexdigest()

            # Convert XML
            try:
                converted = convert_xml(local_path)
            except Exception as exc:
                logger.exception("Conversion failed for %s: %s", local_path, exc)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Conversion error: {exc!s}"
                )

            # Store in MongoDB
            try:
                mongo_db = get_mongo_db()

                template_name = os.path.basename(local_path)
                if template_name.lower().endswith('.xml'):
                    template_name = template_name[:-4]

                insert_doc = {
                    "template_name": f"{template_name}_CUSTOM",
                    "description": f"Custom XML uploaded by {current_user.username} for {cc_ip}",
                    "xml_schema": converted,
                    "IdsDataFormat_version": sim_version,
                    "user_id": str(current_user.user_id),
                    "xml_blob": base64.b64encode(file_bytes).decode(),
                    "xml_checksum": sha256_hash,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                    "is_public": False,
                }

                result = mongo_db.irp_data_formats.insert_one(insert_doc)
                mongo_id = str(result.inserted_id)

                logger.info("Custom XML converted and stored (id=%s, version=%s, checksum=%s...)",
                            mongo_id, sim_version, sha256_hash[:16])

                return {
                    "success": True,
                    "message": f"Custom XML uploaded and converted successfully for version {sim_version}",
                    "version": sim_version,
                    "backup_created": backup_created,
                    "mongo_id": mongo_id
                }

            except Exception as exc:
                logger.exception("Failed to store converted schema in MongoDB: %s", exc)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to store in MongoDB: {exc!s}"
                )

        finally:
            # Clean up temp file
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error uploading custom XML: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading custom XML: {exc!s}"
        )


@router.get(
    "/cc/{cc_ip}/management-ports",
    status_code=status.HTTP_200_OK,
    response_model=ManagementPortsResponse,
)
async def get_management_ports(
        cc_ip: str,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_cc_access),
) -> ManagementPortsResponse:
    """Get management port interfaces from CyberController.

    Args:
        cc_ip: CyberController IP address
        db: Database session
        current_user: Authenticated user with cc_admin or admin role

    Returns:
        ManagementPortsResponse with list of management ports

    Raises:
        HTTPException: If authentication or retrieval fails
    """
    try:
        cc_session = db.query(CCSession).filter(
            CCSession.cc_ip == cc_ip,
            CCSession.user_id == current_user.user_id
        ).first()

        if not cc_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active session for this CC"
            )

        handler = CCHandler(cc_ip, "", "")
        jsession_id = str(cc_session.jsession_id)
        handler._creds = CCCredentials(
            jsession_id=jsession_id,
            cc_ip=cc_ip,
            authenticated_at=getattr(cc_session, 'login_time', None)
        )
        try:
            handler._session.cookies.set("JSESSIONID", jsession_id)
        except Exception:
            pass

        ok, result = handler.get_management_ports()
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve management ports: {result}"
            )

        ports = [ManagementPort(interface=p["interface"], address=p["address"]) for p in result]
        return ManagementPortsResponse(ports=ports)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving management ports: {exc!s}"
        )


@router.get(
    "/cc/{cc_ip}/irp/schemas/{schema_id}/messages",
    status_code=status.HTTP_200_OK,
)
async def list_schema_messages(
        cc_ip: str,
        schema_id: str,
        _current_user: User = Depends(require_cc_access),
):
    """List all available messages for a given IRP schema.

    Args:
        cc_ip: CyberController IP
        schema_id: MongoDB ObjectId of the schema
        _current_user: Authenticated user with cc_admin or admin role

    Returns:
        List of message IDs and names
    """
    try:
        # Load helper locally to avoid import cycles
        from backend.app.modules.reporter.irp.irp_module import load_schema_from_mongo
        mongo_db = get_mongo_db()

        # Load schema from MongoDB
        schema_obj = load_schema_from_mongo(mongo_db, schema_id)

        # Check if schema and messages exist
        if not schema_obj or not hasattr(schema_obj, 'schema'):
            return {"messages": []}

        schema = schema_obj.schema
        if not hasattr(schema, 'messages') or not schema.messages:
            return {"messages": []}

        messages = schema.messages
        message_list = []

        # Handle different message structures
        if isinstance(messages, dict):
            for msg_id, msg_obj in messages.items():
                try:
                    # Try to get name from message object
                    if msg_obj is None:
                        continue

                    if hasattr(msg_obj, 'name'):
                        name = msg_obj.name
                    elif isinstance(msg_obj, dict):
                        name = msg_obj.get('name', f"Message {msg_id}")
                    else:
                        name = str(msg_obj) if msg_obj else f"Message {msg_id}"

                    message_list.append({
                        "id": str(msg_id),
                        "name": name or f"Message {msg_id}"
                    })
                except Exception as e:
                    # Skip problematic messages but continue
                    logger.warning(f"Failed to process message {msg_id}: {e}")
                    continue
        elif isinstance(messages, list):
            # If messages are in a list, try to extract name/index
            for idx, msg_obj in enumerate(messages):
                try:
                    if msg_obj is None:
                        continue
                    if hasattr(msg_obj, 'name'):
                        name = msg_obj.name
                    elif isinstance(msg_obj, dict):
                        name = msg_obj.get('name', f"Message {idx}")
                    else:
                        name = str(msg_obj) if msg_obj else f"Message {idx}"

                    message_list.append({"id": str(idx), "name": name or f"Message {idx}"})
                except Exception as e:
                    logger.warning(f"Failed to process message at index {idx}: {e}")
                    continue
        else:
            # Unknown structure - attempt best-effort iteration if possible
            try:
                for msg_id, msg_obj in getattr(messages, 'items', lambda: [])():
                    try:
                        if msg_obj is None:
                            continue
                        if hasattr(msg_obj, 'name'):
                            name = msg_obj.name
                        elif isinstance(msg_obj, dict):
                            name = msg_obj.get('name', f"Message {msg_id}")
                        else:
                            name = str(msg_obj) if msg_obj else f"Message {msg_id}"

                        message_list.append({"id": str(msg_id), "name": name or f"Message {msg_id}"})
                    except Exception as e:
                        logger.warning(f"Failed to process message {msg_id} in unknown structure: {e}")
                        continue
            except Exception:
                # Cannot iterate messages - return empty
                return {"messages": []}

        return {"messages": message_list}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing messages: {exc!s}"
        )


# New endpoints for IRP schema management
@router.get(
    "/cc/{cc_ip}/irp/schemas",
    status_code=status.HTTP_200_OK,
    response_model=IRPSchemaListResponse,
)
async def list_irp_schemas(
        cc_ip: str,
        current_user: User = Depends(require_cc_access),
) -> IRPSchemaListResponse:
    """List all IRP schemas stored in MongoDB.

    Returns:
        IRPSchemaListResponse with list of schemas
    """
    try:
        mongo_db = get_mongo_db()
        schemas_cursor = mongo_db.irp_data_formats.find({}, {
            "_id": 1,
            "template_name": 1,
            "IdsDataFormat_version": 1,
            "created_at": 1
        })

        schemas = []
        for doc in schemas_cursor:
            created_at = doc.get("created_at", "")
            # Convert datetime to ISO string if needed
            if hasattr(created_at, 'isoformat'):
                created_at = created_at.isoformat()
            elif not isinstance(created_at, str):
                created_at = str(created_at) if created_at else ""

            schemas.append(IRPSchemaListItem(
                mongo_id=str(doc["_id"]),
                template_name=doc.get("template_name", "Unknown"),
                version=doc.get("IdsDataFormat_version", "Unknown"),
                created_at=created_at
            ))

        return IRPSchemaListResponse(schemas=schemas)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing schemas: {exc!s}"
        )


@router.delete(
    "/cc/{cc_ip}/irp/schemas/{schema_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_irp_schema(
        cc_ip: str,
        schema_id: str,
        current_user: User = Depends(require_cc_access),
):
    """Delete an IRP schema from MongoDB.

    Args:
        cc_ip: CyberController IP
        schema_id: MongoDB ObjectId of schema to delete

    Returns:
        Success response
    """
    try:
        from bson.objectid import ObjectId
        mongo_db = get_mongo_db()

        result = mongo_db.irp_data_formats.delete_one({"_id": ObjectId(schema_id)})

        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schema not found"
            )

        return {"success": True, "message": "Schema deleted successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting schema: {exc!s}"
        )


@router.get("/cc/{cc_ip}/device-drivers")
async def list_device_drivers(
        cc_ip: str,
        _current_user=Depends(require_cc_access),
) -> Dict[str, Any]:
    """List all available device drivers (existing + uploaded).

    Returns:
        Dict with:
        - drivers: List of driver metadata (filename, device_type, device_version, dd_version)
        - total: Total count

    Example response:
        {
            "drivers": [
                {
                    "filename": "DefensePro-10.6.0.0-DD-1.00-17.jar",
                    "device_type": "DefensePro",
                    "device_version": "10.6.0.0",
                    "dd_version": "1.00-17"
                }
            ],
            "total": 15
        }
    """
    try:
        filenames = list_existing_drivers()

        drivers = []
        for filename in filenames:
            parsed = parse_driver_filename(filename)
            if parsed:
                drivers.append({
                    "filename": filename,
                    "device_type": parsed["device_type"],
                    "device_version": parsed["device_version"],
                    "dd_version": parsed["dd_version"],
                })

        logger.info(f"Listed {len(drivers)} device drivers")

        return {
            "drivers": drivers,
            "total": len(drivers)
        }

    except Exception as exc:
        logger.error(f"Failed to list device drivers: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list device drivers: {str(exc)}"
        )


@router.post("/cc/{cc_ip}/device-drivers/upload")
async def upload_device_driver(
        cc_ip: str,
        file: UploadFile = File(...),
        _current_user=Depends(require_cc_access),
        mongo_db=Depends(get_mongo_db),
) -> Dict[str, Any]:
    """Upload a new device driver JAR file.

    Args:
        cc_ip: CyberController IP (for route consistency)
        file: JAR file to upload

    Returns:
        Dict with:
        - message: Success message
        - filename: Uploaded filename
        - metadata: Driver metadata

    Errors:
        - 400: Invalid filename format
        - 409: Driver already exists
        - 500: Upload failed
    """
    try:
        # Validate file extension
        if not file.filename or not file.filename.endswith('.jar'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a .jar file"
            )

        # Save file and get metadata
        success, message, metadata = await save_uploaded_driver(
            file=file,
            uploaded_by=_current_user.username if _current_user else None
        )

        if not success:
            if "already exists" in message.lower():
                # Driver exists - that's OK! Return success so user can still install it
                # Find the existing driver metadata
                existing_filename = message.split(": ")[1] if ": " in message else file.filename

                return {
                    "message": "Driver already available. You can install it below.",
                    "filename": existing_filename,
                    "metadata": None  # Don't need metadata for existing driver
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=message
                )

        # Store metadata in MongoDB
        if metadata:
            try:
                collection = mongo_db["device_drivers"]
                result = collection.insert_one(metadata)
                logger.info(f"Stored driver metadata in MongoDB: {metadata['filename']}")

                # Convert ObjectId to string for JSON serialization
                metadata["_id"] = str(result.inserted_id)
            except Exception as mongo_exc:
                logger.warning(f"Failed to store metadata in MongoDB (non-fatal): {mongo_exc}")

        # Convert datetime to ISO string for JSON serialization
        if metadata and "upload_date" in metadata:
            metadata["upload_date"] = metadata["upload_date"].isoformat()

        return {
            "message": message,
            "filename": metadata["filename"] if metadata else file.filename,
            "metadata": metadata
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to upload device driver: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(exc)}"
        )


@router.post("/cc/{cc_ip}/device-drivers/deploy")
async def deploy_device_drivers(
        cc_ip: str,
        payload: DeviceDriverDeploy,
        _current_user=Depends(require_cc_access),
        mongo_db=Depends(get_mongo_db),
) -> Dict[str, Any]:
    """Deploy selected device drivers to CyberController.

    Workflow:
    1. Validate all driver filenames exist
    2. Deploy each driver sequentially (continue on failure)
    3. Update MongoDB deployment status
    4. Return summary with succeeded/failed counts

    Args:
        cc_ip: CyberController IP address
        payload: List of driver filenames to deploy

    Returns:
        Dict with:
        - total: Total drivers attempted
        - succeeded: Number of successful deployments
        - failed: Number of failed deployments
        - results: Per-driver results with filename, success, message

    Example request:
        {
            "driver_filenames": [
                "DefensePro-10.6.0.0-DD-1.00-17.jar",
                "DefensePro-8.30.0.0-DD-1.00-7.jar"
            ]
        }

    Example response:
        {
            "total": 2,
            "succeeded": 2,
            "failed": 0,
            "results": [
                {
                    "filename": "DefensePro-10.6.0.0-DD-1.00-17.jar",
                    "success": true,
                    "message": "M_01472: Upload of device driver succeeded."
                },
                {
                    "filename": "DefensePro-8.30.0.0-DD-1.00-7.jar",
                    "success": true,
                    "message": "Already exists: M_00777: The device driver ... already exists"
                }
            ]
        }
    """
    try:
        driver_filenames = payload.driver_filenames

        if not driver_filenames:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No drivers specified for deployment"
            )

        # Validate all drivers exist before starting deployment
        existing_drivers = list_existing_drivers()
        missing_drivers = [f for f in driver_filenames if f not in existing_drivers]

        if missing_drivers:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Driver files not found: {', '.join(missing_drivers)}"
            )

        logger.info(f"Starting deployment of {len(driver_filenames)} drivers to CC {cc_ip}")

        # Deploy drivers sequentially
        summary = deploy_multiple_drivers(cc_ip, driver_filenames)

        # Update MongoDB deployment status for successful deployments
        try:
            collection = mongo_db["device_drivers"]
            now = datetime.now(timezone.utc)

            for result in summary["results"]:
                if result["success"]:
                    collection.update_one(
                        {"filename": result["filename"]},
                        {
                            "$set": {
                                "status": "deployed",
                                "last_deployed": now
                            }
                        },
                        upsert=True
                    )
        except Exception as mongo_exc:
            logger.warning(f"Failed to update MongoDB deployment status (non-fatal): {mongo_exc}")

        # Log summary
        logger.info(
            f"Deployment to CC {cc_ip} complete: "
            f"{summary['succeeded']}/{summary['total']} succeeded, "
            f"{summary['failed']}/{summary['total']} failed"
        )

        return summary

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to deploy device drivers: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deployment failed: {str(exc)}"
        )


@router.get("/cc/{cc_ip}/device-drivers/match")
async def match_device_drivers(
        cc_ip: str,
        device_type: str,
        device_version: str,
        _current_user=Depends(require_cc_access),
) -> Dict[str, Any]:
    """Find matching device driver for given type and version.

    Utility endpoint to help match simulators to available drivers.
    Args:
        cc_ip: CyberController IP
        device_type: Device type (e.g., "DefensePro")
        device_version: Device version (e.g., "10.6.0.0")

    Returns:
        Dict with:
        - matched: bool
        - filename: Matching JAR filename if found, null otherwise

    Example:
        GET /api/cc/172.17.154.218/device-drivers/match?device_type=DefensePro&device_version=10.6.0.0

        Response:
        {
            "matched": true,
            "filename": "DefensePro-10.6.0.0-DD-1.00-17.jar"
        }
    """
    try:
        filename = match_driver_filename(device_type, device_version)

        return {
            "matched": filename is not None,
            "filename": filename
        }

    except Exception as exc:
        logger.error(f"Failed to match device driver: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Match failed: {str(exc)}"
        )


__all__ = ["router"]
