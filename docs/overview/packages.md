# Roadmap for implementation and PyPI packages (QuickScale)

Note: this document is placed under `docs/overview/` because it is a product
and roadmap decision (package naming, implementation and publication strategy). Technical publishing steps live in the `technical/` docs and are cross-referenced when needed.

---

## QuickScale — Package names to reserve on PyPI

This document is a roadmap for implementing and publishing QuickScale Python
packages (modules and themes) on PyPI. The list is prioritized to guide
implementation order and initial publication (placeholders) so the team can
deliver value and reserve package names during launch.

Guidelines
 - Publish placeholder packages under your organization account to "reserve"
   names. Do not delete placeholders unless you intend to free the name.
 - Use small initial versions (e.g. `0.0.1`) and include a README explaining
   that the package is reserved.

Priority matrix (short list first)

P0 — Table-stakes (publish these first)
 - `quickscale-core` — core library, reusable APIs and templates
 - `quickscale-cli` — command-line interface, provides `quickscale` console script
 - `quickscale` — tiny meta-package (depends on core + cli) for single-install UX

P1 — High priority modules (competitive parity)
 - `quickscale-module-auth` — django-allauth integration, custom user model
 - `quickscale-stripe` — Stripe-specific billing helpers (alias to billing)
 - `quickscale-module-billing` — dj-stripe wiring, subscriptions, invoices
 - `quickscale-module-teams` — teams, invitations, role-based access
 - `quickscale-module-blog` — custom Django blog (Post, Category, Tag, Markdown)
 - `quickscale-module-listings` — generic listings (real estate, jobs, events, products)
 - `quickscale-module-notifications` — email/notification infrastructure (anymail)
 - `quickscale-module-async` — Celery + Redis task patterns and beat
 - `quickscale-module-admin` — admin dashboards, audit logging, enhanced views
 - `quickscale-module-testing` — pytest fixtures, factory_boy snippets

P2 — Differentiation & themes (polish and verticals)
 - `quickscale-module-ai` — AI service framework, BaseService, credits integration
 - `quickscale-theme-showcase-html` — Pure HTML/CSS (renamed from starter_html)
 - `quickscale-theme-showcase-htmx` — HTMX + Alpine.js (renamed from starter_htmx)
 - `quickscale-theme-showcase-react` — React SPA (renamed from starter_react)
 - `quickscale-theme-tailwind` — Tailwind CSS theme (UI primitives)
 - `quickscale-theme-bulma` — Bulma CSS theme (existing styling option)

P3 — Integrations & tooling (lower priority / optional)
 - `quickscale-module-analytics` — Sentry, usage dashboards, basic analytics
 - `quickscale-module-payments` — payment helpers (non-Stripe or common helpers)
 - `quickscale-module-sendgrid` — SendGrid email integration helper
 - `quickscale-module-sentry` — Sentry scaffolding and integration examples
 - `quickscale-marketplace` — marketplace plumbing / licensing hooks

Suggested short-term reservation list
 (first wave to implement and publish placeholders under your org)
 - quickscale-core
 - quickscale-cli
 - quickscale
 - quickscale-module-auth
 - quickscale-stripe
 - quickscale-module-billing
 - quickscale-module-teams
 - quickscale-theme-htmx
 - quickscale-theme-react

How to publish a placeholder quickly (Poetry)
 1. Create a minimal project folder with `pyproject.toml`, `src/<pkg>/__init__.py`
 2. Build & publish:
    - `poetry build`
    - `poetry publish --build` (or configure `poetry config pypi-token.pypi <TOKEN>`)

Naming notes and conventions
 - Use `quickscale-` prefix for first-party modules and themes to make intent
   clear and to keep a tidy namespace on PyPI.
 - For modules use `quickscale-module-<name>`.
 - Theme packages should follow `quickscale-theme-<name>` so they are easily
   discoverable and grouped in PyPI search results.

## Recommended additions for vertical-first (Real‑Estate) workflows

For agencies or customers focused on real‑estate (inmobiliaria) features, implement and publish these additional first‑wave packages so you can quickly assemble a listings + blog site:

- `quickscale-module-listings` — Property/listing models, admin, publish workflow, images, filters and simple geo helpers
- `quickscale-module-blog` — Blog posts, categories, RSS, author pages, SEO helpers
- `quickscale-module-storage` — Storage adapters (local / S3), image resizing helpers, CDN hooks
- `quickscale-theme-realestate` — Real‑estate starter theme that stitches listings + blog + search UI
- `quickscale-module-search` — Postgres full‑text and basic geo radius helpers (important for listings)

Implement and publish these packages in the same first wave as the core packages if you're prioritizing a real‑estate customer.

## Competitor module / feature mapping

The table below maps common modules/features offered by major Django SaaS boilerplates referenced in `docs/overview/competitive_analysis.md`. Use this as a quick comparison when choosing names and priorities for QuickScale modules.

| Competitor | Key modules / features | Rough package/name equivalents (for comparison) |
|---|---|---|
| SaaS Pegasus | Auth (django-allauth), Billing (Stripe), Teams, Admin+CMS (Wagtail), Frontend variants (HTMX/React), Subscriptions | pegasus-auth, pegasus-billing, pegasus-teams, pegasus-wagtail, pegasus-htmx |
| Django Cookiecutter | Production-ready Django setup, Docker, CI, Testing, Custom User, Anymail | cookiecutter-core, cookiecutter-ci, cookiecutter-testing |
| Apptension SaaS Boilerplate | React+TS frontend, AWS deployment, Multi-tenant patterns, GraphQL API | apptension-frontend, apptension-aws, apptension-graphql |
| Ready SaaS | Django+React starter, Stripe, Templates, Docs | readysaas-core, readysaas-billing, readysaas-theme |
| Wagtail (CMS) | CMS, Page types, Marketplace ecosystem | wagtail-core, wagtail-pages, wagtail-packages |

Use the column "Rough package/name equivalents" as inspiration only — they are not official package names for those projects. The goal is to help you map QuickScale modules against the features competitors provide so you can choose names and priorities that are both discoverable and competitive.
