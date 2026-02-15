"""
Polling module for DefensePro API endpoint simulation.

This module provides functionality to:
- Generate XMF (TCL) files that simulate DefensePro REST API endpoints
- Manage polling configuration templates in MongoDB
- Load polling configurations onto simulators via Sapro

Main components:
- PollingService: Template CRUD and XMF loading operations
- XMFGenerator: Converts endpoint configurations to XMF (TCL) scripts

The XMF files are executed by Sapro's embedded HTTP server to respond to
CyberController's polling requests with simulated attack data, traffic statistics,
and other DefensePro API responses.
"""

from .polling_service import PollingService
from .xmf_generator import XMFGenerator

__all__ = [
    "PollingService",
    "XMFGenerator",
]
