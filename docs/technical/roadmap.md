# QuickScale Development Roadmap

> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

Ship 0.89.0 to production. Re-cut the 0.89.0 tag, update `bap-web` to it, prove it on
`bap-web` `develop`, cut over production to the same tag (SA191d), and publish 0.89.0 to PyPI
([publish_procedure.md](publish_procedure.md)). 0.89.0 is unpublished; a live 0.88.0 install moves
to it on a fresh database. The property portal (SA153, SA154) starts only after production runs
0.89.0 and it is on PyPI (see [Deferred — property portal](#deferred-property-portal)).

The scheduling table owns track, dependencies, and release requirement. Ticket bodies own
context, scope, acceptance, and each slice's tier; [CHANGELOG.md](../../CHANGELOG.md) preserves
history.

**Sizing.** Every slice carries an Adaptive tier
(Adaptive `docs/guides/operator-guide.md` § Planning and implementation):
Tier 1 is one bounded low-risk concern within direct context fit; Tier 2-fast is a specified
change with known targets, acceptance, and checks; Tier 2-full is one whose callers, mechanism,
or environment still need discovery, or that carries an open strategic choice. Audit work is
sliced to Tier 2, preferably Tier 2-full. Only SA191d (production) and (retire) stay Tier 3 with
plan review: their risk is the irreversible operation itself.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Track | Depends on | Release requirement |
|---|---|---|---|---|
| SA191d | Prove 0.89.0 on `bap-web` `develop`, then cut over production to it in place (delegated, operator-gated) | 2 | — | Required |
| SA277 | Define the upgrade path for newer projects as `website_migration` code plus a maintained prompt | 3 | SA191d | Optional |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: — (portal deferred)
Track 2: SA191d (re-proof ─► production ─► retire, operator-gated)
Track 3: SA277 (a) done ─► [SA191d (production)] ─► SA277 (b)
     release path: re-cut 0.89.0 ─► bap-web adopts it ─► SA191d (re-proof) ─► SA191d (production)
                   ─► publication ─► SA191d (retire)
     portal (deferred): publication ─► SA153 ─► SA154
```

Arrows are queue order; table dependencies gate ticket completion. SA277 (a) is complete; only
(b) remains, waiting for SA191d (production). SA191d (production) ships exactly the tag re-proof passed; a
defect found there follows the release re-entry loop (fix, re-cut, re-proof). Module migration
history is frozen: a module schema change ships as a new migration, and SA153's tables live in
the project-owned extension as `0002+` migrations.

### Track states

| Track | Next ticket / slice | Can start | Can finish | Can merge |
|---|---|---|---|---|
| 1 | — (portal deferred) | no: nothing queued | no: nothing queued | yes |
| 2 | SA191d (re-proof) | no: 0.89.0 tag re-cut | no: operator gates for (production), (retire) | yes |
| 3 | SA277 (b) | no: SA191d (production) | no: SA191d (production) | yes |

### Ownership and merge coordination

- Track 1: generated-project templates, the theme and managed hooks, release workflows, and
  the deferred portal.
- Track 2: `bap-web` cutover (SA191d), with joint publication and deployment; dependency
  manifests, locks and advisory disposition; module runtime code and tests in billing, CRM, orgs,
  auth, storage, forms, listings and notifications.
- Track 3: `website_migration/`, apply/update state and CLI commands, the contract-vintage gate,
  backups and `dr_engine`, module manifests/READMEs, repository gates, supported-version
  fixtures, versioned upgrade prompt, and upgrade decision/operator guidance.
- One delivery candidate per track; serialize merges into `v89`.
- **Conflict surface:** this roadmap, CHANGELOG, the three audits, `project_contract.yml`,
  `decisions.md`, and `bap-web`'s dependency lock.
  Reconcile after each merge and run the consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

### Track 2 — cutover

**SA191d context.** Old `bap-web` (`~/code/bap-web-old`) serves production on Railway project
`bap-web` with no users and no production submissions. The regenerated `bap-web` (`~/code/bap-web`)
declares `auth`, `listings`, `forms`, `analytics`, `notifications`, `orgs`, and `storage`, the
`properties` app, and the six BAP forms. The cutover runs **in place**: per environment, a new
PostgreSQL 18 service restored from `~/bap-cutover/new-2026-10-22.dump`, new variables, and a
force-push over the unrelated history (kept as `legacy-main`, `legacy-develop`, `v-legacy`); the
old PostgreSQL 17 service stays as the rollback until acceptance, and DNS is never touched.
`develop` already runs the regenerated stack (rehearsed 2026-10-23). The procedure and its run record are `bap-web/CUTOVER.md`. Secrets
live in `~/bap-cutover/` (mode 600), never printed or committed. After Railway's 2026-10-21
incident every old variable is exposed: none is carried, and the old PostgreSQL 17 credentials
are retired after the cutover. A QuickScale defect follows the release re-entry loop; a project
defect is fixed in `bap-web`. The module fixes reach `bap-web` as one update to the re-cut
0.89.0 tag before re-proof. `bap-web` keeps SA153 (h) (public
property head, crawler summary, sitemap, robots); its `properties` models must be classified in
the tenant contract, since the 2026-10-26 `develop` CI run failed the tenant isolation
conformance check on `properties.PropertyAgent` and siblings.

- [ ] **SA191d — Cut over production to the regenerated `bap-web` in place (delegated, operator-gated).**

  One slice per session, each ending with a handoff note in `bap-web/docs/`. Every push, Railway
  change, and restore is an operator gate. **Production acceptance:** on `https://buenosairesproperties.com`,
  `/healthcheck/` prints `OK`, `/` and `/contact` render, a form submitted logged in and
  anonymously reaches `info@buenosairesproperties.com` through Resend, `/admin/` lists it, and
  the old PostgreSQL 17 service and legacy refs exist for rollback. Ticket completion also
  requires (retire), after which the dump and legacy refs remain as recovery artifacts.

  **Slices:**
  - [ ] (re-proof) After the re-cut, update `bap-web` to the 0.89.0 tag, push
    it to `develop`, and pass the acceptance there as the release's final validation, with CI
    green (tenant conformance included) and both dependency audits clean apart from the recorded
    dev-only exception (Tier 2-full).
  - [ ] (production) After re-proof and operator approval, ship the same commit and tag: execute `CUTOVER.md` § S4 steps 1–5;
    pass the production acceptance above, retaining the old database and legacy refs.
    **Tier 3: plan review required** — the production database/credential switch can lose data
    or expose credentials; review restore validation and rollback before execution.
  - [ ] (retire) After production acceptance and a separate operator gate, execute § S4 step 6:
    delete the develop Resend webhook and old PostgreSQL 17 service, retire exposed credentials,
    then rename the new service/volume after 48 hours; verify health and the retained dump/refs.
    **Tier 3: plan review required** — deleting the old database irreversibly removes live rollback.

### Track 3 — upgrade path

- [ ] **SA277 — Define the upgrade path for newer projects as `website_migration` code plus a maintained prompt.**

  One upgrade path in two stages:
  `website_migration` does what it can mechanically; the prompt-driven port (`MIGRATION_PROMPT.md`,
  `CUTOVER.md`) handles what it reports it could not.

  **Acceptance:** decisions record the two-stage path (the gap ledger is the prompt's input, so
  neither stage repeats the other), the boundary rule (a gap that recurs across releases moves
  into code; a one-off stays in the prompt), the revocation trigger (a second long-lived project
  or a template security fix), and the steps-per-release count to watch, trending toward zero
  (58 declared steps on 2026-10-23). Operator docs do not duplicate steps either stage covers.
  Decisions say that supporting further projects meets the "second long-lived project"
  revocation trigger. "Website migration" is the name throughout (the `website_migration`
  package, CLI commands, docs and tests).

  **Slices:**
  - [x] (a) Renamed "beta migration" to "website migration" (`website_migration` in code, CLI,
    docs and tests); recorded the two-stage path, boundary rule and revocation triggers in
    decisions; removed operator steps either stage covers (Tier 2-fast).
  - [ ] (b) After SA191d (production), confirm them and the steps count against the cutover
    evidence; validate links and smoke instructions (Tier 1).

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Standing scope rules, presence contracts, and resource safeguards live in [decisions](decisions.md)
and [validation policy](validation_policy.md#candidate-review-and-integration).

<a id="deferred-property-portal"></a>

### Deferred — property portal (Track 1)

Not scheduled. Resumes only when SA191d (production) has passed and 0.89.0 is published; it is then re-added to the
scheduling table on top of the deployed `bap-web`.

**SA153 — Deliver the first property portal using project-owned extensions.**

Target `buenosairesproperties.com` with one React public property surface over a project-owned
JSON read API under the [extension contract](module-extension.md), building on the React pages
and `/api/properties/` the port carried over. No public API in `listings`, no generic property
behavior in generated projects. Module-coupled data on new pages comes through the generated managed
hooks, and project-owned tenant views
run in the generated isolation lane.

**Acceptance:** the served documents (per-request head and crawler summary), the sitemap and
robots views, and the search → detail → inquiry journey with organization isolation pass on the
deployed site, and the extension/tenant declarations pass in `manage.py check`.

**Slices:**
- (j) Close search → detail → inquiry gaps; test organization isolation
  under the restricted role and the extension declarations, with module data accessed through
  the managed hooks (Tier 2-full).
- (f) After (j), deploy and re-prove that journey on the live site
  with operator approval and a tested deploy-revert path (Tier 2-full).

**SA154 — Property-portal capabilities to promote when a project needs them (after SA153).**

Tier 1 inventory review only: promote reusable property/React pages, translations, maps,
saved searches, profiles, syndication, media, paid placement, cross-links or full-text search
only for a concrete consumer, with bounded acceptance, dependencies and a track. Otherwise
drop the item. Tenant schema changes use incremental migrations on the frozen history.

**Unscheduled — React-theme browser coverage (Track 1, Tier 2-full per ordered slice).**
When activated: (A) wire `pnpm test:e2e` into generated CI and prove the existing smoke;
(B) add named journeys with passing browser checks; (C) add a depth-capped link crawler with
bounded traversal tests; (D) run the journeys on Docker within the E2E budget. Each consumes
its predecessor; no open-ended full-site crawl.

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
