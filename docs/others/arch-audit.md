# Architecture Audit — Open Findings

Audited: `82ff3e7d141cf943ab900eaae5f214c0edfc9e07` (v89) · 2026-10-23 · working tree clean at
snapshot · prompt: deep-architectural-audit v11

Snapshot basis: HEAD `82ff3e7d`; no uncommitted or untracked inputs were present or read. The only
post-snapshot change is this deliverable. A `git status --porcelain` recheck at delivery shows only
`docs/others/arch-audit.md`.

Cite a finding only by its slug ID; section numbers are not stable. Resolved findings and prior
full text are in git history (`git log -- docs/others/arch-audit.md`). The prior pass audited
`cca2eac9` (2026-10-20); its one open finding and eight watchlist items are reconciled at the end.

## Orientation summary

QuickScale is a **code generator plus runtime library and module workspace**: a Python 3.14/Django
CLI (`quickscale_cli`, 19.7 k LOC) renders a standalone Django + React 19/Vite project from Jinja
templates in `quickscale_core` (30.1 k LOC plus templates), vendors twelve first-party Django
modules (`quickscale_modules/*`, 46.6 k LOC excluding tests/migrations) into each project with git
subtree, and ships a versioned `quickscale_core.runtime` library behind a minor-range lockstep pin.
Generated projects use PostgreSQL 18, Poetry, Docker/Railway, and a single **showcase_react** theme.
Generator state is YAML under `.quickscale/`. Deployment realities: **(A) the maintainer repo and
release toolchain** and **(B) generated projects**; the regenerated cutover project is
`bap-web-new`, while the old `bap-web` still serves production until SA191d completes. The configuration space is twelve optional modules, one theme, SaaS/single-tenant orgs
mode, local/S3 media, local/remote backups, console/Resend notifications, and three deployment
paths (Railway, dev Compose, manual). Data handled includes personal data (form IP/user agent,
emails), tenant business data, Stripe identifiers, and private backup artifacts; `decisions.md`
claims a "GDPR-capable" organization purge. One maintainer, very high cadence (3,789 non-merge
commits in twelve months), twelve modules at 0.89.0. Growth direction (roadmap): SA191d production
cutover, SA153 first project-owned property portal, SA277 upgrade path. Stated-vs-actual gaps are
the subject of several findings: "one source" claims coexist with hand-synced lists; the generated
test harness cannot exercise the RLS guarantee it ships.

**Declared architecture (from `docs/technical/decisions.md`, `module_architecture.md`,
`plan-apply-system.md`, `module_conventions.md`, and the test docstrings):**

- `quickscale.yml` is desired state; `.quickscale/state.yml` is the sole authoritative applied-state
  store; apply is declarative, incremental, idempotent, and serialized by an advisory lock.
- Module wiring reaches a project only through managed files and `quickscale_core.runtime`;
  user-owned emitted files carry no module wiring (closed-world emission test).
- Module configuration is declared once in `module.yml`; the manifest is a module's one home for
  identity, version, options, normalization, validation, wiring, CI placeholders, and operations text.
- Modules distribute as split branches and immutable `splits/<module>-module/<version>` tags; embed
  consumes the tag, update consumes the branch; migration content is frozen from 0.89.0.
- Every generated-project contract change is declared once in `data/project_contract.yml` with an
  adoption step id; apply/update/deploy refuse until the operator records adoption.
- Tenant isolation is structural: FORCE RLS on tenant tables, a NOSUPERUSER/NOBYPASSRLS runtime role,
  an eager boot guard, and a restricted-role integration gate.
- `quickscale_core.runtime` is the public module-facing facade; private modules do not import their
  own facade (split-facade gate).

**Quality scenarios.**

| # | Stimulus · conditions | Affected boundary | Required response | Measure / source | Competing quality |
|---|---|---|---|---|---|
| Q1 | A module changes an API subpath or payload while a project is live | module → user-owned theme page | existing project picks it up by apply/update without hand-editing a page | files hand-adopted per project; target unknown (roadmap says steps should trend to zero) | template freedom vs upgradability |
| Q2 | `quickscale update` runs while a module split branch has moved and the process dies between module pulls | split branch → project git/state | project remains buildable and state matches content | recovery time and drift after crash; no declared target | update freshness vs reproducibility |
| Q3 | 0.89 → next release deploys to a running instance | generated production topology | schema and media survive a rolling deploy and can roll back | deploy success and data retention; no SLO/SLA declared | availability vs schema change |
| Q4 | A project-owned tenant model or endpoint ships | generated CI → tenant data | the generated suite catches a missing org filter under the runtime role | isolation regressions caught before deploy; target unknown | starter simplicity vs isolation proof |
| Q5 | A destructive restore is exercised during an incident | backup artifact → PostgreSQL, media, env | one coherent recovery point and a safe retry | RPO/RTO unknown; restore evidence is source-level only | restore completeness vs operational simplicity |
| Q6 | A hard crash occurs after apply checkpoint 4 | apply state / recovery ledger | rerun converges; managed-file drift stays detectable | state fields preserved; no declared target | recovery speed vs state simplicity |

**Boundary map (consequential edges on the selected paths).**

| Component / store | Edge kind | Owner of the invariant | Version / failure assumption |
|---|---|---|---|
| `quickscale_cli apply` → generator emission mapping (143 emitted paths) | call / build | `get_generator_emission_mapping` | template set is source of truth; closed-world test |
| apply → managed files (`settings/modules.py`, `urls_modules.py`, seam `.d.ts`/`.keys.ts`, CI env, operations page, `quickscale_managed/*`) | shared state / hashes | `project_state_hashes.py` + module manifests | 6 paths hash-tracked; 3 module-managed files untracked |
| apply → `.quickscale/state.yml` and `.quickscale/apply-recovery.yml` | shared state | two serializers | independent writes; merge rules differ |
| `quickscale update` → split branch head → `git subtree pull` → `pyproject.toml` | call / VCS | CLI + remote branch | branch is mutable; lockfile not refreshed |
| generated boot → `start.sh` → superuser migrate → runtime role → gunicorn | call / privilege | `start.sh` + runtime settings | migrations at every boot; no pre-deploy/rollback |
| generated request → `ClientIdentityMiddleware` → RLS GUC → module views | call / trust boundary | orgs + runtime settings | RLS only under runtime role; tests bypass |
| `pg_dump` → local/remote artifact + sidecars (media inventory) → restore | shared state / external effect | DR engine | DB-only freeze; media/env live at restore |
| release → split tag/branch + PyPI wheel | build / supply chain | publish/seal scripts | tag is immutable; update reads branch |

**Critical-path walkthrough and lifecycle transition.**

*Apply path.* `quickscale apply` loads `state.yml` and the recovery ledger and merges them, computes
the delta, acquires the project lock, embeds missing modules from tags, snapshots state, regenerates
managed wiring and records six hashes, syncs env/dependencies, runs migrations, then finalizes state.
The failure branch matters more than the happy path: step 4 mutates `managed_files` and checkpoints
the pre-step-4 snapshot; a kill after it resumes at step 5 and finalizes state without hashes (F7).
A kill during step 1 leaves subtree commits and module directories but no checkpoint; a kill during
step 2 aborts without saving the ledger (F7). `update` has no checkpoint at all: it pulls each module
and commits independently, so a kill leaves a mixed set (F2). External effects (subtree commits,
`poetry install`, `migrate`, Docker/Railway) are not reversible; the ledger is the only recovery
record.

*Lifecycle transition.* A 0.89.0 → next-release upgrade stamps 43 version-bearing files, publishes
12 split branches and 12 immutable tags, then an existing project updates from the branch tip,
regenerates managed wiring, and adopts contract steps. Code at N must read state written by N−1:
the desired-state schema stays `"1"`, applied state carries the release version plus per-module
versions, and contract ids union forward. In-flight work: generated project requests during a rolling deploy see `start.sh` migrate
first (F4); in-flight backups are local files with a 300 s stale heuristic (F6); queued work is
external cron, not an in-process queue. Restore is the other lifecycle branch: it reads a database
dump, live media, and live env at different moments (F6). No claim of safe in-flight upgrade or
restore rests on a tested two-version exercise; this is residual risk.

