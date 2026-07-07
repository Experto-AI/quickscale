# Structural Autopsy: QuickScale

> This file is regenerated on each autopsy run to state **present reality for planning**: the
> current orientation, the open findings in full detail, and a curated watchlist. Closed findings
> exist only as dated lines in the **Reconciliation log** at the bottom (closeout detail lives in
> [CHANGELOG.md](../../CHANGELOG.md)); version control preserves prior full text. Finding IDs are stable
> across runs.

---

## Autopsy — 2026-07-07 (re-run, delta pass)

### Orientation (2026-07-07)

QuickScale is a solo-maintained (Experto-AI/Victor Rocco) Python 3.13/3.14 + Poetry monorepo
(VERSION 0.86.0, integration branch `v87`) that generates user-owned Django 6 SaaS projects:
`quickscale_cli` (Click: plan/apply/dr/deploy), `quickscale_core` (Jinja2 generator, plan/apply
engine with the 16-step recovery ledger, manifest/contracts/derivation stack, DR engine), and 13
shipped Django modules under `quickscale_modules/` (teams still an empty placeholder — README
only, re-verified). Generated apps: Django 6 + PostgreSQL 18, single-service Railway; tenancy
enforced twice (fail-closed `TenantManager` + FORCE RLS with the AF9 execute-wrapper). **This is a
delta pass one day after the 2026-07-06 re-run + module deep pass**: the SA34–SA46 closeout batch
(~6,900 insertions since `3056186a` — SA21.2, SA34–SA41, SA43, SA45, SA46 gate) landed in between,
and this pass read that delta in full plus re-verified every open finding's evidence anchors
directly in code. Read fully — the entire `3056186a..HEAD` diff for backups
`services.py`/`admin.py` (SA37/SA38/SA43 dispatch extraction), `dr_engine/orchestration.py`
(CR-SA38-001 parity block), auth `views.py` + billing `services.py` (SA41),
orgs `current_org.py` (SA21.2 client-IP seam, SA39 guard), blog/forms client-IP consumers,
`scripts/check_csrf_exempt_gate.py` header + its CI wiring, `test_doc_consistency.py` (SA15.3
registry cross-check, re-read in full — see Finding 4 correction), the SA45 purge-spec derivation
test, roadmap/tech-audit in full. Sampled — SA35 conformance test, SA26 sanitizer copies
(byte-diffed blog vs listings), start.sh/base.py template diffs. Skipped — everything untouched
since yesterday's deep pass (verified by diffstat: `apply_command.py`, `orgs/views.py`,
`tenancy.py` trigger APIs, billing webhook phases all unchanged). Severity floor unchanged: CLI is
a single-process local tool; generated apps are single-service WSGI; tenant isolation is the
highest-blast property. Growth direction unchanged: teams is the next build; the roadmap now has
exactly four open items (SA47, SA44, SA42, SA46-residual), all first steps of the findings below.

