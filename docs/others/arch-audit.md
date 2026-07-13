# Structural Autopsy: QuickScale

> This file is regenerated on each autopsy run to state **present reality for planning**: the
> current orientation, the open findings in full detail, and a curated watchlist. Closed findings
> exist only as dated lines in the **Reconciliation log** at the bottom (closeout detail lives in
> [CHANGELOG.md](../../CHANGELOG.md)); version control preserves prior full text. Finding IDs are stable
> across runs.

---

## Autopsy — 2026-07-13 (re-run, delta pass over the SA77/SA79/SA59.3–.4/SA80/SA82/SA87 restricted-role closeout batch)

### Orientation (2026-07-13)

QuickScale is a solo-maintained (Experto-AI/Victor Rocco) Python 3.13/3.14 + Poetry monorepo
(VERSION 0.87.0, integration branch `v87`) that is two archetypes at once: a **Django project
generator** (`quickscale_core` Jinja2 templates + plan/apply engine + DR engine; `quickscale_cli`
Click surface) and a **module workspace** of 13 shipped first-party Django modules (teams still
README-only, re-verified). Generated apps: Django 6 + PostgreSQL 18, single-service Railway;
tenancy enforced twice (fail-closed `TenantManager` + FORCE RLS with the AF9 execute-wrapper),
backstopped by the SA58 boot guard (rejects `rolsuper`/`rolbypassrls`). Severity floor unchanged:
CLI is single-process local; generated apps are single-service WSGI; **tenant isolation is the
highest-blast property.**

**Commit-delta classification (§2f).** The last *code-reading* autopsy was 2026-07-11 (base
`ae8c386e`); the 2026-07-12 entry was a docs-only roadmap-reconciliation pass (SA74/75/76/60/70
already reconciled there). This pass classifies the genuinely new code delta `6cc9ab74..HEAD`
(the 2026-07-12 closeout commit to HEAD): *closeouts* — SA77 (`afbd0af3`, orgs restricted-role),
SA78 (`37cc7ff8`), SA79 (`223b3134`, forms/0007 backfill), SA59.3/SA59.4/SA59-umbrella
(`6deaddd6`/`6453a8ea`), SA80 + SA80.2/.3a/.3b (`ed7c84dd`/`657cff28`/`fc15d4e1`), SA82
(`414466f9`, quarantine removal + full-gate rerun), SA87 (backups restore username), all
verified below; *housekeeping* — ~14 roadmap/CHANGELOG commits plus merges; *unlabeled-behavioral*
— `657cff28` ("fix(cli): isolate poetry install/lock subprocess env") is a real behavioral change
but correctly labeled and ticket-shaped, and `f6a8191e` ("Update dependencies across multiple
modules") is housekeeping-shaped (poetry.lock + six pyproject version bumps + two doc lines) and
**verified to carry no first-party code semantics** (the only template touched this delta,
`production.py.j2`, took a one-line f-string quote-style lint fix in `f4cb9711`, not a behavioral
change). **The entire first-party code delta is five files, all read fully:** `apply_command.py`
(+24, new `_isolated_poetry_env`), `forms/…/0007_new_organization_ownership.py` (+28,
`SET LOCAL operator_access`), `scripts/test_integration.sh` (+27, SA80.2 `QS_*_DB_USER` block),
`production.py.j2` (cosmetic), `Makefile` (test-cov flow, `f4cb9711`). Verified untouched by git
log this delta (open-finding seams): `dr_engine/`, `quickscale_core/runtime/`,
`scripts/check_module_core_imports.py`, `mypy.ini`, `backups/services.py`, `orgs/models.py`,
`orgs/tenancy.py`, `orgs/purge_organization.py`, `orgs/apps.py`, `auth/views.py`,
`quickscale_devtools/beta_migration.py`.

**Growth direction (planning surface, roadmap.md 2026-07-13).** SA59 umbrella closed; SA77/SA79
closed by the SA82 full-gate rerun. The **integration gate is red** on four independent, still-open,
"unknown-root-cause" restricted-role residuals surfaced *by* removing the BYPASSRLS quarantine:
SA83 (blog, 86 RLS failures), SA84 (crm, 67 failures/20 skipped), SA85 (forms, 33 failures/8
skipped/10 errors), SA86 (listings, 6 failures). Also open: SA81 (per-module lockfile cleanup,
unrelated) and Finding 1's persistence port (scheduled next planning cycle).

**Result: one new finding, four findings still-open (all quiet — no open-finding file touched in
the code delta; anchors re-resolved and, where the code moved, corrected for freshness).** The new
finding (**Finding 8 `module-rls-context-procedural`**, ranked first) is the structural reading of
the SA83–SA86 cluster: SA82 removing the last BYPASSRLS hatch exposed *four* modules simultaneously,
which is by definition evidence that module RLS-context acquisition is procedural and was
unverified under a real restricted role — one root the roadmap has split into four parallel unknown
investigations. Fix-regression audit of the code delta: SA79's forms/0007 fix
(`SET LOCAL app.operator_access`) is clean for forms but is the *per-callsite* pattern Finding 8
warns must not be sprinkled fleet-wide; `657cff28` (poetry env isolation) is clean and ticket-shaped
but mints a second bespoke subprocess-env builder in `apply_command.py`
(`_isolated_poetry_env` alongside `_build_quickscale_env`), noted on the watchlist. The
module-universe workflow-enumeration watchlist item's **trigger fired** (SA80.2 added a *third*
`QS_*_DB_USER` hand-list, in `test_integration.sh`, comment-synced to the two workflows by line
number rather than derived) — held on fail-loud, third station recorded.

### Enforcement census (§3.4)

