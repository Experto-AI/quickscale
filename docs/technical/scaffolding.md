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

🔎 **Post-MVP reference**: This structure represents the target end-state after Phase 2+. For MVP structure, see Section 3 below.

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
│   └── analysis/            # Consolidated location for legacy analysis artifacts
├── quickscale_core/
├── quickscale_cli/                # CLI tool for project management (MVP: project generation only)
├── quickscale_modules/
│   ├── auth/
│   ├── payments/
│   ├── billing/
│   └── admin/               # Enhanced admin UX and admin-related helpers (scope TBD - under evaluation)
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

ℹ️ **Note**: `quickscale_modules/` shown below is optional for personal monorepos only, NOT part of generated projects. See [Module Extraction Clarification](./decisions.md#integration-note-personal-toolkit-git-subtree-) for authoritative guidance.

The following example is the practical, MVP-friendly monorepo layout recommended for solo developers using the "Personal Toolkit" approach (git subtree). It's more verbose than the high-level Post-MVP tree above and is intended as a copyable reference for setting up your own quickscale monorepo.

```
quickscale/ (your private repo)
├── quickscale_core/                 # Core package: scaffolding, minimal utils (package source for maintainers)
│   └── src/quickscale_core/
│       ├── __init__.py
│       ├── settings/                # Base Django settings templates (used when embedding quickscale_core)
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
├── quickscale_cli/                  # Minimal CLI for `quickscale init` (CLI source for maintainers)
│   
│   └── src/quickscale_cli/
│       ├── main.py
│       └── commands/init.py
├── quickscale_modules/              # OPTIONAL personal-monorepo convenience for extracting reusable Django apps (NOT required for MVP)
│   ├── __init__.py                  # Optional convenience during MVP only. Remove before publishing as standalone packages.
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

-- This layout is intentionally simple: core + CLI + (optional) modules + templates. Git subtree is a documented advanced workflow to embed `quickscale_core` into client repos. Lightweight CLI helpers for subtree operations are planned but not shipped as part of the initial `quickscale init` release. For authoritative technical decisions and tie-breakers, see `DECISIONS.md`.
- Note on `__init__.py`: `quickscale_modules/` is intended as a PEP 420 namespace root in the Post-MVP architecture (no `__init__.py`). During early MVP development a temporary `__init__.py` may exist to simplify local imports; it is considered a local convenience and should be removed before extracting or publishing modules as standalone packages.
- When a feature proves reusable, extract it into `quickscale_modules/<feature>/` and commit to the monorepo.
- For archival history, keep long-form rationale and comparisons in `docs/legacy/` or `legacy/` rather than the repo root.

Requirements vs Packaging note: See [Package Structure and Naming Conventions in DECISIONS.md](./decisions.md#package-structure-and-naming-conventions) for canonical guidance on generated project dependencies versus package metadata.


---
## 3. Phase 1 (MVP) Required Structure {#mvp-structure}
Only `quickscale_core` + `quickscale_cli` needed. NO schemas, NO examples, NO packaged themes. Just project scaffolding templates.

🔎 **Scope note**: For in/out status defer to the [MVP Feature Matrix](./decisions.md#mvp-feature-matrix-authoritative). This section focuses on the file tree details only.

```
quickscale_core/
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
│   │           └── index.html.j2   # Simple homepage
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
- ❌ NO config/ directory (no YAML/JSON configuration loading in MVP)
- ❌ NO apps.py (not a Django app in MVP)
- ❌ NO complex utils (just basics)
- ❌ NO `backend_extensions.py` generation in MVP — see [backend_extensions.py policy](./decisions.md#backend-extensions-policy)
- ❌ NO variants system (just one simple template)
- ❌ NO automatic settings inheritance (standard Django `settings.py` only). Generated starters are standalone by default; optional inheritance patterns are documented for advanced users in `DECISIONS.md`.

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
- ❌ NO automated CLI wrappers: manual `git subtree` commands remain the supported workflow in MVP (see the [canonical workflow in DECISIONS.md](./decisions.md#integration-note-personal-toolkit-git-subtree)).
- ❌ NO git/ directory (no automation in MVP)
- ❌ NO validate/generate commands (Post-MVP)
- ❌ NO complex IO (just basic print)

**Philosophy**: One command. That's it. `quickscale init myapp`

Note: Git subtree documentation is provided for users who want code sharing. Manual subtree commands are documented for transparency and advanced users. For the status of potential Post-MVP CLI wrapper helpers, defer to the [CLI command matrix in DECISIONS.md](./decisions.md#cli-command-matrix).
```

---
## 4. Post-MVP Expansion (Modules & Themes) {#post-mvp-structure}
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
│   └── index.html              # Simple homepage
├── static/
│   └── css/
├── requirements.txt            # Django + essentials only
├── .gitignore
└── README.md                   # Next steps guidance

# Git subtree (ONLY MVP distribution mechanism)
# Commands live in DECISIONS.md to keep documentation single-sourced.
```

**What Users Get:**
- Working Django project in 30 seconds
- Runnable with `python manage.py runserver`
- 100% theirs to customize
- No QuickScale dependencies unless they want them

### MVP Settings (Standalone)

Practical client settings example (how to import QuickScale base settings when `quickscale_core` is embedded via git subtree):

```python
# myapp/config/settings/base.py (MVP Pattern)
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# MVP uses standard Django settings (no inheritance)
# Settings inheritance from quickscale_core.settings is Post-MVP (TBD if needed)

DEBUG = True
ALLOWED_HOSTS = ['localhost']
SECRET_KEY = 'django-insecure-change-this-in-production'

# Standard Django configuration...
```

### Post-MVP Settings (Inheritance - Illustrative Only)

ℹ️ **Post-MVP reference**: See [`DECISIONS.md`](./decisions.md#integration-note-personal-toolkit-git-subtree-) for the illustrative inheritance patterns. Phase 1 projects stay standalone.

### Extraction workflow (Personal Toolkit)

When a feature implemented inside a client project becomes reusable, follow the extraction workflow:

1. Create a module folder inside `quickscale_modules/`, e.g. `quickscale_modules/reports/`.
2. Move or copy the reusable code from the client project into the module directory.
3. Add tests and generic configuration where needed.
4. Commit and push to your quickscale monorepo.
5. In client repos, add or update the module via git subtree (see DECISIONS.md for commands).

This extraction pattern keeps the MVP minimal while enabling shared improvements across your projects.

- **Deferred to Post-MVP (illustrative / NOT in MVP):**
- ❌ `quickscale.yml` and a `config/` directory (no YAML/JSON config system in MVP)
- ❌ backend_extensions.py (not generated by MVP; customize directly if needed)
- ❌ custom_frontend/ structure (just use templates/)
- ❌ variants system
- ❌ Embedded quickscale/ directory (optional, manual)

### 5.2 Post-MVP (Starter theme + modules, user selection)

ℹ️ **Post-MVP reference** – consult the MVP matrix for current scope.
```
myapp/
├── quickscale.yml           # Post-MVP illustrative for future config system
├── pyproject.toml           # (user-added, not generated by quickscale init)
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

Rules: Dotted namespaces for imports, underscore-qualified app labels to avoid collisions. Shared namespace roots (`quickscale_modules`, `quickscale_themes`) are PEP 420 implicit (no `__init__.py`). This table is canonical; DECISIONS.md references it rather than duplicating details.

---
## 7. Rationale Mapping to Decisions
| Decision (DECISIONS.md) | Scaffold Enforcement |
|-------------------------|----------------------|
| Library-Style Modules | Independent `quickscale_modules/<name>/` packages |
| Configuration-Driven | Central `schemas/` + `config/` loader & validator |
| Backend Extension Pattern | Post‑MVP / illustrative: `backend_extensions.py` + theme `base_models.py` (MVP does NOT auto-generate this file) |
| Directory-Based Frontend | `custom_frontend/` with `templates/`, `static/`, `variants/` |
| Git Subtree Distribution | Manual `git subtree` commands are documented for transparency; track planned wrapper helpers in the [CLI command matrix](./decisions.md#cli-command-matrix). |
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
| Backend inheritance | Post‑MVP / illustrative: `backend_extensions.py` + theme `base_models.py` (MVP does NOT auto-generate this file) |
| Frontend variants | `custom_frontend/variants/<variant>/` |
| Git subtree management | Manual git subtree commands are documented for transparency; the CLI does NOT expose wrapper commands for embed/update/sync workflows in the initial MVP. Potential helper automation sits on the Post-MVP backlog (see `quickscale_cli/`) and may be expanded if justified. |
| Shared updates | CLI wrapper commands for subtree update/sync remain Post-MVP backlog items and are NOT included in the initial MVP; additional helper libraries and batch automation may be expanded Post-MVP |
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
- CLI commands (MVP): keep the surface limited to `quickscale init`. If Post-MVP wrapper commands ship, implement them in `quickscale_cli/commands/` with corresponding tests, ensure git operations delegate to a tested helper (for example `git/subtree_manager.py`), and update the [CLI command matrix](./decisions.md#cli-command-matrix). Manual `git subtree` commands remain documented for advanced users and recovery scenarios.
- Never place tests under `src/`; enforce via CI linter.
- Template additions require test coverage in `test_scaffold/test_templates.py`.
- CLI command additions require integration tests in `test_integration/`.
- Backwards-incompatible config changes require: schema bump, migration spec, docs update (`config-schema.md`).
- Keep `backend_extensions.py` minimal—users own its content, so minimize regeneration risk (no destructive overwrites).
 - Keep `backend_extensions.py` minimal—users own its content, so minimize regeneration risk (no destructive overwrites). Note: the MVP CLI will not generate this file automatically; Post‑MVP generators may offer an optional template.

---
**Status Legend (for ROADMAP correlation)**:
- Implemented: Update this file & ROADMAP
- Planned: Listed here, open tasks in ROADMAP
- Deferred: Mark explicitly in ROADMAP with rationale
- CLI Integration: Commands in `quickscale_cli/` with git subtree management

---
Maintainers: Update this document whenever structural conventions change. Treat as canonical scaffolding specification.
