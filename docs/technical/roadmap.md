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
- Before a completed-ticket merge-back: sync the integration branch into the worktree, resolve there, run the ticket's verification, review the exact tip, then merge that tip. An explicitly authorized partial checkpoint may merge only as retained delivery; it stays open and clears no branch-state gate.
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
- **A run killed by a cutoff returns no exit code and is not evidence** — neither of green nor of
  red. One recorded acceptance stall was caused by exactly this, and the gate underneath turned out
  to be red. `make test` and `make quality` must therefore be launched detached (`nohup`, exit code
  written to a file, poll for the file). `make check` no longer needs it: measured at **184 s
  green** on `v88` after the `check-gate-suites` parallelisation, it fits inside a single foreground call —
  see [Gate cost](#gate-cost--re-measured-2026-08-29).
- **A gate that is red on the integration branch is attributed to exactly one ticket, and is never
  deselected.** Test exclusion via `PYTEST_ADDOPTS`, `--deselect`, or a Makefile/CI edit is not a
  scheduling tool: it removes the oracle for the defect the owning ticket exists to fix. Name the
  owner, let the other lanes run unexcluded and treat their evidence as provisional, and complete
  no other ticket merge until the owner is green. An authorized partial checkpoint from the owning
  ticket does not clear the gate. The 2026-08-28 interim known-red protocol is retired for exactly
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
| **A — Restore enforcement** | Gate layer reports green while not running, or runs red on HEAD. | **SA173** — its product work is merged, but `quickscale_modules_storage/__init__.py` measures 45% per-file coverage against the required 80%, so the `make test` chain and ticket acceptance stay red (see below) |
| **B — Release work on the critical paths** | The two longest serialized chains, one holding the exclusive service slot. | SA167c (critical path, after SA173); SA135; SA170; SA167d |
| **C — Bounded independent fixes** | No dependants, small blast radius; absorbed as slack filler. | SA160, SA161, SA164, SA165, SA166, SA171, SA172, SA174, SA175 |

### Band A — one coverage gate is red, and it is the whole blocker

**Measured 2026-08-29 on `v88`.** SA173's product work is merged (`e0730ae9`, then the checkpoint
`4c311a73` integrated through `5bf03b40`/`b5b84ca9`). The eighteen CLI failures, the seven stale
fixtures, the standalone-shim breakage, the ACTIVE-placeholder edge, and criterion 8's negative proof
are all closed on the integration branch; that diagnosis is archived in
[CHANGELOG.md](../../CHANGELOG.md) and is not planner scope any more.

**What is left is one file, and it is now measured exactly.** Two detached runs on `v88` at
`7818ab0c`, clean tree, 2026-08-29:

- **`make check` — exit 0 in 184 s.** The branch-state gate that W1's and W3's acceptance criteria
  name is **green**; `pytest scripts/` inside it is 1319 passed in 92 s.
- **`make test` — exit 2 in 82 s**, failing at `test-integration` for **exactly one reason**:
  `→ Files below 80% coverage: quickscale_modules_storage/__init__.py  11  6  45%  28-35`.
  Nothing else in the run is red. Every module clears the 90% overall floor (storage itself at
  **94.88%**, overall mean **94.31%**).

So the branch-state gate is **one per-file coverage threshold on six statements**. Reproduced
directly:

```text
$ poetry run pytest quickscale_modules/storage/tests -q -o addopts= --cov=quickscale_modules_storage
Name                                                       Stmts  Miss  Cover  Missing
.../quickscale_modules_storage/__init__.py                    11     6    45%  28-35
.../adapter.py  31 1 97%   .../apps.py  6 0 100%   .../helpers.py  167 4 98%
39 passed
```

Lines 28-35 are the **entire body of `__getattr__`** — the lazy re-export shim that keeps package
initialization dependency-free so the manifest adapter can load during `quickscale apply` before
module dependencies are installed. Nothing else in the package is under-covered. The shim is
load-bearing and must not be deleted; the gate must not be weakened or excluded. The fix is a small
unit test over `__getattr__`: one assertion per exported name in `__all__` resolving through
`helpers`, and one asserting `AttributeError` for a name outside `__all__`. **This is bounded, DB-free,
W2-local work — not a campaign.**

**Consequences.**

0. **`make check` is already green, so W1's and W3's `make check` acceptance criteria are satisfiable
   on `v88` today.** What they cannot obtain is a green `make test`, which is the remaining half of
   their merge evidence.
1. **SA173 stays band A.** By the ordering rule a ticket that makes a gate tell the truth outranks
   every other ticket, and this is the branch-state gate all three lanes' merge evidence waits on.
