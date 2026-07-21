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

The green-gate join (SA96-GATE) is green with empty quarantine. All remaining open work is on **Track 3 (release path)**; Tracks 1 and 2 are complete.

1. **[x] SA113** (installed-context implication-resolver fallback, Track 3) — **complete.** `resolve_module_implications` now falls back to bundled manifest snapshots when the source-tree modules path is unavailable, covering both `plan` and `apply` call sites. SA111/SA112 are now unblocked.
2. **SA111** (installed-context `plan`+implication coverage, Track 3) — regression coverage for the now-fixed crash: SA111a (authoritative `smoke-install` probe) + SA111b (optional fast monkeypatch unit test). Deps: SA113 ✓.
3. **SA112** (installed-wheel full-lifecycle e2e `plan → apply → up`, Track 3) — heavy e2e lane covering `apply`'s own resolver call site and the Docker path from a real install. Deps: SA110 ✓ + SA111a + SA113 ✓.
4. **SA96-PUBLISH** (staged PyPI publish, Track 3) — **HUMAN-ONLY**. Green-gate deps met (SA96-GATE ✓ + SA109 ✓ + SA110 ✓ + SA113 ✓); awaits a human maintainer to execute the irreversible publish. Should not publish while SA111/SA112 are open.

Arch **Finding 10** (`frontend-source-generation-specialized`) is **closed** by the SA104→SA108 chain (see arch-audit reconciliation log, 2026-07-21). Arch **Finding 7** (generated-file-ownership taxonomy derivation) stays unscheduled — the Finding 10 chain shrank its surface; sequence any tuple-derivation work after it. Arch Findings **2/4** remain **not ticketed**, deferred with the (unscheduled) teams module.

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a clean rerun at the prior synced code baseline (post-SA92 squash), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). The four-command join covers everything end to end — unit **and** integration **and** e2e. `make check` is the **fast** repo gate — `lint` + `typecheck` + `test-unit` (unit only) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (see the `check` target in `Makefile`; `make check QUIET=1` is the quiet LLM/agent variant). **Integration coverage lives in `make ci`** (unit + integration when PostgreSQL is available), and e2e in `make ci-e2e` (`.github/workflows/e2e.yml`). So `make check` alone does not prove integration — the `ci`/`ci-e2e` legs of the join do.

The join runs entirely **inside the monorepo** and does **not** exercise the pip-installed wheel — that gap was closed by SA109/SA110 (both complete; see [CHANGELOG.md](../../CHANGELOG.md)). `make smoke-install` builds wheels from per-run staged copies (no source mutation), installs into a throwaway venv outside the source tree, and runs every non-mutating CLI command from a sanitized external workdir under the full `>=3.13,<3.15` Python constraint.

### SA96-PUBLISH — Staged release ladder

