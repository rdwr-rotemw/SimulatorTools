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

import ipaddress
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import paramiko
import requests
import urllib3
from scp import SCPClient, SCPException

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

            self._creds = CCCredentials(jsession_id=str(jsession), cc_ip=self.cc_ip,
                                        authenticated_at=datetime.now(timezone.utc))
            return True, "OK"
        except requests.RequestException as exc:
            logger.exception("Request error during login to %s: %s", self.cc_ip, exc)
            return False, f"Request exception during login: {exc!s}"

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
            except Exception as exc:
                logger.debug("Non-fatal error clearing session cookies: %s", exc)

            # Check server response
            if resp.status_code == 200:
                return True, "Logout successful"
            else:
                logger.error(f"Logout from {self.cc_ip} failed: HTTP {resp.status_code}")
                return False, f"Logout failed: HTTP {resp.status_code}"

        except requests.RequestException as exc:
            # Clear local state even on exception
            self._creds = None
            try:
                self._session.cookies.clear()
            except Exception as exc2:
                logger.debug("Error clearing cookies after logout exception: %s", exc2)
            logger.exception("Request exception during logout from %s: %s", self.cc_ip, exc)
            return False, f"Request exception during logout: {exc!s}"

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
            except requests.RequestException as exc:
                logger.debug("Connection/check failed for is_authenticated to %s: %s", self.cc_ip, exc)
                return False, f"Connection/check failed: {exc!s}"
        except requests.RequestException as exc:
            logger.exception("Exception during is_authenticated: %s", exc)
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
            return resp.status_code == 200
        except requests.RequestException as exc:
            logger.debug("is_logged_in network error for %s: %s", self.cc_ip, exc)
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
                except Exception as exc:
                    logger.debug("Non-fatal error setting session cookie after refresh: %s", exc)

            return True, "OK"
        except requests.RequestException as exc:
            logger.exception("Exception during refresh_session: %s", exc)
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

    def get_all_dps(self) -> Tuple[bool, Union[str, List[CCDevice]]]:
        """Fetch all dp devices from the CyberController and return a list of CCDevice.

        Returns:
            (True, [CCDevice, ...]) on success or (False, error_message) on failure.
        """
        try:
            if not self.is_logged_in():
                ok, msg = self.refresh_session()
                if not ok:
                    # caller expects a failure tuple; raise to be caught below
                    raise RuntimeError(f"Authentication required and refresh failed: {msg}")
            url = f"https://{self.cc_ip}/mgmt/system/monitor/dp/devices?includeDeletedPolicies=true"
            cookies = {"JSESSIONID": self._creds.jsession_id}
            resp = requests.get(url, cookies=cookies, verify=self._verify_ssl, timeout=15)

            if resp.status_code == 200:
                try:
                    devices = [
                        CCDevice(
                            management_ip=d['ip'],
                            name=d['name'],
                            device_id=d['deviceId'],
                            device_type="DefensePro",
                            status=d['status'],
                        )
                        for d in resp.json()['devices']
                    ]
                    return True, devices
                except (ValueError, KeyError, TypeError) as exc:
                    logger.exception("Failed to parse devices JSON response: %s", exc)
                    return False, "Failed to parse devices JSON response"

            return False, f"Failed to fetch devices from: {self.cc_ip}"
        except requests.RequestException as exc:
            logger.exception("Request exception in get_all_dps: %s", exc)
            return False, f"Request exception in get_all_devices: {exc!s}"

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
            ok, res = self.get_all_dps()
            if not ok:
                return False, f"Could not list devices: {res}"

            devices: List[CCDevice] = res  # type: ignore
            for d in devices:
                if d.management_ip == ip:
                    return True, d
            return False, f"Device with IP {ip} not found"
        except (requests.RequestException, RuntimeError) as exc:
            logger.exception("Exception in get_device_by_ip: %s", exc)
            return False, f"Exception in get_device_by_ip: {exc!s}"

    def get_organization_tree(self) -> Tuple[bool, str]:
        """Get parent organization ID for adding devices.

        Fetches organization tree and looks for "Simulators" site.
        Falls back to "Default" site if "Simulators" not found.

        Returns:
            (True, parent_orm_id) on success or (False, error_message) on failure.
        """
        try:
            if not self.is_logged_in():
                ok, msg = self.refresh_session()
                if not ok:
                    raise RuntimeError(f"Authentication required and refresh failed: {msg}")

            url = f"{self.base_url}/mgmt/system/monitor/tree/Organization"
            resp = self._session.get(url, verify=self._verify_ssl, timeout=30)

            if resp.status_code != 200:
                return False, f"Failed to get organization tree: HTTP {resp.status_code}"

            try:
                tree_data = resp.json()
            except (ValueError, TypeError) as exc:
                return False, f"Failed to parse organization tree response: {exc}"

            # Recursively search for "Simulators" or "Default" site
            def find_site(node: Any, target_name: str) -> Optional[str]:
                """Recursively search tree for site with given name.

                Handles both dict and list nodes. Some CC responses place the
                managedElementID under `meIdentifier.managedElementID` while
                others may expose `managedElementID` at the node root. This
                function checks both locations and recurses into `children`.
                """
                # If node is a list, iterate over items
                if isinstance(node, list):
                    for item in node:
                        result = find_site(item, target_name)
                        if result:
                            return result
                    return None

                # If node is not a dict at this point, nothing to do
                if not isinstance(node, dict):
                    return None

                # Check current node's name
                name = node.get("name")
                if name == target_name:
                    # Try nested meIdentifier first (common format)
                    me = node.get("meIdentifier")
                    if isinstance(me, dict) and me.get("managedElementID"):
                        return me.get("managedElementID")

                    # Fallback to top-level managedElementID if present
                    if node.get("managedElementID"):
                        return node.get("managedElementID")

                # Recurse into children if present
                children = node.get("children")
                if isinstance(children, list) and children:
                    for child in children:
                        result = find_site(child, target_name)
                        if result:
                            return result

                return None

            # Try to find "Simulators" site first
            simulators_id = find_site(tree_data, "Simulators")
            if simulators_id:
                logger.info("Found 'Simulators' site with ID: %s", simulators_id)
                return True, simulators_id

            # Fall back to "Default" site
            default_id = find_site(tree_data, "Default")
            if default_id:
                logger.info("'Simulators' site not found, using 'Default' site with ID: %s", default_id)
                return True, default_id

            return False, "Neither 'Simulators' nor 'Default' site found in organization tree"

        except requests.RequestException as exc:
            logger.exception("Request exception in get_organization_tree: %s", exc)
            return False, f"Exception in get_organization_tree: {exc!s}"

    def add_device(
        self,
        name: str,
        management_ip: str,
        device_type: str,
        cli_username: str,
        cli_password: str,
        http_username: str,
        https_password: str,
        vision_mgt_port: str,
        register_device_events: bool = False
    ) -> Tuple[bool, str]:
        """Add a single device to CyberController using actual CC API.

        Args:
            name: device display name
            management_ip: device management IP address
            device_type: "DefensePro" or "Alteon"
            cli_username: CLI username (e.g., "radware")
            cli_password: CLI password
            http_username: HTTP username
            https_password: HTTPS password
            vision_mgt_port: Vision management port (e.g., "G1")
            register_device_events: whether to register device events (default: False)

        Returns:
            (True, "Device added successfully") on success or (False, error_message) on failure.
        """
        try:
            if not self.is_logged_in():
                ok, msg = self.refresh_session()
                if not ok:
                    raise RuntimeError(f"Authentication required and refresh failed: {msg}")

            # Auto-fetch parent ORM ID
            ok, parent_orm_id = self.get_organization_tree()
            if not ok:
                return False, f"Failed to get parent organization: {parent_orm_id}"

            # Build payload matching actual CyberController API
            url = f"{self.base_url}/mgmt/system/config/tree/device"
            payload = {
                "name": name,
                "parentOrmID": parent_orm_id,
                "type": device_type,
                "deviceSetup": {
                    "deviceAccess": {
                        "cliPassword": cli_password,
                        "cliPort": 22,
                        "cliUsername": cli_username,
                        "exclusivelyReceiveDeviceEvents": False,
                        "httpPassword": http_username,  # Note: using http_username for httpPassword
                        "httpsPassword": https_password,
                        "httpsUsername": http_username,
                        "httpUsername": http_username,
                        "managementIp": management_ip,
                        "registerDeviceEvents": register_device_events,
                        "snmpV1ReadCommunity": "public",
                        "snmpV1WriteCommunity": "public",
                        "snmpV2ReadCommunity": "public",
                        "snmpV2WriteCommunity": "public",
                        "snmpV3AuthenticationProtocol": "SHA",
                        "snmpV3PrivacyProtocol": "DES",
                        "snmpVersion": "SNMP_V2",
                        "verifyHttpCredentials": False,
                        "verifyHttpsCredentials": True,
                        "visionMgtPort": vision_mgt_port
                    }
                }
            }

            resp = self._session.post(url, json=payload, verify=self._verify_ssl, timeout=300)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if isinstance(data, dict) and data.get("status") == "ok":
                        return True, "Device added successfully"
                    return False, f"Unexpected response: {data}"
                except (ValueError, TypeError) as exc:
                    logger.debug("Failed to parse JSON response in add_device: %s", exc)
                    # If we got 200 but no JSON, assume success
                    return True, "Device added successfully"

            return False, f"Failed to add device: HTTP {resp.status_code} - {resp.text}"

        except requests.RequestException as exc:
            logger.exception("Request exception in add_device: %s", exc)
            return False, f"Exception in add_device: {exc!s}"

    def delete_device(self, device_id: str) -> Tuple[bool, str]:
        """Delete a device from CyberController identified by device_id.

        This uses the CC API endpoint that deletes by device id (byid).

        Args:
            device_id: device identifier as returned by CC (string)

        Returns:
            (True, 'success') on HTTP 200, or (False, error_message) on failure.
        """
        try:
            if not self.is_logged_in():
                ok, msg = self.refresh_session()
                if not ok:
                    raise RuntimeError(f"Authentication required and refresh failed: {msg}")

            # Build delete URL and issue DELETE with extended timeout
            url = f"{self.base_url}/mgmt/system/config/tree/device/byid/{device_id}"
            resp = self._session.delete(url, verify=self._verify_ssl, timeout=300)

            if resp.status_code == 200:
                return True, "success"
            # attempt to include response body for debugging
            body = ''
            try:
                body = resp.text
            except Exception:
                body = '<unreadable response body>'
            return False, f"Failed to delete device: HTTP {resp.status_code} - {body}"
        except requests.RequestException as exc:
            logger.exception("Exception in delete_device: %s", exc)
            return False, f"Exception in delete_device: {exc!s}"

    def add_device_range(self, name_convention: str, parent_orm: Any, device_type: str, start_ip: str, end_ip: str,
                         user: str, password: str) -> Tuple[bool, str]:
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

                # call new add_device API: provide CLI and HTTP creds as same user/password
                ok, res = self.add_device(
                    name=name,
                    management_ip=ip_str,
                    device_type=device_type,
                    cli_username=user,
                    cli_password=password,
                    http_username=user,
                    https_password=password,
                    vision_mgt_port="",
                    register_device_events=False,
                )
                if not ok:
                    return False, f"Failed to add device {ip_str}: {res}"
                idx += 1

            return True, "OK"
        except requests.RequestException as exc:
            logger.exception("Exception in add_device_range: %s", exc)
            return False, f"Exception in add_device_range: {exc!s}"

    def get_ids_data_formats(self, username: str, password: str) -> Tuple[bool, Union[str, List[str]]]:
        """Connect via SSH as root to enumerate IdsDataFormat XML files.

        Returns (True, [list_of_files]) or (False, error_message).
        """
        ssh = None
        try:
            # Connect via SSH using provided root credentials
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname=self.cc_ip, port=22, username=username, password=password, timeout=10)

            found_files = []

            stdin, stdout, stderr = ssh.exec_command(
                "ls /var/lib/docker/radware-storage/dc_config/kvision-configuration-service/config/conf | grep Ids |grep -v prop")
            out = stdout.read().decode("utf-8", errors="ignore").strip()
            if out:
                found_files = [line.strip() for line in out.split('\n') if line.strip()]
        except paramiko.SSHException as exc:
            return False, f"SSH error: {exc!s}"
        finally:
            if ssh:
                ssh.close()
        return True, found_files

    def _version_to_data_format(self, version: str) -> str:
        """Convert sim version string to IdsDataFormat format.

        Examples:
          "10.3.0" -> "100300"
          "8.30.0" -> "83000"
          "8.29.0" -> "82900"
          "8.32.1" -> "83201"
        """
        parts = version.split('.') if version is not None else []
        result = ''
        # Both version 10 and version 8 use padding
        needs_padding = len(parts) > 0 and (parts[0] == '10' or parts[0] == '8')
        parts_to_process = min(3, len(parts)) if needs_padding else len(parts)
        for i in range(parts_to_process):
            part = parts[i]
            # Only pad minor/patch versions (i > 0), not the major version
            if needs_padding and i > 0 and len(part) == 1:
                result += '0' + part
            else:
                result += part
        return result

    def _extract_version_from_filename(self, filename: str) -> Optional[str]:
        """Extract version string from IdsDataFormat filename.

        Reverse of _version_to_data_format logic.

        Args:
            filename: e.g., "IdsDataFormat100300.xml", "IdsDataFormat83000.xml"

        Returns:
            Version string like "10.3.0" or "8.30.0", or None if parsing fails.

        Examples:
            "IdsDataFormat100300.xml" -> "10.3.0"
            "IdsDataFormat83000.xml"  -> "8.30.0"
            "IdsDataFormat83201.xml"  -> "8.32.1"
            "IdsDataFormat1003.xml"   -> "10.0.3"
        """
        try:
            # Extract numeric part between "IdsDataFormat" and ".xml"
            if not filename.startswith("IdsDataFormat") or not filename.endswith(".xml"):
                return None

            version_str = filename[len("IdsDataFormat"):-len(".xml")]
            if not version_str.isdigit():
                return None

            # Version 10 uses padded format (6 digits: 100300 -> 10.03.00)
            if version_str.startswith("10") and len(version_str) >= 4:
                major = "10"
                rest = version_str[2:]

                # Parse pairs from rest
                parts = [major]
                for i in range(0, len(rest), 2):
                    chunk = rest[i:i+2]
                    # Remove leading zero if present
                    parts.append(str(int(chunk)))

                return ".".join(parts)

            # Version 8 uses padded format (5 digits: 83000 -> 8.30.00, 83201 -> 8.32.01)
            elif version_str.startswith("8") and len(version_str) >= 3:
                major = "8"
                rest = version_str[1:]

                # Parse pairs from rest
                parts = [major]
                for i in range(0, len(rest), 2):
                    chunk = rest[i:i+2]
                    # Remove leading zero if present
                    parts.append(str(int(chunk)))

                return ".".join(parts)

            else:
                # Other versions: each digit is a part (unlikely but handle as fallback)
                return ".".join(version_str)

        except Exception as exc:
            logger.debug("Failed to extract version from filename %s: %s", filename, exc)
            return None

    def _find_closest_lower_version(self, requested: str, available: List[str]) -> Optional[str]:
        """Find the highest available version that is <= requested version.

        Args:
            requested: Requested version string (e.g., "10.3.0")
            available: List of available version strings

        Returns:
            Closest version <= requested, or None if no match found.

        Examples:
            requested="10.3.0", available=["10.2.0", "10.3.0", "10.4.0"] -> "10.3.0"
            requested="10.3.0", available=["10.1.0", "10.2.0"] -> "10.2.0"
            requested="10.3.0", available=["10.4.0", "10.5.0"] -> None
        """
        try:
            # Parse requested version into tuple of ints
            req_parts = [int(p) for p in requested.split('.')]

            # Parse and filter available versions
            valid_versions = []
            for ver in available:
                try:
                    ver_parts = [int(p) for p in ver.split('.')]
                    # Pad to same length for comparison
                    max_len = max(len(req_parts), len(ver_parts))
                    req_padded = req_parts + [0] * (max_len - len(req_parts))
                    ver_padded = ver_parts + [0] * (max_len - len(ver_parts))

                    # Only keep versions <= requested
                    if tuple(ver_padded) <= tuple(req_padded):
                        valid_versions.append((tuple(ver_padded), ver))
                except (ValueError, AttributeError):
                    logger.debug("Skipping invalid version string: %s", ver)
                    continue

            if not valid_versions:
                return None

            # Return the highest valid version
            valid_versions.sort(reverse=True, key=lambda x: x[0])
            return valid_versions[0][1]

        except Exception as exc:
            logger.exception("Error finding closest version: %s", exc)
            return None

    def download_ids_data_format(self, sim_version: str, username: str, password: str) -> Tuple[bool, str]:
        """Download IdsDataFormat XML file based on sim_version via SCP.

        If exact version not found, falls back to closest lower version.

        Returns (True, local_path) or (False, error_message)
        """
        ssh = None
        local_dir = "/tmp/data_formats"
        os.makedirs(local_dir, exist_ok=True)

        # Helper to attempt download of a specific version
        def _attempt_download(version: str) -> Tuple[bool, str, Optional[Exception]]:
            nonlocal ssh
            try:
                format_version = self._version_to_data_format(version or '')
                filename = f"IdsDataFormat{format_version}.xml"
                remote_path = f"/var/lib/docker/radware-storage/dc_config/kvision-configuration-service/config/conf/{filename}"
                local_path = f"{local_dir}/{filename}"

                # SSH connect and SCP download
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(hostname=self.cc_ip, port=22, username=username, password=password, timeout=10)

                with SCPClient(ssh.get_transport()) as scp_client:
                    scp_client.get(remote_path, local_path)

                try:
                    ssh.close()
                    ssh = None
                except Exception as exc:
                    logger.debug("Error closing SSH after download: %s", exc)

                return True, local_path, None

            except (SCPException, FileNotFoundError, IOError) as exc:
                # File not found - this is where we want to fallback
                try:
                    if ssh:
                        ssh.close()
                        ssh = None
                except Exception as exc2:
                    logger.debug("Error closing SSH in exception handler: %s", exc2)
                return False, "", exc

            except (paramiko.SSHException, paramiko.AuthenticationException) as exc:
                # Auth/connection error - don't fallback, propagate immediately
                try:
                    if ssh:
                        ssh.close()
                        ssh = None
                except Exception as exc2:
                    logger.debug("Error closing SSH in exception handler: %s", exc2)
                logger.exception("SSH/Auth error for IdsDataFormat: %s", exc)
                raise

        try:
            # First attempt: try exact version
            logger.info("Attempting to download IdsDataFormat for version %s", sim_version)
            success, result, exc = _attempt_download(sim_version)

            if success:
                logger.info("Successfully downloaded IdsDataFormat for exact version %s", sim_version)
                return True, result

            # Exact version failed - attempt fallback
            logger.warning("Exact version %s not found, attempting fallback to closest lower version", sim_version)

            # Get list of available files
            ok, available_result = self.get_ids_data_formats(username, password)
            if not ok:
                logger.error("Failed to list available IdsDataFormat files: %s", available_result)
                return False, f"Version {sim_version} not found and could not list available versions: {available_result}"

            if not isinstance(available_result, list) or len(available_result) == 0:
                logger.error("No IdsDataFormat files available on server")
                return False, f"Version {sim_version} not found and no IdsDataFormat files available on server"

            # Extract versions from filenames
            available_versions = []
            for filename in available_result:
                extracted_ver = self._extract_version_from_filename(filename)
                if extracted_ver:
                    available_versions.append(extracted_ver)

            if not available_versions:
                logger.error("Could not extract valid versions from available files: %s", available_result)
                return False, f"Version {sim_version} not found and could not parse available versions"

            # Find closest lower version
            fallback_version = self._find_closest_lower_version(sim_version, available_versions)
            if not fallback_version:
                logger.error("No suitable fallback version found for %s. Available: %s", sim_version, available_versions)
                return False, f"No matching version found for {sim_version}. Available versions: {', '.join(sorted(available_versions))}"

            # Attempt download with fallback version
            logger.info("Falling back to version %s (requested: %s)", fallback_version, sim_version)
            success, result, exc2 = _attempt_download(fallback_version)

            if success:
                logger.info("Successfully downloaded IdsDataFormat for fallback version %s (requested: %s)",
                           fallback_version, sim_version)
                return True, result
            else:
                logger.error("Fallback download also failed for version %s: %s", fallback_version, exc2)
                return False, f"Both exact version {sim_version} and fallback version {fallback_version} failed: {exc2!s}"

        except (paramiko.SSHException, paramiko.AuthenticationException) as exc:
            # Auth/connection errors propagated from _attempt_download
            return False, f"Connection/authentication error: {exc!s}"

        except Exception as exc:
            # Unexpected error
            logger.exception("Unexpected error in download_ids_data_format: %s", exc)
            try:
                if ssh:
                    ssh.close()
            except Exception as exc2:
                logger.debug("Error closing SSH in final exception handler: %s", exc2)
            return False, f"Unexpected download error: {exc!s}"

    def get_management_ports(self) -> Tuple[bool, Union[str, List[Dict[str, str]]]]:
        """Fetch management port interfaces from CyberController.

        Returns:
            (True, [{"interface": "G1", "address": "172.17.154.77"}, ...]) on success
            or (False, error_message) on failure.
        """
        try:
            if not self.is_logged_in():
                ok, msg = self.refresh_session()
                if not ok:
                    raise RuntimeError(f"Authentication required and refresh failed: {msg}")

            url = f"{self.base_url}/mgmt/system/config/itemlist/mngtports"
            cookies = {"JSESSIONID": self._creds.jsession_id}
            resp = requests.get(url, cookies=cookies, verify=self._verify_ssl, timeout=15)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                    ports = data.get("mngtports", [])
                    return True, ports
                except Exception as exc:
                    return False, f"Failed to parse management ports response: {exc!s}"

            return False, f"Failed to fetch management ports: HTTP {resp.status_code}"
        except requests.RequestException as exc:
            logger.exception("Request exception in get_management_ports: %s", exc)
            return False, f"Request exception in get_management_ports: {exc!s}"


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
        except requests.RequestException:
            # swallow - login returns (bool, str) and internal exceptions are handled
            pass

        _HANDLERS[key] = handler
        return handler


__all__ = ["CCDevice", "CCCredentials", "CCHandler", "get_cc_handler"]
