# decisions.md

<!--
decisions.md - Authoritative Technical Policy Hub

PURPOSE: This document is the repository-wide source of truth for cross-cutting architectural decisions, tie-breakers, prohibitions, and technical document ownership for QuickScale.

CONTENT GUIDELINES:
- Record all authoritative architectural decisions with rationale
- Document technical implementation rules (package naming, directory structure, testing)
- Specify behavioral decisions and operational patterns
- List explicit prohibitions (what NOT to do)
- Include detailed technical notes and code examples
- Maintain consistency across all QuickScale packages and extensions
- Update when technical standards change or new decisions are made

WHAT TO ADD HERE:
- New architectural decisions with full context and rationale
- Changes to package naming conventions or directory structures
- Updates to testing strategies or development patterns
- New prohibitions or anti-patterns discovered during development
- Technical implementation details that affect multiple packages
- Integration patterns between core, modules, and themes

WHAT NOT TO ADD HERE:
- Strategic rationale or competitive analysis (belongs in quickscale.md)
- User-facing documentation or getting started guides (belongs in README.md)
- Implementation timelines or roadmap items (belongs in roadmap.md)

TARGET AUDIENCE: Maintainers, core contributors, community package developers, CI engineers
-->

# Technical Decisions (Authoritative)

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Decisions** (Authoritative)
> **Related docs**: [Scaffolding](scaffolding.md) | [Roadmap](roadmap.md) | [Glossary](../../GLOSSARY.md) | [Start Here](../../START_HERE.md)

**Purpose:** Repository-wide policy and tie-breaker hub for QuickScale architecture and development standards. Narrow companion docs under `docs/technical/` own the current implementation contract, validation policy, and structure references.

**Scope:** All first-party packages (core, CLI, themes, modules). Experto-AI and core contributors own these decisions.

## Quick Reference (AI Context)

**Current Essentials:**
- ✅ CLI workflow: `quickscale plan myapp`, enter the generated directory, then run `quickscale apply`
- ✅ Generates standalone Django project (Poetry + pyproject.toml)
- ✅ Production-ready: Docker, PostgreSQL, pytest, CI/CD, security best practices
- ✅ Git subtree for module distribution
- ✅ Declarative YAML configuration (quickscale.yml)

**Development Stack:**
- ✅ Poetry (package manager), Ruff (format + lint), MyPy (type check), pytest (testing)
- ✅ src/ layout for all packages
- ❌ NO Black, NO Flake8, NO requirements.txt, NO setup.py

**Key Constraints:**
- 90% overall mean + 80% per file minimum test coverage (CI enforced)
- decisions.md is the repo-wide tie-breaker; narrow companion docs in `docs/technical/` own current contract, validation, and structure slices
- Package README.md files are informational context only; they MUST defer to root docs
- Settings: Standalone by default (NO automatic inheritance)

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

### Module & Theme Architecture {#module-theme-architecture}

**Architectural Decision:** Modules and themes serve different purposes and use different distribution mechanisms.

#### **Modules: Split Branch Distribution (Ongoing Dependencies)**

**Purpose:** Reusable Django apps that users embed and update over project lifetime.

<a id="integration-note-personal-toolkit-git-subtree"></a>
<a id="module-extraction-workflow"></a>
**Distribution Strategy:**
1. Develop modules on `main` branch in `quickscale_modules/`
2. Auto-split to `splits/{module}-module` branches on release (GitHub Actions)
3. Users embed via `quickscale plan --add <module>` + `quickscale apply`
4. Users update via `quickscale update` (updates installed modules only)

**Workflow:**
```bash
# User adds auth module to configuration
quickscale plan myapp --add auth
# Adds auth module to quickscale.yml

# Apply configuration (embeds module from splits/auth-module)
quickscale apply
# Embeds from splits/auth-module branch to modules/auth/

# Later: Update installed modules
quickscale update
# Updates modules/auth/ and other installed modules

# Contribute improvements back
quickscale push --module auth
# Pushes to feature branch, maintainer merges to main, auto-split updates split branch
```

**Split Branch Architecture:**
```
QuickScale Repo Branches:
├── main                       # All development (implemented modules + placeholders)
├── splits/auth-module         # Auto-generated from quickscale_modules/auth/
├── splits/blog-module         # Auto-generated from quickscale_modules/blog/
└── splits/storage-module      # Auto-generated from quickscale_modules/storage/
```

**User Project Structure:**
```
myproject/
├── .quickscale/
│   └── state.yml              # Sole authoritative applied-state store
├── modules/                   # Embedded modules (git subtrees)
│   ├── auth/                  # From splits/auth-module
│   └── blog/                  # From splits/blog-module
└── myproject/
    └── settings/
  └── base.py            # INSTALLED_APPS = [..., "modules.auth", "modules.blog"]
```

Billing now has a public-ready implementation line in `quickscale_modules/billing` through the current runtime APIs, module-owned billing pages, and React integration guide. Public `quickscale plan`, `quickscale.yml`, and `quickscale apply` flows now surface billing. The generated `showcase_react` SPA surfaces billing as a module flag only (`modules.billing`); it does not currently include billing dashboard cards, sidebar navigation entries, org-dashboard billing cards/links, module paths for billing, or full-document links into billing Django pages. The org-switch blocker that originally prevented these entry points is now resolved — see "Multi-org membership and org-switch" below; restoration is separate implementation work. Teams remains placeholder inventory only.

**Teams module status:** `quickscale_modules/teams/` is a README-only placeholder from early brainstorming; it has never been scoped, designed, or scheduled. It is **not next** and **not planned** — there is no committed timeline or kickoff date. Structural findings in [arch-audit.md](../others/arch-audit.md) that key their horizon or trigger off "teams kickoff"/"the teams build" (e.g. `deletion-invariants-per-boundary-reimplementation`, `org-model-universe-hand-enumerated`) describe conditions that would apply *if and when* teams is scheduled — they are not on a 6–18 month clock and should not be read as committed roadmap items. Treat them as open-ended/deferred until a separate scheduling decision is made and recorded here.

**Key Characteristics:**
- ✅ Runtime dependencies (in INSTALLED_APPS)
- ✅ Updated over project lifetime
- ✅ Backend-heavy (~70% backend, ~30% frontend)
- ✅ Theme-agnostic (work with all themes)
- ✅ Users can contribute improvements back

---

#### **Themes: Generator Templates (One-time Copy)**

**Purpose:** Complete project scaffolding ranging from empty starters to full vertical applications.

**Current Shipped Theme Surface:**

QuickScale currently ships starter themes only:

1. `showcase_react` — **React + TypeScript + shadcn/ui (default)** ✅
  - Empty foundation for custom development
  - Fresh generations include dormant frontend-only PostHog starter wiring in the
    generated `frontend/src/lib/analytics.ts`
  - Fresh generations also auto-generate Django-owned public social entrypoints at
    `/social` and `/social/embeds` that hydrate the shared React bundle outside the
    SPA router
  - Those public pages are fresh-generation scaffolding only; existing projects and
    non-React themes keep manual adoption for any equivalent public pages, while the
    backend-managed social transport endpoints and settings wiring remain theme-agnostic

2. `showcase_html` — Pure HTML + CSS (secondary option)
  - Empty server-rendered foundation with no frontend build toolchain
  - Fresh generations do not scaffold `/social` or `/social/embeds` public
    pages

Planned vertical themes such as CRM remain roadmap work. They are not part of the
current shipped generator surface until a release note and this file explicitly add
them.

