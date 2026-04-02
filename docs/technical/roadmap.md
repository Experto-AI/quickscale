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

1. **Phase 1: Foundation + Core Modules (React Theme Default)** ✅ _Complete_
   - ✅ Theme system infrastructure and split branch management (v0.61.0-v0.62.0)
   - ✅ Auth module (v0.63.0) - production-ready with django-allauth
   - ✅ Listings module (v0.67.0) - generic base for vertical themes
   - ✅ Plan/Apply System core (v0.68.0-v0.70.0) - Terraform-style configuration
   - ✅ **Plan/Apply System complete** (v0.71.0) - Module manifests & config mutability
   - ✅ Plan/Apply Cleanup (v0.72.0) - Remove legacy init/embed commands
   - ✅ CRM module (v0.73.0) - native Django CRM app (API-only)
   - ✅ **React Default Theme** (v0.74.0) - React + shadcn/ui as default
   - ✅ **Forms module** (v0.75.0) - generic form builder with CLI integration ✅ Complete
  - ✅ Storage module (v0.76.0) - cloud file hosting, media storage adapters, CDN integration
  - ✅ Backups module (v0.77.0) - private database backups, optional private remote offload, guarded BackupPolicy-admin local restore plus CLI restore, and scheduler-ready command hooks

2. **Phase 2: Notifications, Vertical Modules & Theme Expansion (Post-MVP)** 🚧 _In Progress_
  - ✅ Notifications module (v0.78.0) - transactional email foundation with app-owned rendering, recipient-granular tracking, and Anymail-backed Resend delivery
  - 🚧 Social & Link Tree module (v0.79.0) - implementation archived; release closeout pending
  - 📋 Listings Theme (v0.80.0) - React frontend for property listings (sell/rent)
  - 📋 CRM Theme (v0.81.0) - React frontend for CRM module
  - 📋 Billing module (v0.82.0) - Stripe integration
  - 📋 Teams module (v0.83.0) - multi-tenancy

3. **Phase 3: Secondary Theme & Cross-Cutting Validation** 📋 _Planned_
  - 📋 HTML theme polish and parity improvements (v0.84.0+) - maintain the server-rendered secondary option alongside the React default
   - HTML theme remains as secondary option (simpler projects)
  - 📋 Advanced module management features (v0.85.0)
  - 📋 Workflow validation and real-world testing (v0.86.0)

4. **Phase 4: Community Platform (Optional v1.0.0+)** 📋 _Future_
   - 📋 PyPI package distribution
   - 📋 Theme package system
   - 📋 Marketplace and community features

**Legend:**
- ✅ = Completed
- 🚧 = In Progress
- 📋 = Planned/Not Started

**Key Milestones:**
- **v0.71.0:** Plan/Apply System Complete ✅
- **v0.72.0:** Plan/Apply Cleanup (remove legacy commands) ✅
- **v0.74.0:** React Default Theme (React + shadcn/ui) ✅
- **v0.75.0:** Forms Module (generic form builder with DRF API, spam protection, GDPR anonymization) ✅
- **v0.76.0:** Storage Module (cloud file hosting + CDN-ready media infrastructure) 🎯
- **v0.77.0:** Backups module (private local + optional private remote workflows, guarded BackupPolicy-admin local restore plus CLI restore) ✅
- **v0.78.0:** Notifications Module (transactional email foundation; app-owned rendering, recipient-granular tracking, and Anymail-backed Resend delivery) ✅
- **v0.79.0:** Social & Link Tree module (implementation archived; reader-facing release summary still pending) 🚧
- **v0.80.0:** Real Estate MVP (static + listings + social links) 🎯
- **v0.83.0:** SaaS Feature Parity (auth, billing, teams, notifications foundation) 🎯
- **v1.0.0+:** Community platform (if demand exists)

**Status:**
- **Current Status:** the published release remains v0.78.0, while main branch now carries the v0.79.0 social-module implementation and is in release-closeout verification
- **In Progress:** v0.79.0 release closeout, reader-facing summary, and release preparation
- **Next Planned Scope After v0.78.0:** v0.79.0 - Social & Link Tree module
- **Next Milestone:** v0.79.0 - Social & Link Tree module
- **Plan/Apply System:** v0.68.0-v0.71.0 - Terraform-style configuration ✅ Complete
- **SaaS Parity:** v0.83.0 - auth, billing, teams modules complete on top of the notifications foundation

## Notes and References

**Target Audience:** Development team, project managers, stakeholders tracking progress

