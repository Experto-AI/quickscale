# quickscale_modules

First-party module workspace for QuickScale maintainers.

This directory is a maintainer-side inventory of reusable modules. It is not generated into user projects by default, and root documentation remains authoritative for repository-wide policy and scope.

## Module inventory

For packaged modules, `module.yml` is the canonical source for shipped version and configuration metadata. When a module also exposes package-local version metadata, its `pyproject.toml` version and exported `__version__` value should match the manifest.

### Packaged modules

These directories currently include packaging and implementation scaffolding. Use each module README for module-specific setup, behavior, and constraints.

| Module | Notes |
|--------|-------|
| [auth](./auth/README.md) | Authentication module with local packaging, tests, and manifest |
| [blog](./blog/README.md) | Blog/content module with local packaging, tests, and manifest |
| [crm](./crm/README.md) | CRM module with local packaging, tests, and manifest |
| [forms](./forms/README.md) | Forms module with local packaging, tests, and manifest |
| [listings](./listings/README.md) | Listings module with local packaging, tests, and manifest |
| [analytics](./analytics/README.md) | Service-style PostHog analytics module with flat settings, capture helpers, and template-tag support |
| [social](./social/README.md) | Social module with packaged Django app, managed runtime services, admin workflows, and React-facing contracts |
| [storage](./storage/README.md) | Storage module with local packaging, tests, and manifest |
| [backups](./backups/README.md) | Admin/ops-first backups module with private local/remote artifact workflows |

### Placeholder directories

These directories currently act as placeholders or documentation stubs. They do not yet have the same local packaging/test structure as the packaged modules above, and they remain inventory-only until implementation ships.

| Module | Notes |
|--------|-------|
| [billing](./billing/README.md) | Reserved module directory with README-only local context |
| [teams](./teams/README.md) | Reserved module directory with README-only local context |

## Notes for maintainers

- Use this README as a directory-level index only.
- Use each per-module README for module-specific details.
- For architecture, scope, and structural rules, defer to [../README.md](../README.md), [../docs/technical/decisions.md](../docs/technical/decisions.md), and [../docs/technical/scaffolding.md](../docs/technical/scaffolding.md).
