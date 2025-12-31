"""
Device Driver utility for managing JAR files and deployment to CyberController.

Provides functions for:
- Parsing device driver filenames
- Listing existing drivers from filesystem
- Saving uploaded drivers
- Deploying drivers to CyberController via SSH
- Batch deployment with error handling
"""
import os
import re
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile

from backend.app.utils.logger import logger
from backend.app.utils.cc_ssh import get_cc_ssh_client

# Determine base path (works in both dev and Docker)
# In Docker: /app/resources/
# In Dev: <project_root>/backend/resources/
if os.path.exists("/app/resources"):
    # Docker environment
    DEVICE_DRIVER_STORAGE_PATH = "/app/resources/device_drivers"
    DEVICE_DRIVER_SCRIPT_PATH = "/app/resources/scripts/upload_DD.sh"
else:
    # Development environment - find project root
    current_file = Path(__file__)  # backend/app/utils/device_driver.py
    backend_root = current_file.parent.parent.parent  # Go up to backend/
    DEVICE_DRIVER_STORAGE_PATH = str(backend_root / "app" / "resources" / "device_drivers")
    DEVICE_DRIVER_SCRIPT_PATH = str(backend_root / "app" / "resources" / "scripts" / "upload_DD.sh")

CC_STORAGE_PATH = "/opt/radware/storage"

logger.info(f"Device driver storage path: {DEVICE_DRIVER_STORAGE_PATH}")
logger.info(f"Device driver script path: {DEVICE_DRIVER_SCRIPT_PATH}")


def parse_driver_filename(filename: str) -> Optional[Dict[str, str]]:
    """Parse device driver filename to extract metadata.

    Expected format: {DeviceType}-{Version}-DD-{DDVersion}.jar
    Examples:
        - DefensePro-10.6.0.0-DD-1.00-17.jar
        - Alteon-32.6.5.0-DD-1.00-10.jar
        - DefensePro-8.30.0.0-DD-1.00-7.jar

    Args:
        filename: Device driver JAR filename

    Returns:
        Dict with device_type, device_version, dd_version if valid, None otherwise

    Examples:
        >>> parse_driver_filename("DefensePro-10.6.0.0-DD-1.00-17.jar")
        {'device_type': 'DefensePro', 'device_version': '10.6.0.0', 'dd_version': '1.00-17'}
    """
    # Pattern: {Type}-{Version}-DD-{DDVersion}.jar
    # Type: Any characters (non-greedy)
    # Version: X.X.X or X.X.X.X format
    # DDVersion: Any characters until .jar
    pattern = r"^(.+?)-(\d+\.\d+\.\d+(?:\.\d+)?)-DD-(.+)\.jar$"
    match = re.match(pattern, filename)

    if not match:
        logger.warning(f"Invalid device driver filename format: {filename}")
        return None

    return {
        "device_type": match.group(1),
        "device_version": match.group(2),
        "dd_version": match.group(3),
    }


def list_existing_drivers() -> List[str]:
    """List all JAR files in the device_drivers directory.

    Scans the DEVICE_DRIVER_STORAGE_PATH directory for .jar files.
    Returns:
        List of JAR filenames (not full paths)

    Examples:
        >>> list_existing_drivers()
        ['DefensePro-10.6.0.0-DD-1.00-17.jar', 'Alteon-32.6.5.0-DD-1.00-10.jar']
    """
    try:
        driver_path = Path(DEVICE_DRIVER_STORAGE_PATH)
        if not driver_path.exists():
            logger.warning(f"Device driver directory not found: {DEVICE_DRIVER_STORAGE_PATH}")
            return []

        jar_files = [f.name for f in driver_path.glob("*.jar")]
        logger.info(f"Found {len(jar_files)} device driver JAR files in {DEVICE_DRIVER_STORAGE_PATH}")
        return sorted(jar_files)

    except Exception as e:
        logger.error(f"Failed to list device drivers: {e}", exc_info=True)
        return []


