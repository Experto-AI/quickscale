# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Timeline & Tasks)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## General Introduction

**Purpose:** This document tracks the active development timeline, versioned milestone scope, and archived pointers for recent QuickScale releases.

**Content Guidelines:**
- Organize work by versioned milestones with clear deliverables and success criteria
- Include specific implementation tasks with technical requirements
- Provide timeline estimates and dependency relationships
- Track progress and update status as work is completed
- Focus on "when" and "what tasks" rather than "why" or "what"
- Reference other documents for context but avoid duplicating their content

**What to Add Here:**
- New milestone planning and release-specific task tracking
- Specific implementation tasks and acceptance criteria
- Timeline updates and progress tracking
- Resource allocation and team assignments
- Risk mitigation strategies and contingency plans
- Testing strategies and quality gates

**What NOT to Add Here:**
- Strategic rationale or competitive analysis (belongs in quickscale.md)
- Technical specifications or architectural decisions (belongs in decisions.md)
- User documentation or getting started guides (belongs in README.md)
- Directory structures or scaffolding details (belongs in scaffolding.md)

## Broad Overview of the Roadmap

QuickScale's roadmap is milestone-led. It tracks shipped release pointers, the current implementation line, and the next versioned scopes already tied to concrete repository work. Older phase labels still appear in some historical notes, but they are not the active roadmap structure.

## Current Milestone Summary

This table is the single milestone summary for shipped history and the active forward roadmap.

| Version | Status | Milestone | Details |
|---------|--------|-----------|---------|
| v0.71.0 | ✅ Completed | Plan/Apply system | Terraform-style configuration system complete |
| v0.72.0 | ✅ Completed | Plan/Apply cleanup | Legacy commands removed after the Plan/Apply rollout |
| v0.73.0 | ✅ Released | CRM module | API-first Django CRM with 7 core models and CLI integration; archived in changelog |
| v0.74.0 | ✅ Completed | React default theme | React + shadcn/ui baseline shipped |
| v0.75.0 | ✅ Completed | Forms module | Generic form builder with DRF API, spam protection, and GDPR anonymization |
| v0.76.0 | ✅ Released | Storage module | Cloud file hosting plus CDN-ready media infrastructure; archived in release note and changelog |
| v0.77.0 | ✅ Internal baseline | Backups module | Private local and optional private remote workflows, guarded BackupPolicy-admin local restore, and CLI restore; changelog-only historical baseline |
| v0.78.0 | ✅ Released | Notifications module | Transactional email foundation with app-owned rendering, recipient-granular tracking, and Anymail-backed Resend delivery; archived in release note and changelog |
| v0.79.0 | ✅ Released | Social and Link Tree module | Curated social links and embeds, backend-owned preview metadata, and React public pages for fresh `showcase_react` generations; older projects adopt them manually |
| v0.80.0 | ✅ Released | Analytics module | PostHog website analytics with flat mutable settings, service-style backend hooks, and fresh `showcase_react` starter support; existing projects adopt frontend snippets manually |
| v0.81.0 | ✅ Released | Beta-site migration maintainer tooling | Maintainer-only fresh-first and checkpoint-first in-place beta-site migration workflows; archived in release note and changelog |
| v0.82.0 | ✅ Released | Disaster recovery & environment promotion | Public `quickscale dr` capture/plan/execute/report workflows with `snapshot_id` lookup, resumable capture/execute, rollback pins, conservative env-var sync, and source-side media sync; archived in release note and changelog |
| v0.83.0 | ✅ Released | Hardening release | Repo-wide hardening release published; archived in the release note and changelog |
| v0.84.0 | ✅ Released | Backups hardening release | Backup lifecycle hardening and runtime/tooling refresh archived in the release note and changelog |
| v0.85.0 | ✅ Released | Billing module | Stripe-backed one-time credit purchases and recurring subscriptions, credits-first Django ledger, planner/apply readiness, module-owned pricing and dashboard pages, and starter-theme billing links; archived in release note and changelog |
| v0.86.0 | ✅ Released | Organizations module | Multi-tenancy with Solo/SaaS runtime modes, org-scoped billing, billing wiring fix + wiring regression guard, and self-service onboarding; archived in release note and changelog |
| v0.87.0 | 🟡 In progress | Hardening release | Cross-cutting theme hardening across the refreshed showcase_html shell/navigation/dashboard and remaining showcase_react analytics parity work |

**Legend:**
- ✅ = Completed, released, or internally baselined
- 🟡 = In progress in repo or release-prepared, but not yet tagged/published
- 📋 = Planned/Not Started

**Status:**
- **Current release:** v0.86.0 is the published release
- **Active milestone:** v0.87.0 Hardening release
- **Plan/Apply System:** v0.68.0-v0.71.0 - Terraform-style configuration ✅ Complete
- **SaaS Parity:** v0.86.0 ✅ Complete - auth, billing, organizations modules shipped on top of the notifications foundation

## Notes and References

**Target Audience:** Development team, project managers, stakeholders tracking progress

- **Completed Releases:** See [CHANGELOG.md](../../CHANGELOG.md)
- **Release doc layout:** [CHANGELOG.md](../../CHANGELOG.md) is the canonical history index; for each published release, `docs/releases/release-vX.XX.X.md` is the single official release note linked from the GitHub tag and release PR; the roadmap tracks active and unreleased release status until that note exists
- **Technical SSOT**: [decisions.md](./decisions.md)
- **Scaffolding SSOT**: [scaffolding.md](./scaffolding.md)
- **Strategic Vision**: [quickscale.md](../overview/quickscale.md)
- **Commercial Models**: [commercial.md](../overview/commercial.md)
- **Release Documentation Policy**: [Release Summary Template](./release_summary_template.md) for the single public release-note workflow

## ROADMAP
List of upcoming releases with detailed implementation tasks:

---

After release closeout, keep only a concise pointer in the roadmap. Put canonical history in [CHANGELOG.md](../../CHANGELOG.md), and for published releases add `docs/releases/release-vX.XX.X.md` as the single official release note linked from the GitHub tag and release PR. Keep unreleased closeout status in the roadmap until that release note exists.

---

