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

The green-gate join (SA96-GATE), the installed-wheel discovery/resolver chain (SA109 ✓, SA110 ✓, SA113 ✓, SA111a ✓, SA111b ✓), the Track 2 frontend de-specialization chain (SA104 → SA108 ✓), and the Track 1 re-verification chain (SA114 ✓, SA116 ✓) are closed; detail lives in [CHANGELOG.md](../../CHANGELOG.md). Three items remain open.

1. **SA112a → SA112f** (installed-wheel full-lifecycle e2e `plan → apply → up`, Track 3) — six serial, handoff-sized tasks covering provisioning, diagnosis, the traceback-selected fix, permanent lifecycle coverage, CI triggers, and closeout. **Critical path.** Next: SA112a. Deps: SA110 ✓ + SA111a ✓ + SA113 ✓.
2. **SA96-PUBLISH** (staged PyPI publish, Track 3) — **HUMAN-ONLY**. Baseline prerequisites met (SA96-GATE ✓ + SA109 ✓ + SA110 ✓ + SA111a ✓ + SA113 ✓); awaits a human maintainer to execute the irreversible publish. Hold: must not publish while SA112 remains open.
3. **SA115** (E2E in-lane parallelization, Track 2, `deps: none` · **merge after SA112**) — `pytest-xdist` in-lane fan-out for the e2e suite. Implementation committed and reconciled with current `v87`. Heavy validation is NOT authorized (SA115-DEC-001 step 3 remains unauthorized per 2026-07-26 maintainer decision; human-authorization-gated, not SA112-gated). Only the merge is order-gated.

Arch **Finding 7** (generated-file-ownership taxonomy derivation) stays **unscheduled** — gated on a third consumer or a public "update my generated project" command. Arch Findings **2/4** remain **not ticketed**, deferred with the (unscheduled) teams module. Both audits ([arch-audit.md](../others/arch-audit.md), [tech-audit.md](../others/tech-audit.md)) otherwise stand at zero open findings.

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a clean rerun at current `v87` HEAD (last proven green by SA114 — closed — on 2026-07-25), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). The four-command join covers everything end to end — unit **and** integration **and** e2e. `make check` is the **fast** repo gate — `lint` + `typecheck` + `test-unit` (unit only) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (see the `check` target in `Makefile`; `make check QUIET=1` is the quiet LLM/agent variant). **Integration coverage lives in `make ci`** (unit + integration when PostgreSQL is available), and e2e in `make ci-e2e` (`.github/workflows/e2e.yml`). So `make check` alone does not prove integration — the `ci`/`ci-e2e` legs of the join do.

The join runs entirely **inside the monorepo** and does **not** exercise the pip-installed wheel — that gap was closed by SA109/SA110 (both complete; see [CHANGELOG.md](../../CHANGELOG.md)). `make smoke-install` builds wheels from per-run staged copies (no source mutation), installs into a throwaway venv outside the source tree, and runs every non-mutating CLI command from a sanitized external workdir under the full `>=3.13,<3.15` Python constraint.

### SA96-PUBLISH — Staged release ladder

