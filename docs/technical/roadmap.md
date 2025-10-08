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
- Directory structures or scaffolding details (belongs in SCAFFOLDING.md)

RELATIONSHIP TO OTHER DOCUMENTS:
- DECISIONS.md is authoritative for technical scope (MVP Feature Matrix, CLI commands, etc.)
- SCAFFOLDING.md is authoritative for directory structures and layouts
- This roadmap implements what DECISIONS.md defines
- When in doubt, update DECISIONS.md first, then this roadmap

TARGET AUDIENCE: Development team, project managers, stakeholders tracking progress
-->

---

## 🚀 **EVOLUTION-ALIGNED ROADMAP**

Execution details live here; the "personal toolkit first, community platform later" narrative stays in [QUICKSCALE.md](../overview/quickscale.md#evolution-strategy-personal-toolkit-first).

**AUTHORITATIVE SCOPE REFERENCE**: The [MVP Feature Matrix in DECISIONS.md](./decisions.md#mvp-feature-matrix-authoritative) is the single source of truth for what's IN/OUT/PLANNED. When this roadmap conflicts with DECISIONS.md, DECISIONS.md wins.

### **📋 Current State Assessment**
- ✅ **Current Version**: v0.51.0
- ✅ **Evolution Strategy Defined**: Start simple, grow organically
- ✅ **MVP Scope Clarified**: Simple CLI + project scaffolding + git subtree documentation
- ✅ **Legacy Backup Available**: Complete v0.41.0 preserved in `../quickscale-legacy/`
- ✅ **Post-MVP Path Clear**: Module/theme packages when proven necessary
- 🔄 **Next Release**: v0.52.0 - Project Foundation

### **🎯 Release Strategy**
Each minor version (0.x.0) delivers a verifiable improvement that builds toward MVP:
- **v0.52.0**: Package infrastructure (installable packages with tests)
- **v0.53.0**: Template system (working Jinja2 templates)
- **v0.54.0**: Project generator (can generate Django projects)
- **v0.55.0**: CLI implementation (`quickscale init` command works)
- **v0.56.0**: Quality & testing (comprehensive test suite)
- **v0.57.0**: Documentation complete (user guides ready)
- **v0.58.0**: MVP validation (proven with real project)
- **v1.0.0**: MVP release (production-ready personal toolkit)
- **v1.x.0**: Post-MVP features (modules, themes, automation)

> Note: For clarity across project documentation, the releases **v0.52 through v1.0.0** are considered collectively the "MVP" that delivers a production-ready personal toolkit. The earlier 0.52-0.55 releases are the "Foundation Phase" (incremental foundations) that prepare the codebase for the cumulative MVP deliverable.

### **Evolution Context Reference**
Need the narrative backdrop? Jump to [`QUICKSCALE.md`](../overview/quickscale.md#evolution-strategy-personal-toolkit-first) and come back here for the tasks.

---

## **MVP Roadmap: v0.51.0 → v1.0.0**

**🎯 Objective**: Build a simple project generator that creates **production-ready** Django starter projects you can use for client work immediately.

**MVP Scope**: Minimal CLI + production-ready scaffolding. Git subtree is the ONLY MVP distribution mechanism (documented manual workflow). CLI wrapper helpers for subtree operations are deferred to Post-MVP.

**Success Criteria (v1.0.0)**:
- `quickscale init myapp` generates **production-ready** Django project in < 30 seconds
- Generated project includes Docker, PostgreSQL, pytest, CI/CD, security best practices
- Generated project runs with `python manage.py runserver` immediately
- Generated project is 100% owned by user (no QuickScale dependencies by default)
- Generated project is **deployable to production** without major reconfiguration
- Git subtree workflow is documented for advanced users who want code sharing
- Can build a real client project using the generated starter

**🎯 Competitive Positioning**: Match competitors (SaaS Pegasus, Cookiecutter) on production-ready foundations while maintaining QuickScale's unique composability advantage. See [COMPETITIVE_ANALYSIS.md "What Must Be Incorporated"](../overview/competitive_analysis.md#what-quickscale-must-incorporate-from-competitors) for detailed rationale.

**IMPORTANT SCOPE CLARIFICATIONS** (from DECISIONS.md):
- ✅ Generated projects use standalone `settings.py` (NO automatic inheritance from quickscale_core)
- ✅ Git subtree is documented but MANUAL (no CLI wrapper commands in MVP)
- ✅ `quickscale_modules/` extraction is optional/personal-monorepo pattern (NOT auto-generated)
- ✅ **Production-ready foundations**: Docker, PostgreSQL, .env, security, pytest, CI/CD (competitive requirement)
- ❌ NO `backend_extensions.py` auto-generation (users add manually if needed)
- ❌ NO YAML configuration system
- ❌ NO CLI commands beyond `quickscale init`

**Competitive Insight**: Every competitor (SaaS Pegasus, Cookiecutter, Apptension) provides production-ready defaults. Without these, QuickScale won't be taken seriously by agencies and professional developers. See [COMPETITIVE_ANALYSIS.md §1-3](../overview/competitive_analysis.md#-critical-for-mvp-viability-must-have) for P0 requirements.

**Integration Note**: See [Personal Toolkit workflow in DECISIONS.md](./decisions.md#integration-note-personal-toolkit-git-subtree) for the canonical git subtree commands and CLI wrapper roadmap.

**NOT in MVP** (see [MVP Feature Matrix](./decisions.md#mvp-feature-matrix-authoritative) for authoritative list):
- ❌ Module packages (auth, payments, billing)
- ❌ Theme packages
- ❌ YAML configuration system
- ❌ PyPI distribution
- ❌ Marketplace features
- ❌ Multiple template options
- ❌ CLI wrapper commands for git subtree

---

## **Release v0.52.0: Project Foundation**

**Priority**: Establish development infrastructure before building features

**Objective**: Set up the foundational project structure, tooling, and development environment that all subsequent phases depend on.

**✅ Verifiable Improvement**:
- `quickscale_core` and `quickscale_cli` packages are installable via `pip install -e`
- `pytest` runs successfully (even with 0 tests)
- `quickscale --version` and `quickscale --help` work
- Code quality checks pass (`ruff check .`, `black --check .`)
- All package metadata is correct and installable

**Release Validation**:
```bash
# Test installation
pip install -e quickscale_core/
pip install -e quickscale_cli/

# Verify imports
python -c "import quickscale_core; print(quickscale_core.__version__)"

# Verify CLI
quickscale --version
quickscale --help

# Run tests
pytest quickscale_core/tests/
pytest quickscale_cli/tests/

# Run linters
ruff check .
black --check .
```

---

### **Task 0.52.1: Monorepo Structure Initialization**
**Priority**: FIRST - Creates workspace for all development

**Tasks**:
- [ ] **Create top-level repository structure**
  - [ ] Create `quickscale/` monorepo root with README.md, LICENSE, .gitignore
  - [ ] Initialize git repository
  - [ ] Create `docs/`, `scripts/`, `legacy/` directories
  - [ ] Copy v0.41.0 archive to `../quickscale-legacy/` if available
- [ ] **Create package directories**
  - [ ] Create `quickscale_core/` package root
  - [ ] Create `quickscale_cli/` package root
- [ ] **Create documentation directory structure**
  - [ ] Verify DECISIONS.md, QUICKSCALE.md, ROADMAP.md, SCAFFOLDING.md exist
  - [ ] Create `legacy/analysis/` for legacy analysis artifacts (see Phase 1.0.2)

**Deliverable**: Basic monorepo structure ready for package development

**Validation**: `ls -la` shows all expected directories; git repo initialized

---

### **Task 0.52.2: Legacy Analysis (OPTIONAL)**
**Priority**: Understand what to preserve before building new architecture

**Note**: This is OPTIONAL - only do this if you have previous QuickScale code to analyze. If starting fresh, skip to 0.52.3.

**Decision Basis**: `DECISIONS.md` keeps legacy consolidation guidance authoritative; this phase creates the `legacy/analysis/` directory and populates it with findings.

**Tasks**:
- [ ] **Inventory legacy QuickScale artifacts**
  - [ ] Document what exists in `../quickscale-legacy/` or v0.41.0 archive
  - [ ] List all templates, utilities, configs, and scripts
  - [ ] Note test coverage and current compatibility status
- [ ] **Evaluate reusability**
  - [ ] For each artifact, assess: purpose, test coverage, compatibility, reuse risks
  - [ ] Identify Docker configs, utilities, middleware, deployment scripts worth keeping
  - [ ] Flag deprecated patterns to avoid
- [ ] **Document findings**
  - [ ] Create `legacy/analysis/README.md` with recommended extractions
  - [ ] List specific files/patterns to migrate (with rationale)
  - [ ] List patterns to avoid (with rationale)
  - [ ] Create migration plan (which items to port, when, and how)

**Deliverable**: `legacy/analysis/README.md` with clear migration recommendations

**Validation**: Report exists; team agrees on what to extract (if anything)

**Exit Criteria**: Document created OR explicit decision that no legacy code is worth migrating

---

### **Task 0.52.3: Core Package Setup (`quickscale_core`)**
**Priority**: Set up the core package infrastructure

**Tasks**:
- [ ] **Create `quickscale_core/pyproject.toml`**
  - [ ] Add package metadata (name, version, description, authors)
  - [ ] Add build system (setuptools, build backend)
  - [ ] Add dependencies: `Jinja2` (for templates)
  - [ ] Add dev dependencies: `pytest`, `pytest-cov`, `black`, `ruff`
  - [ ] Configure package as regular package with `__init__.py` (NOT namespace package)
- [ ] **Create src layout structure**
  - [ ] Create `quickscale_core/src/quickscale_core/` directory
  - [ ] Create `quickscale_core/src/quickscale_core/__init__.py`
  - [ ] Create `quickscale_core/src/quickscale_core/version.py` with `__version__`
- [ ] **Create test infrastructure**
  - [ ] Create `quickscale_core/tests/` directory (outside src)
  - [ ] Create `quickscale_core/tests/conftest.py` for pytest configuration
  - [ ] Create `quickscale_core/pytest.ini` or `pyproject.toml` pytest config
- [ ] **Verify package installability**
  - [ ] Create virtual environment
  - [ ] Install package in editable mode: `pip install -e quickscale_core/`
  - [ ] Verify import works: `python -c "import quickscale_core; print(quickscale_core.__version__)"`

**Deliverable**: Installable `quickscale_core` package with test infrastructure

**Validation**: Package installs successfully; imports work; pytest runs (even with no tests yet)

**Directory Structure Reference**: See [SCAFFOLDING.md §3 (MVP Structure)](./scaffolding.md#mvp-structure) for authoritative layout.

---

### **Task 0.52.4: CLI Package Setup (`quickscale_cli`)**
**Priority**: Set up the CLI tool infrastructure

**Tasks**:
- [ ] **Create `quickscale_cli/pyproject.toml`**
  - [ ] Add package metadata (name, version, description, authors)
  - [ ] Add build system (setuptools, build backend)
  - [ ] Add dependencies: `click` (CLI framework), `quickscale_core` (local reference)
  - [ ] Add dev dependencies: `pytest`, `pytest-cov`, `black`, `ruff`
  - [ ] **Configure CLI entry point**: `[project.scripts]` with `quickscale = quickscale_cli.main:cli`
- [ ] **Create src layout structure**
  - [ ] Create `quickscale_cli/src/quickscale_cli/` directory
  - [ ] Create `quickscale_cli/src/quickscale_cli/__init__.py`
  - [ ] Create `quickscale_cli/src/quickscale_cli/main.py` with basic Click group
- [ ] **Create test infrastructure**
  - [ ] Create `quickscale_cli/tests/` directory (outside src)
  - [ ] Create `quickscale_cli/tests/conftest.py` for pytest configuration
  - [ ] Create `quickscale_cli/pytest.ini` or `pyproject.toml` pytest config
- [ ] **Verify CLI installability**
  - [ ] Install package in editable mode: `pip install -e quickscale_cli/`
  - [ ] Verify CLI command works: `quickscale --version`
  - [ ] Verify help works: `quickscale --help`

**Deliverable**: Installable `quickscale_cli` tool with working entry point

**Validation**: `quickscale --version` and `quickscale --help` work

---

### **Task 0.52.5: Development Environment Configuration**
**Priority**: Set up tooling for code quality and consistency

**Tasks**:
- [ ] **Create repository-wide configuration**
  - [ ] Create `.editorconfig` for editor consistency
  - [ ] Create `.gitignore` for Python, IDEs, OS files
  - [ ] Create `scripts/lint.sh` for code quality checks
  - [ ] Create `scripts/test-all.sh` for running all tests
- [ ] **Set up pre-commit hooks (optional but recommended)**
  - [ ] Create `.pre-commit-config.yaml` with black, ruff, trailing whitespace
  - [ ] Document pre-commit setup in contributing guide
- [ ] **Create development documentation**
  - [ ] Integrate contributing guidelines into DECISIONS.md
  - [ ] Document how to run tests: `pytest quickscale_core/tests/`
  - [ ] Document how to run linters: `ruff check .`
  - [ ] Document how to build packages: `python -m build`

**Deliverable**: Consistent development environment with quality tooling

**Validation**: Linters run; tests run; pre-commit works (if enabled)

---

## **Release v0.53.0: Template System**

**Priority**: Create Jinja2 templates that will be used to generate Django projects

**Objective**: Build the minimal set of templates needed to generate a working Django starter project.

**✅ Verifiable Improvement**:
- All Jinja2 templates exist and can be loaded
- Templates render correctly with sample data
- Generated output is valid (settings.py is valid Python, HTML is valid, etc.)
- Template tests pass with >90% coverage
- All required Django project files are templated

**Release Validation**:
```bash
# Test template rendering
pytest quickscale_core/tests/test_scaffold/test_templates.py -v

# Verify all templates exist
ls quickscale_core/src/quickscale_core/scaffold/templates/

# Test manual template rendering
python -c "
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
template_dir = Path('quickscale_core/src/quickscale_core/scaffold/templates')
env = Environment(loader=FileSystemLoader(str(template_dir)))
template = env.get_template('settings.py.j2')
print(template.render(project_name='testproject'))
"
```

**Template Storage**: All templates live in `quickscale_core/src/quickscale_core/scaffold/templates/` per [SCAFFOLDING.md §3](./scaffolding.md#mvp-structure).

---

### **Task 0.53.1: Core Django Project Templates (Production-Ready)**
**Priority**: Create essential Django project files with **production-ready configurations**

**🎯 Competitive Requirement**: Match Cookiecutter/Pegasus on production-ready defaults (see [COMPETITIVE_ANALYSIS.md §1](../overview/competitive_analysis.md#1-production-ready-django-foundations))

**Tasks**:
- [ ] **Create `manage.py.j2` template**
  - [ ] Standard Django manage.py with `{{project_name}}` variable
  - [ ] Executable permissions reminder in documentation
- [ ] **Create split settings templates (production-grade)**
  - [ ] **`settings/__init__.py.j2`** - Settings package marker
  - [ ] **`settings/base.py.j2`** - Shared settings (INSTALLED_APPS, MIDDLEWARE, templates, etc.)
    - [ ] **IMPORTANT**: Standalone settings (NO imports from quickscale_core)
    - [ ] Use python-decouple or django-environ for environment variables
    - [ ] Secure SECRET_KEY loading from environment
    - [ ] Proper ALLOWED_HOSTS configuration
    - [ ] Django security middleware configured
    - [ ] Static files with WhiteNoise configuration
    - [ ] Logging configuration (console + file handlers)
  - [ ] **`settings/local.py.j2`** - Development settings
    - [ ] DEBUG = True
    - [ ] SQLite database for quick local dev
    - [ ] Django Debug Toolbar enabled (optional)
  - [ ] **`settings/production.py.j2`** - Production settings
    - [ ] DEBUG = False via environment variable
    - [ ] PostgreSQL database configuration
    - [ ] Security settings (SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE, etc.)
    - [ ] Sentry integration scaffolding (commented)
- [ ] **Create `urls.py.j2` template**
  - [ ] Admin route
  - [ ] Root route pointing to index view
  - [ ] Debug toolbar URLs (if DEBUG=True)
- [ ] **Create `wsgi.py.j2` and `asgi.py.j2` templates**
  - [ ] Standard Django WSGI/ASGI applications
  - [ ] Environment-based settings module selection
- [ ] **Create `__init__.py.j2` template**
  - [ ] Empty or minimal package marker

**Deliverable**: **Production-ready** Django project templates

**Validation**: Generated settings work in both dev and production; security best practices included

**Competitive Benchmark**: Should match or exceed Cookiecutter's settings quality

**Reference**: See [SCAFFOLDING.md §5.1](./scaffolding.md#51-mvp-ultra-minimal-django-project) + [COMPETITIVE_ANALYSIS.md §1](../overview/competitive_analysis.md#1-production-ready-django-foundations)

---

### **Task 0.53.2: Templates and Static Files**
**Priority**: Create frontend templates and static file structure

**Tasks**:
- [ ] **Create `templates/index.html.j2`**
  - [ ] Simple homepage with "Welcome to {{project_name}}" message
  - [ ] Basic HTML structure (DOCTYPE, html, head, body)
  - [ ] Link to static CSS if present
- [ ] **Create `templates/base.html.j2` (optional but useful)**
  - [ ] Base template with blocks for title, content, scripts
  - [ ] Basic responsive meta tags
- [ ] **Create static files structure templates**
  - [ ] Template creates `static/css/` directory
  - [ ] Template creates `static/js/` directory
  - [ ] Template creates `static/images/` directory
  - [ ] Optional: Basic `static/css/style.css` with minimal styling

**Deliverable**: Frontend template files for generated projects

**Validation**: Templates render valid HTML; directory structure is created

---

### **Task 0.53.3: Project Metadata & DevOps Templates**
**Priority**: Create supporting files with **production-grade DevOps setup**

**🎯 Competitive Requirement**: Match Cookiecutter on DevOps quality (see [COMPETITIVE_ANALYSIS.md §1 & §5](../overview/competitive_analysis.md#5-cicd-pipeline-templates))

**Tasks**:
- [ ] **Create `pyproject.toml.j2` template (production-ready Poetry metadata)**
  - [ ] Django>=5.0,<6.0
  - [ ] psycopg2-binary (PostgreSQL driver)
  - [ ] python-decouple or django-environ (environment config)
  - [ ] whitenoise (static files in production)
  - [ ] gunicorn (production WSGI server)
  - [ ] Comment: "Production dependencies declared in pyproject.toml. Dev deps in `[tool.poetry.dev-dependencies]`"
  
- [ ] **Create Docker templates**
  - [ ] **`Dockerfile.j2`** - Production-ready multi-stage build
    - [ ] Python slim base image
    - [ ] Non-root user
    - [ ] Optimized layer caching
  - [ ] **`docker-compose.yml.j2`** - Local development setup
    - [ ] Django service with volume mounts
    - [ ] PostgreSQL service with persistent volume
    - [ ] Redis service (for future Celery)
  - [ ] **`.dockerignore.j2`** - Exclude unnecessary files
- [ ] **Create `.env.example.j2` template**
  - [ ] SECRET_KEY=your-secret-key-here
  - [ ] DEBUG=True
  - [ ] DATABASE_URL=postgresql://user:password@localhost:5432/dbname
  - [ ] ALLOWED_HOSTS=localhost,127.0.0.1
  - [ ] Comments explaining each variable
- [ ] **Create `.gitignore.j2` template**
  - [ ] Python artifacts (__pycache__, *.pyc, .pytest_cache)
  - [ ] Virtual environments (venv/, env/, .venv/)
  - [ ] Django artifacts (db.sqlite3, media/, staticfiles/)
  - [ ] IDE files (.vscode/, .idea/, *.swp)
  - [ ] Environment files (.env, .env.local)
  - [ ] Docker volumes
- [ ] **Create `README.md.j2` template (comprehensive)**
  - [ ] Project name and description
  - [ ] Prerequisites (Python, Docker, PostgreSQL)
  - [ ] **Local Development Setup** (with Docker and without)
  - [ ] Running tests instructions
  - [ ] Deployment instructions (basic)
  - [ ] Project structure overview
  - [ ] Link to QuickScale documentation
- [ ] **Create `.editorconfig.j2` template**
  - [ ] Consistent editor settings (indent, line endings, charset)

**Deliverable**: **Production-ready** project metadata and DevOps configuration

**Validation**: Docker setup works; .env loads correctly; README instructions are complete

**Competitive Benchmark**: Should match Cookiecutter's production-readiness

**Reference**: [COMPETITIVE_ANALYSIS.md §1 (Production Foundations)](../overview/competitive_analysis.md#1-production-ready-django-foundations)

---

### **Task 0.53.4: Template Testing**
**Priority**: Verify templates render correctly before integrating with generator

**Tasks**:
- [ ] **Create template rendering tests**
  - [ ] Test that all templates can be loaded by Jinja2
  - [ ] Test that all templates render with sample project_name
  - [ ] Test that rendered output is valid (e.g., settings.py is valid Python)
  - [ ] Test that required variables are used correctly
- [ ] **Create template validation script**
  - [ ] Script to render all templates with test data
  - [ ] Script to check for common issues (undefined variables, syntax errors)

**Deliverable**: Tests ensuring all templates work correctly

**Validation**: `pytest quickscale_core/tests/test_scaffold/test_templates.py` passes

---

## **Release v0.54.0: Project Generator**

**Priority**: Build the scaffolding engine that uses templates to generate projects

**Objective**: Implement the `ProjectGenerator` class that orchestrates template rendering and file creation.

**✅ Verifiable Improvement**:
- `ProjectGenerator` class can create complete Django project structure
- Generated projects have all required files in correct locations
- Generated files contain valid content (valid Python, HTML, etc.)
- Error handling works (invalid names, existing directories, permissions)
- Generator tests pass with >80% coverage

**Release Validation**:
```bash
# Test generator programmatically
python -c "
from pathlib import Path
from quickscale_core.scaffold import ProjectGenerator
import tempfile
import os

with tempfile.TemporaryDirectory() as tmpdir:
    gen = ProjectGenerator()
    output_path = Path(tmpdir) / 'testproject'
    gen.generate('testproject', output_path)

  # Verify structure
  assert (output_path / 'manage.py').exists()
  assert (output_path / 'testproject' / 'settings.py').exists()
  assert (output_path / 'pyproject.toml').exists()
  print('✅ Generator works!')
"

# Run generator tests
pytest quickscale_core/tests/test_scaffold/test_generator.py -v
```

---

### **Task 0.54.1: Core Generator Logic**
**Priority**: Implement the main generator class

**Tasks**:
- [ ] **Create `quickscale_core/src/quickscale_core/scaffold/` package**
  - [ ] Create `__init__.py` exposing ProjectGenerator
  - [ ] Create `generator.py` with ProjectGenerator class
- [ ] **Implement ProjectGenerator class**
  - [ ] `__init__(self, template_dir: Path = None)` - Initialize with template directory
  - [ ] `generate(self, project_name: str, output_path: Path) -> None` - Main generation method
  - [ ] Template loading using Jinja2 Environment
  - [ ] Variable substitution (project_name, etc.)
  - [ ] Directory structure creation
  - [ ] File writing with correct permissions
- [ ] **Implement file utilities**
  - [ ] Create `quickscale_core/src/quickscale_core/utils/file_utils.py`
  - [ ] `ensure_directory(path: Path)` - Create directory if not exists
  - [ ] `write_file(path: Path, content: str, executable: bool = False)` - Write with permissions
  - [ ] `validate_project_name(name: str) -> bool` - Check valid Python package name

**Code Structure**:
```python
# quickscale_core/src/quickscale_core/scaffold/generator.py
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

class ProjectGenerator:
    def __init__(self, template_dir: Path | None = None):
        """Initialize generator with template directory"""
        if template_dir is None:
            # Use default template directory in package
            template_dir = Path(__file__).parent / "templates"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))

    def generate(self, project_name: str, output_path: Path) -> None:
        """Generate minimal Django project"""
        # Validate project name
        # Create project directory
        # Render all templates
        # Write files to disk
        pass
```

**Deliverable**: Working ProjectGenerator that creates project structure

**Validation**: Generator can create all files and directories; files contain correct content

---

### **Task 0.54.2: Generator Error Handling & Validation**
**Priority**: Make generator robust and user-friendly

**Tasks**:
- [ ] **Add input validation**
  - [ ] Validate project name is valid Python identifier
  - [ ] Reject reserved names (test, django, etc.)
  - [ ] Check output path doesn't already contain project
  - [ ] Validate output path is writable
- [ ] **Add error handling**
  - [ ] Handle template loading errors gracefully
  - [ ] Handle file system errors (permissions, disk full, etc.)
  - [ ] Provide clear error messages for common issues
  - [ ] Rollback on partial failure (clean up created files)
- [ ] **Add generation logging**
  - [ ] Log files being created (optional, for debugging)
  - [ ] Report success/failure clearly

**Deliverable**: Robust generator with good error messages

**Validation**: Error cases are handled; clear messages shown to users

---

### **Task 0.54.3: Generator Testing**
**Priority**: Ensure generator works correctly in all scenarios

**Tasks**:
- [ ] **Create generator unit tests**
  - [ ] Test project creation in empty directory
  - [ ] Test project name validation
  - [ ] Test error handling (invalid names, existing projects, permission issues)
  - [ ] Test template rendering with various project names
- [ ] **Create generator integration tests**
  - [ ] Test end-to-end: generate project → files exist → valid Python
  - [ ] Test generated project can be imported as Python package
  - [ ] Test generated manage.py is executable
- [ ] **Create fixtures and test utilities**
  - [ ] Temporary directory fixture for test projects
  - [ ] Clean-up utilities for test artifacts

**Deliverable**: Comprehensive test suite for ProjectGenerator

**Validation**: `pytest quickscale_core/tests/test_scaffold/` passes with >80% coverage

---

## **Release v0.55.0: CLI Implementation**

**Priority**: Implement the command-line interface for `quickscale init`

**Objective**: Create a simple, user-friendly CLI that calls ProjectGenerator.

**✅ Verifiable Improvement**:
- `quickscale init myapp` command works end-to-end
- Generated projects are functional Django applications
- CLI provides helpful error messages and next-steps guidance
- CLI tests pass with >75% coverage
- **CRITICAL**: Can actually create a working Django project from command line!

**Release Validation**:
```bash
# Test CLI end-to-end
cd /tmp
quickscale init testproject
cd testproject

# Verify generated project works
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
# Recommended: use Poetry
poetry install
poetry run python manage.py check
poetry run python manage.py migrate
poetry run python manage.py runserver &
SERVER_PID=$!
sleep 3
curl http://localhost:8000 | grep "Welcome"
kill $SERVER_PID

# Run CLI tests
cd -
pytest quickscale_cli/tests/ -v
```

---

### **Task 0.55.1: CLI Command Structure**
**Priority**: Implement the main CLI command

**Tasks**:
- [ ] **Implement main CLI entry point**
  - [ ] Create `quickscale_cli/src/quickscale_cli/main.py`
  - [ ] Set up Click group with `@click.group()`
  - [ ] Add `--version` flag showing quickscale_cli version
  - [ ] Add `--help` text explaining QuickScale
- [ ] **Implement `init` command**
  - [ ] Create `quickscale_cli/src/quickscale_cli/commands/init.py`
  - [ ] Add `@click.command()` decorator
  - [ ] Add `@click.argument('project_name')` for required project name
  - [ ] Call ProjectGenerator from quickscale_core
  - [ ] Handle errors and show user-friendly messages
- [ ] **Add output formatting**
  - [ ] Success message: "✅ Created project: {project_name}"
  - [ ] Next steps instructions (cd, runserver commands)
  - [ ] Error messages in red (using Click.secho)

**Code Structure**:
```python
# quickscale_cli/src/quickscale_cli/main.py
import click
from quickscale_cli.commands.init import init

@click.group()
@click.version_option()
def cli():
    """QuickScale - Compose your Django SaaS"""
    pass

cli.add_command(init)

# quickscale_cli/src/quickscale_cli/commands/init.py
import click
from pathlib import Path
from quickscale_core.scaffold import ProjectGenerator

@click.command()
@click.argument('project_name')
def init(project_name: str):
    """Generate a new Django project"""
    try:
        generator = ProjectGenerator()
        output_path = Path.cwd() / project_name
        generator.generate(project_name, output_path)

        click.secho(f"✅ Created project: {project_name}", fg='green')
        click.echo("\nNext steps:")
        click.echo(f"  cd {project_name}")
        click.echo("  # Recommended: use Poetry for dependency management")
        click.echo("  poetry install")
        click.echo("  python manage.py migrate")
        click.echo("  python manage.py runserver")
    except Exception as e:
        click.secho(f"❌ Error: {e}", fg='red', err=True)
        raise click.Abort()
```

**Deliverable**: Working `quickscale init` command

**Validation**: `quickscale init myapp` creates working Django project

**CLI Reference**: See [CLI Command Matrix in DECISIONS.md](./decisions.md#cli-command-matrix) for authoritative command list.

---

### **Task 0.55.2: CLI Testing**
**Priority**: Test CLI commands work correctly

**Tasks**:
- [ ] **Create CLI command tests**
  - [ ] Test `quickscale --version` shows correct version
  - [ ] Test `quickscale --help` shows help text
  - [ ] Test `quickscale init myapp` creates project
  - [ ] Test `quickscale init` without argument shows error
  - [ ] Test `quickscale init` with invalid name shows error
- [ ] **Create CLI integration tests**
  - [ ] Test full workflow: install CLI → run init → project works
  - [ ] Test in isolated environment (fresh virtualenv)
- [ ] **Use Click's testing utilities**
  - [ ] Use `CliRunner` for testing commands
  - [ ] Capture output and verify messages

**Deliverable**: Comprehensive CLI test suite

**Validation**: `pytest quickscale_cli/tests/` passes with >75% coverage

---

## **Release v0.56.0: Quality, Testing & CI/CD**

**Priority**: Ensure MVP is robust, production-ready, and professionally packaged

**Objective**: Comprehensive testing, quality checks, CI/CD automation, and validation.

**🎯 Competitive Requirement**: Match Cookiecutter on testing setup and CI/CD (see [COMPETITIVE_ANALYSIS.md §3 & §5](../overview/competitive_analysis.md#3-testing--quality-infrastructure))

**✅ Verifiable Improvement**:
- Test coverage >80% for quickscale_core, >75% for quickscale_cli
- pytest with factory_boy configured in generated projects
- GitHub Actions CI/CD pipeline working for generated projects
- Pre-commit hooks configured and documented
- All code quality checks pass (ruff, black, mypy optional)
- Integration tests pass (full workflow from CLI to working project)
- Cross-platform testing (Linux, macOS, Windows if possible)
- Cross-version testing (Python 3.10, 3.11, 3.12)

**Release Validation**:
```bash
# Run full test suite with coverage
pytest --cov=quickscale_core --cov=quickscale_cli --cov-report=term-missing

# Verify coverage thresholds
pytest --cov=quickscale_core --cov-fail-under=80
pytest --cov=quickscale_cli --cov-fail-under=75

# Run quality checks
ruff check .
black --check .
mypy quickscale_core/ quickscale_cli/  # optional

# Run integration tests
pytest -m integration -v

# Test on multiple Python versions (if possible)
tox  # or manually test with py310, py311, py312
```

---

### **Task 0.56.1: Integration Testing**
**Priority**: Test the complete workflow end-to-end

**Tasks**:
- [ ] **Create end-to-end integration test**
  - [ ] Test: `quickscale init testproject` → project created
  - [ ] Test: Generated project structure matches expected layout
  - [ ] Test: `cd testproject && python manage.py check` passes
  - [ ] Test: `python manage.py migrate` works
  - [ ] Test: `python manage.py runserver` starts (smoke test)
  - [ ] Test: Generated project imports work (`import testproject`)
- [ ] **Test with different project names**
  - [ ] Simple names: `myapp`, `testproject`
  - [ ] Names with underscores: `my_app`, `test_project`
  - [ ] Edge cases: single letter (`x`), long names
- [ ] **Test error scenarios**
  - [ ] Project directory already exists
  - [ ] Invalid project names (with hyphens, starting with number, etc.)
  - [ ] Insufficient permissions

**Deliverable**: Integration test suite covering real-world usage

**Validation**: All integration tests pass; generated projects are usable

---

### **Task 0.56.2: Code Quality, Coverage & CI/CD Templates**
**Priority**: Ensure code quality meets professional standards + add CI/CD to generated projects

**🎯 Competitive Requirement**: Generated projects must include CI/CD like Cookiecutter (see [COMPETITIVE_ANALYSIS.md §5](../overview/competitive_analysis.md#5-cicd-pipeline-templates))

**Tasks**:
- [ ] **Achieve test coverage targets**
  - [ ] `quickscale_core`: >80% coverage
  - [ ] `quickscale_cli`: >75% coverage
  - [ ] Focus on critical paths (generator, file I/O, validation)
- [ ] **Run code quality checks**
  - [ ] Run `ruff check .` - no errors
  - [ ] Run `black --check .` - code formatted
  - [ ] Run `mypy .` - type checking passes (optional but recommended)
- [ ] **Create CI/CD templates for generated projects**
  - [ ] **`.github/workflows/ci.yml.j2`** - GitHub Actions workflow
    - [ ] Run tests on push/PR
    - [ ] Test matrix: Python 3.10, 3.11, 3.12
    - [ ] Test matrix: Django 4.2, 5.0
    - [ ] Run linters (ruff, black)
    - [ ] Upload coverage reports
  - [ ] **`.github/workflows/deploy.yml.j2`** - Deployment workflow (basic example)
  - [ ] **`.pre-commit-config.yaml.j2`** - Pre-commit hooks
    - [ ] black (code formatting)
    - [ ] ruff (linting)
    - [ ] trailing-whitespace, end-of-file-fixer
- [ ] **Create pytest templates for generated projects**
  - [ ] **`pytest.ini.j2`** or **`pyproject.toml`** pytest section
    - [ ] Configure test paths
    - [ ] Django settings module
    - [ ] Coverage settings (>80% requirement)
  - [ ] **`conftest.py.j2`** - Pytest fixtures
    - [ ] Example factory fixtures using factory_boy
    - [ ] Database fixtures
  - [ ] **`tests/test_example.py.j2`** - Example test demonstrating patterns
- [ ] **Document coverage gaps**
  - [ ] Identify untested edge cases
  - [ ] Document why certain code is excluded from coverage (if any)
  - [ ] Create follow-up tasks for improving coverage

**Deliverable**: High-quality, well-tested codebase + CI/CD templates for generated projects

**Validation**: All quality checks pass; generated projects have working CI/CD pipeline

**Competitive Benchmark**: Generated projects should have CI/CD quality matching Cookiecutter

**Reference**: [COMPETITIVE_ANALYSIS.md §3 (Testing Infrastructure)](../overview/competitive_analysis.md#3-testing--quality-infrastructure) and [§5 (CI/CD)](../overview/competitive_analysis.md#5-cicd-pipeline-templates)

---

### **Task 0.56.3: Documentation Testing**
**Priority**: Ensure generated projects work as documented

**Tasks**:
- [ ] **Test README instructions**
  - [ ] Follow generated project README step-by-step
  - [ ] Verify all commands work (venv creation, pip install, migrate, runserver)
  - [ ] Fix any documentation errors
- [ ] **Test with fresh Python environment**
  - [ ] Test with Python 3.10, 3.11, 3.12 (different versions)
  - [ ] Test on different OS: Linux, macOS, Windows (if possible)
- [ ] **Validate generated pyproject.toml / poetry.lock**
  - [ ] All packages install successfully
  - [ ] No version conflicts
  - [ ] Django version is compatible

**Deliverable**: Verified documentation and cross-platform compatibility

**Validation**: README instructions work on multiple platforms/Python versions

---

## **Release v0.57.0: Documentation Complete**

**Priority**: Complete all user-facing and developer documentation

**Objective**: Ensure users and contributors can understand and use QuickScale effectively.

**✅ Verifiable Improvement**:
- README.md includes installation and usage examples
- Git subtree workflow documented in DECISIONS.md
- Developer documentation (integrated into DECISIONS.md) complete
- All documentation links work and point to correct sections
- Generated project README provides clear next steps

**Release Validation**:
```bash
# Verify documentation exists
ls README.md DECISIONS.md ROADMAP.md SCAFFOLDING.md

# Check for broken links (optional)
markdown-link-check *.md

# Verify user can follow docs
# (Manual: follow README from scratch as new user)

# Verify generated project docs
quickscale init doctest
cat doctest/README.md  # Should have clear instructions
```

---

### **Task 0.57.1: User Documentation**
**Priority**: Create comprehensive user-facing documentation

**Tasks**:
- [ ] **Update README.md**
  - [ ] Add installation instructions for quickscale CLI
  - [ ] Add usage examples with `quickscale init`
  - [ ] Add "What you get" section (generated project structure)
  - [ ] Update links to other documentation
- [ ] **Update DECISIONS.md** (if needed)
  - [ ] Document any technical decisions made during implementation
  - [ ] Update MVP Feature Matrix status (mark completed features)
- [ ] **Create developer documentation**
  - [ ] Document project structure (monorepo layout)
  - [ ] Document how to contribute
  - [ ] Document how to run tests and linters
  - [ ] Document release process (when ready)
- [ ] **Document Git Subtree workflow** (for advanced users)
  - [ ] Verify manual git subtree commands in DECISIONS.md are accurate
  - [ ] Create troubleshooting guide for common git subtree issues
  - [ ] Document when/why users might want to embed quickscale_core

**Deliverable**: Complete documentation for MVP users and contributors

**Validation**: New user can follow docs and create their first project

**Documentation Reference**: See [DECISIONS.md Document Responsibilities](./decisions.md#document-responsibilities-short) for what goes where.

---

---

## **Release v0.58.0: MVP Validation**

**Priority**: **MOST CRITICAL** - Validate MVP with real-world usage

**Objective**: Prove that QuickScale actually works for building client projects.

**✅ Verifiable Improvement**:
- **Built a complete client project** using `quickscale init`
- Project includes real features (CRUD, auth, or other business logic)
- Project deployed to staging environment (optional but recommended)
- Documented pain points and improvement areas
- Created prioritized backlog for v1.0.0 refinements

**Release Validation**:
```bash
# This is a MANUAL validation process

# 1. Create project
quickscale init real_client_project
cd real_client_project

# 2. Set up and run
python -m venv venv
source venv/bin/activate
# Recommended: use Poetry
poetry install
poetry run python manage.py migrate
poetry run python manage.py runserver

# 3. Build real features (spend 1-2 days)
# - Add models
# - Add views
# - Add templates
# - Add tests
# - Verify everything works

# 4. Document experience
# - What worked well?
# - What was confusing?
# - What's missing?
# - What needs fixing before v1.0.0?
```

**SUCCESS CRITERIA**: Can build a deployable client project in < 1 day using QuickScale.

---

### **Task 0.58.1: Real-World Project Validation**
**Priority**: **MOST IMPORTANT** - Validate MVP with actual usage

**Tasks**:
- [ ] **Generate a real client project**
  - [ ] Use `quickscale init client_test` to create project
  - [ ] Follow all setup steps (venv, install, migrate, runserver)
  - [ ] Build a simple feature (e.g., basic CRUD, user registration, etc.)
  - [ ] Deploy to staging environment (optional but recommended)
- [ ] **Document pain points**
  - [ ] Note any missing features or unclear documentation
  - [ ] Record any errors or confusing error messages
  - [ ] Identify workflow improvements needed
- [ ] **Collect feedback**
  - [ ] What worked well?
  - [ ] What was confusing or difficult?
  - [ ] What would make the MVP more useful?
- [ ] **Create improvement backlog**
  - [ ] Log issues found during validation
  - [ ] Prioritize fixes vs. Post-MVP enhancements
  - [ ] Update roadmap with lessons learned

**Deliverable**: PROOF that MVP works for real projects + prioritized improvement list

**Success Criteria**: Can build a working client project from generated starter in < 1 day

**This is the MOST IMPORTANT step**: If you can't build a real client project with MVP, it's not done.

---

### **Task 0.58.2: Improvement Backlog Creation**
**Priority**: Prepare MVP for initial release

**Tasks**:
- [ ] **Version and tagging**
  - [ ] Set version to `0.1.0` in `pyproject.toml` files
  - [ ] Create git tag: `v0.1.0`
  - [ ] Create CHANGELOG.md with MVP release notes
- [ ] **Package verification**
  - [ ] Build packages: `python -m build` in both quickscale_core and quickscale_cli
  - [ ] Test installation from built wheels
  - [ ] Verify package metadata is correct
- [ ] **Create release notes**
  - [ ] Summarize what's included in MVP
  - [ ] Clearly state limitations (what's NOT included)
  - [ ] Link to documentation and getting started guide
  - [ ] Include upgrade path from v0.41.0 (manual migration required)
- [ ] **Optional: PyPI test upload**
  - [ ] Upload to TestPyPI for validation
  - [ ] Test installation from TestPyPI
  - [ ] NOTE: Public PyPI release is optional for MVP (can stay git-only)

**Deliverable**: Shippable MVP release (v0.1.0)

**Validation**: Clean install works; README guides users successfully

---

## **Release v1.0.0: MVP Launch** 🚀

**Priority**: Production-ready release of personal toolkit

**Objective**: Stable, documented, tested personal toolkit ready for real client work.

**✅ Verifiable Improvement**:
- All v0.58.0 feedback addressed
- Release artifacts built and tested
- CHANGELOG.md complete with all changes since v0.51.0
- Git tag created (v1.0.0)
- Optional: Published to TestPyPI or PyPI

**Release Validation**:
```bash
# Build release packages
cd quickscale_core && python -m build && cd ..
cd quickscale_cli && python -m build && cd ..

# Test installation from wheels
pip install quickscale_core/dist/quickscale_core-1.0.0-*.whl
pip install quickscale_cli/dist/quickscale_cli-1.0.0-*.whl

# Verify everything works
quickscale --version  # Should show 1.0.0
quickscale init v1test
cd v1test && python manage.py check

# Create git tag
git tag -a v1.0.0 -m "Release v1.0.0: MVP Personal Toolkit"
git push origin v1.0.0

# Optional: publish to PyPI
twine upload quickscale_core/dist/* quickscale_cli/dist/*
```

**🎉 SUCCESS CRITERIA**:
- Complete personal toolkit for generating Django projects
- Proven with real client project
- Ready for daily use
- Foundation for Post-MVP evolution

---

### **Task 1.0.1: Address v0.58.0 Feedback**
**Tasks**:
- [ ] Fix all critical issues found during real project validation
- [ ] Improve unclear documentation
- [ ] Add missing templates or utilities if needed
- [ ] Re-test with another project if major changes made

### **Task 1.0.2: Release Preparation**
**Tasks**:
- [ ] Set version to `1.0.0` in all `pyproject.toml` files
- [ ] Create CHANGELOG.md with all changes v0.51.0 → v1.0.0
- [ ] Build packages: `python -m build`
- [ ] Test installation from built wheels
- [ ] Create git tag: `v1.0.0`
- [ ] Optional: Upload to TestPyPI first, then PyPI

**Deliverable**: Production-ready QuickScale v1.0.0

---

## **MVP Deliverables Summary (v1.0.0)**

### **✅ v1.0.0 Deliverables - Personal Toolkit (Production-Ready)**
- [ ] 📦 `quickscale_core` package with minimal utilities and template engine
- [ ] 📦 `quickscale_cli` package with `quickscale init` command
- [ ] 🏗️ Project scaffolding creating **production-ready** Django starter with:
  - [ ] ✅ Docker setup (docker-compose.yml + Dockerfile)
  - [ ] ✅ PostgreSQL configuration (development + production)
  - [ ] ✅ Environment-based settings (.env + split settings)
  - [ ] ✅ Security best practices (SECRET_KEY, ALLOWED_HOSTS, middleware)
  - [ ] ✅ pytest + factory_boy test setup
  - [ ] ✅ GitHub Actions CI/CD pipeline
  - [ ] ✅ Pre-commit hooks (black, ruff, isort)
  - [ ] ✅ WhiteNoise static files configuration
  - [ ] ✅ Gunicorn WSGI server for production
- [ ] 🖥️ Ultra-simple CLI: `quickscale init myapp`
- [ ] 📁 Git subtree workflow documented for advanced users
- [ ] ✅ Comprehensive testing (>75% coverage)
- [ ] 📖 User and developer documentation
- [ ] ✅ **VALIDATION: Build 1 real client project successfully**

**🎯 Competitive Achievement**: Match SaaS Pegasus and Cookiecutter on production-ready foundations while maintaining composability advantage. See [COMPETITIVE_ANALYSIS.md Critical Path](../overview/competitive_analysis.md#critical-path-to-competitiveness).

### **Explicit MVP Limitations (By Design)**
See [MVP Feature Matrix in DECISIONS.md](./decisions.md#mvp-feature-matrix-authoritative) for authoritative list.

- ❌ **No module packages**: Build from real needs in Phase 2
- ❌ **No theme packages**: Generated projects are fully customizable
- ❌ **No YAML configuration**: Django settings.py only
- ❌ **No CLI git subtree helpers**: Manual commands documented (Post-MVP consideration)
- ❌ **No PyPI distribution**: Git subtree only for MVP (PyPI optional)
- ❌ **No marketplace**: Personal toolkit, not platform
- ❌ **No multiple templates**: One starter template only
- ❌ **No settings inheritance**: Standalone settings.py by default
- ❌ **No backend_extensions.py auto-generation**: Users add manually if needed

**The Point**: Build the absolute minimum that lets you create client projects faster. Everything else is Post-MVP.

---

## **Post-MVP: Organic Evolution (v1.1.0+)**

**🎯 Objective**: Extract reusable patterns from real client work. Don't build speculatively.

**Timeline**: Ongoing (happens naturally as you build more client projects)

**Release Strategy**: Minor versions (v1.x.0) add incremental improvements based on real usage

**Key Principle**: **Build modules from REAL client needs, not speculation**

**Namespace Packaging Transition Timeline**:
- **v1.0.0 (MVP)**: Regular packages with temporary `__init__.py` allowed
- **v1.1.0 (First module)**: Remove namespace `__init__.py`, adopt PEP 420
- **v1.2.0+**: All new modules MUST use PEP 420 from start

**CI Reminder**: Add a pre-publish CI check (pre-release or package build job) that fails when `quickscale_modules/__init__.py` or `quickscale_themes/__init__.py` exist. This prevents accidental publishing with an `__init__.py` present and enforces the PEP 420 transition.

**Prerequisites Before Starting Post-MVP Development**:
- ✅ MVP (Phase 1) completed and validated
- ✅ Built 2-3 client projects successfully using MVP
- ✅ Identified repeated patterns worth extracting
- ✅ Git subtree workflow working smoothly

### **v1.1.0 - v1.x.0: Pattern Extraction & Module Development**

Each release adds one proven module or significant improvement based on real needs.

**Example Release Sequence** (aligned with competitive priorities):

- **v1.1.0**: `quickscale_modules.auth` - django-allauth integration (P1 - Critical for SaaS)
- **v1.2.0**: `quickscale_modules.billing` - dj-stripe subscriptions (P1 - Core monetization)
- **v1.3.0**: `quickscale_modules.teams` - Multi-tenancy patterns (P1 - B2B requirement) 🎯 **SAAS FEATURE PARITY MILESTONE**
- **v1.4.0**: `quickscale_modules.notifications` - Email infrastructure (P2 - Common need)
- **v1.5.0 (conditional) or v2.0**: CLI git subtree helpers (implement lightweight helpers in v1.5 if manual workflow proves painful; v2.0 reserved for richer orchestration/automation if demand justifies it)
- **v1.6.0**: HTMX frontend variant template (P2 - Differentiation)
- **v1.7.0**: React frontend variant template (P2 - SPA option)
- **v1.x.0**: Additional modules based on real client needs

**🎯 Competitive Parity Goal (v1.3.0)**: At this point, QuickScale matches SaaS Pegasus on core features (auth, billing, teams) while offering superior architecture (composability, shared updates). See [COMPETITIVE_ANALYSIS.md Timeline](../overview/competitive_analysis.md#timeline-reality-check).

**Note**: Prioritization is based on competitive analysis. Adjust based on YOUR actual client needs.

---

### **Pattern Extraction Workflow**

#### **When to Extract a Module**
✅ **Extract when**:
- You've built the same feature 2-3 times across client projects
- The code is stable and battle-tested
- The pattern is genuinely reusable (not client-specific)
- The feature would benefit from centralized updates

❌ **Don't extract when**:
- You've only built it once
- It's highly client-specific
- You're just guessing it might be useful
- The code is still experimental or changing rapidly

#### **Extraction Process**
1. **Identify Reusable Code**: Look for repeated patterns across client projects
2. **Create Module Structure**: `quickscale_modules/<module_name>/` in your monorepo
3. **Extract & Refactor**: Move code, make it generic, add tests
4. **Update Client Projects**: Replace custom code with module via git subtree
5. **Document**: Add module documentation and usage examples

**Git Subtree Commands**: See [DECISIONS.md Git Subtree Workflow](./decisions.md#integration-note-personal-toolkit-git-subtree) for authoritative manual commands.

**Note**: CLI wrapper commands for extraction/sync remain Post-MVP. Evaluate after establishing extraction workflow.

---

### **Module Creation Guide (for v1.x.0 releases)**

**Don't build these upfront. Build them when you actually need them 2-3 times.**

#### **Prioritized Module Development Sequence** (based on competitive analysis):

**Phase 2 Priorities** (see [COMPETITIVE_ANALYSIS.md Module Roadmap](../overview/competitive_analysis.md#phase-2-post-mvp-v1---saas-essentials)):

1. **🔴 P1: `quickscale_modules.auth`** (First module)
   - Wraps django-allauth with social auth providers
   - Custom User model patterns
   - Email verification workflows
   - Account management views
   - **Rationale**: Every SaaS needs auth; Pegasus proves django-allauth is correct choice

2. **🔴 P1: `quickscale_modules.billing`** (Second module)
   - Wraps dj-stripe for Stripe subscriptions
   - Plans, pricing tiers, trials
   - Webhook handling with logging
   - Invoice management
   - **Rationale**: Core SaaS monetization; Stripe-only reduces complexity

3. **🔴 P1: `quickscale_modules.teams`** (Third module)
   - Multi-tenancy patterns (User → Team → Resources)
   - Role-based permissions (Owner, Admin, Member)
   - Invitation system with email tokens
   - Row-level security query filters
   - **Rationale**: Most B2B SaaS requires team functionality

4. **🟡 P2: `quickscale_modules.notifications`** (Fourth module)
   - Wraps django-anymail for multiple email backends
   - Transactional email templates
   - Async email via Celery
   - Email tracking scaffolding

5. **🟡 P2: `quickscale_modules.api`** (Fifth module, if needed)
   - Wraps Django REST framework
   - Authentication patterns
   - Serializer base classes

**Extraction Rule**: Only build after using 2-3 times in real client projects. Don't build speculatively.

**Competitive Context**: This sequence matches successful competitors' feature prioritization while maintaining QuickScale's reusability advantage. See [COMPETITIVE_ANALYSIS.md Strategic Recommendations](../overview/competitive_analysis.md#strategic-recommendations).

#### **Admin Module Scope**

The admin module scope has been defined in [DECISIONS.md Admin Module Scope Definition](./DECISIONS.md#admin-module-scope-definition).

**Summary**: Enhanced Django admin interface with custom views, system configuration, monitoring dashboards, and audit logging. Distinct from auth module (user authentication/authorization).

#### **Module Creation Checklist**:
- [ ] Used successfully in 2-3 client projects
- [ ] Code is stable and well-tested
- [ ] Genuinely reusable (not client-specific hacks)
- [ ] Documented with examples and integration guide
- [ ] Distributed via git subtree to other projects
- [ ] Consider PEP 420 namespace packages if multiple modules exist

**Module Structure Reference**: See [SCAFFOLDING.md §4 (Post-MVP Modules)](./scaffolding.md#post-mvp-structure) for canonical package layout.

---

### **Git Subtree Workflow Refinement (v1.5 conditional / Post-MVP)**

Based on MVP usage feedback, improve code sharing workflow:

**Evaluate CLI Automation** (target: v1.5 conditional; defer to v2.0 if tied to marketplace automation):
- [ ] **Assess demand for CLI helpers**
  - [ ] Survey how often you use git subtree manually
  - [ ] Document pain points with manual workflow
  - [ ] Determine if automation would save significant time
- [ ] **If justified, add CLI commands (target v1.5; conditional)**:
  - [ ] `quickscale embed-core <project>` - Embed quickscale_core via git subtree
  - [ ] `quickscale update-core <project>` - Pull updates from monorepo
  - [ ] `quickscale sync-push <project>` - Push improvements back to monorepo
  - [ ] Update [CLI Command Matrix](./decisions.md#cli-command-matrix) with implementation status
- [ ] **Document versioning strategy**
  - [ ] Git tags for stable snapshots (e.g., `core-v1.0.0`)
  - [ ] Semantic versioning for modules
  - [ ] Compatibility tracking between core and modules
- [ ] **Create extraction helper scripts** (optional)

**Success Criteria (example)**: Implement CLI helpers when one or more of the following are true:
- Manual subtree operations exceed 10 instances/month across maintainers OR
- Teams have performed 5+ module extractions manually and report significant time savings from automation.

(Adjust thresholds based on observed usage and community feedback.)
  - [ ] Script to assist moving code from client project to quickscale_modules/
  - [ ] Validation script to check module structure

**Note**: Only build these if the manual workflow becomes a bottleneck. Don't automate prematurely.

---

### **Configuration System Evaluation (potential v1.x.0 release)**

**After 5+ client projects**, evaluate if YAML config would be useful.

**Questions to answer**:
- Do you find yourself repeating the same Django settings setup?
- Would declarative config speed up project creation?
- Is Django settings inheritance working well enough?
- Would non-developers benefit from YAML-based project config?

**Decision Point**: Add YAML config ONLY if it solves real pain points from MVP usage.

**If pursuing**:
- [ ] Define minimal configuration schema (see [DECISIONS.md illustrative schemas](./decisions.md#architectural-decision-configuration-driven-project-definition))
- [ ] Implement config loader and validator
- [ ] Create CLI commands: `quickscale validate`, `quickscale generate`
- [ ] Update templates to support config-driven generation
- [ ] Document configuration options

---

## **v2.0.0+: Community Platform (Optional Evolution)**

**🎯 Objective**: IF proven successful personally, evolve into community platform.

**Timeline**: 12-18+ months after MVP (or never, if personal toolkit is enough)

**Version Strategy**: Major version (v2.0.0) for community platform features

**Example Release Sequence**:
- **v2.0.0**: PyPI publishing + package distribution
- **v2.1.0**: Theme package system
- **v2.2.0**: Marketplace basics
- **v2.x.0**: Advanced community features

**Prerequisites Before Starting v2.0.0**:
- ✅ 10+ successful client projects built with QuickScale
- ✅ 5+ proven reusable modules extracted
- ✅ Clear evidence that others want to use your patterns
- ✅ Bandwidth to support community and marketplace

### **v2.0.0: Package Distribution**

When you're ready to share with community:

- [ ] **Setup PyPI publishing for modules**
  - [ ] Convert git subtree modules to pip-installable packages
  - [ ] Use PEP 420 implicit namespaces (`quickscale_modules.*`)
  - [ ] Implement semantic versioning and compatibility tracking
  - [ ] Create GitHub Actions for automated publishing
- [ ] **Create private PyPI for commercial modules** (see [COMMERCIAL.md](../overview/commercial.md))
  - [ ] Set up private package repository
  - [ ] Implement license validation for commercial modules
  - [ ] Create subscription-based access system
- [ ] **Document package creation for community contributors**
  - [ ] Package structure guidelines
  - [ ] Contribution process
  - [ ] Quality standards and testing requirements

---

### **v2.1.0: Theme Package System**

If reusable business logic patterns emerge:

- [ ] **Create theme package structure** (`quickscale_themes.*`)
  - [ ] Define theme interface and base classes
  - [ ] Implement theme inheritance system
  - [ ] Create theme packaging guidelines
- [ ] **Create example themes**
  - [ ] `quickscale_themes.starter` - Basic starter theme
  - [ ] `quickscale_themes.todo` - TODO app example
  - [ ] Document theme customization patterns
- [ ] **Document theme creation guide**
  - [ ] Theme architecture overview
  - [ ] Base model and business logic patterns
  - [ ] Frontend integration guidelines

**Theme Structure Reference**: See [SCAFFOLDING.md §4 (Post-MVP Themes)](./scaffolding.md#post-mvp-structure).

---

### **v2.2.0: Marketplace & Community**

Only if there's real demand:

- [ ] **Build package registry/marketplace**
  - [ ] Package discovery and search
  - [ ] Ratings and reviews system
  - [ ] Module/theme compatibility tracking
- [ ] **Create community contribution guidelines**
  - [ ] Code of conduct
  - [ ] Contribution process and standards
  - [ ] Issue and PR templates
- [ ] **Setup extension approval process**
  - [ ] Quality review checklist
  - [ ] Security audit process
  - [ ] Compatibility verification
- [ ] **Build commercial module subscription system**
  - [ ] License management
  - [ ] Payment integration
  - [ ] Customer access control

See [COMMERCIAL.md](../overview/commercial.md) for detailed commercial distribution strategies.

---

### **v2.3.0: Advanced Configuration**

If YAML config proves useful in Phase 2:

- [ ] **Implement full configuration schema**
  - [ ] Module/theme selection via config
  - [ ] Environment-specific overrides
  - [ ] Customization options
- [ ] **Add module/theme selection via config**
  - [ ] Declarative module dependencies
  - [ ] Theme selection and variants
- [ ] **Create migration tools for config updates**
  - [ ] Schema version migration scripts
  - [ ] Backward compatibility checks
- [ ] **Build configuration validation UI** (optional)
  - [ ] Web-based config editor
  - [ ] Real-time validation
  - [ ] Preview generated project

**IMPORTANT**: v2.0.0+ is OPTIONAL. Many successful solo developers and agencies never need a community platform. Evaluate carefully before investing in marketplace features.

---

### **🎯 MVP Focus**

- Single command CLI: `quickscale init myapp`
- Standalone generated projects (no forced dependencies)
- Git subtree documented but manual (no CLI automation)
- One starter template (no variants)
- Clear path to working Django projects
- Validation with real client project

This roadmap can be implemented incrementally, with each task building on the previous ones, leading to a working MVP that validates the architecture before adding complexity.

---

### **Appendix: Quick Reference**

### **Key Documents**
- **MVP Scope**: [DECISIONS.md MVP Feature Matrix](./decisions.md#mvp-feature-matrix-authoritative)
- **Git Subtree Workflow**: [DECISIONS.md Integration Note](./decisions.md#integration-note-personal-toolkit-git-subtree)
- **Directory Structures**: [SCAFFOLDING.md](./scaffolding.md)
- **Strategic Vision**: [QUICKSCALE.md](../overview/quickscale.md#evolution-strategy-personal-toolkit-first)
- **Commercial Models**: [COMMERCIAL.md](../overview/commercial.md)

### **Release Quick Reference**
- **v0.52.0**: Project foundation (packages, tooling, dev environment)
- **v0.53.0**: Templates (Jinja2 templates for Django projects)
- **v0.54.0**: Generator (scaffolding engine)
- **v0.55.0**: CLI (`quickscale init` command)
- **v0.56.0**: Quality & testing (comprehensive test suite)
- **v0.57.0**: Documentation (user guides complete)
- **v0.58.0**: MVP validation (real project built)
- **v1.0.0**: MVP release (production-ready personal toolkit)
- **v1.x.0**: Post-MVP (modules extracted from real needs)
- **v2.0.0+**: Community platform (optional, if proven successful)

### **Version Milestone Mapping**

| Version | Milestone | Competitive Status |
|---------|-----------|-------------------|
| v1.0.0 | MVP Launch | Foundation ready |
| v1.1.0 | Auth Module | Closing feature gap |
| v1.2.0 | Billing Module | Near parity |
| v1.3.0 | Teams Module | **🎯 SaaS Feature Parity** |
| v1.4.0+ | Additional Modules | Differentiation & ecosystem growth |
| v2.0.0+ | Community Platform | Optional marketplace capabilities |

---

**Maintainers**: Update this roadmap as tasks are completed. Mark completed tasks with ✅. When technical scope changes, update DECISIONS.md first, then update this roadmap to reflect those decisions.
