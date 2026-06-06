# Architecture
Two modules under `src/domains`: `accounts` and `billing`.
Rule: `billing` may depend on `accounts`; `accounts` must NOT depend on `billing`.
Cross-module access goes through public functions only.
