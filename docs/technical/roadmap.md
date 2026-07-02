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

**Priority note:** SA11.1–SA11.5 close a **live defect** (anonymous public pages render empty under the hardened production RLS posture — Module Finding 1) and should be the first work landed regardless of track scheduling below.

#### Dependency & parallelization overview

```
Track 1 (tenant-context surface)     Track 2 (money ledger + core boundary)    Track 3 (wiring governance + org-switch)
───────────────────────────────      ───────────────────────────────────      ────────────────────────────────────────
SA11.1 (no deps)                     SA12.1 (no deps)                         SA6.1  (no deps)
  ├─ SA11.2 (←11.1)                  SA9.1  (no deps)                           └─ SA6.2 (←6.1)
  ├─ SA11.3 (←11.1)                  SA9.2  (no deps)                                └─ SA6.3 (←6.2)
  └─ SA11.4 (←11.1)                  SA9.3  (no deps)                          SA7.1  (no deps)
SA11.5 (no deps)                       ├─ SA9.4 (←9.3)                         SA7.2  (no deps)
SA11.6 (no deps)                       └─ SA9.5 (←9.3)                         SA7.3  (no deps)
SA11.7 (no deps)                           └─ SA9.6 (←9.4 & ←9.5)              SA7.4  (no deps)
                                      SA10.1 (no deps)                         SA8.1  (no deps)
                                        └─ SA10.2 (←10.1)                       └─ SA8.2 (←8.1)
                                                                                     └─ SA8.3 (←8.2)
```

No cross-track dependencies. Cross-track file-ownership note: `quickscale_modules/crm/` is touched by **both** Track 1 (`SA11.6` — `views.py` cleanup) and Track 3 (`SA7.1` — new `signals.py`/`services.py` receiver + `apps.py` wiring); the two tasks touch disjoint files inside the package, but track owners should confirm no overlap before merge-back, same as the SA3.2/SA1.3 precedent.

#### Track summary

| Track | Tasks (in order) | Theme |
|-------|------------------|-------|
| **1** | SA11.1 → SA11.2/SA11.3/SA11.4 → SA11.5 → SA11.6 → SA11.7 | Tenant-context request boundary — fixes the live public-page defect |
| **2** | SA12.1 → SA9.1 → SA9.2 → SA9.3 → SA9.4/SA9.5 → SA9.6 → SA10.1 → SA10.2 | Billing ledger idempotency + core-as-runtime-API boundary + contract-vintage detection |
| **3** | SA6.1 → SA6.2 → SA6.3 · SA7.1 → SA7.2 → SA7.3 → SA7.4 · SA8.1 → SA8.2 → SA8.3 | Declarative-wiring migration slice + orgs god-module de-coupling + D1 explicit-org contract |

---

#### Finding — Module Finding 1: request→tenant-context boundary (`why →` [Module Finding 1](../../findings.md#module-finding-1-the-requesttenant-context-boundary-is-a-per-module-convention-with-divergent-idioms--and-bloglistings-public-pages-read-as-empty-under-the-hardened-production-posture))

