# Structural Autopsy: QuickScale

Audited: `2fd8637f` (`v89`) · 2026-10-08 · working tree clean · prompt: deep-architectural-audit v9

> **A full from-scratch pass, followed by a merge with the prior pass.**
>
> - Every finding was first derived independently from current code and history, at the
>   maintainer's request.
> - The prior document (`git show 2fd8637f:docs/others/arch-audit.md`, audited `e2623cb8`)
>   was then read. Each of its items was re-verified against current code and placed under
>   its original ID:
>   - `clean-break-schema-no-data-path` matched.
>   - `generated-file-ownership-unmodeled` is **reopened as regressed**. This pass's
>     independent derivation of it was first written up as `module-contracts-in-user-owned-files`.
>   - W2, W3, W4, and W6 carry on the watchlist.
>   - W7 and W8 are superseded into `rules-held-by-parity-not-derivation`.
>   - The prior resolved findings were re-checked.
> - Placement of every prior ID is in [§15](#15-prior-pass-merge). Closed findings and pass
>   narratives stay in [CHANGELOG.md](../../CHANGELOG.md) and version control, per
>   [decisions.md § Document Responsibilities](../technical/decisions.md#document-responsibilities).

---

## 1. Orientation summary

**Context.** QuickScale is a **code generator plus CLI plus runtime library plus twelve
first-party Django modules**, in one monorepo. It has four Python packages (`quickscale` meta,
`quickscale_core`, `quickscale_cli`, maintainer-only `quickscale_devtools`) and twelve module
packages.

- **Stack:** Python 3.14, Django 6, DRF, PostgreSQL 18, Poetry, Jinja2. The theme is React 19,
  Vite, and TypeScript.
- **Persistence:** generated projects use PostgreSQL with FORCE row-level security in one
  shared schema. The CLI keeps its desired and applied state in YAML (`quickscale.yml`,
  `.quickscale/state.yml`).
- **Two deployment realities:**
  - **(R1) Maintainer repository and release pipeline.** It runs locally and in GitHub
    Actions, publishes to PyPI, and pushes immutable `splits/<module>-module/<version>` tags.
  - **(R2) Generated projects.** Each is one Railway app plus one PostgreSQL 18 service, and
    modules are embedded by git subtree. Exactly one R2 project is deployed, the beta site
    `bap-web` (generated on v0.62.0). SA191 is rebuilding it as `bap-web-new`. A second
    project, `experto-ai-web`, was dropped from the docs on 2026-10-08.
- **Configuration axes:** the 12-module selection (narrowed by `required_modules`), a
  per-module `QUICKSCALE_<MODULE>_ENABLED` flag, orgs mode `solo`/`saas`, storage backend
  `local`/`s3`/`r2`, and deploy target local Docker or Railway. CI exercises module suites
  under the restricted role, plus one generated-project end-to-end lane. Most selection cells
  are exercised only through the per-module suites.
- **Team:** one contributor (4,814 commits since 2025-03-19), working through three
  agent-driven worktree tracks with a serialized merge queue. Cadence is very high: about
  2,000 real commits in 12 months.
- **Data and obligations:** accounts and email addresses, CRM contacts, form submissions,
  Stripe identifiers, and notification addresses. Analytics go to PostHog. No regulatory
  regime is declared, but the product makes a user-facing deletion promise (account removal
  anonymizes the person's data) and claims a GDPR-capable purge.
- **Cost:** the Railway bill is flat by decision. The dominant unit cost is maintainer and
  agent time.
- **Growth direction** ([roadmap](../technical/roadmap.md)): port `bap-web` (SA191), then
  launch a property portal from project-owned extensions, with Spanish public pages,
  prerendering, gallery child tables, and listing-linked CRM inquiries (SA153). Then freeze
  module migration history (SA204).
- **Stated-versus-actual gaps:**
  - "Core imports no module" ([decisions.md:612](../technical/decisions.md)), yet core loads
    storage's services by name.
  - "No per-module wiring blocks in core" (:444), yet core holds social's 509-line manifest
    module and module-named apply steps.
  - "Separate CLI package (independent release cadence)" (:1619), yet versions are lockstep.
  - "No embed/update path for themes" (:118), yet SA214 hardened a "standard upgrade path"
    tool that is not shipped to users.
- **Scope:** the whole monorepo. Depth went to the generator↔project seam, tenancy,
  migrations, and the governance layer.

**Declared architecture**, as rules the system states about itself:
1. `decisions.md` wins every conflict and is updated first.
2. A module is a standard Django app plus one wiring block in its own `module.yml`. Core and
   the CLI hold no per-module wiring (§Module Wiring Authority).
3. Modules sit on layers 0–3. Imports and name references go one way only, and core imports
   no module (Module Conventions rules 5 and 34).
4. Themes are generated once and are user-owned. Themes have no embed or update path (§Themes).
5. Plan/apply: `quickscale.yml` holds desired state and `.quickscale/state.yml` holds applied
   state. Writes are atomic and held under an advisory lock.
6. Fail hard: no silent fallbacks in generator, CLI, manifest, or startup paths. Templates
   render under `StrictUndefined`.
7. PostgreSQL only. Tenant isolation is FORCE RLS under a `NOSUPERUSER NOBYPASSRLS` runtime
   role, with an always-on boot guard.
8. Clean-break migrations: one `0001_initial` per model-bearing module, and upgrades go to a
   fresh database.
9. Lockstep versions. Embeds use the identity-derived immutable split tag.
10. Every Module Conventions rule is enforced by a conformance test (rule 40). Every gate runs
    in every required context (§Publish-Path Gate Coverage). A private split module never
    imports its facade (SA234).
11. No DI containers or service registries. Cross-module needs use `AppConfig` capabilities
    and the listed core ports.
12. Fixed quality lines: no file of 800 lines or more, and CC below 21 (SA243).

**Measurements.** Filter: real commits only, over 12 months.
- 3,259 non-merge commits, of which 1,257 are synthetic subtree-split commits. These are
  detected as trees without `quickscale_core/` and dropped, leaving 2,002 real commits.
- 102 bulk commits touching more than 30 files are dropped, leaving 1,900.
- Lockfiles, changelog, roadmap, audits, `VERSION`, and release notes are excluded from churn.
- Renames are followed (`-M`).

| Measure | Value |
|---|---|
| Lines by area (now) | modules src 42.8k · core src 40.5k (templates 11.9k) · CLI src 18.1k · devtools 12.8k · **scripts/ 69.7k** (118 files: 36.4k tests-of-scripts, 14.5k in 21 `check_*` gates) · docs 25.2k · Makefile 1.7k |
| Trend (first-parent snapshots) | scripts/ 3.5k (2026-04) → 11.3k (07) → 43.9k (08) → 53.6k (09) → 69.7k (10) · gates 7 (08) → 12 (09) → 20 (10) · numbered convention rules 0 (09-25) → 50 (10-06), detectors 0 → 43 · `decisions.md` 1,258 (07) → 2,637 lines · product Python 69.2k (07) → 87.7k (10) |
| Commits touching no product source | 2026-07 70% · 08 86% · 09 57% · 10 42% |
| Churn leaders | `decisions.md` 219 · `Makefile` 88 · `apply_command.py` 70 · `test_templates.py` 70 · `module_config.py` 41 · `generator.py` 35 · `manifest/entry_point.py` 30 |
| Fix density (fix commits / changes) | core:utils .43 · cli:utils .33 · core:runtime .30 · **scripts .29 (79/269)** · core:contracts .29 · manifest .23 · modules .07–.23 |
| Co-change (≥5 shared, degree ≥.5) | blog↔listings 35/.74 (no import; lockstep `pyproject.toml` and convention sweeps; killed) · Makefile↔scripts 53/.60 · core:dr_engine↔backups 14/.67 (declared boundary) · cli commands↔utils 37/.62 |
| Fan-in × churn | `quickscale_core.manifest` 50 importers × 56 changes · `quickscale_core.runtime` 51 × 24 · `orgs.current_org` 25 × 24 |
| Migration census | 10 model-bearing modules × exactly one `0001_initial`; 45 in-place rewrites in 3 months (52 in 6); private symbols referenced from migrations: 1 (`blog/migrations/0001_initial.py:95`) |
| Packages with `_*.py` split files | 12, of which 4 are inside the split-facade gate's `SCAN_ROOTS`. Outside: orgs 22, auth 8, notifications 6, backups 5, social 2, blog 2, storage 1, forms 1 |
| Ownership | one author for every seam. Bus factor is 1 by construction, not a finding at this scale |

**Coverage and residual risk.**
- **Read in full:** the core of `decisions.md` (§Module Conventions, Wiring, Plan/Apply,
  Multi-tenant, Clean-Break, Lockstep, Fail-Hard), `roadmap.md`, `project_contract.yml`,
  `generator/seam.py`, the `_current_org_priming.py` execute wrapper, the
  `module_conventions` core and registry, `gate_registry.json`, the gate-parity and CI-sync
  headers, and the full prior audit.
- **Sampled:** the apply step registry and ledger, the module update guard, crm and blog
  models and migrations, billing's tenant scoping and Stripe version refusal, orgs checks and
  middleware, `module-extension.md`, DR restore vintage, the split-facade gate scope, and the
  anonymize boundary.
- **Skipped:** DR engine internals, notifications/analytics/social internals, publish and
  beta-migration internals, theme TS beyond the seam, and observability. SA226 role
  authorization and SA229 write effects were also not audited at depth, in this pass or the
  prior one.
- **Lens activation:** `active: I, II, III, IV, V, VII, IX, XII, XIII, XV, XVI, XVIII, XIX,
  XX · sampled: VI, VIII, X, XI · inert: XIV (no volume threshold in sight), XVII (flat
  Railway bill, no metered driver beyond maintainer time) · archetypes: code generator, CLI,
  library (runtime facade), multi-tenant output, monorepo`.
- **Lenses that produced findings:** I, II, III, V, XV, XIX, XX, and the §6 generator lens.
- **Unverified out-of-repo architecture:** the `bap-web` and `bap-web-new` repositories,
  Railway service settings (pooling, replicas, proxy), GitHub tag and branch protection, PyPI
  state, Stripe endpoint versions, and PostHog-side deletion.
- **Claims needing runtime confirmation:**
  - That PostgreSQL FK checks and `ON DELETE` actions bypass RLS (documented PostgreSQL
    behavior; not executed here).
  - Whether any non-request write path sets a cross-organization FK.
  - A restored `bap-web` dump migrated under current code (Finding 1).
- **Open lead:** cross-organization references through M2M tag tables (`Contact.tags`,
  `Deal.tags`, `Post.tags`) were not censused.
- **Do not read silence as clearance** for observability, DR internals, role authorization,
  write effects, or the theme's TypeScript.

---

## 2. Enforcement census

| Invariant | Where enforced | Kind | Gate world |
|---|---|---|---|
| Tenant rows isolated by organization | FORCE RLS two-policy contract; restricted runtime role; boot guard (`orgs/checks.py`); ContextVar → per-transaction `SET LOCAL` priming (`_current_org_priming.py:152–260`) | **structural** | — |
| Model enrollment as tenant (incl. project-owned) | `TenantModel` inheritance; W003–W005/E003 system checks run in the project | **structural** | — |
| A tenant row references only its own org's rows | composite `(fk, organization_id)` FK for 6 hand-listed FKs; RLS-scoped serializer lookups elsewhere | **convention** (gated for 6) | open-world (hand-listed pairs) |
| Org-role authorization in module views | one helper (`user_has_org_role`, SA237); its use is checked by harness rules 19/44 (spelling detectors) | structural helper + gated use | open-world (rule 44 admits it) |
| Request integrity (CSRF; webhook signature and replay) | DRF `SessionAuthentication` bases; `check_csrf_exempt_gate.py` pairing; rule 26 detector; unique provider-event DB key | structural + gated | closed-world over `csrf_exempt` |
| Module layer order and file names | `quickscale_core/tests/test_module_import_graph.py` + rule 34; rule 28 allowlists | gated | **closed-world** |
| Option validity | one engine reads each option's `validation` block at plan, apply, and startup (`runtime/conventions.py:340–380`) | **structural** | — |
| Declared removal and anonymize obligations executed | one coordinator per boundary; `_require_obligation_owners` fails deletion closed (`auth/_anonymize_boundary.py:70`); orgs `E002` | **structural** | — |
| Personal-data treatment of user-linked fields | `personal_data_declarations` capability; W006 over candidate fields, in the project | structural check | closed-world over candidates |
| Privileged DB command set | four literal declarations; `test_privileged_command_contract.py` | gated | closed (equality) |
| Stripe API version agrees with the SDK pin | runtime refusal (`billing/services.py:131–135`); five non-test literal copies | structural + convention | — |
| Generator template context complete; output boots | `StrictUndefined` (`generator/generator.py:405`); e2e lifecycle generate → migrate → serve (`test_e2e_full_workflow.py:559–591`) | **structural** | — |
| Module write effects on commit | per-module rollback test; review rule 21 | convention | — |
| Generated-project contract adoption | `--confirm-contract-adoption` flag records step ids; monorepo gate forces a step to be *declared* | **convention** (honor system) | — |
| Vendored module source unmodified in projects | stated in the extension contract only | **convention** | — |
| Shipped migrations immutable | none (SA204 plans a hash-manifest gate) | **none** | — |
| Gate present in every required context | `check_gate_parity.py` compares five hand-written contexts | gated | closed-world (registry ↔ contexts) |
| Private split module never imports its facade | `check_split_facade_imports.py` over 4 hand-listed `SCAN_ROOTS` | gated | **open-world on scope** (8 split packages unscanned) |
| Convention prose ↔ harness | partition test parses `decisions.md` headings; vocabularies hand-mirrored | gated | rule list only |
| Quality thresholds | `check_quality.sh` fixed fail lines (SA243) | gated | closed per metric, **but only over package `src/`** (`:163–178`) |

Findings concentrate on the **convention**, **none**, and open-world rows. The structural rows
are the sound decisions in §8.

---

## 3. Summary table

| Rank | ID | Title | Horizon | Confidence | Size | Reversibility | Problem |
|---|---|---|---|---|---|---|---|
| 1 | `clean-break-schema-no-data-path` | Module schemas have no data upgrade path | now | High | M | one-way door | `0001_initial` is rewritten in place every release, so no database or backup crosses a release |
| 2 | `generated-file-ownership-unmodeled` (regressed) | Module-facing contracts live in user-owned generated files | now | High | M | two-way door | The module↔project seam is emitted once into user-owned files; each change becomes a hand-applied prose step per project |
| 3 | `rules-held-by-parity-not-derivation` | Rules are kept as hand-synced copies held by parity gates | now | High | M | two-way door | Each rule is restated by hand in N places plus a gate to keep them equal; the governance layer outgrew the product |
| 4 | `tenant-reference-equality-partial` | Cross-row tenant equality is storage-enforced for a hand-listed subset | 6–18 months | Medium | S | two-way door (before the freeze) | 6 of 10 shipped intra-tenant FKs carry an org-equality constraint; project FKs are covered by nothing |

---

## 4. Machine-readable index

```yaml
schema: arch-audit/v9
audited: 2fd8637f2d163c65a873ce74337e4f5d88b9ba99
items:
  - {id: clean-break-schema-no-data-path, status: open, rank: 1,
     title: "Module schemas have no data upgrade path", lenses: [I, XIX, XVI],
     horizon: now, confidence: High, size: M, reversibility: one-way door,
     depends_on: [tenant-reference-equality-partial], amplifies: [generated-file-ownership-unmodeled],
     anchors: [docs/technical/decisions.md, quickscale_modules/blog/src/quickscale_modules_blog/migrations/0001_initial.py,
               quickscale_core/src/quickscale_core/dr_engine/recovery.py],
     first_seen: 2026-09-23, last_verified: 2026-10-08}
  - {id: generated-file-ownership-unmodeled, status: open, rank: 2,
     title: "Module-facing contracts live in user-owned generated files", lenses: [V, VII, IX, XV, XIX, "§6 generator"],
     horizon: now, confidence: High, size: M, reversibility: two-way door,
     depends_on: [], amplifies: [clean-break-schema-no-data-path],
     anchors: [quickscale_core/src/quickscale_core/data/project_contract.yml, quickscale_core/src/quickscale_core/generator/seam.py,
               quickscale_core/src/quickscale_core/project_state_hashes.py, quickscale_cli/src/quickscale_cli/commands/contract_vintage.py],
     first_seen: 2026-09-16, last_verified: 2026-10-08}
  - {id: rules-held-by-parity-not-derivation, status: open, rank: 3,
     title: "Rules are kept as hand-synced copies held by parity gates", lenses: [XV, XX, III],
     horizon: now, confidence: High, size: M, reversibility: two-way door,
     depends_on: [], amplifies: [],
     anchors: [scripts/gate_registry.json, scripts/check_gate_parity.py, scripts/sync_ci_gate_jobs.py,
               scripts/module_conventions/core.py, scripts/check_split_facade_imports.py,
               quickscale_core/src/quickscale_core/data/manifests],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: tenant-reference-equality-partial, status: open, rank: 4,
     title: "Cross-row tenant equality is storage-enforced for a hand-listed subset", lenses: [I, II],
     horizon: 6–18 months, confidence: Medium, size: S, reversibility: two-way door,
     depends_on: [], amplifies: [],
     anchors: [quickscale_modules/crm/src/quickscale_modules_crm/models.py, quickscale_modules/orgs/tests/test_tenant_table_conformance.py,
               docs/technical/module-extension.md],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: lockstep-release-unit, status: accepted, title: "Core, CLI, and modules release as one unit", lenses: [XIII, XIX]}
  - {id: privileged-command-four-stations, status: accepted, title: "Privileged command set declared at four stations", lenses: [II]}
  - {id: single-railway-shared-fate, status: accepted, title: "One app and one database per project", lenses: [XVI]}
  - {id: core-holds-module-vocabulary, status: watchlist, title: "Core still names and imports modules", lenses: [III, IX]}
  - {id: manifest-dsl-vocabulary-growth, status: watchlist, title: "Manifest DSL grows one keyword per module need", lenses: [V, XII]}
  - {id: vendored-module-edits-undetected, status: watchlist, title: "Edits under vendored modules/ go undetected", lenses: [XIX, "§6 generator"]}
  - {id: session-advisory-lock-pooling, status: watchlist, title: "Billing mutex is a session-level advisory lock", lenses: [X]}
  - {id: modules-english-only, status: watchlist, title: "Module-rendered pages are English-only", lenses: [I]}
  - {id: two-filesystem-lock-implementations, status: watchlist, title: "Two filesystem-lock implementations (prior W2)", lenses: [IX]}
  - {id: ci-provisioning-hand-pins, status: watchlist, title: "Hand-pinned residue in CI provisioning (prior W3)", lenses: [XV]}
  - {id: trigger-inputs-legacy-name, status: watchlist, title: "trigger_inputs legacy name for an exact allowlist (prior W4)", lenses: [XV]}
  - {id: subscription-status-single-writer, status: watchlist, title: "Subscription.status has one writing module (prior W6)", lenses: [I]}
```

---

## 5. Ranked findings

### Finding 1: Module schemas have no data upgrade path

- **ID:** `clean-break-schema-no-data-path`
- **Rank rationale:** High blast radius, High likelihood, steep compounding.
  - **Blast radius:** data. The only supported upgrade is a fresh database, and backups do not
    restore across releases.
  - **Likelihood:** SA153's go-live creates the first tenant data that cannot be reseeded. It
    is on the roadmap.
  - **Compounding:** the ten `0001_initial` files were rewritten 45 times in 3 months (52 in 6).
  - **Tie-break:** ranked above Finding 2, which scores the same, because this door is one-way
    and closes at a scheduled event.
- **Horizon & trigger:** `now`. The trigger is SA153's go-live on `bap-web-new`, or the first
  module schema change after SA191's cutover.
- **Confidence:** High. The rule, the migration topology, the rewrite counts, and the DR
  refusal were all read or measured; no enforcer of immutability exists. The exact runtime
  symptom on a live database is Medium, because it is inferred.
- **Context dependence:** `wrong-for-now`. The dimension is the first deployed database whose
  data cannot be reseeded. It lives in R2 (generated projects).
- **Problem:** Each model-bearing module ships one `0001_initial` that is rewritten in place
  every release. A database created at version N cannot be migrated to N+1, and a backup taken
  at N cannot be restored under N+1.
- **Evidence** (re-verified this pass):
  - [decisions.md:1852–1870](../technical/decisions.md) says QuickScale "does not support
    in-place database upgrades between releases… every model-bearing shipped module carries
    one final-schema `0001_initial`."
  - Ten modules carry exactly one migration file each.
    `quickscale_core/tests/test_module_migration_topology.py:825` pins that topology.
  - Rewrites over 3 months of filtered commits: auth 3, backups 3, billing 5, blog 7, crm 5,
    forms 5, listings 4, notifications 5, orgs 5, social 3 (45 in total).
  - **Frozen history will pin a private name.** `blog/migrations/0001_initial.py:95`
    references `quickscale_modules_blog.models._BlogMediaAssetImageField`, swapped in by the
    in-place rewrite `6e0ac9da`. Once frozen, that private class can never be renamed or
    moved. Carried from the prior pass, re-verified.
  - `quickscale_core/src/quickscale_core/dr_engine/recovery.py:227–265` refuses a restore with
    "backup module vintage differs from the installed modules". Under clean-break, every
    release therefore makes every existing backup unrestorable on current code.
  - **The containment has a fail-open edge.** A bare file restored with no artifact row and no
    carried vintage returns no issues (`recovery.py:286–287`: "an operator-supplied file that
    records none has nothing to compare"). Carried from the prior pass, still present.
  - `quickscale_core/src/quickscale_core/data/project_contract.yml:79` (`sa221-identity-stem`)
    says "Recreate the project database after adopting… a database created under the previous
    names cannot be carried over."
  - [roadmap.md:165](../technical/roadmap.md) (SA191) says "Data. It cannot move by backup and
    restore". Users are re-invited and submissions are dropped.
- **Counter-evidence:**
  - Searched for incremental migrations: none exist.
  - Searched for a data path in `beta_migration`: it has no dump, restore, `loaddata`, or
    `django_migrations` station. SA214(f) carries **project-owned** app migrations only.
  - Searched for a gate that blocks rewrites: none exists; SA204 specifies one.
  - Searched for a decision record: the Clean-Break decision is deliberate and recorded.
  - SA204 is scheduled, but with release requirement **Optional**
    ([roadmap.md:27](../technical/roadmap.md)) and queued after SA153 on Track 1.
  - SA205's restore refusal is real containment, apart from the bare-file edge above.
- **Why it compounds:**
  - **Growth variable:** deployed databases × releases × schema edits. Every rewrite widens the
    hand-written transform each live database needs.
  - **Private-symbol references** in migrations add names that can never move once frozen (1
    today).
  - **After SA153,** tenant data, users, and CRM inquiries can no longer be reseeded.
  - **Built on top:** RLS installation inside each `0001` (decision rule 2), the DR vintage
    refusal, the topology test, and the identity-stem adoption step.
- **Detection signal:**
  - `InconsistentMigrationHistory`, or a missing-column `ProgrammingError`, during `start.sh`
    migrate.
  - A `migrate --plan` inconsistency against an existing database (SA191 slice (a)).
  - Any adoption step reading "Recreate the project database".
  - SA205 restore refusals that name a vintage mismatch.
  - An `AttributeError` loading a migration after a private field class moves.
- **Steelman:** QuickScale is pre-1.0 with no external users (§Fail-Hard: "no migration
  path"). A single `0001` keeps migration-quality maxima low, keeps RLS installation in one
  place, and let SA215 rename every app label for free. While the only deployed site can be
  reseeded, that freedom is worth more than a data path. Do not fix while no deployed database
  holds data that cannot be reseeded.
- **Correct shape:** Once a database exists that cannot be recreated, every schema change
  that reaches it is an additive, ordered migration. Shipped migration files are immutable
  and reference only symbols with a stability promise. Restore accepts a backup from an older
  vintage by migrating forward, and refuses an unidentifiable one.
- **Do-nothing cost:** After SA153 goes live, every release that touches any of the ten
  schemas forces a hand-written transform (an ETL under RLS) or a skipped upgrade on
  `bap-web-new`. Every release also makes all existing backups unrestorable on current code.
  The current rate is about 45 rewrites per quarter.
- **Options:**
  1. **Freeze at the vintage `bap-web-new` lands on (SA204).** Schema changes from that
     release on ship as `0002+`, and a hash-manifest gate rejects edits to or deletions of
     shipped migrations. Effort M. It is a one-way door, can land incrementally, and removes
     the compounding for every later release. **Live option.**
  2. **Vintage-aware export/import, or per-release "vintage bridge" migrations,** with `0001`
     still rewritten. Effort L. This relocates the cost into a transform per rewrite.
  3. ~~**Accept with restore containment**~~ — landed as SA205. It expires at SA153's
     go-live, which is on the roadmap.
- **Recommendation:** Option 1. Land SA204 **before** SA153's go-live, and raise its release
  requirement from Optional to required for the release `bap-web-new` goes live on. Extend the
  freeze to DR: restore of an older-vintage backup migrates forward instead of being refused,
  and a bare file that records no vintage is refused.
  - **Size:** M.
  - **Reversibility:** `one-way door`. Before it closes, prove on a restored `bap-web` copy that
    `migrate` from the frozen `0001` reproduces the FORCE-RLS parity baseline, as SA204
    specifies.
  - **Guard:** SA204's hash-manifest gate with the inverted `0002` canary, plus a check that
    frozen migrations import no `_`-prefixed module symbols, plus a restore-forward test: a
    backup at vintage N restores and migrates under N+1.
  - **First step:** land Finding 4's composite constraints inside `0001` while it can still
    change, promote `_BlogMediaAssetImageField` to a public field, then record the freeze
    decision.

### Finding 2: Module-facing contracts live in user-owned generated files

- **ID:** `generated-file-ownership-unmodeled` — **regressed, reopened**.
  - The prior closure on 2026-09-24 (SA207 step identities, SA211 emission-derived watch set)
    replaced hand-copied adoption prose with declared, gated adoption steps.
  - That made the compounding visible but did not remove it: the steps are still hand-applied
    per project, and their count has since grown.
  - Under the fix-regression rule, a gate that holds the copy honest does not close the
    finding.
  - This pass derived the same root independently as `module-contracts-in-user-owned-files`.
- **Rank rationale:** High blast radius, High likelihood, steep compounding.
  - **Blast radius:** security and correctness fixes reach deployed projects only as prose
    steps applied by hand (proxy trust, runtime-role provisioning, vendor-secret routing).
  - **Likelihood:** SA191 makes `bap-web-new` a long-lived project, and the next release lands
    on it.
  - **Compounding:** declared adoption steps went from 0 to 30 in the two weeks since SA207
    landed.
- **Horizon & trigger:** `now`. The trigger is SA191's cutover plus the first QuickScale
  release after it.
- **Confidence:** High.
- **Context dependence:** `wrong-for-now`. The dimension is the number of long-lived generated
  projects; the README targets agencies running many client projects. It lives in R2.
- **Problem:** The seam between shipped modules and a generated project is emitted once into
  user-owned files. That seam covers module flags and paths in the React seam, module URL
  routes, DRF composition and error shape, the React API client, and runtime-role
  provisioning. Only two emitted files are QuickScale-managed, so every module or contract
  change becomes a hand-applied prose step per project.
- **Evidence:**
  - [decisions.md:111–119](../technical/decisions.md): themes are copied once, and there is
    "No embed/update path for themes — apply performs no automatic rewrite of user-owned
    files."
  - `quickscale_core/src/quickscale_core/project_state_hashes.py:34–37`: the managed set is
    `settings/modules.py` and `urls_modules.py`, two of about 126 emitted template files.
  - `quickscale_core/src/quickscale_core/generator/generator.py:556–557` renders
    `seam_module_flags` and `seam_module_paths` into the user-owned `templates/index.html` at
    generation time (`themes/showcase_react/templates/index.html.j2:22,29`; producer
    `generator/seam.py:1–47`).
  - The theme's `src/hooks/useModules.ts:1–13` hard-codes the module set, and 36 theme TS files
    name modules.
  - `quickscale_core/src/quickscale_core/data/project_contract.yml` was created 2026-09-24 and
    holds 30 steps, all `minimum: "0.89.0"`, with 36 "Compare and manually adopt" instructions.
    The files those steps name most often are `urls.py` (7), `templates/index.html` (7),
    `settings/base.py` (6), `docker-compose.yml` (6), `Dockerfile` (5), plus the frontend hooks
    `useApi`/`useOrgs`/`useFormSchema`, `start.sh`, and `db/init.sql`. Four module manifests
    add their own steps (backups, billing, orgs, social).
  - Two worked examples of a module change landing in user-owned files:
    - `sa223-orgs-url-mount` (`project_contract.yml:131–137`): a module moving its API forces
      hand edits to `frontend/src/hooks/useOrgs.ts`, `<package>/urls.py`, and any overridden
      orgs templates.
    - `sa235-module-shell-routes` (`:182–188`): "a project that keeps importing
      `react_shell_view` from urls.py… fails to import its URLconf after the embedded-module
      update."
  - `quickscale_cli/src/quickscale_cli/commands/contract_vintage.py:37–38,241`: the
    `--confirm-contract-adoption` flag records every declared id. Nothing checks that the
    project's files changed.
  - Three upgrade mechanisms exist for the same files:
    - prose steps, which ship to users;
    - the fresh-first tool `quickscale_devtools/beta_migration` (about 12.8k lines), which is
      maintainer-only and excluded from publishing (`scripts/prepare_publish.py:27,69`);
    - a prompt-driven port for the one real upgrade
      ([bap-web-migration-prompt.md:4](../planning/bap-web-migration-prompt.md): "the
      fresh-first tool (SA214) is not used for it").

    The prior pass's probe A recorded SA214 tooling 3 of SA191's 9 stations. SA191 now
    bypasses that tooling.
  - The file-ownership taxonomy (`INTENTIONALLY_UNMANAGED`, which grew from 78 to 89 entries,
    [decisions.md:1562](../technical/decisions.md)) lives only in the maintainer tool. The
    product's `apply` and `update` do not consult it.
- **Counter-evidence:**
  - **Runtime seam producer:** the context processors `project_settings` and
    `installed_modules` exist ([frontend.md:184](../technical/frontend.md)). The seam's
    per-module lines are still baked in at generation.
  - **Automated adoption in `update`:** none. `_module_update.py` pulls subtrees and
    regenerates the two managed files only.
  - **Precedent:** SA206's runtime settings facade *did* move the settings contracts into
    upgradable library code, and passed the prior fix-regression audit. It covers settings only.
  - **De-specialization:** the decision ([decisions.md:2193–2213](../technical/decisions.md))
    makes `frontend/src` byte-identical per theme version, so it is replaceable in principle.
    No shipped path replaces it.
  - **SA207/SA211:** they made adoption declared, step-identified, and gated, with
    `scripts/check_project_contract_vintage.py` at 1,351 lines. That makes the cost visible and
    refusable. It does not reduce it.
- **Why it compounds:**
  - **Growth variable:** template-side contract changes per release × long-lived generated
    projects. Every module URL, flag, error-shape, or role change adds steps; this release
    added 30.
  - **Built on top:** the SA206 facade, `project_contract.yml` with its vintage gate and CLI
    refusal and acknowledge flags, the beta-migration taxonomy and smoke gate, the theme seam
    validator, and the producers for rules 31 and 41.
- **Detection signal:**
  - Declared steps per release.
  - Adoption confirmations with no matching file diff.
  - URLconf import failures after `quickscale update`.
  - `bap-web-new` lagging on the proxy-trust or runtime-role contracts.
- **Steelman:** "Full ownership, no vendor lock-in" is the product promise. User-owned files
  let a project restyle and restructure freely; `bap-web` carries a heavily customized design.
  With one deployed site, a prose step costs minutes while a managed boundary costs design
  work. Do not fix if generated projects are meant to be one-shot, with no upgrades after
  generation.
- **Correct shape:** Every emitted file is either QuickScale-managed (regenerated by
  `apply`/`update`, never hand-edited) or user-owned (carrying no QuickScale or module
  contract). Module-facing contracts reach a project only through managed files or the
  versioned runtime library, so a module release changes a project without a hand edit.
- **Do-nothing cost:**
  - Every release adds a batch of prose steps, security fixes included, that `bap-web-new` and
    any client project apply by hand.
  - Three upgrade mechanisms stay maintained (the 12.8k-line tool, its smoke gate, the
    1.35k-line vintage gate, and the steps) while real upgrades go by prompt.
- **Options:**
  1. ~~**Path-enumerated adoption gate**~~ — superseded by SA207/SA211's step identities.
     Landed; it does not remove the mechanism.
  2. **Extend the SA206 pattern to the seam.** Move the seam producer, module flag and path
     rendering, DRF composition, and error-shape parsing into `quickscale_core.runtime`: a
     template tag or context processor for `window.__QUICKSCALE__`, a
     `compose_rest_framework()` helper called from `settings/base.py`, and URL inclusion only
     through managed URLconfs. User-owned files then hold a one-line include. Effort M, low to
     medium risk. Lands one seam piece at a time, each piece costing one final adoption step.
     Removes most of the compounding. **Live option.**
  3. **Add a managed category for infrastructure files** (`index.html`, `urls.py`, the
     `useApi`/`useModules` hooks, `start.sh`, the Dockerfile entrypoint). `update` regenerates
     them under the existing hash guard and refuses on local edits. Effort M–L, medium risk:
     customizations must move to extension points first.
  4. **Accept and document.** Projects are one-shot and upgrades are ports, as in SA191. Retire
     `beta_migration` and the vintage machinery to match. The revocation trigger is a second
     long-lived project or a security fix landing in a template.
- **Recommendation:** Option 2, **before SA191's cutover**, so `bap-web-new` starts on thin
  includes and pays one adoption step rather than one per release. Then retire whichever
  upgrade mechanism is left unused.
  - **Size:** M.
  - **Reversibility:** `two-way door` (library code plus include lines).
  - **Guard:** a closed-world generator test that no Django-side user-owned emitted file
    contains a module name or a module URL name (rule 37's literal-list check, applied to the
    emission mapping). The vintage declaration should trend toward zero steps per release.
  - **First step:** move `seam_module_flags` and `seam_module_paths` from generation time to a
    runtime template tag in `quickscale_core.runtime`.

### Finding 3: Rules are kept as hand-synced copies held by parity gates

- **ID:** `rules-held-by-parity-not-derivation` (new). It supersedes prior watchlist W7 and W8.
- **Rank rationale:** Medium blast radius, High likelihood, steep compounding.
  - **Blast radius:** users are not broken, but this is already the dominant cost.
  - **Likelihood:** already firing.
  - **Compounding:** `scripts/` grew from 3.5k to 69.7k lines in six months and now exceeds all
    module source (42.8k). Gates went from 7 to 20 in two months, and numbered rules from 0 to
    50 in a week.
- **Horizon & trigger:** `now`. Every new rule or gate fires it; SA204 and Finding 4's fix each
  add one.
- **Confidence:** High for the mechanism and the measurements. Medium for attributing delivery
  cost, since commit share is a proxy.
- **Context dependence:** `wrong-for-now`. The dimension is team shape: one maintainer
  coordinating agent tracks. At larger team scale some redundancy pays for itself. It lives
  in R1.
- **Problem:** Each repository rule is authored in prose and then restated by hand in several
  executable places: gate contexts, gate scopes, harness vocabularies, copied manifests,
  repeated literals. A further gate keeps those copies equal. Every new rule therefore costs N
  stations plus a parity check that itself needs maintenance.
- **Evidence:**
  - **Gates.** `scripts/gate_registry.json` declares 20 gates across up to five contexts.
    Adding `check-module-conventions` (`00bcebb1`) and `check-split-facade-imports`
    (`c42f6574`) required edits to about 12 places:
    - the registry;
    - `sync_ci_gate_jobs.py`'s ordered list (`:75–77`) and its `HostedJobSpec` table
      (`:208–216`);
    - the Makefile's `check` aggregate (`:80–81`), help text (`:348–350`), and target
      (`:1105–1119`);
    - `check_ci_locally.sh`'s serial (`:503–513`) and parallel (`:726–731`) cases;
    - `ci.yml` (`:563–619`) and `publish.yml` (`:172–177`);
    - `scripts/README.md` and `validation_policy.md`.

    `check_gate_parity.py` (2,887 lines; docstring `:1–50`) *compares* the registry with five
    hand-written contexts instead of generating them, and its test runs to 4,443 lines.
  - **Conventions.** Rule 40 ([decisions.md:1075–1105](../technical/decisions.md)) puts every
    listed exception "in one test-owned mapping that mirrors this section".
    `scripts/module_conventions/core.py:27` reads "every hand-maintained vocabulary the
    detectors need lives here, mirroring the Module Conventions section". The harness holds
    about 78 module-level constants. `registry.py:84–152` keeps RULES, OPEN, and DELEGATED as a
    partition of the prose headings, enforced by a test that parses `decisions.md`.
    Detectors run to 7.3k lines, with 7.7k lines of tests. `rule_44.py` alone is 1,090 lines,
    and rule 44 still "stays open-world beyond that and is a review rule"
    ([decisions.md:1151](../technical/decisions.md)).
  - **Hand-listed gate scopes** (absorbs prior **W8**). `check_split_facade_imports.py:32–50`
    scans four hand-listed `SCAN_ROOTS` and three `FAMILY_ROOTS`. Twelve packages carry
    `_*.py` split files, and eight of them are outside the scope (orgs 22, auth 8,
    notifications 6, backups 5, and others).
    - **W8's trigger has fired:** SA231 split the backups admin into `_admin_*` siblings
      behind an `admin.py` facade (`2cd4837c`, 2026-10-02). That predates the prior pass's
      "not fired" evaluation, and there are also orgs and auth splits.
    - **No violating import was found:** the module hits were log-channel names allowed by
      rule 46, or names defined in the imported module itself.
    - **The rule therefore holds in those packages by luck, not by gate.**
  - **Copies held equal:**
    - **Bundled manifests** (`quickscale_core/data/manifests/*/module.yml`) are byte-identical
      to the module manifests. All 45 commits that touched a `module.yml` in 3 months also
      touched its copy (Makefile `:1022–1025`).
    - **The Stripe API version literal** appears at five product stations (absorbs prior
      **W7**): `billing/_settings.py:32`, `billing/module.yml:98`, its bundled copy, the CLI's
      `_finalize.py:276`, and `OPERATIONS.md.j2:115–129`. A runtime refusal checks only the
      first (`billing/services.py:131–135`).
    - **The privileged-command set** appears at four stations; "none is a single source of
      truth" ([decisions.md:1832](../technical/decisions.md)).
    - **The composite-FK pairs** are listed twice (Finding 4).
  - **The governance code is exempt from its own bar.** `check_quality.sh` scans only package
    `src/` directories (`:163–178`). Ten non-test gate and tooling scripts exceed the 800-line
    fail line (for example `check_gate_parity.py` at 2,887 lines, `publish_module.py` at 1,651,
    and `check_project_contract_vintage.py` at 1,351). The largest product file is 791 lines.
  - **Defect gravity:** `scripts/` has a fix density of .29 (79 of 269 changes), against
    .07–.23 for the modules.
  - **Coordination hotspot:** `decisions.md` is the most-changed file (219 of 1,900 filtered
    commits, 2,637 lines, doubled since July). The roadmap names it a cross-track conflict
    surface ([roadmap.md:98](../technical/roadmap.md)).
- **Counter-evidence:**
  - **Partial derivation exists.** `sync_ci_gate_jobs.py` generates the `ci.yml` job regions
    and the e2e allowlist. It carries its own per-gate tables, though, and the Makefile, the
    local runner, and `publish.yml` stay hand-written.
  - **SA250** derives the rule *list* from the prose headings, but not the vocabularies.
  - **The team removes governance once it sees the cost:** SA243 deleted about 800 lines of
    baseline-ratchet code ([decisions.md:2523](../technical/decisions.md)).
  - **No budget:** no gate budget or retirement rule was found.
  - **Reversal of a prior rejection.** The prior pass (`95af8e1b`) killed "the conventions
    harness as a 4,749-line god script" as a flat cost. What killed it has changed:
    - The cost is not flat. Rules went 36 → 50 and gates 17 → 20, the harness is now 7.3k
      lines of detectors plus 7.7k of tests, and `scripts/` went 53.6k → 69.7k in a month.
    - This finding's root is different: copies kept equal by parity, not harness size.
- **Why it compounds:**
  - **Growth variable:** rules, gates, and gate scopes.
  - **Unit costs:** a new gate costs about 12 stations. A new convention rule costs prose, a
    detector, vocabulary entries, a control case, and a partition entry. A new split package
    needs a hand edit to `SCAN_ROOTS`, or it goes unscanned.
  - **Measured growth:** 13 gates in two months, 50 rules and 43 detectors in a week, and
    58k lines of `scripts/` in three months.
  - **Side effects:** the copies multiply cross-track conflicts, and the parity tooling is the
    repository's highest-fix-density area.
  - **Built on top:** 20 gates, 43 detectors, three workflows, the local CI runner, and the
    track-ownership model.
- **Detection signal:**
  - The monthly share of commits touching no product source (42–86% from July to October).
  - Fix commits under `scripts/`.
  - Parity failures fixed without any product change.
  - A Stripe bump that misses one of the five stations.
- **Steelman:** One maintainer runs three parallel agent tracks. Agents follow executable
  checks far more reliably than prose, and pre-1.0 is the cheapest moment to converge twelve
  modules. Some copies are forced by packaging and trust: the wheel needs manifests without
  module source, and `publish.yml` re-runs every gate because publication is irreversible.
  Accept the cost if the gates measurably stop agent regressions and the counts plateau.
- **Correct shape:** Every rule has exactly one authored, executable source. Every other place
  the rule must appear, including a gate's scope, is generated or derived from that source or
  deleted, never kept equal by a parity check. Invariants that code can make true by
  construction are enforced there, and their detectors are removed. Governance code meets the
  same quality bar as product code.
- **Do-nothing cost:**
  - About 12 edits per new gate, plus a detector and vocabulary per rule. SA204 and Finding 4
    each add a gate.
  - At current rates the next 12 months add more governance surface than product surface.
  - Split packages outside the hand-listed scope stay unchecked.
  - Defects in `scripts/` (fix density .29) keep consuming delivery time.
- **Options:**
  1. **Generate and derive instead of compare.** Make `gate_registry.json` the only gate list
     and emit everything else from it: a `gates.mk` include, the local runner's stage list, the
     `ci.yml`/`publish.yml`/e2e regions, and the docs table. `check_gate_parity.py` shrinks to
     "generated files are current". Derive gate scopes from the file layout: any package with a
     `_*.py` sibling and a re-exporting module is in scope. Build the bundled manifests at wheel
     build time instead of committing copies. Read the Stripe version from one constant. Effort
     M, low risk, incremental. A new gate drops from about 12 stations to 2. **Live option.**
  2. **Retire rules by construction.** Classify each of the 50 rules as structural (a base
     class, runtime check, or generated value), derivable (for example rule 1's setting names,
     rule 2's identities from the app label, or rule 38's README option lists from the
     manifest), or review-only. Delete the detectors in the first two classes, and stop writing
     spelling detectors for open-world rules (44, 50). Effort M, medium risk.
  3. **Accept with a budget.** No new gate or rule without retiring one, and `scripts/` inside
     `check_quality.sh`. Effort S.
- **Recommendation:** Option 1 plus option 3's budget, with `scripts/` brought under the
  quality gate. Apply option 2 whenever a rule is next touched.
  - **Size:** M.
  - **Reversibility:** `two-way door`.
  - **Guard:** one "generated files are current" check, plus `check_quality.sh` scanning
    `scripts/`, plus a scope-derivation test that fails when a package with `_*.py` split files
    is outside the split-facade scan.
  - **First step:** generate the Makefile gate targets and the `check_ci_locally.sh` stage list
    from `gate_registry.json`.

### Finding 4: Cross-row tenant equality is storage-enforced for a hand-listed subset

- **ID:** `tenant-reference-equality-partial` (new).
- **Rank rationale:** High blast radius, Medium likelihood, linear compounding.
  - **Blast radius:** this crosses the isolation boundary. A cross-organization reference lets
    one organization's delete cascade into another's rows, or block another's purge, because
    referential actions bypass RLS.
  - **Likelihood:** harm needs a write path that skips RLS-scoped validation. SA153 adds new
    tenant references in project code that nothing checks.
  - **Compounding:** a fixed cost per new foreign key.
- **Horizon & trigger:** `6–18 months`. The triggers are SA153 slice (a), the gallery child
  tables, and slice (d), the listing-linked CRM inquiry.
- **Confidence:** Medium. The mechanism was read and the FKs censused. Request paths are
  mitigated: crm serializers resolve IDs through `all_objects` under RLS
  (`crm/serializers.py:268–275, 552–565`). **Settling step:** census the non-request writers
  (commands, seeds, project services, operator paths) for any that set these FKs from
  unscoped IDs.
- **Context dependence:** `wrong-regardless` for the isolation invariant. It lives in R2.
- **Problem:** The rule "a tenant row references only its own organization's rows" has no
  structural owner. A composite `(fk, organization_id)` constraint enforces it for six
  hand-listed FKs. Other intra-tenant FKs, and every project-owned FK, depend on each write
  path validating through RLS-scoped lookups. PostgreSQL FK checks and `ON DELETE` actions
  bypass RLS.
- **Evidence:**
  - **What the decisions require.**
    [decisions.md:1842](../technical/decisions.md) requires a denormalized `organization_id`
    and a direct RLS policy on child tables, but says nothing about reference equality.
    `:1848` describes composite FKs as "added by the `_ADD_COMPOSITE_FK_SQL` helper".
  - **Census of shipped FKs between tenant models:** ten.
    - **With a composite org FK (six):** crm `ContactNote.contact` and `DealNote.deal`; forms
      `FormField.form`, `FormSubmission.form`, `FormFieldValue.submission`, and
      `FormFieldValue.field`.
    - **Without one (four):** crm `Contact.company` (`models.py:101`, CASCADE), `Deal.contact`
      (`:172`, CASCADE), and `Deal.stage` (`:184`, PROTECT); blog `Post.category`
      (`models.py:348`, SET_NULL).
  - **Coverage is open-world.** The pairs are hand-listed twice
    (`orgs/tests/test_composite_fk_conformance.py:24`,
    `orgs/tests/test_tenant_table_conformance.py:50`). Nothing derives the set of
    tenant-to-tenant FKs from model metadata.
  - **Project side:** [module-extension.md §Project-Owned Tenant Models](../technical/module-extension.md)
    documents RLS, provider IDs, removal, and personal data, but never mentions composite or
    child equality (0 occurrences). `orgs/checks.py` registers no reference-equality check.
    `add_composite_child_fk` is public (`orgs/tenancy.py:41`) but undocumented for projects.
- **Counter-evidence:**
  - **Trigger-based equality on the four uncovered FKs:** none. The crm and blog `0001`
    migrations add composites for notes only.
  - **A runtime system check:** W001–W006 and E001–E004 cover no references.
  - **Write-path validation:** DRF serializers reject other-org IDs through RLS-scoped
    lookups, and the admin uses `make_same_org_validated_form`. This mitigation is real.
  - **Still unguarded:** ORM writes outside requests (commands, seeds, project services, data
    migrations) and operator paths.
  - **The prior pass's probe B** exonerated SA153's personal-data and notification stations.
    It did not examine reference equality.
- **Why it compounds:**
  - **Growth variable:** tenant-to-tenant FKs. There are ten shipped today, SA153 adds
    gallery→property and inquiry→listing in project code, and SA154 adds more.
  - **Per new FK:** each must remember both the composite constraint and its two list entries.
    For project FKs nothing reminds anyone.
  - **Built on top:** the crm and forms data models, the PROTECT teardown in the purge plan,
    and SA153.
- **Detection signal:**
  - A per-FK join comparing `organization_id` on both sides returns rows.
  - Purge refusals that name another organization's rows.
- **Steelman:** The composite FKs went on detail tables reached through user-supplied parent
  IDs. Peer references such as `Deal.contact` are only ever set through RLS-scoped
  serializers, so storage enforcement there is belt-and-braces. It also needs
  `UNIQUE(id, organization_id)` on every parent. Do not fix if every tenant write is a request
  write.
- **Correct shape:** Every FK between tenant models, shipped or project-owned, is backed by a
  storage-level organization-equality constraint or carries a recorded exemption. The set is
  derived from model metadata at check time.
- **Do-nothing cost:** SA153 ships at least two new unchecked tenant references. Every seed,
  command, or project service that writes IDs is a chance to persist a cross-organization
  reference, which then lets one org's deletion cascade into another's rows or block another
  org's purge (the GDPR path).
- **Options:**
  1. **A derived orgs system check.** Walk the marker-derived tenant models and find FKs that
     point to other tenant models. Require a composite constraint (checked in
     `pg_constraint`) or a declared `tenant_reference_exemptions` entry. The check runs in
     projects, like W006. Also document `add_composite_child_fk` in `module-extension.md`.
     Effort S–M, low risk, can start as a Warning. **Live option.**
  2. **A `TenantForeignKey` field.** It emits the composite constraint through its own
     migration operation, making the invariant structural by construction. Effort M, medium
     risk.
  3. **Accept and rely on RLS-scoped validation,** documenting that all tenant writes go
     through request paths. The revocation trigger is the first non-request writer.
- **Recommendation:** Option 1, before SA153 slice (a). Add composites for the four shipped
  FKs in the same change, while `0001` can still change; after SA204's freeze they would need
  `0002` migrations.
  - **Size:** S.
  - **Reversibility:** `two-way door` before the freeze.
  - **Guard:** the derived check itself, closed-world over metadata. It replaces both
    hand-listed tuples.
  - **First step:** a W-level check that lists every tenant-to-tenant FK with its constraint
    status.

---

## 6. Change-cost probes

| Probe | Stations, measured | Verdict |
|---|---|---|
| **SA153 gallery child table in a project app** | (1) model on `TenantModel`/`AbstractListing` with `Meta` inheritance; (2) project migration calling `apply_force_rls` (base policy name ≤56 bytes); (3) composite org FK — undocumented, unchecked; (4) `provider_id_classification`; (5) `removal_obligations`; (6) `personal_data_declarations` (+ handler if not `KEEP_LINK`); (7) `TenantModelAdmin`; (8) `about_users` on any notification; (9) boundary tests. Runtime checks W003–W006/E001–E003 hold (1), (2), (4), (5), (6) **in the project** | Mostly **exonerating**: host-project code is under the module contract (§8). One gap → Finding 4 |
| **SA153 listing inquiry + project model with an agent email + "inquiry received" email** (prior probe B, re-verified) | inquiry lands in `crm` (already declared); the email field needs a `personal_data_declarations` entry (W006 warns otherwise); the new sender must pass the required `about_users` keyword (`notifications/services.py:86–91`); rule 50 fails a hand-stamped key | **Exonerated** by SA246/SA248. Reference equality of inquiry→listing is the Finding 4 gap |
| **SA191 rebuild of `bap-web`** (prior probe A, re-evaluated) | 9 stations (facade import, port, project-owned migrations, reseed, verify, deploy + runtime role, Stripe endpoint, rollback, label/URL renames). The prior pass recorded SA214 tooling 3 of them; SA191 now runs as a prompt-driven port that does not use that tool | **Finding evidence** → Findings 1 (reseed) and 2 (three upgrade mechanisms) |
| **A module contract change reaching a deployed project** (historical: SA223 moved orgs' JSON API to `/orgs/api/`) | Automatic: subtree pull, `urls_modules.py` and `settings/modules.py` regeneration. Manual: `frontend/src/hooks/useOrgs.ts`, `<package>/urls.py`, overridden orgs templates. Declaration: `project_contract.yml` step + vintage gate. Operator: `--confirm-contract-adoption` | **Finding evidence** → Finding 2 |
| **Adding one gate** (historical: `check-module-conventions`, `check-split-facade-imports`) | ≈12 stations (listed in Finding 3), held by a parity checker rather than generated | **Finding evidence** → Finding 3 |
| **Adding a module option** (prior probe C) | the option, its `validation` block, and its `django_setting` in `module.yml`; plan, apply, and the startup check read the same block | **Exonerated** (carried; consistent with sound decision 3; not re-run in detail) |
| **Retiring one module** (`social`, removal probe) | 39 non-test files outside the module: 18 generator templates plus 21 others (8 in core: `social_manifest.py`, `module_options.py`, `seam.py`, `module_catalog.py`, the bundled manifest, `project_contract.yml`, and two `runtime` files; CLI `_finalize.py` and `_config.py`; 2 in devtools; 8 in scripts; root `pyproject.toml`), plus the split branch, `AUTHORITATIVE_MODULE_COUNT`, docs and tests | **Watchlist** (`core-holds-module-vocabulary`): no retirement or addition is planned |

---

## 7. Fix order and interactions

- **Finding 4 → Finding 1.** Add the four missing composite constraints, and promote
  `_BlogMediaAssetImageField`, while `0001` may still change. After SA204's freeze each needs a
  `0002`. Both should land before SA153's slice (a) and its go-live.
- **Finding 1 and personal data.** If SA153 adds personal fields to shipped modules, they land
  as `0002+` migrations *and* declaration entries, so the freeze's first migrations are born
  classified (carried from the prior pass).
- **Finding 2 before SA191's cutover.** If `bap-web-new` is ported first and the seam moves
  later, it pays one extra round of adoption.
- **Findings 1 and 2 amplify each other.** Together they make every upgrade a big-bang event:
  code by hand and data by reseed. Fixing either one halves the cost of the other.
- **Finding 3 is independent but cheapens everything else.** Every other fix adds a guard
  (SA204's hash gate, Finding 4's check, Finding 2's emission test). With option 1 in place,
  each costs 2 stations instead of about 12. Do option 1 first if more than one new gate is
  coming.
- **No conflicts found.** Finding 2's move generates one last adoption step per seam piece,
  which the existing vintage gate already handles.

---

## 8. Sound load-bearing decisions (preserve through remediation)

1. **Tenant isolation is structural and fails closed.**
   - FORCE RLS runs under a `NOSUPERUSER NOBYPASSRLS` role, with an always-on boot guard.
   - The tenant carrier is a ContextVar primed into a **transaction-scoped** `SET LOCAL` by a
     connection execute wrapper. It fails closed when no org is set and is safe under
     transaction pooling (`orgs/_current_org_priming.py:152–260`).
   - Every tenant model is on `TenantModel`, and enrollment follows from the marker; it is
     never listed.
2. **The module contract reaches host-project code through declarations and one fail-closed
   coordinator.**
   - Removal and anonymize obligations, provider-ID classification, and personal-data
     treatments are declared on each app's own `AppConfig`.
   - Each boundary discharges them through one coordinator that fails the deletion closed on
     an owner without a handler (`auth/_anonymize_boundary.py:70`).
   - Orgs system checks (W003–W006, E001–E003) run where the project's own models are
     installed, so the rules do not stop at the vendored boundary.
   - [module-extension.md §Project-Owned Tenant Models](../technical/module-extension.md).
3. **Module boundaries are declared once and checked closed-world.**
   - Options, URL mounts, and UI routes live in `module.yml` (SA217, SA223, SA235).
   - One engine validates options at plan, at apply, and at startup through
     `MODULE_SETTINGS_SCHEMA` (`runtime/conventions.py:340–380`).
   - Layer order and package file names are gated closed-world
     (`test_module_import_graph.py`, rule 28).
4. **The runtime settings facade (SA206).**
   - Executable contracts ship as versioned library code through the lockstep pin, not as
     template copies.
   - This is the precedent Finding 2's fix extends.
5. **Generation and release integrity.**
   - Templates render under `StrictUndefined` (`generator/generator.py:405`), and the e2e
     lifecycle generates, migrates, and serves a project (`test_e2e_full_workflow.py:559–591`).
   - The default embed consumes the immutable `splits/<module>-module/<version>` tag, never a
     moving branch (`utils/git_naming.py:61`, `_module_embed.py:273`), and sealing fails
     closed.

---

## 9. Accepted commitments

- **`lockstep-release-unit`**
  - **Commitment:** each module's version equals core's, an embed fails on mismatch, and
    projects pin `>=X.Y.0,<X.(Y+1).0` ([decisions.md §Module Version Lockstep](../technical/decisions.md#module-version-lockstep), SA117).
  - **Containment:** canonical version comparison at embed and at wiring regeneration, plus
    `check-core-compat`.
  - **Revocation trigger:** a runtime fix must reach a deployed project that cannot take the
    same release's module and contract changes.
  - **This pass:** not fired (one deployed project, being rebuilt).
- **`privileged-command-four-stations`** (lineage: prior W1, then a census copy-pair
  correction)
  - **Commitment:** `{migrate, createcachetable}` is declared in orgs `checks.py:103`, in
    `runtime/settings.py:243`, in the CLI's `development_commands.py:44`, and in `start.sh`.
    The duplication is deliberate ([decisions.md:1832](../technical/decisions.md)).
  - **Containment:** `test_privileged_command_contract.py`.
  - **Revocation trigger:** a third privileged command.
  - **This pass:** not fired (the set is unchanged since `52144290`, 2026-07-11).
- **`single-railway-shared-fate`**
  - **Commitment:** one app and one PostgreSQL per project, with all tenants in one schema.
    Rejected alternatives are recorded ([decisions.md §Multi-tenant SaaS Architecture](../technical/decisions.md#multitenant-saas-architecture)).
  - **Containment:** DR capture and restore.
  - **Revocation trigger:** an availability or SLA commitment, or one tenant able to exhaust
    shared capacity.
  - **This pass:** not fired.

---

## 10. Watchlist

This holds nine items, above the usual five, because every carried prior item was kept as
requested. Each carries this pass's trigger evaluation.

- **`core-holds-module-vocabulary`** (new)
  - **What:** core still names modules.
    - `manifest/social_manifest.py` holds 509 lines of social's provider and URL logic.
    - `contracts/module_options.py` holds analytics, backups, billing, notifications,
      storage, and social constants.
    - The canonical apply step registry has four module-named steps (`apply/step.py:99–123`).
      The three env-example steps now invoke the one declarative `.env.example` sync
      (`env_sync.py:1–27`) and keep their names only as recovery sentinels, so the prior
      `module-env-contract-hand-wired` resolution holds.
    - `dr_engine/_metadata.py:76–81` imports `quickscale_modules_storage.services` by name. That
      bypasses the core-port pattern, and static import gates cannot see it.
  - **Why it doesn't qualify yet:** the module population is fixed at 12.
  - **Trigger:** teams is scheduled, a 13th module is added, or a new module-named apply step
    appears.
- **`manifest-dsl-vocabulary-growth`** (new)
  - **What:** the manifest engine grew from 309 to 6,804 lines between May and October. It is
    the highest fan-in × churn in core (50 importers × 56 changes). Four cross-option keywords
    were each added for one module.
  - **Why it doesn't qualify yet:** the strong steelman holds; plan-time validation runs before
    any module code exists.
  - **Trigger:** a new validation keyword added for a single module.
- **`vendored-module-edits-undetected`** (new)
  - **What:** modules are embedded as mutable source. The update guard
    (`_module_update.py:100–194`) checks state and option drift, not edits under
    `modules/<name>/`. `bap-web` already carried in-place `modules/forms` edits.
  - **Trigger:** a second project with vendored edits, or a subtree-pull conflict in
    `update`.
- **`session-advisory-lock-pooling`** (new, from a tech-audit structural smell)
  - **What:** billing's per-org mutex is a session-level `pg_advisory_lock`. Tenant priming is
    transaction-scoped and safe.
  - **Trigger:** PgBouncer transaction pooling, or a pooled `DATABASE_URL`.
- **`modules-english-only`** (new)
  - **What:** rule 14 bans `gettext`, and only 1 of 63 module templates uses translation tags.
    Auth's 12 `templates/account/` overrides shadow allauth's translated templates. A Spanish
    site can localize module pages only by copying templates, and the copies drift: the
    `sa223` step had to audit overridden orgs templates.
  - **Trigger:** SA153 or SA154 needs a module-rendered page (auth, forms, blog) in Spanish.
- **`two-filesystem-lock-implementations`** (prior **W2**)
  - **What:** `quickscale_core/advisory_lock.py` (514 lines) and `dr_engine/_lock.py` (298
    lines). A search of product source for `O_EXCL`, `fcntl.flock`, and `msvcrt.locking` finds
    only these two.
  - **Trigger:** a third implementation.
  - **This pass:** **not fired**; both were last changed 2026-09-05.
- **`ci-provisioning-hand-pins`** (prior **W3**)
  - **What:** `scripts/provision_ci_postgres.sh` derives the isolation set from the inventory
    plus `test_rls_boundary.py` presence (`:153–159`). It still hand-pins a `backups` profile
    (`:126–128`) and an `orgs` literal (`:159`).
  - **Trigger:** a 13th module.
  - **This pass:** **not fired** (12 modules).
- **`trigger-inputs-legacy-name`** (prior **W4**)
  - **What:** `trigger_inputs` is the ordered, bidirectional e2e path-allowlist partition
    (`check_gate_parity.py:42–50`). `sync_ci_gate_jobs.py:349–354` consumes it to build that
    allowlist.
  - **Trigger:** any context skipping a gate on it.
  - **This pass:** **not fired**; no skip is keyed on it.
- **`subscription-status-single-writer`** (prior **W6**)
  - **What:** `Subscription` and its `status` are written only inside billing.
  - **Trigger:** a second payment provider or an outside writer.
  - **This pass:** **not fired**; no module outside billing references `Subscription`.

---

## 11. Rejected candidates

**Killed this pass:**
- **blog↔listings co-change (35 shared commits, degree .74).** No import exists either way.
  The shared files are `pyproject.toml` (14), README, and views, so lockstep bumps and
  convention sweeps explain it, not a hidden contract.
- **core:dr_engine↔backups co-change.** This is the declared DR boundary (F5/M10) with a core
  port; the co-change is the extraction itself.
- **The core/CLI split under lockstep** (`_version.py` co-change 20/20). Generated projects
  depend on the core runtime only, and the split keeps the CLI's dependencies out of them.
- **Apply consistency (16 irreversible steps).** Presence-gated idempotent rerun with a
  recovery ledger fits a single-operator CLI. No cross-mechanism reconciliation glue was found.
- **Typed Stripe adapter** (a tech-audit smell). Single provider is a recorded decision, and
  no second provider is planned (see `subscription-status-single-writer`).
- **Implicit outbound timeouts.** Ticket-shaped; it belongs to the tech audit.
- **TenantMiddleware path literals.** Resolved: orgs paths reverse `quickscale_orgs` routes
  (`middleware.py:71–99`), and only the listed exempt prefixes remain.
- **Two DB-connection constructors** (`start.sh` and the runtime). The `start.sh` half is a
  user-owned template, which makes it a manifestation of Finding 2.
- **Split-facade violations in unscanned packages.** None were found. The hits were rule 46
  log channels, or orgs `_personal_data.py:226` importing a name `tenancy.py` defines itself.
  The scope gap is Finding 3.
- **`contracts/imperative_inventory.py`.** It is vestigial (163 lines, every inventory empty).
  A deletion ticket.
- **`check_quality.sh:170–172`.** It falls back silently to a hardcoded path list when
  discovery finds nothing: a fail-open inside a gate. A ticket for the tech audit.

**Carried from the prior pass, still killed (re-checked where noted):**
- **Core owning the personal-data vocabulary (SA246).** These are generic records consumed by
  modules, and the dependency direction is correct.
- **W006 is warning-only.** Deliberate: startup must not block. The closed-world test is the
  hard gate for shipped code.
- **SA243's fixed thresholds as a regression of the ratchet.** Sound per metric. The scope
  excluding `scripts/` is now Finding 3 evidence.
- **SA216's retained, anonymized user row.** It keeps attribution and needs no null-out pass.
  Operator hard delete still applies rule 27.
- **SA223's manifest-owned URL mounts.** One declaration per module (sound decision 3).
- **Redaction copies and personal-data ownership** (coherence hand-offs). Resolved by SA245
  (core redaction helpers, rule 47) and SA249 (per-module declarations, rule 49, with a
  closed-world W006).

**Prior rejections reversed this pass:**
- **"SA214's carry tooling has no growth variable."** It is one of three upgrade mechanisms,
  and the one real upgrade bypasses it (Finding 2).
- **"The conventions harness is a flat-cost god script."** The cost is measured and growing
  (Finding 3).

---

## 12. Questions that would change the ranking

1. How many generated projects besides `bap-web-new` will be long-lived (client or agency) in
   the next 12 months? `experto-ai-web` was dropped from scope on 2026-10-08. More than one
   promotes `generated-file-ownership-unmodeled`. None demotes it to an accepted "projects are
   one-shot" commitment.
2. Is SA204 committed to land before SA153's go-live, or can it slip as "Optional"? The answer
   sets `clean-break-schema-no-data-path`'s horizon.
3. How often do the convention gates catch an agent regression that needed a product fix, per
   merge? A high rate validates the steelman of `rules-held-by-parity-not-derivation` and
   moves it toward accepted-with-budget.

---

## 13. Red flags (out of scope — fix now)

- 0.88.0 on PyPI ships billing that fails every Stripe webhook and every checkout with real
  keys. The fix is on `v89`, but 0.89.0 is unpublished ([roadmap.md:14](../technical/roadmap.md)).
  Tracked in the roadmap's Release status. The prior pass recorded no red flags.

---

## 14. Coherence hand-offs

- `blog/markdownx_urls.py` and `listings/markdownx_urls.py` differ only in the module name.
  This copy-pair between siblings is listed by rule 28.
- The theme names the module set in 36 TypeScript files beside the server-side seam producer.
  This is rule 31's allowed exception, but the two lists have no shared source.

---

## 15. Prior-pass merge

This is where every item of the prior document (audited `e2623cb8`) lives now, as requested by
the maintainer. It records present placement, not a history ledger.

| Prior ID | Prior status | Now | This pass's evidence |
|---|---|---|---|
| `clean-break-schema-no-data-path` | open, rank 1 | **open, rank 1** | Re-derived independently; the rewrite rate is back up (45 in 3 months); private-symbol pin and bare-file restore edge re-verified |
| `generated-file-ownership-unmodeled` | closed 2026-09-24 (SA207/SA211) | **open, rank 2 — regressed** | The closure relocated the compounding into declared, gated prose steps: 0 → 30 steps since 2026-09-24, three upgrade mechanisms, honor-system adoption |
| W7 Stripe API version literal at five stations | watchlist | **superseded** by `rules-held-by-parity-not-derivation` | Five stations re-verified; one runtime refusal guards only the billing constant |
| W8 split-facade gate scope hand-listed | watchlist | **superseded** by `rules-held-by-parity-not-derivation` (trigger fired) | SA231's backups admin split (`2cd4837c`) and the orgs and auth splits sit outside the four `SCAN_ROOTS`; no violation found |
| W2 two filesystem-lock implementations | watchlist | **watchlist** `two-filesystem-lock-implementations` | Not fired |
| W3 hand-pinned residue in CI provisioning | watchlist | **watchlist** `ci-provisioning-hand-pins` | Not fired |
| W4 `trigger_inputs` legacy name | watchlist | **watchlist** `trigger-inputs-legacy-name` | Not fired |
| W6 `Subscription.status` single writer | watchlist | **watchlist** `subscription-status-single-writer` | Not fired |
| W1 privileged command set (superseded 2026-09-23) | superseded | **accepted** `privileged-command-four-stations` | The set lives at four stations by recorded decision; contract test passes |
| W5 hand-authored ownership taxonomy (superseded 2026-09-23) | superseded | inside `generated-file-ownership-unmodeled` | `INTENTIONALLY_UNMANAGED` 78 → 89, maintainer-tool only |
| `notification-person-link-by-convention` | closed (SA248) | resolved, verified | `send_notification` requires `about_users` (`notifications/services.py:86–91`); rule 50 in the harness |
| `personal-data-coverage-shipped-only` | closed (SA246) | resolved, verified | Per-app `personal_data_declarations`; W006 over project models (`orgs/checks.py:345–384`) |
| `split-facades-patch-coupled` | closed (SA234) | resolved, verified | `check-split-facade-imports` is registered in four contexts; residual scope gap → Finding 3 |
| `deletion-invariants-per-boundary-reimplementation` | closed (SA213) | resolved, verified | App-declared obligations, one coordinator, E002 (`orgs/checks.py:513–547`) |
| `module-env-contract-hand-wired` | closed | resolved, verified | One declarative `.env.example` sync (`apply/steps/env_sync.py:1–27`); the per-module specs are rule 37's listed exception (watchlist `core-holds-module-vocabulary`) |
| Prior questions | purged 2026-10-08 | — | The `experto-ai-web` context is reflected in question 1 |
| Prior red flags | none | — | One red flag this pass (tracked) |
