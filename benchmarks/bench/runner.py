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


def _stage(arm_dir: Path) -> Path:
    wd = Path(tempfile.mkdtemp(prefix="anma-bench-"))
    shutil.copytree(arm_dir, wd, dirs_exist_ok=True)
    return wd


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
        return RunResult(wd, arm, turns=turns, transcript="(replay)")


class ClaudeCodeRunner:
    name = "claude-code"

    def __init__(self, model: str | None = None, timeout: int = 900):
        self.model = model
        self.timeout = timeout

    def run(self, arm_dir: Path, task: str, arm: str) -> RunResult:
        wd = _stage(arm_dir)
        cmd = ["claude", "-p", task, "--output-format", "json",
               "--permission-mode", "acceptEdits"]
        if self.model:
            cmd += ["--model", self.model]
        proc = subprocess.run(cmd, cwd=wd, capture_output=True, text=True,
                              timeout=self.timeout)
        transcript = (proc.stdout or "") + (proc.stderr or "")
        blocked = transcript.count("ANMA: this edit breaks a module boundary")
        turns = transcript.count('"role":"assistant"') or transcript.count('"type":"assistant"')
        return RunResult(wd, arm, turns=turns, blocked=blocked, transcript=transcript)


def build_runner(name: str, scenario_dir: Path, model: str | None):
    if name == "replay":
        return ReplayRunner(scenario_dir)
    if name == "claude-code":
        return ClaudeCodeRunner(model=model)
    raise SystemExit(f"unknown runner: {name}")
