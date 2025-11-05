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

**Purpose:** Single source of truth for QuickScale architecture, technical rules, and development standards for AI coding assistants and maintainers.

**Scope:** All first-party packages (core, CLI, themes, modules). Experto-AI and core contributors own these decisions.

## Quick Reference (AI Context)

**MVP Essentials:**
- ✅ Single CLI command: `quickscale init myapp`
- ✅ Generates standalone Django project (Poetry + pyproject.toml)
- ✅ Production-ready: Docker, PostgreSQL, pytest, CI/CD, security best practices
- ✅ Git subtree for core distribution (manual commands documented)
- ❌ NO YAML config, NO multiple templates, NO CLI wrappers (all Post-MVP)

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
- ✅ Release docs: `docs/releases/release-vX.XX.X-{implementation,review}.md`
- ❌ Never contradict decisions.md elsewhere

**Package README Policy:**
- ❌ Sub-packages (quickscale_core, quickscale_cli) MUST NOT have README.md
- ✅ Use root README.md only (avoids duplication)

## MVP vs Post-MVP Scope

**Terminology:**
- Foundation Phase: v0.52-v0.55 (incremental foundation)
- MVP: v0.56-v0.57.0 (production-ready personal toolkit)
- Post-MVP: v0.58+ (modules, packaging, marketplace)

**MVP (v0.56-v0.57.0):**
- ✅ `quickscale_core`: Scaffolding + git subtree integration (monolithic package)
- ✅ `quickscale_cli`: Single command `quickscale init myapp` (no flags)
- ✅ Generated project: Standalone Django (user owns completely)
- ✅ Settings: Standalone settings.py (NO inheritance from core by default)
- ✅ Templates: Single starter template only
- ❌ CLI git subtree helpers - Post-MVP
- ❌ Multiple templates - Post-MVP
- ❌ YAML configuration - Post-MVP

