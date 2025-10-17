# 🚀 QuickScale

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

QuickScale is a **composable Django framework** designed for **solo developers and development agencies** who build multiple client SaaS applications. It provides a stable foundation with reusable components, enabling you to:

- **Build once, reuse everywhere**: Create modules and themes that work across all your client projects
- **Maintain commercial flexibility**: Keep core components open source while offering premium modules/themes via subscriptions
- **Scale your development business**: Standardize your tech stack and accelerate client project delivery
- **Build a community ecosystem**: Share and monetize your extensions while benefiting from community contributions

🧭 **Evolution Snapshot**: QuickScale intentionally ships as a personal toolkit today and only grows into a community platform when real demand emerges. Catch the full story in the [evolution overview](./docs/overview/quickscale.md#evolution-strategy-personal-toolkit-first).

## Documentation Guide

**Start here for your needs:**
- 📖 **New user?** You're in the right place. This README shows you what QuickScale is and how to get started.
- 🔧 **Need commands?** See [user_manual.md](./docs/technical/user_manual.md) for all commands and workflows
- 📋 **Planning a feature?** Check [decisions.md](./docs/technical/decisions.md) for the authoritative MVP scope and technical rules
- 🗓️ **Timeline & tasks?** See [roadmap.md](./docs/technical/roadmap.md)
- 🏗️ **Project structure?** See [scaffolding.md](./docs/technical/scaffolding.md) for complete directory layouts
- 🎯 **Why QuickScale?** See [quickscale.md](./docs/overview/quickscale.md) for competitive positioning

**Quick Reference:**
- **MVP** = Phase 1 (Personal Toolkit)
- **Post-MVP** = Phase 2+ (Modules & Themes)
- **Generated Project** = Output of `quickscale init`

See [decisions.md - Glossary section](./docs/technical/decisions.md#document-responsibilities-short) for complete terminology and Single Source of Truth reference


### Primary Use Cases:
- **Solo Developer**: Build client projects faster with reusable components you maintain
- **Development Agency**: Standardize your tech stack across multiple client engagements  
- **Commercial Extension Developer**: Create and sell premium modules/themes
- **Open Source Contributor**: Extend the ecosystem with new modules and themes

### Development Flow (MVP)
1. `quickscale init myapp`
  - Generates the minimal Django starter described in the MVP Feature Matrix
  - Ships with standalone `settings.py` by default; there is NO automatic settings inheritance. Advanced users who manually embed `quickscale_core` via git subtree may opt-in to inherit from `quickscale_core.settings` (see [decisions.md](./docs/technical/decisions.md#mvp-feature-matrix-authoritative)).
  - **Optional**: Embed `quickscale_core` via git subtree after generation; follow the [Personal Toolkit workflow](./docs/technical/decisions.md#integration-note-personal-toolkit-git-subtree) for canonical commands and helper roadmap
2. Add your custom Django apps and features
3. Adopt optional inheritance or module extraction patterns only when you embed the core; the rules and best practices stay centralized in `DECISIONS.md`
4. Build your unique client application
5. Deploy using standard Django deployment patterns

ℹ️ QuickScale's MVP centers on the personal toolkit workflow. Extraction patterns, module packaging, and subtree helper command plans stay documented in `docs/technical/decisions.md` so this README can stay concise.

🔎 **Scope note**: The [MVP Feature Matrix](./docs/technical/decisions.md#mvp-feature-matrix-authoritative) is the single source of truth for what's in or out.

### What You Get

Running `quickscale init myapp` generates a **production-ready Django project** with:

- ✅ **Docker** setup (development + production)
- ✅ **PostgreSQL** configuration
- ✅ **Environment-based** settings (dev/prod split)
- ✅ **Security** best practices (SECRET_KEY, ALLOWED_HOSTS, etc.)
- ✅ **Testing** infrastructure (pytest + factory_boy)
- ✅ **CI/CD** pipeline (GitHub Actions)
- ✅ **Code quality** hooks (ruff format + ruff check)
- ✅ **Poetry** for dependency management

**See the complete project structure:** [scaffolding.md - Generated Project Output](./docs/technical/scaffolding.md#5-generated-project-output)

The generated project is **yours to own and modify** - no vendor lock-in, just Django best practices.

## Why QuickScale?

✅ **Production-ready from day one** - Docker, PostgreSQL, pytest, CI/CD, security best practices
✅ **Built on Django** - No magic, just excellent Django patterns and battle-tested packages
✅ **Shared improvements** - Security fixes and updates flow across all your projects via git subtree
✅ **Full ownership** - Generated projects are 100% yours, no vendor lock-in

**QuickScale is a development accelerator**, not a complete solution. You start with production-ready foundations and build your unique client application on top.

See [competitive_analysis.md](./docs/overview/competitive_analysis.md) for detailed comparison with SaaS Pegasus and Cookiecutter.

---


## Quick Start

```bash
# Install QuickScale globally
./scripts/install_global.sh

# Create your first project
quickscale init myapp

# Start developing
cd myapp
poetry install
poetry run python manage.py migrate
poetry run python manage.py runserver
```

**That's it!** Visit http://localhost:8000 to see your new Django project.

**For complete command reference and workflows**, see the [user_manual.md](./docs/technical/user_manual.md).

## Learn More

- **[decisions.md](./docs/technical/decisions.md)** - Technical specifications and implementation rules
- **[quickscale.md](./docs/overview/quickscale.md)** - Strategic vision and competitive positioning
- **[competitive_analysis.md](./docs/overview/competitive_analysis.md)** - Comparison vs SaaS Pegasus and alternatives
- **[roadmap.md](./docs/technical/roadmap.md)** - Development roadmap and implementation plan
- **[user_manual.md](./docs/technical/user_manual.md)** - Commands and workflows
- **[contributing.md](./docs/contrib/contributing.md)** - Development workflow and coding standards

