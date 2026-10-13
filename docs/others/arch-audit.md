# Structural Autopsy: QuickScale

Audited: `451b3dbf` (`v89`) · 2026-10-13 · working tree clean · prompt: deep-architectural-audit v10

> **Re-run pass.** The prior deliverable (audited `2fd8637f`, 2026-10-08, later annotated with
> partial-fix notes on 2026-10-10) was read first. Every prior finding, watchlist item, accepted
> commitment, and red flag was re-verified against current code. The 98 non-merge commits in
> `2fd8637f..451b3dbf` were classified and the remediations went through the fix-regression
> audit (§3.5 of the prompt). The bottom line: **no new findings**, all three prior findings
> **still open**, and two remediations (SA259's gate generator and the SA267/SA268 harness
> splits) **relocated** part of Finding 3's mechanism instead of removing it. The prior pass's
> placement table is in version control (`git show 451b3dbf:docs/others/arch-audit.md`, §15);
> from this pass on, history lives in the append-only [§16 log](#16-reconciliation-log).

---

## 1. Orientation summary

**Context.** QuickScale is a **code generator plus CLI plus runtime library plus twelve
first-party Django modules**, in one monorepo. It has four Python packages (`quickscale` meta,
`quickscale_core`, `quickscale_cli`, maintainer-only `quickscale_devtools`) and twelve module
packages.

- **Stack:** Python 3.14, Django 6, DRF, PostgreSQL 18, Poetry, Jinja2. The theme is React 19,
  Vite, and TypeScript.
- **Persistence:** generated projects use PostgreSQL with FORCE row-level security in one
  shared schema. The CLI keeps desired and applied state in YAML (`quickscale.yml`,
  `.quickscale/state.yml`).
- **Two deployment realities:**
  - **(R1) Maintainer repository and release pipeline.** It runs locally and in GitHub
    Actions, publishes to PyPI, and pushes immutable `splits/<module>-module/<version>` tags.
  - **(R2) Generated projects.** Each is one Railway app plus one PostgreSQL 18 service, with
    modules embedded by git subtree. One R2 project is deployed: the beta site `bap-web`
    (generated on v0.62.0). Its replacement `bap-web-new` was generated on 2026-10-09 against a
    local pre-publication `quickscale_core-0.89.0` wheel and is waiting for the cutover
    (SA191). It has six embedded modules, a project-owned `properties` app, and no edits under
    `modules/`. This pass read it directly, read-only.
- **Configuration axes:** the 12-module selection, a per-module `QUICKSCALE_<MODULE>_ENABLED`
  flag (one off switch since SA260), orgs mode `solo`/`saas`, storage backend `local`/`s3`/`r2`,
  and deploy target local Docker or Railway. CI runs the module suites under the restricted
  role, one generated-project end-to-end lane, and (new, SA253) an offline-rendered
  generated-project automation gate. Most selection cells are exercised only through the
  per-module suites.
- **Team:** one contributor working through three agent-driven worktree tracks with a
  serialized merge queue. In the five-day delta: 98 non-merge commits and 41 merges.
- **Data and obligations:** unchanged since the prior pass. Accounts, email addresses, CRM
  contacts, form submissions, Stripe identifiers, and notification addresses; analytics go to
  PostHog. There is a user-facing deletion promise and a GDPR-capable purge. No regulatory
  regime is declared.
- **Cost:** the Railway bill is flat by decision. The dominant unit cost is maintainer and
  agent time.
- **Growth direction** ([roadmap](../technical/roadmap.md)):
  1. Publish 0.89.0.
  2. SA191's cutover of `bap-web-new`.
  3. SA204's migration freeze. The scheduling table now makes SA153 depend on SA204.
  4. SA153's property portal: Spanish React pages, prerendering, gallery child tables, and
     listing-linked CRM inquiries.

  Tracks 2 and 3 run SA267 and SA268, which bring `scripts/` under the quality thresholds.
- **Stated-versus-actual gaps:**
  - The four gaps in the prior pass's list still stand: core loads storage by name, core holds
    social's manifest module, the CLI's "independent release cadence" coexists with lockstep,
    and the theme upgrade tool is not shipped.
  - **New:** decisions call `module.yml` "the single home" of a retired setting's refusal
    (`manifest/schema.py`, SA264). At Django startup in a generated project, though, the
    refusal is read from **core's bundled snapshot** of that manifest, not from the embedded
    module's own `module.yml` (`contracts/resolvers.py:28–42`, `runtime/conventions.py:527–530`).
  - **New:** SA267's acceptance says "prefer deleting dead or redundant governance code over
    splitting it", but its slices so far split code and added parity tests (§5, Finding 3).
- **Scope:** the whole monorepo. Depth went to re-verifying the three open findings, the
  fix-regression audit of SA258, SA259, SA263, SA264, SA265, SA267, and SA268, and the
  `bap-web-new` recipient.

**Declared architecture.** These are the rules the system states about itself. They are
unchanged except where noted.
1. `decisions.md` wins every conflict and is updated first.
2. A module is a standard Django app plus one wiring block in its own `module.yml`. Core and
   the CLI hold no per-module wiring. SA265 adds that core and the CLI hold no module-name
   branches outside rule 37's reasoned exception list.
3. Modules sit on layers 0–3. Imports and name references go one way only, and core imports
   no module (rules 5 and 34).
4. Themes are generated once and are user-owned. Themes have no embed or update path.
5. Plan/apply: `quickscale.yml` holds desired state and `.quickscale/state.yml` holds applied
   state. Writes are atomic and held under an advisory lock.
6. Fail hard. Templates render under `StrictUndefined`.
7. PostgreSQL only. Tenant isolation is FORCE RLS under a `NOSUPERUSER NOBYPASSRLS` runtime
   role, with an always-on boot guard.
8. Clean-break migrations: one `0001_initial` per model-bearing module, and upgrades go to a
   fresh database.
9. Lockstep versions. Embeds use the identity-derived immutable split tag.
10. Every Module Conventions rule is enforced by a conformance test (rule 40). Every gate runs
    in every required context.
11. No DI containers or service registries. Cross-module needs use `AppConfig` capabilities.
    New: the capability names are a closed vocabulary in core (`CAPABILITIES`, SA265).
12. Fixed quality lines: no file of 800 lines or more, and CC below 21. These apply to package
    `src/` only; `scripts/` is still outside `check_quality.sh`.

**Measurements.**
- **Filter:** real commits only. Synthetic subtree-split commits (trees without
  `quickscale_core/`) and merges are dropped. Bulk commits touching more than 30 files are
  dropped (10 in the delta). The changelog, roadmap, audits, `VERSION`, release notes, and
  lockfiles are excluded from churn.
- **Window:** the delta `2fd8637f..451b3dbf`, five days. The 12-month baseline was not
  recomputed; the prior pass's baseline stands in version control.

| Measure | Value |
|---|---|
| Commits touching product source | delta 35 of 98 (36%) · October to date 88 of 223 (39%; the prior pass read 42%) |
| `scripts/` (all tracked files) | 69.7k lines / 118 files at `2fd8637f` → **86.7k / 181** now (+17.0k in 5 days) |
| Conformance harness, non-test | 7.8k → **15.0k** lines. Tests-of-scripts: 33.8k → 43.9k |
| Module source (non-test, non-migration) | 39.6k → 40.8k |
| Numbered convention rules | 50 → 50 (plateau). The § Module Conventions text grew 735 → 887 lines, so rules gain clauses rather than numbers. Detectors: 43 → 43 |
| Gates in `gate_registry.json` | 20 → 21 (`check-generated-project-automation`, SA253) |
| `project_contract.yml` adoption steps | 30 → **40**, all `minimum: "0.89.0"` |
| `INTENTIONALLY_UNMANAGED` (beta-migration taxonomy) | 92 → 106 entries (counted by AST this pass; the prior pass's 89 used a different count) |
| `0001_initial` rewrites | **13 in the delta** across 10 modules; 58 in 3 months (the prior pass counted 45) |
| Delta churn leaders | `decisions.md` 12 · `rules_misc.py` 9 · `project_contract.yml` 8 · `sa90_emission_manifests.json` 7 · `rules_routes.py` 6 |
| `scripts/` debt against the fixed lines | 29 non-test functions at CC ≥ 21 (radon `-n D`); 9 non-test files ≥ 800 lines (10 at `2fd8637f`) |
| Gate wiring code | `check_gate_parity.py` 2,887 → 769 and `sync_ci_gate_jobs.py` 1,049 → 1,760 (net −1.4k) |

**Commit-delta classification** (98 non-merge commits):
- **Closeout (mapped to tickets and verified):** SA251 (a–c), SA252, SA253, SA254, SA255,
  SA256, SA257, SA258 (a–c), SA259, SA260, SA261, SA262, SA263, SA264, SA265 (a–c), SA266,
  SA267 slices, SA268 slice (a), and SA191 (a–e). SA258, SA259, SA263, SA264, SA265, SA267,
  and SA268 went through the fix-regression audit (§5).
- **Housekeeping:** 11 roadmap, changelog, and validation-policy commits, for example
  `a185f998`, `f107118e`, `61fe1da6`, and `f21a8178`. None of them touches product source.
- **Unlabeled-behavioral, read at full depth:**
  - `41ee0a41` ("SA261 gate fixes") rewrites orgs' `_purge_support.py` imports. It imports
    from the defining siblings, with no semantic change.
  - `a9ac2eee` ("SA253 — align …") edits `module_wiring.py`, the managed URLconf renderer.
    The change is consistent with SA258(c).
  - `6b56515b` ("gate fixes") adds a `project_contract.yml` step under a gate-fix label: one
    more adoption step (Finding 2).
  - Merge `192195e2` resolves conflicts in the blog, listings, and storage `adapter.py` files
    and storage's `module.yml`. The resolution keeps both parents' intents: SA261 moves the
    Markdownx mount to storage, and SA263 stops coercion in hooks.

  No load-bearing semantics change was found hidden under a housekeeping label.

**Coverage and residual risk.**
- **Read in full:**
  - the prior arch audit, the roadmap, and § Module Conventions rules 19 and 44;
  - `sync_ci_gate_jobs.py`'s per-gate tables and refusals, one parity test
    (`test_routes_parity.py`), and `adapter_flow.py`'s contract;
  - `useModules.ts`, `recovery.py`'s vintage logic, `contracts/resolvers.py`, and
    `runtime/conventions.py`'s `CAPABILITIES` and retired-settings path;
  - `project_state_hashes.py`'s managed set, `bap-web-new/.quickscale/state.yml`, and the
    diffs of every unlabeled-behavioral commit and every conflicted merge.
- **Sampled:**
  - the SA263 and SA264 diffs to orgs, adapters, and the manifest engine;
  - the dr_engine storage loaders (`_metadata.py`, `_media.py`, `_sidecar.py`);
  - the generated `LOGGING`, the DRF defaults in the runtime facade, billing's advisory locks,
    and the apply-step registry.
- **Skipped:** DR internals beyond the vintage and storage seams; the notifications, analytics,
  and social internals; publish and beta-migration internals; theme TypeScript beyond the seam
  hooks. SA226 role authorization and SA229 write effects are still not audited at depth; this
  is the third pass to skip them.
- **Lens activation:** `active: I, II, III, IV, V, VII, IX, XII, XIII, XV, XVI, XVIII, XIX,
  XX · sampled: VI, VIII, X, XI · inert: XIV (no volume threshold in sight), XVII (flat
  Railway bill, no metered driver beyond maintainer time) · archetypes: code generator, CLI,
  library (runtime facade), multi-tenant output, monorepo`.
- **Lenses that produced findings:** I, III, V, VII, XV, XIX, XX, and the §6 generator lens.
- **Unverified out-of-repo architecture:** Railway service settings (pooling, replicas,
  proxy), GitHub tag and branch protection, PyPI state (including whether anyone runs 0.88.0
  with billing on), Stripe endpoint versions, PostHog-side deletion, and the old `bap-web`
  repository.
- **Claims needing runtime confirmation:**
  - That a database created by `bap-web-new`'s pre-publication "0.89.0" modules, once
    repinned to the published 0.89.0, gets "no migrations to apply" from `migrate` while its
    schema differs (Finding 1). The source supports this; it was not executed.
  - That PostgreSQL FK checks bypass RLS. This is carried from the prior pass and not
    executed.
- **Open lead:** cross-organization references through M2M tag tables (`Contact.tags`,
  `Deal.tags`, `Post.tags`) are still not censused. This is the second pass to carry it.
- **Do not read silence as clearance** for DR internals, role authorization, write effects,
  or the theme's TypeScript.

---

## 2. Enforcement census

| Invariant | Where enforced | Kind | Gate world | Trend since `2fd8637f` |
|---|---|---|---|---|
| Tenant rows isolated by organization | FORCE RLS two-policy contract; restricted role; boot guard (`orgs/checks.py:183–192`); ContextVar → transaction-scoped `SET LOCAL` (`_current_org_priming.py`) | **structural** | — | unchanged |
| Tenant-to-tenant references stay in one org | composite `(fk, organization_id)` FKs derived by `quickscale_orgs.W007` | **structural** (gated) | closed over model metadata | unchanged (SA257 landed before the prior pass) |
| API authentication by default | `IsAuthenticated` default in `compose_rest_framework()` (`runtime/settings.py:153,197`); closed `REST_FRAMEWORK` admission (SA262) | **structural** | — | strengthened |
| Per-view guard declared | rule 19 detector over view content | gated | closed over detected views | strengthened (SA262 "one declared guard per view") |
| Org-role authorization | `user_has_org_role`; rule 44 spelling detector | structural helper + gated use | open-world (rule 44 says so) | unchanged |
| One owner per URL prefix | `collect_wiring` refuses two modules mounting one prefix (`module_wiring.py:135`) | **structural** | — | **new** (SA261) |
| Option validation, defaults, and secret projection | the manifest boundary; adapters receive canonical values | structural engine + **gated** hook discipline (1.1k-line dataflow detector, `adapter_flow.py`) | bounded call graph | **new** (SA263): the boundary is structural, but "a hook never re-coerces" is policed by detector |
| Capability names | `CAPABILITIES` closed vocabulary; `collect_capabilities` refuses an unlisted name (`runtime/conventions.py:181–219`) | **structural** | — | **new** (SA265) |
| Module error shape | one module error base and one HTTP mapping (SA264); rule 10 closed-world | structural + gated | closed | **new** |
| Declared removal and anonymize obligations | one coordinator per boundary; `_require_obligation_owners` (`auth/_anonymize_boundary.py:95–99`) | **structural** | — | unchanged |
| Personal-data treatment | `personal_data_declarations`; W006 | structural check | closed over candidates | unchanged |
| Core and CLI hold no module names | rule 37 detector plus 31 reasoned exceptions (14 files, 10 literals, 2 branches, 5 constants) | gated | open by exception list | **exception list 22 → 31** |
| Privileged DB command set | four literal declarations; `test_privileged_command_contract.py` | gated | closed (equality) | unchanged |
| Stripe API version agrees with the SDK pin | runtime refusal on one constant; five literal stations | structural + convention | — | unchanged |
| Generator template context and output boot | `StrictUndefined` (`generator.py:404`); e2e lifecycle; executed generated automation (SA253) | **structural** | — | strengthened |
| Module write effects on commit | per-module rollback test; review rule 21 | convention | — | unchanged |
| Generated-project contract adoption | `--confirm-contract-adoption` records ids (`contract_vintage.py:38`) | **convention** (honor system) | — | **30 → 40 steps** |
| Vendored module source unmodified | extension contract prose only | **convention** | — | unchanged; `bap-web-new` has no edits |
| Shipped migrations immutable | none (SA204 plans a hash-manifest gate) | **none** | — | **13 rewrites in 5 days** |
| Schema identity of a "version" | version-string equality at embed, `update`, and DR restore | **convention** (the label stands in for content) | — | **newly measured**: 5 of 5 `bap-web-new` `0001` files differ from HEAD under the same "0.89.0" |
| Gate present in every required context | generated regions plus `gates.mk` from the registry; but `sync_ci_gate_jobs.py` holds hand-ordered copies refused on mismatch (`:89–107`, `:273–290`, `:498–501`, `:1029–1036`) | gated | closed (equality of copies) | relocated (Finding 3) |
| Split detector behavior preserved | 11 parity test files with 1,381 hand-listed literals, including private helper names | gated | closed (frozen lists) | **new** (SA267/SA268) |
| Quality thresholds | `check_quality.sh` fixed lines, package `src/` only | gated | closed per metric, `scripts/` exempt | unchanged scope |

Findings concentrate on the **convention**, **none**, and frozen-copy rows. The structural
rows feed §9.

---

## 3. Summary table

| Rank | ID | Title | Horizon | Confidence | Size | Reversibility | Problem |
|---|---|---|---|---|---|---|---|
| 1 | `clean-break-schema-no-data-path` | Module schemas have no data upgrade path | now | High | M | one-way door | `0001_initial` is rewritten in place (13 times in 5 days), and every containment keys on a version label that does not identify the schema |
| 2 | `generated-file-ownership-unmodeled` | Module-facing contracts live in user-owned generated files | now | High | M | two-way door | The Django side moved into the runtime; adoption steps still grow (30 → 40 in 5 days, six pending on `bap-web-new` four days after generation), and three upgrade mechanisms remain |
| 3 | `rules-held-by-parity-not-derivation` | Rules are kept as hand-synced copies held by parity gates | now | High | M | two-way door | SA259 derived part of it, but the generator re-holds per-gate copies by equality, and SA267/SA268 added 1,381 frozen names while `scripts/` grew 17k lines |

---

## 4. Machine-readable index

```yaml
schema: arch-audit/v9
audited: 451b3dbf318aff993166dfbae11fdd649d686cd7
items:
  - {id: clean-break-schema-no-data-path, status: open, rank: 1,
     title: "Module schemas have no data upgrade path", lenses: [I, XIX, XVI],
     horizon: now, confidence: High, size: M, reversibility: one-way door,
     depends_on: [], amplifies: [generated-file-ownership-unmodeled],
     anchors: [docs/technical/decisions.md, quickscale_modules/blog/src/quickscale_modules_blog/migrations/0001_initial.py,
               quickscale_core/src/quickscale_core/dr_engine/recovery.py, quickscale_cli/src/quickscale_cli/commands/_module_update.py],
     first_seen: 2026-09-23, last_verified: 2026-10-13}
  - {id: generated-file-ownership-unmodeled, status: open, rank: 2,
     title: "Module-facing contracts live in user-owned generated files", lenses: [V, VII, IX, XV, XIX, "§6 generator"],
     horizon: now, confidence: High, size: M, reversibility: two-way door,
     depends_on: [], amplifies: [clean-break-schema-no-data-path],
     anchors: [quickscale_core/src/quickscale_core/data/project_contract.yml, quickscale_core/src/quickscale_core/project_state_hashes.py,
               quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/src/hooks/useModules.ts,
               quickscale_cli/src/quickscale_cli/commands/contract_vintage.py, quickscale_devtools/src/quickscale_devtools/beta_migration/constants.py],
     first_seen: 2026-09-16, last_verified: 2026-10-13}
  - {id: rules-held-by-parity-not-derivation, status: open, rank: 3,
     title: "Rules are kept as hand-synced copies held by parity gates", lenses: [XV, XX, III],
     horizon: now, confidence: High, size: M, reversibility: two-way door,
     depends_on: [], amplifies: [],
     anchors: [scripts/gate_registry.json, scripts/sync_ci_gate_jobs.py, scripts/check_ci_locally.sh,
               scripts/tests_module_conventions, scripts/module_conventions/adapter_flow.py,
               quickscale_core/src/quickscale_core/data/manifests, quickscale_core/src/quickscale_core/contracts/resolvers.py],
     first_seen: 2026-10-08, last_verified: 2026-10-13}
  - {id: lockstep-release-unit, status: accepted, title: "Core, CLI, and modules release as one unit", lenses: [XIII, XIX]}
  - {id: privileged-command-four-stations, status: accepted, title: "Privileged command set declared at four stations", lenses: [II]}
  - {id: single-railway-shared-fate, status: accepted, title: "One app and one database per project", lenses: [XVI]}
  - {id: core-holds-module-vocabulary, status: watchlist, title: "Core still names and imports modules", lenses: [III, IX]}
  - {id: manifest-dsl-vocabulary-growth, status: watchlist, title: "Manifest DSL grows one keyword per module need", lenses: [V, XII]}
  - {id: vendored-module-edits-undetected, status: watchlist, title: "Edits under vendored modules/ go undetected", lenses: [XIX, "§6 generator"]}
  - {id: session-advisory-lock-pooling, status: watchlist, title: "Billing mutex is a session-level advisory lock", lenses: [X]}
  - {id: modules-english-only, status: watchlist, title: "Module-rendered pages are English-only", lenses: [I]}
  - {id: two-filesystem-lock-implementations, status: watchlist, title: "Two filesystem-lock implementations", lenses: [IX]}
  - {id: ci-provisioning-hand-pins, status: watchlist, title: "Hand-pinned residue in CI provisioning", lenses: [XV]}
  - {id: trigger-inputs-legacy-name, status: watchlist, title: "trigger_inputs legacy name for an exact allowlist", lenses: [XV]}
  - {id: subscription-status-single-writer, status: watchlist, title: "Subscription.status has one writing module", lenses: [I]}
```

---

## 5. Ranked findings

### Finding 1: Module schemas have no data upgrade path

- **ID:** `clean-break-schema-no-data-path` — still open. SA204 has not started. It is now
  sliced, and SA153 depends on it.
- **Rank rationale:** High blast radius, High likelihood, steep compounding.
  - **Blast radius:** data. The only supported upgrade is a fresh database, and backups do not
    restore across releases.
  - **Likelihood:** SA153's go-live creates the first tenant data that cannot be reseeded.
    It is on the roadmap, behind SA204.
  - **Compounding:** 13 `0001_initial` rewrites in five days (58 in 3 months, up from 45).
  - **Tie-break:** ranked above Finding 2, which scores the same, because this door is one-way
    and closes at a scheduled event.
- **Horizon & trigger:** `now`. The trigger is the first module schema change after SA191's
  cutover, or SA153's go-live, whichever comes first.
- **Confidence:** High. The rule, the topology, the rewrite counts, the DR refusal, and the
  label-versus-content mismatch were all read or measured. The runtime symptom on a migrated
  database is Medium, because it is inferred.
- **Context dependence:** `wrong-for-now`. The dimension is the first deployed database whose
  data cannot be reseeded. It lives in R2.
- **Problem:** Each model-bearing module ships one `0001_initial` that is rewritten in place,
  and every safety check that should stop a mismatched database compares a **version
  label**, not the schema. The checks are the lockstep embed check, `update`, and DR restore.
  A database or backup from one schema therefore cannot be carried to the next, and within a
  release cycle the label does not even detect the mismatch.
- **Evidence** (re-verified this pass unless marked new):
  - [decisions.md:2056–2060](../technical/decisions.md) § Clean-Break Migration History: "does
    not support in-place database upgrades".
  - Ten model-bearing modules carry exactly one migration each. The topology test pins it and
    keeps a `0002` canary (`quickscale_core/tests/test_module_migration_topology.py:909–916`).
  - **Rewrites in the delta** (new): auth 1, backups 1, billing 1, blog 2, crm 2, forms 1,
    listings 1, notifications 1, orgs 2, social 1. These came from SA257 (composite FKs), SA266
    (the convention sweep), and SA265(a), which moved `stripe_customer_id` off the orgs tenant
    root.
  - **The version label is not schema identity** (new):
    - `bap-web-new` embeds modules labeled 0.89.0 (`pyproject.toml:12,25–30`).
    - The `0001_initial` content hashes of all five model-bearing modules it carries (orgs,
      auth, forms, listings, notifications) differ from HEAD's, which is also 0.89.0. Its orgs
      `0001` still creates `stripe_customer_id` (3 references).
    - `dr_engine/recovery.py:228–265` compares recorded and installed module *version
      strings*, so a backup from that database passes the vintage check against the published
      0.89.0.
    - `_module_update.py` checks versions and option drift, not migration content.
    - Django sees `0001_initial` as already applied, so nothing flags the drift.
  - **The bare-file edge is still fail-open:** `recovery.py:287–288`
    (`if recorded_module_versions is None: return []`).
  - **The frozen history will pin a private name:** `blog/migrations/0001_initial.py:124`
    references `quickscale_modules_blog.models._BlogMediaAssetImageField`. SA204 slice (a)
    targets it.
  - `project_contract.yml` step `sa221-identity-stem`: "Recreate the project database after
    adopting".
  - [roadmap.md:166–175](../technical/roadmap.md) (SA191): the cutover "rebuilds a fresh
    database and reseeds".
- **Counter-evidence:**
  - Searched for incremental migrations: none exist.
  - Searched for a rewrite gate: none exists. SA204(c) specifies a hash-manifest gate.
  - Searched for a content-identity check at embed, update, or restore: none exists. Every
    comparison is on version strings.
  - Searched the cutover plan: it rebuilds fresh, so the label mismatch cannot bite *at
    cutover*. It can bite on any rehearsal database carried across a repin.
  - **Prior question 2 is answered:** SA153 now depends on SA204 in the scheduling table
    ([roadmap.md:34](../technical/roadmap.md)). The order is secured, though SA204's release
    requirement is still "Optional".
- **Why it compounds:**
  - **Growth variable:** deployed databases × schema edits between releases. The current rate
    is about 2.6 rewrites a day.
  - **Release size widens the window:** 871 non-merge commits separate HEAD from 0.88.0, and
    every edit under one label is invisible to the label checks.
  - **Built on top:** RLS installation inside each `0001`, the DR vintage refusal, the topology
    test, the identity-stem adoption step, and SA191's reseed procedure.
- **Detection signal:**
  - `InconsistentMigrationHistory`, or a missing-column `ProgrammingError`, during
    `start.sh`'s migrate.
  - A `migrate --plan` inconsistency (SA191 slice (a) already recorded one).
  - "Recreate the project database" adoption steps.
  - SA205 vintage refusals.
  - **New:** a schema-hash mismatch between a project's `django_migrations`-applied `0001` and
    the embedded file. Instrument this first; today nothing computes it.
- **Steelman:** Pre-1.0 with one reseedable site. A single `0001` keeps RLS installation in one
  place and let SA265 move a billing column off the tenant root for free this week. Within a
  development cycle the version label is not meant to identify anything; only published
  versions are immutable. Do not fix while no deployed database holds data that cannot be
  reseeded.
- **Correct shape:** Once a database exists that cannot be recreated, every schema change
  that reaches it is an additive, ordered migration. Shipped migrations are immutable and name
  only symbols with a stability promise. Every check that decides whether a database or backup
  fits the installed code compares **migration content identity**, not a version label.
- **Do-nothing cost:** After SA153 goes live, every release that touches any of ten schemas
  forces a hand-written transform or a skipped upgrade on `bap-web-new`, and makes every
  existing backup unrestorable. At today's rate that is roughly 40–60 rewrites per release. Any
  rehearsal or pre-release database carried across a repin drifts silently.
- **Options:**
  1. **Freeze at the vintage `bap-web-new` lands on (SA204 a–c),** with the hash manifest
     doubling as the content identity that restore-forward and `update` compare. Effort M,
     one-way door, incremental. **Live option.**
  2. **Vintage bridges:** per-release bridge migrations or an export/import, with `0001` still
     rewritten. Effort L. This relocates the cost into a transform per rewrite.
  3. ~~**Accept with restore containment**~~ — landed as SA205. It expires at SA153 and, as
     measured this pass, it keys on labels.
- **Recommendation:** Option 1, with one addition to SA204(b) and (c). Restore-forward and
  `quickscale update` should compare the frozen-migration hash manifest (per module, the
  hashes of applied files), not `module_versions`, and refuse a mismatch under an equal
  label. Raise SA204's release requirement to required for the release `bap-web-new` goes live
  on.
  - **Size:** M.
  - **Reversibility:** `one-way door`. Before it closes, prove on a restored `bap-web` copy that
    `migrate` from the frozen `0001` reproduces the FORCE-RLS parity baseline, as SA204(c)
    specifies.
  - **Guard:** SA204's hash-manifest gate with an inverted `0002` canary; no `_`-prefixed
    symbol in frozen migrations; a restore-forward test; and a test that a backup recording an
    equal label but different migration hashes is refused.
  - **First step:** SA204(a), promoting `_BlogMediaAssetImageField`.

### Finding 2: Module-facing contracts live in user-owned generated files

- **ID:** `generated-file-ownership-unmodeled` — still open (regressed 2026-10-08; partly
  fixed 2026-10-10).
- **Fix-regression audit of SA258 and SA261** (the remediations since the prior pass):
  1. **Mechanism:** removed for the Django side. The seam renders through the
     `quickscale_seam` runtime tag, DRF composes through `compose_rest_framework()`, module
     URLs compose in the managed `urls_modules.py` with one include in user-owned `urls.py`,
     and a closed-world emission test guards it. The theme's API bases come from the seam's
     `moduleApiPaths` (SA261).
  2. **Sound decisions:** preserved. The SA206 facade pattern was extended.
  3. **New commitment:** as predicted, each seam piece minted one final adoption step
     (`sa258-runtime-seam-tag`, `sa258-runtime-drf-composition`, `sa258-managed-urlconf`,
     `sa261-seam-module-api-paths`).

  Verdict: the Django half is resolved. The finding stays open on the theme half and on the
  step rate, which did not fall.
- **Rank rationale:** High blast radius, High likelihood, steep compounding.
  - **Blast radius:** security and correctness fixes reach projects as hand-applied steps.
  - **Likelihood:** already firing on `bap-web-new` before cutover.
  - **Compounding:** 30 → 40 steps in five days; four of the ten came from this finding's own
    fix, and six from other work.
- **Horizon & trigger:** `now`. The trigger is the repin of `bap-web-new` to the published
  0.89.0 (SA191, remaining work).
- **Confidence:** High.
- **Context dependence:** `wrong-for-now`. The dimension is the number of long-lived
  generated projects. It lives in R2.
- **Problem:** The seam between shipped modules and a generated project is still partly
  emitted once into user-owned files. On the theme side, the module set and per-module path
  maps are typed into the React hooks. Only two emitted files are QuickScale-managed, so
  every contract change outside them becomes a hand-applied prose step per project.
- **Evidence:**
  - `project_state_hashes.py:34–37`: the managed set is still `settings/modules.py` and
    `urls_modules.py`.
  - **`useModules.ts:1–27`** (re-verified): `QuickScaleModules` types 11 module names;
    `QuickScaleModulePaths` names crm, social, and analytics; `QuickScaleModuleApiPaths` names
    orgs, billing, crm, and forms; and `inferCurrentOrgSlug` parses a crm path. 27 non-test
    theme TS files name a module (28 at `2fd8637f`).
  - **`project_contract.yml`:** 40 steps, all `minimum: "0.89.0"`. The ten added in the delta
    are `sa251-billing-async-payment-events`, `sa266-command-flags`, three `sa258-*`,
    `sa262-social-resolution-marker`, two `sa253-*`, and two `sa261-*`. One arrived under a
    "gate fixes" label (`6b56515b`).
  - **`bap-web-new`** (new, read-only, out of repo): `.quickscale/state.yml` records 35
    adopted steps at generation on 2026-10-09. Four days later, **six steps are pending**:
    `sa253-frontend-coverage`, `sa253-generated-automation`, `sa258-managed-urlconf`,
    `sa261-seam-module-api-paths`, `sa261-theme-seam-test-fixtures`, and
    `sa262-social-resolution-marker`.
  - **Adoption is still on the honor system:** `contract_vintage.py:38`
    (`--confirm-contract-adoption`).
  - **Three upgrade mechanisms are still maintained:**
    - prose steps;
    - `quickscale_devtools/beta_migration` (12.9k lines, touched by 4 delta commits;
      `INTENTIONALLY_UNMANAGED` 92 → 106);
    - the prompt-driven port that SA191 uses instead (`bap-web-new/MIGRATION_PROMPT.md`,
      `CUTOVER.md`).

    `scripts/check_project_contract_vintage.py` is still 1,351 lines.
- **Counter-evidence:**
  - The SA258 runtime seam is real, and its closed-world emission test is the guard the prior
    pass recommended.
  - The theme TS reads values from the seam, but its *types* and fallbacks enumerate modules.
    Rules 31 and 41 allow that, and rule 7's TypeScript clause rejects only API path literals.
  - Searched for automated adoption in `update`: none. It regenerates the two managed files.
  - Searched for a retirement decision on `beta_migration`: none. Prior option 4 is unchosen.
- **Why it compounds:**
  - **Growth variable:** template-side contract changes per release × long-lived projects.
    The rate is about two steps a day during active development.
  - **Built on top:** the vintage gate and CLI refusal, the beta-migration taxonomy and smoke
    gate, the theme seam validator, and `bap-web-new`'s adoption record.
- **Detection signal:**
  - Declared steps per release.
  - Pending steps on `bap-web-new` at repin.
  - Confirmations with no matching file diff.
  - URLconf import failures after `update`.
- **Steelman:** "Full ownership, no lock-in" is the product promise, and `bap-web-new` is the
  only long-lived project. Its steps are cheap while the maintainer applies them. The
  remaining TS enumeration is typing, not routing; values come from the runtime seam. Do not
  fix if generated projects are one-shot.
- **Correct shape:** Every emitted file is either QuickScale-managed (regenerated, never
  hand-edited) or user-owned (carrying no module contract). Module-facing contracts reach a
  project only through managed files or the versioned runtime library.
- **Do-nothing cost:**
  - Every release adds a batch of steps (10 in five days) that each long-lived project applies
    by hand.
  - Three upgrade mechanisms keep being maintained while the real upgrade goes by prompt.
- **Options:**
  1. ~~**Path-enumerated adoption gate**~~ — superseded by SA207/SA211.
  2. **Extend the SA206 pattern to the seam.** ~~Django side~~ landed (SA258, SA261).
     **Remaining:** generate the theme's seam *types* from the manifest set (a generated,
     managed `quickscaleSeam.d.ts`), so `useModules.ts` holds no module names. **Live option.**
  3. **A managed category for theme infrastructure hooks** (`useModules.ts`, `useApi.ts`),
     regenerated under the hash guard. Effort M–L.
  4. **Accept and document** that projects are one-shot: retire `beta_migration` and the
     vintage machinery. The revocation trigger is a second long-lived project or a security fix
     in a template.
- **Recommendation:** Finish option 2 on the theme side, then **choose between** keeping
  `beta_migration` and the prompt-driven port. Retire the one SA191 did not use.
  - **Size:** M.
  - **Reversibility:** `two-way door`.
  - **Guard:** extend the closed-world emission test to the theme. No user-owned emitted TS file
    names a module except the generated managed declaration. Also track steps per release,
    which should trend toward zero.
  - **First step:** generate the seam's module-key union type from the manifest set into a
    managed file.

### Finding 3: Rules are kept as hand-synced copies held by parity gates

- **ID:** `rules-held-by-parity-not-derivation` — still open. **Fix-regression verdict: partly
  removed, partly relocated.**
- **Fix-regression audit:**
  - **SA259 (gate wiring):**
    1. **Mechanism:** partly removed. `gates.mk`, the `ci.yml`, `publish.yml`, and `e2e.yml`
       regions, and the `validation_policy.md` table are generated, and the parity checker
       shrank from 2,887 to 769 lines. **But the generator re-holds the registry's gate lists
       by hand:**
       - `HOSTED_GATE_ORDER` (`sync_ci_gate_jobs.py:89–107`) and `PUBLISH_GATE_ORDER`
         (`:273–290`) restate which gates run where.
       - The generator refuses to run unless the copies equal the registry
         (`:498–501`: `if hosted_ids != HOSTED_GATE_ORDER: raise GeneratorError(...)`;
         `:1029–1036`).
       - The per-gate catalogs (`HOSTED_JOB_CATALOG :185`, `PUBLISH_STEP_CATALOG :292`, the
         help-text map around `:385–420`) hold data the registry could carry.
       - `check_ci_locally.sh:532–533` (a hand-written `case` arm per gate) and the
         `Makefile:354` help line remain.

       That is parity relocated into the generator. The prior pass's rejected candidate "Gate
       wiring held by parity" is **reversed**.
    2. **Sound decisions:** preserved.
    3. **New commitment:** none beyond the relocation.
  - **SA267 and SA268 (`scripts/` under the quality lines):**
    1. **Mechanism:** relocated. Ten slices split detector files into a facade plus private
       siblings and added a parity test per family:
       - 11 files, holding **1,381 hand-listed literals**;
       - each family's `FROZEN_SURFACE` pins "every module-level name the pre-split module
         published… private helpers included" (`test_routes_parity.py:53–56`).
    2. **Effect:**
       - The slices added +10.5k net lines in two days (src +3.0k, tests +7.6k).
       - Non-test files ≥ 800 lines went from 10 to 9, and 29 non-test functions remain at
         CC ≥ 21.
       - `scripts/` is still outside `check_quality.sh`.
    3. **New commitment:** each split family is now a hand-synced name list. Renaming a
       detector's private helper edits a frozen copy. This is a new station of the kind the
       finding names.
  - **SA263 (adapter option boundary):**
    1. **Mechanism:** the boundary itself is structural. The engine validates, coerces, and
       defaults.
    2. **Effect:** "a hook never re-coerces or re-reads a raw option" is enforced by a
       **bounded inter-procedural dataflow analyzer** (`adapter_flow.py` 697 lines,
       `adapter_options.py` 353, `url_options.py` 99, and about 1.4k lines of controls). The
       hooks still receive a mutable settings dict containing the raw values.
    3. **Verdict:** a rule that construction could make true is held by a detector (option 2
       territory).
  - **SA264 (retired settings):** the bundled manifest copy
    (`quickscale_core/data/manifests/*/module.yml`, held equal by `check-manifest-sync`) gained
    a **runtime reader**. Django startup in a generated project reads retired-setting refusals
    from core's snapshot, not from the embedded module (`contracts/resolvers.py:28–42`,
    `runtime/conventions.py:527–530`). The copy-pair is now load-bearing in R2 as well as R1.
