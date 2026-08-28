# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Changelog](../../CHANGELOG.md) | [Validation Policy](validation_policy.md) | [v88 Ticket Context](v88_ticket_context.md) | [Release Summary Template](release_summary_template.md)

## Purpose

This is the current task planner. It holds **open work only**.
Completed tickets, closed findings, review evidence, and release records are archived in
[CHANGELOG.md](../../CHANGELOG.md) and removed from here rather than marked done. Every count,
dependency graph, and queue position below refers to open work; no checked entry is permitted.

### Execution rules

- Work develops in three worktrees (**W1** module-wiring migration + watch items, **W2** gate layer + declared wiring, **W3** service lifecycle) and merges into the clean `v88` integration branch. Never implement directly on the integration branch. There are three worktrees and no more; a ticket that does not fit an existing lane is sequenced inside one, not given a new lane.
- One reviewed child runs at a time per worktree. Umbrellas are acceptance-only; their children own implementation.
- Start from a clean worktree after merging the integration branch. Before merge-back, sync the integration branch into the worktree, resolve there, run the ticket's verification, review the exact tip, then merge that tip.
- Every handoff declares its file allowlist, commands, expected exits/artifacts, rollback, and focused validation. Scope findings are ticketed rather than fixed in place.
- Leave `make quality` no worse than found. Do not raise a complexity ceiling or reintroduce file-line ceilings. The default monotonicity path resolves durable `main` and `make quality` emits fresh reports. The current baseline has zero warning regressions, zero critical regressions, and monotonicity passes.
- Shared closeout conflict surfaces are `CHANGELOG.md`, `docs/technical/roadmap.md`, `docs/technical/v88_ticket_context.md` when a ticket's concepts change, and `docs/technical/decisions.md` when policy changes. `docs/others/arch-audit.md` and `docs/others/tech-audit.md` join that surface only when a ticket changes or closes a live audit finding. The sync-before-merge-back procedure above must preserve every concurrent entry, resolve these files in the worktree, rerun the ticket's checks, and leave no unmerged files before the exact tip is reviewed and merged.
- PostgreSQL/Docker work is serialized across worktrees. **W3 holds the exclusive PostgreSQL/Docker slot** and takes scheduling priority whenever one of its legs is active, even though W2 — not W3 — is the longest dependency chain this release.
- **Local database-lane operating constraint:** `make test-integration` and `make test-bypassrls`
  use the same twelve databases and differ only by role. The role for the lane about to run must
  own all twelve databases first, then ownership must be restored to `quickscale_test_role` after
  the lane. Hosted CI uses separate ephemeral servers; this constraint applies to the shared local
  cluster only.
- **W1's wiring leg (SA167d) may not touch `scripts/gate_registry.json` or any `module.yml`.** Those are W2-owned surfaces — SA167c is on W2 for exactly that reason. The wiring leg has no open cross-worktree edge: the `entry_point.py` handoff is settled tree state.
- A ticket whose deliverable is Git ref state cannot be delegated to a file-editing worker. Route it to a maintainer session with ref authority and push credentials.

---

## v88 release plan

### Priority model (revised 2026-08-21)

Audit-derived prerequisites and implementation tickets share one ranked queue rather than
forming separate follow-on work:

> **Ordering rule.** A ticket that makes a gate *tell the truth* outranks a ticket that
> makes the product *better*, because every other ticket's acceptance criteria are
> discharged by those gates. Below that, order by longest dependency chain, then by
> whether the ticket holds an exclusive resource, then by tier.

Applying it produces three ranked bands:

| Band | Rule | Tickets |
|---|---|---|
| **A — Restore enforcement** | The gate layer reports green while not running, or runs red on HEAD. Nothing downstream can be trusted until this is fixed. | — (shared baseline green; prior repair archived) |
| **B — Release work on the critical paths** | The two longest serialized chains, one of which holds the exclusive service slot. | SA167c (critical path); SA135 (+ SA163); SA170; SA167d |
| **C — Bounded independent fixes** | No dependants, small blast radius. Absorbed as slack filler by whichever worktree finishes a band-B leg early. | SA160, SA161, SA164, SA165, SA166 |

**Standing consequences of that rule:**

- **Band A is clear.** Shared repository gates are green; the completion evidence is archived in
  [CHANGELOG.md](../../CHANGELOG.md). No open ticket may waive them.
  *Found red and repaired inside this pass:* `quickscale_core/tests/test_v88_ticket_context_consistency.py`
  failed on `v88` HEAD because `7db1b633` gave SA167c a state header byte-identical to SA135's, so
  the test's non-greedy W3 anchor bound to the earlier SA167c block. SA167c's header now reads
  *Phase-A product slice merged*, the anchors are unambiguous again, and the gate passes
  (20 passed). This is the recurring hazard of the shared closeout surface: **a roadmap edit that
  changes a W1/W2/W3 state block must re-run this test in the same change, and two blocks must
  never share a state header.**
- **The critical path is on the gate track, not the service track.** W2's `SA167c` is one
  serialized merge leg with no prerequisite outside W2. W3 keeps the exclusive PostgreSQL/Docker
  slot and therefore keeps scheduling priority *while a leg is active*, but it is no longer the
  longest chain and no longer sets the release date.
