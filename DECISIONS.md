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

## MVP vs. Post-MVP Scope

**CRITICAL CLARIFICATION**: This document describes both the **MVP implementation** (Phase 1) and the **target architecture** (Post-MVP). QuickScale follows a **"start simple, evolve organically"** strategy.

### **Strategic Evolution Path:**
- **MVP Goal**: Personal toolkit for client projects (CONTENDING-ALTERNATIVE approach)
- **Long-term Vision**: Community ecosystem platform with marketplace
- **Implementation Strategy**: Build MVP fast, evolve based on real usage

### **MVP (Phase 1) - Personal Toolkit First:**
- ✅ **quickscale_core**: Core scaffolding, minimal utilities, git subtree integration
- ✅ **quickscale_cli**: Simple CLI - just `quickscale init myapp` command
- ✅ **Scaffolded starter**: Generates "Hello World" Django project users own completely
- ✅ **Git subtree distribution**: ONLY distribution mechanism for MVP
- ✅ **Django settings inheritance**: Simple Python imports, no YAML config required
- ✅ **Single starter template**: One way to create projects (no multiple templates)

**What MVP Generates:**
```python
myapp/                      # User owns this completely
├── manage.py              # Standard Django
├── myapp/
│   ├── settings.py        # Can import from quickscale_core if embedded
│   ├── urls.py
│   └── wsgi.py
├── quickscale/            # Git subtree embedded (optional)
│   └── quickscale_core/   # Basic utilities only
└── requirements.txt       # Django + minimal dependencies
```

### Integration note: Personal Toolkit (git-subtree) ✅

The Personal Toolkit approach (see the "Personal Toolkit" sections in `README.md` and `ROADMAP.md`) is the chosen MVP implementation strategy: develop client projects from a generated starter, optionally embed `quickscale_core` via git subtree, and extract reusable patterns into `quickscale_modules/` as they prove valuable. This keeps MVP simple while enabling code reuse across your projects.

```
# Quick subtree & extraction reference
# 1) Embed core into a client repo (manual example)
git subtree add --prefix=quickscale https://github.com/Experto-AI/quickscale.git main --squash

# 2) Pull updates from quickscale into client
git subtree pull --prefix=quickscale https://github.com/Experto-AI/quickscale.git main --squash

# 3) Extraction pattern (move client code to quickscale_modules/)
mkdir -p quickscale_modules/myfeature
cp -r ../client_acme/acme/myfeature.py quickscale_modules/myfeature/
git add quickscale_modules/myfeature && git commit -m "chore(modules): extract myfeature"
```


