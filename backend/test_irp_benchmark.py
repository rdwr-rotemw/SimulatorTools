"""
IRP Message Throughput Benchmark Script

Tests the real-world throughput of IRP message sending via UDP.
Sends messages from multiple simulators simultaneously and measures performance
to identify bottlenecks.

Usage:
    python -m backend.test_irp_benchmark \
        --schema report/irp/data_formats/IdsDataFormat100600.xml \
        --simulators "50.40.30.2-49" \
        --destination 10.26.52.175 \
        --duration 15

Strategies tested:
    A) Serial baseline       — one simulator at a time, sequential messages
    B) Concurrent/sequential — N simulators in parallel, sequential messages per sim
    C) Concurrent/no-sleep   — Like B but without the 0.1s sleep between messages
    D) Concurrent/pre-built  — Like C but pre-builds binary payloads once, sends raw UDP
"""

import argparse
import logging
import os
import socket
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so we can import backend modules
# ---------------------------------------------------------------------------
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.app.modules.reporter.irp.irp_module import (
    schema_obj_from_xml_file,
    send_irp_message,
)
from backend.app.modules.reporter.irp.core.irp_formatter import IrpFormatter

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("irp-benchmark")


# ---------------------------------------------------------------------------
# Data classes for results
# ---------------------------------------------------------------------------
@dataclass
class MessageResult:
    simulator_ip: str
    message_name: str
    success: bool
    error: str = ""
    build_time_ms: float = 0.0
    send_time_ms: float = 0.0
    total_time_ms: float = 0.0


