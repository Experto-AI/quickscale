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
- Shared closeout conflict surfaces are `CHANGELOG.md`, `docs/technical/roadmap.md`, `docs/technical/v88_ticket_context.md` when a ticket's concepts change, and `docs/technical/decisions.md` when policy changes. `docs/index.md` joins when its current ledger summary changes; any other current same-fact consumer joins when the ticket changes a scheduling, dependency, queue-count, or ownership claim it makes. An audit document joins when a ticket changes or closes a live finding or when its current queue/status prose changes.
- A roadmap edit that changes a W1/W2/W3 state block must re-run `quickscale_core/tests/test_v88_ticket_context_consistency.py` in the same change, and two state blocks must never share a state header — a duplicate header makes the test's anchors bind to the wrong block.
- PostgreSQL/Docker work is serialized across worktrees. **W3 holds the exclusive PostgreSQL/Docker slot** and takes scheduling priority whenever one of its legs is active.
- **Local database-lane operating constraint:** `make test-integration`, `make test-bypassrls`,
  and `make isolation-conformance` use the owned profiles in
  `scripts/provision_ci_postgres.sh`. Local profiles allocate disjoint, dynamically scoped
  databases on loopback and validate their own role; restricted and BYPASSRLS runs do not flip
  ownership of the standing twelve databases. Commands intentionally pointed at `localhost:5432`
  still require the standing service, but helper-routed module gates take a private server instead
  of queueing for it. Hosted CI uses its separate service/lease setup.
- A ticket whose deliverable is Git ref state cannot be delegated to a file-editing worker. Route it to a maintainer session with ref authority and push credentials.
- **A run killed by a cutoff returns no exit code and is not evidence** — neither of green nor of
  red. One recorded acceptance stall was caused by exactly this, and the gate underneath turned out
  to be red. `make test` and `make quality` must therefore be launched detached (`nohup`, exit code
  written to a file, poll for the file). `make check` no longer needs it: measured at **184 s
  green** on `v88` after the `check-gate-suites` parallelisation, it fits inside a single foreground
  call.
- **Detach with `setsid`, not `nohup` — `nohup` manufactures false reds in signal tests.** `nohup`
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
| **A — Restore enforcement** | Gate layer reports green while not running, or runs red on HEAD. | **Empty.** Re-verify with `poetry run pytest scripts/test_provision_ci_postgres.py -q -o addopts= --no-cov` in the foreground (last measured **35 passed**). No provisioning repair is owed and no provisioning gate is red. |
| **B — Release work on the critical path** | The serialized release-verdict chain. | SA167c |
| **C — Bounded independent fixes** | No dependants, small blast radius; absorbed as slack filler. | SA160, SA161, SA164, SA165, SA166, SA171, SA172, SA174, SA175 |

### Dependency graph and critical path

```text
v88 — three worktrees, ten open merge positions carrying ten open ticket entries, one merge queue

W2 (gates & declared wiring)   ★ CRITICAL PATH — authority-gated head, runnable band-C filler
  SA167c ─► SA166 ─► SA164     #21, #24, #25
  SA174 · SA175                #31, #32   ← runnable while fresh F authority is pending
  (SA167c: A-E accepted; F is unaccepted and awaits fresh reviewed authority)

W1 (module wiring + generated-output fixes)
  SA165 ─► SA161 ─► SA160      #22, #19, #20

W3 (service lifecycle — exclusive PostgreSQL/Docker slot)
  SA171 ─► SA172                           #28, #29
  (SA171 is DB-free and now heads W3)
```

**Position numbers are identifiers, not run order.** Until fresh SA167c Phase-F authority is granted,
W2's runnable order is #31 then #32. Once authority is granted, band-B SA167c resumes ahead of that
filler, followed by #24 and #25.

**W2 sets the release date.** Its chain is `SA167c ─► SA166 ─► SA164`, with **#24 and #25** band-C
tail positions that may slip past the release. The release-committed critical path is therefore
**SA167c**. Its formal ticket chain is entirely inside W2. The W3-owned E2E failures are closed and
the release gate is green; the remaining Phase-F gate is fresh reviewed authority for a new verdict,
not product remediation. W3 holds the exclusive slot and takes scheduling priority while one of its
Docker-backed legs is active, but its two positions are a *queue*, not a chain. W2 is the longest
lane at five positions, but its two extra positions are runnable band-C filler moved there on
2026-09-03 and do not lengthen the release chain. W1's three positions and W3's two positions are
band-C work and set no date.

**Operationally, the release path is now W2-only.** SA170's ordered serial and concurrent campaigns
are accepted and archived in [CHANGELOG.md](../../CHANGELOG.md), so the former W3 blocker is gone.
The effective path is **fresh SA167c F authority ─► SA167c F ─► (SA166 ─► SA164, band-C tail)**.
Granting that authority is the single decision that moves the release date.

