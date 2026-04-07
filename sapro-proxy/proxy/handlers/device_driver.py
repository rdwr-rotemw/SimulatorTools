import logging
import os

from proxy.handlers.base import BaseHandler

logger = logging.getLogger("sapro-proxy")

DRIVER_MAP_FILENAME = "driver_map.json"


class DeviceDriverHandler(BaseHandler):
    """POST /dynamic/hidden/VisionDriver/ReceivefromDevice — serve device driver JAR.

    Response matches real DefensePro behavior captured from DP 172.17.22.54 (8.34.1.0):
    - Status: 200
    - Content-Type: application/octet-stream
    - Content-Disposition: attachment;filename=<jar_name>
    - Server: Radware-web-server
    """

    def routes(self):
        return [("POST", "/dynamic/hidden/VisionDriver/ReceivefromDevice")]

    def handle(self, method, path, headers, body):
        host = headers.get("Host", "")
        device_ip = host.split(":")[0]

        config_path = os.path.join(self.driver_dir, DRIVER_MAP_FILENAME)
        driver_map = self.config.get(config_path)

        jar_name = driver_map.get(device_ip)
        if not jar_name:
            logger.warning("No driver mapping for device %s", device_ip)
            return 404, {}, b""

        jar_path = os.path.join(self.driver_dir, jar_name)
        if not os.path.exists(jar_path):
            logger.error("JAR file not found: %s", jar_path)
            return 404, {}, b""

        with open(jar_path, "rb") as f:
            data = f.read()

        logger.info("Serving %s (%d bytes) for device %s", jar_name, len(data), device_ip)

        return 200, {
            "Content-Type": "application/octet-stream",
            "Content-Disposition": f"attachment;filename={jar_name}",
            "Server": "Radware-web-server",
            "Content-Length": str(len(data)),
        }, data
