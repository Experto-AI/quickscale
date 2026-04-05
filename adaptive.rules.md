---
domain: root
merge_strategy: append
---

# Shared
<!-- Add reusable principles to be included by reference here -->
- **Authoritative SSOT (always read, this rules wins all)**:
    - Decisions: docs/technical/decisions.md
    - Scaffolding: docs/technical/scaffolding.md
- **Documentation precedence**:
    - Package README files are informational context only, SSOT wins any conflicts.
- **Important context (always read)**:
    - README.md
    - START_HERE.md
    - docs/contrib/contributing.md
- **Tooling**:
    - Makefile for common commands and workflows

# Adaptive
<!-- Add rules for the main orchestrator agent here -->
[include](#shared)

# Plan
<!-- Add rules for planning and architectural design here -->
[include](#shared)
- **Important context (always read)**:
    - docs/contrib/plan.md

# Codebase Discovery
<!-- Add rules for discovery and comprehension here -->
[include](#shared)

# External Research
<!-- Add rules for researching external APIs and docs here -->
[include](#shared)

# Implement
<!-- Add rules for writing code (e.g. backend specific syntax) here -->
[include](#shared)
- **Important context (always read)**:
    - docs/contrib/code.md

# Quality Gate
<!-- Add rules for testing, linting, and quality enforcement here -->
[include](#shared)
- **Important context (always read)**:
    - docs/contrib/testing.md
    - docs/contrib/debug.md

# Change Review
<!-- Add rules for PR review and change management here -->
[include](#shared)
- **Important context (always read)**:
    - docs/contrib/review.md
