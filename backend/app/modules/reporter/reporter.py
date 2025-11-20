"""
Reporter integration entry points.

These functions define the interface your API routes call. The SNMP trap
functionality is integrated with the attack_traps module. IRP and Polling
are TODO stubs awaiting implementation.
"""
from typing import Any, Dict, Tuple
import logging

from backend.app.modules.reporter.snmp import attack_traps

logger = logging.getLogger("sim-tools.reporter")


def send_snmp_trap(cc_ip: str, device_ip: str, trap_data: Dict[str, Any]) -> Tuple[bool, str]:
    """Send SNMP trap(s) to CyberController.

    Args:
        cc_ip: CyberController IP address
        device_ip: Source device IP address
        trap_data: Dictionary containing trap configuration (must include 'traps' key)

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Validate trap_data structure
        if not trap_data or 'traps' not in trap_data:
            logger.error("Invalid trap_data: missing 'traps' key")
            return False, "Invalid trap data: 'traps' key is required"

        if not isinstance(trap_data['traps'], list) or not trap_data['traps']:
            logger.error("Invalid trap_data: 'traps' must be a non-empty list")
            return False, "Invalid trap data: 'traps' must be a non-empty list"

        # Call the attack_traps module to send traps
        logger.info(f"Sending {len(trap_data['traps'])} trap(s) from {device_ip} to {cc_ip}")
        attack_traps.send_attack_traps(cc_ip, device_ip, trap_data)

        # Note: send_attack_traps logs individual trap results but doesn't return status
        # We'll consider it successful if no exception was raised
        logger.info(f"Successfully sent {len(trap_data['traps'])} trap(s)")
        return True, f"Traps sent successfully ({len(trap_data['traps'])} trap(s))"

    except KeyError as exc:
        # Missing required keys in trap_data
        logger.error(f"Invalid trap configuration: {exc!s}")
        return False, f"Invalid trap configuration: missing key {exc!s}"
    except Exception as exc:
        # Catch-all for unexpected errors
        logger.exception(f"Failed to send SNMP traps: {exc!s}")
        return False, f"Failed to send traps: {exc!s}"


def send_irp_message(message_data: Dict[str, Any], cc_ip: str, device_ip: str, sapro_server) -> Tuple[bool, str]:
    """Send an IRP message to CyberController.

    Args:
        message_data: Dictionary containing IRP message configuration
        cc_ip: CyberController IP address
        device_ip: Source device IP address
        sapro_server: Sapro server connection object

    Returns:
        Tuple of (success: bool, message: str)
    """
    # TODO: integrate with real IRP module
    logger.warning("IRP message functionality not yet implemented")
    return False, "IRP message functionality not implemented yet"


def send_polling(config_data: Dict[str, Any], cc_ip: str, device_ip: str, sapro_server) -> Tuple[bool, str]:
    """Push polling configuration to target simulator.

    Args:
        config_data: Dictionary containing polling configuration
        cc_ip: CyberController IP address
        device_ip: Target device IP address
        sapro_server: Sapro server connection object

    Returns:
        Tuple of (success: bool, message: str)
    """
    # TODO: integrate with real polling module
    logger.warning("Polling configuration functionality not yet implemented")
    return False, "Polling functionality not implemented yet"


__all__ = ["send_snmp_trap", "send_irp_message", "send_polling"]



