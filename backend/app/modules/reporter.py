"""
Reporter integration entry points (stubs).

These functions define the interface your API routes call. When you
integrate the actual reporting implementations (SNMP, IRP, Polling),
replace the TODO blocks to call into your real modules.
"""
from typing import Any, Dict

# Placeholder imports: when you add actual implementations, import them here
# from external_modules import snmp_module, irp_module, polling_module


def send_snmp_trap(trap_data: Dict[str, Any], target_ip: str) -> Dict[str, Any]:
    """Send an SNMP trap to the target IP.

    Expected to call: snmp_module.send_trap(trap_data, target_ip)
    Return a dict with operation result/status.
    """
    # TODO: integrate with real snmp_module
    return {"status": "not_implemented", "target": target_ip}


def send_irp_message(message_data: Dict[str, Any], target_ip: str) -> Dict[str, Any]:
    """Send an IRP message to the target IP.

    Expected to call: irp_module.send_message(message_data, target_ip)
    """
    # TODO: integrate with real irp_module
    return {"status": "not_implemented", "target": target_ip}


def send_polling(config_data: Dict[str, Any], target_ip: str) -> Dict[str, Any]:
    """Push polling configuration to target simulator.

    Expected to call: polling_module.send_config(config_data, target_ip)
    """
    # TODO: integrate with real polling_module
    return {"status": "not_implemented", "target": target_ip}


__all__ = ["send_snmp_trap", "send_irp_message", "send_polling"]

