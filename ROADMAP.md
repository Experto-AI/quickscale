# QuickScale Development Roadmap

<!-- 
ROADMAP.md - Development Timeline and Implementation Plan

PURPOSE: This document outlines the development timeline, implementation phases, and specific tasks for building QuickScale.

CONTENT GUIDELINES:
- Organize tasks by phases with clear deliverables and success criteria
- Include specific implementation tasks with technical requirements
- Provide timeline estimates and dependency relationships
- Track progress and update status as work is completed
- Focus on "when" and "what tasks" rather than "why" or "what"
- Reference other documents for context but avoid duplicating their content

WHAT TO ADD HERE:
- New development phases and milestone planning
- Specific implementation tasks and acceptance criteria
- Timeline updates and progress tracking
- Resource allocation and team assignments
- Risk mitigation strategies and contingency plans
- Testing strategies and quality gates

WHAT NOT TO ADD HERE:
- Strategic rationale or competitive analysis (belongs in QUICKSCALE.md)
- Technical specifications or architectural decisions (belongs in DECISIONS.md)
- User documentation or getting started guides (belongs in README.md)

TARGET AUDIENCE: Development team, project managers, stakeholders tracking progress
-->

---

## 🚀 **EVOLUTION-ALIGNED ROADMAP**

This roadmap follows the **"personal toolkit first, community platform later"** strategy outlined in [QUICKSCALE.md](./QUICKSCALE.md).

### **Strategic Approach**
- **Phase 1 (MVP)**: Personal toolkit for client projects (CONTENDING-ALTERNATIVE approach)
- **Phase 2+**: Organic evolution to community platform based on proven patterns
- **Key Principle**: Extract from real client work, don't build speculatively

### **📋 Current State Assessment**
- ✅ **Evolution Strategy Defined**: Start simple, grow organically
- ✅ **MVP Scope Clarified**: Simple CLI + project scaffolding + git subtree
- ✅ **Legacy Backup Available**: Complete v0.41.0 preserved in `quickscale-legacy/`
- ✅ **Post-MVP Path Clear**: Module/theme packages when proven necessary
- 🔄 **Ready to Build**: Clear MVP requirements established

### **What Changed from Original Plan**
- **Original**: Build complete ecosystem with modules, themes, marketplace upfront
- **New MVP**: Simple toolkit for YOUR projects first
- **Rationale**: Avoid "never-ending MVP" by starting minimal and extracting patterns from real client work

---

## **Phase 1: MVP - Personal Toolkit** 

**🎯 Objective**: Build a simple project generator that creates Django "Hello World" projects you can use for client work immediately.

**MVP Scope**: Minimal CLI + Basic scaffolding + Optional git subtree

**Success Criteria**: 
- `quickscale init myapp` generates working Django project in < 30 seconds
- Generated project can be customized for any client need
- Optional: Can share code improvements via git subtree across YOUR projects

Integration note: The Personal Toolkit approach is adopted for Phase 1. Key practical steps:

- Create client projects with `quickscale init myapp`.
- When a feature proves reusable across 2+ clients, extract it into `quickscale_modules/<name>/` in your quickscale repo and commit.
- Use git subtree to add or pull modules into client repos (manual commands documented in `SCAFFOLDING.md` and `DECISIONS.md`). See `README.md` for a concise overview.

**NOT in MVP:**
- ❌ Module packages (auth, payments, billing)
- ❌ Theme packages  
- ❌ YAML configuration system
- ❌ PyPI distribution
- ❌ Marketplace features
- ❌ Multiple template options

### **Phase 1.1: Foundation Setup** 

#### **1.1.1 Legacy Analysis (FIRST)**
**Priority**: Understand what to preserve before building new architecture

- [ ] **Analyze quickscale-legacy directory structure and patterns**
- [ ] **Extract valuable Docker deployment configurations** 
- [ ] **Document legacy CLI patterns worth preserving**
- [ ] **Identify legacy utility functions for quickscale_core**
- [ ] **Document legacy patterns to AVOID in new architecture**
- [ ] **Create legacy-analysis.md with findings**

**Deliverable**: `docs/legacy-analysis.md` with clear "keep" vs "avoid" guidance

#### **1.1.2 Repository Structure Setup**
**Priority**: Create basic package structure following DECISIONS.md

