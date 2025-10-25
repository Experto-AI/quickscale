# QuickScale Development Roadmap

<!--
roadmap.md - Development Timeline and Implementation Plan

PURPOSE: This document outlines the development timeline, implementation phases, and specific tasks for building QuickScale.

CONTENT GUIDELINES:
- Organize tasks by phases with clear deliverables and success criteria
- Include specific implementation tasks with technical requirements
- Provide timeline estimates and dependency relationships
- Track progress and update status as work is completed
- Focus on "when" and "what tasks" rather than "why" or "what"
- Reference other documents for context but avoid duplicating their content

WHAT TO ADD HERE:
- New development phases and milestone planning
- Specific implementation tasks and acceptance criteria
- Timeline updates and progress tracking
- Resource allocation and team assignments
- Risk mitigation strategies and contingency plans
- Testing strategies and quality gates

WHAT NOT TO ADD HERE:
- Strategic rationale or competitive analysis (belongs in quickscale.md)
- Technical specifications or architectural decisions (belongs in decisions.md)
- User documentation or getting started guides (belongs in README.md)
- Directory structures or scaffolding details (belongs in scaffolding.md)

RELATIONSHIP TO OTHER DOCUMENTS:
- decisions.md is authoritative for technical scope (MVP Feature Matrix, CLI commands, etc.)
- scaffolding.md is authoritative for directory structures and layouts
- This roadmap implements what decisions.md defines
- When in doubt, update decisions.md first, then this roadmap

TARGET AUDIENCE: Development team, project managers, stakeholders tracking progress
-->

---

## 🚀 **EVOLUTION-ALIGNED ROADMAP**

