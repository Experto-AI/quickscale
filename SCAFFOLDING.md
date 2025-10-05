# SCAFFOLDING: Repository, Packages, and Generated Project Structures

> Authoritative guide to the directory/file scaffolding for QuickScale across MVP and post-MVP phases. Complements: `DECISIONS.md` (technical rules), `ROADMAP.md` (timeline/tasks), `README.md` (user intro), `QUICKSCALE.md` (strategy).

## Table of Contents
1. Scope & Principles
2. Monorepo Target Layout (Ultimate End-State)
3. Phase 1 (MVP) Required Structure
4. Post-MVP Expansion (Modules & Themes)
5. Generated Project Output (MVP & Post-MVP)
6. Naming & Packaging Matrix (Summary)
7. Rationale Mapping to Decisions
8. Evolution Phases & Incremental Adoption
9. Crosswalk: Requirement → Artifact
10. Future Optional Enhancements
11. Authoring & Maintenance Notes

---
## 1. Scope & Principles
The scaffolding defined here covers:
- Repository-level directory layout (monorepo approach)
- Individual package internal `src/` layouts
- Generated end-user Django project structure (what `quickscale init` produces)
- Progressive evolution from MVP (minimal core) to full ecosystem (modules + themes)

Guiding principles:
- Explicit > implicit (Django-aligned)
- Isolated packages with clear responsibilities
- Inheritance-friendly theme base classes; additive customization
- Configuration-driven assembly (creation-time, not runtime dynamic loading)
- Tests *outside* `src/` for clean distributions

---
## 2. Monorepo Target Layout (Post-MVP End-State)

**⚠️ POST-MVP**: This structure represents the target end-state after Phase 2+. For MVP structure, see Section 3 below.

```
quickscale/
├── README.md
├── QUICKSCALE.md
├── DECISIONS.md
├── ROADMAP.md
├── SCAFFOLDING.md                 # (this file)
├── LICENSE
├── CONTRIBUTING.md
├── CHANGELOG.md
├── pyproject.toml                  # (Optional aggregate tooling meta)
├── scripts/
│   ├── bootstrap.sh
│   ├── lint.sh
│   ├── test-all.sh
│   └── release.py
├── tools/
│   ├── codegen/
│   └── quality/
├── docs/
│   ├── architecture/
│   │   ├── overview.md
│   │   ├── backend-modules.md
│   │   ├── themes.md
│   │   └── frontend-patterns.md
│   ├── development/
│   │   ├── local-setup.md
│   │   ├── testing.md
│   │   ├── packaging.md
│   │   └── releasing.md
│   ├── user/
│   │   ├── quickstart.md
│   │   ├── config-schema.md
│   │   ├── backend-extensions-guide.md
│   │   └── upgrading.md
│   └── reference/
│       ├── config-json-schema.md
│       └── api/
├── schemas/
│   ├── quickscale-config-v1.json
│   ├── migrations/
│   │   ├── v1_to_v2.json
│   │   └── README.md
│   └── examples/
│       ├── mvp-minimal.yml
│       ├── starter-basic.yml
│       ├── todo-with-payments.yml
│       └── enterprise-sample.yml
├── examples/
│   ├── minimal/
│   ├── starter-customized/
│   └── todo-extended/
├── legacy/
│   ├── quickscale-legacy/
│   └── analysis/
│       └── legacy-analysis.md
├── quickscale_core/
├── quickscale_cli/                # CLI tool for project management (MVP: project generation only)
├── quickscale_modules/
│   ├── auth/
│   ├── payments/
│   └── billing/
├── quickscale_themes/
│   ├── starter/
│   └── todo/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   ├── publish-core.yml
│   │   ├── publish-module.yml
│   │   └── docs.yml
│   ├── ISSUE_TEMPLATE/
│   └── dependabot.yml
├── .pre-commit-config.yaml
├── .editorconfig
└── .gitignore
```

### Example: personal monorepo (MVP-friendly layout)

The following example is the practical, MVP-friendly monorepo layout recommended for solo developers using the "Personal Toolkit" approach (git subtree). It's more verbose than the high-level Post-MVP tree above and is intended as a copyable reference for setting up your own quickscale monorepo.

