# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap**
> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

The next goal is the first useful property portal (SA153) in a project-owned extension, built on
`bap-web` after the verified migration tools move it onto current QuickScale (SA191).
Capabilities are generalized only after that project proves their value.

SA191 is the first QuickScale upgrade of a site holding real production state. That state is
**reseeded, not carried**, so SA204's migration-history freeze waits for SA153's go-live.

**Release status — v0.88.0 packaged, not published.** No core tag, split-branch republication,
seal, or PyPI upload has happened. Publication stays a maintainer decision; this planner tracks only
that it is owed: release-tier validation on the packaged bytes, the phases in
[publish_procedure.md](publish_procedure.md), and the release PR into `main`. The packaged bytes
predate fixes now on `v89` and carry two S1 billing defects: with billing enabled against real
Stripe keys, every webhook and every checkout fails. Shipping any `v89` fix in 0.88.0 means
repackaging.

The scheduling table owns horizon, track, dependencies, and release requirement. Ticket bodies own
context, scope, and acceptance; [CHANGELOG.md](../../CHANGELOG.md) preserves history.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Horizon | Track | Depends on | Release requirement |
|---|---|---|---|---|---|
| SA204 | Freeze module migration history at the vintage `bap-web` lands on | post-v88 | 1 | — | Deferred |
| SA191 | Migrate `bap-web` onto current QuickScale with the fresh-first migration tool | post-v88 | 1 | — | Deferred |
| SA153 | Deliver the first property portal using project-owned extensions | post-v88 | 1 | SA191 | Deferred |
| SA154 | Property-portal capabilities to promote when a project needs them | post-v88 | 1 | SA153 | Inventory only |
| SA211 | Give every contract adoption step a stable identity and derive the watched template set | post-v88 | 2 | — | Deferred |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA191 ──► SA153 ──► SA204 ──► SA154 (inventory)
Track 2: SA211
Track 3: idle
                         critical path: SA191 → SA153
