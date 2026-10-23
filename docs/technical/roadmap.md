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
| SA191d | Cut over production to the regenerated `bap-web` in place (delegated, operator-gated) | 1 | SA308 | Required |
| SA153 | Deliver the first property portal using project-owned extensions | 1 | SA191d | Optional |
| SA154 | Property-portal capabilities to promote when a project needs them | 1 | SA153 | Inventory only |
| SA308 | Refresh the project lock; verify and document two dev-only advisory exceptions | 2 | — | Required |
| SA277 | Define the upgrade path for newer projects as `beta_migration` code plus a maintained prompt | 3 | SA191d | Optional |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA153 (r → h → j) ──► SA191d (re-proof → production → retire) ──► SA153 (f) ──► SA154
Track 2: SA308 (A → B → C)
Track 3: SA277 (a3) ──► SA277 (a2)
     critical path: SA308 ──► SA191d (re-proof → production → retire) ──► SA153 (f)
```

Arrows are queue order; table dependencies gate ticket completion, with slice exceptions below.
SA153 (r/h/j) and SA277 (a3) can ship before their ticket dependencies; SA153 (f) and SA277 (a2) wait for
SA191d (production). SA191d (retire) closes the ticket. SA308 (A) prepares the lock on Track 2;
SA191d (re-proof) owns publication, `develop` deployment, and their integration checks.
Operator publication of 0.89.0 follows SA191d. Each slice ships with its own checks and handoff.

**Order.** Module migration history is frozen, so a module schema change ships as a new
migration. SA153's own tables live in the project-owned extension as `0002+` migrations.

### Track states

| Track | Next ticket / slice | Can start | Can finish | Can merge |
|---|---|---|---|---|
| 1 | SA153 (r) | yes | no: SA308, then SA191d operator gates | yes: independent slices |
| 2 | SA308 (A) | yes | yes | yes |
| 3 | SA277 (a3) | yes | no: SA191d (production) evidence for (a2) | yes: (a3) |

**Clearing blockers.** Track 1: upstream SA308 completion, then SA191d's operator publication,
production-switch and retirement approvals; finish SA153's local slices meanwhile. Track 3: upstream
SA191d (production) clears (a2); ship (a3) first. No track waits to start.

### Ownership and merge coordination

- Track 1: `bap-web` cutover, project-owned property extension, React pages and managed seam hooks,
  crawler views and journey checks; joint publication and deployment in SA191d.
- Track 2: dependency manifests and locks, runtime pins, and advisory disposition in SA308;
  prepares `bap-web`'s lock without publishing or deploying it.
- Track 3: `beta_migration/`, supported-version fixtures, versioned upgrade prompt, and upgrade
  decision/operator guidance.
- One delivery candidate per track; serialize merges into `v89`.
- **Conflict surface:** this roadmap, CHANGELOG, the three audits, `project_contract.yml`,
  `decisions.md`, and `bap-web`'s dependency lock (Track 2 prepares; Track 1 consumes).
  Reconcile after each merge and run the consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

### Track 1 — cutover and the property portal

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
  - [ ] (re-proof) After SA308: republish the changed modules once
    (joint release), update `bap-web`, push to `develop`, and re-pass the acceptance there with CI
    green and both dependency audits meeting SA308's acceptance below (Tier 2-full).
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
  - [ ] (r) Inventory the existing `properties` API and React pages against acceptance; commit a
    gap list and runnable baseline checks without changing serving behavior (Tier 2-full).
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

### Track 2 — dependencies

- [ ] **SA308 — Refresh dependencies with open advisories in QuickScale and `bap-web`.**

  **Acceptance:** Python/production npm audits are clean in QuickScale and `bap-web`; full npm
  audits show only verified dev-only `braces`/`postcss-selector-parser` exceptions. No blanket
  ignores or Tailwind migration; fix production/build-output exposure or other findings first.

  **Ordered slices (Track 2):**
  - [ ] (A) Refresh `bap-web`'s lock for the merged floors using local build artifacts; commit
    the lock and pass backend/frontend suites, without publishing/deploying (Tier 2-full).
  - [ ] (B) After (A), capture Python plus full/production npm audits in both trees; trace each
    advisory's version, dependency chain, build use and shipped output. Prove the two findings
    are dev-only and production audits clean; fix any production exposure (Tier 2-full).
  - [ ] (C) After (B), document exact advisory IDs/versions/paths, evidence, toolchain risk, Track 2
    owner and expiry within 30 days in the technical audit. Recheck on fixes, dependency/exposure
    changes; remove fixed/expired exceptions. Unmatched audit findings block release (Tier 2-fast).

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
  - [ ] (a3) Declare the supported source-version range; generate a test project at each supported
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
