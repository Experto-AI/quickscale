# decisions.md

<!--
decisions.md - Authoritative Technical Specification

PURPOSE: This document is the single source of truth for all architectural decisions, technical implementation rules, and development standards for QuickScale.

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

**Purpose:** Single source of truth for QuickScale architecture, technical rules, and development standards for AI coding assistants and maintainers.

**Scope:** All first-party packages (core, CLI, themes, modules). Experto-AI and core contributors own these decisions.

## Quick Reference (AI Context)

**MVP Essentials:**
- ✅ CLI workflow: `quickscale plan myapp` + `quickscale apply`
- ✅ Generates standalone Django project (Poetry + pyproject.toml)
- ✅ Production-ready: Docker, PostgreSQL, pytest, CI/CD, security best practices
- ✅ Git subtree for module distribution
- ✅ Declarative YAML configuration (quickscale.yml)

**Development Stack:**
- ✅ Poetry (package manager), Ruff (format + lint), MyPy (type check), pytest (testing)
- ✅ src/ layout for all packages
- ❌ NO Black, NO Flake8, NO requirements.txt, NO setup.py

**Key Constraints:**
- 70% unit test coverage minimum per file (CI enforced)
- decisions.md is authoritative (update FIRST, never contradict)
- Sub-packages MUST NOT have README.md (use root README only)
- Settings: Standalone by default (NO automatic inheritance)

## Critical Rules

**Documentation Hierarchy:**
- ✅ decisions.md is authoritative - always wins conflicts
- ✅ Update decisions.md FIRST, then other docs
- ✅ Contributing guides: `docs/contrib/*.md`
- ✅ Release docs: `docs/releases-archive/release-vX.XX.X-{implementation,review}.md` (archived)
- ❌ Never contradict decisions.md elsewhere

**Package README Policy:**
- ❌ Sub-packages (quickscale_core, quickscale_cli) MUST NOT have README.md
- ✅ `quickscale_modules/*` MUST have README.md (distributed as standalone)
- ✅ Use root README.md only for core/cli (avoids duplication)

## MVP vs Post-MVP Scope

**Terminology:**
- Foundation Phase: v0.52-v0.55 (incremental foundation)
- MVP: v0.56-v0.57.0 (production-ready personal toolkit)
- Post-MVP: v0.58+ (modules, packaging, marketplace)

**MVP (v0.56-v0.57.0):**
- ✅ `quickscale_core`: Scaffolding + git subtree integration (monolithic package)
- ✅ `quickscale_cli`: Plan/apply workflow (`quickscale plan` + `quickscale apply`)
- ✅ Generated project: Standalone Django (user owns completely)
- ✅ Settings: Standalone settings.py (NO inheritance from core by default)
- ✅ Templates: Single starter template only
- ❌ Multiple themes - Post-MVP

