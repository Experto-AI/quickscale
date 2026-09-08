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
A previous green `make ci` does not discharge SA165's current red release verdict or validate later
product changes. Tagging, publishing, and deployment remain separate maintainer actions.
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
Track 2: (idle in v88)      owns post-v88 SA152, SA180
Track 3: (idle in v88)      owns post-v88 SA177
```

**Critical path: SA165 → SA160 → final release validation.** Every remaining v88 task is on it,
and all of it lives on track 1. There is no v88 filler work left and no parallelism left to win:
tracks 2 and 3 are idle for the rest of the release.

SA165 → SA160 is the only v88 task edge, and it gates one thing: the **emission-fixture
rebaseline**. SA165's frozen candidate binds
`quickscale_core/tests/fixtures/sa90_emission_manifests.json` until its verdict returns and
integrates. SA160's helper, its Vitest table, the dead-helper deletions, and their regressions may
all be authored before that, on track 1, and rebaselined once afterwards. SA165 needs review and
acceptance of already-landed implementation; do not restart its product work.

**Neither idle track can take v88 work.** SA160 is one review unit sharing two files with SA165's
frozen set — the emission fixture and `quickscale_core/tests/test_generator/test_generator.py`
(see SA160's acceptance) — and it cannot merge before SA165 either way, so moving it off track 1
would convert an intra-track ordering into a cross-track conflict for no schedule gain.

Post-v88 ordering: SA177 may take the isolation runner only after SA165 closes, which its horizon
supplies. SA152 and SA153 are independent — the portal can use a fresh generated project — though a
real-site cutover through the beta-migration tools would make SA152 a cutover prerequisite. SA154
follows the working portal, and SA180 owns the gate files SA152 also touches.

### Track states

Each track reports three independent states. A track is **truly green** only when all three
are yes.

| Track | Ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA165 | yes — diagnose retained red evidence | no — latest release E2E failed | no — needs resolved blockers and policy-compliant verdict | no | **yes** |
| 1 | SA160 | yes — authoring | no — needs SA165 | no — behind SA165 | no | **yes** |
| 2 | — | n/a — no v88 ticket | n/a | n/a | n/a | no |
| 3 | — | n/a — no v88 ticket | n/a | n/a | n/a | no |

- **Can start** — ***corrected after checkpoint attestation — not independently graded*** — SA165
  can start an evidence-led diagnosis from its retained failed release logs. Diagnosis comes first;
  it may support a policy-authorized unchanged-candidate retry or define a correction scope, but it
  does not make the current red green. SA160's helper, Vitest table, dead-helper deletions, and
  regressions remain authorable today.
- **Can finish** — ***corrected after checkpoint attestation — not independently graded*** — SA165
  cannot finish because its latest release verdict exited 2 in the
  Core and CLI E2E lanes. SA160's emission rebaseline still needs SA165's accepted verdict to
  release the fixture. Both are track-1 tickets, so this is an intra-track ordering, not a
  cross-track dependency.
- **Can merge** — ***corrected after checkpoint attestation — not independently graded*** — the
  diagnostics and this truthful bookkeeping checkpoint may integrate without claiming acceptance.
  SA165 itself cannot merge as accepted until the retained failures are diagnosed and either a
  reasoned, distinctly identified unchanged-candidate retry or a renewed review of changed candidate
  or validation inputs returns a green release verdict. SA160 remains behind SA165 in track 1's
  serialized order.

No v88 ticket is currently **truly green**. Every "no" above is a **hard dependency on resolving
SA165's red release verdict**. ***corrected after checkpoint attestation — not independently
graded*** — Current policy requires diagnosis first, permits a reasoned and distinctly identified
retry when the candidate is unchanged, and requires renewed review and validation when candidate or
validation inputs change.

### Ownership and merge coordination

- Track 1 owns generator templates, the CSRF helper, and emission-fixture updates. SA165's
  retained state-schema and isolation-runner changes stay on this track through acceptance.
- Track 2 owns gate documentation, `scripts/gate_registry.json` and module declarations, and the
  maintainer migration tools. It holds no v88 work; SA152 and SA180 are post-v88.
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
  Only track 1 has open v88 work, so no two v88 tickets run concurrently and the shared closeout
  set has a single writer until the release closes.
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

  The exact reviewed candidate is already on `v88` at object
  `fe5854cf2ed7789b14528b713628f11193664ae2`: corrupt/non-mapping YAML rejection before any write,
  identity-bound isolation skips with a negative control, `_HOST_DEPENDENT_PATHS` rationale, the
  generated local-credential warning, and the accepted SA170 fixture provenance. Historical object
  `573a57a34301e6a91971a7845095bd913bebd5e1` remains comparison context, not current authority. This
  delivery still needs a green verdict and closeout — including the former SA179 documentation work
  — rather than a restart of accepted implementation.

  **Candidate:** `quickscale_core/src/quickscale_core/schema/state_schema.py`,
  `scripts/test_isolation_conformance.sh`,
  `quickscale_core/tests/test_generator/test_generator.py`,
  `quickscale_core/src/quickscale_core/generator/templates/OPERATIONS.md.j2`, and
  `quickscale_core/tests/fixtures/sa90_emission_manifests.json`. The template and its already-landed
  manifest rebaseline must travel together; a review patch omitting the fixture manufactures a
  stale-hash finding that was already refuted.

  **Completed:** Track 1 object
  `8910f2f3a5afd09213c4e093b4dd4ff2023d41aa` extends the existing helper with bounded,
  best-effort backend and frontend logs and calls it before the failed-`up` assertion. Docker-free
  regressions cover service names and order, probe timeout continuation, Compose-plugin
  unavailability, failed-`up` ordering, and successful-`up` exclusion. The focused checks and CLI
  unit suite passed, and independent review found no remaining diagnostics finding.

  Two direct instrumented reproductions then passed independently in 55.80 and 54.51 seconds with
  exact-scope cleanup successful. Under the maintainer-approved relaxed causal gate, those results
  permitted continuation without claiming a cause or fix; the historical frontend failure remains
  unexplained and is an accepted residual risk. A fresh independent review subsequently passed the
  exact five-file current candidate and its callers/consumers, and immediate pre/post binding checks
  held `HEAD == v88 == fe5854cf2ed7789b14528b713628f11193664ae2` with a clean worktree.

  **Latest release evidence:** ***corrected after checkpoint attestation — not independently
  graded*** — The recorded command
  `setsid --wait env QS_E2E_PARALLEL=0 QS_E2E_INTEGRATION_REF=v88 make ci-e2e` ran once from
  2026-09-08 11:18:41 +02:00 through 11:42:12 +02:00. It reported script revision `fe5854cf` up to
  date with `v88`; install, static, coverage, and integration passed; E2E exited 1 and the aggregate
  command atomically recorded exit 2. Core reported 2 failed / 36 passed in 449.26 seconds:
  `test_sa142_backend_image_reuse_and_warm_build` and
  `test_sa142_no_cleanup_diagnostic_probe`. CLI reported 8 failed / 46 passed / 1 warning in 751.80
  seconds: `test_full_development_workflow`, `test_installed_wheel_plan_apply_up_all_modules`,
  `test_apply_with_docker_runs_migrations_in_container`, `test_up_down_lifecycle`,
  `test_up_with_build_flag`, `test_down_with_volumes`, `test_logs_with_options`, and
  `test_manage_test_command`. No cause was inferred and no release retry or diagnosis ran.

  Complete local evidence is retained at
  `/tmp/sa165-d-ev8-close-20260908T075701`; its 149-record manifest SHA-256 is
  `1d0e5af2f48db639626457c421f2c24416819cdf8aaa22a0d747d2acefe8936c`. Exact run-owned Docker
  scopes were cleaned to zero residue and the pre-existing `qscaletest` container, volume, and
  network were preserved. One pre-existing owner-only image disappeared during the run and five new
  owner-only images lacked lifecycle/scope labels; that foreign/unclassified image change remains
  unattributed and independently blocks calling the captured lifecycle green. Candidate bytes,
  all five authorized closeout documents, `HEAD`, and `v88` remained unchanged after the run.

  **Pending:** ***corrected after checkpoint attestation — not independently graded*** — Diagnose
  the retained Core and CLI failures before any retry; separately reconcile the Docker image
  ownership/lifecycle discrepancy; then choose the policy-authorized path: retain the bound candidate
  for a reasoned, distinctly identified retry, or apply evidence-backed corrections and renew review
  and validation. Only after a green release verdict, complete the changelog, ticket-context,
  technical-audit, architecture-audit, and open-work-only roadmap closeout. SA160's fixture
  rebaseline remains blocked until SA165 is accepted. This checkpoint records the halt and does not
  mark SA165 complete.

  **Blocking:** ***corrected after checkpoint attestation — not independently graded*** — The
  release-tier result is immutable and red, so it cannot support acceptance. The retained Core/CLI
  failures must be diagnosed and any necessary correction independently reviewed, while Docker
  ownership accounting must demonstrate a stable foreign baseline and zero unexplained run-owned
  residue or image drift. What closes this block is either a policy-compliant, distinctly identified
  retry of the unchanged bound candidate or a fresh verdict over renewed candidate/validation
  inputs, returning the complete success oracles, status 0, unchanged candidate/foreign resources,
  and exact run-scope cleanup.

  **Decisions needed:** ***corrected after checkpoint attestation — not independently graded*** — No
  additional maintainer grant is required for a reasoned, distinctly recorded retry of unchanged
  bytes within the already authorized delivery. If diagnosis requires product, test, runner, or
  validation-input changes, authorize their exact scope and renew review and validation. If Docker
  evidence assigns the image discrepancy to a foreign worktree, choose an exclusive shared-Docker
  window or another evidence-preserving coordination mechanism before the next verdict.

  **Remaining plan and resume object:** ***corrected after checkpoint attestation — not independently
  graded*** — Plan authority `EV-5` covered `B-repro`, `C-bind`, and `D-ev8-close`. `B-repro` and
  `C-bind` were accepted. `D-ev8-close` was dispatched once and returned partial, so no phase remains
  undispatched under that authority. Resume on `wt-track1` from the retained implementation baseline
  `fe5854cf2ed7789b14528b713628f11193664ae2` by inspecting the evidence directory above. Do not
  redispatch the closed `D-ev8-close` phase: route a reasoned unchanged-candidate retry under current
  validation policy, or obtain renewed reviewed authority when candidate or validation inputs change.

  **Remaining sequence:**

  1. Preserve and inspect the retained logs, event stream, inventories, and manifest; reproduce only
     the minimum failing Core/CLI surfaces needed to establish a cause. Do not run the release gate.
  2. Investigate the foreign/unclassified image discrepancy separately from repository failures;
     preserve resources outside the active worktree and never use broad or name-only cleanup.
  3. Define and authorize the correction scope from evidence. Fix relevant pre-existing issues only
     when the same evidence and ownership boundary includes them; do not infer a product defect.
  4. Run focused owning checks, freeze the resulting candidate, obtain independent whole-candidate
     review, and repeat exact pre-launch Git/content and Docker-baseline binding.
  5. ***corrected after checkpoint attestation — not independently graded*** — Apply the current
     validation policy: if candidate and validation inputs remain unchanged, record the reason and
     run a distinctly identified retry with immutable prior evidence; if either changed, renew review
     and validation before a fresh verdict. Capture complete process, output, Docker-event,
     inventory, cleanup, and provenance evidence in either branch.
  6. If and only if it is green, update the five closeout documents, run their consistency check,
     converge and attest the exact delta, commit it, and fast-forward `v88`. If it is red, preserve
     the evidence and keep SA165 open with another truthful checkpoint.

  ***corrected after checkpoint attestation — not independently graded*** — Independent review must
  return before a verdict when candidate or validation inputs changed; an unchanged-candidate retry
  follows the reasoned, distinctly recorded retry branch in current validation policy. No product,
  template, fixture, runner, or provisioner change is authorized by this checkpoint itself.

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
  - Keep the deletion clear of SA165's frozen candidate. `base.py.j2`'s settings-documentation
    block and the function body each contain `-TRUSTED_PROXY_COUNT`, and
    `test_generator.py::TestGeneratedProjectSettingsProxyMath` asserts that string survives in the
    generated `base.py`. Delete the function and reword the sentence naming it, but preserve the
    proxy-math comment, so no edit to `test_generator.py` is owed. Retarget the two dead-helper
    assertions in `test_templates.py` — which is outside the frozen set — at the orgs resolver.
  - Rebaseline emission parity once after both changes, review the whole candidate, and run the
    generator-change release tier once for that delivery. Retire the duplicate-cookie and dead
    settings-helper findings only with their regression evidence.

  **Surfaces:** React theme, generated settings, emission fixture, and technical audit.

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
  the written more-than-two-edit threshold on hand-pinned count literals. The closed documentation
  pass corrected the descriptions; correcting wording does not and cannot discharge the finding, so
  it is owned here rather than left as an unassigned note in the audit.

  **Acceptance:** compute the count-pinned gate-parity oracles from the registry and workflow
  sources they describe, so adding a gate or station cannot leave a stale literal behind. Keep the
  closed-universe check and the existing failure messages loud. Prove with a regression that adding
  a gate updates the derived count without a hand edit. Retire the count-pinned watch item only
  with that evidence. Renaming `trigger_inputs` stays out of scope: the field is the settled name for the
  bidirectional `e2e.yml` allowlist partition, and only a skip-based use would reopen it.

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
