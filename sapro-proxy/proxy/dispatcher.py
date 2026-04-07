import logging

logger = logging.getLogger("sapro-proxy")


class Dispatcher:
    """Routes (method, path) pairs to registered handlers."""

    def __init__(self):
        self._routes = []

    def register(self, handler):
        """Register all routes from a handler."""
        for method, path in handler.routes():
            self._routes.append((method.upper(), path, handler))
            logger.info("Registered route: %s %s -> %s", method, path, type(handler).__name__)

    def dispatch(self, method, path, headers, body):
        """Find and invoke the matching handler.

        Returns:
            tuple: (status_code, headers_dict, body_bytes)
        """
        # Strip query string for route matching
        match_path = path.split("?")[0]

        for route_method, route_path, handler in self._routes:
            if route_method == method.upper() and route_path == match_path:
                return handler.handle(method, path, headers, body)

        # Unhandled paths return 200 empty — mimics real DP behavior for unsupported endpoints.
        # CC expects this; returning 404 causes HTTPS communication errors.
        logger.info("Unhandled request %s %s — returning 200 empty", method, path)
        return 200, {"Server": "Radware-web-server"}, b""