- [ ] **SA96-PUBLISH — Staged release ladder.** `Tier 1 · v87 · deps: SA96-GATE ✓ + SA109 ✓ + SA110 ✓` · **HUMAN-ONLY — do not delegate to an assistant**
  Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full` for test→verify→prod in one shot). **PyPI publish is irreversible/outward-facing — a human maintainer must confirm version + green-gate status before `publish-prod`. This step is explicitly excluded from any SA93/SA96-GATE assistant handoff.**

  *(Acceptance:* all 12 modules green in isolation; SA96-GATE four-command run exits 0 with empty quarantine; SA109 ✓ and SA110 ✓ closed (installed wheel runs non-mutating commands clean); release published and verified on PyPI.*)*
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*

### Track 1 — Tenant-context surface

**COMPLETE — no open tickets.** All Track 1 work (SA92/SA84/SA86/SA96-T1, Finding 8, SA97/SA99, SA102/SA103, and the full TP test-parallelization suite SA91/TP1/TP2/TP2b/TP3a/TP3b/TP4) is closed. See [CHANGELOG.md](../../CHANGELOG.md). Off the release critical path; none of its changes regressed any gate's pass/fail set or coverage thresholds.

### Track 2 — Module contracts & settings — frontend-theme de-specialization (arch Finding 10)

**COMPLETE — no open tickets.** The frontend-theme de-specialization chain (SA104 → SA105 → SA106 → SA107 → SA108) is fully closed, retiring arch-audit Finding 10 (`frontend-source-generation-specialized`). `frontend/src` is now project-agnostic and byte-identical across projects on the same theme version, with all project/module facts flowing through the `window.__QUICKSCALE__` runtime seam; `beta-site-migration.md` has been rewritten to the copy-not-merge reality. See [CHANGELOG.md](../../CHANGELOG.md) for details. Off the SA96 release critical path; no gate or coverage threshold regressed.

### Track 3 — Core/CLI plumbing — release path

#### SA113 — Installed-context implication-resolver bundled-manifest fallback (the fix)

**Pre-fix diagnosis.** SA113 was the critical-path code change that SA111/SA112 now verify. `resolve_module_implications`
(`quickscale_core/src/quickscale_core/manifest/implications.py:52`) called
`get_modules_base_path()` with no fallback, so in an installed venv (no source
workspace) both `plan` (`plan_command.py:102`) and `apply` (`apply_command.py:973`)
crashed with `ImproperlyConfigured: Modules base path not found`. The module picker
already solved this in SA109 — the resolver now adopts the same pattern.

- [x] **SA113 — Add bundled-manifest fallback to `resolve_module_implications`.** `Tier 1 · Track 3 · deps: SA109 ✓`
  Mirror the picker's SA109 pattern (`module_catalog.get_discovered_module_names` →
  `try/except ImproperlyConfigured → get_bundled_manifests_path()`) inside
  `resolve_module_implications`, so implication resolution falls back to the bundled
  manifest snapshots (`quickscale_core/data/manifests/*/module.yml`) when the source
  workspace is absent. The fix must cover **both** call sites reached from
  `_materialize_implied_module_configs` — `plan` (`plan_command.py:102`) and `apply`
   (`apply_command.py:973`); neither had an installed-context path before the fix. Follow the
  AF7 fail-hard contract ([decisions.md §Bundled Module Inventory (AF7)](./decisions.md#af7-installed-wheel-module-discovery)):
  source-required operations stay fail-hard; only the resolvable-from-snapshot
  implication lookup gains the fallback.
  - Verify: `resolve_module_implications(["billing"])` resolves billing → orgs with
    `get_modules_base_path` unavailable; SA111a `make smoke-install` goes green (was red);
    SA111b unit test passes; no regression in the in-monorepo `plan`/`apply` paths.
  - **Findings/blockers:** None.
  *(why →* SA109 fixed discovery but left the implication resolver fallback-less; it was the sole remaining installed-wheel crash on the release path, and every coverage ticket (SA111/SA112) was red until it landed*)*

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
red until SA113 landed the resolver fix. SA113 is now closed; SA111a/SA111b remain
open as verification coverage (pending implementation).

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

- [ ] **SA111a — Installed-artifact `plan` probe with all modules (authoritative).** `Tier 2 · Track 3 · deps: SA110 ✓ · SA113 ✓`
  Extend `scripts/smoke_install.sh` (SA110 gate — builds wheels, installs into a
  throwaway venv outside the source tree, the exact crash condition) with a
  non-interactive `plan` probe that **selects all 12 modules by default** (mirroring
  the real repro `1,2,...,12` + create-superuser=y), feeding the interactive prompts
  via scripted stdin, asserting exit 0 and no traceback. Selecting all modules
  exercises the full implication graph in one shot. Update the header comment that
  currently lists `plan` among excluded commands; keep `apply` excluded (needs Docker).
  - Verify: `make smoke-install` (with the `plan` probe) will go green now that SA113's resolver fix has landed — the crash it was designed to detect is resolved. Confirms the real project-creation path end to end.
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

- [ ] **SA112 — Installed-wheel lifecycle e2e lane.** `Tier 2 · Track 3 · deps: SA110 ✓ · SA111a · SA113 ✓`
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

### Track 3 (prior) — Core/CLI plumbing — release path

**Prior Track 3 work COMPLETE.** The foundational Track 3 work is closed (arch-audit Finding 1 via SA89a+SA89b; all four GATEs; SA91 parallel worker pool; SA93 e2e in green-gate; SA100 theme preflight; SA101 quality remediation; SA96-GATE join; SA109 installed-wheel discovery fix; SA110 installed-artifact smoke gate; SA113 resolver fix). See [CHANGELOG.md](../../CHANGELOG.md). The **open** Track 3 items are SA111/SA112 (installed-context coverage gap, above) and the human-only **SA96-PUBLISH**.

The AF7 installed-wheel discovery decision is recorded in [`decisions.md`](../technical/decisions.md#af7-installed-wheel-module-discovery): discovery falls back to bundled manifest snapshots (`quickscale_core/data/manifests/*/module.yml`) when the source workspace is absent, while source-required operations (`get_modules_base_path`, `discover_shipped_module_paths`, `load_module_manifest`, `refresh_managed_adapters`) remain fail-hard.

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

Only open work is shown; all prior tickets are complete (see [CHANGELOG.md](../../CHANGELOG.md)).

```
Track 1 (complete)     Track 2 (complete)                Track 3 → release (critical path)
────────────────────   ────────────────────────────     ─────────────────────────────────
✓ all tickets closed    SA104 ✓ → SA105 ✓ → SA106 ✓       SA96-GATE ✓  SA109 ✓  SA110 ✓
                          → SA107 ✓ → SA108 ✓                │
                        (arch Finding 10 chain closed)     SA113 ✓
                                                             │
                                                       ┌─────┴──────┐
                                                    SA111a      SA111b (optional)
                                                  (smoke probe) (fast unit test)
                                                       │
                                                     SA112 ── installed-wheel plan→apply→up e2e
                                                       │
                                                       ▼
                                                  SA96-PUBLISH ── build → publish
                                                    deps: SA96-GATE ✓ + SA109 ✓ + SA110 ✓ + SA113 ✓
                                                    (human-only; hold until SA111/SA112 close)
