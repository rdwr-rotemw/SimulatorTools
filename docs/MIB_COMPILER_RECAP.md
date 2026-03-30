# MIB Compiler — Implementation Recap

**Date:** 2026-03-30
**Branch:** `feature/mib-compiler`
**Status:** Simulator starts successfully, CyberController integration in progress

## What Was Built

A full-stack feature that compiles DefensePro MIB files and OIDs PDF into SAPRO-compatible `.cmf` and `.var` files, with automatic dynamic row creation detection. Files are uploaded to the SAPRO server via SCP.

## Architecture

### Backend Module: `backend/app/modules/sapro/oid_compiler/`

| File | Purpose |
|------|---------|
| `models.py` | Pydantic data models (`OidEntry`, `PdfTableInfo`, `DynamicRowConfig`, `CompilationResult`, etc.) |
| `constants.py` | `SYNTAX_MAP` (MIB→CMF type normalization), default value mappings |
| `mib_parser.py` | Extracts MIB files from archive (ZIP/RAR), compiles with pysmi, loads into pysnmp, walks OID tree |
| `pdf_parser.py` | Parses OIDs PDF with pdfplumber (cached), version extraction via pypdfium2 |
| `cmf_generator.py` | Generates `.cmf` file — OID entries, `%en` entry names, `%ei` index declarations, `%ev` enum definitions |
| `var_generator.py` | Generates `.var` file — header, dynamic row blocks, scalar/table variables |
| `dynamic_row_detector.py` | Detects rowstatus/rmonstatus/newinstance tables by cross-referencing MIB + PDF data |
| `compiler.py` | Main orchestrator — parallel MIB+PDF parsing, PDF supplementation, SSH/SCP upload |

### API Route: `backend/app/routes/oid_compiler.py`

- `POST /api/oid-compiler/compile` — Upload MIB archive + OIDs PDF, returns compilation result
- `GET /api/oid-compiler/health` — Health check
- Uses `require_sapro_access` for authentication
- Output directories derived from user workspace automatically

### Frontend

| File | Purpose |
|------|---------|
| `frontend/src/pages/SaproDashboardPage.tsx` | Sapro hub page with cards for "Simulator Management" and "MIB Tools" |
| `frontend/src/pages/OIDCompilerPage.tsx` | MIB Compiler page — file upload, output name config, results display |
| `frontend/src/api/services/oidCompiler.service.ts` | API client for the compiler endpoint |

### Routing

- `/simulators` → Sapro Dashboard (hub page)
- `/sapro/simulators` → Simulator Management (existing page)
- `/sapro/mib-tools` → MIB Compiler page

## Key Technical Decisions & Challenges Solved

### MIB Parsing

The Radware MIB files are **SMIv1** format. Three issues were solved:

1. **RFC-1215 (TRAP-TYPE macro)** — Fails to compile. Stripped `TRAP-TYPE FROM RFC-1215` imports and TRAP-TYPE definitions from all MIB files before compilation.

2. **IP-MIB implicit dependency** — pysmi's SMIv1→v2 conversion remaps `ipAddrEntry` to `IP-MIB`, which isn't in the archive. Solution: generate a minimal `IP-MIB` stub with `ipAddrEntry` and related objects.

3. **pysmi batch compilation fails** — Single-pass bulk compile, with individual retries for failures.

4. **File naming** — MIB files have mixed extensions (`.mib`, `.txt`, `.asn`, `.smi`, `.mi1`). Files renamed to `<ModuleName>.mib` based on `DEFINITIONS ::= BEGIN` content.

5. **Archive format** — Files labeled `.rar` may actually be ZIP. Detected by magic bytes (`zipfile.is_zipfile()`).

6. **Range extraction** — pysnmp uses `ConstraintsIntersection` with multiple `ValueSizeConstraint` objects. Walk all constraints and take the tightest range.

7. **DEFVAL extraction** — Default values extracted via `node.getSyntax().prettyPrint()`. Enum names resolved to numeric values.

8. **Index column access** — pysnmp returns `readonly` for `not-accessible` index columns. Fixed by forcing `NA` access on index columns (C1..CN based on index count).

9. **Structural node filtering** — Only include `MibScalar`, `MibTableColumn`, `MibTableRow` node types. Skip `MibTree`, `ObjectIdentity`, `ModuleIdentity`, `MibTable`.

### PDF Parsing

1. **Performance** — pdfplumber is slow (~4 min for 265 pages). Solved with caching: first parse saves results to `.pdf_cache/<hash>.json`, subsequent runs with same PDF load instantly.

2. **Version extraction** — Uses pypdfium2 (sub-second) for cover page version, pdfplumber only for table extraction.

3. **21-column layout** — PDF tables have fixed 21-column layout with data at positions 0,3,6,9,12,15,18. Real fields: OID, Label, Syntax, TableName, Index, Access, Description.

4. **Cell wrapping** — PDF wraps identifiers across lines (e.g., `snmpTargetAddr\nTable`). Fixed with `_clean_identifier()` that strips all whitespace.

5. **Compound index resolution** — Index names are concatenated after whitespace removal. Resolved by matching against known column labels in the table using greedy longest-match.