**Measurements** (filter: `--since="12 months ago"`, no merges, commits touching ≤30 files,
excluding `vendor/`, `node_modules/`, `dist/`, `build/`, `htmlcov/`, lockfiles, `CHANGELOG`,
generated caches; synthetic subtree-split replays are ~40% of history and inflate per-file counts).
3,789 non-merge commits in twelve months. Delta since the prior audit: 95 commits, 68 non-merge;
classification: closeout (SA191a–e, SA299e/f, SA300b/c, SA301–SA309, SA277 a3, SA191d re-proof),
housekeeping (roadmap/docs), and **no unlabeled-behavioral commit** — every non-doc change carries
an `SAnnn` subject. Key censuses: twelve modules; 36 split tags (3 releases × 12); `project_contract.yml`
**5 steps at introduction (2026-09-24) → 46 (2026-10-16) → 53 (2026-10-20) → 58 today** with 108
adoption sub-steps; managed outputs 9 (6 hash-tracked, 3 `quickscale_managed/*` untracked); tenant
models 22 enrolled across 6 modules with 20 `TenantModelAdmin` classes; module-contract references
in 5 theme source files plus 2 social templates, including 17 resource-subpath literals in the three
main contract-bearing files; 62 adoption ids per project (58 project + 4 module vintages). Ownership
is heavily concentrated: a single maintainer authored essentially all recent changes; the
load-bearing seams have no second reader.

**Coverage and residual risk.** Read in full: apply executor/ledger/step registry, `_steps.py`,
`_context.py`, `_state.py`, `_finalize.py`, `project_state_*`, `module_wiring.py`, manifest
assembler/loader boundaries, `project_contract.yml`, `_vintage_emission.py`, the update/embed/push
paths, `project_state_hashes.py`, generated settings/Docker/railway/CI/Makefile templates, the
generated test harness, DR capture/restore/lock/metadata paths, orgs tenancy/checks/admin, and the
prior audits. Sampled: all twelve module surfaces (census, not full read), release scripts, billing
and notifications internals. Skipped: full frontend component tree, module migration bodies,
`beta_migration` internals beyond the upgrade-path boundary, and scripts outside the release gates.
Lens activation: `active: I, II, III, IV, V, VI, VII, VIII, IX, X, XI, XII, XIII, XV, XVI, XVII, XVIII, XIX, XX, XXI · inert: XIV (no growing hot path with a structural volume assumption) · archetypes: code generator, CLI, library, plugin host, and the generated service`. Findings produced by I, II, III, IV, V, VII, VIII, XII, XIII, XV, XVI, XVIII, XIX, XX. Out-of-repo and unverified: `bap-web-new`'s actual tree, its Railway configuration, current media usage, and whether its backups engine is used. Runtime confirmation is needed for: crash-window frequency, actual restore drills, and whether any generated project has been deployed via the dev Compose path. The report's silence does not clear those.

## Enforcement census

| Invariant | Where enforced | Kind | Trend since prior pass |
|---|---|---|---|
| Module wiring only in managed files | `test_emission_closed_world.py` over `get_generator_emission_mapping` | gated, closed-world | stable |
| Managed files not hand-edited | `project_state_hashes.py` six paths; `status` drift | structural, incomplete (3 module-managed outputs untracked) | unchanged |
| Contract change carries a new step id | `scripts/check_project_contract_vintage.py` over templates + generator mapping | gated, open-world for runtime/module-managed outputs | unchanged; runtime excluded |
| Project adopted declared steps | operator confirmation; `contract_vintage.py` bulk union | convention | steps 53 → 58 |
| Module version lockstep | manifest assertion + `version_tool.sh` | gated | 40 of 43 version-bearing files checked |
| Embedded module content identity | tag at embed; provenance drift guard at update | gated | stable; update ref is a branch tip |
| Module migrations frozen | migration-content identity in update/restore | gated | stable |
| Tenant RLS on shipped tables | FORCE RLS migrations, boot guard, restricted-role integration gate | structural in modules | 22/22 enrolled |
| Generated-project tenant isolation | catalog conformance only; generated tests run as superuser with bypass | convention | gap |
| Apply state single-writer | `StateManager` + `LedgerManager`, advisory lock | structural but dual-owner | unchanged |
| Apply resume preserves state | `ApplyExecutor` checkpoint + fault harness | gated, content not asserted | gap |
| Production migration safety | `start.sh` boot migration | convention | unchanged |
| Production media durability | docs only; storage module optional | convention | unchanged |
| DR migration identity | module migrations only | gated, project apps excluded | unchanged |
| Tenant removal obligations | app-declared `removal_obligations` | convention (4 of 12 apps declare) | unchanged |
| CLI public/private surface | split-facade gate | gated, one-directional | stable |

## Summary table

| Rank | ID | Title | Horizon | Conf. | Size | Rev. | Problem |
|---|---|---|---|---|---|---|---|
| 1 | `generated-file-ownership-unmodeled` | Module contracts live in user-owned generated files | now | High | M | two-way | Each module API change becomes a manual adoption step recorded by a bulk flag. |
| 2 | `module-upgrade-no-reconciler` | Module update is a mutable multi-commit operation | now | High | M | two-way | Update follows a branch tip and mutates modules without a journal or lockfile refresh. |
| 3 | `contract-vintage-boundary-blind` | Contract gate watches templates, not runtime/managed outputs | now | High | M | two-way | Runtime behavior and module-managed files change existing projects with no step or drift signal. |
| 4 | `generated-deploy-topology-unmodeled` | Generated production topology is prose, not an artifact | now | High | M | two-way | Media is container-local, and schema changes at boot. |
| 5 | `generated-isolation-unverified` | Generated projects never test tenant isolation under the runtime role | now | High | S | two-way | The generated suite bypasses the RLS guarantee it ships. |
| 6 | `backup-restore-incoherent` | Backups cover the database, not a coherent recovery point | 6–18 months | High | L | one-way | Media is live at restore, project schema is excluded, and restore has no lease. |
| 7 | `apply-state-dual-owner` | Apply state has two full owners and a lossy resume snapshot | 6–18 months | High | M | two-way | A crash can persist state without managed-file hashes. |

## Machine-readable index

```yaml
schema: arch-audit/v11
audited: 82ff3e7d141cf943ab900eaae5f214c0edfc9e07
snapshot_basis: "82ff3e7d (v89), clean worktree, no uncommitted or untracked inputs read; only post-snapshot change is this deliverable"
items:
  - {id: generated-file-ownership-unmodeled, status: open, rank: 1,
     title: "Module contracts live in user-owned generated files",
     lenses: [III, V, VII, XIX], horizon: now, confidence: High, size: M,
     reversibility: two-way door, depends_on: [], amplifies: [generated-isolation-unverified],
     anchors: [quickscale_core/src/quickscale_core/project_state_hashes.py,
               quickscale_core/src/quickscale_core/data/project_contract.yml,
               quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/src/pages/CrmPage.tsx],
     first_seen: 2026-07-10, last_verified: 2026-10-23}
  - {id: module-upgrade-no-reconciler, status: open, rank: 2,
     title: "Module update is a mutable multi-commit operation",
     lenses: [IV, VII, X, XIX], horizon: now, confidence: High, size: M,
     reversibility: two-way door, depends_on: [apply-state-dual-owner], amplifies: [contract-vintage-boundary-blind],
     anchors: [quickscale_cli/src/quickscale_cli/commands/_module_update.py,
               quickscale_cli/src/quickscale_cli/commands/_module_embed.py,
               quickscale_core/src/quickscale_core/utils/git_repo.py],
     first_seen: 2026-10-23, last_verified: 2026-10-23}
  - {id: contract-vintage-boundary-blind, status: open, rank: 3,
     title: "Contract gate watches templates, not runtime/managed outputs",
     lenses: [V, VII, XII, XV], horizon: now, confidence: High, size: M,
     reversibility: two-way door, depends_on: [], amplifies: [generated-file-ownership-unmodeled],
     anchors: [scripts/_vintage_emission.py,
               scripts/check_project_contract_vintage.py,
               quickscale_core/src/quickscale_core/project_state_hashes.py,
               quickscale_core/src/quickscale_core/module_wiring.py],
     first_seen: 2026-10-23, last_verified: 2026-10-23}
  - {id: generated-deploy-topology-unmodeled, status: open, rank: 4,
     title: "Generated production topology is prose, not an artifact",
     lenses: [IV, VI, XVI, XIX], horizon: now, confidence: High, size: M,
     reversibility: two-way door, depends_on: [], amplifies: [backup-restore-incoherent],
     anchors: [quickscale_core/src/quickscale_core/generator/templates/README.md.j2,
               quickscale_core/src/quickscale_core/generator/templates/docker-compose.yml.j2,
               quickscale_core/src/quickscale_core/generator/templates/start.sh.j2,
               quickscale_core/src/quickscale_core/generator/templates/project_name/settings/base.py.j2],
     first_seen: 2026-10-23, last_verified: 2026-10-23}
  - {id: generated-isolation-unverified, status: open, rank: 5,
     title: "Generated projects never test tenant isolation under the runtime role",
     lenses: [II, VIII, XV, XVIII], horizon: now, confidence: High, size: S,
     reversibility: two-way door, depends_on: [], amplifies: [],
     anchors: [quickscale_core/src/quickscale_core/generator/templates/Makefile.j2,
               quickscale_core/src/quickscale_core/generator/templates/github/workflows/ci.yml.j2,
               quickscale_core/src/quickscale_core/runtime/settings.py,
               quickscale_modules/orgs/src/quickscale_modules_orgs/checks.py],
     first_seen: 2026-10-23, last_verified: 2026-10-23}
  - {id: backup-restore-incoherent, status: open, rank: 6,
     title: "Backups cover the database, not a coherent recovery point",
     lenses: [I, IV, XVI, XVIII], horizon: 6-18 months, confidence: High, size: L,
     reversibility: one-way door, depends_on: [], amplifies: [],
     anchors: [quickscale_core/src/quickscale_core/dr_engine/_capture.py,
               quickscale_core/src/quickscale_core/dr_engine/_sidecar.py,
               quickscale_core/src/quickscale_core/dr_engine/_media.py,
               quickscale_core/src/quickscale_core/dr_engine/_metadata.py],
     first_seen: 2026-10-23, last_verified: 2026-10-23}
  - {id: apply-state-dual-owner, status: open, rank: 7,
     title: "Apply state has two full owners and a lossy resume snapshot",
     lenses: [I, IV, X], horizon: 6-18 months, confidence: High, size: M,
     reversibility: two-way door, depends_on: [], amplifies: [module-upgrade-no-reconciler],
     anchors: [quickscale_cli/src/quickscale_cli/commands/_context.py,
               quickscale_cli/src/quickscale_cli/commands/_state.py,
               quickscale_core/src/quickscale_core/apply/executor.py,
               quickscale_cli/src/quickscale_cli/commands/_steps.py],
     first_seen: 2026-10-23, last_verified: 2026-10-23}
  - {id: core-holds-module-vocabulary, status: watchlist}
  - {id: manifest-dsl-vocabulary-growth, status: watchlist}
  - {id: session-advisory-lock-pooling, status: watchlist}
  - {id: modules-english-only, status: watchlist}
  - {id: two-filesystem-lock-implementations, status: watchlist}
  - {id: ci-provisioning-hand-pins, status: watchlist}
  - {id: trigger-inputs-legacy-name, status: watchlist}
  - {id: subscription-status-single-writer, status: watchlist}
  - {id: release-gate-version-blind, status: watchlist}
  - {id: cli-headless-gap, status: watchlist}
  - {id: node-pin-duplication, status: watchlist}
  - {id: tenant-removal-coverage, status: watchlist}
  - {id: admin-tenant-authority, status: watchlist}
  - {id: seam-unversioned, status: watchlist}
```

