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

> **Track status (2026-07-04):** All three tracks are clear to continue in parallel — no cross-track dependencies and no unresolved blockers. Track 1: SA13.1 (dead context API deletion) landed already, so SA13.2 and SA13.3 are unblocked and ready to start now. Track 2: SA15 (entire finding), SA17.1, and SA17.2 are complete; SA17.3–SA17.6 and SA17.8 are ready now, SA17.7 waits on SA17.5 within the track. Track 3: SA18.1–SA18.5 are complete; SA18.6–SA18.9 and SA18.11 are ready now, SA18.10 waits on SA18.6/SA18.9 within the track.

### Structural Autopsy Remediation III (opened 2026-07-03)

Fix plan derived from the [2026-07-03 fresh-pass autopsy](../../arch-audit.md#autopsy--2026-07-03-fresh-full-pass) (4 structural findings, 2 now closed) and [tech-audit.md](../../tech-audit.md) (fail-hard findings). Each task below is sized Adaptive **Tier 1 or Tier 2**; every task touching `orgs`/tenancy/RLS or billing floors at Tier 2 per the sensitive-domain rule.

**Naming:** continues the `SAn.m` sequence from `SA12` (last used). `SA13`–`SA16` close the 2026-07-03 structural findings (`SA15` and `SA16` fully closed — see above); `SA17`–`SA18` close the tech-audit fail-hard findings (`SA17` = module-side settings, `SA18` = core/CLI plumbing).

#### Dependency & parallelization overview (2026-07-04)

Per arch-audit's "Fix order and interactions": Finding 3 (`org-context-api-accretion`) must land before Finding 1 (`operator-read-path-undefined`), since the admin/operator contract should be built on the *consolidated* `org_scope` seam — so SA13 → SA14 remains one intra-track dependency chain. `registry-universe-mismatch` (SA15) and `per-module-knowledge-fanout` (SA16) are now closed — see the closed-batches note above. The fail-hard tasks (SA17, SA18) are file-scoped and independent of the structural work and of each other, aside from two noted internal orderings.

```
Track 1 (tenant-context surface)     Track 2 (module contracts & settings)      Track 3 (core/CLI plumbing)
───────────────────────────────      ───────────────────────────────────       ───────────────────────────
SA13.2 (no deps — ready)             SA17.3 (no deps — ready)                  SA18.6 (no deps — ready)
SA13.3 (no deps — ready)             SA17.4 (no deps — ready)                  SA18.7 (no deps — ready)
SA13.4 (deps: SA13.2, SA13.3)        SA17.5 (no deps — ready)                  SA18.8 (no deps — ready)
SA14.1 (no deps — ready)             SA17.6 (no deps — ready)                  SA18.9 (no deps — ready)
SA14.2 (deps: SA14.1)                SA17.7 (deps: SA17.5)                     SA18.10 (deps: SA18.6, SA18.9)
SA14.3 (deps: SA14.1)                SA17.8 (no deps — ready)                  SA18.11 (no deps — ready)
SA14.4 (deps: SA14.2, SA14.3)
SA14.5 (no deps — ready)
SA14.6 (no deps — ready)
```

No cross-track dependencies — all three tracks can run fully in parallel.

#### Track summary

| Track | Tasks (in order) | Theme |
|-------|------------------|-------|
| **1** | {SA13.2, SA13.3} ready → SA13.4, then SA14.1 (ready) → {SA14.2, SA14.3} → SA14.4, plus SA14.5 (ready), SA14.6 (ready) | Tenant-context request/admin boundary (Finding 3, Finding 1) |
| **2** | SA17.3–SA17.6, SA17.8 (ready) → SA17.7 (deps: SA17.5) | Module-side fail-hard settings (Finding 2 fully closed — see CHANGELOG.md) |
| **3** | SA18.6–SA18.9, SA18.11 (ready) → SA18.10 (deps: SA18.6, SA18.9) | Core/CLI fail-hard plumbing (Finding 4 fully closed — see CHANGELOG.md) |

---

#### Finding — `org-context-api-accretion` (`why →` [Finding 3](../../arch-audit.md#finding-3-org-context-entry-is-a-five-api-accretion-every-non-request-path-hand-picks-its-idiom))

- [ ] **SA13.2 — Migrate view/service callsites to `org_scope`.** `Tier 2 · Track 1 · deps: none (SA13.1 complete) · RISK LEVEL: medium`
  Migrate the `tenant_context`/`org_scope`-eligible callsites in module views and services (the majority of the 26 `tenant_context` + 13 `org_scope` callsites) to the blessed `org_scope`/`PublicSystemOrgReadMixin` API.
  *Files:* views/services across `crm`, `billing`, `blog`, `listings`, `notifications` (per arch-audit's caller census).
  *Acceptance:* no view/service module imports the underscored primitives directly; module test suites stay green.

- [ ] **SA13.3 — Migrate serializer/admin/feed/management-command callsites.** `Tier 2 · Track 1 · deps: none (SA13.1 complete) · RISK LEVEL: medium`
  Same migration as SA13.2, scoped to the remaining callsite classes: `crm/serializers.py`, feeds, admin modules, notifications helpers, management commands (the audit's "13 files across 7 modules" spanning non-view surfaces). Runs in parallel with SA13.2 — disjoint file sets.
  *Files:* `crm/serializers.py`, module admin.py files, feed classes, management commands.
  *Acceptance:* same as SA13.2 for this file set; the SA13.1 lint gate flips from warn to **fail** once both SA13.2 and SA13.3 land (tracked as part of SA13.4).

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

- [ ] **SA17.4 — Fail-hard forms module settings.** `Tier 1 · Track 2 · deps: none · (why → TA2)`
  Require explicit settings for the submissions API toggle, rate limit, and spam-protection flag instead of defaulting them.
  *Files:* `forms/views.py:134,146`, `forms/throttles.py:16`, `forms/models.py:32`.
  *Acceptance:* omitting any of the three settings raises at startup instead of silently applying the current defaults.

- [ ] **SA17.5 — Fail-hard blog module settings.** `Tier 2 · Track 2 · deps: none · (why → TA2)`
  Require explicit RSS-enable and media-URL settings; make malformed `BLOG_API_TOKENS` entries raise at startup instead of being silently `continue`-skipped.
  *Files:* `blog/urls.py:18`, `blog/views.py:175,181-190,280`, `blog/models.py:46-48`.
  *Acceptance:* a malformed `BLOG_API_TOKENS` entry raises at startup naming the bad entry; RSS-enable and media-URL settings are required, not defaulted.

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

- [ ] **SA18.6 — Stop swallowing validation errors in project-metadata resolution.** `Tier 2 · Track 3 · deps: none · (why → TA8)`
  Let `validate_config` errors propagate in `resolve_authoritative_project_metadata`'s `quickscale.yml` branch instead of `except Exception: return None` (which makes "broken config" indistinguishable from "no project here"). Separately, scope the F12.2 documented exception properly to cover (or explicitly exclude) `_load_managed_file_records_for_drift`'s legacy `file_hashes.yml` read.
  *Files:* `quickscale_core/src/quickscale_core/project_state.py:~640-679,~600`.
  *Acceptance:* a malformed `quickscale.yml` raises a validation error instead of being treated as "no project"; the F12.2 exception table entry explicitly lists (or explicitly excludes) the drift-read path.

- [ ] **SA18.7 — Narrow `railway_utils.py`'s broad exception swallowing.** `Tier 1 · Track 3 · deps: none · (why → TA10)`
  Narrow the `except Exception: return None` clauses around URL extraction, variable parsing, and status queries to the specific expected failure modes; keep the narrower `subprocess`-error "is the CLI installed" probes as-is.
  *Files:* `quickscale_cli/src/quickscale_cli/utils/railway_utils.py:469,534,774` (and `:52,236` for comparison).
  *Acceptance:* a Railway CLI crash or output-format change surfaces as an error in `quickscale` status output, distinguishable from "not deployed yet".

- [ ] **SA18.8 — Fail-hard invalid `PORT` values.** `Tier 1 · Track 3 · deps: none · (why → TA11)`
  A non-numeric `PORT` env value should raise a descriptive error instead of silently coercing to `8000`; the default-when-unset behavior (`8000`) is fine and stays.
  *Files:* `quickscale_cli/src/quickscale_cli/utils/docker_utils.py:164-173`.
  *Acceptance:* `PORT=notanumber` raises a descriptive error; `PORT` unset still defaults to `8000`.

- [ ] **SA18.9 — Decide and implement the hash-capture step's failure behavior.** `Tier 1 · Track 3 · deps: none · (why → TA13)`
  Decide: either fail `step_capture_hashes` on `OSError` (hash capture over files the apply itself just wrote should never fail) or register the current best-effort behavior as a documented `# F-EXCEPTION:` entry. Implement whichever is chosen.
  *Files:* `quickscale_core/src/quickscale_core/apply/steps/wiring.py:71-120`.
  *Acceptance:* either the step now fails on `OSError` (and `quickscale apply` reports failure, not silent success), or the step carries a `# F-EXCEPTION:` tag and a decisions.md entry justifying it.

- [ ] **SA18.10 — Add mandated `# F-EXCEPTION:` tags to documented exceptions.** `Tier 1 · Track 3 · deps: SA18.6, SA18.9 · (why → TA14)`
  Add the `# F-EXCEPTION: <tag>` comment format decisions.md §fail-hard-principle mandates to every code location it documents as an exception (starting with `_read_through_import_legacy`'s F12.2 reference, corrected to the mandated tag format), and add the currently-undocumented legacy paths in `remove_command.py` (`_load_legacy_tracking`, legacy `config.yml` snapshot/update) to the decisions.md exception table. Depends on SA18.6 and SA18.9 since both may add or reshape exception entries this task must tag.
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
