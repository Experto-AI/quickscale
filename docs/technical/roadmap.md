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

---

## Decisions locked

| Finding | Choice |
|---|---|
| 1 — Tenant isolation | **C** — default-scoped manager (contextvar) **+** Postgres RLS backstop |
| 2 — Ownership contract | **A + C** — universal NOT NULL + reserved System org + one teardown policy |
| 3 — Module wiring | **A** — self-describing manifests + generic resolver; delete the `if`-ladder |
| 4 — Routing | **A** — one URL tree: `/crm/...` for both solo and saas; no `/orgs/<slug>/crm/...` |
| 5 — DR | **A** — hard cutover: delete the legacy env-var protocol, single typed adapter |
| F1 — RLS boot guard | Boot-time `rolbypassrls` assertion in orgs `AppConfig.ready()`; fail-fast in saas/prod if connected role has BYPASSRLS — **implemented T1.18** |
| F2 — Unified org scope | Promote `_billing_org_db_context` to `orgs.current_org.org_scope()`; middleware + billing use the shared primitive; phase out manual `all_objects` + filter sites — **implemented T1.19** |
| **AF1 — child-table policy** | **C** — denormalize `organization_id` onto every child table; every tenant-owned table carries the column and uses a direct FORCE-RLS policy; parent-join RLS policies are not used. This is the project default for all future child/detail tables. |
| **AF7 — module adapter resolution** | **Fail-hard** — no core fallback adapters; `refresh_managed_adapters()` must raise `ImproperlyConfigured` if a managed module's adapter (`quickscale_modules_{name}.adapter`) is not importable; bundled/installed-without-module-source is not a supported context. Delete `_CORE_FALLBACK_ADAPTERS` and the three fallback functions. |
| **AF9 — GUC / ContextVar desync** | **B** — install a Django `execute_wrapper` (or `connection_created` signal) that, on the first statement of every transaction, issues `SET LOCAL app.current_org_id` from `get_current_org_id()`; the ContextVar is the sole source of truth; the two isolation layers can never desync; no per-view discipline required. |
| **AF11 — empty-string-unsafe RLS cast** | **A** — replace `current_setting(…,true)::uuid` with `NULLIF(current_setting(…,true),'')::uuid` in `_FORCE_RLS_FORWARD_SQL` (`orgs/tenancy.py`); one template edit + one sweep migration that drops and recreates every enrolled policy from the corrected template; conformance gate extended to assert `''`-GUC → 0 rows. |
| **AF12 — child-parent equality trigger asymmetry** | **A** — composite FK `(parent_id, organization_id)` on child tables referencing `(parent.id, parent.organization_id)` with a unique constraint on the parent; the database makes a divergent pair structurally impossible; drop the child-only equality trigger. |
| **AF13 — SQLite fallback in test settings** | Delete the `QUICKSCALE_TEST_DB` branch and SQLite `:memory:` default from all 11 `tests/settings.py` files; replace with an unconditional `django.db.backends.postgresql` block reading env vars with sensible defaults; update the Module Implementation Checklist template so new modules start Postgres-only. |
| **AF10 — isolation tests skipped in CI** | **B** — dedicated `isolation-conformance` CI job: Postgres 18 service, NOBYPASSRLS runtime role, `migrate` applied, runs the conformance gate + all `test_rls_boundary.py` + one authenticated-request integration test under the restricted role; fail if any isolation test is skipped. |
| **AF3 — operator escape hatch unaudited** | **A** — single `operator_access(reason=...)` context manager in `orgs/`; the only path to the unfiltered queryset and the privileged role; emits structured audit records; management commands (`purge_organization`, `migrate_billing_to_orgs`, `forms_anonymize_submissions`) routed through it; `all_objects` removed from model declarations — **implemented wt-track1** |
| **VIEW-AS — operator debug mode** | **A** — session key `quickscale_modules_orgs.debug_as_org_id` (superuser-only); `TenantMiddleware._resolve_debug_org()` hook overrides normal Solo/SaaS resolution when set; `OrganizationAdmin` entry/exit views with per-row VIEW-AS button and exit form activate/deactivate it; base-template debug banner shows while active; every activation audit-logged (who, which org, timestamp). No BYPASSRLS — same restricted runtime role as normal tenant path. Depends on AF9. |

