# Structural Autopsy: QuickScale

> **Audit snapshot:** 2026-09-23 · **Branch:** `v89` · **Range audited:** `98b6c455..1cf67cf7`
>
> Live structural findings only. Findings are identified by their **slug**; ordinal numbering is
> pass-local and is not a stable identifier (see
> [decisions.md → Document Responsibilities](../technical/decisions.md)). Closed findings and
> prior-pass narratives live in [CHANGELOG.md](../../CHANGELOG.md) and version control.

## Orientation summary

QuickScale is a Python 3.14 / Poetry **code generator and scaffolding platform**. It has a Click
CLI, a Django 6 project generator, and twelve first-party modules that are embedded into generated
projects by `git subtree` and upgraded by `quickscale update`. Generated projects run PostgreSQL
18, Vite/React, Docker, and Railway. Their public contracts are the CLI, `quickscale.yml` and
applied state, module manifests, the generated trees, and upgrade semantics. Tenant isolation in
generated projects is dual-layer: `TenantManager` plus `FORCE RLS` under a restricted runtime
role. The project has one maintainer and 3,723 commits. Governance is deliberate and dense: a
registered-gate universe, AST and conformance gates, and monotonic baselines. `decisions.md`
§ Clean-Break Migration History declares a **fresh-database-only** upgrade posture.

**Growth direction (planning surface, authoritative).** The live path is
**SA191 → SA153 → SA204**: migrate the production beta site `bap-web` onto current QuickScale with
the fresh-first tool, build the first property portal on it as a project-owned extension, then
freeze the module migration history at the SA153 go-live horizon. The maintainer's decision of
2026-09-23 reseeds `bap-web`'s data rather than carrying it, so SA191 no longer needs a data path
and the first upgrade that must carry **real production state** is the one that reaches SA153's
tenant data (finding 1).

**Commit delta** (`98b6c455..1cf67cf7`: 35 commits, 11 merges, 24 non-merge). Classification:

- **Closeout (14):** SA190 hardening `1270ed46` (already re-read by the prior pass's 09-18
  reconciliation), SA192/SA195 `e12e9867`, `5696f10a` (WIP checkpoints) and `4d8cb461`, SA199
  `5556e710`, SA193 `e05545db`, SA200 `dd310cfc`, SA198 `120d7d8b`, SA196 `5af7d62b`, SA202
  `cba8be07`, SA201 `d7f0cf87` and `9ccc5031`, SA203 `aa5ff547`, SA194 `45ca0c0a`. Each was
  mapped to its ticket. The fix-regression audit is below.
- **Housekeeping (10):** `b9814c05`, `d2aee905`, `978676f3` (audits), `a6322abf`, `6e8b2403`,
  `72d8c264`, `0bf013f6`, `0fd029b2`, `1cf67cf7` (roadmap), `686cd321` (three doc lines).
- **Unlabeled-behavioral (0 by message, 2 by content).** The two WIP checkpoints carry no
  closeout testimony, and `e12e9867` has no `vNN` token (the testimony gate covers only protected
  surfaces, so it passed). Read at full depth, they carry two load-bearing changes: a new
  `INTENTIONALLY_UNMANAGED` entry, and a 5-step `contract_vintage` block pasted into five module
  manifests. Both feed finding 2. Separately, **SA194's closeout changed 10 existing file
  dispositions.** It moved in-place-managed paths into `INTENTIONALLY_UNMANAGED`, including
  `frontend/vite.config.ts`. That is decision-record drift against `decisions.md:705-707`, which
  withholds authorization for "changes to existing file dispositions".

**Measurements run (§3).**
- **Churn × size over 12 months, top 4:** `apply_command.py` (82 commits × 3,967 lines),
  `beta_migration.py` (18 × 6,422), `module_commands.py` (59 × 1,687), billing `services.py`
  (19 × 4,288).
- **Fix-commit density by area:** highest in `quickscale_devtools/src` (8 of 18, **44%**); the
  generator templates have the most fix commits (46 of 174, 26%).
- **Co-change:** `production.py.j2` changed 28 times in 12 months, and `beta_migration.py` changed
  alongside it **0** times, even though the tool polices donor copies of that file. 174
  template-touching commits compare with 19 commits that ever touched a `contract_vintage`
  declaration.
- **Migration-history census:** since `bap-web` was generated (2026-03-05), **10 of 10**
  model-bearing modules' `0001_initial.py` were rewritten 2–5 times each, across 60
  migration-touching commits.
- **Other censuses:** AST census of `INTENTIONALLY_UNMANAGED` at six commits; a census of
  privileged-command stations; a census of `ContractVintage` declarations and their prose;
  ownership is single-author throughout.

**Read fully:**
- `decisions.md` § Clean-Break Migration History, § Generated-File Ownership, § Release scope
  safeguards, and § Beta-Site External Verification Scope.
- `roadmap.md`.
- `beta-site-migration.md` Steps 10, rollback, and checklists.
- `beta_migration.py` copy-scope constants (`:68-145`), `_build_pending_manual_actions`
  (`:1101-1175`), and the report build (`:5775-5795`).
- `check_beta_migration_smoke.py` shims and the fresh-first case.
- `dr_engine` restore command and compatibility checks.
- `contract_vintage.py`.
- `apply_command.py` state snapshot (`:2235-2270`).
- `orgs/removal.py`.
- `test_privileged_command_contract.py`.
- SA201 billing and `base.py.j2` diffs.
- The `production.py.j2` symbol map.

**Sampled:** billing `services.py` (status writes: single-writer, no finding), `base.py.j2`, the
DR orchestration metadata, `module_dependency_sync.py`, and the local `bap-web` and
`experto-ai-web` checkouts. These are read-only inspections of committed files, not their live
deployments, and they stay inside the External Verification Scope decision.

**Skipped:** `contracts/resolvers.py`, `manifest/` internals, the lock implementations beyond size
and history, frontend theme internals, and the module test suites as tests.

**Coverage and residual risk.** This is static analysis at `1cf67cf7`; nothing was executed except
read-only `git` queries and AST/YAML parses. **Needs runtime confirmation:**
- That current code run against a restored `bap-web` database stops with
  `InconsistentMigrationHistory` (finding 1).
- That an existing project's pre-SA201 `base.py` leaves the billing throttle inert (finding 2).
  Both have named commands in the finding.

A reader must **not** conclude from this document's silence that `contracts/resolvers.py`, the
manifest resolver, or the `dr_engine` orchestration internals are sound; no pass has read them at
depth. Nor should a reader conclude that SA191 is otherwise ready. This pass examined its data and
runtime-contract seams, not its frontend or media carry-over.

## Enforcement census

