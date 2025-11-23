"""
Execute Sapro commands either via SSH (development) or direct subprocess (production).

In production with network_mode: host, the container shares the host's network namespace
and can access Sapro processes, maps, and simulators directly via subprocess.
"""

import subprocess
import logging
from typing import Tuple

from backend.app.utils.config import settings

logger = logging.getLogger(__name__)


def execute_sapro_command(command: str, timeout: int = 30) -> Tuple[bool, str]:
    """
    Execute Sapro command via SSH (development) or subprocess (production with host network).

    Args:
        command: The command to execute on the Sapro system
        timeout: Command timeout in seconds (default: 30)

    Returns:
        Tuple of (success: bool, output: str)

    Raises:
        subprocess.TimeoutExpired: If command execution exceeds timeout
        subprocess.SubprocessError: If subprocess execution fails
    """
    try:
        logger.info(
            f"Executing Sapro command in {settings.ENVIRONMENT} environment: {command[:100]}"
        )

        if settings.ENVIRONMENT == "development":
            # SSH to Sapro host in development
            import paramiko

            ssh_target = f"{settings.SAPRO_SSH_USER}@{settings.SAPRO_SSH_HOST}"
            logger.debug(f"Using SSH to {ssh_target}")

            client = None
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                logger.debug(f"Connecting to {settings.SAPRO_SSH_HOST} as {settings.SAPRO_SSH_USER}")
                client.connect(
                    settings.SAPRO_SSH_HOST,
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

        else:
            # Production: Direct subprocess (container runs with network_mode: host)
            logger.debug("Executing via subprocess (host network mode)")

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
            logger.info(f"Command succeeded. Output: {len(output)} chars")
            logger.debug(f"Output: {output[:500]}")
        else:
            logger.warning(f"Command failed. Output: {output[:500]}")

        return success, output

    except subprocess.TimeoutExpired as e:
        error_msg = f"Timeout after {timeout}s: {command[:100]}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

    except subprocess.SubprocessError as e:
        error_msg = f"Subprocess error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

    except Exception as e:
        error_msg = f"Unexpected error executing Sapro command: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

