"""
SNMP Trap Throughput Benchmark Script

Tests the real-world throughput of SNMP trap sending through Sapro.
Sends traps from multiple simulators simultaneously and measures performance
at each layer to identify bottlenecks.

Usage:
    python -m backend.test_snmp_benchmark \
        --cc-ip 10.10.10.10 \
        --simulators "50.50.180.1,50.50.180.2,...,50.50.180.48" \
        --map /opt/sapro/maps/default/default.map \
        --duration 15

Strategies tested:
    A) Serial baseline     — one simulator at a time, single SSH connection
    B) Concurrent/locked   — N simulators via ThreadPoolExecutor, single shared SSH
                             (current production behavior)
    C) Concurrent/pool     — N simulators, small SSH connection pool (--ssh-pool-size)
    D) Concurrent/combined — Like C but merges write+exec+cleanup into 1 SSH call
"""

import argparse
import logging
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import paramiko

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so we can import backend modules
# ---------------------------------------------------------------------------
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.app.modules.reporter.snmp.attack_traps import (
    build_batch_tcl_content,
    resolve_trap_fields,
)
from backend.app.utils.config import settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("snmp-benchmark")


# ---------------------------------------------------------------------------
# Data classes for results
# ---------------------------------------------------------------------------
@dataclass
class BatchResult:
    """Timing result for a single batch execution."""
    simulator_ip: str
    trap_count: int
    success: bool
    tcl_build_ms: float = 0.0
    ssh_write_ms: float = 0.0
    ssh_exec_ms: float = 0.0
    ssh_cleanup_ms: float = 0.0
    total_ms: float = 0.0
    error: str = ""


@dataclass
class StrategyResult:
    """Aggregated result for a whole strategy run."""
    strategy_name: str
    duration_seconds: float = 0.0
    total_traps_attempted: int = 0
    total_traps_sent: int = 0
    total_traps_failed: int = 0
    batches: List[BatchResult] = field(default_factory=list)

    @property
    def throughput(self) -> float:
        if self.duration_seconds > 0:
            return self.total_traps_sent / self.duration_seconds
        return 0.0

    @property
    def avg_batch_ms(self) -> float:
        if not self.batches:
            return 0.0
        return sum(b.total_ms for b in self.batches) / len(self.batches)


# ---------------------------------------------------------------------------
# SSH helpers  (per-connection, NOT using the singleton)
# ---------------------------------------------------------------------------
class BenchmarkSSHClient:
    """Lightweight SSH client for benchmark — one connection per instance, no global lock."""

    def __init__(self, host: str, username: str, password: str, port: int = 22):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self._client: paramiko.SSHClient = None
        self._lock = threading.Lock()

    def connect(self):
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=15,
            allow_agent=False,
            look_for_keys=False,
        )
        transport = self._client.get_transport()
        if transport:
            transport.set_keepalive(30)

    def execute(self, command: str, timeout: int = 60) -> Tuple[bool, str]:
        with self._lock:
            if not self._client or not self._client.get_transport() or not self._client.get_transport().is_active():
                self.connect()
            stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
            stdout.channel.settimeout(timeout)
            out = stdout.read().decode("utf-8", errors="ignore").strip()
            err = stderr.read().decode("utf-8", errors="ignore").strip()
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                return False, err or out or f"exit {exit_status}"
            return True, out

    def close(self):
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Core benchmark: send one batch of traps for ONE simulator
# ---------------------------------------------------------------------------
def _make_random_trap() -> dict:
    """Create a trap dict with all fields randomised."""
    return {
        "randomFields": [
            "attackId", "radwareId", "attackCategory", "attackName",
            "protocol", "srcIp", "srcPort", "dstIp", "dstPort",
            "physicalPort", "policy", "status", "packetCount",
            "packetBandwidth", "samples", "risk", "action", "direction",
        ],
    }


