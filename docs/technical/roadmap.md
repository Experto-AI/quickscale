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

The green-gate join (SA96-GATE), the installed-wheel discovery/resolver chain (SA109 ✓, SA110 ✓, SA113 ✓, SA111a ✓, SA111b ✓), and the Track 2 frontend de-specialization chain (SA104 → SA108 ✓) are closed; detail lives in [CHANGELOG.md](../../CHANGELOG.md). Five items remain open.

1. **SA112** (installed-wheel full-lifecycle e2e `plan → apply → up`, Track 3) — heavy e2e lane covering `apply`'s own resolver call site and the Docker path from a real install. **Critical path.** Pre-diagnostic: gated on one focused plan review of the maintainer-supplied continuation artifact (sections A–E below). Deps: SA110 ✓ + SA111a ✓ + SA113 ✓.
2. **SA96-PUBLISH** (staged PyPI publish, Track 3) — **HUMAN-ONLY**. Baseline prerequisites met (SA96-GATE ✓ + SA109 ✓ + SA110 ✓ + SA111a ✓ + SA113 ✓); awaits a human maintainer to execute the irreversible publish. Hold: must not publish while SA112 remains open.
3. **SA114** (v87 gate re-verification & fix sweep, Track 1, `deps: none`) — ordered gates are green and no source fix was required; SA114-CR-001's documentation half is reconciled. Remaining work is one full-scope re-review, **authorized under `SA114-DEC-002`** — clean to continue.
4. **SA116** (policy-compliant `resolvers.py` line reduction, Track 1, `deps: none`) — implementation and source review complete; remains unchecked because it closes with SA114.
5. **SA115** (E2E in-lane parallelization, Track 2, `deps: none` · **merge after SA112**) — `pytest-xdist` in-lane fan-out for the e2e suite. Implementation committed and reconciled with current `v87`; heavy validation is the next action and needs no SA112 dependency. Only the merge is order-gated.

Arch **Finding 7** (generated-file-ownership taxonomy derivation) stays **unscheduled** — gated on a third consumer or a public "update my generated project" command. Arch Findings **2/4** remain **not ticketed**, deferred with the (unscheduled) teams module. Both audits ([arch-audit.md](../others/arch-audit.md), [tech-audit.md](../others/tech-audit.md)) otherwise stand at zero open findings.

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a clean rerun at current `v87` HEAD (last proven green by SA114 on 2026-07-25), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). The four-command join covers everything end to end — unit **and** integration **and** e2e. `make check` is the **fast** repo gate — `lint` + `typecheck` + `test-unit` (unit only) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (see the `check` target in `Makefile`; `make check QUIET=1` is the quiet LLM/agent variant). **Integration coverage lives in `make ci`** (unit + integration when PostgreSQL is available), and e2e in `make ci-e2e` (`.github/workflows/e2e.yml`). So `make check` alone does not prove integration — the `ci`/`ci-e2e` legs of the join do.

The join runs entirely **inside the monorepo** and does **not** exercise the pip-installed wheel — that gap was closed by SA109/SA110 (both complete; see [CHANGELOG.md](../../CHANGELOG.md)). `make smoke-install` builds wheels from per-run staged copies (no source mutation), installs into a throwaway venv outside the source tree, and runs every non-mutating CLI command from a sanitized external workdir under the full `>=3.13,<3.15` Python constraint.

### SA96-PUBLISH — Staged release ladder

