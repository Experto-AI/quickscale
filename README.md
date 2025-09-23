
# 🚀 QuickScale

---

## QuickScale: Compose your Django SaaS.

QuickScale is a **composable Django SaaS foundation** with a stable core, reusable backend modules, and starting point themes—delivering Python-native simplicity and development acceleration (not turnkey vertical products).

**This is a complete architectural redesign.**

---

## What is QuickScale?

QuickScale is a **composable Django SaaS foundation** that helps you build custom business applications faster:

### What You Get:
- **Composable "Library-Style" Structure:**
- **QuickScale Core** = Python's standard library (project scaffolding + configuration system + utilities)
- **Backend Modules** = Built on proven Django foundations (django-allauth for auth, enhanced admin, dj-stripe for `payments`; future: `notifications`, `backup`, `analytics`)
- **Starting Point Themes** = Foundation applications to customize (e.g., `starter`, `todo`)
- **Multiple Frontends** = Bundled within each theme (e.g., `frontend_htmx/`, `frontend_react/`, `frontend_vue/`)

### What You Build:
- **Your Custom Business Logic**: Unique to your application
- **Your Brand & UX**: Custom styling and user experience  
- **Your Specific Features**: Beyond the foundation components
- **Your SaaS Application**: Powered by QuickScale components

### Development Flow:
1. `quickscale create myapp --theme=starter --frontend=htmx`
2. Customize models and business logic for your needs
3. Override frontend templates and styling
4. Add custom features and modules
5. Deploy your unique SaaS application

### Architecture Evolution:
- **From:** QuickScale Legacy (static project generator) → Independent Django projects
- **To:** QuickScale Core + Modules + Themes (with multiple Frontends)
- **Benefits:**
	- Shared updates and security fixes
	- Modules built on proven Django foundations (battle-tested reliability)
	- Starting point themes requiring customization
	- **Client presentation flexibility** (same business logic, different frontends per client)
	- Technology-agnostic frontends per theme (HTMX, React, Vue)
	- Development acceleration, not end products
	- Simple, reliable deployment (creation-time assembly)

**Learn more:** See [QUICKSCALE.md](./QUICKSCALE.md), [ROADMAP.md](./ROADMAP.md), and [DECISIONS.md](./DECISIONS.md) for the formal architecture decision.

---

## Fresh Start: Clean Slate

QuickScale starts from a clean directory, with only essential files and a new composable architecture. All previous code is preserved in `quickscale-legacy/` (now called QuickScale Legacy) for reference.

**Key Principles:**
- Django-native patterns (no runtime loading)
- Clear separation of concerns (logic vs. presentation)
- PyPI-distributed modules and themes
- Community-first, Python-inspired ecosystem
- Configuration-driven project definition (YAML/JSON-based)

## QuickScale Philosophy: Enabler, Not Complete Solutions

QuickScale provides the foundation and building blocks, not complete vertical solutions:

❌ **What QuickScale is NOT:**
- Complete e-commerce / CRM / real estate platform
- Ready-to-use vertical SaaS
- One-size-fits-all template pack
- Runtime plugin loader (no WordPress-style activation)

✅ **What QuickScale IS:**
- Foundation for building custom SaaS applications
- Modules built on proven Django foundations (dj-stripe, django-allauth, etc.)
- Starting point themes you must extend (models, business logic, UX)
- Development accelerator, not an end product

## Available Theme Examples

QuickScale provides two foundational themes as starting points (distributed via PyPI):

### **Starter Theme (Blank Foundation)**
- **Purpose**: Minimal foundation for custom business applications
- **Includes**: Project structure, configuration examples, module integration patterns
- **Use Case**: When building unique SaaS applications from scratch
- **Command**: `quickscale create myapp --theme=starter --frontend=htmx --modules=auth,payments`

### **TODO Theme (Reference Implementation)**  
- **Purpose**: Complete example showing QuickScale patterns and capabilities
- **Includes**: Task management models, REST API, multiple frontends
- **Use Case**: Learning QuickScale architecture, reference for custom development
- **Command**: `quickscale create myapp --theme=todo --frontend=htmx`

Both themes are **starting points requiring customization** for your specific business needs.

