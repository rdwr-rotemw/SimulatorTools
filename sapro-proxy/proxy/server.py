"""
SAPRO HTTP Proxy — general-purpose HTTPS server for requests forwarded by SAPRO's
SA_xml_request_forwarder. Handles binary responses and complex routing that SAPRO's
XMF/TCL engine cannot do natively.

Architecture:
    Port 8888 (HTTPS) — receives forwarded CC requests via SA_xml_request_forwarder
    Port 8889 (HTTP)  — receives device registration from XMF init_action TCL

Flow per device request:
    1. XMF init_action sends POST /_register with device IP to port 8889
    2. XMF sets up SA_xml_request_forwarder to port 8888
    3. CC request arrives on 8888, proxy uses registered IP to identify device
    4. SNMP query gets JAR filename, proxy serves the binary

Usage:
    python -m proxy.server [--port 8888] [--register-port 8889] [--driver-dir /path]
"""

import argparse
import logging
import os
import ssl
import subprocess
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from proxy.config import ConfigManager
from proxy.device_registry import DeviceRegistry
from proxy.dispatcher import Dispatcher
from proxy.handlers.connectivity import ConnectivityHandler
from proxy.handlers.device_driver import DeviceDriverHandler
from proxy.handlers.health import HealthHandler
from proxy.handlers.register import RegisterHandler

logger = logging.getLogger("sapro-proxy")

DEFAULT_CERT_DIR = "/app/certs"


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
            ">>> %s %s\n    Headers: %s\n    Body (%d bytes): %s",
            method, self.path, dict(headers), len(body), body,
        )

        status, response_headers, response_body = self.dispatcher.dispatch(
            method, self.path, headers, body
        )

        self.send_response(status)
        self.send_header("Connection", "close")
        for key, value in response_headers.items():
            self.send_header(key, value)
        self.end_headers()

        if response_body:
            self.wfile.write(response_body)

    def log_message(self, format, *args):
        logger.info("[%s] %s", self.client_address[0], format % args)


class RegisterRequestHandler(BaseHTTPRequestHandler):
    """Handles device registration on the plain HTTP port.

    The XMF TCL closes the socket immediately after sending (fire-and-forget),
    so BrokenPipeError on the response write is expected and silenced.
    """

    dispatcher = None

    def do_POST(self):
        self._handle("POST")

    def _handle(self, method):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        headers = {key: self.headers[key] for key in self.headers}

        logger.debug(
            ">>> [register] %s %s\n    Body: %s",
            method, self.path, body,
        )

        status, response_headers, response_body = self.dispatcher.dispatch(
            method, self.path, headers, body
        )

        try:
            self.send_response(status)
            self.send_header("Connection", "close")
            for key, value in response_headers.items():
                self.send_header(key, value)
            self.end_headers()

            if response_body:
                self.wfile.write(response_body)
        except BrokenPipeError:
            pass

    def log_message(self, format, *args):
        logger.debug("[register][%s] %s", self.client_address[0], format % args)


def ensure_ssl_cert(cert_dir):
    """Generate a self-signed SSL certificate if one doesn't exist."""
    cert_file = os.path.join(cert_dir, "server.pem")
    key_file = os.path.join(cert_dir, "server.key")

    if os.path.exists(cert_file) and os.path.exists(key_file):
        logger.info("Using existing SSL cert: %s", cert_file)
        return cert_file, key_file

    os.makedirs(cert_dir, exist_ok=True)

    logger.info("Generating self-signed SSL certificate in %s", cert_dir)
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", key_file, "-out", cert_file,
            "-days", "3650", "-nodes",
            "-subj", "/CN=Radware-web-server",
        ],
        check=True, capture_output=True,
    )
    logger.info("SSL certificate generated: %s", cert_file)

    return cert_file, key_file


def build_main_dispatcher(config, driver_dir, registry):
    """Dispatcher for the main HTTPS server (port 8888)."""
    dispatcher = Dispatcher()
    dispatcher.register(HealthHandler(config))
    dispatcher.register(ConnectivityHandler(config))
    dispatcher.register(DeviceDriverHandler(config, driver_dir=driver_dir, registry=registry))
    return dispatcher


def build_register_dispatcher(config, registry):
    """Dispatcher for the registration HTTP server (port 8889)."""
    dispatcher = Dispatcher()
    dispatcher.register(RegisterHandler(config, registry=registry))
    return dispatcher


def parse_args():
    parser = argparse.ArgumentParser(description="SAPRO HTTP Proxy")
    parser.add_argument("--port", type=int, default=8888, help="HTTPS port for forwarded requests (default: 8888)")
    parser.add_argument("--register-port", type=int, default=8889, help="HTTP port for device registration (default: 8889)")
    parser.add_argument("--driver-dir", required=True, help="Directory containing device driver JAR files")
    parser.add_argument("--cert-dir", default=DEFAULT_CERT_DIR, help="Directory for SSL certificates")
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
    registry = DeviceRegistry()

    # Main HTTPS server for forwarded CC requests
    main_dispatcher = build_main_dispatcher(config, args.driver_dir, registry)
    ProxyRequestHandler.dispatcher = main_dispatcher

    cert_file, key_file = ensure_ssl_cert(args.cert_dir)

    main_server = HTTPServer(("127.0.0.1", args.port), ProxyRequestHandler)
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(cert_file, key_file)
    main_server.socket = ssl_context.wrap_socket(main_server.socket, server_side=True)

    _original_shutdown = main_server.shutdown_request

    def _tls_shutdown(request):
        try:
            request.unwrap()
        except (ssl.SSLError, OSError):
            pass
        _original_shutdown(request)

    main_server.shutdown_request = _tls_shutdown

    # Registration HTTP server for XMF init_action calls
    register_dispatcher = build_register_dispatcher(config, registry)
    RegisterRequestHandler.dispatcher = register_dispatcher

    register_server = HTTPServer(("127.0.0.1", args.register_port), RegisterRequestHandler)

    # Run registration server in a background thread
    register_thread = threading.Thread(target=register_server.serve_forever, daemon=True)
    register_thread.start()

    logger.info("SAPRO proxy listening on https://127.0.0.1:%d (forwarded requests)", args.port)
    logger.info("Registration server on http://127.0.0.1:%d (XMF init_action)", args.register_port)
    logger.info("Driver dir: %s", args.driver_dir)

    try:
        main_server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
        register_server.shutdown()
        main_server.server_close()


if __name__ == "__main__":
    main()
