# Architecture Audit — Open Findings

Audited: `cca2eac9` (v89) · 2026-10-20 · working tree clean (no uncommitted inputs read) · prompt: deep-architectural-audit v11

Cite a finding only by its slug ID; section numbers are not stable. Resolved findings and prior
full text are in git history (`git log -- docs/others/arch-audit.md`).

## Orientation summary

QuickScale is a **code generator plus runtime library**: a Python/Django CLI (`quickscale_cli`)
renders projects from templates in `quickscale_core`, vendors 12 Django modules
(`quickscale_modules/*`) into each project, and keeps a versioned `quickscale_core.runtime`
library. Persistence in generated projects is PostgreSQL; the generator's own state is YAML under
`.quickscale/`. Two deployment realities: **(A) the generator repo** and **(B) generated projects**
(the live one being `bap-web-new`, regenerated on 0.89.0). One maintainer,
very high cadence (451 reachable commits since the prior pass, ~40% synthetic subtree splits);
history before 2026 is thin for these paths. Growth direction (roadmap): SA191d cuts `bap-web-new` over and SA153
adds public pages.
Scope: generator ↔ generated-project boundary (largest blast radius, nearest pressure).

**Declared architecture (from `docs/`, the module-conventions harness, and test docstrings):**
module wiring reaches a project only through managed files and `quickscale_core.runtime`;
user-owned emitted files carry no module wiring (closed-world emission test); every contract
change is declared once in `data/project_contract.yml` with an adoption step; module migrations
are frozen from 0.89.0.

| Scenario | Stimulus · boundary | Required response | Measure / source | Competing quality |
|---|---|---|---|---|
| Module release | a module changes an endpoint or payload · module ↔ theme page | existing projects pick it up by `apply` | files hand-edited per project: target unknown (roadmap implies 0) | template freedom vs. upgradability |
| Project upgrade | 0.89.x → next · generator ↔ project | `apply`/`update` succeed after declared adoption | 53 declared steps today; target unknown | correctness vs. operator time |

