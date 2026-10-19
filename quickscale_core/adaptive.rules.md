---
domain: quickscale_core
merge_strategy: append
---

# Shared
- Source lives at quickscale_core/src/quickscale_core/.
- This is the scaffolding engine. Changes here affect the output of every generated project.
- Template changes require regeneration testing — verify that a fresh plan/apply cycle
  produces valid output.
- Tests live at quickscale_core/tests/.

# Adaptive
[include](#shared)

# Plan
[include](#shared)

# Codebase Discovery
[include](#shared)

# External Research
[include](#shared)

# Implement
[include](#shared)
- Template edits in `quickscale_core/src/quickscale_core/generator/` affect generated-project output. Treat template changes as user-facing contract changes.

# Quality Gate
[include](#shared)
- Tier commands for this domain (see `docs/technical/validation_policy.md#validation-tiers`):
  `change` — `make lint`, `make typecheck`, and `poetry run pytest quickscale_core/tests/<file-or-node> --tb=short -m "not e2e" -o addopts= --no-cov`;
  `task` — `make test-unit -- --core`; `release` — `make ci` (`make ci-e2e` after a template change).
- A template change under `src/quickscale_core/generator/` is user-facing generated-project output, so it escalates to `release`: verify generated project structure against `docs/technical/generated_project_structure.md`.

# Change Review
[include](#shared)
