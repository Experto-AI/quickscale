# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Changelog](../../CHANGELOG.md) | [Validation Policy](validation_policy.md) | [v88 Ticket Context](v88_ticket_context.md) | [Release Summary Template](release_summary_template.md)

## Purpose

This is the current task planner. It holds **open work only**. Completed tickets, closed findings,
review evidence, and release records are archived in [CHANGELOG.md](../../CHANGELOG.md) and removed
from here rather than marked done. No checked entry is permitted.

### Execution rules

- Work develops in three worktrees (**W1** module wiring + generated-output fixes, **W2** gate layer + declared wiring, **W3** service lifecycle and its exclusive PostgreSQL/Docker slot) and merges into the clean `v88` integration branch. Never implement directly on the integration branch. A ticket that does not fit an existing lane is sequenced inside one, not given a new lane.
- One reviewed child runs at a time per worktree. Umbrellas are acceptance-only; their children own implementation.
- Before merge-back: sync the integration branch into the worktree, resolve there, run the ticket's verification, review the exact tip, then merge that tip.
- Every handoff declares its file allowlist, commands, expected exits/artifacts, rollback, and focused validation. Scope findings are ticketed rather than fixed in place.
- Leave `make quality` no worse than found. Do not raise a complexity ceiling or reintroduce file-line ceilings. The current baseline has zero warning regressions, zero critical regressions, and monotonicity passes.
- Shared closeout conflict surfaces are `CHANGELOG.md`, `docs/technical/roadmap.md`, `docs/technical/v88_ticket_context.md` when a ticket's concepts change, and `docs/technical/decisions.md` when policy changes. Both audit docs join that surface only when a ticket changes or closes a live finding.
- A roadmap edit that changes a W1/W2/W3 state block must re-run `quickscale_core/tests/test_v88_ticket_context_consistency.py` in the same change, and two state blocks must never share a state header — a duplicate header makes the test's anchors bind to the wrong block.
- PostgreSQL/Docker work is serialized across worktrees. **W3 holds the exclusive PostgreSQL/Docker slot** and takes scheduling priority whenever one of its legs is active.
- **Local database-lane operating constraint:** `make test-integration` and `make test-bypassrls`
  use the same twelve databases and differ only by role. `scripts/provision_ci_postgres.sh run
  --profile {restricted,bypassrls}` owns that ownership flip; drive both lanes through it rather
  than by hand, and leave `quickscale_test_role` owning all twelve afterwards. Hosted CI uses
  separate ephemeral servers; this applies to the shared local cluster only.
- **W1's wiring leg (SA167d) may not touch `scripts/gate_registry.json` or any `module.yml`.** Those are W2-owned surfaces.
- A ticket whose deliverable is Git ref state cannot be delegated to a file-editing worker. Route it to a maintainer session with ref authority and push credentials.
- **Long gates must be run detached, not merely with a raised timeout.** `make check` measures
  **601 s green** on `v88` (41 s when it fails fast — a red run is not a timing sample). That
  exceeds the 600 s ceiling of a single foreground tool call, so waiting on it inline is killed by
  construction. Launch with `nohup`, write the exit code to a file, poll for the file. Same for
  `make test` and `make quality`. A run killed by a cutoff returns no exit code and is **not
  evidence** — neither of green nor of red. One recorded acceptance stall was caused by exactly this,
  and the gate underneath turned out to be red.
- **A gate that is red on the integration branch is attributed to exactly one ticket, and is never
  deselected.** Test exclusion via `PYTEST_ADDOPTS`, `--deselect`, or a Makefile/CI edit is not a
  scheduling tool: it removes the oracle for the defect the owning ticket exists to fix. Name the
  owner, let the other lanes run unexcluded and treat their evidence as provisional, and merge
  nothing until the owner lands. The 2026-08-28 interim known-red protocol is retired for exactly
  this reason and must not be revived.
- **Terminal attestation must be handed its input.** Generate the complete base-to-tip patch to a
  file (`git diff <base>..<tip> > <name>.patch`) and supply it together with a clean-byte binding
  (`git status --porcelain` empty at the exact tip). A reviewer that cannot obtain the patch returns
  *no grade*, which costs a full attestation cycle and proves nothing.

---

## v88 release plan

### Priority model

Audit-derived prerequisites and implementation tickets share one ranked queue.

> **Ordering rule.** A ticket that makes a gate *tell the truth* outranks a ticket that makes the
> product *better*, because every other ticket's acceptance criteria are discharged by those gates.
> Below that, order by longest dependency chain, then by exclusive-resource ownership, then by tier.

| Band | Rule | Tickets |
|---|---|---|
| **A — Restore enforcement** | Gate layer reports green while not running, or runs red on HEAD. | **SA173** — `make check` runs red on `v88` HEAD (measured 2026-08-28; see below) |
| **B — Release work on the critical paths** | The two longest serialized chains, one holding the exclusive service slot. | SA167c (critical path, after SA173); SA135; SA170; SA167d |
| **C — Bounded independent fixes** | No dependants, small blast radius; absorbed as slack filler. | SA160, SA161, SA164, SA165, SA166, SA171, SA172, SA174, SA175 |

### Band A is open — `make check` runs red on `v88` HEAD, for a new reason

**Measured 2026-08-28 on `v88` at `4e410c09`, detached, from a clean tree — `make check` exits 2:**

```text
✅ Linting passed!     ✅ Type checking passed!
quickscale_core:  2886 passed, 1 skipped
quickscale_cli:     18 failed, 2135 passed
```

**The two original SA173 target tests now pass.** `quickscale_cli/tests/test_module_wiring_manager_manifest.py`
is **43 passed**, and the ticket's ordered verification step 1 is **221 passed**. The merged product
commit `e0730ae9` discharged them. Band A did not close, though — it changed shape.

**What is red now.** Eighteen failures, reproducible in isolation as `18 failed, 149 passed` over
just the two files — no pollution, no `e2e`, no ordering dependency. They are **two distinct causes
with different remedies**, and conflating them would get one of them fixed wrongly:

| Cause | Where | Count | Remedy |
|---|---|---|---|
| **A — missing consumer policy (product defect)** | `quickscale_cli/tests/test_status_command.py` | 11 | fix the CLI; **do not edit the tests** |
| **B — stale test fixtures** | `quickscale_cli/tests/commands/test_module_config_extended.py` | 7 | fix the fixtures; **do not weaken `apply`** |

**Cause A — `status` aborts on the drift it exists to report.** SA173 acceptance criterion 5 deleted
the CLI's `if "Manifest file not found" in str(error)` skip at `module_wiring_manager.py:201` and
moved the decision into core. That was correct. But the CLI's **reaction was never written to
replace it**, so `status` now aborts on a module that `.quickscale/state.yml` registers and the
project tree does not carry:

```text
❌ Installed module manifest error during 'status':
  • [auth] Manifest file not found for module 'auth': <project>/modules/auth/module.yml
Aborted!    (exit 1, via _abort_for_manifest_error at status_command.py:229, from :845)
```

Three of the eleven are literally `test_status_detects_missing_modules`,
`test_module_tracking_completeness`, and `test_json_drift_filesystem_drift_populated`. `status` is
the *diagnostic* command; aborting is the one reaction it must not have when it finds drift. D3
already prescribes the answer — consumers own their reaction, `status` **reports**, `apply` **fails
hard**. One policy was written, the other was deleted and left empty. **These eleven tests are the
correct oracle and must not be edited.**

**Cause B — `apply`'s fail-hard is correct; seven fixtures predate it.** These fail differently, at
`module_config.py:546`:

```text
❌ Managed wiring regeneration failed: Managed adapter wiring failed:
   Module presence is incomplete: module 'auth' is missing manifest '<tmp>/myproject/modules/auth/module.yml'
```

The fixtures at `test_module_config_extended.py:961,983` (and the CRM equivalents) create
`modules/<name>/` containing only a `pyproject.toml`. Under the new contract that is INCOMPLETE, and
refusing to wire it is the behaviour SA173 was opened to produce. **The same file already has the
right helper** — `_write_module_package` (`:139-150`) writes `module.yml` alongside `pyproject.toml`
— and `e0730ae9` already gave the lifecycle fixtures this treatment; this file was simply not
included. Route these seven through the helper. **Assertions do not change, and `apply` does not
become tolerant.** One thing to confirm while doing it, so the classification is not assumed: that
the real embed path writes `module.yml` before wiring regeneration runs. If it does, these are
fixtures. If it does not, this is a second product defect and gets its own entry rather than a
fixture edit.

**A third regression, outside `make check` entirely.** `poetry run pytest scripts/` returns
**5 failed, 1313 passed**, all five in `test_version_tool.py::TestUpdateWithTempRepo`.
`quickscale_core/.../contracts/module_discovery.py` is contracted to run as a **standalone shim** —
`scripts/version_tool.sh:14,34` copies that one file into a tree with no importable
`quickscale_core` package and calls `--list-modules` to enumerate the modules it must version-bump.
`e0730ae9` put a catalog import on that path behind a guard that only tolerates
`exc.name == "quickscale_core.contracts.module_catalog"`, while a shim tree fails at the root package
and raises `exc.name == "quickscale_core"`. Widening the guard then exposes a second defect: the
twelve-module release count is enforced against a hermetic tree that legitimately holds fewer.
**Both belong to SA173** (open item 1c) — it is the same contract change, and `version_tool.sh` is a
release-inventory consumer the ticket did not enumerate. This one is invisible from the repo root,
where `--list-modules` prints the twelve names and exits 0.

**Consequences.**

1. **SA173 stays band A.** The gate layer runs red on HEAD; by the ordering rule this still outranks
   every other ticket.
2. **W1 and W3 still cannot finish on their own lanes.** SA167d's and SA135's closeout campaigns
   both require `make check` green on a candidate synced to current `v88`.
3. **The scope is now small and named**, which it was not before this measurement: one consumer
   policy in `status_command.py`, seven fixture rewrites, one two-part standalone-shim repair, and
   the one open consistency edge below.
