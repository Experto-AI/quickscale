# Structural Autopsy: QuickScale

> This file is regenerated on each autopsy run to state **present reality for planning**: the
> current orientation, the open findings in full detail, and a curated watchlist. Closed findings
> exist only as dated lines in the **Reconciliation log** at the bottom (closeout detail lives in
> [CHANGELOG.md](../../CHANGELOG.md)); version control preserves prior full text. Finding IDs are stable
> across runs.

---

## Autopsy — 2026-07-06 (re-run)

### Orientation (2026-07-06)

QuickScale is a solo-maintained (Experto-AI/Victor Rocco) Python 3.13/3.14 + Poetry monorepo
(VERSION 0.86.0, integration branch `v87`) that generates user-owned Django 6 SaaS projects:
`quickscale_cli` (Click: plan/apply/dr/deploy), `quickscale_core` (Jinja2 generator, plan/apply
engine with the 16-step recovery ledger, manifest/contracts/derivation stack, DR engine), and 13
shipped Django modules under `quickscale_modules/` (teams still an empty placeholder). Generated
apps: Django 6 + PostgreSQL 18, single-service Railway; tenancy enforced twice (fail-closed
`TenantManager` + FORCE RLS with the AF9 execute-wrapper — re-verified intact this pass,
`current_org.py:424+`). **Since the 2026-07-04/05 passes, the SA19–SA33 tech-sweep batch closed
almost entirely** (SA19–SA33 all complete as of the 2026-07-06 closeout, including SA20's
CR-SA20-007); the only item still open in this batch is SA21.2. **Growth direction unchanged:** the teams module is the next
build (design locked, Option C child tables). **Depth this pass:** re-walked every watchlist seam
from 2026-07-04 and focused the fresh lens on the code the SA batch changed. Read fully —
`quickscale_core/runtime.py` (all four lazy symbol tables), the `entry_point.py` circular-import
guard region (`:1425–1511`), `backups/services.py` and `backups/admin.py` restore path
(`:380–742`), `scripts/check_module_core_imports.py`, `auth/views.py`, `orgs/signals.py` and the
membership guard region (`orgs/models.py:140–260`), the SA22 regeneration block
(`apply_command.py:1851–1918`), roadmap/tech-audit in full. Sampled — `dr_engine`
adapter/orchestration import surfaces, generated settings templates (SA21.1/SA29 landings),
`module_wiring.py`, forms models, billing services (grep-level re-verification). Skipped —
theme/frontend, blog/crm/listings/social domain internals (read clean in the 2026-07-04 deep pass;
their churn since is all SA-batch remediation), devtools. Severity floor unchanged: CLI is a
single-process local tool; generated apps are single-service WSGI; tenant isolation is the
highest-blast property.

Unlike the 2026-07-04 pass (zero findings immediately after a large remediation wave), this pass
opens **three findings** — all three surfaced by reading the seams the SA batch itself just
stressed: SA20 exposed the DR-domain import lattice and grew the admin-embedded orchestration;
SA28 added a second, divergent implementation of an org invariant at a new boundary.

### Summary table

| # | ID | Horizon | Size | One-line problem |
|---|----|---------|------|------------------|
| 1 | `dr-engine-module-circular-lattice` | now | M (first stage) | DR logic lives in core but its state and shims live in the backups module, producing a bidirectional import lattice held together by hand-maintained symbol tables and a string-matching exception classifier |
| 2 | `deletion-invariants-per-boundary-reimplementation` | 6–18 months (teams) | M | Org/billing invariants at the account-deletion boundary are re-implemented per callsite with divergent semantics instead of being owned by their domain modules |
| 4 | `org-model-universe-hand-enumerated` | 6–18 months (teams) | M | orgs hand-enumerates the cross-module tenant-model universe in unlinked literals (classification registry, purge delete-order registry, test-side copies) with no derivation from the marker/FK sources of truth — opened by the module deep pass below |
| 5 | `json-api-boundary-idiom-fragmentation` | 6–18 months (teams) | M | Three coexisting idioms for authed state-changing JSON endpoints (DRF baseline, orgs mixin stack, billing plain-View + manual CSRF) each re-implement the boundary by hand — opened by the module deep pass below |

---

### Finding 1: DR domain is split across the core↔module boundary into a circular import lattice

- **ID:** `dr-engine-module-circular-lattice`
- **Rank rationale (blast radius × likelihood):** every DR feature crosses this seam (likelihood ~1
  per DR change — SA20 just paid it), and the failure containment is a fragile exception-message
  classifier on the startup path of every generated app.
- **Horizon & trigger:** `now` — SA20 already forced an expansion of the tolerated-cycle allowlist
  to get tests to start; CR-SA20-007 and any future DR feature (second storage backend, scheduled
  restores, new snapshot type) hits the same lattice.
- **Confidence:** High — every edge of the cycle read directly this pass; the compounding event
  (SA20's guard expansion) is documented in `roadmap.md:130` and visible in
  `git log --follow quickscale_core/src/quickscale_core/runtime.py`.
- **Context dependence:** wrong-regardless — the coordination tax and fail-late classification are
  paid today, at current scale, by a solo maintainer.
- **Problem:** the DR engine's logic was extracted into core (`dr_engine/__init__.py:19`:
  "Extracted from `quickscale_modules_backups.services`") while its persistent state
  (`BackupArtifact`, `BackupPolicy`) and its Django-facing entry points stayed in the backups
  module — so neither side can import the other top-down, and the system holds the resulting cycle
  together with lazy-loading tables, a re-export shim, and message-text exception matching instead
  of fixing the topology.
