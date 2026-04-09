# SNMP Engine Implementation Plan

## Purpose
Step-by-step implementation guide for building the SNMP simulation engine to replace SAPRO. Each phase is a self-contained deliverable with its own test suite. Phases are ordered by dependency — each builds on the previous.

## Testing Strategy
Every phase includes unit tests with mocks that run independently of external dependencies (no SAPRO, no live SNMP, no CC). Integration tests run against real MongoDB and real SNMP tools. Tests are written DURING implementation, not after. A phase is not complete until all its tests pass.

```
snmp-engine/
  tests/
    unit/           ← Mocked, fast, no external deps
    integration/    ← Real MongoDB, real SNMP tools
    fixtures/       ← Shared test data (sample schemas, device docs, pcap replays)
```

---

## Phase 1: SNMP Protocol Service Skeleton

**Goal:** A Docker service that receives SNMP packets on a device IP, decodes them, and returns a hardcoded response.

### Sprint 1.1 — SNMP Codec
| ID | Task | Type | Est |
|----|------|------|-----|
| 1.1.1 | Evaluate SNMP libraries (pysnmp, snmplib, raw pyasn1) — pick one | Research | 0.5d |
| 1.1.2 | Implement `snmp_codec.py` — decode v2c Get/GetNext/GetBulk/Set PDU | Code | 1d |
| 1.1.3 | Implement `snmp_codec.py` — encode v2c GetResponse PDU | Code | 0.5d |

**Unit Tests (mocked):**
- [ ] `test_decode_get_request` — raw bytes → structured request (operation, community, oid list)
- [ ] `test_decode_getnext_request` — same for GetNext
- [ ] `test_decode_getbulk_request` — includes non-repeaters and max-repetitions
- [ ] `test_decode_set_request` — includes typed varbinds (Integer, OctetString, ObjectID, IpAddress)
- [ ] `test_encode_get_response` — structured response → raw bytes
- [ ] `test_encode_error_response` — noSuchInstance, noAccess, endOfMibView
- [ ] `test_community_extraction` — correct community string parsed from PDU
- [ ] `test_malformed_packet` — garbage bytes don't crash, return appropriate error
- [ ] `test_roundtrip` — encode response → decode it back → same data

**Fixtures:**
- Captured SNMP packets from real CC sync (from our tcpdump sessions) as byte arrays
- Expected decoded structures for each

### Sprint 1.2 — UDP Listener & Service
| ID | Task | Type | Est |
|----|------|------|-----|
| 1.2.1 | Implement `udp_listener.py` — bind to IP:161, receive/send UDP | Code | 0.5d |
| 1.2.2 | Implement `server.py` — management listener on 127.0.0.1:8889 (8888 taken by proxy), health check | Code | 0.5d |
| 1.2.3 | Implement `listener_manager.py` — MongoDB-driven dynamic listeners (same pattern as proxy) | Code | 0.5d |
| 1.2.4 | Dockerfile + docker-compose entry | Infra | 0.5d |

**Unit Tests (mocked):**
- [ ] `test_listener_binds_to_ip` — mock socket, verify bind called with correct IP:161
- [ ] `test_listener_routes_to_codec` — mock codec, verify packet passed to decode
- [ ] `test_listener_sends_response` — mock socket.sendto, verify encoded response sent
- [ ] `test_listener_manager_adds_device` — mock MongoDB, new IP in collection → listener started
- [ ] `test_listener_manager_removes_device` — IP removed from collection → listener stopped
- [ ] `test_health_endpoint` — HTTP GET /_health returns 200

**Integration Tests:**
- [ ] `test_snmpget_hardcoded` — real snmpget against running engine, returns hardcoded sysObjectID
- [ ] `test_engine_starts_no_devices` — engine starts with empty device_registry, health OK

### Sprint 1 Definition of Done
- All unit tests pass
- Integration test: `snmpget -v 2c -c public {test_ip} sysObjectID.0` returns hardcoded value
- Docker image builds and runs

---

## Phase 2: MongoDB Data Store & Schema

**Goal:** Define the MongoDB collections, create the schema format, and manually insert a test device to verify reads.

### Sprint 2.1 — Schema & Data Model
| ID | Task | Type | Est |
|----|------|------|-----|
| 2.1.1 | Define Pydantic models for `mib_schemas` document | Code | 0.5d |
| 2.1.2 | Define Pydantic models for `device_instances` document | Code | 0.5d |
| 2.1.3 | Define Pydantic models for `device_registry` document | Code | 0.25d |
| 2.1.4 | MongoDB index creation and validation | Code | 0.25d |

