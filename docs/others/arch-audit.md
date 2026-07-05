# Structural Autopsy: QuickScale

> This file is regenerated on each autopsy run to state **present reality for planning**: the
> current orientation, the open findings in full detail, and a curated watchlist. Closed findings
> exist only as dated lines in the **Reconciliation log** at the bottom (closeout detail lives in
> [CHANGELOG.md](../../CHANGELOG.md)); version control preserves prior full text. Finding IDs are stable
> across runs.

---

## Autopsy — 2026-07-04 (re-run)

> **Update (2026-07-05, roadmap cleanup):** The one open finding this pass identified
> (`operator-read-path-undefined`) is now closed — SA14.2–SA14.6 landed on top of SA14.1 (see
> CHANGELOG.md and the Reconciliation log below). The narrative below is left as the historical
> record of the 2026-07-04 pass; treat "still-open"/"in flight" language in it as superseded.

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

*(No open findings this pass — see Reconciliation log for the closeout of Finding 1.)*

### Fix order and interactions

No open findings. Finding 1 (`operator-read-path-undefined`) closed 2026-07-05 once SA14.2–SA14.6
landed on top of SA14.1 — see Reconciliation log for the full closeout note. The SA19–SA26
tech-sweep batch was independent of SA14 except that SA23 (debug-view redirect) touched the same
orgs surface — sequencing was trivial and both are complete.

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

### Red flags (out of scope — fix now)

- `entry_point.py` post-hooks still carry permissive "legacy coercion" defaults — blog
  (`:382–385`: `settings.get("BLOG_ENABLE_RSS", True)`, `"5/hour"` fallback), listings
  (`LISTINGS_PER_PAGE` → 12), forms (five defaults incl. `FORMS_SPAM_PROTECTION` → True) — the
  same fail-open class SA18.2 purged from the analytics hook. Candidate tech-audit finding; the
  module-side SA17 guards mask it only for settings they assert.
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

## Module-by-module autopsy — 2026-07-04 (deep pass)

> Run mode: deeper per-module pass at operator request, **treating `quickscale_core` and
> `quickscale_cli` as modules**. Same §0 decision rules as the repo-level autopsy; blast-radius
> order (core → orgs → cli → billing → backups → notifications/auth → blog/crm/forms → periphery).
> This pass looks *inside* each module; the open repo-level finding
> (`operator-read-path-undefined`) is not repeated per module.
>
> **Result: zero new qualifying findings.** Every candidate surfaced by this pass was steelmanned
> by an existing gate, test, or scheduled task before it could pass all four §0 gates. That is
> recorded per candidate below — the near-misses are the valuable output of this pass, because
> each one names the gate that currently holds it and the event that would break it.

### Candidates investigated and why they did not qualify

1. **orgs: org-management JSON API is per-view mixin discipline, not deny-by-default.** Eight
   `OrgApi*` endpoints (membership, roles, invitations — `views.py:944–1271`) sit on hand-rolled
   `JsonApiMixin`/`JsonOrganizationAccessMixin` stacks outside the project's fail-closed DRF
   baseline, and the org-management tables are deliberately outside RLS (control-plane
   exclusions, `tenancy.py:238+`), so view-layer checks are the only guard. **Held by:**
   `JsonOrganizationAccessMixin.dispatch` enforces org-role on every current endpoint, and
   `test_views.py` (63 tests) exercises both surfaces via html/json parametrization plus 26
   permission tests. **Breaks if:** a new endpoint lands with a wrong mixin stack and no test —
   watch this when teams adds management endpoints; consider folding the full stack into one
   `OrgApiBaseView` before then (S-size hardening, not urgent).
