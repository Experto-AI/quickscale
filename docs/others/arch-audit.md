# Structural Autopsy: QuickScale

Audited: `cdb6223f` (`v89`) · 2026-09-24 · working tree clean · prompt: deep-architectural-audit v8

> Live structural findings only. Findings are identified by their **slug**; ordinal numbering is
> pass-local and is not a stable identifier (see
> [decisions.md → Document Responsibilities](../technical/decisions.md)). Closed findings and
> prior-pass narratives live in [CHANGELOG.md](../../CHANGELOG.md) and version control.

## Orientation summary

QuickScale is a Python 3.14 / Poetry **code generator and scaffolding platform**. It has a Click
CLI, a Django 6 project generator, and twelve first-party modules. Modules are embedded into
generated projects by `git subtree` and upgraded by `quickscale update`. Generated projects run
PostgreSQL 18, Vite/React, Docker, and Railway. The product's public contracts are:
- the CLI;
- `quickscale.yml` and the applied state;
- the module manifests;
- the generated trees;
- upgrade semantics;
- since SA206, the `quickscale_core.runtime.settings` import path.

There are two **deployment realities**: the generator and its CI, and the generated projects
(`bap-web` and `experto-ai-web` are the deployed population). Tenant isolation in generated
projects is dual-layer: `TenantManager` plus `FORCE RLS` under a restricted runtime role. The
project has one maintainer, 3,746 commits, and 2,553 non-merge commits in 12 months. Governance is
deliberate and dense: a registered-gate universe, AST and conformance gates, and monotonic
baselines. `decisions.md` § Clean-Break Migration History (`:986ff`) declares a
**fresh-database-only** upgrade posture. Version `0.89.0` is not yet published.

**Growth direction (planning surface, authoritative).** Track 1 is
**SA191 → SA153 → SA204**:
1. SA191 rebuilds `bap-web` on current QuickScale and reseeds its data (maintainer decision,
   2026-09-23).
2. SA153 builds the first property portal on it as a project-owned extension.
3. SA204 freezes the module migration history at SA153's go-live horizon.

Track 2 is **SA207**, the single project-level contract vintage, which is next (`roadmap.md:36-61`).
**Data sensitivity:** credentials, user PII, and Stripe billing identifiers; no regulatory regime
is declared. **Cost driver:** flat Railway spend plus Stripe calls. **Out-of-repo architecture:**
Railway proxy and service configuration, the Stripe account and its webhook endpoint versions, and
the live `bap-web` database.

**Declared architecture (the system's own rules, abridged):**
- Modules depend on `quickscale_core`, never the reverse; the lockstep pin comes from `VERSION`.
- Tenant data is reached only through `TenantManager` under `FORCE RLS`, with a boot guard against
  `rolsuper`/`rolbypassrls`.
- Clean-break migrations: one `0001_initial` per module, rewritten in place, and no in-place
  database upgrades (`decisions.md:986-1000`).
- `settings/production.py` is donor-owned by policy (`decisions.md:1077`).
- Existing file dispositions do not change without authorization (`decisions.md:708`).
- Every registered gate appears in the gate registry and in CI parity.
- Generated templates render under `StrictUndefined`.

**Commit delta** `1cf67cf7..cdb6223f` has 23 commits: 12 non-merge and 11 merges. The prior
document's header names `1cf67cf7`, but its body had already been amended in place for SA205,
SA206, and SA208. This pass re-audits those three from source rather than trusting the amendments.
- **Closeout (5):** SA205 `58f58864`, SA206 `6b0aafa5`, SA208 `1744355e`, SA209 `f1627c51`, and
  SA210 `77350177`. Each maps to its roadmap ticket; the fix-regression audit is below.
- **Housekeeping (7):** docs and roadmap commits `c9915d62`, `4af38cbc`, `a823f0af`, `8d3ae50a`,
  `247a5c5c`, and `9e082e13`. Tooling commit `85d0311b` scopes `test-integration` to `MODULE` and
  preflights zizmor. Its message is accurate, and it changes no product code.
- **Unlabeled-behavioral: 0 by message, 1 by content.** SA209 appends a fourth adoption step to
  billing's `contract_vintage` without raising `minimum: "0.89.0"` (`quickscale_modules/billing/module.yml:47-50`).
  `check_contract_vintage` compares only the recorded release version with `minimum`
  (`contract_vintage.py:34-44`). So the new step is invisible to every project already recorded at
  `0.89.0`. The message says "the manifest adoption step" but not that the gate cannot surface it.
  Recorded under finding 2.

**Measurements (§3).** Filter: `--no-merges -M`, drop commits touching more than 30 files, and
exclude lockfiles, `*.md`, CHANGELOG, and test paths.
- **Churn × size (12 months).** `apply_command.py` has 65 commits × 4,001 lines. `module_commands.py`
  has 37 × 1,687. `Makefile` has 84 × 1,635. `pyproject.toml` and `module.yml` files churn with
  process, so they are discounted. `beta_migration.py` fell from 6,422 to **4,655** lines (SA206).
- **Migration-history census, recounted.** Since `bap-web` was generated (2026-03-05), all 10
  model-bearing modules' `0001_initial.py` were rewritten, 2–5 times each (auth 2, backups 2,
  billing 5, blog 4, crm 4, forms 3, listings 3, notifications 3, orgs 4, social 4). None were
  rewritten in this delta, and each module still ships a single migration file.
