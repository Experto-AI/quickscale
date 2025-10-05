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

## 🚀 **MVP-ALIGNED IMPLEMENTATION PLAN**

This roadmap is aligned with the MVP frontend architecture decisions (integrated into [DECISIONS.md](./DECISIONS.md)) and focuses on the **Minimum Viable Deliverable**.

### **📋 Current State Assessment**
- ✅ **MVP Architecture Decided**: Directory-based frontend with backend inheritance
- ✅ **Legacy Backup Available**: Complete v0.41.0 preserved in `quickscale-legacy/`
- ✅ **Scope Defined**: Core foundation with scaffolded starter files generated in projects (theme/module packages deferred to post-MVP)
- 🔄 **Ready to Build**: Clear MVP requirements established

---

## **Phase 1: MVP Core Foundation** 

**🎯 Objective**: Build the minimal viable `quickscale_core` package that can generate working Django projects with directory-based frontend development.

**MVP Scope**: Configuration system + Project scaffolding + Basic CLI

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

#### **1.1.3 MVP Configuration Schema (SIMPLE)**
**Priority**: Define ONLY the MVP schema from MVP-FRONTEND-DECISION.md

- [ ] **Create `quickscale-config-mvp.json` with MVP fields only**
- [ ] **Create MVP example: `examples/mvp-minimal.yml`** 
- [ ] **Implement basic YAML loading with validation**
- [ ] **Create `ProjectConfig` dataclass with MVP fields only**
- [ ] **Add schema validation with clear error messages**

**MVP Schema (minimal starter theme included; modules deferred to Post-MVP)**:
```yaml
# examples/mvp-minimal.yml
schema_version: 1
project:
  name: myapp                       # Required: project identifier
  version: 1.0.0                   # Required: semantic version

# MVP: Scaffolded starter files generated in project; theme package loading is Post-MVP
theme: starter                      # Reserved for future theme package loading

# MVP: Backend customization via Python inheritance  
backend_extensions: myapp.extensions

# MVP: Directory-based frontend only
frontend:
  source: ./custom_frontend/        # Directory path only
  variant: default                  # Simple variant support
```

**Deliverable**: Working YAML config loading with validation

### **Phase 1.2: Core Implementation**

#### **1.2.1 Configuration System (MVP)**
**Priority**: Implement config loading for MVP schema only

- [ ] **Create `ProjectConfig` dataclass with MVP fields**
- [ ] **Implement `ProjectConfig.from_file()` with YAML loading**
- [ ] **Create `validate_config()` with MVP schema validation**
- [ ] **Add clear error messages for validation failures**
- [ ] **Test config loading with example files**

```python
# quickscale_core/config/loader.py
@dataclass  
class ProjectConfig:
    schema_version: int
    project: ProjectInfo
    theme: str
    backend_extensions: str
    frontend: FrontendConfig
    
    @classmethod
    def from_file(cls, config_path: Path) -> 'ProjectConfig':
        """Load MVP configuration from YAML file"""
        pass
```

**Deliverable**: Working config system with MVP schema support

#### **1.2.2 Project Scaffolding System (MVP)**
**Priority**: Generate working Django projects with MVP features

- [ ] **Create `ProjectGenerator` class for basic scaffolding**
- [ ] **Implement Django project template generation**
- [ ] **Generate `backend_extensions.py` with inheritance stubs** 
- [ ] **Generate `custom_frontend/` directory structure**
- [ ] **Generate `settings.py` with custom frontend support**
- [ ] **Generate `manage.py`, `urls.py`, basic Django files**

**MVP Templates Needed**:
```
quickscale_core/scaffold/templates/
├── project/
│   ├── settings.py.j2              # Django settings with custom_frontend support
│   ├── manage.py.j2                # Standard Django management
│   ├── urls.py.j2                  # Basic URL configuration  
│   ├── requirements.txt.j2         # MVP dependencies
│   └── backend_extensions.py.j2    # Python inheritance template
└── custom_frontend/
    ├── templates/base.html.j2       # Basic template
    ├── static/css/main.css         # Basic styles
    └── variants/default/           # Default variant structure
```

**Deliverable**: Working project generation that creates Django projects

#### **1.2.3 Basic CLI Command**
**Priority**: Implement `quickscale init` command for MVP

