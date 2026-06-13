"""PreToolUse hook logic.

Claude Code passes the proposed tool call on stdin *before* it runs. We
reconstruct the post-edit content of the single edited file and block (exit 2)
only if that edit introduces a NEW cross-module import the file's module is not
allowed to make. Crucially we do NOT block on the project's current state, so:

- a correct edit always lands, even if the project is red for unrelated reasons;
- the actual violating edit is blocked (we judge the proposed content, not the
  pre-edit state);
- edits that fix or don't worsen an existing violation are never deadlocked.

Kept in the package (not the generated shell script) so it is testable and
fixable via `pip install -U anma` without re-running `anma sync`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .contracts import load_project, is_excluded
from .adapters import any_adapter_handles, get_adapter
from .engine import module_for_file

ALLOW, BLOCK = 0, 2


def _proposed_content(tool_name: str, tool_input: dict, current: str) -> str | None:
    if tool_name == "Write":
        return tool_input.get("content", "")
    if tool_name == "Edit":
        old, new = tool_input.get("old_string", ""), tool_input.get("new_string", "")
        if old and old not in current:
            return None  # edit won't apply; let Claude Code handle it
        if tool_input.get("replace_all"):
            return current.replace(old, new)
        return current.replace(old, new, 1)
    if tool_name == "MultiEdit":
        out = current
        for e in tool_input.get("edits", []):
            old, new = e.get("old_string", ""), e.get("new_string", "")
            if old and old not in out:
                return None
            out = out.replace(old, new, 1)
        return out
    return None  # unknown tool: don't judge


def _find_project(file: Path):
    candidates = [Path.cwd(), *file.resolve().parents]
    seen = set()
    for cand in candidates:
        if cand in seen or not (cand / "anma.yaml").exists():
            continue
        seen.add(cand)
        try:
            project = load_project(cand)
        except Exception:
            continue
        if module_for_file(project, file) is not None:
            return project
    return None


def run_hook(stdin_text: str) -> int:
    try:
        data = json.loads(stdin_text)
    except (ValueError, TypeError):
        return ALLOW
    tool_input = data.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path")
    if not file_path:
        return ALLOW
    file = Path(file_path)
    if not any_adapter_handles(file):   # cheap pre-filter (no language owns this type)
        return ALLOW

    project = _find_project(file)
    if project is None:
        return ALLOW
    try:
        adapter = get_adapter(project.language)
    except ValueError:
        return ALLOW
    if not adapter.handles_file(file):
        return ALLOW
    module = module_for_file(project, file)
    if module is None:
        return ALLOW
    if is_excluded(project, file):
        return ALLOW  # excluded from boundary checks; CI ignores it, so must the hook

    current = file.read_text() if file.exists() else ""
    proposed = _proposed_content(data.get("tool_name", ""), tool_input, current)
    if proposed is None:
        return ALLOW

    current_bad = adapter.disallowed_targets(project, module, file, current)
    proposed_bad = adapter.disallowed_targets(project, module, file, proposed)
    new_bad = proposed_bad - current_bad
    if new_bad:
        targets = ", ".join(sorted(new_bad))
        sys.stderr.write(
            f"ANMA: this edit makes module '{module.name}' import "
            f"[{targets}], which its contract does not allow.\n"
            f"Fix the import, or add it to depends_on in "
            f"{module.path.name}/anma.yaml and run `anma sync` "
            f"(record why in DECISIONS.md).\n"
        )
        return BLOCK
    return ALLOW


def main() -> int:
    return run_hook(sys.stdin.read())
