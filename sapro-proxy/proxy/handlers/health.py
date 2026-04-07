import json
import time

from proxy.handlers.base import BaseHandler

_start_time = time.time()


class HealthHandler(BaseHandler):
    """Management endpoints — not forwarded by SAPRO, used for monitoring."""

    def routes(self):
        return [
            ("GET", "/_health"),
            ("POST", "/_reload"),
        ]

    def handle(self, method, path, headers, body):
        if path == "/_health":
            return self._health()
        if path == "/_reload":
            return self._reload()
        return 404, {}, b""

    def _health(self):
        payload = json.dumps({
            "status": "ok",
            "uptime": round(time.time() - _start_time, 1),
        }).encode()

        return 200, {"Content-Type": "application/json"}, payload

    def _reload(self):
        self.config.reload()
        payload = json.dumps({"status": "reloaded"}).encode()
        return 200, {"Content-Type": "application/json"}, payload
