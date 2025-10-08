# DECISIONS: QuickScale Architecture & Technical Specifications

<!-- 
DECISIONS.md - Authoritative Technical Specification

PURPOSE: This document is the single source of truth for all architectural decisions, technical implementation rules, and development standards for QuickScale.

CONTENT GUIDELINES:
- Record all authoritative architectural decisions with rationale
- Document technical implementation rules (package naming, directory structure, testing)
- Specify behavioral decisions and operational patterns
- List explicit prohibitions (what NOT to do)
- Include detailed technical notes and code examples
- Maintain consistency across all QuickScale packages and extensions
- Update when technical standards change or new decisions are made

WHAT TO ADD HERE:
- New architectural decisions with full context and rationale
- Changes to package naming conventions or directory structures
- Updates to testing strategies or development patterns
- New prohibitions or anti-patterns discovered during development
- Technical implementation details that affect multiple packages
- Integration patterns between core, modules, and themes

WHAT NOT TO ADD HERE:
- Strategic rationale or competitive analysis (belongs in QUICKSCALE.md)
- User-facing documentation or getting started guides (belongs in README.md)
- Implementation timelines or roadmap items (belongs in ROADMAP.md)

TARGET AUDIENCE: Maintainers, core contributors, community package developers, CI engineers
-->

## Purpose

This document records authoritative architecture, technical & behaviour decisions for QuickScale. It is the single source of truth for how we structure packages, name artifacts, run tests, and what patterns are explicitly forbidden.

## Scope

- Applies to the QuickScale repository and all first-party packages (core, CLI, themes, modules).
- Intended for maintainers, core contributors, community package authors, and CI engineers.

## Decision Owners

- QuickScale maintainers (Experto-AI and core contributors) are the authoritative owners of these decisions.
- Community contributors must follow these decisions when creating themes or modules. Exceptions must be approved by maintainers and documented here.

## Documentation Maintenance Guidelines

### Single Source of Truth (SSOT) Principle

**DECISIONS.md is authoritative for**:
- Architectural decisions and rationale
- Technical specifications and rules
- MVP feature scope (Feature Matrix)
- Behavioral decisions (what/why/how)
- Explicit prohibitions

**When updating scope or architecture**:
1. ✅ Update DECISIONS.md FIRST
2. ✅ Then update referencing documents (README, ROADMAP, SCAFFOLDING)
3. ✅ Add cross-references so readers can find the SSOT
4. ❌ Never contradict DECISIONS.md in other docs

### Conflict Resolution

If documents conflict:
1. **DECISIONS.md wins** - it's the tie-breaker
2. Update conflicting document to match DECISIONS.md
3. Add PR review step: check DECISIONS.md alignment

### Documentation Cross-Reference Standards

