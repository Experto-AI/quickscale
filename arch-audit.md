# Structural Autopsy: QuickScale

> This file is regenerated on each autopsy run to state **present reality for planning**: the
> current orientation, the open findings in full detail, and a curated watchlist. Closed findings
> exist only as dated lines in the **Reconciliation log** at the bottom (closeout detail lives in
> [CHANGELOG.md](CHANGELOG.md)); version control preserves prior full text. Finding IDs are stable
> across runs.

---

## Autopsy — 2026-07-04 (re-run)

### Orientation (2026-07-04)

QuickScale is a solo-maintained (Experto-AI/Victor Rocco) Python 3.13/3.14 + Poetry monorepo,
v0.86.0 line, that generates user-owned Django 6 SaaS projects: `quickscale_cli` (Click:
plan/apply/dr/deploy), `quickscale_core` (Jinja2 generator, plan/apply engine with a 16-step
recovery ledger, manifest/contracts/derivation stack, DR engine), and 13 shipped Django modules
under `quickscale_modules/` distributed as git subtrees (teams = still an empty placeholder).
Generated apps: Django 6 + PostgreSQL 18, single-service Railway; tenancy is enforced twice —
ContextVar-driven fail-closed `TenantManager` plus FORCE RLS under a NOBYPASSRLS runtime role with
the AF9 execute-wrapper priming `app.current_org_id` (`current_org.py:423–479`, re-verified).
**Since the 2026-07-03 pass, a large remediation wave merged to `v87`:** `org-context-api-accretion`
(SA13, closed — `org_scope`/`PublicSystemOrgReadMixin` consolidation with a hard-fail AST gate),
`registry-universe-mismatch` (SA15, closed — marker-based default-deny registry),
`per-module-knowledge-fanout` (SA16, closed — manifest-sync CI gate + shrink-only imperative
freeze), the entire fail-hard program (SA17.1–17.6, SA18.1–18.11, closed — TA1–TA15 remediated),
and SA14.1 (the `TenantModelAdmin` base) landed for the one finding still open. Governance is now
gate-enforced in CI (`.github/workflows/ci.yml`): core-compat (:120), module→core import linter
(:148), manifest-sync (:176), org-context AST gate (:204), and the isolation-conformance suite
(:325+). **Growth direction:** the teams module is the next build (design locked in
`docs/technical/organizations.md`; Option C — every child table carries `organization_id`), plus
the SA19–SA26 tech-sweep remediation batch just opened in `roadmap.md`. **Depth this pass:**
re-verified every open-finding and watchlist seam (all five module admins, orgs test posture,
`tenancy.py` API surface, billing webhook dedup path, `apply --force` regeneration flow, middleware
exemptions, `QUICKSCALE_MODE` callsites); read fully — `contracts/imperative_inventory.py`,
`manifest/entry_point.py` adapter registry and post-hooks, `orgs/admin.py` (`TenantModelAdmin`),
the sync gate and CI wiring, `roadmap.md`; sampled — `dr_engine/orchestration.py` structure (3,013
lines, function map only — first time any pass has looked inside); skipped — theme internals,
module domain logic, devtools. Severity floor unchanged: CLI is a single-process local tool;
generated apps are single-service WSGI; tenant isolation is the highest-blast property.

The fresh-lens sweep produced **no new qualifying finding** — the expected result immediately after
a program that closed eight structural findings. The current state is one still-open finding
(mid-remediation) plus a re-curated watchlist aimed at the teams build.

### Summary table

| ID | Title | Horizon | Confidence | Size | Problem (one line) |
|----|-------|---------|------------|------|--------------------|
| `operator-read-path-undefined` | Elevated/operator reads: Python bypass and DB RLS contradict each other | now | High | M | `all_objects` admin querysets promise cross-tenant visibility that FORCE RLS deliberately denies to the runtime role; remediation (SA14) is 1/6 landed |

### Finding 1: Elevated/operator reads are structurally undefined — the Python bypass and the DB backstop disagree

