# Generated Project Structure (Authoritative)

> **You are here**: [QuickScale](../../START_HERE.md) -> [Technical](../index.md) -> **Generated Project Structure**
> **Related docs**: [Scaffolding](scaffolding.md) | [Implementation Contract](implementation_contract.md) | [Validation Policy](validation_policy.md)

This companion owns the current generated-project layout, starter-theme output, generated artifact placement, and generation guardrails. [scaffolding.md](./scaffolding.md) remains the structure hub and compatibility-anchor map; [decisions.md](./decisions.md) remains the tie-breaker for policy disputes.

<a id="mvp-structure"></a>
## Current Generated Structure

QuickScale currently generates a standalone Django project with production foundations, a starter theme, and optional embedded modules.

Key rules:
- The generated project is user-owned code.
- `showcase_react` is the default starter theme.
- `showcase_html` remains the secondary starter option.
- Fresh `showcase_react` generations auto-scaffold Django-owned public `/social` and `/social/embeds` pages; `showcase_html` does not scaffold those public pages in v0.83.0.
- Generated starter output excludes billing and teams placeholder routes, navigation, cards, and flags until those modules ship.
- Modules embed into the generated project and can later be updated through the documented git-subtree workflow.
- QuickScale does not generate a maintainer-style `quickscale_modules/` workspace inside client projects.

### Base Generated Project

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
- `quickscale.yml` is created during planning and remains the user-owned desired-state file.
- `.quickscale/state.yml` and `.quickscale/config.yml` appear after apply writes state and module metadata.
- `frontend/` is omitted for the HTML starter when the user selects `showcase_html`.

### Generated Project with Embedded Modules

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
- Embedded modules are runtime dependencies that land in `modules/`.
- `quickscale apply` owns the managed backend and runtime wiring for installed modules.
- The managed social backend transport remains theme-agnostic, but only fresh `showcase_react` starters auto-scaffold the public `/social` and `/social/embeds` pages; non-React themes keep manual adoption for any equivalent public pages.
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
│   ├── index.html
│   └── social/
│       ├── embeds.html
│       └── link_tree.html
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
- Fresh `showcase_react` generations include `frontend/src/lib/analytics.ts` as dormant PostHog starter wiring. It initializes only when `VITE_POSTHOG_KEY` contains a real key.
- Fresh `showcase_react` generations also include `frontend/src/pages/SocialLinkTreePublicPage.tsx` and `frontend/src/pages/SocialEmbedsPublicPage.tsx`, plus Django `templates/social/*.html` wrappers that keep `/social` and `/social/embeds` under Django ownership while hydrating the shared React bundle through `window.__QUICKSCALE__.publicPage`.
- That public-page scaffolding is fresh-generation-only; existing projects and non-React themes must manually adopt any equivalent public pages they want.

### HTML Starter Output

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

Notes:
- Fresh `showcase_html` generations do not scaffold Django-owned public `/social` or `/social/embeds` pages in v0.83.0.
- Enabling the `social` module still wires the backend-managed transport surface, but non-React themes must manually adopt any public page surface they want.

### State and Module Metadata

When modules are embedded or applies are recorded, QuickScale writes:

```
.quickscale/
├── state.yml   # applied state
└── config.yml  # module metadata for update and push workflows
```

Rules:
- `quickscale.yml` is user-edited desired state.
- `.quickscale/state.yml` and `.quickscale/config.yml` are system-managed.
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
| Applied state | `.quickscale/state.yml` |
| Module metadata | `.quickscale/config.yml` |
| Project generation | `quickscale_core/generator/` templates and generator logic |
| Embedded modules | `modules/<name>/` inside the generated project |
| Starter theme assets | project `frontend/`, `templates/`, and `static/` directories |