- **`INTENTIONALLY_UNMANAGED`** is AST-counted at **89** (`beta_migration.py:144`), unchanged
  since SA194.
- **Contract-vintage census.** 8 module manifests declare `minimum` (6 at `0.89.0`, 2 at
  `0.87.0`), plus `RAILWAY_CONTRACT_VINTAGE`. No project-level vintage exists.
- **Stripe API-version literal census.** `2026-06-24.dahlia` appears at 5 non-test stations:
  `services.py:42`, `apply_command.py:2698`, `module_config.py:1055,1066`, the billing manifest
  and its mirror (`:50`), and `OPERATIONS.md.j2:115-129`. This feeds W7.
- **Co-change and defect gravity** were carried from the 2026-09-23 pass. The window moved one
  day and 12 commits, which is below the resolution of either measurement. Ownership is
  single-author throughout.

**Coverage and residual risk.**
- **Read in full this pass:**
  - the SA205 `recovery.py` vintage path (`:209-295`);
  - `runtime/settings.py` (the header and `__all__`) and the SA206 template imports;
  - `contract_vintage.py`;
  - the SA209 manifest and CLI diffs;
  - the SA210 template diff;
  - the `85d0311b` gate diff;
  - `apply_command.py:2255-2280`;
  - the `removal.py` obligation tuple;
  - the roadmap's SA204, SA207, SA191, and SA153 entries.
- **Sampled:** billing `services.py` around the SA209 changes, the SA208 checks and purge
  command, and `base.py.j2` throttling (`:250-286`).
- **Skipped (never read at depth by any pass):** `contracts/resolvers.py`, the manifest resolver
  internals, the `dr_engine` orchestration internals, and frontend theme internals.
- **Lens activation.** Active: I, II, III, IV, V, VII, IX, XII, XIII, XV, XVI, XIX. Inert:
  - VI, X, and XIV: single-process generated apps with no scale threshold on the roadmap.
  - XVII: no metered driver beyond Stripe calls, which are bounded.
  - XVIII: no declared regulatory obligation.
  - XX: one contributor.
  - VIII is folded into XV.

  Archetypes: code generator, CLI, multi-tenant. Findings came from I, XVI, and XIX (finding 1);
  V, IX, XV, and the generator lens (finding 2); and II and III (finding 3).
- **Needs runtime confirmation:**
  - A restored `bap-web` dump against current code (finding 1).
  - A pre-SA201 project that updates billing, to confirm it gets no 429 on the 31st checkout
    (finding 2).
- **Unverifiable from here:** Railway proxy headers, the live Stripe endpoint's API version, and
  the live databases.
- **Open leads:** none.

A reader must **not** conclude from this document's silence that the resolver, the manifest
internals, or the DR orchestration are sound.

## Enforcement census

| Invariant | Where enforced | Posture | Trend since last pass |
|---|---|---|---|
| Tenant reads/writes stay organization-scoped | `TenantManager`, `FORCE RLS`, restricted-role boot guard | Structural | unchanged |
| Tenant-model universe classified, refreshed, purged | Marker-derived classification, FORCE-RLS refresh, FK-ordered purge | Structural | unchanged |
| Runtime DB role cannot bypass RLS | `rolsuper`/`rolbypassrls` boot guard; exemption narrowed to the role check (SA203) | Structural | unchanged |
| Privileged command set | Single declaration in `runtime/settings.py` (`KNOWN_PRIVILEGED_COMMANDS`) consumed by templates and the donor validator; `start.sh.j2` held equal by `test_privileged_command_contract.py` | Structural + gated | **strengthened** (SA206: the fifth station collapsed into the facade) |
| Runtime security code reaches existing projects | Facade upgradable via lockstep pin; **existing projects must hand-adopt the import, and no manifest declares that step** | Structural for new projects; convention for existing | **strengthened** (SA206); adoption owed to SA207 |
| Schema and data survive a QuickScale upgrade | Clean-break rule; restore refuses an artifact with differing or absent `module_versions` (SA205); a bare `--file` restore is **not** compared (`recovery.py:287-288`) | Convention (explicit non-support) + one refusal gate | unchanged since SA205 |
| Template ↔ upgradable-code contract compatibility | Detection keyed on the release version only; adoption is hand-copied prose; `project_contract` never advances | Detection gated at release granularity; adoption convention | **weakened**: SA209 added a step the gate cannot surface; finding 2 |
| Every emitted path has a migration disposition | Generator-derived conformance over a hand-authored taxonomy (89) | Membership gated | unchanged |
| Module credential env vars reach `.env.example` | Declaration-driven managed-block renderer + conformance | Structural + gated | unchanged |
| Org-removal obligations discharged | Central `ORGANIZATION_REMOVAL_OBLIGATIONS`; provider-ID system check over installed tenant models + purge refusal (SA208) | Inventory structural; conformance runtime | **strengthened** (SA208); finding 3 |
| Stripe webhook API version agrees with the SDK pin | `STRIPE_API_VERSION` set on the SDK; mismatched events refused (fail closed); 4 operator-facing copies of the literal | Structural at runtime; operator copies convention | **new row** (SA209); W7 |
| DRF throttling | Template defaults + module scopes merged via `setdefault` (`base.py.j2:250-286`) | Structural for fresh projects; undeclared for existing | unchanged |
| Generator template context complete | `StrictUndefined` + release-lane boot | Structural | unchanged |
| Publishing supply chain | SHA-pinned actions, minimal permissions, zizmor and secret scanning; zizmor now preflighted | Gated | unchanged (tooling ergonomics only) |
| CSRF-exempt endpoints have alternate integrity | AST gate + sanctioned bases | Structural + gated | unchanged |