## Ranked findings

### Finding 1: Module contracts live in user-owned generated files

- **ID:** `generated-file-ownership-unmodeled`
- **Rank rationale:** High × High, steep. It crosses the generator ↔ project ownership boundary;
  every module API change after 0.89 either mints an adoption step or silently breaks a page; SA153
  is the next work item and adds exactly this surface; declared steps went 53 → 58 in three days.
- **Horizon & trigger:** `now` — the next module endpoint change, or SA153 (j) coupling a
  project-owned page to a module resource.
- **Confidence:** High — mechanism read, theme census counted, gates read, no enforcing layer found.
- **Context dependence:** `wrong-for-now` (dimension: count of live generated projects). Lives in
  deployment reality (B); with one project, regeneration (SA299 style) is a valid containment.
- **Problem:** The generated project has only a two-valued ownership model (regenerated or
  user-owned), but module resource paths and payload types still live in user-owned theme files, so
  each module/template change becomes a hand-adopted contract step recorded by a bulk flag.
- **Evidence:**
  - Managed boundary: `project_state_hashes.py:40-67` declares six hash-tracked paths; `_state.py:56-61`
    explicitly excludes `<package>/quickscale_managed/*` "because they are owned by individual
    modules"; `module_wiring.py:526-549` deletes and rewrites that directory wholesale.
  - Theme census: `pages/CrmPage.tsx:16,36-57` (`stats/`, `contacts/`, `companies/`, `deals/`,
    `tags/`), `hooks/useOrgs.ts:159-265` (eight membership/invitation/settings paths),
    `hooks/usePublicSocialSurface.ts:73-81` (`/_quickscale/social/`, `/embeds/`), plus
    `components/forms/FormRenderer.tsx:113` and `hooks/useFormSchema.ts:61-64`. Five theme source
    files plus two emitted social templates carry module paths/types; the three main files carry
    17 resource-subpath literals and four files declare 29 payload types.
  - `test_emission_closed_world.py:489` / `:540-550` permits "a single module reference"; it
    forbids enumerations, not resource subpaths or payload shapes.
  - Contract steps: `project_contract.yml` has **58 step ids** and 108 adoption sub-steps; growth
    5 → 46 → 53 → 58 since 2026-09-24. The five newest steps are all manual user-owned-file changes.
  - Adoption: `contract_vintage.py:239-295` records every declared id by union, with no check that
    the user-owned file changed; `deployment_commands.py:118-127` records adoption on a clean-tree
    check alone, without regenerating or pulling anything.
  - Fix-regression audit: SA289 moved API **bases** into the seam (`runtime/seam.py:7-10,344,392`)
    but left resource subpaths and types in pages; `test_emission_closed_world` still allows one
    reference. SA277 a3 only versions the handoff prompt. SA153 (j) has not landed. **Relocated,
    not removed.**
- **Counter-evidence:** searched for a generated managed-hooks file (`quickscaleSeam.hooks.*`), a
  detector for module subpaths/payload types in user-owned files, and any adoption verification
  against file content. Found none. The closed-world test and contract-vintage gate are real, but
  their scope stops at enumerations and template *wiring*; the managed-file hash set is six paths.
  SA153's roadmap line already assigns the managed-hook boundary to this finding.
- **Why it compounds:** growth variable = **declared adoption steps × live projects**. Each module
  resource or payload change adds a step (steps are monotonic; the roadmap's stated target is
  "toward zero"); each live project must adopt every step by hand. Built on top: the contract-vintage
  gate in `apply`, `update`, and `deploy railway`, SA299's beta migration, and SA277's two-stage
  prompt. A second live project doubles the operator cost and makes "regenerate and diff" no longer
  sufficient.
- **Detection signal:** step count per release (58 today; five added since the prior audit); any
  `apply`/`update`/`deploy` refusal naming outstanding steps; user-owned theme diffs after a module
  update; a module endpoint rename producing a page 404.
- **Steelman:** user-owned pages are the theme's customization point; routing every module call
  through generated hooks constrains designers. With exactly one live project, SA299-style
  regeneration is cheaper than a seam, and the contract steps keep the operator aware. This holds
  while there is one project and it is regenerated per release. A second project, or a template
  security fix that must reach an existing project, revokes it.
- **Correct shape:** a module's resource paths and payload types reach a user-owned file only through
  a generated, regenerated module (managed hooks/types); user-owned files hold presentation.
  Adoption is verified against the file's actual content/hash, not a bulk flag.
- **Do-nothing cost:** every module API change after 0.89 becomes a new step adopted by hand in each
  project; operator time grows roughly linearly with steps × projects, and one missed step becomes a
  runtime 404 or a silently stale payload.
- **Options:**
  1. **Managed module hooks.** Generate `quickscaleSeam.hooks.ts` plus payload types per installed
     module from its manifest; pages import it. M, two-way, incremental per module; removes the
     mechanism. Spends template freedom.
  2. **Extend the closed-world test** to reject module subpaths/payload types in user-owned files,
     forcing option 1 as SA153 adds pages. S, two-way, guard only; alone it blocks without providing
     the seam.
  3. **Accept and document** regenerate-per-release (SA299/SA277 style). Containment: a step-count
     tripwire and a second-project trigger. Revocation: a second long-lived project or a template
     security fix.
- **Recommendation:** option 1 with option 2 as its guard. **Size:** M · **Reversibility:** two-way
  door · **Guard:** a closed-world check over the emission mapping that fails when a user-owned file
  names a module resource subpath or payload type (with a control case that the managed hook passes).
  **Acceptance check:** changing a module endpoint subpath produces no new `project_contract.yml`
  step and no user-owned diff; the page imports the regenerated hook. Source-checkable through the
  emission mapping. **First step:** move `CrmPage.tsx`'s section paths and `CrmStats` type into a
  generated `quickscaleSeam.hooks.crm` file.
- **Remaining delivery ownership:** SA277 (Track 3) owns the two-stage upgrade rule; it does not
  remove resource contracts from user-owned pages. SA153 (j, Track 1) owns the portal's
  managed-hook boundary. Completing either alone is not closure.

### Finding 2: Module update is a mutable multi-commit operation

- **ID:** `module-upgrade-no-reconciler`
- **Rank rationale:** High × High, steep. Every release and every project executes this path; twelve
  modules mean at least twelve state writes per update; SA308 already forces dependency-floor
  refreshes. A branch move or an interrupted update is unreconcilable without git surgery.