- [ ] **SA96-PUBLISH — Staged release ladder.** `Tier 1 · v87 · deps: SA96-GATE ✓ + SA109 ✓ + SA110 ✓ + SA111a ✓ + SA113 ✓` · **HUMAN-ONLY — do not delegate to an assistant**
  Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full` for test→verify→prod in one shot). **PyPI publish is irreversible/outward-facing — a human maintainer must confirm version + green-gate status before `publish-prod`. This step is explicitly excluded from any SA93/SA96-GATE assistant handoff.**

  *(Acceptance:* all 12 modules green in isolation; SA96-GATE four-command run exits 0 with empty quarantine; SA109 ✓ and SA110 ✓ closed (installed wheel runs non-mutating commands clean); SA113 ✓ closed (resolver fix landed); SA111a ✓ and SA112 closed (optional SA111b is non-gating); release published and verified on PyPI.*)*
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*

### Track 1 — Tenant-context surface — CLEAN TO CONTINUE (re-review authorized)

**All Track 1 source work is complete.** SA114's ordered validation chain is green and SA116's compaction landed. Both tasks remain open only because SA114-CR-001 closes on a full-scope independent review; its documentation-consistency half was reconciled on 2026-07-25. See [CHANGELOG.md](../../CHANGELOG.md).

#### SA114 — v87 gate re-verification & fix sweep

SA96-GATE proved the four-command join green at the post-SA92 synced baseline; commits landed afterwards (SA108/roadmap docs, the `d5d25c08` generator `poetry lock` timeout fix, merges), so this ticket re-verified the gates against current `v87` HEAD and fixed any drift. **That re-verification is done** — the ordered chain exited 0 on 2026-07-25 and required no source fix (evidence below). The ticket stays open only for its closing review.

- [ ] **SA114 — Re-run the make gates on current `v87` HEAD and fix drift.** `Tier 2 · Track 1 · deps: none`
  **Recorded partial delivery (2026-07-25; gates green, closing review authorized and pending).**
  - **Done:** The exact ordered chain `make check && make quality && make ci && make ci-e2e` exited 0 from a clean wt-track1 synced to latest `v87`: QUARANTINE_TICKETS empty, core+CLI equal-weight coverage 92.88%, integration module mean 94.41%, Core E2E 35 passed, CLI E2E 29 passed. SA114-ORDER-001 is satisfied and no source fix was required. Non-gating Django/pytest warnings were observed without assigned ticket IDs.
  - **Pending / blocking:** `SA114-CR-001` (medium, blocking, consistency). The two same-fact scheduling sites the final review named — the open-only dependency diagram still carrying completed Track 1/Track 2 rows, and SA115 scheduling/infra prose treating SA114's heavy legs as future work — were **reconciled in the 2026-07-25 roadmap cleanup pass** (diagram, SA115 concurrency bound, parallelism bullets, track-readiness bullets). A follow-up deep-review pass the same day found and fixed **three further sites of the same class** that the first pass missed: this ticket's own intro paragraph (still asserting "the gates have not been re-run against current `v87` HEAD"), the SA116 problem statement (present-tense "so `make quality` exits 2"), and the SA115 "parked checkpoint" label after the work was committed. Treat the site list as evidence that this defect class recurs under compaction, not as a closed inventory — the reviewer should re-sweep rather than trust it. What remains is the review half: CR-001 closes only on a full-scope independent review returning `STATUS: ok`. This checkpoint is not a waiver.
  - **Decisions needed:** none — resolved. **The maintainer authorized a scoped re-review on 2026-07-25** (`SA114-DEC-002`). See the handoff block below; a continuation may act on this authorization without re-asking.

  **Authorized continuation — SA114/SA116 scoped re-review (`SA114-DEC-002`, 2026-07-25).**

  This is a standing authorization for the next Track 1 executor. Scope is **review only — no source work is authorized.** If the review surfaces a defect requiring a source change, stop and report rather than fixing under this authorization.

  1. Start from a clean Track 1 worktree synced to latest `v87` (Start procedure above).
  2. Submit **one** independent full-scope change review covering both tickets:
     - **SA116 source:** `git show a58f07e0 -- quickscale_core/src/quickscale_core/contracts/resolvers.py` — confirm the 1761→1749 reduction is comment/docstring-only and behavior-preserving (no executable statement, public symbol, signature, default, or branch altered; no load-bearing comment lost). **Pre-identified judgement call:** the diff is 2 insertions / 14 deletions and is verifiably comment/docstring-only, but it removes a `SA5.1` ticket-provenance reference, the "delegates to the manifest-driven pipeline instead of the legacy imperative derivation schema" rationale, and the "behaviour is identical — the flat-dict contract expected by CLI callers is preserved" note. The reviewer must rule on whether losing that provenance/rationale degrades the file or is acceptable compaction. Confirm `scripts/quality_baseline.json`'s resolvers.py entries were **not** loosened (shrink-only policy, decisions.md §5).
     - **SA114 evidence:** no source fix was required, so the review assesses whether the recorded 2026-07-25 ordered-chain evidence is sufficient to close (chain exited 0; QUARANTINE_TICKETS empty; coverage 92.88% / 94.41%; Core E2E 35, CLI E2E 29).
     - **`SA114-CR-001` closure:** confirm `docs/technical/roadmap.md` is internally self-consistent — the dependency diagram shows only open work as its caption claims; no prose describes completed work as pending; the "Open work" list, ticket blocks, diagram, track-readiness bullets, and parallelism bullets agree; and `CHANGELOG.md` claims nothing complete that the roadmap calls pending, or vice versa.
  3. **Do not re-run the gates.** The 2026-07-25 chain is the accepted evidence; re-running `make ci-e2e` would contend for the Docker/PostgreSQL the critical path needs. If the reviewer judges a rerun genuinely necessary, surface that as a finding rather than running it.
  4. On `STATUS: ok`: mark SA114 and SA116 `[x]`, move both to [CHANGELOG.md](../../CHANGELOG.md), delete their blocks from this file, and drop Track 1 from the diagram and track-readiness list.
  5. On anything less than `STATUS: ok`: record the findings here and stop. Track 1 is off the critical path, so it must never be closed on a waiver.

#### SA116 — Policy-compliant `resolvers.py` line reduction (unblocks SA114 four-gate reclose)

Cross-track growth had left `quickscale_core/src/quickscale_core/contracts/resolvers.py` at 1761 lines against its checked-in 1749-line maximum in `scripts/quality_baseline.json`, so `make quality` exited 2 (`SA114-QUALITY-001`). Under the shrink-only quality-maxima policy (decisions.md §5) the only compliant fix was a behavior-preserving reduction; raising the baseline was not authorized. Assigned here by `SA114-DEC-001` (2026-07-23). **Resolved:** the file is now 1749 lines and `make quality` exits 0.

- [ ] **SA116 — Reduce `contracts/resolvers.py` to ≤1749 lines, behavior-preserving.** `Tier 1 · Track 1 · deps: none`
  Compaction landed and is recorded in [CHANGELOG.md](../../CHANGELOG.md): 1761→1749 lines, comment/docstring-only, public API and resolver behavior preserved, `scripts/quality_baseline.json` unchanged at `max_lines` 1749, `make quality` exit 0, independent source review `STATUS: ok` with no findings. No further SA116 source work exists; it remains unchecked because it closes with SA114 after SA114-CR-001 is resolved and full-scope review returns `STATUS: ok`.
  *(why →* shrink-only policy-compliant reduction; dedicated idle-Track-1 ticket resolved `SA114-QUALITY-001` and kept Track 3 on the critical path*)*

### Track 2 — Module contracts & settings — frontend-theme de-specialization (arch Finding 10)

**Feature chain COMPLETE** (SA104 → SA108; arch-audit Finding 10 retired). Detail in [CHANGELOG.md](../../CHANGELOG.md). One independent test-infra ticket (**SA115**) sits on this otherwise-idle track — implemented and reconciled with `v87`, awaiting heavy validation.

#### SA115 — E2E in-lane parallelization (pytest-xdist)

`make ci-e2e` is the longest quality check in the SDLC. It runs the full 12-stage local CI (`scripts/check_ci_locally.sh --e2e`), whose final stage is `scripts/test_e2e.sh`. That script already runs the **Core** and **CLI** e2e lanes concurrently (`QS_E2E_PARALLEL=1`), each in its own Docker Compose project / container prefix / dynamic host port — **but within each lane the ~40–60 `@pytest.mark.e2e` tests run serially** (the pytest invocation has no `-n`). Because each test generates a full Django project, runs `poetry install`, builds, and drives Playwright/Chromium, that serial in-lane run is the dominant cost, and the total is gated by whichever single lane is slowest. Adding in-lane `pytest-xdist` fan-out is the highest-leverage remaining speedup.

Most groundwork already exists and is xdist-aware: `pytest-xdist ^3.8.0` is already a dependency (used for unit tests); `quickscale_core/tests/conftest.py` already isolates per worker via `_isolate_poetry_cache_per_worker()` (per-`PYTEST_XDIST_WORKER` Poetry cache) and the `per_test_db`/`unique_db_name` fixtures (unique DB per test, collision-free across workers); project generation uses per-test `tmp_path`. The **only** real blocker is that the `pytest-docker` **session-scoped** fixtures (`docker_compose_file`, `postgres_service`, conftest lines 122–157) are not xdist-safe — under `-n` each worker is its own session and would bring up the *same* Compose project (same default name, same named volume `postgres_test_data`), colliding.

**Design (ratified with maintainer):** *container-per-worker* Postgres; *scope limited to the E2E stage* (no lane rebalancing).

- [ ] **SA115 — Add in-lane pytest-xdist fan-out to the e2e suite.** `Tier 2 · Track 2 · deps: none · merge after SA112`
  > *Phases 1 and 2 below are **implemented** (see the checkpoint). Their `scripts/test_e2e.sh` line citations are pre-implementation guidance and no longer resolve — the file has since grown via the memory guard, heartbeat, provenance banner, and the SA115 merge itself. Read them as historical intent, not as current anchors.*

  1. **xdist-safe pytest-docker fixtures (container per worker).** In `quickscale_core/tests/conftest.py`, add a session-scoped override of pytest-docker's `docker_compose_project_name` that derives a **unique per-worker** Compose project name from the lane's `QS_E2E_COMPOSE_PROJECT_NAME` (exported per lane at `scripts/test_e2e.sh:225`) plus `PYTEST_XDIST_WORKER` (falls back to a single name when not under xdist). Keep the lane prefix intact so the shell's `cleanup_scoped_containers` (test_e2e.sh:163–176) still matches by `name=<prefix>` substring. Docker Compose auto-prefixes the named volume with the project name, so `docker-compose.test.yml` needs **no change** (port already dynamic). Confirm whether `quickscale_cli/tests/` defines its own docker fixtures and mirror the override there.
  2. **Configurable worker count.** In `scripts/test_e2e.sh`, extend the `pytest_cmd` builder (~line 265) to append `-n <workers> --dist loadscope`, driven by a new `QS_E2E_XDIST_WORKERS` env var. Default to a small `nproc`/RAM-derived cap (mirror the Makefile's existing `PYTEST_XDIST_WORKERS` heuristic — **not** `auto`, since each worker now runs a full Postgres container + Chromium and is memory-heavy). `QS_E2E_XDIST_WORKERS=1` (or `0`) must degrade to today's serial no-`-n` path (debugging escape hatch, mirroring `QS_E2E_PARALLEL=0`). Document the var in the script `--help` and `# Environment:` header. Surface the chosen worker count in the lane banner (near test_e2e.sh:251–253). Keep the two lanes concurrent → total load is `2 lanes × N workers`; pick the default with combined RAM/container budget in mind.
  - **Concurrency bound (infra):** shares the live PostgreSQL/Docker + ports with SA112's installed-wheel e2e — **serialize** heavy runs across worktrees (per-lane knobs namespace lanes *within* one invocation, not across worktrees). SA114's heavy legs already ran to completion on 2026-07-25 and no longer contend for this infra.
  - **Merge-order bound (hazard — re-examined 2026-07-25, weaker than originally assumed):** the bound was set assuming SA112 also edits `scripts/test_e2e.sh` / `.github/workflows/e2e.yml`. In fact `scripts/test_e2e.sh:439` already points the CLI lane at `$CLI_DIR/tests/`, so SA112's lifecycle module is collected with no runner edit (its artifact §E: "confirm, add nothing if so"), and SA112's `e2e.yml` change is an append to `pull_request.paths`, which SA115 does not touch — expected executable overlap is **empty**. The bound is **retained** only because SA112's §C root fix is still unknown pending the traceback, and any rebase burden must not land on the critical path. **Land SA115 after SA112**; shared-closeout overlap (`CHANGELOG.md`/`roadmap.md`) is covered by the Merge procedure. See `SA115-DEC-001`.
  - Verify: the `SA115-DEC-002` clamp — a fired memory guard yields serial lanes **and** serial workers (including when an explicit `QS_E2E_XDIST_WORKERS=N` is overridden, with a visible message), while `QS_E2E_NO_MEMORY_GUARD=1` preserves the requested count; baseline `time QS_E2E_XDIST_WORKERS=1 ./scripts/test_e2e.sh` vs. parallel default is faster with all e2e tests green; `docker ps` mid-run shows one Postgres container per active worker with distinct project names/ports; back-to-back runs leave no leftover containers/volumes (`docker volume ls | grep postgres_test_data`); `QS_E2E_XDIST_WORKERS=1` reproduces the old serial path; `make ci-e2e` stays green; `.github/workflows/e2e.yml` passes on the CI runner (tune default worker count to runner cores/RAM).
  *(why →* `ci-e2e` is the longest gate in the SDLC; lanes are already concurrent but each runs serially inside, and the xdist groundwork (per-worker cache + per-test DB) already exists — the sole blocker is xdist-safe pytest-docker fixtures*)*

  **Checkpoint — SA115 remains open (no longer parked; work is committed):**

  **Done (2026-07-23 implementation; committed and reconciled 2026-07-25).** Phases 1 and 2 are implemented on `wt-track2`: a worker-unique `docker_compose_project_name` fixture and the `QS_E2E_XDIST_WORKERS` runner knob. **`SA115-DEC-001` steps 1–2 are complete:** the four previously parked files are committed (`5193f198`) and `v87` is merged into `wt-track2` (`5b5de830`), so the branch is clean and current. The `scripts/test_e2e.sh` drift is reconciled — three conflicts (Environment header, `--help` list, worker-resolution vs. memory-preflight block), all additive on both sides, resolved by keeping both. Post-merge focus checks are green (combined pytest exit 0): `bash -n` clean, **31 focused tests pass — 16 fixture + 15 harness**, Ruff check/format clean. The harness count moved from the 13 recorded on 2026-07-23 to 15 because `v87` added two harness tests in the interim (the baseline on `v87` is 9; SA115 adds 6) — the earlier figure was correct when written, not an error. No container lifecycle or back-to-back teardown has been exercised yet.

  **Pending / blocking**
  - **Validation not yet run (does *not* require SA112).** Steps 1–3 below need only exclusive Docker/PostgreSQL, which is idle while SA112 sits in its plan-review gate. This is `SA115-DEC-001` step 3, still open for the maintainer to authorize:
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
  - **SA112 gates only the merge.** After SA112 lands: re-merge `v87` into `wt-track2` (should be near-empty now), confirm SA112 added nothing to `scripts/test_e2e.sh` as its artifact §E predicts, obtain independent change review (`STATUS: ok`), then mark SA115 `[x]` and add the CHANGELOG entry.
  - **No completion language or CHANGELOG entry until validation and independent review are green.**

  **Decisions needed:** one — `SA115-DEC-001` step 3 (authorize the heavy validation run in the current idle infra window; see the decision block at the end of this document). Steps 1–2 are done, and the design question `SA115-DEC-002` (guard vs. xdist) is **ratified** — its implementation rides along with the validation phase. Only the *merge* is mechanically gated by SA112; the earlier "wait for SA112, do nothing" posture was too strong.

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

  **Open state — pre-diagnostic; SA112 remains open.**

  No SA112 implementation exists on any branch: an early disposable prototype was rejected by independent review and fully reverted, and every subsequent continuation was plan-only. The prototype's one durable result is the observation the root-fix phase must chase — installed `plan` succeeded for all 12 modules, then installed `apply` failed with `NameError: name 'QUICKSCALE_BILLING_ENABLED' is not defined` during managed-wiring regeneration. Static discovery has twice found no bare-name evaluation of that symbol in the traced path (the billing adapter uses a dict access, which would raise `KeyError`), so the raising frame genuinely requires a runtime traceback. That obstacle is now removed — the `apply` wrapper prints the full traceback under `QUICKSCALE_DEBUG` (landed on `v87`; see CHANGELOG). The plan-review history is recorded in [CHANGELOG.md](../../CHANGELOG.md); all findings except the two below were resolved at plan level.

  **Pending / blocking**
  - `SA112-PR-002` (**high, blocking, completeness**) — the plan must supply a literally executable registry rather than narrative operations: exact full argv arrays, cwd and environment, stdin bytes, captures and exit handling, named helper APIs and outputs, conditional root-fix tests, cleanup behavior, and staged-file allowlist/commit sequencing (allowlist compared against post-`git add -A` cached names, or explicitly against working-tree names before staging).
  - `SA112-CR-005` (**medium, blocking, completeness**) — every workflow-trigger path entry must be expanded to its exact repository-relative GitHub Actions path string, order preserved, including `scripts/_python_requirement.sh`, with deterministic `yaml.BaseLoader` regression coverage.
  - Both are addressed at plan-detail level by the maintainer artifact below. Diagnostics and implementation remain unauthorized until one focused independent plan review of that artifact returns `STATUS: ok`. After the gate: capture the traceback, select the root fix only from the actual raising frame, implement the lane, validate, obtain independent change review, then mark SA112 complete.

  **Maintainer-supplied continuation artifact (2026-07-24) — resolves `SA112-PR-002` and `SA112-CR-005` at plan-detail level.**

  This is the authoritative literal registry the plan reviews kept asking for. It is a **specification for the next continuation**, not an implementation authorization: the next executor starts from a clean Track 3 worktree synced to latest `v87`, submits this artifact (transcribed into the plan) to **one** focused independent plan review, and proceeds to diagnostics/implementation only on `STATUS: ok`. No fourth autonomous plan rewrite.

  *A. Wheel-provision helper (reuses `smoke_install.sh` machinery — `SA112-PR-002`, named helper + outputs).*
  - **New file `scripts/_installed_wheel_venv.sh`** (sourceable library): extract, verbatim, these functions from `scripts/smoke_install.sh` — `read_version`, `python_within_spec`, `smoke_select_python`, `ensure_compatible_python_available`, `ensure_compatible_python_venv_available`, `ensure_poetry_uses_compatible_python`, `build_with_poetry`, `pip_install_isolated`, `stage_package`, `build_staged_package`. Add one public entrypoint:
    `iw_provision_installed_venv OUT_VENV_DIR` — creates its own `STAGE_DIR`/`BUILD_VENVS_DIR`/`WHEEL_COLLECT_DIR` via `mktemp -d /tmp/quickscale-iw-*-XXXXXX` (trap-cleaned on RETURN/EXIT of the helper only); stages+builds in the exact order `quickscale_core` (`"no"`) → `quickscale_cli` (`"yes"`) → `quickscale` (`"no"`); runs `"$PYTHON_BIN" -m venv "$OUT_VENV_DIR"`; installs with `pip_install_isolated "$OUT_VENV_DIR" "$WHEEL_COLLECT_DIR"/quickscale_core-*.whl "$WHEEL_COLLECT_DIR"/quickscale_cli-*.whl "$WHEEL_COLLECT_DIR"/quickscale-*.whl`; prints exactly `"$OUT_VENV_DIR/bin/quickscale"` to stdout and returns 0. **Caller owns `OUT_VENV_DIR` cleanup.** `smoke_install.sh` is refactored to `source` this library (its 20-probe behavior must be unchanged — see validation).
  - **New thin wrapper `scripts/provision_installed_venv.sh`**: `set -euo pipefail`; `source "$(dirname "$0")/_installed_wheel_venv.sh"`; `iw_provision_installed_venv "$1"`. This is the single seam the pytest fixture shells out to.

  *B. Lifecycle lane (`SA112-PR-002` — exact argv/cwd/stdin/captures/cleanup).* **New file `quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py`**, one `@pytest.mark.e2e` test, mirroring `quickscale_cli/tests/test_e2e_development_workflow.py::test_full_development_workflow` but driving the **installed** entrypoint via `subprocess.run`, never `CliRunner`/monorepo import.
  - `session`-scoped fixture `installed_quickscale`: `venv_dir = tempfile.mkdtemp(prefix="qs-iw-venv-")`; `out = subprocess.run(["bash", str(REPO_ROOT/"scripts"/"provision_installed_venv.sh"), venv_dir], check=True, text=True, capture_output=True)`; `qs = out.stdout.strip()`; `yield qs`; `shutil.rmtree(venv_dir, ignore_errors=True)`. Skip the module when Docker/compose is unavailable (reuse `ensure_docker_running` shape).
  - Per-step registry — each is `subprocess.run(argv, cwd=…, input=…, text=True, capture_output=True, env={**os.environ, "PORT": port, "QS_E2E_CONTAINER_PREFIX": prefix}, timeout=…)`; assert `returncode` as noted and `"Traceback (most recent call last)" not in (stdout+stderr)`:
    1. `plan`: `argv=[qs, "plan", "sa112proj"]`, `cwd=workdir`, `input="\n\n1,2,3,4,5,6,7,8,9,10,11,12\ny\ny\ny\ny\n"` (all 12 modules — identical stdin to `scripts/smoke_install.sh:540`), expect `returncode==0`.
    2. `apply`: `argv=[qs, "apply", "quickscale.yml"]`, `cwd=workdir/"sa112proj"`, `input="n\ny\n"` (show-docker-output=N → proceed=Y, per `test_e2e_development_workflow.py:291-292`), `env[PORT]` set, expect `returncode==0`, assert `"Running migrations (Docker)" in stdout`, `'localhost" (127.0.0.1), port 5432' not in stdout`, `"Migrations failed" not in stdout`.
    3. `ps`: `argv=[qs, "ps"]`, `cwd=proj`, expect `0`.
    4. `manage migrate`: `argv=[qs, "manage", "migrate", "--noinput"]`, `cwd=proj`, expect `0`.
    5. `down`: `argv=[qs, "down", "--volumes"]`, `cwd=proj`, expect `0` — always run in a `finally:` so a mid-test failure still tears down containers/volumes.
  - Container-prefix isolation: derive `prefix` from `QS_E2E_CONTAINER_PREFIX` exactly as `test_e2e_development_workflow.py:68-70`, so the lane's `cleanup_scoped_containers` (`scripts/test_e2e.sh:258-271`) matches it.

  *C. Runtime root-fix (`SA112` Phase 1 — pending traceback, not pre-selected).* The prior prototype's installed `apply` raised `NameError: name 'QUICKSCALE_BILLING_ENABLED' is not defined` during managed-wiring regeneration. Confirmed static finding (2026-07-24): the billing adapter (`quickscale_modules/billing/src/quickscale_modules_billing/adapter.py:35`) uses `settings["QUICKSCALE_BILLING_ENABLED"]` (dict access → `KeyError`, not `NameError`), so the bare-name evaluation is **not** in the traced managed-wiring path — matching the earlier pass that also found no bare-name site. The raising frame therefore genuinely requires a runtime traceback, which the `apply` wrapper previously discarded by collapsing to `str(exc)`. **Obstacle removed (2026-07-24, landed on `v87`):** the wrapper now prints the full traceback to stderr when `QUICKSCALE_DEBUG` is set (`apply_command.py`, `_regenerate_managed_wiring_for_apply._wiring_fn`; default behavior unchanged; see CHANGELOG). Phase-1 capture procedure is now simply: run step B.2 with `QUICKSCALE_DEBUG=1`, save the printed traceback, select the root fix **only** from the actual raising frame. Surface a decision to the maintainer only if the frame admits multiple contract-valid fixes with materially different compatibility consequences; otherwise apply the traceback-selected technical fix (expected to follow the SA109/SA113/AF7 bundled-fallback precedent).

  *D. CI trigger tuple (`SA112-CR-005` — fully expanded, ordered, exact repository-relative paths).* Append these to the `pull_request.paths` list in `.github/workflows/e2e.yml`, in this order, immediately after the existing `scripts/test_e2e_parallel.py` entry (`e2e.yml:39`):
    1. `quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py`
    2. `scripts/smoke_install.sh`
    3. `scripts/_installed_wheel_venv.sh`
    4. `scripts/provision_installed_venv.sh`
    5. `scripts/_python_requirement.sh`
  (`scripts/test_e2e.sh` at `e2e.yml:38` and `.github/workflows/e2e.yml` at `:41` already cover the runner and the workflow itself — do not duplicate.) Add a deterministic `yaml.BaseLoader` regression test (in `quickscale_core/tests/` alongside the existing workflow-contract tests) that loads `.github/workflows/e2e.yml`, reads `on.pull_request.paths`, and asserts all five strings above are present **and** that `scripts/_python_requirement.sh` appears (the CR-005-named omission), preserving relative order.

  *E. Wiring + validation order.* Wire the new lane into `scripts/test_e2e.sh`'s CLI lane (it already runs `quickscale_cli/tests/` under `-m e2e`, so the new module is collected automatically — confirm, add nothing if so). Validation sequence, in order: (1) `bash -n` on the three shell files; (2) focused `poetry run pytest` of the new lifecycle module + the yaml.BaseLoader test; (3) **`make smoke-install` exit 0** to prove the `smoke_install.sh` refactor preserved SA110's 20-probe behavior; (4) `make ci-e2e` exit 0 with quarantine empty; (5) independent full-scope change review `STATUS: ok`. Only then mark SA112 `[x]` and add the CHANGELOG entry.

  **Decisions needed:** none. Sections A–E are the maintainer-authorized specification; the next action is a fresh clean Track 3 continuation that submits the artifact to **one** focused plan review. No fourth autonomous plan rewrite; implementation and diagnostic instrumentation stay unauthorized until that review returns `STATUS: ok`.