**Global constraints:** no backward compatibility, no migration path, no existing users — every change is a clean break. Drop dead paths outright; squash/rewrite migrations rather than layering compat shims.

## Design decisions (D1–D5)

- **D1 — saas org source.** Content URLs lose `<slug:org_slug>` (Finding 4A). Saas resolves the active org from **session active-org** set by the existing org switcher. Org-admin API may keep `/api/orgs/<slug>/`.
- **D2 — public/anonymous content owner.** With NULL gone, public pages (blog feed, public listings, social links) need an owner. **System org owns published-public content.** Anonymous visitors see System-org rows; solo authed = personal org; saas authed = active org.
- **D3 — teardown policy.** **`on_delete=PROTECT` + explicit `purge_organization` command** (ordered, FK-safe delete) — GDPR-capable, no accidental cascade.
- **D4 — RLS role.** App DB role is `NOSUPERUSER` + `NOBYPASSRLS`; superuser/admin and management commands set `app.current_org_id` or connect under an explicit operator role. Generator settings/templates updated.
- **D5 — migrations.** No users → no data backfill. Rewrite/squash module migrations to the clean NOT NULL contract; delete `null=True`, `isnull` flat-bucket logic, and `/orgs/<slug>/` content routes outright.

---

## v87 Structural Findings — Complete ✅

All structural findings from the 2026-06-28 autopsy are resolved and merged to `v87`. See [CHANGELOG.md](../../CHANGELOG.md) for full implementation details.

**Track status (2026-06-30):** All three tracks clean — no open work on any track.

| Task | Track | Completed | Summary |
|---|---|---|---|
| **AF13** ✅ | `wt-track3` | 2026-06-29 | Postgres-only test settings in all 11 modules; SQLite smoke-test helper replaced — see CHANGELOG |
| **AF10** ✅ | `wt-track3` | 2026-06-29 | Isolation-conformance CI job (Postgres 18 + NOBYPASSRLS role) — see CHANGELOG |
| **AF11** ✅ | `wt-track2` | 2026-06-29 | NULLIF empty-string guard in RLS policy template; 6 sweep migrations — see CHANGELOG |
| **AF12** ✅ | `wt-track2` | 2026-06-29 | Composite FK for child-parent org equality; all blocking findings resolved — see CHANGELOG |
| **AF3** ✅ | `wt-track1` | 2026-06-29 | Single audited `operator_access(reason=...)` seam; AST-level conformance proof — see CHANGELOG |
| **AF9** ✅ | `wt-track1` | 2026-06-30 | Connection-layer GUC priming execute wrapper; PostgreSQL vendor guard — see CHANGELOG |
| **VIEW-AS** ✅ | `wt-track1` | 2026-06-30 | Operator org-impersonation debug mode; admin entry/exit views; debug banner; 34+ tests — see CHANGELOG |

---

## Pre-existing issues (non-blocking, discovered during AF9 validation)

These are outside v87 scope but should be tracked for a future pass:

- **CRM mypy** — import-not-found error in `adapter.py` (pre-existing).
- **CRM T1.11** — baseline-red tests in the full CRM suite; targeted validation was used for AF9 closeout.
- **Listings conftest** — DB-setup issue (`migrate --run-syncdb` skips migrated apps, leaving orgs tables uncreated); AF9 listings restricted-role proof relocated to the orgs conformance surface as a workaround.

---

## Explicitly out of scope

Single-PR items that do not change the design:

- Orphaned `apply-recovery.yml` cleanup after a crashed final state-write.
- Pinning the Stripe SDK `api_version` as a one-liner.
- Missing `list_filter`/`select_related` in individual admin classes.
- Individual `pragma: no cover` lines.

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [findings.md](../../findings.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
