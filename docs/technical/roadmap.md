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

> **Closed batches (detail in [CHANGELOG.md](../../CHANGELOG.md)):** SA1–SA5 (2026-07-02), SA6–SA12 (2026-07-03), SA13.1–SA13.4 (2026-07-04), SA14.1–SA14.6 (2026-07-05), SA15.1–SA15.3 (2026-07-04), SA16.1/SA16.2 (2026-07-03), SA17.1–SA17.8 (2026-07-05), SA18.1–SA18.11 (2026-07-04), SA19 (2026-07-05), SA20 (2026-07-06), SA21.1 (2026-07-05), SA21.2 (2026-07-07), SA22 (2026-07-05), SA23 (2026-07-05), SA24 (2026-07-05), SA25 (2026-07-05), SA26 (2026-07-06), SA27 (2026-07-05), SA28 (2026-07-05), SA29 (2026-07-05), SA30 (2026-07-06), SA31 (2026-07-05), SA32 (2026-07-06), SA33 (2026-07-05), SA34 (2026-07-06), SA35 (2026-07-07), SA36 (2026-07-07), SA37 (2026-07-07), SA38 (2026-07-07), SA39 (2026-07-06), SA40 (2026-07-06), SA41 (2026-07-07), SA42 (2026-07-07), SA43 (2026-07-07), SA44 (2026-07-07), SA45 (2026-07-06), SA46 (2026-07-07), SA47 (2026-07-07), SA48 (2026-07-07), SA49 (2026-07-07), SA50 (2026-07-07), SA51 (2026-07-07), SA52 (2026-07-07), SA53 (2026-07-08), SA54 (2026-07-08), SA55 (2026-07-07), SA56 (2026-07-08). All closed per template rule — detail lives in CHANGELOG.md.
>
> **Origin note:** SA34–SA47 trace to the 2026-07-06 triage against [tech-audit.md](../others/tech-audit.md) (TA33–TA41) and [arch-audit.md](../others/arch-audit.md) (Findings 1–5), each sized Tier 1–2 (arch-audit's larger Findings 1/2/4/5 are cut down to their recommended *first step* only — later stages are explicitly deferred and remain tracked in arch-audit.md itself).
>
> **Origin note (2026-07-07, fix-plan pass):** SA48–SA56 trace to the 2026-07-07 delta-pass findings in [tech-audit.md](../others/tech-audit.md) (TA42–TA46) and [arch-audit.md](../others/arch-audit.md) (Finding 1's red flags and CR-SA44-REV-001 blocker, Finding 4's coverage-boundary sub-item, Finding 5's two remaining Option 1 pieces plus the billing migration promoted from "long tail" to scheduled work per user decision — no idiom is grandfathered as permanent legacy), each sized Tier 1–2. Every item fit Tier 1–2 without splitting; the two items large enough to flag (SA50, the `OrgApiBaseView` fold; SA56, the billing DRF migration) are Tier 2, not Tier 3.

> **Origin note (2026-07-10, fix-plan pass):** SA57–SA64 trace to the 2026-07-09/10 findings in [tech-audit.md](../others/tech-audit.md) (TA47–TA52, all opened by the unreviewed `6ea37301`/`198a1951` "fix: make check"/"fix: some make ci" commits) and [arch-audit.md](../others/arch-audit.md) (the Red flags section's DR-media/social-admin/createcachetable/TOML-splice/test-artifact items — several of which are the same defects tech-audit found independently and are merged into one task below — plus Finding 6's recommended first step and Finding 4's doc-only decision-record sub-item). Findings 1, 2 and 4's *remaining* structural work (the persistence port, the `pre_delete` backstop, the purge-order derivation) stay in arch-audit.md — each is sized M. Findings 2 and 4 are `deferred`: teams is decided **not next, not planned** (brainstormed placeholder only, no committed timeline — see [decisions.md §Teams module status](../technical/decisions.md#multitenant-saas-architecture)), so their teams-driven horizon no longer applies and there is no near-term trigger pulling them into this batch. Finding 1 Option 2 (the persistence port) is independent of teams' timeline but still M-sized and scheduled for its own next planning cycle rather than this fix-plan pass. Pulling any of the three into this batch as full structural rewrites would be Tier 3. Every item below fit Tier 1–2 without splitting; SA60 (composite-FK policy + conformance gate) and SA63 (Finding 6's launcher-contract first step) are Tier 2, the rest are Tier 1.

> **Track status (2026-07-10, SA57–SA64 opened):** Track 1 — **2 open items** (SA59, SA60). SA58 completed. Track 2 — **2 open items** (SA57, SA64). Track 3 — **1 open item** (SA63). Track 3 completed: SA61, SA62.

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
SA58 — RLS boot guard rolsuper check    SA57 — DR media fallback fail-hard        SA61 — untrack test artifacts
SA59 — drop bypassrls auto-prime        SA64 — social admin → TenantModelAdmin    SA62 — validate TOML splice write
SA60 — composite-FK deferability                                                  SA63 — Finding 6 launcher-contract
  policy + conformance gate                                                         first step (start.sh/local.py.j2)
```

All three tracks run fully in parallel — no hard cross-track implementation dependencies exist; every task below touches files no other open task touches. Within Track 1, SA58/SA59/SA60 touch disjoint files (`orgs/apps.py`; `Makefile`+`scripts/test_unit.sh`; `orgs/tenancy.py`+`decisions.md`+forms migrations) so any order works, but doing SA58 before SA59 is convenient — SA59's fix (removing the blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export) is the change that makes SA58's guard fix observable in CI again. Within Track 3, SA63 touches `start.sh.j2`/`local.py.j2`/`production.py.j2` and is unrelated to SA61 (`.gitignore` + tracked-file removal) or SA62 (`module_dependency_sync.py`) — no ordering constraint. (The shared closeout files `CHANGELOG.md` and `docs/technical/roadmap.md` are the one cross-track exception — every track touches them during closeout, managed by the merge procedure above.)

### Track 1 — Tenant-context surface

SA47, SA48, SA49, SA50 are complete — detail in [CHANGELOG.md](../../CHANGELOG.md). SA50 folded the `JsonApiMixin`/`JsonOrganizationAccessMixin` stack into one `OrgApiBaseView` as part of the `json-api-boundary-idiom-fragmentation` finding (see [arch-audit.md Finding 5](../others/arch-audit.md)). New this pass: SA58–SA60, below.

#### Finding — `rls-boot-guard-misses-superuser` (`why →` [tech-audit.md TA48](../others/tech-audit.md))

- [x] **SA58 — Make the RLS boot guard check `rolsuper` as well as `rolbypassrls`.** `Tier 1 · Track 1 · deps: none`
  `orgs/apps.py:98-108` (`_check_rls_role`) queries only `rolbypassrls`, but PostgreSQL superusers bypass RLS regardless of that attribute and typically have `rolbypassrls = false` — so CI's default `postgres`-superuser connection, and any misconfigured deployment pointing `RUNTIME_DATABASE_URL` at a superuser role, boots cleanly with DB-level tenant isolation silently off (app-level `TenantManager` filtering still applies — this is a defense-in-depth loss, not direct exposure). decisions.md:1124 already states the runtime contract as `NOSUPERUSER/NOBYPASSRLS`; the guard only enforces half of it.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py:98-108`; `quickscale_modules/orgs/tests/test_rls_boot_guard.py`.
  *Acceptance:* the guard query becomes `SELECT rolbypassrls OR rolsuper …` (or equivalent two-column read with an OR in Python), the `ImproperlyConfigured` message names both attributes, and `test_rls_boot_guard.py`'s mocks are extended with a `rolsuper=True, rolbypassrls=False` case that must raise.
  *(why →* [tech-audit.md TA48](../others/tech-audit.md)*)*

#### Finding — `test-tooling-auto-primes-bypassrls-hatch` (`why →` [tech-audit.md TA49](../others/tech-audit.md))

- [ ] **SA59 — Stop auto-priming `QUICKSCALE_ALLOW_BYPASSRLS=1` in the test-unit path.** `Tier 1 · Track 1 · deps: none (do after SA58 for signal, not a hard dependency)`
  `Makefile:321-327` (`test-unit`) and `scripts/test_unit.sh:365-366` both blanket-export `QUICKSCALE_ALLOW_BYPASSRLS=1` for every module suite, which (a) disables the SA58 boot guard entirely during CI and local `make test-unit` runs and (b) flips the SA14.4 collection-time opt-in so `bypass_rls`-marked tests always run — contradicting the SA14.4 decision still documented at `quickscale_modules/orgs/tests/settings.py:14-18` and in every module conftest. Between this and TA48, no environment currently demonstrates the boot guard firing against a bypassing role.
  *Files:* `Makefile:321-327`; `scripts/test_unit.sh:365-366`; `.github/workflows/ci.yml:340` (verify the coverage gate's env after the export is removed).
  *Acceptance:* the blanket export is removed; CI's test-unit job runs against a NOBYPASSRLS role (create one via `QS_*_DB_USER` if the current CI role has BYPASSRLS/superuser — verify against the same container SA58's test targets), and developers set the SA14.4 hatch explicitly per-suite when they need it. `make test-unit` documents the opt-in in its help text if it doesn't already.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

#### Finding — `composite-fk-deferability-contract-diverged` (`why →` [tech-audit.md TA50](../others/tech-audit.md), [arch-audit.md Finding 4](../others/arch-audit.md) caution + Questions)

- [ ] **SA60 — Pick and enforce one composite-FK deferability policy.** `Tier 2 · Track 1 · deps: none`
  `6ea37301` silently flipped the Option C composite-FK helper (`orgs/tenancy.py:903`, `_ADD_COMPOSITE_FK_SQL`) from `DEFERRABLE INITIALLY DEFERRED` to `NOT DEFERRABLE`, with no decisions.md record and no test asserting the new behavior. This diverges from `forms/0007`'s own inlined `DEFERRABLE INITIALLY DEFERRED` SQL (and its `test_migrations.py:457-505` assertion) and from every *existing* database (fresh installs get `NOT DEFERRABLE`, existing ones keep `DEFERRABLE` — fleet drift with no aligning migration). Empirically verified this pass (PostgreSQL 18): `SET CONSTRAINTS <name> IMMEDIATE` on a `NOT DEFERRABLE` FK is a no-op, so `NOT DEFERRABLE` is defensible on fail-fast grounds — but it needs to be the *documented*, uniformly-applied policy, not a one-module drift. Bundle in the second, cheaper doc gap arch-audit flagged in the same commit: `is_tenant_model()`'s `tenant_excluded`-marker-beats-manager/base-class precedence change (`tenancy.py:1548+`) also has no decision record.
  *Files:* `docs/technical/decisions.md` (two new entries: composite-FK deferability policy under the Option C child-table section; `tenant_excluded` precedence rule); `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py:903` (helper SQL, if the decision changes it back) and `:1548+` (precedence — doc-only, no code change expected); `quickscale_modules/forms/src/quickscale_modules_forms/migrations/0007*.py` (align to the chosen policy); `quickscale_modules/forms/tests/test_migrations.py:457-505` and `quickscale_modules/crm/tests/test_migrations.py:1107,1158` (update assertions/stale comments to match); extend the SA35-style cross-module conformance gate to assert one deferability policy for all Option C composite FKs.
  *Acceptance:* decisions.md states the deferability policy (recommend keeping `NOT DEFERRABLE` given the empirical fail-fast verification, but ratify explicitly) and the `tenant_excluded` precedence rule; `forms/0007` and the `tenancy.py` helper emit the same deferability clause; a new conformance test fails if any Option C composite FK diverges; the two now-stale test comments (`crm/tests/test_migrations.py:1107,1158`) are corrected to reflect the no-op-on-NOT-DEFERRABLE behavior.
  *(why →* [tech-audit.md TA50](../others/tech-audit.md)*,* [arch-audit.md Finding 4](../others/arch-audit.md)*)*

### Track 2 — Module contracts & settings

SA21.2, SA37, SA38, SA40, SA43, SA51, SA52, SA53, SA54, plus its earlier share of the SA19–SA33 batch, are complete — detail in [CHANGELOG.md](../../CHANGELOG.md). The `backups-dispatch-fail-open-robustness` finding (SA52/SA53, `why →` [tech-audit.md TA46](../others/tech-audit.md)) is fully closed. New this pass: SA57 and SA64, below.

#### Finding — `dr-media-storage-fallback-swallows-misconfiguration` (`why →` [tech-audit.md TA47](../others/tech-audit.md), [arch-audit.md Red flags](../others/arch-audit.md))

- [x] **SA57 — Restore fail-hard behavior on DR media storage-backend resolution errors.** `Tier 1 · Track 2 · deps: none — Completed 2026-07-10.`
  `6ea37301` changed both `dr_engine/orchestration.py:1910-1913` (`_resolve_media_runtime`) and `dr_engine/_sidecar.py:54-58,102-108` (`_build_media_sync_manifest`) to wrap `select_storage_backend(settings)` in `except Exception: selection = None`, falling through to local-`MEDIA_ROOT` detection. This conflates the one legitimate fallback (storage module not installed — `ModuleNotFoundError`) with every other failure, including the `ImproperlyConfigured` SA30 made `select_storage_backend` raise specifically so misconfigured `QUICKSCALE_STORAGE_BACKEND`/S3 settings fail hard. An S3-media deployment whose storage settings don't resolve at DR-capture time silently walks the (likely empty/ephemeral) local `MEDIA_ROOT` and emits a `status: "ready"` manifest with the wrong inventory — `dr execute` media sync then "completes" against it, and the real media loss is discovered only at cutover. The same swallow applies to the *target*-runtime resolution on the sync side. The regression test that guarded the old behavior was renamed and its assertions flipped in the same commit to bless the new fallback (`backups/tests/test_services.py:2871-2888`), and the sidecar reintroduced a permissive `getattr(settings, "QUICKSCALE_STORAGE_BACKEND", "local")` read (`_sidecar.py:105`) — the coercion idiom SA17/SA30/SA42/SA48 removed elsewhere.
  *Files:* `quickscale_core/src/quickscale_core/dr_engine/orchestration.py:1910-1913`; `quickscale_core/src/quickscale_core/dr_engine/_sidecar.py:54-58,102-108`; `quickscale_modules/backups/tests/test_services.py:2871-2888`.
  *Acceptance:* both call sites catch only `ImportError`/`ModuleNotFoundError` (storage module absent → local-media project, the one sanctioned fallback); every other exception propagates — orchestration re-raises `BackupConfigurationError` with the original message, the sidecar returns the explicit `status: "unsupported"`/error-status payload with `error_type`. The `_sidecar.py:105` permissive `getattr` default is removed in favor of a direct required read. The flipped test is restored to assert `status == "unsupported"` / a raised `BackupConfigurationError` for an `ImproperlyConfigured`-raising mock, and a second new test pins the module-absent fallback so both behaviors stay covered.
  *Findings:* None.
  *(why →* [tech-audit.md TA47](../others/tech-audit.md)*)*

#### Finding — `social-admin-perorgadminmixin-prototype` (`why →` [arch-audit.md Red flags](../others/arch-audit.md))

- [ ] **SA64 — Port social's admin off the `PerOrgAdminMixin` prototype onto `TenantModelAdmin`.** `Tier 2 · Track 2 · deps: none`
  `social/admin.py:112-262` still runs its own near-duplicate of the per-org admin machinery that `orgs/admin.py`'s `TenantModelAdmin` (`:240-330`) already generalizes — `TenantModelAdmin`'s own docstring calls itself "the generalization of the `PerOrgAdminMixin` pattern that social/admin.py proves works under RLS." Drift is already real: social's copy lacks the VIEW-AS debug-session priority and the org-field form-locking the generalized base has. This is isolation-critical admin machinery (`_org_db_context` + view wrappers + fail-closed queryset) — same shape as the already-completed SA14.2/SA14.3 ports of crm/blog/forms/listings/billing.
  *Files:* `quickscale_modules/social/src/quickscale_modules_social/admin.py:112-262`; `quickscale_modules/orgs/src/quickscale_modules_orgs/admin.py:240-330` (base class, read-only reference); social's admin test suite.
  *Acceptance:* social's admin classes subclass `TenantModelAdmin` instead of the local `PerOrgAdminMixin` prototype; the prototype is deleted (not deprecated in place — nothing else uses it, per the arch-audit read); VIEW-AS debug-session priority and org-field locking now apply to social exactly as they do to the other five ported modules; existing social admin tests pass unchanged in behavior (isolation assertions), with new assertions for the two previously-missing behaviors.
  *(why →* [arch-audit.md Red flags](../others/arch-audit.md)*)*

### Track 3 — Core/CLI plumbing

SA44 (Finding 1 stage 1, `dr-engine-module-circular-lattice`), SA56 (Finding 5, `json-api-boundary-idiom-fragmentation`, now fully closed), SA61 (test artifacts untracked, gitignore patterns added, blog test media pointed at tmp_path), and SA62 (module pyproject TOML splice routed through the validated writer) are complete — detail in [CHANGELOG.md](../../CHANGELOG.md). New this pass: SA63, below.

#### Finding — `test-artifacts-committed-again` (`why →` [tech-audit.md TA51](../others/tech-audit.md), TA23 class)

- [x] **SA61 — Untrack accreting test artifacts and close the class with a gitignore fix.** `Tier 1 · Track 3 · deps: none`
  Tracked `pytest_log.txt` is updated at every commit (`.gitignore:232` covers `pytest_cov_log.txt` but not `pytest_log.txt`), and 13 (growing) `quickscale_modules/blog/tests/media/blog/uploads/2026/07/test-*.png` files have accumulated across the last two commits because blog's test `MEDIA_ROOT` writes into the working tree instead of a tmp path.
  *Files:* `.gitignore`; `pytest_log.txt` (git rm --cached); `quickscale_modules/blog/tests/media/` (git rm --cached the 13 PNGs); `quickscale_modules/blog/tests/` settings/conftest (point `MEDIA_ROOT` at a `tmp_path`/`TemporaryDirectory` fixture so the class can't recur for blog specifically).
  *Acceptance:* `git rm --cached` removes all 14 currently-tracked artifact files; `.gitignore` gains patterns for `pytest_log.txt` and `quickscale_modules/*/tests/media/`; blog's test suite no longer writes uploaded test media into a tracked path (verified by running the suite twice and confirming `git status` stays clean).
  *(why →* [tech-audit.md TA51](../others/tech-audit.md)*)*

#### Finding — `module-pyproject-splice-unvalidated` (`why →` [tech-audit.md TA52](../others/tech-audit.md), [arch-audit.md Red flags/Watchlist](../others/arch-audit.md))

- [x] **SA62 — Route the module pyproject TOML splice through the validated writer.** `Tier 1 · Track 3 · deps: none`
  `quickscale_cli/src/quickscale_cli/utils/module_dependency_sync.py`'s `_patch_module_path_dependencies` rewrites embedded-module `pyproject.toml` by line splicing and writes via bare `write_text()` (`:425-427`), skipping the `_write_validated_toml` guard its two sibling writers in the same file use. A malformed splice (e.g. a multi-line table entry) writes invalid TOML that breaks the subsequent `poetry lock` with no earlier signal. This is the third unvalidated splice function in this file per arch-audit's watchlist — fixing it now holds the "re-parse before writing" steelman that justifies the pattern at all.
  *Files:* `quickscale_cli/src/quickscale_cli/utils/module_dependency_sync.py` (`_patch_module_path_dependencies`, its sibling `_write_validated_toml`).
  *Acceptance:* `_patch_module_path_dependencies` writes through `_write_validated_toml` (parse-before-write) exactly like its two siblings; a regression test feeds a splice that would produce invalid TOML (e.g. an unterminated multi-line table entry) and asserts the write is rejected before touching disk, matching the sibling writers' existing test coverage.
  *(why →* [tech-audit.md TA52](../others/tech-audit.md)*)*

#### Finding — `db-privilege-mode-procedural`, first step (`why →` [arch-audit.md Finding 6](../others/arch-audit.md))

- [ ] **SA63 — Fix the createcachetable/boot-guard collision and start the launcher-owned env contract.** `Tier 2 · Track 3 · deps: none`
  Four mechanisms currently decide "does this process run under the superuser `DATABASE_URL` or the restricted `RUNTIME_DATABASE_URL`" with three different semantics (start.sh env-unset, production settings' argv ladder, local settings' argv switch introduced by `198a1951`, and the orgs boot guard's positional argv check) — and one collision already exists at source level: `start.sh.j2:59`'s `createcachetable` step (run when `REDIS_URL` is unset) executes under the superuser role but sets no `QUICKSCALE_ALLOW_BYPASSRLS=1`, so the boot guard (which exempts only `migrate`) should raise `ImproperlyConfigured` on any no-Redis Railway deploy at first boot. Per arch-audit's recommended fix order, this task does the one-line collision fix and Finding 6's first structural step together in one template pass, rather than the collision fix alone: add the env pair to start.sh's `createcachetable` line, and delete `local.py.j2`'s argv-sniffing branch in favor of the same launcher-owned `RUNTIME_DATABASE_URL`/`QUICKSCALE_ALLOW_BYPASSRLS` env pair (documented as a one-liner wrapper for bare `python manage.py migrate` in local dev). The full Option 1 contract (production settings becoming a pure env reader, deleting `orgs/apps.py`'s `_is_migrate_command()` in favor of the existing hatch) is the remainder of Finding 6 and stays open in arch-audit.md pending confirmation the collision fix alone doesn't already resolve the live defect.
  *Files:* `quickscale_core/src/quickscale_core/generator/templates/start.sh.j2` (add `QUICKSCALE_ALLOW_BYPASSRLS=1` to the `createcachetable` line); `quickscale_core/src/quickscale_core/generator/templates/local.py.j2` (delete the argv-sniffing branch, use the env pair); generated-project e2e/boot test coverage for the no-Redis path.
  *Acceptance:* a generated project with `REDIS_URL` unset boots `createcachetable` successfully under the runtime role (or, if intentionally superuser, passes the boot guard because the env pair is now set) — verified by booting a generated app with `REDIS_URL` unset per arch-audit's suggested empirical check; `local.py.j2` no longer inspects `sys.argv`; local dev's `python manage.py migrate` UX is preserved via the documented wrapper.
  *(why →* [arch-audit.md Finding 6](../others/arch-audit.md)*)*

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
