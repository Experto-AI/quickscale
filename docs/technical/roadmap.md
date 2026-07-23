# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [How QuickScale Uses Adaptive](../others/adaptive.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks pending roadmap work. Detailed completed implementation history is in [CHANGELOG.md](../../CHANGELOG.md). Each phase is sized as [Adaptive](../others/adaptive.md) Tier 1–2; split before implementing if a checklist item is Tier 3.

**Rules:**
- Keep open todo items here.
- Move detailed completed implementation history to CHANGELOG.md.
- Each open phase links back (`why →`) to the finding that justifies it.

---

## Parallel Execution Tracks

Work is split across 3 git worktrees that develop in parallel and merge back to `v87` after each phase. `v87` is the clean integration branch — never commit directly to it.

### Start procedure

Run at the beginning of every new phase, before touching any files:

```bash
cd /home/victor/code/quickscale-wt-track{N}
git status             # must be clean — commit or stash any in-progress work first
git merge v87          # pull in everything other tracks have merged since last sync
# resolve any conflicts, then continue with the phase
```

### Merge procedure

Run when a phase (or a full milestone) is complete and ready to integrate:

```bash
cd /home/victor/code/quickscale-wt-track{N}
git merge v87          # sync latest before merge-back; resolve conflicts here
# run phase verification tests
cd /home/victor/code/quickscale
git merge --no-ff wt-track{N}
```

> **Shared closeout files (`CHANGELOG.md` and `docs/technical/roadmap.md`):** Because every track touches these files, they are the most likely source of merge conflicts. The procedure above already handles this — the `git merge v87` before merge-back ensures you resolve any conflicting entries on your track branch rather than on `v87`. Do not skip or reorder that step. When resolving, keep both tracks' entries (don't overwrite another track's completed work).
>
> **Conditionally shared — `docs/technical/decisions.md`:** Added to the shared-closeout set when repository-wide policy or acceptance evidence changes (e.g., recording that a previously open ticket is closed). The existing `git merge v87` synchronization and preserve-both-sides resolution procedure above covers this surface — decisions.md entries must be reconciled with the same discipline as CHANGELOG.md and roadmap.md entries, not overwritten across tracks.

---

## Open work

> Completed work lives in [CHANGELOG.md](../../CHANGELOG.md). This section holds only active work.

The green-gate join (SA96-GATE) is green with empty quarantine. The installed-context resolver crash on the release path is closed by **SA113 ✓** (bundled-manifest fallback, both call sites) and **SA111a ✓** (installed-wheel `plan` coverage, all 12 modules); both are recorded in [CHANGELOG.md](../../CHANGELOG.md) and are referenced below as `SA113 ✓` / `SA111a ✓`. The **Track 3 (release path)** remains blocked on SA112 after a diagnostic/prototype attempt found additional correctness and planning gaps; no SA112 implementation from that attempt landed (see the blocked checkpoint below). **Track 1 is at a blocked checkpoint** — SA114 and SA116 both remain open (blocking finding **SA114-ORDER-001**); see the blocked checkpoint below and CHANGELOG. Track 2's feature chain is complete; one independent test-infra ticket (**SA115**, e2e parallelization) is parked there to use the idle track.

1. **SA112** (installed-wheel full-lifecycle e2e `plan → apply → up`, Track 3) — heavy e2e lane covering `apply`'s own resolver call site and the Docker path from a real install. Blocked checkpoint recorded below; no implementation from the attempt landed. Deps: SA110 ✓ + SA111a ✓ + SA113 ✓.
2. **SA96-PUBLISH** (staged PyPI publish, Track 3) — **HUMAN-ONLY**. Baseline prerequisites met (SA96-GATE ✓ + SA109 ✓ + SA110 ✓ + SA111a ✓ + SA113 ✓); awaits a human maintainer to execute the irreversible publish. Hold: must not publish while SA112 remains open.
3. **SA114** (v87 gate re-verification & fix sweep, Track 1, `deps: none`) — **open (blocked on SA114-ORDER-001).** Source implementation complete: `contracts/resolvers.py` comment/docstring-only compaction (1761→1749 lines); baseline unchanged. Focused 181 resolver tests, lint, typecheck, and quality green. Independent source review `STATUS: ok` with no findings; `SA114-QUALITY-001` resolved. The exact ordered gate chain (`make check && make quality && make ci && make ci-e2e`) lacks a final `make ci-e2e` exit status — see the blocked checkpoint below. SA114 remains unchecked.
4. **SA115** (E2E in-lane parallelization, Track 2, `deps: none` · **merge after SA112**) — add `pytest-xdist` in-lane fan-out to the e2e suite (`scripts/test_e2e.sh`) so the ~40–60 serial per-lane tests run across N workers, shortening the longest quality check (`make ci-e2e`). Shares the `scripts/test_e2e.sh` / `.github/workflows/e2e.yml` surface with SA112 and the PG/Docker infra with SA114 — bounds below.
5. **SA116** (policy-compliant `resolvers.py` line reduction, Track 1, `deps: none`) — **implementation done; ticket remains open (blocked on SA114-ORDER-001).** `contracts/resolvers.py` compacted 1761→1749 lines via comment/docstring-only compaction; `scripts/quality_baseline.json` unchanged. `make quality` exit 0. Independent source review `STATUS: ok` with no findings, resolved `SA114-QUALITY-001`. SA116 closure depends on SA114's completion gate (ORDER-001). SA116 remains unchecked.

