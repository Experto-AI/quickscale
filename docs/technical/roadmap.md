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

**Only the integration suite shards by module.** `scripts/test_integration.sh` loops `quickscale_modules/*` sequentially (one pytest stage per module, each with its own per-file 80% / mean 90% coverage floor). `lint`, `typecheck`, and the `check-*` gates are repo-global — they do not parallelize per module. A single module runs in isolation via `make MODULE=<name> test -- --modules`.

#### Per-module test gate (the parallelizable axis)

- [ ] **SA84 — CRM restricted-role fixtures (67 fail).** `Tier 2 · Track 1 · deps: none` — full brief in the SA84 ticket under Track 1 below. Gate line: `make MODULE=crm test -- --modules` → 0 failures at the 80%/90% floors, no quarantine entry.
- [ ] **SA95 — Blog fixture-finalizer regression.** `Tier 2 · Track 1 · deps: none` — blog was closed green by SA83 but SA93's broad run re-surfaced `pytest-django` fixture-finalizer failures; full brief in the SA95 ticket under Track 1 below.

  forms (SA85), listings (SA86), orgs (SA77), notifications (SA79) are green under the SA82 baseline — see [CHANGELOG.md](../../CHANGELOG.md).

#### Repo-global gates (run once at v87 integration, after per-module work lands)

GATE-lint, GATE-typecheck, GATE-check-suite, and **GATE-quality** are all **done** (2026-07-15; see [CHANGELOG.md](../../CHANGELOG.md)). Track 2's module work and its own gates are complete, so the remaining closeout — the **SA91** tooling and the new **SA93** (e2e in the green-gate) — is **reassigned to the freed Track 3** (idle after SA89a/b closed Finding 1). SA91 has no dependencies. SA93 now carries a hidden cross-track prerequisite — see SA93 entry below.

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

### Cross-cutting decision (re-based 2026-07-15) — eliminate the cross-org-migration class by squashing to a final-schema initial migration (arch-audit Finding 8)

SA84 and SA86 were originally framed as two instances of **arch-audit [Finding 8](../others/arch-audit.md) (`module-rls-context-procedural`)**: RLS-context acquisition is procedural — cross-org *data migrations* and test fixtures must remember to acquire `operator_access`. The blanket BYPASSRLS hatch masked every omission until SA82 removed it.

**Decision re-based (2026-07-15) — drop backward compatibility; squash migrations.** The entire cross-org-*migration* half of Finding 8 is an artifact of **schema evolution**: `organization_id` was added to already-populated tables, so historical migrations (`crm/0006`, `crm/0009`, `forms/0007`) carry `_backfill_*_org` `RunPython` steps that walk existing rows and need elevated context. Since the project is **pre-launch with no deployed database to carry forward**, we squash every module's migrations to a single **final-schema `0001_initial`** where `organization_id` is `NOT NULL` from row zero. **There is then nothing to backfill → the cross-org-migration class is empty → the entire SA88 conformance-gate saga has no target and is deleted.** RLS policies (installed via `apply_force_rls` / `operator_access_rls`, not auto-generated) are manually re-attached to each squashed migration. This supersedes the seam-plus-gate approach (SA88/SA88a–e) below; the shared `operator_access_migration` helper becomes dead code and is retired (`apply_force_rls`/`revert_force_rls` stay).

**What this leaves.** The *fixture* half of Finding 8 survives untouched — squashing migrations does nothing to test fixtures. CRM triage confirmed the split: 67 failures bucket **0 migration / 67 fixture / 0 runtime-query** (test-posture; no production isolation bug). So **SA84 (CRM, 67) remains real work, but decouples from SA88 entirely** — it becomes "route cross-org test fixtures through the shared org-context helper under NOBYPASSRLS," with `deps: none`. SA86 (listings, 6) — the same fixture cleanup — is already done (Track 2; see [CHANGELOG.md](../../CHANGELOG.md)). The runtime RLS enforcement itself (SA59/SA82, PostgreSQL FORCE RLS under `quickscale_test_role`) is unchanged and load-bearing.

