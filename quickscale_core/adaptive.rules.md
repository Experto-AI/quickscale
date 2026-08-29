---
domain: quickscale_core
merge_strategy: append
---

# Shared
<!-- Add reusable principles to be included by reference here -->
- Source lives at quickscale_core/src/quickscale_core/.
- This is the scaffolding engine. Changes here affect the output of every generated project.
- Template changes require regeneration testing — verify that a fresh plan/apply cycle
  produces valid output.
- Tests live at quickscale_core/tests/.

# Adaptive
<!-- Add rules for the main orchestrator agent here -->
[include](#shared)

# Plan
<!-- Add rules for planning and architectural design here -->
[include](#shared)

# Codebase Discovery
<!-- Add rules for discovery and comprehension here -->
[include](#shared)

# External Research
<!-- Add rules for researching external APIs and docs here -->
[include](#shared)

# Implement
<!-- Add rules for writing code (e.g. backend specific syntax) here -->
[include](#shared)
- Template edits in `quickscale_core/src/quickscale_core/generator/` affect generated-project output. Treat template changes as user-facing contract changes.

# Quality Gate
<!-- Add rules for testing, linting, and quality enforcement here -->
[include](#shared)
- Tier commands for this domain (see `docs/technical/validation_policy.md#validation-tiers`):
  `change` — `make lint`, `make typecheck`, and `poetry run pytest quickscale_core/tests/<file-or-node> --tb=short -m "not e2e" -o addopts= --no-cov`;
  `task` — `make test-unit -- --core`; `release` — `make ci` (`make ci-e2e` after a template change).
- A template change under `src/quickscale_core/generator/` is user-facing generated-project output, so it escalates to `release`: verify generated project structure against `docs/technical/generated_project_structure.md`.

# Change Review
<!-- Add rules for PR review and change management here -->
[include](#shared)
