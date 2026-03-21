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

1. **Phase 1: Foundation + Core Modules (React Theme Default)** 🚧 _In Progress_
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
  - 📋 Social & Link Tree module (v0.77.0) - social links page + media embeds
  - 📋 Listings Theme (v0.78.0) - React frontend for property listings (sell/rent)
  - 📋 CRM Theme (v0.79.0) - React frontend for CRM module
  - 📋 Billing module (v0.80.0) - Stripe integration
  - 📋 Teams module (v0.81.0) - multi-tenancy

2. **Phase 2: Additional Themes (Secondary Options)** 📋 _Planned_
  - 📋 HTMX theme with Alpine.js (v0.82.0+) - alternative for progressive enhancement
   - HTML theme remains as secondary option (simpler projects)

3. **Phase 3: Expand Features (All Themes)** 📋 _Planned_
  - 📋 Notifications module with email infrastructure (v0.83.0)
  - 📋 Advanced module management features (v0.84.0)
  - 📋 Workflow validation and real-world testing (v0.85.0)

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
- **v0.77.0:** Social & Link Tree module foundation 📋
- **v0.78.0:** Real Estate MVP (static + listings + social links) 🎯
- **v0.81.0:** SaaS Feature Parity (auth, billing, teams) 🎯
- **v1.0.0+:** Community platform (if demand exists)

**Status:**
- **Current Status:** v0.76.0 — Storage Module ✅ Complete
- **In Progress:** none — next scoped release work starts at v0.77.0
- **Next Release:** v0.77.0 - Social & Link Tree module
- **Next Milestone:** v0.78.0 - Real Estate MVP
- **Plan/Apply System:** v0.68.0-v0.71.0 - Terraform-style configuration ✅ Complete
- **SaaS Parity:** v0.81.0 - auth, billing, teams modules complete

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

Release summaries currently exist in [docs/releases/](../releases/) for selected completed releases. Detailed implementation/review artifacts remain in [docs/releases-archive/](../releases-archive/). Keep v0.76.0 tracked here and in the changelog until a reader-facing summary is actually published.

---

### v0.76.0: `quickscale_modules.storage` - Media Storage & CDN Integration Module

**Status**: ✅ Complete — storage contract cleanup, canonical blog media URLs, permanent deployment/docs alignment, and targeted regression coverage landed; deeper integration/E2E expansion moved to v0.85.0 workflow validation

**Strategic Context**: Shared infrastructure module for user-uploaded files and media delivery. Provides a production-ready path beyond local filesystem storage by standardizing cloud object storage, CDN URL generation, image handling, and deployment wiring across QuickScale modules.

QuickScale-generated projects already work well in local development, but production media handling is still a project-by-project concern. That becomes a serious limitation when a workflow depends on uploaded files being durable across redeployments, publicly accessible at stable URLs, and efficiently cacheable through a CDN. The first concrete use case is **experto.ai blog automation**, where the publishing pipeline must upload images first, receive final public URLs, rewrite Markdown content to those URLs, and then publish the post without relying on local container disk.

This module should solve that infrastructure concern once, centrally, instead of repeating custom storage setup in every generated project or feature module. It should be a reusable dependency layer for media storage concerns, while business modules such as `blog`, `listings`, or future attachment-heavy modules continue to own their domain logic. In practice:

- `quickscale_modules.blog` should continue owning publishing workflows and content models.
- `quickscale_modules.storage` should own where uploaded files live, how their public URLs are built, and how production-safe delivery is configured.
- local filesystem storage must remain the default for development and simple projects.
- cloud-backed storage must be a documented, opt-in path for production projects that need durable media.

**Primary Objectives**:
- [x] Standardize media storage across QuickScale modules
- [x] Make uploaded files durable across Railway redeployments and container restarts
- [x] Provide stable, CDN-ready public URLs for uploaded assets
- [x] Reduce repeated per-project storage and CDN configuration work
- [x] Create a reusable foundation for blog images, avatars, galleries, and future attachments

