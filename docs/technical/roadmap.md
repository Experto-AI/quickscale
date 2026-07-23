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

The green-gate join (SA96-GATE) is green with empty quarantine. The **Track 3 (release path)** remains blocked on SA112 after a diagnostic/prototype attempt found additional correctness and planning gaps; no SA112 implementation from that attempt landed (see the blocked checkpoint below). One independent verification ticket (**SA114**) runs in parallel on the otherwise-idle **Track 1**. Track 2 is complete.

> **SA113 landed** (installed-context implication-resolver bundled-manifest fallback with fail-hard inventory validation, covering both the `plan` and `apply` call sites) and is recorded in [CHANGELOG.md](../../CHANGELOG.md); it unblocked SA111/SA112. Referenced below as `SA113 ✓`.

1. **SA111a ✓** (installed-context `plan`+implication coverage, Track 3) — authoritative `smoke-install` regression probe for the fixed crash; SA111b remains an optional, non-gating fast monkeypatch test. Deps: SA113 ✓.
2. **SA112** (installed-wheel full-lifecycle e2e `plan → apply → up`, Track 3) — heavy e2e lane covering `apply`'s own resolver call site and the Docker path from a real install. Blocked checkpoint recorded below; no implementation from the attempt landed. Deps: SA110 ✓ + SA111a ✓ + SA113 ✓.
3. **SA96-PUBLISH** (staged PyPI publish, Track 3) — **HUMAN-ONLY**. Baseline prerequisites met (SA96-GATE ✓ + SA109 ✓ + SA110 ✓ + SA111a ✓ + SA113 ✓); awaits a human maintainer to execute the irreversible publish. Hold: must not publish while SA112 remains open.
4. **SA114** (v87 gate re-verification & fix sweep, Track 1, `deps: none`) — re-run `make check`/`quality`/`ci`/`ci-e2e` on current `v87` HEAD (the green-gate join was proven at the synced baseline, not HEAD) and fix any drift. Runs in parallel with the Track 3 chain; heavy `ci`/`ci-e2e` legs serialized against Track 3's PG/Docker usage, and any fix in SA113's resolver/`scripts` surface deferred to Track 3.

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
  *(why →* the green-gate join was proven at the synced baseline, not at current HEAD; drift since then is unverified, and re-proving it is independent of the installed-context release chain — a genuine use of the idle track*)*

### Track 2 — Module contracts & settings — frontend-theme de-specialization (arch Finding 10)

**COMPLETE — no open tickets.** The frontend-theme de-specialization chain (SA104 → SA105 → SA106 → SA107 → SA108) is fully closed, retiring arch-audit Finding 10 (`frontend-source-generation-specialized`). `frontend/src` is now project-agnostic and byte-identical across projects on the same theme version, with all project/module facts flowing through the `window.__QUICKSCALE__` runtime seam; `beta-site-migration.md` has been rewritten to the copy-not-merge reality. See [CHANGELOG.md](../../CHANGELOG.md) for details. Off the SA96 release critical path; no gate or coverage threshold regressed.

### Track 3 — Core/CLI plumbing — release path

> **SA113 (installed-context implication-resolver bundled-manifest fallback) is complete** — see [CHANGELOG.md](../../CHANGELOG.md). It added the fallback (mirroring the SA109 picker pattern) to `resolve_module_implications` for both the `plan` and `apply` call sites, with a fail-hard inventory boundary, resolving the sole remaining installed-wheel crash on the release path and unblocking SA111/SA112.

#### SA111 — Installed-context `plan` + module-implication coverage gap

**Pre-SA113 diagnosis — root cause now resolved by SA113.**
Repro (installed venv, outside monorepo): `quickscale plan <name>` selecting any
module crashed with `quickscale_core.contracts.module_discovery.ImproperlyConfigured:
Modules base path not found`. Root cause: two module-discovery paths, only one
handles the installed-wheel case. The module **picker**
(`module_catalog.get_discovered_module_names`, `quickscale_core/src/quickscale_core/contracts/module_catalog.py:135`)
falls back to bundled manifests via `discover_bundled_module_names()`; the
implication **resolver** (`resolve_module_implications`,
`quickscale_core/src/quickscale_core/manifest/implications.py:52`) calls
`get_modules_base_path()` with **no** fallback. It is reached from
`_materialize_implied_module_configs` (`quickscale_cli/src/quickscale_cli/commands/plan_command.py:102`).

**Second, independent call site — `apply` is almost certainly broken the same way.**
`apply` calls the *same* fallback-less resolver at
`quickscale_cli/src/quickscale_cli/commands/apply_command.py:973`
(`resolve_module_implications(qs_config.modules.keys())`, via its own
`_materialize_implied_module_configs`). So even with a hand-written
`quickscale.yml` (no `plan` at all), `apply` will hit the identical
`ImproperlyConfigured` crash in an installed venv unless the module-wiring
override (`set_modules_base_path(project_path/modules)`) already ran — which for a
fresh project it hasn't. This is untested only because `plan` fails first. **The
resolver fix must cover both call sites**, and `apply` needs its own
installed-context coverage (see SA112).

