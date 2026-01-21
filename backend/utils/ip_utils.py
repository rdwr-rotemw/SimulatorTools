from typing import List
import ipaddress
from fastapi import HTTPException, status


def parse_ip_range(ip_range: str) -> List[str]:
    """
    Parse an IP range string and return a list of IP addresses.

    Supports single IP addresses or ranges in the format 'START_IP-END_IP'.

    Examples:
        - parse_ip_range("192.168.1.1") -> ["192.168.1.1"]
        - parse_ip_range("192.168.1.1-192.168.1.5") -> ["192.168.1.1", "192.168.1.2", "192.168.1.3", "192.168.1.4", "192.168.1.5"]

    Raises HTTPException with 400 status for invalid inputs.
    """
    MAX_RANGE = 255
    ip_range = ip_range.strip()

    if '-' not in ip_range:
        # Single IP
        try:
            ipaddress.ip_address(ip_range)
            return [ip_range]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid IP address: {ip_range}"
            )
    else:
        # Range
        parts = ip_range.split('-')
        if len(parts) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid IP range format: {ip_range}. Use format: 'START_IP-END_IP'"
            )
        start_str, end_str = parts[0].strip(), parts[1].strip()
        try:
            start = ipaddress.ip_address(start_str)
            end = ipaddress.ip_address(end_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid IP address: {start_str if '-' in ip_range else ip_range}"
            )
        if start > end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid IP range: start IP ({start_str}) is greater than end IP ({end_str})"
            )
        if start.version != 4 or end.version != 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only IPv4 addresses are supported"
            )
        start_int = int(start)
        end_int = int(end)
        num_ips = end_int - start_int + 1
        if num_ips > MAX_RANGE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="IP range too large. Maximum 255 IPs allowed per request."
            )
        ips = [str(ipaddress.ip_address(i)) for i in range(start_int, end_int + 1)]
        return ips
