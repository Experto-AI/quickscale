# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Timeline & Tasks)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## General Introduction

**Purpose:** This document tracks the active development timeline, versioned milestone scope, and archived pointers for recent QuickScale releases.

**Content Guidelines:**
- Organize work by versioned milestones with clear deliverables and success criteria
- Include specific implementation tasks with technical requirements
- Provide timeline estimates and dependency relationships
- Track progress and update status as work is completed
- Focus on "when" and "what tasks" rather than "why" or "what"
- Reference other documents for context but avoid duplicating their content

**What to Add Here:**
- New milestone planning and release-specific task tracking
- Specific implementation tasks and acceptance criteria
- Timeline updates and progress tracking
- Resource allocation and team assignments
- Risk mitigation strategies and contingency plans
- Testing strategies and quality gates

**What NOT to Add Here:**
- Strategic rationale or competitive analysis (belongs in quickscale.md)
- Technical specifications or architectural decisions (belongs in decisions.md)
- User documentation or getting started guides (belongs in README.md)
- Directory structures or scaffolding details (belongs in scaffolding.md)

## Broad Overview of the Roadmap

QuickScale's roadmap is milestone-led. It tracks shipped release pointers, the current implementation line, and the next versioned scopes already tied to concrete repository work. Older phase labels still appear in some historical notes, but they are not the active roadmap structure.

## Current Milestone Summary

This table is the single milestone summary for shipped history and the active forward roadmap.

| Version | Status | Milestone | Details |
|---------|--------|-----------|---------|
| v0.71.0 | ✅ Completed | Plan/Apply system | Terraform-style configuration system complete |
| v0.72.0 | ✅ Completed | Plan/Apply cleanup | Legacy commands removed after the Plan/Apply rollout |
| v0.73.0 | ✅ Released | CRM module | API-first Django CRM with 7 core models and CLI integration; archived in changelog |
| v0.74.0 | ✅ Completed | React default theme | React + shadcn/ui baseline shipped |
| v0.75.0 | ✅ Completed | Forms module | Generic form builder with DRF API, spam protection, and GDPR anonymization |
| v0.76.0 | ✅ Released | Storage module | Cloud file hosting plus CDN-ready media infrastructure; archived in release note and changelog |
| v0.77.0 | ✅ Internal baseline | Backups module | Private local and optional private remote workflows, guarded BackupPolicy-admin local restore, and CLI restore; changelog-only historical baseline |
| v0.78.0 | ✅ Released | Notifications module | Transactional email foundation with app-owned rendering, recipient-granular tracking, and Anymail-backed Resend delivery; archived in release note and changelog |
| v0.79.0 | ✅ Released | Social and Link Tree module | Curated social links and embeds, backend-owned preview metadata, and React public pages for fresh `showcase_react` generations; older projects adopt them manually |
| v0.80.0 | ✅ Released | Analytics module | PostHog website analytics with flat mutable settings, service-style backend hooks, and fresh `showcase_react` starter support; existing projects adopt frontend snippets manually |
| v0.81.0 | ✅ Released | Beta-site migration maintainer tooling | Maintainer-only fresh-first and checkpoint-first in-place beta-site migration workflows; archived in release note and changelog |
| v0.82.0 | ✅ Released | Disaster recovery & environment promotion | Public `quickscale dr` capture/plan/execute/report workflows with `snapshot_id` lookup, resumable capture/execute, rollback pins, conservative env-var sync, and source-side media sync; archived in release note and changelog |
| v0.83.0 | ✅ Released | Hardening release | Repo-wide hardening release published; archived in the release note and changelog |
| v0.84.0 | ✅ Released | Backups hardening release | Backup lifecycle hardening and runtime/tooling refresh archived in the release note and changelog |
| v0.85.0 | ✅ Released | Billing module | Stripe-backed one-time credit purchases and recurring subscriptions, credits-first Django ledger, planner/apply readiness, module-owned pricing and dashboard pages, and starter-theme billing links; archived in release note and changelog |
| v0.86.0 | ✅ Released | Organizations module | Multi-tenancy with Solo/SaaS runtime modes, org-scoped billing, billing wiring fix + wiring regression guard, and self-service onboarding; archived in release note and changelog |
| v0.87.0 | 📋 Planned | Hardening release | Cross-cutting theme correctness fixes: analytics visibility gap closed in showcase_react and showcase_html, and other theme-parity regressions |

