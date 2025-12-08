# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Timeline & Tasks)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Release Archive](release-archive.md) | [Start Here](../../START_HERE.md)

## General Introduction

**Purpose:** This document outlines the development timeline, implementation phases, and specific tasks for building QuickScale.

**Content Guidelines:**
- Organize tasks by phases with clear deliverables and success criteria
- Include specific implementation tasks with technical requirements
- Provide timeline estimates and dependency relationships
- Track progress and update status as work is completed
- Focus on "when" and "what tasks" rather than "why" or "what"
- Reference other documents for context but avoid duplicating their content

**What to Add Here:**
- New development phases and milestone planning
- Specific implementation tasks and acceptance criteria
- Timeline updates and progress tracking
- Resource allocation and team assignments
- Risk mitigation strategies and contingency plans
- Testing strategies and quality gates

**What NOT to Add Here:**
- Strategic rationale or competitive analysis (belongs in quickscale.md)
- Technical specifications or architectural decisions (belongs in decisions.md)
- User documentation or getting started guides (belongs in README.md)
- Directory structures or scaffolding details (belongs in scaffolding.md)

## Broad Overview of the Roadmap

QuickScale follows an evolution-aligned roadmap that starts as a personal toolkit and potentially evolves into a community platform based on real usage and demand.

**Evolution Strategy:** Personal toolkit first, community platform later. See [quickscale.md](../overview/quickscale.md#evolution-strategy-personal-toolkit-first).


**Roadmap Phases:**

1. **Phase 1: Foundation + Core Modules (Showcase HTML Theme Only)** 🚧 _In Progress_
   - ✅ Theme system infrastructure and split branch management (v0.61.0-v0.62.0)
   - ✅ Auth module (v0.63.0) - production-ready with django-allauth
   - ✅ Listings module (v0.67.0) - generic base for vertical themes
   - ✅ Plan/Apply System core (v0.68.0-v0.70.0) - Terraform-style configuration
   - ✅ **Plan/Apply System complete** (v0.71.0) - Module manifests & config mutability
   - ✅ Plan/Apply Cleanup (v0.72.0) - Remove legacy init/embed commands
   - 📋 CRM module (v0.73.0) - native Django CRM app
   - 📋 CRM Theme (v0.74.0) - React-based theme for CRM
   - 📋 Billing module (v0.75.0) - Stripe integration
   - 📋 Teams module (v0.76.0) - multi-tenancy

2. **Phase 2: Additional Themes (Port Existing Modules)** 📋 _Planned_
   - 📋 HTMX theme with Alpine.js (v0.77.0)
   - 📋 Port all core modules to HTMX theme

3. **Phase 3: Expand Features (All Themes)** 📋 _Planned_
   - 📋 Notifications module with email infrastructure (v0.78.0)
   - 📋 Advanced module management features (v0.79.0)
   - 📋 Workflow validation and real-world testing (v0.80.0)

4. **Phase 4: Community Platform (Optional v1.0.0+)** 📋 _Future_
   - 📋 PyPI package distribution
   - 📋 Theme package system
   - 📋 Marketplace and community features

**Legend:**
- ✅ = Completed
- 🚧 = In Progress
- 📋 = Planned/Not Started

**Key Milestones:**
- **v0.71.0:** Plan/Apply System Complete 🎯
- **v0.72.0:** Plan/Apply Cleanup (remove legacy commands) ✅
- **v0.76.0:** SaaS Feature Parity (auth, billing, teams) 🎯
- **v1.0.0+:** Community platform (if demand exists)

**Status:**
- **Current Status:** v0.72.0 — Plan/Apply Functionality Cleanup ✅ Complete
- **Next Milestone:** v0.73.0 - `quickscale_modules.crm` (CRM Module)
- **Plan/Apply System:** v0.68.0-v0.71.0 - Terraform-style configuration ✅ Complete
- **SaaS Parity:** v0.76.0 - auth, billing, teams modules complete

## Notes and References

**Target Audience:** Development team, project managers, stakeholders tracking progress

- **Completed Releases:** See [CHANGELOG.md](../../CHANGELOG.md)
- **Technical SSOT**: [decisions.md](./decisions.md)
- **Scaffolding SSOT**: [scaffolding.md](./scaffolding.md)
- **Strategic Vision**: [quickscale.md](../overview/quickscale.md)
- **Commercial Models**: [commercial.md](../overview/commercial.md)
- **Release Documentation Policy**: [contributing.md Release Documentation Policy](../contrib/contributing.md#release-documentation-policy)

## ROADMAP

List of upcoming releases with detailed implementation tasks:

---

### v0.73.0: `quickscale_modules.crm` - CRM Module

**Status**: 📋 Planned

**Strategic Context**: Replacing "Real Estate Theme" (pivot). A native Django CRM module providing reusable data structures (Contacts, Deals, Activity). Independent of any frontend theme but includes standard views.

**Core Entities**:
- [ ] **Contacts & Companies**: Core directory functionality (Name, Email, Phone, Related Company)
- [ ] **Pipelines & Deals**: Kanban-ready data structure (Stages, Value, Expected Close Date)
- [ ] **Activity Log**: Generic activity logging (Notes, Calls, Meetings) for any object (using GenericForeignKey or polymorphic)

**Technical Architecture**:
- [ ] **Theme Agnostic**: Provide logical views and HTMX-ready templates, but fully overrideable.
- [ ] **API First**: DRF Serializers for all models to support React/Vue frontends.
- [ ] **Dependencies**: Keep it lightweight (no heavy SvelteKit/Node dependencies like BottleCRM).

**Testing**:
- [ ] Unit tests for CRM models
- [ ] Integration tests for activity logging
- [ ] API tests for all endpoints

---

### v0.74.0: CRM Theme (React)

**Status**: 📋 Planned

**Strategic Context**: Replaces the former "Real Estate Theme". A modern, React-based frontend specifically designed for the CRM module. Demonstrates React + Django integration.

**Prerequisites**:
- ✅ CRM Module (v0.73.0)

**Theme Structure**:
- React + Vite application in `frontend/`
- Consumes CRM Module APIs
- Components: Kanban Board, Contact List, Deal Detail View

**Testing**:
- [ ] E2E tests: Plan -> Apply -> Working CRM project

---

### v0.75.0: `quickscale_modules.billing` - Billing Module

**Status**: 📋 Planned

**Stripe Integration**:
- [ ] Set up dj-stripe for Stripe API integration
- [ ] Configure webhook endpoints for payment events
- [ ] Implement subscription lifecycle management
- [ ] Add payment method handling (cards, etc.)

**Pricing & Plans**:
- [ ] Create pricing tier models and admin
- [ ] Implement plan creation and management
- [ ] Add usage tracking and limits
- [ ] Create pricing page templates

**Subscription Management**:
- [ ] Build subscription dashboard for users
- [ ] Implement plan upgrades/downgrades
- [ ] Add billing history and invoices
- [ ] Create cancellation and pause functionality

**Testing**:
- [ ] Unit tests for billing models and logic
- [ ] Integration tests with Stripe webhooks
- [ ] E2E tests for subscription flows

---

### v0.76.0: `quickscale_modules.teams` - Teams/Multi-tenancy Module

**Status**: 📋 Planned

**Team Management**:
- [ ] Create team and membership models
- [ ] Implement team creation and settings
- [ ] Add member invitation system
- [ ] Build team dashboard interface

**Role-Based Permissions**:
- [ ] Define role hierarchy (Owner, Admin, Member)
- [ ] Implement permission checking decorators
- [ ] Add role assignment and management
- [ ] Create permission-based UI elements

**Multi-Tenancy**:
- [ ] Implement row-level security patterns
- [ ] Add team-scoped data isolation
- [ ] Create tenant-aware querysets
- [ ] Handle cross-team data access

**Testing**:
- [ ] Unit tests for team models and permissions
- [ ] Integration tests for invitation flows
- [ ] E2E tests for multi-tenancy scenarios

---

### Module Showcase Architecture (Deferred to Post-v0.76.0)

**Status**: 🚧 **NOT YET IMPLEMENTED** - Deferred to post-v0.76.0

**Current Reality** (v0.66.0):
- ✅ Basic context processor exists (`quickscale_core/context_processors.py`)
- ❌ Showcase landing page with module cards: **NOT implemented**
- ❌ Module preview pages: **NOT implemented**
- ❌ Showcase CSS styles: **NOT implemented**
- ❌ Current `index.html.j2`: Simple welcome page only

**Why Deferred**:
- Focus on Plan/Apply system and core modules first (v0.68-v0.76)
- Showcase architecture provides maximum value when multiple modules exist
- Current simple welcome page is adequate for MVP

**Implementation Plan**: After v0.76.0 (SaaS Feature Parity milestone), evaluate whether to implement showcase architecture or keep simple welcome page. Decision criteria:
- Are 3+ modules complete and production-ready?
- Is module discovery a user pain point?
- Would showcase provide meaningful marketing value?

**If Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation patterns.

---

### v0.77.0: HTMX Frontend Theme

**Status**: 📋 Planned (after SaaS Feature Parity)

**Rationale**: React theme established via CRM Theme (v0.74.0). HTMX provides alternative for progressive enhancement approach.

**See**: [user_manual.md Theme Selection](../technical/user_manual.md#theme-selection-v0610) for current theme architecture.

**When Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation specifications including HTMX + Alpine.js base templates and progressive enhancement patterns.

---

### v0.78.0: `quickscale_modules.notifications` - Notifications Module

**Status**: 📋 Planned (after SaaS Feature Parity)

**Email Backend Integration**:
- [ ] Set up django-anymail for multiple email providers
- [ ] Configure transactional email templates
- [ ] Implement async email sending with Celery
- [ ] Add email backend failover handling

**Notification System**:
- [ ] Create notification models and admin
- [ ] Implement email template management
- [ ] Add notification scheduling and queuing
- [ ] Create notification dashboard for users

**Multi-Theme Support**:
- [ ] Port notifications to HTML theme
- [ ] Port notifications to HTMX theme (when available)
- [ ] Port notifications to React theme (when available)
- [ ] Ensure theme-agnostic backend code

**Testing**:
- [ ] Unit tests for email sending (70% coverage)
- [ ] Integration tests with email providers
- [ ] Test async processing with Celery
- [ ] Cross-theme compatibility testing

**See**: [competitive_analysis.md Module Roadmap](../overview/competitive_analysis.md#phase-2-post-mvp-v1---saas-essentials) for competitive context.

---

### v0.79.0: Advanced Module Management Features

**Note**: Basic module management commands (`quickscale update`, `quickscale push`) are implemented in **v0.62.0**. Plan/Apply system implemented in **v0.68.0-v0.71.0**. This release adds advanced features for managing multiple modules.

**Batch Operations**:
- [ ] Implement `quickscale update --all` command
- [ ] Add batch conflict resolution
- [ ] Create progress indicators for batch operations
- [ ] Implement rollback for failed batch updates

**Status & Discovery**:
- [ ] Create `quickscale status` command showing installed modules and versions
- [ ] Implement `quickscale list-modules` command for available modules
- [ ] Add module version tracking and compatibility checking

**Enhanced UX**:
- [ ] Improve diff previews and summaries
- [ ] Add interactive conflict resolution
- [ ] Implement better error messages and progress indicators

**Testing**:
- [ ] Test batch operations with multiple modules
- [ ] Verify status and discovery commands
- [ ] Test conflict resolution workflows
- [ ] E2E testing of enhanced UX features

**Future Enhancements** (v0.80.0+, evaluate after v0.76.0):
- [ ] Module versioning: `quickscale plan --add auth@v0.63.0` - Pin specific module version
- [ ] Semantic versioning compatibility checks
- [ ] Automatic migration scripts for breaking changes
- [ ] Extraction helper scripts (optional, only if manual workflow becomes bottleneck)

**Success Criteria**: Implement advanced features only when:
- Manual subtree operations exceed 10 instances/month across maintainers OR
- Teams have performed 5+ module extractions manually and report significant time savings from automation

---

### v0.80.0: Module Workflow Validation & Real-World Testing

**Objective**: Validate that module updates work safely in real client projects and don't affect user's custom code.

**Success Criteria**:
- Automated tests verify user's `templates/`, `static/`, and project code never modified by module updates
- Module update workflow documented with real project examples
- Safety features prevent accidental code modification
- Rollback procedure documented and tested
- Case studies from 3+ client projects using modules

**Implementation Tasks**:
- [ ] Real-world validation: Embed modules in 3+ client projects and document edge cases
- [ ] Safety validation: Automated tests verify user's code never modified by module updates
- [ ] Testing: E2E tests for multi-module workflows, conflict scenarios, and rollback functionality
- [ ] Documentation: Create "Safe Module Updates" guide with screenshots and case studies

**Rationale**: Module embed/update commands implemented in v0.62.0, Plan/Apply system in v0.68.0-v0.71.0. This release validates those systems work safely in production after real usage across multiple client projects.

---

### v1.0.0+: Community Platform (Optional Evolution)

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

#### v1.0.0: Package Distribution

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

#### v1.1.0: Theme Package System

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

#### v1.2.0: Marketplace & Community

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

#### v1.3.0: Advanced Configuration

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
