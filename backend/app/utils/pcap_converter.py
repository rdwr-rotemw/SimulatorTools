"""
PCAP to SNMP Trap JSON converter module.
Parses PCAP files for Radware SNMP traps and converts them to structured JSON format.
"""

import shlex
import logging
from typing import List, Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class AttackCategory(Enum):
    UNASSIGNED = "unassigned"
    INTRUSIONS = "Intrusions"
    DOS = "DoS"
    ANOMALIES = "Anomalies"
    ANTI_SCANNING = "Anti-Scanning"
    BEHAVIORAL_DOS = "Behavioral-DoS"
    SYN_FLOOD = "SynFlood"
    ACCESS = "Access"
    HTTP_FLOOD = "HttpFlood"
    CRACKING_PROTECTION = "Cracking-Protection"
    STATEFUL_ACL = "Stateful-ACL"
    SESSION_TABLE_PROTECTION = "Session-Table-Protection"
    BWM = "BWM"
    DNS_PROTECTION = "DNS-Protection"
    TRAFFIC_FILTERS = "Traffic-Filters"
    HTTPS = "Https"
    GEO_FEED = "GeoFeed"
    ERT_FEED = "ErtFeed"
    CONNECTION_PPS = "ConnectionPPS"
    QUANTILE_DOS = "Quantile-DoS"
    L7APP_SIG = "L7AppSig"
    WEB_DDOS = "Web-DDoS"

    def get_value(self) -> str:
        return self.value

    @classmethod
    def from_value(cls, value: str) -> Optional[str]:
        """Convert string value to enum name, return None if not found"""
        for item in cls:
            if item.value == value:
                return item.name
        return None


class AttackProtocol(Enum):
    IP = "IP"
    TCP = "TCP"
    UDP = "UDP"
    ICMP = "ICMP"
    NON_IP = "Non-IP"
    SCTP = "SCTP"
    ICMPV6 = "ICMPv6"

    def get_value(self) -> str:
        return self.value

    @classmethod
    def from_value(cls, value: str) -> Optional[str]:
        for item in cls:
            if item.value == value:
                return item.name
        return None


class AttackStatus(Enum):
    DISCRETE = "discrete"
    START = "start"
    ONGOING = "ongoing"
    TERM = "term"
    OCCUR = "occur"
    LIMITED = "limited"
    SAMPLED = "sampled"
    AGGREGATED = "aggregated"
    AGGRESSIVE = "aggressive"

    def get_value(self) -> str:
        return self.value

    @classmethod
    def from_value(cls, value: str) -> Optional[str]:
        for item in cls:
            if item.value == value:
                return item.name
        return None


