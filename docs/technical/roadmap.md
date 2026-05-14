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
| v0.85.0 | 📋 Planned | Billing module | Stripe integration after v0.84.0 backups hardening closes the remaining backup lifecycle gaps |
| v0.86.0 | 📋 Planned | Teams module | Multi-tenancy and team workflows as part of SaaS feature parity with auth, billing, teams, and notifications foundation |
| v0.87.0+ | 📋 Planned | HTML theme polish | Server-rendered secondary option maintenance after the hardening, billing, and teams milestones |

**Legend:**
- ✅ = Completed, released, or internally baselined
- 🟡 = In progress in repo but not yet tagged/released
- 📋 = Planned/Not Started

**Status:**
- **Current release:** v0.84.0 is the published release
- **Current in-repo milestone:** v0.85.0 billing module is the next planned roadmap milestone now that v0.84.0 is archived in the changelog and release note
- **Next planned milestone:** v0.86.0 teams module after the billing milestone
- **Plan/Apply System:** v0.68.0-v0.71.0 - Terraform-style configuration ✅ Complete
- **SaaS Parity:** v0.86.0 - auth, billing, teams modules complete on top of the notifications foundation

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

### v0.85.0: `quickscale_modules.billing` - Billing Module

**Status**: 📋 Planned

**Dependency note**: This milestone starts only after v0.84.0 closes the backup hardening work for admin download, full backup completeness, upload-driven restore, and the repo-wide stable runtime/tooling refresh.

**Library Decision**: Direct `stripe` Python SDK (not dj-stripe). dj-stripe mirrors ~50 Stripe tables into the Django ORM but provides none of the credits accounting logic, which is the core domain. The direct SDK gives full control with a minimal footprint, consistent with the notifications module's thin-adapter pattern (`django-anymail` over a full ORM-mirror). Credits, balances, and transactions are custom Django models; Stripe is purely the payment trigger.

**Credits System Design**: Credits are the central abstraction. Monthly plans top up a user's credit balance on each `invoice.paid` webhook. One-time purchases top up credits on `checkout.session.completed`. The credit ledger (`CreditBalance` + `CreditTransaction`) is owned entirely by Django models — Stripe is the payment trigger, not the source of truth for credit counts.

**Domain Models**:
- `Plan` — name, slug, stripe_price_id, credits_per_period, price_cents, billing_interval (monthly/yearly/one_time), is_active
- `CreditBalance` — user (1:1), balance (int), updated_at
- `CreditTransaction` — user (FK), amount, transaction_type (PLAN/PURCHASE/USAGE/REFUND/ADJUSTMENT), stripe refs, description, balance_after (snapshot), created_at
- `Subscription` — user (FK), plan (FK), stripe_subscription_id, stripe_customer_id, status, period dates
- `WebhookEvent` — stripe_event_id (unique), event_type, payload (JSONField), processed, processing_error, created_at

---

#### Phase 1: Foundation — Models, Admin, Module Config

**Estimated hours**: 8–10 h

**Delivers**: A fully migrated, admin-registered module with all five domain models. No Stripe dependency yet.

- [ ] `module.yml` — name, version, mutable settings for `stripe_*_env_var` pointers and `billing_currency`; `django_apps: [quickscale_modules_billing]`
- [ ] `pyproject.toml` — `stripe` NOT yet included; dev deps: `pytest-django`; `--cov-fail-under=90`; mypy `ignore_missing_imports` for `stripe.*`
- [ ] `apps.py` — `QuickscaleBillingConfig`, `label = "quickscale_modules_billing"`, `default_auto_field = BigAutoField`
- [ ] `models.py` — all five models with `select_for_update`-ready `CreditBalance.get_or_create_for_user()` class method
- [ ] `admin.py` — all five models registered; read-only admin for `CreditBalance`, `CreditTransaction`, `WebhookEvent`; full CRUD for `Plan`
- [ ] `migrations/0001_initial.py` — handwritten, includes `UniqueConstraint` on `WebhookEvent.stripe_event_id`
- [ ] `tests/settings.py`, `conftest.py`, `test_models.py`, `test_admin.py`

**Acceptance**: `pytest --cov-fail-under=90` passes; all five models visible in Django admin; no `stripe` import anywhere.

---

#### Phase 2: Stripe Infrastructure — Customer Management and Webhook Endpoint

**Estimated hours**: 10–12 h

**Delivers**: Working webhook endpoint with idempotency gate and a safe credit ledger core. All Stripe API calls are isolated in `services.py`.

