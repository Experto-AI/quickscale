# Structural Autopsy: QuickScale

> This file is regenerated on each autopsy run to state **present reality for planning**: the
> current orientation, the open findings in full detail, and a curated watchlist. Closed findings
> exist only as dated lines in the **Reconciliation log** at the bottom (closeout detail lives in
> [CHANGELOG.md](../../CHANGELOG.md)); version control preserves prior full text. Finding IDs are stable
> across runs.

---

## Autopsy — 2026-07-11 (re-run, delta pass over the SA65/SA66/SA68/SA73 + SA59.1 checkpoint batch)

### Orientation (2026-07-11)

QuickScale is a solo-maintained (Experto-AI/Victor Rocco) Python 3.13/3.14 + Poetry monorepo
(VERSION 0.87.0, integration branch `v87`) that generates user-owned Django 6 SaaS projects:
`quickscale_cli` (Click: plan/apply/dr/deploy), `quickscale_core` (Jinja2 generator, plan/apply
engine, manifest/contracts stack, DR engine), 13 shipped Django modules (teams still README-only,
re-verified), and `quickscale_devtools` (maintainer-only beta-site migration tooling). Generated
apps: Django 6 + PostgreSQL 18, single-service Railway; tenancy enforced twice (fail-closed
`TenantManager` + FORCE RLS with the AF9 execute-wrapper), backstopped by the SA58 boot guard
(rejects `rolsuper` and `rolbypassrls`). **Commit-delta classification (§2f) for
`ae8c386e..HEAD`** (23 non-merge commits): *closeouts* — SA65 (`0b7d6cd8`), SA66 (`0138db60`),
SA68 (`52144290`), SA69 (`ff75ed9d`, docs-only), SA73 (`fc3dc00c`), all verified mapped to
scheduled items and fix-regression-audited below; *housekeeping* — 15 docs commits plus merges;
*unlabeled-behavioral* — the three **`chore: checkpoint SA59…`** commits (`625626e8`, `6c90d8b9`,
`2b9afa6b`), which carry the entire CI/publish **unit/integration gate split** (new
`scripts/test_integration.sh`, restricted `quickscale_test_role` provisioning in both workflows,
removal of the blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export from the unit path, orgs
restricted-role test adaptations) — read at full depth this pass. Unlike the side-channel commits
of prior deltas these are SA-tracked and roadmap-documented, but the `chore:` label still
understates load-bearing gate-semantics changes; `fc3dc00c` ("SA73: fix quality gate failures")
also quietly added `ignore_missing_imports = True` for `quickscale_modules_backups.*` to
`mypy.ini` — a new Finding 1 cycle carrier. Read fully this pass: all four closeout diffs, the
checkpoint commits' workflow/script/conftest portions, `test_integration.sh` (complete),
`test_unit.sh` tail + Makefile test targets, `check_ci_locally.sh`, the SA66 conformance test
(complete), the `production.py.j2` and `orgs/apps.py` diffs, roadmap.md, the two new decisions.md
sections, tech-audit.md's Structural smells. Sampled: orgs restricted-role test adaptations
(conftest read in full, sibling test files stat-only), `test_generated_project_runtime.py`
(grep-level), `generator.py` (structure-level). Verified untouched by git log:
`billing/services.py`, orgs views/middleware/tenancy/purge, `backups/services.py`, `dr_engine/`
(except one SA73 comment line). The full first-party source delta is eight files, all read.
**Growth direction (planning surface):** Track 1 only — SA59.1–SA59.4 (finish the gate split:
pre-existing restricted-role failures, backups PostgreSQL seam, script/Docker role provisioning,
docs), SA60 (composite-FK deferability policy), SA70 (Finding 2's `pre_delete` backstop). Tracks
2 and 3 are clean. Severity floor unchanged: CLI is single-process local; generated apps are
single-service WSGI; tenant isolation is the highest-blast property.

**Result: four findings still-open (Finding 7 narrowed), zero new findings.** This pass's value
is the fix-regression audit of the closeout batch: **SA65 clean** (import-time env snapshot
deleted; `_run_command` defaults to `env=None`; scoped env passed only to the two nested
`quickscale_cli.main` call sites — mechanism removed, nothing relocated). **SA68 clean on its
mechanism** (no argv inspection remains anywhere on the privilege-selection path; Finding 6 stays
closed) but it minted one small new station — the sanctioned-command set now exists as two
parallel frozensets on opposite sides of the template/runtime-library boundary
(`production.py.j2` `_KNOWN_PRIVILEGED_COMMANDS` vs `orgs/apps.py` `_PRIVILEGED_COMMANDS`), both
fail-closed, with no sync gate — recorded as a watchlist item, not a reopening. **SA66 landed a
genuine derivation gate** (Finding 7 narrowed: the emitted-file universe is derived from the
template tree, zero unclassified files, and both of the prior pass's open policy questions are
answered and test-pinned) but the gate itself minted a hand-synced copy of the generator's
template→emitted-path routing inside the test — cited in Finding 7's evidence. **The SA59.1
checkpoint structurally removed the blanket test-path bypass hatch** (enforcement census row 2
strengthened: CI's integration path now runs module suites under a real
NOBYPASSRLS/NOSUPERUSER role with the SA58 guard live) at the cost of a currently-red
integration gate — red-flagged below.

### Enforcement census (§3.4)

| # | Invariant | Enforced by | Class | Trend this pass |
|---|-----------|-------------|-------|-----------------|
| 1 | Tenant isolation on reads/writes | fail-closed `TenantManager` + FORCE RLS + AF9 execute-wrapper | structural | stable |
| 2 | No bypassing DB role at boot | orgs boot guard (`apps.py`), `rolbypassrls` + `rolsuper` | structural | **strengthened** — the SA59 blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export is gone from the unit path; CI/publish integration jobs run module suites under `quickscale_test_role` (NOBYPASSRLS/NOSUPERUSER) with the guard live. Caveats: gate currently red on pre-existing failures (red flag); SQLite suites (backups) outside its reach until SA59.2 |
| 3 | Admin org-scoping | `TenantModelAdmin`; tripwire = NOBYPASSRLS test posture (SA14.4) | structural + gated | **restored** — with the blanket hatch gone, NOBYPASSRLS-by-default is real again in the integration path |
| 4 | DB privilege selection per process | launcher env contract (`QUICKSCALE_PRIVILEGED_COMMAND`/`QUICKSCALE_NON_DB_COMMAND` + `RUNTIME_DATABASE_URL=""`), consumed by production settings + boot guard | structural | completed (SA68, re-verified in code this pass — zero argv inspection). New: sanctioned-set frozensets ×2 (template-side + orgs-module-side), both fail closed on unknown values/desync, no sync gate (watchlist) |
| 5 | JSON endpoint idiom | `OrgApiBaseView`/DRF baseline + SA46 csrf-exempt CI gate | structural + gated | stable |
| 6 | Core↔module import direction | import linter + `LEGACY_ALLOWED_IMPORTS` (3 modules) | gated, with exceptions | list stable (billing, crm, social — did not grow). New cycle **carrier**: `mypy.ini` `ignore_missing_imports = True` for `quickscale_modules_backups.*` (SA73); linter header/dict drift (docstring says billing+CRM only, dict has social) |
| 7 | Module manifest copy-pairs (module.yml ×2) | CI byte-identical sync gate | gated | stable |
| 8 | Tenant-model universe **membership** | SA15.3/SA45/SA49 derivation gates | gated | stable |
| 9 | Tenant-model purge **order** | hand-ordered `_DELETE_SPECS`, comment-justified | convention | unchanged (Finding 4; SA60 open) |
| 10 | Deletion invariants at account boundary | one canonical check, invoked per boundary; no `pre_delete` backstop | convention | unchanged (Finding 2) — first step now **scheduled** (SA70, Track 1) |
| 11 | pyproject TOML write safety | `_write_validated_toml` (3 CLI splice sites) | structural per package | stable; devtools copy unchanged |
| 12 | Generator-emitted file ownership for upgrades | SA66 conformance gate: emitted-file universe derived from `generator/templates/`, every file classified, policy pins for `start.sh`/`production.py`, `INTENTIONALLY_UNMANAGED` explicit class | **gated** (was convention, ungated) | **strengthened** (SA66). Residuals: the gate's template→emitted-path mapping is itself a hand-synced copy of generator routing; the "unmanaged entries need a decisions.md rationale" invariant is stated but unenforced (test asserts non-emptiness only) |
| 13 | Generated-project boot correctness | `test_generated_project_runtime.py` boot smoke harness | gated | strengthened — +284 lines (SA68) covering the privileged-command and bypass-hatch paths end-to-end |
| 14 | Module suites run under a restricted DB role | ci.yml/publish.yml role provisioning + `QS_*_DB_USER` env wiring | gated | **new this delta** — env lists hand-enumerated ×2 workflows (11 modules each); omission fails **loud** for PostgreSQL modules (module test settings fall back to `USER=postgres`, which the boot guard rejects under `QUICKSCALE_ALLOW_BYPASSRLS=0`); silent only for SQLite suites (SA59.2, tracked); `check_ci_locally.sh` lacks the wiring entirely (SA59.3's shared-provisioning design is the scheduled fix) |
| 15 | Release-gate test scope | publish.yml `test` job | gated | **new** — publish.yml now runs the same unit + restricted-role integration split as ci.yml (was a single combined unit script) |

### Summary table

| # | ID | Horizon | Size | One-line problem |
|---|----|---------|------|------------------|
| 1 | `dr-engine-module-circular-lattice` | now | M remaining (Option 2) | DR logic lives in core but its state and lifecycle live in the backups module; the cycle is carried by hand-synced symbol stations and a linter exception list — unchanged this delta (second consecutive quiet pass); carrier count grew by one (SA73's mypy `ignore_missing_imports`); persistence port still scheduled |
| 7 | `generated-file-ownership-unmodeled` | 6–18 months | M remaining (Option 2) | SA66's conformance gate closed the silent-miss class and pinned both ownership policies, but the taxonomy and the gate's emission-path mapping remain hand-synced copies of generator knowledge living in the ungoverned devtools package; Option 2 (generator-emitted ownership manifest) is the mechanism-removing fix |
| 2 | `deletion-invariants-per-boundary-reimplementation` | deferred (teams unscheduled) | M remaining | One canonical last-owner check, but no domain-level `pre_delete` backstop — first step now scheduled as SA70 (Track 1) |
| 4 | `org-model-universe-hand-enumerated` | deferred (teams unscheduled) | M remaining (Option 2) | Tenant-model membership is CI-gated against derivations but the purge *order* is hand-written; SA60 (open) owns the missing deferrability/`tenant_excluded` decision records |

---

### Finding 1: DR domain is split across the core↔module boundary into a circular import lattice

- **ID:** `dr-engine-module-circular-lattice`
- **Rank rationale (blast radius × likelihood):** every DR feature and every new module adapter
  crosses this seam; empirical rate had been ~1 compounding instance per batch for three
  consecutive batches before the current two quiet deltas. Quiet deltas are absence of trigger
  (no DR work landed), not absence of mechanism.
- **Horizon & trigger:** `now` — Option 2 (persistence port) is scheduled for the next planning
  cycle per the 2026-07-09 escalation; any DR feature or new module adapter landing before it
  pays the tax.
- **Confidence:** High — all edges re-verified in current code this pass.
- **Context dependence:** wrong-regardless — the tax is paid at current scale by a solo maintainer.
- **Problem:** the DR engine's logic was extracted into core while its persistent state
  (`BackupArtifact`, `BackupPolicy`) and its Django-facing entry points stayed in the backups
  module — so neither side can import the other top-down, and the system holds the cycle together
  with lazy-loading tables, a re-export shim, hand-synced `__all__` literals, and a per-module
  linter exception list.
- **Evidence (all anchors re-verified this pass):**
  - Core → module: `dr_engine/orchestration.py:80–84` still imports
    `quickscale_modules_backups.models` at module level.
  - The combined facade's hand-synced literal `__all__` station is intact
    (`runtime/__init__.py:36–43` — "When adding a new public symbol to dr.py or manifest.py, add
    it here too").
  - `LEGACY_ALLOWED_IMPORTS` still carries the social routing exception
    (`check_module_core_imports.py:60–82`) — did not grow this delta (billing, crm, social; same
    three as 2026-07-09). Drift note: the linter's own docstring (`:8–15`) now claims exceptions
    are "limited to billing and CRM" while the dict has three keys — the gate's documentation
    disagrees with its own allowlist.
  - **New carrier this delta:** `mypy.ini:94–95` gained `ignore_missing_imports = True` for
    `quickscale_modules_backups.*` (SA73, `fc3dc00c`) — the type-check gate now permanently skips
    resolving the very import that constitutes the cycle's core→module edge. Per the §5.XII rule,
    lazy imports, re-export shims, hand-synced `__all__` unions, linter exceptions, *and now a
    mypy ignore* are cycle carriers, and their count growing is the cycle compounding.
  - Module → core: `backups/services.py` re-export shim unchanged (650 lines, verified untouched
    by git log since SA53); SA54's gated copy-pair (threshold parameter + signature-pin test)
    unchanged.
- **Counter-evidence:** searched the delta for new lazy-table entries, facade `__all__` growth,
  or new linter exceptions — none landed; the only dr_engine change was a one-line comment
  (SA73). Searched the roadmap for the persistence port — still named as scheduled for the next
  planning cycle. Nothing disproves the mechanism; two quiet deltas show only that no DR work
  happened.
- **Why it compounds:** every DR feature touches up to six stations (orchestration function +
  dr.py lazy table + dr.py `__all__` + facade literal `__all__` + services shim + adapter
  signature); every boundary-crossing invariant becomes a gated copy pair; every new module whose
  adapter needs manifest surface either adds a linter exception or pays the cycle. Built on top:
  all backups management commands, admin restore/create/prune, the DR CLI, apply/deploy DR
  integration, the social adapter's import path.
- **Detection signal:** growth of `_LAZY_*` tables, the facade `__all__`,
  `LEGACY_ALLOWED_IMPORTS`, or per-package mypy ignores in any diff; any diff editing one side of
  a gated copy pair.
- **Steelman:** each mechanism is a standard pattern, all are gated, and generated apps ship
  backups+core together so the cycle never bites end users at runtime. It failed on evidence in
  three consecutive batches before the current quiet stretch; quiet deltas do not restore it.
- **Correct shape:** imports across the core↔module boundary form a DAG (modules → core only);
  no underscore-private name crosses a package boundary; a boundary-crossing invariant has exactly
  one implementation; adding a module adapter requires zero linter exceptions.
- **Options:**
  1. ~~Registration-not-import + facade split~~ — **done** (SA44 + the `runtime/` package); it
     clarified the surface but demonstrably did not remove the cycle.
  2. **Persistence port (the live option, scheduled).** Core defines protocols for
     artifact/policy persistence; the backups module implements and injects them at app-ready.
     Kills `orchestration.py:80`, the lazy tables' reason to exist, the SA54 copy-pair class, the
     new mypy ignore's reason to exist, and adapter deep-import exceptions. M–L effort.
  3. **Invert ownership.** Move all Django-model-touching orchestration into the backups module;
     core keeps pure primitives. Largest migration; complicates the CLI's non-Django DR paths.
- **Recommendation:** Option 2, as scheduled — land it before the next DR feature or module
  adapter. · **Size:** M remaining · **First step:** define the artifact/policy persistence
  protocol in core and port `restore_admin_uploaded_backup` (the SA54 seam) onto it — that one
  function exercises the model import, the threshold copy, and the staging lifecycle at once.

---

### Finding 7: Generated projects have no file-level ownership contract — the upgrade path re-encodes it by hand

- **ID:** `generated-file-ownership-unmodeled`
- **Rank rationale (blast radius × likelihood):** blast is the deploy/infra correctness of the
  only two production deployments (`experto-ai-web`, `bap-web`) plus every future generated
  project's upgrade story; likelihood dropped this pass — the SA66 gate turns the previously
  silent miss class (a template file no taxonomy covers) into a CI failure, so the live-gap
  scenario that ranked this `now` is closed.
- **Horizon & trigger:** `6–18 months` — fires on a third consumer site, a public
  "update my generated project" command, a new theme, or a new dynamically generated artifact
  (each stresses the two remaining hand-synced copies described below).
- **Confidence:** High — the SA66 diff, the full conformance test, and the decisions.md record
  were read this pass; the residual copies are directly observable.
- **Context dependence:** wrong-for-now on the **consumer-count** dimension: with one maintainer
  and two sites the gate suffices; a third site, a second operator, or a public update command
  makes the remaining hand-synced knowledge wrong-regardless.
- **Problem:** the generator still has no machine-readable, generator-owned statement of per-file
  ownership — the taxonomy lives as hand-written tuples in the maintainer migration tool, and the
  new conformance gate holds those tuples honest by *re-implementing the generator's
  template→emitted-path routing inside the test* rather than consuming a mapping the generator
  exports.
- **Evidence:**
  - **Fix-regression audit of SA66 (`0138db60`):** (i) the silent-miss mechanism is removed —
    `test_beta_migration_ownership_conformance.py` enumerates every `.j2` template plus non-Jinja
    theme files and the dynamic `poetry.lock`, resolves emitted paths, and fails on any
    unclassified file; `start.sh` was added to both in-place tuples (closing the prior pass's
    live gap) and `INTENTIONALLY_UNMANAGED` (~80 entries) makes "deliberately unmanaged" an
    explicit class. (ii) Fail direction preserved — unclassified files fail loud. (iii) **New
    commitments minted:** the test's `_THEME_DEST_MAP`/`_THEME_SUBDIR_MAP`/`_map_theme_template`
    plus special cases for `project_name/`, `common/`, `github/`, the theme-README skip, and a
    hand entry for `poetry.lock` are a parallel copy of `generator.py`'s procedural emission
    routing (verified: the generator exposes no declarative mapping — `_generate_project`/
    `_generate_react_frontend` compute destinations inline). `_theme_non_jinja_emitted_paths`
    hardcodes `("showcase_react",)`, so a future theme's non-Jinja files would be silently absent
    from the enumerated universe — the one residual silent direction.
  - Both prior open policy questions are now answered and pinned: `settings/production.py` is
    donor-owned **by policy** and `start.sh` is in-place-managed —
    `decisions.md §Generated-File Ownership (Beta-Migration Taxonomy)` records both;
    `test_production_py_is_donor_owned_by_policy` and `test_start_sh_is_in_place_managed`/
    `…_substituted` pin them.
  - Gate-integrity gap (§5.XV): decisions.md rule 3 states every `INTENTIONALLY_UNMANAGED` entry
    "must have a documented exemption rationale in decisions.md," but
    `test_intentionally_unmanaged_entries_have_documented_rationale` asserts only non-emptiness
    (its own docstring admits the cross-check is not implemented).
  - Governance placement: `quickscale_devtools` remains outside the lint/typecheck universe
    (absent from `ruff.toml`, `mypy.ini`, and Makefile targets; present only as a path dep and on
    `pythonpath`), yet the conformance test importing it now runs in the **unit gate of ci.yml
    and publish.yml** — the release pipeline is import-load-bearing on an ungoverned package.
- **Counter-evidence:** searched for a generator-exported emission mapping the test could consume
  (none — routing is procedural); for a decisions.md↔tuple cross-check (none; non-emptiness
  only); for devtools lint/type coverage (none). The strongest disconfirming fact: the gate is
  real, derivation-based, and CI-enforced — the defect class that made this finding `now`
  (a template change silently missing the beta sites) genuinely cannot recur for `.j2` files.
  That narrows the finding to its remaining copies; it does not close it, because the correct
  shape (generator-owned ownership statement) still exists nowhere.
- **Why it compounds:** every generator routing change (new theme, new subdir mapping, new
  dynamic artifact) now requires a matching hand edit inside the conformance test, and every
  taxonomy judgment stays maintainer-memory encoded in tuples the type checker and linter never
  see. Cost grows O(themes × dynamic artifacts × consumer sites). Built on top: the shipped
  `make beta-migrate-*` automation, the two beta sites' release cadence, and now the release
  gate itself (via the conformance test's devtools import). The devtools TOML-splice copy
  (`beta_migration.py:597` twin of `module_dependency_sync.py:223`) remains the second
  manifestation of the same root.
- **Detection signal:** a conformance-gate failure naming an unclassified path is the loud
  (good) signal; the silent direction is a new theme or dynamic artifact absent from the test's
  universe — instrument by asserting the test's enumerated-universe size against the generator's
  actual output in the boot smoke harness (which already generates full projects).
- **Steelman:** Option 1 was this audit's own recommendation, explicitly scoped as the interim
  step; hand-curated tuples encode judgment (donor-owned production.py) that naive derivation
  would get wrong; the emission-routing copy in the test fails loud in most divergence
  scenarios; and the maintainer is the only operator. That holds until a third consumer or a
  public update command — exactly the recorded Option 2 trigger.
- **Correct shape:** the generator owns a single machine-readable statement of per-file ownership
  (generator-owned / user-seeded / protected / unmanaged), emitted with each project or exported
  as an API derived from its own routing; upgrade tooling and the conformance gate *consume* that
  statement; no second implementation of the template→emitted-path mapping exists anywhere.
- **Options:**
  1. ~~Derivation gate over the existing lists~~ — **done** (SA66); it closed the silent-miss
     class and is the right interim, at the cost of one new hand-synced mapping copy.
  2. **Generator-emitted ownership manifest (the live option).** The generator writes per-file
     ownership/provenance (template path + vintage) into the project state it already maintains,
     or exports the emission mapping as a function; `beta_migration` and the conformance test
     derive their sets from it. Removes the parallel taxonomy *and* the test-side routing copy;
     relocates ownership knowledge from ungoverned devtools into governed core. M, and the
     natural substrate for a public upgrade story.
  3. **Fold the upgrade path into the product.** Extend `quickscale apply`'s contract-vintage
     machinery to refresh generator-owned infra on existing projects, retiring the separate
     devtools path. L; only worth it when generated-project upgrades become a public feature.
- **Recommendation:** Option 2 when its trigger fires (third consumer / public update command /
  second theme); until then the SA66 gate carries the load. Opportunistic hardening if touched
  sooner: have the boot smoke harness cross-check the conformance test's enumerated universe
  against a real generated tree, closing the new-theme silent direction cheaply.
  · **Size:** M remaining · **First step:** export the generator's emission mapping as a
  function (pure refactor of `_generate_project`'s inline destination logic) and point the
  conformance test at it — that deletes the test-side routing copy without waiting for the full
  manifest.

---

### Finding 2: Deletion-boundary invariants are re-implemented per boundary with no domain backstop

- **ID:** `deletion-invariants-per-boundary-reimplementation`
- **Rank rationale (blast radius × likelihood):** blast is money and org integrity (orphaned live
  Stripe subscriptions, ownerless shared orgs); likelihood moderate and static while user deletion
  stays single-path and teams stays unscheduled.
- **Horizon & trigger:** `deferred` — teams is not scheduled. Live trigger regardless of teams:
  the first account-deletion path that isn't `AccountDeleteView` (e.g. a GDPR erasure command).
- **Confidence:** High — re-verified this pass: zero `pre_delete` receivers in orgs, billing, or
  auth (repo search); none of the finding's files were touched by this delta.
- **Context dependence:** wrong-for-now → wrong-regardless if/when teams kicks off.
- **Problem:** org-domain and billing-domain rules for "what must hold when a user disappears"
  are enforced only at boundaries that choose to invoke them — there is no layer every ORM
  deletion path traverses.
- **Evidence:** unchanged — `OrganizationMembership.is_last_owner_with_members()`
  (`orgs/models.py:165`) consumed by the lock-guarded `delete()` (`models.py:329`),
  `AccountDeleteView` (`auth/views.py:114,147–164`), and both orgs view callsites
  (`orgs/views.py:808,1161`); instance `delete()` overrides don't run under the deletion
  collector, so a `User` cascade bypasses the model rule.
- **Counter-evidence:** searched again for receivers, collector hooks, or DB-level ownership
  constraints added since the last pass — none; the delta touched none of these files. One
  adjacent caution: SA59.1's orgs conftest now globally mutes `organization_created` via an
  autouse fixture — if SA70's `pre_delete` receiver is tested under a similar muting pattern,
  the backstop would be untested; SA70's acceptance criteria (direct ORM-delete regression test)
  already precludes this if followed.
- **Why it compounds:** cost is N deletion boundaries × M invariants; teams adds M, an erasure
  command adds N.
- **Detection signal:** none today — instrument by alerting on `Organization` rows with zero
  OWNER memberships and on active `Subscription` rows whose org has no members.
- **Steelman:** exactly one deletion path exists today and the operator is the maintainer. Holds
  while user deletion stays single-path.
- **Correct shape / Options:** unchanged (orgs-owned deletion service + `pre_delete` receiver
  backstop / signal-only / DB-level constraints — full text in version control).
- **Recommendation:** the `pre_delete` receiver backstop is now **scheduled as SA70 (Track 1)**
  — land it as specced (receiver calling the SA47 check + a direct-ORM-delete regression test).
  · **Size:** M remaining (S for SA70) · **First step:** SA70.

---

### Finding 4: orgs hand-enumerates the cross-module model universe in unlinked literals

- **ID:** `org-model-universe-hand-enumerated`
- **Rank rationale (blast radius × likelihood):** the enumerations back the isolation boundary's
  bookkeeping and org-offboarding; likelihood approaches 1 if/when a teams build lands, near-zero
  otherwise except for new models in shipped modules.
- **Horizon & trigger:** `deferred` — teams unscheduled; fires independently on any new model
  added to an already-shipped module.
- **Confidence:** High — `tenancy.py` and `purge_organization.py` verified untouched by git log
  this delta; the SA15.3/SA45/SA49 gates' files unchanged.
- **Context dependence:** wrong-for-now on the new-domain dimension.
- **Problem:** knowledge of "which models belong to an organization, and how they die" lives in
  hand-written literals inside orgs; membership is fully CI-gated, purge *order* is not.
- **Evidence:** unchanged — `TENANT_TABLE_REGISTRY` (`tenancy.py:128`, 49 entries, bidirectionally
  gated); `_DELETE_SPECS` (`purge_organization.py:64`, hand-ordered; the SA45 gate checks
  membership, not orderability). The decision-record caution (composite-FK `NOT DEFERRABLE`
  switch + `tenant_excluded` precedence, both undocumented) is owned by **SA60, open on Track 1**.
  Related this delta: SA59.1 discovered `forms/migrations/0007` fails composite-FK validation on
  a fresh restricted-role DB — the deferability divergence SA60 owns is now blocking real work,
  raising SA60's practical urgency without changing this finding's shape.
- **Counter-evidence:** checked the delta for changes to the registry, purge specs, or derivation
  inputs — none; checked decisions.md for the SA60 records — not yet written (SA60 open).
- **Why it compounds:** every new tenant model requires K coordinated edits (marker + registry
  literal + `_DELETE_SPECS` entry with correct position); purge-order correctness is the one
  property no gate checks, and the `NOT DEFERRABLE` change made it less forgiving.
- **Detection signal:** `ProtectedError` from `purge_organization` in any environment;
  `NOT DEFERRABLE` composite-FK violations surfacing mid-purge — and now, concretely, the
  `forms/0007` failure class on restricted-role databases.
- **Steelman:** hand-ordered deletion is explicit, reviewable, and encodes FK subtleties naive
  traversal gets wrong; membership gates are complete and derivation-backed.
- **Correct shape / Options:** unchanged — Option 2 (derive the purge plan topologically from the
  FK graph, `_DELETE_SPECS` reduced to overrides) is the live option, if/when teams' models land.
- **Recommendation:** SA60 first (it now unblocks SA59.1's forms failure as well as closing the
  decision-record caution); purge-order derivation only when a real second consumer (teams)
  gives it a test bed. · **Size:** M remaining · **First step:** SA60 (already scheduled).

---

### Change-cost probes (§3.6)

- **Probe A — "a 14th module lands in `quickscale_modules/`."** Chosen because module addition is
  the recurring change shape this repo's gate architecture is built around, and this delta minted
  new stations for it. Measured stations: (1) module dir + pyproject + module.yml copy-pair —
  gated (census row 7); (2) manifest adapter registration — one line (or a linter exception if it
  deep-imports; Finding 1); (3–5) `ci.yml`: createdb list, role-grant DB list, `QS_*_DB_USER` env
  block — three hand edits; (6–8) `publish.yml`: the same three lists again; (9) the module's own
  `tests/settings.py` — self-contained. Derived automatically (zero cost): `test_integration.sh`
  iterates `quickscale_modules/*` dynamically; Makefile typecheck loops modules; orgs
  conformance-env is SA49-derived. **Six ungated hand stations in workflow files — but omission
  fails loud for PostgreSQL modules:** the settings fallback is `USER=postgres`
  (`tests/settings.py` pattern, verified in orgs and billing), and under the integration jobs'
  `QUICKSCALE_ALLOW_BYPASSRLS=0` the SA58 boot guard rejects `rolsuper`, so a missed env var
  fails the suite rather than silently running unguarded. Silent only for SQLite-based suites
  (backups — SA59.2, already tracked). **Verdict: watchlist** (new item below), not a finding —
  the fail direction is closed where RLS matters; the derivation belongs in SA59.3's shared
  provisioning script.
- **Probe B — "add a third sanctioned privileged command to generated apps"** (re-measuring
  Finding 6's seam post-SA68). Measured stations: (1) the `start.sh.j2` launch line with the env
  pair; (2) `production.py.j2`'s `_KNOWN_PRIVILEGED_COMMANDS` frozenset; (3) `orgs/apps.py`'s
  `_PRIVILEGED_COMMANDS` frozenset — plus each side's tests. Three code stations, two of them a
  copy-pair with no sync gate, split across the template/runtime-library boundary (a generated
  project's `production.py` is frozen at generation vintage while the orgs module upgrades by
  dependency bump). Desync fails **closed** at both consumers (unknown value → `ValueError` in
  settings; guard stays active in orgs). **Verdict: seam exonerated for its fail direction;
  copy-pair recorded as a watchlist item.** Finding 6 stays closed.

### Fix order and interactions

1. **SA59.1's remaining blockers** (pre-existing restricted-role failures, red-flagged gate
   state) come first operationally — while the integration gate is red it cannot catch new
   module-suite regressions, which weakens every census row that depends on it (2, 3, 14).
2. **SA60** now unblocks two things at once: Finding 4's decision-record caution and SA59.1's
   forms/0007 composite-FK failure. Land it early in the SA59 sequence rather than parallel.
3. **SA70** (Finding 2's first step) is independent and small; land opportunistically.
4. **Finding 1 Option 2 (persistence port)** — scheduled next planning cycle; independent of
   everything above.
5. **Finding 7's remainder (Option 2)** waits on its trigger; the cheap interim (export the
   generator's emission mapping and point the SA66 test at it) is independent and small.

### Sound load-bearing decisions (protect these during remediation)

- **The unit/integration gate split along the DB-need boundary (SA59.1):** DB-free unit gate
  (core + CLI) plus a PostgreSQL integration gate running module suites under a
  NOBYPASSRLS/NOSUPERUSER role with the SA58 boot guard live — this is the shape the audit's
  census row 2 has wanted since SA14.4, and the blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export is
  finally gone from the unit path. Finish it (SA59.1–.4); don't regress the blanket hatch back in
  to get the gate green.
- **Dual-layer tenancy enforcement:** fail-closed `TenantManager` + FORCE RLS with the AF9
  execute-wrapper, boot guard rejecting `rolsuper`/`rolbypassrls` — now exercised in CI against a
  genuinely restricted role. The `USER=postgres` settings fallback failing loud *because of* the
  guard (Probe A) is this architecture working as designed.
- **SA68's launcher env contract:** one channel (`QUICKSCALE_PRIVILEGED_COMMAND`/
  `QUICKSCALE_NON_DB_COMMAND` + `RUNTIME_DATABASE_URL=""`), published by start.sh/Dockerfile,
  consumed fail-closed by production settings and the boot guard; verified in code this pass —
  zero argv inspection anywhere on the privilege path. Keep both consumers fail-closed on unknown
  values.
- **Governance by gate, exercised again:** SA66's conformance gate is the house pattern
  (SA15.3/SA45/SA49 family) applied to the generator's emitted-file universe, and it answered
  both of the prior pass's open policy questions with pinned tests plus a decisions.md record.
- **The generated-project boot smoke harness** (`test_generated_project_runtime.py`): grew +284
  lines this delta covering the SA68 command-contract paths end-to-end — still the
  runtime-confirmation layer to route template-contract claims through.
- **`TenantModelAdmin` as the single admin-scoping seam** and **SA47's canonical last-owner
  check** (one implementation, four consumers, lock-guarded) — carried; SA70 extends the latter,
  not parallels it.

### Watchlist (every carried item shows this pass's trigger evaluation — §8)

- **Shared module-runtime code has no *written* commons rule.** Trigger ("a new shared concern
  lands somewhere other than orgs, or teams kickoff"): **not fired** — no new runtime shared
  concern this delta (`tests_shared/` is test-helper commons, out of the item's scope); the SA26
  sanitizer remains byte-similar copies in `blog/views.py` + `listings/views.py` (re-verified).
  Carry: write the "orgs is the module commons" rule and move the sanitizer in one change.
- **`quickscale_devtools` sits outside the governance architecture.** Trigger ("a second devtool
  lands, its tests gate a release, or a copied helper drifts"): **fired in modified form** — the
  SA66 conformance test imports `quickscale_devtools` and runs in the unit gate of ci.yml *and*
  publish.yml, so the release pipeline is now import-load-bearing on a package outside the
  lint/typecheck universe (verified absent from ruff.toml/mypy.ini/Makefile targets). Evaluated
  for promotion: held — absorbed as Finding 7 evidence (the taxonomy's placement is the same
  root); Option 2 relocates the knowledge into governed core. Carry with the remaining triggers
  (second devtool; helper drift from its CLI twin).
- **Module universe hand-enumerated in workflow files (new).** ci.yml and publish.yml each carry
  three hand lists (createdb, role grants, `QS_*_DB_USER` env) — six stations for every new
  module · doesn't qualify: omission fails loud for PostgreSQL modules via the SA58 guard
  (Probe A); population stable at 13 · promotes when a 14th module lands, when SA59.3 implements
  the shared provisioning script *without* deriving the module list from
  `quickscale_modules/*/`, or if any suite is found running under the `postgres` fallback
  without the guard firing.
- **Sanctioned privileged-command set is a template↔module copy-pair (new, SA68-minted).**
  `production.py.j2:_KNOWN_PRIVILEGED_COMMANDS` and `orgs/apps.py:_PRIVILEGED_COMMANDS` must
  agree, with generated-project vintage skew possible against module upgrades · doesn't qualify:
  both consumers fail closed on desync (loud boot/command failure, not silent privilege); two
  values, changes rare · promotes when a third sanctioned command lands, a vintage-skew incident
  fires in a generated project, or a third consumer of the set appears.
- **Billing webhook concurrent-duplicate window.** Trigger ("non-idempotent side effect in a
  handler"): **not fired** — `billing/services.py` verified untouched since SA41. Carry.
- **Dual child-table tenancy APIs.** Trigger ("a teams child table lands on the trigger API"):
  **not fired** — teams unscheduled; SA60 (open) owns the deferrability records; SA59.1's
  forms/0007 restricted-role failure is adjacent pressure on the same seam. Carry.
- **Mutating CLI operations have divergent compensation mechanisms.** Trigger ("a new mutating
  command hand-rolls a fifth mechanism, more reconciliation glue, or a crash git couldn't
  recover"): **not fired** — no new mutating command this delta (SA65 changed subprocess env
  scoping only). Carry.
- **`orgs/views.py` fusion.** Trigger ("teams begins extending org-facing surfaces"): **not
  fired** — 1,226 lines, verified unchanged, teams unscheduled. Carry.
- **Grandfathered option defaults multi-sourced — seventh pass.** Trigger ("a default changes in
  one station only"): **not fired** — `module_config.py` untouched this delta; T2.4/T2.5 remain
  unscheduled. Carry.

*(Carried unchanged at low priority, unprinted: hardcoded `EXEMPT_PATH_PREFIXES` in
`orgs/middleware.py`.)*

### Teams landing checklist (carried unchanged — speculative, teams unscheduled)

> Teams is not scheduled (decisions.md §Teams module status, 2026-07-10). Carried for reference
> *if* a future scheduling decision lands; full checklist in the 2026-07-09 pass text in version
> control. Additions since remain valid: the teams adapter imports
> `quickscale_core.runtime.manifest` only; teams data migrations traverse the SA68 launcher
> env contract; teams' admin subclasses `TenantModelAdmin`; **new this pass:** teams' arrival is
> the promotion trigger for the module-universe workflow-enumeration watchlist item (six hand
> stations) and must land after SA59.3's shared role-provisioning script, or it inherits the
> per-module grant duplication SA59.3 exists to remove.

### Questions that would change the ranking

- **Will SA59.3's shared provisioning script also own the `QS_*_DB_USER` wiring and the workflow
  DB lists, derived from `quickscale_modules/*/`?** If yes, the module-universe watchlist item
  dissolves when SA59.3 lands; if the script hand-lists modules again, the item promotes on
  arrival. (Affects the module-universe watchlist item; worth settling in SA59.3's design before
  implementation.)
- **Was the `NOT DEFERRABLE` composite-FK switch deliberate?** — carried, owned by SA60 (open);
  now also material to SA59.1's forms/0007 blocker. (Affects Finding 4 and the SA59 sequence.)

### Red flags (out of scope — fix now)

- **The integration gate is red at merge on `v87`.** SA59.1 was merged as a blocked checkpoint
  with unresolved pre-existing failures (orgs: 3 `test_models.py` + 6 helper-path errors; forms:
  `0007` composite-FK on restricted-role DBs; notifications: duplicate-db/ownership) and a
  77.55% mean module coverage against `test_integration.sh`'s 90% threshold — and the script
  excludes nothing, so the ci.yml/publish.yml integration jobs should currently fail. While red,
  the gate catches no *new* module-suite regressions, and every day it stays red trains
  merging-over-red. Tracked (SA59.1 blockers), user-directed stop — but consider quarantining the
  known failures (xfail-with-ticket per suite) so the gate stays green for everything else while
  SA59.1 proceeds. *Static-analysis caveat: confirm on the Actions dashboard; `gh` was
  unavailable this pass.*
- **`_session_managed_adapters` swallows `ImproperlyConfigured`**
  (`quickscale_core/tests/test_manifest_entry_point.py`, SA73): a genuinely mis-configured
  managed adapter now yields skips, not failures, in the unit path — fail-hard-audit class;
  hand off to tech-audit. Narrow fix: catch only when the module package is absent
  (`ModuleNotFoundError` cause), re-raise real config errors.
- **Autouse `organization_created` muting in orgs conftest** (SA59.1, `2b9afa6b`): every orgs
  test now runs with the signal's `send` patched out, so a broken cross-module receiver (e.g.
  CRM stage seeding) is invisible to the orgs suite — weakened-test class; hand off to
  tech-audit. The CRM-side bootstrap tests remain the only coverage of that seam.

Lenses scanned with no qualifying finding this pass: data/state integrity, trust boundaries
(SA68 re-verified closed; privilege seam probed and exonerated), module cohesion beyond
Findings 1/7, consistency/failure models, observability, API contracts, testing architecture
(the gate split is census-tracked; its soft edges are red-flagged, not finding-grade),
design conflicts (SA69's exception-identity record landed; linter-docstring drift absorbed into
Finding 1), concurrency, security architecture, performance. Governance/gate lens (§5.XV)
produced the census updates, the SA66 gate-integrity residuals (Finding 7), and both probes
rather than a separate finding.

---

## Autopsy — 2026-07-10 (re-run, delta pass — first run on the V2 prompt)

> Superseded by the 2026-07-11 delta pass above, which re-verified all open findings' evidence
> anchors, fix-regression-audited the SA65/SA66/SA68/SA73 closeouts and the SA59.1 checkpoint
> batch, and re-measured both change-cost probes. The 2026-07-10 pass's full text (Finding 7
> opened, Finding 6 closed via SA68, enforcement census introduced) is preserved in version
> control. This stub heading is kept so existing links resolve.

---

## Autopsy — 2026-07-09 (re-run, delta pass) and module-by-module deep pass

> Superseded by the 2026-07-10 delta pass, which re-verified all open findings' evidence
> anchors directly, audited the SA57–SA64 closeout batch for fix-regressions, and read the
> `628c7d28` unlabeled-behavioral commit in full. The 2026-07-09 passes' full text (Finding 6
> opened, module-by-module verdicts, five held candidates) is preserved in version control. This
> stub heading is kept so existing links resolve.

---

## Autopsy — 2026-07-07 (re-run, delta pass)

> Superseded by the 2026-07-09 delta pass, which re-verified all open findings' evidence
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
- 2026-07-10 (re-run, delta pass over the SA57–SA64 closeout batch; first run on the V2 prompt —
  falsification pass, enforcement census, change-cost probes, and fix-regression audit added) —
  **four findings still-open (two narrowed), one new finding.**
  `dr-engine-module-circular-lattice`: still-open, **unchanged** — first quiet delta in four
  passes (no DR work landed; no new lattice stations; `LEGACY_ALLOWED_IMPORTS` did not grow);
  Option 2 (persistence port) confirmed scheduled for the next planning cycle.
  `db-privilege-mode-procedural`: still-open, **substantially narrowed** — SA63 passed the
  fix-regression audit (mechanism partially removed, not relocated; fail direction preserved; no
  new stations): the launcher env-pair contract landed, local's argv ladder deleted, the
  createcachetable collision fixed and verified by new generated-project boot smoke tests; Probe
  B re-measured a new privileged command at one station, disconfirming the prior "up to three
  places" claim for new commands; residual scope is the migrate path's three deciders
  (`production.py.j2:185,195` argv branches, `orgs/apps.py` `_is_migrate_command()`) plus the
  one-bit hatch overload (SA59's blanket test-harness export is its live consequence); horizon
  downgraded now → 6–18 months. **New Finding 7 `generated-file-ownership-unmodeled`**: the
  generator has no per-file ownership contract; `quickscale_devtools/beta_migration.py:43–115`
  hand-encodes the taxonomy in eight unlinked tuples with no derivation from the template tree
  and no gate; live gap — SA63's `start.sh` is absent from `IN_PLACE_INFRASTRUCTURE_TARGETS` and
  fresh-first keeps the donor's `production.py`, so each SA63 file is missed by one migration
  path (immediate manual verification red-flagged).
  `deletion-invariants-per-boundary-reimplementation`: still-open, deferred — zero `pre_delete`
  receivers re-verified; delta touched none of its files.
  `org-model-universe-hand-enumerated`: still-open, deferred — literals verified untouched; the
  2026-07-09 decision-record caution is now owned by SA60 (open, Track 1).
  Prior red flags reconciled: DR media silent-local coercion → **fixed** (SA57, verified
  `ModuleNotFoundError`-narrow with fail-hard on all other errors at both sites); social admin
  prototype → **fixed** (SA64, both admins verified on `TenantModelAdmin`, prototype deleted);
  createcachetable/boot-guard collision → **fixed** (SA63, verified `start.sh.j2:59` + smoke
  tests); unvalidated TOML write → **fixed** (SA62, all three CLI splice sites verified through
  `_write_validated_toml`); git-tracked test artifacts → **fixed** (SA61/SA25, `git ls-files`
  verified clean); undocumented tenancy-semantics changes → **tracked** (SA60 open; records not
  yet written). Watchlist trigger evaluations (V2 discipline): commons — not fired, carried;
  TOML-splicing — fired in modified form (devtools copy), retired into Finding 7 + new
  devtools-governance item; billing webhook — not fired (untouched since SA41), carried;
  dual child-table API — not fired, carried (SA60 pending); CLI compensation divergence — fired
  in modified form (beta_migrate's checkpoint model), held (no cross-mechanism reconciliation;
  operates on external trees), carried; orgs-views fusion — not fired (1,226 lines, unchanged),
  carried; grandfathered defaults — not fired (sixth pass; listings apply-shim filled a station
  correctly), carried; deploy-config contract — substantially landed (boot smoke harness),
  narrowed to the doc-only paragraph. Questions: local-argv-ladder intent → **answered by SA63**
  (deleted; env pair is the contract), retired; `NOT DEFERRABLE` deliberateness → carried, owned
  by SA60. New red flags: SA63 beta-site rollout verification; `ImproperlyConfigured` re-homing
  undocumented (`628c7d28` — third consecutive delta with semantics under a housekeeping
  message); apply's import-time subprocess-env snapshot (tech-audit hand-off). New watchlist
  item: `quickscale_devtools` outside the governance architecture. Sound decisions: boot guard
  strengthened (SA58 `rolsuper`); the generated-project boot smoke harness recorded as the
  runtime-confirmation layer prior passes asked for.
- 2026-07-10 (roadmap cleanup) — **Red flag resolved:** the `ImproperlyConfigured` re-homing
  decision-record gap is closed (SA69 — `decisions.md §ImproperlyConfigured-Exception-Identity`
  now records the exception-identity split, which class a contracts-layer vs. a Django-runtime
  catcher should import, and the housekeeping-label-discipline watch item; the three named
  adapter docstrings are corrected from the Django class to the first-party class). Removed from
  the Red flags section above. The lint/naming guard for the two same-named classes remains an
  open watch item per the decision record (also tracked in tech-audit.md's Notes section), not
  promoted to its own finding.
- 2026-07-11 (roadmap cleanup) — **Finding 6 (`db-privilege-mode-procedural`): closed.** SA68
  finished Option 1 (recommended path): `start.sh.j2`'s migrate line now carries the same env
  pair as its createcachetable line; `production.py.j2`'s `elif "migrate" in sys.argv` branch and
  `orgs/apps.py`'s `_is_migrate_command()` are both deleted — no argv inspection remains anywhere
  in the privilege-selection path. The one-bit hatch overload flagged in the recommendation is
  also resolved: the explicit `QUICKSCALE_PRIVILEGED_COMMAND`/`QUICKSCALE_NON_DB_COMMAND` pair
  replaces the single `QUICKSCALE_ALLOW_BYPASSRLS` flag for launcher sanction, recorded in
  `decisions.md §Launcher One-Shot Command-Env Contract (SA68)`. Summary table, enforcement
  census, fix-order, and sound-decisions sections updated; full Finding 6 narrative removed per
  this document's own closed-finding convention (prior text in version control). Detail in
  CHANGELOG.md (SA68 entry). **Finding 7 (`generated-file-ownership-unmodeled`): first step
  landed (not closed).** SA66 shipped Option 1's conformance gate — the beta-migration file
  taxonomy is now derived against the template tree with zero unclassified gaps; Option 2
  (generator-emitted ownership manifest) stays open, to be picked up if a third consumer or a
  public update command appears. **Red flag resolved:** `apply`'s import-time subprocess-env
  snapshot is fixed (SA65, closing tech-audit.md TA53) — removed from the Red flags section
  above. Also closed the matching watchlist item (deploy-time configuration contract for
  generated apps) now that `decisions.md` carries the SA68 paragraph.
- 2026-07-11 (roadmap cleanup) — **Red flag closed as out-of-scope:** "verify SA63 actually
  reaches `experto-ai-web` and `bap-web`" (SA67) is retired, not resolved by evidence — a new
  standing scope boundary, `decisions.md §Beta-Site External Verification Scope`, establishes
  that live deployed-state verification for the two beta sites is structurally unreachable from
  this monorepo (no repository or deployment access exists or is expected to exist from a
  coding-agent session or CI job here) and is therefore closed on discovery going forward rather
  than left open pending access. The repo-local half of the original red flag — the in-place
  path missing `start.sh`, the fresh-first path keeping the donor's `production.py` — was the
  actual defect and was already fixed by SA66's conformance gate. The "beta sites deploy without
  Redis?" Question is updated to reflect the same boundary: it cannot be answered by a future
  audit pass and is now a `beta-site-migration.md` maintainer to-do instead. Full detail in
  CHANGELOG.md (SA67 entry) and `docs/technical/roadmap.md` (Track 3, now clean).
- 2026-07-11 (re-run, delta pass over `ae8c386e..HEAD` — the SA65/SA66/SA68/SA69/SA73 closeouts
  plus the three SA59.1 checkpoint commits) — **four findings still-open (Finding 7 narrowed),
  zero new findings.** Fix-regression audits: **SA65 clean** (import-time env snapshot deleted;
  `env=None` default; scoped env only at the two nested CLI call sites — mechanism removed).
  **SA68 clean, Finding 6 closure re-verified in code** (zero argv inspection on the privilege
  path; two-signal contract validated fail-closed at both consumers); one minted station recorded
  as a new watchlist item — the sanctioned-command frozensets are a template↔module copy-pair
  with no sync gate, both halves fail-closed. **SA66 audited** (Finding 7 first step): the gate
  genuinely derives the emitted-file universe from the template tree and pins both ownership
  policies (`start.sh` in-place + substituted; `production.py` donor-owned by policy, recorded in
  `decisions.md §Generated-File Ownership`); residuals cited in the updated Finding 7 — the
  test-side copy of the generator's emission routing (incl. hardcoded `("showcase_react",)` for
  non-Jinja files), the unenforced decisions-rationale invariant, and devtools' placement outside
  the lint/typecheck universe while now import-load-bearing for the release gate. **SA73
  audited**: quality-gate plumbing, but its `mypy.ini` `ignore_missing_imports` for
  `quickscale_modules_backups.*` is a new Finding 1 cycle carrier (recorded), and its
  `_session_managed_adapters` fixture swallow is red-flagged. **SA59.1 checkpoint audited**: the
  blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export is verified gone from the unit path; ci.yml and
  publish.yml both run the split (DB-free unit + restricted-role integration with the SA58 guard
  live) — census rows 2/3 strengthened/restored, new rows 14/15 added; the currently-red
  integration gate is red-flagged (tracked, SA59.1 blockers). Probes: A ("14th module") — six
  ungated hand stations in workflows, fail-loud for PG modules via the guard, verdict watchlist;
  B ("third privileged command") — three stations, copy-pair fail-closed, verdict watchlist,
  Finding 6 stays closed. Findings: 1 still-open (second quiet delta; carrier +1); 7 still-open,
  **narrowed**, horizon now → 6–18 months (silent-miss class closed by the gate); 2 still-open,
  deferred (zero receivers re-verified; first step scheduled as SA70); 4 still-open, deferred
  (literals untouched; SA60's urgency raised by the forms/0007 restricted-role failure).
  Watchlist evaluations: commons — not fired, carried; devtools-governance — fired in modified
  form (release gate imports devtools), held, absorbed into Finding 7 evidence, carried; billing
  webhook — not fired, carried; dual child-table API — not fired, carried; CLI compensation —
  not fired, carried; orgs-views fusion — not fired (1,226 lines), carried; grandfathered
  defaults — not fired (seventh pass), carried; two new items (module-universe workflow
  enumeration; privileged-command copy-pair). Prior red flags: both 2026-07-10 flags already
  closed in the log (SA67 out-of-scope; SA65 resolved — SA65 re-verified in code this pass).
  Questions: "beta sites without Redis" retired (SA67 scope boundary); "production.py
  donor-owned deliberate?" **answered by SA66** (deliberate; recorded and test-pinned) — retired;
  `NOT DEFERRABLE` carried (SA60); one new question (does SA59.3's provisioning script own the
  module-list derivation?). New red flags: red integration gate at merge; the
  `ImproperlyConfigured` fixture swallow; autouse `organization_created` muting (both
  tech-audit hand-offs).
