# Structural Autopsy: QuickScale

Audited: `30b0b6b1` (`v89`) · 2026-10-16 · working tree clean · prompt: deep-architectural-audit v10

> **Re-run pass.** The prior deliverable (audited `451b3dbf`, 2026-10-13, later annotated by
> `11da2d79` and `77fea4d4` to point remediations at tickets) was read first. All 59 non-merge
> commits in `451b3dbf..30b0b6b1` were classified. The delta is almost entirely remediation of
> the three open findings, and each remediation went through the fix-regression audit.
> **Bottom line:** no new findings, and no prior finding is resolved. All three are **still
> open, each with a much narrower residual**:
> - Finding 1 is down to one label-keyed branch and an unlifted decision rule.
> - Finding 2 is down to theme pages and other non-seam user-owned files. Its step rate did not
>   fall.
> - Finding 3 is down to one small relocation, minted by SA280 (b).
>
> Ranks are re-derived: `generated-file-ownership-unmodeled` moves to rank 1. The prior pass's
> full text is in version control (`git show 30b0b6b1:docs/others/arch-audit.md`).

---

## 1. Orientation summary

**Context.** QuickScale is a **code generator plus CLI plus runtime library plus twelve
first-party Django modules**, in one monorepo: `quickscale` (meta), `quickscale_core`,
`quickscale_cli`, maintainer-only `quickscale_devtools`, and twelve module packages.

- **Stack:** Python 3.14, Django 6, DRF, PostgreSQL 18, Poetry, Jinja2. The theme is React 19,
  Vite, and TypeScript.
- **Persistence:** generated projects use PostgreSQL with FORCE row-level security in one
  shared schema. The CLI keeps desired and applied state in YAML (`quickscale.yml`,
  `.quickscale/state.yml`).
- **Deployment realities:**
  - **(R1) Maintainer repository and release pipeline:** local runs and GitHub Actions, PyPI,
    and immutable `splits/<module>-module/<version>` tags.
  - **(R2) Generated projects:** one Railway app plus one PostgreSQL 18 service each, with
    modules embedded by git subtree. The only deployed one is `bap-web` (v0.62.0). Its
    replacement `bap-web-new` (generated 2026-10-09 against a pre-publication 0.89.0, last
    commit 2026-10-10) is waiting for the 0.89.0 publication, the repin, and the cutover
    (SA191). It was read directly, read-only.
- **Configuration axes:** unchanged. They are the 12-module selection, the per-module
  `QUICKSCALE_<MODULE>_ENABLED` flag, orgs `solo`/`saas`, storage `local`/`s3`/`r2`, and local
  Docker versus Railway. CI exercises module suites under the restricted role, one generated
  e2e lane, and the offline generated-automation gate.
- **Team:** one contributor working through three agent-driven worktree tracks with a
  serialized merge queue. The three-day delta has 59 non-merge commits and 44 merges.
- **Data and obligations:** unchanged (accounts, emails, CRM contacts, form submissions,
  Stripe identifiers, PostHog analytics; a user-facing deletion promise; no declared
  regulatory regime).
- **Cost:** flat Railway bill by decision. The dominant unit cost is maintainer and agent time.
- **Growth direction** ([roadmap](../technical/roadmap.md)):
  1. Publish 0.89.0 (a maintainer action; no open ticket blocks it).
  2. SA191's repin and cutover of `bap-web-new`.
  3. SA204 (g), the one-way step: the decision record lifting clean-break rule 1, plus the
     manifest freeze commit. It is the only Track 1 item with no unmet dependency.
  4. SA153's property portal, whose schema work is `0002+` from the start.
- **Stated-versus-actual gaps:**
  - **Decision versus gate (new):** `decisions.md:2112–2117` still says "Do not add `0002_*`
    history". The registered `check-migration-freeze` gate and the topology test already
    accept an ordered `0002+` chain (`518cc377`). The two artifacts disagree until SA204 (g)
    lands.
  - Carried: core loads storage by name; core holds social's manifest module; the "independent
    CLI cadence" coexists with lockstep; the theme upgrade tool is not shipped.
  - Resolved since the prior pass: the bundled manifests are now a build-time derivation, not
    a tracked copy (SA280 (b)). At startup in R2, core still reads its bundled snapshot rather
    than the embedded `module.yml` (`contracts/resolvers.py:34–48`); under lockstep the two are
    the same bytes by construction.
- **Scope:** the whole monorepo. Depth went to the fix-regression audit of SA204 (a–f), SA275,
  SA276, SA278, SA279, SA280, SA281, and SA282, and to the `bap-web-new` adoption state.

**Declared architecture** (changes since the prior pass are marked):
1. `decisions.md` wins every conflict and is updated first.
2. A module is a standard Django app plus one wiring block in its own `module.yml`. Core and
   the CLI hold no per-module wiring and no module-name branches outside rule 37's reasoned
   exceptions.
3. Modules sit on layers 0–3. Imports and name references go one way only, and core imports no
   module (rules 5 and 34).
4. Themes are generated once and are user-owned, except for the managed seam files. **Changed
   (SA276):** `quickscaleSeam.d.ts` and `quickscaleSeam.keys.ts` are now managed and
   hash-tracked.
5. Plan/apply: desired state in `quickscale.yml`, applied state in `.quickscale/state.yml`,
   with atomic writes under an advisory lock.
6. Fail hard. Templates render under `StrictUndefined`.
7. PostgreSQL only. Tenant isolation is FORCE RLS under a `NOSUPERUSER NOBYPASSRLS` runtime
   role, with an always-on boot guard.
8. Clean-break migrations: one `0001_initial` per model-bearing module, upgrades to a fresh
   database. **Contradicted in code since `518cc377`:** the freeze gate permits `0002+`, and
   rule 1 has not yet been lifted (SA204 (g)).
9. Lockstep versions. Embeds use the identity-derived immutable split tag.
10. Every Module Conventions rule is enforced by a conformance test (rule 40). Every gate runs in
    every required context.
11. No DI containers or service registries. Cross-module needs use `AppConfig` capabilities from
    the closed `CAPABILITIES` vocabulary.
12. Fixed quality lines (no file of 800 lines or more, CC below 21). **Changed (SA278 (b)):** they
    now cover non-test `scripts/` too (`check_quality.sh:156–167`).
13. **New (SA282):** every module manifest's `contract_vintage` carries a required
    `sa<NNN>-<slug>` id. Adoption is satisfied by the recorded id alone; there is one adoption
    mechanism.

**Measurements.**
- **Filter:** non-merge commits only. Synthetic subtree-split commits and bulk commits (more than
  30 files) are dropped. The changelog, roadmap, audits, `VERSION`, release notes, and lockfiles
  are excluded from churn. Line counts are over tracked files at each revision.
- **Window:** the delta `451b3dbf..30b0b6b1` (2026-10-13 → 2026-10-16). The 12-month baseline was
  not recomputed.