**Superseded work.** The seam baseline (69cabb47), the runtime-oracle pivot, and the SA88a–e static-analyzer line are all **obsoleted by the squash** — not merely superseded by a stronger proof, but rendered targetless. The gate file `test_sa88_migration_operator_access_conformance.py` (7,144 lines) is deleted; open findings **CR-SA88-REV-006/007, CR-SA88A1-REV-002/003/004** close as **obsoleted-by-schema-squash**. A tiny forward guardrail replaces the gate (see SA92). Historical detail in [CHANGELOG.md §SA88](../../CHANGELOG.md).

### Track 1 — Tenant-context surface

> **↪ HAND-OFF — SA92 (squash migrations) → SA84 (CRM fixtures).** Replaces the deleted SA88d/SA88e runtime-oracle line (see the re-based cross-cutting decision above). The self-contained brief:
> - **Work location:** Track 1 worktree `/home/victor/code/quickscale-wt-track1` (branch `wt-track1`). Run the roadmap start procedure (`git merge v87`) first. Commit checkpoints on `wt-track1`; **do not merge to `v87`** — the maintainer keeps the merge decision and the final independent review.
> - **Compat posture (ratified 2026-07-15):** no deployed database to carry forward. A clean `migrate` on a fresh DB is the only supported path; old migration history is discarded, not `--squash`-chained.
> - **Modules to squash:** `orgs`, `auth`, `blog`, `crm`, `forms`, `listings`, `billing`, `social`, `notifications`. Each collapses `0001..000N` into one final-schema `0001_initial`.
> - **RLS is NOT auto-generated — re-attach it by hand.** Each squashed migration must keep its `RunPython(apply_force_rls, <targets>)` (and for `orgs`: `operator_access_rls` + `operator_access_readonly`). Source the current live policy set from the existing `*_enable_rls` / `*_refresh_rls*` migrations; verify by diffing `pg_policies` before/after against `v87`.
> - **Drop:** all `_backfill_*_org` `RunPython` steps (crm `0006`/`0009`, forms `0007`) — a fresh DB has no rows to backfill. Retire `operator_access_migration` from `tenancy.py` once `forms/0007` is gone; **keep** `apply_force_rls`/`revert_force_rls`.
> - **Delete:** `quickscale_modules/orgs/tests/test_sa88_migration_operator_access_conformance.py` (7,144 lines) in full, plus any SA88 boundary-proof helpers. Replace with a ~30-line forward guardrail in SA92.
> - **Then SA84:** the CRM fixture failures are ContextVar (`set_current_org_id`) seeding under NOBYPASSRLS — untouched by the squash. Route cross-org fixtures through the shared org-context helper.

