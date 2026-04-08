"""
SAPRO HTTP Proxy — listens on specific simulated device IPs, serving CC
requests (device driver downloads, connectivity checks, etc.) without any
SAPRO XMF/forwarder involvement.

Architecture:
    The proxy polls MongoDB (proxy_listeners collection) for device IPs that
    need HTTP/HTTPS service. For each IP, it binds to {ip}:{port} for every
    port in SAPRO_PROXY_PORTS. When CC connects, getsockname() returns the
    device IP — no registration mechanism needed.

    A management listener on 127.0.0.1:8888 (plain HTTP) serves health checks.

    SAPRO handles SNMP only. HTTP/HTTPS for soap-less devices goes through
    this proxy.

Usage:
    python -m proxy.server --driver-dir /path/to/drivers [--ports 80,443]
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
from proxy.dispatcher import Dispatcher
from proxy.handlers.connectivity import ConnectivityHandler
from proxy.handlers.device_driver import DeviceDriverHandler
from proxy.handlers.health import HealthHandler
from proxy.listener_manager import ListenerManager

logger = logging.getLogger("sapro-proxy")

DEFAULT_CERT_DIR = "/app/certs"
MANAGEMENT_PORT = 8888


class ProxyRequestHandler(BaseHTTPRequestHandler):
    """Delegates all requests to the dispatcher, passing device_ip from getsockname()."""

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

        device_ip, local_port = self.request.getsockname()[:2]

        logger.debug(
            ">>> %s %s (device=%s:%d)\n    Headers: %s\n    Body (%d bytes): %s",
            method, self.path, device_ip, local_port, dict(headers), len(body), body,
        )

        status, response_headers, response_body = self.dispatcher.dispatch(
            method, self.path, headers, body, device_ip=device_ip
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


class ManagementRequestHandler(BaseHTTPRequestHandler):
    """Handles management requests (health, reload) on the localhost listener."""

    dispatcher = None

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def _handle(self, method):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""
        headers = {key: self.headers[key] for key in self.headers}

        status, response_headers, response_body = self.dispatcher.dispatch(
            method, self.path, headers, body, device_ip="127.0.0.1"
        )

        self.send_response(status)
        self.send_header("Connection", "close")
        for key, value in response_headers.items():
            self.send_header(key, value)
        self.end_headers()

        if response_body:
            self.wfile.write(response_body)

    def log_message(self, format, *args):
        logger.debug("[mgmt] %s", format % args)


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


def build_main_dispatcher(config, driver_dir):
    """Build the dispatcher for CC-facing traffic."""
    dispatcher = Dispatcher()
    dispatcher.register(HealthHandler(config))
    dispatcher.register(ConnectivityHandler(config))
    dispatcher.register(DeviceDriverHandler(config, driver_dir=driver_dir))
    return dispatcher


def build_management_dispatcher(config):
    """Build the dispatcher for the management listener (health only)."""
    dispatcher = Dispatcher()
    dispatcher.register(HealthHandler(config))
    return dispatcher


def parse_args():
    parser = argparse.ArgumentParser(description="SAPRO HTTP Proxy")
    parser.add_argument(
        "--ports",
        default=os.environ.get("SAPRO_PROXY_PORTS"),
        help="Comma-separated list of ports to listen on (e.g. 80,443)",
    )
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

    if not args.ports:
        logger.error("SAPRO_PROXY_PORTS must be set (comma-separated ports, e.g. 80,443)")
        sys.exit(1)

    mongo_uri = os.environ.get("MONGO_URI")
    mongo_db = os.environ.get("MONGO_DB")
    if not mongo_uri or not mongo_db:
        logger.error("MONGO_URI and MONGO_DB must be set")
        sys.exit(1)

    config = ConfigManager()
    ports = [int(p.strip()) for p in args.ports.split(",")]

    # CC-facing dispatcher (all handlers)
    main_dispatcher = build_main_dispatcher(config, args.driver_dir)
    ProxyRequestHandler.dispatcher = main_dispatcher

    # Management dispatcher (health only, localhost)
    mgmt_dispatcher = build_management_dispatcher(config)
    ManagementRequestHandler.dispatcher = mgmt_dispatcher

    cert_file, key_file = ensure_ssl_cert(args.cert_dir)
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(cert_file, key_file)

    # Management listener on localhost (plain HTTP)
    mgmt_server = HTTPServer(("127.0.0.1", MANAGEMENT_PORT), ManagementRequestHandler)
    mgmt_thread = threading.Thread(target=mgmt_server.serve_forever, daemon=True)
    mgmt_thread.start()
    logger.info("Management listener on 127.0.0.1:%d (HTTP)", MANAGEMENT_PORT)

    # Dynamic listener manager (polls MongoDB)
    manager = ListenerManager(
        ports=ports,
        handler_class=ProxyRequestHandler,
        ssl_context=ssl_context,
        mongo_uri=mongo_uri,
        mongo_db=mongo_db,
    )

    logger.info("SAPRO proxy started (ports %s, management on 127.0.0.1:%d)", ports, MANAGEMENT_PORT)
    logger.info("Driver dir: %s", args.driver_dir)

    try:
        manager.sync()
        manager.run_poll_loop(interval=5)
    except KeyboardInterrupt:
        logger.info("Shutting down")
        manager.shutdown_all()
        mgmt_server.shutdown()
        mgmt_server.server_close()


if __name__ == "__main__":
    main()
