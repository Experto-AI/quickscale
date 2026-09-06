# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap**
> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Ticket context](v88_ticket_context.md) | [Changelog](../../CHANGELOG.md)

## Goal and release finish line

Ship the v88 hardening release with working generated-project writes and accepted retained
hardening. Then deliver the first useful property portal in a
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
| SA174 | Close out the landed command-set and gate-input documentation | v88 | 2 | — | Optional |
| SA152 | Verify maintainer migration modes and their runtime compatibility | post-v88 | 2 | — | Deferred |
| SA180 | Derive the gate-parity count oracles from the registry | post-v88 | 2 | — | Deferred |
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

**Critical path: SA165 → SA160 → final release validation.** It is the only chain with two
required tasks in series, and it lives entirely on track 1. SA174 is optional and shortens
nothing. Work that does not advance SA165 or SA160 is parallel filler, however useful.

Start both open v88 track heads independently. SA165 needs review and acceptance of already-landed
implementation; do not restart its product work. SA174 is a bounded documentation closeout.

SA165 → SA160 is the only v88 task edge, and it gates only the **emission-fixture rebaseline**:
SA165's frozen candidate binds `quickscale_core/tests/fixtures/sa90_emission_manifests.json` until
its verdict returns and integrates. SA160's helper, its Vitest table, the dead-helper deletions,
and their regressions may be authored before that, on track 1, and rebaselined once afterwards.

Track 3 holds no v88 work, and no v88 work can move to it: SA160 shares the emission fixture with
SA165 and is one review unit, and SA174 shares its gate files with track 2's post-v88 SA152 and
SA180. SA177 targets the accepted SA172 helper and may take the isolation runner only after SA165
closes; its post-v88 horizon supplies that ordering. SA152 and SA153 have no hard dependency on
each other — portal development can use a fresh generated project — though a real site cutover
through the beta-migration tools would make SA152 acceptance a cutover prerequisite. SA154 follows
the working portal, and SA180 follows SA174 in ownership of the same gate files, not in code.

### Track states

Each track reports three independent states. A track is **truly green** only when all three
are yes.

| Track | Ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA165 | yes | yes | yes | **yes** | **yes** |
| 1 | SA160 | yes — authoring | no — needs SA165 | no — behind SA165 | no | **yes** |
| 2 | SA174 | yes | yes | yes | **yes** | no — optional filler |
| 3 | — | n/a — no v88 ticket | n/a | n/a | n/a | no |

- **Can start** — no v88 track waits on a decision, authorization, or plan gate. SA160's helper,
  Vitest table, dead-helper deletions, and regressions are executable today.
- **Can finish** — every acceptance criterion is satisfiable by its own track, except SA160's
  emission rebaseline, which needs SA165's verdict to release the fixture. Both are track-1
  tickets, so this is an intra-track ordering, not a cross-track dependency. Docker-backed
  validation remains a scheduling queue, not a dependency.
- **Can merge** — no *track head* is order-gated: SA165 and SA174 may each merge whenever accepted.
  SA160 sits behind SA165 in track 1's own serialized order, which is sequencing within a track,
  not a cross-track gate.

Every "no" above is a **hard dependency on SA165's `EV-8` verdict**, not a decision of yours: only
the returned review and release run can clear it. **No v88 track is held by a pending decision.**

### Ownership and merge coordination

- Track 1 owns generator templates, the CSRF helper, and emission-fixture updates. SA165's
  retained state-schema and isolation-runner changes stay on this track through acceptance.
- Track 2 owns gate documentation, `scripts/gate_registry.json` and module declarations, and the
  maintainer migration tools. SA174 changed descriptions, never gate schema or emitted bytes.
- Track 3 owns deferred predicate conformance under SA177. It may take the isolation
  runner only after SA165 has closed; its post-v88 horizon supplies that ordering without a live
  cross-track implementation overlap.
- Product implementation stays in worktrees, with one delivery candidate at a time per track and
  one serialized merge queue into `v88`. Independent work does not wait for another track's audit
  markdown edits. Reconcile shared documentation at merge time on the owning worktree.
- **Conflict surface.** The cross-track shared closeout set is this roadmap,
  [CHANGELOG.md](../../CHANGELOG.md), [ticket context](v88_ticket_context.md) when concepts change,
  and the owning audit. Every one of them is Markdown with append-or-edit
  semantics and no generated consumer, and the serialized merge queue plus reconcile-on-the-owning-
  worktree rule above covers them: each track resolves the shared set once, at its own merge, after
  the previous merge has landed. The consistency test then checks structure, not status prose.
  No product file is co-owned by two open v88 tickets, so no merge hazard is created by running
  SA165 and SA174 at the same time.
