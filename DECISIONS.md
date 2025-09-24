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

High-level decisions (what)
---------------------------

**ARCHITECTURAL DECISION: Library-Style Backend Modules**

The **Library-Style Backend Modules** architecture for development acceleration and customization.

**Core Architecture Concept:**
- **Backend Modules** = Built on proven Django foundations (dj-stripe, django-allauth, etc.) providing reusable functionality like backup, analytics, payments
- **Starting Point Themes** = Foundation Django applications that developers customize for their specific business needs
- **Directory-Based Frontends** = Custom frontend development via directory structure

**QuickScale as Development Foundation:**
QuickScale provides building blocks and acceleration tools, not complete business solutions:
- **Foundation (Core)**: Project scaffolding, configuration system, extension points, common utilities (hook system deferred to later phase)
- **Backend Modules**: Built on proven Django foundations (django-allauth for auth, enhanced Django admin, dj-stripe, etc.) providing reusable functionality packages such as auth, admin, payments, billing, notifications, backup, analytics
- **Themes**: Starting points that require customization for specific business needs
- **Frontends**: Directory-based presentation layer for theme customization

**Architecture Structure:**
```
quickscale_core/                    # Foundation (like Python stdlib)

quickscale_modules/                 # Backend libraries built on Django foundations
  ├── auth/                        # Built on django-allauth (authentication & user management)
  ├── admin/                       # Enhanced Django admin interface
  ├── payments/                    # Built on dj-stripe (first official)
  ├── billing/                     # Built on proven billing foundations  
  ├── notifications/               # Built on django-anymail (future)
  └── analytics/                   # (future) Analytics functionality library

quickscale_themes/                  # Starting point applications (customize for your needs)
  ├── starter/
  │   ├── models.py               # Foundation models - add your custom models
  │   ├── business.py             # Example patterns - implement your logic
  │   └── frontend/               # Basic frontend foundation - customize for your needs
  └── todo/
      ├── models.py               # Task management example - reference for custom development
      ├── business.py             # Complete workflows - learn from for your application
      └── frontend/               # Full implementation - see patterns for your app
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

**Package Distribution Pattern (Authoritative):**
```bash
# Backend modules (libraries)
pip install quickscale-module-auth           # Authentication & user management (django-allauth)
pip install quickscale-module-admin          # Enhanced Django admin interface
pip install quickscale-module-payments       # Transaction execution (charges, refunds)
pip install quickscale-module-billing        # Subscription plans, entitlements
pip install quickscale-module-notifications  # future
pip install quickscale-module-backup         # future
pip install quickscale-module-analytics      # future

# Starting point themes (distributed packages you MUST customize)
pip install quickscale-theme-starter         # Minimal foundation
pip install quickscale-theme-todo            # Reference implementation

# Themes are customized by developers for specific applications.
```

**Canonical Package Naming Matrix**

| Concern | PyPI Name | Import Path | Django App Label |
|---------|-----------|-------------|------------------|
| Core | quickscale-core | quickscale_core | quickscale_core |
| Auth Module | quickscale-module-auth | quickscale_modules.auth | quickscale_modules_auth |
| Admin Module | quickscale-module-admin | quickscale_modules.admin | quickscale_modules_admin |
| Payments Module | quickscale-module-payments | quickscale_modules.payments | quickscale_modules_payments |
| Billing Module | quickscale-module-billing | quickscale_modules.billing | quickscale_modules_billing |
| Starter Theme | quickscale-theme-starter | quickscale_themes.starter | quickscale_themes_starter |
| TODO Theme | quickscale-theme-todo | quickscale_themes.todo | quickscale_themes_todo |

Rules:
- PyPI names use hyphens: `quickscale-module-<name>` / `quickscale-theme-<name>`.
- Import paths use dotted namespaces: `quickscale_modules.<name>`, `quickscale_themes.<name>`.
- Django app labels are fully qualified with namespace prefix underscore joined: `quickscale_modules_<name>` & `quickscale_themes_<name>` to avoid collisions.
- Shared namespace roots (`quickscale_modules`, `quickscale_themes`) are PEP 420 implicit (no `__init__.py`).

1. Layout
   - Place first-party packages at repository root. Example top-level folders:
     - `quickscale_core/`
     - `quickscale_cli/`
     - `quickscale_modules/` (contains per-module packages)
     - `quickscale_themes/` (contains per-theme packages, including their frontends)
   - Each package uses an internal `src/` layout: code lives in `src/<importable_name>/...`.

2. Namespaces & package naming
   - PyPI package name vs import name mapping:
     - Example: PyPI `quickscale-core` → Python import `quickscale_core`.
   - Theme/module distributions provide subpackages under shared namespaces:
     - `quickscale_themes.<name>`
     - `quickscale_modules.<name>`
   - Use PEP 420 implicit namespace packages (no `__init__.py`) for these shared namespaces. No fallback to pkgutil-style namespace packages.

3. CLI
   - The CLI is a separate package: `quickscale_cli/`.
   - CLI responsibilities:
     - Project creation (creation-time assembly)
     - Package discovery & validation
     - Scaffolding generators for themes/modules
   - Keep the CLI independent of the core runtime to allow early-stage project creation (bootstrap without needing the core preinstalled).

4. Testing
   - Unit tests live inside each package at `package/tests/` (e.g., `quickscale_core/tests/`).
   - Integration tests that cover cross-package interactions (e.g., theme using a module) live in the top-level `integration_tests/` directory.
   - Tests must not be placed inside the `src/` package tree.

5. Packaging & build
   - Each package has its own `pyproject.toml` using a modern build backend (recommended: `hatchling`).
   - Packages should support editable installs for development (`pip install -e ./quickscale_core`).
   - Each theme/module must declare compatibility metadata in `pyproject.toml` (example key in `[project.metadata.quickscale]`: `core-compatibility = ">=2.0.0,<3.0.0"`).

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

**Core Configuration Concept:**
- **Declarative Configuration** = YAML/JSON files define project structure and features
- **Code Generation** = CLI generates Django code from configuration specifications
- **Version Control Integration** = Configuration files tracked in Git for change management
- **Schema Validation** = Prevent invalid configurations through schema validation

**Canonical Configuration Schema v1 (Authoritative):**
```yaml
schema_version: 1
project:
  name: mystore
  version: 1.0.0

theme: starter  # starting point theme (must be customized)
backend_extensions: myproject.backend_extensions  # Python inheritance entrypoint

modules:
  payments:
    provider: stripe   # charge execution
  billing:
    provider: stripe   # subscription & entitlement logic
  # notifications: { provider: sendgrid }
  # backup: { provider: aws, schedule: daily }

frontend:
  source: ./custom_frontend/    # Directory-based frontend (MVP)
  variant: default              # Basic variant support

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

Deprecated fields/structures: `features`, `components`, `technologies`, `primary`, or any `frontend` keys outside `source` and `variant` (MVP scope). These MUST NOT appear in new configs (validation error).

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
