# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Changelog](../../CHANGELOG.md) | [Validation Policy](validation_policy.md) | [v88 Ticket Context](v88_ticket_context.md) | [Release Summary Template](release_summary_template.md)

## Purpose

This is the current task planner. It contains open planned work only. Completed tickets, closed findings, review history, and release evidence live in [CHANGELOG.md](../../CHANGELOG.md) and version control.

### Execution rules

- Work develops in three worktrees and merges into the clean `v88` integration branch (created by `V88-KICKOFF`). Never implement directly on the integration branch.
- One reviewed child runs at a time per track. Umbrellas are acceptance-only; their children own implementation.
- Start from a clean worktree after merging the integration branch. Before merge-back, sync the integration branch into the worktree, resolve there, run the ticket's verification, review the exact tip, then merge that tip.
- Every handoff declares its file allowlist, commands, expected exits/artifacts, rollback, and focused validation. Scope findings are ticketed rather than fixed in place.
- Leave `make quality` no worse than found. Do not raise a complexity ceiling or reintroduce file-line ceilings.
- Shared closeout conflict surfaces are `CHANGELOG.md`, `docs/technical/roadmap.md`, and `docs/technical/decisions.md` when policy changes. `docs/others/arch-audit.md` and `docs/others/tech-audit.md` join that surface only when a ticket changes or closes a live audit finding. The sync-before-merge-back procedure above must preserve every concurrent entry, resolve these files in the worktree, rerun the ticket's checks, and leave no unmerged files before the exact tip is reviewed and merged.
- PostgreSQL/Docker work is serialized across worktrees. Track 3 has priority while a service-backed critical-path leg is active.
- A ticket whose deliverable is Git ref state cannot be delegated to a file-editing worker. Route it to a maintainer session with ref authority and push credentials.

---

## v88 release plan

### Prioritization decision (recorded 2026-08-21)

**Choice: neither.** Architectural Findings 2 (deletion-cleanup coordination), 4 (organization purge ordering), and 7 (generated-file ownership) stay behind their growth triggers. No `teams` domain work and no third generated-project updater is scheduled for v88. This is consistent with the standing decision that `teams` is not planned, and it keeps v88 free of speculative architecture. The nine backlog tickets are planned on their own merits below.

Consequence for the gated findings: they remain live in [arch-audit.md](../others/arch-audit.md) and are **not** closed by any v88 ticket. A v88 ticket may not widen into them; if implementation work discovers a trigger has actually fired, that is a scope finding and gets its own ticket rather than an in-place fix.

`V88-KICKOFF` is closed by this section together with the dependency graph, acceptance criteria, and track/merge-order assignment that follow.

### Dependency graph and critical path

```text
v88 implementation — three tracks, nine tickets

Track 1 (pins & dependency-spec authority)
  SA137 ──► SA134 ──► SA150
  devtools in      derive generated-    fail-hard the
  version prop.    project assertions   wheelhouse seam
                   from authoritative
                   pins

Track 2 (gates & declared wiring)
  SA124 ──► SA123 ──► SA118
  one scope-tool    dependency +        project declared
  path authority    security gates      manifest defaults
                    via gate registry   into wiring
                                          ▲
                              SA150 merges first ──┘  (manifest-spec coordination)

Track 3 (service-backed — exclusive PostgreSQL/Docker slot)
  SA151 ──► SA142 ──► SA135
  clean initial     stable E2E image    owned PostgreSQL
  migrations        identity            lifecycle for suites
```

**Longest open chain:** Track 3, `SA151 → SA142 → SA135`, three serialized service-backed legs. Track 3 holds the exclusive PostgreSQL/Docker slot for the whole release and therefore has priority whenever one of its legs is active.

**Inter-track edges:** exactly one — `SA150` must merge before `SA118`, because both touch module-manifest version-spec handling and `SA118` must project defaults over the fail-hard seam `SA150` establishes, not over the current silent fallback. No other cross-track edge exists; Tracks 1 and 2 are otherwise independent.

**Parallelism result:** three tracks run concurrently at 3/3/3. Track 3 is the critical path. Tracks 1 and 2 have slack; if either finishes early, the available rebalance is to pull nothing forward from Track 3 (the PostgreSQL/Docker slot is exclusive) and instead take the next Track 3 ticket's *non-service* preparation only if it can be verified without the slot.