**Non-Goals for v0.76.0**:
- [ ] No infrastructure provisioning / Terraform automation
- [ ] No video transcoding or advanced media pipeline
- [ ] No full DAM/media-library product scope
- [ ] No forced migration of existing local-media projects
- [ ] No provider-specific premium features unless they fit the shared abstraction cleanly

**Prerequisites**:
- ✅ React Default Theme (v0.74.0)
- ✅ Blog API image upload support available in the blog module

**Implementation Approach**:
- Build this as an infrastructure module, not a vertical feature module
- Keep local filesystem as the default development mode
- Add explicit opt-in configuration for cloud storage providers
- Prefer S3-compatible interfaces first so AWS S3 and Cloudflare R2 share most of the implementation
- Expose simple project-level helpers that other modules can use without importing provider-specific logic

#### Implementation Checklist

**Architecture & Boundaries**:
- [x] Define module boundary: what belongs in `storage` vs what remains in `blog` and other modules
- [x] Define supported provider matrix for v0.76.0 (minimum: local + S3-compatible + Cloudflare R2)
- [x] Define stable public URL contract for uploaded files and CDN fronting
- [x] Define upload path strategy by module / asset type / date / collision-safe suffix
- [x] Define fallback strategy so projects can remain on local storage if desired
- [x] Define the future extension point for private media even if v0.76.0 only ships public media delivery
- [x] Make `public_base_url` the only supported public URL source for storage-backed media and blog-facing asset URLs
- [x] Remove `custom_domain` from the storage module contract entirely instead of keeping any backward-compatibility path
- [x] Fold mixed blog URL behavior into the storage integration plan so uploads, Markdown rewrites, featured images, and future blog-owned assets resolve through one canonical public URL helper

**Core Storage Features**:
- [x] Storage backend abstraction: local filesystem, S3-compatible, Cloudflare R2
- [x] Provider configuration contract with explicit required and optional fields
- [x] Project-level settings wiring for Django `STORAGES["default"]`
- [x] Canonical media URL generation helpers
- [x] CDN base URL support for uploaded media
- [x] Upload path conventions for images, documents, and generic assets
- [x] Validation helpers for file size, content type, and image dimensions
- [x] Shared helper for converting stored file references into final public URLs
- [x] Shared helper for generating immutable, cache-friendly asset names

**Image & Media Processing**:
- [x] Keep richer image variants and WebP/optimized generation out of v0.76.0 scope; preserve the current thumbnail-first MVP and defer broader media processing to a later release
- [x] Cache-friendly filename/versioning strategy for immutable media URLs
- [x] Shared utilities for modules that attach uploaded files to models
- [x] Decide whether image processing is synchronous for v0.76.0 or deferred to future async integration
- [x] Define a clean extension point for future background processing without blocking the initial release
- [x] Ship a minimum viable remote thumbnail generation path for storage-backed images, acceptable as a synchronous first pass
- [x] Ensure generated thumbnail URLs use the same `public_base_url` contract as original media URLs
- [x] Defer richer variants, async/background processing, and broader media-pipeline expansion to a later release

**Module Integrations**:
- [x] Blog integration: use storage module for uploaded featured and inline images
- [x] Author/avatar compatibility for existing blog author profiles
- [x] Defer React showcase guidance and broader cross-module media integration hooks until the related vertical/theme releases land
- [x] Ensure blog upload/publish APIs continue working when the storage backend changes from local to cloud
- [x] Define how feature modules should depend on `storage` without importing provider-specific code
- [x] Make blog templates and model helpers stop relying on direct `.url` for public rendering, using storage-backed public URL helpers instead
- [x] Extend the same canonical public URL strategy to blog author/avatar and similar blog-owned image fields
- [x] Verify blog publish flows no longer mix raw storage URLs, deprecated `custom_domain` behavior, and `public_base_url`-based URLs in the same project