```

Arrows within a track are queue order; the table holds the actual dependency edges.

**Critical path.** SA191 migrates `bap-web` onto current QuickScale, rebuilds and reseeds its
database, and redeploys through `deploy railway`. SA153 builds the portal on it. SA204 freezes
module migration history before any post-SA153 module schema change. SA154 is an inventory, not
work.

**Ordering off the critical path.** SA211 should land before SA191 records the migrated site's
adoption state, and must land before the first release published after 0.89.0.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA191 | yes | yes | yes | **yes** | **yes** |
| 2 | SA211 | yes | yes | yes | **yes** | no |
| 3 | — (idle) | — | — | — | **yes** | no |

### Ownership and merge coordination

- Track 1 owns gate documentation, `scripts/gate_registry.json`, the parity oracles, the hosted
  workflow triggers, the maintainer migration tools with their smoke gate and playbook, the
  migration-history freeze gate and `decisions.md` § Clean-Break Migration History, the `bap-web`
  migration and its reseed step, the property extension, public templates, and the portal's
  extension documentation.
- Track 2 owns `.github/workflows/`, `scripts/publish_module.py`, the `[build-system]` blocks of
  every package, `ruff.toml`, the module page templates
  and test-settings stubs, the generated `base.html`, the CLI apply/deploy/update commands and
  `contract_vintage.py`, the module manifests' `contract_vintage` blocks,
  `contracts/module_options.py` and the `.env.example` template, `quickscale_core/dr_engine/`,
  and the billing module (`billing/services.py`, `billing/views.py`, `billing/adapter.py`, and its
  docs).
- Track 3 owns the orgs tenancy, purge, removal-obligation, and boot path (`orgs/apps.py`,
  `orgs/removal.py`), the privileged-command and runtime-role stations, the
  `quickscale_core.runtime` settings facade, the generated settings templates (`base.py.j2`,
  `production.py.j2`, `local.py.j2`), the generator's Jinja environment, `auth/views.py`, the
  blog rate limiter, and the generated `pyproject.toml.j2` `[build-system]` block.
- **Cross-track edits.** SA211 edits its gate's `scripts/gate_registry.json` row (Track 1) and
  reads Track 3's emission manifest without changing it; the row reconciles with Track 1 at merge.
- One delivery candidate at a time per track, one serialized merge queue into `v89`.
- **Conflict surface.** This roadmap, [CHANGELOG.md](../../CHANGELOG.md), both audits, and
  [decisions.md](decisions.md) (SA204, SA153). Each track resolves the shared set at its
  own merge, after the previous merge lands, then runs the consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

- [ ] **SA204 — Freeze module migration history at the vintage `bap-web` lands on.**

  **Context:** under [decisions.md](decisions.md) § Clean-Break Migration History, each
  model-bearing module ships one `0001_initial` that is rewritten in place every release, and the
  only supported upgrade is a fresh database. Since `bap-web` was generated on 2026-03-05, all ten
  model-bearing modules' `0001_initial` were rewritten two to five times each. Every rewrite adds
  to the hand-written transform each deployed project needs on its next upgrade, and after SA153
  that transform must also assign `organization_id` under FORCE RLS. `bap-web`'s data is
  reseeded, so the freeze is needed only at SA153's go-live, where the first non-reseedable tenant
  data appears; it must land before any module schema change reaches that project. This is a one-way door: once a project applies a frozen `0001`, it can never be
  re-squashed under it (arch audit `clean-break-schema-no-data-path`, option 1).

  **Acceptance:** decisions record that rule 1 of the clean-break decision is lifted from 0.89.0
  onward, the release the freeze lands in. Upgrades from earlier vintages, including 0.88.0,
  stay fresh-database-only. From 0.89.0 on, a schema change to a model-bearing module ships as a
  new incremental migration under the existing migration-quality gates. A registered gate fails
  when an existing migration file of a model-bearing module changes or disappears, with controls
  proving that it rejects an in-place `0001` edit and accepts a new `0002`.

  The gate compares against a checked-in manifest of the frozen files' content hashes, not a git
  ref: no 0.89.0 tag exists yet, and a manifest also works in shallow CI clones. The freeze takes
  effect when SA204 merges, so any later `v89` change to a model-bearing module's models ships as
  a `0002`; confirm before merging that no module schema change shipped between SA191's rebuild
  and this freeze. The
  topology guard in `test_module_migration_topology.py` currently requires exactly one
  `0001_initial` and has a canary that rejects any `0002`; it changes to require a `0001_initial`
  followed by an ordered chain, and that canary is inverted. Fix the freeze release before SA153
  writes its first module-schema change, so that change ships as a `0002` from the start.

  **Surfaces:** decisions, the new gate with its hash manifest, registry row, and gate
  documentation, `quickscale_core/tests/test_module_migration_topology.py`, and the arch audit.

- [ ] **SA191 — Migrate `bap-web` onto current QuickScale with the fresh-first migration tool.**

  Use `make beta-migrate-fresh` with `bap-web` as donor and a fresh scaffold generated with the same
  slug as recipient, continuing manually only where the tool emits `pending_manual_actions`.

  **Context:** `bap-web` is the beta site behind the property portal. It already runs `listings`, `forms`, and a
  project-owned `properties` app with concrete models, a catalog seed command, a public
  `/api/properties/` endpoint, and React property pages. It was generated on an older QuickScale, so
  building the portal on it first requires catching it up to the current release.

  Every point where the tool stops safely becomes a playbook step or a deterministic tool fix.

  Its data cannot move by backup and restore alone. The production database records `listings`
  0001–0003, `forms` 0001–0003, and `auth` 0001–0002 as applied and has no `orgs`. Current
  `listings` and `forms` ship only a rewritten `0001_initial` that depends on `orgs`, and
  `AbstractListing` now carries a NOT NULL organization FK. Running current code on a restored copy
  violates Django's migration-history consistency, and restore refuses it. The database is
  rebuilt and reseeded instead: the catalog through `bap-web`'s own seed command, users by
  re-invitation.

  **Acceptance:** the migrated project records the current QuickScale version in `quickscale.yml`
  and its lock, and passes its own test suite and local verification stack. Its settings import the
  SA206 facade; no QuickScale-owned contract is hand-patched into the donor. The project-owned
  `properties` app, its catalog seed, forms and contact customizations, content, and frontend pages
  carry over and behave as before. Its migrations are regenerated against the current
  `AbstractListing`. `.git`, `media/`, `.env`, and `poetry.lock` are not copied between the two
  trees. Every manual step the tool did not automate is recorded in the migration report and fed
  back into the playbook, or into a tool fix when it is deterministic. The carried `properties`
  models pass SA208's provider-ID system check, which otherwise stops `start.sh` at `migrate`.
  If billing is enabled, the Stripe webhook endpoint is recreated at `2026-06-24.dahlia`.

  The production data is reseeded, not carried. Rehearse first: restore a production dump into a
  scratch PostgreSQL 18 and confirm the expected history inconsistency with `migrate --plan`
  against the recipient; that result is the evidence the old database cannot run current code.
  The cutover rebuilds a fresh database on current code and reseeds the catalog through
  `bap-web`'s own seed command, tenant-scoped to the site's organization under the restricted
  runtime role — not through the privileged `migrate`/`createcachetable` exemption, and never
  under BYPASSRLS; users are re-invited, and form submissions and other transactional rows are
  not carried.
  The pre-cutover database is retained until the reseeded site is verified. The FORCE-RLS table
  and policy counts equal those of a fresh project with the same modules, and
  `check_tenant_isolation` passes. Media is carried over separately and verified.

  The migrated project replaces the old repository and redeploys through `deploy railway`. The
  written rollback restores the previous deploy *and* the retained pre-cutover database, not code
  alone. No property-portal features, frontend stack change, or module-source edits.

  **Surfaces:** the `bap-web` repository and its reseed step; the migration playbook, including its
  data and rollback steps; and, for deterministic gaps found,
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

  This is the first real tenant data on a QuickScale site. From here on, module schema changes
  reach it only as incremental migrations on SA204's frozen history.

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
  rows without a vendored module edit. Every `*_id` field on a property model is classified through
  SA208's project-side declaration, and the SA208 system check passes in the project.

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
  and purge, not on module-source edits, and items that change a module schema ship an incremental
  migration on SA204's frozen history. Close when every item is promoted or dropped with rationale.

- [ ] **SA211 — Give every contract adoption step a stable identity and derive the watched template set.**

  **Context:** every declared adoption step (the project-level declaration and each module's
  `contract_vintage` block) already has a stable id, applied state records adopted ids, and
  `update`, `apply`, and `deploy railway` refuse on exactly the unadopted steps. Three gaps remain:
  SA208's provider-ID classification is not a declared step, a module manifest's step text can
  change without a new id, and the template-change gate watches a hand-listed path set that
  misses `pyproject.toml.j2` and `OPERATIONS.md.j2`.

  **Acceptance:**
  - A declared step covers provider-ID classification, which fails `migrate` on an upgraded
    project with an unclassified `*_id` field.
  - The gate fails when a module manifest's step text changes without a new id, with controls in
    both directions.
  - The template-change gate derives its watched set from the generator's emission manifest. A
    control proves a change to `pyproject.toml.j2` without a step fails.

  **Surfaces:** `project_contract.yml`, the module manifests' `contract_vintage` blocks, the
  `check-project-contract-vintage` gate and its registry row, and the arch audit. The emission
  manifest is read, not changed; Track 3 owns the generator.

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Arch finding `deletion-invariants-per-boundary-reimplementation` is contained until its trigger
fires. Open questions: whether "regenerate and port" is the permanent upgrade model, and whether
`experto-ai-web` migrates too. Standing scope rules, presence contracts, and resource safeguards
live in [decisions](decisions.md) and
[validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
