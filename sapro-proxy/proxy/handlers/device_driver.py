import logging
import os
import re
import subprocess

from proxy.handlers.base import BaseHandler

logger = logging.getLogger("sapro-proxy")

# rndVisionDriverActiveName — the OID that holds the device driver JAR filename
DRIVER_OID = ".1.3.6.1.4.1.89.35.2.9.1.0"
SNMP_COMMUNITY = "public"
SNMP_TIMEOUT_SECONDS = 5

# Valid JAR filename pattern: DeviceType-Version-DD-DDVersion.jar
JAR_FILENAME_PATTERN = re.compile(r'^[\w\.\-]+\.jar$')


def snmpget_driver_filename(device_ip):
    """Query the simulated device via SNMP to get its device driver JAR filename."""
    try:
        result = subprocess.run(
            ["snmpget", "-v", "2c", "-c", SNMP_COMMUNITY, "-Oqv",
             "-t", str(SNMP_TIMEOUT_SECONDS), device_ip, DRIVER_OID],
            capture_output=True, text=True, timeout=SNMP_TIMEOUT_SECONDS + 2,
        )
        if result.returncode != 0:
            logger.error("snmpget failed for %s: %s", device_ip, result.stderr.strip())
            return None

        value = result.stdout.strip().strip('"')
        if not value or value.startswith("No Such"):
            logger.warning("OID %s not found on device %s", DRIVER_OID, device_ip)
            return None

        return value

    except subprocess.TimeoutExpired:
        logger.error("snmpget timed out for %s", device_ip)
        return None
    except FileNotFoundError:
        logger.error("snmpget command not found — install net-snmp")
        return None


class DeviceDriverHandler(BaseHandler):
    """POST /dynamic/hidden/VisionDriver/ReceivefromDevice — serve device driver JAR.

    Flow:
    1. XMF init_action registers device IP via /_register on port 8889
    2. SA_xml_request_forwarder forwards CC's request here on port 8888
    3. Handler consumes the registered IP from the device registry
    4. SNMP query to the device gets the JAR filename (rndVisionDriverActiveName)
    5. Serve the JAR binary with exact real DefensePro response headers

    Response captured from real DP 172.17.22.54 (8.34.1.0):
    - Status: 200
    - Content-Type: application/octet-stream
    - Content-Disposition: attachment;filename=<jar_name>
    - Server: Radware-web-server
    """

    def routes(self):
        return [("POST", "/dynamic/hidden/VisionDriver/ReceivefromDevice")]

    def handle(self, method, path, headers, body):
        device_ip = self.registry.consume()

        if not device_ip:
            logger.warning("No device registered — request arrived without prior /_register")
            return 404, {}, b""

        logger.info("Serving driver request for registered device %s", device_ip)

        jar_name = snmpget_driver_filename(device_ip)
        if not jar_name:
            logger.warning("Could not resolve driver filename for device %s", device_ip)
            return 404, {}, b""

        if not JAR_FILENAME_PATTERN.match(jar_name):
            logger.error("Invalid JAR filename from SNMP: '%s'", jar_name)
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
