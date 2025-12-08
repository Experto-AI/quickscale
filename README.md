# 🚀 QuickScale

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
2. `quickscale apply` → Generates production-ready Django project
3. Add your custom Django apps and features
4. Build your unique client application
5. Deploy to Railway with `quickscale deploy railway` (or use standard Django deployment)

ℹ️ The [MVP Feature Matrix](./docs/technical/decisions.md#mvp-feature-matrix-authoritative) is the single source of truth for what's in or out.

### What You Get

Running `quickscale plan myapp && quickscale apply` generates a **production-ready Django project** with:

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


## Quick Start

```bash
# Install QuickScale globally
./scripts/install_global.sh

# Create a configuration interactively
quickscale plan myapp
# → Select theme, modules, Docker options
# → Generates quickscale.yml

# Execute the configuration
quickscale apply
cd myapp
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
