"""
UDP Packet Listener - Captures UDP packets and converts to PCAP format.

This module provides a lightweight UDP listener that captures IRP messages
and saves them as PCAP files for analysis with Wireshark.
"""

import socket
import struct
from pathlib import Path
from datetime import datetime
from typing import Optional
import threading
import time


class PcapHeader:
    """PCAP file header structure."""

    MAGIC_NUMBER = 0xa1b2c3d4  # Standard PCAP magic
    VERSION_MAJOR = 2
    VERSION_MINOR = 4
    TIMEZONE_OFFSET = 0
    TIMESTAMP_ACCURACY = 0
    SNAPLEN = 65535  # Max packet length
    NETWORK = 1  # Ethernet

    @staticmethod
    def get_header_bytes() -> bytes:
        """Get PCAP file header as bytes."""
        return struct.pack(
            '<IHHIIII',
            PcapHeader.MAGIC_NUMBER,
            PcapHeader.VERSION_MAJOR,
            PcapHeader.VERSION_MINOR,
            PcapHeader.TIMEZONE_OFFSET,
            PcapHeader.TIMESTAMP_ACCURACY,
            PcapHeader.SNAPLEN,
            PcapHeader.NETWORK
        )


class PacketRecord:
    """PCAP packet record header."""

    @staticmethod
    def get_record_header(packet_data: bytes, timestamp: float) -> bytes:
        """
        Get PCAP packet record header.

        Args:
            packet_data: The packet data bytes
            timestamp: Packet timestamp (Unix time)

        Returns:
            Packed record header bytes
        """
        ts_sec = int(timestamp)
        ts_usec = int((timestamp - ts_sec) * 1_000_000)
        packet_len = len(packet_data)

        # Record header format: ts_sec, ts_usec, incl_len, orig_len
        return struct.pack(
            '<IIII',
            ts_sec,
            ts_usec,
            packet_len,
            packet_len
        )


class UdpPacketListener:
    """
    Captures UDP packets and saves them to PCAP format.

    This listener is optimized for capturing IRP messages sent to port 2088.
    """

    def __init__(self,
                 listen_ip: str = "0.0.0.0",
                 listen_port: int = 2088,
                 output_dir: Optional[Path] = None):
        """
        Initialize UDP packet listener.

        Args:
            listen_ip: IP address to listen on
            listen_port: UDP port to listen on
            output_dir: Directory to save PCAP files (default: tests/pcap_captures/)
        """
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.output_dir = output_dir or (Path(__file__).parent / "pcap_captures")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.socket = None
        self.listening = False
        self.packets = []
        self.listener_thread = None

    def start(self, timeout: int = 10, max_packets: Optional[int] = None) -> str:
        """
        Start listening for UDP packets.

        Args:
            timeout: How long to listen (seconds)
            max_packets: Maximum packets to capture (None = no limit)

        Returns:
            Path to the generated PCAP file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pcap_file = self.output_dir / f"capture_{timestamp}.pcap"

        self.listening = True
        self.packets = []
        self.max_packets = max_packets

        # Start listener in background thread
        self.listener_thread = threading.Thread(
            target=self._listen_thread,
            args=(timeout,),
            daemon=True
        )
        self.listener_thread.start()

        print(f"[LISTENER] Listening on {self.listen_ip}:{self.listen_port} for {timeout}s...")
        print(f"[LISTENER] PCAP output: {pcap_file}")

        # Wait for listener to finish
        self.listener_thread.join(timeout + 1)

        # Save PCAP file
        self._save_pcap(pcap_file)
        print(f"[OK] Captured {len(self.packets)} packet(s) to {pcap_file}")

        return str(pcap_file)

    def _listen_thread(self, timeout: int) -> None:
        """Background thread that listens for packets."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.listen_ip, self.listen_port))
            self.socket.settimeout(1.0)  # 1 second timeout per receive

            start_time = time.time()
            receive_attempts = 0

            while self.listening and (time.time() - start_time) < timeout:
                try:
                    receive_attempts += 1
                    data, addr = self.socket.recvfrom(65535)
                    self.packets.append({
                        'timestamp': time.time(),
                        'src_ip': addr[0],
                        'src_port': addr[1],
                        'data': data
                    })
                    print(f"[LISTENER] Packet #{len(self.packets)}: {len(data)} bytes from {addr[0]}:{addr[1]}")

                    if self.max_packets and len(self.packets) >= self.max_packets:
                        break

                except socket.timeout:
                    continue

        except Exception as e:
            print(f"[ERROR] Listener error: {e}")
        finally:
            if self.socket:
                self.socket.close()
            self.listening = False

    def _save_pcap(self, output_path: Path) -> None:
        """
        Save captured packets to PCAP file.

        Args:
            output_path: Path to save PCAP file
        """
        with open(output_path, 'wb') as f:
            # Write PCAP header
            f.write(PcapHeader.get_header_bytes())

            # Write each packet
            for packet in self.packets:
                # Write packet record header
                record_header = PacketRecord.get_record_header(
                    packet['data'],
                    packet['timestamp']
                )
                f.write(record_header)

                # Write packet data
                f.write(packet['data'])

    def stop(self) -> None:
        """Stop listening."""
        self.listening = False
        if self.socket:
            self.socket.close()

    def get_packet_count(self) -> int:
        """Get number of captured packets."""
        return len(self.packets)


def create_test_listener(message_id: int,
                        listen_ip: str = "0.0.0.0",
                        listen_port: int = 2088,
                        timeout: int = 10) -> str:
    """
    Create a test listener for capturing a message.

    Args:
        message_id: Message ID being tested
        listen_ip: IP to listen on
        listen_port: Port to listen on
        timeout: Timeout in seconds

    Returns:
        Path to generated PCAP file
    """
    listener = UdpPacketListener(listen_ip, listen_port)
    pcap_file = listener.start(timeout=timeout, max_packets=1)
    return pcap_file


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="UDP Packet Listener for IRP messages")
    parser.add_argument("--timeout", type=int, default=30, help="Listening timeout in seconds (default: 30)")
    parser.add_argument("--max-packets", type=int, default=None, help="Maximum packets to capture (default: unlimited)")
    args = parser.parse_args()

    listener = UdpPacketListener()
    pcap_file = listener.start(timeout=args.timeout, max_packets=args.max_packets)
    print(f"PCAP file created: {pcap_file}")


# Convenience alias
UDPListener = UdpPacketListener