**CLI & Plan/Apply Integration**:
- [x] Add `module.yml` manifest with mutable and immutable config boundaries
- [x] Define `quickscale plan --add storage` prompts / defaults
- [x] Add CLI wiring so generated projects receive provider-specific settings only when enabled
- [x] Ensure `quickscale apply` can regenerate settings safely without clobbering unrelated project code
- [x] Defer any automatic `blog` ↔ `storage` apply-time coupling until broader cross-module planner work in v0.84.0
- [x] Add interactive `quickscale plan` module configuration for `storage` so backend/provider settings and `public_base_url` can be captured during planning
- [x] Add a planner flag for interactive module configuration instead of forcing manual `quickscale.yml` edits for storage-specific setup
- [x] Fix `quickscale plan --reconfigure` to preserve existing per-module option dictionaries instead of rebuilding them with empty values
- [x] Acceptance: `plan --reconfigure` round-trips unchanged module options safely while updating only the fields the user reconfigures

**Configuration & Deployment**:
- [x] Environment variable contract (`AWS_*`, bucket, endpoint, CDN URL)
- [x] Document minimum environment variables for AWS S3 and Cloudflare R2
- [x] Railway deployment guide for external media storage
- [x] Local development fallback preserving current filesystem behavior
- [x] Staging vs production guidance for media storage
- [x] Explicit note that Railway local disk should not be treated as durable production media storage
- [x] CDN cache guidance for immutable uploaded assets
- [x] Migration guide for moving existing local-media projects to cloud-backed storage
- [x] Document `public_base_url` as the canonical environment-specific override for swapping S3/CDN host or base path without changing stored media keys
- [x] Remove `custom_domain` from storage docs/config guidance so new setups use `public_base_url` only

**Documentation & Acceptance Criteria**:
- [x] Add a module README with local/dev, staging, and production setup paths
- [x] Add troubleshooting guidance for missing credentials, invalid buckets, and broken CDN URLs
- [x] Document how other modules should integrate with storage helpers
- [x] Acceptance: a generated project can run locally with filesystem storage and no cloud credentials
- [x] Acceptance: a generated project can switch to S3-compatible storage via documented environment variables
- [x] Acceptance: blog image upload + publish workflow works end-to-end with cloud-backed URLs
- [x] Acceptance: resulting media URLs are stable and cache-friendly for CDN delivery
- [x] Acceptance: Railway deployment guidance is documented and production-safe
- [x] Acceptance: `public_base_url` is the documented public URL source of truth for storage/blog media in v0.76.0
- [x] Acceptance: storage no longer exposes `custom_domain`; `public_base_url` is the sole public media URL setting
- [x] Acceptance: cloud-backed originals and generated thumbnails both resolve to stable, cache-friendly public URLs

**Testing**:
- [x] Unit tests for storage backend selection and URL helpers
- [x] Keep targeted helper/blog/CLI regressions in v0.76.0 and reschedule deeper storage upload/write/read integration coverage to v0.85.0 workflow validation
- [x] Blog integration tests for uploaded images using storage-backed URLs
- [x] Reschedule Plan → Apply → Blog publish with uploaded CDN-backed images end-to-end coverage to v0.85.0 workflow validation
- [x] Regression tests proving local-development behavior still works without cloud configuration
- [x] Regression tests proving public blog rendering never depends on direct storage `.url` when storage helpers are available
- [x] Planner tests covering interactive storage configuration, option persistence, and safe `plan --reconfigure` round-trips
- [x] Thumbnail tests covering local and storage-backed generation with identical `public_base_url` URL resolution

---

### v0.77.0: `quickscale_modules.social` - Social & Link Tree Module

**Status**: 📋 Planned

**Strategic Context**: Social media presence module providing a link tree page (social network links) and social media embed integration. Supports progressive enhancement from simple social links to rich media embeds.

**Prerequisites**:
- ✅ React Default Theme (v0.74.0)