- **Evidence:**
  - Core → module: `dr_engine/orchestration.py:80` imports `quickscale_modules_backups.models` at
    module level; `:223` dynamically imports `quickscale_modules_storage.helpers`.
    `dr_engine/adapter.py` (14+ function-level imports, e.g. `:41,:76,:103,:295`) imports
    `quickscale_modules_backups.services` — which is a shim that re-exports those same functions
    *from core*, so core's public adapter round-trips through the module back into core's own
    orchestration.
  - Module → core: `backups/services.py:17–125` re-exports ~80 names from
    `quickscale_core.runtime` with `# noqa: F401`, dozens underscore-private
    (`_build_pg_dump_command`, `_stage_admin_restore_upload`, …); its own protocols are placed
    there "to avoid circular imports with dr_engine which already imports from models"
    (`services.py:129–131`).
  - The "facade": `runtime.py:152–272` maintains four hand-written frozensets (~100 symbols, ~60
    private) with a `__getattr__` lazy loader whose stated reason is the cycle itself
    (`runtime.py:147`: "``dr_engine.orchestration`` imports ``quickscale_modules_backups.models``
    at module level, so we cannot import it eagerly"). `__all__` exports privates as a named
    "seam" (`:107–110`).
  - The guard: `manifest/entry_point.py:1436–1462` classifies benign-vs-broken adapter imports by
    string-matching CPython's exception text ("partially initialized module" + "circular import" +
    a module-name allowlist). The allowlist grew from 2 to 3 entries in the SA20 closeout
    (`:1446–1447`), because a *new import path* (backups admin → services → runtime) reached the
    import-time adapter registration (`:1511` `_initialize_managed_adapters_at_import()`).
  - The linter cannot see it: `scripts/check_module_core_imports.py:44–48` allows
    `quickscale_core.runtime` by module path only — `from quickscale_core.runtime import
    _private_name` is invisible to it, so the facade boundary is unenforceable at the granularity
    that matters.
  - Two cycles interlock: `runtime.py` fuses the DR surface with the manifest/social surface
    (`:126–141`), and module manifest adapters import back into it (`social/adapter.py:18`) — so
    importing anything DR-flavored from a Django app can trigger manifest-adapter registration and
    trip the other cycle. That is exactly what SA20 hit.
- **Why it compounds:** every DR feature now touches up to six stations — orchestration function +
  runtime lazy table + `__all__` + services shim + adapter signature + (when a new import path
  appears) the entry-point guard allowlist. SA20 touched all six. Each new tolerated-cycle pattern
  weakens fail-fast: a genuinely broken adapter whose error text happens to match the classifier is
  deferred from import time to first use (fail-late), and the classifier is coupled to CPython's
  message wording. Built on top today: all backups management commands, the admin restore/create/
  prune flows, the DR CLI (`dr` commands), and apply/deploy DR integration.
- **Detection signal:** any recurrence of the SA20 startup failure class —
  `ImproperlyConfigured` raised from `refresh_managed_adapters` during test or app startup after
  adding an import; growth of `_is_import_time_adapter_circular_import`'s allowlist or of the
  `_LAZY_*` tables in a diff is the leading indicator.
- **Steelman:** the extraction direction was right (CLI and admin drive one engine, not two), the
  lazy `__getattr__` is a standard Python pattern, and generated apps always ship backups+core
  together so the cycle never bites end users at runtime. This would be acceptable if DR were
  frozen — but SA20 is mid-flight, a second storage backend is a named watch item, and the guard
  already had to grow once. The steelman held for two passes ("best-engineered seam"); SA20's
  closeout note is the evidence it stopped holding.
- **Correct shape:** imports across the core↔module boundary form a DAG (modules → core only);
  adapter/module registration is an explicit runtime act, not an import-time side effect; no
  underscore-private name crosses a package boundary.
- **Options:**
  1. **Registration-not-import + facade split (recommended first stage).** Replace
     `_initialize_managed_adapters_at_import()` with explicit registration (module
     `AppConfig.ready()` or `importlib.metadata` entry points); delete
     `_is_import_time_adapter_circular_import` outright; split `runtime.py` into `runtime.dr` and
     `runtime.manifest` so the two domains stop interlocking. Removes the fragile classifier and
     the cross-domain trigger; does not yet remove core→module imports. Low risk, reversible,
     contained.
  2. **Persistence port.** Core defines protocols for artifact/policy persistence; the backups
     module implements and injects them at app-ready. Kills `orchestration.py:80`'s model import
     and the lazy tables' reason to exist; M–L effort; touches the whole orchestration surface.
  3. **Invert ownership.** Move all Django-model-touching orchestration back into the backups
     module; core keeps only pure primitives (pg_dump/pg_restore command building, hashing, path
     safety — already model-free in `dr_engine/primitives.py`). Largest migration; would also
     re-fuse the engine with one module and complicate the CLI's non-Django DR paths.
- **Recommendation:** Option 1 now — it is the smallest change that removes the *compounding
  mechanism* (guard growth + cross-domain interlock) and it makes Option 2 straightforward later if
  DR keeps growing. Do Option 2 the next time a DR feature has to add symbols to the lazy tables.
  · **Size:** M · **First step:** move managed-adapter registration out of `entry_point.py` import
  time into explicit registration, and delete the string-matching classifier — the SA20 test for it
  (`test_manifest_entry_point.py`) becomes the regression harness for the replacement.

---

### Finding 2: Deletion-boundary invariants are re-implemented per boundary with divergent semantics

- **ID:** `deletion-invariants-per-boundary-reimplementation`
- **Rank rationale (blast radius × likelihood):** blast is money and org integrity (orphaned live
  Stripe subscriptions, ownerless shared orgs); likelihood is moderate today (shell/admin user
  deletion) and rises sharply when teams multiplies membership-like invariants.
- **Horizon & trigger:** `6–18 months` — the teams build (next on the roadmap) adds more
  membership/ownership invariants; each one lands into this pattern unless the seam is fixed first.
  Second trigger: the first production account-deletion path that isn't `AccountDeleteView`.
