---
domain: quickscale_cli
merge_strategy: append
---

# Shared
- Source lives at quickscale_cli/src/quickscale_cli/.
- This package is the command surface only. Business logic belongs in quickscale_core.
- CLI commands are grouped: lifecycle (plan, apply, status, remove), disaster recovery
  (dr capture/plan/execute/report), local dev (up, down, ps, logs, shell, manage),
  deployment (deploy), and module workflows (update, push).
- Tests live at quickscale_cli/tests/.

# Adaptive
[include](#shared)

# Plan
[include](#shared)
- CLI commands call into `quickscale_core` for heavy lifting. Scope CLI work to command wiring, argument parsing, and user-facing output.

# Codebase Discovery
[include](#shared)

# External Research
[include](#shared)

# Implement
[include](#shared)
- New commands belong here. New scaffolding or generation logic belongs in `quickscale_core`. Do not put template or generation logic in CLI handlers.

# Quality Gate
[include](#shared)
- Tier commands for this domain (see `docs/technical/validation_policy.md#validation-tiers`):
  `change` — `make lint`, `make typecheck`, and `poetry run pytest quickscale_cli/tests/<file-or-node> --tb=short -m "not e2e" -o addopts= --no-cov`;
  `task` — `make test-unit -- --cli`; `release` — `make ci`.

# Change Review
[include](#shared)
