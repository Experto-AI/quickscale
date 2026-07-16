# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks pending roadmap work. Detailed completed implementation history is in [CHANGELOG.md](../../CHANGELOG.md). Each phase is sized as Adaptive Tier 1–2; split before implementing if a checklist item is Tier 3.

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

---

## Open work

> Completed work lives in [CHANGELOG.md](../../CHANGELOG.md). This section holds only active and blocked work.

**Integration baseline (SA82).** The SA82 unquarantined `make test-integration` gate is the accepted baseline for the remaining restricted-role cluster. Under it the closed modules are blog (SA83), forms (SA85), listings (SA86), orgs (SA77), and notifications (SA79) — see [CHANGELOG.md](../../CHANGELOG.md). Two reds remain open: **CRM (SA84)** and a **blog fixture-finalizer regression (SA95)** that SA93's broad run re-surfaced after SA83 had closed blog green (see SA95 under Track 1).

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a fresh clone + fresh `migrate` (post-SA92 squash), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). `make check` is the umbrella gate — `lint` + `typecheck` + `test` (unit + integration) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (`Makefile:652`). `make check` keeps its `-m "not e2e"` scoping; e2e runs in its own lane (`make test-e2e` / `make ci-e2e`, `.github/workflows/e2e.yml`) and is now part of "done" via SA93.

**Only the integration suite shards by module — and now runs in parallel.** `scripts/test_integration.sh` parallelizes module test runs through a configurable worker pool (QS_INTEGRATION_JOBS), with per-worker coverage-file isolation, deterministic replay order, and joined exit codes. Each worker runs one pytest stage per module with per-file 80% / mean 90% coverage floors. `lint`, `typecheck`, and the `check-*` gates are repo-global — they do not parallelize per module. A single module runs in isolation via `make MODULE=<name> test -- --modules`.

#### Per-module test gate (the parallelizable axis)

- [ ] **SA84 — CRM restricted-role fixtures (67 fail).** `Tier 2 · Track 1 · deps: none` — full brief in the SA84 ticket under Track 1 below. Gate line: `make MODULE=crm test -- --modules` → 0 failures at the 80%/90% floors, no quarantine entry.
- [ ] **SA95 — Blog fixture-finalizer regression.** `Tier 2 · Track 1 · deps: none` — blog was closed green by SA83 but SA93's broad run re-surfaced `pytest-django` fixture-finalizer failures; full brief in the SA95 ticket under Track 1 below.

  forms (SA85), listings (SA86), orgs (SA77), notifications (SA79) are green under the SA82 baseline — see [CHANGELOG.md](../../CHANGELOG.md).

#### Repo-global gates (run once at v87 integration, after per-module work lands)

GATE-lint, GATE-typecheck, GATE-check-suite, **GATE-quality**, and the reassigned **SA91** tooling are all **done** (see [CHANGELOG.md](../../CHANGELOG.md)). The remaining closeout is **SA93** (e2e in the green-gate), assigned to Track 3 after SA89a/b closed Finding 1. SA93 carries a hidden cross-track prerequisite — see its entry below.

