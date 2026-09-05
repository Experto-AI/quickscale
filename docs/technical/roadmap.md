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
- Merge-back follows the [handoff checklist](#handoff-checklist--applies-to-all-three-lanes). An explicitly authorized partial checkpoint may merge only as retained delivery; it stays open and clears no branch-state gate.
- Every handoff declares its file allowlist, commands, expected exits/artifacts, rollback, and focused validation. Scope findings are ticketed rather than fixed in place.
- Leave `make quality` no worse than found. Do not raise a complexity ceiling or reintroduce file-line ceilings. The current baseline has zero warning regressions, zero critical regressions, and monotonicity passes.
- Shared closeout conflict surfaces are `CHANGELOG.md`, `docs/technical/roadmap.md`, `docs/technical/v88_ticket_context.md` when a ticket's concepts change, and `docs/technical/decisions.md` when policy changes. `docs/index.md` joins when its current ledger summary changes; any other current same-fact consumer joins when the ticket changes a scheduling, dependency, queue-count, or ownership claim it makes. An audit document joins when a ticket changes or closes a live finding or when its current queue/status prose changes.
- A roadmap edit that changes a W1/W2/W3 state block must re-run `quickscale_core/tests/test_v88_ticket_context_consistency.py` in the same change, and two state blocks must never share a state header — a duplicate header makes the test's anchors bind to the wrong block.
- PostgreSQL/Docker work is serialized across worktrees. **W3 holds the exclusive PostgreSQL/Docker slot** and takes scheduling priority whenever one of its legs is active. Which commands actually claim the standing service is settled in [PostgreSQL routing](#postgresql-routing--who-actually-claims-the-standing-service).
- A ticket whose deliverable is Git ref state cannot be delegated to a file-editing worker. Route it to a maintainer session with ref authority and push credentials.
- **A run killed by a cutoff returns no exit code and is not evidence** — neither of green nor of
  red. One recorded acceptance stall was caused by exactly this, and the gate underneath turned out
  to be red. `make test` and `make quality` must therefore be launched detached under `setsid`,
  with the exit code written to a file and the file polled. `make check` no longer needs it:
  measured at **184 s green** on `v88` after the `check-gate-suites` parallelisation, it fits
  inside a single foreground call.
- **Detach with `setsid`, never `nohup` — `nohup` manufactures false reds in signal tests.** `nohup`
  sets SIGHUP to `SIG_IGN`, and that disposition is inherited by every descendant, so a test that
  signals its own child with SIGHUP never sees it. Measured 2026-09-01 on `v88` at `3aa0c67f`:
  `scripts/test_provision_ci_postgres.py` returns **34 passed / 1 failed** under `nohup` —
  `test_pre_readiness_signal_reaps_child_group_and_preserves_status[1-HUP-129]` times out
  deterministically, 3 of 3 reruns — and **35 passed** in the foreground or under `setsid`. The
  INT and TERM parametrizations pass either way, which is the tell. Treat a HUP-only failure as a
  harness artifact and re-measure before attributing it to a ticket.
- **A gate that is red on the integration branch is attributed to exactly one ticket, and is never
  deselected.** Test exclusion via `PYTEST_ADDOPTS`, `--deselect`, or a Makefile/CI edit is not a
  scheduling tool: it removes the oracle for the defect the owning ticket exists to fix. Name the
  owner, let the other lanes run unexcluded and treat their evidence as provisional, and complete
  no other ticket merge until the owner is green. An authorized partial checkpoint from the owning
  ticket does not clear the gate. The 2026-08-28 interim known-red protocol is retired for exactly
  this reason and must not be revived.
- **A gate budget must be sized against the same command that will be run.** `pytest scripts/` costs
  92 s parallel (`check-gate-suites`) and 302 s serial — the same 1319 tests, 3.3× apart. One recorded
  blocker was a serial run killed 1.8 s short of green under a budget copied from the parallel figure.
  Quote every timing with its parallelism, and prefer a detached run with a generous budget over a
  foreground retry.
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
| **A — Restore enforcement** | Gate layer reports green while not running, or runs red on HEAD. | **Empty — SA176 is archived green and `make ci` passes.** Provisioning is separately clean: no provisioning repair is owed and no provisioning gate is red. Re-verify with `poetry run pytest scripts/test_provision_ci_postgres.py -q -o addopts= --no-cov` in the foreground. |
| **B — Release work on the critical path** | The serialized release-verdict chain. | **Empty — SA167c is archived green.** |
| **C — Bounded independent fixes** | No dependants, small blast radius; absorbed as slack filler. | SA160, SA161, SA165, SA172, SA174, SA175, SA178, SA179 |

### Dependency graph and critical path

```text
v88 — three worktrees, eight open merge positions carrying eight open ticket entries, one merge queue

W2 (gates & declared wiring)          band-C tail
  SA178                        #34
  SA174 ─► SA175              #31, #32

W1 (module wiring + generated-output fixes)
  SA165 ─┬─► SA179             #22, #35
         └─► SA161 ─► SA160    #19, #20

W3 (service lifecycle — exclusive PostgreSQL/Docker slot)
  (empty — the slot remains reserved for future Docker-backed work)
```

**Position numbers are identifiers, not run order.** W2's remaining order is #34, then the
#31/#32 tail. **SA174 and SA175 remain W2 tail by current lane ordering; the band-C displacement
rule imposes no present constraint because no runnable band-B leg remains.**

SA167c verdict is green and archived, as are SA166's testimony gate and SA176's release-gate
correction. W2 carries the three-position band-C queue headed by SA178, with SA174 and SA175 as its
tail. W3 holds the exclusive slot and takes scheduling priority while its Docker-backed leg is
active; its one position is a *queue* of one, and SA172 keeps `deps: none`. All eight positions are
band-C work.
**No open ticket remains on the release critical path; `make ci` is green on the corrected tree.**

**No cross-worktree ticket blocker or open release-gate blocker remains.** One cross-worktree *shared file* does,
made one-directional by merge order: `scripts/test_isolation_conformance.sh` (SA135's merged
partial wrote it; SA165's retained product edit is awaiting closeout, and it is now that file's only
open owner).
`.../settings/production.py.j2` has one open owner, SA161 on W1.

**No open ticket may edit `quickscale_core/contracts/` or `quickscale_core/manifest/`** — the
retained presence-contract implementation owns that settled behaviour, and the cross-lane hazard is
the [standing rule](#standing-rules-carried-from-closed-decisions). The manifest-reading
`entry_point.py`, the fail-hard `QUICKSCALE_LOCAL_WHEELHOUSE` version-spec seam, the regenerated
migration baseline, and `scripts/provision_ci_postgres.sh` are likewise settled tree state that open
tickets build on rather than re-open.

### Track rebalance — settled lane assignment

Lanes are **W1 4 · W2 3 · W3 1**, and every open ticket carries a track. **No move is proposed**:
the remaining queues are lane-ordered band-C work, so no relocation can shorten the release path.

**Three tickets were split on 2026-09-05, in lane, without relocation.** Each carried a small real
defect bundled with documentation or evidence work whose cost dominated the reviewed unit, and in
SA165's case whose file set made the ticket's own evidence self-invalidating. The splits are
**SA164 → SA164 + SA178** (both W2), **SA165 → SA165 + SA179** (both W1), and **SA172 → SA172 +
SA177** (SA177 leaves v88 for the post-v88 backlog because it is the only part needing a live
PostgreSQL beyond the two-line fix). No child changes lane, so no conflict surface gains a second
worktree; splitting raises the ticket count without adding work, and lets each lane's real fix reach
a checked box without waiting on its documentation half.

**SA174 (#31) and SA175 (#32) sit on W2 by a confirmed decision (2026-09-04), not a provisional
one.** The assignment keeps `docs/others/arch-audit.md` **single-lane and one-directional** — its
remaining owners SA174, SA175, and SA178 are all W2, running #34 → #31 → #32 — and
leaves W1 as one coherent chain headed by #22, with #35 and the #19 ─► #20 pair behind it. The same
single-lane requirement is what forced SA178 to stay on W2. No code file carries a second
lane. The assignment stands on that permanent conflict-surface gain rather than on the idle-lane
condition that produced it; the reasoning is archived in [CHANGELOG.md](../../CHANGELOG.md).
**SA174 and SA175 remain W2 tail by current lane ordering; the band-C displacement rule imposes no
present constraint because no runnable band-B leg remains.**

Two structural constraints outlive the decision and bind any future move: **`scripts/gate_registry.json`
and `quickscale_modules/*/module.yml` never cross worktrees**, which pins the gate tickets to W2; and
**W1's `sa90_emission_manifests.json` rebaseline is one ordered pair** (#19 → #20) that may not be
split. Future work requiring the exclusive PostgreSQL/Docker slot remains pinned to W3.

### Lane state

Lane state is the live result of remeasurement, not persisted planner data. The durable scheduling
state is defined by the open-ticket metadata, dependency graph, next actions, and readiness table in
this document. Before acting, re-measure each worktree against the current integration branch:

```bash
for w in wt-track1 wt-track2 wt-track3; do echo -n "$w: "; git rev-list --left-right --count v88...$w; done
```

**Read that output as `behind ahead`** — the left column counts commits on `v88` and not on the
worktree, the right column the reverse. Inspect working-tree status separately. Do not add measured
tips, divergence counts, or clean/dirty claims to this planner; those are transient closeout evidence.

### PostgreSQL routing — who actually claims the standing service

The standing PostgreSQL 18 container (`pg18-af10`) publishes `localhost:5432` and holds the twelve
shared `test_quickscale_*` databases. **Helper-routed local profiles do not use them.** Verified
against `scripts/provision_ci_postgres.sh`: `run --profile {restricted,isolation,bypassrls}` creates a
private ephemeral `postgres:18` container, reads its dynamic loopback port, provisions scoped databases
and the profile role, exports `QS_<MODULE>_DB_{NAME,USER,HOST,PORT}` for the child, and removes the
owned container on exit. Only commands deliberately left on `localhost:5432` contend for the standing
service. **W1's bare `make test` and W2's module acceptance gate both route through private profiles
and claim nothing.** W3 retains priority for its Docker-backed legs; the strict no-listener window is
complete and the standing state was restored exactly.

### Next action per lane

- **W2 — start SA178 (#34).** SA164's fail-loud SA92 guardrail repair is complete and archived;
  SA178 now heads the lane with the watchlist restatement, while SA174 and SA175 remain the band-C
  tail. W2 claims no standing service.
- **W1 — retain SA165 (#22).** SA165-R1 independent review passed over the historical six-file
  candidate, but the checkpoint recording that result changed the roadmap blob and invalidated the
  exact-byte binding for further action. One-run authority remains granted and unspent as `EV-8`.
  The focused status/test reconciliation is green;
  the next action is a fresh terminal SA165-R1 over the current bytes. Only a later root run may
  then enter `FROZEN-CHECK` and the single authorized final-candidate verdict. The ticket body below
  holds the full state, evidence bindings, and pending order. SA165's candidate is now product-only;
  SA179 (#35) carries the documentation reconciliation that used to sit inside it.
- **W3 — idle.** SA176's B105 correction release-accepted retained SA171 lock work, and SA172's
  PostgreSQL-backed correction is now complete and archived. The lane has no open v88 ticket; its
  exclusive PostgreSQL/Docker slot remains reserved for future work that requires it. SA177's
  predicate-text conformance assertion remains post-v88 and unscheduled.

### Track readiness — the three states

A lane is **truly green** only when all three are yes. *Can start* = the next action is executable today.
*Can finish* = the ticket can reach a checked box using only work on its own lane. *Can merge* =
merge-back is not order-gated behind another lane.

| Lane | Head | Can start | Can finish | Can merge | On the critical path |
|---|---|---|---|---|---|
| **W2** | SA178 (#34) | **yes** — `deps: none` and its work is W2-owned | **yes** — no upstream ticket remains | **yes** — nothing is ordered ahead of #34 | no |
| **W1** | SA165 (#22) | **yes** — `deps: none`; the focused status/test reconciliation is green, and the next action is a fresh terminal SA165-R1 before entering the reviewed remainder | **no** — the current bytes lack a fresh SA165-R1 and the `EV-8`-authorized verdict has not returned green | **yes after fresh review and a green verdict** — no cross-lane blocker remains | no |
| **W3** | — *(empty)* | n/a — no open v88 ticket | n/a — no open v88 ticket | n/a — no merge pending | no |

**W2 is truly green; W3 is idle; W1 can start but cannot finish until a fresh SA165-R1 is green and
SA165's `EV-8`-authorized final-candidate verdict is green.** **No open ticket remains on the
release critical path**, so W2's green head is real, useful work that is nonetheless filler with
respect to the release date. W1's *cannot finish* is empirical, not a decision — the
authorized verdict either returns green or it does not.

**Behind the heads, the split changed one answer.** SA179 (#35, W1) can start —
its documentation work is executable today — but cannot finish, because retiring the four tech-audit
notes requires SA165's verdict to have covered the product bytes first. That is a hard dependency on
upstream work, not a decision. SA177 is post-v88 and is not scheduled here at all.

### Maintainer decisions

**No maintainer decision is open anywhere in the v88 queue.** The last one was granted on
2026-09-05 as **`EV-8`**: exactly one replacement `QS_E2E_INTEGRATION_REF=v88 make ci-e2e` verdict
over SA165's settled Phase D candidate, frozen at the moment `wt-track1` syncs. `EV-8`
authorizes that one verdict and nothing else — not a second run, not redoing accepted A-C (which
stay bound to `EV-2`), and not reusing the earlier stale-but-green run as acceptance. A red or
unreturned result requires a repair ticket and then fresh authority.

**Settled 2026-09-05 by the split direction — `EV-8` is re-scoped to SA165's product candidate.**
The grant originally named a six-file candidate that included `docs/technical/roadmap.md`, which is
what made recording a passing review invalidate that review: the act of writing the result edited a
bound blob. Splitting the documentation half out as SA179 removes the roadmap, `docs/index.md`,
`docs/technical/v88_ticket_context.md`, and the consistency test from the frozen set, leaving the
verdict bound to the product bytes it is actually evidence about. This narrows `EV-8`'s scope and
grants nothing new: still exactly one `QS_E2E_INTEGRATION_REF=v88 make ci-e2e` verdict, still no
retry, still no reuse of the stale run.

**Confirmed 2026-09-05 — SA165's release verdict stays a v88 gate**, rather than being deferred
past the release with SA161 promoted to W1's head. Deferral would carry four open tech-audit notes
into the next release and break the rule that a ticket's evidence must cover its own settled bytes
— the rule that caught the stale-but-green run here. Settled and not reopened.

Every other decision is settled and archived with its full reasoning in
[CHANGELOG.md](../../CHANGELOG.md) — SA167c's Phase-F authority (consumed successfully as `EV-7`),
the confirmed SA174/SA175 lane assignment to W2, and the five decisions of 2026-08-31 (the
`sqlparse` suppressions, `quickscale_devtools` publication, the consistency test's canary reduction,
the band-C displacement rule, and the permanence of the privileged-command set). Only their standing
consequences live on here: in [Standing rules](#standing-rules-carried-from-closed-decisions), in the
shrunk SA174 and SA175 ticket bodies, and in the
[deliberately-not-ticketed table](#audit-items-deliberately-not-ticketed). D3 and the
placeholder-declaration policy remain settled and are not reopened here.

### Handoff checklist — applies to all three lanes

Before any ticket work, measure each lane against current `v88`; when a worktree lags:

1. **Sync.** Merge `v88` into the worktree and resolve there, never on the integration branch.
   Expect a conflict in `docs/technical/roadmap.md`; keep this file's structure.
2. **Re-run the consistency test in the same change** if a W1/W2/W3 state block moved:
   `poetry run pytest quickscale_core/tests/test_v88_ticket_context_consistency.py -q -o addopts= --no-cov`.
3. **Route database-backed gates through their owned profiles**, per
   [PostgreSQL routing](#postgresql-routing--who-actually-claims-the-standing-service). `make test`
   delegates its integration leg to `make test-integration`; that target, `make test-bypassrls`,
   and `make isolation-conformance` all take helper profiles and claim no standing service.
4. **Announce core-package edits** under `quickscale_core/contracts/` or
   `quickscale_core/manifest/` in the merge queue — see the standing cross-lane rule below.
5. **Reproduce the ticket's measured starting state** before changing anything. Every open ticket
   below states one.
6. **Merge back** by re-running the ticket's own verification on the exact reviewed tip, then
   merging that tip.

#### Standing rules carried from closed decisions

- **W3 holds the exclusive PostgreSQL/Docker slot.** W3 may stop the container `pg18-af10` for a
  strict-acceptance window and **must restart it afterwards** (`docker start pg18-af10`); the
  container must not be removed, its volume must not be pruned, and the twelve `test_quickscale_*`
  databases plus `quickscale_test_role` ownership must be restored as standing state after the
  window. Helper-routed W1 and W2 database gates do not consume that standing state: each local
  profile owns disjoint, dynamically scoped databases and its own validated role.
- **`quickscale_devtools` is maintainer-internal and will not be published** (settled 2026-08-31; archived in
  [CHANGELOG.md](../../CHANGELOG.md)). Its absence from the publish `PACKAGES` list is a decision, not a default; adding it
  there promotes `generated-file-ownership-unmodeled` to the `now` horizon and is a scope finding
  requiring its own ticket. SA175 (#32) may not widen beyond its single assertion.
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
- **SA123's coupled-test authority is closed;** its provisioning-literal obligation was discharged
  by the closed SA163.
- **Module presence is a three-state fact** (D3, 2026-08-28). Discovery reports ABSENT / ACTIVE /
  INCOMPLETE; consumers own their policy; the subset-validity rule has one implementation; nothing
  classifies module presence by string-matching an exception message. Binding on every lane —
  see [decisions.md](decisions.md#module-presence-states).
- **`quickscale_core/contracts/` and `quickscale_core/manifest/` are cross-lane surfaces.** Every
  lane reads them, so a behavioural change there can turn another lane red without sharing a file.
  No open ticket owns those settled surfaces; any exceptional touch must be announced in the merge
  queue.
- **Band-C filler must not displace a *runnable* band-B leg** (amended and settled 2026-08-31). A
  band-B leg halted on an open decision does not hold its lane idle; the intent is no queue-jumping
  ahead of work that could actually proceed. It is what keeps a
  decision-halted lane from idling.

### Merge order

One queue, one reviewed child at a time per worktree; merge-back follows the
[handoff checklist](#handoff-checklist--applies-to-all-three-lanes).

| # | Ticket | Band | Tier | Worktree | Merges after | Service slot |
|---|---|---|---|---|---|---|
| 19 | **SA161** | C | 3 | W1 | SA165 | no |
| 20 | **SA160** | C | 2 | W1 | SA161 | no |
| 22 | **SA165** | C | 3 | W1 | — | no |
| 29 | **SA172** | C | 3 | W3 | — | no |
| 31 | **SA174** | C | 3 | W2 | — *(band-C tail)* | no |
| 32 | **SA175** | C | 3 | W2 | SA174 *(lane only)* | no |
| 34 | **SA178** | C | 3 | W2 | — | no |
| 35 | **SA179** | C | 3 | W1 | SA165 *(content — verdict evidence)* | no |

Entries carry their declared queue or content dependencies, subject to fresh branch remeasurement
before execution.

Positions #1, #2, #3, #4, #5, #6, #6b, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #21, #23, #24, #25, #26, #27, #28, #33 are **retired and not
reused**; their tickets are closed and archived in [CHANGELOG.md](../../CHANGELOG.md). Gaps carry no meaning.

The per-lane heads are **#34 (W2), #22 (W1), and #29 (W3)**. SA167c's #21 release verdict,
SA166's #24 testimony gate, and SA176's #33 release-gate correction are complete and archived. No
open head is on the release critical path.

Most "Merges after" edges are lane ordering — a queue position, clearable by the upstream work **or
by a maintainer reordering the lane**. One is a **hard content dependency** that no reorder clears:
**SA160 after SA161** (shared emission-parity rebaseline of `sa90_emission_manifests.json`;
the pair must not be split, so the run is ordered #19, #20). **SA179 after SA165** is the second hard content dependency, added by the
2026-09-05 split: SA179 retires the four tech-audit notes, and a note may only be retired once a
verdict has covered the product bytes that discharge it. Band-C positions (19, 20, 22, 29, 31,
32, 34, 35) are *earliest-eligible*, not
commitments, and may slip past the release. **SA174 (#31) and SA175 (#32) are W2 tail work**:
neither has a content dependency and neither needs an exclusive slot.

### Shared conflict surfaces

Standing surface for every ticket: `CHANGELOG.md`, `docs/technical/roadmap.md`, and
`docs/technical/v88_ticket_context.md` when the ticket's concept notes change.

| Ticket | Additional shared surface | Why |
|---|---|---|
| SA160, SA161 | generator templates + **SA90 emission-parity fixture**, `docs/others/tech-audit.md` | emitted output changes |
| SA178 | `scripts/gate_registry.json`, `scripts/check_gate_parity.py`, `scripts/test_gate_parity.py`, `docs/others/arch-audit.md` | **split from SA164 2026-09-05**; watchlist restatement and the `trigger_inputs` naming correction; **W2** — the registry never crosses worktrees |
| SA165 | `quickscale_core/.../state_schema.py`, `scripts/test_isolation_conformance.sh`, `quickscale_core/tests/test_generator/test_generator.py`, `OPERATIONS.md.j2` | retained product discharge; final-candidate release verdict pending on W1. **Documentation surfaces moved to SA179 2026-09-05**, which is what keeps the frozen candidate free of the files that record its own review |
| SA179 | `docs/others/tech-audit.md`, `docs/index.md`, `docs/technical/v88_ticket_context.md`, `quickscale_core/tests/test_v88_ticket_context_consistency.py` | **split from SA165 2026-09-05**; audit-note retirement and status reconciliation; **W1** — no code file, and its own edits cannot invalidate a product verdict |
| SA174 | `quickscale_modules/orgs/.../apps.py`, `docs/others/arch-audit.md` | **shrunk 2026-08-31** to correcting the false SSOT comment and demoting the finding; no emitted bytes, no generator surface, no emission fixture |
| SA175 | `quickscale_cli/tests/test_beta_migration_ownership_conformance.py`, `quickscale_devtools/.../beta_migration.py`, `docs/others/arch-audit.md` | disposition-coherence assertion for the launcher↔settings contract; **W2** — no other open ticket touches either file |

Surfaces needing an explicit ordering note beyond the table:

- `scripts/gate_registry.json` — SA178 is its remaining owner after the 2026-09-05 split; the
  surface never crosses worktrees, which is why SA178 could only be split within W2.
- `quickscale_core/contracts/` and `quickscale_core/manifest/` — settled cross-lane surfaces shared
  by *behaviour* rather than filename; see the standing rule above and the `203fcd61` precedent.
- `scripts/test_gate_parity.py` — SA178 owns any update required by its gate-registry adjudication.
  The `describe --format json` provisioning binding, the regenerated 24-entry publish oracle, and
  SA123's settled hosted-job, `needs`-edge, run-value, publish/E2E-path, and generator expectations
  are settled tree state and must be preserved by anything that touches the file.
- `.github/workflows/ci.yml` and `scripts/provision_ci_postgres.sh` have **no open owner**, and no
  ticket may reopen the provisioning stations. A lane seeing the provisioning script's
  immediate-child status/cleanup path red is behind current `v88`, not looking at an open defect.
- `.../settings/production.py.j2` — SA161 (#19, W1) is the only open owner. SA164 and position #25
  are archived, so this file carries no cross-lane ordering caution.
- `scripts/test_isolation_conformance.sh` — SA163's merged edit is settled bytes, and SA165's
  retained identity-based skip narrowing is now its **only** open owner. The 2026-09-05 split moved
  SA172's policy-text assertion to post-v88 SA177, so this file no longer crosses worktrees and
  carries no cross-lane ordering caution while SA177 stays unscheduled.
- `sa90_emission_manifests.json` — SA161 then SA160, a pair since SA174 left the run. Each rebaseline appends its own
  `baseline_evidence` entry with per-file rationale; every prior entry must be preserved.
- `scripts/test_e2e.sh` has no open owner after SA170's accepted closeout. Preserve its settled
  exact-scope cleanup contract.

`docs/others/arch-audit.md` is on three surfaces — **SA174** (demotes
`privileged-command-set-multi-owner` from rank 1 to the watchlist, without closing
it), **SA175** (records rank-2's first step as discharged
without closing the finding), and **SA178** (restates
the watchlist and its triggers) — and **all three are W2**, so the file stays single-lane and
one-directional under the runnable order #34 → #31 → #32. Keeping SA178 in W2 was the binding
constraint on that split: moving it would have put this file on two worktrees. The rank-3 and rank-4
findings (`deletion-invariants-per-boundary-reimplementation`, `org-model-universe-hand-enumerated`)
remain untouched per the standing "neither" rule, as does the **substance** of rank-2
(`generated-file-ownership-unmodeled`) — SA175 takes only the bounded first step the audit itself
marks as trigger-independent.

**Closeout conflict surface.** Every ticket writes `CHANGELOG.md`, this file, and
`docs/technical/v88_ticket_context.md` at closeout. `docs/index.md` and any other current same-fact
consumer join when the closeout changes a summarized count, status, dependency, schedule, or owner;
`docs/others/tech-audit.md` is shared by
SA160, SA161, SA172, and SA179 — SA165's own tech-audit edits moved to SA179 in the 2026-09-05
split — and `docs/others/arch-audit.md` by SA174, SA175, and SA178, all three on W2. That is
by design and is discharged by the handoff checklist. No lane assignment above puts a *code* file on
two lanes.

---

## Backlog

One list. Each ticket carries its band, assigned worktree, merge position, and acceptance
criteria; the merge-order table above is the authority for scope, worktrees, and sequencing, and
conceptual background lives in [v88_ticket_context.md](v88_ticket_context.md).

Every ticket below is opened from a live finding in [arch-audit.md](../others/arch-audit.md) or
[tech-audit.md](../others/tech-audit.md), both at audit snapshot **2026-08-28**. Those documents
remain the SSOT for finding detail, evidence, and refutation; this section carries scope only. A
ticket that closes or changes a live finding takes its audit document onto its shared conflict
surface.

- [ ] **SA160 — Share one correct CSRF-token helper in the React theme.** `Band C · Tier 2 · W1 · merge #20 · deps: SA161 (emission-parity ordering)`
  Closes tech-audit **TA67** (`spa-csrf-token-duplicate-cookie`, S3) — the only finding in deployment reality #3, the internet-facing generated project. `themes/showcase_react/src/hooks/useApi.ts:20-28` and `src/components/forms/FormRenderer.tsx:206-211` carry the same eleven lines: the parser splits `document.cookie` on `"; csrftoken="` and accepts the result **only when it yields exactly two parts**. Two `csrftoken` cookies yield three, so `getCsrfToken()` returns `''`, `buildRequestHeaders` (`:89-94`) skips `X-CSRFToken`, and Django rejects every POST/PUT/PATCH/DELETE with 403. The triggering state is ordinary: an `app.example.com` deployment alongside a `.example.com` cookie, the outcome of setting or changing `CSRF_COOKIE_DOMAIN`, of a sibling Django app on another subdomain, or of a stale apex-scoped cookie. GETs keep working, so the app looks alive and merely refuses to save, and no error names the cause. Fails closed — availability, not a security hole. There is no shared CSRF helper, no fetch interceptor, and no template-injected token, so no layer-up guard exists.
  **Acceptance:** one shared helper in `src/lib/` iterates cookies rather than counting split segments — splitting on `'; '`, matching the name exactly, and `decodeURIComponent`-ing the value, per Django's own documented `getCookie` — and both call sites import it with no third variant remaining; a `vitest` table test covers `'csrftoken=A; csrftoken=B'`, `'sessionid=x; csrftoken=A'`, `'csrftoken=A'`, and `''`, with the first three returning a non-empty token; the tech-audit finding is retired.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/`, generator emission parity baselines, `docs/others/tech-audit.md`.

- [ ] **SA161 — Remove the dead `get_client_ip` definitions from generated settings.** `Band C · Tier 3 · W1 · merge #19 · deps: SA165 (worktree ordering)`
  Closes tech-audit **TA68** (`generated-settings-dead-client-ip`, S4). `templates/project_name/settings/base.py.j2:61` and `settings/production.py.j2:123` both define a module-level `get_client_ip(request)`, and the production copy rebinds it under a comment claiming the rebind exists "so that production defaults … are actually in effect at request time". Neither is reachable: Django's `Settings` copies only **uppercase** names off the settings module, so `django.conf.settings.get_client_ip` does not exist, and grep across all templates returns only the two definitions. The live implementation is `quickscale_modules_orgs.current_org.get_client_ip`, which reads the uppercase `USE_X_FORWARDED_FOR` / `TRUSTED_PROXY_COUNT` settings dynamically and is correct.
  **Acceptance:** both definitions are deleted — dead code that no caller reaches is removed rather than annotated; the uppercase settings and the `REST_FRAMEWORK["NUM_PROXIES"]` recomputation are retained unchanged; the misleading behavioural comment at `production.py.j2:119-122` is removed either way; a generated project boots and proxy-aware client-IP resolution is unchanged, asserted by a test; emission parity is rebaselined with rationale; the tech-audit finding is retired.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/`, emission parity baselines, `docs/others/tech-audit.md`.

- [ ] **SA165 — Discharge the tech-audit watch items that carry an action.** `Band C · Tier 3 · W1 · merge #22 · deps: none`
  Four action-bearing notes are implemented in retained A-C product object
  `573a57a34301e6a91971a7845095bd913bebd5e1`: state consolidation fails hard on corrupt and
  non-mapping YAML roots without changing the file; isolation-skip authorization is bound to the two
  intended test identities with a red negative control; `_HOST_DEPENDENT_PATHS` records its `.env`
  rationale and escalation rule; and generated `OPERATIONS.md` warns that predictable local
  credentials must not survive into shared environments. Focused A-C evidence and the retained-only
  integration are archived in [CHANGELOG.md](../../CHANGELOG.md); do not redo those phases.

  **State (measured 2026-09-05): retained Phase D candidate; historical SA165-R1 passed; current
  candidate reconciled and awaiting fresh review; final-candidate release verdict outstanding.**
  Independent read-only review accepted the complete six-file patch from
  `b23eb1fd47114dc9f176cd930ee35468f823e4cf` to `f3f29d915f5971c8f47e558a82c292ccfc86add0` with no
  blocking finding, but the checkpoint recording that result changed `docs/technical/roadmap.md` —
  one of the six bound blobs — so that review is historical evidence and authorizes neither
  `FROZEN-CHECK` nor `EV-8` against the current bytes. The retained A-C product object is unchanged.
  The single prior SA165 release run predates the settled candidate, must not be rebound, and closes
  neither SA165 nor its four audit notes. The pre-R1 reconciliation of the current same-fact
  consumers and of the executable consistency contract is complete, with no assertion weakened, and
  its focused suite is green; that measurement trail is archived in
  [CHANGELOG.md](../../CHANGELOG.md). `EV-8` remains unspent. Lane state is remeasured at action
  time rather than persisted here.

  **Candidate narrowed by the 2026-09-05 split.** The frozen set is now the retained product object
  `573a57a34301e6a91971a7845095bd913bebd5e1` as integrated, and nothing else. `CHANGELOG.md`,
  `docs/index.md`, `docs/others/tech-audit.md`, `docs/technical/roadmap.md`,
  `docs/technical/v88_ticket_context.md`, and
  `quickscale_core/tests/test_v88_ticket_context_consistency.py` left the bound set and belong to
  **SA179 (#35, W1)**. That is the whole point of the split: those six files are where a review
  result gets *recorded*, so binding them made recording a pass invalidate the pass. Recording an
  SA165 result no longer touches a bound blob.

  **Pending, in order.** (1) Obtain a fresh terminal SA165-R1 over the narrowed product
  candidate. (2) In a later root run,
  revalidate the fresh review binding and execute `FROZEN-CHECK`. (3) Spend **`EV-8`** — the single
  replacement `QS_E2E_INTEGRATION_REF=v88 make ci-e2e` verdict granted 2026-09-05 — recording it as
  launched before dispatching `EV8-CLOSEOUT`, and retain exact cleanup/provenance evidence. A green
  verdict permits completion-grade convergence, patch-backed terminal attestation, exact-tip
  integration, audit-note retirement, and #22 retirement. A red, unreturned, or undispatched
  verdict keeps this checkpoint open and requires a repair ticket plus fresh authority; `EV-8`
  covers no second run and no retry. Retiring the four tech-audit notes is **not** this ticket's
  step — a green verdict is the evidence that permits it, and SA179 performs it.

  **Constraints on the remainder.** Reviewed plan authority `EV-6` governs `FROZEN-CHECK` and
  `EV8-CLOSEOUT`, but its fresh-R1 entry precondition is unmet, so neither phase is dispatchable and
  the next root run must terminate at the fresh SA165-R1. Retain product object
  `573a57a34301e6a91971a7845095bd913bebd5e1`; do not treat historical reviewed tip
  `f3f29d915f5971c8f47e558a82c292ccfc86add0` as the current candidate. SA167d's completion-grade
  closeout stays archived as a conditional post-integration candidate. Preserve historical SA170 and
  SA167c/SA167d evidence, do not reopen A-C product files, and do not alter SA177's post-v88
  ownership of the isolation script.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/schema/state_schema.py`, `scripts/test_isolation_conformance.sh`, `quickscale_core/tests/test_generator/test_generator.py`, `quickscale_core/.../templates/OPERATIONS.md.j2`, `docs/others/tech-audit.md`.

- [ ] **SA179 — Reconcile SA165's documentation and retire its four audit notes.** `Band C · Tier 3 · W1 · merge #35 · deps: SA165 (verdict evidence)`
  **Split from SA165 on 2026-09-05.** SA165's reviewed candidate used to include the six documents
  that *record* its own review, so every checkpoint writing "the review passed" edited a bound blob
  and invalidated the review it was recording. That loop cost two cycles. This ticket owns those six
  files; SA165 keeps only product bytes. Nothing about the four hardening changes moves — they are
  implemented and retained — and this ticket implements no product behaviour at all.
  **The dependency is real, not lane ordering.** Each of the four live tech-audit notes
  (`flush_empty_consolidated_sections` failing hard, the identity-bound isolation skip,
  `_HOST_DEPENDENT_PATHS` accountability, and predictable generated local credentials) is explicitly
  held open *until a release verdict covers the settled candidate*. Retiring one before SA165's
  `EV-8` verdict returns green would assert evidence that does not exist. That is why this ticket can
  start today but cannot finish on W1's own work.
  **Acceptance:** the four notes are retired in `docs/others/tech-audit.md` with the returned verdict
  named as the evidence, and no note is retired if the verdict is red or unreturned; `docs/index.md`,
  `docs/technical/roadmap.md`, and `docs/technical/v88_ticket_context.md` are reconciled to the
  post-SA165 queue in the same change; `quickscale_core/tests/test_v88_ticket_context_consistency.py`
  is updated in the same change and passes, with no assertion weakened; `#22` is retired.
  **Explicitly out of scope:** any edit under `quickscale_core/src/`, `scripts/`, or the generator
  templates. This ticket carries no code file, which is what makes its own edits incapable of
  invalidating a product verdict.
  **Shared conflict surface:** `docs/others/tech-audit.md`, `docs/index.md`, `docs/technical/v88_ticket_context.md`, `quickscale_core/tests/test_v88_ticket_context_consistency.py`.

- [ ] **SA174 — Correct the false SSOT claim on the privileged-command set.** `Band C · Tier 3 · W2 · merge #31 · deps: none · shrunk 2026-08-31 · moved to W2 2026-09-03`
  **Scope reduced 2026-08-31: the sanctioned privileged-command set is confirmed
  permanent at two commands.** With `{"migrate", "createcachetable"}` fixed, the drift this ticket
  existed to prevent cannot occur, so `privileged-command-set-multi-owner` drops from arch-audit
  **rank 1 to a watchlist item**. The consolidation plan is **archived unimplemented** in
  [CHANGELOG.md](../../CHANGELOG.md) and is reinstated only if the watchlist trigger fires.
  **The defect that remains is a false instruction, not the duplication.** The set is declared in
  four places — `templates/project_name/settings/production.py.j2:185` `_KNOWN_PRIVILEGED_COMMANDS`
  (the **validator**, selecting superuser `DATABASE_URL` vs restricted `RUNTIME_DATABASE_URL`),
  `quickscale_modules/orgs/.../apps.py:36` `_PRIVILEGED_COMMANDS` (the **guard bypass**),
  `quickscale_cli/.../development_commands.py:44` `_PRIVILEGED_DJANGO_COMMANDS` (the **producer**),
  and `templates/start.sh.j2:50,61` by inline literal — and all four currently agree. Every
  divergence direction **fails closed**: a narrower module set means the RLS guard runs and rejects
  the superuser role; a narrower template set raises `ValueError` at settings import. The tech audit
  adjudicated the behavioural question separately and recorded **no finding**. What is not safe is
  the comment above `apps.py:36`: *"Add new commands here when the generated launcher starts setting
  `QUICKSCALE_PRIVILEGED_COMMAND` to additional values"*, backed by a docstring at `:52` claiming
  `_PRIVILEGED_COMMANDS` is "the single source of truth". **Both are false and were already false
  when written** — following them yields a value the generated project's guard rejects at startup.
  Station 3 was added independently in `3523f9f8` (2026-08-18) under a `test:`-labelled message,
  which is how the claim went stale unobserved.
  **Acceptance:**
  1. The comment and docstring at `quickscale_modules/orgs/.../apps.py:34-52` state the truth: this
     set is one of four independent fail-closed declarations, it is **not** a single source of
     truth, and adding a sanctioned command requires updating all four stations — naming them.
  2. `docs/others/arch-audit.md` demotes `privileged-command-set-multi-owner` from rank 1 to the
     watchlist, records the permanence decision as the reason, and arms the trigger: **a third sanctioned
     command, or any two stations disagreeing**. The finding is not closed.
  3. No emitted bytes change. No declaration moves. The module keeps its independent fail-closed
     guard; nothing starts trusting the settings layer.
  **Verification:** `poetry run pytest quickscale_modules/orgs/tests -q -o addopts= --no-cov`;
  `make lint`, `make typecheck`; `make quality` no worse than found. **No emission-parity rebaseline
  and no generator run is required** — that is what removes this ticket from the ordered
  `sa90_emission_manifests.json` run.
  **Shared conflict surface:** `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py`, `docs/others/arch-audit.md`.

- [ ] **SA175 — Assert disposition coherence for the launcher↔settings contract.** `Band C · Tier 3 · W2 · merge #32 · deps: none · moved to W2 2026-09-03 · bounded first step only; does not widen into the deferred finding`
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
  **No content dependency remains (settled 2026-08-31).** The audit's ordering argument — consolidate
  the command set first, then reference the single declaration — was cancelled by settling the set as
  permanent, so **this ticket names its own three participating paths** and holds merge position #32
  by W2 lane ordering alone.
  **Acceptance:** the launcher↔settings contract is named once as a group of participating emitted
  paths (`settings/production.py`, `start.sh`, `Dockerfile`), named once in this ticket's own
  assertion; a conformance assertion in
  `test_beta_migration_ownership_conformance.py` fails when members of one named group are assigned
  dispositions from opposite families (donor-carried vs in-place-substituted); the assertion is
  proved by temporarily moving one member across the line, observing red for the intended reason,
  and restoring the exact bytes; the **existing** donor-wins disposition for `settings/production.py`
  is **preserved unchanged** — the audit argues it is defensible on its own terms, so this ticket
  makes the split *visible*, not different; the deferred finding stays open with its trigger intact
  and `docs/others/arch-audit.md` records the first step as discharged without closing it.
  **Shared conflict surface:** `quickscale_cli/tests/test_beta_migration_ownership_conformance.py`, `quickscale_devtools/src/quickscale_devtools/beta_migration.py`, `docs/others/arch-audit.md`.

- [ ] **SA178 — Restate the arch-audit watchlist and correct the `trigger_inputs` name.** `Band C · Tier 3 · W2 · merge #34 · deps: none · split from SA164 2026-09-05`
  **Split from SA164 on 2026-09-05** so the guardrail repair could land without waiting on
  documentation. This ticket changes no behaviour: it is a naming correction and a restatement of
  triggers. It stays on **W2** because `scripts/gate_registry.json` and `docs/others/arch-audit.md`
  never cross worktrees; moving it would have put the audit document on two lanes.
  **1. `trigger_inputs` has drifted from its name.** `check_gate_parity.py:2652-2690` uses the field
  as a bidirectional partition of `e2e.yml`'s path allowlist, not as "what changes should trigger
  this gate" — which is why `check-core-compat`'s trigger reads `quickscale_modules/backups/**`. Not
  a defect: the check it performs is real and exact. It is a correct mechanism under a name that
  lies, and it becomes load-bearing the moment a gate is ever *skipped* on the basis of the field.
  **2. The three not-fired items must survive the next pass.** A watch item's whole value is its
  written trigger; an item restated from a superseded list has lost its bet.
  **Acceptance:** `trigger_inputs` is either renamed to describe what it does, or its docstring and
  schema description record the actual semantics plus the skip-based promotion trigger; the arch
  audit's **current** watchlist is restated with triggers intact rather than the superseded
  pre-resolution list — the two hand-pinned literals minted inside the provisioning derivation
  (`provision_ci_postgres.sh:93,96`, `!= teams` and `== 12`, trigger: a thirteenth shipped module or
  `teams` graduating), the second copy of the PostgreSQL major (`provision_ci_postgres.sh:15` against
  `runtime_pins.py:30`, trigger: the DR engine's `pg_dump`/`pg_restore` major-version contract coming
  to depend on the two agreeing), and the roughly six count-pinned oracles in
  `scripts/test_gate_parity.py` (trigger: the next gate addition paying more than two oracle edits,
  or two oracles disagreeing) — each noted as **not fired**; no watchlist item is closed.
  **Verification:** `poetry run pytest scripts/test_gate_parity.py -q -o addopts= --no-cov`;
  `make check-gate-parity`; `make quality` no worse than found.
  **Shared conflict surface:** `scripts/gate_registry.json`, `scripts/check_gate_parity.py`, `scripts/test_gate_parity.py`, `docs/others/arch-audit.md`.

- [ ] **SA172 — Make `apply_force_rls`'s idempotency claim true.** `Band C · Tier 3 · W3 · merge #29 · deps: none · shrunk 2026-09-05`
  Closes tech-audit **TA72** (`force-rls-apply-idempotency-claim`, S4, opened 2026-08-28).
  `quickscale_modules/orgs/.../tenancy.py:536-546` documents `apply_force_rls` as "**Idempotent**",
  but `_FORCE_RLS_FORWARD_SQL` issues bare `CREATE POLICY` at `:510` and `:521`, and PostgreSQL has
  no `CREATE POLICY IF NOT EXISTS`. A second application against an already-enrolled table aborts
  the migration with `42710 duplicate_object`. The claim is safe today only because the one
  re-applying caller, `refresh_force_rls_policies` (`:584`), calls `revert_force_rls` first, and the
  reverse template already uses `DROP POLICY IF EXISTS`. The hazard is a future module migration
  calling the helper on the documented assurance that doing so is safe — on the repository's most
  security-critical migration helper.
  **Scope reduced 2026-09-05.** The predicate-text conformance assertion this ticket used to carry
  is the only part needing more than the two-line repair, and it is a *tooling* improvement rather
  than a fix for TA72. It moved out to post-v88 **SA177** so this ticket can reach a checked box on
  W3's slot in one short run. The tech audit's *"RLS policy assertions check existence, not predicate
  text"* tooling gap therefore **stays open** and is not claimed here.
  **Acceptance:** the forward template is prefixed with the same `DROP POLICY IF EXISTS` pair the
  reverse template already carries, making the documented contract real — the two-line fix, chosen
  over correcting the docstring because it leaves a true contract rather than a warning; a test
  asserts it by applying twice against a real table and observing success rather than
  `42710 duplicate_object`; the read/write policy
  split (`FOR ALL` tenant write plus `FOR SELECT` with the `operator_access` OR clause) is unchanged;
  **TA72** is retired.
  **Also carried here (watch items, not findings):** `refresh_force_rls_policies:596-620` derives
  table names from the Django default convention and drops misses through `to_regclass(...) IS NOT
  NULL` without warning — latent today (all 21 enrolled tables match the convention, empirically
  verified) but a silent no-op the moment an enrolled model declares a non-conventional `db_table`.
  Deriving from `apps.get_model(...)._meta.db_table`, the same source `check_tenant_model_isolation`
  already uses, closes it in the same change. This item is retained here and **not** deferred with
  SA177: it is a one-line source change, and a silent no-op in RLS enrollment is the failure mode
  this ticket exists to remove.
  **Shared conflict surface:** `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py`, `docs/others/tech-audit.md`.

### Audit items deliberately **not** ticketed

Recorded so the absence is a decision rather than an oversight.

| Item | Source | Why no ticket |
|---|---|---|
| `generated-file-ownership-unmodeled` (arch rank 2) — **substance only** | arch, deferred | Held by the standing **"neither"** rule, and by the settled decision that **`quickscale_devtools` is maintainer-internal and will not be published** (2026-08-31) — the fact that holds this finding's severity down. Trigger: a third generated-project consumer, public updater, emitted-file expansion, or second theme. Options 1 and 2 (typed disposition metadata; a versioned ownership manifest with vintage negotiation) stay behind it. Its **trigger-independent first step is ticketed as SA175 (#32)** under the carve-out in the standing rules. Related weakness tracked in SA152. |
| `deletion-invariants-per-boundary-reimplementation` (arch rank 3) | arch, deferred | Same rule. Trigger: `teams`, a GDPR erasure command, bulk-admin deletion, or a second deletion boundary. Design together with `org-model-universe-hand-enumerated` at `teams` kickoff. |
| `org-model-universe-hand-enumerated` (arch rank 4) | arch, deferred | Same rule. Trigger: `teams` adds a tenant model, or a module adds a `PROTECT`/non-deferrable dependency among purge-owned rows. |
| Watch items recorded as deliberate | tech *Notes* | Integration-branch CI, generator lock-generation policy, the DB-free healthcheck, CRM/billing cross-tenant `all_objects` count fallbacks, and rename-atomic-but-not-durable state writes are each argued and accepted in the audit; re-examine only on the triggers stated there. |
| `blog/feeds.py` double System-org resolution | tech *Notes* | Narrow trigger (a corrupt singleton row). Not promoted; re-examine if a second fail-closed feed path appears. |
| `table_has_force_rls` schema qualification | tech *Notes* | Single-schema deployments unaffected. Trigger: a schema-per-tenant option. |
| Tooling gap — CSRF helper test | tech | An acceptance criterion inside **SA160**, not a separate item. |
| Tooling gap — RLS predicate-text assertions | tech | Ticketed post-v88 as **SA177**, split out of SA172 on 2026-09-05 — so it is not untracked, only unscheduled for v88. |
| Structural smell — no `src/lib/http` seam | tech | Created by **SA160**'s shared-helper requirement; the other two smells are discharged. |
| Clean sweeps (10) | tech | Verified-clean records, not open items. |

---

## Unscheduled backlog (post-v88)

Not assigned to a v88 track. Listed here so the finding is not lost.

- [ ] **SA177 — Assert RLS policy predicate text, not just policy existence.** `Post-v88 · Tier 3 · deps: none · split from SA172 2026-09-05`
  Closes the tech audit's *"RLS policy assertions check existence, not predicate text"* tooling gap
  and its related structural smell. The isolation and conformance gates currently prove that a table
  has RLS enabled, forced, and **at least one policy row** in `pg_policies`. They do not read what
  the policy says. A table carrying a permissive `USING (true)` policy would pass every isolation
  check the repository runs, which means the read/write split that the whole tenancy model rests on
  — `FOR ALL` tenant-scoped writes plus a `FOR SELECT` policy whose `operator_access` OR clause is
  deliberately read-only — is enforced by a code comment rather than by a gate.
  **Why it left v88 (2026-09-05).** It was bundled into SA172, whose actual defect is a two-line
  template fix. The assertion needs a live PostgreSQL, an enrolled-table walk, and template-to-catalog
  text comparison for every enrolled table, and it is a tooling improvement rather than a fix for
  TA72. Bundling made a short W3 slot occupancy into a long one. Splitting it out lets the fix land
  now; the gap it closes is real and this ticket should be pulled forward if the policy templates are
  edited again.
  **Acceptance:** for each enrolled table, the stored `qual` and `with_check` text in `pg_policies`
  is compared against the rendered template for both the write policy and the operator-read policy,
  and the assertion is proved by temporarily weakening one policy's predicate, observing red for the
  intended reason, and restoring the exact bytes; the tech audit's tooling gap and structural smell
  are retired.
  **Shared conflict surface:** `scripts/test_isolation_conformance.sh`, `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py`, `docs/others/tech-audit.md`.

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
