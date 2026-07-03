# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work, plus recently-completed handoff)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks pending roadmap work and, when open items are resolved, a brief recently-completed handoff section. Detailed completed implementation history remains in [CHANGELOG.md](../../CHANGELOG.md). Each phase is sized as Adaptive Tier 1–2; split before implementing if a checklist item is Tier 3.

**Rules:**
- Keep open todo items here, plus optionally a recently-completed handoff section.
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

### Structural Autopsy Remediation II (opened 2026-07-02)

Fix plan derived from the [2026-07-02 repo-level autopsy](../../findings.md#autopsy--2026-07-02) and the [2026-07-02 module-by-module autopsy](../../findings.md#module-by-module-autopsy--2026-07-02). Each task below is sized Adaptive **Tier 1 or Tier 2** (one concern, statable in one sentence). Tenant-isolation and money-ledger work is sensitive-domain → `RISK LEVEL: medium` → floors at Tier 2. Two items that would be Tier 3 as a whole (the full declarative-wiring migration across all modules, and the full orgs-registry inversion) have been split: only the first credible slice is scheduled now; the remainder is tracked as a per-module/per-step follow-on, not in this batch — matching the precedent set by SA5.2. Every task carries a `why →` link to the finding it closes.

**Naming:** `SAn.m` continues the sequence from the closed 2026-06-30 remediation (`SA1`–`SA5`); this batch starts at `SA6` to avoid collision. `SA6`–`SA10` close repo-level findings, `SA11`–`SA12` close module-level findings.

**Priority note:** SA11.1–SA11.4 close the **live defect** (anonymous public pages render empty under the hardened production RLS posture — Module Finding 1) and should be the first work landed regardless of track scheduling below. SA11.5 should stay in that first landing batch because it closes the broader Module Finding 1 hardening work immediately adjacent to the defect chain.

#### Dependency & parallelization overview (2026-07-02 status)

`SA12.1`, `SA9.1`, `SA6.1`, `SA6.2`, `SA6.3`, and `SA7.1` shipped and merged — see [CHANGELOG.md](../../CHANGELOG.md). Diagram below shows only remaining open work.

```
Track 1 (tenant-context surface)     Track 2 (money ledger + core boundary)    Track 3 (wiring governance + org-switch)
───────────────────────────────      ───────────────────────────────────      ────────────────────────────────────────
SA11.1 groundwork committed,         SA9.2  (no deps)                         SA7.2  (no deps)
  decision resolved, impl pending    SA9.3  (no deps)                         SA7.3  (no deps)
  ├─ SA11.2 (←11.1, pending impl)      ├─ SA9.4 (←9.3)                        SA7.4  (no deps)
  ├─ SA11.3 (←11.1, pending impl)      └─ SA9.5 (←9.3)                        SA8.1  (no deps)
  └─ SA11.4 (←11.1, pending impl)          └─ SA9.6 (←9.4 & ←9.5)               └─ SA8.2 (←8.1)
SA11.5 (no deps — clean)             SA10.1 (no deps)                             └─ SA8.3 (←8.2)
SA11.6 (no deps — clean)               └─ SA10.2 (←10.1)
SA11.7 (no deps — clean)
```

No cross-track dependencies. Cross-track file-ownership note: `quickscale_modules/crm/` is touched by **both** Track 1 (`SA11.6` — `views.py` cleanup) and Track 3 (`SA7.1` — new `signals.py`/`services.py` receiver + `apps.py` wiring); the two tasks touch disjoint files inside the package, but track owners should confirm no overlap before merge-back, same as the SA3.2/SA1.3 precedent.

#### Track summary

| Track | Tasks (in order) | Theme |
|-------|------------------|-------|
| **1** | SA11.1 *(decision resolved, impl pending)* → SA11.2/SA11.3/SA11.4 *(pending SA11.1 impl)* · SA11.5 → SA11.6 → SA11.7 *(clean, no dep on SA11.1)* | Tenant-context request boundary — fixes the live public-page defect |
| **2** | SA9.2 → SA9.3 → SA9.4/SA9.5 → SA9.6 · SA10.1 → SA10.2 | Billing ledger idempotency + core-as-runtime-API boundary + contract-vintage detection |
| **3** | SA7.1 *(completed)* → SA7.2 → SA7.3 → SA7.4 · SA8.1 → SA8.2 → SA8.3 | Declarative-wiring migration slice + orgs god-module de-coupling + D1 explicit-org contract |

#### Track status (as of 2026-07-02)

- **Track 1 — unblocked, implementation pending.** The design decision blocking `SA11.1` (`CR-SA11.1-001`) resolved 2026-07-02 — see below. No further decision is needed; the remaining work is implementation: force `TemplateResponse.render()` inside `org_scope()` in `PublicSystemOrgReadMixin.dispatch()`, then add the real `ListView`/`TemplateResponse` render-lifecycle test (`CR-SA11.1-002`). Once that lands, `SA11.2`/`SA11.3`/`SA11.4` can proceed. `SA11.5`, `SA11.6`, `SA11.7` have no dependency on `SA11.1` and remain clean to start in parallel.
- **Track 2 — clean.** No blockers; `SA9.2` and `SA9.3` are independent and can run in parallel, as can `SA10.1`.
- **Track 3 — clean.** `SA7.1` is complete (see below); the next pending item is `SA7.2`, and `SA7.3`–`SA7.4` plus `SA8.1`–`SA8.3` remain unblocked by dependencies.

#### Track 1 status snapshot (2026-07-03)

- **Delivered but still open:** SA11.1 groundwork is committed in the Track 1 worktree (`quickscale_modules_orgs/public_context.py` + 17 unit tests), but the checklist item stays open until the independent-review blockers below are resolved.
- **Pending + blocked on SA11.1 closeout:** SA11.2 should wait until SA11.1's review findings are closed, and SA11.3/SA11.4 should wait for both that closeout and the request-boundary decision because they are the first public views that would adopt the helper seam.
- **Pending after the live-defect chain:** SA11.5 remains in the first landing batch because it closes the broader Module Finding 1 hardening work, while SA11.6 and SA11.7 stay queued after that batch.
- **Decision still needed before public-view adoption:** decide whether request-scoped public views should keep `org_scope()` as the mixin boundary or switch the mixin seam to a non-atomic caller-managed `transaction.atomic()` + `tenant_context()` pattern.

---

#### Finding — Module Finding 1: request→tenant-context boundary (`why →` [Module Finding 1](../../findings.md#module-finding-1-the-requesttenant-context-boundary-is-a-per-module-convention-with-divergent-idioms--and-bloglistings-public-pages-read-as-empty-under-the-hardened-production-posture))

- [ ] **SA11.1 — Orgs-owned public-read context helper (implementation landed; closeout blocked).** `Tier 2 · Track 1 · deps: none · RISK LEVEL: medium`
  Add a helper in the orgs module (new file, e.g. `quickscale_modules_orgs/public_context.py`) that both scopes a queryset to a given organization *and* primes the tenant `ContextVar`/GUC (`tenant_context(...)`) in one call — generalizing the idiom already proven correct in `quickscale_core/manifest/social_manifest.py:444–447`. Ship as a mixin (`PublicSystemOrgReadMixin`) and a plain function for non-CBV call sites.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/public_context.py` (new).
  *Acceptance:* helper filters by the passed organization and leaves the GUC primed for the duration of the call; unit test confirms a query under the restricted role returns rows when using the helper and `.none()`-equivalent behavior is preserved when no org resolves.

  > **2026-07-02 checkpoint — groundwork committed, implementation resuming after decision.**
  > Code delivered: `resolve_public_org_context()` plain function, `PublicSystemOrgReadMixin` CBV seam (overrides `dispatch()` with `org_scope()`), and 17 unit tests covering org resolution, real tenant-scoped queries, fail-closed no-org path, and mixin dispatch lifecycle.
  >
  > **`CR-SA11.1-001` (high) — RESOLVED 2026-07-02.** Root cause: `org_scope()`'s `transaction.atomic()` block (and the `SET LOCAL app.current_org_id` GUC inside it) closes the instant `dispatch()` returns — but template-backed generic views (`ListView`/`DetailView`, SA11.3/SA11.4's target) return an unrendered `TemplateResponse`; Django calls `.render()` on it *after* `dispatch()` returns, so any queryset lazily evaluated during template rendering runs with no GUC set and RLS silently returns zero rows — reproducing Module Finding 1 inside its own fix.
  > **Decision:** keep `org_scope()` as the mixin's transaction boundary (preserves the one-shared-seam shape Module Finding 1 calls for, instead of pushing transaction discipline back onto every call site). Fix: in `dispatch()`, after calling `super().dispatch()`, if the response is unrendered (has a `.render()` method, e.g. `TemplateResponse`), call `.render()` on it before returning — still inside the `with org_scope():` block, so lazy queryset evaluation happens while the GUC is still primed. Does not cover genuinely streamed responses (not in use for QuickScale's public pages today — note this as a documented limitation in the mixin's docstring).
  >
  > **Remaining before SA11.1 closes (implementation, not a decision):**
  > - Implement the `.render()`-forcing change in `PublicSystemOrgReadMixin.dispatch()`.
  > - `CR-SA11.1-002` (medium, still open) — add a test that exercises a real `ListView`/`TemplateResponse` render lifecycle under the mixin (not just the unit tests against plain views/functions) to prove the fix actually closes the gap for the views SA11.3/SA11.4 will build.

- [ ] **SA11.2 — Restricted-role anonymous-read E2E smoke.** `Tier 2 · Track 1 · deps: SA11.1 · RISK LEVEL: medium`
  Add an integration test that runs against the restricted `NOBYPASSRLS` runtime role (not the superuser test posture used elsewhere) and asserts an anonymous request to a public blog page returns a published System-org post. This is the single test that covers the whole defect class.
  *Files:* new test under `quickscale_modules/blog/tests/` (or a shared restricted-role harness in `tests_shared/isolation.py`).
  *Acceptance:* test fails on current `main` (proving it reproduces the defect) and passes once SA11.3 lands.

- [ ] **SA11.3 — Migrate blog public views to the helper.** `Tier 1 · Track 1 · deps: SA11.1`
  Convert `_resolve_org_for_read`/`_scope_by_org` to use `SA11.1`'s helper so anonymous reads prime the GUC instead of only filtering.
  *Files:* `quickscale_modules/blog/src/quickscale_modules_blog/views.py`.
  *Acceptance:* SA11.2 passes; existing blog test suite stays green.

- [ ] **SA11.4 — Migrate listings public views to the helper.** `Tier 1 · Track 1 · deps: SA11.1`
  Same conversion for the listings module's public list/detail views.
  *Files:* `quickscale_modules/listings/src/quickscale_modules_listings/views.py`.
  *Acceptance:* restricted-role anonymous read of a published System-org listing returns rows; existing listings tests stay green.

- [ ] **SA11.5 — Generated-project DRF permission baseline.** `Tier 1 · Track 1 · deps: none`
  Emit `REST_FRAMEWORK = {"DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"]}` from the generator's settings wiring so module APIs default to authenticated-only unless a view explicitly opts into public access, instead of relying on DRF's `AllowAny` default.
  *Files:* `quickscale_core/src/quickscale_core/generator/templates/` (settings template).
  *Acceptance:* a fresh generation's settings include the explicit DRF default; existing module API tests (which authenticate explicitly) stay green.

- [ ] **SA11.6 — Clean up CRM's `_resolve_active_org`.** `Tier 1 · Track 1 · deps: none`
  Remove the "for tests that bypass middleware" personal-org fallback from production code (move it into test fixtures/middleware instead) and stop performing the stage-seeding write as a side effect of every org resolution — seed once at org-creation time instead.
  *Files:* `quickscale_modules/crm/src/quickscale_modules_crm/views.py`.
  *Acceptance:* `_resolve_active_org` only resolves and primes context; CRM test suite stays green with fixtures updated to set `request.org` directly.

- [ ] **SA11.7 — Fail-hard the auth signup-open default.** `Tier 1 · Track 1 · deps: none`
  Replace the permissive `getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)` fallback with a required-setting read (raise `ImproperlyConfigured` if unset), consistent with the fail-hard principle.
  *Files:* `quickscale_modules/auth/src/quickscale_modules_auth/adapters.py`.
  *Acceptance:* omitting `ACCOUNT_ALLOW_REGISTRATION` from settings raises at startup instead of silently defaulting to open registration.

---

#### Finding — Repo Finding 4: core-as-runtime-API boundary (`why →` [Finding 4](../../findings.md#finding-4-quickscalecores-entire-internal-surface-is-a-de-facto-runtime-api-for-user-owned-generated-projects--with-an-open-ended-version-range-and-a-repo-wide-clean-break-policy))

- [x] **SA9.1 — Compatible-range pin for backups' core dependency.** `Tier 1 · Track 2 · deps: none`
  Changed `quickscale-core>=0.86.0` to `>=0.86.0,<0.87.0` in module.yml. Updated `sync_project_module_dependencies` to fall back to the manifest version spec when the module's pyproject.toml declares a non-string (path/table) dependency, so generated projects receive a bounded version range instead of a developer-only path entry. Wired `_sync_module_dependencies` into `_update_single_module` so `quickscale update` also refreshes generated-project dependencies after subtree pull.
  *Files:* `quickscale_modules/backups/module.yml`, `quickscale_cli/src/quickscale_cli/utils/module_dependency_sync.py`, `quickscale_cli/src/quickscale_cli/commands/module_commands.py`.
  *Acceptance:* a fresh embed of backups writes a bounded core version range into the generated project's `pyproject.toml`.

- [ ] **SA9.2 — CI job: module-vs-oldest-claimed-core import check.** `Tier 1 · Track 2 · deps: none · RISK LEVEL: medium`
  Added `scripts/check_module_core_compatibility.py` — a two-phase script that (1) statically analyses each module's `quickscale_core` imports against the on-disk core source, and (2) performs a real install/import probe: for each module with a quantifiable minimum core version, creates an isolated venv, installs `quickscale-core==<min_claimed>` plus the module's non-core deps, and imports the module's package and key submodules. Wired as `make check-core-compat`, added as step 3/6 in `scripts/check_ci_locally.sh`, and added as a `module-core-compat` gate job in `.github/workflows/ci.yml` that the `test` job depends on. Included in `make check`.
  *Files:* `scripts/check_module_core_compatibility.py`, `Makefile`, `scripts/check_ci_locally.sh`, `.github/workflows/ci.yml`.
  *Acceptance:* `make check-core-compat` passes; the script fails if a module imports a core symbol not present in the current core source, if a module's minimum claimed core version exceeds the repository's VERSION, or if any module with a claimed minimum core version cannot be imported against `quickscale-core==<min_claimed>` in an isolated environment. The `test` CI job will not run unless the `module-core-compat` gate passes. Pass `--skip-install-probe` to skip the heavy runtime check for local development.
  *Discovered finding:* The embedded manifest copy at `quickscale_core/src/quickscale_core/data/manifests/backups/module.yml` still declares `quickscale-core>=0.86.0` (missing the `<0.87.0` upper bound applied in SA9.1 to the authoritative `quickscale_modules/backups/module.yml`). This drift does not block SA9.2 but should be cleaned up to keep the embedded manifest consistent with the shipped inventory. Tracked separately as **SA9.2-FINDING-001** — remains advisory and non-blocking.

  > **2026-07-03 checkpoint — code delivered, install/import probe reveals pre-existing version mismatch — blocked.**
  > Code delivered: `check_module_core_compatibility.py` (two-phase static analysis + real install/import probe), `Makefile` wiring (`make check-core-compat`), `.github/workflows/ci.yml` gate job, `scripts/check_ci_locally.sh` step.
  >
  > **Blocking (pre-existing condition surfaced by the new probe, not created by SA9.2):**
  > - The real install/import probe fails on `quickscale_modules_backups.services` because **no published `quickscale-core` release in the range `>=0.86.0,<0.87.0` contains `quickscale_core.dr_engine`**. Backups' `module.yml` declares compatibility with a version range that does not satisfy its actual import requirements. This is a pre-existing discrepancy between the module's declared compatibility and the published core's API surface — the CI gate is working as designed and correctly caught a latent defect.
  >
  > **Decision needed:** How to resolve the pre-existing compatibility gap between backups' declared `quickscale-core>=0.86.0,<0.87.0` range and the published core's missing `dr_engine` subpackage. Options include: (a) publish a `quickscale-core` 0.86.x release that includes `dr_engine` so the range aligns with the actual API surface, (b) narrow the `module.yml` range to a version that includes `dr_engine` (or add a `>=` floor that matches), or (c) skip the install probe for backups only until the facade work (SA9.3–SA9.5) eliminates the deep import. SA9.2-FINDING-001 remains advisory and non-blocking; any of the above options would also fix it incidentally.

- [ ] **SA9.3 — `quickscale_core.runtime` public facade.** `Tier 2 · Track 2 · deps: none`
  Create a facade module re-exporting the specific symbols module code is known to need today (the DR adapter surface: `capture_snapshot`, `fetch_snapshot_report`, `record_verification`, `set_rollback_pin`, `build_database_plan`, `execute_database_restore`, `sync_media`; plus the social-manifest rendering surface). No behavior change — pure re-export layer.
  *Files:* `quickscale_core/src/quickscale_core/runtime.py` (new).
  *Acceptance:* facade importable and re-exports match the DR adapter's public surface; no existing import path removed yet (that's SA9.4/SA9.5).

- [ ] **SA9.4 — Migrate backups' deep `dr_engine` imports to the facade.** `Tier 2 · Track 2 · deps: SA9.3`
  Repoint `services.py` and the seven management commands from `quickscale_core.dr_engine.{orchestration,primitives,recovery,verification,adapter}` to `quickscale_core.runtime`.
  *Files:* `quickscale_modules/backups/src/quickscale_modules_backups/services.py`, `quickscale_modules/backups/src/quickscale_modules_backups/management/commands/*.py`.
  *Acceptance:* backups test suite green with zero remaining `from quickscale_core.dr_engine` imports outside `quickscale_core` itself.

- [ ] **SA9.5 — Migrate social's deep core imports to the facade.** `Tier 2 · Track 2 · deps: SA9.3`
  Repoint `social/adapter.py` from `quickscale_core.contracts.{module_options,resolvers}` and `quickscale_core.manifest.{assembler,resolver,social_manifest}` to `quickscale_core.runtime`.
  *Files:* `quickscale_modules/social/src/quickscale_modules_social/adapter.py`.
  *Acceptance:* social test suite green with imports going through the facade only.

- [ ] **SA9.6 — CI import-linter gate.** `Tier 1 · Track 2 · deps: SA9.4 & SA9.5`
  Add a CI check that fails if any file under `quickscale_modules/*/src/` imports `quickscale_core` from outside `quickscale_core.runtime` (or another explicitly documented allowlist entry).
  *Files:* new CI script (e.g. `scripts/check_module_core_imports.py`).
  *Acceptance:* introducing a new deep-internal import from a module fails CI; the current (post-SA9.4/9.5) import set passes.

---

#### Finding — Repo Finding 5: module↔generated-project contract drift (`why →` [Finding 5](../../findings.md#finding-5-the-modulegenerated-project-contract-drifts-by-design--every-release-accretes-existing-projects-must-manually-adopt-steps-with-no-mechanism-to-apply-them))

- [ ] **SA10.1 — `project_contract` version in state.yml.** `Tier 1 · Track 2 · deps: none`
  Record the generator/contract version a project was generated against in `.quickscale/state.yml` at generation time.
  *Files:* `quickscale_core/src/quickscale_core/schema/state_schema.py`, generator state-writing path.
  *Acceptance:* a fresh generation's `state.yml` includes `project_contract`; existing state-file tests updated for the new field.

- [ ] **SA10.2 — `quickscale status` contract-vintage check.** `Tier 2 · Track 2 · deps: SA10.1`
  Compare each installed module's declared minimum project-contract requirement against the project's recorded `project_contract` and print the specific manual-adoption steps when the project is behind.
  *Files:* `quickscale_cli/src/quickscale_cli/commands/status_command.py`.
  *Acceptance:* `quickscale status` on a project generated before a contract-requiring module update names the gap and the manual step, instead of silence.

---

#### Finding — Repo Finding 1: wiring fan-out / two coexisting mechanisms (`why →` [Finding 1](../../findings.md#finding-1-per-module-integration-knowledge-is-fanned-across-three-packages-with-two-wiring-mechanisms-coexisting-and-the-declared-migration-unscheduled))

- [x] **SA6.3 — Update the imperative-wiring freeze guardrail.** `Tier 1 · Track 3 · deps: SA6.2`
  Extend `test_imperative_inventory.py` so it also asserts listings stays migrated (mirroring the existing analytics assertion), preventing regression back to imperative wiring.
  *Files:* `quickscale_core/tests/test_imperative_inventory.py`.
  *Acceptance:* re-introducing an imperative listings builder fails this test.

---

#### Finding — Repo Finding 2: orgs composition god module (`why →` [Finding 2](../../findings.md#finding-2-orgs-is-becoming-the-composition-god-module--inter-module-integration-is-hand-wired-pairwise-with-no-contract-and-the-central-tenant-registry-couples-all-module-versions-in-lockstep))

- [x] **SA7.1 — `organization_created` signal replaces CRM bootstrap reverse-import.** `Tier 1 · Track 3 · completed 2026-07-02`
  Added an `organization_created` Django signal in `orgs/signals.py`, fired from `OrgCreateForm.save()`. Converted `crm_bootstrap.maybe_seed_crm_default_stages` into a CRM-side receiver (`crm/signals.py`) connected via `QuickscaleCrmConfig.ready()`. Deleted `crm_bootstrap.py` and its import from `forms.py`. Acceptance verified: org creation still seeds CRM default stages when CRM is installed, orgs contain zero CRM-specific code, personal-org path preserved (no signal from `create_personal_for`), and the composition seam pattern is established for future cross-module behavior.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/signals.py` (new), `quickscale_modules/orgs/src/quickscale_modules_orgs/forms.py` (modified), `quickscale_modules/orgs/src/quickscale_modules_orgs/crm_bootstrap.py` (deleted), `quickscale_modules/crm/src/quickscale_modules_crm/signals.py` (new), `quickscale_modules/crm/src/quickscale_modules_crm/apps.py` (modified).
  *Findings:* None — no blockers discovered. The CRM view-level warm-on-read behavior in `crm/views.py` is untouched and continues to provide the secondary bootstrap path for personal orgs and migrated orgs that bypass the form flow.