**Result: all four prior findings still open, zero new findings.** Finding 1 is *strengthened*
(the batch paid its coordination tax again — CR-SA38-001 hand-copied a module-side guard into
core), Finding 4 is *narrowed with a correction* (the prior pass under-credited SA15.3's existing
registry derivation gate), Finding 5 *progressed* (SA46's pairing gate is live and CI-blocking).
One new watchlist item: shared module-runtime code has no sanctioned home.

### Summary table

| # | ID | Horizon | Size | One-line problem |
|---|----|---------|------|------------------|
| 1 | `dr-engine-module-circular-lattice` | now | M remaining (Option 2; stage 1/SA44 landed 2026-07-07) | DR logic lives in core but its state and lifecycle live in the backups module, producing a bidirectional import lattice held together by hand-maintained symbol tables, a string-matching exception classifier — and now hand-copied parity guards across the boundary |
| 2 | `deletion-invariants-per-boundary-reimplementation` | 6–18 months (teams) | M remaining (receiver backstop + billing seam; first step/SA47 landed 2026-07-07) | Org/billing invariants at the account-deletion boundary are re-implemented per callsite with divergent semantics instead of being owned by their domain modules |
| 4 | `org-model-universe-hand-enumerated` | 6–18 months (teams) | M remaining (Option 2) | orgs hand-enumerates the cross-module tenant-model universe in literals; both literals are now CI-gated against derivations (SA15.3 + SA45), but the purge plan is still hand-ordered and every gate sees only what orgs' hand-maintained test env installs |
| 5 | `json-api-boundary-idiom-fragmentation` | 6–18 months (teams) | M remaining (fold + migration) | Three coexisting idioms for authed state-changing JSON endpoints; the silent-hole class is now closed by the SA46 CI gate, but the three templates remain and teams needs the one it should copy |

---

### Finding 1: DR domain is split across the core↔module boundary into a circular import lattice

- **ID:** `dr-engine-module-circular-lattice`
- **Rank rationale (blast radius × likelihood):** every DR feature crosses this seam — likelihood
  is now empirically ~1 per DR change: SA20 paid it (guard-allowlist growth), and this batch paid
  it again (CR-SA38-001 hand-copy). Failure containment remains a fragile exception-message
  classifier on the startup path of every generated app.
- **Horizon & trigger:** `now` — SA44 (stage 1) is an open, ready roadmap item; any DR feature
  before it lands pays the tax again.
- **Confidence:** High — every edge of the cycle re-verified this pass
  (`entry_point.py:1436–1511` classifier + import-time registration intact;
  `runtime.py:152–272` lazy tables intact), and the new compounding instance was read directly.
- **Context dependence:** wrong-regardless — the coordination tax is paid today, at current scale,
  by a solo maintainer; it fired twice in four days.
- **Problem:** the DR engine's logic was extracted into core while its persistent state
  (`BackupArtifact`, `BackupPolicy`) and its Django-facing entry points stayed in the backups
  module — so neither side can import the other top-down, and the system holds the resulting cycle
  together with lazy-loading tables, a re-export shim, and message-text exception matching instead
  of fixing the topology.
- **Evidence:**
  - **New this pass — the lattice forced a hand-copied invariant.** SA38's stale-restore
    detection lives module-side as the canonical implementation
    (`backups/services.py:524` `STALE_RESTORE_THRESHOLD_MINUTES = 30`, `:535 is_restore_stale()`,
    `:560 reset_stale_restore()`), consumed by the admin at four callsites. Core's uploaded-file
    dry-run path needed the same guard, and because core cannot import module services,
    `dr_engine/orchestration.py:2799–2818` carries an **inline hand copy** — a literal
    `timedelta(minutes=30)` plus duplicated message strings, with a comment declaring "parity with
    prepare_admin_uploaded_restore_artifact (services.py)." Change the threshold or the guidance
    text and one side silently drifts. This is the coordination tax firing on a *defect fix*, not
    a feature.
  - **The boundary contract is now stated in two contradictory places.** `services.py:1–10` still
    declares "intentionally under 400 LOC. Every new orchestration feature should go in
    `dr_engine/`, not here" — while the SA43/SA37/SA38 extractions (correctly) grew the file to
    620 lines of Django-model/Popen lifecycle (`_atomic_claim_restore:232`,
    `dispatch_background_restore:378`, `dispatch_background_create:458`, `:496 prune`,
    `reset_stale_restore:560`). The direction the batch took is the right one (model-touching
    lifecycle belongs module-side); the header codifies the opposite rule.
  - Core → module (unchanged): `dr_engine/orchestration.py:80` imports
    `quickscale_modules_backups.models` at module level; `dr_engine/adapter.py` (14+
    function-level imports) round-trips through the module shim back into core.
  - Module → core (unchanged): `backups/services.py:19–129` re-exports ~80 names from
    `quickscale_core.runtime` with `# noqa: F401`, dozens underscore-private; its protocols are
    placed there "to avoid circular imports."
  - The "facade" (unchanged): `runtime.py:152–272` — four hand-written frozensets with a
    `__getattr__` lazy loader whose stated reason is the cycle itself.
  - The guard (unchanged): `manifest/entry_point.py:1436–1462` classifies benign-vs-broken adapter
    imports by string-matching CPython's exception text; `:1511`
    `_initialize_managed_adapters_at_import()` still runs at import time. SA44 (open, Track 3,
    ready) is scoped to exactly this.
  - The linter still cannot see it: `scripts/check_module_core_imports.py` allows
    `quickscale_core.runtime` by module path only, so private-name crossings are invisible.
- **Why it compounds:** every DR feature touches up to six stations — orchestration function +
  runtime lazy table + `__all__` + services shim + adapter signature + (for new import paths) the
  entry-point guard allowlist — and, as of this batch, any *behavioral invariant* needed on both
  sides of the boundary becomes a hand-synchronized copy pair. Built on top: all backups
  management commands, the admin restore/create/prune flows (now all async-dispatched through the
  module-side service), the DR CLI, and apply/deploy DR integration.
- **Detection signal:** recurrence of the SA20 startup-failure class (`ImproperlyConfigured` from
  `refresh_managed_adapters` during startup after adding an import); growth of the classifier
  allowlist or `_LAZY_*` tables in a diff; **new:** any diff that edits a stale-restore string or
  threshold on one side of the boundary only.
- **Steelman:** the extraction direction was right, lazy `__getattr__` is a standard pattern, and
  generated apps ship backups+core together so the cycle never bites end users at runtime. That
  held for two passes; SA20's guard growth killed it, and CR-SA38-001's copy-pair confirms the
  kill — the steelman now fails on evidence twice over.
- **Correct shape:** imports across the core↔module boundary form a DAG (modules → core only);
  adapter/module registration is an explicit runtime act, not an import-time side effect; no
  underscore-private name crosses a package boundary; a boundary-crossing invariant (like restore
  staleness) has exactly one implementation.
- **Options:**
  1. **Registration-not-import + facade split (SA44, scheduled — recommended first stage).**
     Replace `_initialize_managed_adapters_at_import()` with explicit registration; delete the
     string-matching classifier; split `runtime.py` into `runtime.dr` and `runtime.manifest`.
     Removes the fragile classifier and the cross-domain trigger; does not yet remove core→module
     imports or the copy-pair problem.
  2. **Persistence port.** Core defines protocols for artifact/policy persistence; the backups
     module implements and injects them at app-ready. Kills `orchestration.py:80`'s model import
     and the lazy tables' reason to exist — and gives the stale-guard one home (module-side, with
     core receiving it via the port). M–L effort.
  3. **Invert ownership.** Move all Django-model-touching orchestration into the backups module;
     core keeps only pure primitives. Largest migration; complicates the CLI's non-Django DR paths.
