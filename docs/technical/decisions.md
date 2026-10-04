# decisions.md

<!--
decisions.md — Authoritative Technical Policy Hub

WHAT THIS FILE IS: the repository-wide SSOT for rules, constraints, tie-breakers,
prohibitions, and technical document ownership. Every entry must be a statement
someone could *violate*.

WHAT BELONGS HERE: architectural decisions with their rationale; cross-cutting
implementation rules; explicit prohibitions; the document-ownership map.

WHAT DOES NOT: status reports and "current state" narrative (CHANGELOG.md);
workflow walkthroughs and examples (user_manual.md); timelines and open work
(roadmap.md); structure/spec detail owned by a narrow companion doc under
docs/technical/. If a statement can only become "out of date" rather than
"violated", it belongs in one of those.

TARGET AUDIENCE: Maintainers, core contributors, community package developers,
CI engineers.
-->

# Technical Decisions (Authoritative)

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Decisions** (Authoritative)
> **Related docs**: [Scaffolding](scaffolding.md) | [Roadmap](roadmap.md) | [Glossary](../../GLOSSARY.md) | [Start Here](../../START_HERE.md)

**Purpose:** Repository-wide policy and tie-breaker hub for QuickScale architecture and development standards. Narrow companion docs under `docs/technical/` own the current implementation contract, validation policy, and structure references.

**Scope:** All first-party packages (core, CLI, themes, modules). Experto-AI and core contributors own these decisions.

**For what QuickScale currently ships** — CLI surface, feature matrix, runtime
pins, architecture boundaries — see
[implementation_contract.md](./implementation_contract.md). This file states the
rules that shipped surface must obey; it is not a description of it.

## Critical Rules

**Documentation Hierarchy:**
- ✅ decisions.md is authoritative - always wins conflicts
- ✅ `docs/technical/implementation_contract.md`, `validation_policy.md`, `generated_project_structure.md`, and `repository_layout.md` are the narrow-owner companion docs for current contract, validation, and structure detail
- ✅ Update decisions.md FIRST, then other docs
- ✅ Contributing guides: `docs/contrib/*.md`
- ✅ `CHANGELOG.md` is the canonical release history index for all versions
- ✅ Release notes: `docs/releases/release-vX.XX.X.md` are the single public-facing release document for a version and may exist either as a clearly labeled release-prepared artifact before publish or as the linked note after tag/release publication
- ✅ Use `docs/technical/release_summary_template.md` for every public release note, including prepared artifacts that are awaiting manual publish
- ✅ Public release notes stay reader-facing and outcome-oriented; keep maintainer-only closeout detail in the release PR or active roadmap section instead of a second repository doc
- ✅ Unreleased or internal-only versions stay in `roadmap.md` and `CHANGELOG.md` until a maintainer intentionally prepares the single public release note for that version or publishes the tag/release
- ❌ Do not maintain separate implementation/review release docs or release-archive trees
- ❌ Never contradict decisions.md elsewhere

**Package README Policy:**
- ✅ First-party packages (`quickscale`, `quickscale_core`, `quickscale_cli`) MAY include a local `README.md`
- ✅ Package READMEs are informational context for package-specific installation and boundaries
- ✅ Root `README.md` and `docs/technical/decisions.md` remain authoritative when any wording differs
- ✅ `quickscale_modules/*` MUST have README.md (distributed as standalone)
- ❌ Never treat package README.md files as authoritative architecture, scope, or policy documents

<a id="mvp-vs-post-mvp-scope"></a>
## Current Implementation Scope

