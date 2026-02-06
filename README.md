# 🚀 QuickScale

[![PyPI version](https://img.shields.io/pypi/v/quickscale.svg)](https://pypi.org/project/quickscale/)
[![CI](https://github.com/Experto-AI/quickscale/actions/workflows/ci.yml/badge.svg)](https://github.com/Experto-AI/quickscale/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-90%25-green.svg)](https://github.com/Experto-AI/quickscale/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Version](https://img.shields.io/badge/version-0.74.0-green.svg)](https://github.com/Experto-AI/quickscale/releases)
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

QuickScale is a **composable Django framework** for building client SaaS applications. Start with a stable core, add reusable modules, customize themes, and deploy faster—while maintaining the flexibility to create commercial extensions and build a community ecosystem.

---

## What is QuickScale?

QuickScale is a **Django project generator** that creates production-ready SaaS applications with one command. Designed for **solo developers and development agencies**, it gives you:

- **Production-ready foundations**: Docker, PostgreSQL, testing, CI/CD, and security out-of-the-box
- **One-command deployment**: Deploy to Railway with `quickscale deploy railway`
- **Full ownership**: Generated projects are 100% yours to customize—no vendor lock-in
- **Standardized stack**: Build multiple client projects faster with consistent best practices

🧭 **Future Vision**: QuickScale will evolve to support reusable modules and themes. Today it's a personal toolkit; tomorrow it becomes a community platform when demand emerges. [Read the full evolution strategy](./docs/overview/quickscale.md#evolution-strategy-personal-toolkit-first).

## Documentation Guide

**Start here for your needs:**
- 📖 **New user?** You're in the right place. This README shows you what QuickScale is and how to get started.
- 🔧 **Need commands?** See [user_manual.md](./docs/technical/user_manual.md) for all commands and workflows
- 🚀 **Deploying to Railway?** See [railway.md](./docs/deployment/railway.md) for Railway deployment guide
- 📋 **Planning a feature?** Check [decisions.md](./docs/technical/decisions.md) for the authoritative MVP scope and technical rules
- 🗓️ **Timeline & tasks?** See [roadmap.md](./docs/technical/roadmap.md)
- 🏗️ **Project structure?** See [scaffolding.md](./docs/technical/scaffolding.md) for complete directory layouts
- 🎯 **Why QuickScale?** See [quickscale.md](./docs/overview/quickscale.md) for competitive positioning

**Quick Reference:**
- **MVP** = Phase 1 (Personal Toolkit)
- **Post-MVP** = Phase 2+ (Modules & Themes)
- **Generated Project** = Output of `quickscale plan` + `quickscale apply`

See [decisions.md - Glossary section](./docs/technical/decisions.md#document-responsibilities-short) for complete terminology and Single Source of Truth reference


### Primary Use Cases (MVP):
- **Solo Developer**: Build client projects faster with production-ready foundations
- **Development Agency**: Standardize your tech stack across client engagements

### Future Use Cases (Post-MVP):
- **Commercial Extension Developer**: Create and sell premium modules/themes
- **Open Source Contributor**: Extend the ecosystem with modules and themes

### Development Flow
1. `quickscale plan myapp` → Interactive configuration wizard
2. `cd myapp` → Navigate to your project directory
3. `quickscale apply` → Generates production-ready Django project
4. Add your custom Django apps and features
5. Build your unique client application
6. Deploy to Railway with `quickscale deploy railway` (or use standard Django deployment)

ℹ️ The [MVP Feature Matrix](./docs/technical/decisions.md#mvp-feature-matrix-authoritative) is the single source of truth for what's in or out.

### What You Get

Running `quickscale plan myapp && quickscale apply` generates a **production-ready Django project** with:

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
# → Accept defaults: theme (showcase_html), no modules, Docker enabled

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
# Start all services (web + database)
quickscale up

# Run migrations
quickscale manage migrate

# Create superuser
quickscale manage createsuperuser

# View logs
quickscale logs -f web

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