- **ID:** `operator-read-path-undefined` *(still-open; opened 2026-07-03; remediation SA14 in flight — SA14.1 complete, SA14.2–SA14.6 open)*
- **Rank rationale (blast radius × likelihood):** Blast = the entire admin/operator surface of
  every generated saas project (8+ ModelAdmins across crm/blog/forms/listings/billing, plus the
  backups admin-restore operational surface); likelihood = fires the first time an operator opens
  `/admin/` in production — no special trigger needed.
- **Horizon & trigger:** now — first real operator/admin use of a production saas deployment
  (content moderation, billing support, backups restore triage).
- **Confidence:** High that the contradiction is structural (all seams re-read 2026-07-04). Medium
  on the precise production symptom (empty changelists) — static reasoning; confirm by generating a
  saas project, serving under `RUNTIME_DATABASE_URL`, and opening a CRM admin changelist.
- **Context dependence:** wrong-regardless — it contradicts the project's own hardened posture.
- **Problem:** "Read across tenants as an operator" was never designed as a seam: the Python layer
  offers `all_objects` (bypasses `TenantManager` only), the DB layer deliberately offers **no**
  bypass to the runtime role (BYPASSRLS is boot-blocked), and the documented contract
  (`operator_access(reason=...)`, decisions.md §multitenant "permanent rules") exists in no code —
  so each module improvised.
- **Evidence (re-verified 2026-07-04):**
  - The bare-`all_objects` "cross-tenant visibility" idiom persists in **all five** module admins:
    `crm/admin.py` (:259–260, :280–281, :341–342, :376–377 + related-field bypasses :164–176),
    `blog/admin.py` (:227–242, :272–273, :334–377), `forms/admin.py` (10 refs),
    `billing/admin.py` (3 refs), `listings/admin.py` (2 refs).
  - `orgs/middleware.py:45`: `/admin/` in `EXEMPT_PATH_PREFIXES` → no `request.org`, ContextVar
    stays `None`; the AF9 wrapper then passes through **without priming**
    (`current_org.py:473–479`) → GUC unset → the NULLIF-guarded policies match zero rows for the
    NOBYPASSRLS role. `orgs/apps.py` boot guard (T1.18/SA2.1) still forbids BYPASSRLS at runtime,
    so no legitimate production role exists under which the idiom works.
  - `operator_access` still exists nowhere in code (grep across orgs + core, 2026-07-04).
  - Test blindness unchanged: `orgs/tests/settings.py` sets
    `os.environ.setdefault("QUICKSCALE_ALLOW_BYPASSRLS", "1")` with `USER=postgres` default — the
    superuser posture that makes the wrong idiom pass CI. Flipping this is SA14.4, correctly
    sequenced after the admin ports.
  - **Remediation landed so far:** SA14.1 built the orgs-owned `TenantModelAdmin` base
    (`orgs/admin.py:158–413`) — org resolution chain (VIEW-AS debug session → explicit request
    selection → session key), `org_scope`-wrapped views, **fail-closed empty queryset when no org
    resolves**. This generalizes the pattern social's admin already proved under RLS and matches
    this finding's preferred option 1. No module has been ported yet.
- **Why it compounds:** The Module Implementation Checklist requires an `admin.py` per module, so
  every new module re-picks an idiom; the wrong idiom is invisible to the default test posture
  until SA14.4 lands; every new operator surface (support tooling, exports, dashboards) re-fights
  the same undefined seam. The teams module — the next build — will add its own admin and must not
  land on the broken idiom. This root already burned the project once (Module Finding 1's
  "public pages render empty under production posture" was the anonymous-read instance).
- **Detection signal:** Operator reports of empty admin changelists on tenant tables in
  production; instrument: count admin-path queries on ENROLLED tables returning 0 rows under the
  runtime role.
- **Steelman:** "Admin is a dev-only surface; production operators use VIEW-AS inside the app." —
  Rejected: backups' admin restore is an explicitly documented operational surface, `start.sh`
  provisions a production superuser, and VIEW-AS cannot reach admin because `/admin/` bypasses the
  middleware that reads the debug session key. If dev-only-admin *were* the intent, that itself
  needs deciding once and enforcing (strip module admins in production settings), which is the
  same finding.