- **Recommendation:** land SA44 (Option 1) now — it is scheduled and unblocked. The CR-SA38-001
  copy-pair is the first concrete evidence for escalating to Option 2: do it the next time a DR
  feature must either add lazy-table symbols *or* duplicate an invariant across the boundary.
  · **Size:** M (stage 1) · **First step:** SA44 as written in roadmap.md — move managed-adapter
  registration out of import time, delete the classifier; `test_manifest_entry_point.py` becomes
  the regression harness.

---

### Finding 2: Deletion-boundary invariants are re-implemented per boundary with divergent semantics

- **ID:** `deletion-invariants-per-boundary-reimplementation`
- **Rank rationale (blast radius × likelihood):** blast is money and org integrity (orphaned live
  Stripe subscriptions, ownerless shared orgs); likelihood moderate today, rising sharply when
  teams multiplies membership-like invariants.
- **Horizon & trigger:** `6–18 months` — the teams build; second trigger: the first
  account-deletion path that isn't `AccountDeleteView` (a GDPR erasure command would be a third
  boundary). SA47 (first step) is open and ready on Track 1.
- **Confidence:** High — all implementations re-verified this pass: the two divergent last-owner
  copies are intact, and repo-wide search confirms zero `pre_delete` receivers in orgs, billing,
  or auth.
- **Context dependence:** wrong-for-now → wrong-regardless at teams kickoff; the dimension is the
  new feature domain plus any compliance-driven deletion path.
- **Problem:** org-domain and billing-domain rules for "what must hold when a user disappears"
  have no domain owner — each deletion boundary re-implements them, and the two implementations
  that exist disagree.
