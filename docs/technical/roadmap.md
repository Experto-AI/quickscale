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
| **A — Restore enforcement** | The gate layer reports green while not running, or runs red on HEAD. Nothing downstream can be trusted until this is fixed. | completed |
| **B — Release work on the critical paths** | The two longest serialized chains, one of which holds the exclusive service slot. | SA123 → SA118 → SA167c (critical path); SA135 (+ SA163); SA167b → SA167d |
| **C — Bounded independent fixes** | No dependants, small blast radius. Absorbed as slack filler by whichever worktree finishes a band-B leg early. | SA160, SA161, SA164, SA165, SA166 |

**Standing consequences of that rule:**

- **The critical path is on the gate track, not the service track.** W2's remaining band-B spine
  (`SA123 → SA118 → SA167c`) is three serialized merge legs with no
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
   SA167d are free (parallel on W1) and do not extend the three-leg critical path.
- **SA163 does not get its own slot.** It executes inside SA135, whose allowlist already
  covers the same provisioning files.
- **The implementation tickets and the audit tickets are one queue.** The merge-order table
  is the single authority; the two backlog sections below are presentation, not scope.

### Dependency graph and critical path

```text
v88 — three worktrees, eleven open merge positions carrying twelve open ticket entries, one merge queue

W2 (gates & declared wiring)   ★ CRITICAL PATH — 5 open legs, 3 on the path
  SA123 ─► SA118 ─► SA167c ─► SA166 ─► SA164
  dep+sec  declared  retire    testimony  watch
  gates    defaults  django_   trail      items
                     apps+gate
     #13      #16       #21       #24       #25

W1 (module-wiring migration + watch items)   3 open legs, mostly light, no cross-worktree gate
  SA167b ─► SA167d ─► SA165
  relocate   drain     watch
  3 pending  CLI       items
  (6 landed)
    #17       #18       #22

W3 (service lifecycle — exclusive PostgreSQL/Docker slot)   3 open positions: 1 heavy + 2 band-C
  SA135 + SA163 ──► [SA161, SA160]
  owned PG lifecycle    emission-adjacent
  + derived CI env      fillers
        #15              #19, #20
```

