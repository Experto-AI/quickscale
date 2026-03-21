# quickscale_modules

First-party module workspace for QuickScale maintainers.

This directory is a maintainer-side inventory of reusable modules. It is not generated into user projects by default, and root documentation remains authoritative for repository-wide policy and scope.

## Module inventory

### Packaged modules

These directories currently include packaging and implementation scaffolding. Use each module README for module-specific setup, behavior, and constraints.

| Module | Notes |
|--------|-------|
| [auth](./auth/README.md) | Authentication module with local packaging, tests, and manifest |
| [blog](./blog/README.md) | Blog/content module with local packaging, tests, and manifest |
| [crm](./crm/README.md) | CRM module with local packaging, tests, and manifest |
| [forms](./forms/README.md) | Forms module with local packaging, tests, and manifest |
| [listings](./listings/README.md) | Listings module with local packaging, tests, and manifest |
| [storage](./storage/README.md) | Storage module with local packaging, tests, and manifest |

### Placeholder directories

These directories currently act as placeholders or documentation stubs. They do not yet have the same local packaging/test structure as the packaged modules above.

| Module | Notes |
|--------|-------|
| [billing](./billing/README.md) | Reserved module directory with README-only local context |
| [teams](./teams/README.md) | Reserved module directory with README-only local context |

## Notes for maintainers

- Use this README as a directory-level index only.
- Use each per-module README for module-specific details.
- For architecture, scope, and structural rules, defer to [../README.md](../README.md), [../docs/technical/decisions.md](../docs/technical/decisions.md), and [../docs/technical/scaffolding.md](../docs/technical/scaffolding.md).