def send_single_batch(
    ssh: BenchmarkSSHClient,
    cc_ip: str,
    simulator_ip: str,
    device_map: str,
    traps_per_batch: int,
) -> BatchResult:
    """Send one batch of traps for a single simulator and time each step."""
    result = BatchResult(simulator_ip=simulator_ip, trap_count=traps_per_batch, success=False)
    t_total_start = time.perf_counter()

    # 1. Build TCL content (CPU-only, no I/O)
    t0 = time.perf_counter()
    traps = [_make_random_trap() for _ in range(traps_per_batch)]
    try:
        tcl_content = build_batch_tcl_content(cc_ip, traps)
    except Exception as e:
        result.error = f"TCL build error: {e}"
        result.total_ms = (time.perf_counter() - t_total_start) * 1000
        return result
    result.tcl_build_ms = (time.perf_counter() - t0) * 1000

    # 2. Write TCL file to Sapro host
    batch_id = uuid.uuid4().hex[:12]
    temp_path = f"/tmp/sapro_bench_{batch_id}.tcl"
    write_cmd = f"cat > {temp_path} << 'SAPRO_BATCH_EOF'\n{tcl_content}SAPRO_BATCH_EOF"

    t0 = time.perf_counter()
    ok, out = ssh.execute(write_cmd, timeout=15)
    result.ssh_write_ms = (time.perf_counter() - t0) * 1000
    if not ok:
        result.error = f"Write failed: {out[:200]}"
        result.total_ms = (time.perf_counter() - t_total_start) * 1000
        return result

    # 3. Execute sapcnsl
    exec_cmd = f"/opt/sapro/bin/sapcnsl -m {device_map} -c tcl -d {simulator_ip} -f {temp_path}"
    timeout = max(30, traps_per_batch * 2)

    t0 = time.perf_counter()
    ok, out = ssh.execute(exec_cmd, timeout=timeout)
    result.ssh_exec_ms = (time.perf_counter() - t0) * 1000

    # 4. Cleanup
    t0 = time.perf_counter()
    ssh.execute(f"rm -f {temp_path}", timeout=10)
    result.ssh_cleanup_ms = (time.perf_counter() - t0) * 1000

    result.total_ms = (time.perf_counter() - t_total_start) * 1000

    if ok and "Trap(s) Sent" in out:
        result.success = True
    else:
        result.error = f"Exec {'succeeded but no confirmation' if ok else 'failed'}: {out[:200]}"

    return result


# ---------------------------------------------------------------------------
# Strategy A: Serial baseline
# ---------------------------------------------------------------------------
def strategy_serial(
    ssh_host: str,
    ssh_user: str,
    ssh_pass: str,
    cc_ip: str,
    simulators: List[str],
    device_map: str,
    duration: float,
    traps_per_batch: int,
) -> StrategyResult:
    """Send traps one simulator at a time, single SSH connection."""
    result = StrategyResult(strategy_name="A) Serial (1 SSH, 1 simulator at a time)")
    ssh = BenchmarkSSHClient(ssh_host, ssh_user, ssh_pass)
    ssh.connect()

    start = time.perf_counter()
    try:
        while time.perf_counter() - start < duration:
            for sim_ip in simulators:
                if time.perf_counter() - start >= duration:
                    break
                br = send_single_batch(ssh, cc_ip, sim_ip, device_map, traps_per_batch)
                result.batches.append(br)
                result.total_traps_attempted += br.trap_count
                if br.success:
                    result.total_traps_sent += br.trap_count
                else:
                    result.total_traps_failed += br.trap_count
    finally:
        result.duration_seconds = time.perf_counter() - start
        ssh.close()

    return result


# ---------------------------------------------------------------------------
# Strategy B: Concurrent with SINGLE shared SSH (simulates current production)
# ---------------------------------------------------------------------------
def strategy_concurrent_single_ssh(
    ssh_host: str,
    ssh_user: str,
    ssh_pass: str,
    cc_ip: str,
    simulators: List[str],
    device_map: str,
    duration: float,
    traps_per_batch: int,
    max_workers: int,
) -> StrategyResult:
    """All simulators share one SSH connection — simulates current production."""
    result = StrategyResult(strategy_name=f"B) Concurrent ({max_workers} threads, 1 shared SSH)")
    ssh = BenchmarkSSHClient(ssh_host, ssh_user, ssh_pass)
    ssh.connect()

    lock = threading.Lock()
    stop_event = threading.Event()

    def worker(sim_ip: str):
        local_batches = []
        while not stop_event.is_set():
            br = send_single_batch(ssh, cc_ip, sim_ip, device_map, traps_per_batch)
            local_batches.append(br)
        return local_batches

    start = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(worker, sim): sim for sim in simulators}

            # Wait for duration
            time.sleep(duration)
            stop_event.set()

            for future in as_completed(futures):
                batches = future.result()
                for br in batches:
                    result.batches.append(br)
                    result.total_traps_attempted += br.trap_count
                    if br.success:
                        result.total_traps_sent += br.trap_count
                    else:
                        result.total_traps_failed += br.trap_count
    finally:
        result.duration_seconds = time.perf_counter() - start
        ssh.close()

    return result