## Summary table

| Rank | ID | Title | Horizon | Confidence | Size | Reversibility | Problem in one line |
|---:|---|---|---|---|---|---|---|
| 1 | `clean-break-schema-no-data-path` | Upgrades rewrite schema history with no data carry path | SA153 go-live | High / Medium | M | one-way door | Every release rewrites each module's only migration, and nothing carries a deployed project's data across it, yet SA153 brings the first tenant data that cannot be reseeded. |
| 2 | `generated-file-ownership-unmodeled` | Existing projects receive template contract changes only as hand-copied prose | now | High | M | one-way door | Code-shaped contracts now ship through the facade (SA206). Adoption for existing projects is still prose, keyed only to the release version, never advanced, and invisible when a step is added inside a release. |
| 3 | `deletion-invariants-per-boundary-reimplementation` | Org deletion obligations are declared centrally and executed per boundary | 6–18 months | High | M | two-way door | The obligation inventory lives in vendored `orgs` and names billing's fields as strings; each boundary orchestrates its own subset. |

Rank changes: none. Finding 2's blast radius drops from High to Medium, because SA206 moved the
security-critical code into the upgradable library. It stays at rank 2 because finding 3's
likelihood is lower.

## Machine-readable index

```yaml
schema: arch-audit/v8
audited: cdb6223fb8a9bf28abf2bdf5ca93031feffbe3f7
items:
  - {id: clean-break-schema-no-data-path, status: open, rank: 1,
     title: "Upgrades rewrite schema history with no data carry path",
     lenses: [I, XVI, XIX], horizon: sa153-go-live, confidence: High, size: M,
     reversibility: one-way door, depends_on: [], amplifies: [deletion-invariants-per-boundary-reimplementation],
     anchors: [docs/technical/decisions.md, quickscale_core/src/quickscale_core/dr_engine/recovery.py,
               quickscale_devtools/src/quickscale_devtools/beta_migration.py],
     first_seen: 2026-09-23, last_verified: 2026-09-24}
  - {id: generated-file-ownership-unmodeled, status: open, rank: 2,
     title: "Existing projects receive template contract changes only as hand-copied prose",
     lenses: [V, IX, XV, XIX], horizon: now, confidence: High, size: M,
     reversibility: one-way door, depends_on: [], amplifies: [],
     anchors: [quickscale_cli/src/quickscale_cli/commands/contract_vintage.py,
               quickscale_cli/src/quickscale_cli/commands/apply_command.py,
               quickscale_modules/billing/module.yml,
               quickscale_core/src/quickscale_core/runtime/settings.py],
     first_seen: 2026-09-16, last_verified: 2026-09-24}
  - {id: deletion-invariants-per-boundary-reimplementation, status: open, rank: 3,
     title: "Org deletion obligations are declared centrally and executed per boundary",
     lenses: [II, III], horizon: 6-18 months, confidence: High, size: M,
     reversibility: two-way door, depends_on: [], amplifies: [],
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/removal.py,
               quickscale_modules/auth/src/quickscale_modules_auth/views.py,
               quickscale_modules/billing/src/quickscale_modules_billing/views.py],
     first_seen: 2026-09-17, last_verified: 2026-09-24}
  - {id: W2, status: watchlist, title: "Two filesystem-lock implementations", lenses: [IX]}
  - {id: W3, status: watchlist, title: "Hand-pinned residue in CI provisioning", lenses: [XV]}
  - {id: W4, status: watchlist, title: "trigger_inputs legacy name for an exact allowlist", lenses: [XV]}
  - {id: W6, status: watchlist, title: "Billing services.py is the largest module file", lenses: [III]}
  - {id: W7, status: watchlist, title: "Stripe API version literal at five stations", lenses: [VII, XV]}
```

