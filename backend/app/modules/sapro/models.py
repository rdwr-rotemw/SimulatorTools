from dataclasses import dataclass

@dataclass
class SaproDevice:
    ip_address: str
    map: str
    status: str
    type: str = None
    version: str = None