# ---------------------------------------------------------------------------
# Strategy C: Concurrent with SSH connection POOL
# ---------------------------------------------------------------------------
class SSHPool:
    """Round-robin pool of N SSH connections. Connections are established
    sequentially with a small delay to avoid overwhelming sshd."""

    def __init__(self, host: str, username: str, password: str, size: int):
        self._connections: List[BenchmarkSSHClient] = []
        self._index = 0
        self._index_lock = threading.Lock()
        for i in range(size):
            ssh = BenchmarkSSHClient(host, username, password)
            ssh.connect()
            self._connections.append(ssh)
            if i < size - 1:
                time.sleep(0.1)  # stagger connections to avoid MaxStartups rejection

    def get(self) -> BenchmarkSSHClient:
        with self._index_lock:
            conn = self._connections[self._index % len(self._connections)]
            self._index += 1
            return conn

    def close_all(self):
        for c in self._connections:
            c.close()


def strategy_concurrent_pool(
    ssh_host: str,
    ssh_user: str,
    ssh_pass: str,
    cc_ip: str,
    simulators: List[str],
    device_map: str,
    duration: float,
    traps_per_batch: int,
    max_workers: int,
    pool_size: int,
) -> StrategyResult:
    """Simulators share a pool of N SSH connections (round-robin)."""
    result = StrategyResult(strategy_name=f"C) Concurrent ({max_workers} threads, {pool_size} SSH pool)")
    print(f"  Creating SSH pool with {pool_size} connections...")
    ssh_pool = SSHPool(ssh_host, ssh_user, ssh_pass, pool_size)
    print(f"  SSH pool ready")
    stop_event = threading.Event()

    def worker(sim_ip: str):
        ssh = ssh_pool.get()
        local_batches = []
        while not stop_event.is_set():
            br = send_single_batch(ssh, cc_ip, sim_ip, device_map, traps_per_batch)
            local_batches.append(br)
        return local_batches

    start = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(worker, sim): sim for sim in simulators}

            time.sleep(duration)
            stop_event.set()

            for future in as_completed(futures):
                try:
                    batches = future.result()
                except Exception as e:
                    logger.error(f"Worker failed: {e}")
                    continue
                for br in batches:
                    result.batches.append(br)
                    result.total_traps_attempted += br.trap_count
                    if br.success:
                        result.total_traps_sent += br.trap_count
                    else:
                        result.total_traps_failed += br.trap_count
    finally:
        result.duration_seconds = time.perf_counter() - start
        ssh_pool.close_all()

    return result


