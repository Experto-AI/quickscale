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
- **Local database-lane operating constraint:** `make test-integration`, `make test-bypassrls`,
  and `make isolation-conformance` use the owned profiles in
  `scripts/provision_ci_postgres.sh`. Local profiles allocate disjoint, dynamically scoped
  databases on loopback and validate their own role; restricted and BYPASSRLS runs do not flip
  ownership of the standing twelve databases. Commands intentionally pointed at `localhost:5432`
  still require the standing service, but helper-routed module gates take a private server instead
  of queueing for it. Hosted CI uses its separate service/lease setup.
- **W1's wiring leg (SA167d) may not touch `scripts/gate_registry.json` or any `module.yml`.** Those are W2-owned surfaces.
- A ticket whose deliverable is Git ref state cannot be delegated to a file-editing worker. Route it to a maintainer session with ref authority and push credentials.
- **A run killed by a cutoff returns no exit code and is not evidence** — neither of green nor of
  red. One recorded acceptance stall was caused by exactly this, and the gate underneath turned out
  to be red. `make test` and `make quality` must therefore be launched detached (`nohup`, exit code
  written to a file, poll for the file). `make check` no longer needs it: measured at **184 s
  green** on `v88` after the `check-gate-suites` parallelisation, it fits inside a single foreground
  call.
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
| **A — Restore enforcement** | Gate layer reports green while not running, or runs red on HEAD. | **Empty.** No gate is red on `v88` and none reports green while not running. |
| **B — Release work on the critical paths** | The two longest serialized chains, one holding the exclusive service slot. | SA167c; SA135; SA170; SA167d |
| **C — Bounded independent fixes** | No dependants, small blast radius; absorbed as slack filler. | SA160, SA161, SA164, SA165, SA166, SA171, SA172, SA174, SA175 |

### Dependency graph and critical path

```text
v88 — three worktrees, thirteen open merge positions carrying thirteen open ticket entries, one merge queue

W2 (gates & declared wiring)   ★ CRITICAL PATH — committed head, band-C tail
  SA167c ─► SA166 ─► SA164     #21, #24, #25
  (SA167c: A-D accepted; E closeout and F release validation remain open)

W1 (module wiring + generated-output fixes)
  SA167d ─► SA165 ─► SA161 ─► SA160 ─► SA174 ─► SA175     #18, #22, #19, #20, #31, #32

W3 (service lifecycle — exclusive PostgreSQL/Docker slot)
  SA135 ─► SA170 ─► SA171 ─► SA172      #15, #27, #28, #29
  (SA171 is the one DB-free W3 ticket — the lane's fallback if SA135 stalls again)
```

**W2 sets the release date.** Its chain is `SA167c ─► SA166 ─► SA164`, with **#24 and #25** band-C
tail positions that may slip past the release. The release-committed critical path is therefore
**SA167c**, entirely inside W2 with no prerequisite outside it. W3 holds the exclusive slot and takes
scheduling priority while one of its Docker-backed legs is active, but its four positions are a
*queue*, not a chain. W1 is the longest lane at six positions, and its tails are band C, so it does
not set the date either.

