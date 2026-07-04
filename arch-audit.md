# Structural Autopsy: QuickScale

> **Prior autopsy (2026-06-30): Closed 2026-07-02.** All 5 findings remediated and merged to `v87` (SA1.1–SA5.2); see [CHANGELOG.md](CHANGELOG.md). Closed findings dropped per template rule.
>
> **Closed 2026-07-03:** Findings 2 (orgs god-module — SA7.2–SA7.4), 3 (dual active-org truth — product decision D1), and 4 (core-as-runtime-API — SA9.1–SA9.6). Closeout in [CHANGELOG.md](CHANGELOG.md). Sections dropped below per template rule.
>
> **Closed 2026-07-04** (from the 2026-07-03 fresh-pass autopsy below): `registry-universe-mismatch` (SA15.1–SA15.3, entire finding), `per-module-knowledge-fanout` (SA16.1–SA16.2, entire finding), and `org-context-api-accretion` (SA13.1–SA13.4, entire finding — Finding 3). Finding 3 was remediated via its own preferred option 1 ("Consolidate + gate"): the five overlapping context primitives are now privatized behind `org_scope`/`PublicSystemOrgReadMixin`, all 44 callsites migrated, and the AST lint gate (`check_org_context_primitives.py`) flipped to hard-fail. Closeout in [CHANGELOG.md](CHANGELOG.md). Sections dropped below per template rule.
>
> **Closed 2026-07-03** (from the 2026-07-02 autopsy below, reconciled 2026-07-04): Finding 5 (module↔generated-project contract drift — remediated by SA10.1/SA10.2's `project_contract`/contract-vintage mechanism, the finding's own preferred option 3) and Module Finding 1 (request→tenant-context boundary — remediated by SA11.1–SA11.7's shared `PublicSystemOrgReadMixin`/DRF permission baseline, the finding's own preferred option 1). Both were already treated as resolved in `roadmap.md`'s closed-batches note but never formally closed here; closeout detail in [CHANGELOG.md](CHANGELOG.md). Sections dropped below per template rule.

This file is reused as the template for the next structural autopsy — keep the orientation current, drop closed findings once remediated.

---

## Autopsy — 2026-07-02

### Orientation

A creator-led (solo maintainer, 1,381 commits, weekly cadence, tags through 0.86.0) **monorepo of three archetypes**: a CLI (`quickscale_cli`, Click), a generator/engine library (`quickscale_core`: Jinja2 scaffolding, plan/apply state machine, manifest stack, DR engine), and ~13 first-party Django modules (`quickscale_modules/*`) distributed into generated projects as user-owned git subtrees. Generated apps: Django 6 + PostgreSQL 18, single Railway deployment, multi-tenant via FORCE RLS + `TenantManager` (v0.86.0 architecture, hardened by the 2026-06-30 autopsy remediation). Tool-side state: `quickscale.yml` (desired) / `.quickscale/state.yml` (applied), advisory-locked apply with a saga-style recovery ledger. **Growth direction:** teams module (placeholder today; design locked in `docs/technical/organizations.md`), more org-scoped tenant tables (Option C: every child table carries `organization_id`), vertical themes planned. **Stated-vs-actual gaps noted:** `decisions.md:1145` references `findings.md §Finding-8` and `roadmap.md §AF8`, which no longer exist; the Module Implementation Checklist still describes `AVAILABLE_MODULES` as a hand-edited list though it is now discovery-derived (`module_commands.py:65`). **Depth:** read fully — the module-wiring seam (CLI `module_config.py`/`apply_command.py`, core `contracts/*`, `manifest/entry_point.py`), the tenancy seam (`orgs` tenancy/managers/middleware/checks), module manifests, decisions.md; sampled — DR engine, theme templates, generated-project templates, apply ledger; skipped — module domain logic internals, devtools, htmlcov/examples. Roadmap is empty ("no open items"), so urgency judgments below are calibrated to the teams/SaaS direction, not to scheduled work.

Severity floor: the CLI/generator is a single-process local tool (concurrency lenses discounted); generated apps are single-service WSGI (distributed-systems lenses discounted); tenant isolation is the highest-blast property in the system.

---

### Finding 1: Per-module integration knowledge is fanned across three packages, with two wiring mechanisms coexisting and the declared migration unscheduled

