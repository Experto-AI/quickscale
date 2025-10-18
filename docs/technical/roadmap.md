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
- ✅ **Current Version**: v0.59.0 (Released - CLI Development Commands)
- 🔄 **Next Release**: v0.60.0 - Railway Deployment Support (`quickscale deploy railway`)
- ✅ **Evolution Strategy Defined**: Start simple, grow organically
- ✅ **MVP Scope Clarified**: Simple CLI + project scaffolding + git subtree documentation
- ✅ **Legacy Backup Available**: Complete v0.41.0 preserved in `../quickscale-legacy/`
- ✅ **Post-MVP Path Clear**: Module/theme packages when proven necessary
- ✅ **MVP Validated**: v0.56.2 successfully generates minimal running Django projects
- ✅ **E2E Infrastructure**: v0.58.0 delivers comprehensive end-to-end testing with PostgreSQL 16 and Playwright
- ✅ **CLI Developer Experience**: v0.59.0 delivers user-friendly Docker/Django command wrappers

### **🎯 Release Strategy**
Each minor version (0.x.0) delivers a verifiable improvement that builds toward MVP:
- **v0.52.0**: Package infrastructure (installable packages with tests) ✅
- **v0.53.0**: Template system (working Jinja2 templates) ✅
- **v0.54.0**: Project generator (can generate Django projects) ✅
- **v0.55.0**: CLI implementation (`quickscale init` command works) ✅
- **v0.56.0**: Quality & testing (comprehensive test suite) ✅
- **v0.57.0**: MVP release (production-ready personal toolkit) ✅
- **v0.58.0**: E2E testing infrastructure (PostgreSQL 16, Playwright, full lifecycle validation) ✅
- **v0.59.0**: CLI development commands (Docker/Django operation wrappers) ✅
- **v0.60.0**: Railway deployment support (`quickscale deploy railway` CLI command) 🎯 **NEXT**
- **v0.61.0+**: Post-MVP features (git subtree helpers, modules, themes)

> Note: For clarity across project documentation, the releases **v0.52 through v0.57.0** are considered collectively the "MVP" that delivers a production-ready personal toolkit. The earlier 0.52-0.55 releases are the "Foundation Phase" (incremental foundations) that prepare the codebase for the cumulative MVP deliverable.

