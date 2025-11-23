"""
Execute Sapro commands either via SSH (development/containerized) or direct subprocess (production on host).

This module provides command execution functionality that adapts based on the
environment setting and whether we're running in a Docker container:
- Development: Always use SSH
- Production in Docker: Use SSH to localhost (host machine)
- Production on host: Use subprocess directly
"""

import subprocess
import logging
import os
from typing import Tuple

from backend.app.utils.config import settings

logger = logging.getLogger(__name__)


def _is_running_in_container() -> bool:
    """Check if we're running inside a Docker container."""
    return os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv')


def execute_sapro_command(command: str, timeout: int = 30) -> Tuple[bool, str]:
    """
    Execute Sapro command on DEV (SSH) or PROD (subprocess or SSH).

    Args:
        command: The command to execute on the Sapro system
        timeout: Command timeout in seconds (default: 30)

    Returns:
        Tuple of (success: bool, output: str)
        - success: True if command executed successfully (returncode 0)
        - output: Combined stdout and stderr from the command

    Raises:
        subprocess.TimeoutExpired: If command execution exceeds timeout
        subprocess.SubprocessError: If subprocess execution fails
        Exception: For other unexpected errors during execution
    """
    # Determine if we should use SSH
    use_ssh = settings.ENVIRONMENT == "development" or _is_running_in_container()

    try:
        logger.info(
            f"Executing Sapro command in {settings.ENVIRONMENT} environment "
            f"(container={_is_running_in_container()}, use_ssh={use_ssh}): {command[:100]}"
        )

        if use_ssh:
            # SSH to Sapro host (development or from container to host)
            import paramiko

            # In production container, SSH to localhost (the host machine)
            # In development, SSH to configured SAPRO_SSH_HOST
            ssh_host = "localhost" if settings.ENVIRONMENT == "production" and _is_running_in_container() else settings.SAPRO_SSH_HOST
            ssh_target = f"{settings.SAPRO_SSH_USER}@{ssh_host}"
            logger.debug(f"Using paramiko SSH connection to {ssh_target}")

            client = None
            try:
                # Create SSH client
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                # Connect to the Sapro host
                logger.debug(f"Connecting to {ssh_host} as {settings.SAPRO_SSH_USER}")
                client.connect(
                    ssh_host,
                    username=settings.SAPRO_SSH_USER,
                    password=settings.SAPRO_SSH_PASSWORD,
                    timeout=timeout,
                )

                # Execute command
                logger.debug(f"Executing command via SSH: {command[:100]}")
                stdin, stdout, stderr = client.exec_command(command)

                # Get output
                output = stdout.read().decode() + stderr.read().decode()

                # Check success based on exit status
                exit_status = stdout.channel.recv_exit_status()
                success = exit_status == 0

                logger.debug(f"SSH command completed with exit status: {exit_status}")

            except paramiko.AuthenticationException as e:
                error_msg = f"SSH authentication failed for {ssh_target}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return False, error_msg

            except paramiko.SSHException as e:
                error_msg = f"SSH connection error to {ssh_target}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return False, error_msg

            except OSError as e:
                error_msg = f"Network error connecting to {ssh_target}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return False, error_msg

            finally:
                # Always close the SSH client
                if client:
                    client.close()
                    logger.debug("SSH connection closed")

        else:
            # Direct subprocess (running ON Sapro host, NOT in container)
            logger.debug("Executing command directly on Sapro host via subprocess")

            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            success = result.returncode == 0
            output = result.stdout + result.stderr

        if success:
            logger.info(f"Command executed successfully. Output length: {len(output)} chars")
            logger.debug(f"Command output: {output[:500]}")
        else:
            logger.warning(
                f"Command failed with exit status. Output: {output[:500]}"
            )

        return success, output

    except subprocess.TimeoutExpired as e:
        error_msg = f"Command timed out after {timeout} seconds: {command[:100]}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

    except subprocess.SubprocessError as e:
        error_msg = f"Subprocess error executing command: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

    except Exception as e:
        error_msg = f"Unexpected error executing Sapro command: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