| # | Invariant | Enforced by | Class | Trend this pass |
|---|-----------|-------------|-------|-----------------|
| 1 | Tenant isolation on reads/writes | fail-closed `TenantManager` + FORCE RLS + AF9 execute-wrapper | structural | stable |
| 2 | No bypassing DB role at boot | orgs boot guard (`apps.py`), `rolbypassrls` + `rolsuper` | structural | stable — the SA59 blanket export is gone; the restricted-role integration gate is now genuinely load-bearing. **Gate is red** post-SA82 (expected: SA83–SA86 open; backups now clean under PostgreSQL via SA80.3b/SA87). The red gate is **Finding 8**, not a red flag |
| 3 | Admin org-scoping | `TenantModelAdmin`; tripwire = NOBYPASSRLS test posture (SA14.4) | structural + gated | stable — NOBYPASSRLS-by-default is real in the integration path |
| 4 | DB privilege selection per process | launcher env contract (`QUICKSCALE_PRIVILEGED_COMMAND`/`QUICKSCALE_NON_DB_COMMAND` + `RUNTIME_DATABASE_URL=""`) | structural | stable (SA68). Sanctioned-set frozensets ×2 (template + orgs), both fail-closed, no sync gate (watchlist); `production.py.j2` took only a cosmetic quote fix this delta |
| 5 | JSON endpoint idiom | `OrgApiBaseView`/DRF baseline + SA46 csrf-exempt CI gate | structural + gated | stable |
| 6 | Core↔module import direction | import linter (`scripts/check_module_core_imports.py`) + `LEGACY_ALLOWED_IMPORTS` (3 modules) | gated, with exceptions | stable — list did not grow (billing, crm, social); linter docstring↔dict drift persists (`:8` says "billing and CRM"; dict has 3 keys); `mypy.ini:94` backups ignore persists (Finding 1 carrier) |
| 7 | Module manifest copy-pairs (module.yml ×2) | CI byte-identical sync gate | gated | stable |
| 8 | Tenant-model universe **membership** | SA15.3/SA45/SA49 derivation gates | gated | stable |
| 9 | Tenant-model purge **order** | hand-ordered `_DELETE_SPECS` (`purge_organization.py:64`), comment-justified | convention | unchanged (Finding 4); SA60 policy ratified, purge-order derivation still deferred to teams |
| 10 | Deletion invariants at account boundary | one canonical check + SA70 `pre_delete` backstop | convention + backstop | stable (Finding 2) — `apps.py:194–206` receiver + `models.py:165/298/329` re-verified |
| 11 | pyproject TOML write safety | `_write_validated_toml` (3 CLI splice sites) | structural per package | stable; devtools copy unchanged |
| 12 | Generator-emitted file ownership for upgrades | SA66 conformance gate (emitted-file universe derived from templates) | gated | stable (Finding 7); residual hand-synced routing copy unchanged |
| 13 | Generated-project boot correctness | `test_generated_project_runtime.py` boot smoke harness | gated | stable |
| 14 | Module suites run under a restricted DB role | ci.yml + publish.yml role provisioning **+ now `test_integration.sh` (SA80.2)** `QS_*_DB_USER` wiring | gated | **3rd station added** — the `QS_*_DB_USER` list is now hand-enumerated in *three* places (ci.yml, publish.yml, test_integration.sh:368–382), the new one comment-synced by literal line-number reference (`:373` "Matches ci.yml lines 399-410 and publish.yml 160-171"), not derived from `quickscale_modules/*/`. Omission still fails **loud** (postgres fallback → boot guard). Watchlist trigger fired |
| 15 | Release-gate test scope | publish.yml `test` job (same split as ci.yml) | gated | stable |
| 16 | **Cross-org RLS context in module migrations/fixtures** | per-migration `SET LOCAL app.operator_access` — **orgs and forms only** | **convention** | **NEW row (Finding 8)** — blog/crm/listings have cross-org data migrations (`0002_enable_rls`, `0009_add_note_organization_ownership`, …) that acquire **no** RLS context; exposed by SA82 as SA83/84/86; no shared migration helper or gate |

### Summary table

| # | ID | Horizon | Confidence | Size | One-line problem |
|---|----|---------|-----------|------|------------------|
| 8 | `module-rls-context-procedural` | now | Medium | M | Module migrations and test fixtures acquire elevated RLS context per-callsite (only orgs/forms do it at all); the invariant was unverified under a real restricted role until SA82, which exposed four modules at once — now being fixed as four unknown-root tickets, not one root |
| 1 | `dr-engine-module-circular-lattice` | now | High | M | DR logic lives in core but its state/lifecycle live in the backups module; the cycle is held by hand-synced symbol stations, a linter exception list, and a mypy ignore — third consecutive quiet delta; persistence port still scheduled |
| 7 | `generated-file-ownership-unmodeled` | 6–18 months | High | M | SA66's gate closed the silent-miss class but the taxonomy and the gate's emission-path mapping remain hand-synced copies of generator knowledge in the ungoverned devtools package |
| 2 | `deletion-invariants-per-boundary-reimplementation` | deferred (teams) | High | S | Last-owner check now has an SA70 `pre_delete` backstop; no domain-owned deletion service consolidating other boundaries' invariants (e.g. billing) |
| 4 | `org-model-universe-hand-enumerated` | deferred (teams) | High | M | Tenant-model membership is derivation-gated; purge *order* is hand-written; SA60 ratified the deferrability policy |

---

### Finding 8: Module RLS-context acquisition is procedural — one BYPASSRLS-removal exposed four modules at once

- **ID:** `module-rls-context-procedural`
- **Rank rationale (blast radius × likelihood):** blast is the release gate (red today) plus the
  *confidence* that every shipped module's RLS interaction is correct under real enforcement;
  likelihood is 1 — the trigger has already fired (SA82), four modules are already failing, and
  every future module/migration pays the same tax. Highest active blast×likelihood this pass.
- **Horizon & trigger:** `now` — already causing pain: the integration gate is red on SA83–SA86,
  four open tickets. The forward trigger for *new* instances is any new module or any new cross-org
  data migration.
- **Confidence:** Medium — **High on the structural shape** (verified: NOBYPASSRLS-by-default test
  posture since SA14.4; the blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export removed at SA59.1 and the
  quarantine at SA82; only `orgs` and `forms` migrations acquire `operator_access`; blog/crm/listings
  have cross-org `organization_id` data migrations that set no RLS context). **Medium on the
  per-module specifics** — the roadmap records SA83–SA86 root causes as "unknown/unconfirmed," and I
  cannot run the gate (read-only, needs PostgreSQL), so I have not confirmed each of the 192 failures
  is the same class. Verification step named below.
