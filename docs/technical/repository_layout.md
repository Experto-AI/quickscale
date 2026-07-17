# Repository Layout (Authoritative)

> **You are here**: [QuickScale](../../START_HERE.md) -> [Technical](../index.md) -> **Repository Layout**
> **Related docs**: [Scaffolding](scaffolding.md) | [Implementation Contract](implementation_contract.md) | [Generated Project Structure](generated_project_structure.md)

This companion owns the maintainer-side repository layout, package-placement reference, and naming/import matrix. [scaffolding.md](./scaffolding.md) remains the structure hub and compatibility-anchor map; [decisions.md](./decisions.md) remains the tie-breaker for policy disputes.

<a id="post-mvp-structure"></a>
## Current Maintainer Repository Layout

This section is a maintainer-side reference for how the QuickScale repository is organized today. It is not a promise that every path here appears in generated client projects.

```
quickscale/
├── README.md
├── START_HERE.md
├── CHANGELOG.md
├── GLOSSARY.md
├── docs/
├── scripts/
├── quickscale/
├── quickscale_cli/
├── quickscale_core/
└── quickscale_modules/
    ├── README.md
    ├── analytics/
    ├── auth/
    ├── backups/
    ├── blog/
    ├── crm/
    ├── forms/
    ├── listings/
    ├── notifications/
    ├── social/
    └── storage/
```

Notes:
- Starter-theme assets live under `quickscale_core/generator/templates/themes/`.
- `quickscale_modules/` is the first-party module workspace used by maintainers.
- Package-local READMEs describe local responsibilities, but root docs remain authoritative.

## Optional Extraction / Personal Monorepo Pattern

Advanced users may keep a personal QuickScale-flavored monorepo for extracted reusable code. This is a workflow pattern, not generated output.

```
my-quickscale/
├── quickscale_core/
├── quickscale_cli/
├── quickscale_modules/
│   ├── auth/
│   ├── custom_reports/
│   └── listings/
├── docs/
└── scripts/
```

Use this pattern only when you are intentionally maintaining shared code across multiple projects. Generated client projects remain standard Django repositories.

<a id="6-naming-import-matrix-summary"></a>
<a id="naming-import-matrix-summary"></a>
## 6. Naming & Import Matrix (Summary)

| Concern | Import Path | Django App Label |
|---|---|---|
| Core | `quickscale_core` | `quickscale_core` |
| CLI | `quickscale_cli` | n/a |
| Auth Module | `quickscale_modules.auth` | `quickscale_modules_auth` |
| Listings Module | `quickscale_modules.listings` | `quickscale_modules_listings` |
| Notifications Module | `quickscale_modules.notifications` | `quickscale_modules_notifications` |
| Social Module | `quickscale_modules.social` | `quickscale_modules_social` |
| Storage Module | `quickscale_modules.storage` | `quickscale_modules_storage` |
| React Starter | generated frontend assets | user-owned project code |
| HTML Starter (removed in SA94) | generated Django templates (historical) | user-owned project code (existing projects) |

Rules:
- Dotted import paths map to underscore-qualified Django app labels where needed.
- Generated projects should favor standard Django import patterns.
- Do not introduce alternate naming systems when the existing package and app-label pattern is sufficient.
