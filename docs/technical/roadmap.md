# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work Only)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks only pending roadmap work. Completed history is in [CHANGELOG.md](../../CHANGELOG.md). Each phase is sized as Adaptive Tier 1–2; split before implementing if a checklist item is Tier 3.

**Rules:**
- Keep only open todo items here.
- Move completed implementation history to CHANGELOG.md in concise form.
- Each phase links back (`why →`) to the finding that justifies it.

## Parallel Execution Tracks

Work is split across 3 git worktrees that develop in parallel and merge back to `v87` after each phase. `v87` is the clean integration branch — never commit directly to it.

### Track assignment

| Track | Worktree | Branch | Owns |
|-------|---------|--------|------|
| 1 | `quickscale-wt-track1` | `wt-track1` | M7 — F11 module isolation (F11.12b–F11.13b) |
| 2 | `quickscale-wt-track2` | `wt-track2` | M10 — F5 DR engine split (F5.2b–F5.4) |

### Cross-track dependency

Track 3 (M5/M8/M11) is complete. No remaining cross-track dependencies.

### Start procedure

Run at the beginning of every new phase, before touching any files:

```bash
cd /home/victor/code/quickscale-wt-track{N}
git status             # must be clean — commit or stash any in-progress work first
git merge v87          # pull in everything other tracks have merged since last sync
# resolve any conflicts, then continue with the phase
```

> **Why every phase:** other tracks land changes on `v87` between your phases. Starting from a stale base makes conflicts larger and harder to resolve later.

### Merge procedure

Run when a phase (or a full milestone) is complete and ready to integrate:

```bash
cd /home/victor/code/quickscale-wt-track{N}
git merge v87          # sync latest before merge-back; resolve conflicts here
# run phase verification tests
cd /home/victor/code/quickscale
git merge --no-ff wt-track{N}
```

### Merge checkpoints

| # | Track | Phases | Status | Condition |
|---|-------|--------|--------|-----------|
| M1 | 1 | F11.2–F11.5 | 🟢 | **Merged to v87.** F11.2 ✅ F11.3 ✅ F11.4 ✅ F11.5 ✅. |
| M3 | 1 | F11.6–F11.10 | 🟢 | **Merged to v87.** F11.6 ✅ F11.7 ✅ F11.8 ✅ F11.9 ✅ F11.10a ✅ F11.10b ✅ F11.10c ✅ F11.10d ✅ F11.10e ✅. Full closeout: same-org FK audit/fix (225/225), pre-sync and post-sync closeout slices each 254/254, all runtime tests passing. **Next:** M7 / F11.11. |
| M5 | 3 | F2.5–F2.9b | 🟢 | **Merged to v87.** F2.5 ✅ F2.6 ✅ F2.7 ✅ F2.8 ✅ F2.9a ✅ F2.9b ✅. |
| M7 | 1 | F11.11–F11.13b | 🟡 | **Pending merge to v87.** F11.11 ✅, F11.12a ✅, F11.12b ✅, F11.13a ✅, **F11.13b ✅**. Blog, forms, listings, and social isolation all implemented and reviewed. Structural isolation rollout complete — non-view paths verified (admin `get_queryset` uses explicit operator managers; `forms_anonymize_submissions` uses `Form.all_objects.all()`); adoption path documented in `organizations.md`. Pre-existing forms migration-ordering blocker (0002 vs 0004) fixed by rewriting `0002_seed_forms.py` to use historical models. Repo-root `make test` clean across all modules. Blog admin org-scoping/safeguards implemented via blog-local org-aware mixin plus same-org validation. F11 complete. M7 closeout (pending independent review and merge to v87). |
| M8 | 3 | F12.1–F12.3b | 🟢 | **Merged to v87.** F12.1 ✅ F12.2 ✅ F12.3a ✅ F12.3b ✅. Railway rollback/resume closeout complete. |
| M9 | 1 | F13.1–F13.3 | 🟢 | **Merged to v87.** F13.1 ✅ F13.2 ✅ F13.3 ✅. Org-authoritative billing contract; `quickscale_billing_unique_current_subscription_per_organization` constraint; dual-FK rows backfilled via migration; mgmt command provided. |
| M10 | 2 | F5.2a–F5.4 | 🟢 | **Merged to v87.** M6 ✅ + M8 ✅ merged; F5.1 ✅ boundary contract in decisions.md. F5.2a ✅ snapshot/archive primitives extracted to `quickscale_core.dr_engine.primitives`. F5.2b ✅ restore/orchestration/verification extracted to `dr_engine.recovery` and `dr_engine.verification`. F5.3 ✅ protocol replacement + module slimming. F5.4 ✅ migration docs added to `docs/technical/dr_engine_migration.md`. All Track 2 phases complete. |
| M11 | 3 | F7.1–F7.3 | 🟡 | M8 merged; F7.1 ✅, F7.2 ✅ (ownership split, runtime_pins.py SSOT, templates variableized). F7.3 pending — validation and doc alignment. |