- **Horizon & trigger:** `now` — the next `quickscale update`, especially after a split branch has
  moved independently of its sealed tag.
- **Confidence:** High — the tag/branch asymmetry, per-module commits, missing lock refresh, and
  absent journal were read end to end.
- **Context dependence:** `wrong-for-now` (dimension: project count and release cadence). Lives in
  realities (A) and (B).
- **Problem:** Embed pins an immutable split tag, but update resolves the mutable split-branch tip;
  it then mutates N modules and state in separate commits with no journal and does not refresh
  `poetry.lock`, so a crash or branch move leaves a half-updated project that the next command
  cannot reconcile.
- **Evidence:**
  - Embed: `_module_embed.py:323-343` selects `splits/<module>/<version>`, checks the tag exists, and
    peels it. Update: `_module_update.py:312` calls `resolve_remote_ref`; `git_repo.py:104-105` runs
    `git ls-remote --heads`. No tag check exists in the update path.
  - Per-module mutation: `_module_update.py:528-541` stops on the first failure; each module is
    committed independently (`_module_update_io.py:449-498`); rollback only runs in the handled
    exception path and warns if it fails (`_module_update.py:644-657`). There is no update journal;
    the only ledger reference is a read-only apply-recovery guard (`_module_update.py:84-107`).
  - State is loaded before the lock (`_module_update.py:748-768`), then `_run_update_under_lock`
    acquires it (`:604-614`); a concurrent state change between read and lock is possible.
  - Dependency graph: update repins `pyproject.toml` (`_module_update.py:402-419`) but never runs
    `poetry lock`/`poetry install` (embed does, `_module_embed.py:430-468`). The update snapshot
    includes module tree, config, state, and pyproject, but not `poetry.lock`
    (`_module_update_io.py:100-105`), so rollback cannot restore it.
  - Legacy copy: `_sync_state_module_version` writes `state.yml` and refreshes `embedded_at` every
    run (`_module_shared.py:255-281`); `config.update_module_version` has no non-test caller, so
    `.quickscale/config.yml` never follows.
- **Counter-evidence:** embed is genuinely tag-pinned; the provenance guard detects local edits; the
  migration-content freeze refuses rewritten migrations; maintainer split publication is hardened
  with lease/fast-forward/tree identity. Searched for a tag check in update, an update journal, a
  `poetry lock` call, and a non-test `update_module_version` caller — found none. Rollback is real
  for handled exceptions; it is not a crash recovery mechanism.
- **Why it compounds:** growth variable = **live projects × installed modules × releases**. Every
  update produces N commits and N state writes; each new module adds a pull, a dependency rewrite,
  and a legacy-config copy. Update reads a mutable branch, so `(version, commit_sha)` is not a
  content identity; a moved branch makes two projects with the same recorded version run different
  code. A crash between pulls leaves a mixed module set; a missing lock refresh can leave the next
  generated Docker/CI `poetry install` inconsistent.
- **Detection signal:** `poetry install` failing in Docker/CI after a successful update; `quickscale
  status` reporting local edits immediately after an update; a project needing `git reset` after an
  interrupted update; two projects with the same module version producing different page behavior.
- **Steelman:** update-from-latest is deliberate (`user_manual.md` describes update from the split
  branch); per-module rollback covers handled failures; a single project can be re-applied or
  regenerated. Holds while branches move only at releases, `apply` is always run after `update`, and
  updates never crash mid-set. The branch tip is still not proven equal to the sealed tag, and the
  lock is still not refreshed.
- **Correct shape:** an update is a transaction over a module **set** whose content identity is
  immutable and recorded; one journal/checkpoint, one state write, a refreshed lock, and rollback
  on failure.
- **Do-nothing cost:** every release, each project update carries a manual recovery risk; a single
  interrupted update costs a git rescue; a stale lockfile can break deployments until someone runs
  `poetry lock`; a branch move silently changes content under a fixed version label.
- **Options:**
  1. **Sealed-tag update + journal.** Resolve the tag for the runtime core version, write an update
     journal/checkpoint, refresh the lock, and commit the module set once. M, two-way door; removes
     the mechanism.
  2. **Keep branch tracking, prove it.** Refuse unless the branch tip tree equals the sealed tag,
     refresh `poetry.lock`, and add the journal. S/M, two-way; removes the content-identity gap but
     keeps branch as transport.
  3. **Accept and document.** Keep branch tracking, document recovery, and require `apply` after
     update. Containment: a status warning when the branch tip differs from the tag. Revocation: a
     second live project.
- **Recommendation:** option 1 with option 2 as the transition guard. **Size:** M · **Reversibility:**
  two-way door · **Guard:** a release gate that asserts the split branch tip and the sealed tag share
  a tree, plus an update test that kills the process between pulls and asserts convergence.
  **Acceptance check:** after an update, `poetry.lock` is consistent, state matches installed content,
  and a kill between modules resumes to one coherent set. **First step:** make update resolve and
  verify the sealed tag before the first pull.

### Finding 3: Contract gate watches templates, not runtime or module-managed outputs

- **ID:** `contract-vintage-boundary-blind`
- **Rank rationale:** High × Medium, steep. Existing projects can change behavior through a core
  patch with no adoption step; the architecture is deliberately moving contracts into
  `quickscale_core.runtime` (SA206/SA258/SA286/SA289), so the blind spot grows with each move.
  SA288 already exercised it.
- **Horizon & trigger:** `now` — the next runtime behavior change; SA153's managed hooks will add
  more runtime-side contract surface.
- **Confidence:** High — the watched set and the SA288 precedent were read.
- **Context dependence:** `wrong-regardless` for a contract gate; impact scales with core patch
  cadence. Lives in reality (B).
- **Problem:** The generator's contract-change gate derives its watched set from templates and the
  generator package only; `quickscale_core.runtime` and `<package>/quickscale_managed/*` are outside
  it, so behavior and file changes reach existing projects with no adoption step and no drift signal.
- **Evidence:**
  - `_vintage_emission.py:32-34` defines `TEMPLATE_ROOT`, `GENERATOR_PACKAGE_ROOT`, and `PACKAGE_ROOT`;
    `check_project_contract_vintage.py:412-413` requires `template_paths or mapping_changed`.
    `_generator_paths` matches only the generator package, not `runtime/`.
  - Precedent: `936b8d0b` changed `runtime/settings.py` to make composed DRF defaults JSON-only
    (`DEFAULT_RENDERER_CLASSES`/`DEFAULT_PARSER_CLASSES`) and added no `project_contract.yml` step.
  - Managed outputs: `project_state_hashes.py:40-67` tracks six paths; `_state.py:56-61` explicitly
    excludes `quickscale_managed/*`; `module_wiring.py:526-549` deletes and rewrites it; social
    declares three files (`quickscale_modules/social/module.yml:164-175`). Today 3 of 9 managed
    outputs are untracked.
  - `test_emission_closed_world.py` derives its scan scope from the emission mapping, which is the
    right closed-world model but contains no runtime module.
- **Counter-evidence:** the module-manifest vintage gate does reject a changed step text without a
  new id; the template-side gate is genuinely derived, not hand-listed; runtime has its own tests and
  a minor-range pin. Searched for `runtime` in `_vintage_emission.py`/`check_project_contract_vintage.py`
  and for a derivation of the managed path set from the emission mapping or manifests — found none.
  The only tie is an exact-tuple test for the four project paths
  (`test_generator.py:1056-1072`), which does not require coverage.
- **Why it compounds:** growth variable = **runtime public surface + module-managed outputs**. As
  more contracts move from templates into the runtime facade, the percentage of contract-bearing
  changes the gate can see falls. Each new module-managed file is another untracked output; each
  runtime behavior change ships silently into every existing project. Existing projects cannot
  enumerate which runtime behaviors they adopted.
- **Detection signal:** a core patch changes a generated project's API/renderer/URL behavior with no
  `apply`/`update` warning; a user edits a `quickscale_managed` file and `status` reports no drift,
  then `apply` overwrites it; a contract step list that grows while runtime changes do not.
- **Steelman:** runtime changes are semver-patch library behavior and are intended to roll out
  automatically; contract steps are for manual user-owned edits, not library upgrades. The core pin
  is minor-range and the runtime is tested. This holds while runtime changes remain backward
  compatible. SA288's JSON-only parser is a counterexample: a client sending form-encoded data
  starts receiving 415 with no step.
- **Correct shape:** the contract boundary is derived from the emission mapping **and** the runtime
  public surface; every generated managed output is hashed or explicitly declared unmanaged; a
  contract change cannot ship without a step.
- **Do-nothing cost:** silent behavior changes in every generated project; support burden without an
  adoption record; a growing gap between "what the version pin says" and "what the project runs."
