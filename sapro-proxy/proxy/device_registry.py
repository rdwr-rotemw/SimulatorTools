"""
Device registry for tracking the most recently registered device IP.

XMF init_action registers the device IP via plain HTTP on port 8889.
The next forwarded request on port 8888 reads and clears the IP.
Each SAPRO session (every TCP connection) triggers init_action, so
the register always comes right before the forwarded request.
"""

import logging

logger = logging.getLogger("sapro-proxy")


class DeviceRegistry:
    """Stores the most recently registered device IP."""

    def __init__(self):
        self._device_ip = None

    def register(self, device_ip):
        """Register a device IP."""
        self._device_ip = device_ip
        logger.info("Device registered: %s", device_ip)

    def consume(self):
        """Get and clear the registered device IP."""
        ip = self._device_ip
        self._device_ip = None
        if ip:
            logger.info("Device consumed: %s", ip)
        return ip
