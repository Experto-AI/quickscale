# SCAFFOLDING: Repository, Packages, and Generated Project Structures

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Scaffolding** (Directory Structures)
> **Related docs**: [Decisions](decisions.md) | [Roadmap](roadmap.md) | [Glossary](../../GLOSSARY.md) | [Start Here](../../START_HERE.md)

Authoritative guide to the directory and file layouts QuickScale currently owns. This document complements [decisions.md](./decisions.md), which remains the single source of truth for rules, boundaries, and tie-breakers.

## 1. Scope & Principles

This document covers:
- Repository-level layout for the maintainer monorepo
- Current generated-project output from `quickscale plan`, then entering the generated directory and running `quickscale apply`
- Optional maintainer-side and advanced-user extraction layouts that are helpful context but are not generated into user projects by default

Guiding principles:
- Explicit over implicit, following standard Django structure where practical
- Generated projects are standalone and user-owned
- Themes are one-time scaffolding, while modules are long-lived runtime dependencies
- Package-local READMEs are helpful context, but root docs and [decisions.md](./decisions.md) remain authoritative

## 2. How to Use This Document

Read this file when you need:
- Current repository layout context
- Current generated-project file trees
- Naming and package-placement examples
- Maintainer-side extraction and module-workspace reference

Read [decisions.md](./decisions.md) instead when you need:
- Scope rulings or tie-breakers
- Prohibitions and technical policies
- The authoritative implementation surface matrix
- Tooling and packaging rules

Quick reminders for AI assistants:
- `quickscale_modules/` is a maintainer-side workspace and is not generated into client projects by default
- Generated projects use standalone Django settings unless the user intentionally adopts a documented manual inheritance pattern later
- `quickscale.yml` is the supported desired-state file; do not invent extra config registries or schema trees for generated projects

<a id="mvp-structure"></a>
## 3. Current Generated Structure

QuickScale currently generates a standalone Django project with production foundations, a starter theme, and optional embedded modules.

Key rules:
- The generated project is user-owned code
- `showcase_react` is the default starter theme
- `showcase_html` remains the secondary starter option
- Modules embed into the generated project and can later be updated through the documented git-subtree workflow
- QuickScale does not generate a maintainer-style `quickscale_modules/` workspace inside client projects

### 3.1 Base Generated Project

```
myapp/
├── manage.py
├── quickscale.yml
├── myapp/
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── local.py
│   │   └── production.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── frontend/                  # Default for showcase_react
│   ├── src/
│   ├── components.json
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
├── templates/
├── static/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── poetry.lock
├── .env.example
├── .gitignore
└── README.md
```

Notes:
- `quickscale.yml` is created during planning and remains the user-owned desired-state file
- `.quickscale/state.yml` and `.quickscale/config.yml` appear after apply writes state and module metadata
- `frontend/` is omitted for the HTML starter when the user selects `showcase_html`

### 3.2 Generated Project with Embedded Modules

```
myapp/
├── .quickscale/
│   ├── state.yml
│   └── config.yml
├── quickscale.yml
├── modules/
│   ├── auth/
│   ├── listings/
│   └── social/
├── manage.py
├── myapp/
│   ├── settings/
│   │   └── base.py
│   └── urls.py
└── ...
```

Notes:
- Embedded modules are runtime dependencies that land in `modules/`
- `quickscale apply` owns the managed backend/runtime wiring for installed modules
- Existing projects keep ownership of user-edited theme routes, navigation, and page files unless documentation for a specific release explicitly says otherwise

### 3.3 Current Simplifications

The generated project intentionally does not include:
- Additional `config/` package trees or schema registries beyond the shipped plan/apply files
- Automatic `backend_extensions.py` generation
- Automatic settings inheritance from `quickscale_core`
- Maintainer-side package workspaces such as `quickscale_modules/` or `quickscale_themes/`

<a id="mvp-prohibitions"></a>
### 3.5 Current Generation Guardrails

When generating or editing a QuickScale-managed project structure, do not introduce:
- `requirements.txt` or `setup.py` in place of Poetry metadata
- A generated `quickscale_modules/` maintainer workspace inside client projects
- Untracked config loaders or alternate desired-state files beyond `quickscale.yml`
- Automatic rewrites of user-owned frontend routes or page files in older generated projects unless a specific released contract requires it
- Unsupported CLI surfaces such as `quickscale validate` or `quickscale generate`
- Automatic settings inheritance from `quickscale_core`

<a id="post-mvp-structure"></a>
## 4. Maintainer and Package Layout Reference

This section is a maintainer-side reference for how the QuickScale repository is organized today. It is not a promise that every path here appears in generated client projects.

### 4.1 Current Maintainer Repository Layout

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
- Starter-theme assets live under `quickscale_core/generator/templates/themes/`
- `quickscale_modules/` is the first-party module workspace used by maintainers
- Package-local READMEs describe local responsibilities, but root docs remain authoritative

### 4.2 Optional Extraction / Personal Monorepo Pattern

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

## 5. Generated Project Output

This section is the detailed reference for what QuickScale currently materializes into a user project.

### 5.1 React Starter Output

`showcase_react` remains the default starter theme.

```
myapp/
├── manage.py
├── quickscale.yml
├── myapp/
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── local.py
│   │   └── production.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── lib/
│   │   ├── pages/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── components.json
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
├── templates/
│   └── index.html
├── static/
│   └── images/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── poetry.lock
├── .env.example
├── .gitignore
└── README.md
```

