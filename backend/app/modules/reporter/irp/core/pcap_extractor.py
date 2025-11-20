"""
PCAP Packet Extractor - Exports packet bytes from PCAP files in Wireshark format.

This module reads PCAP files and exports packet dissections as plain text
following Wireshark's export format with all details expanded and no summary.
"""

import struct
from pathlib import Path
from typing import List, Dict, Optional


class PcapReader:
    """Reads PCAP files and extracts packet data."""

    PCAP_MAGIC = 0xa1b2c3d4

    def __init__(self, pcap_file: Path):
        """
        Initialize PCAP reader.

        Args:
            pcap_file: Path to PCAP file
        """
        self.pcap_file = Path(pcap_file)
        if not self.pcap_file.exists():
            raise FileNotFoundError(f"PCAP file not found: {pcap_file}")

    def read_packets(self) -> List[Dict]:
        """
        Read all packets from PCAP file.

        Returns:
            List of packet dictionaries with metadata and raw data
        """
        packets = []

        try:
            with open(self.pcap_file, 'rb') as f:
                # Read and verify PCAP header
                pcap_header = f.read(24)
                if len(pcap_header) < 24:
                    raise ValueError("Invalid PCAP file: header too short")

                magic = struct.unpack('<I', pcap_header[0:4])[0]
                if magic != self.PCAP_MAGIC:
                    raise ValueError(f"Invalid PCAP magic: {hex(magic)}")

                # Read packet records
                packet_num = 1
                while True:
                    record_header = f.read(16)
                    if len(record_header) < 16:
                        break

                    ts_sec, ts_usec, incl_len, orig_len = struct.unpack(
                        '<IIII', record_header
                    )

                    packet_data = f.read(incl_len)
                    if len(packet_data) < incl_len:
                        break

                    packets.append({
                        'packet_num': packet_num,
                        'timestamp': ts_sec + ts_usec / 1_000_000,
                        'length': incl_len,
                        'data': packet_data
                    })
                    packet_num += 1

        except Exception as e:
            raise ValueError(f"Error reading PCAP file: {e}")

        return packets


