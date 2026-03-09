---
domain: root
merge_strategy: append
---

# Shared
<!-- Add reusable principles to be included by reference here -->
- **Authoritative SSOT (always read, this rules wins all)**:
    - Decisions: docs/technical/decisions.md
    - Scaffolding: docs/technical/scaffolding.md
- **Important context (always read)**:
    - README.md
    - START_HERE.md
    - docs/contrib/contributing.md

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

# Quality Gate
<!-- Add rules for testing, linting, and quality enforcement here -->
[include](#shared)

# Change Review
<!-- Add rules for PR review and change management here -->
[include](#shared)
