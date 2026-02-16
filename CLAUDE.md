# SimulatorTools - Claude Code Instructions

## Critical Rules

### Map File Modification

**NEVER modify map files directly except in one specific case:**

✅ **ONLY ALLOWED**: `create_device()` writing to an **empty map file** (first device being added)

❌ **NEVER ALLOWED**: Modifying an existing map file that already has or had devices in it

**Always use Sapro commands for map modifications:**
- Use `delete_device()` which calls `deldev` command
- Use `create_device()` which calls `adddev` command for non-empty maps
- For `update_device()`: ALWAYS use `delete_device()` + `create_device()`, NEVER write to map file

**Why:** Directly modifying map files bypasses Sapro's internal state management and can corrupt the environment.

### Application Management

- **NEVER start or stop the backend/frontend apps yourself**
- Always ask the user to start/restart the application
- Do not use `taskkill`, `uvicorn`, `npm start`, or any process management commands
- If changes require a restart, inform the user and ask them to restart manually

### No Fallbacks

- **NO fallbacks anywhere in the code**
- If data is missing, let it fail explicitly
- Examples of what NOT to do:
  - `workspace = getattr(current_user, 'workspace', 'default')` ❌
  - `workspace: str = "default"` as parameter default ❌
- Correct approach:
  - `workspace = current_user.workspace` ✅
  - `workspace: str` without default ✅

### Import Organization

- **ALL imports MUST be at the top of the file**
- NEVER use inline imports (e.g., `from backend.app.utils... inside functions`)
- Exception: None

### Git Commits

- **NEVER commit unless explicitly asked by user**
- **ALWAYS ASK before adding new untracked files to git** - do not automatically stage new files
- NEVER use `--amend` after hook failures (create NEW commits instead)
- NEVER skip hooks with `--no-verify`
- Always stage specific files, not `git add -A` or `git add .`
- When user asks to commit, show them what files will be added and get confirmation first

### File and Folder Creation

- **NEVER CREATE NEW FOLDERS in project root without explicit user approval**
- If file location is unclear, ASK the user where to place it
- Follow existing project structure:
  - Backend modules: `backend/app/modules/`
  - Backend routes: `backend/app/routes/`
  - Backend models: `backend/app/models/`
  - Backend utilities: `backend/app/utils/`
  - Frontend components: `frontend/src/components/`
  - Frontend pages: `frontend/src/pages/`
  - Frontend services: `frontend/src/api/services/`
- Do not invent new folder structures or locations

## Project Architecture

### Backend (FastAPI + MongoDB)

- **Start command** (from project root):
  ```bash
  python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
  ```
- **Import style**: Absolute imports only: `from backend.app.*`
- **Database**: MongoDB for templates, structures, and user data

### Frontend (React TypeScript)

- **Framework**: React with TypeScript
- **UI Library**: Material-UI
- **State Management**: React hooks and context

### Workspace Handling

- Admin users have `workspace='*'` which causes file path issues
- **Always use** `normalize_workspace_for_paths()` to convert `'*'` → `'default'`
- Located in: `backend/app/utils/auth.py`

### Sapro Integration

- **Map paths**: Use `get_full_map_path()` - NEVER construct paths manually
- **Device operations**: Use Sapro commands via `SaproCommunicationHandler`:
  - `create_device()` - Add device (uses adddev or writes to empty map)
  - `delete_device()` - Remove device (uses deldev)
  - `update_device()` - Update device (uses delete_device + create_device)
  - `start_devices_from_map()` - Start devices (uses startdev)
- **Map data**: Retrieved from session storage `saproSimulators` (matches SNMP pattern)

## Polling Feature

### Key Files

- **Backend**:
  - `backend/app/routes/reporter.py` - API endpoints
  - `backend/app/modules/reporter/polling/polling_service.py` - Business logic
  - `backend/app/modules/reporter/polling/xmf_generator.py` - XMF/TCL generation
  - `backend/app/models/polling.py` - Data models
  - `backend/app/models/polling_structure.py` - Structure template models

- **Frontend**:
  - `frontend/src/pages/PollingPage.tsx` - Main UI page
  - `frontend/src/components/Reporter/Polling/` - UI components
  - `frontend/src/types/polling.ts` - TypeScript types
  - `frontend/src/utils/structureParser.ts` - Structure transformation utilities

### Data Storage

- **Structure templates**: MongoDB `polling_structures` collection (predefined templates)
- **User templates**: MongoDB `polling_templates` collection (user-created configurations)
- **XMF generation**: Uses TCL scripts on Sapro server

### Array Structure Transformation

- **UI format**: Stores configured items in `field.value` array
- **Backend format**: Expects `field.repeat` count and `field.item` template
- **Transform function**: `cleanStructureForBackend()` before sending to API
- **Restore function**: `restoreStructureFromBackend()` when loading templates

### Field-Specific Rules

#### TCP-flag Field
- Must be disabled (grayed out) when protocol is not TCP
- Implemented with `disabled` parameter in `renderNestedField()`
- Visual feedback: opacity 0.6, helper text

#### Timestamp Offsets
- Current standard: `time_from=60`, `time_to=0`
- Old values (120/60) need migration via `backend/scripts/fix_timestamp_offsets.py`

#### Protocol Values
- Use named values: `["tcp", "udp", "icmp", "sftp", "other"]`
- NOT numeric: `["6", "17", "1"]`
- Migration script: `backend/scripts/fix_protocol_options.py`

## API Endpoints

### Polling Structure Templates
- `GET /api/cc/{cc_ip}/reporter/polling/structures` - List all structures
- `GET /api/cc/{cc_ip}/reporter/polling/structures/{structure_id}` - Get specific structure

### Polling Templates (User-created)
- `POST /api/cc/{cc_ip}/polling/templates` - Create template
- `GET /api/cc/{cc_ip}/polling/templates` - List templates
- `GET /api/cc/{cc_ip}/polling/templates/{template_id}` - Get template
- `DELETE /api/cc/{cc_ip}/polling/templates/{template_id}` - Delete template

### Polling Actions
- `POST /api/cc/{cc_ip}/simulators/{simulator_ip}/reporter/polling/save-xmf` - Save XMF only
- `POST /api/cc/{cc_ip}/simulators/{simulator_ip}/reporter/polling` - Full flow (save + load)

## Code Patterns

### Error Handling

- Don't use destructive operations as shortcuts
- Investigate root causes before deleting/overwriting
- Ask user before risky operations (force push, hard reset, etc.)

### Over-Engineering

- Avoid over-engineering solutions
- Only make changes that are directly requested or clearly necessary
- Keep solutions simple and focused
- Don't add features, refactoring, or "improvements" beyond what was asked

### Security

- Be careful not to introduce security vulnerabilities (command injection, XSS, SQL injection, etc.)
- If you notice insecure code, immediately fix it
- Prioritize writing safe, secure, and correct code