- **Correct shape:** One orgs-owned elevated-read contract whose semantics are identical in both
  enforcement layers — any cross-tenant or view-as-tenant read goes through a single API that the
  RLS policies recognize, and that restricted-role tests exercise. `all_objects` alone must never
  be presented as "cross-tenant visibility."
- **Options:**
  1. **Per-org scoped admin (VIEW-AS through admin):** `TenantModelAdmin` (now built) resolving
     the active org and wrapping changelist/change views in `org_scope`. Keeps RLS untouched;
     admin is one-org-at-a-time. Effort M, low risk, reversible; no true cross-tenant lists.
  2. **First-class operator predicate in RLS:** add
     `OR NULLIF(current_setting('app.operator_access', true), '') = 'on'` to the policy template
     and implement the documented `operator_access(reason=...)` (audited, superuser-gated) as the
     only setter. True cross-tenant reads; mechanical policy migration because the SQL template is
     centralized (`apply_force_rls`). Effort M–L.
  3. **Second DB role for operator paths** with permissive policies and per-path connection
     routing. Strongest separation; disproportionate at current scale.
- **Recommendation:** (1) as the default admin experience plus a minimal (2) for genuinely
  cross-tenant operator needs, **and** the SA14.4 test-posture flip (restricted role by default,
  superuser opt-in) — the posture change is what prevents recurrence. This is exactly the SA14.2–
  SA14.6 plan already in `roadmap.md`; the plan's internal ordering (ports before posture flip) is
  correct. **One scope gap:** SA14.6 names only `middleware.py:268`, but the permissive
  `getattr(settings, "QUICKSCALE_MODE", "solo")` read also lives at `orgs/adapters.py:60`,
  `orgs/adapters.py:81`, and `orgs/views.py:63` — all four callsites must go fail-hard or the mode
  fail-open survives the fix. · **Size:** M · **First step (updated):** port CRM's admins to
  `TenantModelAdmin` (SA14.2) — the base now exists.

### Fix order and interactions

One open finding; its internal ordering is already encoded in the roadmap (SA14.2/SA14.3 ports →
SA14.4 posture flip; SA14.5 and SA14.6 independent) and is correct — the posture flip must not land
before the ports or it breaks the suites it protects. Add the `adapters.py`/`views.py`
`QUICKSCALE_MODE` callsites to SA14.6's scope. The SA19–SA26 tech-sweep batch is independent of
SA14 except that SA23 (debug-view redirect) touches the same orgs surface — trivial to sequence.

### Sound load-bearing decisions (protect these during remediation)

- **Dual-layer tenancy enforcement done properly:** fail-closed `TenantManager` (`.none()` on
  missing org) + FORCE RLS with NULLIF-guarded policies + the AF9 execute-wrapper priming the GUC
  in-transaction (`current_org.py:423–479`, re-verified this pass after the SA13 reshuffle).
- **The privileged-role failure mode is structurally unreachable:** always-on BYPASSRLS boot guard
  with two narrow, documented exemptions (`orgs/apps.py`, T1.18/SA2.1) + production settings that
  refuse to serve without the runtime role + generated `db/init.sql` provisioning NOBYPASSRLS.
- **Governance by gate, now systemic (not aspirational):** module→core import linter, org-context
  AST hard-fail gate, manifest-sync gate with orphan detection, the shrink-only imperative freeze
  (`AUTHORIZED_IMPERATIVE_MODULES` + `test_imperative_inventory.py`), and default-deny tenant
  classification (`get_unclassified_concrete_models` + isolation-conformance CI job) — all wired
  as blocking CI jobs (`ci.yml:120,148,176,204,325+`). New modules — teams first — are forced onto
  the declarative manifest path and into tenant classification by construction.
