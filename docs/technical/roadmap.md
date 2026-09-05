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
| **B — Release work on the critical path** | The serialized release-verdict chain. | **Empty — SA167c is archived green.** |
| **C — Bounded independent fixes** | No dependants, small blast radius; absorbed as slack filler. | SA160, SA161, SA164, SA165, SA166, SA171, SA172, SA174, SA175 |

### Dependency graph and critical path

```text
v88 — three worktrees, nine open merge positions carrying nine open ticket entries, one merge queue

W2 (gates & declared wiring)   ★ band-C tail
  SA166 ─► SA164                #24, #25
  SA174 · SA175                #31, #32

W1 (module wiring + generated-output fixes)
  SA165 ─► SA161 ─► SA160      #22, #19, #20

W3 (service lifecycle — exclusive PostgreSQL/Docker slot)
  SA171 ─► SA172                           #28, #29
  (SA171 is DB-free and now heads W3)
```

**Position numbers are identifiers, not run order.** W2's remaining order is #24, #25, and the
#31/#32 tail. **SA174 and SA175 remain W2 tail by current lane ordering; the band-C displacement
rule imposes no present constraint because no runnable band-B leg remains.**

The release-committed SA167c verdict is green and archived. W2 now carries the four-position
band-C queue `SA166 ─► SA164` with SA174 and SA175 as its tail. W3 holds the exclusive slot and
takes scheduling priority while one of its Docker-backed legs is active, but its two positions are a *queue*,
not a chain. No open ticket now sets the release date; W1's three positions, W2's four
positions, and W3's two positions are band-C work.

