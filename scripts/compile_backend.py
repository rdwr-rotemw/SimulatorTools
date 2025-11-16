#!/usr/bin/env python3
"""Compile all Python files under backend/ and print a clear, machine-readable result.
This avoids using shell heredocs so it is robust when invoked from Windows cmd.exe via `bash -lc`.
"""
import sys
import os
from pathlib import Path
import py_compile

root = Path(__file__).resolve().parents[1] / 'backend'
py_files = sorted(root.rglob('*.py'))
fails = []

print('PY_VERSION:', sys.version.replace('\n', ' '))
print('FILES_FOUND:', len(py_files))
for p in py_files:
    try:
        py_compile.compile(str(p), doraise=True)
    except py_compile.PyCompileError as e:
        fails.append((str(p), str(e)))

if not fails:
    print('COMPILE_OK')
    sys.stdout.flush()
    # Use os._exit to ensure the process exit code is set reliably
    os._exit(0)
else:
    print('COMPILE_FAIL')
    for f, e in fails:
        print('FAILED:', f)
        print(e)
    sys.stdout.flush()
    os._exit(2)
