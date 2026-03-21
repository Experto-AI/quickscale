# 🚀 Start Here - QuickScale Documentation Guide

**Quick Mental Model**: QuickScale is a Django project generator that creates production-ready SaaS applications in minutes. It generates standalone projects you own completely, with optional reusable modules for common features (auth, billing, teams, etc.). Think "create-react-app" but for Django SaaS applications.

---

## What is QuickScale? (30-Second Summary)

QuickScale = **Django Generator** + **Reusable Modules** + **Production Foundations**

**Input**: `quickscale plan myapp` (interactive config) → `quickscale apply`
**Output**: Complete Django project with Docker, PostgreSQL, testing, CI/CD, and security best practices
**Future**: Reusable modules installable via git subtree (MVP) and PyPI (Post-MVP)

**Current Status**: v0.76.0 - MVP Phase (production-focused personal toolkit)
**Target Audience**: Solo developers and development agencies building client projects

---

## Key Concepts (Quick Reference)

For complete definitions, see **[GLOSSARY.md](./GLOSSARY.md)**. Here are the essentials:

| Term | Quick Definition | Learn More |
|------|------------------|------------|
| **Generated Project** | The standalone Django app created by `quickscale plan + apply` | [GLOSSARY.md](./GLOSSARY.md#generated-project) |
| **MVP** | Phase 1 (v0.56-v0.77.0) - Personal toolkit for client projects | [GLOSSARY.md](./GLOSSARY.md#mvp-minimum-viable-product) |
| **Post-MVP** | Phase 2+ (v0.78+) - Community platform with marketplace | [GLOSSARY.md](./GLOSSARY.md#post-mvp) |
| **Module** | Reusable Django app (auth, billing, blog) | [GLOSSARY.md](./GLOSSARY.md#module) |
| **Theme** | Frontend scaffolding (React default, HTML/HTMX alternatives) | [GLOSSARY.md](./GLOSSARY.md#theme) |
| **Git Subtree** | Distribution mechanism for sharing code | [GLOSSARY.md](./GLOSSARY.md#git-subtree) |
| **Plan/Apply** | Terraform-style declarative workflow | [GLOSSARY.md](./GLOSSARY.md#planapply-workflow) |

---

## Where Should I Start? (Decision Tree)

```
┌─────────────────────────────────────────────────────────────┐
│          What do you want to do with QuickScale?            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
      ┌───────────────────────┴───────────────────────┐
      │                                               │
      ▼                                               ▼
  [NEW USER]                                  [EXISTING USER]
      │                                               │
      ▼                                               ▼
┌─────────────────────┐                    ┌──────────────────────┐
│ Evaluate QuickScale │                    │  What's your goal?   │
│ for my needs        │                    └──────────────────────┘
└─────────────────────┘                               │
      │                                               ▼
      ▼                                    ┌──────────┴─────────┐
 READ (5-10 min):                          │                    │
 ├─ README.md                              ▼                    ▼
 ├─ docs/overview/                    [ADD FEATURE]      [DEPLOY PROJECT]
 │  quickscale.md                          │                    │
 └─ docs/overview/                         ▼                    ▼
    competitive_analysis.md           READ (30 min):      READ (25 min):
      │                               ├─ roadmap.md       ├─ deployment/
      ▼                               ├─ contrib/            railway.md
 THEN DECIDE:                         │  contributing.md  └─ development.md
 ├─ Build a project → ─────┐          └─ contrib/code.md       │
 └─ Learn more → [continue]│               │                   ▼
                           │               ▼              THEN ACT:
      ┌────────────────────┘           THEN ACT:          └─ Deploy!
      │                                └─ Implement!
      ▼
┌──────────────────────┐
│ Build Quick Project  │
└──────────────────────┘
      │
      ▼
 READ (15 min):
 ├─ README.md
 │  (Quick Start)
 ├─ user_manual.md
 └─ development.md
      │
      ▼
 THEN ACT:
 ├─ quickscale plan myapp
 ├─ cd myapp
 ├─ quickscale apply
 └─ quickscale up


┌────────────────────────────────────────────────────────────┐
│              OR: Browse by Role/Interest                   │
└────────────────────────────────────────────────────────────┘

[ARCHITECT/TECHNICAL LEAD]
├─ Understand Architecture
│  ├─ READ: decisions.md (authoritative rules)
│  ├─ READ: scaffolding.md (directory structure)
│  └─ READ: plan-apply-system.md (workflow)
└─ Total Time: 60-90 minutes

[DEVELOPER/CONTRIBUTOR]
├─ Contributing to QuickScale
│  ├─ READ: contrib/contributing.md (workflow overview)
│  ├─ READ: contrib/code.md (implementation guide)
│  ├─ READ: contrib/testing.md (test standards)
│  └─ READ: development.md (dev setup)
└─ Total Time: 90-120 minutes

[EVALUATOR/STAKEHOLDER]
├─ Strategic Context
│  ├─ READ: overview/quickscale.md (vision & strategy)
│  ├─ READ: overview/competitive_analysis.md (vs alternatives)
│  └─ READ: overview/commercial.md (business model)
└─ Total Time: 60 minutes

[MODULE DEVELOPER]
├─ Building Modules
│  ├─ READ: quickscale_modules/auth/README.md (example)
│  ├─ READ: decisions.md (module architecture)
│  └─ READ: scaffolding.md (structure requirements)
└─ Total Time: 45 minutes
```

---

## Documentation Hierarchy (Tiers)

QuickScale documentation is organized in **3 tiers** based on usage frequency:

### **Tier 1: Foundation** (Read First, Reference Often)

These 4 documents form the core knowledge base:

| Document | Purpose | Length | Authority |
|----------|---------|--------|-----------|
| **[README.md](./README.md)** | Project overview, quick start | 200 lines | User intro |
| **[GLOSSARY.md](./GLOSSARY.md)** | Terminology reference | 200 lines | Terminology |
| **[decisions.md](./docs/technical/decisions.md)** | Technical rules (SSOT) | 1,150 lines | **Authoritative** |
| **[scaffolding.md](./docs/technical/scaffolding.md)** | Directory structures | 1,000 lines | Structure |

**When to use**:
- README.md: First visit, quick reference
- GLOSSARY.md: Any time you see unfamiliar terms
- decisions.md: Before implementing features, resolving conflicts
- scaffolding.md: When creating files or understanding layouts

---

### **Tier 2: Task-Specific** (Read as Needed)

#### **Package Reference Docs** (Informational Context Only)

Use these when you need package-local packaging or responsibility summaries:

| Document | Purpose |
|----------|---------|
| **[quickscale/README.md](./quickscale/README.md)** | Meta-package install and dependency bundle summary |
| **[quickscale_cli/README.md](./quickscale_cli/README.md)** | CLI package scope, entrypoints, and command groups |
| **[quickscale_core/README.md](./quickscale_core/README.md)** | Core scaffolding package contents and template ownership |

**Rule**: These package README files are informational only. If wording differs, **[decisions.md](./docs/technical/decisions.md)** and **[README.md](./README.md)** remain authoritative.

Reference these when performing specific tasks:

| Document | Use When... | Length |
|----------|-------------|--------|
| **[roadmap.md](./docs/technical/roadmap.md)** | Planning features, checking timeline | 550 lines |
| **[user_manual.md](./docs/technical/user_manual.md)** | Running commands, workflows | 660 lines |
| **[development.md](./docs/technical/development.md)** | Setting up dev environment | 520 lines |
| **[contrib/contributing.md](./docs/contrib/contributing.md)** | Contributing to QuickScale | 200 lines |
| **[plan-apply-system.md](./docs/technical/plan-apply-system.md)** | Using plan/apply workflow | 240 lines |
| **[deployment/railway.md](./docs/deployment/railway.md)** | Deploying to Railway | 790 lines |

---

### **Tier 3: Deep Dives** (Reference Only)

Detailed guides for specific stages:

**Contributor Workflow**:
- [contrib/plan.md](./docs/contrib/plan.md) - Planning stage
- [contrib/code.md](./docs/contrib/code.md) - Implementation stage
- [contrib/review.md](./docs/contrib/review.md) - Review stage
- [contrib/testing.md](./docs/contrib/testing.md) - Testing stage
- [contrib/debug.md](./docs/contrib/debug.md) - Debugging stage

**Shared Principles**:
- [contrib/shared/code_principles.md](./docs/contrib/shared/code_principles.md) - SOLID, DRY, KISS
- [contrib/shared/architecture_guidelines.md](./docs/contrib/shared/architecture_guidelines.md) - Tech stack, boundaries
- [contrib/shared/testing_standards.md](./docs/contrib/shared/testing_standards.md) - Testing patterns
- [contrib/shared/task_focus_guidelines.md](./docs/contrib/shared/task_focus_guidelines.md) - Scope discipline

**Strategic Context**:
- [overview/quickscale.md](./docs/overview/quickscale.md) - Vision & strategy
- [overview/competitive_analysis.md](./docs/overview/competitive_analysis.md) - vs Alternatives
- [overview/commercial.md](./docs/overview/commercial.md) - Business model
- [overview/packages.md](./docs/overview/packages.md) - PyPI naming

**Release History**: [release-archive.md](./docs/technical/release-archive.md) (v0.52-v0.72)

---

## Quick Answers to Common Questions

### "Is QuickScale production-ready?"
**Phase 1 (MVP)** is the current production-focused track. Current repository version: v0.76.0. Check the roadmap for the active release scope and remaining milestones.
See: [roadmap.md](./docs/technical/roadmap.md)

### "Can I use it for my client projects?"
**Yes!** That's the primary MVP use case. QuickScale generates standalone Django projects you own completely - no vendor lock-in.
See: [README.md - Primary Use Cases](./README.md#primary-use-cases-mvp)

### "What's the difference between MVP and Post-MVP?"
- **MVP (v0.56-v0.77)**: Personal toolkit, git subtree distribution, React + shadcn/ui default
- **Post-MVP (v0.78+)**: Additional themes, PyPI distribution, marketplace

See: [GLOSSARY.md - MVP](./GLOSSARY.md#mvp-minimum-viable-product) | [GLOSSARY.md - Post-MVP](./GLOSSARY.md#post-mvp)

### "How do I deploy a generated project?"
**Railway** (recommended): One-command deployment via `quickscale deploy railway`
See: [deployment/railway.md](./docs/deployment/railway.md)

### "Where are the release notes?"
Historical releases (v0.52-v0.72): [release-archive.md](./docs/technical/release-archive.md)
Current timeline: [roadmap.md](./docs/technical/roadmap.md)

### "What modules are available?"
Current first-party module directories include **auth, billing, blog, crm, forms, listings, storage, and teams**.
See: [quickscale_modules/](./quickscale_modules/) for the current package list and per-module README files.

### "Can I contribute?"
**Yes!** Start with: [contrib/contributing.md](./docs/contrib/contributing.md)
Workflow: PLAN → CODE → REVIEW → TEST → DEBUG

### "Which Python/Django version?"
- **Python**: 3.14+ required
- **Django**: 6.0+
- **Poetry**: 2.0+ (package manager)

See: [development.md - Prerequisites](./docs/technical/development.md#prerequisites)

---

## Document Relationships (Visual Guide)

```
                    START_HERE.md (you are here)
                              │
            ┌─────────────────┼─────────────┐
            │                 │             │
            ▼                 ▼             ▼
        [Foundation]   [Task-Specific] [Deep Dives]
            │                 │             │
  ┌─────────┴─────┐           │             │
  ▼               ▼           ▼             ▼
decisions.md scaffolding.md roadmap.md   contrib/*
  │               │           │             │
  └───────┬───────┘           │             │
          ▼                   ▼             ▼
       GLOSSARY.md    user_manual.md  testing.md
       (terms)        (commands)      (patterns)
```

**Golden Rule**: If documents conflict, **[decisions.md](./docs/technical/decisions.md)** is authoritative.

---

## Suggested Reading Paths

### **Path 1: New User (20 minutes)**
1. README.md (5 min) - Overview
2. user_manual.md (10 min) - Commands
3. development.md (5 min) - Setup
→ **Result**: Can build first project

### **Path 2: Contributor (90 minutes)**
1. contrib/contributing.md (10 min) - Workflow
2. decisions.md (30 min) - Rules
3. contrib/code.md (20 min) - Implementation
4. contrib/testing.md (20 min) - Testing
5. development.md (10 min) - Environment
→ **Result**: Can contribute features

### **Path 3: Architect (120 minutes)**
1. decisions.md (45 min) - Technical decisions
2. scaffolding.md (30 min) - Structure
3. plan-apply-system.md (20 min) - Workflow
4. overview/quickscale.md (25 min) - Strategy
→ **Result**: Complete architectural understanding

### **Path 4: Module Developer (60 minutes)**
1. quickscale_modules/auth/README.md (15 min) - Example
2. decisions.md § Module Architecture (20 min)
3. scaffolding.md § Module Structure (15 min)
4. contrib/code.md (10 min) - Coding standards
→ **Result**: Can build custom modules

---

## Still Lost?

**If you're looking for**:
- ❓ **Term definitions** → [GLOSSARY.md](./GLOSSARY.md)
- 📖 **Technical rules** → [decisions.md](./docs/technical/decisions.md)
- 🏗️ **Directory layouts** → [scaffolding.md](./docs/technical/scaffolding.md)
- ⚡ **Quick commands** → [user_manual.md](./docs/technical/user_manual.md)
- 🗺️ **Roadmap/timeline** → [roadmap.md](./docs/technical/roadmap.md)
- 🚀 **Deployment** → [deployment/railway.md](./docs/deployment/railway.md)
- 🐛 **Debugging help** → [contrib/debug.md](./docs/contrib/debug.md)
- 💡 **Why QuickScale?** → [overview/quickscale.md](./docs/overview/quickscale.md)
- 🆚 **vs Alternatives** → [overview/competitive_analysis.md](./docs/overview/competitive_analysis.md)

---

## Documentation Principles

1. **[decisions.md](./docs/technical/decisions.md) is authoritative** - Always wins conflicts
2. **[GLOSSARY.md](./GLOSSARY.md) defines terms** - Use it consistently
3. **Update Tier 1 first** - Then propagate to other docs
4. **No broken links** - Validate before committing
5. **Concise is better** - Link to deep dives instead of duplicating

---

**Last Updated**: 2026-03-21
**QuickScale Version**: v0.76.0
**Feedback**: Open an issue if this guide needs improvement!