**No cross-worktree ticket or release-gate blocker remains.** One cross-worktree *shared file* does,
made one-directional by merge order: `scripts/test_isolation_conformance.sh` (SA135's merged
partial wrote it; SA165's retained product edit is awaiting closeout before the remaining W1 pair).
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

### Track rebalance — settled lane assignment

Lanes are **W1 3 · W2 4 · W3 2**, and every open ticket carries a track — none lacks one. Each was
tested against the three questions: is it independent of the rest of its lane, is another lane idle,
and is it on or feeding the critical path. **No move is proposed.** The remaining W2 queue is
lane-ordered band-C work, so no relocation of it can shorten the release path.

**SA174 (#31) and SA175 (#32) sit on W2 by a confirmed decision (2026-09-04), not a provisional
one.** Both are `deps: none` and DB-free, neither touches `scripts/gate_registry.json`,
`quickscale_modules/*/module.yml`, `quickscale_core/contracts/`, or `quickscale_core/manifest/`, and
neither shares a code file with any W2 ticket — SA174 owns `quickscale_modules/orgs/.../apps.py`,
SA175 owns `quickscale_devtools/.../beta_migration.py` and its conformance test, and no other open
ticket touches any of the three. The assignment keeps `docs/others/arch-audit.md` **single-lane and
one-directional** (its three owners SA174, SA175, and SA164 are all W2, running #31 → #32 with #25
merging later) and leaves W1 as one coherent generated-output chain, #22 ─► #19 ─► #20. No code file
carries a second lane and no merge hazard exists. The assignment stands on that permanent
conflict-surface gain rather than on the idle-lane condition that produced it. **SA174 and SA175 remain W2 tail by current lane
ordering; the band-C displacement rule imposes no present constraint because no runnable band-B leg
remains.**

**The moves that do not stand, for structural reasons rather than situational ones:**

- **`scripts/gate_registry.json` and `quickscale_modules/*/module.yml` never cross worktrees.** The
  remaining gate tickets on W2 register or edit gate-registry entries, so none of them may leave W2
  and nothing carrying a registry edit may enter another lane.
- **W1's `sa90_emission_manifests.json` rebaseline is one ordered pair** (#19 → #20) and may not be
  split, and SA165 (#22) precedes it by lane order.
- **SA165 (#22) stays on W1.** Its product changes are retained and its only pending acceptance is
  the final-candidate release verdict. Moving a validation-only closeout buys no critical-path time.
- **SA171 (#28) stays on W3.** It is structurally legal anywhere — DB-free, no shared file, no
  `contracts/`/`manifest/` touch — but it defines the advisory-lock topology that SA172 follows, so
  keeping both on W3 avoids a context handoff. Verified against the tree: `quickscale_core/advisory_lock.py` and
  `quickscale_core/dr_engine/_lock.py` and their suites carry no `django_db` marker and no
  PostgreSQL reference, so **it needs no exclusive slot** and no re-analysis is owed.

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

- **W2 — start SA166 (#24).** SA167c's phases A-E and sole authorized Phase-F release verdict are
  complete on the retained product/frozen-base evidence archived in [CHANGELOG.md](../../CHANGELOG.md).
  SA166 now has `deps: none` and is the W2 head; SA164 remains after SA166, with SA174 and SA175
  as the band-C tail. W2 claims no standing service.
- **W1 — retain SA165 (#22).** Phase D reconciliation is integrated; one-run authority is granted as
  `EV-8`, and the next action is SA165-R1 independent review followed by the single authorized
  final-candidate verdict. SA167d's
  completion-grade closeout is archived as a conditional post-integration candidate; SA165 has
  `deps: none`, remains W1-owned, and its phases A-C are accepted on retained product object
  `573a57a34301e6a91971a7845095bd913bebd5e1`, merged at `3f925b96`. The final-candidate release
  verdict is still outstanding.
- **W3 — start SA171 (#28).** SA170's final acceptance is archived in `CHANGELOG.md`; do not reopen
  its release campaign. SA171 has `deps: none`, is DB-free, and leaves the exclusive service slot
  available for SA172.

### Track readiness — the three states

A lane is **truly green** only when all three are yes. *Can start* = the next action is executable today.
*Can finish* = the ticket can reach a checked box using only work on its own lane. *Can merge* =
merge-back is not order-gated behind another lane.

| Lane | Head | Can start | Can finish | Can merge | On the critical path |
|---|---|---|---|---|---|
| **W2** | SA166 (#24) | **yes** — `deps: none` and its work is W2-owned | **yes** — no upstream ticket remains | **yes** — nothing is ordered ahead of #24 | no |
| **W1** | SA165 (#22) | **yes** — `deps: none`; Phase D reconciliation is integrated; one-run authority is granted as `EV-8`, and the next action is SA165-R1 independent review followed by the single authorized final-candidate verdict | **no** — the `EV-8`-authorized final-candidate release verdict has not yet returned green | **yes after a green verdict** — no cross-lane blocker remains | no |
| **W3** | SA171 (#28) | **yes** — `deps: none` and DB-free | **yes** — all work is W3-owned | **yes** — no ticket is ordered ahead of #28 | no |

**W2 and W3 are truly green; W1 can start but cannot finish until SA165's `EV-8`-authorized
final-candidate verdict returns green.** W1's remaining blocker is now empirical rather than a
maintainer decision. No open ticket is on the release critical path.
All three lanes carry only independent or lane-ordered band-C work. SA174 and SA175 stay on W2 as its
tail.

### Maintainer decisions

**No maintainer decision is open anywhere in the v88 queue.** The last one was granted on
2026-09-05 as **`EV-8`**: exactly one replacement `QS_E2E_INTEGRATION_REF=v88 make ci-e2e` verdict
over SA165's settled six-file Phase D candidate, frozen at the moment `wt-track1` syncs. `EV-8`
authorizes that one verdict and nothing else — not a second run, not redoing accepted A-C (which
stay bound to `EV-2` and to retained product object
`573a57a34301e6a91971a7845095bd913bebd5e1`), and not reusing the earlier stale-but-green run as
acceptance. A red or unreturned result requires a repair ticket and then fresh authority. The run
must be detached under `setsid` with its exit code captured atomically to a file, per the standing
rule that a cutoff-killed run is not evidence. W1's remaining question is therefore empirical:
whether the authorized command returns green.

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
| 22 | **SA165** | C | 3 | W1 | — | no |
| 24 | **SA166** | C | 3 | W2 | — | no |
| 25 | **SA164** | C | 3 | W2 | SA166 | no |
| 28 | **SA171** | C | 2 | W3 | none | no |
| 29 | **SA172** | C | 3 | W3 | SA171 | no |
| 31 | **SA174** | C | 3 | W2 | — *(band-C tail)* | no |
| 32 | **SA175** | C | 3 | W2 | SA174 *(lane only)* | no |

Entries carry their declared queue or content dependencies, subject to fresh branch remeasurement
before execution.

Positions #1, #2, #3, #4, #5, #6, #6b, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #21, #23, #26, #27 are **retired and not
reused**; their tickets are closed and archived in [CHANGELOG.md](../../CHANGELOG.md). Gaps carry no meaning.

The per-lane heads are **#24 (W2), #22 (W1), and #28 (W3)**. SA167c's #21 release verdict is
complete and archived; #24, #22, and #28 are eligible with `deps: none`.

Most "Merges after" edges are lane ordering — a queue position, clearable by the upstream work **or
by a maintainer reordering the lane**. Two are
**hard content dependencies** that no reorder clears: **SA160 after SA161** (shared emission-parity rebaseline of `sa90_emission_manifests.json`;
the pair must not be split, so the run is ordered #19, #20), **SA164's substance after SA166** (its
`test_sa92_migration_squash_guardrail.py` work needs `django_apps:` retired). Band-C positions
(19, 20, 22, 24, 25, 28, 29, 31, 32) are *earliest-eligible*, not commitments, and may slip past the
release. **SA174 (#31) and SA175 (#32) are W2 tail work**: neither has a content dependency and
neither needs an exclusive slot.

### Shared conflict surfaces

Standing surface for every ticket: `CHANGELOG.md`, `docs/technical/roadmap.md`, and
`docs/technical/v88_ticket_context.md` when the ticket's concept notes change.

| Ticket | Additional shared surface | Why |
|---|---|---|
| SA160, SA161 | generator templates + **SA90 emission-parity fixture**, `docs/others/tech-audit.md` | emitted output changes |
| SA164 | `docs/others/arch-audit.md`, `scripts/gate_registry.json`, `scripts/check_gate_parity.py`, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` | current watchlist discharge; **W2** — registry and the SA92 test are W2-owned, and it merges last |
| SA165 | `docs/others/tech-audit.md`, `quickscale_core/.../state_schema.py`, `scripts/test_isolation_conformance.sh`, `quickscale_core/tests/test_generator/test_generator.py`, `OPERATIONS.md.j2` | retained watchlist discharge; final-candidate release verdict pending on W1 |
| SA166 | `scripts/gate_registry.json`, `Makefile`, CI workflow, `docs/others/tech-audit.md` | new process gate |
| SA171 | `quickscale_core/.../dr_engine/_lock.py`, `quickscale_core/.../advisory_lock.py`, `docs/others/tech-audit.md` | two hand-rolled file locks share one TOCTOU; **DB-free** (both suites carry no `django_db` marker), so it needs no exclusive slot |
| SA172 | `quickscale_modules/orgs/.../tenancy.py`, `scripts/test_isolation_conformance.sh`, `docs/others/tech-audit.md` | RLS policy templates and their conformance assertion; **W3** — proved against a live PostgreSQL |
| SA174 | `quickscale_modules/orgs/.../apps.py`, `docs/others/arch-audit.md` | **shrunk 2026-08-31** to correcting the false SSOT comment and demoting the finding; no emitted bytes, no generator surface, no emission fixture |
| SA175 | `quickscale_cli/tests/test_beta_migration_ownership_conformance.py`, `quickscale_devtools/.../beta_migration.py`, `docs/others/arch-audit.md` | disposition-coherence assertion for the launcher↔settings contract; **W2** — no other open ticket touches either file |

Surfaces needing an explicit ordering note beyond the table:

- `scripts/gate_registry.json` — SA166 and SA164, both W2. **This surface never crosses
  worktrees**; that invariant keeps the remaining gate work on W2, and applies equally to
  `quickscale_modules/*/module.yml`.
- `quickscale_core/contracts/` and `quickscale_core/manifest/` are settled cross-lane surfaces,
  shared by *behaviour* rather than by filename: every lane imports them. `entry_point.py`'s
  manifest-read behaviour and module-owned adapter registry stay settled tree state. `203fcd61` is
  the recorded precedent for what happens when this surface moves without a cross-lane announcement.
- `scripts/test_gate_parity.py` — SA167c's retained Phase-C delta rewrote the declaration-gate
  oracle; no remaining open ticket may touch it.
  The closed SA163 replaced its
  transcribed provisioning shell literal with a `describe --format json` binding plus an
  absence-of-the-old-shape assertion. That binding, the regenerated 24-entry publish oracle, and
  SA123's settled hosted-job, `needs`-edge, run-value, publish/E2E-path, and generator expectations
  are settled tree state and must be preserved by anything that touches the file.
- `.github/workflows/ci.yml` — **SA166 is the remaining W2 owner.** SA167c's retained Phase-C delta
  added the declaration-gate job; SA166 (#24) registers a further gate. `scripts/provision_ci_postgres.sh` has **no open owner** after SA163
  closed, and neither ticket may reopen its provisioning stations. Its immediate-child status/cleanup
  path was last corrected inside SA167c's already-merged `91fd3bb6`; a lane seeing it red is behind
  current `v88`, not looking at an open defect.
- `.../settings/production.py.j2` — SA161 (#19, W1) is the only open owner. The privileged-command
  work moved out of SA164, so this file carries no #19-before-#25 cross-lane ordering caution.
- `scripts/test_isolation_conformance.sh` — SA163's merged edit is settled bytes; SA165's retained
  identity-based skip narrowing closes first on W1; SA172 (#29, W3) adds a policy-text assertion in
  a different region and merges last.
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

- [ ] **SA165 — Discharge the tech-audit watch items that carry an action.** `Band C · Tier 3 · W1 · merge #22 · deps: none`
  Four action-bearing notes are implemented in retained A-C product object
  `573a57a34301e6a91971a7845095bd913bebd5e1`: state consolidation fails hard on corrupt and
  non-mapping YAML roots without changing the file; isolation-skip authorization is bound to the two
  intended test identities with a red negative control; `_HOST_DEPENDENT_PATHS` records its `.env`
  rationale and escalation rule; and generated `OPERATIONS.md` warns that predictable local
  credentials must not survive into shared environments. Focused A-C evidence and the retained-only
  integration are archived in [CHANGELOG.md](../../CHANGELOG.md); do not redo those phases.

  **State (measured 2026-09-05): integrated retained Phase D candidate; final-candidate release
  verdict outstanding.** The retained A-C product and the six current closeout files reconcile the
  audit, current queue, context, docs hub, changelog, and executable consistency contract. The sole
  SA165 release run returned exit 0 with Core 38 passed and CLI 54 passed, but `CHANGELOG.md` changed
  afterward. It therefore does not cover the settled candidate and closes neither SA165 nor its four
  audit notes. SA165-R1 remains tracked for independent review of the reconciled temporal lane-state
  handoff; lane state must be remeasured at action time rather than persisted as a current merge
  assertion.

  **Pending, in order.** (1) Obtain independent review of the reconciled candidate (SA165-R1).
  (2) Freeze the final candidate and rerun the focused context suite. (3) Spend **`EV-8`** — the
  single replacement `QS_E2E_INTEGRATION_REF=v88 make ci-e2e` verdict granted 2026-09-05 — launching
  it under `setsid` with its exit code captured atomically to a file, and retain exact
  cleanup/provenance evidence. A green verdict permits completion-grade convergence, patch-backed
  terminal attestation, exact-tip integration, audit-note retirement, and #22 retirement. A red or
  unreturned verdict keeps this checkpoint open and requires a repair ticket plus fresh authority;
  `EV-8` covers no second run.

  **Remaining reviewed plan and handoff.** Plan authority `EV-2` remains binding. Resume from the
  retained product object and the present six-file Phase D candidate: `CHANGELOG.md`, `docs/index.md`,
  `docs/others/tech-audit.md`, `docs/technical/roadmap.md`,
  `docs/technical/v88_ticket_context.md`, and
  `quickscale_core/tests/test_v88_ticket_context_consistency.py`. Review the SA165-R1 temporal
  handoff, then spend `EV-8` on the release-verdict step. Preserve historical SA170 and
  SA167c/SA167d evidence, do not reopen A-C product files, and do not alter SA172's later ownership
  of the isolation script.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/schema/state_schema.py`, `scripts/test_isolation_conformance.sh`, `quickscale_core/tests/test_generator/test_generator.py`, `quickscale_core/.../templates/OPERATIONS.md.j2`, `docs/others/tech-audit.md`.

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

- [ ] **SA166 — Require a testimony trail for behavioural commits.** `Band C · Tier 3 · W2 · merge #24 · deps: none`
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