#### Standing references

The AF7 installed-wheel discovery decision is recorded in [`decisions.md`](../technical/decisions.md#af7-installed-wheel-module-discovery): discovery falls back to bundled manifest snapshots (`quickscale_core/data/manifests/*/module.yml`) when the source workspace is absent, while source-required operations (`get_modules_base_path`, `discover_shipped_module_paths`, `load_module_manifest`, `refresh_managed_adapters`) remain fail-hard. All prior Track 3 work (arch Finding 1, the four GATEs, SA91/SA93/SA100/SA101/SA96-GATE/SA109/SA110/SA113/SA111a/SA111b) is closed in [CHANGELOG.md](../../CHANGELOG.md).

### Dependency & parallelization overview

Only open work is shown; all prior tickets are complete (see [CHANGELOG.md](../../CHANGELOG.md)).

```
Track 1 (review authorized) Track 2 (validate; merge queued)  Track 3 → release (CRITICAL PATH)
─────────────────────────   ───────────────────────────────   ─────────────────────────────────
SA114 / SA116               SA115 (e2e xdist; deps: none)     SA112 ── installed-wheel
  (source+gates done;         │                                 │        plan→apply→up e2e
   re-review authorized)      └── merge after SA112 ◄───────────┤
                                                               ▼
                                                           SA96-PUBLISH ── build → publish
                                                             (human-only; hold until SA112)
```

**Critical path:** `SA112 → SA96-PUBLISH`. That is the longest remaining dependency chain to release, and the only chain worth optimizing — SA112 is also the gate SA115 waits behind, so it is the single scheduling bottleneck in the repo.

**Parallelism.** Every open ticket already sits on a distinct track, and no rebalancing move is available that would speed the critical path:

- **SA112 cannot be split or moved.** Its remaining work is one coherent unit — plan review → traceback capture → root fix → lifecycle lane → validation — over `scripts/smoke_install.sh`, `scripts/test_e2e.sh`, and `.github/workflows/e2e.yml`. Splitting it across tracks would put the same three files on two branches, which is exactly the merge hazard the parallel-track model exists to avoid.
- **SA115 must stay on Track 2.** It edits `scripts/test_e2e.sh` (shared with SA112, hence `merge after SA112`). Moving it to Track 3 would collide with SA112 on that file; moving it to Track 1 would fold an independent test-infra change into SA114/SA116's review unit. Track 2 sitting idle is the correct outcome, not waste. (Its infra contention is now with SA112 only — SA114's heavy legs are done.)
- **SA114 and SA116 remain one review unit** on the same `contracts/resolvers.py` / gate-drift surface, and their remaining work is a single full-scope re-review — indivisible, so there is nothing to move.
- **Neither Track 1 nor Track 2 feeds the critical path.** SA114/SA116 re-proved current `v87` HEAD and now await re-review only; SA115 shortens a gate. Neither is a dependency of SA112 or SA96-PUBLISH, so moving work onto Track 3 could only slow it.

