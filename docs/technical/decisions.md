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
  the affected tags → reseal, until the release converges. After `make
  publish-prod` the version is permanent and a defect is corrected by a new
  version. See §[Module Version Lockstep](#module-version-lockstep) Rule 4 for
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

**Teams tie-breaker:** `quickscale_modules/teams/` is a README-only placeholder.
It is **not next** and **not planned** — no committed timeline, no kickoff date.
[arch-audit.md](../others/arch-audit.md) findings whose horizon keys off "teams
kickoff" (e.g. `deletion-invariants-per-boundary-reimplementation`,
`org-model-universe-hand-enumerated`) describe conditions that apply *if and when*
teams is scheduled. Treat them as open-ended and deferred — not roadmap items on a
clock — until a scheduling decision is recorded here.

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
- ✅ Scheduled execution is command-driven only (`manage.py backups_create
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

**Constraints:**
- ✅ Derivation types are frozen dataclasses and all field types are YAML-safe
  (scalars, lists, dicts), so `module.yml` `derivation:` sections round-trip
  through `yaml.safe_load` without custom codecs
- ✅ `ModuleDerivationSchema` is a **companion** to `ModuleManifest` — it does not
  extend, subclass, or alter `ModuleManifest` or `ConfigOption`
- ✅ Runtime derivation execution is currently active for analytics and listings;
  completing the migration across the remaining modules is separate work
- ❌ No new imperative `normalize_*` / `validate_*` contract logic, and no
  hand-written CLI contract files — an imperative-freeze guardrail enforces this

Type reference:
[implementation_contract.md §Manifest Adapter Architecture](./implementation_contract.md#manifest-adapter-architecture).


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

**Validation and Automation Entry Points:** See [validation_policy.md](./validation_policy.md#repository-command-reference) for the authoritative repository command baseline and assistant guidance.

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
- **validation_policy.md**: Validation entrypoints, testing standards, coverage expectations, and E2E guidance
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
- **roadmap.md**: Timeline, phases, tasks, and active or unreleased release closeout status
- **README.md**: Project overview, user guide, repo-level navigation
- **package README.md files**: Package-local installation and responsibility summaries (informational only)
- **commercial.md**: Commercial distribution background and constraints

**Rule:** Update the narrow owner first when changing its slice. Update decisions.md in the same change when the repository-wide ownership map, policy, or tie-breakers change.

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
   require the superuser ``DATABASE_URL`` (``migrate``, ``createcachetable``).
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
| ``QUICKSCALE_PRIVILEGED_COMMAND`` | ``migrate``, ``createcachetable`` | ``start.sh`` (inline prefix) | ``DATABASE_URL`` (superuser) |
| ``QUICKSCALE_NON_DB_COMMAND`` | ``collectstatic``, ``compilemessages`` | ``Dockerfile`` build step (inline prefix) | Dummy ``postgresql://`` URL |

**Related:** [Fail-Hard Principle](#fail-hard-principle) (the mutual-exclusion
check and missing-arg validation follow fail-hard); [Multi-tenant SaaS
§RLS enforcement rule](#multitenant-saas-architecture) (the runtime role's
``NOSUPERUSER``/``NOBYPASSRLS`` is the reason privileged commands need the
superuser ``DATABASE_URL``).

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
- ❌ Signature-verified webhooks (Stripe, etc.) are a different trust class and are exempt from this rule — they use `csrf_exempt` because the calling party cannot present a CSRF token; verified instead by the pairing gate (`scripts/check_csrf_exempt_gate.py`).

**Narrow documented exception — blog dual-auth function views:** The blog module ships two function views (`upload_media_api` and `publish_post_api` in `quickscale_modules_blog.views`) that use `@_typed_csrf_exempt` (a type-preserving wrapper around `csrf_exempt`) paired with `authenticate_blog_api_request()` for session-or-Bearer-token authentication. This path is not a class-based view and does not subclass either sanctioned base; it is a deliberately narrow exception justified by the function-view architecture and the dual auth model (session + token). The CSRF CI gate (`scripts/check_csrf_exempt_gate.py`) explicitly recognizes `authenticate_blog_api_request` as an approved verification helper, so this exception is enforced rather than silent. No new function-view endpoints may use this exception without explicit approval.

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
- ✅ Shared database + shared schema; isolation enforced by PostgreSQL FORCE RLS on the 21 ENROLLED models (CRM 7, Forms 4, Billing 3, Blog 4, Listings 1, Social 2) plus ContextVar-driven `TenantManager` scoping — the authoritative registry overview is derived from model markers
- ✅ Billing unit: `Subscription → Organization` (not per-user)
- ✅ URL routing: flat routes only — `/crm/`, `/blog/`; no `/orgs/<slug>/` content routes
- ✅ Regular users belong to exactly one organization; no org switcher in the user-facing UI (see §[Module & Theme Architecture](#module-theme-architecture) → Multi-org membership)
- ✅ Module access is differentiated by credits plus ORM-backed `Plan.features` gates

**RLS enforcement rule (critical):**
- RLS enforces only when the app connects as the restricted `NOSUPERUSER/NOBYPASSRLS` runtime role selected by `RUNTIME_DATABASE_URL`
- Generated runtime serving now fails closed when `RUNTIME_DATABASE_URL` is unset; only the named privileged command paths intentionally use the superuser `DATABASE_URL`
- **Always-on boot guard:** `orgs.QuickscaleOrgsConfig.ready()` asserts `rolbypassrls=false AND rolsuper=false` on every boot where `QUICKSCALE_PRIVILEGED_COMMAND` is unset or set to an unrecognised value — regardless of `QUICKSCALE_MODE` or `DEBUG`. Raises `ImproperlyConfigured` if the connected role has BYPASSRLS and/or SUPERUSER unless one of the two explicit exemptions applies:
  1. `QUICKSCALE_PRIVILEGED_COMMAND` set to a sanctioned privileged DB command (`migrate`, `createcachetable`) — the deployment `start.sh` unsets `RUNTIME_DATABASE_URL` so these operations run under the superuser role (correct and deliberate). The sanctioned command set is defined by `_PRIVILEGED_COMMANDS` in `apps.py`; every new sanctioned command is added there.
  2. `QUICKSCALE_ALLOW_BYPASSRLS=1` — environment-variable escape hatch for intentional single-tenant or development use.
- `start.sh` deliberately unsets `RUNTIME_DATABASE_URL` for `migrate` and `createcachetable`; `runserver`/`gunicorn` must still use the restricted runtime role

**Isolation architecture rules (permanent):**
- Registry authority: the marker-based derived registry overview (:func:`get_derived_registry_overview`) is the authoritative human-readable view of the shipped tenant-table surface. The derived view is purely marker-driven (``tenant_excluded`` attributes, ``TenantManager``/``TenantModel`` detection, and implicit M2M through inference) with no fallback to the literal ``TENANT_TABLE_REGISTRY``. The literal ``TENANT_TABLE_REGISTRY`` remains in place as a cross-check target so CI can confirm the two views stay in agreement. Its 21 ENROLLED models (CRM 7, Forms 4, Billing 3, Blog 4, Listings 1, Social 2) each carry a direct ``organization_id``, ``objects = TenantManager()``, ``all_objects = TenantManager(super_scope=True)``, and a live FORCE-RLS policy.
- Child tables: every tenant-owned child/detail table must denormalize `organization_id` directly onto the row and use a direct FORCE-RLS policy referencing that column; parent-join RLS policies are not used. This is the project default for all future tables.
- Ambient scoping: request-scoped tenant reads flow through `request.org` → ContextVar (`app.current_org_id`) → `TenantManager`; the authoritative tenant-facing API is ambient manager scoping, not `.for_org(...)` query chaining.
- Operator access: management commands and operator paths use `operator_access(reason=...)` for audited elevated access. When a command or admin path truly needs an unfiltered queryset, it may read from model `all_objects` explicitly under that contract.
- Org ownership: System org owns all published-public content (blog feed, public listings, social links). Anonymous visitors see System-org rows; solo authenticated = personal org; saas authenticated = active org.
- Teardown policy: `on_delete=PROTECT` on all tenant-owned FKs + explicit `purge_organization` management command for ordered, FK-safe delete — GDPR-capable, no accidental cascade.
- **Composite-FK deferability policy:** every Option C composite FK (the child-table `organization_id` + local-key pair added by the `_ADD_COMPOSITE_FK_SQL` helper in `orgs/tenancy.py`) is `NOT DEFERRABLE`. On PostgreSQL 18, `SET CONSTRAINTS <name> IMMEDIATE` on a `NOT DEFERRABLE` FK is a no-op, so the constraint is already effectively immediate — `NOT DEFERRABLE` is the fail-fast choice consistent with the [fail-hard principle](#fail-hard-principle) and requires no `SET CONSTRAINTS ALL DEFERRED` carve-out for fixture/loaddata restores. A conformance test validates that every Option C composite FK is `NOT DEFERRABLE`.
- **`tenant_excluded` marker precedence:** in `is_tenant_model()` (`orgs/tenancy.py`), an explicit `tenant_excluded = "reason"` marker on a model takes precedence over manager/base-class detection (`TenantManager`/`TenantModel` inheritance) — a model marked excluded is never classified as tenant-scoped even if it also inherits tenant machinery.
- **Intentional CASCADE exception:** `OrganizationInvitation.invited_by` remains `on_delete=CASCADE` because a pending invitation is an action attributed to its sender—if the sender's account is deleted, the invitation has no meaningful sender identity and dissolving it along with the sender is the correct behavior. This is a narrow, documented exception to the general SET_NULL/PROTECT rule for user-FKs in tenant-scoped models. Every other user-FK in `quickscale_modules_*` is SET_NULL or PROTECT (enforced by a conformance test in the orgs cross-module test harness).
- **Last-owner `pre_delete` backstop refusal mechanism:** the orgs `pre_delete` receiver on the `User` model raises (does not silently return/no-op) when the deletion would orphan a shared organization's last owner, matching the [fail-hard principle](#fail-hard-principle) — a caller (admin bulk-delete, management command, a future GDPR erasure path) must see a loud failure rather than believe a refused delete succeeded.
### Migration-Squash Decision {#migration-squash-decision}

**Rule:** The project has no deployed database to preserve, so every module's migration history is a single final-schema `0001_initial` with `organization_id NOT NULL` from row zero. This is a fresh-only posture — there is no cross-org backfill migration class. The rules below are standing constraints for anyone adding or changing migrations.

**Standing rules:**

1. **One `0001_initial` per module.** Each of the nine modules (orgs, auth, blog, crm, forms, listings, billing, social, notifications) carries its final model state in a single initial migration. Do not add backfill `RunPython` steps for `organization_id`; new tenant tables ship with `organization_id NOT NULL` from creation.

2. **Each tenant module installs its own RLS.** Every tenant module's `0001_initial` carries its own `RunPython(apply_force_rls, ...)` and is authoritative for its own FORCE-RLS policy. The orgs module installs no module-table policy (it runs before enrolled tables exist). `apply_force_rls`/`revert_force_rls` in `orgs/tenancy.py` are the only supported RLS-management entrypoints.

3. **No raw cross-table `organization_id` DML in migrations.** A bounded tripwire test regex-scans for the `UPDATE … SET organization_id` cross-table shape against an explicit allowlist; it is a smoke check, not a soundness proof. Correctness is proven by the `pg_policies`/catalog/data parity gate against the baseline (21 FORCE-RLS tables / 42 policies). Any new allowlist entry must be scoped to exact file-plus-statement identity.

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
(``quickscale_devtools/beta_migration.py``) carries a file taxonomy that
classifies every generator-emitted file by its migration path.  The taxonomy
is a set of explicit tuple literals; a conformance gate
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
   scaffold's defaults.  The in-place path does not touch ``production.py``
   because it is not an infrastructure-metadata file — it is hand-written
   production configuration that the existing beta site already has.

2. **``start.sh`` is an in-place infrastructure target.**  The in-place
   migration path delivers template-derived infrastructure files
   (``Dockerfile``, ``docker-compose.yml``, etc.) into the existing beta site.
   ``start.sh`` is managed the same way so the createcachetable env-pair
   fix reaches beta sites through the in-place path (the path that existing
   sites actually use).  Classified under ``IN_PLACE_INFRASTRUCTURE_TARGETS``.

3. **``INTENTIONALLY_UNMANAGED`` is an explicit-only class.**  Files listed
   there are deliberately outside all migration paths.  The tuple must be
   empty unless a current template has a documented exemption rationale in
   this section of ``decisions.md``.  No implicit fallback — every emitted
   file must be explicitly accounted for.

4. **The conformance gate fails on unclassified files.**  When a new template
   is added or an existing template is renamed without updating the taxonomy,
   the gate surfaces the gap as a test failure listing every unclassified
   emitted path.  This is the systematic prevention for the class of defect
   where a new or renamed template file is silently missed by both migration
   paths (e.g. ``start.sh``/``production.py``).

5. **Every ``INTENTIONALLY_UNMANAGED`` entry carries an explicit category and
   rationale.** No entry may be added without stating why that generated file is
   deliberately outside all migration paths. The inventory itself (categories
   U1–U15) is owned by
   [generated_file_ownership.md](./generated_file_ownership.md) — it is data the
   conformance gate cross-checks, not policy.

6. **Directory-level classification support.** The conformance gate
   (``_classify_emitted_path``) checks whether any parent directory of an
   emitted path appears in the classified map as a directory entry (path
   ending in ``/``).  This allows grouping many files under a common
   directory without enumerating every path individually.  The conflict
   gate prevents the same path from appearing in both a managed tuple
   and ``INTENTIONALLY_UNMANAGED``.

7. **``MODE_REQUIRED_SPECS`` entries are also managed classification sources.**
   The beta-migration preflight validation specs
   (``COMMON_REQUIRED_SPECS`` and ``MODE_REQUIRED_SPECS`` in
   ``beta_migration.py``) define files and directories that must exist
   before a migration step can proceed.  Some of these specs (notably
   ``frontend/src/App.tsx`` in the fresh-first recipient spec) are also
   managed copy targets during the migration itself — they are produced
   by the generator and then consumed by the fresh-first copy step.  The
   conformance test includes all ``MODE_REQUIRED_SPECS`` entries as
   classification sources so that a file like ``frontend/src/App.tsx`` is
   properly categorized as part of the fresh-first required recipient
   surface rather than falling into a ``INTENTIONALLY_UNMANAGED``
   category that would contradict its managed behavior.  The conflict
   gate (rule 6) also checks ``MODE_REQUIRED_SPECS`` entries against
   ``INTENTIONALLY_UNMANAGED``.

**Related docs:** [roadmap.md](./roadmap.md) | [arch-audit.md Finding 7](../others/arch-audit.md)

---

### Beta-Site External Verification Scope {#beta-site-external-verification-scope}

**Decision:** Verifying the *deployed* state of `experto-ai-web`
and `bap-web` — confirming a specific commit's generator/template changes
actually reached those running sites, checking their live Redis
configuration, or inspecting/patching their donor-owned `settings/production.py`
— is **permanently out of scope for this monorepo's automated tooling and for
any coding-agent session operating inside it.** Neither site's repository nor
its Railway deployment is reachable from here; this is a structural property
of the two-repo maintainer workflow (`quickscale_devtools/beta_migration.py`,
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
| **G4 — Managed adapter import** | ``refresh_managed_adapters()`` imports ``quickscale_modules_{name}.adapter`` | Wiring-spec assembly for managed modules (billing, CRM, social) | ``ImproperlyConfigured`` if adapter package not importable |

**Source-required operations (G3):** ``get_modules_base_path()``,
``discover_shipped_module_paths()``, ``load_module_manifest()``, and
``refresh_managed_adapters()`` all require a resolvable modules base path. They fail hard
(``ImproperlyConfigured``) in the ``BUNDLED`` provenance state. Only
``discover_bundled_module_names()``, ``get_discovered_module_names()``,
``get_resolution_source()``, and ``resolve_module_implications()`` (with the bundled
fallback) work from bundled data alone. ``resolve_module_implications()`` applies a
fail-hard boundary in the bundled fallback path: missing selected or implied module
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
identity-derived tags, not the branches or the working tree. For core release
`X.Y.Z`, execute this exact six-step sequence:

1. Bump the repository version, stamp every module manifest, and commit the release state.
2. Create the core tag `X.Y.Z` locally only; do not push it yet.
3. Repeatedly run `make publish-module` for the twelve modules with the
   required per-branch remote expectation, testing installed all-module
   `apply` with `--split-ref` between iterations; repeat until verification is
   satisfactory. This is the reversible branch-publication loop. Before any
   mutating publication command, configure the repository-local credential
   helper and commit identity; publication disables system/global Git config
   and fails once with these commands when any value is absent or blank:
   `git config --local credential.helper '<credential-helper>'`,
   `git config --local user.name '<name>'`, and
   `git config --local user.email '<email>'`. Keep credentials in the helper or
   SSH agent — never place tokens in a remote URL or command argument.
4. Run `make seal-modules VERSION=X.Y.Z` to create and push the twelve
   immutable split tags. The seal command has no `EXPECTED_REMOTE_SHA` or
   `ABSENT` authorization input: it samples each branch tip, immediately
   rereads that branch, checks the tag for absence or an identical target, and
   then performs its explicit tag push and post-push checks.
5. Verify twelve-of-twelve split seals and a clean installed all-module
   `apply` without `--split-ref` or any other override. A failure here returns
   to step 3 under Rule 4's correction procedure; it does not consume the
   version.
6. Run `git push origin X.Y.Z`. Pushing the core tag is the irreversible
   release trigger: the tag-matching publication workflow may publish the
   packages to PyPI. It is distinct from both the repeatable branch loop and
   the already-created immutable split-tag boundary.

Publishing core before the splits carry matching manifests ships a `quickscale apply` that
fails for every user selecting any module. This ordering is not advisory.

**Rule 4 — Publication is idempotent up to publication.** Split branches are mutable working
artifacts and may be republished safely as many times as verification requires. This breaks
the publish-before-verification circular dependency: published state must exist before an
installed `apply` can verify it, so publication cannot be modelled as a one-shot mutation.

The same reasoning extends past the seal. Step 5 verifies *after* step 4 has pushed tags, so
a failure there must be correctable or the sequence would have an unrecoverable step. Until
the core tag is pushed and the packages published, a split tag has no external consumer and
is correctable:

1. Delete the affected remote tag(s) and their local counterparts.
2. Fix the cause and rerun the step-3 branch loop for the affected modules.
3. Rerun `make seal-modules VERSION=X.Y.Z` and step 5.

`_seal_module` deliberately refuses to move a tag that exists at a different commit — that
guardrail catches *accidental* moves, and the deletion above is the explicit, intentional
override. Correction is bounded by publication, not by the seal: after the core tag is
pushed and PyPI has the packages, the version is spent and a defect costs a new version.

**Rule 5 — Embed by identity-derived immutable ref.** An embed resolves
`splits/<module>-module/X.Y.Z` directly from the running core version. No version-to-ref
mapping table exists because the identity-derived ref makes one unnecessary. A missing
immutable split tag is a hard error. `--split-ref` is an explicit maintainer override for
controlled verification and does not change the default identity-derived resolution.

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
- ✅ Per-file line ceilings (`large_files.*.max_lines`) are retired; see
  [File-Size Metric Policy](#file-size-metric-policy). The large-file analyzer
  may report advisory diagnostics, but line counts are not baseline entries,
  monotonicity keys, waiver keys, regressions, or gate exit-status inputs. The
  retained baseline sections are `dead_code`, `complexity`, and `duplication`.

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

**Rule:** Per-file line ceilings are retired from the blocking quality policy.
The large-file analyzer may continue to report advisory diagnostics, but line
counts are not baseline entries, monotonicity keys, waiver keys, regressions, or
gate exit-status inputs. The retained baseline sections are `dead_code`,
`complexity`, and `duplication`.

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
- ❌ Route-slug-based org resolution for content routes (`/orgs/<slug>/crm/...`) — use flat routes + session active-org; org-admin API may keep `/api/orgs/<slug>/`

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
- ❌ DI frameworks or service registries (direct imports in production)
- ❌ Custom abstract provider interfaces or app-defined multi-provider contracts (use Django's email path plus `django-anymail` for the approved provider rather than building a generic provider layer)
- ❌ Custom database table naming (use Django's `app_label` default)
- ❌ Core fallback adapters, compat shims, or silent degradation paths — see §fail-hard-principle
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