```

**Parallelism.** All remaining work is on Track 3 and forms one coherent release unit: **SA113** (`implications.py`) has landed (bundled-manifest fallback with fail-hard inventory validation). SA111a/SA111b/SA112 are now executable — they were red until SA113 landed, and there is no remaining head-of-chain bottleneck. The only shared-closeout overlap is `CHANGELOG.md`/`roadmap.md`, covered by the Merge procedure. SA96-PUBLISH (human-only) shares no files with the assistant-executable tickets.

### Track readiness (2026-07-21)

- **Track 1 — COMPLETE (off critical path).** No open tickets.
- **Track 2 — COMPLETE.** Chain stages SA104/SA105/SA106/SA107/SA108 complete. Track 2 frontend de-specialization chain (arch Finding 10) is fully closed. Legacy compatibility finding documented: SA105 dormant-file guarantee applies only to fresh current-theme recipients; legacy pre-SA105 recipients have no retroactive dormant guarantee for any module surface — running `quickscale apply` does not guarantee or backfill blog/crm/listings; the shipped continuation adopts only missing forms/social surfaces (no blog/crm/listings backfill). No blocker.
- **Track 3 — open engineering work, unblocked and sequenced (Option A ratified).** The green-gate join, SA109, SA110, and SA113 are all closed. SA113 resolved the installed-context implication resolver crash by adding a bundled-manifest fallback with fail-hard inventory validation in `resolve_module_implications`. SA111 (coverage) and SA112 (installed-wheel lifecycle e2e) are now executable (they were red until SA113 landed). SA96-PUBLISH (human-only) holds until SA111/SA112 close. Non-gating advisories remain deferred (SA91 CR-SA91-REV-006 low; SA89B-CR-004; SA93-REV-005; SA93-ADV-001..004; SA104-ADV-001; SA105-ADV-001; CR-SA106-002; SA110-ADV-001).

**Track 3 decision — RESOLVED (2026-07-21): Option A, fix-first.** The resolver fix is ticketed as **SA113** on Track 3 and landed before its coverage; SA111a/SA111b/SA112 are now unblocked and expected to verify the landed fix. It stayed on Track 3 (not an idle Track 1/2) because it was the *head* of the dependency chain — nothing ran in parallel with it, and splitting the fix from its coverage (same resolver module, `scripts/`, e2e lane) would only have created a cross-track merge hazard. The fix follows the SA109/AF7 bundled-fallback precedent in decisions.md.

**Net.** Tracks 1 and 2 are complete. Track 3 is **not** done: the installed-wheel resolver crash reopened engineering work that SA109/SA110 did not cover. SA113 (resolver fix) is now closed; the remaining critical path is **SA111a → SA112 → SA96-PUBLISH (human)**, all on Track 3. See [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision) for the recorded squash/guardrail/shrink-only-quality policies and §Bundled Module Inventory (AF7) for the fallback precedent SA113 follows; detailed history is in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