```
quickscale/ (your private repo)
├── quickscale_core/                 # Core package: scaffolding, minimal utils
│   ├── pyproject.toml
│   └── src/quickscale_core/
│       ├── __init__.py
│       ├── settings/                # Base Django settings templates
│       │   ├── base.py
│       │   ├── dev.py
│       │   └── production.py
│       ├── scaffold/                # Project generator templates + logic
│       │   ├── generator.py
│       │   └── templates/
│       │       ├── manage.py.j2
│       │       ├── settings.py.j2
│       │       └── requirements.txt.j2
│       └── utils/
├── quickscale_cli/                  # Minimal CLI for `quickscale init`
│   ├── pyproject.toml
│   └── src/quickscale_cli/
│       ├── main.py
│       └── commands/init.py
├── quickscale_modules/              # Place to extract reusable Django apps
│   ├── __init__.py                  # Regular package to simplify imports in MVP
│   ├── auth/
│   ├── billing/
│   └── common/
├── project_template/                # Cookiecutter-style starter template (optional)
│   └── {{project_name}}/
├── scripts/
│   ├── new_project.sh
│   └── extract_module.sh
├── docs/
│   └── workflows.md                 # git subtree examples and extraction notes
└── README.md
```

Notes:
- This layout is intentionally simple: core + CLI + modules + templates. Use git subtree to embed `quickscale_core`/`quickscale_modules` into client repos.
- When a feature proves reusable, extract it into `quickscale_modules/<feature>/` and commit to the monorepo.
- For archival history, keep long-form rationale and comparisons in `docs/legacy/` or `legacy/` rather than the repo root.


---
## 3. Phase 1 (MVP) Required Structure
Only `quickscale_core` + `quickscale_cli` needed. NO schemas, NO examples, NO packaged themes. Just project scaffolding templates.

```
quickscale_core/
├── pyproject.toml
├── src/quickscale_core/
│   ├── __init__.py
│   ├── version.py
│   ├── scaffold/
│   │   ├── __init__.py
│   │   ├── generator.py            # ProjectGenerator (simple!)
│   │   └── templates/
│   │       ├── manage.py.j2
│   │       ├── settings.py.j2      # Basic Django settings
│   │       ├── urls.py.j2
│   │       ├── wsgi.py.j2
│   │       ├── asgi.py.j2
│   │       ├── requirements.txt.j2 # Django + essentials
│   │       └── templates/
│   │           └── index.html.j2   # Hello World homepage
│   └── utils/                      # Optional utilities (minimal)
│       ├── __init__.py
│       └── file_utils.py           # Basic file operations
└── tests/
    ├── test_scaffold/
    │   ├── test_generator.py
    │   └── test_templates.py
    └── test_integration.py
```

**MVP Simplifications:**
- ❌ NO config/ directory (no YAML loading)
- ❌ NO apps.py (not a Django app in MVP)
- ❌ NO complex utils (just basics)
- ❌ NO automatic `backend_extensions.py` regeneration — the MVP may include a small
    `backend_extensions.py` *stub* in generated projects to illustrate the pattern, but
    users own and modify it; it is not managed or overwritten by the CLI. Treat this file
    as optional and minimal. Projects do not rely on a runtime extension system in MVP.
- ❌ NO variants system (just one simple template)

```
quickscale_cli/
├── pyproject.toml
├── src/quickscale_cli/
│   ├── __init__.py
│   ├── main.py                     # Ultra-simple CLI entry point
│   └── commands/
│       ├── __init__.py
│       └── init.py                 # Just 'quickscale init <name>'
└── tests/
    └── test_cli.py

**MVP Simplifications:**
- ❌ NO update/sync commands (users perform manual git subtree operations as documented)
- ❌ NO git/ directory (no automation in MVP)
- ❌ NO validate/generate commands (Post-MVP)
- ❌ NO complex IO (just basic print)

**Philosophy**: One command. That's it. `quickscale init myapp`

Note: Git subtree documentation is provided for users who want code sharing. Manual subtree commands are the supported MVP workflow; CLI automation for subtree update/sync workflows is planned for Post-MVP.
```

---
## 4. Post-MVP Expansion (Modules & Themes)
Each module/theme is an independently publishable package. Namespaces `quickscale_modules` & `quickscale_themes` are PEP 420 implicit (no namespace `__init__.py`).