- **Plan/apply as a checkpointed saga:** single authoritative `state.yml`, advisory lock, 16-step
  recovery ledger with atomic writes and resume gating (`ApplyExecutor` invoked at
  `apply_command.py:3088`). (The regeneration flow that sits *outside* it is a watchlist item.)
- **`TenantModelAdmin` base shape (SA14.1):** fail-closed, org-resolving, `org_scope`-wrapped —
  the right skeleton for Finding 1's preferred option; port modules onto it rather than inventing
  per-module variants.

### Watchlist

- **Billing webhook concurrent-duplicate window** — the Phase-3 restructure deliberately releases
  the dedup lock before processing (`billing/services.py` `select_for_update` → check → exit
  atomic → process outside), so two concurrent deliveries of one event can both process; safety
  rests entirely on domain idempotency (event-keyed ledger dedup + DB constraints), and no handler
  currently sends mail/notifications (verified) · promotes the moment any non-idempotent side
  effect lands in a handler.
- **Dual child-table tenancy APIs** — trigger-based equality infra
  (`tenancy.py:632` `install_equality_trigger_function`, `:676/:714` enable/disable) retained
  beside its composite-FK replacement (`:856` `add_composite_child_fk`) · flat cost today · the
  teams module is about to author the next batch of Option C child tables — if any lands on the
  trigger API, promote; cheaper: delete the old API before teams starts.
- **Apply regeneration flow runs outside the recovery ledger** —
  `_generate_with_existing_config` (`apply_command.py`, `--force` path) wipes and swaps project
  content with no ledger step, in the repo's top-churn file (3,658 lines; 23 commits/30d) · SA22
  fixes the wipe-before-generate ordering defect (TA20) · promotes if post-SA22 apply features
  keep landing as unledgered CLI-side mutations instead of executor steps.
- **`orgs/views.py` fusion** — 1,271 lines fusing HTML views, org-admin JSON API, and invitation
  flows; unchanged since 2026-07-02 · promotes when teams begins extending org-facing surfaces:
  teams views must land in the teams module, not accrete here.
- **Grandfathered option defaults are multi-sourced with no scheduled driver** — one default lives
  in up to four stations (module.yml source + synced core snapshot, `resolvers.py` `DEFAULT_*`,
  `entry_point.py` post-hook coercion fallbacks — e.g. `BLOG_ENABLE_RSS`); the freeze guardrail
  stops growth and new modules are clean, but the T2.4/T2.5 phases `imperative_inventory.py` names
  as the migration driver appear nowhere in `roadmap.md`/`CHANGELOG.md` · promotes when a
  grandfathered default is changed in one station only, or if T2.4/T2.5 remain unscheduled past
  the teams build.

*(Carried unchanged at low priority, dropped from the printed list: `_is_migrate_command()`
`sys.argv` sniffing in `orgs/apps.py`; hardcoded `EXEMPT_PATH_PREFIXES` in `orgs/middleware.py:45`
— triggers as previously stated.)*

### Questions that would change the ranking

- Are the T2.4/T2.5 declarative-migration phases deliberately abandoned (accepted) or just
  unscheduled? Answer promotes or kills the multi-sourced-defaults watchlist item.
- Will teams' UI surfaces live in the teams module or extend `orgs/views.py`? Answer decides
  whether the views-fusion watchlist item becomes a finding at teams kickoff.
- Is production `/admin/` an intended operator surface (the SA14 plan implies yes)? If it is ever
  decided dev-only instead, `operator-read-path-undefined`'s remaining work collapses to
  "strip module admins in production settings" — same finding, much smaller fix.

### Red flags (out of scope — fix now)

- `entry_point.py` post-hooks still carry permissive "legacy coercion" defaults — blog
  (`:382–385`: `settings.get("BLOG_ENABLE_RSS", True)`, `"5/hour"` fallback), listings
  (`LISTINGS_PER_PAGE` → 12), forms (five defaults incl. `FORMS_SPAM_PROTECTION` → True) — the
  same fail-open class SA18.2 purged from the analytics hook. Candidate tech-audit finding; the
  module-side SA17 guards mask it only for settings they assert.