### **Evolution Context Reference**
Need the narrative backdrop? Jump to [`quickscale.md`](../overview/quickscale.md#evolution-strategy-personal-toolkit-first) and come back here for the tasks.

---

## **MVP Roadmap: v0.51.0 → v0.57.0** - ✅ **COMPLETE**

MVP delivered a production-ready Django project generator with Docker, PostgreSQL, pytest, CI/CD, and security best practices. Generated projects are standalone (no forced dependencies) and deployable to production. Git subtree workflow is documented for advanced users.

**For complete MVP details**, see:
- [Release v0.57.0 Implementation](../releases/release-v0.57.0-implementation.md) - MVP launch details
- [decisions.md MVP Feature Matrix](./decisions.md#mvp-feature-matrix-authoritative) - Authoritative scope reference
- [competitive_analysis.md](../overview/competitive_analysis.md) - Competitive positioning rationale

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

---

## **Post-MVP: Organic Evolution (v0.59.0+)**

**🎯 Objective**: Extract reusable patterns from real client work. Don't build speculatively.

**Timeline**: Ongoing (happens naturally as you build more client projects)

**Release Strategy**: Minor versions (v0.5x.0) add incremental improvements based on real usage

**Key Principle**: **Build modules from REAL client needs, not speculation**

**Namespace Packaging Transition Timeline**:
- **v0.57.0 (MVP)**: Regular packages with temporary `__init__.py` allowed
- **v0.58.0 (E2E Testing)**: Quality infrastructure release
- **v0.59.0 (First module)**: Remove namespace `__init__.py`, adopt PEP 420
- **v0.60.0+**: All new modules MUST use PEP 420 from start

**CI Reminder**: Add a pre-publish CI check (pre-release or package build job) that fails when `quickscale_modules/__init__.py` or `quickscale_themes/__init__.py` exist. This prevents accidental publishing with an `__init__.py` present and enforces the PEP 420 transition.

**Prerequisites Before Starting Post-MVP Development**:
- ✅ MVP (Phase 1) completed and validated
- ✅ Built 2-3 client projects successfully using MVP
- ✅ Identified repeated patterns worth extracting
- ✅ Git subtree workflow working smoothly

### **v0.59.0 - v0.6x.0: CLI Usability & Pattern Extraction**

**Priority Shift**: Developer experience (CLI usability) is prerequisite for all future work. Build solid tooling foundation before modules.

**Revised Release Sequence**:

- **v0.59.0**: CLI Development Commands (P0 - Developer Experience) ✅ **COMPLETE** - See `docs/releases/release-v0.59.0-implementation.md`
- **v0.60.0**: Railway Deployment Support - `quickscale deploy railway` (P0 - Production Deployment) 🎯 **CURRENT**
- **v0.61.0**: CLI Git Subtree Wrappers - `quickscale embed/update/push` (P0 - Core Workflow)
- **v0.62.0**: Update Workflow Validation (P0 - Core Workflow)
- **v0.63.0**: `quickscale_modules.auth` - django-allauth integration (P1 - Critical for SaaS)
- **v0.64.0**: `quickscale_modules.billing` - dj-stripe subscriptions (P1 - Core monetization)
- **v0.65.0**: `quickscale_modules.teams` - Multi-tenancy patterns (P1 - B2B requirement) 🎯 **SAAS FEATURE PARITY MILESTONE**
- **v0.66.0**: `quickscale_modules.notifications` - Email infrastructure (P2 - Common need)
- **v0.67.0**: HTMX frontend variant template (P2 - Differentiation)
- **v0.68.0**: React frontend variant template (P2 - SPA option)
- **v0.6x.0**: Additional modules based on real client needs

**🎯 Competitive Parity Goal (v0.65.0)**: At this point, QuickScale matches SaaS Pegasus on core features (auth, billing, teams) while offering superior architecture (composability, shared updates). See [competitive_analysis.md Timeline](../overview/competitive_analysis.md#timeline-reality-check).

**Rationale**: CLI usability improvements (v0.59-v0.62) eliminate manual Docker/git/deployment commands, enabling smooth development workflows and production deployments. This solid developer experience foundation is prerequisite for all future module development.

---

### **v0.59.0: CLI Development Commands** ✅ **COMPLETE**

**Release v0.59.0**: User-friendly CLI commands that replace complex Docker and docker-compose syntax with simple, memorable commands. Delivered 6 new commands (up, down, shell, manage, logs, ps) with 73% test coverage and comprehensive error handling.

**For complete implementation details**, see: `docs/releases/release-v0.59.0-implementation.md`

---

### **v0.60.0: Railway Deployment Support**

**Objective**: Implement `quickscale deploy railway` CLI command to automate Railway deployment, validate with real-world testing, and provide comprehensive documentation.

**Timeline**: After v0.59.0

**Success Criteria**:
- [ ] `quickscale deploy railway` command implemented and functional
- [ ] Successfully deploy QuickScale-generated project to Railway using CLI command
- [ ] Deployment completes in <5 minutes for standard project
- [ ] Database migrations automated and execute successfully via CLI command
- [ ] Static files collection automated and serve correctly via WhiteNoise
- [ ] Environment variable setup streamlined with interactive prompts (user provides ALLOWED_HOSTS only)
- [ ] SECRET_KEY auto-generated using Django's `get_random_secret_key()`
- [ ] CLI detects and uses existing Railway projects correctly (idempotent)
- [ ] Cross-platform support validated (Python-based, tested on Linux/macOS/Windows WSL2)
- [ ] 70% test coverage for new CLI code (railway_utils.py, deployment_commands.py)
- [ ] SSL/HTTPS working out-of-the-box (Railway auto-provisioning verified)
- [ ] Deployment URL displayed and accessible after successful deployment
- [ ] Error messages provide actionable recovery steps for all 16 error scenarios
- [ ] Documentation updated:
  * `railway.md` includes CLI workflow and troubleshooting
  * `user_manual.md` includes deployment section
  * `decisions.md` CLI Command Matrix updated
  * `README.md` Quick Start includes Railway option
  * `release-v0.60.0-implementation.md` created
- [ ] Real deployment evidence captured (screenshots, logs, deployment URL)
- [ ] Railway CLI minimum version documented and validated

#### **Technical Architecture**

Following the same pattern established in v0.59.0 (CLI Development Commands):

**New Files Structure**:
```
quickscale_cli/src/quickscale_cli/
├── commands/
│   └── deployment_commands.py    (NEW - 150-200 lines)
├── utils/
│   └── railway_utils.py          (NEW - 80-100 lines)
└── tests/
    ├── commands/
    │   └── test_deployment_commands.py  (NEW - 200-250 lines)
    └── utils/
        └── test_railway_utils.py         (NEW - 150-200 lines)
```

**Command Interface**:
```bash
# Basic deployment
quickscale deploy railway

# With options
quickscale deploy railway --skip-migrations
quickscale deploy railway --skip-collectstatic
quickscale deploy railway --project-name my-app

# Help
quickscale deploy --help
quickscale deploy railway --help
```

**Implementation Pattern** (same as v0.59.0):
- Click decorators for command registration
- Subprocess for Railway CLI execution
- Color-coded output with click.secho()
- Comprehensive error handling with try/except
- Interactive prompts with click.prompt()
- No complex base classes (keep it simple)

**Railway CLI Interaction**:
```python
# Check if installed
railway --version

# Check authentication
railway whoami

# Set environment variable
railway variables set KEY=value

# Run command in Railway environment
railway run python manage.py migrate

# Deploy
railway up
```

#### **Implementation Tasks**

**Phase 1: Manual Railway Deployment Testing (Foundation)**

**1. Manual Deployment Validation**:
- [ ] Generate fresh QuickScale project using `quickscale init`
- [ ] Manually initialize Railway project (`railway init`)
- [ ] Manually add PostgreSQL database service
- [ ] Manually configure environment variables (SECRET_KEY, ALLOWED_HOSTS, DEBUG, etc.)
- [ ] Manually deploy to Railway (`railway up`)
- [ ] Document all manual steps and pain points
- [ ] Identify which steps should be automated

**2. Deployment Verification**:
- [ ] Verify application starts successfully
- [ ] Test database connectivity and migrations
- [ ] Verify WhiteNoise serves static files correctly
- [ ] Test SSL/HTTPS auto-provisioning
- [ ] Test admin interface access
- [ ] Verify PostgreSQL 16 compatibility
- [ ] Document all issues encountered

**2a. Comprehensive Environment Variable Documentation**:
- [ ] Create `.env.railway.example` with ALL required variables and descriptions
- [ ] Document auto-provided variables (DATABASE_URL, PORT, RAILWAY_ENVIRONMENT)
- [ ] Document user-provided variables (SECRET_KEY, ALLOWED_HOSTS, DEBUG, DJANGO_SETTINGS_MODULE)
- [ ] Document optional variables (SENTRY_DSN, REDIS_URL, etc.)
- [ ] Test deployment with minimal variables vs full configuration

**2b. Deployment Method Testing**:
- [ ] Test Dockerfile deployment (recommended approach)
- [ ] Test Nixpacks deployment (alternative approach)
- [ ] Document build time comparison and trade-offs
- [ ] Test Railway project settings (restart policies, health checks)
- [ ] Document recommended Railway project configuration

**2c. Error Scenario Testing** (intentional failures for documentation):
- [ ] Deploy with missing SECRET_KEY (document error)
- [ ] Deploy with incorrect DATABASE_URL format (document error)
- [ ] Deploy with missing ALLOWED_HOSTS (document error)
- [ ] Deploy with migrations that fail (document rollback)
- [ ] Deploy with collectstatic failure (document recovery)
- [ ] Deploy with health check timeout (document debugging)

**Phase 2: CLI Command Implementation**

**3. Railway Utilities Module**:
- [ ] Create `quickscale_cli/utils/railway_utils.py`
- [ ] Implement `is_railway_cli_installed()` - Check Railway CLI presence
- [ ] Implement `is_railway_authenticated()` - Check Railway login status
- [ ] Implement `check_railway_cli_version(minimum="3.0.0")` - Validate CLI version compatibility
- [ ] Implement `is_railway_project_initialized()` - Check for existing Railway project (.railway directory)
- [ ] Implement `get_railway_services()` - List existing services (detect PostgreSQL)
- [ ] Implement `get_railway_project_info()` - Get current project details (name, environment, region)
- [ ] Implement `set_railway_variable(key, value)` - Set environment variables via Railway CLI
- [ ] Implement `run_railway_command(args)` - Execute Railway CLI with error handling and output capture
- [ ] Implement `wait_for_deployment_complete(timeout=300)` - Poll deployment status until complete or timeout
- [ ] Implement `get_deployment_url()` - Extract deployment URL from Railway API/CLI output
- [ ] Implement `generate_django_secret_key()` - Use `django.core.management.utils.get_random_secret_key()`
- [ ] Add comprehensive docstrings with type hints

**3a. Main CLI Registration**:
- [ ] Update `quickscale_cli/src/quickscale_cli/main.py` - Register `deploy` command group
- [ ] Add `deploy` group with help text: "Deployment commands for production platforms"
- [ ] Register `railway` subcommand under `deploy` group
- [ ] Verify command appears in `quickscale --help` output
- [ ] Follow v0.59.0 pattern for command group registration

**4. Deployment Command Implementation**:
- [ ] Create `quickscale_cli/commands/deployment_commands.py`
- [ ] Implement `deploy` Click group
- [ ] Implement `railway` command with options:
  - [ ] `--skip-migrations` flag
  - [ ] `--skip-collectstatic` flag
  - [ ] `--project-name` option (for Railway project naming)
- [ ] Add Railway CLI installation check
- [ ] Add Railway authentication check
- [ ] Implement interactive environment variable setup
- [ ] Implement automated migrations execution
- [ ] Implement automated collectstatic execution
- [ ] Add deployment status reporting
- [ ] Provide deployment URL after success

**5. Interactive User Experience**:
- [ ] Detect and skip auto-provided variables (DATABASE_URL - Railway provides this)
- [ ] Prompt for required user variables (ALLOWED_HOSTS must include Railway domain)
- [ ] Auto-generate SECRET_KEY using Django's `get_random_secret_key()` (never prompt)
- [ ] Validate environment variable formats before setting (ALLOWED_HOSTS, DEBUG, etc.)
- [ ] Show deployment summary with confirmation:
  * Project name and Railway environment
  * Environment variables being set (mask sensitive values)
  * Services being created (PostgreSQL 16)
  * Estimated deployment time
- [ ] Display real-time deployment progress (build logs, migration status)
- [ ] Color-coded output (green success, red errors, yellow warnings - v0.59.0 pattern)
- [ ] Clear error messages with actionable recovery steps
- [ ] Post-deployment guidance:
  * Display deployment URL
  * Next steps (create superuser, verify admin access)
  * Link to Railway dashboard

**6. Error Handling**:
- [ ] Handle Railway CLI not installed (with installation instructions per platform)
- [ ] Handle Railway CLI version too old (minimum version requirement message)
- [ ] Handle not authenticated to Railway (prompt `railway login`)
- [ ] Handle authentication expired (re-login guidance)
- [ ] Handle Railway project not initialized (auto-initialize or prompt)
- [ ] Handle Railway project name conflicts (suggest alternative names)
- [ ] Handle Railway quota/limit exceeded (upgrade plan guidance)
- [ ] Handle PostgreSQL service already exists (use existing, don't duplicate)
- [ ] Handle Railway command failures (parse error output, provide context)
- [ ] Handle deployment timeout (configurable timeout, progress indication)
- [ ] Handle build failures (Dockerfile errors, dependency issues)
- [ ] Handle migration failures (rollback guidance, database state check)
- [ ] Handle health check failures (log access, debugging tips)
- [ ] Handle network/connectivity issues (retry with exponential backoff)
- [ ] Handle invalid environment variable formats (validation with examples)
- [ ] Handle DATABASE_URL parsing errors (settings configuration check)
- [ ] Provide actionable error messages with recovery steps and documentation links

**Phase 3: Testing**

**7. Unit Tests**:
- [ ] Create `tests/utils/test_railway_utils.py`
- [ ] Test Railway CLI detection
- [ ] Test authentication status checks
- [ ] Test environment variable setting
- [ ] Test command execution with mocked subprocess
- [ ] Achieve 70% coverage for railway_utils.py

**7a. Additional Unit Tests**:
- [ ] Test `generate_django_secret_key()` produces valid 50-character keys
- [ ] Test environment variable format validation (ALLOWED_HOSTS, DEBUG)
- [ ] Test Railway project name validation (length, allowed characters)
- [ ] Test Railway CLI version parsing and comparison
- [ ] Test deployment URL extraction from various Railway output formats

**8. Integration Tests**:
- [ ] Create `tests/commands/test_deployment_commands.py`
- [ ] Test `quickscale deploy railway` command flow
- [ ] Test with --skip-migrations flag
- [ ] Test with --skip-collectstatic flag
- [ ] Test error scenarios (CLI not installed, not authenticated)
- [ ] Test environment variable prompts
- [ ] Achieve 70% coverage for deployment_commands.py

**8a. Additional Integration Tests**:
- [ ] Test idempotency (running deploy twice should not error)
- [ ] Test with existing Railway project (should detect and use, not re-initialize)
- [ ] Test with existing PostgreSQL service (should not duplicate)
- [ ] Test with custom DJANGO_SETTINGS_MODULE environment variable
- [ ] Test partial deployment recovery (if interrupted mid-deployment)

**9. End-to-End Validation**:
- [ ] Deploy test project using `quickscale deploy railway` command
- [ ] Verify all automated steps work correctly
- [ ] Test with different Railway configurations
- [ ] Verify error handling with intentional failures
- [ ] Document any issues discovered

**9a. Cross-Platform E2E Validation**:
- [ ] Test deployment from Linux (primary development platform)
- [ ] Test deployment from macOS (common developer platform)
- [ ] Test deployment from Windows WSL2 (document WSL2 requirement if needed)
- [ ] Test full lifecycle: `quickscale init` → `quickscale deploy railway` → verify → cleanup
- [ ] Test with actual database migrations (add model, deploy, verify schema)
- [ ] Test admin interface access post-deployment
- [ ] Test static file serving via WhiteNoise
- [ ] Test PostgreSQL 16 connection and query execution
- [ ] Document deployment time benchmarks per platform

**Phase 4: Documentation**

**10. Documentation Updates**:
- [ ] Update `docs/deployment/railway.md` (lines 14-34) - Add CLI workflow BEFORE manual workflow
- [ ] Update `docs/deployment/railway.md` (line 149) - Remove "will be validated" note, add validation evidence
- [ ] Add `docs/deployment/railway.md` - CLI command reference with examples
- [ ] Add `docs/deployment/railway.md` - Troubleshooting section with Railway-specific errors:
  * "No available credit" error
  * "Project limit reached" error
  * "Service failed health check" error
  * "Build timeout" error
  * Railway CLI version compatibility issues
- [ ] Create `.env.railway.example` - Template with ALL required environment variables
- [ ] Document Railway CLI installation (npm, brew, scoop) per platform
- [ ] Document environment variable security (SECRET_KEY generation, sensitive data handling)
- [ ] Create deployment workflow diagram (Mermaid or image)
- [ ] Document CLI automation benefits vs manual Railway setup
- [ ] Update `docs/technical/user_manual.md` - Add new section "§X. Deploying to Railway" (after Git Subtree section)
- [ ] Update `docs/technical/decisions.md` (lines 209-212) - Mark `quickscale deploy railway` as IN
- [ ] Update `README.md` Quick Start - Add Railway deployment option
- [ ] Create `docs/releases/release-v0.60.0-implementation.md` - Follow v0.59.0 template structure
- [ ] Document minimum Railway CLI version requirement (3.0.0 or specify based on testing)

**11. Code Quality**:
- [ ] All code passes ruff formatting
- [ ] All code passes ruff linting
- [ ] All code passes mypy type checking
- [ ] Test coverage meets 70% minimum
- [ ] Update decisions.md CLI Command Matrix (mark Railway deployment as IN)

---

### **v0.61.0: CLI Git Subtree Wrappers**

**Objective**: Provide simple CLI wrappers for git subtree workflow, hiding complex git syntax from users.

**Timeline**: After v0.60.0

**Success Criteria**:
- Users never see `git subtree` syntax
- Updates pull only `quickscale_core/` directory changes
- User's `templates/` and `static/` directories never touched by updates
- Clear error messages guide users through git operations
- Safe by default with confirmation prompts

#### **Technical Implementation Notes**

**1. Repository Configuration**:

Create `~/.quickscale/config.yml` for repository settings:
```yaml
# Default QuickScale repository
default_remote: https://github.com/<org>/quickscale.git
default_branch: main

# User's fork (optional)
fork_remote: null
fork_branch: null

# Subtree configuration
subtree_prefix: quickscale_core
squash: true  # Use --squash by default for clean history
```

**2. Git Subtree Commands**:

`quickscale embed` - Embed quickscale_core via git subtree
- **Implementation**: Wrapper for `git subtree add --prefix=quickscale_core <remote> <branch> --squash`
- **Technical details**:
  - Check if current directory is git repository
  - Verify no existing `quickscale_core/` directory
  - Prompt for remote URL (default: official QuickScale repo)
  - Prompt for branch (default: main)
  - Confirm operation before executing
  - Add remote as `quickscale` (for future updates)
  - Show success message with next steps
- **Safety checks**:
  - Working directory must be clean (no uncommitted changes)
  - Must be run from project root
  - Existing files won't be overwritten
- **Example**:
```bash
cd myproject/
quickscale embed
# Prompts:
# Remote URL [https://github.com/<org>/quickscale.git]:
# Branch [main]:
# This will add quickscale_core/ directory. Continue? (y/N):
```

`quickscale update` - Pull latest QuickScale updates
- **Implementation**: Wrapper for `git subtree pull --prefix=quickscale_core <remote> <branch> --squash`
- **Technical details**:
  - Detect existing subtree configuration (from git log)
  - Verify working directory is clean
  - Show diff summary of what will change
  - Confirm before pulling
  - Handle merge conflicts gracefully
  - Show summary of changes after update
- **Safety checks**:
  - Must have existing subtree (from `quickscale embed`)
  - Working directory must be clean
  - Verify only `quickscale_core/` will be affected
- **Conflict handling**:
  - If user modified `quickscale_core/`, show conflict resolution guide
  - Option to abort and stash changes
- **Example**:
```bash
cd myproject/
quickscale update
# Output:
# Fetching updates from QuickScale repository...
# Changes to quickscale_core/:
#   - Improved Docker configuration
#   - Updated security settings template
#   - Bug fixes in generator
#
# Your templates/ and static/ directories will NOT be affected.
# Continue? (y/N):
```

`quickscale push` - Push improvements back to QuickScale
- **Implementation**: Wrapper for `git subtree push --prefix=quickscale_core <remote> <branch>`
- **Technical details**:
  - Verify user has write access to remote
  - Show diff of changes in `quickscale_core/`
  - Prompt for branch name (default: feature/<description>)
  - Push to feature branch (not main)
  - Provide URL to create pull request
- **Safety checks**:
  - Only changes in `quickscale_core/` will be pushed
  - Confirm before pushing
  - Requires authentication to remote
- **Example**:
```bash
cd myproject/
quickscale push
# Output:
# Changes in quickscale_core/:
#   - Fixed typo in template
#   - Improved error message
#
# Branch name [feature/template-fixes]:
# Push to https://github.com/<org>/quickscale.git? (y/N):
#
# Pushed successfully!
# Create pull request: https://github.com/<org>/quickscale/compare/feature/template-fixes
```

**3. Implementation Details**:

`quickscale_cli/commands/subtree_commands.py`:
```python
class EmbedCommand(Command):
    """Embed quickscale_core via git subtree add."""

    def execute(self, remote: str = None, branch: str = "main") -> None:
        # 1. Validate git repository
        if not self._is_git_repo():
            raise ValidationError("Not a git repository")

        # 2. Check for existing subtree
        if self._has_subtree():
            raise ValidationError("quickscale_core already embedded")

        # 3. Verify working directory clean
        if not self._is_working_directory_clean():
            raise ValidationError("Uncommitted changes detected")

        # 4. Get remote URL (prompt if not provided)
        remote = remote or self._prompt_remote()

        # 5. Confirm operation
        if not self._confirm_embed(remote, branch):
            return

        # 6. Execute git subtree add
        self._run_subtree_add(remote, branch)

        # 7. Save configuration
        self._save_subtree_config(remote, branch)

        # 8. Show success message
        self._show_success_message()
```

`quickscale_cli/utils/git_utils.py`:
```python
def is_git_repo() -> bool:
    """Check if current directory is a git repository."""

def is_working_directory_clean() -> bool:
    """Check if there are uncommitted changes."""

def has_subtree(prefix: str) -> bool:
    """Check if subtree exists by examining git log."""

def get_subtree_config(prefix: str) -> dict:
    """Extract subtree remote/branch from git log."""

def run_git_command(args: list) -> subprocess.CompletedProcess:
    """Execute git command with error handling."""
```

#### **Implementation Tasks**

**Git Subtree Wrappers**:
- [ ] Implement `quickscale embed` command
- [ ] Implement `quickscale update` command
- [ ] Implement `quickscale push` command
- [ ] Create `git_utils.py` helpers
- [ ] Add repository configuration (`~/.quickscale/config.yml`)
- [ ] Implement safety checks (clean working directory, etc.)
- [ ] Add interactive confirmation prompts
- [ ] Add unit tests for git operations
- [ ] Add integration tests (with test git repos)

**Update Safety Features**:
- [ ] Pre-update diff preview
- [ ] Verify only `quickscale_core/` affected
- [ ] Conflict detection and handling
- [ ] Rollback/abort functionality
- [ ] Post-update summary of changes

**Documentation**:
- [ ] Update `user_manual.md` with git subtree commands
- [ ] Update `decisions.md` CLI Command Matrix (mark Phase 2 as IN)
- [ ] Create "Safe Updates" guide
- [ ] Document conflict resolution workflow
- [ ] Add troubleshooting for common git issues

**Testing**:
- [ ] Unit tests for subtree commands (70% coverage per file)
- [ ] Integration tests with test git repositories
- [ ] E2E test: embed → update → verify isolation
- [ ] Test conflict scenarios
- [ ] Test error handling (not a git repo, dirty working directory, etc.)
- [ ] Automated test: verify templates/ never modified by update

---

### **v0.62.0: Update Workflow Validation**

**Objective**: Validate that QuickScale updates work safely and don't affect user content.

**Timeline**: After v0.61.0

**Success Criteria**:
- Automated tests verify `templates/` and `static/` never modified by updates
- Update workflow documented with real project examples
- Safety features prevent accidental content modification
- Rollback procedure documented

**Implementation Tasks**:

**Update Safety Validation**:
- [ ] Create test project with custom content
- [ ] Embed quickscale_core using `quickscale embed`
- [ ] Make test improvements to QuickScale monorepo
- [ ] Run `quickscale update` and verify user content unchanged
- [ ] Automated test: verify templates/ never modified by update
- [ ] Automated test: verify static/ never modified by update
- [ ] Document safe update workflow with examples

**Testing**:
- [ ] E2E test: embed → update → verify content isolation
- [ ] Test conflict scenarios and resolution
- [ ] Test rollback functionality
- [ ] Test error handling (dirty working directory, etc.)

**Documentation**:
- [ ] Create "Safe Updates" guide
- [ ] Document update workflow with screenshots
- [ ] Add conflict resolution examples
- [ ] Document rollback procedure

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

1. **🔴 P1: `quickscale_modules.auth`** (First module)
   - Wraps django-allauth with social auth providers
   - Custom User model patterns
   - Email verification workflows
   - Account management views
   - **Rationale**: Every SaaS needs auth; Pegasus proves django-allauth is correct choice

2. **🔴 P1: `quickscale_modules.billing`** (Second module)
   - Wraps dj-stripe for Stripe subscriptions
   - Plans, pricing tiers, trials
   - Webhook handling with logging
   - Invoice management
   - **Rationale**: Core SaaS monetization; Stripe-only reduces complexity

3. **🔴 P1: `quickscale_modules.teams`** (Third module)
   - Multi-tenancy patterns (User → Team → Resources)
   - Role-based permissions (Owner, Admin, Member)
   - Invitation system with email tokens
   - Row-level security query filters
   - **Rationale**: Most B2B SaaS requires team functionality

4. **🟡 P2: `quickscale_modules.notifications`** (Fourth module)
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

### **Git Subtree Workflow Refinement (v0.64.0 conditional / Post-MVP)**

Based on MVP usage feedback, improve code sharing workflow:

**Evaluate CLI Automation** (target: v0.64.0 conditional; defer to v1.0.0 if tied to marketplace automation):
- [ ] **Assess demand for CLI helpers**
  - [ ] Survey how often you use git subtree manually
  - [ ] Document pain points with manual workflow
  - [ ] Determine if automation would save significant time
- [ ] **If justified, add CLI commands (target v0.64.0; conditional)**:
  - [ ] `quickscale embed-core <project>` - Embed quickscale_core via git subtree
  - [ ] `quickscale update-core <project>` - Pull updates from monorepo
  - [ ] `quickscale sync-push <project>` - Push improvements back to monorepo
  - [ ] Update [CLI Command Matrix](./decisions.md#cli-command-matrix) with implementation status
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