# ---------------------------------------------------------------------------
# Combined single-SSH-command batch sender (for Strategy D)
# ---------------------------------------------------------------------------
def send_single_batch_combined(
    ssh: BenchmarkSSHClient,
    cc_ip: str,
    simulator_ip: str,
    device_map: str,
    traps_per_batch: int,
) -> BatchResult:
    """Send one batch using a single SSH command (write + exec + cleanup combined)."""
    result = BatchResult(simulator_ip=simulator_ip, trap_count=traps_per_batch, success=False)
    t_total_start = time.perf_counter()

    # 1. Build TCL content (CPU-only)
    t0 = time.perf_counter()
    traps = [_make_random_trap() for _ in range(traps_per_batch)]
    try:
        tcl_content = build_batch_tcl_content(cc_ip, traps)
    except Exception as e:
        result.error = f"TCL build error: {e}"
        result.total_ms = (time.perf_counter() - t_total_start) * 1000
        return result
    result.tcl_build_ms = (time.perf_counter() - t0) * 1000

    # 2. Single SSH command: write file, execute sapcnsl, cleanup — all in one call
    batch_id = uuid.uuid4().hex[:12]
    temp_path = f"/tmp/sapro_bench_{batch_id}.tcl"
    timeout = max(30, traps_per_batch * 2)

    combined_cmd = (
        f"cat > {temp_path} << 'SAPRO_BATCH_EOF'\n{tcl_content}SAPRO_BATCH_EOF\n"
        f"/opt/sapro/bin/sapcnsl -m {device_map} -c tcl -d {simulator_ip} -f {temp_path}; "
        f"rm -f {temp_path}"
    )

    t0 = time.perf_counter()
    ok, out = ssh.execute(combined_cmd, timeout=timeout)
    result.ssh_exec_ms = (time.perf_counter() - t0) * 1000

    result.total_ms = (time.perf_counter() - t_total_start) * 1000

    if ok and "Trap(s) Sent" in out:
        result.success = True
    else:
        result.error = f"Combined {'succeeded but no confirmation' if ok else 'failed'}: {out[:200]}"

    return result


