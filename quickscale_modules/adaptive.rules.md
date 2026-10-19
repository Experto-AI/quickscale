---
domain: quickscale_modules
merge_strategy: append
---

# Shared
- This is the maintainer-side module inventory. It is not generated into user projects by default.
- Each module directory under quickscale_modules/<name>/ is independently packaged.
- module.yml is the canonical source for a module's shipped version and configuration metadata.
  The module's pyproject.toml version and exported __version__ must match the manifest.
- Modules are distributed to generated projects via the documented git-subtree workflow.
  Do not copy module files manually into generated project directories.
- Packaged modules: analytics, auth, backups, billing, blog, crm, forms, listings, notifications, orgs, social, storage.

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
- For packaged modules, `module.yml` owns version metadata. Update it in the same change as any version bump.

# Quality Gate
[include](#shared)
- Each packaged module has its own test suite. Run the module-specific target rather than the root suite for module-scoped work.
- Tier commands for this domain (see `docs/technical/validation_policy.md#validation-tiers`):
  `change` — `make lint`, `make typecheck`, and the module's focused pytest node;
  `task` — `make test-integration MODULE=<name>`; `release` — `make ci`.
- Module suites need PostgreSQL and live on the integration gate, never on `make test-unit`.

# Change Review
[include](#shared)
