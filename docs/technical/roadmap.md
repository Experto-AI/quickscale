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
- ✅ **Current Version**: v0.58.0 (Released - E2E Testing Infrastructure)
- 🔄 **Next Release**: v0.59.0+ - Post-MVP Evolution (Module extraction based on real usage)
- ✅ **Evolution Strategy Defined**: Start simple, grow organically
- ✅ **MVP Scope Clarified**: Simple CLI + project scaffolding + git subtree documentation
- ✅ **Legacy Backup Available**: Complete v0.41.0 preserved in `../quickscale-legacy/`
- ✅ **Post-MVP Path Clear**: Module/theme packages when proven necessary
- ✅ **MVP Validated**: v0.56.2 successfully generates minimal running Django projects
- ✅ **E2E Infrastructure**: v0.58.0 delivers comprehensive end-to-end testing with PostgreSQL 16 and Playwright

### **🎯 Release Strategy**
Each minor version (0.x.0) delivers a verifiable improvement that builds toward MVP:
- **v0.52.0**: Package infrastructure (installable packages with tests) ✅
- **v0.53.0**: Template system (working Jinja2 templates) ✅
- **v0.54.0**: Project generator (can generate Django projects) ✅
- **v0.55.0**: CLI implementation (`quickscale init` command works) ✅
- **v0.56.0**: Quality & testing (comprehensive test suite) ✅
- **v0.57.0**: MVP release (production-ready personal toolkit) ✅ 
- **v0.58.0**: E2E testing infrastructure (PostgreSQL 16, Playwright, full lifecycle validation) ✅
- **v0.59.0+**: Post-MVP features (modules, themes, automation) 🎯 **NEXT**

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

### **v0.59.0 - v0.6x.0: Pattern Extraction & Module Development**

Each release adds one proven module or significant improvement based on real needs.

**Example Release Sequence** (aligned with competitive priorities):

- **v0.59.0**: `quickscale_modules.auth` - django-allauth integration (P1 - Critical for SaaS)
- **v0.60.0**: `quickscale_modules.billing` - dj-stripe subscriptions (P1 - Core monetization)
- **v0.61.0**: `quickscale_modules.teams` - Multi-tenancy patterns (P1 - B2B requirement) 🎯 **SAAS FEATURE PARITY MILESTONE**
- **v0.62.0**: `quickscale_modules.notifications` - Email infrastructure (P2 - Common need)
- **v0.63.0 (conditional) or v1.0.0**: CLI git subtree helpers (implement lightweight helpers in v0.63.0 if manual workflow proves painful; v1.0.0 reserved for richer orchestration/automation if demand justifies it)
- **v0.64.0**: HTMX frontend variant template (P2 - Differentiation)
- **v0.65.0**: React frontend variant template (P2 - SPA option)
- **v0.6x.0**: Additional modules based on real client needs

**🎯 Competitive Parity Goal (v0.61.0)**: At this point, QuickScale matches SaaS Pegasus on core features (auth, billing, teams) while offering superior architecture (composability, shared updates). See [competitive_analysis.md Timeline](../overview/competitive_analysis.md#timeline-reality-check).

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

### **Git Subtree Workflow Refinement (v0.63.0 conditional / Post-MVP)**

Based on MVP usage feedback, improve code sharing workflow:

**Evaluate CLI Automation** (target: v0.63.0 conditional; defer to v1.0.0 if tied to marketplace automation):
- [ ] **Assess demand for CLI helpers**
  - [ ] Survey how often you use git subtree manually
  - [ ] Document pain points with manual workflow
  - [ ] Determine if automation would save significant time
- [ ] **If justified, add CLI commands (target v0.63.0; conditional)**:
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
