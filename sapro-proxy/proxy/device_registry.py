"""
Thread-safe device registry with locking.

XMF init_action registers the device IP via plain HTTP on port 8889 (fire-and-forget).
The next forwarded request on port 8888 uses that IP, then clears it.
A threading lock ensures only one device goes through the register → serve cycle at a time.
"""

import logging
import threading

logger = logging.getLogger("sapro-proxy")


class DeviceRegistry:
    """Stores the most recently registered device IP with thread-safe locking."""

    def __init__(self):
        self._lock = threading.Lock()
        self._device_ip = None

    def register(self, device_ip):
        """Register a device IP. Acquires the lock — blocks until previous cycle completes."""
        self._lock.acquire()
        self._device_ip = device_ip
        logger.info("Device registered: %s (lock acquired)", device_ip)

    def consume(self):
        """Get and clear the registered device IP. Releases the lock."""
        ip = self._device_ip
        self._device_ip = None
        try:
            self._lock.release()
            logger.info("Device consumed: %s (lock released)", ip)
        except RuntimeError:
            pass
        return ip
