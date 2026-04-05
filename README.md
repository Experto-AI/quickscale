# 🚀 QuickScale

[![PyPI version](https://img.shields.io/pypi/v/quickscale.svg)](https://pypi.org/project/quickscale/)
[![CI](https://github.com/Experto-AI/quickscale/actions/workflows/ci.yml/badge.svg)](https://github.com/Experto-AI/quickscale/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-90%25-green.svg)](https://github.com/Experto-AI/quickscale/actions/workflows/ci.yml)
[![Python 3.14+](https://img.shields.io/badge/python-3.14+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/Experto-AI/quickscale?color=green)](https://github.com/Experto-AI/quickscale/releases)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

> **You are here**: **QuickScale README** (Project Overview)
> **Related docs**: [Start Here](START_HERE.md) | [Glossary](GLOSSARY.md) | [Decisions](docs/technical/decisions.md) | [User Manual](docs/technical/user_manual.md)

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

QuickScale is a **creator-led Django project generator and module workspace** for building client SaaS applications. It grew out of repeated owner/client work and now turns those patterns into reusable starter themes, first-party modules, and production-ready foundations.

---

## What is QuickScale?

QuickScale is a **Django project generator** that creates production-ready SaaS applications with one command. Designed for **solo developers and development agencies**, it gives you:

- **Production-ready foundations**: Docker, PostgreSQL, testing, CI/CD, and security out-of-the-box
- **One-command deployment**: Deploy to Railway with `quickscale deploy railway`
- **Full ownership**: Generated projects are 100% yours to customize—no vendor lock-in
- **Standardized stack**: Build multiple client projects faster with consistent best practices
- **Implemented first-party modules on the main branch today**: analytics, auth, backups, blog, crm, forms, listings, notifications, social, and storage
- **Creator-led evolution**: New capabilities land because they solve real project needs first, then get generalized into the shared stack

The current published release is v0.81.0, which adds maintainer-only beta-site migration tooling with deterministic fresh-first execution and checkpoint-first in-place continuation.

QuickScale evolves through tagged releases and real owner usage rather than a separate phase model. For the current implementation surface, use [decisions.md](./docs/technical/decisions.md), [roadmap.md](./docs/technical/roadmap.md), and [CHANGELOG.md](./CHANGELOG.md).

On the main branch, backups is the admin/ops-first safety module: private local artifacts are the default, optional private remote offload is supported, and generated local Docker and Railway PostgreSQL projects use PostgreSQL 18 custom dumps as the real backup/restore path. JSON artifacts are export-only rather than restore inputs, admin download and validate stay local-file-only in v1, and the BackupPolicy admin page exposes a guarded restore action only for row-backed local artifacts already present on disk. Exact filename confirmation and the existing environment gate remain required, admin restore never materializes remote-only artifacts, CLI restore keeps its existing syntax, and already-generated projects that predate this follow-up must manually adopt the current Docker/CI/E2E PostgreSQL 18 tooling updates.

## Documentation Guide

**Start here for your needs:**
- 📖 **New user?** You're in the right place. This README shows you what QuickScale is and how to get started.
- 🔧 **Need commands?** See [user_manual.md](./docs/technical/user_manual.md) for all commands and workflows
- 🚀 **Deploying to Railway?** See [railway.md](./docs/deployment/railway.md) for Railway deployment guide
- 📋 **Planning a feature?** Check [decisions.md](./docs/technical/decisions.md) for the authoritative implementation scope and technical rules
- 🗓️ **Timeline & tasks?** See [roadmap.md](./docs/technical/roadmap.md)
- 🏗️ **Project structure?** See [scaffolding.md](./docs/technical/scaffolding.md) for complete directory layouts
- 🎯 **Why QuickScale?** See [quickscale.md](./docs/overview/quickscale.md) for competitive positioning

**Quick Reference:**
- **Current distribution** = Modules embed via git subtree; starter themes generate once and become user-owned code
- **Release history** = [CHANGELOG.md](./CHANGELOG.md) plus official tagged release notes in `docs/releases/`
- **Generated Project** = Output of `quickscale plan`, then entering the generated directory and running `quickscale apply`

See [decisions.md - Document Responsibilities](./docs/technical/decisions.md#document-responsibilities) for complete terminology and Single Source of Truth reference

**Package reference docs (informational context only):**
- [quickscale/README.md](./quickscale/README.md) - meta-package packaging notes
- [quickscale_cli/README.md](./quickscale_cli/README.md) - CLI package scope and command groups
- [quickscale_core/README.md](./quickscale_core/README.md) - core scaffolding package boundaries

If package README text differs from repo docs, [README.md](./README.md) and [decisions.md](./docs/technical/decisions.md) win.


### Primary Use Cases:
- **Solo Developer**: Build client projects faster with production-ready foundations
- **Development Agency**: Standardize your tech stack across client engagements
- **Creator Maintaining Multiple Projects**: Reuse working patterns across owner-led or client-facing Django applications

### Development Flow
1. `quickscale plan myapp` → Interactive configuration wizard
2. `cd myapp` → Navigate to your project directory
3. `quickscale apply` → Generates production-ready Django project
4. Add your custom Django apps and features
5. Build your unique client application
6. Deploy to Railway with `quickscale deploy railway` (or use standard Django deployment)

`quickscale.yml` now uses explicit identity fields:
- `project.slug`: filesystem/service slug (for directory names)
- `project.package`: Python package/import name (for Django module paths)

ℹ️ The [implementation surface matrix](./docs/technical/decisions.md#mvp-feature-matrix-authoritative) is the single source of truth for what QuickScale currently owns.

### What You Get

Running `quickscale plan myapp`, entering the generated directory, and then running `quickscale apply` generates a **production-ready Django project** with:

- ✅ **React + shadcn/ui** frontend (TypeScript, Vite, Tailwind CSS) — **NEW in v0.74.0**
- ✅ **Docker** setup (development + production)
- ✅ **PostgreSQL** configuration
- ✅ **Environment-based** settings (dev/prod split)
- ✅ **Security** best practices (SECRET_KEY, ALLOWED_HOSTS, etc.)
- ✅ **Testing** infrastructure (pytest + factory_boy)
- ✅ **CI/CD** pipeline (GitHub Actions)
- ✅ **Code quality** hooks (ruff format + ruff check)
- ✅ **Advanced quality analysis** (dead code detection, complexity metrics, duplication)
- ✅ **Poetry** for dependency management
- ✅ **One-Command Deployment**: Deploy to Railway with `quickscale deploy railway` - fully automated setup

**Alternative**: Use `quickscale plan myapp --theme showcase_html` for pure HTML/CSS (simpler projects).

**See the complete project structure:** [scaffolding.md - Generated Project Output](./docs/technical/scaffolding.md#5-generated-project-output)

The generated project is **yours to own and modify** - no vendor lock-in, just Django best practices.

## Why QuickScale vs. Alternatives?

✅ **Faster than Cookiecutter** - One command vs. 30+ interactive prompts
✅ **More flexible than SaaS Pegasus** - Open source with full code ownership ($0 vs. $349+)
✅ **Simpler than building from scratch** - Production-ready in 5 minutes vs. days of setup
✅ **Railway deployment automation** - Competitors require manual platform configuration

**QuickScale is a development accelerator**, not a complete solution. You start with production-ready foundations and build your unique client application on top.

See [competitive_analysis.md](./docs/overview/competitive_analysis.md) for detailed comparison with SaaS Pegasus and Cookiecutter.

---

## Installation

QuickScale can be installed in two ways:

### Method 1: Install from PyPI (Recommended)

**Quick install:**
```bash
pip install quickscale
```

**Or with Poetry:**
```bash
poetry add quickscale
```

**Then use directly:**
```bash
quickscale plan myapp
cd myapp
quickscale apply
```

### Method 2: Install from Source

**For those who prefer building from source:**
```bash
git clone https://github.com/Experto-AI/quickscale.git
cd quickscale
./scripts/install_global.sh
```

**Then use directly:**
```bash
quickscale plan myapp
cd myapp
quickscale apply
```

**Both methods use the same command syntax:** `quickscale plan`, `quickscale apply`, etc.

---

### For Contributors

If you want to contribute to QuickScale development, see the [Development Guide](./docs/technical/development.md) for setup instructions.

---

## 🚀 5-Minute Quickstart

**Want to see QuickScale in action right now?** Here's the fastest path to a working Django SaaS:

```bash
# 1. Install QuickScale
./scripts/install_global.sh

# 2. Create your project configuration
quickscale plan myapp
# → Accept defaults: theme (showcase_react), no modules, Docker enabled

# 3. Generate and enter the project
cd myapp
quickscale apply
# → Docker services auto-start! (default: docker.start=true)

# 4. Setup and verify
quickscale manage migrate
quickscale manage createsuperuser
quickscale ps  # Check services are running

# 5. Open http://localhost:8000
```

**That's it!** 🎉 You now have a production-ready Django SaaS running with Docker + PostgreSQL.

**Note**: Services started automatically during `quickscale apply`. No need to run `quickscale up` manually!

**Prefer native Python?** After step 3, run:
```bash
poetry install
poetry run python manage.py migrate
poetry run python manage.py runserver
# Open http://localhost:8000
```

---

## Understanding Docker Auto-Start

**When does `quickscale apply` start Docker automatically?**

✅ **Services auto-start** (no `quickscale up` needed):
- First-time project generation
- When `docker.start: true` in quickscale.yml (**default**)
- When `--no-docker` flag is NOT used

❌ **Manual start required** (`quickscale up` needed):
- You set `docker.start: false` during `quickscale plan` wizard
- After stopping services with `quickscale down`
- When running `quickscale apply --no-docker`
- Adding modules to existing project (incremental apply)

**Example - No manual start needed:**
```bash
quickscale plan myapp  # Accept defaults (docker.start: true)
cd myapp
quickscale apply       # ← Docker services auto-start!

# Already running - just check status:
quickscale ps
curl http://localhost:8000  # ✅ Works immediately
```

**Example - Manual start needed:**
```bash
quickscale plan myapp
# During wizard, set: "Docker start? [Y/n]: n"
cd myapp
quickscale apply       # Services do NOT start

# Must start manually:
quickscale up
```

**Docker configuration options** in quickscale.yml:

```yaml
docker:
  start: true   # Auto-start services during apply?
  build: true   # Rebuild images? (slower but ensures latest)
  create_superuser: false  # Run interactive createsuperuser on first quickscale up?
```

- `start: true` + `build: true` → Full rebuild + start (slowest, most reliable)
- `start: true` + `build: false` → Start with cached images (faster)
- `start: false` → Manual control with `quickscale up`

**Need more details?** See [Docker Workflows Guide](./docs/technical/docker_workflows.md) for comprehensive scenarios and troubleshooting.

---

## Full Documentation & Setup

```bash
# Install QuickScale globally
./scripts/install_global.sh

# Create a configuration interactively
quickscale plan myapp
# → Select theme, modules, Docker options
# → Generates quickscale.yml in myapp/ directory

# Navigate to project and execute the configuration
cd myapp
quickscale apply
```

**Choose your development workflow:**

### Option 1: Docker (Recommended for production parity)

```bash
# Start all services (backend + database)
quickscale up

# Migrations run automatically on quickscale up (safe to run repeatedly)
# Optional manual run:
quickscale manage migrate

# Create superuser
quickscale manage createsuperuser

# View logs
quickscale logs -f backend

# Open a shell in the container
quickscale shell

# Stop services
quickscale down
```

**Visit http://localhost:8000** - Your app is running in Docker with PostgreSQL!

### Option 2: Native Poetry (Simpler for quick testing)

```bash
# Install dependencies
poetry install

# Run migrations
poetry run python manage.py migrate

# Start development server
poetry run python manage.py runserver
```

**Visit http://localhost:8000** - Your app is running natively!

**For complete command reference and workflows**, see the [user_manual.md](./docs/technical/user_manual.md).

## Code Quality Analysis

QuickScale includes comprehensive code quality checks:

```bash
# Run quality analysis
./scripts/check_quality.sh

# View reports
cat .quickscale/quality_report.md     # Human-readable
cat .quickscale/quality_report.json   # Machine-readable
```

**Detects:**
- Dead code (unused imports, functions, variables)
- High complexity (cyclomatic complexity >10)
- Large files (>500 lines warning, >1000 error)
- Code duplication (>6 similar lines)

**Exit codes:** 0 (clean), 1 (warnings), 2 (critical)

## Learn More

- **[decisions.md](./docs/technical/decisions.md)** - Technical specifications and implementation rules
- **[quickscale.md](./docs/overview/quickscale.md)** - Strategic vision and competitive positioning
- **[competitive_analysis.md](./docs/overview/competitive_analysis.md)** - Comparison vs SaaS Pegasus and alternatives
- **[roadmap.md](./docs/technical/roadmap.md)** - Development roadmap and implementation plan
- **[user_manual.md](./docs/technical/user_manual.md)** - Commands and workflows
- **[contributing.md](./docs/contrib/contributing.md)** - Development workflow and coding standards