Execution details live here; the "personal toolkit first, community platform later" narrative stays in [quickscale.md](../overview/quickscale.md#evolution-strategy-personal-toolkit-first).

**AUTHORITATIVE SCOPE REFERENCE**: The [MVP Feature Matrix in decisions.md](./decisions.md#mvp-feature-matrix-authoritative) is the single source of truth for what's IN/OUT/PLANNED. When this roadmap conflicts with decisions.md, decisions.md wins.

### **📋 Current State Assessment**
- ✅ **Current Version**: v0.61.0 (Released - Theme System Foundation)
- 🔄 **Next Release**: v0.62.0 - Split Branch Infrastructure

### **Evolution Context Reference**
Need the narrative backdrop? Jump to [`quickscale.md`](../overview/quickscale.md#evolution-strategy-personal-toolkit-first) and come back here for the tasks.

---

### Completed Releases/Tasks/Sprints:

- Release v0.52.0: Project Foundation: `docs/releases/release-v0.52.0-implementation.md`
- Release v0.53.1: Core Django Project Templates: `docs/releases/release-v0.53.1-implementation.md`
- Release v0.53.2: Templates and Static Files: `docs/releases/release-v0.53.2-implementation.md`
- Release v0.53.3: Project Metadata & DevOps Templates: `docs/releases/release-v0.53.3-implementation.md`
- Release v0.54.0: Project Generator — Core project generation engine with atomic creation and comprehensive validation: `docs/releases/release-v0.54.0-implementation.md`
- Release v0.55.0: CLI implementation: `docs/releases/release-v0.55.0-implementation.md`
- Release v0.56.0-v0.56.2: Quality, Testing & CI/CD — Comprehensive testing infrastructure, code quality improvements, and production-ready CI/CD templates: `docs/releases/release-v0.56.0-implementation.md`
- Release v0.57.0: MVP Launch — Production-ready personal toolkit with comprehensive documentation: `docs/releases/release-v0.57.0-implementation.md`
- Release v0.58.0: E2E Testing Infrastructure — Complete lifecycle validation with PostgreSQL 16 and Playwright browser automation: `docs/releases/release-v0.58.0-implementation.md`
- Release v0.59.0: CLI Development Commands — User-friendly wrappers for Docker/Django operations: `docs/releases/release-v0.59.0-implementation.md`
- Release v0.60.0: Railway Deployment Support — Automated Railway deployment via `quickscale deploy railway` CLI command: `docs/releases/release-v0.60.0-implementation.md`
- Release v0.61.0: Theme System Foundation — `--theme` CLI flag, theme abstraction layer, ships with HTML theme only: `docs/releases/release-v0.61.0-implementation.md`
- Release v0.62.0 (2025-10-25): Module management CLI commands (`embed`, `update`, `push`), git utilities, module configuration tracking, GitHub Actions automation for split branch creation: `docs/releases/release-v0.62.0-implementation.md`

---

### Revised Next Release Sequence:

**Hybrid Approach: Theme Architecture First, Modules Fast, Themes Expand**

This strategy builds the theme system infrastructure upfront, delivers core modules quickly in HTML theme, then expands to additional themes. This avoids 3x development overhead while maintaining future flexibility.

**Phase 1: Foundation + Core Modules (HTML Theme Only)**
- ✅ **v0.61.0**: Theme System Foundation - `--theme` flag, theme abstraction layer, ships with HTML theme only (Released October 24, 2025)
- ✅ **v0.62.0**: Split Branch Infrastructure - Module management commands (`embed/update/push`), GitHub Actions automation (Released October 25, 2025)
- **v0.63.0**: `quickscale_modules.auth` - django-allauth integration (basic auth, NO social providers) - HTML theme only 🎯 **NEXT**
- **v0.64.0**: `quickscale_modules.auth` - Email verification, social auth providers, production email flows - HTML theme only
- **v0.65.0**: `quickscale_modules.billing` - dj-stripe subscriptions - HTML theme only
- **v0.66.0**: `quickscale_modules.teams` - Multi-tenancy patterns - HTML theme only 🎯 **SAAS FEATURE PARITY MILESTONE**

**Phase 2: Additional Themes (Port Existing Modules)**
- **v0.67.0**: HTMX Theme - Port auth/billing/teams components to HTMX + Alpine.js
- **v0.68.0**: React Theme - Port auth/billing/teams components to React + TypeScript SPA

**Phase 3: Expand Features (All Themes)**
- **v0.69.0**: `quickscale_modules.notifications` - Email infrastructure - All 3 themes
- **v0.70.0**: Advanced Module Management Features - Batch operations, status, discovery commands
- **v0.71.0**: Update Workflow Validation (P1 - Module Management)
- **v0.7x.0**: Additional modules based on real client needs

**🎯 Competitive Parity Goal (v0.66.0)**: At this point, QuickScale matches SaaS Pegasus on core features (auth, billing, teams) while offering superior architecture (composability, shared updates). See [competitive_analysis.md Timeline](../overview/competitive_analysis.md#timeline-reality-check).

**Rationale - Hybrid Approach Benefits**:
1. **Fast time-to-value**: Core modules delivered in 6-8 weeks (HTML only) vs. 17+ weeks (3 themes simultaneously)
2. **Architecture future-proof**: Theme system exists from v0.61.0, no refactoring needed later
3. **Lower risk**: Validate module design once before porting to additional themes
4. **Backend reuse**: ~70% of module code (Django models, views, auth) is theme-agnostic
5. **No breaking changes**: Existing users on HTML theme, new users pick theme upfront
6. **Proven pattern**: Matches Laravel Breeze (Blade → React/Vue later) and Rails Devise approaches

---

### **v0.63.0: `quickscale_modules.auth` - Authentication Module (Basic Auth)**

**Objective**: Create reusable authentication module wrapping django-allauth with custom User model patterns. HTML theme only. Basic authentication flows without social providers.

**Timeline**: After v0.62.0 (Target: 2-3 weeks)

**Status**: Ready for implementation - Infrastructure validated in v0.62.0

**Scope Boundaries** (Strict - No Feature Creep):
- ✅ **IN**: django-allauth integration (email/password only)
- ✅ **IN**: Custom User model scaffold (AbstractUser extension)
- ✅ **IN**: Basic auth views (login, logout, signup)
- ✅ **IN**: Password management (change password, reset password)
- ✅ **IN**: Account management (profile view/edit, account deletion)
- ✅ **IN**: HTML theme templates only
- ❌ **OUT**: Social auth providers (Google, GitHub, Facebook) → v0.64.0
- ❌ **OUT**: Email verification workflows → v0.64.0
- ❌ **OUT**: Production email configuration → v0.64.0
- ❌ **OUT**: HTMX/React theme variants → v0.67.0/v0.68.0
- ❌ **OUT**: 2FA/MFA → Future release
- ❌ **OUT**: Advanced permissions → teams module (v0.66.0)

**Competitive Context**: Matches SaaS Pegasus auth foundation without email verification. Validates module architecture before expanding features.

**Module Structure** (Per scaffolding.md §4):
```
quickscale_modules/auth/
├── pyproject.toml              # Module packaging config
├── README.md                   # Module documentation
├── src/quickscale_modules/auth/
│   ├── __init__.py
│   ├── apps.py                 # AppConfig with app_label
│   ├── models.py               # Custom User model (AbstractUser)
│   ├── forms.py                # django-allauth form overrides
│   ├── views.py                # Account management views
│   ├── urls.py                 # Auth URL patterns
│   ├── adapters.py             # django-allauth adapter customizations
│   ├── signals.py              # Post-registration signals
│   ├── templates/quickscale_modules_auth/
│   │   ├── account/
│   │   │   ├── login.html      # Login page (HTML theme)
│   │   │   ├── signup.html     # Signup page
│   │   │   ├── logout.html     # Logout confirmation
│   │   │   ├── password_change.html
│   │   │   ├── password_reset.html
│   │   │   ├── password_reset_done.html
│   │   │   ├── password_reset_confirm.html
│   │   │   ├── password_reset_complete.html
│   │   │   ├── profile.html    # Profile view/edit
│   │   │   └── account_inactive.html
│   │   └── base.html           # Auth template base
│   ├── static/quickscale_modules_auth/
│   │   ├── css/
│   │   │   └── auth.css        # Auth-specific styles
│   │   └── js/
│   │       └── auth.js         # Client-side validation
│   └── migrations/
│       └── 0001_initial.py     # Custom User model migration
└── tests/
    ├── conftest.py             # Test fixtures
    ├── test_models.py          # User model tests
    ├── test_views.py           # Auth view tests
    ├── test_forms.py           # Form validation tests
    ├── test_signals.py         # Signal handler tests
    └── test_adapters.py        # Allauth adapter tests
```

**Implementation Tasks** (11 Task Groups):

**1. Module Scaffolding & Configuration** (Foundation)
- [ ] Create `pyproject.toml` for auth module (Poetry config, dependencies)
- [ ] Add django-allauth to module dependencies (specify version range)
- [ ] Create `apps.py` with `QuickscaleAuthConfig(AppConfig)` and `app_label = "quickscale_modules_auth"`
- [ ] Create `__init__.py` with `default_app_config` and module version
- [ ] Update module README.md with installation instructions and usage examples

**2. Custom User Model** (Core Data Layer)
- [ ] Create `models.py` with `User(AbstractUser)` extending Django's AbstractUser
- [ ] Add custom fields to User model (if any baseline fields needed beyond AbstractUser)
- [ ] Override `USERNAME_FIELD` if using email-only auth (decision: keep username or email-only?)
- [ ] Add `get_absolute_url()` method for profile URLs
- [ ] Add `get_full_name()` and `get_short_name()` overrides (if customized)
- [ ] Create initial migration (`0001_initial.py`)
- [ ] Add model docstrings following Google style (functionality only, no args/returns)

**3. django-allauth Integration** (Auth Backend)
- [ ] Create `adapters.py` with `DefaultAccountAdapter` override
- [ ] Implement `is_open_for_signup()` method (configurable signup enable/disable)
- [ ] Implement `save_user()` method for custom user creation logic
- [ ] Configure allauth settings in module (SESSION_COOKIE_AGE, etc.)
- [ ] Create `signals.py` for post-registration signal handlers (e.g., create user profile)
- [ ] Document allauth settings that must be added to project settings.py

**4. Authentication Forms** (UI Data Layer)
- [ ] Create `forms.py` with custom SignupForm (override allauth default)
- [ ] Create custom LoginForm with validation (email normalization, etc.)
- [ ] Create PasswordChangeForm with strength validation
- [ ] Create PasswordResetForm with email validation
- [ ] Create ProfileUpdateForm for account management
- [ ] Add form docstrings (Google style)

**5. Authentication Views** (Business Logic)
- [ ] Create `views.py` with ProfileView (display user profile)
- [ ] Implement ProfileUpdateView (edit profile with form validation)
- [ ] Implement AccountDeleteView (soft delete or hard delete, with confirmation)
- [ ] Add proper permission checks (`LoginRequiredMixin`, user ownership validation)
- [ ] Add success messages using Django messages framework
- [ ] Add view docstrings (Google style)

**6. URL Configuration** (Routing)
- [ ] Create `urls.py` with auth URL patterns
- [ ] Include django-allauth account URLs (`allauth.urls`)
- [ ] Add custom URLs: profile, profile-edit, account-delete
- [ ] Use namespaced URLs (`app_name = "auth"`)
- [ ] Document URL patterns in module README

**7. HTML Theme Templates** (Presentation Layer - HTML Only)
- [ ] Create `templates/quickscale_modules_auth/base.html` (auth template base)
- [ ] Create `account/login.html` (email/password login form)
- [ ] Create `account/signup.html` (registration form)
- [ ] Create `account/logout.html` (logout confirmation)
- [ ] Create `account/password_change.html` (change password form)
- [ ] Create `account/password_reset.html` (request password reset)
- [ ] Create `account/password_reset_done.html` (reset email sent confirmation)
- [ ] Create `account/password_reset_confirm.html` (set new password form)
- [ ] Create `account/password_reset_complete.html` (reset complete confirmation)
- [ ] Create `account/profile.html` (view profile)
- [ ] Create `account/profile_edit.html` (edit profile form)
- [ ] Create `account/account_delete.html` (delete account confirmation)
- [ ] Add basic CSS styling in `static/quickscale_modules_auth/css/auth.css`
- [ ] Add client-side validation in `static/quickscale_modules_auth/js/auth.js`
- [ ] Ensure all templates extend from base template with proper blocks
- [ ] Add CSRF tokens to all forms
- [ ] Add form error display following Django conventions

**8. Testing** (Quality Assurance - 70% coverage minimum per file)
- [ ] Create `tests/conftest.py` with auth fixtures (user factory, authenticated client)
- [ ] Create `tests/test_models.py`:
  - [ ] Test User.objects.create_user() with valid data
  - [ ] Test User.objects.create_superuser() creates staff/superuser
  - [ ] Test custom User model fields
  - [ ] Test `get_absolute_url()` returns correct profile URL
  - [ ] Test `__str__()` representation
- [ ] Create `tests/test_views.py`:
  - [ ] Test login view GET/POST (valid/invalid credentials)
  - [ ] Test signup view GET/POST (valid/invalid data, duplicate email)
  - [ ] Test logout view
  - [ ] Test password change view (authenticated user required)
  - [ ] Test password reset flow (all steps)
  - [ ] Test profile view (requires authentication)
  - [ ] Test profile update view (requires authentication, validation)
  - [ ] Test account delete view (requires authentication, confirmation)
  - [ ] Test permission checks (unauthenticated users redirected)
- [ ] Create `tests/test_forms.py`:
  - [ ] Test SignupForm validation (email format, password strength)
  - [ ] Test LoginForm validation
  - [ ] Test PasswordChangeForm validation
  - [ ] Test PasswordResetForm validation
  - [ ] Test ProfileUpdateForm validation
- [ ] Create `tests/test_signals.py`:
  - [ ] Test post-registration signal fires correctly
  - [ ] Test signal handlers execute expected actions
- [ ] Create `tests/test_adapters.py`:
  - [ ] Test `is_open_for_signup()` respects configuration
  - [ ] Test `save_user()` creates users correctly
- [ ] Add integration test: Full signup → login → profile edit → logout flow
- [ ] Run coverage report: Verify 70%+ per file (CI enforced)

**9. Documentation** (User & Developer Guides)
- [ ] Update `README.md` with complete installation instructions:
  - [ ] `quickscale embed --module auth` command
  - [ ] Add `quickscale_modules.auth` to INSTALLED_APPS
  - [ ] Add allauth to INSTALLED_APPS
  - [ ] Required settings.py configuration (AUTHENTICATION_BACKENDS, etc.)
  - [ ] Include `auth.urls` in project URLs
  - [ ] Run migrations: `python manage.py migrate`
- [ ] Document configuration options (signup enabled/disabled, session timeout, etc.)
- [ ] Add usage examples (how to require login, how to customize User model further)
- [ ] Document template customization approach (override templates in project)
- [ ] Add troubleshooting section (common issues, solutions)
- [ ] Link to django-allauth documentation for advanced features

**10. Module Distribution** (Split Branch Integration)
- [ ] Ensure module directory structure matches scaffolding.md §4
- [ ] Verify pyproject.toml has correct package name (`quickscale-module-auth`)
- [ ] Test manual git subtree split: `git subtree split --prefix=quickscale_modules/auth -b splits/auth-module`
- [ ] Verify GitHub Actions workflow will auto-split on release tag
- [ ] Test `quickscale embed --module auth` command in clean test project
- [ ] Verify embedded module works in user project (INSTALLED_APPS, migrations, URLs)

**11. Quality Gates** (Pre-Release Validation)
- [ ] Run `./scripts/lint.sh` - All Ruff checks pass
- [ ] Run `./scripts/test_all.sh` - All tests pass
- [ ] Check coverage report - 70%+ per file achieved
- [ ] Test in generated project: `quickscale init test-auth-project`
- [ ] Embed auth module: `cd test-auth-project && quickscale embed --module auth`
- [ ] Add to INSTALLED_APPS, configure allauth, run migrations
- [ ] Manual smoke test: Signup → Login → Profile Edit → Logout flow works end-to-end
- [ ] Verify templates render correctly in HTML theme
- [ ] Verify form validation works (client-side and server-side)
- [ ] Verify error messages display correctly
- [ ] Test account deletion flow (confirmation, actual deletion)
- [ ] Verify no impact on existing generated projects (backward compatibility)

**Success Criteria** (Acceptance Gates):
- ✅ Module embeds successfully via `quickscale embed --module auth`
- ✅ All authentication flows work: signup, login, logout, password reset, profile management
- ✅ 70%+ test coverage per file (CI enforced)
- ✅ HTML theme templates render correctly and are theme-consistent
- ✅ No breaking changes to existing generated projects
- ✅ Documentation complete (README, installation, usage, troubleshooting)
- ✅ Module distributes correctly via split branch (GitHub Actions workflow)
- ✅ Code quality passes: Ruff format/check, MyPy strict mode
- ✅ Manual QA passes: Full auth flows tested in real generated project

**Deliverables**:
1. Production-ready auth module in `quickscale_modules/auth/`
2. Auto-split branch: `splits/auth-module`
3. Complete test suite (70%+ coverage)
4. HTML theme templates (12+ template files)
5. Updated module README.md
6. Release documentation: `docs/releases/release-v0.63.0-implementation.md`

**Dependencies & Prerequisites**:
- django-allauth (latest stable version)
- Django 4.2+ or 5.0+
- v0.62.0 split branch infrastructure complete
- HTML theme from v0.61.0

**Known Limitations** (Documented in README):
- Social auth providers deferred to v0.64.0
- Email verification deferred to v0.64.0
- HTMX/React themes deferred to v0.67.0/v0.68.0
- 2FA/MFA not included (future release)

---

### **v0.64.0: `quickscale_modules.auth` - Email Verification & Production Email**

**Objective**: Complete production-ready email authentication flows for the auth module. HTML theme only.

**Timeline**: After v0.63.0

**Status**: Planned - Production email features for auth module

**Scope**:
- Email verification templates and flows
- Password reset email templates
- Email delivery/provider configuration
- Deliverability tests

**Implementation Tasks**: TBD - Will be detailed in release planning phase.

---

### **v0.65.0: `quickscale_modules.billing` - Billing Module**

**Objective**: Create reusable billing module wrapping dj-stripe for Stripe subscriptions, plans, pricing tiers, webhook handling, and invoice management. HTML theme only.

**Timeline**: After v0.64.0

**Status**: Detailed implementation plan to be created before starting work.

**Scope**: See [Module Creation Guide](#module-creation-guide-for-v05x0-releases) and [competitive_analysis.md Billing Requirements](../overview/competitive_analysis.md#4-stripe-integration--subscription-management).

**Implementation Tasks**: TBD - Will be detailed in release planning phase.

---

### **v0.66.0: `quickscale_modules.teams` - Teams/Multi-tenancy Module**

**Objective**: Create reusable teams module with multi-tenancy patterns, role-based permissions, invitation system, and row-level security. HTML theme only.

**Timeline**: After v0.65.0

**Status**: 🎯 **SAAS FEATURE PARITY MILESTONE** - At this point QuickScale matches SaaS Pegasus on core features (auth, billing, teams).

**Scope**: See [Module Creation Guide](#module-creation-guide-for-v05x0-releases) and [competitive_analysis.md Teams Requirements](../overview/competitive_analysis.md#6-teammulti-tenancy-pattern).

**Implementation Tasks**: TBD - Will be detailed in release planning phase.

---

### **v0.67.0: HTMX Frontend Theme**

**Objective**: Create HTMX + Alpine.js theme variant and port existing modules (auth, billing, teams) to this theme.

### **v0.67.0: HTMX Frontend Theme**

**Objective**: Create HTMX + Alpine.js theme variant and port existing modules (auth, billing, teams) to this theme.

**Timeline**: After v0.66.0

**Status**: Planned - Second theme variant for server-rendered, low-JS applications

**Scope**:
 - Create `themes/starter_htmx/` directory structure
- HTMX + Alpine.js base templates
- Port auth module components (login, signup, account management)
- Port billing module components (subscription management, pricing pages)
- Port teams module components (team dashboard, invitations, roles)
- Tailwind CSS or similar modern CSS framework
- Progressive enhancement patterns

**Success Criteria**:
 - `quickscale init myproject --theme starter_htmx` generates HTMX-based project
- All existing modules (auth/billing/teams) work with HTMX theme
- Backend code remains unchanged (100% theme-agnostic)
- Documentation includes HTMX theme examples

**Implementation Tasks**: TBD - Will be detailed in release planning phase.

---

### **v0.68.0: React Frontend Theme**

**Objective**: Create React + TypeScript SPA theme variant and port existing modules (auth, billing, teams) to this theme.

**Timeline**: After v0.67.0

**Status**: Planned - Third theme variant for modern SPA applications

**Scope**:
 - Create `themes/starter_react/` directory structure
- React + TypeScript + Vite base setup
- Django REST Framework API endpoints for auth/billing/teams
- Port auth module components (login, signup, account management)
- Port billing module components (subscription management, pricing pages)
- Port teams module components (team dashboard, invitations, roles)
- Modern component library (Shadcn/UI or similar)
- State management (React Query, Zustand, or similar)

**Success Criteria**:
 - `quickscale init myproject --theme starter_react` generates React SPA project
- All existing modules (auth/billing/teams) work with React theme
- Backend code remains unchanged (100% theme-agnostic)
- API endpoints auto-generated or clearly documented
- Documentation includes React theme examples

**Implementation Tasks**: TBD - Will be detailed in release planning phase.

---

### **v0.69.0: `quickscale_modules.notifications` - Notifications Module**

**Objective**: Create reusable notifications module wrapping django-anymail for multiple email backends, transactional templates, and async email via Celery. All 3 themes supported (HTML, HTMX, React).

**Timeline**: After v0.68.0

**Status**: Detailed implementation plan to be created before starting work.

**Scope**: See [Module Creation Guide](#module-creation-guide-for-v05x0-releases) and [competitive_analysis.md Email Requirements](../overview/competitive_analysis.md#8-email-infrastructure--templates).

**Implementation Tasks**: TBD - Will be detailed in release planning phase.

---

### **v0.70.0: Advanced Module Management Features**

**Objective**: Enhance module management with batch operations and advanced features.

**Timeline**: After v0.69.0

**Rationale**: Basic embed/update/push commands implemented in v0.62.0. This release adds convenience features based on real usage patterns.

**Scope**:
- Batch operations: `quickscale update --all` (update all installed modules)
- Status command: `quickscale status` (show installed modules and versions)
- Module discovery: `quickscale list-modules` (show available modules)
- Enhanced conflict resolution workflows
- Improved diff previews and change summaries

**Success Criteria**:
- Batch updates work safely across multiple modules
- Clear status overview of module versions
- Easy discovery of new available modules
- Better UX for handling merge conflicts

**Implementation Tasks**: TBD - Will be detailed in release planning phase.

---

#### **Technical Implementation Notes (v0.62.0 Split Branch Foundation)**

**1. Split Branch Architecture**:

QuickScale monorepo maintains split branches for each module:
```
Branches:
├── main                       # All development happens here
├── splits/auth-module         # Auto-generated from quickscale_modules/auth/
├── splits/billing-module      # Auto-generated from quickscale_modules/billing/
└── splits/teams-module        # Auto-generated from quickscale_modules/teams/
```

**2. GitHub Actions Auto-Split Workflow**:

```yaml
# .github/workflows/split-modules.yml
name: Split Module Branches
on:
  push:
    tags:
      - 'v*'

jobs:
  split:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0  # Full history for split

      - name: Split auth module
        run: |
          git subtree split --prefix=quickscale_modules/auth -b splits/auth-module --rejoin
          git push origin splits/auth-module

      - name: Split billing module
        run: |
          git subtree split --prefix=quickscale_modules/billing -b splits/billing-module --rejoin
          git push origin splits/billing-module
```

**3. Module Configuration Tracking**:

Created in user's project at `.quickscale/config.yml`:
```yaml
# QuickScale module configuration
default_remote: https://github.com/<org>/quickscale.git

# Installed modules
modules:
  auth:
    prefix: modules/auth
    branch: splits/auth-module
    installed_version: v0.62.0
    installed_at: 2025-10-23
  billing:
    prefix: modules/billing
    branch: splits/billing-module
    installed_version: v0.64.0
    installed_at: 2025-10-25
```

**4. Core Commands (Implemented in v0.61.0)**:

`quickscale embed --module auth` - Embed module via split branch
- **Implementation**: `git subtree add --prefix=modules/auth <remote> splits/auth-module --squash`
- **Technical details**:
  - Check if git repository
  - Verify module exists (check remote branch)
  - Verify no existing `modules/auth/` directory
  - Add subtree from split branch
  - Update `.quickscale/config.yml` with module metadata
  - Show success message with INSTALLED_APPS instructions
- **Example**:
```bash
cd myproject/
quickscale embed --module auth
# Output:
# Embedding auth module from splits/auth-module...
# Module installed to: modules/auth/
#
# Next steps:
# 1. Add to INSTALLED_APPS in settings/base.py:
#    INSTALLED_APPS = [..., "modules.auth"]
# 2. Run migrations: python manage.py migrate
```

`quickscale update` - Update all installed modules
- **Implementation**: Read `.quickscale/config.yml`, run `git subtree pull` for each module
- **Technical details**:
  - Read installed modules from config
  - For each module: `git subtree pull --prefix=modules/{name} <remote> splits/{name}-module --squash`
  - Show diff summary before pulling
  - Handle conflicts per module
  - Update version in config
- **Example**:
```bash
cd myproject/
quickscale update
# Output:
# Found 2 installed modules: auth, billing
#
# Updating auth module...
#   - Fixed email verification bug
#   - Added Google OAuth provider
#
# Updating billing module...
#   - Updated Stripe API to latest version
#
# Continue? (y/N):
```

`quickscale push` - Contribute improvements to specific module
- **Implementation**: `git subtree push --prefix=modules/auth <remote> feature/my-improvement`
- **Technical details**:
  - Detect which module has changes
  - Push to feature branch in main repo (not split branch)
  - Maintainer merges to main, auto-split updates split branch
- **Example**:
```bash
cd myproject/
quickscale push --module auth
# Output:
# Detected changes in modules/auth/
# Branch name [feature/auth-improvements]:
# Pushing to https://github.com/<org>/quickscale.git...
#
# Create PR: https://github.com/<org>/quickscale/pull/new/feature/auth-improvements
```

**5. Implementation Structure (v0.61.0)**:

`quickscale_cli/commands/module_commands.py`:
```python
class ModuleEmbedCommand(Command):
    """Embed module via git subtree from split branch."""

    def execute(self, module_name: str, remote: str = None) -> None:
        # 1. Validate git repository
        # 2. Check module exists on remote
        # 3. Verify no existing modules/{module_name}/
        # 4. Verify working directory clean
        # 5. Execute: git subtree add --prefix=modules/{module_name}
        #             {remote} splits/{module_name}-module --squash
        # 6. Update .quickscale/config.yml
        # 7. Show success message with INSTALLED_APPS instructions
```

`quickscale_cli/utils/git_utils.py`:
```python
def is_git_repo() -> bool:
    """Check if current directory is a git repository."""

def is_working_directory_clean() -> bool:
    """Check if there are uncommitted changes."""

def check_remote_branch_exists(remote: str, branch: str) -> bool:
    """Check if branch exists on remote."""

def run_git_subtree_add(prefix: str, remote: str, branch: str) -> None:
    """Execute git subtree add with error handling."""

def run_git_subtree_pull(prefix: str, remote: str, branch: str) -> None:
    """Execute git subtree pull with error handling."""
```

#### **Implementation Tasks (v0.61.0)**

**Module Management Commands**:
- [ ] Implement `quickscale embed --module <name>` command
- [ ] Implement `quickscale update` command (updates installed modules only)
- [ ] Implement `quickscale push --module <name>` command
- [ ] Create `module_commands.py` with embed/update/push logic
- [ ] Create `git_utils.py` with subtree helpers
- [ ] Add `.quickscale/config.yml` configuration tracking
- [ ] Implement safety checks (clean working directory, module exists, etc.)
- [ ] Add interactive confirmation prompts with diff previews

**GitHub Actions - Split Branch Automation**:
- [ ] Create `.github/workflows/split-modules.yml`
- [ ] Auto-split on version tags (v0.*)
- [ ] Split each module: auth, billing, teams, notifications
- [ ] Push splits to `splits/{module}-module` branches
- [ ] Add workflow tests to verify splits work

**Module Safety Features**:
- [ ] Pre-update diff preview (per module)
- [ ] Verify only `modules/*` affected by updates
- [ ] Conflict detection and handling (per module)
- [ ] Rollback/abort functionality
- [ ] Post-update summary of changes

**Documentation**:
- [ ] Update `user_manual.md` with module embed/update workflow
- [ ] Update `decisions.md` CLI Command Matrix (mark v0.61.0 commands as IN)
- [ ] Document split branch architecture
- [ ] Create "Module Management Guide"
- [ ] Document conflict resolution workflow
- [ ] Add troubleshooting for common git issues

**Testing**:
- [ ] Unit tests for module commands (70% coverage per file)
- [ ] Integration tests with test git repositories and split branches
- [ ] E2E test: embed module → update → verify isolation
- [ ] Test conflict scenarios
- [ ] Test error handling (not a git repo, dirty working directory, module doesn't exist)
- [ ] Automated test: verify user's templates/ and project code never modified by module updates

---

### **v0.70.0: Module Workflow Validation & Real-World Testing**

**Objective**: Validate that module updates work safely in real client projects and don't affect user's custom code.

**Timeline**: After v0.69.0

**Rationale**: Module embed/update commands implemented in v0.61.0. This release validates those commands work safely in production after real usage across multiple client projects.

**Success Criteria**:
- Automated tests verify user's `templates/`, `static/`, and project code never modified by module updates
- Module update workflow documented with real project examples
- Safety features prevent accidental code modification
- Rollback procedure documented and tested
- Case studies from 3+ client projects using modules

**Implementation Tasks**:

**Real-World Validation**:
- [ ] Embed modules in 3+ client projects
- [ ] Test module updates across different project structures
- [ ] Document edge cases and conflicts discovered in production
- [ ] Create migration guides for module version upgrades
- [ ] Validate split branch workflow scales with multiple modules

**Safety Validation**:
- [ ] Automated test: verify user's templates/ never modified by module updates
- [ ] Automated test: verify user's static/ never modified by module updates
- [ ] Automated test: verify user's project code never modified by module updates
- [ ] Test module updates don't break custom user modifications
- [ ] Document safe update workflow with real examples

**Testing**:
- [ ] E2E test: embed multiple modules → update → verify isolation
- [ ] Test conflict scenarios (user modified module code) and resolution
- [ ] Test rollback functionality
- [ ] Test module updates across different Django versions
- [ ] Performance testing: update speed with 5+ modules

**Documentation**:
- [ ] Create "Safe Module Updates" guide with screenshots
- [ ] Document conflict resolution workflows with examples
- [ ] Document rollback procedure
- [ ] Create case studies from client projects
- [ ] Add troubleshooting guide for common module update issues

---

### **Pattern Extraction Workflow**

#### **When to Extract a Module**
✅ **Extract when**:
- You've built the same feature 2-3 times across client projects
- The code is stable and battle-tested
- The pattern is genuinely reusable (not client-specific)
- The feature would benefit from centralized updates

❌ **Don't extract when**:
- You've only built it once
- It's highly client-specific
- You're just guessing it might be useful
- The code is still experimental or changing rapidly

#### **Extraction Process**
1. **Identify Reusable Code**: Look for repeated patterns across client projects
2. **Create Module Structure**: `quickscale_modules/<module_name>/` in your monorepo
3. **Extract & Refactor**: Move code, make it generic, add tests
4. **Update Client Projects**: Replace custom code with module via git subtree
5. **Document**: Add module documentation and usage examples

**Git Subtree Commands**: See [decisions.md Git Subtree Workflow](./decisions.md#integration-note-personal-toolkit-git-subtree) for authoritative manual commands.

**Note**: CLI wrapper commands for extraction/sync remain Post-MVP. Evaluate after establishing extraction workflow.

---

### **Module Creation Guide (for v0.5x.0 releases)**

**Don't build these upfront. Build them when you actually need them 2-3 times.**

#### **Prioritized Module Development Sequence** (based on competitive analysis):

**Phase 2 Priorities** (see [competitive_analysis.md Module Roadmap](../overview/competitive_analysis.md#phase-2-post-mvp-v1---saas-essentials)):

1. **🔴 P1: `quickscale_modules.auth`** (First module - split across v0.62.0 and v0.63.0)
   - v0.62.0: Core django-allauth integration with social auth providers (Google, GitHub)
   - v0.62.0: Custom User model patterns and account management views
   - v0.63.0: Production email verification workflows and deliverability
   - **Rationale**: Every SaaS needs auth; Pegasus proves django-allauth is correct choice
   - **Delivery Phasing**: Split to validate module patterns (v0.62.0) then complete production email (v0.63.0)

2. **🔴 P1: `quickscale_modules.billing`** (v0.64.0)
   - Wraps dj-stripe for Stripe subscriptions
   - Plans, pricing tiers, trials
   - Webhook handling with logging
   - Invoice management
   - **Rationale**: Core SaaS monetization; Stripe-only reduces complexity

3. **🔴 P1: `quickscale_modules.teams`** (v0.65.0)
   - Multi-tenancy patterns (User → Team → Resources)
   - Role-based permissions (Owner, Admin, Member)
   - Invitation system with email tokens
   - Row-level security query filters
   - **Rationale**: Most B2B SaaS requires team functionality

4. **🟡 P2: `quickscale_modules.notifications`** (v0.68.0)
   - Wraps django-anymail for multiple email backends
   - Transactional email templates
   - Async email via Celery
   - Email tracking scaffolding

5. **🟡 P2: `quickscale_modules.api`** (Fifth module, if needed)
   - Wraps Django REST framework
   - Authentication patterns
   - Serializer base classes

**Extraction Rule**: Only build after using 2-3 times in real client projects. Don't build speculatively.

**Competitive Context**: This sequence matches successful competitors' feature prioritization while maintaining QuickScale's reusability advantage. See [competitive_analysis.md Strategic Recommendations](../overview/competitive_analysis.md#strategic-recommendations).

#### **Admin Module Scope**

The admin module scope has been defined in [decisions.md Admin Module Scope Definition](./decisions.md#admin-module-scope-definition).

**Summary**: Enhanced Django admin interface with custom views, system configuration, monitoring dashboards, and audit logging. Distinct from auth module (user authentication/authorization).

#### **Module Creation Checklist**:
- [ ] Used successfully in 2-3 client projects
- [ ] Code is stable and well-tested
- [ ] Genuinely reusable (not client-specific hacks)
- [ ] Documented with examples and integration guide
- [ ] Distributed via git subtree to other projects
- [ ] Consider PEP 420 namespace packages if multiple modules exist

**Module Structure Reference**: See [scaffolding.md §4 (Post-MVP Modules)](./scaffolding.md#post-mvp-structure) for canonical package layout.

---

### **Module Management Enhancements (Post v0.69.0 / Future)**

**Note**: Basic module management commands (`quickscale embed --module <name>`, `quickscale update`, `quickscale push`) are implemented in **v0.61.0**. Advanced features planned for **v0.69.0**. This section discusses potential future enhancements beyond v0.69.0.

Based on usage feedback after v0.69.0 implementation, consider these enhancements:

**Future Enhancements** (evaluate after v0.69.0 ships and gets real usage in production):
- [ ] **Module versioning and compatibility**
  - [ ] `quickscale embed --module auth@v0.62.0` - Pin specific module version
  - [ ] Semantic versioning compatibility checks
  - [ ] Automatic migration scripts for breaking changes
- [ ] **Document versioning strategy**
  - [ ] Git tags for stable snapshots (e.g., `core-v0.57.0`)
  - [ ] Semantic versioning for modules
  - [ ] Compatibility tracking between core and modules
- [ ] **Create extraction helper scripts** (optional)

**Success Criteria (example)**: Implement CLI helpers when one or more of the following are true:
- Manual subtree operations exceed 10 instances/month across maintainers OR
- Teams have performed 5+ module extractions manually and report significant time savings from automation.

(Adjust thresholds based on observed usage and community feedback.)
  - [ ] Script to assist moving code from client project to quickscale_modules/
  - [ ] Validation script to check module structure

**Note**: Only build these if the manual workflow becomes a bottleneck. Don't automate prematurely.

---

### **Configuration System Evaluation (potential v0.6x.0 release)**

**After 5+ client projects**, evaluate if YAML config would be useful.

**Questions to answer**:
- Do you find yourself repeating the same Django settings setup?
- Would declarative config speed up project creation?
- Is Django settings inheritance working well enough?
- Would non-developers benefit from YAML-based project config?

**Decision Point**: Add YAML config ONLY if it solves real pain points from MVP usage.

**If pursuing**:
- [ ] Define minimal configuration schema (see [decisions.md illustrative schemas](./decisions.md#architectural-decision-configuration-driven-project-definition))
- [ ] Implement config loader and validator
- [ ] Create CLI commands: `quickscale validate`, `quickscale generate`
- [ ] Update templates to support config-driven generation
- [ ] Document configuration options

---

## **v1.0.0+: Community Platform (Optional Evolution)**

**🎯 Objective**: IF proven successful personally, evolve into community platform.

**Timeline**: 12-18+ months after MVP (or never, if personal toolkit is enough)

**Version Strategy**: Major version (v1.0.0) for community platform features

**Example Release Sequence**:
- **v1.0.0**: PyPI publishing + package distribution
- **v1.1.0**: Theme package system
- **v1.2.0**: Marketplace basics
- **v1.x.0**: Advanced community features

**Prerequisites Before Starting v1.0.0**:
- ✅ 10+ successful client projects built with QuickScale
- ✅ 5+ proven reusable modules extracted
- ✅ Clear evidence that others want to use your patterns
- ✅ Bandwidth to support community and marketplace

### **v1.0.0: Package Distribution**

When you're ready to share with community:

- [ ] **Setup PyPI publishing for modules**
  - [ ] Convert git subtree modules to pip-installable packages
  - [ ] Use PEP 420 implicit namespaces (`quickscale_modules.*`)
  - [ ] Implement semantic versioning and compatibility tracking
  - [ ] Create GitHub Actions for automated publishing
- [ ] **Create private PyPI for commercial modules** (see [commercial.md](../overview/commercial.md))
  - [ ] Set up private package repository
  - [ ] Implement license validation for commercial modules
  - [ ] Create subscription-based access system
- [ ] **Document package creation for community contributors**
  - [ ] Package structure guidelines
  - [ ] Contribution process
  - [ ] Quality standards and testing requirements

---

### **v1.1.0: Theme Package System**

If reusable business logic patterns emerge:

- [ ] **Create theme package structure** (`quickscale_themes.*`)
  - [ ] Define theme interface and base classes
  - [ ] Implement theme inheritance system
  - [ ] Create theme packaging guidelines
- [ ] **Create example themes**
  - [ ] `quickscale_themes.starter` - Basic starter theme
  - [ ] `quickscale_themes.todo` - TODO app example
  - [ ] Document theme customization patterns
- [ ] **Document theme creation guide**
  - [ ] Theme architecture overview
  - [ ] Base model and business logic patterns
  - [ ] Frontend integration guidelines

**Theme Structure Reference**: See [scaffolding.md §4 (Post-MVP Themes)](./scaffolding.md#post-mvp-structure).

---

### **v1.2.0: Marketplace & Community**

Only if there's real demand:

- [ ] **Build package registry/marketplace**
  - [ ] Package discovery and search
  - [ ] Ratings and reviews system
  - [ ] Module/theme compatibility tracking
- [ ] **Create community contribution guidelines**
  - [ ] Code of conduct
  - [ ] Contribution process and standards
  - [ ] Issue and PR templates
- [ ] **Setup extension approval process**
  - [ ] Quality review checklist
  - [ ] Security audit process
  - [ ] Compatibility verification
- [ ] **Build commercial module subscription system**
  - [ ] License management
  - [ ] Payment integration
  - [ ] Customer access control

See [commercial.md](../overview/commercial.md) for detailed commercial distribution strategies.

---

### **v1.3.0: Advanced Configuration**

If YAML config proves useful in Phase 2:

- [ ] **Implement full configuration schema**
  - [ ] Module/theme selection via config
  - [ ] Environment-specific overrides
  - [ ] Customization options
- [ ] **Add module/theme selection via config**
  - [ ] Declarative module dependencies
  - [ ] Theme selection and variants
- [ ] **Create migration tools for config updates**
  - [ ] Schema version migration scripts
  - [ ] Backward compatibility checks
- [ ] **Build configuration validation UI** (optional)
  - [ ] Web-based config editor
  - [ ] Real-time validation
  - [ ] Preview generated project

**IMPORTANT**: v1.0.0+ is OPTIONAL. Many successful solo developers and agencies never need a community platform. Evaluate carefully before investing in marketplace features.

---

### **Appendix: Quick Reference**

### **Key Documents**
- **MVP Scope**: [decisions.md MVP Feature Matrix](./decisions.md#mvp-feature-matrix-authoritative)
- **Git Subtree Workflow**: [decisions.md Integration Note](./decisions.md#integration-note-personal-toolkit-git-subtree)
- **Directory Structures**: [scaffolding.md](./scaffolding.md)
- **Strategic Vision**: [quickscale.md](../overview/quickscale.md#evolution-strategy-personal-toolkit-first)
- **Commercial Models**: [commercial.md](../overview/commercial.md)
- **Release Documentation Policy**: [contributing.md Release Documentation Policy](../contrib/contributing.md#release-documentation-policy)
> For the authoritative Version → Feature mapping and competitive milestone table, see [docs/overview/competitive_analysis.md#version-→-feature-mapping](../overview/competitive_analysis.md#version-%E2%86%92-feature-mapping).

**Maintainers**: Update this roadmap as tasks are completed. Mark completed tasks with ✅. When technical scope changes, update decisions.md first, then update this roadmap to reflect those decisions. Follow the [Release Documentation Policy](../contrib/contributing.md#release-documentation-policy) when archiving completed releases.