- **Rank rationale:** Medium blast radius, High likelihood, steep compounding.
  - **Blast radius:** no user is broken, but this is the dominant delivery cost.
  - **Likelihood:** firing; 64% of delta commits touch no product source.
  - **Compounding:** `scripts/` +17.0k lines in five days, now more than double module source
    (86.7k against 40.8k).
- **Horizon & trigger:** `now`. Every new gate fires it, and SA204(c) adds one.
- **Confidence:** High for the mechanism and the measurements. Medium for attributing delivery
  cost, since commit share is a proxy.
- **Context dependence:** `wrong-for-now`. The dimension is team shape: one maintainer with
  agent tracks. It lives in R1, and the manifest copy now also lives in R2.
- **Problem:** Repository rules are authored once and then restated by hand in executable
  copies: gate lists inside the generator, frozen detector surfaces, bundled manifests, and
  repeated literals. Further checks keep the copies equal. Rules that construction could make
  true are policed by ever-larger detectors instead.
- **Evidence:**
  - **Station census for one gate** (`check-split-facade-imports`, outside tests and audits):
    - hand-authored: `gate_registry.json` (source), `sync_ci_gate_jobs.py` ×5,
      `check_ci_locally.sh` ×1, `Makefile` ×1, and `decisions.md`;
    - generated: `gates.mk`, `ci.yml`, `publish.yml`, and `validation_policy.md`.

    A new all-context gate costs about **8 hand stations, down from about 12**, held by
    equality refusals.
  - **The harness grew past the line it is being split to meet.** Between `2fd8637f` and
    `0f5b8d29`, rule clauses added for SA262, SA263, SA264, and SA265 pushed `rules_routes.py`
    to 1,840 lines and `rules_identity.py` to 1,205, and brought `rules_webhooks.py` (830) and
    `core.py` (848) over the 800-line line. SA267 and SA268 then split them.
  - The rule count plateaued at 50, but § Module Conventions grew 735 → 887 lines. The harness
    grows by clauses, not rule numbers.
  - **Rule 37's reasoned exception lists** grew from 22 to 31 entries (two new categories:
    branches and constants; `rules_identity.py:166,185,225,237`).
  - **Copies still held equal:**
    - the Stripe API version at five product stations (`billing/_settings.py:32`,
      `billing/module.yml:115`, its bundled copy, `_finalize.py:276`, and
      `OPERATIONS.md.j2:115–131`);
    - the privileged-command set at four stations (accepted commitment);
    - the bundled manifests (above).
  - **Governance code is still exempt** from its own bar: `check_quality.sh` scans package
    `src/` only, by SA267's own acceptance ("discovery unchanged").
