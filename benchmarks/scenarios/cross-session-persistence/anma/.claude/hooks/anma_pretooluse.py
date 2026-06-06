#!/usr/bin/env python3
"""ANMA PreToolUse hook. Exit code 2 blocks the tool call (Claude Code convention)."""
import json
import subprocess
import sys

def main() -> int:
    try:
        json.load(sys.stdin)  # tool payload; we re-check the whole project, fast.
    except Exception:
        pass
    proc = subprocess.run(["anma", "check", "--quiet"], capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(
            "ANMA: this edit breaks a module boundary.\n"
            + proc.stdout
            + "\nFix the import, or update the module's anma.yaml + run `anma sync` "
            "and note it in DECISIONS.md.\n"
        )
        return 2  # block
    return 0

if __name__ == "__main__":
    sys.exit(main())
