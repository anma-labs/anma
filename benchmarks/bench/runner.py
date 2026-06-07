"""Agent runners.

Two backends behind one interface:

- ReplayRunner (default): deterministic. Applies recorded agent edits from
  ``<scenario>/replay/<arm>/``. This validates the harness + scorer offline; it
  is NOT a measurement of a live model.

- ClaudeCodeRunner: drives the real ``claude`` CLI in headless print mode with
  the staged repo as cwd, so the repo's ``.claude/settings.json`` PreToolUse hook
  and ``CLAUDE.md`` load for real. Requires the ``claude`` CLI on PATH and
  credentials (ANTHROPIC_API_KEY or a logged-in CLI). Flags are kept in one place
  below — confirm them against your `claude --help`, as they evolve.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunResult:
    workdir: Path
    arm: str
    turns: int = 0
    blocked: int = 0
    transcript: str = ""
    status: str = "ok"  # ok | no_change | error
    has_hook: bool = False  # was the ANMA PreToolUse hook installed in this arm?


def _stage(arm_dir: Path) -> Path:
    wd = Path(tempfile.mkdtemp(prefix="anma-bench-"))
    shutil.copytree(arm_dir, wd, dirs_exist_ok=True)
    return wd


def _has_anma_hook(root: Path) -> bool:
    return (root / ".claude" / "hooks" / "anma_pretooluse.py").exists()


def _snapshot(root: Path, globs: tuple[str, ...] = ("*.py",)) -> dict:
    return {str(p.relative_to(root)): p.read_text(errors="ignore")
            for g in globs for p in sorted(root.rglob(g))}


def _py_snapshot(root: Path) -> dict:  # back-compat alias (Python default)
    return _snapshot(root, ("*.py",))


class ReplayRunner:
    name = "replay"

    def __init__(self, scenario_dir: Path):
        self.scenario_dir = scenario_dir

    def run(self, arm_dir: Path, task: str, arm: str) -> RunResult:
        wd = _stage(arm_dir)
        patch = self.scenario_dir / "replay" / arm
        turns = 0
        if patch.exists():
            shutil.copytree(patch, wd, dirs_exist_ok=True)
            turns = 1
        return RunResult(wd, arm, turns=turns, transcript="(replay)",
                         status="ok", has_hook=_has_anma_hook(wd))


class ClaudeCodeRunner:
    name = "claude-code"

    def __init__(self, model: str | None = None, timeout: int = 900,
                 source_globs: tuple[str, ...] = ("*.py",)):
        self.model = model
        self.timeout = timeout
        self.source_globs = source_globs  # which files count for no_change detection

    def run(self, arm_dir: Path, task: str, arm: str) -> RunResult:
        wd = _stage(arm_dir)
        has_hook = _has_anma_hook(wd)
        before = _snapshot(wd, self.source_globs)
        cmd = ["claude", "-p", task, "--output-format", "json",
               "--permission-mode", "acceptEdits"]
        if self.model:
            cmd += ["--model", self.model]
        try:
            proc = subprocess.run(cmd, cwd=wd, capture_output=True, text=True,
                                  timeout=self.timeout)
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return RunResult(wd, arm, status="error", transcript=f"runner error: {e}",
                             has_hook=has_hook)

        transcript = (proc.stdout or "") + (proc.stderr or "")
        turns = blocked = 0
        status = "ok"
        try:
            data = json.loads(proc.stdout)
            turns = int(data.get("num_turns", 0))
            denials = data.get("permission_denials", []) or []
            edit_denials = sum(1 for d in denials
                               if d.get("tool_name") in ("Edit", "Write", "MultiEdit"))
            # Only attribute a block to ANMA when its hook is actually installed.
            blocked = edit_denials if has_hook else 0
            if data.get("is_error") or proc.returncode != 0:
                status = "error"
        except (ValueError, TypeError):
            status = "error"

        if status == "ok" and _snapshot(wd, self.source_globs) == before:
            status = "no_change"
        return RunResult(wd, arm, turns=turns, blocked=blocked,
                         transcript=transcript, status=status, has_hook=has_hook)


def build_runner(name: str, scenario_dir: Path, model: str | None,
                 source_globs: tuple[str, ...] = ("*.py",)):
    if name == "replay":
        return ReplayRunner(scenario_dir)
    if name == "claude-code":
        return ClaudeCodeRunner(model=model, source_globs=source_globs)
    raise SystemExit(f"unknown runner: {name}")
