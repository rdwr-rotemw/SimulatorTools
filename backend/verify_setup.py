"""
Lightweight setup verification script for the backend.

This script performs import-time checks for models, schemas, settings,
database utilities, and auth utilities. It does NOT attempt to connect to
any databases; it validates that DB URLs are present and look well-formed.

Usage: run from repository root (this file is located at backend/verify_setup.py)
    bash -lc "python backend/verify_setup.py"
"""
from __future__ import annotations

import importlib
import sys
import traceback
from urllib.parse import urlparse
from pathlib import Path

# Ensure repository root is on sys.path so absolute imports like
# `backend.app.models` work both when running the script directly and
# when running from other working directories.
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

CHECKS = {
    "config": False,
    "models": False,
    "schemas": False,
    "database_utils": False,
    "auth_utils": False,
}

errors = []

# Helper to try multiple import paths
def try_import(module_path: str, names: list):
    """Try importing names from module_path. Returns dict of name->object or raises."""
    try:
        mod = importlib.import_module(module_path)
    except Exception:
        raise
    out = {}
    for n in names:
        try:
            out[n] = getattr(mod, n)
        except AttributeError:
            raise ImportError(f"Module '{module_path}' has no attribute '{n}'")
    return out

print("\nRunning backend setup verification...\n")

# 1) Load config/settings
settings = None
for cfg_path in ("backend.app.utils.config", "app.utils.config", "backend.app.utils.config"):
    try:
        cfg_mod = importlib.import_module(cfg_path)
        settings = getattr(cfg_mod, "settings", None) or getattr(cfg_mod, "get_settings", None) and cfg_mod.get_settings()
        if settings:
            CHECKS["config"] = True
            print("✓ Config loaded successfully from", cfg_path)
            break
    except Exception as e:
        # try next
        last_exc = e
if not CHECKS["config"]:
    print("✗ Failed to load config/settings. Tried paths: backend.app.utils.config, app.utils.config")
    errors.append(traceback.format_exc())

# 2) Import models
# Replace the models import block with a more robust per-module import check
models_ok = False
model_names = ["User", "Role", "Permission", "Simulator", "CCCredentials", "AuditLog", "UserRole", "RolePermission"]
missing_models = []
for name in model_names:
    found = False
    # try package-level import first
    for base in ("backend.app.models", "app.models"):
        try:
            mod = importlib.import_module(base)
            if hasattr(mod, name):
                found = True
                break
        except Exception:
            pass
    # try module-level imports (e.g., backend.app.models.user)
    if not found:
        candidate_module_names = [f"backend.app.models.{name.lower()}", f"app.models.{name.lower()}"]
        for cand in candidate_module_names:
            try:
                m = importlib.import_module(cand)
                if hasattr(m, name):
                    found = True
                    break
            except Exception:
                # last resort: try importing module by snake_case variations
                try:
                    alt = cand.replace(name.lower(), name.lower().replace('cccredentials','cc_credentials'))
                    m = importlib.import_module(alt)
                    if hasattr(m, name):
                        found = True
                        break
                except Exception:
                    pass
    if not found:
        missing_models.append(name)

if not missing_models:
    models_ok = True
    CHECKS["models"] = True
    print("✓ All models imported (checked individually)")
else:
    print("✗ Missing models:", missing_models)
    errors.append(f"Missing models: {missing_models}")

# 3) Import schemas
schemas_ok = False
schema_pkg_candidates = ("backend.app.schemas", "app.schemas")
schema_names = [
    ("user", ["UserCreate", "UserResponse"]),
    ("simulator", ["SimulatorCreate", "SimulatorUpdate", "SimulatorResponse"]),
    ("cc_credentials", ["CCCredentialsCreate", "CCCredentialsResponse"]),
    ("audit_log", ["AuditLogResponse"]),
    ("role", ["RoleCreate", "RoleResponse"]),
    ("permission", ["PermissionCreate", "PermissionResponse"]),
    ("auth", ["LoginRequest", "LoginResponse"]),
    ("common", ["SuccessResponse", "ErrorResponse"]),
]
try:
    for base in schema_pkg_candidates:
        ok = True
        for module_name, names in schema_names:
            try:
                full = f"{base}.{module_name}"
                m = importlib.import_module(full)
                for n in names:
                    if not hasattr(m, n):
                        raise ImportError(f"Missing {n} in {full}")
            except Exception:
                ok = False
                break
        if ok:
            schemas_ok = True
            CHECKS["schemas"] = True
            print("✓ All schemas imported from", base)
            break
    if not schemas_ok:
        print("✗ Failed to import all schemas from expected packages (backend.app.schemas or app.schemas)")
        errors.append("Schemas import failed")
except Exception:
    errors.append(traceback.format_exc())

# 4) Database utilities
db_utils_ok = False
for db_path in ("backend.app.utils.database", "app.utils.database"):
    try:
        db_mod = importlib.import_module(db_path)
        # Check for common symbols
        has_engine = hasattr(db_mod, "engine")
        has_session = hasattr(db_mod, "SessionLocal") or hasattr(db_mod, "get_db")
        has_mongo = hasattr(db_mod, "mongo_client") or hasattr(db_mod, "get_mongo_db")
        if has_engine and has_session:
            db_utils_ok = True
            CHECKS["database_utils"] = True
            print("✓ Database utilities available from", db_path)
            break
    except Exception:
        continue
if not db_utils_ok:
    print("✗ Database utilities not found in expected locations")
    errors.append("Database utilities import failed")

# 5) Auth utilities
auth_ok = False
for auth_path in ("backend.app.utils.auth", "app.utils.auth"):
    try:
        auth_mod = importlib.import_module(auth_path)
        required = ["hash_password", "verify_password", "create_access_token", "verify_token", "get_current_user"]
        if all(hasattr(auth_mod, name) for name in required):
            auth_ok = True
            CHECKS["auth_utils"] = True
            print("✓ Auth utilities available from", auth_path)
            break
    except Exception:
        continue
if not auth_ok:
    print("✗ Auth utilities not available")
    errors.append("Auth utilities import failed")

# Verify DB URL formatting (do not connect)
print("\nVerifying DB URL formats (no connections will be made):")
if CHECKS["config"]:
    try:
        sql_url = settings.sqlalchemy_database_url()
        mongo_url = settings.mongodb_uri()
        # Basic parsing for SQL URL
        parsed = urlparse(sql_url)
        sql_ok = parsed.scheme.startswith("postgres") and parsed.path and parsed.path != "/"
        print(f" - Postgres URL: {sql_url[:80]}{'...' if len(sql_url)>80 else ''}")
        print("   -> Postgres URL looks ok?", "Yes" if sql_ok else "No")
        # Basic check for mongo
        print(f" - MongoDB URI: {mongo_url[:80]}{'...' if len(mongo_url)>80 else ''}")
        print("   -> MongoDB URI looks ok?", "Yes" if mongo_url.startswith("mongodb") else "No")
    except Exception as e:
        print(" - Error while inspecting DB URLs:", str(e))
        errors.append(traceback.format_exc())
else:
    print(" - Skipped DB URL checks because config failed to load")

# Final summary
print("\nSummary checklist:")
for k, ok in CHECKS.items():
    mark = "✓" if ok else "✗"
    print(f" {mark} {k}")

if errors:
    print("\nErrors / details:")
    for e in errors:
        print("---\n", e)
    sys.exit(2)

print("\nAll import checks passed.")
