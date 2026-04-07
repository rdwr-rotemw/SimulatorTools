from proxy.handlers.base import BaseHandler


class ConnectivityHandler(BaseHandler):
    """GET / — CC connectivity check. Must return HTML body like real DP."""

    def routes(self):
        return [("GET", "/")]

    def handle(self, method, path, headers, body):
        return 200, {
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Content-Type": "text/html",
            "Server": "Radware-web-server",
        }, b"<html><body>No Content</body></html>"