### Track assignment and merge order

| # | Ticket | Tier | Track | Merges after | Service slot |
|---|---|---|---|---|---|
| 1 | **SA137** | 1 | Track 1 | — | no |
| 2 | **SA124** | 1 | Track 2 | — | no |
| 3 | **SA151** | 1 | Track 3 | — | **yes** — PostgreSQL |
| 4 | **SA134** | 2 | Track 1 | SA137 | no |
| 5 | **SA142** | 1 | Track 3 | SA151 | **yes** — Docker |
| 6 | **SA123** | 2 | Track 2 | SA124 | no |
| 7 | **SA150** | 2 | Track 1 | SA134 | no |
| 8 | **SA135** | 2 | Track 3 | SA142 | **yes** — PostgreSQL + Docker |
| 9 | **SA118** | 2 | Track 2 | SA123, **SA150** | no |

Within a track, one reviewed child runs at a time. Merge order is the table order; a ticket syncs the integration branch into its worktree, resolves there, reruns its own verification, and only then merges its exact reviewed tip.

### Shared conflict surfaces

Standing surface for every ticket: `CHANGELOG.md`, `docs/technical/roadmap.md`. Additional per-ticket surfaces:

| Ticket | Additional shared surface | Why |
|---|---|---|
| SA151 | `docs/technical/decisions.md` | records the no-migration-history policy |
| SA123 | `scripts/gate_registry.json`, `Makefile`, CI workflow | new blocking gates |
| SA124 | `scripts/gate_registry.json`, `Makefile`, `scripts/sa117_scope.json` | gate + path authority |
| SA134 | — | test-side literals only |
| SA137 | `VERSION`, `scripts/version_tool.sh`, `Makefile` | propagation set |
| SA118 | module manifests, wiring emission baselines | manifest projection |
| SA142 | `scripts/test_e2e.sh`, E2E fixtures | image/container identity |
| SA135 | `scripts/test_integration.sh`, `scripts/provision_test_roles.sh`, `Makefile`, `docs/technical/validation_policy.md` | changes the documented DB precondition |
| SA150 | `docs/others/tech-audit.md` (closes a live finding), new `docs/technical/` seam doc | fail-hard + documentation |

`docs/others/arch-audit.md` is **not** on any v88 ticket's surface: the "neither" decision closes no architectural finding this release.

---

## v88 backlog track

`V88-KICKOFF` is closed. Each ticket below carries its assigned track, merge position, and acceptance criteria.
Conceptual background and implementation context for all nine tickets live in [v88_ticket_context.md](v88_ticket_context.md); this roadmap remains authoritative for scope, tracks, and merge order.

- [x] **V88-KICKOFF — Open v88 planning and assign executable tracks.** `Tier 1 · Track: kickoff · CLOSED 2026-08-21`
  v88 integration branch created; prioritization choice recorded as **neither**; dependency graph, acceptance criteria, tracks, shared conflict surfaces, and merge order assigned above.

- [ ] **SA137 — Add `quickscale_devtools` to version propagation.** `Tier 1 · Track 1 · merge #1 · deps: none`
  Make version check/bump discover and update devtools with the other workspace packages.
  **Acceptance:** `scripts/version_tool.sh check` fails when `quickscale_devtools/pyproject.toml` diverges from `VERSION`; `make version-check` passes with devtools included; `scripts/version_tool.sh update` mutates devtools in the same pass as the other versioned packages; the propagation set is derived, not a second hand-maintained list; `scripts/test_version_tool.py` gains contract coverage for the devtools member and for the failure case.

- [ ] **SA134 — Derive generated-project version assertions from authoritative pins.** `Tier 2 · Track 1 · merge #4 · deps: SA137`
  Remove repeated runtime/dependency literals while retaining meaningful retired-version negative controls.
  **Acceptance:** no test asserts a runtime or dependency version as a bare literal where an authoritative pin exists; assertions read the pin source directly; retired-version negative controls remain and still fail when a retired version is reintroduced; bumping a pin requires no test edit, demonstrated by a temporary bump that leaves the suite green.

