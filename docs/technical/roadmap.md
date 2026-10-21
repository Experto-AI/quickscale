# QuickScale Development Roadmap

> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

The immediate goal is one convention across all modules, as recorded in
[module_conventions.md](module_conventions.md#module-conventions). `bap-web` is then ported
once, onto the standardized names: the regenerated `bap-web-new`, already at visual parity, is
cut over (SA191a–e) and then carries the first property portal in a project-owned extension
(SA153). Capabilities are generalized only after that project proves
their value.

**Release status.** 0.89.0 fixes 0.88.0's S1 billing defects; a live 0.88.0 install moves to
0.89.0 on a fresh database. The local `0.89.0` tag is validated; SA191d's cutover is the proof
before the operator's Phases 5–6 sealing and PyPI publication
([publish_procedure.md](publish_procedure.md)).

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
| SA191c | Write the operator cutover checklist | 1 | — | Required |
| SA191d | Cut over production to `bap-web-new` (operator) | 1 | SA191c | Required |
| SA153 | Deliver the first property portal using project-owned extensions | 1 | SA191d | Optional |
| SA154 | Property-portal capabilities to promote when a project needs them | 1 | SA153 | Inventory only |
| SA277 | Define the upgrade path for newer projects as `beta_migration` code plus a maintained prompt | 2 | SA191d | Optional |
| SA304 | Fail the release check when a sealed module changed after its seal | 2 | — | Required |
| SA305 | Detect hand edits to an embedded module before `quickscale update` | 2 | — | Optional |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA191c ─────────────┐
Track 3: SA191e (done) ──────┼─► SA191d (operator) ──► SA153 (r, f) ──► SA154 (inventory)
Track 2: SA304 ──► SA305 ──► SA277 (a3) ──► SA277 (a2, after SA191d)
     release path:  SA191a, SA191b, SA191e (done) ──► SA191c–d ──► operator publish 0.89.0
     critical path: SA191c ──► SA191d ──► SA153 (f)
```

Arrows within a track are queue order; the table holds the dependency edges. SA191a, SA191b,
and SA191e have landed; SA191c can start now; SA191d is the operator's own production cutover
after SA191c.
SA304 and SA305 run now, ahead of SA277 (a3); (a2) waits on SA191d's cutover evidence.

**Slices.** Each slice is one implementer session with a fresh context, scoped to its text and
named surfaces, and ends with a short handoff note committed with the work. A ticket closes when
its last slice lands; slices are not scheduled.

**Order.** Module migration history is frozen, so a module schema change ships as a new
migration. SA153's own tables live in the project-owned extension as `0002+` migrations.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA191c | yes | no | yes | no | yes |
| 2 | SA304 | yes | no | yes | no | no |
| 3 | — | no | yes | yes | yes | no |

### Ownership and merge coordination

- Track 1 owns the generated `urls.py.j2` and the theme's social seam pages, the parity oracles,
  the hosted workflow triggers (including `e2e.yml`'s tag pattern), the `bap-web-new` cutover,
  the property extension, public templates, and the portal's
  extension documentation, the `bap-web-new` forms import, the design-system
  extraction and the visual-parity harness, the managed CI-environment and operations-guide
  includes, and, for the conventions, module identities, models and their `0001_initial`,
  module READMEs, and module templates, static files, and template tags, with the module page templates and the generated
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
- Track 3 owns the `bap-web-new` admin parity (SA191e), the orgs tenancy, purge,
  removal-obligation, invite-throttle, and boot path (`orgs/apps.py`, `orgs/removal.py`, `orgs/views.py`), the privileged-command and runtime-role
  stations, `is_platform_operator` and `operator_access`, the `quickscale_core.runtime`
  settings facade and its scheduled-off refusal helper, the generated settings templates
  (`base.py.j2`, `production.py.j2`, `local.py.j2`) with the generated `REST_FRAMEWORK`
  defaults, the generator's Jinja environment, `auth/views.py`, the blog rate limiter, the
  generated `pyproject.toml.j2` `[build-system]` block, orgs' `quickscale_orgs_create_site_org`
  command, the notifications webhook (`_webhooks.py`), the CRM list API and the theme's CRM
  page, the CLI help, the generated
  theme seam types and the theme hooks that read them, and the frontend decisions in
  `frontend.md`, and, for the conventions, the `quickscale_core.runtime` helpers, module `checks.py` and `exceptions.py`, core's `CAPABILITIES`, the adapter hook signature,
  write effects and email, orgs' `permissions`, and module URLs, APIs, and webhooks, with the
  theme's React API client, module settings snapshots and the module split facades' loggers and
  re-exports, the conformance harness with its registry row, parity families and
  `module-extension.md`'s authoring checklist, the five `_anonymization.py` handlers with
  core's redaction helpers, and the migration-history freeze gate, its hash manifest, and
  `decisions.md` § Clean-Break Migration History.
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

### Tracks 1 and 3 — cutover and the property portal

**SA191 family — validate and cut over the regenerated `bap-web-new`.** Context shared by
SA191a–e: old `bap-web` (`~/code/bap-web`) serves production on Railway with no users, only form
submissions and configuration. `bap-web-new` (`~/code/bap-web-new`) already declares every
module (`auth`, `listings`, `forms`, `analytics`, `notifications`, `orgs`, `storage`), carries
the `properties` app with `/api/properties/` and `properties_seed_catalog`, and recreates the six
BAP form definitions (`compradores`, `vendedores`, `alquiler-propietario`,
`alquiler-inquilino`, `reubicacion`, `consulta-general`) in
`client_extensions/.../forms_seed_presets.py`.
SA191e runs on track 3; the rest on track 1.
SA191a, b, c, and e are coding-assistant tasks that touch no production system; SA191d is the
operator's own cutover. A QuickScale defect found follows the release re-entry loop; a project
defect is fixed in `bap-web-new`, project-specific behavior in its `client_extensions`.

- [x] **SA191a — Prove `bap-web-new` on a fresh local stack.**

- [x] **SA191b — Import old `bap-web` form submissions into `bap-web-new`.**

- [x] **SA191e — Bring the `bap-web-new` admin to parity with old `bap-web`.**

- [ ] **SA191c — Write the operator cutover checklist.**

  Tier 1. `bap-web-new/CUTOVER.md`, one page: export the old database and forms (`pg_dump` plus
  the SA191b `dumpdata` command); the Railway variables for the new service (secret key, allowed
  hosts, database URL, analytics key, email provider and sender, storage backend, site
  organization); deploy as a new Railway service beside the old one; the post-deploy commands
  (migrate, site organization, catalog and forms seed, SA191b's import); the checks
  (healthcheck, home, property search and detail, a form submission with its notification email
  received, imported submissions visible in admin); the domain switch; and rollback (point the
  domain back; the old service stays untouched until the operator retires it).

- [ ] **SA191d — Cut over production to `bap-web-new` (operator).**

  Operator action, not handed off. Run `CUTOVER.md` on Railway, switch the domain, then retire
  the old service and archive the `bap-web` repository. Each production step is
  operator-authorized; the old database export is kept outside every repository.

- [ ] **SA153 — Deliver the first property portal using project-owned extensions.**

  Target `buenosairesproperties.com` with one React public property surface over a project-owned
  JSON read API under the [extension contract](module-extension.md), building on the React pages
  and `/api/properties/` the port carried over. No public API in `listings`, no generic property
  behavior in generated projects. Module-coupled data on new pages comes through seam-declared
  hooks in managed files (arch `generated-file-ownership-unmodeled`, Next (b)).

  **Acceptance:** the served documents (per-request head and crawler summary), the sitemap and
  robots views, and the search → detail → inquiry journey with organization isolation pass on the
  deployed site, and the SA208 and SA246 declarations pass in `manage.py check`.

  **Slices:**
  - [ ] (r) Audit the portal work already in `bap-web-new` (the `properties` app, its API, and
    the React pages) against this acceptance, list what is missing, and close the gaps with
    tests in the project (Tier 2-full).
  - [ ] (f) Go-live on `buenosairesproperties.com` after SA191d's cutover; re-prove the journey on
    the deployed site (Tier 2-full; production deploy, maintainer action).

- [ ] **SA154 — Property-portal capabilities to promote when a project needs them.**

  Inventory only: generalizing the property API, React pages, or crawler fill into reusable
  modules or the theme; React read API and pages for the blog, generic listings, and the CRM
  dashboard; React `auth` and `billing` flows; broader translations; maps/geocoding; saved
  searches, favorites, and alerts; agent/office profiles; syndication; tours/video; paid
  placement; blog/listing cross-links; and PostgreSQL full-text search. Promote an item only with
  a concrete consumer, bounded acceptance, and a fresh dependency and track. Tenant tables build
  on marker-derived enrollment and purge; schema changes ship incremental migrations on the
  frozen history. Close when every item is promoted or dropped with rationale.

### Track 2 — module provenance and upgrade path

Context shared by SA304 and SA305: SA302 changed `quickscale_modules/orgs/` on `v89` after
`splits/orgs-module/0.89.0` was sealed at `6b970dc`, and nothing flagged the stale seal. SA191a
then copied the fix into `bap-web-new/modules/orgs` by hand, leaving `.quickscale/state.yml`
pointing at a split without it, where a later `quickscale update` could revert it. The instance
itself is repaired by an operator reseal of the orgs split and a project update, outside these
tickets; these tickets make the next one visible.

- [ ] **SA304 — Fail the release check when a sealed module changed after its seal.**

  Tier 2-fast. `make publish-module-status` already lists orgs as "unsealed outdated", but only
  as a warning, and it does not say that a remote `0.89.0` seal exists on the stale commit. The
  status and the publish-quality check report a module whose sealed `splits/<module>-module/X.Y.Z`
  tag for the current `VERSION` differs from its current subtree split as a blocking
  "sealed but stale" state that names the module and points at the Phase 5 reseal path in
  `publish_procedure.md`.

  **Acceptance:** a test repository with a sealed module tag and a later commit under that
  module fails the check with that module named; an unchanged module and an unsealed module do
  not fail it.

- [ ] **SA305 — Detect hand edits to an embedded module before `quickscale update`.**

  Tier 2-full. Before a subtree pull, `quickscale update` compares each embedded
  `modules/<module>/` tree with the tree at its recorded `commit_sha` (allowing for the rewrites
  embedding applies, such as `pyproject.toml`), and refuses with a list of the changed paths
  unless `--allow-local-changes` is passed. `quickscale status` reports the same drift.
  The roadmap rule that a QuickScale defect follows the release re-entry loop gains the line
  "never patch an embedded module in a project; republish and update". The update's dependency
  sync also keeps a project's `quickscale-core` path dependency on a committed wheel: in
  `bap-web-new` it rewrote it to `>=0.89.0,<0.90.0`, a version not yet on PyPI.

  **Acceptance:** tests cover an unchanged module (passes), a hand-edited file (refused, path
  listed), and the override flag; `quickscale status` shows the drift; an update of a project
  whose `quickscale-core` is a wheel path leaves that line unchanged.

- [ ] **SA277 — Define the upgrade path for newer projects as `beta_migration` code plus a maintained prompt.**

  Closes arch `generated-file-ownership-unmodeled` Next (a). One path in two stages:
  `beta_migration` does what it can mechanically; the prompt-driven port (`MIGRATION_PROMPT.md`,
  `CUTOVER.md`) handles what it reports it could not.

  **Acceptance:** decisions record the two-stage path (the gap ledger is the prompt's input, so
  neither stage repeats the other), the boundary rule (a gap that recurs across releases moves
  into code; a one-off stays in the prompt), the revocation trigger (a second long-lived project
  or a template security fix), and the steps-per-release count to watch, trending toward zero
  (50 declared steps on 2026-10-16). Operator docs do not duplicate steps either stage covers.
  `bap-web` is an old project; the path must also serve "not so old" ones: a declared supported
  source-version range, `beta_migration` proven against projects generated at each version in
  it, and the AI-assistant prompt kept and versioned in the QuickScale repository rather than only
  in a recipient. Supporting further projects meets the "second long-lived project" revocation
  trigger, and decisions say so.

  **Slices:**
  - [x] (a1) The handoff names every recorded gap; draft decision record in
    `docs/planning/migration-upgrade-path-draft.md`.
  - [ ] (a2) After SA191d's cutover: the decision record and boundary rule in decisions, the
    (a1) draft confirmed or amended against the cutover evidence, and the operator docs pruned of
    steps either stage covers (Tier 2-fast).
  - [ ] (a3) The supported source-version range, test projects generated at each version in it
    with `beta_migration` smoke runs against them, and the prompt moved into the QuickScale
    repository as a versioned artifact (Tier 2-full).

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Standing scope rules, presence contracts, and resource safeguards live in [decisions](decisions.md)
and [validation policy](validation_policy.md#candidate-review-and-integration).

**Unscheduled — React-theme browser coverage.** The generated Playwright E2E now asserts the
current dashboard heading against the Django-served origin, and `bap-web-new` has a live-site
screenshot harness; the repository still has no full journey suite. Remaining
order when scheduled: (1) add `pnpm test:e2e` to `ci.yml.j2`;
(2) the named user journeys; (3) a depth-capped link crawler in `test_e2e_full_workflow.py`;
(4) full journey E2E against the Docker stack, only if it fits the E2E time budget in
validation_policy.md.

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