**Infra serialization (not a track constraint).** SA112's and SA115's e2e lanes (and any future `make ci`/`make ci-e2e` rerun) all need the same live PostgreSQL server, Docker daemon, and ports. The `QS_CI_PARALLEL`/`QS_E2E_PARALLEL`/per-lane-scope knobs namespace lanes *within* one invocation, not across worktrees — only one track may exercise PG/Docker at a time regardless of track assignment.

**Conflict surface.** The shared closeout files are `CHANGELOG.md` and `docs/technical/roadmap.md` (plus `docs/technical/decisions.md` when policy or acceptance evidence changes). All three are covered by the Merge procedure above: the `git merge v87` before every merge-back forces conflicts to resolve on the track branch, preserving both sides. No open ticket shares any *executable* file with a ticket on another track except SA112/SA115 on `scripts/test_e2e.sh`, which the `merge after SA112` ordering bound already serializes.

### Track readiness (2026-07-25)

- **Track 1 — CLEAN TO CONTINUE (re-review authorized; not on the critical path).** SA114's ordered chain exited 0 on 2026-07-25 (QUARANTINE_TICKETS empty, coverage 92.88%/94.41%, Core 35/CLI 29 E2E) and no source fix was required; SA116 source work is complete. `SA114-CR-001`'s documentation half is reconciled, and the remaining review half is **authorized under `SA114-DEC-002`** — a continuation can start now and needs no further decision. Handoff steps are in the `SA114-DEC-002` block under SA114.
- **Track 2 — CLEAN TO VALIDATE; merge queued behind SA112 (off the critical path).** SA115 is committed (`5193f198`) and reconciled with current `v87` (`5b5de830`) as of 2026-07-25 — `SA115-DEC-001` steps 1–2 are done, and the `scripts/test_e2e.sh` drift (memory guard, heartbeat, provenance, swap-veto correction) is resolved with post-merge focus checks green. The branch is clean, current, and ready. **Next action:** the heavy validation sequence in SA115's Pending/blocking list, which needs only the Docker/PostgreSQL that SA112's plan-review gate is currently leaving idle — no dependency on SA112. Only the *merge* is gated. Legacy compatibility finding stands: the SA105 dormant-file guarantee covers only fresh current-theme recipients; legacy pre-SA105 recipients get no retroactive dormant guarantee, and the shipped continuation adopts only missing forms/social surfaces (no blog/crm/listings backfill).
- **Track 3 — BLOCKED (process gate, on the critical path).** SA112 is pre-diagnostic behind `SA112-PR-002` (high) and `SA112-CR-005` (medium). The maintainer-supplied artifact (sections A–E) addresses both at plan-detail level. **Clean to continue:** start a fresh Track 3 worktree synced to latest `v87`, transcribe the artifact into the plan, and submit it to **one** focused plan review; on `STATUS: ok`, proceed to traceback capture and implementation. SA96-PUBLISH (human-only) holds until SA112 closes. Non-gating advisories remain deferred (SA91 CR-SA91-REV-006; SA89B-CR-004; SA93-REV-005; SA93-ADV-001..004; SA104-ADV-001; SA105-ADV-001; CR-SA106-002; SA110-ADV-001).

