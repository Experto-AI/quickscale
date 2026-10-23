# QuickScale Development Roadmap

> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

Cut over the regenerated `bap-web` at visual parity (SA191d), then deliver the first
property portal in a project-owned extension (SA153), following
[module conventions](module_conventions.md#module-conventions). Generalize capabilities only
after that project proves their value.

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
or environment still need discovery. High-risk transitions stay Tier 3 with plan review
required; preparation ships separately.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Track | Depends on | Release requirement |
|---|---|---|---|---|
| SA191d | Cut over production to the regenerated `bap-web` in place (delegated, operator-gated) | 2 | — | Required |
| SA153 | Deliver the first property portal using project-owned extensions | 1 | SA191d | Optional |
| SA154 | Property-portal capabilities to promote when a project needs them | 1 | SA153 | Inventory only |
| SA277 | Define the upgrade path for newer projects as `beta_migration` code plus a maintained prompt | 3 | SA191d | Optional |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA153 (h → j) ──► [SA191d (production)] ──► SA153 (f) ──► SA154
Track 2: SA191d (re-proof → production → retire)
Track 3: SA277 (a3) ──► SA277 (a2)
     critical path: SA191d (re-proof → production → retire) ──► SA153 (f)
```

Arrows are queue order; table dependencies gate ticket completion, with slice exceptions below.
SA153 (h/j) and SA277 (a3) can ship before their ticket dependencies; SA153 (f) and SA277 (a2) wait for
SA191d (production). SA191d (retire) closes the ticket; (re-proof) owns publication, `develop`
deployment, and their integration checks. Operator publication of 0.89.0 follows SA191d. Each
slice ships with its own checks and handoff.

**Order.** Module migration history is frozen, so a module schema change ships as a new
migration. SA153's own tables live in the project-owned extension as `0002+` migrations.

### Track states

| Track | Next ticket / slice | Can start | Can finish | Can merge |
|---|---|---|---|---|
| 1 | SA153 (h) | yes | no: SA191d (production) for (f) | yes: (h/j) |
| 2 | SA191d (re-proof) | yes | no: SA191d operator gates | yes: SA191d (re-proof) |
| 3 | SA277 (a2) | no: SA191d (production) | no: SA191d (production) | no: (a2) waits for SA191d |

**Clearing blockers.** Track 1: SA191d (production) clears SA153 (f) (upstream only); ship
(h/j) meanwhile. Track 2: the operator's SA191d publication,
production-switch and retirement approvals. Track 3: SA191d
(production) clears (a2) (upstream only).

### Ownership and merge coordination

- Track 1: project-owned property extension, React pages and managed seam hooks, crawler views
  and journey checks.
- Track 2: `bap-web` cutover (SA191d), with joint publication and
  deployment; dependency manifests, locks and advisory disposition.
- Track 3: `beta_migration/`, supported-version fixtures, versioned upgrade prompt, and upgrade
  decision/operator guidance.
- One delivery candidate per track; serialize merges into `v89`.
- **Conflict surface:** this roadmap, CHANGELOG, the three audits, `project_contract.yml`,
  `decisions.md`, `bap-web`'s dependency lock, and `bap-web`'s frontend tests and routes
(`App.test.tsx`, `AppRoutes.test.tsx`; SA153 adds pages).
  Reconcile after each merge and run the consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

### Tracks 1–2 — property portal (1); suite reds and cutover (2)

**SA191d context.** Old `bap-web` (`~/code/bap-web-old`) serves production on Railway project
`bap-web` with no users and no production submissions. The regenerated `bap-web` (`~/code/bap-web`)
declares `auth`, `listings`, `forms`, `analytics`, `notifications`, `orgs`, and `storage`, the
`properties` app, and the six BAP forms. The cutover runs **in place**: per environment, a new
PostgreSQL 18 service restored from `~/bap-cutover/new-2026-10-22.dump`, new variables, and a
force-push over the unrelated history (kept as `legacy-main`, `legacy-develop`, `v-legacy`); the
old PostgreSQL 17 service stays as the rollback until acceptance, and DNS is never touched.
`develop` already runs it. The procedure and its run record are `bap-web/CUTOVER.md`. Secrets
live in `~/bap-cutover/` (mode 600), never printed or committed. After Railway's 2026-10-21
incident every old variable is exposed: none is carried, and the old PostgreSQL 17 credentials
are retired after the cutover. A QuickScale defect follows the release re-entry loop; a project
defect is fixed in `bap-web`.

- [ ] **SA191d — Cut over production to the regenerated `bap-web` in place (delegated, operator-gated).**

  One slice per session, each ending with a handoff note in `bap-web/docs/`. Every push, Railway
  change, and restore is an operator gate. **Production acceptance:** on `https://buenosairesproperties.com`,
  `/healthcheck/` prints `OK`, `/` and `/contact` render, a form submitted logged in and
  anonymously reaches `info@buenosairesproperties.com` through Resend, `/admin/` lists it, and
  the old PostgreSQL 17 service and legacy refs exist for rollback. Ticket completion also
  requires (retire), after which the dump and legacy refs remain as recovery artifacts.

  **Slices:**
  - [ ] (re-proof) Republish the changed modules once
    (joint release), update `bap-web`, push to `develop`, and re-pass the acceptance there with CI
    green and both dependency audits clean apart from the recorded dev-only exception (Tier 2-full).
  - [ ] (production) After re-proof and operator approval, execute `CUTOVER.md` § S4 steps 1–5;
    pass the production acceptance above, retaining the old database and legacy refs.
    **Tier 3: plan review required** — the production database/credential switch can lose data
    or expose credentials; review restore validation and rollback before execution.
  - [ ] (retire) After production acceptance and a separate operator gate, execute § S4 step 6:
    delete the develop Resend webhook and old PostgreSQL 17 service, retire exposed credentials,
    then rename the new service/volume after 48 hours; verify health and the retained dump/refs.
    **Tier 3: plan review required** — deleting the old database irreversibly removes live rollback.

- [ ] **SA153 — Deliver the first property portal using project-owned extensions.**

  Target `buenosairesproperties.com` with one React public property surface over a project-owned
  JSON read API under the [extension contract](module-extension.md), building on the React pages
  and `/api/properties/` the port carried over. No public API in `listings`, no generic property
  behavior in generated projects. Module-coupled data on new pages comes through seam-declared
  hooks in managed files (arch `generated-file-ownership-unmodeled`).

  **Acceptance:** the served documents (per-request head and crawler summary), the sitemap and
  robots views, and the search → detail → inquiry journey with organization isolation pass on the
  deployed site, and the extension/tenant declarations pass in `manage.py check`.

  **Slices:**
  - [x] (r)
  - [ ] (h) After (r), close only served-head, crawler-summary, sitemap and robots gaps in the
    project; request-level crawler tests pass with the existing React build (Tier 2-full).
  - [ ] (j) After (h), close search → detail → inquiry gaps; test organization isolation and
    extension declarations, with module data accessed through managed hooks (Tier 2-full).
  - [ ] (f) After (j) and SA191d (production), deploy and re-prove that journey on the live site
    with operator approval and a tested deploy-revert path (Tier 2-full).

- [ ] **SA154 — Property-portal capabilities to promote when a project needs them.**

  Tier 1 inventory review only: promote reusable property/React pages, translations, maps,
  saved searches, profiles, syndication, media, paid placement, cross-links or full-text search
  only for a concrete consumer, with bounded acceptance, dependencies and a track. Otherwise
  drop the item. Tenant schema changes use incremental migrations on the frozen history.

- [x] **SA309 — Clear `bap-web`'s pre-existing suite reds.**

### Track 3 — upgrade path

- [ ] **SA277 — Define the upgrade path for newer projects as `beta_migration` code plus a maintained prompt.**

  Addresses the upgrade-path part of arch `generated-file-ownership-unmodeled`; managed
  resource hooks remain SA153's scope. One path in two stages:
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
  - [x] (a3) Declare the supported source-version range; generate a test project at each supported
    version, pass `beta_migration` smoke runs, and version the upgrade prompt in QuickScale
    (Tier 2-full). Fixtures and prompt ship together without changing production projects.
  - [ ] (a2) After (a3) and SA191d (production), record the two-stage boundary and revocation
    triggers against the cutover evidence; confirm/amend the existing upgrade-path draft and
    remove duplicate operator steps (Tier 2-fast). Validate links and smoke instructions.

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Standing scope rules, presence contracts, and resource safeguards live in [decisions](decisions.md)
and [validation policy](validation_policy.md#candidate-review-and-integration).

**Unscheduled — React-theme browser coverage (Track 1, Tier 2-full per ordered slice).**
When activated: (A) wire `pnpm test:e2e` into generated CI and prove the existing smoke;
(B) add named journeys with passing browser checks; (C) add a depth-capped link crawler with
bounded traversal tests; (D) run the journeys on Docker within the E2E budget. Each consumes
its predecessor; no open-ended full-site crawl.

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
