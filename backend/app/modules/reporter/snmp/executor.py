"""
Execute Sapro commands via SSH.

The backend runs with network_mode: host to bind to simulator IPs for IRP sends,
but uses SSH to execute Sapro commands on the host (sapcnsl, etc.).
"""

import subprocess
import logging
from typing import Tuple

from backend.app.utils.config import settings

logger = logging.getLogger(__name__)


def execute_sapro_command(command: str, timeout: int = 30) -> Tuple[bool, str]:
    """
    Execute Sapro command via SSH to localhost (production) or remote host (development).

    In production with network_mode: host, the backend shares the host's network
    (needed for binding simulator IPs for IRP), but executes Sapro commands via
    SSH to localhost to access the host's Sapro installation.

    Args:
        command: The command to execute on the Sapro system
        timeout: Command timeout in seconds (default: 30)

    Returns:
        Tuple of (success: bool, output: str)

    Raises:
        subprocess.TimeoutExpired: If command execution exceeds timeout
        Exception: For SSH connection errors
    """
    from backend.app.utils.sapro_ssh import get_sapro_ssh_client

    # The centralized SSH client handles host selection based on environment
    ssh_client = get_sapro_ssh_client()
    ssh_host = ssh_client.host
    ssh_target = f"{settings.SAPRO_SSH_USER}@{ssh_host}"

    try:
        logger.info(f"Executing Sapro command via SSH to {ssh_host}: {command[:100]}")

        # Use centralized SSH client with connection pooling
        success, output = ssh_client.execute_command(command, timeout=timeout, check_stderr=False)

        logger.debug(f"SSH command result: success={success}, output length={len(output)} chars")

        if success:
            logger.info(f"Command succeeded. Output: {len(output)} chars")
            logger.debug(f"Output: {output[:500]}")
        else:
            logger.warning(f"Command failed. Output: {output[:500]}")

        return success, output

    except Exception as e:
        error_msg = f"Unexpected error executing Sapro command: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

