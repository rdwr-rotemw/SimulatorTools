from enum import Enum


class DeviceStatus(Enum):
    """Device status codes."""

    SHUTDOWN = 1
    LOADING = 2
    OK = 3
    FAILED = 4
    DISABLED = 5
    STOPPING = 6

    @staticmethod
    def get_status(code: int) -> str:
        """Get status name by code."""
        return DeviceStatus(code).name