- **SA164 sits on W2, not W1.** It edits `scripts/gate_registry.json` and
  `scripts/check_gate_parity.py` — both W2-only surfaces — and
  `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`, which SA167c (W2)
  rewrites first. As band-C tail (#25) it adds nothing to the critical path.
- **SA167c is pinned to W2** because it registers a gate in `scripts/gate_registry.json` and
  rewrites every `module.yml` — both W2-only surfaces. **SA167d stays on W1** because it touches
  `module_config.py`, which no other v88 ticket touches; it carries no cross-worktree gate and
  does not extend the one-leg critical path.
- **SA163 does not get its own slot.** It executes inside SA135, whose allowlist already covers the
  same provisioning files.
- **The implementation tickets and the audit tickets are one queue.** The merge-order table is the
  single authority; the two backlog sections below are presentation, not scope.


### Dependency graph and critical path

```text
v88 — three worktrees, nine open merge positions carrying ten open ticket entries, one merge queue

BAND A — clear; shared repository gates are green

W2 (gates & declared wiring)   ★ CRITICAL PATH — 3 open legs, 1 on the path — PARTIAL MERGED
  SA167c ─► SA166 ─► SA164
  retire    testimony  watch
  django_   trail      items
  apps+gate
  (retirement bytes merged;
   A acceptance retried:
   2 caller tests red; B-F open)
    #21       #24       #25

W1 (module-wiring migration + watch items)   2 open legs, no cross-worktree dependency
                                             (SA165 shares one file with W3's SA163 — merge-ordered)
  SA167d ─► SA165
  CLI       watch
  drain     items
  (A-D ok,  (open,
   E open)   shares a file
             with SA163)
     #18       #22

W3 (service lifecycle — exclusive PostgreSQL/Docker slot)   4 open positions: 1 heavy PARTIAL MERGED
                                                           + 1 harness repair + 2 band-C
  SA135 + SA163 ──► SA170 ──► [SA161, SA160]
  owned PG lifecycle  E2E docker   emission-adjacent
  + derived CI env    resource     fillers
                      contract
        #15             #27          #19, #20
```

**Longest open release chain — the critical path:** W2's
`SA167c`. One open band-B
leg; SA166 (#24) and SA164 (#25) are band-C tails behind
the chain, not on it. W2's back half is the release's implementation work, so W2 sets the
date. SA167d costs nothing on the critical path: W1 runs it against W2's second half.
**Load check:** W1 carries two open legs (SA167d's outstanding phase E, then SA165); W3 carries
four positions (SA135+SA163, then SA170, then SA161 and SA160), against the three-leg W2 spine.
W3's band-C tails do not gate release and SA170 is off the critical path, so W2 remains the binding
lane — SA170 lengthens W3's queue without lengthening the release.


**Second chain:** W3, `SA135` carrying `SA163`, one service-backed open leg — **no longer stalled**
  after this pass root-caused the E1 blocker out of it — followed by `SA170`'s harness repair and the
  emission-adjacent fillers, serialized on the exclusive slot while a leg is active. At four
  positions W3 is now the longest *queue*, but SA167c on W2 remains the longest *chain* and still
  sets the date.

**Active cross-worktree dependency edges — none.** Every remaining *dependency* is intra-lane.
One cross-worktree **shared file** remains but no live contention does: SA163's merged partial and
SA165 (#22, W1) both touch `scripts/test_isolation_conformance.sh`. Merge order #15 before #22 makes
the handoff one-directional, so SA165 starts from the merged SA163 bytes rather than waiting on it.
The manifest-reading `entry_point.py`, the
fail-hard `QUICKSCALE_LOCAL_WHEELHOUSE` version-spec seam, and the regenerated migration baseline
are all merged tree state that open tickets build on, not pending dependencies.

**Merge-back status (measured 2026-08-27, twenty-second pass, `v88` at `713bd4a7`): two of three
tracks are fully merged back; only W1 is not.**

| Worktree | Tip | Ahead / behind `v88` | Merged back? | Tree |
|---|---|---|---|---|
| `wt-track2` (W2) | `80ca33b4` | 0 / 1 | **yes** — ancestor of `v88` | clean, idle |
| `wt-track3` (W3) | `0aabb4a0` | 0 / 4 | **yes** — ancestor of `v88` | clean, idle |
| `wt-track1` (W1) | `467714cb` | **9 / 7** | **no** | clean |

W2's SA167c Phase-A slice (`f6f3bbce`) and W3's SA135+SA163 partial (through `0661f55f` and
`f070f39b`, the latter carrying the `203fcd61` lifecycle/module-E2E remediation) are both on the
integration branch, and both worktrees are now clean and idle. **`wt-track1` holds the release's
only unmerged product delta:** SA167d's A-D-accepted work at product tip `1743871f`, plus one
docs-only checkpoint `467714cb`. It is also **seven commits behind**, so its sync-before-merge-back
will have to resolve `docs/technical/roadmap.md` against this pass. No suite is running and
`pg18-af10` holds all twelve `test_quickscale_*` databases.
Each lane still syncs current `v88` before its own exact-candidate validation.

**Rebalance result (twenty-second pass): no track moves; one ticket opened.**
Every open ticket already carries a track, and the binding constraint is physical — one PostgreSQL 18
cluster on `localhost:5432` holding the twelve shared test databases, which W3 needs *empty*. No
ticket move relieves that; only scheduling does. What changed this pass is that **W3's stall was
root-caused out of SA135 into the new SA170 (#27)**, so W3 has executable band-B work at its head
again and needs no reorder. Moves tested and rejected:

- **SA161 (#19) + SA160 (#20) off W3** — rejected. SA161's acceptance needs the exclusive
  PostgreSQL/Docker slot, which is W3-owned by standing rule, so any other lane leaves it blocked
  on W3 anyway. Onto W2 it would additionally put band-C filler on the lane that sets the release
  date. Revisit only if the slot rule changes.
- **SA166 (#24) or SA164 (#25) off W2** — rejected on the standing invariant that
  `scripts/gate_registry.json` never crosses worktrees. SA164 additionally has a hard content
  dependency on SA167c.
- **SA160 ahead of SA161 inside W3** — rejected: they share the emission-parity rebaseline
  ordering on `sa90_emission_manifests.json` and must not be split.
- **SA161 (#19) + SA160 (#20) *ahead of* SA135 (#15) inside W3** — **raised, then withdrawn within
  this pass.** It was proposed to stop W3 idling while SA135 was stalled; root-causing that stall
  out of SA135 removed the idle window, so the standing rule that band-C filler must not displace a
  band-B leg applies normally again.
- **SA170 (#27) onto W1 or W2** — rejected. It edits `quickscale_cli/tests/test_react_theme_e2e.py`,
  `test_e2e_development_workflow.py`, `docker_utils.py`, and `scripts/test_e2e.sh`, and its
  acceptance runs real Docker builds — the exclusive slot is W3-owned by standing rule. Placing it
  on W2 would also put non-critical-path work on the lane that sets the release date.
- **SA165 (#22) off W1** — rejected. SA163's edit to
  `scripts/test_isolation_conformance.sh` is now merged into `v88`, so it is settled input rather
  than an active cross-worktree hazard. Moving SA165 still buys nothing on the critical path and
  would move W1-owned filler without shortening its queue. Its W1 *ordering* remains the separate
  open decision below.

**Nothing can shorten the release.** SA170 lengthens W3's queue but not the release: W3 was already
off the critical path. The critical path is `SA167c`, pinned to W2 by
`quickscale_modules/*/module.yml` and `scripts/gate_registry.json` ownership, with no prerequisite
outside W2. SA166 (#24) and SA164 (#25) are band-C tails *behind* the spine. W2 is idle, so the
only lever available is **continuing SA167c from its merged retirement slice**, not moving anything.

**Standing serialization constraint between lanes.** W3's database-backed legs and any W1/W2 run of
`make check` / `make test-integration` contend for the *ownership* of the twelve local test
databases, not just for the Docker slot. This is a local-cluster artifact that hosted CI does not
have, and retiring it is **SA135**/**SA163** work.

Shared closeout surfaces (`CHANGELOG.md`, `docs/technical/roadmap.md`,
`docs/technical/v88_ticket_context.md`, and both audit docs) remain covered by the standing
sync-before-merge-back procedure.


### Track readiness (re-measured 2026-08-27, twenty-second pass)

Each track reports three independent states. A track is **truly green** only when all three are
yes.

**Measured worktree state.** See the merge-back table above: `wt-track2` (`80ca33b4`) and
`wt-track3` (`0aabb4a0`) are ancestors of `v88` — both merged, clean, and idle. `wt-track1` is
**nine commits ahead and seven behind**, clean, holding SA167d's A-D-accepted product tip `1743871f`
under one docs-only checkpoint. `pg18-af10` is up with the twelve databases intact and no suite is
in flight. Evidence produced after terminal attestation in the W1 and W3 passes was not
independently graded; the affected claims are marked once here rather than repeated per line.

| Track | Next ticket | Can start | Can finish on its own track | Can merge in order | Verdict |
|---|---|---|---|---|---|
| **W1** | SA167d (#18) — A-D accepted, **E outstanding** | **yes** — re-running phase E is executable today; no decision, no upstream ticket. Contends with W3 for the shared cluster | **yes** — phase E, the ledger reconciliation, and the merge-back are all W1-owned | **yes** — #18 is the W1 queue head with no upstream ticket | **truly green — off the critical path** |
| **W2** | SA167c (#21) — Phase-A slice merged, **A unaccepted; B-F outstanding** | **no** — corrected acceptance exposed a pre-existing caller-test/runtime contract mismatch: two tests expect embedded inventory drift to fail while the bundled twelve-module fallback succeeds. D3 below must settle which contract is authoritative | **yes, after D3** — the correction, remaining gate, proof, closeout, and frozen-candidate work are W2-owned | **yes** — #21 remains the W2 queue head | **blocked on one contract decision — on the critical path** |
| **W3** | SA135 + SA163 (#15) — C/D accepted, E outstanding | **yes** — E1 is re-scoped to the PostgreSQL-lifecycle evidence SA135 owns, which is deterministic today. The two E2E Docker failures that stalled it are re-ticketed as SA170 (#27); no decision or upstream ticket blocks #15 | **yes** — the remaining E/F/G work is W3-owned; the exclusive slot remains authorized when needed | **yes** — #15 is the W3 queue head | **truly green — off the critical path; worktree merged, clean, and idle** |
| **W3 (queue tail)** | SA170 (#27) — newly opened | **yes** — the root cause is identified and its proofs are pure unit tests plus one labelled-resource assertion; none needs the cluster | **yes** — every file it touches is W3-owned CLI test/util and harness code | **no** — merges after SA135 (#15) | **blocked on merge order only** |

**W1 and W3 remain truly green at their queue heads; W2 is blocked on D3.** W3's earlier block is
cleared: SA135's phase E1 was stalled on an acceptance criterion that could not be satisfied, not on
missing work. **SA167c (#21)** remains the critical path and the one ticket whose progress moves the
release date, but its corrected Phase-A acceptance exposed a caller-test/runtime contract mismatch
that the verification-only phase was not authorized to change. SA167d and
SA135+SA163 are real band-B work but are **filler with respect to the release date**: finishing
either does not shorten the chain. W1 is additionally the only track with an unmerged product
delta, so its merge-back is the one outstanding integration risk. SA170 (#27) is band-B work behind
SA135 on W3 and is off the critical path.

**The binding constraint is the shared PostgreSQL cluster, not any ticket edge.** No W3 suite is
currently holding it. W1's phase-E `make test`, W2's SA167c campaign, and the next W3 E2E rerun
must still be scheduled serially around that physical resource.

**Blocked open tickets, edge kind, and what clears each.** Every edge is classified so no blocker
is ambiguous between "a maintainer decision clears it" and "only the upstream work clears it".

| Ticket | Blocking ticket | Edge kind | What clears it |
|---|---|---|---|
| SA167c (#21) | D3 below | **queue head; Phase-A slice merged; acceptance retry red** | Settle whether the bundled twelve-module fallback or the two failing embedded-inventory-drift expectations own the contract. Then correct the losing surface under fresh plan authority, rerun A from the beginning, and continue B-F only after A is accepted. |
| SA167d (#18) | — | **queue head** | Nothing blocks it. Startable today; competes with W3 for the cluster. |
| SA135 + SA163 (#15) | — | **queue head; partial merged; unblocked this pass** | Nothing blocks it. The former decision block is retired: the two E2E Docker failures were root-caused out of this ticket into SA170 (#27), and E1 is re-scoped to the deterministic PostgreSQL-lifecycle evidence SA135 owns. |
| SA170 (#27) | SA135 (#15) | **lane-ordering** — W3 queue position; SA170 also needs the Docker slot SA135 holds | **Upstream work only.** No decision clears it. It is deliberately behind SA135 so it starts from the settled provisioning bytes. |
| SA161 (#19) | SA135 (#15) | **lane-ordering** — W3 queue position; SA161 also needs the PostgreSQL/Docker slot SA135 holds | **Upstream work only, again.** D2 is withdrawn: it existed to fill W3 idle time while SA135 was stalled, and SA135 is no longer stalled. |
| SA160 (#20) | SA161 (#19) | **hard content** — emission-parity ordering on the shared `sa90_emission_manifests.json` rebaseline | Only SA161. No decision clears it; the pair must not be split. |
| SA166 (#24) | SA167c (#21) | **lane-ordering** — W2 queue position behind the spine; SA166 also owns `scripts/gate_registry.json` | Upstream work, or a maintainer reordering W2. Not recommended: it would put band-C filler ahead of the critical path. |
| SA164 (#25) | SA166 (#24) | **lane-ordering** for the queue position, **hard content** for its substance — its `test_sa92_migration_squash_guardrail.py` work depends on SA167c having retired `django_apps:` | The content half only SA167c clears. The SA166 position is reorderable by decision, but not recommended. |
| SA165 (#22) | SA167d (#18) | **lane-ordering only** — W1 queue position; SA165 shares no file with SA167d, and its `scripts/test_isolation_conformance.sh` edit is contended with SA163 (#15), not with #18 | **Upstream work only.** The reorder decision was put to the maintainer on 2026-08-27 and answered *keep the ordering*; it is now a standing rule below, so no decision remains that clears this. |

**Dispatch prerequisites, measured 2026-08-27 after this pass.** All three worktrees are clean and
no suite is running; `pg18-af10` is up with all twelve `test_quickscale_*` databases owned by
`quickscale_test_role`. **Every worktree is behind `v88` and must sync before its ticket starts.**
A trial merge of current `v88` into each shows: **W2 (3 behind) and W3 (6 behind) merge cleanly**;
**W1 (9 ahead / 9 behind) conflicts in `docs/technical/roadmap.md`** — expected, because `467714cb`
and this pass both rewrote its state blocks. Resolve in the worktree by keeping this pass's
structure and re-running `test_v88_ticket_context_consistency.py` in the same change, per the
standing rule.

**Recommended concurrency right now:**

- **W2 — settle D3, then resume SA167c (#21).** Do not redo the merged manifest-retirement bytes.
  Correct the losing caller-test or runtime surface under fresh plan authority, rerun A's full
  ordered acceptance chain, and implement B-F only after A is accepted. This remains the only
  action that shortens the release.
- **W3 — resume SA135 + SA163 (#15) at the re-scoped phase E1.** Do not redo C or D, and do not
  attempt the two E2E Docker failures here — they are SA170's. Accept E1 on the provisioning
  evidence this ticket owns, then run E2's unchanged-tree serial E2E and `ci-e2e`.
- **W1 — re-run and accept SA167d's phase E (#18)**, then do the ledger reconciliation and the
  merge-back. This is the release's only unmerged delta and it is ageing seven commits behind
  `v88`; schedule its `make test` outside W3's window.


#### Open decisions

**One maintainer decision is open in the v88 plan: D3.** The earlier SA135 phase-E1 evidence policy,
carried as **D1**, remains closed on engineering grounds, and **D2 remains withdrawn** because the
idle window it was written to fill no longer exists. D1 and D2 stay recorded until SA170 merges.

**D3 — open: which embedded-inventory contract owns the two red SA167c caller tests?** The corrected
Phase-A chain's loader suite exited 0 with 112 passed; the restricted-role orgs suite exited 0 with
884 passed, 11 skipped, and 2 warnings; manifest sync exited 0; and gate parity exited 0. Its
four-caller command then exited 1 with 256 passed and 2 failed in
`TestRegenerateManagedWiringSkipManifestNotFound`, at
`quickscale_cli/tests/test_module_wiring_manager_manifest.py:767,796`: both tests expect an embedded
registered module with no manifest to return `success is False` with `inventory count drift`, while
the current `authoritative_module_names` / `regenerate_managed_wiring` path accepts the bundled
twelve-module fallback and returns success. The verification-only phase made no tracked edit and,
under the required stop-at-first-unexpected-red rule, did not run either the literal twelve-module
source-bound projection probe or the final `git diff --exit-code` unchanged-tree oracle.

> **Option 1 — update the two stale expectations to the current bundled-inventory contract
> (recommended).** This preserves the implemented fail-hard twelve-module fallback used by current
> discovery and limits the pre-existing repair to caller tests, but a fresh plan must first confirm
> that no authoritative policy requires embedded inventory drift to fail in this scenario.
>
> **Option 2 — restore runtime failure on embedded inventory drift.** This preserves the two test
> expectations but changes live fallback behavior and therefore requires caller-parity review across
> every `regenerate_managed_wiring` consumer.

Until D3 is settled, Phase A is unaccepted and phases B-F remain unreached. The exact failure
signature is the two assertions at
`quickscale_cli/tests/test_module_wiring_manager_manifest.py:767,796`; no product or test byte was
changed in the failed phase.

**D1 — closed: the criterion was unsatisfiable, and the cause was findable by reading the harness.**
The phase demanded deterministic red-before/green-after evidence for a Docker `No such container`
startup race and a 300-second React build timeout. Neither symptom could be scheduled on demand, so
the two alternatives previously offered were *accept green re-runs and never learn the cause*
(Option 1) or *stress the boundaries until something breaks* (Option 2). Both were the wrong shape:
Option 1 leaves live defects in the tree, and Option 2 hunts a collision whose cause is already
legible in about forty lines of source. Root-causing the harness this pass produced a third answer,
which is what the plan now follows:

> **Option 3 — fix the structure, and prove the fix where determinism actually exists.**
> Both symptoms come from one shape: `quickscale_cli/tests/test_react_theme_e2e.py:657` opts out of
> the per-scope Docker resource contract that every other E2E resource obeys (fixed
> `quickscale-react-test` tag, no `com.quickscale.*` labels, no scope prefix), so concurrent runs
> collide on the tag and the harness's label-driven cleanup cannot see the image; and
> `docker_utils.py:328-348` filters containers with `docker ps -a --filter name=<name>`, a
> **substring** regex over dead containers, so `quickscale_cli/tests/test_e2e_development_workflow.py:157-168`
> reads a crashed container as "not up yet", waits out its full 40 s, and reports a generic timeout
> that names no cause. **That last one explains the whole stall:** when this harness fails it cannot
> say why, so re-running it was never going to yield the evidence the phase asked for.
> The repair is ticketed as **SA170 (#27)** with proofs that *are* deterministic — a unit test over
> the readiness predicate and the `docker ps` argv, a labelled-resource assertion that
> `cleanup_scoped_resources` reclaims the build image, and a two-scope collision test. None requires
> reproducing a flake. Nothing is waived: the obligation moved to a ticket that can discharge it.

Effect on the three states: W3's **can start** moves from *no* to *yes*, because SA135's E1 is now
scoped to PostgreSQL-lifecycle evidence it can produce today. **Can finish** and **can merge** were
already *yes*.

**D2 — withdrawn.** It proposed running SA161/SA160 ahead of SA135 to stop W3 idling while D1 was
unanswered. With D1 closed, W3 has band-B work at its head again, and the standing rule that band-C
filler must not displace a band-B leg applies normally. Revisit only if SA135 stalls again.

#### Standing rules carried from closed decisions

- **W3 holds the exclusive PostgreSQL/Docker slot.** W3 may stop the container `pg18-af10` for a
  strict-acceptance window and **must restart it afterwards**; the container must not be removed
  and its volume must not be pruned, and the twelve `test_quickscale_*` databases plus
  `quickscale_test_role` ownership must be intact when W1 and W2 next run. Recovery is
  `docker start pg18-af10`. The window was authorized on 2026-08-26 and has been exercised once;
  `pg18-af10` is currently up. The full rationale and rejected alternatives are archived in
  [CHANGELOG.md](../../CHANGELOG.md).
- **Neither `teams` nor a third generated-project updater is in v88.** Arch Findings 2, 4, and 7
  stay behind their growth triggers and are closed by no v88 ticket. A v88 ticket may not widen
  into them; a fired trigger is a scope finding and gets its own ticket.
- **Roadmap documentation ownership is Option A** — the roadmap holds open work only, and
  completed work is archived rather than marked done.
- **Local database-lane ownership flip** — whichever of `make test-integration` and
  `make test-bypassrls` is about to run must own the twelve test databases first.
- **SA165 (#22) stays behind SA167d (#18) on W1.** Decided 2026-08-27. W1 runs one reviewed
  child at a time, so band-C filler does not preempt an open band-B acceptance even when the two
  share no file. SA165's **can start** stays *no* until SA167d is accepted and merged; its **can
  finish** and **can merge** were never affected, and the critical path is untouched either way.
  Revisit only if SA167d is abandoned rather than merged.
- **SA123's coupled-test authority is closed;** the one surviving obligation is stated inside
  SA135+SA163 (#15).


### Merge order

One queue. Within a worktree, one reviewed child at a time; a ticket syncs the integration
branch into its worktree, resolves there, reruns its own verification, then merges its
exact reviewed tip.

| # | Ticket | Band | Tier | Worktree | Merges after | Service slot |
|---|---|---|---|---|---|---|
| 15 | **SA135** + **SA163** | B | 2 | W3 | — | **yes** — PostgreSQL + Docker |
| 18 | **SA167d** | B | 3 | W1 | — | no |
| 19 | **SA161** | C | 3 | W3 | SA135 | no |
| 20 | **SA160** | C | 2 | W3 | SA161 | no |
| 21 | **SA167c** | B | 2 | W2 | — | no |
| 22 | **SA165** | C | 3 | W1 | SA167d | no |
| 24 | **SA166** | C | 3 | W2 | SA167c | no |
| 25 | **SA164** | C | 3 | W2 | SA166 | no |
| 27 | **SA170** | B | 2 | W3 | SA135 | **yes** — Docker |

Positions #1, #2, #3, #4, #5, #6, #6b, #7, #8, #9, #10, #11, #12, #13, #14, #16, #17, #23, and #26 are **retired and not
reused**; #27 is newly allocated to SA170 (opened 2026-08-27); the tickets that held them are closed and archived in
[CHANGELOG.md](../../CHANGELOG.md). Gaps in the numbering are expected and carry no meaning.
#15, #18, and #21 are the per-lane heads. #21 has a merged Phase-A slice at `f6f3bbce`: its product
bytes are reviewed, but A remains unaccepted after the caller-suite failure recorded in D3 and B-F
are outstanding. #18 is a stalled acceptance on
`wt-track1` product tip `1743871f` (phases A-D accepted, E outstanding) and is the only unmerged
delta in the release; #15 has a merged partial with C/D accepted and E outstanding. All three remain
serialized by the shared PostgreSQL cluster, not by any ticket edge. #27 is newly opened behind #15
on W3 and carries the E2E-harness obligation lifted out of #15's phase E1.

Band-C positions (19, 20, 22, 24, 25) are *earliest-eligible*, not commitments. #27 is band B and
is not a band-C tail: it discharges an obligation lifted out of #15, so it may not be dropped. Any of them may slip
past the release without blocking it; none may displace a band-A or band-B leg.

### Shared conflict surfaces

Standing surface for every ticket: `CHANGELOG.md`, `docs/technical/roadmap.md`, and `docs/technical/v88_ticket_context.md` when the ticket's concept notes change.
Additional per-ticket surfaces:

| Ticket | Additional shared surface | Why |
|---|---|---|
| SA167c | every `quickscale_modules/*/module.yml`, `quickscale_core/.../manifest/{schema,loader}.py`, `scripts/gate_registry.json`, `Makefile`, CI workflow, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` | retires the inert key and registers the declaration gate; **registry membership is why this is W2** |
| SA167d | `quickscale_cli/src/quickscale_cli/commands/module_config.py`, `docs/technical/module-extension.md` | CLI wiring drain; touched by no other v88 ticket |
| SA135 + SA163 | `scripts/test_integration.sh`, `scripts/provision_test_roles.sh`, `scripts/provision_ci_postgres.sh` (new), all four `.github/workflows/`, `scripts/test_gate_parity.py`, `Makefile`, `docs/technical/validation_policy.md`, `docs/others/arch-audit.md` | changes the documented DB precondition and the CI environment |
| SA160, SA161 | generator templates + **SA90 emission-parity fixture**, `docs/others/tech-audit.md` | emitted output changes |
| SA164 | `docs/others/arch-audit.md`, `scripts/gate_registry.json`, `scripts/check_gate_parity.py`, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`, `.../production.py.j2`, `quickscale_modules/orgs/.../apps.py` | watchlist discharge; **W2** — registry and the SA92 test are W2-owned surfaces, and it merges last |
| SA165 | `docs/others/tech-audit.md`, `quickscale_core/.../state_schema.py`, `scripts/test_isolation_conformance.sh`, `quickscale_core/tests/test_generator/test_generator.py`, `OPERATIONS.md.j2` | watchlist discharge; W1-isolated |
| SA166 | `scripts/gate_registry.json`, `Makefile`, CI workflow, `docs/others/tech-audit.md` | new process gate |
| SA170 | `quickscale_cli/src/quickscale_cli/utils/docker_utils.py`, `quickscale_cli/tests/test_e2e_development_workflow.py`, `quickscale_cli/tests/test_react_theme_e2e.py`, `scripts/test_e2e.sh`, `docs/others/tech-audit.md` | E2E Docker resource contract and failure diagnostics; **W3** — needs the exclusive Docker slot |

**Eight surfaces are contended and need naming explicitly:**

- `scripts/gate_registry.json` — SA167c, SA166, and SA164 own this W2-only surface. SA123's two
  scanner entries are settled tree state and remain preserved while the registry never crosses
  worktrees.
- `quickscale_modules/*/module.yml` — SA167c (#21), **on W2**. Its merged partial retires
  `django_apps:` from the eleven manifests that carried it while preserving all twelve accepted
  app projections. Keeping this W2-only surface on one
  lane is why SA167c could not move to W1 with the other wiring legs.
- `quickscale_core/.../manifest/entry_point.py` — no open ticket owns this file. Its
  manifest-read behaviour and module-owned adapter registry are settled tree state; future
  changes must preserve the generic-only boundary rather than reinstating any literal.
- `scripts/test_gate_parity.py` — sole remaining open owner is SA135+SA163 (W3, merge #15).
  The regenerated 24-entry publish oracle is already on the integration branch; SA135+SA163
  must preserve it when retiring or deriving its own transcribed shell literal, along with SA123's
  settled hosted-job, `needs`-edge, run-value, publish/E2E-path, and generator expectations — see
  [Standing rules carried from closed decisions](#standing-rules-carried-from-closed-decisions).
  No other open W1 or W2 ticket touches this file.
- `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` — SA167c (#21)
  removes its dependence on the retired `django_apps:` key, then SA164 (#25) fixes its
  `_migdir()` fallback and re-anchors its parity backstop. Both are on W2 and merge in that
  order, so this surface no longer crosses worktrees; SA164's migration-baseline work is a
  content dependency on the regenerated migrations rather than a file dependency.
- `quickscale_core/.../templates/project_name/settings/production.py.j2` — SA161 (#19, W3)
  deletes or annotates the dead `get_client_ip` definition and removes the misleading rebind
  comment at `:119-123`; SA164 (#25, W2) makes the privileged-command frozenset at `:185` stop
  claiming an authority it does not hold. Different regions of one file on **two lanes**, with no
  ordering edge between them. Merge order is #19 before #25, so the contention is one-directional
  and the standing sync-before-merge-back procedure covers it; neither ticket may widen into the
  other's region.
- `scripts/test_isolation_conformance.sh` — SA163's edit is merged in the W3 partial; SA165 (#22,
  W1) still owns its skip-allowlist narrowing. The prior two-lane contention is now settled input:
  SA165 syncs current `v88` and applies its one-line narrowing over the merged SA163 behavior.
- `quickscale_core/tests/fixtures/sa90_emission_manifests.json` — SA161 and SA160. Each
  rebaseline appends its own `baseline_evidence` entry with per-file rationale; the
  sync-before-merge-back procedure must preserve every prior entry.

- `scripts/test_e2e.sh` — SA170 (#27, W3) is the only open owner. SA135+SA163's merged partial
  already settled the provisioning side of the E2E lane; SA170 touches the scope/cleanup side.
  Merge order #15 before #27 keeps the handoff one-directional within W3, and no other lane touches
  this file.

`docs/others/arch-audit.md` is on the surface of SA163 only (Finding 13).
Findings 2, 4, and 7 remain untouched, per the standing "neither" rule above.

---

## v88 backlog track

Each ticket below carries its band, assigned worktree, merge position, and acceptance criteria.

This section holds the implementation tickets; the
[audit-derived backlog](#audit-derived-backlog) below holds the rest of the same queue.
**Read them as one list** — the merge-order table above is the authority, and four audit tickets
sit ahead of open work in this section.

Conceptual background, mental models, and implementation notes for **every** ticket live in [v88_ticket_context.md](v88_ticket_context.md); this roadmap remains authoritative for scope, worktrees, and merge order.

- [ ] **SA167c — Retire `django_apps:` and gate the app declaration.** `Band B · Tier 2 · W2 · merge #21 · deps: none · closes the SA167 family`
  `django_apps:` was inert declarative surface: eleven manifests carried it, the loader parsed it,
  no production path read it, and one SA92 helper used it before falling back to a guessed path.
  The merged partial below removes that redundant surface; SA164 still owns making the remaining
  conventional migration-path lookup fail hard and re-anchoring its parity backstop.
  **Acceptance:** `django_apps:` is either derived from the `apps` wiring projection or removed from all manifests, `ModuleManifest`, and the loader, with no key parsed-but-unread remaining; a conformance gate fails when a module ships models or a migration without declaring at least one Django app, registered in `scripts/gate_registry.json` and passing `scripts/check_gate_parity.py`; the gate is proved by deleting a module's app declaration and observing red, reverted before merge; `test_sa92_migration_squash_guardrail.py` no longer depends on the retired key.
  **State (measured 2026-08-28): Phase-A product slice merged; corrected acceptance partial.**
  Product commit `f6f3bbce` remains merged. `wt-track2` synchronized cleanly to `v88` at
  `8a8f364b` before this attempt. Phase A is **not accepted**; phases B-F were not reached.
  Keep this item unchecked under the open-work-only policy.
  **Completed in the merged partial:** removed `django_apps:` from `ModuleManifest`, the loader,
  the obsolete loader test, all eleven source declarations and their eleven byte-identical core
  snapshots; removed the SA92 helper's retired-key dependency and stale payload plumbing; preserved
  all twelve non-empty `apps` wiring projections and public adapter outputs. Independent convergence
  fixed the stale helper plumbing, and terminal review found no product-slice defect.
  **Latest acceptance evidence.** The coverage-isolated loader command exited 0 with 112 passed;
  the restricted-role orgs command exited 0 with 884 passed, 11 skipped, and 2 warnings;
  `make check-manifest-sync` exited 0; and `make check-gate-parity` exited 0. The required
  four-caller command then exited 1 with 256 passed and 2 failed in
  `TestRegenerateManagedWiringSkipManifestNotFound`, at
  `quickscale_cli/tests/test_module_wiring_manager_manifest.py:767,796`: both expect embedded
  inventory drift to fail, while the current bundled twelve-module fallback succeeds. Under the
  required stop-at-first-unexpected-red rule, neither the literal twelve-module source-bound caller
  probe nor the final `git diff --exit-code` unchanged-tree oracle was run. No tracked file changed,
  and this green prefix is not Phase-A acceptance.
  **Blocking:** D3 must select the authoritative embedded-inventory contract. Correct the losing
  test or runtime surface under fresh plan authority, rerun all of A in order, and retain broad
  coverage in the final campaign. Do not treat the green prefix as retroactive Phase-A acceptance.
  **Decisions needed:** D3 under [Open decisions](#open-decisions).
  **Remaining plan (all phases serial; do not redo the merged retirement bytes):**
  0. **Pre-existing caller mismatch:** settle D3 and correct the losing test/runtime surface under a
     fresh reviewed plan, including caller-parity evidence if runtime behavior changes.
  1. **A-acceptance:** after the D3 correction is reviewed and the candidate starts with no tracked
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
        — expect exit 0 after the D3-selected contract correction.
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
  2. **B-gate:** add a fail-hard `check_module_app_declaration` checker and hermetic tests covering
     model/migration evidence, empty or malformed projections, malformed manifests, inventory and
     filesystem failures, evidence-free modules, deterministic diagnostics, and current tree state.
  3. **C-integration:** register `check-module-app-declaration` in Make and the gate registry for
     local serial, local parallel, and hosted CI; update the hosted generator/catalog, generated
     `ci.yml`, parity/current-state tests, local-runner labels, and script map. Publish and E2E remain
     unchanged.
  4. **D-negative proof:** remove `social`'s sole apps projection temporarily, require the new gate
     to fail for the intended reason, restore the exact bytes, and prove both the gate and manifest
     sync green.
  5. **E-closeout:** reconcile decisions, implementation contract, validation policy, ticket
     context, roadmap queue/counts, and changelog evidence. Archive and remove SA167c only after all
     acceptance is green; retain the SA164 and SA166 boundaries.
  6. **F-frozen candidate:** sync current `v88`, run the complete focused-to-broad campaign on one
     unchanged candidate, perform independent convergence and terminal attestation, and merge only
     that exact tip.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/manifest/{schema,loader}.py`, every `quickscale_modules/*/module.yml`, `scripts/gate_registry.json`, `Makefile`, CI workflow, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`.

- [ ] **SA167d — Complete the CLI wiring-drain acceptance.** `Band B · Tier 2 · W1 · merge #18 · deps: none · blocks SA165`
  `quickscale_cli/src/quickscale_cli/commands/module_config.py` carried a
  `configure_<name>_module()` / `apply_<name>_configuration()` pair per module — a fifth place the
  same wiring facts were expressed. Plan-time interactive prompts that collect **desired
  configuration** are legitimate and stay; anything deciding what a module *wires* belongs in the
  module. The product bytes implementing that boundary are written.
  **Acceptance:** no function in `module_config.py` decides a module's apps, middleware, settings
  keys, or URL includes — those come from the module's manifest through its adapter; the remaining
  surface is desired-configuration collection only, and that boundary is stated in the module's
  docstring; a test asserts the CLI contributes nothing to `ModuleWiringSpec`; the stale-flow note
  in [module-extension.md §Building a Module](module-extension.md#building-a-module-authoring-checklist)
  is retired once the deviation it names is gone.
  **State (measured 2026-08-27): phases A-D accepted, phase E outstanding.** The retained product
  tip is `1743871f`, carried under one docs-only checkpoint at `wt-track1` tip `467714cb`; the
  worktree is clean. Against `v88` at `713bd4a7`, `wt-track1` is **nine commits ahead and seven
  behind** — **this is the release's only unmerged product delta.** A-D acceptance evidence is
  archived in [CHANGELOG.md](../../CHANGELOG.md). Keep this item unchecked: the retained product
  delta is unmerged and its terminal review produced no grade.
  **This is not a merge-back-only ticket.**
  **Completed in the latest resumption.** The worktree synchronized the then-current `v88` at
  `ca9ecbdc` and preserved strict twelve-module no-argument adapter refresh plus scoped
  selected-module refresh. E0's focused acceptance surface passed 816 tests, and lint and type
  checks passed. Its ordered `make test` then failed on the storage package's lazy public API at
  45% coverage, so E0 was not accepted. Serial convergence retained the intended CLI boundary and
  corrected that synced coverage seam, the root pytest `scripts` import path, a stale Bandit
  suppression identity, auth-migration assessment complexity and coverage, and the obsolete quality
  baseline identity. On the resulting `1743871f` tip, the coupled auth/storage suite passed 31 tests;
  `make lint`, `make typecheck`, `make test`, `make check`, and `make quality` all passed. The full
  totals were Core 2,881 passed / 1 skipped, CLI 2,098 passed, and modules 2,554 passed / 85 skipped;
  quality reported zero warning, critical, and total regressions.
  **Pending.** E0 remains unaccepted because its scoped sequence was red at return and convergence
  cannot retroactively accept it. C1 ledger reconciliation and V1 exact-candidate validation were
  not reached after that halt. Phase E must be rerun and explicitly accepted on the retained delta;
  then every current-status assertion in `CHANGELOG.md`, `docs/index.md`,
  `docs/others/arch-audit.md`, `docs/technical/decisions.md`,
  `docs/technical/implementation_contract.md`, `docs/technical/module-extension.md`,
  `docs/technical/v88_ticket_context.md`, and
  `quickscale_core/tests/test_v88_ticket_context_consistency.py` must be reconciled to the accepted
  A-E ledger and the final observed totals.
  **Blocking.** The terminal review was blocked because it did not receive the complete authoritative
  diff from the pre-run base through `1743871f`; therefore the product delta is ungraded. `v88` has
  also advanced seven commits past the last synchronization, so the sync will have to resolve
  `docs/technical/roadmap.md` against the current pass. Close both blocks by accepting E0,
  completing C1, synchronizing the then-current `v88` successor, running the complete final campaign
  on one unchanged tip, and supplying that tip's complete diff to an independent reviewer before
  merge-back.
  **Decisions needed:** none. SA165 remains blocked only by completion of this ticket.
  **E0's ordered acceptance sequence — reconstructed 2026-08-27 and now written down.** The prior
  plan said only *"re-run E0's exact ordered sequence"*, whose referent lived in a dispatch document
  that is not in the tree; **that made this ticket undispatchable**. The sequence below is
  reconstructed from this ticket's own acceptance criteria and the recorded E0 evidence (816 focused
  tests, then lint, then typecheck, then an ordered `make test` that failed on storage coverage).
  Run it in this order on the retained delta, stopping at the first red:
  1. `poetry run pytest quickscale_cli/tests/commands/test_module_config.py quickscale_cli/tests/commands/test_module_config_extended.py quickscale_cli/tests/commands/test_module_commands.py quickscale_cli/tests/test_module_wiring_manager_manifest.py quickscale_cli/tests/test_module_manifest_contract.py -q -o addopts= --no-cov`
     — the CLI wiring-boundary surface; expect green and the recorded **816** focused total.
  2. `make lint` and `make typecheck` — expect exit 0.
  3. `make test` — the ordered combined gate; expect Core, CLI, and module totals green with no
     coverage regression. This is the step E0 failed on; it is the one that must now be green.
  4. `make check` and `make quality` — expect `make quality` no worse than found (zero warning,
     critical, and total regressions).
  **Rollback:** the delta is committed at `1743871f`; `git reset --hard 1743871f` in `wt-track1`
  discards any correction attempt without touching `v88`. Schedule steps 1-4 outside W3's cluster
  window.
  **Remaining plan, in order.** (1) Run the reconstructed E0 sequence above on the retained
  delta and accept phase E only if every step is green. (2) Complete C1's same-fact ledger reconciliation and
  executable consistency test without archiving SA167d early. (3) Synchronize current `v88`, resolve
  the standing closeout conflict surface, and run V1's complete validation campaign on one frozen
  candidate. (4) Independently review the complete authoritative diff for that exact candidate.
  (5) Only after green acceptance and review, archive completion, remove this open-work entry, retire
  merge position #18, release SA165, and merge the reviewed tip. Report final changed-line and
  elapsed-time/lines-per-hour metrics from the original `2026-08-27 18:52:34 +0200` measurement
  start.
  **Shared conflict surface:** `quickscale_cli/src/quickscale_cli/commands/module_config.py`, `docs/technical/module-extension.md`, plus `CHANGELOG.md`, `docs/index.md`, `docs/others/arch-audit.md`, `docs/technical/{decisions,implementation_contract,roadmap,v88_ticket_context}.md` and `quickscale_core/tests/test_v88_ticket_context_consistency.py` for the ledger reconciliation.
- [ ] **SA135 — Give test suites an owned PostgreSQL lifecycle.** `Band B · Tier 2 · W3 · merge #15 · deps: none · PostgreSQL + Docker slot · carries SA163`
  Provision and tear down the server used by repository gates; replace the current out-of-band host assumption while retaining an asserted unavailability negative control.
  **Acceptance:** the integration gate provisions its own PostgreSQL 18 server and tears it down, with no reliance on a pre-existing host server; the `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` role contract is preserved; the asserted-unavailability negative control still fails loudly when the server cannot be provisioned, rather than skipping; `make test-integration` passes on a machine with no PostgreSQL running; [validation_policy.md](validation_policy.md) is updated to drop the out-of-band host precondition; image identity follows the settled content-addressed backend-image convention.
  **State (measured 2026-08-27): partial delivery merged into `v88`.** The merge object is
  `f070f39b`, the second of two merges (`0661f55f`, then `f070f39b` carrying the `203fcd61`
  lifecycle/module-E2E remediation). Phases P/A/B and C/D are accepted; E was
  dispatched but is not accepted, and F/G were not reached. Keep this item unchecked under the
  open-work-only policy. In the latest resumption, E0 accepted the unchanged external-state
  baseline; E1 returned partial with no file change because no deterministic cause reproduced.
  **Completed in the merged partial:** phases P/A/B and C/D — the hermetic Docker-unavailable
  probe, the strict no-host-server window, the single four-caller provisioning authority, and the
  `203fcd61` lifecycle/module-E2E remediation. The evidence is archived in
  [CHANGELOG.md](../../CHANGELOG.md); do not repeat C or D.
  **Completed in the latest resumption:** E0 confirmed both former SA142 orphan names and
  `quickscale-react-test` absent, with no deletion; `pg18-af10` retained its exact container, image,
  mount, and running identity, and all twelve databases remained owned by `quickscale_test_role`.
  E1 then recorded these green runs without changing a file: the isolated development node (1
  passed), isolated React node (1 passed), synchronized two-node run (2 passed), and exact
  `QS_E2E_PARALLEL=0 make test-e2e` context (Core 38 passed; CLI 40 passed; cleanup complete). E1's
  exact literal `TEST COMMAND` chain was not run — **historical note only**; that chain belonged to
  the superseded E1 scope and is discharged by SA170 (#27), not by this ticket.
  **Pending:** E1 is narrowed to what this ticket actually owns — the **PostgreSQL lifecycle**
  evidence: provisioning, teardown, the role contract, and the asserted-unavailability negative
  control, all of which E0 and the C/D phases already exercise deterministically. The two historical
  **E2E Docker-harness** failures that stalled E1 are **not SA135 defects** and are re-ticketed as
  **SA170 (#27)**; see that ticket for the root cause. E2 must then run
  `QS_E2E_PARALLEL=0 make test-e2e` followed only on green by `make ci-e2e` on one unchanged
  candidate; `make ci-e2e` was not reached in this pass.
  F must reconcile validation policy, Finding 13, ticket context, roadmap counts/dependencies, and
  changelog evidence. G must sync current `v88`, run the complete campaign and independent review
  on one unchanged tip, and merge only that exact tip.
  **Why the previous blocker is retired, not waived.** E1 was previously held on deterministic
  red-before/green-after evidence for a Docker `No such container` startup race and a 300-second
  React build timeout. Neither reproduced in isolated, paired, or exact serial full-E2E contexts,
  and the runner emitted `qs_e2e_tmp_*` lane scopes instead of the fixed label the phase named.
  **Root-causing the harness showed the criterion was unsatisfiable as written and that both
  symptoms have a readable structural cause** — see SA170. Re-running SA135's phase E can never
  produce that evidence, because the defects are not in SA135's provisioning code. The obligation
  moves to SA170 with a deterministic proof; nothing is waived.
  **Decisions needed:** none. The scope split is recorded under
  [Open decisions](#open-decisions) as **D1**, already answered by this pass's root-cause reading;
  it is retained there only until SA170 merges. The exclusive service-window authorization remains
  available; `pg18-af10` is running.
  **Inherited obligation from the closed SA123.** When this ticket retires or derives the
  transcribed provisioning shell literal in `scripts/test_gate_parity.py`, it must preserve SA123's
  settled hosted-job, `needs`-edge, run-value, publish/E2E-path, and generator expectations (the
  12→14 hosted-job and 6→8 `test`-barrier lines) and the regenerated 24-entry publish oracle. The
  decision that authorized them is closed and archived.
  **Cross-worktree surface:** the merged partial edits `scripts/test_isolation_conformance.sh`,
  which **SA165 (#22, W1) also owns**. See
  [Shared conflict surfaces](#shared-conflict-surfaces) — merge order #15 before #22 means SA165
  starts from the settled SA163 bytes, and the sync-before-merge-back procedure covers it.
  **Remaining plan (all phases serial; P/A/B/C/D and accepted E0 are not repeated):**
  1. **E1 — PostgreSQL-lifecycle evidence only:** accept E1 on the provisioning surface this
     ticket owns — `make test-integration` on a host with no PostgreSQL running, the
     `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` role contract, the hermetic
     Docker-unavailable probe, and the asserted-unavailability negative control failing loudly
     rather than skipping. Each of these is deterministic today and needs no flake reproduction.
     Record the emitted `qs_e2e_tmp_*` scope as the harness's intended per-run isolation contract
     (`scripts/test_e2e.sh:557` derives it from `mktemp -d`), not as a deviation. Do **not** attempt
     the two E2E Docker failures here; they are SA170's.
  2. **E2 — unchanged-candidate acceptance:** after E1 is accepted, run exact serial E2E and then
     `make ci-e2e` on one unchanged tree, with exact cleanup and PostgreSQL baseline equality.
  3. **F — policy and status reconciliation:** reconcile validation policy, Finding 13, ticket
     context, roadmap counts/dependencies, changelog evidence, docs navigation, and the executable
     consistency consumer. Keep the ticket open if any required gate is red.
  4. **G-sync / G-validate:** sync current `v88` in W3, preserve concurrent closeout entries, and run
     the complete focused, provisioning, parity, lint, type, check, integration, BYPASSRLS,
     isolation, test, quality, serial-E2E, and CI-E2E campaign on one frozen candidate.
  5. **G-closeout / G-final:** only after the complete campaign and independent convergence are
     green, archive and remove SA135/SA163 from this open-work-only roadmap, retire Finding 13,
     rerun the final frozen-tip campaign, terminally attest, and merge that exact tip. Report final
     changed lines and elapsed-time/lines-per-hour metrics from the original
     `2026-08-26 16:07:35 +0200` measurement start.

---

## Audit-derived backlog

Tickets opened from the live findings in [arch-audit.md](../others/arch-audit.md) (2026-08-21) and [tech-audit.md](../others/tech-audit.md) (2026-08-21). Both documents remain the SSOT for finding detail, evidence, and refutation; this section is authoritative for scope and sequencing only.

**These are not follow-on work.** The former band-A gate-layer ticket is complete; the remaining
audit-derived entries are sequenced with the implementation section.
SA163 executes inside SA135, and SA170 is band-B harness work opened out of SA135's phase E1. The
remaining five are **band C** slack filler. The merge-order
table above is the single authority; this section carries the finding detail.

Every ticket here that closes or changes a live finding takes `docs/others/arch-audit.md`
or `docs/others/tech-audit.md` onto its shared conflict surface per the execution rules.

### Sequencing of the audit-derived legs

```text
W2 spine:  SA167c (#21) ──► SA166 (#24) ──► SA164 (#25)

SA163 (arch F13, CI environment) ──► rides inside SA135 (W3, merge #15)

W3 tail:   SA135 (#15) ──► SA170 (#27) ──► SA161 (#19) ──► SA160 (#20)
```

Band A is clear. The completed shared-baseline repair and the previous gate-layer prerequisite are
archived in [CHANGELOG.md](../../CHANGELOG.md), and their positions are retired rather than reused.

- [ ] **SA170 — Give the E2E Docker harness a closed resource contract and a truthful failure report.** `Band B · Tier 2 · W3 · merge #27 · deps: SA135 (worktree ordering) · PostgreSQL + Docker slot · absorbs SA135's stalled E1 flake obligation`
  Closes tech-audit **TA70** (`container-status-substring-match`, S4) and the carried tooling gap
  *"no test exercises the E2E harness's own failure paths"*.
  Opened 2026-08-27 by root-causing the two historical failures that stalled SA135's phase E1 — a
  Docker `No such container` startup race and a 300-second React build timeout. Neither is a SA135
  provisioning defect, and neither is a genuine race in Docker. Both are readable in the harness
  source, and both come from the **same shape**: one test opts out of the per-scope resource
  contract every other E2E resource obeys, and the readiness helper cannot report why anything
  failed.
  - **The scope contract works and the React build test is outside it.** `scripts/test_e2e.sh:557`
    derives `RUN_SCOPE` from `mktemp -d` and `:596` appends `$BASHPID` per lane, so every run and
    lane gets a unique scope; `docker-compose.yml.j2` stamps `com.quickscale.{owner,lifecycle,scope}`
    on every container and volume, and `cleanup_scoped_resources` reclaims by label. The emitted
    `qs_e2e_tmp_*` names are that design working, not a deviation.
    `quickscale_cli/tests/test_react_theme_e2e.py:657` instead hardcodes `image_tag =
    "quickscale-react-test"` and builds with no `--label` and no scope prefix. Consequences, both
    structural: two concurrent E2E runs on one daemon share that tag, so one test's
    `finally: docker rmi quickscale-react-test` (`:692`) removes the image the other is about to
    `docker run` — which is exactly the `No such container`/`No such image` class; and because the
    image carries none of the `com.quickscale.*` labels and is tagged rather than dangling,
    `cleanup_scoped_images` (`scripts/test_e2e.sh:401-420`) **cannot** see it by construction, which
    is why the prior pass had to hunt it by literal name.
  - **`timeout=300` measures the Docker layer cache, not the product.** The same call
    (`test_react_theme_e2e.py:663-668`) budgets five minutes for a cold build that compiles a React
    frontend and installs a PostgreSQL 18 client. Warm it is seconds; cold — after a prune, a base
    image bump, or a loaded host — it is minutes. `subprocess.TimeoutExpired` is not caught, so a
    timeout aborts before the assertions and leaves the partial build behind. This is a benchmark
    wearing an assertion's clothes and **cannot be made deterministic by re-running it.**
  - **The readiness helper destroys its own diagnostic.**
    `quickscale_cli/tests/test_e2e_development_workflow.py:157-168` polls
    `get_container_status(name)` and accepts `"up" in status.lower()`.
    `get_container_status` (`quickscale_cli/src/quickscale_cli/utils/docker_utils.py:328-348`) runs
    `docker ps -a --filter name=<name>`, where Docker's `name` filter is a **substring regex**, not
    an exact match, and `-a` includes dead containers. So `<scope>_backend` also matches any
    container whose name contains that string, several matches are concatenated into one blob before
    the substring test, and a container that **exited immediately** yields a status the predicate
    reads as "not up yet" — the poll then burns its full 40 s and reports the generic
    *"Backend container did not become running within 40s"*. **The crash reason is never surfaced.**
    That is why repeated E1 reruns kept returning green-but-uninformative: when the harness does
    fail, it cannot tell you why, so no number of reruns yields a cause.
  **Acceptance:** the React build image is tagged from `QS_E2E_RESOURCE_SCOPE` and carries the same
  `com.quickscale.{owner,lifecycle,scope}` labels as every other E2E resource, so
  `scripts/test_e2e.sh --cleanup-scope <scope>` reclaims it and no fixed tag remains in any test;
  `subprocess.TimeoutExpired` is caught and fails with a message naming cache state and the observed
  duration, and the build budget is either raised to a documented cold-cache figure or split into a
  correctness assertion plus a separately-reported duration; `get_container_status` filters on an
  anchored exact name (`name=^<name>$`), returns a structured state rather than a display string,
  and distinguishes *absent*, *created*, *running*, and *exited(code)*; the readiness poll fails
  immediately and loudly on *exited*, naming the exit code and the last log lines, instead of
  waiting out its timeout; a test asserts a second concurrent scope cannot observe or delete the
  first scope's build image; tech-audit **TA70** (`container-status-substring-match`) is retired.
  **Evidence policy — this is the deterministic red-before/green-after E1 could not produce.**
  Each defect is proved at the level where determinism exists, with no flake reproduction required:
  (1) a pure unit test over the readiness predicate and over `get_container_status`'s argv, fed
  `Exited (1) 3 seconds ago`, `Created`, `Up 3 seconds`, a two-container blob, and `None` — red on
  today's substring logic, green after; (2) a labelled-resource assertion that
  `cleanup_scoped_resources <scope>` removes the React build image — red today because the image is
  unlabelled, green after; (3) a two-scope test proving the fixed-tag collision is gone. All three
  are repeatable and none depends on scheduling a collision.
  **Why this is a separate ticket rather than a widening of SA135.** SA135 owns the PostgreSQL
  lifecycle; these are E2E Docker-harness defects in CLI test code and `docker_utils.py`, files SA135
  does not touch. Per the execution rules, a scope finding is ticketed rather than fixed in place.
  Splitting it lets SA135's phase E close on the provisioning evidence it can actually produce.
  **Serialization:** inherits W3's exclusive PostgreSQL + Docker slot. Merges after SA135 so it
  starts from the settled provisioning bytes.
  **Shared conflict surface:** `quickscale_cli/src/quickscale_cli/utils/docker_utils.py`, `quickscale_cli/tests/test_e2e_development_workflow.py`, `quickscale_cli/tests/test_react_theme_e2e.py`, `scripts/test_e2e.sh`, `docs/others/tech-audit.md`.

- [ ] **SA160 — Share one correct CSRF-token helper in the React theme.** `Band C · Tier 2 · W3 · merge #20 · deps: SA161 (emission-parity ordering)`
  Closes tech-audit **TA67** (`spa-csrf-token-duplicate-cookie`, S3) — the only finding in deployment reality #3, the internet-facing generated project. `themes/showcase_react/src/hooks/useApi.ts:20-28` and `src/components/forms/FormRenderer.tsx:206-211` carry the same eleven lines: the parser splits `document.cookie` on `"; csrftoken="` and accepts the result **only when it yields exactly two parts**. Two `csrftoken` cookies yield three, so `getCsrfToken()` returns `''`, `buildRequestHeaders` (`:89-94`) skips `X-CSRFToken`, and Django rejects every POST/PUT/PATCH/DELETE with 403. The triggering state is ordinary: an `app.example.com` deployment alongside a `.example.com` cookie, the outcome of setting or changing `CSRF_COOKIE_DOMAIN`, of a sibling Django app on another subdomain, or of a stale apex-scoped cookie. GETs keep working, so the app looks alive and merely refuses to save, and no error names the cause. Fails closed — availability, not a security hole. There is no shared CSRF helper, no fetch interceptor, and no template-injected token, so no layer-up guard exists.
  **Acceptance:** one shared helper in `src/lib/` iterates cookies rather than counting split segments — splitting on `'; '`, matching the name exactly, and `decodeURIComponent`-ing the value, per Django's own documented `getCookie` — and both call sites import it with no third variant remaining; a `vitest` table test covers `'csrftoken=A; csrftoken=B'`, `'sessionid=x; csrftoken=A'`, `'csrftoken=A'`, and `''`, with the first three returning a non-empty token; the tech-audit finding is retired.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/`, generator emission parity baselines, `docs/others/tech-audit.md`.

- [ ] **SA161 — Remove the dead `get_client_ip` definitions from generated settings.** `Band C · Tier 3 · W3 · merge #19 · deps: SA135 (worktree ordering)`
  Closes tech-audit **TA68** (`generated-settings-dead-client-ip`, S4). `templates/project_name/settings/base.py.j2:61` and `settings/production.py.j2:123` both define a module-level `get_client_ip(request)`, and the production copy rebinds it under a comment claiming the rebind exists "so that production defaults … are actually in effect at request time". Neither is reachable: Django's `Settings` copies only **uppercase** names off the settings module, so `django.conf.settings.get_client_ip` does not exist, and grep across all templates returns only the two definitions. The live implementation is `quickscale_modules_orgs.current_org.get_client_ip`, which reads the uppercase `USE_X_FORWARDED_FOR` / `TRUSTED_PROXY_COUNT` settings dynamically and is correct.
  **Acceptance:** both definitions are deleted, or each carries a comment pointing at the orgs helper as the live implementation; the uppercase settings and the `REST_FRAMEWORK["NUM_PROXIES"]` recomputation are retained unchanged; the misleading behavioural comment at `production.py.j2:119-122` is removed either way; a generated project boots and proxy-aware client-IP resolution is unchanged, asserted by a test; emission parity is rebaselined with rationale; the tech-audit finding is retired.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/`, emission parity baselines, `docs/others/tech-audit.md`.

- [ ] **SA163 — Derive the CI PostgreSQL environment from one authoritative source.** `Band B · Tier 2 · W3 · merge #15 · deps: SA135 — executes inside SA135, not as a separate pass`
  Closes arch-audit **Finding 13** (`ci-environment-hand-replicated`, rank 2, horizon `now`). The gate registry declares *which* gates run in *which* contexts, but the environment those gates require is expressed nowhere declaratively and is hand-replicated as shell across **13 stations** (a **14th** was identified 2026-08-24, see below): the PGDG PG18 install in four copies (`ci.yml:92-107`, `ci.yml:408-427`, `publish.yml:161-187`, `e2e.yml:74-91`), divergent PG18 verification (three check `command -v` *and* `--version | grep "(PostgreSQL) 18"`; `e2e.yml:92` checks only `test -x`), four `createdb` lists, four grant loops, five `QS_*_DB_USER` blocks, and a **14th** station where `scripts/test_gate_parity.py:1125-1180` transcribes the shell verbatim as a Python literal. `nightly-bypassrls.yml:81-82` installs plain `postgresql-client` — Ubuntu 16.x, no PGDG — while creating `test_quickscale_backups` and setting `QS_BACKUPS_DB_USER`, against `ci.yml:93-95`'s statement that the backups DR engine enforces a PostgreSQL 18 `pg_dump`/`pg_restore` contract that 16.x fails.
  Two apparent divergences are **deliberate and verified correct — do not "fix" them**: the 6-entry `QS_*_DB_USER` block at `ci.yml:627-632` is exactly `orgs` plus `RLS_MODULES` from `test_isolation_conformance.sh:141`, and the isolation job's 11-database list omits `backups` because that job runs no backups tests.
  Take **Option 1** (one `scripts/provision_ci_postgres.sh`, four callers, module list derived from the discovery shim exactly as `check_sa117_scope.py:48` already does). Do it **inside SA135**, whose allowlist already spans `scripts/test_integration.sh`, `scripts/provision_test_roles.sh`, the `Makefile`, and the documented DB precondition — not as a separate pass over the same files. The registry already contains SA123's implemented security-gate schema, so any later environment-schema change must preserve it.
  **Acceptance:** the PGDG install, `createdb` loop, and grant loop exist once and all four workflows call them; the module universe is derived from `contracts/module_discovery.py --list-modules` and fails hard when unavailable, with no hand-maintained module list among the provisioning stations; PG18 client verification is identical in all four contexts, including `e2e.yml`; the nightly PostgreSQL 16 client question is settled by determining whether `make test-bypassrls` reaches a `pg_dump`/`pg_restore` path — if it does, the divergence is a live defect and is fixed; the two deliberate divergences above are preserved and documented as deliberate; `test_gate_parity.py`'s transcribed shell literal is retired or derived; the
  **BYPASSRLS role provisioning station** — the role creation plus twelve `ALTER DATABASE …
  OWNER` / `GRANT ALL ON SCHEMA public` pairs living only inside
  `.github/workflows/nightly-bypassrls.yml` and reachable by no repository script, which is what
  stranded the prior BYPASSRLS lane locally — is either folded into `scripts/provision_test_roles.sh`
  behind an explicit opt-in flag or extracted alongside the other provisioning, with its
  `LOGIN CREATEDB BYPASSRLS NOINHERIT NOSUPERUSER NOCREATEROLE` contract asserted the way the
  three `NOBYPASSRLS` contracts already are, and its database list derived rather than
  hand-listed, and the two database lanes are made able to coexist on one cluster — a per-lane
  database set, or a provisioning step that owns the ownership flip — so that running
  `make test-bypassrls` no longer breaks the next `make test-integration` and vice versa
  (measured 2026-08-24); `QUICKSCALE_ALLOW_BYPASSRLS: "0"` at `ci.yml:626` and the restricted-role isolation connection survive the refactor unchanged; arch Finding 13 is retired with evidence.
  **Shared conflict surface:** all four `.github/workflows/`, `scripts/provision_ci_postgres.sh` (new), `scripts/test_integration.sh`, `scripts/provision_test_roles.sh`, `scripts/test_gate_parity.py`, `.github/workflows/nightly-bypassrls.yml`, `Makefile`, `docs/others/arch-audit.md`. **Serialization:** inherits SA135's exclusive PostgreSQL + Docker slot.

- [ ] **SA164 — Adjudicate the arch-audit watchlist's unevaluable and drifted items.** `Band C · Tier 3 · W2 · merge #25 · deps: SA166 (worktree ordering)`
  The arch audit carries five watch items; three are simply not fired and need no work, but two carry explicit actions and one is a naming question that becomes load-bearing on a specific trigger.
  - **SA92 migration-squash discovery tuple — artifact located 2026-08-21, now evaluable.** The audit recorded this as unlocatable, but the artifact is `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` — a bounded literal tripwire for cross-table `UPDATE … SET organization_id` DML in migrations. The prior search missed it because it grepped for `squash` in source rather than in test filenames. SA167c's merged partial removed the helper's dependency on the retired `django_apps:` key; `_migdir()` still uses the conventional path and returns `None` when it is absent, so SA164 must make that lookup fail hard rather than silently skipping a module. Its authoritative backstop is also still a catalog/data parity gate anchored to `v87`, a retired release ref no longer resolved by the quality gate. Re-anchor both remaining obligations against the regenerated migrations now on the integration branch.
  - **Privileged-command template/runtime pair — values verified equal, governance artifacts disagree.** `production.py.j2:185` and `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py:36` both hold `frozenset({"migrate", "createcachetable"})`, but the `apps.py` docstring calls itself "the single source of truth for which commands are privileged" while the template holds an independent copy. The values agree; the claimed authority does not.
  - **`trigger_inputs` has drifted from its name.** `check_gate_parity.py:2652-2690` uses the field as a bidirectional partition of `e2e.yml`'s path allowlist, not as "what changes should trigger this gate" — which is why `check-core-compat`'s trigger is `quickscale_modules/backups/**`. Not a defect; the check it performs is real and exact. Becomes load-bearing only if a gate is ever *skipped* on the basis of `trigger_inputs`.
  **Acceptance:** the SA92 item is re-anchored to `test_sa92_migration_squash_guardrail.py` with a stated trigger, its `_migdir()` fallback fails loudly instead of guessing the path, and its `v87`-anchored parity backstop is re-anchored to the current regenerated migrations; the privileged-command SSOT claim is made true — either the template reads the runtime frozenset or the docstring stops claiming sole authority — with a test asserting the two cannot diverge; `trigger_inputs` is either renamed to describe what it does or its docstring/schema description records the actual semantics plus the skip-based promotion trigger; the three not-fired items (module universe in environment lists, frontend runtime module keys, and the now-absorbed watch half of Finding 13) are re-stated with their triggers intact; `docs/others/arch-audit.md` is updated in the same change.
  **Shared conflict surface:** `docs/others/arch-audit.md`, `quickscale_core/.../templates/project_name/settings/production.py.j2`, `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py`, `scripts/gate_registry.json`, `scripts/check_gate_parity.py`.

- [ ] **SA165 — Discharge the tech-audit watch items that carry an action.** `Band C · Tier 3 · W1 · merge #22 · deps: SA167d (worktree ordering)`
  Of the remaining items in the tech audit's *Notes*, most are accepted trade-offs or are owned elsewhere (the local-wheelhouse seam is discharged by the closed SA150; integration-branch CI, generator lock generation, the DB-free healthcheck, the CRM count fallbacks, and non-durable atomic state writes are each recorded as deliberate and are **not** in this ticket's scope). Four carry a concrete action:
  - **`flush_empty_consolidated_sections` swallows a corrupt state file.** `quickscale_core/src/quickscale_core/schema/state_schema.py:386-388` returns silently on `yaml.YAMLError, OSError`, skipping the explicit `modules: {}` / `managed_files: []` markers downstream readers use to distinguish "M2 has spoken" from pre-M2 state. The trigger is narrow — the file was just written successfully by `save()` — but this is exactly the silent-fallback shape the Fail-Hard Principle names (`decisions.md:634`, `:716-732`), and `tech-audit.md` is the declared SSOT for that class.
  - **The isolation-gate skip allowlist matches on message, not test identity.** `scripts/test_isolation_conformance.sh:184` keys on `message.startswith('got empty parameter set')`, silencing an empty parameter set on *any* of the eleven parametrized tests in `test_tenant_table_conformance.py`, not only the two `PENDING_REMEDIATION` ones its own comment describes. Narrowing it to the two test names costs one line.
  - **`_HOST_DEPENDENT_PATHS` is a new hand-maintained exception station.** `be5cf024` added `frozenset({".env"})` to the SA90 emission byte-parity gate (`quickscale_core/tests/test_generator/test_generator.py:1023`). The justification is sound and the `755`/`644` mode normalization correctly removes a umask dependency, but this is an exception list on the repository's strictest gate: a second entry deserves scrutiny, a third deserves a derivation.
  - **Generated local-development credentials are predictable by construction.** `generator.py:507-508` derives `runtime_db_role = f"{package_name}_app"` and `runtime_db_password = f"{role}_password"` into `db/init.sql`, `docker-compose.yml`, and `.env.example`, none of which `.gitignore.j2` excludes. Safe as shipped — no published DB port, local dev only, production supplies `RUNTIME_DATABASE_URL` from the environment — but undocumented.
  **Acceptance:** `flush_empty_consolidated_sections` raises or reports rather than returning silently, with a regression test asserting the raise and not a log, and the fail-hard deviation is retired from the audit; the isolation skip allowlist keys on the two `PENDING_REMEDIATION` test identities rather than a message prefix, and a deliberately emptied ENROLLED set turns the gate red; `_HOST_DEPENDENT_PATHS` gains a written per-entry rationale and a monotonicity note stating the second/third-entry escalation, or is derived; `OPERATIONS.md` states explicitly that the generated local credentials must not survive into any shared environment; `docs/others/tech-audit.md` is updated to reflect each discharge.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/schema/state_schema.py`, `scripts/test_isolation_conformance.sh`, `quickscale_core/tests/test_generator/test_generator.py`, `quickscale_core/.../templates/OPERATIONS.md.j2`, `docs/others/tech-audit.md`.

- [ ] **SA166 — Require a testimony trail for behavioural commits.** `Band C · Tier 3 · W2 · merge #24 · deps: SA167c`
  Closes the tech audit's carried tooling gap *"no gate requires a changelog/ticket trail for behavioural commits"*. `d3d4c633` and `d4b0e834` were both titled "v0.87.0: QuickScale 0.87.0" while in fact changing hosted and publish provisioning, and `d3d4c633` left a repository conformance test red (TA66/SA158). Both audits independently flagged the same shape: a release-shaped message carrying a CI-topology change, read closely only because the arch audit's delta-classification step treats unlabeled-behavioural commits as read-at-full-depth. Recorded in the audit as maintainer-process risk rather than a source finding, which is why this is Tier 3 and remains behind the completed gate-layer prerequisite.
  **Acceptance:** a change touching `.github/workflows/`, `scripts/gate_registry.json`, or the provisioning stations requires either a roadmap ticket reference or a `CHANGELOG.md` entry, enforced mechanically rather than by convention; the check is registered in `scripts/gate_registry.json` and passes `scripts/check_gate_parity.py`; the gate fails on a deliberately introduced untitled workflow change, reverted before merge; false-positive cost is measured on the existing history and the rule is narrowed until it is quiet on legitimate release commits; the tooling gap is retired from the tech audit.
  **Shared conflict surface:** `scripts/gate_registry.json`, `Makefile`, CI workflow, `docs/others/tech-audit.md`.

### Audit items deliberately **not** ticketed

Recorded so the absence is a decision rather than an oversight.

| Item | Source | Why no ticket |
|---|---|---|
| Finding 7 `generated-file-ownership-unmodeled` | arch, deferred | Held by the standing **"neither"** rule under [Standing rules carried from closed decisions](#standing-rules-carried-from-closed-decisions). Trigger: a third generated-project consumer, public updater, emitted-file expansion, or second theme. Related weakness is tracked in SA152. |
| Finding 2 `deletion-invariants-per-boundary-reimplementation` | arch, deferred | Held by the same rule. Trigger: `teams`, a GDPR erasure command, bulk-admin deletion, or a second deletion boundary. Design together with Finding 4 at `teams` kickoff. |
| Finding 4 `org-model-universe-hand-enumerated` | arch, deferred | Held by the same rule. Trigger: `teams` adds a tenant model, or a module adds a `PROTECT`/non-deferrable dependency among purge-owned rows. SA151 is noted as a natural derivation moment for the next audit pass. |
| Tooling gaps — dependency-vulnerability scanner, security static analysis | tech | **Tooling gaps closed by SA123's implemented and accepted Trivy/Bandit gates; completion evidence is archived in [CHANGELOG.md](../../CHANGELOG.md).** |
| Watch items recorded as deliberate | tech *Notes* | Integration-branch CI, generator lock-generation policy, the DB-free healthcheck, CRM cross-tenant count fallbacks, and rename-atomic-but-not-durable state writes are each argued and accepted in the audit; re-examine only on the triggers stated there. |
| Tooling gap — CSRF helper test | tech | An acceptance criterion inside **SA160** (merge #20), not a separate item. |
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