---

## Finding 1: Upgrades rewrite schema history with no data carry path

- **ID:** `clean-break-schema-no-data-path`
- **Rank rationale:** High × High, steep. The blast radius is a production tenant database. The
  trigger is on the roadmap (SA153's go-live). The 10-of-10 rewrite census grows with every model
  change.
- **Horizon & trigger:** SA153's go-live. The forcing event is the first QuickScale upgrade of a
  site holding tenant data that cannot be reseeded.
- **Confidence:** High on the mechanism, which was read in the decision record, the tool, and the
  restore path. Medium on the exact runtime symptom, which is inferred from Django's history
  consistency rule.
- **Context dependence:** `wrong-for-now`, keyed on production data. The finding lives in the
  generated-project reality.

**Problem:** Each model-bearing module ships exactly one `0001_initial`, rewritten in place every
release. The only upgrade path is a fresh database, and no tool carries a deployed project's data
from vintage N to N+k.

**Evidence** (anchors re-verified this pass):
- **The rule.** `decisions.md:986-1000` says QuickScale "does not support in-place database
  upgrades".
- **The rate.** The census above: 10 of 10 modules rewritten 2–5 times since 2026-03-05, and each
  still ships a single migration file.
- **The donor.** The local `bap-web` records `listings`/`forms` 0001–0003 and `auth` 0001–0002,
  and it has no `orgs`. Current `listings.0001` and `forms.0001` depend on `orgs.0001`, and
  `AbstractListing` carries a NOT NULL `organization` foreign key.
- **The tool has no data station.** `beta_migration.py` has no dump, restore, `loaddata`, or
  `django_migrations` handling.
- **Restore is contained but does not carry data.** SA205 refuses an artifact whose recorded
  `module_versions` differ from the installed modules, or that records none
  (`recovery.py:209-293`). A source with no artifact row and no carried vintage returns no issues
  (`:287-288`): "an operator-supplied file that records none has nothing to compare." That is a
  fail-open edge on the one bare-file path, recorded as a counter-evidence limit, not a new
  finding.
- **CI cannot see it.** The migration smoke gate generates both donor and recipient from the
  current tree.

**Counter-evidence:** searched `decisions.md`, the playbook, `dr_engine_migration.md`, and the
user manual for a data-carry plan (`dumpdata`, `loaddata`, export/import, "carry"): none. The
backups JSON export is documented as export-only. SA205's refusal is real containment, and the
2026-09-23 reseed decision removes SA191 from the trigger. No commit in this delta touched a
migration.

**Why it compounds:** the growth variable is **model changes × deployed projects holding data**.
Every in-place `0001` rewrite adds to the hand-written transform each deployed project needs on
its next upgrade. After SA153 that transform must also run under RLS with composite foreign keys,
and it grows with every tenant table SA153/SA154 add. Built on top: `bap-web` after SA191,
`experto-ai-web`, and every future production project.

**Detection signal:** `InconsistentMigrationHistory`, or `ProgrammingError: column …
organization_id does not exist`, during `start.sh` migrate. SA205's refusal message on restore.

**Steelman:** before 1.0, with no paying tenants, a single legible `0001` per module avoided a
long tail of data migrations and let the tenancy retrofit land without backfill code. Reseeding
`bap-web` was cheaper than a platform capability. Do not fix it while every deployed database is
reseedable.

**Correct shape:** once a project holds production data, a QuickScale upgrade has a verified,
tool-owned path from its recorded vintage to the current one, and restore refuses what the running
code cannot read.

**Do-nothing cost:** at SA153's go-live, every later module schema change becomes a hand-written
ETL under RLS for `bap-web`. The first incident is a failed production deploy.

**Options:**
1. **Freeze history at the first production vintage (SA204).** From a named release, modules ship
   `0002+` incremental migrations, and an in-place `0001` edit fails a gate. This uses Django's
   native path and removes the compounding. It is a one-way door. **Live option.**
2. **Vintage-aware logical export/import.** Keeps clean-break but **relocates** the compounding:
   every rewrite must ship a transform.
3. ~~Accept and document with restore containment~~: the containment landed (SA205), and the
   reseed decision is recorded. It is revoked at SA153's go-live.

**Recommendation:** Option 1, landed as SA204 before any post-SA153 module schema change, frozen
at the vintage SA191 lands `bap-web` on.
- **Size:** `M`.
- **Reversibility:** `one-way door`. Before closing it, prove on a restored `bap-web` copy that
  `migrate` from the frozen `0001` reproduces the parity baseline (22 FORCE-RLS tables, 44
  policies).
- **Guard:** a registered gate that fails when a released `0001_initial.py` changes.
- **First step:** decide the freeze release number now, so the SA153 schema work is written as
  `0002+` from its first commit.

---

## Finding 2: Existing projects receive template contract changes only as hand-copied prose

- **ID:** `generated-file-ownership-unmodeled` (reopened 2026-09-23)
- **Rank rationale:** Medium × High, steep. Blast radius is down from High: SA206 made the
  middleware, proxy trust, privileged-command/runtime-DB selection, and SECRET_KEY guard
  upgradable library code. The remainder is configuration-shaped contracts (throttling order,
  Vite Host enforcement, templates) and the adoption channel for existing projects. Likelihood is
  already firing: SA209 in this delta.
- **Horizon & trigger:** now. Next forcing events: SA191 carries a donor `production.py` forward,
  and any post-release project runs `update`.
- **Confidence:** High. The gate semantics were read in `contract_vintage.py`, and the manifests
  were censused.
- **Context dependence:** `wrong-for-now`. It lives in the deployed generated projects, and is
  noise for projects that are regenerated.

**Problem:** A template-side contract change reaches an existing project only through adoption
prose pasted into module manifests. The gate keys that prose to a release version, so it cannot
tell whether a project has adopted a given step, and it cannot surface a step added within a
release. `project_contract` never advances, so acknowledgement is per-invocation forever.

**Evidence** (re-verified this pass unless marked new):
- **Release-granularity detection (new).** `check_contract_vintage` flags a consumer only when
  `project_tuple < parse_version_tuple(vintage.minimum)` (`contract_vintage.py:34-44`). SA209
  appended the Stripe dahlia webhook step to billing's `manual_adoption_steps` under an unchanged
  `minimum: "0.89.0"` (`quickscale_modules/billing/module.yml:47-50`). A project recorded at
  `0.89.0` is never shown it. That step's failure mode is webhook 500s and uncredited events,
  which fails closed but costs money until someone reconciles.
- **`project_contract` never advances.** It is written only when state is created
  (`apply_command.py:2263`); existing states "preserve whatever they already have" (`:2272-2278`).
  Acknowledgement is per-invocation (`contract_vintage.py:90-96`).
- **Hand-copied prose persists.** 6 manifests are at `minimum: "0.89.0"`. The SA192 shared-design
  block is still pasted into auth, billing, listings, blog, and CRM, and
  `RAILWAY_CONTRACT_VINTAGE` (`deployment_commands.py:43`) still duplicates orgs' steps.
- **SA206's own adoption step is undeclared.** The facade docstring says "existing projects adopt
  it through a declared contract step" (`runtime/settings.py:25-26`). No manifest or constant
  mentions `quickscale_core.runtime.settings`; the roadmap assigns it to SA207
  (`roadmap.md:294-295`).
- **SA201's fail-open gap is unchanged for existing projects.** Fresh projects merge throttle
  classes by `setdefault` (`base.py.j2:250-286`). A pre-SA201 `base.py` assigns `REST_FRAMEWORK`
  wholesale with no throttle classes.
- **The template-change gate SA207 specifies is path-enumerated (new).** It covers
  `settings/*`, `start.sh.j2`, and `Dockerfile.j2` (`roadmap.md:300-301`). SA210 changed
  `pyproject.toml.j2`'s build requirement in this delta, and SA209 changed `OPERATIONS.md.j2`.
  Neither path is in that set. Both changes are benign, but they show the planned gate would be a
  hand list.

**Counter-evidence:**
- Searched for a project-level vintage: none.
- Searched for any writer advancing `project_contract`: only fresh state creation.
- Searched for a step-level identity or hash in `ContractVintage`: none (`minimum` plus a list of
  strings).
- Searched for a gate tying manifest step additions to a `minimum` bump: none.
- Real containment exists. The gate refuses before mutation, and SA206 removed the largest
  compounding source: the donor validator shrank by about 1,770 lines, and the fifth privileged
  station collapsed.

**Why it compounds:** the growth variable is **template-side or operator-side contract changes ×
existing projects**. Each change is written once for fresh projects and again as prose, and it
reaches an existing project only if the author also bumps `minimum`. Built on top:
- SA207's acceptance criteria;
- the five SA192 copies;
- the Railway duplicate;
- SA209's step;
- SA191's donor path.

**Detection signal:** `quickscale status` "behind" on a project that did every step; a module
feature that works fresh but not updated (throttling); Stripe webhook 500s after a billing update
on an already-0.89 project. To instrument: a gate that fails when a manifest's
`manual_adoption_steps` changes without a `minimum` change.

**Steelman:** a generated project's files belong to the user. Before 1.0 "regenerate and port" is
legitimate, `0.89.0` is unpublished (so no real project is recorded at it yet), and the gate is an
honest fail-closed statement. Do not fix it if regenerate-and-port is the permanent model.

**Correct shape:** every contract change an existing project must adopt has a **stable identity**
(not a release number), is declared once at the right owner (project-level, or the module that
owns it), and is shown to exactly the projects that have not recorded adopting it. Adoption is
recorded, and a step added without an identity fails a gate.

**Do-nothing cost:** after 0.89 publishes, every step added in a patch release reaches only the
projects that happen to be below its `minimum`. The acknowledgement flag becomes a permanent part
of every `update`. SA191's migrated site starts life behind.

**Options:**
1. ~~Move code-shaped contracts into the runtime library~~: **done (SA206)**.
2. **Step-identified project contract (SA207, extended).** Replace `minimum` plus prose with named
   steps (id, owner, text). Record adopted step ids in state, and show only the unadopted ones. A
   gate fails when step text changes without a new id, or when a watched template changes without
   a step. Derive the watched set from the emission manifest rather than a path list. **Live
   option.**
3. **SA207 as currently written.** A single project vintage keyed on version, and a
   path-enumerated gate. This removes the ×5 copies but keeps release granularity, which is the
   SA209 hole, and keeps a hand path list.
4. **Accept and document** under regenerate-and-port. Revocation trigger: the first published
   release after SA153.

**Recommendation:** Option 2, which means amending SA207's acceptance before it starts. It is
cheap now: SA207 has not begun, and no published project records `0.89.0`.
- **Size:** `M`.
- **Reversibility:** `one-way door` (the state schema gains adopted step ids). Verify on a copy of
  `bap-web`'s post-SA191 state before closing.
- **Guard:** the step-identity gate plus an emission-manifest-derived watch set.
- **First step:** add the step-identity requirement to SA207's acceptance, and in the meantime
  bump billing's `minimum`, or record that 0.89.0 is unpublished so the step reaches everyone at
  release.

---

## Finding 3: Organization deletion obligations are declared centrally and executed per boundary

- **ID:** `deletion-invariants-per-boundary-reimplementation`
- **Rank rationale:** High × Medium, linear. Billing and retention for real organizations are at
  stake, and both boundaries exist, but no third boundary or erasure requirement is scheduled.
- **Horizon & trigger:** 6–18 months. The trigger is a third destructive removal boundary, a
  durable-erasure requirement, or a project-owned tenant model with an external provider ID.
  **Not fired:** SA153's scope names none.
- **Confidence:** High.
- **Context dependence:** `wrong-for-now` (production tenants).

**Problem:** The obligation inventory is declared in the vendored `orgs` module, which names
billing's model labels and fields as strings. Each boundary (account deletion, org purge)
orchestrates its own subset.

**Evidence** (re-verified): `RemovalBoundary` is a two-member enum (`removal.py:12`), and
`ORGANIZATION_REMOVAL_OBLIGATIONS` begins at `:72`, with billing labels at `:79-109`.
`cancel_current_subscription` has exactly two callers (`billing/views.py:320`,
`auth/views.py:463`). SA208 runs the provider-ID walk as an orgs system check over
`get_tenant_models()` and refuses a purge while a provider-backed field holds a value.

**Counter-evidence:** billing has no `pre_delete`/`post_delete` receivers. Live-subscription
refusal precedes the purge. Account deletion records its deliberate skips. SA208's containment
holds at runtime for project-owned models.

**Why it compounds:** the growth variable is **obligations × boundaries**. Each new obligation
extends the central tuple and every boundary's handler, and each new boundary adds an enum member
and its own orchestration. SA208's project provider-ID declaration discharges only the purge
boundary.

**Detection signal:** a new deletion path that does not consume the contract; the orgs system
check failing on an unclassified `*_id`.

**Steelman:** the two boundaries have different intents, and a coordinator before real tenants
exist is premature.

**Correct shape:** each domain, project apps included, declares its own obligations where it
lives. Every boundary discharges the discovered set idempotently, and conformance runs in the
generated project.

**Do-nothing cost:** bounded until SA153 holds real organizations. After that, the first
divergence is a retention or billing incident diagnosed by hand.

**Options:**
1. **Domain-registered obligations plus a coordinator** (an `AppConfig` hook, as tenant markers
   use). **Live when the trigger fires.**
2. **Domain-local safeguards** with an outbox.
3. ~~Containment: system check over installed models~~: **done (SA208)**.

**Recommendation:** keep the containment and move to option 1 when the trigger fires.
- **Size:** `M`.
- **Reversibility:** `two-way door`.
- **Guard:** the SA208 system check, extended to assert that every boundary calls the
  coordinator.
- **First step:** move billing's obligation declarations into billing's `AppConfig`, leaving the
  tuple as the aggregate.

---

## Change-cost probe

**Probe A: SA191, rebuild `bap-web`** (next on the critical path). Stations:
1. Patch the donor `production.py` to call the `runtime.settings` facade (the validator refuses
   an inline copy).
2. `make beta-migrate-fresh`.
3. Rewrite the project-owned `properties` migrations for the NOT NULL org foreign key and SA153's
   tenancy.
4. Rebuild and reseed the database (project-owned work, no tool).
5. Verify the catalog and re-invited users (no tool).
6. `deploy railway` plus the runtime role (Railway vintage prose).
7. **New:** recreate the Stripe webhook endpoint at dahlia, if billing is enabled. That step is
   surfaced by `apply`'s next-steps output, but not by the vintage gate once the recipient records
   `0.89.0`.
8. Roll back by redeploying, with the retained old database as the data rollback (no tool).

**Verdict: finding evidence** (findings 1 and 2). 4 of 8 stations have no mechanism. SA206
shrank station 1 from a hand port to a single import.

**Probe B: ship one more contract change to existing projects,** measured on SA209. It edited the
module (upgradable, good), the manifest prose, two CLI echo sites, and `OPERATIONS.md.j2`, and it
did not bump `minimum`. **Verdict: finding 2 evidence.** The adoption channel dropped the step
for already-current projects.

**Probe C: add a project-owned tenant child table.** Tenancy and purge are unchanged apart from
SA208's additive check. **Verdict: still exonerated.**

## Fix-regression audit (closeouts in this delta)

- **SA205** (`58f58864`): removed the silent bad restore for artifact-backed and DR-snapshot
  sources. Fail direction: closed for artifacts, and for artifacts recording no vintage. A bare
  `--file` source with no carried vintage is not compared (`recovery.py:287-288`), which is
  documented in the docstring. No new structural commitment. **Containment for finding 1, sound.**
- **SA206** (`6b0aafa5`): **removed** the code-shaped compounding. The contracts moved to
  `quickscale_core.runtime.settings`, templates import them, the donor validator checks for the
  facade call, and the fifth station collapsed. It **minted** one public import path, which is a
  deliberate one-way door. `test_runtime_settings_facade.py:25-41` asserts that the expected names
  are a subset of `__all__`, which is a partial API guard. It preserved the fail-closed
  privileged/runtime selection (`:238-280` tests). The adoption step for existing projects was
  left to SA207 and is undeclared today. Finding 2 stays open, narrowed.
- **SA208** (`1744355e`): containment as recorded; the fail direction is refusal. Sound; finding
  3 stays open.
- **SA209** (`f1627c51`): replaced the hand-built Stripe fakes with real-SDK contract tests, and
  refuses mismatched-version events (fail closed). It **minted** a hand-synced version literal at
  5 stations (W7), and a step the vintage gate cannot surface (finding 2).
- **SA210** (`77350177`): a one-line template bound plus a fixture regeneration. No structural
  commitment. It is a template change outside SA207's planned watch set (finding 2 evidence).

## Fix order and interactions

- **SA207 should absorb finding 2's step-identity shape before it starts.** Otherwise it lands
  option 3 and needs a second schema change later. This is independent of Track 1.
- **Finding 1's freeze (SA204) must land before any post-SA153 module schema change.** Deciding
  the freeze release early lets SA153 write `0002+` from the start.
- **Finding 1 amplifies finding 3:** a failed data carry after SA153 would also strand removal
  obligations tied to rows that no longer migrate.
- Finding 3 is otherwise independent.

## Sound load-bearing decisions

- **Tenant isolation is dual-layer and fails closed** (boot guard plus SA203). Remediations must
  keep reseed, ETL, and coordinator work under the restricted role or `operator_access`, never
  BYPASSRLS at runtime.
- **Runtime contracts live in one upgradable facade** (SA206). Future security contract changes
  must go there, not back into templates.
- **Single-declaration derivation seams** work: tenant classification, module identity, runtime
  pins, and the SA193 credential blocks.
- **The generator fails loudly and proves its output boots** (`StrictUndefined` plus release-lane
  boot).
- **Vendor contract drift fails closed** (SA209): mismatched Stripe event versions are refused
  and logged rather than being mis-credited.

## Watchlist

- **W2: two filesystem-lock implementations** (`advisory_lock.py`, `dr_engine/_lock.py`).
  Trigger: a third implementation or divergent behavior. **Not fired:** neither file changed.
- **W3: hand-pinned residue in `provision_ci_postgres.sh`** (`POSTGRES_MAJOR=18`, the module
  count). Trigger: a 13th module or a new migration-bearing module. **Not fired:** there are still
  12 modules, 10 of them migration-bearing.
- **W4: `trigger_inputs` is a legacy name** for an exact E2E allowlist partition. Trigger: a
  skip keyed on it. **Not fired:** `check_gate_parity.py` is unchanged.
- **W6: billing `services.py` is the largest module file.** SA209 added about 120 net lines. It
  doesn't qualify, because status writes are still single-writer. Trigger: a second payment
  provider, or a second writer of `Subscription.status`. **Not fired.**
- **W7 (new): the Stripe API version literal lives at 5 non-test stations** (`services.py:42`,
  `apply_command.py:2698`, `module_config.py:1055,1066`, the billing manifest and mirror at `:50`,
  and `OPERATIONS.md.j2`). It doesn't qualify: bumps are rare, and a miss fails closed (refused
  events can be replayed for 30 days). Trigger: the next Stripe API version bump, or a second
  provider. Then derive the operator copies from `STRIPE_API_VERSION`.

