"""
SAPRO HTTP Proxy — general-purpose HTTP server for requests forwarded by SAPRO's
SA_xml_request_forwarder. Handles binary responses and complex routing that SAPRO's
XMF/TCL engine cannot do natively.

Usage:
    python -m proxy.server [--port 8888] [--driver-dir /path/to/drivers]
"""

import argparse
import logging
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

from proxy.config import ConfigManager
from proxy.dispatcher import Dispatcher
from proxy.handlers.connectivity import ConnectivityHandler
from proxy.handlers.device_driver import DeviceDriverHandler
from proxy.handlers.health import HealthHandler

logger = logging.getLogger("sapro-proxy")


class ProxyRequestHandler(BaseHTTPRequestHandler):
    """Delegates all requests to the dispatcher."""

    dispatcher = None

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")

    def do_DELETE(self):
        self._handle("DELETE")

    def do_PATCH(self):
        self._handle("PATCH")

    def _handle(self, method):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        headers = {key: self.headers[key] for key in self.headers}

        logger.debug(
            ">>> %s %s\n    Headers: %s\n    Body length: %d",
            method, self.path, dict(headers), len(body),
        )

        status, response_headers, response_body = self.dispatcher.dispatch(
            method, self.path, headers, body
        )

        self.send_response(status)
        for key, value in response_headers.items():
            self.send_header(key, value)
        self.end_headers()

        if response_body:
            self.wfile.write(response_body)

    def log_message(self, format, *args):
        logger.info("[%s] %s", self.client_address[0], format % args)


def build_dispatcher(config, driver_dir):
    """Create dispatcher and register all handlers."""
    dispatcher = Dispatcher()

    dispatcher.register(HealthHandler(config))
    dispatcher.register(ConnectivityHandler(config))
    dispatcher.register(DeviceDriverHandler(config, driver_dir=driver_dir))

    return dispatcher


def parse_args():
    parser = argparse.ArgumentParser(description="SAPRO HTTP Proxy")
    parser.add_argument("--port", type=int, default=8888, help="Port to listen on (default: 8888)")
    parser.add_argument("--driver-dir", required=True, help="Directory containing device driver JAR files")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def main():
    args = parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    config = ConfigManager()
    dispatcher = build_dispatcher(config, driver_dir=args.driver_dir)

    ProxyRequestHandler.dispatcher = dispatcher

    server = HTTPServer(("127.0.0.1", args.port), ProxyRequestHandler)
    logger.info("SAPRO proxy listening on 127.0.0.1:%d", args.port)
    logger.info("Driver dir: %s", args.driver_dir)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
        server.server_close()


if __name__ == "__main__":
    main()
