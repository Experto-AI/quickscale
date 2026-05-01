---
domain: examples
merge_strategy: append
---

# Shared
<!-- Add reusable principles to be included by reference here -->
- Examples are reference material, not authoritative product scope.
- Examples are not generated into projects by default unless a workflow explicitly says otherwise.
- Treat examples as patterns that can be selectively copied, not as tested components.
- Do not add examples that imply features or constraints that are not in the main product.

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
- Examples should be minimal and copyable. If an example grows into a tested module, it belongs in `quickscale_modules/`, not here.

# Quality Gate
<!-- Add rules for testing, linting, and quality enforcement here -->
[include](#shared)

# Change Review
<!-- Add rules for PR review and change management here -->
[include](#shared)
- New examples must not contradict the generated project contract in `docs/technical/generated_project_structure.md`.