- **Context dependence:** `wrong-for-now` on the **enforcement-posture** dimension that just flipped
  — the BYPASSRLS hatch is now gone and will not return (a protected sound decision), which is
  precisely what makes the pre-existing procedural handling wrong-regardless going forward.
- **Problem:** there is no shared, structural contract by which a module's schema-touching code
  (data migrations, test fixtures, and any runtime path that must read across orgs) *declares and
  acquires* the RLS context it needs; each module hand-rolls it (or omits it), the blanket bypass
  hatch masked every omission for the whole SA14.4→SA82 window, and its removal exposed four modules
  simultaneously — the definition of a procedural, unenforced cross-cutting invariant.
- **Evidence (established this pass):**
  - Test posture: every module's `tests/settings.py` declares NOBYPASSRLS-by-default and requires
    `@pytest.mark.bypass_rls` (blog `settings.py:9–13`, listings `:8–12`, crm `:5–9`, forms `:5–9`),
    but each falls back to `USER=postgres` when `QS_<MOD>_DB_USER` is unset — real enforcement
    depended entirely on CI wiring the restricted role, which the blanket export defeated until
    SA59.1/SA82.
  - RLS-context acquisition census: `grep -rl "operator_access\|SET LOCAL app\.\|current_org_id"`
    over `quickscale_modules/*/src/*/migrations/` returns **only** `orgs` (`0005`, `0006`) and
    `forms/0007`. blog (`0002_enable_rls`, `0003_refresh_rls_policies_nullif_guard`), crm
    (`0006_enforce_required_organization`, `0008_enable_rls`, `0009_add_note_organization_ownership`,
    `0010_…`), and listings (`0002_enable_rls`, `0003_…`) have cross-org `organization_id`
    backfill/RLS migrations that acquire **no** context (`grep -c` returns 0 for all).
  - The already-landed fix confirms the class: SA79's `forms/0007` added
    `schema_editor.execute("SET LOCAL app.operator_access = 'on'")`
    (`0007_new_organization_ownership.py:113–116`) so a correlated subquery over `Form` could read
    across orgs under FORCE RLS — the per-callsite fix the remaining three modules have not made.
  - The roadmap (`roadmap.md:90–132`) tracks the four as SA83–SA86, each "root cause
    unknown/unconfirmed … RLS policy violations under `quickscale_test_role`," reassigned across two
    tracks to parallelize — i.e. treated as four independent problems.
- **Counter-evidence:** searched for a shared migration/context helper modules could route through
  (none — `operator_access` is set inline where used); searched for a gate that would have caught an
  RLS-context omission earlier (none — the blanket bypass export *was* the reason the gate stayed
  green); considered whether this is purely a test-environment artifact with no production surface
  (**strongest disconfirming fact:** in production, generated apps run `migrate` under the SA68
  privileged one-shot command as a superuser-class role, so these backfills succeed in prod
  regardless — the migration-time failures are test-posture, not a live data-loss bug). That caveat
  bounds the *severity* (this is not "tenant data leaks in prod") but does not dissolve the finding:
  the failures also include runtime-query and fixture paths (forms' "10 errors," crm's "20 skipped"),
  and without a shared contract you cannot distinguish, among 192 failures, a benign "test assumed
  bypass" from a real "a NOBYPASSRLS runtime read path is missing its context" — which is exactly
  the class that *would* bite production.
- **Why it compounds:** cost is (modules × cross-org migrations × runtime read paths) of remembered
  RLS-context calls, with no enforcement that any given one is present; the failure surfaces only at
  full-integration-gate time, and — the compounding already realized — the remediation is four
  parallel "unknown root" investigations for one structural pattern. Worse, the obvious per-ticket
  fix is to copy SA79's `SET LOCAL operator_access` into each failing migration, which **relocates**
  the procedural pattern module-by-module rather than removing it (a §0 fix-regression in the
  making). Built on top: the release gate itself, the four open tickets, and every future module.
- **Detection signal:** the red integration gate is the loud signal today. To confirm the shared
  root and separate benign from real: run one module's restricted-role suite
  (`QS_BLOG_DB_USER=quickscale_test_role … pytest quickscale_modules/blog`) and bucket failures into
  migration-time (backfill blocked by FORCE RLS), fixture-time (test creates cross-org data without
  context), and runtime-query (a view/manager path that runs NOBYPASSRLS in prod too). The third
  bucket is the only production-severity one and must be triaged out of the pile first.
- **Steelman:** SA59.1→SA82 *is* the correction — removing the hatch and surfacing the failures is
  the system working as designed, and four independent small fixes are a legitimate way to drain
  them for a solo maintainer. Migrations run privileged in production, so most of these are
  test-hardening, not bugs. This holds *if* someone first confirms no failure is a real
  NOBYPASSRLS-in-production read-path gap and *if* the fix isn't just operator_access-sprinkling. If
  both hold, downgrade to a testing-architecture cleanup.
- **Correct shape:** a module acquires elevated RLS context through exactly one declared mechanism
  (a shared migration/operations helper or a marked context manager owned by orgs/core), so (a) a new
  cross-org migration cannot silently depend on BYPASSRLS, (b) the gate distinguishes
  declared-elevation from assumed-bypass, and (c) a single diagnosis covers all modules rather than N
  unknown-root tickets.
- **Options:**
  1. **Shared migration/ops RLS-context helper (recommended).** orgs (the de facto module commons)
     exports a `with operator_access_migration(schema_editor):` (or a `RunPython` wrapper) that every
     cross-org data migration uses; a conformance gate flags any module migration that writes
     `organization_id` across orgs without it. Removes the per-callsite convention; one diagnosis for
     SA83–SA86. M effort.
  2. **Per-ticket operator_access, no shared seam (the path SA83–SA86 are drifting toward).** Copy
     SA79's inline `SET LOCAL` into each failing migration/fixture. S per ticket, but explicitly
     relocates the procedural pattern into three more modules and leaves the invariant ungated — a
     fix-regression by §0.
  3. **Split test-posture from production-posture explicitly.** Accept that migrations run privileged
     and gate only the *runtime* read paths under NOBYPASSRLS (bucket 3 above), documenting that
     migration/fixture elevation is a test-harness concern with a helper. M; narrows the gate to what
     actually maps to production risk.