**Legend:**
- ✅ = Completed, released, or internally baselined
- 🟡 = In progress in repo or release-prepared, but not yet tagged/published
- 📋 = Planned/Not Started

**Status:**
- **Current release:** v0.86.0 is the published release
- **Next planned milestone:** v0.87.0 Hardening release
- **Plan/Apply System:** v0.68.0-v0.71.0 - Terraform-style configuration ✅ Complete
- **SaaS Parity:** v0.86.0 ✅ Complete - auth, billing, organizations modules shipped on top of the notifications foundation

## Notes and References

**Target Audience:** Development team, project managers, stakeholders tracking progress

- **Completed Releases:** See [CHANGELOG.md](../../CHANGELOG.md)
- **Release doc layout:** [CHANGELOG.md](../../CHANGELOG.md) is the canonical history index; for each published release, `docs/releases/release-vX.XX.X.md` is the single official release note linked from the GitHub tag and release PR; the roadmap tracks active and unreleased release status until that note exists
- **Technical SSOT**: [decisions.md](./decisions.md)
- **Scaffolding SSOT**: [scaffolding.md](./scaffolding.md)
- **Strategic Vision**: [quickscale.md](../overview/quickscale.md)
- **Commercial Models**: [commercial.md](../overview/commercial.md)
- **Release Documentation Policy**: [Release Summary Template](./release_summary_template.md) for the single public release-note workflow

## ROADMAP
List of upcoming releases with detailed implementation tasks:

---

After release closeout, keep only a concise pointer in the roadmap. Put canonical history in [CHANGELOG.md](../../CHANGELOG.md), and for published releases add `docs/releases/release-vX.XX.X.md` as the single official release note linked from the GitHub tag and release PR. Keep unreleased closeout status in the roadmap until that release note exists.

---

### v0.86.0: Organizations Module

**Status**: ✅ Released — archived in [release note](../releases/release-v0.86.0.md) and [changelog](../../CHANGELOG.md)

**Design document**: [`docs/technical/organizations.md`](organizations.md)

---

### v0.87.0: Hardening Release

**Status**: 📋 Planned

**Scope**: Cross-cutting theme correctness fixes discovered after v0.86.0.

**showcase_react gaps (analytics)**
- [ ] Wire analytics into `window.__QUICKSCALE__.modules` in the main shell template (`main.tsx.j2`)
- [ ] Add analytics to the TypeScript module registry (`useModules` hook)
- [ ] Add Analytics dashboard card to `Dashboard.tsx.j2`

**showcase_html parity gaps**
- [x] Add Social module card to `showcase_html/templates/index.html.j2` dashboard
- [x] Add Orgs module card to `showcase_html/templates/index.html.j2` dashboard
- [x] Fix empty-state condition to include `quickscale_modules_social` and `quickscale_modules_orgs`
- [x] Add Social navigation section to `showcase_html/templates/components/navigation.html.j2`
- [x] Add Orgs navigation section to `showcase_html/templates/components/navigation.html.j2`
- [x] Create `showcase_html/templates/social/link_tree.html.j2` — server-rendered public link tree using `.qs-social-*` CSS classes
- [x] Create `showcase_html/templates/social/embeds.html.j2` — server-rendered public embeds gallery
- [x] Add `social_link_tree_view` and `social_embeds_view` to `generator/templates/project_name/views.py.j2` (showcase_html block)
- [x] Add `/social/` and `/social/embeds/` URL patterns to `generator/templates/project_name/urls.py.j2` (showcase_html block)

---
