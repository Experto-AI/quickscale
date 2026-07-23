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

The green-gate join (SA96-GATE) is green with empty quarantine. The **Track 3 (release path)** remains blocked on SA112 after a diagnostic/prototype attempt found additional correctness and planning gaps; no SA112 implementation from that attempt landed (see the blocked checkpoint below). One independent verification ticket (**SA114**) runs in parallel on the otherwise-idle **Track 1**. Track 2's feature chain is complete; one independent test-infra ticket (**SA115**, e2e parallelization) is parked there to use the idle track.

> **SA113 landed** (installed-context implication-resolver bundled-manifest fallback with fail-hard inventory validation, covering both the `plan` and `apply` call sites) and is recorded in [CHANGELOG.md](../../CHANGELOG.md); it unblocked SA111/SA112. Referenced below as `SA113 ✓`.

1. **SA112** (installed-wheel full-lifecycle e2e `plan → apply → up`, Track 3) — heavy e2e lane covering `apply`'s own resolver call site and the Docker path from a real install. Blocked checkpoint recorded below; no implementation from the attempt landed. Deps: SA110 ✓ + SA111a ✓ + SA113 ✓.
2. **SA96-PUBLISH** (staged PyPI publish, Track 3) — **HUMAN-ONLY**. Baseline prerequisites met (SA96-GATE ✓ + SA109 ✓ + SA110 ✓ + SA111a ✓ + SA113 ✓); awaits a human maintainer to execute the irreversible publish. Hold: must not publish while SA112 remains open.
3. **SA114** (v87 gate re-verification & fix sweep, Track 1, `deps: none`) — re-run `make check`/`quality`/`ci`/`ci-e2e` on current `v87` HEAD (the green-gate join was proven at the synced baseline, not HEAD) and fix any drift. Runs in parallel with the Track 3 chain; heavy `ci`/`ci-e2e` legs serialized against Track 3's PG/Docker usage, and any fix in SA113's resolver/`scripts` surface deferred to Track 3.
4. **SA115** (E2E in-lane parallelization, Track 2, `deps: none` · **merge after SA112**) — add `pytest-xdist` in-lane fan-out to the e2e suite (`scripts/test_e2e.sh`) so the ~40–60 serial per-lane tests run across N workers, shortening the longest quality check (`make ci-e2e`). Shares the `scripts/test_e2e.sh` / `.github/workflows/e2e.yml` surface with SA112 and the PG/Docker infra with SA114 — bounds below.

> **SA111a landed** (installed-context `plan` probe selecting all 12 modules in `smoke-install`, plus the `_load_notifications_manifest` bundled-manifest fallback it exposed) and is recorded in [CHANGELOG.md](../../CHANGELOG.md); referenced below as `SA111a ✓`. SA111b remains an optional, non-gating fast monkeypatch test.

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
  - **Blocked checkpoint (2026-07-23; not complete):**
    - **Done:** Started from `v87` at `556f7510`; fixed gate drift outside the installed-context resolver surface; added focused migration-seam coverage; and obtained clean ordered evidence on the pre-final-sync Track 1 baseline: `make check` exit 0, `make quality` exit 0 with zero baseline regressions, `make ci` exit 0, and `make ci-e2e` exit 0 after removing only stranded run-specific `e2e_cli_test_*` containers. Evidence: core 95.35%, CLI 90.43%, 92.89% equal-weight package mean, all 90 files ≥80%, 94.41% module-integration mean, Core E2E 35 passed, CLI E2E 29 passed, and `QUARANTINE_TICKETS` empty. No installed-context resolver file changed.
    - **Pending / blocking:** `SA114-REV-001` (**high**, correctness) — in-place migration still does not require `validateQuickScaleSeam.ts` during donor preflight and can silently skip the dependency; `SA114-REV-002` (**medium**, completeness) — modules-only `make check` passes an empty `SECTIONS` value to `test-unit`, which falls back to default core/CLI suites; `SA114-REV-004` (**medium**, test gap) — runtime-branding E2E assertions must verify the exact `projectName` binding and recursively prove the generated project literal is absent from frontend source consumers; `SA114-SYNC-001` (**medium**, validation gap) — the required final synchronization merged `v87` at `5db3b535` after the accepted gate run, so the four-command evidence has not been re-established on the final merged baseline. `SA114-REV-003` is resolved. Independent change-review pass 2 remains `STATUS: partial`; SA114 stays unchecked.
    - **Decisions needed:** None. Clean continuation requires implementing only the three review blockers, rerunning their focused checks plus all four ordered gates on the final synced baseline, and obtaining an independent `STATUS: ok` review before marking SA114 complete.
  *(why →* the green-gate join was proven at the synced baseline, not at current HEAD; drift since then is unverified, and re-proving it is independent of the installed-context release chain — a genuine use of the idle track*)*

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