Arch **Finding 10** (`frontend-source-generation-specialized`) is **closed** by the SA104→SA108 chain (see arch-audit reconciliation log, 2026-07-21). Arch **Finding 7** (generated-file-ownership taxonomy derivation) stays unscheduled — the Finding 10 chain shrank its surface; sequence any tuple-derivation work after it. Arch Findings **2/4** remain **not ticketed**, deferred with the (unscheduled) teams module.

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a clean rerun at the prior synced code baseline (post-SA92 squash), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). The four-command join covers everything end to end — unit **and** integration **and** e2e. `make check` is the **fast** repo gate — `lint` + `typecheck` + `test-unit` (unit only) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (see the `check` target in `Makefile`; `make check QUIET=1` is the quiet LLM/agent variant). **Integration coverage lives in `make ci`** (unit + integration when PostgreSQL is available), and e2e in `make ci-e2e` (`.github/workflows/e2e.yml`). So `make check` alone does not prove integration — the `ci`/`ci-e2e` legs of the join do.

The join runs entirely **inside the monorepo** and does **not** exercise the pip-installed wheel — that gap was closed by SA109/SA110 (both complete; see [CHANGELOG.md](../../CHANGELOG.md)). `make smoke-install` builds wheels from per-run staged copies (no source mutation), installs into a throwaway venv outside the source tree, and runs every non-mutating CLI command from a sanitized external workdir under the full `>=3.13,<3.15` Python constraint.

### SA96-PUBLISH — Staged release ladder

