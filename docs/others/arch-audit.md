# Structural Autopsy: QuickScale

> This file is regenerated on each autopsy run to state **present reality for planning**: the
> current orientation, the open findings in full detail, and a curated watchlist. Closed findings
> exist only as dated lines in the **Reconciliation log** at the bottom (closeout detail lives in
> [CHANGELOG.md](../../CHANGELOG.md)); version control preserves prior full text. Finding IDs are stable
> across runs.

---

## Autopsy — 2026-07-09 (re-run, delta pass) and module-by-module deep pass

### Orientation (2026-07-09)

QuickScale is a solo-maintained (Experto-AI/Victor Rocco) Python 3.13/3.14 + Poetry monorepo
(VERSION 0.87.0, integration branch `v87`) that generates user-owned Django 6 SaaS projects:
`quickscale_cli` (Click: plan/apply/dr/deploy), `quickscale_core` (Jinja2 generator, plan/apply
engine with the 16-step recovery ledger, manifest/contracts/derivation stack, DR engine), and 13
shipped Django modules under `quickscale_modules/` (teams still a README-only placeholder,
re-verified). Generated apps: Django 6 + PostgreSQL 18, single-service Railway; tenancy enforced
twice (fail-closed `TenantManager` + FORCE RLS with the AF9 execute-wrapper). **This is a delta
pass over two batches**: the SA47–SA56 closeout (already reconciled line-by-line in the log
below) and — new to this pass — the 2026-07-09 `fix: make check` / `fix: some make ci` commits
(`6ea37301`, `198a1951`, ~4,300 insertions), which landed behavioral changes under housekeeping
messages: the `runtime.py` → `runtime/` package split (dr/manifest facade), a new `social` entry
in the import linter's shrink-only legacy list, an argv-sniffing DB-role ladder in `local.py.j2`,
a composite-FK `NOT DEFERRABLE` semantic change in `tenancy.py`, a `tenant_excluded` precedence
change in `is_tenant_model()`, a third (unvalidated) TOML splice function in the CLI, and a new
listings configurator. Read fully this pass — the SA54/SA53 diffs, `runtime/__init__.py` +
`runtime/dr.py`, `check_module_core_imports.py` delta, all three settings templates + `start.sh.j2`,
`orgs/apps.py` boot guard, `module_dependency_sync.py`, the `module_config.py` listings addition;
**deep-pass first-ever full reads** — the entire social module (models/services/contracts/admin),
`storage/helpers.py`, `remove_command.py`, `orgs/admin.py`'s `TenantModelAdmin`, and the
`_sidecar.py`/`_resolve_media_runtime` storage-coercion diffs. Sampled — SA53's retry/checkpoint
tests, `check_module_core_compatibility.py` facade support, billing's SA56-migrated view bodies,
lifecycle e2e tests. Skipped — files verified untouched since 2026-07-07 by git log
(`billing/services.py`, `apply_command.py`, `apply/`, `project_state.py`, orgs
middleware/current_org/managers, tenancy trigger APIs beyond the one-line SQL change). Severity floor
unchanged: CLI is single-process local; generated apps are single-service WSGI; tenant isolation
is the highest-blast property. Growth direction: **the roadmap is fully drained** (all three
tracks 0 open items) and teams remains unscheduled — this pass feeds the next planning cycle.

**Result: three prior findings still open, one new finding from the delta pass, zero new
findings from the module deep pass** (five candidates investigated and held, two new red flags,
two watchlist items sharpened — see the deep-pass section below). Finding 1 is *progressed and
re-strengthened* (the facade split landed — the right direction — but added a new hand-synced
symbol station, and the social module had to route around the facade via a linter exception,
breaking that list's shrink-only contract). **New Finding 6**: the "which DB privilege does this
process run under" decision has no single owner — four mechanisms with three different semantics,
already colliding at source level on the no-Redis deploy path. Finding 2 is *narrowed* (SA47's
canonical check verified consumed at all four callsites; the receiver backstop is still missing).
Finding 4 is *unchanged in structure* with a caution: two derivation-input semantics
(`is_tenant_model` exclusion precedence, composite-FK deferrability) changed inside housekeeping
commits with no decision record. Finding 5 remains closed — no unsanctioned endpoint idiom
appeared in the delta; the SA46 gate got stronger (`cbde517a`).

### Summary table

| # | ID | Horizon | Size | One-line problem |
|---|----|---------|------|------------------|
| 1 | `dr-engine-module-circular-lattice` | now | M remaining (Option 2) | DR logic lives in core but its state and lifecycle live in the backups module; the cycle is held by hand-maintained symbol tables that the facade split *relocated and grew* rather than removed, and new modules now route around the facade via a growing linter exception list |
| 6 | `db-privilege-mode-procedural` | now | M | "Which DB role does this process get" is decided independently by start.sh (env-unset), production settings (argv-shaped errors), local settings (argv-switching, new this delta), and the orgs boot guard (positional argv) — four mechanisms, three semantics, one live source-level collision |
| 2 | `deletion-invariants-per-boundary-reimplementation` | deferred (teams unscheduled) | M remaining | Org/billing invariants at the account-deletion boundary now share one canonical last-owner check (SA47) but still have no domain-level `pre_delete` backstop — every deletion path other than `AccountDeleteView` enforces nothing |
| 4 | `org-model-universe-hand-enumerated` | deferred (teams unscheduled) | M remaining (Option 2) | orgs hand-enumerates the cross-module tenant-model universe; membership is CI-gated against derivations (SA15.3/SA45/SA49) but the purge *order* is still hand-written, and this delta changed two derivation-input semantics without a decision record |

---

### Finding 1: DR domain is split across the core↔module boundary into a circular import lattice

- **ID:** `dr-engine-module-circular-lattice`
- **Rank rationale (blast radius × likelihood):** every DR feature and now every *new module
  adapter* crosses this seam; empirical rate is ~1 compounding instance per batch (SA20 guard
  growth, CR-SA38-001 hand-copy, and this delta's social linter exception + facade `__all__`
  station).
- **Horizon & trigger:** `now` — the social exception landed this delta; the teams module's
  adapter will face the same import choice. Any DR feature or new adapter pays the tax until
  Option 2.
- **Confidence:** High — every edge re-verified this pass in current code.
- **Context dependence:** wrong-regardless — the tax is paid today, at current scale, by a solo
  maintainer; it has now fired in three consecutive batches.
- **Problem:** the DR engine's logic was extracted into core while its persistent state
  (`BackupArtifact`, `BackupPolicy`) and its Django-facing entry points stayed in the backups
  module — so neither side can import the other top-down, and the system holds the cycle together
  with lazy-loading tables, a re-export shim, hand-synced `__all__` literals, and a growing
  per-module linter exception list.
- **Evidence (updated this pass):**
  - **The facade split landed — and added a station.** `runtime.py` is now the `runtime/`
    package: `runtime/dr.py` + `runtime/manifest.py` + a combined facade. The four `_LAZY_*`
    frozensets and the `__getattr__` loader survived intact (`runtime/dr.py:91–210, 213–236`).
    The combined facade (`runtime/__init__.py:42–105`) carries a **hardcoded literal `__all__`**
    that must be hand-kept as the union of `dr.__all__` and `manifest.__all__` — its own
    docstring says "When adding a new public symbol to dr.py or manifest.py, add it here too"
    (`:39–40`). Mismatches are partially gated (`check_module_core_compatibility.py` resolves
    `__all__` literals and was extended for the facade), but the sync itself is manual.
  - **New modules now route *around* the facade.** `runtime/__init__.py:12–14` instructs:
    "Module-owned adapters should import from `quickscale_core.runtime.manifest` directly to
    avoid pulling in the DR surface at import time and triggering circular imports." To let the
    social adapter do that, `check_module_core_imports.py:77–81` added a `"social"` entry to
    `LEGACY_ALLOWED_IMPORTS` — a list whose own contract says entries exist only to be removed
    (`:55–57`). The shrink-only list grew, and the linter now classifies as "legacy" the exact
    import the facade docstring *recommends*. Two governance artifacts state opposite rules for
    the same import; the root is the cycle.
  - **SA54's dedup chose a parameter seam with a test-pinned copy.** The stale-restore threshold
    now flows module→core through an explicit parameter
    (`orchestration.py` `restore_admin_uploaded_backup(..., stale_threshold_minutes: int = 30)`;
    admin passes `STALE_RESTORE_THRESHOLD_MINUTES` from `services.py:554`), with an
    `inspect.signature` test failing CI if the core default drifts from the module constant
    (`test_services.py::test_sa54_stale_threshold_default_matches_constant`). Right direction —
    but the default is still a literal copy held consistent by a gate, because core still cannot
    import the module's constant.
  - Core → module (narrowed): `dr_engine/orchestration.py:80` imports
    `quickscale_modules_backups.models` at module level; `dr_engine/adapter.py` carries 12+
    function-level lazy imports of orchestration plus two direct `quickscale_modules_backups`
    imports (`adapter.py:295`). **Improvement found in the deep pass:** `6ea37301` repointed the
    adapter's lazy imports from `quickscale_modules_backups.services` (the round-trip through the
    module shim) to `quickscale_core.dr_engine.orchestration` directly — one lattice edge the
    2026-07-07 pass cited is now gone.
  - Module → core (unchanged): `backups/services.py:20–129` re-exports ~80 names from
    `quickscale_core.runtime`, dozens underscore-private (`_build_pg_dump_command`,
    `_SNAPSHOTS_DIRECTORY_NAME`, …) — and three underscore-private names are now codified in the
    facade's public `__all__` (`runtime/__init__.py:70–72`).
