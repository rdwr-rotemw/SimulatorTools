# DefensePro Modeling File Generation — Implementation Plan

**Date:** 2026-03-30
**Status:** Planning phase
**Depends on:** MIB Compiler (feature/mib-compiler branch, completed)

## Problem Statement

The MIB compiler generates `.cmf` and `.var` files that allow SAPRO to start a simulated DefensePro device. The simulator responds to SNMP Get requests correctly. However, **SNMP Set requests for table row creation fail** because:

1. The real DefensePro firmware has internal logic that auto-computes certain columns when other columns are set (e.g., setting a network address auto-computes `FromIP` and `ToIP`)
2. CyberController sends Set requests with only a subset of columns, expecting the device firmware to fill in the rest
3. SAPRO's `%drow`/`%dcol` blocks handle row creation but don't simulate the firmware's auto-computation logic

SAPRO solves this with **modeling files** (`.tcl` scripts) that contain TCL code triggered by SNMP events. These scripts simulate the firmware behavior.

## What Was Already Done

### MIB Compiler (Completed)
- Generates `.cmf` with OID entries, `%en` entry names, `%ei` index declarations, `%ev` enum values
- Generates `.var` with dynamic row blocks (`%drow`/`%dcol`), scalar variables with proper defaults
- Device driver integration for `rndVisionDriverActiveName`
- Version-dependent scalars (`rndBrgVersion`, `rsIDSVersion`, etc.)
- SAPRO tokens (`$$MYIPADDRESS$$`, `$$MYMAINMACADDR$$`)
- Files uploaded to SAPRO via SCP

### Working Example — `rsBWMNetworkTable`
A hand-written TCL modeling file exists at `backend/app/modules/sapro/oid_compiler/test_snmp.tcl` that solves the `rsBWMNetworkTable` row creation problem:

- **Trigger:** `%after_set_action 1.3.6.1.4.1.89.35.1.60.63.1.3` (when Address column is set)
- **Logic:** Copies Address to `FromIP`, reads Mask, computes broadcast address as `ToIP`
- **Uses:** `SA_getreqvb`, `SA_setvar`, `SA_getvar` SAPRO TCL commands

### Key Discovery: `soap_metadata.c`
The file `backend/dp_debug/DefensePro_v10-12-0-1_SOAP_API/wsdl.tar/wsdl/soap_metadata.c` contains the DefensePro firmware's SOAP-to-SNMP mapping. It reveals:

- **Which columns are visible** to the management API (CC)
- **Which columns are "hidden"** — these are firmware-computed columns not exposed via SOAP
- **Key (index) columns** for each table
- **SOAP class names** mapping to MIB table entries

This is the Rosetta Stone for understanding which columns need modeling.

## Data Sources Available

### 1. `soap_metadata.c` (Primary — for DP module tables)
**Location:** `backend/dp_debug/DefensePro_v10-12-0-1_SOAP_API/wsdl.tar/wsdl/soap_metadata.c`

Contains C code with:
```c
UINT_8 *soap_rsBWMNetworkEntry_attrList[] = {
    "Name", "Index", "Address", "Mask",
    "hidden", "hidden", "hidden", "hidden", NULL
};
UINT_8 *soap_rsBWMNetworkEntry_keyAttrList[] = {
    "Name", "Index", NULL
};
```

**What it tells us:**
- `attrList` — ordered list of all columns. `"hidden"` entries are firmware-computed.
- `keyAttrList` — which columns form the table's index/key
- Operation mappings show SOAP class → MIB table relationships

**Statistics (DP module only):**
- 29 tables with attribute lists
- 11 tables with key lists
- 18 tables with at least 1 hidden column

**Tables with hidden columns (firmware-computed):**

