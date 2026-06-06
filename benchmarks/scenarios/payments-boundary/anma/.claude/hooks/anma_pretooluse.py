#!/usr/bin/env python3
"""ANMA PreToolUse hook (generated). Exit code 2 blocks the tool call.

Thin shim: the real logic lives in `anma.hook`, so it is tested and upgradable
via `pip install -U anma` without re-running `anma sync`. Fails OPEN (allows the
edit) with a warning if anma is not importable, so a missing install never blocks
your work — CI and pre-commit remain the hard gate.
"""
import sys

try:
    from anma.hook import run_hook
except Exception:
    sys.stderr.write("ANMA hook: `anma` not importable in this environment; "
                     "skipping in-session check (CI/pre-commit still enforce).\n")
    sys.exit(0)

sys.exit(run_hook(sys.stdin.read()))