2. **W1 and W3 can implement and validate but cannot complete a merge.** Their acceptance requires a
   green `make check`/`make test` on a candidate synced to current `v88`.
3. **After the coverage fix**, SA173 owes the unexcluded frozen-candidate campaign, authoritative
   documentation closeout, and one terminal attestation — then the gate clears for all three lanes at
   once.

#### Gate cost — re-measured 2026-08-29

The `check-gate-suites` parallelisation (`-n auto --dist loadfile`, `Makefile:1021`) cut that stage
from 299 s to 94 s with byte-identical outcomes, and `lint-frontend` was measured at 13.89 s — it is
**not** the dominant cost, contrary to the figure this file previously carried. Profiled green path:

| Stage | Time |
|---|---|
| lint + typecheck + core (2886) + cli (2135) unit tests | 41 s |
| core-compat, module-core-imports, manifest-sync, org-context, csrf-exempt | 5 s |
| **check-gate-suites** (`pytest scripts/`, parallel) | **94 s** |
| check-dependency-vulnerabilities (Trivy) | 50 s |
| check-security-static-analysis (Bandit) | 3 s |
| gate parity + CI gate generation | ~5 s |
| lint-frontend | 14 s |
| **Total (composed)** | **~212 s** |
| **Measured end-to-end, `v88`, 2026-08-29** | **184 s, exit 0** |

`make check` therefore now fits comfortably inside a single foreground tool call. **`make test` and
`make quality` are still to be launched detached** — write the exit code to a file and poll it. The
rule that survives unchanged is the important one: **a run killed by a cutoff returns no exit code and
is not evidence**, neither of green nor of red. One recorded acceptance stall was caused by exactly
that, and the gate underneath turned out to be red. `--dist loadfile` is load-bearing, not a tuning
knob; the default `loadscan` splits `test_quality_baseline_monotonicity.py` across workers and
produces spurious failures.

#### Full-suite baseline — SA170's four rows only

`make check` filters with `-m "not integration and not e2e"`; the unfiltered combined suite does not
and costs ~80 minutes. The 2026-08-28 measurement's SA173 rows are green and its pollution row is
retired with the code path that caused it (archived in [CHANGELOG.md](../../CHANGELOG.md)). What
remains is four `e2e` rows, all **SA170's**, carried forward unre-measured — an 80-minute run is not
repeated to restate an attribution no ticket disputes:

- `test_e2e_development_workflow.py::…::test_logs_with_options`
- `test_e2e_development_workflow.py::…::test_manage_test_command`
- `test_e2e_installed_wheel_lifecycle.py::test_installed_wheel_plan_apply_up_all_modules`
- `test_e2e_full_workflow.py::TestDockerIntegration::test_sa142_no_cleanup_diagnostic_probe`

### Dependency graph and critical path

```text
v88 — three worktrees, fourteen open merge positions carrying fourteen open ticket entries, one merge queue

W2 (gates & declared wiring)   ★ CRITICAL PATH
  SA173 ─► SA167c ─► SA166 ─► SA164     #30, #21, #24, #25
  (SA173: product merged; storage coverage + closeout open.
   SA167c: Phase-A slice merged, A retry gated on SA173 acceptance, B-F open)

W1 (module wiring + generated-output fixes)
  SA167d ─► SA165 ─► SA161 ─► SA160 ─► SA174 ─► SA175     #18, #22, #19, #20, #31, #32

W3 (service lifecycle — exclusive PostgreSQL/Docker slot)
  SA135 ─► SA170 ─► SA171 ─► SA172      #15, #27, #28, #29
```

**W2 sets the release date.** The critical path is four positions — `SA173 ─► SA167c ─► SA166 ─►
SA164` — entirely inside W2 with no prerequisite outside it. W3 holds the exclusive slot and takes
scheduling priority while one of its legs is active, but its four positions are a *queue*, not a
chain. **Finishing SA167d or SA135 does not shorten the release; finishing SA173 does** — it is the
only work on the board that is both a branch-state gate and on the critical path. W1 is the longest
lane at six positions, but its four tails are band C and may slip past the release, so it does not set
the date.

