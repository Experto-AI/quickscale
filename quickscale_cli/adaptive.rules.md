---
domain: quickscale_cli
merge_strategy: append
---

# Shared
<!-- Add reusable principles to be included by reference here -->
- Source lives at quickscale_cli/src/quickscale_cli/.
- This package is the command surface only. Business logic belongs in quickscale_core.
- CLI commands are grouped: lifecycle (plan, apply, status, remove), disaster recovery
  (dr capture/plan/execute/report), local dev (up, down, ps, logs, shell, manage),
  deployment (deploy), and module workflows (update, push).
- Tests live at quickscale_cli/tests/.

# Adaptive
<!-- Add rules for the main orchestrator agent here -->
[include](#shared)

# Plan
<!-- Add rules for planning and architectural design here -->
[include](#shared)
- CLI commands call into `quickscale_core` for heavy lifting. Scope CLI work to command wiring, argument parsing, and user-facing output.

# Codebase Discovery
<!-- Add rules for discovery and comprehension here -->
[include](#shared)

# External Research
<!-- Add rules for researching external APIs and docs here -->
[include](#shared)

# Implement
<!-- Add rules for writing code (e.g. backend specific syntax) here -->
[include](#shared)
- New commands belong here. New scaffolding or generation logic belongs in `quickscale_core`. Do not put template or generation logic in CLI handlers.

# Quality Gate
<!-- Add rules for testing, linting, and quality enforcement here -->
[include](#shared)

# Change Review
<!-- Add rules for PR review and change management here -->
[include](#shared)
