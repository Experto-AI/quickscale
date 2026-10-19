---
domain: scripts
merge_strategy: append
---

# Shared
- The root Makefile is the entrypoint. Call a script directly only when
  no make target exists or a script header says otherwise.
- Scripts expect to be run from the repository root. Repo-relative paths will break if
  a script is run from a subdirectory.
- Do not add a new script if a make target already covers the same workflow.

# Adaptive
[include](#shared)

# Plan
[include](#shared)
- Check whether an existing make target or script already covers the need before designing a new one. See `scripts/README.md` for the full command map.

# Codebase Discovery
[include](#shared)

# External Research
[include](#shared)

# Implement
[include](#shared)
- New automation belongs in the Makefile first. Add a script only when the logic is too complex for a make target.

# Quality Gate
[include](#shared)

# Change Review
[include](#shared)