- [ ] Add `stripe>=12.0.0,<13.0.0` to `pyproject.toml` and `module.yml`
- [ ] `services.py` — `BillingSettingsSnapshot.from_settings()` (mirrors `AnalyticsRuntimeSettingsSnapshot` pattern); `BillingError` exception hierarchy (`BillingConfigurationError`, `BillingWebhookError`, `BillingWebhookSignatureError`); `get_or_create_stripe_customer(user) -> str`; `credit_user(user, amount, type, description, stripe_refs) -> CreditTransaction` with `select_for_update()` inside `transaction.atomic()` and `F('balance') + amount` ORM update; `handle_stripe_event()` stub
- [ ] `views.py` — `StripeWebhookView` (`@csrf_exempt`): verifies Stripe signature, `get_or_create(stripe_event_id=...)` for idempotency, dispatches to `handle_stripe_event`, marks `processed=True` on success, returns 200 always (Stripe retries on non-2xx)
- [ ] `urls.py` — `POST billing/webhooks/stripe/`
- [ ] `tests/test_services.py` — `credit_user` atomicity (`@pytest.mark.django_db(transaction=True)`), `balance_after` integrity, `get_or_create_stripe_customer` (mock `stripe.customers.create`), all error paths
- [ ] `tests/test_views.py` — invalid signature → 403; duplicate event id → 200 idempotent; valid signature with unknown event type → row stored `processed=True`

**Acceptance**: Webhook endpoint rejects bad signatures; duplicate events are absorbed; `credit_user` is concurrency-safe; `pytest --cov-fail-under=90` passes.

---

#### Phase 3: One-Time Credit Purchases End-to-End

**Estimated hours**: 10–12 h

**Delivers**: Full purchase flow — API to create a Stripe Checkout Session + webhook handler that credits the user on payment completion.

- [ ] `services.py` — `create_checkout_session(user, plan, success_url, cancel_url) -> str` (Stripe Checkout `mode="payment"`); `handle_stripe_event` dispatch for `checkout.session.completed` → calls `credit_user` with `transaction_type="PURCHASE"`
- [ ] `serializers.py` — `CreateCheckoutSessionSerializer` (validates plan slug + `billing_interval="one_time"`), `CreditBalanceSerializer`, `CreditTransactionSerializer`
- [ ] `views.py` — `CreateCheckoutSessionView` (authenticated, returns `checkout_url`); `CreditBalanceView`; `CreditTransactionListView` (paginated); `PurchaseSuccessView` / `PurchaseCancelView` (template views for Stripe redirect targets)
- [ ] `urls.py` — `POST api/billing/purchase/checkout/`, `GET api/billing/balance/`, `GET api/billing/transactions/`, `GET billing/purchase/success/`, `GET billing/purchase/cancel/`
- [ ] Templates — `purchase_success.html` and `purchase_cancel.html` with React mount div pattern
- [ ] `tests/test_purchase.py` — full purchase flow mocked; idempotency on duplicate `checkout.session.completed`; balance reflects credited amount; unauthenticated → 401

**Acceptance**: `POST /api/billing/purchase/checkout/` returns checkout URL; duplicate webhook does not double-credit; `GET /api/billing/balance/` reflects new balance; `pytest --cov-fail-under=90` passes.

---

#### Phase 4: Subscription Plans End-to-End

**Estimated hours**: 12–14 h

**Delivers**: Recurring subscription flow — Stripe Checkout Session in subscription mode, lifecycle webhooks that credit users on each billing cycle.

- [ ] `services.py` — `create_subscription_checkout_session(user, plan, success_url, cancel_url) -> str` (Stripe Checkout `mode="subscription"`); `handle_stripe_event` dispatch for: `invoice.paid` (billing_reason guard: only `subscription_cycle`/`subscription_create` trigger `credit_user` with `transaction_type="PLAN"`); `customer.subscription.created/updated` (sync `Subscription` row); `customer.subscription.deleted` (set `status="canceled"`); `cancel_subscription(subscription) -> Subscription`
- [ ] `serializers.py` — `SubscriptionSerializer`, `CreateSubscriptionCheckoutSerializer`, `PlanSerializer`
- [ ] `views.py` — `PlanListView` (public); `CreateSubscriptionCheckoutView` (authenticated); `SubscriptionDetailView` (authenticated, 404 if none); `CancelSubscriptionView` (authenticated POST)
- [ ] `urls.py` — `GET api/billing/plans/`, `POST api/billing/subscription/checkout/`, `GET api/billing/subscription/`, `POST api/billing/subscription/cancel/`, `GET billing/subscription/success/`
- [ ] `tests/test_subscriptions.py` — `invoice.paid` credits once; duplicate event idempotent; manual billing_reason skipped; subscription status transitions; cancel API; `PlanListView` public access; 404 when no subscription

**Acceptance**: `invoice.paid` grants `credits_per_period` credits; duplicates are absorbed; subscription status reflected in `Subscription` row; `GET /api/billing/plans/` is unauthenticated; `pytest --cov-fail-under=90` passes.

---

#### Phase 5: React UI — Credit Dashboard and Pricing Page

**Estimated hours**: 10–14 h

**Delivers**: Django template mount points for a React billing UI + publishable key API; React starter component guide in README.

