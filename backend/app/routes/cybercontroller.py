"""CyberController REST integration routes.

Endpoints:
- POST   /api/cc/{cc_ip}/login                                -> authenticate CC handler
- POST   /api/cc/{cc_ip}/logout                               -> logout from CC handler
- GET    /api/cc/{cc_ip}/simulators                           -> list devices from CC
- POST   /api/cc/{cc_ip}/simulators                           -> add device to CC
- DELETE /api/cc/{cc_ip}/simulators/{simulator_ip}            -> delete device from CC
- GET    /api/cc/{cc_ip}/irp/IdsDataFormat                    -> get IdsDataFormat XML files

All endpoints require the caller to possess either 'admin' or 'cc_admin' role
(enforced by `require_cc_access`). Authentication to the CyberController is
handled via username/password in request body or query parameters.
"""
from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.models.cc_session import CCSession
from backend.app.models.user import User
from backend.app.modules.cc.cc_client import get_cc_handler, CCDevice, CCHandler, CCCredentials
from backend.app.modules.sapro.sapro_client import get_sapro_handler
from backend.app.modules.sapro.src.returnTypes.models import SaproDevice
from backend.app.modules.reporter.irp.irp_module import convert_xml
from backend.app.utils.database import get_mongo_db
from backend.app.modules.mongo_models import IRPMessageTemplate
from backend.app.utils.auth import require_cc_access
from backend.app.utils.database import get_db

logger = logging.getLogger("sim-tools.cybercontroller")

router = APIRouter(prefix="/api", tags=["cybercontroller"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CCLoginPayload(BaseModel):
    """Login payload for CyberController authentication."""
    username: str
    password: str


class CCLoginResponse(BaseModel):
    """Response for CC login."""
    success: bool
    message: str


class CCAddDevicePayload(BaseModel):
    """Payload for adding a device to CyberController."""
    username: str
    password: str
    name: str
    management_ip: str
    device_type: str
    device_user: str
    device_password: str
    parent_orm: Optional[Any] = None


class CCDeviceResponse(BaseModel):
    """Single device response."""
    management_ip: str
    name: Optional[str] = None
    device_id: Optional[str] = None
    device_type: Optional[str] = None
    status: Optional[str] = None


class CCDevicesListResponse(BaseModel):
    """List of devices response."""
    devices: List[CCDeviceResponse]


class CCDeleteResponse(BaseModel):
    """Response for device deletion."""
    success: bool
    message: str


class CCLogoutResponse(BaseModel):
    """Response for CC logout."""
    success: bool
    message: str


class CCIdsDataFormatResponse(BaseModel):
    """Response for IdsDataFormat XML files."""
    files: List[str]


class IdsDataFormatPayload(BaseModel):
    """Payload for listing IdsDataFormat files via SSH credentials."""
    username: str
    password: str


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
            return CCLoginResponse(success=False, message=f"Login failed: {msg}")

        # Get the JSESSIONID from the handler's credentials
        if not handler._creds or not handler._creds.jsession_id:
            return CCLoginResponse(success=False, message="Login succeeded but no JSESSIONID found")

        jsession_id = handler._creds.jsession_id

        # Check if a session already exists for this user and CC
        existing_session = db.query(CCSession).filter(
            CCSession.cc_ip == cc_ip,
            CCSession.user_id == current_user.user_id
        ).first()

        if existing_session:
            # Update existing session with new JSESSIONID
            existing_session.jsession_id = jsession_id
            existing_session.login_time = handler._creds.authenticated_at
            existing_session.last_activity = None
        else:
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
    except Exception as exc:
        db.rollback()
        return CCLoginResponse(success=False, message=f"Login error: {exc!s}")


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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve devices: {result}"
            )

        # Query Sapro for available simulators and filter DP devices accordingly
        sapro_sims =  list[SaproDevice]
        try:
            sapro_handler = get_sapro_handler()
            sapro_sims = sapro_handler.get_all_devices()
        except Exception as e:
            logger.error(f"failed to get sapro simulators: {str(e)}")

        sapro_ips = {getattr(s, 'ip_address', None) for s in sapro_sims if
                     getattr(s, 'ip_address', None) is not None}
        filtered_devices = [d for d in result if d.management_ip in sapro_ips]

        # Convert to response model
        device_responses = [
            CCDeviceResponse(
                management_ip=d.management_ip,
                name=d.name,
                device_id=d.device_id,
                device_type=d.device_type,
                status=d.status,
            )
            for d in filtered_devices
        ]

        return CCDevicesListResponse(devices=device_responses)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving devices: {exc!s}"
        )


