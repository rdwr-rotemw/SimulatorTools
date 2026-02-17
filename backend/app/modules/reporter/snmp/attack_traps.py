import logging
import random
import time
import uuid
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


def _resolve_enum_field(trap, field_name, enum_class, default_member, legacy_field=None):
    """Resolve an enum field from trap dict: try enum member name, then direct value, then default.

    Args:
        trap: Trap dictionary
        field_name: Key name in trap dict
        enum_class: Enum class to resolve against
        default_member: Default enum member to use
        legacy_field: Optional legacy field name to check as fallback

    Returns:
        Resolved string value
    """
    raw = trap.get(field_name)
    if legacy_field and not raw and legacy_field in trap:
        logger.warning(f"Found '{legacy_field}' field instead of '{field_name}' - using '{legacy_field}' value")
        raw = trap.get(legacy_field)

    try:
        if raw:
            try:
                return enum_class[raw].value
            except KeyError:
                return raw
        else:
            return default_member.value
    except Exception as e:
        logger.warning(f"Error processing {field_name} '{raw}': {e}, using default value")
        return default_member.value


def resolve_trap_fields(cc_ip, trap):
    """Resolve and validate all trap fields, applying defaults and enum conversion.

    Supports both enum member names (e.g., "BEHAVIORAL_DOS") and direct values (e.g., "Behavioral-DoS").

    Args:
        cc_ip: CyberController IP address (used as trap manager)
        trap: Dictionary containing trap data

    Returns:
        Dictionary with all resolved field values

    Raises:
        ValueError: If required fields are missing
    """
    if "attackName" not in trap:
        raise ValueError("Missing required field: attackName")
    if "policy" not in trap:
        raise ValueError("Missing required field: policy")

    return {
        "trap_manager": cc_ip,
        "attack_id": trap.get("attackId", generate_attack_id()),
        "radware_id": trap.get("radwareId", generate_radware_id()),
        "category": _resolve_enum_field(trap, "attackCategory", ATTACK_CATEGORY, ATTACK_CATEGORY.BEHAVIORAL_DOS),
        "attack_name": trap["attackName"],
        "protocol": _resolve_enum_field(trap, "protocol", ATTACK_PROTOCOL, ATTACK_PROTOCOL.TCP),
        "src_ip": trap.get("srcIp", "0.0.0.0"),
        "src_port": trap.get("srcPort", "80"),
        "dst_ip": trap.get("dstIp", "0.0.0.0"),
        "dst_port": trap.get("dstPort", "80"),
        "physical_port": trap.get("physicalPort", "1"),
        "policy": trap["policy"],
        "status": _resolve_enum_field(trap, "status", ATTACK_STATUS, ATTACK_STATUS.ONGOING),
        "packet_count": trap.get("packetCount", "1000"),
        "packet_bandwidth": trap.get("packetBandwidth", "2000"),
        "samples": trap.get("samples", "0-0-0"),
        "risk": _resolve_enum_field(trap, "risk", ATTACK_RISK, ATTACK_RISK.MEDIUM),
        "action": _resolve_enum_field(trap, "action", ATTACK_ACTION, ATTACK_ACTION.DROP, legacy_field="actions"),
        "direction": _resolve_enum_field(trap, "direction", ATTACK_DIRECTION, ATTACK_DIRECTION.IN),
    }


def generate_radware_id():
    return str(random.randint(1, 999999))


def generate_attack_id():
    part1 = random.randint(100, 999)
    part2 = int(random.random() * 1_000_000_0000)
    return f"{part1}-{part2:010d}"


def set_trap_string_to_send(cc_ip, trap):
    """Build comma-separated trap string for send_attack.tcl -a argument.

    Delegates field resolution to resolve_trap_fields() to avoid duplication.

    Args:
        cc_ip: CyberController IP address
        trap: Dictionary containing trap data

    Returns:
        Comma-separated string for Sapro command

    Raises:
        ValueError: If required fields are missing
    """
    f = resolve_trap_fields(cc_ip, trap)
    return (f'{f["trap_manager"]},{f["attack_id"]},{f["radware_id"]},{f["category"]},'
            f'{f["attack_name"]},{f["protocol"]},'
            f'{f["src_ip"]},{f["src_port"]},{f["dst_ip"]},{f["dst_port"]},'
            f'{f["physical_port"]},{f["policy"]},{f["status"]},'
            f'{f["packet_count"]},{f["packet_bandwidth"]},{f["samples"]},'
            f'{f["risk"]},{f["action"]},{f["direction"]}')


def build_sa_sendtrap_line(fields):
    """Build a single SA_sendtrap TCL command line from resolved trap fields.

    The varbind format matches the existing send_attack.tcl output exactly:
    V_8 {attack_id} {radware_id} {category} \"{attack_name}\" {protocol}
    {src_ip} {src_port} {dst_ip} {dst_port} {physical_port} Regular
    \"{policy}\" {status} {packet_count} {packet_bandwidth} {samples}
    {risk} {action} 0 0 19 N/A {direction} 0

    Args:
        fields: Dictionary from resolve_trap_fields()

    Returns:
        A complete SA_sendtrap TCL command string
    """
    # Sanitize fields that get quoted in the varbind (strip double-quotes)
    attack_name = str(fields["attack_name"]).replace('"', '')
    policy = str(fields["policy"]).replace('"', '')

    return (
        f'SA_sendtrap {{ 1.3.6.1.4.1.89.35.1.65.107 6 1 '
        f'{{ rsIDSIntrusionErrorDesc.0 OctetString '
        f'"V_8 {fields["attack_id"]} {fields["radware_id"]} {fields["category"]} '
        f'\\"{attack_name}\\" {fields["protocol"]} '
        f'{fields["src_ip"]} {fields["src_port"]} '
        f'{fields["dst_ip"]} {fields["dst_port"]} '
        f'{fields["physical_port"]} '
        f'Regular '
        f'\\"{policy}\\" {fields["status"]} '
        f'{fields["packet_count"]} {fields["packet_bandwidth"]} '
        f'{fields["samples"]} '
        f'{fields["risk"]} {fields["action"]} '
        f'0 0 19 N/A {fields["direction"]} 0" '
        f'}} {{ rsIDSIntrusionErrorSeverity.0 Integer "2" }} }}'
    )


