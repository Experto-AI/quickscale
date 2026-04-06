# Changelog

`CHANGELOG.md` is the canonical QuickScale release history index. For published releases, pair each version entry with a single official release note in `docs/releases/` linked from the GitHub tag and release PR. Use `docs/technical/roadmap.md` for active or unreleased release status. Entries are version-ordered; listed dates reflect the recorded artifact date when available.

- v0.82.0 — 2026-04-06 — Disaster Recovery & Environment Promotion Workflows (public `quickscale dr capture/plan/execute/report` workflows for local and Railway routes with `snapshot_id`-based stored snapshots, resumable capture and execute, rollback pins for production routes, conservative env-var sync, and source-side media sync as a separate surface from database restore; Railway-target media sync requires storage-backed object storage rather than container disk)
- v0.81.0 — 2026-04-05 — Beta-Site Migration Maintainer Tooling (maintainer-only Make/Python workflows for beta-site catch-up: fresh-first executes deterministic recipient mutation plus local verification, while in-place stays checkpoint-first by default and continues through deterministic copy/apply/verification only with explicit opt-in; recipient-owned routing files, smoke checks, env vars, PR merge, deploy, and rollback remain manual)
- v0.80.0 — 2026-04-04 — Analytics Module (PostHog-only website analytics with flat `QUICKSCALE_ANALYTICS_*` settings, service-style capture helpers, apply-time env-example sync and operator guidance, guarded forms integration, QuickScale-owned social click tracking, dormant `showcase_react` starter support for fresh generations, and manual server-rendered template-tag support; existing projects adopt frontend snippets manually)
- v0.79.0 — 2026-04-03 — Social & Link Tree Module (curated social links and embeds, backend-owned YouTube/TikTok preview metadata, managed `/_quickscale/social/` integration endpoints, and Django-owned public React pages for fresh `showcase_react` generations; older projects adopt those pages manually)
- v0.78.0 — 2026-03-30 — Notifications Module (transactional email foundation, Anymail-backed Resend delivery, recipient-granular tracking, and signed delivery webhooks)
- v0.77.0 — internal main-branch baseline — Backups Module (private database backups, optional private remote offload, guarded CLI restore, and scheduler-ready command hooks; no tagged public release note was published for this internal baseline)
- v0.76.0 — 2026-03-21 — Storage Module (cloud file hosting, media storage adapters, CDN-ready media infrastructure)
- v0.75.0 — 2026-02-23 — Forms Module (generic customizable form builder with admin, DRF API, spam protection, GDPR anonymization, and React mount point)
- v0.74.0 — 2026-02-05 — React Default Theme (showcase_react theme with Vite, TypeScript, TanStack Query, and Zustand)
- v0.73.0 — 2026-02-04 — CRM Module (API-first Django CRM with 7 core models and CLI integration)
- v0.72.0 — 2025-12-07 — Plan/Apply Cleanup (removed legacy init/embed commands, full transition to plan/apply)
- v0.71.0 — 2025-06-25 — Module manifests & config mutability (Plan/Apply system complete)
- v0.70.0 — 2025-12-19 — Existing project support (status, plan --add, plan --reconfigure)
- v0.69.0 — 2025-12-03 — State management and incremental applies
- v0.68.0 — 2025-12-01 — Plan/Apply System core commands (Terraform-style declarative workflow)
- v0.67.0 — 2025-11-29 — Listings module with AbstractListing base model for verticals
- v0.66.0 — 2025-11-24 — Blog module with Markdown, featured images, and RSS feeds
- v0.65.0 — 2025-11-03 — Enhanced auth module and development tooling
- v0.64.0 — 2025-11-01 — Theme rename to showcase_* (breaking change)
- v0.63.0 — 2025-10-29 — Authentication Module with django-allauth and interactive embed
- v0.62.0 — 2025-10-25 — Split Branch Infrastructure (module management CLI commands, GitHub Actions automation)
- v0.61.0 — 2025-10-24 — Theme System Foundation (--theme CLI flag, theme abstraction layer, HTML theme)
- v0.60.0 — 2025-10-19 — Railway Deployment Support (automated deployment via quickscale deploy railway)
- v0.59.0 — 2025-10-18 — CLI Development Commands (Docker/Django operation wrappers)
- v0.58.0 — 2025-10-18 — Comprehensive E2E testing infrastructure with Playwright and PostgreSQL
- v0.57.0 — 2025-10-15 — Production-ready generator baseline
- v0.56.0 — 2025-10-13 — Quality, Testing & CI/CD
- v0.55.0 — 2025-10-13 — CLI implementation
- v0.54.0 — 2025-10-13 — Project Generator
- v0.53.3 — 2025-10-12 — Project Metadata & DevOps Templates
- v0.53.2 — 2025-01-11 — Templates and Static Files
- v0.53.1 — 2025-10-11 — Core Django Project Templates
- v0.52.0 — 2025-10-08 — Project Foundation
- v0.51.0 — 2025-10-08 — documentation foundation
- v0.41.0 and earlier — legacy codebase (see Github repository for history)