**Unit Tests (mocked):**
- [ ] `test_schema_model_validation` — valid schema document passes, invalid rejects
- [ ] `test_device_instance_model` — valid device doc passes, missing required fields reject
- [ ] `test_scalar_oid_format` — OIDs must end with .0, dotted notation only
- [ ] `test_table_column_references` — column oid_suffix matches schema definition
- [ ] `test_augments_relationship` — augmented table references valid base table
- [ ] `test_index_encoding_field` — each index column has "implied" or "length_prefixed"

### Sprint 2.2 — Test Device Bootstrap
| ID | Task | Type | Est |
|----|------|------|-----|
| 2.2.1 | Write bootstrap script — parse existing 10.4 VAR/CMF → MongoDB documents | Code | 1d |
| 2.2.2 | Device data access layer — `device_store.py` (get device, get scalar, get table rows) | Code | 0.5d |

**Unit Tests (mocked):**
- [ ] `test_get_device_by_ip` — mock MongoDB, returns device document
- [ ] `test_get_device_not_found` — mock MongoDB, returns None
- [ ] `test_get_scalar_value` — lookup scalar by OID from device document
- [ ] `test_get_table_row` — lookup table row by entry OID + index
- [ ] `test_get_table_all_rows` — returns all rows sorted by index OID

**Integration Tests:**
- [ ] `test_bootstrap_creates_device` — run bootstrap script, verify document in MongoDB
- [ ] `test_bootstrap_scalar_count` — verify ~3000+ scalars populated
- [ ] `test_bootstrap_table_structure` — verify table_rows has expected tables

### Sprint 2 Definition of Done
- All unit tests pass
- Test device in MongoDB with real 10.4 data
- device_store.py can read all scalars and table rows

---

## Phase 3: OID Resolver — Get, GetNext, GetBulk

**Goal:** The engine reads from MongoDB and returns correct SNMP responses for read operations.

### Sprint 3.1 — Get & GetNext
| ID | Task | Type | Est |
|----|------|------|-----|
| 3.1.1 | Implement `oid_resolver.py` — `get(device, oid)` | Code | 0.5d |
| 3.1.2 | Implement OID index — sorted list of all active OIDs per device | Code | 0.5d |
| 3.1.3 | Implement `get_next(device, oid)` — binary search on index | Code | 0.5d |
| 3.1.4 | GetNext across table/scalar boundaries | Code | 0.5d |

**Unit Tests (mocked):**
- [ ] `test_get_scalar_exists` — returns (oid, type, value)
- [ ] `test_get_scalar_not_exists` — returns noSuchInstance
- [ ] `test_get_table_column_instance` — returns correct column value for row
- [ ] `test_get_table_column_no_row` — returns noSuchInstance
- [ ] `test_getnext_scalar` — sysDescr.0 → sysObjectID.0
- [ ] `test_getnext_last_scalar` — last scalar → first table instance
- [ ] `test_getnext_table_column` — walks rows within a column
- [ ] `test_getnext_last_row` — last row of column → first row of next column
- [ ] `test_getnext_last_column` — last column of table → next table or scalar
- [ ] `test_getnext_end_of_mib` — past last OID → endOfMibView
- [ ] `test_oid_index_sorted` — verify index is lexicographically sorted (OID numeric comparison)
- [ ] `test_oid_index_includes_table_instances` — all row OIDs present
- [ ] `test_dynamic_values` — sysUpTime returns computed value, not stored

### Sprint 3.2 — GetBulk & Wire-Up
| ID | Task | Type | Est |
|----|------|------|-----|
| 3.2.1 | Implement `get_bulk(device, non_repeaters, max_reps, oid_list)` | Code | 0.5d |
| 3.2.2 | Wire resolver into UDP listener — replace hardcoded responses | Code | 0.5d |
| 3.2.3 | Community string validation | Code | 0.25d |

**Unit Tests (mocked):**
- [ ] `test_getbulk_non_repeaters` — first N OIDs processed as Get
- [ ] `test_getbulk_max_repetitions` — remaining OIDs get max_reps rounds of GetNext
- [ ] `test_getbulk_mixed` — combination of non-repeaters and repeaters
- [ ] `test_getbulk_endofmib_padding` — endOfMibView fills remaining slots
- [ ] `test_community_mismatch` — wrong community → auth failure response
- [ ] `test_community_read_vs_write` — read community accepted for Get, write for Set

