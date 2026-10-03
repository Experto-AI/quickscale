# bap-web one-off migration prompt (SA191)

Hand everything below the line to a coding assistant, started in `/home/victor/code/bap-web-new`.
This is a one-off, prompt-driven migration; the fresh-first tool (SA214) is not used for it.

**SA215 has landed; the port stays parked until its remaining dependencies (SA235–SA238) land.**
SA215 renamed module settings, app labels, URL
namespaces, and commands ([decisions.md § Module Conventions](../technical/decisions.md#module-conventions)).
SA215 also moved module back offices (blog, listings, crm, forms) from `is_staff` to org roles
(rule 19), so the port gives `bap-web`'s editors an org role (`admin` or as the module README
states), never `is_staff`. Start it only after the
[schedule](../technical/roadmap.md#scheduling-table) clears SA235–SA238, regenerate `bap-web-new`
from that checkout, and update the version numbers below; the current `bap-web-new` was generated
before the renames.

---

You are migrating the QuickScale beta site `bap-web` onto current QuickScale (v0.89.0, unreleased,
from the `v89` checkout at `/home/victor/code/quickscale`).

## Trees

| Role | Path | Access |
|---|---|---|
| Donor (old site, generated 2026-03-05 on v0.62.0) | `/home/victor/code/bap-web` | **read-only** — never write, run migrations, or install into it |
| Recipient (fresh `quickscale plan` + `apply` of v0.89.0) | `/home/victor/code/bap-web-new` | yours to edit |
| QuickScale source | `/home/victor/code/quickscale` | read-only reference; report needed upstream changes, don't make them |

The recipient was generated with slug `bap-web`, package `bap_web`, theme `showcase_react`, and
modules `auth`, `forms`, `listings`, `orgs`, `notifications`, embedded from the published
`splits/<module>-module` branches. Before you start: if `git status` shows uncommitted `apply`
output, commit it as `Baseline: quickscale apply v0.89.0`, and run `poetry install` (the `.venv`
was removed after a move). Commit after each numbered step below so every step is reviewable.

## What to carry over

Diff donor against recipient and carry only what the donor added or changed on purpose. Where a
recipient file is newer QuickScale scaffolding, keep the recipient's version and re-apply the
donor's customization on top.

1. **`properties` app** (`bap-web/properties/`): models on `AbstractListing`, admin, serializers,
   views, URLs, pagination, `catalog.py`, `data/`, and the `properties_seed_catalog` command.
   Register and URL-mount it through project-owned files (`bap_web/urls.py`, project settings),
   never by editing QuickScale-managed wiring (`settings/modules.py`, `urls_modules.py`).
   **Delete and regenerate its migrations** against the current `AbstractListing`
   (`makemigrations properties`); do not copy donor migrations `0001`/`0002`. Carry
   `bap_web/public_listings.py` and the donor's `tests/properties/`.
2. **Other project package files**: `bap_web/views.py`, `bap_web/context_processors.py`,
   `bap_web/urls.py` customizations, `bap_web/settings/ci.py`, and any real change in
   `settings/base.py`/`local.py` (diff each; ignore scaffold drift).
3. **`settings/production.py`**: keep the recipient's generated, facade-based file (it calls
   `quickscale_core.runtime.settings.resolve_runtime_database_url`). Port only the donor's
   deploy-specific values onto it — notably the `ALLOWED_HOSTS` domains
   (`buenosairesproperties.com`, `buenosaires.properties`, their `www.` and wildcard forms). Do not
   bring back the donor's inline `DATABASES` block or its unconditional `SECURE_PROXY_SSL_HEADER`.
4. **Frontend**: `App.tsx` routes, `pages/`, every `components/` subfolder (`home`, `layout`,
   `properties`, `seo`, `shared`, **and `ui`**), `assets/`, `data/`, `hooks/` (merge with the
   recipient's `useModules.ts`; keep the recipient's), `lib/`, `stores/`, `types/`, `test/`,
   `index.css` design tokens, `tailwind.config.js`, `components.json`, `public/` brand assets, and
   the donor's Vitest and Playwright specs and configs. Merge donor-added `package.json`
   dependencies into the recipient's; report every version conflict instead of silently picking one.
   Read the donor's `docs/design-system.md` and `docs/frontend-architecture.md` first.
5. **Templates and static**: donor `templates/` overrides and `static/` sources. Never `staticfiles/`.
6. **`modules/forms` edits**: compare donor `modules/forms` against its upstream (donor
   `git log -- modules/forms` and the recipient's fresh `modules/forms`). The recipient must end
   with **no edits under any `modules/` directory**. Re-express each customization as project-owned
   configuration, templates, or extension code. If one is generic and cannot be expressed that way,
   stop and list it under "Upstream candidates" in your report instead of patching the module.
7. **Project docs and tooling** worth keeping (`docs/`, `adaptive.yml`, `adaptive.rules.md`,
   `Makefile` targets the donor added). Skip `roadmap.md`, `properties-plan.md`, `formularios.md`
   unless still relevant — say which you skipped.

## Hard constraints

- Never write to the donor or to the QuickScale source.
- Never copy `.git`, `media/`, `.env`, `poetry.lock`, `pnpm-lock.yaml`, `node_modules/`,
  `.venv/`, `htmlcov/`, `coverage*`, `playwright-report/`, `test-results/`, `staticfiles/`, or
  `__pycache__/` between trees. Regenerate locks in the recipient.
- Do not hand-patch QuickScale-owned files: the vendored `modules/*`, `settings/modules.py`,
  `urls_modules.py`, `start.sh`, `Dockerfile`, `.quickscale/`. If a carry-over seems to need one,
  stop and report it.
- Do not change the frontend stack or add property-portal features (that is SA153).
- Keep billing disabled. Never use BYPASSRLS for app data; seed under the restricted runtime role.
- No data migration: the production database is rebuilt, not carried (see "Out of scope").

## Done criteria

Run each and include the output summary in your report:

1. `poetry install`, `poetry lock --check` (or the equivalent), `pnpm install`, `pnpm build` pass.
2. `poetry run python manage.py migrate` on a fresh local PostgreSQL succeeds; `makemigrations
   --check` reports no changes.
3. The donor's pytest suite, carried into the recipient, passes: `poetry run pytest`. A donor test
   that asserts the v0.62 layout (`tests/test_project_infrastructure.py`) may be adapted or
   excluded, with the reason written in your report.
4. The donor's Vitest suite passes in the recipient: `pnpm test`.
5. The donor's Playwright specs pass against the local recipient (`e2e/forms.live.spec.ts`
   targets the live site; exclude it locally and say so).
6. `poetry run python manage.py check` passes, including SA208's provider-ID check on the
   `properties` models; `check_tenant_isolation` passes; the FORCE-RLS table and policy counts equal
   a fresh project's with the same modules.
7. The catalog seeds through `properties_seed_catalog`, scoped to a local site organization
   (create it with `quickscale_orgs_create_site_org <slug> <name>`, delivered by SA240 before this
   port), under the restricted runtime role, and the home, catalog, detail, and contact pages render locally with
   the donor's design.
8. `git diff <baseline commit> -- modules/` is empty (no vendored edits).

## Report

End with: what was carried (per step above), what was skipped and why, every adapted or excluded
test with its reason, dependency conflicts and how you resolved them, upstream candidates for
QuickScale, and anything left undone.

## Out of scope (maintainer, later)

The production dump rehearsal, creating the new repository, Railway cutover, media transfer, re-inviting users,
live-site screenshot parity, and archiving the old repository.