**No cross-worktree dependency edges remain.** One cross-worktree *shared file* does, made
one-directional by merge order: `scripts/test_isolation_conformance.sh` (SA135's merged partial wrote
it; SA165 narrows one line over those settled bytes; #15 merges before #22).
`.../settings/production.py.j2` has one open owner, SA161 on W1; SA164's settled scope excludes it.

**Any edit under `quickscale_core/contracts/` or `quickscale_core/manifest/` is cross-lane** — every
lane imports them, so a behavioural change there can turn another lane red without sharing a file.
Announce it in the merge queue and re-run the other lanes' focused caller suites before merging. The
`203fcd61` precedent that established this rule is archived in [CHANGELOG.md](../../CHANGELOG.md). No
open ticket may edit these packages; the retained presence-contract implementation owns the settled
behaviour.

The manifest-reading `entry_point.py`, the fail-hard `QUICKSCALE_LOCAL_WHEELHOUSE` version-spec seam,
the regenerated migration baseline, and `scripts/provision_ci_postgres.sh` are settled tree state that
open tickets build on rather than re-open.

### Track rebalance — 2026-08-31 (fourth pass): no move stands

Lanes are **W1 6 · W2 3 · W3 4**, and every open ticket carries a track. Each was tested against the
three questions — independent of the rest of its lane, is another lane idle, and is it on or feeding
the critical path. **No cross-lane move passes**, for reasons that are structural rather than
situational:

- **`scripts/gate_registry.json` and `quickscale_modules/*/module.yml` never cross worktrees.** All
  three W2 tickets register or edit gate-registry entries, so moving any of them would put two lanes
  into one registry file — on the release-setting chain, where it is least affordable. SA166 and
  SA164 additionally share that file with each other and with SA167c, failing question one.
- **W1's `sa90_emission_manifests.json` rebaseline is one ordered pair** (#19 → #20) and may not be
  split. SA174 and SA175 carry no content dependency, but both stay W1 band-C slack: moving DB-free
  work onto W3's exclusive-slot queue buys no release progress, and moving it onto W2 would park
  filler behind the release-setting queue for a documentation-file gain only.
- **SA165 (#22) to W3 would make `scripts/test_isolation_conformance.sh` single-lane** — a real gain —
  but SA165 is DB-free and the move would park it behind the exclusive-slot queue. Cost exceeds
  benefit; the file is already one-directional under #15 → #22 → #29.

**Recorded fact, not assumption: SA171 (#28) needs no exclusive slot.** Verified against the tree —
`quickscale_core/advisory_lock.py` and `quickscale_core/dr_engine/_lock.py`, with suites
`test_advisory_lock.py` and `test_dr_engine_lock.py`, carry no `django_db` marker and no PostgreSQL
reference; its two-thread barrier test is pure filesystem. It shares no file with SA135 or SA170 and
touches neither `contracts/` nor `manifest/`. **It is W3's fallback the moment SA135 stalls again**,
with no re-analysis owed. The reorder that briefly moved it to W3's head, and the two decisions that
unwound it, are archived in [CHANGELOG.md](../../CHANGELOG.md).

**W1 is the longest lane at six positions and that is deliberate**: it is off the critical path, so
band-C work accumulates there rather than behind the release-setting chain. Band-C positions are
*earliest-eligible*, not commitments; the five W1 band-C positions are the slip budget.

**Conflict surface, unchanged by this pass.** No *code* file gains a second lane. The standing
closeout surface is `CHANGELOG.md`, this file, `docs/technical/v88_ticket_context.md`, and an audit
document when a ticket closes a live finding — all covered by the merge procedure's
sync-resolve-rerun-review step in the execution rules.

### Lane state

**Measured 2026-08-31 against the branches themselves.** Never trust a transcribed count:

```bash
for w in wt-track1 wt-track2 wt-track3; do echo -n "$w: "; git rev-list --left-right --count v88...$w; done
```

**Read that output as `behind ahead`** — the left column counts commits on `v88` and not on the
worktree, the right column the reverse. **All three worktrees are clean** (`git status --porcelain`
empty), and **no unmerged product delta remains anywhere in the release.**

- **`wt-track1`** is at `c0ebf34b`, **0 ahead / 0 behind `v88`**. SA167d's retained partial and the
  settled-decision reconciliation are both merged; the previously staged ledger edits are committed
  and the sync is finished. **Startable with no sync**; what remains is one Phase C campaign, not
  re-implementation.
- **`wt-track2`** is at `88a0778a`, **0 ahead / 23 behind `v88`**. SA167c's Phase-C product delta
  merged into `v88` at `d31c6b41` as retained delivery; the ticket remains open with C unaccepted and
  D-F not run. **Startable after a sync.**
- **`wt-track3`** is at `c78d9957`, **0 ahead / 27 behind `v88`**, with SA135's accepted E1/F delta
  merged. **SA135 is the lane head and is not blocked** — the canary that made archiving it unsafe is
  gone, so archive-and-G-FINAL is ordinary closeout. **Startable after a sync.**

Both lagging worktrees are behind only on integration-branch documentation and the two merged product
deltas they already contributed; neither sync carries a foreign code change into its lane.

### PostgreSQL routing — who actually claims the standing service

The standing PostgreSQL 18 container (`pg18-af10`) publishes `localhost:5432` and holds the twelve
shared `test_quickscale_*` databases. **Helper-routed local profiles do not use them.** Verified
against `scripts/provision_ci_postgres.sh`: `run --profile {restricted,isolation,bypassrls}` creates a
private ephemeral `postgres:18` container, reads its dynamic loopback port, provisions scoped databases
and the profile role, exports `QS_<MODULE>_DB_{NAME,USER,HOST,PORT}` for the child, and removes the
owned container on exit. Only commands deliberately left on `localhost:5432` contend for the standing
service. **W1's bare `make test` and W2's module acceptance gate both route through private profiles
and claim nothing.** W3 retains priority for its Docker-backed legs; SA135 E1's strict no-listener
window is complete and the standing state was restored exactly.

### Next action per lane

- **W2 — resume SA167c (#21) at E-closeout.** Retained product commit
  `91fd3bb6e6b638735361b511c1515cddccce5d15` accepts C's local/hosted gate surface and D's restored
  negative proof, aligns local-CI help with runtime stages, and fixes the coupled child-probe race.
  Do not reimplement A-D. Reconcile E, then run F's frozen-candidate release validation. W2 claims no
  standing service.
- **W1 — SA167d (#18) needs closeout, not re-implementation.** The sync is finished and `wt-track1`
  is level with `v88`, so freeze the candidate as it stands, run one Phase C validation campaign in
  order, then perform one terminal attestation **supplied with the complete base-to-tip patch as a
  file** — the missing input, not any finding, is what ungraded the last attempt.
- **W3 — SA135 (#15) closeout is unblocked; it is the lane head.** Sync `wt-track3` (27 behind)
  first. Removing the stale SA135-bound canary took away the only reason archiving was unsafe, so what
  remains is archive-and-G-FINAL, not a validation campaign:
  its E1/F evidence and returned-green Phase G campaign are accepted and must not be repeated. SA171
  (#28) stays the lane's fallback if SA135 stalls again — it is DB-free and needs no slot. Do not
  attempt SA170's E2E Docker work.

### Track readiness — the three states

A lane is **truly green** only when all three are yes. *Can start* = the next action is executable today.
*Can finish* = the ticket can reach a checked box using only work on its own lane. *Can merge* =
merge-back is not order-gated behind another lane.

| Lane | Head | Can start | Can finish | Can merge | On the critical path |
|---|---|---|---|---|---|
| **W2** | SA167c (#21) | **yes** — sync 23 commits of documentation, then revalidate C on the merged bytes | **yes** — C-F and the numbering advisory are W2-owned | **yes** — nothing is ordered ahead of #21 | **yes** — release-committed |
| **W1** | SA167d (#18) | **yes** — sync complete and tree clean; freeze, validate, attest | **yes** — its own acceptance and closeout are W1-owned | **yes** — no cross-lane branch-state gate remains | no |
| **W3** | SA135 (#15) | **yes** — sync, then closeout only; the canary blocker is gone | **yes** — archive, G-FINAL, convergence, attestation are all W3-owned | **yes** — nothing is ordered ahead of #15 | no |

**All three lanes are truly green.** Only **SA167c (#21)** is on the critical path and constitutes
real release progress; **SA167d (#18)** and **SA135 (#15)** are truly green but off it. **No lane is
blocked by another lane's ticket, and no ticket is blocked by a maintainer decision** — the five
settled on 2026-08-31 cleared the last one.

### Maintainer decisions

**Nothing is open for you.** Every lane can start, no ticket waits on an authorization or a plan
gate, and every remaining blocker is ordinary upstream work on its own lane. The five decisions
settled on 2026-08-31 — the `sqlparse` suppressions, `quickscale_devtools` publication, the
consistency test's canary reduction, the band-C displacement rule, and the permanence of the
privileged-command set — are archived with their full reasoning in
[CHANGELOG.md](../../CHANGELOG.md). Only their standing consequences live on here: in
[Standing rules](#standing-rules-carried-from-closed-decisions), in the shrunk SA174 and SA175
ticket bodies, and in the
[deliberately-not-ticketed table](#audit-items-deliberately-not-ticketed).

**One accepted red is scheduled rather than owned.** The four `sqlparse` CVE suppressions in
`scripts/security_suppressions.json` expire **2026-09-30**. `check_security_gates.py:545` compares
`expires` against `date.today()` and raises `GateError` on a stale entry — a pure date comparison
needing no scanner and no network — so from **2026-10-01** the security gate fails **locally as well
as in CI**, on the suppression file rather than on any finding, and it fails even if `sqlparse` is
patched. This is the one knowingly accepted red with no owning ticket. Nothing pins `sqlparse`
(Django's constraint is `>=0.5.0`, unbounded) and 0.6.0 is published, so a lockfile bump plus a
rescan is the cheap exit. **Revisit on 2026-09-30, not before.**

D3 and the placeholder-declaration policy remain settled and are not reopened here.

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
  No open ticket owns those settled surfaces; any exceptional touch must be announced in the merge
  queue.
- **Band-C filler must not displace a *runnable* band-B leg** (amended and settled 2026-08-31). A
  band-B leg halted on an open decision does not hold its lane idle; the intent is no queue-jumping
  ahead of work that could actually proceed. It briefly authorized SA171 (#28) to take W3's head while
  SA135 was halted; SA135 then became runnable, so #28 returned to its place. The rule is what keeps a
  decision-halted lane from idling next time.

### Merge order

One queue. Within a worktree, one reviewed child at a time; a ticket syncs the integration branch
into its worktree, resolves there, reruns its own verification, then merges its exact reviewed tip.

| # | Ticket | Band | Tier | Worktree | Merges after | Service slot |
|---|---|---|---|---|---|---|
| 15 | **SA135** | B | 2 | W3 | — | **yes** — PostgreSQL + Docker |
| 18 | **SA167d** | B | 3 | W1 | — | no |
| 19 | **SA161** | C | 3 | W1 | SA165 | no |
| 20 | **SA160** | C | 2 | W1 | SA161 | no |
| 21 | **SA167c** | B | 2 | W2 | — | no |
| 22 | **SA165** | C | 3 | W1 | SA167d | no |
| 24 | **SA166** | C | 3 | W2 | SA167c | no |
| 25 | **SA164** | C | 3 | W2 | SA166 | no |
| 27 | **SA170** | B | 2 | W3 | SA135 | **yes** — Docker |
| 28 | **SA171** | C | 2 | W3 | SA170 | no |
| 29 | **SA172** | C | 3 | W3 | SA171 | no |
| 31 | **SA174** | C | 3 | W1 | SA160 *(lane only)* | no |
| 32 | **SA175** | C | 3 | W1 | SA174 *(lane only)* | no |

No branch-state gate remains. Every entry above carries only its declared queue or content
dependency.

Positions #1, #2, #3, #4, #5, #6, #6b, #7, #8, #9, #10, #11, #12, #13, #14, #16, #17, #23, #26 are **retired and not
reused**; their tickets are closed and archived in [CHANGELOG.md](../../CHANGELOG.md). Gaps carry no meaning. Position
#15 carries SA135 alone; SA163 is closed and archived in [CHANGELOG.md](../../CHANGELOG.md).

The per-lane heads are **#21 (W2), #18 (W1), and #15 (W3)**. #21 has accepted A-D, including retained
product commit `91fd3bb6e6b638735361b511c1515cddccce5d15`; E closeout and F release validation remain
outstanding, so the retained checkpoint clears no gate. #18 is a
phase-E-accepted candidate on `wt-track1` at `0930b500`, awaiting a finished sync, one validation
campaign, and one attestation. #15 has accepted P/A/B/C/D/E0/E1/F evidence and a returned-green G
validation campaign, with archive-and-G-FINAL outstanding and **no blocker** since the stale
canary was removed.

Most "Merges after" edges are lane ordering — a queue position, clearable by the upstream work **or
by a maintainer reordering the lane**. Three are
**hard content dependencies** that no reorder clears: **SA160 after SA161** (shared emission-parity rebaseline of `sa90_emission_manifests.json`;
the pair must not be split, so the run is ordered #19, #20 — **SA174 left this run on 2026-08-31**
when the privileged-command set was settled as permanent and its emitted-byte change was dropped), **SA164's substance after SA167c** (its
`test_sa92_migration_squash_guardrail.py` work needs `django_apps:` retired). Band-C positions
(19, 20, 22, 24, 25, 28, 29, 31, 32) are *earliest-eligible*, not commitments, and may slip past the
release. **SA174 (#31) and SA175 (#32) are the two band-C positions worth pulling forward if slack
appears**: neither has a content dependency, neither needs an exclusive slot, and
SA174 is now a comment correction plus an audit demotion. #27 is band B — it discharges an obligation lifted out of #15 and may not be dropped.

### Shared conflict surfaces

Standing surface for every ticket: `CHANGELOG.md`, `docs/technical/roadmap.md`, and
`docs/technical/v88_ticket_context.md` when the ticket's concept notes change.

| Ticket | Additional shared surface | Why |
|---|---|---|
| SA167c | every `quickscale_modules/*/module.yml`, `scripts/gate_registry.json`, `scripts/{check,test}_module_app_declaration.py`, `scripts/test_gate_parity.py`, `scripts/{check_ci_locally.sh,sync_ci_gate_jobs.py}`, `Makefile`, `.github/workflows/ci.yml`, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` | retires the inert key and registers the declaration gate; **registry membership is why this is W2** |
| SA167d | `quickscale_cli/src/quickscale_cli/commands/module_config.py`, `docs/technical/module-extension.md` | CLI wiring drain; touched by no other v88 ticket |
| SA135 | `scripts/test_integration.sh`, `scripts/provision_test_roles.sh`, `scripts/provision_ci_postgres.sh`, `Makefile`, `docs/technical/validation_policy.md` | changes the documented local DB precondition |
| SA160, SA161 | generator templates + **SA90 emission-parity fixture**, `docs/others/tech-audit.md` | emitted output changes |
| SA164 | `docs/others/arch-audit.md`, `scripts/gate_registry.json`, `scripts/check_gate_parity.py`, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` | current watchlist discharge; **W2** — registry and the SA92 test are W2-owned, and it merges last |
| SA165 | `docs/others/tech-audit.md`, `quickscale_core/.../state_schema.py`, `scripts/test_isolation_conformance.sh`, `quickscale_core/tests/test_generator/test_generator.py`, `OPERATIONS.md.j2` | watchlist discharge; W1-isolated |
| SA166 | `scripts/gate_registry.json`, `Makefile`, CI workflow, `docs/others/tech-audit.md` | new process gate |
| SA170 | `quickscale_cli/src/quickscale_cli/utils/docker_utils.py`, `quickscale_cli/tests/test_e2e_development_workflow.py`, `quickscale_cli/tests/test_react_theme_e2e.py`, `scripts/test_e2e.sh`, `docs/others/tech-audit.md` | E2E Docker resource contract and failure diagnostics; **W3** — needs the exclusive Docker slot |
| SA171 | `quickscale_core/.../dr_engine/_lock.py`, `quickscale_core/.../advisory_lock.py`, `docs/others/tech-audit.md` | two hand-rolled file locks share one TOCTOU; **W3 fallback** — DB-free (both suites carry no `django_db` marker), so it needs no exclusive slot and can run if SA135 stalls again |
| SA172 | `quickscale_modules/orgs/.../tenancy.py`, `scripts/test_isolation_conformance.sh`, `docs/others/tech-audit.md` | RLS policy templates and their conformance assertion; **W3** — proved against a live PostgreSQL |
| SA174 | `quickscale_modules/orgs/.../apps.py`, `docs/others/arch-audit.md` | **shrunk 2026-08-31** to correcting the false SSOT comment and demoting the finding; no emitted bytes, no generator surface, no emission fixture |
| SA175 | `quickscale_cli/tests/test_beta_migration_ownership_conformance.py`, `quickscale_devtools/.../beta_migration.py`, `docs/others/arch-audit.md` | disposition-coherence assertion for the launcher↔settings contract; **W1** — no other open ticket touches either file |

Surfaces needing an explicit ordering note beyond the table:

- `scripts/gate_registry.json` — SA167c, SA166, SA164, all W2. **This surface never crosses
  worktrees**; that invariant is why SA167c could not move to W1 with the other wiring legs, and it
  applies equally to `quickscale_modules/*/module.yml`.
- `quickscale_core/contracts/` and `quickscale_core/manifest/` are settled cross-lane surfaces,
  shared by *behaviour* rather than by filename: every lane imports them. `entry_point.py`'s
  manifest-read behaviour and module-owned adapter registry stay settled tree state. `203fcd61` is
  the recorded precedent for what happens when this surface moves without a cross-lane announcement.
- `scripts/test_gate_parity.py` — **SA167c (#21, W2) owns it for the release**; its merged Phase-C
  delta rewrote 48 lines there to register the declaration gate. No other open ticket may touch it.
  The closed SA163 replaced its
  transcribed provisioning shell literal with a `describe --format json` binding plus an
  absence-of-the-old-shape assertion. That binding, the regenerated 24-entry publish oracle, and
  SA123's settled hosted-job, `needs`-edge, run-value, publish/E2E-path, and generator expectations
  are settled tree state and must be preserved by anything that touches the file.
- `.github/workflows/ci.yml` — **two W2 owners, sequenced.** SA167c's merged Phase-C delta added the
  declaration-gate job; SA166 (#24) registers a further gate after it. Merge order #21 before #24
  makes it one-directional. `scripts/provision_ci_postgres.sh` has **no open owner** after SA163
  closed, and neither ticket may reopen its provisioning stations.
- `.../settings/production.py.j2` — SA161 (#19, W1) is the only open owner. The privileged-command
  work moved out of SA164, so this file carries no #19-before-#25 cross-lane ordering caution.
- `scripts/test_isolation_conformance.sh` — three owners, all sequenced. SA163's merged edit is
  settled bytes; SA165 (#22, W1) applies its one-line skip-allowlist narrowing over them; SA172
  (#29, W3) adds a policy-text assertion in a different region and merges last.
- `sa90_emission_manifests.json` — SA161 then SA160, a pair since SA174 left the run. Each rebaseline appends its own
  `baseline_evidence` entry with per-file rationale; every prior entry must be preserved.
- `scripts/test_e2e.sh` — SA170 (#27, W3) is the only open owner, and touches the scope/cleanup side
  that SA135's merged provisioning work did not.

`docs/others/arch-audit.md` is on three surfaces: **SA174** (demotes
`privileged-command-set-multi-owner` from rank 1 to the watchlist, without closing
it), **SA175** (records rank-2's first step as discharged
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

- [ ] **SA167c — Retire `django_apps:` and gate the app declaration.** `Band B · Tier 2 · W2 · merge #21 · deps: none · closes the SA167 family`
  `django_apps:` was inert declarative surface: eleven manifests carried it, the loader parsed it,
  no production path read it, and one SA92 helper used it before falling back to a guessed path.
  **Acceptance:** `django_apps:` is either derived from the `apps` wiring projection or removed from all manifests, `ModuleManifest`, and the loader, with no key parsed-but-unread remaining; a conformance gate fails when a module ships models or a migration without declaring at least one Django app, registered in `scripts/gate_registry.json` and passing `scripts/check_gate_parity.py`; the gate is proved by deleting a module's app declaration and observing red, reverted before merge; `test_sa92_migration_squash_guardrail.py` no longer depends on the retired key.



  **State (measured 2026-09-01): retained partial checkpoint; A-D are accepted, E and F are
  outstanding.** Phase A's unchanged-candidate chain and Phase B's fail-hard declaration checker stay
  accepted. Phase C accepted the retained Make/registry/local/hosted/parity surface and aligned
  local-CI help with the runtime's eleven non-E2E stages plus optional stage twelve. Its focused suite
  passed 293 tests and the declaration, manifest-sync, parity, and hosted-generation checks. Phase D
  removed `social`'s sole `apps` projection under fail-safe restoration, observed the intended
  `missing apps declaration` exit 1, restored the exact blob, and returned both declaration and
  manifest-sync gates green with no persistent manifest delta.
  A task-gate run then exposed a pre-existing xdist-only child process-group probe race. Serial
  convergence fixed that coupled lifecycle defect and passed 326 focused task tests plus the four gate
  checks. Terminal review found one high-normal-exit classification gap; the bounded remediation now
  preserves explicit exit 200 and real signal status, with 35 lifecycle tests green. That final
  correction is ***applied after terminal attestation — not independently graded***.
  The retained product object is `91fd3bb6e6b638735361b511c1515cddccce5d15`. It is partial delivery,
  keeps SA167c open at #21, leaves SA166 dependent, and clears no release gate.
  **Outstanding: E-closeout, then F-frozen-candidate release validation.** E was not dispatched after
  the inherited task gate halted the forward chain; although convergence corrected that gate defect,
  the closed implementation stage was not re-entered. F depends on E. Release readiness remains
  unestablished because `make ci-e2e` has not run.
  **Decisions needed:** none. D3 and the declaration source authority are settled; see
  [decisions.md → Module Presence States](decisions.md#module-presence-states). No PostgreSQL
  scheduling decision is required — W2's only cluster-addressed command runs through
  `provision_ci_postgres.sh run --profile restricted`, a private ephemeral server.
  **Remaining plan (serial; do not reimplement A-D).** Reviewed plan authority `EV-4` covers phases
  C-F; C and D are accepted. The first resumable phase is E because all of its dependencies are
  accepted. If that reference no longer resolves, this paragraph is the cold-start resume object and
  fresh reviewed-plan authority must preserve the accepted A-D boundary.
  1. **E-closeout.** Reconcile decisions, implementation contract, validation policy, ticket context,
     docs index, roadmap queue/counts, and changelog evidence. Retain the SA164 and SA166 boundaries.
     Record the retained product object and the not-independently-graded terminal correction without
     claiming release readiness.
  2. **F-frozen candidate.** Resync current `v88`, freeze one clean candidate, run the release campaign
     once including `make ci-e2e`, then serial convergence and patch-backed terminal attestation before
     closeout. Merge only the attested exact tip.
  **The key itself is already gone.** `grep -rn django_apps` over `quickscale_core`,
  `quickscale_modules`, and `quickscale_cli` returns nothing (verified 2026-08-31): the manifests,
  `ModuleManifest`, the loader, and the SA92 helper are all clear. That half of the acceptance is
  discharged and `quickscale_core/manifest/` is off this ticket's forward surface; what remains to
  prove is the gate.
  **Constraints.** SA167c must not edit `TestRegenerateManagedWiringSkipManifestNotFound` or the
  `commands/test_module_config_extended.py` fixtures — both are green on `v88` and are no longer an
  oracle for this ticket — and must not touch `quickscale_core/contracts/` or
  `quickscale_core/manifest/`.
  **Retained-delivery boundary:** keep product object
  `91fd3bb6e6b638735361b511c1515cddccce5d15`; a continuation builds E/F on that object rather than
  rewinding or recreating accepted phases.
  **Shared conflict surface:** every `quickscale_modules/*/module.yml`, `scripts/gate_registry.json`, `scripts/{check,test}_module_app_declaration.py`, `scripts/test_gate_parity.py`, `scripts/{check_ci_locally.sh,sync_ci_gate_jobs.py}`, `Makefile`, `.github/workflows/ci.yml`, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`.

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
  **State (measured 2026-08-31): retained partial checkpoint; phases A-E accepted at E0_ACCEPTED_TIP;
  current closeout phases A and B are accepted, and closeout Phase C is outstanding.**
  E0 tip `bd2c291ba2d40494970464741ac51bfd45445a19` made no tracked edits and records the accepted
  E0 history; those facts are historical evidence only. Retained-partial convergence and terminal
  attestation are complete over the reviewed tree
  `542dcc5130cbe2093f19a8a3a603248f295a84cc`, and **retained-partial-only merge-back is authorized — and
  now performed**: retained product object `0930b50049eed83fb86f19dde55d7c2488b477bd` and the latest-v88 status
  reconciliation are merged, so `wt-track1` is clean and level with `v88` at `c0ebf34b`. The merge
  retains SA167d as open at #18, and **SA165 remains dependent**; it does not imply Phase C acceptance,
  ticket completion, or release green. No product defect remains open from the partial attestation.
  **What is outstanding is one thing: Phase C, run whole.** The prior attempt went green on the focused
  suite and the consistency suite, then stopped at `make lint` over a Ruff formatting defect that is now
  corrected. It never reached `make typecheck`, `make check`, `make test`, `make quality`, the
  conditional evidence/status transition, or the final integration-ready consistency check, so its green
  prefix is not reusable and the phase restarts from its first command.
  Completion-grade Phase C validation, convergence, terminal attestation, and exact-tip
  integration remain pending; the partial convergence and attestation above do not discharge them. The
  accepted-open operational checkpoint stays in force until the exact attested tip integrates.
  **Decisions needed:** none.
  **Remaining plan.** Reviewed plan authority `EV-6` covers closeout phases A-C; A and B are accepted
  and must not be redone. On one frozen candidate — `wt-track1` as it stands, since no sync is owed —
  run in order: the five-file focused suite, the accepted-open consistency suite, `make lint`,
  `make typecheck`, `make check`, `make test`, `make quality`. Only when all are green, author the
  conditional post-integration ledger image and run the final consistency check. Then perform fresh
  completion-grade convergence and terminal attestation over a **complete base-to-tip patch supplied as
  a file**, and integrate only that exact tip. No post-attestation edit is allowed. Launch `make test`
  and `make quality` detached per the execution rules. If `EV-6` no longer resolves, this paragraph is
  the cold-start resume object and the next run must obtain fresh reviewed-plan authority without
  redoing A and B.
  **Shared conflict surface:** `quickscale_cli/src/quickscale_cli/commands/module_config.py`, `docs/technical/module-extension.md`, plus the ledger-reconciliation files listed above.

- [ ] **SA135 — Give test suites an owned PostgreSQL lifecycle.** `Band B · Tier 2 · W3 · merge #15 · deps: none · PostgreSQL + Docker slot`
  Provision and tear down the server used by repository gates; replace the former out-of-band host
  assumption while retaining an asserted unavailability negative control.
  **Acceptance:** the integration gate provisions its own PostgreSQL 18 server and tears it down,
  with no reliance on a pre-existing host server; the `LOGIN CREATEDB NOINHERIT NOBYPASSRLS
  NOSUPERUSER` role contract is preserved; the asserted-unavailability negative control still fails
  loudly when the server cannot be provisioned, rather than skipping; `make test-integration` passes
  on a machine with no PostgreSQL running; [validation_policy.md](validation_policy.md) records the
  owned local lifecycle; image identity follows the settled content-addressed backend-image convention.
  **State (measured 2026-08-31): phases P/A/B/C/D/E0, E1 and F are accepted, and Phase G's
  synchronized validation campaign returned all eleven commands green.** `wt-track3` is clean at
  `c78d9957`, **0 ahead / 27 behind `v88`**; its accepted E1/F delta is merged. E1 proved the owned
  dynamic-loopback lifecycle with the standing listener absent, the restricted role contract intact,
  exact-scope cleanup, a loud denied-provisioning failure, and exact restoration of the standing
  container, image, mount, twelve database owners, and role tuple. All of that evidence, plus the E2
  scope transfer to SA170, is archived in [CHANGELOG.md](../../CHANGELOG.md). **G-FINAL did not run,
  so SA135 stays open and unchecked.**
  **What remains is closeout reconciliation and G-FINAL, not another validation campaign.** Do not
  repeat Phase G, E1/F, C, or D; do not reopen `.github/workflows/`, `scripts/provision_ci_postgres.sh`,
  or `scripts/test_gate_parity.py`; and do not run the full E2E campaign — it is SA170's.
  **The closeout blocker is gone (2026-08-31).** Removing SA135 used to make an expected-red canary
  stale, because that canary mutated a hardcoded dependency literal naming this ticket; the previous
  closeout attempt was rolled back over it. The consistency-test reduction removed that obsolete
  SA135-bound mutation source, and the reconciled suite routes its unknown-dependency mutation through
  SA167d instead. **Nothing goes stale when SA135 is archived and no reviewed-plan scope extension is
  owed.**
  **Remaining plan (serial).** Sync `wt-track3` to `v88` (27 behind, clean, nothing ahead — no retained
  object needs re-merging). Then, in one change: archive SA135 to the changelog, remove it from this
  file, and clear SA170's dependency, re-running
  `poetry run pytest quickscale_core/tests/test_v88_ticket_context_consistency.py -q -o addopts= --no-cov`
  in that same change. Then run G-FINAL once on the unchanged closeout candidate, followed by serial
  convergence, a materialized complete patch, and one patch-backed terminal attestation. No
  implementation phase is re-entered after convergence.
  **Decisions needed:** none.
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
  **Absorbed from SA135 — the full E2E campaign.** `QS_E2E_PARALLEL=0 make test-e2e` followed by
  `make ci-e2e` on an unchanged tree, with exact cleanup and PostgreSQL baseline equality, is **SA170's
  final acceptance** and runs *after* the three fixes above, where the result is interpretable. It must
  also clear the four `e2e` rows listed in *Unfiltered-suite rows*, which are this ticket's. The transfer
  rationale is archived in [CHANGELOG.md](../../CHANGELOG.md).
  **Shared conflict surface:** `quickscale_cli/src/quickscale_cli/utils/docker_utils.py`, `quickscale_cli/tests/test_e2e_development_workflow.py`, `quickscale_cli/tests/test_react_theme_e2e.py`, `scripts/test_e2e.sh`, `docs/others/tech-audit.md`.

- [ ] **SA160 — Share one correct CSRF-token helper in the React theme.** `Band C · Tier 2 · W1 · merge #20 · deps: SA161 (emission-parity ordering)`
  Closes tech-audit **TA67** (`spa-csrf-token-duplicate-cookie`, S3) — the only finding in deployment reality #3, the internet-facing generated project. `themes/showcase_react/src/hooks/useApi.ts:20-28` and `src/components/forms/FormRenderer.tsx:206-211` carry the same eleven lines: the parser splits `document.cookie` on `"; csrftoken="` and accepts the result **only when it yields exactly two parts**. Two `csrftoken` cookies yield three, so `getCsrfToken()` returns `''`, `buildRequestHeaders` (`:89-94`) skips `X-CSRFToken`, and Django rejects every POST/PUT/PATCH/DELETE with 403. The triggering state is ordinary: an `app.example.com` deployment alongside a `.example.com` cookie, the outcome of setting or changing `CSRF_COOKIE_DOMAIN`, of a sibling Django app on another subdomain, or of a stale apex-scoped cookie. GETs keep working, so the app looks alive and merely refuses to save, and no error names the cause. Fails closed — availability, not a security hole. There is no shared CSRF helper, no fetch interceptor, and no template-injected token, so no layer-up guard exists.
  **Acceptance:** one shared helper in `src/lib/` iterates cookies rather than counting split segments — splitting on `'; '`, matching the name exactly, and `decodeURIComponent`-ing the value, per Django's own documented `getCookie` — and both call sites import it with no third variant remaining; a `vitest` table test covers `'csrftoken=A; csrftoken=B'`, `'sessionid=x; csrftoken=A'`, `'csrftoken=A'`, and `''`, with the first three returning a non-empty token; the tech-audit finding is retired.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/`, generator emission parity baselines, `docs/others/tech-audit.md`.

- [ ] **SA161 — Remove the dead `get_client_ip` definitions from generated settings.** `Band C · Tier 3 · W1 · merge #19 · deps: SA165 (worktree ordering)`
  Closes tech-audit **TA68** (`generated-settings-dead-client-ip`, S4). `templates/project_name/settings/base.py.j2:61` and `settings/production.py.j2:123` both define a module-level `get_client_ip(request)`, and the production copy rebinds it under a comment claiming the rebind exists "so that production defaults … are actually in effect at request time". Neither is reachable: Django's `Settings` copies only **uppercase** names off the settings module, so `django.conf.settings.get_client_ip` does not exist, and grep across all templates returns only the two definitions. The live implementation is `quickscale_modules_orgs.current_org.get_client_ip`, which reads the uppercase `USE_X_FORWARDED_FOR` / `TRUSTED_PROXY_COUNT` settings dynamically and is correct.
  **Acceptance:** both definitions are deleted, or each carries a comment pointing at the orgs helper as the live implementation; the uppercase settings and the `REST_FRAMEWORK["NUM_PROXIES"]` recomputation are retained unchanged; the misleading behavioural comment at `production.py.j2:119-122` is removed either way; a generated project boots and proxy-aware client-IP resolution is unchanged, asserted by a test; emission parity is rebaselined with rationale; the tech-audit finding is retired.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/`, emission parity baselines, `docs/others/tech-audit.md`.

- [ ] **SA174 — Correct the false SSOT claim on the privileged-command set.** `Band C · Tier 3 · W1 · merge #31 · deps: none · shrunk 2026-08-31`
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
  **Consequences of the shrink, reconciled below:** SA174 leaves the ordered `#19 → #20 → #31`
  rebaseline run, which is now the pair `#19 → #20`; it no longer touches
  `.../settings/production.py.j2`, which now has SA161 as its only open owner; its dependency on SA160
  is also dropped.
  **Shared conflict surface:** `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py`, `docs/others/arch-audit.md`.

- [ ] **SA175 — Assert disposition coherence for the launcher↔settings contract.** `Band C · Tier 3 · W1 · merge #32 · deps: none · bounded first step only; does not widen into the deferred finding`
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
  **Its dependency on SA174 is gone (2026-08-31).** The audit's ordering argument was: consolidate
  the command set first, then reference the now-single declaration. Settling the set as permanent cancelled that
  consolidation, so there is no single declaration to source from and **this ticket names its own
  three participating paths**. SA175 now has no content dependency on anything; it keeps merge
  position #32 by lane ordering alone and could be pulled forward if W1 finds slack.
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
  - **SA92 migration-squash discovery tuple — artifact located 2026-08-21, now evaluable.** The audit recorded this as unlocatable, but the artifact is `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` — a bounded literal tripwire for cross-table `UPDATE … SET organization_id` DML in migrations. The prior search missed it because it grepped for `squash` in source rather than in test filenames. SA167c's merged partial removed the helper's dependency on the retired `django_apps:` key; `_migdir()` still uses the conventional path and returns `None` when it is absent, so SA164 must make that lookup fail hard rather than silently skipping a module. Its authoritative backstop is also still a catalog/data parity gate anchored to `v87`, a retired release ref no longer resolved by the quality gate.
  - **Privileged-command set — promoted out of the watchlist and out of this ticket.** The
    2026-08-28 structural pass promoted it to the arch audit's **rank-1 finding**
    (`privileged-command-set-multi-owner`), counting four independent owners of one security-relevant
    command set. It is no longer a watch item and is no longer SA164's: **SA174 (#31, W1)** owns it.
    SA164 must not edit `.../settings/production.py.j2`, `orgs/apps.py`,
    `development_commands.py`, or `start.sh.j2` — that removes this ticket's only cross-lane file
    surface.
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

- [ ] **SA171 — Make stale-lock clearing atomic in both file locks.** `Band C · Tier 2 · W3 · merge #28 · deps: SA170 (worktree ordering) · DB-free; needs no exclusive slot`
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
| Tooling gaps — dependency-vulnerability scanner, security static analysis | tech | Closed by SA123's implemented and accepted Trivy/Bandit gates; evidence archived in [CHANGELOG.md](../../CHANGELOG.md). |
| Watch items recorded as deliberate | tech *Notes* | Integration-branch CI, generator lock-generation policy, the DB-free healthcheck, CRM/billing cross-tenant `all_objects` count fallbacks, and rename-atomic-but-not-durable state writes are each argued and accepted in the audit; re-examine only on the triggers stated there. |
| Four suppressed `sqlparse` CVEs | tech *Notes* | **Settled 2026-08-31: left as-is by explicit decision.** `CVE-2026-54284/-59893/-71491/-59894` expire **2026-09-30**; from **2026-10-01** `check_security_gates.py:545` raises `GateError` on the stale entries — a pure date check, so it fails locally as well as in CI, on the file rather than on any finding. This is the one knowingly accepted red with no owning ticket. Revisit on the expiry date. |
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
