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

> **Closed batches (fully resolved, dropped per template rule — detail lives in [CHANGELOG.md](../../CHANGELOG.md)):** Structural Autopsy Remediation I (SA1–SA5, closed 2026-07-02) and II (SA6–SA12, closed 2026-07-03) — repo Findings 2–5 and Module Finding 1 are fully resolved with no open tasks. Within Remediation III, Finding `registry-universe-mismatch` (SA15.1–SA15.3, entire finding, closed 2026-07-04) and Finding `per-module-knowledge-fanout` (SA16.1/SA16.2, entire finding, closed 2026-07-03) are also fully resolved and dropped from both this file and arch-audit.md — see CHANGELOG.md.

> **Track status (2026-07-04):** All three tracks are clear to continue in parallel — no cross-track dependencies and no unresolved blockers. Track 1: SA13.1–SA13.3 are complete; SA13.4 is unblocked. Track 2: SA15 (entire finding) and SA17.1–SA17.5 are complete; SA17.6 and SA17.8 are ready now; SA17.7 is unblocked (SA17.5 complete). Track 3: SA18.1–SA18.6 are complete; SA18.7 has substantial implementation landed but remains open on one deploy `DATABASE_URL`-link follow-up; SA18.8, SA18.9 and SA18.11 are ready now (SA18.9 decision made — fail hard on OSError); SA18.10 is unblocked (no longer depends on SA18.9).

### Structural Autopsy Remediation III (opened 2026-07-03)