| Invariant | Enforcement | Posture | Trend since last pass |
|---|---|---|---|
| Tenant reads/writes stay organization-scoped | `TenantManager`, `FORCE RLS`, restricted-role boot guard | Structural | unchanged |
| Tenant-model universe is classified, refreshed, and purged | Marker-derived classification, FORCE-RLS refresh, FK-ordered purge | Structural; open to project-owned models | unchanged |
| Runtime DB role cannot bypass RLS | `rolsuper`/`rolbypassrls` boot guard | Structural | **strengthened**: SA203 narrowed the privileged exemption to the role check only, so the last-owner backstop and isolation-check registration now run on every startup path (`aa5ff547`) |
| Privileged Django command set | 3 frozensets + `start.sh.j2`, held equal by `test_privileged_command_contract.py`; a 5th copy in `beta_migration.py:3389-3396` is validated only through the fresh-first smoke gate, whose donor is always current-vintage | Gated, exact-member | unchanged. The station exists *because* `production.py` is donor-owned; now counted under finding 2 |
| **Schema and data survive a QuickScale upgrade** | **Containment only.** Clean-break rule (`decisions.md:952-968`). Restore refuses an artifact whose recorded `module_versions` differ from the installed modules — or that records none — before `pg_restore` runs (SA205); engine, format, and PG majors are still checked. No tool carries data across a rewrite. Migration smoke gate is same-vintage with `migrate` shimmed | **Convention (explicit non-support), one refusal gate** | **strengthened**: SA205 added the restore vintage refusal; finding 1 |
| **Template ↔ upgradable-code contract compatibility** | Detection: `project_contract` versus manifest vintages at `update`/`apply`/`deploy railway`. Adoption: prose steps, hand-copied (one block ×5, Railway ×2); `project_contract` never advances, so acknowledgement is per-invocation forever | **Detection gated; adoption content is convention** | **regressed**: SA200 and SA201 changed runtime contracts with no adoption step; finding 2 |
| Every emitted path has a migration disposition | Generator-derived conformance test over a hand-authored taxonomy | Membership gated both ways; disposition and doc mirror not gated | **weakened**: `INTENTIONALLY_UNMANAGED` grew **78 → 89**, and 4 entries have no rationale in `generated_file_ownership.md` |
| Module-declared credential env vars reach `.env.example` | One declaration-driven managed-block renderer plus conformance | Structural and gated | unchanged. The managed-block shape is the precedent for finding 2 |
| Cross-domain org-removal obligations are discharged | `ORGANIZATION_REMOVAL_OBLIGATIONS` in `orgs/removal.py`; last-owner predicate plus `pre_delete` backstop; SA208 provider-ID system check plus model-level `provider_id_classification` | Obligation inventory structural; provider-ID conformance **runtime, over installed tenant models** | **strengthened**: SA208 landed the option-3 containment; finding 3 stays open |
| DRF throttling | SA201: template defaults plus module-contributed scopes merged in `base.py.j2:390ff` | Structural for fresh projects; **undeclared for existing projects** | **new row**: see finding 2 |
| Generator template context is complete | `StrictUndefined` (`generator.py:373`) plus release-lane boot of a generated project | Structural | **new** (SA196) |
| Publishing supply chain | SHA-pinned actions, minimal `permissions:`, `check-workflow-security`, `check-secret-scanning` | Gated | **strengthened** (SA202) |
| CSRF-exempt endpoints have alternate integrity checks | AST gate plus sanctioned endpoint bases | Structural and gated | unchanged |
| Core/module dependency direction and lockstep pin | Import-compatibility and reverse-import gates; exact pin from `VERSION` | Gated | unchanged. String-label knowledge (`orgs/removal.py` naming billing fields) bypasses these gates; see finding 3 |
| Generated emission matches the recorded manifest | SA90 fixture comparison; `_HOST_DEPENDENT_PATHS` has 1 entry | Gated | unchanged (still 1) |

## Summary table

| Rank | ID | Horizon | Confidence | Size | Reversibility | Problem in one line |
|---:|---|---|---|---|---|---|
| 1 | `clean-break-schema-no-data-path` | SA153 go-live | High (mechanism) / Medium (exact failure) | M | one-way door | Every release rewrites each module's only migration, and nothing carries a deployed project's data across that rewrite, yet SA153's go-live brings the first tenant data that cannot be reseeded. |
| 2 | `generated-file-ownership-unmodeled` | now (regressed) | High | M | one-way door | QuickScale-owned runtime and security contracts live in template text that existing projects never receive. The vintage gate detects the gap but delivers only hand-copied prose that is already incomplete. |
| 3 | `deletion-invariants-per-boundary-reimplementation` | 6–18 months | High | M | two-way door | Org-removal obligations are declared centrally in vendored `orgs`, checked at runtime over installed tenant models, and executed per boundary. |

Rank changes: finding 1 is new and takes rank 1 by blast radius — a production database — and by
irreversibility; its horizon moved to SA153's go-live when the reseed decision removed it from the
critical path. Finding 2 reopens a finding that `882b5cf6` closed; the fix-regression audit is
below. Finding 3 moves from 1 to 3 with its horizon unchanged.

## Machine-readable finding index

```yaml
- id: clean-break-schema-no-data-path
  title: Upgrades rewrite schema history with no data carry path
  horizon: sa153-go-live
  confidence: high
  size: M
  reversibility: one-way-door
  status: open
  depends_on: []
- id: generated-file-ownership-unmodeled
  title: QuickScale-owned runtime contracts are frozen in user-owned template text
  horizon: now
  confidence: high
  size: M
  reversibility: one-way-door
  status: open
  depends_on: []
- id: deletion-invariants-per-boundary-reimplementation
  title: Organization deletion obligations are split across two boundaries
  horizon: 6-18-months
  confidence: high
  size: M
  reversibility: two-way-door
  status: open
  depends_on: []
```

---

## Finding 1: Upgrades rewrite schema history with no data carry path

**ID:** `clean-break-schema-no-data-path` · **Horizon:** SA153's go-live. The trigger is **SA153
shipping the first real tenant data**, followed by every QuickScale upgrade of a site holding data
that cannot be reseeded. · **Confidence:** High on the mechanism, verified from source,
the local `bap-web` checkout, and the tool. Medium on the exact runtime symptom, which is inferred
from Django's migration-consistency rule. · **Context dependence:** `wrong-for-now`, keyed on the
first production data. The clean-break rule was right while no generated project held data
anyone wanted to keep, and `bap-web`'s data is disposable by decision (2026-09-23).

**Rank rationale:** blast radius is a production database holding tenant data that cannot be
reseeded. Likelihood is certain within the horizon: SA153's go-live creates that data, and the
next module schema change would otherwise rewrite the only migration under it.

