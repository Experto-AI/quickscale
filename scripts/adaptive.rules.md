---
domain: scripts
merge_strategy: append
---

# Shared
<!-- Add reusable principles to be included by reference here -->
- Always prefer the root Makefile as the entrypoint. Call a script directly only when
  no make target exists or a script header says otherwise.
- Scripts expect to be run from the repository root. Repo-relative paths will break if
  a script is run from a subdirectory.
- Do not add a new script if a make target already covers the same workflow.

# Adaptive
<!-- Add rules for the main orchestrator agent here -->
[include](#shared)

# Plan
<!-- Add rules for planning and architectural design here -->
[include](#shared)
- Check whether an existing make target or script already covers the need before designing a new one. See `scripts/README.md` for the full preferred-command map.

# Codebase Discovery
<!-- Add rules for discovery and comprehension here -->
[include](#shared)

# External Research
<!-- Add rules for researching external APIs and docs here -->
[include](#shared)

# Implement
<!-- Add rules for writing code (e.g. backend specific syntax) here -->
[include](#shared)
- New automation belongs in the Makefile first. Add a script only when the logic is too complex for a make target.

# Quality Gate
<!-- Add rules for testing, linting, and quality enforcement here -->
[include](#shared)

# Change Review
<!-- Add rules for PR review and change management here -->
[include](#shared)