- **Completed Releases:** See [CHANGELOG.md](../../CHANGELOG.md)
- **Release doc layout:** Reader-facing summaries live in [docs/releases/](../releases/) when published; detailed implementation/review artifacts and older records live in [docs/releases-archive/](../releases-archive/)
- **Technical SSOT**: [decisions.md](./decisions.md)
- **Scaffolding SSOT**: [scaffolding.md](./scaffolding.md)
- **Strategic Vision**: [quickscale.md](../overview/quickscale.md)
- **Commercial Models**: [commercial.md](../overview/commercial.md)
- **Release Documentation Policy**: [contributing.md Release Documentation Policy](../contrib/contributing.md#release-documentation-policy)

## ROADMAP

List of upcoming releases with detailed implementation tasks:

---

Release summaries currently exist in [docs/releases/](../releases/) for selected completed releases. Detailed implementation/review artifacts remain in [docs/releases-archive/](../releases-archive/). When a completed release is archived, keep a concise pointer here and move the detailed implementation checklist into the corresponding release documents.

---

### v0.76.0: `quickscale_modules.storage` - Media Storage & CDN Integration Module

**Status**: ✅ Released and archived on 2026-03-21

This release completed QuickScale's shared media-storage milestone: the storage contract now uses `public_base_url` as the single public media URL source, the deprecated `custom_domain` path was removed from module/CLI/planner behavior, and blog uploads plus thumbnails resolve through canonical helper-built URLs.

**Release artifacts**:
- [Reader-facing summary](../releases/release-v0.76.0.md)

**Deferred follow-up**:
- deeper storage upload/write/read integration coverage moved to [v0.86.0](#v0860-module-workflow-validation--real-world-testing)
- Plan → Apply → Blog publish E2E workflow validation with CDN-backed media moved to [v0.86.0](#v0860-module-workflow-validation--real-world-testing)

---

### v0.77.0: `quickscale_modules.backups` - Database Backup & Restore Module

**Status**: ✅ Archived retrospectively on 2026-03-31; hardening continuation archived on 2026-04-01

This completed release now lives outside the active roadmap. The original MVP closeout scope and the detailed PostgreSQL 18 / guarded BackupPolicy-admin restore hardening continuation now live in the implementation archive.

**Release artifacts**:
- [Implementation archive](../releases-archive/release-v0.77.0-implementation.md)

---

### v0.78.0: `quickscale_modules.notifications` - Notifications Module

**Status**: ✅ Released on 2026-03-30

This release starts QuickScale's post-MVP expansion line and ships the notifications module as the new transactional-email foundation. Generated projects now have an opinionated delivery path centered on a read-only operational settings snapshot backed by Django settings and environment variables, app-owned email rendering, recipient-granular delivery tracking, Django email compatibility with the Anymail Resend backend, and signed webhook ingestion for delivery events.

**Release artifacts**:
- [Reader-facing summary](../releases/release-v0.78.0.md)

**Deferred follow-up**:
- inbound or reply workflows, provider-hosted templates, and richer broadcast/newsletter tooling remain deferred to later post-MVP releases
- multi-provider failover and shared async worker extraction remain deferred beyond v0.78.0

---

### v0.79.0: `quickscale_modules.social` - Social & Link Tree Module

**Status**: 🚧 Detailed implementation archived; published release still pending

This implemented release scope now lives outside the active roadmap. The detailed v0.79.0 checklist, support matrix, validation notes, and deferred items now live in the implementation archive, while the published release metadata remains at v0.78.0 until the v0.79.0 reader-facing summary and release cut are completed.

**Release artifacts**:
- [Implementation archive](../releases-archive/release-v0.79.0-implementation.md)

**Current closeout scope**:
- publish the reader-facing v0.79.0 release summary and update release metadata when the release is cut
- keep end-to-end `quickscale plan` → `quickscale apply` → React public-page coverage deferred to [v0.86.0](#v0860-module-workflow-validation--real-world-testing)
- keep provider auth or write APIs, automated sync, analytics, and HTML-theme polish deferred beyond v0.79.0

---

### v0.80.0: Listings Theme (React Frontend for Listings)

**Status**: 📋 Planned

**Strategic Context**: React frontend for property listings (sell & rent), building on the `showcase_react` foundation from v0.74.0 and the Listings module backend from v0.67.0. Prioritized for the Real Estate Agency use case.

**Prerequisites**:
- ✅ Listings Module (v0.67.0)
- ✅ React Default Theme (v0.74.0)

**Theme Features**:
- **Extends**: `showcase_react` base patterns
- **Components**: Property Cards, Search/Filter Bar, Detail View, Image Gallery, Map View
- **API Integration**: Consumes Listings Module REST APIs
- **Listing Types**: Sell and Rent with type-specific filters

**Implementation Tasks**:
- [ ] Listings-specific page layouts (grid, list, map views)
- [ ] Property card component with image, price, type (sell/rent), location
- [ ] Search and filter bar (price range, type, location, bedrooms, etc.)
- [ ] Property detail view with image gallery and contact form
- [ ] Listings dashboard with stats and featured properties
- [ ] Responsive design for mobile property browsing
- [ ] SEO-friendly property pages (meta tags, structured data)

**Testing**:
- [ ] E2E tests: Plan → Apply → Working Listings project
- [ ] Unit tests for filter/search components
- [ ] API integration tests with Listings backend

---

### v0.81.0: CRM Theme (React Frontend for CRM)

**Status**: 📋 Planned

**Strategic Context**: React frontend specifically for the CRM module, building on the `showcase_react` foundation from v0.74.0.

**Prerequisites**:
- ✅ CRM Module (v0.73.0)
- ✅ React Default Theme (v0.74.0)

**Theme Features**:
- **Extends**: `showcase_react` base patterns
- **Components**: Kanban Board, Contact List, Deal Detail View, Pipeline Management
- **API Integration**: Consumes CRM Module REST APIs

**Implementation Tasks**:
- [ ] CRM-specific page layouts
- [ ] Kanban board for deal pipeline
- [ ] Contact and company list views
- [ ] Detail views with inline editing
- [ ] Dashboard with CRM metrics

**Testing**:
- [ ] E2E tests: Plan → Apply → Working CRM project

---

### v0.82.0: `quickscale_modules.billing` - Billing Module

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

### v0.83.0: `quickscale_modules.teams` - Teams/Multi-tenancy Module

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

### Module Showcase Architecture (Deferred to Post-v0.83.0)

**Status**: 🚧 **NOT YET IMPLEMENTED** - Deferred to post-v0.83.0

**Current Reality** (v0.66.0):
- ✅ Basic context processor exists (`quickscale_core/context_processors.py`)
- ❌ Showcase landing page with module cards: **NOT implemented**
- ❌ Module preview pages: **NOT implemented**
- ❌ Showcase CSS styles: **NOT implemented**
- ❌ Current `index.html.j2`: Simple welcome page only

**Why Deferred**:
- Focus on notifications, Plan/Apply system, and core modules first (v0.68-v0.83)
- Showcase architecture provides maximum value when multiple modules exist
- Current simple welcome page is adequate for MVP

**Implementation Plan**: After v0.83.0 (SaaS Feature Parity milestone), evaluate whether to implement showcase architecture or keep simple welcome page. Decision criteria:
- Are 3+ modules complete and production-ready?
- Is module discovery a user pain point?
- Would showcase provide meaningful marketing value?

**If Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation patterns.

---

### v0.84.0+: HTML Secondary Theme Polish (Optional)

**Status**: 📋 Planned (low priority, after SaaS Feature Parity)

**Rationale**: React theme is now the default (v0.74.0). The HTML theme remains the lightweight secondary option for users preferring a simpler server-rendered stack.

**See**: [user_manual.md](../technical/user_manual.md) for current theme architecture and user-facing theme selection guidance.

**When Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation guidance covering the supported React default and HTML secondary theme set.

---

### v0.85.0: Advanced Module Management Features

**Note**: Basic module management commands (`quickscale update`, `quickscale push --module <name>`) are implemented in **v0.62.0**. Plan/Apply system implemented in **v0.68.0-v0.71.0**. This release adds advanced features for managing multiple modules.

**Planner follow-up**: Cross-module planner work now lives directly in the checklist below; there is no separate temporary handoff doc.

**Batch Operations**:
- [ ] Implement `quickscale update --all` command
- [ ] Add batch conflict resolution
- [ ] Create progress indicators for batch operations
- [ ] Implement rollback for failed batch updates

**Status & Discovery**:
- [ ] Expand `quickscale status` to show installed modules, versions, and richer diagnostics
- [ ] Implement `quickscale list-modules` command for available modules
- [ ] Add module version tracking and compatibility checking

**Enhanced UX**:
- [ ] Improve diff previews and summaries
- [ ] Add interactive conflict resolution
- [ ] Implement better error messages and progress indicators

**Planner UX & Cross-Module Configuration**:
- [ ] Generalize interactive per-module configuration so `quickscale plan` can invoke manifest-backed configurators across all supported modules
- [ ] Add dependency-aware planner sequencing for multi-module setups
- [ ] Expand `quickscale plan --reconfigure` into a safe all-modules workflow with merge-preserving updates
- [ ] Add planner regression coverage for mixed module stacks, dependency prompts, and option-retention behavior

**Testing**:
- [ ] Test batch operations with multiple modules
- [ ] Verify status and discovery commands
- [ ] Test conflict resolution workflows
- [ ] E2E testing of enhanced UX features

**Future Enhancements** (v0.86.0+, evaluate after v0.83.0):
- [ ] Module versioning: `quickscale plan --add auth@v0.63.0` - Pin specific module version
- [ ] Semantic versioning compatibility checks
- [ ] Automatic migration scripts for breaking changes
- [ ] Extraction helper scripts (optional, only if manual workflow becomes bottleneck)

**Success Criteria**: Implement advanced features only when:
- Manual subtree operations exceed 10 instances/month across maintainers OR
- Teams have performed 5+ module extractions manually and report significant time savings from automation

---

### v0.86.0: Module Workflow Validation & Real-World Testing

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
- [ ] Storage validation: add upload/write/read integration coverage for local storage and mocked S3-compatible backends
- [ ] Storage/blog workflow validation: add Plan → Apply → Blog publish E2E coverage with CDN-backed media URLs
- [ ] Storage URL regression validation: verify helper-built public media URLs remain canonical across blog rendering and upload flows in real project scaffolds
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
