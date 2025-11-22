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
   - � Billing module (v0.68.0) - stub directory exists, implementation pending
   - 📋 Teams module (v0.69.0) - stub directory exists, implementation pending
   - 📋 Showcase architecture for module discovery (deferred to post-v0.69.0)

2. **Phase 2: Additional Themes (Port Existing Modules)** 📋 _Planned_
   - 📋 HTMX theme with Alpine.js (v0.70.0)
   - 📋 React theme with TypeScript SPA (v0.71.0)
   - 📋 Port all core modules to new themes

3. **Phase 3: Expand Features (All Themes)** 📋 _Planned_
   - 📋 Notifications module with email infrastructure (v0.72.0)
   - 📋 Advanced module management features (v0.73.0)
   - 📋 Workflow validation and real-world testing (v0.74.0)

4. **Phase 4: Community Platform (Optional v1.0.0+)** 📋 _Future_
   - 📋 PyPI package distribution
   - 📋 Theme package system
   - 📋 Marketplace and community features

**Legend:**
- ✅ = Completed
- 🚧 = In Progress
- 📋 = Planned/Not Started

**Key Milestones:**
- **v0.69.0:** SaaS Feature Parity (auth, billing, teams) 🎯
- **v1.0.0+:** Community platform (if demand exists)

**Status:**
- **Current Status:** v0.66.0 — Blog module with custom Django implementation
- **Validation:** Real estate project testing blog and listings modules
- **Next Milestone:** v0.67.0 - Listings module (generic multi-vertical pattern)
- **SaaS Parity:** v0.69.0 - auth, billing, teams modules complete

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

### v0.66.0: Blog Module (`quickscale_modules.blog`)

**Status**: 🚧 In Development

**Strategic Context**: Custom lightweight Django blog built for QuickScale philosophy. No suitable Django-native blog exists (zinnia unmaintained, Puput too heavy). Provides immediate validation via real estate project while maintaining generic reusability for any vertical.

**Blog Module Development**:
- [ ] Create blog models in `quickscale_modules/blog/models.py`:
  - Post model (title, slug, content, author, published_date, status, featured_image)
  - Category model (name, slug, description)
  - Tag model (name, slug)
  - AuthorProfile model (user, bio, avatar)
  - **Acceptance Criteria**: All models have __str__ methods, Meta ordering, and admin registration
- [ ] Implement Markdown editor integration in `quickscale_modules/blog/fields.py`:
  - Use django-markdownx for WYSIWYG Markdown editing
  - Configure image upload handling
  - **Acceptance Criteria**: Editor renders in admin, supports image uploads, preview functionality works
- [ ] Build views in `quickscale_modules/blog/views.py`:
  - PostListView (paginated, 10 posts per page)
  - PostDetailView (single post with category/tags)
  - CategoryListView (posts filtered by category)
  - TagListView (posts filtered by tag)
  - **Acceptance Criteria**: All views handle published vs draft status, pagination works
- [ ] Add URL routing in `quickscale_modules/blog/urls.py`:
  - `/blog/` - post list
  - `/blog/<slug>/` - post detail
  - `/blog/category/<slug>/` - category list
  - `/blog/tag/<slug>/` - tag list
  - `/blog/feed/` - RSS feed
  - **Acceptance Criteria**: All URLs resolve correctly, slug patterns work
- [ ] Design blog templates:
  - `quickscale_modules/blog/templates/quickscale_modules/blog/`:
    - `base.html` - Zero-style semantic HTML (no CSS classes)
    - `post_list.html` - Zero-style list view
    - `post_detail.html` - Zero-style detail view
  - `themes/default/templates/quickscale_modules/blog/`:
    - Styled overrides for the default theme
  - **Acceptance Criteria**: Zero-style templates render clean HTML, Default theme adds styling via `themes/` directory
- [ ] Add featured images in `quickscale_modules/blog/models.py`:
  - Use Pillow for image processing
  - Generate thumbnails (300x200, 800x450)
  - Store in MEDIA_ROOT/blog/images/
  - **Acceptance Criteria**: Images upload, thumbnails generate, alt text supported
