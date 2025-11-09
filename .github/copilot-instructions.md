# Terminal command execution guidance

- When running terminal commands from Windows `cmd.exe` in this workspace, always invoke them through Git Bash using `bash -lc` so the command is executed in a Bash shell and the output can be captured reliably by tooling.

- Examples
  - From Windows `cmd.exe` (recommended for automation / tools):

    bash -lc "echo hello_from_git_bash; pwd; ls -la"

  - From Git Bash interactively (no `bash -lc` required):

    echo hello_from_git_bash; pwd; ls -la

- Rationale
  - Using `bash -lc` creates a POSIX-compatible bash subprocess on Windows and avoids quoting/encoding issues that can prevent the tool from reading stdout/stderr correctly.

- Tips
  - Avoid nested unescaped single quotes inside the `bash -lc "..."` wrapper; prefer double quotes outside and single quotes inside when needed, or escape appropriately.
  - If a command produces large output, pipe it to tools like `head` or `tail` to limit captured output.

## Import rules for code generation and edits

- NEVER use relative imports (for example: `from .module import X` or `from ..pkg import Y`) in the backend code.
- Always use absolute imports rooted at the repository package root. In this project that means using `from backend.app...` for backend modules.
- Do NOT use `from app...` or other ambiguous package roots — use `backend.app` explicitly.
- If you're unsure which package root to use, stop and ask before editing the files.

These rules ensure imports resolve the same way both when running the app as a module (e.g. `python -m backend.app.main`) and when running scripts directly from the repository.
