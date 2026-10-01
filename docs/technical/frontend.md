# Frontend Architecture

> **You are here**: [QuickScale](../../START_HERE.md) → [Docs](../index.md) → **Technical** → Frontend Architecture
> **Related docs**: [Decisions](decisions.md) | [Module Extension Contract](module-extension.md) | [Generated Project Structure](generated_project_structure.md) | [Generated File Ownership](generated_file_ownership.md) | [Organizations](organizations.md) | [Frontend E2E Coverage](../planning/frontend-e2e-coverage.md)

<!--
frontend.md - Frontend Architecture Reference

PURPOSE: Define the Django/React boundary in generated projects: what crosses it,
who owns which surface, and how the static pipeline is wired.

CONTENT GUIDELINES:
- Describe the seam and the contracts, not component-level implementation detail
- Every claim should be traceable to a file in the generator templates or a module
- Record current state honestly, including surfaces that are inconsistent
- decisions.md stays authoritative for technical rules; this document is the
  frontend-specific expansion of them

TARGET AUDIENCE: Contributors changing the theme, the generator's frontend
emission, or a module's user-facing surface
-->

## Scope

This document covers the **frontend of a generated project**: the `showcase_react` theme, the Django templates that host it, module-owned server-rendered surfaces, and the static-asset pipeline that joins them.

It does not cover the QuickScale CLI or the generator's internals except where they determine emitted frontend paths.

---

## The one-sentence architecture

**A generated QuickScale project is a Django application that serves one React SPA at the site root, plus a set of module-owned server-rendered Django surfaces at fixed URL prefixes. The only channel from Django to React is a single injected configuration object.**

Everything below is an expansion of that sentence.

---

## Where the frontend lives

Frontend source lives in the generator as a **theme** and is emitted into the generated project. There is currently exactly one theme, `showcase_react`.

| Repository path | Emitted project path |
| --- | --- |
| `themes/showcase_react/src/` | `frontend/src/` |
| `themes/showcase_react/public/` | `frontend/public/` |
| `themes/showcase_react/e2e/` | `frontend/e2e/` |
| `themes/showcase_react/templates/` | `templates/` (**project template root, not `frontend/`**) |
| `themes/showcase_react/static/` | `static/` |
| `themes/showcase_react/<root files>` | `frontend/` |

This routing is authoritative in `_THEME_DEST_MAP` and `_THEME_SUBDIR_MAP` (`quickscale_core/src/quickscale_core/generator/generator.py`), and is consumed by the SA66 conformance gate. **The theme's `templates/` subdirectory is deliberately re-homed to the project template root** — the Django template loader must find `index.html` and `base.html` as top-level templates, so they cannot sit under `frontend/`.

Theme files are emitted whether or not the theme is "selected"; frontend source emission is no longer gated by theme selection (SA105).

---

## The Django → React seam

### `window.__QUICKSCALE__`

**`window.__QUICKSCALE__` is the only sanctioned channel from Django to React.** React must not learn about server state any other way — no data attributes on `#root`, no additional inline `<script>` payloads, no second global.

