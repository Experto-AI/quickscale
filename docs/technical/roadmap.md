# QuickScale Development Roadmap

> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

The immediate goal is one convention across all modules, as recorded in
[decisions.md § Module Conventions](decisions.md#module-conventions). `bap-web` is then ported
once, onto the standardized names (SA191), and carries the first property portal in a
project-owned extension (SA153). Capabilities are generalized only after that project proves
their value.

**Release status.** 0.88.0 is published with S1 billing defects (with real Stripe keys, every
webhook and every checkout fails). The fixes are on `v89` and ship in 0.89.0
([publish_procedure.md](publish_procedure.md)). 0.89.0's one open release requirement is SA292. A live
0.88.0 install moves to 0.89.0 on a fresh database, and the 0.89.0 release notes say so.
Publication is assistant-driven up to the two operator commands. Done on `v89`: Part 1 is green on
the release bytes — `7821db42` readies the CHANGELOG and release note, `f4c8c79f` brings three
quality-gate functions under the CC threshold, and `make ci-e2e` and `make release-gate` pass with
the E2E lanes serial (`QS_E2E_PARALLEL=0`; concurrent-lane Poetry installs exceed the per-test
timeout on this machine) — and Phases 2–3 re-pointed the local `0.89.0` tag at the tip and
published the four outdated split branches. Phases 4a–4b then passed on this tip: an all-module
generated project (`quickscale plan` + `quickscale apply --split-refs-from-branches`) answered its
twelve documented routes locally, and `quickscale deploy railway` booted the same project's runtime
role, migrations, and Gunicorn on the deployed URL. The run recorded what the phases needed but the
procedure did not name — the test-only vendor credentials a billing/notifications/analytics
selection needs before `apply` and before the deployment serves, and the non-interactive Railway
initialization behavior — in [publish_procedure.md](publish_procedure.md) Phases 4a–4b and
[railway.md](../deployment/railway.md). Remaining: SA292 lands with Part 1 re-run and the
local `0.89.0` tag re-pointed at its tip; the operator then runs `make seal-modules VERSION=0.89.0`
and `make seal-status VERSION=0.89.0` (Phase 5), then `git push origin 0.89.0` (Phase 6); the
assistant then verifies PyPI and the GitHub Release and opens the release PR.

Audit tickets name the [arch](../others/arch-audit.md), [tech](../others/tech-audit.md), or
[coherence](../others/coherence-audit.md) IDs they close; the audits keep the evidence. Coherence
tickets merge the matching coherence proposal into decisions with a harness detector, or record a
review-only clause without one.

The scheduling table owns track, dependencies, and release requirement. Ticket bodies own
context, scope, acceptance, and each slice's tier; [CHANGELOG.md](../../CHANGELOG.md) preserves
history.

**Sizing.** Every slice carries an Adaptive tier
(Adaptive `docs/guides/operator-guide.md` § Planning and implementation):
Tier 1 is one bounded low-risk concern within direct context fit; Tier 2-fast is a specified
change with known targets, acceptance, and checks; Tier 2-full is one whose callers, mechanism,
or environment still need discovery. No slice is Tier 3: work that would be is split so that its
one-way or high-risk step stands alone behind the slices that prove it.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Track | Depends on | Release requirement |
|---|---|---|---|---|
| SA292 | Fix `quickscale deploy railway` re-initializing a linked directory, and correct the manual-deploy docs | 1 | — | Required |
| SA191 | Migrate `bap-web` onto current QuickScale by a one-off prompt-driven port | 1 | SA292 | Optional |
| SA153 | Deliver the first property portal using project-owned extensions | 1 | SA191 | Optional |
| SA154 | Property-portal capabilities to promote when a project needs them | 1 | SA153 | Inventory only |
| SA277 | Define the upgrade path as `beta_migration` code plus a prompt for the remainder | 2 | SA191 | Optional |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA292 ──► SA191 (cutover) ──► SA153 (f, go-live) ──► SA154 (inventory)
Track 2: SA277 (a2)
Track 3: — (SA204 (j) landed)
     release path:  SA292 ──► seal + publish 0.89.0 ──► SA191 cutover ──► SA153 (f)
     critical path: SA191 (cutover) ──► SA153 (f)
```

Arrows within a track are queue order; the table holds the dependency edges. SA191's cutover
waits on the 0.89.0 publication, now that SA153 (e3) has landed so the reverted contract step
never ships; SA153 (e4) has landed. SA292 heads Track 1 because it changes release-gated bytes
and must land before the split tags are sealed. SA153 (f) waits on
the cutover, with the migration freeze it also waited on landed. SA277 (a1) has landed; only
SA277 (a2) waits on the cutover, whose evidence confirms the line between what `beta_migration`
automates and what the prompt handles.

**Slices.** Each slice is one implementer session with a fresh context, scoped to its text and
named surfaces, and ends with a short handoff note committed with the work. A ticket closes when
its last slice lands; slices are not scheduled.

**Order.** SA204 (j) froze migration history before SA153 (f) puts non-reseedable tenant data on
`bap-web`, and no module `0001` edit was outstanding, so `bap-web` needs no reseed. SA153's own
tables live in the project-owned extension as `0002+` migrations. No open ticket changes a module
schema; a schema change from the freeze release on ships as a new migration. SA153 (a…e) builds on
the `v89` pin, re-pinned at each `v89` merge that touches modules.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA292 | yes | yes | yes | no | yes |
| 2 | SA277 (a2) | no | no | yes | no | no |
| 3 | — | yes | yes | yes | yes | no |

### Ownership and merge coordination

- Track 1 owns the generated `urls.py.j2` and the theme's social seam pages, the parity oracles,
  the hosted workflow triggers (including `e2e.yml`'s tag pattern), the `bap-web`
  migration and its reseed step, the property extension, public templates, and the portal's
  extension documentation, the managed CI-environment and operations-guide includes, and, for the
  conventions, module identities, models and their `0001_initial`, module READMEs, and module
  templates, static files, and template tags, with the module page templates and the generated
  `base.html`, cross-module imports and settings reads, and the `services.py` public surface.
- Track 2 owns the gate registry and everything generated from it (`scripts/gate_registry.json`,
  `check_quality.sh`, `check_gate_parity.py`, `sync_ci_gate_jobs.py`, `check_ci_locally.sh`'s
  gate arms, the Makefile gate help, the gate documentation table), `.github/workflows/`,
  `scripts/publish_module.py`, the `[build-system]` blocks of every package, the core build
  target, the bundled-manifest build step and the publish-artifact check, `ruff.toml`, the
  test-settings base, stubs and conftest plugin, `scripts/security_suppressions.json`, the
  gate-script parity families, the CLI apply/deploy/update commands, `utils/_dependency_write.py`,
  and `contract_vintage.py`, the module manifests' `contract_vintage` blocks, `throttle_scopes`
  and `project_contract.yml`, `contracts/module_options.py` and the `.env.example` template,
  `quickscale_core/dr_engine/`, and the billing module (`billing/services.py`,
  `billing/views.py`, `billing/adapter.py`, `_customers.py`, `_stripe_client.py`, its commands,
  and its docs), the split facades of the CLI commands, `dr_engine`, and billing with the tests
  that patch them, the blog and storage upload-path builders and the storage Markdownx upload,
  and, for the conventions, the manifest option schema and the CLI's `module_config`, module
  settings names, `is_enabled()`, and the per-module personal-data declarations with the orgs
  personal-data check, and the maintainer migration tools (`beta_migration/`) with their smoke
  gate, playbook, gap ledger, and the `showcase_react` design layer.
- Track 3 owns the orgs tenancy, purge, removal-obligation, invite-throttle, and boot path
  (`orgs/apps.py`, `orgs/removal.py`, `orgs/views.py`), the privileged-command and runtime-role
  stations, `is_platform_operator` and `operator_access`, the `quickscale_core.runtime`
  settings facade and its scheduled-off refusal helper, the generated settings templates
  (`base.py.j2`, `production.py.j2`, `local.py.j2`) with the generated `REST_FRAMEWORK`
  defaults, the generator's Jinja environment, `auth/views.py`, the blog rate limiter, the
  generated `pyproject.toml.j2` `[build-system]` block, orgs' `quickscale_orgs_create_site_org`
  command, the notifications webhook (`_webhooks.py`), the CRM list API and the theme's CRM
  page, the generated theme seam types and the theme hooks that read them, and the frontend
  decisions in `frontend.md`, and, for the conventions, the `quickscale_core.runtime` helpers,
  module `checks.py` and `exceptions.py`, core's `CAPABILITIES`, the adapter hook signature,
  write effects and email, orgs' `permissions`, and module URLs, APIs, and webhooks, with the
  theme's React API client, module settings snapshots and the module split facades' loggers and
  re-exports, the conformance harness with its registry row, parity families and
  `module-extension.md`'s authoring checklist, the five `_anonymization.py` handlers with
  core's redaction helpers, and the migration-history freeze gate, its hash manifest, and
  `decisions.md` § Clean-Break Migration History.
- **Cross-track edits.** SA153 (e3) reverts Track 3's `publicPage` seam type, with Track 3
  review, and lands through the serialized merge queue.
- One delivery candidate at a time per track, one serialized merge queue into `v89`.
- **Conflict surface.** This roadmap, [CHANGELOG.md](../../CHANGELOG.md), the three audits,
  `project_contract.yml`, and [decisions.md](decisions.md). Each track resolves the shared set at
  its own merge, after the previous merge lands, then runs the consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

### Track 1 — migration history and the property portal

- [x] **SA204 — Freeze module migration history at the vintage `bap-web` lands on.**

- [ ] **SA292 — Fix `quickscale deploy railway` re-initializing a linked directory, and correct the manual-deploy docs.**

  Found in 0.89.0's Phase 4b. `quickscale_cli`'s `is_railway_project_initialized()` checks for a
  `.railway/` directory, but Railway CLI 5.x (5.70.0, the current release) keeps directory links in
  `~/.railway/config.json`, so `quickscale deploy railway` re-runs `railway init` in a pre-linked
  directory and creates a second project.

  **Acceptance:** the check reads the live link state (for example `railway status --json`), with a
  test for a linked directory that has no `.railway/`; railway.md's Manual Deployment section uses
  per-variable `railway variable set` commands verified against CLI 5.70, and the Phase 4b caution
  in publish_procedure.md is reduced to match the fixed behavior. Full gates pass, Part 1 is re-run
  on the tip, and the local `0.89.0` tag is re-pointed there; sealing (Phase 5) follows as the
  operator's step (Tier 2-fast).

- [ ] **SA191 — Migrate `bap-web` onto current QuickScale by a one-off prompt-driven port.**

  `bap-web-new` (`/home/victor/code/bap-web-new`) is the ported recipient, path-pinned to the
  `v89` checkout with every pending contract step adopted; `scripts/cutover.sh` and
  `CUTOVER.md` rebuild a fresh database, reseed the catalog under the restricted runtime role
  (billing disabled), verify, and roll back, rehearsed on scratch.

  **Remaining:** the cutover. After 0.89.0 is published, an assistant swaps the pin to `0.89.0`,
  re-runs the rehearsal, so the unpublished pin never reaches production, and stages the
  production run (exact commands, media manifest, invite list, rollback). The operator then gives
  the go: the Railway cutover against production, the media carry, the user re-invites, and the
  old repository's archive. The
  pre-cutover database is retained until the reseeded site is verified. The production dump at
  `/home/victor/code/bap-web-prod.dump` holds real user data and stays out of every repository.

- [ ] **SA153 — Deliver the first property portal using project-owned extensions.**

  Target `buenosairesproperties.com` with one React public property surface over a project-owned
  JSON read API under the [extension contract](module-extension.md), building on the React pages
  and `/api/properties/` SA191 carried over. No public API in `listings`, no generic property
  behavior in generated projects. Module-coupled data on new pages comes through seam-declared
  hooks in managed files (arch `generated-file-ownership-unmodeled`, Next (b)).

  **Landed (a)–(e4)** on `bap-web-new`: explicit per-listing currency labels, the tenant-owned
  `PropertyImage`/`PropertyFeature`/`PropertyInquiry` tables (own `organization_id`, forced RLS,
  composite FKs, boundary tests), the listing inquiry filing a CRM record with the listing
  reference, and (e4)'s per-request fill: Django writes the catalog and detail documents' head
  and a plain-HTML crawler summary from the live published listings, `sitemap.xml` and
  `robots.txt` are Django views over the same data, and the build-time prerender path is gone.

  **Acceptance (remaining):** the deployed site (f). The served documents, the sitemap and robots
  views, and the search → detail → inquiry journey with organization isolation pass in the
  project, and the SA208 and SA246 declarations pass in `manage.py check`.

  **Slices** (in order; (e1) and (e2) built a build-time prerender from a committed snapshot that
  (e3)–(e4) replaced with Decision 2's per-request fill):
  - [x] (e3): landed on QuickScale as the revert: the theme's `publicPage` seam carries the social
    shapes only, `main.tsx` mounts with `createRoot` (no hydration), the static-location render is
    gone, the prerender contract step is retired (replaced by `sa153e3-public-page-prerender-reverted`
    — the contract gate requires a fresh id on a template change), its CHANGELOG bullet is out, and
    frontend.md matches Decision 2.
  - [x] (e4): landed on `bap-web-new`: the catalog and detail routes' Django view fills the SPA
    document's head and a crawler summary per request from the published, organization-scoped
    listings; `sitemap.xml` and `robots.txt` are Django views over the same data; the prerender
    build step, the snapshot command, the committed artifacts, and the reverted contract step's
    project-side traces are gone; the no-JavaScript crawler test, rendered-document organization
    isolation, and the journey test pass (Tier 2-fast).
  - [ ] (f) Go-live on `buenosairesproperties.com` after SA191's cutover and the migration
    freeze; re-prove the journey on the deployed site (Tier 2-full; production deploy,
    maintainer action).

- [ ] **SA154 — Property-portal capabilities to promote when a project needs them.**

  Inventory only: generalizing the property API, React pages, or crawler fill into reusable
  modules or the theme; React read API and pages for the blog, generic listings, and the CRM
  dashboard; React `auth` and `billing` flows; broader translations; maps/geocoding; saved
  searches, favorites, and alerts; agent/office profiles; syndication; tours/video; paid
  placement; blog/listing cross-links; and PostgreSQL full-text search. Promote an item only with
  a concrete consumer, bounded acceptance, and a fresh dependency and track. Tenant tables build
  on marker-derived enrollment and purge; schema changes ship incremental migrations on SA204's
  frozen history. Close when every item is promoted or dropped with rationale.

### Track 2 — upgrade path

- [ ] **SA277 — Define the upgrade path as `beta_migration` code plus a prompt for the remainder.**

  Closes arch `generated-file-ownership-unmodeled` Next (a). One path in two stages:
  `beta_migration` does what it can mechanically; the prompt-driven port (`MIGRATION_PROMPT.md`,
  `CUTOVER.md`) handles what it reports it could not.

  **Acceptance:** decisions record the two-stage path (the gap ledger is the prompt's input, so
  neither stage repeats the other), the boundary rule (a gap that recurs across releases moves
  into code; a one-off stays in the prompt), the revocation trigger (a second long-lived project
  or a template security fix), and the steps-per-release count to watch, trending toward zero
  (50 declared steps on 2026-10-16). Operator docs do not duplicate steps either stage covers.

  **Slices:**
  - [x] (a1) The wired handoff: the completed prompt names every recorded unresolved gap in its
    remaining-work form — the pre-port surfaces and the donor's module divergences (older copies
    the current module content supersedes, and local edits to upstream or re-express), each with
    paths and a governing rule — and the smoke gate's gap-handoff case proves the handoff file
    carries them. The working prompt and `CUTOVER.md` are copied into the maintained tree
    (`docs/planning/beta-site-migration-prompt.md`, `docs/planning/beta-site-cutover.md`; the
    `bap-web-new` copies stay the cutover's source). This slice's handoff note carries the
    decision-record and boundary-rule draft:
    `docs/planning/migration-upgrade-path-draft.md`. Next: (a2), after the cutover.
  - [ ] (a2) After SA191's cutover: the decision record and boundary rule in decisions, the
    (a1) draft confirmed or amended against the cutover evidence, and the operator docs pruned of
    steps either stage covers (Tier 2-fast).

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Standing scope rules, presence contracts, and resource safeguards live in [decisions](decisions.md)
and [validation policy](validation_policy.md#candidate-review-and-integration).

**Unscheduled — React-theme browser coverage.** No test drives `showcase_react` in a real
browser against a real backend. The repo's Playwright E2E asserts only status 200, the title and
the first stylesheet; the generated `e2e/home.spec.ts.j2` is stale and no CI runs it. Order when
scheduled: (1) fix the stub and add `pnpm test:e2e` to `ci.yml.j2`; (2) the named user journeys;
(3) a depth-capped link crawler in `test_e2e_full_workflow.py`; (4) full journey E2E against the
Docker stack, only if it fits the E2E time budget in validation_policy.md.

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