**Integration Tests:**
- [ ] `test_snmpget_from_mongodb` — real snmpget returns value from test device document
- [ ] `test_snmpwalk_system` — `snmpwalk system` returns all system scalars in correct order
- [ ] `test_snmpwalk_vacm_group` — walks VACM group table with correct index encoding
- [ ] `test_snmpbulkwalk_full` — full device walk, compare line count with SAPRO output
- [ ] `test_snmpwalk_diff` — diff snmpwalk output against captured SAPRO snmpwalk (fixture)

### Sprint 3 Definition of Done
- All unit and integration tests pass
- `snmpwalk` output matches SAPRO-based device (captured fixture)
- GetBulk with max-repetitions=10 works correctly

---

## Phase 4: Set Handler & RowStatus

**Goal:** The engine handles SNMP Set operations including row creation/deletion.

### Sprint 4.1 — Basic Set
| ID | Task | Type | Est |
|----|------|------|-----|
| 4.1.1 | Implement `set_handler.py` — validate and apply scalar Sets | Code | 0.5d |
| 4.1.2 | Value type validation (Integer range, OctetString length, ObjectID format) | Code | 0.5d |
| 4.1.3 | Access validation (RO → noAccess, RW/RC → allowed) | Code | 0.25d |

**Unit Tests (mocked):**
- [ ] `test_set_scalar_rw` — write to RW scalar, value updated
- [ ] `test_set_scalar_ro` — write to RO scalar → noAccess
- [ ] `test_set_integer_in_range` — value within constraints → accepted
- [ ] `test_set_integer_out_of_range` — value outside constraints → wrongValue
- [ ] `test_set_string_too_long` — exceeds max_length → wrongLength
- [ ] `test_set_wrong_type` — Integer to OctetString column → wrongType
- [ ] `test_set_multiple_varbinds` — all succeed → all applied
- [ ] `test_set_atomic_failure` — one fails → none applied

### Sprint 4.2 — RowStatus & Cross-Table
| ID | Task | Type | Est |
|----|------|------|-----|
| 4.2.1 | RowStatus state machine (createAndGo, destroy, active) | Code | 1d |
| 4.2.2 | Cross-table Set — AUGMENTS columns resolved to same row | Code | 0.5d |
| 4.2.3 | OID index rebuild after row create/delete | Code | 0.25d |
| 4.2.4 | Wire Set handler into UDP listener | Code | 0.25d |

**Unit Tests (mocked):**
- [ ] `test_rowstatus_create_and_go` — new row created, status=active, required cols present
- [ ] `test_rowstatus_create_missing_required` — missing Req column → inconsistentValue
- [ ] `test_rowstatus_create_existing` — createAndGo on active row → inconsistentValue
- [ ] `test_rowstatus_destroy` — row deleted, OID index updated
- [ ] `test_rowstatus_destroy_nonexistent` — destroy non-existing row → handled gracefully
- [ ] `test_cross_table_set` — base table + ext table columns in one Set → single row created
- [ ] `test_cross_table_columns_merged` — ext columns visible under base table OID in GetNext
- [ ] `test_oid_index_after_create` — new row's OIDs appear in index
- [ ] `test_oid_index_after_delete` — deleted row's OIDs removed from index

**Integration Tests:**
- [ ] `test_snmpset_scalar` — real snmpset changes a scalar, snmpget returns new value
- [ ] `test_create_target_addr_with_ext` — replay CC's cross-table Set PDU → row created → snmpwalk shows it
- [ ] `test_cc_sync_set_replay` — replay all Set operations from captured CC sync → all succeed
- [ ] `test_destroy_then_recreate` — RowStatus destroy, then createAndGo → clean row

### Sprint 4 Definition of Done
- All unit and integration tests pass
- CC sync Set operations replayed successfully from capture
- Cross-table Set works (the test SAPRO cannot pass)

---

## Phase 5: MIB Compiler Output Refactor

**Goal:** The compiler outputs MongoDB schema documents instead of CMF/VAR files.

### Sprint 5.1 — Schema Generator
| ID | Task | Type | Est |
|----|------|------|-----|
| 5.1.1 | New `schema_generator.py` — takes OidEntry list → mib_schemas document | Code | 1d |
| 5.1.2 | Scalar generation (defaults, overrides, types, constraints) | Code | 0.5d |
| 5.1.3 | Table/column generation (including AUGMENTS linking) | Code | 0.5d |
| 5.1.4 | Index encoding specification per table (IMPLIED vs length-prefixed) | Code | 0.5d |

