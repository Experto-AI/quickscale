# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Changelog](../../CHANGELOG.md) | [Validation Policy](validation_policy.md) | [v88 Ticket Context](v88_ticket_context.md) | [Release Summary Template](release_summary_template.md)

## Purpose

This is the current task planner. It primarily contains open planned work. Completed tickets, closed findings, review history, and release evidence normally live in [CHANGELOG.md](../../CHANGELOG.md) and version control; SA137 remains below as a checked item because its acceptance explicitly requires retention in this roadmap.

### Execution rules

- Work develops in three worktrees (**W1** pins/interpreter + module-wiring migration, **W2** gate layer + declared wiring, **W3** service lifecycle) and merges into the clean `v88` integration branch. Never implement directly on the integration branch. There are three worktrees and no more; a ticket that does not fit an existing lane is sequenced inside one, not given a new lane.
- One reviewed child runs at a time per worktree. Umbrellas are acceptance-only; their children own implementation.
- Start from a clean worktree after merging the integration branch. Before merge-back, sync the integration branch into the worktree, resolve there, run the ticket's verification, review the exact tip, then merge that tip.
- Every handoff declares its file allowlist, commands, expected exits/artifacts, rollback, and focused validation. Scope findings are ticketed rather than fixed in place.
- Leave `make quality` no worse than found. Do not raise a complexity ceiling or reintroduce file-line ceilings. The rule is measurable again (SA156, closed): the default monotonicity path resolves durable `main` and `make quality` emits fresh reports. The known baseline is one pre-existing complexity regression at `development_commands.py::up`.
- Shared closeout conflict surfaces are `CHANGELOG.md`, `docs/technical/roadmap.md`, and `docs/technical/decisions.md` when policy changes. `docs/others/arch-audit.md` and `docs/others/tech-audit.md` join that surface only when a ticket changes or closes a live audit finding. The sync-before-merge-back procedure above must preserve every concurrent entry, resolve these files in the worktree, rerun the ticket's checks, and leave no unmerged files before the exact tip is reviewed and merged.
- PostgreSQL/Docker work is serialized across worktrees. **W3 holds the exclusive PostgreSQL/Docker slot** and takes scheduling priority whenever one of its legs is active, even though W2 — not W3 — is the longest dependency chain this release.
- **W1's wiring legs (SA167b, SA167d) may not touch `scripts/gate_registry.json` or any `module.yml`.** Both are W2-owned surfaces — SA167a and SA167c are on W2 for exactly that reason. The wiring legs' only cross-worktree edge is `entry_point.py`, one-way: SA167a merges at #8 before SA167b starts.
- A ticket whose deliverable is Git ref state cannot be delegated to a file-editing worker. Route it to a maintainer session with ref authority and push credentials.

---

## v88 release plan

### Prioritization decision (recorded 2026-08-21)

**Choice: neither.** Architectural Findings 2 (deletion-cleanup coordination), 4 (organization purge ordering), and 7 (generated-file ownership) stay behind their growth triggers. No `teams` domain work and no third generated-project updater is scheduled for v88. This is consistent with the standing decision that `teams` is not planned, and it keeps v88 free of speculative architecture. The implementation tickets are planned on their own merits below, in one queue with the audit-derived tickets.

Consequence for the gated findings: they remain live in [arch-audit.md](../others/arch-audit.md) and are **not** closed by any v88 ticket. A v88 ticket may not widen into them; if implementation work discovers a trigger has actually fired, that is a scope finding and gets its own ticket rather than an in-place fix.

The priority model, dependency graph, acceptance criteria, and worktree/merge-order assignment below are the authoritative plan. (v88 planning is closed; see [CHANGELOG.md](../../CHANGELOG.md).)

### Priority model (revised 2026-08-21)

The first plan ranked the nine implementation tickets on their own merits, and the
audit-derived backlog was appended afterwards. Reconciling the two changes the
answer, because four audit tickets are **prerequisites**, not follow-on work:

> **Ordering rule.** A ticket that makes a gate *tell the truth* outranks a ticket that
> makes the product *better*, because every other ticket's acceptance criteria are
> discharged by those gates. Below that, order by longest dependency chain, then by
> whether the ticket holds an exclusive resource, then by tier.

Applying it produces three ranked bands:

| Band | Rule | Tickets |
|---|---|---|
| **A — Restore enforcement** | The gate layer reports green while not running, or runs red on HEAD. Nothing downstream can be trusted until this is fixed. | SA157, SA158, SA159, SA155 *(SA156 done)* |
| **B — Release work on the critical paths** | The two longest serialized chains, one of which holds the exclusive service slot. | SA151→SA142→SA135(+SA163); SA134→SA150→SA167b→SA167d (SA137 done); then SA167a→SA124→SA123→SA118→SA167c |
| **C — Bounded independent fixes** | No dependants, small blast radius. Absorbed as slack filler by whichever worktree finishes a band-B leg early. | SA160, SA161, SA162, SA164, SA165, SA166 |

**What changed from the first plan and why:**

- **The critical path moved off the service track.** W2 (`SA157 → SA155 → SA124 → SA123 → SA118`)
  is now five serialized legs against W3's three. W3 keeps the exclusive
  PostgreSQL/Docker slot and therefore keeps scheduling priority *while a leg is
  active*, but it is no longer the longest chain and no longer sets the release date.
