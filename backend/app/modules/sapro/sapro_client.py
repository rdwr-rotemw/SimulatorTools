import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from typing import Optional, Tuple

# removed devices_templates import (DB-only templates now)
from backend.app.modules.sapro.src import (
    saproCommunication,
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

    def get_all_devices(self, workspace: str) -> List[SaproDevice]:
        """Get all devices from all running maps using SSH commands.

        Returns empty list if workspace has no maps.

        New flow:
        1. Get all maps and their status via wspstats
        2. For each running map, execute devlist command to get devices
        3. Query device type/version via SNMP (parallelized)

        Returns:
            List of SaproDevice objects, or empty list if no maps/devices
        """

        start_time = time.time()

        # FIRST: Get all maps and check if empty
        try:
            all_maps = self.get_all_maps(workspace=workspace)
        except Exception as e:
            logger.error(f"Failed to get map list: {e}")
            return []

        if not all_maps:
            logger.warning(f"Workspace '{workspace}' has no maps defined. No devices to retrieve.")
            return []

        # Filter only running maps
        running_maps = [m for m in all_maps if m['status'] == 'running']
        logger.info(f"Found {len(running_maps)} running maps out of {len(all_maps)} total maps")

        # Step 2: Get device list from each running map via SSH
        ssh_client = get_sapro_ssh_client()
        device_tasks = []

        for map_info in running_maps:
            map_name = map_info['name']
            map_full_path = map_info['full_path']
            cmd = f"/opt/sapro/bin/sapcnsl -m {map_full_path} -c devlist"

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

    def get_all_maps(self, workspace: str = "default") -> List[Dict[str, str]]:
        """Get list of all available maps from specified Sapro workspace with their status.

        IMPORTANT: Check if workspace has any maps BEFORE running wspstats command,
        because wspstats HANGS if workspace file has no <Map> tags.

        Args:
            workspace: Workspace name (without .wsp extension). Defaults to "default".
                        Use "*" to query all workspaces and aggregate results.

        Returns:
            List of dicts with:
            - name: Map name (without .map extension and path)
            - status: "running" if R, "" if stopped, "error" otherwise
            - full_path: Full path to map file (from workspace file)
        """

        # Special case: aggregate all workspaces for superuser
        if workspace == "*":
            return self._get_all_maps_aggregated()

        try:
            ssh_client = get_sapro_ssh_client()
            workspace_path = f"/opt/sapro/wsp/{workspace}.wsp"

            # STEP 1: Read workspace file to check if it has any <Map> tags
            logger.debug(f"Reading workspace file: {workspace_path}")
            read_cmd = f"cat {workspace_path}"
            success, workspace_content = ssh_client.execute_command(read_cmd, check_stderr=False)

            if not success:
                raise Exception(f"Failed to read workspace file: {workspace_content}")

            # Check if workspace has any <Map> tags
            if '<Map' not in workspace_content:
                logger.info(f"Workspace '{workspace}' has no maps defined (no <Map> tags in file)")
                return []

            # STEP 2: Only run wspstats if workspace has maps
            cmd = f"/opt/sapro/bin/sapcnsl -w {workspace_path} -c wspstats"
            logger.debug(f"Executing wspstats command for workspace '{workspace}': {cmd}")

            success, output = ssh_client.execute_command(cmd, check_stderr=False)

            if not success:
                raise Exception(f"SSH command failed: {output}")

            # STEP 3: Parse the table output
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
                # Status is first column (1 char: R, space, or other)
                # Map Name is the full path like /opt/sapro/map/Alteons.map

                parts = line.split()
                if not parts:
                    continue

                # Determine status from first column
                status_char = line[0] if len(line) > 0 else ' '

                # Find map path (must contain /opt/sapro/ and end with .map)
                # It's typically the last part of the line
                map_path = None
                for part in reversed(parts):
                    if '/opt/sapro/' in part and part.endswith('.map'):
                        map_path = part
                        break

                if not map_path:
                    logger.debug(f"Could not parse map path from line: {line}")
                    continue

                # Extract map name (just the filename without path and extension)
                map_name = map_path.split('/')[-1]  # Get filename
                if map_name.endswith('.map'):
                    map_name = map_name[:-4]  # Remove .map extension

                # Determine status
                if status_char == 'R':
                    status = "running"
                elif status_char == ' ':
                    status = ""  # stopped
                else:
                    status = "error"

                result.append({
                    'name': map_name,
                    'status': status,
                    'full_path': map_path
                })

                logger.debug(f"Map found: {map_name} -> {map_path} (status: {status})")

            logger.info(f"Retrieved {len(result)} maps from workspace '{workspace}'")
            return result

        except Exception as e:
            logger.error(f"Failed to get map list from workspace '{workspace}': {e}", exc_info=True)
            raise Exception(f"Failed to get map list from workspace '{workspace}': {e}")

    def _get_all_maps_aggregated(self) -> List[Dict[str, str]]:
        """Get maps from all workspaces and aggregate results (super user only).

        Returns:
            List of dicts with name, status, and workspace fields.
        """
        try:
            ssh_client = get_sapro_ssh_client()
            wsp_dir = "/opt/sapro/wsp/"

            # List all .wsp files
            all_files = ssh_client.list_directory(wsp_dir)
            wsp_files = [f.replace('.wsp', '') for f in all_files if f.endswith('.wsp')]

            if not wsp_files:
                logger.warning("No workspace files found")
                return []

            # Query each workspace and aggregate
            aggregated_maps: List[Dict[str, str]] = []

            for workspace in wsp_files:
                try:
                    maps = self.get_all_maps(workspace=workspace)
                    # Add workspace field to each map
                    for map_info in maps:
                        map_info['workspace'] = workspace
                        aggregated_maps.append(map_info)
                except Exception as e:
                    logger.warning(f"Failed to query workspace '{workspace}': {e}")
                    continue

            logger.info(f"Aggregated {len(aggregated_maps)} maps from {len(wsp_files)} workspaces")
            return aggregated_maps

        except Exception as e:
            logger.error(f"Failed to aggregate maps from all workspaces: {e}", exc_info=True)
            raise Exception(f"Failed to aggregate maps: {e}")

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

    def get_full_map_path(self, map_name: str, workspace: str = "default") -> str:
        """Return the full path to a map file on the sapro server.

        Args:
            map_name: The logical map name (without extension).
            workspace: Workspace to search in (defaults to "default")

        Returns:
            Full path string from get_all_maps().

        Raises:
            Exception: If map not found.
        """
        maps = self.get_all_maps(workspace=workspace)
        map_info = next((m for m in maps if m['name'] == map_name), None)
        if not map_info:
            raise Exception(f"Map {map_name} not found in workspace {workspace}")
        return map_info['full_path']

    def _get_local_map_dir(self, workspace: str = "default") -> str:
        """Extract LocalMappedDir from workspace file.

        Reads the workspace .wsp file and extracts the LocalMappedDir attribute,
        which defines where maps are stored for this workspace.

        Args:
            workspace: Workspace name (without .wsp extension)

        Returns:
            Full path to map directory from workspace file (ends with /)

        Raises:
            Exception: If workspace file not found or LocalMappedDir not set
        """
        try:
            ssh_client = get_sapro_ssh_client()
            workspace_path = f"/opt/sapro/wsp/{workspace}.wsp"

            # Read workspace file
            read_cmd = f"cat {workspace_path}"
            success, workspace_content = ssh_client.execute_command(read_cmd, check_stderr=False)

            if not success:
                raise Exception(f"Failed to read workspace file: {workspace_content}")

            # Extract LocalMappedDir using regex
            # Match: LocalMappedDir = "/opt/sapro/projects/scale/map/"
            match = re.search(r'LocalMappedDir\s*=\s*"([^"]*)"', workspace_content)

            if not match:
                # Default workspace may not have LocalMappedDir explicitly set
                if workspace == "default":
                    logger.info(f"Workspace '{workspace}' has no LocalMappedDir, using default /opt/sapro/map/")
                    return "/opt/sapro/map/"
                raise Exception(f"LocalMappedDir not found in workspace {workspace}")

            local_dir = match.group(1)

            # Ensure it ends with /
            if not local_dir.endswith('/'):
                local_dir += '/'

            logger.info(f"LocalMappedDir for workspace '{workspace}': {local_dir}")
            return local_dir

        except Exception as e:
            logger.error(f"Failed to get LocalMappedDir for workspace '{workspace}': {e}", exc_info=True)
            raise

    def start_map_and_wait(self, map_name: str, workspace: str = "default") -> Tuple[bool, str]:
        """Start a map and wait until it's running.

        Executes async start command, then polls status every 2 seconds.
        Timeout: 5 minutes (300 seconds).

        Args:
            map_name: Map name (without .map extension)
            workspace: Workspace name (defaults to "default")

        Returns:
            (success, message)
        """
        import time

        # FIRST: Check if workspace has any maps
        try:
            all_maps = self.get_all_maps(workspace=workspace)
        except Exception as e:
            logger.error(f"Failed to get maps from workspace '{workspace}': {e}")
            return False, f"Cannot access workspace '{workspace}': {e}"

        if not all_maps:
            logger.warning(f"Workspace '{workspace}' has no maps defined.")
            return False, f"Workspace '{workspace}' has no maps. Cannot start map '{map_name}'."

        # THEN: Find the map to start
        map_info = next((m for m in all_maps if m['name'] == map_name), None)
        if not map_info:
            return False, f"Map '{map_name}' not found in workspace '{workspace}'"

        map_path = map_info['full_path']

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
                maps = self.get_all_maps(workspace=workspace)
                map_status = next((m for m in maps if m['name'] == map_name), None)

                if map_status and map_status['status'] == 'running':
                    logger.info(f"Map {map_name} is now running (took {elapsed}s)")
                    return True, f"Map {map_name} started successfully"

                logger.debug(
                    f"Map {map_name} status: {map_status['status'] if map_status else 'not found'}, elapsed: {elapsed}s")

            # Timeout reached
            return False, f"Timeout waiting for map {map_name} to start (5 minutes)"

        except Exception as e:
            logger.error(f"Failed to start map {map_name}: {e}", exc_info=True)
            return False, f"Failed to start map: {e}"

    def stop_map_and_wait(self, map_name: str, workspace: str = "default") -> Tuple[bool, str]:
        """Stop a map and wait until terminated.

        Executes synchronous stop command that blocks until termination.
        Timeout: 5 minutes.

        Args:
            map_name: Map name (without .map extension)
            workspace: Workspace name (defaults to "default")

        Returns:
            (success, message)
        """
        # FIRST: Check if workspace has any maps
        try:
            all_maps = self.get_all_maps(workspace=workspace)
        except Exception as e:
            logger.error(f"Failed to get maps from workspace '{workspace}': {e}")
            return False, f"Cannot access workspace '{workspace}': {e}"

        if not all_maps:
            logger.warning(f"Workspace '{workspace}' has no maps defined.")
            return False, f"Workspace '{workspace}' has no maps. Cannot stop map '{map_name}'."

        # THEN: Find the map to stop
        map_info = next((m for m in all_maps if m['name'] == map_name), None)
        if not map_info:
            return False, f"Map '{map_name}' not found in workspace '{workspace}'"

        map_path = map_info['full_path']

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

    def create_map(self, map_name: str, workspace: str = "default") -> Tuple[bool, str]:
        """Create a new map file and add it to workspace using SSH.

        Creates the physical map file in the location specified by LocalMappedDir,
        then adds a reference to the workspace file with the FULL PATH.

        Args:
            map_name: Map name (without .map extension)
            workspace: Workspace name (defaults to "default")

        Returns:
            (success, message)
        """
        try:
            ssh_client = get_sapro_ssh_client()
            workspace_path = f"/opt/sapro/wsp/{workspace}.wsp"

            # Step 1: Get map directory from LocalMappedDir
            try:
                map_directory = self._get_local_map_dir(workspace=workspace)
            except Exception as e:
                return False, f"Failed to get map directory: {e}"

            logger.info(f"Creating map in directory: {map_directory}")

            # Step 2: Read workspace file to check if map already exists
            read_cmd = f"cat {workspace_path}"
            success, workspace_content = ssh_client.execute_command(read_cmd, check_stderr=False)

            if not success:
                return False, f"Failed to read workspace file: {workspace_content}"

            # Parse existing maps to check if already exists
            map_paths = re.findall(r'Name\s*=\s*"([^"]+\.map)"', workspace_content)
            existing_names = [p.split('/')[-1].replace('.map', '') for p in map_paths]

            if map_name in existing_names:
                return False, f"Map {map_name} already exists in workspace {workspace}"

            # Step 3: Create physical map file
            map_file_path = f"{map_directory}{map_name}.map"

            map_file_content = '''<DeviceMap
        Release = "11.0"
        Description = ""
        UserData = ""
        SetupFile = ""
        Interface = ""
        Separator = ""
        StartInterfaceNum = "0"
        Username = "">
</DeviceMap>'''

            # Write PHYSICAL map file to server
            escaped_content = map_file_content.replace("'", "'\\''")
            create_map_file_cmd = f"echo '{escaped_content}' > {map_file_path}"
            success, output = ssh_client.execute_command(create_map_file_cmd, check_stderr=False)

            if not success:
                return False, f"Failed to create physical map file: {output}"

            logger.info(f"Created physical map file: {map_file_path}")

            # Step 4: Add map reference to workspace file with FULL PATH
            new_map_entry = f'''                <Map
                        Name = "{map_file_path}"
                />'''

            # Find position to insert (before </Server> closing tag)
            if '</Server>' not in workspace_content:
                return False, "Workspace file format invalid (no </Server> tag)"

            # Insert new map entry before </Server>
            updated_content = workspace_content.replace('</Server>', f'{new_map_entry}\n        </Server>')

            # Write updated workspace file
            escaped_content = updated_content.replace("'", "'\\''")
            write_workspace_cmd = f"echo '{escaped_content}' > {workspace_path}"
            success, output = ssh_client.execute_command(write_workspace_cmd, check_stderr=False)

            if not success:
                return False, f"Failed to update workspace file: {output}"

            logger.info(f"Added map reference to workspace with full path: {map_file_path}")
            return True, f"Map {map_name} created successfully in workspace {workspace}"

        except Exception as e:
            logger.error(f"Failed to create map {map_name}: {e}", exc_info=True)
            return False, f"Failed to create map: {e}"

    def start_devices_from_map(self, map_full_path: str, devices_names: list) -> Tuple[bool, str]:
        """Start one or more devices listed in a map using SSH commands.

        Args:
            map_full_path: Full path to map file (e.g., /opt/sapro/projects/dev/map/DP.map)
            devices_names: List of device names/IPs to start

        Returns:
            (success, combined_messages)
        """
        try:
            ssh_client = get_sapro_ssh_client()
            messages = []

            for device_ip in devices_names:
                # Build SSH command with full path (already provided)
                cmd = f"/opt/sapro/bin/sapcnsl -p {self.sapro_port} -m {map_full_path} -c startdev -d {device_ip}"

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
            logger.error(f"Failed to start device(s): {e}", exc_info=True)
            return False, f"Failed to start device(s): {e}"

    def stop_devices_from_map(self, map_full_path: str, devices_names: list) -> Tuple[bool, str]:
        """Stop one or more devices listed in a map using SSH commands.

        Args:
            map_full_path: Full path to map file (e.g., /opt/sapro/projects/dev/map/DP.map)
            devices_names: List of device names/IPs to stop

        Returns:
            (success, combined_messages)
        """
        try:
            ssh_client = get_sapro_ssh_client()
            messages = []

            for device_ip in devices_names:
                # Build SSH command with full path (already provided)
                cmd = f"/opt/sapro/bin/sapcnsl -p {self.sapro_port} -m {map_full_path} -c stopdev -d {device_ip}"

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
            logger.error(f"Failed to stop device(s): {e}", exc_info=True)
            return False, f"Failed to stop device(s): {e}"

    def create_device(self, device_ip: str, raw_xml_content: str, map_name: str, workspace: str = "default") -> Tuple[bool, str]:
        """Create (or start existing) simulator device on the sapro server using SSH.

        Special handling for empty maps:
        - Empty map: Add device XML directly to map file, then start map
        - Non-empty map: Use normal adddev command

        Workflow:
        1. Get full map path from workspace
        2. Check if device already exists
        3. If exists: start it
        4. If not exists:
           a. Check if map is empty (no <Device> tags)
           b. If empty: insert device XML into map file
           c. If not empty: use adddev command
        5. Start map if needed

        Args:
            device_ip: Device IP address
            raw_xml_content: Device configuration XML
            map_name: Map name (without extension)
            workspace: Workspace name (defaults to "default")

        Returns:
            (success, message)
        """
        try:
            ssh_client = get_sapro_ssh_client()

            # FIRST: Check if workspace has any maps
            try:
                all_maps = self.get_all_maps(workspace=workspace)
            except Exception as e:
                logger.error(f"Failed to get maps from workspace '{workspace}': {e}")
                return False, f"Cannot access workspace '{workspace}': {e}"

            if not all_maps:
                logger.warning(f"Workspace '{workspace}' has no maps defined.")
                return False, f"Workspace '{workspace}' has no maps. Cannot add device '{device_ip}'."

            # THEN: Find the map
            map_info = next((m for m in all_maps if m['name'] == map_name), None)
            if not map_info:
                return False, f"Map '{map_name}' not found in workspace '{workspace}'"

            map_path = map_info['full_path']
            was_map_running = (map_info['status'] == 'running')

            # Check if device already exists using SSH devlist command
            if was_map_running:
                devlist_cmd = f"/opt/sapro/bin/sapcnsl -m {map_path} -c devlist"
                logger.debug(f"Checking if device {device_ip} exists: {devlist_cmd}")

                success, output = ssh_client.execute_command(devlist_cmd, check_stderr=False)

                device_exists = False
                if success and output:
                    # Parse devlist output to check if device exists
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

                        parts = line.split()
                        if parts:
                            device_name = parts[0]
                            if '//' in device_name:
                                ip = device_name.split('//')[0]
                            else:
                                ip = device_name

                            if ip == device_ip:
                                device_exists = True
                                break

                if device_exists:
                    # Device exists - start it
                    logger.info(f"Device {device_ip} already exists, starting it")
                    ok, msg = self.start_devices_from_map(map_path, [device_ip])
                    if ok:
                        return True, f"Simulator {device_ip} already exists and was started"
                    return False, f"Simulator {device_ip} already exists but failed to start: {msg}"

                # Device doesn't exist - need to add it
            logger.info(f"Device {device_ip} doesn't exist, adding to map {map_name}")

            # Get map directory from LocalMappedDir (not by parsing map path)
            try:
                map_directory = self._get_local_map_dir(workspace=workspace)
            except Exception as e:
                logger.error(f"Failed to get map directory: {e}")
                return False, f"Failed to get map directory: {e}"

            # Step 1: Read map file to check if it's empty
            read_map_cmd = f"cat {map_path}"
            success, map_content = ssh_client.execute_command(read_map_cmd, check_stderr=False)

            if not success:
                return False, f"Failed to read map file: {map_content}"

            # Check if map is empty (no <Device> tags)
            is_empty_map = '<Device>' not in map_content

            logger.info(f"Map {map_name} is {'empty' if is_empty_map else 'not empty'}")

            if is_empty_map:
                # EMPTY MAP: Add device XML directly into map file
                logger.info(f"Adding first device to empty map {map_name} by editing map file")

                # Insert device XML before closing </DeviceMap> tag
                if '</DeviceMap>' not in map_content:
                    return False, "Map file format invalid (no </DeviceMap> tag)"

                # Extract only the <Device>...</Device> section from raw_xml_content
                # The template may contain full <DeviceMap> wrapper or just <Device> tags
                device_xml = raw_xml_content.strip()

                # If the XML contains <DeviceMap> wrapper, extract only the <Device> section
                if '<DeviceMap' in device_xml and '</DeviceMap>' in device_xml:
                    # Find the content between <DeviceMap...> and </DeviceMap>
                    start_idx = device_xml.find('>') + 1  # After first > in <DeviceMap...>
                    end_idx = device_xml.rfind('</DeviceMap>')
                    device_xml = device_xml[start_idx:end_idx].strip()

                # Now insert only the Device section before </DeviceMap>
                updated_map_content = map_content.replace('</DeviceMap>', f'\n{device_xml}\n</DeviceMap>')

                # Write updated map file
                escaped_content = updated_map_content.replace("'", "'\\''")
                write_map_cmd = f"echo '{escaped_content}' > {map_path}"
                success, output = ssh_client.execute_command(write_map_cmd, check_stderr=False)

                if not success:
                    return False, f"Failed to update map file: {output}"

                logger.info(f"Added device {device_ip} directly to map file {map_path}")

                # Start map after adding device to empty map
                if not was_map_running:
                    logger.info(f"Map {map_name} was not running, starting it now...")
                    start_ok, start_msg = self.start_map_and_wait(map_name, workspace=workspace)
                    if not start_ok:
                        return False, f"Device {device_ip} added but failed to start map: {start_msg}"
                    logger.info(f"Map {map_name} started successfully")
            else:
                # NON-EMPTY MAP: Use normal adddev command
                logger.info(f"Adding device to non-empty map using adddev command")

                # If map is stopped, start it first before using adddev
                if not was_map_running:
                    logger.info(f"Map {map_name} is stopped with existing devices, starting it first...")
                    start_ok, start_msg = self.start_map_and_wait(map_name, workspace=workspace)
                    if not start_ok:
                        return False, f"Failed to start map before adding device: {start_msg}"
                    logger.info(f"Map {map_name} started successfully")

                # Create device file path
                new_device_file_path = f"{map_directory}{device_ip}.map"

                # Write device file to server using SSH
                device_file_content = raw_xml_content.strip()
                escaped_content = device_file_content.replace("'", "'\\''")
                write_device_file_cmd = f"echo '{escaped_content}' > {new_device_file_path}"
                success, output = ssh_client.execute_command(write_device_file_cmd, check_stderr=False)

                if not success:
                    return False, f"Failed to create device file: {output}"

                logger.info(f"Created device file: {new_device_file_path}")

                # Add device to map using SSH adddev command (map is now running)
                adddev_cmd = f"/opt/sapro/bin/sapcnsl -p {self.sapro_port} -m {map_path} -c adddev -f {new_device_file_path}"
                logger.debug(f"Adding device to map: {adddev_cmd}")

                success, output = ssh_client.execute_command(adddev_cmd, check_stderr=False)

                if not success:
                    return False, f"Failed to add device to map: {output}"

                logger.info(f"Device {device_ip} added to map successfully: {output}")

                # Start the newly added device (map is already running)
                ok, msg = self.start_devices_from_map(map_path, [device_ip])
                if not ok:
                    return False, f"Device {device_ip} added but failed to start: {msg}"

            return True, f"Device {device_ip} created and added to map {map_path}"

        except Exception as e:
            logger.error(f"Failed to create device {device_ip}: {e}", exc_info=True)
            return False, f"Failed to create device {device_ip}: {str(e)}"

    def update_device(self, device_ip: str, raw_xml_content: str, map_name: str, workspace: str = "default") -> Tuple[bool, str]:
        """Update an existing simulator device by deleting and re-adding with new configuration.

        Workflow:
        1. Check map status before deletion
        2. Delete device from map
        3. Check if map is empty after deletion
        4. If empty: Add device XML directly to map file, then start map if needed
        5. If not empty: Start map if stopped, then use adddev command

        Args:
            device_ip: Device IP address
            raw_xml_content: New device configuration XML
            map_name: Map name (without extension)
            workspace: Workspace name (defaults to "default")

        Returns:
            (success, message)
        """
        try:
            ssh_client = get_sapro_ssh_client()

            # FIRST: Check if workspace has any maps
            try:
                all_maps = self.get_all_maps(workspace=workspace)
            except Exception as e:
                logger.error(f"Failed to get maps from workspace '{workspace}': {e}")
                return False, f"Cannot access workspace '{workspace}': {e}"

            if not all_maps:
                logger.warning(f"Workspace '{workspace}' has no maps defined.")
                return False, f"Workspace '{workspace}' has no maps. Cannot update device '{device_ip}'."

            # THEN: Find the map
            map_info = next((m for m in all_maps if m['name'] == map_name), None)
            if not map_info:
                return False, f"Map '{map_name}' not found in workspace '{workspace}'"

            was_map_running = (map_info['status'] == 'running')
            logger.info(f"Map {map_name} status before update: {'running' if was_map_running else 'stopped'}")

            # Step 2: Delete device from map
            logger.info(f"Deleting device {device_ip} from map {map_name}")
            success, message = self.delete_device(map_name, device_ip, workspace=workspace)
            if not success:
                logger.warning(f"Delete device warning (continuing anyway): {message}")
                # Don't fail - device might not be in map, we'll add it back

            # Get full map path
            map_path = self.get_full_map_path(map_name, workspace=workspace)

            # Get map directory from LocalMappedDir (not by parsing map path)
            try:
                map_directory = self._get_local_map_dir(workspace=workspace)
            except Exception as e:
                logger.error(f"Failed to get map directory: {e}")
                return False, f"Failed to get map directory: {e}"

            # Step 3: Check if map is empty after deletion
            read_map_cmd = f"cat {map_path}"
            success, map_content = ssh_client.execute_command(read_map_cmd, check_stderr=False)

            if not success:
                return False, f"Failed to read map file: {map_content}"

            is_empty_map = '<Device>' not in map_content
            logger.info(f"Map {map_name} is {'empty' if is_empty_map else 'not empty'} after device deletion")

            # Step 4: Add device back to map
            if is_empty_map:
                # EMPTY MAP: Add device XML directly into map file
                logger.info(f"Adding device to empty map {map_name} by editing map file")

                if '</DeviceMap>' not in map_content:
                    return False, "Map file format invalid (no </DeviceMap> tag)"

                # Extract only the <Device> section
                device_xml = raw_xml_content.strip()
                if '<DeviceMap' in device_xml and '</DeviceMap>' in device_xml:
                    start_idx = device_xml.find('>') + 1
                    end_idx = device_xml.rfind('</DeviceMap>')
                    device_xml = device_xml[start_idx:end_idx].strip()

                # Insert device XML before </DeviceMap>
                updated_map_content = map_content.replace('</DeviceMap>', f'\n{device_xml}\n</DeviceMap>')

                # Write updated map file
                escaped_content = updated_map_content.replace("'", "'\\''")
                write_map_cmd = f"echo '{escaped_content}' > {map_path}"
                success, output = ssh_client.execute_command(write_map_cmd, check_stderr=False)

                if not success:
                    return False, f"Failed to update map file: {output}"

                logger.info(f"Added device {device_ip} directly to map file {map_path}")

                # Start map after adding device to empty map (if it was stopped)
                if not was_map_running:
                    logger.info(f"Map {map_name} was stopped, starting it now...")
                    start_ok, start_msg = self.start_map_and_wait(map_name, workspace=workspace)
                    if not start_ok:
                        return False, f"Device {device_ip} updated but failed to start map: {start_msg}"
                    logger.info(f"Map {map_name} started successfully")
            else:
                # NON-EMPTY MAP: Use adddev command
                logger.info(f"Adding device to non-empty map using adddev command")

                # If map is stopped, start it first before using adddev
                if not was_map_running:
                    logger.info(f"Map {map_name} is stopped with existing devices, starting it first...")
                    start_ok, start_msg = self.start_map_and_wait(map_name, workspace=workspace)
                    if not start_ok:
                        return False, f"Failed to start map before updating device: {start_msg}"
                    logger.info(f"Map {map_name} started successfully")

                # Create device file
                device_file_path = f"{map_directory}{device_ip}.map"
                device_file_content = raw_xml_content.strip()
                escaped_content = device_file_content.replace("'", "'\\''")
                write_device_file_cmd = f"echo '{escaped_content}' > {device_file_path}"
                success, output = ssh_client.execute_command(write_device_file_cmd, check_stderr=False)

                if not success:
                    return False, f"Failed to create device file: {output}"

                logger.info(f"Created device file: {device_file_path}")

                # Add device to map using adddev command (map is now running)
                adddev_cmd = f"/opt/sapro/bin/sapcnsl -p {self.sapro_port} -m {map_path} -c adddev -f {device_file_path}"
                logger.debug(f"Adding device to map: {adddev_cmd}")

                success, output = ssh_client.execute_command(adddev_cmd, check_stderr=False)

                if not success:
                    return False, f"Failed to add device to map: {output}"

                logger.info(f"Device {device_ip} added to map successfully: {output}")

                # Start the newly added device (map is already running)
                ok, msg = self.start_devices_from_map(map_path, [device_ip])
                if not ok:
                    logger.warning(f"Device {device_ip} updated but failed to start: {msg}")
                    # Don't fail the whole operation if device start fails

            return True, f"Device {device_ip} updated successfully on map {map_name}"

        except Exception as e:
            logger.error(f"Failed to update device {device_ip}: {e}", exc_info=True)
            return False, f"Failed to update device {device_ip}: {str(e)}"

    def delete_device(self, map_name: str, device_ip: str, workspace: str = "default") -> Tuple[bool, str]:
        """Delete a device from the specified map using SSH.

        Args:
            map_name: Map name (without .map extension)
            device_ip: IP/name of the device to delete
            workspace: Workspace name (defaults to "default")

        Returns:
            (success, message)
        """

        try:
            # FIRST: Check if workspace has any maps
            try:
                all_maps = self.get_all_maps(workspace=workspace)
            except Exception as e:
                logger.error(f"Failed to get maps from workspace '{workspace}': {e}")
                return False, f"Cannot access workspace '{workspace}': {e}"

            if not all_maps:
                logger.warning(f"Workspace '{workspace}' has no maps defined.")
                return False, f"Workspace '{workspace}' has no maps. Cannot delete device from map '{map_name}'."

            # THEN: Get full map path (consistent with other methods)
            map_path = self.get_full_map_path(map_name, workspace=workspace)

            ssh_client = get_sapro_ssh_client()

            # Execute delete command via SSH
            cmd = f"/opt/sapro/bin/sapcnsl -m {map_path} -c deldev -d {device_ip}"

            logger.debug(f"Executing delete device command via SSH: {cmd}")
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