Generated starter output surfaces billing as a module flag only (`modules.billing`).
The generated `showcase_react` SPA does not currently include billing dashboard cards, sidebar
navigation entries, org-dashboard billing cards/links, module paths for billing, or
full-document links into billing Django pages. The org-switch blocker that originally
prevented these entry points is now resolved — see "Multi-org membership and org-switch" below; restoration is separate
implementation work. QuickScale does not generate a starter-owned billing React page.
Teams routes, flags, dashboard cards, and navigation remain excluded until teams ships
as a valid public `quickscale plan` / `quickscale.yml` / `quickscale apply` selection.

**Default React Theme Tech Stack:**

| # | Category | Technology | Rationale |
|---|----------|------------|-----------|
| | **Core** | | |
| 1 | Framework | React 19+ | Industry standard, excellent ecosystem |
| 2 | Language | TypeScript | Type safety, better developer experience |
| 3 | Build Tool | Vite | Fast HMR, modern bundling |
| 4 | Package Manager | pnpm | Best disk efficiency, fast installs, enterprise adoption |
| | **UI/Styling** | | |
| 5 | UI Components | shadcn/ui | Copy-paste components, full ownership |
| 6 | Admin Components | shadcn/admin | Pre-built admin patterns |
| 7 | Icons | Lucide React | Clean, modern, shadcn default |
| 8 | CSS Framework | Tailwind CSS | Required by shadcn/ui, utility-first |
| 9 | Animation | Motion (Framer Motion) | De-facto standard for React animations |
| | **Data & State** | | |
| 10 | Routing | React Router v7 | Approved stable routing baseline for QuickScale and matches the shipped `showcase_react` dependency surface |
| 11 | Server State | TanStack Query | Best performance, highest satisfaction |
| 12 | Client State | Zustand | Simplest API, fastest growing, #1 sentiment |
| 13 | Forms | React Hook Form + Zod | Most popular, best performance |
| | **Quality** | | |
| 14 | Unit Testing | Vitest + React Testing Library | Fast, Vite-native, modern |
| 15 | E2E Testing | Playwright | Already in QuickScale |
| 16 | Linting | ESLint + Prettier | Standard tooling |
| | **Backend Integration** | | |
| 17 | Authentication | Django allauth (backend) | Handled by QuickScale auth module |
| 18 | API Client | TanStack Query | Handles fetch + caching |

**Optional Utilities (for CRM):**
- **date-fns** — Date handling (tree-shakeable, shadcn uses it)
- **Recharts** — Charts (shadcn/charts uses it)
- **TanStack Table** — Data tables (shadcn uses it)

**Distribution Strategy:**
1. Store themes in `quickscale_core/generator/templates/themes/{theme_name}/`
2. User selects theme via `quickscale plan` → `quickscale apply`
3. Generator copies theme files to user's project (Jinja2 rendering)
4. User owns generated code completely, customizes immediately
5. **NO embed/update for themes** - one-time scaffolding only

**Workflow:**
```bash
# Create project with default React theme (empty foundation)
quickscale plan myproject
# → Theme defaults to: showcase_react (React + shadcn/ui)
# → Select modules to embed: auth, blog
quickscale apply

# Create project with HTML theme (simpler alternative)
quickscale plan myproject
# → Select showcase_html during the interactive theme prompt
# → Uses pure HTML + CSS instead of React
quickscale apply

# Vertical themes such as CRM remain planned work, not current CLI syntax
```

**Theme Directory Structure:**
```
quickscale_core/generator/templates/
└── themes/
    ├── showcase_react/        # React + shadcn/ui (DEFAULT) ✅
  │   ├── src/
  │   │   ├── components/
  │   │   │   ├── social/
  │   │   │   └── ui/               # shadcn/ui components
  │   │   ├── hooks/
  │   │   │   ├── useModules.ts
  │   │   │   └── usePublicSocialSurface.ts
  │   │   ├── lib/
  │   │   │   ├── analytics.ts      # Dormant PostHog starter helper
  │   │   │   └── utils.ts          # shadcn/ui utilities
  │   │   ├── pages/
  │   │   │   ├── SocialEmbedsPublicPage.tsx
  │   │   │   └── SocialLinkTreePublicPage.tsx
  │   │   ├── App.tsx
  │   │   └── main.tsx
    │   ├── templates/
  │   │   ├── index.html.j2         # SPA entry point
  │   │   └── social/
  │   │       ├── embeds.html.j2    # Django-owned public embed route
  │   │       └── link_tree.html.j2 # Django-owned public social route
  │   ├── components.json.j2
  │   ├── tailwind.config.js.j2
  │   ├── vite.config.ts.j2
  │   └── package.json.j2
    │   └── static/                   # Static assets
    ├── showcase_html/         # Pure HTML + CSS (secondary)
    │   ├── templates/         # No scaffolded public /social pages
    │   └── static/
```

Fresh generations copy `showcase_react/src/**` into the generated project's
`frontend/src/` directory and copy `showcase_react/templates/**` into Django
  `templates/`. Only fresh `showcase_react` generations auto-scaffold the Django-owned
  public `/social` and `/social/embeds` pages. `showcase_html` does not ship those
  public routes/templates, and non-React themes must adopt any equivalent
  public pages manually. QuickScale does not currently ship any vertical theme template
  trees.


**Key Characteristics:**
- ❌ NOT runtime dependencies (just generated code)
- ❌ NO updates after generation (user owns completely)
- ✅ One-time scaffolding, user owns completely
- ✅ `showcase_react` and `showcase_html` are the current shipped starter themes
- ✅ Fresh `showcase_react` generations include dormant analytics starter support and
  Django-owned public social pages
- ✅ Fresh `showcase_html` generations do not scaffold public social pages; non-React
  themes rely on manual adoption for that public page surface
- ✅ Generated starter output surfaces billing as a module flag only (`modules.billing`);
  the generated SPA does not currently include billing dashboard cards, sidebar navigation entries,
  org-dashboard billing cards/links, module paths for billing, or full-document links into
  billing Django pages. The org-switch blocker is resolved — see "Multi-org membership and org-switch" below; these entry points
  can now be restored. Teams routes, navigation, flags, and dashboard cards remain excluded until teams ships
- ❌ Complete vertical themes are not part of the current shipped CLI surface yet
- ✅ Module releases may extend managed backend/runtime surfaces in existing projects, but newly scaffolded theme-owned routes, navigation, registries, and page source are only guaranteed on fresh generation or explicit manual adoption

**Multi-org membership and org-switch:**
Previously, the `showcase_react` SPA performed org-switches client-side while the
server resolved the org from the session, creating a dual-authority problem (a
client-side switch could silently operate on the previous session org).

**Resolution:** Regular SaaS users belong to
exactly one organization. There is no org switcher in the user-facing UI. The
server session (`ACTIVE_ORG_SESSION_KEY`) is the sole authority for org resolution
for regular users, eliminating the dual-source-of-truth problem.

Consequences:
- Billing SPA entry points (dashboard cards, sidebar navigation,
  `modulePaths.billing`) can be restored — the wrong-org-after-switch bug does
  not exist when there is no switch
- The org switcher is removed from the regular user UI
- VIEW-AS (superuser-only session override, already shipped) remains the sole
  path for operator org-scope debugging
- No explicit-org API contract or session-sync endpoint is needed
- Future multi-org membership is not precluded, but would require revisiting
  this decision and implementing the explicit-org API contract at that time

---



#### **Summary: Modules vs Themes**