- [ ] **Create `quickscale_core/` package directory with src layout**
- [ ] **Setup `quickscale_core/pyproject.toml` with MVP dependencies only**
- [ ] **Create `src/quickscale_core/` source directory structure**
- [ ] **Create `quickscale_core/tests/` directory outside src/**
- [ ] **Create `schemas/` directory for configuration schemas**
- [ ] **Create `docs/` and `examples/` directories**

**Deliverable**: Basic directory structure per DECISIONS.md standards

```
quickscale/
├── quickscale_core/                 # Core package root  
│   ├── pyproject.toml              # MVP dependencies only
│   ├── src/quickscale_core/        # Source code (src layout)
│   │   ├── __init__.py
│   │   ├── config/                 # Configuration system
│   │   ├── scaffold/               # Project scaffolding  
│   │   └── utils/                  # Common utilities
│   └── tests/                      # Unit tests (outside src/)
├── schemas/                        # YAML schema definitions
├── docs/                           # Documentation
└── examples/                       # Example configurations
```

#### **1.1.3 MVP Scaffolding Templates (SIMPLE)**
**Priority**: Create minimal Jinja2 templates for Django project generation

- [ ] **Create basic Django project template structure**
- [ ] **Create `manage.py` template**
- [ ] **Create `settings.py` template with optional quickscale_core imports**
- [ ] **Create `urls.py` template**
- [ ] **Create simple homepage template (Hello World)**
- [ ] **Create `requirements.txt` template (Django + essentials)**

**MVP Templates Needed**:
```
quickscale_core/scaffold/templates/
├── manage.py.j2                 # Standard Django manage.py
├── settings.py.j2               # Settings with optional imports
├── urls.py.j2                   # Basic URL configuration
├── wsgi.py.j2                   # WSGI config
├── templates/
│   └── index.html.j2           # Simple homepage
└── requirements.txt.j2          # Django + minimal deps
```

**NO YAML Configuration in MVP**: Configuration system is deferred to Post-MVP (TBD if needed).

**Deliverable**: Working templates that generate minimal Django project

### **Phase 1.2: Core Implementation**

#### **1.2.1 Project Scaffolding System (MVP - SIMPLIFIED)**
**Priority**: Generate minimal Django projects

- [ ] **Create `ProjectGenerator` class for basic scaffolding**
- [ ] **Implement template rendering with Jinja2**
- [ ] **Generate standard Django project structure**
- [ ] **Add simple homepage (Hello World)**
- [ ] **Generate requirements.txt with Django**
- [ ] **Add README with next steps**

```python
# quickscale_core/scaffold/generator.py
class ProjectGenerator:
    def generate(self, project_name: str, output_path: Path):
        """Generate minimal Django project"""
        # Render templates
        # Create directory structure
        # Done!
```

**Deliverable**: Working project generator that creates runnable Django projects

**REMOVED from MVP**: Configuration system (YAML loading, validation) - deferred to Post-MVP

#### **1.2.2 Git Subtree Integration (OPTIONAL)**
**Priority**: Optional utility for embedding quickscale_core (evaluate if needed)

- [ ] **Document manual git subtree workflow for users**
- [ ] **Create optional `--embed-core` flag for CLI**
- [ ] **Test: User can pull updates from quickscale repo**
- [ ] **Test: User can push improvements back**

**Git Subtree Documentation (For Users)**:
```bash
# If user wants to embed quickscale_core:
cd myapp
git subtree add --prefix=quickscale \\
  https://github.com/Experto-AI/quickscale.git main --squash

# Pull updates later:
git subtree pull --prefix=quickscale \\
  https://github.com/Experto-AI/quickscale.git main --squash
```

**Deliverable**: Git subtree workflow documented; automation optional

**Note**: Full CLI commands (`quickscale update`, `quickscale sync`) can be added in Phase 2 if users find manual git subtree commands cumbersome.

#### **1.2.3 Minimal CLI Command**
**Priority**: Implement ultra-simple `quickscale init` command

- [ ] **Create basic CLI entry point with Click or argparse**
- [ ] **Implement `quickscale init <project_name>` command (NO FLAGS)**
- [ ] **Call ProjectGenerator with project name**
- [ ] **Add basic error handling (project already exists, invalid name)**
- [ ] **Display success message with next steps**

```python
# quickscale_cli/main.py
import click
from quickscale_core.scaffold import ProjectGenerator

@click.command()
@click.argument('project_name')
def init(project_name):
    """Generate a new Django project"""
    generator = ProjectGenerator()
    generator.generate(project_name, Path.cwd())
    click.echo(f"✅ Created project: {project_name}")
    click.echo("Next steps:")
    click.echo(f"  cd {project_name}")
    click.echo("  python manage.py runserver")
```

**Deliverable**: Working `quickscale init myapp` command (ultra-simple, no options)

**REMOVED from MVP**: 
- `--template` flag (only one starter)
- `--embed-code` flag (optional, can be manual)
- `--config` flag (no YAML config in MVP)

### **Phase 1.3: Core Utilities & Django Integration**

#### **1.3.1 Django App Configuration**
**Priority**: Ensure proper Django app integration

- [ ] **Create `QuickScaleCoreConfig` Django app configuration class**
- [ ] **Setup proper Django app metadata (name, verbose_name, etc.)**
- [ ] **Implement `ready()` method for initialization**
- [ ] **Test Django app loading and initialization**

```python
# quickscale_core/apps.py
from django.apps import AppConfig

class QuickScaleCoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'quickscale_core'
    verbose_name = 'QuickScale Core'
    
    def ready(self):
        """Initialize QuickScale core when Django starts"""
        # Future: Register signals, setup hooks
        pass
```

**Deliverable**: Working Django app that loads properly in INSTALLED_APPS

#### **1.3.2 Core Utilities**
**Priority**: Essential utilities for project generation and Django integration

- [ ] **Create `get_project_settings()` function for Django settings generation**
- [ ] **Create file utilities (`ensure_directory`, `copy_template`)**
- [ ] **Create version utilities (`parse_version`, `compare_versions`)**
- [ ] **Add comprehensive utility function tests**
- [ ] **Migrate valuable legacy utility functions** identified in analysis

```python
# quickscale_core/utils/__init__.py
from .django_utils import get_project_settings, setup_logging
from .file_utils import ensure_directory, copy_template
from .version_utils import parse_version, compare_versions

# quickscale_core/utils/django_utils.py
def get_project_settings(config: ProjectConfig) -> Dict[str, Any]:
    """Generate Django settings dict from QuickScale config"""
    pass

def setup_logging(config: ProjectConfig) -> None:
    """Setup logging configuration"""
    pass
```

**Deliverable**: Complete utility library supporting project generation

### **Phase 1.4: Testing & MVP Validation**

#### **1.4.1 Essential Test Suite (MVP-Focused)**
**Priority**: Test core functionality, keep it simple

- [ ] **Create project generation tests (does it create files?)**
- [ ] **Create template rendering tests (do templates work?)**
- [ ] **Create CLI tests (does `quickscale init` work?)**
- [ ] **Create integration test (end-to-end: init → runserver)**
- [ ] **Achieve >70% coverage (good enough for MVP)**

```
quickscale_core/tests/
├── test_scaffold/
│   ├── test_generator.py          # Project generation tests  
│   └── test_templates.py          # Template rendering tests
└── test_integration.py            # Full workflow: init → works

quickscale_cli/tests/
└── test_cli.py                    # CLI command tests
```

**Deliverable**: Working test suite that validates MVP functionality

**Deferred to Post-MVP**: Extensive test coverage, config validation tests, utility tests

#### **1.4.2 MVP Documentation**
**Priority**: Document what exists, not what's planned

- [ ] **Write README for quickscale_core package**
- [ ] **Write README for quickscale_cli package**
- [ ] **Document generated project structure**
- [ ] **Write "Next Steps After MVP" guide**
- [ ] **Document git subtree workflow (if included)**

**Deliverable**: Minimal but sufficient documentation for MVP users

#### **1.4.3 MVP Validation with Real Project**
**Priority**: USE IT YOURSELF - build a real client project

- [ ] **Generate project with `quickscale init client_test`**
- [ ] **Build simple SaaS feature (auth, billing, or simple CRUD)**
- [ ] **Document pain points and what's missing**
- [ ] **Identify first patterns worth extracting**
- [ ] **Validate: Can you reuse code across 2-3 projects?**

**Deliverable**: **PROOF that MVP actually works for real client projects**

**This is the MOST IMPORTANT step**: If you can't build a real client project with MVP, it's not done.

---

## **Phase 2: Organic Evolution (Client-Driven Growth)**

**🎯 Objective**: Extract reusable patterns from real client work. Don't build speculatively.

**Timeline**: Ongoing (happens naturally as you build more client projects)

**Key Principle**: **Build modules from REAL client needs, not speculation**

### **Phase 2.1: Pattern Extraction Workflow**

#### **When to Extract a Module**
✅ **Extract when**:
- You've built the same feature 2-3 times across client projects
- The code is stable and battle-tested
- The pattern is genuinely reusable (not client-specific)

❌ **Don't extract when**:
- You've only built it once
- It's highly client-specific
- You're just guessing it might be useful

#### **Extraction Process**
1. **Identify Reusable Code**: Look for repeated patterns across client projects
2. **Create Module Structure**: `quickscale_modules/<module_name>/`
3. **Extract & Refactor**: Move code, make it generic, add tests
4. **Update Client Projects**: Replace custom code with module via git subtree
5. **Document**: Add module to internal documentation

### **Phase 2.2: First Modules (Build from Real Needs)**

**Don't build these upfront. Build them when you actually need them 2-3 times:**

#### **Likely First Modules** (based on common client needs):
- **auth**: If you keep building custom user models + authentication
- **payments**: If multiple clients need Stripe integration
- **billing**: If you keep building subscription logic
- **api**: If multiple clients need REST APIs
- **notifications**: If you keep adding email/SMS features

#### **Module Creation Checklist**:
- [ ] Used successfully in 2-3 client projects
- [ ] Code is stable and well-tested
- [ ] Genuinely reusable (not client-specific hacks)
- [ ] Documented with examples
- [ ] Distributed via git subtree to other projects
- [ ] Consider PEP 420 namespace packages if multiple modules exist

### **Phase 2.3: Git Subtree Workflow Refinement**

Based on MVP usage, improve code sharing:

- [ ] **Add CLI commands if manual git subtree is painful**:
  - `quickscale update myproject` (pull changes)
  - `quickscale sync push myproject` (push improvements back)
- [ ] **Document versioning strategy** (git tags for stable snapshots)
- [ ] **Create extraction scripts** to help move code from clients to modules

### **Phase 2.4: Evaluate Configuration System**

**After 5+ client projects**, evaluate if YAML config would be useful:

Questions to answer:
- Do you find yourself repeating the same Django settings setup?
- Would declarative config speed up project creation?
- Is Django settings inheritance working well enough?

**Decision Point**: Add YAML config ONLY if it solves real pain points from MVP usage.

---

## **Phase 3: Community Platform (Optional Evolution)**

**🎯 Objective**: IF proven successful personally, evolve into community platform.

**Timeline**: 12-18+ months after MVP (or never, if personal toolkit is enough)

**Prerequisites Before Starting Phase 3:**
- ✅ 10+ successful client projects built with QuickScale
- ✅ 5+ proven reusable modules extracted
- ✅ Clear evidence that others want to use your patterns
- ✅ Bandwidth to support community and marketplace

### **Phase 3.1: Package Distribution**

When you're ready to share with community:

- [ ] **Setup PyPI publishing for modules**
  - Convert git subtree modules to pip-installable packages
  - Use PEP 420 implicit namespaces (`quickscale_modules.*`)
  - Implement semantic versioning
- [ ] **Create private PyPI for commercial modules** (see COMMERCIAL.md)
- [ ] **Document package creation for community contributors**

### **Phase 3.2: Theme Package System**

If reusable business logic patterns emerge:

- [ ] **Create theme package structure** (`quickscale_themes.*`)
- [ ] **Implement theme inheritance system**
- [ ] **Create example themes** (starter, todo, etc.)
- [ ] **Document theme creation guide**

### **Phase 3.3: Marketplace & Community**

Only if there's real demand:

- [ ] **Build package registry/marketplace**
- [ ] **Create community contribution guidelines**
- [ ] **Setup extension approval process**
- [ ] **Build commercial module subscription system**

### **Phase 3.4: Advanced Configuration**

If YAML config proves useful in Phase 2:

- [ ] **Implement full configuration schema**
- [ ] **Add module/theme selection via config**
- [ ] **Create migration tools for config updates**
- [ ] **Build configuration validation UI**

**IMPORTANT**: Phase 3 is OPTIONAL. Many successful solo developers and agencies never need a community platform. Evaluate carefully before investing in marketplace features.

---

## **MVP Deliverables Summary**

### **Phase 1 Deliverables (v0.1.0) - Personal Toolkit**
- [ ] � `quickscale_core` package with minimal utilities
- [ ] 📦 `quickscale_cli` package with simple `init` command
- [ ] 🏗️ Project scaffolding creating Django "Hello World"
- [ ] 🖥️ Ultra-simple CLI: `quickscale init myapp`
- [ ] 📁 Optional git subtree integration for code sharing
- [ ] ✅ Basic testing validating project generation works
- [ ] 📖 Minimal documentation (README + usage guide)
- [ ] ✅ **VALIDATION: Build 1 real client project successfully**

### **Explicit MVP Limitations (By Design)**
- ❌ **No module packages**: Build from real needs in Phase 2
- ❌ **No theme packages**: Generated projects are fully customizable
- ❌ **No YAML configuration**: Django settings inheritance only
- ❌ **No PyPI distribution**: Git subtree only for MVP
- ❌ **No marketplace**: Personal toolkit, not platform
- ❌ **No multiple templates**: One starter template only
- ❌ **No advanced CLI features**: Just `quickscale init`

**The Point**: Build the absolute minimum that lets you create client projects faster. Everything else is Post-MVP.

**Backward compatibility stance**: The new QuickScale architecture is a breaking change and is not backward compatible. Automated migration of existing QuickScale projects is out-of-scope for the MVP. Phase 1 includes a legacy analysis and guidance to help maintainers extract useful assets manually (see `docs/legacy-analysis.md`).

### **Post-MVP (Future Phases)**
- **Phase 2**: Actual theme system with `quickscale_themes/starter`
- **Phase 3**: Module system with `quickscale_modules/auth`
- **Phase 4**: Frontend marketplace and advanced features

---

## **Key Changes from Original ROADMAP**

### **✅ Fixed Issues**
1. **Removed complex theme/module references** - MVP scope only
2. **Reordered tasks logically** - Legacy analysis first, progressive building
3. **Added missing CLI implementation** - Core MVP requirement
4. **Simplified configuration schema** - Only MVP fields
5. **Clear deliverables for each task** - Concrete success criteria  
6. **Aligned with MVP-FRONTEND-DECISION.md** - Consistent architecture

### **🎯 MVP Focus**
- Configuration system + Project scaffolding + Basic CLI
- Directory-based frontend development only
- Backend inheritance pattern only
- Clear path to working Django projects
 - Scaffolded starter files generated in projects (theme packages are Post-MVP)
 - Module packages are Post-MVP

This roadmap can be implemented incrementally, with each task building on the previous ones, leading to a working MVP that validates the architecture before adding complexity.

---

## **APPENDIX: Future Architecture Reference**

### **Post-MVP Theme Structure (Phase 2+ Reference)**
*Preserved for future implementation - NOT part of MVP*

```
# Future Theme Structure - Business Logic + Multi-Frontend Support
quickscale_themes/{theme_name}/
├── __init__.py
├── apps.py                 # Django AppConfig
├── src/quickscale_themes/{theme_name}/  # Business theme package
│   ├── __init__.py
│   ├── models.py          # Business models and database schema
│   ├── business.py        # Pure business logic classes
│   ├── api.py             # REST API endpoints and serializers
│   ├── admin.py           # Django admin interfaces
│   ├── urls.py            # API URL patterns (no template views)
│   ├── services/          # Business service classes
│   ├── migrations/        # Database migrations
│   └── theme_config.py    # Business theme metadata
├── frontend_htmx/         # HTMX presentation layer
│   ├── templates/         # Django templates
│   ├── static/           # CSS, JS, images, fonts
│   └── components/       # Reusable UI components
└── tests/                # Theme-specific tests
```

### **Post-MVP Module Structure (Phase 3+ Reference)**
*Preserved for future implementation - NOT part of MVP*

```
# Future Module Structure - Backend Services (Built on Django Foundations)
quickscale_modules/{module_name}/
├── __init__.py
├── apps.py                # Django AppConfig with compatibility info
├── src/quickscale_modules/{module_name}/
│   ├── __init__.py
│   ├── models.py          # Backend module data models (e.g., dj-stripe models)
│   ├── admin.py           # Feature module admin interfaces
│   ├── services.py        # Pure Python services for themes to import
│   ├── signals.py         # Signal handlers for theme integration
│   └── module_config.py   # Module metadata and service specifications
└── tests/                 # Module-specific tests
```

### **Post-MVP Configuration Schema (Future Reference)**
*Preserved for future implementation - NOT part of MVP*

```yaml
# Future: Full configuration schema (Phase 2+)
schema_version: 1
project:
  name: my_saas_project
  version: 1.0.0

theme: starter                           # Actual theme loading (Phase 2)
backend_extensions: myproject.extensions # Python inheritance

modules:                                 # Module system (Phase 3)
  auth:
    provider: django-allauth
  payments:
    provider: stripe

frontend:
  source: ./custom_frontend/             # Directory-based (MVP)
  variant: default                       # Basic variant support (MVP)
  # Future: marketplace frontends, advanced features

customizations:                          # Advanced customization (Phase 4+)
  models:
    - name: Product
      fields:
        - { name: name, type: string }
  business_rules:
    - "Products require approval before listing"
```

### **Package Naming Matrix (Future Reference)**
*From DECISIONS.md - preserved for Phase 2+ implementation*

| Concern | PyPI Name | Import Path | Django App Label |
|---------|-----------|-------------|------------------|
| Core | quickscale-core | quickscale_core | quickscale_core |
| Auth Module | quickscale-module-auth | quickscale_modules.auth | quickscale_modules_auth |
| Starter Theme | quickscale-theme-starter | quickscale_themes.starter | quickscale_themes_starter |