- [ ] **SA96-PUBLISH — Staged release ladder.** `Tier 1 · v87 · deps: SA96-GATE ✓ + SA109 ✓ + SA110 ✓ + SA111a ✓ + SA113 ✓` · **HUMAN-ONLY — do not delegate to an assistant**
  Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full` for test→verify→prod in one shot). **PyPI publish is irreversible/outward-facing — a human maintainer must confirm version + green-gate status before `publish-prod`. This step is explicitly excluded from any SA93/SA96-GATE assistant handoff.**

  *(Acceptance:* all 12 modules green in isolation; SA96-GATE four-command run exits 0 with empty quarantine; SA109 ✓ and SA110 ✓ closed (installed wheel runs non-mutating commands clean); SA113 ✓ closed (resolver fix landed); SA111a ✓ and SA112 closed (optional SA111b is non-gating); release published and verified on PyPI.*)*
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*

### Track 1 — Tenant-context surface

**Prior Track 1 work COMPLETE.** All prior Track 1 work (SA92/SA84/SA86/SA96-T1, Finding 8, SA97/SA99, SA102/SA103, and the full TP test-parallelization suite SA91/TP1/TP2/TP2b/TP3a/TP3b/TP4) is closed. See [CHANGELOG.md](../../CHANGELOG.md). One new verification ticket (SA114) is parked here to use the idle track in parallel with the Track 3 release chain.

#### SA114 — v87 gate re-verification & fix sweep

SA96-GATE proved the four-command join green **at the post-SA92 synced baseline**. Commits have landed since (SA108/roadmap docs, the `d5d25c08` generator `poetry lock` timeout fix, merges), so the gates have not been re-run against current `v87` HEAD. This ticket re-verifies them and fixes any drift. It was introduced while SA113 was still active (alongside the installed-context resolver fix) and now runs alongside the remaining SA112 work on Track 3.

- [ ] **SA114 — Re-run the make gates on current `v87` HEAD and fix drift.** `Tier 2 · Track 1 · deps: none`
  Run, in order, `make check` → `make quality` → `make ci` → `make ci-e2e` against current `v87` HEAD; fix any lint/typecheck/unit/complexity/coverage/integration/e2e drift so each exits 0 with `QUARANTINE_TICKETS` empty. Record the evidence (exit codes, coverage mean, pass/fail counts) in the completed-work block on merge.
  - **Concurrency bound (infra):** `make check`/`make quality` are static/light and run fully parallel with Track 3. `make ci`/`make ci-e2e` need a live PostgreSQL server + Docker daemon + ports and **must be serialized** against any Track 3 SA112 e2e run — the `QS_CI_PARALLEL`/`QS_E2E_PARALLEL`/per-lane-scope knobs namespace lanes *within* one invocation, not across worktrees hitting the same server. Coordinate the heavy legs so only one track exercises PG/Docker at a time.
  - **Fix-scope bound (merge hazard):** if a failure lands in SA113's surface — `quickscale_core/src/quickscale_core/manifest/implications.py`, `scripts/smoke_install.sh`, or the installed-wheel e2e lane — **do not fix it here**; route it to Track 3 follow-up ownership (SA112 or subsequent work). SA113 completed its resolver fix and is no longer an active handoff destination. This ticket owns only gate drift *outside* the installed-context resolver work. Any fix it does make outside that surface is disjoint, so the only shared-closeout overlap with Track 3 is `CHANGELOG.md`/`roadmap.md`, covered by the Merge procedure.
  - Verify: `make check`, `make quality`, `make ci`, `make ci-e2e` each exit 0 on current `v87` HEAD with empty quarantine; any fixes are behavior-preserving and touch no installed-context resolver file.
  - **Blocked checkpoint (2026-07-23; implementation and partial final-sync validation recorded — task remains open):**
    - **Done (prior + this continuation):** Started from `v87` at `556f7510`; fixed gate drift outside the installed-context resolver surface; added focused migration-seam coverage; and obtained clean ordered evidence on the pre-final-sync Track 1 baseline. The continuation synchronized Track 1 to `v87` at `c09e2093` before editing and applied all three requested review changes: `SA114-REV-001` enforcement (`validateQuickScaleSeam.ts` added to `MODE_REQUIRED_SPECS['in-place']['donor']` with preflight regression coverage and the CLI migration fixture updated for caller parity); `SA114-REV-002` implementation (modules-only `make check` guards `test-unit` behind a non-empty sections check); and `SA114-REV-004` strengthened evidence (exact `projectName` binding proof in the Django template, recursive `frontend/src/` project-name leakage scan, and stale-placeholder scan). No installed-context resolver file changed. On that synced baseline, `make check` exited 0 (core 2526 passed / 1 skipped; CLI 1998 passed), `make ci` exited 0 (11/11 stages; 92.89% equal-weight coverage mean; all 90 measured files at least 80%; all 12 integration modules green at 94.41% mean), and `make ci-e2e` exited 0 (12/12 stages; Core E2E 34 passed / 1 expected offline skip; CLI E2E 29 passed). Quarantine remained empty.
    - **Prior review blockers (resolved):** Independent checkpoint review resolved `SA114-REV-001` (fail-closed runtime-seam donor preflight), `SA114-REV-002` (normal/quiet section dispatch and Ruff/MyPy/pytest caller parity), `SA114-REV-004` (exact runtime `projectName` binding plus recursive frontend-source leakage checks), and `SA114-REV-005` (status surface synchronization). Focused closeout evidence for REV-002 passed 65 policy/dispatch tests and a real modules-only quiet check.
    - **Resolved blockers:**
      - `SA114-QUALITY-001` — pre-existing `contracts/resolvers.py` line growth (1761 lines against shrink-only 1749-line maximum). Resolved by SA116's policy-compliant comment/docstring-only compaction (1761→1749 lines; `scripts/quality_baseline.json` unchanged; `make quality` exit 0). Independent source review `STATUS: ok` with no findings.
    - **Blocking (still open):**
      - **SA114-ORDER-001** (medium, blocking for completion, completeness) — the exact ordered gate chain (`make check && make quality && make ci && make ci-e2e`) lacks a final `make ci-e2e` exit status on the literal ordered run. First QG on unchanged source ran all four gates and passed (all exit 0, quarantine empty) but NOT in the literal required order. Second/final QG ran exact prefix `make check` → `make quality` → `make ci` successfully with matching evidence; `make ci-e2e` exceeded the 30-minute agent runtime window after pre-stages and returned no final exit code. Tree unchanged. Prior identical-tree E2E 30/30 (identical-tree provenance — first QG after SA116 source compaction) remains supporting evidence but does not resolve the literal ordered-chain requirement.
    - **Mitigation available (landed on `v87` 2026-07-23; see CHANGELOG):** `scripts/test_e2e.sh` now carries a low-memory preflight guard (serial-lane fallback under memory pressure, guarding against `systemd-oomd` reaping the run) and a `QS_E2E_HEARTBEAT_INTERVAL` progress heartbeat. These directly target the ORDER-001 failure mode (a long `make ci-e2e` hanging/returning no exit code) and should be in effect on any Track 1 worktree synced to latest `v87` before the continuation run below.
    - **Required clean continuation (from a clean Track 1 worktree synced to latest v87):**
      1. Rerun exact `make check && make quality && make ci && make ci-e2e` with a runtime window sufficient for E2E.
      2. Require all exit 0 and quarantine empty.
      3. Obtain independent full-scope change review `STATUS: ok`.
      4. Only then mark SA114/SA116 `[x]` and add completion CHANGELOG language.
    - **User direction:** checkpoint commit/merge authorized despite incomplete completion criterion. This is authorization to merge an open checkpoint, not waiver of ORDER-001. The historical `SA114-DEC-001` decision (assigning resolvers.py reduction to SA116) is recorded and SA116's compaction is complete; what remains is the gate-order completion requirement.
  *(why →* the green-gate join was proven at the synced baseline, not at current HEAD; drift since then is unverified, and re-proving it is independent of the installed-context release chain — a genuine use of the idle track*)*

#### SA116 — Policy-compliant `resolvers.py` line reduction (unblocks SA114 four-gate reclose)

Cross-track growth left `quickscale_core/src/quickscale_core/contracts/resolvers.py` at 1761 lines against its checked-in 1749-line maximum in `scripts/quality_baseline.json`, so `make quality` exits 2 (this is `SA114-QUALITY-001`). Under the shrink-only quality-maxima policy (decisions.md §5) the only compliant fix is a behavior-preserving reduction; raising the baseline is not authorized. Assigned here by `SA114-DEC-001` (2026-07-23).

- [ ] **SA116 — Reduce `contracts/resolvers.py` to ≤1749 lines, behavior-preserving.** `Tier 1 · Track 1 · deps: none` — **implementation done; ticket remains open (blocked on SA114-ORDER-001).**
  `contracts/resolvers.py` compacted 1761→1749 lines via comment/docstring-only compaction, preserving public API, resolver behavior, and test outcomes. `scripts/quality_baseline.json` unchanged at `max_lines` 1749. `make quality` exit 0 with 0 warning/critical regressions. Independent source review `STATUS: ok` with no findings, resolved `SA114-QUALITY-001`. SA116 closure is dependent on SA114's completion gate (ORDER-001 — see SA114 blocked checkpoint for required clean continuation). SA116 remains unchecked.
  *(why →* shrink-only policy-compliant reduction; dedicated idle-Track-1 ticket resolved `SA114-QUALITY-001` and kept Track 3 on the critical path*)*

### Track 2 — Module contracts & settings — frontend-theme de-specialization (arch Finding 10)

**Feature chain COMPLETE.** The frontend-theme de-specialization chain (SA104 → SA105 → SA106 → SA107 → SA108) is fully closed, retiring arch-audit Finding 10 (`frontend-source-generation-specialized`). `frontend/src` is now project-agnostic and byte-identical across projects on the same theme version, with all project/module facts flowing through the `window.__QUICKSCALE__` runtime seam; `beta-site-migration.md` has been rewritten to the copy-not-merge reality. See [CHANGELOG.md](../../CHANGELOG.md) for details. Off the SA96 release critical path; no gate or coverage threshold regressed. One independent test-infra ticket (**SA115**) is parked on this otherwise-idle track.

#### SA115 — E2E in-lane parallelization (pytest-xdist)

`make ci-e2e` is the longest quality check in the SDLC. It runs the full 12-stage local CI (`scripts/check_ci_locally.sh --e2e`), whose final stage is `scripts/test_e2e.sh`. That script already runs the **Core** and **CLI** e2e lanes concurrently (`QS_E2E_PARALLEL=1`), each in its own Docker Compose project / container prefix / dynamic host port — **but within each lane the ~40–60 `@pytest.mark.e2e` tests run serially** (the pytest invocation has no `-n`). Because each test generates a full Django project, runs `poetry install`, builds, and drives Playwright/Chromium, that serial in-lane run is the dominant cost, and the total is gated by whichever single lane is slowest. Adding in-lane `pytest-xdist` fan-out is the highest-leverage remaining speedup.

Most groundwork already exists and is xdist-aware: `pytest-xdist ^3.8.0` is already a dependency (used for unit tests); `quickscale_core/tests/conftest.py` already isolates per worker via `_isolate_poetry_cache_per_worker()` (per-`PYTEST_XDIST_WORKER` Poetry cache) and the `per_test_db`/`unique_db_name` fixtures (unique DB per test, collision-free across workers); project generation uses per-test `tmp_path`. The **only** real blocker is that the `pytest-docker` **session-scoped** fixtures (`docker_compose_file`, `postgres_service`, conftest lines 122–157) are not xdist-safe — under `-n` each worker is its own session and would bring up the *same* Compose project (same default name, same named volume `postgres_test_data`), colliding.

**Design (ratified with maintainer):** *container-per-worker* Postgres; *scope limited to the E2E stage* (no lane rebalancing).

- [ ] **SA115 — Add in-lane pytest-xdist fan-out to the e2e suite.** `Tier 2 · Track 2 · deps: none · merge after SA112`
  1. **xdist-safe pytest-docker fixtures (container per worker).** In `quickscale_core/tests/conftest.py`, add a session-scoped override of pytest-docker's `docker_compose_project_name` that derives a **unique per-worker** Compose project name from the lane's `QS_E2E_COMPOSE_PROJECT_NAME` (exported per lane at `scripts/test_e2e.sh:225`) plus `PYTEST_XDIST_WORKER` (falls back to a single name when not under xdist). Keep the lane prefix intact so the shell's `cleanup_scoped_containers` (test_e2e.sh:163–176) still matches by `name=<prefix>` substring. Docker Compose auto-prefixes the named volume with the project name, so `docker-compose.test.yml` needs **no change** (port already dynamic). Confirm whether `quickscale_cli/tests/` defines its own docker fixtures and mirror the override there.
  2. **Configurable worker count.** In `scripts/test_e2e.sh`, extend the `pytest_cmd` builder (~line 265) to append `-n <workers> --dist loadscope`, driven by a new `QS_E2E_XDIST_WORKERS` env var. Default to a small `nproc`/RAM-derived cap (mirror the Makefile's existing `PYTEST_XDIST_WORKERS` heuristic — **not** `auto`, since each worker now runs a full Postgres container + Chromium and is memory-heavy). `QS_E2E_XDIST_WORKERS=1` (or `0`) must degrade to today's serial no-`-n` path (debugging escape hatch, mirroring `QS_E2E_PARALLEL=0`). Document the var in the script `--help` and `# Environment:` header. Surface the chosen worker count in the lane banner (near test_e2e.sh:251–253). Keep the two lanes concurrent → total load is `2 lanes × N workers`; pick the default with combined RAM/container budget in mind.
  - **Concurrency bound (infra):** shares the live PostgreSQL/Docker + ports with SA114's `ci-e2e` leg and SA112's installed-wheel e2e — **serialize** heavy runs across worktrees (per-lane knobs namespace lanes *within* one invocation, not across worktrees).
  - **Merge-order bound (hazard):** SA112 (Track 3) also edits `scripts/test_e2e.sh` / `.github/workflows/e2e.yml` (adds the installed-wheel lifecycle lane). **Land SA115 after SA112** and rebase onto its lane-wiring changes to avoid a conflict on the shared runner surface; the only other shared-closeout overlap is `CHANGELOG.md`/`roadmap.md`, covered by the Merge procedure.
  - Verify: baseline `time QS_E2E_XDIST_WORKERS=1 ./scripts/test_e2e.sh` vs. parallel default is faster with all e2e tests green; `docker ps` mid-run shows one Postgres container per active worker with distinct project names/ports; back-to-back runs leave no leftover containers/volumes (`docker volume ls | grep postgres_test_data`); `QS_E2E_XDIST_WORKERS=1` reproduces the old serial path; `make ci-e2e` stays green; `.github/workflows/e2e.yml` passes on the CI runner (tune default worker count to runner cores/RAM).
  *(why →* `ci-e2e` is the longest gate in the SDLC; lanes are already concurrent but each runs serially inside, and the xdist groundwork (per-worker cache + per-test DB) already exists — the sole blocker is xdist-safe pytest-docker fixtures*)*

  **Blocked checkpoint (2026-07-23) — roadmap record only; SA115 remains open:**

  **Done**
  - In `wt-track2` after clean sync to `v87` at `c09e2093`:
    - **Phase 1** — worker-unique `pytest-docker` `docker_compose_project_name` fixture in `quickscale_core/tests/conftest.py`, with `QS_E2E_COMPOSE_PROJECT_NAME` + `PYTEST_XDIST_WORKER` derivation. The fixture reuses the existing `postgres_service` unchanged — it only makes the Compose project name worker-unique so that per-worker `postgres_service` instances (brought up by the unchanged `pytest-docker` session-scoped fixture) do not collide under xdist. Focused tests in `quickscale_core/tests/test_e2e_xdist_fixtures.py` check the derived name and per-worker isolation; these are pure deterministic naming/fixture tests and do **not** exercise containers or back-to-back container lifecycle.
    - **Phase 2** — `QS_E2E_XDIST_WORKERS` env var in `scripts/test_e2e.sh`: defaults to a RAM-derived cap (mirroring the Makefile `PYTEST_XDIST_WORKERS` heuristic); `QS_E2E_XDIST_WORKERS=1` or `0` degrades to the serial no-`-n` path; `>=2` appends `-n <N> --dist loadscope`. Documented in `--help` and the `# Environment:` header. Lane banner prints the chosen worker count.
    - **Harness tests** — Python-based in `scripts/test_e2e_parallel.py`: validate the `>=2` vs. `0`/`1`/unset paths and the `--dist loadscope` / `--help` / banner integration.
  - **Evidence (all pass):** 16 fixture tests; 13 runner-harness tests; Bash syntax check (`bash -n`); focused `poetry run ruff check`; `poetry run ruff format --check`.
  - **These executable changes are parked/uncommitted on `wt-track2` and are NOT part of this status-only checkpoint.** This checkpoint records only the factual state of the work — SA115 remains unfinished. The four uncommitted files are: `quickscale_core/tests/conftest.py`, `quickscale_core/tests/test_e2e_xdist_fixtures.py`, `scripts/test_e2e.sh`, `scripts/test_e2e_parallel.py`.

  **Pending / blocking**
  - **SA112 is still open.** SA115 cannot merge until SA112 lands — both edit `scripts/test_e2e.sh` and the shared CI surface, and the merge-order bound (`merge after SA112`) is documented in the SA115 task block above. After SA112 closes:
    1. Merge `v87` into `wt-track2`.
    2. Refresh/reconcile shared runner/workflow edges (`scripts/test_e2e.sh`, `.github/workflows/e2e.yml`). **Note:** `scripts/test_e2e.sh` moved on `v87` on 2026-07-23 (memory preflight guard + `QS_E2E_HEARTBEAT_INTERVAL` heartbeat; see CHANGELOG) — the parked SA115 edits to that file must be reconciled against those changes, not just SA112's lane wiring.
    3. Rerun focused checks: fixture tests, harness tests, Bash syntax, Ruff.
    4. Run serial baseline (`QS_E2E_XDIST_WORKERS=1`) vs. default parallel E2E, proving distinct container names/ports per worker and clean teardown.
    5. Run `make ci-e2e`.
    6. Run local `./scripts/check_ci_locally.sh --e2e`, and separately run the hosted CI runner (`.github/workflows/e2e.yml`) if available, listing results for each.
    7. Obtain independent change review (`STATUS: ok`).
    8. Mark SA115 `[x]` and add completion entry to CHANGELOG.md.
  - **No completion language or CHANGELOG entry until validation and independent review are green.**

  **Decisions needed:** None. Continuation is mechanically gated by SA112 — the next action is always "wait for SA112 to land, then follow the post-SA112 sequence above."