## Rejected candidates

- **`85d0311b`'s `PINNED_VERSION` literal in `check_workflow_security.py`:** advisory warning
  text only, flat cost. A ticket.
- **SA209's 500 on a mismatched webhook version:** a deliberate fail-closed choice with a
  documented replay path. It is a sound decision, not a finding.
- **SA205's bare `--file` edge:** documented, operator-supplied input, and covered by finding 1's
  live option. Not a separate root.

## Questions that would change the ranking

- **`generated-file-ownership-unmodeled`:** is "regenerate and port" the permanent upgrade model?
  If so, option 4 applies and the finding drops to watchlist containment. (Carried; unanswered.)
- **`clean-break-schema-no-data-path` and `generated-file-ownership-unmodeled`:** will
  `experto-ai-web` migrate too? It doubles the population both findings affect. (Carried;
  unanswered.)
- **`generated-file-ownership-unmodeled`:** will 0.89.0 publish with billing's `minimum`
  unchanged? If yes, the SA209 step reaches every pre-0.89 project at release, and the new
  evidence becomes a latent hole for patch releases only.

*No red flags this pass.* No committed credential, unauthenticated surface, injection path, or
imminent data-loss condition was encountered.

## Reconciliation log

- 2026-09-24 — `clean-break-schema-no-data-path`: **still-open**, rank 1. No migration changed in
  the delta. SA205 was audited from source: it is sound containment, with a documented bare-file
  edge.