- **Rank rationale (blast radius × likelihood):** Every module addition and every module-option change pays a 5–9 file coordination tax across `quickscale_cli` + `quickscale_core` + the module — likelihood ≈ 1 (it is the product's main axis of growth), blast = the three highest-churn files in the repo.
- **Horizon:** now — this is the tax on all current work; the teams module will pay it in full.
- **Confidence:** High. Verified directly by symbol listings of all files cited; the two-mechanism state is documented in `decisions.md` itself.
- **Context dependence:** wrong-regardless — for a product whose unit of growth is "add a module," per-module knowledge belongs in the module.
- **Problem:** Module wiring is a platform-side, hand-coded concern: each module's defaults, normalization, validation, derivation schema, CLI prompts, apply hooks, and env-example rendering are separate hand-written functions in central files, while the declared replacement (manifest-driven derivation, piloted on analytics in SA5.1) covers 1 of 12 modules and its continuation is on no roadmap.
- **Evidence:**
  - `quickscale_core/src/quickscale_core/contracts/resolvers.py` (1,781 lines) — per-module quintuples `default_/normalize_/resolve_/validate_*` plus hand-built `_build_<module>_derivation_schema()` for all 12 modules (e.g. notifications' schema alone is `resolvers.py:894–1104`).
  - `quickscale_core/src/quickscale_core/contracts/module_options.py` (1,036 lines) — per-module option constants.
  - `quickscale_cli/src/quickscale_cli/commands/module_config.py` (2,098 lines) — per-module `get_default_/configure_/apply_<module>_configuration` triads (auth :283, blog :587, listings :660, crm :718, forms :832, storage :934, backups :1260, notifications :1444, analytics :1618, billing :1745, social :1855, orgs :1974).
  - `quickscale_cli/src/quickscale_cli/commands/apply_command.py:1134–1509` — module-specific logic inside the apply orchestrator: `_render_notifications_env_example_block`, `_sync_analytics_env_example`, `_render_billing_env_example_block`, `_ensure_backups_gitignore_rules`.
  - `quickscale_core/src/quickscale_core/manifest/entry_point.py` (1,460 lines) — split mechanism: core-inline adapters for analytics/blog/listings/forms/backups/notifications/auth (`MANIFEST_ADAPTER_REGISTRY` assignments at :351, :423, :482, :553, :690, :952, …) vs module-owned managed adapters only for billing/crm/social (`MANAGED_ADAPTER_ORIGINS` :360, :491). `manifest/social_manifest.py` (514 lines) is an entire module-specific renderer file living in core.
  - Migration state (updated 2026-07-04): `contracts/imperative_inventory.py` — `ANALYTICS_MANIFEST = []` and `LISTINGS_MANIFEST = []` (2 of 12 modules now fully migrated; listings landed via SA6.2, 2026-07-04) while the remaining 10 modules hold populated freeze lists; `decisions.md:715` — "Later phases will add loader wiring, runtime derivation execution, and progressive contract-file deletion — one module at a time." The migration is proceeding (SA6.1/SA6.2 landed the loader + first post-pilot module) but has no scheduled next module on the open roadmap.
- **Why it compounds:** Adding one module today means coordinated edits to `module.yml`, `module_options.py`, `resolvers.py` (≈5 functions), `entry_point.py` (adapter or origin registration), `module_config.py` (3 functions), possibly `apply_command.py` (env-example/gitignore hooks), `imperative_inventory.py`, plus theme templates and docs — the checklist in `decisions.md:816–831` institutionalizes this as process. Meanwhile every new option lands on whichever of the two mechanisms its module happens to be on, deepening the split the longer it persists. Two mechanisms also means every engine improvement (validation errors, drift detection) must be built twice or diverge.
- **Correct shape:** All knowledge specific to module X lives in module X's package (manifest + module-owned adapter); central code contains only the generic engine — the invariant is "adding a module touches zero central files that enumerate modules."
- **Trigger for urgency:** The teams module — the next planned module — will either be built on the legacy path (adding a 12th imperative wiring set under a freeze meant to prevent exactly that) or force the derivation engine to be finished under feature pressure.
- **Compounding factor:** All 11 unmigrated modules, the freeze inventory (which must shrink module-by-module as the migration proceeds), and the SA5.2 guardrail test (`quickscale_core/tests/test_imperative_inventory.py`) which codifies today's split as the frozen baseline.
- **Detection signal:** In git history, any module-option PR touching ≥4 central files (already observable across the v0.8x series). Instrument: track "files changed per module-scoped PR" — it should trend toward 1–2.
- **Strongest counter-argument (steelman):** This is a known, deliberately staged migration: the pilot shipped, the freeze prevents regression, and a solo maintainer amortizes migration cost against feature work rationally. That holds *if* the migration is actually scheduled — but the roadmap is empty and the next module will arrive before the engine does. Choose not to fix only if no new modules or options are expected for several releases.
- **Alternative solutions:**
  1. **Finish the declared derivation migration, landing adapters module-side** — extend `module.yml` with the deferred `derivation:` section + YAML loader, migrate one module per release via the existing `MANAGED_ADAPTER_ORIGINS` mechanism, deleting its `resolvers.py`/`module_config.py`/`entry_point.py` code as it moves. Effort: medium per module, spread; reversible per module; removes ~all of the tax.
  2. **Consolidate without migrating** — keep imperative wiring but collapse each module's scattered functions into one `contracts/modules/<name>.py` implementing a small protocol. Effort: low; bounds fan-out to one central file per module but keeps knowledge platform-side and keeps two mechanisms.
  3. **Freeze the surface** — declare the current 12 modules the permanent set and accept the tax for options only. Effort: zero; contradicts the teams roadmap, so not credible.
- **Preferred option + why:** (1) — it is the architecture the project already chose and partially built; the managed-adapter vehicle exists and is proven on billing/crm/social; the freeze guardrail was explicitly designed to hold the line while it happens. (2) is a fallback if YAML derivation proves too rigid for gnarly modules (notifications, backups).
- **Migration path:** Put the next derivation slice on the roadmap now — ship the `module.yml` `derivation:` loader and migrate one small module (listings or blog) end-to-end, deleting its imperative entries from the freeze inventory.

---

**Lenses scanned with no qualifying finding:** consistency/failure model of apply itself (advisory lock, saga ledger, atomic state writes — sound), CLI concurrency, DR engine boundary (post-F5.3 typed adapter is a reasonable shape), security architecture beyond tenancy (ORM parameterization, env-var-name-only credential policy), testing architecture (Postgres-only policy + isolation conformance gates are structurally enforced), build/supply chain (Poetry locks, split-branch automation). Watch-items, not findings: dangling doc refs (`decisions.md:1145` → deleted `findings.md §Finding-8`/`roadmap §AF8`; stale `AVAILABLE_MODULES` checklist step) — feed them to the SA3.2 doc-consistency gate.

---

## Module-by-module autopsy — 2026-07-02

Same decision rules as the repo-level autopsy, applied per module in `quickscale_modules/`, in blast-radius order. Cross-module structural issues (Findings 2–4, now closed — see CHANGELOG.md) are **not repeated** here; this pass looks *inside* each module. Two findings qualified at the time of this autopsy (Module Finding 2, billing webhook idempotency, has since closed — remediated by SA12.1, see CHANGELOG.md); everything else gets an explicit verdict. Reading depth: orgs/billing/blog/crm read deeply (models, services, views, migrations, RLS mechanics); forms/listings/social/auth/notifications medium; backups/storage/analytics sampled (their platform-boundary risk was covered repo-level); teams is an empty placeholder — skipped.

### Per-module verdicts (2026-07-02, superseded)

Module Finding 1 (request→tenant-context boundary) is closed — see closure note above. The remaining per-module watch items from this pass that were not part of that finding: **orgs** — `views.py` (1,271 lines) fuses HTML views, org-admin JSON API, and invitation flows, approaching the fusion threshold; `_is_org_management_path` (`middleware.py:225–263`) is a hand-maintained path classifier (fails closed, so a miss is friction not a leak). **billing** — Module Finding 2 (webhook idempotency) closed 2026-07-02 via SA12.1. **auth** — swap-in `User` model is a one-way door, handled by the CLI's late-adoption gate. **notifications** — watch item: when teams ships, invitation/notification bodies become tenant-adjacent PII in unscoped tables; revisit the registry's `EXCLUDED_REVIEWED` reasons then. **backups** — structural exposure (deep `quickscale_core.dr_engine` imports, open-ended core pin) is repo-level Finding 4, closed 2026-07-03. **teams** — still an empty placeholder; it will be the first module built after the freeze and should land on the derivation-schema path (Finding 1) and the now-closed shared request-context seam (Module Finding 1) from day one.

---

## Autopsy — 2026-07-03 (fresh full pass)

> Run mode: fresh module-by-module analysis per operator instruction ("do not continue previous reviews"). Prior sections above are retained verbatim so roadmap anchors stay valid; this section does not reconcile prior finding IDs except where an open SA task directly overlaps a new finding (noted inline). Naming: new findings use stable kebab-case IDs to avoid collision with the numbered 2026-07-02 findings.

### Orientation (2026-07-03)

QuickScale is a solo-maintained (Experto-AI/Victor Rocco) Python 3.13/3.14 + Poetry monorepo, v0.86.0 line, that generates user-owned Django 6 SaaS projects: `quickscale_cli` (plan/apply/dr commands), `quickscale_core` (Jinja2 generator, plan/apply engine with 16-step recovery ledger, manifest/contracts stack, DR engine), and 13 embeddable Django modules under `quickscale_modules/` distributed as git subtrees from split branches (teams = empty placeholder). Persistence is PostgreSQL-only; the flagship architectural commitment (v0.86.0) is shared-schema multi-tenancy enforced twice — ContextVar-driven `TenantManager` scoping plus FORCE RLS under a `NOBYPASSRLS` runtime role with an AF9 execute-wrapper priming the `app.current_org_id` GUC. Deployment target is single-service Railway + Docker Compose dev. Governance discipline is unusually high (SSOT doc hierarchy, import-linter gates, 90% coverage CI) and a large remediation program (SA1–SA12) closed the 2026-07-02 findings, including SA10.2 and SA11.5–11.7 (all complete as of 2026-07-03 — see CHANGELOG.md). Near-term growth: teams module, billing SPA entry-point restoration (post-D1), more modules onto the tenant registry. **Scope note:** I read the orgs tenancy stack, generated-project templates (settings/db/start/CI/urls), billing ledger+webhook path, apply engine, and manifest/contracts machinery in full; sampled admin/views/migrations of crm/blog/social/listings/auth/backups/notifications and CLI command structure; skipped React theme internals, `dr_engine/orchestration.py` body, railway utils, and devtools. Severity judgments assume the production saas posture (restricted role, FORCE RLS) that the project itself declares authoritative.

### Summary table

| ID | Title | Horizon | Confidence | Size | Problem (one line) |
|----|-------|---------|------------|------|--------------------|
| `operator-read-path-undefined` | Elevated/operator reads: Python bypass and DB RLS contradict each other | now | High (structure) / Medium (exact prod symptom) | M | `all_objects` admin querysets promise cross-tenant visibility that FORCE RLS deliberately denies to the runtime role; the documented `operator_access()` contract does not exist in code |

`registry-universe-mismatch`, `per-module-knowledge-fanout`, and `org-context-api-accretion` (all closed 2026-07-04) — see closure note above.

### Finding 1: Elevated/operator reads are structurally undefined — the Python bypass and the DB backstop disagree

- **ID:** `operator-read-path-undefined`
- **Rank rationale:** Blast = the entire admin/operator surface of every generated saas project (8+ ModelAdmins across crm/blog/forms/listings/billing, plus the backups admin-restore operational surface); likelihood = fires the first time an operator opens `/admin/` in production — no special trigger needed.
- **Horizon:** now.
- **Confidence:** High that the contradiction is structural (all seams read directly). Medium on the precise production symptom (empty changelists) — static reasoning; confirm by generating a saas project, serving under `RUNTIME_DATABASE_URL`, and opening a CRM admin changelist.
- **Context dependence:** wrong-regardless — it contradicts the project's own hardened posture.
- **Problem:** "Read across tenants as an operator" was never designed as a seam: the Python layer offers `all_objects` (bypasses `TenantManager` only), the DB layer deliberately offers **no** bypass to the runtime role (BYPASSRLS is boot-blocked), and the documented contract (`operator_access(reason=...)`, decisions.md §multitenant "permanent rules") exists in no code — so each module improvised.
- **Evidence:**
  - `quickscale_modules/crm/src/quickscale_modules_crm/admin.py:258-260` (and 7 sibling admins): `return Tag.all_objects.all()` under the comment "Operator path: use all_objects for cross-tenant visibility"; same idiom in `blog/admin.py:226-242`.
  - `orgs/middleware.py:45`: `/admin/` is in `EXEMPT_PATH_PREFIXES` → no `request.org`, ContextVar stays `None`.
  - `orgs/current_org.py:472-476`: the AF9 wrapper passes through **without priming** when the ContextVar is `None` → GUC unset → policy `NULLIF(current_setting('app.current_org_id', true), '')::uuid = organization_id` (tenancy.py:414-421) matches zero rows for the NOBYPASSRLS role.
  - `orgs/apps.py:52-83`: boot guard forbids BYPASSRLS at runtime (correct), so there is no legitimate role under which the admin idiom works in production.
  - Divergent sibling idiom: social's admin implements its own org resolution (POST/GET/session) + DB context scoping (`social/tests/test_admin.py:211-469`) — it works under RLS, one org at a time. Two modules, two contradictory answers to the same question.
  - Test blindness: `orgs/tests/settings.py:14-18` defaults to `USER=postgres` (superuser ⇒ RLS inert) with `QUICKSCALE_ALLOW_BYPASSRLS=1` — the bare-`all_objects` belief passes the default suite and can only fail in production. (Dedicated `test_rls_boundary.py` files do create a restricted role, but admin tests don't run under it except social's.)
- **Why it compounds:** The Module Implementation Checklist requires an `admin.py` per module, so every new module re-picks an idiom; the wrong idiom is invisible to the default test posture; every new operator surface (support tooling, exports, dashboards) re-fights the same undefined seam. This exact root already burned the project once — Module Finding 1's "public pages render empty under production posture" was the anonymous-read instance; admin is the operator-read instance of the same class.
- **Correct shape:** One orgs-owned elevated-read contract whose semantics are identical in both enforcement layers — any cross-tenant or view-as-tenant read goes through a single API that the RLS policies recognize, and that restricted-role tests exercise. `all_objects` alone must never be presented as "cross-tenant visibility."
- **Trigger for urgency:** First real operator/admin use of a production saas deployment (content moderation, billing support, backups restore triage).
- **Compounding factor:** 8+ existing ModelAdmins; the backups guarded-restore admin contract; VIEW-AS (app-only today); the superuser-default test posture; `check_tenant_isolation`'s catalog checks (they verify policies exist, not that operator surfaces behave).
- **Detection signal:** Operator reports of empty admin changelists on tenant tables in production; instrument: count admin-path queries on ENROLLED tables returning 0 rows under the runtime role.
- **Steelman:** "Admin is a dev-only surface; production operators use VIEW-AS inside the app." — Rejected: backups' admin restore is an explicitly documented operational surface, `start.sh` provisions a production superuser, and VIEW-AS cannot reach admin because `/admin/` bypasses the middleware that reads the debug session key. If dev-only-admin *were* the intent, that itself needs deciding once and enforcing (strip module admins in production settings), which is the same finding.
- **Alternative solutions:**
  1. **Per-org scoped admin (VIEW-AS through admin):** an orgs-owned `TenantModelAdmin` base (or AdminSite) that resolves the VIEW-AS/session org and wraps changelist/change views in `org_scope`. Keeps RLS untouched; admin becomes one-org-at-a-time (social's pattern, generalized). Effort M, low risk, reversible; does not give true cross-tenant lists.
  2. **First-class operator predicate in RLS:** add `OR NULLIF(current_setting('app.operator_access', true), '') = 'on'` to the policy template and implement the documented `operator_access(reason=...)` context manager (audited, superuser-gated) as the only setter. True cross-tenant reads; policy migration across 21 tables is mechanical because the SQL template is already centralized (`apply_force_rls`). Effort M–L; slightly widens in-process DB trust, but no further than the existing `app.current_org_id` GUC.
  3. **Second DB role for operator paths** with permissive policies and per-path connection routing. Strongest separation, highest complexity (dual connections, routing middleware); disproportionate at current scale.
- **Preferred option + why:** (1) as the default admin experience, plus a minimal (2) for the few genuinely cross-tenant operator needs — this matches the product's own VIEW-AS philosophy, finally implements the documented contract instead of deleting it, and keeps the RLS story honest. Additionally flip the module-test default DB role to NOBYPASSRLS (superuser opt-in per test) so this bug class becomes visible to the suite — that posture change is what prevents recurrence.
- **Remediation size:** M.
- **Migration path:** Build `TenantModelAdmin` in orgs (org-resolving, `org_scope`-wrapping) and port CRM's eight admins to it; delete the "cross-tenant visibility" comments as you go.

### Fix order and interactions

Finding 3 (`org-context-api-accretion`) is closed (2026-07-04, see closure note above) — it was completed as the prerequisite step for Finding 1: the operator/admin contract is now built on the consolidated `org_scope` seam. `registry-universe-mismatch` and `per-module-knowledge-fanout` are also closed and no longer part of the ordering. SA11.6/SA11.7 and SA10.2 are complete (see CHANGELOG.md) — they were partial, already-landed steps toward Finding 3's (now-complete) consolidation and Finding 5's contract-vintage detection respectively.

### Sound load-bearing decisions (protect these during remediation)

- **Dual-layer tenancy enforcement done properly:** fail-closed `TenantManager` (`.none()` on missing org, `managers.py:38-48`) + FORCE RLS with NULLIF-guarded policies (`tenancy.py:414-421`) + the AF9 execute-wrapper priming the GUC in-transaction with atomic-identity memoization (`current_org.py:377-527`). Defense-in-depth here is real, not aspirational.
- **The privileged-role failure mode is structurally unreachable:** always-on BYPASSRLS boot guard with two narrow exemptions (`apps.py:52-133`) + production settings that refuse to serve without `RUNTIME_DATABASE_URL` (`production.py` runtime-role block) + the generated `db/init.sql` provisioning a NOBYPASSRLS role.
- **Plan/apply as a checkpointed saga:** single authoritative `state.yml`, advisory lock, and a 16-step recovery ledger with atomic writes and resume gating (`core/apply/executor.py`, `core/apply/ledger.py`) — the CLI's hardest consistency problem is engineered, not hoped away. (decisions.md still calls this "future Phase 12 work" — update the doc, keep the code.)
- **Managed-wiring isolation seam:** machine-owned `settings/modules.py` + `urls_modules.py` ("DO NOT EDIT") consumed by user-owned `base.py`/`urls.py` — module updates can rewire projects without rewriting user code.
- **Money-ledger idempotency:** event-keyed dedup with a DB-constraint backstop, row-locked `F()` balance updates, and a `balance_after` audit column (`billing/services.py:803-922`), plus the transport-level `WebhookEvent` gate.
- **Self-enforcing boundaries:** the module→core import linter restricting modules to the `quickscale_core.runtime` facade with per-module scoped exceptions (SA9.6, `scripts/check_module_core_imports.py`) — governance by gate, not by convention. Reuse this pattern for Findings 1–3.

### Watchlist

- `WebhookEvent.processed` doesn't serialize concurrent duplicate deliveries (lock released before processing, `billing/services.py:967-975`); domain-level dedup carries it today · promotes when a non-idempotent event handler is added.
- Trigger-based child-parent equality infra (`tenancy.py:523-674`) retained beside its composite-FK replacement with one caller · promotes if a new child table is authored against the old API.
- `_is_migrate_command()` detects the migration exemption by `sys.argv` sniffing (`orgs/apps.py:45-49`) · promotes when any non-`manage.py` entry point (programmatic Django, custom scripts) needs to migrate.
- `apply_command.py` (3648 lines / 102 functions, top churn) keeps absorbing per-module and per-step logic despite the core executor seam existing · promotes when a new apply feature can't be expressed as a step callback.
- `EXEMPT_PATH_PREFIXES` hardcoded in orgs middleware (`middleware.py:45`) · promotes when a generated project first needs a project-specific exempt path (currently requires editing embedded module source).

### Red flags (out of scope — fix now)

- `QUICKSCALE_MODE` is read with a permissive default (`getattr(settings, "QUICKSCALE_MODE", "solo")`, `middleware.py:268`): a saas deployment that loses the setting silently flips to solo-mode tenancy (personal orgs auto-created, org data invisible) — contradicts the fail-hard principle; make it a required setting when orgs is installed.
- decisions.md cites `operator_access(reason=...)` as a permanent isolation rule, but the symbol exists nowhere in code — a security-relevant contract that is documentation-only (see Finding 1).
- SSOT drift instances: decisions.md calls the shipped apply recovery ledger "future Phase 12 work" and the shipped derivation YAML loader "deferred" (both already shipped and SA11.5's DRF baseline is complete and no longer on the roadmap — decisions.md hasn't caught up). Cheap doc fixes; they matter because decisions.md is the declared tie-breaker.

Lenses scanned with no qualifying finding: data/state-model integrity (UUID/timestamps/N+1), consistency & failure models beyond items above, observability (correlation-ID + JSON logging is structural in the templates), API contract stability (covered by open SA10.2), build/release/supply chain (Poetry, lockfiles, split-branch automation), performance/scalability, frontend state architecture (sampled only).
