
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

🧭 **Evolution Snapshot**: QuickScale intentionally ships as a personal toolkit today and only grows into a community platform when real demand emerges. Catch the full story in the [evolution overview](./QUICKSCALE.md#evolution-strategy-personal-toolkit-first).

## Documentation map

```
Repository docs
├── README.md — Quick start guidance for newcomers (this file)
├── DECISIONS.md — Authoritative technical rules and MVP scope
├── ROADMAP.md — Execution timeline that follows DECISIONS.md
├── SCAFFOLDING.md — Directory and package layout standards
├── QUICKSCALE.md — Strategic vision and market positioning
└── COMMERCIAL.md — Post-MVP monetisation guidance
```

- Start with `README.md` for the big-picture overview, then dive into `DECISIONS.md` whenever you need the canonical rule or tie-breaker.
- Use `ROADMAP.md` only for planning work that implements decisions already captured in `DECISIONS.md`.
- Maintainers should cross-check the [document responsibilities section in `DECISIONS.md`](./DECISIONS.md#document-responsibilities-short) to keep this map aligned.

## SSOT (Single Source of Truth) Reference

This table shows which document to consult for authoritative decisions on common topics.

| Topic | Single Source | Notes |
|---|---|---|
| MVP Scope & Feature Matrix | `DECISIONS.md` | Canonical IN/OUT matrix for MVP
| Git Subtree Workflow | `DECISIONS.md#integration-note-personal-toolkit-git-subtree` | Full commands and guidance
| Directory Layouts / Scaffolding | `SCAFFOLDING.md` | Full tree diagrams and templates
| Strategic Rationale / Evolution | `QUICKSCALE.md` | Long-form narrative and market context
| Commercial Models & Licensing | `COMMERCIAL.md` | Post-MVP monetization guidance


### Primary Use Cases:
- **Solo Developer**: Build client projects faster with reusable components you maintain
- **Development Agency**: Standardize your tech stack across multiple client engagements  
- **Commercial Extension Developer**: Create and sell premium modules/themes
- **Open Source Contributor**: Extend the ecosystem with new modules and themes

### Development Flow (MVP)
1. `quickscale init myapp`
  - Generates the minimal Django starter described in the MVP Feature Matrix
  - Ships with standalone `settings.py` by default; there is NO automatic settings inheritance. Advanced users who manually embed `quickscale_core` via git subtree may opt-in to inherit from `quickscale_core.settings` (see [`DECISIONS.md`](./DECISIONS.md#mvp-feature-matrix-authoritative)).
  - **Optional**: Embed `quickscale_core` via git subtree after generation; follow the [Personal Toolkit workflow](./DECISIONS.md#integration-note-personal-toolkit-git-subtree) for canonical commands and helper roadmap
2. Add your custom Django apps and features
3. Adopt optional inheritance or module extraction patterns only when you embed the core; the rules and best practices stay centralized in `DECISIONS.md`
4. Build your unique client application
5. Deploy using standard Django deployment patterns

ℹ️ QuickScale's MVP centers on the personal toolkit workflow. Extraction patterns, module packaging, and subtree helper command plans stay documented in `DECISIONS.md` so this README can stay concise.

🔎 **Scope note**: The [MVP Feature Matrix](./DECISIONS.md#mvp-feature-matrix-authoritative) is the single source of truth for what's in or out.

 ### What MVP Generates
```bash
$ quickscale init myapp

myapp/
├── manage.py                    # Standard Django
├── myapp/
│   ├── __init__.py
│   ├── settings.py             # Standalone by default (no quickscale_core imports)
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── templates/
│   └── index.html              # Simple homepage
├── static/
│   └── css/
├── requirements.txt            # Django + essentials only (pyproject.toml is user-added, not generated)
└── README.md

# quickscale/ (embeddable via manual subtree)
# Commands live in DECISIONS.md; CLI helpers sit in the Post-MVP backlog.
└── quickscale/
    └── quickscale_core/
```

 **Key Point**: The generated project is **yours to own and modify**. QuickScale just gives you a good starting point. For any tie-breakers about what belongs in the MVP vs Post-MVP, see `DECISIONS.md` (authoritative).

## Key Benefits

- **Shared Updates**: Get security fixes and improvements automatically
- **Proven Foundations**: Built on battle-tested Django packages (django-allauth, dj-stripe)
- **Starting Points**: Themes provide foundations you customize for your business
- **Flexible Frontends**: Same backend, multiple client presentations
- **Simple Deployment**: Standard Django deployment patterns

## QuickScale Philosophy: Enabler, Not Complete Solutions

QuickScale provides the foundation and building blocks, not complete vertical solutions:

✅ **What QuickScale IS:**
- Foundation for building custom SaaS applications
- Modules built on proven Django foundations (dj-stripe, django-allauth, etc.)
- Starting point themes you must extend (models, business logic, UX)
- Development accelerator, not an end product

❌ **What QuickScale is NOT:**
- Complete e-commerce / CRM / real estate platform
- Ready-to-use vertical SaaS
- One-size-fits-all template pack
- Runtime plugin loader (no WordPress-style activation)

## From Template to Client Project

Start with the generated Django starter, build what your client needs, and only later decide if a pattern is worth extracting into `quickscale_modules/`. Distribution upgrades (PyPI, subscriptions, etc.) stay Post-MVP—follow the [MVP Feature Matrix](./DECISIONS.md#mvp-feature-matrix-authoritative) and [`QUICKSCALE.md`](./QUICKSCALE.md#evolution-strategy-personal-toolkit-first) for the bigger story.

---

 ### Development Approach (MVP)

QuickScale currently ships a single CLI entry point: `quickscale init`. The [CLI command matrix](./DECISIONS.md#cli-command-matrix) tracks the **planned** additions and their phases, keeping this README focused on commands that already exist.

### **Post-MVP: Configuration-Driven (Optional)**
Declarative configuration is a Post-MVP consideration. Prototype commands, sample schemas, and status notes now live exclusively in `DECISIONS.md`.

### Settings Pattern (Post-MVP)

Generated projects use standalone `settings.py` files by default. Optional inheritance and future settings plans are recorded in `DECISIONS.md` alongside the authoritative MVP feature matrix.

---

## CLI Reference (MVP)

### **QuickScale CLI - Simple and Minimal**

#### **Project Creation**

```bash
quickscale init <project_name>
```

**That's it.** No flags, no options, no complexity.

**What It Does:**
1. Creates Django project structure
2. Generates minimal starter application  
3. Optionally embeds `quickscale_core` utilities via git subtree
4. Ready to code in 30 seconds

**Example:**
```bash
quickscale init myapp
cd myapp
python manage.py runserver
# Visit http://localhost:8000 - see your minimal starter!
```

#### **Update Commands (Post-MVP Backlog)**

ℹ️ Wrapper helpers are deferred to the Post-MVP backlog. Track any future work in the [CLI command matrix](./DECISIONS.md#cli-command-matrix); until they ship, rely on the manual commands documented in [`DECISIONS.md`](./DECISIONS.md#integration-note-personal-toolkit-git-subtree).

## Glossary

Canonical terminology used across QuickScale documentation:

- MVP = Phase 1 (minimal personal toolkit)
- Post-MVP = Phase 2+ (features planned after MVP; prefer explicit phase numbers)
- Module = Backend module (Django app under `quickscale_modules`)
- Theme = Starting point Django app under `quickscale_themes`
- Generated Project = Output of `quickscale init`

Add new terms here as documentation evolves; this section consolidates terminology so other docs can link here as the canonical source.

## Learn More

- **[DECISIONS.md](./DECISIONS.md)** - Technical specifications and implementation rules
- **[QUICKSCALE.md](./QUICKSCALE.md)** - Strategic vision and competitive positioning
- **[ROADMAP.md](./ROADMAP.md)** - Development roadmap and implementation plan

For optional backend customization patterns, reference the [backend extensions policy](./DECISIONS.md#backend-extensions-policy).