- **Why it compounds:** every DR feature touches up to six stations (orchestration function +
  dr.py lazy table + dr.py `__all__` + the combined facade's literal `__all__` + services shim +
  adapter signature); every boundary-crossing invariant becomes a gated copy pair (SA54's shape);
  and — new this pass — **every new module whose adapter needs manifest surface either adds a
  linter exception or pays the cycle**. Teams is the next module. Built on top: all backups
  management commands, admin restore/create/prune, the DR CLI, apply/deploy DR integration, and
  now the social adapter's import path.
- **Detection signal:** growth of `_LAZY_*` tables, the facade `__all__`, or
  `LEGACY_ALLOWED_IMPORTS` in any diff (all three fired or persisted this delta); any diff
  editing one side of a gated copy pair (SA54's test is the tripwire).
- **Steelman:** each individual mechanism is a standard pattern (lazy facades, parameter
  injection, linter grandfathering), all are now gated, and generated apps ship backups+core
  together so the cycle never bites end users at runtime. That held for two passes and has now
  failed on evidence three times — the mechanisms are multiplying, not converging.
- **Correct shape:** imports across the core↔module boundary form a DAG (modules → core only);
  no underscore-private name crosses a package boundary; a boundary-crossing invariant has
  exactly one implementation; adding a module adapter requires zero linter exceptions.
- **Options:**
  1. ~~Registration-not-import + facade split~~ — **done** (SA44 + this delta's `runtime/`
     package). It removed the classifier and clarified the surface, but demonstrably did not
     remove the cycle: social had to route around the facade the same week the split landed.
  2. **Persistence port (the live option).** Core defines protocols for artifact/policy
     persistence; the backups module implements and injects them at app-ready. Kills
     `orchestration.py:80`, the lazy tables' reason to exist, the SA54 copy-pair class, and the
     need for adapter deep-import exceptions. M–L effort.
  3. **Invert ownership.** Move all Django-model-touching orchestration into the backups module;
     core keeps pure primitives. Largest migration; complicates the CLI's non-Django DR paths.
- **Recommendation:** Option 2. The trigger condition named last pass ("the next time a DR
  feature must add lazy-table symbols *or* duplicate an invariant") has been met twice since —
  SA54 duplicated an invariant (mitigated by a gate) and social needed a routing exception.
  Schedule it in the next planning cycle, before the teams adapter lands a fourth workaround.
  · **Size:** M remaining · **First step:** define the artifact/policy persistence protocol in
  core and port `restore_admin_uploaded_backup` (the SA54 seam) onto it — that one function
  exercises the model import, the threshold copy, and the staging lifecycle at once.

---

### Finding 6: Database-privilege selection has no owning contract — four mechanisms, three semantics

- **ID:** `db-privilege-mode-procedural`
- **Rank rationale (blast radius × likelihood):** blast is generated-app deploy availability and
  the legibility of the RLS privilege boundary (the system's highest-blast property); likelihood
  is high — one collision is already present at source level, and teams migrations plus every new
  privileged command re-enter this seam.
- **Horizon & trigger:** `now` — the `local.py.j2` argv ladder landed this delta
  (`198a1951`), and the start.sh↔boot-guard collision on the no-Redis path exists in current
  templates. Also fires on: any new command needing DDL, any new execution context (DR
  subprocesses, cron, background workers).
- **Confidence:** High for the structural divergence (all four mechanisms read directly this
  pass); Medium for the live deploy defect (static analysis only — confirm by booting a generated
  app with `REDIS_URL` unset and a superuser `DATABASE_URL`; the tech-audit's proposed
  generated-project boot smoke test is the right harness).
- **Context dependence:** wrong-regardless for the divergence; the collision is
  wrong-for-Railway-deploys-without-Redis specifically.
- **Problem:** the decision "does this process run under the superuser `DATABASE_URL` or the
  restricted NOSUPERUSER/NOBYPASSRLS `RUNTIME_DATABASE_URL`" — the switch on which the RLS
  isolation guarantee rests — is re-decided independently by four components using three
  different detection semantics, instead of being decided once by the process launcher and
  consumed everywhere else.
- **Evidence:**
  - **Mechanism 1 — start.sh env-unset (the sanctioned one):** `start.sh.j2:47–59` runs
    `RUNTIME_DATABASE_URL="" python manage.py migrate` and, when `REDIS_URL` is unset,
    `RUNTIME_DATABASE_URL="" python manage.py createcachetable`.
  - **Mechanism 2 — production settings argv ladder:** `production.py.j2:166–194` — runtime URL
    wins when present; `elif "migrate" in sys.argv` (membership, any position) requires the
    superuser URL; `collectstatic`/`compilemessages` get a dummy-URL fallback; serving without
    the runtime URL fails closed.
  - **Mechanism 3 — local settings argv switch (new this delta):** `local.py.j2:36–43` —
    `if _runtime_db_url and "migrate" not in sys.argv:` use the runtime role, `elif
    _database_url:` use the superuser. Here argv *is* the switch, precedence is inverted relative
    to production, and non-migrate serving **falls back open** to the superuser URL when the
    runtime URL is unset (production fails closed).
  - **Mechanism 4 — orgs boot guard positional check:** `orgs/apps.py:32–50`
    (`_is_migrate_command()`: `sys.argv[1] == "migrate"`, exact position) is the *only* exemption
    from the BYPASSRLS boot guard (`apps.py:152–154`, `_check_rls_role():77–109`), whose
    docstring names start.sh's env-unset as the mechanism it trusts.
  - **The collision:** start.sh's `createcachetable` line runs under the superuser (BYPASSRLS)
    role, but the boot guard exempts only `migrate` and that line sets no
    `QUICKSCALE_ALLOW_BYPASSRLS=1` — so on a deploy without Redis, `ready()` should raise
    `ImproperlyConfigured` and the deploy fails at that step. Mechanisms 1 and 4 disagree about
    whether the same invocation is sanctioned. (Also listed under Red flags — the one-line fix is
    independent of the structural one.)
- **Why it compounds:** every new privileged operation must be hand-registered in up to three
  places (a start.sh unset line, an argv token in local's sniff, a boot-guard exemption), and
  each registration uses a different matching idiom — `createcachetable` already demonstrates a
  missed registration. Every new execution context (the DR engine's spawned `manage.py`
  subprocesses, future cron/workers, teams' data migrations) inherits whichever role its argv
  happens to imply. Built on top: the entire generated-app boot path, start.sh, both settings
  templates, and the boot guard that backstops RLS.
- **Detection signal:** deploy failures at the `createcachetable` step on no-Redis Railway
  deploys (`ImproperlyConfigured: ...BYPASSRLS...`); locally, `manage.py createcachetable` or any
  non-migrate DDL command failing with PostgreSQL permission errors under the runtime role. If
  neither has been seen, the paths are unexercised — the boot smoke test would surface both.
- **Steelman:** the fail direction is correct almost everywhere — the boot guard hard-fails on
  unexpected BYPASSRLS, production serving hard-fails without the runtime URL — so the isolation
  guarantee itself is not silently breachable; and argv-sniffing for `migrate` is a common Django
  idiom. That steelman holds for *isolation* but not for *operability*: the divergence already
  produces a deploy-breaking disagreement, and each future privileged command re-rolls the dice.
  Local's silent superuser fallback for serving also weakens the "fail direction" half in dev.
- **Correct shape:** exactly one component (the process launcher) interprets the execution
  context and publishes the privilege decision through one channel; settings files and boot
  guards *consume* the published decision and never inspect argv themselves.
- **Options:**
  1. **Launcher-owned env contract (recommended).** start.sh (and generated dev tooling —
     Makefile target or compose command — for local) sets the pair
     `RUNTIME_DATABASE_URL="" QUICKSCALE_ALLOW_BYPASSRLS=1` for its fixed list of privileged
     commands; both settings templates become pure env readers (runtime URL if set, else
     superuser URL, no argv anywhere); orgs' `_is_migrate_command()` is deleted in favor of the
     existing `QUICKSCALE_ALLOW_BYPASSRLS` hatch. One decider, one escape hatch, and the
     createcachetable defect fixes itself. Cost: bare `python manage.py migrate` in local dev
     needs the wrapper (or both URLs unset except `DATABASE_URL`) — a documented one-liner.
  2. **Generated manage.py wrapper.** Keep argv interpretation but move it to *one* owned place:
     a generated `manage.py` that maps a fixed privileged-command allowlist to the env pair
     before Django loads. Preserves `python manage.py migrate` UX exactly; adds a generated-file
     surface to maintain.
  3. **Separate settings modules.** `settings/maintenance.py` (superuser, privileged flag) vs
     serving settings; start.sh selects `DJANGO_SETTINGS_MODULE` per command; the boot guard
     keys off the settings flag. Most Django-idiomatic; most template surface and the largest
     migration for existing generated projects.
- **Recommendation:** Option 1, with Option 2's wrapper as the dev-UX sweetener if bare
  `manage.py migrate` friction proves real. This is a generator: the contract ships in templates,
  so fixing it now costs one template pass; fixing it after teams ships its own migrations and
  management commands costs a re-generation story. · **Size:** M (start.sh + two settings
  templates + orgs guard + docs + e2e) · **First step:** add `QUICKSCALE_ALLOW_BYPASSRLS=1` to
  start.sh's createcachetable line (the red-flag fix), then delete `local.py.j2`'s argv branch in
  the same PR that gives local a documented privileged-command wrapper.

---

### Finding 2: Deletion-boundary invariants are re-implemented per boundary with no domain backstop

- **ID:** `deletion-invariants-per-boundary-reimplementation`
- **Rank rationale (blast radius × likelihood):** blast is money and org integrity (orphaned live
  Stripe subscriptions, ownerless shared orgs); likelihood moderate today, rising sharply when
  teams multiplies membership-like invariants.
- **Horizon & trigger:** `deferred` — teams is not scheduled (decided 2026-07-10, see
  decisions.md §Teams module status: brainstormed placeholder only, no committed timeline), so the
  teams-build trigger is not on a clock. Live trigger regardless of teams: the first
  account-deletion path that isn't `AccountDeleteView` (a GDPR erasure command would be a second
  boundary).
- **Confidence:** High — re-verified this pass: the canonical check is consumed at all four
  callsites, and repo-wide search confirms zero `pre_delete` receivers in orgs, billing, or auth.
- **Context dependence:** wrong-for-now → wrong-regardless if/when teams kicks off.
- **Problem:** org-domain and billing-domain rules for "what must hold when a user disappears"
  are enforced only at boundaries that choose to invoke them — there is no layer every ORM
  deletion path traverses.
- **Evidence (updated):**
  - **SA47 closed the divergence half:** `OrganizationMembership.is_last_owner_with_members()`
    (`orgs/models.py:165`) is now the single semantic, consumed by the model's lock-guarded
    `delete()` (`models.py:329`), `AccountDeleteView._get_blocking_orgs_for_deletion`
    (`auth/views.py:114,147–164`), and both orgs view callsites (`orgs/views.py:808,1161`).
  - **The backstop half is unchanged:** instance `delete()` overrides do not run under the
    deletion collector, so a `User` cascade still bypasses the model rule; there is no
    `pre_delete` receiver on `User` anywhere (re-verified by search this pass). Every deletion
    boundary other than `AccountDeleteView` enforces nothing.
  - The project already names the receiver pattern as canonical for cross-module lifecycle
    behavior (`orgs/signals.py:3–9`, SA7.1).
- **Why it compounds:** cost is N deletion boundaries × M invariants; teams adds M
  (membership/ownership rules), an erasure command adds N. With SA47 the invariant count is
  honest, but each new boundary must still *remember to call* it.
- **Detection signal:** none today — instrument by alerting on `Organization` rows with zero
  OWNER memberships and on active `Subscription` rows whose org has no members.
- **Steelman:** exactly one deletion path exists today, the operator is the maintainer, and SA47
  settled the semantics. Holds only while user deletion stays single-path; the locked teams
  design breaks that assumption.
- **Correct shape:** each domain owns its lifecycle rules in exactly one place, enforced at a
  layer every ORM deletion path traverses (domain service + `pre_delete` receiver backstop);
  boundaries *invoke* the domain rather than re-implementing it.
- **Options:** unchanged from 2026-07-06 (orgs-owned deletion service + signal backstop /
  signal-only / DB-level constraints; full text in version control).
- **Recommendation:** Option 1's remaining half — a `pre_delete` receiver on `User` in orgs (and
  a billing receiver for subscription anomaly detection) that calls the SA47 check. Do it before
  teams lands its first membership-like model. · **Size:** M remaining · **First step:** the
  orgs `pre_delete` receiver, wired through the existing `signals.py` seam, with a test that
  deletes a last-owner `User` directly via the ORM (bypassing the view) and asserts refusal.

---

### Finding 4: orgs hand-enumerates the cross-module model universe in unlinked literals

- **ID:** `org-model-universe-hand-enumerated`
- **Rank rationale (blast radius × likelihood):** the enumerations back the isolation boundary's
  bookkeeping and the org-offboarding path; likelihood approaches 1 if/when a teams build lands.
- **Horizon & trigger:** `deferred` — teams is not scheduled (decided 2026-07-10, see
  decisions.md §Teams module status), so this finding is not on a teams-driven clock. It also
  fires independently on any new model added to an existing (already-shipped) module.
- **Confidence:** High — literals re-verified this pass (49 registry entries, hand-ordered
  `_DELETE_SPECS`); gates re-verified landed (SA15.3, SA45, SA49).
- **Context dependence:** wrong-for-now on the new-domain dimension, if/when teams lands.
- **Problem:** knowledge of "which models belong to an organization, and how they die" lives in
  hand-written literals inside orgs; membership staleness is now fully CI-gated, but the purge
  *order* remains hand-encoded, and the derivation inputs themselves changed semantics this delta
  without a decision record.
- **Evidence (updated):**
  - `orgs/tenancy.py:128` — `TENANT_TABLE_REGISTRY`, 49 hand-written entries (unchanged), gated
    bidirectionally against the marker-driven derivation (SA15.3).
  - `purge_organization.py:64` — `_DELETE_SPECS`, hand-ordered with comment-justified deletion
    order; the SA45 gate checks membership, not orderability — a wrong hand-ordering still
    surfaces as `ProtectedError` mid-offboarding.
  - SA49's coverage-boundary gate landed: orgs' conformance-env module list is derived from
    `quickscale_modules/*/pyproject.toml` presence, closing the one-level-up enumeration gap
    named last pass.
  - **New caution — derivation inputs moved inside housekeeping commits:** `6ea37301`
    ("fix: make check") changed `is_tenant_model()` so a truthy `tenant_excluded` marker now
    beats manager/base-class detection (`tenancy.py:1548+`), and switched the composite-FK
    template from `DEFERRABLE INITIALLY DEFERRED` to `NOT DEFERRABLE` (`tenancy.py:903`).
    Both are plausibly correct; neither has a decision record, and both alter what the Finding 4
    gates *mean* (classification semantics; FK enforcement timing during purge/restore). The
    locked child-table policy docs (decisions.md/organizations.md) don't mention deferrability.
- **Why it compounds:** every new tenant model still requires K coordinated edits (marker +
  registry literal + `_DELETE_SPECS` entry with correct position); teams multiplies the entry
  count, and purge-order correctness is the one property no gate checks.
- **Detection signal:** `ProtectedError` from `purge_organization` in any environment (ordering
  defects — still ungated); `NOT DEFERRABLE` composite-FK violations surfacing mid-purge where
  deferred checking previously masked ordering sensitivity (same signal, now stricter timing).
- **Steelman:** hand-ordered deletion is explicit, reviewable, and encodes FK subtleties naive
  traversal gets wrong; membership gates are now complete and derivation-backed. What keeps the
  finding open is the ordering half — which the `NOT DEFERRABLE` change just made *less*
  forgiving — and a teams build, if scheduled, would multiply entries.
- **Correct shape:** one derivation path from the existing sources of truth (tenant markers + FK
  topology) produces classification, RLS-conformance parametrization, and the purge plan; any
  remaining literal is a pinned snapshot CI-validated against the derivation.
- **Options:**
  1. ~~Derive the completeness gates~~ — **done** (SA15.3 + SA45 + SA49).
  2. **Derive the purge plan itself (the live option):** topological delete order from the FK
     graph restricted to org-owned models, `_DELETE_SPECS` reduced to explicit overrides. M
     effort; do it if/when teams' models land and give the derivation a real test bed — not
     time-boxed, since teams is unscheduled (decisions.md §Teams module status).
  3. **Module-contributed specs** via the manifest/`AppConfig.ready()` seam — only if a second
     consumer of per-module lifecycle knowledge appears.
- **Recommendation:** Option 2 if/when teams kicks off, unchanged; not scheduled otherwise.
  Meanwhile: record the `NOT DEFERRABLE` and `tenant_excluded`-precedence decisions in
  decisions.md (S, doc-only — they are load-bearing inputs to this finding's gates, independent
  of teams' timeline). · **Size:** M remaining · **First step:** the decisions.md entries now
  (scheduled as SA60, `why →` roadmap.md); the purge-order derivation only if/when teams' first
  models land.

---

### Fix order and interactions

1. **Finding 6's first step rides the red-flag fix** — the start.sh createcachetable line and the
   `local.py.j2` argv deletion belong in one template pass; do it before the next generated-app
   release. Independent of all other findings.
2. **Finding 1 Option 2 (persistence port)** — schedule in the next planning cycle; a future teams
   adapter should land *after* it (or accept a fourth routing workaround), but this is not gated
   on a teams timeline — teams is unscheduled. Independent of Findings 2/4/6.
3. **Findings 2 and 4** are both deferred (teams unscheduled, decisions.md §Teams module status)
   and independent of each other; Finding 2's receiver backstop is small enough to land as a
   general hardening item without waiting on teams.
4. Finding 4's doc-only sub-item (decision records for the two semantics changes) is scheduled now
   as SA60 (`why →` roadmap.md), independent of teams.

### Sound load-bearing decisions (protect these during remediation)

- **Dual-layer tenancy enforcement, re-read in full this pass:** fail-closed `TenantManager` +
  FORCE RLS with the AF9 execute-wrapper, the always-on BYPASSRLS boot guard
  (`orgs/apps.py:77–109,152–154`), and production's fail-closed serving ladder
  (`production.py.j2:185–194` — no silent superuser fallback). Finding 6's remediation must
  preserve exactly this fail direction.
- **Governance by gate — the family grew again and keeps paying:** the csrf-exempt gate's AST
  matcher was hardened (`cbde517a`), `check_module_core_compatibility.py` learned the facade's
  `__all__`/`__getattr__` shape, and SA54 added the signature-pin test class (a gate holding a
  copy pair honest). The pattern of "every hand-list gets a derivation gate" is this codebase's
  most reliable defense.
- **SA47's canonical last-owner seam:** one implementation, four consumers, lock-guarded —
  Finding 2's remaining work should extend it, not parallel it.
- **The facade split direction itself** (`runtime/dr.py` vs `runtime/manifest.py`): separating
  the manifest surface (which modules legitimately need at import time) from the DR surface
  (which triggers the cycle) is the right decomposition — Finding 1's Option 2 completes it
  rather than reversing it.
- **SA54's parameter-injection direction:** boundary-crossing invariants flowing as explicit
  call parameters (module constant → core parameter) is the correct interim shape while the
  persistence port doesn't exist.

### Watchlist

- **Shared module-runtime code has no *written* sanctioned home — sharpened, and the de facto
  answer has emerged.** The deep pass found the third shared concern the trigger was waiting
  for: per-org admin machinery (`_org_db_context` + view wrappers + fail-closed queryset). It
  resolved itself into orgs — `TenantModelAdmin`'s docstring calls itself "the generalization of
  the `PerOrgAdminMixin` pattern that social/admin.py proves works under RLS"
  (`orgs/admin.py:300`). Tally: client-IP → orgs (SA21.2), admin machinery → orgs (SA14.1),
  sanitizer → still byte-identical copies in blog+listings. Two of three concerns landing in
  orgs is a de facto "orgs is the module commons" rule with no decisions.md record · doesn't
  qualify as a finding: the seam exists and works; what's missing is the written rule and the
  sanitizer's migration — both ticket-shaped · close by writing the rule at (or before) teams
  kickoff and moving the sanitizer to orgs in the same change. Client-IP also remains
  triple-implemented across the settings templates (`base.py.j2` + `production.py.j2`
  redefinition forced by `from .base import *` layering) — distinct structural cause, watch for
  divergence.
- **String-spliced TOML editing — sharpened, holding condition broken.** The 2026-07-06 steelman
  rested on "`_write_validated_toml` re-parses before writing, so corruption fails loud." The new
  `_patch_module_path_dependencies` (`module_dependency_sync.py:345–427`, landed `198a1951`)
  writes module pyproject.toml files with bare `write_text()` (`:425–427`) — no validation. The
  one-line fix is a red flag below; the watch is the pattern: three splice functions and growing
  per-module dependency knowledge (`_STORAGE_CLOUD_BACKENDS`) · promotes on the fourth splice
  site or any corruption incident.
- **Billing webhook concurrent-duplicate window** — carried; `billing/services.py` verified
  untouched since 2026-07-07 · promotes when any non-idempotent side effect lands in a handler.
- **Dual child-table tenancy APIs — sharpened.** Carried, plus this delta changed the
  composite-FK API's SQL semantics (`NOT DEFERRABLE`, `tenancy.py:903`) inside a housekeeping
  commit (see Finding 4's caution) · promotes if any teams child table lands on the trigger API.
- **Mutating CLI operations have divergent compensation mechanisms — broadened from the
  apply-regeneration item.** The deep pass's first-ever read of `remove_command.py` (785 lines)
  found a third mechanism: hand-rolled `PathSnapshot` rollback with snapshots in a
  `TemporaryDirectory` (`remove_command.py:279–317,636`) — exception-safe but not crash-safe,
  same class as SA22's regeneration recovery. The update path's git-commit-per-module is a
  fourth strategy. Cross-mechanism glue already exists:
  `_build_updated_apply_recovery_state` (`remove_command.py:206–228`) hand-reconciles remove's
  mutations against the apply ledger's pending snapshots, with dedicated e2e tests
  (`test_module_lifecycle_cycle.py:510`) · doesn't qualify yet: each mechanism fits its
  operation's shape, all are exception-safe, advisory-locked, and the generated project is a
  user-owned git repo (the universal undo) · promotes on the next piece of cross-mechanism
  reconciliation glue, a new mutating command hand-rolling a fifth mechanism, or any
  crash-mid-operation report git couldn't recover.
- **`orgs/views.py` fusion** — carried; 1,226 lines post-SA50-fold · promotes when teams begins
  extending org-facing surfaces.
- **Grandfathered option defaults multi-sourced — fifth consecutive pass; tax paid again.** The
  new listings configurator (`module_config.py:864–899` + registry entry `:2077`) added
  `listings_per_page` across the manifest pair, `entry_point.py`, the CLI defaults, and the
  views consumer — the coordination stations were all paid correctly, which is the tax working,
  not failing. T2.4/T2.5 remain unscheduled with the roadmap now empty · promotes when a default
  changes in one station only, or if/when teams kicks off (unscheduled — not a near-term trigger).
- **Deploy-time configuration contract for generated apps — narrowed.** The privilege-selection
  half promoted to Finding 6; what remains is the broader class (a settings-template requirement
  discovered per-instance instead of asserted by a template test — TA33's class) · still cheapest
  as the tech-audit's boot smoke test plus a one-paragraph decisions.md rule.

*(Carried unchanged at low priority, unprinted: hardcoded `EXEMPT_PATH_PREFIXES` in
`orgs/middleware.py`. The `_is_migrate_command()` argv-sniffing item is no longer carried
separately — it is Finding 6's Mechanism 4.)*

### Teams landing checklist (carried forward, updated — speculative, teams unscheduled)

> Teams is not scheduled (decided 2026-07-10, see decisions.md §Teams module status). This
> checklist is kept for reference *if* a future scheduling decision puts teams on the roadmap —
> it is not an implication that teams is imminent.

Declarative manifest path (freeze enforces) · `TenantModel` base + markers for every model ·
`TenantModelAdmin` for its admin · own module for views (not `orgs/views.py`) ·
notifications-PII exclusion review at kickoff · membership/ownership invariants go into the
SA47 seam (and its coming `pre_delete` backstop), not into views · background work reuses the
`dispatch_background_*` service pattern · teams' app enters orgs' cross-module test env in the
same PR as its first model (SA49 gate now derives the expected list — it will fail loudly) ·
endpoints subclass `OrgApiBaseView`/the DRF baseline per decisions.md
§json-api-endpoint-base-contract; a teams webhook adds its verifier to the SA46 gate ·
client-IP/attribution uses `current_org.get_client_ip`; a third shared-runtime helper triggers
the commons decision · **new:** the teams *adapter* imports `quickscale_core.runtime.manifest`
only (never the combined facade), and lands after Finding 1's persistence port if scheduling
allows · **new:** teams data migrations and management commands must not assume a DB role from
argv — they traverse Finding 6's seam; land them after the mode contract · **new:** teams'
admin subclasses `TenantModelAdmin` — never a `PerOrgAdminMixin`-style local prototype (see the
social red flag).

### Module-by-module deep pass (2026-07-09, core and cli included as modules)

**Zero new findings promoted.** First-ever full reads this pass: the entire social module
(models, services, contracts resolution surface, admin), `storage/helpers.py`,
`remove_command.py`, `runtime/dr.py` + `runtime/__init__.py`, `dr_engine/_sidecar.py` (diff
depth). Candidates investigated and *not* promoted, each with its holding gate and breaking
trigger:

1. **billing: auth enforced per-handler in the sanctioned DRF baseline.** Every SA56-migrated
   POST view declares `permission_classes = [AllowAny]` + `SessionAuthentication` and opens with
   a manual `if not request.user.is_authenticated: return 401` preamble
   (`billing/views.py:171–330`) — procedural where `IsAuthenticated` (or a custom permission
   returning the legacy 401 body) would be structural. **Held by:** per-view tests assert the
   401s; the contract-preserving motive is legible. **Breaks if:** a new billing endpoint omits
   the two-line preamble — then centralize via a shared permission class and reopen Finding 5's
   reopen-condition review.
2. **social: missing-table tolerance by exception-message matching.**
   `_is_missing_social_table_error` (`services.py:74–89`) string-matches Postgres/SQLite
   "relation does not exist" texts — the shape SA44 deleted from core's entry point. **Held by:**
   narrow exception types (`OperationalError`/`ProgrammingError` only), exact
   table-name matching, re-raise on non-match (permission errors stay fail-hard), and a real
   deploy-window rationale (public link tree between code rollout and migrate). **Breaks if:**
   the pattern spreads to another module or the matcher loosens — then replace with an
   app-registry/migration-state check.
3. **backups: restore-attempt-not-an-entity — carried, trigger re-checked, did not fire.**
   SA53's "blocked restore checkpoint" added no lifecycle state (`BackupArtifact` status set
   unchanged, re-verified `models.py:89–101`); the work was crash-safe copy mechanics
   (mkstemp + fd-writes + fsync + `os.replace`) and consolidated cleanup — sound. Watch
   condition unchanged (promote when restore grows queueing/progress/cancellation states).
4. **cli: remove/apply/update compensation divergence** — promoted into the broadened watchlist
   item above, not to a finding (git-repo backstop + advisory lock + single-process context).
5. **core: `normalize_notifications_module_options` empty→manifest-defaults materialization**
   with a lazy import to dodge a contracts-internal cycle (`module_options.py:555–563`) —
   in-package, function-level, ticket-shape at most; watch only if the contracts↔resolvers
   cycle grows more lazy-import sites.

Per-module verdicts:

- **quickscale_core** — Finding 1 evidence updated (adapter shim round-trip removed; facade
  split landed with the new `__all__` station). New red flag: the DR media-path silent-local
  coercion (two sites, `6ea37301`). `apply/`, `project_state.py`, manifest loader verified
  untouched since the 2026-07-06 deep read — prior candidates carry unchanged.
- **quickscale_cli** — `remove_command.py` read in full for the first time: confirmation prompt,
  advisory lock, snapshot/rollback, ledger-reconciliation glue — disciplined but a third
  compensation mechanism (watchlist). Dependency-sync TOML red flag recorded in the delta pass.
  Lifecycle e2e tests assert the right invariants (removed modules don't resurrect through
  pending recovery). The listings configurator paid the option-pipeline tax correctly.
- **orgs** — load-bearing seams (`middleware.py`, `current_org.py`, `managers.py`) churn-free
  since the already-reconciled SA21.2/SA48. `TenantModelAdmin` read in full: fail-closed,
  RLS-primed via `org_scope`, VIEW-AS + org-field locking — sound; it is the sanctioned home of
  the per-org admin pattern (see social red flag for the straggler prototype).
- **social** — first-ever deep read; disciplined overall: `tenant_org_fk` + dual managers,
  org-partitioned cache keys with old-org invalidation (CR-T1-9-001), provider allowlists
  enforced in `clean()`, embed "resolution" is pure URL derivation (no network in `save()` —
  verified against contracts.py imports). Two items: the missing-table classifier (candidate 2)
  and the admin prototype (red flag).
- **storage** — helpers are fail-hard (`ImproperlyConfigured` on missing/invalid backend
  setting) but expose no "is storage active in this runtime?" query, which is why DR callers
  resorted to blanket excepts — note for the red-flag fix.
- **backups** — SA53/SA54 read in full; sound (candidate 3). Services file is 650 lines of
  sanctioned module-side lifecycle; header contract now accurate (SA51).
- **billing** — SA56 migration verified real (DRF `APIView`s, webhook `csrf_exempt` remains the
  SA46-gated exception); candidate 1 recorded. `services.py` untouched since SA41.
- **auth** — re-read; Finding 2 territory unchanged (module-top orgs import, function-level
  billing import behind a settings check).
- **blog / listings** — type-annotation churn only; SA26 sanitizer copies carried (commons
  watchlist). Listings admin on `TenantModelAdmin` (verified).
- **crm / notifications / analytics** — churn-free since SA35/make-check test-only additions;
  spot-checked, nothing new. CRM admin on `TenantModelAdmin` (verified).
- **forms** — still on the manager-idiom (`TenantManager` + `tenant_org_fk`, no `TenantModel`
  base; re-verified `models.py:45–74,135–155`) — the 2026-07-04 ticket-shaped port remains
  pending and is now the *second* straggler-idiom instance alongside social's admin.
- **teams** — README-only placeholder (re-verified).

### Questions that would change the ranking

- **T2.4/T2.5 and the teams build — answered 2026-07-10.** Decided: teams is **not next, not
  planned** — `quickscale_modules/teams/` is a brainstormed placeholder only, with no committed
  scoping or timeline (see decisions.md §Teams module status). Findings 2 and 4 are accordingly
  `deferred` rather than `6–18 months`, and Finding 1 Option 2 is scheduled on its own
  merits (next planning cycle) rather than as a pre-teams gate. Re-open this question only when a
  future scheduling decision actually puts teams on the roadmap.
- **Was `NOT DEFERRABLE` a deliberate policy change for the composite-FK child-table API?**
  (Affects Finding 4's purge-order risk and the locked Option C child-table policy.) If
  deliberate, one decisions.md paragraph closes the caution; if incidental to making `make check`
  pass, it deserves review before the next migration ships.
- **Is `local.py.j2`'s argv ladder intended as the local contract, or a stopgap for compose/e2e?**
  (Affects Finding 6's option choice — a deliberate "local is argv-driven" answer argues for
  Option 2's owned wrapper over Option 1's pure-env contract.)

### Red flags (out of scope — fix now)

- **DR media path silently coerces storage failures to "local" — two sites, data-loss-shaped.**
  `6ea37301` changed `_sidecar.py`'s `_build_media_sync_manifest` and `orchestration.py`'s
  `_resolve_media_runtime` from fail-loud (`status: "unsupported"` / `BackupConfigurationError`)
  to `except Exception: selection = None` → treat as local backend. `storage.helpers.
  select_storage_backend` raises the *same* `ImproperlyConfigured` for "module not installed"
  (local is correct) and "backend misconfigured" (must fail), so the blanket except conflates
  them: an S3 project whose selection fails at capture writes a `status: "ready"` manifest with
  a local (likely empty) inventory, and `sync_backup_snapshot_media` — which hard-rejects
  non-"ready" manifests — proceeds on wrong premises; restore verification passes with all
  remote media missing. Fix: distinguish module-absence (app-registry check or
  `ImportError`-only except) from selection errors, which stay fail-hard. This is the
  fail-hard-audit class (tech-audit SSOT) — hand off as a TA item.
- **Social's admin still runs the `PerOrgAdminMixin` prototype that `TenantModelAdmin`
  generalized** (`social/admin.py:112–262` vs `orgs/admin.py:240–330`): near-duplicate
  isolation-critical machinery, and drift is already real — social's copy lacks the VIEW-AS
  debug-session priority and the org-field form locking the generalized base has. Port social
  onto `TenantModelAdmin`, delete the prototype (same shape as the SA14.2/SA14.3 ports).
- **start.sh's `createcachetable` step runs under the superuser but the boot guard only exempts
  `migrate`** (`start.sh.j2:59` vs `orgs/apps.py:152` — no `QUICKSCALE_ALLOW_BYPASSRLS=1` on the
  line): the no-Redis deploy path should fail with `ImproperlyConfigured` at first boot. One-line
  fix; also Finding 6's collision evidence. Needs runtime confirmation.
- **`_patch_module_path_dependencies` writes pyproject.toml without validation**
  (`module_dependency_sync.py:425–427`) — route it through `_write_validated_toml` like its two
  siblings.
- **Test artifacts are git-tracked and accreting:** 13 generated PNGs under
  `quickscale_modules/blog/tests/media/blog/uploads/2026/07/` (one more added per CI-fix commit)
  and `pytest_log.txt` at the repo root (modified by `198a1951`). Point test `MEDIA_ROOT` at a
  temp directory, untrack the files, and gitignore both.
- **Two tenancy-semantics changes landed inside housekeeping commits with no decision record**
  (`NOT DEFERRABLE`, `tenant_excluded` precedence — both in `6ea37301` "fix: make check"). The
  code may be right; the record is missing. One decisions.md entry each.

Lenses scanned with no qualifying finding this pass: data/state integrity beyond Finding 4's
caution, trust boundaries beyond Finding 6 (boot guard re-read in full — fail direction sound),
module cohesion beyond Findings 1/6, consistency/failure models (SA53's checkpoint/retry work
read — sound at code level), observability, API contracts (Finding 5 verified still closed — no
new endpoint idiom in the delta), testing architecture (the new gate work is the right kind),
design conflicts beyond Finding 6, concurrency, security architecture (copies → watchlist),
build/supply chain (pip-audit gap remains a tech-audit tooling item), performance.

---

## Autopsy — 2026-07-07 (re-run, delta pass)

> Superseded by the 2026-07-09 delta pass above, which re-verified all open findings' evidence
> anchors directly and read the SA47–SA56 closeout plus the 2026-07-09 make-check/make-ci delta
> in full. This stub heading is kept so existing links resolve.

---

## Autopsy — 2026-07-06 (re-run) and module-by-module deep pass

> Superseded by the 2026-07-07 delta pass, which re-verified all four open findings'
> evidence anchors directly and read the full SA34–SA46 closeout delta. The 2026-07-06 passes'
> full text (three findings opened at the repo level, two more from the module deep pass, five
> steelmanned candidates, per-module verdicts) is preserved in version control. This stub heading
> is kept so existing links resolve.

---

## Autopsy — 2026-07-04 (re-run) and module-by-module deep pass

> Superseded by the 2026-07-06 re-run. The 2026-07-04 passes' full text (orientation,
> zero-findings result, five steelmanned candidates, per-module verdicts) is preserved in version
> control. This stub heading is kept so existing links resolve.

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
- 2026-07-07 (re-run, delta pass over the SA34–SA46 closeout batch) — **all four findings
  still-open, zero new findings.** `dr-engine-module-circular-lattice`: still-open,
  **strengthened** — CR-SA38-001 hand-copied the module-side stale-restore guard
  (`services.py:524–557`) into `orchestration.py:2799–2818` with a literal 30-minute threshold and
  duplicated message strings because core cannot import module services; second dated instance of
  the coordination tax in four days; `services.py` header ("under 400 LOC, features go in
  dr_engine/") now contradicts both reality (620 lines) and the correct extraction direction the
  SA43 batch took. `deletion-invariants-per-boundary-reimplementation`: still-open, evidence
  unchanged (divergent last-owner copies intact, zero `pre_delete` receivers re-verified); SA41
  and SA35 hardened the existing boundary without giving invariants a domain owner; SA47 ready.
  `org-model-universe-hand-enumerated`: still-open, **narrowed with a correction** — the
  2026-07-06 claim that `TENANT_TABLE_REGISTRY` lacked a derivation check was inaccurate (SA15.3's
  `test_doc_consistency.py` bidirectionally cross-checks the literal against the marker-driven
  derived view; both Option 1 halves are therefore done); remaining scope is Option 2 (purge-order
  derivation) plus a newly named coverage boundary: every derivation gate sees only the 9-of-13
  modules hand-listed in `orgs/tests/settings.py:34–42`. `json-api-boundary-idiom-fragmentation`:
  still-open, **progressed** — SA46's csrf-exempt pairing gate landed as a blocking CI job
  (`ci.yml:206–231`), closing the silent-miss class; the three idioms remain in code; remaining
  scope is the `OrgApiBaseView` fold + a decisions.md rule + opportunistic billing migration.
  Watchlist: **new** item — shared module-runtime code has no sanctioned home (SA21.2 put
  client-IP into orgs' tenant-context module; SA26's sanitizer is byte-identical copies in
  blog+listings); six items carried delta-verified-untouched. Prior red flags reconciled:
  `BillingValidationError` swallow → **fixed** (SA41, distinct `BillingSubscriptionAnomalyError`
  logged); post-hook coercion defaults → **tracked** (SA42 scheduled, no longer re-flagged). New
  red flags: `_get_manage_py()` silent fallback to bare `"manage.py"`; SA21.2 helper's
  `getattr`-default settings reads; stale `services.py` header contract. Questions updated: the
  registry-retirement question is partially answered in code ("temporary SSOT … eventually
  replace"); T2.4/T2.5 hits its fourth unanswered pass with the teams boundary now imminent.
- 2026-07-07 (roadmap cleanup) — **progress recorded on all four open findings; none closed.**
  `dr-engine-module-circular-lattice`: SA44 (Option 1, stage 1) **landed** — the string-matching
  classifier is deleted and adapter registration is explicit; the finding stays open, Option 2
  (persistence port) is unscheduled and remains the next trigger (the CR-SA38-001 copy-pair is
  untouched by SA44, as noted when SA44 was scheduled). `deletion-invariants-per-boundary-reimplementation`:
  SA47 (first step) **landed** — the three divergent last-owner implementations are now one
  canonical `OrganizationMembership.is_last_owner_with_members()` with lock-guarded concurrent-deletion
  protection; the finding stays open pending a `pre_delete` receiver backstop and the teams build.
  `org-model-universe-hand-enumerated`: SA49 (coverage-boundary sub-item) **landed** — orgs'
  conformance-env module list is now CI-derived from `quickscale_modules/*/pyproject.toml`
  presence instead of hand-listed; the finding stays open pending Option 2 (purge-order
  derivation), scoped for teams kickoff. `json-api-boundary-idiom-fragmentation`: SA55 (the
  decisions.md rule) **landed** — `§json-api-endpoint-base-contract` now names the two sanctioned
  bases and schedules billing's migration (SA56) rather than grandfathering it; the finding stays
  open pending the `OrgApiBaseView` fold (SA50, open on Track 1) and the billing migration (SA56,
  open on Track 3). Red flags reconciled: `_get_manage_py()` silent fallback → **fixed** (SA52);
  SA21.2 helper's `getattr`-default settings reads → **fixed** (SA48); stale `services.py` header
  contract → **fixed** (SA51) — all three removed from the Red flags section, detail in
  CHANGELOG.md and tech-audit.md (TA42/TA43/TA44). Full narrative re-verification of Findings
  1/2/4/5's evidence prose is deferred to the next full autopsy re-run; this entry records what
  changed since the 2026-07-07 delta pass above without rewriting it.
- 2026-07-08 (docs cleanup, continued) — Finding 5 (`json-api-boundary-idiom-fragmentation`): **closed.**
  SA50 landed since the 2026-07-07 entry (SA55 already recorded). SA56 billing migration **completed
  2026-07-08** — all four plain-View endpoints migrated onto the DRF baseline. The blog dual-auth
  function-view path (`@_typed_csrf_exempt` + `authenticate_blog_api_request`) was not migrated — it was
  validated as a narrow documented bounded exception in decisions.md §json-api-endpoint-base-contract,
  matching the SA46 gate's existing treatment of `authenticate_blog_api_request` as an approved verification
  helper. All Finding 5 sub-items are resolved (SA46 gate, SA50 fold, SA55 rule, SA56 migration plus
  the bounded-exception documentation). Finding 5 is now closed. Summary table size updated from M to S
  on the prior entry, now marked closed.
- 2026-07-09 (re-run, delta pass over SA47–SA56 closeout + the 2026-07-09 make-check/make-ci
  commits) — **three findings still-open, one new finding, Finding 5 verified still closed.**
  `dr-engine-module-circular-lattice`: still-open, **progressed and re-strengthened** — the
  `runtime/` facade split landed (`dr.py`/`manifest.py`, Option 1 complete) but the combined
  facade added a hand-synced literal `__all__` union station (`runtime/__init__.py:42–105`), the
  social adapter had to route around the facade via a new `LEGACY_ALLOWED_IMPORTS["social"]`
  entry (`check_module_core_imports.py:77–81`) — the shrink-only list grew, and the linter now
  calls "legacy" the import the facade docstring recommends; SA54 deduplicated the stale-restore
  threshold as a parameter seam with a signature-pin test (right interim direction; the copy pair
  persists in gated form). Recommendation escalated: schedule Option 2 (persistence port) in the
  next planning cycle. **New Finding 6 `db-privilege-mode-procedural`**: DB-privilege selection
  has four mechanisms with three semantics (start.sh env-unset; production argv-membership
  ladder; local argv-switching ladder, new in `198a1951`; orgs positional argv boot-guard
  exemption); live source-level collision — start.sh's `createcachetable` runs under the
  superuser with no boot-guard exemption (no-Redis deploys should fail; red-flagged).
  `deletion-invariants-per-boundary-reimplementation`: still-open, **narrowed** — SA47's
  canonical check verified consumed at all four callsites; zero `pre_delete` receivers
  re-verified; remaining scope is the receiver backstop + teams.
  `org-model-universe-hand-enumerated`: still-open — literals intact (49 registry entries,
  hand-ordered `_DELETE_SPECS`), SA49 gate verified; **new caution:** `is_tenant_model()` gained
  `tenant_excluded` precedence and the composite-FK template switched to `NOT DEFERRABLE`, both
  inside housekeeping commits with no decision record. Watchlist: commons item sharpened
  (client-IP now ×3 counting the base/production template copies forced by settings-layering);
  TOML-splicing item sharpened (holding condition broken — new `_patch_module_path_dependencies`
  writes without validation; red-flagged); dual child-table API sharpened (`NOT DEFERRABLE`);
  billing-webhook/apply-regeneration/orgs-views-fusion carried verified-untouched;
  grandfathered-defaults carried (fifth pass, tax paid correctly on the new listings
  configurator); deploy-config item narrowed (privilege half promoted to Finding 6);
  `_is_migrate_command` unprinted item absorbed into Finding 6. New red flags: start.sh
  createcachetable BYPASSRLS collision; unvalidated TOML write; git-tracked accreting test
  artifacts (13 blog-upload PNGs + `pytest_log.txt`); two undocumented tenancy-semantics changes.
  Questions: T2.4/T2.5+teams (fifth pass, roadmap now fully drained); `NOT DEFERRABLE`
  deliberateness; local argv ladder intent.
- 2026-07-09 (module-by-module deep pass, core and cli included as modules) — **zero new
  findings promoted.** First-ever full reads: the social module end-to-end, `storage/helpers.py`,
  `remove_command.py`, `TenantModelAdmin` in `orgs/admin.py`. Five candidates investigated and
  held with recorded gates/triggers: billing per-handler auth preamble in the sanctioned DRF
  baseline; social's missing-table exception-message classifier (narrow, fail-hard on
  non-match); backups restore-attempt-not-an-entity carried — SA53 added crash-safe copy
  mechanics, not lifecycle states, so the trigger did not fire; CLI compensation-mechanism
  divergence (remove's `PathSnapshot` + ledger + SA22 + update's git-commits, with
  cross-mechanism reconciliation glue already present) — broadened the apply-regeneration
  watchlist item rather than promoting; core contracts-internal lazy-import cycle (ticket-shape).
  Finding 1 evidence **corrected in the finding's favor**: `6ea37301` repointed
  `dr_engine/adapter.py`'s lazy imports off the module shim onto orchestration directly — one
  cycle edge removed. Commons watchlist item resolved its own question: the third shared
  concern (per-org admin machinery) landed in orgs (`TenantModelAdmin` is the documented
  generalization of social's prototype), making "orgs is the module commons" the de facto rule —
  remaining work is writing it down and migrating the SA26 sanitizer copies. New red flags: DR
  media-path silent-local coercion (two sites in `6ea37301`, data-loss-shaped, fail-hard-audit
  class — hand off to tech-audit); social admin still on the ungeneralized `PerOrgAdminMixin`
  prototype with real drift (no VIEW-AS, no org-field locking). Straggler-idiom tally now two:
  forms (no `TenantModel` base, re-verified) and social admin. Periphery
  (crm/notifications/analytics/blog/listings) verified churn-free or type-only since reconciled
  SAs; teams still README-only.
