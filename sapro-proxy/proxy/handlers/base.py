from abc import ABC, abstractmethod


class BaseHandler(ABC):
    """Base class for all proxy request handlers."""

    def __init__(self, config, **kwargs):
        self.config = config
        for key, value in kwargs.items():
            setattr(self, key, value)

    @abstractmethod
    def handle(self, method, path, headers, body, *, device_ip):
        """Handle an HTTP request.

        Args:
            device_ip: Target device IP from socket getsockname().

        Returns:
            tuple: (status_code: int, headers: dict, body: bytes)
        """

    @abstractmethod
    def routes(self):
        """Return list of (method, path) tuples this handler serves."""
