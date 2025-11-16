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

## Assistant session rules (applies to every session)

The assistant will follow these rules for every session unless you explicitly change them:

- The assistant will NOT run the project-wide compile script `python scripts/compile_backend.py` automatically; you will run it locally and report the output when you want it checked.
- The assistant will NOT run long-running or invasive commands (servers, build/watch mode, etc.) without your explicit permission.
- When asked to run commands or checks, the assistant will always state the exact command it will run before executing it.
- The assistant will only run targeted, lightweight checks (for example: import checks or single-file py_compile) when you explicitly request them.
- The assistant will avoid using shell here-documents and will wrap `cmd.exe` invoked commands with `bash -lc` as described in this file.
- The assistant will follow the project's import rules: use absolute backend imports (e.g. `from backend.app...`) and never use relative imports in backend code.
- The assistant will start each response with a one-line task receipt and a concise high-level plan for the action it will take.
- The assistant will use `insert_edit_into_file` for edits and will not produce raw file-diff codeblocks in replies.
- If you run the compile helper locally and paste its output, the assistant will treat that output as canonical verification and proceed accordingly.

How to request the assistant to run the global compile here

If you DO want the assistant to run the global compile script within the workspace, request it explicitly with a command like:

```bash
bash -lc "python scripts/compile_backend.py"
```

and the assistant will run it after confirming the exact command with you.

(End of assistant session rules)