4. **SA167d (#18, W1) inherits cause B's seven directly.** `commands/test_module_config_extended.py`
   is inside its focused validation command. They are not W1's to fix — SA173 owns them — and they
   clear when #30 merges.

#### Interim known-red protocol — **retired 2026-08-28, superseded**

The two-node-id `PYTEST_ADDOPTS` deselect recorded in the previous pass is **void**: both node ids
now pass, so the exclusion silently excludes nothing and the eighteen real failures are not among
them. **Do not carry it forward, and do not widen it to the eighteen** — that would deselect the
oracle for the defect SA173 is open to fix, which is the exact failure the original protocol was
written to prevent.

**W1 and W3 run unexcluded from here.** Their own campaigns are green on their own surfaces; what
they cannot obtain is a green `v88` for merge evidence, and no deselect can manufacture that. Both
lanes may run their *provisional* campaigns today knowing `make check` on the integration branch is
red for a cause neither lane owns and neither lane may touch — SA173's, in
`quickscale_cli/src/quickscale_cli/commands/{status,apply}_command.py`. Provisional evidence accepts
a lane's own work; it never accepts a merge. No lane merges until SA173 lands.

#### Gate cost — budget against these, run detached

`make check` measures **~601 s green** and **~40 s when it fails fast at `test-unit`** (`Makefile:377`);
a red run is not a timing sample. The green figure exceeds the 600 s ceiling of a single foreground
tool call, so `make check`, `make test`, and `make quality` must be launched with `nohup`, writing
the exit code to a file that is then polled. A run killed by a cutoff returns no exit code and is
**not evidence** — neither of green nor of red. One recorded acceptance stall was caused by exactly
this, and the gate underneath turned out to be red. The dominant cost is `lint-frontend`, which
renders the theme variants, installs their dependencies, and runs ESLint plus `tsc` twice.

The previously recorded *"broad CLI validation returned no verdict at 120 s and again at 360 s"*
blocker is **closed by diagnosis**: run detached, the suite completes in seconds and the verdict is
the eighteen failures above. It was never a stall; it was a foreground cutoff on a run that also
happened to be red.

#### Full-suite baseline

`make check` filters with `-m "not integration and not e2e"`. The unfiltered combined suite does not.
The 2026-08-28 pre-`e0730ae9` measurement was **7 failed / 5134 passed / 16 skipped in 1:18:19**;
its two SA173 rows are now green, and the four `e2e` rows below are **SA170's** and are carried
forward unre-measured — an 80-minute run is not repeated to restate an attribution no ticket disputes.

| Failure | Marked `e2e`? | In `make check`? | Owner |
|---|---|---|---|
| `test_status_command.py` × 11, `commands/test_module_config_extended.py` × 7 | no | **yes** | **SA173** (new, measured at `4e410c09`) |
| `test_e2e_development_workflow.py::…::test_logs_with_options` | yes | no | **SA170** |
| `test_e2e_development_workflow.py::…::test_manage_test_command` | yes | no | **SA170** |
| `test_e2e_installed_wheel_lifecycle.py::test_installed_wheel_plan_apply_up_all_modules` | yes | no | **SA170** |
| `test_e2e_full_workflow.py::TestDockerIntegration::test_sa142_no_cleanup_diagnostic_probe` | yes | no | **SA170** |

The prior baseline's seventh row —
`test_module_discovery.py::TestAuthoritativeModuleNames::test_partial_generated_override_uses_bundled_shipped_inventory`
— was an order-dependent pollution artifact on the OVERRIDE→bundled path. SA173's merged commit
**removed that path**, so the trap is gone and the row is retired rather than carried.

### Dependency graph and critical path

```text
v88 — three worktrees, fourteen open merge positions carrying fourteen open ticket entries, one merge queue

W2 (gates & declared wiring)   ★ CRITICAL PATH
  SA173 ─► SA167c ─► SA166 ─► SA164     #30, #21, #24, #25
  (SA173's contract merged at `e0730ae9`; its CLI consumer policy is open and holds `make check` red.
   SA167c's Phase-A slice merged, A retry gated on SA173, B-F open)

W1 (module wiring + generated-output fixes)
  SA167d ─► SA165 ─► SA161 ─► SA160 ─► SA174 ─► SA175     #18, #22, #19, #20, #31, #32

W3 (service lifecycle — exclusive PostgreSQL/Docker slot)
  SA135 ─► SA170 ─► SA171 ─► SA172      #15, #27, #28, #29
```

**W2 sets the release date.** The critical path is four positions —
`SA173 ─► SA167c ─► SA166 ─► SA164` — entirely inside W2 with no prerequisite outside it. W3 holds
the exclusive slot and therefore takes scheduling priority while one of its legs is active, but its
four positions are a *queue*, not a *chain*. **Finishing SA167d or SA135 does not shorten the
release; finishing SA173 does** — and SA173 is additionally the branch-state gate that every lane's
merge evidence waits on, so it is the only work on the board that is both truly green and on the
critical path. W1 is the longest lane at six positions, but its four tails are band C and may slip
past the release, so it does not set the date.

**Position count is unchanged this pass.** No ticket opened, closed, or moved lanes; the change is
that SA173's scope was re-measured and narrowed to a named defect.

**No cross-worktree dependency edges remain.** Two cross-worktree *shared files* do, both made
one-directional by merge order:

- `scripts/test_isolation_conformance.sh` — SA135's merged partial wrote it; SA165 (#22, W1)
  narrows one line over those settled bytes. #15 merges before #22.
- `.../settings/production.py.j2` — **no longer cross-worktree.** Moving the privileged-command
  finding off SA164 (W2) onto SA174 (#31, W1) leaves this file with two W1 owners, SA161 (#19) then
  SA174 (#31), sequenced on one lane. The prior #19-before-#25 caution is retired.

**One cross-lane hazard already fired, and is recorded here so it is not repeated.** W3's merged
SA135 remediation `203fcd61` added the `OVERRIDE`→bundled fallback in
`quickscale_core/.../contracts/module_discovery.py`, which changed inventory behaviour and turned
**W2's** SA167c caller suite red two days later. Neither ticket's file allowlist named the other's
surface, because the coupling is behavioural rather than textual: `quickscale_core/contracts/` and
`quickscale_core/manifest/` are read by every lane. **Treat any edit under those two packages as
cross-lane**: announce it in the merge queue and re-run the other lanes' focused caller suites
before merging, even when no file is shared. SA173 owns both packages for the rest of v88 — and its
own 2026-08-28 regression is the second instance of the same shape, this time inside one lane: a
core-contract change that turned eighteen CLI tests red without touching them.

The manifest-reading `entry_point.py`, the fail-hard `QUICKSCALE_LOCAL_WHEELHOUSE` version-spec
seam, the regenerated migration baseline, and `scripts/provision_ci_postgres.sh` (the single
PostgreSQL environment contract landed by the closed SA163) are settled tree state that open
tickets build on rather than re-open.

### Track rebalance — evaluated this pass, **no move made**

The prior pass's two moves stand and are not restated here; they are archived in
[CHANGELOG.md](../../CHANGELOG.md). Lanes are **W1 6 · W2 4 · W3 4**. Each open ticket was re-tested
against the three rebalance questions — is it independent of the rest of its lane, is another lane
idle, and is it on or feeding the critical path — and **none passes all three**:

- **W1's four band-C tails (#19, #20, #31, #32) cannot move to W3.** They are DB-free generator and
  module-wiring work. Putting DB-free tickets on the exclusive-slot lane is the exact defect the
  previous pass corrected by moving SA161/SA160 the other way; redoing it would re-serialize them
  behind SA135 and SA170 for nothing. They also form one ordered emission-parity rebaseline run
  (#19 → #20 → #31), which may not be split.
- **SA165 (#22) looks moveable to W3 and is not.** It shares `scripts/test_isolation_conformance.sh`
  with SA172 (#29, W3), so the move would make that file single-lane — a real gain. But SA165 is
  DB-free, and moving it would place it *behind* SA135 and SA170 on the slot lane, delaying a ticket
  that today only waits on lane ordering. The shared file is already one-directional under merge
  order #15 → #22 → #29. **Cost exceeds benefit; not moved.**
- **Nothing may move onto or off W2.** `scripts/gate_registry.json` and `quickscale_modules/*/module.yml`
  are W2-owned surfaces that never cross worktrees, and SA173's remaining scope is the presence
  contract's own consumer policy. Splitting it from SA167c, the ticket it blocks, would force a
  cross-lane sync in the middle of an acceptance chain.

**W1 is the longest lane at six positions and that is deliberate**: it is off the critical path, so
band-C work accumulates there rather than behind the release-setting chain. Band-C positions are
*earliest-eligible*, not commitments, and may slip past the release; the four W1 tails are the slip
budget. **Conflict surface for every lane is unchanged** — the standing closeout files
(`CHANGELOG.md`, this file, `docs/technical/v88_ticket_context.md`, plus an audit document when a
ticket closes a live finding), which the merge procedure's sync-resolve-rerun-review step already
covers.

### Lane state

**Verified 2026-08-28.** `wt-track3` is an ancestor of `v88`, merged and idle.
**`wt-track2` now holds an unmerged SA173 product candidate at
`4c311a73ef445dfd48e4b3cda4563ca345259661` and is 1 ahead / 1 behind `v88` at
`3a16b3106ae06872c18b254e95a8e5d5fdafde9d`.** It must sync and repeat the frozen-candidate
validation before merge. **`wt-track1` holds SA167d's separate unmerged product delta:** clean at `f392641c`,
carrying the accepted E0 tip and convergence corrections at `8b20800d`. Measure current ahead/behind
rather than relying on any transcribed count:

```bash
for w in wt-track1 wt-track2 wt-track3; do echo -n "$w: "; git rev-list --left-right --count v88...$w; done
```

W1's next sync may conflict in `docs/technical/roadmap.md`; resolve in the worktree keeping this
file's structure, and re-run the consistency test in the same change.

The binding constraint is physical, not a ticket edge: one PostgreSQL 18 cluster on
`localhost:5432` holding the twelve shared `test_quickscale_*` databases, which W3 needs *empty*.
W1's SA167d phase-E `make test` and W3's SA135 E1 campaign must be scheduled serially around it. No
ticket move relieves that; only scheduling does. **SA173's remaining work needs no cluster** — its
eighteen failing tests are CLI-level and run in seconds — so W2 is not in contention at all.

### Next action per lane

- **W2 — resume SA173 (#30) from the unmerged candidate
  `4c311a73ef445dfd48e4b3cda4563ca345259661` in `wt-track2`; do not reimplement its product work.**
  First raise `quickscale_modules/storage/src/quickscale_modules_storage/__init__.py` from 45% to the
  required 80% per-file coverage with legitimate tests or production simplification. Then sync
  current `v88` into the worktree, resolve there, run the complete unexcluded frozen-candidate
  campaign and cross-lane callers, reconcile the closeout documents, review the exact new tip, and
  merge it. SA167c (#21) stays blocked until that sequence is accepted and merged.
- **W3 — resume SA135 (#15) at phase E1, unexcluded.** Do not redo C or D, and do not attempt the
  E2E Docker failures — they are SA170's. SA135's remaining scope is **the PostgreSQL-lifecycle
  evidence and the `validation_policy.md` precondition update only**. An executable plan is written
  into the ticket below; no plan-authoring step remains before dispatch. Its own campaign can go
  green today; only the merge waits on SA173.
- **W1 — SA167d's phase E is accepted; the lane needs closeout, not re-implementation.**
  `wt-track1` is clean at `f392641c`. What remains is one full validation campaign on a synced frozen
  candidate and one terminal attestation supplied with the complete base-to-tip patch — the input
  whose absence, not any finding, ungraded the last attempt. Schedule `make test` outside W3's
  window. W1's tail runs six positions (#18, #22, #19, #20, #31, #32); the last four are band C and
  may slip, with **SA174 (#31)** the one worth pulling forward if slack appears.

### Track readiness — the three states

A lane is **truly green** only when all three are yes. *Can start* = the next action is executable
today. *Can finish* = the ticket can reach a checked box using only work on its own lane. *Can
merge* = merge-back is not order-gated behind another lane.

| Lane | Head | Can start | Can finish | Can merge | On the critical path |
|---|---|---|---|---|---|
| **W2** | SA173 (#30, unmerged partial) | **yes** — resume from `4c311a73`; no product reimplementation or decision is pending | **no** — storage coverage, documentation closeout, sync, and final validation remain | **no** — the candidate is 1 ahead / 1 behind current `v88` and is not merge-ready | **yes** — band A, and it gates both other lanes' merges |
| **W1** | SA167d (#18) | **yes** — unexcluded; schedule `make test` outside W3's window | **provisionally** — its own work reaches green, but final acceptance needs a green `v88` | **no — gated on SA173 (#30)** | no |
| **W3** | SA135 (#15) | **yes** — unexcluded; take the exclusive slot first | **provisionally** — same gate | **no — gated on SA173 (#30)** | no |

**W2 remains the critical-path lane, but it is not truly green.** Its product candidate is retained
and independently reviewed, yet the required storage coverage gate, documentation closeout, sync,
and final frozen-candidate evidence remain. W1 and W3 can start and can produce provisional evidence,
but neither can close a ticket until #30 lands. No maintainer decision is pending; the remaining
inputs are implementation, integration, independent review, and acceptance evidence.

**No open maintainer decision remains anywhere in this plan.** D3 and the placeholder-declaration
policy are settled; the eighteen-failure regression has one correct resolution that D3 already
prescribes (consumers own their policy) and is not a judgement call. The remaining inputs everywhere
are execution, independent review, and acceptance evidence.

Downstream positions are lane-ordering only and clear by the upstream work or by a maintainer
reordering the lane, with four exceptions that no reorder clears: **SA167c after SA173**,
**SA160 after SA161**, **SA174 after SA160** (the emission-parity rebaseline run of three), and
**SA164's substance after SA167c**.

### Handoff checklist — applies to all three lanes

Every lane's worktree lags `v88`. Before any ticket work:

1. **Sync.** Merge `v88` into the worktree and resolve there, never on the integration branch.
   Expect a conflict in `docs/technical/roadmap.md`; keep this file's structure.
2. **Re-run the consistency test in the same change** if a W1/W2/W3 state block moved:
   `poetry run pytest quickscale_core/tests/test_v88_ticket_context_consistency.py -q -o addopts= --no-cov`.
3. **Claim the cluster.** `make test`, `make test-integration`, and `make test-bypassrls` all use
   the twelve shared `test_quickscale_*` databases. Drive the lane flip through
   `scripts/provision_ci_postgres.sh run --profile {restricted,bypassrls}` and leave
   `quickscale_test_role` owning all twelve afterwards. **W3 has priority whenever one of its legs
   is active.**
4. **Announce core-package edits.** A change under `quickscale_core/contracts/` or
   `quickscale_core/manifest/` can turn another lane red without sharing a file — see the recorded
   `203fcd61` precedent. Only SA173 should be touching them in v88.
5. **Reproduce the ticket's measured starting state** before changing anything. Every open ticket
   below states one.
6. **Merge back** by re-running the ticket's own verification on the exact reviewed tip, then
   merging that tip.

#### Settled decision D3 — module presence is a three-state fact (2026-08-28)

**Chosen: Option 3 — split the question at the layer that loses it.** Discovery reports ABSENT /
ACTIVE / INCOMPLETE, **each consumer owns its own reaction**, the subset-validity rule has one
implementation, and nothing classifies module presence by string-matching an exception message. The
policy is written in [decisions.md → Module Presence States](decisions.md#module-presence-states)
and implemented by **SA173 (#30)**; the full investigation — the traced run, the three unreconciled
commits, and the rejected Options 1 and 2 — is archived in [CHANGELOG.md](../../CHANGELOG.md) and is
not restated here.

**The clause that is still being paid for.** *Each consumer owns its own reaction* is half of the
decision, not a footnote to it. Removing a consumer's classification without writing its policy
leaves the consumer with no behaviour at all — which is precisely SA173's open regression: the CLI's
substring test was deleted, `status`'s report-as-drift policy was never written, and `status` now
aborts on drift. **Deleting a wrong policy and writing the right one are one change, not two.**

*Cost, stated plainly.* The critical path grew by one ticket. That was accepted deliberately.

#### Standing rules carried from closed decisions

- **W3 holds the exclusive PostgreSQL/Docker slot.** W3 may stop the container `pg18-af10` for a
  strict-acceptance window and **must restart it afterwards** (`docker start pg18-af10`); the
  container must not be removed, its volume must not be pruned, and the twelve `test_quickscale_*`
  databases plus `quickscale_test_role` ownership must be intact when W1 and W2 next run.
- **Neither `teams` nor a third generated-project updater is in v88.** The arch audit's
  `generated-file-ownership-unmodeled`, `deletion-invariants-per-boundary-reimplementation`, and
  `org-model-universe-hand-enumerated` stay behind their growth triggers. A v88 ticket may not
  widen into them; a fired trigger is a scope finding and gets its own ticket. **One narrow
  carve-out, added 2026-08-28:** where the audit itself marks a step as *independent of the trigger*,
  that step alone may be ticketed, and only as written. SA175 (#32) is the sole instance — a
  coherence assertion over the existing taxonomy. It does not derive the taxonomy, add typed
  disposition metadata, emit an ownership manifest, or change any file's current disposition, and
  the finding stays open with its trigger intact.
- **Roadmap documentation ownership is Option A** — open work only; completed work is archived.
- **Local database-lane ownership flip** — whichever of `make test-integration` and
  `make test-bypassrls` is about to run must own the twelve test databases first. The closed SA163
  made the two lanes coexist through per-profile ownership, but the local cluster is still shared.
- **SA165 (#22) stays behind SA167d (#18) on W1** (decided 2026-08-27). W1 runs one reviewed child
  at a time, so band-C filler does not preempt an open band-B acceptance even when the two share no
  file. Revisit only if SA167d is abandoned rather than merged.
- **SA123's coupled-test authority is closed;** its provisioning-literal obligation was discharged
  by the closed SA163.
- **Module presence is a three-state fact** (D3, 2026-08-28). Discovery reports ABSENT / ACTIVE /
  INCOMPLETE; consumers own their policy; the subset-validity rule has one implementation; nothing
  classifies module presence by string-matching an exception message. Binding on every lane —
  see [decisions.md](decisions.md#module-presence-states).
- **`quickscale_core/contracts/` and `quickscale_core/manifest/` are cross-lane surfaces.** Every
  lane reads them, so a behavioural change there can turn another lane red without sharing a file.
  SA173 owns both for the rest of v88; anyone else touching them announces it in the merge queue.
- **Band-C filler must not displace a band-B leg.**

### Merge order

One queue. Within a worktree, one reviewed child at a time; a ticket syncs the integration branch
into its worktree, resolves there, reruns its own verification, then merges its exact reviewed tip.

| # | Ticket | Band | Tier | Worktree | Merges after | Service slot |
|---|---|---|---|---|---|---|
| 15 | **SA135** | B | 2 | W3 | — | **yes** — PostgreSQL + Docker |
| 18 | **SA167d** | B | 3 | W1 | — | no |
| 19 | **SA161** | C | 3 | W1 | SA165 | no |
| 20 | **SA160** | C | 2 | W1 | SA161 | no |
| 21 | **SA167c** | B | 2 | W2 | SA173 | no |
| 22 | **SA165** | C | 3 | W1 | SA167d | no |
| 24 | **SA166** | C | 3 | W2 | SA167c | no |
| 25 | **SA164** | C | 3 | W2 | SA166 | no |
| 27 | **SA170** | B | 2 | W3 | SA135 | **yes** — Docker |
| 28 | **SA171** | C | 2 | W3 | SA170 | no |
| 29 | **SA172** | C | 3 | W3 | SA171 | no |
| 30 | **SA173** | **A** | 1 | W2 | — | no |
| 31 | **SA174** | C | 2 | W1 | SA160 | no |
| 32 | **SA175** | C | 3 | W1 | SA174 | no |

**Branch-state gate, not a queue edge: nothing merges before SA173.** `make check` is red on `v88`
(see *Band A*), so every lane's merge evidence is unobtainable until #30 lands. This is deliberately
**not** recorded as a `deps:` edge on #15 and #18 — it is not a content dependency between tickets,
it is the state of the integration branch, and it clears for all lanes at once the moment SA173
merges. The merge-order table above is otherwise unchanged.

Positions #1, #2, #3, #4, #5, #6, #6b, #7, #8, #9, #10, #11, #12, #13, #14, #16, #17, #23, and #26 are **retired and not
reused**; their tickets are closed and archived in [CHANGELOG.md](../../CHANGELOG.md). Gaps carry no meaning. Position
#15 was shared with SA163 until that ticket closed on 2026-08-28; it now carries SA135 alone.

The per-lane heads are **#30 (W2, partial — contract merged at `e0730ae9`, consumer policy open),
#18 (W1, partial), and #15 (W3, partial)**. #21 is no longer a lane head — it now merges after #30.
Of the partials: #21 has a merged Phase-A slice at `f6f3bbce` with A unaccepted pending SA173's
contract and B-F outstanding; #18 is a phase-E-accepted candidate on `wt-track1` at `f392641c`
awaiting one validation campaign and one attestation; #15 has a merged partial with C/D accepted and
E outstanding after SA163's share of it closed.

Most "Merges after" edges are lane ordering — a queue position, clearable only by the upstream work
or by a maintainer reordering the lane. Three are **hard content dependencies** that no reorder
clears: **SA160 after SA161** (shared emission-parity rebaseline of `sa90_emission_manifests.json`;
the pair must not be split, and **SA174 appends the third rebaseline entry** after them, so the run
of three is ordered #19, #20, #31), **SA164's substance after SA167c** (its
`test_sa92_migration_squash_guardrail.py` work needs `django_apps:` retired), and **SA167c's
Phase-A acceptance after SA173** (two of its four caller tests are answered by the presence
contract; rerunning A before SA173 lands reproduces the same red). Band-C positions
(19, 20, 22, 24, 25, 28, 29, 31, 32) are *earliest-eligible*, not commitments, and may slip past the
release. **SA174 (#31) is the one band-C position worth pulling forward if slack appears**: it
carries the structural audit's rank-1 finding, needs no exclusive slot, and its drift mechanism has
already fired once unobserved. #27 is band B — it discharges an obligation lifted out of #15 and may not be dropped.

### Shared conflict surfaces

Standing surface for every ticket: `CHANGELOG.md`, `docs/technical/roadmap.md`, and
`docs/technical/v88_ticket_context.md` when the ticket's concept notes change.

| Ticket | Additional shared surface | Why |
|---|---|---|
| SA173 | `quickscale_core/.../contracts/module_discovery.py`, `quickscale_core/.../manifest/entry_point.py`, `quickscale_cli/.../commands/{status,apply}_command.py`, `quickscale_cli/.../utils/module_wiring_manager.py`, `docs/technical/decisions.md` | the module-presence contract and its CLI consumer policies; **cross-lane by behaviour** — every lane reads these two core packages |
| SA167c | every `quickscale_modules/*/module.yml`, `quickscale_core/.../manifest/{schema,loader}.py`, `scripts/gate_registry.json`, `Makefile`, CI workflow, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` | retires the inert key and registers the declaration gate; **registry membership is why this is W2** |
| SA167d | `quickscale_cli/src/quickscale_cli/commands/module_config.py`, `docs/technical/module-extension.md` | CLI wiring drain; touched by no other v88 ticket |
| SA135 | `scripts/test_integration.sh`, `scripts/provision_test_roles.sh`, `scripts/provision_ci_postgres.sh`, `Makefile`, `docs/technical/validation_policy.md` | changes the documented local DB precondition |
| SA160, SA161 | generator templates + **SA90 emission-parity fixture**, `docs/others/tech-audit.md` | emitted output changes |
| SA164 | `docs/others/arch-audit.md`, `scripts/gate_registry.json`, `scripts/check_gate_parity.py`, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`, `.../production.py.j2`, `quickscale_modules/orgs/.../apps.py`, `quickscale_cli/.../development_commands.py`, `.../start.sh.j2` | watchlist discharge plus the rank-1 privileged-command finding; **W2** — registry and the SA92 test are W2-owned, and it merges last |
| SA165 | `docs/others/tech-audit.md`, `quickscale_core/.../state_schema.py`, `scripts/test_isolation_conformance.sh`, `quickscale_core/tests/test_generator/test_generator.py`, `OPERATIONS.md.j2` | watchlist discharge; W1-isolated |
| SA166 | `scripts/gate_registry.json`, `Makefile`, CI workflow, `docs/others/tech-audit.md` | new process gate |
| SA170 | `quickscale_cli/src/quickscale_cli/utils/docker_utils.py`, `quickscale_cli/tests/test_e2e_development_workflow.py`, `quickscale_cli/tests/test_react_theme_e2e.py`, `scripts/test_e2e.sh`, `docs/others/tech-audit.md` | E2E Docker resource contract and failure diagnostics; **W3** — needs the exclusive Docker slot |
| SA171 | `quickscale_core/.../dr_engine/_lock.py`, `quickscale_core/.../advisory_lock.py`, `docs/others/tech-audit.md` | two hand-rolled file locks share one TOCTOU; **W3** — the backups suite needs the cluster |
| SA172 | `quickscale_modules/orgs/.../tenancy.py`, `scripts/test_isolation_conformance.sh`, `docs/others/tech-audit.md` | RLS policy templates and their conformance assertion; **W3** — proved against a live PostgreSQL |
| SA174 | `quickscale_core/.../generator/runtime_pins.py`, `.../generator/generator.py`, `.../templates/project_name/settings/production.py.j2`, `.../templates/start.sh.j2`, `quickscale_core/tests/test_generator/test_templates.py`, `quickscale_modules/orgs/.../apps.py`, `quickscale_cli/.../development_commands.py`, **SA90 emission-parity fixture**, `docs/others/arch-audit.md` | one privileged-command declaration replacing four; **W1** — generated output plus module wiring, and it touches `generator/` only, never `contracts/` or `manifest/` |
| SA175 | `quickscale_cli/tests/test_beta_migration_ownership_conformance.py`, `quickscale_devtools/.../beta_migration.py`, `docs/others/arch-audit.md` | disposition-coherence assertion for the launcher↔settings contract; **W1** — no other open ticket touches either file |

Surfaces needing an explicit ordering note beyond the table:

- `scripts/gate_registry.json` — SA167c, SA166, SA164, all W2. **This surface never crosses
  worktrees**; that invariant is why SA167c could not move to W1 with the other wiring legs, and it
  applies equally to `quickscale_modules/*/module.yml`.
- `quickscale_core/contracts/` and `quickscale_core/manifest/` — **SA173 (#30, W2) is the sole open
  owner**, and it is the one surface on this list that is shared by *behaviour* rather than by
  filename: every lane imports it. `entry_point.py`'s manifest-read behaviour and module-owned
  adapter registry stay settled tree state — SA173 changes how presence is reported and where the
  subset rule lives, and must preserve the generic-only boundary rather than reinstating any
  literal. `203fcd61` is the recorded precedent for what happens when this surface moves without a
  cross-lane announcement.
- `scripts/test_gate_parity.py` — **no open ticket owns it.** The closed SA163 replaced its
  transcribed provisioning shell literal with a `describe --format json` binding plus an
  absence-of-the-old-shape assertion. That binding, the regenerated 24-entry publish oracle, and
  SA123's settled hosted-job, `needs`-edge, run-value, publish/E2E-path, and generator expectations
  are settled tree state and must be preserved by anything that touches the file.
- `.github/workflows/` and `scripts/provision_ci_postgres.sh` — **no open ticket owns them** after
  SA163 closed. SA166 (#24, W2) registers a new gate in the CI workflow and must not reopen the
  provisioning stations.
- `.../settings/production.py.j2` — SA161 (#19, W1) and SA164 (#25, W2) edit **different regions on
  two lanes** with no ordering edge. Merge order #19 before #25 makes it one-directional; neither
  ticket may widen into the other's region.
- `scripts/test_isolation_conformance.sh` — three owners, all sequenced. SA163's merged edit is
  settled bytes; SA165 (#22, W1) applies its one-line skip-allowlist narrowing over them; SA172
  (#29, W3) adds a policy-text assertion in a different region and merges last.
- `sa90_emission_manifests.json` — SA161 then SA160. Each rebaseline appends its own
  `baseline_evidence` entry with per-file rationale; every prior entry must be preserved.
- `scripts/test_e2e.sh` — SA170 (#27, W3) is the only open owner, and touches the scope/cleanup side
  that SA135's merged provisioning work did not.

`docs/others/arch-audit.md` is now on three surfaces: **SA174** (retires the rank-1
`privileged-command-set-multi-owner` finding), **SA175** (records rank-2's first step as discharged
without closing the finding), and **SA164** (adjudicates the watchlist). None of the three merges
adjacent to another, so the file resolves through the standard sync-resolve-rerun-review step. The
prior rank-1 `ci-environment-hand-replicated` is resolved and archived. The rank-3 and rank-4
findings (`deletion-invariants-per-boundary-reimplementation`, `org-model-universe-hand-enumerated`)
remain untouched per the standing "neither" rule, as does the **substance** of rank-2
(`generated-file-ownership-unmodeled`) — SA175 takes only the bounded first step the audit itself
marks as trigger-independent.

**Closeout conflict surface.** Every ticket writes `CHANGELOG.md`, this file, and
`docs/technical/v88_ticket_context.md` at closeout; `docs/others/tech-audit.md` is shared by
SA160, SA161, SA165, SA166, SA170, SA171, and SA172, and `docs/others/arch-audit.md` by SA164,
SA174, and SA175. That is by design and is covered by the merge
procedure in the execution rules: sync the integration branch into the worktree, resolve there,
re-run the ticket's verification (including
`quickscale_core/tests/test_v88_ticket_context_consistency.py` whenever a state block changes),
review the exact tip, then merge it. No lane move above adds a *code* file to a second lane.

---

## v88 backlog track

Each ticket carries its band, assigned worktree, merge position, and acceptance criteria. This
section and the [audit-derived backlog](#audit-derived-backlog) below are **one list** — the
merge-order table is the authority for scope, worktrees, and sequencing. Conceptual background and
implementation notes for every ticket live in [v88_ticket_context.md](v88_ticket_context.md).

- [ ] **SA173 — Make module presence a three-state fact.** `Band A · Tier 1 · W2 · merge #30 · deps: none · settles decision D3 · unblocks SA167c Phase-A and both other lanes' merges`
  Discovery collapsed *"module absent"* and *"directory present but no `module.yml`"* into one
  output, and downstream consumers reconstructed the discarded fact by **counting**. The policy
  chosen by decision D3 is written in
  [decisions.md → Module Presence States](decisions.md#module-presence-states); this ticket
  implements it. The investigation that produced D3 is archived in
  [CHANGELOG.md](../../CHANGELOG.md) and is not restated here.
  **State (checkpointed 2026-08-28): a reviewed product candidate is committed on `wt-track2` at
  `4c311a73ef445dfd48e4b3cda4563ca345259661`, but it is not merged and SA173 remains open.** This
  checkpoint supersedes the older open-state wording below; retain that wording only as the measured
  starting diagnosis and do not redo work recorded as completed here.
  **Completed on the unmerged candidate:** `status` reports registered ABSENT/INCOMPLETE modules as
  drift while `apply` remains fail-hard; all eight runtime-proven auth/CRM fixtures use real
  manifests without assertion changes; the lone-file discovery shim supports hermetic inventories;
  repository direct-file consumers resolve the sibling catalog and exclude declared placeholder
  `teams`; ACTIVE placeholders fail before adapter import with registry/import-state atomicity; the
  criterion-8 missing-manifest proof restored exact bytes; and the `refresh_managed_adapters`
  complexity warning was removed. Focused, broad non-E2E, scripts, parity, lint, type, provisioning,
  and static checks passed. Independent terminal review found no additional defect in these product
  bytes.
  **Pending:** phase B4 is not accepted because the required `make test` chain is red; phases B5
  (authoritative documentation closeout) and B6 (synced frozen-candidate and cross-lane validation)
  were not reached. `make check` and `make quality` were not run after the stop.
  **Blocking:** `quickscale_modules/storage/src/quickscale_modules_storage/__init__.py` measures 45%
  against the required 80% per-file coverage threshold even though the storage tests pass. Close it
  with legitimate tests or production simplification, then rerun `make test` green. Separately,
  `wt-track2` is 1 ahead / 1 behind `v88` at
  `3a16b3106ae06872c18b254e95a8e5d5fdafde9d`; sync in the worktree and repeat the complete
  frozen-candidate validation before merge.
  **Decisions needed:** none.
  **Remaining plan (serial):**
  1. Start from `wt-track2` product commit `4c311a73ef445dfd48e4b3cda4563ca345259661` and do not redo
     the completed SA173 consumer, fixture, shim, or placeholder work.
  2. Fix the storage per-file coverage blocker to at least 80% without weakening the gate, then run
     `make test` to a returned green verdict.
  3. Merge current `v88` into `wt-track2`, resolve there, and rerun criterion 8 plus the complete
     ordered SA173 campaign, including detached `make test`, `make check`, and `make quality`, the W1
     and W3 caller suites, and the ticket-context consistency test.
  4. Only after every gate is green, reconcile `CHANGELOG.md`,
     `docs/technical/implementation_contract.md`, `docs/technical/v88_ticket_context.md`,
     `docs/index.md`, and this open-work roadmap; then run convergence and one terminal attestation
     over the exact synced tip and merge that tip into `v88`.
  **Settled and merged — do not reimplement.** Product commit `e0730ae9` is on `v88`. Verified
  on HEAD: discovery reports ABSENT / ACTIVE / INCOMPLETE; `grep -rn "inventory count drift"
  --include=*.py` outside tests returns **one** production site
  (`module_discovery.py:309`); the CLI's `"Manifest file not found"` substring classification is
  **gone**; `PLACEHOLDER_MODULE_NAMES` is **retired** in favour of a catalog `placeholder` flag; the
  `OVERRIDE`→bundled substitution is **removed**; and the loader/adapter refresh enforce typed
  presence atomically. Acceptance criteria **1, 3, 4, 6, 7 are met**, and criterion 2's
  subset-plus-fail-hard pair is met at the core boundary. `wt-track2` is identical to `v88`, so W2
  resumes with no sync.
  **Open — the whole of what remains, and why it is exactly this.**
  1. **Criterion 5 is half-written, and it is what makes `make check` red — 11 failures in
     `quickscale_cli/tests/test_status_command.py`.** Deleting the CLI's classification was correct;
     **no CLI reaction was written to replace it**, so `status_command.py:229`'s
     `_abort_for_manifest_error` (reached from `:845`) now aborts on a module that
     `.quickscale/state.yml` registers and the project tree does not carry.
     **These eleven tests are the correct oracle and must not be edited to match the abort.** Three
     of them are `test_status_detects_missing_modules`, `test_module_tracking_completeness`, and
     `test_json_drift_filesystem_drift_populated`: `status` is the diagnostic command, and aborting
     is the one reaction it must not have when it finds drift. D3 says consumers own their reaction —
     **`status` *reports as drift* and exits 0; `apply` *fails hard*.** Write the missing one; keep
     the written one.
  1b. **Seven stale fixtures in `quickscale_cli/tests/commands/test_module_config_extended.py`.**
     A different failure, at `module_config.py:546` with `Module presence is incomplete`. The
     fixtures at `:961,983` and the CRM equivalents build `modules/<name>/` holding only a
     `pyproject.toml`; that is INCOMPLETE, and `apply` refusing to wire it is exactly the behaviour
     this ticket was opened to produce. **Do not weaken `apply`.** Route the seven through the
     helper the same file already provides — `_write_module_package` (`:139-150`), which writes
     `module.yml` alongside `pyproject.toml` — the treatment `e0730ae9` already applied to the
     lifecycle fixtures and did not extend here. Assertions do not change. **Confirm rather than
     assume** that the real embed path writes `module.yml` before wiring regeneration; if it does
     not, that is a second product defect and gets its own entry instead of a fixture edit.
  1c. **The standalone discovery shim is broken, and it takes `scripts/` red with it — 5 failures in
     `scripts/test_version_tool.py::TestUpdateWithTempRepo`.** `module_discovery.py` is contracted to
     run **alone**, copied into a tree with no importable `quickscale_core` package:
     `scripts/version_tool.sh:14,34` copies it as `MODULE_DISCOVERY_SHIM` and calls `--list-modules`
     to enumerate the release modules it must bump. `e0730ae9` put `_declared_module_names()`
     (`:217-229`) on that path, and **its `ModuleNotFoundError` guard is too narrow**: it compares
     `exc.name != "quickscale_core.contracts.module_catalog"`, but in a shim tree the interpreter
     fails at the *root* package and raises `exc.name == "quickscale_core"`, so the guard re-raises
     and `--list-modules` exits 1. Measured: `ModuleNotFoundError: No module named 'quickscale_core'`
     at `:220`. The same too-narrow comparison is in `_declared_placeholder_names` (`:231-239`).
     **There is a second defect behind the first.** Widening the guard to accept a prefix of the
     target path (verified in a scratch tree) gets past the import and then fails with
     `ERROR: Module inventory count drift: expected 12 unique release modules, found 1` — with an
     empty catalog the shim now enforces the twelve-module release count against a hermetic tree
     that legitimately carries fewer. Both must be fixed for the shim contract to hold; repairing
     only the guard converts an import crash into a count crash.
     **Consequence for this ticket's own verification:** `poetry run pytest scripts/` returns
     **5 failed, 1313 passed** and cannot reach exit 0 until this is repaired. The ticket already
     names `publish_module.py` and `check_sa117_scope.py` as release-inventory consumers of the
     changed contract; `version_tool.sh` is a third that was missed.
  2. **An ACTIVE catalog-declared placeholder is handled two ways.**
     `refresh_managed_adapters` (`manifest/entry_point.py:218-236`) filters placeholders out of both
     the INCOMPLETE check and the active set with `and not is_placeholder_module(...)`, so an ACTIVE
     placeholder is **silently excluded**; `validate_module_presence`
     (`contracts/module_discovery.py:250-266`) **rejects that same state**. Make the ACTIVE-placeholder
     case fail atomically with an actionable pre-import error, while preserving the intentional
     declared-INCOMPLETE placeholder behaviour that keeps `teams` fail-closed. Settled D3 does not
     authorize accepting this deviation.
  3. **Criterion 8's negative proof and the closeout campaign were never reached.** No waiver, no
     deselection, no `PYTEST_ADDOPTS`.
  **Closed by diagnosis, not carried forward.** The recorded *"broad CLI validation returned no
  verdict at 120 s and again at 360 s"* blocker was a foreground cutoff, not a stall: run detached,
  the suite completes in seconds. Its verdict is the eighteen failures above. The recorded
  order-dependent `test_partial_generated_override_uses_bundled_shipped_inventory` trap is gone —
  `e0730ae9` deleted the OVERRIDE path and the test with it. The interim known-red protocol is
  **retired**; its two node ids pass, and it may not be widened to cover this ticket's own oracle.
  **Decisions needed:** none. D3 and placeholder-declaration policy are settled; item 1 has the one
  resolution D3 already prescribes, item 1b is a fixture repair with an existing helper, and item 1c
  is a contract restoration. The remaining inputs are execution, independent review, and acceptance
  evidence.
  **Measured starting state (2026-08-28 at `4e410c09`), reproduce before changing anything:**
  - `poetry run pytest quickscale_cli/tests/test_status_command.py quickscale_cli/tests/commands/test_module_config_extended.py -q -o addopts= --no-cov -p no:cacheprovider`
    — **18 failed, 149 passed**; 11 from the first file, 7 from the second, two different causes.
  - Cause A text, verbatim: `❌ Installed module manifest error during 'status':` /
    `• [auth] Manifest file not found for module 'auth': <project>/modules/auth/module.yml` /
    `Aborted!` — raised at `status_command.py:229`, reached from `status_command.py:845`.
  - Cause B text, verbatim: `❌ Managed wiring regeneration failed: Managed adapter wiring failed:
    Module presence is incomplete: module 'auth' is missing manifest
    '<tmp>/myproject/modules/auth/module.yml'` — raised at `module_config.py:546`.
  - `poetry run pytest quickscale_cli/tests/test_module_wiring_manager_manifest.py -q -o addopts= --no-cov`
    — **43 passed.** The two original target tests are green; do not reopen them.
  - `make check` (detached) — **exit 2**, lint and typecheck green, `quickscale_core` 2886 passed /
    1 skipped, `quickscale_cli` 18 failed / 2135 passed.
  - `poetry run pytest scripts/ -q -o addopts= --no-cov -p no:cacheprovider` — **5 failed, 1313
    passed**, all five in `test_version_tool.py::TestUpdateWithTempRepo`.
  - Shim probe: copy `module_discovery.py` alone into an empty tree beside one
    `quickscale_modules/<name>/module.yml` and run `python3 <path> --list-modules` — observe
    `ModuleNotFoundError: No module named 'quickscale_core'`. On the real repo the same command
    prints the twelve names and exits 0, which is why this is invisible from the repo root.
  **Remaining plan (serial; start on `v88` and do not redo merged product work):**
  1. Write `status`'s report-as-drift reaction so its eleven tests pass **unedited**, and assert in a
     test that the CLI still contributes no presence *classification* — the decision stays in core;
     only the reaction is the CLI's. Separately, repair the seven `test_module_config_extended.py`
     fixtures through `_write_module_package`, changing no assertion and leaving `apply`'s fail-hard
     intact. Then repair the standalone-shim contract (item 1c) — **both** defects — and add a
     hermetic test that runs `module_discovery.py --list-modules` in a shim tree, so the contract is
     gated rather than rediscovered by a release tool.
  2. Resolve the ACTIVE-placeholder consistency edge above, and have it independently reviewed
     together with the post-attestation all-INCOMPLETE wiring correction retained in `e0730ae9`,
     which stands ungraded.
  3. Run criterion 8's negative proof: temporarily empty one module's `module.yml`, observe the
     INCOMPLETE fail-hard for the intended reason, restore the exact bytes, prove green.
  4. Run the ordered verification below on one frozen candidate. Long gates detached, exit code to a
     file, polled — a truncated run is not evidence. Schedule `make test` outside W3's window.
  5. Only after every required result is green, reconcile `CHANGELOG.md`,
     `docs/technical/implementation_contract.md`, `docs/technical/v88_ticket_context.md`,
     `docs/index.md`, and this file's queue/counts/dependencies, re-run the consistency test in the
     same change, and archive/remove SA173 from this open-work-only roadmap.
  6. Materialize the complete base-to-tip patch to a file, supply it with a clean-byte binding
     (`git status --porcelain` empty at the exact tip), perform serial convergence and **one**
     terminal attestation, and merge only that exact accepted tip. Announce the merge in the queue
     and re-run W1's and W3's focused caller suites first — see the cross-lane obligation below.
  **Acceptance:**
  1. Discovery reports ABSENT / ACTIVE / INCOMPLETE distinctly and no code path silently drops a
     manifest-less directory. *(met on HEAD)*
  2. `refresh_managed_adapters` loads the **subset** present and fails hard on INCOMPLETE, naming the
     directory and the missing manifest, both proved by separate tests — **and an ACTIVE
     catalog-declared placeholder fails atomically with an actionable pre-import error rather than
     being silently excluded**, while a declared-INCOMPLETE placeholder stays fail-closed. *(first
     half met on HEAD; the placeholder half is open item 2)*
  3. The subset-validity rule and its diagnostic text exist **once**;
     `grep -rn "inventory count drift" --include=*.py` outside tests returns a single production
     site. *(met on HEAD)*
  4. `authoritative_module_names` answers the *release inventory* question only; the
     `OVERRIDE`→bundled substitution is removed. *(met on HEAD)*
  5. The CLI contributes no presence **classification** — the substring test at
     `module_wiring_manager.py:201` stays deleted — **and each CLI consumer states its own reaction
     to a typed presence result: `status` reports a registered-but-missing or INCOMPLETE module as
     drift and exits 0; `apply` fails hard.** The eleven tests in `test_status_command.py` pass
     **without being edited**, and the seven in `commands/test_module_config_extended.py` pass with
     **fixture-only** repair and no assertion or `apply` change. *(first clause met on HEAD; the
     rest is open items 1 and 1b)*
  9. **The standalone-shim contract holds:** `module_discovery.py`, copied alone into a tree with no
     importable `quickscale_core`, still answers `--list-modules` for whatever modules that tree
     carries — no root-package import crash, and no twelve-module release count imposed on a
     hermetic tree — and a hermetic test asserts it, so `scripts/version_tool.sh` cannot break again
     unobserved. *(open item 1c)*
  6. `PLACEHOLDER_MODULE_NAMES` is retired in favour of a declaration mechanism, with `teams` still
     fail-closed. *(met on HEAD)*
  7. `test_module_wiring_manager_manifest.py`'s two tests, their class name, and both docstrings
     agree with the contract. *(met on HEAD — 43 passed)*
  8. Negative proof: temporarily empty one module's `module.yml`, observe the INCOMPLETE fail-hard
     for the intended reason, restore the exact bytes, prove green. *(open)*
  **Verification (ordered; stop at the first unexpected red):**
  1. `poetry run pytest quickscale_cli/tests/test_status_command.py quickscale_cli/tests/commands/test_module_config_extended.py -q -o addopts= --no-cov -p no:cacheprovider` — expect exit 0 with **167 passed** and no test file edited.
  2. `poetry run pytest quickscale_cli/tests/test_module_wiring_manager_manifest.py quickscale_core/tests/test_manifest_entry_point.py quickscale_cli/tests/test_module_lifecycle_cycle.py quickscale_core/tests/test_module_migration_topology.py -q -o addopts= --no-cov` — expect exit 0; **221 passed** at the measurement start.
  3. `poetry run pytest quickscale_cli/tests quickscale_core/tests -m "not e2e" -q -o addopts= --no-cov` — expect exit 0. This isolates the ticket's surface without SA170's four `e2e` failures; the unfiltered variant costs ~80 minutes and proves nothing extra here.
  4. `poetry run pytest scripts/ -q -o addopts= --no-cov -p no:cacheprovider` — expect exit 0 and **1318 passed**; measured **5 failed, 1313 passed** at the start (open item 1c). `publish_module.py`, `check_sa117_scope.py`, and `version_tool.sh` are release-inventory consumers of the changed contract.
  5. `make check-manifest-sync` and `make check-gate-parity` — expect exit 0.
  6. `make lint`, `make typecheck` — expect exit 0. Then `make test`, `make check`, `make quality` **detached**: `make check` expects exit 0 in ~601 s, and `make quality` no worse than found.
  **Rollback:** `git reset --hard 4e410c09` discards the resumption without touching the merged
  contract; the merged `e0730ae9` is not rolled back by this ticket.
  **Cross-lane obligation.** These two core packages are read by every lane, and `203fcd61` is the
  recorded precedent for a behavioural change here turning another lane red with no shared file.
  Before merging, announce in the merge queue and re-run W1's and W3's focused caller suites against
  the candidate.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/contracts/module_discovery.py`, `quickscale_core/src/quickscale_core/manifest/entry_point.py`, `quickscale_cli/src/quickscale_cli/commands/status_command.py`, `quickscale_cli/src/quickscale_cli/commands/apply_command.py`, `quickscale_cli/src/quickscale_cli/utils/module_wiring_manager.py`, `docs/technical/decisions.md`.

- [ ] **SA167c — Retire `django_apps:` and gate the app declaration.** `Band B · Tier 2 · W2 · merge #21 · deps: SA173 · closes the SA167 family`
  `django_apps:` was inert declarative surface: eleven manifests carried it, the loader parsed it,
  no production path read it, and one SA92 helper used it before falling back to a guessed path.
  **Acceptance:** `django_apps:` is either derived from the `apps` wiring projection or removed from all manifests, `ModuleManifest`, and the loader, with no key parsed-but-unread remaining; a conformance gate fails when a module ships models or a migration without declaring at least one Django app, registered in `scripts/gate_registry.json` and passing `scripts/check_gate_parity.py`; the gate is proved by deleting a module's app declaration and observing red, reverted before merge; `test_sa92_migration_squash_guardrail.py` no longer depends on the retired key.
  **State (measured 2026-08-28): Phase-A product slice merged; corrected acceptance partial.**
  Product commit `f6f3bbce` remains merged. `wt-track2` synchronized cleanly to `v88` at
  `8a8f364b` before this attempt. Phase A is **not accepted**; phases B-F were not reached. The
  merged bytes removed `django_apps:` from `ModuleManifest`, the loader, the obsolete loader test,
  all eleven source declarations and their core snapshots, and removed the SA92 helper's retired-key
  dependency, while preserving all twelve `apps` wiring projections and public adapter outputs.
  Terminal review found no product-slice defect.
  **Latest acceptance evidence.** The coverage-isolated loader command exited 0 with 112 passed;
  the restricted-role orgs command exited 0 with 884 passed, 11 skipped, and 2 warnings;
  `make check-manifest-sync` exited 0; and `make check-gate-parity` exited 0. The required
  four-caller command then exited 1 with 256 passed and 2 failed in
  `TestRegenerateManagedWiringSkipManifestNotFound`, at
  `quickscale_cli/tests/test_module_wiring_manager_manifest.py:767,796`. Under the required
  stop-at-first-unexpected-red rule, neither the literal twelve-module source-bound caller probe nor
  the final `git diff --exit-code` unchanged-tree oracle was run. No tracked file changed, and this
  green prefix is not Phase-A acceptance.
  **Not this ticket's defect.** Decision D3 (2026-08-28) established that those two failures are a
  module-presence contract question, not a `django_apps:` question: the deciding code is
  `refresh_managed_adapters`, the tests contradict their own docstrings, and the runtime was flipped
  by W3's `203fcd61`. **SA173 (#30) owns the fix and the two tests.** SA167c must not edit them, and
  must not touch `quickscale_core/contracts/` or `quickscale_core/manifest/`.
  **Blocking:** SA173 must be **accepted and merged**. Its contract commit `e0730ae9` is already on
  `v88` and the two caller tests it owed are green (43 passed in
  `test_module_wiring_manager_manifest.py`), but SA173 is still open on its CLI consumer policy and
  `make check` is red — so #30 has not merged and #21 is still gated. Nothing else blocks Phase A;
  the other three commands in the chain were green on this exact candidate. **Note for step 5
  below:** `commands/test_module_config_extended.py` is not in SA167c's chain, so SA173's eighteen
  open failures do not touch this ticket's commands.
  **Decisions needed:** none. D3 is settled; see
  [Settled decision D3](#settled-decision-d3-module-presence-is-a-three-state-fact-2026-08-28).
  **Remaining plan (serial; do not redo the merged retirement bytes):**
  0. **Wait for SA173 to merge.** No SA167c work is required for the caller mismatch, and the
     contract half is already on `v88`. When #30 merges, sync it into `wt-track2` before rerunning A.
     `wt-track2` is currently identical to `v88`.
  1. **A-acceptance:** on a candidate carrying SA173's contract and no tracked
     diff, rerun the exact chain below in order. Stop at the first command whose observed result does
     not match its expected result; do not run any later command after that red, and do not treat a
     green prefix as acceptance.

     1. `poetry run pytest quickscale_core/tests/test_manifest_loader.py -q -o addopts= --no-cov`
        — expect exit 0.
     2. `QS_ORGS_DB_USER=quickscale_test_role make MODULE=orgs test -- --modules`
        — expect exit 0 under the restricted PostgreSQL role.
     3. `make check-manifest-sync`
        — expect exit 0 with all twelve source and bundled manifests in sync.
     4. `make check-gate-parity`
        — expect exit 0 through Make's blocking parity wrapper.
     5. `poetry run pytest quickscale_cli/tests/commands/test_module_config_extended.py quickscale_cli/tests/test_module_wiring_manager_manifest.py quickscale_cli/tests/test_orgs_contract.py quickscale_cli/tests/test_manifest_entry_point_integration.py -q -o addopts= --no-cov`
        — expect exit 0 once SA173's presence contract is present. This is the command that was red;
        the other four were green on this candidate.
     6. Run this literal read-only source-bound probe; expect exit 0 and exactly
        `verified 12 source-bound module app projections`:

        ```bash
        poetry run python - <<'PY'
        from quickscale_core.contracts.module_discovery import (
            authoritative_module_names,
            get_modules_base_path,
        )
        from quickscale_core.manifest.entry_point import (
            build_manifest_wiring_spec,
            refresh_managed_adapters,
        )
        from quickscale_core.manifest.loader import load_manifest_from_path

        base = get_modules_base_path()
        source_apps = {}
        defaults = {}
        for name in authoritative_module_names():
            manifest = load_manifest_from_path(base / name / "module.yml")
            projections = [
                item
                for item in manifest.wiring_projections
                if isinstance(item, dict) and item.get("wiring_field") == "apps"
            ]
            assert len(projections) == 1, (name, projections)
            projection = projections[0]
            assert projection.get("derivation_type") == "static", name
            expression = projection.get("expression")
            assert isinstance(expression, dict), name
            values = expression.get("value")
            assert isinstance(values, list) and values, name
            assert all(isinstance(value, str) and value.strip() for value in values), name
            source_apps[name] = tuple(values)
            defaults[name] = manifest.get_defaults()

        refresh_managed_adapters()
        caller_apps = {
            name: build_manifest_wiring_spec(
                name,
                defaults[name],
                project_package="sa167_acceptance",
            ).apps
            for name in source_apps
        }
        assert caller_apps == source_apps, (source_apps, caller_apps)
        print(f"verified {len(source_apps)} source-bound module app projections")
        PY
        ```

     7. `git diff --exit-code`
        — expect exit 0 as the final unchanged-tracked-tree oracle. Only all seven expected results,
        on this one ordered run and one unchanged candidate, accept Phase A.
  2. **B-gate:** add a fail-hard `check_module_app_declaration` checker with hermetic tests covering
     model/migration evidence, empty or malformed projections, malformed manifests, inventory and
     filesystem failures, evidence-free modules, deterministic diagnostics, and current tree state.
  3. **C-integration:** register `check-module-app-declaration` in Make and the gate registry for
     local serial, local parallel, and hosted CI; update the hosted generator/catalog, generated
     `ci.yml`, parity/current-state tests, local-runner labels, and script map. Publish and E2E
     remain unchanged.
  4. **D-negative proof:** remove `social`'s sole apps projection temporarily, require the gate to
     fail for the intended reason, restore the exact bytes, prove gate and manifest sync green.
  5. **E-closeout:** reconcile decisions, implementation contract, validation policy, ticket
     context, roadmap queue/counts, and changelog evidence. Retain the SA164 and SA166 boundaries.
  6. **F-frozen candidate:** sync current `v88`, run the complete focused-to-broad campaign on one
     unchanged candidate, perform independent convergence and terminal attestation, merge that tip.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/manifest/{schema,loader}.py`, every `quickscale_modules/*/module.yml`, `scripts/gate_registry.json`, `Makefile`, CI workflow, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`.

- [ ] **SA167d — Complete the CLI wiring-drain acceptance.** `Band B · Tier 2 · W1 · merge #18 · deps: none · blocks SA165`
  `quickscale_cli/src/quickscale_cli/commands/module_config.py` carried a boundary violation:
  functions **collecting desired configuration** are legitimate and stay; anything deciding what a
  module *wires* belongs in the module. The product bytes implementing that boundary are written.
  **Acceptance:** no function in `module_config.py` decides a module's apps, middleware, settings
  keys, or URL includes — those come from the module's manifest through its adapter; the remaining
  surface is desired-configuration collection only, and that boundary is stated in the module's
  docstring; a test asserts the CLI contributes nothing to `ModuleWiringSpec`; the stale-flow note
  in [module-extension.md §Building a Module](module-extension.md#building-a-module-authoring-checklist)
  is retired once the deviation it names is gone.
  **State (re-measured 2026-08-28 from `wt-track1` itself): phases A-E accepted; closeout is all
  that remains.** The prior entry here described a lane six commits behind reality and instructed a
  rerun of work already accepted. Corrected against the branch:
  - `wt-track1` is **clean** at `f392641c`, 15 ahead / 3 behind `v88`, and is the release's only
    unmerged product delta.
  - Phase E **is accepted** at E0 tip `bd2c291b`, retained inside `8b20800d` — the clean committed
    product tip. E0 made no tracked edits and recorded **282 focused tests passed**, with `make lint`,
    `make typecheck`, `make test`, `make check`, and `make quality` all at exit 0 and `make check`
    reporting **1,318 passed**.
  - Independent convergence then ran and **corrected real defects**: ineffective auth-migration flush
    guidance, a non-operational fresh-database recovery path, and three stale quality-baseline
    identities. Those corrections are `8b20800d`.
  - The measured product delta `c50de1c1..8b20800d` is **30 files, 1,012 insertions, 2,228
    deletions**.
  **Why the last attempt did not close, precisely.** Terminal attestation was attempted once and
  **returned no grade**. Its read-only surface could resolve the exact tip but could not obtain the
  complete `c50de1c1..8b20800d` patch or independently exclude uncommitted-byte drift. That is a
  **review-input failure, not an attestation finding** — nothing was found wrong with the delta.
  Separately, V0 stopped when `make check` hit a 120-second cutoff before returning an exit code.
  Both causes are now removed: the patch is producible in one command, and `make check`'s real
  behaviour is measured above under *Band A*.
  **Closeout shape (decided 2026-08-28): validate, then attest.** The recorded five-stage
  V0/C2/V1/convergence/attestation pipeline is **not** required. Convergence has already run and
  corrected this delta, every gate has been green on it once, and the single unmet step failed for a
  reason that no longer applies. Re-running the full staging would re-prove passed work.
  **Remaining plan (serial; do not re-implement anything):**
  1. **Sync.** Merge current `v88` into `wt-track1` and resolve there, preserving the retained
     candidate and the closeout checkpoint. Expect a conflict in this file — keep its structure.
  2. **Validate on one frozen candidate,** unexcluded — the known-red protocol is retired and no
     `PYTEST_ADDOPTS` is authorized. Ordered, stopping at the first unexpected red:
     - `poetry run pytest quickscale_cli/tests/commands/test_module_config.py quickscale_cli/tests/commands/test_module_config_extended.py quickscale_cli/tests/commands/test_module_commands.py quickscale_cli/tests/test_module_wiring_manager_manifest.py quickscale_cli/tests/test_module_manifest_contract.py -q -o addopts= --no-cov` — expect the recorded **816** focused total. **Seven of these are SA173's open regression in `commands/test_module_config_extended.py`** (see *Band A*); they are not W1's to fix or to deselect, and they clear when #30 merges. Until then this command's expected result is 816 less those seven.
     - `poetry run pytest quickscale_core/tests/test_v88_ticket_context_consistency.py -q -o addopts= --no-cov` — expect **21 passed**.
     - `make lint`, `make typecheck` — exit 0.
     - `make test`, `make check`, `make quality` — **run detached and poll for an exit-code file;
       `make check` alone measures ~601 s green and cannot complete inside one foreground call.** A
       truncated run is not evidence. `make quality` no worse than found.
  3. **Ledger reconciliation** across `CHANGELOG.md`, `docs/index.md`, `docs/others/arch-audit.md`,
     `docs/technical/{decisions,implementation_contract,module-extension,v88_ticket_context}.md`,
     and the executable consistency test. Do not archive SA167d early: keep it open, #18 active, and
     SA165 dependent until the exact tip merges.
  4. **Attest once, with the input supplied.** Generate the complete patch first —
     `git diff <frozen-base>..<frozen-tip> > sa167d.patch` — and hand the attesting reviewer that
     file plus a clean-byte binding (`git status --porcelain` empty at the exact tip). The
     2026-08-28 measurement of `c50de1c1..8b20800d` is **4,274 lines / 183 KB**, comfortably
     readable; there is no reason for a second ungraded attempt.
  5. **Merge only the attested exact tip** — and only after SA173 has landed and step 2 has been
     re-run on a candidate synced to the post-SA173 `v88`, with all 816 green. That re-run is the
     merge evidence; the pre-SA173 run is provisional and is not.
  **Rollback:** `git reset --hard f392641c` in `wt-track1` discards any closeout attempt without
  touching `v88`.
  **Shared conflict surface:** `quickscale_cli/src/quickscale_cli/commands/module_config.py`, `docs/technical/module-extension.md`, plus the ledger-reconciliation files listed above.

- [ ] **SA135 — Give test suites an owned PostgreSQL lifecycle.** `Band B · Tier 2 · W3 · merge #15 · deps: none · PostgreSQL + Docker slot`
  Provision and tear down the server used by repository gates; replace the current out-of-band host assumption while retaining an asserted unavailability negative control.
  **Acceptance:** the integration gate provisions its own PostgreSQL 18 server and tears it down, with no reliance on a pre-existing host server; the `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` role contract is preserved; the asserted-unavailability negative control still fails loudly when the server cannot be provisioned, rather than skipping; `make test-integration` passes on a machine with no PostgreSQL running; [validation_policy.md](validation_policy.md) is updated to drop the out-of-band host precondition; image identity follows the settled content-addressed backend-image convention.
  **State (measured 2026-08-27): partial delivery merged into `v88`.** The merge object is
  `f070f39b`, the second of two merges (`0661f55f`, then `f070f39b` carrying the `203fcd61`
  lifecycle/module-E2E remediation). Phases P/A/B and C/D are accepted — the hermetic
  Docker-unavailable probe, the strict no-host-server window, and the single four-caller
  provisioning authority; **do not repeat C or D.** E was
  dispatched but is not accepted, and F/G were not reached. E0 accepted the unchanged external-state
  baseline (both former SA142 orphan names and `quickscale-react-test` absent; `pg18-af10` retained
  its exact container, image, mount, and running identity; all twelve databases owned by
  `quickscale_test_role`). E1 recorded green runs without changing a file but could not produce the
  deterministic red-before/green-after evidence it was asked for.
  **Prior blocker (2026-08-28) — cleared.** The last attempt never ran a command: its mandatory
  reviewed plan required a disinterested review inside G-sync/G-validate and then resumed authored
  documentation mutation in G-closeout/G-final. The strictly forward pipeline cannot resume
  implementation after terminal review, so the plan was not executable. **A compliant plan is now
  written below and no plan-authoring step remains before dispatch** — every implementation and
  authored closeout mutation happens before serial convergence, and exactly one terminal attestation
  ends the ticket.
  **Scope narrowed again 2026-08-28 — stage E2 moved to SA170.** E2 required a full
  `QS_E2E_PARALLEL=0 make test-e2e` followed by `make ci-e2e`. That re-coupled SA135's acceptance to
  the very E2E harness whose fixed-tag collision, uncaught `subprocess.TimeoutExpired`, and
  blind readiness poll are **SA170's open defects** — the same harness that stalled phase E once
  already. Requiring a green full-E2E campaign from the lane that does not own those defects repeats
  the mistake E1 was rescoped to escape. **SA170 (#27) takes the full E2E campaign**, which it can
  run once its own fixes make the result mean something. This is the same lift that moved E1's flake
  obligation, and it leaves SA135 holding only evidence it can deterministically produce.
  **What remains here is the local PostgreSQL lifecycle and its documented precondition, nothing
  else.** Do not reopen `.github/workflows/`, `scripts/provision_ci_postgres.sh`, or
  `scripts/test_gate_parity.py`.
  **Remaining plan (serial; P/A/B/C/D and accepted E0 are not repeated). Stage order is E1, F,
  G-sync/G-validate, G-closeout/G-final, serial convergence, one terminal attestation — no review
  dispatch may be placed between G-sync/G-validate and G-closeout/G-final.**
  1. **E1 — PostgreSQL-lifecycle evidence only.** All four items are deterministic today and need no
     flake reproduction. Take the exclusive slot first; W3 has priority.
     - `make test-integration` on a host with **no** PostgreSQL running — the gate provisions its own
       server and tears it down. Stop `pg18-af10` for the window and **restart it afterwards**
       (`docker start pg18-af10`); do not remove the container or prune its volume.
     - The `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` role contract is preserved.
     - The hermetic Docker-unavailable probe still passes.
     - The asserted-unavailability negative control **fails loudly rather than skipping** when the
       server cannot be provisioned. Prove it by denying provisioning and observing the loud failure,
       then restore.
     - Leave `quickscale_test_role` owning all twelve `test_quickscale_*` databases, and drive any
       lane flip through `scripts/provision_ci_postgres.sh run --profile {restricted,bypassrls}`.
     Do **not** attempt the two E2E Docker failures, and do not run the full E2E campaign — both are
     SA170's.
  2. **F — policy and status reconciliation.** Update `validation_policy.md` at `:41` and `:94`,
     which still state "No local PostgreSQL provisioning is implied by this target or policy" against
     a Makefile that now provisions. Then ticket context, roadmap counts and dependencies, changelog
     evidence, docs navigation, and the executable consistency consumer. Keep the ticket open if any
     required gate is red.
  3. **G-sync / G-validate.** Sync current `v88` into W3, preserve concurrent closeout entries, and
     run the complete focused, provisioning, parity, lint, type, check, integration, BYPASSRLS,
     isolation, test, and quality campaign on **one frozen candidate**, unexcluded — the known-red
     protocol is retired and no `PYTEST_ADDOPTS` is authorized. `make check` is red on `v88` for
     SA173's regression (see *Band A*), which W3 neither owns nor may touch; W3's own stages are
     unaffected by it. **Run `make check`, `make test`, and
     `make quality` detached, polling for an exit-code file — `make check` alone measures ~601 s
     green and cannot complete inside one foreground call.** A truncated run is not evidence. The
     serial and CI E2E campaigns are **not** part of this stage any more.
  4. **G-closeout / G-final.** Only after G-validate is green: archive and remove SA135 from this
     open-work-only roadmap, then rerun the final frozen-tip campaign.
  5. **Serial convergence** over the complete product-and-closeout delta, then **exactly one terminal
     attestation**. Supply it with the complete base-to-tip patch as a file and a clean-byte binding
     (`git status --porcelain` empty at the exact tip) — SA167d's attestation returned no grade for
     want of exactly that input, and the same mistake must not be paid twice.
  6. **Merge only that attested exact tip** — and only after SA173 has landed and G-validate has been
     re-run on a candidate synced to the post-SA173 `v88`, fully green. Report final changed lines and
     lines-per-hour metrics from the `2026-08-26 16:07:35 +0200` measurement start.
  **Cross-worktree surface:** the merged partial edits `scripts/test_isolation_conformance.sh`,
  which SA165 (#22, W1) also owns; merge order #15 before #22 covers it.

---

## Audit-derived backlog

Tickets opened from the live findings in [arch-audit.md](../others/arch-audit.md) and
[tech-audit.md](../others/tech-audit.md), both at audit snapshot **2026-08-28**. Both documents remain the SSOT for finding
detail, evidence, and refutation; this section carries scope only, and the merge-order table above
remains the sequencing authority. **These are not follow-on work** — they are sequenced with the
implementation section. Any ticket here that closes or changes a live finding takes its audit
document onto its shared conflict surface.

The 2026-08-28 pass changed what this section owes. On the tech side it is unchanged in substance:
TA67, TA68, TA70, TA71 and TA72 map one-to-one onto SA160, SA161, SA170, SA171 and SA172, and every
tooling gap and actionable watch item is claimed. On the structural side the pass **resolved** the
prior rank-1 finding, **promoted** the privileged-command pair out of the watchlist into rank 1, and
added new evidence under rank 2. Those two movements are what **SA174 (#31)** and **SA175 (#32)**
integrate; the deferred rank-3 and rank-4 findings, and rank-2's substance, stay behind their
triggers.

- [ ] **SA170 — Give the E2E Docker harness a closed resource contract and a truthful failure report.** `Band B · Tier 2 · W3 · merge #27 · deps: SA135 (worktree ordering) · PostgreSQL + Docker slot · absorbs SA135's stalled E1 flake obligation and its full E2E campaign`
  Closes tech-audit **TA70** (`container-status-substring-match`, S4) and the carried tooling gap
  *"no test exercises the E2E harness's own failure paths"*. Opened 2026-08-27 by root-causing the
  two historical failures that stalled SA135's phase E1. Neither is a SA135 provisioning defect, and
  neither is a genuine race in Docker; both come from the **same shape** — one test opts out of the
  per-scope resource contract every other E2E resource obeys, and the readiness helper cannot report
  why anything failed.
  - **The scope contract works; the React build test is outside it.** `scripts/test_e2e.sh:557`
    derives `RUN_SCOPE` from `mktemp -d` and `:596` appends `$BASHPID` per lane, so every run and
    lane gets a unique scope; `docker-compose.yml.j2` stamps `com.quickscale.{owner,lifecycle,scope}`
    on every container and volume, and `cleanup_scoped_resources` reclaims by label.
    `quickscale_cli/tests/test_react_theme_e2e.py:657` opts out: a fixed `quickscale-react-test`
    tag, no labels, no scope prefix. Concurrent runs collide on the tag and label-driven cleanup
    cannot see the image. Its 300-second budget also times a real frontend build plus a PostgreSQL
    18 client install — seconds warm, minutes cold — and `subprocess.TimeoutExpired` is not caught,
    so a timeout aborts before the assertions and leaves the partial build behind. This is a
    benchmark wearing an assertion's clothes and **cannot be made deterministic by re-running it.**
  - **The readiness helper destroys its own diagnostic.**
    `quickscale_cli/tests/test_e2e_development_workflow.py:157-168` polls `get_container_status(name)`
    and accepts `"up" in status.lower()`. `get_container_status`
    (`quickscale_cli/src/quickscale_cli/utils/docker_utils.py:328-348`) runs
    `docker ps -a --filter name=<name>`, where Docker's `name` filter is a **substring regex**, not
    an exact match, and `-a` includes dead containers. So `<scope>_backend` matches any container
    whose name contains that string, several matches concatenate into one blob before the substring
    test, and a container that **exited immediately** yields a status the predicate reads as "not up
    yet" — the poll burns its full 40 s and reports a generic *"Backend container did not become
    running within 40s"*. **The crash reason is never surfaced**, which is exactly why repeated E1
    reruns returned green-but-uninformative: when this harness fails it cannot say why.
  **Acceptance:** the React build image is tagged from `QS_E2E_RESOURCE_SCOPE` and carries the same
  `com.quickscale.{owner,lifecycle,scope}` labels as every other E2E resource, so
  `scripts/test_e2e.sh --cleanup-scope <scope>` reclaims it and no fixed tag remains in any test;
  `subprocess.TimeoutExpired` is caught and fails with a message naming cache state and observed
  duration, and the build budget is either raised to a documented cold-cache figure or split into a
  correctness assertion plus a separately-reported duration; `get_container_status` filters on an
  anchored exact name (`name=^<name>$`), returns a structured state rather than a display string,
  and distinguishes *absent*, *created*, *running*, and *exited(code)*; the readiness poll fails
  immediately and loudly on *exited*, naming the exit code and last log lines, instead of waiting
  out its timeout; a test asserts a second concurrent scope cannot observe or delete the first
  scope's build image; **TA70** is retired.
  **Evidence policy — this is the deterministic evidence E1 could not produce.** Each defect is
  proved where determinism exists, with no flake reproduction: (1) a pure unit test over the
  readiness predicate and over `get_container_status`'s argv, fed `Exited (1) 3 seconds ago`,
  `Created`, `Up 3 seconds`, a two-container blob, and `None` — red on today's substring logic,
  green after; (2) a labelled-resource assertion that `cleanup_scoped_resources <scope>` removes the
  React build image — red today because the image is unlabelled, green after; (3) a two-scope test
  proving the fixed-tag collision is gone.
  **Also absorbed 2026-08-28 — SA135's stage E2, the full E2E campaign.** SA135's plan required
  `QS_E2E_PARALLEL=0 make test-e2e` followed by `make ci-e2e` on an unchanged tree, with exact
  cleanup and PostgreSQL baseline equality. That campaign is now **SA170's**, and runs after the
  three fixes above rather than before them. The reason is the same one that moved E1's flake
  obligation: a green full-E2E run against a harness with a fixed-tag collision, an uncaught
  `subprocess.TimeoutExpired`, and a readiness poll that cannot report a crash is not evidence of
  anything, and a red one cannot be attributed. Run it as SA170's final acceptance, where the result
  is interpretable — and where the two-scope and cleanup assertions above give it something to mean.
  **Why this is a separate ticket rather than a widening of SA135.** SA135 owns the PostgreSQL
  lifecycle; these are E2E Docker-harness defects in CLI test code and `docker_utils.py`, files
  SA135 does not touch. Per the execution rules, a scope finding is ticketed rather than fixed in
  place — which lets SA135's phase E close on evidence it can actually produce.
  **Shared conflict surface:** `quickscale_cli/src/quickscale_cli/utils/docker_utils.py`, `quickscale_cli/tests/test_e2e_development_workflow.py`, `quickscale_cli/tests/test_react_theme_e2e.py`, `scripts/test_e2e.sh`, `docs/others/tech-audit.md`.

- [ ] **SA160 — Share one correct CSRF-token helper in the React theme.** `Band C · Tier 2 · W1 · merge #20 · deps: SA161 (emission-parity ordering)`
  Closes tech-audit **TA67** (`spa-csrf-token-duplicate-cookie`, S3) — the only finding in deployment reality #3, the internet-facing generated project. `themes/showcase_react/src/hooks/useApi.ts:20-28` and `src/components/forms/FormRenderer.tsx:206-211` carry the same eleven lines: the parser splits `document.cookie` on `"; csrftoken="` and accepts the result **only when it yields exactly two parts**. Two `csrftoken` cookies yield three, so `getCsrfToken()` returns `''`, `buildRequestHeaders` (`:89-94`) skips `X-CSRFToken`, and Django rejects every POST/PUT/PATCH/DELETE with 403. The triggering state is ordinary: an `app.example.com` deployment alongside a `.example.com` cookie, the outcome of setting or changing `CSRF_COOKIE_DOMAIN`, of a sibling Django app on another subdomain, or of a stale apex-scoped cookie. GETs keep working, so the app looks alive and merely refuses to save, and no error names the cause. Fails closed — availability, not a security hole. There is no shared CSRF helper, no fetch interceptor, and no template-injected token, so no layer-up guard exists.
  **Acceptance:** one shared helper in `src/lib/` iterates cookies rather than counting split segments — splitting on `'; '`, matching the name exactly, and `decodeURIComponent`-ing the value, per Django's own documented `getCookie` — and both call sites import it with no third variant remaining; a `vitest` table test covers `'csrftoken=A; csrftoken=B'`, `'sessionid=x; csrftoken=A'`, `'csrftoken=A'`, and `''`, with the first three returning a non-empty token; the tech-audit finding is retired.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/`, generator emission parity baselines, `docs/others/tech-audit.md`.

- [ ] **SA161 — Remove the dead `get_client_ip` definitions from generated settings.** `Band C · Tier 3 · W1 · merge #19 · deps: SA165 (worktree ordering)`
  Closes tech-audit **TA68** (`generated-settings-dead-client-ip`, S4). `templates/project_name/settings/base.py.j2:61` and `settings/production.py.j2:123` both define a module-level `get_client_ip(request)`, and the production copy rebinds it under a comment claiming the rebind exists "so that production defaults … are actually in effect at request time". Neither is reachable: Django's `Settings` copies only **uppercase** names off the settings module, so `django.conf.settings.get_client_ip` does not exist, and grep across all templates returns only the two definitions. The live implementation is `quickscale_modules_orgs.current_org.get_client_ip`, which reads the uppercase `USE_X_FORWARDED_FOR` / `TRUSTED_PROXY_COUNT` settings dynamically and is correct.
  **Acceptance:** both definitions are deleted, or each carries a comment pointing at the orgs helper as the live implementation; the uppercase settings and the `REST_FRAMEWORK["NUM_PROXIES"]` recomputation are retained unchanged; the misleading behavioural comment at `production.py.j2:119-122` is removed either way; a generated project boots and proxy-aware client-IP resolution is unchanged, asserted by a test; emission parity is rebaselined with rationale; the tech-audit finding is retired.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/`, emission parity baselines, `docs/others/tech-audit.md`.

- [ ] **SA174 — Give the sanctioned privileged-command set one owner.** `Band C · Tier 2 · W1 · merge #31 · deps: SA160 (emission-parity ordering) · closes the arch audit's rank-1 finding`
  Closes arch-audit **`privileged-command-set-multi-owner`** (rank 1, promoted 2026-08-28, size S).
  The set of Django commands sanctioned to run with superuser privileges is a single runtime
  contract between the generated launcher and the generated settings, but it is *declared* four
  times with no derivation and no gate holding the copies equal: the frozen template
  `templates/project_name/settings/production.py.j2:185` `_KNOWN_PRIVILEGED_COMMANDS` (the
  **validator** — it selects superuser `DATABASE_URL` vs restricted `RUNTIME_DATABASE_URL`), the
  upgradable module `quickscale_modules/orgs/.../apps.py:36` `_PRIVILEGED_COMMANDS` (the **guard
  bypass** — `ready()` returns early and skips `_check_rls_role()`), the upgradable CLI
  `quickscale_cli/.../development_commands.py:44` `_PRIVILEGED_DJANGO_COMMANDS` (the **producer**),
  and a literal-string **oracle** at `quickscale_core/tests/test_generator/test_templates.py:4278`.
  `templates/start.sh.j2:50,61` is a fifth, by inline literal prefix.
  **The drift mechanism has already fired once, silently.** Stations 1 and 2 landed together in
  `52144290` (SA68); station 3 was added independently in `3523f9f8` (2026-08-18) under the message
  *"test: add installed-wheel lifecycle e2e"* — a test-labeled commit that introduced a new
  production decider on the privilege seam without touching the docstring at `apps.py:52` that
  claims `_PRIVILEGED_COMMANDS` is "the single source of truth". **That claim is false and was
  already false when written.**
  **Why this is not a defect and not a vulnerability.** All four sets currently hold exactly
  `{"migrate", "createcachetable"}`, and every divergence direction fails closed — a narrower module
  set means the RLS guard runs and rejects the superuser role; a narrower template set raises
  `ValueError` at settings import. The tech audit adjudicated the behavioural question separately and
  recorded **no finding**. The cost is structural and it is paid on the next change: the audit's
  change-cost probe for a third sanctioned command measures **seven stations, four of them executable
  code plus one oracle**, none derived, none gated, and station 1 unreachable in already-generated
  projects because the updater carries `settings/production.py` forward from the donor.
  **Chosen shape — the audit's Option 1, extend the existing `runtime_pins` seam.** This is the
  repository's own proven pattern: `generator/runtime_pins.py` already declares Python, Django, and
  PostgreSQL pins once and renders them into templates through `generator.py:521-526`, and tests read
  them rather than transcribing them. Option 2 (an AST parity gate over four retained copies) is the
  fallback only if rendering the set into the template proves awkward; it leaves four owners and pays
  the gate-registration tax. Option 3 (collapse to one decider) is **rejected** — it would delete the
  module's independent fail-closed backstop, which is a recorded sound decision.
  **Acceptance:**
  1. The sanctioned set is declared **once**, in `quickscale_core` alongside the existing runtime
     pins, by the component that owns the launcher↔settings contract.
  2. `production.py.j2`'s frozenset is **rendered** from that declaration exactly as
     `POSTGRES_VERSION` already is — the emitted copy remains, honestly frozen, but as a *rendering*
     rather than a restatement.
  3. The CLI copy at `development_commands.py:44` is deleted in favour of an import; the `orgs`
     copy reads the declaration through `quickscale_core.runtime`, the one import path the
     module-core-imports gate permits, **and keeps its own independent fail-closed guard** — the
     module must not start trusting the settings layer.
  4. The station-4 oracle **derives**: it compares the rendered template's set against the imported
     CLI and module sets instead of matching a literal string. It must be red if any two disagree,
     proved by temporarily widening one set and restoring the exact bytes.
  5. The false SSOT docstring at `apps.py:52` names the real owner.
  6. `start.sh.j2`'s inline literals, `OPERATIONS.md.j2`, `README.md.j2`, and
     `docs/deployment/railway.md` are reconciled with the single declaration, or their divergence is
     stated in writing.
  7. Emission parity is rebaselined with per-file rationale — this changes emitted bytes.
  8. `docs/others/arch-audit.md` retires the finding in the same change.
  **Verification:** `poetry run pytest quickscale_core/tests/test_generator quickscale_cli/tests quickscale_modules/orgs/tests -q -o addopts= --no-cov`; `make check-module-core-imports`; `make lint`, `make typecheck`, `make check`, `make quality` no worse than found. Schedule any `make test` outside W3's cluster window.
  **Why W1, and why it *reduces* the cross-lane surface.** This is generated-output plus module
  wiring — W1's charter exactly. It touches `quickscale_core/generator/`, never
  `quickscale_core/contracts/` or `quickscale_core/manifest/`, so it does not collide with SA173's
  cross-lane ownership. Moving this work off SA164 makes
  `.../settings/production.py.j2` a **W1-only surface** (SA161 then SA174) instead of a two-lane
  one, which removes the standing #19-before-#25 one-directional caution.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/generator/runtime_pins.py`, `quickscale_core/src/quickscale_core/generator/generator.py`, `quickscale_core/.../templates/project_name/settings/production.py.j2`, `quickscale_core/.../templates/start.sh.j2`, `quickscale_core/tests/test_generator/test_templates.py`, `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py`, `quickscale_cli/src/quickscale_cli/commands/development_commands.py`, emission parity baselines, `docs/others/arch-audit.md`.

- [ ] **SA175 — Assert disposition coherence for the launcher↔settings contract.** `Band C · Tier 3 · W1 · merge #32 · deps: SA174 · bounded first step only; does not widen into the deferred finding`
  Discharges the **trigger-independent first step** the arch audit attaches to
  `generated-file-ownership-unmodeled` (rank 2, deferred): *"independently of the trigger, add a
  cheap coherence assertion for the one contract now known to straddle the line, so `start.sh` and
  `settings/production.py` cannot silently take opposite dispositions."*
  **The new evidence this discharges.** Beta migration assigns upgrade behaviour **per file**, with
  no model of which files participate in a shared runtime contract — and the privileged-command
  contract lands on both sides of the line. `settings/production.py`, the **validator** holding the
  fail-closed privilege guard, is in `FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES`
  (`beta_migration.py:59`) and `FRESH_FIRST_DONOR_DJANGO_FILES` (`:92`), so it is copied **from the
  donor** — the user's existing project — over the freshly generated one. `start.sh` and
  `Dockerfile`, the **producers** of the very env vars that file validates, are in
  `IN_PLACE_INFRASTRUCTURE_TARGETS` (`:109,121`) and
  `IN_PLACE_SUBSTITUTED_INFRASTRUCTURE_TARGETS` (`:125,128`) and are copied with substitution. The
  producer is updated to the new vintage; the validator is carried forward at the old one.
  `quickscale_cli/tests/test_beta_migration_ownership_conformance.py` cannot see this: it checks
  **membership** of the taxonomy, not **coherence** across it.
  **Scope discipline — this is deliberately not the finding's fix.** The standing "neither" rule
  holds: no typed disposition metadata, no derivation of the taxonomy from emission, no versioned
  ownership manifest, no vintage negotiation against `project_contract`. Those are the finding's
  Options 1 and 2 and stay behind their trigger (a third generated-project consumer, a public
  updater, an emitted-file expansion, or a second theme). This ticket adds **one assertion and a
  named contract group**, nothing more. Widening is a scope finding and gets its own ticket.
  **Why after SA174.** The audit records the interaction directly: do the command-set consolidation
  first, then let the coherence work reference the now-single declaration rather than re-deriving
  which files participate in the contract. Ordering only — no shared file.
  **Acceptance:** the launcher↔settings contract is named once as a group of participating emitted
  paths (`settings/production.py`, `start.sh`, `Dockerfile`), sourced from SA174's single
  declaration rather than re-listed; a conformance assertion in
  `test_beta_migration_ownership_conformance.py` fails when members of one named group are assigned
  dispositions from opposite families (donor-carried vs in-place-substituted); the assertion is
  proved by temporarily moving one member across the line, observing red for the intended reason,
  and restoring the exact bytes; the **existing** donor-wins disposition for `settings/production.py`
  is **preserved unchanged** — the audit argues it is defensible on its own terms, so this ticket
  makes the split *visible*, not different; the deferred finding stays open with its trigger intact
  and `docs/others/arch-audit.md` records the first step as discharged without closing it.
  **Shared conflict surface:** `quickscale_cli/tests/test_beta_migration_ownership_conformance.py`, `quickscale_devtools/src/quickscale_devtools/beta_migration.py`, `docs/others/arch-audit.md`.

- [ ] **SA164 — Adjudicate the arch-audit watchlist's unevaluable and drifted items.** `Band C · Tier 3 · W2 · merge #25 · deps: SA166 (worktree ordering)`
  The 2026-08-28 pass rewrote this watchlist: the prior rank-1 `ci-environment-hand-replicated`
  resolved (retiring the environment-schema item), the privileged-command pair **fired and was
  promoted to a ranked finding** — now SA174's — and three new items were minted inside the landed
  provisioning derivation. What remains for SA164 is one item carrying an explicit action, one naming
  question that becomes load-bearing on a specific trigger, and the restatement of the three new
  not-fired items so their triggers survive the next pass.
  - **SA92 migration-squash discovery tuple — artifact located 2026-08-21, now evaluable.** The audit recorded this as unlocatable, but the artifact is `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` — a bounded literal tripwire for cross-table `UPDATE … SET organization_id` DML in migrations. The prior search missed it because it grepped for `squash` in source rather than in test filenames. SA167c's merged partial removed the helper's dependency on the retired `django_apps:` key; `_migdir()` still uses the conventional path and returns `None` when it is absent, so SA164 must make that lookup fail hard rather than silently skipping a module. Its authoritative backstop is also still a catalog/data parity gate anchored to `v87`, a retired release ref no longer resolved by the quality gate.
  - **Privileged-command set — promoted out of the watchlist and out of this ticket.** The
    2026-08-28 structural pass promoted it to the arch audit's **rank-1 finding**
    (`privileged-command-set-multi-owner`), counting four independent owners of one security-relevant
    command set. It is no longer a watch item and is no longer SA164's: **SA174 (#31, W1)** owns it.
    SA164 must not edit `.../settings/production.py.j2`, `orgs/apps.py`, or
    `development_commands.py` — that removes this ticket's only cross-lane file surface.
  - **`trigger_inputs` has drifted from its name.** `check_gate_parity.py:2652-2690` uses the field as a bidirectional partition of `e2e.yml`'s path allowlist, not as "what changes should trigger this gate" — which is why `check-core-compat`'s trigger is `quickscale_modules/backups/**`. Not a defect; the check it performs is real and exact. Becomes load-bearing only if a gate is ever *skipped* on the basis of `trigger_inputs`.
  **Acceptance:** the SA92 item is re-anchored to `test_sa92_migration_squash_guardrail.py` with a stated trigger, its `_migdir()` fallback fails loudly instead of guessing the path, and its `v87`-anchored parity backstop is re-anchored to the current regenerated migrations; `trigger_inputs` is either renamed to describe what it does or its docstring/schema description records the actual semantics plus the skip-based promotion trigger; the arch audit's **current** watchlist is re-stated with its triggers intact rather than the superseded pre-resolution list — the two hand-pinned literals minted inside the new provisioning derivation (`provision_ci_postgres.sh:93,96`, `!= teams` and `== 12`, trigger: a thirteenth shipped module or `teams` graduating), the second copy of the PostgreSQL major (`provision_ci_postgres.sh:15` against `runtime_pins.py:30`, trigger: the DR engine's `pg_dump`/`pg_restore` major-version contract coming to depend on the two agreeing), and the roughly six count-pinned oracles in `scripts/test_gate_parity.py` (trigger: the next gate addition paying more than two oracle edits, or two oracles disagreeing) — noting for each that it is **not fired**; `docs/others/arch-audit.md` is updated in the same change.
  **Shared conflict surface:** `docs/others/arch-audit.md`, `scripts/gate_registry.json`, `scripts/check_gate_parity.py`, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`.

- [ ] **SA165 — Discharge the tech-audit watch items that carry an action.** `Band C · Tier 3 · W1 · merge #22 · deps: SA167d (worktree ordering)`
  Of the remaining items in the tech audit's *Notes*, most are accepted trade-offs or are owned elsewhere (the local-wheelhouse seam is discharged by the closed SA150; integration-branch CI, generator lock generation, the DB-free healthcheck, the CRM count fallbacks, and non-durable atomic state writes are each recorded as deliberate and are **not** in this ticket's scope). Four carry a concrete action:
  - **`flush_empty_consolidated_sections` swallows a corrupt state file.** `quickscale_core/src/quickscale_core/schema/state_schema.py:386-388` returns silently on `yaml.YAMLError, OSError`, skipping the explicit `modules: {}` / `managed_files: []` markers downstream readers use to distinguish "M2 has spoken" from pre-M2 state. The trigger is narrow — the file was just written successfully by `save()` — but this is exactly the silent-fallback shape the Fail-Hard Principle names (`decisions.md:634`, `:716-732`).
  - **The isolation-gate skip allowlist matches on message, not test identity.** `scripts/test_isolation_conformance.sh:184` keys on `message.startswith('got empty parameter set')`, silencing an empty parameter set on *any* of the eleven parametrized tests in `test_tenant_table_conformance.py`, not only the two `PENDING_REMEDIATION` ones its own comment describes. Narrowing it to the two test names costs one line.
  - **`_HOST_DEPENDENT_PATHS` is a new hand-maintained exception station.** `be5cf024` added `frozenset({".env"})` to the SA90 emission byte-parity gate (`quickscale_core/tests/test_generator/test_generator.py:1023`). The justification is sound and the `755`/`644` mode normalization correctly removes a umask dependency, but this is an exception list on the repository's strictest gate: a second entry deserves scrutiny, a third deserves a derivation.
  - **Generated local-development credentials are predictable by construction.** `generator.py:507-508` derives `runtime_db_role = f"{package_name}_app"` and `runtime_db_password = f"{role}_password"` into `db/init.sql`, `docker-compose.yml`, and `.env.example`, none of which `.gitignore.j2` excludes. Safe as shipped — no published DB port, local dev only, production supplies `RUNTIME_DATABASE_URL` from the environment — but undocumented.
  **Acceptance:** `flush_empty_consolidated_sections` raises or reports rather than returning silently, with a regression test asserting the raise and not a log, and the fail-hard deviation is retired from the audit; the isolation skip allowlist keys on the two `PENDING_REMEDIATION` test identities rather than a message prefix, and a deliberately emptied ENROLLED set turns the gate red; `_HOST_DEPENDENT_PATHS` gains a written per-entry rationale and a monotonicity note stating the second/third-entry escalation, or is derived; `OPERATIONS.md` states explicitly that the generated local credentials must not survive into any shared environment; `docs/others/tech-audit.md` is updated to reflect each discharge.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/schema/state_schema.py`, `scripts/test_isolation_conformance.sh`, `quickscale_core/tests/test_generator/test_generator.py`, `quickscale_core/.../templates/OPERATIONS.md.j2`, `docs/others/tech-audit.md`.

- [ ] **SA166 — Require a testimony trail for behavioural commits.** `Band C · Tier 3 · W2 · merge #24 · deps: SA167c`
  Closes the tech audit's carried tooling gap *"no gate requires a changelog/ticket trail for behavioural commits"*. `d3d4c633` and `d4b0e834` were both titled "v0.87.0: QuickScale 0.87.0" while in fact changing hosted and publish provisioning, and `d3d4c633` left a repository conformance test red (TA66/SA158). Both audits independently flagged the same shape: a release-shaped message carrying a CI-topology change. Recorded in the audit as maintainer-process risk rather than a source finding, which is why this is Tier 3.
  **Acceptance:** a change touching `.github/workflows/`, `scripts/gate_registry.json`, or the provisioning stations requires either a roadmap ticket reference or a `CHANGELOG.md` entry, enforced mechanically rather than by convention; the check is registered in `scripts/gate_registry.json` and passes `scripts/check_gate_parity.py`; the gate fails on a deliberately introduced untitled workflow change, reverted before merge; false-positive cost is measured on the existing history and the rule is narrowed until it is quiet on legitimate release commits; the tooling gap is retired from the tech audit.
  **Shared conflict surface:** `scripts/gate_registry.json`, `Makefile`, CI workflow, `docs/others/tech-audit.md`.

- [ ] **SA171 — Make stale-lock clearing atomic in both file locks.** `Band C · Tier 2 · W3 · merge #28 · deps: SA170 (worktree ordering)`
  Closes tech-audit **TA71** (`backup-lock-stale-clear-toctou`, S3, opened 2026-08-28).
  `quickscale_core/.../dr_engine/_lock.py:119-137` decides a lock is stale by `stat`-ing it and then
  `unlink`-ing it — two separate syscalls. Two backup runs can both observe the same stale lock,
  both unlink it, and both then create their own, so the "exclusive" backup lock admits two holders.
  `advisory_lock.py`'s acquire/release/stale path hand-rolls the identical mtime/PID shape and
  carries the same race. Neither uses `flock`. The blast radius is deployment reality #3: two
  concurrent `pg_dump` runs against one database, or a restore racing a backup.
  **Acceptance:** stale-lock reclamation is atomic — the check and the act are one operation (an
  `flock`-guarded critical section, or `os.rename`/`O_EXCL` re-creation keyed on the observed
  identity) — in **both** `dr_engine/_lock.py` and `advisory_lock.py`; a two-thread barrier test
  drives two acquirers into the stat/unlink gap and asserts exactly one holder, red before the fix
  and green after, in both implementations; the existing stale-detection behaviour (a genuinely
  abandoned lock is still reclaimed, not deadlocked) is preserved and asserted; **TA71** is retired
  from the tech audit.
  **In-ticket option, not a maintainer decision:** the audit's structural smell asks why the
  repository owns two hand-rolled filesystem locks at all. Consolidating them is **out of scope** —
  fix the shape twice and record the consolidation question on the structural watchlist. Widening
  into a shared lock primitive is a scope finding and gets its own ticket.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/dr_engine/_lock.py`, `quickscale_core/.../advisory_lock.py`, `docs/others/tech-audit.md`.

- [ ] **SA172 — Make `apply_force_rls`'s idempotency claim true.** `Band C · Tier 3 · W3 · merge #29 · deps: SA171 (worktree ordering)`
  Closes tech-audit **TA72** (`force-rls-apply-idempotency-claim`, S4, opened 2026-08-28).
  `quickscale_modules/orgs/.../tenancy.py:536-546` documents `apply_force_rls` as "**Idempotent**",
  but `_FORCE_RLS_FORWARD_SQL` issues bare `CREATE POLICY` at `:510` and `:521`, and PostgreSQL has
  no `CREATE POLICY IF NOT EXISTS`. A second application against an already-enrolled table aborts
  the migration with `42710 duplicate_object`. The claim is safe today only because the one
  re-applying caller, `refresh_force_rls_policies` (`:584`), calls `revert_force_rls` first, and the
  reverse template already uses `DROP POLICY IF EXISTS`. The hazard is a future module migration
  calling the helper on the documented assurance that doing so is safe — on the repository's most
  security-critical migration helper.
  **Acceptance:** the forward template is prefixed with the same `DROP POLICY IF EXISTS` pair the
  reverse template already carries, making the documented contract real (the two-line fix), **or**
  the docstring is corrected to state the helper is not idempotent and must be preceded by
  `revert_force_rls` — with a test asserting whichever contract is chosen by applying twice against
  a real table; the read/write policy split (`FOR ALL` tenant write plus `FOR SELECT` with the
  `operator_access` OR clause) is unchanged, asserted by comparing `pg_policies`' `qual`/`with_check`
  text against the template for each enrolled table, which also closes the tech audit's
  *"RLS policy assertions check existence, not predicate text"* tooling gap and the related
  structural smell; **TA72** is retired.
  **Also carried here (watch items, not findings):** `refresh_force_rls_policies:596-620` derives
  table names from the Django default convention and drops misses through `to_regclass(...) IS NOT
  NULL` without warning — latent today (all 21 enrolled tables match the convention, empirically
  verified) but a silent no-op the moment an enrolled model declares a non-conventional `db_table`.
  Deriving from `apps.get_model(...)._meta.db_table`, the same source `check_tenant_model_isolation`
  already uses, closes it in the same change.
  **Shared conflict surface:** `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py`, `scripts/test_isolation_conformance.sh`, `docs/others/tech-audit.md`.

### Audit items deliberately **not** ticketed

Recorded so the absence is a decision rather than an oversight.

| Item | Source | Why no ticket |
|---|---|---|
| `generated-file-ownership-unmodeled` (arch rank 2) — **substance only** | arch, deferred | Held by the standing **"neither"** rule. Trigger: a third generated-project consumer, public updater, emitted-file expansion, or second theme. Options 1 and 2 (typed disposition metadata; a versioned ownership manifest with vintage negotiation) stay behind it. Its **trigger-independent first step is ticketed as SA175 (#32)** under the carve-out in the standing rules. Related weakness tracked in SA152. |
| `deletion-invariants-per-boundary-reimplementation` (arch rank 3) | arch, deferred | Same rule. Trigger: `teams`, a GDPR erasure command, bulk-admin deletion, or a second deletion boundary. Design together with `org-model-universe-hand-enumerated` at `teams` kickoff. |
| `org-model-universe-hand-enumerated` (arch rank 4) | arch, deferred | Same rule. Trigger: `teams` adds a tenant model, or a module adds a `PROTECT`/non-deferrable dependency among purge-owned rows. |
| Tooling gaps — dependency-vulnerability scanner, security static analysis | tech | Closed by SA123's implemented and accepted Trivy/Bandit gates; evidence archived in [CHANGELOG.md](../../CHANGELOG.md). |
| Watch items recorded as deliberate | tech *Notes* | Integration-branch CI, generator lock-generation policy, the DB-free healthcheck, CRM/billing cross-tenant `all_objects` count fallbacks, and rename-atomic-but-not-durable state writes are each argued and accepted in the audit; re-examine only on the triggers stated there. |
| Four suppressed `sqlparse` CVEs | tech *Notes* | `CVE-2026-54284/-59893/-71491/-59894` are accountable and unexpired, but all four expire **2026-09-30** and will re-block CI on the same day. Dependency maintenance, not v88 scope — but it lands inside the release window, so track it. |
| `blog/feeds.py` double System-org resolution | tech *Notes* | Narrow trigger (a corrupt singleton row). Not promoted; re-examine if a second fail-closed feed path appears. |
| `table_has_force_rls` schema qualification | tech *Notes* | Single-schema deployments unaffected. Trigger: a schema-per-tenant option. |
| Tooling gap — CSRF helper test | tech | An acceptance criterion inside **SA160**, not a separate item. |
| Structural smell — no `src/lib/http` seam | tech | Created by **SA160**'s shared-helper requirement; the other two smells are discharged. |
| Clean sweeps (10) | tech | Verified-clean records, not open items. |

---

## Unscheduled backlog (post-v88)

Not assigned to a v88 track. Listed here so the finding is not lost.

- [ ] **SA152 — Refresh the beta-migration maintainer targets for the current release.** `Post-v88 · Tier 3 · deps: none`
  Audit of `make beta-migrate-fresh` / `make beta-migrate-in-place` (2026-08-21) found the mechanics current: the Makefile flag surface (`DONOR`, `RECIPIENT`, `DRY_RUN`, `CONTINUE`, `REPORT`) matches `build_argument_parser()` in `quickscale_devtools/src/quickscale_devtools/beta_migration.py`; every command in `VERIFICATION_COMMAND_SPECS` still exists on the CLI; and the file-ownership taxonomy is in sync with the emitted `showcase_react` template set, enforced by `quickscale_cli/tests/test_beta_migration_ownership_conformance.py` (7 passing, including forward and reverse staleness checks). The residual gaps are these:
  - **Settled migration-history collision.** The workflow's verification stack runs `quickscale manage migrate` against a recipient that may carry an existing database. The clean-break migration policy makes a fresh database the only upgrade path, so this in-place assumption must be reconciled within SA152.
  - **No end-to-end exercise.** The targets appear in no CI workflow and no entry in `scripts/gate_registry.json`. Coverage is unit-level taxonomy conformance only; a `DRY_RUN=1` / checkpoint-only path is never run against a real donor/recipient pair, so breakage surfaces first for a maintainer mid-migration.
  - **Silent skip in the conformance gate.** `_template_emitted_paths()` calls `pytest.skip()` when the template tree is not found, so a path-resolution regression turns the ownership gate green instead of red. This is the silent-fallback pattern tracked in [tech-audit.md](../others/tech-audit.md).
  - **Stale doc provenance.** [beta-site-migration.md](../planning/beta-site-migration.md) is headed "shipped in v0.81.0" against a `VERSION` of 0.87.0, and describes the tool as "backed by Python scripts under `scripts/`" when `scripts/beta_migrate.py` is an eight-line wrapper over `quickscale_devtools`.

  **Acceptance:** the in-place workflow's database precondition is reconciled with the SA151 no-migration-history policy and the resolution is stated in the playbook; a cheap non-mutating smoke gate exercises both targets against a generated donor/recipient pair (`DRY_RUN=1` for fresh-first, checkpoint-only for in-place) and is registered in `scripts/gate_registry.json` with `scripts/check_gate_parity.py` passing; `_template_emitted_paths()` fails loudly instead of skipping when the template tree is missing, with a regression test asserting the raise; the playbook's version and implementation-location claims match the tree; `make quality` is no worse than found.

  **Shared conflict surface:** `docs/planning/beta-site-migration.md`, `scripts/gate_registry.json`, `Makefile`, CI workflow, `docs/others/tech-audit.md`.

- [ ] **SA153 — Close the property-portal basics gap in `listings`.** `Post-v88 · Tier 2 · deps: none · highest-value post-release work`
  Audit driven by the planned `buenosairesproperties.com` migration (2026-08-21). The `listings` module ships a deliberately generic `AbstractListing` plus a concrete `Listing`, and `blog` is substantially complete, so the gap is not module existence — it is property-vertical depth and public presentation. Every sub-item below is a *basic*: a real-estate portal cannot launch without it. The umbrella is acceptance-only; each sub-item owns its own implementation and may be split into a child ticket.
  - **Image galleries.** `AbstractListing` carries a single `featured_image` with no child image model and no ordering. Real-estate listings need many images per property. A `ListingImage` child table must carry its own `organization_id` column per the locked child-table RLS policy in [decisions.md](decisions.md) — no parent-join RLS.
  - **Property attributes.** `AbstractListing` has no bedrooms, bathrooms, area, property type, or operation type (sale/rent). The documented answer is subclassing, but `views.py`, `urls.py`, `admin.py`, and `ListingFilter` in `quickscale_modules/listings/src/quickscale_modules_listings/` are all bound to the concrete `Listing`. Subclassing today yields a model and an admin base but no working public views, URLs, or filters; the Tier 2 abstract-model contract in [module-extension.md](module-extension.md) is therefore only half-delivered.
  - **Filtering on those attributes.** `ListingFilter` exposes price range, location, and status only. There is no keyword search over `title`/`description`, despite the module README claiming search as an implemented feature.
  - **Currency.** `listing_detail.html` hardcodes a `$` prefix against a single-currency `DecimalField`. Markets that quote in more than one currency cannot be represented, and the rendered symbol is unlabeled.
  - **Spanish / i18n.** Generated settings set `USE_I18N = True`, but there is no `LocaleMiddleware`, no locale directories, and no marked strings in any module template or admin label.
  - **Public presentation.** `ListingsPage.tsx` and `BlogPage.tsx` in `showcase_react` are dashboard link cards that point at the Django views; the public surface is the modules' zero-style semantic-HTML templates. There is no themed public listing experience.
  - **Lead capture on a listing.** `forms` and `crm` both ship, but nothing links an inquiry to the listing that produced it — no per-listing inquiry surface and no listing reference on the resulting contact or deal.
  - **SEO.** No `django.contrib.sitemaps` usage anywhere in the tree, no `robots.txt`, and no Open Graph or structured-data output. Slugs and semantic HTML are the whole current surface.
  - **Public read API.** `listings` and `blog` expose staff-only publish/media *write* endpoints. There is no public JSON read endpoint, so a user-owned frontend cannot consume listings or posts without project-owned code.

  **Acceptance:** a generated project with `listings` enabled serves a property listing with multiple ordered images, vertical attributes, and attribute-aware filtering including keyword search, without project-owned view/URL/filter code; the module README's feature claims match the shipped filter surface; multi-currency prices render with an explicit currency label and no hardcoded symbol; `LocaleMiddleware`, locale directories, and marked strings are present and a non-English locale renders module templates translated; the public listing and blog surfaces are themed rather than zero-style; an inquiry submitted from a listing produces a CRM record that references that listing; sitemaps, `robots.txt`, and Open Graph output are emitted for listing and post detail pages and are asserted by tests; a documented public read endpoint returns published listings and posts scoped to the resolving organization; every new child table carries `organization_id` with its own RLS policy and RLS-boundary coverage matching the existing `test_rls_boundary.py` pattern; `make quality` is no worse than found.

  **Shared conflict surface:** `quickscale_modules/listings/`, `quickscale_modules/blog/`, `quickscale_modules/crm/`, `quickscale_modules/forms/`, `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/`, `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/base.py.j2`, `docs/technical/module-extension.md`, `docs/technical/decisions.md`.

- [ ] **SA154 — Property-portal optional capabilities.** `Post-v88 · Tier 3 · deps: SA153 · inventory only, not schedulable`
  Capabilities identified alongside SA153 that are valuable for a real-estate vertical but are not launch blockers. Deliberately held behind SA153 so the basics land first and none of these widen that ticket. This entry exists to keep the findings recorded; each sub-item is expected to become its own ticket when a real project pulls it forward, and none is scheduled by listing it here.
  - **Map and geocoding.** Latitude/longitude on listings plus a map surface. Expected on regional property sites but shippable after launch.
  - **Saved searches, favorites, and match alerts.** Per-user persisted searches with email notification on new matching listings, over the existing `notifications` module.
  - **Agent and office profiles.** Per-agent pages and listing attribution, analogous to the `blog` module's `AuthorProfile`.
  - **Portal syndication feeds.** Outbound feeds for third-party real-estate portals. High commercial value, high effort, per-portal format authority.
  - **Virtual tours and video embeds.** Could build on the existing `social` module's embed metadata resolution rather than a new provider integration.
  - **Featured and premium listing placement.** Paid placement tiers, which would tie the vertical into the `billing` credits ledger.
  - **Blog-to-listing cross-linking.** Editorial content surfacing related listings, and listings surfacing related posts.
  - **Full-text search.** PostgreSQL `SearchVector`-backed search, once listing volume makes the SA153 keyword filter insufficient.

  **Acceptance:** none — this is a recorded backlog inventory, not schedulable work. It is discharged when every sub-item has either been promoted to its own ticket with its own acceptance criteria or been explicitly dropped with a written rationale. Promoting a sub-item does not authorize implementing it inside SA153.

  **Shared conflict surface:** none while unscheduled; inherited from SA153 for any sub-item promoted after SA153 merges.

---

## References

- [Changelog — completed and closed work](../../CHANGELOG.md)
- [Architectural audit — live structural findings](../others/arch-audit.md)
- [Technical audit — live defect posture](../others/tech-audit.md)
- [Decisions — policy authority](decisions.md)
- [Validation policy — command authority](validation_policy.md)
- [v88 ticket context — concepts and implementation notes](v88_ticket_context.md)
