"""Generate the SNMP Simulation Engine planning document as a Word file."""

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
import os

doc = Document()

# Styles
style = doc.styles['Normal']
style.font.name = 'Calibri'
style.font.size = Pt(11)

# Title
title = doc.add_heading('SimulatorTools SNMP Engine', level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
subtitle = doc.add_paragraph('High-Level Architecture & Implementation Plan')
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
subtitle.runs[0].font.size = Pt(14)
subtitle.runs[0].font.color.rgb = RGBColor(0x66, 0x66, 0x66)

doc.add_paragraph()
meta = doc.add_table(rows=4, cols=2)
meta.style = 'Light Grid Accent 1'
cells = [
    ('Document Type', 'Technical Planning Document'),
    ('Project', 'SimulatorTools — SAPRO Replacement'),
    ('Date', 'April 2026'),
    ('Status', 'Draft — For Review'),
]
for i, (k, v) in enumerate(cells):
    meta.rows[i].cells[0].text = k
    meta.rows[i].cells[1].text = v

doc.add_page_break()

# ─── TABLE OF CONTENTS ───
doc.add_heading('Table of Contents', level=1)
toc_items = [
    '1. Executive Summary',
    '2. Problem Statement — Why Replace SAPRO',
    '3. What We Already Have',
    '4. Architecture Overview',
    '5. Component Breakdown',
    '   5.1 SNMP Protocol Engine',
    '   5.2 Data Store (MongoDB)',
    '   5.3 OID Resolver & Walker',
    '   5.4 Set Handler & RowStatus State Machine',
    '   5.5 MIB Compiler Output Refactor',
    '   5.6 Device Lifecycle Manager',
    '   5.7 Device Templates Simplification',
    '   5.8 Integration with Existing Systems',
    '6. Additional Modules Requiring Migration',
    '   6.1 Polling (XMF to Proxy)',
    '   6.2 IRP (Binary Reporting)',
    '   6.3 SNMP Traps',
    '7. SNMPv3 — Future Considerations',
    '8. Data Model',
    '9. Resource Consumption Estimates',
    '10. Migration Strategy',
    '11. Implementation Phases',
    '12. Risk Assessment',
    '13. Success Criteria',
]
for item in toc_items:
    doc.add_paragraph(item, style='List Number' if not item.startswith('   ') else 'List Number 2')

doc.add_page_break()

# ─── 1. EXECUTIVE SUMMARY ───
doc.add_heading('1. Executive Summary', level=1)
doc.add_paragraph(
    'This document outlines the plan to replace SAPRO\'s SNMP simulation engine with a '
    'purpose-built service within the SimulatorTools ecosystem. The new engine will handle '
    'all SNMP operations (Get, GetNext, GetBulk, Set) using MongoDB as the data store, '
    'eliminating SAPRO\'s architectural limitations while leveraging the extensive CC '
    'compatibility knowledge already acquired through the MIB compiler project.'
)
doc.add_paragraph(
    'The replacement is not a rewrite-from-scratch — it builds on top of existing components: '
    'the MIB compiler (parsing and schema generation), the sapro-proxy (HTTP/HTTPS handling), '
    'the device template system (device lifecycle), and months of validated CC sync behavior.'
)

# ─── 2. PROBLEM STATEMENT ───
doc.add_heading('2. Problem Statement — Why Replace SAPRO', level=1)

doc.add_heading('SAPRO Limitations Encountered', level=2)
problems = [
    ('Cross-table Set PDUs', 'SAPRO cannot process a single SNMP Set that spans two table OID trees (e.g., snmpTargetAddrTable + snmpTargetAddrExtTable). CC sends these routinely. SAPRO returns noAccess. No TCL workaround exists — %before_snmp_request and %check_set_action do not fire.'),
    ('Binary HTTP corruption', 'SAPRO\'s text buffer (SA_xml_append_plain_text) corrupts binary data — null bytes become UTF-8 c080. Device driver JAR serving was impossible until we built the sapro-proxy.'),
    ('Map-based process model', 'Devices share CMF/VAR files per map. One device crashing or resetting can affect all devices on the same map. Memory and CPU consumption scales poorly.'),
    ('AUGMENTS tables ignored', 'SAPRO\'s row detection doesn\'t handle AUGMENTS table entries. We had to fix the compiler to detect and generate %drow blocks for these.'),
    ('Index encoding assumptions', 'SAPRO stores IMPLIED indexes even when the MIB specifies length-prefixed encoding. Causes data corruption visible to CC.'),
    ('dfixed() buffer corruption', 'NOT-ACCESSIBLE index columns defined with dfixed() return uninitialized memory when queried, corrupting SNMP responses.'),
    ('Documentation inaccuracies', 'SAPRO manual has wrong command names (SA_xml_proxyfwd_stringmap vs strmap), undocumented behavioral limitations, and features that don\'t work as described.'),
    ('Licensing constraints', 'SAPRO licensing limits the number of devices and features available.'),
    ('No programmatic control', 'Device management requires SSH + sapcnsl commands. No API, no events, no integration hooks beyond TCL modeling files.'),
    ('Single SOAP port limitation', 'Only one HTTP and one HTTPS port per device for SOAP/XMF — already bypassed by the proxy.'),
]
for title_text, desc in problems:
    p = doc.add_paragraph()
    run = p.add_run(title_text + ': ')
    run.bold = True
    p.add_run(desc)

# ─── 3. WHAT WE ALREADY HAVE ───
doc.add_heading('3. What We Already Have', level=1)
doc.add_paragraph(
    'The SimulatorTools project has already solved most of the hard problems. '
    'The SNMP engine is the missing piece that ties everything together.'
)

assets = doc.add_table(rows=9, cols=3)
assets.style = 'Light Grid Accent 1'
assets.rows[0].cells[0].text = 'Component'
assets.rows[0].cells[1].text = 'Status'
assets.rows[0].cells[2].text = 'Reuse in New Engine'
data = [
    ('MIB Compiler', 'Working — compiles MIBs to CMF/VAR', 'Change output to MongoDB schema documents'),
    ('Device Templates', 'Working — MongoDB + UI', 'Reuse as-is for device creation'),
    ('sapro-proxy', 'Working — HTTP/HTTPS per device IP', 'Reuse as-is (already SAPRO-independent)'),
    ('CC Sync Knowledge', 'Validated — 10.4 and 10.6 sync working', 'Direct transfer — same OIDs, same behavior'),
    ('VACM/SNMP Infrastructure', 'Working — TCL init populates tables', 'Convert TCL init to Python startup logic'),
    ('Device Driver Serving', 'Working — proxy serves JARs via SNMP lookup', 'Reuse as-is'),
    ('Frontend UI', 'Working — device management, templates, compiler', 'Reuse as-is, minor endpoint refactoring'),
    ('Backend API', 'Working — FastAPI + MongoDB + PostgreSQL', 'Extend with SNMP engine management endpoints'),
]
for i, (comp, status, reuse) in enumerate(data, 1):
    assets.rows[i].cells[0].text = comp
    assets.rows[i].cells[1].text = status
    assets.rows[i].cells[2].text = reuse

# ─── 4. ARCHITECTURE OVERVIEW ───
doc.add_heading('4. Architecture Overview', level=1)
doc.add_paragraph(
    'The new architecture replaces SAPRO with two services: the SNMP Engine (new) and '
    'the existing sapro-proxy (HTTP/HTTPS). Both run with network_mode: host to bind '
    'to simulated device IPs.'
)

doc.add_heading('High-Level Architecture', level=2)
arch_lines = [
    'CC (CyberController)',
    '  │',
    '  ├── SNMP (port 161) ──→ SNMP Engine Service (Python/Docker)',
    '  │                          ├── UDP listener per device IP',
    '  │                          ├── Protocol: pysnmp / custom BER codec',
    '  │                          ├── Data: MongoDB (schema + values)',
    '  │                          └── OID resolver + Set handler',
    '  │',
    '  ├── HTTPS (port 443) ──→ sapro-proxy (existing)',
    '  │                          ├── Device driver JAR serving',
    '  │                          ├── Connectivity checks',
    '  │                          └── Future: polling, REST API simulation',
    '  │',
    '  └── Monitoring (port 8790) ──→ Future: sapro-proxy or SNMP engine',
    '',
    'Backend (FastAPI)',
    '  ├── Device CRUD ──→ MongoDB (templates, device state)',
    '  ├── MIB Compiler ──→ MongoDB (schema output)',
    '  ├── Proxy listener management ──→ MongoDB (proxy_listeners)',
    '  └── SNMP engine management ──→ MongoDB (snmp_devices)',
]
for line in arch_lines:
    p = doc.add_paragraph(line)
    p.style = doc.styles['No Spacing']
    for run in p.runs:
        run.font.name = 'Consolas'
        run.font.size = Pt(9)

# ─── 5. COMPONENT BREAKDOWN ───
doc.add_heading('5. Component Breakdown', level=1)

# 5.1
doc.add_heading('5.1 SNMP Protocol Engine', level=2)
doc.add_paragraph(
    'Receives SNMP v2c UDP packets, decodes them, routes to the correct device by '
    'destination IP (getsockname pattern, same as the proxy), processes the operation '
    'against MongoDB, and sends the response.'
)
p = doc.add_paragraph()
p.add_run('Technology: ').bold = True
p.add_run('Python with pysnmp/pyasn1 for BER encoding/decoding, or a lighter library like snmplib. '
          'The protocol layer is a solved problem — we only build the data backend.')

p = doc.add_paragraph()
p.add_run('Key features:').bold = True
features = [
    'UDP listener per device IP (dynamic, driven by MongoDB — same pattern as proxy)',
    'SNMPv2c community string validation',
    'Request routing by destination IP → device document in MongoDB',
    'Get: direct OID lookup',
    'GetNext: ordered OID walk using MongoDB index',
    'GetBulk: GetNext repeated N times with max-repetitions',
    'Set: validate constraints, apply RowStatus state machine, write values',
    'Error responses: noSuchObject, noSuchInstance, endOfMibView, noAccess, inconsistentValue',
]
for f in features:
    doc.add_paragraph(f, style='List Bullet')

# 5.2
doc.add_heading('5.2 Data Store (MongoDB)', level=2)
doc.add_paragraph(
    'MongoDB replaces both CMF (schema) and VAR (values) files. The schema is shared '
    'across devices of the same firmware version. Values are per-device.'
)
p = doc.add_paragraph()
p.add_run('Collections:').bold = True

collections = [
    ('mib_schemas', 'Shared per firmware version. Contains OID tree structure, column definitions, '
     'table metadata, index specifications, value constraints, access levels. '
     'Generated by the MIB compiler. Replaces CMF.'),
    ('device_instances', 'Per device. Contains all current OID values (scalars + table rows). '
     'Initialized from schema defaults when device is created. Replaces VAR. '
     'Each document: { device_ip, schema_id, scalars: {oid: value}, tables: {table_oid: [rows]} }'),
    ('device_registry', 'Per device. IP, firmware version, schema reference, status, '
     'creation time. Used by the SNMP engine to discover which devices to serve.'),
]
for name, desc in collections:
    p = doc.add_paragraph()
    run = p.add_run(name + ': ')
    run.bold = True
    run.font.name = 'Consolas'
    p.add_run(desc)

# 5.3
doc.add_heading('5.3 OID Resolver & Walker', level=2)
doc.add_paragraph(
    'The core lookup engine. Given an OID and operation type, it finds the correct value '
    'from the device\'s data document.'
)
ops = [
    ('Get', 'Direct lookup by exact OID in the device document. O(1) with MongoDB index on OID.'),
    ('GetNext', 'Find the lexicographically next OID. Requires an ordered index on OID paths. '
     'MongoDB can use a sorted index on the OID string field (dotted notation sorts correctly '
     'if zero-padded, or stored as an array of integers).'),
    ('GetBulk', 'Repeated GetNext. The non-repeaters are processed as Get, then max-repetitions '
     'rounds of GetNext for the remaining varbinds.'),
    ('endOfMibView', 'When GetNext walks past the last OID in the device\'s tree, return endOfMibView.'),
]
for op, desc in ops:
    p = doc.add_paragraph()
    run = p.add_run(op + ': ')
    run.bold = True
    p.add_run(desc)

doc.add_paragraph()
p = doc.add_paragraph()
p.add_run('OID storage strategy: ').bold = True
p.add_run(
    'Store each OID as a string in dotted notation (e.g., "1.3.6.1.2.1.1.1.0"). '
    'For GetNext performance, maintain a sorted array of all active OIDs per device. '
    'This array is rebuilt when rows are created/deleted and cached in memory. '
    'GetNext becomes a binary search on the sorted array — O(log n) per varbind.'
)

# 5.4
doc.add_heading('5.4 Set Handler & RowStatus State Machine', level=2)
doc.add_paragraph(
    'The Set handler validates and applies SNMP Set operations. This is where we '
    'solve SAPRO\'s cross-table limitation — our engine sees ALL varbinds as one '
    'operation against a unified data store, regardless of which MIB table they belong to.'
)

doc.add_paragraph('Set processing flow:', style='List Bullet')
steps = [
    'Parse all varbinds from the Set PDU',
    'For each varbind: validate OID exists, check access (RW/RC), check value constraints',
    'For RowStatus columns: apply state machine (createAndGo → active, destroy → delete row)',
    'If any varbind fails validation: return error, change nothing (atomic)',
    'If all pass: write all values to MongoDB in one operation',
    'Return success response with all varbinds',
]
for s in steps:
    doc.add_paragraph(s, style='List Bullet 2')

doc.add_paragraph()
p = doc.add_paragraph()
p.add_run('RowStatus state machine: ').bold = True
p.add_run(
    'Implement RFC 2579 RowStatus transitions: createAndGo(4) → active(1), '
    'createAndWait(5) → notInService(2), destroy(6) → row deleted. '
    'This is implemented ONCE in the engine, correctly, for all tables. '
    'No more per-table TCL workarounds.'
)

# 5.5
doc.add_heading('5.5 MIB Compiler Output Refactor', level=2)
doc.add_paragraph(
    'The existing MIB compiler parses MIB files and generates CMF + VAR files. '
    'The refactor changes the output format to MongoDB documents while keeping '
    'all the parsing, detection, and CC compatibility logic intact.'
)

changes = [
    ('CMF → mib_schemas collection', 'OID tree structure, column definitions, table metadata, '
     'index specifications, value types, constraints, enum mappings. JSON instead of flat text.'),
    ('VAR → device initialization template', 'Default scalar values, static instance rows, '
     'dynamic table configurations. Used as a template when creating new devices.'),
    ('cmf_supplement.txt → schema_supplement.json', 'Same data, JSON format. '
     'OIDs that can\'t be parsed from MIBs.'),
    ('scalar_diff.json → unchanged', 'Already JSON. Directly usable.'),
    ('TCL init_action → Python startup script', 'SNMP infrastructure population (VACM, '
     'target tables, community, notify) becomes Python code that writes directly to MongoDB. '
     'No more TCL, no more dos2unix, no more SAPRO upload.'),
]
for title_text, desc in changes:
    p = doc.add_paragraph()
    run = p.add_run(title_text + ': ')
    run.bold = True
    p.add_run(desc)

# 5.6
doc.add_heading('5.6 Device Lifecycle Manager', level=2)
doc.add_paragraph(
    'Replaces SAPRO\'s map-based device management (adddev, deldev, startdev, stopdev) '
    'with direct MongoDB operations.'
)

lifecycle = [
    ('Create device', '1) Load schema for firmware version from mib_schemas. '
     '2) Initialize device_instances document with default values from schema. '
     '3) Apply scalar overrides (scalar_diff, configuration, licenses). '
     '4) Run startup logic (VACM, SNMP infrastructure, geo feed). '
     '5) Register in device_registry. '
     '6) SNMP engine picks up new device on next poll cycle and starts UDP listener.'),
    ('Delete device', '1) Remove from device_registry. '
     '2) SNMP engine stops UDP listener. '
     '3) Optionally archive or delete device_instances document.'),
    ('Update device', '1) Stop listener. 2) Re-initialize from new schema/template. 3) Restart listener.'),
    ('No maps', 'Each device is independent. No shared state, no shared processes. '
     'One device crashing cannot affect another.'),
]
for title_text, desc in lifecycle:
    p = doc.add_paragraph()
    run = p.add_run(title_text + ': ')
    run.bold = True
    p.add_run(desc)

# 5.7
doc.add_heading('5.7 Device Templates Simplification', level=2)
doc.add_paragraph(
    'Current device templates contain many SAPRO-specific fields that become unnecessary '
    'with the new engine: map file paths, CMF/VAR file references, SAPRO TCL modeling file '
    'paths, SOAP/XMF configuration, SSH settings for sapcnsl commands, etc.'
)
doc.add_paragraph(
    'With the new engine, templates simplify to:'
)
template_fields = [
    'Firmware version (determines which mib_schema to use)',
    'SNMP community strings (read/write)',
    'SNMP port (default 161)',
    'Device type and platform identifier',
    'Network configuration (subnet mask, interface)',
    'Optional: custom scalar overrides per template',
]
for f in template_fields:
    doc.add_paragraph(f, style='List Bullet')
doc.add_paragraph(
    'The entire <Soap>, <SSH>, and most <General> fields (ModelingFile, CommonDataFile, etc.) '
    'become irrelevant. The template system UI should be refactored to reflect this simpler model, '
    'removing fields that no longer serve a purpose.'
)

# 5.8
doc.add_heading('5.8 Integration with Existing Systems', level=2)

integrations = [
    ('sapro-proxy', 'Unchanged. Continues to handle HTTP/HTTPS. '
     'The proxy\'s MongoDB polling (proxy_listeners) works independently. '
     'Both services read from the same device_registry to know which IPs to serve.'),
    ('Backend API', 'Device CRUD endpoints refactored to write to MongoDB instead of '
     'calling SAPRO via SSH. Template system unchanged. Compiler endpoint outputs to MongoDB.'),
    ('Frontend', 'Minimal changes. Device creation/deletion calls the same API endpoints. '
     'The UI doesn\'t know or care whether SAPRO or our engine handles SNMP.'),
    ('Docker deployment', 'New snmp-engine Docker service alongside sapro-proxy, backend, frontend. '
     'network_mode: host for direct IP binding. MongoDB shared between all services.'),
]
for title_text, desc in integrations:
    p = doc.add_paragraph()
    run = p.add_run(title_text + ': ')
    run.bold = True
    p.add_run(desc)

# ─── 6. ADDITIONAL MODULES ───
doc.add_heading('6. Additional Modules Requiring Migration', level=1)
doc.add_paragraph(
    'Beyond SNMP, several existing features currently depend on SAPRO and will need '
    'migration or reimplementation as part of the full SAPRO retirement.'
)

doc.add_heading('6.1 Polling (XMF to Proxy)', level=2)
doc.add_paragraph(
    'Polling currently uses SAPRO\'s XMF/TCL mechanism on port 8790 to generate and serve '
    'reporting data to CC. This needs to be migrated to the sapro-proxy service, which already '
    'handles HTTP/HTTPS traffic. The proxy approach is significantly better — direct JSON/HTTP '
    'handling in Python instead of the cumbersome TCL-based XMF generation. The polling service, '
    'XMF generator, and TCL templates would be replaced with Python HTTP handlers in the proxy '
    'that serve the same data structures CC expects, reading from MongoDB instead of generating '
    'TCL scripts.'
)

doc.add_heading('6.2 IRP (Binary Reporting)', level=2)
doc.add_paragraph(
    'IRP (Intrusion Report Protocol) currently sends binary attack reports from simulated '
    'devices to CC. The simulator binds to the device\'s IP address and sends UDP/TCP packets '
    'containing IRP-formatted binary data. With SAPRO removed, we need to understand how the '
    'IP binding for IRP sending works and replicate it. The backend currently handles IRP '
    'generation — the question is whether the new SNMP engine service or a dedicated IRP '
    'sender service should handle the network binding to device IPs for outbound traffic. '
    'Since the SNMP engine already binds to device IPs for inbound UDP, it may be natural '
    'to add outbound IRP sending capability to the same service.'
)

doc.add_heading('6.3 SNMP Traps', level=2)
doc.add_paragraph(
    'SNMP Traps are outbound notifications sent from the simulated device to CC (typically '
    'on port 162). With the new SNMP engine owning the device\'s UDP socket on port 161, '
    'sending traps becomes straightforward — the engine already has the device context, '
    'community strings, and target address configuration (from the snmpTargetAddrTable). '
    'Trap sending is essentially the reverse of the SNMP engine: construct a trap PDU with '
    'the appropriate varbinds, BER-encode it, and send from the device\'s IP to the configured '
    'trap destinations. This is likely much simpler and more reliable than SAPRO\'s trap '
    'mechanism (SA_sendtrap), and can be triggered by the backend via an API call to the engine.'
)

# ─── 7. SNMPv3 ───
doc.add_heading('7. SNMPv3 — Future Considerations', level=1)
doc.add_paragraph(
    'SNMPv3 with USM (User-based Security Model) is NOT required for initial implementation — '
    'CC uses SNMPv2c for all operations. However, the architecture should not preclude adding '
    'v3 support in the future.'
)
doc.add_paragraph('Preparations for future SNMPv3 support:')
v3_items = [
    'Abstract the community string validation into an authentication layer that can be extended',
    'Design the request handler to accept a "security context" parameter (v2c: community string, v3: user/auth/priv)',
    'Store USM user table data in MongoDB (already populated by VACM init) so v3 auth can look it up',
    'Keep the pysnmp/pyasn1 dependency which has full v3 support if needed later',
    'Engine ID generation and management — store per device in device_registry',
]
for item in v3_items:
    doc.add_paragraph(item, style='List Bullet')

# ─── 8. DATA MODEL ───
doc.add_heading('8. Data Model', level=1)

doc.add_heading('mib_schemas document', level=2)
schema_example = '''{
  "_id": ObjectId,
  "firmware_version": "10.4.0.0",
  "device_type": "DefensePro",
  "created_from_mibs": ["RADWARE-MIB", "SNMP-FRAMEWORK-MIB", ...],

  "oid_tree": {
    "1.3.6.1.2.1.1.1": {
      "label": "sysDescr",
      "syntax": "OctetString",
      "access": "RO",
      "max_length": 255,
      "default_value": "Virtual DefensePro X"
    },
    ...
  },

  "tables": {
    "snmpTargetAddrTable": {
      "entry_oid": "1.3.6.1.6.3.12.1.2.1",
      "row_type": "rowstatus",
      "rowstatus_column": "snmpTargetAddrRowStatus",
      "index_columns": ["snmpTargetAddrName"],
      "index_encoding": "implied",
      "columns": {
        "snmpTargetAddrName": { "oid_suffix": 1, "syntax": "OctetString", "access": "NA" },
        "snmpTargetAddrTDomain": { "oid_suffix": 2, "syntax": "ObjectID", "access": "RC" },
        ...
      },
      "augmented_by": ["snmpTargetAddrExtTable"]
    },
    "snmpTargetAddrExtTable": {
      "entry_oid": "1.3.6.1.6.3.18.1.2.1",
      "augments": "snmpTargetAddrTable",
      "columns": { ... }
    }
  }
}'''
p = doc.add_paragraph(schema_example)
p.style = doc.styles['No Spacing']
for run in p.runs:
    run.font.name = 'Consolas'
    run.font.size = Pt(8)

doc.add_heading('device_instances document', level=2)
instance_example = '''{
  "_id": ObjectId,
  "device_ip": "50.50.83.2",
  "schema_id": ObjectId("..."),  // reference to mib_schemas
  "firmware_version": "10.4.0.0",

  "scalars": {
    "1.3.6.1.2.1.1.1.0": { "type": "OctetString", "value": "Virtual DefensePro X" },
    "1.3.6.1.2.1.1.2.0": { "type": "ObjectID", "value": "1.3.6.1.4.1.89.1.1.62.16" },
    "1.3.6.1.2.1.1.3.0": { "type": "TimeTicks", "value": "dynamic:uptime" },
    ...
  },

  "table_rows": {
    "1.3.6.1.6.3.12.1.2.1": [
      {
        "index": "118.51.77.110.103.83.116.97.116.105.111.110.115",
        "columns": {
          "1": "v3MngStations",
          "2": "1.3.6.1.6.1.1",
          "6": "v3Traps",
          "7": "radware-authPriv",
          "9": 1
        }
      }
    ]
  },

  "oid_index": ["1.3.6.1.2.1.1.1.0", "1.3.6.1.2.1.1.2.0", ...]  // sorted for GetNext
}'''
p = doc.add_paragraph(instance_example)
p.style = doc.styles['No Spacing']
for run in p.runs:
    run.font.name = 'Consolas'
    run.font.size = Pt(8)

# ─── 9. RESOURCE CONSUMPTION ESTIMATES ───
doc.add_heading('9. Resource Consumption Estimates', level=1)
doc.add_paragraph(
    'Rough estimates for the SNMP engine service running simulated devices. '
    'These are baseline estimates — actual values depend on CC polling frequency '
    'and the number of concurrent operations.'
)

resources = doc.add_table(rows=5, cols=4)
resources.style = 'Light Grid Accent 1'
res_headers = ['Resource', '10 devices', '100 devices', '500 devices']
for i, h in enumerate(res_headers):
    resources.rows[0].cells[i].text = h
res_data = [
    ('Memory (engine process)', '~50 MB', '~200 MB', '~800 MB'),
    ('Memory (MongoDB, device data)', '~20 MB', '~200 MB', '~1 GB'),
    ('CPU (idle, periodic polling)', '<1%', '~2-5%', '~10-15%'),
    ('CPU (during CC sync burst)', '~5%', '~15-25%', '~40-60%'),
]
for i, (res, d10, d100, d500) in enumerate(res_data, 1):
    resources.rows[i].cells[0].text = res
    resources.rows[i].cells[1].text = d10
    resources.rows[i].cells[2].text = d100
    resources.rows[i].cells[3].text = d500

doc.add_paragraph()
doc.add_paragraph('Key factors affecting resource usage:')
res_factors = [
    'Each device holds ~3,000-5,000 OIDs in memory for fast GetNext walking',
    'MongoDB stores all device data persistently — engine can restart without data loss',
    'UDP sockets are lightweight — one per device IP per port (typically just port 161)',
    'Network: SNMP packets are small (typically <1500 bytes). Even 500 devices under '
    'active CC polling generate minimal network traffic (<10 Mbps)',
    'Comparison: SAPRO uses ~50-100 MB per map process, with shared state causing '
    'cascading failures. The new engine isolates devices in MongoDB documents — '
    'one device failing cannot affect others',
]
for f in res_factors:
    doc.add_paragraph(f, style='List Bullet')

# ─── 10. MIGRATION STRATEGY ───
doc.add_heading('10. Migration Strategy', level=1)
doc.add_paragraph(
    'The migration is incremental — SAPRO and the new engine can coexist during transition. '
    'Devices can be individually moved from SAPRO to the new engine.'
)

phases_mig = [
    ('Phase 1: Parallel operation', 'New engine runs alongside SAPRO. New devices created through '
     'the compiler use the new engine. Existing SAPRO devices remain on SAPRO.'),
    ('Phase 2: Feature parity', 'All CC sync operations validated on the new engine. '
     'Template system updated to target new engine by default.'),
    ('Phase 3: SAPRO retirement', 'All devices migrated. SAPRO services removed from docker-compose. '
     'SSH dependency eliminated.'),
]
for title_text, desc in phases_mig:
    p = doc.add_paragraph()
    run = p.add_run(title_text + ': ')
    run.bold = True
    p.add_run(desc)

# ─── 11. IMPLEMENTATION PHASES ───
doc.add_heading('11. Implementation Phases', level=1)

doc.add_heading('Phase 1: Core SNMP Engine (Estimated: 3-5 days)', level=2)
phase1 = [
    'Python Docker service with UDP socket per device IP',
    'BER/ASN.1 encoding/decoding via pysnmp or snmplib',
    'MongoDB connection and device document lookup',
    'Get operation: exact OID lookup',
    'GetNext operation: sorted OID walking',
    'GetBulk operation: repeated GetNext with max-repetitions',
    'SNMPv2c community string validation',
    'Basic error responses (noSuchObject, noSuchInstance, endOfMibView)',
    'Health check endpoint',
    'Test: snmpget/snmpwalk against a manually created device document',
]
for item in phase1:
    doc.add_paragraph(item, style='List Bullet')

doc.add_heading('Phase 2: Set Operations & RowStatus (Estimated: 2-3 days)', level=2)
phase2 = [
    'Set operation: validate access, constraints, write values',
    'RowStatus state machine (createAndGo, createAndWait, destroy)',
    'Cross-table Set support (naturally handled — unified data store, no table boundaries)',
    'AUGMENTS table transparent handling',
    'Atomic Set semantics (all-or-nothing)',
    'Test: CC sync Set operations against the engine',
]
for item in phase2:
    doc.add_paragraph(item, style='List Bullet')

doc.add_heading('Phase 3: MIB Compiler Refactor (Estimated: 2-3 days)', level=2)
phase3 = [
    'New output format: MongoDB schema documents',
    'Convert CMF generation to mib_schemas collection output',
    'Convert VAR generation to device initialization template',
    'Convert cmf_supplement to JSON schema supplement',
    'Convert TCL init_action to Python device startup script',
    'Scalar overrides, licenses, version templates — already JSON, minimal change',
    'Test: compile 10.4 MIBs, verify schema document matches current CMF/VAR behavior',
]
for item in phase3:
    doc.add_paragraph(item, style='List Bullet')

doc.add_heading('Phase 4: Device Lifecycle Integration (Estimated: 2-3 days)', level=2)
phase4 = [
    'Backend API refactor: device CRUD writes to MongoDB instead of SSH to SAPRO',
    'Device creation: initialize from schema + template + overrides',
    'SNMP infrastructure startup (VACM, targets, community, notify) in Python',
    'Dynamic listener management (same MongoDB polling pattern as proxy)',
    'Integration with existing template system',
    'Test: create device via UI, verify CC can discover and sync',
]
for item in phase4:
    doc.add_paragraph(item, style='List Bullet')

doc.add_heading('Phase 5: CC Sync Validation (Estimated: 2-3 days)', level=2)
phase5 = [
    'Full CC discovery + sync test against new engine',
    'Compare SNMP responses with SAPRO-based device (diff snmpwalk output)',
    'Fix any discrepancies in OID ordering, value formatting, error codes',
    'Validate all resolved CC sync issues (M_00170, M_00187, M_00162, etc.)',
    'Test: multiple device versions (10.4, 10.6)',
    'Test: bulk device creation (10+ devices)',
]
for item in phase5:
    doc.add_paragraph(item, style='List Bullet')

doc.add_heading('Phase 6: Production Deployment & SAPRO Retirement (Estimated: 1-2 days)', level=2)
phase6 = [
    'Docker service added to docker-compose',
    'Production .env configuration',
    'Migrate existing devices from SAPRO to new engine',
    'Remove SAPRO services from docker-compose',
    'Remove SSH dependency for device management',
    'Documentation update',
]
for item in phase6:
    doc.add_paragraph(item, style='List Bullet')

doc.add_paragraph()
p = doc.add_paragraph()
p.add_run('Total estimated effort: 12-19 days').bold = True
p.add_run(
    ' — with AI-assisted development (our established working pattern), '
    'this is realistic for a working, CC-validated replacement. '
    'The bulk of the intellectual work (understanding CC behavior, MIB parsing, '
    'SNMP infrastructure requirements) is already done.'
)

# ─── 12. RISK ASSESSMENT ───
doc.add_heading('12. Risk Assessment', level=1)

risks = doc.add_table(rows=6, cols=4)
risks.style = 'Light Grid Accent 1'
headers = ['Risk', 'Likelihood', 'Impact', 'Mitigation']
for i, h in enumerate(headers):
    risks.rows[0].cells[i].text = h

risk_data = [
    ('GetNext performance at scale', 'Medium', 'Medium',
     'Sorted OID index in memory. MongoDB index on OID. Benchmark early.'),
    ('Unknown CC behavior in edge cases', 'Low', 'Medium',
     'Extensive CC knowledge already captured. SNMP captures available for comparison.'),
    ('pysnmp library limitations', 'Low', 'Low',
     'Multiple SNMP libraries available. BER encoding is standardized.'),
    ('SNMPv3 support needed', 'Low', 'High',
     'CC uses v2c for all operations. v3 can be added later if needed.'),
    ('Concurrent Set operations', 'Medium', 'Medium',
     'MongoDB atomic operations. Per-device locking if needed.'),
]
for i, (risk, like, impact, mit) in enumerate(risk_data, 1):
    risks.rows[i].cells[0].text = risk
    risks.rows[i].cells[1].text = like
    risks.rows[i].cells[2].text = impact
    risks.rows[i].cells[3].text = mit

# ─── 13. SUCCESS CRITERIA ───
doc.add_heading('13. Success Criteria', level=1)

criteria = [
    'CC can discover a device on the new engine (sysObjectID, version, platform)',
    'CC can download device driver via proxy (already working)',
    'CC can complete full device sync with zero errors',
    'snmpwalk output matches SAPRO-based device for the same firmware version',
    'Device creation/deletion takes under 2 seconds (vs current 30-60s with SAPRO SSH)',
    '100+ devices can run simultaneously without memory/CPU issues',
    'No SAPRO process required — all SNMP handled by the new engine',
    'All existing UI functionality works without changes',
]
for c in criteria:
    doc.add_paragraph(c, style='List Bullet')

# Save
output_path = os.path.join(os.path.dirname(__file__), 'SNMP_Engine_Plan.docx')
doc.save(output_path)
print(f'Document saved to: {output_path}')