**Net.** One critical path — **SA112 → SA96-PUBLISH (human)** — with Track 3 clean to continue behind a single plan-review gate. All three tracks now have a next action that needs no further decision: Track 1's re-review is authorized (`SA114-DEC-002`), Track 3's plan review is specified (artifact A–E), and Track 2's owed commit-and-reconcile work is **done**, leaving heavy validation as its next action — infra-gated, not SA112-gated (`SA115-DEC-001` step 3).

**Resolved decision — `SA114-DEC-002` (2026-07-25): scoped re-review authorized.** SA114-CR-001 was a *consistency* finding, not a source defect — the gates were green and the ticket was blocked purely because the roadmap described completed work as pending. That half is reconciled; the maintainer authorized the remaining review half. The alternatives considered and rejected: deferring the re-review until SA112 lands (saves one cycle but carries two open tickets across the release gate) and leaving Track 1 parked (no closure path). The authorization fits the project's established discipline — every ticket in this cycle closed on an explicit independent `STATUS: ok`, and the recorded checkpoints repeatedly state they are "not a waiver" — and is off the critical path, so it cannot delay SA112. **Executable handoff: see the `SA114-DEC-002` block under SA114.**

**Open decision — `SA115-DEC-001`: how far to unblock Track 2.** The `merge after SA112` bound was set when SA112's runner footprint was unknown. Re-examined on 2026-07-25, the premise is largely falsified: `scripts/test_e2e.sh:439` already points the CLI lane at `$CLI_DIR/tests/`, so SA112's new lifecycle module is collected with **no runner edit** (its own artifact §E says "confirm, add nothing if so"), and SA112's `.github/workflows/e2e.yml` change is an append to `pull_request.paths` — a file SA115 does not touch. The expected executable overlap is therefore **empty**, not the shared-surface collision originally assumed. Four graduated steps, the first two carrying no downside:

