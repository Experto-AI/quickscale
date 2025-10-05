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

Execution details live here; the "personal toolkit first, community platform later" narrative stays in [QUICKSCALE.md](./QUICKSCALE.md#evolution-strategy-personal-toolkit-first). Treat the [MVP Feature Matrix](./DECISIONS.md#mvp-feature-matrix-authoritative) as the scope source of truth.

### **📋 Current State Assessment**
- ✅ **Evolution Strategy Defined**: Start simple, grow organically
- ✅ **MVP Scope Clarified**: Simple CLI + project scaffolding + git subtree
- ✅ **Legacy Backup Available**: Complete v0.41.0 preserved in `quickscale-legacy/`
- ✅ **Post-MVP Path Clear**: Module/theme packages when proven necessary
- 🔄 **Ready to Build**: Clear MVP requirements established

### **Evolution Context Reference**
Need the narrative backdrop? Jump to [`QUICKSCALE.md`](./QUICKSCALE.md#evolution-strategy-personal-toolkit-first) and come back here for the tasks.

---

## **Phase 1: MVP - Personal Toolkit** 

**🎯 Objective**: Build a simple project generator that creates minimal Django starter projects you can use for client work immediately.

**MVP Scope**: Minimal CLI + basic scaffolding. Git subtree remains an advanced workflow documented in `DECISIONS.md`; any CLI helpers stay deferred to the Post-MVP backlog and are not part of the initial `quickscale init` release.

**Success Criteria**:
- `quickscale init myapp` generates working Django project in < 30 seconds
- Generated project can be customized for any client need
- Code sharing via git subtree is documented; CLI wrapper helpers remain on the Post-MVP backlog per `DECISIONS.md`, so MVP relies on the manual commands captured there

**Integration Note**: See [Personal Toolkit workflow in DECISIONS.md](./DECISIONS.md#integration-note-personal-toolkit-git-subtree) for the canonical git subtree commands, extraction patterns, and CLI wrapper roadmap.

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
**Decision Basis**: `DECISIONS.md` keeps legacy consolidation guidance authoritative; during this phase maintainers must create the `legacy/analysis/` directory and populate it with fresh findings rather than assuming prior work shipped.

**Action Items (concrete)**:
- [ ] Inventory deprecated/archived QuickScale code (e.g. v0.41.0 archive) and associated scripts/docs into `legacy/analysis/`.
- [ ] For each archived artifact, record: purpose, test coverage, current compatibility, and risks of reuse.
- [ ] Identify reusable pieces (templates, utilities, docs) and create small follow-up tasks to either migrate, adapt, or retire them.
- [ ] Produce a short report `legacy/analysis/README.md` with recommended items to re-use and a small migration plan (one-page).

**Goal**: Ensure we salvage useful work from prior QuickScale versions instead of reimplementing proven pieces. This is an analysis task; migration/porting work should be split into explicit follow-up tasks based on the findings.

#### **1.1.2 Repository Structure Setup**
**Priority**: Create basic package structure following DECISIONS.md

- [ ] **Create `quickscale_core/` package directory with src layout**
 - [ ] **Create `src/quickscale_core/` source directory structure**
- [ ] **Create `quickscale_core/tests/` directory outside src/**
- [ ] **Create `docs/` and `examples/` directories**

**Deliverable**: Basic directory structure per DECISIONS.md standards. Use the authoritative layout in [SCAFFOLDING.md §3](./SCAFFOLDING.md#mvp-structure) rather than duplicating trees here.

**Note**: `schemas/` directory (YAML config schemas) is Post-MVP and not needed for Phase 1.

#### **1.1.3 MVP Scaffolding Templates (SIMPLE)**
**Priority**: Create minimal Jinja2 templates for Django project generation

- [ ] **Create basic Django project template structure**
- [ ] **Create `manage.py` template**
 - [ ] **Create `settings.py` template; default standalone settings.py (optional quickscale_core import only when user opts to embed)**
- [ ] **Create `urls.py` template**
- [ ] **Create simple homepage template**
- [ ] **Create `requirements.txt` template (Django + essentials)**

**MVP Templates Needed**: See [SCAFFOLDING.md §3](./SCAFFOLDING.md#mvp-structure) for the complete template inventory and file layout.

**NO YAML Configuration in MVP**: Configuration system is deferred to Post-MVP (TBD if needed).

**Deliverable**: Working templates that generate minimal Django project

### **Phase 1.2: Core Implementation**

#### **1.2.1 Project Scaffolding System (MVP - SIMPLIFIED)**
**Priority**: Generate minimal Django projects

- [ ] **Create `ProjectGenerator` class for basic scaffolding**
- [ ] **Implement template rendering with Jinja2**
- [ ] **Generate standard Django project structure**
- [ ] **Add simple homepage**
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

#### **1.2.2 Git Subtree Documentation (advanced/manual workflow)**
**Priority**: Document git subtree as an advanced/manual workflow for embedding `quickscale_core` into generated projects. Wrapper helpers stay deferred to Post-MVP, so Phase 1 focuses on clear guidance and validation of the manual path.

- [ ] **Document git subtree workflow for users (manual commands also documented for transparency)**
- [ ] **Validate the manual embed/update/sync instructions against a generated project**
- [ ] **Capture common failure modes and recovery steps for manual subtree operations**

**Git Subtree Documentation (For Users)**: Avoid duplicating command snippets here. Link directly to the [canonical workflow in DECISIONS.md](./DECISIONS.md#integration-note-personal-toolkit-git-subtree) and ensure the roadmap tasks track implementation and documentation milestones only.

**Deliverable**: Git subtree workflow documented in `DECISIONS.md`; any automation remains on the Post-MVP backlog until usage feedback justifies it.

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

**Deliverable**: Working `quickscale init myapp` command (ultra-simple, no options). Any additional CLI wrappers remain Post-MVP backlog items.

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
#### **Phase 2.2: First Modules (Build from Real Needs)**

#### **Likely First Modules** (based on common client needs):
- **auth**: If you keep building custom user models + authentication
- **payments**: If multiple clients need Stripe integration
- **billing**: If you keep building subscription logic
- **api**: If multiple clients need REST APIs
- **notifications**: If you keep adding email/SMS features

#### **Admin Module Scope Exploration (Under Evaluation)**

**Note**: Admin module scope is still under evaluation and NOT confirmed for Phase 2. See tracking notes below.
- [ ] Review auth vs admin responsibilities documented in `DECISIONS.md` and capture open questions
- [ ] Interview current maintainers about desired admin UX improvements separate from authentication
- [ ] Draft scope options for `quickscale_modules.admin` (e.g., dashboard UX, moderation tooling) and circulate for decision in `DECISIONS.md`
- [ ] Record findings and recommended decision timeline

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
- [ ] 🏗️ Project scaffolding creating minimal Django starter
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

**Backward compatibility stance**: The new QuickScale architecture is a breaking change and is not backward compatible. Automated migration of existing QuickScale projects is out-of-scope for the MVP. Phase 1 includes a legacy analysis and guidance to help maintainers extract useful assets manually; place findings under `legacy/analysis/` in-repo.

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

## Appendix: Future Architecture Reference

Keep the future architecture diagrams and naming matrices centralized to avoid drift:

- **Theme and module structures** → [SCAFFOLDING.md §4](./SCAFFOLDING.md#post-mvp-structure)
- **Generated project layouts** → [SCAFFOLDING.md §5](./SCAFFOLDING.md#5-generated-project-output)
- **Configuration schema drafts** → [DECISIONS.md](./DECISIONS.md#architectural-decision-configuration-driven-project-definition)
- **Naming and packaging matrix** → [SCAFFOLDING.md §6](./SCAFFOLDING.md#6-naming-import-matrix-summary)
