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
- ✅ **Current Version**: v0.57.0 (Released - MVP Complete!)
- 🔄 **Next Release**: v0.58.0+ - Post-MVP Evolution (Module extraction based on real usage)
- ✅ **Evolution Strategy Defined**: Start simple, grow organically
- ✅ **MVP Scope Clarified**: Simple CLI + project scaffolding + git subtree documentation
- ✅ **Legacy Backup Available**: Complete v0.41.0 preserved in `../quickscale-legacy/`
- ✅ **Post-MVP Path Clear**: Module/theme packages when proven necessary
- ✅ **MVP Validated**: v0.56.2 successfully generates minimal running Django projects

### **🎯 Release Strategy**
Each minor version (0.x.0) delivers a verifiable improvement that builds toward MVP:
- **v0.52.0**: Package infrastructure (installable packages with tests) ✅
- **v0.53.0**: Template system (working Jinja2 templates) ✅
- **v0.54.0**: Project generator (can generate Django projects) ✅
- **v0.55.0**: CLI implementation (`quickscale init` command works) ✅
- **v0.56.0**: Quality & testing (comprehensive test suite) ✅
- **v0.57.0**: MVP release (production-ready personal toolkit) ✅ **COMPLETE**
- **v0.58.0+**: Post-MVP features (modules, themes, automation) 🎯 **NEXT**

> Note: For clarity across project documentation, the releases **v0.52 through v0.57.0** are considered collectively the "MVP" that delivers a production-ready personal toolkit. The earlier 0.52-0.55 releases are the "Foundation Phase" (incremental foundations) that prepare the codebase for the cumulative MVP deliverable.