def build_batch_tcl_content(cc_ip, traps):
    """Build complete TCL script content for batch trap sending.

    Sets the trap manager once, then sends all traps sequentially.
    Pauses between traps are converted to TCL 'after' commands (milliseconds).

    Args:
        cc_ip: CyberController IP address (trap manager destination)
        traps: List of trap dictionaries from payload

    Returns:
        Complete TCL script content as a string

    Raises:
        ValueError: If any trap has invalid/missing required fields
    """
    lines = [f'SA_settrapmgrs {cc_ip}', '']

    total_traps = len(traps)
    for index, trap in enumerate(traps):
        fields = resolve_trap_fields(cc_ip, trap)
        lines.append(build_sa_sendtrap_line(fields))

        # Add pause if specified and not the last trap
        pause_seconds = trap.get('pause')
        if pause_seconds is not None and pause_seconds > 0 and index < total_traps - 1:
            lines.append(f'after {int(pause_seconds * 1000)}')

    return '\n'.join(lines) + '\n'


def send_attack_traps(cc_ip, device_ip, payload):
    """Send attack traps to CyberController using batch execution.

    Generates a single TCL script with all SA_sendtrap calls and executes
    it in one sapcnsl invocation via a temp file, reducing N SSH round-trips to 1.

    Supports optional 'pause' field in each trap (converted to TCL 'after' commands).

    Returns:
        Tuple of (success_count: int, failed_count: int, total_count: int)
    """
    total_traps = len(payload['traps'])
    device_map = payload['map']

    # Build batch TCL content
    try:
        tcl_content = build_batch_tcl_content(cc_ip, payload['traps'])
    except ValueError as e:
        logger.error(f"Failed to build batch TCL content: {e}")
        return 0, total_traps, total_traps

    # Generate unique temp file path
    batch_id = uuid.uuid4().hex[:12]
    temp_tcl_path = f'/tmp/sapro_batch_{batch_id}.tcl'

    # Scale timeout: base 30s + 2s per trap + explicit pause durations
    total_pause = sum(trap.get('pause', 0) or 0 for trap in payload['traps'])
    timeout = max(30, total_traps * 2) + int(total_pause)

    # Step 1: Write TCL script to temp file via heredoc
    # Single-quoted delimiter 'SAPRO_BATCH_EOF' prevents shell variable expansion.
    write_command = (
        f"cat > {temp_tcl_path} << 'SAPRO_BATCH_EOF'\n"
        f"{tcl_content}"
        f"SAPRO_BATCH_EOF"
    )
    logger.info(f"Writing batch TCL script to {temp_tcl_path} ({total_traps} traps)")
    write_success, write_output = execute_sapro_command(write_command, timeout=30)
    if not write_success:
        logger.error(f"Failed to write batch TCL file: {write_output[:500]}")
        return 0, total_traps, total_traps

    # Step 2: Execute the batch TCL script via sapcnsl
    exec_command = (
        f"/opt/sapro/bin/sapcnsl -m {device_map} -c tcl -d {device_ip} "
        f"-f {temp_tcl_path}"
    )
    logger.info(f"Executing batch of {total_traps} trap(s) from {device_ip} to {cc_ip} (timeout={timeout}s)")
    success, output = execute_sapro_command(exec_command, timeout=timeout)
    logger.info(f"Batch execution output: {output[:1000]}")

    # Step 3: Cleanup temp file
    cleanup_command = f"rm -f {temp_tcl_path}"
    execute_sapro_command(cleanup_command, timeout=10)

    if success:
        # sapcnsl outputs a single "Trap(s) Sent" for the entire batch
        if "Trap(s) Sent" in output:
            logger.info(f"Batch sent all {total_traps} trap(s) from {device_ip} to {cc_ip}")
            return total_traps, 0, total_traps
        else:
            logger.error(
                f"Batch execution succeeded but no traps confirmed sent "
                f"from {device_ip} to {cc_ip}. Output: {output[:500]}"
            )
            return 0, total_traps, total_traps
    else:
        logger.error(f"Batch execution failed from {device_ip} to {cc_ip}: {output[:500]}")
        return 0, total_traps, total_traps


def send_attack_traps_with_progress(cc_ip, device_ip, payload):
    """Send attack traps to CyberController with progress reporting.

    Uses batch execution (single sapcnsl call) and yields progress events.

    Yields:
        {"type": "progress", "current": total, "total": total, "trap_name": "batch", "status": "success" or "failed"}
        {"type": "complete", "success_count": X, "failed_count": Y, "total_count": Z}
    """
    total_traps = len(payload['traps'])

    yield {"type": "progress", "current": 0, "total": total_traps, "trap_name": "batch", "status": "sending"}

    success_count, failed_count, total_count = send_attack_traps(cc_ip, device_ip, payload)

    if failed_count == 0:
        status = "success"
    elif success_count > 0:
        status = "partial"
    else:
        status = "failed"

    yield {"type": "progress", "current": total_traps, "total": total_traps, "trap_name": "batch", "status": status}
    yield {"type": "complete", "success_count": success_count, "failed_count": failed_count, "total_count": total_count}