- [ ] **SA92 — Squash all module migrations to a final-schema initial migration; delete the SA88 gate saga.** `Tier 2 · Track 1 · deps: none`
  Collapse each module's migrations to one `0001_initial` at the final model state, with `organization_id NOT NULL` from creation. Manually re-attach each module's RLS `RunPython` (`apply_force_rls`, orgs `operator_access_rls`/`operator_access_readonly`); drop all `_backfill_*_org` steps. Delete `test_sa88_migration_operator_access_conformance.py` and retire the now-dead `operator_access_migration` helper. Add a **~30-line forward guardrail** unit test asserting no module migration contains cross-table org-id DML (`UPDATE ... SET organization_id` referencing another table), so the eliminated class cannot silently return.

  *Acceptance:* fresh `migrate` on an empty DB builds the identical schema **and identical RLS policy set** as `v87` (diff `pg_policies`); NOBYPASSRLS integration suite behaves as before the squash; guardrail test green; MyPy + orgs lint green; independent review confirms the RLS re-attachment is complete and no backfill logic was silently lost. Closes CR-SA88-REV-006/007 and CR-SA88A1-REV-002/003/004 as **obsoleted-by-schema-squash**.
  *(why →* arch-audit Finding 8; 2026-07-15 squash re-base*)*

  *Implementation landed on `v87`* (confirmed in tree: one `0001_initial` per module, 35 intermediates + the SA88 gate file deleted, `operator_access_migration` retired, forward guardrail added, `pg_policies`/catalog/RLS/data parity exact against `v87`). Concise done-history is in [CHANGELOG.md §SA92](../../CHANGELOG.md).

  **Blocked checkpoint (2026-07-16; explicit maintainer cap decision: stop, record, and merge):**
  - **Done:** all nine module migration histories are collapsed to final-schema `0001_initial` files; 35 intermediate migrations, the SA88 gate, and `operator_access_migration` are removed. Fresh-database catalog/RLS/data captures match `v87` exactly (21 FORCE-RLS tables / 42 policies, five parent UNIQUE constraints, six composite FKs, Forms four presets / 16 fields). Ruff, MyPy, focused tests, and the restricted-role integration comparison are validated; the only integration failures at implementation time were SA84 CRM 67 and SA86 listings 6 baselines (SA86 since resolved per v87). Listing's concrete index names remain exact while the public abstract seam uses portable generated names.
  - **Pending/Blocking:** **CR-SA90-MSQ-002 (high/blocking)** remains open: the compact migration-DML guardrail still accepts some unresolved imported SQL sinks, mishandles parameterized same-table assignments and positional sink arguments, and does not yet resolve bindings lexically/in source order or close comment-obscured bypasses. **CR-SA90-MSQ-003 (medium/blocking)** remains open: CRM/Forms/Billing regression tests still use permissive predicate fragments instead of exact normalized RLS and Billing partial-index expressions, so unsafe extra clauses could remain undetected. SA92 stays unchecked until independent review resolves or explicitly waives both findings.
  - **Decisions needed:** none. The maintainer selected stop-and-merge at the review cap. A future continuation must fix only the two blocking findings above, rerun the affected guardrail/predicate tests plus canonical and restricted-role gates, and obtain clean independent review before checking SA92.
  - **Advisory:** **CR-SA90-MSQ-005 (low/advisory)** remains open: roadmap prose still implies orgs installs operator policies even though tenant modules install their own policies and orgs installs none at its migration point.

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

**Reassigned closeout work (from Track 2, to use freed Track 3 capacity — all `deps: none`):**

> **↪ Next up for Track 3 (hand off now): SA91.** It is unblocked (`deps: none`), non-gating, and independent of the SA93 cross-track wait — start it immediately rather than idling behind SA93.

- [ ] **SA91 — Fork the per-module integration loop for true parallel execution.** `Tier 2 · Track 3 · deps: none`
  `scripts/test_integration.sh` runs module stages serially (loop at `:414–442`). Fork each module's pytest stage and join exit codes + coverage. Contention points to resolve: the shared `COVERAGE_RESULTS_FILE` mktemp (`:57`) must become per-module and be merged before `check_overall_mean_coverage`; the per-module `QS_*_DB_USER` role setup (`:375–386`) and pre-created test databases must not collide across concurrent workers. CI-time speedup only — not a gate for the green-gate milestone.

  *Acceptance:* parallel run produces the identical pass/fail verdict and the identical overall-mean coverage as the serial run; no cross-worker DB collision under the restricted role.
  *(why →* parallelize testing by module*)*

- **GATE-quality** (done 2026-07-15, see [CHANGELOG.md](../../CHANGELOG.md)) and **SA93** (fold e2e into the green-gate) were also reassigned here; SA93 is defined in the green-gate section above and remains open (blocked checkpoint on the SA84/SA95 cross-track prerequisite).

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA92 — squash migrations +          SA94 — remove showcase_html theme     Finding 1 ✓ DONE (SA89a+SA89b)
  delete SA88 gate saga               deps: none (non-gating)               GATE-lint/typecheck/check/quality ✓
  deps: none                          (prior module work + gates COMPLETE)  SA93 — e2e in green-gate (blocked)
      │                                                                       SA91 — parallel loop (non-gating)
      ▼
SA84 — CRM (67 fixtures) ┐
SA95 — blog regression   ┘ deps: none
  │  (per-module gates; SA93 prereqs)
  Track 1                            Track 2                               Track 3