**Why existing e2e/unit coverage misses it — the coverage axis, not the scenario.**
The `plan`-with-modules scenario *is* already tested: `test_plan_command.py`
drives `plan` selecting `1,3` (line 204) and `billing` (line 248, which implies
`orgs`, exercising `resolve_module_implications` and `_materialize_implied_module_configs`),
asserting exit 0. But **every one of those tests — and all of `make e2e`/`ci-e2e` —
runs inside the monorepo checkout**, where `get_modules_base_path()` resolves
`quickscale_modules/` on disk and the missing bundled-fallback branch is never
taken. The crash only occurs in an **installed venv** with no source workspace.
The only gate that runs an installed wheel outside the source tree is
`make smoke-install` (SA110) — and it **deliberately excludes `plan`/`apply`**.
So the gap is the installed-context axis of an already-tested scenario.

**Scope here: coverage only** — the coverage tests assert post-fix behavior and were
red until SA113 landed the resolver fix. SA113 and authoritative SA111a coverage are
now closed; SA111b remains an optional, non-gating quick-signal test.

**Coverage location decision.** The authoritative test lives in the
**installed-wheel `smoke-install` gate (SA111a)**, not in-monorepo. Rationale: a
real project is *only* ever created from an installed wheel outside the source
tree — nobody runs `quickscale plan` inside the codebase — so the installed
context is the genuine use case, not a simulation. An in-monorepo test could only
*fake* the installed context by monkeypatching `get_modules_base_path`, and that
simulation-vs-reality drift is exactly how this bug shipped past every green gate.
Cost tradeoff accepted: `smoke-install` is slower (it builds 3 wheels + a
throwaway venv before probing), but it is the only environment that actually
reproduces the crash. SA111b (fast in-monorepo monkeypatch test) is **optional**
quick-signal only — not required, since it cannot prove the real path.

- [x] **SA111a — Installed-artifact `plan` probe with all modules (authoritative).** `Tier 2 · Track 3 · deps: SA110 ✓ · SA113 ✓`
  Extend `scripts/smoke_install.sh` (SA110 gate — builds wheels, installs into a
  throwaway venv outside the source tree, the exact crash condition) with a
  non-interactive `plan` probe that **selects all 12 modules by default** (mirroring
  the real repro `1,2,...,12` + create-superuser=y), feeding the interactive prompts
  via scripted stdin, asserting exit 0 and no traceback. Selecting all modules
  exercises the full implication graph in one shot. Update the header comment that
  currently lists `plan` among excluded commands; keep `apply` excluded (needs Docker).
  - Verify: `make smoke-install` (with the `plan` probe) exercises the full real project-creation path end to end and catches remaining crashes. A second crash site was discovered during implementation — `_load_notifications_manifest` in `resolvers.py:794` also lacks a bundled-manifest fallback, hit via `sanitize_module_options("notifications", {})` → `default_notifications_module_options`. This is separate from the `resolve_module_implications` path SA113 fixed. **Fix applied:** `_load_notifications_manifest` now catches `ImproperlyConfigured` from `get_modules_base_path()` and falls back to `get_bundled_manifests_path()`, following the SA113/AF7 pattern. Two dedicated regression tests assert the fallback resolves via the bundled path for both `default_notifications_module_options` and `resolve_notifications_module_options`. Independent review approved the change after a source-contaminated `PYTHONPATH` smoke run passed all 20 probes.
  *(why →* SA110 is the only installed-context gate and it excluded `plan`, leaving the sole environment where the code actually breaks with zero gate coverage*)*

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
  - `SA112-PR-002` (high, blocking) — the remediation command registry is not yet literally executable: helper environment/path resolution, SA112-scoped documentation assertions, and exact non-mutating command argv still require one focused plan correction and review before any diagnostic phase may begin.
  - `SA112-CONT-001` (high, blocking for completion) — capture the full installed-apply traceback, identify the actual `QUICKSCALE_BILLING_ENABLED` raising frame, then plan/review the root fix. Do not choose a billing fix from the current user-facing error alone.
  - `SA112-CR-001` (high) — preserve tracking of authoritative `.quickscale/state.yml`; never ignore the whole `.quickscale/` directory.
  - `SA112-CR-002` / `SA112-CR-003` (high) — disable apply auto-start for this explicit lifecycle and make dependent phases fail fast while cleanup still runs.
  - `SA112-CR-004` (high) — align per-run project, Compose, container, port, and cleanup identities and prove interruption-safe cleanup.
  - `SA112-CR-005` (medium) — make E2E workflow triggers cover the resolver, bundled-manifest, managed-adapter, and lane dependency surfaces.
  - `SA112-CR-006` (medium) — implement tri-state staged-diff probing (`0` no changes, `1` changes, `>1`/`OSError` failure) with index restoration and caller-test parity.
  - `SA112-CR-007` (medium) — add truthful packaged-inventory fallback proof rather than claiming notifications/orgs examples cover all 12 modules.
  - `SA112-CR-008` (high) — keep roadmap/CHANGELOG evidence factual and defer completion language until installed lifecycle validation and independent review are green.

  **Decisions needed before clean continuation**
  - A human must explicitly authorize one narrowly scoped `SA112-PR-002` plan-correction/review cycle. No product implementation or diagnostic instrumentation is authorized before that plan review returns `STATUS: ok`.
  - After the runtime traceback is captured, surface a decision only if it reveals multiple contract-valid fixes with materially different compatibility consequences; otherwise use the traceback-selected technical fix.

