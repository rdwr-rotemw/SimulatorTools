# Contributing

Please follow these repository conventions when contributing code:

- Backend import rules
  - Use absolute imports rooted at the repository package root: `backend.app...`
  - Never use relative imports like `from .module import X` or `from ..pkg import Y` in backend code.
  - Do not use ambiguous `from app...` imports; use `backend.app...` explicitly.

- Running the project
  - Use `python -m backend.app.main` or `uvicorn backend.app.main:app` to run the backend so package imports resolve correctly.

- Local checks
  - A small check script is available at `scripts/check_imports.py` to validate imports; you can run it before committing.

Thank you for contributing!