- [ ] **SA150 — Document and fail-hard the `QUICKSCALE_LOCAL_WHEELHOUSE` seam.** `Tier 2 · Track 1 · merge #7 · deps: SA134`
  Carried forward as non-blocking observations from the installed-wheel lifecycle review: the seam is referenced only by production code and its own E2E with no `docs/technical/` description, and `_resolve_local_wheel_dependency()` silently falls back to the manifest version spec when the wheelhouse is set but matches no wheel.
  **Acceptance:** the seam has a `docs/technical/` description covering purpose, accepted values, and failure modes; `_resolve_local_wheel_dependency()` in `quickscale_cli/src/quickscale_cli/utils/module_dependency_sync.py` raises a named, actionable error when `QUICKSCALE_LOCAL_WHEELHOUSE` is set but no wheel matches, instead of returning the manifest spec; a regression test asserts the raise (not a log); the unset-wheelhouse path is unchanged and still resolves from the manifest; the tech-audit **live watch item** is retired with evidence (no numbered finding is open — the severity table stays at zero).

- [ ] **SA124 — Unify SA117 scope-tool path authority.** `Tier 1 · Track 2 · merge #2 · deps: none`
  Make the CLI, `--help`, Make target, and `scripts/sa117_scope.json` derive one required-path set; carry advisory `SA117E1-REV-004`.
  **Acceptance:** exactly one definition of the required-path set exists; CLI behavior, `--help` text, the Make target, and `scripts/sa117_scope.json` all read it; a test fails if any consumer is added without going through that source; advisory `SA117E1-REV-004` is addressed or explicitly re-carried with rationale; `scripts/test_check_sa117_scope.py` covers the divergence failure.

- [ ] **SA123 — Add dependency-vulnerability and security static-analysis gates.** `Tier 2 · Track 2 · merge #6 · deps: SA124`
  Add blocking dependency and focused security scanners with reviewed suppressions; register every new gate through the authoritative gate registry.
  **Acceptance:** a dependency-vulnerability scanner and a focused security static-analysis scanner run as blocking gates; both are registered in `scripts/gate_registry.json` and pass `scripts/check_gate_parity.py`; every suppression carries a written rationale and an owner; the gates fail on a deliberately introduced known-vulnerable pin and on a deliberately introduced flagged pattern, both reverted before merge; `make quality` is no worse than found.

- [ ] **SA118 — Project every declared manifest default into wiring.** `Tier 2 · Track 2 · merge #9 · deps: SA123, SA150`
  Materialize authoritative declared defaults without widening into the full imperative-to-declarative migration; rebaseline emission parity with per-file rationale.
  **Acceptance:** every default declared in a module manifest is projected into generated wiring, with no default reachable only through imperative code; the imperative-to-declarative migration is *not* attempted — out-of-scope seams are ticketed, not converted; emission parity is rebaselined with a per-file rationale for each changed output; a generated project boots and its module wiring reflects the declared defaults; manifest version-spec handling uses the fail-hard seam from SA150.