Example module (`auth`):
```
quickscale_modules/auth/
├── pyproject.toml
├── src/quickscale_modules/auth/
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── services.py
│   ├── adapters.py
│   ├── urls.py
│   ├── views/
│   │   ├── __init__.py
│   │   └── login.py
│   ├── templates/quickscale_modules_auth/login.html
│   └── migrations/0001_initial.py
└── tests/
    ├── test_models.py
    ├── test_views.py
    └── test_integration.py
```

Example theme (`starter`):
```
quickscale_themes/starter/
├── pyproject.toml
├── src/quickscale_themes/starter/
│   ├── __init__.py
│   ├── apps.py
│   ├── base_models.py              # Inheritance-friendly base classes
│   ├── business.py
│   ├── urls.py
│   ├── templates/quickscale_themes_starter/
│   │   ├── base.html
│   │   └── dashboard.html
│   └── migrations/0001_initial.py
└── tests/
    ├── test_base_models.py
    └── test_business_logic.py
```

---
## 5. Generated Project Output
### 5.1 MVP (Ultra-Minimal Django Project)
```
myapp/
├── manage.py                    # Standard Django
├── myapp/
│   ├── __init__.py
│   ├── settings.py             # Basic Django settings
│   ├── urls.py                 # Minimal URL config
│   ├── wsgi.py
│   └── asgi.py
├── templates/
│   └── index.html              # Simple "Hello World" homepage
├── static/
│   └── css/
├── requirements.txt            # Django + essentials only
├── .gitignore
└── README.md                   # Next steps guidance

# Optional: User can manually add git subtree later
# (Not generated by MVP CLI)
```

**What Users Get:**
- Working Django project in 30 seconds
- Runnable with `python manage.py runserver`
- 100% theirs to customize
- No QuickScale dependencies unless they want them

Practical client settings example (how to import QuickScale base settings when `quickscale_core` is embedded via git subtree):

```python
# myapp/config/settings/base.py
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# If you embedded quickscale/ via git subtree, add it to the path so imports work:
sys.path.insert(0, str(BASE_DIR / 'quickscale'))

# Import QuickScale base settings (optional)
try:
    from quickscale_core.settings import *  # noqa: F401,F403
except Exception:
    # QuickScale core not embedded — fall back to local defaults
    pass

# Override client-specific settings below
DEBUG = True
ALLOWED_HOSTS = ['localhost']
```

### Extraction workflow (Personal Toolkit)

When a feature implemented inside a client project becomes reusable, follow the extraction workflow:

1. Create a module folder inside `quickscale_modules/`, e.g. `quickscale_modules/reports/`.
2. Move or copy the reusable code from the client project into the module directory.
3. Add tests and generic configuration where needed.
4. Commit and push to your quickscale monorepo.
5. In client repos, add or update the module via git subtree (see DECISIONS.md for commands).

This extraction pattern keeps the MVP minimal while enabling shared improvements across your projects.

**Deferred to Post-MVP:**
- ❌ quickscale.yml (no config system)
- ❌ backend_extensions.py (just customize directly)
- ❌ custom_frontend/ structure (just use templates/)
- ❌ variants system
- ❌ Embedded quickscale/ directory (optional, manual)

### 5.2 Post-MVP (Starter theme + modules, user selection)
```
myapp/
├── quickscale.yml
├── pyproject.toml
├── manage.py
├── backend_extensions.py
├── myapp/
│   ├── __init__.py
│   ├── settings.py                 # Adds quickscale_core, theme, modules to INSTALLED_APPS
│   ├── urls.py
│   ├── asgi.py
│   ├── wsgi.py
│   └── modules_overrides/
│       └── __init__.py
├── custom_frontend/
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   └── overrides/ (optional theme template overrides)
│   ├── variants/
│   │   ├── default/
│   │   └── dark/
│   └── static/
│       ├── css/
│       ├── js/
│       └── img/
├── scripts/
│   ├── dev.sh
│   └── collectstatic.sh
└── README.md
```

---
## 6. Naming & Import Matrix (Summary)
| Concern | Import Path | Django App Label |
|--------|-------------|------------------|
| Core | quickscale_core | quickscale_core |
| CLI | quickscale_cli | (n/a) |
| Auth Module | quickscale_modules.auth | quickscale_modules_auth |
| Payments Module | quickscale_modules.payments | quickscale_modules_payments |
| Billing Module | quickscale_modules.billing | quickscale_modules_billing |
| Starter Theme | quickscale_themes.starter | quickscale_themes_starter |
| TODO Theme | quickscale_themes.todo | quickscale_themes_todo |

