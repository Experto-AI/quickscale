---
domain: quickscale_modules
merge_strategy: append
---

# Shared
<!-- Add reusable principles to be included by reference here -->
- This is the maintainer-side module inventory. It is not generated into user projects by default.
- Each module directory under quickscale_modules/<name>/ is independently packaged.
- module.yml is the canonical source for a module's shipped version and configuration metadata.
  The module's pyproject.toml version and exported __version__ must match the manifest.
- Modules are distributed to generated projects via the documented git-subtree workflow.
  Do not copy module files manually into generated project directories.
- Packaged modules: analytics, auth, backups, blog, crm, forms, listings, notifications, social, storage.
- In-repo packaged implementation line through Phase 6b (still gated from public plan/apply until Phase 7): billing.
- Placeholder-only (no tests/packaging yet): teams.

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
- For packaged modules, `module.yml` owns version metadata. Update it in the same change as any version bump.

# Quality Gate
<!-- Add rules for testing, linting, and quality enforcement here -->
[include](#shared)
- Each packaged module has its own test suite. Run the module-specific test target (`make MODULE=<name> test-unit -- --modules`) rather than the root test suite for module-scoped work.

# Change Review
<!-- Add rules for PR review and change management here -->
[include](#shared)
