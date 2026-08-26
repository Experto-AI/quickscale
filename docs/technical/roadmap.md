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
- **W1's wiring legs (SA167b, SA167d) may not touch `scripts/gate_registry.json` or any `module.yml`.** Both are W2-owned surfaces — SA167c is on W2 for exactly that reason. The wiring legs have no open cross-worktree edge: the `entry_point.py` handoff is settled tree state.
- A ticket whose deliverable is Git ref state cannot be delegated to a file-editing worker. Route it to a maintainer session with ref authority and push credentials.

---

## v88 release plan

### Prioritization decision (recorded 2026-08-21)

**Choice: neither.** Architectural Findings 2 (deletion-cleanup coordination), 4 (organization purge ordering), and 7 (generated-file ownership) stay behind their growth triggers. No `teams` domain work and no third generated-project updater is scheduled for v88. This is consistent with the standing decision that `teams` is not planned, and it keeps v88 free of speculative architecture. The implementation tickets are planned on their own merits below, in one queue with the audit-derived tickets.

Consequence for the gated findings: they remain live in [arch-audit.md](../others/arch-audit.md) and are **not** closed by any v88 ticket. A v88 ticket may not widen into them; if implementation work discovers a trigger has actually fired, that is a scope finding and gets its own ticket rather than an in-place fix.

The priority model, dependency graph, acceptance criteria, and worktree/merge-order assignment below are the authoritative plan. (v88 planning is closed; see [CHANGELOG.md](../../CHANGELOG.md).)

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
| **B — Release work on the critical paths** | The two longest serialized chains, one of which holds the exclusive service slot. | SA118 → SA167c (critical path); SA135 (+ SA163); SA167b → SA167d |
| **C — Bounded independent fixes** | No dependants, small blast radius. Absorbed as slack filler by whichever worktree finishes a band-B leg early. | SA160, SA161, SA164, SA165, SA166 |

**Standing consequences of that rule:**

- **Band A is clear.** The shared lifecycle fixture repair passed the complete ordered campaign;
  `make check`, `make test`, and `make quality` are green, and the completion evidence is archived
  in [CHANGELOG.md](../../CHANGELOG.md). No open ticket is permitted to waive these gates.
- **The critical path is on the gate track, not the service track.** W2's remaining band-B spine
  (`SA118 → SA167c`) is two serialized merge legs with no
  prerequisite outside W2. W3 keeps the exclusive PostgreSQL/Docker slot and
  therefore keeps scheduling priority *while a leg is active*, but it is no longer the
  longest chain and no longer sets the release date.
- **The `make quality` baseline is fixed.** `make quality` runs and reports zero warning and
  zero critical regressions with monotonicity passing; the generated quality report is the
  current evidence for that state.
- **SA164 sits on W2, not W1.** It edits `scripts/gate_registry.json` and
  `scripts/check_gate_parity.py` — both W2-only surfaces — and
  `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`, which SA167c
  (W2) rewrites first. Keeping it on W2 preserves the "the registry never crosses
  worktrees" invariant; as band-C tail (#25) it adds nothing to the critical path. Its
  `deps: SA166` (W2) edge is the remaining ordering dependency and keeps SA164 at the tail.
- **The remaining SA167 family is in v88 (decision 2026-08-21).** The five hand-written app
  declarations are already manifest-owned and core reads their projections; that is settled tree
  state. The remaining SA167b/SA167c/SA167d work is deliberately bounded to adapter
  relocation, inert-key retirement plus its gate, and CLI wiring cleanup.
  Placement is driven by files, not preference:
  - **SA167c** must be on W2 because it registers a gate, and
    `scripts/gate_registry.json` is a W2-only surface. It also rewrites every
    `module.yml`, so it merges after SA118.
  - **SA167b** and **SA167d** touch files no other v88 ticket touches (`entry_point.py`,
    the nine `adapter.py` targets, `module_config.py`), so they go to **W1** — the
    lightest lane — and run parallel to W2's second half instead of extending it. Neither
    carries a cross-worktree gate.
  **Cost, stated plainly:** SA167c is a serialized W2 leg; SA167b and
   SA167d are free (parallel on W1) and do not extend the two-leg critical path.
- **SA163 does not get its own slot.** It executes inside SA135, whose allowlist already
  covers the same provisioning files.
- **The implementation tickets and the audit tickets are one queue.** The merge-order table
  is the single authority; the two backlog sections below are presentation, not scope.

### Dependency graph and critical path

```text
v88 — three worktrees, ten open merge positions carrying eleven open ticket entries, one merge queue

BAND A — clear; shared repository gates are green

W2 (gates & declared wiring)   ★ CRITICAL PATH — 4 open legs, 2 on the path
  SA118 ─► SA167c ─► SA166 ─► SA164
  declared  retire    testimony  watch
  defaults  django_   trail      items
            apps+gate
      #16       #21       #24       #25

W1 (module-wiring migration + watch items)   3 open legs, mostly light, no cross-worktree gate
  SA167b ─► SA167d ─► SA165
  P4 only    drain     watch
  (P1-P3     CLI       items
   merged)
    #17       #18       #22

W3 (service lifecycle — exclusive PostgreSQL/Docker slot)   3 open positions: 1 heavy + 2 band-C
  SA135 + SA163 ──► [SA161, SA160]
  owned PG lifecycle    emission-adjacent
  + derived CI env      fillers
        #15              #19, #20
```

