---
domain: examples
merge_strategy: append
---

# Shared
- Examples are reference material, not authoritative product scope.
- Examples are not generated into projects by default unless a workflow explicitly says otherwise.
- Treat examples as patterns that can be selectively copied, not as tested components.
- Do not add examples that imply features or constraints that are not in the main product.

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
- Examples are minimal and copyable. If an example grows into a tested module, it belongs in `quickscale_modules/`, not here.

# Quality Gate
[include](#shared)

# Change Review
[include](#shared)
- New examples must not contradict the generated project contract in `docs/technical/generated_project_structure.md`.
