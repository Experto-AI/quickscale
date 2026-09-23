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
predate fixes now on `v89` (the `.env.example` credential placeholders, backup/restore TLS, and the
account-deletion transaction boundary), and SA202 hardens the workflow that would upload them;
shipping any of those in 0.88.0 means repackaging.

The scheduling table owns horizon, track, dependencies, and release requirement. Ticket bodies own
context, scope, and acceptance; [CHANGELOG.md](../../CHANGELOG.md) preserves history.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Horizon | Track | Depends on | Release requirement |
|---|---|---|---|---|---|
| SA191 | Migrate `bap-web` onto current QuickScale with the fresh-first migration tool | post-v88 | 1 | — | Deferred |
| SA194 | Remove the in-place beta-migration mode | post-v88 | 1 | SA191 | Deferred |
| SA153 | Deliver the first property portal using project-owned extensions | post-v88 | 1 | SA191 | Deferred |
| SA154 | Property-portal capabilities to promote when a project needs them | post-v88 | 1 | SA153 | Inventory only |
| SA202 | Pin the publishing supply chain and add the missing CI scanners | post-v88 | 2 | — | Deferred |
| SA196 | Fail hard on undefined generator template context | post-v88 | 3 | — | Deferred |
| SA201 | Give generated projects one throttling contract | post-v88 | 3 | — | Deferred |
| SA203 | Narrow the privileged-command exemption in the orgs boot path | post-v88 | 3 | — | Deferred |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA191 ──► SA194 ──► SA153 ──► SA154 (inventory)   critical path: SA191 → SA153
Track 2: SA202
Track 3: SA196 ──► SA201 ──► SA203
```

Arrows within a track are queue order; the table holds the actual dependency edges.

**Critical path.** SA191 → SA153. SA191 migrates `bap-web` with the fresh-first mode and
redeploys through `deploy railway`; SA153 builds the portal on the migrated project. SA194 waits
for SA191 so the removal keeps anything the real run needs, and is off the critical path. SA154 is an inventory, not work. Everything else is off the critical path.

**Ordering.** Tracks 2 and 3 carry no dependency edges. SA196 strict rendering touches templates
other tracks own (the `.env.example` template, settings templates, generated `base.html`), so
SA201 re-runs the generator tests and the SA90 emission fixture after SA196 lands.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA191 | yes | yes | yes | **yes** | **yes** |
| 2 | SA202 | yes | yes | yes | **yes** | no |
| 3 | SA196 (in progress) | yes | yes | yes | **yes** | no |

### Ownership and merge coordination

- Track 1 owns gate documentation, `scripts/gate_registry.json`, the parity oracles, the hosted
  workflow triggers, the maintainer migration tools with their smoke gate and playbook, the
  `bap-web` migration, the property extension, public templates, and the portal's extension
  documentation.
- Track 2 owns `.github/workflows/`, `scripts/publish_module.py`, the `[build-system]` blocks of
  every package, `ruff.toml`, the module page templates and test-settings stubs, the generated
  `base.html`, the CLI apply/deploy/update commands, `contracts/module_options.py` and the
  `.env.example` template, and `quickscale_core/dr_engine/`. SA202's new gates add rows to
  `scripts/gate_registry.json`, reconciled with Track 1 at merge.
- Track 3 owns the orgs tenancy, purge, and boot path (`orgs/apps.py`), the privileged-command and
  runtime-role stations, the generated settings templates (`base.py.j2`, `production.py.j2`,
  `local.py.j2`), the generator's Jinja environment, `billing/services.py`, `billing/views.py`,
  `auth/views.py`, and the blog rate limiter.
- One delivery candidate at a time per track, one serialized merge queue into `v89`.
- **Conflict surface.** This roadmap, [CHANGELOG.md](../../CHANGELOG.md), and the tech audit
  (SA196, SA201, SA202, SA203 each edit only their own finding's entry). Each track resolves the
  shared set at its own merge, after the previous merge lands, then runs the consistency test.
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

  The fresh-first mode is the documented primary path: a fresh scaffold with the same slug receives
  the donor's custom content, so infrastructure files start correct instead of being merged. Manual continuation is expected where the tool stops safely; the value of
  this ticket is that every such stop becomes either a playbook step or a deterministic tool fix.

  The migration preserves behavior, including the existing React and JSON API property surface that
  the portal then builds on.

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

- [ ] **SA194 — Remove the in-place beta-migration mode.**

  **Context:** Fresh-first is the only migration path: a fresh scaffold receives the old site's
  custom content, and data moves by backup and restore under the fresh-database rule. Upgrading a
  live project is `quickscale update`/`apply` with contract-vintage adoption steps. In-place mode
  duplicates that upgrade path with a riskier shape (it rewrites the recipient, then halts at the
  vintage gate), and its smoke gate shims the CLI, so it is never observed working.

  **Acceptance:** `beta-migrate-in-place`, the in-place mode, its continuation, and their tests are
  gone; fresh-first behavior is unchanged. The smoke gate covers fresh-first only, and any gate
  registry or parity count it feeds is updated. The playbook, `generated_file_ownership.md`, and
  the `decisions.md` ownership entry describe one migration mode, and `decisions.md` records the
  removal. Before deleting, port anything SA191's real run showed fresh-first lacks.

  **Surfaces:** `quickscale_devtools/.../beta_migration.py`, `scripts/beta_migrate.py`, the
  Makefile targets, `scripts/check_beta_migration_smoke.py`, the migration playbook,
  `generated_file_ownership.md`, and `decisions.md`.

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

  A public read API inside the reusable `listings` module, and generic support requiring no
  project-owned code, belong in the optional inventory until a second consumer justifies them.

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

- [ ] **SA202 — Pin the publishing supply chain and add the missing CI scanners.**

  **Context:** `publish.yml` pins two third-party actions to `@release/v1`, which is a **branch**,
  not a tag: whoever can push to it changes what runs inside the job that holds the OIDC
  trusted-publishing identity. Poetry is installed unpinned in the same workflow, and every package
  in the monorepo declares `requires = ["poetry-core"]` with no upper bound, so the build backend is
  whatever resolves at build time. None of this is exploitable by a defect in this repository; all
  of it is trust extended to something outside it, on the exact path that would upload the release
  the project is currently holding.

  The audit reached no conclusion at all about CVE exposure, because no dependency scanner exists
  to run — that silence is a tooling gap, not a clean result. The same holds for secret scanning:
  the sweep found no committed secret, but that rests on greps. Both belong with the pinning work,
  because they are the same job's hygiene and because a workflow linter is what keeps the pinning
  caught rather than re-derived by the next audit.

  **Acceptance:** every third-party `uses:` in every workflow is pinned to a full commit SHA with
  the human-readable version in a trailing comment; Poetry is installed at a pinned version; every
  package's `[build-system]` declares a bounded `poetry-core` range. A workflow linter (`zizmor` or
  `actionlint`) runs as a registered gate and fails on an unpinned `uses:` ref and on a workflow
  missing a top-level `permissions:`, so the pinning cannot silently regress. Dependency scanning
  (`pip-audit` against `poetry.lock`) and secret scanning run in CI, each as a registered gate with
  its failure policy stated — including whether a new advisory fails the build or files a finding,
  which is decided here rather than left to the tool's default. Ruff's `S` rule set is selected and
  its findings are either fixed or per-line suppressed with a reason; `ASYNC` is selected only if
  the tree has async code to govern, and otherwise recorded as not applicable. The gate registry
  rows and the parity oracles they feed are updated in the same change and reconciled with Track 1
  at merge. Publication behavior is otherwise unchanged; this ticket publishes nothing.

  **Surfaces:** `.github/workflows/` (all four), the `[build-system]` block of every package,
  `ruff.toml`, `scripts/gate_registry.json` and the parity oracles, the publication procedure doc,
  and the tech audit.

- [ ] **SA154 — Property-portal capabilities to promote when a project needs them.**

  Inventory only: generalizing the property API, React pages, or prerender step into reusable
  modules or the theme; React read API and pages for the blog, generic listings, and the CRM
  dashboard; React `auth` and `billing` flows; broader translations; maps/geocoding; saved
  searches, favorites, and alerts; agent/office profiles; syndication; tours/video; paid
  placement; blog/listing cross-links; and PostgreSQL full-text search. Promote an item only with a concrete consumer, bounded acceptance, and
  a fresh dependency and track. Items that add tenant tables (saved searches, favorites, profiles,
  tours) build on marker-derived enrollment and purge, not on module-source edits. Close
  when every item is promoted or dropped with rationale.

  Promote a capability only with a concrete consumer, bounded acceptance criteria, and evidence
  that it improves the working portal. Public API design and generic extension work should follow
  the actual project contracts they need to support.

- [ ] **SA196 — Fail hard on undefined generator template context.**

  **Context:** The generator's Jinja environment uses the default undefined behavior, so a missing
  or renamed context key renders as empty text with no error — confirmed for plain substitution,
  loops, and filters alike. SA189 moved the runtime role's attributes and grant statements out of
  template literals and into context variables, which means a rename now silently emits a role
  creation statement with no `NOSUPERUSER`, no `NOBYPASSRLS`, and no grants. The only thing
  standing between that and a generated project is a content assertion in one test file.

  The rest of the system applies the fail-hard principle to every configuration error, missing
  dependency, and invalid runtime state. The generator's own rendering is the station where it was
  never applied, and SA189 made that station load-bearing for the privilege contract.

  **Acceptance:** the generator's Jinja environment raises on an undefined context key instead of
  emitting empty text, and a regression test renders a template with a missing key and asserts the
  failure. Generation still succeeds for every shipped template and module combination, and the
  emission fixture stays byte-identical; any template that relied on undefined-renders-empty is
  fixed by supplying or removing the key, never by restoring a permissive default. Fixes may reach
  templates other tracks own, and they are in scope here. Additionally close the tech audit's
  generated-project smoke-boot gap: CI generates a project, runs its `start.sh`, and hits
  `/healthcheck/`, so a template regression that survives strict rendering is still caught by the
  artifact refusing to boot. The repo has extensive rendered-template assertions and nothing that
  boots the result, and strict rendering is the half of that gap this ticket already owns.

  **Surfaces:** the generator's Jinja environment, any template rendering an undefined key,
  generator and emission-fixture tests, the CI smoke-boot station, and the tech audit.

- [ ] **SA201 — Give generated projects one throttling contract.**

  **Context:** Rate limiting in this system is per-module folklore. `forms` uses a DRF
  `ScopedRateThrottle`; `blog` hand-rolls a cache-counter limiter with its own IP normalization;
  everything else has nothing. The generated `REST_FRAMEWORK` block defines
  `DEFAULT_PERMISSION_CLASSES` and `NUM_PROXIES` but no `DEFAULT_THROTTLE_CLASSES` or
  `DEFAULT_THROTTLE_RATES`, and no billing view declares `throttle_classes` — so any authenticated
  org owner can POST `/billing/checkout/` in a loop, and each request makes one or two outbound
  Stripe calls. The failure is fleet-wide, not per-tenant: Stripe rate-limit exhaustion takes every
  other tenant's checkout and webhook processing down with it. `production.py.j2` tunes
  `NUM_PROXIES` with a comment explaining it is "so that DRF throttles are enforced consistently",
  which reads as though throttles are configured. They are not.

  `blog`'s limiter has its own two defects. It relies on `cache.add` plus `cache.incr` being
  atomic, which holds on Redis and not on `DatabaseCache` — and production without `REDIS_URL` is a
  configuration the template explicitly supports and `start.sh.j2` provisions a cache table for. In
  that cell concurrent requests read the same counter and write back the same increment, so the
  effective limit is far above the configured one, and the fallback branch has the same
  read-modify-write shape. Separately, its cache key replaces both `":"` and `"."` with `"_"`, so
  an IPv4 address and an IPv6 fragment can normalize into the same bucket — two unrelated clients
  sharing a budget, or one evading it.

  There is a structural obstacle worth naming up front: `base.py.j2` **replaces** the whole
  `REST_FRAMEWORK` dict after `MODULE_SETTINGS`, so a module cannot contribute DRF configuration at
  all, even though the settings-composition system exists to let modules contribute settings. The
  natural fix for the throttle defaults is exactly to make that block composable. The audit records
  the clobber as a watch item precisely because no module ships a `REST_FRAMEWORK` key today; this
  ticket is the one that would make one, so it fires the trigger and owns it.

  **Acceptance:** the generated settings declare `DEFAULT_THROTTLE_CLASSES` and
  `DEFAULT_THROTTLE_RATES` with conservative `user` and `anon` scopes, documented as defaults an
  operator raises; the checkout and billing-portal views carry an explicit tighter `throttle_scope`,
  and a test posts past the rate and asserts a 429. The `REST_FRAMEWORK` composition stops
  clobbering module-supplied DRF configuration — modules merge into it on the same terms as every
  other settings key — and a test proves a module-contributed throttle rate survives composition.
  `blog`'s limiter either requires a backend with atomic `incr` and fails closed on boot when one
  is absent, or moves its counter to a single atomic `UPDATE ... RETURNING`; a regression drives it
  from N threads against a `DatabaseCache`-configured settings module and asserts the observed
  count never exceeds the limit — the runtime confirmation the audit marks this as needing. The
  throttle identity is hashed rather than character-substituted, so no two distinct client
  identifiers share a bucket. The rate defaults must not break legitimate polling clients, and the
  numbers chosen are written down with the reasoning.

  **Surfaces:** the `REST_FRAMEWORK` block and settings composition in `base.py.j2`, the
  `NUM_PROXIES` comment in `production.py.j2`, `billing/views.py`, `blog/views.py` and its cache
  key helper, `forms/throttles.py` if a shared scope absorbs it, the module settings-composition
  tests, and the tech audit.

- [ ] **SA203 — Narrow the privileged-command exemption in the orgs boot path.**

  **Context:** `QuickscaleOrgsConfig.ready()` opens with `if _is_privileged_command(): return`,
  which exits `ready()` entirely and so skips three installations that come after it: the AF9 GUC
  priming wrapper with its `connection_created` signal, the SA70 `pre_delete` last-owner backstop
  receiver, and the SA1.3 tenant-isolation system check registration. The intent — skip the
  BYPASSRLS boot guard during `migrate` — is served by `_check_rls_role()` alone. The asymmetry is
  the tell: the *other* exemption, `QUICKSCALE_ALLOW_BYPASSRLS=1`, returns from inside
  `_check_rls_role` and leaves the rest of `ready()` intact. The block's comment explains why the
  guard is exempted and says nothing about the other three, which reads as a consequence of
  `return` rather than a decision.

  Concretely: a data migration that deletes `OrganizationMembership` rows under
  `QUICKSCALE_PRIVILEGED_COMMAND=migrate` runs with the last-owner invariant unenforced and can
  leave an organization with members and no owner — a state the application's own guard exists to
  prevent and cannot repair afterwards. The priming wrapper's absence is harmless in this window
  because the privileged role bypasses RLS anyway, and `check_tenant_isolation` is invoked
  explicitly by the Makefile, which is what keeps this below the backstop's own severity.

  **Acceptance:** `ready()` skips only `_check_rls_role()` under a privileged command; the priming
  wrapper, the `pre_delete` receiver, and the system check registration install unconditionally. A
  test sets `QUICKSCALE_PRIVILEGED_COMMAND=migrate`, re-runs `ready()`, and asserts the last-owner
  receiver is connected to `pre_delete`. Existing migrations are checked before landing for one
  that legitimately deletes owner memberships — if one exists it gets an explicit, named bypass
  rather than the backstop being weakened. The BYPASSRLS guard's own exemption semantics, the
  `QUICKSCALE_ALLOW_BYPASSRLS` path, and the privileged-command contract test are unchanged.

  **Surfaces:** `orgs/apps.py` `ready()`, the orgs boot tests, and the tech audit.

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
SA202 owns the dependency-scan, secret-scan and workflow-lint gaps, SA196 the generated-project
smoke-boot gap, and SA201 the `REST_FRAMEWORK` clobber watch note. The standing scope rules,
presence contracts, and resource safeguards live in [decisions](decisions.md) and
[validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
