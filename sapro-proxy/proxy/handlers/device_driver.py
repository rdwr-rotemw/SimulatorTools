import logging
import os
import re

from proxy.handlers.base import BaseHandler

logger = logging.getLogger("sapro-proxy")

DRIVER_MAP_FILENAME = "driver_map.json"

# Valid JAR filename pattern: DeviceType-Version-DD-DDVersion.jar
JAR_FILENAME_PATTERN = re.compile(r'^[\w\-]+\.jar$')


class DeviceDriverHandler(BaseHandler):
    """POST /dynamic/hidden/VisionDriver/ReceivefromDevice — serve device driver JAR.

    Since SAPRO's SA_xml_request_forwarder replaces the Host header with 127.0.0.1,
    we cannot identify the device from the request. Instead, driver_map.json maps
    device IPs to JAR filenames. The backend updates this file when compiling or
    uploading device drivers.

    For requests from the forwarder (Host: 127.0.0.1), we look up all entries in
    driver_map.json. When only one device is mapped, we serve that JAR directly.
    When multiple devices exist, we use the source port from the Soap section
    to disambiguate (future enhancement).

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

        if not driver_map:
            logger.error("driver_map.json is empty or missing at %s", config_path)
            return 404, {}, b""

        # SAPRO's forwarder sets Host to 127.0.0.1 — can't identify device from it.
        # If only one device is mapped, serve that. Otherwise log which are available.
        jar_name = driver_map.get(device_ip)
        if not jar_name and len(driver_map) == 1:
            only_ip, jar_name = next(iter(driver_map.items()))
            logger.info("Single device in driver_map, serving %s (mapped to %s)", jar_name, only_ip)
        elif not jar_name:
            logger.warning(
                "Cannot identify device from Host '%s'. driver_map has %d entries: %s",
                host, len(driver_map), list(driver_map.keys()),
            )
            return 404, {}, b""

        if not JAR_FILENAME_PATTERN.match(jar_name):
            logger.error("Invalid JAR filename in driver_map: '%s'", jar_name)
            return 404, {}, b""

        jar_path = os.path.join(self.driver_dir, jar_name)
        real_path = os.path.realpath(jar_path)
        if not real_path.startswith(os.path.realpath(self.driver_dir) + os.sep):
            logger.error("Path traversal blocked: '%s'", jar_name)
            return 404, {}, b""

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
