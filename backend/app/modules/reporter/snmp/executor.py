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
    import paramiko

    # In production, SSH to localhost (the host machine)
    # In development, SSH to configured remote host
    ssh_host = "localhost" if settings.ENVIRONMENT == "production" else settings.SAPRO_SSH_HOST
    ssh_target = f"{settings.SAPRO_SSH_USER}@{ssh_host}"

    try:
        logger.info(f"Executing Sapro command via SSH to {ssh_host}: {command[:100]}")

        client = None
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            logger.debug(f"Connecting to {ssh_host} as {settings.SAPRO_SSH_USER}")
            client.connect(
                ssh_host,
                username=settings.SAPRO_SSH_USER,
                password=settings.SAPRO_SSH_PASSWORD,
                timeout=timeout,
            )

            logger.debug(f"Executing via SSH: {command[:100]}")
            stdin, stdout, stderr = client.exec_command(command)

            output = stdout.read().decode() + stderr.read().decode()
            exit_status = stdout.channel.recv_exit_status()
            success = exit_status == 0

            logger.debug(f"SSH command exit status: {exit_status}")

        except paramiko.AuthenticationException as e:
            error_msg = f"SSH auth failed for {ssh_target}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

        except paramiko.SSHException as e:
            error_msg = f"SSH error to {ssh_target}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

        except OSError as e:
            error_msg = f"Network error to {ssh_target}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

        finally:
            if client:
                client.close()
                logger.debug("SSH closed")

        if success:
            logger.info(f"Command succeeded. Output: {len(output)} chars")
            logger.debug(f"Output: {output[:500]}")
        else:
            logger.warning(f"Command failed. Output: {output[:500]}")

        return success, output

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

    except Exception as e:
        error_msg = f"Unexpected error executing Sapro command: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