- **Confidence:** High on the code shape (all three implementations read this pass); Medium on the
  admin-bypass exploitability — whether a generated app exposes User delete in Django admin depends
  on module composition (the auth module registers no User admin; apps *without* it get
  `django.contrib.auth`'s default UserAdmin, delete button included). Verify by generating both
  compositions and checking `/admin/`.
- **Context dependence:** wrong-for-now → wrong-regardless at teams kickoff; the dimension is the
  new feature domain (teams) plus any compliance-driven deletion path (GDPR erasure would be a
  third boundary).
- **Problem:** org-domain and billing-domain rules for "what must hold when a user disappears" have
  no domain owner — each deletion boundary re-implements them, and the two implementations that
  exist already disagree.
- **Evidence:**
  - `orgs/models.py:231–252` (`OrganizationMembership.delete()`): lock-guarded
    (`select_for_update` on the org), raises unconditionally when the last owner would be removed —
    but instance `delete()` overrides do not run under the deletion collector, so a `User` cascade
    (admin bulk delete, shell, any queryset path) bypasses it. That is the original TA30 defect
    class.
  - `auth/views.py:51–213` (`AccountDeleteView`, SA28): re-implements the last-owner rule
    *differently* — deletion is allowed when the org has no other members (`:130–137`), no row
    locks (plain `.exists()` check-then-act), plus billing knowledge inline
    (`_cancel_personal_org_subscriptions`, `:156–213`, with
    `except (BillingDisabledError, BillingValidationError): pass`). auth now hard-imports orgs
    models at module top (`:13–16`).
  - No backstop at the domain layer: no `pre_delete` receiver on `User` exists anywhere in orgs or
    billing (verified by search), so every boundary other than this one view enforces nothing —
    the personal org's live Stripe subscription survives its owner's deletion.
  - The project already knows the correct shape and wrote it down: `orgs/signals.py:3–9` (SA7.1)
    defines `organization_created` as "the canonical extension seam for cross-module behavior…
    Future org lifecycle events should follow the same pattern — define here and let consuming
    modules connect their own receivers." SA28 did the opposite: the consuming module (auth)
    absorbed the producing domains' logic.
  - Hand-off honored: tech-audit.md §Structural smells flagged exactly this
    ("any *future* invariant of this kind needs the same boundary-level enforcement convention —
    worth an arch-audit look when teams lands").
- **Why it compounds:** cost is N deletion boundaries × M invariants, each hand-written, some
  locked and some not, with semantics drifting per copy (already observable: "never remove last
  owner" vs "fine if no other members"). Teams adds M (team ownership, team-scoped resources);
  a GDPR-style erasure command adds N. Every divergence is a silent policy difference between
  paths that users and operators believe are equivalent.
- **Detection signal:** today, none — instrument by logging/alerting on `Organization` rows with
  zero OWNER memberships and on active `Subscription` rows whose org has no members; either
  appearing in production means a bypass path fired.
- **Steelman:** there are exactly two deletion paths today, the operator is the maintainer, and
  SA28 fixed the one users can reach — a reasonable defect-sized closeout. That holds only while
  user deletion stays single-path and invariants stay two; the locked teams design breaks both
  assumptions, and the semantic divergence between the two existing copies is already a latent bug
  regardless.
- **Correct shape:** each domain owns its lifecycle rules in exactly one place, enforced at a layer
  every ORM deletion path traverses (domain service + `pre_delete` receiver backstop), and
  boundaries *invoke* the domain rather than re-implementing it.
- **Options:**
  1. **Orgs-owned deletion service + signal backstop (recommended).** orgs exposes
     `validate_user_deletion(user)` / `prepare_user_deletion(user)` as the single implementation;
     `AccountDeleteView` calls it; orgs additionally connects a `pre_delete` receiver on the user
     model (in its `AppConfig.ready()`, per the SA7.1 pattern) that enforces the invariant on every
     collector path. Billing connects its own cancellation at the service seam (network calls stay
     out of the `pre_delete` transaction).
  2. **Signal-only:** auth defines `account_will_be_deleted`; orgs/billing connect receivers.
     Matches SA7.1 aesthetically but only fires where the signal is sent — admin/shell cascade
     still bypasses unless every boundary remembers to send it (same procedural trap).
  3. **DB-level:** conditional constraints/triggers guaranteeing every non-empty org has an OWNER.
     Strongest guarantee, but cross-row invariants in triggers are the tenancy layer's most complex
     idiom, and it cannot express the billing side at all.
- **Recommendation:** Option 1 — it reuses the project's established receiver convention, catches
  all ORM paths, and gives teams a ready-made place for its invariants. The first decision inside
  it is semantic, not technical: pick which last-owner rule is canonical (the model's unconditional
  one or the view's "no other members" allowance) and make the other copy delegate. · **Size:** M
  · **First step:** move `_get_blocking_orgs_for_deletion` into orgs as the single implementation
  and reconcile it with `OrganizationMembership.delete()`'s rule.

---

### Fix order and interactions

1. **Finding 1 stage 1** (registration-not-import + facade split) next — Finding 3
   (`backups-admin-orchestration-accretion`) is resolved (SA43, see reconciliation log); every
   future DR/module feature benefits from stage 1 landing.
2. **The three pre-teams seams — Findings 2, 4, and 5 — before teams kickoff**, in whatever track
   order fits, since all three are independent of each other: Finding 2 decides where teams'
   membership invariants live; Finding 4's derivation gate (its S-size first step) must exist
   before teams authors models, or every teams model needs triple entry in orgs literals;
   Finding 5's `csrf_exempt`-pairing gate plus base-view fold gives teams' management endpoints
   the one template they should copy. Interaction notes: Finding 2 touches billing's cancellation
   seam — don't move it while SA20 is mid-merge in the same worktree track; Findings 4 and 5 both
   edit orgs surfaces (`tenancy.py`/tests and `views.py` respectively) — sequence within one track
   to avoid conflict churn.

### Sound load-bearing decisions (protect these during remediation)

- **Dual-layer tenancy enforcement:** fail-closed `TenantManager` + FORCE RLS with the AF9
  execute-wrapper priming the GUC in-transaction (`current_org.py:424+`, re-verified this pass),
  under the NOBYPASSRLS runtime role with the always-on boot guard.
- **Governance by gate:** module→core import linter, org-context AST gate, manifest-sync gate,
  shrink-only imperative freeze, default-deny tenant classification + isolation-conformance suite —
  all still wired as blocking CI jobs (`ci.yml:122,150,178,325`), re-verified present. (Finding 1
  extends the import linter's granularity; it does not weaken it.)
- **Plan/apply as a checkpointed saga:** the `ApplyExecutor` + 16-step recovery ledger remains the
  repo's best crash-safety engineering; new apply-path mutations belong inside it (see watchlist).
- **`TenantModelAdmin` everywhere:** SA14.2–14.6 completed the port — all five module admins off
  `all_objects`, module test suites NOBYPASSRLS-by-default, `operator_access(reason=...)` audited.
- **SA21.1's env-first settings landing:** `USE_X_FORWARDED_FOR`/`TRUSTED_PROXY_COUNT` read via
  `config(...)` at runtime with fail-closed defaults (`base.py.j2:40–79`) — the right template for
  the deploy-time-config watchlist item below.

### Watchlist

- **Billing webhook concurrent-duplicate window** — carried unchanged, re-verified: Phase-3 still
  releases the dedup lock before processing (`billing/services.py:955–1012`); no handler sends
  mail/notifications (re-verified by search) · promotes the moment any non-idempotent side effect
  lands in a handler.
- **Dual child-table tenancy APIs** — carried: trigger-based equality infra
  (`tenancy.py:738` `install_equality_trigger_function`) still sits beside its composite-FK
  replacement (`:962` `add_composite_child_fk`); teams is still a placeholder, so deleting the old
  API first is still the cheap move · promotes if any teams child table lands on the trigger API.
- **Apply regeneration runs outside the recovery ledger — sharpened.** SA22 fixed TA20's ordering
  defect but landed as a *second recovery mechanism*: a hand-rolled backup/swap/rollback saga in
  `apply_command.py:1851–1918` that is exception-safe but not crash-safe (process death mid-swap
  strands project content across two anonymous `mkdtemp` dirs with no ledger entry to resume
  from), in the repo's top-churn file (25 commits/30d, now 3,768 lines) · promotes when the next
  apply-path mutation lands outside the `ApplyExecutor`, or if a crash-mid-`--force` report ever
  materializes.
- **`orgs/views.py` fusion** — carried: 1,273 lines fusing HTML views, org-admin JSON API, and
  invitation flows · promotes when teams begins extending org-facing surfaces: teams views must
  land in the teams module.
- **Grandfathered option defaults multi-sourced, T2.4/T2.5 unscheduled — third consecutive pass.**
  The shrink-only freeze holds and new modules ride the declarative path, but the migration phases
  `imperative_inventory.py` names as the driver (`:81–129` et al.) still appear nowhere in
  `roadmap.md` · promotes when a grandfathered default changes in one station only, or if
  T2.4/T2.5 remain unscheduled past the teams build (that boundary is now imminent).
- **NEW — Deploy-time configuration contract for generated apps** (promoted from tech-audit
  §Structural smells): there is still no generator-wide rule for which settings are baked literals
  vs env-read at deploy time — `MODULE_SETTINGS` is `pformat` literals (`module_wiring.py:107–131`),
  secrets use per-module `*_env_var` convention (now consistent after SA29), and SA21.1's proxy
  settings read env directly. Three idioms, chosen per feature by review discipline · promotes when
  the next deploy-varying option lands as a baked literal (a TA31 recurrence) — cheaper: write the
  one-paragraph rule into decisions.md and point the manifest-sync gate's docs at it.

*(Carried unchanged at low priority, unprinted: `_is_migrate_command()` argv sniffing in
`orgs/apps.py`; hardcoded `EXEMPT_PATH_PREFIXES` in `orgs/middleware.py`.)*

### Teams landing checklist (carried forward, updated)

Declarative manifest path (freeze enforces) · `TenantModel` base + markers for every model ·
`TenantModelAdmin` for its admin · own module for views (not `orgs/views.py`) · notifications-PII
exclusion review at kickoff · expect orgs' `TENANT_TABLE_REGISTRY` double-entry if its models
enter orgs' test env (see Questions) · **new:** membership/ownership invariants go into the
Finding 2 seam (orgs-owned deletion/lifecycle services + receivers), not into views ·
**new:** any teams background work reuses the `dispatch_background_restore`-pattern dispatch
service (the shape landed resolving Finding 3), not a fresh Popen block.

### Questions that would change the ranking

- Which last-owner semantic is canonical — `OrganizationMembership.delete()`'s unconditional rule
  or `AccountDeleteView`'s "allowed when no other members" allowance? The answer decides Finding
  2's first step and whether the current divergence is a latent bug or an undocumented rule.
- Is the static `TENANT_TABLE_REGISTRY` literal intended to retire in favor of SA15 marker
  derivation, or is double-entry bookkeeping the permanent design? (Carried, still unanswered —
  and now subsumed by Finding 4, which found a second hand registry of the same universe; the
  answer decides how far Finding 4's derivation option should go.)
- Are T2.4/T2.5 deliberately abandoned or just unscheduled? Third pass without an answer; the
  watchlist item's promotion boundary (teams build) is now imminent.
- Will any deletion/erasure path beyond `AccountDeleteView` ship (GDPR command, admin tooling)?
  Any yes promotes Finding 2's horizon to `now`.

### Red flags (out of scope — fix now)

- **Carried, still unfixed:** `entry_point.py` post-hooks retain permissive coercion defaults —
  blog (`:387–389`: `BLOG_POSTS_PER_PAGE` → 10, `BLOG_ENABLE_RSS` → True), listings (`:451` →
  12), forms (`:520–529`, five defaults incl. `FORMS_SPAM_PROTECTION` → True), notifications
  (`:900–920`). SA27 removed the resolver-side coercions and enforced apply-gate validation, but
  these post-hook fallbacks still second-guess validated input — the same fail-open class SA18.2
  purged from the analytics hook. Candidate tech-audit finding (TA-class), flagged second time.
- `AccountDeleteView._cancel_personal_org_subscriptions` swallows
  `BillingValidationError` unconditionally (`auth/views.py:212–213`) — "no active subscription"
  and "cancellation genuinely failed" are indistinguishable; part of Finding 2's remediation but
  worth a narrower except now.

Lenses scanned with no qualifying finding this pass: data/state integrity (billing subscription
modeling re-verified sound), trust boundaries (org-API mixin discipline unchanged; SA23/SA24
closed their defects), module cohesion beyond Findings 1/3, consistency/failure models (webhook
window stays watchlist; SA20's non-clobber races verifiedly closed), trajectory (option pipeline
frozen + gated), observability (SA20 improved restore observability — status/error/started-at now
persisted), API contract stability, testing architecture (NOBYPASSRLS default landed), design
conflicts beyond Finding 2, concurrency, security architecture (SA26 tracked), build/supply chain
(pip-audit gap remains a tech-audit tooling item), performance.

---

## Module-by-module autopsy — 2026-07-06 (deep pass)

> Run mode: deeper per-module pass at operator request, **treating `quickscale_core` and
> `quickscale_cli` as modules**, in blast-radius order (core → orgs → cli → billing → backups →
> notifications/auth → periphery). Same §0 decision rules. This pass deliberately went *below* the
> altitude of the 2026-07-04 deep pass: it read the seams that pass only sampled or graded by
> function map (`project_state.py`, the apply executor/ledger internals, `dr_engine` capture/lock
> internals, `plan_command.py` — first read by any pass, the purge command, billing's view layer).
>
> **Result: two new findings** (4 and 5 below) — both are *promotions of candidates the
> 2026-07-04 pass steelmanned*, promoted because this pass found the holding gate does not cover a
> second instance of the same pattern. That is the expected way re-run steelmen die: not by the
> gate failing, but by the pattern reproducing outside it.

### Finding 4: orgs hand-enumerates the cross-module model universe in unlinked literals

- **ID:** `org-model-universe-hand-enumerated`
- **Rank rationale (blast radius × likelihood):** the enumerations back the isolation boundary's
  bookkeeping and the org-offboarding path; likelihood approaches 1 at the teams build, when a
  batch of new tenant models must be hand-entered into each literal or the corresponding operation
  degrades.
- **Horizon & trigger:** `6–18 months` — the teams build; also fires on any new model added to an
  existing module, and on the first real org purge that hits a model someone forgot to register.
- **Confidence:** High — all enumerations read directly this pass, including the test that was
  believed to gate them.
- **Context dependence:** wrong-for-now on the new-domain dimension (teams); the classification
  half alone was an acceptable double ledger, which is exactly how the 2026-07-04 pass graded it.
- **Problem:** knowledge of "which models belong to an organization, and how they die" lives in
  hand-written literals inside orgs — a module that owns none of those models — instead of being
  derived from the sources of truth that already exist (tenant markers, the FK graph).
- **Evidence:**
  - `orgs/tenancy.py:119–410` — `TENANT_TABLE_REGISTRY`, 49 hand-written entries classifying other
    modules' models (known; candidate 3 of the 2026-07-04 pass).
  - `orgs/management/commands/purge_organization.py:64–212` — `_DELETE_SPECS`, a **second**
    hand-maintained registry: 21 cross-module models with hand-ordered, comment-justified FK-safe
    deletion order ("DealNote before Deal before Stage…").
  - `orgs/tests/test_management_commands.py:1281–1332` — **fixed by SA45** (2026-07-06): the
    "completeness" test previously validated `_DELETE_SPECS` against a third hand-written copy of
    the same universe (`expected_models = {...}`), deriving nothing. It now computes its expected
    model set from `get_tenant_models()` (the marker-derived tenant tables), so a new tenant model
    without a matching `_DELETE_SPECS` entry fails CI instead of passing silently. This closes
    Option 1's purge-spec half only — `TENANT_TABLE_REGISTRY`'s equivalent derivation check (the
    other half of Option 1) and the full purge-plan derivation (Option 2) remain open.
  - The prior steelman covered classification only: the runtime default-deny gate accepts
    marker-only models, so `TENANT_TABLE_REGISTRY` omissions are caught. A purge-side gate now
    exists too (SA45, above) — but only for `_DELETE_SPECS`; `TENANT_TABLE_REGISTRY` itself still
    has no derivation check of its own, so a classification-only omission still surfaces only as a
    `ProtectedError` mid-purge — fail-closed for integrity, but discovered during an org
    offboarding, the worst time.
- **Why it compounds:** every new tenant model in any module requires K coordinated edits inside
  orgs (classification literal, purge registry, test copies, RLS conformance parametrization), and
  the enumerations already cover different subsets with nothing forcing them to agree. Teams
  multiplies the entry count; a GDPR-class deletion obligation would make the purge path
  load-bearing overnight.
- **Detection signal:** `ProtectedError` raised from `purge_organization` in any environment; a
  diff adding a tenant model without a same-PR `_DELETE_SPECS` change now fails CI directly (SA45's
  derived completeness test) rather than surfacing only at purge time — the same is not yet true
  for a `TENANT_TABLE_REGISTRY` omission.
- **Steelman:** hand-ordered deletion is explicit, reviewable, and encodes FK subtleties
  (CASCADE-vs-PROTECT interactions) that naive traversal gets wrong; the module set is small and
  closed. That held while the universe was static — the teams build ends that condition, and the
  self-referential completeness test means the explicitness is not actually verified against
  anything.
- **Correct shape:** one derivation path from the existing sources of truth (tenant markers + FK
  topology) produces classification, RLS-conformance parametrization, and the purge plan; any
  hand-written literal that remains is a pinned snapshot that CI validates *against the
  derivation*, not against another hand copy.
- **Options:**
  1. **Derive the completeness gates first (cheap, immediate):** make the purge-spec test compute
     its expected universe from the marker-derived tenant tables (org-FK-bearing concrete models) —
     **done, SA45** — and add the same derivation check for `TENANT_TABLE_REGISTRY` — **still open**.
     Literals stay, but omissions fail CI the moment a model lands. S effort, removes the
     silent-staleness half.
  2. **Derive the purge plan itself:** topological delete order from the FK graph restricted to
     org-owned models, with `_DELETE_SPECS` reduced to explicit overrides for the genuinely tricky
     cases. M effort; removes the hand-ordering tax; needs care exactly where the current comments
     admit subtlety.
  3. **Module-contributed specs:** each module registers its own purge plan through the manifest /
     `AppConfig.ready()` seam and orgs iterates contributions. Cleanest ownership story, but
     invents a new cross-module protocol right before teams — highest coordination risk.
- **Recommendation:** Option 1 now (before teams starts), Option 2 when teams' models land and the
  derivation has a real test bed. Option 3 only if a second consumer of per-module lifecycle
  knowledge appears. · **Size:** M total (S for option 1 alone) · **First step:** replace the
  test's `expected_models` hand-list with a derivation from the tenant-classification universe —
  one test file, immediate CI protection.

### Finding 5: Authed state-changing JSON endpoints have three coexisting boundary idioms

- **ID:** `json-api-boundary-idiom-fragmentation`
- **Rank rationale (blast radius × likelihood):** the hand-built instances guard money paths
  (billing checkout/cancel/portal) and org management (control-plane tables deliberately outside
  RLS — view checks are the only guard); likelihood of a miss rises with every new endpoint that
  must *choose* an idiom, starting with teams' management surface.
- **Horizon & trigger:** `6–18 months` — teams management endpoints are the named trigger (the
  2026-07-04 pass already directed "consider folding the full stack into one `OrgApiBaseView`
  before then"); this pass found the pattern is not orgs-local, so the fold must be wider.
- **Confidence:** High on existence (all three idioms read this pass); Medium on urgency — every
  *current* endpoint is individually covered and tested.
- **Context dependence:** wrong-for-now on the new-domain dimension; three idioms among 13 shipped
  modules is absorbable, three idioms as the template pool for a new module's API surface is how a
  silent hole ships.
- **Problem:** the project established a fail-closed DRF baseline as the sanctioned JSON-API shape
  (SA11), but two parallel hand-rolled idioms survived beside it, so the boundary contract
  (CSRF, auth, org-role, payload validation) is re-implemented per idiom and enforced per endpoint
  by discipline plus tests, with no gate pushing new surfaces onto the baseline.
- **Evidence:**
  - Sanctioned baseline: SA11's `PublicSystemOrgReadMixin`/DRF stack — used by billing's own read
    endpoints (`views.py:139,377,406,436,471` are DRF `APIView`s).
  - Idiom 2 (orgs): `JsonApiMixin`/`JsonOrganizationAccessMixin` stacks on the eight `OrgApi*`
    endpoints (`orgs/views.py:944–1271`) — candidate 1 of the 2026-07-04 pass.
  - Idiom 3 (billing, confirmed this pass): four state-changing plain Django Views
    (`views.py:158–376`: checkout ×2, cancel, portal) each decorated
    `@method_decorator(csrf_exempt, name="dispatch")` and then *manually re-implementing* CSRF via
    `_enforce_csrf` (`views.py:82–84`, wrapping `CsrfViewMiddleware` to get JSON error shape),
    plus hand JSON parsing (`_parse_json_object_payload`) and hand org/role resolution
    (`_resolve_request_organization`, `views.py:63–79`). Four of the five exempt views call
    `_enforce_csrf`; the fifth is the signature-verified Stripe webhook (correctly exempt).
  - Per-view CSRF tests exist (`billing/tests/test_views.py:125+`, `enforce_csrf_checks=True`
    clients) — the discipline is real, and it is only discipline: a new endpoint copying the
    decorator without the helper call fails no gate.
- **Why it compounds:** every new JSON surface picks one of three idioms or invents a fourth; each
  hand idiom re-implements the same four boundary concerns, so the cost of a boundary-rule change
  (e.g. SA21's canonical-IP work, a future session policy) is ×3; and each endpoint built on a
  hand stack raises the migration cost of ever consolidating. A missed `_enforce_csrf` on a
  money-moving endpoint is a silent CSRF hole with no structural detection.
- **Detection signal:** none today for the miss case — instrument by adding a checks/lint gate:
  every `csrf_exempt` callsite must be paired with either a signature-verification call or
  `_enforce_csrf` (the org-context AST gate at `ci.yml:178` is the in-repo template for exactly
  this kind of rule).
- **Steelman:** the plain-View idiom exists for a reason (JSON error bodies instead of Django's
  HTML CSRF failure; webhook exemption legitimately needed), every instance is tested, and
  migrating working money paths to DRF is churn with regression risk. That justifies the *current*
  endpoints; it does not justify leaving three templates lying around when a new module's API
  surface is the next thing to be built.
- **Correct shape:** one base per transport need (a session-authed JSON base view or DRF baseline
  extension) owns CSRF/auth/org-role/parsing exactly once; `csrf_exempt` appears only where a
  cryptographic request authenticator (webhook signature) replaces it; a lint/CI gate enforces the
  pairing so new endpoints cannot silently opt out.
- **Options:**
  1. **Gate first, consolidate opportunistically (recommended):** add the `csrf_exempt`-pairing
     AST gate (S), fold orgs' `OrgApi*` mixin stack into one `OrgApiBaseView` (the prior pass's
     S-size hardening), and declare the DRF baseline the required shape for *new* endpoints —
     migrate billing's four plain Views only when next touched.
  2. **Full consolidation onto DRF now:** migrate orgs' and billing's hand stacks to the SA11
     baseline in one program. Removes all three-idiom cost immediately; highest regression risk on
     money paths for no user-visible change.
- **Recommendation:** Option 1 — the gate removes the silent-hole class before teams, the base-view
  fold gives teams the template it should copy, and the billing migration can ride routine work.
  · **Size:** M (gate + fold S each; billing migration the long tail) · **First step:** the
  `csrf_exempt`-pairing gate, modeled on `check_org_context_primitives.py`.

### Candidates investigated and why they did not qualify

1. **core: M2 state consolidation is shape-sniffed, and the schema version field is dead.**
   `project_state.py:336–384` decides whether `state.yml` is "consolidated" by duck-typing keys
   (`managed_files` present / explicit empty `modules` / `prefix|branch|installed_at` fields)
   while `QuickScaleState.version` stays `"1"` forever; three state files remain live, and the
   `file_hashes.yml` fallback in drift detection is documented as *permanent* design, not
   migration compat (`:600–615`). **Held by:** the F12.2 exception is bounded and documented,
   parsing is fail-loud where it matters (SA18.6), writes are atomic, and only one migration
   generation exists. **Breaks if:** a second state-format migration adds a second generation of
   key-sniffing instead of finally using the version field — check this at the next `state.yml`
   schema change.
2. **core/dr_engine: hand-rolled compensation per capture step.** The capture path's failure
   engineering is genuinely excellent at code level (verified this pass, not just by function
   names: upload rollback with cleanup-failure surfacing `orchestration.py:953–990`, prune
   failures recorded without masking success `:1040–1044`), but it is bespoke inline saga logic
   per step. **Held by:** deliberate, tested, single backend, single snapshot type. **Breaks if:**
   a second storage backend or snapshot child type forces replicating the pattern by hand —
   unchanged watch condition.
3. **backups: "restore attempt" is not an entity** — one status slot plus `restore_started_at`/
   `restore_error` on `BackupArtifact` (`models.py:89–101`) fuses artifact lifecycle
   (ready/validated/deleted) with restore-operation state (restoring/restored/failed). This is the
   *root* of the CR-SA20-007 clobber problem: retries overwrite the only record of the prior
   attempt, which is why the pre-spawn snapshot/rollback dance exists at all. **Held by:** the
   locked Option A decision (2026-07-06) is a sound tactical fix within the current model, and
   restore volume is tiny. **Breaks if:** the restore lifecycle grows more states (queueing,
   progress, cancellation) or concurrent attempts become possible — then promote "restore attempt"
   to its own row and let artifact status derive; feeds Finding 3's correct shape.
4. **cli: TOML edited by string manipulation.** `module_dependency_sync.py` renders and splices
   pyproject entries textually (`_render_toml_literal`, `_append_dependency_entries`) — but
   `_write_validated_toml` re-parses before writing, so corruption fails loud. Per-module
   dependency knowledge (`_STORAGE_CLOUD_BACKENDS` → boto3) is another frozen-layer station.
   Ticket-shape at most.
5. **billing: ledger/locking discipline re-verified sound** — `select_for_update` consistently on
   every contested write path (`services.py:585–2217`), conditional-unique current-subscription
   constraint, event-keyed dedup. The webhook lock-window watchlist item is unchanged.

### Per-module verdicts

- **quickscale_core** — no new finding beyond repo-level Finding 1 (whose evidence this pass
  deepened). First full reads this pass: `project_state.py` (candidate 1), `apply/executor.py` +
  ledger flow (invariants stated and honored; the `__checkpoint__` placeholder state is mitigated
  by AF5-CR-002 snapshot passing), `advisory_lock.py` (pid + staleness metadata, manual-clear
  guidance), `dr_engine/_lock.py` (O_EXCL lockfile with stale-clear — correct for the single-host
  deployment model), manifest `loader.py`/`derivation.py` (typed, fail-loud parsing; clean).
- **orgs** — Finding 4. Beyond it: `purge_organization` command *contract* discipline is good
  (UUID-only destructive targeting, tombstone in-transaction, dry-run, reserved-org guard);
  `signals.py` remains the right seam pattern awaiting more producers (Finding 2's point);
  middleware/managers unchanged since their last deep read.
- **quickscale_cli** — no finding. `plan_command.py` (1,271 lines, first read by any pass):
  interactive plan/reconfigure flow with per-module special-casing (auth validation-error
  classifier `:360`, notifications existing-project validation `:402`) — more stations of the
  frozen T2.5 layer, dying with the declarative migration; structure is service-like and testable.
  `module_dependency_sync.py` → candidate 4. Deploy/DR command surfaces re-verified only at the
  SA31 seam (stdin secret transport present).
- **billing** — Finding 5 (shared with orgs). Candidate 5 records the re-verified sound core. The
  provider-named `stripe_event_id` dedup key note carries unchanged.
- **backups** — no new finding; candidate 3 records the restore-attempt entity note that feeds
  repo-level Finding 3. Management commands remain thin `ADAPTER_FUNCTIONS` wrappers (the
  private-import pair in `services.py:181,192` is Finding 1 evidence, not a separate item).
- **notifications** — no finding. `NotificationWebhookView` read this pass: signature +
  timestamp verified, fail-closed on disabled/signature errors, dedup-aware response — the right
  shape for an exempt endpoint (and the counter-example Finding 5's gate should encode). The
  PII/tenant-exclusion watch item carries unchanged to teams kickoff.
- **auth** — covered by repo-level Finding 2 (its view owns org/billing invariant copies); nothing
  further in its 296 lines.
- **blog / crm / forms / listings / social / storage / analytics** — churn since the 2026-07-04
  deep pass is exclusively SA-batch remediation (verified via log); spot-checks only this pass.
  Forms' `TenantModel` port stays a carried ticket; SA26 (markdown URI sanitization) and SA30
  (listings/storage fail-open residuals) remain roadmap defect items, not structural.
- **teams** — still an empty placeholder. Landing-checklist additions from this pass: land
  Finding 4's derivation gate *before* authoring models (else every teams model needs triple
  entry in orgs literals), and build management endpoints on the Finding 5 base/gate, not on any
  of the three existing idioms by copy-paste.

---

## Autopsy — 2026-07-04 (re-run) and module-by-module deep pass

> Superseded by the 2026-07-06 re-run above, which re-verified all watchlist evidence and opened
> three findings from the seams the SA19–SA33 batch changed. The 2026-07-04 passes' full text
> (orientation, zero-findings result, five steelmanned candidates, per-module verdicts) is
> preserved in version control; their still-current outputs — the watchlist, the teams landing
> checklist, and the open questions — are carried forward above. This stub heading is kept so
> existing links resolve.

---

## Autopsy — 2026-07-03 (fresh full pass)

> Superseded by the 2026-07-04 re-run, which re-verified all of this pass's evidence. Its four
> findings are reconciled in the log below. This stub heading is kept so existing links resolve.

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
- 2026-07-06 (re-run) — **three findings opened** from the seams the SA19–SA33 batch changed:
  `dr-engine-module-circular-lattice` (bidirectional core↔backups import lattice; SA20's guard
  expansion at `entry_point.py:1446` is the compounding evidence),
  `deletion-invariants-per-boundary-reimplementation` (SA28's view-level guard diverges from the
  lock-guarded model rule; no domain-level backstop; tech-audit §Structural-smells hand-off
  honored), `backups-admin-orchestration-accretion` (SA20 async lifecycle landed inline in
  `admin.py` against the 2026-07-04 shape guidance; 2026-07-04 candidate 5's holding gate broke).
  Watchlist reconciled: billing-webhook window carried (re-verified, no non-idempotent handlers);
  dual child-table API carried (both APIs present, teams still placeholder); apply-regeneration
  item carried **sharpened** (SA22 landed as a second, exception-safe-but-not-crash-safe recovery
  mechanism outside the ledger); orgs-views fusion carried (1,273 lines); grandfathered-defaults
  carried (T2.4/T2.5 unscheduled, third pass); **new** item: deploy-time configuration contract
  (literal-vs-env), promoted from tech-audit smell. Prior red flags reconciled: CHANGELOG dangling
  arch-audit anchor → **fixed** (verified gone); `entry_point.py` post-hook coercion defaults →
  **still present**, re-flagged (SA27 cleaned resolvers/apply-gate, not post-hooks). Sound
  decisions re-verified: CI gates present (`ci.yml:122,150,178,325`), AF9 execute-wrapper intact,
  SA14 admin port complete. Forms `TenantModel` port still pending (ticket-shaped, carried).
- 2026-07-06 (module-by-module deep pass, core and cli included as modules) — **two findings
  opened**, both promotions of candidates the 2026-07-04 deep pass had steelmanned, promoted
  because the pattern reproduced outside the holding gate: `org-model-universe-hand-enumerated`
  (2026-07-04 candidate 3 covered only the classification registry; this pass found the purge
  command's `_DELETE_SPECS` is a second hand registry and its "completeness" test validates a
  hand-list against a hand-list — no derivation anywhere) and `json-api-boundary-idiom-fragmentation`
  (2026-07-04 candidate 1 was orgs-local; this pass confirmed billing's checkout/cancel/portal
  views are a third idiom — plain Views with `csrf_exempt` plus manual `_enforce_csrf`). Five
  candidates investigated and not promoted, each recorded with its holding gate and breaking
  trigger: M2 state-consolidation shape-sniffing with a dead schema-version field (core),
  hand-rolled per-step capture compensation (core/dr), restore-attempt-not-an-entity (backups —
  feeds Finding 3's correct shape), string-spliced TOML editing (cli), billing ledger/locking
  discipline (re-verified sound). First-ever full reads: `project_state.py`, `apply/executor.py`,
  `advisory_lock.py`, `dr_engine/_lock.py`, `plan_command.py`, `purge_organization.py`, billing's
  view layer, notifications' webhook view. Periphery modules verified SA-batch-churn-only since
  the 2026-07-04 deep pass and spot-checked. Teams landing checklist extended (Finding 4 gate
  before models; Finding 5 base before endpoints).
- 2026-07-06 (roadmap cleanup, doc-consistency correction) — Finding 3
  (`backups-admin-orchestration-accretion`) reframed, **not resolved**: CR-SA20-007 and the TA36
  compare-and-swap fix (both cited here as the finding's "now" trigger) closed as part of SA20's
  full closeout, confirmed present in code (`backups/admin.py`'s `_atomic_claim_restore()`). The
  structural duplication itself (lifecycle logic inline in `admin.py`, once per branch) was not
  extracted during that closeout, so the finding stands but as standalone follow-up work rather
  than one that rides an already-open item. Orientation's "still open: SA20 (CR-SA20-007), SA21.2,
  SA26, SA30" line corrected — SA20, SA26, and SA30 are all complete; SA21.2 is the only open item.
- 2026-07-06 (roadmap cleanup) — Finding 4 (`org-model-universe-hand-enumerated`): **partial
  progress, not resolved**. SA45 landed Option 1's purge-spec half — the completeness test now
  derives its expected model set from `get_tenant_models()` instead of a third hand-written copy,
  closing the silent-staleness gap on the `_DELETE_SPECS` side. `TENANT_TABLE_REGISTRY`'s
  equivalent derivation check (Option 1's other half) and the full purge-plan derivation (Option 2)
  remain open; Finding 4 stays open pending those, and pending the teams build that motivates its
  horizon.
- 2026-07-07 (roadmap cleanup) — **Finding 3 (`backups-admin-orchestration-accretion`): resolved.**
  SA43 landed exactly the recommended first step: `dispatch_background_restore(artifact, *,
  confirmation)` (plus `_atomic_claim_restore`, `_get_manage_py`, and the claimable-status set) was
  extracted into `backups/services.py`, and both the recorded-artifact and uploaded-file admin
  dispatch branches now call the same function instead of carrying two inline copies. The
  2026-07-06 "reframed, not resolved" note above is superseded — the extraction it flagged as
  still-pending has since landed. Summary table and fix-order renumbered accordingly (Finding 3 row
  dropped; findings 1/2/4/5 keep their stable IDs and numbers).