- **Recommendation:** Option 1 — before (or as) SA83–SA86 land, so the four tickets share one
  diagnosis and one seam instead of minting three more inline copies. · **Size:** M · **First step:**
  triage one module's failures into the three buckets to confirm the root and size the runtime-path
  subset; then lift SA79's `operator_access` migration idiom into an orgs-owned helper and point the
  first fix (blog, largest at 86) at it.

---

### Finding 1: DR domain is split across the core↔module boundary into a circular import lattice

- **ID:** `dr-engine-module-circular-lattice`
- **Rank rationale (blast radius × likelihood):** every DR feature and every new module adapter
  crosses this seam; empirically ~1 compounding instance per batch for three batches before the
  current three quiet deltas. Quiet = absence of trigger (no DR work), not absence of mechanism.
- **Horizon & trigger:** `now` — Option 2 (persistence port) is scheduled for the next planning
  cycle; any DR feature or new module adapter landing before it pays the tax.
- **Confidence:** High — all edges re-verified in current code this pass.
- **Context dependence:** wrong-regardless — the tax is paid at current scale by a solo maintainer.
- **Problem:** the DR engine's logic was extracted into core while its persistent state
  (`BackupArtifact`, `BackupPolicy`) and Django-facing entry points stayed in the backups module —
  neither side can import the other top-down, so the system holds the cycle together with
  lazy-loading tables, a re-export shim, a hand-synced `__all__` literal, a per-module linter
  exception list, and a mypy ignore.
- **Evidence (anchors re-resolved this pass; the DR facade moved and is corrected):**
  - Core → module: `dr_engine/orchestration.py:80–85` still imports
    `quickscale_modules_backups.models` (`BackupArtifact`, `BackupPolicy`, `BackupSnapshot`) at
    module level (`# noqa: E402 # isort:skip`).
  - Combined-facade hand-synced literal `__all__`: **now at
    `quickscale_core/runtime/__init__.py:39–42`** (was cited as `runtime/__init__.py:36–43`; the
    `dr.py`/`manifest.py` split is intact, comment at `:39–40` "When adding a new public symbol to
    dr.py or manifest.py, add it here too. The compatibility checker will catch any mismatch").
  - `LEGACY_ALLOWED_IMPORTS`: **the linter is at `scripts/check_module_core_imports.py:60–82`**;
    keys are `billing`, `crm`, `social` — did **not** grow this delta. Docstring drift persists:
    `:8` and `:15` say exceptions are "limited to billing and CRM adapter" while the dict has three
    keys and `:52`/`:55` name social — the gate's own documentation disagrees with its allowlist.
  - Cycle carrier `mypy.ini:94–95` (`[mypy-quickscale_modules_backups.*] ignore_missing_imports =
    True`, SA73) still present — the type-check gate permanently skips resolving the core→module edge.
  - Module → core: `backups/services.py` re-export shim + SA54's gated copy-pair (threshold param +
    signature-pin test) unchanged (verified untouched by git log this delta).
- **Counter-evidence:** searched the delta for new lazy-table entries, facade `__all__` growth, new
  linter exceptions, or new per-package mypy ignores — none landed (dr_engine untouched since SA73,
  which was audited last pass). Roadmap still names the persistence port as scheduled. Nothing
  disproves the mechanism; the third quiet delta shows only that no DR work happened.
- **Why it compounds:** every DR feature touches up to six stations (orchestration function + dr.py
  lazy table + dr.py `__all__` + facade literal `__all__` + services shim + adapter signature); every
  boundary-crossing invariant becomes a gated copy-pair; every new module whose adapter needs
  manifest surface either adds a linter exception or pays the cycle. Built on top: all backups
  management commands, admin restore/create/prune, the DR CLI, apply/deploy DR integration, the
  social adapter's import path.
- **Detection signal:** growth of `_LAZY_*` tables, the facade `__all__`, `LEGACY_ALLOWED_IMPORTS`,
  or per-package mypy ignores in any diff; any diff editing one side of a gated copy-pair.
- **Steelman:** each mechanism is a standard pattern, all are gated, and generated apps ship
  backups+core together so the cycle never bites end users at runtime. It failed on evidence three
  consecutive batches before the quiet stretch; quiet deltas do not restore it.
- **Correct shape:** imports across the core↔module boundary form a DAG (modules → core only); no
  underscore-private name crosses a package boundary; a boundary-crossing invariant has exactly one
  implementation; adding a module adapter requires zero linter exceptions.
- **Options:**
  1. ~~Registration-not-import + facade split~~ — **done** (SA44 + the `runtime/` package); clarified
     the surface but did not remove the cycle.
  2. **Persistence port (the live option, scheduled).** Core defines protocols for artifact/policy
     persistence; the backups module implements and injects them at app-ready. Kills
     `orchestration.py:80`, the lazy tables, the SA54 copy-pair class, and the mypy ignore's reason to
     exist. M–L.
  3. **Invert ownership.** Move all Django-model-touching orchestration into the backups module; core
     keeps pure primitives. Largest migration; complicates the CLI's non-Django DR paths.
- **Recommendation:** Option 2, as scheduled — land it before the next DR feature or module adapter.
  · **Size:** M remaining · **First step:** define the artifact/policy persistence protocol in core
  and port `restore_admin_uploaded_backup` (the SA54 seam) onto it.

---

### Finding 7: Generated projects have no file-level ownership contract — the upgrade path re-encodes it by hand

- **ID:** `generated-file-ownership-unmodeled`
- **Rank rationale (blast radius × likelihood):** blast is the deploy/infra correctness of the two
  production sites (`experto-ai-web`, `bap-web`) plus every future generated project's upgrade story;
  likelihood dropped after SA66 turned the silent-miss class into a CI failure.
