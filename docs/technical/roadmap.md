# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap**
> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

The next goal is the first useful property portal (SA153) in a project-owned extension, built on
`bap-web` after the verified migration tools move it onto current QuickScale (SA191).
Capabilities are generalized only after that project proves their value.

SA191 is the first QuickScale upgrade that carries real production state, and the 2026-09-23
audits found three things it needs first: a frozen module migration history to land on (SA204),
a restore that refuses a schema its code cannot read (SA205, closed on v89), and runtime contracts
that ship as library code instead of being hand-patched into the donor's settings (SA206).

**Release status — v0.88.0 packaged, not published.** No core tag, split-branch republication,
seal, or PyPI upload has happened. Publication stays a maintainer decision; this planner tracks only
that it is owed: release-tier validation on the packaged bytes, the phases in
[publish_procedure.md](publish_procedure.md), and the release PR into `main`. The packaged bytes
predate fixes now on `v89`; shipping any of them in 0.88.0 means repackaging. They also carry both
S1 billing defects that SA209 fixes: with billing enabled against real Stripe keys, every webhook
and every checkout fails.

The scheduling table owns horizon, track, dependencies, and release requirement. Ticket bodies own
context, scope, and acceptance; [CHANGELOG.md](../../CHANGELOG.md) preserves history.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Horizon | Track | Depends on | Release requirement |
|---|---|---|---|---|---|
| SA204 | Freeze module migration history at the vintage `bap-web` lands on | post-v88 | 1 | — | Deferred |
| SA206 | Move code-shaped runtime contracts from the settings templates into `quickscale_core.runtime` | post-v88 | 3 | — | Deferred |
| SA191 | Migrate `bap-web` onto current QuickScale with the fresh-first migration tool | post-v88 | 1 | SA204, SA206 | Deferred |
| SA208 | Run provider-ID removal conformance in generated projects | post-v88 | 3 | — | Deferred |
| SA153 | Deliver the first property portal using project-owned extensions | post-v88 | 1 | SA191, SA208 | Deferred |
| SA154 | Property-portal capabilities to promote when a project needs them | post-v88 | 1 | SA153 | Inventory only |
| SA209 | Make billing work against the real Stripe SDK at API version `2026-06-24.dahlia` | post-v88 | 2 | — | Deferred |
| SA207 | Declare generated-project contract changes once and let adoption advance the recorded vintage | post-v88 | 2 | — | Deferred |
| SA210 | Bound the generated projects' `poetry-core` build requirement | post-v88 | 2 | — | Deferred |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA204 ──► SA191 ──► SA153 ──► SA154 (inventory)
Track 2: SA209 ──► SA207 ──► SA210
Track 3: SA206 ──► SA208
                         critical path: {SA204, SA206} → SA191 → SA153
