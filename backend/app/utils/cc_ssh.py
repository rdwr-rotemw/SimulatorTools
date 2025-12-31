"""
Centralized SSH client for CyberController with connection pooling.

Provides SSH connection management with connection reuse per CC instance.
Unlike Sapro (single instance), supports multiple CC IPs with separate connections.

Usage:
    from backend.app.utils.cc_ssh import get_cc_ssh_client

    # Get client for specific CC
    client = get_cc_ssh_client(cc_ip="10.0.0.100")
    success, output = client.execute_command("ls /opt/radware")

    # Or use as context manager
    with get_cc_ssh_client(cc_ip="10.0.0.100") as client:
        success, output = client.execute_command("uptime")
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple

import paramiko

from backend.app.utils.logger import logger


class CCSSHClient:
    """SSH client with connection pooling for CyberController operations.

    Features:
    - Connection reuse via Transport layer
    - Auto-reconnect on connection drop
    - Thread-safe operations
    - Proper timeout handling
    - Context manager support
    - File transfer support (SCP)

    Default credentials: root/radware
    """

    # Class-level default credentials
    DEFAULT_USERNAME = "root"
    DEFAULT_PASSWORD = "radware"

    def __init__(
        self,
        host: str,
        port: int = 22,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 15,
        keepalive_interval: int = 30,
        max_retries: int = 3,
    ):
        """Initialize SSH client for CyberController.

        Args:
            host: CC IP or hostname
            port: SSH port (default: 22)
            username: SSH username (default: root)
            password: SSH password (default: radware)
            timeout: Connection and command timeout in seconds
            keepalive_interval: TCP keepalive interval in seconds
            max_retries: Maximum connection retry attempts
        """
        self.host = host
        self.port = port
        self.username = username or self.DEFAULT_USERNAME
        self.password = password or self.DEFAULT_PASSWORD
        self.timeout = timeout
        self.keepalive_interval = keepalive_interval
        self.max_retries = max_retries

        # Connection state
        self._transport: Optional[paramiko.Transport] = None
        self._client: Optional[paramiko.SSHClient] = None
        self._lock = threading.RLock()
        self._last_used = 0.0
        self._connection_id = 0

        logger.debug(
            f"CCSSHClient initialized: {self.username}@{self.host}:{self.port} "
            f"(timeout={self.timeout}s, keepalive={self.keepalive_interval}s)"
        )

    def __enter__(self):
        """Context manager entry."""
        self._ensure_connected()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type is not None:
            logger.error(f"Error in CC SSH context: {exc_type.__name__}: {exc_val}")
        return False

    def _ensure_connected(self) -> bool:
        """Ensure SSH connection is established and alive."""
        with self._lock:
            if self._transport and self._transport.is_active():
                self._last_used = time.time()
                return True

            logger.info(f"Establishing CC SSH connection to {self.host} (connection_id: {self._connection_id})")
            return self._connect()

    def _connect(self) -> bool:
        """Establish new SSH connection with retry logic."""
        for attempt in range(1, self.max_retries + 1):
            try:
                self._close_internal()

                self._client = paramiko.SSHClient()
                self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                logger.debug(f"CC SSH connect attempt {attempt}/{self.max_retries} to {self.username}@{self.host}:{self.port}")

                self._client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=self.timeout,
                    banner_timeout=self.timeout,
                    auth_timeout=self.timeout,
                    allow_agent=False,
                    look_for_keys=False,
                )

                self._transport = self._client.get_transport()
                if self._transport:
                    self._transport.set_keepalive(self.keepalive_interval)
                    self._connection_id += 1
                    self._last_used = time.time()

                    logger.info(
                        f"CC SSH connection established: {self.username}@{self.host}:{self.port} "
                        f"(connection_id: {self._connection_id})"
                    )
                    return True
                else:
                    logger.error("Failed to get transport from CC SSH client")

            except paramiko.AuthenticationException as e:
                logger.error(f"CC SSH authentication failed (attempt {attempt}/{self.max_retries}): {e}")
                return False

            except paramiko.SSHException as e:
                logger.warning(f"CC SSH error (attempt {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    time.sleep(1 * attempt)

            except (OSError, EOFError) as e:
                logger.warning(f"CC network error (attempt {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    time.sleep(1 * attempt)

            except Exception as e:
                logger.error(f"Unexpected CC SSH connection error (attempt {attempt}/{self.max_retries}): {e}", exc_info=True)
                if attempt < self.max_retries:
                    time.sleep(1 * attempt)

        logger.error(f"Failed to establish CC SSH connection after {self.max_retries} attempts")
        return False

    def _close_internal(self):
        """Close SSH connection and transport."""
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.debug(f"Error closing CC SSH client: {e}")
            self._client = None

        if self._transport:
            try:
                self._transport.close()
            except Exception as e:
                logger.debug(f"Error closing CC SSH transport: {e}")
            self._transport = None

    def close(self):
        """Close SSH connection and release resources."""
        with self._lock:
            if self._connection_id > 0:
                logger.info(f"Closing CC SSH connection (connection_id: {self._connection_id})")
            self._close_internal()
            self._connection_id = 0

    def is_connected(self) -> bool:
        """Check if SSH connection is active."""
        with self._lock:
            return self._transport is not None and self._transport.is_active()

    def execute_command(
        self,
        command: str,
        timeout: Optional[int] = None,
        check_stderr: bool = True,
    ) -> Tuple[bool, str]:
        """Execute a command on the CyberController.

        Args:
            command: Shell command to execute
            timeout: Command timeout in seconds
            check_stderr: If True, treat stderr output as error

        Returns:
            Tuple of (success: bool, output: str)
        """
        if timeout is None:
            timeout = self.timeout

        with self._lock:
            if not self._ensure_connected():
                return False, "Failed to establish CC SSH connection"

            try:
                logger.debug(f"Executing CC SSH command: {command[:100]}{'...' if len(command) > 100 else ''}")

                stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)

                stdout_text = stdout.read().decode('utf-8', errors='ignore').strip()
                stderr_text = stderr.read().decode('utf-8', errors='ignore').strip()
                exit_status = stdout.channel.recv_exit_status()

                logger.debug(
                    f"CC command exit status: {exit_status}, "
                    f"stdout: {len(stdout_text)} chars, stderr: {len(stderr_text)} chars"
                )

                if exit_status != 0:
                    error_msg = stderr_text or stdout_text or f"Command exited with status {exit_status}"
                    logger.warning(f"CC command failed with exit status {exit_status}: {error_msg[:200]}")
                    return False, error_msg

                if check_stderr and stderr_text:
                    logger.warning(f"CC command succeeded but has stderr: {stderr_text[:200]}")
                    return False, f"STDERR: {stderr_text}"

                output = stdout_text if stdout_text else stderr_text
                if not output:
                    output = "Command executed successfully (no output)"

                logger.debug(f"CC command succeeded: {output[:200]}{'...' if len(output) > 200 else ''}")
                return True, output

            except paramiko.SSHException as e:
                logger.error(f"CC SSH error executing command: {e}")
                self._close_internal()
                return False, f"SSH error: {e}"

            except (OSError, EOFError) as e:
                logger.error(f"CC network error executing command: {e}")
                self._close_internal()
                return False, f"Network error: {e}"

            except Exception as e:
                logger.error(f"Unexpected CC SSH error executing command: {e}", exc_info=True)
                return False, f"Unexpected error: {e}"

    def list_directory(self, path: str) -> List[str]:
        """List files and directories at the specified path."""
        success, output = self.execute_command(f"ls -1 {path}", check_stderr=False)

        if not success:
            logger.warning(f"Failed to list CC directory {path}: {output}")
            return []

        files = [line.strip() for line in output.splitlines() if line.strip()]
        logger.debug(f"Listed {len(files)} items in CC directory {path}")
        return files

    def file_exists(self, path: str) -> bool:
        """Check if a file or directory exists on CC."""
        success, _ = self.execute_command(f"test -e {path}", check_stderr=False)
        logger.debug(f"CC file exists check for {path}: {success}")
        return success

    def read_file(self, path: str, max_size: int = 1024 * 1024) -> Tuple[bool, str]:
        """Read contents of a text file from CC."""
        success, output = self.execute_command(
            f"test -f {path} && stat -c %s {path}",
            check_stderr=False
        )

        if not success:
            return False, f"File not found or not a regular file: {path}"

        try:
            file_size = int(output.strip())
            if file_size > max_size:
                return False, f"File too large: {file_size} bytes (max: {max_size})"
        except ValueError:
            logger.warning(f"Could not parse CC file size: {output}")

        success, content = self.execute_command(f"cat {path}", check_stderr=False)

        if not success:
            return False, f"Failed to read CC file: {content}"

        logger.debug(f"Read {len(content)} bytes from CC file {path}")
        return True, content

    def upload_file(self, local_path: str, remote_path: str) -> Tuple[bool, str]:
        """Upload a file to CyberController using SCP.

        Args:
            local_path: Local file path
            remote_path: Remote file path on CC

        Returns:
            Tuple of (success: bool, message: str)
        """
        from scp import SCPClient, SCPException

        with self._lock:
            if not self._ensure_connected():
                return False, "Failed to establish CC SSH connection"

            try:
                logger.info(f"Uploading file to CC: {local_path} -> {remote_path}")

                with SCPClient(self._transport) as scp:
                    scp.put(local_path, remote_path)

                logger.info(f"Successfully uploaded file to CC: {remote_path}")
                return True, f"File uploaded successfully: {remote_path}"

            except SCPException as e:
                logger.error(f"SCP error uploading file to CC: {e}")
                return False, f"SCP error: {e}"

            except Exception as e:
                logger.error(f"Unexpected error uploading file to CC: {e}", exc_info=True)
                return False, f"Unexpected error: {e}"

    def download_file(self, remote_path: str, local_path: str) -> Tuple[bool, str]:
        """Download a file from CyberController using SCP.

        Args:
            remote_path: Remote file path on CC
            local_path: Local file path

        Returns:
            Tuple of (success: bool, message: str)
        """
        from scp import SCPClient, SCPException

        with self._lock:
            if not self._ensure_connected():
                return False, "Failed to establish CC SSH connection"

            try:
                logger.info(f"Downloading file from CC: {remote_path} -> {local_path}")

                with SCPClient(self._transport) as scp:
                    scp.get(remote_path, local_path)

                logger.info(f"Successfully downloaded file from CC: {local_path}")
                return True, f"File downloaded successfully: {local_path}"

            except SCPException as e:
                logger.error(f"SCP error downloading file from CC: {e}")
                return False, f"SCP error: {e}"

            except Exception as e:
                logger.error(f"Unexpected error downloading file from CC: {e}", exc_info=True)
                return False, f"Unexpected error: {e}"

    def get_connection_info(self) -> dict:
        """Get current connection information for debugging."""
        with self._lock:
            return {
                "host": self.host,
                "port": self.port,
                "username": self.username,
                "connected": self.is_connected(),
                "connection_id": self._connection_id,
                "last_used": self._last_used,
                "idle_seconds": time.time() - self._last_used if self._last_used > 0 else 0,
            }


# Module-level storage for multiple CC instances
_cc_ssh_clients: Dict[str, CCSSHClient] = {}
_clients_lock = threading.Lock()


def get_cc_ssh_client(
    cc_ip: str,
    username: Optional[str] = None,
    password: Optional[str] = None
) -> CCSSHClient:
    """Get SSH client instance for specific CyberController.

    Maintains separate connection pools per CC IP. Credentials default to root/radware.

    Args:
        cc_ip: CyberController IP address
        username: SSH username (default: root)
        password: SSH password (default: radware)

    Returns:
        CCSSHClient instance for the specified CC

    Examples:
        >>> from backend.app.utils.cc_ssh import get_cc_ssh_client
        >>>
        >>> # Get client for specific CC
        >>> client = get_cc_ssh_client(cc_ip="10.0.0.100")
        >>> success, output = client.execute_command("uptime")
        >>>
        >>> # Context manager usage
        >>> with get_cc_ssh_client(cc_ip="10.0.0.100") as client:
        ...     success, output = client.execute_command("ls /opt/radware")
    """
    global _cc_ssh_clients

    # Create key from IP + credentials
    key = f"{cc_ip}:{username or CCSSHClient.DEFAULT_USERNAME}"

    with _clients_lock:
        if key not in _cc_ssh_clients:
            logger.info(f"Initializing CCSSHClient for {cc_ip}")
            _cc_ssh_clients[key] = CCSSHClient(
                host=cc_ip,
                username=username,
                password=password
            )

        return _cc_ssh_clients[key]


def close_cc_ssh_client(cc_ip: str, username: Optional[str] = None):
    """Close SSH client connection for specific CC.

    Args:
        cc_ip: CyberController IP address
        username: SSH username (default: root)
    """
    global _cc_ssh_clients

    key = f"{cc_ip}:{username or CCSSHClient.DEFAULT_USERNAME}"

    with _clients_lock:
        if key in _cc_ssh_clients:
            logger.info(f"Closing CCSSHClient for {cc_ip}")
            _cc_ssh_clients[key].close()
            del _cc_ssh_clients[key]


def close_all_cc_ssh_clients():
    """Close all CC SSH client connections.

    Typically called during application shutdown.
    """
    global _cc_ssh_clients

    with _clients_lock:
        for key, client in list(_cc_ssh_clients.items()):
            logger.info(f"Closing CCSSHClient: {key}")
            client.close()
        _cc_ssh_clients.clear()


@contextmanager
def cc_ssh_context(cc_ip: str, username: Optional[str] = None, password: Optional[str] = None):
    """Context manager for CC SSH operations.

    Args:
        cc_ip: CyberController IP address
        username: SSH username (default: root)
        password: SSH password (default: radware)

    Yields:
        CCSSHClient instance
    """
    client = get_cc_ssh_client(cc_ip=cc_ip, username=username, password=password)
    try:
        yield client
    finally:
        # Don't close - allow connection reuse
        pass


__all__ = [
    "CCSSHClient",
    "get_cc_ssh_client",
    "close_cc_ssh_client",
    "close_all_cc_ssh_clients",
    "cc_ssh_context",
]