### Track 3 (prior) — Core/CLI plumbing — release path

**Prior Track 3 work COMPLETE.** The foundational Track 3 work is closed (arch-audit Finding 1 via SA89a+SA89b; all four GATEs; SA91 parallel worker pool; SA93 e2e in green-gate; SA100 theme preflight; SA101 quality remediation; SA96-GATE join; SA109 installed-wheel discovery fix; SA110 installed-artifact smoke gate; SA113 resolver fix; SA111a installed-context plan coverage). See [CHANGELOG.md](../../CHANGELOG.md). The **open** Track 3 engineering item is SA112 (installed-wheel lifecycle coverage, above); SA111b is optional and non-gating, and **SA96-PUBLISH** remains human-only.

The AF7 installed-wheel discovery decision is recorded in [`decisions.md`](../technical/decisions.md#af7-installed-wheel-module-discovery): discovery falls back to bundled manifest snapshots (`quickscale_core/data/manifests/*/module.yml`) when the source workspace is absent, while source-required operations (`get_modules_base_path`, `discover_shipped_module_paths`, `load_module_manifest`, `refresh_managed_adapters`) remain fail-hard.

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

Only open work is shown; all prior tickets are complete (see [CHANGELOG.md](../../CHANGELOG.md)).

```
Track 1 (idle → SA114)   Track 2 (complete)              Track 3 → release (critical path)
────────────────────   ────────────────────────────     ─────────────────────────────────
SA114 (gate re-verify   SA104 ✓ → SA105 ✓ → SA106 ✓       SA96-GATE ✓  SA109 ✓  SA110 ✓
  & fix; deps: none)      → SA107 ✓ → SA108 ✓                │
  ‖ parallel, heavy                                          │
  legs serialized                                            │
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

### Track readiness (updated 2026-07-23)

- **Track 1 — one open ticket (SA114), off the critical path.** All prior Track 1 work is closed; SA114 (v87 gate re-verification & fix sweep, `deps: none`) is parked here to use the idle track in parallel with the Track 3 chain, with heavy `ci`/`ci-e2e` legs serialized against Track 3's PG/Docker usage and SA113-surface fixes deferred to Track 3. Clean to start.
- **Track 2 — COMPLETE.** Chain stages SA104/SA105/SA106/SA107/SA108 complete. Track 2 frontend de-specialization chain (arch Finding 10) is fully closed. Legacy compatibility finding documented: SA105 dormant-file guarantee applies only to fresh current-theme recipients; legacy pre-SA105 recipients have no retroactive dormant guarantee for any module surface — running `quickscale apply` does not guarantee or backfill blog/crm/listings; the shipped continuation adopts only missing forms/social surfaces (no blog/crm/listings backfill). No blocker.
- **Track 3 — open engineering work (SA112 blocked; no implementation landed in this checkpoint).** The green-gate join, SA109, SA110, SA113, and SA111a are closed. SA113 resolved the installed-context implication resolver crash, and SA111a proves installed-wheel `plan` coverage with all 12 modules. SA111b remains optional and non-gating. **SA112** is blocked first on plan finding `SA112-PR-002`, then on a traceback-selected resolution of `SA112-CONT-001` and review findings `SA112-CR-001..008`; see the SA112 block for the exact continuation ledger. SA96-PUBLISH (human-only) holds until SA112 closes. Non-gating advisories remain deferred (SA91 CR-SA91-REV-006 low; SA89B-CR-004; SA93-REV-005; SA93-ADV-001..004; SA104-ADV-001; SA105-ADV-001; CR-SA106-002; SA110-ADV-001).

**Track 3 decision — RESOLVED (2026-07-21): Option A, fix-first.** The resolver fix was ticketed as **SA113** on Track 3 and landed before its coverage; SA111a then verified the installed `plan` path, making SA112 dependency-unblocked at that point. SA111b remains optional. SA112 is now checkpoint-blocked on `SA112-PR-002`, followed by `SA112-CONT-001` and `SA112-CR-001..008`, as recorded above. The resolver work stayed on Track 3 (not an idle Track 1/2) because it was the *head* of the dependency chain — nothing ran in parallel with it, and splitting the fix from its coverage (same resolver module, `scripts/`, e2e lane) would only have created a cross-track merge hazard. The fix follows the SA109/AF7 bundled-fallback precedent in decisions.md.

**Net.** Track 1 has one independent off-path ticket (SA114, gate re-verification). Track 2 is complete. Track 3 is **not** done: SA113 and SA111a are closed, and the remaining critical path is **SA112 → SA96-PUBLISH (human)**, with optional SA111b off-path and SA114 running in parallel on Track 1. See [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision) for the recorded squash/guardrail/shrink-only-quality policies and §Bundled Module Inventory (AF7) for the fallback precedent SA113 follows; detailed history is in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