**Longest open release chain — the critical path:** W2's
`SA123 → SA118 → SA167c`. Three open band-B legs; every
prerequisite outside W2 is satisfied. SA166 (#24) and SA164 (#25) are band-C tails behind
the chain, not on it. W2's back half is the release's implementation work, so W2 sets the
date. SA167b and SA167d cost nothing on the critical path: W1 runs them against W2's second
half. **Load check:** W1 carries three open legs and W3 three positions against the three-leg
critical path. W3's two band-C tails do not gate release, so W2 remains the binding lane — see
the irreducibility argument below.

**Second chain:** W3, `SA135` carrying `SA163`, one service-backed open leg followed by
  emission-adjacent fillers and serialized on the exclusive slot while that leg is active.

**Active cross-worktree dependency edges — none.** Every remaining dependency is intra-lane.
The manifest-reading `entry_point.py`, the fail-hard `QUICKSCALE_LOCAL_WHEELHOUSE` version-spec
seam, and the regenerated migration baseline are all merged tree state that open tickets build
on, not pending dependencies.

**Parallelism result:** W1 has implementation *in flight* and the other two lanes have executable
work available. W1 carries SA167b P3 as four unmerged commits plus a working-tree `entry_point.py`
drain. W2's SA123 (#13) is **released to start**: the narrow-authority option was recorded on
2026-08-25, so SA123 may make SA123-coupled expectation updates to `scripts/test_gate_parity.py`
and its reviewed plan resumes at Phase A. W3 is released to start SA135+SA163 (#15) now that the
stable image lifecycle is settled. All three worktrees carry executable work, and the critical
path is moving again.

**No track moves this pass.** Every open ticket carries a worktree; none lacks one. One
candidate was re-tested against the ordering rule and rejected again: moving **SA161 (#19) and
SA160 (#20) from W3 to W1** would relieve the lane holding the exclusive PostgreSQL/Docker
slot of two band-C tails that need neither PostgreSQL nor Docker. It fails two of the three move tests:

- **Not on or feeding the critical path.** The remaining path is `SA123 → SA118 →
  SA167c`, entirely on W2. Neither ticket appears on it or feeds it, so the move buys no
  release date — it is filler relocated, not a spine shortened.
- **It creates a merge hazard.** `quickscale_core/tests/fixtures/sa90_emission_manifests.json`
  is still owned by SA118, SA161, and SA160 — today W2 plus W3, two worktrees. Moving the
  pair to W1 would spread one rebaselined fixture across three lanes.

Re-open the question only if W3 becomes the binding lane, and move the pair together — SA160's
`deps: SA161` is an emission-parity ordering edge on that shared fixture and must not be split.

**W2 is irreducible.** It remains the longest at five open legs: SA123,
SA166, and SA164 all own `scripts/gate_registry.json`, which by standing invariant
never crosses worktrees, and SA118 and SA167c must rewrite
`quickscale_modules/*/module.yml` in that order on that same lane. Nothing may be pulled forward from
W3 because the PostgreSQL/Docker slot is exclusive — and W3 can now take it for SA135+SA163, which
will regain scheduling priority while active. SA165 stays on W1 because it edits `scripts/test_isolation_conformance.sh`
and the SA90 emission gate's `_HOST_DEPENDENT_PATHS`, which W3's SA163/SA161/SA160 legs read or
rebaseline.

**Standing serialization constraint between lanes.** W3's database-backed legs and any W1/W2 run of
`make check` / `make test-integration` contend for the *ownership* of the twelve local test
databases, not just for the Docker slot. This is a local-cluster artifact
that hosted CI does not have, and retiring it is **SA135**/**SA163** work.

The remaining critical path is `SA123 → SA118 → SA167c`, three serialized legs,
all on W2. Shared closeout surfaces (`CHANGELOG.md`,
`docs/technical/roadmap.md`, `docs/technical/v88_ticket_context.md`, and both audit docs)
remain covered by the standing sync-before-merge-back procedure.

### Track readiness (reconciled 2026-08-25, eleventh pass; SA123 authority decision recorded)

Each track reports three independent states. A track is **truly green** only when all three
are yes. The queue and track states below were re-tested for rebalance opportunities (none
taken — see above).

| Track | Next ticket | Can start | Can finish on its own track | Can merge in order | Verdict |
|---|---|---|---|---|---|
| **W2** | SA123 (#13) | **yes** — the narrow-authority decision is recorded (2026-08-25); G-001 is discharged and the reviewed plan resumes at Phase A | **yes** — the scanner contract, registry entries, wiring, and SA123-coupled parity expectations are all now within W2's authority | **yes** — #13 is the W2 queue head and is gated by nothing | **truly green — on the critical path** |
| **W1** | SA167b P3 (#17) | **yes — started** — P1/P2 accepted; P3 has four unmerged commits (adapter contracts, auth, orgs, storage) plus an in-progress `entry_point.py` drain | **yes** — the remaining `MANAGED_ADAPTER_ORIGINS` proof and P4 closeout are W1-owned | **yes** — #17 remains W1's open queue head, gated by nothing | **truly green — in flight** |
| **W3** | SA135 + SA163 (#15) | **yes** — `deps: none` and the PostgreSQL/Docker lane is released | **yes** — the owned PostgreSQL lifecycle and derived CI environment remain entirely W3-owned | **yes** — #15 is W3's queue head | **truly green** |

**All three tracks are truly green, and W2's is the one on the critical path:**

- **W2 / SA123 (#13) — truly green, on the critical path.** The narrow-authority decision
  discharges G-001. Discovery and the reviewed plan are reusable; start at Phase A from a clean
  W2 worktree synced to current `v88`. This is the only currently executable action that shortens
  the release.
- **W1 / SA167b P3 (#17) — truly green, in flight, off the critical path.** Auth, orgs, and
  storage adapters are committed in the worktree; finish the `entry_point.py` drain, then prove
  `MANAGED_ADAPTER_ORIGINS` equals the twelve-module inventory before P4 closeout.
- **W3 / SA135 + SA163 (#15) — truly green, off the critical path.** The stable image
  lifecycle prerequisite is settled, so the owned PostgreSQL lifecycle may start.

**Blocked next-after tickets, and what clears each:**

| Ticket | Blocked state | Blocking ticket | Clearable by a maintainer decision? |
|---|---|---|---|
| SA164 (#25) | can start · can finish — no | SA166 (#24) | No — W2 ordering must clear. |

**Recommended concurrency right now:**

- **W1 — finish SA167b P3 (#17).** The three remaining adapters are relocated in the worktree;
  what is left is draining the per-module blocks from `entry_point.py` and proving the origin
  inventory. Then P4 closeout, then merge #17.
- **W2 — start SA123 (#13).** This is the highest-value action available: it is the head of the
  only remaining critical path. Sync `v88` into a clean W2 worktree, then run the reusable plan
  from Phase A under the recorded narrow authority.
- **W3 — start SA135 + SA163 (#15).** The PostgreSQL/Docker slot is free, the stable image
  lifecycle is settled tree state, and no open ticket gates this leg.

#### Recorded maintainer decisions

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
must preserve SA123's expectation lines, and because #13 merges before #15 the contention is
one-directional. The standing sync-before-merge-back procedure covers it.

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
| 13 | **SA123** | B | 2 | W2 | — | no |
| 15 | **SA135** + **SA163** | B | 2 | W3 | — | **yes** — PostgreSQL + Docker |
| 16 | **SA118** | B | 2 | W2 | SA123 | no |
| 17 | **SA167b** | B | 2 | W1 | — | no |
| 18 | **SA167d** | B | 3 | W1 | SA167b | no |
| 19 | **SA161** | C | 3 | W3 | SA135 | no |
| 20 | **SA160** | C | 2 | W3 | SA161 | no |
| 21 | **SA167c** | B | 2 | W2 | SA118 | no |
| 22 | **SA165** | C | 3 | W1 | SA167d | no |
| 24 | **SA166** | C | 3 | W2 | SA118, SA167c | no |
| 25 | **SA164** | C | 3 | W2 | SA166 | no |

Positions #1, #2, #3, #4, #5, #6, #6b, #7, #8, #9, #10, #11, #12, #14, and #23 are **retired and not
reused**; the tickets that held them are closed and archived in
[CHANGELOG.md](../../CHANGELOG.md). Gaps in the numbering are expected and carry no meaning.
Positions #13, #15, and #17 are queue heads, and all three are gated by nothing — #13's
scope-authority gate was discharged by the narrow-authority decision recorded above.

Band-C positions (19, 20, 22, 24, 25) are *earliest-eligible*, not commitments. Any of them may slip
past the release without blocking it; none may displace a band-A or band-B leg.

### Shared conflict surfaces

Standing surface for every ticket: `CHANGELOG.md`, `docs/technical/roadmap.md`, and `docs/technical/v88_ticket_context.md` when the ticket's concept notes change.
Additional per-ticket surfaces:

| Ticket | Additional shared surface | Why |
|---|---|---|
| SA123 | `scripts/gate_registry.json`, `Makefile`, CI workflow, `scripts/test_gate_parity.py` (narrow, SA123-coupled expectations only) | new blocking gates |
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

- `scripts/gate_registry.json` — SA123, SA166, SA164. All three are on W2 and
  serialized by the merge order, so the registry never crosses worktrees. Preserve that; it
  is the reason none of the three may be rebalanced off W2.
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
  [Recorded maintainer decisions](#recorded-maintainer-decisions) lets SA123 (W2, #13) change this
  file for its own two gates' hosted jobs, `needs`, run values, publish/E2E paths, and generator
  expectations only. #13 merges before #15, so SA135+SA163 inherits and must preserve those lines.
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

- [ ] **SA123 — Add dependency-vulnerability and security static-analysis gates.** `Band B · Tier 2 · W2 · merge #13 · deps: none · blocks SA118`
  Add blocking dependency and focused security scanners with reviewed suppressions; register every new gate through the authoritative gate registry.
  **Acceptance:** a dependency-vulnerability scanner and a focused security static-analysis scanner run as blocking gates; both are registered in `scripts/gate_registry.json` and pass `scripts/check_gate_parity.py`; every suppression carries a written rationale and an owner; the gates fail on a deliberately introduced known-vulnerable pin and on a deliberately introduced flagged pattern, both reverted before merge; `make quality` is no worse than found.
  **Planning checkpoint (2026-08-25; keep this ticket open):** W2 was clean at
  `22860e52e0009d8c44e557d8811505b52e19f423` after merging `v88`. Repository discovery and
  authoritative tool research completed; the reviewed design selects pinned `pip-audit` and
  Bandit gates, audits both committed lock projects, rejects native/unaccountable suppressions,
  and uses an exact owner/rationale/decision/expiry ledger. No scanner dependency, gate, test,
  workflow, product, or environment change was made, and no implementation validation ran.
  Mandatory plan review stopped before Phase A because adding two hosted gates necessarily changes
  SA123-coupled 12-to-14 hosted-job and six-to-eight `test`-barrier expectations in
  `scripts/test_gate_parity.py`.
  **G-001 is discharged (2026-08-25): narrow authority granted.** SA123 may change that file only
  for its own two gates' hosted jobs, `needs`, run values, publish/E2E paths, and generator
  expectations; generic parity semantics, the 24-entry publish oracle, and the transcribed
  provisioning shell literal stay unchanged. See
  [Recorded maintainer decisions](#recorded-maintainer-decisions). **Implementation is released
  and starts at Phase A.**
  **Reusable handoff (all phases serial):**
  0. **Base:** reconfirm a clean W2 worktree after merging current `v88`; the prior rollback
     object above is historical evidence, not a future-session base.
  2. **A-contract — scanner contract:** modify only root `pyproject.toml`/`poetry.lock` and add
     `scripts/check_security_gates.py`, `scripts/security_suppressions.json`,
     `scripts/security_probe_cases.json`, and `scripts/test_security_gates.py`. Keep
     `quickscale_core/poetry.lock` and all member manifests read-only. Observe the installed scanner
     CLIs before freezing arguments; fail closed if either committed lock cannot be audited
     lock-natively. Pre-capture `make quality`; require focused wrapper tests, both clean scans, and
     temporary known-advisory/B602 probes that arm cleanup before creating inputs and finish clean.
  3. **B-wiring — every caller:** update `Makefile`, `scripts/gate_registry.json`, local runner
     labels, hosted generator/catalog, generated CI/E2E regions, hand-maintained publish calls, and
     coupled local/parity tests. `scripts/check_gate_parity.py` remains read-only. Under the
     granted narrow authority, `scripts/test_gate_parity.py` may change only for SA123's hosted
     jobs, `needs`, run values, publish/E2E paths, and generator expectations; any need beyond
     that is a scope finding and gets its own ticket. Require public gate targets,
     parity, generation, and gate-suite checks to exit 0.
  4. **C-acceptance — no tracked edits:** run both normal gates; the negative-control target;
     `make check-gate-parity`; `make check-ci-gate-generation`; `make check-gate-suites`;
     `make lint`; `make typecheck`; `make check`; and `make quality`. Preserve exact exits and
     scanner/probe identities; quality must be no worse than the Phase A capture.
  5. **D-closeout:** only after all acceptance evidence passes, align decisions, validation,
     reviewer/operator, audit, context, roadmap, and changelog documentation. Remove SA123 under
     the open-work-only policy rather than adding a second checked marker; do not claim merge or
     publication before it occurs.
  6. **Post-sync verification and merge:** the maintainer syncs current `v88` into W2, freezes the
     resulting exact tree, reruns the complete Phase C commands with no tracked edits, then sends
     that settled delta through convergence review and terminal attestation. Merge only the exact
     reviewed tip into `v88`; any changed outcome or scope decision stops the handoff.

- [ ] **SA118 — Project every declared manifest default into wiring.** `Band B · Tier 2 · W2 · merge #16 · deps: SA123 · blocks SA167c`
  Materialize authoritative declared defaults without widening into the full imperative-to-declarative migration; rebaseline emission parity with per-file rationale.
  **Acceptance:** every default declared in a module manifest is projected into generated wiring, with no default reachable only through imperative code (the five app-declaration literals are already cleared in the tree); the imperative-to-declarative migration is *not* attempted — out-of-scope seams are ticketed, not converted; emission parity is rebaselined with a per-file rationale for each changed output; a generated project boots and its module wiring reflects the declared defaults; manifest version-spec handling uses the merged fail-hard `QUICKSCALE_LOCAL_WHEELHOUSE` seam (SA150, closed; see [local-wheelhouse.md](local-wheelhouse.md)).

- [ ] **SA167b — Relocate the nine core-side adapters into their modules.** `Band B · Tier 2 · W1 · merge #17 · deps: none · blocks SA167d`
  **Partial implementation checkpoint (2026-08-25; keep this ticket open):** P1 is accepted: analytics, blog, listings, and forms are module-owned, billing and CRM use the public lazy runtime facade, and the adapter/core/runtime/CLI plus import/lint/type checks passed. P2's backups and notifications implementation and split suites are accepted. Its original literal two-module pytest command failed during collection because both module trees resolved `tests.conftest`; no implementation assertion failed. Equivalent grouped coverage is established with `PYTEST_ADDOPTS='--noconftest --import-mode=importlib'` and `QUICKSCALE_ALLOW_BYPASSRLS=1`, without changing unrelated test-package layout.
  **P3 is in flight on W1 and unmerged.** Nine modules ship module-owned adapters on the integration branch: analytics, backups, billing, blog, CRM, forms, listings, notifications, and social. The worktree adds auth, orgs, and storage adapters plus the shared adapter manifest contracts, and the `entry_point.py` drain is still in the working tree. Nothing has merged, so `entry_point.py` on `v88` still carries the three core-side blocks.
  **Remaining handoff:** finish the `entry_point.py` drain, then prove `MANAGED_ADAPTER_ORIGINS` exactly equals the authoritative twelve-module inventory with fail-hard import/sentinel and registry identity/custom-entry coverage. P4 then runs the integration, generator parity, full repository gates, and documentation closeout. Do not close SA167b before both phases and all acceptance evidence finish.
  Keep it as **one ticket, not one per module**: all nine core-side blocks began in the same file, and the three remaining blocks still share it. Per-module tickets would serialize anyway while adding contention on `entry_point.py` and splitting one logical change nine ways.
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
W2 spine:  SA123 (#13) ──► SA118 (#16) ──► SA167c (#21)
                                                 └─► SA166 (#24) ──► SA164 (#25)

SA163 (arch F13, CI environment) ──► rides inside SA135 (W3, merge #15)
```

Band A is empty: the gate-layer prerequisite is complete and archived in
[CHANGELOG.md](../../CHANGELOG.md), and its position is retired rather than reused.

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
  Take **Option 1** (one `scripts/provision_ci_postgres.sh`, four callers, module list derived from the discovery shim exactly as `check_sa117_scope.py:48` already does). Do it **inside SA135**, whose allowlist already spans `scripts/test_integration.sh`, `scripts/provision_test_roles.sh`, the `Makefile`, and the documented DB precondition — not as a separate pass over the same files. Option 2 (an `environment` block in the gate registry) only if SA123's registry work lands cleanly first, since both bump the registry schema.
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
| Tooling gaps — dependency-vulnerability scanner, security static analysis | tech | Already owned by **SA123** (merge #13). |
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
