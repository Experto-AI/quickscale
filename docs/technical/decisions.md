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

**Current Contract:**
- ✅ `quickscale_core`: scaffolding and shared generator/runtime support
- ✅ `quickscale_cli`: plan/apply plus development, deployment, and module-management workflows
- ✅ Generated project: standalone Django application that the user owns completely
- ✅ Settings: standalone settings by default (no automatic inheritance from core)
- ✅ First-party modules and starter themes that are implemented in-repo and documented per release

**Historical note:** Older docs may still use legacy release-era shorthand from earlier planning. Treat those labels as historical context only; active documentation should describe the implemented surface directly.

**Current Generated Output:** See [scaffolding.md §3](./scaffolding.md#mvp-structure)

### Module & Theme Architecture {#module-theme-architecture}

**Architectural Decision (v0.61.0):** Modules and themes serve different purposes and use different distribution mechanisms.

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

Billing now has a public-ready implementation line in `quickscale_modules/billing` through the current runtime APIs, module-owned billing pages, and React integration guide. Public `quickscale plan`, `quickscale.yml`, and `quickscale apply` flows now surface billing. The generated `showcase_react` SPA surfaces billing as a module flag only (`modules.billing`); it does not include billing dashboard cards, sidebar navigation entries, org-dashboard billing cards/links, module paths for billing, or full-document links into billing Django pages. Teams remains placeholder inventory only.

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
  - Fresh v0.83.0 generations do not scaffold `/social` or `/social/embeds` public
    pages

Planned vertical themes such as CRM remain roadmap work. They are not part of the
current shipped generator surface until a release note and this file explicitly add
them.

Generated starter output surfaces billing as a module flag only (`modules.billing`).
The generated `showcase_react` SPA does not include billing dashboard cards, sidebar
navigation entries, org-dashboard billing cards/links, module paths for billing, or
full-document links into billing Django pages until a session-sync contract (D1 Option A)
explicitly syncs the server session's active org after client-side org switches.
QuickScale does not generate a starter-owned billing React page. Teams routes, flags, dashboard cards,
and navigation remain excluded until teams ships as a valid public `quickscale plan` /
`quickscale.yml` / `quickscale apply` selection.

**Default React Theme Tech Stack (v0.74.0):**

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

**Optional Utilities (for CRM v0.75.0):**
- **date-fns** — Date handling (tree-shakeable, shadcn uses it)
- **Recharts** — Charts (shadcn/charts uses it)
- **TanStack Table** — Data tables (shadcn uses it)

**Distribution Strategy:**
1. Store themes in `quickscale_core/generator/templates/themes/{theme_name}/`
2. User selects theme via `quickscale plan` → `quickscale apply` (v0.68.0+)
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
    │   ├── templates/         # No scaffolded public /social pages in v0.83.0+
    │   └── static/
```

Fresh generations copy `showcase_react/src/**` into the generated project's
`frontend/src/` directory and copy `showcase_react/templates/**` into Django
  `templates/`. Only fresh `showcase_react` generations auto-scaffold the Django-owned
  public `/social` and `/social/embeds` pages. `showcase_html` does not ship those
  public routes/templates in v0.83.0, and non-React themes must adopt any equivalent
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
  the generated SPA does not include billing dashboard cards, sidebar navigation entries,
  org-dashboard billing cards/links, module paths for billing, or full-document links into
  billing Django pages. Teams routes, navigation, flags, and dashboard cards remain excluded until teams ships
- ❌ Complete vertical themes are not part of the current shipped CLI surface yet
- ✅ Module releases may extend managed backend/runtime surfaces in existing projects, but newly scaffolded theme-owned routes, navigation, registries, and page source are only guaranteed on fresh generation or explicit manual adoption

**D1 — Generated showcase_react SSA org-switch billing parity (Option B locked):**
The generated `showcase_react` SPA performs org-switches client-side, but the server
session `ACTIVE_ORG_SESSION_KEY` is not explicitly synced before billing API calls
fire. This means billing pages can resolve the wrong org after a client-side switch.
QuickScale has locked **Option B** — remove generated SPA billing entry points
(dashboard cards, sidebar navigation, org-dashboard billing cards/links, and
`modulePaths.billing` from the React hook contract) until a session-sync contract
(Option A) is designed and implemented. The module flags (`modules.billing`) remain
in the generated config so the frontend can still detect whether billing is installed.
Option A (session-sync endpoint) is deferred; the D1 decision applies to the current
shipped surface in `showcase_react` templates and will be revisited when a session-sync
contract is ready.

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

**For detailed workflow documentation** (split branch mechanics, conflict resolution, troubleshooting), see [roadmap.md §v0.61.0](./roadmap.md#v0610-theme-system-foundation--split-branch-infrastructure)

---

### Plan/Apply Architecture {#planapply-architecture}

**Architectural Decision (v0.68.0+):** QuickScale uses **Terraform-style declarative configuration** with distinct desired state and applied state tracking.

#### **Core Decision**

Projects are managed through two configuration files with clear separation of concerns:

| File | Purpose | Role |
|------|---------|------|
| `quickscale.yml` | Declared desired configuration | Input (what user wants) |
| `.quickscale/state.yml` | Applied state after execution | Sole authoritative applied-state store (output — what was actually done) |
| `.quickscale/config.yml` | Legacy module metadata | Compatibility input only (read-through imported when `state.yml` lacks consolidated sections; ignored when consolidated sections are present) |

#### **Desired State Schema** (`quickscale.yml`)

User-editable configuration file with this structure:

```yaml
version: 0.86.0
project:
  slug: myapp
  package: myapp
  theme: showcase_react
modules:
  auth: {}
  listings: {}
  storage:
    backend: s3
    public_base_url: https://cdn.example.com
docker:
  build: true
  start: true
```

**Constraints**:
- ✅ Version-controllable (stored in git)
- ✅ `version` is the plan/apply schema version and is currently the string `"1"`
- ✅ User-editable and reviewable
- ✅ One file per project
- ✅ `project.slug` is the filesystem/service identity
- ✅ `project.package` is the Python import/package identity and MUST NOT be inferred from the project directory name
- ✅ Location: Project root

#### **Applied State Schema** (`.quickscale/state.yml`, v0.69.0+; consolidated sub-sections in Phase 2 / M2)

System-managed state file tracking what has been applied. `.quickscale/state.yml` is the sole authoritative applied-state store:

```yaml
version: 0.86.0
project:
  slug: myapp
  package: myapp
  theme: showcase_react
  created_at: 2025-12-03T14:30:00
  last_applied: 2025-12-03T14:32:00
modules:
  auth:
    version: 0.86.0
    commit_sha: abc123def456
    embedded_at: 2025-12-03T14:30:00
    options:
      registration_enabled: true
      email_verification: none
      authentication_method: email
    # Consolidated tracking fields (Phase 2 / M2):
    prefix: splits
    branch: splits/auth-module
    installed_at: 2025-12-03T14:30:00
  listings:
    version: 0.86.0
    commit_sha: xyz789uvw012
    embedded_at: 2025-12-03T14:31:00
    options: null
    prefix: splits
    branch: splits/listings-module
    installed_at: 2025-12-03T14:31:00
managed_files:
  - path: myapp/settings/base.py
    hash: sha256hex...
    applied_at: 2025-12-03T14:32:00
```

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

- **Module tracking**: `.quickscale/state.yml` (Phase 2 / M2) — The sole authoritative applied-state store. Per-module consolidated tracking fields (`prefix`, `branch`, `installed_at`) and the `managed_files` sub-section replace the legacy `config.yml` and `file_hashes.yml`. Legacy files are read-through imported as compatibility inputs when `state.yml` lacks consolidated sections and ignored when consolidated sections are present.
- **Advisory lock**: `.quickscale/<name>.lock` — Exclusive-create file-based advisory lock used to serialize concurrent operations that mutate `state.yml`. Fail-fast contention; stale-lock inspection and manual-clear guidance only.
- **Recovery state**: `.quickscale/apply-recovery.yml` — Separate recovery-only state for the saga-model apply recovery ledger (future Phase 12 work).
- **User manual**: See [user_manual.md §4.3](./user_manual.md#43-planapply-commands-shipped-in-v0680) for workflow examples and CLI usage.
- **Project structure**: See [scaffolding.md §5](./scaffolding.md#generated-project-output) for complete project layout including state files.

---

### Module Configuration Strategy {#module-configuration-strategy}

**Architectural Decision (v0.72.0):** Modules require configuration when embedded. QuickScale uses a **plan/apply workflow with declarative YAML configuration**:

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
# quickscale.yml (v0.68.0+)
version: 0.86.0
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

**Auth desired-config validation rule (v0.83.0):** `quickscale.yml` is
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

**Storage URL rule (v0.76.0):** `modules.storage.public_base_url` is the sole
public media URL setting for storage-backed assets. Helper-built blog/storage
URLs must use `public_base_url` when configured and fall back to `MEDIA_URL`
behavior in local development when it is blank. `custom_domain` is not part of
the supported storage contract.

**Backups contract rule (v0.77.0 follow-up):** `modules.backups` artifacts are
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
- **v0.72.0+**: Plan/apply is the primary workflow
- `quickscale plan` selects modules and creates `quickscale.yml`
- Module-specific values are configured in `quickscale.yml` before apply

**Authoritative Reference**: [roadmap.md §Plan/Apply Architecture](./roadmap.md#-planapply-architecture-v06800)

---

### Module Manifest Architecture {#module-manifest-architecture}

**Architectural Decision (v0.71.0):** Each module includes `module.yml` declaring configuration options as mutable or immutable.

**Manifest Schema:**
```yaml
name: auth
version: 0.86.0
config:
  mutable:
    registration_enabled:
      type: boolean
      default: true
      django_setting: ACCOUNT_ALLOW_REGISTRATION
  immutable:
    authentication_method:
      type: string
      default: email
```

**Configuration Rules:**

| Aspect | Mutable | Immutable |
|--------|---------|-----------|
| **Definition** | Runtime-changeable via `quickscale apply` | Embed-time-only, locked after |
| **Storage** | Django `settings.py` | `.quickscale/state.yml` |
| **Changes** | Auto-update settings.py on apply | Reject with error guidance |
| **Code** | Read from settings (no hardcoding) | Configured at embed time |
| **Example** | `ACCOUNT_ALLOW_REGISTRATION` | `authentication_method` |

**Apply Behavior** (extends v0.68.0-v0.70.0 Plan/Apply):
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

**YAML-friendly shapes:** All dataclass fields use simple scalars (`str`, `int`, `float`, `bool`, `None`), lists, and dicts so that future `module.yml` `derivation:` sections can round-trip through `yaml.safe_load` without custom codecs. YAML serialisation and loader wiring are intentionally deferred to a later roadmap item.

**Dataclass summary:**

| Type | Purpose |
|------|---------|
| `NormalizationRule` | Declarative normalisation transformation (choice-map, lowercase, strip, coerce) |
| `ValidationRule` | Declarative validation constraint (choices, range, required, pattern, type) |
| `LegacyKeyAlias` | Mapping from deprecated configuration keys to current replacements |
| `DerivedSetting` | Django setting projected from one or more configuration options |
| `OptionDerivation` | Per-option bundle of normalisation, validation, alias, and derivation rules |
| `ModuleDerivationSchema` | Top-level container keyed by module name with per-option derivations and shared rules |

**Roadmap context:** This foundation is the first step toward eventually replacing the imperative `normalize_*` / `validate_*` functions and CLI contract files that historically duplicated per-module knowledge (seven hand-written contract files, the now-deleted `module_wiring_specs.py`, and `module_config.py`). The analytics module is the planned first pilot slice. Later phases will add loader wiring, runtime derivation execution, and progressive contract-file deletion — one module at a time.

**Constraints:**
- ✅ Derivation types are frozen dataclasses (immutable after construction)
- ✅ All field types are YAML-safe (scalars, lists, dicts)
- ✅ `ModuleDerivationSchema` is a companion to `ModuleManifest`, not a replacement
- ✅ No current loader, runtime, or CLI behaviour changes
- ❌ No YAML loading from `module.yml` yet (deferred to next roadmap item)
- ❌ No runtime derivation execution yet (deferred to analytics pilot)
- ❌ No contract-file deletion yet (deferred to per-module migration phases)

---

### Module Implementation Checklist {#module-implementation-checklist}

**Architectural Decision (v0.67.0):** Every QuickScale module must be complete, embeddable, and usable immediately after `quickscale apply`. This checklist ensures no gaps between planning and implementation.

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
- [ ] Add module name to `AVAILABLE_MODULES` list in `module_commands.py`
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

#### Blog Module (v0.66.0) - Custom Django Implementation

**Architectural Decision (v0.66.0):** Build custom Django blog instead of using existing solutions.

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

**Features Included (v0.66.0)**:
- Markdown content editing with live preview
- Categories and tags for organization
- Featured images with automatic thumbnail generation
- RSS feed for content syndication
- Responsive templates for showcase_html theme

**Features Deferred (Post-v0.66.0)**:
- Comments (use third-party like Disqus/Commento)
- Advanced SEO (Open Graph, JSON-LD schema)
- Related posts algorithm
- Scheduled publishing (use django-celery-beat if needed)

**Distribution**: Split branch pattern (`splits/simple-blog`), added via `quickscale plan` and `quickscale apply`

**Theme Support**: showcase_html (v0.66.0), showcase_react (v0.71.0)

---

#### Disaster Recovery Engine Boundary Contract (F5 / M10)

**Status:** Target boundary for the M10 DR engine split, now shipped across
all four phases (F5.2a/F5.2b/F5.3/F5.4). See "Current state" below for the
post-F5.3 code layout. This entry originally defined the boundary only
(roadmap phase F5.1); the extraction phases F5.2a/F5.2b/F5.3 shipped the
core/module split and explicit adapter described here, and F5.4 added the
migration documentation at `docs/technical/dr_engine_migration.md`.

**Why (Finding 5):** The embeddable `backups` module originally carried
platform-level backup/restore orchestration and communicated with the CLI through
a hidden management-command + environment-variable protocol. The engine must move
into centrally owned code, leaving only thin Django-facing surfaces in the
embeddable module. F5.2a/F5.2b shipped the core extraction; F5.3 replaced the
hidden protocol with an explicit typed adapter. F5.4 ships the migration
documentation at `docs/technical/dr_engine_migration.md`.

**Current state (post-F5.3):**
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
    command, replacing the hidden env-var protocol.
- **Embeddable `backups` module (`quickscale_modules_backups.services`):**
  retains Django-backed orchestration surfaces including snapshot capture,
  archive upload, sidecar capture, media-sync orchestration, and report-assembly
  logic that still reference the `quickscale_modules` Django app environment.
  F5.2a/F5.2b shipped the Django-free primitives, recovery, and verification
  into `quickscale_core.dr_engine`, while the module retains the higher-level
  platform orchestration that depends on Django project context. F5.3 replaced
  the hidden protocol with the explicit adapter; the module also gained an
  explicit ``target_runtime_settings`` parameter on ``sync_backup_snapshot_media``
  (replacing the ``QUICKSCALE_DR_TARGET_*`` env-var protocol) while preserving
  the env-var fallback for admin/manual use through the preserved management
  commands.
- **CLI protocol (F5.3 shipped):** The CLI
  (`quickscale_cli/src/quickscale_cli/commands/dr_commands.py`) now drives DR
  through the explicit typed adapter (`quickscale_core.dr_engine.adapter`), called
  via the single ``dr_adapter_call`` management command bridge (subprocess +
  JSON stdout). All per-operation management commands have been replaced by
  adapter dispatch. The env-var protocol (`_TARGET_ENV_PREFIX`,
  `QUICKSCALE_DR_TARGET_*`, `ROUTE_KIND`) has been removed from CLI
  orchestration; the route kind marker is carried explicitly via the
  ``target_runtime_settings`` dict. Remaining management commands
  (``backups_create``, ``backups_report``, etc.) are preserved as thin
  Django/admin-facing surfaces for manual use, with backward-compatible env-var
  fallback in the service layer (``_load_target_runtime_settings``). Railway-
  target media sync fail-closed guard is preserved through the explicit
  ``ROUTE_KIND`` marker in the adapter path.

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

**Boundary interface (replaces the hidden protocol; implemented in F5.3):**
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
  backward-compatibility shim; generated-project migration guidance is documented
  in F5.4.

**Out of scope for this section:** Migration documentation (F5.4) is shipped at
`docs/technical/dr_engine_migration.md`. F5.2a (snapshot/archive primitives),
F5.2b (restore/orchestration), F5.3 (explicit adapter boundary), and F5.4
(migration docs) are all shipped and reflected in the current-state description
above.

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
- ✅ Django email delivery for notifications uses `django-anymail` as the approved delivery layer with Resend as the current first-class provider for v0.78.0
- ✅ Version pinning (predictable compatibility for Django foundations)
- ✅ **Fail hard** — every configuration error, missing dependency, and invalid runtime state raises an explicit exception; no silent fallbacks, no graceful degradation (see §fail-hard-principle below)

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
| F12.2 | `project_state.py:_read_through_import_legacy()` | One-time M2 consolidation path: pre-M2 projects have `config.yml` + `file_hashes.yml` but lack consolidated `state.yml` fields; failing hard on stale legacy files would block the M2 migration. Failures are logged and import is skipped. | Remove when the M2 state format has been deployed for two full releases with no known pre-M2 projects in active use. |

**Known violations:** See [findings.md §Finding-8](../../findings.md#finding-8) for the active violation list and [roadmap.md §AF8](./roadmap.md#af8) for remediation tasks.

---

### Notifications Contract (v0.83.0 behavior)

- Authoritative notifications configuration lives in `quickscale.yml`, generated Django settings, and environment variables. Any `NotificationSettings` admin surface is a read-only operational snapshot only, with no secrets and no alternate mutable config path.
- `modules.notifications.sender_email` defaults to `noreply@example.com` as a local-development placeholder only.
- When `modules.notifications.resend_domain` is set, `quickscale apply` requires a non-placeholder sender email plus a valid `modules.notifications.resend_api_key_env_var` reference; apply fails hard instead of silently leaving live delivery on the console backend.
- Runtime backend selection stays on Django's console email backend until live Resend delivery is fully configured. If the live Resend backend is active anyway and the placeholder sender or resolved API key is still missing, queued deliveries fail explicitly rather than degrading silently.
- Delivery tracking is recipient-granular. A multi-recipient send fans out into one tracked provider send/message ID per recipient delivery record.
- Provider-visible tags/metadata are optional and limited to a tiny non-sensitive allowlist. Internal correlation identifiers stay local to QuickScale-owned records.

### Multi-tenant SaaS Architecture {#multitenant-saas-architecture}

**Architectural Decision (v0.86.0):** QuickScale-generated SaaS apps use **PostgreSQL FORCE RLS on a single Railway deployment** — one app service + one PostgreSQL 18 service, all tenants share one database and schema. Organizations are the billing and isolation unit. See [organizations.md](./organizations.md) for the full design and [roadmap.md](./roadmap.md) for open implementation work.

**Chosen shape:**
- ✅ Single Railway project (one app + one PostgreSQL 18 service); Railway bill is flat regardless of tenant count
- ✅ Shared database + shared schema; isolation enforced by PostgreSQL FORCE RLS + contextvar TenantManager
- ✅ Billing unit: `Subscription → Organization` (not per-user)
- ✅ URL routing: flat routes only — `/crm/`, `/blog/`; no `/orgs/<slug>/` content routes
- ✅ Users may belong to multiple organizations; org-switcher in the React UI
- ✅ All organizations get all modules; differentiate by credit limits only (no feature gating)

**RLS enforcement rule (critical):**
- RLS enforces only when the app connects as the `NOSUPERUSER/NOBYPASSRLS` runtime role, selected by `RUNTIME_DATABASE_URL`
- When `RUNTIME_DATABASE_URL` is unset the app falls back to the superuser `DATABASE_URL` (BYPASSRLS) — **all RLS silently disables; fail open**
- Boot guard required: `orgs.QuickscaleOrgsConfig.ready()` must assert `rolbypassrls=false` in saas mode with `DEBUG=False`; raise `ImproperlyConfigured` and refuse to start if the connected role has BYPASSRLS (T1.18)
- `start.sh` deliberately unsets `RUNTIME_DATABASE_URL` for `migrate` — this is correct for migrations; catastrophic for `runserver`/`gunicorn`

**Rejected alternatives (do not re-introduce):**
- ❌ **Per-client Railway deployment** — linear operational overhead per tenant; not a SaaS platform
- ❌ **App-layer-only filtering without RLS** — no defence-in-depth; a single missed filter leaks cross-tenant data
- ❌ **PostgreSQL schema-per-tenant isolation** — schema metadata bloat, migration complexity with many tenants
- ❌ **Supabase as the database provider** — valid for teams that want managed infrastructure, but introduces vendor lock-in and changes the cost/operational model; our self-hosted Railway approach is equivalent in security model once AF9 is fixed (both use a GUC parameter set per-transaction as the tenant context carrier)

**Supabase architecture parity note (2026-06-29):**
QuickScale's shared-schema + FORCE RLS model is structurally equivalent to Supabase's multi-tenant architecture. Both use a PostgreSQL GUC parameter as the per-transaction tenant context carrier; both use `FORCE ROW LEVEL SECURITY`; both use a NOBYPASSRLS runtime role for application queries and a BYPASSRLS role for operator/admin access. The key difference is injection mechanism: Supabase's PostgREST sets the GUC from JWT claims before every query; QuickScale's AF9 fix (execute_wrapper deriving GUC from ContextVar at transaction start) achieves the same guarantee. After AF9 merges, the two models are equivalent. Supabase also ships a dashboard "Impersonate User" button — QuickScale's VIEW-AS task (see roadmap.md §Phase C) closes that parity gap.

**Operator debug mode — locked design (VIEW-AS, 2026-06-29):**
Django superusers may activate a debug session that scopes the entire request to a selected organization — allowing them to see the app exactly as that org's members see it. Design: session key `quickscale_modules_orgs.debug_as_org_id` (superuser-only); `TenantMiddleware._resolve_debug_org()` overrides Solo/SaaS resolution when key is present; `OrganizationAdmin` action activates it; debug banner rendered in base template while active; every activation audit-logged (who, which org, timestamp). No BYPASSRLS — debug session runs under the same restricted runtime role as all other tenant paths (RLS remains fully enforced). See roadmap.md §Phase C for the implementation task.

**Related docs:** [organizations.md](./organizations.md) (design) | [roadmap.md](./roadmap.md) (open implementation tasks D1, AF1–AF7, Phase C) | [findings.md](../../findings.md) (current risk posture)

---

### Billing Contract (v0.85.0 behavior)

- Authoritative billing configuration lives in `quickscale.yml`, generated Django settings, and environment variables. Planner/apply may write env-var references into managed settings, but Stripe publishable keys, secret keys, and webhook secrets stay environment-only and never persist in QuickScale database rows.
- Billing requires auth-backed users at apply/runtime; QuickScale does not support a standalone billing install without the auth module.
- Billing ships module-owned Django routes for public pricing (`/billing/pricing/`) and the signed-in dashboard (`/billing/dashboard/`). Fresh starter output may link into those pages, but QuickScale does not generate a starter-owned billing React page and does not rewrite existing project React files to adopt billing automatically.
- `WebhookEvent` is the transport-level replay/idempotency gate for incoming billing webhooks.
- `debit_user` is the approved service API for credit consumption.

**Not part of the current contract:**
- ❌ Independent namespace-package distribution for published modules/themes
- ❌ Hook/event systems beyond the documented extension contract
- ❌ Advanced configuration layers beyond the shipped `quickscale.yml` + `.quickscale/state.yml` workflow

## Prohibitions (Critical - DO NOT)

**Database:**
- ❌ SQLite for any purpose — dev, test, or production (see §Database Policy above); `django.db.backends.sqlite3` in any test settings file is a policy violation that must be resolved before merge
- ❌ `skipif(not postgres)` guards that allow isolation tests to be silently skipped rather than failing the build when Postgres is unavailable

**Multi-tenant / Tenant Isolation:**
- ❌ Per-client Railway deployment (linear overhead per tenant — not a SaaS platform)
- ❌ App-layer-only filtering without a PostgreSQL RLS backstop (no defence-in-depth; one missed filter leaks cross-tenant data)
- ❌ PostgreSQL schema-per-tenant isolation (schema metadata bloat, migration complexity)
- ❌ Connecting generated apps in saas/prod mode under a BYPASSRLS role (silently disables all RLS policies across all modules)
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
