from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from typing import Optional, Tuple

# removed devices_templates import (DB-only templates now)
from backend.app.modules.sapro.src import (
    saproCommunication,
    saproMapFunctions,
    saproDeviceFunctions,
    saproFileFunctions,
)
from backend.app.modules.sapro.src.returnTypes.enums import DeviceStatus
from backend.app.modules.sapro.src.returnTypes.models import SaproDevice
from backend.app.modules.sapro.src.saproException import SaproException
from backend.app.utils.config import settings
from backend.app.utils.logger import logger
from backend.app.utils.sapro_ssh import get_sapro_ssh_client
from backend.app.utils.snmp import SnmpClient


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
        """Get all devices from all running maps using SSH commands.

        New flow:
        1. Get all maps and their status via wspstats
        2. For each running map, execute devlist command to get devices
        3. Query device type/version via SNMP (parallelized)

        Returns:
            List of SaproDevice objects with IP, map, status, type, version
        """
        import time

        start_time = time.time()

        # Step 1: Get all maps with status
        try:
            all_maps = self.get_all_maps()
        except Exception as e:
            logger.error(f"Failed to get map list: {e}")
            return []

        # Filter only running maps
        running_maps = [m for m in all_maps if m['status'] == 'running']
        logger.info(f"Found {len(running_maps)} running maps out of {len(all_maps)} total maps")

        # Step 2: Get device list from each running map via SSH
        ssh_client = get_sapro_ssh_client()
        device_tasks = []

        for map_info in running_maps:
            map_name = map_info['name']
            cmd = f"/opt/sapro/bin/sapcnsl -m /opt/sapro/map/{map_name}.map -c devlist"

            try:
                logger.debug(f"Executing devlist for map {map_name}")
                success, output = ssh_client.execute_command(cmd, check_stderr=False)

                if not success:
                    logger.error(f"Failed to get device list for map {map_name}: {output}")
                    continue

                # Parse devlist output
                lines = output.split('\n')
                in_table = False

                for line in lines:
                    # Skip header separators
                    if line.strip().startswith('---'):
                        in_table = True
                        continue

                    # Stop at footer separator
                    if in_table and line.strip().startswith('---'):
                        break

                    # Skip non-table lines
                    if not in_table or not line.strip():
                        continue

                    # Parse: "Device Name              Status"
                    parts = line.split()
                    if not parts:
                        continue

                    # First part is device name (e.g., "50.50.180.1//161")
                    device_name = parts[0]

                    if device_name == "Device":
                        # Skip header line if present
                        continue

                    # Extract IP (strip //port suffix)
                    if '//' in device_name:
                        device_ip = device_name.split('//')[0]
                    else:
                        device_ip = device_name

                    # Determine status from second column if present
                    # Parse status character and map to numeric code
                    # DeviceStatus mapping: 1=' ', 2='*', 3='R', 4='F', 5='D', 6='S'
                    status_char = parts[1] if len(parts) > 1 else ''

                    # Map SSH status character to numeric code
                    if status_char == 'R':
                        status_code = 3  # OK (running)
                    elif status_char == '*':
                        status_code = 2  # LOADING
                    elif status_char == 'F':
                        status_code = 4  # FAILED
                    elif status_char == 'D':
                        status_code = 5  # DISABLED
                    elif status_char == 'S':
                        status_code = 6  # STOPPING
                    else:
                        status_code = 1  # SHUTDOWN (empty/space)

                    device_tasks.append((device_ip, map_name, status_code))

            except Exception as e:
                logger.error(f"Failed to process devlist for map {map_name}: {e}")
                continue

        logger.info(f"Found {len(device_tasks)} total devices from {len(running_maps)} running maps")

        # Step 3: Query device type/version via SNMP (parallel)
        devices: List[SaproDevice] = []
        snmp_start = time.time()

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
                        type=device_type or "",
                        version=device_version or ""
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

        snmp_end = time.time()
        logger.info(f"SNMP queries completed in {snmp_end - snmp_start:.2f} seconds for {len(devices)} devices")
        logger.info(f"get_all_devices completed in {time.time() - start_time:.2f} seconds")

        return devices

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

    def get_all_maps(self) -> List[Dict[str, str]]:
        """Get list of all available maps from Sapro workspace with their status.

        Executes SSH command: /opt/sapro/bin/sapcnsl -w /opt/sapro/wsp/default.wsp -c wspstats
        Parses the table output to extract map names and running status.

        Returns:
            List of dicts with:
            - name: Map name (without .map extension and /opt/sapro/map/ prefix)
            - status: "running" if R in Status column, "" (empty) if stopped, "error" otherwise
        """
        cmd = "/opt/sapro/bin/sapcnsl -w /opt/sapro/wsp/default.wsp -c wspstats"

        try:
            ssh_client = get_sapro_ssh_client()
            logger.debug(f"Executing wspstats command via SSH: {cmd}")

            success, output = ssh_client.execute_command(cmd, check_stderr=False)

            if not success:
                raise Exception(f"SSH command failed: {output}")

            # Parse the table output
            result: List[Dict[str, str]] = []
            lines = output.split('\n')

            # Find where the table data starts (after "Status    Port #    Map Name" header)
            in_table = False
            for line in lines:
                # Skip header separators (lines with only dashes)
                if line.strip().startswith('---'):
                    in_table = True
                    continue

                # Stop at footer separator
                if in_table and line.strip().startswith('---'):
                    break

                # Skip non-table lines
                if not in_table or not line.strip():
                    continue

                # Parse table row: "Status    Port #    Map Name"
                # Status is first column (1 char: R or empty)
                # Map name is last part after port number

                parts = line.split()
                if not parts:
                    continue

                # Determine status from first column
                status_char = line[0] if len(line) > 0 else ' '

                # Find map name (last element, should contain /opt/sapro/map/)
                map_path = None
                for part in reversed(parts):
                    if '/opt/sapro/map/' in part:
                        map_path = part
                        break

                if not map_path:
                    continue

                # Extract map name (remove path and extension)
                map_name = map_path.split('/')[-1]
                if map_name.endswith('.map'):
                    map_name = map_name[:-4]

                # Determine status
                if status_char == 'R':
                    status = "running"
                elif status_char == ' ':
                    status = ""  # stopped
                else:
                    status = "error"

                result.append({'name': map_name, 'status': status})

            logger.info(f"Retrieved {len(result)} maps from workspace")
            return result

        except Exception as e:
            logger.error(f"Failed to get map list via wspstats: {e}", exc_info=True)
            raise Exception(f"Failed to get map list: {e}")

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

    def start_map_and_wait(self, map_name: str) -> Tuple[bool, str]:
        """Start a map and wait until it's running.

        Executes async start command, then polls status every 2 seconds.
        Timeout: 5 minutes (300 seconds).

        Args:
            map_name: Map name (without .map extension)

        Returns:
            (success, message)
        """
        import time

        map_path = f"/opt/sapro/map/{map_name}.map"
        cmd = f"/opt/sapro/bin/sapcnsl -m {map_path} -c start"

        try:
            ssh_client = get_sapro_ssh_client()
            logger.info(f"Starting map {map_name}")

            # Execute start command (async - returns immediately)
            success, output = ssh_client.execute_command(cmd, check_stderr=False)

            if not success:
                return False, f"Failed to start map: {output}"

            # Check for success message
            if "Started sathrd process for map successfully" not in output:
                return False, f"Unexpected start output: {output}"

            # Poll status every 2 seconds for up to 5 minutes
            timeout = 300  # 5 minutes
            poll_interval = 2  # seconds
            elapsed = 0

            logger.info(f"Polling map {map_name} status until running...")

            while elapsed < timeout:
                time.sleep(poll_interval)
                elapsed += poll_interval

                # Get current map status
                maps = self.get_all_maps()
                map_status = next((m for m in maps if m['name'] == map_name), None)

                if map_status and map_status['status'] == 'running':
                    logger.info(f"Map {map_name} is now running (took {elapsed}s)")
                    return True, f"Map {map_name} started successfully"

                logger.debug(f"Map {map_name} status: {map_status['status'] if map_status else 'not found'}, elapsed: {elapsed}s")

            # Timeout reached
            return False, f"Timeout waiting for map {map_name} to start (5 minutes)"

        except Exception as e:
            logger.error(f"Failed to start map {map_name}: {e}", exc_info=True)
            return False, f"Failed to start map: {e}"

    def stop_map_and_wait(self, map_name: str) -> Tuple[bool, str]:
        """Stop a map and wait until terminated.

        Executes synchronous stop command that blocks until termination.
        Timeout: 5 minutes.

        Args:
            map_name: Map name (without .map extension)

        Returns:

        (success, message)
        """
        map_path = f"/opt/sapro/map/{map_name}.map"
        cmd = f"/opt/sapro/bin/sapcnsl -m {map_path} -c stop"

        try:
            ssh_client = get_sapro_ssh_client()
            logger.info(f"Stopping map {map_name}")

            # Execute stop command with extended timeout (sync - blocks until done)
            # Use 320 seconds (5 min + 20s buffer) to allow for 5-minute map termination
            success, output = ssh_client.execute_command(cmd, check_stderr=False, timeout=320)

            if not success:
                return False, f"Failed to stop map: {output}"

            # Check for termination message
            if "PACKET_EVALUATED: Map terminated" in output:
                logger.info(f"Map {map_name} stopped successfully")
                return True, f"Map {map_name} stopped successfully"

            # Check for other possible success indicators
            if "terminated" in output.lower() or "stopped" in output.lower():
                logger.info(f"Map {map_name} stopped (alternate message): {output}")
                return True, f"Map {map_name} stopped successfully"

            # Unexpected output
            return False, f"Unexpected stop output: {output}"

        except Exception as e:
            logger.error(f"Failed to stop map {map_name}: {e}", exc_info=True)
            return False, f"Failed to stop map: {e}"

    # create_map and delete_map methods were removed. Map creation/deletion is not provided
    # by this handler anymore. Use higher-level APIs or tools to manage map files if needed.

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
        """Start one or more devices listed in a map using SSH commands.

        Args:
            map_name: Map path or name
            devices_names: List of device names/IPs to start

        Returns:
            (success, combined_messages)
        """
        try:
            ssh_client = get_sapro_ssh_client()
            messages = []

            for device_ip in devices_names:
                # Normalize map name (ensure .map extension)
                if not map_name.endswith('.map'):
                    map_full = f"{map_name}.map"
                else:
                    map_full = map_name

                # Build SSH command
                cmd = f"/opt/sapro/bin/sapcnsl -p {self.sapro_port} -m {map_full} -c startdev -d {device_ip}"

                logger.debug(f"Executing start device command via SSH: {cmd}")
                success, output = ssh_client.execute_command(cmd, check_stderr=False)

                if not success:
                    messages.append(f"Failed to start {device_ip}: {output}")
                else:
                    messages.append(f"Started {device_ip}: {output}" if output else f"Started {device_ip}")

            # Return success if all devices started successfully
            all_success = all("Failed" not in msg for msg in messages)
            return all_success, "\n".join(messages)

        except Exception as e:
            logger.error(f"Failed to start device(s) from map {map_name}: {e}", exc_info=True)
            return False, f"Failed to start device(s): {e}"

    def stop_devices_from_map(self, map_name: str, devices_names: list) -> Tuple[bool, str]:
        """Stop one or more devices listed in a map using SSH commands.

        Args:
            map_name: Map path or name
            devices_names: List of device names/IPs to stop

        Returns:
            (success, combined_messages)
        """
        try:
            ssh_client = get_sapro_ssh_client()
            messages = []

            for device_ip in devices_names:
                # Normalize map name (ensure .map extension)
                if not map_name.endswith('.map'):
                    map_full = f"{map_name}.map"
                else:
                    map_full = map_name

                # Build SSH command
                cmd = f"/opt/sapro/bin/sapcnsl -p {self.sapro_port} -m {map_full} -c stopdev -d {device_ip}"

                logger.debug(f"Executing stop device command via SSH: {cmd}")
                success, output = ssh_client.execute_command(cmd, check_stderr=False)

                if not success:
                    messages.append(f"Failed to stop {device_ip}: {output}")
                else:
                    messages.append(f"Stopped {device_ip}: {output}" if output else f"Stopped {device_ip}")

            # Return success if all devices stopped successfully
            all_success = all("Failed" not in msg for msg in messages)
            return all_success, "\n".join(messages)

        except Exception as e:
            logger.error(f"Failed to stop device(s) from map {map_name}: {e}", exc_info=True)
            return False, f"Failed to stop device(s): {e}"

    def create_device(self, device_ip: str, raw_xml_content: str, map_name: str) -> Tuple[bool, str]:
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
            map_path = self.get_full_map_path(map_name)

            started_ok, start_msg = self.start_map(map_path)
            if not started_ok:
                # still attempt to proceed only if map is "already running"
                if "already running" not in start_msg:
                    return False, start_msg

            # Inline FindDevice call to avoid static-analysis unresolved-attribute warning
            found = saproDeviceFunctions.FindDevice(self._sapro, device_ip)
            if found:
                # start the device
                devices_list = [device_ip]
                ok, msg = self.start_devices_from_map(map_path, devices_list)
                if ok:
                    return True, f"Simulator {device_ip} already exists and was started"
                return False, f"Simulator {device_ip} already exists but failed to start: {msg}"

            # create device file path
            new_device_file_path = f"{self.map_directory}{map_name}/{device_ip}.map"

            # use raw XML content directly
            device_file_content = raw_xml_content.strip()

            ok, msg = self.create_device_file_on_server(new_device_file_path, device_file_content)
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
        # Normalize map_full_name: if provided map_name already looks like a path or endswith .map use it,
        # otherwise resolve against configured map directory.
        if map_name.endswith('.map') or '/' in map_name:
            map_full_name = map_name
        else:
            map_full_name = self.get_full_map_path(map_name)

        # 1) Stop device first (keep existing behavior)
        try:
            saproDeviceFunctions.SendStopCmdToDevice(self._sapro, map_full_name, device_ip)
        except Exception as e:
            # Log but continue to attempt deletion via SSH
            logger.debug("Stopping device before delete raised: %s", e)

        # 2) Execute remote sapcnsl delete command over SSH on the Sapro server using centralized SSH client
        cmd = f"/opt/sapro/bin/sapcnsl -p {self.sapro_port} -m {map_full_name} -c deldev -d {device_ip}"

        try:
            ssh_client = get_sapro_ssh_client()
            logger.debug(f"Executing delete command via SSH: {cmd}")

            # Use centralized SSH client with connection pooling
            success, output = ssh_client.execute_command(cmd, check_stderr=False)

            if not success:
                return False, f"SSH delete command failed: {output}"

            # Analyze output to determine success
            out_l = output.lower()

            if ('deleted' in out_l) or ('success' in out_l) or ('error' not in out_l and output):
                return True, output or "Device deleted successfully"

            # Fallback: if no clear error indicators, consider success
            if output and 'error' not in out_l:
                return True, output

            return False, f"Unexpected delete output: {output}"

        except Exception as exc:
            logger.error(f"Failed to execute SSH delete command: {exc}", exc_info=True)
            return False, f"Failed to execute SSH delete command: {exc}"


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
