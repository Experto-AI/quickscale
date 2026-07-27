# Generated Project Structure (Authoritative)

> **You are here**: [QuickScale](../../START_HERE.md) -> [Technical](../index.md) -> **Generated Project Structure**
> **Related docs**: [Scaffolding](scaffolding.md) | [Implementation Contract](implementation_contract.md) | [Validation Policy](validation_policy.md)

This companion owns the current generated-project layout, starter-theme output, generated artifact placement, and generation guardrails. [scaffolding.md](./scaffolding.md) remains the structure hub and compatibility-anchor map; [decisions.md](./decisions.md) remains the tie-breaker for policy disputes.

<a id="mvp-structure"></a>
## Current Generated Structure

QuickScale currently generates a standalone Django project with production foundations, a starter theme, and optional embedded modules.

Key rules:
- The generated project is user-owned code.
- `showcase_react` is the sole starter theme; no server-rendered HTML theme is offered.
- Fresh generations include a root `Makefile` with generic `setup`, `lint`, `format`, `test`, `check`, and `ci` entrypoints; frontend-only targets guard on `frontend/package.json`.
- Fresh generations also ship `scripts/lint.sh` as the shared helper surface behind `make lint` and `make check`.
- Fresh `showcase_react` generations auto-scaffold Django-owned public `/social` and `/social/embeds` pages.
- Generated starter output surfaces billing as a module flag only (`modules.billing`); the generated SPA does not currently include billing dashboard cards, sidebar navigation entries, org-dashboard billing cards/links, module paths for billing, or full-document links into billing Django pages (restoring those entry points is separate implementation work, not a blocked item). Teams placeholder routes, navigation, cards, and flags remain excluded.
- Modules embed into the generated project and can later be updated through the documented git-subtree workflow.
- QuickScale does not generate a maintainer-style `quickscale_modules/` workspace inside client projects.

### Base Generated Project

```
myapp/
├── manage.py
├── quickscale.yml
├── Makefile
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
├── scripts/
│   └── lint.sh
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── poetry.lock
├── .env.example
├── .gitignore
└── README.md
```

Notes:
- `quickscale.yml` is created during planning and remains the user-owned desired-state file.
- `.quickscale/state.yml` is the sole authoritative applied-state store after apply writes state. It carries consolidated sub-sections for module-tracking metadata and managed-file drift records. Legacy `.quickscale/config.yml` and `.quickscale/file_hashes.yml` are compatibility inputs only (read-through imported when `state.yml` lacks consolidated sections; ignored when consolidated sections are present). Leftover legacy files may remain on disk as ignored compatibility debris after a successful authoritative save.
- `.quickscale/<name>.lock` advisory lock files serialize concurrent `apply` operations.
- `Makefile` is always generated at the project root and is the preferred local entrypoint for setup, lint, format, test, check, and ci workflows.
- `scripts/lint.sh` is generated alongside the root `Makefile` and backs the shared `make lint` and `make check` workflows.
- Frontend-specific Makefile targets run only when `frontend/package.json` exists.

### Generated Project with Embedded Modules

