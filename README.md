
# 🚀 QuickScale

<!-- 
README.md - User-Focused Introduction

PURPOSE: This file serves as the first contact point for users, developers, and evaluators visiting the QuickScale project.

CONTENT GUIDELINES:
- Keep content user-facing and accessible to newcomers
- Focus on "what" and "how to get started" rather than "why" or technical details  
- Include quick examples and development workflows
- Avoid deep architectural explanations (those belong in DECISIONS.md)
- Avoid competitive analysis or strategic context (those belong in QUICKSCALE.md)
- Maximum length: ~200 lines to ensure quick readability
- Link to other documents for detailed information

TARGET AUDIENCE: New users, potential adopters, GitHub visitors, developers evaluating QuickScale
-->

---

## QuickScale: Compose your Django SaaS.

QuickScale is a **composable Django SaaS foundation** with a stable core, reusable backend modules, and starting point themes—delivering Python-native simplicity and development acceleration (not turnkey vertical products).

---

## What is QuickScale?

QuickScale is a **composable Django SaaS foundation** that helps you build custom business applications faster:

### What You Get:
- **Composable "Library-Style" Structure:**
- **QuickScale Core** = Python's standard library (project scaffolding + configuration system + utilities)
- **Backend Modules** = Built on proven Django foundations (django-allauth for auth, enhanced admin, dj-stripe for `payments`; future: `notifications`, `backup`, `analytics`)
- **Starting Point Themes** = Foundation applications to customize (e.g., `starter`, `todo`)
- **Directory-Based Frontends** = Custom frontend development via directory structure

### What You Build:
- **Your Custom Business Logic**: Unique to your application
- **Your Brand & UX**: Custom styling and user experience  
- **Your Specific Features**: Beyond the foundation components
- **Your SaaS Application**: Powered by QuickScale components

### Development Flow:
1. `quickscale create myapp --theme=starter --frontend=htmx`
2. Extend the generated `backend_extensions.py` to customise theme models, services, and workflows while inheriting future updates
3. Wire up your presentation layer: edit the scaffolded `custom_frontend/` directory for custom frontend development
4. Add custom features and modules
5. Deploy your unique SaaS application

### Custom Frontend Quick Start (MVP)
- Open `backend_extensions.py` and subclass the theme components you need to customize—keep changes additive and call `super()` for compatibility.
- Edit `custom_frontend/templates/` and `custom_frontend/static/` to customize your frontend presentation layer.
- Use basic variants by creating directories under `custom_frontend/variants/<name>/` for different UX styles.

## Key Benefits

- **Shared Updates**: Get security fixes and improvements automatically
- **Proven Foundations**: Built on battle-tested Django packages (django-allauth, dj-stripe)
- **Starting Points**: Themes provide foundations you customize for your business
- **Flexible Frontends**: Same backend, multiple client presentations
- **Simple Deployment**: Standard Django deployment patterns

## QuickScale Philosophy: Enabler, Not Complete Solutions

QuickScale provides the foundation and building blocks, not complete vertical solutions:

✅ **What QuickScale IS:**
- Foundation for building custom SaaS applications
- Modules built on proven Django foundations (dj-stripe, django-allauth, etc.)
- Starting point themes you must extend (models, business logic, UX)
- Development accelerator, not an end product

❌ **What QuickScale is NOT:**
- Complete e-commerce / CRM / real estate platform
- Ready-to-use vertical SaaS
- One-size-fits-all template pack
- Runtime plugin loader (no WordPress-style activation)

## Available Theme Examples

QuickScale provides two foundational themes as starting points:

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

**MVP Configuration Schema (`quickscale.yml`)**:
```yaml
schema_version: 1
project:
  name: mystore
  version: 1.0.0

theme: starter                             # Base theme
backend_extensions: mystore.extensions     # Python inheritance for customization

frontend:
  source: ./custom_frontend/               # Directory-based frontend (MVP)
  variant: default                         # Basic variant support
```

This configuration assumes `mystore/extensions.py` exists for backend customization and `custom_frontend/` directory for frontend development.

**Simple Usage Example**:
```yaml
# Basic SaaS Application
project:
  name: myapp
  version: 1.0.0
  
theme: starter
backend_extensions: myapp.extensions

frontend:
  source: ./custom_frontend/
  variant: default
```

**Benefits**: Version control friendly, simple configuration, supports directory-based frontend development.

---

## Learn More

- **[DECISIONS.md](./DECISIONS.md)** - Technical specifications and implementation rules
- **[QUICKSCALE.md](./QUICKSCALE.md)** - Strategic vision and competitive positioning  
- **[ROADMAP.md](./ROADMAP.md)** - Development roadmap and implementation plan

