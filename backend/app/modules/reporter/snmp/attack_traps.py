import logging
import random
from enum import Enum

from backend.app.modules.reporter.snmp.executor import execute_sapro_command

logger = logging.getLogger("sim-tools.attack_traps")


class ATTACK_CATEGORY(str, Enum):
    unassigned = "unassigned"
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
    Connection_PPS = "ConnectionPPS"
    QUANTILE_DoS = "Quantile-DoS"
    L7APP_SIG = "L7AppSig"
    WEB_DDOS = "Web-DDoS"


class ATTACK_PROTOCOL(str, Enum):
    IP = "IP"
    TCP = "TCP"
    UDP = "UDP"
    ICMP = "ICMP"
    NON_IP = "Non-IP"
    SCTP = "SCTP"
    ICMPV6 = "ICMPv6"


class ATTACK_STATUS(str, Enum):
    DISCRETE = "discrete"
    START = "start"
    ONGOING = "ongoing"
    TERM = "term"
    OCCUR = "occur"
    LIMITED = "limited"
    SAMPLED = "sampled"
    AGGREGATED = "aggregated"
    AGGRESSIVE = "aggressive"


class ATTACK_RISK(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    NA = "N/A"


class ATTACK_ACTION(str, Enum):
    FORWARD = "forward"
    CHALLENGE = "challenge"
    DROP = "drop"
    source_reset = "source-reset"
    dest_reset = "dest-reset"
    source_dest_reset = "source-dest-reset"
    app_reset = "app-reset"
    quarantine = "quarantine"
    drop_and_quarantine = "drop-and-quarantine"
    http_200_ok = "http-200-ok"
    HTTP_200_OK_RESET_DEST = "http-200-ok-reset-dest"
    http_403_forbidden = "http-403-forbidden"
    http_403_forbidden_reset_dest = "http-403-forbidden-reset-dest"


class ATTACK_DIRECTION(str, Enum):
    UNKNOWN = "unknown"
    IN = "in"
    OUT = "out"


def send_attack_traps(cc_ip, device_ip, payload):
    """Send attack traps to CyberController.

    Supports optional 'pause' field in each trap to wait between traps.
    Returns:
        Tuple of (success_count: int, failed_count: int, total_count: int)
    """
    import time

    success_count = 0
    failed_count = 0
    total_traps = len(payload['traps'])

    for index, trap in enumerate(payload['traps'], start=1):
        command_to_send = (f'/opt/sapro/bin/sapcnsl -m DefensePros.map -c tcl -d {device_ip} '
                           f'-f /opt/sapro/util/send_attack.tcl -a '
                           f'\"{set_trap_string_to_send(cc_ip, trap)}\"')
        success, output = execute_sapro_command(command_to_send)
        attack_name = trap['attackName']

        if success and "Trap(s) Sent" in output:
            logger.info(f"Successfully sent trap {index}/{total_traps} of attack: {attack_name} from: {device_ip} to: {cc_ip}")
            success_count += 1
        else:
            logger.error(f"Failed to send trap {index}/{total_traps} of attack: {attack_name} from: {device_ip} to: {cc_ip}: {output}")
            failed_count += 1

        # Handle pause after sending trap (if not the last trap)
        pause_seconds = trap.get('pause')
        if pause_seconds is not None and pause_seconds > 0 and index < total_traps:
            logger.info(f"Pausing for {pause_seconds} seconds before next trap ({index}/{total_traps})")
            time.sleep(pause_seconds)

    total_count = success_count + failed_count
    return success_count, failed_count, total_count


def generate_radware_id():
    return str(random.randint(1, 999999))


def generate_attack_id():
    part1 = random.randint(100, 999)
    part2 = int(random.random() * 1_000_000_0000)
    return f"{part1}-{part2:010d}"


def set_trap_string_to_send(cc_ip, trap):
    """
    Build trap string with defaults and validation.

    Supports both enum member names (e.g., "BEHAVIORAL_DOS") and direct values (e.g., "Behavioral-DoS").

    Args:
        cc_ip: CyberController IP address
        trap: Dictionary containing trap data

    Returns:
        Comma-separated string for Sapro command

    Raises:
        ValueError: If required fields are missing
    """
    # Validate required fields
    if "attackName" not in trap:
        raise ValueError("Missing required field: attackName")
    if "policy" not in trap:
        raise ValueError("Missing required field: policy")

    # Generate or extract IDs
    attack_id = trap.get("attackId", generate_attack_id())
    radware_id = trap.get("radwareId", generate_radware_id())

    # Get attack name (required)
    attack_name = trap["attackName"]

    # Get policy (required)
    policy = trap["policy"]

    # Get attackCategory with enum conversion (required, but has default)
    try:
        category_input = trap.get("attackCategory")
        if category_input:
            # Try to convert enum member name to value
            try:
                category = ATTACK_CATEGORY[category_input].value
            except KeyError:
                # Not an enum member name, use as-is (assume it's the direct value)
                category = category_input
        else:
            category = ATTACK_CATEGORY.BEHAVIORAL_DOS.value
    except Exception as e:
        category = trap.get("attackCategory", ATTACK_CATEGORY.BEHAVIORAL_DOS.value)
        logger.warning(f"Error processing attackCategory '{trap.get('attackCategory')}': {e}, using raw/default value")

    # Get protocol with enum conversion and default
    try:
        protocol_input = trap.get("protocol")
        if protocol_input:
            # Try to convert enum member name to value
            try:
                protocol = ATTACK_PROTOCOL[protocol_input].value
            except KeyError:
                # Not an enum member name, use as-is (assume it's the direct value)
                protocol = protocol_input
        else:
            protocol = ATTACK_PROTOCOL.TCP.value
    except Exception as e:
        protocol = trap.get("protocol", ATTACK_PROTOCOL.TCP.value)
        logger.warning(f"Error processing protocol '{trap.get('protocol')}': {e}, using raw/default value")

    # Get IPs and ports with defaults
    src_ip = trap.get("srcIp", "0.0.0.0")
    src_port = trap.get("srcPort", "80")
    dst_ip = trap.get("dstIp", "0.0.0.0")
    dst_port = trap.get("dstPort", "80")
    physical_port = trap.get("physicalPort", "1")

    # Get status with enum conversion and default
    try:
        status_input = trap.get("status")
        if status_input:
            # Try to convert enum member name to value
            try:
                status = ATTACK_STATUS[status_input].value
            except KeyError:
                # Not an enum member name, use as-is (assume it's the direct value)
                status = status_input
        else:
            status = ATTACK_STATUS.ONGOING.value
    except Exception as e:
        status = trap.get("status", ATTACK_STATUS.ONGOING.value)
        logger.warning(f"Error processing status '{trap.get('status')}': {e}, using raw/default value")

    # Get traffic metrics with defaults
    packet_count = trap.get("packetCount", "1000")
    packet_bandwidth = trap.get("packetBandwidth", "2000")
    samples = trap.get("samples", "0-0-0")

    # Get risk with enum conversion and default
    try:
        risk_input = trap.get("risk")
        if risk_input:
            # Try to convert enum member name to value
            try:
                risk = ATTACK_RISK[risk_input].value
            except KeyError:
                # Not an enum member name, use as-is (assume it's the direct value)
                risk = risk_input
        else:
            risk = ATTACK_RISK.MEDIUM.value
    except Exception as e:
        risk = trap.get("risk", ATTACK_RISK.MEDIUM.value)
        logger.warning(f"Error processing risk '{trap.get('risk')}': {e}, using raw/default value")

    # Get action with enum conversion and default
    # Note: handle legacy 'actions' vs 'action' field
    action_input = trap.get("action")
    if "actions" in trap and not action_input:
        logger.warning("Found 'actions' field instead of 'action' - using 'actions' value")
        action_input = trap.get("actions")

    try:
        if action_input:
            # Try to convert enum member name to value
            try:
                action = ATTACK_ACTION[action_input].value
            except KeyError:
                # Not an enum member name, use as-is (assume it's the direct value)
                action = action_input
        else:
            action = ATTACK_ACTION.DROP.value
    except Exception as e:
        action = trap.get("action", ATTACK_ACTION.DROP.value)
        logger.warning(f"Error processing action '{action_input}': {e}, using raw/default value")

    # Get direction with enum conversion and default
    try:
        direction_input = trap.get("direction")
        if direction_input:
            # Try to convert enum member name to value
            try:
                direction = ATTACK_DIRECTION[direction_input].value
            except KeyError:
                # Not an enum member name, use as-is (assume it's the direct value)
                direction = direction_input
        else:
            direction = ATTACK_DIRECTION.IN.value
    except Exception as e:
        direction = trap.get("direction", ATTACK_DIRECTION.IN.value)
        logger.warning(f"Error processing direction '{trap.get('direction')}': {e}, using raw/default value")


    # Build comma-separated string
    # Field order: trapManager, attackId, radwareId, attackCategory, attackName, protocol,
    #              srcIp, srcPort, dstIp, dstPort, physicalPort, policy, status,
    #              packetCount, packetBandwidth, samples, risk, action, direction
    return (f'{cc_ip},{attack_id},{radware_id},{category},{attack_name},{protocol},'
            f'{src_ip},{src_port},{dst_ip},{dst_port},{physical_port},{policy},{status},'
            f'{packet_count},{packet_bandwidth},{samples},{risk},{action},{direction}')


def send_attack_traps_with_progress(cc_ip, device_ip, payload):
    """Send attack traps to CyberController with progress reporting.

    Yields progress dictionaries for each trap and completion.

    Supports optional 'pause' field in each trap to wait between traps.

    Yields:
        {"type": "progress", "current": index, "total": total_traps, "trap_name": attack_name, "status": "success" or "failed"}
        {"type": "complete", "success_count": X, "failed_count": Y, "total_count": Z}
    """
    import time

    success_count = 0
    failed_count = 0
    total_traps = len(payload['traps'])

    for index, trap in enumerate(payload['traps'], start=1):
        command_to_send = (f'/opt/sapro/bin/sapcnsl -m DefensePros.map -c tcl -d {device_ip} '
                           f'-f /opt/sapro/util/send_attack.tcl -a '
                           f'\"{set_trap_string_to_send(cc_ip, trap)}\"')
        success, output = execute_sapro_command(command_to_send)
        attack_name = trap['attackName']

        if success and "Trap(s) Sent" in output:
            logger.info(f"Successfully sent trap {index}/{total_traps} of attack: {attack_name} from: {device_ip} to: {cc_ip}")
            success_count += 1
            status = "success"
        else:
            logger.error(f"Failed to send trap {index}/{total_traps} of attack: {attack_name} from: {device_ip} to: {cc_ip}: {output}")
            failed_count += 1
            status = "failed"

        yield {"type": "progress", "current": index, "total": total_traps, "trap_name": attack_name, "status": status}

        # Handle pause after sending trap (if not the last trap)
        pause_seconds = trap.get('pause')
        if pause_seconds is not None and pause_seconds > 0 and index < total_traps:
            logger.info(f"Pausing for {pause_seconds} seconds before next trap ({index}/{total_traps})")
            time.sleep(pause_seconds)

    total_count = success_count + failed_count
    yield {"type": "complete", "success_count": success_count, "failed_count": failed_count, "total_count": total_count}