- [ ] **SA7.2 — Fail-hard the auth-adapter import fallback.** `Tier 1 · Track 3 · deps: none`
  Replace the silent `try: from quickscale_modules_auth.adapters import ... except ImportError: fallback to DefaultAccountAdapter` with an explicit check: if auth is a declared dependency (it is, transitively, via allauth), require it; only allow the fallback in an explicitly test-only code path, not production import resolution.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/adapters.py`.
  *Acceptance:* orgs-without-auth-installed either raises a clear configuration error or the fallback is demonstrably confined to test contexts (per `decisions.md` §fail-hard-principle).

- [ ] **SA7.3 — De-duplicate notifications defaults out of orgs' manifest.** `Tier 1 · Track 3 · deps: none`
  Remove the inlined `default_config` block for notifications from `orgs/module.yml`'s `implies:` section; reference notifications' own canonical defaults instead of copying them.
  *Files:* `quickscale_modules/orgs/module.yml`, `quickscale_modules/notifications/module.yml`.
  *Acceptance:* embedding orgs still applies the same notifications defaults as before, sourced from one place; a doc/test asserts the two files can't drift (mirroring the SA3.2 doc-consistency gate pattern).

- [ ] **SA7.4 — Version-range constraints on `required_modules`.** `Tier 2 · Track 3 · deps: none`
  Add a minimum-version constraint to each module's `required_modules: [orgs]` declaration (billing, blog, crm, social — the four modules that declare it today) and make `_validate_module_prerequisites` in `apply_command.py` fail closed when an installed module's required-module version is below the declared minimum.
  *Files:* `quickscale_modules/{billing,blog,crm,social}/module.yml`, `quickscale_cli/src/quickscale_cli/commands/apply_command.py` (`_validate_module_prerequisites`).
  *Acceptance:* `quickscale apply` refuses to proceed when an installed `orgs` version is older than a dependent module's declared minimum, with an explicit error naming both versions.

---

#### Finding — Repo Finding 3: dual source of truth for active organization (`why →` [Finding 3](../../findings.md#finding-3-active-organization-has-two-sources-of-truth-in-generated-saas-apps--the-server-session-and-the-spas-client-state--and-the-shipped-resolution-was-to-amputate-features-d1-option-b))

- [ ] **SA8.1 — D1 Option A decision record: explicit-org API contract.** `Tier 1 · Track 3 · deps: none`
  Write the deferred D1 Option A decision: org-scoped JSON APIs take the org slug/id explicitly in the request (path or body) and the server validates membership per request; ambient session scoping is reserved for server-rendered flat routes only. Update `decisions.md` §D1 to record this as the chosen direction (superseding "Option A deferred").
  *Files:* `docs/technical/decisions.md`.
  *Acceptance:* `decisions.md` §D1 states the explicit-org contract as decided, with the scope of "org-scoped API" defined precisely enough for SA8.2 to implement against.

- [ ] **SA8.2 — Membership-validating request wrapper for org-scoped endpoints.** `Tier 2 · Track 3 · deps: SA8.1 · RISK LEVEL: medium`
  Add a reusable server-side decorator/mixin (extending the existing `require_org_role`/`OrgRoleMixin` pattern in `permissions.py`) that resolves the org from an explicit request parameter (not the session), validates the requesting user's membership, and sets tenant context for the duration of the request.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/permissions.py`.
  *Acceptance:* a request naming an org the user is not a member of is rejected regardless of the session's active org; a request naming an org the user belongs to succeeds even if it differs from the session's active org.

- [ ] **SA8.3 — Theme `useApi`/`useOrgs` explicit-org contract.** `Tier 2 · Track 3 · deps: SA8.2`
  Update the generated React theme's API hooks to pass the explicit org (from client state) on every org-scoped request instead of relying on the ambient session, using SA8.2's validated endpoints.
  *Files:* `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/src/hooks/{useApi.ts.j2,useOrgs.ts.j2}`.
  *Acceptance:* switching org client-side and immediately firing an org-scoped query resolves the newly-selected org, not the previous session org (manual verification: switch org, inspect the next request's resolved org server-side).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [findings.md](../../findings.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
