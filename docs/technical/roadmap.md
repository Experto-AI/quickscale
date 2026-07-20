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

> Completed work lives in [CHANGELOG.md](../../CHANGELOG.md). This section holds only active and blocked work.

**Integration baseline (SA82).** The SA82 unquarantined `make test-integration` gate is green with all per-module restricted-role gates closed. See [CHANGELOG.md](../../CHANGELOG.md).

**Open workstreams before release:**
1. **SA96-GATE** (green-gate join, Track 3) — **complete**. All deps met (SA96-T1/T2, SA93, SA103, SA101) and both blockers cleared. The four-command join passed — see [CHANGELOG.md](../../CHANGELOG.md).
2. **Installed-wheel release blockers (Track 3, critical path — new)** — **SA109** (fix installed-wheel module discovery) → **SA110** (installed-artifact smoke gate). The green-gate runs inside the monorepo, so it never exercised the pip-installed layout; `make install` currently produces a `quickscale` that crashes on *every* invocation (including `--version`) because module discovery hard-requires the maintainer `quickscale_modules/` tree. Both are hard prerequisites of SA96-PUBLISH — publishing a wheel that crashes on import is worse than not publishing.
3. **SA96-PUBLISH** (staged PyPI publish, human-only), deps on SA96-GATE **+ SA109 + SA110**.
4. **Frontend-theme de-specialization (arch-audit Finding 10, Track 2)** — staged chain **SA104 ✓ → SA105 ✓ → SA106 ✓ → SA107/SA108**. SA104 (stage 1) is complete; **SA105** (module de-spec) is complete (see [CHANGELOG.md](../../CHANGELOG.md) for validation and review evidence); **SA106** (identity de-spec) is complete. The chain closes with **SA107** (fail-hard validation on the now load-bearing `window.__QUICKSCALE__` seam) and **SA108** (in-chain rewrite of `beta-site-migration.md` to the copy-not-merge reality). Off the release critical path. Arch **Finding 7** stays unscheduled (SA104 shrank its surface — sequence any tuple-derivation work after it); arch Findings **2/4** remain **not ticketed** with the (unscheduled) teams module.
5. **Track 1 test-parallelization** — **TP4** (docs-only AI fast-loop recipes) is **complete** (see [CHANGELOG.md](../../CHANGELOG.md)); no open TP tickets remain. Off the release critical path.

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a clean rerun at the prior synced code baseline (post-SA92 squash), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). `make check` is the umbrella gate — `lint` + `typecheck` + `test` (unit + integration) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (see the `check` target in `Makefile`). `make check` keeps its `-m "not e2e"` scoping; e2e runs in its own lane (`make test-e2e` / `make ci-e2e`, `.github/workflows/e2e.yml`) and is now part of "done" via SA93.

**Only the integration suite shards by module — and now runs in parallel** (SA91). `scripts/test_integration.sh` parallelizes module test runs through a configurable worker pool (QS_INTEGRATION_JOBS), with per-worker coverage-file isolation, deterministic replay order, and joined exit codes. Each worker runs one pytest stage per module with per-file 80% / mean 90% coverage floors. `lint`, `typecheck`, and the `check-*` gates are repo-global — they do not parallelize per module. A single module runs in isolation via `make MODULE=<name> test -- --modules`.

#### Per-module test gates and repo-global gates — CLOSED

