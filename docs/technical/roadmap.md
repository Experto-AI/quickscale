# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap**
> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Ticket context](v88_ticket_context.md) | [Changelog](../../CHANGELOG.md)

## Goal and release finish line

Ship the v88 hardening release with working generated-project writes, accepted retained hardening,
and an idempotent RLS enrollment helper. Then deliver the first useful property portal in a
project-owned extension, generalizing capabilities only after that project proves their value.

The release is ready when every **required** v88 delivery below is accepted, the final integrated
candidate passes the release tier in [validation policy](validation_policy.md#validation-tiers),
including E2E for generator changes, and release notes and version/package checks are complete.
A previous green `make ci` does not discharge SA165's outstanding candidate verdict or validate
later product changes. Tagging, publishing, and deployment remain separate maintainer actions.
Optional maintenance may move past the release without delaying it.

This planner holds open work only. A single scheduling table owns horizon, track, dependencies,
and release requirement. Ticket bodies own scope and acceptance; [context](v88_ticket_context.md)
explains implementation concepts; [CHANGELOG.md](../../CHANGELOG.md) preserves history and evidence.
Absorbing a ticket transfers its unfinished obligations and does not claim its finding is fixed.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Horizon | Track | Depends on | Release requirement |
|---|---|---|---|---|---|
| SA165 | Accept retained hardening and record its closeout | v88 | 1 | — | Required |
| SA160 | Fix generated CSRF handling and remove dead settings helpers | v88 | 1 | SA165 | Required |
| SA174 | Correct command-set and gate-input documentation and watchlists | v88 | 2 | — | Optional |
| SA152 | Verify maintainer migration modes and their runtime compatibility | post-v88 | 2 | — | Deferred |
| SA177 | Verify the predicates of enrolled RLS policies | post-v88 | 3 | — | Deferred |
| SA153 | Deliver the first property portal using project-owned extensions | post-v88 | 1 | — | Deferred |
| SA154 | Property-portal capabilities to promote when a project needs them | post-v88 | 1 | SA153 | Inventory only |

Track numbers map to the existing worktrees: **1 = W1 / wt-track1**, **2 = W2 / wt-track2**,
**3 = W3 / wt-track3**. Post-v88 assignments identify future ownership, not authorization to
start them during release work. SA154 is an inventory, not an implementation queue.

```text
Track 1: SA165 ──► SA160 ──► final release validation and closeout
Track 2: SA174              optional; runs alongside track 1
Track 3: SA177              deferred post-v88
```

Start both open v88 track heads independently. SA165 needs review/acceptance of existing
implementation; do not restart its product work. SA174 is a bounded documentation change.
On track 1, begin SA160's product/fixture changes only after SA165's reviewed candidate has passed
its verdict and integrated. That is the one v88 task dependency: SA165 binds the same emission
fixture that SA160 rebaselines. Combining the old dead-code and CSRF tickets removes a second
fixture handoff and validation cycle. The longest dependency chain is SA165 → SA160; elapsed
critical-path duration still depends on measured review and validation times on every track.

SA177 follows SA172 so its policy oracle targets the accepted helper. SA152 and SA153 have no
hard product dependency on each other: portal development can use a fresh generated project.
If the eventual site cutover uses the beta-migration tools, their SA152 acceptance becomes a
cutover prerequisite; it does not block building the portal. SA154 follows the working portal.

### Ownership and merge coordination

- Track 1 owns generator templates, the CSRF helper, and emission-fixture updates. SA165's
  retained state-schema and isolation-runner changes stay on this track through acceptance.
- Track 2 owns gate documentation, `scripts/gate_registry.json` and module declarations if later
  work needs them, and the maintainer migration tools. SA174 changes descriptions, not gate schema.
- Track 3 owns deferred predicate conformance under SA177. It may take the isolation runner only
  after SA165 has closed; its post-v88 horizon supplies that ordering without a live cross-track
  implementation overlap.
- Product implementation stays in worktrees, with one delivery candidate at a time per track and
  one serialized merge queue into `v88`. Independent work does not wait for another track's audit
  markdown edits. Reconcile shared documentation at merge time on the owning worktree.
- Shared closeout files are this roadmap, the changelog, ticket context when concepts change, and
  the relevant audit. Other documents link to the schedule instead of copying counts or readiness.
  The consistency test checks structure, not exact status prose. No new tracking framework is needed.
- The active task requiring Docker-backed acceptance owns that validation slot. Other tracks may
  prepare and run DB-free checks concurrently. Private PostgreSQL profiles do not claim the standing
  service; coordinate Docker-heavy runs across active tracks. See the
  [execution policy](validation_policy.md#candidate-review-and-integration) for routing, cleanup,
  candidate binding, and review/merge rules.

Before starting or resuming a delivery, measure branch divergence and working-tree status; do not
persist tips or clean/dirty claims as planner state. A shared filename alone is a merge concern,
not a product dependency. A changed input to an active reviewed candidate is a real dependency.

### Recovery before the next handoff

**A dirty worktree is a recovery step, not a stop-before-discovery condition.** Read this roadmap,
inspect the assigned task and existing diffs, and evaluate dependencies before deciding what is
blocked. Cleanliness is required for the eventual sync, frozen review, and merge; it is not required
for read-only inspection or continuing understood, in-scope edits. The following recovery is part
of each next-task handoff. Re-measure everything in the new session; do not infer completion from
an old report or draft changelog entry.

1. **Inspect and preserve.** Check the assigned branch, staged/unstaged changes, untracked files,
   and any merge already in progress. Read the diffs and prior evidence. Coordinate with any active
   writer before snapshotting its work. Preserve recoverable copies of tracked changes and needed
   untracked files before reconciliation; do not discard changes to manufacture a clean status.
2. **Checkpoint unfinished work.** In the assigned worktree, stage an explicit reviewed file list
   and make a clearly labeled WIP/retained checkpoint for the existing task. It is not acceptance
   and must not enter the integration branch as a completed delivery. Keep unrelated work separate;
   never sweep it into the task with `git add .`. If a named stash is necessary, record its exact
   identity, include relevant untracked files, and retain it until restoration is verified. Do not
   auto-drop stashes, overwrite unknown files, or use destructive reset/checkout commands.
3. **Publish the shared planning checkpoint once.** The track 1 handoff coordinates this bootstrap
   with the maintainer: inspect and commit the already-approved roadmap simplification and its
   companion files currently in `/home/victor/code/quickscale` on `v88`, using an explicit file list
   and the focused consistency check below. This preserves existing planning work; it is not
   product implementation on the integration branch. If already committed, verify and reuse it.
   Tracks 2 and 3 must not independently commit, stash, or clean the shared checkout. They may
   inspect `/home/victor/code/quickscale/docs/technical/roadmap.md` and preserve their own work while
   awaiting this checkpoint: `git merge v88` cannot transfer uncommitted planning edits.
4. **Sync and reconcile.** Once local work is preserved and the planning checkpoint is committed,
   merge `v88` into the assigned worktree. Inspect existing in-progress merges before issuing a
   new merge. Resolve conflicts there, preserving useful implementation and historical evidence.
   Use the consolidated schedule and structural consistency checks; do not restore the old ticket
   queue, exact-prose assertions, or unsupported completion claims from a WIP checkpoint. Run the
   roadmap/context consistency suite after reconciliation, then continue the task's own validation.
5. **Resume, review, and integrate.** Reuse valid prior work, obtain any missing independent review
   and candidate-bound validation, and merge only the accepted delivery through the serialized
   queue. If `v88` becomes dirty again, coordinate with its writer and defer only the affected
   merge; inspection and independent local work may continue. Stop only at a concrete unresolved
   ownership conflict, missing authority, or failed prerequisite, naming the affected files and
   action rather than reporting only “worktree not clean.”

Each outgoing handoff records the task, inspected diff, preservation/checkpoint or stash identity,
remaining changes, any conflicts, evidence obtained, and the exact next command/action. Keep this
transient record in the handoff or delivery evidence rather than adding branch-status tables here.

### Next handoff — track 1

Resume **SA165** in `/home/victor/code/quickscale-wt-track1` on `wt-track1`. First coordinate the
single shared planning checkpoint above, then sync the track. Preserve local changes if present;
do not create a WIP commit when there is nothing to preserve. Continue the five-file product review
and release verdict described below; exclude review-recording documentation from the frozen product
set. After accepted integration and documentation closeout, proceed to **SA160**. No other track
must finish its product task before this review can begin; coordinate Docker-backed validation.

### Next handoff — track 2

Resume **SA174** in `/home/victor/code/quickscale-wt-track2` on `wt-track2`. Inspect and checkpoint
the retained former-SA178 changes in `scripts/check_gate_parity.py`, `scripts/gate_registry.json`,
`scripts/test_gate_parity.py`, `scripts/README.md`, and the associated audit/planning documents.
After syncing the planning checkpoint, reuse the compatible `trigger_inputs` documentation and
regressions, then finish the privileged-command comment/docstring and watchlist reconciliation.

The retained review reports that the count-oracle trigger already fired, citing `d31c6b41` and
`437dd0e0`. Verify that evidence and preserve the finding; do not restore a blanket “not fired”
claim. If confirmed, record a separately scoped follow-up with an owner, dependency assessment,
and promotion rationale. Oracle redesign is not part of SA174, and its implementation is not a
prerequisite for correcting the documentation. Keep the finding open and do not revise its trigger
merely to obtain a green closeout. Reconcile old SA178 completion/dependency prose to SA174's
current scope, then validate and obtain review. No product dependency on track 1 or 3 is added.

## v88 deliveries

- [ ] **SA165 — Accept retained hardening and record its closeout.**

  Includes the former SA179 documentation closeout in the same delivery, after product acceptance.
  Retained product object `573a57a34301e6a91971a7845095bd913bebd5e1` covers corrupt/non-mapping YAML
  rejection without modifying the file, identity-bound isolation skips with a negative control,
  `_HOST_DEPENDENT_PATHS` rationale, and the generated local-credential warning. Accepted A–C
  evidence stays in the changelog; no product repair is currently owed.

  **Candidate:** `quickscale_core/src/quickscale_core/schema/state_schema.py`,
  `scripts/test_isolation_conformance.sh`,
  `quickscale_core/tests/test_generator/test_generator.py`,
  `quickscale_core/src/quickscale_core/generator/templates/OPERATIONS.md.j2`, and
  `quickscale_core/tests/fixtures/sa90_emission_manifests.json` as reviewable context. The template
  and its already-landed manifest rebaseline must travel together. The historical stale-hash
  finding was refuted; omitting the fixture from the review patch caused it. Do not redo that repair.

  **Acceptance sequence:**

  1. Sync the owning worktree, verify the retained product binding, and supply an independent
     reviewer the complete materialized base-to-tip patch, clean-tip evidence, and the five-file
     context. The three `test_generated_tree_matches_manifest` variants and
     `test_operations_md_warns_generated_credentials_are_local_only` must be green.
  2. After a green review, recheck candidate inputs and run
     `QS_E2E_INTEGRATION_REF=v88 make ci-e2e`, recording actual exit status, provenance, and exact
     cleanup evidence. This remains a required release verdict; historical stale-but-green evidence
     cannot replace it. The first replacement retains the `EV-8` evidence label. Apply the
     [candidate policy](validation_policy.md#candidate-review-and-integration) to any subsequent
     attempt; a red or unreturned run is never acceptance.
  3. Integrate the reviewed product tip, then record the verdict and retire only the four audit
     notes it discharges. Prepare the documentation commit in the same worktree/delivery and
     merge it through the same queue. Review-recording documents and their structural consistency
     test are outside the frozen product set, so recording the verdict does not invalidate it.

  There is no mandatory root-session boundary between these steps. Independent review still must
  return before the verdict is launched. No additional ticket is needed merely to record results,
  recover an interrupted verification, or correct an in-scope defect; changed product inputs need
  renewed review and validation. New product scope remains separately planned.

- [ ] **SA160 — Fix generated CSRF handling and remove dead settings helpers.**

  Includes the former SA161 dead-code removal. Deliver one combined template candidate and one
  emission-fixture rebaseline, preserving every previous `baseline_evidence` entry and recording
  a separate rationale for each emitted file change.

  **Acceptance:**

  - Replace the duplicate cookie parsers in `themes/showcase_react/src/hooks/useApi.ts` and
    `src/components/forms/FormRenderer.tsx` with one `src/lib/` helper. Match cookie names exactly,
    decode values, and select a token deterministically when duplicate names occur. Both callers
    use it; no third implementation remains. A Vitest table covers duplicate cookies, a preceding
    session cookie, a single cookie, and no cookie. Verify the selected token and write-request
    header behavior, not only that a string is non-empty.
  - Delete unreachable `get_client_ip` definitions in `settings/base.py.j2` and
    `settings/production.py.j2` and the misleading production-rebind comment. Preserve uppercase
    proxy settings and `REST_FRAMEWORK["NUM_PROXIES"]` recomputation. A generated-project regression
    proves settings import and the live orgs client-IP resolver retain their expected behavior.
  - Rebaseline emission parity once after both changes, review the whole candidate, and run the
    generator-change release tier once for that delivery. Retire the duplicate-cookie and dead
    settings-helper findings only with their regression evidence.

  **Surfaces:** React theme, generated settings, emission fixture, and technical audit.

- [ ] **SA174 — Correct command-set and gate-input documentation and watchlists.**

  Includes former SA178, using its documentation-only option instead of a field rename.

  **Acceptance:**

  - Correct the comment and docstring in `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py`:
    the privileged-command set is one of four independent fail-closed declarations, not a single
    source of truth. Name the module guard, production settings validator, CLI producer, and
    `start.sh` launcher. No declaration or emitted byte changes.
  - Document `trigger_inputs` as the bidirectional partition of the E2E workflow path allowlist
    in the parity checker and its schema description. Keep the field name and behavior. Record
    the trigger for reassessment if it starts deciding whether a gate runs.
  - Reconcile the architecture watchlist once. Demote the privileged-command finding under the
    settled two-command decision, retaining its trigger (a third command or disagreement). Preserve
    the provisioning module-count/`teams` trigger, PostgreSQL-major agreement trigger, count-pinned
    oracle triggers, and SA92 watch trigger. No watch item is closed merely by restating it.

  **Validation:** focused gate-parity checks and lint appropriate to the touched descriptions;
  required pre-merge checks follow validation policy. No generator run or emission rebaseline is
  owed for comments alone. Update the audit in the same delivery. Broader command consolidation,
  new gate mechanisms, and a registry field rename are outside scope.

## Post-v88 work

- [ ] **SA152 — Verify maintainer migration modes and their runtime compatibility.**

  Includes former SA175. Compare outcomes within each migration mode, not membership in constants
  from different modes. Donor-carried `settings/production.py` and substituted infrastructure may
  be intentional; a blanket assertion rejecting that arrangement while preserving it cannot be
  the acceptance condition.

  **Acceptance:** name the launcher/settings contract once and derive each mode's effective file
  sources for `settings/production.py`, `start.sh`, and `Dockerfile`. Preserve the accepted donor
  precedence. Exercise compatible and deliberately incompatible file combinations in isolated
  fixtures through the existing validation seam, proving the compatible contract passes and an
  unsupported privileged-command/runtime combination fails for the intended reason. Do not turn
  an expected file classification into a claim of runtime compatibility.

  In the same smoke suite, run fresh-first dry-run and in-place checkpoint-only workflows on a
  generated donor/recipient pair, without modifying a real project or database. Reconcile the
  in-place database precondition with the fresh-database migration policy. Replace missing-template
  `pytest.skip()` with a tested explicit failure. Register the smoke gate in the existing registry,
  keep gate parity green, and correct the migration playbook's version/location claims. Retire only
  discharged findings; the broader ownership-model finding remains behind its growth triggers.

  **Surfaces:** `quickscale_devtools/.../beta_migration.py`, CLI ownership/migration tests, existing
  gate registry and parity wiring, Make/CI entrypoints as needed, and migration playbook. No public
  updater, typed ownership framework, or changed file precedence is included.

- [ ] **SA177 — Verify the predicates of enrolled RLS policies.**

  **Acceptance:** walk enrolled tables and compare both policies' stored `qual` and `with_check`
  expressions in `pg_policies` against the rendered expected policies, accounting for PostgreSQL's
  catalog representation. A deliberately weakened predicate must fail for the intended reason;
  restore the exact policy after the negative control. Preserve tenant-write/operator-read
  semantics and existing RLS boundary checks. Retire the predicate-conformance tooling gap only
  after this proof. Reassess priority if later work changes policy semantics before this lands.

  **Surfaces:** isolation-conformance runner, orgs policy template/tests, and technical audit.

- [ ] **SA153 — Deliver the first property portal using project-owned extensions.**

  Target the planned `buenosairesproperties.com` use case with one Django-rendered public surface.
  Use the documented project-owned extension pattern for property models, views, URLs, filters,
  and templates. Do not require a public JSON API, a second React public implementation, or generic
  property behavior in every generated project to launch the first site.

  **Acceptance:** a fresh generated project with listings serves an organization-scoped property
  catalog and detail page with ordered image galleries; bedrooms, bathrooms, area, property type,
  and sale/rent fields; keyword and attribute filters; and explicitly labeled currencies. Its
  public listing/blog pages share a usable theme and render in Spanish, with locale middleware
  and translated strings needed by this public flow. A listing inquiry creates a CRM record with
  a listing reference. Add sitemap entries, `robots.txt`, and Open Graph output for the public
  detail pages. Correct reusable-module feature claims to match what the module itself provides.

  Every new tenant-owned child table has its own `organization_id`, forced RLS, and boundary tests;
  no parent-join policy replaces that requirement. Prove the user journey from search through
  detail to inquiry, and isolation between organizations. Keep property-specific glue in the
  project extension and avoid direct edits to embedded module code. Validate any required shared
  extension seam narrowly. A real-site data cutover requires a verified data/migration path and
  explicit deployment scope; building this delivery does not authorize production mutation.

  **Surfaces:** project-owned property extension and public templates first; listings/blog/forms/CRM
  seams only where necessary, plus extension documentation. Broad module translation and generic
  no-project-glue integration are deferred until reuse demonstrates a need.

- [ ] **SA154 — Property-portal capabilities to promote when a project needs them.**

  Inventory only: public read API and an alternate frontend; generalizing the proven property
  extension into reusable modules; broader translations; maps/geocoding; saved searches, favorites,
  and alerts; agent/office profiles; portal syndication; tours/video; paid placement; blog/listing
  cross-links; and PostgreSQL full-text search beyond basic keyword filtering.

  Promote an item only with a concrete consumer, bounded acceptance criteria, and a fresh dependency
  and track assignment. Listing it does not authorize implementation or make it a launch blocker.
  Close the inventory only when its items have been promoted or explicitly dropped with rationale.

## Deferred constraints and references

The live [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md)
own deferred findings and their exact growth triggers. Do not duplicate those lists here. The
standing no-`teams`/third-updater scope, internal-only devtools decision, settled presence contracts,
and resource safeguards remain in [decisions](decisions.md) and
[validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_v88_ticket_context_consistency.py -q -o addopts= --no-cov`.
That test checks ticket/context coverage, valid track and horizon assignments, and acyclic
dependencies; it does not certify a release verdict. Release evidence belongs in the changelog.
