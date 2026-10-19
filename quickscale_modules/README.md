# quickscale_modules

Maintainer-side workspace of the first-party modules. Each module directory is a packaged Django
app; its `module.yml` is the canonical source for version and configuration, and its README is
its PyPI description. Repository policy: [decisions.md](../docs/technical/decisions.md); module
rules: [module_conventions.md](../docs/technical/module_conventions.md).

| Module | Scope |
|--------|-------|
| [analytics](./analytics/README.md) | Service-style PostHog analytics: capture helpers and template tags |
| [auth](./auth/README.md) | Authentication (django-allauth) |
| [backups](./backups/README.md) | Admin/ops backups with private local/remote artifacts |
| [billing](./billing/README.md) | Credits-first Stripe billing with module-owned pricing and dashboard routes |
| [blog](./blog/README.md) | Blog and content |
| [crm](./crm/README.md) | CRM |
| [forms](./forms/README.md) | Forms and submissions |
| [listings](./listings/README.md) | Structured listings |
| [notifications](./notifications/README.md) | Email notifications through django-anymail |
| [orgs](./orgs/README.md) | Organizations and multi-tenancy (Solo/SaaS, RBAC, FORCE-RLS) |
| [social](./social/README.md) | Social links and embeds with React-facing contracts |
| [storage](./storage/README.md) | Media storage (local or S3-compatible) |