- [ ] Implement RSS feed in `quickscale_modules/blog/feeds.py`:
  - Use django.contrib.syndication.views.Feed
  - Include last 20 published posts
  - Full content vs excerpt (configurable)
  - **Acceptance Criteria**: Feed validates at feedvalidator.org, includes pubDate, link, description

**Features Deferred to Future**:
- Comments (use third-party like Disqus)
- Advanced SEO (Open Graph, schema)
- Related posts algorithm
- Scheduled publishing

**Architecture Compliance**:
- [ ] Follow split branch distribution pattern (develop in `quickscale_modules/blog/`, split to `splits/simple-blog`)
- [ ] Theme compatibility: Zero-Style base + Default Theme (v0.66.0)
- [ ] Interactive configuration during embed:
  - Posts per page (default: 10)
  - Excerpt length (default: 300 characters)
  - Enable categories/tags (default: yes)
  - Enable RSS feed (default: yes)
- [ ] Auto-configuration during `quickscale embed --module simple-blog`:
  - Add 'modules.blog' to INSTALLED_APPS
  - Add MARKDOWNX_* settings to settings.py
  - Include blog.urls in project urls.py (at /blog/)
  - Run migrations automatically
  - Create sample blog post (optional prompt)
- **Acceptance Criteria**: Embed completes without manual settings editing, blog accessible at /blog/

**Module Configuration**:
- [ ] Interactive prompts for blog configuration during embed
- [ ] Configure blog settings (posts per page, excerpt length, etc.)
- [ ] Add blog URLs to generated project
- [ ] Create initial blog migrations

**Testing**:
- [ ] Unit tests in `quickscale_modules/blog/tests/`:
  - `test_models.py`: All model methods, string representations, ordering (Target: 80%+ coverage)
  - `test_views.py`: All view classes, context data, pagination (Target: 75%+ coverage)
  - `test_urls.py`: URL resolution and reverse lookups (Target: 100% coverage)
  - `test_feeds.py`: RSS feed content and validation (Target: 80%+ coverage)
  - **Overall Target**: 70%+ coverage for blog module
- [ ] Integration tests in `quickscale_modules/blog/tests/test_integration.py`:
  - Test blog embedding via `quickscale embed --module simple-blog`
  - Verify auto-configuration (INSTALLED_APPS, URLs, migrations)
  - Test published vs draft filtering
  - Verify category/tag filtering
  - **Acceptance Criteria**: All integration scenarios pass, no manual config required
- [ ] E2E tests in `quickscale_modules/blog/tests/test_e2e.py`:
  - Create blog post via admin (with Playwright)
  - Publish post and verify on frontend
  - Test image upload and display
  - Verify RSS feed generation
  - Test pagination on post list
  - **Acceptance Criteria**: Complete blog workflow (create → publish → view → RSS) validated
- [ ] Real-world validation:
  - Initialize `examples/real_estate` project
  - Embed blog module
  - Create 10+ sample posts
  - Test filtering, pagination, RSS feed
  - Document edge cases and iterate
  - **Acceptance Criteria**: Real project successfully uses blog module without issues

**Dependencies & Prerequisites**:
- [ ] No module dependencies (blog is standalone)
- [ ] Optional integration: If auth module installed, use allauth for author profiles
- [ ] Django dependencies: django-markdownx, Pillow
- [ ] Task Order:
  1. Models (foundation)
  2. Admin registration (enables manual testing)
  3. Views and URLs (frontend access)
  4. Templates (visual design)
  5. RSS feed (content syndication)
  6. Interactive embed configuration (integration)
  7. Testing (validation)

**Documentation**:
- [ ] Create `quickscale_modules/blog/README.md`:
  - Features overview (Markdown editing, categories, tags, RSS)
  - Installation: `quickscale embed --module simple-blog`
  - Configuration options reference
  - Template customization guide
  - Model extension patterns (for custom fields)
  - **Acceptance Criteria**: README enables users to embed, configure, and customize blog without asking questions

- [ ] Create blog customization guide in `quickscale_modules/blog/docs/customization.md`:
  - Adding custom fields to Post model
  - Creating custom blog templates
  - Extending views with filters
  - SEO optimization patterns
