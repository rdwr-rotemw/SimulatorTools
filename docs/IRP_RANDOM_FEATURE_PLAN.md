# IRP Random On-the-Fly Feature — Suspended Work Notes

> **Status:** Reverted. All code changes backed out. This document captures the full design
> and implementation so the work can be resumed later without starting from scratch.

---

## What Was Being Built

**Per-field live randomization for IRP messages**, mirroring the existing SNMP random feature.

Each leaf field in the IRP message form gets a **ShuffleIcon** toggle button. When toggled:
- The field is disabled / grayed out in the UI
- On every send (single or loop iteration) the **backend** generates a fresh random value
- The loop gets different values on every iteration without any UI interaction

This is **distinct** from the existing "Generate Random Values" (CasinoIcon) button on the
attack-id field, which randomizes once in the UI before sending.

### Design Decisions
- Use `ShuffleIcon` (not `CasinoIcon` — already taken by attack-id)
- Supported leaf types: `integer`, `float`, `string`, `enum`, `ipv4`, `ipv6`, `ipv4and6`, `attack-id`
- Supported at ALL nesting depths (objects, arrays, switch fields, clone fields)
- Frontend sends enriched objects `{path, fieldType, options?, min?, max?}` to backend
- Backend generates fresh values — no frontend randomization at send time
- "Set all fields to live-random" header button to toggle all fields at once

---

## Files Changed

### `frontend/src/components/irp/IRPMessageForm.tsx`

Added two new props:
```typescript
randomFields?: string[]
onRandomFieldToggle?: (path: string) => void
```

For each leaf field type (`enum`, `integer`, `float`, `ipv4`/`ipv6`, `string`, `attack-id`):
- Added `isRandom` check: `(randomFields ?? []).includes(pathString)`
- When random: field is `disabled`, `opacity: 0.6`, placeholder/helper = "Randomized per iteration"
- Added `ShuffleIcon` `IconButton` as `endAdornment` (or standalone for enum/boolean)

**Exclusions (no ShuffleIcon):**
- `relation` field (`or`/`and`) — structural discriminator; randomizing breaks footprint structure
- Boolean fields — structural (e.g. `ipv6-enable`); randomizing breaks message structure

### `frontend/src/pages/IRPSenderPage.tsx`

**New state field per message:**
```typescript
randomFields: string[]   // dot-notation paths of fields toggled as live-random
```

**New helpers:**

`getFieldSchemaAtPath(schema, pathParts)` — navigates UI schema tree to find field type info
at a given dot-notation path. Critical: handles ALL schema structural types:
- `_switchCases` (named switch, `fieldType:'object'`) — MUST be checked BEFORE object branch
- Options-based switch (`fieldType:'switch'`)
- Clone (`type:'clone'`, `fieldType:'object'`) — excluded from plain object branch
- Plain object
- `array` / `fixed-array` including flat-dict `itemSchema`

Uses `navigateIntoFieldSchema` sub-helper so sub-schema navigation always goes through
the full dispatch chain (not just `.fields`).

`collectAllRandomizablePaths(schema, data)` — traverses entire schema/data tree to collect
all randomizable leaf paths. Used by "Set all fields to live-random" button.
- Excludes `relation` key inside footprint objects
- Excludes `fixed-array` items (e.g. `current-mitigation-methods` bitmap enums)

**Send/loop payloads** now include enriched `randomFields` array:
```typescript
// Before sending, enriches string paths → field info objects
const enriched = randomFields.map(path => getFieldSchemaAtPath(schema, path.split('.')))
payload.random_fields = enriched
```

**All message construction sites updated** (PCAP import, JSON import, template load, loop start)
to include `randomFields: []`.

**Stale closure bug fixed** in `memoizedTestMessage`: was `[]` deps, holding stale empty
`messages`. Fixed by passing `msg` as direct parameter from render.

### `backend/app/modules/reporter/irp/irp_module.py`

New imports: `import copy`, `import random as _random` (already had `import time`)

**New functions:**

```python
def _generate_irp_random_value(field_info: Dict) -> Any:
    """Generate random value from {fieldType, options?, min?, max?}."""
    field_type = field_info.get('fieldType', 'string')
    if field_type == 'attack-id':
        return {'cnt': _random.randint(0, 9999), 'time': int(time.time())}
    elif field_type == 'integer':
        # Digit-count-uniform to avoid bias (plain randint is 90% 9-digit)
        min_val = int(field_info.get('min', 0))
        max_val = min(int(field_info.get('max', 255)), 999_999_999)
        max_digits = len(str(max_val))
        min_digits = len(str(max(min_val, 1)))
        num_digits = _random.randint(min_digits, max_digits)
        low = max(min_val, 10 ** (num_digits - 1) if num_digits > 1 else 1)
        high = min(max_val, 10 ** num_digits - 1)
        return _random.randint(low, high)
    elif field_type == 'float':
        return round(_random.uniform(0.0, 100.0), 2)
    elif field_type == 'string':
        # URL fields get proper URL format
        last_segment = field_info.get('path', '').split('.')[-1]
        if 'url' in last_segment.lower():
            # generates realistic URL
            ...
        return f"random_{_random.randint(1000, 9999)}"
    elif field_type == 'enum':
        return _random.choice(field_info.get('options', []))
    elif field_type in ('ipv4', 'ipv4and6'):
        return f"{_random.randint(1,254)}.{_random.randint(0,255)}.{_random.randint(0,255)}.{_random.randint(1,254)}"
    elif field_type == 'ipv6':
        return ':'.join(f'{_random.randint(0, 65535):04x}' for _ in range(8))
```