- **Options:**
  1. **Derive the watched set** from the emission mapping plus `quickscale_core.runtime`'s public
     modules, and hash all generated `quickscale_managed` outputs. M, two-way; removes the mechanism.
  2. **Treat runtime as a semantic-versioned library** with a deprecation policy; require a step only
     for breaking runtime changes and gate it with a compatibility test. S/M, two-way; lighter, but
     depends on classifying "breaking" correctly.
  3. **Accept** and rely on the core pin/tests. Containment: a release note per runtime behavior
     change. Revocation: the first runtime-caused production regression.
- **Recommendation:** option 1, with option 2 as the policy for what counts as a step. **Size:** M ·
  **Reversibility:** two-way door · **Guard:** the existing vintage gate extended to the runtime
  public surface and to every `quickscale_managed` output, plus a control case that an ordinary
  internal refactor passes. **Acceptance check:** a change like `936b8d0b` fails without a step; a
  local edit under `quickscale_managed/` is reported by `status`. **First step:** add the runtime
  public module list to `_vintage_emission.py` and derive the managed output set from the manifests.

### Finding 4: Generated production topology is prose, not an artifact

- **ID:** `generated-deploy-topology-unmodeled`
- **Rank rationale:** High × Medium, steep. The generated README previously told users to run a dev
  stack as production (since corrected); the default media backend is container-local while
  blog/listings can store user files; every deploy runs schema changes at boot. SA191d makes
  production live now; the cost is paid on the first self-hosted deploy or media upload.
- **Horizon & trigger:** `now` — SA191d production cutover, the first self-hosted production deploy,
  or the first media-bearing feature in a project without the storage module.
- **Confidence:** High — templates read in full; no production profile, volume, or pre-deploy hook
  exists.
- **Context dependence:** `wrong-for-now` (dimensions: production use, self-hosting, replicas,
  media volume). Lives in reality (B); Railway single-instance with external storage is the
  documented mitigation.
- **Problem:** The generated project has no production deployment artifact distinct from its dev
  stack, and production media defaults to container-local storage, while migrations run at every
  boot with no pre-deploy or rollback contract.
- **Evidence:**
  - `README.md.j2:338-346` then said the included `Dockerfile` and `docker-compose.yml` were "ready
    for production use" (since corrected: the template now labels Compose as local development);
    the Compose file sets `INSTALL_DEV: "true"`, runs `python manage.py runserver`, uses
    `settings.local`, binds the source tree, and runs as host UID
    (`docker-compose.yml.j2:70,78,80-86`). `local.py.j2:24,118` forces `DEBUG=True` and wildcard
    hosts.
  - Boot migrations: `start.sh.j2:103-120` runs `migrate` and `createcachetable` on every boot;
    `railway.json.j2:7-12` makes `start.sh` the `startCommand` with a 100 s healthcheck and no
    pre-deploy/rollback step.
  - Media: `base.py.j2:214-225` defaults to `FileSystemStorage` under `BASE_DIR/media`; media is
    served only under `DEBUG` (`urls.py.j2:54-56`); the generated Railway config declares no volume
    (`railway-operations.md:102-110` warns, but no startup check refuses local media). Blog and
    listings now require `storage` (`blog/module.yml:80-82`, `listings/module.yml:40-42`), but
    storage's default backend is `local` (`storage/module.yml:13-17`), so a project can satisfy the
    dependency and still write uploads to container-local storage; `blog/checks.py` only requires a
    non-empty `MEDIA_URL`.
  - The healthcheck is DB-free (`urls.py.j2:31-37`), so it is liveness, not readiness.
- **Counter-evidence:** production settings fail closed on the shipped `SECRET_KEY`, `ALLOWED_HOSTS`,
  secure cookies, HSTS, and proxy trust; the database role split is sound; Railway is the documented
  production path; the operations doc explicitly warns against container media. Searched for a
  production Compose/profile, a pre-deploy migration, a persistent volume in the generated deploy
  config, and a startup check that refuses local storage in production — found none. Compose does
  mount a media volume, but only for the dev stack.
- **Why it compounds:** growth variable = **generated projects × deploy events × media-bearing
  features**. Every new upload field inherits the loss path; every deployment inherits boot-time
  schema mutation; every additional replica makes migration races and partial rollbacks more likely.
  The cost is not paid until a real deploy, so it accumulates silently.
- **Detection signal:** uploaded files disappearing after a redeploy; `docker compose up` exposing
  Django's dev server with `DEBUG=True`; a deploy rollback leaving the schema ahead of the old image;
  migration lock contention across replicas; `/media/...` returning the SPA HTML.
- **Steelman:** Railway is the only supported production path, and Compose is a local-dev
  convenience; media is expected to use the storage module; single-instance boot migrations are a
  common small-SaaS trade-off. That holds while every project uses Railway, one replica, and S3. The
  former README production claim (now corrected) and the default local backend contradicted it for
  anyone who followed the generated instructions.
- **Correct shape:** one generated production deployment contract — a production Compose/profile or
  a documented platform path with pre-deploy migrations, persistent or object media, separate
  readiness/liveness, and a rollback story.
- **Do-nothing cost:** a self-hosted user gets an insecure dev server; every media-bearing project
  risks data loss on redeploy; every schema change is a stop-the-world bet with no rollback; the
  first incident is diagnosed from prose rather than an artifact.
- **Options:**
  1. **Production Compose/profile** with gunicorn/production settings, a one-shot migrate job, a
     media volume or required S3, and readiness. M, two-way; removes the artifact gap.
  2. **Make Railway the only supported production path**, keep the Compose file documented as local
     development, and add a startup check that refuses local media in production. S, two-way;
     cheaper, but narrows self-hosting.
  3. **Accept and document** with an operator checklist and a media warning. Containment: a deploy
     preflight. Revocation: first self-hosted deployment or first media loss.
- **Recommendation:** option 1 if self-hosting is supported; option 2 if Railway-only is the
  intended product. **Size:** M · **Reversibility:** two-way door · **Guard:** a generated deployment
  test that boots production settings and asserts the media backend is not `FileSystemStorage` unless
  an explicit dev flag is set. **Acceptance check:** `docker compose -f production.yml up` runs
  gunicorn with `DEBUG=False`, one migrate job, and uploaded files survive a redeploy. **First step:**
  split the Compose file into a dev and a production service definition.

### Finding 5: Generated projects never test tenant isolation under the runtime role

- **ID:** `generated-isolation-unverified`
- **Rank rationale:** High × Medium, steep. The generated harness bypasses the RLS guarantee it
  ships; SA153 adds the first project-owned tenant models and endpoints, which no module suite
  covers. A missed org filter then passes the project's own tests.
- **Horizon & trigger:** `now` — SA153's project-owned extension, or the first generated project that
  adds its own tenant model.
- **Confidence:** High — Makefile, CI, pytest plugin, runtime settings, and the orgs guard were read.
- **Context dependence:** `wrong-for-now` (dimensions: project-owned tenant models, compliance). Lives
  in reality (B).
- **Problem:** The generated test and CI harness runs tenant paths with
  `QUICKSCALE_ALLOW_BYPASSRLS=1` and the superuser URL, so no generated project exercises FORCE RLS
  or its own tenant scoping.
- **Evidence:**
  - `Makefile.j2:49-50` prefixes `pytest` with `QUICKSCALE_ALLOW_BYPASSRLS=1` whenever `orgs` is
    selected (or no module list is supplied). `ci.yml.j2:102-128` runs tests, migrations, and the
    tenant-isolation conformance check with `DATABASE_URL=postgres://postgres@localhost/postgres`
    and the bypass flag.
  - `pytest_plugin.py:43-50` *runs* every `bypass_rls`-marked test when the flag is `"1"`; the
    generated default is exactly `"1"`. The generated suite has no test that connects as the
    restricted runtime role.
  - `runtime/settings.py:422-431` accepts the same flag in serving when `RUNTIME_DATABASE_URL` is
    blank; `orgs/checks.py:193-196` returns `[]` for the boot guard under the same flag. A leaked
    test setting plus a blank runtime URL silently bridges serving to the superuser URL.
  - The repository's own gate is the counter-model: decisions `:433-443` require the integration
    gate to run against `NOBYPASSRLS NOSUPERUSER`; the generated harness is the only one that does
    not.
- **Counter-evidence:** the shipped modules have strong isolation coverage in the repo (22/22 tenant
  tables, composite FKs, RLS boundary suites, conformance command); the generated boot guard fails
  closed when the runtime URL is absent and the flag is unset; the flag is documented as
  non-serving. Searched for a generated `RUNTIME_DATABASE_URL` CI job, a generated tenant isolation
  test, and a production check rejecting the flag — found none. The CI conformance command is a
  catalog check under the superuser, not a behavioral isolation test.