2. **core/cli: the module-option pipeline spans seven stations.** One option's knowledge can
   touch: `module.yml` (source + synced core snapshot), the YAML derivation loader, the
   `contracts/resolvers.py` per-module switchboard (1,724 lines, ~6 functions × 12 modules —
   crm's derivation rules exist **both** in `module.yml` and re-encoded in
   `_build_crm_derivation_schema()`, `resolvers.py:480–549`), `config_schema.py` per-module
   validators, `entry_point.py` post-hooks, CLI `module_config.py` (2,038 lines of per-module
   interactive prompts + settings-text generation), and the module's `apps.py` guard.
   **Held by:** the shrink-only freeze (`AUTHORIZED_IMPERATIVE_MODULES`), the manifest-sync CI
   gate, wiring-parity tests holding Python and YAML derivation equal, and YAML being
   authoritative for defaults (`manifest.get_defaults()`). New modules (teams) ride the clean
   declarative path. **Breaks if:** the T2.4/T2.5 migration stays unscheduled and a grandfathered
   option's rules change in one station only — this is the existing watchlist item, now with
   sharper evidence.
3. **orgs: static `TENANT_TABLE_REGISTRY` literal retained beside marker derivation.** 49
   hand-written entries in `tenancy.py:119–410` classify *other modules'* models inside orgs,
   and orgs' conformance suite (`test_registry_covers_all_concrete_qs_models`) plus the
   per-table RLS test parametrization key on the literal. **Held by:** the *runtime* default-deny
   check accepts marker-only classification (`is_classified_in_registry`, `tenancy.py:1191` —
   literal OR marker OR m2m-derived), so a teams model with its marker/`TenantManager` is
   self-contained at runtime; the literal is double-entry bookkeeping for the highest-blast
   property, enforced only inside orgs' own test env. **Breaks if:** the double ledger is
   actually intended to retire (the derived-overview docstring calls the literal "the
   hand-maintained alternative") but never does — see Questions.
4. **billing: `services.py` (2,362 lines) fuses Stripe transport, credit ledger, and ~20
   webhook payload-resolution helpers.** **Held by:** internal seams are clean (ledger functions
   have no Stripe dependency; the `_resolve_*`/`_extract_*` layer is a proper anti-corruption
   band), and no second payment provider is on any roadmap. Noted: the money ledger's dedup key
   is literally `stripe_event_id` — provider-named column on `WebhookEvent`; rename/generalize
   only if a second provider ever becomes real.
5. **backups: operational domain lives inside `ModelAdmin` classes** (1,096-line `admin.py` —
   restore eligibility, candidate selection, orchestration — vs a 195-line `services.py`).
   **Held by:** it is one engine (admin and DR CLI both drive core `dr_engine` through the typed
   facade), and SA20 already schedules moving restore off the request path. **Shape guidance for
   SA20:** extract the restore orchestration into `services.py` while doing it, so the admin
   becomes a thin trigger and the logic is reusable off-admin.

### Per-module verdicts

- **quickscale_core** — no finding. The generator/apply/manifest stack's structural risk is
  concentrated in the seven-station option pipeline (candidate 2, frozen + gated).
  `schema/` (config/state/delta dataclasses + `StateManager`) is a clean desired/applied model;
  `apply/` (ledger + executor) remains the best-engineered seam in the repo;
  `dr_engine/orchestration.py` (3,013 lines, ~60 functions) fuses capture/upload/prune/media-sync
  /policy behind the typed adapter — deliberate failure-mode engineering throughout
  (`_rollback_remote_upload_after_persistence_failure`, `_record_prune_failure_without_masking_success`);
  watch it if a second storage backend or snapshot type is ever added. `social_manifest.py`
  remains social's special-cased path, frozen with the rest.
- **quickscale_cli** — no finding. The command layer holds orchestration weight
  (`apply_command.py` 3,658/91 defs, `module_config.py` 2,038/61 defs, `module_commands.py`
  1,596) but the heavy per-module content is the frozen T2.5 adapter layer scheduled to die with
  the declarative migration; the unledgered regeneration flow is already on the watchlist (SA22).
  Railway coupling (`railway_utils.py` 961 + deploy plumbing) is a deliberate single-platform
  commitment; it becomes a seam question only if a second deploy target is ever wanted.
- **orgs** — no new finding beyond the open repo-level one. Data model is sound (last-owner
  invariant lock-guarded in `models.py:145–253`, invitation dedup + tombstones); the
  HTML/JSON view duplication is well-factored (shared `InvitationNotificationMixin` +
  `InviteForm` + model invariants — domain logic lives once, views are thin adapters); candidates
  1 and 3 above. `views.py` fusion (1,271 lines) stays on the watchlist with the teams trigger;
  `_is_org_management_path` hand-classifier unchanged (fails closed, friction not leak).
- **billing** — no finding (candidate 4). Subscription state modeling is good: `Status`
  TextChoices + `current_subscription_status_q` + a conditional unique constraint enforcing
  one-current-subscription-per-org at the DB. Ledger idempotency remains a protected sound
  decision; the Phase-3 webhook lock window stays on the watchlist.
- **backups** — no finding (candidate 5); SA20 shape guidance recorded.
- **notifications** — no finding; the existing PII watch item is **sharpened**: message/delivery
  tables are `tenant_excluded` by reviewed marker ("System-wide notification send-request…"),
  yet org-invitation emails already flow through them today (org name, invitee email in
  `NotificationMessage` rows) — teams multiplies this, it does not create it. Revisit the
  exclusion reasons at teams kickoff, as the 2026-07-02 pass already directed.
- **auth** — no finding. 296 lines total; the swap-in User model one-way door remains handled by
  the CLI's late-adoption gate (`assess_auth_migration_state`, `module_config.py:123–277`).
- **blog / crm** — no findings. Both fully on the SA1.1 `TenantModel` base (crm: all 7 models);
  `AuthorProfile` correctly marker-excluded. Blog's defect-class items (markdown XSS, rate
  limits) are tracked SA26/SA21.2.