- **Evidence:**
  - `orgs/models.py:231–252` (`OrganizationMembership.delete()`): lock-guarded
    (`select_for_update` on the org), raises unconditionally when the last owner would be removed —
    but instance `delete()` overrides do not run under the deletion collector, so a `User` cascade
    bypasses it.
  - `auth/views.py:86,115` (`AccountDeleteView._get_blocking_orgs_for_deletion`): re-implements
    the rule *differently* — deletion allowed when the org has no other members, no row locks,
    billing knowledge inline. auth hard-imports orgs models at module top.
  - No backstop at the domain layer: no `pre_delete` receiver on `User` anywhere (re-verified this
    pass by search), so every boundary other than this one view enforces nothing.
  - **Movement since last pass (does not close the finding):** SA41 fixed the red-flagged
    exception conflation — `cancel_current_subscription` now raises a distinct
    `BillingSubscriptionAnomalyError` (`billing/services.py:95,757`) which the view logs instead
    of swallowing (`auth/views.py:218–228`); SA35 fixed the content-cascade defect
    (author/created-by FKs → `SET_NULL`) and added the derivation-based
    `TestUserFkDeleteRuleConformance` gate. Both harden the *existing* boundary; neither gives the
    invariants a domain owner — the structural problem is unchanged.
  - The project already knows the correct shape: `orgs/signals.py:3–9` (SA7.1) names the
    receiver-based lifecycle pattern as canonical for cross-module behavior.
- **Why it compounds:** cost is N deletion boundaries × M invariants, each hand-written, some
  locked and some not, semantics drifting per copy (observable today: "never remove last owner"
  vs "fine if no other members"). Teams adds M; an erasure command adds N.
- **Detection signal:** none today — instrument by alerting on `Organization` rows with zero OWNER
  memberships and on active `Subscription` rows whose org has no members.
- **Steelman:** exactly two deletion paths today, operator is the maintainer, SA28/SA35/SA41 fixed
  the reachable defects. Holds only while user deletion stays single-path and invariants stay two;
  the locked teams design breaks both assumptions, and the semantic divergence is a latent bug
  regardless.
- **Correct shape:** each domain owns its lifecycle rules in exactly one place, enforced at a
  layer every ORM deletion path traverses (domain service + `pre_delete` receiver backstop);
  boundaries *invoke* the domain rather than re-implementing it.
- **Options:** (unchanged from 2026-07-06 — orgs-owned deletion service + signal backstop /
  signal-only / DB-level constraints; see reconciliation history for full text.)
- **Recommendation:** Option 1, first step already scheduled as SA47 (move the last-owner check
  into orgs as the single implementation, pick one semantic, add the concurrent-deletion test).
  The semantic question — which last-owner rule is canonical — is SA47's first decision.
  · **Size:** M · **First step:** SA47 as written in roadmap.md.

---

### Finding 4: orgs hand-enumerates the cross-module model universe in unlinked literals

- **ID:** `org-model-universe-hand-enumerated`
- **Rank rationale (blast radius × likelihood):** the enumerations back the isolation boundary's
  bookkeeping and the org-offboarding path; likelihood approaches 1 at the teams build.
- **Horizon & trigger:** `6–18 months` — the teams build; also fires on any new model added to an
  existing module.
- **Confidence:** High — all enumerations and *both* derivation gates read directly this pass.
- **Context dependence:** wrong-for-now on the new-domain dimension (teams).
- **Problem:** knowledge of "which models belong to an organization, and how they die" lives in
  hand-written literals inside orgs — a module that owns none of those models. The
  silent-staleness half of this is now closed by CI gates; the coordination-tax half and the
  gates' own coverage boundary remain.