```python
def _set_nested_value(obj, path_parts, value):
    """Set value at nested path in dict/list structure."""
    # Navigates using path_parts, handles integer indices for lists

def apply_random_fields(message: Dict, random_fields: List[Dict]) -> Dict:
    """Apply random values to listed fields. Returns deep copy with fresh values.
    Call once per send/iteration."""
    # Special attack-id handling: detects whether message uses 'attack-id' key
    # (UI format) or separate 'cnt'/'time' keys (backend format after transform)
    if 'attack-id' in message:
        message['attack-id'] = f"{cnt}-{time}"
    else:
        message['cnt'] = cnt; message['time'] = time
```

**Modified `send_irp_messages`:** extracts `randomFields` before cleaning, calls
`apply_random_fields` on cleaned message.

**Modified `send_irp_messages_with_progress`:** same — extracts `random_fields` and
`pause` before building `cleaned_message`, calls `apply_random_fields`.

### `backend/app/modules/reporter/irp/irp_loop_manager.py`

In `_send_batch()`, before building the payload:
```python
resolved_messages = []
for msg in config.messages:
    msg_copy = dict(msg)
    random_fields = msg_copy.pop('randomFields', [])
    msg_copy = apply_random_fields(msg_copy, random_fields)
    resolved_messages.append(msg_copy)
payload = {"messages": resolved_messages}
```

### `backend/app/routes/reporter.py`

In `test_irp_message` endpoint: extracts `random_fields` from payload, calls
`apply_random_fields(template_data, random_fields)` before passing to coordinator.

Also: capture timeout reduced from 30s → 10s (unrelated UX improvement).

### `backend/app/modules/sapro/sapro_client.py` — UNRELATED FIX (also reverted)

In `start_map_and_wait()`, added check for `"Map was already running"` string in
output before the "unexpected output" failure path:
```python
if "Map was already running" in output:
    logger.info(f"Map {map_name} was already running")
    return True, f"Map {map_name} is already running"
```
**This is a useful, correct fix and can be re-applied independently.**

---

## Problems Encountered (and Solutions)

| Problem | Solution |
|---------|----------|
| `CasinoIcon` already used by attack-id | Chose `ShuffleIcon` |
| TypeScript compile errors: `randomFields` missing from 3+ message construction sites | Added `randomFields: []` to PCAP import, JSON import, `successfulMessages` type |
| Stale closure in `memoizedTestMessage` (always held empty `messages`) | Pass `msg` as direct render-time parameter instead of capturing from state |
| `getFieldSchemaAtPath` returning null for nested paths | Many iterations; root cause: `_switchCases`/clone branch ordering. Fixed with `navigateIntoFieldSchema` helper |
| attack-id not changing on send | Backend was setting `message['cnt']`/`message['time']` but MessageBuilder parsed `attack-id` key. Fixed: detect which format and update accordingly |
| `random_3632` string error from IRP MessageBuilder | `getFieldSchemaAtPath` returned null → defaulted to `'string'` → backend sent `"random_XXXX"` to an integer field. Each path type fix revealed a new failing path |
| Integer statistical bias | `randint(1, 999_999_999)` is 90% 9-digit. Fixed: pick digit count uniformly (1–9), then generate in that range |
| `relation` field causing inconsistent packets | Excluded from ShuffleIcon and "Randomize All" |
| `fixed-array` items with restricted enum values | Excluded from `collectAllRandomizablePaths` |
| `ipv4and6` field type not recognized | Added to `RANDOMIZABLE_FIELD_TYPES` and backend handler |
| URL fields needing proper URL format | Backend checks path segment for `'url'` and generates realistic URL |

---

## Why It Was Reverted

Too many edge cases in `getFieldSchemaAtPath` / `collectAllRandomizablePaths` — the IRP
schema tree has many structural variants (plain objects, named switches, options switches,
clones, arrays, fixed-arrays, flat-dict items) and each new test case exposed a new
unhandled path. Each fix bypassed/ignored the problem rather than solving the structural
navigation cleanly. The feature needs a clean rewrite of the schema traversal logic before
the randomization layer can be reliably applied.

---

## Recommended Approach for Re-implementation

1. **Write a dedicated schema walker** that handles all IRP schema types in one place,
   returning a flat list of `{path, fieldType, options, min, max}` objects. Test this
   independently against the full schema tree before connecting it to randomization.

2. **Use the walker for both** "collect all paths" and "find one path" — avoids
   maintaining two parallel traversal implementations.

3. **Test against real schemas** before wiring up UI: verify the walker produces correct
   output for every structural variant (named switch, options switch, clone, flat-dict array).

4. **Then add ShuffleIcon** to the form fields, using the walker output to validate
   that toggled paths will actually resolve.

5. **Backend `apply_random_fields`** is essentially correct and can be reused as-is.
   The `_set_nested_value` and `_generate_irp_random_value` logic is sound.