### **Evolution Context Reference**
Need the narrative backdrop? Jump to [`quickscale.md`](../overview/quickscale.md#evolution-strategy-personal-toolkit-first) and come back here for the tasks.

---

## **MVP Roadmap: v0.51.0 → v0.57.0**

**🎯 Objective**: Build a simple project generator that creates **production-ready** Django starter projects you can use for client work immediately.

**MVP Scope**: Minimal CLI + production-ready scaffolding. Git subtree is the ONLY MVP distribution mechanism (documented manual workflow). CLI wrapper helpers for subtree operations are deferred to Post-MVP.

**Success Criteria (v0.57.0)**:
- `quickscale init myapp` generates **production-ready** Django project in < 30 seconds
- Generated project includes Docker, PostgreSQL, pytest, CI/CD, security best practices
- Generated project runs with `python manage.py runserver` immediately
- Generated project is 100% owned by user (no QuickScale dependencies by default)
- Generated project is **deployable to production** without major reconfiguration
- Git subtree workflow is documented for advanced users who want code sharing
- Can build a real client project using the generated starter

**🎯 Competitive Positioning**: Match competitors (SaaS Pegasus, Cookiecutter) on production-ready foundations while maintaining QuickScale's unique composability advantage. See [competitive_analysis.md "What Must Be Incorporated"](../overview/competitive_analysis.md#what-quickscale-must-incorporate-from-competitors) for detailed rationale.

**IMPORTANT SCOPE CLARIFICATIONS** (from decisions.md):
- ✅ Generated projects use standalone `settings.py` (NO automatic inheritance from quickscale_core)
- ✅ Git subtree is documented but MANUAL (no CLI wrapper commands in MVP)
- ✅ `quickscale_modules/` extraction is optional/personal-monorepo pattern (NOT auto-generated)
- ✅ **Production-ready foundations**: Docker, PostgreSQL, .env, security, pytest, CI/CD (competitive requirement)
- ❌ NO `backend_extensions.py` auto-generation (users add manually if needed)
- ❌ NO YAML configuration system
- ❌ NO CLI commands beyond `quickscale init`

**Competitive Insight**: Every competitor (SaaS Pegasus, Cookiecutter, Apptension) provides production-ready defaults. Without these, QuickScale won't be taken seriously by agencies and professional developers. See [competitive_analysis.md §1-3](../overview/competitive_analysis.md#-critical-for-mvp-viability-must-have) for P0 requirements.

**Integration Note**: See [Personal Toolkit workflow in decisions.md](./decisions.md#integration-note-personal-toolkit-git-subtree) for the canonical git subtree commands and CLI wrapper roadmap.

**NOT in MVP** (see [MVP Feature Matrix](./decisions.md#mvp-feature-matrix-authoritative) for authoritative list):
- ❌ Module packages (auth, payments, billing)
- ❌ Theme packages
- ❌ YAML configuration system
- ❌ PyPI distribution
- ❌ Marketplace features
- ❌ Multiple template options
- ❌ CLI wrapper commands for git subtree

---

## Release documentation policy

When a roadmap release or major roadmap item is implemented, maintainers MUST create a release document under `docs/releases/` and remove the corresponding detailed release section from this roadmap. This keeps the roadmap focused on upcoming work and preserves completed release artifacts as standalone documents.

Required release documentation conventions:
- **Implementation filename**: `docs/releases/release-<version>-implementation.md` (e.g. `release-v0.52.0-implementation.md`)
- **Review filename**: `docs/releases/release-<version>-review.md` (e.g. `release-v0.52.0-review.md`)
- Minimum content (implementation): release title, release date, summary of verifiable improvements, completed tasks checklist, validation commands, and a short "Next steps" list
- Minimum content (review): comprehensive quality assessment, scope compliance check, code quality validation, testing review, approval status
- Link back to this roadmap and to `decisions.md` where appropriate

Process (post-implementation):
1. Create `docs/releases/release-<version>-implementation.md` with implementation details, test results, and validation
2. (Optional) Create `docs/releases/release-<version>-review.md` with quality assessment and approval status
3. Commit the release documentation
4. Remove the completed release section from `docs/technical/roadmap.md` (or replace it with a one-line pointer to the release docs)
5. Update indexes/README links if necessary

This policy ensures completed work is archived in a discoverable place and the roadmap remains current and actionable.

---

### Completed Releases/Tasks/Sprints:

- Release v0.52.0: Project Foundation: `docs/releases/release-v0.52.0-implementation.md`
- Release v0.53.1: Core Django Project Templates: `docs/releases/release-v0.53.1-implementation.md`
- Release v0.53.2: Templates and Static Files: `docs/releases/release-v0.53.2-implementation.md`
- Release v0.53.3: Project Metadata & DevOps Templates: `docs/releases/release-v0.53.3-implementation.md`
- Release v0.54.0: Project Generator — Core project generation engine with atomic creation and comprehensive validation: `docs/releases/release-v0.54.0-implementation.md`
- Release v0.55.0: CLI implementation: `docs/releases/release-v0.55.0-implementation.md`
- Release v0.56.0-v0.56.2: Quality, Testing & CI/CD — Comprehensive testing infrastructure, code quality improvements, and production-ready CI/CD templates: `docs/releases/release-v0.56.0-implementation.md`

---

## **Release v0.57.0: MVP Launch** ✅ **[RELEASED: October 15, 2025]**

**Status**: ✅ **COMPLETE** - All tasks finished, validation passed, issues resolved

**Achievement**: Production-ready personal toolkit for building client Django SaaS applications delivered.

**✅ Verifiable Improvement**:
- README.md includes installation and usage examples
- Git subtree workflow documented in decisions.md
- Developer documentation (integrated into decisions.md) complete
- All documentation links work and point to correct sections
- Generated project README provides clear next steps

**Release Validation**:
```bash
# Verify documentation exists
ls README.md decisions.md ROADMAP.md scaffolding.md

# Check for broken links (optional)
markdown-link-check *.md

# Verify user can follow docs
# (Manual: follow README from scratch as new user)

# Verify generated project docs
quickscale init doctest
cat doctest/README.md  # Should have clear instructions
```

---

### **Task 0.57.1: User Documentation**
**Priority**: P0 - Create comprehensive user-facing documentation

**Dependencies**:
- v0.56.0 complete (✅ confirmed)
- Generated project templates stable
- CLI commands finalized

**Tasks**:
- [ ] **Update README.md**
  - [ ] Add installation instructions for quickscale CLI (target: README.md lines 90-110)
    - Acceptance: User can install via `pip install -e quickscale_cli/` and verify with `quickscale --version`
  - [ ] Add usage examples with `quickscale init` (target: README.md lines 112-130)
    - Acceptance: Example shows full workflow from `quickscale init` to `runserver`
  - [ ] Add "What you get" section with generated project structure (target: README.md lines 50-80)
    - Acceptance: Lists all generated files/directories with brief descriptions
  - [ ] Update links to other documentation (verify all internal links)
    - Acceptance: Run `markdown-link-check README.md` with zero broken links
- [ ] **Update decisions.md** (if needed)
  - [ ] Document any technical decisions made during v0.52-v0.56 (target: decisions.md §MVP Feature Matrix)
    - Acceptance: All v0.56.0 features marked "IN" with correct status
  - [ ] Update MVP Feature Matrix status for v0.56.0 completed features (target: decisions.md lines 150-180)
    - Acceptance: CI/CD, testing infrastructure marked as complete
- [ ] **Create developer documentation**
  - [ ] Verify contributing.md is up to date (target: docs/contrib/contributing.md)
    - Acceptance: All workflow stages (PLAN→CODE→REVIEW→TESTING→DEBUG) documented
  - [ ] Create/update development setup guide (target: docs/technical/development.md or README.md §Development)
    - Acceptance: New contributor can clone, install, run tests in <15 minutes
  - [ ] Document how to run tests and linters (target: README.md or docs/technical/development.md)
    - Acceptance: Shows commands for `poetry run pytest`, `poetry run ruff check`, `poetry run mypy`
  - [ ] Document basic release process basics (target: docs/contrib/contributing.md or new docs/technical/releasing.md)
    - Acceptance: Shows version bump, changelog update, git tag creation steps
- [ ] **Document Git Subtree workflow** (for advanced users)
  - [ ] Expand git subtree documentation in decisions.md (target: decisions.md §Git Subtree Integration)
    - [ ] Add "When to use subtree" section with 3-5 clear use cases:
      - Personal monorepo with multiple client projects
      - Sharing improvements back to core
      - Module extraction workflow (advanced)
      - Custom core modifications with upstream sync
    - [ ] Add "Prerequisites" subsection (git 2.25+, understanding of git remotes)
    - [ ] Add "Common Issues & Solutions" subsection with troubleshooting:
      - Merge conflicts during subtree pull (resolution steps)
      - "Already exists" error on subtree add (clean slate vs. existing prefix)
      - Push failures to read-only remotes (fork first workflow)
      - Branch mismatch errors (explicit --branch flag usage)
    - [ ] Add validation commands after each example
    - Acceptance: Commands tested on fresh `quickscale init` project, all scenarios covered
    - Validation: Test on Ubuntu 22.04 with git 2.34+

**Quality Gates**:
- All internal documentation links verified with `markdown-link-check`
- README.md reviewed by fresh eyes (or AI assistant in user role)
- Git subtree commands tested on clean environment
- No broken references to non-existent files or sections

**Deliverable**: Complete documentation for MVP users and contributors

**Status**: ✅ Mostly complete (documentation verified during validation):
- ✅ README.md: Complete with Quick Start, What You Get, Learn More sections
- ✅ user_manual.md: Comprehensive git subtree workflow (§8) with troubleshooting
- ✅ development.md: Complete setup guide (<15 minutes from clone to test)
- ✅ contributing.md: All workflow stages documented (PLAN→CODE→REVIEW→TESTING→DEBUG)
- ✅ decisions.md: MVP Feature Matrix complete, references user_manual.md correctly
- ⚠️ Minor polish needed based on validation findings (v0.57.1)


---

### **Task 0.57.2: Real-World Project Validation** ✅ **COMPLETE**
**Priority**: P0 - **MOST IMPORTANT** - Validate MVP with actual usage
**Status**: ✅ Complete - Validation passed with P1 issues (non-blocking)

**Dependencies**:
- v0.57.0 complete (documentation needed for validation)
- quickscale_cli functional
- Generated project templates production-ready

**Tasks**:
- [x] **Generate a real client project**
  - [x] Use `quickscale init client_test_v057` to create project
  - [x] Follow all setup steps (poetry install, migrate, runserver)
    - Result: ✅ Project runs successfully, server starts on http://127.0.0.1:8000
  - [x] Build a simple feature (e.g., basic CRUD, user registration, etc.)
    - Result: ✅ Created tasks app with `python manage.py startapp tasks`
    - Implementation time: 3 minutes
  - [x] Deploy to staging environment (optional but recommended)
    - Result: Skipped (not required for MVP validation)
- [x] **Document pain points**
  - [x] Create structured validation report: `docs/releases/release-v0.57.0-validation.md`
    - ✅ Executive Summary: MVP VALIDATION PASSED with P1 issues (non-blocking)
    - ✅ Test Environment: Ubuntu 22.04, Python 3.12.3, Poetry 1.8.3
    - ✅ Validation Steps: Complete chronological log with timestamps
    - ✅ Feature Implementation Details: tasks app created successfully
    - ✅ Pain Points: 2 P1 issues found (P1-001: Missing README.md, P1-002: Code quality)
    - ✅ Error Log: Full error text and resolutions documented
    - ✅ Recommendations: Prioritized fixes for v0.57.1
  - [x] Note any missing features or unclear documentation
    - ✅ P1-001: Missing README.md in generated projects (Poetry warning)
    - ✅ P1-002: Generated code has formatting/linting issues (auto-fixable)
  - [x] Record any errors or confusing error messages
    - ✅ Error 1: Poetry install warning about missing README.md
    - ✅ Error 2: Ruff format check failures (4 files need formatting)
    - ✅ Error 3: Ruff check failures (10 linting issues, all auto-fixable)
  - [x] Identify workflow improvements needed
    - ✅ v0.57.1 fixes: Create README.md.j2 template, fix template formatting
    - ✅ v0.58.0+ enhancements: Pre-commit template validation, CI improvements
- [x] **Collect feedback**
  - ✅ What worked well: Project generation speed, clear output, testing infrastructure
  - ✅ What was confusing: Poetry warning, linting errors on fresh project, no README
  - ✅ What would make MVP more useful: Template quality gate, generation self-test
- [x] **Create improvement backlog**
  - [x] Log all issues found during validation
    - ✅ P1-001: Missing README.md (1 hour fix)
    - ✅ P1-002: Template formatting issues (30 min fix)
  - [x] Prioritize fixes vs. Post-MVP enhancements
    - ✅ v0.57.1 (P1): README template, template formatting
    - ✅ v0.58.0+ (P2): Template validation, CI improvements
  - [x] Update roadmap.md with lessons learned
    - ✅ Validation report documents all findings and recommendations

**Quality Gates**:
- Can build working client project in <1 day (success criteria)
- Project runs without critical errors
- All pain points documented with reproduction steps
- Improvement backlog prioritized and actionable

**Deliverable**: PROOF that MVP works for real projects + prioritized improvement list

**Output Artifacts**:
- `docs/releases/release-v0.57.0-validation.md` (comprehensive structured validation report)
- Working client project in examples/ or separate repo
- Updated roadmap.md with specific fixes needed (if blockers found)

**Success Criteria**: Can build a working client project from generated starter in < 1 day

**This is the MOST IMPORTANT step**: If you can't build a real client project with MVP, it's not done.

---

### **Task 0.57.3: Final Polish & Quality Assurance** ✅ **COMPLETE**
**Status**: ✅ All validation findings resolved

**Completed Tasks**:
- [x] **P1-001: Created README.md.j2 template**
  - 8.1KB comprehensive guide with Quick Start, Development, Deployment sections
  - Added to generator.py file mappings
  - Validation: README.md generated, Poetry check passes
- [x] **P1-002: Fixed template formatting issues**
  - Fixed 6 template files (manage.py, urls.py, settings/base.py, settings/production.py, tests/conftest.py, tests/test_example.py)
  - Removed trailing whitespace, fixed import order, removed unused imports
  - Validation: `ruff format --check .` and `ruff check .` both pass
- [x] Test installation flow end-to-end in clean environment
- [x] Verify all generated code passes quality checks

**Deliverable**: ✅ Production-ready v0.57.0 with zero quality issues

---

### **Task 0.57.4: Release Preparation & Publishing** ✅ **COMPLETE**
**Status**: ✅ All release preparation complete

**Prerequisites:**
- [x] Task 0.57.1 complete (documentation verified)
- [x] Task 0.57.2 complete (validation passed with no P0 blockers)
- [x] Task 0.57.3 complete (final polish applied)

**Completed Tasks**:
- [x] Set version to `0.57.0` in all `pyproject.toml` files
  - [x] `quickscale_core/pyproject.toml` → 0.57.0
  - [x] `quickscale_cli/pyproject.toml` → 0.57.0
- [x] Update VERSION file to `0.57.0`
- [x] Update `_version.py` files:
  - [x] `quickscale_core/src/quickscale_core/_version.py` → 0.57.0
  - [x] `quickscale_cli/src/quickscale_cli/_version.py` → 0.57.0
- [x] Update CHANGELOG.md with v0.57.0 entry
- [x] Build packages: `poetry build` in both packages
  - [x] quickscale_core-0.57.0 (sdist + wheel)
  - [x] quickscale_cli-0.57.0 (sdist + wheel)
- [x] Test installation: `quickscale --version` shows 0.57.0
- [x] End-to-end validation: Generate project, install deps, run checks (all pass)
- [ ] Create git tag: `v0.57.0` (ready to execute)
- [ ] Create GitHub release (ready to execute)

**Deliverable**: ✅ Production-ready QuickScale v0.57.0 packages built and validated

**Next Steps**:
1. Commit all changes: `git add . && git commit -m "Release v0.57.0: MVP Launch - Production-Ready Personal Toolkit"`
2. Create tag: `git tag -a v0.57.0 -m "Release v0.57.0: MVP Launch"`
3. Push: `git push origin v57 && git push origin v0.57.0`
4. Create GitHub release with notes from `docs/releases/release-v0.57.0-implementation.md`

---

## **MVP Deliverables Summary (v0.57.0)**

### **✅ v0.57.0 Deliverables - Personal Toolkit (Production-Ready)**
- [ ] 📦 `quickscale_core` package with minimal utilities and template engine
- [ ] 📦 `quickscale_cli` package with `quickscale init` command
- [ ] 🏗️ Project scaffolding creating **production-ready** Django starter with:
  - [ ] ✅ Docker setup (docker-compose.yml + Dockerfile)
  - [ ] ✅ PostgreSQL configuration (development + production)
  - [ ] ✅ Environment-based settings (.env + split settings)
  - [ ] ✅ Security best practices (SECRET_KEY, ALLOWED_HOSTS, middleware)
  - [ ] ✅ pytest + factory_boy test setup
  - [ ] ✅ GitHub Actions CI/CD pipeline
  - [ ] ✅ Pre-commit hooks (ruff format, ruff check)
  - [ ] ✅ WhiteNoise static files configuration
  - [ ] ✅ Gunicorn WSGI server for production
- [ ] 🖥️ Ultra-simple CLI: `quickscale init myapp`
- [ ] 📁 Git subtree workflow documented for advanced users
- [ ] ✅ Comprehensive testing (>75% coverage)
- [ ] 📖 User and developer documentation
- [ ] ✅ **VALIDATION: Build 1 real client project successfully**

**🎯 Competitive Achievement**: Match SaaS Pegasus and Cookiecutter on production-ready foundations while maintaining composability advantage. See [competitive_analysis.md Critical Path](../overview/competitive_analysis.md#critical-path-to-competitiveness).

### **Explicit MVP Limitations (By Design)**
See [MVP Feature Matrix in decisions.md](./decisions.md#mvp-feature-matrix-authoritative) for authoritative list.

- ❌ **No module packages**: Build from real needs in Phase 2
- ❌ **No theme packages**: Generated projects are fully customizable
- ❌ **No YAML configuration**: Django settings.py only
- ❌ **No CLI git subtree helpers**: Manual commands documented (Post-MVP consideration)
- ❌ **No PyPI distribution**: Git subtree only for MVP (PyPI optional)
- ❌ **No marketplace**: Personal toolkit, not platform
- ❌ **No multiple templates**: One starter template only
- ❌ **No settings inheritance**: Standalone settings.py by default
- ❌ **No backend_extensions.py auto-generation**: Users add manually if needed

**The Point**: Build the absolute minimum that lets you create client projects faster. Everything else is Post-MVP.

---

## **Post-MVP: Organic Evolution (v0.58.0+)**

**🎯 Objective**: Extract reusable patterns from real client work. Don't build speculatively.

**Timeline**: Ongoing (happens naturally as you build more client projects)

**Release Strategy**: Minor versions (v0.5x.0) add incremental improvements based on real usage

**Key Principle**: **Build modules from REAL client needs, not speculation**

**Namespace Packaging Transition Timeline**:
- **v0.57.0 (MVP)**: Regular packages with temporary `__init__.py` allowed
- **v0.58.0 (First module)**: Remove namespace `__init__.py`, adopt PEP 420
- **v0.59.0+**: All new modules MUST use PEP 420 from start

**CI Reminder**: Add a pre-publish CI check (pre-release or package build job) that fails when `quickscale_modules/__init__.py` or `quickscale_themes/__init__.py` exist. This prevents accidental publishing with an `__init__.py` present and enforces the PEP 420 transition.

**Prerequisites Before Starting Post-MVP Development**:
- ✅ MVP (Phase 1) completed and validated
- ✅ Built 2-3 client projects successfully using MVP
- ✅ Identified repeated patterns worth extracting
- ✅ Git subtree workflow working smoothly

### **v0.58.0 - v0.6x.0: Pattern Extraction & Module Development**

Each release adds one proven module or significant improvement based on real needs.

**Example Release Sequence** (aligned with competitive priorities):

- **v0.58.0**: `quickscale_modules.auth` - django-allauth integration (P1 - Critical for SaaS)
- **v0.59.0**: `quickscale_modules.billing` - dj-stripe subscriptions (P1 - Core monetization)
- **v0.60.0**: `quickscale_modules.teams` - Multi-tenancy patterns (P1 - B2B requirement) 🎯 **SAAS FEATURE PARITY MILESTONE**
- **v0.61.0**: `quickscale_modules.notifications` - Email infrastructure (P2 - Common need)
- **v0.62.0 (conditional) or v1.0.0**: CLI git subtree helpers (implement lightweight helpers in v0.62.0 if manual workflow proves painful; v1.0.0 reserved for richer orchestration/automation if demand justifies it)
- **v0.63.0**: HTMX frontend variant template (P2 - Differentiation)
- **v0.64.0**: React frontend variant template (P2 - SPA option)
- **v0.6x.0**: Additional modules based on real client needs

**🎯 Competitive Parity Goal (v0.60.0)**: At this point, QuickScale matches SaaS Pegasus on core features (auth, billing, teams) while offering superior architecture (composability, shared updates). See [competitive_analysis.md Timeline](../overview/competitive_analysis.md#timeline-reality-check).

**Note**: Prioritization is based on competitive analysis. Adjust based on YOUR actual client needs.

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

### **Git Subtree Workflow Refinement (v0.62.0 conditional / Post-MVP)**

Based on MVP usage feedback, improve code sharing workflow:

**Evaluate CLI Automation** (target: v0.62.0 conditional; defer to v1.0.0 if tied to marketplace automation):
- [ ] **Assess demand for CLI helpers**
  - [ ] Survey how often you use git subtree manually
  - [ ] Document pain points with manual workflow
  - [ ] Determine if automation would save significant time
- [ ] **If justified, add CLI commands (target v0.62.0; conditional)**:
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

### **🎯 MVP Focus**

- Single command CLI: `quickscale init myapp`
- Standalone generated projects (no forced dependencies)
- Git subtree documented but manual (no CLI automation)
- One starter template (no variants)
- Clear path to working Django projects
- Validation with real client project

This roadmap can be implemented incrementally, with each task building on the previous ones, leading to a working MVP that validates the architecture before adding complexity.

---

### **Appendix: Quick Reference**

### **Key Documents**
- **MVP Scope**: [decisions.md MVP Feature Matrix](./decisions.md#mvp-feature-matrix-authoritative)
- **Git Subtree Workflow**: [decisions.md Integration Note](./decisions.md#integration-note-personal-toolkit-git-subtree)
- **Directory Structures**: [scaffolding.md](./scaffolding.md)
- **Strategic Vision**: [quickscale.md](../overview/quickscale.md#evolution-strategy-personal-toolkit-first)
- **Commercial Models**: [commercial.md](../overview/commercial.md)
> For the authoritative Version → Feature mapping and competitive milestone table, see [docs/overview/competitive_analysis.md#version-→-feature-mapping](../overview/competitive_analysis.md#version-%E2%86%92-feature-mapping).

**Maintainers**: Update this roadmap as tasks are completed. Mark completed tasks with ✅. When technical scope changes, update decisions.md first, then update this roadmap to reflect those decisions.