**Boundary map (critical path: `quickscale apply`).** CLI `apply` → generator emission mapping →
managed files (`settings/modules.py`, `urls_modules.py`, seam `.d.ts`/keys, CI env, operations
page; hash-tracked in `project_state_hashes.py:40–67`) vs. user-owned files (theme pages, settings,
compose, workflows) → contract-vintage gate (`project_contract.yml`, adoption recorded in
`.quickscale/state.yml` on the operator's confirmation). Invariant owner for user-owned files:
the operator, by hand.

**Measurements** (filter: date-bound `--since=2026-10-15`, no merges, deduped subjects; subtree
splits excluded). Commit delta: 63 unique non-doc subjects. Classification: closeout — SA286
(a, b), SA289 (a, b), SA291, SA153 (e1–e4), SA299 (a–d), SA204 (j); housekeeping — doc splits,
roadmap; **unlabeled-behavioral** — `cca2eac9` ("feat: … migrating existing recipients in
place", adds an existing-recipient path to `beta_migration/regeneration.py` that skips
regeneration). Census: adoption steps **46 at `30b0b6b1` (2026-10-15) → 53 today**; file absent a
year ago.

**Coverage and residual risk.** Read in full: `project_state_hashes.py`, `project_contract.yml`
header and ids, `test_emission_closed_world.py` docstring, `cca2eac9` diff. Sampled: theme
`src/` (census of module-API consumers), module directory list, lock and subscription writers.
Skipped: module internals, DR engine, billing flows (covered by prior passes and the companion
audits). Lens activation: `active: III, V, VII, XV, XIX · inert: XVII (no metered cost driver
in generator), XVIII (generator holds no subject data) · unassessed: IV, X, XVI, XXI this pass
(carried from the prior pass, not re-walked) · archetypes: code generator, CLI, plugin host`.
Finding produced by V/XIX. Out-of-repo: `bap-web-new`'s current tree was not read. Runtime
confirmation needed: none for the open finding.

## Enforcement census

| Invariant | Where enforced | Kind | Trend |
|---|---|---|---|
| Module wiring only in managed files | `test_emission_closed_world.py` over the emission mapping | gated, closed-world | widened (CI env, operations, SA286) |
| Managed files not hand-edited | `project_state_hashes.py` drift hashes | structural | 6 paths, unchanged |
| Contract change declared with a new id | `scripts/check_project_contract_vintage.py` | gated, closed-world (derives watched set) | stable |
| Project adopted declared steps | operator confirmation in `contract_vintage.py` | convention | 46 → 53 steps |
| Module resource contracts (subpaths, payload shapes) out of user-owned pages | none — single module references are allowed by rule 37 | convention | 6 theme files |
| Module migrations frozen | SA204 (h, j) freeze gate | gated | new |
| Embedded module edits are detected before update | `quickscale_cli/utils/module_provenance.py`; update refusal and status drift | gated (refuses unless `--allow-local-changes`) | new |

## Summary table

| Rank | ID | Title | Horizon | Conf. | Size | Rev. | Problem |
|---|---|---|---|---|---|---|---|
| 1 | `generated-file-ownership-unmodeled` | Module contracts live in user-owned generated files | now | High | M | two-way | Module resource contracts and template contract changes reach projects as hand-applied adoption steps. |

## Machine-readable index

```yaml
schema: arch-audit/v11
audited: cca2eac9bbbabb633593a32d9d5dfc79d45dcf2d
snapshot_basis: "cca2eac9 (v89), clean worktree, no uncommitted inputs"
items:
  - {id: generated-file-ownership-unmodeled, status: open, rank: 1, title: "Module contracts live in user-owned generated files",
     lenses: [V, VII, XIX], horizon: now, confidence: High, size: M, reversibility: two-way door,
     depends_on: [], amplifies: [],
     anchors: [quickscale_core/src/quickscale_core/project_state_hashes.py, quickscale_core/src/quickscale_core/data/project_contract.yml, quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/src/pages/CrmPage.tsx],
     last_verified: 2026-10-20}
  - {id: core-holds-module-vocabulary, status: watchlist}
  - {id: manifest-dsl-vocabulary-growth, status: watchlist}
  - {id: session-advisory-lock-pooling, status: watchlist}
  - {id: modules-english-only, status: watchlist}
  - {id: two-filesystem-lock-implementations, status: watchlist}
  - {id: ci-provisioning-hand-pins, status: watchlist}
  - {id: trigger-inputs-legacy-name, status: watchlist}
  - {id: subscription-status-single-writer, status: watchlist}
```

## Ranked findings

### Finding 1: Module contracts live in user-owned generated files
- **ID:** `generated-file-ownership-unmodeled`
- **Rank rationale:** High × High, steep — blocks upgrade of every generated project; SA153 is
  on the roadmap now; adoption steps grew 46 → 53 in five days.
- **Horizon & trigger:** the donor has been migrated into the regenerated `bap-web-new`;
  the next trigger is the first post-0.89.0 module release.
- **Confidence:** High — mechanism read, census counted, gate scope read.
- **Context dependence:** wrong-for-now (dimension: count of live generated projects; with one it
  is operator time, with several it multiplies). Lives in reality (B).
- **Problem:** A file is either regenerated (6 managed paths) or user-owned, but user-owned theme
  pages still encode module resource contracts, so template and module changes ship as manual
  adoption steps confirmed on the operator's word.
- **Evidence (re-verified):** `project_state_hashes.py:40–67` (6 managed paths);
  `project_contract.yml` 53 step ids, newest `sa289-theme-*`, `sa291-declared-throttle-scopes`,
  `sa153e3-public-page-prerender-reverted`, `sa299d-generated-test-harness`. **New:** theme files
  holding a module's resource paths or payload types: `pages/CrmPage.tsx:15–57`
  (`${crmApiBase}stats/`, `contacts/`, `deals/`, `tags/`), `pages/FormsPage.tsx`,
  `components/forms/FormRenderer.tsx`, `hooks/useFormSchema.ts`, `hooks/useOrgs.ts`,
  `hooks/useOrgNavigation.ts` — 6 files.
- **Counter-evidence:** searched for an enforcer of resource contracts in user-owned files.
  `test_emission_closed_world.py` (SA276/SA286) is closed-world over the emission mapping but
  forbids only module *wiring* (name sets, routes, CI values, operations text); it allows "a single
  module reference", so subpaths and payload shapes pass. SA289 moved API *bases* to the seam
  (partial removal). `cca2eac9` lets SA299 migrate into a freshly applied recipient, sidestepping
  adoption for this one project — it does not reduce the step population.
- **Why it compounds:** growth variable = declared adoption steps × live projects. Each module
  endpoint or payload change edits a user-owned page and mints a step; SA286 itself added two
  steps to adopt the managed files. Built on top: the contract-vintage gate in `apply`, `update`,
  `deploy railway`; SA299's migration tooling.
- **Fix-regression audit:** SA286 removed the mechanism for CI env and operations text (resolved
  for those surfaces, guarded closed-world); SA289 relocated API bases into the seam but left
  resource paths in pages — **relocated, finding stays open**. No sound decision regressed.
- **Detection signal:** step count per release; any `apply` refusal naming an outstanding step.
- **Steelman:** user-owned pages are the theme's customization point; routing every module call
  through managed hooks constrains designers, and with one live project regeneration (SA299) is
  cheaper than a seam. Holds while there is exactly one project and it is regenerated per release.
- **Correct shape:** a module's resource paths and payload types reach a user-owned file only by
  importing a managed, regenerated module (seam hooks/types); user-owned files hold presentation.
- **Do-nothing cost:** every module API change after 0.89.0 is a new step adopted by hand in each
  project; the freeze (SA204 j) stops migrations drifting but not this.
- **Options:**
  1. *Managed module hooks* — generate `quickscaleSeam.hooks.ts` per installed module (paths +
     types from manifests); pages import it. M, two-way, incremental per module; removes the
     mechanism. Spends template freedom.
  2. *Extend the closed-world test* to reject module subpaths in user-owned files, forcing option 1
     as SA153 adds pages. S, guard only; alone it blocks without providing the seam.
  3. *Accept and document* — regenerate-per-release as the upgrade path (SA299 style); revocation
     trigger: a second live project.
- **Recommendation:** 1 with 2 as its guard. **Size:** M · **Reversibility:** two-way door ·
  **Guard:** option 2's detector with a control case · **Acceptance check:** a module changing an
  endpoint subpath produces no new `project_contract.yml` step and no user-owned diff (source-
  checkable via the emission mapping) · **First step:** move `CrmPage.tsx`'s section paths and
  `CrmStats` type into a generated managed hooks file.

**Remaining delivery ownership:** SA277 (a3 → a2), Track 3, owns the supported-version
migration fixtures, versioned prompt and two-stage upgrade rule; it does not remove resource
contracts from user-owned pages. SA153 (r → h → j), Track 1, owns the portal's managed-hook
boundary and its checks. The finding stays open until the resource-contract mechanism and
manual-adoption burden above are addressed; completing either ticket alone is not closure.

## Change-cost probe

Target: SA153 adds a module-backed public page. Stations: theme page (user-owned), module
endpoint, manifest, `project_contract.yml` step, adoption in `bap-web-new`, CHANGELOG — 6, with
the page ↔ endpoint pair held by no gate. Verdict: finding evidence.
Second target: a module adds a CI secret — 1 station (manifest); managed include regenerates.
Verdict: exonerated (SA286 works).

## Fix order and interactions

Single open finding. SA305 resolved `vendored-module-edits-undetected` for the update and status paths.

## Sound load-bearing decisions

- Closed-world emission test derives its scope from `get_generator_emission_mapping`, not a list.
- Contract-vintage check derives its watched set from the emission mapping.
- Managed-file drift hashes (`project_state_hashes.py`).
- SA286's manifest-declared CI env and operations text rendered into managed files.

## Watchlist

| ID | Concern | Trigger | 2026-10-20 evaluation |
|---|---|---|---|
| `core-holds-module-vocabulary` | Core/CLI name modules | 13th module, new module-named apply step | not fired (12 modules; SA287 moved option validation to a generic hook) |
| `manifest-dsl-vocabulary-growth` | DSL gains a keyword per module need | a keyword added for one module | not fired (SA291 throttle scopes is generic) |
| `session-advisory-lock-pooling` | Billing mutex is a session advisory lock | pooled `DATABASE_URL` | not fired (no pooler config found) |
| `modules-english-only` | Module pages English-only | SA153/154 needs Spanish module page | not fired |
| `two-filesystem-lock-implementations` | `advisory_lock.py` and `dr_engine/_lock.py` | a third implementation | not fired (still two) |
| `ci-provisioning-hand-pins` | Hand-pinned CI residue | 13th module | not fired |
| `trigger-inputs-legacy-name` | Legacy name of e2e allowlist | a gate skipped on it | not fired (not re-checked in depth) |
| `subscription-status-single-writer` | One writing module | second provider/outside writer | not fired (one writer: `_subscription_checkout.py`) |

## Rejected candidates

- `cca2eac9` existing-recipient path as a new bypass of adoption — killed: it validates slug,
  package, theme and resolved module set against the donor and blocks on mismatch.

## Questions that would change the ranking

- Will a second generated project go live before 1.0? Yes → keeps rank 1 and kills option 3.

## Reconciliation log

- 2026-10-20 — `generated-file-ownership-unmodeled`: still-open (SA289 relocated API bases;
  resource paths remain; steps 46 → 53).
- 2026-10-20 — all nine watchlist items: carried (triggers not fired, evaluations above).
- 2026-10-21 — `vendored-module-edits-undetected`: resolved by SA305. `quickscale update`
  compares each embedded module with its recorded split commit and refuses a changed or
  unverifiable tree unless `--allow-local-changes` is passed; `quickscale status` reports the
  same drift. `bap-web-new`'s hand edit is the trigger instance the new check detects.
