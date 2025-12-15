"""
Pytest fixtures for backend integration tests.

Provides:
- mongo_db fixture that returns a pymongo Database instance using application settings

Usage in tests:
    def test_x(mongo_db):
        coll = mongo_db['irp_data_formats_test']

"""
from __future__ import annotations

import pytest

from backend.app.utils.database import get_mongo_db


@pytest.fixture(scope="session")
def mongo_db():
    """Return a pymongo Database instance for tests (session scoped)."""
    return get_mongo_db()

