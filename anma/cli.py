"""anma CLI. Exit codes: 0 = ok, 1 = violations / contract errors / drift."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .compile import check_drift, sync as compile_sync
from .contracts import load_project, validate
from .adapters import get_adapter
from .scaffold import init_project


def _load(root: Path):
    project = load_project(root)
    return project, validate(project)


def cmd_init(args) -> int:
    root = Path(args.path).resolve()
    created = init_project(root)
    print(f"Initialized ANMA in {root}")
    for c in created:
        print(f"  + {Path(c).relative_to(root)}")
    print("\nNext: edit the contracts, then run `anma sync`.")
    return 0


def cmd_sync(args) -> int:
    root = Path(args.path).resolve()
    project, issues = _load(root)
    if issues:
        print("Contract problems (fix these first):", file=sys.stderr)
        for i in issues:
            print(f"  - {i}", file=sys.stderr)
        return 1
    if args.check:
        stale = check_drift(project)
        if stale:
            print("✗ Generated artifacts are out of date — run `anma sync`:")
            for s in stale:
                print(f"  {s}")
            return 1
        print("✓ Generated artifacts are up to date with the contracts")
        return 0
    written = compile_sync(project)
    print(f"Synced {len(project.modules)} module(s). Generated:")
    for w in written:
        print(f"  ~ {Path(w).relative_to(root)}")
    return 0


def cmd_check(args) -> int:
    root = Path(args.path).resolve()
    project, issues = _load(root)
    if issues:
        if args.json:
            print(json.dumps({"contract_errors": issues, "violations": []}))
        elif not args.quiet:
            for i in issues:
                print(f"contract: {i}", file=sys.stderr)
        return 1

    adapter = get_adapter(project.language)
    engine = adapter.engine_name(project)
    violations = adapter.check(project)
    hard = [v for v in violations if not v.deprecated]

    if args.json:
        print(json.dumps({
            "engine": engine,
            "contract_errors": [],
            "violations": [v.as_dict() for v in violations],
        }))
        return 0 if (args.warn or not hard) else 1

    if violations:
        kind = "warning" if (args.warn or not hard) else "violation"
        mark = "!" if (args.warn or not hard) else "✗"
        if not args.quiet:
            print(f"{mark} {len(violations)} boundary {kind}(s) [engine: {engine}]")
        for v in violations:
            print(f"  {v}")
        return 0 if (args.warn or not hard) else 1

    if not args.quiet:
        print(f"✓ All module boundaries respected [engine: {engine}]")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="anma",
        description="Architecture contracts that keep Claude Code inside module boundaries.")
    p.add_argument("--version", action="version", version=f"anma {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="scaffold ANMA into a project")
    pi.add_argument("path", nargs="?", default=".")
    pi.set_defaults(func=cmd_init)

    ps = sub.add_parser("sync", help="regenerate CLAUDE.md / hooks / tach config from contracts")
    ps.add_argument("path", nargs="?", default=".")
    ps.add_argument("--check", action="store_true",
                    help="don't write; fail if generated artifacts are stale (for CI)")
    ps.set_defaults(func=cmd_sync)

    pc = sub.add_parser("check", help="enforce module boundaries (hook / pre-commit / CI)")
    pc.add_argument("path", nargs="?", default=".")
    pc.add_argument("--warn", action="store_true",
                    help="report violations but exit 0 (incremental adoption)")
    pc.add_argument("--json", action="store_true", help="machine-readable output")
    pc.add_argument("--quiet", action="store_true")
    pc.set_defaults(func=cmd_check)

    ph = sub.add_parser("_hook", help=argparse.SUPPRESS)  # internal: PreToolUse
    ph.set_defaults(func=lambda _a: _run_hook())

    args = p.parse_args(argv)
    return args.func(args)


def _run_hook() -> int:
    from .hook import main as hook_main
    return hook_main()


if __name__ == "__main__":
    sys.exit(main())