---

## Development Approaches

QuickScale supports two complementary approaches for project creation (both produce the same structure):

### **1. Imperative CLI Commands**
```bash
quickscale create mystore --theme=starter --frontend=htmx --modules=auth,payments,billing
```
(`create` is an imperative shortcut that internally generates a transient config then calls the declarative engine.)

### **2. Configuration-Driven (Declarative)**
```bash
quickscale init --interactive  # Creates quickscale.yml
quickscale generate           # Generates project from config
```

**Canonical Configuration Schema v1 (`quickscale.yml`)** (authoritative – matches DECISIONS.md):
```yaml
schema_version: 1
project:
  name: mystore
  version: 1.0.0

theme: starter  # starting point (must customize)

modules:
  auth:
    provider: django-allauth  # built on django-allauth foundations
  payments:
    provider: stripe          # built on dj-stripe foundations
  billing:
    provider: stripe          # built on proven Django billing foundations
  # notifications: { provider: sendgrid }  # built on django-anymail
  # backup: { provider: aws, schedule: daily }

frontend:
  technologies: [htmx, react]  # theme may support multiple; choose for your project
  primary: htmx
  variant: modern-dark

customizations:
  models:
    - name: Product
      fields:
        - { name: name, type: string }
        - { name: price, type: decimal }
        - { name: category, type: string }
    - name: Order
      fields:
        - { name: user, type: foreign_key, target: User }
        - { name: products, type: many_to_many, target: Product }
        - { name: total, type: decimal }
  business_rules:
    - "Products require approval before listing"
    - "Orders over $1000 need manager approval"
```

**Client Customization Example (Different business apps from same foundation)**:
```yaml
# E-commerce SaaS
project: mystore
theme: starter
modules:
  auth: { provider: django-allauth }
  admin: { enabled: true }
  payments: { provider: stripe }
  billing: { provider: stripe }
frontend:
  technologies: [htmx, react]
customizations:
  models: [Product, Order, Cart]

---
# Blog/Content Site (no auth needed)
project: myblog  
theme: starter
modules:
  # No auth/admin needed for public blog
  # Could add: content management module
frontend:
  technologies: [htmx]
customizations:
  models: [Post, Category, Tag]

---
# API-only Service
project: myapi
theme: starter  
modules:
  auth: { provider: django-allauth }  # for API authentication
  # No admin frontend needed
frontend:
  technologies: []  # API-only, no frontend
customizations:
  models: [DataModel, APIKey]
```

Deprecated config keys: `features`, `components`, singular `technology` (use `technologies` + `primary`). These will be rejected by future `quickscale validate`.

**Benefits**: Version control friendly, non-developer accessible, automated CI/CD integration, supports multi-frontend projects.

### Module Examples: True Modularity
| Use Case | Core | Auth | Admin | Payments | Billing | Notes |
|----------|------|------|-------|----------|---------|--------|
| Public Blog | ✅ | ❌ | ❌ | ❌ | ❌ | No users needed |
| API Service | ✅ | ✅ | ❌ | ❌ | ❌ | Auth for API keys |
| E-commerce SaaS | ✅ | ✅ | ✅ | ✅ | ✅ | Full featured app |
| Static Tool | ✅ | ❌ | ❌ | ❌ | ❌ | Just utilities |

### Module Boundary: Billing vs Payments (Built on Django Foundations)
| Concern | Billing Module | Payments Module |
|---------|----------------|-----------------|
| Django Foundation | Built on proven billing apps | Built on dj-stripe |
| Role | Plans, subscriptions, entitlements | Charge execution, refunds |
| Models | Plan, Subscription, Entitlement | Transaction, WebhookEvent |
| External API | Billing provider (Stripe Billing) | Payment provider (Stripe Payments) |
| Provides | Entitlement checks, decorators | Payment service classes |
| Excludes | Direct charge execution | Subscription lifecycle logic |

### Dependency Injection Policy
Production code uses direct imports; tests may inject alternative service objects into constructors for isolation. No service containers or runtime plugin registries.

### Hook System
Deferred until a later phase (initial releases use explicit service calls). A lightweight dispatcher will be introduced and existing integration points refactored gradually.

---