When referencing concepts defined elsewhere:
- Link to the canonical section (don't duplicate content)
- Use consistent link format: `[descriptive text](./DOCUMENT.md#section-anchor)`
- Prefer deep links over file-level references

## MVP vs. Post-MVP Scope

**CRITICAL CLARIFICATION**: This document describes both the **MVP implementation** (Phase 1) and the **target architecture** (Post-MVP). QuickScale follows a **"start simple, evolve organically"** strategy. For the narrative rationale behind this evolution, defer to the [strategic overview in QUICKSCALE.md](../overview/quickscale.md#evolution-strategy-personal-toolkit-first); this section focuses on the technical implications.

### MVP Definition (clarification)

To remove ambiguity across documentation, the project defines the term "MVP" as the cumulative set of releases from **v0.52** through **v1.0.0** that together deliver a production-ready personal toolkit. Early 0.52-0.55 releases are considered the "Foundation Phase" (incremental engineering steps that prepare the ground for the MVP). When other documents reference "Foundation" or "Phase 1 increments", they refer to the pre-MVP incremental releases (v0.52-v0.55). This file (`DECISIONS.md`) remains the authoritative source for feature-inclusion decisions and is the tie-breaker if other docs disagree about whether a feature is in the MVP.

Guidance summary:
- "Foundation Phase" = v0.52 - v0.55 (incremental foundation work)
- "MVP" = v0.56 - v1.0.0 (production-ready personal toolkit; cumulative)
- Post-MVP = v1.1+ (module extraction, packaging, marketplace evolution)

### **Strategic Evolution Path:**

### **MVP (Phase 1) - Personal Toolkit First:**
- ✅ **quickscale_core**: Core scaffolding, minimal utilities, git subtree integration
- ✅ **quickscale_cli**: Simple CLI - just `quickscale init myapp` command
- ✅ **Scaffolded starter**: Generates minimal Django starter project users own completely
 These requirements ensure QuickScale matches competitors on production-readiness while maintaining its unique composability advantage. See [COMPETITIVE_ANALYSIS.md "What Must Be Incorporated"](../overview/competitive_analysis.md#what-quickscale-must-incorporate-from-competitors) for detailed analysis.
- ✅ **Django settings inheritance**: Simple Python imports, no YAML config required
- ✅ **Single starter template**: One way to create projects (no multiple templates)

Note: The MVP CLI intentionally implements a single, ultra-simple command: `quickscale init <project>`. Helper wrapper commands for git-subtree workflows (for example `quickscale embed-core`, `quickscale update-core`, `quickscale sync-push`) are not required for the initial release and therefore are not part of the MVP CLI. Those helpers are deferred to the Post-MVP backlog and will only be reconsidered after the initial `quickscale init` release proves sustained manual demand from users who opt into embedding the core.

**What MVP Generates:** See the [authoritative MVP structure diagram in SCAFFOLDING.md §3](./scaffolding.md#mvp-structure) for the full tree. The starter remains the standard Django layout with standalone settings by default.

### Integration note: Personal Toolkit (git-subtree) ✅ {#integration-note-personal-toolkit-git-subtree}

**This is the canonical Personal Toolkit documentation. Other documents reference this section.**

The Personal Toolkit approach is the chosen MVP implementation strategy:
1. Generate client projects from starter with `quickscale init`
2. Optionally embed `quickscale_core` via Git subtree (ONLY MVP distribution mechanism)
3. Extract reusable patterns into `quickscale_modules/` directory as they prove valuable across 2+ client projects (optional; NOT required for MVP)
4. CLI wrapper commands remain a Post-MVP consideration; until introduced, rely on the documented manual subtree operations

- **Module Extraction Clarification**:
- ✅ **MVP (recommended default)**: `quickscale_modules/` is NOT required and should NOT be created as part of the generated starter. Extraction of reusable code into an explicit `quickscale_modules/` workspace directory is an optional, later-stage workflow that teams may adopt once they have ≥2 projects and a clear reusable pattern.
- ✅ **MVP (advanced users)**: Teams that prefer a personal monorepo layout may create `quickscale_modules/` locally to organize extracted code; this is purely a local convention and is not part of the initial generated template.
- ❌ **Post-MVP**: When packaging modules for community distribution, `quickscale_modules/` becomes a canonical place to organize packages and will follow PEP 420 namespace guidelines.
- ❌ **Post-MVP**: Package modules for PyPI distribution and community sharing
- ❌ **Post-MVP**: PEP 420 namespace packaging and version management

The `quickscale_modules/` directory is a workspace convention for organizing YOUR reusable code, not a published package namespace in MVP.

**Git Subtree Workflow (Manual Commands for MVP)**:
```bash
# 1) Embed core into a client repo
git subtree add --prefix=quickscale https://github.com/Experto-AI/quickscale.git main --squash

# 2) Pull updates from quickscale into client
git subtree pull --prefix=quickscale https://github.com/Experto-AI/quickscale.git main --squash

# 3) Push client improvements back to quickscale
git subtree push --prefix=quickscale https://github.com/Experto-AI/quickscale.git feature-branch

# 4) Extraction pattern (move client code to quickscale_modules/)
mkdir -p quickscale_modules/myfeature
cp -r ../client_acme/acme/myfeature.py quickscale_modules/myfeature/
git add quickscale_modules/myfeature && git commit -m "chore(modules): extract myfeature"
```

**Note**: CLI wrapper commands (`quickscale embed-core`, `quickscale update-core`, `quickscale sync-push`) are deferred to Post-MVP. Until implemented, use the manual commands above.

### Module Extraction Workflow (Advanced Users)

Intent: This section documents the recommended workflow for extracting reusable code into a `quickscale_modules/` workspace. It is an advanced, optional workflow for maintainers and teams that manage multiple client projects. It is NOT part of the starter generated by `quickscale init`.

Key rules:
- The generated project (output of `quickscale init`) does NOT include a `quickscale_modules/` directory by default.
- `quickscale_modules/` is a workspace/monorepo convention used by maintainers (official modules) and by advanced users (personal monorepo) to organize reusable Django apps.
- During Post‑MVP packaging, `quickscale_modules/` will be a PEP 420 implicit namespace root (no `__init__.py`). A temporary `__init__.py` may be used locally during MVP development but MUST be removed prior to publishing packages.

When to extract:
- Extract when a feature is reused across 2+ projects or when you need independent versioning and testing.

Canonical commands (MVP manual git subtree patterns):
```bash
# Add core into a client repo
git subtree add --prefix=quickscale https://github.com/Experto-AI/quickscale.git main --squash

# Pull updates from quickscale into client
git subtree pull --prefix=quickscale https://github.com/Experto-AI/quickscale.git main --squash

# Push client improvements back to quickscale (when appropriate)
git subtree push --prefix=path/to/extracted/module origin main
```

Migration checklist (MVP → Post‑MVP packaging):
- Remove `quickscale_modules/__init__.py` and `quickscale_themes/__init__.py` (PEP 420 namespace)
- Ensure each module has a `pyproject.toml` and uses `find_namespace_packages()`
- Validate installs by creating a wheel and installing it in an isolated venv
- Add CI checks to fail builds where a namespace `__init__.py` remains prior to publish



### **Post-MVP (Phases 2+) - Organic Evolution:**
- ❌ **quickscale_modules/***: Packaged backend modules (auth, payments, billing, etc.)
  - Built as needed from real client projects (extraction pattern)
  - Distributed via git subtree initially, PyPI later for commercial use
- ❌ **quickscale_themes/***: Packaged theme applications
  - Emerge from successful client project patterns
- ❌ **YAML configuration**: Optional declarative config system (TBD if needed)
- ❌ **PyPI distribution**: For commercial modules, subscriptions, external agencies
- ❌ **Marketplace ecosystem**: Community-driven package discovery

**Post-MVP Package Structure (When Ready):** Refer to the [detailed post-MVP layout in SCAFFOLDING.md §4](./scaffolding.md#post-mvp-structure) for the canonical directory tree and packaging notes. Key enforcement rules are summarised in the MVP feature matrix and the naming matrix inside SCAFFOLDING.md §6.

Implementation policy (MVP vs Post-MVP):
- `quickscale_core` remains a regular Python package and MUST include an `__init__.py`.
- `quickscale_modules` and `quickscale_themes` transition to PEP 420 implicit namespace roots when published; if you add a temporary `__init__.py` during MVP experimentation, remove it before distributing packages.

Packaging / generated project rule (explicit):
See the "Packaging / generated-project policy (authoritative)" section later in this file for the canonical packaging decision (Poetry / `pyproject.toml` for generated projects and packages).

## MVP Feature Matrix (authoritative)

This matrix is the authoritative source of truth for **what is IN / OUT / PLANNED for the MVP** at the **feature level**.

**Scope**: High-level features and capabilities (e.g., "Docker support", "Testing infrastructure")

**Not in scope**: Implementation details (e.g., specific template files, task breakdowns)

**For implementation details**: See [ROADMAP.md](./ROADMAP.md) which implements the features defined in this matrix.

**Tie-breaker rule**: If ROADMAP.md conflicts with this matrix on feature scope, this matrix wins. Update ROADMAP to match.

Other documents (README.md, ROADMAP.md, SCAFFOLDING.md, COMMERCIAL.md) MUST reference this section when describing MVP scope; DECISIONS.md is the tie-breaker for any ambiguity.

| Feature / Area | MVP Status | Notes / Decision Reference |
|---|---:|---|
| **CORE CLI & SCAFFOLDING** |
| `quickscale init <project>` (single command, no flags) | IN | Core MVP entrypoint. (See: Phase 1.2.3) |
| Generate Django starter (manage.py, settings.py, urls.py, wsgi/asgi, templates, pyproject.toml) | IN | Starter uses `pyproject.toml` (Poetry). Generated projects include a `pyproject.toml` and `poetry.lock` by default; `requirements.txt` is not generated. |
| `quickscale_core` package (monolithic, src layout) | IN | Treat `quickscale_core` as a regular monolithic package in MVP (explicit `__init__.py`). See Section: "Core package shape" in this file. |
| `quickscale_core` embedding via git-subtree (manual documented workflow) | IN (manual) | Manual subtree commands are documented and supported; embedding is opt-in and advanced. |
| CLI git-subtree wrapper commands (`embed-core`, `update-core`, `sync-push`) | PLANNED | Post-MVP backlog; implement only after manual workflows demonstrate sustained demand. |
| Settings inheritance from `quickscale_core` into generated project | OPTIONAL | Default generated project uses standalone `settings.py`. If user explicitly embeds `quickscale_core`, optional settings inheritance is allowed and documented. |
| **PRODUCTION-READY FOUNDATIONS (Competitive Requirement)** | | **See [COMPETITIVE_ANALYSIS.md §1-3](../overview/competitive_analysis.md#-critical-for-mvp-viability-must-have)** |
| Docker setup (Dockerfile + docker-compose.yml) | IN | Production-ready multi-stage Dockerfile + local dev docker-compose with PostgreSQL & Redis services. Match Cookiecutter quality. |
| PostgreSQL configuration (dev + production) | IN | Split settings: SQLite for local dev, PostgreSQL for production. DATABASE_URL env var support via python-decouple/django-environ. |
| Environment-based configuration (.env + split settings) | IN | settings/base.py, settings/local.py, settings/production.py pattern. Secure SECRET_KEY loading from environment. |
| Security best practices | IN | ALLOWED_HOSTS, security middleware, SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE in production settings. Sentry scaffolding (commented). |
| WhiteNoise static files configuration | IN | Production static file serving without CDN complexity. |
| Gunicorn WSGI server | IN | Production-ready WSGI server declared in `pyproject.toml` (Poetry). |
| pytest + factory_boy test setup | IN | Modern testing with pytest-django, factory_boy for fixtures. Sample tests demonstrating patterns. |
| GitHub Actions CI/CD pipeline | IN | .github/workflows/ci.yml for automated testing on push/PR. Test matrix: Python 3.10-3.12, Django 4.2-5.0. |
| Pre-commit hooks (black, ruff, isort) | IN | .pre-commit-config.yaml for code quality enforcement before commits. |
| Comprehensive README with setup instructions | IN | README.md.j2 with Docker setup, local dev, testing, deployment instructions. |
| **MODULES & DISTRIBUTION** |
| `quickscale_modules/` (extracted reusable apps in personal monorepo) | OPTIONAL / NOT REQUIRED | Allowed as a local convenience for personal monorepos, but NOT a required MVP artifact. Packaging for distribution is Post-MVP. |
| `quickscale_themes/` packaged themes | OUT (Post-MVP) | Themes become packages in Post-MVP only. |
| YAML declarative configuration (`quickscale.yml`) | OUT (Post-MVP) | Deferred. |
| PyPI / private-registry distribution for commercial modules | OUT (Post-MVP) | Commercial distribution is Post-MVP (see COMMERCIAL.md). |
| Multiple starter templates / `--template` flag | OUT (Post-MVP) | Single starter only for MVP. |

Notes:
- This table is authoritative for release planning and documentation. If any document needs to show an example layout or convenience (e.g., `quickscale_modules/` appearing in a monorepo example), it must note that the item is "optional/personal-monorepo convenience" and point readers to this matrix for MVP status.

**Competitive Rationale for Production-Ready Foundations**:
The production-ready foundations (Docker, PostgreSQL, pytest, CI/CD, etc.) are classified as **P0 - Critical for MVP Viability** based on competitive analysis. Every successful Django boilerplate (SaaS Pegasus, Cookiecutter, Apptension) provides these as table stakes. Without them, QuickScale would be perceived as a toy project rather than a professional tool suitable for agency work. These requirements ensure QuickScale matches competitors on production-readiness while maintaining its unique composability advantage. See [COMPETITIVE_ANALYSIS.md "What Must Be Incorporated"](../overview/competitive_analysis.md#what-quickscale-must-incorporate-from-competitors) for detailed analysis.

Authoritative policy (tie-breakers)
----------------------------------

- **Settings inheritance (authoritative)**: The MVP generator creates a standalone `settings.py` by default and does **not** scaffold automatic inheritance from `quickscale_core.settings`. Teams that manually embed `quickscale_core` into a generated project via git subtree may opt-in to inherit from `quickscale_core.settings` by editing their generated `settings.py`. This is an advanced, manual pattern and is intentionally not automatic in the MVP. DECISIONS.md is the canonical location for this policy; other documents must link to this section for tie-breakers.

- **Packaging / generated-project policy (authoritative)**: Generated user projects (the starters created by `quickscale init`) use `pyproject.toml` and Poetry as the canonical packaging and dependency management tool for both MVP and Post‑MVP.

- **Packaging / generated-project policy (authoritative)**: Generated starters created by `quickscale init` MUST include a `pyproject.toml` and a `poetry.lock`. Poetry is the canonical packaging tool for MVP and Post‑MVP; the generator does not emit a `requirements.txt` by default.

- QuickScale first-party packages (core, CLI, modules) MUST include `pyproject.toml` when prepared for distribution. Rationale: Poetry + lockfiles enable deterministic installs, align with PEP 517/518/621, and simplify later packaging for PyPI.

### CLI Command Reference Matrix {#cli-command-matrix}

| Command | MVP Status | Target Phase | Description | Notes |
|---------|------------|--------------|-------------|-------|
| `quickscale embed-core` | 📋 PLANNED | v1.5 / v2.0 (conditional) | Embed `quickscale_core` via git subtree | Implement if manual workflow proves painful; v1.5 = lightweight helpers, v2.0 = richer orchestration/automation depending on usage metrics |
| `quickscale update-core` | 📋 PLANNED | v1.5 / v2.0 (conditional) | Pull git subtree updates into client project | Consider bundling with embed-core decision; implement if manual workflow proves painful |
| `quickscale sync-push` | 📋 PLANNED | v1.5 / v2.0 (conditional) | Push improvements back to QuickScale repo | Automates documented manual subtree push; conditional on usage metrics |
| `quickscale validate` | ❌ POST-MVP | 2+ | Validate YAML/JSON configuration | Depends on configuration system approval |
| `quickscale generate` | ❌ POST-MVP | 2+ | Generate project from configuration | Builds on declarative config capabilities |

The CLI remains intentionally minimal. This matrix tracks **pending and planned** commands; implemented commands (currently just `quickscale init`) are documented in the user-facing CLI reference to avoid duplication.

## Document responsibilities (short)

To avoid overlap and conflicting statements across files, the repository follows these responsibilities:
- `DECISIONS.md`: authoritative technical decisions, MVP feature matrix, package layout rules, and any tie-breakers. Use this file as the source of truth for "what" and "how" decisions.
- `ROADMAP.md`: timeline, phases, tasks, and acceptance criteria. Roadmap items should reference DECISIONS.md for technical specifics.
- `SCAFFOLDING.md`: example layouts and scaffolding guidance. Example blocks must be annotated as "example / optional" when they show conveniences that are not required for MVP.
- `README.md`: user-facing getting-started and high-level summary. It also carries the newcomer documentation map and canonical glossary, so keep that section in sync with this responsibility list and ensure it links back here for authoritative scope.
- `COMMERCIAL.md`: commercial models and Post-MVP guidance only; avoid asserting MVP behavior.

**Terminology**: For canonical terms (MVP, Phase 1, Post-MVP, etc.), refer to the [Glossary in README.md](./README.md#glossary) for standardized usage across all documentation.

Maintainers should update `DECISIONS.md` first when changing technical scope; other documents must be updated to reference the new decisions.

## Testing Standards (Authoritative)

### Coverage Targets

All QuickScale packages and modules must meet minimum test coverage thresholds:

- **quickscale_core**: Minimum 70% test coverage
- **quickscale_cli**: Minimum 70% test coverage
- **quickscale_modules/***: Minimum 70% test coverage per module (Post-MVP)
- **quickscale_themes/***: Minimum 70% test coverage per theme (Post-MVP)

### Testing Requirements

- All new features MUST include tests
- Bug fixes MUST include regression tests
- Integration tests for CLI workflows
- Unit tests for business logic
- End-to-end tests for critical user paths

### Test Infrastructure

- **pytest** with pytest-django for Django components
- **factory_boy** for test data generation
- **Coverage measured** with pytest-cov
- **CI fails** if coverage drops below targets
- **Coverage reports** generated on each CI run

### Generated Project Testing

Generated projects (`quickscale init myapp`) include:
- Sample test demonstrating pytest-django patterns
- factory_boy configuration for model factories
- pytest.ini configuration
- GitHub Actions CI workflow with coverage reporting

**When reading this document**: Sections describing module packages, theme packages, or complex configuration schemas refer to the **target architecture (Post-MVP)**, not the MVP implementation. The MVP is deliberately minimal - a personal toolkit that can evolve.

High-level decisions (what)
---------------------------

**ARCHITECTURAL DECISION: Library-Style Backend Modules (Post-MVP Vision)**

The **Library-Style Backend Modules** architecture for development acceleration and customization.

ℹ️ **Post-MVP Architecture Vision** – the details below outline future phases, not current MVP scope.

The architecture described below represents the **target end-state (Post-MVP)**. For MVP implementation status:
- ✅ **quickscale_core**: Implemented in Phase 1
- ✅ **Directory-based frontends**: Implemented in Phase 1 (scaffolded files)
- ❌ **quickscale_modules/***: Post-MVP (Phase 2+) - NOT in MVP
- ❌ **quickscale_themes/***: Post-MVP (Phase 2+) - NOT in MVP
- ❌ **Module/theme packages**: Post-MVP - MVP uses scaffolding only

**Core Architecture Concept (Target State):**
- **Backend Modules** = Built on proven Django foundations (dj-stripe, django-allauth, etc.) providing reusable functionality like backup, analytics, payments
- **Starting Point Themes** = Foundation Django applications that developers customize for their specific business needs
- **Directory-Based Frontends** = Custom frontend development via directory structure

**QuickScale as Development Foundation (Target State):**
QuickScale provides building blocks and acceleration tools, not complete business solutions:
- **Foundation (Core)**: Project scaffolding, configuration system, extension points, common utilities (hook system deferred to later phase)
- **Backend Modules** (Post-MVP): Built on proven Django foundations (django-allauth for auth, enhanced Django admin, dj-stripe, etc.) providing reusable functionality packages such as auth, admin, payments, billing, notifications, backup, analytics
- **Themes** (Post-MVP): Starting points that require customization for specific business needs
- **Frontends** (MVP): Directory-based presentation layer for customization via scaffolded templates

**Target Architecture Structure (Post-MVP):** The full tree lives in [SCAFFOLDING.md §2](./scaffolding.md#2-monorepo-target-layout-post-mvp-end-state). This section focuses on the architectural rationale; see SCAFFOLDING.md for the canonical layout.

MVP Architecture Structure (Phase 1): refer to [SCAFFOLDING.md §3](./scaffolding.md#mvp-structure) for the generated package tree. DECISIONS.md records the policies that guide that layout rather than duplicating the tree.

**Key Advantages of Library-Style Architecture:**
- ✅ **Familiar Mental Model**: Like Python's ecosystem (import what you need)
- ✅ **Maximum Reusability**: Modules work across all themes and custom applications
- ✅ **Clear Separation**: Modules = libraries, Themes = starting points, Frontends = presentations
- ✅ **Development Acceleration**: Start with foundations, customize for specific needs
- ✅ **Developer Specialization**: Module developers vs Theme maintainers vs Application developers
- ✅ **Composability**: Applications pick exactly the modules they need and customize themes

**Community Specialization Model:**
- **Module Developers**: Focus on integrating proven Django apps with QuickScale patterns
  - Authentication experts integrate django-allauth into `quickscale_modules/auth`
  - Admin interface experts enhance Django admin in `quickscale_modules/admin`
  - Payment processing experts integrate dj-stripe into `quickscale_modules/payments`
  - Email experts integrate django-anymail into `quickscale_modules/notifications`
  - (Future) Analytics experts build `quickscale_modules/analytics`
- **Theme Maintainers**: Focus on foundational patterns and examples
  - Provide starting point themes like `starter` and `todo`
  - Maintain example implementations showing best practices
- **Application Developers**: Focus on building custom business applications
  - Use starting point themes as foundations
  - Customize models, business logic, and presentation for their specific needs
  - Integrate modules to add functionality

### Admin Module Scope Definition

**Status**: Defined for Post-MVP implementation

The `quickscale_modules.admin` module provides enhanced Django admin capabilities with custom views, system configuration, monitoring dashboards, and audit logging.

**Admin Module IS:**
- ✅ **Enhanced Django Admin Interface**: Custom admin views, improved UX, bulk actions
- ✅ **System Configuration**: Settings management, feature flags, environment configuration
- ✅ **Monitoring Dashboards**: System health metrics, performance monitoring, application insights
- ✅ **Audit Logging**: Activity tracking, change history, compliance logging
- ✅ **Admin Workflows**: Custom admin actions, batch operations, data management tools

**Admin Module IS NOT:**
- ❌ **User Authentication**: Authentication, login/logout, password management (belongs in `quickscale_modules.auth`)
- ❌ **User Management**: User registration, profile management, permissions (belongs in `quickscale_modules.auth`)
- ❌ **Authorization**: Role-based access control, permissions (belongs in `quickscale_modules.auth`)

**Clear Module Boundaries:**
- **auth module**: Handles user identity, authentication, authorization, and user-facing account management
- **admin module**: Handles administrative interface enhancements, system configuration, and operational tools

**Post-MVP Implementation Notes:**
- Built on Django's admin framework with custom ModelAdmin classes and views
- Provides reusable admin mixins and utilities for common patterns
- Integrates with audit logging for compliance and security
- Extensible through standard Django admin customization patterns

**Implementation Challenges & Mitigations:**
- **API Compatibility**: Modules need stable APIs → Semantic versioning, clear API documentation, compatibility matrices
- **Integration Complexity**: Themes integrating multiple modules → Standard interfaces, integration guides, example implementations  
- **Documentation Overhead**: Each module needs docs → Documentation templates, automated API docs, community examples

6. Testing Strategy (Unified DI Policy)
   - Production code uses direct imports of services (no service container / registry).
   - Tests MAY pass alternative implementations (constructor/function parameter injection) for isolation.
   - Keep injection shallow: only boundary collaborators (payment gateway, billing calculator, notification sender).
   - No global mutable registries. No runtime plugin mutation of core.
   - Example pattern (minimal):
     ```python
     class OrderProcessor:
         def __init__(self, payment_service=None):
             from quickscale_modules.payments import services as payment_services
             self.payment_service = payment_service or payment_services.DefaultPaymentService()
     ```

**ARCHITECTURAL DECISION: Configuration-Driven Project Definition**

The **Configuration-Driven Alternative** approach for project definition and assembly.

ℹ️ **Configuration status**: YAML/JSON-driven project definition is Post-MVP vision work. Phase 1 sticks with plain Django settings files; any schemas shown here are illustrative only.

**MVP Approach (Phase 1):**
- Projects use standard Django settings.py (no inheritance, no YAML)
- Settings inheritance from `quickscale_core.settings` is Post-MVP (TBD if needed)
- No configuration files or schemas required
- Generated projects are standalone and fully owned by user

**Post-MVP Evolution (Phase 2+):**
- **Declarative Configuration** = YAML/JSON files define project structure and features (if proven useful)
- Evaluate if configuration layer adds value based on MVP usage
- **Code Generation** = CLI generates Django code from configuration specifications
- **Version Control Integration** = Configuration files tracked in Git for change management
- **Schema Validation** = Prevent invalid configurations through schema validation

**Post-MVP illustrative schema (v1.0 example — NOT used in MVP)**

The snippet below is an illustrative, minimal configuration schema provided as a Post-MVP design example. It is included for planning and compatibility discussions only; the MVP does not read or validate YAML/JSON configuration files.

```yaml
schema_version: 1
project:
  name: myapp
  version: 1.0.0

# NOTE (Post-MVP example): In this illustrative example the 'theme' key would refer to a
# packaged theme. In the MVP this field is ignored and packaged themes are not loaded.
theme: starter

# Python inheritance entrypoint (illustrative)
backend_extensions: myapp.extensions

# Directory-based frontend only in MVP; Post-MVP examples may extend this
frontend:
  source: ./custom_frontend/
  variant: default
```

Schema notes (illustrative / Post-MVP compatibility guidance):
- `modules` field: NOT supported in MVP (would be a validation error if enforced in MVP)
- `customizations` field: NOT supported in MVP
- `theme` field: Reserved for Post-MVP use; in MVP this has no runtime effect
- `frontend`: MVP only supports a simple directory-based frontend; Post-MVP schemas may extend this

**Post-MVP Configuration Schema v2.0 (Target Architecture):**
```yaml
schema_version: 2
project:
  name: mystore
  version: 1.0.0

# Post-MVP: Actual theme package loading
theme: starter

# Python inheritance entrypoint
backend_extensions: myapp.extensions

# Post-MVP: Module system with package loading
modules:
  payments:
    provider: stripe   # charge execution
  billing:
    provider: stripe   # subscription & entitlement logic
  # notifications: { provider: sendgrid }
  # backup: { provider: aws, schedule: daily }

frontend:
  source: ./custom_frontend/
  variant: default

# Post-MVP: Advanced customization support
customizations:
  models:
    - name: Product
      fields:
        - { name: name, type: string }
        - { name: price, type: decimal }
  business_rules:
    - "Products require approval before listing"
    - "Orders over $1000 need manager approval"
```

**Deprecated fields/structures** (all versions): `features`, `components`, `technologies`, `primary`, or any `frontend` keys outside `source` and `variant`. These MUST NOT appear in configs (validation error).

**Key Advantages of Configuration-Driven Architecture:**
- ✅ **Non-Developer Accessibility**: Business users can modify project configurations without coding
- ✅ **Version Control Friendly**: Configuration changes tracked and reviewable in Git
- ✅ **Automated CI/CD**: Deployment pipelines can process configuration files automatically
- ✅ **Self-Documenting**: Configuration serves as living project documentation
- ✅ **Schema Validation**: Prevents invalid configurations through automated validation
- ✅ **Reproducible Deployments**: Exact project recreation from configuration files

**CLI Integration Pattern (Post-MVP illustrative):**
```bash
# Interactive configuration creation (Post-MVP idea / illustrative only)
quickscale init --interactive        # (Post-MVP idea) Creates quickscale.yml through guided wizard
quickscale validate                  # (Post-MVP idea) Validates configuration against schemas
quickscale generate                  # (Post-MVP idea) Generates Django code from configuration
quickscale preview                   # (Post-MVP idea) Shows what will be generated without creating files
quickscale deploy --env=staging      # (Post-MVP idea) Deploys based on configuration + environment
```

**Implementation Strategy:**
- Configuration schema definitions for validation
- Template engine for code generation from configurations
- Environment-specific configuration overrides
- Migration system for configuration format changes
- Integration with existing Library-Style Backend Modules architecture

**ARCHITECTURAL DECISION: Git Subtree Distribution**

The **Git Subtree Distribution** decision establishes git subtree as the mechanism for distributing and managing shared code across multiple client projects.

Git Subtree Distribution Concept:
- **Git Subtree Operations**: Git subtree (ONLY MVP distribution mechanism) is the canonical workflow for sharing code; the document provides examples and guidance for users in the MVP.
- **CLI Command Abstraction (MVP scope)**: Git subtree is the primary distribution mechanism for the MVP. Lightweight CLI wrapper commands to perform common embed/update/sync workflows (for example: `quickscale embed-core`, `quickscale update-core`, `quickscale sync-push`) are deferred to Post-MVP evaluation. Until those helpers are implemented, the documented manual `git subtree` commands are the supported workflow for advanced users.
- **Monorepo Source of Truth**: All shared code maintained in the quickscale monorepo with proper versioning
- **Automated Dependency Management (MVP)**: CLI wrapper commands for subtree operations remain on the Post-MVP backlog and are not included in the initial `quickscale init` release. More advanced automation (batch updates, centralized orchestration, conflict heuristics) may be expanded Post‑MVP.

# CLI Command Structure (MVP vs Post-MVP):

MVP (authoritative):
```bash
# Ultra-minimal CLI surface (single command, no flags)
quickscale init myapp
```

Notes:
- The MVP intentionally exposes a single, simple entrypoint: `quickscale init <project_name>`. No flags or template variants are part of the MVP contract.
- Wrapper helpers to simplify git-subtree workflows (for example: `quickscale embed-core`, `quickscale update-core`, `quickscale sync-push`) are a Post-MVP evaluation item. They MUST preserve the documented manual `git subtree` commands if introduced and must not change the MVP CLI's minimal surface.

Post-MVP (illustrative ideas — NOT part of MVP):
```bash
# Interactive or advanced commands considered only for Post-MVP
quickscale init --interactive        # (Post-MVP idea) create quickscale.yml through guided wizard
quickscale validate                  # (Post-MVP idea) validate configuration against schemas
quickscale generate                  # (Post-MVP idea) generate Django code from configuration
quickscale preview                   # (Post-MVP idea) show what will be generated without creating files
quickscale deploy --env=staging      # (Post-MVP idea) deploy based on configuration + environment
```

Implementation note: keep the MVP CLI small. Any advanced flag/command must be introduced later with clear migration notes and tests.

**Key Advantages of Git Subtree Distribution:**
- ✅ **Zero External Dependencies**: No package registries or artifact repositories required
- ✅ **Version Control Transparency**: All code changes tracked in git history with proper attribution
- ✅ **Offline Development**: No network dependency for development after initial setup
- ✅ **Conflict Resolution**: Standard git merge tools handle code conflicts
- ✅ **Bidirectional Sync**: Changes can flow from monorepo to projects and back
- ✅ **Selective Updates**: Update individual components without affecting others

**MVP Distribution Guidance**
- For the MVP, git subtree is the default distribution mechanism for embedding `quickscale_core` and the minimal starter theme into client projects. This keeps the developer workflow simple and avoids early reliance on package indices.
- Publishing modules/themes to package registries (pip) for private or subscription distribution is considered Post-MVP and will be designed after initial feedback from the community and commercial users.

**Backward compatibility stance**
- The new QuickScale architecture is intentionally breaking. Automated migration of existing QuickScale projects is out-of-scope for the MVP. The project provides legacy analysis and extraction guidance to help maintainers manually migrate useful assets where feasible.

**Distribution Architecture:**
- **Monorepo Structure**: `quickscale_core/`, `quickscale_modules/`, `quickscale_themes/`, `quickscale_cli/`
- **Project Integration**: Each client project contains git subtrees for shared components
- **Version Management**: Semantic versioning with git tags for stable releases
- **Branch Strategy**: `main` for stable releases, feature branches for development

**Implementation Requirements:**
- For MVP: document manual git subtree workflows clearly and provide examples for maintainers and client projects.
- CLI helper commands for git-subtree workflows are NOT included in the initial MVP `quickscale init` release; they remain on the Post-MVP backlog. If introduced later, those helpers must include proper error handling, clear conflict-resolution guidance, and automated tests in CI/CD. Post-MVP enhancements may extend automation to batch or centralized workflows. Documentation must explain failure modes and recovery steps.

**Distribution Strategy: MVP vs. Post-MVP**

**AUTHORITATIVE STATEMENT ON DISTRIBUTION:**

QuickScale uses different distribution strategies for different phases:

**MVP (Phase 1) - Git Subtree Distribution:**
- ✅ **Primary mechanism**: Git subtree for embedding quickscale_core into client projects
- ✅ **CLI commands (MVP)**: `quickscale init` is the single CLI command included in the initial release. Lightweight wrapper commands for subtree workflows (for example `quickscale embed-core`, `quickscale update-core`, `quickscale sync-push`) are deferred to Post-MVP and are NOT part of the initial `init` release. Post-MVP may add further convenience flags and batch automation.
- ✅ **Benefits**: No package registry dependencies, offline development, simple workflows
- ✅ **Use cases**: Solo developers, small agencies, rapid iteration
- ❌ **Not using**: PyPI, pip packages, package registries (for core distribution)

**Post-MVP (Phase 3:) - Package Registry Distribution:**
- 📦 **Additional option**: PyPI publishing for modules and themes
- 📦 **Use cases**: Commercial extensions, subscription models, marketplace ecosystem
- 📦 **Benefits**: Version management, dependency resolution, wider distribution
- 📦 **Scope**: Modules and themes only, NOT core (core stays git-based)

**Why Git Subtree for MVP:**
- No external dependencies for distribution
- Simple developer workflow
- Proven pattern for code sharing
- Aligns with solo developer/agency use cases
- Faster iteration without version bumps

**Why Package Registry for Post-MVP:**
- Commercial extension monetization (see COMMERCIAL.md)
- Community marketplace support
- Standard dependency management for extensions
- Optional (git subtree remains supported)

**ARCHITECTURAL DECISION: Backend Extension & Frontend Development (Post‑MVP)** {#backend-extensions-policy}

The **Backend Extension & Frontend Development** decision describes the long‑term, Post‑MVP pattern for simple project customization using standard Django patterns. For the MVP we keep the scaffolding minimal and avoid generating runtime extension files; the extension pattern below is targeted at Post‑MVP when module/theme packaging and optional generation facilities are introduced.

**Backend Extension Pattern (Post‑MVP):**
- Themes provide inheritance‑friendly base classes (models, services, forms).
- Projects MAY use `backend_extensions.py` for customizations via Python inheritance in Post‑MVP toolchains (generators or templates).
- Call `super()` in extensions for compatibility with theme updates.

**Frontend Development Pattern (MVP & Post‑MVP):**
- Directory‑based frontends (`frontend.source`) are supported in the MVP for local development and customization; richer tooling and optional generation are Post‑MVP.
- Basic variant support (MVP: simple folder variants) maps to `variants/<name>/` folders for different UX styles.

**Configuration Rules (MVP scope):**
- `frontend` accepts only `source` and `variant` keys in MVP scope.
- `backend_extensions.py` is a Post‑MVP convention and is not automatically generated by the MVP CLI. Projects may add a `backend_extensions.py` manually if desired; Post‑MVP tooling may optionally scaffold/import it.
- Schema validation provides clear errors for missing directories or configuration (Post‑MVP schema tooling).

### Backend customization (MVP decision)

Decision: The MVP does NOT scaffold a `backend_extensions.py` file. Projects own backend customizations; the recommended, idiomatic pattern is to add a local app (e.g. `client_extensions`) and perform startup wiring in an `AppConfig.ready()` method (idempotent registration).

Post‑MVP: tooling may optionally provide scaffolds or helpers; any contract will be recorded here in DECISIONS.md.

**Implementation Notes:**
- MVP: The CLI and scaffold produce a minimal Django project and optional `custom_frontend/` directory. The MVP intentionally does NOT generate `backend_extensions.py` automatically. This avoids regeneration risks and keeps the generated project fully owned by the user.
- Post‑MVP: When module and theme packaging is introduced, the scaffolding may optionally generate `backend_extensions.py` templates or helpers as part of richer project generation flows.

*Illustrative Backend Extension Pattern (Post‑MVP):* (Commercial licensing integrations expand on this pattern in [`COMMERCIAL.md`](../overview/commercial.md#subscription-based-repository-implementation).)
```python
# Example: illustrative backend_extensions.py (Post‑MVP)
from quickscale_themes.starter import models as starter_models
from quickscale_themes.starter import business as starter_business

class ExtendedUser(starter_models.User):
  """Extended user model with custom fields"""
  department = models.CharField(max_length=100)
    
class ExtendedBusinessLogic(starter_business.StarterBusiness):
  """Extended business logic with custom rules"""
  def process_order(self, order):
    # Custom business logic
    result = super().process_order(order)
    # Additional custom processing
    return result
```

*Directory‑Based Frontend Pattern (MVP illustrative):* Refer to the concise starter tree in [SCAFFOLDING.md §5](./scaffolding.md#5-generated-project-output) for the canonical layout. This section only records the decision that `custom_frontend/` remains optional in MVP while richer tooling is deferred.

*Generated Project Structure (MVP):* The structure is catalogued once in [SCAFFOLDING.md §5.1](./scaffolding.md#51-mvp-ultra-minimal-django-project); DECISIONS.md defers to that reference to avoid duplication.

**MVP Core Features:**
1. **Directory‑Based Frontend**: Optional `custom_frontend/` with template and static directories
2. **Basic Variant Support**: Simple variant switching via `frontend.variant` configuration
3. **Django Settings Integration**: Automatic template and static file directory configuration
4. **Standard Django Patterns**: No custom framework overhead, pure Django approach

**MVP Limitations:**
- ❌ **No multi‑client config array** - Just single `variant` string for now
- ❌ **No automated API contract versioning** - Manual compatibility for MVP  
- ❌ **No registry or marketplace** - Directory‑based development only
- ❌ **No advanced CLI features** - Basic project creation only

**ARCHITECTURAL DECISION: Standard Django Database Architecture**

The **Standard Django App-based Database Architecture**.

**Database Architecture Concept:**
- **Standard Django Apps**: Each backend module and theme is a standard Django app with its own `app_label`
- **Django's Built-in Namespacing**: Tables automatically namespaced as `{app_label}_{model_name}`
- **Standard Migration System**: Django's migration system handles dependencies and schema changes
- **No Custom Table Naming**: Use Django's default table naming patterns

**Database Structure:**
```python
# Each module is a standard Django app
# quickscale_modules/payments/ (Django app with app_label='quickscale_payments')
class Transaction(models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20)
    
    class Meta:
        app_label = 'quickscale_payments'
# Results in table: quickscale_payments_transaction

# quickscale_modules/analytics/ (Django app with app_label='quickscale_analytics')
class Event(models.Model):
    event_type = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'quickscale_analytics'
# Results in table: quickscale_analytics_event
```

**Key Advantages of Standard Django Architecture:**
- ✅ **Zero Conflicts**: Django's app_label system automatically prevents table name conflicts
- ✅ **Standard Migrations**: `python manage.py migrate` handles all inter-app dependencies automatically
- ✅ **Proven at Scale**: Used successfully by Wagtail (NASA, Google), Django CMS, and all major Django platforms
- ✅ **Normal Django Patterns**: Admin, signals, management commands, ForeignKeys all work normally
- ✅ **Developer Familiarity**: Every Django developer understands this approach
- ✅ **Simple Deployment**: Standard Django deployment patterns, no special database coordination needed

**INSTALLED_APPS Configuration (truly modular - only install what you need):**
```python
INSTALLED_APPS = [
  'quickscale_core',                 # Core scaffolding & utilities (minimal)
  # Optional modules - install only what your app needs (use dotted import paths):
  # 'quickscale_modules.auth',       # Authentication & user management
  # 'quickscale_modules.admin',      # Enhanced Django admin, monitoring, audit logging
  # 'quickscale_modules.payments',   # Payments backend module
  # 'quickscale_modules.billing',    # Billing backend module
  # 'quickscale_modules.notifications',  # future
  # 'quickscale_modules.backup',          # future
  # 'quickscale_modules.analytics',       # future
  # Themes are standard Django apps as well:
  # 'quickscale_themes.starter',
]
```
**Multiple Frontends** = Each theme supports N presentation technologies (HTMX, React, Vue, etc.) that may be bundled with the theme or installed as standalone frontend packages
**Cross-Module Relationships:**
```python
# Standard Django ForeignKey relationships work normally between apps
from quickscale_modules.auth.models import User
from quickscale_modules.payments.models import Transaction

class Order(models.Model):
    user = models.ForeignKey('quickscale_modules_auth.User', on_delete=models.CASCADE)
    transaction = models.ForeignKey('quickscale_modules_payments.Transaction', on_delete=models.SET_NULL, null=True)
```

Behaviour & operational decisions (why)
-------------------------------------
-- **Foundation, not complete solutions**: QuickScale provides starting points that developers customize for their specific business needs, not ready-to-use complete applications
- **Creation-time assembly**: we intentionally choose not to support runtime dynamic loading of themes/modules. This aligns with Django patterns and avoids runtime migration/coordination complexity.
- **Standard Django database architecture**: each backend module and theme is a standard Django app with its own app_label. This leverages Django's built-in table namespacing and migration system, following proven patterns used by all successful Django platforms (Wagtail, Django CMS).
- **Customization-focused themes**: starting point themes provide foundational patterns and examples that developers extend and customize rather than complete industry solutions
- **Separate CLI**: bootstrapping must be possible before a full core install; the CLI also has a different release cadence and responsibilities.
- **src/ layout**: prevents accidental imports of local source when running tests or building packages.
- **Namespace packages**: allow many independently distributed themes/modules to share top-level import names (no `__init__.py` at namespace root).
- **Configuration-driven development**: project structure and features defined declaratively in YAML/JSON configuration files rather than imperative CLI commands. This enables version control of project configuration, automated deployments, and non-developer participation in project definition.
- **Direct imports with minimal dependency injection**: themes import modules directly; constructor-based injection only for tests (no DI frameworks/service containers).
- **Hook system deferred**: initial phases do not implement the hook/event system; future phase will introduce a lightweight event dispatcher.
- **Single provider implementations**: embrace specific provider implementations (Stripe, SendGrid) rather than abstract interfaces, allowing access to full feature sets and reducing complexity.
- **Version pinning for Django foundations**: QuickScale modules pin exact versions of their underlying Django apps (e.g., `quickscale-module-auth==0.9.0` pins `django-allauth==1.2.3`) for predictable, tested compatibility.

What NOT to do (explicit prohibitions)
-------------------------------------
- DO NOT implement runtime dynamic `INSTALLED_APPS` modifications to install themes/modules while an application is running.
- DO NOT place first-party packages under a nested `quickscale/quickscale_*` directory (avoid `quickscale/quickscale_core`); this creates import and packaging ambiguity.
- DO NOT expose external HTTP APIs from modules; they should expose functionality via a Python service layer (e.g., classes in `services.py`).
- DO NOT tightly couple themes to modules. (Interim) Until hook system ships, use explicit service calls; refactor to hooks later.
- DO NOT place tests inside `src/` (keeps packaging lean and avoids shipping tests in wheel unless explicitly desired).
- DO NOT rely on implicit, unpinned versions for production assemblies. The CLI must pin compatible versions at project creation time.
- DO NOT allow configuration files to execute arbitrary code or import Python modules; configurations must be pure data YAML for security and portability.
- DO NOT create configuration formats that require deep nesting or complex syntax; prioritize readability and maintainability for non-developers.
- DO NOT use complex service registry patterns or dependency injection frameworks. Use simple constructor-based dependency injection for testing purposes only.
- DO NOT abstract away provider-specific features behind generic interfaces. Embrace single implementations (e.g., Stripe for payments) to access full feature sets.
- DO NOT use custom database table naming schemes, event sourcing, or shared schema patterns. Use standard Django app architecture with Django's built-in table namespacing via app_label.

Package Structure and Naming Conventions
-----------------------------------------

**AUTHORITATIVE DECISION: PEP 420 Namespace Packages**

The canonical naming and import matrix now lives in [SCAFFOLDING.md §6](./scaffolding.md#6-naming-import-matrix-summary). This section records the policy-level decisions only:

- Post-MVP modules and themes MUST use PEP 420 implicit namespace packages so independently released wheels can share the `quickscale_modules` / `quickscale_themes` namespaces without a namespace `__init__.py`.
- MVP starters remain simple: `quickscale_core` is a regular package with an explicit `__init__.py`, no namespace packaging required until Phase 2+.
- When preparing a namespace package for release, follow the directory layout and app-label guidance captured in SCAFFOLDING.md §6; do not duplicate the matrix elsewhere.

**Why PEP 420 Namespaces (recap):** independent distribution, conflict-free installs, standard Python behaviour, and room for third-party extensions.

**MVP Note:** During Phase 1, generated projects and in-repo packages use conventional packages for simplicity. Transition to namespace packages only when modules/themes graduate to separate distributions.

## Packaging & namespaces (summary)

Keep packaging guidance short and easy to find: for the MVP treat `quickscale_core` as a normal, single package (regular `__init__.py`, simple editable installs, and easy subtree embedding). For Phase 2+ where modules/themes are released independently, adopt PEP 420 implicit namespace packages for `quickscale_modules` and `quickscale_themes` so independent wheels can contribute subpackages under the same logical namespace (use `find_namespace_packages()` in `pyproject.toml`). This approach preserves simple developer experience in MVP while enabling an ecosystem of independently-versioned modules/themes later.

## Namespace Package Migration Checklist (MVP → Post-MVP)

When extracting a module for independent distribution:

**Step 1: Verify MVP Package Structure**
- ✅ Module works as editable install via git subtree
- ✅ Tests pass with temporary `__init__.py`
- ✅ No circular imports or dependency issues

**Step 2: Remove Namespace `__init__.py`**
- ❌ Delete `quickscale_modules/__init__.py`
- ❌ Delete `quickscale_themes/__init__.py`
- ✅ Keep `quickscale_modules/auth/__init__.py` (leaf package)

**Step 3: Update `pyproject.toml`**
- Use `find_namespace_packages()` instead of `find_packages()`
- Configure namespace package in build settings

**Step 4: Test Namespace Package**
- Install two different modules in same environment
- Verify both work without conflicts
- Check `import quickscale_modules.auth` succeeds

**Step 5: Publish to PyPI**
- Build wheel with `python -m build`
- Verify wheel metadata with `wheel unpack`
- Test install from wheel before publishing

## Namespace Package Quality Assurance

**CI Checks**: Add automated checks to fail builds where namespace `__init__.py` files exist in published modules. This prevents accidental inclusion of temporary MVP `__init__.py` files.

**PEP 420 Validation**: Include namespace package compliance checks in CI pipeline to ensure proper `find_namespace_packages()` configuration and absence of namespace `__init__.py` files.

**Guidelines Location**: Namespace package guidelines are documented in this section and cross-referenced in SCAFFOLDING.md examples.

Detailed technical notes
------------------------
- src layout example (package `quickscale_core`):
  - `quickscale_core/pyproject.toml`
  - `quickscale_core/src/quickscale_core/__init__.py`
  - `quickscale_core/src/quickscale_core/apps.py`
  - `quickscale_core/tests/`

- Namespace example (PEP 420 implicit):
  - `quickscale_themes/ecommerce/src/quickscale_themes/ecommerce/...`
  - `quickscale_themes/realestate/src/quickscale_themes/realestate/...`
  - No `src/quickscale_themes/__init__.py` file required.

- Compatibility metadata (example in `pyproject.toml`):
  ```toml
  [project.metadata.quickscale]
  core-compatibility = ">=2.0.0,<3.0.0"
  ```

- Dependency injection example (tests only):
  ```python
  class StarterTheme:
    def __init__(self, payment_service=None):
      from quickscale_modules.payments import services as payment_services
      self.payment_service = payment_service or payment_services.DefaultPaymentService()
  ```

Billing vs Payments Boundary (Authoritative):
| Concern | Billing Module | Payments Module |
|---------|----------------|-----------------|
| Primary Role | Subscription & plan management, entitlements | Charge execution, refunds, payment intents |
| Data Models | Plan, Subscription, Entitlement | Transaction, ProviderWebhookEvent |
| External Integration | Billing provider APIs (e.g., Stripe Billing) | Payment provider APIs (e.g., Stripe Payments) |
| Provides to Themes | Subscription status checks, entitlement decorators | Payment execution services |
| Not Responsible For | Direct charge execution | Subscription lifecycle logic |

_Legacy configuration example removed: see canonical configuration schema v1 earlier (uses `modules:` rather than `features:` and omits admin as a module)._
