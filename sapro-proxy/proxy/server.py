"""
SAPRO HTTP Proxy — general-purpose HTTPS server for requests forwarded by SAPRO's
SA_xml_request_forwarder. Handles binary responses and complex routing that SAPRO's
XMF/TCL engine cannot do natively.

Usage:
    python -m proxy.server [--port 8888] [--driver-dir /path/to/drivers]

On first run, generates a self-signed SSL certificate at /app/certs/ (or --cert-dir).
"""

import argparse
import logging
import os
import ssl
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

from proxy.config import ConfigManager
from proxy.dispatcher import Dispatcher
from proxy.handlers.connectivity import ConnectivityHandler
from proxy.handlers.device_driver import DeviceDriverHandler
from proxy.handlers.health import HealthHandler

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
            ">>> %s %s\n    Headers: %s\n    Body length: %d",
            method, self.path, dict(headers), len(body),
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
    dispatcher = build_dispatcher(config, driver_dir=args.driver_dir)

    ProxyRequestHandler.dispatcher = dispatcher

    cert_file, key_file = ensure_ssl_cert(args.cert_dir)

    server = HTTPServer(("127.0.0.1", args.port), ProxyRequestHandler)

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(cert_file, key_file)
    server.socket = ssl_context.wrap_socket(server.socket, server_side=True)

    # Proper TLS shutdown — without this, clients get "unexpected eof" errors
    _original_shutdown = server.shutdown_request

    def _tls_shutdown(request):
        try:
            request.unwrap()
        except (ssl.SSLError, OSError):
            pass
        _original_shutdown(request)

    server.shutdown_request = _tls_shutdown

    logger.info("SAPRO proxy listening on https://127.0.0.1:%d", args.port)
    logger.info("Driver dir: %s", args.driver_dir)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
        server.server_close()


if __name__ == "__main__":
    main()
