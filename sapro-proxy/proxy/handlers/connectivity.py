from proxy.handlers.base import BaseHandler


class ConnectivityHandler(BaseHandler):
    """GET / — CC connectivity check. Real DP returns 200 with no-cache headers, empty body."""

    def routes(self):
        return [("GET", "/")]

    def handle(self, method, path, headers, body):
        return 200, {
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
        }, b""