```

Arrows within a track are queue order; the table holds the actual dependency edges.

**Critical path.** SA204 and SA206 start together, one per track, and both gate SA191; SA206 is
the largest and most likely sets the pace. SA191 migrates `bap-web` onto the frozen
history, carries its data by a project-owned ETL, and redeploys through `deploy railway`. SA153
builds the portal on the migrated project. SA154 is an inventory, not work.

**Ordering off the critical path.** SA208 must land before SA153 starts and has all of SA191 to do
it in. SA209 is S1 and goes next on Track 2. SA207 and SA206 carry no edge: whichever
merges second reconciles the facade's adoption step (see SA207). SA210 is trivial and fills the
Track 2 tail.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA204 | yes | yes | yes | **yes** | **yes** |
| 2 | SA209 | yes | yes | yes | **yes** | no |
| 3 | SA206 | yes | yes | yes | **yes** | **yes** (SA206 only) |

### Ownership and merge coordination

- Track 1 owns gate documentation, `scripts/gate_registry.json`, the parity oracles, the hosted
  workflow triggers, the maintainer migration tools with their smoke gate and playbook, the
  migration-history freeze gate and `decisions.md` § Clean-Break Migration History, the `bap-web`
  migration and its data ETL, the property extension, public templates, and the portal's
  extension documentation.
- Track 2 owns `.github/workflows/`, `scripts/publish_module.py`, the `[build-system]` blocks of
  every package and of the generated `pyproject.toml.j2`, `ruff.toml`, the module page templates
  and test-settings stubs, the generated `base.html`, the CLI apply/deploy/update commands and
  `contract_vintage.py`, the module manifests' `contract_vintage` blocks,
  `contracts/module_options.py` and the `.env.example` template, `quickscale_core/dr_engine/`,
  and the billing module (`billing/services.py`, `billing/views.py`, `billing/adapter.py`, and its
  docs), moved from Track 3 so SA209 runs in parallel with the critical path.
- Track 3 owns the orgs tenancy, purge, removal-obligation, and boot path (`orgs/apps.py`,
  `orgs/removal.py`), the privileged-command and runtime-role stations, the
  `quickscale_core.runtime` settings facade, the generated settings templates (`base.py.j2`,
  `production.py.j2`, `local.py.j2`), the generator's Jinja environment, `auth/views.py`, and the
  blog rate limiter.
- **Cross-track edits.** SA206 shrinks the donor-settings validator in Track 1's
  `beta_migration.py`; it merges before SA191 starts, while Track 1 is on SA204, which does not
  touch that tool. SA204 and SA207 each add a registered gate; Track 2 reconciles its
  `scripts/gate_registry.json` row with Track 1 at merge.
- One delivery candidate at a time per track, one serialized merge queue into `v89`.
- **Conflict surface.** This roadmap, [CHANGELOG.md](../../CHANGELOG.md), both audits,
  [decisions.md](decisions.md) (SA204, SA206, SA207, SA153), and the SA90 emission fixture (SA206,
  SA210). Each track resolves the shared set at its own merge, after the previous merge lands, then
  runs the consistency test.
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
  that transform must also assign `organization_id` under FORCE RLS. SA191 rebuilds `bap-web`'s
  database anyway, which makes its landing vintage the cheapest freeze point. This is a one-way
  door: once a project applies a frozen `0001`, it can never be re-squashed under it
  (arch audit `clean-break-schema-no-data-path`, option 1).

  **Acceptance:** decisions record that rule 1 of the clean-break decision is lifted from 0.89.0
  onward, the release SA191 lands `bap-web` on. Upgrades from earlier vintages, including 0.88.0,
  stay fresh-database-only. From 0.89.0 on, a schema change to a model-bearing module ships as a
  new incremental migration under the existing migration-quality gates. A registered gate fails
  when an existing migration file of a model-bearing module changes or disappears, with controls
  proving that it rejects an in-place `0001` edit and accepts a new `0002`. Proof that the frozen
  history carries real data belongs to SA191.

  The gate compares against a checked-in manifest of the frozen files' content hashes, not a git
  ref: no 0.89.0 tag exists yet, and a manifest also works in shallow CI clones. The freeze takes
  effect when SA204 merges, so any later `v89` change to a model-bearing module's models ships as
  a `0002`; confirm before merging that SA208 and SA209 change no module models. The topology guard
  in `test_module_migration_topology.py` currently requires exactly one `0001_initial` and has a
  canary that rejects any `0002`; it changes to require a `0001_initial` followed by an ordered
  chain, and that canary is inverted. Settle the arch audit's open question of whether `bap-web`'s
  data is reseeded instead of carried before this merges, because the freeze cannot be undone.

  **Surfaces:** decisions, the new gate with its hash manifest, registry row, and gate
  documentation, `quickscale_core/tests/test_module_migration_topology.py`, and the arch audit.

- [x] **SA205 — Refuse a restore whose recorded module vintage differs from the installed modules.**

- [ ] **SA206 — Move code-shaped runtime contracts from the settings templates into `quickscale_core.runtime`.**

  **Context:** generated settings are user-owned and never upgraded, yet they carry executable
  QuickScale contracts. `base.py.j2` defines `ClientIdentityMiddleware`, whose client-IP
  normalization throttling keys on, and `CorrelationIdMiddleware`. `production.py.j2` holds the
  SECRET_KEY guard, the proxy-trust derivation, and the privileged-command/runtime-database bridge.
  SA200's proxy-trust fix therefore reached only new projects. The fresh-first migration copies the
  donor's `production.py` over the fresh one by policy, and `bap-web`'s copy has neither `_KNOWN_*`
  allowlist and trusts `X-Forwarded-Proto` unconditionally, so the playbook requires hand-patching
  it before the tool runs. About 3,670 of `beta_migration.py`'s lines are a static validator that
  polices that donor copy, and it is the fifth privileged-command station
  (arch audit `generated-file-ownership-unmodeled`, option 1).

  **Acceptance:** `quickscale_core.runtime` exports, as a versioned settings facade, the two
  middleware classes, the proxy-trust derivation, the privileged-command/runtime-database
  selection, and the SECRET_KEY guard. `base.py.j2` and `production.py.j2` import them and keep only
  user configuration. Freshly generated projects behave as before: the deploy-posture gate and the
  release-lane boot through `start.sh` pass, and the SA90 emission fixture is updated. The boot
  check also boots a project whose older settings were updated to the facade. A zero-module
  generated project still installs `quickscale-core` under the lockstep pin. The privileged-command
  contract test holds the facade in place of the template copy. The beta-migration validator
  checks that donor settings call the facade instead of parsing an inline copy of the contract, so
  the fifth station is gone. Decisions record the facade's import path as public API. Existing
  projects adopt it through a declared contract step (SA207).

  **Surfaces:** `quickscale_core/runtime/`, `base.py.j2`, `production.py.j2`, the
  privileged-command contract test, the donor validator in `beta_migration.py` with its smoke gate,
  the SA90 fixture, decisions, `generated_file_ownership.md`, and the arch audit.

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
  violates Django's migration-history consistency, and SA205 refuses that restore. The data
  therefore moves by a project-owned ETL into a fresh database on SA204's frozen history. SA206's
  facade replaces the hand-patched donor settings.

  **Acceptance:** the migrated project records the current QuickScale version in `quickscale.yml`
  and its lock, and passes its own test suite and local verification stack. Its settings import the
  SA206 facade; no QuickScale-owned contract is hand-patched into the donor. The project-owned
  `properties` app, its catalog seed, forms and contact customizations, content, and frontend pages
  carry over and behave as before. Its migrations are regenerated against the current
  `AbstractListing`. `.git`, `media/`, `.env`, and `poetry.lock` are not copied between the two
  trees. Every manual step the tool did not automate is recorded in the migration report and fed
  back into the playbook, or into a tool fix when it is deterministic.

  The production data moves as follows. Rehearse first: restore a production dump into a scratch
  PostgreSQL 18, confirm the expected history inconsistency with `migrate --plan` against the
  recipient, then run a `bap-web`-owned ETL into a fresh database migrated on the frozen history.
  The ETL assigns every row to the site's organization and runs under the privileged command path,
  never under a BYPASSRLS runtime role. On both the rehearsal and the cutover, listing, form, and
  user counts match before and after. The FORCE-RLS table and policy counts equal those of a fresh
  project with the same modules, and `check_tenant_isolation` passes. Media is carried over
  separately and verified.

  The migrated project replaces the old repository and redeploys through `deploy railway`. The
  written rollback restores the previous deploy *and* the retained pre-cutover database, not code
  alone. No property-portal features, frontend stack change, or module-source edits.

  **Surfaces:** the `bap-web` repository and its ETL script; the migration playbook, including its
  data and rollback steps; and, for deterministic gaps found,
  `quickscale_devtools/.../beta_migration.py` and its tests.

- [ ] **SA208 — Run provider-ID removal conformance in generated projects.**

  **Context:** organization-removal obligations are declared centrally in vendored
  `orgs/removal.py`. `external_provider_obligation_mismatches` is called only from orgs' own test
  suite, over its test `INSTALLED_APPS`. It never runs in a generated project and cannot see
  project-owned models. Its heuristic treats any non-relational `*_id` field as a provider ID, so a
  SA153 property model with, say, an `mls_id` would be purged without refusal or reconciliation.
  Declaring it would require editing vendored `orgs` source, which SA153 forbids. This containment
  lands before SA153's first tenant tables. The domain-registered coordinator stays in the arch
  audit until its trigger fires (arch audit `deletion-invariants-per-boundary-reimplementation`,
  option 3).

  **Acceptance:** the conformance walk runs as an orgs system check over `get_tenant_models()` in
  generated projects. A project-owned app classifies each of its `*_id` fields as provider-backed or
  not from its own code, in the same way it declares tenant markers, without editing vendored `orgs`
  source. `purge_organization` refuses an organization with a row carrying a provider-backed
  project field, naming the field. A test model with an undeclared `*_id` fails the check, and
  declaring it passes; shipped modules still pass. The last-owner predicate, the `pre_delete`
  backstop, and both removal boundaries are unchanged.

  **Surfaces:** `orgs/removal.py`, `orgs/apps.py` check registration, `purge_organization`, the orgs
  tests, the [extension contract](module-extension.md), and the arch audit.

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

- [ ] **SA209 — Make billing work against the real Stripe SDK at API version `2026-06-24.dahlia`.**

  **Context:** two chained S1 defects (tech audit `billing-stripe-objects-normalized-empty` and
  `billing-stripe-api-version-drift`) mean billing has never worked against the real SDK.
  - Since stripe-python 13, `StripeObject` is not a `Mapping`, so `_normalize_mapping` turns every
    event, price, customer, session, and subscription into `{}`. Every signed webhook gets a 400
    ("missing an id"), and every checkout gets a 400 on price parity.
  - Behind that, billing reads pre-2025 payload shapes: `invoice.subscription`,
    `line.price`, and top-level `subscription.current_period_*`. Under dahlia these live at
    `invoice.parent.subscription_details`, `line.pricing.price_details.price`, and on subscription
    items. So subscribers are charged each period and never credited, and every subscription event
    writes `NULL` period bounds.
  - The tests pass only because the fakes return plain dicts in the retired shape.

  Team decisions of 2026-09-23 apply: target the SDK's pinned `2026-06-24.dahlia`, keep no legacy
  fallback, and reject a webhook from a different named release, matching by release name rather
  than date. Ship both fixes together, because fixing only the first unmasks the second.

  **Acceptance:**
  - SDK objects are converted before normalization. A locally signed body through the real
    `StripeClient.construct_event` yields its event id, and a `construct_from` checkout session
    keeps its id.
  - Billing declares one `STRIPE_API_VERSION` and sets it on the SDK. A test fails when the
    installed SDK's pinned version moves to a different named release.
  - `handle_stripe_event` rejects an event from a different named release with
    `BillingConfigurationError` naming the expected version, which gives a 500 so Stripe retries.
    It logs each event's version.
  - Billing reads only dahlia shapes:
    - The subscription id and resolution metadata come from `parent.subscription_details`.
    - The price comes from `pricing.price_details.price`, falling back to the subscription-details
      metadata.
    - Period bounds come from subscription items, which must agree, and known bounds are never
      overwritten with `None`.
  - Fixtures and fake clients are rewritten to dahlia shapes built from real SDK objects, and the
    legacy fixtures are removed.
  - The following tests pass:
    - a dahlia `invoice.paid` (`subscription_cycle`) grants exactly one plan credit;
    - a dahlia `customer.subscription.updated` keeps item-derived bounds;
    - a `2025-03-31.basil` event raises and creates no credit.
  - The billing docs and the generated operations guidance state the required endpoint version,
    and the webhook-wiring output prints it. The upgrade note says that an endpoint on an older
    version stops processing until it is recreated.

  **Surfaces:** `billing/services.py`, `billing/views.py`, the billing tests and fake clients, the
  billing module docs and webhook-wiring output, the generated operations guidance, and the tech
  audit.

- [ ] **SA207 — Declare generated-project contract changes once and let adoption advance the recorded vintage.**

  **Context:** the contract-vintage gate detects a project that is behind the template contract,
  at `update`, `apply`, and `deploy railway`. Adoption, however, is prose copied by hand:
  - One five-step block for SA192's shared design is pasted into the auth, billing, listings,
    blog, and CRM manifests, and `RAILWAY_CONTRACT_VINTAGE` duplicates orgs' three steps.
  - `project_contract` is written only when state is created, and acknowledgement is
    per-invocation. A pre-0.89 project therefore passes `--acknowledge-contract-vintage` on every
    mutating command for as long as it lives.
  - SA200 and SA201 changed runtime contracts and declared no adoption step. SA201's gap fails
    open. It moved billing's throttle scopes into the upgradable module, but a pre-SA201 `base.py`
    assigns `REST_FRAMEWORK` wholesale with no throttle classes. So an existing project that
    updates billing loses the checkout-loop bound silently.

  (Arch audit `generated-file-ownership-unmodeled`, option 3 for what remains configuration.)

  **Acceptance:**
  - One project-level contract vintage declares each template contract change once, with its
    adoption steps. The five manifest copies and the Railway duplicate are gone.
  - It declares SA192's shared design, SA200's proxy trust, and SA201's throttling. Whichever of
    SA206 and SA207 merges second adds the facade adoption step.
  - `update billing` on a project behind SA201's step refuses before mutation and names the step.
    After adoption, the 31st checkout in an hour returns 429.
  - `project_contract` advances when the user confirms adoption, so a project that has adopted
    every step no longer needs the flag.
  - A registered gate fails when `templates/project_name/settings/*`, `start.sh.j2`, or
    `Dockerfile.j2` changes without a project-vintage edit, with controls in both directions.
  - [decisions.md](decisions.md) § Release scope safeguards records the growth of
    `INTENTIONALLY_UNMANAGED` from 78 to 89 entries, including the dispositions SA194 changed.
    [generated_file_ownership.md](generated_file_ownership.md) gives a rationale for
    `validateQuickScaleSeam.ts`, `FormsPage.tsx`, `SocialEmbedsPublicPage.tsx`, and
    `SocialLinkTreePublicPage.tsx`.

  **Surfaces:** `contract_vintage.py`, the module manifests' `contract_vintage` blocks,
  `deployment_commands.py`, the apply-state writer, the new gate and its registry row, decisions,
  `generated_file_ownership.md`, and the arch audit.

- [ ] **SA210 — Bound the generated projects' `poetry-core` build requirement.**

  The 17 repository manifests declare `poetry-core>=2.0,<3.0`, but `pyproject.toml.j2` still emits
  an unbounded `requires = ["poetry-core"]` into every generated project (tech audit
  `build-system-requires-unpinned`).

  **Acceptance:** the template emits `poetry-core>=2.0,<3.0`, and the SA90 emission fixture is
  updated in the same change.

  **Surfaces:** `generator/templates/pyproject.toml.j2`, the SA90 fixture, and the tech audit.

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Every live finding of the 2026-09-23 passes is scheduled above. The architecture audit's open
questions still apply: whether `bap-web`'s data could be reseeded instead of carried (which would
reshape SA191 and SA204), whether "regenerate and port" is the permanent upgrade model (which would
reshape SA206 and SA207), and whether `experto-ai-web` migrates too.
The standing scope
rules, presence contracts, and resource safeguards live in [decisions](decisions.md) and
[validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