### v0.86.0: Organizations Module

**Status**: ✅ Released — archived in [release note](../releases/release-v0.86.0.md) and [changelog](../../CHANGELOG.md)

**Design document**: [`docs/technical/organizations.md`](organizations.md)

---

### v0.87.0: Hardening Release

**Status**: 🟡 In progress

**Scope**: Cross-cutting theme correctness fixes discovered after v0.86.0.

**showcase_react gaps (analytics)**
- [ ] Wire analytics into `window.__QUICKSCALE__.modules` in the main shell template (`main.tsx.j2`)
- [ ] Add analytics to the TypeScript module registry (`useModules` hook)
- [ ] Add Analytics dashboard card to `Dashboard.tsx.j2`

**showcase_html hardening**
- [x] Refresh `showcase_html/templates/base.html.j2` and `showcase_html/static/css/style.css.j2` toward the lighter `showcase_react` shell while remaining server-rendered and JS-free
- [x] Simplify `showcase_html/templates/components/navigation.html.j2` to a topbar-style nav while keeping auth-aware links and starter-safe module entry points
- [x] Refresh `showcase_html/templates/index.html.j2` so the home/dashboard hierarchy aligns more closely with the `showcase_react` dashboard structure
- [x] Update narrow generator assertions for the refreshed HTML starter shell
- [x] Add Social module card to `showcase_html/templates/index.html.j2` dashboard
- [x] Add Orgs module card to `showcase_html/templates/index.html.j2` dashboard
- [x] Fix empty-state condition to include `quickscale_modules_social` and `quickscale_modules_orgs`
- [x] Add Social navigation section to `showcase_html/templates/components/navigation.html.j2`
- [x] Add Orgs navigation section to `showcase_html/templates/components/navigation.html.j2`
- [x] Create `showcase_html/templates/social/link_tree.html.j2` — server-rendered public link tree using `.qs-social-*` CSS classes
- [x] Create `showcase_html/templates/social/embeds.html.j2` — server-rendered public embeds gallery
- [x] Add `social_link_tree_view` and `social_embeds_view` to `generator/templates/project_name/views.py.j2` (showcase_html block)
- [x] Add `/social/` and `/social/embeds/` URL patterns to `generator/templates/project_name/urls.py.j2` (showcase_html block)

# QuickScale — Architectural Review Findings

Scope: structural / architectural / systemic issues across the monorepo (`quickscale_core`, `quickscale_cli`, `quickscale_modules`, build & release infrastructure). Deliberately excludes line-level style issues. Findings are ordered by architectural significance, not ease of fixing.