```
myapp/
├── .quickscale/
│   ├── state.yml
│   └── config.yml
├── quickscale.yml
├── Makefile
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
- Embedded modules are runtime dependencies that land in `modules/`.
- `quickscale apply` owns the managed backend and runtime wiring for installed modules.
- The managed social backend transport remains theme-agnostic, but only fresh `showcase_react` starters auto-scaffold the public `/social` and `/social/embeds` pages.
- Existing projects keep ownership of user-edited theme routes, navigation, and page files unless documentation for a specific release explicitly says otherwise.

### Current Simplifications

The generated project intentionally does not include:
- additional `config/` package trees or schema registries beyond the shipped plan/apply files
- automatic `backend_extensions.py` generation
- automatic settings inheritance from `quickscale_core`
- maintainer-side package workspaces such as `quickscale_modules/` or `quickscale_themes/`

<a id="mvp-prohibitions"></a>
### Current Generation Guardrails

When generating or editing a QuickScale-managed project structure, do not introduce:
- `requirements.txt` or `setup.py` in place of Poetry metadata
- a generated `quickscale_modules/` maintainer workspace inside client projects
- untracked config loaders or alternate desired-state files beyond `quickscale.yml`
- automatic rewrites of user-owned frontend routes or page files in older generated projects unless a specific released contract requires it
- unsupported CLI surfaces such as `quickscale validate` or `quickscale generate`
- automatic settings inheritance from `quickscale_core`

<a id="generated-project-output"></a>
<a id="5-generated-project-output"></a>
## Generated Project Output

This section is the detailed reference for what QuickScale currently materializes into a user project.

### React Starter Output

`showcase_react` remains the default starter theme.

```
myapp/
├── manage.py
├── quickscale.yml
├── Makefile
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
│   ├── public/
│   │   └── favicon.svg
│   ├── components.json
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
├── templates/
│   ├── index.html
│   └── social/
│       ├── embeds.html
│       └── link_tree.html
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── poetry.lock
├── .env.example
├── .gitignore
└── README.md
```

Notes:
- Fresh `showcase_react` generations include `frontend/src/lib/analytics.ts` as dormant PostHog starter wiring. It initializes only when `VITE_POSTHOG_KEY` contains a real key.
- Fresh `showcase_react` generations also include `frontend/src/pages/SocialLinkTreePublicPage.tsx` and `frontend/src/pages/SocialEmbedsPublicPage.tsx`, plus Django `templates/social/*.html` wrappers that keep `/social` and `/social/embeds` under Django ownership while hydrating the shared React bundle through `window.__QUICKSCALE__.publicPage`.
- Fresh `showcase_react` generations surface billing as a module flag only (`modules.billing`). The generated SPA does not currently include billing dashboard cards, sidebar navigation entries, org-dashboard billing cards, module paths for billing, or full-document links into billing Django pages (restoring those entry points is separate implementation work, not a blocked item). QuickScale does not generate a starter-owned `BillingPage.tsx`.
- That public-page scaffolding is fresh-generation-only; existing projects must manually adopt any equivalent public pages they want.

### HTML Starter Output (Removed)

`showcase_react` is the sole supported theme; no server-rendered HTML + CSS theme is offered. Existing generated projects keep their user-owned files — apply performs no automatic rewrite. Any desired/state/recovery reference to `showcase_html` fails closed before operational side effects.

### State and Module Metadata

When modules are embedded or applies are recorded, QuickScale writes:

```
.quickscale/
├── state.yml   # Sole authoritative applied-state store
└── <name>.lock # Advisory lock for concurrent-apply serialization
```

Rules:
- `quickscale.yml` is user-edited desired state.
- `.quickscale/state.yml` is the sole authoritative applied-state store (system-managed). It carries consolidated sub-sections for module-tracking metadata (`prefix`, `branch`, `installed_at`) and managed-file drift records (`managed_files`).
- Legacy `.quickscale/config.yml` and `.quickscale/file_hashes.yml` are compatibility inputs only: read-through imported when `state.yml` lacks consolidated sections, ignored when consolidated sections are present. Leftover legacy files may remain on disk as ignored compatibility debris.
- Generated projects remain standalone even when modules are embedded.

### Optional Manual Inheritance / Extraction Notes

Some advanced users manually embed shared code or keep a personal monorepo. That is separate from the default generated-project contract.

If you intentionally adopt a manual inheritance or extraction pattern:
- keep the generated project usable as standard Django first
- document the git-subtree workflow clearly
- avoid introducing extra generated wrapper commands unless they are actually shipped and documented

## Crosswalk: Requirement to Artifact

| Requirement | Artifact |
|---|---|
| Desired state | `quickscale.yml` |
| Local developer workflow entrypoints | `Makefile` |
| Lint/check helper surface | `scripts/lint.sh` |
| Applied state | `.quickscale/state.yml` (sole authoritative store; consolidated sub-sections for module tracking and managed-file drift) |
| Advisory lock | `.quickscale/<name>.lock` (concurrent-apply serialization) |
| Legacy compatibility inputs | `.quickscale/config.yml`, `.quickscale/file_hashes.yml` (read-through imported when `state.yml` lacks consolidated sections; ignored when present) |
| Project generation | `quickscale_core/generator/` templates and generator logic |
| Embedded modules | `modules/<name>/` inside the generated project |
| Starter theme assets | project `frontend/` and `templates/` directories |
