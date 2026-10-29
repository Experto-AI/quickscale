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
test harness now runs under the RLS runtime role.

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
  adoption step id; the gate watches emitted templates, the generator mapping, and the public
  `quickscale_core.runtime` module tree; apply/update/deploy refuse until the operator records
  adoption.
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
| Q4 | A project-owned tenant model or endpoint ships | generated CI → tenant data | the generated suite catches a missing org filter under the runtime role | isolation regressions caught by the generated two-organization lane | starter simplicity vs isolation proof |
| Q5 | A destructive restore is exercised during an incident | backup artifact → PostgreSQL, media, env | one coherent recovery point and a safe retry | RPO/RTO unknown; restore evidence is source-level only | restore completeness vs operational simplicity |
| Q6 | A hard crash occurs after apply checkpoint 4 | apply state / recovery ledger | rerun converges; managed-file drift stays detectable | state fields preserved; no declared target | recovery speed vs state simplicity |

**Boundary map (consequential edges on the selected paths).**

| Component / store | Edge kind | Owner of the invariant | Version / failure assumption |
|---|---|---|---|
| `quickscale_cli apply` → generator emission mapping (144 emitted paths) | call / build | `get_generator_emission_mapping` | template set is source of truth; closed-world test |
| apply → managed files (`settings/modules.py`, `urls_modules.py`, seam `.d.ts`/`.keys.ts`, CI env, operations page, `quickscale_managed/*`) | shared state / hashes | `project_state_hashes.py` + module manifests | every managed output hash-tracked (SA316) |
| apply → `.quickscale/state.yml` (applied state) and `.quickscale/apply-recovery.yml` (resume pointer) | shared state | `state.yml` | one applied-state owner; the ledger records progress only |
| `quickscale update` → split branch head → `git subtree pull` → `pyproject.toml` | call / VCS | CLI + remote branch | branch tree proven equal to the seal before pull; lock refreshed once; per-module commits remain |
| generated boot → `predeploy.sh` (pre-deploy) → `start.sh` (role) → gunicorn | call / privilege | `predeploy.sh` + `start.sh` + runtime settings | migrations once per deployment; readiness gates pending schema; no boot DDL |
| generated request → `ClientIdentityMiddleware` → RLS GUC → module views | call / trust boundary | orgs + runtime settings | RLS only under runtime role; generated tests run under it |
| `pg_dump` + captured media → local/remote artifact + sidecars → restore | shared state / external effect | DR engine | DB+media freeze; live env at restore; restore advisory lock |
| release → split tag/branch + PyPI wheel | build / supply chain | publish/seal scripts | tag is immutable; update reads branch |

**Critical-path walkthrough and lifecycle transition.**

*Apply path.* `quickscale apply` loads `state.yml` and the recovery ledger (resume pointer only),
computes the delta, acquires the project lock, embeds missing modules from tags, writes the
post-embed snapshot to `state.yml`, regenerates managed wiring and records every managed output's
hash in `state.yml`, syncs env/dependencies, runs migrations, then finalizes state and clears the
ledger.
The failure branch matters more than the happy path: step 4 mutates `managed_files` and writes the
live snapshot to `state.yml` before its checkpoint, so a kill after it resumes at step 5 with
managed-file drift still detectable. A kill during step 1 leaves subtree commits and module
directories but no checkpoint; the next run re-plans from `state.yml`. `update` journals its module set before the first pull,
applies the set to one state write, and commits it once; a kill between pulls leaves the journal
for the next update to restore. External effects (subtree commits, `poetry install`, `migrate`,
Docker/Railway) are not reversible; the apply ledger and the update journal are the only recovery
records.