| Measure | Prior pass (`451b3dbf`) | This pass (`30b0b6b1`) |
|---|---|---|
| Commits touching package `src/` | 35 of 98 (36%) | **26 of 59 (44%)** |
| `scripts/` non-test lines | 40.1k | 43.8k (+3.7k) |
| `scripts/` test lines | 46.6k | 48.7k (+2.1k) |
| `scripts/` tracked files | 181 | 234 |
| Module source (non-test, non-migration) | 40.8k | 41.3k (+0.5k) |
| `0001_initial` rewrites in the delta | 13 in 5 days | **2** (billing SA270, blog SA204 (a)), **both before the freeze gate; 0 since `518cc377`** |
| `project_contract.yml` steps | 40 | **46** (+6 in 3 days) |
| Pending adoption steps on `bap-web-new` | 6 | **12** |
| Gates in `gate_registry.json` | 21 | 21 (+`check-migration-freeze`, −`check-manifest-sync`) |
| Hand stations to add one gate | ≈8 | **1 authored row + 1 count pin** (4 test oracles before SA285 (a), measured on `518cc377`) |
| `FROZEN_*` name lists in parity tests | 1,381 literals in 11 files | **0** (guarded by `test_no_frozen_surface.py`) |
| `test_*parity*.py` files | 21 | 34 (the 13 SA267/SA268 additions keep behavioral corpora only) |
| Adapter dataflow detector | 1.1k lines plus controls | **deleted** (SA281 (b)); hooks receive typed resolved options |
| `CAPABILITIES` entries | 11 | 12 (`organization_cache_invalidation_hooks`, SA283 (b)) |
| Stripe API version authored stations | 5 | 1 (SA280 (a)) |

**Commit-delta classification** (59 non-merge commits):
- **Closeout (mapped and verified):** SA204 (a–f), SA267 (a–e), SA268 (d) and its sub-slices,
  SA269, SA270, SA271 (a–b), SA272 (a–c), SA273, SA274, SA275 (a–b), SA276 (a–b), SA278 (a–b),
  SA279, SA280 (a–b), SA281 (a–b), SA282 (a–b), SA283 (a–c).
- **Housekeeping:** `49edb504` (the prior audit), `34d2a9f0` (tech and coherence audits),
  `77fea4d4` (roadmap clean pass), `4f0a80ce`, `a7f3172a`, `cab32d8a`, `726fcb7e`, and
  `126dc0cb` (roadmap and slice records). None touches product source.
- **Unlabeled-behavioral, read at full depth:**
  - `0fdf2b44` ("enhance gate-parity plan checks with load-tolerant timeout"): it changes a
    timeout in the gate-parity plan check only. No product semantics.
  - `30228aa4` ("SA271 test fix"): it stops a DR test mock leaking a fabricated `storages`
    package. Test-only.
  - `b9dff3da` ("fix the two gate failures"): the pre-commit vintage hook keeps selecting the
    bundled-manifest path, and a test pin drops from 24 to 23. No product semantics.
  - `340cde24` ("restore the manifests package marker"): a tracked `__init__.py` deleted by a
    probe cleanup in the previous commit is restored. **It is evidence for Finding 3:** the
    SA280 (b) derivation needed four follow-up commits.

  No load-bearing semantics change was found under a housekeeping label.

**Coverage and residual risk.**
- **Read in full:**
  - the prior audit, the roadmap's SA204 and SA191 entries, and `decisions.md` § Clean-Break
    Migration History;
  - `check_migration_freeze.py`'s contract, `sync_migration_hashes.py`'s modes,
    `recovery.py`'s migration-content functions, and `_module_update.py`'s SA204 (e) branch;
  - `project_state_hashes.py`'s managed sets, the six new `project_contract.yml` steps, and
    `useModules.ts`;
  - `check_quality.sh`'s discovery, `test_no_frozen_surface.py`, and the stat lists of
    `518cc377`, `7a254c4f`, `c998244f`, and `aa9fff24`;
  - `publish.yml`'s build job, and `bap-web-new/.quickscale/state.yml`.
- **Sampled:** the SA275 generated regions; the SA276 managed seam; the parity files' residual
  private-name lists; and `contracts/resolvers.py`.
- **Skipped:** DR internals beyond migration identity; the internals of notifications,
  analytics, and social; beta-migration internals; theme pages beyond seam consumption. SA226
  role authorization and SA229 write effects are again not audited at depth (the fourth pass to
  skip them).
- **Lens activation:** `active: I, II, III, IV, V, VII, IX, XII, XIII, XV, XVI, XVIII, XIX, XX ·
  sampled: VI, VIII, X, XI · inert: XIV (no volume threshold in sight), XVII (flat Railway bill)
  · archetypes: code generator, CLI, library (runtime facade), multi-tenant output, monorepo`.
- **Lenses that produced findings:** I, V, VII, IX, XIII, XV, XIX, and the §6 generator lens.
- **Unverified out-of-repo architecture:** Railway service settings, GitHub tag and branch
  protection, PyPI state, Stripe endpoint versions, PostHog-side deletion, and the old `bap-web`
  repository.
- **Claims needing runtime confirmation:**
  - That a bare `poetry build` of `quickscale_core` without the materializer yields a wheel with
    no bundled manifests rather than an error (Finding 3). The source and `5dd2b2a6`'s message
    support this; it was not executed.
  - That PostgreSQL FK checks bypass RLS. Carried; not executed.
- **Open lead:** cross-organization references through M2M tag tables (`Contact.tags`,
  `Deal.tags`, `Post.tags`) are still not censused. This is the third pass to carry it.
- **Do not read silence as clearance** for DR internals, role authorization, write effects, or
  theme pages.

---

## 2. Enforcement census