**Link Tree Features**:
- [ ] Configurable social links page (Instagram, TikTok, YouTube, Facebook, X/Twitter, LinkedIn)
- [ ] Link tree models: SocialLink (platform, url, icon, order, is_active)
- [ ] Admin interface for managing social links
- [ ] Link tree React component with platform icons and branding
- [ ] Customizable link tree layout (grid, list, card styles)
- [ ] Click tracking and analytics (optional)

**Social Media Embed Integration**:
- [ ] oEmbed protocol support for rich media embeds
- [ ] Instagram feed/post embed component
- [ ] TikTok video embed component
- [ ] YouTube video/channel embed component
- [ ] Facebook post embed component
- [ ] Embed gallery page (aggregate social feeds)
- [ ] Caching layer for embed data (reduce API calls)

**Backend**:
- [ ] Social media models and Django Admin
- [ ] REST API endpoints for social links and embeds
- [ ] oEmbed resolver service
- [ ] Rate limiting for external API calls

**Testing**:
- [ ] Unit tests for social models and oEmbed resolver
- [ ] Integration tests for embed components
- [ ] E2E tests: Plan → Apply → Working social links project

---

### v0.78.0: Listings Theme (React Frontend for Listings)

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

### v0.79.0: CRM Theme (React Frontend for CRM)

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

### v0.80.0: `quickscale_modules.billing` - Billing Module

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

### v0.81.0: `quickscale_modules.teams` - Teams/Multi-tenancy Module

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

### Module Showcase Architecture (Deferred to Post-v0.81.0)

**Status**: 🚧 **NOT YET IMPLEMENTED** - Deferred to post-v0.81.0

**Current Reality** (v0.66.0):
- ✅ Basic context processor exists (`quickscale_core/context_processors.py`)
- ❌ Showcase landing page with module cards: **NOT implemented**
- ❌ Module preview pages: **NOT implemented**
- ❌ Showcase CSS styles: **NOT implemented**
- ❌ Current `index.html.j2`: Simple welcome page only

**Why Deferred**:
- Focus on Plan/Apply system and core modules first (v0.68-v0.81)
- Showcase architecture provides maximum value when multiple modules exist
- Current simple welcome page is adequate for MVP

**Implementation Plan**: After v0.81.0 (SaaS Feature Parity milestone), evaluate whether to implement showcase architecture or keep simple welcome page. Decision criteria:
- Are 3+ modules complete and production-ready?
- Is module discovery a user pain point?
- Would showcase provide meaningful marketing value?

**If Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation patterns.

---

### v0.82.0+: HTMX Frontend Theme (Optional)

**Status**: 📋 Planned (low priority, after SaaS Feature Parity)

**Rationale**: React theme is now the default (v0.74.0). HTMX provides an optional alternative for users preferring progressive enhancement.

**See**: [user_manual.md](../technical/user_manual.md) for current theme architecture and user-facing theme selection guidance.

**When Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation specifications including HTMX + Alpine.js base templates and progressive enhancement patterns.

---

### v0.83.0: `quickscale_modules.notifications` - Notifications Module

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
- [ ] Unit tests for email sending (80%+ per file coverage)
- [ ] Integration tests with email providers
- [ ] Test async processing with Celery
- [ ] Cross-theme compatibility testing

**See**: [competitive_analysis.md Module Roadmap](../overview/competitive_analysis.md#phase-2-post-mvp-v1---saas-essentials) for competitive context.

---

### v0.84.0: Advanced Module Management Features

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

**Future Enhancements** (v0.85.0+, evaluate after v0.81.0):
- [ ] Module versioning: `quickscale plan --add auth@v0.63.0` - Pin specific module version
- [ ] Semantic versioning compatibility checks
- [ ] Automatic migration scripts for breaking changes
- [ ] Extraction helper scripts (optional, only if manual workflow becomes bottleneck)

**Success Criteria**: Implement advanced features only when:
- Manual subtree operations exceed 10 instances/month across maintainers OR
- Teams have performed 5+ module extractions manually and report significant time savings from automation

---

### v0.85.0: Module Workflow Validation & Real-World Testing

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