**MVP Output:** See [scaffolding.md §3](./scaffolding.md#mvp-structure)

### Module & Theme Architecture {#module-theme-architecture}

**Architectural Decision (v0.61.0):** Modules and themes serve different purposes and use different distribution mechanisms.

#### **Modules: Split Branch Distribution (Ongoing Dependencies)**

**Purpose:** Reusable Django apps that users embed and update over project lifetime.

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
├── main                       # All development (auth, billing, teams, etc.)
├── splits/auth-module         # Auto-generated from quickscale_modules/auth/
├── splits/billing-module      # Auto-generated from quickscale_modules/billing/
└── splits/teams-module        # Auto-generated from quickscale_modules/teams/
```

**User Project Structure:**
```
myproject/
├── .quickscale/
│   └── config.yml             # Tracks installed modules
├── modules/                   # Embedded modules (git subtrees)
│   ├── auth/                  # From splits/auth-module
│   └── billing/               # From splits/billing-module
└── myproject/
    └── settings/
        └── base.py            # INSTALLED_APPS = [..., "modules.auth", "modules.billing"]
```

**Key Characteristics:**
- ✅ Runtime dependencies (in INSTALLED_APPS)
- ✅ Updated over project lifetime
- ✅ Backend-heavy (~70% backend, ~30% frontend)
- ✅ Theme-agnostic (work with all themes)
- ✅ Users can contribute improvements back

---

#### **Themes: Generator Templates (One-time Copy)**

**Purpose:** Complete project scaffolding ranging from empty starters to full vertical applications.

**Theme Categories (v0.67.0 Decision):**

1. **Starter Themes** — Empty foundations for building custom applications
   - `showcase_html` — Pure HTML + CSS (default)
   - `showcase_htmx` — HTMX + Alpine.js (planned v0.74.0)
   - `showcase_react` — React + TypeScript + Vite (planned v0.75.0)
   - Minimal code, ready for module embedding
   - Foundation for custom development

2. **Vertical Themes** — Complete applications for specific industries
   - `crm` — CRM application, React-based (v0.74.0)
   - `saas_starter` — SaaS with billing/teams (future)
   - Pre-configured modules, production-ready
   - Can be used as-is or further enhanced

**Distribution Strategy:**
1. Store themes in `quickscale_core/generator/templates/themes/{theme_name}/`
2. User selects theme via `quickscale plan` → `quickscale apply` (v0.68.0+)
3. Generator copies theme files to user's project (Jinja2 rendering)
4. User owns generated code completely, customizes immediately
5. **NO embed/update for themes** - one-time scaffolding only

**Workflow:**
```bash
# Create project with starter theme (empty foundation)
quickscale plan myproject
# → Select theme: showcase_html
# → Select modules to embed: auth, billing
quickscale apply

# Create project with vertical theme (complete application)
quickscale plan mycrm
# → Select theme: crm
# → Modules pre-configured (crm auto-embedded)
quickscale apply
```

**Theme Directory Structure:**
```
quickscale_core/generator/templates/
└── themes/
    # Starter Themes (empty foundations)
    ├── showcase_html/         # Pure HTML + CSS
    │   ├── templates/
    │   └── static/
    ├── showcase_htmx/         # HTMX + Alpine.js (planned v0.75.0)
    │   ├── templates/
    │   ├── static/
    │   └── package.json
    ├── showcase_react/        # React + TypeScript + Vite (planned, via crm)
    │   ├── frontend/
    │   │   ├── src/
    │   │   └── vite.config.ts
    │   └── package.json
    #
    # Vertical Themes (complete applications)
    └── crm/                   # CRM application, React-based (v0.74.0)
        ├── frontend/          # React + Vite application
        │   ├── src/
        │   │   ├── components/
        │   │   └── pages/
        │   └── vite.config.ts
        ├── api/               # Django REST Framework
        │   ├── serializers.py.j2
        │   └── views.py.j2
        ├── templates/         # Django templates (React entry point)
        ├── models.py.j2       # CRM models (extends core)
        ├── views.py.j2        # CRM views
        └── README.md          # Vertical documentation
```

**Starter vs Vertical Theme Comparison:**

| Aspect | Starter Themes | Vertical Themes |
|--------|----------------|-----------------|
| **Purpose** | Empty foundation | Complete application |
| **Modules** | None (embed later) | Pre-configured |
| **Use case** | Custom development | Production-ready or enhance |
| **Examples** | showcase_html, showcase_react | crm, job_board |
| **Customization** | Build from scratch | Modify existing features |


**Key Characteristics:**
- ❌ NOT runtime dependencies (just generated code)
- ❌ NO updates after generation (user owns and customizes)
- ✅ One-time scaffolding, user owns completely
- ✅ Starter themes: empty foundations for custom development
- ✅ Vertical themes: complete applications ready for production

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
| `.quickscale/state.yml` | Applied state after execution | Output (what was actually done) |
| `.quickscale/config.yml` | Module metadata for updates | System state (v0.62.0 legacy) |

#### **Desired State Schema** (`quickscale.yml`)

User-editable configuration file with this structure:

```yaml
version: 0.73.0
project:
  name: myapp
  theme: showcase_html
modules:
  - name: auth
  - name: listings
docker:
  build: true
  start: true
```

**Constraints**:
- ✅ Version-controllable (stored in git)
- ✅ User-editable and reviewable
- ✅ One file per project
- ✅ Location: Project root

#### **Applied State Schema** (`.quickscale/state.yml`, v0.69.0+)

System-managed state file tracking what has been applied:

```yaml
version: 0.73.0
project:
  name: myapp
  theme: showcase_html
applied_modules:
  - name: auth
    version: 0.73.0
    commit: abc123def456
    applied_at: 2025-12-03T14:30:00Z
  - name: listings
    version: 0.73.0
    commit: xyz789uvw012
    applied_at: 2025-12-03T14:31:00Z
docker:
  build: true
  start: true
generated_by_version: 0.68.0
last_apply_at: 2025-12-03T14:32:00Z
```

**Constraints**:
- ✅ Auto-generated and auto-updated by `quickscale apply`
- ✅ Do NOT edit manually (system will overwrite)
- ✅ One file per project
- ✅ Location: `.quickscale/state.yml`

#### **Operational Properties**

- **Declarative**: User specifies desired state in YAML; tool computes and executes changes
- **Idempotent**: Running apply with unchanged config is safe (no-op, no re-execution)
- **Incremental**: Apply computes delta between desired and applied state; only applies necessary changes
- **Traceable**: State file records what modules/versions/commits were applied and when
- **Recoverable**: State enables drift detection and recovery workflows

#### **Implementation Rules**

**State Computation** (`quickscale apply`):
1. Read `quickscale.yml` (desired state)
2. Read `.quickscale/state.yml` (applied state)
3. Compute delta (what changed)
4. Show delta to user for confirmation
5. Execute changes
6. Write new state to `.quickscale/state.yml`

**Idempotency Requirements**:
- ❌ NEVER re-execute already-applied modules
- ✅ Skip modules that are already embedded
- ✅ Only embed modules that appear in desired state but not in applied state
- ✅ Remove modules that were applied but no longer appear in desired state (future)

**State Integrity**:
- ✅ Write state file atomically (no partial writes)
- ✅ Include timestamp and generator version for auditing
- ✅ Never corrupt state from manual edits (reject if format invalid)

#### **Related Files**

- **Module tracking**: `.quickscale/config.yml` (v0.62.0+) — Records module branches and versions for `quickscale update` and `quickscale push` operations. Will consolidate into `state.yml` post-MVP.
- **User manual**: See [user_manual.md §4.3](./user_manual.md#43-planapply-commands-shipped-in-v0680) for workflow examples and CLI usage.
- **Project structure**: See [scaffolding.md §5](./scaffolding.md#generated-project-output) for complete project layout including state files.

---

### Module Configuration Strategy {#module-configuration-strategy}

**Architectural Decision (v0.72.0):** Modules require configuration when embedded. QuickScale uses an **interactive wizard during plan**:

#### **Interactive Configuration via Plan/Apply**

**How**:
- `quickscale plan myapp --add auth` → adds auth module to configuration
- The `plan` wizard asks interactive questions for module-specific options
- `quickscale apply` → embeds modules and applies configuration automatically
- User does NOT manually edit settings.py, urls.py, or INSTALLED_APPS
- Configuration is tracked in `.quickscale/state.yml`

**Example**:
```bash
$ quickscale plan myapp --add auth
? Select theme (showcase_html): showcase_html
? Enable user registration? (y/n) [y]: y
? Email verification required? (y/n) [n]: n

✅ Configuration saved to quickscale.yml

$ quickscale apply
✅ Module 'auth' embedded successfully!
Automatic changes made:
  ✅ Added 'modules.auth' to INSTALLED_APPS
  ✅ Added allauth configuration to settings
  ✅ Added auth URLs to urls.py
  ✅ Ran initial migrations
```

**Benefits**:
- ✅ Declarative configuration (version-controllable quickscale.yml)
- ✅ Reproducible project generation
- ✅ No manual settings editing required
- ✅ Terraform-style workflow (plan → review → apply)

**Implementation Requirements**:
1. Each module defines configuration prompts (via click.confirm/click.prompt in plan wizard)
2. Apply handler automatically updates:
   - INSTALLED_APPS in settings.py
   - Module-specific settings (e.g., ACCOUNT_ALLOW_REGISTRATION)
   - urls.py (include module URLs)
   - Runs initial migration (`python manage.py migrate`)
3. Configuration state stored in `.quickscale/state.yml` for tracking/updates

**When to Use Interactive Config**:
- ✅ Simple yes/no options (enable registration, require verification)
- ✅ 1-5 modules being embedded
- ✅ User wants declarative configuration they can version control

---

#### **Phase 2 (Post-MVP): YAML Configuration (Optional)**

**When**: v1.0.0+ (optional convenience feature)

**Why Defer**:
- 📋 MVP MVP focuses on 3 core modules — interactive prompts work fine
- 🎯 Complexity threshold not reached until 5+ modules
- 🚀 Faster to ship MVP with simple interactive UX
- 🔄 Interactive approach creates foundation for YAML

**Future workflow** (v1.0.0+):
```yaml
# quickscale.yml (v0.68.0+)
version: 0.73.0
project:
  name: myproject
  theme: showcase_html
modules:
  auth:
    options:
      ACCOUNT_ALLOW_REGISTRATION: true
      ACCOUNT_EMAIL_VERIFICATION: "optional"
  billing:
    options:
      STRIPE_API_KEY: "${STRIPE_API_KEY}"
      BILLING_CURRENCY: "usd"
docker:
  start: true
  build: true

# Usage: quickscale plan myproject → creates quickscale.yml
#        quickscale apply → executes configuration
```

**Decision Rule**:
- **v0.72.0+**: Plan/apply is the primary workflow
- Interactive prompts guide configuration during `quickscale plan`

**Authoritative Reference**: [roadmap.md §Plan/Apply Architecture](./roadmap.md#-planapply-architecture-v06800)

---

### Module Manifest Architecture {#module-manifest-architecture}

**Architectural Decision (v0.71.0):** Each module includes `module.yml` declaring configuration options as mutable or immutable.

**Manifest Schema:**
```yaml
name: auth
version: 0.73.0
config:
  mutable:
    registration_enabled:
      type: boolean
      default: true
      django_setting: ACCOUNT_ALLOW_REGISTRATION
  immutable:
    social_providers:
      type: list
      default: []
```

**Configuration Rules:**

| Aspect | Mutable | Immutable |
|--------|---------|-----------|
| **Definition** | Runtime-changeable via `quickscale apply` | Embed-time-only, locked after |
| **Storage** | Django `settings.py` | `.quickscale/state.yml` |
| **Changes** | Auto-update settings.py on apply | Reject with error guidance |
| **Code** | Read from settings (no hardcoding) | Configured at embed time |
| **Example** | `ACCOUNT_ALLOW_REGISTRATION` | `social_providers` list |

**Apply Behavior** (extends v0.68.0-v0.70.0 Plan/Apply):
1. Load module manifest from embedded module
2. Compare desired config (`quickscale.yml`) vs applied state (`.quickscale/state.yml`)
3. For mutable changes: update `settings.py` automatically
4. For immutable changes: error with guidance ("To change X, run `quickscale remove <module>` then re-embed")
5. Update `.quickscale/state.yml` with new config values

**Constraints:**
- ✅ Every module MUST have `module.yml` at package root
- ✅ Mutable options MUST specify `django_setting` key
- ✅ Immutable options MUST NOT have `django_setting`
- ✅ Module code MUST read configurable values from settings (not hardcoded)
- ✅ Backward compatible: modules without manifest treated as all-immutable

**Tie-Breaker:** For config option disputes, default to **immutable** (safer) unless explicit `django_setting` mapping exists.

---

### Module Implementation Checklist {#module-implementation-checklist}

**Architectural Decision (v0.67.0):** Every QuickScale module must be complete, embeddable, and usable immediately after `quickscale apply`. This checklist ensures no gaps between planning and implementation.

#### **Required Components (All Modules)**

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
[tool.poetry]
name = "quickscale-module-<name>"
version = "0.XX.0"
description = "QuickScale <name> module - brief description"
authors = ["Experto-AI <contact@experto.ai>"]
license = "MIT"
readme = "README.md"
packages = [{include = "quickscale_modules_<name>", from = "src"}]

[tool.poetry.dependencies]
python = "^3.11"
Django = ">=5.0,<6.0"
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
- [ ] `models.py` — **Concrete model(s)** for immediate use (not just abstract base classes)
- [ ] `views.py` — Views with `model` attribute set (not requiring subclassing)
- [ ] `urls.py` — URL patterns with `app_name` for namespacing
- [ ] `admin.py` — Admin registration for concrete models (not just base admin classes)
- [ ] `migrations/0001_initial.py` — **Initial migration for concrete models**
- [ ] `migrations/__init__.py` — Migrations package init

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
- [ ] Unit tests for models, views, filters, admin
- [ ] 70%+ test coverage (CI enforced)
- [ ] Tests use concrete models (not abstract stubs)

**7. Split Branch Publishing:**
- [ ] Run `./scripts/publish_module.sh <name>` after implementation
- [ ] Verify split branch exists: `splits/<name>-module`

#### **Rationale**

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

**Post-MVP (v1.0.0+):**
- 📦 `quickscale_modules/*`: Optional PyPI packages (for easier installation)
- 📦 `quickscale_themes/*`: Optional PyPI packages (alternative to generator templates)
- 📦 YAML configuration system (declarative project definition)
- 📦 Marketplace ecosystem (commercial extensions)

**Structure:** See [scaffolding.md §4](./scaffolding.md#post-mvp-structure)

**Packaging Rules:**
- ✅ `quickscale_core`: Regular package (has `__init__.py`)
- ✅ `quickscale_modules/`, `quickscale_themes/`: PEP 420 namespaces (NO `__init__.py` at root)
- ✅ Poetry + pyproject.toml for ALL packages
- ✅ `find_namespace_packages()` for modules/themes (Post-MVP)

## MVP Feature Matrix (authoritative)

This matrix is the authoritative source of truth for **what is IN / OUT / PLANNED for the MVP** at the **feature level**.

**Scope**: High-level features and capabilities (e.g., "Docker support", "Testing infrastructure")

**Not in scope**: Implementation details (e.g., specific template files, task breakdowns)

**For implementation details**: See [roadmap.md](./roadmap.md) which implements the features defined in this matrix.

**Tie-breaker rule**: If roadmap.md conflicts with this matrix on feature scope, this matrix wins. Update ROADMAP to match.

Other documents (README.md, roadmap.md, scaffolding.md, commercial.md) MUST reference this section when describing MVP scope; decisions.md is the tie-breaker for any ambiguity.

| Feature / Area | MVP Status | Notes / Decision Reference |
|---|---:|---|
| **CORE CLI & SCAFFOLDING** |
| `quickscale plan <project>` and `quickscale apply` | IN (v0.68.0+) | Primary workflow. Terraform-style declarative configuration. Creates `quickscale.yml`, then executes it. |
| Generate Django starter (manage.py, settings.py, urls.py, wsgi/asgi, templates, pyproject.toml) | IN | Starter uses `pyproject.toml` (Poetry). Generated projects include a `pyproject.toml` and `poetry.lock` by default; `requirements.txt` is not generated. |
| `quickscale_core` package (monolithic, src layout) | IN | Treat `quickscale_core` as a regular monolithic package in MVP (explicit `__init__.py`). See Section: "Core package shape" in this file. |
| `quickscale_core` embedding via git-subtree (manual documented workflow) | IN (manual) | Manual subtree commands are documented and supported; embedding is opt-in and advanced. |
| CLI development commands (`up`, `down`, `shell`, `manage`, `logs`, `ps`) | IN (v0.59.0) | User-friendly wrappers for Docker/Django operations to improve developer experience. |
| CLI module management commands (`update`, `push`) | IN (v0.62.0) | Module update/push via split branches. Module embedding now handled by `quickscale apply`. |
| Module configuration (interactive prompts via plan wizard) | IN (v0.63.0+) | Modules configured via interactive questions during `quickscale plan`. See [§Module Configuration Strategy](#module-configuration-strategy). |
| Module manifests (`module.yml`) with mutable/immutable config | IN (v0.71.0+) | **v0.71.0**: Each module includes `module.yml` declaring config options as mutable or immutable. `quickscale apply` updates settings.py for mutable changes. See [§Module Manifest Architecture](#module-manifest-architecture). |
| `quickscale remove <module>` command | IN (v0.71.0+) | **v0.71.0**: Remove embedded modules with cleanup. Data loss warning required. Re-embed for new config. |
| Settings inheritance from `quickscale_core` into generated project | OPTIONAL | Default generated project uses standalone `settings.py`. If user explicitly embeds `quickscale_core`, optional settings inheritance is allowed and documented. |
| **PRODUCTION-READY FOUNDATIONS (Competitive Requirement)** | | **See [competitive_analysis.md §1-3](../overview/competitive_analysis.md#-critical-for-mvp-viability-must-have)** |
| Docker setup (Dockerfile + docker-compose.yml) | IN | Production-ready multi-stage Dockerfile + local dev docker-compose with PostgreSQL & Redis services. Match Cookiecutter quality. |
| PostgreSQL configuration (dev + production) | IN | Split settings: SQLite for local dev, PostgreSQL for production. DATABASE_URL env var support via python-decouple/django-environ. |
| Environment-based configuration (.env + split settings) | IN | settings/base.py, settings/local.py, settings/production.py pattern. Secure SECRET_KEY loading from environment. |
| Security best practices | IN | ALLOWED_HOSTS, security middleware, SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE in production settings. Sentry scaffolding (commented). |
| WhiteNoise static files configuration | IN | Production static file serving without CDN complexity. |
| Gunicorn WSGI server | IN | Production-ready WSGI server declared in `pyproject.toml` (Poetry). |
| pytest + factory_boy test setup | IN | Modern testing with pytest-django, factory_boy for fixtures. Sample tests demonstrating patterns. |
| GitHub Actions CI/CD pipeline | IN | .github/workflows/ci.yml for automated testing on push/PR. Test matrix: Python 3.10-3.12, Django 4.2-5.0. |
| Pre-commit hooks (ruff) | IN | .pre-commit-config.yaml for code quality enforcement before commits. |
| Comprehensive README with setup instructions | IN | README.md.j2 with Docker setup, local dev, testing, deployment instructions. |
| **MODULES & DISTRIBUTION** |
| `quickscale_modules/` (split branch distribution) | IN (v0.62.0+) | Modules distributed via git subtree split branches. Embed via `quickscale plan --add <name>` + `quickscale apply`. |
| Themes (HTML, HTMX, React) | IN (v0.61.0+) | Generator templates, one-time copy during apply. User owns generated code, no updates. |
| `quickscale_themes/` packaged themes | OUT (Post-MVP) | Themes as PyPI packages is Post-MVP. Current: generator templates only. |
| YAML declarative configuration (`quickscale.yml`) | IN (v0.68.0+) | **v0.68.0**: Shipped as part of Plan/Apply system. `quickscale plan` creates `quickscale.yml`, `quickscale apply` executes it. Terraform-style workflow. See [§Plan/Apply Architecture](#planapply-architecture). |
| State tracking (`.quickscale/state.yml`) | IN (v0.69.0+) | **v0.69.0**: Applied state tracking for incremental applies. Distinguishes desired state (`quickscale.yml`) from applied state (`.quickscale/state.yml`). |
| PyPI / private-registry distribution for commercial modules | OUT (Post-MVP) | Commercial distribution is Post-MVP (see commercial.md). |

**Notes:**
- This table is authoritative for release planning
- Production foundations (Docker, PostgreSQL, pytest, CI/CD) are P0 - table stakes for professional tool
- See [competitive_analysis.md](../overview/competitive_analysis.md#what-quickscale-must-incorporate-from-competitors)

## Authoritative Policies

**Settings Inheritance:**
- ✅ MVP: Standalone `settings.py` (no automatic inheritance from quickscale_core)
- ✅ Optional: Manual inheritance after git subtree embed (advanced users)
- ❌ NO automatic settings inheritance in MVP

**Packaging (All QuickScale Packages):**
- ✅ Poetry package manager
- ✅ pyproject.toml + poetry.lock (required)
- ✅ src/ layout (prevents accidental imports)
- ✅ Use ./scripts/install_global.sh for global Poetry install
- ❌ NO requirements.txt generation
- ❌ NO setup.py files
- ❌ NO pip commands (use Poetry only)

**Development Tools:**
- ✅ Ruff: Format + lint (replaces Black + Flake8)
- ✅ MyPy: Type checking (strict mode)
- ✅ pytest + pytest-django: Testing
- ✅ pytest-cov: Coverage reporting
- ❌ NO Black (use Ruff format)
- ❌ NO Flake8 (use Ruff check)

**Scripts Reference (AI Assistant Guidance):**
- `./scripts/install_global.sh` - **Install Poetry globally** - use official installer (REQUIRED FIRST: avoids version conflicts, DO NOT use pip/pipx)
- `./scripts/bootstrap.sh` - **Initial setup** - installs all dependencies and configures pre-commit hooks (run after install_global.sh)
- `./scripts/lint.sh` - **Format and lint** - runs Ruff format + check across all packages (replaces Black + Flake8)
- `./scripts/test_all.sh` - **Test all packages** - executes full test suite across quickscale_core, quickscale_cli, and modules
- `./scripts/test_e2e.sh` - **End-to-end tests** - runs E2E tests with PostgreSQL container and browser automation (slow, for release validation)
- `./scripts/publish.sh` - **Publish to PyPI** - automates package publishing workflow (Post-MVP for modules)
- `./scripts/version_tool.sh` - **Version management** - bumps version numbers across all packages consistently
- `./scripts/quickscale_legacy_symlink.sh` - **Legacy compatibility** - manages symlinks for legacy QuickScale installations

**AI Assistant Rules:**
- ✅ ALWAYS use `./scripts/install_global.sh` FIRST (never pip install poetry / pipx install poetry)
- ✅ Use `./scripts/lint.sh` for formatting (DO NOT use black or flake8 directly)
- ✅ Use `./scripts/test_all.sh` for running tests (DO NOT use pytest directly on individual packages without coordination)
- ✅ Use `./scripts/test_e2e.sh` for E2E validation before releases (DO NOT skip for production releases)
- ❌ NEVER install Poetry via pip/pipx (causes version conflicts with system Poetry)

### CLI Commands {#cli-command-matrix}

**Primary Workflow (v0.72.0+):**
- ✅ `quickscale plan <project>` - Create configuration interactively
- ✅ `quickscale apply [config.yml]` - Execute configuration to generate project

**Development Commands:**
- ✅ `quickscale up` - Start Docker services (wrapper for docker-compose up)
- ✅ `quickscale down` - Stop Docker services (wrapper for docker-compose down)
- ✅ `quickscale shell` - Interactive bash shell in container
- ✅ `quickscale manage <cmd>` - Run Django management commands
- ✅ `quickscale logs [service]` - View Docker logs
- ✅ `quickscale ps` - Show service status

**Deployment Commands:**
- ✅ `quickscale deploy railway` - Automated Railway deployment with PostgreSQL setup
- ✅ `quickscale deploy railway --project-name <name>` - Specify project name

**Module Management Commands:**
- ✅ `quickscale status` - Show project and module status
- ✅ `quickscale update` - Update installed modules
- ✅ `quickscale remove <module>` - Remove embedded module
- ✅ `quickscale push --module <name>` - Contribute module improvements

**Post-MVP (Future):**
- ❌ `quickscale validate` - YAML configuration validation (requires config system)
- ❌ `quickscale generate` - Generate from config (requires config system)
- 📋 `quickscale plan --add auth@v0.63.0` - Pin specific module versions

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

**Theme Support**: showcase_html (v0.66.0), showcase_htmx (v0.70.0), showcase_react (v0.71.0)

---

## Document Responsibilities

- **decisions.md**: Technical decisions, MVP matrix, tie-breakers (authoritative)
- **roadmap.md**: Timeline, phases, tasks
- **scaffolding.md**: Layout examples
- **README.md**: User guide, glossary
- **commercial.md**: Commercial models (Post-MVP)

**Rule:** Update decisions.md FIRST when changing scope.

## Testing Standards

**Coverage Targets:**
- ✅ 70% minimum unit test coverage per file: `quickscale_core`, `quickscale_cli`, modules, themes
- ✅ CI fails if any file falls below threshold
- ✅ Coverage reports on every CI run
- ℹ️ Note: 70% threshold applies to unit tests only, measured per file (not overall mean)

**Test Requirements:**
- ✅ New features: Tests required
- ✅ Bug fixes: Regression tests required
- ✅ CLI: Integration tests
- ✅ Business logic: Unit tests
- ✅ Critical paths: E2E tests

**Test Stack:**
- ✅ pytest + pytest-django: Test framework
- ✅ factory_boy: Test fixtures
- ✅ pytest-cov: Coverage measurement
- ✅ GitHub Actions: CI/CD

**Generated Projects Include:**
- Sample pytest-django test (demonstrates patterns)
- factory_boy configuration (for model factories)
- pytest.ini (test configuration)
- .github/workflows/ci.yml (automated testing)

### Test Isolation Policy (CRITICAL)

**Policy (MANDATORY):**
- ❌ **NEVER create test artifacts in the codebase directory**
- ✅ **ALWAYS use isolated filesystems for tests that create files**
- ✅ CLI tests: Use `CliRunner.isolated_filesystem()` context manager
- ✅ File generation tests: Use `pytest.tmp_path` or `pytest.tmpdir` fixtures
- ✅ Integration tests: Use temporary directories (`tempfile.mkdtemp()`)

### E2E Testing Policy

**Purpose**: Validate complete user workflows with real database and browser automation before releases.

**Requirements:**
- ✅ PostgreSQL 16 container via pytest-docker
- ✅ Playwright browser automation (Chromium)
- ✅ Full project lifecycle testing (generate → install → migrate → serve → browse)
- ✅ Separate from fast CI using pytest markers (`@pytest.mark.e2e`)

**When Required:**
- Pre-release validation
- Production-readiness verification
- Frontend regression testing
- Docker/database integration verification
- After generator template changes

**Tech Stack:**
- `pytest-docker`: Container orchestration for PostgreSQL
- `pytest-playwright`: Browser automation for frontend testing
- `docker-compose.test.yml`: Test infrastructure definition (PostgreSQL 16 with health checks)
- Playwright Chromium: Headless/headed browser for UI testing

**Execution Time**: 5-10 minutes for full suite (acceptable for release gates, excludes from fast CI)

**CI Strategy:**
- ✅ Fast CI (daily): Excludes E2E (`pytest -m "not e2e"`)
- ✅ Release CI (pre-release): Includes E2E (`pytest -m e2e`)
- ✅ Separate workflows ensure fast feedback for daily development

**Test Organization**: See [scaffolding.md §13](./scaffolding.md#13-e2e-test-infrastructure) for structure details.

**Usage**: See [user_manual.md §2.1](./user_manual.md#21-end-to-end-e2e-tests) for running instructions.

## Architecture (Post-MVP Vision)

**Library-Style Backend Modules:**
- ✅ Backend Modules: Reusable packages (auth, payments, billing, admin)
- ✅ Themes: Starting point applications (customize for business needs)
- ✅ Frontends: Directory-based presentation layer
- ✅ Built on proven Django foundations (django-allauth, dj-stripe, etc.)

**MVP Status:**
- ✅ `quickscale_core`: Scaffolding, utilities
- ✅ Directory-based frontends: Scaffolded templates
- ❌ `quickscale_modules/*`: Post-MVP only
- ❌ `quickscale_themes/*`: Post-MVP only

**See:** [scaffolding.md §2-3](./scaffolding.md#mvp-structure) for layouts

### Module Boundaries (Post-MVP)

**Admin Module (`quickscale_modules.admin`):**
- ✅ Enhanced Django admin interface
- ✅ System configuration, feature flags
- ✅ Monitoring dashboards
- ✅ Audit logging
- ❌ NOT authentication/authorization (use `auth` module)

**Auth Module (`quickscale_modules.auth`):**
- ✅ User identity, authentication, authorization
- ✅ User registration, profile management
- ❌ NOT admin interface enhancements

**Dependency Injection (Testing Only):**
- ✅ Production: Direct imports
- ✅ Tests: Constructor injection for mocking
- ❌ No DI frameworks or service registries

```python
class OrderProcessor:
    def __init__(self, payment_service=None):
        from quickscale_modules.payments import services
        self.payment_service = payment_service or services.DefaultPaymentService()
```

### Configuration (Post-MVP)

**MVP:**
- ✅ Standard Django `settings.py` (no YAML)
- ✅ No configuration files
- ✅ Standalone projects
- ❌ NO declarative configuration

**Post-MVP (Illustrative - NOT Implemented):**
```yaml
# Example only - NOT used in MVP
schema_version: 2
project: {name: mystore, version: 0.57.0}
theme: starter
backend_extensions: myapp.extensions
modules:
  payments: {provider: stripe}
  billing: {provider: stripe}
frontend: {source: ./custom_frontend/, variant: default}
```

**CLI (Post-MVP Ideas):**
- `quickscale validate` - Validate config
- `quickscale generate` - Generate from config
- ❌ NOT in MVP

### Distribution Strategy

**MVP - Git Subtree:**
- ✅ Primary distribution mechanism
- ✅ CLI workflow: `quickscale plan myapp` + `quickscale apply`
- ✅ Manual git subtree commands (documented)
- ✅ No package registries, offline development

**Post-MVP - PyPI:**
- 📦 Optional for modules/themes only
- 📦 NOT for core (stays git-based)
- 📦 For commercial extensions, marketplace

**Backward Compatibility:**
- ❌ Intentionally breaking from legacy QuickScale
- ❌ No automated migration

### Backend Extensions & Frontends {#backend-extensions-policy}

**MVP Backend:**
- ❌ NO `backend_extensions.py` generated
- ✅ Add local Django app for customizations
- ✅ Use `AppConfig.ready()` for wiring

**Post-MVP Pattern (Illustrative):**
```python
# backend_extensions.py - NOT in MVP
from quickscale_themes.starter import models
class ExtendedUser(models.User):
    department = models.CharField(max_length=100)
```

**MVP Frontend:**
- ✅ Optional `custom_frontend/` directory
- ✅ Basic variant support
- ✅ Standard Django templates
- ❌ No advanced tooling

**See:** [scaffolding.md §5](./scaffolding.md#5-generated-project-output)

### Database Architecture

**Standard Django Apps (Post-MVP):**
- ✅ Each module is a Django app with `app_label`
- ✅ Tables: `{app_label}_{model_name}` (Django default)
- ✅ Standard migrations handle dependencies
- ✅ Proven at scale (Wagtail, Django CMS)

```python
# Post-MVP example
class Transaction(models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    class Meta:
        app_label = 'quickscale_payments'
# Table: quickscale_payments_transaction
```

**INSTALLED_APPS (Post-MVP):**
```python
INSTALLED_APPS = [
    'quickscale_core',
    # 'quickscale_modules.auth',
    # 'quickscale_modules.payments',
    # 'quickscale_themes.starter',
]
```

## Operational Decisions

**Core Principles:**
- ✅ Starting points over complete solutions (customize for business needs)
- ✅ Creation-time assembly (NO runtime dynamic loading)
- ✅ Standard Django architecture (app_label namespacing, standard migrations)
- ✅ Separate CLI package (independent release cadence from core)
- ✅ src/ layout (prevents import errors during testing/building)
- ✅ Direct imports (NO DI frameworks or service registries)
- ✅ Single providers (Stripe payments, SendGrid email - embrace specifics)
- ✅ Version pinning (predictable compatibility for Django foundations)

**Post-MVP Only:**
- ❌ PEP 420 namespace packages (Post-MVP: independent module distribution)
- ❌ Hook/event system (deferred to Post-MVP)
- ❌ YAML configuration (deferred to Post-MVP)

## Prohibitions (Critical - DO NOT)

**Package Structure:**
- ❌ Nested package names (NO `quickscale/quickscale_core`)
- ❌ Tests inside `src/` (place in parallel `tests/` directory)
- ❌ README.md in sub-packages (use root README only)
- ❌ NEVER run `quickscale plan`/`quickscale apply` in the QuickScale codebase (would generate unwanted project files)

**Dependencies & Versions:**
- ❌ Unpinned versions in production
- ❌ Black or Flake8 (use Ruff instead)
- ❌ requirements.txt or setup.py (use Poetry + pyproject.toml)

**Architecture & Patterns:**
- ❌ Runtime dynamic `INSTALLED_APPS` modifications
- ❌ DI frameworks or service registries (direct imports in production)
- ❌ Abstract provider interfaces (embrace Stripe, SendGrid specifics)
- ❌ Custom database table naming (use Django's `app_label` default)
- ❌ HTTP APIs from modules (expose Python service layer only)
- ❌ Tight coupling themes to modules

**Configuration (Post-MVP):**
- ❌ Execute code in config files (pure data YAML only)
- ❌ Deep nesting in config syntax (keep flat and readable)

## Package Structure

**PEP 420 Namespace Packages (Post-MVP):**
- ✅ `quickscale_modules/`, `quickscale_themes/`: PEP 420 namespaces (no `__init__.py` at root)
- ✅ `quickscale_core`: Regular package (has `__init__.py`)
- ✅ Use `find_namespace_packages()` in `pyproject.toml`

**See:** [scaffolding.md §6](./scaffolding.md#6-naming-import-matrix-summary) for complete matrix

**Migration Checklist (MVP → Post-MVP):**
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