| Table | Total Cols | Hidden | Visible | Notes |
|-------|-----------|--------|---------|-------|
| `rsBWMNetworkEntry` | 8 | 4 | 4 | FromIP, ToIP, Mode, Status hidden |
| `rsBWMFilterEntry` | 26 | 6 | 20 | Various filter params hidden |
| `rsBWMRulesEntry` | 27 | 12 | 15 | Policy rule params hidden |
| `rsBWMExtRulesEntry` | 16 | 3 | 13 | Extended rule params hidden |
| `rsBWMCurrentRulesEntry` | 25 | 11 | 14 | Current rules (read-only mirror) |
| `rsBWMCurrentNetworkEntry` | 7 | 3 | 4 | Current networks (read-only mirror) |
| `rsBWMACLModifyPolicyEntry` | 17 | 17 | 0 | Entirely hidden (internal) |
| `rsBWMACLActualPolicyEntry` | 16 | 16 | 0 | Entirely hidden (internal) |
| `rsBWMVLANTagGroupEntry` | 6 | 1 | 5 | Status hidden |
| `rsBWMBwmPortOperationEntry` | 4 | 1 | 3 | Status hidden |
| `rsBWMPhysicalPortGroupEntry` | 3 | 1 | 2 | Status hidden |
| `rsBWMAppPortGroupEntry` | 5 | 1 | 4 | Status hidden |
| `rsSSLCertificateEntry` | 19 | 1 | 18 | One param hidden |
| `rsWSDSNMPPortsEntry` | 6 | 1 | 5 | One param hidden |
| `rsBWMStatisticsEntry` | 34 | 2 | 32 | Two stats hidden |
| `usmUserEntry` | 13 | 8 | 5 | SNMPv3 user table, many hidden |
| `rndModulesInfoEntry` | 7 | 1 | 6 | Hardware info |
| `rsBWMCurrentExtRulesEntry` | 15 | 2 | 13 | Current ext rules mirror |

### 2. IDS WSDL Files (For security module tables)
**Location:** `backend/dp_debug/DefensePro_v10-12-0-1_SOAP_API/ids_wsdl/wsdl/`

60+ WSDL files for security features (policies, BDoS, DNS, signatures, etc.). These are XML and contain:
- `complexType` definitions with element names and types
- `minOccurs="0"` vs `minOccurs="1"` — indicating optional vs required fields
- Key definitions for table lookups
- Operation definitions (create, delete, get, getAll, getNext, update)

These WSDLs define the CC→DP API for all security tables. The element names map to SNMP column names (with naming convention translation).

**Key security WSDL files:**
- `Security.Policy.wsdl` — Attack policies (the most important one for CC)
- `Security.BehavioralDoS.wsdl` — BDoS profiles
- `Security.DnsProtection.wsdl` — DNS protection
- `Security.SignatureProtection.wsdl` — Signature protection
- `Security.ConnectionLimit.wsdl` — Connection limit profiles
- `Security.OutOfState.wsdl` — Out-of-state protection
- `Security.SynProtection.wsdl` — SYN flood protection
- `Security.AccessLists.wsdl` — Access lists
- `Security.TrafficFilter.wsdl` — Traffic filters (New Traffic filters)

### 3. DP WSDL Files (For device/networking tables)
**Location:** `backend/dp_debug/DefensePro_v10-12-0-1_SOAP_API/dp_wsdl/wsdl/`

33 WSDL files for device management, networking, management access.

### 4. DefensePro User Guide
**Location:** `backend/dp_debug/DefensePro_v10-12-0-1_User_Guide.pdf`

541 pages. Contains configuration procedures that describe what happens when you configure features. Useful for understanding firmware behavior but not machine-parseable.

### 5. Real DefensePro + CyberController
Available in dev environment. Can be used for:
- Capturing SNMP traffic (tcpdump) to see exact Set/Get sequences
- Verifying modeling file behavior matches real device

### 6. SAPRO Guide
**Location:** `backend/app/modules/sapro/oid_compiler/sapro290.pdf`

1091 pages. Contains:
- Modeling file TCL command reference (Chapter 6, pages 111-126)
- `%after_set_action`, `%init_action`, `%timer_action` documentation
- TCL commands: `SA_getreqvb`, `SA_setvar`, `SA_getvar`, `SA_getmyip`, `SA_puts`, etc.
- Dynamic row creation details and examples

## SAPRO Modeling File Reference

### File Structure
A modeling file is a TCL script associated with a SAPRO device. It contains action blocks:

```tcl
%init_action
    # Runs when device starts
    set myIP [SA_getmyip]

%after_set_action <oid_prefix>
    # Runs after an SNMP Set on any OID matching the prefix
    set varbind [SA_getreqvb]
    # ... process and auto-set related columns

%after_all_set_action <column_label>
    # Runs after any Set that includes the named column
    set vblist [SA_getreqvars]

%getvalue_action <column_label>
    # Runs when a Get is done on the named column
    # Can override the returned value dynamically

%timer_action <seconds>
    # Runs periodically every N seconds
```