All per-module restricted-role gates (CRM/SA84, blog/SA83+SA95, forms/SA85, listings/SA86, orgs/SA77, notifications/SA79) and repo-global gates (GATE-lint, GATE-typecheck, GATE-check-suite, GATE-quality, SA91 parallel worker pool), including **SA93** (e2e in the green-gate), are **complete** — see [CHANGELOG.md §SA93 continuation](../../CHANGELOG.md#sa93-continuation) for the local `make ci-e2e` gate and the verified hosted evidence (SA93-EVID-001). Both former cross-track prerequisites (SA84 CRM, SA95 blog) are met. Non-gating advisories SA93-REV-005 and SA93-ADV-001..004 remain deferred (tracked in the Track 3 readiness bullet).

### Pre-publish verification & release sweep (SA96)

Pre-release re-verification: **SA96-T1 (Track 1) and SA96-T2 (Track 2) module sweeps are complete** — all 12 modules re-verified green in isolation on post-SA92 v87, no regression, empty quarantine. **SA93 and SA96-GATE are complete; the remaining release-path steps are SA109 → SA110 (installed-wheel fix + smoke gate, assistant-executable) → SA96-PUBLISH (human-only).** See [CHANGELOG.md](../../CHANGELOG.md).

**SA96-GATE (green-gate join) is complete** — all four commands (`make check`/`quality`/`ci`/`ci-e2e`) exited 0 on a clean rerun with empty quarantine; detail in [CHANGELOG.md](../../CHANGELOG.md). Note the join runs entirely inside the monorepo and does **not** exercise the pip-installed wheel — that gap is now ticketed as **SA109/SA110** (see Track 3), which must close before the human-only **SA96-PUBLISH**.

- [ ] **SA96-PUBLISH — Staged release ladder.** `Tier 1 · v87 · deps: SA96-GATE + SA109 + SA110` · **HUMAN-ONLY — do not delegate to an assistant**
  Only after SA96-GATE passes **and the installed-wheel blockers SA109/SA110 are closed**. Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full` for test→verify→prod in one shot). **PyPI publish is irreversible/outward-facing — a human maintainer must confirm version + green-gate status before `publish-prod`. This step is explicitly excluded from any SA93/SA96-GATE assistant handoff.**

  *(Acceptance:* all 12 modules green in isolation; SA96-GATE four-command run exits 0 with empty quarantine; SA109/SA110 closed (installed wheel runs non-mutating commands clean); release published and verified on PyPI.*)*
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*

### Track 1 — Tenant-context surface — TP (test-parallelization) suite

Prior Track 1 tickets are closed — SA92, SA84, SA86, SA96-T1, Finding 8, the audit-remediation tickets SA97/SA99, the CI-gate tickets SA102/SA103 (rebalanced here from Track 3), and the test-parallelization suite SA91/TP1/TP2/TP2b (the E2E sub-chain TP3a/TP3b was rebalanced to Track 2). See [CHANGELOG.md](../../CHANGELOG.md).

Track 1 carried the tail of the **TP (test-parallelization)** suite — the goal was to shorten the SDLC feedback loop (and let an AI assistant run partial tests concurrently) by parallelizing the long-running quality gates. The suite is now **complete** with the landing of **TP4** (docs-only AI fast-loop recipes). All TP tickets (TP1, TP2, TP2b, TP3a, TP3b, TP4) are closed — see [CHANGELOG.md](../../CHANGELOG.md). Track 1 has no remaining open tickets.

### Track 2 — Module contracts & settings — frontend-theme de-specialization (arch Finding 10)

Prior Track 2 tickets are closed — SA88b, SA86, SA94, SA95, GATE-lint/typecheck/check-suite, SA96-T2, SA98 (SA97+SA98 close arch-audit **Finding 9**), and the E2E-concurrency sub-chain TP3a→TP3b (rebalanced off Track 1). See [CHANGELOG.md](../../CHANGELOG.md).

#### Frontend-theme de-specialization (arch-audit Finding 10 — SA105/SA106, downstream of the complete SA104)

The 2026-07-19 arch pass promoted **Finding 10** (`frontend-source-generation-specialized`) to the top-ranked finding: the `showcase_react` theme bakes project identity and the module universe into user-editable frontend *source* at generation time, duplicating facts the `window.__QUICKSCALE__` runtime config seam already delivers per request — so every generated frontend is a unique source tree, migration is a per-file merge instead of a copy, and every frontend-visible module adds an entry to ≥5 hand-synced stations (billing shipped flag-only to skip the tax). This is the frontend counterpart to Track 2's SA94 react-only work, so it lands here. The recommended fix is **Option 1, staged** — extend the existing `window.__QUICKSCALE__` seam and the generator's existing verbatim-copy path (`_theme_non_jinja_emitted_paths`), adding no second injection mechanism. **SA104 (stage 1) is complete**; SA105 stage 2a is complete (review STATUS ok), SA106 stage 2b is complete (identity de-spec), and SA107/SA108 close the chain. Off the SA96 release critical path; must not regress any gate or coverage threshold. **File ownership:** this workstream owns the `quickscale_core` generator + `showcase_react` template tree, with SA108 additionally owning `docs/planning/beta-site-migration.md` — no overlap with the CI/Makefile surfaces SA102/SA103 touch, so it runs fully in parallel with Tracks 1 and 3.

> **SA104 (stage 1, byte-static source move) is complete** — 57 files converted onto the verbatim-copy path, SA90-fixture-verified, review STATUS ok. It unblocked SA105/SA106. See [CHANGELOG.md](../../CHANGELOG.md). The residual **advisory SA104-ADV-001** (generated projects' `.pre-commit-config.yaml.j2:10` still runs strict `check-json` against emitted JSONC `frontend/tsconfig.json`) is a non-blocking deferred follow-up — fixing it changes generated output and fixture hashes.

> **SA105 (stage 2a, module-availability de-specialization) is complete** — module surfaces are React.lazy/Suspense with fail-closed `window.__QUICKSCALE__` flag checks, the full module universe is always emitted, and all 10 dormant surfaces carry static byte-identical banners; independent change-review STATUS ok. See [CHANGELOG.md](../../CHANGELOG.md). It unblocked SA106/SA108. The residual **advisory SA105-ADV-001** (non-blocking) remains — `.venv` fixture records symmetrically excluded from parity.

- [x] **SA106 — Stage 2b: de-specialize project identity via runtime config.** `Tier 2 · Track 2 · deps: SA104 ✓ · assistant-executable · complete`
  Replace generation-baked project identity in frontend source with reads from the existing runtime seam: `Sidebar.tsx`/`Dashboard.tsx` "Welcome to {{ project_name }}" JSX → `window.__QUICKSCALE__.projectName` (already injected at `templates/index.html.j2:14-15`); confine remaining Jinja specialization to the Django-side templates. After this, `frontend/src` is project-agnostic and byte-identical across projects on the same theme version, so migration becomes "copy user-owned dirs, rebuild."
  - SA105 is now complete (review STATUS ok); SA106 deps remain SA104 ✓ only — SA106 touched `useModules`/`Dashboard`/`Sidebar` (identity de-spec); SA105 touched module surfaces (`main.tsx`, `App.tsx`, `App.test.tsx`, `PublicSocialPages.test.tsx`).
  - Verify: two-project `frontend/src` diff shows zero identity-bearing differences; generated project renders the correct project name from runtime config; boot smoke + SA103 gate green.
  *(why →* arch-audit Finding 10 stage 2, identity half — stop double-encoding `projectName` in source*)*

- [ ] **SA107 — Fail-hard validation on the `window.__QUICKSCALE__` runtime seam.** `Tier 2 · Track 2 · deps: SA105 ✓ + SA106 · assistant-executable`
  Now that route selection and project identity read from `window.__QUICKSCALE__` at runtime (SA105/SA106), correctness depends on that config being present and well-formed — the failure mode shifts from build-time to runtime. Add an explicit fail-hard guard at seam read time: assert `window.__QUICKSCALE__` exists and carries the expected shape (module flags object, `projectName`) before any route-decision or identity read consumes it; on a missing/malformed seam, fail loudly (throw at boot) rather than silently defaulting flags to `false` or rendering a blank identity. Consistent with the project's fail-hard policy — no silent fallback/coercion (see [tech-audit.md](../others/tech-audit.md)).
  - Trace every render path that can reach a seam read (initial HTML, SPA route change, error/404 pages) and confirm the seam cannot be `undefined` at read time; if any path can, that path is the bug SA107 must close.
  - Verify: a project booted with a stripped/malformed `window.__QUICKSCALE__` fails hard with a clear diagnostic (not a silent blank/disabled UI); SA103 gate + boot smoke green with a well-formed seam.
  *(why →* SA105/SA106 make the runtime seam load-bearing for correctness, not just display; the fail-hard audit policy forbids silent-fallback on a load-bearing seam*)*

- [ ] **SA108 — Rewrite `beta-site-migration.md` as part of this chain (not deferred).** `Tier 2 · Track 2 · deps: SA105 ✓ + SA106 (+ SA107 if landed) · docs-only`
  Finding 10 collapses migration from a per-file merge into "copy user-owned dirs, rebuild" — but that win is only realized when the playbook stops describing the old merge process. `docs/planning/beta-site-migration.md` is the artifact most invalidated by SA105/SA106: its identity-fix step (Step 1 `useModules.ts`/`projectName`, `Sidebar`/`Dashboard` transplant), `main.tsx`-conditional patching, per-module page-copy logic (in-place Step 6), and the per-file classification table all describe the pre-de-specialization scaffold. Rewrite it so the frontend sections reflect the project-agnostic, byte-identical `frontend/src` reality: shrink the fresh-first/in-place frontend transplant steps to the user-owned-dirs copy, drop the now-obsolete identity/module-station patches, and note the dormant-file model (SA105 Option A) so maintainers understand why unselected-module pages appear in their tree. Land this in the same track chain as SA105/SA106 — a de-specialization that leaves a stale 900-line playbook has only moved the mess from source into docs.
  - Verify: playbook frontend sections contain no `projectName`/`useModules.ts`/`main.tsx`-conditional patch steps that SA105/SA106 removed; the classification table reflects "user-owned copy, everything else regenerated"; cross-references to the runtime seam (and SA107 fail-hard behavior, if landed) are present.
  *(why →* the Finding 10 win is not banked until the migration doc matches the new copy-not-merge reality; otherwise the drift moves from generator source into the playbook*)*

### Track 3 — Core/CLI plumbing — owns the SA96-GATE join + installed-wheel release blockers

All prior Track 3 work is closed (arch-audit Finding 1 via SA89a+SA89b; all four GATEs; SA91 parallel worker pool; SA93 e2e in green-gate; SA100 TA58/TA59 theme preflight; SA101 quality remediation; **SA96-GATE** join complete) — see [CHANGELOG.md](../../CHANGELOG.md). The two open Track 3 tickets are the installed-wheel release blockers **SA109 → SA110**; both feed the human-only **SA96-PUBLISH**.

#### Installed-wheel release blockers (SA109 → SA110)

The green-gate (`make check`/`quality`/`ci`/`ci-e2e`) runs entirely inside the maintainer monorepo, where `quickscale_modules/` resolves relative to the source tree — so **no gate exercises the pip-installed wheel layout**. `make install` (which mirrors what a PyPI `pip install quickscale` produces) currently yields a `quickscale` CLI that crashes on *every* invocation, including `quickscale --version`: `config_schema.py:92` runs `AVAILABLE_MODULES = set(get_discovered_module_names())` at **import time**, which calls `get_modules_base_path()` (`contracts/module_discovery.py:83`); that resolver only accepts the monorepo `parents[4]/quickscale_modules` directory and otherwise raises `ImproperlyConfigured` (the AF7 "no installed-package fallback" posture). Nothing in CLI bootstrap calls `set_modules_base_path()`, and although the wheel bundles a manifest snapshot at `quickscale_core/data/manifests/*/module.yml`, discovery never consults it. Net: the release artifact is DOA and the gate can't see it. **File ownership:** `quickscale_core` discovery/schema + CI publish surface — disjoint from Track 2's `showcase_react`/generator chain, so it runs in parallel with Track 2.

- [ ] **SA109 — Fix installed-wheel module discovery.** `Tier 2 · Track 3 · deps: none · assistant-executable · CRITICAL PATH (blocks SA96-PUBLISH)`
  Make an installed `quickscale` wheel discover its modules without the maintainer monorepo. Preferred shape: `get_modules_base_path()` falls back to the wheel-bundled manifest snapshot (`quickscale_core/data/manifests/`) when `parents[4]/quickscale_modules` is absent, instead of raising — *and/or* make the import-time `AVAILABLE_MODULES`/`READY_MODULES` in `config_schema.py:92-93` lazy so a missing base path never crashes CLI import. Preserve the fail-hard AF7 intent where it is genuinely load-bearing (generation needs real module source), but distinguish "reading the shipped module universe" (must work from the bundled snapshot) from "operating on module source trees" (may still require a resolvable base path). Confirm the AF7 decision text (docstring cites it; not found in `decisions.md`) and reconcile it — if this fix changes the ratified posture, record the amendment in `decisions.md` (conditionally-shared closeout file).
  - Verify: `make install` then `hash -r && quickscale --version` exits 0; `quickscale status`/`--help` exit 0 from a directory outside the source tree; the full set of shipped module names is still reported; monorepo/in-repo behavior and all existing gates unchanged.
  *(why →* the release artifact crashes on import; the green-gate never exercised the installed layout, so this is invisible to SA96-GATE and must be fixed before SA96-PUBLISH*)*

- [ ] **SA110 — Installed-artifact smoke gate for non-mutating commands.** `Tier 2 · Track 3 · deps: SA109 · assistant-executable · CRITICAL PATH (blocks SA96-PUBLISH)`
  Add a gate that builds the wheels, installs them into a **throwaway venv outside the source tree** (so `parents[4]/quickscale_modules` cannot resolve — the property the in-repo gates lack), and runs every **non-mutating** CLI command asserting exit 0 and no traceback: `quickscale --version`, `quickscale version`, `quickscale --help` (+ per-subcommand `--help`), and `quickscale status` (outside a project). Explicitly excludes state-changing/outward-facing commands (`up`/`down`/`apply`/`plan`/`deploy`/`dr`/`update`/`push`/`remove`/`manage`/`shell`). Wire it into `publish.yml` **before** the build/publish steps (alongside the SA103 `frontend-proof` dependency) so a DOA wheel can never publish; optionally expose a local `make smoke-install` target for pre-publish confidence.
  - Verify: the gate fails on a deliberately reintroduced SA109 regression (revert the fix → `quickscale --version` traceback → gate red), then passes with SA109 in place; `publish.yml` orders the smoke gate ahead of build/publish.
  *(why →* the coverage gap that let SA109 through was that no gate runs the installed artifact; this closes it so the class can't regress into a published release*)*

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

All prior release-path and audit-remediation tickets are complete (SA92/SA84/SA86/SA93/SA94/SA95/SA96-T1/T2/SA97/SA98/SA99/SA100/SA91/SA101/SA102/SA103/SA104/SA105/SA106/TP1/TP2/TP2b/TP3a/TP3b/TP4, Finding 1, all four GATEs) — see [CHANGELOG.md](../../CHANGELOG.md). Only open work is shown below.

```
Track 1 (complete)         Track 2 (off crit. path)          Track 3 → release (critical path)
────────────────────────   ────────────────────────────      ─────────────────────────────────
✓ TP4 complete              SA105 ✓ ── module de-spec (2a;     SA96-GATE ✓ ── green-gate join
✓ TP suite closed             complete)                           (make check/quality/ci/ci-e2e)
  (TP1/TP2/TP2b/           SA106 ✓ ── identity de-spec (2b;             │
   TP3a/TP3b/TP4)             deps SA104 ✓; complete)            SA109 ── fix installed-wheel
                               │                                       module discovery (deps none)
                             SA107 ── fail-hard seam guard           │
                             SA108 ── migration-doc rewrite    SA110 ── installed-artifact smoke
                                (both deps SA105 ✓+SA106)              gate (deps SA109)
                             (arch Finding 10 chain)                 │
                                                                     ▼
                                                             SA96-PUBLISH ── build → publish
                                                               deps: SA96-GATE ✓ + SA109 + SA110
                                                               (human-only)
```

**Open work only:** Track 2's closeout pair `SA107` (fail-hard seam guard) and `SA108` (migration-doc rewrite), downstream of the complete SA104/SA105/SA106 frontend chain; Track 3's installed-wheel blockers `SA109` → `SA110`; and the release **SA96-PUBLISH** (human-only, deps: SA96-GATE ✓ + SA109 + SA110). Track 1's TP suite is **complete** (TP1/TP2/TP2b/TP3a/TP3b/TP4). SA105 is complete (review STATUS ok; see [CHANGELOG.md](../../CHANGELOG.md) for validation evidence); SA106 is complete (identity de-spec). The frontend chain owns the `quickscale_core` generator + `showcase_react` template tree, with SA108 additionally owning `docs/planning/beta-site-migration.md` — disjoint from the TP work and the SA103 CI surfaces — so Track 2 runs concurrently with release; only the closeout files (`CHANGELOG.md`, `roadmap.md`) are shared, covered by the Merge procedure. Tracks 1 and 2 are off the release critical path and must not regress any gate's pass/fail set or coverage thresholds.

**Critical path.** SA96-GATE is complete — all four commands exit 0 with empty quarantine (see [CHANGELOG.md](../../CHANGELOG.md)). Remaining critical-path items, in order: **SA109** (fix installed-wheel discovery, assistant-executable) → **SA110** (installed-artifact smoke gate, assistant-executable) → **SA96-PUBLISH** (human-only). SA109/SA110 surfaced because the green-gate runs only inside the monorepo and never exercised the pip-installed wheel, which currently crashes on import.

### Track readiness (2026-07-20)

- **Track 1 — COMPLETE (off critical path).** All TP work (TP1/TP2/TP2b/TP3a/TP3b/TP4) and the two rebalanced CI-gate tickets (SA102/SA103) are closed — see [CHANGELOG.md](../../CHANGELOG.md). The TP suite is fully landed with no open tickets. Off the SA96 release critical path; none of its changes regressed any gate's pass/fail set or coverage thresholds.
- **Track 2 — SA105/SA106 complete, SA107–SA108 remaining (off critical path).** All prior release/audit work is closed (SA94, SA88b, SA86, SA95, SA96-T2, SA98, TP3a/TP3b, SA105, and now SA106). **SA105** is complete (independent review STATUS ok; validation evidence in [CHANGELOG.md](../../CHANGELOG.md)). **SA106** (identity de-spec) is complete. The chain continues with **SA107** (fail-hard seam guard) and **SA108** (migration-doc rewrite). The chain owns the `quickscale_core` generator + `showcase_react` template tree only (SA108 additionally touches `docs/planning/beta-site-migration.md`), disjoint from TP and SA103 CI surfaces; it must not regress any gate or coverage threshold.
- **Track 3 — SA109/SA110 open on the critical path (release blockers).** All prior Track 3 work is closed (Finding 1, four GATEs, SA91, SA100, SA93, SA101, and **SA96-GATE**). Two new critical-path tickets are open: **SA109** (fix installed-wheel module discovery — the pip-installed CLI crashes on import; deps none, assistant-executable) → **SA110** (installed-artifact smoke gate for non-mutating commands; deps SA109, assistant-executable). Both block **SA96-PUBLISH** (human-only). They own `quickscale_core` discovery/schema + the CI publish surface — disjoint from Track 2's `showcase_react`/generator chain, so they run in parallel. Non-gating advisories remain deferred (SA91 CR-SA91-REV-006 low; SA89B-CR-004; SA93-REV-005; SA93-ADV-001..004).

**Net — Tracks 2 and 3 have assigned, independent work and none is a merge hazard (file-disjoint except the shared closeout files, covered by the Merge procedure).** Track 1 is **complete** (all TP tickets closed). Track 2 = `SA105` ✓ (complete) + `SA106` ✓ (complete) + its closeout pair `SA107` + `SA108` (arch Finding 10 chain, off critical path); Track 3 = `SA96-GATE` ✓ (complete) → `SA109` (fix installed-wheel discovery) → `SA110` (installed-artifact smoke gate) → `SA96-PUBLISH` (human-only). SA109/SA110 own `quickscale_core` discovery/schema + the CI publish surface, disjoint from Track 2's `showcase_react`/generator tree, so the two open tracks run in parallel with no merge hazard beyond the shared closeout files. SA109→SA110→SA96-PUBLISH is a strict ordering chain (installed-layout fix must precede its guard, which must precede publish), so it stays on one track and no rebalancing move helps. See [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92) for the recorded squash/guardrail/shrink-only-quality policies; detailed history is in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