**Unit Tests (mocked):**
- [ ] `test_scalar_generation` — known scalar → correct schema entry with type, access, default
- [ ] `test_scalar_overrides_applied` — scalar_diff values override MIB defaults
- [ ] `test_table_columns_generated` — all columns present with correct oid_suffix and access
- [ ] `test_augments_linked` — ext table's columns listed under augmented_by in base table
- [ ] `test_index_encoding_implied` — snmpTargetAddrName → implied
- [ ] `test_index_encoding_length_prefixed` — vacmSecurityName → length_prefixed
- [ ] `test_enum_mappings` — RowStatus enums generated correctly
- [ ] `test_supplement_entries_included` — cmf_supplement OIDs present in schema

### Sprint 5.2 — Device Initialization
| ID | Task | Type | Est |
|----|------|------|-----|
| 5.2.1 | Device initializer — schema + template → device_instances document | Code | 0.5d |
| 5.2.2 | SNMP infrastructure init in Python (VACM, community, notify) | Code | 0.5d |
| 5.2.3 | Static instance rows (ports, interfaces) | Code | 0.5d |
| 5.2.4 | API endpoint: compile → schema to MongoDB | Code | 0.5d |

**Unit Tests (mocked):**
- [ ] `test_device_init_scalars_populated` — all scalars from schema have values
- [ ] `test_device_init_vacm_tables` — group, access, view tables populated correctly
- [ ] `test_device_init_community_table` — snmpCommunityTable has "public" entry
- [ ] `test_device_init_notify_table` — snmpNotifyTable has "allTraps" entry
- [ ] `test_device_init_static_ports` — ifTable has Port-1, Port-2, MNG-1
- [ ] `test_device_init_oid_count` — roughly matches SAPRO device OID count

**Integration Tests:**
- [ ] `test_compile_and_create_device` — compile 10.4 MIBs → schema → create device → snmpwalk matches
- [ ] `test_compile_10_6` — same for 10.6

### Sprint 5 Definition of Done
- All unit and integration tests pass
- Compiled schema produces device that matches SAPRO snmpwalk output
- No CMF/VAR files needed

---

## Phase 6: Device Lifecycle & Backend Integration

**Goal:** Create/delete/update devices through the existing UI, backed by the new engine.

### Sprint 6.1 — Engine Client
| ID | Task | Type | Est |
|----|------|------|-----|
| 6.1.1 | `snmp_engine_client.py` — create_device, delete_device, update_device | Code | 0.5d |
| 6.1.2 | Template simplification — remove SAPRO-specific fields | Code | 0.5d |
| 6.1.3 | Route refactoring — backend selects SAPRO or engine per device | Code | 0.5d |

**Unit Tests (mocked):**
- [ ] `test_create_device_writes_mongodb` — mock MongoDB, verify all 3 collections written
- [ ] `test_create_device_snmp_init` — verify VACM/community/notify populated
- [ ] `test_delete_device_cleans_up` — verify all 3 collections cleaned
- [ ] `test_update_device_reinitializes` — verify delete + create sequence
- [ ] `test_template_without_soap` — simplified template creates valid device

### Sprint 6.2 — UI Integration
| ID | Task | Type | Est |
|----|------|------|-----|
| 6.2.1 | Frontend template dialog updates (remove SAPRO fields) | Code | 0.5d |
| 6.2.2 | Device creation flow end-to-end via UI | Code | 0.5d |
| 6.2.3 | Bulk creation streaming endpoint | Code | 0.5d |

**Integration Tests:**
- [ ] `test_create_via_api` — POST /simulators → device created → snmpget works
- [ ] `test_delete_via_api` — DELETE /simulators/{ip} → device gone → snmpget fails
- [ ] `test_bulk_create_10_devices` — streaming creation of 10 devices, all respond to snmpget
- [ ] `test_create_time_under_2s` — single device creation completes in <2 seconds

### Sprint 6 Definition of Done
- All tests pass
- Device CRUD works through UI without SSH
- Creation time <2 seconds

---

## Phase 7: CC Sync Full Validation

**Goal:** Zero-error CC sync against the new engine.