- `QUICKSCALE_MODE` fail-open scope gap: SA14.6/TA19 name `middleware.py:268` (+`views.py:63`),
  but `orgs/adapters.py:60` and `:81` carry the same permissive default — fix all four or the
  silent solo-mode flip survives.
- CHANGELOG links to the dropped arch-audit heading
  `#finding-4-per-module-contract-knowledge-…` — dangling historical anchor; cheap fix, feed to
  the doc-consistency gate.

Lenses scanned with no qualifying finding this pass: data/state integrity, module/layer cohesion
(`dr_engine/orchestration.py` sampled — 3,013 lines behind a typed adapter with deliberate
failure-mode engineering; not promoted), consistency/failure models (webhook → watchlist), trust
boundaries beyond Finding 1 (SA19–SA26 track the defect-class items), trajectory (option pipeline
steelmanned by freeze + gates), observability, API contract stability (contract-vintage landed),
testing architecture (posture flip pending as SA14.4), design conflicts, concurrency, security
architecture, dependency/config, build/supply chain, performance.

---

## Autopsy — 2026-07-03 (fresh full pass)

> Superseded by the 2026-07-04 re-run above, which re-verified all of this pass's evidence. Its
> four findings are reconciled in the log below: three closed, one still open (Finding 1, retained
> above in full). This stub heading is kept so existing links resolve.

---

## Reconciliation log (append-only)

- 2026-07-02 — 2026-06-30 autopsy, Findings 1–5: **resolved** (SA1.1–SA5.2; closeout in CHANGELOG.md).
- 2026-07-02 — Module Finding 2 (billing webhook idempotency): **resolved** (SA12.1).
- 2026-07-03 — 2026-07-02 Finding 2 (orgs god-module): **resolved** (SA7.2–SA7.4); Finding 3 (dual
  active-org truth): **resolved** (product decision D1); Finding 4 (core-as-runtime-API):
  **resolved** (SA9.1–SA9.6); Finding 5 (module↔generated-project contract drift): **resolved**
  (SA10.1/SA10.2 contract-vintage mechanism); Module Finding 1 (request→tenant-context boundary):
  **resolved** (SA11.1–SA11.7 shared `PublicSystemOrgReadMixin`/DRF baseline).
- 2026-07-04 — `registry-universe-mismatch`: **resolved** (SA15.1–SA15.3);
  `per-module-knowledge-fanout`: **resolved** (SA16.1/SA16.2 + SA6.1/SA6.2 derivation groundwork;
  the remaining grandfathered imperative entries are frozen shrink-only — residual tracked as a
  watchlist item above); `org-context-api-accretion`: **resolved** (SA13.1–SA13.4, its own option
  1 "consolidate + gate": five context primitives privatized behind
  `org_scope`/`PublicSystemOrgReadMixin`, 44 callsites migrated, AST lint gate hard-fail).
- 2026-07-04 (re-run) — `operator-read-path-undefined`: **still-open**; evidence re-verified
  current; SA14.1 (`TenantModelAdmin` base) landed, SA14.2–SA14.6 open; scope gap flagged
  (`adapters.py` `QUICKSCALE_MODE` callsites). Watchlist reconciled: billing-webhook window
  (updated for the Phase-3 restructure), child-table dual API, and `apply_command` growth carried
  forward; `_is_migrate_command` argv-sniffing and `EXEMPT_PATH_PREFIXES` carried unchanged at low
  priority; orgs-views fusion promoted from per-module note to watchlist; new item: grandfathered
  defaults multi-sourcing (T2.4/T2.5 unscheduled). Prior red flags reconciled: `QUICKSCALE_MODE`
  fail-open → tracked (SA14.6/TA19, scope gap noted); `operator_access` documentation-only →
  tracked (SA14.5); 2026-07-03 SSOT-drift instances (Phase-12/ledger/loader staleness, dangling
  `findings.md §Finding-8`/`roadmap §AF8` refs) → **fixed** (verified gone 2026-07-04).
