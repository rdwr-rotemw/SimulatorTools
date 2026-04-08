"""Manage the proxy_listeners MongoDB collection.

Devices without a SOAP section need the sapro-proxy to handle HTTP/HTTPS
traffic directly. This module provides helpers to register/unregister
device IPs in the collection that the proxy polls.
"""

import logging

from backend.app.utils.database import get_mongo_db

logger = logging.getLogger(__name__)

COLLECTION_NAME = "proxy_listeners"


def register_proxy_listener(device_ip: str) -> None:
    """Add a device IP to the proxy listeners collection."""
    db = get_mongo_db()
    db[COLLECTION_NAME].update_one(
        {"device_ip": device_ip},
        {"$set": {"device_ip": device_ip}},
        upsert=True,
    )
    logger.info("Registered proxy listener for %s", device_ip)


def unregister_proxy_listener(device_ip: str) -> None:
    """Remove a device IP from the proxy listeners collection."""
    db = get_mongo_db()
    result = db[COLLECTION_NAME].delete_one({"device_ip": device_ip})
    if result.deleted_count:
        logger.info("Unregistered proxy listener for %s", device_ip)


def template_has_soap(template_dict: dict) -> bool:
    """Check if a template dict contains a SOAP section with any fields."""
    device = template_dict.get("device_map", {}).get("device", {})
    soap = device.get("soap", {})
    return bool(soap)
