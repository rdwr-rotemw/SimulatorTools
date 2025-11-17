"""
CyberController integration module

Provides:
- CCDevice: dataclass describing a device known to CyberController
- CCCredentials: dataclass holding session info (JSESSIONID)
- CCHandler: instance-based handler that authenticates and performs CRUD
  operations against a CyberController REST API (uses requests, verify=False).
- get_cc_handler: module-level singleton factory that returns a handler per
  (cc_ip, username, password) tuple and auto-authenticates on creation.

NOTE: Endpoints used by this client are best-effort guesses. Adjust endpoint
paths to match your CyberController deployment if needed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
import ipaddress
import logging
import threading

import requests
import urllib3

# Suppress only the single InsecureRequestWarning raised when verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Module-level singleton storage
_LOCK = threading.Lock()
_HANDLERS: Dict[Tuple[str, str, str], "CCHandler"] = {}

# Logger for CC client operations
logger = logging.getLogger("sim-tools.cc_client")


@dataclass
class CCDevice:
    """Structured representation of a CyberController device.

    Only a single IP field (management_ip) is retained. Previously both
    ip_address and management_ip were present but they represented the same
    value in our usage, so ip_address was removed for clarity.
    """

    management_ip: str
    name: Optional[str] = None
    device_id: Optional[str] = None
    device_type: Optional[str] = None
    status: Optional[str] = None


@dataclass
class CCCredentials:
    """Holds authentication/session information for CyberController.

    jsession_id: Optional[str] = None
    cc_ip: Optional[str] = None
    authenticated_at: Optional[datetime] = None
    """

    jsession_id: Optional[str] = None
    cc_ip: Optional[str] = None
    authenticated_at: Optional[datetime] = None


class CCHandler:
    """Instance-based handler for a CyberController server.

    This class uses the requests library and disables SSL verification by
    default (verify=False). All public methods return a Tuple[bool, Any] where
    the boolean indicates success and the second value is either the result or
    an error message.
    """

    def __init__(self, cc_ip: str, username: str, password: str):
        """Create a handler for a CyberController instance.

        Args:
            cc_ip: IP or hostname of the CyberController (no scheme)
            username: administrative username
            password: password
        """
        self.cc_ip = cc_ip
        self.username = username
        self.password = password
        self.base_url = f"https://{cc_ip}"
        self._session = requests.Session()
        # Use verify=False as requested; individual methods still pass verify
        self._verify_ssl = False
        self._creds: Optional[CCCredentials] = None

    def login(self) -> Tuple[bool, str]:
        """Authenticate to the CyberController and store JSESSIONID.

        Returns:
            (True, 'OK') on success or (False, error_message) on failure.
        """
        try:
            # Common CyberController form-based auth endpoint (adjust if needed)
            login_url = f"{self.base_url}/mgmt/system/user/login"
            payload = {"username": self.username, "password": self.password}
            resp = self._session.post(login_url, json=payload, verify=self._verify_ssl, timeout=30)

            # Some CC versions set JSESSIONID cookie on any response that sets it; try to extract it
            jsession = None
            # cookies may contain 'JSESSIONID' or 'JSESSIONIDCC' etc. Take the first JSESSION-like cookie
            for name, cookie in self._session.cookies.items():
                if name.upper().startswith("JSESSION"):
                    jsession = cookie
                    break

            if not jsession:
                # fallback: check response headers for set-cookie
                sc = resp.headers.get("Set-Cookie", "")
                if "JSESSION" in sc:
                    jsession = sc

            if not jsession:
                # As a last resort, treat 200/302 as success but warn
                if resp.status_code not in (200, 302):
                    logger.error(f"Login failed to {self.cc_ip}: HTTP {resp.status_code}")
                    return False, f"Login failed: HTTP {resp.status_code}"
                logger.error(f"Login to {self.cc_ip} did not return JSESSIONID cookie")
                return False, "Login response did not contain JSESSIONID cookie"

            self._creds = CCCredentials(jsession_id=str(jsession), cc_ip=self.cc_ip, authenticated_at=datetime.now(timezone.utc))
            return True, "OK"
        except Exception as exc:  # pragma: no cover - network error handling
            logger.error(f"Exception during login to {self.cc_ip}: {exc!s}")
            return False, f"Exception during login: {exc!s}"

    def logout(self, jsession_id: str) -> Tuple[bool, str]:
        """Gracefully close the session on the CyberController.

        Args:
            jsession_id: The JSESSIONID to disconnect

        Returns:
            (True, 'Logout successful') on success or (False, error_message) on failure.
        """
        try:
            logout_url = f"{self.base_url}/mgmt/system/user/logout"

            # Create a temporary session with the provided JSESSIONID
            temp_session = requests.Session()
            temp_session.cookies.set("JSESSIONID", jsession_id)

            # POST to logout endpoint with JSESSIONID cookie
            resp = temp_session.post(logout_url, verify=self._verify_ssl, timeout=10)

            # Clear local session state regardless of server response
            self._creds = None
            try:
                self._session.cookies.clear()
            except Exception:
                pass

            # Check server response
            if resp.status_code == 200:
                return True, "Logout successful"
            else:
                logger.error(f"Logout from {self.cc_ip} failed: HTTP {resp.status_code}")
                return False, f"Logout failed: HTTP {resp.status_code}"

        except Exception as exc:  # pragma: no cover
            # Clear local state even on exception
            self._creds = None
            try:
                self._session.cookies.clear()
            except Exception:
                pass
            logger.error(f"Exception during logout from {self.cc_ip}: {exc!s}")
            return False, f"Exception during logout: {exc!s}"
            logger.error(f"Exception during logout from {self.cc_ip}: {exc!s}")
            return False, f"Exception during logout: {exc!s}"

    def is_authenticated(self) -> Tuple[bool, str]:
        """Check whether the current session appears authenticated.

        Performs a lightweight GET to the base URL and returns True if we get a
        200 response and a JSESSION cookie is present in the session.

        Returns:
            (True, 'OK') if authenticated, else (False, reason).
        """
        try:
            if not self._creds or not self._creds.jsession_id:
                return False, "No stored credentials"

            try:
                resp = self._session.get(self.base_url, verify=self._verify_ssl, timeout=10)
                if resp.status_code == 200:
                    # also ensure a JSESSION-like cookie exists
                    for name in self._session.cookies.keys():
                        if name.upper().startswith("JSESSION"):
                            return True, "OK"
                    return False, "No JSESSION cookie present"
                return False, f"Unexpected status code: {resp.status_code}"
            except Exception as exc:
                return False, f"Connection/check failed: {exc!s}"
        except Exception as exc:  # pragma: no cover
            return False, f"Exception during is_authenticated: {exc!s}"

    def is_logged_in(self) -> bool:
        """Return True if session JSESSIONID cookie is valid for the user.

        Performs GET to `/mgmt/system/user/info?showpolicies=true` and verifies
        the returned JSON contains a `username` field matching `self.username`.
        This method performs validation only and avoids mutating the handler's
        session or stored credentials (no side effects).
        Returns False on any exception or mismatch.
        """
        try:
            if not self._creds or not self._creds.jsession_id:
                return False
            info_url = f"{self.base_url}/mgmt/system/user/info?showpolicies=true"
            # Use a one-off requests.get call and pass the JSESSION cookie explicitly
            # so we do not mutate self._session.cookies (pure validation).
            cookies = {"JSESSIONID": self._creds.jsession_id}
            resp = requests.get(info_url, cookies=cookies, verify=self._verify_ssl, timeout=15)
            if resp.status_code != 200:
                return False
            try:
                data = resp.json()
            except Exception:
                return False
            username = data.get("username") or data.get("user") or data.get("name")
            return bool(username and username == self.username)
        except Exception:
            return False

    def refresh_session(self) -> Tuple[bool, str]:
        """Attempt to re-authenticate using stored username/password.

        Calls `login()` and, on success, updates the internal credentials and
        ensures the session contains the new JSESSIONID cookie. Returns
        (True, 'OK') on success or (False, error_message) on failure.
        """
        try:
            ok, msg = self.login()
            if not ok:
                return False, msg

            # Ensure the session has the new JSESSIONID if available.
            if self._creds and self._creds.jsession_id:
                try:
                    # set a conventional cookie name; the server may use other
                    # JSESSION-like names but JSESSIONID is the common one.
                    self._session.cookies.set("JSESSIONID", str(self._creds.jsession_id))
                except Exception:
                    # non-fatal: return success since login itself succeeded
                    pass

            return True, "OK"
        except Exception as exc:  # pragma: no cover - network/login errors
            return False, f"Exception during refresh_session: {exc!s}"

    def _map_device(self, raw: Dict[str, Any]) -> CCDevice:
        """Map a raw device dict from CC API to CCDevice dataclass.

        This mapping is permissive: missing keys become None.
        """
        management_ip = str(
            raw.get("managementIp")
            or raw.get("management_ip")
            or raw.get("mgmtIp")
            or raw.get("ip")
            or raw.get("ipAddress")
            or raw.get("address")
            or ""
        )
        return CCDevice(
            management_ip=management_ip,
            name=raw.get("name") or raw.get("displayName"),
            device_id=str(raw.get("id") or raw.get("deviceId") or ""),
            device_type=raw.get("type") or raw.get("deviceType"),
            status=raw.get("status"),
        )

    def get_all_devices(self) -> Tuple[bool, Union[str, List[CCDevice]]]:
        """Fetch all devices from the CyberController and return a list of CCDevice.

        Returns:
            (True, [CCDevice, ...]) on success or (False, error_message) on failure.
        """
        try:
            if not self.is_logged_in():
                ok, msg = self.refresh_session()
                if not ok:
                    # caller expects a failure tuple; raise to be caught below
                    raise RuntimeError(f"Authentication required and refresh failed: {msg}")
            # Try a few common device listing endpoints - adjust as needed for your CC
            candidates = ("/api/devices", "/devices", "/rest/devices", "/api/device")
            last_err = "No endpoints tried"
            for path in candidates:
                url = f"{self.base_url}{path}"
                try:
                    resp = self._session.get(url, verify=self._verify_ssl, timeout=30)
                except Exception as exc:
                    last_err = f"Connection failed for {url}: {exc!s}"
                    continue

                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except Exception:
                        # If response is not JSON, skip
                        last_err = f"Non-JSON response from {url}"
                        continue

                    # data could be a dict with items under a key or a list
                    devices_raw = []
                    if isinstance(data, dict):
                        # try common wrapper keys
                        for key in ("devices", "items", "data"):
                            if key in data and isinstance(data[key], list):
                                devices_raw = data[key]
                                break
                        else:
                            # fallback: if dict contains many device-like dicts, try to extract
                            # if values are dicts and contain 'ip' keys, treat them as list
                            maybe = [v for v in data.values() if isinstance(v, dict) and ("ip" in v or "name" in v)]
                            if maybe:
                                devices_raw = maybe
                    elif isinstance(data, list):
                        devices_raw = data

                    if not devices_raw:
                        last_err = f"No device array found in response from {url}"
                        continue

                    devices = [self._map_device(d) for d in devices_raw]
                    return True, devices

                last_err = f"Unexpected HTTP {resp.status_code} from {url}"

            return False, f"Failed to fetch devices: {last_err}"
        except Exception as exc:  # pragma: no cover
            return False, f"Exception in get_all_devices: {exc!s}"

    def get_device_by_ip(self, ip: str) -> Tuple[bool, Union[str, CCDevice]]:
        """Find a single device by its IP (management or device IP).

        Returns:
            (True, CCDevice) if found, else (False, message).
        """
        try:
            if not self.is_logged_in():
                ok, msg = self.refresh_session()
                if not ok:
                    raise RuntimeError(f"Authentication required and refresh failed: {msg}")
            ok, res = self.get_all_devices()
            if not ok:
                return False, f"Could not list devices: {res}"

            devices: List[CCDevice] = res  # type: ignore
            for d in devices:
                if d.management_ip == ip:
                    return True, d
            return False, f"Device with IP {ip} not found"
        except Exception as exc:  # pragma: no cover
            return False, f"Exception in get_device_by_ip: {exc!s}"

    def add_device(self, name: str, parent_orm: Any, management_ip: str, device_type: str, user: str, password: str) -> Tuple[bool, Union[str, CCDevice]]:
        """Add a single device to CyberController.

        Args:
            name: device display name
            parent_orm: parent object id or representation expected by CC (pass-through)
            management_ip: device management IP address
            device_type: type identifier
            user: device username
            password: device password

        Returns:
            (True, CCDevice) on success or (False, error_message) on failure.
        """
        try:
            if not self.is_logged_in():
                ok, msg = self.refresh_session()
                if not ok:
                    raise RuntimeError(f"Authentication required and refresh failed: {msg}")
            url = f"{self.base_url}/api/devices"
            payload = {
                "name": name,
                "parent": parent_orm,
                "managementIp": management_ip,
                "type": device_type,
                "credentials": {"user": user, "password": password},
            }
            resp = self._session.post(url, json=payload, verify=self._verify_ssl, timeout=30)
            if resp.status_code in (200, 201):
                try:
                    data = resp.json()
                except Exception:
                    # fallback: create CCDevice from provided info
                    device = CCDevice(management_ip=management_ip, name=name, device_type=device_type)
                    return True, device

                # map and return
                device = self._map_device(data if isinstance(data, dict) else (data[0] if isinstance(data, list) and data else {}))
                return True, device
            return False, f"Failed to add device: HTTP {resp.status_code} - {resp.text}"
        except Exception as exc:  # pragma: no cover
            return False, f"Exception in add_device: {exc!s}"

    def delete_device(self, ip_address: str) -> Tuple[bool, str]:
        """Delete a device from CyberController identified by IP address.

        Returns:
            (True, 'OK') on success or (False, error_message) on failure.
        """
        try:
            if not self.is_logged_in():
                ok, msg = self.refresh_session()
                if not ok:
                    raise RuntimeError(f"Authentication required and refresh failed: {msg}")
            # Discover device id first
            ok, found = self.get_device_by_ip(ip_address)
            if not ok:
                return False, f"Device lookup failed: {found}"

            device: CCDevice = found  # type: ignore
            if not device.device_id:
                url = f"{self.base_url}/api/devices?managementIp={ip_address}"
                resp = self._session.delete(url, verify=self._verify_ssl, timeout=30)
            else:
                url = f"{self.base_url}/api/devices/{device.device_id}"
                resp = self._session.delete(url, verify=self._verify_ssl, timeout=30)

            if resp.status_code in (200, 204):
                return True, "OK"
            return False, f"Failed to delete device: HTTP {resp.status_code} - {resp.text}"
        except Exception as exc:  # pragma: no cover
            return False, f"Exception in delete_device: {exc!s}"

    def add_device_range(self, name_convention: str, parent_orm: Any, device_type: str, start_ip: str, end_ip: str, user: str, password: str) -> Tuple[bool, str]:
        """Add a range of devices created from an IP start/end inclusive.

        name_convention may include a single formatting placeholder '{ip}' or '{i}' to
        embed the IP or an incremental index into the device name.

        Returns:
            (True, 'OK') on full success, or (False, error_message) on first failure.
        """
        try:
            if not self.is_logged_in():
                ok, msg = self.refresh_session()
                if not ok:
                    raise RuntimeError(f"Authentication required and refresh failed: {msg}")
            start = ipaddress.ip_address(start_ip)
            end = ipaddress.ip_address(end_ip)
            if start > end:
                return False, "start_ip must be <= end_ip"

            cur = int(start)
            last = int(end)
            idx = 1
            for ip_int in range(cur, last + 1):
                ip_str = str(ipaddress.ip_address(ip_int))
                if "{ip}" in name_convention:
                    name = name_convention.replace("{ip}", ip_str)
                elif "{i}" in name_convention:
                    name = name_convention.replace("{i}", str(idx))
                else:
                    name = f"{name_convention}-{ip_str}"

                ok, res = self.add_device(name=name, parent_orm=parent_orm, management_ip=ip_str, device_type=device_type, user=user, password=password)
                if not ok:
                    return False, f"Failed to add device {ip_str}: {res}"
                idx += 1

            return True, "OK"
        except Exception as exc:  # pragma: no cover
            return False, f"Exception in add_device_range: {exc!s}"


def get_cc_handler(cc_ip: str, username: str, password: str) -> CCHandler:
    """Return a singleton CCHandler for the given (cc_ip, username, password).

    The handler will be auto-authenticated (login called) on first creation.
    Subsequent calls with the same credentials will return the cached instance.
    """
    key = (cc_ip, username, password)
    with _LOCK:
        if key in _HANDLERS:
            return _HANDLERS[key]

        handler = CCHandler(cc_ip=cc_ip, username=username, password=password)
        # Auto-authenticate but do not raise on failure; caller can check is_authenticated().
        try:
            handler.login()
        except Exception:
            # swallow - login returns (bool, str) and internal exceptions are handled
            pass

        _HANDLERS[key] = handler
        return handler


__all__ = ["CCDevice", "CCCredentials", "CCHandler", "get_cc_handler"]
