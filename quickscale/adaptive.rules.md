---
domain: quickscale
merge_strategy: append
---

# Shared
- This is the installation meta-package. It has no implementation code; it only
  declares the combined quickscale-core and quickscale-cli dependency bundle.
- The only meaningful changes here are version pins in pyproject.toml.
- Do not add application logic under quickscale/src/; changes there affect the
  import shim only.

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
- Changes in this package are version pin updates in `pyproject.toml` only. Anything beyond a version bump requires a scope question first.

# Quality Gate
[include](#shared)
- This package has minimal test coverage by design — it contains no implementation to test.

# Change Review
[include](#shared)