1. ~~**Commit the parked work on `wt-track2`.**~~ **DONE 2026-07-25** (`5193f198`). The four files are committed; the branch is no longer one `git checkout` from losing the work.
2. ~~**Reconcile against current `v87`.**~~ **DONE 2026-07-25** (`5b5de830`). Three additive conflicts in `scripts/test_e2e.sh` resolved keeping both sides; `bash -n`, 31 focused tests, and Ruff all green afterwards. The eventual post-SA112 merge should now be near-empty.
**Ratified within Track 2 — `SA115-DEC-002` (2026-07-25): on low memory, the guard clamps xdist workers to serial.** The guard and the worker knob were two independent throttles that multiply (`lanes × workers`), so a guard-demoted run was still fanning out and could exceed the load the guard existed to prevent. The guard now wins; the existing `QS_E2E_NO_MEMORY_GUARD=1` remains the single opt-out. Spec and rationale are in the SA115 Pending/blocking list. Alternatives rejected: leaving the knobs orthogonal (keeps a guard advertising protection it does not deliver) and proportional scaling (two interacting heuristics are harder to predict and debug than one conservative rule). This is implementation work, so it lands as part of SA115's validation phase, not before it.

3. **Run SA115's heavy validation in the current idle infra window (OPEN — next action).** SA112 is sitting in a *plan-review* gate, which consumes zero Docker/PostgreSQL — so the infra the two tickets contend for is idle right now. Running the serial-vs-parallel baseline, container-isolation checks, and `make ci-e2e` now is free parallelism, and steps 1–2 have left the branch ready for exactly this. Cost: if SA112's plan review returns `STATUS: ok` mid-run, Track 3 waits for the infra — bounded, since SA112's next step is a fast traceback capture. See the SA115 Pending/blocking list for the concrete sequence.
4. **Relax the merge-order bound and let SA115 merge first (decision — not recommended).** Justified by the empty-overlap finding, and it would close Track 2 outright. But SA112's §C root fix is still unknown pending the traceback; if it does touch the runner, the rebase burden lands on **the critical path**, which is the one place this project has consistently refused to put it. Keeping the bound costs Track 2 nothing once steps 1–3 are done — the work would be complete, validated, and merely queued.

**Recommendation:** do 1–3, keep the bound (skip 4). That converts Track 2 from "blocked and rotting" to "done, validated, queued behind SA112" without touching the critical path. Steps 1 and 2 need no decision; they are owed work being deferred for no reason. See [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision) for the squash/guardrail/shrink-only-quality policies and §Bundled Module Inventory (AF7) for the fallback precedent SA113 follows; detailed history is in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