### Track 3 — Core/CLI plumbing — release path

> The installed-context resolver crash (`ImproperlyConfigured: Modules base path not found`) is closed: **SA113 ✓** added the bundled-manifest fallback to `resolve_module_implications` for both the `plan` and `apply` call sites (with a fail-hard inventory boundary), and **SA111a ✓** proved the fixed `plan` path in `smoke-install` (all 12 modules from an installed wheel). Both are recorded in [CHANGELOG.md](../../CHANGELOG.md). `apply`'s own installed-context lifecycle coverage remains open as **SA112**. (The optional in-monorepo fallback regression test **SA111b ✓** is complete and recorded in [CHANGELOG.md](../../CHANGELOG.md).)

#### SA112 — Installed-wheel full-lifecycle e2e (`plan → apply → up`)

**Pre-SA113 gap analysis — the resolver crash that blocked installed-context `plan`/`apply` is now resolved by SA113.**
Before the fix, a broken `plan`/`apply` could reach a user because **no gate ever runs
`apply`/`up` from an installed wheel**. `test_e2e_development_workflow.py` already
drives `plan → apply → up → ps/manage/logs → down` with real Docker + PostgreSQL —
but from **monorepo source**, so it never exercises bundled-manifest discovery and
never hits the crash. The missing axis is *installed artifact*, not the lifecycle
itself. This does **not** belong in `smoke-install`: `apply` runs `poetry lock` +
`poetry install` (minutes) and `manage migrate` needs a live PostgreSQL, and `up`
needs the Docker daemon + image builds — all antithetical to the fast, service-free
smoke gate. It belongs in a heavy lane gated like `ci-e2e`.