- **SA156 is closed** (merge #1, detail in [CHANGELOG.md](../../CHANGELOG.md)). Its one live
  consequence for planning: `make quality` now runs, and the broader gate is red on the
  unrelated pre-existing complexity regression at
  `quickscale_cli/src/quickscale_cli/commands/development_commands.py::up` (15 versus
  allowed 14). Any ticket claiming "no worse than found" measures against that baseline.
- **SA158 moved from W2 to W1 (rebalance 2026-08-21).** It has `deps: none`, its file
  (`scripts/test_gate_parity.py`) is touched by no other W1 ticket, and W1 carries slack
  against W2. Moving it removes one serialized leg from the critical path and un-gates
  SA157, which now merges at #4 with no predecessor.
- **SA157 was promoted ahead of SA124** because SA124's acceptance criterion lands in
  `scripts/test_check_sa117_scope.py`, the exact file carrying a guaranteed false-green.
- **The whole SA167 family is in v88 (decision 2026-08-21).** The ordering argument is
  band A's, one level down: five modules declare their Django apps as Python literals
  inside core, which is precisely the "default reachable only through imperative code"
  that SA118's acceptance forbids — SA118 could neither satisfy that criterion nor widen
  into the literals without breaking its own scope bound. That made **SA167a** a
  prerequisite rather than follow-on work, and once the declaration lands there is no
  reason to ship the release with four of the five wiring surfaces still divergent.
  Placement is driven by files, not preference:
  - **SA167a** is on W2 at **merge #8** — the earliest defensible slot. It has no
    dependencies, but it is deliberately *not* placed ahead of band A: its acceptance
    rests on "emission parity unchanged" and "`make quality` no worse than found", and
    neither claim is verifiable until the gate layer tells the truth (SA155, #7).
    Landing it at #8 rather than #14 unblocks SA167b/SA167c six positions earlier.
  - **SA167c** must be on W2 because it registers a gate, and
    `scripts/gate_registry.json` is a W2-only surface. It also rewrites every
    `module.yml`, so it merges after SA118.
  - **SA167b** and **SA167d** touch files no other v88 ticket touches (`entry_point.py`,
    the nine `adapter.py` targets, `module_config.py`), so they go to **W1** — the
    lightest lane — and run parallel to W2's second half instead of extending it. They
    slot in after SA150 (#12) and SA162 (#17) without displacing anything.
  **Cost, stated plainly:** the critical path grows from six legs to eight. SA167b and
  SA167d are free (parallel on W1); SA167a and SA167c are not.
- **SA163 does not get its own slot.** It executes inside SA135, whose allowlist already
  covers the same provisioning files.
- **The nine "v88 tickets" and the audit tickets are one queue.** Keeping them in separate
  sections with separate numbering is what hid the prerequisite relationship for a full
  planning pass.

### Dependency graph and critical path

```text
v88 — three worktrees, twenty-two open tickets (SA156 and SA137 closed), one merge queue

W2 (gate layer ─► gates & declared wiring)   ★ CRITICAL PATH — 8 serialized legs
  SA157 ─► SA155 ─► SA167a ─► SA124 ─► SA123 ─► SA118 ─► SA167c ─► SA166
  false-   register  apps into  one path  dep+sec  declared  retire    testimony
  green    suites    manifests  authority gates    defaults  django_   trail
                     (5 mods)                                apps+gate
              ▲   ▲     │           ▲                ▲
              │   │     │           │                │
   SA158 (W1)─┘   │     │           │                │
   SA159 (W1)─────┘     │           │   SA150 (W1) merges first
   SA157 also blocks SA124 ─────────┘
   (SA156 closed — was the fifth input to SA155)
                        └──────────────► unblocks SA167b (W1) at #8

  (W1 picks up the wiring legs — see below)

W1 (pins/interpreter + module-wiring migration)   9 open legs, mostly light
  [SA137 closed] ─► SA159 ─► SA158 ─► SA134 ─► SA150 ─► SA167b ─► SA162 ─► SA167d ─► SA165 ─► SA164
  devtools project  publish  derive   fail-hard relocate  csrf     drain     watch    watch
  in prop. interp.  oracle   pins     wheelhse  9 adapters gate     CLI       items    items
             └────────┴──────────────► both block SA155 (W2)
                                        ▲                  ▲
                        SA167a (W2, #8) ┘   SA167b blocks ─┘
                        one-way on entry_point.py

W3 (service lifecycle — exclusive PostgreSQL/Docker slot)   3 heavy legs
  SA151 ──► SA142 ──► SA135 + SA163 ──► [SA161, SA160]
  clean     stable    owned PG lifecycle    emission-adjacent
  initial   image     + derived CI env      fillers
  migrations identity
```

**Longest open chain:** W2, `SA157 → SA155 → SA167a → SA124 → SA123 → SA118 → SA167c`,
seven legs before the SA166 filler, eight with it. This is the release's critical path.
W1 now carries nine open legs, but seven of them are script/test edits; W2's back half is the
release's implementation work, so W2 still sets the date — and the SA167 pull-in moved
that date out by two legs (SA167a, SA167c), deliberately. SA167b and SA167d cost nothing
on the critical path: W1 runs them against W2's second half. **Watch W1's load** — if it
becomes the binding lane in practice, the band-C fillers (SA162, SA165, SA164) are the
ones to defer, never the wiring legs.

**Second chain:** W3, `SA151 → SA142 → SA135`, three legs, each service-backed and
serialized on the exclusive slot. Longest *wall-clock* chain despite fewer legs; it keeps
scheduling priority whenever one of its legs is active.

**Cross-worktree edges — five:**

0. `SA158` (W1) → `SA155` (W2). Created by the rebalance. SA155 must register **green**;
   SA158 is one of the tickets resolving the 74 failures.
1. `SA159` (W1) → `SA155` (W2). SA155 must register **green**; SA159 is one of the
   tickets resolving the 74 failures.
2. `SA150` (W1) → `SA118` (W2). Manifest version-spec handling: SA118 must project
   defaults over SA150's fail-hard seam, not over the current silent fallback.
3. `SA167a` (W2, #8) → `SA167b` (W1, #14). Shared `entry_point.py`, one-way. This is the
   wiring legs' only cross-worktree surface; they are otherwise isolated.
4. `SA151` (W3) → `SA152` (post-v88). Recorded, not scheduled this release.

**Parallelism result:** W3 carries slack against W2; W1 absorbs SA158 plus both wiring
legs, which is what keeps SA167b/SA167d off the critical path. Band-C tickets are the sanctioned way to spend what remains. The unavailable
rebalance is still the same one: nothing may be pulled forward from W3, because the
PostgreSQL/Docker slot is exclusive. SA157 cannot leave W2 (its file is SA124's file),
and SA166 cannot leave W2 (`gate_registry.json`).

### Merge order

One queue. Within a worktree, one reviewed child at a time; a ticket syncs the integration
branch into its worktree, resolves there, reruns its own verification, then merges its
exact reviewed tip.

| # | Ticket | Band | Tier | Worktree | Merges after | Service slot |
|---|---|---|---|---|---|---|
| 3 | **SA151** | B | 1 | W3 | — | **yes** — PostgreSQL |
| 4 | **SA157** | A | 2 | W2 | — | no |
| 5 | **SA159** | A | 2 | W1 | SA137 | no |
| 6 | **SA158** | A | 2 | W1 | SA159 | no |
| 7 | **SA155** | A | 1 | W2 | SA157, SA158, SA159 | no |
| 8 | **SA167a** | B | 1 | W2 | SA155 | no |
| 9 | **SA134** | B | 2 | W1 | SA159 | no |
| 10 | **SA142** | B | 1 | W3 | SA151 | **yes** — Docker |
| 11 | **SA124** | B | 1 | W2 | SA155, SA157 | no |
| 12 | **SA150** | B | 2 | W1 | SA134 | no |
| 13 | **SA123** | B | 2 | W2 | SA124 | no |
| 14 | **SA167b** | B | 2 | W1 | SA150, **SA167a** | no |
| 15 | **SA135** + **SA163** | B | 2 | W3 | SA142 | **yes** — PostgreSQL + Docker |
| 16 | **SA118** | B | 2 | W2 | SA123, **SA150**, **SA167a** | no |
| 17 | **SA162** | C | 3 | W1 | SA150 | no |
| 18 | **SA167d** | B | 3 | W1 | SA162, **SA167b** | no |
| 19 | **SA161** | C | 3 | W3 | SA135 | no |
| 20 | **SA160** | C | 2 | W3 | SA161 | no |
| 21 | **SA167c** | B | 2 | W2 | **SA167a**, **SA118** | no |
| 22 | **SA165** | C | 3 | W1 | SA162 | no |
| 23 | **SA164** | C | 3 | W1 | SA165 | no |
| 24 | **SA166** | C | 3 | W2 | SA155, SA118, SA167c | no |

Merge #1 (SA156) is closed and archived in [CHANGELOG.md](../../CHANGELOG.md).
Merge #2 (SA137) is closed, retained below as a checked item, and has its closure evidence
recorded in the changelog. Positions were renumbered on 2026-08-21 when the SA167 family was pulled into the release: SA167a
moved to #8 (earliest slot after band A), SA167b/SA167d sequence inside W1 at #14 and #18, and SA167c takes #21
after SA118. Positions 1–7 are unchanged.

Band-C positions (17, 19, 20, 22, 23, 24) are *earliest-eligible*, not commitments. Any of them may slip
past the release without blocking it; none may displace a band-A or band-B leg.

### Shared conflict surfaces

Standing surface for every ticket: `CHANGELOG.md`, `docs/technical/roadmap.md`.
Additional per-ticket surfaces:

| Ticket | Additional shared surface | Why |
|---|---|---|
| SA155 | `Makefile`, `scripts/gate_registry.json`, `scripts/sync_ci_gate_jobs.py`, `.github/workflows/ci.yml`, `scripts/check_ci_locally.sh`, `docs/others/arch-audit.md` | new registered gate + hosted job |
| SA158 | `scripts/test_gate_parity.py`, both audit docs | parity oracle; **W1** — crosses worktrees with SA135+SA163 (W3), which merges later |
| SA157 | `scripts/test_check_sa117_scope.py`, `docs/others/tech-audit.md` | **also SA124's file** |
| SA159 | `scripts/version_tool.sh`, `scripts/lint_frontend.sh`, `scripts/_python_requirement.sh`, `.pre-commit-config.yaml`, `docs/others/tech-audit.md` | **`version_tool.sh` carries SA137's settled propagation change** |
| SA151 | `docs/technical/decisions.md` | records the no-migration-history policy |
| SA123 | `scripts/gate_registry.json`, `Makefile`, CI workflow | new blocking gates |
| SA124 | `scripts/gate_registry.json`, `Makefile`, `scripts/sa117_scope.json`, `scripts/test_check_sa117_scope.py` | gate + path authority |
| SA134 | — | test-side literals only |
| SA167a | `quickscale_core/.../manifest/entry_point.py`, `quickscale_modules/{auth,backups,notifications,orgs,storage}/module.yml` | app declarations move into manifests; **shares module manifests with SA118 and SA167c, merges first**; shares `entry_point.py` with SA167b (W1), merges first |
| SA167b | `quickscale_core/.../manifest/entry_point.py`, every `quickscale_modules/*/adapter.py`, `docs/technical/implementation_contract.md` | adapter relocation; **on W1, with `entry_point.py` inherited one-way from SA167a (W2, #8)** |
| SA167c | every `quickscale_modules/*/module.yml`, `quickscale_core/.../manifest/{schema,loader}.py`, `scripts/gate_registry.json`, `Makefile`, CI workflow, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` | retires the inert key and registers the declaration gate; **registry membership is why this is W2** |
| SA167d | `quickscale_cli/src/quickscale_cli/commands/module_config.py`, `docs/technical/module-extension.md` | CLI wiring drain; touched by no other v88 ticket |
| SA118 | module manifests, wiring emission baselines | manifest projection; inherits SA167a's five manifests |
| SA142 | `scripts/test_e2e.sh`, E2E fixtures, **SA90 emission-parity fixture** | image/container identity |
| SA135 + SA163 | `scripts/test_integration.sh`, `scripts/provision_test_roles.sh`, `scripts/provision_ci_postgres.sh` (new), all four `.github/workflows/`, `scripts/test_gate_parity.py`, `Makefile`, `docs/technical/validation_policy.md`, `docs/others/arch-audit.md` | changes the documented DB precondition and the CI environment |
| SA150 | `docs/others/tech-audit.md` (retires a watch item), new `docs/technical/` seam doc | fail-hard + documentation |
| SA160, SA161 | generator templates + **SA90 emission-parity fixture**, `docs/others/tech-audit.md` | emitted output changes |
| SA162 | `scripts/check_csrf_exempt_gate.py`, both audit docs | gate semantics |
| SA164, SA165 | `docs/others/arch-audit.md`, `docs/others/tech-audit.md`, assorted named files | watchlist discharge |
| SA166 | `scripts/gate_registry.json`, `Makefile`, CI workflow, `docs/others/tech-audit.md` | new process gate |

**Four surfaces are contended and need naming explicitly:**

- `scripts/gate_registry.json` — SA155, SA124, SA123, SA166. All four are on W2 and
  serialized by the merge order, so the registry never crosses worktrees. Preserve that.
- `quickscale_modules/*/module.yml` — SA167a (#8), SA118 (#16), SA167c (#21), in that
  order, **all on W2**. SA167a adds the `apps` projection to five manifests; SA118
  projects the remaining declared defaults over them; SA167c retires `django_apps:`
  across all twelve. Keeping all three on W2 is what stops the module manifests from
  becoming a cross-worktree surface, and is why SA167c could not move to W1 with the other wiring legs.
- `quickscale_core/.../manifest/entry_point.py` — SA167a (W2, #8) then SA167b (W1, #14).
  One-way: SA167b starts from an integration branch that already carries SA167a, and its
  relocation must preserve the manifest-read behaviour SA167a introduced rather than
  reinstating any literal. No W1 ticket other than SA167b touches this file.
- `scripts/test_check_sa117_scope.py` — SA157 then SA124, in that order, same worktree (W2).
- `scripts/test_gate_parity.py` — SA158 (W1, merge #6) then SA135+SA163 (W3, merge #13).
  The rebalance moved SA158 off W2 but this surface already crossed worktrees; the merge
  order keeps it one-way, and SA135+SA163 must sync the integration branch and preserve
  SA158's regenerated oracle before retiring or deriving its own transcribed shell literal.
- `quickscale_core/tests/fixtures/sa90_emission_manifests.json` — SA142, SA118, SA161,
  SA160. SA118 is on W2 and the other three on W3, so this **does** cross worktrees. Each
  rebaseline appends its own `baseline_evidence` entry with per-file rationale; the
  sync-before-merge-back procedure must preserve every prior entry.

`docs/others/arch-audit.md` is on the surface of SA155 and SA163 only (Findings 12 and 13).
Findings 2, 4, and 7 remain untouched, per the "neither" decision above.

---

## v88 backlog track

Each ticket below carries its band, assigned worktree, merge position, and acceptance criteria.

This section holds the implementation tickets; the [audit-derived backlog](#audit-derived-backlog) below holds the rest of the same queue. **Read them as one list** — the merge-order table above is the authority, and four audit tickets sit ahead of work in this section.

Conceptual background, mental models, and implementation notes for **every** ticket live in [v88_ticket_context.md](v88_ticket_context.md); this roadmap remains authoritative for scope, worktrees, and merge order.

- [x] **SA137 — Add `quickscale_devtools` to version propagation.** `Band B · Tier 1 · W1 · merge #2 · deps: none · blocks SA159, SA134`
  Make version check/bump discover and update devtools with the other workspace packages.
  **Acceptance:** `scripts/version_tool.sh check` fails when `quickscale_devtools/pyproject.toml` diverges from `VERSION`; `make version-check` passes with devtools included; `scripts/version_tool.sh update` mutates devtools in the same pass as the other versioned packages; the propagation set is derived, not a second hand-maintained list; `scripts/test_version_tool.py` gains contract coverage for the devtools member and for the failure case.
  **Closure findings/blockers:** publication exclusion remains preserved; devtools stays pyproject-only with no runtime `__version__`; the focused version-tool suite remains gate-orphaned under SA155 ownership; there is no implementation blocker.

- [ ] **SA134 — Derive generated-project version assertions from authoritative pins.** `Band B · Tier 2 · W1 · merge #8 · deps: SA159 (SA137 closed)`
  Remove repeated runtime/dependency literals while retaining meaningful retired-version negative controls.
  **Acceptance:** no test asserts a runtime or dependency version as a bare literal where an authoritative pin exists; assertions read the pin source directly; retired-version negative controls remain and still fail when a retired version is reintroduced; bumping a pin requires no test edit, demonstrated by a temporary bump that leaves the suite green.

- [ ] **SA150 — Document and fail-hard the `QUICKSCALE_LOCAL_WHEELHOUSE` seam.** `Band B · Tier 2 · W1 · merge #11 · deps: SA134 · blocks SA118`
  Carried forward as non-blocking observations from the installed-wheel lifecycle review: the seam is referenced only by production code and its own E2E with no `docs/technical/` description, and `_resolve_local_wheel_dependency()` silently falls back to the manifest version spec when the wheelhouse is set but matches no wheel.
  **Acceptance:** the seam has a `docs/technical/` description covering purpose, accepted values, and failure modes; `_resolve_local_wheel_dependency()` in `quickscale_cli/src/quickscale_cli/utils/module_dependency_sync.py` raises a named, actionable error when `QUICKSCALE_LOCAL_WHEELHOUSE` is set but no wheel matches, instead of returning the manifest spec; a regression test asserts the raise (not a log); the unset-wheelhouse path is unchanged and still resolves from the manifest; the tech-audit **live watch item** is retired with evidence (no numbered finding is open — the severity table stays at zero).

- [ ] **SA124 — Unify SA117 scope-tool path authority.** `Band B · Tier 1 · W2 · merge #10 · deps: SA155, SA157 · blocks SA123`
  Make the CLI, `--help`, Make target, and `scripts/sa117_scope.json` derive one required-path set; carry advisory `SA117E1-REV-004`.
  **Acceptance:** exactly one definition of the required-path set exists; CLI behavior, `--help` text, the Make target, and `scripts/sa117_scope.json` all read it; a test fails if any consumer is added without going through that source; advisory `SA117E1-REV-004` is addressed or explicitly re-carried with rationale; `scripts/test_check_sa117_scope.py` covers the divergence failure.

- [ ] **SA123 — Add dependency-vulnerability and security static-analysis gates.** `Band B · Tier 2 · W2 · merge #12 · deps: SA124 (and SA155, transitively) · blocks SA118`
  Add blocking dependency and focused security scanners with reviewed suppressions; register every new gate through the authoritative gate registry.
  **Acceptance:** a dependency-vulnerability scanner and a focused security static-analysis scanner run as blocking gates; both are registered in `scripts/gate_registry.json` and pass `scripts/check_gate_parity.py`; every suppression carries a written rationale and an owner; the gates fail on a deliberately introduced known-vulnerable pin and on a deliberately introduced flagged pattern, both reverted before merge; `make quality` is no worse than found.

- [ ] **SA167a — Move the five hand-written app declarations into their manifests.** `Band B · Tier 1 · W2 · merge #8 · deps: SA155 (worktree ordering; see note) · blocks SA118, SA167b, SA167c`
  Prerequisite of SA118, not follow-on work. `auth`, `backups`, `notifications`, `orgs`, and `storage` carry their `INSTALLED_APPS` contribution as a Python literal inside a core-side adapter block in `quickscale_core/src/quickscale_core/manifest/entry_point.py` (e.g. `expression={"value": ["quickscale_modules_backups"]}` at `:680`), not in their own `module.yml`. Those are **defaults reachable only through imperative code** — the exact condition SA118's acceptance criterion forbids, so SA118 cannot satisfy it while they stand, and may not widen into them.
  Scope is deliberately narrow: **declaration only, no relocation.** Add a `derivation.wiring_projections` entry with `wiring_field: apps` to each of the five manifests; change core to read it. Adapters stay in `entry_point.py` — moving them is SA167b (#14, W1). The other four core-side modules (analytics, blog, listings, forms) already read `apps` from their manifests and are untouched.
  **Acceptance:** each of the five manifests declares its Django apps in its own `derivation.wiring_projections` `apps` entry; no `apps` value is a Python literal in `entry_point.py` for any module; the resolved `spec.apps` for all twelve modules is byte-identical before and after, recorded as a before/after table; generator emission parity is **unchanged** — no rebaseline, which is what proves the change is behaviour-preserving; a generated project with all modules boots with an identical `MODULE_INSTALLED_APPS`; `make quality` is no worse than found.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/manifest/entry_point.py`, `quickscale_modules/{auth,backups,notifications,orgs,storage}/module.yml`. **Ordering:** must merge before SA118 (#16) and SA167c (#21), which both rewrite the same manifests, and before SA167b (#14, W1), which relocates the adapter blocks this ticket makes manifest-reading.
  **Why #8 and not earlier:** SA167a has no ticket dependencies and could run first, but its acceptance rests on unchanged emission parity and `make quality` no worse than found — neither is verifiable until the gate layer reports the truth. It therefore sits immediately after SA155 (#7), the earliest slot where its own evidence means anything.

- [ ] **SA118 — Project every declared manifest default into wiring.** `Band B · Tier 2 · W2 · merge #16 · deps: SA123, SA150, SA167a · blocks SA167c`
  Materialize authoritative declared defaults without widening into the full imperative-to-declarative migration; rebaseline emission parity with per-file rationale.
  **Acceptance:** every default declared in a module manifest is projected into generated wiring, with no default reachable only through imperative code (the five app-declaration literals are cleared by SA167a first); the imperative-to-declarative migration is *not* attempted — out-of-scope seams are ticketed, not converted; emission parity is rebaselined with a per-file rationale for each changed output; a generated project boots and its module wiring reflects the declared defaults; manifest version-spec handling uses the fail-hard seam from SA150.

- [ ] **SA167b — Relocate the nine core-side adapters into their modules.** `Band B · Tier 2 · W1 · merge #14 · deps: SA167a (shares entry_point.py, merges first), SA150 (worktree ordering) · blocks SA167d`
  With app declarations already in the manifests (SA167a, #8), what remains is relocation. `analytics, auth, backups, blog, forms, listings, notifications, orgs, storage` still register core-side at import time from per-module blocks in `quickscale_core/src/quickscale_core/manifest/entry_point.py` — about 1,139 lines across nine blocks, ranging from 57 (forms) to 265 (notifications). `billing`, `crm`, and `social` already ship module-owned adapters and collapse to a 2–7 line pointer comment each; that is the shape all twelve should end in, leaving `entry_point.py` at roughly 350 lines of discovery machinery.
  Do it as **one ticket, not one per module**: all nine delete from the same file, so per-module tickets would serialize anyway while adding nine-way contention on `entry_point.py` and splitting one logical change nine ways.
  **Acceptance:** every shipped module owns its adapter at `quickscale_modules/<name>/src/quickscale_modules_<name>/adapter.py` exposing `get_manifest_adapter()`; `MANAGED_ADAPTER_ORIGINS` covers the full inventory; no per-module block remains in `entry_point.py`, which retains only generic helpers, the registry, and the public entry point; generator emission parity is unchanged, proving the relocation is behaviour-preserving; the tree conforms to [decisions.md §Module Wiring Authority](decisions.md#module-wiring-authority).
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/manifest/entry_point.py`, every `quickscale_modules/*/adapter.py`, `docs/technical/implementation_contract.md`.

- [ ] **SA167c — Retire `django_apps:` and gate the app declaration.** `Band B · Tier 2 · W2 · merge #21 · deps: SA167a, SA118 (shared manifests) · closes the SA167 family`
  `django_apps:` is declared in eleven manifests and parsed by `manifest/loader.py:597` into `ModuleManifest.django_apps`, where **no production code path reads it**. It is inert declarative surface that reads as authoritative — the trap that made `social` look declared when it was not. One test helper does consume it (`quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py:53`) and silently falls back to a guessed path when it is absent, which is why `social` passed that gate too; that fallback is owned by SA164.
  **Acceptance:** `django_apps:` is either derived from the `apps` wiring projection or removed from all manifests, `ModuleManifest`, and the loader, with no key parsed-but-unread remaining; a conformance gate fails when a module ships models or a migration without declaring at least one Django app, registered in `scripts/gate_registry.json` and passing `scripts/check_gate_parity.py`; the gate is proved by deleting a module's app declaration and observing red, reverted before merge; `test_sa92_migration_squash_guardrail.py` no longer depends on the retired key.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/manifest/{schema,loader}.py`, every `quickscale_modules/*/module.yml`, `scripts/gate_registry.json`, `Makefile`, CI workflow, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`.

- [ ] **SA167d — Drain per-module wiring logic out of the CLI.** `Band B · Tier 3 · W1 · merge #18 · deps: SA167b, SA162 (worktree ordering)`
  `quickscale_cli/src/quickscale_cli/commands/module_config.py` is 2,154 lines carrying a `configure_<name>_module()` / `apply_<name>_configuration()` pair per module — a fifth place the same wiring facts are expressed. Plan-time interactive prompts that collect **desired configuration** are legitimate and stay; anything deciding what a module *wires* belongs in the module.
  **Acceptance:** no function in `module_config.py` decides a module's apps, middleware, settings keys, or URL includes — those come from the module's manifest through its adapter; the remaining surface is desired-configuration collection only, and that boundary is stated in the module's docstring; a test asserts the CLI contributes nothing to `ModuleWiringSpec`; the stale-flow note in [module-extension.md §Building a Module](module-extension.md#building-a-module-authoring-checklist) is retired once the deviation it names is gone.
  **Shared conflict surface:** `quickscale_cli/src/quickscale_cli/commands/module_config.py`, `docs/technical/module-extension.md`.

- [ ] **SA151 — Recreate module migrations as clean initial schemas.** `Band B · Tier 1 · W3 · merge #3 · deps: none · PostgreSQL slot · blocks SA142, SA152 · PARTIAL CHECKPOINT 2026-08-21`
  QuickScale is pre-1.0 and explicitly not backward compatible across versions, so incremental migration history carries no value. Delete every existing migration in `quickscale_modules/*/src/quickscale_modules_*/migrations/` (notably `backups` `0002`–`0005`, plus each module's stale `0001_initial`) and regenerate a single `0001_initial` per module from the current models.
  **Acceptance:** exactly one `0001_initial` per module with models, and no other migration files; a generated project applies all module migrations from an empty database in one pass; `makemigrations --check --dry-run` reports no pending changes for every module; `make test-integration` passes; existing databases are out of scope by policy — the documented upgrade path is a fresh database; the no-migration-history policy is recorded in [decisions.md](decisions.md).

  **Checkpoint disposition:** retain and merge the reviewed partial implementation into `v88`; SA151 remains open, and SA142/SA152 remain blocked until the remaining acceptance work closes.

  **Done at this checkpoint:** all ten modules regenerated to a single `0001_initial`, with schema parity, dry-run, integration, BYPASSRLS, and quality evidence recorded in [CHANGELOG.md](../../CHANGELOG.md). P1 is also completed and convergence-reviewed: social's canonical manifest now owns one static `apps` projection, the bundled snapshot is byte-identical, the module-owned adapter consumes that projection fail-hard, and direct wiring plus repeated apply-path coverage assert the manifest-owned app exactly once.

  **Pending/blocking:** P2 — the exact-ten topology guardrail and non-skippable generated empty-PostgreSQL install/migrate proof — and P3 — the [decisions.md](decisions.md) no-migration-history record, final changelog/roadmap closure, broad terminal gates, and terminal attestation — remain unreached. They were not started because the P1 implementer correctly returned partial when a directly coupled apply-path test outside its five-file allowlist still asserted social-app absence. Convergence repaired only that stale consumer and recorded this partial status; it did not implement P2 or P3. The earlier `apps=()` blocker is resolved, but SA151 remains open until both unreached phases pass.

  **Decision taken 2026-08-21 — authorized.** `social` **is** a managed Django app. A reviewed production-wiring scope is authorized to register `quickscale_modules_social`, rather than injecting it in a test or reducing the expected app set.

  **P1 implementation completed 2026-08-21 (verified by execution, not inspection).** The live source of social's `spec.apps` is now the canonical `derivation.wiring_projections` entry with `wiring_field: apps`; its bundled core snapshot matches byte-for-byte. The module-owned adapter retains its managed-file post-hook but validates and consumes that projection instead of carrying `apps=()`. The top-level `django_apps:` key remains intentionally untouched for SA167c; it is still parsed by `manifest/loader.py:597` and read by no production path, so it was not used as a substitute authority.

  **Terminal-review route: not a blocker (resolved 2026-08-21 by inspection).** The prior run recorded terminal attestation as blocked because the overlay "does not define the requested `final-review` hydration section". It does not, and it is not supposed to: hydration sections are **content slices**, not agents. `adaptive.rules.md` defines seven — Shared, Adaptive, Plan, Codebase Discovery, External Research, Implement, Quality Gate, Change Review — and `~/.claude/agents/Adaptive-final-review.md:115` instructs the agent to *"default to `sections=["change-review"]`"*. The run passed a section name that was never a section. The fix is to call the agent as documented; no overlay change is required, and reading the `change-review` slice costs no independence — that comes from the agent being a separate read-only reviewer with its own attestation rubric, not from a separate content slice.

  **Pending plan:** start from the reviewed P1 checkpoint; implement P2's exact-ten migration guardrail and non-skippable local generated-project test; rerun ten dry checks, generated empty-PostgreSQL migration, restricted and BYPASSRLS suites, aggregate schema/security/seed parity, integration, and quality; then perform P3's decisions/changelog/roadmap closure, convergence, and terminal attestation. Do not begin SA142 or SA152 before SA151 closes.

- [ ] **SA142 — Reuse and clean E2E Docker images.** `Band B · Tier 1 · W3 · merge #9 · deps: SA151 · Docker slot · blocks SA135`
  Separate stable image identity from per-run container/port/volume identity, reclaim variable images under normal cleanup, and preserve `--no-cleanup` diagnostics.
  **Acceptance:** image identity is stable across runs and is reused rather than rebuilt when inputs are unchanged; container, port, and volume identity remain per-run; a normal `make test-e2e` run leaves no variable images behind, verified by an image listing before and after; `--no-cleanup` still preserves containers and logs for diagnosis; a second consecutive run is measurably faster than a cold run.

- [ ] **SA135 — Give test suites an owned PostgreSQL lifecycle.** `Band B · Tier 2 · W3 · merge #13 · deps: SA142 · PostgreSQL + Docker slot · carries SA163`
  Provision and tear down the server used by repository gates; replace the current out-of-band host assumption while retaining an asserted unavailability negative control.
  **Acceptance:** the integration gate provisions its own PostgreSQL 18 server and tears it down, with no reliance on a pre-existing host server; the `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` role contract is preserved; the asserted-unavailability negative control still fails loudly when the server cannot be provisioned, rather than skipping; `make test-integration` passes on a machine with no PostgreSQL running; [validation_policy.md](validation_policy.md) is updated to drop the out-of-band host precondition; image identity follows the SA142 convention.

---

## Audit-derived backlog

Tickets opened from the live findings in [arch-audit.md](../others/arch-audit.md) (2026-08-21) and [tech-audit.md](../others/tech-audit.md) (2026-08-21). Both documents remain the SSOT for finding detail, evidence, and refutation; this section is authoritative for scope and sequencing only.

**These are not follow-on work.** Three of them (SA157, SA158, SA159) plus SA155 are
**band A** in the priority model above and merge *ahead of* most of the implementation
section: they are what makes the gate layer report the truth. SA156 is the fourth and is
closed. SA163 executes inside SA135.
The remaining six are **band C** slack filler. The merge-order table above is the single
authority; this section carries the finding detail.

Every ticket here that closes or changes a live finding takes `docs/others/arch-audit.md`
or `docs/others/tech-audit.md` onto its shared conflict surface per the execution rules.

### Why band A comes first

```text
SA156 (TA63, quality-gate base ref) — CLOSED, 72 of the 74 historical failures
   ├── SA157 (TA64, false-green)    W2 · also SA124's target file
   ├── SA158 (TA66, publish oracle) W1 · red on HEAD, repo-vs-repo
   └── SA159 (TA65, bare python)    W1 · also SA137's target file
              │
              ▼
        SA155 (arch F12, register the gate suites)
        must register GREEN, not red — hence the three above
              │
              ▼
        SA124 (#10) ──► SA123 (#12) ──► SA118 (#14)
        the whole of W2's implementation work sits behind this

SA163 (arch F13, CI environment) ──► rides inside SA135 (W3, merge #13)
```

The failure this ordering prevents: SA124 and SA123 ship acceptance criteria expressed as
gates, written into a suite that nothing executes, beside a test that passes when the tool
under test is deleted, on a branch where the quality baseline has not been enforced once.

- [ ] **SA155 — Give the gate layer a gate of its own.** `Band A · Tier 1 · W2 · merge #7 · deps: SA157, SA158, SA159 (SA156 closed) · blocks SA124, SA123, SA166`
  Closes arch-audit **Finding 12** (`gate-suites-unexecuted`, rank 1, horizon `now`). Gate implementations and their conformance suites live in `scripts/`, deliberately outside `TEST_DIRS` (`Makefile:150`) and outside `.coveragerc` — so gate code is the only first-party code with no owning execution context, while being the code every other gate's credibility rests on. Of 14 `scripts/test_*.py` suites, **4 are wired to a target and 10 are wired to nothing**; `git log -S` shows the orphans were never wired, and the population grows one per new gate. Executed under the project interpreter this pass: **959 passed, 74 failed** across code nothing runs. Hosted *job membership* is genuinely closed by `sync_ci_gate_jobs.py:314-320` and must be preserved — the gap is the suites and the non-`ci.yml` contexts, since `check_gate_parity.py:2509-2511` filters rather than asserts, so parity proves *registered → present* and never *present → registered*.
  Take the audit's **Option 1** here (one registered `check-gate-suites` target running `pytest scripts/ --no-cov`, keeping `scripts/` out of the coverage metric) and leave **Option 2** (a per-gate `self_test` registry binding) to SA123's own acceptance work. Option 3 (relocating the helpers into a first-party package) is explicitly out of scope — it collides with SA124's in-flight `sa117_scope.json` edits.
  **Acceptance:** a `check-gate-suites` target runs the `scripts/` suites with coverage disabled and is registered in `scripts/gate_registry.json` with `required_contexts` covering at least `local-serial`, `local-parallel`, and `hosted`; `scripts/sync_ci_gate_jobs.py` generates its hosted job and `scripts/check_gate_parity.py` passes; the gate is registered **green** — all 74 failures are resolved by the dependency tickets before registration, verified by a recorded pass/fail baseline; `scripts/` remains absent from `.coveragerc` and the `--cov-fail-under=90` product metric is unchanged; the `sync_ci_gate_jobs.py` job-set closure is preserved intact; the six `UNOWNED_JOB_IDS` entries are each justified in writing or registered, with `isolation-conformance` — which has no Makefile target and is invoked only from `ci.yml:634` — resolved explicitly; arch Finding 12 is retired with evidence.
  **Shared conflict surface:** `Makefile`, `scripts/gate_registry.json`, `scripts/sync_ci_gate_jobs.py`, `.github/workflows/ci.yml`, `scripts/check_ci_locally.sh`, `docs/others/arch-audit.md`.

- [ ] **SA158 — Regenerate the stale `publish.yml` parity oracle.** `Band A · Tier 2 · W1 · merge #6 · deps: none (sequenced after SA159 in W1) · blocks SA155`
  Closes tech-audit **TA66** (`gate-parity-publish-oracle-stale`, S3; also arch red flag #1). `scripts/test_gate_parity.py:1090` `test_all_twenty_one_publish_run_values_are_structural` compares `publish.yml`'s ordered `run:` blocks against a literal oracle. `d3d4c633` added two steps and removed two `apt-get` lines and never touched the oracle, so the test is **red on HEAD** — repository content versus repository content, no environment dependence. The next real parity drift in `publish.yml` lands on an already-red test and is indistinguishable from this one.
  **Acceptance:** the oracle matches current `publish.yml` and the test passes; the regenerated diff is reviewed line by line and each changed entry is confirmed to correspond to an intended change in `d3d4c633`/`d4b0e834`; the count-pinned literal oracles named in the arch audit's change-cost probe (`:1064`, `:958`, and the four `all_five_conformance_gates` assertions at `:803`, `:809`, `:815`, `:847`) are either derived or restated as structural assertions rather than exact text, or each is explicitly re-carried with rationale; the tech-audit finding is retired.
  **Shared conflict surface:** `scripts/test_gate_parity.py`, `docs/others/tech-audit.md`, `docs/others/arch-audit.md`.

- [ ] **SA157 — Fix the SA117 scope-tool test that asserts the interpreter's exit code.** `Band A · Tier 2 · W2 · merge #4 · deps: none · blocks SA155, SA124`
  Closes tech-audit **TA64** (`sa117-scope-cli-test-false-green`, S3). `scripts/test_check_sa117_scope.py:596-617` runs `subprocess.run(["python", "scripts/check_sa117_scope.py", …], cwd=version_fixture["root"])` and asserts `returncode == 2`. The fixture root (`:85-96`) contains no `scripts/` subdirectory, so the relative path never resolves and CPython exits 2 on `can't open file` — the exact code asserted. The test passes today, would pass if `check_sa117_scope.py` were deleted, and would pass if the tool accepted the argument it is supposed to reject. argparse also exits 2, which is precisely why the collision is invisible. The same file uses `sys.executable` in three other places, so this is an inconsistency within one file rather than a house convention.
  **Sequencing note:** roadmap **SA124** names this exact file as where its acceptance criterion lands. Fix this first, or SA124's new divergence test is written beside — and most plausibly copied from — a guaranteed false-green, inside a suite nothing executes.
  **Acceptance:** the test invokes `sys.executable` and resolves the script via `pathlib.Path(__file__).with_name("check_sa117_scope.py")`, matching the sibling at `:619-631`; it asserts a distinguishing signal as well as the exit code (`"unrecognized arguments"` in stderr, or that the evidence file was not written), so an interpreter-level failure cannot satisfy it; deleting or renaming `check_sa117_scope.py` turns the test red, demonstrated and reverted; `grep 'subprocess.run(\["python"' scripts/test_*.py` returns zero hits; the tech-audit finding is retired.
  **Shared conflict surface:** `scripts/test_check_sa117_scope.py`, `docs/others/tech-audit.md`.

- [ ] **SA159 — Route repo-source execution through the project interpreter.** `Band A · Tier 2 · W1 · merge #5 · deps: SA137 (closed; same file) · blocks SA155, SA134`
  Closes tech-audit **TA65** (`repo-sources-run-under-bare-python`, S3) and arch red flag #2. `ruff.toml:8-11` states the invariant verbatim — *"Anything that executes repo sources must therefore use the project interpreter (`sys.executable` / the venv), never a bare `python` off PATH"* — and three sites violate it: `scripts/version_tool.sh:11` (`PYTHON="${PYTHON:-python3}"`, used at `:28` to run the authoritative module-discovery shim) and `scripts/lint_frontend.sh:57,:173` (`python3 render_j2_template.py`). Both targets happen to parse under 3.12 today, so all three work **by luck, not by contract**; the repository floor is 3.14 and ruff is configured to emit PEP 758 syntax that nothing below 3.14 can parse, so the day `ruff format` collapses a two-type `except` in `module_discovery.py`, `version_tool.sh check` dies with a `SyntaxError` from a shim rather than a message naming the interpreter. `scripts/_python_requirement.sh` already exists and probes candidate interpreters; neither script sources it.
  **Acceptance:** all three sites resolve the project interpreter (`poetry run python`, `$REPO_ROOT/.venv/bin/python`, or the `_python_requirement.sh` probe) and fail loudly with the required version when none is found, rather than taking whatever `python3` is on PATH; with a 3.12 interpreter first on PATH, `scripts/version_tool.sh check` and `scripts/lint_frontend.sh` still succeed; a pre-commit or CI rule rejects `python3 <repo>.py` in `scripts/*.sh` and `["python",` as an executor of a repo source in `scripts/test_*.py`, making the class self-policing; `scripts/check_ci_locally.sh:62-70`, which selects `python3` the same way but feeds it only a stdlib heredoc, is either brought into the same seam or documented as deliberately adjacent; the tech-audit finding is retired.
  **Shared conflict surface:** `scripts/version_tool.sh`, `scripts/lint_frontend.sh`, `scripts/_python_requirement.sh`, `.pre-commit-config.yaml`, `docs/others/tech-audit.md`.

- [ ] **SA160 — Share one correct CSRF-token helper in the React theme.** `Band C · Tier 2 · W3 · merge #17 · deps: SA161 (emission-parity ordering)`
  Closes tech-audit **TA67** (`spa-csrf-token-duplicate-cookie`, S3) — the only finding in deployment reality #3, the internet-facing generated project. `themes/showcase_react/src/hooks/useApi.ts:20-28` and `src/components/forms/FormRenderer.tsx:206-211` carry the same eleven lines: the parser splits `document.cookie` on `"; csrftoken="` and accepts the result **only when it yields exactly two parts**. Two `csrftoken` cookies yield three, so `getCsrfToken()` returns `''`, `buildRequestHeaders` (`:89-94`) skips `X-CSRFToken`, and Django rejects every POST/PUT/PATCH/DELETE with 403. The triggering state is ordinary: an `app.example.com` deployment alongside a `.example.com` cookie, the outcome of setting or changing `CSRF_COOKIE_DOMAIN`, of a sibling Django app on another subdomain, or of a stale apex-scoped cookie. GETs keep working, so the app looks alive and merely refuses to save, and no error names the cause. Fails closed — availability, not a security hole. There is no shared CSRF helper, no fetch interceptor, and no template-injected token, so no layer-up guard exists.
  **Acceptance:** one shared helper in `src/lib/` iterates cookies rather than counting split segments — splitting on `'; '`, matching the name exactly, and `decodeURIComponent`-ing the value, per Django's own documented `getCookie` — and both call sites import it with no third variant remaining; a `vitest` table test covers `'csrftoken=A; csrftoken=B'`, `'sessionid=x; csrftoken=A'`, `'csrftoken=A'`, and `''`, with the first three returning a non-empty token; the tech-audit finding is retired.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/`, generator emission parity baselines, `docs/others/tech-audit.md`.

- [ ] **SA161 — Remove the dead `get_client_ip` definitions from generated settings.** `Band C · Tier 3 · W3 · merge #16 · deps: SA135 (worktree ordering)`
  Closes tech-audit **TA68** (`generated-settings-dead-client-ip`, S4). `templates/project_name/settings/base.py.j2:61` and `settings/production.py.j2:123` both define a module-level `get_client_ip(request)`, and the production copy rebinds it under a comment claiming the rebind exists "so that production defaults … are actually in effect at request time". Neither is reachable: Django's `Settings` copies only **uppercase** names off the settings module, so `django.conf.settings.get_client_ip` does not exist, and grep across all templates returns only the two definitions. The live implementation is `quickscale_modules_orgs.current_org.get_client_ip`, which reads the uppercase `USE_X_FORWARDED_FOR` / `TRUSTED_PROXY_COUNT` settings dynamically and is correct.
  **Acceptance:** both definitions are deleted, or each carries a comment pointing at the orgs helper as the live implementation; the uppercase settings and the `REST_FRAMEWORK["NUM_PROXIES"]` recomputation are retained unchanged; the misleading behavioural comment at `production.py.j2:119-122` is removed either way; a generated project boots and proxy-aware client-IP resolution is unchanged, asserted by a test; emission parity is rebaselined with rationale; the tech-audit finding is retired.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/`, emission parity baselines, `docs/others/tech-audit.md`.

- [ ] **SA162 — Fix the deprecated bool inversion in the CSRF AST gate.** `Band C · Tier 3 · W1 · merge #15 · deps: SA150 (worktree ordering)`
  Closes tech-audit **TA69** (`csrf-gate-bool-invert-deprecated`, S4) and arch red flag #5. `scripts/check_csrf_exempt_gate.py:271` uses `~val != 0` where `val` may be a `bool`; this raises `DeprecationWarning` on 3.12+ and is **removed in Python 3.16**, verified under `-W error::DeprecationWarning` on 3.14.6. Reachable only when analysed source contains a literal `~True`/`~False`, so the cost is future breakage rather than present miscomputation.
  **Correction to carry:** the arch audit's suggested fix (`not val`) is **wrong** and must not be applied. The function evaluates the truthiness of a *bitwise invert* in analysed source: `~True` is `-2` (truthy) whereas `not True` is `False`, so that substitution would make the CSRF gate misjudge every `~<constant>` operand it sees. The correct fix is `~int(val) != 0`, preserving the semantics.
  **Acceptance:** the expression is `~int(val) != 0` or equivalent; the gate runs clean under `-W error::DeprecationWarning`; a test pins the gate's verdict on analysed source containing `~True` and `~False` so the semantics cannot silently change; the arch-audit red flag is retired with the correction recorded, and the tech-audit finding is retired.
  **Shared conflict surface:** `scripts/check_csrf_exempt_gate.py`, `docs/others/tech-audit.md`, `docs/others/arch-audit.md`.

- [ ] **SA163 — Derive the CI PostgreSQL environment from one authoritative source.** `Band B · Tier 2 · W3 · merge #13 — executes inside SA135, not as a separate pass`
  Closes arch-audit **Finding 13** (`ci-environment-hand-replicated`, rank 2, horizon `now`). The gate registry declares *which* gates run in *which* contexts, but the environment those gates require is expressed nowhere declaratively and is hand-replicated as shell across **13 stations**: the PGDG PG18 install in four copies (`ci.yml:92-107`, `ci.yml:408-427`, `publish.yml:161-187`, `e2e.yml:74-91`), divergent PG18 verification (three check `command -v` *and* `--version | grep "(PostgreSQL) 18"`; `e2e.yml:92` checks only `test -x`), four `createdb` lists, four grant loops, five `QS_*_DB_USER` blocks, and a **14th** station where `scripts/test_gate_parity.py:1125-1180` transcribes the shell verbatim as a Python literal. `nightly-bypassrls.yml:81-82` installs plain `postgresql-client` — Ubuntu 16.x, no PGDG — while creating `test_quickscale_backups` and setting `QS_BACKUPS_DB_USER`, against `ci.yml:93-95`'s statement that the backups DR engine enforces a PostgreSQL 18 `pg_dump`/`pg_restore` contract that 16.x fails.
  Two apparent divergences are **deliberate and verified correct — do not "fix" them**: the 6-entry `QS_*_DB_USER` block at `ci.yml:627-632` is exactly `orgs` plus `RLS_MODULES` from `test_isolation_conformance.sh:141`, and the isolation job's 11-database list omits `backups` because that job runs no backups tests.
  Take **Option 1** (one `scripts/provision_ci_postgres.sh`, four callers, module list derived from the discovery shim exactly as `check_sa117_scope.py:48` already does). Do it **inside SA135**, whose allowlist already spans `scripts/test_integration.sh`, `scripts/provision_test_roles.sh`, the `Makefile`, and the documented DB precondition — not as a separate pass over the same files. Option 2 (an `environment` block in the gate registry) only if SA123's registry work lands cleanly first, since both bump the registry schema.
  **Acceptance:** the PGDG install, `createdb` loop, and grant loop exist once and all four workflows call them; the module universe is derived from `contracts/module_discovery.py --list-modules` and fails hard when unavailable, with no hand-maintained module list among the provisioning stations; PG18 client verification is identical in all four contexts, including `e2e.yml`; the nightly PostgreSQL 16 client question is settled by determining whether `make test-bypassrls` reaches a `pg_dump`/`pg_restore` path — if it does, the divergence is a live defect and is fixed; the two deliberate divergences above are preserved and documented as deliberate; `test_gate_parity.py`'s transcribed shell literal is retired or derived; `QUICKSCALE_ALLOW_BYPASSRLS: "0"` at `ci.yml:626` and the restricted-role isolation connection survive the refactor unchanged; arch Finding 13 is retired with evidence.
  **Shared conflict surface:** all four `.github/workflows/`, `scripts/provision_ci_postgres.sh` (new), `scripts/test_integration.sh`, `scripts/provision_test_roles.sh`, `scripts/test_gate_parity.py`, `Makefile`, `docs/others/arch-audit.md`. **Serialization:** inherits SA135's exclusive PostgreSQL + Docker slot.

- [ ] **SA164 — Adjudicate the arch-audit watchlist's unevaluable and drifted items.** `Band C · Tier 3 · W1 · merge #19 · deps: SA151 (re-anchors the SA92 item)`
  The arch audit carries five watch items; three are simply not fired and need no work, but two carry explicit actions and one is a naming question that becomes load-bearing on a specific trigger.
  - **SA92 migration-squash discovery tuple — artifact located 2026-08-21, now evaluable.** The audit recorded this as unlocatable, but the artifact is `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` — a bounded literal tripwire for cross-table `UPDATE … SET organization_id` DML in migrations. The prior search missed it because it grepped for `squash` in source rather than in test filenames. Two live observations: its `_migdir()` helper (`:53-59`) reads the **inert** `django_apps:` manifest key and then silently falls back to the conventional path when it is absent. P1 gave `social` a production `apps` wiring projection but intentionally did not add the inert key, so this helper still passes social only through that fallback — a silent fallback of exactly the class [tech-audit.md](../others/tech-audit.md) owns; and its authoritative backstop is a catalog/data parity gate anchored to `v87`, the retired release ref SA156 just removed from the quality gate. Re-anchor both against SA151's regenerated migrations.
  - **Privileged-command template/runtime pair — values verified equal, governance artifacts disagree.** `production.py.j2:185` and `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py:36` both hold `frozenset({"migrate", "createcachetable"})`, but the `apps.py` docstring calls itself "the single source of truth for which commands are privileged" while the template holds an independent copy. The values agree; the claimed authority does not.
  - **`trigger_inputs` has drifted from its name.** `check_gate_parity.py:2652-2690` uses the field as a bidirectional partition of `e2e.yml`'s path allowlist, not as "what changes should trigger this gate" — which is why `check-core-compat`'s trigger is `quickscale_modules/backups/**`. Not a defect; the check it performs is real and exact. Becomes load-bearing only if a gate is ever *skipped* on the basis of `trigger_inputs`.
  **Acceptance:** the SA92 item is re-anchored to `test_sa92_migration_squash_guardrail.py` with a stated trigger, its `_migdir()` fallback fails loudly instead of guessing the path, and its `v87`-anchored parity backstop is re-anchored to SA151's regenerated migrations; the privileged-command SSOT claim is made true — either the template reads the runtime frozenset or the docstring stops claiming sole authority — with a test asserting the two cannot diverge; `trigger_inputs` is either renamed to describe what it does or its docstring/schema description records the actual semantics plus the skip-based promotion trigger; the three not-fired items (module universe in environment lists, frontend runtime module keys, and the now-absorbed watch half of Finding 13) are re-stated with their triggers intact; `docs/others/arch-audit.md` is updated in the same change.
  **Shared conflict surface:** `docs/others/arch-audit.md`, `quickscale_core/.../templates/project_name/settings/production.py.j2`, `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py`, `scripts/gate_registry.json`, `scripts/check_gate_parity.py`.

- [ ] **SA165 — Discharge the tech-audit watch items that carry an action.** `Band C · Tier 3 · W1 · merge #18 · deps: SA150 (owns an item excluded here)`
  Of the remaining items in the tech audit's *Notes*, most are accepted trade-offs or are owned elsewhere (`SA150` owns the local-wheelhouse seam; integration-branch CI, generator lock generation, the DB-free healthcheck, the CRM count fallbacks, and non-durable atomic state writes are each recorded as deliberate and are **not** in this ticket's scope). Four carry a concrete action:
  - **`flush_empty_consolidated_sections` swallows a corrupt state file.** `quickscale_core/src/quickscale_core/schema/state_schema.py:386-388` returns silently on `yaml.YAMLError, OSError`, skipping the explicit `modules: {}` / `managed_files: []` markers downstream readers use to distinguish "M2 has spoken" from pre-M2 state. The trigger is narrow — the file was just written successfully by `save()` — but this is exactly the silent-fallback shape the Fail-Hard Principle names (`decisions.md:634`, `:716-732`), and `tech-audit.md` is the declared SSOT for that class.
  - **The isolation-gate skip allowlist matches on message, not test identity.** `scripts/test_isolation_conformance.sh:184` keys on `message.startswith('got empty parameter set')`, silencing an empty parameter set on *any* of the eleven parametrized tests in `test_tenant_table_conformance.py`, not only the two `PENDING_REMEDIATION` ones its own comment describes. Narrowing it to the two test names costs one line.
  - **`_HOST_DEPENDENT_PATHS` is a new hand-maintained exception station.** `be5cf024` added `frozenset({".env"})` to the SA90 emission byte-parity gate (`quickscale_core/tests/test_generator/test_generator.py:1023`). The justification is sound and the `755`/`644` mode normalization correctly removes a umask dependency, but this is an exception list on the repository's strictest gate: a second entry deserves scrutiny, a third deserves a derivation.
  - **Generated local-development credentials are predictable by construction.** `generator.py:507-508` derives `runtime_db_role = f"{package_name}_app"` and `runtime_db_password = f"{role}_password"` into `db/init.sql`, `docker-compose.yml`, and `.env.example`, none of which `.gitignore.j2` excludes. Safe as shipped — no published DB port, local dev only, production supplies `RUNTIME_DATABASE_URL` from the environment — but undocumented.
  **Acceptance:** `flush_empty_consolidated_sections` raises or reports rather than returning silently, with a regression test asserting the raise and not a log, and the fail-hard deviation is retired from the audit; the isolation skip allowlist keys on the two `PENDING_REMEDIATION` test identities rather than a message prefix, and a deliberately emptied ENROLLED set turns the gate red; `_HOST_DEPENDENT_PATHS` gains a written per-entry rationale and a monotonicity note stating the second/third-entry escalation, or is derived; `OPERATIONS.md` states explicitly that the generated local credentials must not survive into any shared environment; `docs/others/tech-audit.md` is updated to reflect each discharge.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/schema/state_schema.py`, `scripts/test_isolation_conformance.sh`, `quickscale_core/tests/test_generator/test_generator.py`, `quickscale_core/.../templates/OPERATIONS.md.j2`, `docs/others/tech-audit.md`.

- [ ] **SA166 — Require a testimony trail for behavioural commits.** `Band C · Tier 3 · W2 · merge #20 · deps: SA155, SA118`
  Closes the tech audit's carried tooling gap *"no gate requires a changelog/ticket trail for behavioural commits"*. `d3d4c633` and `d4b0e834` were both titled "v0.87.0: QuickScale 0.87.0" while in fact changing hosted and publish provisioning, and `d3d4c633` left a repository conformance test red (TA66/SA158). Both audits independently flagged the same shape: a release-shaped message carrying a CI-topology change, read closely only because the arch audit's delta-classification step treats unlabeled-behavioural commits as read-at-full-depth. Recorded in the audit as maintainer-process risk rather than a source finding, which is why this is Tier 3 and sits behind SA155 — a process gate is worth little while the gate layer it would run in is itself unexecuted.
  **Acceptance:** a change touching `.github/workflows/`, `scripts/gate_registry.json`, or the provisioning stations requires either a roadmap ticket reference or a `CHANGELOG.md` entry, enforced mechanically rather than by convention; the check is registered in `scripts/gate_registry.json` and passes `scripts/check_gate_parity.py`; the gate fails on a deliberately introduced untitled workflow change, reverted before merge; false-positive cost is measured on the existing history and the rule is narrowed until it is quiet on legitimate release commits; the tooling gap is retired from the tech audit.
  **Shared conflict surface:** `scripts/gate_registry.json`, `Makefile`, CI workflow, `docs/others/tech-audit.md`.

### Audit items deliberately **not** ticketed

Recorded so the absence is a decision rather than an oversight.

| Item | Source | Why no ticket |
|---|---|---|
| Finding 7 `generated-file-ownership-unmodeled` | arch, deferred | Held by the **"neither" prioritization decision** above, which names it explicitly. Trigger: a third generated-project consumer, public updater, emitted-file expansion, or second theme. Related weakness is tracked in SA152. |
| Finding 2 `deletion-invariants-per-boundary-reimplementation` | arch, deferred | Held by the same decision. Trigger: `teams`, a GDPR erasure command, bulk-admin deletion, or a second deletion boundary. Design together with Finding 4 at `teams` kickoff. |
| Finding 4 `org-model-universe-hand-enumerated` | arch, deferred | Held by the same decision. Trigger: `teams` adds a tenant model, or a module adds a `PROTECT`/non-deferrable dependency among purge-owned rows. SA151 is noted as a natural derivation moment for the next audit pass. |
| Arch red flag — `tech-audit.md` header reads `Branch: v87` | arch | **Already resolved** — the 2026-08-21 regeneration carries `Branch: v88`. |
| Tooling gaps — dependency-vulnerability scanner, security static analysis | tech | Already owned by **SA123** (merge #12). |
| Watch item — local-wheelhouse seam | tech | Already owned by **SA150** (merge #11). |
| Tooling gaps — interpreter grep gate, CSRF helper test | tech | Each is an acceptance criterion inside **SA159** and **SA160** respectively rather than separate work. The gate-default-refs gap was discharged by SA156. |
| Structural smells (3) | tech | Declared by the tech audit as candidate inputs for the companion structural pass, explicitly "not findings here". One was the structural half of SA156 (closed), one is SA159's; the third (no `src/lib/http` seam) is created by SA160. |
| Watch items recorded as deliberate | tech *Notes* | Integration-branch CI, generator lock-generation policy, the DB-free healthcheck, CRM cross-tenant count fallbacks, and rename-atomic-but-not-durable state writes are each argued and accepted in the audit; re-examine only on the triggers stated there. |
| Clean sweeps (10) | tech | Verified-clean records, not open items. |

---

## Unscheduled backlog (post-v88)

Not assigned to a v88 track. Listed here so the finding is not lost.

- [ ] **SA152 — Refresh the beta-migration maintainer targets for the current release.** `Post-v88 · Tier 3 · deps: SA151`
  Audit of `make beta-migrate-fresh` / `make beta-migrate-in-place` (2026-08-21) found the mechanics current: the Makefile flag surface (`DONOR`, `RECIPIENT`, `DRY_RUN`, `CONTINUE`, `REPORT`) matches `build_argument_parser()` in `quickscale_devtools/src/quickscale_devtools/beta_migration.py`; every command in `VERIFICATION_COMMAND_SPECS` still exists on the CLI; and the file-ownership taxonomy is in sync with the emitted `showcase_react` template set, enforced by `quickscale_cli/tests/test_beta_migration_ownership_conformance.py` (7 passing, including forward and reverse staleness checks). The residual gaps are these:
  - **SA151 collision.** The workflow's verification stack runs `quickscale manage migrate` against a recipient that may carry an existing database. SA151 deletes all module migration history and documents a fresh database as the only upgrade path, which invalidates the in-place workflow's implicit assumption. This must be resolved after SA151 merges, not before.
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
