import ipaddress
import logging

from proxy.handlers.base import BaseHandler

logger = logging.getLogger("sapro-proxy")


def validate_ip(ip_string):
    """Validate that a string is a valid IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(ip_string)
        return True
    except ValueError:
        return False


class RegisterHandler(BaseHandler):
    """POST /_register — called by XMF init_action to register the device IP.

    The XMF sends the device IP as the request body before the forwarder
    handles the actual CC request. This lets the proxy identify which device
    the next forwarded request belongs to.
    """

    def routes(self):
        return [("POST", "/_register")]

    def handle(self, method, path, headers, body):
        device_ip = body.decode("utf-8").strip()

        if not device_ip or not validate_ip(device_ip):
            logger.warning("Invalid device IP in register request: '%s'", device_ip)
            return 400, {}, b"Invalid IP"

        self.registry.register(device_ip)

        return 200, {"Content-Type": "text/plain"}, b"OK"