- **Why it compounds:** growth variable = **project-owned tenant models × endpoints**. Each new
  project-owned table or query adds isolation surface the generated suite cannot see. The product's
  extension contract encourages such models (SA153). A regression passes CI and is caught, if at
  all, only by production RLS — which the same flag can disable.
- **Detection signal:** a project-owned view missing an org filter passes `make test`; a tenant
  cross-read appears only in production; an operator reports that the generated security test
  "passes" while RLS is disabled.
- **Steelman:** generated tests are a starter, not a compliance suite; the shipped modules carry
  their own isolation proofs; project owners are expected to write app tests. That holds while
  projects use only shipped modules and never enable the bypass in serving. SA153 breaks the first
  condition; a leaked env breaks the second.
- **Correct shape:** the generated CI/test path connects as the restricted runtime role for at least
  one tenant-isolation suite; production refuses the bypass; project-owned tenant models are enrolled
  in the same conformance check.
- **Do-nothing cost:** every project-owned tenant feature ships without a structural isolation
  check; one missed filter becomes a cross-tenant leak that the suite calls green.
- **Options:**
  1. **Generated isolation target**: a second CI job with `RUNTIME_DATABASE_URL` as a NOBYPASSRLS
     role, plus a tenant-isolation test template that creates two orgs and asserts a 404/403. S/M,
     two-way; removes the gap.
  2. **Generate the conformance check only**; keep the unit suite superuser. S, two-way; verifies the
     catalog but not behavior.
  3. **Accept and document**; revocation trigger: the first project-owned tenant model.
- **Recommendation:** option 1. **Size:** S · **Reversibility:** two-way door · **Guard:** the
  generated CI job fails if the runtime role is absent or the test is skipped; a production check
  rejects `QUICKSCALE_ALLOW_BYPASSRLS=1` while serving. **Acceptance check:** deleting an org filter
  from a sample project-owned view fails the generated isolation suite. **First step:** add the
  restricted-role CI job and the two-org test template.

### Finding 6: Backups cover the database, not a coherent recovery point

- **ID:** `backup-restore-incoherent`
- **Rank rationale:** High × Medium, steep. The backup is the disaster path; media is read live at
  restore, project-app migrations are excluded from identity, and restore has no lease. SA153 adds
  the first project-owned schema, which makes the exclusion load-bearing.
- **Horizon & trigger:** `6–18 months` — the first restore drill of a project with project-owned
  migrations or media, or an incident restore.
- **Confidence:** High on the mechanism and the exclusions; runtime behavior of a real restore was
  not exercised.
- **Context dependence:** `wrong-for-now` (dimensions: project-owned schema, media volume, disaster
  recovery obligation). Lives in reality (B).
- **Problem:** A backup freezes only PostgreSQL; media is inventoried but read live at restore,
  project-app migrations are excluded from identity, and restore has no lease or rollback, so
  recovery is not a coherent point in time.
- **Evidence:**
  - Capture: `_capture.py:142` captures sidecars *after* the dump; `_sidecar.py:158-170` records a
    media inventory (paths, sizes, checksums) but copies no media bytes. Restore reads live source
    media at execute time (`_media.py:226`) and the DB restore receives no target settings
    (`_dr_adapter.py:157`), so the DB uses the local `connections["default"]` (`_restore.py:139`)
    while media/env use route variables.
  - Restore safety: `primitives.py:350-356` runs `pg_restore --clean --if-exists` with no
    `--single-transaction`; there is no restore lock, maintenance mode, or pre-restore dump. The
    backup lock is a 300 s mtime heuristic (`_lock.py:154-157`); the `flock` is released at
    acquisition, so a long backup can be declared stale by a second process. The admin `RESTORING`
    CAS is only on the admin dispatch path; CLI/management-command restores bypass it.
  - Identity/version: `_metadata.py:68` hashes only apps whose name starts with
    `quickscale_modules_`; project apps are excluded. `manifest_version: 1` is written in five
    places but never read. `app_version`, `django_version`, and `module_versions` are recorded but
    not compared at restore (`_metadata.py:139-150`, `recovery.py:325`).
  - Retention/placement: the default is `target_mode: local`, `.quickscale/backups` under
    `BASE_DIR` (`backups/module.yml:30-38`); the catalog is rows in the database being dumped;
    `automation_enabled` is metadata only (`models.py:64`); prune marks rows deleted rather than
    removing them (`_prune.py:111`). One credential pair per policy (`_remote.py:44`).
- **Counter-evidence:** the database is the system of record; the docs explicitly separate database
  restore, media sync, and env sync (`railway-operations.md:92-95`); module migration identity is
  enforced and fails closed; restore is gated by exact filename confirmation and an environment
  flag; remote streaming is bounded. Searched for a restore lease, a single-transaction restore, a
  project-app migration hash, a reader of `manifest_version`, and media capture — found none. The
  media sync command is a separate surface, not a consistency mechanism.
- **Why it compounds:** growth variable = **data stores × projects**. Every new module table,
  project-owned app, and media-bearing feature adds a surface the snapshot does not freeze or
  validate. Project-owned migrations are already on the roadmap (SA153), so the restore check will
  keep passing while the schema moves. A backup set that is not coherent becomes less coherent with
  each release.
- **Detection signal:** a restore completes but media URLs 404; a project table is missing columns
  after restore; two operators restore concurrently; a newer engine restores an older artifact
  silently; prune deletes a file still referenced by a rollback pin or an in-flight restore.
- **Steelman:** PostgreSQL is the only system of record; media is expected in external object
  storage with its own backup; project-owned schema is the user's responsibility; restore is a
  deliberate, gated, last-resort operation. That holds while no project-owned schema exists and
  media is externally backed up. The live project already has a project-owned app and the roadmap
  adds migrations, so the first condition is ending.
- **Correct shape:** a backup defines a coherent recovery point across the database, media, and
  project schema, with a format version and a restore lease — or it explicitly declares itself
  DB-only and refuses to be called disaster recovery.
- **Do-nothing cost:** the first real restore drill fails on media or project schema, discovered
  during an incident; retention and catalog loss can orphan artifacts; each new store widens the
  untested surface.
- **Options:**
  1. **Close the recovery point**: capture media (or record an immutable media manifest with
     object-store versions), hash project-app migrations, version the manifest and read it at
     restore, and add a restore advisory lock. M/L, one-way for the artifact format; removes the
     incoherence.
  2. **Declare DB-only**: rename/label the feature, require a separate media/project backup in the
     runbook, and add a preflight that reports uncovered surfaces. S/M, two-way; honest but does not
     recover.
  3. **Accept** with a documented restore drill. Containment: a restore checklist naming media and
     project migrations. Revocation: the first restore of a project-owned schema.
- **Recommendation:** option 1 for the module; option 2 for immediate release notes if the format
  work cannot land this cycle. **Size:** L · **Reversibility:** one-way door (artifact format) ·
  **Guard:** the restore check refuses an artifact whose manifest version is unknown or whose
  project-app migration hashes do not match. **Acceptance check:** a restore of a DB+media+project
  schema drill produces the captured file set and schema; killing restore mid-way leaves no
  partially restored database (or a documented resumable state). **First step:** include
  project-app migration hashes and a manifest version check before touching media.

### Finding 7: Apply state has two full owners and a lossy resume snapshot

- **ID:** `apply-state-dual-owner`
- **Rank rationale:** Medium × Medium, linear-to-steep. The state is the generator's contract with
  the project; every new state field and every apply step widens the merge surface, and a crash
  after hash capture silently disables drift detection.
- **Horizon & trigger:** `6–18 months` — a hard crash after apply checkpoint 4, or the first observed
  managed-file drift miss.
- **Confidence:** High on the code path; production frequency is inferred (no crash telemetry).
- **Context dependence:** `wrong-regardless` for the state-ownership design; likelihood scales with
  apply failure frequency. Lives in realities (A) and (B).
- **Problem:** Applied state has two full owners; the recovery ledger carries a pre-hash snapshot and
  apply merges the two field-asymmetrically, so an interrupted apply can persist state without
  managed-file hashes.
- **Evidence:**
  - `_context.py:250-266` loads `state.yml` and `apply-recovery.yml`, then
    `_merge_apply_recovery_state` overlays only `last_applied` and modules (`_state.py:299-314`);
    `state.yml`'s `managed_files` and contract steps come from one side, modules from the other.
  - `ApplyExecutor.checkpoint_step` carries `existing.applied_state` forward unless a snapshot is
    passed (`executor.py:270-287`). Step 4 mutates the in-memory state's `managed_files`
    (`_state.py:128-131`) and then checkpoints without passing it (`_steps.py:313-325`), so the
    ledger keeps the pre-step-4 snapshot.
  - On resume, `_resume_post_embed_state` returns the ledger's snapshot when step 2 is skipped
    (`_steps.py:253-255`); steps 3–4 are skipped by the checkpoint; finalization saves that snapshot
    (`_finalize.py:363-371`). A crash after step 4 therefore writes a state with no managed-file
    hashes.
  - The legacy reconciliation documented at `_state.py:74-77` references
    `_sync_legacy_module_config_versions`, which has no definition anywhere; `config.yml` is written
    non-atomically (`module_config.py:184-194`) and its version is never updated (no non-test caller).
