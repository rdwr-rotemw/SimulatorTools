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


# Weighted random distributions derived from real traffic analysis (10,034 traps)
_CATEGORY_CHOICES = [
    ATTACK_CATEGORY.DNS_PROTECTION,
    ATTACK_CATEGORY.BEHAVIORAL_DOS,
    ATTACK_CATEGORY.TRAFFIC_FILTERS,
    ATTACK_CATEGORY.ANTI_SCANNING,
    ATTACK_CATEGORY.DOS,
    ATTACK_CATEGORY.INTRUSIONS,
    ATTACK_CATEGORY.ANOMALIES,
]
_CATEGORY_WEIGHTS = [33.3, 33.0, 11.5, 11.0, 6.1, 4.7, 0.3]

_PROTOCOL_CHOICES = [
    ATTACK_PROTOCOL.UDP,
    ATTACK_PROTOCOL.TCP,
    ATTACK_PROTOCOL.IP,
    ATTACK_PROTOCOL.ICMP,
]
_PROTOCOL_WEIGHTS = [44.6, 33.4, 16.4, 5.5]

_STATUS_RANDOM_CHOICES = [
    ATTACK_STATUS.SAMPLED,
    ATTACK_STATUS.ONGOING,
    ATTACK_STATUS.OCCUR,
    ATTACK_STATUS.TERM,
    ATTACK_STATUS.START,
]
_STATUS_WEIGHTS = [1.0, 80.0, 4.0, 13.0, 2.0]

_RISK_CHOICES = [
    ATTACK_RISK.HIGH,
    ATTACK_RISK.MEDIUM,
    ATTACK_RISK.LOW,
]
_RISK_WEIGHTS = [77.7, 21.5, 0.9]

_ACTION_CHOICES = [
    ATTACK_ACTION.DROP,
    ATTACK_ACTION.CHALLENGE,
    ATTACK_ACTION.FORWARD,
]
_ACTION_WEIGHTS = [93.8, 5.4, 0.7]