# ---------------------------------------------------------------------------
# Strategy D: Concurrent with SSH pool + combined command
# ---------------------------------------------------------------------------
def strategy_concurrent_combined(
    ssh_host: str,
    ssh_user: str,
    ssh_pass: str,
    cc_ip: str,
    simulators: List[str],
    device_map: str,
    duration: float,
    traps_per_batch: int,
    max_workers: int,
    pool_size: int,
) -> StrategyResult:
    """SSH pool + combined write/exec/cleanup in single SSH call."""
    result = StrategyResult(strategy_name=f"D) Combined cmd ({max_workers} threads, {pool_size} SSH pool)")
    print(f"  Creating SSH pool with {pool_size} connections...")
    ssh_pool = SSHPool(ssh_host, ssh_user, ssh_pass, pool_size)
    print(f"  SSH pool ready")
    stop_event = threading.Event()

    def worker(sim_ip: str):
        ssh = ssh_pool.get()
        local_batches = []
        while not stop_event.is_set():
            br = send_single_batch_combined(ssh, cc_ip, sim_ip, device_map, traps_per_batch)
            local_batches.append(br)
        return local_batches

    start = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(worker, sim): sim for sim in simulators}

            time.sleep(duration)
            stop_event.set()

            for future in as_completed(futures):
                try:
                    batches = future.result()
                except Exception as e:
                    logger.error(f"Worker failed: {e}")
                    continue
                for br in batches:
                    result.batches.append(br)
                    result.total_traps_attempted += br.trap_count
                    if br.success:
                        result.total_traps_sent += br.trap_count
                    else:
                        result.total_traps_failed += br.trap_count
    finally:
        result.duration_seconds = time.perf_counter() - start
        ssh_pool.close_all()

    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_strategy_report(sr: StrategyResult):
    """Print detailed results for one strategy."""
    print(f"\n{'=' * 70}")
    print(f"  {sr.strategy_name}")
    print(f"{'=' * 70}")
    print(f"  Duration:           {sr.duration_seconds:.1f}s")
    print(f"  Traps attempted:    {sr.total_traps_attempted}")
    print(f"  Traps sent OK:      {sr.total_traps_sent}")
    print(f"  Traps failed:       {sr.total_traps_failed}")
    print(f"  Throughput:         {sr.throughput:.1f} traps/sec")
    print(f"  Total batches:      {len(sr.batches)}")
    print(f"  Avg batch time:     {sr.avg_batch_ms:.1f} ms")

    if sr.batches:
        successful = [b for b in sr.batches if b.success]
        failed = [b for b in sr.batches if not b.success]

        if successful:
            print(f"\n  --- Timing breakdown (successful batches) ---")
            print(f"  TCL build:     avg {_avg(successful, 'tcl_build_ms'):.1f} ms  |  "
                  f"min {_min(successful, 'tcl_build_ms'):.1f} ms  |  "
                  f"max {_max(successful, 'tcl_build_ms'):.1f} ms")
            print(f"  SSH write:     avg {_avg(successful, 'ssh_write_ms'):.1f} ms  |  "
                  f"min {_min(successful, 'ssh_write_ms'):.1f} ms  |  "
                  f"max {_max(successful, 'ssh_write_ms'):.1f} ms")
            print(f"  SSH exec:      avg {_avg(successful, 'ssh_exec_ms'):.1f} ms  |  "
                  f"min {_min(successful, 'ssh_exec_ms'):.1f} ms  |  "
                  f"max {_max(successful, 'ssh_exec_ms'):.1f} ms")
            print(f"  SSH cleanup:   avg {_avg(successful, 'ssh_cleanup_ms'):.1f} ms  |  "
                  f"min {_min(successful, 'ssh_cleanup_ms'):.1f} ms  |  "
                  f"max {_max(successful, 'ssh_cleanup_ms'):.1f} ms")
            print(f"  Total:         avg {_avg(successful, 'total_ms'):.1f} ms  |  "
                  f"min {_min(successful, 'total_ms'):.1f} ms  |  "
                  f"max {_max(successful, 'total_ms'):.1f} ms")

        # Per-simulator breakdown
        sim_stats: Dict[str, Dict] = {}
        for b in sr.batches:
            if b.simulator_ip not in sim_stats:
                sim_stats[b.simulator_ip] = {"sent": 0, "failed": 0, "batches": 0, "total_ms": 0.0}
            sim_stats[b.simulator_ip]["batches"] += 1
            sim_stats[b.simulator_ip]["total_ms"] += b.total_ms
            if b.success:
                sim_stats[b.simulator_ip]["sent"] += b.trap_count
            else:
                sim_stats[b.simulator_ip]["failed"] += b.trap_count

        print(f"\n  --- Per-simulator breakdown (top 10 + bottom 5) ---")
        sorted_sims = sorted(sim_stats.items(), key=lambda x: x[1]["sent"], reverse=True)
        show_sims = sorted_sims[:10]
        if len(sorted_sims) > 15:
            show_sims += [("...", {"sent": 0, "failed": 0, "batches": 0, "total_ms": 0})]
            show_sims += sorted_sims[-5:]
        elif len(sorted_sims) > 10:
            show_sims = sorted_sims

        for sim_ip, stats in show_sims:
            if sim_ip == "...":
                print(f"  {'...':>18s}")
                continue
            avg_ms = stats["total_ms"] / stats["batches"] if stats["batches"] > 0 else 0
            print(f"  {sim_ip:>18s}:  sent={stats['sent']:>4d}  "
                  f"failed={stats['failed']:>3d}  "
                  f"batches={stats['batches']:>3d}  "
                  f"avg={avg_ms:.0f}ms")

        if failed:
            # Show unique error messages
            errors: Dict[str, int] = {}
            for b in failed:
                err = b.error[:80] if b.error else "unknown"
                errors[err] = errors.get(err, 0) + 1
            print(f"\n  --- Errors ({len(failed)} failed batches) ---")
            for err, count in sorted(errors.items(), key=lambda x: -x[1])[:5]:
                print(f"    [{count}x] {err}")


def _avg(batches: list, attr: str) -> float:
    vals = [getattr(b, attr) for b in batches]
    return sum(vals) / len(vals) if vals else 0.0

def _min(batches: list, attr: str) -> float:
    vals = [getattr(b, attr) for b in batches]
    return min(vals) if vals else 0.0

def _max(batches: list, attr: str) -> float:
    vals = [getattr(b, attr) for b in batches]
    return max(vals) if vals else 0.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_simulator_range(raw: str) -> List[str]:
    """Parse simulator IPs from a string supporting ranges and commas.

    Formats:
        "50.50.180.1-48"               → 50.50.180.1 .. 50.50.180.48
        "50.50.180.1,50.50.180.2"      → two explicit IPs
        "50.50.180.1-24,50.50.181.1-24"→ two ranges combined
    """
    results = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            # Check if it's a range like "50.50.180.1-48"
            # Split on the LAST hyphen only
            last_dash = part.rfind("-")
            base = part[:last_dash]
            end_str = part[last_dash + 1:]
            # Validate: base should be an IP, end_str should be a number
            if "." in base and end_str.isdigit():
                prefix = base.rsplit(".", 1)[0]  # e.g. "50.50.180"
                start_octet = int(base.rsplit(".", 1)[1])  # e.g. 1
                end_octet = int(end_str)  # e.g. 48
                for i in range(start_octet, end_octet + 1):
                    results.append(f"{prefix}.{i}")
            else:
                # Not a range, just an IP that happens to have a hyphen (unlikely but safe)
                results.append(part)
        else:
            results.append(part)
    return results