### **Post-MVP (Phases 2+) - Organic Evolution:**
- ❌ **quickscale_modules/***: Packaged backend modules (auth, payments, billing, etc.)
  - Built as needed from real client projects (extraction pattern)
  - Distributed via git subtree initially, PyPI later for commercial use
- ❌ **quickscale_themes/***: Packaged theme applications
  - Emerge from successful client project patterns
- ❌ **YAML configuration**: Optional declarative config system (TBD if needed)
- ❌ **PyPI distribution**: For commercial modules, subscriptions, external agencies
- ❌ **Marketplace ecosystem**: Community-driven package discovery

**Post-MVP Package Structure (When Ready):**
```python
quickscale_modules/
├── auth/                  # Built on django-allauth
├── payments/              # Built on dj-stripe  
└── billing/               # Custom billing logic

# PEP 420 implicit namespaces (no __init__.py at namespace level)
```

**When reading this document**: Sections describing module packages, theme packages, or complex configuration schemas refer to the **target architecture (Post-MVP)**, not the MVP implementation. The MVP is deliberately minimal - a personal toolkit that can evolve.

High-level decisions (what)
---------------------------

**ARCHITECTURAL DECISION: Library-Style Backend Modules (Post-MVP Vision)**

The **Library-Style Backend Modules** architecture for development acceleration and customization.

**⚠️ IMPORTANT: Post-MVP Architecture Vision - NOT in MVP**

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

**Target Architecture Structure (Post-MVP):**
```
quickscale_core/                    # Foundation (like Python stdlib)

quickscale_modules/                 # Backend libraries built on Django foundations (POST-MVP)
  ├── auth/                        # Built on django-allauth (authentication & user management)
  ├── admin/                       # Enhanced Django admin interface
  ├── payments/                    # Built on dj-stripe (first official)
  ├── billing/                     # Built on proven billing foundations
  ├── notifications/               # Built on django-anymail (future)
  └── analytics/                   # (future) Analytics functionality library

quickscale_themes/                  # Starting point applications (POST-MVP)
  ├── starter/                     # Planned: Foundation models and business logic
  └── todo/                        # Planned: Reference implementation
```

**MVP Architecture Structure (Phase 1):**
```
quickscale_core/                    # Core scaffolding + config + utilities
quickscale_cli/                     # CLI tool for project generation

# Generated in user projects (not packages):
project/
  ├── backend_extensions.py        # Python inheritance stub
  └── custom_frontend/             # Scaffolded frontend files
      ├── templates/
      ├── static/
      └── variants/
```

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

**⚠️ MVP STATUS**: Configuration system is **OPTIONAL/TBD** for MVP. MVP uses simple Django settings inheritance.

**MVP Approach (Phase 1):**
- Projects use standard Django settings with Python imports
- Optional: Import base settings from `quickscale_core.settings`
- No YAML configuration required
- Example: `from quickscale_core.settings import *` then override

**Post-MVP Evolution (Phase 2+):**
- **Declarative Configuration** = YAML/JSON files define project structure and features (if proven useful)
- Evaluate if configuration layer adds value based on MVP usage
- **Code Generation** = CLI generates Django code from configuration specifications
- **Version Control Integration** = Configuration files tracked in Git for change management
- **Schema Validation** = Prevent invalid configurations through schema validation

**MVP Configuration Schema v1.0 (Authoritative for Phase 1):**
```yaml
schema_version: 1
project:
  name: myapp
  version: 1.0.0

# MVP: Scaffolded starter files generated (NOT a packaged theme)
# This field is preserved for future compatibility but doesn't load packages in MVP
theme: starter

# MVP: Python inheritance for backend customization
backend_extensions: myapp.extensions

# MVP: Directory-based frontend only
frontend:
  source: ./custom_frontend/
  variant: default
```

**MVP Schema Rules:**
- `modules` field: NOT supported in MVP (validation warning if present)
- `customizations` field: NOT supported in MVP (validation warning if present)
- `theme` field: Reserved for future use; doesn't load packaged themes in MVP
- `frontend`: Only `source` and `variant` keys supported

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

**CLI Integration Pattern:**
```bash
# Interactive configuration creation
quickscale init --interactive        # Creates quickscale.yml through guided wizard
quickscale validate                  # Validates configuration against schemas
quickscale generate                  # Generates Django code from configuration
quickscale preview                   # Shows what will be generated without creating files
quickscale deploy --env=staging      # Deploys based on configuration + environment
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
- **Git Subtree Operations**: Git subtree is the recommended mechanism for sharing code; the document provides manual commands and guidance for users in the MVP.
- **CLI Command Abstraction (scope clarified)**: For the MVP the CLI surface is intentionally minimal and provides only project creation (`quickscale init`). Convenience CLI wrappers that automate subtree `update`/`sync` workflows are considered Post-MVP work (Phase 2+) and will be designed after the manual workflow proves valuable. Documentation contains manual git subtree examples developers can run today.
- **Monorepo Source of Truth**: All shared code maintained in the quickscale monorepo with proper versioning
- **Automated Dependency Management (Post-MVP)**: Full automated subtree management (pulls, pushes, conflict resolution) is a Post-MVP feature; the MVP documents manual subtree usage.

# CLI Command Structure (MVP vs Post-MVP):
```bash
# MVP - ultra-minimal CLI surface (single command, no flags)
quickscale init myapp

# NOTE: Flags like `--template` or `--embed-code` are Post-MVP ideas only.
# The MVP intentionally provides a single, simple entrypoint. Convenience
# wrappers for subtree, update, and sync workflows are planned for Phase 2+.

# Post-MVP (Phase 2+): convenience wrappers for subtree operations may be added;
# examples of what those CLI helpers could look like (NOT MVP features):
# quickscale update --component=core
# quickscale update --component=modules
# quickscale update --component=themes
# quickscale sync push --component=core
# quickscale sync push --component=modules
# quickscale sync push --component=themes
```

**Git Subtree Implementation Pattern (manual commands documented for MVP):**
```bash
# Manual git subtree commands users can run today (MVP guidance)
git subtree add --prefix=quickscale_core https://github.com/quickscale/quickscale.git core --squash
git subtree pull --prefix=quickscale_core https://github.com/quickscale/quickscale.git core --squash
git subtree push --prefix=quickscale_core https://github.com/quickscale/quickscale.git core
```

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
- Post-MVP: when CLI commands are implemented to automate subtree operations, those CLI helpers must handle git subtree operations with proper error handling, clear conflict-resolution guidance, and automated tests in CI/CD. Documentation must explain failure modes and recovery steps.

**Distribution Strategy: MVP vs. Post-MVP**

**AUTHORITATIVE STATEMENT ON DISTRIBUTION:**

QuickScale uses different distribution strategies for different phases:

**MVP (Phase 1) - Git Subtree Distribution:**
- ✅ **Primary mechanism**: Git subtree for embedding quickscale_core into client projects
- ✅ **CLI commands (MVP)**: `quickscale init` (minimal project creation only). Helper commands that automate `update`/`sync` workflows are Post-MVP.
- ✅ **Benefits**: No package registry dependencies, offline development, simple workflows
- ✅ **Use cases**: Solo developers, small agencies, rapid iteration
- ❌ **Not using**: PyPI, pip packages, package registries (for core distribution)

**Post-MVP (Phase 2+) - Package Registry Distribution:**
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

**ARCHITECTURAL DECISION: MVP Backend Extension & Frontend Development**

The **MVP Backend Extension & Frontend Development** decision ensures simple project customization using standard Django patterns.

**Backend Extension Pattern (MVP):**
- Themes provide inheritance-friendly base classes (models, services, forms).
- Projects use `backend_extensions.py` for customizations via Python inheritance.
- Call `super()` in extensions for compatibility with theme updates.

**Frontend Development Pattern (MVP):**
- Directory-based frontends (`frontend.source`) for local development and customization.
- Basic variant support via `frontend.variant` configuration.
- Variants map to `variants/<name>/` folders for different UX styles.

**Configuration Rules (MVP):**
- `frontend` accepts only `source` and `variant` keys in MVP scope.
- `backend_extensions` must resolve to an importable module for customizations.
- Schema validation provides clear errors for missing directories or configuration.

**Implementation Requirements (MVP):**
- Scaffolding generates `backend_extensions.py` with inheritance stubs.
- When `frontend.source` is specified, generate `custom_frontend/` directory structure.
- Django settings template supports custom frontend template and static directories.
- Basic variant switching mechanism for different presentation styles.

**MVP Implementation Details:**

*Backend Extension Pattern (Python Inheritance):*
```python
# Generated backend_extensions.py in user project
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

*Directory-Based Frontend Pattern:*
```bash
my_project/
├── quickscale.yml              # Simple configuration
├── backend_extensions.py       # Backend customizations (generated)
├── custom_frontend/            # Custom frontend directory (generated)
│   ├── templates/             # Custom Django templates
│   ├── static/               # Custom CSS, JS, images
│   └── variants/             # Client-specific variations
│       ├── default/          # Default styling
│       └── client_a/         # Client A customizations
```

*Generated Project Structure (MVP):*
```bash
my_project/
├── quickscale.yml              # Simple configuration
├── backend_extensions.py       # Backend customizations (generated with stubs)
├── manage.py                   # Standard Django management
├── settings.py                 # Django settings (supports custom_frontend)
├── requirements.txt            # Pinned dependencies
├── custom_frontend/            # Custom frontend directory (optional)
│   ├── templates/             # Custom Django templates
│   │   ├── base.html         # Base template override
│   │   └── components/       # Reusable components
│   ├── static/               # Custom CSS, JS, images
│   │   ├── css/main.css      # Main stylesheet
│   │   └── js/app.js         # Main JavaScript
│   └── variants/             # Client variant support
│       ├── default/          # Default styling
│       │   ├── templates/
│       │   └── static/
│       └── client_a/         # Example client variant
│           ├── templates/
│           └── static/
```

**MVP Core Features:**
1. **Backend Extension Scaffolding**: Generated `backend_extensions.py` with inheritance stubs
2. **Directory-Based Frontend**: Optional `custom_frontend/` with template and static directories  
3. **Basic Variant Support**: Simple variant switching via `frontend.variant` configuration
4. **Django Settings Integration**: Automatic template and static file directory configuration
5. **Standard Django Patterns**: No custom framework overhead, pure Django approach

**MVP Limitations:**
- ❌ **No multi-client config array** - Just single `variant` string for now
- ❌ **No automated API contract versioning** - Manual compatibility for MVP  
- ❌ **No registry or marketplace** - Directory-based development only
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
  # 'quickscale_modules.admin',      # Enhanced admin interface
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

QuickScale uses **PEP 420 implicit namespace packages** for modules and themes to enable independent distribution while sharing import namespaces.

**Namespace Package Structure (Post-MVP):**
- `quickscale_modules/` - NO `__init__.py` at this level (PEP 420 namespace)
  - Individual modules like `auth/`, `payments/` each have their own `__init__.py`
- `quickscale_themes/` - NO `__init__.py` at this level (PEP 420 namespace)
  - Individual themes like `starter/`, `todo/` each have their own `__init__.py`

**Import Paths:**
```python
# Correct - using dotted namespace
from quickscale_modules.auth import models
from quickscale_themes.starter import business

# Incorrect - will fail without namespace __init__.py
from quickscale_modules import auth  # NO - auth is not in __init__.py
```

**Why PEP 420 Namespaces:**
- ✅ Independent distribution of modules/themes
- ✅ No conflicts between separately installed packages
- ✅ Standard Python namespace pattern
- ✅ Supports third-party extensions

**MVP Note:** For Phase 1, package namespacing is not implemented. Generated projects contain only `quickscale_core` as a regular package. Namespace packages become relevant in Phase 2+ when modules and themes are implemented as separate packages.

**Clarification (MVP vs Post-MVP):**
While the long-term plan is to use PEP 420 implicit namespace packages for independently distributed modules/themes, this is a Post-MVP decision. During the MVP (Phase 1) the repository and generated projects use regular Python packages (with `__init__.py`) for simplicity and predictability. When modules/themes are promoted to separately distributed packages in Phase 2+, maintainers should adopt the PEP 420 namespace pattern and update the documentation and packaging accordingly.

## Packaging & namespaces (summary)

Keep packaging guidance short and easy to find: for the MVP treat `quickscale_core` as a normal, single package (regular `__init__.py`, simple editable installs, and easy subtree embedding). For Phase 2+ where modules/themes are released independently, adopt PEP 420 implicit namespace packages for `quickscale_modules` and `quickscale_themes` so independent wheels can contribute subpackages under the same logical namespace (use `find_namespace_packages()` in `pyproject.toml`). This approach preserves simple developer experience in MVP while enabling an ecosystem of independently-versioned modules/themes later.

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