- **Horizon & trigger:** `6–18 months` — fires on a third consumer site, a public "update my
  generated project" command, a new theme, or a new dynamically generated artifact.
- **Confidence:** High — SA66 diff, conformance test, and decisions.md record read in prior passes;
  `beta_migration.py` verified untouched this delta.
- **Context dependence:** wrong-for-now on the **consumer-count** dimension; wrong-regardless at a
  third site / second operator / public update command.
- **Problem:** the generator has no machine-readable, generator-owned statement of per-file
  ownership — the taxonomy lives as hand-written tuples in the maintainer migration tool, and the
  SA66 conformance gate holds them honest by *re-implementing the generator's template→emitted-path
  routing inside the test* rather than consuming a mapping the generator exports.
- **Evidence (carried; files verified untouched this delta):**
  - `test_beta_migration_ownership_conformance.py`'s `_THEME_DEST_MAP`/`_THEME_SUBDIR_MAP`/
    `_map_theme_template` plus special cases and a hand entry for `poetry.lock` are a parallel copy
    of `generator.py`'s procedural emission routing (the generator exposes no declarative mapping).
    `_theme_non_jinja_emitted_paths` hardcodes `("showcase_react",)` — a future theme's non-Jinja
    files would be silently absent from the enumerated universe (the residual silent direction).
  - decisions.md rule 3 requires each `INTENTIONALLY_UNMANAGED` entry to have a documented rationale,
    but `test_intentionally_unmanaged_entries_have_documented_rationale` asserts only non-emptiness.
  - `quickscale_devtools` remains outside the lint/typecheck universe (absent from `ruff.toml`,
    `mypy.ini`, Makefile targets; present only as a path dep + on `pythonpath`), yet the conformance
    test importing it runs in the unit gate of ci.yml **and** publish.yml — the release pipeline is
    import-load-bearing on an ungoverned package.
- **Counter-evidence:** searched for a generator-exported emission mapping (none), a decisions.md↔tuple
  cross-check (none), devtools lint/type coverage (none). Strongest disconfirming fact: the gate is
  real, derivation-based, CI-enforced — the `.j2` silent-miss class cannot recur. That narrows the
  finding to its remaining copies; it does not close it (the correct shape exists nowhere).
- **Why it compounds:** every generator routing change (new theme, subdir mapping, dynamic artifact)
  needs a matching hand edit inside the conformance test; taxonomy judgments stay maintainer-memory
  encoded in tuples the type checker and linter never see. Cost grows O(themes × dynamic artifacts ×
  consumer sites). The devtools TOML-splice copy (`beta_migration.py:597` twin of
  `module_dependency_sync.py:223`) is the second manifestation.
- **Detection signal:** a conformance-gate failure naming an unclassified path is the loud (good)
  signal; the silent direction is a new theme/dynamic artifact absent from the test's universe —
  instrument by asserting the test's enumerated-universe size against a real generated tree in the
  boot smoke harness.
- **Steelman:** Option 1 was this audit's own scoped interim; hand-curated tuples encode judgment
  naive derivation would get wrong; the emission-routing copy fails loud in most divergence
  scenarios; the maintainer is the only operator. Holds until a third consumer or a public update
  command.
- **Correct shape:** the generator owns a single machine-readable per-file ownership statement
  (generator-owned / user-seeded / protected / unmanaged), emitted with each project or exported as
  a routing API; upgrade tooling and the conformance gate consume it; no second implementation of
  the template→emitted-path mapping exists anywhere.
- **Options:**
  1. ~~Derivation gate over the existing lists~~ — **done** (SA66); closed the silent-miss class at
     the cost of one hand-synced mapping copy.
  2. **Generator-emitted ownership manifest (the live option).** The generator writes per-file
     ownership/provenance into project state, or exports the emission mapping as a function;
     `beta_migration` and the conformance test derive their sets from it. M; the natural substrate
     for a public upgrade story.
  3. **Fold the upgrade path into the product.** Extend `quickscale apply`'s contract-vintage
     machinery to refresh generator-owned infra on existing projects. L; only when generated-project
     upgrades become a public feature.
- **Recommendation:** Option 2 when its trigger fires; until then the SA66 gate carries the load.
  Cheap interim if touched: export the generator's emission mapping as a function and point the
  conformance test at it, deleting the test-side routing copy. · **Size:** M remaining · **First
  step:** export the generator's emission mapping as a function (pure refactor of `_generate_project`'s
  inline destination logic) and point the conformance test at it.

---

### Finding 2: Deletion-boundary invariants are re-implemented per boundary with no domain backstop

- **ID:** `deletion-invariants-per-boundary-reimplementation`
- **Rank rationale (blast radius × likelihood):** blast is money and org integrity (orphaned live
  Stripe subscriptions, ownerless shared orgs); likelihood moderate and static while user deletion
  stays single-path and teams stays unscheduled.
- **Horizon & trigger:** `deferred` — teams unscheduled. Live trigger regardless of teams: the first
  account-deletion path that isn't `AccountDeleteView` (e.g. a GDPR erasure command).
- **Confidence:** High — re-verified this pass: `is_last_owner_with_members` (`orgs/models.py:165`)
  consumed by the lock-guarded `delete()` (`models.py:298/329`); SA70 receiver
  `_protect_last_owner_on_membership_delete` wired in `orgs/apps.py:194–206`; none of these files
  touched this delta.
- **Context dependence:** wrong-for-now → wrong-regardless if/when teams kicks off.
- **Problem:** org-domain and billing-domain rules for "what must hold when a user disappears" are
  enforced only at boundaries that choose to invoke them — there is no layer every ORM deletion path
  traverses (SA70 added a `pre_delete` backstop for the last-owner invariant specifically, not a
  general one).