- The active task requiring Docker-backed acceptance owns that validation slot. Other tracks may
  prepare and run DB-free checks concurrently. Private PostgreSQL profiles do not claim the standing
  service; coordinate Docker-heavy runs across active tracks. See the
  [execution policy](validation_policy.md#candidate-review-and-integration) for routing, cleanup,
  candidate binding, and review/merge rules.

### Resuming a track

Measure state; do not read it from this planner. Check the assigned branch, divergence from `v88`,
staged/unstaged changes, untracked files, and any merge in progress, then read the diffs and prior
evidence before deciding anything is blocked. A dirty worktree is a recovery step, not a stop
condition: cleanliness is required for the frozen review and the merge, never for inspection or
for continuing understood, in-scope edits. A shared filename alone is a merge concern; a changed
input to an active reviewed candidate is a real dependency.

Preserve before you reconcile. Stage an explicit reviewed file list and make a clearly labeled
WIP checkpoint for work that would otherwise be lost — a checkpoint is not acceptance and must not
enter `v88` as a completed delivery. Never sweep unrelated work in with `git add .`, never
auto-drop a stash, and never use destructive reset or checkout to manufacture a clean status.
Then merge `v88` into the worktree, resolve conflicts there, run the consistency suite, and
continue the task's own validation. Merge only the reviewed and accepted delivery, through the
serialized queue. Stop only at a concrete unresolved ownership conflict, missing authority, or
failed prerequisite, naming the affected files and action.

Each outgoing handoff records the task, inspected diff, checkpoint or stash identity, remaining
changes, conflicts, evidence obtained, and the exact next command. Keep that record in the handoff
or delivery evidence, not here.

## v88 deliveries

- [ ] **SA165 — Accept retained hardening and record its closeout.**

  The reviewed product bytes are already on `v88` at object
  `573a57a34301e6a91971a7845095bd913bebd5e1`: corrupt/non-mapping YAML rejection before any write,
  identity-bound isolation skips with a negative control, `_HOST_DEPENDENT_PATHS` rationale, and the
  generated local-credential warning. This delivery adds the verdict and the closeout — including
  the former SA179 documentation work — not new implementation. No product repair is owed.

  **Candidate:** `quickscale_core/src/quickscale_core/schema/state_schema.py`,
  `scripts/test_isolation_conformance.sh`,
  `quickscale_core/tests/test_generator/test_generator.py`,
  `quickscale_core/src/quickscale_core/generator/templates/OPERATIONS.md.j2`, and
  `quickscale_core/tests/fixtures/sa90_emission_manifests.json`. The template and its already-landed
  manifest rebaseline must travel together; a review patch omitting the fixture manufactures a
  stale-hash finding that was already refuted.

  **Acceptance sequence:**

  1. Supply an independent reviewer the complete materialized base-to-tip patch, clean-tip
     evidence, and the five-file context. The three `test_generated_tree_matches_manifest`
     variants and `test_operations_md_warns_generated_credentials_are_local_only` must be green.
  2. After a green review, recheck candidate inputs and run
     `QS_E2E_INTEGRATION_REF=v88 make ci-e2e`, recording actual exit status, provenance, and exact
     cleanup evidence. This remains a required release verdict; historical stale-but-green evidence
     cannot replace it. The first replacement retains the `EV-8` evidence label. Apply the
     [candidate policy](validation_policy.md#candidate-review-and-integration) to any subsequent
     attempt; a red or unreturned run is never acceptance.
  3. Record the verdict and retire only the four audit notes it discharges. Prepare the
     documentation commit in the same worktree/delivery and merge it through the same queue.
     Review-recording documents and their structural consistency test are outside the frozen
     product set, so recording the verdict does not invalidate it.

  Independent review must return before the verdict is launched. No additional ticket is needed to
  record results, recover an interrupted verification, or correct an in-scope defect; changed
  product inputs need renewed review and validation.

- [ ] **SA160 — Fix generated CSRF handling and remove dead settings helpers.**

  Closes TA67 and TA68. Deliver one combined candidate — the CSRF helper and the former SA161
  dead-code removal — and one emission-fixture rebaseline, preserving every previous
  `baseline_evidence` entry and recording a separate rationale for each emitted file change. Author
  the code and tests whenever track 1 is free; land the rebaseline only after SA165's verdict
  releases the fixture. The two halves are independent in code but share the single rebaseline, so
  splitting them buys no parallelism and costs a second fixture handoff, review, and generator run.

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

- [ ] **SA174 — Close out the landed command-set and gate-input documentation.**

  **All three corrections are already on `v88`** — the `orgs/apps.py` multi-owner comment, the
  `trigger_inputs` allowlist-partition definition in `check_gate_parity.py` and the registry, and
  the reconciled architecture watchlist. Nothing is left to author; this is evidence and closeout
  only. No declaration, gate behavior, registry field, or emitted byte changed.

  **Acceptance:** run the focused gate-parity checks and lint appropriate to the touched
  descriptions, obtain independent review of the landed documentation delta, and record the
  closeout. No generator run or emission rebaseline is owed for comments alone. The confirmed
  count-oracle trigger stays open as SA180 and is not closed here; no watch item closes merely by
  being restated. Broader command consolidation, new gate mechanisms, and a registry field rename
  are outside scope.

  **Surfaces:** `quickscale_modules/orgs/.../apps.py`, `scripts/check_gate_parity.py`,
  `scripts/gate_registry.json`, `scripts/README.md`, and the architecture audit.

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

- [ ] **SA180 — Derive the gate-parity count oracles from the registry.**

  The architecture audit confirmed this trigger **fired** — `d31c6b41` and `437dd0e0` each crossed
  the written more-than-two-edit threshold on hand-pinned count literals. SA174 corrected the
  descriptions; it does not and cannot discharge the finding, so it is promoted here with its own
  owner rather than left as an unassigned note in the audit.

  **Acceptance:** compute the count-pinned gate-parity oracles from the registry and workflow
  sources they describe, so adding a gate or station cannot leave a stale literal behind. Keep the
  closed-universe check and the existing failure messages loud. Prove with a regression that adding
  a gate updates the derived count without a hand edit. Retire the count-pinned watch item only
  with that evidence. Renaming `trigger_inputs` stays out of scope under SA174's settled decision.

  **Surfaces:** `scripts/check_gate_parity.py`, `scripts/test_gate_parity.py`,
  `scripts/gate_registry.json` if a derivation source is needed, and the architecture audit.

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