This rule is owned by [decisions.md § Frontend Theme Source De-Specialization](decisions.md#frontend-theme-despecialization-dormant-files), which is authoritative: `frontend/src` stays project-agnostic and byte-identical across projects on a theme version, and there is **no second injection mechanism**. The sections below describe how that rule is implemented, not a separate policy.

It is written by `templates/index.html.j2` and carries:

| Field | Meaning |
| --- | --- |
| `projectName` | Display name |
| `modules` | Boolean flag per module: `true` only when the module is installed and its `QUICKSCALE_<MODULE>_ENABLED` is on |
| `modulePaths` | Server-resolved base paths for `crm`, `social`, `analytics` |

[decisions.md § Module Conventions](decisions.md#module-conventions) rule 31 (SA219) changes how
the producer fills `modules` and `modulePaths`: a flag is `true` only when the module is installed
and its `QUICKSCALE_<MODULE>_ENABLED` is on, and paths come from `{% url %}`, not literals. Every
shipped module flag now requires installed-and-enabled, and the public social producers
(`templates/social/link_tree.html.j2`, `templates/social/embeds.html.j2`) and the shared
navigation apply the same installed-and-enabled social condition before hydrating or linking. The
`modulePaths` rework to `{% url %}` and the discovery-rendered producer D34 option A describes
remain open until SA215 enforces rule 31. The three-place rule below is unchanged.
| `owner.mode` | `"solo"` or `"saas"` — see [organizations.md](organizations.md) |
| `owner.currentOrgSlug` | Current org slug, or `null` |
| `publicPage` | Optional; present only on public non-SPA social surfaces |

### The validator is the contract

`frontend/src/lib/validateQuickScaleSeam.ts` validates the seam and **throws on anything missing or malformed** rather than defaulting. Every load-bearing read goes through it, so a broken seam produces one diagnostic error instead of a silently blank or half-disabled UI.

**Rules for changing the seam:**

1. A new field is added in **three** places together: `index.html.j2` (producer), `hooks/useModules.ts` (type), `lib/validateQuickScaleSeam.ts` (validator). A field added to fewer than all three is a defect.
2. Required fields fail hard. Optional fields are validated strictly *when present* (see `publicPage`).
3. `modules` keys are checked as **own** boolean properties, so a prototype-inherited or string-typed value is rejected, not coerced.
4. Do not read `window.__QUICKSCALE__` directly. Go through `useProjectConfig()` / `useModules()` / `useOwnerMode()` / `useCurrentOrgSlug()`.

### React → Django

The return path is plain `fetch` against same-origin DRF endpoints, wrapped by `hooks/useApi.ts` (TanStack Query for caching, `ApiError` for typed failures, `getApiFieldErrors` for DRF validation payloads). CSRF is read from the `<meta name="csrf-token">` tag emitted by `index.html.j2` and attached as `X-CSRFToken` on every non-GET/HEAD request (`lib/csrf.ts`).

There is no token auth and no separate API origin. Session cookies plus CSRF is the whole authentication story for the SPA.

---

## URL ownership

The generated `urls.py` establishes precedence. Order matters and is the actual specification of who owns what:

1. `healthcheck/`, `admin/`
2. **React shell patterns** — `/`, and the reserved `^orgs...`, `^(profile|blog|listings|crm|settings)/?$`, `^forms/?$`, `^forms/<slug>/?$` routes
3. `PRE_HOME_MODULE_URLPATTERNS`
4. Public social surfaces — `^social/?$`, `^social/embeds/?$`
5. `POST_HOME_MODULE_URLPATTERNS`
6. **React SPA catch-all** — `re_path(r".*", react_shell_view)`

Consequences worth internalising:

- The shell patterns at step 2 are **anchored and shallow** (`/blog` exactly). Deeper module paths such as `/blog/post/<slug>/` fall through to the module at step 5. This is why a project can have both a React "Blog" page and a server-rendered blog index — they are different URLs, by design.
- The catch-all at step 6 means **404s from unmatched paths render the SPA**, not `handler404`. `custom_404_view` fires only for explicit `Http404` raises inside a matched view.
- **`PRE_HOME` vs `POST_HOME` is how a module takes a URL away from the shell.** Modules declare this through `pre_home_url_includes` / `url_includes` on their wiring spec (`quickscale_core/src/quickscale_core/module_wiring.py`). The only current user is `orgs`: in **solo** mode it registers pre-home so Django owns `/orgs*`; in **saas** mode it registers post-home so the React org pages win (`quickscale_modules/orgs/module.yml`).
- `/orgs*` shell routes are served by `orgs_react_shell_view`, which is `@login_required`. Anonymous users are redirected by Django rather than hydrating an SPA that would immediately fail.

---

## The static pipeline

This chain is load-bearing and is currently held together by convention:

```
development: frontend/src/index.css ──Vite :5173──▶ /static/frontend/src/index.css

production:  frontend/ ──vite build──▶ static/frontend/assets/{index.js,index.css}
                                           │
                                 STATICFILES_DIRS = [BASE_DIR / "static"]
                                           │
                                    collectstatic ──▶ staticfiles/
                                           │
                      {% static 'frontend/assets/index.{js,css}' %} in templates
```

Contract points, all of which must move together:

- `vite.config.ts` sets `base: '/static/frontend/'` and `outDir: '../static/frontend'` — matching `STATIC_URL = "/static/"` and `STATICFILES_DIRS = [BASE_DIR / "static"]` in the generated `settings/base.py`.
- `entryFileNames` / `chunkFileNames` / `assetFileNames` are pinned to **unhashed, stable names** (`assets/[name].js`) specifically so Django templates can hard-reference them. In non-DEBUG deployments, the React host and `base.html` load compiled `index.css`; in DEBUG both load `/static/frontend/src/index.css` directly from Vite so one token edit reaches both rendering systems. `index.html` continues to load the compiled JavaScript entry in both modes. `manifest: true` is emitted but **not currently consumed by Django**; the production templates reference filenames directly.
- **Therefore: do not enable content hashing in the Vite output without first switching the templates to a manifest-driven tag.** Hashed filenames silently break `{% static %}` references.
- `manualChunks` splits vendor code into `analytics` / `router` / `ui` / `data` / `react-vendor` / `vendor`. Chunks are lazily fetched by the browser; only the entry names are referenced from Django.

In development, Vite listens on `:5173`, serves the shared token source at `/static/frontend/src/index.css` under its configured base path, and proxies the Django-owned prefixes (`/admin`, `/accounts`, `/blog`, `/listings`, `/crm`, `/social`, Django-owned `/static` paths outside `/static/frontend/`, `/healthcheck`, `/markdownx`, `/_quickscale`) to `:8000`. Native Vite startup uses `strictPort`, so an occupied port 5173 fails explicitly rather than silently moving away from Django's stylesheet URL. Compose can publish that internal Vite port on a different browser-facing port through `QUICKSCALE_FRONTEND_HOST_PORT`, which must be a canonical decimal from 1 through 65535; `QUICKSCALE_FRONTEND_ORIGIN` supplies a canonical full browser-visible origin for remote hosts or HTTPS tunnels. When the full origin is blank, Django and Vite both derive `http://localhost:<QUICKSCALE_FRONTEND_HOST_PORT>`. The server always rejects a missing Host, and a pre-internal Vite guard rejects HTTP and WebSocket requests whose Host differs from that effective origin's exact host, including localhost and IP values that Vite otherwise permits automatically. Compose passes both values to Vite and Django and sends the effective Host in its health check so every DEBUG host renders and accepts the same URL. Run `pnpm dev` alongside the DEBUG Django server; open the application through Django because the standalone Vite HTML does not carry the Django-injected runtime seam. A built stylesheet is not used in DEBUG. **This proxy list is a duplicate of the URL-ownership table above** — a new server-rendered module prefix must be added here too, or it will 404 under `pnpm dev` while working in production.

---

## Templates: four distinct jobs

`templates/` in a generated project is not one thing. Four populations coexist, and conflating them is the most common source of confusion:

| # | Job | Source | Notes |
| --- | --- | --- | --- |
| 1 | **SPA host** | theme `templates/index.html.j2` → `templates/index.html` | Injects the seam; serves `#root`. Contains no application markup. |
| 2 | **Server-rendered shell** | theme `templates/base.html.j2` → `templates/base.html` | A full standalone page shell whose `.qs-*` CSS consumes the Vite-served token source in DEBUG and compiled React tokens otherwise. Used by modules that extend it. Not used by the SPA. |
| 3 | **Project chrome** | generator `templates/`, `common/templates/` | `404.html`, `500.html`, Django admin overrides. |
| 4 | **Module surfaces** | `quickscale_modules/<name>/.../templates/` | Server-rendered module UI and notification email bodies. Found via `APP_DIRS: True`. |

Populations 1 and 2 are **generated project files the user owns** and may edit freely ([generated_file_ownership.md](generated_file_ownership.md)). Population 4 is module-owned and updateable; users customise it by template override, which means the override stops receiving upstream fixes ([module-extension.md](module-extension.md)).

Context processors `project_settings` and `installed_modules` expose `settings` and a resolved `modules.billing.url` to every template. `settings` in a template is how `index.html.j2` derives the `modules` flags, and how `base.html.j2` conditionally renders social nav links.

---

## Styling ownership

There is one project-owned token source with two rendering systems. Tailwind plus shadcn/ui conventions define HSL custom properties on `:root` in `frontend/src/index.css` (`--background`, `--primary`, `--border`, `--radius`, chart and sidebar ramps). The generated React host and `base.html` both load that source from Vite while DEBUG is enabled and load compiled `static/frontend/assets/index.css` otherwise. React consumes the properties through `tailwind.config.js`; shell CSS plus module styles consume them through `hsl(var(--token))`. Dark mode remains class-based, with `base.html` restoring React's persisted light/dark class before either stylesheet loads. React primitives live in `src/components/ui/`; Django modules provide ordinary CSS components without assuming Tailwind utility classes are emitted for module templates.

Current server-rendered surfaces:

| Surface | Styling |
| --- | --- |
| `auth` | Extends `base.html` through `quickscale_auth/base.html`, adds token-based `quickscale_auth/css/auth.css` via `{{ block.super }}` — **the reference pattern** |
| `billing` | Extends `base.html` through `quickscale_billing/base.html`; all pricing, dashboard, checkout-return, and portal-return pages use token-based `quickscale_billing/css/billing.css` |
| `blog` | Extends `base.html` through `quickscale_blog/base.html`; content-only `quickscale_blog/css/blog.css`; children fill `{% block blog_content %}` |
| `listings` | Extends `base.html` through `quickscale_listings/base.html`; content-only `quickscale_listings/css/listings.css`; children fill `{% block listings_content %}` |
| `crm` | Extends `base.html` through `quickscale_crm/base.html`; content-only `quickscale_crm/css/crm.css`; children fill `{% block crm_content %}` |
| `orgs` | Extends `base.html` through `quickscale_orgs/base.html`; children fill `{% block orgs_content %}` |
| `analytics` | Extends `base.html` through `quickscale_analytics/base.html`; children fill `{% block analytics_content %}` |
| `forms` | Extends `base.html` through `quickscale_forms/base.html`; children fill `{% block forms_content %}` |
| `backups` | Operator pages use the Django admin shell and the `admin/` template exception; outside the module page contract |
| `notifications` | Email bodies under `templates/quickscale_notifications/email/` — intentionally self-contained; email clients require inlined styles |

**Every module page — auth, billing, blog, listings, CRM, orgs, analytics, and forms — extends
`base.html` through one flat module base.** The shell — reset, `body`, topbar, `<main>`, messages,
footer, link colour — is defined once for those surfaces and never restated by them. Admin-owned
backups pages follow the Django admin shell and the `admin/` template exception instead.

The pattern, established by `auth` and now used by `billing`, `blog`, `listings`, and `crm`:

```django
{% extends "base.html" %}
{% load static %}

{% block extra_css %}
{{ block.super }}
<link rel="stylesheet" href="{% static 'quickscale_<name>/css/<name>.css' %}">
{% endblock %}

{% block content %}
{% include "quickscale_orgs/_debug_banner.html" %}
<nav class="<name>-nav">…</nav>

<div class="<name>-content">
{% block <name>_content %}{% endblock %}
</div>
{% endblock %}
```

Two constraints make this work:

1. **The module base occupies `{% block content %}`, so child templates fill a module-specific block** (`auth_content`, `billing_content`, `blog_content`, `listings_content`, `crm_content`, `orgs_content`, `analytics_content`, `forms_content`) rather than `content`.
2. **Only blocks that `base.html` already defines may be used** — `title`, `extra_css`, `content`, `extra_js`. `templates/base.html` is user-owned **category U3** ([generated_file_ownership.md](generated_file_ownership.md)) and is never rewritten by `quickscale update` ([user_manual.md](user_manual.md#what-quickscale-update-changes-and-what-stays-yours)), so a module template that depends on a *new* block would silently render nothing on any already-generated project — Django ignores a child block the parent does not define. The generated-file ownership rules therefore require the existing block contract rather than a new frozen project-file dependency.
3. **The module base wraps the child block in a `<div class="<name>-content">`.** `base.html` applies a `*, *::before, *::after { margin: 0; padding: 0 }` reset, so module content written as plain semantic HTML (`<article>`, `<h1>`, `<p>`) has **no default spacing**. The wrapper gives the module stylesheet a scope to restore its own vertical rhythm without leaking rules into the shell or other modules. `auth` uses `.auth-container` / `.auth-main` for the same purpose.

A module stylesheet therefore contains **content styling only** and reads the project tokens instead of declaring colors or radii. If a rule would style the page shell, it belongs in `base.html`, not in the module. This is the split [user_manual.md](user_manual.md#what-quickscale-update-changes-and-what-stays-yours) already promises project owners: *change the look — colors, fonts, header — through the project token source and `base.html`, and leave each page's own styling to the module so updates keep delivering it.*

The authoritative statement of both rules is [decisions.md § Module Implementation Requirements](decisions.md#module-implementation-checklist).

---

## Module frontend surfaces

Modules are pluggable on the backend and **hard-wired on the frontend**. No module ships TSX. All SPA pages for module surfaces live in the theme (`src/pages/BlogPage.tsx`, `CrmPage.tsx`, `ListingsPage.tsx`, `FormsPage.tsx`, `src/pages/orgs/*`), and the module name list is duplicated in `index.html.j2`, `useModules.ts`, and `validateQuickScaleSeam.ts`.

Adding a module with a React surface therefore touches the theme. That is the current design, consistent with [module-extension.md](module-extension.md)'s "Theme/frontend → user-owned generated code" classification: modules own backend contracts, the theme owns presentation.

SPA module pages are marked `// DORMANT:` at the top of the file and are inert unless their `modules.<name>` flag is true. They are `React.lazy`-loaded and tree-shaken when unused, so a dormant page costs nothing in a project that does not install that module. Keep the marker comment when adding one.

Each module surface is in one of three states, and **this is the most important thing to know before working on a module's UI**:

| State | Meaning | Examples |
| --- | --- | --- |
| **API-backed SPA** | React page reads the module's DRF endpoints and renders the real UI | `crm` (`/crm/api/` via `useApiData`), `forms` (`/forms/api/<slug>/`), `orgs` (saas mode) |
| **Launcher** | React page is a description and a set of links out to the server-rendered surface and Django admin | `blog`, `listings` |
| **Server-only** | No SPA page; Django templates are the whole UI | `billing`, `auth`, `orgs` (solo mode), `backups` |

`blog` and `listings` consequently have two user-facing presentations for different jobs, while both now read the same project design tokens.

### Public non-SPA React surfaces

`social` is the one surface where React is mounted **outside** the SPA router. `templates/social/link_tree.html.j2` and `templates/social/embeds.html.j2` are separate Django-rendered pages that mount React via `renderQuickScaleRoot(surface)`. Given a `surface` argument and `modules.social`, the root renderer bypasses `BrowserRouter` entirely and lazy-renders a single public page. This is the mechanism to reuse for any future publicly-addressable, server-routed React surface.

---

## Testing

| Layer | Tool | Location |
| --- | --- | --- |
| Unit / component | Vitest + Testing Library | `frontend/src/test/` |
| Seam contract | Vitest | `src/test/validateQuickScaleSeam.test.ts` |
| Root dispatch | Vitest | `src/test/RootDispatch.test.tsx` |
| Browser E2E | Playwright | `frontend/e2e/` |
| Lint / types | ESLint + `tsc --noEmit` | `pnpm lint:all` |

`scripts/lint_frontend.sh` and `scripts/frontend_proof.sh` drive the repository-side checks against rendered theme output. Coverage status and gaps are tracked in [frontend-e2e-coverage.md](../planning/frontend-e2e-coverage.md).

---

## Rules of thumb

1. **Django owns data and authorization. React owns presentation and navigation within the SPA.** No business rule lives only in TypeScript.
2. **One seam.** New server state reaches React through `window.__QUICKSCALE__`, validated, or through a DRF endpoint. Nothing else.
3. **A new URL prefix is a four-place change**: the module's URL wiring, the Vite dev proxy, the shell-pattern list if the SPA should own it, and this document.
4. **A new server-rendered module surface extends `base.html` through one flat `templates/quickscale_<module>/base.html`.** Do not emit a standalone document or fill the project's `content` block directly.
5. **New SPA UI uses `src/components/ui/` primitives and the `index.css` tokens.** Do not add ad-hoc CSS to the SPA.
6. **Do not hash Vite output filenames** unless the Django templates are switched to the manifest first.
7. **Module frontend pages live in the theme, not in the module**, and are marked `DORMANT` with a lazy import.

---

## Known gaps

Recorded so they are not rediscovered as surprises. None of these are settled decisions; they are the current state.

- **Two presentations for one module.** `blog` and `listings` have both a React launcher page and a server-rendered UI, even though they now share design tokens.
- **Module name list duplicated in three files** (`index.html.j2`, `useModules.ts`, `validateQuickScaleSeam.ts`), with no gate binding them together. Module Conventions rules 31 and 37 remove the `index.html.j2` copy (it is rendered from discovery, SA219); the two TypeScript copies stay by design.
- **Vite dev proxy duplicates the URL-ownership table** with no gate binding them together.
- **`manifest: true` is emitted but unused**, leaving the unhashed-filename convention as the only thing keeping `{% static %}` references valid.
- **Theme frontend internals are explicitly out of scope** for [arch-audit.md](../others/arch-audit.md), so none of the above appears in the structural findings.