def main():
    parser = argparse.ArgumentParser(
        description="SNMP Trap throughput benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--cc-ip", required=True, help="CyberController IP (trap destination)")
    parser.add_argument("--simulators", required=True,
                        help="Simulator IPs. Supports: range '50.50.180.1-48', "
                             "comma-separated '50.50.180.1,50.50.180.2', "
                             "or mixed '50.50.180.1-24,50.50.181.1-24'")
    parser.add_argument("--map", required=True,
                        help="Full Sapro map path (e.g. /opt/sapro/maps/default/default.map)")
    parser.add_argument("--duration", type=float, default=15,
                        help="Test duration in seconds (default: 15)")
    parser.add_argument("--traps-per-batch", type=int, default=1,
                        help="Number of traps per sapcnsl execution (default: 1, max: 10)")
    parser.add_argument("--workers", type=int, default=48,
                        help="Thread pool size for concurrent strategies (default: 48)")
    parser.add_argument("--ssh-pool-size", type=int, default=8,
                        help="Number of SSH connections in pool for strategies C/D (default: 8)")
    parser.add_argument("--strategies", default="A,B,C,D",
                        help="Comma-separated strategies to run: A=serial, B=concurrent-single-ssh, "
                             "C=concurrent-pool, D=concurrent-combined (default: A,B,C,D)")
    parser.add_argument("--ssh-host", default=None,
                        help="SSH host (default: from settings)")
    parser.add_argument("--ssh-user", default=None,
                        help="SSH user (default: from settings)")
    parser.add_argument("--ssh-pass", default=None,
                        help="SSH password (default: from settings)")

    args = parser.parse_args()

    simulators = parse_simulator_range(args.simulators)
    strategies = [s.strip().upper() for s in args.strategies.split(",")]
    traps_per_batch = min(args.traps_per_batch, 10)  # respect _MAX_TRAPS_PER_BATCH

    ssh_host = args.ssh_host or (
        "localhost" if settings.ENVIRONMENT == "production" else settings.SAPRO_SSH_HOST
    )
    ssh_user = args.ssh_user or settings.SAPRO_SSH_USER
    ssh_pass = args.ssh_pass or settings.SAPRO_SSH_PASSWORD

    print(f"\n{'#' * 70}")
    print(f"  SNMP TRAP THROUGHPUT BENCHMARK")
    print(f"{'#' * 70}")
    print(f"  CC IP:             {args.cc_ip}")
    print(f"  Simulators:        {len(simulators)} devices")
    print(f"  Map:               {args.map}")
    print(f"  Duration:          {args.duration}s per strategy")
    print(f"  Traps/batch:       {traps_per_batch}")
    print(f"  Workers:           {args.workers}")
    print(f"  SSH host:          {ssh_host}")
    print(f"  SSH pool size:     {args.ssh_pool_size}")
    print(f"  Strategies:        {', '.join(strategies)}")
    print(f"{'#' * 70}\n")

    # Quick connectivity test
    print("Testing SSH connectivity...")
    test_ssh = BenchmarkSSHClient(ssh_host, ssh_user, ssh_pass)
    try:
        test_ssh.connect()
        ok, out = test_ssh.execute("echo ok", timeout=10)
        if not ok:
            print(f"  ERROR: SSH test failed: {out}")
            sys.exit(1)
        print(f"  SSH connection OK")
    except Exception as e:
        print(f"  ERROR: Cannot connect to SSH: {e}")
        sys.exit(1)
    finally:
        test_ssh.close()

    # Verify sapcnsl exists
    test_ssh = BenchmarkSSHClient(ssh_host, ssh_user, ssh_pass)
    try:
        test_ssh.connect()
        ok, _ = test_ssh.execute("test -x /opt/sapro/bin/sapcnsl", timeout=10)
        if not ok:
            print("  WARNING: /opt/sapro/bin/sapcnsl not found — traps may fail")
        else:
            print("  sapcnsl found")
    finally:
        test_ssh.close()

    # Verify map file exists
    test_ssh = BenchmarkSSHClient(ssh_host, ssh_user, ssh_pass)
    try:
        test_ssh.connect()
        ok, _ = test_ssh.execute(f"test -f {args.map}", timeout=10)
        if not ok:
            print(f"  WARNING: Map file {args.map} not found")
        else:
            print(f"  Map file verified")
    finally:
        test_ssh.close()

    results: List[StrategyResult] = []

    # --- Strategy A ---
    if "A" in strategies:
        print(f"\n>>> Running Strategy A: Serial baseline ({args.duration}s)...")
        sr = strategy_serial(
            ssh_host, ssh_user, ssh_pass,
            args.cc_ip, simulators, args.map,
            args.duration, traps_per_batch,
        )
        results.append(sr)
        print_strategy_report(sr)

    # --- Strategy B ---
    if "B" in strategies:
        print(f"\n>>> Running Strategy B: Concurrent, single SSH ({args.duration}s)...")
        sr = strategy_concurrent_single_ssh(
            ssh_host, ssh_user, ssh_pass,
            args.cc_ip, simulators, args.map,
            args.duration, traps_per_batch, args.workers,
        )
        results.append(sr)
        print_strategy_report(sr)

    # --- Strategy C ---
    if "C" in strategies:
        print(f"\n>>> Running Strategy C: Concurrent, SSH pool ({args.duration}s)...")
        sr = strategy_concurrent_pool(
            ssh_host, ssh_user, ssh_pass,
            args.cc_ip, simulators, args.map,
            args.duration, traps_per_batch, args.workers,
            args.ssh_pool_size,
        )
        results.append(sr)
        print_strategy_report(sr)

    # --- Strategy D ---
    if "D" in strategies:
        print(f"\n>>> Running Strategy D: Combined cmd + SSH pool ({args.duration}s)...")
        sr = strategy_concurrent_combined(
            ssh_host, ssh_user, ssh_pass,
            args.cc_ip, simulators, args.map,
            args.duration, traps_per_batch, args.workers,
            args.ssh_pool_size,
        )
        results.append(sr)
        print_strategy_report(sr)

    # --- Comparison Summary ---
    if len(results) > 1:
        print(f"\n{'=' * 70}")
        print(f"  COMPARISON SUMMARY")
        print(f"{'=' * 70}")
        print(f"  {'Strategy':<50s}  {'Traps/s':>8s}  {'Total':>6s}  {'Failed':>6s}")
        print(f"  {'-' * 50}  {'-' * 8}  {'-' * 6}  {'-' * 6}")
        for sr in results:
            print(f"  {sr.strategy_name:<50s}  {sr.throughput:>8.1f}  "
                  f"{sr.total_traps_sent:>6d}  {sr.total_traps_failed:>6d}")

        # Identify bottleneck
        print(f"\n  --- Bottleneck Analysis ---")
        if len(results) >= 2:
            a_tp = results[0].throughput if results[0].throughput > 0 else 0.001
            for sr in results[1:]:
                ratio = sr.throughput / a_tp
                if ratio > 1.5:
                    print(f"  {sr.strategy_name}: {ratio:.1f}x faster than serial")
                elif ratio > 0.7:
                    print(f"  {sr.strategy_name}: ~same as serial ({ratio:.1f}x)")
                else:
                    print(f"  {sr.strategy_name}: {ratio:.1f}x SLOWER than serial (contention!)")

        # Find best result
        best = max(results, key=lambda r: r.throughput)
        print(f"\n  BEST: {best.strategy_name}")
        print(f"        {best.throughput:.0f} traps/sec, "
              f"{best.total_traps_sent} traps in {best.duration_seconds:.1f}s")

    print(f"\n{'#' * 70}")
    print(f"  Benchmark complete.")
    print(f"{'#' * 70}\n")


if __name__ == "__main__":
    main()