See [implementation_contract.md § Current Implementation Scope](./implementation_contract.md#mvp-vs-post-mvp-scope) for the canonical current-contract summary and generated-output pointer. This file remains the tie-breaker for cross-cutting policy; that file owns the shipped-surface description.

## Architecture Decisions

### Module & Theme Architecture {#module-theme-architecture}

**Decision:** Modules and themes serve different purposes and use different
distribution mechanisms. Modules are ongoing runtime dependencies; themes are
one-time scaffolding.

<a id="integration-note-personal-toolkit-git-subtree"></a>
<a id="module-extraction-workflow"></a>

#### Modules — split-branch distribution

- ✅ Modules are developed on `main` in `quickscale_modules/`, published to mutable
  `splits/{module}-module` branches by the maintainer release tooling, sealed under
  identity-derived immutable version tags, and embedded by git subtree
- ✅ Users embed via `quickscale plan --add <module>` + `quickscale apply`, and
  update via `quickscale update`
- ✅ **The default embed path consumes the immutable
  `splits/<module>-module/<version>` tag — never a moving branch or the
  working tree.** Split branches are producer-side publication artifacts; the
  identity-derived tag is the released module ref. This is why release
  ordering is mandatory; see §[Module Version Lockstep](#module-version-lockstep)
  Rule 3.
- ✅ **A split tag becomes permanent at PyPI publication, not at push.** Before the
  core release for that version is published, `splits/<module>-module/<version>`
  has no external consumer, so a wrong tag is corrected by deleting it and
  resealing rather than by burning a version number. Seal → test → fix → delete
  the affected tags → reseal, until the release converges. Once the core tag is
  pushed and PyPI has the packages the version is permanent, and a defect is
  corrected by a new version. See §[Module Version Lockstep](#module-version-lockstep) Rule 4 for
  the correction procedure; the pre-publication loop is the intended way to
  converge, not a failure path.
- ✅ Modules are runtime dependencies (in `INSTALLED_APPS`), theme-agnostic, and
  backend-weighted; users can contribute improvements back via
  `quickscale push --module <name>`
- ❌ Modules are never tightly coupled to a theme

Workflow examples: [user_manual.md §4.3](./user_manual.md#43-planapply-commands).
Branch and generated-project layouts:
[repository_layout.md](./repository_layout.md) and
[generated_project_structure.md](./generated_project_structure.md).

#### Themes — generator templates

- ✅ `showcase_react` (React + TypeScript + shadcn/ui) is the **sole** supported
  and configured theme; the plan/apply CLI offers no other theme selection
- ✅ Themes are copied once at generation time (Jinja2 rendering); the user owns
  the generated code completely
- ✅ Any desired/state/recovery reference to `showcase_html` — or any other
  non-React theme — MUST fail closed before operational side effects
- ✅ Module releases MAY extend managed backend/runtime surfaces in existing
  projects, but newly scaffolded theme-owned routes, navigation, registries, and
  page source are guaranteed only on fresh generation or explicit manual adoption
- ❌ No embed/update path for themes — apply performs no automatic rewrite of
  user-owned files
- ❌ Vertical themes (CRM and similar) are not part of the shipped generator
  surface until a release note and this file explicitly add them

Theme-owned scaffolding that only fresh generations receive — the dormant PostHog
analytics helper and the Django-owned public `/social` and `/social/embeds`
entrypoints — is enumerated in
[generated_project_structure.md §React Starter Output](./generated_project_structure.md#react-starter-output).
Existing projects adopt equivalents manually; the backend-managed social transport
endpoints and settings wiring stay theme-agnostic.

The approved frontend stack (React 19+, TypeScript, Vite, pnpm, shadcn/ui,
Tailwind, React Router v7, TanStack Query, Zustand, React Hook Form + Zod,
Vitest, Playwright, ESLint + Prettier) is pinned in
[implementation_contract.md §Runtime Pins](./implementation_contract.md#runtime-pins-and-constraints).
Adding or swapping a frontend dependency requires a decision entry here.

#### Starter surface: billing and teams

- ✅ Generated starter output surfaces billing as a module flag only
  (`modules.billing`). Billing ships module-owned Django routes; QuickScale does
  not generate a starter-owned billing React page and does not rewrite existing
  project React files to adopt billing
- ✅ Billing SPA entry points (dashboard cards, sidebar navigation,
  `modulePaths.billing`, org-dashboard links) are restorable — restoring them is
  separate implementation work, not a blocked item
- ❌ Teams routes, flags, dashboard cards, and navigation stay excluded until
  teams ships as a valid public `quickscale plan` / `quickscale.yml` /
  `quickscale apply` selection

**Teams tie-breaker:** `teams` is not a shipped module and nothing is committed
— no timeline, no kickoff date. Its preserved planning note lives at
[docs/planning/teams.md](../planning/teams.md); the former README-only
placeholder directory under `quickscale_modules/` has been deleted.
Any [arch-audit.md](../others/arch-audit.md) finding whose horizon keys off "teams
kickoff" describes a condition that applies *if and when* teams is scheduled. Treat
every such finding as open-ended and deferred — not a roadmap item on a clock —
until a scheduling decision is recorded here. This rule is stated by trigger, not by
finding ID, so it survives audit regeneration.

#### Multi-org membership and org-switch

- ✅ Regular SaaS users belong to **exactly one** organization
- ✅ The server session (`ACTIVE_ORG_SESSION_KEY`) is the sole authority for org
  resolution for regular users
- ✅ VIEW-AS (superuser-only session override) is the sole path for operator
  org-scope debugging
- ❌ No org switcher in the user-facing UI
- ❌ No explicit-org API contract or session-sync endpoint — a client-side org
  parameter alongside a server-resolved session is a dual-authority defect

Future multi-org membership is not precluded, but requires revisiting this
decision and implementing the explicit-org API contract at that time.

Design detail: [organizations.md](./organizations.md). Isolation rules:
§[Multi-tenant SaaS Architecture](#multitenant-saas-architecture).

---

### Plan/Apply Architecture {#planapply-architecture}

**Architectural Decision:** QuickScale uses **Terraform-style declarative configuration** with distinct desired state and applied state tracking.

#### **Core Decision**

Projects are managed through two configuration files with clear separation of concerns:

| File | Purpose | Role |
|------|---------|------|
| `quickscale.yml` | Declared desired configuration | Input (what user wants) |
| `.quickscale/state.yml` | Applied state after execution | Sole authoritative applied-state store (output — what was actually done) |
| `.quickscale/config.yml` | Legacy module metadata | Compatibility input only (read-through imported when `state.yml` lacks consolidated sections; ignored when consolidated sections are present) |

#### **Desired State Schema** (`quickscale.yml`)

User-editable configuration file. See [plan-apply-system.md § Schema Definitions](./plan-apply-system.md#quickscaleyml-desired-state) for the canonical shape.

**Constraints**:
- ✅ Version-controllable (stored in git)
- ✅ `version` is the plan/apply schema version and is currently the string `"1"`
- ✅ User-editable and reviewable
- ✅ One file per project
- ✅ `project.slug` is the filesystem/service identity
- ✅ `project.package` is the Python import/package identity and MUST NOT be inferred from the project directory name
- ✅ Location: Project root

#### **Applied State Schema** (`.quickscale/state.yml`)

System-managed state file tracking what has been applied. `.quickscale/state.yml` is the sole authoritative applied-state store. See [plan-apply-system.md § Schema Definitions](./plan-apply-system.md#quickscalestateyml-applied-state--sole-authoritative-store) for the canonical shape, including the consolidated per-module tracking fields (`prefix`, `branch`, `installed_at`) and `managed_files` sub-section.

Legacy `config.yml` and `file_hashes.yml` are compatibility inputs only: they are read-through imported when the consolidated sections above are absent from `state.yml`, and ignored when consolidated sections are present. Leftover legacy files may remain on disk as ignored compatibility debris after a successful authoritative save.

**Constraints**:
- ✅ Auto-generated and auto-updated by `quickscale apply`
- ✅ Do NOT edit manually (system will overwrite)
- ✅ Uses the same schema version string `"1"`; installed module versions stay as per-module metadata inside state
- ✅ One file per project
- ✅ Preserve explicit `project.slug` and `project.package` identity in state
- ✅ Location: `.quickscale/state.yml`

#### **Installed Module Version Source**

- ✅ The installed version recorded for an embedded module MUST come from that module's embedded `modules/<name>/module.yml` `version` field
- ✅ `.quickscale/state.yml` stores that canonical manifest version for each installed module
- ✅ `.quickscale/state.yml` is the sole authoritative applied-state store; per-module tracking fields (`prefix`, `branch`, `installed_at`) and the `managed_files` sub-section consolidate what legacy `config.yml` and `file_hashes.yml` used to hold
- ✅ Legacy `.quickscale/config.yml` is a compatibility input only: read-through imported when `state.yml` lacks consolidated sections, ignored when consolidated sections are present; leftover legacy files may remain on disk as ignored compatibility debris after a successful authoritative save
- ✅ Package `pyproject.toml` version fields and any exported module `__version__` string MUST match `module.yml` when they exist
- ✅ Legacy `v`-prefixed stored versions normalize to the manifest form without the prefix

#### **Idempotency Requirements**

- ❌ NEVER re-execute already-applied modules
- ✅ Skip modules that are already embedded
- ✅ Only embed modules that appear in desired state but not in applied state
- ✅ Remove modules that were applied but no longer appear in desired state

#### **State Integrity**

- ✅ Write state file atomically (no partial writes)
- ✅ Include timestamps plus canonical installed module version/commit metadata for auditing
- ✅ Never repair state from manual edits — reject an invalid format outright
- ✅ Hold an advisory lock (`.quickscale/<name>.lock`, exclusive-create, fail-fast)
  around every `state.yml` read/modify/write so concurrent `apply` fails closed
  instead of racing
- ✅ Recovery state is separate: `.quickscale/apply-recovery.yml` holds the
  saga-model apply-recovery ledger and is not part of applied state

The apply execution sequence, the delta computation, and the declarative/
idempotent/incremental/traceable/recoverable properties they produce are described
in [plan-apply-system.md §Execution Order](./plan-apply-system.md#execution-order)
and [§State Management](./plan-apply-system.md#state-management). Workflow examples:
[user_manual.md §4.3](./user_manual.md#43-planapply-commands).
Generated layout: [generated_project_structure.md](./generated_project_structure.md#state-and-module-metadata).

### Module Configuration Strategy {#module-configuration-strategy}

**Rule:** Module configuration is declarative. `quickscale plan` selects modules
and writes `quickscale.yml`; module-specific values are set in `quickscale.yml`
(optionally captured interactively via `quickscale plan --configure-modules`);
`quickscale apply` materializes them.

- ✅ Plan/apply is the primary workflow — desired config lives in
  `quickscale.yml`, applied config is tracked in `.quickscale/state.yml`
- ✅ Apply owns the wiring: `INSTALLED_APPS`, module-specific settings,
  module URLs, and the initial migration
- ❌ The user never hand-edits `settings.py`, `urls.py`, or `INSTALLED_APPS` to
  install a module

Schema and worked examples:
[plan-apply-system.md §Schema Definitions](./plan-apply-system.md#schema-definitions) and
[user_manual.md §4.3](./user_manual.md#43-planapply-commands).

#### Per-module desired-config contracts

**Auth desired-config validation rule:** `quickscale.yml` is
validated against the canonical auth desired-config contract before
sanitize/post-init normalization runs. Legacy desired-config keys such as
`modules.auth.allow_registration` and `modules.auth.social_providers`, plus any
other non-canonical auth keys, are rejected at the `quickscale.yml` boundary.
The accepted desired-config contract is:

- `modules.auth.registration_enabled: true|false`
- `modules.auth.email_verification: none|optional|mandatory`
- `modules.auth.authentication_method: email|username|both`
- `modules.auth.session_cookie_age: <positive integer seconds>` (optional)

Already-written `.quickscale/state.yml` snapshots and state-derived managed
wiring remain tolerant of legacy auth keys during load/reapply so older
projects can preserve historical state while new desired config fails hard.
SA215 removes this tolerance: under §[Module Conventions](#module-conventions)
rule 6, retired keys fail hard in state as well.

**Storage URL rule:** `modules.storage.public_base_url` is the sole
public media URL setting for storage-backed assets. Helper-built blog/storage
URLs must use `public_base_url` when configured and fall back to `MEDIA_URL`
behavior in local development when it is blank. `custom_domain` is not part of
the supported storage contract.

**Backups contract rule:** `modules.backups` artifacts are private operational
files.

- ✅ Native PostgreSQL 18 custom dumps are the real disaster-recovery path for
  generated PostgreSQL projects, on both local Docker and Railway
- ✅ JSON artifacts are **export-only** — acceptable for non-PostgreSQL
  development/test fixture export and operator inspection
- ✅ Destructive restore is guarded on both supported surfaces: BackupPolicy-admin
  restore requires exact filename confirmation plus the environment gate; CLI
  restore keeps its existing syntax under the same guardrails
- ✅ Scheduled execution is command-driven only (`manage.py quickscale_backups_create
  --scheduled`, or an equivalent platform cron job)
- ✅ Private-remote credentials are referenced by environment-variable **name**
  only
- ✅ When `modules.backups.local_directory` is repo-relative, `quickscale apply`
  MUST add that directory to `.gitignore` without hiding `.quickscale/state.yml`
- ❌ Backup artifacts MUST NOT use `public_base_url`, public media URLs, or
  template-visible asset helpers
- ❌ JSON artifacts are NOT a supported restore surface for generated PostgreSQL
  projects
- ❌ No standalone admin upload/offload action, and no admin materialization path
  for remote-only artifacts — the admin restore surface covers row-backed local
  artifacts already on disk; admin download and validate stay local-file-only
- ❌ Raw credential values MUST NOT be persisted in `quickscale.yml`,
  `.quickscale/state.yml`, or `BackupArtifact` rows

`quickscale apply` MAY update managed backend/runtime wiring, but does NOT rewrite
user-owned Docker, Compose, CI, or E2E workflow files in already-generated
projects. When the PostgreSQL 18 backups contract requires new image packages or
runner tooling, existing generated projects adopt those changes manually; fresh
generations pick them up from the updated templates.

Engine boundary: §[DR Engine Boundary Contract](#disaster-recovery-engine-boundary-contract-f5--m10).

---

### Module Manifest Architecture {#module-manifest-architecture}

**Architectural Decision:** Each module includes `module.yml` declaring configuration options as mutable or immutable.

**Manifest Schema:** See [plan-apply-system.md § Module Manifest](./plan-apply-system.md#module-manifest-moduleyml) for the canonical shape.

**Configuration Rules:**

| Aspect | Mutable | Immutable |
|--------|---------|-----------|
| **Definition** | Runtime-changeable via `quickscale apply` | Embed-time-only, locked after |
| **Storage** | Django `settings.py` | `.quickscale/state.yml` |
| **Changes** | Auto-update settings.py on apply | Reject with error guidance |
| **Code** | Read from settings (no hardcoding) | Configured at embed time |
| **Example** | `ACCOUNT_ALLOW_REGISTRATION` | `authentication_method` |

**Apply Behavior** (extends Plan/Apply):
1. Load module manifest from embedded module
2. Compare desired config (`quickscale.yml`) vs applied state (`.quickscale/state.yml`)
3. For mutable changes: update `settings.py` automatically
4. For immutable changes: error with guidance ("To change X, run `quickscale remove <module>` then re-embed")
5. Update `.quickscale/state.yml` with new config values

**Constraints:**
- ✅ Every module MUST have `module.yml` at package root
- ✅ `module.yml` `version` is the canonical installed-version source after embed
- ✅ `module.yml` dependency names MUST match the non-baseline runtime package names declared in the module `pyproject.toml`; `module.yml` defines the required package set and `pyproject.toml` carries the Poetry specs
- ✅ Mutable options MUST specify `django_setting` key
- ✅ Immutable options MUST NOT have `django_setting`
- ✅ Package `pyproject.toml` version metadata and exported `__version__` values MUST match `module.yml` when present
- ✅ Module code MUST read configurable values from settings (not hardcoded)
- ✅ Backward compatible: modules without manifest treated as all-immutable
- ✅ Options that would require rewriting generated theme-owned frontend routes, navigation, or page registries are not valid mutable plan/apply config; use fixed built-in routes or treat the frontend change as fresh-generation/manual-adoption work

**Tie-Breaker:** For config option disputes, default to **immutable** (safer) unless explicit `django_setting` mapping exists.

---

### Module Derivation Schema {#module-derivation-schema}

**Rule:** Declarative derivation is the **single source** of per-module
normalisation and validation knowledge. `module.yml` — not imperative helpers —
is authoritative for how a configuration option normalises, validates, and
projects into a Django setting.

**SA215 amendment** (§[Module Conventions](#module-conventions) rule 12): within
`module.yml`, an option's checks are written in its own `validation` block under
`config`, and the option-validation engine reads that block directly — one
engine, authored next to the option; `derivation.option_derivations.<option>.validation_rules`
and `legacy_aliases` are refused at load, as are the top-level
`derivation.validation_rules` and `derivation.legacy_aliases` lists (rule 6
forbids aliases). A direct one-to-one projection is the option's `django_setting`
alone; `derived_settings` is only for a setting computed from several options or
transformed, and carries no default (the option's `default` is the only one). The
derivation section keeps normalisation, those computed settings, and wiring.

**Constraints:**
- ✅ Derivation types are frozen dataclasses and all field types are YAML-safe
  (scalars, lists, dicts), so `module.yml` `derivation:` sections round-trip
  through `yaml.safe_load` without custom codecs
- ✅ `ModuleDerivationSchema` is a **companion** to `ModuleManifest` — it does not
  extend, subclass, or alter `ModuleManifest` or `ConfigOption`
- ✅ Runtime derivation execution runs through the manifest engine for every module; the
  per-module option code is gone, and a module's adapter contributes only what the declarative
  resolver cannot express
- ❌ No new imperative `normalize_*` / `validate_*` contract logic, and no
  hand-written CLI contract files — an imperative-freeze guardrail enforces this

Type reference:
[implementation_contract.md §Manifest Adapter Architecture](./implementation_contract.md#manifest-adapter-architecture).


### Module Wiring Authority {#module-wiring-authority}

**Rule:** A QuickScale module is a **standard Django app** plus **one declarative
wiring block in its own `module.yml`**. The module owns both. Neither
`quickscale_core` nor `quickscale_cli` may hold per-module wiring knowledge.

**Why this section exists.** Django's own answer to "how does an app get into
`INSTALLED_APPS`" is a paragraph in a README that a human reads and types.
QuickScale generates the project instead, so that instruction must exist as data a
program reads. That machine-readable instruction is the **adapter**. It is the only
QuickScale-specific concept in module wiring — everything else about a module is
ordinary Django.

**The two layers, kept separate:**

| Layer | What it is | Standard? |
|---|---|---|
| **The Django app** | `apps.py` with an `AppConfig`, concrete models, `0001_initial`, optional `admin.py`/`urls.py`/`views.py` | Ordinary Django. No QuickScale divergence. |
| **The wiring** | `derivation.wiring_projections` in the module's `module.yml`, executed by the module's own `adapter.py` | QuickScale-specific, because Django never automated this step. |

**Constraints:**

- ✅ Every module MUST be a standard Django app: `apps.py` declaring an `AppConfig`
  with explicit `name` and `label`, plus concrete models and a `0001_initial`
  migration for domain modules (see
  [§Module Implementation Requirements](#module-implementation-checklist) for the
  service-style exception)
- ✅ Every module MUST own its adapter at
  `quickscale_modules/<name>/src/quickscale_modules_<name>/adapter.py`, exposing the
  `get_manifest_adapter()` sentinel that `refresh_managed_adapters()` discovers
- ✅ Every module MUST declare the Django apps it contributes **exactly once**, in the
  `derivation.wiring_projections` entry with `wiring_field: apps` in **its own**
  `module.yml`. That block is the sole authority for `INSTALLED_APPS` membership
- ✅ A module that ships models or a migration MUST declare at least one Django app.
  This is enforced by a conformance gate, not by review
- ✅ Adapters SHOULD route through `build_generic_manifest_spec()` so `apps` is read
  from the manifest. A hand-built `ResolverResult` is permitted only for a
  module needing a custom post-hook, and MUST still source `apps` from the manifest —
  never as a Python literal in the adapter
- ❌ **No per-module wiring blocks in `quickscale_core`.** Core discovers and executes
  adapters; it does not contain them, and does not enumerate its modules
- ❌ **No per-module wiring logic in `quickscale_cli`.** The CLI collects desired
  configuration; it does not decide what a module wires
- ❌ **No compatibility-fallback adapters, and no bundled/installed fallback wiring
  path.** A managed module whose manifest is present but whose adapter is not
  importable raises `ImproperlyConfigured` — see
  [§Bundled Module Inventory and Source-Required Paths (AF7)](#bundled-module-inventory-and-source-required-paths-af7)
  guard **G4** and the [§Fail-Hard Principle](#fail-hard-principle). Bundled manifests
  are inventory metadata, never a second wiring authority
- ❌ **No parsed-but-unread declarative surface.** A key accepted by the manifest
  loader MUST be projected into wiring by a live code path, or MUST be removed from
  the schema. A key that looks authoritative and is inert is a false-green

**Tie-breaker:** When two places state which apps a module contributes, the module's
own `module.yml` wins and the other copy is deleted, not reconciled.

**Known deviations and completed boundary work (updated 2026-08-25).** This section records
the current state of the target rule. Completed work is retained as evidence; each remaining
deviation has an owner:

The remaining deviations are scheduled inside v88; none is deferred.

| Deviation | Owner |
|---|---|
| Five modules (auth, backups, notifications, orgs, storage) now declare their app lists in their own manifests; core reads those projections | **SA167a** — completed v88, merge #8 |
| All twelve shipped modules own their adapters and consume the public `quickscale_core.runtime` facade or its `runtime.manifest` subfacade; `quickscale_core/.../manifest/entry_point.py` contains only generic registry/dispatch logic | **SA167b** — completed v88, merge #17; implementation, P4 acceptance, convergence, attestation, and merge-back are complete |
| The settled CLI product bytes no longer hold per-module wiring logic | **SA167d** — completed v88; evidence in [CHANGELOG.md](../../CHANGELOG.md). |
| `django_apps:` was parsed by `manifest/loader.py` and read by no production code path; the declaration gate now enforces app projections | **SA167c** — completed v88, merge #21; phases A-F accepted, evidence in [CHANGELOG.md](../../CHANGELOG.md). |

Type reference:
[implementation_contract.md §Manifest Adapter Architecture](./implementation_contract.md#manifest-adapter-architecture).
Authoring mechanics:
[module-extension.md §Building a Module](./module-extension.md#building-a-module-authoring-checklist).


### Module Conventions (SA215) {#module-conventions}

**Rule:** Every first-party module follows one convention for its settings, its identity names,
how it reads configuration, how it depends on and talks to other modules, how it exposes URLs,
templates, APIs, checks, errors, files, tests, and docs, and how it declares options, tenant models,
model basics, signals, and management commands, and how it authorizes, sends email, runs write
effects, names analytics events, declares its service surface, names constraints, receives
webhooks, deletes related rows, and names its files and tests, and how its wiring shares settings,
how the theme sees it, how it throttles, stems shared names, refers to other modules, receives
secrets, is type-checked, is listed outside itself, documents its options, and declares its
dependencies. A conformance test enforces each rule. Evidence and the options weighed:
[module-conventions-inventory.md](../planning/module-conventions-inventory.md).

**Why.** The modules grew one at a time and each invented its own naming, settings reader, and
cross-module coupling. The recorded boundary rules cover core ↔ module only; nothing governed
module ↔ module, which produced an `auth ↔ orgs` import cycle, modules reading each other's settings,
settings read but never declared, and every default written twice. Renames are a clean break
(§[Module Version Lockstep](#module-version-lockstep)) and cost least before
§[Clean-Break Migration History](#migration-squash-decision) is frozen.

**1. Settings names.**
- ✅ Every first-party setting is `QUICKSCALE_<MODULE>_<NAME>`, `<MODULE>` being the module name in
  upper case (`QUICKSCALE_BLOG_POSTS_PER_PAGE`, `QUICKSCALE_ORGS_MODE`).
- ✅ A setting read by Django or a third-party library keeps the name that library reads; the
  exceptions are listed, not implied: auth's `ACCOUNT_ALLOW_REGISTRATION`,
  `ACCOUNT_EMAIL_VERIFICATION`, `SESSION_COOKIE_AGE`; storage's `MEDIA_URL` and django-storages
  `AWS_*`. Adding one needs a decision edit.
- ✅ The manifest option key equals the setting suffix in lower case and never repeats the module
  name (`QUICKSCALE_CRM_API_ENABLED` ↔ `api_enabled`).
- ✅ Standard suffixes, each with a fixed type:

  | Suffix | Meaning | Type |
  |---|---|---|
  | `_ENABLED` | turns a module or a feature on or off | boolean |
  | `_API_ENABLED` | turns the module's REST API on or off (name the API only if there are several) | boolean |
  | `<THING>_PER_PAGE` | page size; name the thing unless it is the module's own name | integer |
  | `_RATE_LIMIT` | throttle, `"<count>/<period>"`, parsed by DRF's throttle (rule 9) | string |
  | `_RETENTION_DAYS` | days before deletion or anonymization; `0` keeps forever | integer |
  | `_TTL_SECONDS` | lifetime of a cache entry or signed token | integer |
  | `_ENV_VAR` | the *name* of an environment variable holding a secret, never the secret (rule 35) | string |

  Booleans that describe behavior rather than switch a feature keep a descriptive name
  (`QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG`).
- ✅ Every module has `QUICKSCALE_<MODULE>_ENABLED`. Off means installed, data untouched, public
  surfaces (URLs, pages, API, scheduled jobs) disabled; admin stays. `apply` refuses to switch a
  module off while an installed module lists it in `required_modules`.
- ✅ Vendor credentials default to the vendor's variable name (`STRIPE_SECRET_KEY`,
  `RESEND_API_KEY`, `AWS_ACCESS_KEY_ID`); secrets QuickScale itself defines use
  `QUICKSCALE_<MODULE>_<NAME>`.

**2. Identity names.** One stem, `quickscale_<module>`, for everything a project or database sees:

| Name | Form |
|---|---|
| Django app label (and so table, content-type, and permission names) | `quickscale_<module>` |
| URL namespace (`app_name`) | `quickscale_<module>` |
| Template folder | `templates/quickscale_<module>/` |
| Management command | `quickscale_<module>_<action>` |
| Cache key | `quickscale_<module>:<name>` |
| Constraint / index name | `quickscale_<module>_<model>_<purpose>` / `qs_<module>_<model>_<field>_idx` (rule 25) |
| Reverse accessor on another module's model | `quickscale_<module>_<name>` (rule 14) |
| Analytics event | `quickscale_<module>_<event>` (rule 22) |
| DRF throttle scope | `quickscale_<module>_<purpose>` (rule 32) |
| PostgreSQL function created by a module's raw SQL | `quickscale_<module>_<name>` (orgs' `qs_child_parent_org_equality` → `quickscale_orgs_child_parent_org_equality`) |
| Advisory-lock key (the string hashed into the lock id) | `quickscale_<module>:<purpose>:<id>` |

- ✅ Every name a module places in a namespace shared with the project or other modules takes the
  stem, and the namespace is listed in this table (rule 33).
- ✅ The Python package stays `quickscale_modules_<module>`; only developers see it.
- ✅ Tables use the app-label default; no module sets `db_table`.
- ✅ Template folders required by other software stay as listed exceptions: `templates/account/`
  (django-allauth) and `templates/admin/` (Django admin).

**3. Reading settings.**
- ✅ Values reach a running site only through `quickscale apply`, which writes every declared
  setting (the operator's value, else the manifest default) into the managed `settings/modules.py`,
  together with a `MODULE_SETTINGS_SCHEMA` holding each setting's type and the manifest's
  validation rules.
- ✅ Module code reads `settings.QUICKSCALE_<MODULE>_<NAME>` directly, with no default. The
  manifest default is the only default and is applied by `apply`, never at runtime.
- ✅ Each module calls the generic startup check from `quickscale_core.runtime` for its own
  label in `AppConfig.ready()` (rule 10). The check validates every declared setting against the schema,
  with the same validation vocabulary `plan`/`apply` use (the option's `validation` block), without coercion, and
  fails startup naming the setting, the rule, and "run `quickscale apply`". Core holds no
  per-module names; the schema comes from the project.
- ✅ Module test settings define every declared setting; they may be generated from the manifest.
- ✅ Database-backed settings (backups' `BackupPolicy`, notifications' `NotificationSettings`) keep
  their models as read-only mirrors of settings; settings are the only switch (rule 20), and the
  models' initial values come from settings.
- ❌ `getattr(settings, NAME, default)`, a settings reader that defaults or coerces, or defaults
  written in code.
- ❌ Reading a setting the module's manifest does not declare, or another module's setting.
- ❌ A runtime accessor, generated per-module settings file, or Pydantic-style second schema.

**4. How one module uses another.** A module imports another module only through that module's
**public surface**:

- every module: `services.py` — operations and questions (`send_notification`,
  `capture_event`, `is_enabled`);
- a foundation (layer 1, rule 5) additionally publishes the extension bases other modules build
  on. For orgs these are the ones modules use today: `models` (`Organization`, `TenantModel`),
  `managers` (`TenantManager`), `admin` (`TenantModelAdmin`), `current_org`, `tenancy`, `removal`,
  `sanitization`, `public_context`, `permissions`, and `signals`. The list is part of this decision
  and changes only by editing it.

Each interaction uses the mechanism that fits it:

| Interaction | Mechanism |
|---|---|
| A module asks one it may depend on (rule 5) to do something or answer something | call the lower module's `services.py`, guarded by `apps.is_installed(...)` and that module's `services.is_enabled()` when it is optional |
| A module builds on a foundation (tenant models, admin, org context) | import the foundation's published extension bases |
| A module announces an event and does not care who reacts | a Django signal defined in the sender |
| A module needs every installed module that depends on it to act | a capability declared on the dependent module's `AppConfig` and collected by one core helper (generalizing the SA213 removal obligations) |

- ❌ Importing anything of another module outside its public surface (migrations referencing
  another module's models excepted).
- ❌ Reading another module's settings.
- This narrows the "no service registries" prohibition: `AppConfig`-declared capabilities collected
  by one helper, and the listed core ports (rule 10), are allowed; a general registry,
  lookup-by-name, or DI container stays forbidden.
- How a *project* extends a module is unchanged and stays governed by
  [module-extension.md](module-extension.md); this rule covers module-to-module use only.

**5. Dependency direction.** A module may import only from its own layer or lower ones, and its
`required_modules` includes every module it imports (it may list more, such as a module whose
models it references only by string, like orgs relying on auth's user model). The layers are fixed by the table below,
not by a manifest key: a `module.yml` key read only by a test would break the "no parsed but
unprojected manifest keys" prohibition. Moving a module between layers is a decision edit.

| Layer | Modules |
|---|---|
| 0 — core | `quickscale_core` (imports no module; already gated) |
| 1 — foundations | orgs, auth, storage, notifications |
| 2 — platform | analytics, backups |
| 3 — features | billing, blog, crm, forms, listings, social |

- ✅ Within a layer, imports go one way only; no cycles. `orgs` does not import `auth`: auth owns the
  single allauth adapter and collects post-login redirects that orgs declares as a capability.
- ✅ Upward needs use a capability (rule 4): billing declares account-deletion handlers that auth
  collects; social declares org-scoped cache keys that orgs' purge collects.
- ✅ Core never names a module's settings: backups reads its own settings and passes a policy to
  the `dr_engine` call.
- ✅ The layer order covers references by name as well as imports (rule 34).

**6. No legacy names.** Renames land in one release, in modules, core, CLI, generator templates,
tests, fixtures, and docs together — including names quoted elsewhere in this file, which now
carry their renamed forms (`QUICKSCALE_ORGS_MODE`, `quickscale_backups_create`,
`quickscale_<module>` app labels).
- ❌ Aliases, `LegacyKeyAlias` entries, or fallback reads for a renamed option or setting.
- ✅ `apply` refuses a retired option key — in `quickscale.yml` and in `.quickscale/state.yml` — and
  the startup check refuses a retired setting, each naming its replacement.

**7. URLs.**
- ✅ The manifest's `url_includes` sets a module's mount (`blog/`, `accounts/` for auth, `orgs/`
  for orgs) and is the only place; a module's `urls.py` holds no prefix and `adapter.py` declares
  no URL include. The site root belongs to the project; no module mounts at `""`. A module's React
  shell routes are declared by rule 41.
- ✅ Moving a public URL is a breaking change recorded in the release notes, with the operator
  step it needs (webhook endpoints registered with Stripe and Resend move with their module).
- ✅ APIs at `<mount>api/<resource>/`; webhooks at `<mount>webhooks/<vendor>/`.
- ✅ Route names are snake_case and never repeat the module (`quickscale_blog:post_list`).

**8. Templates, static files, template tags.**
- ✅ One module base, `templates/quickscale_<module>/base.html`; it extends `base.html` and owns
  `{% block content %}`; every page extends it and fills `<module>_content`. No module template
  emits `<html>` or fills the project's `content` block directly. Templates under the rule 2
  folder exceptions (`account/`, `admin/`) follow the software that loads them.
- ✅ Email templates under `templates/quickscale_<module>/email/`.
- ✅ Static files under `static/quickscale_<module>/{css,js,img}/`.
- ✅ Template-tag libraries are named `quickscale_<module>`, or `quickscale_<module>_<purpose>`
  for a separate one (`quickscale_orgs_debug`).

**9. HTTP APIs.**
- ✅ Every JSON endpoint is a DRF view on one of the two bases of
  §[JSON API Endpoint Base Contract](#json-api-endpoint-base-contract). `OrgApiBaseView` is rebased
  on DRF's `APIView` and keeps its org-role logic as it is (it is not rewritten as a permission
  class). Signature-verified webhooks keep that contract's exemption.
- ✅ Every error has one QuickScale shape, with the HTTP status carrying the class of error:

  ```json
  {"error": {"code": "validation_error", "message": "Invalid input.",
             "fields": {"title": ["This field is required."]}}}
  ```

  `code` is a stable snake_case string (DRF's error code, or the module's own); `message` is
  human-readable; `fields` appears only for validation errors. One generic exception handler in
  `quickscale_core.runtime` produces it and names no module; the generated `settings/base.py`
  sets it as `REST_FRAMEWORK["EXCEPTION_HANDLER"]` in the existing composed `REST_FRAMEWORK`
  block. Module code raises DRF exceptions (or its `<Module>Error`, mapped by rule 10's
  `exceptions.py`) and builds no error body itself; the theme's API client parses the one shape.
- ✅ Lists page with `PageNumberPagination` sized by the module's `<THING>_PER_PAGE`; throttles are
  DRF throttles fed by the module's `_RATE_LIMIT` setting (rule 32).
- ❌ `JsonResponse` APIs, error bodies built in module code, a third-party error-format library, hand-written rate
  parsers, per-module token schemes (blog's `BLOG_API_TOKENS` is removed; a shared token scheme is
  SA154 inventory).

**10. Startup checks, errors, core ports.**
- ✅ A module's configuration and invariant checks are functions in its `checks.py`. From
  `ready()`, the module passes them to the generic helper in `quickscale_core.runtime`, which runs
  them with rule 3's schema check and raises one `ImproperlyConfigured` listing every failure —
  so every process refuses to start, including the WSGI server, which does not run Django system
  checks — and also registers them as system checks tagged with the module label, so
  `manage.py check` reports them. orgs' always-on RLS boot guard
  (§[Multi-tenant SaaS Architecture](#multitenant-saas-architecture), RLS enforcement rule) is one such check and keeps its
  exemptions.
- ✅ Invalid configuration fails startup; an unreachable vendor (PostHog, Resend, Stripe) does not —
  it is logged and handled when the module is used.
- ✅ A module's own exceptions live in `exceptions.py` under one `<Module>Error` base;
  `services.py` re-exports those callers catch.
- ✅ **Core port:** core defines a `Protocol` for something it needs, exactly one module
  implements it and registers it from `ready()` through `quickscale_core.runtime`, and a second
  or missing registration fails hard. The allowed ports are listed here:
  `register_backup_persistence` (backups). Adding one needs a decision edit.
- ✅ **Build-time check skip:** the generated image build may set the one-shot
  `QUICKSCALE_SKIP_MODULE_CHECKS=all` (comma-separated labels, or `all`) so its credential-free
  `collectstatic` step does not run the eager checks — a configured credential name cannot be known
  statically at build. The skip is effective only in a genuine Django management invocation of
  `collectstatic` (`sys.argv[0]` basenamed to `manage.py`/`django-admin` and `sys.argv[1]` equal to
  `collectstatic`), the callables stay registered, and the launcher never sets the variable, so a
  value left in a serving environment — or a serving executable whose argument merely reads
  `collectstatic` — cannot disable the checks there.
- ❌ A hand-written `raise` or check in `ready()` outside the helper, or catching and logging a
  configuration failure (Fail-Hard Principle).

**11. Package files, tests, models, docs.**
- ✅ Every module ships `apps.py`, `adapter.py`, `services.py` with `is_enabled()`, `module.yml`,
  `pyproject.toml`, `poetry.toml`, `py.typed`, and `README.md`; one-off public files (`contracts.py`,
  `helpers.py`, `constants.py`) fold into these or become private. allauth's adapter file is
  `allauth_adapter.py`, so no module has both `adapter.py` and `adapters.py`.
- ✅ Required tests: `test_apps.py`, `test_services.py`, `test_migrations.py` when the module has
  models, and `test_isolation.py` plus `test_rls_boundary.py` for a module with tenant models.
- ✅ Model choices are `TextChoices`/`IntegerChoices`, and code compares against their members,
  not string literals. A tuple derived from those members or from a data catalog (orgs'
  `INVITABLE_ORG_ROLE_CHOICES`, social's `SOCIAL_PROVIDER_CHOICES`) is allowed.
  ❌ `*_CHOICES` tuple lists written out as literals.
- ✅ README headings, in order: Overview, Configuration (every manifest option), Public surface,
  URLs, Management commands, Operations, Extending. No versions in headings. The test checks the
  headings and, under rule 38, that every option key and command name appears.

**12. Manifest option schema.**
- ✅ Every option has `type`, `default`, and `description`. A mutable option has `django_setting`;
  an immutable one has none and is read by the module's `adapter.py` at apply time (auth's
  `authentication_method`, storage's `private_media_enabled`), as
  §[Module Manifest Architecture](#module-manifest-architecture) already requires.
- ✅ The manifest is the only place option values are checked (rule 3). Each option carries its
  checks in its own `validation` block (the authoring form §[Module Derivation
  Schema](#module-derivation-schema) records). `plan`, `apply`, and the startup check read that block;
  the `derivation.validation_rules` list is removed (listings is its only user).
- ✅ **This is the complete validation vocabulary** — these single-value and cross-option keys, and
  no others. A check it cannot express needs a decision edit before it is added.
  - Single-value: `choices` (a closed set; on a `list` option it checks each item), `min` / `max`
    (numeric bounds), `pattern` (a full-match regular expression), and `not_empty: true` (a string
    not blank; a list or mapping not empty).
  - Cross-option: `required_when` (the option must be set when the condition holds),
    `any_of: [<option>, …]` (at least one listed sibling is set — backups' `endpoint_url` or
    `region_name`; a boolean `false` counts as unset inside `any_of` only, so a boolean option that
    must be true participates correctly, while `option_value_is_empty` itself is unchanged and
    `required_when` keeps its boolean meaning), `subset_of: <option>` (every item of this list is
    in the other list — notifications' `default_tags` inside `allowed_tags`),
    `excludes: {values: [...], when: <condition>}` (the value must equal none of the listed values,
    compared case-insensitively; `when` optional — notifications' placeholder sender), and
    `intersects: {values: [...], when: <condition>}` (the list must contain at least one of the
    listed values; `when` optional — social's embed-capable providers).
  - Condition grammar, shared by `required_when`, `excludes.when`, and `intersects.when`: a mapping
    whose entries must **all** hold; each entry's value is a literal, a list of literals (the
    condition holds on any of them), or `{not_empty: true}` (the option is set). Existing
    single-entry literal/list conditions keep their meaning.
- ✅ Every option whose type admits invalid values has a check: `<THING>_PER_PAGE` a range from 1,
  `_RETENTION_DAYS` from 0, or from 1 where the module offers no keep-forever (backups),
  `_TTL_SECONDS` from 1; `_RATE_LIMIT` the pattern
  `^\d+/(second|minute|hour|day)$`; a closed set of strings its `choices`. Booleans and free text
  are exempt.
- ✅ Declarative normalization kinds are `identity`, `strip`, `lowercase`, `url`, `choice_map`,
  `coerce_int`, `coerce_bool`, `slug`, and `list`. `slug` lowercases, maps `_` and whitespace to
  `-`, drops characters outside `[a-z0-9-]`, collapses repeated dashes, trims leading/trailing
  dashes, and takes an optional `max_length` and an optional `replace` mapping applied first.
  `list` comma-splits a string or wraps a scalar, applies its nested `item_rules` to each item,
  drops empties, and dedupes preserving order; a provider alias table is a `choice_map` item rule.
- ✅ A mutable option's `django_setting` is its only projection when the setting equals the option
  value; `derivation.option_derivations.<option>.derived_settings` is only for a setting computed
  from several options or transformed, and never repeats a setting name or a default. The
  option's `default` is the manifest's only default (rule 3).
- ✅ `config` always has `mutable` and `immutable` (`{}` when empty); `dependencies` is always
  present (`[]` when empty). Top-level key order is not a rule.
- ✅ A runtime predicate that decides module behavior from resolved options — notifications'
  production-targeted / live-delivery checks that select the runtime email backend — is adapter
  code in the module's `adapter.py`, not an option validation rule: it constrains no supplied
  value, so the option-validation engine never runs it.
- ❌ Option checks, defaults, or legacy option names written for a named module in core or the CLI
  (today `quickscale_core.contracts.resolvers`, `contracts.module_options`,
  `schema.config_schema`, and the CLI's `module_config`); option validation in module code — a
  module's `checks.py` (rule 10) checks what options cannot express (the database role, installed
  apps, cross-module invariants), never an option's value; a second schema file. The CLI's interactive plan-time prompts stay where
  [module-extension.md](module-extension.md) puts them, taking defaults and choices from the manifest.

**13. Tenant models.**
- ✅ Every organization-scoped model — in a module or in a project — subclasses orgs' `TenantModel`,
  directly or through a module's abstract base (`AbstractListing`, `BaseSocialItem`), which owns
  the `organization` field, the `objects` / `all_objects` `TenantManager` pair, and
  `base_manager_name`. A subclass's `Meta` inherits `TenantModel.Meta` (or its module base's
  `Meta`), so Django does not drop `base_manager_name`.
- ✅ Inheritance is the only tenant marker: `tenancy.is_tenant_model` answers by `issubclass(…,
  TenantModel)` alone, and a model with a `TenantManager` that does not inherit `TenantModel` fails
  startup through orgs' `checks.py` (rule 10) instead of being left unenrolled. `tenant_excluded`
  keeps its meaning.
- ✅ The `organization` field keeps the base's reverse name, `%(app_label)s_%(class)s_set`
  (stemmed by construction once rule 2's label is `quickscale_<module>`, e.g.
  `quickscale_blog_post_set`; rule 14's `related_name` rule is met). The one allowed override
  is a one-per-organization model (billing's `CreditBalance`), which redeclares `organization` as a
  `PROTECT` `OneToOneField` and keeps everything else.
- ✅ Tenant models are registered on `TenantModelAdmin`, other models on `admin.ModelAdmin`, both
  with `@admin.register`.
- ❌ `tenant_org_fk(...)` or `TenantManager()` in a model outside `TenantModel`; a retyped
  `base_manager_name`; the manager-only ("dual-manager") tenant form.

**14. Model basics.**
- ✅ Timestamps `created_at` / `updated_at`; other moments `<event>_at`.
- ✅ Primary keys are the `BigAutoField` default; a `UUIDField` key only for an identifier shown
  outside the site. Listed exception: orgs (`Organization`, `OrganizationTombstone`, invitation
  token).
- ✅ Users are referenced as `settings.AUTH_USER_MODEL`.
- ✅ Every relation to another module's model (`User` and `Organization` included) sets
  `related_name="quickscale_<module>_<name>"` — plural for a foreign key or many-to-many, singular
  for a one-to-one (`quickscale_blog_posts`, `quickscale_blog_author_profile`) — or `"+"` when no
  reverse access is wanted (rule 33);
  the tenant `organization` field is covered by rule 13. Reverse accessors on shared models are
  one namespace for every installed module.
- ✅ Every concrete model defines `__str__` and `Meta.ordering`; a singleton or one-per-parent model
  (a `OneToOneField` owner, or `BackupPolicy`, `NotificationSettings`) may omit the ordering.
- ✅ English only: modules do not call `gettext`, and set `verbose_name` only where Django's default
  reads wrong. Adding translation is a separate decision.

**15. Package root.** `__init__.py` holds `__version__` and `__all__ = ["__version__"]` and nothing
else. ❌ `default_app_config` (removed in Django 4.1), re-exports from the package root — the
public surface is `services.py` (rule 4).

**16. Signals.**
- ✅ `signals.py` holds only the `Signal()` objects the module sends; it is public (rule 4).
- ✅ `receivers.py` holds the module's receivers, private, as `@receiver` functions, imported once
  in `ready()`. Only receivers of Django's database-backend signals (orgs' `connection_created`
  RLS guard) may be connected in `apps.py`.
- ❌ Receivers in `signals.py`: importing a sender's public signals must not register another
  module's receivers.

**17. Management commands.**
- ✅ A command subclasses `BaseCommand`, writes through `self.stdout` / `self.stderr` with
  `self.style`, and reports an expected failure by raising `CommandError` (a clean message and a
  non-zero exit).
- ✅ A command that deletes, anonymizes, or overwrites data takes `--dry-run`, which reports what
  would change and writes nothing; database-only work runs in `transaction.atomic()`.
- ✅ Modules ship no scheduler. A command a site should run periodically is listed under the
  README's Operations heading with a suggested interval; the operator's cron or platform scheduler
  runs it (backups' `schedule` and `automation_enabled` options already only document this).
- ✅ A retired command is deleted, not kept behind a guard (rule 6). `migrate_billing_to_orgs`
  is deleted with its recovery documentation: its 2026-09-16 retirement already stated current
  installs cannot hold the shape it repairs.
- ❌ `print()`, `sys.exit()`, or returning normally after a failure.

**18. Package tooling.**
- ✅ Every module's `pyproject.toml` has `[tool.pytest.ini_options]` (with `--cov-fail-under=90`)
  and `[tool.ruff]`; the test compares section keys, not values. Type checking is configured in the
  root `mypy.ini` only (rule 36).
- ✅ Test settings are `tests/settings.py`; an additional file is `tests/settings_<purpose>.py`.
- ✅ Every directory under `quickscale_modules/` is a module with a `module.yml`; there are no
  placeholder directories. The `teams` placeholder is deleted, its README moved to
  `docs/planning/teams.md`, and core's placeholder handling (the catalog's `teams` entry and the
  skips in module discovery and constraint validation) is gone with it.

**19. Authorization.**
- ✅ A view or API that manages a tenant model's data authorizes by org role through orgs'
  published `permissions` (`require_org_role`, `OrgRoleMixin`, and the DRF permission class
  `HasOrgRole(min_role)` beside them, delegating to the same `user_has_org_role` that
  `OrgApiBaseView`'s `min_org_role` uses, so rule 9's base keeps its logic and there is one role
  check). Each module fixes the minimum role per action in code and lists it in its README under
  Public surface. This extends [organizations.md](organizations.md)'s "no tenant should ever have
  `is_staff`" (org administration happens through org roles) to module back offices.
- ✅ "Logged in" is `LoginRequiredMixin`, `login_required`, or DRF `IsAuthenticated`.
- ✅ `is_staff` / `is_superuser` gate only Django admin and `operator_access` paths; forms' "every
  organization" branch moves under `operator_access`. analytics' `EXCLUDE_STAFF` reads `is_staff`
  to filter traffic, not to authorize, and is a listed exception.
- ❌ `is_staff`, `is_superuser`, `IsAdminUser`, or a hand-written `redirect_to_login` in a module's
  views, outside the listed operator paths.

**20. Email.**
- ✅ Every email a module sends goes through notifications' `send_notification`; a module that
  emails lists `notifications` in `required_modules` (orgs' `implies: notifications` becomes a
  requirement). Listed exception: auth's django-allauth mail.
- ✅ Notifications can still be off at runtime; `QUICKSCALE_NOTIFICATIONS_ENABLED` is the only
  switch (its `NotificationSettings` row is a read-only mirror, not a switch). `send_notification`
  then raises `NotificationDisabledError` (rule 23), and a sender for which email is optional checks
  `is_enabled()` first instead of catching it (rule 43).
- ❌ A module's own `EmailMessage` / `send_mail` path, or a fallback sender when notifications is
  absent or off.

**21. Effects of a write.**
- ✅ An email, analytics event, vendor call, or cache purge triggered by a database write is
  scheduled with `transaction.on_commit(...)` by the code that performs the write, not ordered by
  hand in the caller. A vendor call that must succeed before the write (Stripe checkout session
  creation) is not triggered by it and is exempt.
- ✅ Each module that has such an effect has a test that rolls the write back and asserts no effect.
  A static test cannot prove this rule; it is also a review rule.

**22. Analytics events.**
- ✅ analytics publishes `capture_event(*, distinct_id, event, properties)` and no per-event helper.
- ✅ The sending module names its events in its own `services.py` as
  `quickscale_<module>_<event>` in snake_case (`quickscale_forms_submitted`, rule 33), calls
  `capture_event` guarded as rule 4
  requires, and lists them in its README under Public surface. Listed exception: `$pageview`
  (PostHog's name).
- ✅ Renaming an event is a breaking change recorded in the release notes, like a moved URL (rule 7).

**23. Service surface.**
- ✅ `services.py` defines `__all__`; exactly that list is the module's public service surface
  (rule 4).
- ✅ A public service function takes keyword-only parameters after at most one leading subject
  (`send_notification(*, template_key, recipients, context)` already does).
- ✅ A service that cannot do what it was asked raises the module's `<Module>Error` (rule 10);
  whether an optional module is usable is `is_enabled()`. Listed exception: analytics' capture is
  best-effort (a vendor outage must not fail a request) and says so in its docstring.
- ❌ Returning `None` / `False` to signal a failure, or a cross-module import of a name not in
  `__all__`.

**24. Small conventions.**
- ✅ Every module ships `py.typed` (added to rule 11's file list).
- ✅ The current time is `django.utils.timezone.now()`.
- ✅ Cache keys are `quickscale_<module>:<name>` (added to rule 2's identity table).

**25. Constraint and index names.**
- ✅ Every `UniqueConstraint`, `CheckConstraint`, and `Index` sets `name`. A constraint is
  `quickscale_<module>_<model>_<purpose>` (at most 63 characters); an index is
  `qs_<module>_<model>_<field>_idx`, abbreviated to fit Django's 30-character limit. PostgreSQL
  index and unique-constraint names are one namespace per schema, shared with the project.
- ✅ Exception: an `Index` declared in a `Meta` with `abstract = True` may stay unnamed. A fixed or
  templated name is inherited by every concrete subclass, so two subclasses collide in the shared
  schema or exceed Django's 30-character `models.E034` check; Django generates a unique, bounded
  name per concrete subclass instead.
- ❌ `unique_together`, `index_together`, an unnamed `Index`, or a name without the prefix.

**26. Inbound webhooks.**
- ✅ A webhook is a DRF `APIView` with empty `authentication_classes`, `permission_classes`, and
  `throttle_classes` (the generated settings set default throttles; a provider's retry burst must
  not be refused), mounted at `<mount>webhooks/<vendor>/` (rule 7), that passes `request.body` and the signature
  headers to one `services.py` function. The signature is its authentication; this narrows the
  §[JSON API Endpoint Base Contract](#json-api-endpoint-base-contract) exemption to that.
- ✅ The service verifies the signature before parsing (the vendor SDK, else `hmac.compare_digest`
  with a timestamp window) and records each provider event under a unique database key, so a
  replay is a no-op.
- ✅ Responses: `200` `{"status": "accepted", "duplicate": <bool>}`; `400` with rule 9's error shape
  (`webhook_signature_invalid`, `webhook_payload_invalid`); `404` when the module is off (rule 1).
  A missing webhook secret fails startup in `checks.py` (rule 10). Write effects follow rule 21.
- ❌ Error bodies built from `str(exc)`, `403` for a bad signature, logic in the view.

**27. `on_delete` on `User`.**
- ✅ A relation to `User`, in a module or a project's own app, is `SET_NULL`
  (with `null=True`): the row stays with its organization and
  loses only the link. `CASCADE` only on rows that mean nothing without that user:
  `OrganizationMembership.user`, `OrganizationInvitation.invited_by` (reason in
  § [Multi-tenant SaaS Architecture](#multitenant-saas-architecture)), and blog's `AuthorProfile.user`;
  adding one is a decision edit and an edit of the gate's allowlist.
- ❌ `PROTECT` on `User`: it makes account deletion fail because of one module. A module that must
  keep a record past its user handles it in its SA213 removal obligation, visibly.
- The user-FK conformance gate (`orgs/tests/test_user_fk_conformance.py`) enforces this; rule 40 does not repeat it.
  It runs in orgs' test suite, so it sees the modules installed there and orgs' project-style test
  apps; nothing checks a generated project's own apps, where the rule is a review rule.

**28. Module file names.** A package holds only: rule 11's files; `checks.py`, `exceptions.py`
(rule 10); `signals.py`, `receivers.py` (rule 16); the Django and DRF names (`models`, `views`,
`urls`, `admin`, `forms`, `serializers`, `managers`, `filters`, `feeds`, `middleware`, `validators`,
`throttles`, `permissions`, `templatetags/`, `management/`, `migrations/`); `templates/` and
`static/` (rule 8); rule 4's listed
foundation surface files; the listed extras backups' `persistence.py` (rule 10's port), orgs'
`debug_views.py`, and blog's and listings' `markdownx_urls.py` (the staff-guarded MarkdownX
endpoint URLconf each module mounts in place of the vendor's unguarded one); and private files
named `_<name>.py`. Any other name needs a decision edit.

**29. Test names.** Test files are `test_<subject>.py`, named for what they protect; neither the file
name nor its docstrings and comments carry a ticket number (`SA<n>`, `AF<n>`, `CR-SA<n>-<n>`); the
test checks both. Other files in `tests/` are `conftest.py`,
`settings*.py`, `urls*.py`, private `_<name>.py` helpers, and test apps named `<purpose>_app/`.

**30. Settings written by module wiring.**
- ✅ A module's wiring (`adapter.py`, `module.yml`) writes its own settings and the Django or
  third-party settings it needs. Two modules may write the same key only with an equal value;
  `apply` fails otherwise, naming both modules and the key. `REST_FRAMEWORK` is merged key by key
  (its `DEFAULT_THROTTLE_RATES` too), and two modules setting one sub-key differently also fail.
  Core's `collect_wiring` enforces this and names no module.
- ❌ A setting whose value depends on the order of module names.

**31. The theme seam.**
- ✅ The seam's producer, the theme's `index.html.j2`, is rendered by the generator from the
  discovered module set (rule 37), so `window.__QUICKSCALE__.modules` carries a key for every
  shipped module, as the seam validator requires. A key is `true` only when the module is installed
  and its `QUICKSCALE_<MODULE>_ENABLED` is on (rule 1). A `modulePaths` entry is resolved from the
  module's URL names when it is installed (`{% url %}`), never written as a literal (rule 7). The
  two public social pages render the same seam content through `generator/seam.py`, with no
  hand-written per-module line. The seam itself is unchanged
  (§[Frontend Theme Source De-Specialization](#frontend-theme-despecialization-dormant-files)).
- ✅ The theme's TypeScript (the `QuickScaleModules` type, the seam validator, the SPA pages) still
  names the modules that have React surfaces, as [frontend.md](frontend.md) § Module frontend
  surfaces records; a module with a React surface adds itself there.
- ✅ The generated `templates/index.html` is user-owned (U3), so the change reaches new projects and
  the release notes carry the step for existing ones.
- ❌ Hand-written per-module lines or `INSTALLED_APPS` tests in `index.html.j2`, or mount paths
  written as literals.

**32. Throttles.**
- ✅ A DRF throttle scope is `quickscale_<module>_<purpose>` (rule 2); its rate is the module's
  `_RATE_LIMIT` option (rule 1), contributed to `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`
  through rule 30's merge.
- ❌ A rate written in code or `adapter.py`; a table created by `RunSQL` (blog's throttle-counter
  table goes with its hand-written limiter, rule 9).

**33. Shared-namespace stems.**
- ✅ Every name a module places in a namespace shared with the project or other modules carries the
  `quickscale_<module>` stem, and rule 2's table lists the namespace: labels, URL namespaces,
  template folders, commands, cache keys, constraints, reverse accessors on another module's
  models (rule 14), analytics events (rule 22), throttle scopes (rule 32), database functions, and
  advisory-lock keys. Settings and QuickScale-defined environment variables take rule 1's
  upper-case form, `QUICKSCALE_<MODULE>_`. Exceptions: names another program fixes (PostHog's
  `$pageview`, the `account/` and `admin/` template folders), index names, which Django limits to
  30 characters (`qs_<module>_…`, rule 25), and names core owns (its runtime-role variables
  `QUICKSCALE_ALLOW_BYPASSRLS` and `QUICKSCALE_PRIVILEGED_COMMAND`).
- ✅ A new shared namespace joins rule 2's table by a decision edit.

**34. References by name.**
- ✅ Rule 5's layer order and its one-way rule within a layer apply to every reference to another
  module, not only imports: an app label, a package name given to `import_module`,
  `apps.get_model`, `apps.is_installed`, or `apps.get_app_config`. An upward need uses a capability
  (rule 4). Migrations referencing another module's models are excepted.
- ✅ Applied: orgs' `require_org_feature` (it reads billing's plan features) moves to billing's
  published surface; the purge command's billing steps become billing's `removal_obligations`
  declaration with its boundary-guarded fields and hooks (the SA213 pattern), and its blog and crm
  label prefixes come from those modules' own declarations; orgs'
  `checks.py` boundary table is declared by each boundary's owner (auth declares
  account deletion); `TENANT_TABLE_REGISTRY`, a CI parity oracle only
  (§[Multi-tenant SaaS Architecture](#multitenant-saas-architecture)), is test-owned and absent
  from shipped source; blog
  reaches storage through its `services.py` and lists `storage` in `required_modules`.
- ❌ A higher-layer module's app label, package name, or model name in a module's source.

**35. Secrets.**
- ✅ A secret reaches module code as a Django setting that `apply` renders in `settings/modules.py`
  as a read of the environment variable its `_ENV_VAR` option names (core's generic `__QS_ENV__`
  projection, as storage does today); module code reads the setting. The setting's name lets
  Django's error reporter mask it (it contains `KEY`, `SECRET`, or `TOKEN`).
- ✅ A module's `checks.py` (rule 10) fails startup when a secret its switched-on features need is
  empty; an unreachable vendor is still tolerated (rule 10). The webhook secret of rule 26 is one
  such check. backups' credentials reach the DR engine through the policy backups passes (rule 5).
  Storage is the one carve-out: an `s3`/`r2` backend may take credentials from the environment's
  default provider chain (instance role, shared config), which the storage helper already supports
  by omitting empty static keys, so only a half-configured static pair fails startup.
- ❌ `os.getenv` / `os.environ` in module code (listed exception: orgs' RLS boot guard reads core's
  runtime-role variables `QUICKSCALE_ALLOW_BYPASSRLS` and `QUICKSCALE_PRIVILEGED_COMMAND`, which
  start before settings load), or a default variable name written in code.

**36. Type checking.**
- ✅ Every module is type-checked through the root `mypy.ini`, where it has one
  `[mypy-quickscale_modules_<module>.*]` section ([module-extension.md](module-extension.md) step
  1.3). The section relaxes at most `disallow_untyped_defs`, `warn_return_any`,
  `warn_unused_ignores`, and the `var-annotated` error code; stricter is allowed.
- ❌ A per-module `[tool.mypy]` (CI runs mypy from the repository root and does not read it),
  `ignore_missing_imports` in a module section, or another disabled error code.

**37. Module lists.**
- ✅ Code outside `quickscale_modules/` that needs the set of modules (the CLI,
  scripts and CI gates, generator templates including the seam producer of rule 31) computes it
  from discovery
  (`quickscale_modules/*/module.yml`) plus what each module states about itself: a tenant model is
  a `TenantModel` subclass (rule 13), a description is `module.yml`'s. A list that must exclude a
  module states the exclusion and its reason beside the derivation.
- ✅ Core's declared release inventory (`contracts.module_catalog.MODULE_CATALOG`) names the
  shipped modules and their readiness metadata, and its consistency test keeps it equal to
  discovery.  Discovery refuses a declared module directory that is missing, so a same-count
  substitution cannot re-point the inventory, and `AUTHORITATIVE_MODULE_COUNT` keeps an addition
  or removal fail-hard until the shipped contract — inventory, count, and manifests — is
  deliberately updated together.
- ❌ A literal list of module names outside a module. Allowed: rule 5's layer table, rule 40's
  test-owned mapping, the theme's module surfaces (rule 31), its server-side seam producer
  (`generator/seam._SEAM_MODULE_PATHS`) included, core's declared release inventory above, and the
  `.env.example` managed-block catalog (`apply/steps/env_sync.ENV_EXAMPLE_MODULE_SPECS`), whose
  per-module prose and block order are presentation data pinned by the env-example conformance
  suite.

**38. README content.** Rule 11's Configuration heading names every manifest option key, and its
Management commands heading every command the module ships; the test checks both, besides the
headings.

**39. Module dependencies.**
- ✅ `required_modules` lists bare module names (`[orgs]`); `plan` and `apply` select a required
  module together with its dependant. Lockstep versions
  (§[Module Version Lockstep](#module-version-lockstep)) make version floors meaningless.
- ❌ A version specifier on a first-party module; the `implies` key (orgs' `implies: notifications`
  is a requirement under rule 20).

**40. Enforcement.** A conformance test over every `module.yml`, every module's source, and core's
and the CLI's option handling fails on each of rules 1–39 and 42–43 (rule 21 stays a review rule
with each module's write-effect rollback test; rule 27 through the user-FK conformance gate; rule 30
in `apply` itself): names, suffixes and types, `_ENABLED`
presence, undeclared and cross-module settings reads, defaults in code, import targets and layers,
`required_modules` against imports, identity names, `db_table`, retired names, URL mounts and route
names, template and static paths, non-DRF JSON and hand-built error bodies, checks outside
`checks.py` or swallowed, required files and tests, README headings, choice lists, unlisted core
ports, option fields and validation, per-module option code in core or the CLI, duplicated setting names or defaults in a manifest,
tenant-model base,
`Meta` inheritance, and admin, primary keys, `related_name`, `__str__` and ordering, `gettext`,
`__init__.py` content, receivers outside `receivers.py`, command output, `CommandError`, and
`--dry-run`, `pyproject.toml` sections, a module directory without `module.yml`, `is_staff` and
hand-written login checks in views, email sent outside notifications, per-event analytics helpers and
event names, `services.py` `__all__` and keyword-only signatures, `py.typed`, `datetime.now`, and
cache-key prefixes, constraint and index names and `unique_together`, webhook view bases, empty
authentication and throttle classes, a signature-verifying service call in every such view (taking
over from the CSRF pairing gate for webhooks), and response bodies, unlisted package file names, and ticket numbers in test file names, docstrings, and comments,
hand-written module lines and literal mount paths in the seam producer, throttle scopes and rates
and `RunSQL` tables, database function and advisory-lock names,
stems in shared namespaces, references by name against the layers, `os.getenv` in module code, the
root `mypy.ini` module sections and any per-module `[tool.mypy]`, literal module lists outside the
modules, option keys and command names in READMEs, and `required_modules` specifiers and
`implies`, settings snapshots outside `_settings.py` or in `__all__` and cross-module settings
objects, and `except Exception` around another module's service call — with a control case proving
each rule rejects a violation. The layer table, each
foundation's published extension bases, and every listed exception live in one test-owned
mapping that mirrors this section.

**41. Module UI paths.**
- ✅ A path that serves a module's UI, React shell routes included, is declared by that module's
  manifest (`spa_routes`) and rendered by `apply` from the discovered, installed, and enabled set,
  after the module's own URL includes; a module that is installed but switched off contributes
  none.
- ✅ Project-namespace route names for module pages served by the module's own URLconf are
  `quickscale_<module>:<name>` (rule 2). A host-rendered shell route carries the module stem in a
  flat project route name (`quickscale_crm_shell`): Django resolves one resolver per namespace, so
  a second include cannot share the module's `quickscale_<module>` namespace and a colon form
  cannot reverse.
- ✅ `TenantMiddleware`'s orgs path guards read their prefixes from orgs' URL names rather than
  literals.
- ❌ A module path written as a literal in generator or theme templates, or in another module's
  code. ❌ Two routes that resolve the same path.
- **Exceptions.** orgs' `/orgs*` React shell reservations stay in `urls.py.j2` because the
  tenancy mode decides which side owns the path (solo mounts orgs before home, saas after);
  forms' shallow reservations (`/forms`, `/forms/<slug>/`) stay host-rendered until its module
  entrypoint hydrates, because that entrypoint currently renders only a mount-point div;
  social's public `/social` and `/social/embeds` pages are the theme's host-rendered pages
  (flat route names `social-link-tree` and `social-embeds`), not a module mount: the manifest
  declares social's `_quickscale/social/` transport include, and the project owns those public
  theme routes; `TenantMiddleware`'s exempt prefixes (`/accounts/`, `/admin/`, `/healthcheck/`)
  are not orgs paths; and the generated 404 hint's path tests are diagnostics against a
  requested path, not route declarations.
**42. Settings snapshots.**
- ✅ A module that needs one consistent view of several of its own settings builds it in its private
  `_settings.py` as a frozen dataclass with a `from_settings()` classmethod, reading each setting
  directly, with no default and no coercion. It stays private; callers outside the module ask
  `is_enabled()` or a `services.py` function.
- ❌ A settings snapshot defined outside `_settings.py`, named in `__all__`, or read by another
  module; a snapshot that defaults, coerces, or reads another module's settings.

**43. Optional senders.**
- ✅ A sender guards an optional module with `apps.is_installed(...)` and that module's
  `services.is_enabled()`, and catches only that module's `<Module>Error` where its failure is
  tolerable.
- ❌ Reading another module's settings object; `except Exception` around another module's service
  call (rule 23's listed analytics best-effort exception aside).

**46. Splits (D48).**
- ✅ A split keeps its facade's public import path and its log channel: the private files log on
  the facade's logger; the facade re-exports public names only and its tests patch the defining
  module (§[Split-Facade Seams](#split-facade-seams)).
- ✅ Rule 19 finds view code by content, not by file name: a Django or DRF view subclass, or a
  function that takes `request`.
- ❌ A moved log channel without a release-notes line.

---

### Split-Facade Seams (SA234) {#split-facade-seams}

**Rule:** A test's seam is the module that defines the name (or an injected collaborator),
never the re-export path. A private module (`_<name>.py`) imports the sibling modules that
define its collaborators and never imports its own package's facade. A facade imports its
private siblings one way and re-exports public names only.

- ✅ `patch("<defining-module>.X")`; a private module resolves each collaborator at call time
  through the module that defines it, and a facade keeps its public import paths by
  re-exporting public names (`X as X`) from its private siblings.
- ❌ A `_<name>.py` module importing its own package's facade — the CLI command and utility
  facades, `dr_engine`, and billing included; a private or incidental name in a facade's
  re-export block or in a facade-surface test's expected set.
- Enforcement: `scripts/check_split_facade_imports.py` (registered gate
  `check-split-facade-imports`) rejects a private module importing a facade in its family; the
  CLI split facades (`quickscale_cli/tests/test_split_facade_surfaces.py`) and billing
  `services` (`test_services_facade_surface.py`) each carry a surface test that pins public
  names only.

Evidence and options weighed: [arch audit § Finding 2](../others/arch-audit.md)
(`split-facades-patch-coupled`, option 1 with option 3's ratchet re-key).

---

### Frontend Rendering Decisions (SA241) {#frontend-rendering-decisions-sa241}

**Decision 1 — Frontend split.** React is the standard frontend for new
application and public pages — including a public page whose crawlable first
response is prerendered (Decision 2), where the React surface owns the
interactive page. Django-rendered surfaces stay Django-rendered on
the shared design (SA192): `auth` and `billing` keep their Django pages, the
module-shipped Django pages (`blog`, `listings`, and the CRM dashboard) keep
theirs until an SA154 item promotes a React replacement, and Django admin stays
as shipped.

- ✅ A new application page, or a new public page, is built as a React surface
  in the theme and reaches the browser through the one `window.__QUICKSCALE__`
  seam or a DRF endpoint (§[Frontend Theme Source
  De-Specialization](#frontend-theme-despecialization-dormant-files)).
- ✅ A module-shipped Django page keeps its Django rendering and its existing
  module base and block contract; promoting it to React is an SA154 inventory
  item, not an incidental edit.
- ❌ Rewriting a module's shipped Django page as a React page outside an SA154
  promotion; a second frontend stack, a second seam, or a second design source.

**Decision 2 — Public catalog and detail pages are prerendered React documents
at the project's build/deploy step.** SA153's public catalog and detail pages
stay the project's React public surface. The project's prerender step renders
them with Vite's SSR build into HTML that carries their indexable content, Open
Graph tags, and structured metadata, and Django serves those documents; React
hydrates the document for the interactive layer (filters, galleries, inquiry).
The JSON read API remains the React layer's data contract, and the prerender
reads the same published, organization-scoped listing data the API serves.

- ✅ The prerender runs in the project's build/deploy step from the published
  listings that step reads; when published listings change, the project
  regenerates the affected documents and the sitemap by re-running that step.
- ✅ `sitemap.xml` and `robots.txt` are generated from the published listings in
  the same step, never from a hand-maintained list.
- ✅ React hydrates the prerendered document; the page remains the React surface
  SA153 delivers, and the API stays its data contract.
- ✅ No new frontend dependency is added: Vite's built-in SSR build and
  `react-dom/server` (part of `react-dom`, already in the approved stack) cover
  the mechanism. A plugin or renderer beyond them records a decision entry
  first (§[Module & Theme Architecture](#module-theme-architecture),
  [implementation_contract.md § Runtime
  Pins](./implementation_contract.md#runtime-pins-and-constraints)).
- ❌ Django-rendered property pages — they replace the React public surface
  SA153 delivers; a runtime React SSR service or Node sidecar — a Node runtime
  outside the shipped Python-only, single-service deployment; an on-demand
  headless-browser prerender; a crawler-only document (no user-agent detection).

**Options considered for Decision 2:**

| Option | Why not chosen |
|---|---|
| Django server-render of the public document | Replaces the React public property surface SA153 delivers with Django-rendered property pages, which SA153's scope prohibits |
| Runtime React SSR in a Node renderer (Vite SSR build plus a Node process) | Adds a Node runtime and service to a Python-only, single-service deployment and a second data path; a new operational surface outside the shipped contract |
| On-demand headless-browser prerender (Playwright plus a cache) | A browser runtime in production plus cache invalidation; fragile, and outside the shipped stack |
| Prerender the React pages in the project's build/deploy step (chosen) | Keeps the React surface SA153 delivers; no new runtime and no new dependency; the documents are regenerated with the content that produced them |

**Related docs:** [frontend.md](frontend.md) | [roadmap.md](./roadmap.md)

---

### Module Implementation Requirements {#module-implementation-checklist}

**Rule:** Every QuickScale module must be complete, embeddable, and usable
immediately after `quickscale apply`. A module that requires the user to write
code before it works is not shippable.

**Constraints:**

- ✅ `src/` layout, with `tests/` outside `src/`, and a `module.yml` at package root
- ✅ Domain modules MUST ship **concrete** models plus a `0001_initial` migration
  — abstract-only modules force user implementation and produce "missing
  QuerySet" errors at runtime
- ✅ `quickscale_modules/*` MUST have a `README.md` (they are distributed standalone)
- ✅ Templates, settings wiring, URLs, and migrations must work immediately after
  embed, with no user customization required
- ✅ `tests/settings.py` uses `django.db.backends.postgresql` only — SQLite in any
  test settings file is a Database Policy violation
- ✅ 90% overall mean + 80% per-file minimum coverage (CI enforced)
- ✅ Module code MUST read configurable values from settings, never hardcode them
- ✅ Settings, identity names, module-to-module use, URLs, templates, APIs, checks, errors,
  package files, required tests, README outline, option schema, tenant models, model basics,
  package root, signals, management commands, package tooling, authorization, email, write effects,
  analytics events, the service surface, constraint names, webhooks, `on_delete`, file names,
  test names, shared settings, the theme seam, throttles, shared-name stems, references by name,
  secrets, type checking, module lists, README content, and dependencies follow
  §[Module Conventions](#module-conventions)
- ✅ A module's server-rendered templates **extend the project's `base.html`** and
  never emit their own `<html>` document. Child templates fill a module-named
  block (`<module>_content`); the module base owns `{% block content %}`. A module
  stylesheet carries **content styling only** — the page shell belongs to
  `base.html`. See [frontend.md § Styling ownership](./frontend.md#styling-ownership).
- ✅ Module templates use **only the blocks `base.html` already defines**
  (`title`, `extra_css`, `content`, `extra_js`). `templates/base.html` is
  user-owned category U3 (see
  [generated_file_ownership.md](./generated_file_ownership.md)) and is never
  rewritten by `quickscale update`, so a module template that depends on a *new*
  block renders empty in every already-generated project — Django ignores a child
  block the parent does not define.
- ❌ Do not hand-edit `AVAILABLE_MODULES` — CLI module discovery is
  discovery-derived (`get_discovered_module_names()`); a module only needs to be
  discoverable

**Service-style exception (integration-only modules):** a module whose approved
contract is settings plus helper/service APIs only MAY omit `models.py`,
`views.py`, `urls.py`, `admin.py`, and migrations. The exception MUST be recorded
explicitly in this file or in the active roadmap milestone **before**
implementation starts — it is prior approval, not a post-hoc justification.
Service-style modules still require package metadata, documented public APIs,
lifecycle wiring where needed, and tests for the shipped contract.

**Why this is a rule and not a preference:** `quickscale plan --add <name>` +
`quickscale apply` is the primary distribution mechanism. `manage.py migrate`
must succeed straight after embedding, so migrations for concrete models are the
module's responsibility, not the user's. Forcing placeholder models or admin
classes onto genuinely service-style modules creates fake extension seams — which
is why the exception exists but must be explicit.

**Authoring guide** — package layout, the `pyproject.toml` and `mypy.ini`
templates, registration steps, and the per-component checklist are in
[module-extension.md § Building a Module](./module-extension.md#building-a-module-authoring-checklist).

<a id="package-structure-and-naming-conventions"></a>

---

**Extended package-layout note:** See [scaffolding.md §4](./scaffolding.md#post-mvp-structure) for maintainer-side namespace and package-layout reference material. It is not part of the current generated-project contract unless a release note and this file say otherwise.

<a id="mvp-feature-matrix-authoritative"></a>
## Implementation Surface Matrix (authoritative)

The authoritative shipped-surface matrix now lives in [implementation_contract.md](./implementation_contract.md#mvp-feature-matrix-authoritative).

Keep this anchor in place for compatibility. Update the companion doc when the shipped feature surface changes.

## Authoritative Policies

**Settings Inheritance:**
- ✅ Current generated projects: Standalone `settings.py` (no automatic inheritance from quickscale_core)
- ✅ Generated settings import the versioned `quickscale_core.runtime.settings` facade for executable runtime contracts (SA206) — a library import, not settings inheritance
- ✅ Optional: Manual inheritance after git subtree embed (advanced users)
- ❌ NO automatic settings inheritance in generated projects

**Packaging (All QuickScale Packages):**
- ✅ Poetry package manager
- ✅ Root-level pyproject.toml + poetry.lock (required); per-module `poetry.lock` files are not supported (monorepo root is the single resolution source)
- ✅ src/ layout (prevents accidental imports)
- ✅ Use ./scripts/install_global.sh for Poetry-built user installs
- ❌ NO requirements.txt generation
- ❌ NO setup.py files
- ❌ NO direct system-Python pip install flows (`pip install --user`, `--break-system-packages`, etc.)

**Development Tools:**
- ✅ Ruff: Format + lint (replaces Black + Flake8)
- ✅ MyPy: Type checking (strict mode)
- ✅ pytest + pytest-django: Testing
- ✅ pytest-cov: Coverage reporting
- ❌ NO Black (use Ruff format)
- ❌ NO Flake8 (use Ruff check)

**Database Policy (Breaking):**
- ✅ PostgreSQL-only — dev, CI testing, and production; no exceptions
- ✅ `DATABASE_URL` is required for local DB configuration
- ❌ SQLite is prohibited for any purpose, **including test databases** — `django.db.backends.sqlite3` in any `tests/settings.py` is a policy violation
- ❌ `skipif(not postgres)` / `QUICKSCALE_TEST_DB` env-var guards on isolation tests are prohibited — isolation tests must run against PostgreSQL unconditionally; a job that cannot provision Postgres is misconfigured, not a valid reason to skip
- ❌ No backward compatibility layer, migration shim, or fallback mode for SQLite-based setups

**Validation and Automation Entry Points:** See [validation_policy.md](./validation_policy.md#repository-command-reference) for the authoritative repository command baseline and assistant guidance, and [§Validation Tiers](./validation_policy.md#validation-tiers) for which of those commands a given change owes.

**Security gate tooling:**
- ✅ Dependency vulnerability scanning uses Trivy v0.74.0 against the single
  committed root Poetry lockfile (which resolves core, CLI, and modules through
  path dependencies), including development dependencies; Trivy is the approved
  lock-native replacement for the originally proposed `pip-audit` design
- ✅ Static security analysis uses Bandit 1.9.4 over maintained first-party Python
  source with the focused category contract and reviewed suppression ledger
- ✅ Native Trivy acquisition supports Linux x86_64/arm64 and macOS
  x86_64/arm64; Windows contributors use WSL. Every release asset is bound to
  the official v0.74.0 manifest SHA-256 before safe extraction
- ❌ A missing tool, unsupported native host, stale vulnerability database,
  checksum mismatch, unsafe archive, or malformed scanner result must fail the
  gate; security checks never silently skip

### CLI Commands {#cli-command-matrix}

The authoritative current CLI command surface now lives in [implementation_contract.md](./implementation_contract.md#cli-command-matrix). Keep this legacy anchor in place for inbound links.

---

### Module-Specific Architecture Decisions {#module-specific-architecture}

#### Blog Module — Custom Django Implementation

**Decision:** The blog module is a custom Django implementation, not a wrapper
around an existing blogging package.

**Rejected (do not re-introduce):**
- ❌ **Wagtail** — a full CMS with 50+ dependencies; contradicts QuickScale's lightweight philosophy
- ❌ **django-blog-zinnia** — unmaintained (last release 2016), incompatible with Django 4.x+
- ❌ **Puput** — Wagtail-based, so it inherits Wagtail's complexity

**Scope boundary:** comments, advanced SEO (Open Graph, JSON-LD), related-posts
algorithms, and scheduled publishing are deliberately **out of scope** — users
reach for a third party (Disqus/Commento, django-celery-beat). Adding any of them
to the module requires a decision entry here.

---

#### Disaster Recovery Engine Boundary Contract (F5 / M10)

**Why:** The embeddable `backups` module must not carry platform-level
backup/restore orchestration or talk to the CLI through a hidden
management-command + environment-variable protocol. That orchestration
belongs in centrally owned code, leaving only thin Django-facing surfaces in
the embeddable module, reached through an explicit typed adapter rather than
implicit env-var/stdout-JSON coupling.

**Target ownership split:**

1. **Centrally owned DR engine (CLI/core layer)** — owns all platform-level
   orchestration:
   - Snapshot and archive primitives (database custom-dump capture, archive
     packaging).
   - Restore and orchestration flow (validation, ordered execution sequencing,
     destructive-operation gating).
   - Verification logic and verification-record assembly.
   - Rollback-pin lifecycle and pin handling.
   - Sidecar payload assembly (environment-variable manifests, release metadata,
     verification records).
   - Remote-storage orchestration.
   - Route/environment resolution and cross-route promotion sequencing.

2. **Embeddable `backups` module (thin Django-facing surfaces)** — owns only what
   genuinely requires Django/project context:
   - ORM models `BackupArtifact` and `BackupPolicy` (project-local DR records) and
     their migrations.
   - Admin UI for those models, including the guarded local-file restore surface.
   - A thin, explicitly documented Django adapter that exposes project-bound
     capabilities the engine needs (database connection/settings, `MEDIA_ROOT`,
     app/settings introspection).
   - No platform-level orchestration logic.

**Boundary interface:**
- The engine MUST NOT be reached through implicit management-command +
  environment-variable + stdout-JSON coupling. Replace it with an explicit
  internal boundary:
  - **Typed requests** (snapshot, restore — carrying an explicit destructive-op
    flag —, media-sync, verification) instead of environment-variable passing.
  - **Typed results** (snapshot descriptor, per-surface results, sidecar
    payloads, rollback pin) instead of parsing stdout JSON.
  - The embeddable module exposes a single documented adapter that the engine
    calls for project-bound operations. Management commands, if retained, become
    thin wrappers over this boundary rather than the protocol itself.
- Destructive restore stays gated; the gate becomes an explicit parameter on the
  restore request rather than the `QUICKSCALE_BACKUPS_ALLOW_RESTORE` env var.

**Invariants preserved across the split:**
- The Backups contract rule (above) remains authoritative: PostgreSQL 18 native
  custom dumps as the real restore path, JSON artifacts export-only, private
  operational artifacts, credentials referenced by environment-variable name only,
  and guarded destructive restore across both supported surfaces.
- No change to the user-facing `quickscale dr {capture,plan,execute,report}` CLI
  surface.
- The protocol replacement is a maintainer-internal boundary and needs no
  backward-compatibility shim; generated-project migration guidance is
  documented in `docs/technical/dr_engine_migration.md`.

---

## Document Responsibilities

- **decisions.md**: Repo-wide policy, tie-breakers, prohibitions, and document ownership map (authoritative)
- **implementation_contract.md**: Current shipped implementation contract, CLI surface, and architecture-boundary reference
- **validation_policy.md**: Validation entrypoints, validation tiers, candidate review and integration, testing standards, coverage expectations, and E2E guidance
- **generated_project_structure.md**: Generated-project layout, artifact placement, and generation guardrails
- **repository_layout.md**: Maintainer-repository layout and naming/import matrix
- **scaffolding.md**: Concise structure hub plus compatibility anchors and backlinks into the structure companions
- **plan-apply-system.md**: Plan/apply schemas, state management, and execution order
- **module-extension.md**: Module extension contract and the module-authoring checklist
- **generated_file_ownership.md**: Beta-migration `INTENTIONALLY_UNMANAGED` category inventory
- **quality_tools.md**: Quality analyzers plus the baseline-monotonicity gate specification
- **dr_engine_migration.md**: DR engine architecture and generated-project migration guidance
- **user_manual.md**: CLI workflows and worked examples
- **CHANGELOG.md**: Canonical all-version release history index
- **docs/releases/**: Single public release notes, whether they are clearly labeled prepared artifacts awaiting publish or notes already linked from GitHub tags and release PRs
- **docs/technical/release_summary_template.md**: Template for public release notes and release-prepared artifacts
- **publish_procedure.md**: Authoritative pre-publish quality gate and the ordered release phases — version stamping, split-branch publication, verification by generated project and deployment, sealing, and the irreversible publication step. Other documents link to it instead of restating release commands; this file keeps the lockstep *rules* it executes
- **versioning.md**: `VERSION` single-source declaration and propagation semantics, including what the version tool does not derive. Carries no release or publication sequence
- **roadmap.md**: Open work and active or unreleased release closeout status; its scheduling table is the canonical source for task tracks, dependencies, release requirements, and next actions. Completed work is removed and archived in CHANGELOG.md
- **docs/others/arch-audit.md**: Live structural findings only — the current open set, each with its promotion trigger. Not a ledger: closed findings, prior-pass narratives, and reconciliation history belong in CHANGELOG.md. Finding numbers are pass-local and MUST NOT be cited as stable identifiers from any other document, test, or source comment
- **docs/others/tech-audit.md**: Live defect posture only, and the SSOT for found-not-yet-fixed fail-hard violations. Same rule as above: remediated findings are dropped, not archived in place, and no other artifact may pin its finding counts or IDs
- **README.md**: Project overview, user guide, repo-level navigation
- **package README.md files**: Package-local installation and responsibility summaries (informational only)
- **commercial.md**: Commercial distribution background and constraints

**Rule:** Update the narrow owner first when changing its slice. Update decisions.md in the same change when the repository-wide ownership map, policy, or tie-breakers change.

Other documents link to the roadmap scheduling table instead of repeating queue
counts, lane readiness, or dependency prose. Consistency tests validate structural
contracts such as task coverage, legal tracks, and valid dependencies; they must
not hardcode current-status narrative wording. Keep durable execution rules in
[validation_policy.md](validation_policy.md#candidate-review-and-integration),
and historical reviews and scheduling decisions in CHANGELOG.md.

### Release scope safeguards

The v88 cleanup does not authorize teams, another theme, or a third
generated-project updater. `quickscale_devtools` remains maintainer-internal and
must not enter the public publish package list. Architecture watchlist findings
retain their growth triggers; only an explicitly scoped, trigger-independent
step may proceed before its trigger fires. Such a step does not authorize typed
disposition metadata, ownership-manifest generation, taxonomy derivation, or
changes to existing file dispositions.

Preserve the settled module-presence contract and manifest dispatch, local
wheelhouse version checks, migration baseline, and provisioning behavior. The
current cleanup grants no edits to `quickscale_core/contracts/` or
`quickscale_core/manifest/`; any newly authorized behavioral change there must
be announced in the merge queue because every track consumes those contracts.
The gate registry and module manifests retain one assigned owning track; do
not spread their implementation across worktrees. New scope requires its own
ticket rather than expansion of a cleanup delivery.

**Recorded disposition drift (SA207).** `INTENTIONALLY_UNMANAGED` grew from 78
to 89 entries across `e12e9867` (78→79) and SA194's closeout `45ca0c0a`
(79→89) without an update here, and the 2026-09-23 architecture audit classifies
that growth as decision-record drift against the paragraph above. The ten
dispositions SA194 added are `.pre-commit-config.yaml`, `frontend/vite.config.ts`,
`frontend/tsconfig.json`, `frontend/eslint.config.js`,
`frontend/postcss.config.js`, `frontend/src/lib/validateQuickScaleSeam.ts`,
`frontend/src/pages/FormsPage.tsx`,
`frontend/src/pages/SocialLinkTreePublicPage.tsx`,
`frontend/src/pages/SocialEmbedsPublicPage.tsx`, and
`frontend/src/hooks/usePublicSocialSurface.ts`. Recording the drift here does
not authorize further disposition changes; new scope still requires its own
ticket.

## Unit/Integration Gate Split

**Rule:** The test suite is split into two independent gates — a DB-free unit gate
and a PostgreSQL 18 integration gate.

- ✅ The unit gate (`make test-unit`) covers core + CLI only and requires no
  PostgreSQL and no special database role
- ✅ The integration gate (`make test-integration`) runs module suites against a
  restricted `NOBYPASSRLS NOSUPERUSER` role, in both `ci.yml` and `publish.yml`,
  with the RLS boot guard active — that restricted role *is* the tenant-isolation
  coverage
- ✅ `QUICKSCALE_ALLOW_BYPASSRLS=1` is set explicitly per-suite by a developer when
  a BYPASSRLS-dependent test needs it
- ✅ Known restricted-role failures are quarantined **individually against a
  ticket**; quarantined entries are excluded from the exit code and coverage mean
- ❌ No blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export on the unit path
- ❌ Non-quarantined module-suite regressions never pass the gate

Gate scopes, make targets, and role grants:
[validation_policy.md §Testing Standards](./validation_policy.md#testing-standards).
Which gate a given change owes is decided by tier, not by habit:
[validation_policy.md §Validation Tiers](./validation_policy.md#validation-tiers).

## Testing Standards

The authoritative validation rules, coverage expectations, and E2E policy now live in [validation_policy.md](./validation_policy.md#testing-standards). Keep this section as a compatibility hub for older links.

## Current Architecture Boundaries

The authoritative architecture-boundary reference now lives in [implementation_contract.md](./implementation_contract.md#current-architecture-boundaries).

See [implementation_contract.md](./implementation_contract.md#backend-extensions-policy) for the current module extension contract and [generated_project_structure.md](./generated_project_structure.md#mvp-structure) for generated-project layout context.

### Module Extension Contract {#backend-extensions-policy}

This legacy anchor now routes to [implementation_contract.md](./implementation_contract.md#backend-extensions-policy).

## Operational Decisions

**Core Principles:**
- ✅ Starting points over complete solutions (customize for business needs)
- ✅ Creation-time assembly (NO runtime dynamic loading)
- ✅ Standard Django architecture (app_label namespacing, standard migrations)
- ✅ Separate CLI package (independent release cadence from core)
- ✅ src/ layout (prevents import errors during testing/building)
- ✅ Direct imports (NO DI frameworks or service registries)
- ✅ Single providers at the product policy layer (Stripe payments, Resend email)
- ✅ Django email delivery for notifications uses `django-anymail` as the approved delivery layer with Resend as the current first-class provider
- ✅ Version pinning (predictable compatibility for Django foundations)
- ✅ **Fail hard** — every configuration error, missing dependency, and invalid runtime state raises an explicit exception; no silent fallbacks, no graceful degradation (see §fail-hard-principle below)

---

### Launcher One-Shot Command-Env Contract {#launcher-one-shot-command-env-contract}

**Rule:** Generated project startup scripts
and settings use two mutually exclusive one-shot environment variables to
select the database connection and bootstrap mode. These variables are always
set as inline command prefixes — never as persistent environment configuration.

**Design:**

1. **``QUICKSCALE_PRIVILEGED_COMMAND``** — Privileged DB operations that
   require the superuser ``DATABASE_URL`` (``migrate`` and
   ``createcachetable``).
   The launcher sets this as an inline prefix *and* blanks
   ``RUNTIME_DATABASE_URL=""`` so the superuser role is used for schema
   changes (the runtime role has ``NOSUPERUSER``/``NOBYPASSRLS`` and cannot
   run DDL).

2. **``QUICKSCALE_NON_DB_COMMAND``** — DB-free bootstrap operations
   (``collectstatic``, ``compilemessages``) that do not need a live
   ``DATABASE_URL``. ``production.py`` supplies a dummy ``postgresql://``
   URL when ``DATABASE_URL`` is unset, keeping the process importable
   without a real database connection.

**Rules:**

- ✅ Both variables are one-shot inline prefixes only (e.g.,
  ``QUICKSCALE_PRIVILEGED_COMMAND=migrate RUNTIME_DATABASE_URL="" python manage.py migrate``).
  They are never exported, never set in ``.env``, never written to
  ``docker-compose.yml`` ``environment:`` blocks, never documented as
  persistent configuration, and never checked into version control.
- ✅ They are mutually exclusive — the ``production.py`` seam raises
  ``ValueError`` if both are set simultaneously.
- ✅ ``QUICKSCALE_PRIVILEGED_COMMAND`` requires ``RUNTIME_DATABASE_URL=""``
  (explicitly blank); omitting it raises ``ValueError``.
- ✅ ``QUICKSCALE_NON_DB_COMMAND`` does not require a real ``DATABASE_URL``;
  a dummy URL is substituted when ``DATABASE_URL`` is absent.
- ✅ The default serving path (neither command var set) uses
  ``RUNTIME_DATABASE_URL`` when present, or raises ``ValueError`` (fail-closed).

**Implementation surface:**

| Variable | Values | Set by | Connection selected |
|---|---|---|---|
| ``QUICKSCALE_PRIVILEGED_COMMAND`` | ``migrate``, ``createcachetable`` | ``start.sh`` / ``quickscale manage`` (inline prefix) | ``DATABASE_URL`` (superuser) |
| ``QUICKSCALE_NON_DB_COMMAND`` | ``collectstatic``, ``compilemessages`` | ``Dockerfile`` build step (inline prefix) | Dummy ``postgresql://`` URL |

**2026-09-16 retirement decision:** ``migrate_billing_to_orgs`` is not a
permanent privileged command. Current installs cannot contain its historical
nullable ownership shape, so the command received no automatic superuser
connection and is now deleted with its recovery documentation. The sanctioned
set is permanently the two stable Django built-ins above. Each of the four
enforcing stations keeps an independent fail-closed refusal, with a
cross-station regression requiring their declarations to agree. This dated
decision supersedes the informal 2026-08-31 “permanent two” answer and the
intervening three-command contract.

**Related:** [Fail-Hard Principle](#fail-hard-principle) (the mutual-exclusion
check and missing-arg validation follow fail-hard); [Multi-tenant SaaS
§RLS enforcement rule](#multitenant-saas-architecture) (the runtime role's
``NOSUPERUSER``/``NOBYPASSRLS`` is the reason privileged commands need the
superuser ``DATABASE_URL``).

---

### Runtime Settings Facade (Public API) {#runtime-settings-facade}

**Decision (SA206):** `quickscale_core.runtime.settings` is the public import
path for the executable runtime contracts shared by generated settings and
launchers. It exports the client-identity and correlation-id middleware, the
trusted-proxy derivation, the privileged-command/runtime-database selection,
the production SECRET_KEY guard, and the structured-logging helpers.

**Why:** generated settings are user-owned and never upgraded, so an inline
contract copy reached only freshly generated projects — SA200's proxy-trust fix
was the last example — and the fresh-first migration had to hand-patch donor
settings copies. One facade ships every contract fix through the existing
`quickscale-core` lockstep pin.

**Rules:**
- ✅ Generated `settings/base.py` and `settings/production.py` import the
  facade and keep only user configuration.
- ✅ Every generated project declares the bounded `quickscale-core` lockstep
  pin (`>=X.Y.0,<X.(Y+1).0`) in its `pyproject.toml`, including zero-module
  projects.
- ✅ The privileged-command contract test holds the facade's
  `KNOWN_PRIVILEGED_COMMANDS` declaration in place of the retired template
  copy.
- ✅ The beta-migration donor validator checks that donor settings call
  `resolve_runtime_database_url` instead of parsing an inline copy of the
  contract.
- ❌ No generated settings module re-declares the contract inline.

**Adoption:** existing projects adopt the facade through the declared
generated-project contract step (SA207).

---

### ImproperlyConfigured Exception Identity {#improperlyconfigured-exception-identity}

**Decision:** QuickScale's shared contract layer
(``quickscale_core.contracts``) defines its own
:class:`~quickscale_core.contracts.module_discovery.ImproperlyConfigured`
exception, decoupled from Django's ``django.core.exceptions.ImproperlyConfigured``.

Two same-named ``ImproperlyConfigured`` classes coexist — one in the contracts
layer and one in Django's module-runtime layer. Catchers and raisers must choose
the correct import:

- **Contracts-layer catchers** (code in ``quickscale_core.contracts`` or
  code that catches exceptions from contract-layer APIs) import
  ``quickscale_core.contracts.module_discovery.ImproperlyConfigured``.
- **Django-runtime catchers** (generated-project settings, module
  ``AppConfig.ready()`` code, standard Django startup paths) import
  ``django.core.exceptions.ImproperlyConfigured``.

Importing the wrong class will silently fail to catch the intended exception,
causing an unhandled crash instead of graceful handling. This is a documented
identity-split — not a refactoring opportunity to consolidate into one shared
alias.

---

### Fail-Hard Principle {#fail-hard-principle}

**Rule:** Every configuration error, missing required dependency, or invalid runtime state must raise an explicit, descriptive exception immediately. Silent fallbacks, best-effort defaults, and graceful degradation are prohibited in the generator, CLI, and manifest stack.

**What this means concretely:**
- ✅ Raise `ImproperlyConfigured`, `ValueError`, `RuntimeError`, or `SystemExit` on invalid config — never substitute a default
- ✅ Raise immediately when a required adapter, path, or resource cannot be located — do not attempt to continue with a substitute
- ✅ Surface the root cause in the error message so the operator knows exactly what to fix
- ✅ Fail at startup / import time — not at first use — so configuration problems are visible immediately
- ❌ No `except Exception: pass` or `except ImportError: pass` in configuration, setup, or discovery paths
- ❌ No "best-effort defaults" when a required path or resource cannot be found
- ❌ No silent fallback chains (try A → try B → silently return something)
- ❌ No backward-compat shims or read-through legacy imports, unless explicitly documented below with a bounded exception and a sunset plan

**Scope:** Applies to the generator/CLI setup, manifest adapter resolution, module discovery, configuration loading, and Django app startup. Does **not** apply to domain logic inside generated projects (which are user-owned code) or to DR recovery orchestration (which is intentionally error-recovery context — fallback artifacts and remote restoration are by design).

**Global constraint that reinforces this:** No existing users, no migration path, no backward compatibility — every change is a clean break. The fail-hard principle is the runtime expression of this constraint: if something is misconfigured it must be fixed, not silently worked around.

**Documented exceptions** (each requires explicit justification in the code comment, a `# F-EXCEPTION: <tag>` label, and removal when the condition no longer applies):

| Tag | Location | Justification | Sunset |
|-----|----------|---------------|--------|
| F12.2 | `project_state.py:_read_through_import_legacy()` and `materialize_authoritative_state()`; `remove_command.py:_load_legacy_tracking()` and `_record_mutation_snapshots()` (legacy `config.yml` / `file_hashes.yml` compatibility paths) | One-time compatibility window: projects predating the consolidated `state.yml` format may still depend on legacy `config.yml` / `file_hashes.yml` data while consolidated `state.yml` becomes authoritative. `project_state.py` logs-and-skips stale legacy import failures so consolidation is not blocked; `remove_command.py` still consults and snapshots legacy `config.yml` so rollback-safe module removal can preserve compatibility tracking during the same sunset window. Does NOT cover `_load_managed_file_records_for_drift()` — its legacy `file_hashes.yml` fallback is a drift-detection design choice, not a compatibility path. | Remove once the consolidated state format has been deployed for two full releases with no known pre-consolidation projects in active use. |

**Known violations:** tracked in [tech-audit.md](../others/tech-audit.md), the SSOT for found-not-yet-fixed fail-hard violations. Remediated findings are dropped from that file and closed out in CHANGELOG.md.

---

### JSON API Endpoint Base Contract {#json-api-endpoint-base-contract}

**Rule:** Every authed, state-changing JSON endpoint subclasses one of exactly two sanctioned bases. There is no third permanent option.

- ✅ **DRF baseline** (`rest_framework.views.APIView` with `SessionAuthentication` for automated CSRF enforcement; permission class per endpoint) — the default for any new JSON endpoint that does not need organization-role scoping. `AllowAny` is used when the view performs its own auth checks (the billing-module pattern); `IsAuthenticated` is the default for endpoints where all requests require an authenticated user. Used by billing, CRM, and forms.
- ✅ **`OrgApiBaseView`** — for endpoints that need organization-role/membership scoping specifically. Chosen as a second sanctioned base rather than reimplementing org-role checks as a DRF permission class, because that logic is tenant-isolation-adjacent (see §multitenant-saas-architecture) and rewriting working, tested code for stylistic consistency alone carries regression risk for no user-visible benefit.
- ❌ A plain-`View` + `@csrf_exempt` + manual `_enforce_csrf()` idiom is not a third sanctioned option and is not grandfathered as legacy — this project removes workarounds rather than permanently tolerating them alongside the sanctioned shape.
- ✅ **Signature-verified webhooks** (Stripe, etc.) are a different trust class, exempt from this rule's authentication and CSRF requirements — the calling party cannot present a CSRF token. They are DRF `APIView`s without authentication, permission, or throttle classes (Module Conventions rule 26), which DRF does not CSRF-check; the signature is their authentication, rule 9's handler renders their errors, and the pairing gate (`scripts/check_csrf_exempt_gate.py`) carries no webhook helper.

**SA215's change to this section has landed** (§[Module Conventions](#module-conventions) rule 9):
`OrgApiBaseView` is a DRF `APIView`, so both bases are DRF views and the plain-`View` idiom is
gone from modules. The blog module's function-view exception below is retired: both blog API
endpoints are DRF views with session authentication only, and `BLOG_API_TOKENS` is removed.

**Retired exception — blog dual-auth function views:** the blog module's `upload_media_api` and
`publish_post_api` were function views paired with `authenticate_blog_api_request()` for
session-or-Bearer-token authentication. Both are now DRF views with session authentication only,
and `BLOG_API_TOKENS` is removed; the CSRF CI gate (`scripts/check_csrf_exempt_gate.py`) no longer
recognizes the retired helper. No new function-view endpoints may use this exception without
explicit approval.

The CSRF CI gate continues to enforce the pairing requirement across all `csrf_exempt` callsites.

**Related docs:** [roadmap.md](./roadmap.md) | [arch-audit.md](../others/arch-audit.md)

---

### Notifications Contract

- Authoritative notifications configuration lives in `quickscale.yml`, generated Django settings, and environment variables. Any `NotificationSettings` admin surface is a read-only operational snapshot only, with no secrets and no alternate mutable config path.
- `modules.notifications.sender_email` defaults to `noreply@example.com` as a local-development placeholder only.
- When `modules.notifications.resend_domain` is set, `quickscale apply` requires a non-placeholder sender email plus a valid `modules.notifications.resend_api_key_env_var` reference; apply fails hard instead of silently leaving live delivery on the console backend.
- Runtime backend selection stays on Django's console email backend until live Resend delivery is fully configured. If the live Resend backend is active anyway and the placeholder sender or resolved API key is still missing, queued deliveries fail explicitly rather than degrading silently.
- Delivery tracking is recipient-granular. A multi-recipient send fans out into one tracked provider send/message ID per recipient delivery record.
- Provider-visible tags/metadata are optional and limited to a tiny non-sensitive allowlist. Internal correlation identifiers stay local to QuickScale-owned records.

### Multi-tenant SaaS Architecture {#multitenant-saas-architecture}

**Architectural Decision:** QuickScale-generated SaaS apps use **PostgreSQL FORCE RLS on a single Railway deployment** — one app service + one PostgreSQL 18 service, all tenants share one database and schema. Organizations are the billing and isolation unit. See [organizations.md](./organizations.md) for the full design and [roadmap.md](./roadmap.md) for open implementation work.

**Chosen shape:**
- ✅ Single Railway project (one app + one PostgreSQL 18 service); Railway bill is flat regardless of tenant count
- ✅ Shared database + shared schema; isolation enforced by PostgreSQL FORCE RLS on the 22 shipped ENROLLED models (CRM 7, Forms 4, Billing 4, Blog 4, Listings 1, Social 2) plus ContextVar-driven `TenantManager` scoping — runtime membership is derived from model markers
- ✅ Billing unit: `Subscription → Organization` (not per-user)
- ✅ URL routing: flat routes only — `/crm/`, `/blog/`; no `/orgs/<slug>/` content routes
- ✅ Regular users belong to exactly one organization; no org switcher in the user-facing UI (see §[Module & Theme Architecture](#module-theme-architecture) → Multi-org membership)
- ✅ Module access is differentiated by credits plus ORM-backed `Plan.features` gates

**RLS enforcement rule (critical):**
- RLS enforces only when the app connects as the restricted `NOSUPERUSER/NOBYPASSRLS` runtime role selected by `RUNTIME_DATABASE_URL`
- Generated runtime serving now fails closed when `RUNTIME_DATABASE_URL` is unset; only the named privileged command paths intentionally use the superuser `DATABASE_URL`
- **Always-on boot guard:** `orgs.QuickscaleOrgsConfig.ready()` asserts `rolbypassrls=false AND rolsuper=false` on every boot where `QUICKSCALE_PRIVILEGED_COMMAND` is unset or set to an unrecognised value — regardless of `QUICKSCALE_ORGS_MODE` or `DEBUG`. Raises `ImproperlyConfigured` if the connected role has BYPASSRLS and/or SUPERUSER unless one of the two explicit exemptions applies:
  1. `QUICKSCALE_PRIVILEGED_COMMAND` set to a sanctioned privileged DB command (`migrate` or `createcachetable`) — the deployment `start.sh` and `quickscale manage` unset `RUNTIME_DATABASE_URL` so these operations run under the superuser role (correct and deliberate). The two-command contract is independently declared by the `orgs` module guard (`_PRIVILEGED_COMMANDS` in `checks.py`), the `quickscale_core.runtime.settings` facade, the CLI producer, and the generated `start.sh` launcher; none is a single source of truth, and all four must remain fail-closed and aligned.
  2. `QUICKSCALE_ALLOW_BYPASSRLS=1` — non-serving environment-variable escape hatch for intentional single-tenant/development use. It is never a production serving mode.
- `start.sh` deliberately unsets `RUNTIME_DATABASE_URL` for `migrate` and `createcachetable`; supplied argv exits 2 without a privileged path; `runserver`/`gunicorn` must still use the restricted runtime role
- `quickscale manage` clears `RUNTIME_DATABASE_URL` only for those two sanctioned commands; every other management command (for example `createsuperuser`) runs under the restricted runtime role, which the boot guard requires
- Runtime-role provisioning is not a third privileged Django command: when `RUNTIME_DB_PASSWORD` is set (as `quickscale deploy railway` does), `start.sh` creates or updates the `NOSUPERUSER/NOBYPASSRLS` role with a direct superuser `DATABASE_URL` connection *before* Django boots, so the guard and the two-command contract are untouched. It refuses a role that is the superuser login or an existing superuser

**Isolation architecture rules (permanent):**

- Runtime tenant classification and membership: `is_classified_in_registry()` classifies installed concrete project models from explicit ``tenant_excluded`` markers, ``TenantModel`` inheritance, and implicit M2M-through inference. `is_tenant_model()` and `get_tenant_models()` derive only the positively enrolled tenant-model set from ``TenantModel`` inheritance; ``tenant_excluded`` wins over every enrollment signal, and a ``TenantManager`` on a model that does not inherit ``TenantModel`` fails startup through orgs' ``checks.py`` (Module Conventions rule 13). Classification and FORCE-RLS refresh must not fall back to or consult the literal ``TENANT_TABLE_REGISTRY``. The literal remains only a shipped-module CI parity oracle and is test-owned (Module Conventions rule 34 keeps it out of shipped source). Its 22 shipped ENROLLED models (CRM 7, Forms 4, Billing 4, Blog 4, Listings 1, Social 2) each carry a direct ``organization_id``, inherit the ``objects`` / ``all_objects`` ``TenantManager`` pair from ``TenantModel``, and ship the exact two-policy FORCE-RLS contract rendered by ``apply_force_rls``.
- Project-owned tenant extensions: a concrete model in an installed project app may join the runtime tenant set by inheriting ``TenantModel`` (directly or through a module's abstract base) without a shipped-registry entry or vendored-module edit. Its initial migration owns the table and calls ``apply_force_rls`` to install exactly one tenant-only ``FOR ALL`` base policy plus its ``<base>_select`` operator-read ``FOR SELECT`` policy. Both policies are permissive and apply to ``PUBLIC``; the base policy has identical current-organization ``USING`` and ``WITH CHECK`` predicates, while the select policy has the rendered current-organization-or-operator ``USING`` predicate and no ``WITH CHECK``. Runtime refresh resolves each existing table's unique base policy from ``pg_policies`` before any DDL; missing or ambiguous policy metadata fails before mutation. The base name remains migration-owned rather than inferred from model metadata, but the companion must be named ``<base>_select``. The isolation checks reject a missing, extra, misnamed companion, restrictive, role-limited, or predicate-weakened policy.
- Child tables: every tenant-owned child/detail table must denormalize `organization_id` directly onto the row and use a direct FORCE-RLS policy referencing that column; parent-join RLS policies are not used. This is the project default for all future tables.
- Ambient scoping: request-scoped tenant reads flow through `request.org` → ContextVar (`app.current_org_id`) → `TenantManager`; the authoritative tenant-facing API is ambient manager scoping, not `.for_org(...)` query chaining.
- Operator access: management commands and operator paths use `operator_access(reason=...)` for audited elevated access. When a command or admin path truly needs an unfiltered queryset, it may read from model `all_objects` explicitly under that contract. Self-service account deletion does not receive or yield that context: the orgs-owned `account_deletion_user_reference_organization_ids()` seam validates nullable user relations and returns only matching organization IDs, using one indexed query per matching tenant model; all subsequent nulling remains under each organization's ordinary write scope.
- Org ownership: System org owns all published-public content (blog feed, public listings, social links). Anonymous visitors see System-org rows; solo authenticated = personal org; saas authenticated = active org.
- Teardown policy: `on_delete=PROTECT` on all tenant-owned FKs + explicit `quickscale_orgs_purge_organization` management command for ordered, FK-safe delete — GDPR-capable, no accidental cascade.
- **Composite-FK deferability policy:** every Option C composite FK (the child-table `organization_id` + local-key pair added by the `_ADD_COMPOSITE_FK_SQL` helper in `orgs/_tenancy_equality.py`) is `NOT DEFERRABLE`. On PostgreSQL 18, `SET CONSTRAINTS <name> IMMEDIATE` on a `NOT DEFERRABLE` FK is a no-op, so the constraint is already effectively immediate — `NOT DEFERRABLE` is the fail-fast choice consistent with the [fail-hard principle](#fail-hard-principle) and requires no `SET CONSTRAINTS ALL DEFERRED` carve-out for fixture/loaddata restores. A conformance test validates that every Option C composite FK is `NOT DEFERRABLE`.
- **`tenant_excluded` marker precedence:** in `is_tenant_model()` (`orgs/tenancy.py`), an explicit `tenant_excluded = "reason"` marker on a model takes precedence over class-hierarchy detection (``TenantModel`` inheritance) — a model marked excluded is never classified as tenant-scoped even if it also inherits tenant machinery.
- **Intentional CASCADE exception:** `OrganizationInvitation.invited_by` remains `on_delete=CASCADE` because a pending invitation is an action attributed to its sender—if the sender's account is deleted, the invitation has no meaningful sender identity and dissolving it along with the sender is the correct behavior. This is a narrow, documented exception to the general SET_NULL rule for user-FKs in tenant-scoped models (`PROTECT` is not allowed; Module Conventions rule 27). The other two `CASCADE` user-FKs are `OrganizationMembership.user` and blog's `AuthorProfile.user` (rows that mean nothing without their user); every other user-FK in `quickscale_modules_*` is SET_NULL (enforced by a conformance test in the orgs cross-module test harness).
- **Last-owner `pre_delete` backstop refusal mechanism:** the orgs `pre_delete` receiver on the `User` model raises (does not silently return/no-op) when the deletion would orphan a shared organization's last owner, matching the [fail-hard principle](#fail-hard-principle) — a caller (admin bulk-delete, management command, a future GDPR erasure path) must see a loud failure rather than believe a refused delete succeeded.
### Clean-Break Migration History {#migration-squash-decision}

**Rule:** QuickScale is pre-1.0 and does not support in-place database upgrades
between releases. The supported upgrade path is a fresh database, so every
model-bearing shipped module carries one final-schema `0001_initial` and no
incremental migration history. Service-style modules carry no migrations. This
is a clean-break, fresh-only posture — there is no cross-release backfill or
compatibility migration class. The rules below are standing constraints for
anyone adding or changing migrations.

**Standing rules:**

1. **One `0001_initial` per model-bearing module.** The current ten are auth,
   backups, billing, blog, crm, forms, listings, notifications, orgs, and social.
   Each carries its final model state in a single initial migration with
   `Migration.initial = True`; analytics and storage are service-style and carry
   no migrations. Do not add `0002_*` history or cross-release backfill
   `RunPython` steps. New tenant tables ship with `organization_id NOT NULL` from
   creation.

2. **Each tenant app installs its own RLS.** Every tenant module's `0001_initial` carries its own `RunPython(apply_force_rls, ...)` and is authoritative for its own exact two-policy FORCE-RLS pair. A project-owned tenant app follows the same rule in its own initial migration. The orgs module installs no module-table policy (it runs before enrolled tables exist). `apply_force_rls`/`revert_force_rls` in `orgs/tenancy.py` are the only supported RLS-management entrypoints.

3. **No raw cross-table `organization_id` DML in migrations.** A bounded tripwire test regex-scans for the `UPDATE … SET organization_id` cross-table shape against an explicit allowlist; it is a smoke check, not a soundness proof. Correctness is proven by the `pg_policies`/catalog/data parity gate against the baseline (22 FORCE-RLS tables / 44 policies). Any new allowlist entry must be scoped to exact file-plus-statement identity.

4. **Preserved schema surfaces — keep matching the baseline:** forms' four presets / 16 fields (auto-created via initial data migration), the five parent UNIQUE constraints and six composite FKs, and listings' pinned index names.

5. **Quality maxima are shrink-only.** Remediation may only reduce a measured
   maximum or leave it unchanged. A migration that exceeds a threshold must be
   compacted with a parity proof preserving its exact historical operation,
   schema, data, and reverse contracts — never allowlisted, threshold-exempted,
   or gate-exempted. See §[Quality Baseline Monotonicity](#quality-baseline-monotonicity)
   for how the ceiling comparison is enforced.

**Related docs:** [roadmap.md](./roadmap.md) | [CHANGELOG.md](../../CHANGELOG.md)

**Rejected alternatives (do not re-introduce):**
- ❌ **Per-client Railway deployment** — linear operational overhead per tenant; not a SaaS platform
- ❌ **App-layer-only filtering without RLS** — no defence-in-depth; a single missed filter leaks cross-tenant data
- ❌ **PostgreSQL schema-per-tenant isolation** — schema metadata bloat, migration complexity with many tenants
- ❌ **Supabase as the database provider** — valid for teams that want managed infrastructure, but introduces vendor lock-in and changes the cost/operational model; our self-hosted Railway approach uses the same GUC-carried tenant-context pattern without changing the current contract

**Supabase architecture parity note:** QuickScale's shared-schema + FORCE RLS
model is structurally equivalent to Supabase's — both carry per-transaction tenant
context in a PostgreSQL GUC and isolate with `FORCE ROW LEVEL SECURITY`; only the
injection mechanism differs (PostgREST sets the GUC from JWT claims, QuickScale's
execute-wrapper derives it from the ContextVar at transaction start). The rule this
supports: runtime admin/debug access stays on the restricted role. **BYPASSRLS is
reserved for the migration exception and any future explicitly documented
non-runtime privileged path** — never for a debug or impersonation feature.

**Operator debug mode (VIEW-AS) contract:**
- ✅ VIEW-AS is superuser-only, session-keyed
  (`quickscale_modules_orgs.debug_as_org_id`), and resolved by
  `TenantMiddleware._resolve_debug_org()` ahead of Solo/SaaS resolution
- ✅ Every activation is audit-logged, and a debug banner renders while active
- ❌ No BYPASSRLS — the debug session runs under the same restricted runtime role
  as every other tenant path, so RLS stays fully enforced

Implementation detail: [organizations.md §Operator Debug Mode](./organizations.md#operator-debug-mode-view-as).

**Related docs:** [organizations.md](./organizations.md) (design) | [roadmap.md](./roadmap.md) (current open work) | [arch-audit.md](../others/arch-audit.md) (current risk posture)

---

### Billing Contract

- Authoritative billing configuration lives in `quickscale.yml`, generated Django settings, and environment variables. Planner/apply may write env-var references into managed settings, but Stripe publishable keys, secret keys, and webhook secrets stay environment-only and never persist in QuickScale database rows.
- Billing requires auth-backed users at apply/runtime; QuickScale does not support a standalone billing install without the auth module.
- Billing ships module-owned Django routes for public pricing (`/billing/pricing/`) and the signed-in dashboard (`/billing/dashboard/`). Fresh starter output may link into those pages, but QuickScale does not generate a starter-owned billing React page and does not rewrite existing project React files to adopt billing automatically.
- `WebhookEvent` is the transport-level replay/idempotency gate for incoming billing webhooks.
- `debit_user` is the approved service API for credit consumption.

**Not part of the current contract:**
- ❌ Independent namespace-package distribution for published modules/themes
- ❌ Hook/event systems beyond the documented extension contract
- ❌ Advanced configuration layers beyond the shipped `quickscale.yml` + `.quickscale/state.yml` workflow

---

### Generated-File Ownership (Beta-Migration Taxonomy) {#generated-file-ownership-taxonomy}

**Rule:** The beta-migration maintainer tooling
(``quickscale_devtools/beta_migration/``) carries a file taxonomy that
classifies every generator-emitted file by its migration path. The taxonomy
combines explicit path tuples with operation-derived directory selectors; a conformance gate
(``test_beta_migration_ownership_conformance.py``) derives the expected file
inventory from the template tree (``quickscale_core/generator/templates/``)
and asserts every emitted file is classified.

**Key policy rules:**

1. **``settings/production.py`` is donor-owned by policy, not an omission.**
   The fresh-first migration path intentionally copies the **donor's**
   ``settings/production.py`` onto the fresh recipient (via
   ``FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES`` and
   ``FRESH_FIRST_DONOR_DJANGO_FILES``).  The donor's production settings carry
   the real deploy-time configuration and must not be replaced by the fresh
   scaffold's defaults.  Since SA206 the donor copy must call the versioned
   ``quickscale_core.runtime.settings`` facade; the donor validator refuses an
   inline copy of the command-mode contract before any mutation.

2. **``start.sh`` follows the recipient scaffold's identity.**  The fresh
   scaffold's ``start.sh`` is the effective launcher and is reconciled in
   place: its embedded slug/package references follow the reconciled
   identity, so the createcachetable env-pair fix reaches the migrated
   project through the fresh-first path.  Classified under
   ``FRESH_FIRST_IDENTITY_ROOT_FILES``.

3. **``INTENTIONALLY_UNMANAGED`` is an explicit-only replacement/merge
   ownership class.** Existing files listed there are deliberately outside
   structural replacement and merge paths. A listed path may be created only
   by an explicit copy-if-missing adoption rule, which never overwrites an
   existing user-owned file. The tuple must be empty unless a current template has a
   documented exemption rationale in
   [generated_file_ownership.md](./generated_file_ownership.md). A
   listed file may also receive fresh-first identity-only reconciliation when
   it contains scaffold-derived slug, package, database-role, or frontend
   package values; that bounded rewrite does not transfer file ownership. No
   implicit fallback — every emitted file must be explicitly accounted for.

4. **The conformance gate fails on unclassified files.**  When a new template
   is added or an existing template is renamed without updating the taxonomy,
   the gate surfaces the gap as a test failure listing every unclassified
   emitted path.  This is the systematic prevention for the class of defect
   where a new or renamed template file is silently missed by the migration
   path (e.g. ``start.sh``/``production.py``).

5. **Every ``INTENTIONALLY_UNMANAGED`` entry carries an explicit category and
   rationale.** No entry may be added without stating why that generated file is
   deliberately outside replacement and merge paths. The inventory itself
   (categories U1–U12) is owned by
   [generated_file_ownership.md](./generated_file_ownership.md) — it is data the
   conformance gate cross-checks, not policy.

6. **Directory-level classification support.** The conformance gate
   (``_classify_emitted_path``) checks whether any parent directory of an
   emitted path appears in the classified map as a directory entry (path
   ending in ``/``).  This allows grouping many files under a common
   directory without enumerating every path individually. The conflict gate
   derives replacement, merge, and copy-if-missing dispositions from the same
   constants used by the executor. It prevents a path from being both
   structurally replaced/merged and ``INTENTIONALLY_UNMANAGED``; identity-only
   reconciliation and copy-if-missing adoption are the permitted overlaps
   because neither overwrites user-owned contents.

7. **``MODE_REQUIRED_SPECS`` entries are classification sources, not mutation
   authority.**
   The beta-migration preflight validation specs
   (``COMMON_REQUIRED_SPECS`` and ``MODE_REQUIRED_SPECS`` in the
   ``quickscale_devtools.beta_migration`` package) define files and directories that must exist
   before a migration step can proceed. Some of these specs (notably
   ``frontend/src/App.tsx``) independently appear in an executor-owned
   replacement or merge disposition, but merely being required does not make
   a path structurally managed. The
   conformance test includes all ``MODE_REQUIRED_SPECS`` entries as
   classification sources so that a file like ``frontend/src/App.tsx`` is
   properly categorized as part of the fresh-first required recipient
   surface. The operation-derived disposition model, not this preflight list,
   decides whether overlap with ``INTENTIONALLY_UNMANAGED`` is a conflict.

8. **Fresh-first identity reconciliation covers the complete generated
   identity seam.** The recipient is a throwaway, newly generated scaffold,
   so changing its identity must reconcile every generated occurrence of the
   old slug/package, including derived database role/password values and the
   frontend package name. Reconciliation is field-aware when the source slug
   and package share one token, token-boundary-aware for underscore-bearing
   slugs, and non-cascading. A file can remain user-owned and structurally
   unmanaged while participating in this one-time identity rewrite.

9. **Every structural executor path has an operation-derived disposition.**
   The conformance gate models direct file replacement, directory replacement,
   donor-authoritative merge, and copy-if-missing adoption from the executor's
   constants and selectors. This includes fresh-first component and utility
   directory replacement; a path
   cannot remain ``INTENTIONALLY_UNMANAGED`` merely because the mutation is
   implemented by a directory walk or a dedicated merge helper rather than a
   named copy tuple.

**Removal record:** The in-place beta-migration mode (``make
beta-migrate-in-place``, ``--continue-after-checkpoint``, its infrastructure
copy/apply continuation, and the ``IN_PLACE_*`` taxonomy entries) was removed
when fresh-first became the only migration path.  The remaining taxonomy
classifies every emitted file against that single path, and the smoke gate
exercises the fresh-first path, including one iterate regeneration case.

**Related docs:** [roadmap.md](./roadmap.md) | [arch-audit.md](../others/arch-audit.md) (generated-file ownership finding, if currently open)

---

### Beta-Site External Verification Scope {#beta-site-external-verification-scope}

**Decision:** Verifying the *deployed* state of `experto-ai-web`
and `bap-web` — confirming a specific commit's generator/template changes
actually reached those running sites, checking their live Redis
configuration, or inspecting/patching their donor-owned `settings/production.py`
— is **permanently out of scope for this monorepo's automated tooling and for
any coding-agent session operating inside it.** Neither site's repository nor
its Railway deployment is reachable from here; this is a structural property
of the two-repo maintainer workflow (`quickscale_devtools/beta_migration/`,
[beta-site-migration.md](../planning/beta-site-migration.md)), not a
credentials gap expected to close.

**Rationale:** the beta sites are external, maintainer-operated repositories
outside this monorepo by design (see the Split Branch Distribution model
above and `beta-site-migration.md`'s two-repo migration workflow). No CI job,
generator run, or agent session in this repo can open a shell in Railway or
push to those repos. Treating this as a temporary blocker awaiting "access"
mischaracterizes the boundary — access to another maintainer's private
deployment infrastructure is not something this repo's tooling can or should
grant itself.

**What stays in scope (and is not affected by this decision):** everything
this repo *can* verify mechanically — the generator templates themselves,
the beta-migration file taxonomy and its conformance gate,
and the launcher env-pair contract's correctness in the templates it emits.
Those are the actual defect classes; this decision
only scopes out the one step no in-repo mechanism can perform: confirming a
human maintainer applied the fix to a live external deployment.

**Standing rule for future findings:** any roadmap item, tech-audit finding,
or arch-audit red flag whose acceptance criteria requires inspecting or
patching the live `experto-ai-web`/`bap-web` deployments (not just this
repo's generator output) is closed on discovery with a pointer to this
section, rather than left open as a blocked roadmap item. Record the
manual-verification ask as a maintainer to-do in
[beta-site-migration.md](../planning/beta-site-migration.md) instead of a
roadmap.md checklist entry — the roadmap tracks repo-local implementation
work, not manual maintainer operations against external infrastructure.

**Related docs:** [roadmap.md](./roadmap.md) | [arch-audit.md live findings](../others/arch-audit.md) | [beta-site-migration.md](../planning/beta-site-migration.md)

---

### Test-Commons Ownership Rule {#test-commons-ownership}

**Rule:** Define the boundary between
org-context runtime helpers and cross-module test plumbing, citing the
`apply_force_rls`/`revert_force_rls` seam as the existing house pattern
for a working shared-commons precedent.

**Ownership:**

1. **`quickscale_modules/orgs/` owns org-context runtime helpers** — the
   `reset_current_org_id()`, `org_scope()`, and `operator_access()` public
   API surface is owned by the orgs module and lives in
   `quickscale_modules_orgs.current_org`.  No test code may maintain a
   private copy of these helpers.
2. **`tests_shared/` owns cross-module test plumbing** — reusable fixture
   modules (e.g. `isolation.py`, `reset_state.py`) and any future
   cross-module test infrastructure live under `tests_shared/`.  No module
   conftest may maintain a private copy of the per-test state-reset
   contract or any sanctioned cross-module test utility that already exists
   in `tests_shared/`.

**Precedent — `apply_force_rls`/`revert_force_rls`:** The
`apply_force_rls`/`revert_force_rls` seam is the house pattern for a working
shared-commons relationship.  Orgs owns the RLS policy-management helper,
each tenant module calls it during its own migration, and no module
maintains a private copy.  This same principle extends to the test
plumbing layer.

**Enforcement:** Any module conftest that defines a fixture whose
documentation or identifier references resetting `app.current_org_id`,
`SET ROLE`, execute-wrapper priming memo, or the Django cache should instead import
the shared `reset_test_state` fixture from `tests_shared.reset_state`.
New cross-module test utilities must be placed in `tests_shared/` rather
than duplicated across module conftests.

**Related docs:** [roadmap.md](./roadmap.md) | [CHANGELOG.md](../../CHANGELOG.md)

---

### Rendered-Link Sanitization Ownership (SA98) {#rendered-link-sanitization-ownership-sa98}

**Decision:** The orgs module owns the narrow shared rendered-link sanitization
seam used by the blog and listings modules. The public API is
`quickscale_modules_orgs.sanitization.sanitize_href` and
`quickscale_modules_orgs.sanitization.sanitize_rendered_html`; the consumer
views import the rendered-HTML helper directly and do not define or re-export
local aliases. Direct primitive tests live with the orgs owner, while blog and
listings retain their detail-view regression coverage.

This is a narrow existing-dependency/distribution exception: blog and listings
already depend on and distribute alongside orgs, so placing this security
primitive there avoids a second implementation without adding a new runtime
dependency or package. It is not a generic commons decision, and orgs must not
become a general-purpose utility bucket. New shared helpers still require a
separate ownership decision based on an existing dependency and a concrete
module boundary.

The sanitizer contract remains deliberately limited to scheme checks for
double-quoted rendered `href` attributes and the established allowed-link
semantics; this decision does not authorize unrelated HTML or URL utility
surface.

### Frontend Theme Source De-Specialization {#frontend-theme-despecialization-dormant-files}

**Rule:** `frontend/src` must be project-agnostic and byte-identical across all projects on
the same theme version. Project- and module-specific facts flow only through the existing
`window.__QUICKSCALE__` runtime seam — never baked into frontend source at generation time.
No second injection mechanism.

**Module availability:** the generator emits **every** module's frontend files unconditionally;
absence of a module is expressed only as a runtime flag (`false`), gating routes/rendering.
Dormant module files in generated trees are accepted (tree-shaken from the built bundle). Do
not narrow the emitted file set or the `QuickScaleModules` TS interface per project.

**Project identity** (name, etc.) is read from runtime config, not JSX/source literals. Jinja
specialization is confined to Django-side templates and at most `package.json`.

Rejected: per-project source specialization plus an ownership-manifest overlay — it preserves
the per-file migration merge and a second hand-synced list.

Module Conventions rule 31 fixes what the seam's `modules` flags mean (installed and enabled) and
has the generator render its producer from the discovered module set.

---

<a id="af7-installed-wheel-module-discovery"></a>
### Bundled Module Inventory and Source-Required Paths (AF7)

**Architectural Decision (SA109):** Distinguish authoritative bundled manifest inventory
from real module source. The installed-wheel context uses synchronized bundled manifests
for inventory and discovery; source-required paths remain fail-hard.

The ``quickscale_core`` package ships a synchronized manifest snapshot at
``quickscale_core/data/manifests/*/module.yml`` for every shipped module. Bundled
manifests are inventory metadata, **not** module source trees.

**Resolution precedence** (``get_discovered_module_names``):
1. **Source inventory** — ``quickscale_modules/*/module.yml`` via ``discover_shipped_module_names()``
2. **Bundled inventory** — ``quickscale_core/data/manifests/*/module.yml`` via ``discover_bundled_module_names()``
3. **Fail-hard** — ``ImproperlyConfigured`` if neither source nor bundled inventory is available

**Observable provenance:** The :class:`ModuleResolutionSource` enum in
``module_discovery.py`` exposes which source is currently active (``OVERRIDE``,
``MONOREPO``, ``BUNDLED``). Callers can query ``get_resolution_source()`` to adapt
behaviour or diagnostics to the current context.

**G1–G4 Guardrails:**

| Guard | Mechanism | Scope | Fail behaviour |
|-------|-----------|-------|----------------|
| **G1 — Source inventory** | ``discover_shipped_module_names()`` scans ``*/module.yml`` at the configured base path | Monorepo dev / runtime override | Returns empty list (no manifests found) |
| **G2 — Bundled inventory** | ``discover_bundled_module_names()`` reads ``importlib.resources:quickscale_core/data/manifests/`` | Installed wheel / editable install | ``ImproperlyConfigured`` if manifests dir absent or empty |
| **G3 — Source-required path** | ``get_modules_base_path()`` resolves the monorepo path or override | Any operation needing real module source trees | ``ImproperlyConfigured`` — no fallback to bundled (bundled manifests are not source trees) |
| **G4 — Managed adapter import** | ``refresh_managed_adapters()`` imports ``quickscale_modules_{name}.adapter`` | Wiring-spec assembly for the current managed modules (analytics, backups, billing, blog, CRM, forms, listings, notifications, and social) | ``ImproperlyConfigured`` if adapter package not importable |

**Source-required operations (G3):** ``get_modules_base_path()``,
``discover_shipped_module_paths()``, ``load_module_manifest()``, and
``refresh_managed_adapters()`` all require a resolvable modules base path. They fail hard
(``ImproperlyConfigured``) in the ``BUNDLED`` provenance state. Only
``discover_bundled_module_names()``, ``get_discovered_module_names()``,
``get_resolution_source()``, and ``resolve_required_modules()`` (with the bundled
fallback) work from bundled data alone. ``resolve_required_modules()`` applies a
fail-hard boundary in the bundled fallback path: missing selected or required module
manifests raise ``ImproperlyConfigured`` rather than being silently skipped. This preserves
the AF7 fail-hard intent where it is genuinely load-bearing — generation needs real module
source — while allowing the shipped module universe to be read from the bundled snapshot.

❌ **No import-time filesystem discovery.** Module discovery must be lazy —
resolved on first use (config validation, CLI argument parsing), never at module
import. An eager `AVAILABLE_MODULES = set(get_discovered_module_names())` or a
static `click.Choice` evaluated at load time makes the installed wheel crash on
import in the ``BUNDLED`` context.

**Cross-reference:** This decision is a specific expression of the
`Fail-Hard Principle <#fail-hard-principle>`_: source-required operations fail immediately
with a descriptive ``ImproperlyConfigured`` rather than silently falling back to
incomplete data. The bundled inventory path is not a fail-hard exception — it is a
distinct data source that carries synchronized manifest metadata, not module source trees.
The ``ImproperlyConfigured`` identity rules in
`§ImproperlyConfigured Exception Identity <#improperlyconfigured-exception-identity>`_
apply: contracts-layer catchers import the contracts-layer exception; Django-runtime
catchers import Django's.

---

### Module Presence States {#module-presence-states}

**Architectural Decision (2026-08-28, settling roadmap decision D3):** Module discovery
reports **what it observed**, and each consumer applies its own policy. Presence is a
three-state fact, not a count.

**The three states.** A directory under the active modules base path is exactly one of:

| State | Physical shape | Meaning |
|---|---|---|
| **ABSENT** | no directory | Legitimate subset — a generated project selected fewer modules |
| **ACTIVE** | directory + valid ``module.yml`` | A shipped module available for wiring |
| **INCOMPLETE** | directory present, **no** ``module.yml`` | Ambiguous on its face: placeholder scaffolding, or a corrupt/partial install |

**Why this is a decision and not an implementation detail.** Before the three-state
contract, ``discover_shipped_module_names()`` collapsed ABSENT and INCOMPLETE into the same output —
its own docstring recorded that manifest-less directories are "silently excluded". The
distinguishing fact was discarded at the discovery layer, so every downstream consumer had
to reconstruct it by **counting** against ``AUTHORITATIVE_MODULE_COUNT`` and testing for a
subset. A count is a proxy for information that was thrown away, and the proxy was
implemented twice — in ``refresh_managed_adapters()`` and in
``authoritative_module_names()`` — with a hand-copied ``"Authoritative module inventory
count drift"`` message.

``PLACEHOLDER_MODULE_NAMES = frozenset({"teams"})`` was the proof: ``quickscale_modules/teams/``
(a ``README.md``, no ``module.yml``) is **structurally identical** to a half-installed module,
and the only thing separating them was a hardcoded name. A hand-maintained list of names
standing in for a state the model cannot express is the state model's missing case, written
out by hand.

**The rule.**

1. Discovery **must** report INCOMPLETE distinctly. It may not silently exclude a
   manifest-less directory.
2. Consumers own their policy over the three states, and the policies differ legitimately:
   - **Adapter loading** (``refresh_managed_adapters``) — ABSENT is fine (subset projects are
     the normal case); INCOMPLETE is **fail-hard**.
   - **Release inventory** (``authoritative_module_names``) — the shipped count is authoritative;
     a project subset is not a release inventory and must not be answered with one.
3. The subset-validity rule has **one** implementation. No consumer may hand-copy it or its
   diagnostic text.
4. A placeholder was an INCOMPLETE directory that is **declared** as such, not a name matched
   against a literal set.  The catalog no longer declares any: every directory under
   ``quickscale_modules/`` carries a ``module.yml``, and an incomplete directory fails closed
   (Module Conventions rule 18).
5. No consumer may classify module presence by string-matching an exception message.

**Cross-reference.** This is a direct application of the
`Fail-Hard Principle <#fail-hard-principle>`_. The prior shape carried three silent
fallbacks in one path: discovery silently excluding manifest-less directories, the CLI
silently skipping on a ``"Manifest file not found"`` substring, and
``authoritative_module_names`` silently substituting the bundled inventory under an override.
Reporting the observed state removes all three. It refines, and does not replace,
`§Bundled Module Inventory and Source-Required Paths (AF7) <#bundled-module-inventory-and-source-required-paths-af7>`_:
the OVERRIDE / MONOREPO / BUNDLED precedence answers *where inventory came from*; these states
answer *what was found there*.

---

### Module Version Lockstep and Embed Compatibility {#module-version-lockstep}

**Architectural Decision (SA117):** Shipped modules are versioned in lockstep with the
repository `VERSION`, and an embedded module manifest whose version does not match the
running core is a hard error.

**Rule 1 — Lockstep versioning.** Every `quickscale_modules/*/module.yml` `version:` field
equals the repository `VERSION` at release time. Modules are not independently versioned.
A module's version denotes *which release it shipped with*, not what changed inside it, so
untouched modules are bumped along with everything else.

**Why lockstep and not independent versions:** independent module versions only earn their
keep when mixed-version combinations are supported. The global constraint above — *no
existing users, no migration path, no backward compatibility; every change is a clean
break* — means mixed versions are never a supported configuration. An independent version
number therefore advertises a compatibility model that does not exist, and is worse than no
number at all because consumers reach for it when checking compatibility.

**Rule 2 — Embed compatibility is asserted, not assumed.** Module embedding and managed
wiring regeneration must compare the embedded `module.yml` version against the running
core's version and raise an explicit, descriptive error naming **both** versions when they
differ. A version mismatch must never be allowed to surface as a downstream failure
(missing setting, `KeyError`, absent derivation). This is a specific expression of the
[Fail-Hard Principle](#fail-hard-principle): surface the root cause where it can be fixed.

**Rule 2a — The comparison is canonical, not literal.** Version equality is decided on a
canonical parse, so padded, whitespace-bearing, or otherwise non-canonical spellings
(`0.87.0 `, `0.087.0`) do not satisfy a lockstep check they should fail. A version string
that cannot be canonically parsed is itself a hard error, never a fallback to literal
string comparison — a permissive comparison is the same defect class as the missing
assertion Rule 2 exists to close.

**Rule 3 — Release ordering is mandatory.** The producer publishes mutable
`splits/<module>-module` branches, then seals the release as immutable
`splits/<module>-module/X.Y.Z` tags. The default embed path consumes those
identity-derived tags, not the branches or the working tree. The ordering is fixed: stamp
the version, create the core tag locally, publish the mutable branches, verify by generated project
and deployment, seal the immutable tags, and only then push the core tag — which is the irreversible
publication trigger. The seal step accepts no `EXPECTED_REMOTE_SHA` or `ABSENT` authorization input;
it samples each branch tip, rereads it, requires the tag to be absent or already at the intended
commit, and verifies after pushing.

The executable phases, their exact commands, and the pre-publish quality gate are owned by
[publish_procedure.md](publish_procedure.md).

Publishing core before the splits carry matching manifests ships a `quickscale apply` that
fails for every user selecting any module. This ordering is not advisory.

**Rule 4 — Publication is idempotent up to publication.** Split branches are mutable working
artifacts and may be republished safely as many times as verification requires. This breaks
the publish-before-verification circular dependency: published state must exist before an
installed `apply` can verify it, so publication cannot be modelled as a one-shot mutation.

The same reasoning extends past the seal. Seal verification happens *after* the tags are pushed, so
a failure there must be correctable or the sequence would have an unrecoverable step. Until
the core tag is pushed and the packages published, a split tag has no external consumer and
is correctable: delete the affected remote and local tags, fix the cause, republish the affected
branches, then reseal and re-verify. The executable loop is owned by
[publish_procedure.md](publish_procedure.md#re-entrancy-summary).

`_seal_module` deliberately refuses to move a tag that exists at a different commit — that
guardrail catches *accidental* moves, and the deletion above is the explicit, intentional
override. Correction is bounded by publication, not by the seal: after the core tag is
pushed and PyPI has the packages, the version is spent and a defect costs a new version.

**Rule 5 — Embed by identity-derived immutable ref.** An embed resolves
`splits/<module>-module/X.Y.Z` directly from the running core version. No version-to-ref
mapping table exists because the identity-derived ref makes one unnecessary. A missing
immutable split tag is a hard error. `--split-ref`, and its bulk form
`--split-refs-from-branches`, are explicit maintainer overrides for controlled verification and
do not change the default identity-derived resolution.

**Rule 6 — Tags follow content identity.** When a re-split produces an unchanged tree, the
same commit carries both release-version split tags. Tag reuse follows content identity,
not an assumption that every release changes every module.

**Rule 7 — Seal enforcement is client-side and fail-closed.** Sealing uses
check-then-act: the client samples each remote branch tip, immediately rereads
the branch and rejects movement, requires the immutable tag to be absent or
already at the intended commit, and pushes one explicit tag refspec. A
fail-closed post-push verification rereads both the tag target and branch and
rejects any mismatch. The seal target accepts no pre-authorized SHA or
`ABSENT` value; branch-publication expectations belong only to the preceding
`publish-module` loop. The narrow reread-to-push race window is accepted and
detected rather than eliminated; the 2026-08-07 re-scope accepted it because
that window is strictly smaller than the already accepted residual risk that a
force-privileged maintainer can move a tag.

**Known limitation (accepted residual):** split-tag permanence is enforced by client-side
checks plus transport refusal under ordinary permissions, not by a server-side transaction
or an unbypassable repository policy. A force-privileged maintainer can still move a tag;
that residual is recorded and accepted, while the normal release path remains fail-closed.
Note this is about *unintended* movement. Rule 4's pre-publication correction loop is a
deliberate, documented use of the same privilege, and the fail-closed checks are what force
it to be deliberate — the tooling never moves a tag on its own.

---

### Publish-Path Gate Coverage {#publish-path-gate-coverage}

**Architectural Decision:** The publish path is a **full-coverage** gate context. Every
repository conformance gate required in local and hosted contexts is also required in
`.github/workflows/publish.yml`. Publish is not a narrower context.

**Why publish does not get to trust upstream.** Publishing is the last step and the only
irreversible one: a published artifact reaches users and cannot be recalled, only yanked
after the fact. Every earlier context — local `check`, local CI, hosted CI — gates a state
that is still editable, so a gap there costs a fix. A gap at publish costs a release. The
asymmetry means the last step must **re-verify rather than trust**, even when the same
gates already passed upstream on what is nominally the same commit. Re-running a gate that
will pass is cheap; discovering at publish time that a required property was never checked
in the path that ships is not.

**Rule — no silent narrowing.** A gate absent from a required context is a defect unless
that absence is a *declared exclusion* carried as registry metadata with a recorded
rationale. An undeclared absence is an unowned gap, not an intentional design. This applies
to every gate context, but publish specifically may not hold exclusions for reasons of
redundancy or cost — those are exactly the reasons that produce a false-green release path.

**Consequence.** A parity checker failing on a gate missing from `publish.yml` is
reporting a real defect. Close the gap by adding the gate — never by declaring an
exclusion to silence the check. Open gap status is tracked in
[roadmap.md](./roadmap.md).

---

### Integration-Branch CI Coverage {#integration-branch-ci-coverage}

**Architectural Decision:** Hosted CI is **not** triggered on `vNN` integration branches.
`.github/workflows/ci.yml` keeps its `main`/`develop` push and `main` pull-request triggers.
Gate coverage during an integration window rests on the local run of the same registered gate
set, and the accepted gap is recorded here rather than left unowned.

**Why the trigger is not extended.** An integration branch takes many small commits, and three
tracks merge into it through a serialized queue. Running the hosted set on every push there
charges the full gate cost — including the BYPASSRLS lane, E2E, and the Docker-backed stations —
against ordinary development turnaround, on a branch whose state is still editable. The friction
is paid continuously; the coverage it buys is already obtainable locally on demand, and is
re-obtained unconditionally before anything ships.

**The compensating local step.** `make ci` runs the registered gate set locally with its own
PostgreSQL lifecycle; `make ci-e2e` adds the E2E and privileged lanes. Parity between the local,
hosted, and publish sets is machine-checked against `scripts/gate_registry.json`, so each context
runs its declared set rather than a hand-picked subset — the registry records per-gate context
membership, including the local-only quality ratchet and the hosted-only commit-testimony gate. A
partial run announces itself as `PARTIAL CI — NOT a full pass` and does not count.

**Where coverage is mandatory rather than discretionary.** The publish quality check requires
`QS_E2E_INTEGRATION_REF=<integration-branch> make ci-e2e` on the exact bytes being published
([publish_procedure.md §1.2](publish_procedure.md#12-release-tier-validation)), and the tag push
re-runs the full set hosted under the
[publish-path full-coverage rule](#publish-path-gate-coverage). Merging the integration branch
into `main` opens a pull request, which is a hosted trigger. So no release and no `main` history
is reached without a hosted full-set run; what is accepted is the absence of hosted gating
*between* those points.

**Rule.** This acceptance covers the trigger surface only. It is **not** an exclusion: no gate
may leave the registered set, and parity must stay green across registry, Makefile, workflow,
and local script. The accepted residual is that a red gate on an integration branch can go
unnoticed until the maintainer next runs `make ci`, the branch is proposed into `main`, or the
publish gate runs. Revisit if the repository gains a second regular contributor, since the
compensating step is one maintainer's discipline and does not generalize.

---

### Quality Baseline Monotonicity Gate (SA121) {#quality-baseline-monotonicity}

**Rule:** The shrink-only quality baseline (`scripts/quality_baseline.json`) is
enforced against its **merge-base ancestor**, never against its own current
values. Any ceiling increase relative to the merge-base blob is a violation
unless a structured, time-bounded waiver in `scripts/quality_waivers.json`
covers it.

**Why a separate helper exists:** `check_quality.sh` reads the current baseline
and trusts it as authority, so an edit that raises a ceiling simultaneously
erases the evidence of the prohibited growth.
`scripts/check_quality_baseline_monotonicity.py` uses a different comparison
authority — the merge-base blob from Git — so the growth stays visible.

**Standing constraints:**

- ✅ An active waiver is the only thing that clears an increase; every other
  ledger state (malformed, duplicate, expired, orphan, stale base, over
  ceiling) blocks the gate, as does missing coverage
- ✅ Every waiver carries an owner, a reason, an expiry date, and a
  `decision_ref` that MUST resolve to an anchor declared in **this file** — a
  waived increase with no recorded decision is not a decision
- ✅ The gate reads the merge-base blob from the local Git object store only
- ❌ No automatic fetch, no `HEAD`/`HEAD^` fallback, and no silent skipping when
  the base ref or base blob cannot be resolved — that is a hard failure, per
  §[Fail-Hard Principle](#fail-hard-principle)
- ❌ No migration or other historical artifact may be allowlisted, threshold-
  exempted, or gate-exempted to avoid this check (see
  §[Migration-Squash Decision](#migration-squash-decision) rule 5)
- ✅ Per-file line ceilings are part of the ratchet again, under the
  `file_length` section (SA231): every entry carries its `max_lines` ceiling
  and the reason it is listed. Line counts are baseline entries, monotonicity
  keys, waiver keys, regressions, and gate exit-status inputs for files at or
  above 800 lines; the retired `large_files` name stays ignored. See
  [File-Size Metric Policy](#file-size-metric-policy). The baseline sections
  are `dead_code`, `complexity`, `file_length`, and `duplication`.

**Specification** — the baseline and waiver-ledger schemas, the waiver state
machine, the canonical diagnostic record, the deterministic error envelope,
ceiling-index construction, and merge-base resolution precedence are owned by
[quality_tools.md §Baseline Monotonicity Gate](./quality_tools.md#baseline-monotonicity-gate-sa121).

<!-- Compatibility anchors for inbound links and waiver `decision_ref` values.
     The specification they name is owned by quality_tools.md. -->
<a id="exact-baseline-schema"></a>
<a id="exact-waiver-ledger-schema"></a>
<a id="canonical-diagnostic-record"></a>
<a id="deterministic-error-envelope"></a>
<a id="waiver-state-machine"></a>
<a id="validated-ceiling-indexes"></a>
<a id="merge-base-resolution-precedence"></a>

**Related docs:** [quality_tools.md](./quality_tools.md#baseline-monotonicity-gate-sa121) |
[arch-audit.md current posture](../others/arch-audit.md) | [roadmap.md](./roadmap.md) |
[CHANGELOG.md closure history](../../CHANGELOG.md)

---

### File-Size Metric Policy {#file-size-metric-policy}

**Rule:** Files at or above 800 lines are gated by the quality ratchet. The
baseline's `file_length` section lists each accepted file with its `max_lines`
ceiling and the reason it is listed; `make quality` fails when a file at or
above 800 lines is unlisted or grows past its ceiling, and the merge-base
monotonicity gate treats each ceiling as a ratchet key. Files below 800 lines
remain advisory diagnostics. The retired `large_files.max_lines` name is never
indexed.

**One-time re-baseline (SA231).** The closing batch re-tightened the baseline
to the measured tree and recorded each increase against the merge base as a
time-bounded waiver expiring 2027-03-31. From that baseline on the ratchet is
shrink-only: a new or worsened finding fails `make quality` until it is fixed
or a new decision waives it.

**Related docs:** [Quality Baseline Monotonicity Gate](#quality-baseline-monotonicity) |
[roadmap.md](./roadmap.md) | [CHANGELOG.md](../../CHANGELOG.md)

---

## Prohibitions (Critical - DO NOT)

**Database:**
- ❌ SQLite for any purpose — dev, test, or production (see §Database Policy above); `django.db.backends.sqlite3` in any test settings file is a policy violation that must be resolved before merge
- ❌ `skipif(not postgres)` guards that allow isolation tests to be silently skipped rather than failing the build when Postgres is unavailable

**Multi-tenant / Tenant Isolation:**
- ❌ Per-client Railway deployment (linear overhead per tenant — not a SaaS platform)
- ❌ App-layer-only filtering without a PostgreSQL RLS backstop (no defence-in-depth; one missed filter leaks cross-tenant data)
- ❌ PostgreSQL schema-per-tenant isolation (schema metadata bloat, migration complexity)
- ❌ Connecting generated apps in saas/prod mode under a BYPASSRLS or SUPERUSER role (silently disables all RLS policies across all modules)
- ❌ Route-slug-based org resolution for content routes (`/orgs/<slug>/crm/...`) — use flat routes + session active-org; org-admin API may keep `/orgs/api/<slug>/`

**Package Structure:**
- ❌ Nested package names (NO `quickscale/quickscale_core`)
- ❌ Tests inside `src/` (place in parallel `tests/` directory)
- ❌ Treating package `README.md` files as authoritative over root docs or `decisions.md`
- ❌ NEVER run `quickscale plan`/`quickscale apply` in the QuickScale codebase (would generate unwanted project files)
- ❌ Standalone `poetry install`/`poetry lock` of an individual `quickscale_modules/*` package outside the monorepo — not a supported use case; see §Package Structure below

**Dependencies & Versions:**
- ❌ Unpinned versions in production
- ❌ Black or Flake8 (use Ruff instead)
- ❌ requirements.txt or setup.py (use Poetry + pyproject.toml)

**Architecture & Patterns:**
- ❌ Runtime dynamic `INSTALLED_APPS` modifications
- ❌ DI frameworks or service registries (direct imports in production); `AppConfig`-declared capabilities collected by one core helper and the listed core ports are the allowed forms — see §[Module Conventions](#module-conventions)
- ❌ Module settings read with a code default or a reader that defaults or coerces, another module's settings, or a settings snapshot outside the private `_settings.py`; module-to-module imports outside the target's public surface or against the layer order — see §[Module Conventions](#module-conventions)
- ❌ Custom abstract provider interfaces or app-defined multi-provider contracts (use Django's email path plus `django-anymail` for the approved provider rather than building a generic provider layer)
- ❌ Custom database table naming (use Django's `app_label` default)
- ❌ Core fallback adapters, compat shims, or silent degradation paths — see §[Fail-Hard Principle](#fail-hard-principle). This includes any "compatibility fallback" wiring path for bundled/installed contexts: an unimportable managed adapter raises, it does not degrade (AF7 **G4**)
- ❌ Per-module wiring knowledge inside `quickscale_core` or `quickscale_cli` — a module declares its own wiring in its own `module.yml` and executes it through its own `adapter.py`; see §[Module Wiring Authority](#module-wiring-authority)
- ❌ Manifest keys that the loader parses but no live code path projects into wiring — derive the key or delete it from the schema
- ❌ Ad hoc or undocumented module HTTP APIs beyond the documented module-owned routes and webhooks QuickScale wires today
- ❌ Tight coupling themes to modules

**Module Versioning & Embedding:**
- ❌ Independent per-module version numbers — every `module.yml` `version:` tracks the repository `VERSION` (see §[Module Version Lockstep](#module-version-lockstep))
- ❌ Publishing `quickscale_core`/`quickscale_cli` to PyPI before the matching `splits/*` branches are pushed — ships a `quickscale apply` that fails for every user
- ❌ Letting an embedded/core version mismatch surface as a downstream failure (missing setting, `KeyError`) instead of an explicit version-mismatch error

**Configuration:**
- ❌ Execute code in config files (pure data YAML only)
- ❌ Deep nesting in config syntax (keep flat and readable)

## Package Structure

**Standalone module installation is not supported.** Individual
`quickscale_modules/*` packages are never installed or resolved on their own
outside the monorepo — they run interconnected, wired together by
`quickscale plan`/`quickscale apply` into a generated project.

- ✅ The root `pyproject.toml` is the single source of dependency resolution: it
  wires every module in as a `path = "...", develop = true` dependency and
  resolves them together into one `poetry.lock`
- ✅ `quickscale_modules/` and `quickscale_themes/` are PEP 420 namespaces (no
  `__init__.py` at the namespace root); `quickscale_core` is a regular package
- ✅ Use `find_namespace_packages()` in `pyproject.toml`
- ✅ CI fails the build if a namespace `__init__.py` exists
- ❌ No per-module `poetry.lock` files
- ❌ No sibling-module version-range dependencies (a module pyproject declaring
  `quickscale-module-orgs = ">=x,<y"` instead of relying on root path wiring)
- ❌ No other standalone-install machinery for a module package

**Layout examples:**

```
quickscale_core/            # src/ layout, tests parallel to src/
  pyproject.toml
  src/quickscale_core/
    __init__.py
    apps.py
  tests/

quickscale_themes/ecommerce/src/quickscale_themes/ecommerce/...
# NO __init__.py at quickscale_themes/
```

**Compatibility metadata:**
```toml
[project.metadata.quickscale]
core-compatibility = ">=2.0.0,<3.0.0"
```

Full naming/import matrix: [scaffolding.md §6](./scaffolding.md#6-naming-import-matrix-summary).
Module responsibility boundaries:
[implementation_contract.md §Module Boundaries](./implementation_contract.md#module-boundaries).