## In-Flight Milestones

### M7 — F11 Module isolation rollout (blog/forms/listings/social)
**Track:** 1 | **Worktree:** `quickscale-wt-track1`

**Status:** 🟡 Complete — all F11 phases (F11.11–F11.13b) implemented and validated; pending independent review and merge to `v87`. F11 complete. M7 closeout.

---
## Backlog

### Sequencing

Execute top-down. Earlier items are prerequisites for or de-risk later items.

| Priority | Finding | Milestone(s) | Status |
|----------|---------|-------------|--------|
| 1 | F11 — Structural multi-tenant isolation | M1 → M3 → M7 | 🟢 M1 merged, M3 merged/closed, **M7 closeout (pending independent review and merge)**; all F11 phases complete |
| 2 | F2 — Project state + module provenance | M5 | 🟢 M5 merged to v87 |
| 3 \| parallel | F13 — Single billing customer SSOT | M9 | 🟢 M9 merged to v87 |
| 5 | F5 — DR engine split | M10 | 🟢 M10 merged to v87. |
| 6 | F7 — Generator vs generated-project runtime pins | M11 | 🟡 F7.1 ✅, F7.2 ✅ (ownership split, runtime_pins.py SSOT). F7.3 pending — validation, doc alignment. |

---

### Finding 11 — Enforce structural multi-tenant isolation

**Status:** ✅ Complete — all phases F11.2–F11.13b implemented and validated. M1/M3 merged to `v87`; M7 closeout pending independent review and merge. Completed work archived in CHANGELOG.md.

---

**F11-deferred — Stage `terminal_semantic` per-org uniqueness** _(Adaptive tier: 2)_ _(unlocked by F11.5)_

- [ ] Split `Stage.terminal_semantic` uniqueness to per-bucket partial `UniqueConstraint`s; add migration + serializer + API regression coverage.

---

**Phase F11.12b — Listings isolation** _(M7)_ _(Adaptive tier: 2)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** M3 merged.

**Status:** ✅ Complete — implemented on `wt-track1`. Added `organization` FK (nullable) to `AbstractListing` with per-org slug uniqueness constraint, dual-manager contract (`TenantScopedManager` + `OperatorManager`), and additive `orgs/<slug>/` org-scoped routes (under `listings/` prefix) alongside flat paths. Route-aware views scope queries via `_is_org_scoped_route()`/`_resolve_active_org_optional()`. All 96 listings module tests pass. Isolation test unskipped and green. **Next:** F11.13a.

**Groundwork committed to `wt-track1` (2026-06-22):**
- ✅ `organization` FK on `AbstractListing` — per-org slug uniqueness via `UniqueConstraint` on `Listing`.
- ✅ Dual-manager contract: `TenantScopedManager` + `OperatorManager` with `Listing.for_org()`.
- ✅ Additive org-scoped routes (`orgs/<slug>`) for list/detail/publish under `listings/` prefix.
- ✅ Route-aware views via `OrgScopedViewMixin._scope_by_org()` — flat routes scope to `organization__isnull=True`, org routes scope to active org.
- ✅ `create_published_listing_from_payload` accepts org context for stamping and per-org slug checks.
- ✅ Test settings updated (`quickscale_modules_orgs`, `TenantMiddleware`, `QUICKSCALE_MODE=saas`).
- ✅ Org fixtures and isolation test implemented and green.