Fix plan derived from the [2026-07-03 fresh-pass autopsy](../../arch-audit.md#autopsy--2026-07-03-fresh-full-pass) (4 structural findings, 2 now closed) and [tech-audit.md](../../tech-audit.md) (fail-hard findings). Each task below is sized Adaptive **Tier 1 or Tier 2**; every task touching `orgs`/tenancy/RLS or billing floors at Tier 2 per the sensitive-domain rule.

**Naming:** continues the `SAn.m` sequence from `SA12` (last used). `SA13`–`SA16` close the 2026-07-03 structural findings (`SA15` and `SA16` fully closed — see above); `SA17`–`SA18` close the tech-audit fail-hard findings (`SA17` = module-side settings, `SA18` = core/CLI plumbing).

#### Dependency & parallelization overview (2026-07-04)

Per arch-audit's "Fix order and interactions": Finding 3 (`org-context-api-accretion`) must land before Finding 1 (`operator-read-path-undefined`), since the admin/operator contract should be built on the *consolidated* `org_scope` seam — so SA13 → SA14 remains one intra-track dependency chain. `registry-universe-mismatch` (SA15) and `per-module-knowledge-fanout` (SA16) are now closed — see the closed-batches note above. The fail-hard tasks (SA17, SA18) are file-scoped and independent of the structural work and of each other, aside from two noted internal orderings.

```
Track 1 (tenant-context surface)     Track 2 (module contracts & settings)      Track 3 (core/CLI plumbing)
───────────────────────────────      ───────────────────────────────────       ───────────────────────────
SA13.2 (no deps — complete)           SA17.3 (no deps — complete)               SA18.6 (no deps — complete)
SA13.3 (no deps — complete)           SA17.4 (no deps — complete)                  SA18.7 (partial — 1 deploy follow-up still open)
SA13.4 (deps: SA13.2, SA13.3)        SA17.5 (no deps — complete)                  SA18.8 (no deps — ready)
SA14.1 (no deps — ready)             SA17.6 (no deps — ready)                  SA18.9 (no deps — ready)
SA14.2 (deps: SA14.1)                SA17.7 (deps: SA17.5 — ready)            SA18.10 (no deps — ready)
SA14.3 (deps: SA14.1)                SA17.8 (no deps — ready)                  SA18.11 (no deps — ready)
SA14.4 (deps: SA14.2, SA14.3)
SA14.5 (no deps — ready)
SA14.6 (no deps — ready)
```

No cross-track dependencies — all three tracks can run fully in parallel.

#### Track summary

| Track | Tasks (in order) | Theme |
|-------|------------------|-------|
| **1** | SA13.2, SA13.3 (complete) → SA13.4 (deps met), then SA14.1 (ready) → {SA14.2, SA14.3} → SA14.4, plus SA14.5 (ready), SA14.6 (ready) | Tenant-context request/admin boundary (Finding 3, Finding 1) |
| **2** | SA17.3–SA17.5 (complete), SA17.6, SA17.8 (ready) → SA17.7 (ready, deps met) | Module-side fail-hard settings (Finding 2/TA2 not fully closed until SA17.6 lands) |
| **3** | SA18.6 (complete), SA18.7 (partial — deploy follow-up still open), SA18.8–SA18.11 (ready, no deps) | Core/CLI fail-hard plumbing (Finding 4 not fully closed until SA18.7 follow-up lands) |

---

#### Finding — `org-context-api-accretion` (`why →` [Finding 3](../../arch-audit.md#finding-3-org-context-entry-is-a-five-api-accretion-every-non-request-path-hand-picks-its-idiom))

- [x] **SA13.1 — Delete the dead context API and gate the rest.** `Tier 2 · Track 1 · deps: none · RISK LEVEL: medium`
  Delete `resolve_public_org_context` (0 module+core src callers per the Finding 3 census; internal/test references remain). Underscore-privatize `set_db_current_org_id`, `set_current_org_for_context`, and `tenant_context` as internal helpers behind the public `org_scope`/`PublicSystemOrgReadMixin` surface, kept importable for the callsite migrations in SA13.2/13.3. Add an AST/import-lint gate (reuse the SA9.6 `check_module_core_imports.py` pattern) that *warns* (not yet fails) on direct external use of the three privatized primitives only.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/current_org.py`, new `scripts/check_org_context_primitives.py`.
  *Acceptance:* `resolve_public_org_context` is gone; the three primitives are renamed with a leading underscore but remain importable; the new lint script runs in warn-only mode and flags direct use of `_tenant_context` / `_set_current_org_for_context` / `_set_db_current_org_id` only — 31 pre-migration callsites (`tenant_context` 26 + `set_current_org_for_context` 5) — without failing CI; `org_scope` usage is never flagged, since it is the permanent public API, not a migration source.

  > **Scope decision (2026-07-04):** Resolved the discovery-note ambiguity between the task text (gate the 3 privatized primitives only) and the acceptance text's broader "44-count" (which wrongly folded in `org_scope`'s 13 callers). **Decision: gate the 3 privatized primitives only.** `org_scope` stays public and exempt — it's the permanent target API under arch-audit Finding 3's locked-in "Consolidate + gate" option, so flagging it would contradict the chosen design and would immediately self-conflict with SA13.2/13.3 (which migrate callers *to* `org_scope`). Also decided: keep the **warn-now / fail-later staging** (SA13.1 warns, SA13.4 flips to hard-fail once SA13.2/13.3 finish migrating callsites) rather than failing immediately — an immediate hard-fail would break CI on the ~31 not-yet-migrated callsites before the migration work has even started, which is a sequencing self-inflicted break, not a real misconfiguration. This staging does not conflict with the fail-hard principle: that principle governs runtime/production misconfiguration behavior, not an in-flight internal lint-gate rollout, and this project has staged an equivalent guardrail before (SA6.3's imperative-freeze test). **Implementation is unblocked.**
  >
  > **Review-driven follow-up (2026-07-04 — CR-SA13.1-001, CR-SA13.1-002, CR-SA13.1-003):**
  > - **CR-SA13.1-001 resolved:** The social managed-view generator (`social_manifest.py:render_social_managed_views_module`) now emits `org_scope()` instead of `tenant_context()` — eliminating the generated code's use of a privatized primitive. The lint gate scope is extended to also scan `quickscale_core/src/` for direct Python-level imports of the privatized primitives. Template-string usages are not AST-detectable; those are resolved by migrating the generator to emit the public API.
  > - **CR-SA13.1-002 resolved:** `get_public_org_context()` now wraps `_tenant_context()` and yields the resolved org UUID instead of delegating directly (which yielded `None`). The documented `Iterator[uuid.UUID | None]` contract is now fulfilled. Regression tests added proving the yield value matches the expected org UUID, and fail-closed behavior yields `None`.
  > - **CR-SA13.1-003 resolved:** Added regeneration evidence to `test_social_module_produces_managed_files` in `test_module_wiring_manager_manifest.py`. The test now reads the regenerated `social_views.py` file produced by `regenerate_managed_wiring` and asserts the SA13.1 contract: `org_scope(resolved_org)` is present; `tenant_context`, `organization_id`, `set_current_org_id`, `set_db_current_org_id`, and `from django.db import transaction` are all absent — confirming the template change propagates through the full regeneration pipeline to the on-disk managed file.

- [x] **SA13.2 — Migrate view/service callsites to `org_scope`.** `Tier 2 · Track 1 · deps: none (SA13.1 complete) · RISK LEVEL: medium`
  Migrate the `tenant_context`/`org_scope`-eligible callsites in module views and services (the majority of the 26 `tenant_context` + 13 `org_scope` callsites) to the blessed `org_scope`/`PublicSystemOrgReadMixin` API.
  *Files:* views/services across `crm`, `billing`, `blog`, `listings`, `notifications` (per arch-audit's caller census).
  *Acceptance:* no view/service module imports the underscored primitives directly; module test suites stay green.

- [x] **SA13.3 — Migrate serializer/admin/feed/management-command callsites.** `Tier 2 · Track 1 · deps: none (SA13.1 complete) · RISK LEVEL: medium`
  Same migration as SA13.2, scoped to the remaining callsite classes: `crm/serializers.py`, feeds, admin modules, notifications helpers, management commands (the audit's "13 files across 7 modules" spanning non-view surfaces). Runs in parallel with SA13.2 — disjoint file sets.
  *Files:* `crm/serializers.py`, module admin.py files, feed classes, management commands.
  *Acceptance:* same as SA13.2 for this file set; the SA13.1 lint gate flips from warn to **fail** once both SA13.2 and SA13.3 land (tracked as part of SA13.4).

  > **Collapse finding (2026-07-04):** Fresh discovery found only one remaining non-exempt production callsite — `social/admin.py`'s `_org_db_context` using the `tenant_context` compatibility alias. All other SA13.3 target surfaces (serializers, feeds, management commands, other admin modules) were either already migrated by SA13.2, belong to orgs-internal exempt paths, or had no direct import of the privatized primitives. The migration:
  > - Replaced the `tenant_context` import with `org_scope` (the blessed public API).
  > - Rewrote `_org_db_context` to fetch the `Organization` instance from the resolved UUID and delegate to `org_scope(instance)`; the fail-closed path (`None` or org-not-found) uses `org_scope(None)`.
  > - Removed the outer `transaction.atomic()` wrapper (now internal to `org_scope`).
  > - Removed the unused `from django.db import transaction` import.
  > - Updated the test that exercised `_org_db_context` with a random UUID to use the `org` fixture (the Organization lookup requires a real DB record).
  > - Updated module and function docstrings to reference `org_scope` instead of `tenant_context`.
  > SA13.3 acceptance: the social module test suite stays green; the lint gate (`make check-org-context-primitives`) reports zero remaining external uses of `tenant_context` or the other privatized primitives (warn-only during SA13.1–SA13.3).

- [ ] **SA13.4 — Flip the lint gate to hard-fail; harden the AF9 `None`-path.** `Tier 2 · Track 1 · deps: SA13.2, SA13.3 · RISK LEVEL: medium`
  Flip `check_org_context_primitives.py` from warn to fail (closing the migration). Separately evaluate and, if safe, implement AF9's `None`-path hardening (option 3 in Finding 3: prime-to-empty instead of pass-through when the ContextVar is `None`) to close the last ContextVar/GUC desync window — needs careful autocommit-path review since it changes wrapper semantics on hot paths.
  *Files:* `scripts/check_org_context_primitives.py`, `quickscale_modules/orgs/src/quickscale_modules_orgs/current_org.py`.
  *Acceptance:* lint gate fails CI on any new direct use of the privatized primitives; AF9 wrapper behavior on `None` context is either hardened (with regression tests for autocommit/atomic paths) or explicitly deferred with a written reason if the risk outweighs the benefit.

---

#### Finding — `operator-read-path-undefined` (`why →` [Finding 1](../../arch-audit.md#finding-1-elevatedoperator-reads-are-structurally-undefined--the-python-bypass-and-the-db-backstop-disagree))

- [ ] **SA14.1 — Build the orgs-owned `TenantModelAdmin` base.** `Tier 2 · Track 1 · deps: none (SA13.1 complete) · RISK LEVEL: medium`
  Add an org-resolving, `org_scope`-wrapping `TenantModelAdmin` (or `AdminSite`) to `orgs` that resolves the VIEW-AS/session org and wraps changelist/change views accordingly — generalizing the pattern social's admin already proves works under RLS.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/admin.py` (new base class).
  *Acceptance:* a model admin subclassing `TenantModelAdmin` shows the VIEW-AS-resolved org's rows under the restricted `NOBYPASSRLS` role and denies cross-tenant rows without an explicit operator grant.

- [ ] **SA14.2 — Port CRM's 8 admins to `TenantModelAdmin`.** `Tier 2 · Track 1 · deps: SA14.1 · RISK LEVEL: medium`
  Replace `all_objects.all()` "cross-tenant visibility" idiom in CRM's `ModelAdmin`s with the new base; delete the now-inaccurate comments.
  *Files:* `quickscale_modules/crm/src/quickscale_modules_crm/admin.py`.
  *Acceptance:* CRM admin changelists render correctly under the restricted role in a manual/E2E check; no `all_objects` reference remains in `crm/admin.py`.

- [ ] **SA14.3 — Port blog/forms/listings/billing admins to `TenantModelAdmin`.** `Tier 2 · Track 1 · deps: SA14.1 · RISK LEVEL: medium`
  Same port as SA14.2 for the remaining modules' admin classes. Runs in parallel with SA14.2 — disjoint files.
  *Files:* `blog/admin.py`, `forms/admin.py`, `listings/admin.py`, `billing/admin.py`.
  *Acceptance:* same as SA14.2 for these modules.

- [ ] **SA14.4 — Flip module test suites' default DB role to `NOBYPASSRLS`.** `Tier 2 · Track 1 · deps: SA14.2, SA14.3 · RISK LEVEL: medium`
  Change the module test settings default from superuser (`QUICKSCALE_ALLOW_BYPASSRLS=1`) to the restricted runtime role, with superuser opt-in only for tests that explicitly need it (e.g. migration tests). This is the posture change that makes the operator-read bug class visible to CI going forward, so it must land *after* the admin ports (SA14.2/14.3) to avoid breaking the suites it's meant to protect.
  *Files:* `*/tests/settings.py` across modules.
  *Acceptance:* module test suites pass by default under the restricted role; only explicitly-marked tests opt into superuser/BYPASSRLS.

- [ ] **SA14.5 — Implement `operator_access(reason=...)` as a real, audited RLS predicate.** `Tier 2 · Track 1 · deps: none (SA13.1 complete) · RISK LEVEL: medium`
  Add `OR NULLIF(current_setting('app.operator_access', true), '') = 'on'` to the FORCE RLS policy template and implement `operator_access(reason=...)` (superuser-gated, audit-logged context manager) as the only setter — finally implementing the contract `decisions.md` already documents as a "permanent rule" but which exists in no code today.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py` (policy template), `current_org.py` (new context manager).
  *Acceptance:* `operator_access(reason=...)` grants true cross-tenant reads for its duration only, is audit-logged, and requires superuser; without it, no code path bypasses RLS.

- [ ] **SA14.6 — Fail-hard `QUICKSCALE_MODE` when orgs is installed.** `Tier 1 · Track 1 · deps: none`
  Replace `getattr(settings, "QUICKSCALE_MODE", "solo")` with a required-setting read that raises `ImproperlyConfigured` when `orgs` is installed and `QUICKSCALE_MODE` is unset, so a saas deployment can't silently flip to solo-mode tenancy.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/middleware.py:268`.
  *Acceptance:* omitting `QUICKSCALE_MODE` in a saas-mode generated project raises at startup instead of defaulting to `"solo"`.

---

### Fail-Hard Remediation (opened 2026-07-03)

Fix plan derived from [tech-audit.md](../../tech-audit.md). `SA17` covers module-side settings defaults (Track 2); `SA18` covers core/CLI/generator plumbing (Track 3). Both continue the `SAn.m` sequence.

#### `SA17` — Module-side settings and config fail-hard fixes (Track 2)

- [x] **SA17.1 — Reject legacy config keys instead of silently translating/dropping them (complete).** `Tier 2 · Track 2 · deps: none · (why → TA1, closed)`
  `normalize_auth_module_options`/`normalize_crm_module_options`/`normalize_notifications_module_options` now raise `ConfigValidationError` naming the legacy key and its replacement instead of silently mapping or dropping it. Closes tech-audit TA1. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA17.2 — Fail-hard analytics/billing enabled-flag settings (complete).** `Tier 2 · Track 2 · deps: none · RISK LEVEL: medium (billing) · (why → TA2)`
  Added AppConfig.ready() startup guards to `analytics/apps.py` and `billing/apps.py` that raise `ImproperlyConfigured` at startup when `QUICKSCALE_ANALYTICS_ENABLED` / `QUICKSCALE_BILLING_ENABLED` are missing. Removed default-`True` fallbacks in `analytics/services.py`, `billing/services.py`, and `billing/adapter.py`. Updated test settings (`billing/tests/settings.py`) with the required enabled-flag. Rewrote the analytics `test_configure_analytics_client_defaults_missing_enabled_setting_to_enabled` test as `test_configure_analytics_client_missing_enabled_setting_raises_attribute_error`. Added ready()-method tests to both modules' `test_apps.py` (analytics: `test_ready_raises_improperly_configured_when_enabled_setting_missing`, billing: `test_app_config_ready_raises_improperly_configured_when_enabled_setting_missing`). Added `test_billing_settings_snapshot_missing_enabled_setting_raises_attribute_error` to billing `test_services.py`. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.
  *Files:* `analytics/apps.py`, `analytics/services.py`, `analytics/tests/test_apps.py`, `analytics/tests/test_services.py`, `billing/apps.py`, `billing/services.py`, `billing/adapter.py`, `billing/tests/settings.py`, `billing/tests/test_apps.py`, `billing/tests/test_services.py`.
  *Acceptance:* omitting either setting from a generated project raises at startup instead of silently enabling the feature.

- [x] **SA17.3 — Fail-hard CRM's API-enable flag and page-size settings (complete).** `Tier 1 · Track 2 · deps: none · (why → TA2)`
  `CRM_ENABLE_API` required (no `True` default); replaced `int(getattr(...) or 50)` page-size reads with explicit validation that rejects non-numeric values instead of silently swallowing them to `50`. Added `AppConfig.ready()` startup guard to `crm/apps.py` that raises `ImproperlyConfigured` when `CRM_ENABLE_API` is missing. Removed default-`True` fallback in `CRMApiEnabledMixin.initial()` and default-`25`/`50` fallbacks in `ContactPagination.get_page_size()` / `DealPagination.get_page_size()`. Removed fallback defaults in `adapter.py` `_crm_post_hook` — all three settings now use direct key access (must be present from `module.yml` derivation). Updated test settings with the required settings. Added `ready()`-method guard test to `crm/tests/test_apps.py`. Added four page-size fail-hard tests to `crm/tests/test_views.py`. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.
  *Files:* `crm/apps.py`, `crm/adapter.py`, `crm/views.py`, `crm/tests/settings.py`, `crm/tests/test_apps.py` (new), `crm/tests/test_views.py`.
  *Acceptance:* missing `CRM_ENABLE_API` or a malformed page-size setting raises at startup/request time with a descriptive error.

- [x] **SA17.4 — Fail-hard forms module settings (complete).** `Tier 1 · Track 2 · deps: none · (why → TA2)`
  Added AppConfig.ready() startup guard to `forms/apps.py` that raises `ImproperlyConfigured` at startup when any of `FORMS_SUBMISSIONS_API`, `FORMS_RATE_LIMIT`, or `FORMS_SPAM_PROTECTION` is missing. Removed default-`True` fallbacks in `views.py` (`FormsAdminApiMixin.initial()`), `throttles.py` (`FormSubmitThrottle.get_rate()`), and `models.py` (`is_form_spam_protection_enabled()`). Updated test settings with the required settings. Replaced the `test_form_submit_throttle_falls_back_to_parent_rate` fallback test with `test_form_submit_throttle_missing_rate_raises_improperly_configured`. Added five ready()-method tests to `forms/tests/test_apps.py` (new). See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.
  *Files:* `forms/apps.py`, `forms/views.py`, `forms/throttles.py`, `forms/models.py`, `forms/tests/settings.py`, `forms/tests/test_apps.py` (new), `forms/tests/test_throttles.py`.
  *Acceptance:* omitting any of the three settings raises at startup instead of silently applying the current defaults.

- [x] **SA17.5 — Fail-hard blog module settings (complete).** `Tier 2 · Track 2 · deps: none · (why → TA2)`
  Added `AppConfig.ready()` startup guard to `blog/apps.py` that raises `ImproperlyConfigured` at startup when `BLOG_ENABLE_RSS` is missing, `MEDIA_URL` is empty/unset, or any `BLOG_API_TOKENS` entry is malformed (naming the bad entry). Removed the default-`True` fallback in `urls.py:_blog_enable_rss()` and the `getattr(settings, "MEDIA_URL", "/media/")` fallbacks in `views.py:_build_media_response_url()` and `models.py:_build_public_media_url()`. Updated test settings with the required `BLOG_ENABLE_RSS = True`. Updated `test_urls.py` to remove the `None`-unset parametrize case. Added `blog/tests/test_apps.py` with 9 ready()-method guard tests (3 general + 6 malformed-token variations). Acceptance: a malformed `BLOG_API_TOKENS` entry raises at startup naming the bad entry; RSS-enable and media-URL settings are required, not defaulted. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [ ] **SA17.6 — Fail-hard notifications module settings.** `Tier 1 · Track 2 · deps: none · (why → TA2)`
  Require explicit enabled-flag and provider settings instead of defaulting to `True`/`"resend"`.
  *Files:* `notifications/services.py:155-157`.
  *Acceptance:* omitting either setting raises at startup instead of silently enabling the "resend" provider.

- [ ] **SA17.7 — Replace optional-dependency soft degradation with generation-time wiring.** `Tier 2 · Track 2 · deps: SA17.5 (SA17.2 complete) · (why → TA9)`
  Analytics' PostHog SDK import failure currently logs a warning and disables capture; forms' analytics integration currently probes for the sibling module via a soft `ImportError`/`getattr(None)` chain. Since module assembly happens at generation time, wire the analytics↔forms integration (and the PostHog SDK requirement) as a hard dependency the generator resolves, not a runtime probe. Depends on SA17.5 landing the surrounding settings checks first so the two changes don't fight over the same code paths (SA17.2's half of this ordering is already satisfied — it's complete).
  *Files:* `analytics/services.py:218-223`, `forms/views.py:92-97`.
  *Acceptance:* if analytics is assembled into a project, a missing PostHog SDK raises at startup (not a warning); forms' analytics integration is generation-time wired, not runtime-probed.

- [ ] **SA17.8 — Remove or gate deprecated `module_catalog` compat delegates; fix fail-open readiness.** `Tier 1 · Track 2 · deps: none · (why → TA12)`
  Remove `get_module_names()`/`get_module_entries()` from the public `contracts/__init__.py` API (or add the mandated `# F-EXCEPTION:` tag if a caller genuinely still needs them), and make `get_module_readiness_reason()` raise or return an explicit "unknown module" sentinel for unrecognized names instead of `None` (indistinguishable from "ready").
  *Files:* `quickscale_core/src/quickscale_core/contracts/module_catalog.py:128-175,270-289`.
  *Acceptance:* the deprecated delegates are either removed from the public API or carry an `# F-EXCEPTION:` tag; readiness checks on an unknown module name raise/return a distinguishable value from "ready".

#### `SA18` — Core/CLI/generator plumbing fail-hard fixes (Track 3)

- [x] **SA18.1 — Narrow the import-time `except Exception: pass` in manifest adapter init (complete — 2026-07-03).** `Tier 1 · Track 3 · deps: none`
  Closed the fail-hard violation formerly tracked as tech-audit TA3 (now dropped from tech-audit.md). See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA18.2 — Raise instead of silently defaulting empty analytics manifest settings (complete — 2026-07-03).** `Tier 1 · Track 3 · deps: none · (why → TA4)`
  Replaced the silent PostHog fallback defaults in `_analytics_post_hook` with a `ManifestError` that raises when resolved settings are empty, naming the empty keys. The PR-4 disabled short-circuit (`enabled=False` → empty spec) is unaffected and remains before the validation check. Five unit tests added to `TestAnalyticsPostHookFailHard` covering empty provider, empty host, multiple empty keys, non-empty happy path, and disabled short-circuit.
  **Follow-up (CR-SA18.2-001):** Fixed `regenerate_managed_wiring` in `module_wiring_manager.py` which was silently swallowing `ManifestError` from `build_manifest_wiring_spec`, masking the analytics fail-hard validation. The `except ManifestError: continue` handler now only skips "Manifest file not found" errors for modules absent from the embedded directory; all other `ManifestError` instances (including invalid analytics configuration) propagate as real failures. Two regression tests added proving invalid analytics options fail through the regenerate/apply seam. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.
  *Files:* `quickscale_core/src/quickscale_core/manifest/entry_point.py`, `quickscale_core/tests/test_manifest_entry_point.py`, `quickscale_cli/src/quickscale_cli/utils/module_wiring_manager.py`, `quickscale_cli/tests/test_module_wiring_manager_manifest.py`.
  *Acceptance:* an empty-after-resolution analytics config raises a descriptive error through `build_manifest_wiring_spec` *and* through the `regenerate_managed_wiring`/apply seam; the disabled short-circuit behaviour is unaffected.

- [x] **SA18.3 — Delete the `quickscale_cli.schema` compat shim (complete).** `Tier 2 · Track 3 · deps: none · (why → TA5, closed)`
  Migrated all CLI internal imports and tests from `quickscale_cli.schema.*` to `quickscale_core.schema.*`; deleted the shim package. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA18.4 — Fix generator template-resolution fallback chains (complete).** `Tier 2 · Track 3 · deps: none · (why → TA6)`
  Replaced the template-dir discovery guess chain (dev dir → package dir → cwd-relative guesses) with a single deterministic resolution rule (installed package path, with an explicit override param for dev use). Deleted the "backward compatibility" root-template fallback tier in `_get_theme_template_path` and raises `FileNotFoundError` immediately with the attempted path on a miss instead of deferring to a later Jinja `TemplateNotFound`. Added `common/templates/admin/` directory with copies of the shared Django admin templates so the common fallback resolves them correctly. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA18.5 — Remove the version fallback chain's terminal `"0.0.0"` default (complete).** `Tier 1 · Track 3 · deps: none · (why → TA7)`
  Narrowed `quickscale_core.version` from `except Exception` to `ImportError`, kept the dev-tree `VERSION` fallback, and now raises `FileNotFoundError` instead of silently reporting `"0.0.0"` when both resolution paths fail. Updated targeted version tests to preserve fallback-to-`VERSION` behavior and assert the new fail-hard path.
  *Finding:* the repository currently ships a generated `quickscale_core/_version.py`, so the fail-hard branch is primarily a broken-build/source-tree guard; targeted tests now cover that seam explicitly.
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA18.6 — Stop swallowing validation errors in project-metadata resolution (complete).** `Tier 2 · Track 3 · deps: none · (why → TA8)`
  Removed `except Exception: return None` from `resolve_authoritative_project_metadata`'s `quickscale.yml` branch — `validate_config` errors now propagate as `ConfigValidationError` instead of being indistinguishable from "no project here." `_load_managed_file_records_for_drift` is explicitly documented as outside F12.2 scope (its legacy `file_hashes.yml` fallback is a drift-detection design choice, not an M2 migration compatibility path). The F12.2 exception table entry now carries the SA18.6 annotation. Closes tech-audit TA8. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.
  *Files:* `quickscale_core/src/quickscale_core/project_state.py`, `quickscale_core/tests/test_project_state.py`, `docs/technical/decisions.md`.
  *Acceptance:* a malformed `quickscale.yml` raises `ConfigValidationError`; `_load_managed_file_records_for_drift` is explicitly outside F12.2; targeted tests updated to expect fail-hard behavior.
- [ ] **SA18.7 — Narrow `railway_utils.py`'s broad exception swallowing.** `Tier 1 · Track 3 · deps: none · (why → TA10)`
  Narrow the `except Exception: return None` clauses around URL extraction, variable parsing, and status queries to the specific expected failure modes; keep the narrower `subprocess`-error "is the CLI installed" probes as-is.
  **Progress landed (2026-07-04):** `get_deployment_url()`, `generate_railway_domain()`, `get_railway_variables()`, and `_get_railway_variables_json()` now narrow their broad catches to the expected Railway command failure types (`TimeoutError`, `FileNotFoundError`). Successful-but-unparseable Railway output (returncode 0 but unrecognizable format) now raises `ValueError` instead of collapsing to `None`/`{}` across the URL/domain parsing paths and the DR/runtime-variable path. Focused Railway utility tests plus deploy/DR caller-level regression coverage were added for those seams. The narrower `subprocess`-error probes at lines 52 and 236 remain unchanged.
  **Pending / blocking follow-up (user-directed stop after review cap):** the deploy `DATABASE_URL` link path (`_link_database_step()` → `link_database_to_service()` → `get_railway_variables()`) still needs the same descriptive fail-hard conversion and a caller-level regression test. Today that path can still surface the parse-drift `ValueError` uncaught instead of converting it into the same operator-visible non-zero CLI failure used by the other deploy/DR seams.
  **Decision status:** no product or design decision remains open here — the remaining work is a narrow implementation follow-up only.
  *Files landed so far:* `quickscale_cli/src/quickscale_cli/utils/railway_utils.py`; `quickscale_cli/src/quickscale_cli/commands/deployment_commands.py`; `quickscale_cli/src/quickscale_cli/commands/dr_commands.py`; `quickscale_cli/tests/utils/test_railway_utils.py`; `quickscale_cli/tests/commands/test_deployment_commands.py`; `quickscale_cli/tests/commands/test_deployment_commands_extended.py`; `quickscale_cli/tests/commands/test_dr_commands.py`.
  *Pending file for closeout:* `quickscale_cli/src/quickscale_cli/commands/deployment_commands.py` (deploy `DATABASE_URL`-link seam) plus the direct regression coverage for that path.
  *Acceptance:* every Railway caller seam surfaces CLI crashes or output-format drift as a descriptive error, distinguishable from benign "not deployed yet" / empty-output states; successful-but-unparseable output does not collapse to `None`/`{}` anywhere in the deploy/DR Railway helpers.

- [ ] **SA18.8 — Fail-hard invalid `PORT` values.** `Tier 1 · Track 3 · deps: none · (why → TA11)`
  A non-numeric `PORT` env value should raise a descriptive error instead of silently coercing to `8000`; the default-when-unset behavior (`8000`) is fine and stays.
  *Files:* `quickscale_cli/src/quickscale_cli/utils/docker_utils.py:164-173`.
  *Acceptance:* `PORT=notanumber` raises a descriptive error; `PORT` unset still defaults to `8000`.

- [ ] **SA18.9 — Fail `step_capture_hashes` on `OSError`.** `Tier 1 · Track 3 · deps: none · (why → TA13)`
  Return `StepOutcome(success=False)` on `OSError` with a descriptive error message. Hash capture runs over files the apply pipeline itself just wrote — a read-back failure is a genuine system-level problem (disk full, permissions, filesystem corruption), not a best-effort informational path.
  **Decision (2026-07-04):** Option 1 (fail hard), per user direction. Consistent with all prior SA17/SA18 precedent (SA17.1–SA17.4, SA18.1–SA18.6). No F-EXCEPTION needed.
  *Files:* `quickscale_core/src/quickscale_core/apply/steps/wiring.py:71-120`.
  *Acceptance:* `step_capture_hashes` returns `success=False` on `OSError`; docstring updated (remove "always succeeds" contract); `quickscale apply` reports failure instead of silent degradation.

- [ ] **SA18.10 — Add mandated `# F-EXCEPTION:` tags to documented exceptions.** `Tier 1 · Track 3 · deps: none · (why → TA14)`
  Add the `# F-EXCEPTION: <tag>` comment format decisions.md §fail-hard-principle mandates to every code location it documents as an exception (starting with `_read_through_import_legacy`'s F12.2 reference, corrected to the mandated tag format), and add the currently-undocumented legacy paths in `remove_command.py` (`_load_legacy_tracking`, legacy `config.yml` snapshot/update) to the decisions.md exception table. SA18.6 is already complete (its exception entries are in place); SA18.9 chose the fail-hard path (no new F-EXCEPTION), so no dependency remains.
  *Files:* `quickscale_core/src/quickscale_core/project_state.py:415`, `quickscale_cli/src/quickscale_cli/commands/remove_command.py`, `docs/technical/decisions.md`.
  *Acceptance:* `grep -rn "F-EXCEPTION"` returns a hit for every exception decisions.md documents, and decisions.md's exception table lists every exception the grep finds.

- [ ] **SA18.11 — Fix dev-tooling silent parse failure in the compatibility checker.** `Tier 1 · Track 3 · deps: none · (why → TA15)`
  A malformed module `pyproject.toml` should fail the compatibility check loudly, not be silently skipped.
  *Files:* `scripts/check_module_core_compatibility.py:381-388`.
  *Acceptance:* a malformed `pyproject.toml` in any module causes the checker to fail/report an error for that module instead of silently skipping it.

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../../arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../../tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
