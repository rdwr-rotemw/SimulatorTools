import ipaddress
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
JAR_FILENAME_PATTERN = re.compile(r'^[\w\-]+\.jar$')


def validate_ip(ip_string):
    """Validate that a string is a valid IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(ip_string)
        return True
    except ValueError:
        return False


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

    Mirrors real DefensePro behavior:
    1. Query the device via SNMP for rndVisionDriverActiveName to get the JAR filename
    2. Serve that JAR binary with exact same headers as a real DP

    Response captured from real DP 172.17.22.54 (8.34.1.0):
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

        logger.debug("Request headers: %s", dict(headers))

        if not device_ip or not validate_ip(device_ip):
            logger.warning("Invalid or missing device IP from Host header: '%s'", host)
            return 404, {}, b""

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