- [ ] **SA11.1 — Orgs-owned public-read context helper.** `Tier 2 · Track 1 · deps: none · RISK LEVEL: medium`
  Add a helper in the orgs module (new file, e.g. `quickscale_modules_orgs/public_context.py`) that both scopes a queryset to a given organization *and* primes the tenant `ContextVar`/GUC (`tenant_context(...)`) in one call — generalizing the idiom already proven correct in `quickscale_core/manifest/social_manifest.py:444–447`. Ship as a mixin (`PublicSystemOrgReadMixin`) and a plain function for non-CBV call sites.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/public_context.py` (new).
  *Acceptance:* helper filters by the passed organization and leaves the GUC primed for the duration of the call; unit test confirms a query under the restricted role returns rows when using the helper and `.none()`-equivalent behavior is preserved when no org resolves.

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

#### Finding — Module Finding 2: billing webhook idempotency (`why →` [Module Finding 2](../../findings.md#module-finding-2-billing-webhook-idempotency-is-procedural-flag--check-then-act-with-no-database-backstop-on-the-money-ledger))

- [x] **SA12.1 — DB-enforced ledger idempotency.** `Tier 2 · Track 2 · deps: none · RISK LEVEL: medium`
  Add a partial unique index on `CreditTransaction` over `(stripe_event_id, transaction_type)` where `stripe_event_id <> ''`, and make `credit_user` catch `IntegrityError` and return the existing row instead of relying solely on the pre-lock `_find_existing_credit_transaction` read.
  *Files:* `quickscale_modules/billing/src/quickscale_modules_billing/models.py` (constraint), new migration, `quickscale_modules/billing/src/quickscale_modules_billing/services.py` (`credit_user`).
  *Acceptance:* a test that fires two concurrent `credit_user` calls with the same `stripe_event_id` results in exactly one `CreditTransaction` row and a correct `balance_after`.

---

#### Finding — Repo Finding 4: core-as-runtime-API boundary (`why →` [Finding 4](../../findings.md#finding-4-quickscalecores-entire-internal-surface-is-a-de-facto-runtime-api-for-user-owned-generated-projects--with-an-open-ended-version-range-and-a-repo-wide-clean-break-policy))

- [x] **SA9.1 — Compatible-range pin for backups' core dependency.** `Tier 1 · Track 2 · deps: none`
  Changed `quickscale-core>=0.86.0` to `>=0.86.0,<0.87.0` in module.yml. Updated `sync_project_module_dependencies` to fall back to the manifest version spec when the module's pyproject.toml declares a non-string (path/table) dependency, so generated projects receive a bounded version range instead of a developer-only path entry. Wired `_sync_module_dependencies` into `_update_single_module` so `quickscale update` also refreshes generated-project dependencies after subtree pull.
  *Files:* `quickscale_modules/backups/module.yml`, `quickscale_cli/src/quickscale_cli/utils/module_dependency_sync.py`, `quickscale_cli/src/quickscale_cli/commands/module_commands.py`.
  *Acceptance:* a fresh embed of backups writes a bounded core version range into the generated project's `pyproject.toml`.

- [ ] **SA9.2 — CI job: module-vs-oldest-claimed-core import check.** `Tier 1 · Track 2 · deps: none`
  Add a CI job that installs each module against the *oldest* core version its `module.yml` claims and imports the module, so a drift between claimed and actual minimum compatibility fails loudly instead of silently.
  *Files:* new CI workflow step / script under `scripts/`.
  *Acceptance:* the job fails if a module imports a core symbol not present in its manifest's minimum core version.

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

- [x] **SA6.1 — `module.yml` `derivation:` YAML loader.** `Tier 2 · Track 3 · deps: none`
  Implement the deferred YAML loading for `ModuleDerivationSchema` (declared but unimplemented per `decisions.md` §Module Derivation Schema) so a module can declare its normalization/validation/derivation rules in `module.yml` instead of a hand-written `_build_<module>_derivation_schema()` Python function.
  *Files:* `quickscale_core/src/quickscale_core/manifest/derivation.py`, `quickscale_core/src/quickscale_core/manifest/loader.py`.
  *Acceptance:* a `module.yml` with a `derivation:` section round-trips through `yaml.safe_load` into a `ModuleDerivationSchema` equal to a directly-constructed hand-built schema for a sample module, with all seven field categories preserved (normalization_rules, validation_rules, legacy_aliases, derived_settings at both module and per-option level, wiring_projections, and option_derivations); no runtime behavior change yet.
  *Note:* Module-level `derived_settings` are now preserved via the `shared_derived_settings` field on `ModuleDerivationSchema` and wired through `build_schema_from_manifest()`. The round-trip test uses directly-constructed dataclasses for the hand-built reference to eliminate shared-helper bias.

- [ ] **SA6.2 — Migrate `listings` onto the derivation loader end-to-end.** `Tier 2 · Track 3 · deps: SA6.1`
  Move listings' config (defaults, normalization, validation) into `module.yml`'s `derivation:` section; delete `_build_listings_derivation_schema` and the `default_/normalize_/resolve_/validate_listings_module_options` functions from `resolvers.py`; delete the listings triad from `module_config.py`; confirm the listings adapter (already core-inline per `entry_point.py:457`) now sources its schema from the loaded manifest. Include listings' own `required_modules: [orgs]` version-range addition in this task (see SA7.4 scope note).
  *Files:* `quickscale_modules/listings/module.yml`, `quickscale_core/src/quickscale_core/contracts/resolvers.py`, `quickscale_core/src/quickscale_core/contracts/module_options.py`, `quickscale_cli/src/quickscale_cli/commands/module_config.py`, `quickscale_core/src/quickscale_core/contracts/imperative_inventory.py` (`LISTINGS_MANIFEST → []`).
  *Acceptance:* `quickscale plan --add listings` + `quickscale apply` behavior unchanged; `imperative_inventory.py` shows listings fully migrated (matching analytics' `ANALYTICS_MANIFEST = []` precedent).

- [ ] **SA6.3 — Update the imperative-wiring freeze guardrail.** `Tier 1 · Track 3 · deps: SA6.2`
  Extend `test_imperative_inventory.py` so it also asserts listings stays migrated (mirroring the existing analytics assertion), preventing regression back to imperative wiring.
  *Files:* `quickscale_core/tests/test_imperative_inventory.py`.
  *Acceptance:* re-introducing an imperative listings builder fails this test.

---

#### Finding — Repo Finding 2: orgs composition god module (`why →` [Finding 2](../../findings.md#finding-2-orgs-is-becoming-the-composition-god-module--inter-module-integration-is-hand-wired-pairwise-with-no-contract-and-the-central-tenant-registry-couples-all-module-versions-in-lockstep))

- [ ] **SA7.1 — `organization_created` signal replaces CRM bootstrap reverse-import.** `Tier 1 · Track 3 · deps: none`
  Add an `organization_created` Django signal fired by orgs on org creation; convert `crm_bootstrap.maybe_seed_crm_default_stages` into a CRM-side receiver of that signal instead of orgs importing CRM via `apps.is_installed(...)` + `import_module(...)`.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/{models.py or signals.py}` (signal definition + dispatch), `quickscale_modules/orgs/src/quickscale_modules_orgs/crm_bootstrap.py` (delete), `quickscale_modules/crm/src/quickscale_modules_crm/{signals.py new, apps.py}` (receiver + connection).
  *Acceptance:* creating an organization still seeds CRM default stages when CRM is installed, with orgs containing zero CRM-specific code; establishes the composition seam pattern for future cross-module behavior.

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