**Longest open release chain — the critical path:** W2's
`SA118 → SA167c`. Two open band-B
legs; SA166 (#24) and SA164 (#25) are band-C tails behind
the chain, not on it. W2's back half is the release's implementation work, so W2 sets the
date. SA167b and SA167d cost nothing on the critical path: W1 runs them against W2's second
half. **Load check:** W1 carries three open legs — SA167b, SA167d, SA165 — and W3
three positions, against the four-leg W2 spine. W3's two band-C tails do not gate release, so W2 remains the binding lane — see
the irreducibility argument below.

**Second chain:** W3, `SA135` carrying `SA163`, one service-backed open leg followed by
  emission-adjacent fillers and serialized on the exclusive slot while that leg is active.

**Active cross-worktree dependency edges — none.** Every remaining dependency is intra-lane.
The manifest-reading `entry_point.py`, the
fail-hard `QUICKSCALE_LOCAL_WHEELHOUSE` version-spec seam, and the regenerated migration baseline
are all merged tree state that open tickets build on, not pending dependencies.

**Parallelism result: all three worktrees are merged into `v88` and all three queue heads are
executable.** `wt-track1`, `wt-track2`, and `wt-track3` are each verified ancestors of the
integration branch, so no lane carries unmerged work and every lane starts from the integration tip.
All twelve modules own an adapter and `entry_point.py` is drained to generic registry/dispatch
logic (SA167b P1-P3); SA135+SA163's P/A/B and partial C implementation is merged and W3 resumes at the strict C
no-host acceptance remainder rather than restarting. Each lane still syncs current `v88` before its
own exact-candidate validation; the roadmap does not preserve worktree-object pointers after their
scheduling purpose expires.

**Rebalance result: no track moves, and the binding constraint is no longer merge debt.** With
every lane merged and idle, the one contended resource is physical: a single PostgreSQL 18 cluster
holding `localhost:5432` and the twelve shared test databases. W1's SA167b P4 campaign and W3's
strict-C proof need it, and W3 needs it *empty* — no ticket move can
relieve that, only scheduling. W2 stays the binding lane because SA118 and SA167c follow its first
leg. Moving SA161/SA160 from W3 to W2 would put band-C filler on that lane and land the pair later
than it would on W3; moving SA166 or SA164 off W2 would split the gate-registry ownership invariant.
Move SA161 and SA160 together if a later rebalance is ever approved, because their shared
emission-parity fixture is an ordering edge.

**W2 is irreducible, and now also thinner than it looks.** It still holds four open legs. SA166 and
SA164 own `scripts/gate_registry.json`, which by standing invariant never crosses worktrees; SA123's
merged scanner entries remain preserved as settled tree state. SA118 and SA167c
must rewrite `quickscale_modules/*/module.yml` in that order on that same lane. Nothing may be pulled forward from
W3 because the PostgreSQL/Docker slot is exclusive — and W3 can now take it for SA135+SA163, which
will regain scheduling priority while active. SA165 stays on W1 because it edits `scripts/test_isolation_conformance.sh`
and the SA90 emission gate's `_HOST_DEPENDENT_PATHS`, which W3's SA163/SA161/SA160 legs read or
rebaseline.

**Standing serialization constraint between lanes.** W3's database-backed legs and any W1/W2 run of
`make check` / `make test-integration` contend for the *ownership* of the twelve local test
databases, not just for the Docker slot. This is a local-cluster artifact
that hosted CI does not have, and retiring it is **SA135**/**SA163** work.

The remaining critical path is `SA118 → SA167c`: two serialized implementation legs on W2.
Shared closeout surfaces (`CHANGELOG.md`,
`docs/technical/roadmap.md`, `docs/technical/v88_ticket_context.md`, and both audit docs)
remain covered by the standing sync-before-merge-back procedure.

### Track readiness (reconciled 2026-08-26; all three worktrees merged into `v88`)

Each track reports three independent states. A track is **truly green** only when all three
are yes. The queue and track states below were re-tested for rebalance opportunities; no move is
needed.

| Track | Next ticket | Can start | Can finish on its own track | Can merge in order | Verdict |
|---|---|---|---|---|---|
| **W1** | SA167b (#17) | **yes** — P1-P3 are merged, the lane is at the integration tip, and P4's shared gate prerequisite is green | **yes** — the remaining exact-candidate checks and closeout are W1-owned, subject to the shared PostgreSQL/Docker serialization rule | **yes** — #17 is the W1 queue head | **truly green — off the critical path** |
| **W2** | SA118 (#16) | **yes** — SA123's acceptance and closeout are complete, leaving the manifest-default implementation unblocked | **yes** — the phase is W2-owned and starts from a green shared baseline | **yes** — #16 is the W2 queue head | **truly green — on the critical path** |
| **W3** | SA135 + SA163 (#15) | **yes to continue** — P/A/B and the local C implementation are merged into `v88`, and the exclusive PostgreSQL/Docker window is authorized | **yes** — strict C acceptance and phases D-G are W3-owned; the `pg18-af10` stop/restart that gated them is granted | **yes in order** — #15 is the W3 queue head and has no upstream ticket ahead of it | **truly green — off the critical path** |

**All three tracks are truly green.** W2's SA118 is the only truly green ticket **on** the critical
path and should run first, because it heads `SA118 → SA167c`. W1's SA167b P4 and
W3's SA135+SA163 are real band-B work but sit off the path, so neither moves the release date.
**Scheduling, not dependency, is now the only thing separating them:** all three need the shared
PostgreSQL cluster and W3 needs it empty, so W3 takes priority while its owned-lifecycle leg is
active and W1's and W2's campaigns must not overlap that window.

**Blocked open tickets, edge kind, and what clears each.** Every edge is classified so no blocker
is ambiguous between "a maintainer decision clears it" and "only the upstream work clears it".

| Ticket | Blocking ticket | Edge kind | What clears it |
|---|---|---|---|
| SA167c (#21) | SA118 (#16) | **hard content** — both rewrite every `quickscale_modules/*/module.yml`, and SA167c retires `django_apps:` over SA118's projection | Only SA118. No decision clears it. |
| SA167d (#18) | SA167b (#17) | **hard content** — the CLI drain removes wiring logic that must already live in the module adapters | Only SA167b's P4 closure. No decision clears it. |
| SA161 (#19) | SA135 (#15) | **lane-ordering** — W3 queue position; SA161 also needs the PostgreSQL/Docker slot SA135 holds | Upstream work, or a maintainer reordering W3. Not recommended: SA135 is band B and SA161 is band-C filler. |
| SA160 (#20) | SA161 (#19) | **hard content** — emission-parity ordering on the shared `sa90_emission_manifests.json` rebaseline | Only SA161. No decision clears it; the pair must not be split. |
| SA166 (#24) | SA118 (#16), SA167c (#21) | **lane-ordering** — W2 queue position behind the spine; SA166 also owns `scripts/gate_registry.json` | Upstream work, or a maintainer reordering W2. Not recommended: it would put band-C filler ahead of the critical path. |
| SA164 (#25) | SA166 (#24) | **lane-ordering** for the queue position, **hard content** for its substance — its `test_sa92_migration_squash_guardrail.py` work depends on SA167c having retired `django_apps:` | The content half only SA167c clears. The SA166 position is reorderable but not recommended. |
| SA165 (#22) | SA167d (#18) | **lane-ordering** — W1 queue position only; SA165 shares no file with SA167d | Upstream work, or a maintainer reordering W1. Reordering is defensible if W1 finishes P4 early and the slot is held by W3. |

**Recommended concurrency right now:**

- **W1 — resume SA167b P4.** Sync current `v88`, rerun its exact runtime and gate campaign, then
  close out only the reviewed exact candidate.
- **W2 — resume SA118.** SA123's implementation and acceptance are complete; the manifest-default
  projection is now the critical-path head.
- **W3 — continue SA135 + SA163 (#15) from strict C acceptance.** The window is authorized: with
  no W1 or W2 campaign in flight, stop `pg18-af10`, confirm nothing listens on `localhost:5432`,
  run the remaining C proof and the D-G plan below, then restart the container and verify the
  restore. Rebind against the current eight-hosted-gate registry and hold the PostgreSQL/Docker
  slot against W1 for the duration.

**No maintainer decision is open anywhere in the v88 plan.** The last one — W3's exclusive
PostgreSQL/Docker window — was decided on 2026-08-26 and is recorded below.

#### Recorded maintainer decisions

**W3 exclusive PostgreSQL/Docker window — decided 2026-08-26: authorized, narrowly.** W3 may stop
the container `pg18-af10` for one window and must restart it afterwards.

**Why the window is needed.** SA135's strict C acceptance must show the suites provision their
*own* PostgreSQL 18 server. That is only observable when nothing is already listening on
`localhost:5432`; with a host server present the proof is vacuous, because the suites could be
silently reusing it. `pg18-af10` holds that port and the twelve shared `test_quickscale_*`
databases.

**Why this option.** The rejected alternative — standing a second cluster up on another port —
does not satisfy the criterion at all, since the criterion is precisely the *absence* of a host
server. Deferring W3 was the other alternative; it was rejected because SA135 is band B and the
window is cheap and reversible. The grant is also the organic reading of the standing rule that
**W3 holds the exclusive PostgreSQL/Docker slot** — this authorizes the slot rather than inventing
a new privilege.

**What is authorized, and its bounds.** Stopping `pg18-af10` and restarting it after the proof.
Nothing else: the container must not be removed, its volume must not be pruned, and the twelve
databases and the `quickscale_test_role` ownership state must be intact when W1 and W2 next run.
Recovery is `docker start pg18-af10`.

**Cost accepted, and who carries it.** W1 and W2 lose the shared cluster for the duration, so
**neither may have a campaign in flight when the window opens** — W3 takes scheduling priority
while its owned-lifecycle leg is active, per the standing serialization rule, and W1's
exact-candidate runtime window must not overlap it. **W3 owns the restore**: the window is not
closed until `pg18-af10` is running again and the restricted-role lane is verified green.

**SA123 coupled-test authority — decided 2026-08-25: option 1, narrow authority.** Adding the
ticket's two hosted scanner gates changes generator/parity expectations in
`scripts/test_gate_parity.py`, which the ownership rule at
[Shared conflict surfaces](#shared-conflict-surfaces) otherwise reserves to SA135+SA163.

**What is authorized.** SA123/W2 may update `scripts/test_gate_parity.py` **only** for the
hosted-job set, `needs` edges, run values, publish/E2E paths, and generator expectations directly
coupled to its two new gates — concretely, the 12→14 hosted-job and 6→8 `test`-barrier
expectations. Generic parity-checker semantics, the 24-entry publish oracle, and the transcribed
provisioning shell literal stay unchanged. Anything beyond that remains SA135+SA163's, and a need
to go further is a scope finding that gets its own ticket rather than an in-place widening.

**Why this option.** It matches the standing ordering rule — a ticket that makes a gate tell the
truth outranks one that makes the product better — and it keeps the gate lane, not the service
lane, as the critical path. The two rejected alternatives are recorded so the choice is legible:
splitting SA123 into local-then-hosted would have left both scanners non-blocking in hosted CI
until #15 merged and grown the heaviest W3 leg; reversing the merge order would have put the
release date behind the exclusive PostgreSQL/Docker slot.

**Cost accepted, and who carries it.** Two lanes now touch one file this release. **SA135+SA163
(#15) owns the reconciliation**: when it later retires or derives the transcribed shell literal it
must preserve SA123's expectation lines, and because #13 precedes #15 in the lane order the
contention is one-directional. The standing sync-before-merge-back procedure covers it.

Roadmap documentation ownership remains **Option A** — the roadmap holds open work only, and
completed work is archived rather than marked done.

**One standing operating constraint, not a decision:** the local database-lane ownership flip —
whichever of `make test-integration` and `make test-bypassrls` is about to run must own the
twelve test databases first.

### Merge order

One queue. Within a worktree, one reviewed child at a time; a ticket syncs the integration
branch into its worktree, resolves there, reruns its own verification, then merges its
exact reviewed tip.

| # | Ticket | Band | Tier | Worktree | Merges after | Service slot |
|---|---|---|---|---|---|---|
| 15 | **SA135** + **SA163** | B | 2 | W3 | — | **yes** — PostgreSQL + Docker |
| 16 | **SA118** | B | 2 | W2 | — | no |
| 17 | **SA167b** | B | 2 | W1 | — | no |
| 18 | **SA167d** | B | 3 | W1 | SA167b | no |
| 19 | **SA161** | C | 3 | W3 | SA135 | no |
| 20 | **SA160** | C | 2 | W3 | SA161 | no |
| 21 | **SA167c** | B | 2 | W2 | SA118 | no |
| 22 | **SA165** | C | 3 | W1 | SA167d | no |
| 24 | **SA166** | C | 3 | W2 | SA118, SA167c | no |
| 25 | **SA164** | C | 3 | W2 | SA166 | no |

Positions #1, #2, #3, #4, #5, #6, #6b, #7, #8, #9, #10, #11, #12, #13, #14, #23, and #26 are **retired and not
reused**; the tickets that held them are closed and archived in
[CHANGELOG.md](../../CHANGELOG.md). Gaps in the numbering are expected and carry no meaning.
#15, #16, and #17 are the per-lane heads and all three may act today — #16 resumes after SA123's
completion, #17 resumes its remaining P4 validation, and #15 resumes
from strict C acceptance over its merged partial implementation under the authorized exclusive
PostgreSQL/Docker window. They are serialized by that shared cluster, not by any ticket edge.

Band-C positions (19, 20, 22, 24, 25) are *earliest-eligible*, not commitments. Any of them may slip
past the release without blocking it; none may displace a band-A or band-B leg.

### Shared conflict surfaces

Standing surface for every ticket: `CHANGELOG.md`, `docs/technical/roadmap.md`, and `docs/technical/v88_ticket_context.md` when the ticket's concept notes change.
Additional per-ticket surfaces:

| Ticket | Additional shared surface | Why |
|---|---|---|
| SA167b | `quickscale_core/.../manifest/entry_point.py`, every `quickscale_modules/*/adapter.py`, `docs/technical/implementation_contract.md` | adapter relocation; **on W1 at #17; sole open owner of `entry_point.py`** |
| SA167c | every `quickscale_modules/*/module.yml`, `quickscale_core/.../manifest/{schema,loader}.py`, `scripts/gate_registry.json`, `Makefile`, CI workflow, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` | retires the inert key and registers the declaration gate; **registry membership is why this is W2** |
| SA167d | `quickscale_cli/src/quickscale_cli/commands/module_config.py`, `docs/technical/module-extension.md` | CLI wiring drain; touched by no other v88 ticket |
| SA118 | module manifests, wiring emission baselines | manifest projection over the merged app declarations |
| SA135 + SA163 | `scripts/test_integration.sh`, `scripts/provision_test_roles.sh`, `scripts/provision_ci_postgres.sh` (new), all four `.github/workflows/`, `scripts/test_gate_parity.py`, `Makefile`, `docs/technical/validation_policy.md`, `docs/others/arch-audit.md` | changes the documented DB precondition and the CI environment |
| SA160, SA161 | generator templates + **SA90 emission-parity fixture**, `docs/others/tech-audit.md` | emitted output changes |
| SA164 | `docs/others/arch-audit.md`, `scripts/gate_registry.json`, `scripts/check_gate_parity.py`, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`, `.../production.py.j2`, `quickscale_modules/orgs/.../apps.py` | watchlist discharge; **W2** — registry and the SA92 test are W2-owned surfaces, and it merges last |
| SA165 | `docs/others/tech-audit.md`, `quickscale_core/.../state_schema.py`, `scripts/test_isolation_conformance.sh`, `quickscale_core/tests/test_generator/test_generator.py`, `OPERATIONS.md.j2` | watchlist discharge; W1-isolated |
| SA166 | `scripts/gate_registry.json`, `Makefile`, CI workflow, `docs/others/tech-audit.md` | new process gate |

**Six surfaces are contended and need naming explicitly:**

- `scripts/gate_registry.json` — SA167c, SA166, and SA164 own this W2-only surface. SA123's two
  scanner entries are settled tree state and remain preserved while the registry never crosses
  worktrees.
- `quickscale_modules/*/module.yml` — SA118 (#16) then SA167c (#21), in that order, **both on
  W2**. SA118 projects the remaining declared defaults over the merged `apps` projections;
  SA167c retires `django_apps:` across all twelve. Keeping both on W2 is what stops the module
  manifests from becoming a cross-worktree surface, and is why SA167c could not move to W1 with
  the other wiring legs.
- `quickscale_core/.../manifest/entry_point.py` — sole open owner is SA167b (W1, #17). The
  manifest-read behaviour is already on the integration branch; SA167b's relocation must
  preserve it rather than reinstating any literal. No other open ticket touches this file.
- `scripts/test_gate_parity.py` — sole remaining open owner is SA135+SA163 (W3, merge #15).
  The regenerated 24-entry publish oracle is already on the integration branch; SA135+SA163
  must preserve it when retiring or deriving its own transcribed shell literal. **One authorized
  exception:** the narrow-authority decision under
  [Recorded maintainer decisions](#recorded-maintainer-decisions) authorized SA123's now-merged
  hosted-job, `needs`-edge, run-value, publish/E2E-path, and generator-expectation changes only.
  SA135+SA163 inherits and must preserve those settled expectation lines.
  No other open W1 or W2 ticket touches this file.
- `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` — SA167c (#21)
  removes its dependence on the retired `django_apps:` key, then SA164 (#25) fixes its
  `_migdir()` fallback and re-anchors its parity backstop. Both are on W2 and merge in that
  order, so this surface no longer crosses worktrees; SA164's migration-baseline work is a
  content dependency on the regenerated migrations rather than a file dependency.
- `quickscale_core/tests/fixtures/sa90_emission_manifests.json` — SA118, SA161,
  SA160. SA118 is on W2 and the other two on W3, so this **does** cross worktrees. Each
  rebaseline appends its own `baseline_evidence` entry with per-file rationale; the
  sync-before-merge-back procedure must preserve every prior entry.

`docs/others/arch-audit.md` is on the surface of SA163 only (Finding 13).
Findings 2, 4, and 7 remain untouched, per the "neither" decision above.

---

## v88 backlog track

Each ticket below carries its band, assigned worktree, merge position, and acceptance criteria.

This section holds the implementation tickets; the
[audit-derived backlog](#audit-derived-backlog) below holds the rest of the same queue.
**Read them as one list** — the merge-order table above is the authority, and four audit tickets
sit ahead of open work in this section.

Conceptual background, mental models, and implementation notes for **every** ticket live in [v88_ticket_context.md](v88_ticket_context.md); this roadmap remains authoritative for scope, worktrees, and merge order.

- [ ] **SA118 — Project every declared manifest default into wiring.** `Band B · Tier 2 · W2 · merge #16 · deps: none · blocks SA167c`
  Materialize authoritative declared defaults without widening into the full imperative-to-declarative migration; rebaseline emission parity with per-file rationale.
  **Acceptance:** every default declared in a module manifest is projected into generated wiring, with no default reachable only through imperative code (the five app-declaration literals are already cleared in the tree); the imperative-to-declarative migration is *not* attempted — out-of-scope seams are ticketed, not converted; emission parity is rebaselined with a per-file rationale for each changed output; a generated project boots and its module wiring reflects the declared defaults; manifest version-spec handling uses the merged fail-hard `QUICKSCALE_LOCAL_WHEELHOUSE` seam (SA150, closed; see [local-wheelhouse.md](local-wheelhouse.md)).

- [ ] **SA167b — Relocate the nine core-side adapters into their modules.** `Band B · Tier 2 · W1 · merge #17 · deps: none · blocks SA167d`
  **P1-P3 are merged integration-branch state (2026-08-26); the ticket stays open for P4.**
  All twelve shipped modules own
  `quickscale_modules/<name>/src/quickscale_modules_<name>/adapter.py`; `entry_point.py` retains
  generic registry/dispatch logic only; `MANAGED_ADAPTER_ORIGINS` derives from the discovered
  inventory; transient regeneration restores registry and origin identities and contents together.
  Merge object, command list, and test evidence are archived in [CHANGELOG.md](../../CHANGELOG.md).
  Do not redo P1-P3 — the merged state is the continuation base.
  P4's finished nodes — the registry/origin/context-restoration review, the standalone all-module
  PostgreSQL 18 runtime node, and the shared lifecycle-fixture prerequisite — are archived in
  [CHANGELOG.md](../../CHANGELOG.md) and must not be redone. No P4 design decision remains open.
  **Remaining P4 plan:**
  1. Restart Phase C from exact SA90 parity, then run `make lint`, `make typecheck`, `make check`,
     `make test`, and `make quality` as one ordered campaign; require every exit 0 and
     `.quickscale/quality_gate_status.json` to report a loaded baseline, zero warning/critical
     regressions, and monotonicity pass.
  2. Reconcile `decisions.md`, `implementation_contract.md`, `validation_policy.md` only if drifted,
     `v88_ticket_context.md`, `adaptive.intake.yml`, `CHANGELOG.md`, and every roadmap same-fact
     consumer. On full completion remove SA167b under the open-work-only policy rather than checking
     it; on another partial result retain this block and refresh only observed evidence.
  3. Sync current `v88` into W1, reconcile shared docs, create a clean candidate commit, and rerun
     the focused restoration suite, exact PG18 node, parity, consistency test, and full gate campaign
     against that exact tip.
  4. Run convergence review and terminal attestation over the exact candidate, merge that reviewed
     tip into `v88`, verify ancestry and clean integration state, then release SA167d.
  Do not close SA167b or start SA167d before this P4 plan finishes.
  Keep it as **one ticket, not one per module**: all nine original core-side blocks began in the
  same file and the relocation shared one registry contract. Per-module tickets would have
  serialized anyway while adding contention on `entry_point.py` and splitting one logical change
  nine ways.
  **Acceptance:** every shipped module owns its adapter at `quickscale_modules/<name>/src/quickscale_modules_<name>/adapter.py` exposing `get_manifest_adapter()`; `MANAGED_ADAPTER_ORIGINS` covers the full inventory; no per-module block remains in `entry_point.py`, which retains only generic helpers, the registry, and the public entry point; generator emission parity is unchanged, proving the relocation is behaviour-preserving; the tree conforms to [decisions.md §Module Wiring Authority](decisions.md#module-wiring-authority).
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/manifest/entry_point.py`, every `quickscale_modules/*/adapter.py`, `docs/technical/implementation_contract.md`.

- [ ] **SA167c — Retire `django_apps:` and gate the app declaration.** `Band B · Tier 2 · W2 · merge #21 · deps: SA118 (shared manifests) · closes the SA167 family`
  `django_apps:` is declared in eleven manifests and parsed by `manifest/loader.py:597` into `ModuleManifest.django_apps`, where **no production code path reads it**. It is inert declarative surface that reads as authoritative — the trap that made `social` look declared when it was not. One test helper does consume it (`quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py:53`) and silently falls back to a guessed path when it is absent, which is why `social` passed that gate too; that fallback is owned by SA164.
  **Acceptance:** `django_apps:` is either derived from the `apps` wiring projection or removed from all manifests, `ModuleManifest`, and the loader, with no key parsed-but-unread remaining; a conformance gate fails when a module ships models or a migration without declaring at least one Django app, registered in `scripts/gate_registry.json` and passing `scripts/check_gate_parity.py`; the gate is proved by deleting a module's app declaration and observing red, reverted before merge; `test_sa92_migration_squash_guardrail.py` no longer depends on the retired key.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/manifest/{schema,loader}.py`, every `quickscale_modules/*/module.yml`, `scripts/gate_registry.json`, `Makefile`, CI workflow, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`.

- [ ] **SA167d — Drain per-module wiring logic out of the CLI.** `Band B · Tier 3 · W1 · merge #18 · deps: SA167b`
  `quickscale_cli/src/quickscale_cli/commands/module_config.py` is 2,154 lines carrying a `configure_<name>_module()` / `apply_<name>_configuration()` pair per module — a fifth place the same wiring facts are expressed. Plan-time interactive prompts that collect **desired configuration** are legitimate and stay; anything deciding what a module *wires* belongs in the module.
  **Acceptance:** no function in `module_config.py` decides a module's apps, middleware, settings keys, or URL includes — those come from the module's manifest through its adapter; the remaining surface is desired-configuration collection only, and that boundary is stated in the module's docstring; a test asserts the CLI contributes nothing to `ModuleWiringSpec`; the stale-flow note in [module-extension.md §Building a Module](module-extension.md#building-a-module-authoring-checklist) is retired once the deviation it names is gone.
  **Shared conflict surface:** `quickscale_cli/src/quickscale_cli/commands/module_config.py`, `docs/technical/module-extension.md`.

- [ ] **SA135 — Give test suites an owned PostgreSQL lifecycle.** `Band B · Tier 2 · W3 · merge #15 · deps: none · PostgreSQL + Docker slot · carries SA163`
  Provision and tear down the server used by repository gates; replace the current out-of-band host assumption while retaining an asserted unavailability negative control.
  **Acceptance:** the integration gate provisions its own PostgreSQL 18 server and tears it down, with no reliance on a pre-existing host server; the `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` role contract is preserved; the asserted-unavailability negative control still fails loudly when the server cannot be provisioned, rather than skipping; `make test-integration` passes on a machine with no PostgreSQL running; [validation_policy.md](validation_policy.md) is updated to drop the out-of-band host precondition; image identity follows the settled content-addressed backend-image convention.
  **Merged partial state (do not restart):** phases P, A, and B are complete and phase C is
  delivered but not accepted; `scripts/provision_ci_postgres.sh` and its hermetic test suite are
  integration-branch state. The full delivery record — counts, the eight corrected P-C defects, and
  the two post-attestation remediations that are **not** independently graded — is archived in
  [CHANGELOG.md](../../CHANGELOG.md). Resume at the strict C acceptance remainder.
  **Environment precondition (measured 2026-08-26):** strict C acceptance requires no listener on
  `localhost:5432`. The container `pg18-af10` (`postgres:18`) holds that port and the twelve shared
  test databases, which W1's and W2's campaigns also use.
  **Authorized (2026-08-26):** W3 may stop `pg18-af10` for one window and **must restart it
  afterwards** — see [Recorded maintainer decisions](#recorded-maintainer-decisions) for the bounds
  and the restore obligation. Confirm no W1 or W2 campaign is in flight before opening the window,
  then resume at step 1 below without redoing P, A, or B. No decision remains open on this ticket.
  **Current handoff (2026-08-26): ready to continue from strict C acceptance.** SA123's two
  exact-tree acceptance campaigns are complete, and W2 has released the shared PostgreSQL cluster.
  Before source or service mutation, confirm no W1 or W2 campaign has since started, then open W3's
  exclusive window under the authorization above. The worktree is synchronized with `v88`; no
  SA135/SA163 product change from the blocked continuation is pending or needs salvage. No task
  prerequisite or maintainer decision is unresolved; the standing shared-cluster scheduling rule
  remains, but this handoff records no active contention.
  **Next handoff refinement:** before opening the window, make the existing Docker-unavailable
  lifecycle probe deterministic in `scripts/test_provision_ci_postgres.py` by supplying hermetic
  PostgreSQL clients while making Docker unresolvable, and require the exact fail-closed Docker
  prerequisite error with no allocation. Then execute the serial plan below. Workflow adoption must
  cover exactly the six hosted stations through the source-defined `backups`, `restricted`,
  `isolation`, `client-only`, and `bypassrls` profiles; closeout must update every active same-fact
  count and dependency consumer before the exact post-sync campaign runs.
  **Remaining plan (all phases serial):**
  1. **C-local-lifecycle acceptance remainder:** open the authorized window by stopping
     `pg18-af10`, confirm nothing listens on `localhost:5432`, then run the exact strict sequence
     and require no skips, exact-scope cleanup, canary survival, frozen image identity, dynamic
     loopback endpoints, and restricted → BYPASSRLS → restricted coexistence. Include the
     post-attestation remediation bytes in the next independent exact-candidate review. **Close the
     window before handing the cluster back:** restart `pg18-af10`, confirm the twelve databases and
     `quickscale_test_role` ownership survived, and record that restore with the phase evidence.
  2. **D-workflow-parity:** migrate all four maintainer workflows and six provisioning contexts to
      the helper, preserve deliberate isolation differences and inherited eight-hosted-gate behavior, add the
      helper to the existing E2E trigger-input owner, regenerate the E2E path region, and replace
      transcribed provisioning-shell assertions with structural parity.
  3. **E-acceptance:** prove Docker-unavailable failure, host independence, exact cleanup,
      restricted → BYPASSRLS → restricted coexistence, generated-project runtime, full repository
      gates, and quality no worse than the Phase A baseline.
  4. **F-closeout:** only after E is green, reconcile validation policy, Finding 13, ticket context,
      roadmap counts/dependencies, and changelog evidence under the open-work-only policy.
  5. **G-post-sync:** sync current `v88` again, rerun the complete acceptance on one clean frozen
      tree, perform independent convergence and terminal attestation, and merge only that exact tip.
  6. **Standing closeout obligations:** archive actual evidence in `CHANGELOG.md`, remove SA135 and
     SA163 only after full completion under the open-work-only policy, retire Finding 13 only with
     passing evidence, merge the exact reviewed tip into `v88`, and report final changed-line and
     elapsed-time/lines-per-hour metrics using the original measurement start of
     `2026-08-26 16:07:35 +0200`.

---

## Audit-derived backlog

Tickets opened from the live findings in [arch-audit.md](../others/arch-audit.md) (2026-08-21) and [tech-audit.md](../others/tech-audit.md) (2026-08-21). Both documents remain the SSOT for finding detail, evidence, and refutation; this section is authoritative for scope and sequencing only.

**These are not follow-on work.** The former band-A gate-layer ticket is complete; the remaining
audit-derived entries are sequenced with the implementation section.
SA163 executes inside SA135. The remaining five are **band C** slack filler. The merge-order
table above is the single authority; this section carries the finding detail.

Every ticket here that closes or changes a live finding takes `docs/others/arch-audit.md`
or `docs/others/tech-audit.md` onto its shared conflict surface per the execution rules.

### Sequencing of the audit-derived legs

```text
W2 spine:  SA118 (#16) ──► SA167c (#21)
                                                 └─► SA166 (#24) ──► SA164 (#25)

SA163 (arch F13, CI environment) ──► rides inside SA135 (W3, merge #15)
```

Band A is clear. The completed shared-baseline repair and the previous gate-layer prerequisite are
archived in [CHANGELOG.md](../../CHANGELOG.md), and their positions are retired rather than reused.

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
  - **SA92 migration-squash discovery tuple — artifact located 2026-08-21, now evaluable.** The audit recorded this as unlocatable, but the artifact is `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` — a bounded literal tripwire for cross-table `UPDATE … SET organization_id` DML in migrations. The prior search missed it because it grepped for `squash` in source rather than in test filenames. Two live observations: its `_migdir()` helper (`:53-59`) reads the **inert** `django_apps:` manifest key and then silently falls back to the conventional path when it is absent. `social` has a production `apps` wiring projection but deliberately no inert key, so this helper still passes social only through that fallback — a silent fallback of exactly the class [tech-audit.md](../others/tech-audit.md) owns; and its authoritative backstop is a catalog/data parity gate anchored to `v87`, a retired release ref no longer resolved by the quality gate. Re-anchor both against the regenerated migrations now on the integration branch.
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

- [ ] **SA166 — Require a testimony trail for behavioural commits.** `Band C · Tier 3 · W2 · merge #24 · deps: SA118, SA167c`
  Closes the tech audit's carried tooling gap *"no gate requires a changelog/ticket trail for behavioural commits"*. `d3d4c633` and `d4b0e834` were both titled "v0.87.0: QuickScale 0.87.0" while in fact changing hosted and publish provisioning, and `d3d4c633` left a repository conformance test red (TA66/SA158). Both audits independently flagged the same shape: a release-shaped message carrying a CI-topology change, read closely only because the arch audit's delta-classification step treats unlabeled-behavioural commits as read-at-full-depth. Recorded in the audit as maintainer-process risk rather than a source finding, which is why this is Tier 3 and remains behind the completed gate-layer prerequisite.
  **Acceptance:** a change touching `.github/workflows/`, `scripts/gate_registry.json`, or the provisioning stations requires either a roadmap ticket reference or a `CHANGELOG.md` entry, enforced mechanically rather than by convention; the check is registered in `scripts/gate_registry.json` and passes `scripts/check_gate_parity.py`; the gate fails on a deliberately introduced untitled workflow change, reverted before merge; false-positive cost is measured on the existing history and the rule is narrowed until it is quiet on legitimate release commits; the tooling gap is retired from the tech audit.
  **Shared conflict surface:** `scripts/gate_registry.json`, `Makefile`, CI workflow, `docs/others/tech-audit.md`.

### Audit items deliberately **not** ticketed

Recorded so the absence is a decision rather than an oversight.

| Item | Source | Why no ticket |
|---|---|---|
| Finding 7 `generated-file-ownership-unmodeled` | arch, deferred | Held by the **"neither" prioritization decision** above, which names it explicitly. Trigger: a third generated-project consumer, public updater, emitted-file expansion, or second theme. Related weakness is tracked in SA152. |
| Finding 2 `deletion-invariants-per-boundary-reimplementation` | arch, deferred | Held by the same decision. Trigger: `teams`, a GDPR erasure command, bulk-admin deletion, or a second deletion boundary. Design together with Finding 4 at `teams` kickoff. |
| Finding 4 `org-model-universe-hand-enumerated` | arch, deferred | Held by the same decision. Trigger: `teams` adds a tenant model, or a module adds a `PROTECT`/non-deferrable dependency among purge-owned rows. SA151 is noted as a natural derivation moment for the next audit pass. |
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
