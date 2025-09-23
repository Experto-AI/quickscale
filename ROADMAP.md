# QuickScale Roadmap

---

## 🚀 **FRESH START IMPLEMENTATION PLAN**

This roadmap outlines the complete transformation from the current static project generator to the new composable architecture described in [QUICKSCALE.md](./QUICKSCALE.md).

### **📋 Current State Assessment**
- ✅ **Legacy Backup Created**: Complete v0.41.0 preserved in `quickscale-legacy/`
- ✅ **Git History Preserved**: Full development history available for reference
- ✅ **Architecture Validated**: Evolution document provides detailed technical specification
- 🔄 **Fresh Start Ready**: Ready to implement clean new architecture

---

## **Phase 1: Core Foundation (Internal Development)**

**🎯 Objective**: Build the foundational `quickscale_core` package to validate architecture and establish patterns for future modules/themes. This is an **internal milestone** - not for public release.

### **Phase 1.1: Project Structure & YAML Schema**

#### **1.1.1 Repository Structure Setup**
- [ ] Create `quickscale_core/` package directory with src layout
- [ ] Setup `quickscale_core/pyproject.toml` with proper dependencies
- [ ] Create source directory structure under `src/quickscale_core/`
- [ ] Setup test directory structure outside `src/`
- [ ] Create documentation and examples directories

```
quickscale/
├── quickscale_core/                 # Core package root
│   ├── pyproject.toml              # Package configuration
│   ├── src/                        # Source code (src layout)
│   │   └── quickscale_core/
│   │       ├── __init__.py
│   │       ├── config/             # Configuration management
│   │       ├── scaffold/           # Project scaffolding
│   │       ├── utils/              # Common utilities
│   │       └── apps.py             # Django app configuration
│   └── tests/                      # Unit tests (outside src/)
├── docs/                           # Documentation
├── schemas/                        # YAML schema definitions
└── examples/                       # Example configurations
```

#### **1.1.2 Legacy Code Analysis & Component Identification**
**Priority**: Identify valuable components from quickscale-legacy before building new architecture

- [ ] Extract Docker deployment configurations and patterns
- [ ] Document legacy database models worth preserving
- [ ] Identify legacy utility functions suitable for quickscale_core
- [ ] Analyze legacy configuration handling patterns
- [ ] Document legacy authentication/user management patterns
- [ ] Review legacy CLI
- [ ] Review legacy project generation templates and logic
- [ ] Create migration strategy for valuable legacy components
- [ ] Document legacy patterns that should be carried forward
- [ ] Document legacy patterns that should NOT be carried forward

**Legacy Analysis Deliverables**:
```
docs/
├── what-to-keep.md            # What carry forward
└── what-NOT-to-keep.md        # What NOT to carry forward
```

#### **1.1.3 YAML Configuration Schema Definition**
**Priority**: Define the canonical schema from DECISIONS.md and README.md

- [ ] Create JSON Schema file for validation (`quickscale-config-v1.json`)
- [ ] Create YAML schema documentation (`quickscale-config-v1.yaml`)
- [ ] Create minimal example configuration (`minimal.yml`)
- [ ] Create core-only example configuration (`core-only.yml`)
- [ ] Create full example configuration (`full-example.yml`)
- [ ] Implement schema validation logic
- [ ] Add semantic version validation for project.version
- [ ] Add reserved name validation (no Django/Python conflicts)
- [ ] Add schema version compatibility checking

**Schema Files to Create**:
```
schemas/
├── quickscale-config-v1.json       # JSON Schema for validation
├── quickscale-config-v1.yaml       # YAML schema documentation
└── examples/
    ├── minimal.yml                 # Simplest possible config
    ├── core-only.yml              # Core features only
    └── full-example.yml           # Complete schema example
```

**Core Schema Structure** (based on DECISIONS.md):
```yaml
# schemas/examples/core-only.yml
schema_version: 1
project:
  name: myapp                       # Required: project identifier
  version: 1.0.0                   # Required: semantic version
  description: "My application"     # Optional: project description

theme: none                         # Phase 1: no themes yet
modules: {}                         # Phase 1: no modules yet

frontend:
  technologies: []                  # Phase 1: empty array
  primary: null                     # Phase 1: null
  variant: null                     # Phase 1: null

# Phase 1: Basic customizations only
customizations:
  models: []                        # Future: custom model definitions
  business_rules: []               # Future: business rule definitions
```

**Validation Requirements**:
- [ ] JSON Schema validation for structure
- [ ] Semantic version validation for project.version
- [ ] Reserved name validation (no conflicts with Django/Python)
- [ ] Schema version compatibility checking
- [ ] Future-proofing for modules/themes (accept but ignore)

