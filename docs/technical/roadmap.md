# QuickScale Development Roadmap

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
   - 📋 Real Estate theme (v0.73.0) - first vertical theme (React-based)
   - 📋 Billing module (v0.74.0) - Stripe integration
   - 📋 Teams module (v0.75.0) - multi-tenancy

2. **Phase 2: Additional Themes (Port Existing Modules)** 📋 _Planned_
   - 📋 HTMX theme with Alpine.js (v0.76.0)
   - 📋 Port all core modules to HTMX theme

3. **Phase 3: Expand Features (All Themes)** 📋 _Planned_
   - 📋 Notifications module with email infrastructure (v0.77.0)
   - 📋 Advanced module management features (v0.78.0)
   - 📋 Workflow validation and real-world testing (v0.79.0)

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
- **v0.75.0:** SaaS Feature Parity (auth, billing, teams) 🎯
- **v1.0.0+:** Community platform (if demand exists)

**Status:**
- **Current Status:** v0.72.0 — Plan/Apply Functionality Cleanup ✅ Complete
- **Next Milestone:** v0.73.0 - Real Estate Theme (React-based)
- **Plan/Apply System:** v0.68.0-v0.71.0 - Terraform-style configuration ✅ Complete
- **SaaS Parity:** v0.75.0 - auth, billing, teams modules complete

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

### v0.67.0: Listings Module — ✅ Complete

See [release-v0.67.0-implementation.md](../releases/release-v0.67.0-implementation.md) for details.

---

### v0.68.0: Plan/Apply System — Core Commands

**Status**: ✅ Complete

See [release-v0.68.0-implementation.md](../releases/release-v0.68.0-implementation.md) for details.

---

### v0.69.0: Plan/Apply System — State Management

**Status**: ✅ Complete

Terraform-style state management with incremental applies. See [release-v0.69.0-implementation.md](../releases/release-v0.69.0-implementation.md).

---

### v0.70.0: Plan/Apply System - Existing Project Support

**Status**: ✅ Complete — 2025-12-19

Release v0.70.0 adds existing project support to the Plan/Apply system. Users can now check project status, add modules, and reconfigure options. New commands: `quickscale status`, `quickscale plan --add`, `quickscale plan --reconfigure`. Includes 37 new tests and full state management integration.

See [release-v0.70.0-implementation.md](../releases/release-v0.70.0-implementation.md) for details.

---

### v0.71.0: Plan/Apply System - Module Manifests & Config Mutability

**Status**: ✅ Complete — 2025-12-04

Release v0.71.0 completes the Plan/Apply system (v0.68.0-v0.71.0) with module manifests enabling configuration mutability. Users can now modify mutable configuration options after initial embed without re-embedding, while immutable options are locked at embed time with clear upgrade guidance. Includes `quickscale remove` command for module removal. Auth module updated with manifest. 643 tests passing, full coverage achieved.