- **Evidence:** unchanged — `is_last_owner_with_members()` (`orgs/models.py:165`) consumed by the
  lock-guarded `delete()` (`models.py:329`), `AccountDeleteView` (`auth/views.py:114,147–164`), both
  orgs view callsites (`orgs/views.py:808,1161`); SA70's `pre_delete` receiver on
  `OrganizationMembership` (`apps.py:205–206`) catches cascade-driven last-owner deletions. Billing's
  active-subscription-on-ownerless-org invariant has no equivalent backstop.
- **Counter-evidence:** searched again for a domain-owned deletion *service* or a billing-side
  backstop — none added this delta (the delta touched none of these files). SA70's direct
  `user.delete()` regression test remains the coverage.
- **Why it compounds:** cost is N deletion boundaries × M invariants; teams adds M, an erasure command
  adds N; billing's invariant is still uncovered.
- **Detection signal:** none today — instrument by alerting on `Organization` rows with zero OWNER
  memberships and active `Subscription` rows whose org has no members.
- **Steelman:** exactly one deletion path exists today and the operator is the maintainer. Holds
  while user deletion stays single-path.
- **Correct shape / Options:** unchanged (orgs-owned deletion service + `pre_delete` receiver backstop
  / signal-only / DB-level constraints — full text in version control). SA70 landed the first step.
- **Recommendation:** land a `pre_delete`/service backstop for the billing side if/when teams or an
  erasure command creates a second deletion path. · **Size:** S remaining · **First step:** none
  scheduled; deferred with teams.

---

### Finding 4: orgs hand-enumerates the cross-module model universe in unlinked literals

- **ID:** `org-model-universe-hand-enumerated`
- **Rank rationale (blast radius × likelihood):** the enumerations back the isolation boundary's
  bookkeeping and org-offboarding; likelihood approaches 1 if/when a teams build lands, near-zero
  otherwise except for new models in shipped modules.
- **Horizon & trigger:** `deferred` — teams unscheduled; fires independently on any new model added
  to an already-shipped module.
- **Confidence:** High — `tenancy.py:128` (`TENANT_TABLE_REGISTRY`) and `purge_organization.py:64`
  (`_DELETE_SPECS`) re-resolved and verified untouched this delta.
- **Context dependence:** wrong-for-now on the new-domain dimension.
- **Problem:** knowledge of "which models belong to an organization, and how they die" lives in
  hand-written literals inside orgs; membership is fully CI-gated, purge *order* is not.
- **Evidence:** `TENANT_TABLE_REGISTRY` (`tenancy.py:128`, bidirectionally gated); `_DELETE_SPECS`
  (`purge_organization.py:64`, hand-ordered; the SA45 gate checks membership, not orderability) —
  both unchanged. SA60 ratified the `NOT DEFERRABLE` composite-FK policy in decisions.md and added a
  cross-module conformance gate; `forms/0007`'s composite-FK contract side is aligned (the data
  backfill was the separate SA79, closed this pass).
- **Counter-evidence:** checked the delta for registry/purge-spec changes — none; the purge-*order*
  half (Option 2) is untouched by SA60.
- **Why it compounds:** every new tenant model requires K coordinated edits (marker + registry literal
  + `_DELETE_SPECS` entry at the correct position); purge-order correctness is the one property no
  gate checks — now on a uniformly `NOT DEFERRABLE` foundation, *less* forgiving of an ordering
  mistake at delete time.
- **Detection signal:** `ProtectedError` from `purge_organization`; `NOT DEFERRABLE` composite-FK
  violations surfacing mid-purge.
- **Steelman:** hand-ordered deletion is explicit, reviewable, and encodes FK subtleties naive
  traversal gets wrong; membership gates are complete and derivation-backed.
- **Correct shape / Options:** unchanged — Option 2 (derive the purge plan topologically from the FK
  graph, `_DELETE_SPECS` reduced to overrides) is the live option, if/when teams' models land.
- **Recommendation:** decision-record gap closed (SA60); purge-order derivation only when teams gives
  it a test bed. · **Size:** M remaining · **First step:** none scheduled; deferred with teams.

---

### Change-cost probes (§3.6)

- **Probe A — "a 14th module lands in `quickscale_modules/`."** Re-measured because SA80.2 minted a
  new station. Measured stations: (1) module dir + pyproject + module.yml copy-pair — gated (row 7);
  (2) manifest adapter registration — one line (or a linter exception if it deep-imports; Finding 1);
  (3–5) `ci.yml`: createdb list, role-grant list, `QS_*_DB_USER` env — three hand edits; (6–8)
  `publish.yml`: the same three lists; (9) **`test_integration.sh:368–382` `QS_*_DB_USER` block —
  new hand station (SA80.2)**; (10) the module's own `tests/settings.py`; (11) **a cross-org data
  migration must remember `operator_access` — Finding 8's ungated convention.** Derived automatically
  (zero cost): `test_integration.sh` iterates `quickscale_modules/*` for the *suites*; Makefile
  typecheck loops modules; orgs conformance-env is SA49-derived. **Seven ungated hand stations across
  three CI/script files (up from six) — omission fails loud for PostgreSQL modules** (settings
  fallback `USER=postgres` → SA58 boot guard under `QUICKSCALE_ALLOW_BYPASSRLS=0`). backups no longer
  the silent SQLite edge (PostgreSQL since SA82). **Verdict: the `QS_*_DB_USER` triplication stays
  watchlist (fail-loud); the migration-RLS-context station is Finding 8.**
- **Probe B — "add a third sanctioned privileged command to generated apps"** (Finding 6 seam,
  carried). Three code stations, two a copy-pair (`production.py.j2:_KNOWN_PRIVILEGED_COMMANDS` /
  `orgs/apps.py:_PRIVILEGED_COMMANDS`) with no sync gate across the template/runtime-library boundary;
  desync fails **closed** at both consumers. **Verdict: seam exonerated for its fail direction;
  copy-pair remains a watchlist item.** Unchanged this delta (`production.py.j2` took only a cosmetic
  quote fix).

### Fix order and interactions

1. **Finding 8 Option 1 (shared RLS-context migration helper)** — highest-value now; sequence it
   *ahead of or alongside* SA83–SA86 so the four tickets share one diagnosis and seam instead of
   minting three inline `operator_access` copies. Independent of Findings 1/2/4/7.