- [ ] **SA112 — Installed-wheel lifecycle e2e lane.** `Tier 2 · Track 3 · deps: SA110 ✓ · SA111a ✓ · SA113 ✓`
  Add an installed-wheel e2e that builds+installs the wheels (reuse the
  `smoke_install.sh` staging/build/venv machinery), then from an external workdir
  runs `plan` (all 12 modules) → `apply` → `up` → `ps`/`manage migrate` → `down`
  against real Docker + PostgreSQL, mirroring `quickscale_cli/tests/test_e2e_development_workflow.py`
  but using the installed `quickscale` entrypoint instead of monorepo source. Wire it
  into the e2e lane (`scripts/test_e2e.sh` / `.github/workflows/e2e.yml`), not
  `make check`/`smoke-install`. Confirms `apply`'s own resolver call site
  (`apply_command.py:973`) and the Docker path work from a real install.
  - Verify: once implemented, this lane confirms the full installed-wheel `plan → apply → up` lifecycle works end to end (SA113's resolver fix already covers both call sites). Full `up` lifecycle boots and serves.
  *(why →* `apply`/`up` have zero installed-artifact coverage; the existing lifecycle e2e runs only from source, which cannot reproduce install-context discovery bugs*)*

  **Blocked checkpoint (2026-07-23; plan-review cap continuation) — roadmap record only; SA112 remains open:**

  **Done**
  - Began from a clean Track 3 worktree synced to `v87` at `ae398a22` and confirmed the Poetry Python 3.13 environment and Docker daemon were available.
  - A disposable prototype proved installed `plan` with all 12 modules and reached installed `apply` through all 12 module embeds. The apply attempt then reported `NameError: name 'QUICKSCALE_BILLING_ENABLED' is not defined` during managed-wiring regeneration. `up`, `ps`, `manage migrate`, `down`, and the integrated `make test-e2e` gate were not reached.
  - Prototype-only diagnostics passed 81 resolver tests, 9 shell/e2e harness tests, shell syntax checks, and workflow YAML parsing. Those results describe the discarded prototype, not the current branch.
  - Static discovery found no bare-name evaluation of `QUICKSCALE_BILLING_ENABLED` in the traced managed-wiring path and no billing source/bundled/package version skew. The apply wrapper reduces the exception to `str(exc)`, so the exact raising frame still requires a runtime traceback.
  - Independent change review rejected the executable prototype for merge. All executable, test, workflow, and CHANGELOG changes from the attempt were restored to `v87`; this checkpoint lands no SA112 implementation.
  - Big-tier remediation planning resolved plan findings `SA112-PR-001`, `SA112-PR-003`, `SA112-PR-004`, and `SA112-PR-005`, including safe dirty-state reconstruction, phase ownership, finding closure criteria, and Track-3-only merge handling.
  - This continuation began from clean `wt-track3` at `9dc09f02`, merged `v87` to `243c697d` before touching files, and confirmed the existing Poetry Python 3.13.14 environment, Docker daemon, and `make ci-e2e` entrypoint. All task prerequisites remain complete: SA110 ✓ + SA111a ✓ + SA113 ✓.
  - Discovery produced the validated `sa112-topology-v1` snapshot and confirmed that no prior SA112 plan artifact or implementation survived in the tracked tree. The first authorized plan correction reduced the review ledger to four blockers. Two explicit cap-continuation decisions then narrowed the plan further; the latest independent plan review resolved `SA112-CONT-001` at plan level (durable traceback evidence and Phase 1→2 handoff) and `SA112-CR-008` at plan level (pre-document gate, clean Track 3 sync, post-sync smoke/full validation, and final review ordering). Prior review also resolved the plan requirements for `SA112-CR-001`, `SA112-CR-002`, `SA112-CR-003`, `SA112-CR-004`, `SA112-CR-006`, and `SA112-CR-007` without authorizing implementation.
  - No diagnostic instrumentation, product code, test runner, workflow, CHANGELOG, or completion-checkbox change was made. No SA112 test or heavy Docker/PostgreSQL lane ran in this continuation.

  **Pending / blocking**
  - `SA112-PR-002` (**high, blocking**) — the command registry is still not literally executable. The final review found remaining ellipses/shorthand plus unspecified helper outputs, stdin byte sequences, full argv arrays, focused validation commands, and exact documentation assertions. Existing smoke stdin cannot be reused without proving parity because adding `--package` changes the planner prompt sequence. Diagnostics remain forbidden until an independent plan review returns `STATUS: ok`.
  - `SA112-CR-005` (**medium, blocking**) — the exact ordered workflow trigger registry still omits `scripts/_python_requirement.sh`, an installed-artifact helper dependency, and must expand every path/glob into literal GitHub Actions strings covered by the deterministic BaseLoader regression.
  - Runtime work remains pending after the plan gate: capture the full installed-apply traceback, select the root fix only from the actual raising frame, implement the maintained installed-wheel lifecycle lane, run focused and full validation, obtain independent change review, and only then mark SA112 complete and update CHANGELOG.

  **Decisions needed**
  - The maintainer previously selected **stop and record/merge this blocked checkpoint** after the second capped review remained partial. **Authorization granted (2026-07-23):** the maintainer has authorized one more blocking-only `Adaptive-plan` → plan-review cycle, scoped strictly to closing `SA112-PR-002` (high — literally-executable command registry: exact stdin byte sequences, full argv arrays, helper outputs, focused validation commands, documentation assertions; prove `--package` planner-prompt parity rather than reusing smoke stdin) and `SA112-CR-005` (medium — ordered workflow-trigger registry expanded to literal GitHub Actions strings, including the `scripts/_python_requirement.sh` installed-artifact helper dependency, under the deterministic BaseLoader regression). Product implementation and diagnostic instrumentation remain unauthorized until that review returns `STATUS: ok`. If this third cycle again returns partial, escalate to a maintainer-supplied literal registry rather than a fourth cycle.
  - After the runtime traceback is eventually captured, surface a decision only if it reveals multiple contract-valid fixes with materially different compatibility consequences; otherwise use the traceback-selected technical fix.

### Track 3 (prior) — Core/CLI plumbing — release path

**Prior Track 3 work COMPLETE.** The foundational Track 3 work is closed (arch-audit Finding 1 via SA89a+SA89b; all four GATEs; SA91 parallel worker pool; SA93 e2e in green-gate; SA100 theme preflight; SA101 quality remediation; SA96-GATE join; SA109 installed-wheel discovery fix; SA110 installed-artifact smoke gate; SA113 resolver fix; SA111a installed-context plan coverage; SA111b fast in-monorepo fallback regression test). See [CHANGELOG.md](../../CHANGELOG.md). The **open** Track 3 engineering item is SA112 (installed-wheel lifecycle coverage, above); **SA96-PUBLISH** remains human-only.

The AF7 installed-wheel discovery decision is recorded in [`decisions.md`](../technical/decisions.md#af7-installed-wheel-module-discovery): discovery falls back to bundled manifest snapshots (`quickscale_core/data/manifests/*/module.yml`) when the source workspace is absent, while source-required operations (`get_modules_base_path`, `discover_shipped_module_paths`, `load_module_manifest`, `refresh_managed_adapters`) remain fail-hard.

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

Only open work is shown; all prior tickets are complete (see [CHANGELOG.md](../../CHANGELOG.md)).

```
Track 1 (open — blocked)  Track 2 (chain done → SA115)    Track 3 → release (critical path)
──────────────────────   ────────────────────────────     ─────────────────────────────────
SA114 (gate re-verify    SA104 ✓ → SA105 ✓ → SA106 ✓       SA96-GATE ✓  SA109 ✓  SA110 ✓
  & fix; deps: none)      → SA107 ✓ → SA108 ✓                │
SA116 (resolvers.py      SA115 (e2e xdist; deps: none,       │
  ≤1749; deps: none)      merge after SA112)                │
                          (arch Finding 10 chain closed)     SA113 ✓ ── bundled-manifest fallback
                                                                      │  both call sites (plan+apply)
                                                             SA111a ✓ (smoke probe) · SA111b ✓ (unit test)
                                                             │
                                                           SA112 ── installed-wheel plan→apply→up e2e
                                                             │
                                                             ▼
                                                         SA96-PUBLISH ── build → publish
                                                           deps: SA96-GATE ✓ + SA109 ✓ + SA110 ✓ + SA111a ✓ + SA113 ✓
                                                           (human-only; hold until SA112 closes)
```

**Parallelism.** The remaining gating Track 3 work forms one release unit: SA112 → SA96-PUBLISH; SA111a and SA111b are complete (SA111b was optional and non-gating). **SA113** (`implications.py`) has landed (bundled-manifest fallback with fail-hard inventory validation). **Track 1 is at a blocked checkpoint** — SA114 and SA116 both remain open on **SA114-ORDER-001** (the exact ordered gate chain lacks a final `make ci-e2e` exit status). SA116's policy-compliant `contracts/resolvers.py` compaction (1761→1749 lines) resolved `SA114-QUALITY-001`; independent source review `STATUS: ok` with no findings. The completion gate is not satisfied. See the SA114 blocked checkpoint below for the full done/pending ledger. SA96-PUBLISH (human-only) shares no files with the assistant-executable tickets.

### Track readiness (2026-07-23)

- **Track 1 — open (blocked checkpoint).** SA114 and SA116 both remain unchecked. **SA114-ORDER-001** (medium, blocking for completion) — the exact ordered gate chain (`make check && make quality && make ci && make ci-e2e`) lacks a final `make ci-e2e` exit status on the literal ordered run. The prior completed work and resolved blockers are recorded in the SA114 blocked checkpoint below. SA116's policy-compliant `contracts/resolvers.py` compaction (1761→1749 lines, comment/docstring-only) resolved `SA114-QUALITY-001`; independent source review `STATUS: ok` with no findings. No unresolved blocker remains on the compaction work itself, but the completion gate (ORDER-001) is not satisfied. The E2E-window mitigation landed on `v87` on 2026-07-23 (memory preflight guard + heartbeat in `scripts/test_e2e.sh`; see CHANGELOG) and is available for the clean-continuation run — ORDER-001 stays open until that literal ordered chain actually completes with all exit 0.
- **Track 2 — feature chain COMPLETE; one parked infra ticket (SA115), off the critical path.** Chain stages SA104/SA105/SA106/SA107/SA108 complete. Track 2 frontend de-specialization chain (arch Finding 10) is fully closed. SA115 (e2e in-lane pytest-xdist parallelization, `deps: none`) is parked here to use the idle track; it shares the `scripts/test_e2e.sh` runner surface with SA112 (**merge after SA112**) and the PG/Docker infra with SA114 (serialize heavy runs). SA115 implementation reached a parked executable checkpoint on `wt-track2` (16 fixture tests + 13 harness tests green, Bash syntax and scoped Ruff clean); the four changed files remain uncommitted — this is a merge-order-blocked checkpoint, not clean-to-start. Merge order: SA112 must land first, then the post-SA112 reconciliation and full validation sequence documented in the SA115 checkpoint below. No completion language or CHANGELOG entry until then. Legacy compatibility finding documented: SA105 dormant-file guarantee applies only to fresh current-theme recipients; legacy pre-SA105 recipients have no retroactive dormant guarantee for any module surface — running `quickscale apply` does not guarantee or backfill blog/crm/listings; the shipped continuation adopts only missing forms/social surfaces (no blog/crm/listings backfill). No blocker.
- **Track 3 — open engineering work; SA112 plan review stopped at a mergeable blocked checkpoint (2026-07-23).** The green-gate join, SA109, SA110, SA113, SA111a, and SA111b are closed. SA113 resolved the installed-context implication resolver crash, and SA111a proves installed-wheel `plan` coverage with all 12 modules. SA111b (optional, now complete) adds a fast in-monorepo fallback regression test. **SA112** remains pre-diagnostic: capped plan corrections reduced the open review ledger to `SA112-PR-002` (high) and `SA112-CR-005` (medium), but independent review is still `STATUS: partial`. **The maintainer authorized one more blocking-only plan/review cycle (2026-07-23)** scoped to closing `SA112-PR-002` and `SA112-CR-005` (see the SA112 blocked checkpoint's Decisions block); no product implementation or diagnostic instrumentation is authorized until that review returns `STATUS: ok`, and a third partial escalates to a maintainer-supplied literal registry. SA96-PUBLISH (human-only) holds until SA112 closes. Non-gating advisories remain deferred (SA91 CR-SA91-REV-006 low; SA89B-CR-004; SA93-REV-005; SA93-ADV-001..004; SA104-ADV-001; SA105-ADV-001; CR-SA106-002; SA110-ADV-001).

**Track 3 decision — RESOLVED (2026-07-21): Option A, fix-first.** The resolver fix was ticketed as **SA113** on Track 3 and landed before its coverage; SA111a then verified the installed `plan` path, making SA112 dependency-unblocked at that point. SA111b (optional, now complete) adds the fast in-monorepo companion test. SA112 is now checkpoint-blocked on the two remaining plan findings `SA112-PR-002` and `SA112-CR-005`; all runtime diagnosis, implementation, and validation remain pending behind a plan-review `STATUS: ok`, as recorded above. The resolver work stayed on Track 3 (not an idle Track 1/2) because it was the *head* of the dependency chain — nothing ran in parallel with it, and splitting the fix from its coverage (same resolver module, `scripts/`, e2e lane) would only have created a cross-track merge hazard. The fix follows the SA109/AF7 bundled-fallback precedent in decisions.md.

**Net.** Track 1 is **at a blocked checkpoint** — SA114 and SA116 both remain open (blocking finding **SA114-ORDER-001**: the exact ordered gate chain lacks a final `make ci-e2e` exit status). SA116's policy-compliant `contracts/resolvers.py` compaction (1761→1749 lines, comment/docstring-only) is implemented and resolved `SA114-QUALITY-001`; independent source review `STATUS: ok` with no findings. The compaction evidence and the prior checkpoint's gate-drift fixes are recorded in the SA114 blocked checkpoint below. ORDER-001 requires a clean continuation (see continuation steps in the SA114 blocked checkpoint). Track 2's feature chain is complete, with one independent off-path infra ticket at a merge-order-blocked executable checkpoint (SA115, e2e in-lane parallelization — merge after SA112, PG/Docker serialized with SA114); its four executable files remain uncommitted on `wt-track2` pending SA112 and the documented reconciliation/validation sequence. Track 3 is **not** done: SA113, SA111a, and SA111b are closed, and the remaining critical path is **SA112 → SA96-PUBLISH (human)**. See [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision) for the recorded squash/guardrail/shrink-only-quality policies and §Bundled Module Inventory (AF7) for the fallback precedent SA113 follows; detailed history is in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