```

**Ordering.** The squash (SA92) eliminates the cross-org-migration class, so the SA88 gate saga (SA88a–e) is deleted, not completed. SA84 and SA95 survived as **fixture / test-posture** cleanups. Track 1 runs SA92 → SA84 → SA95. Track 2's prior work is complete (module work + its own gates); its one open item is SA94 (remove the `showcase_html` theme, non-gating). Track 3, freed after closing Finding 1, took over the remaining closeout (all GATEs done, SA93, SA91).

**Green-gate milestone (cross-track join).** "All quality make commands pass" is the integration join: the per-module gates (SA84 CRM + SA95 blog, Track 1) plus the repo-global closeout (SA93 e2e, Track 3) must all land on `v87`. GATE-lint, GATE-typecheck, GATE-check-suite, and GATE-quality are complete. **SA93 is a blocked checkpoint** — the broad pre-review run reached coverage but blog+CRM integration failed before E2E, and independent review leaves CR-SA93-REV-002/004 open in the post-fix local-CI path. See the SA93 entry above for the exact Done / Pending-Blocking / Decisions-needed ledger. SA91 is a separate non-gating optimization (Track 3) — CI-time speedup only, not a gate for green.

### Track readiness (2026-07-16)

- **Track 1 — BLOCKED checkpoint merged (SA92, unchecked), with SA84 and SA95 still open.** The squash-and-drop-backward-compat decision is ratified and the validated implementation is landed, but SA92 remains unchecked on CR-SA90-MSQ-002/003; CR-SA90-MSQ-005 remains advisory. No maintainer design decision is pending — the maintainer selected stop-and-merge at the review cap. A future continuation must fix those review findings, rerun affected gates, and obtain clean independent review before checking SA92. SA84 (CRM fixtures) and SA95 (blog regression) remain separate open work; rerun both after the squash to confirm no failure is a migration-state artifact. The retired SA88a–e findings (CR-SA88-REV-006/007, CR-SA88A1-REV-002/003/004) close as obsoleted-by-schema-squash.
- **Track 2 — BLOCKED checkpoint (SA94).** Prior module work (SA86, SA88b) and its own gates (GATE-lint, GATE-typecheck, GATE-check-suite) are all done; earlier closeout items were reassigned to Track 3. **SA94** remains the only open Track-2 item and is paused at the 2026-07-16 plan-review cap on **SA94-PLAN-CALLER-001**; no executable SA94 delta is landed. It is independent of the green-gate milestone.
- **Track 3 — BLOCKED (partially).** Finding 1 (DR persistence port) is closed (SA89a + SA89b) and all four GATEs are done. **SA93** (fold e2e into the green-gate) is a blocked checkpoint: it first needs the deterministic CR-SA93-REV-002/004 fixes (no decision required), then cannot complete until CRM (**SA84**) and blog (**SA95**) integration shards are green on `v87` — a cross-track dependency on Track 1. The blog-ownership decision is now resolved (dedicated ticket SA95, 2026-07-16). **SA91** (non-gating parallel-loop tooling) is unblocked and can proceed in parallel. **SA89B-CR-004 (low/advisory)** remains against `check_module_core_compatibility.py` independently, not gating.

**Net:** Track 1 carries the merged SA92 blocked checkpoint (unchecked) plus open SA84/SA95 work — no maintainer design decision is pending. Track 2 is blocked at the SA94 plan-review cap. Track 3's SA93 is blocked on Track 1 (SA84 + SA95) plus its own deterministic fixes; SA91 on Track 3 can proceed now.

**Decision (ratified 2026-07-15) — Track 1: squash migrations, delete the SA88 gate saga.** After the static-analyzer line and its runtime-oracle successor both proved to be chasing an artifact of schema evolution, the maintainer confirmed (no deployed DB to preserve) that squashing every module to a final-schema `0001_initial` eliminates the cross-org-*migration* class outright. **Why:** the backfills only exist because `organization_id` was added to populated tables; a fresh schema has no rows to backfill, so there is no invariant left to gate. RLS enforcement (SA59/SA82) is unchanged; the *fixture* failures (SA84) are a separate, ContextVar-level concern the squash does not touch. **Sub-decisions:** (1) squash-and-drop-compat over continue-oracle; (2) manually re-attach RLS `RunPython` to the squashed migrations (not auto-generated); (3) keep a ~30-line forward guardrail against reintroducing cross-org migration DML. This supersedes every SA88 decision — the SA88a–e static-analyzer line and its runtime-oracle successor (SA88d/e) are all obsoleted-by-squash; their full reasoning trail is preserved in [CHANGELOG.md §SA88](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