**Problem:** Each model-bearing module ships exactly one `0001_initial` that is rewritten in place
every release. The only upgrade path is a fresh database. No tool, contract, or guard carries a
deployed project's data from vintage N to vintage N+k. At the audit snapshot restore would even
replay a vintage-N schema under vintage-N+k code without objection; SA205 has since refused that
for an artifact-backed restore, and a bare operator-supplied `--file` restore records no vintage
to compare.

**Evidence:**

- **The rule.** `decisions.md:952-968`: "does not support in-place database upgrades between
  releases. The supported upgrade path is a fresh database … no cross-release backfill or
  compatibility migration class."
- **The rate.** Since `bap-web` was generated on 2026-03-05, `0001_initial.py` was rewritten
  for all 10 model-bearing modules: auth 2, backups 2, billing 5, blog 4, crm 4, forms 3,
  listings 3, notifications 3, orgs 4, social 4. This delta rewrote three more: blog
  (`d7f0cf87`), billing and orgs (`1270ed46`).
- **The donor.** The local `bap-web` checkout records `listings` 0001–0003, `forms` 0001–0003,
  and `auth` 0001–0002 as applied. It has no `orgs` module. Its project-owned
  `properties.PropertyListing` extends `AbstractListing`, and the project's own migrations
  0001–0002 carry no organization column. Current code differs:
  - `listings`, `forms`, and `auth` ship only `0001_initial`.
  - `listings.0001` and `forms.0001` depend on `quickscale_modules_orgs.0001_initial`.
  - `AbstractListing` now carries `organization = tenant_org_fk(...)` (`listings/models.py:22`),
    which is NOT NULL.
  - Running current code against that database violates Django's history consistency:
    `listings.0001` is recorded as applied while its new dependency `orgs.0001` is not.
- **The tool has no data station.** `beta_migration.py` contains no reference to dump, restore,
  `loaddata`, or `django_migrations`. `_build_pending_manual_actions` (`:1101-1175`) ends in
  "deploy-and-verify: confirm migrations in logs". The playbook's rollback is
  `railway redeploy <previous>` (`beta-site-migration.md:548-553`), which restores code but not
  the database.
- **The restore path cannot carry it either.** `_build_pg_restore_command` is a whole-database
  `pg_restore --clean --if-exists --no-owner` (`primitives.py:350-360`), so it restores the *old*
  schema and the old `django_migrations` rows. Backup metadata records `module_versions`
  (`orchestration.py:391`). At the audit snapshot `_get_restore_compatibility_issues`
  (`recovery.py:208-256`) checked engine, format, and PostgreSQL majors, and never compared module
  vintage. **SA205 has since added that refusal**: an artifact-backed restore whose recorded
  `module_versions` differ from the installed modules — or that records none — is refused before
  `pg_restore` runs, naming each differing module with both versions. The DR snapshot route
  compares the vintage recorded with the snapshot's authoritative dump, so a resumed snapshot is
  judged by the dump it restores rather than by recaptured sidecars. That containment does not
  carry data: it converts a silent bad restore into a hard stop, and a bare operator-supplied
  `--file` restore records no vintage to compare.
- **The CLI already tells users the answer.** On `InconsistentMigrationHistory`,
  `development_commands.py:385-420` offers to destroy the volume, or to "reconcile the migration
  history manually."
- **CI cannot see it.** The migration smoke gate generates donor *and* recipient from the current
  tree (`check_beta_migration_smoke.py:321-324`) and shims `quickscale`, `poetry`, `pnpm`, and
  `pytest` to `exit 0` (`:26`, `:114-130`). The verification stack's `quickscale manage migrate`
  (`beta_migration.py:482-484`) therefore always runs against a same-vintage scratch database.

**Counter-evidence.** The falsification pass searched for the following:
- A data-carry plan in `decisions.md`, the playbook, `dr_engine_migration.md`, and the user
  manual (`dumpdata`, `loaddata`, natural keys, export/import, "carry"): none. The backups JSON
  artifacts are documented as "export-only rather than restore inputs" (`user_manual.md:495`).
- A vintage check in restore: none at the audit snapshot; SA205 has since added one for
  artifact-backed restores (a recorded artifact that records no vintage is refused too).
- A deploy-time migration-state preflight: none. The only `InconsistentMigrationHistory`
  handling is the stale-local-volume helper.
- A recorded decision that SA191 may reseed instead of carry: **recorded 2026-09-23** — its data
  is reseeded, so the acceptance no longer requires count matching and this finding's trigger
  moves to SA153's go-live (see the reconciliation log).