### Key TCL Commands
| Command | Description |
|---------|-------------|
| `SA_getreqvb` | Get the varbind from the current Set request |
| `SA_getreqvars` | Get all varbinds from the current Set request |
| `SA_setvar {{oid type value} ...}` | Set one or more variables |
| `SA_getvar {oid ...}` | Get current values of variables |
| `SA_getmyip` | Get this device's IP address |
| `SA_puts "msg"` | Debug output |
| `SA_setcurvalue value` | Set return value for getvalue_action |
| `SA_settcldebugflag 1` | Enable TCL debug logging |
| `SA_settcldebugfile filename` | Set debug log file |

### Modeling File Association
In SAPRO, the modeling file is associated with a device in the map file. The map entry includes:
```
<ip> <cmf_file> <var_file> <modeling_file> ...
```

## Implementation Plan

### Phase 1: Parse and Map — `soap_metadata.c` Analysis
**Goal:** Extract the complete mapping of SOAP attributes → SNMP columns for all tables, identifying hidden (firmware-computed) columns.

**Steps:**
1. Parse `soap_metadata.c` to extract:
   - All `*_attrList[]` → ordered column attributes (visible + hidden)
   - All `*_keyAttrList[]` → index/key columns
   - Operation mappings → SOAP class to MIB entry name

2. Map SOAP attribute names to SNMP column names:
   - SOAP uses short names like `"Address"`, SNMP uses full names like `rsBWMNetworkAddress`
   - The mapping follows a pattern: `<tablePrefix><AttributeName>` → e.g., `rsBWMNetwork` + `Address` = `rsBWMNetworkAddress`
   - Column positions in `attrList` correspond to column positions in the MIB (C1, C2, ...)

3. For each table, produce a structured record:
   ```json
   {
     "entry_name": "rsBWMNetworkEntry",
     "entry_oid": "1.3.6.1.4.1.89.35.1.60.63.1",
     "soap_class": "radware.Classes.Networks",
     "keys": ["rsBWMNetworkName", "rsBWMNetworkSubIndex"],
     "columns": [
       {"pos": 1, "snmp_name": "rsBWMNetworkName", "soap_name": "Name", "hidden": false, "is_key": true},
       {"pos": 2, "snmp_name": "rsBWMNetworkSubIndex", "soap_name": "Index", "hidden": false, "is_key": true},
       {"pos": 3, "snmp_name": "rsBWMNetworkAddress", "soap_name": "Address", "hidden": false},
       {"pos": 4, "snmp_name": "rsBWMNetworkMask", "soap_name": "Mask", "hidden": false},
       {"pos": 5, "snmp_name": "rsBWMNetworkFromIP", "soap_name": null, "hidden": true},
       {"pos": 6, "snmp_name": "rsBWMNetworkToIP", "soap_name": null, "hidden": true},
       {"pos": 7, "snmp_name": "rsBWMNetworkMode", "soap_name": null, "hidden": true},
       {"pos": 8, "snmp_name": "rsBWMNetworkStatus", "soap_name": null, "hidden": true}
     ]
   }
   ```

### Phase 2: Parse IDS WSDLs
**Goal:** Extract the same information for security module tables from WSDL XML files.

**Steps:**
1. Parse each WSDL file to extract:
   - `complexType` definitions → table structure (column names, types)
   - Key definitions → index columns
   - `minOccurs` attributes → required vs optional

2. Map WSDL element names to SNMP column names using the same prefix pattern

3. Identify "hidden" columns by comparing WSDL elements against CMF columns — any CMF column not in the WSDL is firmware-computed

### Phase 3: Capture Real Device Behavior
**Goal:** For tables with hidden columns, understand what values the firmware computes.

**Approach:**
1. Write a script that connects to the real CC and real DP
2. For each table identified in Phase 1/2 as having hidden columns:
   - Use CC's SOAP API to create a row with minimal data
   - Capture the SNMP traffic (tcpdump) to see what CC sends
   - After row creation, SNMP Get all columns to see what firmware computed
   - Record the mapping: input columns → computed columns
3. Delete the created row to clean up

**Alternative approach (simpler):**
1. Configure the real DP fully via CC (create policies, networks, etc.)
2. Do a full SNMP walk of the real DP to capture all current values
3. Compare against the CMF to identify which columns have computed values
4. Analyze patterns in the computed values