> **How to read the assessments:** Each finding ends with an `**Assessment:**` block that gives a verdict (Worth pursuing / Partially / Defer), the implementation phase, and the concrete first step. The [Phased Implementation Plan](#phased-implementation-plan) at the bottom converts all assessments into a `- [ ]` checklist.

Verified metrics used throughout (measured, not estimated):

| File | Lines |
|---|---|
| `quickscale_modules/backups/src/quickscale_modules_backups/services.py` | 4,229 |
| `quickscale_cli/src/quickscale_cli/commands/apply_command.py` | 2,539 |
| `quickscale_cli/src/quickscale_cli/beta_migration.py` | 2,451 |
| `quickscale_cli/src/quickscale_cli/commands/module_config.py` | 2,005 |
| `quickscale_cli/src/quickscale_cli/commands/dr_commands.py` | 1,319 |
| `quickscale_cli/src/quickscale_cli/commands/plan_command.py` | 1,229 |
| `scripts/check_quality.sh` | 1,281 |
| `quickscale_cli/src/quickscale_cli/commands/module_wiring_specs.py` | 700 |
| `Makefile` | 658 |
| `scripts/publish.sh` | 641 |

---

## 1. The module system is a half-built plugin architecture — the CLI secretly hardcodes every module

This is the deepest structural problem in the codebase, because it silently negates the system's own central design.

The architecture *claims* modules are self-describing: each module ships a `module.yml` manifest (config schema with mutable/immutable options, types, defaults, validation choices, `django_settings` mappings, dependencies, `django_apps`). `quickscale_core/manifest/` exists precisely to load and validate these manifests. This is plugin-architecture shape: "drop in a manifest, the system wires it."

In reality, the CLI re-implements every module by hand, in four parallel places:

1. **Seven hand-written contract files** — `quickscale_cli/src/quickscale_cli/{auth,analytics,billing,notifications,backups,social,crm}_contract.py` — each redeclaring option keys, defaults, allowed values, and legacy-key normalization that the manifest already declares. Example: `auth_contract.py` hardcodes `AUTH_EMAIL_VERIFICATION_VALUES = ("none", "optional", "mandatory")` and `session_cookie_age: 1209600` — both already in `quickscale_modules/auth/module.yml` (`validation.choices` and `default`).
2. **`module_wiring_specs.py` (700 lines)** — per-module Python functions (`_auth_wiring`, etc.) that hardcode each module's Django settings derivation (e.g., the auth function derives `signup_fields`/`login_methods` from `authentication_method`), importing constants from all seven contract files.
3. **`module_config.py` (2,005 lines)** — per-module interactive configurators.
4. **`implied_module_defaults.py`** and the catalog — more per-module knowledge.

Consequences:

- **Adding a module is O(CLI files), not O(1 manifest).** The manifest system pays its complexity cost (loader, schema, validation) without delivering its benefit (extensibility). You maintain both the declarative layer and the imperative duplicate.
- **Two sources of truth that can disagree silently.** If `module.yml` changes a default and the contract file doesn't, behavior depends on which code path consumed which source — and nothing checks consistency. (CI has a "module-manifest-contract" job, which is an admission this drift is real, fought with tests instead of removed by design.)
- **Third-party modules are structurally impossible** despite the manifest format implying otherwise. The "Compose your Django SaaS" pitch is bounded by what the CLI authors hand-wire.

Recommendation: pick a side. Either (a) make the manifest the only source — extend `module.yml` with the derivation logic that genuinely needs code (or accept a small per-module Python hook *shipped in the module*, discovered by the CLI), or (b) delete the manifest schema and own that modules are first-party-only and hardcoded. The current halfway state is the worst of both.

**Assessment — Worth pursuing, Phase 4.** Highest structural value but highest effort. The manifest system pays its full complexity cost without delivering its benefit. Start incrementally: pick the simplest module (analytics or forms), extend its `module.yml` with derivation hints, and delete that contract file. Each contract file removed reduces the O(CLI files) cost of adding a new module by one step toward O(1 manifest). Third-party module support only becomes real when this is complete.

## 2. Versioning is theater: the distribution mechanism ignores the versions everyone maintains

Modules carry PyPI-style versions in *two* places each (`pyproject.toml` and `module.yml`), there's a root `VERSION` file, a `scripts/version_tool.sh` sync tool, and `make version-check`. Yet actual module distribution is **git subtree from split branches** — which is content-addressed by commit and ignores package versions entirely.

The observable result is exactly what this design predicts — uncontrolled drift:

```
root/core/cli:  0.86.0          orgs:    0.86.0
billing: 0.85.0   analytics: 0.80.0   social: 0.79.0
notifications: 0.78.0   backups: 0.77.0   storage: 0.76.0
forms: 0.75.0   blog/crm/listings: 0.73.0   auth: 0.71.0
```

`auth` is 15 minor versions behind root. This isn't sloppiness — it's structural: **nothing consumes these versions, so nothing forces them to be correct.** Meanwhile they look authoritative (they're in manifests the loader parses, in user-visible `module.yml`, in `.quickscale/config.yml` state). A user inspecting state will reason from version numbers that mean nothing about what `git subtree pull` will actually fetch.

A second-order symptom: subtree split commits leak into main history (`git log` shows `Split 'quickscale_modules/orgs/' into commit '3ebae68…'` merges on the main line), so release plumbing is entangled with development history.

Recommendation: either make module versions *mean something* (cut subtree split branches only at tagged versions; record the embedded commit SHA + version in state and verify on update) or remove per-module versions and key everything off the monorepo version. Today's scheme actively misleads.

**Assessment — Partially worth pursuing, Phase 3/4.** At minimum, surface version drift as a warning at `apply`/`update` time — users should not be able to reason from version numbers that mean nothing. That warning is Phase 3 and bounded. The full structural fix (tagging subtree splits at versioned commits, recording embedded commit SHA in state) is Phase 4 and should follow Finding 1's module boundary work.

## 3. You are building a miniature Terraform without admitting it — and the state is split across owners

The plan/apply workflow has all the parts of a desired-state reconciler:

- **desired state**: `quickscale.yml` (user-edited)
- **applied state**: `.quickscale/state.yml` (schema in `quickscale_cli/schema/state_schema.py`)
- **delta engine**: `quickscale_cli/schema/delta.py`
- **a second state file**: `.quickscale/config.yml`, owned by *core* (`quickscale_core/config/module_config.py`) tracking module prefixes/branches/versions
- **crash-recovery state**: `apply-recovery.yml` plus git-index snapshot logic inside `apply_command.py`
- **generated artifacts that are themselves state**: `settings/modules.py`, `urls_modules.py`

Three structural problems follow:

1. **Split state ownership.** CLI owns `state.yml`, core owns `config.yml`, both describe overlapping facts about embedded modules. There is no single reconciliation point; a bug or interrupted run can leave them disagreeing, and no command audits cross-file consistency.
2. **No drift detection against reality.** The real system state is the user's working tree (which they're explicitly *encouraged* to edit — "100% yours"). Nothing verifies that `state.yml` still describes the project: a user can delete `modules/auth/`, hand-edit `settings/modules.py` (marked DO-NOT-EDIT but unenforced), or rewrite `urls.py`, and the next `apply` will reason from fiction. Terraform solved this with `refresh`/`plan` against reality; QuickScale's `plan` only diffs YAML against YAML.
3. **Recovery logic is embedded in the largest command file** (apply, 2,539 lines) rather than being a first-class state machine, which guarantees it grows hair with every new failure mode.

Recommendation: unify the state files under one schema/owner, and add a cheap `quickscale doctor`-style reconciliation (hash the managed files at apply time, compare on next run) so drift is *detected* even if not repaired.

**Assessment — Worth pursuing, Phase 3.** Start with unifying state files under one schema/owner — bounded change, eliminates the cross-file consistency gap with no user-visible breakage. Drift detection via file hashing at apply time is a contained addition that prevents the worst silent-corruption scenarios. The full write-ahead journal redesign (write intent → act → commit) is deferred.

## 4. Two contradictory philosophies for touching user-owned code coexist

The codebase contains both:

- **The right mechanism** — `quickscale_core/module_wiring.py`: fully regenerated, clearly-marked machine-owned files (`settings/modules.py`, `urls_modules.py`). Deterministic, idempotent, no parsing of user code.
- **The wrong mechanism** — `quickscale_core/settings_manager.py` (268 lines): regex patching of the *user-owned* `settings.py` (`re.sub` on `^(SETTING\s*=\s*).*$` with hand-rolled Python-value serializers `_dict_to_string`/`_set_to_string`…). This breaks on multi-line values, matches commented-out settings, and mutates a file the product promise says belongs to the user.

The deep issue isn't that regex is fragile (any LLM will tell you that); it's that **the project already built the correct alternative and didn't migrate.** Every mutable module option mapped to a `django_setting` in `module.yml` could be routed through the regenerated `modules.py` (the generated `base.py` already imports module wiring), making `settings_manager.py` deletable. Two write-paths into Django settings means every config change has two possible semantics depending on which path the option takes.

Related smell, same family: `module_wiring.py` builds Python source via `pformat()` and f-string `path("{route}", include("{target}"))` lines — fine for today's controlled inputs, but it's unescaped code generation that will bite as soon as routes come from manifests of less-trusted modules (see Finding 1's third-party ambition).

**Assessment — Worth pursuing, Phase 2.** The correct mechanism already exists and is used for most settings. Route all mutable module options through `modules.py` regeneration and delete the regex path in `settings_manager.py`. Low effort relative to the corruption class it eliminates. The code-generation escaping smell (f-string route construction in `module_wiring.py`) is a note to track as Finding 1 progresses toward third-party modules — not urgent while modules are first-party only.

## 5. The backups module is a platform/ops engine wearing a Django-app costume — and it's shipped into every client project

`backups/services.py` is 4,229 lines — **larger than the entire core generator package** — plus a ~700-line admin and 8 management commands. Its contents are not "app" concerns: PostgreSQL 18 binary-archive handling (`PGDMP` magic, hardcoded `_REQUIRED_POSTGRESQL_MAJOR = 18`), S3 offload, snapshot substrate with sidecar manifests, env-var portability manifests, promotion verification records, lockfiles, rollback pins. The CLI's `dr` commands drive it via `docker exec` + `QUICKSCALE_DR_TARGET_*` env vars.

Why this placement is structurally wrong:

1. **Distribution mismatch.** Modules are embedded by subtree into *user-owned* projects. So every client app permanently carries the full DR engine as editable source, and every bugfix to a 4,229-line safety-critical file must propagate via `git subtree pull` to each generated project, one by one — with possible merge conflicts against user edits. DR tooling is exactly the code you want centrally updated; it's been put in the one place updates are hardest. (The version-drift finding compounds this: `backups` is pinned at 0.77.0 while the CLI orchestrating it is 0.86.0 — the contract between `dr_commands.py` and the management commands it calls is verified by nothing.)
2. **Inverted trust boundary.** Restore (a destructive, environment-level operation) is initiated from inside the Django admin of the app being restored — the component most likely to be broken or compromised in the very scenario where you need DR. The guardrails (exact-filename confirmation, env gate) are policy patches over an architectural placement issue.
3. **Hidden cross-process API.** CLI↔module communication via management-command JSON output + env-var conventions is an unversioned protocol spread across two packages, testable only end-to-end.

Recommendation: split the snapshot/restore *engine* into a CLI/core-owned library (centrally updatable, version-locked to `dr_commands.py`), leaving only the thin Django-facing surface (models, policy admin, scheduled-trigger command) in the embeddable module.

**Assessment — Worth pursuing, Phase 4.** Structurally correct and important for safety-critical update propagation, but high effort and disruptive to every existing generated project. Defer until Finding 1's module boundary work clarifies what belongs in the embeddable layer. In the meantime, surface the `backups` version drift (0.77.0 vs CLI 0.86.0) as an explicit warning per Finding 2's partial fix.

## 6. The stated layering is inverted: "core" is the small library, the CLI is the actual product

Naming and docs imply `quickscale_core` holds the engine and `quickscale_cli` is a shell. The measured reality is the opposite: core's generator is ~580 lines of Jinja2 mappings, while the CLI contains the orchestration brain — apply state machine (2,539), wizard (1,229), module ops (~1,200), DR (1,319), Railway (~1,200), wiring specs (700), configurators (2,005). Even `quickscale.yml`'s schema — the system's central contract — lives in the *CLI* (`quickscale_cli/schema/config_schema.py`), as does the delta engine.

This matters beyond aesthetics:

- Anything that wants to drive generation programmatically (CI, a future web UI, tests in other packages) must import a Click-oriented package and untangle business logic from `click.echo`/prompt flow.
- Core's `settings_manager.py` reads `quickscale.yml` *by hand* with `yaml.safe_load` because the real schema is upstream in the CLI — a quiet inversion where the lower layer re-parses, unvalidated, what the upper layer owns.
- `beta_migration.py` (2,451 lines of maintainer-only, owner-workflow tooling, wired to `scripts/beta_migrate.py`) ships inside the end-user CLI package, inflating the product surface with code no user should run.

Recommendation: move `config_schema`/`state_schema`/`delta` and the apply orchestration into core (or a new `quickscale_engine`), leave Click/UX in the CLI; extract `beta_migration` to `scripts/` or a dev-only package.

**Assessment — Partially worth pursuing, Phase 3.** Move `config_schema`/`state_schema`/`delta` to core now — bounded, high ROI, enables the engine to be tested and driven without importing Click. Extract `beta_migration.py` to `scripts/` separately; it has no end-user business in the distributed CLI package. Hold the full apply-orchestration rebalancing for after Finding 1's contract-file elimination, when the scope is clearer.

## 7. The compatibility window is dangerously narrow for a generator whose output must outlive it

The whole stack pins `python >=3.13,<3.15`, `Django >=6.0.5,<6.1.0`, and hardcodes PostgreSQL 18 (refusing other majors). For an internal tool that's a choice; for a generator whose pitch is *user-owned, long-lived client projects*, it's a structural liability:

- Generated projects inherit bleeding-edge pins at their *birth* and then are owned by clients who won't track the generator's upgrades. Every generated project is born with an expiry date.
- The DR/backups path hard-fails on PostgreSQL ≠ 18, so the *safety tooling* is the most environment-brittle component — precisely backwards.
- Docs already drift from reality: README badge says "Python 3.14+", `pyproject.toml` says `>=3.13,<3.15`.

Recommendation: decouple the generator's own runtime requirements from the *generated project's* requirements (they are conflated today), and widen the generated-side window deliberately.

**Assessment — Defer, monitor.** Urgent only if users report version conflicts. The one bounded near-term action: separate the generator's own version pins from the generated-project template pins in `pyproject.toml.j2` so they can diverge independently — a template edit, not a structural change. Hold the broader window-widening investment until there is real demand from generated-project users.

## 8. The quality gate is being gamed by its own incentives (Goodhart's law, visible in filenames)

The repo enforces 90% mean / 80% per-file coverage. The codebase responds with test files literally named for the metric: `test_generator_coverage.py`, `test_loader_coverage.py`, `test_schema_coverage.py`, `test_settings_manager_coverage.py` — the first one's docstring is "Additional tests … covering uncovered branches." These are branch-chasing tests organized around the *instrument*, not behavior; they cement current implementation details (mock-heavy, branch-targeted) and make refactoring — which several findings above require — more expensive while providing weak regression value.

Adjacent infra symptoms of the same metric-first culture: coverage artifacts tracked in git (`coverage.json`, `pytest_cov_log.txt`), a 1,281-line `check_quality.sh` integrating vulture/radon/pylint with baseline files, and a 658-line Makefile using `MAKECMDGOALS`-rewriting tricks (`$(eval $(SECTION_FLAG_ARGS):;@:)`) to fake flag parsing — build logic that has outgrown Make and shell.

Recommendation: merge the `*_coverage.py` tests into the behavioral suites (or delete redundant ones), untrack the artifacts, and move the Makefile's shell loops (per-module PYTHONPATH assembly, section filtering) into a small Python task runner where they can be tested.

**Assessment — Worth pursuing, Phase 1.** Untracking `coverage.json`/`pytest_cov_log.txt` from git is a one-liner. Merging or deleting `*_coverage.py` tests reduces refactoring drag before the structural changes in Phases 2–4. The Makefile Python-runner migration is lower priority — tackle it when it causes a real pain point, not proactively.

## 9. Release engineering rewrites package metadata with sed at publish time

`scripts/publish.sh` (641 lines) and `install_global.sh` mutate `pyproject.toml` files during release: path deps (`{path = "../quickscale_core"}`) are textually replaced with version constraints (`^0.86.0`), READMEs copied around, then restored. This means **the artifact that gets published is never the artifact that was tested** — CI tests the path-dep graph; PyPI users get a sed-edited dependency graph that only existed transiently inside a shell script. Combined with Finding 2 (versions that nothing validates), a publish that pins `quickscale-cli` against a `quickscale-core` version with a different API is detectable only by end users. Poetry's own mechanisms (or hatch/uv workspaces, or `poetry-monorepo`-style plugins) exist to make the dev graph and publish graph the same declared object.

**Assessment — Worth pursuing, Phase 3.** The CI-tests-one-thing/users-get-another gap is a real correctness problem. Move to Poetry workspace or uv workspace mechanisms so the dev and publish dependency graphs are the same declared object. Medium effort with clear tooling support; pairs well with any version-correctness work from Finding 2.

## 10. Documentation has become load-bearing architecture, with explicit precedence rules as a symptom

The repo needs *meta-rules about which document wins*: README states "If package README text differs from repo docs, README.md and decisions.md win." A precedence rule between prose documents is a structural confession that the same facts live in many places (README / START_HERE / GLOSSARY / decisions.md / scaffolding.md / per-package READMEs / per-directory `adaptive.rules.md` AI-hydration files / `ai_hydration_topology.md`, which is a ~250-line *authority contract about the other documents*). The drift this predicts is already observable (Python version, Finding 7; "implemented modules" lists vs the actual `teams` stub). The AI-context apparatus (`adaptive.yml`, scattered `adaptive.rules.md`) multiplies the surfaces that must be kept consistent by hand.

Recommendation: generate the duplicable facts (version, module list & readiness, support matrix) from code/manifests into the docs, and collapse the README/START_HERE overlap; keep decisions.md as the only prose authority.

**Assessment — Defer.** Low ROI for current team size. The precedence rules are annoying but not breaking anything. The natural fix — auto-generating version and module-list facts from manifests — falls out of Finding 1's work anyway. Revisit only if doc drift causes real onboarding failures.

---

## What is genuinely good (and worth protecting)

- **Module isolation discipline is real and rare**: zero cross-module imports across 12 modules; optional coupling done via settings-gated `import_module()` (forms→analytics/notifications, backups→storage); only one declared hard dependency (billing→orgs). This is the strongest architectural asset in the repo.
- **The managed-wiring pattern** (`modules.py` / `urls_modules.py`, regenerate-don't-patch) is the correct idea — it should *win* over `settings_manager.py`, not coexist with it (Finding 4).
- **No layering violations in imports**: core never imports CLI; clean schemas→loaders→managers flow inside core.
- **Migrations hygiene** across modules is clean (1–4 each, forward-only).
- **Atomic generation** (temp-dir then move) and explicit file mappings make the generator's behavior auditable.

## Priority summary

| # | Finding | Risk | Effort to address |
|---|---|---|---|
| 1 | CLI hardcodes per-module contracts, bypassing manifests | Correctness drift + blocks extensibility | High, incremental |
| 2 | Versions unconsumed by subtree distribution → drift | Misleading state, untestable compat | Medium |
| 3 | Split state ownership, no drift detection vs reality | Apply corrupts on edited projects | Medium |
| 5 | DR engine embedded in user-owned module code | Safety-critical update propagation | High |
| 4 | Dual settings-write paths (regex vs regeneration) | Silent settings corruption | Low–Medium |
| 6 | Engine logic & schemas live in CLI package | Reuse/testing friction | Medium |
| 7 | Narrow runtime window inherited by generated projects | Generated-project longevity | Medium |
| 9 | sed-rewritten metadata at publish time | Untested published artifacts | Medium |
| 8 | Coverage-gamed tests, shell-heavy build | Refactoring drag | Low |
| 10 | Doc precedence rules / duplication | Drift, onboarding confusion | Low |

---

# Part 2 — Deeper findings (reconciliation semantics, hidden contracts, test topology)

These findings come from tracing actual control flow through `apply_command.py`, the module lifecycle commands, the DR env classification, the theme templates, and the test suites — i.e., behavior that emerges from the *interaction* of components rather than any single file.

## 11. `quickscale.yml` is not a desired-state document — apply has asymmetric semantics that contradict the plan/apply naming

The plan/apply vocabulary promises Terraform-like declarative reconciliation. Tracing `_handle_delta_and_existing_state` in `apply_command.py` shows three different semantics coexisting in the same file:

- **Adding a module**: declarative. Add it to `quickscale.yml`, run `apply`, it embeds.
- **Removing a module**: *forbidden declaratively.* `_abort_for_config_driven_module_removals()` hard-aborts with "config-driven module removals are not supported" and instructs the user to run imperative `quickscale remove` first, then re-run `apply`.
- **Changing an immutable option**: hard abort, with guidance to `remove` + re-add the *entire module* — a destructive round-trip (data migrations, user edits to module code lost) for a one-line config change.

So the same file is a desired-state spec for additions, a trap for removals, and a tombstone for immutable options. Users must learn which mental model applies per edit-type, and the failure is discovered only at apply time. Either commit to reconciliation (implement declarative removal with the same safety checkpoints `remove` already has — it even has a snapshot mechanism, see Finding 13) or rename the workflow to stop promising it.

**Assessment — Worth pursuing, Phase 2/3.** The forced remove+re-add round-trip for a single immutable option change is a real data-loss risk (data migrations lost, user edits to module code lost). Implement declarative removal in apply using the snapshot safety that `quickscale remove` already has — the mechanism exists, it just is not wired into the apply path. At minimum, Phase 2: emit a clear safe-path error at apply time that walks the user through the exact sequence without losing data.

## 12. Apply's crash-recovery snapshots the *wrong* state, and the real-world/state.yml write gap is structural

The apply sequence is: embed modules (each one **git-committed individually** into the user's repo) → regenerate wiring → sync `.env` → sync dependencies → poetry lock/install → start Docker → run migrations → **only then** write `.quickscale/state.yml` (`_finalize_apply_state`, end of `_execute_apply_steps`).

Two consequences:

1. **The recovery state is built from `ctx.existing_state` — the state captured *before* apply began** (`_abort_after_post_embed_failure(ctx, embedded_modules, …)` passes `ctx.existing_state`). If modules A and B embed successfully (already committed to git) and *wiring regeneration* then fails, the recovery file describes a world where A and B don't exist — while the git history says they do. On retry, the delta engine recomputes `modules_to_add` from a state that omits A/B, but the subtree prefixes already exist; depending on which check fires first, the retry can skip dependency-sync for already-embedded modules, leaving `pyproject.toml` without the module's dependencies — a project that imports packages it never declared.
2. **The crash window spans every externally-visible mutation.** Docker containers started, database migrated, git commits created, `poetry.lock` rewritten — all before the single state write at the end. A crash anywhere in that span produces a project whose observable reality (containers, migrated schema, commits) is invisible to the next apply's delta computation. This is the precise inverse of journaled systems (write intent → act → commit), and it's not an implementation accident — there is no write-ahead structure anywhere in the flow.

Related: apply *creates commits in the user's repository* ("Add module: X" checkpoint commits, plus auto-committing dirty `quickscale.yml`/state files) because `git subtree` demands a clean tree. The tool taking authorship inside the user's repo is a real product decision currently buried as an implementation detail of subtree.

**Assessment — Worth pursuing, Phase 2.** The `_abort_after_post_embed_failure` state-capture bug is concrete and fixable now: pass the post-embed state (reflecting successfully-embedded modules) instead of `ctx.existing_state`. The wide crash window (state.yml written only after Docker start + migrations) is a larger write-ahead redesign — deferred, but the immediate recovery-state bug should not wait for it.

## 13. Rollback rigor is inconsistent across the three module-lifecycle commands — the most dangerous one has the least protection

Comparing the three commands that mutate an existing project's `modules/` tree:

| Command | Pre-mutation snapshot | Rollback path | Version check before acting |
|---|---|---|---|
| `remove` | Yes — snapshots all mutable files before operating | Yes | n/a |
| `apply` (embed) | Partial — git index byte-snapshot + recovery YAML (flawed, Finding 12) | Partial | No |
| `update` (subtree pull) | **None** | **None** — "💡 Tip: Check for conflicts in modules/<name>/" | **No — version is read *after* the pull succeeds** |

`_update_single_module` runs `run_git_subtree_pull(...)` first, *then* reads the embedded module's version and writes it into config/state. So version follows code instead of constraining it — the inverse of a dependency system, and the mechanism by which Finding 2's version drift propagates into user projects unchecked. A subtree pull that lands a Python-3.14-only module into a 3.13 project succeeds silently; the failure surfaces later as an import error with no marker tying it to the update. Multi-module update stops on first failure, persisting versions for modules 1..k-1 and leaving the rest behind — a partial update with no record that it's partial.

Meanwhile the git-index snapshot machinery in apply (`_capture_git_index_snapshot` / `_restore_git_index_snapshot`) reads and rewrites `.git/index` as raw bytes with no lock against concurrent git activity — bespoke surgery on git internals where `git stash` / `git read-tree` plumbing would be both safer and simpler.

**Assessment — Worth pursuing, Phase 2.** `update` being the most dangerous command with the least protection is the wrong ordering. Add: (1) a pre-pull mutable-file snapshot mirroring what `remove` already does, and (2) a version/compat check before the subtree pull. Replace the `.git/index` raw-byte surgery in apply with `git stash`/`git read-tree` — both changes are well-bounded and independent.

## 14. Every write-path into user-owned files is text surgery; every read-path is a real parser

A pattern invisible in any single file but consistent across the codebase:

| Target | Read | Write |
|---|---|---|
| `pyproject.toml` (dependency sync) | `tomllib.load` (real parser) | `splitlines()` + string insertion; next-section detection by "line starts with `[` and ends with `]`"; hand-rolled `_render_toml_literal` serializer |
| `settings.py` (mutable options) | — | regex `re.sub` on `^(NAME\s*=\s*).*$` (Finding 4) |
| `.git/index` | `read_bytes` | `write_bytes` of a binary internal structure |
| `settings/modules.py` / `urls_modules.py` | — | full regeneration (the correct pattern) |

The dependency-sync writer is the most consequential: an inline table value containing `[...]` text, or a user-reorganized `[tool.poetry.dependencies]` section, mis-detects the section boundary and inserts dependencies into the wrong section — and there is **no post-write `tomllib` parse to validate the result**, even though the validating parser is already imported in the same module. One line (`tomllib.loads(new_content)` before writing) would convert silent corruption into a clean failure; the absence of that line in three separate writers indicates the asymmetry is a blind spot, not a tradeoff.

**Assessment — Worth pursuing, Phase 1.** One `tomllib.loads(new_content)` call per writer, before each file write. Zero architectural change; converts silent file corruption into a loud clean failure. The asymmetry is a blind spot, not a deliberate tradeoff — fix it immediately.

## 15. The module registry now exists in at least five places — and the fifth is compiled into every generated frontend

Beyond the four CLI-side copies (Finding 1), the *generated artifacts themselves* hardcode the module list:

- `useModules.ts.j2` declares a TypeScript interface enumerating all 11 modules (`auth`, `blog`, `listings`, `crm`, `forms`, `storage`, `backups`, `notifications`, `analytics`, `billing`, `social`) — baked into every generated React app.
- The React theme ships per-module components **unconditionally**: `OrgSwitcher.tsx`, `OrgStatePanel.tsx`, `FormRenderer.tsx`, `FormFieldRenderer.tsx`, `PublicSocialShell.tsx`, etc. The generator walks the entire theme tree with no module-awareness (its only "module" references are the two wiring-file mappings), so a project generated with *zero* modules still contains orgs/forms/social UI code, dead but owned by the user, gated at runtime by the hook.
- The HTML theme's `index.html.j2` and `navigation.html.j2` hardcode per-module cards (`{% if 'quickscale_modules_orgs' in settings.INSTALLED_APPS and settings.QUICKSCALE_MODE == 'saas' %}` …) — including literal route knowledge (`/orgs/`) that bypasses both URL reversing and the wiring system.
- The context-processor template hardcodes billing/orgs *route construction* (`f"/orgs/{org_slug}/billing/pricing/"`) — a third place (after `module.yml` and `social_contract.py`) where module URL topology lives.

Consequence: adding a module to the catalog requires touching generated-frontend templates in both themes; and **every already-generated project's UI hardcodes a module list frozen at generation time** with no update path (themes are explicitly generate-once). The themes are also divergent copies of each other — six Django templates exist at identical relative paths in both themes with different content, so every shared fix must be applied twice.

**Assessment — Partially worth pursuing, Phase 3.** For fresh generations: conditionally include per-module React components and TypeScript interface entries based on which modules are selected at generation time — the right fix, bounded to the generator templates. Already-generated projects are out of scope by design (themes are generate-once). The six-way Django template divergence across themes should be consolidated wherever templates are genuinely identical; each shared bug currently requires two fixes.

## 16. Dead runtime twin: core ships a 158-line module whose only production reference is a test asserting it must not be used

`quickscale_core/src/quickscale_core/context_processors.py` (158 lines: billing dashboard URL logic, orgs compatibility resolution, `load_config()` reads of `.quickscale/config.yml` at request time) is referenced by **nothing** in core, CLI, modules, or templates. The generated projects get a separate, diverged 42-line template copy instead. The only non-test acknowledgment of its existence is a guard in `test_react_theme_integration.py`:

```python
assert "quickscale_core.context_processors" not in base_py, (
    "settings/base.py must not reference quickscale_core context processors — "
```

— the codebase *actively asserts the module must never be used*, yet keeps it, and maintains a dedicated `test_context_processors.py` exercising it (which keeps it green under the 90% coverage gate — Finding 8's incentive problem producing tested dead code). This is residue of an abandoned architecture where `quickscale_core` was a runtime dependency of generated projects; the residue should be deleted before someone "fixes a bug" in the dead twin.

**Assessment — Worth pursuing, Phase 1.** Delete `quickscale_core/src/quickscale_core/context_processors.py` and `test_context_processors.py`. A test already asserts this module must never be used. This is the clearest win in the entire list: trivial effort, zero downside, removes the risk of investing effort in a file that must stay dead.

## 17. DR env-var portability is a name-pattern heuristic making a security decision the manifests already know the answer to

`dr_commands.py` decides which environment variables cross environment boundaries (e.g., develop → production) via string matching: a non-portable check (exact names, prefixes like `STRIPE_`/`AWS_`, substrings like `KEY`, `TOKEN`, `SECRET`, `URL`) followed by a portable allowlist (`_PORTABLE_ENV_PREFIXES = ("ACCOUNT_", "ANALYTICS_", …, "QUICKSCALE_", "SOCIAL_", …)`).

The ordering is correct (deny-checks run first — `DJANGO_SECRET_KEY` is caught by the `KEY` substring before `DJANGO_` makes it portable), but the *structure* is wrong in two ways:

1. **The allowlist auto-promotes by prefix.** Any future variable under a module prefix is portable-by-default unless its name happens to contain a magic substring. `SOCIAL_SIGNING_SALT` or `FORMS_WEBHOOK_HMAC` would be classified portable and synced across environments — a secrets leak determined by whether a developer's naming taste collides with a hardcoded token list.
2. **The knowledge already exists declaratively and is ignored.** Module contracts explicitly name their secret-bearing env vars (e.g., `BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION` in `backups_contract.py`); `module.yml` declares config→env mappings. The DR layer could derive portability from those declarations per-module, but instead re-derives it centrally from string shape — Finding 1's manifest-bypass pattern recurring at a *security boundary*. The classification lists also hardcode module prefixes (`ANALYTICS_`, `BLOG_`, `FORMS_`…), making this the sixth copy of the module registry.

**Assessment — Worth pursuing, Phase 3.** The prefix allowlist auto-promoting arbitrary future variables to portable is a latent secrets leak, not just a code smell. Derive portability from the module contract declarations that already name secret-bearing env vars — the information is available, it is just not consulted. Coordinate with Finding 1's contract-file work so portability declarations land in `module.yml`, eliminating the sixth copy of the module registry as a side effect.

## 18. The test suite is an hourglass with the product's defining contract at the missing waist

Mapping what each test layer actually exercises:

- **Module tests** (bottom, wide): real Django, real migrations, in-memory DB, ~no mocks. Solid.
- **CLI tests** (top, wide): ~95% mocked. The 3,936-line `test_apply_command_extended.py` patches `subprocess.run`, `_git_commit`, `_init_git`, `embed_module`, `ProjectGenerator` and asserts boolean returns and echoed strings. An **autouse** `mock_dependencies` fixture force-passes dependency checks for *every* CLI test, so the real dependency-detection code has zero coverage of its failure modes.
- **E2E** (the waist): `test_e2e_full_workflow.py` genuinely generates, installs, migrates, boots, and browser-tests a project — **with no modules embedded**. The "module smoke" e2e copies module sources with `copytree` (not `git subtree`), syncs dependencies, and asserts `import quickscale_modules_forms` succeeds — it never writes wiring, never boots Django with the module, never hits a module URL.

Therefore the sequence that *is the product* — generate → real subtree embed → wiring regeneration → Django boots → module URL responds — is executed by **no test anywhere**. Every defect class identified in Findings 12–14 (recovery-state mismatch, partial-update state, dependency-sync corruption) lives precisely in the mocked-out seams between layers. The suite's enormous mass (a 3.9k-line test file; 90% coverage gates) creates confidence pressure exactly where the verification is thinnest: the integration points are asserted by mock-call-counts, and the one heavy e2e validates the only path (module-less project) where the risky machinery doesn't run.

One real-subtree-embed e2e per theme (even just `auth`, the simplest full app) would cover more genuine risk than the entire mocked apply suite.

**Assessment — Worth pursuing, Phase 2.** The most impactful single addition to the test suite. One real e2e — generate → actual `git subtree` embed → wiring regeneration → Django boots → module URL responds — for the `auth` module in both themes catches the entire defect class from Findings 12–14 that lives in the mocked-out seams. Do this before the structural refactors in Phases 3–4 so regressions surface early.

---

## Updated priority summary (Parts 1 + 2 combined)

| # | Finding | Risk | Effort |
|---|---|---|---|
| 1+15+17 | Module registry duplicated 6× (CLI contracts, wiring specs, configurators, frontend hook, theme templates, DR env prefixes) | Drift compounds with every module; blocks extensibility | High, incremental |
| 12 | Recovery snapshots pre-apply state; state.yml written after all mutations | Corrupted projects on mid-apply failure | Medium |
| 18 | No test exercises the generate→embed→wire→boot contract | All integration defects ship blind | Medium — one real e2e |
| 13 | `update` has no rollback/pre-pull version check | Silent breaking updates in client projects | Medium |
| 17 | Env-var portability by name heuristic at a security boundary | Secret leakage across environments | Low–Medium |
| 14 | Parser-read / string-write asymmetry (TOML, settings, git index) | Silent file corruption | Low (validate-after-write) per site |
| 11 | Asymmetric apply semantics (declarative add, imperative remove, destructive immutables) | User data loss via remove+re-add round-trips | Medium |
| 16 | Dead-but-tested runtime twin in core | Wasted maintenance, wrong-file fixes | Trivial — delete |
| 2 | Versions unconsumed by subtree distribution → drift | Misleading state | Medium |
| 5 | DR engine embedded in user-owned module code | Safety-critical update propagation | High |

---

## Phased Implementation Plan

### Phase 1 — Quick wins (< 1 day each, no architectural risk)
- [x] Delete `quickscale_core/src/quickscale_core/context_processors.py` and `test_context_processors.py` (Finding 16)
- [x] Add `tomllib.loads(new_content)` post-write validation in all three TOML writers in dependency sync (Finding 14)
- [x] Untrack `coverage.json` and `pytest_cov_log.txt` from git; add both to `.gitignore` (Finding 8)
- [x] Merge or delete `*_coverage.py` branch-chasing tests; fold any real coverage into behavioral suites (Finding 8)

### Phase 2 — Correctness and safety fixes (contained, safety-critical)
- [ ] Fix apply recovery: pass post-embed state (not `ctx.existing_state`) to `_abort_after_post_embed_failure` (Finding 12)
- [ ] Replace `.git/index` raw-byte snapshot in apply with `git stash`/`git read-tree` plumbing (Finding 13)
- [ ] Add pre-pull mutable-file snapshot and version/compat check to `_update_single_module` before the subtree pull (Finding 13)
- [ ] Remove regex patching from `settings_manager.py`; route all mutable module options through `modules.py` regeneration (Finding 4)
- [ ] Add one real e2e test: generate → `git subtree` embed → wiring regeneration → Django boots → module URL responds, for `auth` in both themes (Finding 18)
- [ ] Emit a clear safe-path error at apply time for asymmetric cases (removal, immutable option change); implement full declarative removal if safe-path error is insufficient (Finding 11)

### Phase 3 — Architecture improvements (medium effort, bounded scope)
- [ ] Move `config_schema.py`, `state_schema.py`, and `delta.py` from `quickscale_cli` into `quickscale_core` (Finding 6)
- [ ] Extract `beta_migration.py` from the end-user CLI package to `scripts/` or a dev-only package (Finding 6)
- [ ] Unify `.quickscale/state.yml` and `.quickscale/config.yml` under one schema/owner (Finding 3)
- [ ] Add drift detection to apply: hash managed files at apply time, warn on mismatch at next run (Finding 3)
- [ ] Surface module version drift as a warning at `apply`/`update` time (Finding 2, partial)
- [ ] Fix `scripts/publish.sh` to use Poetry or uv workspace mechanisms instead of sed-rewriting `pyproject.toml` at publish time (Finding 9)
- [ ] Derive DR env-var portability from module contract declarations instead of name-pattern heuristics (Finding 17)
- [ ] Conditionally include per-module React components and TypeScript interface entries in generated apps based on selected modules (Finding 15)
- [ ] Consolidate Django templates duplicated at identical relative paths across `showcase_html` and `showcase_react` themes (Finding 15)

### Phase 4 — Long-term restructuring (high effort, requires planning)
- [ ] Incrementally eliminate per-module CLI contract files: extend `module.yml` with derivation hints, delete contract file per module — start with `analytics` or `forms` (Finding 1)
- [ ] Delete `module_wiring_specs.py` and per-module handlers in `module_config.py` once `module.yml` is authoritative (Finding 1)
- [ ] Split DR/backup engine into a CLI/core-owned library; leave only thin Django surface (models, policy admin) in the embeddable module (Finding 5)
- [ ] Make module versions meaningful: cut subtree split branches only at tagged versions; record embedded commit SHA + version in state (Finding 2)
- [ ] Decouple generated-project Python/Django/PostgreSQL pins from the generator's own runtime requirements (Finding 7)

### Deferred — Low ROI, monitor for escalation
- Finding 10 (documentation consolidation): defer until doc drift causes real onboarding failures; auto-generation of duplicable facts is a natural side-effect of Finding 1
- Finding 7 (widen compat window broadly): monitor for user-reported version conflicts before investing beyond the pin-decoupling note above
