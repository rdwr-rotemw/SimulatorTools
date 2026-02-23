import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
from typing import List, Dict, Optional, Tuple

from backend.app.utils.config import settings
from backend.app.utils.logger import logger
from backend.app.utils.sapro_ssh import get_sapro_ssh_client
from backend.app.utils.snmp import SnmpClient


class DeviceStatus(Enum):
    SHUTDOWN = 1
    LOADING = 2
    OK = 3
    FAILED = 4
    DISABLED = 5
    STOPPING = 6

    @staticmethod
    def get_status(code: int) -> str:
        return DeviceStatus(code).name


class SaproDevice:
    def __init__(self, ip_address: str, map: str, status: str, type: str = None, version: str = None):
        self.ip_address = ip_address
        self.map = map
        self.status = status
        self.type = type
        self.version = version


class SaproCommunicationHandler:
    """Instance-based handler for communicating with the Sapro server.

    This class wraps the lower-level `sapro` ProductLibraries module and exposes
    small helper methods suitable for dependency-injection in FastAPI.
    """

    # Per-map-path locks to serialise concurrent read-modify-write operations.
    # _map_locks_guard protects the dict itself; each entry is the actual map lock.
    _map_locks: Dict[str, threading.Lock] = {}
    _map_locks_guard: threading.Lock = threading.Lock()

    @classmethod
    def _get_map_lock(cls, map_path: str) -> threading.Lock:
        with cls._map_locks_guard:
            if map_path not in cls._map_locks:
                cls._map_locks[map_path] = threading.Lock()
            return cls._map_locks[map_path]

    def __init__(self, sapro_ip: str, sapro_port: int):
        """Initialize handler state for SSH-based Sapro communication.

        Args:
            sapro_ip: IP address of the sapro server.
            sapro_port: Port of the sapro server.
        """
        self.sapro_ip = sapro_ip
        self.sapro_port = int(sapro_port)

    @staticmethod
    def _extract_workspace_and_map_name(map_path: str) -> Tuple[str, str]:
        """Extract workspace and map_name from full map path.

        Args:
            map_path: Full path like /opt/sapro/map/default.map or /opt/sapro/projects/dev/map/DP.map

        Returns:
            (workspace, map_name) tuple
        """
        # Extract map name (filename without .map extension)
        map_name = map_path.split("/")[-1].replace(".map", "")

        # Extract workspace from path
        # Default workspace: /opt/sapro/map/{map_name}.map
        # Custom workspace: /opt/sapro/projects/{workspace}/map/{map_name}.map
        if "/projects/" in map_path:
            # Custom workspace
            parts = map_path.split("/projects/")[1].split("/")
            workspace = parts[0]
        else:
            # Default workspace
            workspace = "default"

        return workspace, map_name

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
            logger.warning(
                f"Workspace '{workspace}' has no maps defined. No devices to retrieve."
            )
            return []

        # Filter only running maps
        running_maps = [m for m in all_maps if m["status"] == "running"]
        logger.info(
            f"Found {len(running_maps)} running maps out of {len(all_maps)} total maps"
        )

        # Step 2: Get device list from each running map via SSH
        ssh_client = get_sapro_ssh_client()
        device_tasks = []

        for map_info in running_maps:
            map_name = map_info["name"]
            map_full_path = map_info["full_path"]
            cmd = f"/opt/sapro/bin/sapcnsl -m {map_full_path} -c devlist"

            try:
                logger.debug(f"Executing devlist for map {map_name}")
                success, output = ssh_client.execute_command(cmd, check_stderr=False)

                if not success:
                    logger.error(
                        f"Failed to get device list for map {map_name}: {output}"
                    )
                    continue

                # Parse devlist output
                lines = output.split("\n")
                in_table = False

                for line in lines:
                    # Skip header separators
                    if line.strip().startswith("---"):
                        in_table = True
                        continue

                    # Stop at footer separator
                    if in_table and line.strip().startswith("---"):
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
                    if "//" in device_name:
                        device_ip = device_name.split("//")[0]
                    else:
                        device_ip = device_name

                    # Determine status from second column if present
                    # Parse status character and map to numeric code
                    # DeviceStatus mapping: 1=' ', 2='*', 3='R', 4='F', 5='D', 6='S'
                    status_char = parts[1] if len(parts) > 1 else ""

                    # Map SSH status character to numeric code
                    if status_char == "R":
                        status_code = 3  # OK (running)
                    elif status_char == "*":
                        status_code = 2  # LOADING
                    elif status_char == "F":
                        status_code = 4  # FAILED
                    elif status_char == "D":
                        status_code = 5  # DISABLED
                    elif status_char == "S":
                        status_code = 6  # STOPPING
                    else:
                        status_code = 1  # SHUTDOWN (empty/space)

                    device_tasks.append((device_ip, map_name, status_code))

            except Exception as e:
                logger.error(f"Failed to process devlist for map {map_name}: {e}")
                continue

        logger.info(
            f"Found {len(device_tasks)} total devices from {len(running_maps)} running maps"
        )

        # Step 3: Query device type/version via SNMP (parallel)
        devices: List[SaproDevice] = []
        snmp_start = time.time()

        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_device = {
                executor.submit(self.snmp_get_device_info, dev_ip): (
                    dev_ip,
                    map_name,
                    status,
                )
                for dev_ip, map_name, status in device_tasks
            }

            for future in as_completed(future_to_device):
                dev_ip, map_name, status = future_to_device[future]
                try:
                    device_type, device_version = future.result()
                    devices.append(
                        SaproDevice(
                            ip_address=dev_ip,
                            map=map_name,
                            status=DeviceStatus.get_status(status),
                            type=device_type or "",
                            version=device_version or "",
                        )
                    )
                except Exception as e:
                    logger.error(f"Failed to query device {dev_ip}: {e}")
                    devices.append(
                        SaproDevice(
                            ip_address=dev_ip,
                            map=map_name,
                            status=DeviceStatus.get_status(status),
                            type="",
                            version="",
                        )
                    )

        snmp_end = time.time()
        logger.info(
            f"SNMP queries completed in {snmp_end - snmp_start:.2f} seconds for {len(devices)} devices"
        )
        logger.info(
            f"get_all_devices completed in {time.time() - start_time:.2f} seconds"
        )

        return devices

    def snmp_get_device_info(
        self, device_ip: str
    ) -> Tuple[Optional[str], Optional[str]]:
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
                logger.warning(
                    f"Unrecognized device type for {device_ip}: {device_type}"
                )
                return None, None

        except Exception as e:
            logger.error(f"SNMP query failed for {device_ip}: {type(e).__name__}: {e}")
            return None, None

    def get_all_maps(self, workspace: str) -> List[Dict[str, str]]:
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
            success, workspace_content = ssh_client.execute_command(
                read_cmd, check_stderr=False
            )

            if not success:
                raise Exception(f"Failed to read workspace file: {workspace_content}")

            # Check if workspace has any <Map> tags
            if "<Map" not in workspace_content:
                logger.info(
                    f"Workspace '{workspace}' has no maps defined (no <Map> tags in file)"
                )
                return []

            # STEP 2: Only run wspstats if workspace has maps
            cmd = f"/opt/sapro/bin/sapcnsl -w {workspace_path} -c wspstats"
            logger.debug(
                f"Executing wspstats command for workspace '{workspace}': {cmd}"
            )

            success, output = ssh_client.execute_command(cmd, check_stderr=False)

            if not success:
                raise Exception(f"SSH command failed: {output}")

            # STEP 3: Parse the table output
            result: List[Dict[str, str]] = []
            lines = output.split("\n")

            # Find where the table data starts (after "Status    Port #    Map Name" header)
            in_table = False
            for line in lines:
                # Skip header separators (lines with only dashes)
                if line.strip().startswith("---"):
                    in_table = True
                    continue

                # Stop at footer separator
                if in_table and line.strip().startswith("---"):
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
                status_char = line[0] if len(line) > 0 else " "

                # Find map path (must contain /opt/sapro/ and end with .map)
                # It's typically the last part of the line
                map_path = None
                for part in reversed(parts):
                    if "/opt/sapro/" in part and part.endswith(".map"):
                        map_path = part
                        break

                if not map_path:
                    logger.debug(f"Could not parse map path from line: {line}")
                    continue

                # Extract map name (just the filename without path and extension)
                map_name = map_path.split("/")[-1]  # Get filename
                if map_name.endswith(".map"):
                    map_name = map_name[:-4]  # Remove .map extension

                # Determine status
                if status_char == "R":
                    status = "running"
                elif status_char == " ":
                    status = ""  # stopped
                else:
                    status = "error"

                result.append(
                    {"name": map_name, "status": status, "full_path": map_path}
                )

                logger.debug(f"Map found: {map_name} -> {map_path} (status: {status})")

            logger.info(f"Retrieved {len(result)} maps from workspace '{workspace}'")
            return result

        except Exception as e:
            logger.error(
                f"Failed to get map list from workspace '{workspace}': {e}",
                exc_info=True,
            )
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
            wsp_files = [f.replace(".wsp", "") for f in all_files if f.endswith(".wsp")]

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
                        map_info["workspace"] = workspace
                        aggregated_maps.append(map_info)
                except Exception as e:
                    logger.warning(f"Failed to query workspace '{workspace}': {e}")
                    continue

            logger.info(
                f"Aggregated {len(aggregated_maps)} maps from {len(wsp_files)} workspaces"
            )
            return aggregated_maps

        except Exception as e:
            logger.error(
                f"Failed to aggregate maps from all workspaces: {e}", exc_info=True
            )
            raise Exception(f"Failed to aggregate maps: {e}")

    def find_map_workspace(self, map_name: str) -> Optional[str]:
        """Find which workspace contains the given map by searching all workspaces.

        Args:
            map_name: The logical map name (without extension).

        Returns:
            Workspace name containing the map, or None if not found.
        """
        # Get all maps from all workspaces
        all_maps = self.get_all_maps(workspace="*")
        map_info = next((m for m in all_maps if m["name"] == map_name), None)
        if not map_info:
            return None

        # Extract workspace from full_path
        # Path format: /opt/sapro/<workspace>/<map_name>.map OR /opt/sapro/<map_name>.map (default)
        full_path = map_info["full_path"]
        # Remove /opt/sapro/ prefix
        if full_path.startswith("/opt/sapro/"):
            path_suffix = full_path[len("/opt/sapro/"):]
            # If there's a directory before the map file, that's the workspace
            if "/" in path_suffix:
                workspace_candidate = path_suffix.split("/")[0]
                # Verify it's not the map file itself
                if not workspace_candidate.endswith(".map"):
                    return workspace_candidate
        # Default workspace if no subdirectory
        return "default"

    def get_full_map_path(self, map_name: str, workspace: str) -> str:
        """Return the full path to a map file on the sapro server.

        Args:
            map_name: The logical map name (without extension).
            workspace: Workspace to search in. Use "*" to auto-detect workspace.

        Returns:
            Full path to map file.

        Raises:
            Exception: If workspace not found or invalid.
        """
        # Auto-detect workspace if "*" is provided
        if workspace == "*":
            detected_workspace = self.find_map_workspace(map_name)
            if not detected_workspace:
                raise Exception(f"Map '{map_name}' not found in any workspace")
            workspace = detected_workspace

        # Get the map directory for this workspace
        # For default: /opt/sapro/map/
        # For custom: reads LocalMappedDir from .wsp file
        map_dir = self._get_local_map_dir(workspace)

        # Construct the full path
        map_path = f"{map_dir}{map_name}.map"

        return map_path

    def _get_local_map_dir(self, workspace: str) -> str:
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
        if workspace == "*" or workspace == "default":
            # For default workspace, map directory is always /opt/sapro/map/
            default_map_dir = "/opt/sapro/map/"
            logger.info(
                f"Using default map directory for workspace '{workspace}': {default_map_dir}"
            )
            return default_map_dir
        try:
            ssh_client = get_sapro_ssh_client()
            workspace_path = f"/opt/sapro/wsp/{workspace}.wsp"

            # Read workspace file
            read_cmd = f"cat {workspace_path}"
            success, workspace_content = ssh_client.execute_command(
                read_cmd, check_stderr=False
            )

            if not success:
                raise Exception(f"Failed to read workspace file: {workspace_content}")

            # Extract LocalMappedDir using regex
            # Match: LocalMappedDir = "/opt/sapro/projects/scale/map/"
            match = re.search(r'LocalMappedDir\s*=\s*"([^"]*)"', workspace_content)

            if not match:
                # Default workspace may not have LocalMappedDir explicitly set
                if workspace == "default":
                    logger.info(
                        f"Workspace '{workspace}' has no LocalMappedDir, using default /opt/sapro/map/"
                    )
                    return "/opt/sapro/map/"
                raise Exception(f"LocalMappedDir not found in workspace {workspace}")

            local_dir = match.group(1)

            # Ensure it ends with /
            if not local_dir.endswith("/"):
                local_dir += "/"

            logger.info(f"LocalMappedDir for workspace '{workspace}': {local_dir}")
            return local_dir

        except Exception as e:
            logger.error(
                f"Failed to get LocalMappedDir for workspace '{workspace}': {e}",
                exc_info=True,
            )
            raise

    def start_map_and_wait(self, map_path: str) -> Tuple[bool, str]:
        """Start a map and wait until it's running.

        Executes async start command, then polls status every 2 seconds.
        Timeout: 5 minutes (300 seconds).

        Args:
            map_path: Full map path (e.g., /opt/sapro/map/default.map)

        Returns:
            (success, message)
        """
        import time

        # Extract workspace and map_name from path
        workspace, map_name = self._extract_workspace_and_map_name(map_path)

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
                map_status = next((m for m in maps if m["name"] == map_name), None)

                if map_status and map_status["status"] == "running":
                    logger.info(f"Map {map_name} is now running (took {elapsed}s)")
                    return True, f"Map {map_name} started successfully"

                logger.debug(
                    f"Map {map_name} status: {map_status['status'] if map_status else 'not found'}, elapsed: {elapsed}s"
                )

            # Timeout reached
            return False, f"Timeout waiting for map {map_name} to start (5 minutes)"

        except Exception as e:
            logger.error(f"Failed to start map {map_name}: {e}", exc_info=True)
            return False, f"Failed to start map: {e}"

    def stop_map_and_wait(self, map_path: str) -> Tuple[bool, str]:
        """Stop a map and wait until terminated.

        Executes synchronous stop command that blocks until termination.
        Timeout: 5 minutes.

        Args:
            map_path: Full map path (e.g., /opt/sapro/map/default.map)

        Returns:
            (success, message)
        """
        # Extract workspace and map_name from path
        workspace, map_name = self._extract_workspace_and_map_name(map_path)

        cmd = f"/opt/sapro/bin/sapcnsl -m {map_path} -c stop"

        try:
            ssh_client = get_sapro_ssh_client()
            logger.info(f"Stopping map {map_name}")

            # Execute stop command with extended timeout (sync - blocks until done)
            # Use 320 seconds (5 min + 20s buffer) to allow for 5-minute map termination
            success, output = ssh_client.execute_command(
                cmd, check_stderr=False, timeout=320
            )

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

    def create_map(self, map_name: str, workspace: str) -> Tuple[bool, str]:
        """Create a new map file and add it to workspace using SSH.

        Creates the physical map file in the location specified by LocalMappedDir,
        then adds a reference to the workspace file with the FULL PATH.

        Args:
            map_name: Map name (without .map extension)
            workspace: Workspace name

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
            success, workspace_content = ssh_client.execute_command(
                read_cmd, check_stderr=False
            )

            if not success:
                return False, f"Failed to read workspace file: {workspace_content}"

            # Parse existing maps to check if already exists
            map_paths = re.findall(r'Name\s*=\s*"([^"]+\.map)"', workspace_content)
            existing_names = [p.split("/")[-1].replace(".map", "") for p in map_paths]

            if map_name in existing_names:
                return False, f"Map {map_name} already exists in workspace {workspace}"

            # Step 3: Create physical map file
            map_file_path = f"{map_directory}{map_name}.map"

            map_file_content = """<DeviceMap
        Release = "11.0"
        Description = ""
        UserData = ""
        SetupFile = ""
        Interface = ""
        Separator = ""
        StartInterfaceNum = "0"
        Username = "">