Rules: Dotted namespaces for import, underscore-qualified app labels to avoid collisions. Shared namespace roots (`quickscale_modules`, `quickscale_themes`) are PEP 420 implicit (no `__init__.py`).

---
## 7. Rationale Mapping to Decisions
| Decision (DECISIONS.md) | Scaffold Enforcement |
|-------------------------|----------------------|
| Library-Style Modules | Independent `quickscale_modules/<name>/` packages |
| Configuration-Driven | Central `schemas/` + `config/` loader & validator |
| Backend Extension Pattern | Generated `backend_extensions.py` + theme `base_models.py` |
| Directory-Based Frontend | `custom_frontend/` with `templates/`, `static/`, `variants/` |
| Git Subtree Distribution | Manual git subtree commands for MVP; CLI helpers (e.g. `git/subtree_manager.py`) are Post-MVP examples |
| PEP 420 Namespaces | No `__init__.py` at `quickscale_modules/` root |
| Tests Outside src | `package/tests/` placement enforced |
| Creation-Time Assembly | Generator emits static Django project (no runtime plugin loading) |

---
## 8. Evolution Phases & Incremental Adoption
| Phase | Adds | Deliverables |
|-------|------|-------------|
| 1 (MVP) | Core + CLI | Config load, scaffolding, create command, git subtree setup |
| 2 | Starter Theme | Theme packaging, inheritance base classes |
| 3 | First Module (auth) | Module packaging, settings integration |
| 4 | Update/Sync Commands | Full CLI for managing multiple client projects |
| 5 | Hooks & Advanced Modules | Extensibility, analytics, notifications |

Backward compatibility stance: Config migrations tracked under `schemas/migrations/` when schema version increments.

---
## 9. Crosswalk: Requirement → Artifact
| Requirement | Artifact |
|-------------|----------|
| Declarative config | `schemas/quickscale-config-v1.json`, `config/loader.py` |
| Simple project generation | `scaffold/generator.py` + templates tree |
| Backend inheritance | Generated `backend_extensions.py` + theme `base_models.py` |
| Frontend variants | `custom_frontend/variants/<variant>/` |
| Git subtree management | Manual git subtree commands documented for MVP; CLI helpers (`git/subtree_manager.py`) are Post-MVP examples |
| Shared updates | Manual subtree workflows in MVP; CLI `update`/`sync` helpers are Post-MVP |
| Clear naming conventions | Packaging matrix (§6) |
| Future theme/module marketplace | Namespaced package roots + independent pyproject.toml files |

---
## 10. Future Optional Enhancements
- `integrations/` root for third-party connectors (post Phase 5)
- `playground/` (gitignored) for manual generation QA
- `benchmark/` for performance profiling scripts
- Automatic doc build pipeline -> `docs/reference/api/` from docstrings
- Scaffold diff/preview command: `quickscale preview` (dry-run)
- Config migration CLI: `quickscale migrate-config --from 1 --to 2`
-- Batch update commands (Post-MVP example): `quickscale update-all --dry-run`
- Pluggable template overlays for modules (`overrides/` folder detection)

---
## 11. Authoring & Maintenance Notes
- When adding a new package: follow naming matrix, create `pyproject.toml`, add to CI publish workflow.
- When adding CLI commands (Post-MVP): update `quickscale_cli/commands/`, add corresponding tests, ensure git operations use `git/subtree_manager.py` (or equivalent helper). For MVP, prefer documenting manual git subtree workflows.
- Never place tests under `src/`; enforce via CI linter.
- Template additions require test coverage in `test_scaffold/test_templates.py`.
- CLI command additions require integration tests in `test_integration/`.
- Backwards-incompatible config changes require: schema bump, migration spec, docs update (`config-schema.md`).
- Keep `backend_extensions.py` minimal—users own its content, so minimize regeneration risk (no destructive overwrites).

---
**Status Legend (for ROADMAP correlation)**:
- Implemented: Update this file & ROADMAP
- Planned: Listed here, open tasks in ROADMAP
- Deferred: Mark explicitly in ROADMAP with rationale
- CLI Integration: Commands in `quickscale_cli/` with git subtree management

---
Maintainers: Update this document whenever structural conventions change. Treat as canonical scaffolding specification.