- [ ] Add blog examples to `examples/`:
  - Real estate blog example
  - Tech blog example
  - Agency blog example
  - **Acceptance Criteria**: Examples demonstrate vertical-specific customizations

---

### v0.67.0: Listings Module (`quickscale_modules.listings`)

**Status**: 📋 Planned (after blog module)

**Strategic Context**: Generic listings base model supporting multiple verticals (real estate, jobs, events, products). Real estate becomes first implementation, validating generic pattern. Proves reusability from day 1.

**Core Abstraction**:
- [ ] `AbstractListing` model (title, description, price, location, status) - Abstract Base Class
- [ ] Search and filtering infrastructure
- [ ] Zero-style templates

**Real Estate Vertical** (First Implementation):
- [ ] `Property` model extending `AbstractListing` (Concrete model in `examples/real_estate`)
- [ ] Property-specific fields (bedrooms, bathrooms, sqft, type)
- [ ] Real estate theme in `themes/real_estate` (or similar)

**Future Verticals**:
- JobPosting, Event, Product, BusinessListing models
- Vertical-specific extensions via Abstract Inheritance

**Validation Workflow**:
- [ ] Test in real estate project during development
- [ ] Iterate module design based on real usage
- [ ] Push improvements back to QuickScale
- [ ] Update via `quickscale update`

**Testing**:
- [ ] Unit tests for base Listing model (70% coverage)
- [ ] Integration tests for Property vertical
- [ ] Real estate site validation

---

### v0.70.0: HTMX Frontend Theme (Deferred)

**Status**: Deferred to post-v0.69.0 (after SaaS Feature Parity)

**Rationale**: Focus on completing core modules (auth, billing, teams) before adding new themes.

**See**: [user_manual.md Theme Selection](../technical/user_manual.md#theme-selection-v0610) for current theme architecture.

**When Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation specifications including HTMX + Alpine.js base templates and progressive enhancement patterns.

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

### Module Showcase Architecture (Deferred to Post-v0.69.0)

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

**If Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation patterns and [release-v0.65.0-plan.md](../releases/release-v0.65.0-plan.md) for original showcase specifications.

---

### v0.70.0: HTMX Frontend Theme (Deferred)

**Status**: Deferred to post-v0.69.0 (after SaaS Feature Parity)

**See**: v0.67.0 above for implementation details - this is the actual implementation release after deferral.

---

### v0.71.0: React Frontend Theme (Deferred)

**Status**: Deferred to post-v0.69.0 (after SaaS Feature Parity)

**Rationale**: Focus on completing core modules (auth, billing, teams) before adding new themes.

**See**: [user_manual.md Theme Selection](../technical/user_manual.md#theme-selection-v0610) for current theme architecture.

**When Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation specifications including React + TypeScript + Vite setup and Django REST Framework API endpoints.

---

### v0.72.0: `quickscale_modules.notifications` - Notifications Module (Deferred)

**Status**: Deferred to post-v0.69.0 (after SaaS Feature Parity)

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

### v0.73.0: Advanced Module Management Features

**Note**: Basic module management commands (`quickscale embed --module <name>`, `quickscale update`, `quickscale push`) are implemented in **v0.62.0**. This release adds advanced features for managing multiple modules.

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

**Future Enhancements** (v0.74.0+, evaluate after v0.69.0):
- [ ] Module versioning: `quickscale embed --module auth@v0.62.0` - Pin specific module version
- [ ] Semantic versioning compatibility checks
- [ ] Automatic migration scripts for breaking changes
- [ ] Extraction helper scripts (optional, only if manual workflow becomes bottleneck)

**Success Criteria**: Implement advanced features only when:
- Manual subtree operations exceed 10 instances/month across maintainers OR
- Teams have performed 5+ module extractions manually and report significant time savings from automation

---

### v0.74.0: Module Workflow Validation & Real-World Testing

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

**Rationale**: Module embed/update commands implemented in v0.62.0. This release validates those commands work safely in production after real usage across multiple client projects.

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