| Aspect | Modules | Themes |
|--------|---------|--------|
| **Distribution** | Split branches (git subtree) | Generator templates (Jinja2) |
| **User Command** | `quickscale plan --add` | `quickscale plan` (theme selection) |
| **Updates** | `quickscale update` (ongoing) | N/A (user owns code) |
| **Lifecycle** | Runtime dependency | One-time scaffolding |
| **Ownership** | Shared (can push back) | User owns completely |
| **Customization** | Minimal (mostly backend) | Heavy (colors, layout, etc.) |
| **Backend/Frontend** | 70% backend, 30% frontend | 10% backend, 90% frontend |

**For detailed workflow documentation** (split branch mechanics, conflict resolution, troubleshooting), see [§Module & Theme Architecture](#module-theme-architecture) above

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

#### **Operational Properties**

- **Declarative**: User specifies desired state in YAML; tool computes and executes changes
- **Idempotent**: Running apply with unchanged config is safe (no-op, no re-execution)
- **Incremental**: Apply computes delta between desired and applied state; only applies necessary changes
- **Traceable**: State file records what modules/versions/commits were applied and when
- **Recoverable**: State enables drift detection and recovery workflows

#### **Implementation Rules**

**State Computation** (`quickscale apply`):
1. Acquire advisory lock on `.quickscale/state.yml` (fail-fast if held)
2. Read `quickscale.yml` (desired state)
3. Read `.quickscale/state.yml` (applied state; read-through import from legacy `config.yml`/`file_hashes.yml` when consolidated sections are absent)
4. Compute delta (what changed)
5. Show delta to user for confirmation
6. Execute changes
7. Write new state to `.quickscale/state.yml` with consolidated sub-sections
8. Release advisory lock

**Idempotency Requirements**:
- ❌ NEVER re-execute already-applied modules
- ✅ Skip modules that are already embedded
- ✅ Only embed modules that appear in desired state but not in applied state
- ✅ Remove modules that were applied but no longer appear in desired state (future)

**State Integrity**:
- ✅ Write state file atomically (no partial writes)
- ✅ Include timestamps plus canonical installed module version/commit metadata for auditing
- ✅ Never corrupt state from manual edits (reject if format invalid)
- ✅ Advisory lock around `state.yml` read/modify/write so concurrent `apply` fails closed instead of racing

#### **Related Files**

- **Module tracking**: `.quickscale/state.yml` — The sole authoritative applied-state store. Per-module consolidated tracking fields (`prefix`, `branch`, `installed_at`) and the `managed_files` sub-section replace the legacy `config.yml` and `file_hashes.yml`. Legacy files are read-through imported as compatibility inputs when `state.yml` lacks consolidated sections and ignored when consolidated sections are present.
- **Advisory lock**: `.quickscale/<name>.lock` — Exclusive-create file-based advisory lock used to serialize concurrent operations that mutate `state.yml`. Fail-fast contention; stale-lock inspection and manual-clear guidance only.
- **Recovery state**: `.quickscale/apply-recovery.yml` — Separate recovery-only state for the saga-model apply recovery ledger, shipped as a 16-step checkpointed ledger with atomic writes and resume gating (`quickscale_core/apply/executor.py`, `ledger.py`).
- **User manual**: See [user_manual.md §4.3](./user_manual.md#43-planapply-commands-shipped-in-v0680) for workflow examples and CLI usage.
- **Project structure**: See [scaffolding.md §5](./scaffolding.md#generated-project-output) for complete project layout including state files.

---

### Module Configuration Strategy {#module-configuration-strategy}

**Architectural Decision:** Modules require configuration when embedded. QuickScale uses a **plan/apply workflow with declarative YAML configuration**:

#### **Configuration via Plan/Apply**

**How**:
- `quickscale plan myapp --add auth` → adds auth module to configuration
- `quickscale plan` selects modules and writes `quickscale.yml`
- Module-specific options are configured in `quickscale.yml` before `quickscale apply`
- `quickscale apply` → embeds modules and applies configuration automatically
- User does NOT manually edit settings.py, urls.py, or INSTALLED_APPS
- Configuration is tracked in `.quickscale/state.yml`

**Example**:
```bash
$ quickscale plan myapp
? Select theme (showcase_react): showcase_react
? Select modules: auth,storage

✅ Configuration saved to quickscale.yml

$ quickscale plan myapp --configure-modules
# optionally capture module-specific values such as modules.storage.public_base_url

$ quickscale apply
✅ Modules embedded successfully!
Automatic changes made:
  ✅ Added selected modules to INSTALLED_APPS
  ✅ Added module-specific settings wiring
  ✅ Added module URLs where needed
  ✅ Ran initial migrations where applicable
```

**Benefits**:
- ✅ Declarative configuration (version-controllable quickscale.yml)
- ✅ Reproducible project generation
- ✅ No manual settings.py / urls.py editing required
- ✅ Terraform-style workflow (plan → review → apply)

**Implementation Requirements**:
1. `quickscale plan` selects modules and writes `quickscale.yml`
2. Apply handler automatically updates:
   - INSTALLED_APPS in settings.py
   - Module-specific settings (e.g., ACCOUNT_ALLOW_REGISTRATION)
   - urls.py (include module URLs)
   - Runs initial migration (`python manage.py migrate`)
3. Configuration state stored in `.quickscale/state.yml` for tracking/updates

**Current workflow**:
- ✅ Use `quickscale plan` to select modules and generate `quickscale.yml`
- ✅ Use `quickscale plan --configure-modules` when you want supported module
  options captured interactively during planning
- ✅ Edit module-specific values directly in `quickscale.yml` as needed
- ✅ Use `quickscale apply` to materialize the configuration

---

#### **Current YAML Workflow**

**Current workflow**:
```yaml
# quickscale.yml
version: "1"
project:
  slug: myproject
  package: myproject
  theme: showcase_react
modules:
  auth: {}
  storage:
    backend: s3
    public_base_url: https://cdn.example.com
docker:
  start: true
  build: true

# Usage: quickscale plan myproject --configure-modules → optionally captures
#        module values interactively for supported modules
#        edit quickscale.yml module values as needed
#        quickscale apply → executes configuration
```

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

**Backups contract rule:** `modules.backups` artifacts are
private operational files. They MUST NOT use `public_base_url`, public media
URLs, or template-visible asset helpers. For generated QuickScale PostgreSQL
projects, the supported local Docker and Railway backup/restore contract
targets PostgreSQL 18 server/client tooling and native PostgreSQL custom dumps
as the real disaster-recovery path. JSON artifacts are export-only: they
remain acceptable for non-PostgreSQL development/test fixture export and
operator inspection, but they are NOT a supported restore surface for
generated PostgreSQL projects. Admin create/delete/history flows remain
available, admin download and validate stay local-file-only in v1, and the
BackupPolicy admin page exposes a guarded restore surface only for row-backed
local artifacts already present on disk; there is no standalone admin
upload/offload action and no admin materialization path for remote-only
artifacts. Scheduled execution remains command-driven only
(`manage.py backups_create --scheduled` or equivalent platform cron job).
Destructive restore execution remains guarded across both supported surfaces:
BackupPolicy-admin restore requires exact filename confirmation plus the
existing environment gate and never materializes remote-only artifacts, while
CLI restore remains available with its existing syntax under the same
guardrails. Private-remote credentials MUST be referenced by
environment-variable name only; raw credential values MUST NOT be persisted in
`quickscale.yml`, `.quickscale/state.yml`, or `BackupArtifact` rows. When
`modules.backups.local_directory` is repo-relative, `quickscale apply` MUST add
that directory to `.gitignore` without hiding `.quickscale/state.yml`.
`quickscale apply` MAY update managed backend/runtime wiring, but it does NOT
rewrite user-owned Docker, Compose, CI, or E2E workflow files in already-
generated projects; when the PostgreSQL 18 backups contract requires new image
packages or runner tooling, existing generated projects MUST adopt those
changes manually, while fresh generations pick them up from the updated
templates. This section defines the authoritative contract for the implemented
follow-up, and the current runtime enforcement, generated templates, and
workflow coverage are aligned to it.

**Decision Rule**:
- Plan/apply is the primary workflow
- `quickscale plan` selects modules and creates `quickscale.yml`
- Module-specific values are configured in `quickscale.yml` before apply

**Authoritative Reference**: [§Plan/Apply Architecture](#planapply-architecture) above (this document)

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

**Architectural Decision (Phase 4, Finding 1):** A companion derivation schema describes how `module.yml` configuration options normalise, validate, and project into Django settings, making the manifest authoritative for behaviour that was historically duplicated across CLI contract files, the now-deleted `module_wiring_specs.py`, and imperative `normalize_*` / `validate_*` helpers.

**Companion, not extension:** `ModuleDerivationSchema` and its six dataclasses (`NormalizationRule`, `ValidationRule`, `LegacyKeyAlias`, `DerivedSetting`, `OptionDerivation`, `ModuleDerivationSchema`) live in `quickscale_core/src/quickscale_core/manifest/derivation.py`. They are exported from `quickscale_core.manifest` alongside the existing `ModuleManifest` and `ConfigOption` types. They do **not** extend, subclass, or alter `ModuleManifest` or `ConfigOption`. The existing manifest loader, runtime behaviour, and CLI contract-file path are unchanged.

**YAML-friendly shapes:** All dataclass fields use simple scalars (`str`, `int`, `float`, `bool`, `None`), lists, and dicts so `module.yml` `derivation:` sections round-trip through `yaml.safe_load` (via `load_manifest`/`build_schema_from_manifest`) without custom codecs.

**Dataclass summary:**

| Type | Purpose |
|------|---------|
| `NormalizationRule` | Declarative normalisation transformation (choice-map, lowercase, strip, coerce) |
| `ValidationRule` | Declarative validation constraint (choices, range, required, pattern, type) |
| `LegacyKeyAlias` | Mapping from deprecated configuration keys to current replacements |
| `DerivedSetting` | Django setting projected from one or more configuration options |
| `OptionDerivation` | Per-option bundle of normalisation, validation, alias, and derivation rules |
| `ModuleDerivationSchema` | Top-level container keyed by module name with per-option derivations and shared rules |

**Why this exists:** This foundation replaces the imperative `normalize_*` / `validate_*` functions and CLI contract files that historically duplicated per-module knowledge across hand-written contract files. Migrated modules use declarative derivation exclusively; an imperative-freeze guardrail prevents unmigrated modules from growing further imperative logic. See [roadmap.md Track 2](roadmap.md#track-2--module-contracts--settings) for per-module migration status.

**Constraints:**
- ✅ Derivation types are frozen dataclasses (immutable after construction)
- ✅ All field types are YAML-safe (scalars, lists, dicts)
- ✅ `ModuleDerivationSchema` is a companion to `ModuleManifest`, not a replacement
- ✅ YAML loading from `module.yml` shipped (SA6.1)
- ✅ Runtime derivation execution shipped for analytics and listings (SA6.2); other modules remain imperative pending migration
- ❌ No contract-file deletion yet for unmigrated modules (deferred to per-module migration phases)

---

### Module Implementation Checklist {#module-implementation-checklist}

**Architectural Decision:** Every QuickScale module must be complete, embeddable, and usable immediately after `quickscale apply`. This checklist ensures no gaps between planning and implementation.

#### **Required Components (All Modules)**

**Service-style exception (integration-only modules):**
- [ ] If a module's approved contract is settings plus helper/service APIs only, it may omit `models.py`, `views.py`, `urls.py`, `admin.py`, and migrations
- [ ] This exception must be called out explicitly in `decisions.md` or the active roadmap milestone before implementation starts
- [ ] Service-style modules still require package metadata, documented public APIs, lifecycle wiring when needed, and tests for the shipped contract

<a id="package-structure-and-naming-conventions"></a>
**1. Package Structure:**
- [ ] `quickscale_modules/<name>/pyproject.toml` — Package config (see template below)
- [ ] `quickscale_modules/<name>/README.md` — Installation, configuration, and usage guide
- [ ] `quickscale_modules/<name>/src/quickscale_modules_<name>/` — Source code (src/ layout)
- [ ] `quickscale_modules/<name>/tests/` — Test suite (outside src/)
- [ ] `quickscale_modules/<name>/tests/__init__.py` — Tests package init
- [ ] `quickscale_modules/<name>/tests/settings.py` — Django test settings
- [ ] `quickscale_modules/<name>/tests/conftest.py` — pytest fixtures

**1.1. Module pyproject.toml Template:**
```toml
[project]
name = "quickscale-module-<name>"
version = "0.XX.0"
description = "QuickScale <name> module - brief description"
requires-python = ">=3.13,<3.15"
authors = [{name = "Experto AI", email = "victor@experto.ai"}]
license = "Apache-2.0"
readme = "README.md"
dynamic = ["dependencies"]

[tool.poetry]
packages = [{include = "quickscale_modules_<name>", from = "src"}]

[tool.poetry.dependencies]
python = ">=3.13,<3.15"
Django = ">=6.0.3,<7.0.0"
# Add module-specific runtime dependencies here (e.g., django-allauth, Pillow)

[tool.poetry.group.dev.dependencies]
# Minimal dev dependencies - shared tools come from root pyproject.toml
pytest-django = "^4.7.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "tests.settings"
pythonpath = ["."]
python_files = ["test_*.py"]
testpaths = ["tests"]
addopts = "-v --cov=src/quickscale_modules_<name> --cov-report=html --cov-report=term-missing --cov-fail-under=70"
```

**1.2. Register Module in Root pyproject.toml:**
Add the module to root `pyproject.toml` for centralized testing:
```toml
[tool.poetry.dependencies]
quickscale-module-<name> = {path = "./quickscale_modules/<name>", develop = true}
```

**1.3. Register Module in Root mypy.ini:**
Add mypy overrides for the module (Django models need relaxed type checking):
```ini
[mypy-quickscale_modules_<name>.*]
disallow_untyped_defs = False
warn_return_any = False
warn_unused_ignores = False
disable_error_code = var-annotated
```

**2. Source Code (src/quickscale_modules_<name>/):**
- [ ] `__init__.py` — Module version (e.g., `__version__ = "0.67.0"`)
- [ ] `apps.py` — Django AppConfig with proper `name` and `label`
- [ ] `models.py` — **Concrete model(s)** for immediate use (required for domain modules; not required for explicitly approved service-style/integration-only modules)
- [ ] `views.py` — Views with `model` attribute set (required when the module ships routed views)
- [ ] `urls.py` — URL patterns with `app_name` for namespacing (required when the module ships routed views)
- [ ] `admin.py` — Admin registration for concrete models or operational surfaces (required only when the module ships an admin surface)
- [ ] `migrations/0001_initial.py` — **Initial migration for concrete models** (not required for explicitly approved service-style/integration-only modules)
- [ ] `migrations/__init__.py` — Migrations package init (only when migrations exist)

**3. Templates (if applicable):**
- [ ] `templates/quickscale_modules_<name>/` — Zero-style semantic HTML templates
- [ ] Templates must work immediately after embed (no user customization required)

**4. CLI Integration (quickscale_cli):**
- [ ] `AVAILABLE_MODULES` in `module_commands.py` is discovery-derived (`get_discovered_module_names()`) — no manual list edit needed; just ensure the module is discoverable (correct manifest/package layout)
- [ ] Create `configure_<name>_module()` function for interactive prompts
- [ ] Create `apply_<name>_configuration()` function to:
  - [ ] Add dependencies to project's `pyproject.toml`
  - [ ] Add module to `INSTALLED_APPS` in settings.py
  - [ ] Add module-specific settings
  - [ ] Add module URLs to project's `urls.py`
- [ ] Add module to `MODULE_CONFIGURATORS` dictionary
- [ ] Update embed command docstring with module description
- [ ] Add module-specific "Next steps" instructions in embed output

**5. Template Integration (showcase_html theme):**
- [ ] Add module section to `navigation.html.j2` (installed/not-installed states)
- [ ] Add module to "Installed Modules" section in `index.html.j2`
- [ ] Update "no modules installed" condition to include new module

**6. Testing:**
- [ ] Unit tests for the shipped module contract (models/views/admin for domain modules; services and lifecycle helpers for service-style modules)
- [ ] 90% overall mean + 80% per file minimum coverage (CI enforced)
- [ ] Tests use concrete models (not abstract stubs)
- [ ] `tests/settings.py` uses `django.db.backends.postgresql` only — SQLite in test settings is prohibited per Database Policy

**7. Split Branch Publishing:**
- [ ] Run `./scripts/publish_module.sh <name>` after implementation
- [ ] Verify split branch exists: `splits/<name>-module`

#### **Rationale**

**Why service-style modules can skip models/admin/migrations when explicitly approved:**
- Some modules exist to wrap an external provider or shared runtime behavior rather than own domain data
- Forcing placeholder models, admin classes, or migrations creates fake extension seams and misleading maintenance work
- The exception must stay explicit so modules do not silently narrow their supported contract

**Why concrete models are required (not just abstract):**
- Modules must work immediately after `quickscale apply`
- Users should not need to create their own models to use the module
- Abstract-only modules require user implementation, causing "missing QuerySet" errors
- Concrete models can still be extended by users who need customization

**Why initial migrations are required:**
- `poetry run python manage.py migrate` must succeed after embedding
- Migrations for concrete models are module responsibility, not user's
- Abstract models cannot be migrated; concrete models can and must be

**Why CLI integration is required:**
- `quickscale plan --add <name>` + `quickscale apply` is the primary distribution mechanism
- Interactive configuration provides immediate, working setup
- Users should not manually edit settings.py, urls.py, or pyproject.toml

**Why template integration is required:**
- Generated projects show module status in navigation and homepage
- Users can immediately see what's installed and access module features
- Reduces confusion about which modules are available

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
- ✅ pyproject.toml + poetry.lock (required)
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

#### Blog Module - Custom Django Implementation

**Architectural Decision:** Build custom Django blog instead of using existing solutions.

**Rationale**:
- ❌ **Wagtail**: Too heavy (full CMS with 50+ dependencies), contradicts QuickScale's lightweight philosophy
- ❌ **django-blog-zinnia**: Unmaintained (last release 2016), incompatible with Django 4.x+
- ❌ **Puput**: Wagtail-based (inherits Wagtail's complexity), overkill for simple blogging
- ✅ **Custom Django**: Lightweight, Django-native, exactly the features needed, no CMS overhead

**Technical Stack**:
- Django models (Post, Category, Tag, AuthorProfile)
- django-markdownx for WYSIWYG Markdown editing
- Pillow for image processing and thumbnails
- Django syndication framework for RSS feeds

**Features Included**:
- Markdown content editing with live preview
- Categories and tags for organization
- Featured images with automatic thumbnail generation
- RSS feed for content syndication
- Responsive templates for showcase_html theme

**Features Deferred**:
- Comments (use third-party like Disqus/Commento)
- Advanced SEO (Open Graph, JSON-LD schema)
- Related posts algorithm
- Scheduled publishing (use django-celery-beat if needed)

**Distribution**: Split branch pattern (`splits/simple-blog`), added via `quickscale plan` and `quickscale apply`

**Theme Support**: showcase_html, showcase_react

---

#### Disaster Recovery Engine Boundary Contract (F5 / M10)

**Why:** The embeddable `backups` module must not carry platform-level
backup/restore orchestration or talk to the CLI through a hidden
management-command + environment-variable protocol. That orchestration
belongs in centrally owned code, leaving only thin Django-facing surfaces in
the embeddable module, reached through an explicit typed adapter rather than
implicit env-var/stdout-JSON coupling.

**Current state:**
- **Centrally owned DR engine (`quickscale_core.dr_engine`):**
  - `primitives` — snapshot creation, archive packaging, database custom-dump
    capture.
  - `recovery` — restore validation, ordered execution sequencing,
    destructive-operation gating, orchestration flow.
  - `verification` — verification-record assembly, rollback-pin lifecycle and
    pin-field logic.
  - `adapter` — explicit typed adapter boundary (`capture_snapshot`,
    `fetch_snapshot_report`, `record_verification`,
    `set_rollback_pin`, `build_database_plan`, `execute_database_restore`,
    `sync_media`) that the CLI calls through a single bridge management
    command.
- **Embeddable `backups` module (`quickscale_modules_backups.services`):**
  retains Django-backed orchestration surfaces including snapshot capture,
  archive upload, sidecar capture, media-sync orchestration, and report-assembly
  logic that reference the `quickscale_modules` Django app environment — the
  higher-level platform orchestration that depends on Django project context.
  ``sync_backup_snapshot_media`` takes an explicit ``target_runtime_settings``
  parameter, with an env-var fallback preserved for admin/manual use through
  the management commands below.
- **CLI protocol:** The CLI
  (`quickscale_cli/src/quickscale_cli/commands/dr_commands.py`) drives DR
  through the explicit typed adapter (`quickscale_core.dr_engine.adapter`), called
  via the single ``dr_adapter_call`` management command bridge (subprocess +
  JSON stdout). The route kind marker is carried explicitly via the
  ``target_runtime_settings`` dict — there is no env-var protocol in CLI
  orchestration. Remaining management commands (``backups_create``,
  ``backups_report``, etc.) are thin Django/admin-facing surfaces for manual
  use, with env-var fallback in the service layer
  (``_load_target_runtime_settings``). Railway-target media sync fail-closed
  guard is preserved through the explicit ``ROUTE_KIND`` marker in the adapter
  path.

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
- **CHANGELOG.md**: Canonical all-version release history index
- **docs/releases/**: Single public release notes, whether they are clearly labeled prepared artifacts awaiting publish or notes already linked from GitHub tags and release PRs
- **docs/technical/release_summary_template.md**: Template for public release notes and release-prepared artifacts
- **roadmap.md**: Timeline, phases, tasks, and active or unreleased release closeout status
- **README.md**: Project overview, user guide, repo-level navigation
- **package README.md files**: Package-local installation and responsibility summaries (informational only)
- **commercial.md**: Commercial distribution background and constraints

**Rule:** Update the narrow owner first when changing its slice. Update decisions.md in the same change when the repository-wide ownership map, policy, or tie-breakers change.

## Unit/Integration Gate Split (SA59.4)

**Decision (SA59.4, ratified 2026-07-12):** The test suite is split into two independent gates — a DB-free unit gate and a PostgreSQL 18 integration gate. This split ensures fast, environment-independent feedback for core/CLI unit tests while module integration tests run against a restricted `NOBYPASSRLS` role for tenant-isolation coverage.

**Gate responsibilities:**

| Gate | Make target | Scope | Database | Role |
|------|-------------|-------|----------|------|
| Unit | `make test-unit` | `quickscale_core/tests`, `quickscale_cli/tests` (DB-free, marked `not integration and not e2e`) | None | N/A |
| Integration | `make test-integration` | `quickscale_modules/*/tests` (PostgreSQL-required, marked `not e2e`) | PostgreSQL 18 per-module test DB | `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` |

**Key properties:**

- The unit gate (`make test-unit`) is DB-free and runs core + CLI tests only. It requires no PostgreSQL and no special database role. The blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export is removed from the unit-only path.
- The integration gate (`make test-integration`) runs module suites against a `NOBYPASSRLS` role in both `ci.yml` and `publish.yml`. The SA58 boot guard (RLS role check) stays active. Developers set the SA14.4 hatch (`QUICKSCALE_ALLOW_BYPASSRLS=1`) explicitly per-suite when BYPASSRLS-dependent tests need to run.
- Non-quarantined module-suite regressions fail the gate. Known restricted-role failures are tracked individually (SA77 for orgs, SA79 for notifications) with a ticketed quarantine mechanism (SA76) that excludes quarantined entries from the exit code and coverage mean.
- `make test` runs both gates sequentially as a combined check.

**Related docs:** [validation_policy.md](./validation_policy.md) | [roadmap.md §Track 1](./roadmap.md)

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

### Launcher One-Shot Command-Env Contract (SA68) {#launcher-one-shot-command-env-contract-sa68}

**Decision (SA68):** Generated project startup scripts
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
- ❌ Signature-verified webhooks (Stripe, etc.) are a different trust class and are exempt from this rule — they use `csrf_exempt` because the calling party cannot present a CSRF token; verified instead by the SA46 pairing gate (`scripts/check_csrf_exempt_gate.py`).

**Narrow documented exception — blog dual-auth function views:** The blog module ships two function views (`upload_media_api` and `publish_post_api` in `quickscale_modules_blog.views`) that use `@_typed_csrf_exempt` (a type-preserving wrapper around `csrf_exempt`) paired with `authenticate_blog_api_request()` for session-or-Bearer-token authentication. This path is not a class-based view and does not subclass either sanctioned base; it is a deliberately narrow exception justified by the function-view architecture and the dual auth model (session + token). The SA46 CI gate (`scripts/check_csrf_exempt_gate.py`) explicitly recognizes `authenticate_blog_api_request` as an approved verification helper, so this exception is enforced rather than silent. No new function-view endpoints may use this exception without explicit approval.

The SA46 CI gate continues to enforce the pairing requirement across all `csrf_exempt` callsites.

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
- ✅ Shared database + shared schema; isolation enforced by PostgreSQL FORCE RLS on the 21 ENROLLED models (CRM 7, Forms 4, Billing 3, Blog 4, Listings 1, Social 2) plus ContextVar-driven `TenantManager` scoping — the authoritative registry overview is derived from model markers (SA15.3)
- ✅ Billing unit: `Subscription → Organization` (not per-user)
- ✅ URL routing: flat routes only — `/crm/`, `/blog/`; no `/orgs/<slug>/` content routes
- ✅ Users may belong to multiple organizations; org-switcher in the React UI
- ✅ Module access is differentiated by credits plus ORM-backed `Plan.features` gates

**RLS enforcement rule (critical, updated by SA2.1 + SA2.2 + CR-SA68-001):**
- RLS enforces only when the app connects as the restricted `NOSUPERUSER/NOBYPASSRLS` runtime role selected by `RUNTIME_DATABASE_URL`
- Generated runtime serving now fails closed when `RUNTIME_DATABASE_URL` is unset; only the named privileged command paths intentionally use the superuser `DATABASE_URL`
- **Always-on boot guard (SA2.1, CR-SA68-001):** `orgs.QuickscaleOrgsConfig.ready()` asserts `rolbypassrls=false AND rolsuper=false` on every boot where `QUICKSCALE_PRIVILEGED_COMMAND` is unset or set to an unrecognised value — regardless of `QUICKSCALE_MODE` or `DEBUG`. Raises `ImproperlyConfigured` if the connected role has BYPASSRLS and/or SUPERUSER unless one of the two explicit exemptions applies:
  1. `QUICKSCALE_PRIVILEGED_COMMAND` set to a sanctioned privileged DB command (`migrate`, `createcachetable`) — the deployment `start.sh` unsets `RUNTIME_DATABASE_URL` so these operations run under the superuser role (correct and deliberate). The sanctioned command set is defined by `_PRIVILEGED_COMMANDS` in `apps.py`; every new sanctioned command is added there.
  2. `QUICKSCALE_ALLOW_BYPASSRLS=1` — environment-variable escape hatch for intentional single-tenant or development use.
- `start.sh` deliberately unsets `RUNTIME_DATABASE_URL` for `migrate` and `createcachetable`; `runserver`/`gunicorn` must still use the restricted runtime role

**Isolation architecture rules (permanent):**
- Registry authority: the marker-based derived registry overview (:func:`get_derived_registry_overview`) is the authoritative human-readable view of the shipped tenant-table surface. The derived view is purely marker-driven (``tenant_excluded`` attributes, ``TenantManager``/``TenantModel`` detection, and implicit M2M through inference) with no fallback to the literal ``TENANT_TABLE_REGISTRY`` (SA15.3 follow-up). The literal ``TENANT_TABLE_REGISTRY`` remains in place as a cross-check target so CI can confirm the two views stay in agreement. Its 21 ENROLLED models (CRM 7, Forms 4, Billing 3, Blog 4, Listings 1, Social 2) each carry a direct ``organization_id``, ``objects = TenantManager()``, ``all_objects = TenantManager(super_scope=True)``, and a live FORCE-RLS policy.
- Child tables: every tenant-owned child/detail table must denormalize `organization_id` directly onto the row and use a direct FORCE-RLS policy referencing that column; parent-join RLS policies are not used. This is the project default for all future tables.
- Ambient scoping: request-scoped tenant reads flow through `request.org` → ContextVar (`app.current_org_id`) → `TenantManager`; the authoritative tenant-facing API is ambient manager scoping, not `.for_org(...)` query chaining.
- Operator access: management commands and operator paths use `operator_access(reason=...)` for audited elevated access. When a command or admin path truly needs an unfiltered queryset, it may read from model `all_objects` explicitly under that contract.
- Org ownership: System org owns all published-public content (blog feed, public listings, social links). Anonymous visitors see System-org rows; solo authenticated = personal org; saas authenticated = active org.
- Teardown policy: `on_delete=PROTECT` on all tenant-owned FKs + explicit `purge_organization` management command for ordered, FK-safe delete — GDPR-capable, no accidental cascade.
- **Composite-FK deferability policy (SA60, ratified 2026-07-12):** every Option C composite FK (the child-table `organization_id` + local-key pair added by the `_ADD_COMPOSITE_FK_SQL` helper in `orgs/tenancy.py`) is `NOT DEFERRABLE`. Empirically verified on PostgreSQL 18: `SET CONSTRAINTS <name> IMMEDIATE` on a `NOT DEFERRABLE` FK is a no-op, so the constraint is already effectively immediate — `NOT DEFERRABLE` is the fail-fast choice consistent with the [fail-hard principle](#fail-hard-principle) and requires no `SET CONSTRAINTS ALL DEFERRED` carve-out for fixture/loaddata restores. `forms/migrations/0007_new_organization_ownership.py`'s inlined `DEFERRABLE INITIALLY DEFERRED` SQL was the lone outlier and has been migrated to `NOT DEFERRABLE` (SA60). The forms and CRM migration tests were updated to match the `NOT DEFERRABLE` contract; the `SET CONSTRAINTS ... IMMEDIATE` calls in those tests are retained as harmless no-ops. A conformance test (SA60) validates that every Option C composite FK is `NOT DEFERRABLE`.
- **`tenant_excluded` marker precedence (SA60, ratified 2026-07-12):** in `is_tenant_model()` (`orgs/tenancy.py:1548+`), an explicit `tenant_excluded = "reason"` marker on a model takes precedence over manager/base-class detection (`TenantManager`/`TenantModel` inheritance) — a model marked excluded is never classified as tenant-scoped even if it also inherits tenant machinery. This is a doc-only ratification of already-shipped behavior; no code change.
- **Intentional CASCADE exception (SA35):** `OrganizationInvitation.invited_by` remains `on_delete=CASCADE` because a pending invitation is an action attributed to its sender—if the sender's account is deleted, the invitation has no meaningful sender identity and dissolving it along with the sender is the correct behavior. This is a narrow, documented exception to the general SET_NULL/PROTECT rule for user-FKs in tenant-scoped models. Every other user-FK in `quickscale_modules_*` is SET_NULL or PROTECT (enforced by a conformance test in the orgs cross-module test harness at ``orgs/tests/test_sa35_conformance.py``).
- **Last-owner `pre_delete` backstop refusal mechanism (SA70, ratified 2026-07-12):** the new orgs `pre_delete` receiver on the `User` model raises (does not silently return/no-op) when the deletion would orphan a shared organization's last owner, matching the [fail-hard principle](#fail-hard-principle) that governs the rest of this cycle's hardening work — a caller (admin bulk-delete, management command, a future GDPR erasure path) must see a loud failure rather than believe a refused delete succeeded.

**Rejected alternatives (do not re-introduce):**
- ❌ **Per-client Railway deployment** — linear operational overhead per tenant; not a SaaS platform
- ❌ **App-layer-only filtering without RLS** — no defence-in-depth; a single missed filter leaks cross-tenant data
- ❌ **PostgreSQL schema-per-tenant isolation** — schema metadata bloat, migration complexity with many tenants
- ❌ **Supabase as the database provider** — valid for teams that want managed infrastructure, but introduces vendor lock-in and changes the cost/operational model; our self-hosted Railway approach uses the same GUC-carried tenant-context pattern without changing the current contract

**Supabase architecture parity note:**
QuickScale's shared-schema + FORCE RLS model is structurally equivalent to Supabase's multi-tenant architecture. Both use a PostgreSQL GUC parameter as the per-transaction tenant context carrier and `FORCE ROW LEVEL SECURITY` for tenant data isolation. The key difference is injection mechanism: Supabase's PostgREST sets the GUC from JWT claims before every query; QuickScale's AF9 execute-wrapper derives the GUC from the ContextVar at transaction start. Supabase also ships a dashboard "Impersonate User" button — QuickScale now ships VIEW-AS for the same restricted-role debugging need. In QuickScale's shipped surface, runtime admin/debug access stays on the restricted role; BYPASSRLS is reserved for the migration exception and any future explicitly documented non-runtime privileged path.

**Operator debug mode — shipped VIEW-AS contract:**
Django superusers may activate a debug session that scopes the entire request to a selected organization so they can see the app exactly as that org's members see it. The shipped surface uses the session key `quickscale_modules_orgs.debug_as_org_id` (superuser-only); `TenantMiddleware._resolve_debug_org()` overrides Solo/SaaS resolution when the key is present; the admin surface activates or exits the session; a debug banner renders while active; and every activation is audit-logged. No BYPASSRLS — the debug session runs under the same restricted runtime role as all other tenant paths, so RLS remains fully enforced.

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

**Decision (SA66):** The beta-migration maintainer tooling
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
   ``start.sh`` is managed the same way so the SA63 createcachetable env-pair
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

5. **``INTENTIONALLY_UNMANAGED`` entries are organized by category with explicit rationale.** Each category below documents why those generated files are deliberately outside all migration paths. Add new entries to the appropriate category; add a new category only when the existing ones do not fit, with rationale.

   **Category U1 — Project-level user-owned files (root-level generated config/docs):**
    ``Makefile``, ``README.md``, ``.gitignore``, ``.dockerignore``, ``.editorconfig``,
    ``.env.example``, ``.env``, ``scripts/lint.sh``, ``.github/workflows/ci.yml``,
    ``poetry.lock``, ``db/init.sql``, ``OPERATIONS.md``.
    Rationale: One-time scaffold that the user tailors to their deployment,
    CI, and documentation needs.  ``poetry.lock`` is a dynamically generated
    artifact created by ``_generate_poetry_lock()`` after all templates are
    rendered; it is regenerated by the verification stack (``poetry lock``)
    and is not a migration target.  Not migration targets.

   **Category U2 — Package ``__init__`` markers:**
   ``{package}/__init__.py``, ``{package}/settings/__init__.py``.
   Rationale: These are identity-dependent only through the package name,
   which the fresh-first path resolves by renaming the entire package
   directory.  A separate taxonomy entry would duplicate the package-
   rename logic.

   **Category U3 — Django HTML templates:**
   ``templates/404.html``, ``templates/500.html``, ``templates/base.html``,
   ``templates/index.html``, ``templates/admin/index.html``,
   ``templates/admin/app_index.html``, ``templates/components/navigation.html``,
   ``templates/social/link_tree.html``, ``templates/social/embeds.html``.
   Rationale: User-editable Django templates.  Unlike infrastructure files
   (``Dockerfile``, ``start.sh``), they are not copy targets during migration.
   Fresh-first preserves the recipient's templates; in-place does not touch
   them.  Theme-specific template overrides (social, components) are
   user-owned once generated.

   **Category U4 — Static assets:**
   ``static/css/style.css``, ``static/images/favicon.svg``.
   Rationale: User-owned static files.  Generated once; not migration targets.

   **Category U5 — Test scaffolding:**
   ``tests/__init__.py``, ``tests/conftest.py``, ``tests/test_example.py``.
   Rationale: One-time generated test scaffold that users customize.

   **Category U6 — Frontend root configs (user-owned after generation):**
   ``frontend/package.json``, ``frontend/pnpm-workspace.yaml``,
   ``frontend/.prettierignore``, ``frontend/.prettierrc``,
   ``frontend/vitest.config.ts``, ``frontend/playwright.config.ts``,
   ``frontend/components.json``, ``frontend/tailwind.config.js``,
   ``frontend/index.html``, ``frontend/public/favicon.svg``.
   Rationale: Unlike infrastructure frontend configs (``vite.config.ts``,
   ``tsconfig.json``, ``eslint.config.js``, ``postcss.config.js``,
   ``prettier.config.js``) which are in ``IN_PLACE_INFRASTRUCTURE_TARGETS``,
   these files are either merged in-place with recipient identity
   preservation (``package.json``) or user-editable after generation.
   ``package.json`` is identity-preserved during in-place merge but does
   not need to be a managed copy target since the donor's version already
   carries the correct structural content.  ``tailwind.config.js``,
   ``components.json``, ``playwright.config.ts``, ``.prettierrc``, and
   ``index.html`` are user-owned after one-time generation.

   **Category U7 — Frontend user-owned source files:**
    ``frontend/src/main.tsx``, ``frontend/src/index.css``,
    ``frontend/src/vite-env.d.ts``, ``frontend/src/posthog-js.d.ts``,
    ``frontend/src/lib/utils.ts``, ``frontend/src/lib/analytics.ts``,
    ``frontend/src/stores/themeStore.ts``, ``frontend/src/test/setup.ts``,
    ``frontend/src/test/App.test.tsx``,
    ``frontend/src/test/PublicSocialPages.test.tsx``,
    ``frontend/e2e/home.spec.ts``.
    Rationale: User-editable application source, styles, type declarations,
    utility helpers, and test files.  Not migration targets.  Specific
    infrastructure-relevant files under ``frontend/src/`` (``useModules.ts``,
    ``vite.config.ts``, ``tsconfig*.json``, ``eslint.config.js``,
    ``postcss.config.js``, ``prettier.config.js``) are in the managed
    tuples.  ``frontend/src/App.tsx`` is classified by the fresh-first
    required recipient spec (``MODE_REQUIRED_SPECS``) — it is a required
    preflight check for the fresh-first path and is copied from donor to
    recipient during the copy-custom-router-and-pages step (see rule 7).
    Everything else stays with the user.

   **Category U8 — shadcn/ui components:**
   All ``frontend/src/components/ui/*.tsx`` files.
   Rationale: shadcn/ui components are copy-pasted user-owned code after
   generation.  They are not migration targets.

   **Category U9 — Layout components:**
   ``frontend/src/components/layout/Header.tsx``,
   ``frontend/src/components/layout/Layout.tsx``,
   ``frontend/src/components/layout/Sidebar.tsx``.
   Rationale: User-editable theme layout components.  Fresh-first copies
   the donor component directory (via copy-custom-components, skipping
   ``ui/``), but the taxonomy models these as user-owned because users
   customize them extensively.

   **Category U10 — Org/state components:**
   ``frontend/src/components/orgs/OrgStatePanel.tsx``,
   ``frontend/src/components/orgs/OrgSwitcher.tsx``.
   Rationale: Generated org-management components that users customise
   per-project.  Not migration targets.

   **Category U11 — Social wrapper component:**
   ``frontend/src/components/social/PublicSocialShell.tsx``.
   Rationale: Theme-owned React wrapper for social module public pages.
   The module-owned social surfaces (pages, hooks) are tracked separately
   in ``IN_PLACE_MODULE_REACT_SURFACES``.  This shell is user-editable.

   **Category U12 — Non-module pages:**
   ``frontend/src/pages/Dashboard.tsx``, ``frontend/src/pages/NotFound.tsx``,
   ``frontend/src/pages/ProfilePage.tsx``, ``frontend/src/pages/SettingsPage.tsx``.
   Rationale: User-editable application pages, always emitted for the
   React theme.  Fresh-first copies donor-only pages via the hardcoded
   copy-custom-router-and-pages step, but individual pages are not
   migration-managed taxonomy entries.

   **Category U13 — Module-conditional pages (non-module-surface):**
   ``frontend/src/pages/BlogPage.tsx``, ``frontend/src/pages/CrmPage.tsx``,
   ``frontend/src/pages/ListingsPage.tsx``.
   Rationale: Emitted only when the gating module is selected at generation
   time.  After generation they are user-editable.  ``FormsPage.tsx``,
   ``SocialLinkTreePublicPage.tsx``, and ``SocialEmbedsPublicPage.tsx``
   are managed via ``IN_PLACE_MODULE_REACT_SURFACES`` (post-apply module
   surface adoption targets) and are **not** in this category — they are
   migration-managed, not intentionally unmanaged.

   **Category U14 — Org pages (React theme):**
   ``frontend/src/pages/orgs/OrgLayout.tsx``,
   ``frontend/src/pages/orgs/OrgDashboardPage.tsx``,
   ``frontend/src/pages/orgs/OrgMembersPage.tsx``,
   ``frontend/src/pages/orgs/OrgSettingsPage.tsx``,
   ``frontend/src/pages/orgs/OrgCreatePage.tsx``,
   ``frontend/src/pages/orgs/OrgListPage.tsx``.
   Rationale: Generated org-management pages that are user-editable after
   generation.  Not migration targets.

   **Category U15 — Non-infrastructure hooks:**
   ``frontend/src/hooks/useOrgNavigation.ts``,
   ``frontend/src/hooks/useOrgs.ts``,
   ``frontend/src/hooks/useApi.ts``,
   ``frontend/src/hooks/useFormSchema.ts``.
   Rationale: User-editable React hooks.  ``useModules.ts`` and
   ``usePublicSocialSurface.ts`` are in the managed tuples; the rest are
   user-owned after generation.

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

**Related docs:** [roadmap.md SA66](./roadmap.md) | [arch-audit.md Finding 7](../others/arch-audit.md)

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
the beta-migration file taxonomy and its conformance gate (SA66, ✅ landed),
and the launcher env-pair contract's correctness in the templates it emits
(SA63/SA68, ✅ landed). Those are the actual defect classes; this decision
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

**Related docs:** [roadmap.md](./roadmap.md) | [arch-audit.md Red flags](../others/arch-audit.md) | [beta-site-migration.md](../planning/beta-site-migration.md)

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

**Configuration:**
- ❌ Execute code in config files (pure data YAML only)
- ❌ Deep nesting in config syntax (keep flat and readable)

## Package Structure

**Namespace Packaging Notes (maintainer reference, not current generated-project contract):**
- ✅ `quickscale_modules/`, `quickscale_themes/`: PEP 420 namespaces (no `__init__.py` at root)
- ✅ `quickscale_core`: Regular package (has `__init__.py`)
- ✅ Use `find_namespace_packages()` in `pyproject.toml`

**See:** [scaffolding.md §6](./scaffolding.md#6-naming-import-matrix-summary) for complete matrix

**Namespace Packaging Checklist:**
1. ✅ Verify editable install works
2. ❌ Delete namespace `__init__.py` files
3. ✅ Update to `find_namespace_packages()`
4. ✅ Test multi-module install
5. ✅ Publish to PyPI

**CI Requirements:**
- ✅ Fail build if namespace `__init__.py` exists
- ✅ Validate PEP 420 compliance

## Technical Reference

**src/ Layout Example:**
```
quickscale_core/
  pyproject.toml
  src/quickscale_core/
    __init__.py
    apps.py
  tests/
```

**Namespace Example (PEP 420):**
```
quickscale_themes/ecommerce/src/quickscale_themes/ecommerce/...
# NO __init__.py at quickscale_themes/
```

**Compatibility Metadata:**
```toml
[project.metadata.quickscale]
core-compatibility = ">=2.0.0,<3.0.0"
```

**Module Boundaries:**

| Concern | Billing Module | Payments Module |
|---------|----------------|-----------------|
| Role | Subscriptions, entitlements | Charge execution, refunds |
| Models | Plan, Subscription | Transaction, WebhookEvent |
| Integration | Stripe Billing API | Stripe Payments API |
| Provides | Status checks, decorators | Payment execution services |
| NOT | Charge execution | Subscription logic |
