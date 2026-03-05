"""
Centralized SSH client for Sapro server with connection pooling.

Provides a singleton SSH connection manager that reuses connections,
auto-reconnects on failure, and implements best practices for SSH operations.

Usage:
    from backend.app.utils.sapro_ssh import get_sapro_ssh_client

    client = get_sapro_ssh_client()
    success, output = client.execute_command("/opt/sapro/sapcnsl -h")

    # Or use as context manager
    with get_sapro_ssh_client() as client:
        success, output = client.execute_command("ls /opt/sapro")
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import List, Optional, Tuple

import paramiko

from backend.app.utils.config import settings
from backend.app.utils.logger import logger


class SaproSSHClient:
    """SSH client with connection pooling and auto-reconnect for Sapro server operations.

    Features:
    - Connection reuse via Transport layer
    - Auto-reconnect on connection drop
    - Thread-safe operations
    - Proper timeout handling
    - Context manager support
    - Comprehensive logging

    Configuration:
    - SAPRO_SSH_HOST: SSH host (localhost in production, remote in dev)
    - SAPRO_SSH_USER: SSH username (default: root)
    - SAPRO_SSH_PASSWORD: SSH password
    - ENVIRONMENT: Determines host selection (production uses localhost)
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: int = 22,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 15,
        keepalive_interval: int = 30,
        max_retries: int = 3,
    ):
        """Initialize SSH client with connection pooling.

        Args:
            host: SSH host (defaults to settings-based selection)
            port: SSH port (default: 22)
            username: SSH username (defaults to SAPRO_SSH_USER)
            password: SSH password (defaults to SAPRO_SSH_PASSWORD)
            timeout: Connection and command timeout in seconds
            keepalive_interval: TCP keepalive interval in seconds
            max_retries: Maximum connection retry attempts
        """
        # Determine host based on environment if not explicitly provided
        if host is None:
            if settings.ENVIRONMENT == "production":
                # In production (Docker with network_mode: host), connect to localhost
                host = "localhost"
                logger.info("Using localhost for SSH (production mode with network_mode: host)")
            else:
                # In development, use configured remote host
                host = settings.SAPRO_SSH_HOST
                logger.info(f"Using remote SSH host: {host} (development mode)")

        self.host = host
        self.port = port
        self.username = username or settings.SAPRO_SSH_USER
        self.password = password or settings.SAPRO_SSH_PASSWORD
        self.timeout = timeout
        self.keepalive_interval = keepalive_interval
        self.max_retries = max_retries

        # Connection state
        self._transport: Optional[paramiko.Transport] = None
        self._client: Optional[paramiko.SSHClient] = None
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        self._last_used = 0.0
        self._connection_id = 0

        # Validate credentials
        if not self.username:
            raise ValueError("SSH username not configured (SAPRO_SSH_USER)")
        if not self.password:
            logger.warning("SSH password not configured (SAPRO_SSH_PASSWORD) - authentication may fail")

        logger.debug(
            f"SaproSSHClient initialized: {self.username}@{self.host}:{self.port} "
            f"(timeout={self.timeout}s, keepalive={self.keepalive_interval}s)"
        )

    def __enter__(self):
        """Context manager entry - ensure connection is established."""
        self._ensure_connected()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - optionally close connection."""
        # Keep connection open for reuse, but log if error occurred
        if exc_type is not None:
            logger.error(f"Error in SSH context: {exc_type.__name__}: {exc_val}")
        return False  # Don't suppress exceptions

    def _ensure_connected(self) -> bool:
        """Ensure SSH connection is established and alive.

        Returns:
            True if connected, False otherwise
        """
        with self._lock:
            # Check if transport exists and is active
            if self._transport and self._transport.is_active():
                self._last_used = time.time()
                return True

            # Need to (re)connect
            logger.info(f"Establishing SSH connection to {self.host} (connection_id: {self._connection_id})")
            return self._connect()

    def _connect(self) -> bool:
        """Establish new SSH connection with retry logic.

        Returns:
            True if connection successful, False otherwise
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                # Close any existing connection
                self._close_internal()

                # Create new client and transport
                self._client = paramiko.SSHClient()
                self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                logger.debug(f"SSH connect attempt {attempt}/{self.max_retries} to {self.username}@{self.host}:{self.port}")

                # Connect and get transport
                self._client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=self.timeout,
                    banner_timeout=self.timeout,
                    auth_timeout=self.timeout,
                    allow_agent=False,  # Disable SSH agent for consistency
                    look_for_keys=False,  # Disable key-based auth
                )

                # Get and configure transport for connection pooling
                self._transport = self._client.get_transport()
                if self._transport:
                    self._transport.set_keepalive(self.keepalive_interval)
                    self._connection_id += 1
                    self._last_used = time.time()

                    logger.info(
                        f"SSH connection established: {self.username}@{self.host}:{self.port} "
                        f"(connection_id: {self._connection_id})"
                    )
                    return True
                else:
                    logger.error("Failed to get transport from SSH client")

            except paramiko.AuthenticationException as e:
                logger.error(f"SSH authentication failed (attempt {attempt}/{self.max_retries}): {e}")
                # Don't retry auth failures
                return False

            except paramiko.SSHException as e:
                logger.warning(f"SSH error (attempt {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    time.sleep(1 * attempt)  # Exponential backoff

            except (OSError, EOFError) as e:
                logger.warning(f"Network error (attempt {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    time.sleep(1 * attempt)  # Exponential backoff

            except Exception as e:
                logger.error(f"Unexpected SSH connection error (attempt {attempt}/{self.max_retries}): {e}", exc_info=True)
                if attempt < self.max_retries:
                    time.sleep(1 * attempt)

        logger.error(f"Failed to establish SSH connection after {self.max_retries} attempts")
        return False

    def _close_internal(self):
        """Close SSH connection and transport (internal, assumes lock held)."""
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.debug(f"Error closing SSH client: {e}")
            self._client = None

        if self._transport:
            try:
                self._transport.close()
            except Exception as e:
                logger.debug(f"Error closing SSH transport: {e}")
            self._transport = None

    def close(self):
        """Close SSH connection and release resources.

        Typically not needed due to connection pooling, but provided for
        explicit cleanup when required.
        """
        with self._lock:
            if self._connection_id > 0:
                logger.info(f"Closing SSH connection (connection_id: {self._connection_id})")
            self._close_internal()
            self._connection_id = 0

    def is_connected(self) -> bool:
        """Check if SSH connection is active.

        Returns:
            True if connected and transport is active
        """
        with self._lock:
            return self._transport is not None and self._transport.is_active()

    def execute_command(
        self,
        command: str,
        timeout: Optional[int] = None,
        check_stderr: bool = True,
        get_pty: bool = False,
    ) -> Tuple[bool, str]:
        """Execute a command on the remote server.

        Args:
            command: Shell command to execute
            timeout: Command timeout in seconds (defaults to instance timeout)
            check_stderr: If True, treat stderr output as error
            get_pty: If True, allocate a pseudo-terminal (fixes buffering issues)

        Returns:
            Tuple of (success: bool, output: str)
            - success: True if command executed successfully
            - output: Combined stdout/stderr or error message

        Examples:
            >>> client = get_sapro_ssh_client()
            >>> success, output = client.execute_command("ls /opt/sapro")
            >>> if success:
            ...     print(f"Files: {output}")
        """
        if timeout is None:
            timeout = self.timeout

        with self._lock:
            # Ensure connection
            if not self._ensure_connected():
                return False, "Failed to establish SSH connection"

            try:
                logger.debug(f"Executing SSH command: {command[:100]}{'...' if len(command) > 100 else ''}")

                # Execute command with optional PTY allocation
                stdin, stdout, stderr = self._client.exec_command(
                    command,
                    timeout=timeout,
                    get_pty=get_pty
                )

                # Set channel timeout for read operations to prevent indefinite blocking
                stdout.channel.settimeout(timeout)

                # Read output
                stdout_text = stdout.read().decode('utf-8', errors='ignore').strip()
                stderr_text = stderr.read().decode('utf-8', errors='ignore').strip()
                exit_status = stdout.channel.recv_exit_status()

                logger.debug(
                    f"Command exit status: {exit_status}, "
                    f"stdout: {len(stdout_text)} chars, stderr: {len(stderr_text)} chars"
                )

                # Determine success
                if exit_status != 0:
                    error_msg = stderr_text or stdout_text or f"Command exited with status {exit_status}"
                    logger.warning(f"Command failed with exit status {exit_status}: {error_msg[:200]}")
                    return False, error_msg

                if check_stderr and stderr_text:
                    # Some commands write to stderr even on success, so this is configurable
                    logger.warning(f"Command succeeded but has stderr: {stderr_text[:200]}")
                    return False, f"STDERR: {stderr_text}"

                # Success
                output = stdout_text if stdout_text else stderr_text
                if not output:
                    output = "Command executed successfully (no output)"

                logger.debug(f"Command succeeded: {output[:200]}{'...' if len(output) > 200 else ''}")
                return True, output

            except paramiko.SSHException as e:
                logger.error(f"SSH error executing command: {e}")
                # Try to reconnect on next call
                self._close_internal()
                return False, f"SSH error: {e}"

            except (OSError, EOFError) as e:
                logger.error(f"Network error executing command: {e}")
                # Try to reconnect on next call
                self._close_internal()
                return False, f"Network error: {e}"

            except Exception as e:
                logger.error(f"Unexpected error executing command: {e}", exc_info=True)
                return False, f"Unexpected error: {e}"

    def list_directory(self, path: str) -> List[str]:
        """List files and directories at the specified path.

        Args:
            path: Directory path to list

        Returns:
            List of filenames/directory names, or empty list on error

        Examples:
            >>> client = get_sapro_ssh_client()
            >>> files = client.list_directory("/opt/sapro/map")
            >>> print(files)
            ['map1.map', 'map2.map', 'default.map']
        """
        # Use ls -1 for simple one-per-line output
        success, output = self.execute_command(f"ls -1 {path}", check_stderr=False)

        if not success:
            logger.warning(f"Failed to list directory {path}: {output}")
            return []

        # Parse output into list
        files = [line.strip() for line in output.splitlines() if line.strip()]
        logger.debug(f"Listed {len(files)} items in {path}")
        return files

    def file_exists(self, path: str) -> bool:
        """Check if a file or directory exists.

        Args:
            path: File or directory path to check

        Returns:
            True if path exists, False otherwise

        Examples:
            >>> client = get_sapro_ssh_client()
            >>> if client.file_exists("/opt/sapro/map/default.map"):
            ...     print("Map file exists")
        """
        # Use test -e which returns 0 if path exists
        success, _ = self.execute_command(f"test -e {path}", check_stderr=False)
        logger.debug(f"File exists check for {path}: {success}")
        return success

    def read_file(self, path: str, max_size: int = 1024 * 1024) -> Tuple[bool, str]:
        """Read contents of a text file.

        Args:
            path: File path to read
            max_size: Maximum file size to read in bytes (default: 1MB)

        Returns:
            Tuple of (success: bool, content: str)
            - success: True if file read successfully
            - content: File contents or error message

        Examples:
            >>> client = get_sapro_ssh_client()
            >>> success, content = client.read_file("/opt/sapro/map/default.map")
            >>> if success:
            ...     print(content)
        """
        # First check file exists and get size
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
            logger.warning(f"Could not parse file size: {output}")

        # Read file contents
        success, content = self.execute_command(f"cat {path}", check_stderr=False)

        if not success:
            return False, f"Failed to read file: {content}"

        logger.debug(f"Read {len(content)} bytes from {path}")
        return True, content

    def get_connection_info(self) -> dict:
        """Get current connection information for debugging.

        Returns:
            Dictionary with connection details
        """
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


# Module-level connection pool
_SSH_POOL_SIZE = 24
_sapro_ssh_pool: Optional[List[SaproSSHClient]] = None
_pool_index = 0
_pool_lock = threading.Lock()


def get_sapro_ssh_client() -> SaproSSHClient:
    """Get an SSH client from the connection pool (round-robin).

    On first call, creates a pool of _SSH_POOL_SIZE connections with staggered
    initialization to avoid overwhelming sshd's MaxStartups limit.
    Subsequent calls rotate through the pool, allowing parallel SSH commands.

    Returns:
        SaproSSHClient instance from the pool
    """
    global _sapro_ssh_pool, _pool_index

    with _pool_lock:
        if _sapro_ssh_pool is None:
            logger.info(f"Initializing SSH connection pool with {_SSH_POOL_SIZE} connections")
            _sapro_ssh_pool = []
            for i in range(_SSH_POOL_SIZE):
                client = SaproSSHClient()
                _sapro_ssh_pool.append(client)
                if i < _SSH_POOL_SIZE - 1:
                    time.sleep(0.1)  # stagger to avoid MaxStartups rejection
            logger.info(f"SSH connection pool ready ({_SSH_POOL_SIZE} connections)")

        client = _sapro_ssh_pool[_pool_index % _SSH_POOL_SIZE]
        _pool_index += 1
        return client


def close_sapro_ssh_client():
    """Close all SSH connections in the pool.

    Typically called during application shutdown to ensure graceful cleanup.
    The pool will be re-created automatically on next use.
    """
    global _sapro_ssh_pool, _pool_index

    with _pool_lock:
        if _sapro_ssh_pool is not None:
            logger.info(f"Closing SSH connection pool ({len(_sapro_ssh_pool)} connections)")
            for client in _sapro_ssh_pool:
                client.close()
            _sapro_ssh_pool = None
            _pool_index = 0


@contextmanager
def sapro_ssh_context():
    """Context manager that returns a pooled SSH client.

    Yields:
        SaproSSHClient instance from the pool
    """
    client = get_sapro_ssh_client()
    try:
        yield client
    finally:
        # Don't close - allow connection reuse
        pass


__all__ = [
    "SaproSSHClient",
    "get_sapro_ssh_client",
    "close_sapro_ssh_client",
    "sapro_ssh_context",
]