- 2026-09-24 — `generated-file-ownership-unmodeled`: **still-open**, rank 2, blast radius High →
  Medium. SA206 passed the fix-regression audit for code-shaped contracts (mechanism removed,
  fail direction preserved, one deliberate public API minted). New evidence: SA209 added an
  adoption step under an unchanged `minimum`, which the release-granularity gate cannot surface.
  SA207's planned gate is path-enumerated and already misses two template changes in this delta.
  Option 1 struck; option 2 (step identity) is the live recommendation.
- 2026-09-24 — `deletion-invariants-per-boundary-reimplementation`: **still-open**, rank 3.
  Trigger **not fired**. SA208 was audited from source: containment is sound.
- 2026-09-24 — Watch items **W2, W3, W4, W6**: **carried**, triggers not fired (evidence above).
  **W7** opened from SA209.
- 2026-09-24 — Questions: two carried unanswered, one opened.
- 2026-09-24 — Red flags: none prior, none this pass.
- 2026-09-24 — `deletion-invariants-per-boundary-reimplementation`: **containment landed** (SA208,
  option 3). The provider-ID walk runs as an orgs system check over `get_tenant_models()`, and
  purge refuses a provider-backed value.
- 2026-09-23 — `clean-break-schema-no-data-path`: horizon **moved** to SA153's go-live (reseed
  decision). SA205 (`58f58864`) landed the restore vintage refusal.
