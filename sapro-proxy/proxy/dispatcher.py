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
        for route_method, route_path, handler in self._routes:
            if route_method == method.upper() and route_path == path:
                return handler.handle(method, path, headers, body)

        return 404, {}, b""
