# QuickScale Glossary

**Purpose**: Centralized terminology reference for QuickScale project. All terms are defined once here and referenced throughout the documentation.

**Authority**: Terms defined here supersede inline definitions elsewhere. When in doubt, this glossary is authoritative for terminology.

---

## Core Concepts

### Generated Project
**Definition**: The standalone Django application created by running `quickscale plan <name>` + `quickscale apply`. This is the output that users own and customize for their client work.

**Key Characteristics**:
- Complete Django project with manage.py, settings.py, urls.py
- Production-ready: Docker, PostgreSQL, pytest, CI/CD
- 100% user-owned (no vendor lock-in)
- Can embed modules via git subtree

**See**: [scaffolding.md - Generated Project Output](./docs/technical/scaffolding.md#5-generated-project-output), [user_manual.md](./docs/technical/user_manual.md)

---

### Git Subtree
**Definition**: Git mechanism for embedding external repository code into a subdirectory of your project while preserving history and enabling bidirectional updates.

**QuickScale Usage**: MVP (Phase 1) distribution mechanism for:
- Embedding modules from QuickScale into client projects
- Sharing code across multiple client projects
- Contributing improvements back to QuickScale

**Workflow**:
- `quickscale apply` → Embeds modules using git subtree
- `quickscale update` → Pulls latest module changes
- `quickscale push` → Contributes improvements back

**See**: [decisions.md - Personal Toolkit Git Subtree](./docs/technical/decisions.md#integration-note-personal-toolkit-git-subtree), [plan-apply-system.md](./docs/technical/plan-apply-system.md)

---

### Module
**Definition**: Reusable Django app providing specific functionality (auth, billing, blog, etc.) that can be embedded into generated projects and updated over project lifetime.

**Key Characteristics**:
- Installable via `quickscale plan --add <module>` + `quickscale apply`
- Runtime dependencies (added to INSTALLED_APPS)
- Backend-heavy (~70% Python, ~30% templates)
- Theme-agnostic (works with all themes)
- Users can contribute improvements back

**Distribution**: Split branches (git subtree) for MVP; PyPI for Post-MVP

**Examples**: `auth`, `billing`, `teams`, `blog`, `listings`

**See**: [decisions.md - Module Architecture](./docs/technical/decisions.md#module-theme-architecture)

---

### Monorepo
**Definition**: QuickScale's development repository structure where all packages (core, CLI, modules, themes) are developed together in a single repository.

**Structure**:
```
quickscale/
├── quickscale_core/        # Core library
├── quickscale_cli/         # CLI tool
├── quickscale_modules/     # All modules (auth, billing, etc.)
│   ├── auth/
│   ├── billing/
│   └── teams/
└── pyproject.toml         # Monorepo package manager
```

**Benefits**: Atomic commits across packages, shared tooling, simplified testing

**See**: [scaffolding.md - Monorepo Layout](./docs/technical/scaffolding.md#2-monorepo-target-layout)

---

### Mutable Configuration
**Definition**: Module configuration options that can be changed after module embedding by editing `quickscale.yml` and running `quickscale apply`.

**Examples**:
- `auth.registration_enabled` - Enable/disable signups
- `auth.email_verification` - Email verification mode
- `blog.comments_enabled` - Enable/disable comments

**Mechanism**: Stored in Django settings.py and updated when config changes

**Opposite**: Immutable Configuration

**See**: [plan-apply-system.md - Configuration Mutability](./docs/technical/plan-apply-system.md#configuration-mutability)

---

### Immutable Configuration
**Definition**: Module configuration options that CANNOT be changed after module embedding. Changing these requires removing the module and re-embedding.

**Examples**:
- `auth.custom_user_model` - Affects database schema
- `auth.authentication_method` - Core auth mechanism
- `auth.social_providers` - OAuth providers

**Reason**: These affect database migrations, code structure, or architectural patterns that cannot be changed safely after initial setup.

**Opposite**: Mutable Configuration

**See**: [plan-apply-system.md - Configuration Mutability](./docs/technical/plan-apply-system.md#configuration-mutability)

---

### MVP (Minimum Viable Product)
**Definition**: Phase 1 of QuickScale (v0.56-v0.75.0) - Production-ready "Personal Toolkit" for solo developers and development agencies to build client projects faster.

**Scope**:
- ✅ Django project generator (`quickscale plan` + `quickscale apply`)
- ✅ Git subtree module distribution
- ✅ Production-ready foundations (Docker, PostgreSQL, testing, CI/CD)
- ✅ Single showcase theme
- ❌ Multiple themes (Post-MVP)
- ❌ PyPI distribution (Post-MVP)
- ❌ Marketplace (Post-MVP)

**Primary Use Case**: Fast client project spinup with code reuse across YOUR projects

**Synonym**: Phase 1, Personal Toolkit, Foundation Phase (v0.52-v0.55)

**Opposite**: Post-MVP

**See**: [decisions.md - MVP Feature Matrix](./docs/technical/decisions.md#mvp-feature-matrix-authoritative), [quickscale.md - Evolution Strategy](./docs/overview/quickscale.md#evolution-strategy-personal-toolkit-first)

---

### Personal Toolkit
**Definition**: MVP (Phase 1) implementation strategy where QuickScale serves as a personal development accelerator for YOUR client projects, using git subtree for code sharing.

**Philosophy**: Build simple tools for your own use first, extract patterns from real client work, evolve to community platform only when proven necessary.

**Key Principle**: "Start simple, grow organically based on real usage" - avoid building marketplace features until you have multiple successful client projects proving the patterns work.

**Synonym**: MVP, Phase 1

**Opposite**: Community Platform (Post-MVP)

**See**: [quickscale.md - Personal Toolkit Strategy](./docs/overview/quickscale.md#evolution-strategy-personal-toolkit-first)

---

### Plan/Apply Workflow
**Definition**: Terraform-style declarative configuration workflow where users define desired state in YAML and QuickScale applies changes incrementally.

**Commands**:
- `quickscale plan <name>` - Interactive wizard to create `quickscale.yml`
- `quickscale plan --add` - Add modules to existing config
- `quickscale plan --edit` - Reconfigure mutable options
- `quickscale apply` - Execute configuration
- `quickscale status` - Show current vs desired state

**Principle**: Declarative YAML (WHAT, not HOW). The YAML describes what you want; the execution engine knows the correct order.

**Introduced**: v0.68.0

**See**: [plan-apply-system.md](./docs/technical/plan-apply-system.md), [user_manual.md](./docs/technical/user_manual.md)

---

### Post-MVP
**Definition**: Phase 2+ of QuickScale (v0.76.0+) - Community platform with PyPI module distribution, multiple themes, and marketplace ecosystem.

**Planned Features**:
- ✅ Multiple themes (HTMX, React, vertical-specific)
- ✅ PyPI package distribution
- ✅ Community marketplace
- ✅ Commercial subscription model
- ✅ Advanced integrations (AI, analytics)

**Evolution Path**: Organic growth based on proven MVP usage, not speculative features

**Synonym**: Phase 2+, Community Platform

**Opposite**: MVP

**See**: [quickscale.md - Post-MVP Vision](./docs/overview/quickscale.md#future-strategy), [roadmap.md](./docs/technical/roadmap.md)

---

### Showcase Theme
**Definition**: Minimal starter theme demonstrating QuickScale's frontend capabilities with minimal code, designed as a foundation for custom development.

**Available Themes**:
- `showcase_html` - Pure HTML + CSS (default, MVP)
- `showcase_htmx` - HTMX + Alpine.js (planned v0.74.0)
- `showcase_react` - React + TypeScript + Vite (planned v0.75.0)

**Characteristics**:
- Minimal code (ready for customization)
- Not opinionated (user builds on top)
- Foundation for module embedding
- One-time generation (user owns code)

**Opposite**: Vertical Theme (complete industry-specific applications)

**See**: [decisions.md - Theme Categories](./docs/technical/decisions.md#module-theme-architecture)

---

### Split Branch
**Definition**: Git branch containing a single module's code, automatically generated from `quickscale_modules/<module>/` on the main branch for distribution.

**Purpose**: Enable git subtree embedding of individual modules into user projects without pulling the entire QuickScale repository.

**Naming Convention**: `splits/<module>-module` (e.g., `splits/auth-module`, `splits/billing-module`)

**Workflow**:
1. Develop module on `main` branch in `quickscale_modules/auth/`
2. GitHub Actions auto-splits to `splits/auth-module` on release
3. Users embed via `quickscale apply` (uses git subtree from split branch)
4. Users update via `quickscale update` (pulls from split branch)

**See**: [decisions.md - Split Branch Distribution](./docs/technical/decisions.md#module-theme-architecture)

---

### SSOT (Single Source of Truth)
**Definition**: The authoritative document or location for specific information. When conflicts arise, the SSOT always wins.

**QuickScale SSOTs**:
- **Technical Rules**: [decisions.md](./docs/technical/decisions.md) - Authoritative for all architectural decisions, technical rules, MVP scope
- **Terminology**: This glossary (GLOSSARY.md)
- **Directory Structure**: [scaffolding.md](./docs/technical/scaffolding.md)
- **Roadmap**: [roadmap.md](./docs/technical/roadmap.md)

**Principle**: Update SSOT FIRST, then propagate to other docs. Never contradict the SSOT.

**See**: [decisions.md - Critical Rules](./docs/technical/decisions.md#critical-rules)

---

### Theme
**Definition**: Complete frontend scaffolding for generated projects, ranging from minimal starters to full vertical applications. Unlike modules, themes are one-time generation (not updated after creation).

**Categories**:
1. **Showcase Themes** - Minimal foundations (HTML, HTMX, React)
2. **Vertical Themes** - Complete industry apps (real estate, SaaS)

**Distribution**: Generator templates (one-time copy)

**Key Difference from Modules**:
- Themes: Frontend-focused, one-time generation, not updated
- Modules: Backend-focused, ongoing updates via git subtree/PyPI

**Examples**: `showcase_html`, `showcase_htmx`, `real_estate`, `saas_starter`

**See**: [decisions.md - Theme Architecture](./docs/technical/decisions.md#module-theme-architecture)

---

### Vertical Theme
**Definition**: Complete, industry-specific application theme providing end-to-end functionality for a particular use case (real estate, job boards, e-commerce, etc.).

**Characteristics**:
- Pre-configured modules (auth, listings, blog, etc.)
- Industry-specific models and workflows
- Complete UI/UX implementation
- Ready for customization, not production deployment

**Examples**:
- `real_estate` - Property listings with React UI (v0.72.0+)
- `saas_starter` - SaaS with billing and teams (planned)
- `job_board` - Job listings and applications (planned)

**Opposite**: Showcase Theme (minimal starter)

**See**: [decisions.md - Vertical Themes](./docs/technical/decisions.md#module-theme-architecture)

---

## Development Terms

### Custom User Model
**Definition**: Django AbstractUser extension providing additional fields and functionality beyond Django's default User model.

**QuickScale Implementation**: All projects use a custom User model by default (following Django best practices) to enable future extensibility without database migrations.

**Configuration**: Immutable (set at project creation)

**See**: [Module: auth](./quickscale_modules/auth/README.md)

---

### Foundation Phase
**Definition**: Early QuickScale releases (v0.52-v0.55) focused on building incremental foundations before MVP.

**Synonym**: Pre-MVP

**Opposite**: MVP (v0.56+)

**See**: [decisions.md - Terminology](./docs/technical/decisions.md#mvp-vs-post-mvp-scope)

---

## Related Documentation

- **[decisions.md](./docs/technical/decisions.md)** - Authoritative technical rules and architectural decisions
- **[scaffolding.md](./docs/technical/scaffolding.md)** - Directory structures and file layouts
- **[plan-apply-system.md](./docs/technical/plan-apply-system.md)** - Plan/apply workflow specification
- **[quickscale.md](./docs/overview/quickscale.md)** - Strategic vision and evolution rationale
- **[roadmap.md](./docs/technical/roadmap.md)** - Development timeline and phases

---

**Last Updated**: 2025-12-07
**Maintained By**: QuickScale maintainers
**Feedback**: Open issue if terms need clarification or addition