_DIRECTION_CHOICES = [
    ATTACK_DIRECTION.IN,
    ATTACK_DIRECTION.OUT,
    ATTACK_DIRECTION.UNKNOWN,
]
_DIRECTION_WEIGHTS = [67.2, 27.8, 5.0]


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
    Fields listed in trap["randomFields"] receive a freshly generated random value each call.

    Args:
        cc_ip: CyberController IP address (used as trap manager)
        trap: Dictionary containing trap data

    Returns:
        Dictionary with all resolved field values

    Raises:
        ValueError: If required fields are missing (and not marked random)
    """
    rf = set(trap.get("randomFields", []))

    if "attackName" not in rf and "attackName" not in trap:
        raise ValueError("Missing required field: attackName")
    if "policy" not in rf and "policy" not in trap:
        raise ValueError("Missing required field: policy")

    attack_name = f"Attack_{random.randint(1000, 9999)}" if "attackName" in rf else trap["attackName"]
    policy = f"pol{random.randint(1, 200)}" if "policy" in rf else trap["policy"]
    attack_id = generate_attack_id() if "attackId" in rf else trap.get("attackId", generate_attack_id())
    radware_id = generate_radware_id() if "radwareId" in rf else trap.get("radwareId", generate_radware_id())
    src_ip = _random_ip() if "srcIp" in rf else trap.get("srcIp", "0.0.0.0")
    src_port = _random_port() if "srcPort" in rf else trap.get("srcPort", "80")
    dst_ip = _random_ip() if "dstIp" in rf else trap.get("dstIp", "0.0.0.0")
    dst_port = _random_port() if "dstPort" in rf else trap.get("dstPort", "80")
    physical_port = str(random.randint(1, 8)) if "physicalPort" in rf else trap.get("physicalPort", "1")
    packet_count = str(random.randint(100, 100000)) if "packetCount" in rf else trap.get("packetCount", "1000")
    packet_bandwidth = str(random.randint(1000, 1000000)) if "packetBandwidth" in rf else trap.get("packetBandwidth", "2000")
    # Status: weighted random based on real traffic distribution
    status = (
        random.choices(_STATUS_RANDOM_CHOICES, weights=_STATUS_WEIGHTS, k=1)[0].value
        if "status" in rf
        else _resolve_enum_field(trap, "status", ATTACK_STATUS, ATTACK_STATUS.ONGOING)
    )
    samples = (
        f"{random.randint(0, 100)}-{random.randint(0, 100)}-{random.randint(0, 100)}"
        if "samples" in rf else trap.get("samples", "0-0-0")
    )
    # Samples must be 0-0-0 unless status is 'sampled'
    if status != ATTACK_STATUS.SAMPLED.value:
        samples = "0-0-0"
    category = (
        random.choices(_CATEGORY_CHOICES, weights=_CATEGORY_WEIGHTS, k=1)[0].value
        if "attackCategory" in rf
        else _resolve_enum_field(trap, "attackCategory", ATTACK_CATEGORY, ATTACK_CATEGORY.BEHAVIORAL_DOS)
    )
    protocol = (
        random.choices(_PROTOCOL_CHOICES, weights=_PROTOCOL_WEIGHTS, k=1)[0].value
        if "protocol" in rf
        else _resolve_enum_field(trap, "protocol", ATTACK_PROTOCOL, ATTACK_PROTOCOL.TCP)
    )
    risk = (
        random.choices(_RISK_CHOICES, weights=_RISK_WEIGHTS, k=1)[0].value
        if "risk" in rf
        else _resolve_enum_field(trap, "risk", ATTACK_RISK, ATTACK_RISK.MEDIUM)
    )
    action = (
        random.choices(_ACTION_CHOICES, weights=_ACTION_WEIGHTS, k=1)[0].value
        if "action" in rf
        else _resolve_enum_field(trap, "action", ATTACK_ACTION, ATTACK_ACTION.DROP, legacy_field="actions")
    )
    direction = (
        random.choices(_DIRECTION_CHOICES, weights=_DIRECTION_WEIGHTS, k=1)[0].value
        if "direction" in rf
        else _resolve_enum_field(trap, "direction", ATTACK_DIRECTION, ATTACK_DIRECTION.IN)
    )

    return {
        "trap_manager": cc_ip,
        "attack_id": attack_id,
        "radware_id": radware_id,
        "category": category,
        "attack_name": attack_name,
        "protocol": protocol,
        "src_ip": src_ip,
        "src_port": src_port,
        "dst_ip": dst_ip,
        "dst_port": dst_port,
        "physical_port": physical_port,
        "policy": policy,
        "status": status,
        "packet_count": packet_count,
        "packet_bandwidth": packet_bandwidth,
        "samples": samples,
        "risk": risk,
        "action": action,
        "direction": direction,
    }


def generate_radware_id():
    return str(random.randint(1, 999999))


def generate_attack_id():
    part1 = random.randint(100, 999)
    part2 = int(random.random() * 1_000_000_0000)
    return f"{part1}-{part2:010d}"


def _random_ip():
    return f"{random.randint(1, 254)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def _random_port():
    return str(random.randint(1, 65535))


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

    Uses [list ...] syntax as recommended by Sapro documentation for proper
    TCL list construction and escaping.

    Args:
        fields: Dictionary from resolve_trap_fields()

    Returns:
        A complete SA_sendtrap TCL command string
    """
    # Sanitize fields (strip quotes and braces to avoid breaking TCL syntax)
    attack_name = str(fields["attack_name"]).replace('"', '').replace('{', '').replace('}', '')
    policy = str(fields["policy"]).replace('"', '').replace('{', '').replace('}', '')

    value = (
        f'V_8 {fields["attack_id"]} {fields["radware_id"]} {fields["category"]} '
        f'"{attack_name}" {fields["protocol"]} '
        f'{fields["src_ip"]} {fields["src_port"]} '
        f'{fields["dst_ip"]} {fields["dst_port"]} '
        f'{fields["physical_port"]} '
        f'Regular '
        f'"{policy}" {fields["status"]} '
        f'{fields["packet_count"]} {fields["packet_bandwidth"]} '
        f'{fields["samples"]} '
        f'{fields["risk"]} {fields["action"]} '
        f'0 0 19 N/A {fields["direction"]} 0'
    )

    return (
        f'SA_sendtrap [list 1.3.6.1.4.1.89.35.1.65.107 6 1 '
        f'[list rsIDSIntrusionErrorDesc.0 OctetString {{{value}}}] '
        f'[list rsIDSIntrusionErrorSeverity.0 Integer 2]]'
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


_MAX_TRAPS_PER_BATCH = 10


def _execute_trap_batch(cc_ip, device_ip, device_map, traps, batch_label=""):
    """Execute a single sub-batch of traps via sapcnsl.

    Uses a single SSH command that writes the TCL file, executes sapcnsl,
    and cleans up — avoiding 3 separate SSH round-trips.

    Returns:
        Tuple of (success_count: int, failed_count: int)
    """
    trap_count = len(traps)

    try:
        tcl_content = build_batch_tcl_content(cc_ip, traps)
    except ValueError as e:
        logger.error(f"Failed to build batch TCL content{batch_label}: {e}")
        return 0, trap_count

    batch_id = uuid.uuid4().hex[:12]
    temp_tcl_path = f'/tmp/sapro_batch_{batch_id}.tcl'

    total_pause = sum(trap.get('pause', 0) or 0 for trap in traps)
    timeout = max(30, trap_count * 2) + int(total_pause)

    # Combined command: write TCL file, execute sapcnsl, cleanup — all in one SSH call
    combined_command = (
        f"cat > {temp_tcl_path} << 'SAPRO_BATCH_EOF'\n"
        f"{tcl_content}"
        f"SAPRO_BATCH_EOF\n"
        f"/opt/sapro/bin/sapcnsl -m {device_map} -c tcl -d {device_ip} -f {temp_tcl_path}; "
        f"rm -f {temp_tcl_path}"
    )

    logger.info(f"Executing batch{batch_label} of {trap_count} trap(s) from {device_ip} to {cc_ip} (timeout={timeout}s)")
    success, output = execute_sapro_command(combined_command, timeout=timeout)
    logger.info(f"Batch{batch_label} execution output: {output[:1000]}")

    if success and "Trap(s) Sent" in output:
        logger.info(f"Batch{batch_label} sent {trap_count} trap(s) from {device_ip} to {cc_ip}")
        return trap_count, 0
    elif success:
        logger.error(
            f"Batch{batch_label} succeeded but no traps confirmed from {device_ip} to {cc_ip}. "
            f"Output: {output[:500]}"
        )
        return 0, trap_count
    else:
        logger.error(f"Batch{batch_label} failed from {device_ip} to {cc_ip}: {output[:500]}")
        return 0, trap_count


def send_attack_traps(cc_ip, device_ip, payload):
    """Send attack traps to CyberController using batch execution.

    Splits traps into sub-batches of _MAX_TRAPS_PER_BATCH to stay within
    sapcnsl's TCL script size limits.

    Returns:
        Tuple of (success_count: int, failed_count: int, total_count: int)
    """
    all_traps = payload['traps']
    total_traps = len(all_traps)
    device_map = payload['map']

    total_success = 0
    total_failed = 0

    for batch_start in range(0, total_traps, _MAX_TRAPS_PER_BATCH):
        batch_traps = all_traps[batch_start:batch_start + _MAX_TRAPS_PER_BATCH]
        batch_num = batch_start // _MAX_TRAPS_PER_BATCH + 1
        total_batches = (total_traps + _MAX_TRAPS_PER_BATCH - 1) // _MAX_TRAPS_PER_BATCH
        batch_label = f" [{batch_num}/{total_batches}]" if total_batches > 1 else ""

        success, failed = _execute_trap_batch(cc_ip, device_ip, device_map, batch_traps, batch_label)
        total_success += success
        total_failed += failed

    return total_success, total_failed, total_traps


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