- The roadmap commit `0bf013f6` states the intent ("data moves by backup and restore under the
  fresh-database rule"), but that combination has no mechanism.

**Why it compounds:**

- **Every release widens the gap.** Each in-place `0001` rewrite adds to the transform that
  every deployed project must hand-write on its next upgrade (10 of 10 modules, 60 commits in six
  months).
- **The data grows under stricter invariants.** After SA153, `bap-web` holds tenant rows under
  FORCE RLS and composite FKs. Under the clean-break rule its next upgrade would need an ETL that
  runs under `operator_access`, assigns `organization_id`, and preserves RLS policies, and it
  grows with every tenant table SA153 and SA154 add. The freeze removes that ETL for every upgrade
  after it.
- **Backups decay into write-only artifacts.** A backup taken before any upgrade used to restore
  cleanly at the PostgreSQL level into code that cannot run on it; restore now refuses that
  artifact on its recorded module vintage (SA205), so it is a hard stop rather than a silent bad
  restore. Without a data path it stays unrestorable. The recovery path is untested
  exactly where it matters (§5.XVI).
- **The population grows.** `experto-ai-web` (generated before `orgs`, with auth, forms, and
  blog) and every future production project join the set.

**Detection signal:** `InconsistentMigrationHistory` or `ProgrammingError: column … organization_id
does not exist` during `start.sh` migrate on a redeploy; a restore that reports success followed
by 500s. **Runtime confirmation:** restore a `bap-web` dump into a scratch PostgreSQL 18, point a
fresh-first recipient at it, and run `python manage.py migrate --plan`.

**Steelman:** pre-1.0 with no paying tenants, a clean-break history keeps every module's schema
legible in one file, avoids a long tail of data migrations, and let the tenancy retrofit land
without backfill code. `bap-web`'s data was small enough, and partly reseedable through its
catalog seed command, that reseeding beat building a platform capability — the maintainer's
decision of 2026-09-23. The finding stays live because SA153's tenant data is not reseedable.

**Correct shape:** once a project holds production data, a QuickScale upgrade has a verified,
tool-owned path from the project's recorded vintage to the current one. Restore refuses an
artifact whose recorded vintage the running code cannot read.

**Do-nothing cost:** SA191 reseeds and drops the old rows; the cost lands at SA153's go-live, where
each later upgrade of `bap-web` needs a hand-written transform with more tables and RLS in the
way. Backups taken before any upgrade stay unrestorable in practice. The first incident is a
failed production deploy or a "successful" restore that the application cannot run on.

**Options:**

1. **Freeze history at the first production vintage.** Lift rule 1 of the clean-break decision
   from a named release onward. From then on, each model-bearing module ships `0002+` incremental
   migrations, and in-place `0001` edits become a gated failure. This uses Django's native upgrade
   path, removes the compounding going forward, and reuses the existing migration-quality gates.
   With the reseed decision this no longer waits on SA191. This is a one-way door: once a project
   applies a frozen `0001`, it can never be re-squashed under it.
2. **Vintage-aware logical export/import.** Promote the backups JSON export to a restore input
   and add an importer keyed on the artifact's `module_versions`, with per-vintage transforms
   (org assignment, renamed fields). This keeps clean-break but **relocates** the compounding:
   every release that rewrites a `0001` must ship a transform. It is fully reversible.
3. **Accept and document.** Declare cross-release data carry out of scope before 1.0:
   - Rewrite SA191's acceptance to reseed `bap-web`'s catalog and re-invite its users (done
     2026-09-23).
   - Add one containment gate: restore refuses when the artifact's `module_versions` differ from
     the installed modules (done, SA205).
   - Revocation trigger: SA153's go-live with any tenant data that is not reseedable.

**Recommendation:** Option 3's containment now, and decide on option 1 before SA153 goes live.
Concretely: add the restore vintage refusal, and freeze `0001_initial` at the vintage `bap-web`
lands on. That vintage is the cheapest freeze point, because its database is rebuilt anyway. This
fits a one-maintainer project that is about to have its first real tenant. · **Size:** `M` ·
**Reversibility:** `one-way door` for option 1. Before closing it, prove on a restored `bap-web`
copy that `migrate` from the frozen `0001` produces the parity baseline (22 FORCE-RLS tables / 44
policies). · **First step (done, SA205):** in `recovery.py`, restore refuses an artifact whose
`module_versions` differ from the installed modules.

**Settled 2026-09-23.** The maintainer reseeds `bap-web`'s data instead of carrying it: SA191's
acceptance rebuilds and reseeds the database, so no ETL is written, and SA204's freeze is deferred
to the SA153 go-live horizon (roadmap reshaped the same day). SA205's restore refusal is the
containment that landed in the meantime.

---

## Finding 2: QuickScale-owned runtime contracts are frozen in user-owned template text

**ID:** `generated-file-ownership-unmodeled` (reopened; closed by `882b5cf6` on 2026-09-16) ·
**Horizon:** now. It is already regressing, and SA191 copies a donor `production.py` into the
migrated site. · **Confidence:** High · **Context dependence:** `wrong-for-now` (deployed
projects). It is noise for a project that is regenerated rather than upgraded.

**Rank rationale:** blast radius is the security and runtime contract of every existing generated
project: proxy trust, the privileged-command bridge, runtime-role database selection, and
throttling. Likelihood is demonstrated. Two contract changes in this delta reach no existing
project, one of them fails open, and the next ticket carries a pre-`orgs` settings file forward.

**Status (2026-09-23):** Option 1's code move is implemented by SA206 — the runtime contracts
now live in `quickscale_core.runtime.settings`, generated settings import them, and the donor
validator checks the facade call instead of parsing an inline copy (see the reconciliation log).
The finding stays open for the remaining configuration surface and the migration path (SA207's
single project-level vintage and template-change gate, SA191's donor adoption).

**Problem:** QuickScale's executable runtime and security contracts are emitted as template text
inside files classified as user-owned (`settings/production.py`, `settings/base.py`, `start.sh`,
`vite.config.ts`). Those files are never upgraded. The vintage mechanism that replaced the old
finding detects the gap, but it delivers the fix only as hand-copied prose. It does not advance
`project_contract`, and it cannot tell whether the prose is complete.

**Evidence:**

- **Code, not config, lives in the templates.** `base.py.j2` defines `ClientIdentityMiddleware`
  (`:111`), the client-IP normalizer that throttling keys on, and `CorrelationIdMiddleware`
  (`:177`). `production.py.j2` (398 lines) holds the SECRET_KEY guard, the proxy-trust
  derivation (`:117-129`), the privileged-command/runtime-database bridge (`:171-190`), and
  logging. Generated settings import nothing from QuickScale, although `quickscale_core.runtime`
  describes itself as "the public import path for generated-project code," and generated
  projects already install `quickscale-core` through manifest-declared pins
  (`module_dependency_sync.py:21`).
- **Delivery is prose, copied by hand.** The same five-step block is pasted verbatim into the
  `contract_vintage` of auth, billing, listings, blog, and crm. It describes one
  *project-template* change (SA192's shared design) and has no project-level owner.
  `RAILWAY_CONTRACT_VINTAGE` (`deployment_commands.py:43-50`) duplicates orgs' three steps
  verbatim. Both duplications were verified by parsing.
- **The prose is already incomplete.** Of the 7 commits that changed generator templates after
  vintage enforcement landed (`882b5cf6..HEAD`), SA200 (`dd310cfc`, proxy trust) and SA201
  (`d7f0cf87`, throttling) changed runtime contracts and declared no adoption step anywhere. This
  repeats the tally that opened the original finding ("0 of them declared a vintage").
- **One is skew-unsafe and fails open.**
  - SA201 moved billing's Stripe-endpoint throttle rates into the **upgradable** module
    (`billing/adapter.py`, `views.py:179,235,291,346` `throttle_scope = …`).
  - The pre-SA201 `base.py` assigns `REST_FRAMEWORK` wholesale *after* `MODULE_SETTINGS` ("so
    this template's safe default wins over any module-provided DRF config"). It declares no
    `DEFAULT_THROTTLE_CLASSES`.
  - An existing project that updates `billing` therefore gets scope attributes that no
    `ScopedRateThrottle` ever reads. The checkout-loop bound SA201 exists for is silently absent.
  - **Runtime confirmation:** in a pre-SA201 project, update billing and call
    `/billing/checkout` 31 times in an hour; expect no 429.
- **The gate cannot be satisfied, only silenced.** `project_contract` is written only when state
  is created (`apply_command.py:2254`). Existing states "preserve whatever they already have"
  (`:2262-2268`), and acknowledgement is per-invocation (`contract_vintage.py:91-96`). A
  pre-0.89 project must pass `--acknowledge-contract-vintage` on every `update`/`apply`/`deploy`
  for as long as it lives, unless it is regenerated.
- **The migration path discards the template half by policy.**
  - Fresh-first copies the donor's `settings/production.py` over the fresh scaffold's
    (`beta_migration.py:68-73`; `decisions.md:1043-1049`, "donor-owned by policy").
  - The local `bap-web` `production.py` has neither `_KNOWN_*` allowlist, and it trusts
    `X-Forwarded-Proto` unconditionally (`:61`), the pre-SA200 shape. That shape is benign behind
    Railway's proxy, which is exactly why the gap is invisible.
  - The playbook compensates by requiring a hand-patched donor before the tool runs
    (`beta-site-migration.md:568`).
- **The compensating machinery is the largest thing in the tool.** About 3,670 of
  `beta_migration.py`'s 6,422 lines (`:1221-4887`) are a static validator: Python AST, `start.sh`
  grammar, Dockerfile grammar. It polices a donor's copy of QuickScale's own contract, and it
  checks only the privileged-command subset. It co-changed with `production.py.j2` in 0 of 28
  commits.
- **The taxonomy that encodes these dispositions is growing, not shrinking.**
  - `INTENTIONALLY_UNMANAGED` went from 78 to 79 (`e12e9867`) and then to 89 (`45ca0c0a`).
  - The new entries include `frontend/vite.config.ts`, whose Host-enforcement contract five
    manifests tell users to "manually adopt".
  - Four entries have no rationale in `generated_file_ownership.md`: `validateQuickScaleSeam.ts`,
    `FormsPage.tsx`, `SocialEmbedsPublicPage.tsx`, and `SocialLinkTreePublicPage.tsx`.

**Counter-evidence.** The falsification pass searched for the following:
- A project-level (non-module) vintage: none; `ContractVintage` exists only on module manifests
  and the Railway constant.
- Any writer that advances `project_contract`: only fresh state creation.
- A gate requiring a vintage declaration when settings, `start.sh`, or Dockerfile templates
  change: none.
- `check_generated_deploy_posture.py`: it deploy-checks a *freshly generated* project only.
- A runtime import of shared middleware in generated settings: none.

Partial containment exists and is real: the vintage gate refuses before mutation, the
privileged-command cross-station test holds the frozen copies equal, and the SA193 managed-block
renderer proves in-repo that QuickScale can own a region of a user file safely.

**Why it compounds:**

- **Every runtime contract change pays three times.** It is written into the template, written
  again as prose, and pasted into each manifest that "owns" it. A missed paste fails silently in
  existing projects (the SA200/SA201 cases).
- **Every contract that lands template-side grows the donor-file validator.** Otherwise it is
  lost on migration. The 5th privileged-command station (former **W1**) exists for this reason.
- **Every existing project accumulates an unbounded acknowledgement debt** and drifts further
  from what the tests exercise.
- **The ownership taxonomy grows** by the files that neither mode can manage (former **W5**),
  against its decision record.

**Detection signal:** `quickscale status` reporting "behind" on a project that has done every
listed step; a module feature that works in fresh projects but not in updated ones (the throttling
case); `INTENTIONALLY_UNMANAGED` growth. To instrument: a CI check that fails when a commit changes
`templates/project_name/settings/*`, `start.sh.j2`, or `Dockerfile.j2` without touching a vintage
declaration.

**Steelman:** a generated project's settings belong to the user. Anything QuickScale imports at
runtime becomes a versioned API that is expensive to change. Before 1.0, "regenerate and port" is
a legitimate upgrade model, and the vintage gate is an honest, fail-closed statement of that model.
You would not fix this if generated projects are treated as disposable until 1.0 and the beta
sites are the only deployed population.

**Correct shape:** every contract QuickScale needs a generated project to honor either (a)
executes from upgradable QuickScale code the project imports, or (b) lives in a QuickScale-owned
region that a QuickScale command re-renders. The project-level vintage that describes it is
declared once, advances when adopted, and is gated against template changes.

**Do-nothing cost:** each release ships runtime fixes to new projects only. SA191 carries a
hand-patched pre-`orgs` settings file into the portal site. The validator and the taxonomy keep
growing (57% of the maintainer tool already). The first security fix that matters for a deployed
site reaches it only if the maintainer remembers to paste the prose.

**Options:**

1. **Move code-shaped contracts into the runtime library.** Put the middleware, the proxy-trust
   derivation, the privileged-command/runtime-database selection, and the SECRET_KEY guard into
   a versioned `quickscale_core.runtime` settings facade. Templates keep one import and user
   configuration. This removes the most compounding: fixes ship through the existing lockstep
   pin, the donor validator shrinks to "does the file call the bridge", and the 5th station
   collapses. The import path becomes a public API.
2. **QuickScale-managed regions in settings.** Extend SA193's `# QuickScale … (managed)` block
   renderer to the security sections of `production.py` and `base.py`, re-rendered by `apply`.
   It has an in-repo precedent and delivers through an existing command. Python ordering
   semantics make regions fragile, and SA201's `REST_FRAMEWORK` ordering bug is exactly that
   hazard.
3. **Accept and document.** Keep templates as they are and add containment:
   - A project-level vintage with a single declaration of adoption steps, replacing the ×5 and
     ×2 copies.
   - A gate that fails when those templates change without a vintage edit.
   - `project_contract` advances when the user confirms the steps.
   - Revocation trigger: the first release after SA153 that changes a production-settings
     contract.

**Recommendation:** Option 1 for code-shaped contracts, starting with the two middleware classes
and the privileged-command bridge. Use option 3's template-change gate and single project-level
vintage for what remains configuration. A generator whose shipped modules already depend on a
runtime facade should not keep its security middleware in templates. · **Size:** `M` ·
**Reversibility:** `one-way door`, because generated projects will import the facade. SA206
implemented option 1 and confirmed the zero-module `quickscale-core` pin; what remains is SA207's
project-level vintage and template-change gate and SA191's donor adoption (see the Status note
above). · **First step (done, SA206):** move `ClientIdentityMiddleware` and
`CorrelationIdMiddleware` into `quickscale_core.runtime`, and have `base.py.j2` import them.

---

## Finding 3: Organization deletion obligations are split across two boundaries

**ID:** `deletion-invariants-per-boundary-reimplementation` · **Horizon:** 6–18 months ·
**Confidence:** High · **Context dependence:** `wrong-for-now` (production tenants / compliance)

**Rank rationale:** blast radius is billing and retention for real organizations, which SA153
creates first. Likelihood is moderate. Both boundaries exist, but no third boundary or erasure
requirement is scheduled.

**Trigger:** another destructive organization-removal boundary, a durable-erasure requirement, or
**a project-owned tenant model with an external provider ID** (new this pass). **Not fired:** no
new boundary, and SA153's scope names no provider ID. But see the last evidence bullet.

**Problem:** Last-owner safety and the obligation inventory are structural, but the inventory is
declared centrally in the vendored `orgs` module. Its conformance check now runs as an orgs system
check over installed tenant models (SA208), but each boundary still orchestrates its own subset.

**Evidence (re-verified in the 2026-09-23 pass; `removal.py` was unchanged since `1270ed46` until
SA208):**

- `ORGANIZATION_REMOVAL_OBLIGATIONS` (`orgs/removal.py:72-141`) declares four obligations against
  a hard-coded two-member `RemovalBoundary` enum (`:12-16`).
- The billing obligation names **billing's** model labels and field names as strings
  (`quickscale_modules_billing.credittransaction`, `…subscription`, and others). The base module
  therefore encodes knowledge of a dependent module, and the import-direction gates cannot see it.
- `cancel_current_subscription` has exactly two callers (`billing/views.py:320`,
  `auth/views.py:463`), unchanged. The last-owner predicate and the `pre_delete` backstop are
  unchanged. SA203 made the backstop install on the privileged startup path too (`aa5ff547`).
- **Corrected from the prior pass:** `external_provider_obligation_mismatches` (`:261-373`) was
  called only from `orgs/tests/test_removal.py:42`. It ran over orgs' test `INSTALLED_APPS`, never
  in a generated project, and could not see project-owned models. Its heuristic
  (`:187-196`) treated any non-relational `*_id` field as a provider ID, so a SA153 property model
  with, say, an `mls_id` would have been purged without refusal or reconciliation. **SA208 landed
  the option-3 containment:** the walk now runs as an orgs system check over
  `get_tenant_models()`, including project-owned models; a project model classifies each of its
  `*_id` fields in its own `provider_id_classification` without editing vendored `orgs` source;
  and `purge_organization` refuses while a row carries a value in a field classified
  provider-backed, naming the field.

**Counter-evidence:**
- Searched billing for `pre_delete`/`post_delete` receivers and model `delete()` hooks: none.
- Live-subscription refusal is enforced before purge.
- Account deletion records its deliberate skips (`skipped_removal_obligations`).
- The prior pass's claim that provider-ID conformance "rejects a purged external ID" now holds at
  runtime for installed tenant models, including project-owned ones (SA208).

**Why it compounds:** each new obligation extends the central tuple and each boundary's handler.
Each new boundary (bulk admin, GDPR erasure, `teams`) needs its own orchestration and a new enum
member. A project-owned provider ID now has a declaration path (SA208), but it discharges only the
purge boundary: account deletion and any future boundary still have no declared handling for it.

**Detection signal:** a new deletion boundary that does not consume the contract. A project model's
undeclared `*_id` field now fails the orgs system check, and a provider-backed value refuses the
purge by name.

**Steelman:** the two boundaries have genuinely different intents (remove a person versus tear
down an organization). A coordinator before real tenants exist is premature, and a central tuple
is the simplest thing that makes the differences visible.

**Correct shape:** each domain, including a project app, declares its own removal obligations
where it lives. Every boundary discharges the discovered set idempotently. Conformance runs in the
generated project, over the installed models.

**Do-nothing cost:** bounded until SA153 holds real organizations. After that, the first divergence
is a retention or billing incident, diagnosed by hand.

**Options:**

1. **Domain-registered obligations plus a coordinator.** Each app contributes obligations (for
   example through an `AppConfig` hook, the way tenant markers work). A coordinator called by
   both boundaries discharges them, and the conformance walk runs as a Django system check in
   generated projects.
2. **Domain-local safeguards.** Billing refuses deletion of rows with a live provider ID, with an
   outbox for reconciliation. This is strong against bypass but brings network effects into
   transactions.
3. **Accept and document.** Keep the central tuple and move the conformance walk into a
   generated-project system check (containment). Revocation trigger: a third boundary or a
   project provider ID.

**Recommendation:** option 3's containment when SA153 starts, because it is cheap and puts the
check where project models exist. Move to option 1 when the trigger fires. · **Size:** `M` ·
**Reversibility:** `two-way door`. · **First step (done, SA208):** register
`external_provider_obligation_mismatches` as an orgs system check over `get_tenant_models()`, with
the model-level `provider_id_classification` declaration and the purge refusal.

---

## Change-cost probe

**Probe A: SA191, rebuild `bap-web` on current QuickScale** (the only scheduled change; the
reseed decision reshaped its data station).
Station list, in order:

1. Hand-patch the donor `settings/production.py` to call the versioned
   `quickscale_core.runtime.settings` facade in its canonical shape; the preflight refuses an
   inline copy of the command-mode contract (`beta-site-migration.md:50-63`).
2. Run `make beta-migrate-fresh`. It copies the patched donor `production.py` over the fresh one;
   the runtime contracts now arrive through the facade and the lockstep pin, so SA200/SA201-era
   fixes reach the migrated project.
3. Rewrite the project-owned `properties` migrations. `AbstractListing` now adds a NOT NULL org
   FK, and SA153 requires `TenantManager`, `apply_force_rls`, and composite FKs on
   `PropertyImage`/`PropertyFeature`.
4. **Data:** a production database recording `listings` 0001–0003, `forms` 0001–0003, `auth`
   0001–0002, and no `orgs`. Rebuilt fresh and reseeded through `bap-web`'s own seed command,
   with users re-invited; no ETL. **No tool; project-owned work.**
5. Verify the reseeded catalog and the re-invited users against the old site. **No tool.**
6. Replace the repo, deploy with `deploy railway`, and provision the runtime role (Railway vintage
   prose, 3 steps).
7. Roll back. Playbook redeploy restores code; the retained pre-cutover database is the data
   rollback, and it is project-owned work. **No tool.**

**Verdict: finding evidence** for findings 1 and 2. Of 7 stations, 3 have no mechanism, and 2 are
hand edits of QuickScale-owned contract. The reseed decision removes station 4's ETL from SA191,
but the finding stays live at SA153's go-live.

**Probe B: ship one more runtime-security fix to existing generated projects,** measured on
SA200 (`dd310cfc`, 22 files). Stations:
1. Edit `production.py.j2`/`base.py.j2`.
2. Add a deploy-posture gate (fresh projects only).
3. Update the SA90 emission fixture.
4. Existing projects: choose a module manifest to host the prose (none is the right owner),
   paste it into each relevant manifest, and have each project hand-diff its settings.
5. Migrated projects: the donor copy discards the fix again.

SA200 did 1–3 and skipped 4. **Verdict: finding 2 evidence.**

**Probe C: add a project-owned tenant child table** (carried from the prior pass). The tenancy
and purge paths are unchanged since it exonerated them (`removal.py`/purge touched only by SA202
lint and SA199). **Verdict: still exonerated**, with finding 3's caveat for provider-ID fields.

## Fix-regression audit (closeouts in this delta)

- **SA193** (`e05545db`): the mechanism was removed. The declaration-driven renderer plus
  conformance keeps the prior closure of `module-env-contract-hand-wired`. Sound. Managed blocks
  are a precedent for finding 2.
- **SA194** (`45ca0c0a`): removed 3,308 lines and an entire mode. **It minted** 10 new
  `INTENTIONALLY_UNMANAGED` dispositions (78→89) against the Release-scope-safeguards record,
  without updating that record. It did not remove the 5th privileged-command station. Counted
  under finding 2.
- **SA200 / SA201:** each removed its own defect class in *fresh* projects. **Relocated:** the
  contract change is invisible to existing projects (no vintage), and SA201's is skew-unsafe.
  Finding 2.
- **SA203** (`aa5ff547`): narrowed a privileged exemption. It preserved the fail direction and
  strengthened a sound decision. Sound.
- **SA196** (`5af7d62b`), **SA198** (`120d7d8b`), **SA199** (`5556e710`), **SA202**
  (`cba8be07`), **SA192/SA195** (`4d8cb461`): no new structural commitment beyond what is
  recorded above. SA195 removed the byte-identical test stubs flagged by the prior probe A, and
  the flagged cleanup is closed. SA198 unified TLS parameters for `pg_dump`/`pg_restore`. The
  tech audit's remaining "separate connection constructor" in `start.sh.j2` stays a tech-audit
  smell.

## Fix order and interactions

- **Findings 1 and 2 touch SA191, and both are decided before it runs, not during.**
  - Finding 1 is settled: `bap-web` is reseeded, and the freeze lands at SA153's go-live horizon
    on the vintage SA191 lands `bap-web` on.
  - Finding 2's first step removes one of SA191's hand edits (station 1) whenever the migrated
    settings adopt the runtime import.
  - They do not conflict, and each can proceed in parallel.
- **Finding 2's option 1 shrinks the migration tool.** Its validator could check "imports the
  runtime bridge" instead of parsing shell and AST. Do finding 2 before investing further in
  `beta_migration.py`.
- **Finding 3 is independent.** Its containment step should land with SA153's first tenant tables.
- **W3 interacts with finding 1:** a restore vintage guard makes the DR contract depend on module
  versions as well as on the two PostgreSQL majors.

## Sound load-bearing decisions

- **Tenant isolation is dual-layer and fails closed**, and SA203 made it more so. The boot guard
  still rejects `rolbypassrls`/`rolsuper`. The last-owner backstop and isolation-check
  registration now run even under the privileged command (`aa5ff547`, with discriminating tests).
  Remediation of findings 1 and 3 must keep reseed/ETL and coordinator work under the restricted
  runtime role, or `operator_access` where elevated scope is needed, never BYPASSRLS at runtime.
- **Single-declaration derivation seams work where they are used.** Tenant classification and
  purge are marker-derived. Module identity is derived. Runtime pins and the runtime role have one
  declaration each. SA193's credential blocks are declaration-driven. These are the precedent for
  finding 2's options.
- **The generator fails loudly and proves its output boots.** `StrictUndefined`
  (`generator.py:373`) plus a release-lane boot of a generated project through its shipped
  `start.sh` (SA196). Finding 2's runtime-library move should extend this boot check to an
  *updated* project, not replace it.
- **The vintage gate refuses before mutation.** Its detection half is right: it compares recorded
  state with declared requirements at every mutating boundary. Finding 2 targets its content,
  ownership, and non-advancing state, not the gate.
- **The publishing supply chain is pinned and scanned** (SA202): SHA-pinned actions, minimal
  permissions, and secret and workflow scanning as registered gates.

## Watchlist

- **W2: Two independent filesystem-lock implementations** (`advisory_lock.py` 514 lines,
  `dr_engine/_lock.py` 298 lines). *Doesn't qualify:* both contracts are preserved and the split
  is release-accepted. **Trigger:** a third implementation, or divergent behavior or platform
  support. **Not fired:** neither file changed in the delta, and a repo-wide
  `fcntl`/`flock`/`O_EXCL` search finds only these two.
- **W3: Hand-pinned residue inside derived provisioning** (`provision_ci_postgres.sh:6`
  `POSTGRES_MAJOR=18`, `:93` `!= teams`, `:96` `== 12`). *Doesn't qualify:* all fail loudly.
  **Trigger:** a thirteenth module, `teams` graduating, another migration-bearing module, or the
  DR contract depending on the two majors agreeing. **Not fired:** the universe is still 12, 10
  modules are migration-bearing, and the script is unchanged in the delta.
- **W4: `trigger_inputs` is a legacy name for an exact E2E allowlist partition**
  (`check_gate_parity.py:42-49,326,512`). *Doesn't qualify:* the check is exact and documented.
  **Trigger:** any context skipping a gate based on `trigger_inputs`. **Not fired:**
  `check_gate_parity.py` is unchanged in the delta, and the registry description still forbids
  skips.
- **W6 (new): Billing `services.py` is the largest module file (4,288 lines, +2,521 in one
  commit).** *Doesn't qualify:* subscription status writes are single-writer inside billing, and
  the sampled seams are coherent. Size alone is a ticket. **Trigger:** a second payment provider,
  or a second module writing `Subscription.status`.

## Questions that would change the ranking

- **`generated-file-ownership-unmodeled`:** is "regenerate and port" the intended *permanent*
  upgrade model for generated projects, or only a pre-1.0 one? If permanent, option 3 is the right
  end state and the finding drops to watchlist containment.
- **Both findings:** is `experto-ai-web` scheduled to migrate too? It is generated before `orgs`,
  with auth, forms, and blog, and it doubles the population both findings affect.

The `clean-break-schema-no-data-path` question — carry or reseed — was settled on 2026-09-23: the
data is reseeded, and the finding's horizon moves to SA153's go-live (reconciliation log below).

*No red flags this pass.* No committed credential, unauthenticated surface, injection path, or
imminent data-loss condition was encountered. `bap-web`'s unconditional `X-Forwarded-Proto` trust
is benign behind Railway and is recorded as finding-2 evidence, not as a red flag.

## Reconciliation log

- 2026-09-24 — `deletion-invariants-per-boundary-reimplementation`: **containment landed** (SA208,
  option 3). The provider-ID conformance walk runs as an orgs system check over
  `get_tenant_models()`; a project-owned model classifies each non-relational `*_id` field in its
  own `provider_id_classification` without editing vendored `orgs` source; and
  `purge_organization` refuses an organization while a row carries a value in a field classified
  provider-backed, naming the field. The finding stays open with its trigger unchanged: the
  containment refuses a project provider ID rather than reconciling it, so option 1 is owed when a
  third destructive boundary, a durable-erasure requirement, or a project-owned tenant model with
  an external provider ID arrives.
- 2026-09-23 — `clean-break-schema-no-data-path`: horizon **moved** to SA153's go-live. Maintainer
  decision: `bap-web`'s data is reseeded rather than carried, so SA191's acceptance no longer
  requires a data path and SA204's freeze is deferred to the SA153 go-live horizon (roadmap
  reshaped the same day). SA205's restore vintage refusal (`58f58864`) is the containment that
  landed in the meantime; the question that opened this finding is closed.
- 2026-09-23 — `clean-break-schema-no-data-path`: **new**, rank 1. SA191's acceptance requires
  carrying production data across a clean-break schema rewrite with no mechanism.
- 2026-09-23 — `generated-file-ownership-unmodeled`: **regressed** (reopened, rank 2). `882b5cf6`
  had closed it by enforcing contract vintages at mutation boundaries. The fix-regression audit
  finds the compounding relocated into hand-copied adoption prose: one block ×5 and Railway ×2.
  That prose was already incomplete for SA200/SA201, `project_contract` never advances, and SA194
  grew the unmanaged taxonomy 78→89.
- 2026-09-23 — `generated-file-ownership-unmodeled`: **option 1 implemented (SA206)**. The
  middleware, proxy-trust derivation, privileged-command/runtime-database selection, and
  SECRET_KEY guard now live in `quickscale_core.runtime.settings`; generated settings import
  the facade and keep only user configuration, and the donor validator checks that donor
  settings call `resolve_runtime_database_url` instead of parsing the inline contract
  (`beta_migration.py` shrinks by ~2,000 lines, and the fifth station collapses to the facade).
  A zero-module generated project declares the bounded `quickscale-core` lockstep pin in its
  `pyproject.toml`. Remaining scope: SA207's single project-level vintage and template-change
  gate, and SA191's donor adoption.
- 2026-09-23 — `deletion-invariants-per-boundary-reimplementation`: **still-open**, rank 3. The
  prior counter-evidence was corrected: provider-ID conformance runs only in orgs' test suite and
  cannot see project-owned models. The trigger gained a project-provider-ID clause.
- 2026-09-23 — Watch item **W1** (privileged-command set, five stations): **superseded** by
  `generated-file-ownership-unmodeled`. The fifth station exists because `production.py` is
  donor-owned. Trigger evaluation: the donor-vintage clause **fired** for `bap-web`, whose
  `production.py` has neither allowlist. It is contained, not drifting: `_validate_runtime_compatibility`
  runs on the fresh-first report path (`beta_migration.py:5788`) and blocks. The smoke gate
  reaches it only with a current-vintage donor.
- 2026-09-23 — Watch item **W5** (hand-authored ownership taxonomy): trigger **fired**. There is a
  second doc drift: 4 tuple entries lack a rationale in `generated_file_ownership.md`, while the
  prior drift entry was fixed. The list also grew 78→89 instead of shrinking. **Superseded** by
  `generated-file-ownership-unmodeled`, as the manifestation of that root.
- 2026-09-23 — Watch items **W2**, **W3**, **W4**: carried, triggers **not fired** (evidence
  above). **W6** opened.
- 2026-09-23 — Prior-pass change-cost probe A's cleanup (byte-identical test `base.html` stubs):
  **resolved** by SA195 (`4d8cb461`). Blog, CRM, listings, and analytics use `tests_shared`;
  auth and billing keep local stubs by recorded choice.
- 2026-09-23 — Questions: the prior document at `98b6c455` carried no open-questions section, so
  there is nothing to reconcile. Three new questions opened.
- 2026-09-23 — Red flags: none prior, none this pass.
- 2026-09-23 — `module-env-contract-hand-wired`: **closed**. The generated `.env.example`
  contract renders from each module's declared `*_env_var` options in one place; the static
  template copy and the three hand-written render/splice triples are retired, and a conformance
  check fails when a declaration has no placeholder. `storage` and `backups` gain placeholders on
  the next `apply` — a deliberate behavior change. With rank 1 closed,
  `deletion-invariants-per-boundary-reimplementation` is the only live finding and takes rank 1;
  closure archived in CHANGELOG.
- 2026-09-18 — `deletion-invariants-per-boundary-reimplementation`: **still-open**. SA190 made the
  obligation inventory structural and completed marker-derived, FK-ordered purge, retiring the
  former purge-membership dependency whose closure is archived in CHANGELOG. Boundary-local
  execution remains; horizon stays 6–18 months and rank is now 2.
- 2026-09-17 — `module-env-contract-hand-wired`: **new**. Opened at rank 1; the only finding with a
  live defect rather than a scheduled trigger.
- 2026-09-17 — Prior watch item *"Privileged-command set has four independent enforcing stations"*:
  carried as **W1**, trigger **partially fired** — a fifth declaration
  (`beta_migration.py:3663`) exists outside the cross-station test. Not promoted: the
  beta-migration smoke gate contains the drift. Separately, `37987df9` **resolved** the prior
  pass's noted third sanctioned command by retiring it, and gated the retirement.
- 2026-09-17 — Prior watch item *"Two independent filesystem-lock implementations"*: carried as
  **W2**, trigger **not fired** — neither file changed; no third implementation exists.
- 2026-09-17 — Prior watch items *"Hand-pinned residue inside the provisioning derivation"* and
  *"SA92 migration-squash discovery tuple"*: **merged** into **W3** (same shape: hand-pinned
  residue that fails loud). Both triggers **not fired** — census re-run: 12 modules, and the SA92
  tuple's 10 names match the 10 modules with migration directories.
- 2026-09-17 — Prior watch item *"`trigger_inputs` is a legacy name"*: carried as **W4**, trigger
  **not fired**.
- 2026-09-17 — New watch item **W5** opened for the beta-migration ownership taxonomy, explicitly
  bounded by `decisions.md` § Release scope safeguards.
- 2026-09-17 — Prior *"Questions that would change the ranking"* recorded no open question. Two new
  questions opened this pass.
- 2026-09-17 — No red flags this pass: no committed credential, unauthenticated surface, injection
  path or imminent data-loss condition was encountered. The `str`-vs-`bytes` `compare_digest`
  defect that would have qualified was found already **fixed** in this delta (`adc753c6`), and its
  census (2 of 2 hand-rolled verifiers affected, both corrected) is recorded in the enforcement
  census instead.

*Lenses scanned with no qualifying finding this pass:*
- Observability and operability.
- CLI/API contract stability.
- Performance and scalability.
- Concurrency (beyond W2).
- Build, release, and supply chain (strengthened by SA202).
- Cost and resource economics: no metered driver beyond Stripe calls, which SA201 bounds for
  fresh projects.
- Data lifecycle, privacy, and residency: no declared regulatory obligation.
- Contributor model: single maintainer; the lens is inert.

The ranked findings came from:
- **Data/state model, failure domains and recovery, and change safety and rollout** (finding 1).
- **The code-generator archetype lens, governance and gate architecture, and design conflicts**
  (finding 2).
- **Trust boundaries and module cohesion** (finding 3).