2. **Finding 1 Option 2 (persistence port)** — scheduled next planning cycle; independent of
   everything above.
3. **Finding 7's remainder (Option 2)** waits on its trigger; the cheap interim (export the
   generator's emission mapping, point the SA66 test at it) is independent and small.
4. Findings 2 and 4 are deferred with teams; independent.

All five findings are independent — no fix forces rework of another.

### Sound load-bearing decisions (protect these during remediation)

- **The unit/integration gate split along the DB-need boundary (SA59):** DB-free unit gate + a
  PostgreSQL integration gate running module suites under a NOBYPASSRLS/NOSUPERUSER role with the
  SA58 boot guard live. This split is *what surfaced Finding 8* — it is working exactly as designed.
  Do not regress the blanket BYPASSRLS hatch back in to get the gate green; drain SA83–SA86 through a
  real RLS-context contract instead.
- **Dual-layer tenancy enforcement:** fail-closed `TenantManager` + FORCE RLS with the AF9
  execute-wrapper, boot guard rejecting `rolsuper`/`rolbypassrls`. The `USER=postgres` settings
  fallback failing loud *because of* the guard (Probe A) is the architecture working as designed.
- **SA68's launcher env contract:** one channel (`QUICKSCALE_PRIVILEGED_COMMAND`/
  `QUICKSCALE_NON_DB_COMMAND` + `RUNTIME_DATABASE_URL=""`), consumed fail-closed by production
  settings and the boot guard; zero argv inspection on the privilege path. Keep both consumers
  fail-closed.
- **Governance by gate:** SA66's conformance gate is the house pattern (SA15.3/SA45/SA49 family)
  applied to the generator's emitted-file universe. SA60 extended it to composite-FK deferability.
  Finding 8's fix should adopt the same pattern (a conformance gate over module migrations' RLS
  context).
- **`TenantModelAdmin` as the single admin-scoping seam** and **SA47's canonical last-owner check**
  (one implementation, four consumers, lock-guarded, SA70 `pre_delete` backstop) — carried.
- **The generated-project boot smoke harness** (`test_generated_project_runtime.py`) — the
  runtime-confirmation layer to route template-contract claims through.

### Watchlist (every carried item shows this pass's trigger evaluation — §8)

- **Module universe hand-enumerated in CI/script files — trigger FIRED.** SA80.2 added a *third*
  `QS_*_DB_USER` hand-list (`test_integration.sh:368–382`), comment-synced to ci.yml/publish.yml by
  literal line-number reference (`:373`) rather than derived from `quickscale_modules/*/`. Held, not
  promoted: omission fails loud (Probe A), and the standing design question is now **answered** —
  SA59.3/SA80 chose hand-list-with-comment-sync over derivation. Promotes if the comment-sync drifts
  and a real module runs unguarded, or if a 14th module's seven-station edit is missed in review.
- **Subprocess-env construction has no single CLI policy (new, `657cff28`).** `apply_command.py` now
  carries two bespoke env-builders — `_build_quickscale_env` (`:243`, RUNTIME_DATABASE_URL scoping,
  SA65) and `_isolated_poetry_env` (`:540`, ambient-venv stripping, SA80). Doesn't qualify: localized
  to one file, both fail toward correctness, ticket-shaped. Promotes if a third ambient-env leakage
  class gets a third bespoke builder, or if a builder is needed outside `apply_command.py`.
