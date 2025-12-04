from typing import List
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.app.modules.sapro.devices_templates import get_template_by_name
from backend.app.modules.sapro.src import (
    saproCommunication,
    saproMapFunctions,
    saproDeviceFunctions,
    saproFileFunctions,
)
from backend.app.modules.sapro.src.returnTypes.enums import DeviceStatus
from backend.app.modules.sapro.src.returnTypes.models import SaproDevice
from backend.app.modules.sapro.src.saproDeviceFunctions import GetDeviceListOfMap
from backend.app.modules.sapro.src.saproException import SaproException
from backend.app.modules.sapro.src.saproMapFunctions import getMapListFromServer
from backend.app.utils.config import settings
from backend.app.utils.snmp import SnmpClient
from backend.app.utils.logger import logger


class SaproCommunicationHandler:
    """Instance-based handler for communicating with the Sapro server.

    This class wraps the lower-level `sapro` ProductLibraries module and exposes
    small helper methods suitable for dependency-injection in FastAPI.
    """

    def __init__(self, sapro_ip: str, sapro_port: int, map_directory: str):
        """Initialize handler state and the underlying SaproCommunication object.

        Args:
            sapro_ip: IP address of the sapro server.
            sapro_port: Port of the sapro server.
            map_directory: Directory on the sapro server where maps live (should end with '/').
        """
        self.sapro_ip = sapro_ip
        self.sapro_port = int(sapro_port)
        self.map_directory = map_directory or "/opt/sapro/map/"
        self._sapro: Optional[saproCommunication.SaproCommunication] = saproCommunication.SaproCommunication()
        # configure the underlying object similar to previous implementation
        try:
            # these attributes are used by the src functions
            self._sapro.serverIP = self.sapro_ip
            self._sapro.serverPort = int(self.sapro_port)
        except SaproException:
            # Defensive - if attributes are not present, ignore and rely on initConnection
            pass
        self._is_connected: bool = False

    def init_connection(self) -> Tuple[bool, str]:
        """Open connection to the Sapro server.

        Returns:
            (success, message)
        """
        try:
            # src expects initialization via initConnection(serverIP, serverPort)
            self._sapro.initConnection(self.sapro_ip, int(self.sapro_port))
            self._is_connected = True
            return True, "Connected to Sapro"
        except SaproException as e:
            # Normalize exception message
            msg = getattr(e, "toString", lambda: str(e))()
            return False, f"Failed to connect to sapro: {msg}"
        except Exception as e:  # catch-all for unexpected issues
            return False, f"Failed to connect to sapro: {str(e)}"

    def close_connection(self) -> Tuple[bool, str]:
        """Close connection to the Sapro server.

        Returns:
            (success, message)
        """
        try:
            self._sapro.closeConnection()
            self._is_connected = False
            return True, "Disconnected from Sapro"
        except SaproException as e:
            msg = getattr(e, "toString", lambda: str(e))()
            return False, f"Failed to disconnect from sapro: {msg}"
        except Exception as e:
            return False, f"Failed to disconnect from sapro: {str(e)}"

    def is_connected(self) -> bool:
        """Return whether the handler currently has an open connection.

        Returns:
            True if connected, False otherwise.
        """
        return bool(self._is_connected)

    def get_all_devices(self) -> List[SaproDevice]:
        devices = []
        all_maps = getMapListFromServer(self._sapro)

        # Collect all devices first
        device_tasks = []
        for sim_map in all_maps:
            map_name = sim_map.mapName.split("/")[-1].replace(".map", "")
            devices_from_map = GetDeviceListOfMap(self._sapro, sim_map.mapPort)

            for device in devices_from_map:
                device_tasks.append((device.devName, map_name, device.devStatus))

        # Query all devices in parallel (max 20 concurrent queries)
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_device = {
                executor.submit(self.snmp_get_device_info, dev_ip): (dev_ip, map_name, status)
                for dev_ip, map_name, status in device_tasks
            }

            for future in as_completed(future_to_device):
                dev_ip, map_name, status = future_to_device[future]
                try:
                    device_type, device_version = future.result()
                    devices.append(SaproDevice(
                        ip_address=dev_ip,
                        map=map_name,
                        status=DeviceStatus.get_status(status),
                        type=device_type,
                        version=device_version
                    ))
                except Exception as e:
                    logger.error(f"Failed to query device {dev_ip}: {e}")
                    devices.append(SaproDevice(
                        ip_address=dev_ip,
                        map=map_name,
                        status=DeviceStatus.get_status(status),
                        type="",
                        version=""
                    ))

        return devices

    # def snmp_get_device_info(self, device_map: str, device_ip: str) -> Tuple[Optional[str], Optional[str]]:
    #     """Retrieve device type and version via SNMP.
    #
    #     Args:
    #         device_map: Map name where the device is located.
    #         device_ip: IP address of the device."""
    #
    #     device_type_response = SendTclCmdToDevice(self._sapro, device_map + ".map", device_ip, "SA_getvar { sysDescr.0 }")
    #     device_type = ""
    #     if "DefensePro" in device_type_response:
    #         version_response = SendTclCmdToDevice(self._sapro, device_map + ".map", device_ip,
    #                                               "SA_getvar { rndApsoluteOSVersion.0 }")
    #         version = version_response.split(":")[1][:-1]
    #         device_type = "DefensePro"
    #     elif "Application" in device_type_response:
    #         version = SendTclCmdToDevice(self._sapro, device_map + ".map", device_ip,
    #                                               "SA_getvar { agSoftwareVersion.0 }")
    #         device_type = "Alteon"
    #     else:
    #         device_type = None
    #         version = None
    #
    #     return device_type, version

    def snmp_get_device_info(self, device_ip: str) -> Tuple[Optional[str], Optional[str]]:
        """Retrieve device type and version via SNMP."""
        logger.debug(f"snmp_get_device_info called for {device_ip}")

        if settings.ENVIRONMENT == "development":
            logger.debug(f"Development mode - returning mock values for {device_ip}")
            return "DefensePro", "10.6.0.0"

        try:
            logger.debug(f"Creating SNMP client for {device_ip}")
            snmp_client = SnmpClient(device_ip)

            logger.debug(f"Querying device type OID for {device_ip}")
            device_type = snmp_client.get("1.3.6.1.2.1.1.1.0")
            logger.debug(f"Device type query result for {device_ip}: {device_type}")

            if device_type and "DefensePro" in device_type:
                logger.debug(f"DefensePro detected for {device_ip}, querying version")
                version = snmp_client.get("1.3.6.1.4.1.89.2.13.0")
                logger.debug(f"Version query result for {device_ip}: {version}")
                if version and ":" in version:
                    version = version.split(":")[1].strip()
                device_type = "DefensePro"
                logger.info(f"Device {device_ip}: DefensePro {version}")
                return device_type, version

            elif device_type and "Application" in device_type:
                logger.debug(f"Alteon detected for {device_ip}, querying version")
                version = snmp_client.get("1.3.6.1.4.1.1872.2.5.1.1.1.10.0")
                logger.debug(f"Version query result for {device_ip}: {version}")
                device_type = "Alteon"
                logger.info(f"Device {device_ip}: Alteon {version}")
                return device_type, version

            else:
                logger.warning(f"Unrecognized device type for {device_ip}: {device_type}")
                return None, None

        except Exception as e:
            logger.error(f"SNMP query failed for {device_ip}: {type(e).__name__}: {e}")
            return None, None

    def get_map_by_type(self, device_type: str) -> Optional[str]:
        """Return the map name for a given device type.

        Args:
            device_type: The device type string (case-insensitive).

        Returns:
            Map name (string) when recognized, otherwise None.
        """
        if not device_type:
            return None
        t = device_type.lower()
        if "ipv6" in t:
            return "IPv6"
        if "alteon" in t:
            return "Alteons"
        if "defensepro" in t:
            return "DefensePros"
        if "lp" in t:
            return "LinkProofs"
        return None

    def get_full_map_path(self, map_name: str) -> str:
        """Return the full path to a map file on the sapro server.

        Args:
            map_name: The logical map name (without extension).

        Returns:
            Full path string (map_directory + map_name + ".map").
        """
        return f"{self.map_directory}{map_name}.map"

    def start_map(self, map_name: str) -> Tuple[bool, str]:
        """Start a map on the sapro server.

        Args:
            map_name: The map path or name expected by the underlying library.

        Returns:
            (success, message)
        """
        try:
            saproMapFunctions.SendStartCmdToMap(self._sapro, map_name)
            return True, f"Map {map_name} started"
        except SaproException as e:
            msg = getattr(e, "toString", lambda: str(e))()
            # keep same semantics as previous code for already running
            if "Map was already running" in msg:
                return True, f"Map {map_name} was already running"
            return False, f"Failed to start map {map_name}: {msg}"
        except Exception as e:
            return False, f"Failed to start map {map_name}: {str(e)}"

    def find_device(self, device_ip: str) -> bool:
        """Find a device in sapro by IP.

        Args:
            device_ip: IP string of the device to locate.

        Returns:
            (success, info_message) - on success info_message contains the device info repr.
        """
        try:
            dev = saproDeviceFunctions.FindDevice(self._sapro, device_ip)
            return dev
        except SaproException as e:
            msg = getattr(e, "toString", lambda: str(e))()
            raise f"Find device failed for {device_ip}: {msg}"

    def set_new_device_file(self, device_ip: str, device_template: str) -> Tuple[bool, str]:
        """Generate device file content for the given device type and IP.

        Returns:
            (success, device_file_content)
        """
        try:
            device_string = get_template_by_name(device_template)
            content = device_string.replace("<ip>", device_ip)
            return True, content
        except Exception as e:
            return False, f"Failed to build device file for {device_ip}: {str(e)}"

    def create_device_file_on_server(self, remote_file_path: str, device_file_data: str) -> Tuple[bool, str]:
        """Write a device file to the sapro server filesystem.

        Args:
            remote_file_path: Absolute path on the sapro server where the file should be written.
            device_file_data: Content to write.

        Returns:
            (success, message)
        """
        try:
            saproFileFunctions.WriteDataIntoFile(self._sapro, remote_file_path, device_file_data)
            return True, f"Device file written to {remote_file_path}"
        except SaproException as e:
            msg = getattr(e, "toString", lambda: str(e))()
            return False, f"Failed to create device file on server {remote_file_path}: {msg}"
        except Exception as e:
            return False, f"Failed to create device file on server {remote_file_path}: {str(e)}"

    def add_new_device(self, map_name: str, remote_file_path: str) -> Tuple[bool, str]:
        """Add a previously uploaded device file to the specified map.

        Args:
            map_name: Map path or name expected by underlying library.
            remote_file_path: Path to the device file on the sapro server filesystem.

        Returns:
            (success, message)
        """
        try:
            add_device_msg = saproMapFunctions.SendAddDevCmdToMap(self._sapro, map_name, remote_file_path)
            return True, str(add_device_msg)
        except SaproException as e:
            msg = getattr(e, "toString", lambda: str(e))()
            return False, f"Failed to add device to map {map_name}: {msg}"
        except Exception as e:
            return False, f"Failed to add device to map {map_name}: {str(e)}"

    def start_devices_from_map(self, map_name: str, devices_names: list) -> Tuple[bool, str]:
        """Start one or more devices listed in a map.

        Args:
            map_name: Map path or name.
            devices_names: Iterable of device names/IPs to start.

        Returns:
            (success, combined_messages)
        """
        try:
            messages = []
            for device in devices_names:
                msg = saproDeviceFunctions.SendStartCmdToDevice(self._sapro, map_name, device)
                messages.append(str(msg))
            return True, "\n".join(messages)
        except SaproException as e:
            msg = getattr(e, "toString", lambda: str(e))()
            return False, f"Failed to start device(s) from map {map_name}: {msg}"
        except Exception as e:
            return False, f"Failed to start device(s) from map {map_name}: {str(e)}"

    def stop_devices_from_map(self, map_name: str, devices_names: list) -> Tuple[bool, str]:
        """Stop one or more devices listed in a map.

        Returns:
            (success, message)
        """
        try:
            messages = []
            for device in devices_names:
                msg = saproDeviceFunctions.SendStopCmdToDevice(self._sapro, map_name, device)
                messages.append(str(msg))
            return True, "\n".join(messages)
        except SaproException as e:
            msg = getattr(e, "toString", lambda: str(e))()
            return False, f"Failed to stop device(s) from map {map_name}: {msg}"
        except Exception as e:
            return False, f"Failed to stop device(s) from map {map_name}: {str(e)}"

    def create_device(self, device_ip: str, device_type: str, template: str, sim_map=None) -> Tuple[bool, str]:
        """Create (or start existing) simulator device on the sapro server.

        Workflow:
        - Resolve map name by device type or get map from user
        - Ensure map is started
        - If device exists: start it
        - Otherwise: create device file, upload it, and add it to the map

        Returns:
            (success, message)
        """
        try:
            map_name = self.get_map_by_type(device_type) if not sim_map else sim_map
            if not map_name:
                return False, f"Map: {map_name} not found"
            map_path = self.get_full_map_path(map_name)

            started_ok, start_msg = self.start_map(map_path)
            if not started_ok:
                # still attempt to proceed only if map is "already running"
                if "already running" not in start_msg:
                    return False, start_msg

            found = self.find_device(device_ip)
            if found:
                # start the device
                devices_list = [device_ip]
                ok, msg = self.start_devices_from_map(map_path, devices_list)
                if ok:
                    return True, f"Simulator {device_ip} already exists and was started"
                return False, f"Simulator {device_ip} already exists but failed to start: {msg}"

            # create device file path and content
            new_device_file_path = f"{self.map_directory}{map_name}/{device_ip}.map"
            ok, content_or_msg = self.set_new_device_file(device_ip, template)
            if not ok:
                return False, content_or_msg

            ok, msg = self.create_device_file_on_server(new_device_file_path, content_or_msg)
            if not ok:
                return False, msg

            ok, msg = self.add_new_device(map_path, new_device_file_path)
            if not ok:
                return False, msg

            ok, msg = self.start_devices_from_map(map_path, [device_ip])
            if not ok:
                return False, f"Device {device_ip} added but failed to start: {msg}"

            return True, f"Device {device_ip} created and added to map {map_path}"
        except SaproException as e:
            msg = getattr(e, "toString", lambda: str(e))()
            return False, f"Failed to create device {device_ip}: {msg}"
        except Exception as e:
            return False, f"Failed to create device {device_ip}: {str(e)}"

    def delete_device(self, map_name: str, device_ip: str) -> Tuple[bool, str]:
        """Delete a device from the specified map.

        Args:
            map_name: Logical map name (without extension) or full path expected by the underlying library.
            device_ip: IP/name of the device to delete.

        Returns:
            (success, message)
        """
        try:
            map_path = self.get_full_map_path(map_name)
            reply = saproMapFunctions.SendDeleteDevCmdToMap(self._sapro, map_path, device_ip)
            return True, str(reply)
        except SaproException as e:
            msg = getattr(e, "toString", lambda: str(e))()
            return False, f"Failed to delete device {device_ip} from map {map_name}: {msg}"
        except Exception as e:
            return False, f"Failed to delete device {device_ip} from map {map_name}: {str(e)}"


# Module-level singleton factory
_sapro_handler: Optional[SaproCommunicationHandler] = None


def get_sapro_handler() -> SaproCommunicationHandler:
    """Return a singleton SaproCommunicationHandler.

    On first call the handler is created using configuration values from
    `backend.app.utils.config.settings` (attempts to read
    `SAPRO_IP`, `SAPRO_PORT`, `SAPRO_MAP_DIR`), and `init_connection()` is called.

    If settings are missing the function falls back to sensible defaults.
    """
    global _sapro_handler
    if _sapro_handler is None:
        sapro_ip = getattr(settings, "SAPRO_IP", "127.0.0.1")
        sapro_port = getattr(settings, "SAPRO_PORT", 2100)
        map_dir = getattr(settings, "SAPRO_MAP_DIR", "/opt/sapro/map/")
        handler = SaproCommunicationHandler(sapro_ip, int(sapro_port), map_dir)
        # attempt to initialize connection; ignore failures but keep handler available
        handler.init_connection()
        _sapro_handler = handler
    return _sapro_handler