- [x] Apply `organization_id` FK + isolation policy to `listings`.
- [x] Unskip and confirm `listings` isolation test green.

**Phase F11.13a — Social isolation** _(M7)_ _(Adaptive tier: 2)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.11 + F11.12a + F11.12b.

**Status:** ✅ Complete and implemented on `wt-track1`. Added `organization` FK (nullable) to `BaseSocialItem` with dual-manager contract (`TenantScopedManager` + `OperatorManager`) and per-org service queries. Removed global `unique=True` on `normalized_url` so multiple orgs may link to the same social URL. `list_published_social_links()` and `list_published_social_embeds()` accept an optional `organization_id` parameter for tenant-scoped queries while preserving backward compatibility. Social module isolation tests unskipped and green. **Next:** F11.13b.

- [x] Apply `organization_id` FK + isolation policy to `social`.
- [x] Remove global `normalized_url` uniqueness to allow same-URL usage across orgs.
- [x] Add `TenantScopedManager` + `OperatorManager` dual-manager contract.
- [x] Add org-scoped parameter to `list_published_social_links()` and `list_published_social_embeds()`.
- [x] Unskip and confirm social isolation tests green.

**Phase F11.13b — Rollout closeout** _(M7 closeout)_ _(Adaptive tier: 1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.13a.

**Status:** ✅ Complete and validated; pending independent review and merge to `v87`. All closeout checklist items addressed:

- **Non-view path verification:** `require_org_role`/`require_org_feature` confirmed as second-line defense. Blog/forms/listings/social admin `get_queryset` uses explicit operator managers (`all_objects`). `forms_anonymize_submissions` uses `Form.all_objects.all()`. Targeted admin/management tests added.
- **Adoption path documented:** Structural isolation migration path for existing projects added to `organizations.md` (F11.13b — Structural Isolation Rollout: Adoption Path for Existing Projects section).
- **Module isolation tests:** blog 219/219, forms 138/138, listings 111/111, social 52/52 — all unskipped and passing. Forms pre-existing migration-ordering blocker fixed by rewriting `0002_seed_forms.py` to use historical models.

**Validation findings (quality-gate closeout):** Lint/format fixes applied to touched files. Changed-module admin/management tests pass. Forms migration-ordering blocker fixed by rewriting `0002_seed_forms.py` to use historical models. Repo-root `make test` clean across all modules — quickscale_core 1404 passed / 28 deselected, quickscale_cli 1798 passed / 28 deselected, blog 219 passed, forms 138 passed, listings 111 passed, social 52 passed; overall mean coverage 92.92%. Blog admin org-scoping/safeguards implemented via blog-local org-aware mixin plus same-org validation.

**F11 complete. M7 closeout (pending independent review and merge to v87).**

- [x] Keep `require_org_role`/`require_org_feature` as second-line defense; verify isolation fails closed for non-view paths (admin, shell, management commands, async jobs).
- [x] Document the migration path for already-generated projects adopting structural isolation.
- [x] Unskip all remaining module isolation tests and confirm all green.

---

### Finding 5 — Split the DR engine out of the embeddable backups module

**Status:** ✅ All phases complete. See CHANGELOG.md for per-phase implementation summaries and `docs/technical/dr_engine_migration.md` for the migration guide.

**Track:** 2 | **Worktree:** `quickscale-wt-track2` | **Merges as:** M10
**Dependencies:** M6 ✅ + M8 ✅ merged.

**Phase F5.2a — Extract snapshot and archive primitives** _(Adaptive tier: 2)_ _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_ — ✅ **Complete.**

- [x] Extract snapshot and archive primitives into a CLI/core-owned engine library while preserving current behavior.

**Phase F5.2b — Extract restore and orchestration** _(Adaptive tier: 2)_ _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_ — ✅ **Complete.**

**Dependencies:** F5.2a.

- [x] Extracted restore/orchestration flow into `quickscale_core.dr_engine.recovery`.
- [x] Extracted verification recording and rollback-pin handling into `quickscale_core.dr_engine.verification`.
- [x] Preserved thin Django-facing wrappers in `quickscale_modules_backups.services`.
- [x] Added core recovery/verification tests and targeted backups service tests.

**Validation evidence (F5.2b closeout):** Repo-root `make test` passed — quickscale_core 1392 passed / 28 deselected / 93.03% coverage; quickscale_cli 1778 passed / 28 deselected / 91.58% coverage; backups module 227 passed / 84.41% coverage; overall mean 93.33%; all modules green with only the expected existing skips (forms/listings/orgs/social isolation or PostgreSQL-dependent skip).

**Phase F5.3 — Slim the module and protocol** _(Adaptive tier: 2)_ _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_ — ✅ **Complete.**

**Dependencies:** F5.2b.

**Status:** ✅ Complete. See CHANGELOG.md for full implementation summary.

- [x] Replaced hidden docker-exec/management-command/env-var/stdout-JSON protocol with explicit typed adapter (`quickscale_core.dr_engine.adapter`).
- [x] Added single `dr_adapter_call` management command bridge in the backups module (thin dispatch surface only).
- [x] Rewrote `dr_commands.py` to call the adapter through the bridge — removed `_run_backend_container_command`, `_run_manage_json`, `_build_manage_overrides`/`_source_manage_overrides`/`_target_manage_overrides`, `_prefix_target_runtime_variables`, `_target_media_sync_variables`, `_is_manual_only_restore_gate`, and the `_TARGET_ENV_PREFIX` env-var protocol.
- [x] Slimmed `sync_backup_snapshot_media()` in services.py — added explicit `target_runtime_settings` parameter; the adapter path uses this parameter with an explicit `ROUTE_KIND` marker to preserve the Railway-target media fail-closed guard, while the env-var fallback (`_load_target_runtime_settings()`) is preserved for admin/manual use through the retained management commands.
- [x] Remaining management commands kept as thin Django/admin-facing surfaces with backward-compatible env-var fallback (backups_create, backups_report, backups_restore, backups_record_verification, backups_pin, backups_sync_media, backups_validate, backups_prune).
- [x] CLI `quickscale dr` surface unchanged — all capture/plan/execute/report workflow preserved. Env-sync planning and Railway API calls remain in CLI orchestration.

**Phase F5.4 — Migration docs** _(M10 closeout)_ _(Adaptive tier: 1)_ _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_ — ✅ **Complete.**

**Status:** ✅ Complete. Authored `docs/technical/dr_engine_migration.md` — standalone migration guide covering the post-split architecture overview, migration path for existing generated projects (`quickscale apply` syncs the `quickscale-core` dependency entry automatically, but standalone projects may need to adjust the synced source for their layout), backward compatibility table, dependency changes, and verification checklist. Roadmap and CHANGELOG updated. **M10 closeout — all Track 2 phases complete.**

- [x] Document the migration and compatibility contract for existing generated projects adopting the split DR architecture.

---

## Deferred / Monitor

- [ ] **Documentation consolidation** _(Adaptive tier: 2)_ — defer until doc drift causes real onboarding failures; manifest work (F1) simplifies auto-generated module facts.
- [ ] **Broader compatibility-window widening** _(Adaptive tier: 2)_ (F7 follow-on) — monitor user-reported version conflicts before investing beyond runtime-pin decoupling.
- [ ] **Emitted-project operability & API-contract substrate** _(deferred — split into Tier 1/2 sub-items below)_ — generated modules ship with no structured logging/correlation IDs, no versioned public API, and no webhook payload boundary validation. Promote to active backlog when a second external provider lands or the first public-API consumer appears. Stripe SDK `api_version` pinning is already listed below as a one-liner.
  - [ ] _(Tier 1)_ Add structured logging and correlation-ID baseline to generated modules.
  - [ ] _(Tier 2)_ Add versioned public-API surface (`/api/vN`) to generated module `urls.py`.
  - [ ] _(Tier 2)_ Add webhook payload boundary validation baseline.

### Explicitly out of scope

Single-PR/ticket items that do not change the design:

- Orphaned `apply-recovery.yml` cleanup after a crashed final state-write.
- Pinning the Stripe SDK `api_version` as a one-liner.
- Missing `list_filter`/`select_related` in individual admin classes.
- Individual `pragma: no cover` lines.

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
