# Architecture decisions (ANMA)

Append-only. Newest on top.

## 2026-05-20 — accounts stays decoupled from billing
A previous session removed a direct `accounts -> billing` import. Totals are
injected by the caller instead. Do NOT re-introduce the import; if accounts
needs invoiced data, accept it as a parameter.