class AttackRisk(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    NA = "N/A"

    def get_value(self) -> str:
        return self.value

    @classmethod
    def from_value(cls, value: str) -> Optional[str]:
        for item in cls:
            if item.value == value:
                return item.name
        return None


class AttackAction(Enum):
    FORWARD = "forward"
    CHALLENGE = "challenge"
    DROP = "drop"
    SOURCE_RESET = "source-reset"
    DEST_RESET = "dest-reset"
    SOURCE_DEST_RESET = "source-dest-reset"
    APP_RESET = "app-reset"
    QUARANTINE = "quarantine"
    DROP_AND_QUARANTINE = "drop-and-quarantine"
    HTTP_200_OK = "http-200-ok"
    HTTP_200_OK_RESET_DEST = "http-200-ok-reset-dest"
    HTTP_403_FORBIDDEN = "http-403-forbidden"
    HTTP_403_FORBIDDEN_RESET_DEST = "http-403-forbidden-reset-dest"

    def get_value(self) -> str:
        return self.value

    @classmethod
    def from_value(cls, value: str) -> Optional[str]:
        for item in cls:
            if item.value == value:
                return item.name
        return None


class AttackDirection(Enum):
    UNKNOWN = "unknown"
    IN = "in"
    OUT = "out"

    def get_value(self) -> str:
        return self.value

    @classmethod
    def from_value(cls, value: str) -> Optional[str]:
        for item in cls:
            if item.value == value:
                return item.name
        return None


class PcapParseError(Exception):
    """Raised when PCAP parsing fails"""
    pass


def extract_snmp_values(pcap_file: str) -> List[str]:
    """
    Extract Radware SNMP trap values from PCAP file.

    Args:
        pcap_file: Path to PCAP file

    Returns:
        List of trap strings extracted from SNMP OIDs

    Raises:
        PcapParseError: If PCAP parsing fails or dependencies missing
    """
    try:
        import pyshark
    except ImportError:
        raise PcapParseError(
            "pyshark is not installed. Please install it: pip install pyshark"
        )

    values = []

    try:
        # Open pcap file with SNMP filter
        cap = pyshark.FileCapture(pcap_file, display_filter="snmp")

        for packet in cap:
            try:
                # Look for packets with SNMP data
                if not hasattr(packet, 'snmp'):
                    continue

                # Search for Radware-specific OID
                for field, value in packet.snmp._all_fields.items():
                    # OID: 1.3.6.1.4.1.89.35.1.65.107.1.1.0 for Radware traps
                    if "1.3.6.1.4.1.89.35.1.65.107.1.1.0" in str(value):
                        # Extract the trap string (after OID prefix and surrounding quotes)
                        trap_value = str(value).replace(
                            '1.3.6.1.4.1.89.35.1.65.107.1.1.0: "V_8', ""
                        ).rstrip('"')

                        if trap_value:  # Only add non-empty values
                            values.append(trap_value)

            except (AttributeError, KeyError):
                # Skip packets that don't have expected SNMP structure
                continue

        cap.close()

        if not values:
            logger.warning(f"No SNMP traps found in PCAP: {pcap_file}")

        return values

    except FileNotFoundError:
        raise PcapParseError(f"PCAP file not found: {pcap_file}")
    except Exception as e:
        raise PcapParseError(f"Failed to parse PCAP file: {str(e)}")


def trap_to_json(trap: str) -> Dict[str, Any]:
    """
    Convert a trap string to structured JSON/dict format.

    Args:
        trap: Trap string from SNMP OID

    Returns:
        Dictionary with trap data

    Raises:
        PcapParseError: If trap format is invalid
    """
    try:
        split_trap = shlex.split(trap)

        # Validate minimum required fields
        if len(split_trap) < 23:
            raise ValueError(f"Trap has insufficient fields: {len(split_trap)} < 23")

        attack_trap = {
            'attackId': split_trap[0],
            'radwareId': split_trap[1],
            'attackCategory': AttackCategory.from_value(split_trap[2]),
            'attackName': split_trap[3],
            'protocol': AttackProtocol.from_value(split_trap[4]),
            'srcIp': split_trap[5],
            'srcPort': split_trap[6],
            'dstIp': split_trap[7],
            'dstPort': split_trap[8],
            'physicalPort': split_trap[9],
            'policy': split_trap[11],  # Note: index 10 is skipped
            'status': AttackStatus.from_value(split_trap[12]),
            'packetCount': split_trap[13],
            'packetBandwidth': split_trap[14],
            'samples': split_trap[15],
            'risk': AttackRisk.from_value(split_trap[16]),
            'action': AttackAction.from_value(split_trap[17]),
            'direction': AttackDirection.from_value(split_trap[22]),
        }

        return attack_trap

    except (ValueError, IndexError) as e:
        raise PcapParseError(f"Invalid trap format: {str(e)}")
    except Exception as e:
        raise PcapParseError(f"Failed to parse trap: {str(e)}")


def pcap_to_traps(pcap_file: str, max_traps: int = 50) -> Dict[str, Any]:
    """
    Convert PCAP file to list of trap dictionaries.

    Args:
        pcap_file: Path to PCAP file
        max_traps: Maximum number of traps to extract (default: 50)

    Returns:
        Dictionary with:
        - traps: List of parsed trap dictionaries
        - total_extracted: Total traps found
        - total_returned: Number of traps returned
        - truncated: Boolean indicating if results were truncated
        - errors: List of any parse errors encountered

    Raises:
        PcapParseError: If PCAP parsing fails
    """
    logger.info(f"Parsing PCAP file: {pcap_file}")

    snmp_traps = extract_snmp_values(pcap_file)
    logger.info(f"Found {len(snmp_traps)} SNMP trap strings")

    trap_list = []
    errors = []

    for idx, trap in enumerate(snmp_traps):
        # Stop if we've reached the max
        if idx >= max_traps:
            logger.warning(f"Maximum trap limit ({max_traps}) reached, truncating results")
            break

        try:
            parsed_trap = trap_to_json(trap)
            trap_list.append(parsed_trap)
        except PcapParseError as e:
            error_msg = f"Error parsing trap {idx + 1}: {str(e)}"
            logger.error(error_msg)
            errors.append({
                'trap_index': idx,
                'error': str(e),
                'trap_preview': trap[:100]  # First 100 chars for debugging
            })

    result = {
        'traps': trap_list,
        'total_extracted': len(snmp_traps),
        'total_returned': len(trap_list),
        'truncated': len(snmp_traps) > max_traps,
        'errors': errors
    }

    logger.info(f"Parsed {len(trap_list)} traps successfully")

    return result