- [ ] **SA96-PUBLISH — Staged release ladder.** `Tier 1 · v87 · deps: SA96-GATE ✓ + SA109 ✓ + SA110 ✓ + SA111a ✓ + SA113 ✓` · **HUMAN-ONLY — do not delegate to an assistant**
  Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full` for test→verify→prod in one shot). **PyPI publish is irreversible/outward-facing — a human maintainer must confirm version + green-gate status before `publish-prod`. This step is explicitly excluded from any SA93/SA96-GATE assistant handoff.**

  *(Acceptance:* all 12 modules green in isolation; SA96-GATE four-command run exits 0 with empty quarantine; SA109 ✓ and SA110 ✓ closed (installed wheel runs non-mutating commands clean); SA113 ✓ closed (resolver fix landed); SA111a ✓ and SA112 closed (optional SA111b is non-gating); release published and verified on PyPI.*)*
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*
### Track 2 — Module contracts & settings — frontend-theme de-specialization (arch Finding 10)

**Feature chain COMPLETE** (SA104 → SA108; arch-audit Finding 10 retired). Detail in [CHANGELOG.md](../../CHANGELOG.md). One independent test-infra ticket (**SA115**) sits on this otherwise-idle track — implemented and reconciled with `v87`, but heavy validation remains unauthorized pending explicit future maintainer approval (SA115-DEC-001 step 3).

#### SA115 — E2E in-lane parallelization (pytest-xdist)

`make ci-e2e` is the longest quality check in the SDLC. It runs the full 12-stage local CI (`scripts/check_ci_locally.sh --e2e`), whose final stage is `scripts/test_e2e.sh`. That script already runs the **Core** and **CLI** e2e lanes concurrently (`QS_E2E_PARALLEL=1`), each in its own Docker Compose project / container prefix / dynamic host port — **but within each lane the ~40–60 `@pytest.mark.e2e` tests run serially** (the pytest invocation has no `-n`). Because each test generates a full Django project, runs `poetry install`, builds, and drives Playwright/Chromium, that serial in-lane run is the dominant cost, and the total is gated by whichever single lane is slowest. Adding in-lane `pytest-xdist` fan-out is the highest-leverage remaining speedup.

Most groundwork already exists and is xdist-aware: `pytest-xdist ^3.8.0` is already a dependency (used for unit tests); `quickscale_core/tests/conftest.py` already isolates per worker via `_isolate_poetry_cache_per_worker()` (per-`PYTEST_XDIST_WORKER` Poetry cache) and the `per_test_db`/`unique_db_name` fixtures (unique DB per test, collision-free across workers); project generation uses per-test `tmp_path`. The **only** real blocker is that the `pytest-docker` **session-scoped** fixtures (`docker_compose_file`, `postgres_service`, conftest lines 122–157) are not xdist-safe — under `-n` each worker is its own session and would bring up the *same* Compose project (same default name, same named volume `postgres_test_data`), colliding.

**Design (ratified with maintainer):** *container-per-worker* Postgres; *scope limited to the E2E stage* (no lane rebalancing).

- [ ] **SA115 — Add in-lane pytest-xdist fan-out to the e2e suite.** `Tier 2 · Track 2 · deps: none · merge after SA112`
  > *Phases 1 and 2 below are **implemented** (see the checkpoint). Their `scripts/test_e2e.sh` line citations are pre-implementation guidance and no longer resolve — the file has since grown via the memory guard, heartbeat, provenance banner, and the SA115 merge itself. Read them as historical intent, not as current anchors.*

  1. **xdist-safe pytest-docker fixtures (container per worker).** In `quickscale_core/tests/conftest.py`, add a session-scoped override of pytest-docker's `docker_compose_project_name` that derives a **unique per-worker** Compose project name from the lane's `QS_E2E_COMPOSE_PROJECT_NAME` (exported per lane at `scripts/test_e2e.sh:225`) plus `PYTEST_XDIST_WORKER` (falls back to a single name when not under xdist). Keep the lane prefix intact so the shell's `cleanup_scoped_containers` (test_e2e.sh:163–176) still matches by `name=<prefix>` substring. Docker Compose auto-prefixes the named volume with the project name, so `docker-compose.test.yml` needs **no change** (port already dynamic). Confirm whether `quickscale_cli/tests/` defines its own docker fixtures and mirror the override there.
  2. **Configurable worker count.** In `scripts/test_e2e.sh`, extend the `pytest_cmd` builder (~line 265) to append `-n <workers> --dist loadscope`, driven by a new `QS_E2E_XDIST_WORKERS` env var. Default to a small `nproc`/RAM-derived cap (mirror the Makefile's existing `PYTEST_XDIST_WORKERS` heuristic — **not** `auto`, since each worker now runs a full Postgres container + Chromium and is memory-heavy). `QS_E2E_XDIST_WORKERS=1` (or `0`) must degrade to today's serial no-`-n` path (debugging escape hatch, mirroring `QS_E2E_PARALLEL=0`). Document the var in the script `--help` and `# Environment:` header. Surface the chosen worker count in the lane banner (near test_e2e.sh:251–253). Keep the two lanes concurrent → total load is `2 lanes × N workers`; pick the default with combined RAM/container budget in mind.
  - **Concurrency bound (infra):** shares the live PostgreSQL/Docker + ports with SA112's installed-wheel e2e — **serialize** heavy runs across worktrees (per-lane knobs namespace lanes *within* one invocation, not across worktrees). SA114's heavy legs already ran to completion on 2026-07-25 and no longer contend for this infra.
  - **Merge-order bound (hazard — re-examined 2026-07-26):** `scripts/test_e2e.sh:439` already points the CLI lane at `$CLI_DIR/tests/`, so SA112d must confirm collection and avoid a runner edit when that remains true. Executable overlap is limited but not empty: SA112e and SA115-CI-001 both append entries to `.github/workflows/e2e.yml`'s `pull_request.paths` list and must preserve both ordered tuples. The bound is **retained** for that coordination, because SA112c's root-fix scope stays unknown until SA112b captures the traceback, and because any rebase burden must not land on the critical path. **Land SA115 after SA112**; shared-closeout overlap (`CHANGELOG.md`/`roadmap.md`) is covered by the Merge procedure. See `SA115-DEC-001`.
  - Verify: the `SA115-DEC-002` clamp — a fired memory guard yields serial lanes **and** serial workers (including when an explicit `QS_E2E_XDIST_WORKERS=N` is overridden, with a visible message), while `QS_E2E_NO_MEMORY_GUARD=1` preserves the requested count; baseline `time QS_E2E_XDIST_WORKERS=1 ./scripts/test_e2e.sh` vs. parallel default is faster with all e2e tests green; `docker ps` mid-run shows one Postgres container per active worker with distinct project names/ports; back-to-back runs leave no leftover containers/volumes (`docker volume ls | grep postgres_test_data`); `QS_E2E_XDIST_WORKERS=1` reproduces the old serial path; `make ci-e2e` stays green; `.github/workflows/e2e.yml` passes on the CI runner (tune default worker count to runner cores/RAM).
  *(why →* `ci-e2e` is the longest gate in the SDLC; lanes are already concurrent but each runs serially inside, and the xdist groundwork (per-worker cache + per-test DB) already exists — the sole blocker is xdist-safe pytest-docker fixtures*)*

  **Checkpoint — SA115 remains open (no longer parked; work is committed):**

  **Done (2026-07-23 implementation; committed and reconciled 2026-07-25).** Phases 1 and 2 are implemented on `wt-track2`: a worker-unique `docker_compose_project_name` fixture and the `QS_E2E_XDIST_WORKERS` runner knob. **`SA115-DEC-001` steps 1–2 are complete:** the four previously parked files are committed (`5193f198`) and `v87` is merged into `wt-track2` (`5b5de830`), so the branch is clean and current. The `scripts/test_e2e.sh` drift is reconciled — three conflicts (Environment header, `--help` list, worker-resolution vs. memory-preflight block), all additive on both sides, resolved by keeping both. Post-merge focus checks are green (combined pytest exit 0): `bash -n` clean, **31 focused tests pass — 16 fixture + 15 harness**, Ruff check/format clean. The harness count moved from the 13 recorded on 2026-07-23 to 15 because `v87` added two harness tests in the interim (the baseline on `v87` is 9; SA115 adds 6) — the earlier figure was correct when written, not an error. No container lifecycle or back-to-back teardown has been exercised yet.

  **Pending / blocking**
  - **Validation not yet run (does *not* require SA112).** `SA115-DEC-001` step 3 was resolved on 2026-07-26: the maintainer chose **Keep unauthorized**. The heavy validation sequence below remains pending explicit future approval. Steps 1–3 need only exclusive Docker/PostgreSQL:
    1. Run serial baseline (`QS_E2E_XDIST_WORKERS=1`) vs. default parallel E2E, proving distinct container names/ports per worker and clean teardown (`docker volume ls | grep postgres_test_data` shows no leftovers).
    2. Run `make ci-e2e`.
    3. Run local `./scripts/check_ci_locally.sh --e2e`, and separately the hosted runner (`.github/workflows/e2e.yml`) if available, listing results for each.
    - **Guard/xdist interaction — RATIFIED: the guard wins (`SA115-DEC-002`, 2026-07-25).** Total machine load is `lanes × workers`. The memory preflight was written when one lane meant half the load, so when it demotes to serial lanes it believes it halved the run — but SA115 changed what a lane *contains*, and a demoted run still fans out N workers per lane (old normal `2×1=2`; demoted-with-xdist `1×4=4` — i.e. the "protected" run is heavier than the load the guard was protecting). At default settings the two agree by coincidence, because the worker default is itself RAM-derived (~1 worker per 4 GB, cap 4); the real exposure is an explicit `QS_E2E_XDIST_WORKERS=N` override, which bypasses the memory-derived default and leaves the guard counting only lanes. **Decision: when the guard fires, it also clamps workers to serial.**
      - **Implementation:** inside `memory_preflight_guard`'s `if [ -n "$reason" ]` block (`scripts/test_e2e.sh:244-251` on `wt-track2` at `5b5de830`, alongside the existing `E2E_PARALLEL=false` / `SERIAL_CAUSE=` assignments), set `E2E_XDIST_WORKERS=1`. Ordering already works: workers resolve at ~line 144-172, the guard is called at line 254, and the `Xdist:` banner prints afterwards — so the banner reports the clamped value with no extra plumbing.
      - **Must be visible, not silent:** when the clamp overrides an explicit user-supplied `QS_E2E_XDIST_WORKERS`, say so on the existing warning path (the guard already prints its reason and the `QS_E2E_NO_MEMORY_GUARD=1` override hint). A silent clamp would make a slow run look inexplicable.
      - **Escape hatch is the existing one:** `QS_E2E_NO_MEMORY_GUARD=1` bypasses the guard entirely and therefore the clamp too. Do not add a second override.
      - **Cover it:** extend the harness tests so a fired guard is asserted to produce both serial lanes *and* serial workers, and a bypassed guard is asserted to preserve an explicit worker count.
      - *(why →* fits the house fail-closed style — the RLS boot guard, the theme preflight, and this guard all refuse conservatively and offer one explicit opt-out (see [decisions.md §fail-hard-principle](./decisions.md#fail-hard-principle)). Leaving the knobs orthogonal would keep a guard that advertises protection it no longer delivers, and the failure it prevents (an OOM kill mid-run) is expensive and presents as a confusing random crash rather than a memory problem.*)*
    - **Close the workflow-trigger gap (`SA115-CI-001`, found 2026-07-25).** SA115's two new/changed test surfaces — `quickscale_core/tests/test_e2e_xdist_fixtures.py` and `quickscale_core/tests/conftest.py` — appear in **neither** `on.pull_request.paths` list in `.github/workflows/e2e.yml`, so a PR touching only them would not trigger the e2e workflow. This is the same defect class as `SA112-CR-005` (workflow-trigger path completeness) and should be fixed to the same standard: exact repository-relative path strings, order preserved, with `yaml.BaseLoader` regression coverage. Coordinate with SA112's own paths append to avoid duplicate entries.
  - **SA112 gates only the merge.** After SA112f closes the umbrella: re-merge `v87` into `wt-track2` (should be near-empty now), confirm SA112d added nothing to `scripts/test_e2e.sh`, obtain independent change review (`STATUS: ok`), then mark SA115 `[x]` and add the CHANGELOG entry.
  - **No completion language or CHANGELOG entry until validation and independent review are green.**

  **Decision:** `SA115-DEC-001` step 3 was resolved on 2026-07-26: the maintainer chose **Keep unauthorized**. Heavy validation remains unauthorized pending explicit future approval; it is human-authorization-gated, not SA112-gated. SA115-DEC-002 (guard vs. xdist) remains **ratified** — its implementation will ride along with the validation phase when authorized. Only the merge is mechanically gated by SA112.

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
  Umbrella acceptance only: SA112a–SA112f must prove that an installed wheel can
  provision an external project, run `plan` with all 12 modules, run `apply`, invoke
  the installed `up` command explicitly, boot and serve through Docker/PostgreSQL,
  run `ps` and `manage migrate`, and tear down cleanly. The chain must also preserve
  the 20-probe smoke gate and add exact CI trigger coverage. Child tickets own all
  implementation; do not execute this parent block as a monolithic handoff.
  - Verify: every child is independently reviewed and merged in order, and SA112f records the complete installed `plan → apply → up → serve → ps/manage → down` evidence before this parent is marked complete.
  *(why →* `apply`/`up` have zero installed-artifact coverage; the existing lifecycle e2e runs only from source, which cannot reproduce install-context discovery bugs*)*

  **Recorded partial delivery (2026-07-26; plan-review cap reached; no implementation landed).**

  - **Done:** SA110, SA111a, and SA113 remain satisfied. Two focused plan-review cycles checked the former monolithic A–E artifact. They confirmed the exact five-path GitHub Actions trigger tuple and deterministic `yaml.BaseLoader` contract, resolving `SA112-CR-005` at plan-detail level. They also corrected the installed `apply` stdin to the current three confirmations (`"n\ny\ny\n"`). An unexpected uncommitted SA112 prototype was preserved in `45e37a86`, reviewed only as evidence, and then fully neutralized by `56b27045`; its 13 paths have zero net delta from the synced `v87` baseline. No SA112 implementation is present in the mergeable tree.
  - **Pending / blocking:** `SA112-PR-002` (**high, blocking, completeness**) remains open. Across review cycles 1 and 2 the highest unresolved severity stayed high and the unresolved count stayed one, so the plan loop hit its non-convergence cap. Missing literal details include copyable phase commands and expected exits/artifacts, NUL-safe staged-file checks, diagnostic/negative-control capture and scoped cleanup, explicit cleanup-failure precedence and tests, rollback mechanics, exact focused validation commands, quarantine proof, and a final review that includes closeout documentation.
  - **Decisions needed:** none. At the cap, the maintainer chose recorded partial delivery and replaced the all-at-once handoff with the six serial tasks below. Do not reconstruct or execute the superseded monolithic artifact. Each child starts from a clean Track 3 worktree synced to `v87`, receives its own narrow literal plan, and may mutate only after that scoped plan review returns `STATUS: ok`.

  **Serial handoff contract.** Execute exactly one child at a time on Track 3. Each child must name its complete file allowlist, commands, expected exits/artifacts, rollback, and focused validation before implementation; compare the staged names against that allowlist after `git add -A`; obtain independent change review; merge the reviewed child back to `v87`; then start the next child from a fresh sync. A child may stop with evidence and no source delta. Never carry an unreviewed implementation across child boundaries. `SA112` closes only after SA112a–SA112f are all complete.

  - [ ] **SA112a — Extract the installed-wheel provisioner and preserve smoke parity.** `Tier 2 · Track 3 · deps: SA110 ✓ + SA111a ✓ + SA113 ✓`
    Extract the reusable staging/build/venv helpers from `scripts/smoke_install.sh` into a sourceable `scripts/_installed_wheel_venv.sh`, add the thin `scripts/provision_installed_venv.sh` wrapper, and keep all 20 smoke probes unchanged. The scoped plan must specify helper-owned temporary directories and signal/exit cleanup, caller-owned output cleanup, exact core → CLI → umbrella build/install order, one-line stdout, stderr chatter, usage exits, caller-trap/status preservation tests, the three-file allowlist, and exact `bash -n`, focused-test, and `make smoke-install` evidence. **Current status:** next pending task; implementation requires scoped plan-review `STATUS: ok`. **Open decisions:** none.
    *(why →* `SA112-PR-002`; creates a green, independently reviewable provisioning seam before Docker lifecycle work*)*

  - [ ] **SA112b — Capture the installed `apply` traceback with a literal diagnostic.** `Tier 2 · Track 3 · deps: SA112a`
    From an external workdir and the installed entrypoint produced by SA112a, run the exact all-module `plan` and current three-confirmation `apply` under `QUICKSCALE_DEBUG=1`. Record argv, cwd, sanitized environment, stdin bytes, timeouts, return handling, traceback path, final raising frame/call chain, and exact-prefix Docker/volume cleanup. This child is evidence-first and may complete with no source delta. If the checkpoint state unexpectedly passes, require a disposable negative control that reproduces the original failure; stop rather than infer a fix. **Open decisions:** ask only if the actual frame admits multiple contract-valid fixes with materially different compatibility effects.
    *(why →* `SA112-PR-002`; the static searches cannot identify the bare-name raising frame*)*

  - [ ] **SA112c — Apply the traceback-selected root fix.** `Tier 2 · Track 3 · deps: SA112b`
    Change only the production site(s) justified by SA112b's final raising frame. Add the nearest regression for the previously raising branch and enumerate callers whenever an exported/shared contract changes; an out-of-allowlist caller requires explicit scope expansion. Re-run the diagnostic to prove the original frame is gone without weakening fail-hard inventory behavior. **Open decisions:** inherited only if SA112b recorded multiple materially different valid fixes.
    *(why →* `SA112-PR-002`; prevents speculative broad fallbacks and preserves caller compatibility*)*

  - [ ] **SA112d — Add the permanent installed-wheel lifecycle E2E.** `Tier 2 · Track 3 · deps: SA112c`
    Add `quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py` using the installed binary, external cwd, all 12 modules, current apply stdin `"n\ny\ny\n"`, bounded subprocesses, and exact lane/container scoping. After `apply` completes its own start/migration path, run installed `down` without volumes to remove double-start ambiguity, then invoke installed `up` explicitly, poll the allocated application URL to a bounded deadline and require a successful HTTP response, then run `ps`, `manage migrate`, and final `down --volumes`. Cover provisioning failure before fixture yield and cleanup precedence for timeout, exception, and nonzero `down`: a primary lifecycle failure stays primary; cleanup failure is primary only when no earlier failure exists. Confirm `scripts/test_e2e.sh` already collects the CLI test directory; do not edit the runner if it does. **Open decisions:** none.
    *(why →* `SA112-PR-002`; supplies the permanent installed-artifact coverage after the root fix is known*)*

  - [ ] **SA112e — Add the exact E2E workflow-trigger contract.** `Tier 1 · Track 3 · deps: SA112d`
    Immediately after `scripts/test_e2e_parallel.py` in `.github/workflows/e2e.yml`, add exactly once and in order: `quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py`, `scripts/smoke_install.sh`, `scripts/_installed_wheel_venv.sh`, `scripts/provision_installed_venv.sh`, `scripts/_python_requirement.sh`. Add a named `yaml.BaseLoader` regression that asserts the exact slice and uniqueness. Do not duplicate `scripts/test_e2e.sh` or the workflow self-path. **Open decisions:** none; `SA112-CR-005` is resolved at plan-detail level and this child supplies implementation evidence.
    *(why →* `SA112-CR-005`; a PR changing any installed-wheel dependency must trigger E2E*)*

  - [ ] **SA112f — Run ordered acceptance, review the complete delta, and close SA112.** `Tier 2 · Track 3 · deps: SA112e`
    In exclusive Docker/PostgreSQL capacity, run the declared shell syntax and focused tests, `make smoke-install` with all 20 probes, then `make ci-e2e` with `QUARANTINE_TICKETS` empty. Obtain a full-scope independent review of the executable delta. Only after `STATUS: ok`, update this roadmap and `CHANGELOG.md`, then obtain the final full-scope review covering those closeout files before commit/merge. Record every command, exit, skip/warning, review finding, and evidence artifact. **Open decisions:** none unless validation or review returns a new blocker.
    *(why →* `SA112-PR-002`; completion claims and release-path integration require reviewed evidence, including closeout docs*)*

#### Standing references

The AF7 installed-wheel discovery decision is recorded in [`decisions.md`](../technical/decisions.md#af7-installed-wheel-module-discovery): discovery falls back to bundled manifest snapshots (`quickscale_core/data/manifests/*/module.yml`) when the source workspace is absent, while source-required operations (`get_modules_base_path`, `discover_shipped_module_paths`, `load_module_manifest`, `refresh_managed_adapters`) remain fail-hard. All prior Track 3 work (arch Finding 1, the four GATEs, SA91/SA93/SA100/SA101/SA96-GATE/SA109/SA110/SA113/SA111a/SA111b) is closed in [CHANGELOG.md](../../CHANGELOG.md).

### Dependency & parallelization overview

Only open work is shown; all prior tickets are complete (see [CHANGELOG.md](../../CHANGELOG.md)).

```
Track 2 (validation-paused; merge queued)  Track 3 → release (CRITICAL PATH)
───────────────────────────────   ──────────────────────────────────
SA115 (e2e xdist; deps: none)     SA112a → b → c → d → e → f
  │                                 │      serial reviewed handoffs
  └── merge after SA112 ◄───────────┤
                                     ▼
                                 SA96-PUBLISH ── build → publish
                                   (human-only; hold until SA112)
```

**Critical path:** `SA112a → SA112b → SA112c → SA112d → SA112e → SA112f → SA96-PUBLISH`. That is the longest remaining dependency chain to release, and the only chain worth optimizing — the SA112 umbrella is also the merge gate SA115 waits behind, so it is the single scheduling bottleneck in the repo.

**Parallelism.** The three top-level open tickets occupy two tracks (SA112a–SA112f → SA96-PUBLISH sequentially on Track 3, SA115 on Track 2), and no rebalancing move is available that would speed the critical path:

- **SA112 is split only as a serial Track 3 chain.** SA112a–SA112f are separate reviewed handoffs on the same worktree, each merged to `v87` before the next starts. They must not fan out across tracks: provisioning, traceback evidence, the root fix, lifecycle coverage, triggers, and closeout remain causally ordered, and parallel branches would recreate the shared-file and stale-evidence hazard the split is designed to remove.
- **SA115 must stay on Track 2.** SA112d has no expected runner overlap because it must use existing CLI-directory collection without editing `scripts/test_e2e.sh`. SA112e and SA115-CI-001 do share the workflow `pull_request.paths` list and must preserve both ordered tuples. The `merge after SA112` bound remains for that path-list coordination, because SA112c's traceback-selected root-fix scope is still unknown, and because critical-path rebase risk belongs off Track 3. (Its infra contention is now with SA112 only — SA114's heavy legs are done.)
- **Track 2 does not feed the critical path.** SA115 shortens a gate; it is not a dependency of SA112 or SA96-PUBLISH, so moving work onto Track 3 could only slow it.

**Infra serialization (not a track constraint).** SA112's and SA115's e2e lanes (and any future `make ci`/`make ci-e2e` rerun) all need the same live PostgreSQL server, Docker daemon, and ports. The `QS_CI_PARALLEL`/`QS_E2E_PARALLEL`/per-lane-scope knobs namespace lanes *within* one invocation, not across worktrees — only one track may exercise PG/Docker at a time regardless of track assignment.

**Conflict surface.** The shared closeout files are `CHANGELOG.md` and `docs/technical/roadmap.md` (plus `docs/technical/decisions.md` when policy or acceptance evidence changes). All three are covered by the Merge procedure above: the `git merge v87` before every merge-back forces conflicts to resolve on the track branch, preserving both sides. SA112d has no expected `scripts/test_e2e.sh` overlap with SA115; SA112e and SA115-CI-001 share `.github/workflows/e2e.yml`'s path-list surface. The `merge after SA112` bound serializes that coordination and protects the critical path from SA112c's still-unknown traceback-selected scope and later rebase burden.

### Track readiness (2026-07-26)

- **Track 2 — IMPLEMENTATION-READY BUT VALIDATION-PAUSED; merge queued behind SA112 (off the critical path).** SA115 is committed (`5193f198`) and reconciled with current `v87` (`5b5de830`) as of 2026-07-25 — `SA115-DEC-001` steps 1–2 are done, and the `scripts/test_e2e.sh` drift (memory guard, heartbeat, provenance, swap-veto correction) is resolved with post-merge focus checks green. The branch is clean and current, but SA115-DEC-001 step 3 heavy validation remains unauthorized per the 2026-07-26 maintainer decision. Validation is human-authorization-gated, not SA112-gated. Only the *merge* is order-gated behind SA112. Legacy compatibility finding stands: the SA105 dormant-file guarantee covers only fresh current-theme recipients; legacy pre-SA105 recipients get no retroactive dormant guarantee, and the shipped continuation adopts only missing forms/social surfaces (no blog/crm/listings backfill).
- **Track 3 — BLOCKED AT SA112a (process gate, on the critical path).** Two plan-review cycles on the former monolithic artifact hit the non-convergence cap with `SA112-PR-002` still high/blocking; `SA112-CR-005` is resolved at plan-detail level. The unreviewed prototype is neutralized and the mergeable tree has no SA112 executable delta. **Clean to continue:** start SA112a only, from a clean Track 3 worktree synced to latest `v87`, and obtain `STATUS: ok` on SA112a's narrow literal plan before editing. Complete and merge each child before opening the next. SA96-PUBLISH (human-only) holds until SA112f closes the umbrella. Non-gating advisories remain deferred (SA91 CR-SA91-REV-006; SA89B-CR-004; SA93-REV-005; SA93-ADV-001..004; SA104-ADV-001; SA105-ADV-001; CR-SA106-002; SA110-ADV-001).

**Net.** One critical path — **SA112a → SA112b → SA112c → SA112d → SA112e → SA112f → SA96-PUBLISH (human)**. Track 3's next action is only SA112a's scoped plan review; no umbrella implementation is authorized. Track 2 is implementation-ready but validation-paused pending explicit future maintainer approval (SA115-DEC-001 step 3: **Keep unauthorized**), merge after SA112.

**Resolved decision — `SA115-DEC-001` (2026-07-26): step 3 heavy validation remains unauthorized.** The maintainer chose **Keep unauthorized** for SA115-DEC-001 step 3. All roadmap authority surfaces are updated to state consistently that SA115 heavy Docker/PostgreSQL validation is NOT authorized; Track 2 is implementation-ready but validation-paused pending explicit future maintainer approval. Steps 1 and 2 (commit and reconcile) remain **DONE** as recorded on 2026-07-25. `SA115-DEC-002` (guard vs. xdist) remains **ratified** — its implementation will ride along with the validation phase when authorized. Options 3 and 4 from the prior analysis (run validation now, or relax the merge bound and merge first) are superseded: validation cannot proceed without explicit future authorization, and the merge-order bound (merge after SA112) remains in place. See [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision) for the squash/guardrail/shrink-only-quality policies and §Bundled Module Inventory (AF7) for the fallback precedent SA113 follows; detailed history is in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