@router.post(
    "/cc/{cc_ip}/simulators",
    status_code=status.HTTP_201_CREATED,
    response_model=CCDeviceResponse,
)
async def add_cc_simulator(
        cc_ip: str,
        payload: CCAddDevicePayload,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_cc_access),
) -> CCDeviceResponse:
    """Add a device (simulator) to a CyberController instance.

    Args:
        cc_ip: CyberController IP address or hostname
        payload: Device details and CC credentials
        db: Database session
        current_user: Authenticated user with cc_admin or admin role

    Returns:
        CCDeviceResponse with the created device details

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

        # Add device
        ok, result = handler.add_device(
            name=payload.name,
            parent_orm=payload.parent_orm,
            management_ip=payload.management_ip,
            device_type=payload.device_type,
            user=payload.device_user,
            password=payload.device_password,
        )

        if not ok:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to add device: {result}"
            )

        device: CCDevice = result  # type: ignore

        return CCDeviceResponse(
            management_ip=device.management_ip,
            name=device.name,
            device_id=device.device_id,
            device_type=device.device_type,
            status=device.status,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding device: {exc!s}"
        )


@router.delete(
    "/cc/{cc_ip}/simulators/{simulator_ip}",
    status_code=status.HTTP_200_OK,
    response_model=CCDeleteResponse,
)
async def delete_cc_simulator(
        cc_ip: str,
        simulator_ip: str,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_cc_access),
) -> CCDeleteResponse:
    """Delete a device (simulator) from a CyberController instance.

    Args:
        cc_ip: CyberController IP address or hostname
        simulator_ip: IP address of the simulator to delete
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

        # Delete device
        ok, msg = handler.delete_device(simulator_ip)

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


class IdsDownloadPayload(BaseModel):
    """Payload for downloading an IdsDataFormat based on simulator version.

    sim_version: Simulator version string such as "10.3.0" or "8.2.1". This
    will be converted to the corresponding IdsDataFormat filename (for example
    "10.3.0" -> "IdsDataFormat100300.xml") and that file will be downloaded
    via SCP to /tmp/data_formats/ on the backend host.
    """
    sim_version: str
    username: str
    password: str


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

    This endpoint accepts a simulator version string (for example "10.6.0.0" or
    "8.2.1"). The version is converted to the corresponding IdsDataFormat
    filename (e.g. "IdsDataFormat100300.xml"), then the endpoint connects to
    the CC host via SSH using provided root credentials and downloads the file
    via SCP to /tmp/data_formats/ on the backend host.

    Returns a JSON object with keys: success (bool), message (str), local_path (str).
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
        try:
            handler._session.cookies.set("JSESSIONID", str(cc_session.jsession_id))
        except Exception:
            pass

        ok, res = handler.download_ids_data_format(payload.sim_version, payload.username, payload.password)
        if not ok:
            return {"success": False, "message": res, "local_path": "", "mongo_id": ""}

        local_path = res

        # Ensure file exists before attempting conversion
        if not os.path.exists(local_path):
            return {"success": False, "message": f"Downloaded file not found: {local_path}", "local_path": local_path, "mongo_id": ""}

        # Convert XML to JSON-like structure and insert into MongoDB
        try:
            converted = convert_xml(local_path)
            # Debug: print what convert_xml returns
            print("DEBUG convert_xml output:")
            print(f"Type: {type(converted)}")
            print(f"Keys: {list(converted.keys()) if isinstance(converted, dict) else 'N/A'}")
            print(f"Content: {converted}")
            mongo_db = get_mongo_db()
            template_name = os.path.basename(local_path)
            if template_name.lower().endswith('.xml'):
                template_name = template_name[:-4]

            doc = IRPMessageTemplate(
                template_name=template_name,
                description=f"Downloaded from {cc_ip}",
                schema=converted,  # Pass entire converted schema dict
                IdsDataFormat_version=payload.sim_version,
                user_id=str(current_user.user_id),
            )

            result = mongo_db.irp_data_formats.insert_one(doc.model_dump())
            mongo_id = str(result.inserted_id)

            return {"success": True, "message": "Downloaded and saved", "local_path": local_path, "mongo_id": mongo_id}
        except FileNotFoundError:
            return {"success": False, "message": "Downloaded file disappeared before conversion", "local_path": local_path, "mongo_id": ""}
        except Exception as exc:
            # Conversion or Mongo insertion failed
            return {"success": False, "message": f"Conversion/Mongo error: {exc!s}", "local_path": local_path, "mongo_id": ""}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading IdsDataFormat: {exc!s}"
        )


__all__ = ["router"]
