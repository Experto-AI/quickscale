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

1. **Phase 1: Foundation + Core Modules (Showcase HTML Theme Only)**
   - Theme system infrastructure and split branch management
   - Core modules: auth, blog, billing, teams
   - Showcase architecture for module discovery

2. **Phase 2: Additional Themes (Port Existing Modules)**
   - HTMX theme with Alpine.js
   - React theme with TypeScript SPA
   - Port all core modules to new themes

3. **Phase 3: Expand Features (All Themes)**
   - Notifications module with email infrastructure
   - Advanced module management features
   - Workflow validation and real-world testing

4. **Phase 4: Community Platform (Optional v1.0.0+)**
   - PyPI package distribution
   - Theme package system
   - Marketplace and community features

**Key Milestones:**
- **v0.69.0:** SaaS Feature Parity (auth, billing, teams) 🎯
- **v1.0.0+:** Community platform (if demand exists)

---

## Module Showcase Architecture (Deferred to Post-v0.69.0)

**Status**: 🚧 **NOT YET IMPLEMENTED** - Deferred to post-v0.69.0

**Current Reality** (v0.66.0):
- ✅ Basic context processor exists (`quickscale_core/context_processors.py`)
- ❌ Showcase landing page with module cards: **NOT implemented**
- ❌ Module preview pages: **NOT implemented**
- ❌ Showcase CSS styles: **NOT implemented**
- ❌ Current `index.html.j2`: Simple welcome page only

**Why Deferred**:
- Focus on completing auth, billing, teams modules first (v0.66-v0.69)
- Showcase architecture provides maximum value when multiple modules exist
- Current simple welcome page is adequate for MVP

**Implementation Plan**: After v0.69.0 (SaaS Feature Parity milestone), evaluate whether to implement showcase architecture or keep simple welcome page. Decision criteria:
- Are 3+ modules complete and production-ready?
- Is module discovery a user pain point?
- Would showcase provide meaningful marketing value?