### Track 3 — Core/CLI plumbing — release path

> **SA113 (installed-context implication-resolver bundled-manifest fallback) is complete** — see [CHANGELOG.md](../../CHANGELOG.md). It added the fallback (mirroring the SA109 picker pattern) to `resolve_module_implications` for both the `plan` and `apply` call sites, with a fail-hard inventory boundary, resolving the sole remaining installed-wheel crash on the release path and unblocking SA111/SA112.

#### SA111 — Installed-context `plan` + module-implication coverage (SA111a ✓; SA111b optional)

**Root cause resolved (SA113 ✓) and authoritative coverage landed (SA111a ✓).** The installed-wheel
`plan`/`apply` crash (`ImproperlyConfigured: Modules base path not found`, from the fallback-less
`resolve_module_implications`) was fixed by SA113's bundled-manifest fallback across both call
sites, and SA111a proved the fixed `plan` path in the `smoke-install` gate (all 12 modules, from an
installed wheel outside the source tree). Both are closed and recorded in
[CHANGELOG.md](../../CHANGELOG.md). The only reason coverage lived in `smoke-install` rather than
in-monorepo: the crash only reproduces in an installed venv with no `quickscale_modules/` workspace —
an in-monorepo test could merely *simulate* the installed context, the exact drift that shipped this
bug past every green gate. **`apply`'s own installed-context coverage remains open as SA112.**
Only SA111b (below) remains, and it is optional and non-gating.

- [ ] **SA111b — (optional) Fast in-monorepo resolver monkeypatch test.** `Tier 1 · Track 3 · deps: SA109 ✓ · optional`
  Optional quick-signal companion: a unit test in
  `quickscale_core/tests/test_manifest_implications.py` that monkeypatches
  `implications.get_modules_base_path` to raise `ImproperlyConfigured` and asserts
  `resolve_module_implications(["billing"])` still resolves billing → orgs via
  `get_bundled_manifests_path()`. Runs in `make check` for a fast regression tick,
  but is **not** the authoritative guard (it simulates rather than reproduces the
  installed context — see decision above). Skip if SA111a is deemed sufficient.
   - Verify: now unblocked — the resolver's bundled-manifest fallback (SA113) has landed, so this quick-signal unit test is expected to verify the fix once implemented.
  *(why →* cheap early signal on every commit, but explicitly secondary to the real installed-wheel probe*)*

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

  **Blocked checkpoint (2026-07-23) — roadmap record only; SA112 remains open:**

  **Done**
  - Began from a clean Track 3 worktree synced to `v87` at `ae398a22` and confirmed the Poetry Python 3.13 environment and Docker daemon were available.
  - A disposable prototype proved installed `plan` with all 12 modules and reached installed `apply` through all 12 module embeds. The apply attempt then reported `NameError: name 'QUICKSCALE_BILLING_ENABLED' is not defined` during managed-wiring regeneration. `up`, `ps`, `manage migrate`, `down`, and the integrated `make test-e2e` gate were not reached.
  - Prototype-only diagnostics passed 81 resolver tests, 9 shell/e2e harness tests, shell syntax checks, and workflow YAML parsing. Those results describe the discarded prototype, not the current branch.
  - Static discovery found no bare-name evaluation of `QUICKSCALE_BILLING_ENABLED` in the traced managed-wiring path and no billing source/bundled/package version skew. The apply wrapper reduces the exception to `str(exc)`, so the exact raising frame still requires a runtime traceback.
  - Independent change review rejected the executable prototype for merge. All executable, test, workflow, and CHANGELOG changes from the attempt were restored to `v87`; this checkpoint lands no SA112 implementation.
  - Big-tier remediation planning resolved plan findings `SA112-PR-001`, `SA112-PR-003`, `SA112-PR-004`, and `SA112-PR-005`, including safe dirty-state reconstruction, phase ownership, finding closure criteria, and Track-3-only merge handling.

  **Pending / blocking**
  - `SA112-PR-002` (high, blocking — **human-authorized 2026-07-23**, cycle not yet run) — the remediation command registry is not yet literally executable: helper environment/path resolution, SA112-scoped documentation assertions, and exact non-mutating command argv still require one focused plan correction and review before any diagnostic phase may begin. The maintainer has authorized this single scoped cycle (see Decisions); it must return `STATUS: ok` before any diagnostic phase starts.
  - `SA112-CONT-001` (high, blocking for completion) — capture the full installed-apply traceback, identify the actual `QUICKSCALE_BILLING_ENABLED` raising frame, then plan/review the root fix. Do not choose a billing fix from the current user-facing error alone.
  - `SA112-CR-001` (high) — preserve tracking of authoritative `.quickscale/state.yml`; never ignore the whole `.quickscale/` directory.
  - `SA112-CR-002` / `SA112-CR-003` (high) — disable apply auto-start for this explicit lifecycle and make dependent phases fail fast while cleanup still runs.
  - `SA112-CR-004` (high) — align per-run project, Compose, container, port, and cleanup identities and prove interruption-safe cleanup.
  - `SA112-CR-005` (medium) — make E2E workflow triggers cover the resolver, bundled-manifest, managed-adapter, and lane dependency surfaces.
  - `SA112-CR-006` (medium) — implement tri-state staged-diff probing (`0` no changes, `1` changes, `>1`/`OSError` failure) with index restoration and caller-test parity.
  - `SA112-CR-007` (medium) — add truthful packaged-inventory fallback proof rather than claiming notifications/orgs examples cover all 12 modules.
  - `SA112-CR-008` (high) — keep roadmap/CHANGELOG evidence factual and defer completion language until installed lifecycle validation and independent review are green.

  **Decisions**
  - **AUTHORIZED (2026-07-23):** the maintainer explicitly authorized **one narrowly scoped `SA112-PR-002` plan-correction/review cycle** — make the remediation command registry literally executable (helper environment/path resolution, SA112-scoped documentation assertions, exact non-mutating command argv). This authorization is bounded: no product implementation or diagnostic instrumentation is authorized until that plan-correction returns `STATUS: ok` from independent review. **Next action on Track 3:** run the single `SA112-PR-002` correction + review cycle, then proceed to the traceback capture (`SA112-CONT-001`).
  - After the runtime traceback is captured, surface a decision only if it reveals multiple contract-valid fixes with materially different compatibility consequences; otherwise use the traceback-selected technical fix.

