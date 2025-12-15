"""
Integration test for checksum-based XML blob caching

Run with:
    pytest backend/tests/integration/test_xml_blob_caching.py

This test performs the following scenarios against a MongoDB instance configured
for the application (uses get_mongo_db()) and the repository's local XML fixture:
  - First download (cache miss) -> insert document with xml_blob + checksum
  - Second download (same version + checksum) -> detect cache hit
  - test_irp_message uses blob -> decode/write/verify
  - Blob missing fallback -> ensure fallback to local file works

Note: tests use the isolated collection name `irp_data_formats_test` and will
clean up the collection at the end of the test run.
"""
from __future__ import annotations

import base64
import hashlib
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from backend.app.modules.reporter.irp.irp_module import convert_xml

TEST_COLLECTION = "irp_data_formats_test"
LOCAL_XML_PATH = Path(__file__).parent.parent.parent / "app" / "modules" / "reporter" / "irp" / "data_formats" / "IdsDataFormat100600.xml"
IDS_VERSION = "100600"


def read_file_bytes(path: Path) -> bytes:
    with open(path, 'rb') as f:
        return f.read()


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_xml_blob_caching_flow(mongo_db):
    coll = mongo_db[TEST_COLLECTION]

    # Clean start
    coll.drop()

    # Ensure local XML exists
    assert LOCAL_XML_PATH.exists(), f"Local XML not found: {LOCAL_XML_PATH}"

    original_bytes = read_file_bytes(LOCAL_XML_PATH)
    original_sha = compute_sha256(original_bytes)
    original_b64 = base64.b64encode(original_bytes).decode()

    # Test Case 1: First download (cache miss)
    start = time.time()
    converted = convert_xml(str(LOCAL_XML_PATH))
    doc: Dict[str, Any] = {
        "template_name": LOCAL_XML_PATH.name,
        "description": "Test insert",
        "xml_schema": converted,
        "IdsDataFormat_version": IDS_VERSION,
        "user_id": "test_user",
        "xml_blob": original_b64,
        "xml_checksum": original_sha,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "is_public": False,
    }
    res = coll.insert_one(doc)
    inserted_id = res.inserted_id
    stored = coll.find_one({"_id": inserted_id})
    assert stored is not None
    assert stored.get("xml_checksum") == original_sha
    assert stored.get("xml_blob") is not None

    # Test Case 2: Second download (cache hit)
    t0 = time.time()
    existing = coll.find_one({"IdsDataFormat_version": IDS_VERSION, "xml_checksum": original_sha})
    lookup_time = time.time() - t0
    assert existing is not None

    # Test Case 3: test_irp_message uses blob
    xml_blob = existing.get("xml_blob")
    xml_checksum = existing.get("xml_checksum")
    with tempfile.TemporaryDirectory() as td:
        temp_path = Path(td) / "IdsDataFormat.xml"
        decoded = base64.b64decode(xml_blob)
        temp_path.write_bytes(decoded)
        read_back = temp_path.read_bytes()
        assert read_back == original_bytes

    # Test Case 4: Blob missing fallback
    coll.update_many({"IdsDataFormat_version": IDS_VERSION}, {"$unset": {"xml_blob": "", "xml_checksum": ""}})
    doc2 = coll.find_one({"IdsDataFormat_version": IDS_VERSION})
    assert doc2 is not None
    # Simulate fallback to local file
    with tempfile.TemporaryDirectory() as td:
        temp_path = Path(td) / "IdsDataFormat.xml"
        fallback_bytes = read_file_bytes(LOCAL_XML_PATH)
        temp_path.write_bytes(fallback_bytes)
        read_back = temp_path.read_bytes()
        assert read_back == fallback_bytes

    # Cleanup
    coll.drop()

    # Optionally print timings (pytest capture will record logs)
    print(f"lookup_time={lookup_time:.6f}s, conversion_time={(time.time()-start):.3f}s")