Notes:
- Fresh `showcase_react` generations include `frontend/src/lib/analytics.ts` as dormant
    PostHog starter wiring. It initializes only when `VITE_POSTHOG_KEY` contains a real
    key.
- Fresh `showcase_react` generations also include
    `frontend/src/pages/SocialLinkTreePublicPage.tsx` and
    `frontend/src/pages/SocialEmbedsPublicPage.tsx`, plus Django `templates/social/*.html`
    wrappers that keep `/social` and `/social/embeds` under Django ownership while
    hydrating the shared React bundle through `window.__QUICKSCALE__.publicPage`.

### 5.2 HTML Starter Output

When the user selects `showcase_html`, the frontend stays server-rendered.

```
myapp/
├── manage.py
├── quickscale.yml
├── myapp/
├── templates/
│   ├── base.html
│   └── index.html
├── static/
│   ├── css/
│   └── images/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── poetry.lock
└── ...
```

### 5.3 State and Module Metadata

When modules are embedded or applies are recorded, QuickScale writes:

```
.quickscale/
├── state.yml   # applied state
└── config.yml  # module metadata for update/push workflows
```

Rules:
- `quickscale.yml` is user-edited desired state
- `.quickscale/state.yml` and `.quickscale/config.yml` are system-managed
- Generated projects remain standalone even when modules are embedded

### 5.4 Optional Manual Inheritance / Extraction Notes

Some advanced users manually embed shared code or keep a personal monorepo. That is separate from the default generated-project contract.

If you intentionally adopt a manual inheritance or extraction pattern:
- keep the generated project usable as standard Django first
- document the git-subtree workflow clearly
- avoid introducing extra generated wrapper commands unless they are actually shipped and documented

## 6. Naming & Import Matrix (Summary)

| Concern | Import Path | Django App Label |
|--------|-------------|------------------|
| Core | `quickscale_core` | `quickscale_core` |
| CLI | `quickscale_cli` | n/a |
| Auth Module | `quickscale_modules.auth` | `quickscale_modules_auth` |
| Listings Module | `quickscale_modules.listings` | `quickscale_modules_listings` |
| Notifications Module | `quickscale_modules.notifications` | `quickscale_modules_notifications` |
| Social Module | `quickscale_modules.social` | `quickscale_modules_social` |
| Storage Module | `quickscale_modules.storage` | `quickscale_modules_storage` |
| React Starter | generated frontend assets | user-owned project code |
| HTML Starter | generated Django templates | user-owned project code |

Rules:
- Dotted import paths map to underscore-qualified Django app labels where needed
- Generated projects should favor standard Django import patterns
- Do not introduce alternate naming systems when the existing package/app-label pattern is sufficient

## 7. Rationale Mapping to Decisions

| Decision Area | Scaffold Effect | Notes |
|---------------|-----------------|-------|
| Standalone generated project | Split settings, user-owned project tree | No automatic core inheritance |
| Plan/apply workflow | `quickscale.yml` plus `.quickscale/*.yml` state files | Current desired/applied state model |
| Module distribution | `modules/` in generated projects, `quickscale_modules/` in maintainer repo | Do not confuse maintainer and generated layouts |
| Theme ownership | One-time copy into project-owned templates and frontend files | Generated theme code is not a live runtime package |
| Poetry packaging | `pyproject.toml` + `poetry.lock` | No `requirements.txt`/`setup.py` fallback |

## 8. Incremental Adoption Notes

QuickScale evolves by extending the current contract, not by redefining the generated-project model each release.

Current progression points:
- Start with a standalone generated project
- Add modules through `quickscale plan --add ...` and `quickscale apply`
- Keep user-owned frontend files user-owned unless a release explicitly documents a managed boundary
- Treat maintainer-side namespace or package-layout notes as repository context, not generated-project requirements

## 9. Crosswalk: Requirement to Artifact

| Requirement | Artifact |
|-------------|----------|
| Desired state | `quickscale.yml` |
| Applied state | `.quickscale/state.yml` |
| Module metadata | `.quickscale/config.yml` |
| Project generation | `quickscale_core/generator/` templates and generator logic |
| Embedded modules | `modules/<name>/` inside the generated project |
| Starter theme assets | project `frontend/`, `templates/`, and `static/` directories |

## 10. Authoring & Maintenance Notes

- Update this document when QuickScale's generated output or maintainer repo layout changes materially
- Keep generated-project examples focused on what ships today
- Push speculative or release-sequencing material into [roadmap.md](./roadmap.md), not this file
- Preserve compatibility anchors when restructuring sections that other docs link to

## 13. E2E Test Infrastructure

**Purpose**: End-to-end testing validates the full QuickScale project lifecycle with real database and browser automation.

**Current structure:**

```
quickscale_core/tests/
├── test_e2e_full_workflow.py
├── docker-compose.test.yml
└── conftest.py
```

Key expectations:
- Use isolated temporary directories for generated-project tests
- Cover generate → install → migrate → serve → browse flows
- Keep E2E separate from the fast default test path
- Validate database, Docker, and browser integration together before release closeout when appropriate

Maintainers: Update this document whenever generated output or repository structure changes. Treat it as the canonical scaffolding reference alongside [decisions.md](./decisions.md).