### Track 3 (prior) — Core/CLI plumbing — release path

**Prior Track 3 work COMPLETE.** The foundational Track 3 work is closed (arch-audit Finding 1 via SA89a+SA89b; all four GATEs; SA91 parallel worker pool; SA93 e2e in green-gate; SA100 theme preflight; SA101 quality remediation; SA96-GATE join; SA109 installed-wheel discovery fix; SA110 installed-artifact smoke gate; SA113 resolver fix; SA111a installed-context plan coverage). See [CHANGELOG.md](../../CHANGELOG.md). The **open** Track 3 engineering item is SA112 (installed-wheel lifecycle coverage, above); SA111b is optional and non-gating, and **SA96-PUBLISH** remains human-only.

The AF7 installed-wheel discovery decision is recorded in [`decisions.md`](../technical/decisions.md#af7-installed-wheel-module-discovery): discovery falls back to bundled manifest snapshots (`quickscale_core/data/manifests/*/module.yml`) when the source workspace is absent, while source-required operations (`get_modules_base_path`, `discover_shipped_module_paths`, `load_module_manifest`, `refresh_managed_adapters`) remain fail-hard.

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

Only open work is shown; all prior tickets are complete (see [CHANGELOG.md](../../CHANGELOG.md)).

```
Track 1 (idle → SA114)   Track 2 (chain done → SA115)    Track 3 → release (critical path)
────────────────────   ────────────────────────────     ─────────────────────────────────
SA114 (gate re-verify   SA104 ✓ → SA105 ✓ → SA106 ✓       SA96-GATE ✓  SA109 ✓  SA110 ✓
  & fix; deps: none)      → SA107 ✓ → SA108 ✓                │
  ‖ parallel, heavy     SA115 (e2e xdist; deps: none,       │
  legs serialized         merge after SA112)                │
                         (arch Finding 10 chain closed)     SA113 ✓ ── bundled-manifest fallback
                                                                      │  both call sites (plan+apply)
                                                             ┌────────┴────────┐
                                                           SA111a ✓         SA111b (optional)
                                                         (smoke probe)     (fast unit test)
                                                             │
                                                           SA112 ── installed-wheel plan→apply→up e2e
                                                             │
                                                             ▼
                                                         SA96-PUBLISH ── build → publish
                                                           deps: SA96-GATE ✓ + SA109 ✓ + SA110 ✓ + SA111a ✓ + SA113 ✓
                                                           (human-only; hold until SA112 closes)
```

**Parallelism.** The remaining gating Track 3 work forms one release unit: SA112 → SA96-PUBLISH; SA111a is complete, and SA111b is optional and non-gating. **SA113** (`implications.py`) has landed (bundled-manifest fallback with fail-hard inventory validation). **SA114** is an independent open Track 1 workstream: re-verifying the make gates against current `v87` HEAD is a different intent from adding installed-context coverage, and `deps: none`. It runs in parallel with the Track 3 release chain under two explicit bounds: (1) **infra** — its heavy `make ci`/`ci-e2e` legs share the same PostgreSQL/Docker as Track 3's `smoke-install`/e2e runs and must be serialized against them (per-lane knobs don't span worktrees); (2) **fix scope** — any failure inside SA113's surface (`implications.py`, `scripts/smoke_install.sh`, the installed-wheel e2e lane) is handed to Track 3, not fixed on Track 1. With those bounds the only shared-closeout overlap across all tracks is `CHANGELOG.md`/`roadmap.md`, covered by the Merge procedure. SA96-PUBLISH (human-only) shares no files with the assistant-executable tickets.