- **Counter-evidence:** both serializers write atomically (tmp + replace); loaders fail hard on
  malformed input; the fault-injection harness covers step boundaries; tests round-trip modules
  through the ledger. Searched for an equality/reconciliation function, a resume test asserting
  `managed_files`, and a definition of the named legacy sync — found none. The harness uses no-op
  callbacks and does not assert state content.
- **Why it compounds:** growth variable = **state fields × apply steps**. Each new field (provenance,
  contract steps, managed files) must be threaded through both serializers and the merge; the
  resume path already drops one. The managed-file hashes are what make drift detection possible;
  losing them makes the next apply silently overwrite user edits. A second project doubles the
  number of states exposed to the same path.
- **Detection signal:** after a failed apply, `status` shows no managed-file drift for an edited
  managed file; `state.yml` has no `managed_files`; the next apply changes a managed file with no
  warning; operators learn to delete `.quickscale/apply-recovery.yml`.
- **Steelman:** the ledger is a recovery aid, `state.yml` is authoritative, and resume is best-effort;
  a full re-run recaptures hashes. That holds while crashes are rare and every recovery is followed
  by a clean apply. The code does not enforce either condition.
- **Correct shape:** one owner for applied state; the recovery record stores the resume pointer and
  immutable facts, not a second full snapshot; resume mutates the authoritative state and every
  checkpoint carries the live snapshot.
- **Do-nothing cost:** silent drift blindness after interrupted applies; each new state field adds a
  merge bug; the recovery mechanism becomes a source of state corruption rather than a cure.
- **Options:**
  1. **Single owner**: the ledger stores step progress and the resume pointer only; state comes from
     `state.yml` on every resume. M, two-way; removes the mechanism.
  2. **Keep snapshots, close the gap**: pass the live state on every checkpoint, add an
     equality/reconciliation check on load, and add a resume test asserting `managed_files`. S,
     two-way; contains but does not remove the duplication.
  3. **Accept and document** `rm .quickscale/apply-recovery.yml` recovery. Containment: a status
     warning when the ledger and state diverge. Revocation: an observed drift miss.
- **Recommendation:** option 1 with option 2 as the interim. **Size:** M · **Reversibility:** two-way
  door · **Guard:** a fault-injection test that kills after step 4, resumes, and asserts
  `managed_files` and contract steps survive; an equality check on ledger/state. **Acceptance
  check:** the same crash leaves a state that detects an edited managed file. **First step:** stop
  carrying `applied_state` in the ledger; keep only the checkpoint.

## Change-cost probe

**Probe A — SA153 adds a project-owned public page (next feature).** Stations: user-owned theme page,
module endpoint, manifest wiring, `project_contract.yml` step, adoption in `bap-web-new`, docs, and
the missing managed-hook file. Seven stations, and the page↔endpoint pair is held by no gate.
Verdict: **finding evidence for F1 and F3.** The roadmap itself assigns the managed-hook boundary to
SA153.

**Probe B — add a 13th module.** Stations: module directory and `module.yml`, package
`pyproject.toml`, `MODULE_CATALOG`, `AUTHORITATIVE_MODULE_COUNT`, root `pyproject.toml`, `mypy.ini`
section, module layer entry, initial split branch, split tag/seal, CI env/seam/URL rows, docs.
Nine to fourteen hand edits, of which catalog/count, layer, and mypy are gated by consistency
tests. Verdict: **finding evidence for F2/F3**; the catalog gate converts a silent break into a
build failure but does not remove the edit.

**Probe C — change runtime DRF renderer/parser defaults (SA288 class).** Stations:
`runtime/settings.py`, runtime tests, CHANGELOG/release note. Three stations, no
`project_contract.yml` step. Verdict: **finding evidence for F3**; this is the exact `936b8d0b`
shape.

**Probe D — add a module-declared environment variable (control).** Stations: `module.yml` only;
apply regenerates the managed `.env.example` include and CI environment from the manifest. One
station, gated by the env-example conformance test. Verdict: **exonerated** — SA286's manifest-driven
rendering works.

## Fix order and interactions

- **F3 before F1** (or in the same change): F3 defines the contract boundary that must watch the
  generated hooks F1 creates. Landing F1 without F3 mints a new managed file with no drift signal.
- **F7 before/with F2:** the update journal needs one state owner. Fixing F2 on top of the dual-owner
  state would add a third writer.
- **F4 and F6 share media:** F4's production storage backend reduces F6's media gap but does not
  close it; F6 must still decide whether media is captured or explicitly external.
- **F1 amplifies F5:** the first project-owned tenant models arrive with SA153, the same work that
  needs managed hooks. F5 should land with or before SA153 (j).
- **F5 is independent** of the others and can run in parallel; its CI job is also the natural place
  to exercise F4's production profile.
- **Ranking already reflects amplification:** F1/F2 are High × High; F3/F4/F5 are High × Medium;
  F6 is High × Medium with a later horizon; F7 is Medium × Medium.

## Sound load-bearing decisions

1. **Closed-world emission mapping.** `get_generator_emission_mapping` derives 143 emitted paths from
   templates, and `test_emission_closed_world.py` derives its scan scope from that mapping, not a
   hand list. Keep this derivation; extend it (F3) rather than replacing it.
2. **Module embed is tag-pinned and provenance-checked.** Embed resolves and peels an immutable
   `splits/<module>/<version>` tag (`_module_embed.py:323-343`); the update guard detects local edits
   against the recorded commit (`module_provenance.py`); migration content is frozen from 0.89.0.
   This is the right identity model — update should join it (F2), not abandon it.
3. **RLS is structural in the shipped modules.** 22/22 tenant models carry FORCE RLS, the
   `TenantManager` pair, and composite tenant-equality FKs; the runtime-role boot guard fails
   closed; the repository integration gate runs under `NOBYPASSRLS NOSUPERUSER`. Do not weaken this
   to fix F5 — extend the generated harness to use it.
4. **State and ledger writes are atomic and fail hard.** `StateManager.save` and `LedgerManager.save`
   use tmp + replace; malformed state raises rather than silently degrading; lock release checks
   inode, PID, and an acquisition token. Keep these properties through the F7 refactor.
5. **Split publication/seal is hardened.** Maintainer publish enforces release-authoritative
   `VERSION`, origin/local config, expected remote SHA, fast-forward ancestry, and a post-push
   tree/tag check. The user-facing update path should reuse this, not reinvent it.

## Accepted commitments

None. No team decision record accepts any open finding with a containment and revocation trigger.

## Watchlist

**Carried from the prior pass — all re-evaluated at `82ff3e7d`.**

| ID | Concern | Trigger | This pass |
|---|---|---|---|
| `core-holds-module-vocabulary` | Core/CLI name module-specific vocabulary | 13th module, or a new module-named apply step | not fired: 12 modules; `AUTHORITATIVE_MODULE_COUNT = 12`; 4 module-named env-sync steps and 5 module-named display functions; `social_manifest.py` still 512 lines. Related to F3. |
| `manifest-dsl-vocabulary-growth` | DSL gains a keyword per module need | a keyword added for one module | not fired: 14 top-level keys; `throttle_scopes` is generic; no manifest change in the delta. |
| `session-advisory-lock-pooling` | Billing mutex is a session advisory lock | pooled `DATABASE_URL` | not fired: still `pg_advisory_lock` (`_locks.py:41,70`); no pooler in generated settings; `CONN_MAX_AGE=600` is per-process. |
| `modules-english-only` | Module pages are English-only | SA153/154 needs a Spanish module page | not fired: no `gettext`/`trans` in module source; SA154 is inventory-only. |
| `two-filesystem-lock-implementations` | `advisory_lock.py` and `dr_engine/_lock.py` | a third implementation | not fired: exactly two; the DR lock's mtime heuristic is carried under F6, not as a third lock. |
| `ci-provisioning-hand-pins` | Hand-pinned CI residue | 13th module | not fired: 12 modules; `provision_ci_postgres.sh:95` hard-asserts the count; the `backups-validation` job is still hand-written. |
| `trigger-inputs-legacy-name` | Legacy name of the E2E allowlist | a gate skipped on it | not fired: field feeds the E2E allowlist only; validated at `_gate_registry_schema.py:481-511`; no execution path skips. |
| `subscription-status-single-writer` | One writing module for subscription status | second provider or an outside writer | not fired: Stripe-only, one module; **prior evidence corrected** — six assignment sites in five billing files (`_subscription_checkout.py:480`, `_subscription_events.py:192`, `_subscription_mutations.py:406`, `_webhooks_checkout.py:561`, `_webhooks_invoice.py:491,569`), all inside billing. |