### Phase 4: Generate Modeling TCL Scripts
**Goal:** Auto-generate TCL modeling files that replicate firmware behavior.

**Categories of hidden column behavior:**

1. **RowStatus column** — Always hidden, always the last column. SAPRO handles this via `rowstatus(1)` in `%dcol`. No TCL needed.

2. **Copy/Mirror** — Hidden column gets same value as a visible column. Example: `FromIP` = copy of `Address`.
   ```tcl
   %after_set_action <address_oid_prefix>
       set vb [SA_getreqvb]
       set from_ip_oid [transform_oid $vb "<from_ip_oid_prefix>"]
       SA_setvar [list $from_ip_oid]
   ```

3. **Computed** — Hidden column computed from visible columns. Example: `ToIP` = broadcast(Address, Mask).
   ```tcl
   # After Address is set, compute ToIP from Address + Mask
   set mask [SA_getvar [list $mask_oid]]
   set to_ip [compute_broadcast $address $mask]
   SA_setvar [list [list $to_ip_oid OctetString $to_ip]]
   ```

4. **Default/Fixed** — Hidden column gets a constant default value. Example: `Mode = 1`.
   ```tcl
   # No TCL needed — handled by %dcol default value
   ```

5. **Status mirroring** — "Current" tables mirror the "Config" tables after activation. Example: `rsBWMCurrentRulesEntry` mirrors `rsBWMRulesEntry`. These may need `%init_action` or activation-triggered copy.

### Phase 5: Integration
**Goal:** Integrate modeling file generation into the MIB compiler pipeline.

1. Add modeling file generation step to the compiler
2. Generate a single `.tcl` file with all `%after_set_action` blocks
3. Upload to SAPRO alongside `.cmf` and `.var` files
4. Update the SAPRO map to associate the modeling file with devices

## File Locations

| Resource | Path |
|----------|------|
| SOAP metadata (DP) | `backend/dp_debug/DefensePro_v10-12-0-1_SOAP_API/wsdl.tar/wsdl/soap_metadata.c` |
| IDS WSDLs | `backend/dp_debug/DefensePro_v10-12-0-1_SOAP_API/ids_wsdl/wsdl/*.wsdl` |
| DP WSDLs | `backend/dp_debug/DefensePro_v10-12-0-1_SOAP_API/dp_wsdl/wsdl/*.wsdl` |
| User Guide | `backend/dp_debug/DefensePro_v10-12-0-1_User_Guide.pdf` |
| Release Notes | `backend/dp_debug/DefensePro_v10-12-0-1_Release_Notes.pdf` |
| SAPRO Guide | `backend/app/modules/sapro/oid_compiler/sapro290.pdf` |
| Existing TCL example | `backend/app/modules/sapro/oid_compiler/test_snmp.tcl` |
| MIB compiler module | `backend/app/modules/sapro/oid_compiler/` |
| Generated CMF | `backend/app/modules/sapro/oid_compiler/DP_10_12_01.cmf` (reference) |
| Generated VAR | `backend/app/modules/sapro/oid_compiler/DP_10_12_01.var` (reference) |
| Working VAR (10.6) | `backend/app/modules/sapro/oid_compiler/DPX_10-6.var` (reference) |
| Working CMF (10.6) | `backend/app/modules/sapro/oid_compiler/DPX.cmf` (reference) |

## Key Constraints

1. **DPX.var dynamic rows don't work** — The DPX.var file (from SAPRO's teaching agent) has broken dynamic rows. Do NOT use it as reference for dynamic row behavior. Only use it for scalar/format reference.
2. **SAPRO guide is source of truth** for modeling file syntax and TCL commands
3. **soap_metadata.c** is source of truth for which columns are firmware-computed
4. **Real DP + CC** is source of truth for actual computed values
5. **All modeling must be automated** — no manual per-table work

## Risk Areas

1. **IDS tables not in soap_metadata.c** — Security module tables are only in WSDLs, which don't have the `hidden` flag. Need to cross-reference WSDL elements against CMF columns to identify hidden ones.
2. **Complex computation logic** — Some hidden columns may require non-trivial TCL (like the broadcast address calculation). May need pattern library.
3. **"Current" table mirroring** — Tables like `rsBWMCurrentRulesEntry` mirror config tables after activation. This may require understanding the activation workflow.
4. **Table interdependencies** — Setting a value in one table may affect another table. Example: creating a policy may auto-create entries in statistics tables.