**MVP Output:** See [scaffolding.md §3](./scaffolding.md#mvp-structure)

### Module & Theme Architecture {#module-theme-architecture}

**Architectural Decision (v0.61.0):** Modules and themes serve different purposes and use different distribution mechanisms.

#### **Modules: Split Branch Distribution (Ongoing Dependencies)**

**Purpose:** Reusable Django apps that users embed and update over project lifetime.

**Distribution Strategy:**
1. Develop modules on `main` branch in `quickscale_modules/`
2. Auto-split to `splits/{module}-module` branches on release (GitHub Actions)
3. Users embed via `quickscale embed --module <name>`
4. Users update via `quickscale update` (updates installed modules only)

**Workflow:**
```bash
# User embeds auth module
quickscale embed --module auth
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

**Purpose:** Frontend scaffolding with different tech stacks (HTML, HTMX, React).

**Distribution Strategy:**
1. Store themes in `quickscale_core/generator/templates/themes/{showcase_html,showcase_htmx,showcase_react}/`
2. User selects theme during init: `quickscale init myproject --theme showcase_react`
3. Generator copies theme files to user's project (Jinja2 rendering)
4. User owns generated code completely, customizes immediately
5. **NO embed/update for themes** - one-time scaffolding only

**Workflow:**
```bash
# User generates project with React theme
quickscale init myproject --theme showcase_react
# Copies themes/showcase_react/ → myproject/
# User owns code, no git tracking

# User immediately customizes:
# - Changes colors, fonts, layout
# - Adds custom React components
# - Modifies package.json, vite.config.ts

# No updates for themes (user owns the code)
```

**Theme Directory Structure:**
```
quickscale_core/generator/templates/
└── themes/
  ├── showcase_html/         # Pure HTML + CSS
    │   ├── templates/
    │   └── static/
  ├── showcase_htmx/          # HTMX + Alpine.js + Tailwind
    │   ├── templates/
    │   ├── static/
    │   └── package.json
  └── showcase_react/         # React + TypeScript + Vite
        ├── frontend/
        │   ├── src/
        │   └── vite.config.ts
        └── package.json
```

**Key Characteristics:**
- ❌ NOT runtime dependencies (just generated code)
- ❌ NO updates after generation (user owns and customizes)
- ✅ Frontend-heavy (~90% frontend, ~10% backend integration)
- ✅ Heavy customization expected (colors, layout, components)
- ✅ Disposable scaffolding, not ongoing dependencies

---

#### **Summary: Modules vs Themes**

| Aspect | Modules | Themes |
|--------|---------|--------|
| **Distribution** | Split branches (git subtree) | Generator templates (Jinja2) |
| **User Command** | `quickscale embed --module auth` | `quickscale init --theme showcase_react` |
| **Updates** | `quickscale update` (ongoing) | N/A (user owns code) |
| **Lifecycle** | Runtime dependency | One-time scaffolding |
| **Ownership** | Shared (can push back) | User owns completely |
| **Customization** | Minimal (mostly backend) | Heavy (colors, layout, etc.) |
| **Backend/Frontend** | 70% backend, 30% frontend | 10% backend, 90% frontend |

**For detailed workflow documentation** (split branch mechanics, conflict resolution, troubleshooting), see [roadmap.md §v0.61.0](./roadmap.md#v0610-theme-system-foundation--split-branch-infrastructure)

---

### Module Configuration Strategy {#module-configuration-strategy}

**Architectural Decision (v0.63.0):** Modules require configuration when embedded. QuickScale uses a **two-phase approach**:

#### **Phase 1 (MVP): Interactive Prompts During Embed**

**When**: v0.63.0 through v0.66.0 (core 3 modules)

**How**:
- `quickscale embed --module auth` → asks interactive questions → applies configuration automatically
- User does NOT manually edit settings.py, urls.py, or INSTALLED_APPS
- Configuration is tracked in `.quickscale/config.yml`

**Example**:
```bash
$ quickscale embed --module auth
? Enable user registration? (y/n) [y]: y
? Email verification required? (y/n) [n]: n

✅ Module 'auth' embedded successfully!
Automatic changes made:
  ✅ Added 'modules.auth' to INSTALLED_APPS
  ✅ Added allauth configuration to settings
  ✅ Added auth URLs to urls.py
  ✅ Ran initial migrations
```

**Benefits for MVP**:
- ✅ Simple, self-documenting UX (no YAML complexity)
- ✅ Scales well for 2-3 modules (auth, billing, teams)
- ✅ No manual settings editing required
- ✅ Creates foundation for YAML (same config options)

**Constraints**:
- ❌ NOT suitable for 10+ modules with many options (complexity threshold ~5 modules)
- ❌ NOT suitable for batch initialization (one module at a time)

**Implementation Requirements**:
1. Each module defines configuration prompts (via click.confirm/click.prompt)
2. Embed handler automatically updates:
   - INSTALLED_APPS in settings.py
   - Module-specific settings (e.g., ACCOUNT_ALLOW_REGISTRATION)
   - urls.py (include module URLs)
   - Runs initial migration (`python manage.py migrate`)
3. Configuration state stored in `.quickscale/config.yml` for tracking/updates

**When to Use Interactive Config** (MVP guidance):
- ✅ Simple yes/no options (enable registration, require verification)
- ✅ 1-3 modules being embedded
- ✅ User wants "quick setup" without thinking about config

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
# quickscale.yml (optional, v1.0.0+)
version: 0.66.0
modules:
  auth:
    ACCOUNT_ALLOW_REGISTRATION: true
    ACCOUNT_EMAIL_VERIFICATION: "optional"
  billing:
    STRIPE_API_KEY: "${STRIPE_API_KEY}"
    BILLING_CURRENCY: "usd"

# Usage: quickscale embed --config quickscale.yml
# OR: quickscale init myproject --config quickscale.yml
```

**Backward Compatibility**:
- Interactive prompts always work (even after YAML support added)
- YAML is optional convenience, not required
- Existing `embed` commands continue unchanged

**Decision Rule**:
- **MVP (v0.63.0-v0.66.0)**: Interactive prompts ONLY, no YAML
- **Post-MVP (v1.0.0+)**: YAML support optional, interactive prompts unchanged

**Authoritative Reference**: [roadmap.md §Module Configuration Strategy](./roadmap.md#-module-configuration-strategy-v06300)

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
| `quickscale init <project>` (single command, no flags) | IN | Core MVP entrypoint. (See: Phase 1.2.3) |
| Generate Django starter (manage.py, settings.py, urls.py, wsgi/asgi, templates, pyproject.toml) | IN | Starter uses `pyproject.toml` (Poetry). Generated projects include a `pyproject.toml` and `poetry.lock` by default; `requirements.txt` is not generated. |
| `quickscale_core` package (monolithic, src layout) | IN | Treat `quickscale_core` as a regular monolithic package in MVP (explicit `__init__.py`). See Section: "Core package shape" in this file. |
| `quickscale_core` embedding via git-subtree (manual documented workflow) | IN (manual) | Manual subtree commands are documented and supported; embedding is opt-in and advanced. |
| CLI development commands (`up`, `down`, `shell`, `manage`, `logs`, `ps`) | IN (v0.59.0) | User-friendly wrappers for Docker/Django operations to improve developer experience. |
| `quickscale init --theme <name>` flag | IN (v0.61.0) | Theme selection during init (showcase_html). Themes are one-time copy, not embedded. |
| CLI module management commands (`embed --module`, `update`, `push`) | IN (v0.62.0) | Module embed/update via split branches. **Starting v0.63.0**: Interactive prompts for module configuration (user doesn't manually edit settings.py). See [§Module Configuration Strategy](#module-configuration-strategy). |
| Module configuration (interactive prompts, not YAML) | IN (v0.63.0+) | Modules configured via interactive questions during embed (`--module auth`). YAML support deferred to Post-MVP (v1.0.0+). See [§Module Configuration Strategy](#module-configuration-strategy). |
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
| `quickscale_modules/` (split branch distribution) | IN (v0.62.0+) | Modules distributed via git subtree split branches. Embed with `quickscale embed --module <name>`. |
| Themes (HTML, HTMX, React) | IN (v0.61.0+) | Generator templates, one-time copy during init. User owns generated code, no updates. |
| `quickscale_themes/` packaged themes | OUT (Post-MVP) | Themes as PyPI packages is Post-MVP. Current: generator templates only. |
| YAML declarative configuration (`quickscale.yml`) | OUT (Post-MVP) | **v0.63.0-v0.66.0**: Use interactive prompts instead. **v1.0.0+**: YAML optional convenience feature. See [§Module Configuration Strategy](#module-configuration-strategy). |
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

- ✅ `quickscale init <project>` - ONLY command (no flags, single starter template)
- ✅ `quickscale up` - Start Docker services (wrapper for docker-compose up)
- ✅ `quickscale down` - Stop Docker services (wrapper for docker-compose down)
- ✅ `quickscale shell` - Interactive bash shell in container
- ✅ `quickscale manage <cmd>` - Run Django management commands
- ✅ `quickscale logs [service]` - View Docker logs
- ✅ `quickscale ps` - Show service status
- ✅ `quickscale deploy railway` - Automated Railway deployment with PostgreSQL setup
- ✅ `quickscale deploy railway --skip-migrations` - Deploy without running migrations
- ✅ `quickscale deploy railway --skip-collectstatic` - Deploy without collecting static files
- ✅ `quickscale deploy railway --project-name <name>` - Specify project name

**v0.61.0 - Theme System Foundation:**
- 📋 `quickscale init --theme <name>` - Theme selection (showcase_html/showcase_htmx/showcase_react)
- 📋 Theme directory structure in generator templates
- 📋 Refactor existing templates into `themes/showcase_html/` directory
- 📋 Placeholder directories for `themes/showcase_htmx/` and `themes/showcase_react/`

**v0.62.0 - Split Branch Infrastructure (Module Management):**
- 📋 `quickscale embed --module <name>` - Embed modules via split branches
- 📋 `quickscale update` - Update installed modules
- 📋 `quickscale push --module <name>` - Contribute module improvements
- 📋 GitHub Actions for automatic split branch creation
- 📋 `.quickscale/config.yml` module tracking

**v0.63.0-v0.66.0 - Module Development:**
- 📋 `quickscale_modules.auth` - Authentication module core (v0.63.0)
- 📋 `quickscale_modules.auth` - Email verification & production email (v0.64.0)
- 📋 `quickscale_modules.billing` - Billing module (v0.65.0)
- 📋 `quickscale_modules.teams` - Teams/multi-tenancy module (v0.66.0)

**v0.67.0-v0.68.0 - Additional Themes:**
- 📋 HTMX theme variant with auth/billing/teams components (v0.67.0)
- 📋 React theme variant with auth/billing/teams components (v0.68.0)

**v0.69.0 - Cross-Theme Module:**
- 📋 `quickscale_modules.notifications` - Email infrastructure for all 3 themes (v0.69.0)

**v0.70.0 - Advanced Module Management:**
- 📋 `quickscale update --all` - Batch update all modules
- 📋 `quickscale status` - Show installed module versions
- 📋 `quickscale list-modules` - Discover available modules

**Post-MVP (Future):**
- ❌ `quickscale validate` - YAML configuration validation (requires config system)
- ❌ `quickscale generate` - Generate from config (requires config system)
- 📋 `quickscale embed --module auth@v0.63.0` - Pin specific module versions

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
- ✅ CLI: `quickscale init myapp` (single command)
- ✅ Manual git subtree commands (documented)
- ✅ No package registries, offline development
- ❌ No CLI wrapper helpers (`embed-core`, `update-core`, `sync-push`) - Post-MVP

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
- ❌ NEVER run `quickscale init` in the QuickScale codebase (would generate unwanted project files)

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