**New, below the cut.**

| ID | Concern | Why it does not qualify yet | Trigger |
|---|---|---|---|
| `release-gate-version-blind` | `version_tool.sh check` does not read the two `_version.py` files; TestPyPI is `continue-on-error`; `check-module-seals` is outside `gate_registry.json` | latent: 34 of 37 `VERSION` commits also touch `_version.py`; CI still tests and builds the tag | the next release where `_version.py` and `VERSION` diverge, or a TestPyPI-only failure would have caught a defect; or a stale seal ships |
| `cli-headless-gap` | `apply`/`update` call `click.confirm` with no `--yes`/non-interactive flag; cancel exit codes differ by command | the interactive wizard is the declared default; no CI automation requirement yet | a deployment or CI workflow needs to run apply/update unattended |
| `node-pin-duplication` | Node/pnpm versions are literals in six generated files; no parity gate (Python/Django/Postgres are derived) | SA308 refreshes them together; a drift is a build failure, not data loss | the next Node/pnpm bump that edits fewer than all six stations |
| `tenant-removal-coverage` | Purge covers 22 tenant tables but not NotificationMessage/deliveries, billing webhook payloads, backup artifacts, media objects, or analytics; obligations are opt-in (4 of 12 apps declare) | no erasure request or external retention obligation has been recorded; the docs call it GDPR-capable | the first erasure/export request, or a compliance commitment; then promote with F1/F6 |
| `admin-tenant-authority` | `TenantModelAdmin` takes an org UUID from request parameters and queries under it; `OrganizationMembershipAdmin`/`InvitationAdmin` let staff edit memberships | the docs require tenants never to be `is_staff`; only superusers are the documented operators; conditional on a non-superuser staff account | any non-superuser staff account is created |
| `seam-unversioned` | `window.__QUICKSCALE__` has no version; key presence is validated by a user-owned TS file; payload shapes are unvalidated | core pin is minor-range; key skew fails loudly; no skew incident recorded | the first frontend/core skew failure in a live project |

## Rejected candidates

- **`core-holds-module-vocabulary` as a finding** — killed for now: the 13th-module trigger has not
  fired; the existing seam tables are real but do not add a new cost until a module/page arrives.
  Watchlist.
- **`manifest-dsl-vocabulary-growth`** — no per-module keyword was added; the last manifest additions
  are generic. Watchlist.
- **`two-filesystem-lock-implementations` as a standalone finding** — the third-implementation
  trigger has not fired; the DR lock's stale heuristic is evidence inside F6, not a separate root.
- **`session-advisory-lock-pooling`** — no pooler configuration exists; a session lock is correct
  under direct connections. Watchlist.
- **`migrate-runs-per-replica` as a standalone finding** — folded into F4; the trigger is more than
  one replica, and the live project is single-instance. The boot contract is the structural root.
- **`allow-bypassrls-serving-undetected` as a standalone finding** — folded into F5; the production
  escape hatch is one manifestation of a test harness that never exercises RLS.
- **CLI exit-code inconsistency** — ticket-shaped: three cancellation policies, one `sys.exit(0)`
  path; no compounding root and no current automation consumer. Watchlist (`cli-headless-gap`).
- **Node/pnpm literal duplication** — a configuration-SSOT gap; SA308 refreshes the set together.
  Watchlist (`node-pin-duplication`).
- **TestPyPI/seal gate gaps** — release-process tickets; the authoritative CI path is tag-checked
  and test-gated. Watchlist (`release-gate-version-blind`).
- **Tenant purge global stores** — a real coverage gap but no recorded erasure obligation; below the
  cut. Watchlist (`tenant-removal-coverage`).
- **Admin tenant authority** — conditional on a non-superuser staff account; the documented model
  is superuser-only. Watchlist (`admin-tenant-authority`).
- **DR sidecar checksum/path containment** — requires write access to the private backup store; a
  hardening ticket, not a structural root. It is noted in F6's evidence but not promoted.
- **`start.sh` second DB connection constructor** — a ticket; the role split is sound.
- **Tech-audit S4s** (`notifications-message-status-aggregate-race`, `forms-retention-skips-null-ip-rows`,
  `beta-migrate-existing-recipient-no-dirty-guard`) — defect-shaped; owned by `tech-audit.md`, not
  re-reported here.

## Questions that would change the ranking

- **Will a second generated project go live before 1.0?** Yes → F1 stays rank 1 and option 3 is
  dead; the steps × projects cost doubles immediately.
- **Is self-hosted Compose a supported production path or a dev convenience?** If dev-only, F4's
  preferred option becomes 2 (keep the corrected local-development labeling and add the release
  gate), and the finding drops to a documentation/gate fix.
- **Will SA153's project-owned extension add tenant models and migrations?** The roadmap says it adds
  `0002+` migrations; if it also adds tenant tables, F5 and F6 both rise (F5's Medium likelihood
  becomes High; F6's horizon moves to now).
- **Is the backups engine the live project's recovery path, or is the cutover's manual `pg_dump` the
  real path?** If the engine is unused, F6 drops to a watchlist; if it is used, its rank rises.
- **Is a tenant erasure/export obligation actually contracted?** Yes → `tenant-removal-coverage`
  promotes into a finding (likely High × Medium).

## Red flags (out of scope — fix now)

None found in this pass. No committed credentials, unauthenticated admin surface, obvious injection
path, or imminent data-loss path was identified beyond the structural findings above.

## Coherence hand-offs

- `TenantModelAdmin`'s request-supplied org selector (`orgs/admin.py:177-197,313-329`) differs from
  the session-authority used by content routes; the coherence audit may want to check whether the
  20 admin classes consistently use the selector or should share the content-route permission
  contract. This is a security-architecture watchlist item (`admin-tenant-authority`), not a §0
  finding here.

## Reconciliation log

Reconciliation counts: prior findings still-open **1**; resolved this pass **0** (SA305 was
resolved before this pass); regressed **0**; new findings **6**. Prior watchlist carried **8**; new
watchlist **6**.

- 2026-10-23 — `generated-file-ownership-unmodeled`: **still-open**. Mechanism unchanged; project
  steps 53 → **58**; theme resource subpaths/types remain (5 source files + 2 templates); no
  `quickscaleSeam.hooks.*`; SA277 a3 only versions the handoff prompt; SA153 (j) not landed. New
  evidence: `quickscale_managed/*` is untracked and the vintage gate excludes runtime (now F3).
- 2026-10-23 — `core-holds-module-vocabulary`: carried (trigger not fired: 12 modules; count and
  catalog still hand-declared).
- 2026-10-23 — `manifest-dsl-vocabulary-growth`: carried (no new keyword in the delta).
- 2026-10-23 — `session-advisory-lock-pooling`: carried (no pooler; `pg_advisory_lock` unchanged).
- 2026-10-23 — `modules-english-only`: carried (no i18n in module source; SA154 inventory-only).
- 2026-10-23 — `two-filesystem-lock-implementations`: carried (still two; DR mtime heuristic folded
  into `backup-restore-incoherent`).
- 2026-10-23 — `ci-provisioning-hand-pins`: carried (12 modules; hard count assertion remains).
- 2026-10-23 — `trigger-inputs-legacy-name`: carried (verified in depth; no gate skip).
- 2026-10-23 — `subscription-status-single-writer`: carried (one module/Stripe; prior "one writer"
  anchor corrected to six assignment sites in five billing files).
- 2026-10-23 — `vendored-module-edits-undetected`: **resolved** (SA305: update refuses a changed or
  unverifiable tree; `status` reports it; re-verified, no regression).
- 2026-10-23 — prior `Sound load-bearing decisions` (4): all re-verified; closed-world emission,
  vintage-template derivation, six-path drift hashes, and SA286 manifest CI/ops rendering still hold.
- 2026-10-23 — prior `Rejected candidates` (`cca2eac9` existing-recipient path): still holds; the
  recipient is validated against slug/package/theme/resolved modules.
- 2026-10-23 — prior `Red flags`: none existed; none found now.
- 2026-10-23 — prior `Accepted commitments`: none existed; none recorded now.
- 2026-10-23 — prior `Questions`: second live project still hypothetical; answer unchanged.
- 2026-10-23 — new IDs: `module-upgrade-no-reconciler`, `contract-vintage-boundary-blind`,
  `generated-deploy-topology-unmodeled`, `generated-isolation-unverified`,
  `backup-restore-incoherent`, `apply-state-dual-owner`; new watchlist: `release-gate-version-blind`,
  `cli-headless-gap`, `node-pin-duplication`, `tenant-removal-coverage`, `admin-tenant-authority`,
  `seam-unversioned`.