@dataclass
class StrategyResult:
    name: str
    duration: float = 0.0
    messages_attempted: int = 0
    messages_sent: int = 0
    messages_failed: int = 0
    avg_message_time_ms: float = 0.0
    per_simulator: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    results: List[MessageResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def parse_simulator_range(raw: str) -> List[str]:
    """Parse simulator IPs from a string supporting ranges and commas."""
    results = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            last_dash = part.rfind("-")
            base = part[:last_dash]
            end_str = part[last_dash + 1:]
            if "." in base and end_str.isdigit():
                prefix = base.rsplit(".", 1)[0]
                start_octet = int(base.rsplit(".", 1)[1])
                end_octet = int(end_str)
                for i in range(start_octet, end_octet + 1):
                    results.append(f"{prefix}.{i}")
            else:
                results.append(part)
        else:
            results.append(part)
    return results


def prepare_messages(raw_messages: List[Dict]) -> List[Tuple[str, Dict]]:
    """Clean messages: extract name and remove 'message'/'pause' keys."""
    cleaned = []
    for msg in raw_messages:
        name = msg["message"]
        data = {k: v for k, v in msg.items() if k not in ("message", "pause")}
        cleaned.append((name, data))
    return cleaned


def pre_build_payloads(schema_obj, messages: List[Tuple[str, Dict]]) -> List[Tuple[int, bytes]]:
    """Pre-build binary payloads for all messages (build once, send many)."""
    formatter = IrpFormatter(schema_obj.schema, "0.0.0.0", "0.0.0.0")
    payloads = []
    for name, data in messages:
        message_id = formatter.message_resolver.resolve(name)
        binary_data = formatter.message_builder.build_message(message_id, data)
        # Build full UDP packet (header + data)
        version = 0x91
        event_type = 4
        timestamp = int(time.time())
        parser_version = 2
        byte_order = 1
        schema_version = 100600
        code = int(message_id)
        data_header = struct.pack(
            '<BBIBBIB', version, event_type, timestamp,
            parser_version, byte_order, schema_version, code
        )
        payloads.append((message_id, data_header + binary_data))
    return payloads


def send_raw_udp(from_ip: str, to_ip: str, packet: bytes):
    """Send a pre-built UDP packet."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((from_ip, 0))
        sock.sendto(packet, (to_ip, 2088))
    finally:
        sock.close()


# ---------------------------------------------------------------------------
# Strategy A: Serial baseline
# ---------------------------------------------------------------------------
def run_strategy_a(
    schema_obj, messages: List[Tuple[str, Dict]], simulators: List[str],
    destination: str, duration: float
) -> StrategyResult:
    result = StrategyResult(name="A) Serial baseline")
    t_start = time.time()
    t_end = t_start + duration

    while time.time() < t_end:
        for sim_ip in simulators:
            if time.time() >= t_end:
                break
            for name, data in messages:
                if time.time() >= t_end:
                    break
                t0 = time.time()
                ok, msg = send_irp_message(schema_obj, name, data, sim_ip, destination)
                elapsed = (time.time() - t0) * 1000
                result.messages_attempted += 1
                mr = MessageResult(
                    simulator_ip=sim_ip, message_name=name,
                    success=ok, error="" if ok else msg, total_time_ms=elapsed,
                )
                result.results.append(mr)
                if ok:
                    result.messages_sent += 1
                else:
                    result.messages_failed += 1
                time.sleep(0.1)  # Same as production

    result.duration = time.time() - t_start
    return result


# ---------------------------------------------------------------------------
# Strategy B: Concurrent with 0.1s sleep (production behavior)
# ---------------------------------------------------------------------------
def run_strategy_b(
    schema_obj, messages: List[Tuple[str, Dict]], simulators: List[str],
    destination: str, duration: float, workers: int
) -> StrategyResult:
    result = StrategyResult(name="B) Concurrent + 0.1s sleep")
    t_start = time.time()
    t_end = t_start + duration
    lock = __import__("threading").Lock()

    def send_for_simulator(sim_ip: str):
        local_results = []
        while time.time() < t_end:
            for name, data in messages:
                if time.time() >= t_end:
                    break
                t0 = time.time()
                ok, msg = send_irp_message(schema_obj, name, data, sim_ip, destination)
                elapsed = (time.time() - t0) * 1000
                mr = MessageResult(
                    simulator_ip=sim_ip, message_name=name,
                    success=ok, error="" if ok else msg, total_time_ms=elapsed,
                )
                local_results.append(mr)
                time.sleep(0.1)  # Same as production
        return local_results

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(send_for_simulator, s): s for s in simulators}
        for future in as_completed(futures):
            for mr in future.result():
                result.results.append(mr)
                result.messages_attempted += 1
                if mr.success:
                    result.messages_sent += 1
                else:
                    result.messages_failed += 1

    result.duration = time.time() - t_start
    return result


# ---------------------------------------------------------------------------
# Strategy C: Concurrent without sleep
# ---------------------------------------------------------------------------
def run_strategy_c(
    schema_obj, messages: List[Tuple[str, Dict]], simulators: List[str],
    destination: str, duration: float, workers: int
) -> StrategyResult:
    result = StrategyResult(name="C) Concurrent, no sleep")
    t_start = time.time()
    t_end = t_start + duration

    def send_for_simulator(sim_ip: str):
        local_results = []
        while time.time() < t_end:
            for name, data in messages:
                if time.time() >= t_end:
                    break
                t0 = time.time()
                ok, msg = send_irp_message(schema_obj, name, data, sim_ip, destination)
                elapsed = (time.time() - t0) * 1000
                mr = MessageResult(
                    simulator_ip=sim_ip, message_name=name,
                    success=ok, error="" if ok else msg, total_time_ms=elapsed,
                )
                local_results.append(mr)
        return local_results

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(send_for_simulator, s): s for s in simulators}
        for future in as_completed(futures):
            for mr in future.result():
                result.results.append(mr)
                result.messages_attempted += 1
                if mr.success:
                    result.messages_sent += 1
                else:
                    result.messages_failed += 1

    result.duration = time.time() - t_start
    return result


# ---------------------------------------------------------------------------
# Strategy D: Concurrent + pre-built payloads (raw UDP, no rebuild)
# ---------------------------------------------------------------------------
def run_strategy_d(
    payloads: List[Tuple[int, bytes]], simulators: List[str],
    destination: str, duration: float, workers: int
) -> StrategyResult:
    result = StrategyResult(name="D) Concurrent, pre-built UDP")
    t_start = time.time()
    t_end = t_start + duration

    def send_for_simulator(sim_ip: str):
        local_results = []
        while time.time() < t_end:
            for msg_id, packet in payloads:
                if time.time() >= t_end:
                    break
                t0 = time.time()
                try:
                    send_raw_udp(sim_ip, destination, packet)
                    elapsed = (time.time() - t0) * 1000
                    mr = MessageResult(
                        simulator_ip=sim_ip, message_name=str(msg_id),
                        success=True, total_time_ms=elapsed,
                    )
                except Exception as e:
                    elapsed = (time.time() - t0) * 1000
                    mr = MessageResult(
                        simulator_ip=sim_ip, message_name=str(msg_id),
                        success=False, error=str(e), total_time_ms=elapsed,
                    )
                local_results.append(mr)
        return local_results

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(send_for_simulator, s): s for s in simulators}
        for future in as_completed(futures):
            for mr in future.result():
                result.results.append(mr)
                result.messages_attempted += 1
                if mr.success:
                    result.messages_sent += 1
                else:
                    result.messages_failed += 1

    result.duration = time.time() - t_start
    return result


# ---------------------------------------------------------------------------
# Print results
# ---------------------------------------------------------------------------
def print_result(result: StrategyResult, num_messages: int):
    throughput = result.messages_sent / result.duration if result.duration > 0 else 0

    # Per-message type timing
    msg_times: Dict[str, List[float]] = {}
    sim_stats: Dict[str, Dict[str, int]] = {}
    for mr in result.results:
        msg_times.setdefault(mr.message_name, []).append(mr.total_time_ms)
        if mr.simulator_ip not in sim_stats:
            sim_stats[mr.simulator_ip] = {"sent": 0, "failed": 0, "total_ms": 0.0}
        if mr.success:
            sim_stats[mr.simulator_ip]["sent"] += 1
        else:
            sim_stats[mr.simulator_ip]["failed"] += 1
        sim_stats[mr.simulator_ip]["total_ms"] += mr.total_time_ms

    all_times = [mr.total_time_ms for mr in result.results if mr.success]
    avg_time = sum(all_times) / len(all_times) if all_times else 0

    print(f"\n{'=' * 70}")
    print(f"  {result.name}")
    print(f"{'=' * 70}")
    print(f"  Duration:           {result.duration:.1f}s")
    print(f"  Messages attempted: {result.messages_attempted}")
    print(f"  Messages sent OK:   {result.messages_sent}")
    print(f"  Messages failed:    {result.messages_failed}")
    print(f"  Throughput:         {throughput:.1f} msgs/sec")
    print(f"  Avg message time:   {avg_time:.1f} ms")

    # Per-simulator breakdown
    sorted_sims = sorted(sim_stats.items(), key=lambda x: x[1]["sent"], reverse=True)
    print(f"\n  --- Per-simulator breakdown (top 10 + bottom 5) ---")
    for i, (sim_ip, stats) in enumerate(sorted_sims):
        if i < 10 or i >= len(sorted_sims) - 5:
            avg = stats["total_ms"] / (stats["sent"] + stats["failed"]) if (stats["sent"] + stats["failed"]) > 0 else 0
            print(f"  {sim_ip:>20s}:  sent={stats['sent']:>5d}  failed={stats['failed']:>3d}  avg={avg:.1f}ms")
        elif i == 10:
            print(f"  {'...':>20s}")


# ---------------------------------------------------------------------------
# Test messages (hardcoded from user input)
# ---------------------------------------------------------------------------
TEST_MESSAGES = [
    {
        "message": "dns-protection-rt-monitoring",
        "policy-name": "pol1",
        "policy-type": "policy-based",
        "ipv4": {
            "controllers": [
                {
                    "protection-type": {"protection": "dns-a", "direction": "in"},
                    "all-controllers-data": {
                        "state": "non-attack", "degree-of-attack": 247,
                        "degree-of-attack-noise": 2, "action": "none"
                    }
                }
            ]
        },
        "ipv6": {
            "controllers": [
                {
                    "protection-type": {"protection": "dns-mx", "direction": "in"},
                    "all-controllers-data": {
                        "state": "non-attack", "degree-of-attack": 4825,
                        "degree-of-attack-noise": 1893355814,
                        "action": "allow-list-and-signature"
                    }
                }
            ]
        }
    },
    {
        "message": "dns-protection-rt-rate-vectors",
        "policy-name": "pol1",
        "policy-type": "policy-based",
        "ipv4": {
            "rate-vectors": {
                "normal-rate-vector-bps": {
                    "dns-a": {"in": 1000000, "out": 900000},
                    "dns-mx": {"in": 800000, "out": 600000},
                    "dns-ptr": {"in": 500000, "out": 400000},
                    "dns-https": {"in": 200000, "out": 180000},
                    "dns-aaaa": {"in": 100000, "out": 90000},
                    "dns-text": {"in": 50000, "out": 40000},
                    "dns-soa": {"in": 20000, "out": 15000},
                    "dns-naptr": {"in": 10000, "out": 8000},
                    "dns-srv": {"in": 5000, "out": 4000},
                    "dns-other": {"in": 1000, "out": 900},
                },
                "full-rate-vector-bps": {
                    "dns-a": {"in": 1000000, "out": 900000},
                    "dns-mx": {"in": 800000, "out": 600000},
                    "dns-ptr": {"in": 500000, "out": 400000},
                    "dns-https": {"in": 200000, "out": 180000},
                    "dns-aaaa": {"in": 100000, "out": 90000},
                    "dns-text": {"in": 50000, "out": 40000},
                    "dns-soa": {"in": 20000, "out": 15000},
                    "dns-naptr": {"in": 10000, "out": 8000},
                    "dns-srv": {"in": 5000, "out": 4000},
                    "dns-other": {"in": 1000, "out": 900},
                },
                "partial-rate-vector-bps": {
                    "dns-a": {"in": 1000000, "out": 900000},
                    "dns-mx": {"in": 800000, "out": 600000},
                    "dns-ptr": {"in": 500000, "out": 400000},
                    "dns-https": {"in": 200000, "out": 180000},
                    "dns-aaaa": {"in": 100000, "out": 90000},
                    "dns-text": {"in": 50000, "out": 40000},
                    "dns-soa": {"in": 20000, "out": 15000},
                    "dns-naptr": {"in": 10000, "out": 8000},
                    "dns-srv": {"in": 5000, "out": 4000},
                    "dns-other": {"in": 1000, "out": 900},
                },
                "normal-rate-vector-pps": {
                    "dns-a": {"in": 1000, "out": 900},
                    "dns-mx": {"in": 800, "out": 600},
                    "dns-ptr": {"in": 500, "out": 400},
                    "dns-https": {"in": 200, "out": 180},
                    "dns-aaaa": {"in": 100, "out": 90},
                    "dns-text": {"in": 50, "out": 40},
                    "dns-soa": {"in": 20, "out": 15},
                    "dns-naptr": {"in": 10, "out": 8},
                    "dns-srv": {"in": 5, "out": 4},
                    "dns-other": {"in": 1, "out": 0.9},
                },
                "full-rate-vector-pps": {
                    "dns-a": {"in": 1000, "out": 900},
                    "dns-mx": {"in": 800, "out": 600},
                    "dns-ptr": {"in": 500, "out": 400},
                    "dns-https": {"in": 200, "out": 180},
                    "dns-aaaa": {"in": 100, "out": 90},
                    "dns-text": {"in": 50, "out": 40},
                    "dns-soa": {"in": 20, "out": 15},
                    "dns-naptr": {"in": 10, "out": 8},
                    "dns-srv": {"in": 5, "out": 4},
                    "dns-other": {"in": 1, "out": 0.9},
                },
                "partial-rate-vector-pps": {
                    "dns-a": {"in": 1000, "out": 900},
                    "dns-mx": {"in": 800, "out": 600},
                    "dns-ptr": {"in": 500, "out": 400},
                    "dns-https": {"in": 200, "out": 180},
                    "dns-aaaa": {"in": 100, "out": 90},
                    "dns-text": {"in": 50, "out": 40},
                    "dns-soa": {"in": 20, "out": 15},
                    "dns-naptr": {"in": 10, "out": 8},
                    "dns-srv": {"in": 5, "out": 4},
                    "dns-other": {"in": 1, "out": 0.9},
                },
            }
        },
        "ipv6": {
            "rate-vectors": {
                "normal-rate-vector-bps": {
                    "dns-a": {"in": 500000, "out": 450000},
                    "dns-mx": {"in": 400000, "out": 300000},
                    "dns-ptr": {"in": 250000, "out": 200000},
                    "dns-https": {"in": 100000, "out": 90000},
                    "dns-aaaa": {"in": 50000, "out": 40000},
                    "dns-text": {"in": 25000, "out": 20000},
                    "dns-soa": {"in": 10000, "out": 8000},
                    "dns-naptr": {"in": 5000, "out": 4000},
                    "dns-srv": {"in": 2000, "out": 1500},
                    "dns-other": {"in": 500, "out": 450},
                },
                "full-rate-vector-bps": {
                    "dns-a": {"in": 500000, "out": 450000},
                    "dns-mx": {"in": 400000, "out": 300000},
                    "dns-ptr": {"in": 250000, "out": 200000},
                    "dns-https": {"in": 100000, "out": 90000},
                    "dns-aaaa": {"in": 50000, "out": 40000},
                    "dns-text": {"in": 25000, "out": 20000},
                    "dns-soa": {"in": 10000, "out": 8000},
                    "dns-naptr": {"in": 5000, "out": 4000},
                    "dns-srv": {"in": 2000, "out": 1500},
                    "dns-other": {"in": 500, "out": 450},
                },
                "partial-rate-vector-bps": {
                    "dns-a": {"in": 500000, "out": 450000},
                    "dns-mx": {"in": 400000, "out": 300000},
                    "dns-ptr": {"in": 250000, "out": 200000},
                    "dns-https": {"in": 100000, "out": 90000},
                    "dns-aaaa": {"in": 50000, "out": 40000},
                    "dns-text": {"in": 25000, "out": 20000},
                    "dns-soa": {"in": 10000, "out": 8000},
                    "dns-naptr": {"in": 5000, "out": 4000},
                    "dns-srv": {"in": 2000, "out": 1500},
                    "dns-other": {"in": 500, "out": 450},
                },
                "normal-rate-vector-pps": {
                    "dns-a": {"in": 500, "out": 450},
                    "dns-mx": {"in": 400, "out": 300},
                    "dns-ptr": {"in": 250, "out": 200},
                    "dns-https": {"in": 100, "out": 90},
                    "dns-aaaa": {"in": 50, "out": 40},
                    "dns-text": {"in": 25, "out": 20},
                    "dns-soa": {"in": 10, "out": 8},
                    "dns-naptr": {"in": 5, "out": 4},
                    "dns-srv": {"in": 2, "out": 1.5},
                    "dns-other": {"in": 0.5, "out": 0.45},
                },
                "full-rate-vector-pps": {
                    "dns-a": {"in": 500, "out": 450},
                    "dns-mx": {"in": 400, "out": 300},
                    "dns-ptr": {"in": 250, "out": 200},
                    "dns-https": {"in": 100, "out": 90},
                    "dns-aaaa": {"in": 50, "out": 40},
                    "dns-text": {"in": 25, "out": 20},
                    "dns-soa": {"in": 10, "out": 8},
                    "dns-naptr": {"in": 5, "out": 4},
                    "dns-srv": {"in": 2, "out": 1.5},
                    "dns-other": {"in": 0.5, "out": 0.45},
                },
                "partial-rate-vector-pps": {
                    "dns-a": {"in": 500, "out": 450},
                    "dns-mx": {"in": 400, "out": 300},
                    "dns-ptr": {"in": 250, "out": 200},
                    "dns-https": {"in": 100, "out": 90},
                    "dns-aaaa": {"in": 50, "out": 40},
                    "dns-text": {"in": 25, "out": 20},
                    "dns-soa": {"in": 10, "out": 8},
                    "dns-naptr": {"in": 5, "out": 4},
                    "dns-srv": {"in": 2, "out": 1.5},
                    "dns-other": {"in": 0.5, "out": 0.45},
                },
            }
        },
    },
    {
        "message": "dns-protection-rt-portion-vectors",
        "policy-name": "pol1",
        "policy-type": "policy-based",
        "ipv4": {
            "portion-vectors": {
                vec_name: {
                    prot: {"portion-data": val}
                    for prot, val in [
                        ("dns-a", 90.0), ("dns-mx", 75.0), ("dns-ptr", 80.0),
                        ("dns-https", 90.0), ("dns-aaaa", 90.0), ("dns-text", 80.0),
                        ("dns-soa", 75.0), ("dns-naptr", 80.0), ("dns-srv", 80.0),
                        ("dns-other", 90.0),
                    ]
                }
                for vec_name in [
                    "normal-portion-vector-in", "normal-portion-vector-out",
                    "full-portion-vector-in", "full-portion-vector-out",
                    "partial-portion-vector-in", "partial-portion-vector-out",
                ]
            }
        },
        "ipv6": {
            "portion-vectors": {
                vec_name: {
                    prot: {"portion-data": val}
                    for prot, val in [
                        ("dns-a", 90.0), ("dns-mx", 75.0), ("dns-ptr", 80.0),
                        ("dns-https", 90.0), ("dns-aaaa", 90.0), ("dns-text", 80.0),
                        ("dns-soa", 75.0), ("dns-naptr", 80.0), ("dns-srv", 80.0),
                        ("dns-other", 90.0),
                    ]
                }
                for vec_name in [
                    "normal-portion-vector-in", "normal-portion-vector-out",
                    "full-portion-vector-in", "full-portion-vector-out",
                    "partial-portion-vector-in", "partial-portion-vector-out",
                ]
            }
        },
    },
    {
        "message": "dns-protection-rt-fuzzy-info",
        "policy-name": "pol1",
        "policy-type": "policy-based",
        "ipv4": {
            "fuzzy-edges-info": {
                "fuzzy-edges-vector-in": {
                    prot: {
                        "protection-fuzzy-edges-data": {
                            "suspect-fuzzy-pps-edge": 50.0,
                            "attack-fuzzy-pps-edge": 50.0,
                            "suspect-fuzzy-noise-edge": 50.0,
                            "attack-fuzzy-noise-edge": 50.0,
                        }
                    }
                    for prot in [
                        "dns-a", "dns-mx", "dns-ptr", "dns-https", "dns-aaaa",
                        "dns-text", "dns-soa", "dns-naptr", "dns-srv", "dns-other",
                    ]
                },
                "fuzzy-edges-vector-out": {
                    prot: {
                        "protection-fuzzy-edges-data": {
                            "suspect-fuzzy-pps-edge": 50.0,
                            "attack-fuzzy-pps-edge": 50.0,
                            "suspect-fuzzy-noise-edge": 50.0,
                            "attack-fuzzy-noise-edge": 50.0,
                        }
                    }
                    for prot in [
                        "dns-a", "dns-mx", "dns-ptr", "dns-https", "dns-aaaa",
                        "dns-text", "dns-soa", "dns-naptr", "dns-srv", "dns-other",
                    ]
                },
            }
        },
        "ipv6": {
            "fuzzy-edges-info": {
                "fuzzy-edges-vector-in": {
                    prot: {
                        "protection-fuzzy-edges-data": {
                            "suspect-fuzzy-pps-edge": 50.0,
                            "attack-fuzzy-pps-edge": 50.0,
                            "suspect-fuzzy-noise-edge": 50.0,
                            "attack-fuzzy-noise-edge": 50.0,
                        }
                    }
                    for prot in [
                        "dns-a", "dns-mx", "dns-ptr", "dns-https", "dns-aaaa",
                        "dns-text", "dns-soa", "dns-naptr", "dns-srv", "dns-other",
                    ]
                },
                "fuzzy-edges-vector-out": {
                    prot: {
                        "protection-fuzzy-edges-data": {
                            "suspect-fuzzy-pps-edge": 50.0,
                            "attack-fuzzy-pps-edge": 50.0,
                            "suspect-fuzzy-noise-edge": 50.0,
                            "attack-fuzzy-noise-edge": 50.0,
                        }
                    }
                    for prot in [
                        "dns-a", "dns-mx", "dns-ptr", "dns-https", "dns-aaaa",
                        "dns-text", "dns-soa", "dns-naptr", "dns-srv", "dns-other",
                    ]
                },
            }
        },
    },
]

# Duplicate for pol2 (same messages, different policy name)
TEST_MESSAGES_POL2 = []
for msg in TEST_MESSAGES:
    m = dict(msg)
    m["policy-name"] = "pol2"
    TEST_MESSAGES_POL2.append(m)

ALL_TEST_MESSAGES = TEST_MESSAGES + TEST_MESSAGES_POL2


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="IRP Message Throughput Benchmark")
    parser.add_argument("--schema", required=True, help="Path to IdsDataFormat XML file")
    parser.add_argument("--simulators", required=True, help="Simulator IPs (range: 50.40.30.2-49)")
    parser.add_argument("--destination", required=True, help="Destination IP (CC IP)")
    parser.add_argument("--duration", type=float, default=15.0, help="Duration per strategy (seconds)")
    parser.add_argument("--workers", type=int, default=0, help="Thread pool workers (0 = num simulators)")
    parser.add_argument("--strategies", default="A,B,C,D", help="Comma-separated strategies to run")
    args = parser.parse_args()

    simulators = parse_simulator_range(args.simulators)
    workers = args.workers if args.workers > 0 else len(simulators)
    strategies = [s.strip().upper() for s in args.strategies.split(",")]

    print(f"\n{'#' * 70}")
    print(f"  IRP MESSAGE THROUGHPUT BENCHMARK")
    print(f"{'#' * 70}")
    print(f"  Schema:            {args.schema}")
    print(f"  Simulators:        {len(simulators)} devices")
    print(f"  Destination:       {args.destination}")
    print(f"  Duration:          {args.duration}s per strategy")
    print(f"  Workers:           {workers}")
    print(f"  Messages/batch:    {len(ALL_TEST_MESSAGES)} ({len(TEST_MESSAGES)} x 2 policies)")
    print(f"  Strategies:        {', '.join(strategies)}")
    print(f"{'#' * 70}")

    # Load schema
    print(f"\nLoading schema from {args.schema}...")
    schema_obj = schema_obj_from_xml_file(args.schema)
    print(f"  Schema loaded OK")

    # Prepare messages
    messages = prepare_messages(ALL_TEST_MESSAGES)
    print(f"  Prepared {len(messages)} messages")

    # Test single send
    print(f"\nTesting single message send...")
    test_sim = simulators[0]
    test_name, test_data = messages[0]
    t0 = time.time()
    ok, msg = send_irp_message(schema_obj, test_name, test_data, test_sim, args.destination)
    t1 = time.time()
    if ok:
        print(f"  Single send OK ({(t1-t0)*1000:.1f}ms)")
    else:
        print(f"  Single send FAILED: {msg}")
        print(f"  Aborting benchmark.")
        sys.exit(1)

    # Pre-build payloads for strategy D
    payloads = None
    if "D" in strategies:
        print(f"\nPre-building binary payloads for strategy D...")
        payloads = pre_build_payloads(schema_obj, messages)
        print(f"  Built {len(payloads)} payloads")

    # Run strategies
    for strat in strategies:
        if strat == "A":
            print(f"\n>>> Running Strategy A: Serial baseline ({args.duration}s)...")
            result = run_strategy_a(schema_obj, messages, simulators, args.destination, args.duration)
            print_result(result, len(messages))
        elif strat == "B":
            print(f"\n>>> Running Strategy B: Concurrent + 0.1s sleep ({args.duration}s)...")
            result = run_strategy_b(schema_obj, messages, simulators, args.destination, args.duration, workers)
            print_result(result, len(messages))
        elif strat == "C":
            print(f"\n>>> Running Strategy C: Concurrent, no sleep ({args.duration}s)...")
            result = run_strategy_c(schema_obj, messages, simulators, args.destination, args.duration, workers)
            print_result(result, len(messages))
        elif strat == "D":
            print(f"\n>>> Running Strategy D: Concurrent, pre-built UDP ({args.duration}s)...")
            result = run_strategy_d(payloads, simulators, args.destination, args.duration, workers)
            print_result(result, len(messages))

    print(f"\n{'#' * 70}")
    print(f"  Benchmark complete.")
    print(f"{'#' * 70}\n")


if __name__ == "__main__":
    main()
