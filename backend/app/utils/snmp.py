from typing import Optional
import subprocess
import ipaddress

from backend.app.utils.logger import logger


class SnmpClient:
    def __init__(self, host: str, port: int = 161, community: str = 'public'):
        self.host = host
        self.port = port
        self.community = community

    def get(self, oid: str) -> Optional[str]:
        """Use native snmpget command for speed.

        Supports both IPv4 and IPv6 textual addresses. Hostnames are treated as
        IPv4/host targets.

        Returns the value string on success or None on failure/timeouts.
        """
        try:
            # Detect if host is an IPv6 literal
            try:
                ip_obj = ipaddress.ip_address(self.host)
                is_ipv6 = isinstance(ip_obj, ipaddress.IPv6Address)
            except ValueError:
                # Not a literal IP (probably a hostname) - assume not IPv6
                is_ipv6 = False

            # Build target for snmpget; for IPv6 we need udp6:[addr]:port
            if is_ipv6:
                target = f"udp6:[{self.host}]:{self.port}"
            else:
                target = f"{self.host}:{self.port}"

            result = subprocess.run(
                ['snmpget', '-v2c', '-c', self.community, target, oid],
                capture_output=True,
                text=True,
                timeout=1
            )

            if result.returncode != 0:
                logger.debug(f"snmpget returned non-zero for {target} oid={oid}: {result.stderr.strip()}")
                return None

            output = result.stdout.strip()
            if not output:
                return None

            # Expected format: "SNMPv2-MIB::sysDescr.0 = STRING: DefensePro ..."
            if '=' in output:
                value = output.split('=', 1)[1].strip()
                # Remove type prefix like "STRING: " or "INTEGER: "
                if ':' in value:
                    value = value.split(':', 1)[1].strip()
                # Remove surrounding quotes
                value = value.strip('"').strip("'")
                return value

            return None

        except Exception as e:
            logger.debug(f"snmpget failed for {self.host}:{self.port} oid={oid}: {type(e).__name__}: {e}")
            return None