See [release-v0.71.0-implementation.md](../releases/release-v0.71.0-implementation.md) and [decisions.md: Module Manifest Architecture](./decisions.md#module-manifest-architecture).

---

### v0.72.0: Plan/Apply Functionality Cleanup — ✅ Complete

**Status**: ✅ Complete

**Strategic Context**: Completed transition to Plan/Apply workflow by removing legacy `init` and `embed` commands entirely. Cleaned up all related code and updated documentation to use only the modern workflow.

**Prerequisites**:
- ✅ Plan/Apply system complete (v0.68.0-v0.71.0)
- ✅ All modules support Plan/Apply workflow

**CLI Cleanup Tasks**:
- [x] Remove `init` command entirely (was `InitCommand` class in main.py)
- [x] Remove `embed` CLI command (converted to internal `embed_module()` function in `module_commands.py`)
- [x] Update command registrations in `quickscale_cli/src/quickscale_cli/main.py`
- [x] Update `apply_command.py` to call `embed_module()` directly instead of subprocess
- [x] Clean up unused imports and dead code paths

**Documentation Updates**:
- [x] Update `docs/technical/user_manual.md`: Remove init/embed command sections, update to plan/apply workflow
- [x] Update `docs/technical/decisions.md`: Update MVP Feature Matrix, CLI Commands section
- [x] Update `docs/deployment/railway.md`: Replace all `quickscale init` with plan/apply workflow
- [x] Update `docs/contrib/testing.md`: Update testing examples
- [x] Update `docs/contrib/shared/testing_standards.md`: Update testing examples

**Test Updates**:
- [x] Remove `test_init_themes.py` (tests for removed init command)
- [x] Remove `test_embed_command.py` (tests for removed embed command)
- [x] Update `test_cli.py` to verify removed commands return "No such command"
- [x] Fix `conftest.py` mock that was patching removed import
- [x] All 377 CLI tests pass

**Acceptance Criteria**:
- ✅ `quickscale init` returns "No such command"
- ✅ `quickscale embed` returns "No such command"
- ✅ `quickscale --help` shows only: plan, apply, up, down, shell, manage, logs, ps, update, push, remove, status, deploy
- ✅ All documentation references plan/apply workflow exclusively
- ✅ No deprecation warning code remains in codebase
- ✅ All tests pass

---

### v0.73.0: Real Estate Theme (React-based)

**Status**: 📋 Planned

**Strategic Context**: First vertical theme demonstrating React + Django integration. Uses `quickscale plan`/`quickscale apply` workflow and embeds listings module automatically. Serves as the React theme implementation.

**Prerequisites**:
- ✅ Listings module (v0.67.0)
- ✅ Plan/Apply system (v0.68.0-v0.72.0)

**Theme Structure** (in `quickscale_core/generator/templates/themes/real_estate/`):
```
real_estate/
├── frontend/                    # React + Vite application
│   ├── src/
│   │   ├── components/          # Property cards, filters, gallery
│   │   ├── pages/               # PropertyList, PropertyDetail
│   │   ├── api/                 # API client for Django backend
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
├── templates/                   # Django templates (minimal, React entry point)
├── api/                         # Django REST Framework endpoints
│   ├── serializers.py.j2
│   ├── views.py.j2
│   └── urls.py.j2
├── models.py.j2                 # Property model extending AbstractListing
├── views.py.j2                  # Property views (API + template)
├── urls.py.j2                   # URL patterns
├── admin.py.j2                  # Property admin configuration
└── README.md                    # Theme documentation
```

**Backend Tasks**:
- [ ] `models.py.j2` — `Property` model extending `AbstractListing` (bedrooms, bathrooms, sqft, property_type, amenities)
- [ ] `api/serializers.py.j2` — PropertySerializer with nested images, filtering support
- [ ] `api/views.py.j2` — PropertyViewSet with filtering, pagination, search
- [ ] `api/urls.py.j2` — REST API URL patterns
- [ ] `admin.py.j2` — Property admin with inline images, map preview

**Frontend Tasks**:
- [ ] `frontend/src/components/PropertyCard.tsx` — Property card with image, price, details
- [ ] `frontend/src/components/PropertyFilters.tsx` — Price range, bedrooms, property type filters
- [ ] `frontend/src/components/PropertyGallery.tsx` — Image gallery with lightbox
- [ ] `frontend/src/pages/PropertyList.tsx` — Paginated property grid with filters
- [ ] `frontend/src/pages/PropertyDetail.tsx` — Full property details with gallery
- [ ] `frontend/src/api/client.ts` — API client for Django REST endpoints
- [ ] `frontend/package.json` — Dependencies (React, Vite, axios, etc.)
- [ ] `frontend/vite.config.ts` — Vite configuration for Django integration

**Plan/Apply Integration**:
- [ ] Add `real_estate` to theme choices in plan wizard
- [ ] Auto-embed listings module when real_estate theme selected
- [ ] Configure default module options for real estate use case
- [ ] Generate working React + Django project via `quickscale apply`

**Acceptance Criteria**:
- `quickscale plan myrealestate` → select `real_estate` theme → `quickscale apply` generates working project
- Property model successfully extends AbstractListing from listings module
- React frontend communicates with Django API
- Property list supports filtering by price, bedrooms, property type
- Image gallery works with multiple property images
- Development server runs both Django and Vite dev server

**Testing**:
- [ ] Unit tests for Property model and serializers
- [ ] API tests for PropertyViewSet endpoints
- [ ] E2E test: plan → apply → working real estate application

**Quality Gates**:
- `./scripts/lint.sh` passes
- Generated project runs successfully with `quickscale up`
- React frontend builds without errors

---

### v0.74.0: `quickscale_modules.billing` - Billing Module

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

### v0.75.0: `quickscale_modules.teams` - Teams/Multi-tenancy Module

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

### Module Showcase Architecture (Deferred to Post-v0.75.0)

**Status**: 🚧 **NOT YET IMPLEMENTED** - Deferred to post-v0.75.0

**Current Reality** (v0.66.0):
- ✅ Basic context processor exists (`quickscale_core/context_processors.py`)
- ❌ Showcase landing page with module cards: **NOT implemented**
- ❌ Module preview pages: **NOT implemented**
- ❌ Showcase CSS styles: **NOT implemented**
- ❌ Current `index.html.j2`: Simple welcome page only

**Why Deferred**:
- Focus on Plan/Apply system and core modules first (v0.68-v0.75)
- Showcase architecture provides maximum value when multiple modules exist
- Current simple welcome page is adequate for MVP

**Implementation Plan**: After v0.75.0 (SaaS Feature Parity milestone), evaluate whether to implement showcase architecture or keep simple welcome page. Decision criteria:
- Are 3+ modules complete and production-ready?
- Is module discovery a user pain point?
- Would showcase provide meaningful marketing value?

**If Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation patterns.

---

### v0.76.0: HTMX Frontend Theme

**Status**: 📋 Planned (after SaaS Feature Parity)

**Rationale**: React theme established via Real Estate theme (v0.73.0). HTMX provides alternative for progressive enhancement approach.

**See**: [user_manual.md Theme Selection](../technical/user_manual.md#theme-selection-v0610) for current theme architecture.

**When Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation specifications including HTMX + Alpine.js base templates and progressive enhancement patterns.

---

### v0.77.0: `quickscale_modules.notifications` - Notifications Module

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

### v0.78.0: Advanced Module Management Features

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

**Future Enhancements** (v0.79.0+, evaluate after v0.75.0):
- [ ] Module versioning: `quickscale plan --add auth@v0.63.0` - Pin specific module version
- [ ] Semantic versioning compatibility checks
- [ ] Automatic migration scripts for breaking changes
- [ ] Extraction helper scripts (optional, only if manual workflow becomes bottleneck)

**Success Criteria**: Implement advanced features only when:
- Manual subtree operations exceed 10 instances/month across maintainers OR
- Teams have performed 5+ module extractions manually and report significant time savings from automation

---

### v0.79.0: Module Workflow Validation & Real-World Testing

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
