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

> **Scoped 2026-07-03:** The [2026-07-03 fresh-pass autopsy](../../arch-audit.md#autopsy--2026-07-03-fresh-full-pass)'s 4 structural findings and [tech-audit.md](../../tech-audit.md)'s 15 fail-hard findings are now broken into tasks under **Structural Autopsy Remediation III** and **Fail-Hard Remediation** below (`SA13`–`SA18`).

### Structural Autopsy Remediation II (opened 2026-07-02)

Fix plan derived from the [2026-07-02 repo-level autopsy](../../arch-audit.md#autopsy--2026-07-02) and the [2026-07-02 module-by-module autopsy](../../arch-audit.md#module-by-module-autopsy--2026-07-02). Each task below is sized Adaptive **Tier 1 or Tier 2**. Tenant-isolation and money-ledger work is sensitive-domain → `RISK LEVEL: medium` → floors at Tier 2.

**Naming:** `SAn.m` continues the sequence from the closed 2026-06-30 remediation (`SA1`–`SA5`); this batch starts at `SA6` to avoid collision. `SA6`–`SA10` close repo-level findings, `SA11`–`SA12` close module-level findings.

**Priority note:** SA11.1–SA11.5 closed the **live defect** (anonymous public pages render empty under the hardened production RLS posture — Module Finding 1) and its adjacent hardening work; see CHANGELOG.md. SA11.6–SA11.7 continue the Module Finding 1 remediation. SA11.7 is complete; see CHANGELOG.md for closeout details.

#### Dependency & parallelization overview (2026-07-03)

**Completed — closeout in [CHANGELOG.md](../../CHANGELOG.md):** SA6.1–SA6.3, SA7.1–SA7.4, SA9.1–SA9.6, SA10.1–SA10.2, SA11.1–SA11.5, SA12.1. Repo Findings 2, 3, 4, and 5 are fully resolved — see CHANGELOG.md and, for Finding 3, `decisions.md` §D1.

Diagram below shows only remaining open work.

```
Track 1 (tenant-context surface)     Track 2                                   Track 3
───────────────────────────────      ───────────────────────────────────      ───────
No open tasks                       No open tasks                             —
```

All SAII tracks are fully resolved — see CHANGELOG.md for closeout details.

#### Track summary

| Track | Tasks (in order) | Theme |
|-------|------------------|-------|
| **1** | *(complete — see CHANGELOG.md)* | Auth fail-hard default |
| **2** | No open tasks | All SA9.x/SA10.x complete |
| **3** | No open tasks | All SA7.x complete |

---

#### Finding — Module Finding 1: request→tenant-context boundary (`why →` [Module Finding 1](../../arch-audit.md#module-finding-1-the-requesttenant-context-boundary-is-a-per-module-convention-with-divergent-idioms--and-bloglistings-public-pages-read-as-empty-under-the-hardened-production-posture))

- [x] **SA11.1 — Orgs-owned public-read context helper (complete — 2026-07-03).** `Tier 2 · Track 1 · deps: none · RISK LEVEL: medium`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA11.2 — Restricted-role anonymous-read E2E smoke (complete).** `Tier 2 · Track 1 · deps: SA11.1 · RISK LEVEL: medium`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA11.3 — Migrate blog public views to the helper (complete).** `Tier 1 · Track 1 · deps: SA11.1`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA11.4 — Migrate listings public views to the helper (complete).** `Tier 1 · Track 1 · deps: SA11.1`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA11.6 — Clean up CRM's `_resolve_active_org` (complete — 2026-07-03).** `Tier 1 · Track 1 · deps: none`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA11.7 — Fail-hard the auth signup-open default (complete — 2026-07-03).** `Tier 1 · Track 1 · deps: none`
  Replaced the permissive `getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)` fallback with a required-setting read (raises `ImproperlyConfigured` if unset), consistent with the fail-hard principle. Startup check added to `QuickscaleAuthConfig.ready()` so the error surfaces at Django boot time. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.
  *Files:* `quickscale_modules/auth/src/quickscale_modules_auth/adapters.py`, `quickscale_modules/auth/src/quickscale_modules_auth/apps.py`.
  *Acceptance:* omitting `ACCOUNT_ALLOW_REGISTRATION` from settings raises at startup instead of silently defaulting to open registration.

---

> **Closed findings:** Repo Finding 2 (orgs god-module — SA7.2–SA7.4), Repo Finding 3 (dual active-org truth — product decision 2026-07-03), Repo Finding 4 (core-as-runtime-API boundary — SA9.1–SA9.6), and Repo Finding 5 (module↔generated-project contract drift — SA10.1–SA10.2) are fully resolved with no open tasks. Closeout detail is in [CHANGELOG.md](../../CHANGELOG.md); the Finding 3 product decision is recorded in `decisions.md` §D1.

---

### Structural Autopsy Remediation III (opened 2026-07-03)

Fix plan derived from the [2026-07-03 fresh-pass autopsy](../../arch-audit.md#autopsy--2026-07-03-fresh-full-pass) (4 structural findings) and [tech-audit.md](../../tech-audit.md) (15 fail-hard findings). Each task below is sized Adaptive **Tier 1 or Tier 2**; every task touching `orgs`/tenancy/RLS or billing floors at Tier 2 per the sensitive-domain rule.

**Naming:** continues the `SAn.m` sequence from `SA12` (last used). `SA13`–`SA16` close the 2026-07-03 structural findings; `SA17`–`SA18` close the tech-audit fail-hard findings (`SA17` = module-side settings, `SA18` = core/CLI plumbing).

#### Dependency & parallelization overview (2026-07-03)

Per arch-audit's "Fix order and interactions": Finding 3 (`org-context-api-accretion`) must land before Finding 1 (`operator-read-path-undefined`), since the admin/operator contract should be built on the *consolidated* `org_scope` seam. Finding 2 (`registry-universe-mismatch`) uses the marker-based option, which the audit notes is independent of Finding 4's sync gate — so all four structural findings collapse to **one intra-track dependency chain** (SA13 → SA14) plus two fully independent chains (SA15, SA16). The fail-hard tasks (SA17, SA18) are file-scoped and independent of the structural work and of each other, aside from two noted internal orderings.

```
Track 1 (tenant-context surface)     Track 2 (module contracts & settings)      Track 3 (core/CLI plumbing)
───────────────────────────────      ───────────────────────────────────       ───────────────────────────
SA11.7 (no deps)                     SA15.2 → SA15.3                            SA16.1 ✅ (complete)
                                     SA17.1 (no deps)                          SA16.2 ✅ (complete)
SA13.1 (no deps)                     SA17.2 (no deps)                          SA18.2 (no deps)
SA13.2 (deps: SA13.1)                SA17.3 (no deps)                          SA18.3 (no deps)
SA13.3 (deps: SA13.1)                SA17.4 (no deps)                          SA18.4 (no deps)
SA13.4 (deps: SA13.2, SA13.3)        SA17.5 (no deps)                          SA18.5 (no deps)
SA14.1 (deps: SA13.1)                SA17.6 (no deps)                          SA18.6 (no deps)
SA14.2 (deps: SA14.1)                SA17.7 (deps: SA17.2, SA17.5)             SA18.7 (no deps)
SA14.3 (deps: SA14.1)                SA17.8 (no deps)                          SA18.8 (no deps)
SA14.4 (deps: SA14.2, SA14.3)                                                  SA18.9 (no deps)
SA14.5 (deps: SA13.1)                                                          SA18.10 (deps: SA18.6, SA18.9)
SA14.6 (no deps)                                                               SA18.11 (no deps)
```

No cross-track dependencies — all three tracks can run fully in parallel.

#### Track summary

| Track | Tasks (in order) | Theme |
|-------|------------------|-------|
| **1** | SA11.7 *(carried over)*, then SA13.1 → {SA13.2, SA13.3} → SA13.4, then SA14.1 → {SA14.2, SA14.3} → SA14.4, plus SA14.5, SA14.6 | Tenant-context request/admin boundary (Finding 3, Finding 1) |
| **2** | SA15.2 → SA15.3 *(SA15.1 complete)*, plus SA17.1–SA17.8 | Default-deny registry (Finding 2) + module-side fail-hard settings |
| **3** | ~~SA16.1~~ ✅, ~~SA16.2~~ ✅, ~~SA18.1~~ ✅, plus SA18.2–SA18.11 | Manifest-snapshot drift (Finding 4) + core/CLI fail-hard plumbing |

---

#### Finding — `org-context-api-accretion` (`why →` [Finding 3](../../arch-audit.md#finding-3-org-context-entry-is-a-five-api-accretion-every-non-request-path-hand-picks-its-idiom))

- [ ] **SA13.1 — Delete the dead context API and gate the rest.** `Tier 2 · Track 1 · deps: none · RISK LEVEL: medium`
  Delete `resolve_public_org_context` (0 callers). Underscore-privatize `set_db_current_org_id`, `set_current_org_for_context`, and `tenant_context` as internal helpers behind the public `org_scope`/`PublicSystemOrgReadMixin` surface, kept importable for the callsite migrations in SA13.2/13.3. Add an AST/import-lint gate (reuse the SA9.6 `check_module_core_imports.py` pattern) that *warns* (not yet fails) on direct external use of the privatized primitives, so the gate is in place before callsites move.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/current_org.py`, new `scripts/check_org_context_primitives.py`.
  *Acceptance:* `resolve_public_org_context` is gone; the three primitives are renamed with a leading underscore but remain importable; the new lint script runs in warn-only mode and lists today's 44 callsites without failing CI.

- [ ] **SA13.2 — Migrate view/service callsites to `org_scope`.** `Tier 2 · Track 1 · deps: SA13.1 · RISK LEVEL: medium`
  Migrate the `tenant_context`/`org_scope`-eligible callsites in module views and services (the majority of the 26 `tenant_context` + 13 `org_scope` callsites) to the blessed `org_scope`/`PublicSystemOrgReadMixin` API.
  *Files:* views/services across `crm`, `billing`, `blog`, `listings`, `notifications` (per arch-audit's caller census).
  *Acceptance:* no view/service module imports the underscored primitives directly; module test suites stay green.

- [ ] **SA13.3 — Migrate serializer/admin/feed/management-command callsites.** `Tier 2 · Track 1 · deps: SA13.1 · RISK LEVEL: medium`
  Same migration as SA13.2, scoped to the remaining callsite classes: `crm/serializers.py`, feeds, admin modules, notifications helpers, management commands (the audit's "13 files across 7 modules" spanning non-view surfaces). Runs in parallel with SA13.2 — disjoint file sets.
  *Files:* `crm/serializers.py`, module admin.py files, feed classes, management commands.
  *Acceptance:* same as SA13.2 for this file set; the SA13.1 lint gate flips from warn to **fail** once both SA13.2 and SA13.3 land (tracked as part of SA13.4).

- [ ] **SA13.4 — Flip the lint gate to hard-fail; harden the AF9 `None`-path.** `Tier 2 · Track 1 · deps: SA13.2, SA13.3 · RISK LEVEL: medium`
  Flip `check_org_context_primitives.py` from warn to fail (closing the migration). Separately evaluate and, if safe, implement AF9's `None`-path hardening (option 3 in Finding 3: prime-to-empty instead of pass-through when the ContextVar is `None`) to close the last ContextVar/GUC desync window — needs careful autocommit-path review since it changes wrapper semantics on hot paths.
  *Files:* `scripts/check_org_context_primitives.py`, `quickscale_modules/orgs/src/quickscale_modules_orgs/current_org.py`.
  *Acceptance:* lint gate fails CI on any new direct use of the privatized primitives; AF9 wrapper behavior on `None` context is either hardened (with regression tests for autocommit/atomic paths) or explicitly deferred with a written reason if the risk outweighs the benefit.

---

#### Finding — `operator-read-path-undefined` (`why →` [Finding 1](../../arch-audit.md#finding-1-elevatedoperator-reads-are-structurally-undefined--the-python-bypass-and-the-db-backstop-disagree))

- [ ] **SA14.1 — Build the orgs-owned `TenantModelAdmin` base.** `Tier 2 · Track 1 · deps: SA13.1 · RISK LEVEL: medium`
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

- [ ] **SA14.5 — Implement `operator_access(reason=...)` as a real, audited RLS predicate.** `Tier 2 · Track 1 · deps: SA13.1 · RISK LEVEL: medium`
  Add `OR NULLIF(current_setting('app.operator_access', true), '') = 'on'` to the FORCE RLS policy template and implement `operator_access(reason=...)` (superuser-gated, audit-logged context manager) as the only setter — finally implementing the contract `decisions.md` already documents as a "permanent rule" but which exists in no code today.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py` (policy template), `current_org.py` (new context manager).
  *Acceptance:* `operator_access(reason=...)` grants true cross-tenant reads for its duration only, is audit-logged, and requires superuser; without it, no code path bypasses RLS.

- [ ] **SA14.6 — Fail-hard `QUICKSCALE_MODE` when orgs is installed.** `Tier 1 · Track 1 · deps: none`
  Replace `getattr(settings, "QUICKSCALE_MODE", "solo")` with a required-setting read that raises `ImproperlyConfigured` when `orgs` is installed and `QUICKSCALE_MODE` is unset, so a saas deployment can't silently flip to solo-mode tenancy.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/middleware.py:268`.
  *Acceptance:* omitting `QUICKSCALE_MODE` in a saas-mode generated project raises at startup instead of defaulting to `"solo"`.

---

#### Finding — `registry-universe-mismatch` (`why →` [Finding 2](../../arch-audit.md#finding-2-the-default-deny-registrys-universe-is-the-orgs-test-matrix-not-the-module-set-users-can-deploy))

- [x] **SA15.1 — Add the `tenant_excluded` marker; widen classification scope; add implicit M2M inference (complete).** `Tier 2 · Track 2 · deps: none · RISK LEVEL: medium`
  Added a `has_tenant_excluded_marker()` helper and updated `is_classified_in_registry()` to consider models with the `tenant_excluded = "reason"` class attribute as classified. Widened `is_project_app()` from the `quickscale_modules_` prefix to all non-contrib installed apps, with an explicit `THIRD_PARTY_APP_PREFIXES` allowlist excluding known third-party packages. Added `_is_implicit_m2m_through()` and `_get_m2m_through_classification()` to auto-classify auto-created ManyToMany through models whose source and target models are both classified (Option A — relation inference). Updated W005 hint and CLI guidance to mention all remediation options (registry entry, `tenant_excluded` marker, and implicit M2M inference). Added generated-project caller-parity tests proving CI/Makefile templates exercise the widened classification contract. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py`, `quickscale_modules/orgs/src/quickscale_modules_orgs/checks.py`, `quickscale_modules/orgs/src/quickscale_modules_orgs/management/commands/check_tenant_isolation.py`, `quickscale_modules/orgs/tests/test_checks.py`, `quickscale_modules/orgs/tests/test_management_commands.py`, `quickscale_core/tests/test_generator/test_templates.py`.
  *Acceptance:* the classification check now considers any installed concrete model (not just `quickscale_modules_*`); models can declare exclusion via the new attribute; auto-created M2M through models are auto-classified when their related models are classified; W005 and CLI output provide actionable remediation guidance.

- [x] **SA15.2 — Backfill markers on auth/backups/notifications/storage models (complete).** `Tier 2 · Track 2 · deps: SA15.1 · RISK LEVEL: medium`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA15.3 — Derive the human-readable registry as a generated artifact; backfill excluded-model markers; remove registry fallback (complete — SA15.3 follow-up).** `Tier 1 · Track 2 · deps: SA15.2`
  Added `get_derived_registry_overview()` to `tenancy.py` — a runtime-computed registry overview derived from the `tenant_excluded` marker, implicit M2M through classification, and `TenantManager`/`TenantModel` detection instead of hand-maintaining the HTML count assertions. The literal `TENANT_TABLE_REGISTRY` is retained as a cross-check target. Replaced the doc-assertion tests in `test_doc_consistency.py` with cross-check tests that verify the derived ENROLLED set matches the literal registry for all project-owned apps. Removed the manual `<!-- enrolled-models assertion: ... -->` HTML comments from both `decisions.md` and `organizations.md`, and updated the prose in both docs to reference the marker-based derived view as the authoritative human-readable overview.
  **SA15.3 follow-up (2026-07-04):** Backfilled `tenant_excluded` markers on all excluded concrete models that lacked them: orgs control-plane models (``Organization``, ``OrganizationMembership``, ``OrganizationInvitation``, ``OrganizationTombstone``), billing system-wide metadata (``Plan``, ``WebhookEvent``), blog user-profile (``AuthorProfile``), and test-only models (``ConcreteTenantResource``, ``ForwardFKChild``). Removed the ``REGISTRY_LOOKUP`` fallback from ``get_derived_registry_overview()`` — the `else` branch that silently classified non-marker-detectable models as ``EXCLUDED_REVIEWED`` now issues ``continue`` instead. Strengthened ``test_doc_consistency.py`` with three new cross-check tests: ``test_derived_registry_full_overview_matches_literal`` (full status/app_label/model_name parity for installed models), ``test_derived_registry_no_fallback_reason`` (asserts no entry uses a registry-fallback reason string), and ``test_derived_registry_covers_installed_exclusions`` (every model with a ``tenant_excluded`` marker appears in derived overview). Updated docs to reflect the purely marker-driven derivation.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/models.py`, `quickscale_modules/orgs/tests/test_models.py`, `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py`, `quickscale_modules/orgs/tests/test_doc_consistency.py`, `quickscale_modules/billing/src/quickscale_modules_billing/models.py`, `quickscale_modules/blog/src/quickscale_modules_blog/models.py`, `docs/technical/decisions.md`, `docs/technical/organizations.md`, `docs/technical/roadmap.md`, `CHANGELOG.md`.
  *Acceptance:* the registry overview is generated from model markers **with no registry fallback**; every excluded model declares its own marker; the cross-check test suite (ENROLLED parity, full overview parity, no-fallback-reason, and exclusion coverage) passes in CI.

---

#### Finding — `per-module-knowledge-fanout` (`why →` [Finding 4](../../arch-audit.md#finding-4-per-module-contract-knowledge-is-still-fanned-across-6-hand-written-surfaces--and-the-duplicate-manifest-snapshots-already-drift)) — urgent slice only

- [x] **SA16.1 — Add the manifest sync gate; sync all drifted core snapshots (complete — 2026-07-03).** `Tier 1 · Track 3 · deps: none`
  Created `scripts/sync_module_manifests.py` with `--check` (default, compares source vs snapshot, exits 1 on drift) and `--sync` (copies source to snapshot) modes. Wired as `make check-manifest-sync` (included in `make check` and `make ci`), step 5 in `scripts/check_ci_locally.sh`, and a `manifest-sync-gate` CI job that gates `test`, `isolation-conformance`, and `lint-cli`. All 12 module manifests are now in sync — synced `backups`/`blog`/`billing`/`crm`/`listings`/`social` core snapshots to match their source counterparts (version floor, contract vintage, and derivation metadata).
  *Files:* new `scripts/sync_module_manifests.py`, `quickscale_core/src/quickscale_core/data/manifests/{backups,blog,billing,crm,listings,social}/module.yml`, `Makefile`, `.github/workflows/ci.yml`, `scripts/check_ci_locally.sh`.
  *Acceptance:* `diff`-ing module-owned and core-snapshot `module.yml` files is empty; CI fails if a future PR reintroduces drift.

- [x] **SA16.2 — Fix SSOT doc drift on shipped features (complete — 2026-07-03).** `Tier 1 · Track 3 · deps: none`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.
  *Finding:* after syncing `wt-track3` with `v87`, the shipped-state wording was already present in `decisions.md`; this phase closes the stale roadmap status and changelog alignment.

---

### Fail-Hard Remediation (opened 2026-07-03)

Fix plan derived from [tech-audit.md](../../tech-audit.md) (`TA1`–`TA15`). `SA17` covers module-side settings defaults (Track 2, pairs naturally with the registry work); `SA18` covers core/CLI/generator plumbing (Track 3, pairs with the manifest-fanout work). Both continue the `SAn.m` sequence.

#### `SA17` — Module-side settings and config fail-hard fixes (Track 2)

- [ ] **SA17.1 — Reject legacy config keys instead of silently translating/dropping them.** `Tier 2 · Track 2 · deps: none · (why → TA1)`
  In `normalize_auth_module_options()` and the CRM/notifications equivalents, raise `ConfigValidationError` naming the legacy key and its replacement instead of silently mapping (`allow_registration` → `registration_enabled`) or dropping (`social_providers`, `default_pipeline_stages`, `_LEGACY_NOTIFICATIONS_SECRET_OPTIONS`) the key.
  *Files:* `quickscale_core/src/quickscale_core/contracts/resolvers.py` (~:222-233, :556, :780).
  *Acceptance:* a `quickscale.yml` containing any of the named legacy keys fails `quickscale plan`/`apply` with an error naming the dead key and its replacement, instead of silently changing behavior.

- [ ] **SA17.2 — Fail-hard analytics/billing enabled-flag settings.** `Tier 2 · Track 2 · deps: none · RISK LEVEL: medium (billing) · (why → TA2)`
  Add module `apps.py` Django system checks that raise `ImproperlyConfigured` when `QUICKSCALE_ANALYTICS_ENABLED` / `QUICKSCALE_BILLING_ENABLED` are missing, instead of defaulting `True`; the generator already knows these values at generation time and must guarantee emission.
  *Files:* `analytics/services.py:61`, `billing/services.py:117`, and each module's `apps.py`.
  *Acceptance:* omitting either setting from a generated project raises at startup instead of silently enabling the feature.

- [ ] **SA17.3 — Fail-hard CRM's API-enable flag and page-size settings.** `Tier 1 · Track 2 · deps: none · (why → TA2)`
  `CRM_ENABLE_API` required (no `True` default); replace `int(getattr(...) or 50)` page-size reads with explicit validation that rejects non-numeric values instead of silently swallowing them to `50`.
  *Files:* `quickscale_modules/crm/src/quickscale_modules_crm/views.py:219,238,246`.
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

- [ ] **SA17.7 — Replace optional-dependency soft degradation with generation-time wiring.** `Tier 2 · Track 2 · deps: SA17.2, SA17.5 · (why → TA9)`
  Analytics' PostHog SDK import failure currently logs a warning and disables capture; forms' analytics integration currently probes for the sibling module via a soft `ImportError`/`getattr(None)` chain. Since module assembly happens at generation time, wire the analytics↔forms integration (and the PostHog SDK requirement) as a hard dependency the generator resolves, not a runtime probe. Depends on SA17.2/17.5 landing the surrounding settings checks first so the two changes don't fight over the same code paths.
  *Files:* `analytics/services.py:218-223`, `forms/views.py:92-97`.
  *Acceptance:* if analytics is assembled into a project, a missing PostHog SDK raises at startup (not a warning); forms' analytics integration is generation-time wired, not runtime-probed.

- [ ] **SA17.8 — Remove or gate deprecated `module_catalog` compat delegates; fix fail-open readiness.** `Tier 1 · Track 2 · deps: none · (why → TA12)`
  Remove `get_module_names()`/`get_module_entries()` from the public `contracts/__init__.py` API (or add the mandated `# F-EXCEPTION:` tag if a caller genuinely still needs them), and make `get_module_readiness_reason()` raise or return an explicit "unknown module" sentinel for unrecognized names instead of `None` (indistinguishable from "ready").
  *Files:* `quickscale_core/src/quickscale_core/contracts/module_catalog.py:128-175,270-289`.
  *Acceptance:* the deprecated delegates are either removed from the public API or carry an `# F-EXCEPTION:` tag; readiness checks on an unknown module name raise/return a distinguishable value from "ready".

#### `SA18` — Core/CLI/generator plumbing fail-hard fixes (Track 3)

- [x] **SA18.1 — Narrow the import-time `except Exception: pass` in manifest adapter init (complete — 2026-07-03).** `Tier 1 · Track 3 · deps: none · (why → TA3)`
  Replaced the module-level broad swallow with a targeted import-time initializer that defers only the documented partially-initialized core circular-import case. `refresh_managed_adapters()` now preserves the underlying `ImportError` as the `ImproperlyConfigured` cause, so genuinely broken managed adapters fail at import time instead of being masked.
  *Files:* `quickscale_core/src/quickscale_core/manifest/entry_point.py`, `quickscale_core/tests/test_manifest_entry_point.py`.
  *Acceptance:* a deliberately broken adapter registration raises at import time; only the documented circular-import case is swallowed.
  *Finding:* the tolerated import-time cycle is narrower than the old comment implied — the defer path is now limited to partially initialized `quickscale_core.manifest.entry_point` / `quickscale_core.contracts.resolvers` imports. No blockers discovered.
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [ ] **SA18.2 — Raise instead of silently defaulting empty analytics manifest settings.** `Tier 1 · Track 3 · deps: none · (why → TA4)`
  Empty-after-resolution analytics settings currently get silently replaced with hardcoded defaults ("fallback defaults matching legacy behaviour"); an empty result after resolution means the derivation produced an invalid result and should raise.
  *Files:* `quickscale_core/src/quickscale_core/manifest/entry_point.py:302-311`.
  *Acceptance:* an empty-after-resolution analytics config raises a descriptive error instead of silently filling in `posthog`/`us.i.posthog.com` defaults.

- [ ] **SA18.3 — Delete the `quickscale_cli.schema` compat shim.** `Tier 2 · Track 3 · deps: none · (why → TA5)`
  Migrate the CLI's own internal imports (`utils/project_manager.py`, `utils/module_wiring_manager.py`, `commands/plan_command.py`, `commands/remove_command.py`) to `quickscale_core.schema` directly, then delete the undocumented `quickscale_cli/src/quickscale_cli/schema/` shim package.
  *Files:* `quickscale_cli/src/quickscale_cli/schema/*`, the four internal-import call sites listed above.
  *Acceptance:* `quickscale_cli/src/quickscale_cli/schema/` no longer exists; all CLI code imports schema types from `quickscale_core.schema`.

- [ ] **SA18.4 — Fix generator template-resolution fallback chains.** `Tier 2 · Track 3 · deps: none · (why → TA6)`
  Replace the template-dir discovery guess chain (dev dir → package dir → cwd-relative guesses) with a single deterministic resolution rule (installed package path, with an explicit override param for dev use); delete the "backward compatibility" root-template fallback tier in `_get_theme_template_path` and raise immediately with the attempted path on a miss instead of deferring to a later `TemplateNotFound`.
  *Files:* `quickscale_core/src/quickscale_core/generator/generator.py:96-131,165-178`.
  *Acceptance:* template resolution follows one deterministic rule; a missing template raises immediately naming the attempted path, not a downstream Jinja `TemplateNotFound`.

- [ ] **SA18.5 — Remove the version fallback chain's terminal `"0.0.0"` default.** `Tier 1 · Track 3 · deps: none · (why → TA7)`
  Narrow the `except Exception` around `from ._version import __version__` to `ImportError` (or the specific expected failure), keep the legitimate dev-tree `VERSION`-file read, but raise instead of silently returning `"0.0.0"` when both resolution paths fail.
  *Files:* `quickscale_core/src/quickscale_core/version.py:16-27`.
  *Acceptance:* a broken build (missing `_version.py` and `VERSION` file) raises instead of reporting version `"0.0.0"`.

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
