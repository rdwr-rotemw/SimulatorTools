"""
HTTP client interface for Sapro API interactions (stubbed).

This module defines a `SaproClient` class with method signatures the
application will call. Implement the HTTP logic later (e.g., using
`httpx.AsyncClient` or `requests`). For now the methods are async
stubs that should be replaced with real implementations when available.
"""
from typing import Any, Dict, List, Optional


class SaproClient:
    """Client for interacting with Sapro simulators API.

    Example usage:
        client = SaproClient(base_url="https://sapro.example.local", api_key="...")
        await client.get_simulators()

    Implementers: replace stub methods with real HTTP calls.
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: int = 30):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        # TODO: create an async HTTP client (httpx.AsyncClient) and manage lifecycle

    async def get_simulators(self) -> List[Dict[str, Any]]:
        """Return list of simulators from Sapro (stub).

        Replace with real API call and response parsing.
        """
        # TODO: perform async HTTP GET to self.base_url + '/simulators'
        return []

    async def add_simulator(self, simulator_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a simulator to Sapro and return created resource (stub).
        """
        # TODO: POST to Sapro API
        return {"status": "not_implemented", "data": simulator_data}

    async def edit_simulator(self, simulator_ip: str, simulator_data: Dict[str, Any]) -> Dict[str, Any]:
        """Edit a simulator identified by IP (stub)."""
        # TODO: PUT to Sapro API
        return {"status": "not_implemented", "ip": simulator_ip, "data": simulator_data}

    async def delete_simulator(self, simulator_ip: str) -> bool:
        """Delete simulator on Sapro by IP. Return True on success (stub)."""
        # TODO: DELETE to Sapro API
        return False


__all__ = ["SaproClient"]

