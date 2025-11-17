from pysnmp.hlapi import *
from typing import Optional, Tuple


class SnmpClient:
    def __init__(self, host: str, port: int = 161, community: str = 'public'):
        self.host = host
        self.port = port
        self.community = community
        self.engine = SnmpEngine()

    def get(self, oid: str) -> Optional[str]:
        """Synchronous SNMP GET"""
        try:
            iterator = getCmd(
                self.engine,
                CommunityData(self.community),
                UdpTransportTarget((self.host, self.port), timeout=2),
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )

            error_indication, error_status, error_index, var_binds = next(iterator)

            if error_indication or error_status:
                return None

            _, value = var_binds[0]
            return str(value)
        except Exception as e:
            print(f"Error: {e}")
            return None


# Usage - pure sync, no async needed
def snmp_get_device_info(self, device_ip: str) -> Tuple[Optional[str], Optional[str]]:
    """Retrieve device type and version via SNMP."""
    snmp_client = SnmpClient(device_ip)

    device_type = snmp_client.get("1.3.6.1.2.1.1.1.0")
    if device_type and "DefensePro" in device_type:
        version = snmp_client.get("1.3.6.1.2.1.25.3.2.1.5.1")
        device_type = "DefensePro"
    elif device_type and "Application" in device_type:
        version = snmp_client.get("1.3.6.1.2.1.1.1.0")
        device_type = "Alteon"
    else:
        device_type = None
        version = None

    return device_type, version