**No cross-worktree ticket or release-gate blocker remains.** One cross-worktree *shared file* does,
made one-directional by merge order: `scripts/test_isolation_conformance.sh` (SA135's merged
partial wrote it; SA165 narrows one line over those settled bytes; SA135's retired #15 precedes #22).
`.../settings/production.py.j2` has one open owner, SA161 on W1; SA164's settled scope excludes it.

**Any edit under `quickscale_core/contracts/` or `quickscale_core/manifest/` is cross-lane** — every
lane imports them, so a behavioural change there can turn another lane red without sharing a file.
Announce it in the merge queue and re-run the other lanes' focused caller suites before merging. The
`203fcd61` precedent that established this rule is archived in [CHANGELOG.md](../../CHANGELOG.md). No
open ticket may edit these packages; the retained presence-contract implementation owns the settled
behaviour.

The manifest-reading `entry_point.py`, the fail-hard `QUICKSCALE_LOCAL_WHEELHOUSE` version-spec seam,
the regenerated migration baseline, and `scripts/provision_ci_postgres.sh` are settled tree state that
open tickets build on rather than re-open. The provisioning script's immediate-child status/cleanup
path was last corrected in retained tree state and is green; **no open ticket owns it**, and a
lane that observes it red must first confirm it is synced to current `v88` before opening anything.

### Track rebalance — one move stands

Lanes are **W1 3 · W2 5 · W3 2**, and every open ticket carries a track — none lacks one. Each was
tested against the three questions: is it independent of the rest of its lane, is another lane idle,
and is it on or feeding the critical path.

**The move: SA174 (#31) and SA175 (#32) leave W1 for W2.** Both are `deps: none`, both are DB-free,
neither touches `scripts/gate_registry.json`, `quickscale_modules/*/module.yml`,
`quickscale_core/contracts/`, or `quickscale_core/manifest/`, and neither shares a code file with
any W2 ticket — SA174 owns `quickscale_modules/orgs/.../apps.py`, SA175 owns
`quickscale_devtools/.../beta_migration.py` and its conformance test, and no other open ticket
touches any of the three. W2's band-B head is **authority-gated**, not busy, which is precisely the case the
standing band-C displacement rule was written for: filler may take a lane whose band-B leg cannot
proceed. The move gives W2 two runnable tickets instead of an idle lane, and leaves W1 as one
coherent generated-output chain, #22 ─► #19 ─► #20.

**Conflict surface of this move — it strictly reduces sharing.** `docs/others/arch-audit.md` had
three owners split across two lanes (SA174 and SA175 on W1, SA164 on W2); all three are now W2, so
the file becomes **single-lane and one-directional** under the runnable order #31 → #32 with #25
merging later. `apps.py` and `beta_migration.py` move from W1-only to W2-only. **No code file gains
a second lane and no merge hazard is created.** The pass writes the shared closeout files —
`CHANGELOG.md`, this roadmap, `docs/technical/v88_ticket_context.md`, and `docs/index.md`, whose
ledger summary changes — plus `docs/others/tech-audit.md` for one stale resolved note. Those are
covered by the merge procedure's sync-resolve-rerun-review step in the execution rules, and
`quickscale_core/tests/test_v88_ticket_context_consistency.py` is re-run in the same change because
W1 and W2 state blocks moved.

**The moves that still do not stand, for structural reasons rather than situational ones:**

- **`scripts/gate_registry.json` and `quickscale_modules/*/module.yml` never cross worktrees.** All
  three chain tickets on W2 register or edit gate-registry entries, so none of them may leave W2 and
  nothing carrying a registry edit may enter another lane.
- **W1's `sa90_emission_manifests.json` rebaseline is one ordered pair** (#19 → #20) and may not be
  split, and SA165 (#22) precedes them by lane order.
- **SA165 (#22) to W3 would make `scripts/test_isolation_conformance.sh` single-lane** — a real gain
  — but SA165 is DB-free and the move would park it behind the exclusive-slot queue. Cost exceeds
  benefit; the file is already one-directional under the settled closeout → #22 → #29 sequence.
- **SA171 (#28) stays on W3.** It is structurally legal anywhere — DB-free, no shared file, no
  `contracts/`/`manifest/` touch — but it defines the advisory-lock topology that SA172 follows, so
  keeping both on W3 avoids a context handoff. Verified against the tree: `quickscale_core/advisory_lock.py` and
  `quickscale_core/dr_engine/_lock.py` and their suites carry no `django_db` marker and no
  PostgreSQL reference, so **it needs no exclusive slot** and no re-analysis is owed.

### Lane state

**Measured 2026-09-04** against `v88` at `78fcfc3a30b5ecf1f42f0b44dcf7c7a307ce4e83`. Never trust a
transcribed count; re-measure before acting.

```bash
for w in wt-track1 wt-track2 wt-track3; do echo -n "$w: "; git rev-list --left-right --count v88...$w; done
```

**Read that output as `behind ahead`** — the left column counts commits on `v88` and not on the
worktree, the right column the reverse.

| Worktree | behind / ahead | Tip | Standing |
|---|---|---|---|
| `wt-track1` | 9 / 0 | `a14ea029` | clean; SA167d's conditional post-integration candidate is integrated at exact-tip, and SA165's retained A-C product merged at `3f925b96` |
| `wt-track2` | 15 / 0 | `35dfa3c9` | clean; SA167c's retained A-E product object remains authoritative and F awaits fresh authority |
| `wt-track3` | 0 / 0 | `78fcfc3a` | accepted SA170 closeout candidate in the working tree |

**No lane branch is ahead, but W3 carries the accepted SA170 closeout as a reviewed working-tree
candidate.** It is ready for maintainer commit and merge through the normal ref-authority path before
the other lanes are synced. SA167c remains open because Phase F has not received a fresh authority
or verdict.

### SA170 retained closeout handoff — exact-diff review complete; Git delivery remains

**Selected-task status at this handoff (2026-09-04): no SA170 implementation or validation phase
remains.** The retained 17-file working-tree candidate is intentionally preserved. Calling the
working tree a *partial improvement* describes its uncommitted/unmerged delivery state, not an
unfinished SA170 product phase. The roadmap therefore carries no checked SA170 entry: under the
open-work-only policy its completed work is archived in [CHANGELOG.md](../../CHANGELOG.md), while
this section records the exact boundary the next maintainer must preserve.

**Completed in the retained candidate:**

1. **Phases A and B — deterministic Docker lifecycle ownership and diagnostics.** Exact-name
   structured container status, fail-loud readiness diagnostics, scoped and labelled React build
   images, exact-scope cleanup, and hermetic two-scope coverage are retained.
2. **Phase C-correct — release-campaign prerequisites and initialized-database readiness.** The
   dependency-security, manifest-parity, provisioning-pipefail, lane-port, cleanup-evidence,
   current-status, and end-of-init sentinel corrections are retained.
3. **Phase C-release — ordered release evidence.** The serial `QS_E2E_PARALLEL=0 make test-e2e`
   campaign and, only after it passed, the concurrent `make ci-e2e` campaign both exited 0. Their
   exact Core/CLI counts, cleanup evidence, and standing PostgreSQL invariants are archived in the
   changelog closeout.
4. **Closeout reconciliation.** SA170 and TA70 are removed from the live queue, merge position #27
   is retired, SA171 is the dependency-free W3 head, the queue/lane counts are reconciled, and the
   focused consistency contract covers the new state.

**Pending or blocking for this selected task:** no product, test, documentation, reviewed-plan
implementation, or exact-diff review phase is pending. The complete 17-file candidate was reviewed
as one closeout set on 2026-09-04; no substantive correctness, scope, compatibility, or integration
defect was found. The required focused consistency command returned **31 passed**, and the generated
emission-manifest parity class returned **7 passed**. The only remaining boundary is repository
delivery: preserve the reviewed candidate and let a maintainer with Git authority commit and merge it
into `v88`. The prior second-pass reviewer's incomplete report blocked that delivery step; it did not
produce a correctness finding and does not reopen SA170, TA70, or any accepted phase.

**Decisions required to continue cleanly:** none for SA170. The two open maintainer decisions below
belong to future queue execution — fresh SA167c Phase-F authority and confirmation or reversal of
the unstarted SA174/SA175 lane move. They must not be represented as unfinished SA170 work or used
to hold this accepted candidate open.

**Remaining delivery plan (not a new implementation plan):**

1. A maintainer with ref authority commits the reviewed 17-file candidate and merges it into `v88`; no sync
   merge is needed while both tips remain at `78fcfc3a`. Once this handoff is present on `v88`, that
   delivery boundary is satisfied by definition.
2. Re-measure all lane tips before starting future tickets, then execute the per-lane actions below.
   Do not rerun SA170's accepted release campaign merely because delivery moved the ref.

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

- **W2 — obtain fresh reviewed authority for SA167c (#21) Phase F; if it is not immediately
  available, start SA174 (#31), the band-C filler moved onto this lane.** Do not start SA166.
  Phases A-E are accepted on retained product object
  `91fd3bb6e6b638735361b511c1515cddccce5d15`; do not reimplement or re-close them. F is unaccepted
  after its sole `QS_E2E_INTEGRATION_REF=v88 make ci-e2e` run exited 2 with 2 Core and 8 CLI E2E
  failures then owned by SA170/W3. The nine-file status checkpoint merged only as retained-partial-only
  merge-back at `ef712e2d649d73aec0bdd9b4d3ca0b23913da419`, without accepting F and without closing
  SA167c. The upstream failure is now closed, but that retained checkpoint still makes no completion
  claim. Obtain fresh reviewed authority, freeze the then-current `v88`, and run one fresh F release
  verdict including `make ci-e2e`. W2 claims no standing service.
- **W1 — retain SA165 (#22) and run its Phase D documentation reconciliation, then hold.** SA167d's
  completion-grade closeout is archived as a conditional post-integration candidate; SA165 has
  `deps: none`, remains W1-owned, and its phases A-C are accepted on retained product object
  `573a57a34301e6a91971a7845095bd913bebd5e1`, merged at `3f925b96`. The repository-wide release gate
  is green, so run Phase D's final `make ci-e2e` on SA165's own candidate before closing it. SA165's
  `deps:` stay `none`.
- **W3 — start SA171 (#28).** SA170's final acceptance is archived in `CHANGELOG.md`; do not reopen
  its release campaign. SA171 has `deps: none`, is DB-free, and leaves the exclusive service slot
  available for SA172.

### Track readiness — the three states

A lane is **truly green** only when all three are yes. *Can start* = the next action is executable today.
*Can finish* = the ticket can reach a checked box using only work on its own lane. *Can merge* =
merge-back is not order-gated behind another lane.

| Lane | Head | Can start | Can finish | Can merge | On the critical path |
|---|---|---|---|---|---|
| **W2** | SA167c (#21) | **no** — fresh reviewed authority is required before Phase F | **no** — the same authority gates a fresh verdict | **yes after authority and a green verdict** | **yes** — it is the remaining release-committed work |
| **W1** | SA165 (#22) | **yes** — `deps: none`; Phase D is runnable and the repository-wide gate is green | **yes** — its own Phase-D release verification remains W1-owned | **yes** — no cross-lane blocker remains | no |
| **W3** | SA171 (#28) | **yes** — `deps: none` and DB-free | **yes** — all work is W3-owned | **yes** — no ticket is ordered ahead of #28 | no |

**W1 and W3 are truly green.** W2 is no longer blocked by another lane; its two "no" cells are the
explicit authority gate for SA167c Phase F. SA174 and SA175 remain runnable filler on W2 while that
decision is pending, but they do not move the release date.

### Maintainer decisions

**Two decisions are open.**

**Decision 1 — grant fresh release authority for SA167c Phase F.** Phase F is a *release verdict*,
not ordinary implementation: re-running it requires fresh reviewed authority against a freshly frozen
`v88`. SA170's upstream E2E surface is green, so this authorization is now the only condition behind
W2's two "no" cells and the decision that moves the release date.

**Decision 2 — confirm or reverse the SA174/SA175 lane move.** The 2026-09-03 pass moved both tickets from W1
to W2 on the reasoning in [Track rebalance](#track-rebalance--one-move-stands). It is cheap to
reverse today (no work has started on either) and expensive after either ticket is in flight.
Confirming it keeps filler available while W2 waits for authority and makes
`docs/others/arch-audit.md` single-lane; reversing it returns W1 to five positions. No work has
started on either ticket, so this is the last low-cost point to decide.

The five decisions settled on 2026-08-31 — the `sqlparse` suppressions, `quickscale_devtools`
publication, the consistency test's canary reduction, the band-C displacement rule, and the
permanence of the privileged-command set — are archived with their full reasoning in
[CHANGELOG.md](../../CHANGELOG.md). Only their standing consequences live on here: in
[Standing rules](#standing-rules-carried-from-closed-decisions), in the shrunk SA174 and SA175
ticket bodies, and in the
[deliberately-not-ticketed table](#audit-items-deliberately-not-ticketed). D3 and the
placeholder-declaration policy remain settled and are not reopened here.

### Handoff checklist — applies to all three lanes

Before any ticket work, measure each lane against current `v88`; when a worktree lags:

1. **Sync.** Merge `v88` into the worktree and resolve there, never on the integration branch.
   Expect a conflict in `docs/technical/roadmap.md`; keep this file's structure.
2. **Re-run the consistency test in the same change** if a W1/W2/W3 state block moved:
   `poetry run pytest quickscale_core/tests/test_v88_ticket_context_consistency.py -q -o addopts= --no-cov`.
3. **Route database-backed gates through their owned profiles.** `make test` delegates its
   integration leg to `make test-integration`; that target, `make test-bypassrls`, and
   `make isolation-conformance` use the repository-owned helper profiles. Local runs allocate
   disjoint, dynamically scoped databases on loopback and do not flip ownership of the standing
   twelve `test_quickscale_*` databases. **W3 has priority whenever one of its Docker-backed legs
   is active; E1's strict no-listener window is complete and its standing state was restored.**
4. **Announce core-package edits.** A change under `quickscale_core/contracts/` or
   `quickscale_core/manifest/` can turn another lane red without sharing a file — see the recorded
   `203fcd61` precedent. No open ticket may touch the settled presence-contract surfaces.
5. **Reproduce the ticket's measured starting state** before changing anything. Every open ticket
   below states one.
6. **Merge back** by re-running the ticket's own verification on the exact reviewed tip, then
   merging that tip.

#### Standing rules carried from closed decisions

- **W3 holds the exclusive PostgreSQL/Docker slot.** W3 may stop the container `pg18-af10` for a
  strict-acceptance window and **must restart it afterwards** (`docker start pg18-af10`); the
  container must not be removed, its volume must not be pruned, and the twelve `test_quickscale_*`
  databases plus `quickscale_test_role` ownership must be restored as standing state after the
  window. Helper-routed W1 and W2 database gates do not consume that standing state.
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
- **Local database-lane profile isolation** — `make test-integration`, `make test-bypassrls`, and
  `make isolation-conformance` must run through their corresponding helper profiles. Each local
  profile owns disjoint, dynamically scoped databases and its validated role; it does not alter
  ownership of the standing twelve test databases.
- **SA165 (#22) is released with `deps: none` after SA167d's conditional closeout candidate.** W1
  still runs one reviewed child at a time and keeps its remaining chain ordered locally.
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

One queue. Within a worktree, one reviewed child at a time; a ticket syncs the integration branch
into its worktree, resolves there, reruns its own verification, then merges its exact reviewed tip.

| # | Ticket | Band | Tier | Worktree | Merges after | Service slot |
|---|---|---|---|---|---|---|
| 19 | **SA161** | C | 3 | W1 | SA165 | no |
| 20 | **SA160** | C | 2 | W1 | SA161 | no |
| 21 | **SA167c** | B | 2 | W2 | — | no |
| 22 | **SA165** | C | 3 | W1 | — | no |
| 24 | **SA166** | C | 3 | W2 | SA167c | no |
| 25 | **SA164** | C | 3 | W2 | SA166 | no |
| 28 | **SA171** | C | 2 | W3 | none | no |
| 29 | **SA172** | C | 3 | W3 | SA171 | no |
| 31 | **SA174** | C | 3 | W2 | — *(runnable while SA167c awaits authority)* | no |
| 32 | **SA175** | C | 3 | W2 | SA174 *(lane only)* | no |

SA167c's synchronized status checkpoint merged under its retained-partial authorization after fresh
exact-tip convergence and patch-backed terminal attestation. That integration does not
accept F, close the ticket, unblock SA166, or clear any release gate. Other entries carry their
declared queue or content dependencies, subject to fresh branch remeasurement before execution.

Positions #1, #2, #3, #4, #5, #6, #6b, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #23, #26, #27 are **retired and not
reused**; their tickets are closed and archived in [CHANGELOG.md](../../CHANGELOG.md). Gaps carry no meaning.

The per-lane heads are **#21 (W2), #22 (W1), and #28 (W3)**. #21 has accepted A-E, including retained
product commit `91fd3bb6e6b638735361b511c1515cddccce5d15`; F release validation remains outstanding
after the historical 2 Core and 8 CLI E2E failures; SA170 has cleared those failures, but fresh
authority is still required before a new F verdict. #22 and #28 are eligible with `deps: none`.

Most "Merges after" edges are lane ordering — a queue position, clearable by the upstream work **or
by a maintainer reordering the lane**. Two are
**hard content dependencies** that no reorder clears: **SA160 after SA161** (shared emission-parity rebaseline of `sa90_emission_manifests.json`;
the pair must not be split, so the run is ordered #19, #20 — **SA174 left this run on 2026-08-31**
when the privileged-command set was settled as permanent and its emitted-byte change was dropped), **SA164's substance after SA166** (its
`test_sa92_migration_squash_guardrail.py` work needs `django_apps:` retired). Band-C positions
(19, 20, 22, 24, 25, 28, 29, 31, 32) are *earliest-eligible*, not commitments, and may slip past the
release. **SA174 (#31) and SA175 (#32) were pulled forward onto idle W2 on 2026-09-03**: neither has a
content dependency, neither needs an exclusive slot, and SA174 is now a comment correction plus an
  audit demotion. They may run while W2's authority-gated head is waiting.

### Shared conflict surfaces

Standing surface for every ticket: `CHANGELOG.md`, `docs/technical/roadmap.md`, and
`docs/technical/v88_ticket_context.md` when the ticket's concept notes change.

| Ticket | Additional shared surface | Why |
|---|---|---|
| SA167c | every `quickscale_modules/*/module.yml`, `scripts/gate_registry.json`, `scripts/{check,test}_module_app_declaration.py`, `scripts/test_gate_parity.py`, `scripts/{check_ci_locally.sh,sync_ci_gate_jobs.py}`, `Makefile`, `.github/workflows/ci.yml`, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` | retires the inert key and registers the declaration gate; **registry membership is why this is W2** |
| SA160, SA161 | generator templates + **SA90 emission-parity fixture**, `docs/others/tech-audit.md` | emitted output changes |
| SA164 | `docs/others/arch-audit.md`, `scripts/gate_registry.json`, `scripts/check_gate_parity.py`, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` | current watchlist discharge; **W2** — registry and the SA92 test are W2-owned, and it merges last |
| SA165 | `docs/others/tech-audit.md`, `quickscale_core/.../state_schema.py`, `scripts/test_isolation_conformance.sh`, `quickscale_core/tests/test_generator/test_generator.py`, `OPERATIONS.md.j2` | watchlist discharge; W1-isolated |
| SA166 | `scripts/gate_registry.json`, `Makefile`, CI workflow, `docs/others/tech-audit.md` | new process gate |
| SA171 | `quickscale_core/.../dr_engine/_lock.py`, `quickscale_core/.../advisory_lock.py`, `docs/others/tech-audit.md` | two hand-rolled file locks share one TOCTOU; **DB-free** (both suites carry no `django_db` marker), so it needs no exclusive slot |
| SA172 | `quickscale_modules/orgs/.../tenancy.py`, `scripts/test_isolation_conformance.sh`, `docs/others/tech-audit.md` | RLS policy templates and their conformance assertion; **W3** — proved against a live PostgreSQL |
| SA174 | `quickscale_modules/orgs/.../apps.py`, `docs/others/arch-audit.md` | **shrunk 2026-08-31** to correcting the false SSOT comment and demoting the finding; no emitted bytes, no generator surface, no emission fixture |
| SA175 | `quickscale_cli/tests/test_beta_migration_ownership_conformance.py`, `quickscale_devtools/.../beta_migration.py`, `docs/others/arch-audit.md` | disposition-coherence assertion for the launcher↔settings contract; **W2** — no other open ticket touches either file |

Surfaces needing an explicit ordering note beyond the table:

- `scripts/gate_registry.json` — SA167c, SA166, SA164, all W2. **This surface never crosses
  worktrees**; that invariant is why SA167c could not move to W1 with the other wiring legs, and it
  applies equally to `quickscale_modules/*/module.yml`.
- `quickscale_core/contracts/` and `quickscale_core/manifest/` are settled cross-lane surfaces,
  shared by *behaviour* rather than by filename: every lane imports them. `entry_point.py`'s
  manifest-read behaviour and module-owned adapter registry stay settled tree state. `203fcd61` is
  the recorded precedent for what happens when this surface moves without a cross-lane announcement.
- `scripts/test_gate_parity.py` — **SA167c (#21, W2) owns it for the release**; its retained Phase-C
  delta rewrote the declaration-gate oracle. No other open ticket may touch it.
  The closed SA163 replaced its
  transcribed provisioning shell literal with a `describe --format json` binding plus an
  absence-of-the-old-shape assertion. That binding, the regenerated 24-entry publish oracle, and
  SA123's settled hosted-job, `needs`-edge, run-value, publish/E2E-path, and generator expectations
  are settled tree state and must be preserved by anything that touches the file.
- `.github/workflows/ci.yml` — **two W2 owners, sequenced.** SA167c's retained Phase-C delta added the
  declaration-gate job; SA166 (#24) registers a further gate after it. Merge order #21 before #24
  makes the surface one-directional. `scripts/provision_ci_postgres.sh` has **no open owner** after SA163
  closed, and neither ticket may reopen its provisioning stations. Its immediate-child status/cleanup
  path was last corrected inside SA167c's already-merged `91fd3bb6`; a lane seeing it red is behind
  current `v88`, not looking at an open defect.
- `.../settings/production.py.j2` — SA161 (#19, W1) is the only open owner. The privileged-command
  work moved out of SA164, so this file carries no #19-before-#25 cross-lane ordering caution.
- `scripts/test_isolation_conformance.sh` — three owners, all sequenced. SA163's merged edit is
  settled bytes; SA165 (#22, W1) applies its one-line skip-allowlist narrowing over them; SA172
  (#29, W3) adds a policy-text assertion in a different region and merges last.
- `sa90_emission_manifests.json` — SA161 then SA160, a pair since SA174 left the run. Each rebaseline appends its own
  `baseline_evidence` entry with per-file rationale; every prior entry must be preserved.
- `scripts/test_e2e.sh` has no open owner after SA170's accepted closeout. Preserve its settled
  exact-scope cleanup contract.

`docs/others/arch-audit.md` is on three surfaces — **SA174** (demotes
`privileged-command-set-multi-owner` from rank 1 to the watchlist, without closing
it), **SA175** (records rank-2's first step as discharged
without closing the finding), and **SA164** (adjudicates the watchlist) — and after the 2026-09-03
lane move **all three are W2**, so the file is single-lane and one-directional under the runnable
order #31 → #32 with #25 merging later. It still resolves through the standard
sync-resolve-rerun-review step. The
prior rank-1 `ci-environment-hand-replicated` is resolved and archived. The rank-3 and rank-4
findings (`deletion-invariants-per-boundary-reimplementation`, `org-model-universe-hand-enumerated`)
remain untouched per the standing "neither" rule, as does the **substance** of rank-2
(`generated-file-ownership-unmodeled`) — SA175 takes only the bounded first step the audit itself
marks as trigger-independent.

**Closeout conflict surface.** Every ticket writes `CHANGELOG.md`, this file, and
`docs/technical/v88_ticket_context.md` at closeout. `docs/index.md` and any other current same-fact
consumer join when the closeout changes a summarized count, status, dependency, schedule, or owner;
`docs/others/tech-audit.md` is shared by
SA160, SA161, SA165, SA166, SA171, and SA172, and `docs/others/arch-audit.md` by SA164,
SA174, and SA175 — all three now on W2. That is by design and is covered by the merge
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

- [ ] **SA167c — Retire `django_apps:` and gate the app declaration.** `Band B · Tier 2 · W2 · merge #21 · deps: none · closes the SA167 family`
  `django_apps:` was inert declarative surface: eleven manifests carried it, the loader parsed it,
  no production path read it, and one SA92 helper used it before falling back to a guessed path.
  **Acceptance:** `django_apps:` is either derived from the `apps` wiring projection or removed from
  all manifests, `ModuleManifest`, and the loader, with no key parsed-but-unread remaining; a
  conformance gate fails when a module ships models or a migration without declaring at least one
  Django app, registered in `scripts/gate_registry.json` and passing `scripts/check_gate_parity.py`;
  the gate is proved by deleting a module's app declaration and observing red, reverted before
  merge; `test_sa92_migration_squash_guardrail.py` no longer depends on the retired key.

  **State (measured 2026-09-01): retained partial checkpoint; phases A-E are accepted and F is
  outstanding.** Retained product object `91fd3bb6e6b638735361b511c1515cddccce5d15` remains
  authoritative. E's ordered `make lint`, `make typecheck`, and focused ticket-context suite exited
  0. F froze the nine-file archive/remove candidate at
  `f60fe2bcb6efba654782c96ee1113ea6c90b74ee` and ran
  `QS_E2E_INTEGRATION_REF=v88 make ci-e2e` exactly once. Stages 1-11 passed and stage 12 ran, but the
  command exited **2**: Core reported **2 failed / 36 passed** and CLI reported **8 failed / 32
  passed**; exact-scope cleanup passed. Those historical failures were owned by SA170/W3 and are now
  closed; they were not accepted or repaired in this worktree. F is still unaccepted, SA167c remains open at #21, SA166 remains
  dependent on it, SA164 remains after SA166, and no completion or release-readiness claim is made.
  During F, `v88` advanced to `3aa0c67f843eddd779f9766de4c274a5a249f485`; the frozen F candidate
  could not merge then. The later retained status checkpoint reconciled the moved base and merged
  without accepting F.

  **Completed:** phases A-E and the retained product object above. **Pending:** fresh reviewed
  authority, F release validation,
  then completion-grade convergence, patch-backed terminal attestation, and exact-tip integration.
  **Blocking:** fresh reviewed authority for a new F verdict. The moved integration base is reconciled
  and the former SA170/W3 blocker is green. **Decisions needed:** grant that authority. **Remaining
  reviewed plan:** plan authority `EV-6` remains binding for accepted A-E; do not redo A-E,
  reinterpret the historical red as accepted, or reopen SA170/W3 here.

  **Exact cold-start resume object.** Resume from retained product object
  `91fd3bb6e6b638735361b511c1515cddccce5d15` with phases A-E accepted and F unaccepted, from the
  settled nine-file status/test checkpoint, after failed command
  `QS_E2E_INTEGRATION_REF=v88 make ci-e2e` exit 2 (stages 1-11 passed; Core 2/36 and CLI 8/32 at
  stage 12; cleanup passed) over frozen base `f60fe2bcb6efba654782c96ee1113ea6c90b74ee` against
  moved `v88` `3aa0c67f843eddd779f9766de4c274a5a249f485`. That checkpoint is `4de75d39`,
  synchronized with `v88` base `8385780fe624893dc66e1382f2f68ce1ea759a02` at
  `eacad160d92b37f81f593085a64e18db4fb271f0`, converged and terminally attested, remediated to exact
  tip `cb7517470df4f7e5c6890310de1a39ae0ca2c395`, and merged at
  `ef712e2d649d73aec0bdd9b4d3ca0b23913da419` as retained partial delivery only — the review
  narrative is archived in [CHANGELOG.md](../../CHANGELOG.md). The former SA170/W3 blocker is green;
  obtain fresh reviewed authority preserving `EV-6`, re-freeze the
  then-current `v88`, reconcile only the retained status surface, and run one newly authorized F
  release verdict before completion-grade convergence and patch-backed attestation. Retain rather
  than restore any halted candidate, and never redo accepted A-E.

  **The key itself is already gone.** `grep -rn django_apps` over `quickscale_core`,
  `quickscale_modules`, and `quickscale_cli` returns nothing: the manifests, `ModuleManifest`, loader,
  and SA92 helper are clear. Do not reopen `quickscale_core/contracts/`,
  `quickscale_core/manifest/`, accepted A-E product bytes, gate wiring, or closed SA170/W3 implementation.
  **Shared conflict surface:** every `quickscale_modules/*/module.yml`, `scripts/gate_registry.json`,
  `scripts/{check,test}_module_app_declaration.py`, `scripts/test_gate_parity.py`,
  `scripts/{check_ci_locally.sh,sync_ci_gate_jobs.py}`, `Makefile`, `.github/workflows/ci.yml`, and
  `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`.

---

## Audit-derived backlog

Tickets opened from the live findings in [arch-audit.md](../others/arch-audit.md) and
[tech-audit.md](../others/tech-audit.md), both at audit snapshot **2026-08-28**. Both documents remain the SSOT for finding
detail, evidence, and refutation; this section carries scope only, and the merge-order table above
remains the sequencing authority. **These are not follow-on work** — they are sequenced with the
implementation section. Any ticket here that closes or changes a live finding takes its audit
document onto its shared conflict surface.

The 2026-08-28 pass changed what this section owes. On the tech side TA70 is now retired: TA67,
TA68, TA71 and TA72 map one-to-one onto SA160, SA161, SA171 and SA172, and every remaining tooling
gap and actionable watch item is claimed. On the structural side the pass **resolved** the
prior rank-1 finding, **promoted** the privileged-command pair out of the watchlist into rank 1, and
added new evidence under rank 2. Those two movements are what **SA174 (#31)** and **SA175 (#32)**
integrate; the deferred rank-3 and rank-4 findings, and rank-2's substance, stay behind their
triggers.

- [ ] **SA160 — Share one correct CSRF-token helper in the React theme.** `Band C · Tier 2 · W1 · merge #20 · deps: SA161 (emission-parity ordering)`
  Closes tech-audit **TA67** (`spa-csrf-token-duplicate-cookie`, S3) — the only finding in deployment reality #3, the internet-facing generated project. `themes/showcase_react/src/hooks/useApi.ts:20-28` and `src/components/forms/FormRenderer.tsx:206-211` carry the same eleven lines: the parser splits `document.cookie` on `"; csrftoken="` and accepts the result **only when it yields exactly two parts**. Two `csrftoken` cookies yield three, so `getCsrfToken()` returns `''`, `buildRequestHeaders` (`:89-94`) skips `X-CSRFToken`, and Django rejects every POST/PUT/PATCH/DELETE with 403. The triggering state is ordinary: an `app.example.com` deployment alongside a `.example.com` cookie, the outcome of setting or changing `CSRF_COOKIE_DOMAIN`, of a sibling Django app on another subdomain, or of a stale apex-scoped cookie. GETs keep working, so the app looks alive and merely refuses to save, and no error names the cause. Fails closed — availability, not a security hole. There is no shared CSRF helper, no fetch interceptor, and no template-injected token, so no layer-up guard exists.
  **Acceptance:** one shared helper in `src/lib/` iterates cookies rather than counting split segments — splitting on `'; '`, matching the name exactly, and `decodeURIComponent`-ing the value, per Django's own documented `getCookie` — and both call sites import it with no third variant remaining; a `vitest` table test covers `'csrftoken=A; csrftoken=B'`, `'sessionid=x; csrftoken=A'`, `'csrftoken=A'`, and `''`, with the first three returning a non-empty token; the tech-audit finding is retired.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/`, generator emission parity baselines, `docs/others/tech-audit.md`.

- [ ] **SA161 — Remove the dead `get_client_ip` definitions from generated settings.** `Band C · Tier 3 · W1 · merge #19 · deps: SA165 (worktree ordering)`
  Closes tech-audit **TA68** (`generated-settings-dead-client-ip`, S4). `templates/project_name/settings/base.py.j2:61` and `settings/production.py.j2:123` both define a module-level `get_client_ip(request)`, and the production copy rebinds it under a comment claiming the rebind exists "so that production defaults … are actually in effect at request time". Neither is reachable: Django's `Settings` copies only **uppercase** names off the settings module, so `django.conf.settings.get_client_ip` does not exist, and grep across all templates returns only the two definitions. The live implementation is `quickscale_modules_orgs.current_org.get_client_ip`, which reads the uppercase `USE_X_FORWARDED_FOR` / `TRUSTED_PROXY_COUNT` settings dynamically and is correct.
  **Acceptance:** both definitions are deleted, or each carries a comment pointing at the orgs helper as the live implementation; the uppercase settings and the `REST_FRAMEWORK["NUM_PROXIES"]` recomputation are retained unchanged; the misleading behavioural comment at `production.py.j2:119-122` is removed either way; a generated project boots and proxy-aware client-IP resolution is unchanged, asserted by a test; emission parity is rebaselined with rationale; the tech-audit finding is retired.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/`, emission parity baselines, `docs/others/tech-audit.md`.

- [ ] **SA174 — Correct the false SSOT claim on the privileged-command set.** `Band C · Tier 3 · W2 · merge #31 · deps: none · shrunk 2026-08-31 · moved to W2 2026-09-03`
  **Scope reduced 2026-08-31: the sanctioned privileged-command set is confirmed
  permanent at two commands.** With `{"migrate", "createcachetable"}` fixed, the drift this ticket
  existed to prevent cannot occur, so `privileged-command-set-multi-owner` drops from arch-audit
  **rank 1 to a watchlist item** and this ticket collapses from eight acceptance criteria to the one
  that was always the real defect. The consolidation plan (rendering the set through the
  `runtime_pins` seam, a deriving oracle, an emission rebaseline) is **archived unimplemented** in
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
  **Consequences of the shrink, reconciled below:** SA174 left the ordered `#19 → #20 → #31`
  rebaseline run, which is now the pair `#19 → #20`; it no longer touches
  `.../settings/production.py.j2`, which now has SA161 as its only open owner; its dependency on SA160
  is dropped. With no emitted bytes and no generator surface left, nothing tied it to W1, which is
  why the 2026-09-03 rebalance moved it to idle W2.
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
  **Its dependency on SA174 is gone (2026-08-31); it keeps W2 lane ordering behind SA174 only.** The audit's ordering argument was: consolidate
  the command set first, then reference the now-single declaration. Settling the set as permanent cancelled that
  consolidation, so there is no single declaration to source from and **this ticket names its own
  three participating paths**. SA175 now has no content dependency on anything; it keeps merge
  position #32 by lane ordering alone.
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

- [ ] **SA164 — Adjudicate the arch-audit watchlist's unevaluable and drifted items.** `Band C · Tier 3 · W2 · merge #25 · deps: SA166 (worktree ordering)`
  The 2026-08-28 pass rewrote this watchlist: the prior rank-1 `ci-environment-hand-replicated`
  resolved (retiring the environment-schema item), the privileged-command pair **fired and was
  promoted to a ranked finding** — now SA174's — and three new items were minted inside the landed
  provisioning derivation. What remains for SA164 is one item carrying an explicit action, one naming
  question that becomes load-bearing on a specific trigger, and the restatement of the three new
  not-fired items so their triggers survive the next pass.
  - **SA92 migration-squash discovery tuple — artifact located 2026-08-21, now evaluable.** The audit recorded this as unlocatable, but the artifact is `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` — a bounded literal tripwire for cross-table `UPDATE … SET organization_id` DML in migrations. The prior search missed it because it grepped for `squash` in source rather than in test filenames. The completed declaration-gate work removed the helper's dependency on the retired `django_apps:` key; `_migdir()` still uses the conventional path and returns `None` when it is absent, so SA164 must make that lookup fail hard rather than silently skipping a module. Its authoritative backstop is also still a catalog/data parity gate anchored to `v87`, a retired release ref no longer resolved by the quality gate.
  - **Privileged-command set — promoted out of the watchlist and out of this ticket.** The
    2026-08-28 structural pass promoted it to the arch audit's **rank-1 finding**
    (`privileged-command-set-multi-owner`), counting four independent owners of one security-relevant
    command set. It is no longer a watch item and is no longer SA164's: **SA174 (#31, W2)** owns it.
    SA164 must not edit `.../settings/production.py.j2`, `orgs/apps.py`,
    `development_commands.py`, or `start.sh.j2` — that removes this ticket's only cross-lane file
    surface.
  - **`trigger_inputs` has drifted from its name.** `check_gate_parity.py:2652-2690` uses the field as a bidirectional partition of `e2e.yml`'s path allowlist, not as "what changes should trigger this gate" — which is why `check-core-compat`'s trigger is `quickscale_modules/backups/**`. Not a defect; the check it performs is real and exact. Becomes load-bearing only if a gate is ever *skipped* on the basis of `trigger_inputs`.
  **Acceptance:** the SA92 item is re-anchored to `test_sa92_migration_squash_guardrail.py` with a stated trigger, its `_migdir()` fallback fails loudly instead of guessing the path, and its `v87`-anchored parity backstop is re-anchored to the current regenerated migrations; `trigger_inputs` is either renamed to describe what it does or its docstring/schema description records the actual semantics plus the skip-based promotion trigger; the arch audit's **current** watchlist is re-stated with its triggers intact rather than the superseded pre-resolution list — the two hand-pinned literals minted inside the new provisioning derivation (`provision_ci_postgres.sh:93,96`, `!= teams` and `== 12`, trigger: a thirteenth shipped module or `teams` graduating), the second copy of the PostgreSQL major (`provision_ci_postgres.sh:15` against `runtime_pins.py:30`, trigger: the DR engine's `pg_dump`/`pg_restore` major-version contract coming to depend on the two agreeing), and the roughly six count-pinned oracles in `scripts/test_gate_parity.py` (trigger: the next gate addition paying more than two oracle edits, or two oracles disagreeing) — noting for each that it is **not fired**; `docs/others/arch-audit.md` is updated in the same change.
  **Shared conflict surface:** `docs/others/arch-audit.md`, `scripts/gate_registry.json`, `scripts/check_gate_parity.py`, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`.

- [ ] **SA165 — Discharge the tech-audit watch items that carry an action.** `Band C · Tier 3 · W1 · merge #22 · deps: none`
  Of the remaining items in the tech audit's *Notes*, most are accepted trade-offs or are owned elsewhere (the local-wheelhouse seam is discharged by the closed SA150; integration-branch CI, generator lock generation, the DB-free healthcheck, the CRM count fallbacks, and non-durable atomic state writes are each recorded as deliberate and are **not** in this ticket's scope). Four carry a concrete action:
  - **`flush_empty_consolidated_sections` swallows a corrupt state file.** `quickscale_core/src/quickscale_core/schema/state_schema.py:386-388` returns silently on `yaml.YAMLError, OSError`, skipping the explicit `modules: {}` / `managed_files: []` markers downstream readers use to distinguish "M2 has spoken" from pre-M2 state. The trigger is narrow — the file was just written successfully by `save()` — but this is exactly the silent-fallback shape the Fail-Hard Principle names (`decisions.md:634`, `:716-732`).
  - **The isolation-gate skip allowlist matches on message, not test identity.** `scripts/test_isolation_conformance.sh:184` keys on `message.startswith('got empty parameter set')`, silencing an empty parameter set on *any* of the eleven parametrized tests in `test_tenant_table_conformance.py`, not only the two `PENDING_REMEDIATION` ones its own comment describes. Narrowing it to the two test names costs one line.
  - **`_HOST_DEPENDENT_PATHS` is a new hand-maintained exception station.** `be5cf024` added `frozenset({".env"})` to the SA90 emission byte-parity gate (`quickscale_core/tests/test_generator/test_generator.py:1023`). The justification is sound and the `755`/`644` mode normalization correctly removes a umask dependency, but this is an exception list on the repository's strictest gate: a second entry deserves scrutiny, a third deserves a derivation.
  - **Generated local-development credentials are predictable by construction.** `generator.py:507-508` derives `runtime_db_role = f"{package_name}_app"` and `runtime_db_password = f"{role}_password"` into `db/init.sql`, `docker-compose.yml`, and `.env.example`, none of which `.gitignore.j2` excludes. Safe as shipped — no published DB port, local dev only, production supplies `RUNTIME_DATABASE_URL` from the environment — but undocumented.
  **Acceptance:** `flush_empty_consolidated_sections` raises or reports rather than returning silently, with a regression test asserting the raise and not a log, and the fail-hard deviation is retired from the audit; the isolation skip allowlist keys on the two `PENDING_REMEDIATION` test identities rather than a message prefix, and a deliberately emptied ENROLLED set turns the gate red; `_HOST_DEPENDENT_PATHS` gains a written per-entry rationale and a monotonicity note stating the second/third-entry escalation, or is derived; `OPERATIONS.md` states explicitly that the generated local credentials must not survive into any shared environment; `docs/others/tech-audit.md` is updated to reflect each discharge.
  **State (measured 2026-09-02): retained partial checkpoint; implementation phases A-C are
  accepted and closeout Phase D is outstanding.** Retained product object
  `573a57a34301e6a91971a7845095bd913bebd5e1` contains the fail-hard state-read behavior and
  rollback regressions, exact identity-based isolation-skip authorization and hermetic negative
  coverage, accountable host-dependent manifest exceptions, the rendered shared-environment
  credential warning, and the three synchronized generated-output manifests. Task-tier convergence
  removed excluded `.venv/` fixture records and added a recurrence guard. Terminal review then found
  the remaining non-mapping YAML-root path; list and scalar roots, including `[]` and `null`, now
  raise `StateError` before any write and retain byte-identical state. That correction was
  applied after terminal attestation and carries only the remediation author's grade. Focused state/removal coverage
  passed with 141 tests; the combined state, removal, generator, template, and hermetic provisioning
  evidence passed with 423 tests plus one conditional environment skip, followed by 36 provisioning
  tests. These are retained product facts, not ticket completion or release-readiness evidence.

  That retained product merged into `v88` at `3f925b96` as retained partial delivery only; it
  accepts no Phase D evidence and closes neither SA165 nor its four watch items.

  **Pending:** Phase D must update `docs/others/tech-audit.md` first, archive the four discharged
  watch items in `CHANGELOG.md`, reconcile this roadmap and every current-status consumer including
  `docs/technical/v88_ticket_context.md` and `docs/index.md`, update
  `quickscale_core/tests/test_v88_ticket_context_consistency.py`, and run `make ci-e2e` on the final
  candidate. Only a green release gate may remove SA165 and merge position #22 under the roadmap's
  open-work-only policy. **Blocking:** none from another ticket; the repository-wide release gate is
  green and Phase D's documentation reconciliation is runnable today. SA165 must still run its own
  final `make ci-e2e` on its final candidate. SA165's `deps:` stay `none`. **Decisions needed:** none — the maintainer chose
  the standing open-work-only policy, so completion removes and archives SA165 rather than retaining
  a checked roadmap item.

  **Remaining reviewed plan and cold-start resume object.** Plan authority `EV-2` remains binding for
  Phase D. Resume Phase D from retained product object
  `573a57a34301e6a91971a7845095bd913bebd5e1`; do not redo accepted phases A-C, reopen the corrected
  non-mapping state path, or alter SA172's later isolation-script ownership. Re-read the current
  integration tip, reconcile the listed documentation/status consumers as one same-fact set, run the
  ticket-context consistency test whenever a W1 state block moves, then run the single release gate.
  If that gate is not green, keep SA165 open and record its exact returned failure rather than claiming
  completion.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/schema/state_schema.py`, `scripts/test_isolation_conformance.sh`, `quickscale_core/tests/test_generator/test_generator.py`, `quickscale_core/.../templates/OPERATIONS.md.j2`, `docs/others/tech-audit.md`.

- [ ] **SA166 — Require a testimony trail for behavioural commits.** `Band C · Tier 3 · W2 · merge #24 · deps: SA167c`
  Closes the tech audit's carried tooling gap *"no gate requires a changelog/ticket trail for behavioural commits"*. `d3d4c633` and `d4b0e834` were both titled "v0.87.0: QuickScale 0.87.0" while in fact changing hosted and publish provisioning, and `d3d4c633` left a repository conformance test red (TA66/SA158). Both audits independently flagged the same shape: a release-shaped message carrying a CI-topology change. Recorded in the audit as maintainer-process risk rather than a source finding, which is why this is Tier 3.
  **Acceptance:** a change touching `.github/workflows/`, `scripts/gate_registry.json`, or the provisioning stations requires either a roadmap ticket reference or a `CHANGELOG.md` entry, enforced mechanically rather than by convention; the check is registered in `scripts/gate_registry.json` and passes `scripts/check_gate_parity.py`; the gate fails on a deliberately introduced untitled workflow change, reverted before merge; false-positive cost is measured on the existing history and the rule is narrowed until it is quiet on legitimate release commits; the tooling gap is retired from the tech audit.
  **Shared conflict surface:** `scripts/gate_registry.json`, `Makefile`, CI workflow, `docs/others/tech-audit.md`.

- [ ] **SA171 — Make stale-lock clearing atomic in both file locks.** `Band C · Tier 2 · W3 · merge #28 · deps: none · DB-free; needs no exclusive slot`
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
| `generated-file-ownership-unmodeled` (arch rank 2) — **substance only** | arch, deferred | Held by the standing **"neither"** rule, and by the settled decision that **`quickscale_devtools` is maintainer-internal and will not be published** (2026-08-31) — the fact that holds this finding's severity down. Trigger: a third generated-project consumer, public updater, emitted-file expansion, or second theme. Options 1 and 2 (typed disposition metadata; a versioned ownership manifest with vintage negotiation) stay behind it. Its **trigger-independent first step is ticketed as SA175 (#32)** under the carve-out in the standing rules. Related weakness tracked in SA152. |
| `deletion-invariants-per-boundary-reimplementation` (arch rank 3) | arch, deferred | Same rule. Trigger: `teams`, a GDPR erasure command, bulk-admin deletion, or a second deletion boundary. Design together with `org-model-universe-hand-enumerated` at `teams` kickoff. |
| `org-model-universe-hand-enumerated` (arch rank 4) | arch, deferred | Same rule. Trigger: `teams` adds a tenant model, or a module adds a `PROTECT`/non-deferrable dependency among purge-owned rows. |
| Watch items recorded as deliberate | tech *Notes* | Integration-branch CI, generator lock-generation policy, the DB-free healthcheck, CRM/billing cross-tenant `all_objects` count fallbacks, and rename-atomic-but-not-durable state writes are each argued and accepted in the audit; re-examine only on the triggers stated there. |
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