#### **1.1.4 Django App Structure**
- [ ] Create Django app configuration (`apps.py`)
- [ ] Setup proper app label: `quickscale_core`
- [ ] Configure package metadata following DECISIONS.md naming matrix
- [ ] Setup Django app registration patterns
- [ ] Incorporate valuable legacy patterns identified in analysis
**Package Configuration** (`quickscale_core/pyproject.toml`):
```toml
[project]
name = "quickscale-core"
version = "0.51.0"
description = "QuickScale core foundation for Django SaaS applications"
dependencies = [
    "Django>=4.2,<6.0",
    "PyYAML>=6.0",
    "jsonschema>=4.0",
    "pydantic>=2.0",
]

[project.metadata.quickscale]
# Establish the metadata pattern for future modules
core-compatibility = ">=2.0.0,<3.0.0"
package-type = "core"
```

**Django App Label**: `quickscale_core` (following DECISIONS.md naming matrix)

### **Phase 1.2: Configuration Management System**

#### **1.2.1 Configuration Loading & Validation**
- [ ] Create `ProjectConfig` dataclass with all required fields
- [ ] Implement `from_file()` class method for YAML loading
- [ ] Implement `from_dict()` class method for programmatic loading
- [ ] Create supporting dataclasses (`ProjectInfo`, `FrontendConfig`, etc.)
- [ ] Add comprehensive error handling and user-friendly error messages

```python
# quickscale_core/config/__init__.py
from .loader import ProjectConfig, ConfigLoader, ConfigError
from .validator import validate_config, ValidationError
from .schema import SCHEMA_VERSION, get_schema

# quickscale_core/config/loader.py
@dataclass
class ProjectConfig:
    schema_version: int
    project: ProjectInfo
    theme: Optional[str] = None
    modules: Dict[str, Any] = field(default_factory=dict)
    frontend: FrontendConfig = field(default_factory=FrontendConfig)
    customizations: CustomizationConfig = field(default_factory=CustomizationConfig)
    
    @classmethod
    def from_file(cls, config_path: Path) -> 'ProjectConfig':
        """Load configuration from YAML file with validation"""
        pass
    
    @classmethod 
    def from_dict(cls, config_data: dict) -> 'ProjectConfig':
        """Load configuration from dictionary with validation"""
        pass
```

#### **1.2.2 Schema Validation Engine**
- [ ] Create `validate_config()` function with JSON schema integration
- [ ] Implement `ValidationResult` class for detailed error reporting
- [ ] Create `ValidationError` exception class with user-friendly messages
- [ ] Add business rule validation beyond basic schema checking
- [ ] Create validation utilities for common patterns (names, versions, etc.)

```python
# quickscale_core/config/validator.py
def validate_config(config: dict) -> ValidationResult:
    """Validate configuration against JSON schema"""
    # - Load appropriate schema version
    # - Validate structure with jsonschema
    # - Validate business rules (naming, versions, etc.)
    # - Return detailed error messages
    pass

class ValidationError(Exception):
    """Configuration validation error with detailed messages"""
    pass
```

### **Phase 1.3: Project Scaffolding System**

#### **1.3.1 Basic Scaffolding Engine**
- [ ] Create `ProjectGenerator` class for project creation
- [ ] Implement `TemplateEngine` for Jinja2-based template rendering
- [ ] Create `generate_project()` method with full Django project structure
- [ ] Add error handling and recovery for scaffolding failures
- [ ] Implement directory creation and file writing with proper permissions
- [ ] **Integrate legacy Docker deployment patterns** from legacy analysis
- [ ] **Incorporate proven legacy project templates** and structure patterns

```python
# quickscale_core/scaffold/__init__.py
from .generator import ProjectGenerator, ScaffoldError
from .templates import TemplateEngine

# quickscale_core/scaffold/generator.py
class ProjectGenerator:
    def __init__(self, config: ProjectConfig):
        self.config = config
        self.template_engine = TemplateEngine()
    
    def generate_project(self, output_path: Path) -> None:
        """Generate basic Django project structure from config"""
        # - Create directory structure
        # - Generate settings.py with proper INSTALLED_APPS
        # - Generate urls.py
        # - Generate manage.py
        # - Generate basic templates structure
        # - Generate requirements.txt
        pass
```

#### **1.3.2 Django Integration Templates**
- [ ] Create Django settings.py template with proper INSTALLED_APPS
- [ ] Create URLs configuration template
- [ ] Create manage.py template
- [ ] Create requirements.txt template with dependencies
- [ ] Create basic HTML template structure
- [ ] Add template validation and rendering tests
- [ ] **Incorporate legacy Docker configurations** (Dockerfile, docker-compose.yml)
- [ ] **Integrate proven legacy deployment patterns** in templates

**Template Files to Create**:
```
quickscale_core/scaffold/templates/
├── project/
│   ├── settings.py.jinja2         # Django settings template
│   ├── urls.py.jinja2             # URL configuration
│   ├── manage.py.jinja2           # Management script
│   └── requirements.txt.jinja2    # Dependencies
├── apps/
│   └── __init__.py               # Future: app templates
└── frontend/
    └── base.html.jinja2          # Basic HTML template
```

