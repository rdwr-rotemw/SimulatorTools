"""
Safe model package initializer.

Imports model modules dynamically and exposes model classes on the
package namespace while avoiding hard failures from circular imports.
This makes `from backend.app.models import User` more robust during
startup-time checks.
"""
from importlib import import_module
from typing import List

# List of model module names and the class names they should export
_MODEL_MAP = {
    "user": ["User"],
    "simulator": ["Simulator"],
    "cc_credentials": ["CCCredentials"],
    "audit_log": ["AuditLog"],
    "role": ["Role"],
    "permission": ["Permission"],
    "user_role": ["UserRole"],
    "role_permission": ["RolePermission"],
}

__all__: List[str] = []

for module_name, class_names in _MODEL_MAP.items():
    loaded = False
    for pkg_prefix in ("backend.app.models", "app.models"):
        try:
            mod = import_module(f"{pkg_prefix}.{module_name}")
        except Exception:
            mod = None
        if mod:
            for cls in class_names:
                if hasattr(mod, cls):
                    globals()[cls] = getattr(mod, cls)
                    __all__.append(cls)
            loaded = True
            break
    # If not loaded, continue to next; missing models will be handled by verifier script

# Provide a helpful repr when introspected
__doc__ = "Model package: exports: " + ", ".join(__all__)
