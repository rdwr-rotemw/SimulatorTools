"""
Pytest fixtures for backend integration tests.

Provides:
- mongo_db fixture that returns a pymongo Database instance using application settings
  Skips automatically when MongoDB is not reachable (e.g. in CI without a DB service).

Usage in tests:
    def test_x(mongo_db):
        coll = mongo_db['irp_data_formats_test']

"""
from __future__ import annotations

import pytest

from backend.app.utils.database import get_mongo_db


@pytest.fixture(scope="session")
def mongo_db():
    """Return a pymongo Database instance for tests (session scoped).

    Skips the test if MongoDB is not reachable within 2 seconds.
    """
    db = get_mongo_db()
    try:
        db.client.server_info()
    except Exception as exc:
        pytest.skip(f"MongoDB not available: {exc}")
    return db