- [ ] **SA93 — Fold the e2e lane into the green-gate definition of done.** `Tier 1 · Track 3 · deps: blog+CRM integration green (previously unstated cross-track join prerequisite)`
  **Blocked checkpoint (2026-07-15; maintainer-selected stop-and-merge; not complete).**

  **Done:**
  - Added the combined core/CLI/backups coverage path, `scripts/check_coverage_policy.py`, maintained helper tests, and focused DR-engine lock/path/sidecar tests.
  - The broad pre-review QG run reached the then-current coverage stage: its statement-weighted report was **92.02%** with **0/83 per-file offenders** (`_lock 97%`, `_paths 100%`, `_sidecar 94%); integration then failed in blog and CRM, so E2E did not run.
  - Review follow-up corrected the intended policy to an **equal-weight core/CLI package mean**, deferred pytest's weighted threshold so the helper is the final authority, and wired `make test-cov-policy` into the local CI path. Post-fix focused evidence is **24/24 helper tests passed**, Ruff passed, and `bash -n scripts/check_ci_locally.sh` passed.
  - Independent review resolved **CR-SA93-REV-001** (equal-package arithmetic/final authority) and **CR-SA93-REV-003** (maintained helper-test collection).

  **Pending/Blocking:**
  - **CR-SA93-REV-002 (high/blocking):** coverage JSON validation is not fully fail-closed. Scalar/null roots and non-dict file records can raise; reports missing either expected package can pass; prefix-only classification accepts non-canonical traversal paths. Add root/container/record validation, require both packages, reject non-canonical paths, and add malformed/missing-package/traversal proofs.
  - **CR-SA93-REV-004 (medium/blocking):** `scripts/check_ci_locally.sh` advertises 12 stages but uses inconsistent `/11` denominators and duplicates `[11/11]` on the non-E2E path. Normalize conditional stage totals and make the E2E-skip message unnumbered before relying on stage-number evidence.
  - **SA93-BLOCK-001 (high/blocking):** blog and CRM integration shards fail with `pytest-django` fixture-finalizer errors. CRM maps to open **SA84** (Track 1); the blog regression is now owned by dedicated ticket **SA95** (Track 1).
  - **SA93-BLOCK-002 (high/blocking):** core and CLI E2E remain unexecuted because integration fails first. The current post-review 12-stage flow has not received a broad rerun; only the focused post-fix evidence above is current.

  **Decisions needed (resolved 2026-07-16):**
  - Blog-regression ownership is **decided**: it is a dedicated ticket, **SA95** (Track 1), and — together with CRM/**SA84** — is now an explicit cross-track prerequisite for SA93. Preserve the exact unquarantined `make ci-e2e` contract; quarantine and threshold weakening are not acceptable.
  - No design decision is needed for CR-SA93-REV-002 or CR-SA93-REV-004; they are deterministic first fixes for the next Track 3 continuation.

  **Clean continuation:** fix CR-SA93-REV-002/004 → land SA84 (CRM) + SA95 (blog) fixes on `v87` → resync `wt-track3` → rerun exact `make ci-e2e` → verify both E2E suites execute and `e2e.yml` is green on `v87` → independent final review → mark SA93 complete.

  *(Acceptance unchanged:* `make ci-e2e` exits 0 on a fresh clone; `e2e.yml` green on `v87`; exit-criteria prose lists the e2e lane.*)*
  *(why →* green-gate milestone; e2e was outside the definition of done*)*

### Track 1 — Tenant-context surface

> **Migration-squash context (SA92, complete 2026-07-16).** The cross-org-*migration* half of arch-audit [Finding 8](../others/arch-audit.md) (`module-rls-context-procedural`) was eliminated by squashing every module to a final-schema `0001_initial` (`organization_id NOT NULL` from row zero) — nothing to backfill, so the SA88 gate saga was deleted, not completed. Full decision record: [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92); reasoning trail in [CHANGELOG.md §SA88/§SA92](../../CHANGELOG.md). The **fixture** half survives (squashing does nothing to test fixtures): **SA84 (CRM, `deps: none`)** and **SA95 (blog)** are the remaining open Track 1 work; SA86 (listings) is done.

- [ ] **SA84 — Fix CRM's 67 restricted-role RLS fixture failures (plus 20 skipped).** `Tier 2 · Track 1 · deps: none (decoupled from SA88 by the squash)`
  Under the SA82 gate, CRM showed 195 passed, 67 fixture-time RLS failures, 20 skipped (triage: 0 migration / 67 fixture / 0 runtime — test-posture, not a production isolation bug). These are ContextVar-seeded fixtures failing under NOBYPASSRLS and are unaffected by SA92. Route each cross-org *fixture* through the shared org-context helper rather than inlining `SET LOCAL`. Any runtime-query-bucket failure that surfaces is fixed as a real isolation bug (with its own regression test), not test-posture.

  *Acceptance:* CRM restricted-role suite passes clean (0 failures) under `make test-integration`, no quarantine entry.
  *(why →* CR-SA82-NT-003; arch-audit Finding 8 (fixture half)*)*

- [ ] **SA95 — Fix the blog restricted-role fixture-finalizer regression.** `Tier 2 · Track 1 · deps: none`
  SA83 closed blog green (211 passed/0 failed under the SA82 gate), but SA93's broad pre-review run re-surfaced blog integration-shard failures with `pytest-django` fixture-finalizer errors. **First step — triage before fixing** (matches the SA83–SA86 discipline): run blog's restricted-role suite on current `v87` (`QS_BLOG_DB_USER=quickscale_test_role make MODULE=blog test -- --modules`) and bucket the failures into fixture-teardown-ordering vs migration-state vs runtime-query. Fix the confirmed root; a runtime-query-bucket failure is a real isolation bug (with its own regression test), not test-posture. Note the interaction with SA92: the squash regenerates blog's migrations, so re-run this suite after SA92 lands to confirm the regression is not a migration-state artifact before closing.

  *Acceptance:* blog restricted-role suite passes clean (0 failures) under `make test-integration`, no quarantine entry; regression test pins the finalizer fix.
  *(why →* SA93-BLOCK-001; blog regression re-surfaced after SA83 closure*)*

### Track 2 — Module contracts & settings

> **Prior Track 2 work is complete.** SA88b (forms diagnosis) done 2026-07-14; SA86 (listings) done 2026-07-15; GATE-lint / GATE-typecheck / GATE-check-suite all green 2026-07-15 — detail in [CHANGELOG.md](../../CHANGELOG.md). The remaining closeout items (GATE-quality, SA91, SA93) were reassigned to the freed Track 3 to balance load — see the green-gate section and Track 3 below. **One new item (SA94) is open** below.

- [ ] **SA94 — Remove the `showcase_html` generator theme; make `showcase_react` the sole theme.** `Tier 2 · Track 2 · deps: none`
  The "HTML demo" is the `showcase_html` generator theme — one of two scaffold themes (the other, `showcase_react`, is already the default and the one used in real projects). It never gained adoption but carries ongoing maintenance cost, so remove it entirely. **Delete** `quickscale_core/.../generator/templates/themes/showcase_html/` (9 files) and `quickscale_core/tests/test_html_theme_integration.py`. **Prune wiring:** `_THEME_DEST_MAP` + `available_themes` in `generator/generator.py`; `VALID_THEMES` in `schema/config_schema.py`; the `AVAILABLE_THEMES` entry + help strings in `plan_command.py`, `apply_command.py`, `module_config.py`; the `test_html_theme_integration.py` line in `.github/workflows/e2e.yml`. **Collapse theme conditionals** in the generated-project templates `project_name/views.py.j2` and `project_name/urls.py.j2` — drop the `{% if theme == 'showcase_html' %}` blocks (including the HTML-only `social_link_tree_view` / `social_embeds_view` and their routes — *drop them, do not port*; the social module's server-rendered payload builders stay) and make the `theme != 'showcase_react'` inverse branches unconditional. **Remove the now-orphaned shared root assets** `templates/static/*` and `templates/templates/components/*` (react skips them) — *only after* confirming no react path or `common/` admin fallback consumes them. **Migrate the ~27 fixture tests** that pass `theme="showcase_html"` merely as a scaffold theme over to `showcase_react` (adjusting emitted-path assertions: react emits to `frontend/`), regenerate the `showcase_html` entries in `tests/fixtures/sa90_emission_manifests.json` + `tests/generator/test_themes.py` for the SA66/SA90 conformance gate, and flip any `test_config_schema_validation.py` case that asserted `showcase_html` valid. **Verify** the `beta_migration.py:155` "showcase_html only" static-asset branch is unreachable for migrated projects before deleting it. **Docs:** update `GLOSSARY.md`, top-level `README.md`, and `docs/technical/...`.

  *Acceptance:* `grep -rn "showcase_html" quickscale_core quickscale_cli quickscale_devtools quickscale_modules docs .github` returns only historical release notes (or nothing); full test suite + SA66/SA90 emission-conformance gate green; a default-theme scaffold builds/runs and the plan/apply interactive flow no longer offers `showcase_html`; generated `views.py`/`urls.py` contain no HTML-only `social_link_tree_view` / `social_embeds_view` definitions or bindings, while the supported React `TemplateView` social routes remain.
  *(why →* unused theme, ongoing maintenance cost; single supported frontend is `showcase_react`*)*

  **Blocked checkpoint (2026-07-16; maintainer-selected stop-and-merge at plan-review cap; not complete):**
  - **Done:** Resynced the clean Track 2 worktree to `v87`, confirmed the worktree-local Poetry/Docker/Playwright/PostgreSQL-tooling prerequisites, refreshed the full SA94 topology, and produced a serial eight-phase plan with executable Review Barrier A, completion-doc Review Barrier B, and exact reviewed-tree resync/merge discipline. Plan review resolved the prior coverage-isolation, barrier-ordering, desired/authoritative/recovery-state validation, one-theme E2E input, React-route-preservation, and fail-closed reference-scan planning gaps. No product/source/test/template/workflow/devtools implementation was made; the pre-SA94 executable tree remains unchanged.
  - **Pending/Blocking:** **SA94-PLAN-CALLER-001 (high/blocking)** — caller parity is still incomplete because DR `_build_context` and development `up` can perform Docker-backed checks before strict identity/config validation. A clean continuation must add both seams to the state-safety and validation phases, require retired-theme rejection before `_validate_project_and_docker`, and add sentinels proving no Docker/Railway/adapter subprocess, write, generation, remote call, deletion, or wiring occurs before rejection. The full SA94 implementation, validation, both review barriers, completion docs, and merge remain pending; SA94 stays unchecked.
  - **Decisions needed:** none. At the cycle-2 cap, the maintainer selected stop, record this blocked checkpoint, and merge. Future continuation should revise only SA94-PLAN-CALLER-001 first, obtain clean plan review, then execute the already-defined phased plan.

### Track 3 — Core/CLI plumbing

> **Finding 1 closed.** arch-audit **[Finding 1](../others/arch-audit.md)** (`dr-engine-module-circular-lattice`, DR persistence port) is closed: SA89a (persistence protocol in `core` + `restore_admin_uploaded_backup` port, done 2026-07-14) and SA89b (orchestration port closeout — declarative reverse import ban + modules-absent runtime proof, custom boundary scanner deleted, done 2026-07-15). Detail in [CHANGELOG.md §SA89a/§SA89b](../../CHANGELOG.md). **SA89B-CR-004 (low/advisory)** remains open against `check_module_core_compatibility.py` independently — not gating.

**Reassigned closeout work (from Track 2, to use freed Track 3 capacity):**

> **SA91 complete (2026-07-16)** — parallel integration worker pool validated and independently reviewed; identical verdicts/coverage vs sequential mode, no cross-worker DB collision. Detail in [CHANGELOG.md §SA91](../../CHANGELOG.md). Non-gating (CI-time speedup only). Residual **CR-SA91-REV-006 (low/advisory)** open: bounded scheduling can temporarily underutilize capacity — correctness/failure-propagation unaffected. SA93 remains Track 3's open closeout item.

- **GATE-quality** (done 2026-07-15, see [CHANGELOG.md](../../CHANGELOG.md)) and **SA93** (fold e2e into the green-gate) were also reassigned here; SA93 is defined in the green-gate section above and remains open (blocked checkpoint on the SA84/SA95 cross-track prerequisite).

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA92 ✓ DONE (squash migrations)      SA94 — remove showcase_html theme     Finding 1 ✓ DONE (SA89a+SA89b)
  delete SA88 gate saga               deps: none (non-gating)               GATE-lint/typecheck/check/quality ✓
  deps: none                          (prior module work + gates COMPLETE)  SA93 — e2e in green-gate (blocked)
      │                                                                       SA91 — parallel loop ✓ DONE (non-gating)
      ▼
SA84 — CRM (67 fixtures) ┐
SA95 — blog regression   ┘ deps: none
  │  (per-module gates; SA93 prereqs)
  Track 1                            Track 2                               Track 3
```

**Ordering.** The squash (SA92) eliminates the cross-org-migration class, so the SA88 gate saga (SA88a–e) is deleted, not completed. SA84 and SA95 survived as **fixture / test-posture** cleanups. Track 1 runs SA92 → SA84 → SA95. Track 2's prior work is complete (module work + its own gates); its one open item is SA94 (remove the `showcase_html` theme, non-gating). Track 3, freed after closing Finding 1, took over the remaining closeout (all GATEs done, SA93, SA91).

**Green-gate milestone (cross-track join).** "All quality make commands pass" is the integration join: the per-module gates (SA84 CRM + SA95 blog, Track 1) plus the repo-global closeout (SA93 e2e, Track 3) must all land on `v87`. GATE-lint, GATE-typecheck, GATE-check-suite, and GATE-quality are complete. **SA93 is a blocked checkpoint** — the broad pre-review run reached coverage but blog+CRM integration failed before E2E, and independent review leaves CR-SA93-REV-002/004 open in the post-fix local-CI path. See the SA93 entry above for the exact Done / Pending-Blocking / Decisions-needed ledger. SA91 is a separate non-gating optimization (Track 3) — CI-time speedup only, not a gate for green.

### Track readiness (2026-07-16)

- **Track 1 — CLEAN to continue on SA84/SA95; SA92 completed.** SA84 (CRM fixtures) and SA95 (blog regression) are both `deps: none` and can start now — this is the productive Track 1 work. **SA92 completed** (bounded guardrail strategy implemented and independently reviewed; CR-SA90-MSQ-002/003/005 and SA92-QG-001 resolved). Rerun SA84/SA95 suites on the post-squash `v87` to confirm no failure is a migration-state artifact. Retired SA88a–e findings (CR-SA88-REV-006/007, CR-SA88A1-REV-002/003/004) close as obsoleted-by-schema-squash.
- **Track 2 — BLOCKED on work, not a decision.** Prior module work (SA86, SA88b) and its gates (GATE-lint/typecheck/check-suite) are done. **SA94** is the only open item, paused at the 2026-07-16 plan-review cap on **SA94-PLAN-CALLER-001** — a deterministic plan fix (add the DR `_build_context` and development `up` seams to the state-safety/validation phases with no-subprocess/no-mutation sentinels), **no maintainer decision required**. Revise the plan, obtain clean plan review, then execute the phased plan. Independent of the green-gate milestone.
- **Track 3 — PARTIAL (SA91 complete; SA93 blocked on cross-track work).** Finding 1 (DR persistence port, SA89a+SA89b), all four GATEs, and **SA91** (parallel integration worker pool) are done. SA91 retains **CR-SA91-REV-006** as a low, non-blocking throughput advisory. **SA93** (e2e in green-gate) is a blocked checkpoint needing the deterministic CR-SA93-REV-002/004 fixes (no decision), then cannot complete until CRM (**SA84**) and blog (**SA95**) shards are green on `v87` — a cross-track dependency on Track 1. **SA89B-CR-004 (low/advisory)** remains independent, not gating.

**Net — no remaining maintainer decisions. SA92 and SA91 completed.** Track 1 → SA84 + SA95; Track 2 → revise the SA94 plan and re-review; Track 3 → SA93's deterministic fixes while awaiting the SA84/SA95 cross-track join. The squash-migrations decision and bounded guardrail strategy are recorded in [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision-sa92); reasoning trail in [CHANGELOG.md §SA88/§SA92](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