*Lifecycle transition.* A 0.89.0 → next-release upgrade stamps 43 version-bearing files, publishes
12 split branches and 12 immutable tags, then an existing project updates from the branch tip,
regenerates managed wiring, and adopts contract steps. Code at N must read state written by N−1:
the desired-state schema stays `"1"`, applied state carries the release version plus per-module
versions, and contract ids union forward. In-flight work: generated project requests during a rolling deploy see `predeploy.sh` migrate
first (F2, closed by SA321); in-flight backups are local files with a 300 s stale heuristic (F3); queued work is
external cron, not an in-process queue. Restore is the other lifecycle branch: it restores a
database dump under a dedicated advisory lease, and its captured media is restored by the separate
media-sync surface, while the environment is read live (F3). No claim of safe in-flight upgrade
rests on a tested two-version exercise; this is residual risk.

**Measurements** (filter: `--since="12 months ago"`, no merges, commits touching ≤30 files,
excluding `vendor/`, `node_modules/`, `dist/`, `build/`, `htmlcov/`, lockfiles, `CHANGELOG`,
generated caches; synthetic subtree-split replays are ~40% of history and inflate per-file counts).
3,789 non-merge commits in twelve months. Delta since the prior audit: 95 commits, 68 non-merge;
classification: closeout (SA191a–e, SA299e/f, SA300b/c, SA301–SA309, SA277 a3, SA191d re-proof),
housekeeping (roadmap/docs), and **no unlabeled-behavioral commit** — every non-doc change carries
an `SAnnn` subject. Key censuses: twelve modules; 36 split tags (3 releases × 12); `project_contract.yml`
**5 steps at introduction (2026-09-24) → 46 (2026-10-16) → 53 (2026-10-20) → 61 today** with 116
adoption sub-steps; managed outputs 9, all hash-tracked (SA316); tenant
models 22 enrolled across 6 modules with 20 `TenantModelAdmin` classes; module-contract references
in 5 theme source files plus 2 social templates, including 17 resource-subpath literals in the three
main contract-bearing files; 65 adoption ids per project (61 project + 4 module vintages). Ownership
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
| Managed files not hand-edited | `project_state_hashes.py` resolves the wiring, project, and every module-managed output; `status` drift | structural | **strengthened** (SA316: all module-managed outputs hash-tracked) |
| Contract change carries a new step id | `scripts/check_project_contract_vintage.py` over emitted templates, the generator mapping, and public runtime modules | gated | **strengthened** (SA316: runtime surface watched) |
| Project adopted declared steps | operator confirmation; `contract_vintage.py` bulk union | convention | steps 53 → 61 |
| Module version lockstep | manifest assertion + `version_tool.sh` | gated | 40 of 43 version-bearing files checked |
| Embedded module content identity | tag at embed; sealed-tag tree verified at update; provenance drift guard | gated | **strengthened** (SA319 (a): update proves the branch tip tree equals the seal) |
| Module migrations frozen | migration-content identity in update/restore | gated | stable |
| Tenant RLS on shipped tables | FORCE RLS migrations, boot guard, restricted-role integration gate | structural in modules | 22/22 enrolled |
| Generated-project tenant isolation | two-organization isolation lane under the restricted runtime role | gated | **closed** (SA318) |
| Apply state single-writer | `StateManager` + `LedgerManager` + update journal, advisory lock | structural | **strengthened** (SA319 (b): one state write per update set; the journal carries intent only) |
| Apply resume preserves state | `ApplyExecutor` checkpoint + fault harness | gated, content not asserted | gap |
| Production migration safety | `predeploy.sh` pre-deploy command; `/ready/` refuses pending migrations | gated | **closed** (SA321: schema work leaves boot) |
| Production media durability | production settings refuse `FileSystemStorage` unless `QUICKSCALE_ALLOW_LOCAL_MEDIA=1` | gated | **closed** (SA321) |
| DR recovery point | dump + captured media + module/project migration identity; restore advisory lock | gated | **closed** (SA322: captured media restored from the snapshot, project identity enforced, restore serialized) |
| Tenant removal obligations | app-declared `removal_obligations` | convention (4 of 12 apps declare) | unchanged |
| CLI public/private surface | split-facade gate | gated, one-directional | stable |

