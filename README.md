
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
1. `quickscale init myapp`
   - Generates minimal Django "Hello World" project
1. `quickscale init myapp`
  - Generates minimal Django "Hello World" project
  - Optionally embeds `quickscale_core` via git subtree for shared utilities
   - You own and customize the generated project completely
2. Add your custom Django apps and features
3. Optionally: Inherit base settings from `quickscale_core` if embedded
4. Build your unique client application
5. Deploy using standard Django deployment patterns

Note: QuickScale's chosen MVP approach is the "Personal Toolkit" (a.k.a. the git-subtree workflow). The Personal Toolkit approach is integrated as the MVP implementation strategy: generate a project with `quickscale init`, optionally embed `quickscale_core` via git subtree, and extract reusable code into `quickscale_modules/` as you build real client projects. See `DECISIONS.md` and `ROADMAP.md` for practical workflows and examples.

### What MVP Generates
```bash
$ quickscale init myapp

myapp/
├── manage.py                    # Standard Django
├── myapp/
│   ├── __init__.py
│   ├── settings.py             # Can import from quickscale_core
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── templates/
│   └── index.html              # Simple homepage
├── static/
│   └── css/
├── requirements.txt            # Django + essentials
└── README.md

# Optional: quickscale/ embedded via git subtree
└── quickscale/
    └── quickscale_core/        # Basic utilities if you want them
```

**Key Point**: The generated project is **yours to own and modify**. QuickScale just gives you a good starting point.

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

## From Template to Client Project

**MVP Philosophy**: Generate a starter Django project that you own and customize completely for each client.

### **MVP: Simple Starter Generation**
- **Purpose**: Fast "Hello World" Django project generation
- **What You Get**: Standard Django project structure with optional `quickscale_core` utilities
- **Ownership**: 100% yours - modify anything, no restrictions
- **Customization**: Extend for your specific client needs (models, views, templates, etc.)
- **Updates**: Optional - pull utility improvements via git subtree if you want them

### **Post-MVP: Extracting Reusable Patterns**
As you build multiple client projects, you'll naturally extract reusable patterns:
- **Module Packages**: Auth, payments, billing modules (when you've built them 2-3 times)
- **Theme Packages**: Common business logic patterns (when proven across clients)
- **Distribution**: Git subtree initially, PyPI for commercial/community later

**Evolution Pattern:**
```
MVP:        Generate starter → Customize for Client A → Ship
Phase 2:    Extract pattern → Create module → Share via git subtree
Phase 3:    Package module → Distribute via PyPI → Build community
```

**MVP Scope**: Simple project generation. Modules and themes emerge organically from real client work.

---

## Development Approach (MVP)

QuickScale MVP uses a **simple imperative CLI** for fast project generation:

### **MVP: Simple CLI Command**
```bash
quickscale init myapp
```

**What This Does:**
1. Creates Django project structure
2. Generates minimal "Hello World" application
3. Optionally embeds `quickscale_core` via git subtree
4. Sets up requirements.txt with Django + essentials
5. Creates README with next steps

**No templates, no configuration files, no complexity.** Just: `quickscale init myapp` and start coding.

### **Post-MVP: Configuration-Driven (Optional)**
If proven useful by MVP usage, we may add declarative configuration:

```bash
quickscale init --interactive  # Creates quickscale.yml
quickscale generate           # Generates project from config
```

```yaml
# Potential Post-MVP configuration (TBD)
project:
  name: myapp
  modules: [auth, payments]    # When module packages exist
```

**MVP Decision**: Configuration is **optional/TBD**. Start with simple CLI, evaluate if config layer adds value based on real usage.

Practical settings example

If you embed `quickscale_core` into a client project (via git subtree), a minimal settings pattern looks like:

```python
# myapp/config/settings/base.py
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / 'quickscale'))

# Import QuickScale base settings if available
try:
  from quickscale_core.settings import *  # noqa: F401,F403
except Exception:
  pass

# Client overrides
DEBUG = True
```

---

## CLI Reference (MVP)

### **QuickScale CLI - Simple and Minimal**

#### **Project Creation**

```bash
quickscale init <project_name>
```

**That's it.** No flags, no options, no complexity.

**What It Does:**
1. Creates Django project structure
2. Generates minimal "Hello World" application  
3. Optionally embeds `quickscale_core` utilities via git subtree
4. Ready to code in 30 seconds

**Example:**
```bash
quickscale init myapp
cd myapp
python manage.py runserver
# Visit http://localhost:8000 - Hello World!
```

#### **Update Commands (For Git Subtree Users)**

If you embedded `quickscale_core` via git subtree:

```bash
cd myapp
git subtree pull --prefix=quickscale https://github.com/Experto-AI/quickscale.git main --squash
```

**Post-MVP**: We may add convenience commands like `quickscale update` if git subtree usage proves common.

**Philosophy**: Keep MVP CLI simple. Add commands only when proven necessary by real usage.

---

## Learn More

- **[DECISIONS.md](./DECISIONS.md)** - Technical specifications and implementation rules
- **[QUICKSCALE.md](./QUICKSCALE.md)** - Strategic vision and competitive positioning
- **[ROADMAP.md](./ROADMAP.md)** - Development roadmap and implementation plan

