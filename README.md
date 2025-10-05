
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

QuickScale is a **composable Django framework** for building client SaaS applications. Start with a stable core, add reusable modules, customize themes, and deploy faster—while maintaining the flexibility to create commercial extensions and build a community ecosystem.

---

## What is QuickScale?

QuickScale is a **composable Django framework** designed for **solo developers and development agencies** who build multiple client SaaS applications. It provides a stable foundation with reusable components, enabling you to:

- **Build once, reuse everywhere**: Create modules and themes that work across all your client projects
- **Maintain commercial flexibility**: Keep core components open source while offering premium modules/themes via subscriptions
- **Scale your development business**: Standardize your tech stack and accelerate client project delivery
- **Build a community ecosystem**: Share and monetize your extensions while benefiting from community contributions

### Primary Use Cases:
- **Solo Developer**: Build client projects faster with reusable components you maintain
- **Development Agency**: Standardize your tech stack across multiple client engagements  
- **Commercial Extension Developer**: Create and sell premium modules/themes
- **Open Source Contributor**: Extend the ecosystem with new modules and themes

### Development Flow (MVP)
1. `quickscale init myapp --template=saas --embed-code`
  - NOTE: The `quickscale` CLI is part of the MVP and can be used to create the minimal/core project scaffolding. See `quickscale_cli/` for the CLI package and installation guidance.
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

## Scaffolded Starter Files

**MVP Note**: QuickScale generates **scaffolded starter files** (NOT packaged themes) in your project. These generated files provide a practical starting point with templates, backend extension stubs, and frontend structure. The full theme package system and marketplace remain Post-MVP.

### **MVP: Scaffolded Starter Files (Generated in Your Project)**
- **Purpose**: Immediate runnable project structure demonstrating extension patterns
- **Includes**: Base templates, `backend_extensions.py` stub, `custom_frontend/` directory structure
- **Location**: Generated directly in your project (not installed as a package)
- **Customization**: Full ownership - modify these files as needed for your project

### **Post-MVP: Theme Packages (Future)**
- **Purpose**: Installable theme packages with reusable business logic and patterns
- **Examples**:
  - `quickscale_themes/starter`: Minimal foundation package
  - `quickscale_themes/todo`: Reference implementation with task management
- **Distribution**: Pip-installable packages from QuickScale repository
- **Use Case**: Consistent starting points across multiple projects, community sharing

**MVP Scope**: QuickScale CLI generates Django projects with scaffolded files. Packaged themes and module ecosystem are Post-MVP features.

---

## Development Approaches

QuickScale supports two complementary approaches for project creation (both produce the same structure):

### **1. Imperative CLI Commands**
```bash
quickscale init mystore --template=saas --embed-code
```
(`init` creates a new project with git subtree integration for code sharing.)

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
backend_extensions: myapp.extensions     # Python inheritance for customization

frontend:
  source: ./custom_frontend/               # Directory-based frontend (MVP)
  variant: default                         # Basic variant support
```

This configuration assumes `myapp/extensions.py` exists for backend customization and `custom_frontend/` directory for frontend development.

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

## CLI Reference

### **QuickScale CLI Commands**

The `quickscale` CLI provides commands for project creation and code sharing management.

#### **Project Creation**

```bash
quickscale init <project_name> --template=<template_type> --embed-code
```

**Arguments:**
- `<project_name>`: Name of your new project (required)

**Flags:**
- `--template=<type>`: Template type to use for project generation
  - `saas`: SaaS application template (MVP default)
  - Future: Additional templates may be added Post-MVP

- `--embed-code`: Use git subtree to embed QuickScale code directly in your project
  - Copies `quickscale_core` into your project via git subtree
  - Enables pulling updates from QuickScale repository
  - Alternative: External dependency (not implemented in MVP)
  - **MVP Default**: This flag is required for MVP implementation

**Example:**
```bash
quickscale init myapp --template=saas --embed-code
```

This creates a new Django project named `myapp` with QuickScale embedded via git subtree.

#### **Update Commands (MVP)**

```bash
quickscale update <project_name>        # Pull latest QuickScale updates
quickscale sync push <project_name>     # Push improvements back to QuickScale
```

See [Git Subtree Distribution](./DECISIONS.md#distribution-strategy-mvp-vs-post-mvp) for details.

---

## Learn More

- **[DECISIONS.md](./DECISIONS.md)** - Technical specifications and implementation rules
- **[QUICKSCALE.md](./QUICKSCALE.md)** - Strategic vision and competitive positioning
- **[ROADMAP.md](./ROADMAP.md)** - Development roadmap and implementation plan