### Tasks
| ID | Task | Type | Est |
|----|------|------|-----|
| 7.1 | Full CC sync test — 10.4 device | Test | 0.5d |
| 7.2 | Full CC sync test — 10.6 device | Test | 0.5d |
| 7.3 | Side-by-side snmpwalk comparison (new engine vs SAPRO) | Test | 0.5d |
| 7.4 | Fix discrepancies | Code | 1-2d |
| 7.5 | Edge case testing (reconnect, multi-CC, rapid CRUD) | Test | 0.5d |
| 7.6 | Performance baseline (latency, memory, throughput) | Test | 0.5d |

**Integration Tests:**
- [ ] `test_cc_discovery_flow` — replay CC discovery SNMP capture → all responses correct
- [ ] `test_cc_sync_flow` — replay full CC sync capture → all Gets and Sets succeed
- [ ] `test_cc_sync_no_warnings` — M_00170, M_00187, M_00162 do not appear
- [ ] `test_snmpwalk_diff_under_threshold` — diff against SAPRO capture < 10 lines difference
- [ ] `test_response_latency_p95` — 95th percentile SNMP response time < 10ms
- [ ] `test_100_devices_memory` — engine with 100 devices uses < 500MB

### Sprint 7 Definition of Done
- CC syncs with zero errors on both 10.4 and 10.6
- Performance baseline documented
- All known CC warnings eliminated

---

## Phase 8: Polling Migration (XMF → Proxy)

### Sprint 8.1
| ID | Task | Type | Est |
|----|------|------|-----|
| 8.1.1 | Analyze XMF polling request/response format | Research | 0.5d |
| 8.1.2 | Implement polling handler in proxy | Code | 1d |
| 8.1.3 | Add port 8790 to proxy listener config | Code | 0.25d |
| 8.1.4 | Migrate polling_service.py | Code | 1d |

**Unit Tests (mocked):**
- [ ] `test_polling_handler_returns_expected_format` — mock data → correct HTTP response
- [ ] `test_polling_reads_from_mongodb` — mock MongoDB → data flows to response

**Integration Tests:**
- [ ] `test_cc_receives_polling_data` — CC's polling request on port 8790 returns valid data

### Sprint 8 Definition of Done
- Polling works through proxy
- No SAPRO XMF dependency

---

## Phase 9: IRP & Trap Migration

### Sprint 9.1 — Traps
| ID | Task | Type | Est |
|----|------|------|-----|
| 9.1.1 | Trap sender — construct v2c trap PDU, send from device IP | Code | 0.5d |
| 9.1.2 | Read trap destinations from device's MongoDB data | Code | 0.25d |
| 9.1.3 | API endpoint to trigger trap | Code | 0.25d |

### Sprint 9.2 — IRP
| ID | Task | Type | Est |
|----|------|------|-----|
| 9.2.1 | Analyze current IRP IP binding mechanism | Research | 0.5d |
| 9.2.2 | Implement IRP sender in engine service | Code | 1d |
| 9.2.3 | API endpoint to trigger IRP send | Code | 0.25d |

**Unit Tests (mocked):**
- [ ] `test_trap_pdu_encoding` — correct BER encoding for v2c trap
- [ ] `test_trap_sent_to_destinations` — mock socket, verify sent to all target addresses
- [ ] `test_irp_binding_device_ip` — mock socket, verify bind to device IP

**Integration Tests:**
- [ ] `test_trap_received_by_collector` — real trap receiver gets our trap
- [ ] `test_irp_received_by_cc` — CC receives IRP data

### Sprint 9 Definition of Done
- Traps and IRP work without SAPRO

---

## Phase 10: Production Deployment & SAPRO Retirement

### Tasks
| ID | Task | Type | Est |
|----|------|------|-----|
| 10.1 | Docker compose updates (add engine, remove SAPRO) | Infra | 0.5d |
| 10.2 | Production .env configuration | Infra | 0.25d |
| 10.3 | Migration script — SAPRO devices → new engine | Code | 1d |
| 10.4 | Remove SAPRO-specific code (sapro_client SSH, sapcnsl, TCL files) | Code | 0.5d |
| 10.5 | Final validation — all devices, all features | Test | 1d |

**Integration Tests:**
- [ ] `test_migration_preserves_device_state` — migrated device's snmpwalk matches pre-migration
- [ ] `test_no_sapro_processes` — verify no SAPRO processes running
- [ ] `test_all_devices_synced` — every device passes CC sync

### Sprint 10 Definition of Done
- SAPRO completely removed
- All production devices on new engine
- All tests green
