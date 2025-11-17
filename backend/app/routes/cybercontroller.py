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

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.modules.cc.cc_client import get_cc_handler, CCDevice, CCHandler
from backend.app.utils.auth import require_cc_access
from backend.app.utils.database import get_db
from backend.app.models.user import User
from backend.app.models.cc_session import CCSession

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
    then attempts to login. On success, stores the JSESSIONID in the database
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
    username: str = Query(..., description="CC username"),
    password: str = Query(..., description="CC password"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cc_access),
) -> CCDevicesListResponse:
    """Get all devices (simulators) from a CyberController instance.

    Args:
        cc_ip: CyberController IP address or hostname
        username: CC authentication username (query param)
        password: CC authentication password (query param)
        db: Database session
        current_user: Authenticated user with cc_admin or admin role

    Returns:
        CCDevicesListResponse containing list of devices

    Raises:
        HTTPException: If authentication or device retrieval fails
    """
    try:
        handler = get_cc_handler(cc_ip, username, password)

        # Ensure authenticated (handler will auto-refresh if needed)
        if not handler.is_logged_in():
            ok, msg = handler.refresh_session()
            if not ok:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"CC authentication failed: {msg}"
                )

        # Get all devices
        ok, result = handler.get_all_devices()
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve devices: {result}"
            )

        devices: List[CCDevice] = result  # type: ignore

        # Convert to response model
        device_responses = [
            CCDeviceResponse(
                management_ip=d.management_ip,
                name=d.name,
                device_id=d.device_id,
                device_type=d.device_type,
                status=d.status,
            )
            for d in devices
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
        handler = get_cc_handler(cc_ip, payload.username, payload.password)

        # Ensure authenticated
        if not handler.is_logged_in():
            ok, msg = handler.refresh_session()
            if not ok:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"CC authentication failed: {msg}"
                )

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
    username: str = Query(..., description="CC username"),
    password: str = Query(..., description="CC password"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cc_access),
) -> CCDeleteResponse:
    """Delete a device (simulator) from a CyberController instance.

    Args:
        cc_ip: CyberController IP address or hostname
        simulator_ip: IP address of the simulator to delete
        username: CC authentication username (query param)
        password: CC authentication password (query param)
        db: Database session
        current_user: Authenticated user with cc_admin or admin role

    Returns:
        CCDeleteResponse with success status and message

    Raises:
        HTTPException: If authentication or device deletion fails
    """
    try:
        handler = get_cc_handler(cc_ip, username, password)

        # Ensure authenticated
        if not handler.is_logged_in():
            ok, msg = handler.refresh_session()
            if not ok:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"CC authentication failed: {msg}"
                )

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
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active session found for CC {cc_ip}"
            )

        # Get the jsession_id from the database
        jsession_id = str(cc_session.jsession_id)

        # Create CCHandler instance without logging in (we only need it to call logout)
        # Use empty strings for username/password since we're not authenticating
        handler = CCHandler(cc_ip, "", "")

        # Call logout with the stored jsession_id
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


@router.get(
    "/cc/{cc_ip}/irp/IdsDataFormat",
    status_code=status.HTTP_200_OK,
    response_model=CCIdsDataFormatResponse,
)
async def get_ids_data_format(
    cc_ip: str,
    username: str = Query(..., description="CC username"),
    password: str = Query(..., description="CC password"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_cc_access),
) -> CCIdsDataFormatResponse:
    """Get IdsDataFormat XML files from CyberController.

    This endpoint retrieves the list of IdsDataFormat XML configuration files
    available on the CyberController instance.

    Args:
        cc_ip: CyberController IP address or hostname
        username: CC authentication username (query param)
        password: CC authentication password (query param)
        db: Database session
        current_user: Authenticated user with cc_admin or admin role

    Returns:
        CCIdsDataFormatResponse containing list of XML file names

    Raises:
        HTTPException: If authentication or file retrieval fails
    """
    try:
        handler = get_cc_handler(cc_ip, username, password)

        # Ensure authenticated
        if not handler.is_logged_in():
            ok, msg = handler.refresh_session()
            if not ok:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"CC authentication failed: {msg}"
                )

        # TODO: Implement IdsDataFormat XML retrieval in CCHandler
        # For now, return placeholder
        # Example implementation:
        # ok, files = handler.get_ids_data_format_files()
        # if not ok:
        #     raise HTTPException(
        #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        #         detail=f"Failed to retrieve IdsDataFormat files: {files}"
        #     )

        # Placeholder response
        return CCIdsDataFormatResponse(
            files=["IdsDataFormat_placeholder.xml"]
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving IdsDataFormat: {exc!s}"
        )


__all__ = ["router"]

