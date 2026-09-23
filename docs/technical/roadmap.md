# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap**
> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

The next goal is the first useful property portal (SA153) in a project-owned extension, built on
`bap-web` after the verified migration tools move it onto current QuickScale (SA191).
Capabilities are generalized only after that project proves their value.

**Release status — v0.88.0 packaged, not published.** No core tag, split-branch republication,
seal, or PyPI upload has happened. Publication stays a maintainer decision; this planner tracks only
that it is owed: release-tier validation on the packaged bytes, the phases in
[publish_procedure.md](publish_procedure.md), and the release PR into `main`. The packaged bytes
predate fixes now on `v89`; shipping any of them in 0.88.0 means repackaging.

The scheduling table owns horizon, track, dependencies, and release requirement. Ticket bodies own
context, scope, and acceptance; [CHANGELOG.md](../../CHANGELOG.md) preserves history.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Horizon | Track | Depends on | Release requirement |
|---|---|---|---|---|---|
| SA191 | Migrate `bap-web` onto current QuickScale with the fresh-first migration tool | post-v88 | 1 | — | Deferred |
| SA153 | Deliver the first property portal using project-owned extensions | post-v88 | 1 | SA191 | Deferred |
| SA154 | Property-portal capabilities to promote when a project needs them | post-v88 | 1 | SA153 | Inventory only |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA191 ──► SA153 ──► SA154 (inventory)   critical path: SA191 → SA153
Track 2: —
Track 3: —
```

Arrows within a track are queue order; the table holds the actual dependency edges.

**Critical path.** SA191 → SA153. SA191 migrates `bap-web` with the fresh-first migration tool and
redeploys through `deploy railway`; SA153 builds the portal on the migrated project. SA154 is an
inventory, not work. Tracks 2 and 3 are empty.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA191 | yes | yes | yes | **yes** | **yes** |
| 2 | — | yes | yes | yes | **yes** | no |
| 3 | — | yes | yes | yes | **yes** | no |

### Ownership and merge coordination

- Track 1 owns gate documentation, `scripts/gate_registry.json`, the parity oracles, the hosted
  workflow triggers, the maintainer migration tools with their smoke gate and playbook, the
  `bap-web` migration, the property extension, public templates, and the portal's extension
  documentation.
- Track 2 owns `.github/workflows/`, `scripts/publish_module.py`, the `[build-system]` blocks of
  every package, `ruff.toml`, the module page templates and test-settings stubs, the generated
  `base.html`, the CLI apply/deploy/update commands, `contracts/module_options.py` and the
  `.env.example` template, and `quickscale_core/dr_engine/`.
- Track 3 owns the orgs tenancy, purge, and boot path (`orgs/apps.py`), the privileged-command and
  runtime-role stations, the generated settings templates (`base.py.j2`, `production.py.j2`,
  `local.py.j2`), the generator's Jinja environment, `billing/services.py`, `billing/views.py`,
  `auth/views.py`, and the blog rate limiter.
- One delivery candidate at a time per track, one serialized merge queue into `v89`.
- **Conflict surface.** This roadmap, [CHANGELOG.md](../../CHANGELOG.md), and the tech audit.
  Each track resolves the shared set at its own merge, after the previous merge lands, then runs
  the consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

- [ ] **SA191 — Migrate `bap-web` onto current QuickScale with the fresh-first migration tool.**

  Use `make beta-migrate-fresh` with `bap-web` as donor and a fresh scaffold generated with the same
  slug as recipient, continuing manually only where the tool emits `pending_manual_actions`.

  **Context:** `bap-web` is the beta site behind the property portal. It already runs `listings`, `forms`, and a
  project-owned `properties` app with concrete models, a catalog seed command, a public
  `/api/properties/` endpoint, and React property pages. It was generated on an older QuickScale, so
  building the portal on it first requires catching it up to the current release.

  Every point where the tool stops safely becomes a playbook step or a deterministic tool fix.

  **Acceptance:** the migrated project records the current QuickScale version in `quickscale.yml`
  and its lock, and passes its own test suite and local verification stack. The project-owned
  `properties` app, its migrations and catalog seed, forms and contact customizations, content,
  and frontend pages carry over and behave as before; `.git`, `media/`, `.env`, and `poetry.lock`
  are not copied between the two trees. Every manual step the tool did not automate is recorded in
  the migration report and fed back into the playbook, or into a tool fix when it is deterministic.
  The migrated project replaces the old repository and deploys, with a written rollback to the
  previous deploy. The production database and media are carried over by a verified backup and
  restore, and listing, form, and user counts match before and after. Redeploy through
  `deploy railway`. No property-portal features,
  frontend stack change, or module-source edits.

  **Surfaces:** the `bap-web` repository; the migration playbook and, for deterministic gaps found,
  `quickscale_devtools/.../beta_migration.py` and its tests.

- [ ] **SA153 — Deliver the first property portal using project-owned extensions.**

  Target `buenosairesproperties.com` with one React public property surface over a project-owned
  JSON read API, using the documented project-owned extension pattern for property models,
  serializers, API views, URLs, and filters. Build on the React pages and `/api/properties/` that
  SA191 carries over instead of replacing them. No Django-rendered property pages, public API in the
  reusable `listings` module, or generic property behavior in every generated project.

  **Context:** `listings` provides `AbstractListing`, but its shipped views, URLs, admin registration, and
  filters target the concrete `Listing`. A property subclass therefore needs a project-owned read
  API, URLs, and filters under the documented [extension contract](module-extension.md).
  Use that extension path to launch `buenosairesproperties.com` and let working project needs
  inform later reusable module changes.

  A client-rendered page gives crawlers and link-preview bots an empty document, so catalog and
  detail pages must be prerendered or server-rendered for Open Graph and indexing. Choosing that
  mechanism adds to the approved frontend stack and needs its decision entry.

  The launch needs property fields and galleries, explicit currency labels, attribute filtering
  and keyword search applied by the API, Spanish public pages, listing-linked inquiries into `crm`,
  and launch SEO including metadata, sitemap, and robots guidance. Currency labels must not imply
  exchange-rate conversion, and Spanish launch coverage does not require translating every
  QuickScale interface.

  Every new child table, including gallery images, must carry its own `organization_id` and RLS
  policy under the child-table decision in [decisions.md](decisions.md). Match the existing
  `test_rls_boundary.py` coverage pattern and verify tenant isolation across the API, the rendered
  pages, and inquiry handling. These tables join the tenant universe through the marker-derived
  classification of SA182, never through edits to the vendored `orgs` source.

  **Acceptance:** first record in decisions that React is the standard frontend for new application
  and public pages; `auth` and `billing` stay Django-rendered on the shared design (SA192); the
  existing module-shipped Django pages (blog, listings, CRM dashboard) stay Django-rendered on that
  design until an SA154 item promotes a React replacement; Django admin stays as shipped. Then the
  `bap-web` project migrated by SA191 serves an organization-scoped React property catalog and
  detail page with ordered image galleries; bedrooms, bathrooms, area, property type, sale/rent,
  and explicitly labeled currency fields; keyword and attribute filters that the API applies
  server-side. Property pages use the React app's visual design and render in Spanish. A listing
  inquiry creates a CRM record with a listing reference. Catalog and detail pages are prerendered or
  server-rendered so a crawler that runs no JavaScript receives the content and Open Graph tags; the
  site has a sitemap and `robots.txt` generated from published listings. The API exposes only
  published listings of the requested organization. Every new tenant-owned child table has its own `organization_id`, forced RLS, and boundary tests,
  and passes the generated project's `check_tenant_isolation` through marker-derived enrollment, with no
  edit under vendored module source. Prove the search → detail → inquiry journey and isolation
  between organizations through both the API and the rendered pages. Correct reusable-module feature
  claims that the module does not provide. Adding a frontend dependency for prerendering follows the
  decisions rule for the approved frontend stack. The marker-derived purge plan covers property
  rows without a vendored module edit.

  **Surfaces:** the project-owned property extension, its API and React pages, and the project's
  prerender build and deploy step; listings/blog/forms/CRM seams only where needed; decisions;
  extension documentation.

- [ ] **SA154 — Property-portal capabilities to promote when a project needs them.**

  Inventory only: generalizing the property API, React pages, or prerender step into reusable
  modules or the theme; React read API and pages for the blog, generic listings, and the CRM
  dashboard; React `auth` and `billing` flows; broader translations; maps/geocoding; saved
  searches, favorites, and alerts; agent/office profiles; syndication; tours/video; paid
  placement; blog/listing cross-links; and PostgreSQL full-text search. Promote an item only with a concrete consumer, bounded acceptance, and
  a fresh dependency and track. Items that add tenant tables build on marker-derived enrollment
  and purge, not on module-source edits. Close when every item is promoted or dropped with rationale.

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
The standing scope
rules, presence contracts, and resource safeguards live in [decisions](decisions.md) and
[validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
