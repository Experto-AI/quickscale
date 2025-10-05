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
## 2. Monorepo Target Layout (Ultimate End-State)
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
├── quickscale_cli/                # CLI tool for project management and git subtree operations
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

---
## 3. Phase 1 (MVP) Required Structure
Only `quickscale_core` + `quickscale_cli` + schemas/examples needed. A minimal starter theme is included in generated projects as part of the MVP.
```
quickscale_core/
├── pyproject.toml
├── src/quickscale_core/
│   ├── __init__.py
│   ├── version.py
│   ├── apps.py                     # QuickScaleCoreConfig
│   ├── config/
│   │   ├── __init__.py
│   │   ├── loader.py               # ProjectConfig.from_file()
│   │   ├── schema_validator.py
│   │   └── errors.py
│   ├── scaffold/
│   │   ├── __init__.py
│   │   ├── generator.py            # ProjectGenerator
│   │   ├── context.py              # Template context assembly
│   │   └── templates/
│   │       ├── project/
│   │       │   ├── manage.py.j2
│   │       │   ├── pyproject.toml.j2
│   │       │   ├── requirements.txt.j2
│   │       │   ├── settings.py.j2
│   │       │   ├── urls.py.j2
│   │       │   ├── backend_extensions.py.j2
│   │       │   └── asgi.py.j2
│   │       └── frontend/
│   │           ├── templates/
│   │           │   ├── base.html.j2
│   │           │   └── index.html.j2
│   │           ├── static/
│   │           │   ├── css/style.css.j2
│   │           │   └── js/app.js.j2
│   │           └── variants/
│   │               └── default/README.md.j2
│   └── utils/
│       ├── __init__.py
│       ├── file_utils.py
│       ├── version_utils.py
│       ├── django_utils.py
│       └── logging_utils.py
└── tests/
    ├── test_config/
    │   ├── test_loader.py
    │   ├── test_validator.py
    │   └── fixtures/
    │       ├── valid-minimal.yml
    │       ├── invalid-missing-name.yml
    │       └── invalid-extra-field.yml
    ├── test_scaffold/
    │   ├── test_generator.py
    │   └── test_templates.py
    ├── test_utils/
    │   ├── test_file_utils.py
    │   └── test_version_utils.py
    └── test_integration/
        └── test_end_to_end.py
```
```
quickscale_cli/
├── pyproject.toml
├── src/quickscale_cli/
│   ├── __init__.py
│   ├── main.py                     # Entry point → console_scripts = quickscale
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── create.py               # Project creation with git subtree setup
│   │   ├── update.py               # Git subtree pull operations
│   │   ├── sync.py                 # Git subtree push operations
│   │   ├── validate.py             # MVP optional
│   │   ├── init.py                 # Post-MVP
│   │   └── generate.py             # Post-MVP
│   ├── git/
│   │   ├── subtree_manager.py      # Git subtree operations abstraction
│   │   └── repo_manager.py         # Repository management utilities
│   ├── io/
│   │   ├── printer.py
│   │   └── prompts.py
│   └── errors.py
└── tests/
    ├── test_create_command.py
    ├── test_update_command.py
    └── test_sync_command.py

Note: Git subtree is the default distribution strategy for Phase 1 (MVP). Publishing packages to a package index (pip) for private/subscription distribution is a Post-MVP activity (see `COMMERCIAL.md`).
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
### 5.1 MVP (No real theme/modules yet)
```
myapp/
├── quickscale.yml
├── pyproject.toml (or requirements.txt depending on template strategy)
├── manage.py
├── myapp/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── backend_extensions.py
├── custom_frontend/
│   ├── templates/
│   │   ├── base.html
│   │   └── index.html
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/app.js
│   └── variants/
│       └── default/README.md
├── .env.example
├── .gitignore
└── README.md
```

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
| Git Subtree Distribution | CLI commands in `quickscale_cli/commands/` with `git/subtree_manager.py` |
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
| Git subtree management | `quickscale_cli/git/subtree_manager.py` + CLI commands |
| Shared updates | CLI `update`/`sync` commands for code sharing between repos |
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
- Batch update commands: `quickscale update-all --dry-run`
- Pluggable template overlays for modules (`overrides/` folder detection)

---
## 11. Authoring & Maintenance Notes
- When adding a new package: follow naming matrix, create `pyproject.toml`, add to CI publish workflow.
- When adding CLI commands: update `quickscale_cli/commands/`, add corresponding tests, ensure git operations use `git/subtree_manager.py`.
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
