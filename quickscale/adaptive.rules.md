---
domain: quickscale
merge_strategy: append
---

# Shared
<!-- Add reusable principles to be included by reference here -->
- This is the installation meta-package. It has no implementation code; it only
  declares the combined quickscale-core and quickscale-cli dependency bundle.
- The only meaningful changes here are version pins in pyproject.toml.
- Do not add application logic under quickscale/src/; changes there affect the
  import shim only.

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
- All changes in this package should be version pin updates in `pyproject.toml`. Anything beyond a version bump should prompt a scope question.

# Quality Gate
<!-- Add rules for testing, linting, and quality enforcement here -->
[include](#shared)
- This package has minimal test coverage by design — it contains no implementation to test.

# Change Review
<!-- Add rules for PR review and change management here -->
[include](#shared)
