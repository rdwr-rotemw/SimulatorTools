"""
Dynamic listener manager — polls MongoDB for device IPs that need HTTP/HTTPS
proxy service and creates/destroys per-IP listeners accordingly.

Each device IP gets one HTTPServer per configured port, all sharing the same
dispatcher and TLS context. Listeners are started in daemon threads and
shut down cleanly when the device is removed from the database.
"""

import logging
import ssl
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List

from pymongo import MongoClient

logger = logging.getLogger("sapro-proxy")

COLLECTION_NAME = "proxy_listeners"


class ListenerManager:
    """Manages dynamic per-IP HTTPS listeners driven by MongoDB."""

    def __init__(
        self,
        ports: List[int],
        handler_class: type,
        ssl_context: ssl.SSLContext,
        mongo_uri: str,
        mongo_db: str,
    ):
        self.ports = ports
        self.handler_class = handler_class
        self.ssl_context = ssl_context
        self.active_listeners: Dict[str, List[HTTPServer]] = {}

        client = MongoClient(mongo_uri)
        self.collection = client[mongo_db][COLLECTION_NAME]
        self.collection.create_index("device_ip", unique=True)
        logger.info("ListenerManager connected to MongoDB %s/%s", mongo_uri, mongo_db)

    def sync(self):
        """Poll MongoDB and sync listeners with the desired state."""
        desired_ips = {
            doc["device_ip"]
            for doc in self.collection.find({}, {"device_ip": 1, "_id": 0})
        }
        current_ips = set(self.active_listeners.keys())

        # Start listeners for new IPs
        for ip in desired_ips - current_ips:
            self._start_listener(ip)

        # Stop listeners for removed IPs
        for ip in current_ips - desired_ips:
            self._stop_listener(ip)

    def _start_listener(self, device_ip: str):
        """Create and start HTTPS servers for a device IP on all configured ports."""
        servers = []
        for port in self.ports:
            try:
                server = HTTPServer((device_ip, port), self.handler_class)
                server.socket = self.ssl_context.wrap_socket(
                    server.socket, server_side=True
                )

                original_shutdown = server.shutdown_request

                def make_tls_shutdown(orig):
                    def _tls_shutdown(request):
                        try:
                            request.unwrap()
                        except (ssl.SSLError, OSError):
                            pass
                        orig(request)
                    return _tls_shutdown

                server.shutdown_request = make_tls_shutdown(original_shutdown)

                thread = threading.Thread(
                    target=server.serve_forever, daemon=True
                )
                thread.start()
                servers.append(server)
                logger.info("Started listener on %s:%d (HTTPS)", device_ip, port)
            except OSError as e:
                logger.error(
                    "Failed to bind %s:%d — %s", device_ip, port, e
                )
                # Clean up any servers we already started for this IP
                for s in servers:
                    s.shutdown()
                    s.server_close()
                return

        self.active_listeners[device_ip] = servers
        logger.info(
            "Device %s: listening on ports %s", device_ip, self.ports
        )

    def _stop_listener(self, device_ip: str):
        """Shut down all servers for a device IP."""
        servers = self.active_listeners.pop(device_ip, [])
        for server in servers:
            server.shutdown()
            server.server_close()
        if servers:
            logger.info("Stopped listeners for %s", device_ip)

    def run_poll_loop(self, interval: int = 5):
        """Block forever, polling MongoDB every `interval` seconds."""
        logger.info(
            "Polling MongoDB every %ds for listener changes", interval
        )
        while True:
            try:
                self.sync()
            except Exception as e:
                logger.error("Listener sync failed: %s", e)
            time.sleep(interval)

    def shutdown_all(self):
        """Shut down all active listeners."""
        for ip in list(self.active_listeners.keys()):
            self._stop_listener(ip)