**No cross-worktree dependency edges remain.** One cross-worktree *shared file* does, made
one-directional by merge order: `scripts/test_isolation_conformance.sh` — SA135's merged partial wrote
it; SA165 (#22, W1) narrows one line over those settled bytes; #15 merges before #22.
`.../settings/production.py.j2` is no longer cross-worktree: moving the privileged-command finding off
SA164 (W2) onto SA174 (#31, W1) left it with two W1 owners, SA161 (#19) then SA174 (#31), sequenced on
one lane.

**One cross-lane hazard already fired, and is recorded so it is not repeated.** W3's merged SA135
remediation `203fcd61` added the `OVERRIDE`→bundled fallback in
`quickscale_core/.../contracts/module_discovery.py`, which turned **W2's** SA167c caller suite red two
days later. Neither ticket's allowlist named the other's surface, because the coupling is behavioural
rather than textual: `quickscale_core/contracts/` and `quickscale_core/manifest/` are read by every
lane. **Treat any edit under those two packages as cross-lane** — announce it in the merge queue and
re-run the other lanes' focused caller suites before merging, even when no file is shared. SA173 owns
both packages for the rest of v88, and its own regression was the second instance of the same shape.

The manifest-reading `entry_point.py`, the fail-hard `QUICKSCALE_LOCAL_WHEELHOUSE` version-spec seam,
the regenerated migration baseline, and `scripts/provision_ci_postgres.sh` are settled tree state that
open tickets build on rather than re-open.

### Track rebalance — evaluated 2026-08-29, **no move made**

Lanes are **W1 6 · W2 4 · W3 4**. Every open ticket was re-tested against the three questions — is it
independent of the rest of its lane, is another lane idle, and is it on or feeding the critical path.
**W1 and W3 are both effectively idle**, so question two now passes for the first time; no ticket
passes all three:

- **The critical path cannot be shortened by moving work off W2.** `scripts/gate_registry.json` and
  `quickscale_modules/*/module.yml` are W2-owned surfaces that never cross worktrees, and three of
  W2's four tickets (SA167c, SA166, SA164) register or edit gate-registry entries. Moving any of them
  would put two lanes into one registry file — a merge hazard on the release-setting chain, which is
  the one place it is least affordable.
- **W2's tail is not splittable from its head either.** SA167c's Phase-A acceptance is answered by
  SA173's presence contract, and SA164's substance needs `django_apps:` retired by SA167c. Splitting
  SA173 from SA167c would force a cross-lane sync in the middle of an acceptance chain.
- **W1's four band-C tails (#19, #20, #31, #32) cannot move to W3.** They are DB-free generator and
  module-wiring work; putting them on the exclusive-slot lane would re-serialize them behind SA135 and
  SA170 for nothing — the exact defect a previous pass corrected by moving SA161/SA160 the other way.
  #19 → #20 → #31 is also one ordered emission-parity rebaseline run, which may not be split.
- **SA165 (#22) looks moveable to W3 and is not.** It shares `scripts/test_isolation_conformance.sh`
  with SA172 (#29, W3), so the move would make that file single-lane — a real gain. But SA165 is
  DB-free, and the move would place it *behind* SA135 and SA170 on the slot lane, delaying a ticket
  that today waits only on lane ordering. The shared file is already one-directional under merge order
  #15 → #22 → #29. **Cost exceeds benefit.**

**The idleness is not a track-assignment problem and no move fixes it.** W1 and W3 are stopped on a
*branch-state* gate — one under-covered file on W2 — not on a queue position. The lever is SA173's
coverage fix, not a rebalance. Meanwhile **neither lane should sit idle**: both can execute their next
action and bank durable artifacts today (see *Next action per lane*); only the final merge-evidence
re-run has to wait.

**W1 is the longest lane at six positions and that is deliberate**: it is off the critical path, so
band-C work accumulates there rather than behind the release-setting chain. Band-C positions are
*earliest-eligible*, not commitments; the four W1 tails are the slip budget.

**Conflict surface, unchanged by this pass.** No lane move above adds a *code* file to a second lane.
The standing closeout surface is `CHANGELOG.md`, this file, `docs/technical/v88_ticket_context.md`, and
an audit document when a ticket closes a live finding — covered by the merge procedure's
sync-resolve-rerun-review step in the execution rules.

### Lane state

**Verified 2026-08-29 against the branches themselves.** Measure current ahead/behind rather than
trusting a transcribed count:

```bash
for w in wt-track1 wt-track2 wt-track3; do echo -n "$w: "; git rev-list --left-right --count v88...$w; done
```

- **`wt-track3`** is an ancestor of `v88` — fully merged, clean, idle.
- **`wt-track2`** is at `b5b84ca9`, one commit behind `v88` (a docs-only commit). SA173's product
  checkpoint is **integrated**; the lane resumes from `v88` itself.
- **`wt-track1`** is clean at `f392641c`, **15 ahead / 14 behind `v88`** — the release's only unmerged
  product delta, carrying the accepted E0 tip and the convergence corrections at `8b20800d`. It must
  sync before validating; expect a conflict in this file and keep its structure.

The binding constraint is physical, not a ticket edge: one PostgreSQL 18 cluster on `localhost:5432`
holding the twelve shared `test_quickscale_*` databases, which W3 needs *empty*. W1's SA167d `make
test` and W3's SA135 E1 campaign must be scheduled serially around it. No ticket move relieves that;
only scheduling does. SA173's remaining coverage work is DB-free, but its frozen-candidate `make test`
must claim the cluster and run outside W3's exclusive window.

### Next action per lane

- **W2 — resume SA173 (#30) from `v88`; do not reimplement its merged product work.** Add the
  `__getattr__` unit test that raises `quickscale_modules_storage/__init__.py` from 45% to ≥80%
  per-file coverage, run `make test` to a returned green verdict, then run the complete unexcluded
  frozen-candidate campaign and cross-lane caller suites, reconcile the authoritative closeout
  documents, review the exact tip, and merge. SA167c (#21) stays blocked until that closes.
- **W3 — resume SA135 (#15) at phase E1, unexcluded, today.** Do not redo C or D, and do not attempt
  the E2E Docker failures — they are SA170's. Remaining scope is **the PostgreSQL-lifecycle evidence
  and the `validation_policy.md` precondition update only**. An executable plan is written into the
  ticket below; no plan-authoring step remains. Its own campaign can go green today; only the merge
  waits on SA173.
- **W1 — SA167d's phase E is accepted; the lane needs closeout, not re-implementation.** Sync
  `wt-track1` (14 behind), run one validation campaign on the synced frozen candidate, and perform one
  terminal attestation **supplied with the complete base-to-tip patch as a file** — the missing input,
  not any finding, is what ungraded the last attempt. Schedule `make test` outside W3's window.

### Track readiness — the three states

A lane is **truly green** only when all three are yes. *Can start* = the next action is executable
today. *Can finish* = the ticket can reach a checked box using only work on its own lane. *Can merge* =
merge-back is not order-gated behind another lane.

| Lane | Head | Can start | Can finish | Can merge | On the critical path |
|---|---|---|---|---|---|
| **W2** | SA173 (#30) | **yes** — resume from `v88`; no decision or authorization pending | **yes** — the storage coverage fix, closeout, and validation are all W2-local and DB-free | **yes** — nothing is ordered ahead of #30 | **yes** — band A, and it gates both other lanes |
| **W1** | SA167d (#18) | **yes** — sync, validate, attest; schedule `make test` outside W3's window | **no — hard dependency on SA173 (#30)**; its own work reaches green, but final acceptance needs a green `v88` | **no — gated on SA173 (#30)** | no |
| **W3** | SA135 (#15) | **yes** — take the exclusive slot first; the plan is written | **no — hard dependency on SA173 (#30)**; same gate | **no — gated on SA173 (#30)** | no |

**W2 is the one truly green lane, and it is on the critical path** — so it is the only place real
progress can be made right now. Every "no" above names **SA173 (#30)** and every one of them is a
**hard dependency**: only the upstream work clears it, no maintainer decision can. W1 and W3 can still
start and bank provisional evidence; they simply cannot close a ticket until #30 closes, at which point
the gate clears for all three lanes at once.

**No open maintainer decision blocks any of the three states.** D3 and the placeholder-declaration
policy are settled. Two items are flagged for maintainer awareness rather than as blockers: the
`make check` cost model correction above, and the four `sqlparse` CVE suppressions expiring
**2026-09-30**, inside the release window (see *Audit items deliberately not ticketed*).

### Handoff checklist — applies to all three lanes

Before any ticket work, measure each lane against current `v88`; when a worktree lags:

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

**The clause is implemented and merged.** *Each consumer owns its own reaction* is half of the
decision, not a footnote to it: the merged work writes `status`'s report-as-drift policy while
preserving `apply`'s fail-hard reaction. SA173 remains open because one per-file coverage gate is red,
not because D3 lacks an implementation. *Cost, stated plainly:* the critical path grew by one ticket,
accepted deliberately.

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

**Branch-state gate, not a queue edge: nothing else completes its merge before SA173 closes.**
SA173's product work is integrated, but its 45% storage per-file coverage against the required 80%
leaves the `make test` chain red, so every other lane's completed merge evidence stays unobtainable
until #30 is accepted. This is deliberately **not** recorded as a `deps:` edge on #15 and #18 — it is
not a content dependency between tickets, it is the state of the integration branch, and it clears for
all lanes at once the moment SA173 closes green. The merge-order table above is otherwise unchanged.

Positions #1, #2, #3, #4, #5, #6, #6b, #7, #8, #9, #10, #11, #12, #13, #14, #16, #17, #23, and #26 are **retired and not
reused**; their tickets are closed and archived in [CHANGELOG.md](../../CHANGELOG.md). Gaps carry no meaning. Position
#15 was shared with SA163 until that ticket closed on 2026-08-28; it now carries SA135 alone.

The per-lane heads are **#30 (W2 — all product work merged, storage coverage and closeout open),
#18 (W1, partial), and #15 (W3, partial)**. #21 is no longer a lane head — it now merges after #30.
Of the partials: #21 has a merged Phase-A slice at `f6f3bbce` with A unaccepted pending SA173's
completed acceptance and B-F outstanding; #18 is a phase-E-accepted candidate on `wt-track1` at `f392641c`
awaiting one validation campaign and one attestation; #15 has a merged partial with C/D accepted and
E outstanding after SA163's share of it closed.

Most "Merges after" edges are lane ordering — a queue position, clearable only by the upstream work
or by a maintainer reordering the lane. Three are **hard content dependencies** that no reorder
clears: **SA160 after SA161** (shared emission-parity rebaseline of `sa90_emission_manifests.json`;
the pair must not be split, and **SA174 appends the third rebaseline entry** after them, so the run
of three is ordered #19, #20, #31), **SA164's substance after SA167c** (its
`test_sa92_migration_squash_guardrail.py` work needs `django_apps:` retired), and **SA167c's
Phase-A acceptance after SA173** (two of its four caller tests are answered by the presence
contract; rerunning A before SA173 is accepted cannot provide completed merge evidence). Band-C positions
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
  Discovery collapsed *"module absent"* and *"directory present but no `module.yml`"* into one output,
  and downstream consumers reconstructed the discarded fact by **counting**. The policy chosen by
  decision D3 is written in
  [decisions.md → Module Presence States](decisions.md#module-presence-states); this ticket implements
  it. The investigation that produced D3, and the full 2026-08-28 regression diagnosis this ticket
  worked through, are archived in [CHANGELOG.md](../../CHANGELOG.md) and are not restated here.
  **State (2026-08-29): partial completion retained; coverage fixed, acceptance and closeout open.**
  The already-integrated product behavior remains unchanged. Track branch `wt-track2` carries retained
  implementation commit `1edb95381b78b64605bd71116456d67405dc6984`, which adds only
  `quickscale_modules/storage/tests/test_init.py`; check `v88` history to determine whether that exact
  object has been integrated. **Do not reimplement the three-state contract or the retained test.**

  **Completed in the retained delivery:**
  - Phase A reproduced the source-bound starting state: 39 storage tests passed, while
    `quickscale_modules_storage/__init__.py` remained at 45% because lines 28-35 were uncovered.
  - Phase B added exactly two tests over every runtime `__all__` export, package caching, helper
    identity, and the unknown-name `AttributeError` path. The focused pair passed; the storage suite
    then reported 41 passed, `__init__.py` at 100%, and package coverage at 97.67%, with no product or
    coverage-policy edit. Serial convergence independently approved that one-file delta and repeated
    the same green storage result.

  **Pending:**
  - Phase C is not accepted. Its first two checks were green (41 storage tests and 167 CLI caller
    tests); its third command exited 0 with **222 passed**, but the recorded oracle required **221**.
    The ordered stop rule therefore prevented the remaining CLI/core aggregate, scripts suite,
    manifest/parity checks, lint, typecheck, and `make check` from running.
  - Phase D's detached `make test` / `make quality` campaign and W1/W3 caller evidence were not
    reached. Phase E's changelog, implementation-contract, ticket-context, docs-index, roadmap-count,
    and consistency-test closeout was not reached. SA173 remains open and unmarked.

  **Blocking:**
  - ***corrected after checkpoint attestation — not independently graded*** The 222-versus-221
    collection drift must be explained before acceptance, and Phase C is closed to the current run.
    A new run must first obtain revised reviewed-plan authority and adjudicate the caller-count
    difference from collected node IDs; only then may it bind the oracle to 222 when the added test is
    intentional or correct an unintended collection difference and rerun Phase C from command one.
  - ***corrected after checkpoint attestation — not independently graded*** The retained product
    delta has no terminal grade. Its attestation was blocked before reading the patch because the
    review handoff omitted the required validation tier, consuming this run's sole product-attestation
    budget. No second product attestation is authorized in this run; a future run must explicitly
    establish a fresh attestation budget before supplying the complete patch, clean exact-tip binding,
    and validation tier to an independent reviewer.

  **Decisions needed:** ***corrected after checkpoint attestation — not independently graded*** A new
  run must authorize revised reviewed-plan authority and a fresh product-attestation budget. No
  product-design decision is currently open; ask the maintainer about the count only if collected-test
  evidence leaves two policy-valid oracle choices.

  **Remaining plan (serial; reuse the retained implementation and do not redo Phases A-B):**
  1. ***corrected after checkpoint attestation — not independently graded*** Start a new run, obtain
     revised reviewed-plan authority, and adjudicate the count from collected node IDs before
     authorizing any Phase C rerun. Then rerun all Phase C commands in the recorded order, stopping at
     the first unexpected result.
  2. Obtain W3's shared-slot grant and run Phase D once: detached `make test`, detached `make quality`,
     W1's focused caller suite, and W3's provisioning/BYPASSRLS/isolation/restricted caller family,
     leaving `quickscale_test_role` owning all twelve test databases.
  3. Only after every gate is green, perform Phase E's five-document closeout and same-change
     consistency test, then run serial convergence over the complete retained-plus-closeout delta.
  4. ***corrected after checkpoint attestation — not independently graded*** Only after the new run
     establishes a fresh product-attestation budget, materialize the complete patch and clean exact-tip
     binding, run one independent terminal attestation with the validation tier stated explicitly, and
     merge only that accepted exact tip.
  **Acceptance:**
  1. Discovery reports ABSENT / ACTIVE / INCOMPLETE distinctly and no code path silently drops a
     manifest-less directory. *(met)*
  2. `refresh_managed_adapters` loads the **subset** present and fails hard on INCOMPLETE, naming the
     directory and the missing manifest, both proved by separate tests — and an ACTIVE
     catalog-declared placeholder fails atomically with an actionable pre-import error rather than
     being silently excluded, while a declared-INCOMPLETE placeholder stays fail-closed. *(met)*
  3. The subset-validity rule and its diagnostic text exist **once**;
     `grep -rn "inventory count drift" --include=*.py` outside tests returns a single production site.
     *(met)*
  4. `authoritative_module_names` answers the *release inventory* question only; the `OVERRIDE`→bundled
     substitution is removed. *(met)*
  5. The CLI contributes no presence **classification** — the substring test at
     `module_wiring_manager.py:201` stays deleted — and each CLI consumer states its own reaction to a
     typed presence result: `status` reports a registered-but-missing or INCOMPLETE module as drift and
     exits 0; `apply` fails hard. The eleven tests in `test_status_command.py` pass **without being
     edited**, and the seven in `commands/test_module_config_extended.py` pass with **fixture-only**
     repair and no assertion or `apply` change. *(met)*
  6. `PLACEHOLDER_MODULE_NAMES` is retired in favour of a declaration mechanism, with `teams` still
     fail-closed. *(met)*
  7. `test_module_wiring_manager_manifest.py`'s two tests, their class name, and both docstrings agree
     with the contract. *(met — 43 passed)*
  8. Negative proof: temporarily empty one module's `module.yml`, observe the INCOMPLETE fail-hard for
     the intended reason, restore the exact bytes, prove green. *(met)*
  9. The standalone-shim contract holds: `module_discovery.py`, copied alone into a tree with no
     importable `quickscale_core`, still answers `--list-modules` for whatever modules that tree
     carries — no root-package import crash, and no twelve-module release count imposed on a hermetic
     tree — and a hermetic test asserts it, so `scripts/version_tool.sh` cannot break again unobserved.
     *(met)*
  10. **The required per-file coverage gate is green with no exclusion, waiver, or threshold change.**
      *(implemented and focused green — the full acceptance campaign remains pending)*
  **Verification (ordered; stop at the first unexpected red):**
  1. `poetry run pytest quickscale_modules/storage/tests -q -o addopts= --cov=quickscale_modules_storage --cov-report=term-missing` — expect `__init__.py` at ≥80% and no file regressed.
  2. `poetry run pytest quickscale_cli/tests/test_status_command.py quickscale_cli/tests/commands/test_module_config_extended.py -q -o addopts= --no-cov -p no:cacheprovider` — expect exit 0 with **167 passed** and no test file edited.
  3. `poetry run pytest quickscale_cli/tests/test_module_wiring_manager_manifest.py quickscale_core/tests/test_manifest_entry_point.py quickscale_cli/tests/test_module_lifecycle_cycle.py quickscale_core/tests/test_module_migration_topology.py -q -o addopts= --no-cov` — expect exit 0, **221 passed**.
  4. `poetry run pytest quickscale_cli/tests quickscale_core/tests -m "not e2e" -q -o addopts= --no-cov` — expect exit 0. This isolates the ticket's surface without SA170's four `e2e` failures; the unfiltered variant costs ~80 minutes and proves nothing extra here.
  5. `poetry run pytest scripts/ -q -o addopts= --no-cov -p no:cacheprovider` — expect exit 0 and **1319 passed** (measured green on `v88` 2026-08-29 in 92 s). `publish_module.py`, `check_sa117_scope.py`, and `version_tool.sh` are release-inventory consumers of the changed contract.
  6. `make check-manifest-sync` and `make check-gate-parity` — expect exit 0.
  7. `make lint`, `make typecheck`, `make check` — expect exit 0 (`make check` measured 184 s green on `v88`). Then `make test` (expect exit 0; it exits 2 in 82 s today) and `make quality` **detached**; `make quality` no worse than found.
  **Rollback:** after the retained delivery is integrated, `git reset --hard
  1edb95381b78b64605bd71116456d67405dc6984` in `wt-track2` discards a later completion attempt
  without discarding the accepted coverage test.
  **Cross-lane obligation.** `quickscale_core/contracts/` and `quickscale_core/manifest/` are read by
  every lane, and `203fcd61` is the recorded precedent for a behavioural change here turning another
  lane red with no shared file. Before merging, announce in the merge queue and re-run W1's and W3's
  focused caller suites against the candidate.
  **Shared conflict surface:** `quickscale_modules/storage/`, `quickscale_core/src/quickscale_core/contracts/module_discovery.py`, `quickscale_core/src/quickscale_core/manifest/entry_point.py`, `quickscale_cli/src/quickscale_cli/commands/status_command.py`, `quickscale_cli/src/quickscale_cli/commands/apply_command.py`, `quickscale_cli/src/quickscale_cli/utils/module_wiring_manager.py`, `docs/technical/decisions.md`.

- [ ] **SA167c — Retire `django_apps:` and gate the app declaration.** `Band B · Tier 2 · W2 · merge #21 · deps: SA173 · closes the SA167 family`
  `django_apps:` was inert declarative surface: eleven manifests carried it, the loader parsed it,
  no production path read it, and one SA92 helper used it before falling back to a guessed path.
  **Acceptance:** `django_apps:` is either derived from the `apps` wiring projection or removed from all manifests, `ModuleManifest`, and the loader, with no key parsed-but-unread remaining; a conformance gate fails when a module ships models or a migration without declaring at least one Django app, registered in `scripts/gate_registry.json` and passing `scripts/check_gate_parity.py`; the gate is proved by deleting a module's app declaration and observing red, reverted before merge; `test_sa92_migration_squash_guardrail.py` no longer depends on the retired key.
  **State (2026-08-29): Phase-A product slice merged; Phase A not yet accepted; B-F not reached.**
  Product commit `f6f3bbce` is on `v88`. The merged bytes removed `django_apps:` from
  `ModuleManifest`, the loader, the obsolete loader test, all eleven source declarations and their
  core snapshots, and removed the SA92 helper's retired-key dependency, while preserving all twelve
  `apps` wiring projections and public adapter outputs. Terminal review found no product-slice defect.
  On the last acceptance attempt four of the five commands were green (loader 112 passed; restricted-role
  orgs 884 passed / 11 skipped; `make check-manifest-sync` and `make check-gate-parity` exit 0) and the
  four-caller command exited 1 on two tests in `TestRegenerateManagedWiringSkipManifestNotFound`
  (`test_module_wiring_manager_manifest.py:767,796`). Under the stop-at-first-unexpected-red rule the
  source-bound probe and the `git diff --exit-code` oracle were not run, so this green prefix is **not**
  Phase-A acceptance.
  **Not this ticket's defect — and already fixed.** Decision D3 established those two failures as a
  module-presence question, not a `django_apps:` question, and **SA173 (#30)** owned them. They are
  green on `v88` today (`test_module_wiring_manager_manifest.py` 43 passed). SA167c must not edit them
  and must not touch `quickscale_core/contracts/` or `quickscale_core/manifest/`.
  **Blocking: SA173 must be accepted and closed.** Its product work is merged and the caller tests are
  green, but its storage per-file coverage gate is red, so #30 is open and #21 is still gated. Nothing
  else blocks Phase A. **Note for step 5 below:** `commands/test_module_config_extended.py` is no longer
  an oracle for this ticket; its seven former failures are fixed on `v88`.
  **Decisions needed:** none. D3 is settled; see
  [Settled decision D3](#settled-decision-d3--module-presence-is-a-three-state-fact-2026-08-28).
  **Remaining plan (serial; do not redo the merged retirement bytes):**
  0. **Wait for SA173 to be accepted.** No SA167c work is required for the caller mismatch, and the
     contract and all its consumer/fixture/shim product work are already on `v88`. When #30
     closes green, sync that completed state into `wt-track2` before rerunning A.
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
  **State (verified 2026-08-29 against the branch): phases A-E accepted; closeout is all that
  remains.** `wt-track1` is **clean at `f392641c`, 15 ahead / 14 behind `v88`** — the release's only
  unmerged product delta. Phase E is accepted at E0 tip `bd2c291b`, retained inside `8b20800d`; E0
  made no tracked edits and recorded **282 focused tests passed**, with `make lint`, `make typecheck`,
  `make test`, `make check`, and `make quality` all at exit 0. Independent convergence then ran and
  **corrected real defects** — ineffective auth-migration flush guidance, a non-operational
  fresh-database recovery path, and three stale quality-baseline identities — as `8b20800d`. The
  measured product delta `c50de1c1..8b20800d` is **30 files, 1,012 insertions, 2,228 deletions**.
  **Why the last attempt did not close, precisely.** Terminal attestation was attempted once and
  **returned no grade**: its read-only surface could resolve the exact tip but could not obtain the
  complete `c50de1c1..8b20800d` patch or independently exclude uncommitted-byte drift. That is a
  **review-input failure, not an attestation finding** — nothing was found wrong with the delta.
  Separately, V0 stopped when `make check` hit a 120-second foreground cutoff. Both causes are removed:
  the patch is producible in one command, and `make check` is now measured at ~184-212 s green.
  **Closeout shape: validate, then attest.** The recorded five-stage V0/C2/V1/convergence/attestation
  pipeline is **not** required. Convergence has already run and corrected this delta, every gate has
  been green on it once, and the single unmet step failed for a reason that no longer applies.
  Re-running the full staging would re-prove passed work.
  **Remaining plan (serial; do not re-implement anything):**
  1. **Sync.** Merge current `v88` into `wt-track1` and resolve there, preserving the retained
     candidate and the closeout checkpoint. Expect a conflict in this file — keep its structure.
  2. **Validate on one frozen candidate,** unexcluded — the known-red protocol is retired and no
     `PYTEST_ADDOPTS` is authorized. Ordered, stopping at the first unexpected red:
     - `poetry run pytest quickscale_cli/tests/commands/test_module_config.py quickscale_cli/tests/commands/test_module_config_extended.py quickscale_cli/tests/commands/test_module_commands.py quickscale_cli/tests/test_module_wiring_manager_manifest.py quickscale_cli/tests/test_module_manifest_contract.py -q -o addopts= --no-cov` — expect the recorded **816** focused total. The seven former SA173 fixture failures in `commands/test_module_config_extended.py` are fixed on `v88`; they are not W1's work and may not be reintroduced or deselected.
     - `poetry run pytest quickscale_core/tests/test_v88_ticket_context_consistency.py -q -o addopts= --no-cov` — expect **21 passed**.
     - `make lint`, `make typecheck` — exit 0.
     - `make check` — exit 0 (measured ~184 s green on `v88`, 2026-08-29; it fits in one foreground
       call). Then `make test` and `make quality` **detached, polling for an exit-code file** — a
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
  5. **Merge only the attested exact tip** — and only after SA173 has been accepted and step 2 has
     been re-run on a candidate synced to the completed SA173 `v88`, with all 816 green. That re-run is the
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
  **Prior blocker — cleared.** The last attempt never ran a command: its reviewed plan required a
  disinterested review inside G-sync/G-validate and then resumed authored documentation mutation in
  G-closeout/G-final, which the strictly forward pipeline cannot do. **A compliant plan is written
  below and no plan-authoring step remains before dispatch** — every implementation and authored
  closeout mutation happens before serial convergence, and exactly one terminal attestation ends the
  ticket.
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
     protocol is retired and no `PYTEST_ADDOPTS` is authorized. SA173's product work is merged, but
     its storage per-file coverage still leaves the required branch gate red (see *Band A*); W3
     neither owns nor may touch it, and W3's own stages are unaffected by it. **Run `make test` and
     `make quality` detached, polling for an exit-code file**; `make check` measures ~184 s green and
     may run in the foreground. A truncated run is not evidence. The serial and CI E2E campaigns are
     **not** part of this stage any more.
  4. **G-closeout / G-final.** Only after G-validate is green: archive and remove SA135 from this
     open-work-only roadmap, then rerun the final frozen-tip campaign.
  5. **Serial convergence** over the complete product-and-closeout delta, then **exactly one terminal
     attestation**. Supply it with the complete base-to-tip patch as a file and a clean-byte binding
     (`git status --porcelain` empty at the exact tip) — SA167d's attestation returned no grade for
     want of exactly that input, and the same mistake must not be paid twice.
  6. **Merge only that attested exact tip** — and only after SA173 has been accepted and G-validate
     has been re-run on a candidate synced to the completed SA173 `v88`, fully green. Report final changed lines and
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