- [ ] **Create basic CLI entry point**
- [ ] **Implement `quickscale init myapp --template=saas --embed-code` command** 
- [ ] **Add `--config` option for custom config files**
- [ ] **Generate default `quickscale.yml` if not provided**
- [ ] **Add basic error handling and user messages**

```python
# Basic CLI interface
def init_project(name: str, config_path: Optional[Path] = None):
    """Create new QuickScale project with MVP features"""
    pass
```

**Deliverable**: Working `quickscale init myapp --template=saas --embed-code` command

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

### **Phase 1.4: Testing & Quality**

#### **1.4.1 Comprehensive Test Suite**
**Priority**: Ensure reliability and maintainability

- [ ] **Create configuration loading and validation tests**
- [ ] **Create schema validation tests with various input scenarios**
- [ ] **Create project generation tests with filesystem validation**
- [ ] **Create template rendering tests**
- [ ] **Create utility function tests**
- [ ] **Achieve >90% test coverage**
- [ ] **Setup continuous integration testing**

```
quickscale_core/tests/
├── test_config/
│   ├── test_loader.py             # Configuration loading tests
│   ├── test_validator.py          # Schema validation tests
│   └── fixtures/                  # Test configuration files
├── test_scaffold/
│   ├── test_generator.py          # Project generation tests  
│   └── test_templates.py          # Template rendering tests
├── test_utils/
│   └── test_django_utils.py       # Utility function tests
└── test_integration/
    └── test_end_to_end.py         # Full workflow tests
```

**Deliverable**: Comprehensive test suite with >90% coverage

#### **1.4.2 Documentation & Architecture**
**Priority**: Document MVP implementation for future phases

- [ ] **Create API documentation from docstrings**
- [ ] **Write architecture notes explaining core patterns**
- [ ] **Document future integration points for modules/themes**
- [ ] **Create development environment setup guide**
- [ ] **Document MVP limitations and extension points**

**Deliverable**: Complete technical documentation

### **Phase 1.5: MVP Validation**

#### **1.3.1 End-to-End Testing**
**Priority**: Validate the complete MVP workflow works

- [ ] **Test: `quickscale init testproject --template=saas --embed-code` generates working project**
- [ ] **Test: Generated project runs `python manage.py runserver`**
- [ ] **Test: `backend_extensions.py` inheritance pattern works**
- [ ] **Test: `custom_frontend/` directory structure loads properly**
- [ ] **Test: Variant switching works (default vs custom)**
- [ ] **Test: Configuration validation catches errors properly**

**Success Criteria**:
- Generated project boots without errors
- Custom frontend templates load properly  
- Backend extensions inheritance works
- Configuration validation provides clear errors

#### **1.3.2 Documentation & Examples**
**Priority**: Document the MVP functionality

- [ ] **Update README.md with MVP usage examples**
- [ ] **Create quickstart guide for directory-based frontend**
- [ ] **Document backend extensions inheritance pattern**
- [ ] **Create example projects showing MVP features**
- [ ] **Document limitations and future phases**

**Deliverable**: Clear documentation for MVP users

---

## **MVP Deliverables Summary**

### **Phase 1 Deliverables (v0.1.0)**
- [ ] 📦 `quickscale-core` package with MVP functionality
- [ ] ⚙️ Configuration system supporting MVP schema only
- [ ] 🏗️ Project scaffolding creating working Django projects
- [ ] 🐍 Backend extensions via Python inheritance pattern
- [ ] 📁 Directory-based frontend with basic variant support
- [ ] 🖥️ Basic CLI: `quickscale init projectname --template=saas --embed-code`
- [ ] ✅ End-to-end testing validating complete workflow
- [ ] 📖 Documentation and usage examples
 - [ ] ⭐ Scaffolded starter files generated in projects (templates, backend_extensions.py stub, custom_frontend/ structure)

### **Explicit MVP Limitations**
- ❌ **No theme packages**: Scaffolded starter files are generated in projects (NOT packaged themes); theme packaging and marketplace are Post-MVP
- ❌ **No module packages**: `modules` field ignored in MVP (module packaging is Post-MVP)
- ❌ **No frontend marketplace**: Directory-based only
- ❌ **No advanced CLI**: Basic project creation only
- ❌ **No complex configuration**: MVP schema only

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