- **Counter-evidence:**
  - SA259's derivation is real: about −1.4k lines of wiring code and four generated
    projections.
  - SA267's acceptance text prefers deletion, and the commit messages claim "behavior parity",
    not new rules.
  - The rule-number plateau meets half of the prior steelman's condition ("the counts
    plateau").
  - The parity tests may be meant as temporary characterization scaffolding. No ticket text
    says they are retired at slice close; searched `roadmap.md` SA267 and SA268 and the parity
    file docstrings ("so a later slice cannot silently drop… them").
  - The team removed governance code before (SA243, and SA259's −4.8k parity checker).
- **Why it compounds:**
  - **Growth variable:** rules, rule clauses, gates, and split families.
  - **Unit costs:** a new gate costs about 8 hand stations. A new clause costs a detector
    branch, controls, sometimes an exception entry, and now possibly a frozen-surface edit. A
    split family costs a parity file of 57–183 literals.
  - **Measured growth:** `scripts/` +17.0k lines in five days. The harness doubled in non-test
    lines, and 1,381 frozen literals were minted in two days.
  - **Built on top:** 21 gates, 43 detectors, 11 parity families, three workflows, the local
    CI runner, and the track-ownership model.
- **Detection signal:**
  - The share of commits touching no product source (64% in the delta).
  - `scripts/` lines per product line (2.1).
  - Parity-test edits in commits that change no detector behavior.
  - `GeneratorError: unsupported hosted gate set` on a new gate.
- **Steelman:** One maintainer runs three agent tracks, and agents follow executable checks far
  better than prose. Characterization tests are the standard safe way to split code, and the
  frozen surfaces can be deleted once the splits land. The generator's order tuples make the
  emitted YAML ordering explicit and reviewable. Accept the cost if the parity files are
  retired at SA268's close and the gate count stays flat.
- **Correct shape:** Every rule has exactly one authored, executable source. Every other place
  it appears is generated or derived from that source, or deleted, never kept equal by an
  equality check. Invariants that code can make true by construction are enforced there, and
  their detectors are removed. Governance code meets the same quality bar as product code, by
  deletion first.
- **Do-nothing cost:**
  - About 8 hand edits per new gate (SA204 adds one).
  - Every detector refactor edits frozen name lists.
  - At the delta's rate, `scripts/` keeps growing several times faster than product code.
  - The bundled-manifest copy now affects runtime behavior in projects.
- **Options:**
  1. **Generate and derive instead of compare** (partly landed). Remaining:
     - Move the gate order and the hosted, publish, and help metadata into
       `gate_registry.json` fields, and delete `HOSTED_GATE_ORDER`, `PUBLISH_GATE_ORDER`, and
       the catalogs.
     - Generate `check_ci_locally.sh`'s `case` arms and the Makefile help.
     - Build the bundled manifests at wheel build time, and read the Stripe version from one
       constant.

     Effort S–M. A new gate drops from about 8 stations to 1. **Live option.**
  2. **Retire rules by construction.** For SA263, the hook receives a frozen, typed
     resolved-options object and no raw settings, so the dataflow detector can be deleted.
     Apply the same classification (structural, derivable, or review-only) to each of the 50
     rules as it is next touched. Effort M.
  3. **Accept with a budget.** Parity scaffolding is deleted at slice close, there is no new
     gate without retiring one, and `scripts/` comes under `check_quality.sh`. Effort S.
- **Recommendation:**
  - Fold option 1's remaining items into **SA267 slice (a)**, which already owns
    `sync_ci_gate_jobs.py`: delete the hand lists rather than split the file.
  - Add to SA267 and SA268 acceptance that `FROZEN_SURFACE` name lists are deleted when the
    family's slice closes. The exact-findings corpora may stay as behavioral tests.
  - Apply option 2 to SA263's hook signature.
  - **Size:** M.
  - **Reversibility:** `two-way door`.
  - **Guard:** one "generated files are current" check with no copy-equality refusals in the
    generator; `check_quality.sh` scanning `scripts/`; and a test that no `test_*_parity.py`
    survives a closed slice.
  - **First step:** move gate order into the registry and delete `HOSTED_GATE_ORDER` and
    `PUBLISH_GATE_ORDER`.

---

## 6. Change-cost probes

| Probe | Stations, measured | Verdict |
|---|---|---|
| **Adding one gate** (re-run; next instance: SA204(c)'s freeze gate) | Hand-authored: registry row; `sync_ci_gate_jobs.py` hosted order, hosted catalog, publish order, publish catalog, and help text (5); `check_ci_locally.sh` `case` arm; `Makefile` help. Then re-run the sync, which regenerates `gates.mk`, three workflow regions, and the docs table. Generation fails until the hand copies equal the registry | **Finding evidence** → Finding 3 (≈12 → ≈8; target 1) |
| **A module contract change reaching a deployed project** (re-run; instance: SA261 moved the theme API bases onto the seam) | Automatic: the runtime seam carries `moduleApiPaths`. Manual on `bap-web-new`: `sa261-seam-module-api-paths` plus its test-fixture step. Declaration: a `project_contract.yml` step plus the vintage gate. Operator: `--confirm-contract-adoption`. Six steps pending four days after generation | **Finding evidence** → Finding 2 |
| **Repin `bap-web-new` to the published 0.89.0** (new, SA191's remaining step) | (1) wheel repin; (2) six pending adoption steps; (3) subtree pulls of six modules whose `0001` files all differ under an equal label; (4) the cutover's fresh rebuild and reseed. Label checks at (3) pass silently | **Finding evidence** → Findings 1 and 2; the fresh rebuild contains it at cutover |
| **SA153 gallery child table in a project app** (carried) | Model on `TenantModel`; project migration with `apply_force_rls`; composite org FK (W007); `provider_id_classification`; `removal_obligations`; `personal_data_declarations`; `TenantModelAdmin`; boundary tests. Runtime checks hold them **in the project** | **Exonerating** (§9.2) |
| **SA153 listing inquiry into CRM** (carried) | Inquiry lands in `crm`; email field declared; `about_users` required; W007 checks reference equality | **Exonerated** |
| **Adding a module option** (re-checked against SA263) | `module.yml` option, `validation`, and `django_setting`. The engine validates, coerces, defaults, and projects secrets; the adapter adds nothing | **Exonerated**. SA263 made it stronger; the cost moved into the hook detector (Finding 3) |
| **Retiring one module** (`social`, carried) | 39 non-test files outside the module (not recounted) | **Watchlist** (`core-holds-module-vocabulary`) |

---

## 7. Fix order and interactions

- **Finding 1 before SA153, already secured.** The scheduling table makes SA153 depend on
  SA204. The addition in this pass (compare migration content, not labels) belongs inside
  SA204(b) and (c) and adds no ticket.
- **Finding 3's remaining option 1 before SA204(c).** SA204(c) adds a gate row (a cross-track
  edit into Track 2's registry). If SA267(a) first moves gate order and metadata into the
  registry, the freeze gate costs one station instead of about eight.
- **Finding 2 interacts with SA191's repin.** Each Finding 2 piece landed before the repin is
  one more step `bap-web-new` applies once. Each piece landed after is a step applied on a
  live site. Finish the theme-type generation before the repin if it fits.
- **Findings 1 and 2 amplify each other.** Together they make every upgrade a big-bang event:
  code by hand and data by reseed.
- **No conflicts found.**

---

## 8. Sound load-bearing decisions (preserve through remediation)

All five prior decisions were re-verified this pass, and one was strengthened.

1. **Tenant isolation is structural and fails closed.**
   - FORCE RLS under a `NOSUPERUSER NOBYPASSRLS` role, with the boot guard at
     `orgs/checks.py:183–192`.
   - Transaction-scoped `SET LOCAL` priming (`_current_org_priming.py`).
   - Marker-derived enrollment.
   - SA264 reordered orgs' startup checks so the settings check runs before the role guard
     (`apps.py`), and the fail direction is preserved.
2. **The module contract reaches host-project code through declarations and one fail-closed
   coordinator.**
   - Obligations, provider-ID classification, and personal-data treatments are declared on
     each `AppConfig`.
   - One coordinator refuses deletion on an owner without a handler
     (`auth/_anonymize_boundary.py:95–99`).
   - Orgs' system checks run in the project.
   - SA265 strengthens this: capability names are now a closed, fail-loud vocabulary.
3. **Module boundaries are declared once.**
   - Options, URL mounts, and UI routes live in `module.yml`.
   - One engine validates at plan, at apply, and at startup.
   - SA263 extends this: the engine also coerces, defaults, and projects secrets.
   - SA261 adds a structural one-owner-per-prefix refusal in `collect_wiring`.
4. **The runtime settings facade, extended to the seam (SA206, then SA258).** Executable
   contracts ship as versioned library code, not template copies. `compose_rest_framework()`
   installs deny-by-default `IsAuthenticated` (`runtime/settings.py:153,197`).
5. **Generation and release integrity.**
   - `StrictUndefined` (`generator/generator.py:404`) and the e2e lifecycle.
   - Immutable split tags (`utils/git_naming.py:57`).
   - New (SA253): the generated project's CI, migrate, and healthcheck commands are
     *executed* offline in a gate, not grepped.

---

## 9. Accepted commitments

- **`lockstep-release-unit`**
  - **Commitment:** each module's version equals core's, and projects pin
    `>=X.Y.0,<X.(Y+1).0`.
  - **Containment:** version comparison at embed and wiring regeneration, plus
    `check-core-compat`.
  - **Revocation trigger:** a runtime fix must reach a deployed project that cannot take the
    same release's module and contract changes.
  - **This pass:** **not fired for any known project.** There is pressure on it:
    - The 0.88.0 billing fix can reach a 0.88.0 user only through 0.89.0, which carries 871
      commits, 40 adoption steps, and a fresh-database clean break.
    - No known deployment runs 0.88.0 with billing (`bap-web` is on 0.62.0 with billing
      off), but PyPI consumers are unknown.
    - New observation: within an unreleased cycle the shared label identifies no content
      (Finding 1).
- **`privileged-command-four-stations`**
  - **Commitment:** `{migrate, createcachetable}` at four stations
    (`orgs/checks.py:108`, `runtime/settings.py`, `development_commands.py`, `start.sh`).
  - **Containment:** `test_privileged_command_contract.py`.
  - **Revocation trigger:** a third privileged command.
  - **This pass:** not fired.
- **`single-railway-shared-fate`**
  - **Commitment:** one app and one PostgreSQL per project.
  - **Containment:** DR capture and restore.
  - **Revocation trigger:** an SLA, or one tenant able to exhaust shared capacity.
  - **This pass:** not fired.

---

## 10. Watchlist

Nine items are carried, because no trigger fired or became obsolete. Each carries this pass's
evaluation.

- **`core-holds-module-vocabulary`**
  - **What:** core and the CLI still name modules:
    - `social_manifest.py` (513 lines);
    - `contracts/module_options.py` (421 lines; SA265(c) deleted dead analytics and billing
      constants);
    - four module-named apply steps (`apply/step.py`);
    - dr_engine's storage loader (`_metadata.py:80`), whose `ModuleNotFoundError` name check
      is now copied into `_media.py:57–59` and `_sidecar.py:62–64` (SA256).

    New this pass: rule 37 gates this, with an exception list of 22 → 31 entries. Core's
    `CAPABILITIES` names higher-layer capability words (`notification_templates`,
    `organization_pricing_url_hooks`, `post_login_redirect_hooks`). Each new cross-module
    capability is a one-line core edit, which is flat under lockstep.
  - **Trigger:** teams is scheduled, a 13th module is added, a new module-named apply step
    appears, or **rule 37's exception list grows beyond 31**.
  - **This pass:** **not fired.** Still 12 modules and four module-named steps. The list grew
    when it was created (new categories), not by accretion.
- **`manifest-dsl-vocabulary-growth`**
  - **What:** the manifest engine is at 6,992 lines (6,804 at the prior pass).
  - **Trigger:** a validation keyword added for a single module.
  - **This pass:** **not fired.** SA263's `retired_settings` is used by five modules
    (blog, crm, forms, listings, orgs).
- **`vendored-module-edits-undetected`**
  - **What:** the update guard does not detect edits under `modules/<name>/`.
  - **Trigger:** a second project with vendored edits, or a subtree-pull conflict.
  - **This pass:** **not fired.** `bap-web-new`'s `modules/` history holds only subtree merges.
- **`session-advisory-lock-pooling`**
  - **What:** billing's `pg_advisory_lock` (`billing/_locks.py:41–46,70–75`, unlock in
    `finally`).
  - **Trigger:** PgBouncer or a pooled `DATABASE_URL`.
  - **This pass:** **not fired.** The generated production settings use
    `conn_max_age=600` (persistent, not pooled).
- **`modules-english-only`**
  - **Trigger:** SA153 or SA154 needs a module-rendered page in Spanish.
  - **This pass:** **not fired.** SA153's Spanish surface is React, and the inquiry goes through
    the API.
- **`two-filesystem-lock-implementations`**
  - **What:** only `advisory_lock.py` and `dr_engine/_lock.py` match `O_EXCL`, `flock`, or
    `msvcrt`.
  - **Trigger:** a third implementation.
  - **This pass:** **not fired.**
- **`ci-provisioning-hand-pins`**
  - **Trigger:** a 13th module.
  - **This pass:** **not fired.**
- **`trigger-inputs-legacy-name`**
  - **What:** still the e2e allowlist partition (`check_gate_parity.py:24–54`).
  - **Trigger:** any context skipping a gate on it.
  - **This pass:** **not fired.**
- **`subscription-status-single-writer`**
  - **Trigger:** a second provider or an outside writer.
  - **This pass:** **not fired.** No module source outside billing names `Subscription`.

---

## 11. Rejected candidates

**Killed this pass:**
- **"Version label is not content identity" as its own finding.** It shares Finding 1's root
  (schema identity unmodeled under clean-break). After publication the split tags are
  immutable, so the gap is confined to pre-release consumers, and the cutover rebuilds fresh.
  It is folded into Finding 1 and the lockstep evaluation.
- **`CAPABILITIES` as dependency inversion through vocabulary.** It is a one-line core edit per
  capability under lockstep, and the closed list buys fail-loud misspellings. The cost is flat,
  so it fails gate 4. Noted under `core-holds-module-vocabulary`.
- **Observability scattered or ad hoc.** The runtime facade ships the `JsonFormatter` and the
  `CorrelationIdFilter` (`runtime/settings.py:220–261`). Only the `LOGGING` dict sits in the
  user-owned `production.py.j2`, which is a manifestation of Finding 2 rather than a root.
- **API authorization per callsite.** Killed by `IsAuthenticated` as the DRF default, plus
  rule 19's closed-world declaration detector.
- **Local `0.89.0` tag at `7a66075f`, 695 commits behind HEAD.** It is the documented
  local-only pre-push tag, re-pointed with `git tag -f` (`publish_procedure.md:172–200`), and
  never pushed.
- **Merge `192195e2`'s adapter resolution.** It is consistent with both parents (SA261 moved
  the Markdownx mount to storage, SA263 stopped hook coercion), with no semantic change
  smuggled in.

**Prior rejection reversed this pass:**
- **"Gate wiring held by parity" (killed 2026-10-10 as resolved by SA259).** The workflow
  regions are generated, but the generator itself holds hand copies of the registry's
  per-context gate lists and refuses to run until they match (`sync_ci_gate_jobs.py:498–501`,
  `:1029–1036`). This is now Finding 3 evidence.

**Carried, still killed** (the killing evidence is unchanged):
- blog↔listings co-change.
- core:dr_engine↔backups co-change (declared boundary).
- The core/CLI split under lockstep.
- Apply consistency.
- The typed Stripe adapter (single provider by decision).
- Implicit outbound timeouts (ticket-shaped).
- TenantMiddleware path literals.
- Two DB-connection constructors (a Finding 2 manifestation).
- `contracts/imperative_inventory.py` (deleted).
- `check_quality.sh`'s silent fallback (fixed).
- Core owning the personal-data vocabulary.
- W006 being warning-only.
- SA243's fixed thresholds.
- SA216's retained anonymized row.
- SA223's manifest-owned URL mounts.
- The redaction and personal-data copies.

---

## 12. Questions that would change the ranking

1. How many generated projects besides `bap-web-new` will be long-lived in the next 12 months?
   More than one promotes `generated-file-ownership-unmodeled`. None demotes it to an accepted
   "projects are one-shot" commitment, which retires `beta_migration`. (Carried, unanswered.)
2. Are the SA267 and SA268 parity files permanent, or scaffolding deleted at slice close?
   Scaffolding means the `FROZEN_SURFACE` relocation in `rules-held-by-parity-not-derivation`
   is transient. Permanent confirms it. (New.)
3. How often do the convention gates catch an agent regression that needed a product fix, per
   merge? A high rate validates Finding 3's steelman. (Carried, unanswered.)

**Answered and retired:** prior question 2 ("Is SA204 committed before SA153's go-live?").
Yes: SA153 depends on SA204 in the scheduling table. Effect: Finding 1's ordering risk is
gone, its horizon stays `now`, and its rank is unchanged.

---

## 13. Red flags (out of scope — fix now)

- **0.88.0 on PyPI ships billing that fails every Stripe webhook and every checkout with real
  keys.** The fix is on `v89`, and 0.89.0 is still unpublished, 871 commits after 0.88.0
  ([roadmap.md:13–17](../technical/roadmap.md)). It is tracked in the roadmap's Release
  status. Carried; still present.

---

## 14. Coherence hand-offs

- The theme's TypeScript types enumerate the module set (`useModules.ts:1–27`) beside the
  server-side seam producer. This is rule 31's allowed exception, and the two lists have no
  shared source. (Carried; the structural part is Finding 2.)
- dr_engine copies the storage-absent `ModuleNotFoundError` name check across `_media.py` and
  `_sidecar.py`. (New; the structural part is on the watchlist.)

The prior hand-off "`blog/markdownx_urls.py` ↔ `listings/markdownx_urls.py` copy-pair" is
resolved: SA261 left one `storage/markdownx_urls.py`.

---

## 15. Companion hand-off intake

- **From `coherence-audit.md` (to the architectural audit):**
  - `core-cli-module-knowledge` → merged into watchlist `core-holds-module-vocabulary`. Rule 37
    now gates it, and its exception list is the new trigger.
  - `upward-name-references` → SA265(a) moved `Organization.stripe_customer_id` into billing;
    there is no `stripe_customer_id` in orgs source at HEAD. Killed. The schema move itself is
    Finding 1 evidence: one of the 13 rewrites.
  - `capability-collection` → SA265(b) folded orgs' `getattr` walks onto
    `collect_capabilities`. Killed; noted under the watchlist.
- **From `tech-audit.md` §9 (structural smells):**
  - The session advisory lock → watchlist (carried).
  - The typed Stripe adapter, outbound timeouts, and the second DB constructor → still killed
    (§11).
  - "Generated artifacts are now executed" → recorded as sound decision 5.

---

## 16. Reconciliation log

Append-only. One dated line per ID per pass. Earlier placements are in version control
(`git show 451b3dbf:docs/others/arch-audit.md`, §15).

- 2026-10-13 — `clean-break-schema-no-data-path`: still-open. 13 rewrites in the delta; label-keyed containment measured on `bap-web-new`; bare-file edge still present.
- 2026-10-13 — `generated-file-ownership-unmodeled`: still-open. Django half resolved by SA258 and SA261 (fix-regression passed for that half); steps 30 → 40; six pending on `bap-web-new`; theme types still enumerate modules.
- 2026-10-13 — `rules-held-by-parity-not-derivation`: still-open. SA259 partly removed the mechanism and relocated the rest into the generator's equality refusals; SA267 and SA268 relocated it into 1,381 frozen parity literals; SA263 added a dataflow detector in place of construction; SA264 gave the bundled manifest copy a runtime reader.
- 2026-10-13 — `lockstep-release-unit`: accepted, carried (trigger not fired for known projects; pressure noted).
- 2026-10-13 — `privileged-command-four-stations`: accepted, carried (set unchanged).
- 2026-10-13 — `single-railway-shared-fate`: accepted, carried.
- 2026-10-13 — `core-holds-module-vocabulary`: carried (not fired); trigger extended to rule 37 exception-list growth.
- 2026-10-13 — `manifest-dsl-vocabulary-growth`: carried (`retired_settings` serves five modules).
- 2026-10-13 — `vendored-module-edits-undetected`: carried (`bap-web-new` has no vendored edits).
- 2026-10-13 — `session-advisory-lock-pooling`: carried (persistent connections, no pooler).
- 2026-10-13 — `modules-english-only`: carried.
- 2026-10-13 — `two-filesystem-lock-implementations`: carried.
- 2026-10-13 — `ci-provisioning-hand-pins`: carried.
- 2026-10-13 — `trigger-inputs-legacy-name`: carried.
- 2026-10-13 — `subscription-status-single-writer`: carried.
- 2026-10-13 — Rejected candidate "Gate wiring held by parity": reversed (now Finding 3 evidence).
- 2026-10-13 — Red flag "0.88.0 billing broken on PyPI": still-present (tracked in the roadmap's Release status).
- 2026-10-13 — Prior question 2 (SA204 before SA153): answered (dependency edge) and retired.
- 2026-10-13 — Coherence hand-off "markdownx_urls copy-pair": resolved (SA261).