### Track readiness (2026-07-23)

- **Track 1 — SA114 blocked checkpoint, off the critical path.** The four ordered gates were green with empty quarantine on the pre-final-sync baseline, but independent review still has three blocking findings (`SA114-REV-001`, `SA114-REV-002`, `SA114-REV-004`) and final-sync validation gap `SA114-SYNC-001`; the ticket remains unchecked. No product decision is open — clean continuation is the bounded fix/validate/re-review sequence recorded in the task block. Heavy `ci`/`ci-e2e` legs remain serialized against Track 3's PG/Docker usage, and installed-context resolver-surface fixes remain deferred to Track 3 follow-up ownership.
- **Track 2 — feature chain COMPLETE; one parked infra ticket (SA115), off the critical path.** Chain stages SA104/SA105/SA106/SA107/SA108 complete. Track 2 frontend de-specialization chain (arch Finding 10) is fully closed. SA115 (e2e in-lane pytest-xdist parallelization, `deps: none`) is parked here to use the idle track; it shares the `scripts/test_e2e.sh` runner surface with SA112 (**merge SA115 after SA112**) and the PG/Docker infra with SA114 (serialize heavy runs). Clean to start. Legacy compatibility finding documented: SA105 dormant-file guarantee applies only to fresh current-theme recipients; legacy pre-SA105 recipients have no retroactive dormant guarantee for any module surface — running `quickscale apply` does not guarantee or backfill blog/crm/listings; the shipped continuation adopts only missing forms/social surfaces (no blog/crm/listings backfill). No blocker.
- **Track 3 — open engineering work; SA112-PR-002 cycle human-authorized (2026-07-23), not yet run.** The green-gate join, SA109, SA110, SA113, and SA111a are closed. SA113 resolved the installed-context implication resolver crash, and SA111a proves installed-wheel `plan` coverage with all 12 modules. SA111b remains optional and non-gating. **SA112**'s first blocker — the `SA112-PR-002` plan-correction/review cycle — is now **maintainer-authorized**; the next action is to run that single scoped cycle to `STATUS: ok`, then proceed to the traceback capture (`SA112-CONT-001`) and the traceback-selected root fix, with review findings `SA112-CR-001..008` still to clear (see the SA112 block for the exact continuation ledger). SA96-PUBLISH (human-only) holds until SA112 closes. Non-gating advisories remain deferred (SA91 CR-SA91-REV-006 low; SA89B-CR-004; SA93-REV-005; SA93-ADV-001..004; SA104-ADV-001; SA105-ADV-001; CR-SA106-002; SA110-ADV-001).

**Track 3 decision — RESOLVED (2026-07-21): Option A, fix-first.** The resolver fix was ticketed as **SA113** on Track 3 and landed before its coverage; SA111a then verified the installed `plan` path, making SA112 dependency-unblocked at that point. SA111b remains optional. SA112 is now checkpoint-blocked on `SA112-PR-002`, followed by `SA112-CONT-001` and `SA112-CR-001..008`, as recorded above. The resolver work stayed on Track 3 (not an idle Track 1/2) because it was the *head* of the dependency chain — nothing ran in parallel with it, and splitting the fix from its coverage (same resolver module, `scripts/`, e2e lane) would only have created a cross-track merge hazard. The fix follows the SA109/AF7 bundled-fallback precedent in decisions.md.

**Net.** Track 1 has one independent off-path ticket at a blocked checkpoint (SA114, gate re-verification); its three review blockers and final-sync validation gap must close before completion. Track 2's feature chain is complete, with one independent off-path infra ticket (SA115, e2e in-lane parallelization — merge after SA112, PG/Docker serialized with SA114). Track 3 is **not** done: SA113 and SA111a are closed, and the remaining critical path is **SA112 → SA96-PUBLISH (human)**, with optional SA111b off-path. See [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision) for the recorded squash/guardrail/shrink-only-quality policies and §Bundled Module Inventory (AF7) for the fallback precedent SA113 follows; detailed history is in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