| Invariant | Where enforced | Kind | Gate world | Trend since `451b3dbf` |
|---|---|---|---|---|
| Tenant rows isolated by organization | FORCE RLS two-policy contract; restricted role; boot guard (`orgs/checks.py:147`, `check_rls_role`); transaction-scoped `SET LOCAL` priming | **structural** | — | unchanged |
| Tenant-to-tenant references stay in one org | composite `(fk, organization_id)` FKs derived by `quickscale_orgs.W007` | **structural** (gated) | closed over model metadata | unchanged |
| API authentication by default | `IsAuthenticated` default (`runtime/settings.py:153`); closed `REST_FRAMEWORK` admission | **structural** | — | unchanged |
| Per-view guard declared | rule 19 detector | gated | closed over detected views | unchanged |
| Org-role authorization | `user_has_org_role`; rule 44 spelling detector | structural helper + gated use | open-world | SA282 (a): one organization-selector spelling |
| One owner per URL prefix | `collect_wiring` refusal (`module_wiring.py:133`) | **structural** | — | unchanged |
| Option validation, defaults, secret projection | manifest engine; hooks receive **typed resolved options** (SA281) | **structural** | — | **strengthened**: the 1.1k-line dataflow detector is deleted |
| Capability names | closed `CAPABILITIES` (`runtime/conventions.py`) | **structural** | — | 11 → 12 names |
| Declared removal and anonymize obligations | one coordinator (`auth/_anonymize_boundary.py:95–99`) | **structural** | — | SA283 (b): the purge collects declared cache-invalidation hooks |
| Core and CLI hold no module names | rule 37 detector plus reasoned exceptions | gated | open by exception list | decision text unchanged; list not recounted |
| Privileged DB command set | four literal declarations; `test_privileged_command_contract.py` | gated | closed (equality) | unchanged |
| Stripe API version | one authored constant (`billing/_settings.py`), rendered into the manifest and the operations guide | **structural** | — | **5 stations → 1** (SA280 (a)) |
| Shipped migrations immutable | `check-migration-freeze` against `scripts/migration_hashes.json`, append-only against the latest release tag | **gated** | closed over recorded files and released values | **new** (SA204 (c), (h)); was "none" |
| Schema identity a backup restores against | per-module migration hashes recorded with every backup; `recovery.py:231–275` refuses changed, missing, or unrecorded identity, including the bare file | **structural** | — | **new** (SA204 (d)); was label-keyed |
| Schema identity across `quickscale update` | content compared **only when the version label is equal** (`_module_update.py:286–297`, `:365`) | **convention** across a label change | — | **partly new** (SA204 (e)) |
| Generated-project contract adoption | recorded adoption id (`contract_vintage.py:38`, `--confirm-contract-adoption`) | **convention** (honor system) | — | one mechanism (SA282); **40 → 46 steps** |
| Theme seam types and keys | managed, hash-tracked `quickscaleSeam.d.ts` / `.keys.ts` (`project_state_hashes.py:47–50`) | **structural** | — | **new** (SA276) |
| Vendored module source unmodified | extension contract prose only | **convention** | — | unchanged |
| Gate present in every required context | registry-generated regions, `gates.mk`, local arms (`check_ci_locally.sh:456–542`), and Makefile help | **structural** (generated) | — | **strengthened** (SA275, SA285 (a)); the four oracles derive the inventory, one hand count pin remains |
| Bundled manifests ship in the core wheel | `sync_module_manifests.py` run by each build entrypoint (7 call sites, plus 3 conftests) | **convention** per entrypoint | — | **new** (SA280 (b)); replaces a tracked copy held by parity |
| Quality thresholds | `check_quality.sh`, package `src/` plus non-test `scripts/` | gated | closed per metric | **scope extended** (SA278 (b)) |

Findings concentrate on the three **convention** rows that grew or were minted this pass: update
across a label change, adoption, and the build-entrypoint materializer.

---

## 3. Summary table

| Rank | ID | Title | Horizon | Confidence | Size | Reversibility | Problem |
|---|---|---|---|---|---|---|---|
| 1 | `generated-file-ownership-unmodeled` | Module-facing contracts live in user-owned generated files | now | High | M | two-way door | Seam types are now managed, but theme pages, CI workflow, and docs still carry module contracts; steps 40 → 46 in 3 days, 12 pending on `bap-web-new` |
| 2 | `clean-break-schema-no-data-path` | Module schemas have no verified data upgrade path | now | High | S | one-way door | The freeze and append-only content identity landed; `update` checks content only under an equal label until `MIGRATION_FREEZE_VINTAGE` is set, and rule 1 still forbids `0002` |
| 3 | `rules-held-by-parity-not-derivation` | Rules are kept as hand-synced copies | 6–18 months | High | S | two-way door | Most copies are derived or deleted; the residual is a materializer every build entrypoint must remember, with one hand count pin in the gate oracles |

---

## 4. Machine-readable index