- **Shared module-runtime code has no *written* commons rule.** Trigger ("a new shared concern lands
  somewhere other than orgs, or teams kickoff"): **not fired** — the SA26 sanitizer remains
  byte-similar copies in `blog/views.py` + `listings/views.py` (unchanged this delta). Note: Finding
  8's recommended helper *is* the next shared-commons concern (orgs owning the RLS-context idiom) —
  landing it is the write-it-down opportunity. Carry.
- **`quickscale_devtools` sits outside the governance architecture.** Trigger ("a second devtool, its
  tests gate a release, or a copied helper drifts"): **fired in prior form** (release gate imports
  devtools) — held, absorbed into Finding 7 evidence. `beta_migration.py` unchanged this delta. Carry.
- **Sanctioned privileged-command set is a template↔module copy-pair (SA68-minted).**
  `production.py.j2:_KNOWN_PRIVILEGED_COMMANDS` / `orgs/apps.py:_PRIVILEGED_COMMANDS` must agree.
  Trigger ("third sanctioned command / vintage-skew incident / third consumer"): **not fired** — only
  a cosmetic quote change this delta. Carry.
- **Billing webhook concurrent-duplicate window.** Trigger ("non-idempotent side effect in a
  handler"): **not fired** — `billing/services.py` untouched. Carry.
- **Dual child-table tenancy APIs.** Trigger ("a teams child table lands on the trigger API"): **not
  fired** — teams unscheduled. Carry.
- **Mutating CLI operations have divergent compensation mechanisms.** Trigger ("a new mutating command
  hand-rolls a fifth mechanism / more reconciliation glue / an unrecoverable crash"): **not fired** —
  `657cff28` changed subprocess env only. Carry.
- **`orgs/views.py` fusion.** Trigger ("teams begins extending org-facing surfaces"): **not fired** —
  ~1,226 lines, verified unchanged, teams unscheduled. Carry.
- **Grandfathered option defaults multi-sourced — eighth pass.** Trigger ("a default changes in one
  station only"): **not fired** — `module_config.py` untouched. Carry.

*(Carried unchanged at low priority, unprinted: hardcoded `EXEMPT_PATH_PREFIXES` in
`orgs/middleware.py`.)*

### Teams landing checklist (carried unchanged — speculative, teams unscheduled)

> Teams is not scheduled (decisions.md §Teams module status). Carried for reference *if* a future
> scheduling decision lands; full checklist in version control. Additions since remain valid: the
> teams adapter imports `quickscale_core.runtime.manifest` only; teams data migrations traverse the
> SA68 launcher env contract **and (new this pass) must use Finding 8's RLS-context helper for any
> cross-org backfill**; teams' admin subclasses `TenantModelAdmin`; teams' arrival promotes the
> module-universe workflow-enumeration item (now seven hand stations) and must land after a shared
> role-provisioning script that derives the module list from `quickscale_modules/*/`.

### Questions that would change the ranking

- **Among the SA83–SA86 failures, is any a runtime read path that runs NOBYPASSRLS in production
  too (not just a migration/fixture that runs privileged in prod)?** If yes, that subset is a
  production-severity isolation bug and Finding 8's horizon/severity rises sharply; if all are
  migration/fixture-only, Finding 8 is a testing-architecture cleanup at reduced blast. (Affects
  Finding 8; settle by bucketing one module's failures before fixing.)
- **Will the SA83–SA86 fixes go through a shared RLS-context helper, or copy SA79's inline
  `operator_access` per migration?** The latter relocates the procedural pattern into three more
  modules (a §0 fix-regression). (Affects Finding 8; settle in the first ticket's design.)

### Red flags (out of scope — fix now)

> None open this pass. The red integration gate (SA83–SA86) is captured as **Finding 8**, not a
> standalone red flag. All three 2026-07-11 red flags remain resolved (SA74/SA75/SA76 — see the
> Reconciliation log).

Lenses scanned with no qualifying finding this pass: data/state integrity, trust boundaries (SA68
re-verified closed; the migration RLS-context seam became Finding 8), module cohesion beyond
Findings 1/7, consistency/failure models, observability, API contracts, concurrency, security
architecture, performance, code-generator archetype (Finding 7 owns it). Testing architecture
(§5.VIII) produced Finding 8; governance/gate lens (§5.XV) produced the census updates (rows 14/16)
and both probes.

---

## Autopsy — 2026-07-11 (re-run, delta pass over the SA65/SA66/SA68/SA73 + SA59.1 checkpoint batch)

> Superseded by the 2026-07-13 delta pass above, which re-verified all open findings' evidence
> anchors against current code (re-resolving the moved DR facade and import-linter paths),
> fix-regression-audited the SA77/SA79/SA80/SA82 restricted-role closeout batch and `657cff28`, and
> opened Finding 8 (`module-rls-context-procedural`). The 2026-07-11 pass's full text (four findings
> re-verified still-open, Finding 7 narrowed to 6–18 months, the SA59.1 gate-split analysis, the
> SA68 privilege-contract re-verification, and both change-cost probes) is preserved in version
> control. This stub heading is kept so existing links resolve.

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
- 2026-07-12 (roadmap closeout pass) — **all three 2026-07-11 red flags resolved:** integration
  gate red at merge → **SA76** (ticketed quarantine mechanism, gate green); `_session_managed_adapters`
  `ImproperlyConfigured` swallow → **SA75** (narrowed to genuine missing-package-root only, CI
  registry assertion added); autouse `organization_created` muting → **SA74** (removed, replaced
  with opt-in fixture; the production defect it was concealing, tech-audit's TA54, is also fixed).
  **Finding 2's first step landed: SA70** (orgs `pre_delete` receiver backstop for the last-owner
  invariant on cascade-driven deletions) — finding stays open at reduced size (S remaining) pending
  a domain-owned deletion service for other boundaries (e.g. billing), deferred with teams.
  **Finding 4's decision-record caution resolved: SA60** (composite-FK `NOT DEFERRABLE` policy
  ratified in decisions.md, cross-module conformance gate added) — finding stays open pending the
  purge-order derivation (Option 2), deferred with teams. Findings 1 and 7 untouched this pass.
  Enforcement census rows 2, 9, 10 updated to reflect the above. This was a docs-hygiene/roadmap
  reconciliation pass, not a fresh code-reading autopsy — no new findings sought or opened.
- 2026-07-13 (re-run, delta pass over `6cc9ab74..HEAD` — the SA77/SA79/SA59.3–.4/SA80/SA82/SA87 restricted-role closeout batch plus `657cff28`) — **one new finding; four findings still-open (all quiet — no open-finding file touched in the code delta).** **New Finding 8 `module-rls-context-procedural`:** SA82 removed the SA76 BYPASSRLS quarantine and ran the full integration gate under the restricted `quickscale_test_role`, simultaneously exposing restricted-role RLS failures in four modules (blog SA83/86 fails, crm SA84/67+20, forms SA85/33+8+10err, listings SA86/6) — one structural root (procedural, per-callsite RLS-context acquisition, unverified under a real restricted role until now) split into four unknown-root tickets; verified statically that only `orgs` and `forms` migrations acquire `operator_access` while blog/crm/listings have cross-org data migrations that set none. Fix-regression audits of the code delta: SA79's `forms/0007` fix (`SET LOCAL app.operator_access`) is clean for forms but is the per-callsite pattern Finding 8 warns against relocating fleet-wide; `657cff28` (poetry env isolation) is clean/ticket-shaped but mints a second bespoke subprocess-env builder in `apply_command.py` (`_isolated_poetry_env` alongside `_build_quickscale_env`) — new watchlist item. `f6a8191e` ("Update dependencies") verified to carry no first-party code semantics; `production.py.j2` took only a cosmetic f-string quote fix. Findings 1/2/4/7 anchors re-resolved to current code — DR facade corrected to `quickscale_core/runtime/__init__.py:39–42`, import linter to `scripts/check_module_core_imports.py:60–82`; all four unchanged (Finding 1 third quiet delta; carrier count stable). Watchlist: module-universe workflow-enumeration item **trigger fired** (SA80.2 added a third `QS_*_DB_USER` hand-list in `test_integration.sh:368–382`, comment-synced by line number, not derived) — held on fail-loud, third station recorded, standing design question answered (SA59.3/SA80 chose hand-list). Probe A re-measured at seven ungated hand stations (up from six). Red flags: none open (the red integration gate is Finding 8). Questions: two on Finding 8 (is any SA83–SA86 failure a production NOBYPASSRLS read path; will the fixes share a helper or copy operator_access inline).