### **Phase 1.4: Core Utilities & Django Patterns**

#### **1.4.1 Common Utilities**
- [ ] Create `get_project_settings()` function for Django settings generation
- [ ] Create `setup_logging()` function for logging configuration
- [ ] Create file utilities (`ensure_directory`, `copy_template`)
- [ ] Create version utilities (`parse_version`, `compare_versions`)
- [ ] Add comprehensive utility function tests
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

#### **1.4.2 Django App Configuration**
- [ ] Create `QuickScaleCoreConfig` app configuration class
- [ ] Setup proper Django app metadata (name, verbose_name, etc.)
- [ ] Implement `ready()` method for initialization
- [ ] Add future hook system preparation (commented patterns)
- [ ] Test Django app loading and initialization

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

### **Phase 1.5: Testing & Documentation**

#### **1.5.1 Test Suite Structure**
- [ ] Create configuration loading and validation tests
- [ ] Create schema validation tests with various input scenarios
- [ ] Create project generation tests with filesystem validation
- [ ] Create template rendering tests
- [ ] Create utility function tests
- [ ] Achieve >90% test coverage
- [ ] Setup continuous integration testing

```
quickscale_core/tests/
├── test_config/
│   ├── test_loader.py             # Configuration loading tests
│   ├── test_validator.py          # Schema validation tests
│   └── fixtures/                  # Test configuration files
├── test_scaffold/
│   ├── test_generator.py          # Project generation tests  
│   └── test_templates.py          # Template rendering tests
└── test_utils/
    └── test_django_utils.py       # Utility function tests
```

#### **1.5.2 Internal Documentation**
- [ ] Create API documentation from docstrings
- [ ] Write architecture notes explaining core patterns
- [ ] Document future integration points for modules/themes
- [ ] Create development environment setup guide
- [ ] Write troubleshooting and debugging guide

### **Phase 1.6: Validation & Architecture Proof**

#### **1.6.1 Internal Testing Scenarios**
- [ ] Test basic configuration loading and validation
- [ ] Test Django project generation from minimal config
- [ ] Test core app installation in Django project
- [ ] Test schema versioning and compatibility checking
- [ ] Test error handling and user-friendly error messages
- [ ] Validate generated projects run successfully (`python manage.py runserver`)
- [ ] **Validate legacy component integration** works in generated projects

#### **1.6.2 Success Criteria**
- [ ] **YAML Schema**: Complete v1 schema with validation
- [ ] **Configuration Loading**: Robust config loading with clear errors
- [ ] **Project Scaffolding**: Generates working Django projects
- [ ] **Django Integration**: Core app works in Django INSTALLED_APPS
- [ ] **Test Coverage**: >90% test coverage for core functionality
- [ ] **Documentation**: Complete internal API documentation
- [ ] **Architecture Validation**: Proves patterns work for future modules
- [ ] **Legacy Integration**: Valuable legacy components successfully incorporated

### **Phase 1.7: Preparation for Phase 2**

#### **1.7.1 Module Integration Points**
- [ ] Create `ModuleRegistry` class structure (commented/placeholder)
- [ ] Define module interface contracts and patterns
- [ ] Setup module discovery patterns for future use
- [ ] Document module integration architecture
- [ ] Prepare hook system foundation (for future phases)

```python
# quickscale_core/registry.py (future)
class ModuleRegistry:
    """Registry for QuickScale modules (Phase 2)"""
    # Establish patterns for module discovery
    # Define module interface contracts
    # Setup for future hook system
    pass
```

#### **1.7.2 Theme Integration Points**
- [ ] Create `ThemeRegistry` class structure (commented/placeholder)
- [ ] Define theme interface contracts and patterns
- [ ] Setup theme discovery patterns for future use
- [ ] Document theme integration architecture

```python  
# quickscale_core/themes.py (future)
class ThemeRegistry:
    """Registry for QuickScale themes (Phase 2)"""
    # Establish patterns for theme discovery
    # Define theme interface contracts
    pass
```

---

## **Phase 1 Deliverables**

### **Internal Release: v0.51.0**
- [ ] 📦 `quickscale-core` package (internal distribution)
- [ ] 📋 Complete YAML configuration schema v1
- [ ] 🏗️ Basic project scaffolding system
- [ ] 🧪 Comprehensive test suite
- [ ] 📖 Internal API documentation
- [ ] ✅ Architecture validation complete

### **Next Phase Preview**
Phase 1 establishes the foundation for:
- **Phase 2**: First module (quickscale-module-auth built on django-allauth)
- **Phase 3**: First theme (quickscale-theme-starter)  
- **Phase 4**: CLI package (quickscale-cli)
- **Phase 5**: Public release

---

