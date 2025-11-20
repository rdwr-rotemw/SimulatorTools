"""
Execute Sapro commands either via SSH (development) or direct subprocess (production).

This module provides command execution functionality that adapts based on the
environment setting - using SSH for development environments and direct
subprocess calls when running on the Sapro host in production.
"""

import subprocess
import logging
from typing import Tuple

from backend.app.utils.config import settings

logger = logging.getLogger(__name__)


def execute_sapro_command(command: str, timeout: int = 30) -> Tuple[bool, str]:
    """
    Execute Sapro command on DEV (SSH) or PROD (subprocess).

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
    try:
        logger.info(
            f"Executing Sapro command in {settings.ENVIRONMENT} environment: {command[:100]}"
        )

        if settings.ENVIRONMENT == "development":
            # SSH to Sapro host in development using paramiko
            import paramiko

            ssh_target = f"{settings.SAPRO_SSH_USER}@{settings.SAPRO_SSH_HOST}"
            logger.debug(f"Using paramiko SSH connection to {ssh_target}")

            client = None
            try:
                # Create SSH client
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                # Connect to the Sapro host
                logger.debug(f"Connecting to {settings.SAPRO_SSH_HOST} as {settings.SAPRO_SSH_USER}")
                client.connect(
                    settings.SAPRO_SSH_HOST,
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
            # Direct subprocess (running ON Sapro host in Docker/production)
            logger.debug("Executing command directly on Sapro host")

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

