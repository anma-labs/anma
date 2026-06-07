# Architecture decisions (ANMA)

Append-only. Each entry explains *why* a boundary is the way it is, so neither
you nor Claude relitigates it next session. Newest on top.

## 2026-06-07 — Adopted ANMA contracts
Module boundaries are now declared in per-module `anma.yaml` files and enforced
by `anma check` (pre-commit + CI + Claude Code PreToolUse hook).