- [ ] **SA151 — Recreate module migrations as clean initial schemas.** `Tier 1 · Track 3 · merge #3 · deps: none · PostgreSQL slot`
  QuickScale is pre-1.0 and explicitly not backward compatible across versions, so incremental migration history carries no value. Delete every existing migration in `quickscale_modules/*/src/quickscale_modules_*/migrations/` (notably `backups` `0002`–`0005`, plus each module's stale `0001_initial`) and regenerate a single `0001_initial` per module from the current models.
  **Acceptance:** exactly one `0001_initial` per module with models, and no other migration files; a generated project applies all module migrations from an empty database in one pass; `makemigrations --check --dry-run` reports no pending changes for every module; `make test-integration` passes; existing databases are out of scope by policy — the documented upgrade path is a fresh database; the no-migration-history policy is recorded in [decisions.md](decisions.md).

- [ ] **SA142 — Reuse and clean E2E Docker images.** `Tier 1 · Track 3 · merge #5 · deps: SA151 · Docker slot`
  Separate stable image identity from per-run container/port/volume identity, reclaim variable images under normal cleanup, and preserve `--no-cleanup` diagnostics.
  **Acceptance:** image identity is stable across runs and is reused rather than rebuilt when inputs are unchanged; container, port, and volume identity remain per-run; a normal `make test-e2e` run leaves no variable images behind, verified by an image listing before and after; `--no-cleanup` still preserves containers and logs for diagnosis; a second consecutive run is measurably faster than a cold run.

- [ ] **SA135 — Give test suites an owned PostgreSQL lifecycle.** `Tier 2 · Track 3 · merge #8 · deps: SA142 · PostgreSQL + Docker slot`
  Provision and tear down the server used by repository gates; replace the current out-of-band host assumption while retaining an asserted unavailability negative control.
  **Acceptance:** the integration gate provisions its own PostgreSQL 18 server and tears it down, with no reliance on a pre-existing host server; the `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` role contract is preserved; the asserted-unavailability negative control still fails loudly when the server cannot be provisioned, rather than skipping; `make test-integration` passes on a machine with no PostgreSQL running; [validation_policy.md](validation_policy.md) is updated to drop the out-of-band host precondition; image identity follows the SA142 convention.

---

## Unscheduled backlog (post-v88)

Not assigned to a v88 track. Listed here so the finding is not lost.

- [ ] **SA152 — Refresh the beta-migration maintainer targets for the current release.** `Tier 3 · Track: unscheduled · deps: SA151`
  Audit of `make beta-migrate-fresh` / `make beta-migrate-in-place` (2026-08-21) found the mechanics current: the Makefile flag surface (`DONOR`, `RECIPIENT`, `DRY_RUN`, `CONTINUE`, `REPORT`) matches `build_argument_parser()` in `quickscale_devtools/src/quickscale_devtools/beta_migration.py`; every command in `VERIFICATION_COMMAND_SPECS` still exists on the CLI; and the file-ownership taxonomy is in sync with the emitted `showcase_react` template set, enforced by `quickscale_cli/tests/test_beta_migration_ownership_conformance.py` (7 passing, including forward and reverse staleness checks). The residual gaps are these:
  - **SA151 collision.** The workflow's verification stack runs `quickscale manage migrate` against a recipient that may carry an existing database. SA151 deletes all module migration history and documents a fresh database as the only upgrade path, which invalidates the in-place workflow's implicit assumption. This must be resolved after SA151 merges, not before.
  - **No end-to-end exercise.** The targets appear in no CI workflow and no entry in `scripts/gate_registry.json`. Coverage is unit-level taxonomy conformance only; a `DRY_RUN=1` / checkpoint-only path is never run against a real donor/recipient pair, so breakage surfaces first for a maintainer mid-migration.
  - **Silent skip in the conformance gate.** `_template_emitted_paths()` calls `pytest.skip()` when the template tree is not found, so a path-resolution regression turns the ownership gate green instead of red. This is the silent-fallback pattern tracked in [tech-audit.md](../others/tech-audit.md).
  - **Stale doc provenance.** [beta-site-migration.md](../planning/beta-site-migration.md) is headed "shipped in v0.81.0" against a `VERSION` of 0.87.0, and describes the tool as "backed by Python scripts under `scripts/`" when `scripts/beta_migrate.py` is an eight-line wrapper over `quickscale_devtools`.

  **Acceptance:** the in-place workflow's database precondition is reconciled with the SA151 no-migration-history policy and the resolution is stated in the playbook; a cheap non-mutating smoke gate exercises both targets against a generated donor/recipient pair (`DRY_RUN=1` for fresh-first, checkpoint-only for in-place) and is registered in `scripts/gate_registry.json` with `scripts/check_gate_parity.py` passing; `_template_emitted_paths()` fails loudly instead of skipping when the template tree is missing, with a regression test asserting the raise; the playbook's version and implementation-location claims match the tree; `make quality` is no worse than found.

  **Shared conflict surface:** `docs/planning/beta-site-migration.md`, `scripts/gate_registry.json`, `Makefile`, CI workflow, `docs/others/tech-audit.md`.

---

## References

- [Changelog — completed and closed work](../../CHANGELOG.md)
- [Architectural audit — live structural findings](../others/arch-audit.md)
- [Technical audit — live defect posture](../others/tech-audit.md)
- [Decisions — policy authority](decisions.md)
- [Validation policy — command authority](validation_policy.md)
- [v88 ticket context — concepts and implementation notes](v88_ticket_context.md)