- [ ] `views.py` — `StripPublishableKeyView` (authenticated, returns `{"publishable_key": ...}` resolved from env var — never hardcoded); `BillingDashboardView(LoginRequiredMixin, TemplateView)`; `PricingPageView(TemplateView)` (public)
- [ ] Templates — `dashboard.html` (`<div id="billing-root" data-view="dashboard">`); `pricing.html` (`<div id="billing-root" data-view="pricing">`)
- [ ] `urls.py` — `GET billing/dashboard/`, `GET billing/pricing/`, `GET api/billing/config/`
- [ ] `README.md` — React starter guide: five components (CreditBalance widget, PricingPage, PurchaseButton, SubscriptionStatus, TransactionHistory), exact API endpoints, TanStack Query patterns, shadcn/ui component choices, `loadStripe()` redirect pattern
- [ ] `tests/test_views.py` extensions — dashboard redirects unauthenticated; pricing page public; config returns publishable key

**Acceptance**: Dashboard redirects anonymous users; pricing page public; API returns publishable key (never secret key); React starter guide documented; `pytest --cov-fail-under=90` passes (backend only).

---

#### Phase 6: Tests, Docs, and Release Prep

**Estimated hours**: 6–8 h

**Delivers**: 90%+ coverage, mypy clean, `debit_user` API, decisions.md billing contract, full public README.

- [ ] `services.py` — `debit_user(user, amount, description) -> CreditTransaction` with `InsufficientCreditsError(BillingError)` guard; uses `select_for_update()` inside `transaction.atomic()`
- [ ] `tests/test_debit.py` — `debit_user` success, `InsufficientCreditsError` when balance zero, `balance_after` accuracy, `transaction_type="USAGE"`
- [ ] `tests/test_apps.py` — `AppConfig` attributes; `ready()` does not raise
- [ ] `tests/test_circular_import.py` — top-level import confirms no circular dependency (mirrors auth module pattern)
- [ ] Coverage audit — run `pytest --cov-report=html`; close any branch below 80% per-file
- [ ] `decisions.md` — add billing module contract section (mirrors notifications contract at line 928): authoritative config in env vars + `quickscale.yml`; `WebhookEvent` is the idempotency gate; `debit_user` is the approved credit-consumption API; Stripe keys never stored in DB
- [ ] `README.md` — finalize public docs: env var list, Stripe dashboard setup, credits system explanation, React UI integration guide, debit API usage example
- [ ] `module.yml` — version `"0.85.0"`, all deps pinned
- [ ] `mypy src/quickscale_modules_billing` — zero errors
- [ ] CLI gating — coordinate with CLI team to enable `billing` as a selectable module in `quickscale plan`

**Acceptance**: `pytest --cov-fail-under=90`; `mypy` clean; no circular imports; `decisions.md` billing contract section present; `debit_user` raises `InsufficientCreditsError` when balance insufficient; module selectable via `quickscale plan --add billing`.

---

#### Cross-Phase Technical Notes

- **Credit ledger safety**: `credit_user` and `debit_user` MUST use `select_for_update()` on `CreditBalance` inside `transaction.atomic()`, then `F('balance') + amount` ORM update followed by `refresh_from_db()`. Never `balance = balance + amount` in Python.
- **Webhook idempotency**: `WebhookEvent.stripe_event_id` unique constraint + `get_or_create` in `StripeWebhookView` is the outer gate. A second Stripe delivery of the same event is absorbed at the view layer before any handler runs.
- **No dj-stripe**: `stripe` SDK calls only, isolated to `services.py`. Mock with `unittest.mock.patch` in all tests.
- **Secret handling**: Raw Stripe keys are never stored in the database. Only env-var names are stored in config. Keys are resolved at call time via `os.getenv()`, following the notifications module pattern.

---

### v0.86.0: `quickscale_modules.teams` - Teams/Multi-tenancy Module

**Status**: 📋 Planned

**Dependency note**: This milestone remains the SaaS-parity target after the v0.84.0 backups hardening release and the v0.85.0 billing milestone.

**Team Management**:
- [ ] Create team and membership models
- [ ] Implement team creation and settings
- [ ] Add member invitation system
- [ ] Build team dashboard interface

**Role-Based Permissions**:
- [ ] Define role hierarchy (Owner, Admin, Member)
- [ ] Implement permission checking decorators
- [ ] Add role assignment and management
- [ ] Create permission-based UI elements

**Multi-Tenancy**:
- [ ] Implement row-level security patterns
- [ ] Add team-scoped data isolation
- [ ] Create tenant-aware querysets
- [ ] Handle cross-team data access

**Testing**:
- [ ] Unit tests for team models and permissions
- [ ] Integration tests for invitation flows
- [ ] E2E tests for multi-tenancy scenarios

---

### v0.87.0+: HTML Secondary Theme Polish (Optional)

**Status**: 📋 Planned (low priority, after SaaS Feature Parity)

**Rationale**: React theme is now the default (v0.74.0). The HTML theme remains the lightweight secondary option for users preferring a simpler server-rendered stack. Any blocking HTML contract corrections discovered in v0.83.0 belong to the hardening release; this later milestone is for optional polish after the shipped contract is stable again.

**See**: [user_manual.md](../technical/user_manual.md) for current theme architecture and user-facing theme selection guidance.

**When Implemented**: See [decisions.md: Module & Theme Architecture](./decisions.md#module-theme-architecture) for implementation guidance covering the supported React default and HTML secondary theme set.

---
