from pathlib import Path
from typing import List, Dict, Optional
import struct
import asyncio
import threading
import pyshark
from .message_resolver import MessageResolver


class IRPPcapAnalyzer:
    """Analyzes PCAP files to extract IRP message information."""

    IRP_HEADER_FORMAT = '<BBIBBIB'
    IRP_HEADER_SIZE = 13
    IRP_VERSION = 0x91
    IRP_UDP_PORT = 2088

    def __init__(self, schema=None):
        """
        Initialize analyzer with optional schema for message resolution.

        Args:
            schema: Optional parsed ConvertXml schema object.
                   If None, will show message IDs without names.
        """
        self.schema = schema
        self.resolver = MessageResolver(schema.schema) if schema else None

    def analyze_pcap(self, pcap_file: Path) -> Dict:
        """
        Analyze PCAP file and extract IRP message statistics.
        Runs PyShark in a separate thread to avoid event loop conflicts.

        Args:
            pcap_file: Path to PCAP file

        Returns:
            Dict with analysis results
        """
        results = {
            "total_packets": 0,
            "irp_packets": 0,
            "messages": [],
            "errors": [],
            "schema_info": {
                "schema_available": self.schema is not None,
                "schema_version": getattr(self.schema, 'version', None) if self.schema else None
            }
        }

        message_stats = {}  # {message_id: {"count": int, "packets": [int], "schema_versions": set()}}

        def run_pyshark():
            """Run PyShark capture in a separate thread with its own event loop."""
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                cap = pyshark.FileCapture(str(pcap_file))
                packet_num = 0

                for packet in cap:
                    packet_num += 1
                    results["total_packets"] = packet_num

                    # Check if IRP packet (UDP port 2088)
                    if not self._is_irp_packet(packet):
                        continue

                    # Extract UDP payload
                    udp_payload = self._get_udp_payload(packet)
                    if not udp_payload:
                        continue

                    # Parse IRP header
                    header = self._extract_irp_header(udp_payload)
                    if not header:
                        results["errors"].append({
                            "packet_number": packet_num,
                            "error": "Invalid IRP header"
                        })
                        continue

                    results["irp_packets"] += 1
                    message_id = str(header["message_id"])

                    # Track message statistics
                    if message_id not in message_stats:
                        message_stats[message_id] = {
                            "count": 0,
                            "packets": [],
                            "schema_versions": set()
                        }

                    message_stats[message_id]["count"] += 1
                    message_stats[message_id]["packets"].append(packet_num)
                    message_stats[message_id]["schema_versions"].add(header["schema_version"])

                cap.close()

            except Exception as e:
                raise ValueError(f"Error reading PCAP: {str(e)}")
            finally:
                loop.close()

        # Run PyShark in separate thread
        thread = threading.Thread(target=run_pyshark)
        thread.start()
        thread.join()

        # Convert statistics to output format
        for message_id, stats in message_stats.items():
            # Try to resolve message name
            message_name = self._resolve_message_name(message_id)

            results["messages"].append({
                "message_id": message_id,
                "message_name": message_name,
                "count": stats["count"],
                "packet_numbers": stats["packets"],
                "schema_versions": sorted(list(stats["schema_versions"]))
            })

        # Sort by message_id (numeric)
        results["messages"].sort(key=lambda x: int(x["message_id"]))

        return results

    def _resolve_message_name(self, message_id: str) -> str:
        """
        Resolve message ID to name using schema.

        Args:
            message_id: Message ID as string

        Returns:
            Message name or "Message <id> (Unknown)" if not in schema
        """
        if not self.resolver:
            return f"Message {message_id} (No schema loaded)"

        try:
            # Try to get name from schema
            name = self.resolver.get_message_name(message_id)
            # If resolver returns the ID back (not found), format as unknown
            if name == message_id:
                return f"Message {message_id} (Unknown)"
            return name
        except:
            return f"Message {message_id} (Unknown)"

    def _is_irp_packet(self, packet) -> bool:
        """
        Check if PyShark packet is an IRP packet (UDP port 2088).

        Args:
            packet: PyShark packet object

        Returns:
            True if packet is UDP destined to port 2088
        """
        try:
            if 'UDP' not in packet:
                return False
            return int(packet.udp.dstport) == self.IRP_UDP_PORT
        except:
            return False

    def _get_udp_payload(self, packet) -> Optional[bytes]:
        """
        Extract UDP payload from PyShark packet.
        PyShark handles fragmentation, so we get complete payload.

        Args:
            packet: PyShark packet object

        Returns:
            UDP payload as bytes or None
        """
        try:
            if 'UDP' not in packet:
                return None

            # Get payload hex string and convert to bytes
            payload_hex = packet.udp.payload.replace(':', '')
            return bytes.fromhex(payload_hex)
        except:
            return None

    def _extract_irp_header(self, udp_payload: bytes) -> Optional[Dict]:
        """
        Extract and parse IRP header from UDP payload.

        Args:
            udp_payload: Raw UDP payload bytes

        Returns:
            Dict with parsed header fields or None if invalid:
            {
                "version": int,
                "event_type": int,
                "timestamp": int,
                "parser_version": int,
                "byte_order": int,
                "schema_version": int,  # Informational only
                "message_id": int
            }
        """
        # Validate length
        if len(udp_payload) < self.IRP_HEADER_SIZE:
            return None

        # Parse header
        try:
            header_data = struct.unpack(
                self.IRP_HEADER_FORMAT,
                udp_payload[:self.IRP_HEADER_SIZE]
            )

            # Validate version byte only
            if header_data[0] != self.IRP_VERSION:
                return None

            return {
                "version": header_data[0],
                "event_type": header_data[1],
                "timestamp": header_data[2],
                "parser_version": header_data[3],
                "byte_order": header_data[4],
                "schema_version": header_data[5],  # Keep for info, don't validate
                "message_id": header_data[6]  # The code field - this is what we need!
            }
        except struct.error:
            return None


def analyze_irp_pcap_file(pcap_file: Path, schema=None) -> Dict:
    """
    Convenience function to analyze IRP PCAP file.

    Args:
        pcap_file: Path to PCAP file
        schema: Optional parsed schema object (for name resolution)

    Returns:
        Analysis results dict
    """
    analyzer = IRPPcapAnalyzer(schema)
    return analyzer.analyze_pcap(pcap_file)