**If Implemented**: See [decisions.md: Module Showcase Pattern](./decisions.md#module-showcase-pattern) for detailed specifications (module cards, preview pages, CSS styles, integration checklist).

---

## Notes and References

**Target Audience:** Development team, project managers, stakeholders tracking progress

- **Previous Releases:** [release notes](./releases.md).
- **Technical SSOT**: [decisions.md](./decisions.md)
- **Scaffolding SSOT**: [scaffolding.md](./scaffolding.md)
- **Strategic Vision**: [quickscale.md](../overview/quickscale.md)
- **Commercial Models**: [commercial.md](../overview/commercial.md)
- **Release Documentation Policy**: [contributing.md Release Documentation Policy](../contrib/contributing.md#release-documentation-policy)

## ROADMAP

**Current Status:** v0.66.0 (In Development) — Blog module with Wagtail CMS integration.
**Next Milestone:** v0.69.0 - SaaS Feature Parity (auth, billing, teams modules complete)
**Completed Releases:** v0.61.0-v0.65.0 (Module management, git subtree automation, auth module)

### v0.66.0: Blog Module (`quickscale_modules.blog`) — IN DEVELOPMENT

**Status**: 🚧 In Development

**Blog Module Development**:
- [ ] Integrate Wagtail CMS for blog functionality
- [ ] Create blog models (Post, Category, Tag, Author)
- [ ] Implement blog views and URL routing
- [ ] Design blog templates for showcase_html theme
- [ ] Add rich text editor integration
- [ ] Implement image handling and media management

**Module Configuration**:
- [ ] Add interactive prompts for blog configuration during embed
- [ ] Configure blog settings (posts per page, comment system, etc.)
- [ ] Add blog URLs to generated project
- [ ] Create initial blog migrations

**Testing**:
- [ ] Unit tests for blog models and views (70% coverage)
- [ ] Integration tests for Wagtail integration
- [ ] E2E tests for blog creation and publishing workflows

**Documentation**:
- [ ] Create blog module README with features and setup
- [ ] Document blog configuration options
- [ ] Add blog module to user manual
- [ ] Create blog customization guide

---

### v0.67.0: HTMX Frontend Theme (Deferred)

**Status**: Deferred to post-v0.69.0 (after SaaS Feature Parity)

**Rationale**: Focus on completing core modules (auth, billing, teams) before adding new themes.

**See**: [user_manual.md Theme Selection](../technical/user_manual.md#theme-selection-v0610) for current theme architecture.

**When Implemented**, tasks will include:
- HTMX + Alpine.js base templates
- Port auth, billing, teams modules to HTMX
- Progressive enhancement patterns

---

### v0.68.0: `quickscale_modules.billing` - Billing Module

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

### v0.69.0: `quickscale_modules.teams` - Teams/Multi-tenancy Module

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

### v0.70.0: HTMX Frontend Theme (Deferred)

**Status**: Deferred to post-v0.69.0 (after SaaS Feature Parity)

**Rationale**: Focus on completing core modules (auth, billing, teams) before adding new themes.

**See**: [user_manual.md Theme Selection](../technical/user_manual.md#theme-selection-v0610) for current theme architecture.

**When Implemented**, tasks will include:
- HTMX + Alpine.js base templates
- Port auth, billing, teams modules to HTMX
- Progressive enhancement patterns

---

### v0.71.0: React Frontend Theme (Deferred)

**Status**: Deferred to post-v0.69.0 (after SaaS Feature Parity)

**Rationale**: Focus on completing core modules (auth, billing, teams) before adding new themes.

**See**: [user_manual.md Theme Selection](../technical/user_manual.md#theme-selection-v0610) for current theme architecture.

**When Implemented**, tasks will include:
- React + TypeScript + Vite setup
- Django REST Framework API endpoints
- Port auth, billing, teams modules to React
- Responsive React interfaces

---

### v0.72.0: `quickscale_modules.notifications` - Notifications Module (Deferred)

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
- [ ] Port notifications to HTMX theme
- [ ] Port notifications to React theme
- [ ] Ensure theme-agnostic backend code

**Testing**:
- [ ] Unit tests for email sending
- [ ] Integration tests with email providers
- [ ] Test async processing with Celery
- [ ] Cross-theme compatibility testing

---

### v0.73.0: Advanced Module Management Features

**Batch Operations**:
- [ ] Implement `quickscale update --all` command
- [ ] Add batch conflict resolution
- [ ] Create progress indicators for batch operations
- [ ] Implement rollback for failed batch updates

**Status & Discovery**:
- [ ] Create `quickscale status` command
- [ ] Implement `quickscale list-modules` command
- [ ] Add module version tracking
- [ ] Create module compatibility checking

**Enhanced UX**:
- [ ] Improve diff previews and summaries
- [ ] Add interactive conflict resolution
- [ ] Implement better error messages
- [ ] Create progress bars and status updates

**Testing**:
- [ ] Test batch operations with multiple modules
- [ ] Verify status and discovery commands
- [ ] Test conflict resolution workflows
- [ ] E2E testing of enhanced UX features

---

### v0.74.0: Module Workflow Validation & Real-World Testing

**Objective**: Validate that module updates work safely in real client projects and don't affect user's custom code.

**Timeline**: After v0.73.0 (advanced module management)

**Rationale**: Module embed/update commands implemented in v0.62.0. This release validates those commands work safely in production after real usage across multiple client projects.

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

#### Pattern Extraction Workflow

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

#### Module Creation Guide (for v0.5x.0 releases)

**Don't build these upfront. Build them when you actually need them 2-3 times.**

#### **Prioritized Module Development Sequence** (based on competitive analysis):

**Phase 2 Priorities** (see [competitive_analysis.md Module Roadmap](../overview/competitive_analysis.md#phase-2-post-mvp-v1---saas-essentials)):

1. **🔴 P1: `quickscale_modules.auth`** (First module - core features only)
  - v0.65.0: Core django-allauth integration (email/password auth only)
  - v0.65.0: Custom User model patterns and account management views
  - post-v0.65.0: Production email verification workflows and deliverability
  - **Rationale**: Every SaaS needs auth; Pegasus proves django-allauth is correct choice
  - **Delivery Phasing**: Validate basic auth patterns (v0.65.0) then add email (post-v0.65.0)

2. **🔴 P1: `quickscale_modules.billing`** (v0.64.0)
   - Wraps dj-stripe for Stripe subscriptions
   - Plans, pricing tiers, trials
   - Webhook handling with logging
   - Invoice management
   - **Rationale**: Core SaaS monetization; Stripe-only reduces complexity

3. **🔴 P1: `quickscale_modules.teams`** (v0.69.0)
   - Multi-tenancy patterns (User → Team → Resources)
   - Role-based permissions (Owner, Admin, Member)
   - Invitation system with email tokens
   - Row-level security query filters
   - **Rationale**: Most B2B SaaS requires team functionality

4. **🟡 P2: `quickscale_modules.notifications`** (v0.72.0)
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

#### Module Management Enhancements (Post v0.73.0 / Future)

**Note**: Basic module management commands (`quickscale embed --module <name>`, `quickscale update`, `quickscale push`) are implemented in **v0.62.0**. Advanced features planned for **v0.73.0**. This section discusses potential future enhancements beyond v0.73.0.

Based on usage feedback after v0.73.0 implementation, consider these enhancements:

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

#### Configuration System Evaluation (potential v0.6x.0 release)

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

---

## REFERENCE MATERIAL

This section contains implementation guides, patterns, and reference documentation for module development and configuration.

---

### Module Configuration Strategy

**Status**: Implemented in v0.63.0+ (Interactive Prompts)

Modules require configuration when embedded (e.g., auth signup enabled/disabled, billing plan defaults). QuickScale uses a **two-phase approach**:

- **Phase 1 (MVP: v0.63.0-v0.69.0)**: Interactive prompts during `embed` command (IMPLEMENTED)
- **Phase 2 (Post-MVP: v1.0.0+)**: Optional YAML configuration file support (DEFERRED)

**For complete specifications**, see [decisions.md: Module Configuration Strategy](./decisions.md#module-configuration-strategy), which includes:
- Interactive prompt workflow examples
- Configuration state tracking (`.quickscale/config.yml`)
- YAML configuration schema (Post-MVP)
- Implementation notes for module developers

**Why this is in decisions.md**: Configuration strategy affects multiple modules and is an architectural decision that must remain consistent across the codebase.

---
