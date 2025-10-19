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
- ✅ **Current Version**: v0.60.0 (Released - Railway Deployment Support)
- 🔄 **Next Release**: v0.61.0 - CLI Git Subtree Wrappers (`quickscale embed/update/push`)

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

---

### Revised Next Release Sequence:

- **v0.61.0**: CLI Git Subtree Wrappers - `quickscale embed/update/push` (P0 - Core Workflow) 🎯 **NEXT**
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