6. **Parallel execution** — MIB parsing and PDF parsing run in parallel via `ThreadPoolExecutor`.

### CMF File Format

The CMF must include three directive sections beyond OID column lines:

1. **`%en` lines** — Entry/node name mappings for table entries (OID → label)
2. **`%ei` lines** — Index declarations per table entry. String-based indices (OctetString) get `*` prefix. **Critical: without `%ei`, SAPRO returns "Cannot get index information"**
3. **`%ev` lines** — Enum value definitions

Access levels: `RO`, `RW`, `RC` (read-create), `NA` (not-accessible for index columns).

Enum flags: `d` (default with range), `e` (enum), `r` (RowStatus), `p` (PhysAddress). No flag when no range.

Range: omitted for ObjectID. IpAddress always `(4,4)`. Enum ranges derived from enum values when no explicit MIB constraint.

### VAR File Format

- **Header** — Value type format documentation block
- **Dynamic row blocks** — `%drow` uses OID path (not entry name). `%dcol` uses `RC` access for read-create columns. `r_lastset(min, max, default)` with MIB DEFVAL when available.
- **Scalars** — `label.0 , syntax , access , value_info`. System scalars (`sysDescr`, `sysName`, etc.) have hardcoded defaults. `sysName` uses `$$MYIPADDRESS$$` SAPRO token.
- **Table variables** — `label.1 , syntax , access , value_info` format.
- **Unix line endings** — Written with `newline="\n"` to prevent CRLF on Windows.

### PDF Supplementation

The OIDs PDF may contain columns not in the MIB files (Radware firmware extensions). These are added to the OID entries so they appear in both CMF and `%dcol` blocks. Without this, SAPRO fails because `%dcol` references columns not in the CMF.

### Dynamic Row Detection

Only tables with actual evidence of deletion patterns in descriptions get `newinstance` type:
- **Pattern A:** `Setting this object to value invalid(N) has the effect of invalidating`
- **Pattern B:** `Status is invalid ... entry will be deleted`
- **Pattern C:** `Validity ... Invalid indicates`

Tables with `RowStatus` syntax → `rowstatus` type. Tables with `EntryStatus` → `rmonstatus` type. Regular tables with RW columns but no deletion evidence are NOT flagged as newinstance.

### File Upload

Generated files are written to SAPRO server via SCP (not local filesystem). Uses existing `SaproSSHClient` with `upload_file()` method. Temp files written with Unix line endings before upload.

## Compilation Results (DefensePro v10.12.0.1)

- **3777+ OID entries** parsed from MIB files (+ ~14 supplemented from PDF)
- **234 tables** from PDF
- **207 rowstatus** dynamic row tables detected
- **~15 newinstance** tables detected
- **3500+ entries** with range constraints
- **1106 entries** with enum values
- **Simulator starts successfully** in SAPRO

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pdfplumber` | 0.11.9 | PDF table extraction |
| `pypdfium2` | (bundled) | Fast PDF version extraction |
| `rarfile` | 4.2 | RAR archive support |
| `pysmi` | 1.6.2 | MIB compilation (already in project) |
| `pysnmp` | 4.4.12 | MIB loading/walking (already in project) |

## Known Issues / Future Work

- **CyberController SNMP errors** — Some OIDs return `noSuchObject` or `noSuchInstance`. Likely OIDs present in CC's expectations but missing from the compiled var file (e.g., `rsWSDSysUpTime`). Need to investigate which OIDs CC queries and ensure they're all present.
- **PDF parsing speed** — First compilation with a new PDF takes ~4 min (pdfplumber). Cached after first run.
- **MIB compilation speed** — ~1.5 min on slower machines. Runs in parallel with PDF parsing.

## Files Changed/Created

### New Files
- `backend/app/modules/sapro/oid_compiler/__init__.py`
- `backend/app/modules/sapro/oid_compiler/models.py`
- `backend/app/modules/sapro/oid_compiler/constants.py`
- `backend/app/modules/sapro/oid_compiler/mib_parser.py`
- `backend/app/modules/sapro/oid_compiler/cmf_generator.py`
- `backend/app/modules/sapro/oid_compiler/pdf_parser.py`
- `backend/app/modules/sapro/oid_compiler/dynamic_row_detector.py`
- `backend/app/modules/sapro/oid_compiler/var_generator.py`
- `backend/app/modules/sapro/oid_compiler/compiler.py`
- `backend/app/routes/oid_compiler.py`
- `frontend/src/pages/OIDCompilerPage.tsx`
- `frontend/src/pages/SaproDashboardPage.tsx`
- `frontend/src/api/services/oidCompiler.service.ts`
- `docs/MIB_COMPILER_PLANNING.md`
- `docs/MIB_COMPILER_RECAP.md`

### Modified Files
- `backend/app/main.py` — registered `oid_compiler_router`
- `backend/app/utils/sapro_ssh.py` — added `upload_file()` method
- `backend/requirements.txt` — added `pdfplumber`, `rarfile`
- `frontend/src/App.tsx` — added Sapro dashboard route, MIB tools route
- `frontend/src/components/cc/CCDeviceDriverDialog.tsx` — lint fixes