class PacketDissector:
    """Dissects packet data into layers."""

    @staticmethod
    def has_ethernet_header(packet_data: bytes) -> bool:
        """
        Check if packet has real Ethernet header.

        Args:
            packet_data: Raw packet bytes

        Returns:
            True if packet starts with Ethernet header, False if raw payload
        """
        if len(packet_data) < 14:
            return False

        # Check if it starts with IRP message (version 0x91) - no Ethernet header
        if packet_data[0] == 0x91:
            return False

        # Check Ethernet type field at offset 12-14
        eth_type = struct.unpack('!H', packet_data[12:14])[0]
        # Common Ethernet types: 0x0800=IPv4, 0x0806=ARP, 0x86DD=IPv6
        return eth_type in [0x0800, 0x0806, 0x86DD]

    @staticmethod
    def create_mock_headers(payload: bytes) -> bytes:
        """
        Create mock Ethernet/IP/UDP headers for payload (loopback packet).

        Args:
            payload: IRP message payload

        Returns:
            Complete packet with mock headers
        """
        # Mock Ethernet header (14 bytes)
        eth_dest = b'\x00\x50\x56\x9e\x47\xa0'  # Mock destination MAC
        eth_src = b'\x00\x50\x56\x9e\x05\xe9'   # Mock source MAC
        eth_type = b'\x08\x00'  # IPv4
        ethernet_header = eth_dest + eth_src + eth_type

        # Mock IP header (20 bytes, no options)
        ip_version_ihl = 0x45  # Version 4, IHL 5
        ip_dscp_ecn = 0x00
        ip_total_len = 20 + 8 + len(payload)  # IP + UDP + payload
        ip_id = b'\x65\x5d'
        ip_flags_frag = b'\x00\x00'
        ip_ttl = 0x3f
        ip_protocol = 0x11  # UDP
        ip_checksum = b'\xfb\x9a'  # Mock checksum
        ip_src = b'\xac\x10\x16\x2e'  # 172.16.22.46
        ip_dst = b'\xac\x11\xac\x5f'  # 172.17.172.95

        ip_header = struct.pack('!BBHHHBBH4s4s',
            ip_version_ihl,
            ip_dscp_ecn,
            ip_total_len,
            int.from_bytes(ip_id, 'big'),
            int.from_bytes(ip_flags_frag, 'big'),
            ip_ttl,
            ip_protocol,
            int.from_bytes(ip_checksum, 'big'),
            ip_src,
            ip_dst
        )

        # Mock UDP header (8 bytes)
        udp_src_port = 0x0828  # 2088
        udp_dst_port = 0x0828  # 2088
        udp_len = 8 + len(payload)
        udp_checksum = 0x0000

        udp_header = struct.pack('!HHHH',
            udp_src_port,
            udp_dst_port,
            udp_len,
            udp_checksum
        )

        return ethernet_header + ip_header + udp_header + payload

    @staticmethod
    def get_udp_payload(packet_data: bytes) -> Optional[bytes]:
        """
        Extract UDP payload from a packet.

        Handles both:
        - Ethernet frame with IPv4 and UDP headers
        - Raw UDP payload (no Ethernet/IP headers) - returns as-is

        Args:
            packet_data: Raw packet bytes

        Returns:
            UDP payload or None if not found
        """
        if not packet_data or len(packet_data) < 8:
            return None

        # Check if this looks like raw UDP payload (IRP message)
        # IRP messages start with version byte 0x91
        if len(packet_data) >= 1 and packet_data[0] == 0x91:
            # This is likely a raw IRP message payload (no IP/Ethernet headers)
            return packet_data

        # Try to parse as Ethernet + IP + UDP
        if len(packet_data) < 14:  # Minimum Ethernet header
            # Too short for Ethernet, return as-is (might be raw IP)
            return packet_data

        # Skip Ethernet header (14 bytes) to get to IP
        eth_type = struct.unpack('!H', packet_data[12:14])[0]

        if eth_type != 0x0800:  # IPv4
            # Not IPv4, return whole packet
            return packet_data

        ip_header = packet_data[14:]
        if len(ip_header) < 20:
            return None

        # Extract IP header length
        ihl = (ip_header[0] & 0x0F) * 4
        protocol = ip_header[9]

        if protocol != 17:  # UDP
            return None

        # Extract UDP payload (skip IP and UDP headers)
        udp_data = packet_data[14 + ihl:]
        if len(udp_data) < 8:  # UDP header minimum
            return None

        # UDP header is 8 bytes, skip it
        payload = udp_data[8:]
        return payload if payload else None

    @staticmethod
    def format_bytes_line(offset: int, data: bytes, line_size: int = 16) -> str:
        """
        Format bytes in Wireshark-style hex dump.

        Args:
            offset: Byte offset
            data: Bytes to format
            line_size: Bytes per line

        Returns:
            Formatted line
        """
        hex_str = ' '.join(f'{b:02x}' for b in data[:line_size])
        ascii_str = ''.join(
            chr(b) if 32 <= b < 127 else '.'
            for b in data[:line_size]
        )

        return f"{offset:04x}  {hex_str:<{line_size * 3}}  {ascii_str}"