```yaml
schema: arch-audit/v9
audited: 30b0b6b1bf5412cffe1cae9fc0d6020c288b485c
items:
  - {id: generated-file-ownership-unmodeled, status: open, rank: 1,
     title: "Module-facing contracts live in user-owned generated files", lenses: [V, VII, IX, XV, XIX, "§6 generator"],
     horizon: now, confidence: High, size: M, reversibility: two-way door,
     depends_on: [], amplifies: [clean-break-schema-no-data-path],
     anchors: [quickscale_core/src/quickscale_core/data/project_contract.yml, quickscale_core/src/quickscale_core/project_state_hashes.py,
               quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/src/pages,
               quickscale_cli/src/quickscale_cli/commands/contract_vintage.py, quickscale_devtools/src/quickscale_devtools/beta_migration],
     first_seen: 2026-09-16, last_verified: 2026-10-16}
  - {id: clean-break-schema-no-data-path, status: open, rank: 2,
     title: "Module schemas have no verified data upgrade path", lenses: [I, IX, XIX, XVI],
     horizon: now, confidence: High, size: S, reversibility: one-way door,
     depends_on: [], amplifies: [generated-file-ownership-unmodeled],
     anchors: [docs/technical/decisions.md, quickscale_cli/src/quickscale_cli/commands/_module_update.py,
               scripts/check_migration_freeze.py, scripts/sync_migration_hashes.py, scripts/migration_hashes.json,
               quickscale_core/src/quickscale_core/dr_engine/recovery.py],
     first_seen: 2026-09-23, last_verified: 2026-10-16}
  - {id: rules-held-by-parity-not-derivation, status: open, rank: 3,
     title: "Rules are kept as hand-synced copies", lenses: [XV, XIII, XX],
     horizon: 6–18 months, confidence: High, size: S, reversibility: two-way door,
     depends_on: [], amplifies: [],
     anchors: [scripts/gate_registry.json, scripts/test_ci_coverage_policy.py, scripts/test_ci_local_parallel.py,
               scripts/test_gate_parity.py, scripts/test_refresh_action_pins.py, scripts/sync_module_manifests.py,
               .github/workflows/publish.yml, quickscale_core/pyproject.toml],
     first_seen: 2026-10-08, last_verified: 2026-10-16}
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

### Finding 1: Module-facing contracts live in user-owned generated files

- **ID:** `generated-file-ownership-unmodeled`. Still open (regressed 2026-10-08, partly fixed
  2026-10-10 and 2026-10-15).
- **Fix-regression audit:**
  - **SA276 (managed theme seam):**
    1. **Mechanism:** removed for the seam's types and keys. `quickscaleSeam.d.ts` and
       `quickscaleSeam.keys.ts` render from the shipped module set and are hash-tracked
       (`project_state_hashes.py:44–50`). `useModules.ts:1–5` imports the type tables instead
       of declaring them. The validator reads the key manifest, and the owner slug comes from
       the producer instead of being parsed from a crm path. This is the prior pass's option 2,
       landed.
    2. **Sound decisions:** preserved; it extends the SA206/SA258 managed pattern.
    3. **New commitment:** none structural. As before, it minted adoption steps: three of them
       (`sa276-managed-seam-types`, `sa276-theme-seam-consumers`, and
       `sa276-seam-manifest-rendering`). The last is a fix of the fix: the template's whitespace
       diverged from the runtime renderer (`069fe0e7`).
  - **SA282 (one adoption mechanism):** the CLI's mechanism selection is gone, and every vintage
    carries a required id. This is simpler, but adoption is still recorded on the operator's
    word (`contract_vintage.py:38`). The convention row is unchanged.

  **Verdict:** the seam half is resolved. The finding stays open because module contracts keep
  arriving in user-owned files outside the seam, and the step rate did not fall.
- **Rank rationale:** High blast radius, High likelihood, steep compounding.
  - **Blast radius:** security and correctness fixes reach projects as hand-applied steps.
  - **Likelihood:** already firing. `bap-web-new` has 12 pending steps (6 at the prior pass)
    and has not been touched since 2026-10-10.
  - **Compounding:** 30 → 40 → 46 steps over eight days.
  - **Ranked first** now that Finding 2's compounding mechanism is gated.
- **Horizon & trigger:** `now`. The trigger is SA191's repin of `bap-web-new` to the published
  0.89.0.
- **Confidence:** High. The steps, the managed set, and the pending list were all read or
  computed.
- **Context dependence:** `wrong-for-now`. The dimension is the number of long-lived generated
  projects. It lives in R2.
- **Problem:** The seam between shipped modules and a generated project is managed only for four
  files (`settings/modules.py`, `urls_modules.py`, and the two theme seam files). Module
  contracts still land in user-owned emitted files, so every such contract change becomes a
  hand-applied prose step per project. The user-owned files involved are theme pages, the
  generated CI workflow, and the operations guide.
- **Evidence** (re-verified this pass unless marked new):
  - The managed sets are `project_state_hashes.py:38–50`: two wiring paths and two seam paths
    (new).
  - **The six steps added in the delta** (new), by where the contract landed:
    - `sa272-generated-ci-notifications-secret`: a module's startup check now refuses a
      placeholder that the **user-owned** `.github/workflows/ci.yml` carries.
    - `sa274-crm-theme-stats`: a theme page (`CrmPage.tsx`, **user-owned**) consumes a new crm
      endpoint. The step also requires the embedded crm to update in the same move.
    - `sa276-*` ×3: the price of the SA276 fix itself.
    - `sa280-operations-stripe-version`: the **user-owned** `OPERATIONS.md` renders a module
      constant.
  - **`bap-web-new` pending steps** (new, out of repo, read-only): the 12 are `sa253-frontend-coverage`,
    `sa253-generated-automation`, `sa258-managed-urlconf`, `sa261-seam-module-api-paths`,
    `sa261-theme-seam-test-fixtures`, `sa262-social-resolution-marker`, `sa272-…`, `sa274-…`,
    `sa276-…` ×3, and `sa280-…`. Two non-`sa` ids are also unrecorded under that spelling.
  - Three upgrade mechanisms are still maintained: prose steps; `quickscale_devtools/beta_migration`
    (12.5k lines); and SA191's prompt-driven port. `check_project_contract_vintage.py` shrank
    from 1,351 to 763 lines.
- **Counter-evidence:**
  - SA276 is a real structural fix, and it removes the theme-type half the prior pass named.
  - Searched for a managed category beyond the four files: none.
  - Searched for automated adoption: none. `apply --confirm-contract-adoption` regenerates
    managed files and records ids; it does not adopt page, workflow, or doc changes.
  - Searched for a decision retiring `beta_migration` or the port: none.
- **Why it compounds:**
  - **Growth variable:** module contract changes that touch an emitted non-managed file, times
    long-lived projects. The rate is about two steps a day during active development.
  - **What drives it:** feature work (SA274), operational hardening (SA272), and the finding's
    own fixes (SA276). Every kind of change pays it.
  - **Built on top:** the vintage gate and CLI refusal, the beta-migration taxonomy and smoke
    gate, the seam validator, and `bap-web-new`'s adoption record.
- **Detection signal:**
  - Steps per release (46 at 0.89.0).
  - Pending steps on `bap-web-new` at repin.
  - Confirmations with no matching file diff.
  - A crm stats card showing no total after a partial adoption.
- **Steelman:** "Full ownership, no lock-in" is the product promise. Pages, CI, and docs are
  exactly what users customize, and managing them would take that away. `bap-web-new` is the only
  long-lived project, and the maintainer applies its steps cheaply. Do not fix if generated
  projects are one-shot.
- **Correct shape:** Every emitted file is either QuickScale-managed (regenerated, never
  hand-edited) or user-owned with no module contract. Module-facing contracts reach a project only
  through managed files or the versioned runtime library.
- **Do-nothing cost:** about 2 steps a day of active development, each applied by hand per
  long-lived project. Three upgrade mechanisms keep being maintained. Every step landed after
  SA191's cutover is applied on a live site.
- **Options:**
  1. ~~**Path-enumerated adoption gate**~~: superseded (SA207/SA211).
  2. **Extend the managed pattern.** ~~Django side~~ (SA258, SA261), ~~theme seam types~~
     (SA276). **Remaining:** route module-coupled page data through seam-declared hooks that live
     in managed files, so pages consume hooks, not endpoints. Render module-owned CI environment
     values and operations text into managed include files that the user-owned files reference
     once. Effort M. **Live option.**
  3. **Accept and document** that projects are one-shot: retire `beta_migration` and the vintage
     machinery. Revocation trigger: a second long-lived project, or a security fix in a template.
  4. **Choose one upgrade mechanism.** Keep either `beta_migration` or the prompt-driven port and
     retire the other. Effort S. This is independent of options 2 and 3.
- **Recommendation:** option 4 now (S), then option 2 for the CI-environment and operations-guide
  cases (they are mechanical), and theme page hooks as SA153 adds pages.
  - **Size:** M.
  - **Reversibility:** `two-way door`.
  - **Guard:** extend the closed-world emission test so that no user-owned emitted file names a
    module setting, endpoint, or constant except through a managed include. Track steps per
    release; the number should trend toward zero.
  - **First step:** move the module-owned CI environment block into a managed file that the
    generated `ci.yml` includes once.

### Finding 2: Module schemas have no verified data upgrade path

- **ID:** `clean-break-schema-no-data-path`. Still open; **most of the mechanism removed**.
- **Fix-regression audit of SA204 (a–f):**
  1. **Mechanism:** largely removed.
     - (a) Frozen history names only public symbols: `BlogMediaAssetImageField`.
     - (b, c) A content-hash manifest and a registered freeze gate: an in-place edit or a
       deletion of a recorded migration fails, and a new `0002` passes
       (`check_migration_freeze.py:13–29`).
     - (d) Restore keys on recorded migration hashes, forward-capable, and the bare-file
       fail-open is closed (`recovery.py:244–245`: "backup records no migration content
       identity").
     - (e) `update` refuses a same-label rewrite.
     - (f) The rehearsal proved that the frozen `0001` reproduces the FORCE-RLS baseline (6
       tables, 12 policies).

     Rewrites dropped from 13 in five days to **0 since the gate**.
  2. **Sound decisions:** preserved. Each tenant `0001` still installs its own RLS, and the DR
     fail direction is now closed on every path read.
  3. **New commitment:** none minted. **One branch still keys on labels or authorship** (the
     other closed by SA204 (h)):
     - **`update` checks content only under an equal label.**
       `_module_update.py:286–289`: "A label change is … fresh-database path, so only an equal
       label compares content". `:365`: `if installed_version == applied_version:`. After
       SA204 (g) lifts rule 1, the *cross-release* update is exactly the upgrade the freeze
       exists to make safe, and it is the one path that does not compare the applied migration
       files with the pulled ones. SA204 (g) landed the vintage-keyed guard
       (`MIGRATION_FREEZE_VINTAGE`, still unset): the branch flips when SA204 (j) sets it.
     - **The manifest re-freezes on demand.** `sync_migration_hashes.py --write` regenerates
       every recorded hash from disk. An edited `0001` plus `--write` in one commit passes
       `check-migration-freeze`. The gate catches drift, not intent. Immutability then rests on
       review noticing a changed line in `migration_hashes.json`. *(Closed by SA204 (h): the
       gate compares the checked-in manifest with `scripts/migration_hashes.json` at the latest
       release tag, refuses a changed or removed released value even after `--write`, excludes
       the release being tagged, and fetches the one baseline tag in a shallow clone.)*
- **Rank rationale:** High blast radius, High likelihood, linear compounding (down from steep).
  - **Blast radius:** data in the first non-reseedable database.
  - **Likelihood:** SA204 (g) is next, and SA153 follows.
  - **Compounding:** every release after (g) adds applied migration files that the
    cross-release update path does not verify.
- **Horizon & trigger:** `now`. The trigger is SA204 (g) landing without the update branch
  changed, or SA153's go-live.
- **Confidence:** High. Both branches were read, and the gate and generator modes were read.
- **Context dependence:** `wrong-for-now`. The dimension is the first deployed database that
  cannot be reseeded. It lives in R2.
- **Problem:** The freeze makes shipped migrations immutable in the repository and makes restore
  content-keyed, but the project upgrade path (`quickscale update`) still trusts the version
  label across releases. The declared rule still forbids the `0002` that SA153 needs. The
  freeze's content identity therefore does not yet guard the move it was built for.
- **Evidence:**
  - `decisions.md:2112–2117`: "Do not add `0002_*` history" (still in force). The gate and the
    topology test accept `0002+` since `518cc377`. This is a governance conflict (lens IX/XV)
    until (g).
  - `_module_update.py:286–297`, `:362–375`: the equal-label branch, quoted above.
  - `sync_migration_hashes.py:18–25`: `--write` "regenerate[s] the checked-in manifest from the
    shipped modules".
  - `check_migration_freeze.py:17–18`: "a numbered migration present on disk but not yet
    recorded is a legal forward addition; the next manifest regeneration freezes it".
  - Roadmap SA204 (g): "the decision record lifting rule 1 and the freeze commit of the
    manifest… kept to docs and the manifest".
- **Counter-evidence:**
  - DR restore is content-keyed regardless of label (`recovery.py:231–275`, `:356–363`), so
    backups are protected.
  - Published split tags are immutable (`utils/git_naming.py`), so a released `0001` cannot
    change under a consumer *within* a version.
  - Searched for a cross-label content check in `update`, the `apply` path, or a startup check:
    none.
  - Searched for an append-only check on `migration_hashes.json` (for example, against the merge
    base): none. The gate deliberately needs no Git history (`check_migration_freeze.py:11`).
    *(SA204 (h) added the append-only comparison against the release baseline; see §16.)*
- **Why it compounds:**
  - **Growth variable:** releases × applied migration files on deployed databases.
  - **The mechanism:** each post-freeze release that a project updates to crosses a label
    change, and none of those crossings is content-checked. One re-frozen edit reaches every
    project silently.
  - **Built on top:** the SA191 cutover, SA153's `0002+` schema work, and the DR
    restore-forward contract.
- **Detection signal:** `InconsistentMigrationHistory` or a missing-column `ProgrammingError` on
  `migrate` after an update. A diff in `migration_hashes.json` that changes an existing value
  rather than adding a key. Instrument the second: today nothing flags it. *(SA204 (h) flags it:
  a changed recorded value fails the freeze gate; see §16.)*
- **Steelman:** Before (g), every label change *is* a fresh-database upgrade by decision, so
  checking content across labels would refuse the only supported path. The `--write` escape is
  how the maintainer intentionally freezes new files, and on a single-maintainer repository a
  changed hash value is visible in review. Do not fix before (g). After (g), the steelman no
  longer holds.
- **Correct shape:** After the freeze, every check that decides whether a database fits the
  installed code compares migration content identity, **regardless of label**. A recorded
  migration hash can only be added, never changed or removed, and an automated check holds that.
- **Do-nothing cost:** the first post-freeze release that re-freezes an edited migration, or any
  vendored edit, upgrades `bap-web` without a refusal and diverges its schema from its migration
  record. The fix then needs a hand-written repair on a live database.
- **Options:**
  1. **Finish (g) with two small code edits:**
     - In `update`, compare the applied identity on every pull. An applied file must stay
       byte-identical, and new files apply forward. Keep only the pre-freeze vintages on the
       fresh-database path, keyed on the freeze vintage rather than "any label change".
     - Make the manifest append-only: the gate compares recorded values with the merge-base or
       published copy, or a released-vintage manifest ships in the wheel.

     Effort S. **Live option.**
  2. **Accept the equal-label scope** and document cross-release update as review-guarded.
     Containment: the DR content check plus the freeze gate. Revocation: the first post-freeze
     release.
- **Recommendation:** option 1, inside SA204 (g), which then stops being "docs and the
  manifest only". It is still the one-way step; this only widens what it verifies.
  - **Size:** S.
  - **Reversibility:** `one-way door` (lifting rule 1). Before it closes, re-run the (f)
    rehearsal with the cross-release update path on a copy.
  - **Guard:** an `update` test in which a label change plus a changed applied file is refused;
    a freeze-gate control in which a changed recorded hash value fails.
  - **First step:** change the `:365` condition to "the applied version is at or after the
    freeze vintage".

### Finding 3: Rules are kept as hand-synced copies

- **ID:** `rules-held-by-parity-not-derivation`. Still open; **most of the mechanism removed,
  with one small relocation**.
- **Fix-regression audit:**
  - **SA275 (a, b): gate wiring.**
    1. **Mechanism:** removed. Gate order and the hosted, publish, and help metadata are
       registry fields, the order tuples and copy-equality refusals are deleted
       (`HOSTED_GATE_ORDER`: 0 occurrences), and the local arms (`check_ci_locally.sh:456–542`)
       and the Makefile help are generated.
    2. **Sound decisions:** preserved.
    3. **Relocation:** measured on `518cc377` (the first gate added after SA275). The authored
       station is one registry row, but four test files restate the gate inventory by hand:
       - `test_ci_coverage_policy.py` (the id);
       - `test_ci_local_parallel.py` (the banner);
       - `test_gate_parity.py` (the `needs:` list literal, three times, plus a publish order
         number);
       - `test_refresh_action_pins.py` (a checkout count, 23 → 24 → 23 across the delta).

       The copies moved from generator to test oracle: one authored station plus four held
       ones, down from about eight.
  - **SA278 and SA279 (frozen surfaces):** removed. No `FROZEN_*` list remains, guarded by
    `test_no_frozen_surface.py`, which is open-world: it bans the `FROZEN_` prefix only. Residual
    private-name literals are 6–11 per file, as sibling-structure invariants. This is resolved
    for this finding.
  - **SA281 (typed resolved options):** removed by construction. The dataflow detector is
    deleted. This is the prior pass's option 2.
  - **SA280 (a) (Stripe version):** removed: 5 stations become 1 authored constant.
  - **SA280 (b) (bundled manifests):** the tracked copy and `check-manifest-sync` are gone, but the
    change **minted a new hand-synced station list**:
    - **Seven build entrypoints** must each run `sync_module_manifests.py` before
      `poetry build`: three Makefile targets, `publish.yml:249`, `publish.sh:322`,
      `_installed_wheel_venv.sh:679`, and `install_global.sh:285`. **Three conftests** must also
      run it.
    - The derivation already needed four follow-up commits: `5dd2b2a6` (Poetry silently dropped
      the gitignored manifests from every Git-aware wheel), `340cde24`, `cee5b995` (the user
      manual still showed a bare `poetry build`), and `b9dff3da`.
    - **The artifact actually uploaded to PyPI was not content-checked.** `publish.yml:295`
      builds, and `:330` publishes; `smoke-install` (`:185`) runs in another job against its own
      build. *(Closed by SA284: the build job runs `scripts/check_core_wheel_manifests.py`
      between the build loop and the upload and fails unless the wheel's bundled manifests are
      byte-equal to `quickscale_modules/*/module.yml`.)*
  - **SA285 (a) (gate test oracles):** removed. The four oracles
    (`test_ci_coverage_policy.py`, `test_ci_local_parallel.py`, `test_gate_parity.py`,
    `test_refresh_action_pins.py`) read the gate set from `gate_registry.json` and derive their
    expectations from it; the one hand pin kept on the count is `test_gate_parity.py`'s
    `EXPECTED_GATE_COUNT`.
- **Rank rationale:** Medium blast radius, Medium likelihood, linear compounding (down from
  steep).
  - **Blast radius:** delivery cost. One release-integrity edge: a core wheel without manifests
    fails at startup in every installed project.
  - **Likelihood:** each new gate and each new build path fires it, about one gate a week.
  - **Compounding:** a fixed cost per gate or entrypoint. Governance code still grew 5.8k lines
    against 0.5k of module source in the delta, but mostly from closing slices, not new copies.
- **Horizon & trigger:** `6–18 months`. The triggers are a new build entrypoint (a new install
  script, a CI lane that builds wheels), or the next gate.
- **Confidence:** High for the stations (read and measured). Medium for the unverified-wheel
  edge, which needs runtime confirmation.
- **Context dependence:** `wrong-for-now`. The dimension is team shape (one maintainer with agent
  tracks). It lives in R1, and the wheel edge reaches R2.
- **Problem:** One rule is still authored once and restated by hand: "materialize the manifests
  first" at every build entrypoint (the gate inventory in test oracles now derives from the
  registry with a single hand count pin — SA285 (a)). Its correctness is held by each copy being
  remembered, not by derivation.
- **Evidence:** as above. Measured: `git show --stat 518cc377`; `git grep sync_module_manifests`
  gives 7 non-test entrypoints and 3 conftests.
- **Counter-evidence:**
  - Searched for a Poetry build hook or a `build.py` that would make materialization structural:
    none (`quickscale_core/pyproject.toml:29–33` only declares the include).
  - Searched for a post-build wheel-content assertion on the publish artifact: none before SA284,
    which adds one (`scripts/check_core_wheel_manifests.py`, run by the build job);
    `test_bundled_manifest_wheel.py` checks a wheel it builds itself.
  - The test oracles are deliberate end-to-end assertions on generated text. Rejecting
    unexpected output is valuable, and the cost is low.
- **Why it compounds:**
  - **Growth variable:** gates (one count-pin edit each) and build entrypoints (one more caller
    to remember each).
  - **Built on top:** the 21-gate registry, three workflows, the installed-wheel provisioner,
    and the publish pipeline.
- **Detection signal:** an `ImproperlyConfigured` manifest load in a freshly installed project. A
  commit that adds a gate and re-pins the oracle count. A build entrypoint that misses the
  materializer.
- **Steelman:** One count-pin edit per gate is cheap, and the oracle set stays a deliberate
  end-to-end assertion on generated text that a fully self-derived test would miss. The
  materializer callers are few and stable, and the next release runs through `make`. Accept the
  residual if no new build entrypoint appears.
- **Correct shape:** Every rule has one authored source. Tests derive their expectations from the
  registry. The shipped artifact is verified for the derived content it must carry, at the step
  that uploads it.
- **Do-nothing cost:** one count-pin edit per gate; and a nonzero chance that a new build path
  ships a manifest-less core wheel, failing every project that installs it until a patch release.
- **Options:**
  1. **Derive and verify:**
     - Tests read the gate set from `gate_registry.json`, keeping one hand pin on the
       count. *(Landed as SA285 (a).)*
     - Add a wheel-content assertion (12 bundled manifests, byte-equal to the source) to
       `publish.yml` between `:295` and the upload.
     - Route all build entrypoints through one `make build-core` that materializes.

     Effort S. **Live option.**
  2. **Accept and document** the oracle pattern; keep only the publish-artifact assertion. Effort
     XS.
- **Recommendation:** option 1's publish-artifact assertion now, since it is release integrity
  before 0.89.0 publishes (landed as SA284). The rest goes in as gates are next touched: the
  oracle derivation landed as SA285 (a); the one core-build step remains (SA285 (b)).
  - **Size:** S.
  - **Reversibility:** `two-way door`.
  - **Guard:** the publish-job wheel assertion itself; and a test that no script under `scripts/`
    or `.github/` runs `poetry build` for `quickscale_core` outside the one target.
  - **First step:** add the post-build manifest-count and hash check to `publish.yml`'s build job
    (landed as `scripts/check_core_wheel_manifests.py`, SA284).

---

## 6. Change-cost probes

| Probe | Stations, measured | Verdict |
|---|---|---|
| **Adding one gate** (re-run; instance: `check-migration-freeze`, `518cc377`; re-checked after SA285 (a)) | Authored: the registry row. Generated: `gates.mk`, the `ci.yml` and `publish.yml` regions, the local arms, the Makefile help, and the docs table. Hand-held: one count pin | **Finding evidence** → Finding 3 (≈8 → **1 + 1** after SA285 (a); was 1 + 4 on `518cc377`) |
| **A module contract change reaching a deployed project** (re-run; instance: SA274's crm stats) | Module endpoint; user-owned `CrmPage.tsx`; a `project_contract.yml` step; the vintage gate; the operator's `--confirm-contract-adoption`; and the embedded crm must update in the same move | **Finding evidence** → Finding 1 |
| **SA153's first `0002` in a module, then `update` on `bap-web`** (new) | (1) the migration file; (2) `sync_migration_hashes.py --write`; (3) the freeze gate passes; (4) release; (5) `update` crosses a label change, so **no content comparison**; (6) `migrate` applies forward. A concurrent edit to the frozen `0001` re-frozen at step (2) also passes (3) and (5) *(measured on the re-run pass; SA204 (h) now fails step (3) when the edited value is recorded at the latest release tag, and step (5)'s cross-label content gap remains until `MIGRATION_FREEZE_VINTAGE` is set)* | **Finding evidence** → Finding 2 (authoring half closed by SA204 (h)) |
| **Repin `bap-web-new` to the published 0.89.0** (re-run) | Wheel repin; **12** pending steps; subtree pulls; fresh rebuild and reseed | **Finding evidence** → Finding 1; the rebuild contains Finding 2 at cutover |
| **SA153 gallery child table in a project app** (carried) | `TenantModel`; project migration with `apply_force_rls`; W007; classification and obligation declarations; boundary tests | **Exonerating** (§8.2) |
| **Adding a module option** (re-checked against SA281) | `module.yml` option, `validation`, and `django_setting`; the hook receives typed resolved options | **Exonerated**, now with no detector cost |

---

## 7. Fix order and interactions

- **Finding 2's update branch belongs inside SA204 (g).** That is the one-way step, and both
  edits are S. Landing (g) without them makes the first post-freeze release the first unverified
  upgrade.
- **Finding 3's publish-artifact assertion before the 0.89.0 publication.** It is independent of
  everything else.
- **Finding 1 interacts with SA191's repin.** Each step landed before the repin is applied once,
  offline. After the cutover, each one is applied on a live site.
- **Findings 1 and 2 amplify each other.** Together they make an upgrade code-by-hand plus
  data-on-trust.
- **No conflicts found.**

---

## 8. Sound load-bearing decisions (preserve through remediation)

All five were re-verified, and three were strengthened in this delta.

1. **Tenant isolation is structural and fails closed.** FORCE RLS under a restricted role; the
   always-on `check_rls_role` boot guard (`orgs/checks.py:147`); transaction-scoped `SET LOCAL`.
   The SA204 (f) rehearsal reproduced the 6-table, 12-policy baseline on frozen migrations.
2. **The module contract reaches host-project code through declarations and fail-closed
   coordinators.** Obligations, classifications, and personal-data treatments are declared on
   `AppConfig`; one anonymize coordinator; orgs' checks run in the project. SA283 (b) routes
   cache invalidation through a declared capability rather than a call list.
3. **Module boundaries are declared once.** `module.yml` options, mounts, and routes; one engine
   at plan, apply, and startup. **Strengthened:** hooks now receive typed resolved options
   (SA281), and startup checks read projected setting names from the manifest (SA283 (a)).
4. **The runtime facade extended to the seam.** Executable contracts ship as library code.
   **Strengthened:** the theme seam types are now managed (SA276).
5. **Generation and release integrity.** `StrictUndefined` (`generator.py:405`), the e2e
   lifecycle, immutable split tags, and executed generated automation. **Strengthened:** DR
   restore keys on migration content identity and refuses the bare file (SA204 (d)).

---

## 9. Accepted commitments

- **`lockstep-release-unit`.** Module versions equal core's; projects pin
  `>=X.Y.0,<X.(Y+1).0`. Containment: the version comparison at embed and regeneration, and
  `check-core-compat`. Revocation trigger: a runtime fix must reach a deployed project that cannot
  take the same release's other changes. **This pass: not fired** for any known project. The
  pressure is unchanged: the 0.88.0 billing fix still ships only inside 0.89.0, now with 46
  adoption steps.
- **`privileged-command-four-stations`.** `{migrate, createcachetable}` at four stations, held by
  `test_privileged_command_contract.py`. Revocation trigger: a third privileged command. **This
  pass: not fired.**
- **`single-railway-shared-fate`.** One app and one PostgreSQL per project, with DR capture and
  restore as containment. Revocation trigger: an SLA, or one tenant able to exhaust shared
  capacity. **This pass: not fired.** DR containment is stronger (content-keyed restore).

---

## 10. Watchlist

Nine items are carried. No trigger fired, and none became obsolete.

- **`core-holds-module-vocabulary`.** Core and the CLI still name modules (`social_manifest.py`,
  `module_options.py`, four module-named apply steps, the dr_engine storage loaders).
  - **Trigger:** teams is scheduled, a 13th module, a new module-named apply step, or rule 37's
    list growing.
  - **This pass: not fired.** Still 12 modules. `CAPABILITIES` grew by one name, a flat cost
    (killed as a separate candidate). Rule 37's list was not recounted; its decision text is
    unchanged.
- **`manifest-dsl-vocabulary-growth`.**
  - **Trigger:** a validation keyword added for one module.
  - **This pass: not fired.** The delta added no keyword. SA283 (a) reads existing projections.
- **`vendored-module-edits-undetected`.**
  - **Trigger:** a second project with vendored edits, or a subtree-pull conflict.
  - **This pass: not fired.** Note: SA204 (e) now detects a *same-label* change to applied
    migration files under `modules/`, which is a partial detector.
- **`session-advisory-lock-pooling`.**
  - **Trigger:** a pooler or a pooled `DATABASE_URL`.
  - **This pass: not fired.** `production.py.j2:180` still sets `conn_max_age=600`.
- **`modules-english-only`.**
  - **Trigger:** SA153 or SA154 needs a module-rendered Spanish page.
  - **This pass: not fired.**
- **`two-filesystem-lock-implementations`.**
  - **Trigger:** a third implementation.
  - **This pass: not fired.** Only `advisory_lock.py` and `dr_engine/_lock.py` match.
- **`ci-provisioning-hand-pins`.**
  - **Trigger:** a 13th module.
  - **This pass: not fired.**
- **`trigger-inputs-legacy-name`.**
  - **Trigger:** any context skipping a gate on it.
  - **This pass: not fired.** 64 references remain, used as the exact e2e allowlist (SA280 (b)
    re-homed three paths onto it).
- **`subscription-status-single-writer`.**
  - **Trigger:** a second provider or an outside writer.
  - **This pass: not fired.** No module source outside billing names `Subscription`.

---

## 11. Rejected candidates

**Killed this pass:**
- **The freeze gate's `--write` re-freeze as its own finding.** It shares Finding 2's root
  (schema identity enforced at authoring, not at upgrade). It is folded into Finding 2.
- **`CAPABILITIES` growth (11 → 12).** A one-line core edit per capability under lockstep, so
  the cost is flat and it fails gate 4.
- **`test_no_frozen_surface.py` being open-world.** It bans one prefix only, but the slices that
  produced frozen lists are closed and no new split family is scheduled. No compounding.
- **The 13 new `test_*parity*.py` files.** They keep behavioral corpora and 6–11 sibling-structure
  literals each. This is characterization testing, not rule copies.
- **SA282's embedded-copy opt-out for a missing vintage id** (`aa9fff24`). It is scoped to the
  embedded resolution source with a strictness-keyed cache, and it fails closed on the authored
  and bundled reads. It is a bounded compatibility path, not a structure.

**Carried, still killed** (the killing evidence is unchanged): the version label as its own
finding (folded into Finding 2); observability scattered; API authorization per callsite; the
local `0.89.0` pre-push tag; merge `192195e2`; blog↔listings co-change; core:dr_engine↔backups
co-change; the core/CLI split under lockstep; apply consistency; the typed Stripe adapter;
implicit outbound timeouts; TenantMiddleware path literals; two DB-connection constructors;
`imperative_inventory.py`; `check_quality.sh`'s silent fallback; core owning the personal-data
vocabulary; W006 being warning-only; SA243's thresholds; SA216's anonymized row; SA223's mounts;
the redaction and personal-data copies.

---

## 12. Questions that would change the ranking

1. How many generated projects besides `bap-web-new` will be long-lived in the next 12 months?
   More than one promotes `generated-file-ownership-unmodeled`. None demotes it to an accepted
   "projects are one-shot" commitment. (Carried, unanswered.)
2. Will SA204 (g) change `update`'s equal-label branch, or is cross-release update intended to
   stay review-guarded? The first resolves Finding 2. The second makes option 2 an accepted
   commitment. (New.)
3. How often do the convention gates catch an agent regression that needed a product fix, per
   merge? A high rate validates Finding 3's steelman. (Carried, unanswered.)

**Answered and retired:** prior question 2 ("Are the SA267/SA268 parity files permanent?").
**Answered by SA278 and SA279:** the frozen surfaces were deleted at slice close and the
behavioral corpora kept. Effect: that relocation in Finding 3 is resolved.

---

## 13. Red flags (out of scope — fix now)

- **0.88.0 on PyPI ships billing that fails every Stripe webhook and every checkout with real
  keys.** The fix is on `v89`, and 0.89.0 is still unpublished (roadmap Release status). Carried;
  still present.

---

## 14. Coherence hand-offs

- dr_engine copies the storage-absent `ModuleNotFoundError` name check across `_media.py` and
  `_sidecar.py`. (Carried; the structural part is on the watchlist.)

The prior hand-off "theme TS types enumerate the module set beside the seam producer" is resolved
by SA276: the types now come from the managed `quickscaleSeam.d.ts`.

---

## 15. Companion hand-off intake

- **From `coherence-audit.md`:** `command-flag-conventions` and `contract-vintage-identity` are
  recorded as resolved by SA282 there. No new hand-off to this audit.
- **From `tech-audit.md`:** the `project_contract.yml` hand-off was dropped there (SA282). The
  watchlist items `dr-restore-vintage-exact-match` and `initial-migration-edited-in-place` are
  served by SA204 (d), and by SA204 (c) with Finding 2's residual.

---

## 16. Reconciliation log

Append-only. One dated line per ID per pass. Placements before 2026-10-13 are in version control
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
- 2026-10-16 — `generated-file-ownership-unmodeled`: still-open, rank 2 → 1. SA276 resolved the theme-type half (fix-regression passed for it); SA282 unified adoption; steps 40 → 46; 12 pending on `bap-web-new`; contracts now arrive via user-owned pages, CI, and docs.
- 2026-10-16 — `clean-break-schema-no-data-path`: still-open, rank 1 → 2, size M → S. SA204 (a–f) removed most of the mechanism (freeze gate, content-keyed restore, bare-file closed, 0 rewrites since the gate); SA204 (g) keys the update guard on the freeze vintage, and SA204 (h) closes the `--write` re-freeze branch (the gate is append-only against the latest release tag, excludes the release being tagged, and acquires that one tag in a shallow clone); residual: `MIGRATION_FREEZE_VINTAGE` is still unset — the cross-release update compares content only under an equal label until SA204 (j) — and decision rule 1 still forbids `0002`.
- 2026-10-16 — `rules-held-by-parity-not-derivation`: still-open, horizon now → 6–18 months, size M → S. SA275, SA278, SA279, SA280 (a), SA281, and SA285 (a) removed their copies; residual relocation: seven materializer build entrypoints (minted by SA280 (b)); the gate oracles now derive with one hand count pin; the publish artifact is now content-checked (SA284).
- 2026-10-16 — `lockstep-release-unit`: accepted, carried (not fired).
- 2026-10-16 — `privileged-command-four-stations`: accepted, carried (not fired).
- 2026-10-16 — `single-railway-shared-fate`: accepted, carried (not fired; DR containment strengthened).
- 2026-10-16 — `core-holds-module-vocabulary`: carried (12 modules; `CAPABILITIES` +1, flat).
- 2026-10-16 — `manifest-dsl-vocabulary-growth`: carried (no keyword added).
- 2026-10-16 — `vendored-module-edits-undetected`: carried (SA204 (e) adds a partial same-label detector).
- 2026-10-16 — `session-advisory-lock-pooling`: carried (`conn_max_age=600`, no pooler).
- 2026-10-16 — `modules-english-only`: carried.
- 2026-10-16 — `two-filesystem-lock-implementations`: carried.
- 2026-10-16 — `ci-provisioning-hand-pins`: carried.
- 2026-10-16 — `trigger-inputs-legacy-name`: carried.
- 2026-10-16 — `subscription-status-single-writer`: carried.
- 2026-10-16 — Red flag "0.88.0 billing broken on PyPI": still-present (0.89.0 unpublished).
- 2026-10-16 — Prior question 2 (SA267/SA268 parity files permanent?): answered by SA278/SA279 (deleted at close) and retired.
- 2026-10-16 — Coherence hand-off "theme TS types enumerate modules": resolved (SA276).
- 2026-10-16 — Coherence hand-off "dr_engine ModuleNotFoundError copy": carried.