</DeviceMap>"""

            # Write PHYSICAL map file to server
            escaped_content = map_file_content.replace("'", "'\\''")
            create_map_file_cmd = f"echo '{escaped_content}' > {map_file_path}"
            success, output = ssh_client.execute_command(
                create_map_file_cmd, check_stderr=False
            )

            if not success:
                return False, f"Failed to create physical map file: {output}"

            logger.info(f"Created physical map file: {map_file_path}")

            # Step 4: Add map reference to workspace file with FULL PATH
            new_map_entry = f"""                <Map
                        Name = "{map_file_path}"
                />"""

            # Find position to insert (before </Server> closing tag)
            if "</Server>" not in workspace_content:
                return False, "Workspace file format invalid (no </Server> tag)"

            # Insert new map entry before </Server>
            updated_content = workspace_content.replace(
                "</Server>", f"{new_map_entry}\n        </Server>"
            )

            # Write updated workspace file
            escaped_content = updated_content.replace("'", "'\\''")
            write_workspace_cmd = f"echo '{escaped_content}' > {workspace_path}"
            success, output = ssh_client.execute_command(
                write_workspace_cmd, check_stderr=False
            )

            if not success:
                return False, f"Failed to update workspace file: {output}"

            logger.info(
                f"Added map reference to workspace with full path: {map_file_path}"
            )
            return True, f"Map {map_name} created successfully in workspace {workspace}"

        except Exception as e:
            logger.error(f"Failed to create map {map_name}: {e}", exc_info=True)
            return False, f"Failed to create map: {e}"

    def start_devices_from_map(
        self, map_full_path: str, devices_names: list
    ) -> Tuple[bool, str]:
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
                    messages.append(
                        f"Started {device_ip}: {output}"
                        if output
                        else f"Started {device_ip}"
                    )

            # Return success if all devices started successfully
            all_success = all("Failed" not in msg for msg in messages)
            return all_success, "\n".join(messages)

        except Exception as e:
            logger.error(f"Failed to start device(s): {e}", exc_info=True)
            return False, f"Failed to start device(s): {e}"

    def stop_devices_from_map(
        self, map_full_path: str, devices_names: list
    ) -> Tuple[bool, str]:
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
                    messages.append(
                        f"Stopped {device_ip}: {output}"
                        if output
                        else f"Stopped {device_ip}"
                    )

            # Return success if all devices stopped successfully
            all_success = all("Failed" not in msg for msg in messages)
            return all_success, "\n".join(messages)

        except Exception as e:
            logger.error(f"Failed to stop device(s): {e}", exc_info=True)
            return False, f"Failed to stop device(s): {e}"

    def create_device(
        self, device_ip: str, raw_xml_content: str, map_path: str
    ) -> Tuple[bool, str]:
        """Create (or start existing) simulator device on the sapro server using SSH.

        Special handling for empty maps:
        - Empty map: Add device XML directly to map file, then start map
        - Non-empty map: Use normal adddev command

        Workflow:
        1. Check if device already exists
        2. If exists: start it
        3. If not exists:
           a. Check if map is empty (no <Device> tags)
           b. If empty: insert device XML into map file
           c. If not empty: use adddev command
        4. Start map if needed

        Args:
            device_ip: Device IP address
            raw_xml_content: Device configuration XML
            map_path: Full map path (e.g., /opt/sapro/map/default.map)

        Returns:
            (success, message)
        """
        try:
            ssh_client = get_sapro_ssh_client()

            # Extract workspace and map_name from path
            workspace, map_name = self._extract_workspace_and_map_name(map_path)

            # Check if workspace has any maps and get map status
            try:
                all_maps = self.get_all_maps(workspace=workspace)
            except Exception as e:
                logger.error(f"Failed to get maps from workspace '{workspace}': {e}")
                return False, f"Cannot access workspace '{workspace}': {e}"

            if not all_maps:
                logger.warning(f"Workspace '{workspace}' has no maps defined.")
                return (
                    False,
                    f"Workspace '{workspace}' has no maps. Cannot add device '{device_ip}'.",
                )

            # Find the map to get status
            map_info = next((m for m in all_maps if m["name"] == map_name), None)
            if not map_info:
                return False, f"Map '{map_name}' not found in workspace '{workspace}'"

            was_map_running = map_info["status"] == "running"

            # Step 1: Read map file to check if it's empty BEFORE doing anything else
            read_map_cmd = f"cat {map_path}"
            success, map_content = ssh_client.execute_command(
                read_map_cmd, check_stderr=False
            )

            if not success:
                return False, f"Failed to read map file: {map_content}"

            # Check if map is empty (no <Device> tags)
            is_empty_map = "<Device>" not in map_content
            logger.info(f"Map {map_name} is {'empty' if is_empty_map else 'not empty'}")

            # CRITICAL: If map is empty AND running, we must STOP it first before writing
            # because Sapro caches the map content in memory when running
            if is_empty_map and was_map_running:
                logger.info(f"Map {map_name} is empty but running, stopping it first to write device")
                stop_ok, stop_msg = self.stop_map_and_wait(map_path)
                if not stop_ok:
                    return False, f"Failed to stop empty map {map_name}: {stop_msg}"
                was_map_running = False  # Update status after stopping

            # If map is not empty and not running, start it to check device list
            if not is_empty_map and not was_map_running:
                logger.info(f"Map {map_name} is not running, starting it")
                ok, msg = self.start_map_and_wait(map_path)
                if not ok:
                    return False, f"Failed to start map {map_name}: {msg}"
                was_map_running = True  # Update status after starting

            # Check if device already exists (only if map is not empty)
            device_exists = False
            device_status = None

            if not is_empty_map:
                devlist_cmd = f"/opt/sapro/bin/sapcnsl -m {map_path} -c devlist"
                logger.debug(f"Checking if device {device_ip} exists: {devlist_cmd}")

                success, output = ssh_client.execute_command(
                    devlist_cmd, check_stderr=False
                )

                if success and output:
                    # Parse devlist output to check if device exists and get its status
                    lines = output.split("\n")
                    in_table = False
                    for line in lines:
                        # Skip header separators
                        if line.strip().startswith("---"):
                            in_table = True
                            continue

                        # Stop at footer separator
                        if in_table and line.strip().startswith("---"):
                            break

                        # Skip non-table lines
                        if not in_table or not line.strip():
                            continue

                        parts = line.split()
                        if parts:
                            device_name = parts[0]
                            if "//" in device_name:
                                ip = device_name.split("//")[0]
                            else:
                                ip = device_name

                            if ip == device_ip:
                                device_exists = True
                                # Get device status from second column (R=running, ' '=stopped, etc.)
                                if len(parts) > 1:
                                    device_status = parts[1]
                                break

                if device_exists:
                    # Device already exists - check status and start if needed
                    if device_status == "R":
                        logger.info(f"Device {device_ip} already exists and is running")
                        return (
                            True,
                            f"Simulator {device_ip} already exists and is running",
                        )
                    else:
                        # Device exists but not running - start it
                        logger.info(
                            f"Device {device_ip} exists but not running (status: {device_status}), starting it"
                        )
                        ok, msg = self.start_devices_from_map(map_path, [device_ip])
                        if ok:
                            return True, f"Simulator {device_ip} was started"
                        return False, f"Simulator {device_ip} failed to start: {msg}"

            # Device doesn't exist - need to add it
            logger.info(f"Device {device_ip} doesn't exist, adding to map {map_name}")

            # Get map directory from LocalMappedDir (not by parsing map path)
            try:
                map_directory = self._get_local_map_dir(workspace=workspace)
            except Exception as e:
                logger.error(f"Failed to get map directory: {e}")
                return False, f"Failed to get map directory: {e}"

            if is_empty_map:
                # EMPTY MAP: Add device XML directly into map file
                logger.info(
                    f"Adding first device to empty map {map_name} by editing map file"
                )

                # Insert device XML before closing </DeviceMap> tag
                if "</DeviceMap>" not in map_content:
                    return False, "Map file format invalid (no </DeviceMap> tag)"

                # Extract only the <Device>...</Device> section from raw_xml_content
                # The template may contain full <DeviceMap> wrapper or just <Device> tags
                device_xml = raw_xml_content.strip()

                # If the XML contains <DeviceMap> wrapper, extract only the <Device> section
                if "<DeviceMap" in device_xml and "</DeviceMap>" in device_xml:
                    # Find the content between <DeviceMap...> and </DeviceMap>
                    start_idx = (
                        device_xml.find(">") + 1
                    )  # After first > in <DeviceMap...>
                    end_idx = device_xml.rfind("</DeviceMap>")
                    device_xml = device_xml[start_idx:end_idx].strip()

                # Now insert only the Device section before </DeviceMap>
                updated_map_content = map_content.replace(
                    "</DeviceMap>", f"\n{device_xml}\n</DeviceMap>"
                )

                # Write updated map file
                escaped_content = updated_map_content.replace("'", "'\\''")
                write_map_cmd = f"echo '{escaped_content}' > {map_path}"
                success, output = ssh_client.execute_command(
                    write_map_cmd, check_stderr=False
                )

                if not success:
                    return False, f"Failed to update map file: {output}"

                logger.info(f"Added device {device_ip} directly to map file {map_path}")

                # Start map after adding device to empty map
                logger.info(f"Starting map {map_name} after adding device...")
                start_ok, start_msg = self.start_map_and_wait(map_path)
                if not start_ok:
                    return (
                        False,
                        f"Device {device_ip} added but failed to start map: {start_msg}",
                    )
                logger.info(f"Map {map_name} started successfully")
            else:
                # NON-EMPTY MAP: Use normal adddev command
                logger.info(f"Adding device to non-empty map using adddev command")

                # If map is stopped, start it first before using adddev
                if not was_map_running:
                    logger.info(
                        f"Map {map_name} is stopped with existing devices, starting it first..."
                    )
                    start_ok, start_msg = self.start_map_and_wait(map_path)
                    if not start_ok:
                        return (
                            False,
                            f"Failed to start map before adding device: {start_msg}",
                        )
                    logger.info(f"Map {map_name} started successfully")

                # Create device file path
                new_device_file_path = f"{map_directory}{device_ip}.map"

                # Write device file to server using SSH
                device_file_content = raw_xml_content.strip()
                escaped_content = device_file_content.replace("'", "'\\''")
                write_device_file_cmd = (
                    f"echo '{escaped_content}' > {new_device_file_path}"
                )
                success, output = ssh_client.execute_command(
                    write_device_file_cmd, check_stderr=False
                )

                if not success:
                    return False, f"Failed to create device file: {output}"

                logger.info(f"Created device file: {new_device_file_path}")

                # Add device to map using SSH adddev command (map is now running)
                # Note: Commands with -p flag connect to Sapro daemon - no stdout output expected
                adddev_cmd = f"/opt/sapro/bin/sapcnsl -p {self.sapro_port} -m {map_path} -c adddev -f {new_device_file_path}"
                logger.info(f"Executing adddev command: {adddev_cmd}")

                # Adddev can take time to process - use longer timeout (60 seconds)
                success, output = ssh_client.execute_command(
                    adddev_cmd, timeout=60, check_stderr=False
                )

                if not success:
                    logger.error(f"Adddev command failed: {output}")
                    return False, f"Failed to add device to map: {output}"

                logger.info(f"Adddev command completed, starting device {device_ip}...")

                # Start the newly added device (map is already running)
                ok, msg = self.start_devices_from_map(map_path, [device_ip])
                if not ok:
                    logger.warning(f"Start device command returned: {msg}")

                # Verify device is running using devlist (with retry loop up to 1 minute)
                logger.info(f"Verifying device {device_ip} is running...")
                max_wait = 60  # 1 minute
                check_interval = 5  # Check every 5 seconds
                elapsed = 0
                device_running = False

                while elapsed < max_wait:
                    devlist_cmd = f"/opt/sapro/bin/sapcnsl -m {map_path} -c devlist"
                    dev_success, dev_output = ssh_client.execute_command(devlist_cmd, check_stderr=False)

                    if dev_success and dev_output:
                        # Check if device appears with status 'R' (Running)
                        # Device format: "50.50.130.6//161         R"
                        for line in dev_output.splitlines():
                            if device_ip in line:
                                parts = line.split()
                                if len(parts) >= 2 and parts[1] == 'R':
                                    device_running = True
                                    logger.info(f"Device {device_ip} verified running (status: R)")
                                    break
                                else:
                                    logger.debug(f"Device {device_ip} found but status: {parts[1] if len(parts) >= 2 else 'unknown'}")

                        if device_running:
                            break

                    logger.debug(f"Device {device_ip} not running yet, waiting... ({elapsed}/{max_wait}s)")
                    time.sleep(check_interval)
                    elapsed += check_interval

                if not device_running:
                    # Check if device is in list but not running - try starting it again
                    logger.warning(f"Device {device_ip} not running after {max_wait}s, checking if it exists in devlist...")
                    devlist_cmd = f"/opt/sapro/bin/sapcnsl -m {map_path} -c devlist"
                    dev_success, dev_output = ssh_client.execute_command(devlist_cmd, check_stderr=False)

                    device_in_list = False
                    if dev_success and dev_output:
                        for line in dev_output.splitlines():
                            if device_ip in line:
                                device_in_list = True
                                parts = line.split()
                                current_status = parts[1] if len(parts) >= 2 else 'unknown'
                                logger.info(f"Device {device_ip} found in devlist with status: {current_status}")
                                break

                    if device_in_list:
                        logger.info(f"Device {device_ip} exists but not running, attempting to start again...")
                        ok, msg = self.start_devices_from_map(map_path, [device_ip])
                        logger.info(f"Retry start result: {msg}")

                        # Wait 30 seconds and check one more time
                        logger.info(f"Waiting 30s for device {device_ip} to start...")
                        time.sleep(30)

                        devlist_cmd = f"/opt/sapro/bin/sapcnsl -m {map_path} -c devlist"
                        dev_success, dev_output = ssh_client.execute_command(devlist_cmd, check_stderr=False)

                        if dev_success and dev_output:
                            for line in dev_output.splitlines():
                                if device_ip in line:
                                    parts = line.split()
                                    if len(parts) >= 2 and parts[1] == 'R':
                                        logger.info(f"Device {device_ip} now running after retry")
                                        device_running = True
                                        break
                                    else:
                                        logger.error(f"Device {device_ip} still not running, status: {parts[1]}")

                    if not device_running:
                        return False, f"Device {device_ip} added but not running after retry"

                # Clean up temporary device file
                cleanup_cmd = f"rm -f {new_device_file_path}"
                ssh_client.execute_command(cleanup_cmd, check_stderr=False)
                logger.info(f"Cleaned up device file: {new_device_file_path}")

            return True, f"Device {device_ip} created and added to map {map_path}"

        except Exception as e:
            logger.error(f"Failed to create device {device_ip}: {e}", exc_info=True)
            return False, f"Failed to create device {device_ip}: {str(e)}"

    def update_device(
        self, device_ip: str, raw_xml_content: str, map_path: str
    ) -> Tuple[bool, str]:
        """Update an existing simulator device by deleting and re-creating it.

        Uses delete_device() + create_device() to avoid touching the map file directly.

        Args:
            device_ip: Device IP address
            raw_xml_content: New device configuration XML
            map_path: Full map path (e.g., /opt/sapro/map/default.map)

        Returns:
            (success, message)
        """
        try:
            # Extract map_name from path for logging
            _, map_name = self._extract_workspace_and_map_name(map_path)

            logger.info(f"Updating device {device_ip} in map {map_name}")

            # Step 1: Delete device from map
            logger.info(f"Deleting device {device_ip} from map {map_name}")
            success, message = self.delete_device(device_ip, map_path)
            if not success:
                logger.warning(f"Delete device warning (continuing anyway): {message}")

            # Sleep briefly to allow sapro to process the deletion before re-adding
            time.sleep(4)

            # Step 2: Create device with new configuration
            logger.info(f"Creating device {device_ip} with updated configuration")
            return self.create_device(device_ip, raw_xml_content, map_path)

        except Exception as e:
            logger.error(f"Failed to update device {device_ip}: {e}", exc_info=True)
            return False, f"Failed to update device {device_ip}: {str(e)}"

    def update_device_fields(
        self, device_ip: str, fields: Dict[str, str], map_path: str
    ) -> Tuple[bool, str]:
        """Update specific fields of a device in the map file.

        Flow:
        1. Stop the device
        2. Read the map file
        3. Find the device's <Device>...</Device> block by its Name attribute
        4. Update the specified fields within that block using regex
        5. Write the updated map file back
        6. Start the device

        Args:
            device_ip: Device IP address (used to locate the device block)
            fields: Dict of field name -> new value (e.g. {"MibFile": "/opt/sapro/cmf/new.cmf"})
            map_path: Full map path (e.g., /opt/sapro/map/default.map)

        Returns:
            (success, message)
        """
        map_lock = self._get_map_lock(map_path)
        acquired = map_lock.acquire(timeout=600)
        if not acquired:
            return False, f"Timed out waiting for map file lock (another operation is in progress): {map_path}"

        try:
            ssh_client = get_sapro_ssh_client()
            _, map_name = self._extract_workspace_and_map_name(map_path)

            # Step 1: Stop the device
            logger.info(f"Stopping device {device_ip} before field update")
            stop_ok, stop_msg = self.stop_devices_from_map(map_path, [device_ip])
            if not stop_ok:
                logger.warning(f"Stop device {device_ip} returned: {stop_msg}")

            # Step 2: Read the map file
            read_cmd = f"cat {map_path}"
            success, map_content = ssh_client.execute_command(read_cmd, check_stderr=False)
            if not success:
                return False, f"Failed to read map file: {map_content}"

            # Step 3: Find the device block and update fields
            device_block_pattern = re.compile(r'(<Device>.*?</Device>)', re.DOTALL)
            name_pattern = re.compile(rf'Name\s*=\s*"{re.escape(device_ip)}"')

            device_found = False

            def replace_block(match: re.Match) -> str:
                nonlocal device_found
                block = match.group(1)
                if not name_pattern.search(block):
                    return block
                device_found = True
                for field_name, new_value in fields.items():
                    field_pattern = re.compile(rf'(\b{re.escape(field_name)}\s*=\s*")[^"]*(")')
                    block = field_pattern.sub(rf'\g<1>{new_value}\g<2>', block)
                return block

            updated_content = device_block_pattern.sub(replace_block, map_content)

            if not device_found:
                return False, f"Device {device_ip} not found in map file {map_path}"

            # Step 4: Write updated map file
            escaped_content = updated_content.replace("'", "'\\''")
            write_cmd = f"echo '{escaped_content}' > {map_path}"
            success, output = ssh_client.execute_command(write_cmd, check_stderr=False)
            if not success:
                return False, f"Failed to write map file: {output}"

            logger.info(f"Updated fields {list(fields.keys())} for device {device_ip} in map {map_name}")

            # Step 5: Start the device
            logger.info(f"Starting device {device_ip} after field update")
            start_ok, start_msg = self.start_devices_from_map(map_path, [device_ip])
            if not start_ok:
                return False, f"Fields updated in map file but failed to start device: {start_msg}"

            return True, f"Device {device_ip} fields updated and device started successfully"

        except Exception as e:
            logger.error(f"Failed to update device fields for {device_ip}: {e}", exc_info=True)
            return False, f"Failed to update device fields: {str(e)}"

        finally:
            map_lock.release()

    def delete_device(self, device_ip: str, map_path: str) -> Tuple[bool, str]:
        """Delete a device from the specified map using SSH.

        Args:
            device_ip: IP/name of the device to delete
            map_path: Full map path (e.g., /opt/sapro/map/default.map)

        Returns:
            (success, message)
        """

        try:
            # First stop the device if it's running to ensure clean deletion
            stop_device_from_map_ok, stop_device_msg = self.stop_devices_from_map(map_path, [device_ip])
            time.sleep(1) # Wait briefly to allow sapro to process the stop command before deletion
            
            if not stop_device_from_map_ok:
                logger.warning(f"Failed to stop device {device_ip} before deletion: {stop_device_msg}")
            
            ssh_client = get_sapro_ssh_client()

            # Execute delete command via SSH
            cmd = f"/opt/sapro/bin/sapcnsl -m {map_path} -c deldev -d {device_ip}"

            logger.debug(f"Executing delete device command via SSH: {cmd}")
            success, output = ssh_client.execute_command(cmd, timeout=60, check_stderr=False)

            if not success:
                return False, f"SSH delete command failed: {output}"

            # Analyze output to determine success
            if "PACKET_EVALUATED: Device deleted." in output:
                return True, output or "Device deleted successfully"
            else:
                return False, f"Unexpected delete output: {output}"

        except Exception as exc:
            logger.error(f"Failed to execute SSH delete command: {exc}", exc_info=True)
            return False, f"Failed to execute SSH delete command: {exc}"


# Module-level singleton factory
_sapro_handler: Optional[SaproCommunicationHandler] = None


def get_sapro_handler() -> SaproCommunicationHandler:
    """Return a singleton SaproCommunicationHandler.

    On first call the handler is created using configuration values from
    `backend.app.utils.config.settings` (reads `SAPRO_IP`, `SAPRO_PORT`).

    Uses SSH-only communication - no API connection.
    Default map directory is hardcoded to /opt/sapro/map/
    """
    global _sapro_handler
    if _sapro_handler is None:
        sapro_ip = settings.SAPRO_IP
        sapro_port = settings.SAPRO_PORT
        handler = SaproCommunicationHandler(sapro_ip, int(sapro_port))
        # SSH-only communication - no API connection needed
        _sapro_handler = handler
    return _sapro_handler