def match_driver_filename(device_type: str, device_version: str) -> Optional[str]:
    """Find matching device driver filename for given type and version.

    Searches existing drivers for a match with the specified device type and version.
    Args:
        device_type: Device type (e.g., "DefensePro", "Alteon")
        device_version: Device version (e.g., "10.6.0.0")

    Returns:
        Matching JAR filename if found, None otherwise

    Examples:
        >>> match_driver_filename("DefensePro", "10.6.0.0")
        'DefensePro-10.6.0.0-DD-1.00-17.jar'
    """
    existing_drivers = list_existing_drivers()

    for filename in existing_drivers:
        parsed = parse_driver_filename(filename)
        if parsed and parsed["device_type"] == device_type and parsed["device_version"] == device_version:
            logger.debug(f"Found matching driver: {filename} for {device_type} {device_version}")
            return filename

    logger.warning(f"No matching driver found for {device_type} {device_version}")
    return None


async def save_uploaded_driver(
    file: UploadFile,
    uploaded_by: Optional[str] = None
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Save uploaded device driver JAR file to filesystem.

    Validates filename format, checks for duplicates, and saves to storage directory.
    Args:
        file: Uploaded JAR file from FastAPI
        uploaded_by: Username of person uploading (optional)

    Returns:
        Tuple of:
        - success (bool): True if saved successfully
        - message (str): Success or error message
        - metadata (dict): Driver metadata if successful, None otherwise

    Examples:
        >>> await save_uploaded_driver(file, "admin@example.com")
        (True, "Driver uploaded successfully", {...metadata...})
    """
    try:
        filename = file.filename
        if not filename:
            return False, "No filename provided", None

        # Validate filename format
        parsed = parse_driver_filename(filename)
        if not parsed:
            return False, f"Invalid filename format. Expected: DeviceType-Version-DD-DDVersion.jar", None

        # Check if file already exists
        file_path = os.path.join(DEVICE_DRIVER_STORAGE_PATH, filename)
        if os.path.exists(file_path):
            return False, f"Driver already exists: {filename}", None

        # Ensure directory exists
        os.makedirs(DEVICE_DRIVER_STORAGE_PATH, exist_ok=True)

        # Save file
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        file_size = len(content)
        logger.info(f"Saved device driver: {filename} ({file_size} bytes)")

        # Prepare metadata for MongoDB
        metadata = {
            "filename": filename,
            "device_type": parsed["device_type"],
            "device_version": parsed["device_version"],
            "dd_version": parsed["dd_version"],
            "file_path": file_path,
            "file_size": file_size,
            "upload_date": datetime.now(timezone.utc),
            "uploaded_by": uploaded_by,
            "status": "available",
        }

        return True, "Driver uploaded successfully", metadata

    except Exception as e:
        logger.error(f"Failed to save uploaded driver: {e}", exc_info=True)
        return False, f"Failed to save driver: {str(e)}", None


def deploy_driver_to_cc(
    cc_ip: str,
    driver_filename: str,
    timeout: int = 120
) -> Tuple[bool, str]:
    """Deploy a device driver to CyberController via SSH.

    Workflow:
    1. Copy upload_DD.sh script to CC at /opt/radware/storage/
    2. Copy JAR file to CC at /opt/radware/storage/
    3. Make script executable (chmod +x)
    4. Execute: /opt/radware/storage/upload_DD.sh <jar_filename>
    5. Parse JSON output for success/error/exists

    Args:
        cc_ip: CyberController IP address
        driver_filename: JAR filename (e.g., DefensePro-10.6.0.0-DD-1.00-17.jar)
        timeout: SSH command timeout in seconds (default: 120 for 2 minutes)

    Returns:
        Tuple of (success: bool, message: str)

    Expected script output formats:
        - Success: {"status":"ok","message":"M_01472: Upload of device driver succeeded."}
        - Exists: {"status":"error","message":"M_00777: The device driver ... already exists in the database."}
        - Error: {"status":"error","message":"<any other error>"}
    """
    try:
        logger.info(f"Deploying device driver {driver_filename} to CC {cc_ip}")

        # Get CC SSH client (uses default root/radware credentials)
        ssh_client = get_cc_ssh_client(cc_ip=cc_ip)

        # 1. Upload upload_DD.sh script to CC
        local_script = DEVICE_DRIVER_SCRIPT_PATH
        remote_script = f"{CC_STORAGE_PATH}/upload_DD.sh"

        logger.debug(f"Uploading script: {local_script} -> {remote_script}")
        success, msg = ssh_client.upload_file(local_script, remote_script)
        if not success:
            return False, f"Failed to upload script: {msg}"

        # Convert Windows line endings to Unix (remove \r characters)
        logger.debug("Converting script line endings to Unix format")
        success, output = ssh_client.execute_command(
            f"sed -i 's/\\r$//' {remote_script}",
            check_stderr=False
        )
        if not success:
            logger.warning(f"Line ending conversion warning (continuing anyway): {output}")

        # 2. Upload JAR file to CC
        local_jar = os.path.join(DEVICE_DRIVER_STORAGE_PATH, driver_filename)
        remote_jar = f"{CC_STORAGE_PATH}/{driver_filename}"

        if not os.path.exists(local_jar):
            return False, f"Local JAR file not found: {local_jar}"

        logger.debug(f"Uploading JAR: {local_jar} -> {remote_jar}")
        success, msg = ssh_client.upload_file(local_jar, remote_jar)
        if not success:
            return False, f"Failed to upload JAR: {msg}"

        # 3. Make script executable
        logger.debug("Making script executable")
        success, output = ssh_client.execute_command(f"chmod +x {remote_script}", check_stderr=False)
        if not success:
            logger.warning(f"chmod warning (continuing anyway): {output}")

        # 4. Execute upload script with absolute path to JAR
        remote_jar_path = f"{CC_STORAGE_PATH}/{driver_filename}"
        cmd = f"{remote_script} {remote_jar_path}"
        logger.info(f"Executing: {cmd} (timeout: {timeout}s)")

        success, output = ssh_client.execute_command(cmd, timeout=timeout, check_stderr=False)

        if not success:
            return False, f"Script execution failed: {output}"

        # 5. Parse JSON output
        logger.debug(f"Script output: {output}")

        import json
        try:
            result = json.loads(output)
            status = result.get("status", "").lower()
            message = result.get("message", "")

            if status == "ok":
                # Success: M_01472
                logger.info(f"Driver deployed successfully: {driver_filename}")
                return True, message

            elif "already exists" in message.lower():
                # Already exists: M_00777 - treat as success with info message
                logger.info(f"Driver already exists on CC: {driver_filename}")
                return True, f"Already exists: {message}"

            else:
                # Error
                logger.error(f"Driver deployment failed: {message}")
                return False, message

        except json.JSONDecodeError:
            # Script output is not valid JSON - treat as error
            logger.error(f"Unexpected script output (not JSON): {output}")
            return False, f"Unexpected script output: {output}"

    except Exception as e:
        logger.error(f"Failed to deploy driver {driver_filename}: {e}", exc_info=True)
        return False, f"Deployment error: {str(e)}"


def deploy_multiple_drivers(
    cc_ip: str,
    driver_filenames: List[str]
) -> Dict[str, Any]:
    """Deploy multiple device drivers to CC sequentially.

    Executes deployment one-by-one, continues on failure, and returns summary.
    Args:
        cc_ip: CyberController IP address
        driver_filenames: List of JAR filenames to deploy

    Returns:
        Dict with:
        - total (int): Total number of drivers attempted
        - succeeded (int): Number of successful deployments
        - failed (int): Number of failed deployments
        - results (List[Dict]): Per-driver results with filename, success, message

    Examples:
        >>> deploy_multiple_drivers("172.17.154.218", ["DefensePro-10.6.0.0-DD-1.00-17.jar"])
        {
            'total': 1,
            'succeeded': 1,
            'failed': 0,
            'results': [{'filename': '...', 'success': True, 'message': '...'}]
        }
    """
    results = []
    succeeded = 0
    failed = 0

    for i, filename in enumerate(driver_filenames, 1):
        logger.info(f"Deploying driver {i}/{len(driver_filenames)}: {filename}")

        success, message = deploy_driver_to_cc(cc_ip, filename)

        results.append({
            "filename": filename,
            "success": success,
            "message": message
        })

        if success:
            succeeded += 1
        else:
            failed += 1

    summary = {
        "total": len(driver_filenames),
        "succeeded": succeeded,
        "failed": failed,
        "results": results
    }

    logger.info(
        f"Deployment complete: {succeeded}/{len(driver_filenames)} succeeded, "
        f"{failed}/{len(driver_filenames)} failed"
    )

    return summary


__all__ = [
    "parse_driver_filename",
    "list_existing_drivers",
    "match_driver_filename",
    "save_uploaded_driver",
    "deploy_driver_to_cc",
    "deploy_multiple_drivers",
]
