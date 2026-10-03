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

**Growth direction (planning surface, authoritative).** After the module conventions (SA215),
Track 1 is **SA191 → SA153 → SA204**:
1. SA191 rebuilds `bap-web` on current QuickScale and reseeds its data (maintainer decision,
   2026-09-23).
2. SA153 builds the first property portal on it as a project-owned extension.
3. SA204 freezes the module migration history at SA153's go-live horizon.

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
| Runtime security code reaches existing projects | Facade upgradable via lockstep pin; the generated-project declaration declares the facade adoption step and applied state records it (SA207) | Structural for new projects; declared and recorded for existing | **strengthened** (SA206, SA207, SA211: the SA208 provider-ID step is declared) |
| Schema and data survive a QuickScale upgrade | Clean-break rule; restore refuses an artifact with differing or absent `module_versions` (SA205); a bare `--file` restore is **not** compared (`recovery.py:287-288`) | Convention (explicit non-support) + one refusal gate | unchanged since SA205 |
| Template ↔ upgradable-code contract compatibility | One project-level declaration plus module-specific vintages; applied state records adopted step ids, confirmation advances the recorded vintage, and a registered gate requires a new step id when an emitted template or a module manifest step changes (SA207, SA211) | Gated: declaration, step-id adoption, module-manifest step identity, and template coupling; the watched set derives from the generator's emission mapping | **strengthened** (SA207, SA211) |
| Every emitted path has a migration disposition | Generator-derived conformance over a hand-authored taxonomy (89) | Membership gated | unchanged |
| Module credential env vars reach `.env.example` | Declaration-driven managed-block renderer + conformance | Structural + gated | unchanged |
| Org-removal obligations discharged | Each app declares its own obligations on its `AppConfig`, and app-owned stages name the declaring app's executor hook; one coordinator discharges each boundary's stages over the discovered set and fails closed; the system check rejects an unrouted, executor-less, or uninspectable declaration and a boundary that stops routing its stages; provider-ID system check and purge refusal cover model-classified and declared provider fields (SA208/SA213) | Domain-declared; conformance runtime | **remediated** (SA213) |
| Stripe webhook API version agrees with the SDK pin | `STRIPE_API_VERSION` set on the SDK; mismatched events refused (fail closed); 4 operator-facing copies of the literal | Structural at runtime; operator copies convention | **new row** (SA209); W7 |
| DRF throttling | Template defaults + module scopes merged via `setdefault` (`base.py.j2:250-286`); declared for existing projects as the project-level `sa201-throttling` step (SA207) | Structural for fresh projects; declared for existing | **declared** (SA207) |
| Generator template context complete | `StrictUndefined` + release-lane boot | Structural | unchanged |
| Publishing supply chain | SHA-pinned actions, minimal permissions, zizmor and secret scanning; zizmor now preflighted | Gated | unchanged (tooling ergonomics only) |
| CSRF-exempt endpoints have alternate integrity | AST gate + sanctioned bases | Structural + gated | unchanged |

## Summary table

| Rank | ID | Title | Horizon | Confidence | Size | Reversibility | Problem in one line |
|---:|---|---|---|---|---|---|---|
| 1 | `clean-break-schema-no-data-path` | Upgrades rewrite schema history with no data carry path | SA153 go-live | High / Medium | M | one-way door | Every release rewrites each module's only migration, and nothing carries a deployed project's data across it, yet SA153 brings the first tenant data that cannot be reseeded. |
Rank changes: **findings 2 and 3 are closed and dropped** (SA211 and SA213). SA211
identified every declared step and derived the gate's watched set from the emission
manifest; SA213 moved removal obligations onto each app's `AppConfig` behind a
coordinator that fails closed. Closed findings leave this file; their prior-pass
narratives are in version control and the changelog.

## Machine-readable index