## Summary table

| Rank | ID | Title | Horizon | Conf. | Size | Rev. | Problem |
|---|---|---|---|---|---|---|---|
| 1 | `generated-file-ownership-unmodeled` | Module contracts live in user-owned generated files | now | High | M | two-way | Each module API change becomes a manual adoption step recorded by a bulk flag. **Resolved 2026-10-26 by SA320 (c).** |
| 2 | `generated-deploy-topology-unmodeled` | Generated production topology is prose, not an artifact | now | High | M | two-way | Media is container-local, and schema changes at boot. **Resolved 2026-10-29 by SA321.** |

## Machine-readable index

```yaml
schema: arch-audit/v11
audited: 82ff3e7d141cf943ab900eaae5f214c0edfc9e07
snapshot_basis: "82ff3e7d (v89), clean worktree, no uncommitted or untracked inputs read; only post-snapshot change is this deliverable"
items:
  - {id: generated-file-ownership-unmodeled, status: resolved, rank: 1,
     title: "Module contracts live in user-owned generated files",
     lenses: [III, V, VII, XIX], horizon: now, confidence: High, size: M,
     reversibility: two-way door, depends_on: [], amplifies: [],
     anchors: [quickscale_core/src/quickscale_core/project_state_hashes.py,
               quickscale_core/src/quickscale_core/data/project_contract.yml,
               quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/src/pages/CrmPage.tsx],
     first_seen: 2026-07-10, last_verified: 2026-10-23}
  - {id: generated-deploy-topology-unmodeled, status: resolved, rank: 2,
     title: "Generated production topology is prose, not an artifact",
     lenses: [IV, VI, XVI, XIX], horizon: now, confidence: High, size: M,
     reversibility: two-way door, depends_on: [], amplifies: [],
     anchors: [quickscale_core/src/quickscale_core/generator/templates/railway.json.j2,
               quickscale_core/src/quickscale_core/generator/templates/predeploy.sh.j2,
               quickscale_core/src/quickscale_core/generator/templates/project_name/urls.py.j2,
               quickscale_core/src/quickscale_core/generator/templates/project_name/settings/production.py.j2],
     first_seen: 2026-10-23, last_verified: 2026-10-29}

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
  is the next work item and adds exactly this surface; declared steps went 53 → 61 in three days.
- **Horizon & trigger:** `now` — the next module endpoint change, or SA153 (j) coupling a
  project-owned page to a module resource.
- **Confidence:** High — mechanism read, theme census counted, gates read, no enforcing layer found.
- **Context dependence:** `wrong-for-now` (dimension: count of live generated projects). Lives in
  deployment reality (B); with one project, regeneration (SA299 style) is a valid containment.
- **Problem:** The generated project has only a two-valued ownership model (regenerated or
  user-owned), but module resource paths and payload types still live in user-owned theme files, so
  each module/template change becomes a hand-adopted contract step recorded by a bulk flag.
- **Evidence:**
  - Managed boundary: `project_state_hashes.py` resolves the wiring and project files plus every
    file under `<package>/quickscale_managed/`, so all module-managed outputs are hash-tracked
    (SA316); `module_wiring.py` deletes and rewrites that directory wholesale.
  - Theme census: `pages/CrmPage.tsx:16,36-57` (`stats/`, `contacts/`, `companies/`, `deals/`,
    `tags/`), `hooks/useOrgs.ts:159-265` (eight membership/invitation/settings paths),
    `hooks/usePublicSocialSurface.ts:73-81` (`/_quickscale/social/`, `/embeds/`), plus
    `components/forms/FormRenderer.tsx:113` and `hooks/useFormSchema.ts:61-64`. Five theme source
    files plus two emitted social templates carry module paths/types; the three main files carry
    17 resource-subpath literals and four files declare 29 payload types.
  - **Post-snapshot (2026-10-24):** SA320 (a) moved `CrmPage.tsx`'s five subpaths and `CrmStats`
    into the generated managed `frontend/src/quickscaleSeam.hooks.ts`, and the closed-world test
    now rejects a declared resource subpath or payload type in a user-owned file with the managed
    hook as its passing control.
  - **Post-snapshot (2026-10-26):** SA320 (b) moved the remaining theme pages onto the hook: orgs,
    billing, social and forms declare their `frontend_resources` (parameterized paths render typed
    builders; payload types may use optional, array, reference, nullable and union forms), and
    `useOrgs.ts`, `useFormSchema.ts`, `FormRenderer.tsx`, `usePublicSocialSurface.ts` and
    `useModules.ts` import the generated declarations instead of restating them; the emitted social
    templates already read the module's settings paths, so they carry no module resource literal.
    The closed-world check now also rejects a hand-written builder path and a union alias
    declaration, with the managed hook as its control. The core-template module branches remain, so
    the finding stays open for SA320 (c).
  - `test_emission_closed_world.py:489` / `:540-550` permits "a single module reference"; it
    forbids enumerations, not resource subpaths or payload shapes.
  - Contract steps: `project_contract.yml` has **61 step ids** and 116 adoption sub-steps; growth
    5 → 46 → 53 → 61 since 2026-09-24. The four newest steps are all manual user-owned-file changes.
  - Adoption: `contract_vintage.py:239-295` records every declared id by union, with no check that
    the user-owned file changed; `deployment_commands.py:118-127` records adoption on a clean-tree
    check alone, without regenerating or pulling anything.
  - Fix-regression audit: SA289 moved API **bases** into the seam (`runtime/seam.py:7-10,344,392`)
    but left resource subpaths and types in pages; `test_emission_closed_world` still allows one
    reference. SA277 a3 only versions the handoff prompt. SA153 (j) has not landed. **Relocated,
    not removed.**
- **Counter-evidence:** at the audit snapshot the search found no generated managed-hooks file
  (`quickscaleSeam.hooks.*`), no detector for module subpaths/payload types in user-owned files,
  and no adoption verification against file content. The closed-world test and contract-vintage
  gate are real, but their scope stopped at enumerations and template *wiring*; SA316 hashes every
  managed output. **SA320 (a) has since landed (2026-10-24)** and **(b) on 2026-10-26:** the
  generated `frontend/src/quickscaleSeam.hooks.ts` renders each active manifest's
  `frontend_resources`, the closed-world test rejects a declared resource subpath, builder path, or
  payload type in a user-owned file with the managed hook as its passing control, and the theme's
  page hooks and the CRM page import it. SA320 (c) then moved the core-template module branches:
  the admin templates render a module-owned shortcut through the generic `quickscale_admin` tag,
  the Makefile/CI/Compose contributions are marker-paired managed regions rendered from each
  module's `project_blocks` declaration, and the notifications adapter writes `ANYMAIL` into the
  managed settings. Rule 37 now rejects a single-name module branch or module-prefixed constant in
  a generator template, and rule 30 rejects a core template that reads a module's setting. SA153's
  roadmap line still owns the portal's managed-hook boundary.
- **Why it compounds:** growth variable = **declared adoption steps × live projects**. Each module
  resource or payload change adds a step (steps are monotonic; the roadmap's stated target is
  "toward zero"); each live project must adopt every step by hand. Built on top: the contract-vintage
  gate in `apply`, `update`, and `deploy railway`, SA299's beta migration, and SA277's two-stage
  prompt. A second live project doubles the operator cost and makes "regenerate and diff" no longer
  sufficient.
- **Detection signal:** step count per release (61 today; eight added since the prior audit); any
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
  emission mapping. **First step:** delivered by SA320 (a) on 2026-10-24 — `CrmPage.tsx`'s section
  paths and `CrmStats` type now come from the generated `frontend/src/quickscaleSeam.hooks.ts`.
  SA320 (b) delivered the remaining theme pages on 2026-10-26, and SA320 (c) delivered the
  per-module core-template branches the same day, closing the finding.
- **Remaining delivery ownership:** SA277 (Track 3) owns the two-stage upgrade rule; it does not
  remove resource contracts from user-owned pages. SA153 (j, Track 1) owns the portal's
  managed-hook boundary. Completing either alone is not closure.

### Finding 2: Generated production topology is prose, not an artifact

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

- **Post-snapshot (2026-10-29):** SA321 delivered option 2. `railway.json` runs `./predeploy.sh`
  as `deploy.preDeployCommand` (migrations then cache table under the superuser URL) and gates the
  deployment on `/ready/`, which answers 200 only when the database is reached and no migration is
  pending; `/healthcheck/` stays DB-free liveness. `start.sh` keeps runtime-role provisioning and
  runs no schema work. Production serving refuses `FileSystemStorage` unless
  `QUICKSCALE_ALLOW_LOCAL_MEDIA=1` marks a development or test deployment, and the README and
  decisions name Railway as the one production path. A generated-project test boots production
  settings and fails closed on local media without the flag; a smoke station runs `predeploy.sh`
  then `start.sh` and asserts both probes. The finding is closed.

### Finding 3: Backups cover the database, not a coherent recovery point

## Change-cost probe

**Probe A — SA153 adds a project-owned public page (next feature).** Stations: user-owned theme page,
module endpoint, manifest wiring, `project_contract.yml` step, adoption in `bap-web-new`, docs, and
the managed-hook file (delivered by SA320 (a) and (b); only the core-template branches remain).
Seven stations, and the page↔endpoint pair is held by no gate. Verdict: **finding evidence for F1.**
The roadmap
itself assigns the managed-hook boundary to SA153.

**Probe B — add a 13th module.** Stations: module directory and `module.yml`, package
`pyproject.toml`, `MODULE_CATALOG`, `AUTHORITATIVE_MODULE_COUNT`, root `pyproject.toml`, `mypy.ini`
section, module layer entry, initial split branch, split tag/seal, CI env/seam/URL rows, docs.
Nine to fourteen hand edits, of which catalog/count, layer, and mypy are gated by consistency
tests. Verdict: **finding evidence for the module catalog surface**; the catalog gate converts a silent break into a
build failure but does not remove the edit.

**Probe D — add a module-declared environment variable (control).** Stations: `module.yml` only;
apply regenerates the managed `.env.example` include and CI environment from the manifest. One
station, gated by the env-example conformance test. Verdict: **exonerated** — SA286's manifest-driven
rendering works.

## Fix order and interactions

- **F2 and F3 share media:** F2's production storage backend reduces F3's media gap but does not
  close it; SA322 captured media and added the restore lease, and SA321 closed the deploy topology
  with a pre-deploy schema step, a readiness gate, and a local-media refusal.
- **Ranking already reflects amplification:** F1 is High × High; F2/F3 are High × Medium.

## Sound load-bearing decisions

1. **Closed-world emission mapping.** `get_generator_emission_mapping` derives 144 emitted paths from
   templates, and `test_emission_closed_world.py` derives its scan scope from that mapping, not a
   hand list. Keep this derivation; SA316 extended it to the public runtime module tree rather than
  replacing it.
2. **Module embed is tag-pinned and provenance-checked.** Embed resolves and peels an immutable
   `splits/<module>/<version>` tag (`_module_embed.py:323-343`); the update guard detects local edits
   against the recorded commit (`module_provenance.py`); migration content is frozen from 0.89.0.
   This is the right identity model — update joined it through the journaled set transaction (SA319 (b)).
3. **RLS is structural in the shipped modules.** 22/22 tenant models carry FORCE RLS, the
   `TenantManager` pair, and composite tenant-equality FKs; the runtime-role boot guard fails
   closed; the repository integration gate runs under `NOBYPASSRLS NOSUPERUSER`. Do not weaken this.
   The generated two-organization lane runs under the same role and the serving refusal keeps it
   there.
4. **State and ledger writes are atomic and fail hard.** `StateManager.save` and `LedgerManager.save`
   use tmp + replace; malformed state raises rather than silently degrading; lock release checks
   inode, PID, and an acquisition token. Keep these properties through future state changes.
5. **Split publication/seal is hardened.** Maintainer publish enforces release-authoritative
   `VERSION`, origin/local config, expected remote SHA, fast-forward ancestry, and a post-push
   tree/tag check. The user-facing update path should reuse this, not reinvent it.

## Accepted commitments

None. No team decision record accepts any open finding with a containment and revocation trigger.

## Watchlist

**Carried from the prior pass — all re-evaluated at `82ff3e7d`.**

| ID | Concern | Trigger | This pass |
|---|---|---|---|
| `core-holds-module-vocabulary` | Core/CLI name module-specific vocabulary | 13th module, or a new module-named apply step | not fired: 12 modules; `AUTHORITATIVE_MODULE_COUNT = 12`; 4 module-named env-sync steps and 5 module-named display functions; `social_manifest.py` still 512 lines. |
| `manifest-dsl-vocabulary-growth` | DSL gains a keyword per module need | a keyword added for one module | not fired: 14 top-level keys; `throttle_scopes` is generic; no manifest change in the delta. |
| `session-advisory-lock-pooling` | Billing mutex is a session advisory lock | pooled `DATABASE_URL` | not fired: still `pg_advisory_lock` (`_locks.py:41,70`); no pooler in generated settings; `CONN_MAX_AGE=600` is per-process. |
| `modules-english-only` | Module pages are English-only | SA153/154 needs a Spanish module page | not fired: no `gettext`/`trans` in module source; SA154 is inventory-only. |
| `two-filesystem-lock-implementations` | `advisory_lock.py` and `dr_engine/_lock.py` | a third implementation | not fired: exactly two; the DR lock's mtime heuristic is carried under F3, not as a third lock. |
| `ci-provisioning-hand-pins` | Hand-pinned CI residue | 13th module | not fired: 12 modules; `provision_ci_postgres.sh:95` hard-asserts the count; the `backups-validation` job is still hand-written. |
| `trigger-inputs-legacy-name` | Legacy name of the E2E allowlist | a gate skipped on it | not fired: field feeds the E2E allowlist only; validated at `_gate_registry_schema.py:481-511`; no execution path skips. |
| `subscription-status-single-writer` | One writing module for subscription status | second provider or an outside writer | not fired: Stripe-only, one module; **prior evidence corrected** — six assignment sites in five billing files (`_subscription_checkout.py:480`, `_subscription_events.py:192`, `_subscription_mutations.py:406`, `_webhooks_checkout.py:561`, `_webhooks_invoice.py:491,569`), all inside billing. |

**New, below the cut.**

| ID | Concern | Why it does not qualify yet | Trigger |
|---|---|---|---|
| `release-gate-version-blind` | `version_tool.sh check` does not read the two `_version.py` files; TestPyPI is `continue-on-error`; `check-module-seals` became a publish-context registry gate on 2026-10-25 | latent: 34 of 37 `VERSION` commits also touch `_version.py`; CI still tests and builds the tag | the next release where `_version.py` and `VERSION` diverge, or a TestPyPI-only failure would have caught a defect |
| `cli-headless-gap` | `apply`/`update` call `click.confirm` with no `--yes`/non-interactive flag; cancel exit codes differ by command | the interactive wizard is the declared default; no CI automation requirement yet | a deployment or CI workflow needs to run apply/update unattended |
| `node-pin-duplication` | Node/pnpm versions are literals in six generated files; no parity gate (Python/Django/Postgres are derived) | SA308 refreshes them together; a drift is a build failure, not data loss | the next Node/pnpm bump that edits fewer than all six stations |
| `tenant-removal-coverage` | Purge covers 22 tenant tables but not NotificationMessage/deliveries, billing webhook payloads, backup artifacts, media objects, or analytics; obligations are opt-in (4 of 12 apps declare) | no erasure request or external retention obligation has been recorded; the docs call it GDPR-capable | the first erasure/export request, or a compliance commitment; then promote with F1/F3 |
| `admin-tenant-authority` | `TenantModelAdmin` takes an org UUID from request parameters and queries under it; `OrganizationMembershipAdmin`/`InvitationAdmin` let staff edit memberships | the docs require tenants never to be `is_staff`; only superusers are the documented operators; conditional on a non-superuser staff account | any non-superuser staff account is created |
| `seam-unversioned` | `window.__QUICKSCALE__` has no version; key presence is validated by a user-owned TS file; payload shapes are unvalidated | core pin is minor-range; key skew fails loudly; no skew incident recorded | the first frontend/core skew failure in a live project |

## Rejected candidates

- **`core-holds-module-vocabulary` as a finding** — killed for now: the 13th-module trigger has not
  fired; the existing seam tables are real but do not add a new cost until a module/page arrives.
  Watchlist.
- **`manifest-dsl-vocabulary-growth`** — no per-module keyword was added; the last manifest additions
  are generic. Watchlist.
- **`two-filesystem-lock-implementations` as a standalone finding** — the third-implementation
  trigger has not fired; the DR lock's stale heuristic is evidence inside F3, not a separate root.
- **`session-advisory-lock-pooling`** — no pooler configuration exists; a session lock is correct
  under direct connections. Watchlist.
- **`migrate-runs-per-replica` as a standalone finding** — folded into F2; the trigger is more than
  one replica, and the live project is single-instance. The boot contract is the structural root.
- **`allow-bypassrls-serving-undetected` as a standalone finding** — resolved with SA318:
  production serving refuses the bypass, and the generated two-organization lane runs under the
  restricted role.
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
  hardening ticket, not a structural root. It is noted in F3's evidence but not promoted.
- **`start.sh` second DB connection constructor** — a ticket; the role split is sound.
- **Tech-audit S4s** (`notifications-message-status-aggregate-race`, `forms-retention-skips-null-ip-rows`,
  `beta-migrate-existing-recipient-no-dirty-guard`) — defect-shaped; owned by `tech-audit.md`, not
  re-reported here.

## Questions that would change the ranking

- **Will a second generated project go live before 1.0?** Yes → F1 stays rank 1 and option 3 is
  dead; the steps × projects cost doubles immediately.
- **Is self-hosted Compose a supported production path or a dev convenience?** If dev-only, F2's
  preferred option becomes 2 (keep the corrected local-development labeling and add the release
  gate), and the finding drops to a documentation/gate fix.
- **Will SA153's project-owned extension add tenant models and migrations?** The roadmap says it adds
  `0002+` migrations; if it also adds tenant tables, F3's horizon moves to now.
- **Is the backups engine the live project's recovery path, or is the cutover's manual `pg_dump` the
  real path?** If the engine is unused, F3 drops to a watchlist; if it is used, its rank rises.
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

- 2026-10-24 — SA318 closed `generated-isolation-unverified`: generated CI provisions a
  `NOSUPERUSER/NOBYPASSRLS` role and runs the two-organization isolation template, and production
  serving refuses `QUICKSCALE_ALLOW_BYPASSRLS=1`. The finding is removed from the open findings.
- 2026-10-24 — SA316 closed `contract-vintage-boundary-blind`: the vintage gate watches
  `quickscale_core.runtime`'s public modules, and every `quickscale_managed` output is hash-tracked
  so a local edit is reported by `quickscale status`. The finding is removed from the open findings.

Reconciliation counts: prior findings still-open **1**; resolved this pass **0** (SA305 was
resolved before this pass); regressed **0**; new findings **6**. Prior watchlist carried **8**; new
watchlist **6**.

- 2026-10-23 — `generated-file-ownership-unmodeled`: **still-open**. Mechanism unchanged; project
  steps 53 → **58**; theme resource subpaths/types remain (5 source files + 2 templates); no
  `quickscaleSeam.hooks.*`; SA277 a3 only versions the handoff prompt; SA153 (j) not landed. New
  evidence: `quickscale_managed/*` was untracked and the vintage gate excluded runtime (closed by
  SA316 on 2026-10-24).
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
  `backup-restore-incoherent`; new watchlist: `release-gate-version-blind`,
  `cli-headless-gap`, `node-pin-duplication`, `tenant-removal-coverage`, `admin-tenant-authority`,
  `seam-unversioned`.
- 2026-10-24 — `apply-state-dual-owner`: resolved by SA317.  The recovery ledger now stores the
  resume pointer and diagnostic progress only; `state.yml` is the single applied-state owner and
  resume reads it.
- 2026-10-24 — `module-upgrade-no-reconciler`: **resolved** by SA319. Slice (a) verifies the sealed
  tag and canonical branch tree for the whole set before the first pull and refreshes `poetry.lock`
  once. Slice (b) records `.quickscale/update-journal.yml` before the first pull, applies the set to
  one `state.yml` write, commits the set once, and resumes the recorded set on the next update after
  a hard interruption without re-pulling an already merged target; `apply` and deploy refuse while
  the journal is pending.
- 2026-10-25 — `backup-restore-incoherent`: **resolved** by SA322. Slice (b) versions the artifact
  manifest and enforces module and project-app migration identity at restore. Slice (c) captures the
  media set into the version 2 snapshot with per-file checksums, restores media sync from that
  captured set (a version 1 snapshot warns and stays database-only), and holds a dedicated restore
  advisory lock; a PostgreSQL drill restores database, media and project schema, an aborted restore
  rolls back, and a SIGKILLed restore leaves the target database unchanged.
- 2026-10-26 — `generated-file-ownership-unmodeled`: **resolved** by SA320 (c). The remaining
  core-template module branches move onto module declarations: a generic admin tag plus the
  backups-owned shortcut template, managed Makefile/CI/Compose regions rendered from each
  manifest's `project_blocks`, and the notifications adapter's own `ANYMAIL`. Rule 37 catches a
  single-name template branch or module-prefixed constant, and rule 30 reads the core templates;
  both ship fixture controls. The generated-project contract step `sa320c-project-blocks` carries
  the one-time adoption.
- 2026-10-26 — `generated-file-ownership-unmodeled`: **still-open, slice (b) landed**. SA320 (b)
  moves the remaining theme pages onto the managed hook: orgs, billing, social and forms declare
  their resource paths (parameterized paths as typed builders) and payload types; the theme hooks
  import the generated declarations; and the closed-world check rejects a hand-written builder path
  or union alias. The core-template module branches remain for SA320 (c).
- 2026-10-29 — `generated-deploy-topology-unmodeled`: **resolved** by SA321. `predeploy.sh` owns
  `migrate` and `createcachetable` as Railway's `deploy.preDeployCommand`; `start.sh` only
  provisions the runtime role and serves. `/ready/` gates the deployment on a reached database with
  no pending migrations, `/healthcheck/` stays DB-free liveness, and production serving refuses
  `FileSystemStorage` unless `QUICKSCALE_ALLOW_LOCAL_MEDIA=1`. README and decisions name Railway as
  the one production path, and `sa321-production-deploy-contract` carries the adoption step.
- 2026-10-24 — `generated-file-ownership-unmodeled`: **still-open, slice (a) landed**. SA320 (a)
  generates `frontend/src/quickscaleSeam.hooks.ts` from each active manifest's `frontend_resources`
  section (CRM declares five subpaths and `CrmStats`), moves `CrmPage.tsx` onto it, and extends the
  closed-world test to reject a declared resource subpath or payload type in a user-owned file with
  the managed hook as the passing control. The remaining theme pages and the core-template module
  branches still carry paths and types, so the finding stays open for SA320 (b)/(c).