- 2026-09-23 — `clean-break-schema-no-data-path`: **new**, rank 1.
- 2026-09-23 — `generated-file-ownership-unmodeled`: **regressed** (reopened, rank 2). `882b5cf6`'s
  closure relocated the compounding into hand-copied adoption prose. SA206 then implemented option
  1.
- 2026-09-23 — `deletion-invariants-per-boundary-reimplementation`: **still-open**, rank 3. Prior
  counter-evidence corrected, and the trigger gained a project-provider-ID clause.
- 2026-09-23 — **W1** (privileged command set, five stations): **superseded** by
  `generated-file-ownership-unmodeled`. The station has since collapsed into the facade (SA206).
- 2026-09-23 — **W5** (hand-authored ownership taxonomy): trigger **fired**. **Superseded** by
  `generated-file-ownership-unmodeled`.
- 2026-09-23 — W2, W3, W4 carried; W6 opened. Probe A cleanup resolved by SA195. Red flags: none.
- 2026-09-23 — `module-env-contract-hand-wired`: **resolved** (declaration-driven `.env.example`
  renderer plus conformance); archived in CHANGELOG.
- 2026-09-18 — `deletion-invariants-per-boundary-reimplementation`: **still-open** (SA190 made the
  inventory structural).
- 2026-09-17 — `module-env-contract-hand-wired`: **new**, rank 1. W1–W5 established or carried.
  No red flags; a `compare_digest` defect was found already fixed (`adc753c6`).