class WiresharkExporter:
    """Exports packet data in Wireshark format."""

    @staticmethod
    def export_packets_text(pcap_file: Path,
                           output_file: Path,
                           selected_packets: Optional[List[int]] = None,
                           expand_all: bool = True) -> None:
        """
        Export packets from PCAP file in Wireshark format.

        Format:
        - No summary lines
        - All details expanded
        - Bytes only (no timestamp or secondary data)
        - Hex dump format like Wireshark

        Args:
            pcap_file: Input PCAP file
            output_file: Output text file
            selected_packets: List of packet numbers to export (None = all)
            expand_all: Always expand all details
        """
        reader = PcapReader(pcap_file)
        packets = reader.read_packets()

        with open(output_file, 'w') as f:
            for packet in packets:
                # Check if we should export this packet
                if selected_packets and packet['packet_num'] not in selected_packets:
                    continue

                # Get packet data - add mock headers if it's a loopback packet (raw payload)
                packet_data = packet['data']
                if not PacketDissector.has_ethernet_header(packet_data):
                    # This is a loopback packet with no Ethernet headers - add mock headers
                    payload = PacketDissector.get_udp_payload(packet_data)
                    if payload:
                        packet_data = PacketDissector.create_mock_headers(payload)

                # Extract UDP payload
                payload = PacketDissector.get_udp_payload(packet_data)

                f.write(f"\nFrame {packet['packet_num']}: {len(packet_data)} bytes on wire, {len(packet_data)} bytes captured\n")
                f.write(f"{'=' * 80}\n\n")

                if payload:
                    # Write Ethernet header dissection
                    eth_dest = packet_data[0:6].hex(':')
                    eth_src = packet_data[6:12].hex(':')
                    f.write("Ethernet II\n")
                    f.write(f"    Destination: {eth_dest}\n")
                    f.write(f"    Source: {eth_src}\n")
                    f.write(f"    Type: IPv4 (0x0800)\n\n")

                    # Write IP header dissection
                    ip_version_ihl = packet_data[14]
                    ip_src = '.'.join(str(b) for b in packet_data[26:30])
                    ip_dst = '.'.join(str(b) for b in packet_data[30:34])
                    f.write("Internet Protocol Version 4\n")
                    f.write(f"    Version: 4, Header Length: 20 bytes\n")
                    f.write(f"    Source Address: {ip_src}\n")
                    f.write(f"    Destination Address: {ip_dst}\n\n")

                    # Write UDP header dissection
                    udp_src = struct.unpack('!H', packet_data[34:36])[0]
                    udp_dst = struct.unpack('!H', packet_data[36:38])[0]
                    f.write("User Datagram Protocol\n")
                    f.write(f"    Source Port: {udp_src}\n")
                    f.write(f"    Destination Port: {udp_dst}\n")
                    f.write(f"    UDP payload ({len(payload)} bytes)\n\n")

                    # Write IRP Protocol Data section
                    f.write("IRP Protocol Data\n")
                    f.write(f"    Protocol Version: 0x{payload[0]:02x}\n")
                    f.write(f"    Report Type: Data Report\n\n")

                    # Write hex dump
                    f.write(f"{'=' * 80}\n\n")
                    offset = 0
                    while offset < len(packet_data):
                        chunk = packet_data[offset:offset + 16]
                        line = PacketDissector.format_bytes_line(offset, chunk)
                        f.write(line + "\n")
                        offset += 16
                else:
                    f.write("No UDP payload found\n")

        print(f"[OK] Exported {len(packets)} packet(s) to {output_file}")


class PcapExtractor:
    """
    High-level interface for extracting packets from PCAP files.
    """

    def __init__(self, pcap_file: Path):
        """Initialize extractor."""
        self.pcap_file = Path(pcap_file)

    def extract_bytes_to_text(self, output_file: Optional[Path] = None) -> Path:
        """
        Extract packet bytes to text file.

        Args:
            output_file: Output file path (auto-generated if None)

        Returns:
            Path to generated text file
        """
        if output_file is None:
            output_dir = self.pcap_file.parent
            stem = self.pcap_file.stem
            output_file = output_dir / f"{stem}_extracted.txt"

        WiresharkExporter.export_packets_text(self.pcap_file, output_file)
        return output_file

    def get_packets(self) -> List[Dict]:
        """Get raw packet data."""
        reader = PcapReader(self.pcap_file)
        return reader.read_packets()

    def get_payload_bytes(self, packet_num: int = 1) -> Optional[bytes]:
        """
        Get payload bytes from a specific packet.

        Args:
            packet_num: Packet number (1-indexed)

        Returns:
            Payload bytes or None
        """
        reader = PcapReader(self.pcap_file)
        packets = reader.read_packets()

        if packet_num <= 0 or packet_num > len(packets):
            return None

        packet = packets[packet_num - 1]
        return PacketDissector.get_udp_payload(packet['data'])


def extract_pcap_to_text(pcap_file: Path) -> Path:
    """
    Convenience function to extract PCAP to text.

    Args:
        pcap_file: PCAP file to extract

    Returns:
        Path to extracted text file
    """
    extractor = PcapExtractor(pcap_file)
    return extractor.extract_bytes_to_text()


if __name__ == "__main__":
    # Demo usage
    import sys

    if len(sys.argv) > 1:
        pcap_path = Path(sys.argv[1])
        text_file = extract_pcap_to_text(pcap_path)
        print(f"Extracted to: {text_file}")
    else:
        print("Usage: python pcap_extractor.py <pcap_file>")