- **Evidence — with a correction to the 2026-07-06 record:**
  - `orgs/tenancy.py:128–441` — `TENANT_TABLE_REGISTRY`, 49 hand-written entries (unchanged).
  - `purge_organization.py:64–212` — `_DELETE_SPECS`, 21 cross-module models with hand-ordered,
    comment-justified deletion order (unchanged).
  - **Correction:** the 2026-07-06 pass reported `TENANT_TABLE_REGISTRY` "still has no derivation
    check of its own." That was inaccurate — SA15.3's `test_doc_consistency.py` (read in full this
    pass) already cross-checks the literal against the purely marker-driven
    `get_derived_registry_overview()` (`tenancy.py:1449`) with **bidirectional set equality** on
    the ENROLLED universe (`test_doc_consistency.py:60–80`), per-app counts (`:83–106`), and full
    per-status triples for installed models (`:109+`). A marker-bearing model missing from the
    literal (or vice versa) fails CI. Together with SA45's purge-spec completeness test (expected
    set derived from `get_tenant_models()`,
    `orgs/tests/test_management_commands.py:1291–1332`), **both halves of Option 1 are in place.**
  - **What actually remains open:** (a) the purge *order* is still hand-written — the SA45 gate
    checks membership, not orderability, so a wrong hand-ordering still surfaces as
    `ProtectedError` mid-offboarding (Option 2's territory); (b) **every one of these gates sees
    only the models installed in orgs' test environment**, and that installed-apps list is itself
    a hand-maintained literal (`orgs/tests/settings.py:34–42` — 9 of 13 modules; notifications,
    storage, analytics, and future teams absent). A new tenant-bearing module whose app label
    never enters that list is invisible to the registry cross-check, the purge completeness gate,
    and the SA35 FK-conformance gate simultaneously — the enumeration problem reproduced one level
    up.
- **Why it compounds:** every new tenant model still requires K coordinated edits (marker +
  registry literal + `_DELETE_SPECS` entry with correct position + orgs test-env enrollment), and
  the gates that catch omissions are themselves keyed to one more hand list. Teams multiplies the
  entry count.
- **Detection signal:** `ProtectedError` from `purge_organization` in any environment (ordering
  defects — still ungated); for membership omissions the gates now fail CI *provided the module is
  installed in orgs' test env* — so the leading indicator to watch is a new module PR that
  doesn't touch `orgs/tests/settings.py`.
- **Steelman:** hand-ordered deletion is explicit, reviewable, and encodes FK subtleties naive
  traversal gets wrong; the module set is small and closed; and the gates now verify membership
  against real derivations. This steelman is *stronger* than last pass — what keeps the finding
  open is the ordering half and the coverage boundary, both of which the teams build stresses.
- **Correct shape:** one derivation path from the existing sources of truth (tenant markers + FK
  topology) produces classification, RLS-conformance parametrization, and the purge plan; any
  remaining literal is a pinned snapshot CI-validated against the derivation; the validation
  universe itself is derived (all shipped modules), not hand-listed.
- **Options:**
  1. ~~Derive the completeness gates~~ — **done** (SA15.3 registry cross-check + SA45 purge-spec
     derivation; correction above).
  2. **Derive the purge plan itself (now the live option):** topological delete order from the FK
     graph restricted to org-owned models, `_DELETE_SPECS` reduced to explicit overrides. M
     effort; do it when teams' models land and give the derivation a real test bed.
  3. **Module-contributed specs** via the manifest/`AppConfig.ready()` seam — only if a second
     consumer of per-module lifecycle knowledge appears.
  - **New sub-item (S, this pass):** close the coverage boundary — assert in CI that every shipped
    `quickscale_modules_*` package with models is installed in the cross-module conformance
    environment (derive the expected app list from the repo's module directory instead of the
    hand literal).
- **Recommendation:** the S-size coverage-boundary assertion now (before teams adds the tenth
  module), Option 2 at teams kickoff. · **Size:** M remaining (S for the coverage assertion)
  · **First step:** derive orgs' conformance-env expected-module list from
  `quickscale_modules/*/pyproject.toml` presence and fail CI on omissions.

---

### Finding 5: Authed state-changing JSON endpoints have three coexisting boundary idioms

- **ID:** `json-api-boundary-idiom-fragmentation`
- **Rank rationale (blast radius × likelihood):** the hand-built instances guard money paths
  (billing checkout/cancel/portal) and org management; the *silent-miss* class is now gated (see
  below), so remaining likelihood concentrates on teams copying the wrong template.
- **Horizon & trigger:** `6–18 months` — teams management endpoints.
- **Confidence:** High — all three idioms re-verified in code this pass; the gate and its CI
  wiring read directly.
- **Context dependence:** wrong-for-now on the new-domain dimension.
- **Problem:** the project established a fail-closed DRF baseline as the sanctioned JSON-API shape
  (SA11), but two parallel hand-rolled idioms survive beside it, so the boundary contract is
  re-implemented per idiom — three templates lie around for the next module to copy.
- **Evidence:**
  - The three idioms are unchanged in code: DRF baseline (billing read endpoints); orgs
    `JsonApiMixin`/`JsonOrganizationAccessMixin` stack across eight `OrgApi*` views
    (`orgs/views.py:220–1271`, file untouched since last pass, still 1,273 lines); billing's four
    state-changing plain Views with `@method_decorator(csrf_exempt)` + manual `_enforce_csrf`
    (`billing/views.py:82–84,159,215,271,326`).
  - **Progressed — the recommended gate landed and is blocking:** SA46 shipped
    `scripts/check_csrf_exempt_gate.py` (hard-fail AST gate: every `csrf_exempt` callsite must
    pair with `_enforce_csrf`, blog's session/token authenticator, or a webhook signature
    verifier) with a 1,755-line test suite, wired as a required CI job that the test,
    isolation-conformance, and lint jobs all depend on (`ci.yml:206–231,236,355,436`). The
    "silent CSRF hole on a new endpoint" failure mode from the 2026-07-06 pass is structurally
    closed. Residual: CR-SA46-REV-003 (evaluator completeness for `not`/`~`/unary-bool literals —
    ticket-shaped, scheduled, no pairing hole).
  - Note the gate's approved-verifier list is a hand-maintained name allowlist inside the script —
    a new module with its own signature-verified webhook must add its verifier name there. One
    more station, inherent to gate design; acceptable, worth knowing at teams kickoff.
- **Why it compounds:** every new JSON surface picks one of three idioms or invents a fourth; each
  hand idiom re-implements the same boundary concerns, so a boundary-rule change costs ×3 (SA21.2
  just demonstrated the class: the client-IP change had to be applied per-idiom — DRF
  `NUM_PROXIES`, blog's limiter, forms' throttle); each endpoint on a hand stack raises later
  consolidation cost.
- **Detection signal:** the miss case is now gated (CI); remaining signal is process-level — a
  teams PR whose endpoints subclass anything other than the sanctioned base.
- **Steelman:** the plain-View idiom exists for JSON error bodies; every instance is tested;
  migrating working money paths is churn with regression risk. Justifies current endpoints, not
  three templates at the moment a new module's API surface is about to be built.
- **Correct shape:** one base per transport need owns CSRF/auth/org-role/parsing exactly once;
  `csrf_exempt` appears only where a cryptographic request authenticator replaces it; a CI gate
  enforces the pairing (**this last clause is now satisfied**).
- **Options:**
  1. **Gate first, consolidate opportunistically (recommended — gate half done):** ~~add the
     pairing gate~~ (done, SA46); fold orgs' `OrgApi*` mixin stack into one `OrgApiBaseView`
     (S, still open); declare the DRF baseline required for *new* endpoints (a decisions.md
     paragraph, still open); migrate billing's four plain Views when next touched.
  2. **Full consolidation onto DRF now** — highest regression risk on money paths for no
     user-visible change; still not recommended.
- **Recommendation:** finish Option 1's remaining two S-size pieces before teams kickoff: the
  `OrgApiBaseView` fold and the decisions.md rule naming the sanctioned shape for new endpoints.
  · **Size:** M (remaining: fold S + rule S + billing migration as the long tail)
  · **First step:** the `OrgApiBaseView` fold in `orgs/views.py:944–1271`.

---

### Fix order and interactions

1. **SA44 (Finding 1 stage 1)** — ready now on Track 3, no deps; every future DR change benefits.
   The CR-SA38-001 copy-pair is unaffected by SA44 (it's an Option 2 problem) — leave the copies
   in place until then; do not "fix" one side alone.
2. **SA47 (Finding 2 first step)** — ready now on Track 1, no blocker.
3. **Finding 4's coverage-boundary assertion (S) and Finding 5's `OrgApiBaseView` fold + rule (S+S)
   before teams kickoff** — independent of each other and of SA44/SA47, but both edit orgs
   surfaces (`tests/settings.py`+CI vs `views.py`), so sequence within one track.
4. Finding 4 Option 2 (purge-plan derivation) waits for teams' models as its test bed.

All four findings are otherwise independent; no fix forces rework of another.

### Sound load-bearing decisions (protect these during remediation)

- **Dual-layer tenancy enforcement:** fail-closed `TenantManager` + FORCE RLS with the AF9
  execute-wrapper (`current_org.py:424+`), NOBYPASSRLS runtime role, always-on boot guard.
- **Governance by gate — now seven blocking CI gates and the pattern keeps paying:** module→core
  import linter, org-context AST gate, manifest-sync gate, isolation-conformance suite,
  default-deny tenant classification, SA35 FK-delete-rule conformance, and the new SA46
  csrf-exempt pairing gate (`ci.yml:206–231`). The SA15.3 registry cross-check and SA45 purge
  derivation belong to the same family (Finding 4's correction credits them).
- **Plan/apply as a checkpointed saga:** the `ApplyExecutor` + 16-step recovery ledger; new
  apply-path mutations belong inside it (watchlist).
- **The SA43/SA37 dispatch extraction direction:** Django-model/Popen lifecycle consolidated
  module-side in `backups/services.py` with core kept pure — this is Finding 1's correct shape
  being built incrementally; protect it (and fix the file's stale header that says the opposite).
- **SA21.2's consumer discipline:** blog limiter and forms throttle both consume the one shared
  `get_client_ip()` rather than growing private copies — right call given the seam that exists
  (but see the new watchlist item on *where* that seam landed).

### Watchlist

- **NEW — Shared module-runtime code has no sanctioned home.** Two placements were chosen this
  batch for cross-module runtime behavior: SA21.2 put HTTP client-IP resolution into orgs'
  *tenant-context* module (`current_org.py:584` — justified as "they already depend on orgs"),
  and SA26 left its href/markdown sanitizer as **byte-identical copies** in blog and listings
  (`blog/views.py:69,106` ≡ `listings/views.py:35+` — verified by diff). Each new shared concern
  either re-grows the orgs god-module SA7.2–7.4 dismantled or forks a security-relevant copy pair
  (the SA26 obfuscation hardening already had to be applied twice) · doesn't qualify yet: two
  instances, both tested, both small · promotes on the third shared-runtime concern, or if teams
  needs any of these helpers — decide then between a `quickscale_modules_common` package and a
  documented "orgs is the module commons" rule.
- **Billing webhook concurrent-duplicate window** — carried; `billing/services.py` untouched this
  delta except the SA41 exception class · promotes when any non-idempotent side effect lands in a
  handler.
- **Dual child-table tenancy APIs** — carried, `tenancy.py` trigger/composite-FK APIs untouched
  this delta; teams still placeholder · promotes if any teams child table lands on the trigger API.
- **Apply regeneration runs outside the recovery ledger** — carried sharpened;
  `apply_command.py` untouched this delta · promotes when the next apply-path mutation lands
  outside the `ApplyExecutor`, or on any crash-mid-`--force` report.
- **`orgs/views.py` fusion** — carried, untouched, 1,273 lines · promotes when teams begins
  extending org-facing surfaces; interacts with Finding 5's fold (same file — do the fold first).
- **Grandfathered option defaults multi-sourced, T2.4/T2.5 unscheduled — fourth consecutive
  pass.** The teams build (the promotion boundary named three passes ago) is now the next item of
  work · promotes when a grandfathered default changes in one station only, or at teams kickoff
  if still unscheduled.
- **Deploy-time configuration contract for generated apps** — carried; SA21.2 added a fourth
  data point (module code reading `USE_X_FORWARDED_FOR`/`TRUSTED_PROXY_COUNT` via
  `getattr`-with-default while generated settings bake them) · still cheapest as a one-paragraph
  decisions.md rule.

*(Carried unchanged at low priority, unprinted: `_is_migrate_command()` argv sniffing in
`orgs/apps.py`; hardcoded `EXEMPT_PATH_PREFIXES` in `orgs/middleware.py`.)*

### Teams landing checklist (carried forward, updated)

Declarative manifest path (freeze enforces) · `TenantModel` base + markers for every model ·
`TenantModelAdmin` for its admin · own module for views (not `orgs/views.py`) · notifications-PII
exclusion review at kickoff · membership/ownership invariants go into the Finding 2 seam (SA47's
service), not into views · background work reuses the `dispatch_background_*` service pattern in
`backups/services.py`, not a fresh Popen block · **updated:** teams' app must be added to orgs'
cross-module test env (`orgs/tests/settings.py`) *in the same PR that adds its first model*, or
every derivation gate is blind to it (Finding 4's coverage boundary) · endpoints subclass the
Finding 5 sanctioned base (post-fold), never the billing plain-View idiom; a teams webhook adds
its verifier to the SA46 gate's allowlist · client-IP/attribution needs use
`quickscale_modules_orgs.current_org.get_client_ip`, and a third shared-runtime helper triggers
the commons decision (watchlist).

### Questions that would change the ranking

- Which last-owner semantic is canonical? — **now SA47's first decision**; answer resolves
  Finding 2's divergence either way.
- Is `TENANT_TABLE_REGISTRY` intended to retire in favor of marker derivation? — **partially
  answered in code this pass**: `test_doc_consistency.py:11–14` calls the literal "the temporary
  SSOT" kept "so the derived view can eventually replace the hand-maintained literal." If that
  intent is current, Finding 4's Option 2 should plan the retirement; confirm and record it in
  decisions.md.
- Are T2.4/T2.5 deliberately abandoned or just unscheduled? Fourth pass without an answer; the
  promotion boundary (teams kickoff) has arrived.
- Will any deletion/erasure path beyond `AccountDeleteView` ship? Any yes promotes Finding 2 to
  `now`.

### Red flags (out of scope — fix now)

- **Resolved 2026-07-07 (roadmap cleanup), no longer re-flagged:** `_get_manage_py()`'s silent
  fallback (SA52), the SA21.2 helper's permissive `getattr` settings reads (SA48), and the false
  `backups/services.py:1–10` header contract (SA51) — all three landed; detail in CHANGELOG.md
  and the tech-audit.md reconciliation log (TA42/TA43/TA44).
- **Carried → now scheduled, no longer re-flagged:** the `entry_point.py` post-hook permissive
  coercion defaults (flagged 2026-07-05 and 2026-07-06) are tracked as SA42, open on Track 3.

Lenses scanned with no qualifying finding this pass: data/state integrity, trust boundaries
(SA46 gate strengthens; SA39 made `operator_access` fail-hard outside transactions), module
cohesion beyond Findings 1/5 (commons question → watchlist), consistency/failure models
(SA37/SA38/SA43 dispatch lifecycle read in full — CAS claims, snapshot/rollback, stale reset all
sound at code level), trajectory, observability (SA38 added the missing staleness surfacing),
API contracts, testing architecture (three new derivation-based gates — the right kind),
design conflicts beyond Finding 2, concurrency (`_atomic_claim_restore` + `reset_stale_restore`
CAS verified), security architecture (SA26 copies noted → watchlist), build/supply chain
(pip-audit gap remains a tech-audit tooling item), performance.

---

## Autopsy — 2026-07-06 (re-run) and module-by-module deep pass

> Superseded by the 2026-07-07 delta pass above, which re-verified all four open findings'
> evidence anchors directly and read the full SA34–SA46 closeout delta. The 2026-07-06 passes'
> full text (three findings opened at the repo level, two more from the module deep pass, five
> steelmanned candidates, per-module verdicts) is preserved in version control; their
> still-current outputs — the findings themselves, the watchlist, the teams landing checklist,
> and the open questions — are carried forward above with this pass's updates. This stub heading
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
