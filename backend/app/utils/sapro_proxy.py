"""
Utilities for managing the SAPRO HTTP proxy's driver_map.json configuration.

The driver_map.json file maps device IPs to JAR filenames. It lives alongside
the JAR files in the device driver storage directory (shared volume in production).

SAPRO's SA_xml_request_forwarder replaces the Host header with 127.0.0.1,
so the proxy cannot identify devices from the forwarded request. This mapping
is the only way to resolve which JAR to serve for which device.
"""

import json
import os

from backend.app.utils.device_driver import DEVICE_DRIVER_STORAGE_PATH
from backend.app.utils.logger import logger

DRIVER_MAP_FILENAME = "driver_map.json"
DRIVER_MAP_PATH = os.path.join(DEVICE_DRIVER_STORAGE_PATH, DRIVER_MAP_FILENAME)


def _read_driver_map() -> dict:
    """Read the current driver_map.json."""
    if not os.path.exists(DRIVER_MAP_PATH):
        return {}
    with open(DRIVER_MAP_PATH, "r") as f:
        return json.load(f)


def _write_driver_map(driver_map: dict) -> None:
    """Write driver_map.json."""
    with open(DRIVER_MAP_PATH, "w") as f:
        json.dump(driver_map, f, indent=2)
    logger.info("Updated driver_map.json at %s", DRIVER_MAP_PATH)


def update_driver_map(device_ip: str, jar_filename: str) -> None:
    """Add or update a device IP -> JAR filename mapping."""
    driver_map = _read_driver_map()
    driver_map[device_ip] = jar_filename
    _write_driver_map(driver_map)
    logger.info("Mapped device %s -> %s", device_ip, jar_filename)


def remove_driver_mapping(device_ip: str) -> None:
    """Remove a device IP mapping."""
    driver_map = _read_driver_map()
    if device_ip in driver_map:
        removed = driver_map.pop(device_ip)
        _write_driver_map(driver_map)
        logger.info("Removed mapping for device %s (was %s)", device_ip, removed)


def get_driver_map() -> dict:
    """Return the current driver map."""
    return _read_driver_map()