```yaml
schema: arch-audit/v8
audited: cdb6223fb8a9bf28abf2bdf5ca93031feffbe3f7
items:
  - {id: clean-break-schema-no-data-path, status: open, rank: 1,
     title: "Upgrades rewrite schema history with no data carry path",
     lenses: [I, XVI, XIX], horizon: sa153-go-live, confidence: High, size: M,
     reversibility: one-way door, depends_on: [], amplifies: [],
     anchors: [docs/technical/decisions.md, quickscale_core/src/quickscale_core/dr_engine/recovery.py,
               quickscale_devtools/src/quickscale_devtools/beta_migration.py],
     first_seen: 2026-09-23, last_verified: 2026-09-24}
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

## Change-cost probe

**Probe A: SA191, rebuild `bap-web`** (on the critical path after SA215). Stations:
1. Patch the donor `production.py` to call the `runtime.settings` facade (the validator refuses
   an inline copy).
2. The one-off prompt-driven port onto a fresh recipient.
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
  left to SA207, which declared it and records its adoption in state. Finding 2 then stayed open,
  narrowed to SA211's remainder, which closed it on 2026-09-24.
- **SA208** (`1744355e`): containment as recorded; the fail direction is refusal. Sound; finding
  3 was later resolved by SA213 (reconciliation log).
- **SA209** (`f1627c51`): replaced the hand-built Stripe fakes with real-SDK contract tests, and
  refuses mismatched-version events (fail closed). It **minted** a hand-synced version literal at
  5 stations (W7), and a step the vintage gate initially could not surface; SA207 gives it the id
  `sa209-stripe-webhook-version` (finding 2).
- **SA210** (`77350177`): a one-line template bound plus a fixture regeneration. No structural
  commitment. It was a template change outside SA207's watched path set; SA211 derives that set
  from the emission manifest (finding 2 evidence).

## Fix order and interactions

- **SA207 absorbed finding 2's step-identity shape** for the project-level declaration, and SA211
  landed the remainder: the SA208 provider-ID step, module-manifest step gating, and the
  emission-manifest-derived watch set. The finding is closed. This was independent of Track 1.
- **Finding 1's freeze (SA204) must land before any post-SA153 module schema change.** Deciding
  the freeze release early lets SA153 write `0002+` from the start.

## Sound load-bearing decisions

- **Tenant isolation is dual-layer and fails closed** (boot guard plus SA203). Remediations must
  keep reseed, ETL, and coordinator work under the restricted role or `operator_access`, never
  BYPASSRLS at runtime.
- **Runtime contracts live in one upgradable facade** (SA206). Future security contract changes
  must go there, not back into templates.
- **Single-declaration derivation seams** work: tenant classification, module identity, runtime
  pins, the SA193 credential blocks, and, since SA213, organization-removal obligations declared
  on each app's `AppConfig`.
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
- **W6: billing `Subscription.status` has one writer.** It doesn't qualify while that holds. Trigger: a second payment
  provider, or a second writer of `Subscription.status`. **Not fired.**
- **W7 (new): the Stripe API version literal lives at 5 non-test stations** (`services.py:42`,
  `apply_command.py:2698`, `module_config.py:1055,1066`, the billing manifest and mirror at `:50`,
  and `OPERATIONS.md.j2`). It doesn't qualify: bumps are rare, and a miss fails closed (refused
  events can be replayed for 30 days). Trigger: the next Stripe API version bump, or a second
  provider. Then derive the operator copies from `STRIPE_API_VERSION`.

## Rejected candidates

- **`85d0311b`'s `PINNED_VERSION` literal in `check_workflow_security.py`:** advisory warning
  text only, flat cost. A ticket; SA212 replaced the literal with a `pyproject.toml` read.
- **SA209's 500 on a mismatched webhook version:** a deliberate fail-closed choice with a
  documented replay path. It is a sound decision, not a finding.
- **SA205's bare `--file` edge:** documented, operator-supplied input, and covered by finding 1's
  live option. Not a separate root.

## Questions that would change the ranking

- **Upgrade model (the closed `generated-file-ownership-unmodeled`):** is "regenerate and port"
  the permanent upgrade model? If so, that finding reopens as watchlist containment. (Carried;
  unanswered.)
- **`clean-break-schema-no-data-path` and the closed `generated-file-ownership-unmodeled`:** will
  `experto-ai-web` migrate too? It doubles the population both findings affect. (Carried;
  unanswered.)

*No red flags this pass.* No committed credential, unauthenticated surface, injection path, or
imminent data-loss condition was encountered.

## Reconciliation log

- 2026-09-24 — `deletion-invariants-per-boundary-reimplementation`: **resolved** (SA213). Each app
  declares its own removal obligations on its `AppConfig`; `orgs` aggregates the discovered set
  with no vendored labels or fields, both removal boundaries discharge it through one coordinator
  that fails closed on an undischarged obligation, declared provider fields refuse the purge until
  they are cleared or reconciled, app-owned stages run the declaring app's own executor hook, and
  the orgs system check (`E002`) fails a declaration no boundary can route or execute and a
  boundary that stops routing its stages through the coordinator. Archived in CHANGELOG.
- 2026-09-24 — `generated-file-ownership-unmodeled`: **SA211 landed and the finding is closed**
  (merge reconciliation; not audited by this pass). The SA208 provider-ID classification is a
  declared, identified step (`sa208-provider-id-classification` in `orgs`' manifest, mirrored to
  the bundled snapshot), so an upgraded project with an unclassified `*_id` field is refused on
  `apply`/`update`/`deploy railway` until it adopts it. The registered
  `check-project-contract-vintage` gate now fails a module manifest's `contract_vintage` step
  whose text changes without a new id (range, staged, and merge-resolution cases, with controls
  in both directions) and derives its watched template set from
  `get_generator_emission_mapping`, so `pyproject.toml.j2` and `OPERATIONS.md.j2` changes require
  an adoption step. Closed findings leave this file; the prior-pass narrative is in version
  control and the changelog.
- 2026-09-24 — `generated-file-ownership-unmodeled`: **SA207 landed** (merge reconciliation; not
  audited by this pass). One project-level declaration now owns each generated-template contract
  change with its adoption steps, the five SA192 manifest copies, orgs' block, and
  `RAILWAY_CONTRACT_VINTAGE` are gone, applied state records the adopted step ids, `apply`/
  `update`/`deploy railway` refuse on exactly the unadopted steps, confirmation advances the
  recorded vintage, and the registered `check-project-contract-vintage` gate fails a template
  change without a new adoption step id (range, staged, and merge-resolution cases; local, hosted,
  and publish contexts). The finding stays open for what SA211 now carries: step owners, SA208's
  provider-ID step, module-manifest step gating, and a watched set derived from the emission
  manifest.
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