- **forms** — no structural finding; one consistency ticket: the tenant contract is
  hand-assembled per model (T1.7-era `tenant_org_fk` + dual `TenantManager`s + composite
  constraints on all four models, `models.py:42–230`) instead of inheriting `TenantModel` —
  registry + RLS enrollment are intact, but it is the second idiom for the same contract and it
  misses the base's `base_manager_name = "all_objects"` Meta. Port when next touching forms
  models.
- **listings / social / storage / analytics** — sampled; no findings. Classification is
  gate-enforced (default-deny); listings/social share the abstract-base pattern
  (`AbstractListing`, `BaseSocialItem`); storage/analytics are service-layer modules with no
  meaningful model surface.
- **teams** — still an empty placeholder. Landing checklist from this pass: declarative manifest
  path (freeze enforces), `TenantModel` base + markers for every model (runtime default-deny is
  self-contained), `TenantModelAdmin` for its admin (never bare `all_objects`), own module for
  views (not `orgs/views.py`), notifications-PII exclusion review, and expect orgs'
  `TENANT_TABLE_REGISTRY` entries + RLS conformance parametrization if its models enter orgs'
  test environment.

### Additional question raised by this pass

- Is the static `TENANT_TABLE_REGISTRY` literal intended to be retired in favor of the SA15
  marker derivation (its own docstring frames the derived overview as the replacement), or is
  double-entry bookkeeping the permanent design for the isolation boundary? The answer decides
  whether teams' models must be double-entered and whether candidate 3 ever promotes.

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
- 2026-07-04 (module-by-module deep pass, core and cli included as modules) — **zero new
  findings**; five candidates investigated and steelmanned (org-API mixin discipline, seven-station
  option pipeline, static tenant-registry double ledger, billing services fusion, backups
  admin-embedded ops) — each recorded with the gate that holds it and its breaking trigger.
  Per-module verdicts added, including the teams landing checklist and SA20 shape guidance.
  New ticket-shaped item: port forms models to the `TenantModel` base (second idiom for the
  tenant contract).
- 2026-07-05 (roadmap cleanup) — `operator-read-path-undefined`: **resolved**. SA14.2/SA14.3
  ported all five module admins (crm/blog/forms/listings/billing) off `all_objects` onto
  `TenantModelAdmin`; SA14.4 flipped module test suites to NOBYPASSRLS-by-default; SA14.5 landed
  `operator_access(reason=...)` as a real, audited, read-only RLS predicate; SA14.6 fail-hardened
  `QUICKSCALE_MODE`, closing the scope gap this document flagged (`adapters.py:60,81` and
  `views.py:63`, in addition to `middleware.py:268` — all four now direct required reads, per
  CHANGELOG.md). This closes the sole open finding from the 2026-07-04 pass; no other finding is
  currently open.
