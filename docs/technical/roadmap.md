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
| v0.85.0 | 🟡 Release-prepared | Billing module | Billing ships in-repo with release-history closeout and quality gates green; maintainer tag/publish still pending |
| v0.86.0 | 📋 Planned | Teams module | Multi-tenancy and team workflows as part of SaaS feature parity with auth, billing, teams, and notifications foundation |
| v0.87.0+ | 📋 Planned | HTML theme polish | Server-rendered secondary option maintenance after the hardening, billing, and teams milestones |

**Legend:**
- ✅ = Completed, released, or internally baselined
- 🟡 = In progress in repo or release-prepared, but not yet tagged/published
- 📋 = Planned/Not Started

**Status:**
- **Current release:** v0.84.0 is the published release
- **Current in-repo milestone:** v0.85.0 billing module is release-prepared in-repo with non-publish quality gates green; maintainer tag/publish is still pending before it moves to published-release history
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

**Status**: 🟡 Release-prepared (pending maintainer publish/tag)

**Release-prep note**: The billing module is implemented and the non-publish release gates are green via `make lint`, `make typecheck`, `make test`, `make version-check`, and `make ci-e2e`. Split-branch publishing plus the maintainer tag/release publication remain manual and are not claimed as complete here.

**Dependency note**: This milestone starts only after v0.84.0 closes the backup hardening work for admin download, full backup completeness, upload-driven restore, and the repo-wide stable runtime/tooling refresh.

**Library Decision**: Direct `stripe` Python SDK (not dj-stripe). dj-stripe mirrors ~50 Stripe tables into the Django ORM but provides none of the credits accounting logic, which is the core domain. The direct SDK gives full control with a minimal footprint, consistent with the notifications module's thin-adapter pattern (`django-anymail` over a full ORM-mirror). Credits, balances, and transactions are custom Django models; Stripe is purely the payment trigger.

**Credits System Design**: Credits are the central abstraction. Monthly plans top up a user's credit balance on each `invoice.paid` webhook. One-time purchases top up credits on `checkout.session.completed`. The credit ledger (`CreditBalance` + `CreditTransaction`) is owned entirely by Django models — Stripe is the payment trigger, not the source of truth for credit counts.

**Shipping Outcome**: This milestone is complete only when billing becomes a real shipped QuickScale module, not just a Django app package. The release must cover package implementation, planner/apply config validation, `quickscale plan --add billing` readiness, generated-project/runtime wiring, and the documentation updates that remove "placeholder only" language.

**Explicit Non-Goals (v0.85.0)**: No Stripe catalog authoring from Django admin, no coupons, no tax/VAT workflows, no metered billing, no seat billing, no proration logic beyond Stripe defaults, no teams-aware shared balances, and no app-owned invoice-history UI. Customer self-service should use Stripe-hosted primitives where needed rather than a custom invoice/payment-method subsystem.

**Pricing Source of Truth**: Stripe Price objects are authoritative for money values. Local `Plan` rows exist for QuickScale-owned API/UI rendering and credit semantics. `Plan.price_cents`, `currency`, and `billing_interval` are mirrored display fields that MUST match the referenced Stripe Price before a Checkout Session is created. v0.85.0 admin flows may activate/deactivate plans and maintain local display metadata, but they do not create or mutate Stripe catalog objects.

**Planner/Apply Config Contract (must exist before readiness flips to public)**:
- `enabled`
- `publishable_key_env_var`
- `secret_key_env_var`
- `webhook_secret_env_var`
- `billing_currency` — ISO 4217 three-letter code (e.g. `usd`, `eur`); defaults to `usd`; validated at apply time against a curated list of Stripe-supported currency codes; `resolve_billing_module_options()` rejects unknown values with an actionable error

**Domain Models**:
- `Plan` — name, slug, stripe_price_id, credits_per_period, price_cents, currency, billing_interval (monthly/yearly/one_time), is_active
- `CreditBalance` — user (1:1), balance (int), updated_at
- `CreditTransaction` — user (FK), amount, transaction_type (PLAN/PURCHASE/USAGE/REFUND/ADJUSTMENT), `stripe_event_id`, `stripe_object_id`, other Stripe refs, description, balance_after (snapshot), created_at
- `Subscription` — user (FK), plan (FK), stripe_subscription_id, stripe_customer_id, status, period dates
- `WebhookEvent` — stripe_event_id (unique), event_type, payload (JSONField), processed, processing_error, created_at

---

**Repository Touchpoints**:
- `quickscale_modules/billing/` — package, tests, public README, manifest
- `quickscale_cli/` — billing contract helper, config schema, planner prompts, apply validation, module catalog readiness
- `quickscale_core/` — generated-project helper surfaces, runtime hints, and tests that now surface billing as module-owned starter links while teams stays hidden
- `docs/technical/` — roadmap, decisions, generated-project structure, user manual, and release note handoff

---

#### Phase 1: Foundation — Package, Models, Admin, Repo Registration

**Estimated hours**: 8–10 h

**Current state**: Complete in-repo as the packaged Phase 1 foundation. Public planner/apply readiness remains gated on later phases in this milestone.

**Delivers**: A fully migrated, admin-registered module skeleton that is importable in the monorepo and aligned with QuickScale packaging contracts. No Stripe dependency yet.

- [x] `module.yml` — name, version, mutable settings for `enabled`, `publishable_key_env_var`, `secret_key_env_var`, `webhook_secret_env_var`, and `billing_currency`; `django_apps: [quickscale_modules_billing]`
- [x] `pyproject.toml` — `stripe` NOT yet included; dev deps: `pytest-django`; `--cov-fail-under=90`; mypy `ignore_missing_imports` for `stripe.*`
- [x] Root `pyproject.toml` — add editable `quickscale-module-billing = {path = "./quickscale_modules/billing", develop = true}`
- [x] Root `mypy.ini` — add `[mypy-quickscale_modules_billing.*]` override alongside `stripe.*` ignore-missing-imports
- [x] `src/quickscale_modules_billing/__init__.py` — export `__version__ = "0.85.0"` matching `module.yml` and `pyproject.toml`
- [x] `apps.py` — `QuickscaleBillingConfig`, `label = "quickscale_modules_billing"`, `default_auto_field = BigAutoField`
- [x] `models.py` — all five models with `select_for_update`-ready `CreditBalance.get_or_create_for_user()` class method
- [x] `admin.py` — all five models registered; read-only admin for `CreditBalance`, `CreditTransaction`, `WebhookEvent`; full CRUD for `Plan`
- [x] `migrations/0001_initial.py` — handwritten, includes `UniqueConstraint` on `WebhookEvent.stripe_event_id`
- [x] `README.md` — replace the placeholder scope with the credits-first direct-Stripe plan, shipping contract, and current non-goals
- [x] `tests/settings.py`, `conftest.py`, `test_models.py`, `test_admin.py`

**Acceptance**: `pytest --cov-fail-under=90` passes; all five models visible in Django admin; no `stripe` import anywhere; package version metadata is self-consistent across `module.yml`, `pyproject.toml`, and `__init__.py`.

---

#### Phase 2: Planner/Apply Contract and Validation

**Estimated hours**: 8–10 h

**Delivers**: A concrete billing config contract that the planner, `quickscale.yml` validation, and apply flow can enforce before the module is marked publicly ready.

- [x] `quickscale_cli/src/quickscale_cli/billing_contract.py` — `default_billing_module_options()`, `resolve_billing_module_options()`, env-var reference validation, currency validation, and `billing_production_targeted()` helper mirroring analytics/notifications contract patterns
- [x] `quickscale_cli/tests/test_billing_contract.py` — defaults match `module.yml`; invalid env-var names fail; invalid currency fails; resolved config is stable
- [x] `quickscale_cli/src/quickscale_cli/schema/config_schema.py` — reject unknown `modules.billing.*` keys and surface actionable suggestions
- [x] `quickscale_cli/src/quickscale_cli/commands/module_config.py` — interactive prompt/resolver for the five mutable keys above
- [x] `quickscale_cli/src/quickscale_cli/commands/apply_command.py` — validate resolved billing config before wiring; fail hard on malformed env-var references instead of silently embedding a broken module
- [x] `quickscale_cli/src/quickscale_cli/module_catalog.py` — keep `billing.ready = False` in this phase; the readiness flip happens only after the full module surface ships

**Acceptance**: Invalid `modules.billing.*` values fail fast in `quickscale.yml` validation and apply preflight; defaults match `module.yml`; billing still remains placeholder-only in public planner flows at the end of this phase.

---

#### Phase 3: Stripe Infrastructure — Customer Management and Webhook Endpoint

**Estimated hours**: 10–12 h

**Current state**: Complete in-repo for the Phase 3 Stripe runtime slice. Public milestone readiness still depends on later phases in this milestone.

**Delivers**: Working webhook endpoint with a persisted idempotency gate and a safe credit ledger core. Stripe SDK integration stays isolated in `services.py`.

- [x] `pyproject.toml` and `module.yml` — align on `stripe>=15.0.0,<16.0.0`, with the CLI dependency-sync regression covering manifest-backed Stripe dependency propagation
- [x] `services.py` — `BillingSettingsSnapshot.from_settings()` (mirrors the analytics runtime snapshot pattern); `BillingError` hierarchy (`BillingConfigurationError`, `BillingDisabledError`, `BillingValidationError`, `BillingWebhookError`, `BillingWebhookSignatureError`); `get_or_create_stripe_customer(user) -> tuple[str, bool]`; `credit_user(...)` atomic duplicate-safe credit grants; `handle_stripe_event()` verifies, persists, and dispatches Stripe webhook events
- [x] `views.py` — `StripeWebhookView` (`@csrf_exempt`) delegates raw body/signature handling to `handle_stripe_event`, returns accepted JSON on success, and maps disabled/signature/configuration/processing failures to explicit HTTP responses
- [x] `urls.py` — `POST billing/webhooks/stripe/`
- [x] `tests/settings_auth_parity.py`, `tests/test_services.py`, `tests/test_views.py` — cover Stripe customer provisioning, duplicate-business-object suppression, webhook error handling, duplicate deliveries, processed/ignored unknown event types, and the auth-backed parity lane

**Acceptance**: `module.yml` and `pyproject.toml` stay aligned on the shipped Stripe dependency; the webhook endpoint rejects bad signatures, records duplicate/unknown events safely through `WebhookEvent.stripe_event_id` and credit-ledger business-object guards, and the targeted CLI dependency-sync regression plus billing service/view tests pass in both the default and auth-backed settings lanes.

---

#### Phase 4a: One-Time Credit Purchases — Domain Layer

**Estimated hours**: 5–6 h

**Delivers**: The purchase domain layer — checkout session creation, webhook dispatch for `checkout.session.completed`, and the serializers that validate purchase requests and expose balance/transaction data. No HTTP surface yet.

- [x] `services.py` — `create_checkout_session(user, plan, success_url, cancel_url) -> str` (Stripe Checkout `mode="payment"`); attach local metadata on both the Checkout Session and underlying PaymentIntent; `handle_stripe_event` dispatch for `checkout.session.completed` → calls `credit_user` with `transaction_type="PURCHASE"`
- [x] `serializers.py` — `CreateCheckoutSessionSerializer` (validates plan slug + `billing_interval="one_time"`), `CreditBalanceSerializer`, `CreditTransactionSerializer`
- [x] `tests/test_purchase.py` (service layer) — `create_checkout_session` returns Stripe URL; `checkout.session.completed` credits correctly; idempotency on duplicate event delivery; second distinct event object for the same Checkout Session does not double-credit; balance snapshot accuracy

**Acceptance**: `create_checkout_session` returns a Stripe-hosted URL; duplicate `checkout.session.completed` deliveries and duplicate underlying Checkout Session events do not double-credit; `pytest --cov-fail-under=90` passes (service layer only).

---

#### Phase 4b: One-Time Credit Purchases — API Surface and Templates

**Estimated hours**: 5–6 h

**Delivers**: The HTTP surface for one-time purchases — authenticated API views, redirect-target template views, and end-to-end coverage of the purchase flow through the API layer.

- [x] `views.py` — `CreateCheckoutSessionView` (authenticated, returns `checkout_url`); `CreditBalanceView`; `CreditTransactionListView` (paginated); `PurchaseSuccessView` / `PurchaseCancelView` (template views for Stripe redirect targets)
- [x] `urls.py` — `POST api/billing/purchase/checkout/`, `GET api/billing/balance/`, `GET api/billing/transactions/`, `GET billing/purchase/success/`, `GET billing/purchase/cancel/`
- [x] Templates — `purchase_success.html` and `purchase_cancel.html` with React mount div pattern
- [x] `tests/test_purchase.py` extensions — `POST /api/billing/purchase/checkout/` returns checkout URL; `GET /api/billing/balance/` reflects credited amount; `GET /api/billing/transactions/` is paginated; unauthenticated → 401; redirect template views respond 200

**Acceptance**: `POST /api/billing/purchase/checkout/` returns checkout URL; `GET /api/billing/balance/` reflects new balance; unauthenticated requests are rejected; `pytest --cov-fail-under=90` passes.

---

#### Phase 5a: Subscription Core Lifecycle

**Estimated hours**: 7–8 h

**Current state**: Complete in-repo for the Phase 5a subscription lifecycle slice. Phase 5b still owns self-service cancel and portal flows plus out-of-order event recovery.

**Delivers**: The shipped subscription slice covers reservation-first checkout session creation, recurring invoice and subscription-state webhook handling, the recurring-only plan/current-subscription API surface, and dedicated subscription success/cancel return pages.

**Tracked contract for this phase**:
- The public plan catalog is recurring-only. `GET /api/billing/plans/` returns active `monthly` and `yearly` plans only; `one_time` plans remain purchase-only and stay out of the subscription catalog by contract.
- Recurring checkout uses the shared recurring/purchase Stripe Price parity helper before creating Stripe Checkout, so local `Plan.price_cents`, `currency`, and `billing_interval` must still match the authoritative Stripe Price for subscription checkouts as well as one-time purchases.
- Supported local subscription statuses are `incomplete`, `incomplete_expired`, `trialing`, `active`, `past_due`, `canceled`, `unpaid`, and `paused`. Unknown future Stripe statuses fail webhook processing explicitly for retry instead of being coerced.
- A current subscription means any nonterminal row in `incomplete`, `trialing`, `active`, `past_due`, `unpaid`, or `paused`. Starting a second subscription checkout is blocked while any current row exists.
- Subscription checkout is reservation-first. A reusable live `incomplete` reservation for the same recurring plan reuses its active Checkout Session URL; stale or failed reservations are expired before a fresh checkout reservation is created.
- The singular current-subscription API returns the newest current row if one exists; otherwise it returns `404` instead of surfacing historical canceled rows as current state.
- Subscription checkout uses dedicated server-owned success and cancel routes. Purchase success and cancel routes remain unchanged.

- [x] `services.py` — `create_subscription_checkout_session(user, plan, success_url, cancel_url) -> str` now uses Stripe Checkout `mode="subscription"`, attaches metadata on the Checkout Session and `subscription_data.metadata`, enforces shared recurring/purchase Stripe Price parity, and uses reservation-first retry reuse/expire semantics; `handle_stripe_event` dispatch covers `invoice.paid` (billing_reason guard: only `subscription_cycle`/`subscription_create` trigger `credit_user` with `transaction_type="PLAN"`), `invoice.payment_failed` (set local `Subscription.status = "past_due"`), `customer.subscription.created/updated` (sync `Subscription` row), and `customer.subscription.deleted` (set `status="canceled"`)
- [x] `models.py` and `migrations/0002_subscription_reservation_invariants.py` — `Subscription.Status` now carries the supported local vocabulary for this phase (`incomplete`, `incomplete_expired`, `trialing`, `active`, `past_due`, `canceled`, `unpaid`, `paused`), exposes the shared current-subscription predicate used by checkout blocking and current-subscription lookup, and enforces the reservation-capable single-current-subscription invariant
- [x] `serializers.py` — `SubscriptionSerializer`, `CreateSubscriptionCheckoutSerializer`, and `PlanSerializer` ship; `PlanSerializer` remains the recurring-only public contract and exposes `billing_interval` explicitly
- [x] `views.py` — `PlanListView` serves the public recurring catalog only; `CreateSubscriptionCheckoutView` is authenticated, rejects caller-supplied redirect fields, and blocks checkout when any current subscription exists; `SubscriptionDetailView` returns the newest current row or `404`; dedicated subscription success/cancel template views stay separate from purchase-branded copy and DOM hooks
- [x] `urls.py` — `GET api/billing/plans/`, `POST api/billing/subscription/checkout/`, `GET api/billing/subscription/`, `GET billing/subscription/success/`, and `GET billing/subscription/cancel/` are live; existing purchase success/cancel routes stay unchanged
- [x] Templates — subscription-specific success/cancel pages now ship, while purchase success/cancel pages and purchase DOM hooks remain stable
- [x] Focused coverage — `tests/test_models.py`, `tests/test_migrations.py`, `tests/test_services.py`, `tests/test_views.py`, `tests/test_purchase.py`, and `tests/test_subscriptions.py` cover recurring crediting, duplicate invoice protection, manual `billing_reason` skips, payment-failed status sync, supported subscription status transitions, unsupported Stripe status retry behavior, price-parity mismatches, reservation reuse/expiration, current-subscription lookup, recurring-only plan filtering, authenticated checkout, and dedicated subscription success/cancel routes

**Acceptance**: `invoice.paid` grants `credits_per_period` credits only for `subscription_create` and `subscription_cycle`; duplicate deliveries and duplicate underlying invoice events are absorbed; `invoice.payment_failed` sets `Subscription.status = "past_due"` and a later qualifying `invoice.paid` restores the local row to the synced current status; `customer.subscription.created`, `customer.subscription.updated`, and `customer.subscription.deleted` keep the local subscription row aligned with supported Stripe states while unsupported future states fail explicitly for retry; recurring checkout enforces shared Stripe Price parity, reuses a live reservation Checkout Session when safe, expires stale or failed reservations before recreating checkout, and blocks a second checkout while any current subscription row exists; `GET /api/billing/plans/` is unauthenticated and recurring-only; `GET /api/billing/subscription/` returns the newest current row or `404`; both subscription success and cancel routes are live while purchase routes remain unchanged; focused validation coverage exists in `test_models.py`, `test_migrations.py`, `test_services.py`, `test_views.py`, `test_purchase.py`, and `test_subscriptions.py`.

---

#### Phase 5b: Subscription Self-Service and Event Recovery

**Estimated hours**: 5–6 h

**Current state**: Complete in-repo for the Phase 5b subscription self-service and event-recovery slice.

**Delivers**: The shipped Phase 5b slice adds cancel and billing portal self-service flows plus out-of-order `invoice.paid` recovery so a late recurring charge reconciles either an existing incomplete reservation or a missing local subscription row before credits are granted.

- [x] `services.py` — `cancel_current_subscription(user)` schedules `cancel_at_period_end=True`; `create_billing_portal_session(user, return_url) -> str` returns a Stripe-hosted portal URL; `invoice.paid` recovery falls back to Stripe subscription retrieval when the local row is missing and reconciles an existing incomplete reservation before crediting
- [x] `views.py` — `CancelSubscriptionView` is an authenticated POST that returns `204 No Content`; `CreateBillingPortalSessionView` is an authenticated POST that returns `portal_url`, uses the server-owned module `billing/portal/return/` target, and rejects caller-supplied redirect input
- [x] `urls.py` — `POST api/billing/subscription/cancel/`, `POST api/billing/portal/`, and `GET billing/portal/return/`
- [x] `tests/test_views.py` and `tests/test_services.py` — cancel API returns `204`; portal-session API returns `portal_url`, rejects caller-supplied redirect input, and uses the server-owned return target; missing-row `invoice.paid` recovery backfills the local `Subscription` row through Stripe subscription retrieval
- [x] `tests/test_subscriptions.py` — `invoice.paid` arriving before `customer.subscription.created` reconciles an existing incomplete reservation before crediting and remains stable when the later subscription update lands

**Acceptance**: Cancel defaults to `cancel_at_period_end=True` and `POST /api/billing/subscription/cancel/` returns `204`; `POST /api/billing/portal/` returns a Stripe-hosted `portal_url`, uses the server-owned module `billing/portal/return/` target, and rejects caller-supplied redirect input; out-of-order `invoice.paid` recovery now handles both the missing-row and incomplete-reservation paths via Stripe subscription retrieval fallback before crediting; focused billing checkpoints passed.

---

#### Phase 6a: Module-Owned UI — Backend Pages and API

**Estimated hours**: 4–6 h

**Delivers**: Django backend for billing UI — publishable key API, login-gated dashboard, and public pricing page. No Stripe JS or React in this phase; only the Django mount points and their tests.

- [x] `views.py` — `StripePublishableKeyView` (authenticated, returns `{"publishable_key": ...}` resolved from env var — never hardcoded); `BillingDashboardView(LoginRequiredMixin, TemplateView)`; `PricingPageView(TemplateView)` (public)
- [x] Templates — `dashboard.html` (`<div id="billing-root" data-view="dashboard">`); `pricing.html` (`<div id="billing-root" data-view="pricing">`)
- [x] `urls.py` — `GET billing/dashboard/`, `GET billing/pricing/`, `GET api/billing/config/`
- [x] `tests/test_views.py` extensions — dashboard redirects unauthenticated; pricing page public; config returns publishable key; config never leaks secret key

**Acceptance**: Dashboard redirects anonymous users to login; pricing page is publicly accessible; `GET /api/billing/config/` returns publishable key and never the secret key; `pytest --cov-fail-under=90` passes.

---

#### Phase 6b: React Integration Guide

**Estimated hours**: 5–7 h

**Current state**: Complete in-repo for the Phase 6b React integration guide slice.

**Delivers**: A complete React adoption guide in `README.md` so developers can wire the billing API into the generated React frontend without QuickScale rewriting user-owned files.

- [x] `README.md` — React starter guide covering: five components (CreditBalance widget, PricingPage, PurchaseButton, SubscriptionStatus, TransactionHistory); exact API endpoint reference table; TanStack Query patterns for balance polling and transaction pagination; shadcn/ui component choices for each surface; `loadStripe()` redirect pattern for checkout and portal flows; environment variable wiring (`VITE_STRIPE_PUBLISHABLE_KEY` from `/api/billing/config/`)

**Acceptance**: All five component patterns documented with working API call examples; `loadStripe()` redirect pattern shown for both purchase and subscription checkout; env-var wiring is explicit and does not require hardcoded keys.

---

#### Phase 6c: Module-Owned Django Pages — Pricing Showcase

**Estimated hours**: 3–4 h

**Context**: Phase 6a shipped `pricing.html` and `dashboard.html` as minimal mount-point stubs (`<div id="billing-root" data-view="...">` only). This phase replaces those stubs with real server-rendered Django pages that are usable without any React frontend. The billing module owns these pages; no starter-theme files are touched.

**Explicit scope boundary**: These pages must be self-contained Django HTML — no Vite, no React, no external JS dependencies. Inline CSS only. The `<div id="billing-root">` data attribute is preserved so a React layer can mount on top later if desired.

**Delivers**: A functional public pricing page and all six Stripe redirect / portal landing pages with real layout and content.

- [x] `views.py` — `PricingPageView.get_context_data()` passes `plans` queryset (all active plans, ordered by `billing_interval`, `price_cents`); attach a `price_display` annotation on each plan using a module-local `_format_price_cents(cents, currency)` helper; `PurchaseSuccessView`, `PurchaseCancelView`, `SubscriptionSuccessView`, `SubscriptionCancelView`, `BillingPortalReturnView` remain plain `TemplateView` subclasses (no extra context needed)
- [x] `templates/quickscale_modules_billing/pricing.html` — self-contained inline-CSS page; plans grouped by `billing_interval` with inline `{% regroup %}`; each plan card shows name, interval, `price_display`, `credits_per_period`; auth-aware CTA: authenticated users see a "Go to dashboard →" primary button per plan (linking to `/billing/dashboard/`), unauthenticated users see a "Sign in to purchase" button linking to the login URL with `?next=/billing/pricing/`; empty-state card when no plans exist; footer note with dashboard/login link
- [x] `templates/quickscale_modules_billing/purchase_success.html` — centered card layout; green-tinted icon; heading "Purchase complete"; body explains credits may take a moment; two actions: "Go to dashboard" (primary) and "Back to app" (outline)
- [x] `templates/quickscale_modules_billing/purchase_cancel.html` — centered card layout; amber-tinted icon; heading "Purchase canceled"; body confirms no charge; two actions: "Try again" → `/billing/pricing/` (primary) and "Back to app" (outline)
- [x] `templates/quickscale_modules_billing/subscription_success.html` — centered card layout; indigo-tinted icon; heading "Subscription started"; body + processing-delay note; two actions: "Go to dashboard" (primary) and "Back to app" (outline)
- [x] `templates/quickscale_modules_billing/subscription_cancel.html` — centered card layout; amber-tinted icon; heading "Subscription not started"; body confirms no charge; two actions: "View plans" → `/billing/pricing/` (primary) and "Back to app" (outline)
- [x] `templates/quickscale_modules_billing/billing/portal_return.html` — centered card layout; indigo-tinted icon; heading "Back from billing portal"; body explains changes may take a moment; two actions: "Go to dashboard" (primary) and "Back to app" (outline)
- [x] `tests/test_views.py` — update `test_pricing_page_view_is_public_and_render` to add `@pytest.mark.django_db` (pricing view now queries DB) and match the new heading text; update `test_subscription_return_views_are_public_and_render` param for `subscription-success` to match "Subscription started"

**Template constraints**:
- All CSS is inline `<style>` in each file — no external stylesheet or `{% static %}` reference
- Each file preserves the existing `id` and `data-*` attributes (`id="billing-root"`, `data-view`, `id="billing-purchase-root"`, `data-purchase-status`, etc.) so the React mount contract from Phase 6a is not broken
- No JavaScript in any template — Stripe redirect landing pages are purely informational

**Acceptance**: `GET /billing/pricing/` renders plan cards when plans exist and an empty-state card when none exist; `price_display` formats correctly for USD and non-USD currencies; all six redirect/portal landing pages respond 200 with meaningful headings and back-link actions; `pytest --cov-fail-under=90` passes; no `{% static %}` or external JS in any template.

---

#### Phase 6d: Module-Owned Django Pages — Dashboard Showcase

**Estimated hours**: 4–5 h

**Context**: Continues Phase 6c. The dashboard is login-gated and requires real context data — credit balance, current subscription, and recent transactions — to be useful. This phase delivers that context plumbing and the dashboard template.

**Delivers**: A functional login-gated billing dashboard that shows a user's current credit balance, subscription status, and the 10 most recent credit transactions without requiring any React.

- [x] `views.py` — `BillingDashboardView.get_context_data()` passes: `balance` (from `CreditBalance.get_or_create_for_user(self.request.user)`); `recent_transactions` (last 10 `CreditTransaction` rows for the user ordered by `-created_at, -id`); `subscription` (newest current `Subscription` row via `Subscription.current_status_q()`, or `None`)
- [x] `templates/quickscale_modules_billing/dashboard.html` — self-contained inline-CSS page with:
  - **Balance card**: shows `balance.balance` (int) with "available credits" label
  - **Subscription card**: shows plan name + `get_status_display` badge if subscription exists; shows "No active subscription" with a "View plans →" link to `/billing/pricing/` otherwise
  - **Active subscription block** (conditional on subscription): plan name + interval, `current_period_start/end` dates if set; "Manage via Stripe portal" button (`data-action="billing-portal"` for future JS wiring); "Cancel subscription" button (`data-action="cancel-subscription"`) shown only when `subscription.status` is `active` or `trialing`
  - **No subscription block** (conditional): description copy + "View plans" primary button → `/billing/pricing/`
  - **Recent transactions table**: date (`M j, Y`), transaction type badge colour-coded by `PLAN/PURCHASE/USAGE/REFUND/ADJUSTMENT`, signed amount, `balance_after`, description; empty-state row when no transactions
- [x] `tests/test_views.py` — extend `test_billing_dashboard_view_renders_for_authenticated_users` to assert `credit balance`, `id="billing-root"`, and `data-view="dashboard"` are present in the rendered output

**Template constraints** (same as Phase 6c):
- Inline CSS only; no external stylesheets or JS
- Preserves `id="billing-root"` and `data-view="dashboard"` for the React mount contract
- Uses `{% if subscription.status == 'active' or subscription.status == 'trialing' %}` (not `in` string membership) for the cancel button guard

**Acceptance**: Dashboard redirects anonymous users to login (existing behaviour unchanged); authenticated users see their balance, subscription state, and transaction history; `BillingDashboardView.get_context_data()` is covered by the updated test; `pytest --cov-fail-under=90` passes; no external JS or CSS in the template.

---

#### Phase 7: QuickScale Distribution Enablement

**Estimated hours**: 10–12 h

**Delivers**: Billing becomes a real selectable QuickScale module across planner, generated projects, runtime helper surfaces, and repo tests that currently enforce placeholder-only behavior.

- [x] `quickscale_cli/src/quickscale_cli/module_catalog.py` — flip `billing.ready` to `True`, remove placeholder-only readiness messaging, keep description aligned with the credits-first Stripe scope
- [x] `quickscale_core/context_processors.py` + tests — decide and implement whether billing joins the shipped helper-module output once it is a real module
- [x] `quickscale_core/tests/test_react_theme_integration.py` — replace billing-placeholder assertions with the final shipped contract for starter routes/cards/module flags
- [x] `quickscale_core/tests/test_error_pages.py` — replace "never mention billing" assertions with the final shipped install/runtime guidance
- [x] Generated project templates/docs — update any helper surfaces, starter copy, or managed hints that currently exclude billing because it is a placeholder
- [x] Public planner/apply flow — billing becomes selectable only after Phases 1–6 pass; billing hard-requires the QuickScale `auth` module at `quickscale apply` time — apply fails with an actionable error if `auth` is absent

**Acceptance**: `quickscale plan --add billing` works in public flows; placeholder-only wording is removed from shipped helper surfaces; generator/core tests reflect the final billing contract rather than a hidden placeholder.

---

#### Phase 8a: React Showcase Theme — Billing Integration Verification and Tests

**Estimated hours**: 3–4 h

**Context**: The `showcase_react` theme templates already contain billing wiring added during Phase 7 (`useModules.ts.j2`, `index.html.j2`, `Dashboard.tsx.j2`, `Sidebar.tsx.j2`). This phase audits that wiring for correctness, closes any gaps, and adds dedicated test methods that pin the exact generated output so future template changes cannot silently regress billing theme support.

**Template audit checklist** (read each file in `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/` and verify each contract point before writing tests):

- `src/hooks/useModules.ts.j2`:
  - `QuickScaleModules` interface declares `billing: boolean`
  - `defaultConfig.modules` initializes `billing: false`
  - `QuickScaleModulePaths` interface declares `billing: string`
  - `defaultConfig.modulePaths.billing` is set to `'/billing/pricing/'`

- `templates/index.html.j2`:
  - `window.__QUICKSCALE__.modules.billing` is rendered as `{% if 'quickscale_modules_billing' in settings.INSTALLED_APPS %}true{% else %}false{% endif %}`
  - `window.__QUICKSCALE__.modulePaths.billing` renders the auth-aware path: `/billing/dashboard/` when `user.is_authenticated`, `/billing/pricing/` otherwise — the exact `{% if user.is_authenticated %}` branch must be present and produce the correct strings

- `src/pages/Dashboard.tsx.j2`:
  - `buildModuleInfo()` receives `billingPath` as a parameter (alongside `socialPath`)
  - The billing card entry has `key: 'billing'`, `icon: CreditCard`, `reloadDocument: true`, `actionLabel: 'Open billing'`, and `href: billingPath` (not a hardcoded string)
  - `CreditCard` is imported from `lucide-react`
  - `buildModuleInfo(...)` is called with `modulePaths.billing` as the `billingPath` argument

- `src/components/layout/Sidebar.tsx.j2`:
  - `CreditCard` is imported from `lucide-react`
  - The billing `NavItem` has `name: 'Billing'`, `href: modulePaths.billing`, `icon: CreditCard`, `show: modules.billing`, `reloadDocument: true`
  - The `navigation` array entry is positioned relative to the other module entries (between Forms and Social)

- `src/App.tsx.j2`:
  - No `/billing/` `<Route>` is declared — billing pages are Django-owned (`reloadDocument: true` in both Dashboard card and Sidebar means the SPA never intercepts billing routes)
  - Confirm no `BillingPage` import exists

**Implementation tasks**:

- [x] Audit each template file against the checklist above; fix any gaps before writing tests
- [x] `quickscale_core/tests/test_react_theme_integration.py` — add `test_react_theme_billing_window_config_flag`:
  - Generate a project with `theme="showcase_react"`
  - Read `templates/index.html` from the output
  - Assert the `billing:` module flag uses the conditional `INSTALLED_APPS` check (exact substring match)
  - Assert the `modulePaths.billing` entry uses the `{% if user.is_authenticated %}` auth-aware branch with `/billing/dashboard/` for authenticated and `/billing/pricing/` for unauthenticated
- [x] `test_react_theme_billing_dashboard_card`:
  - Generate a project; read `src/pages/Dashboard.tsx` from the output
  - Assert `key: 'billing'` is present
  - Assert `icon: CreditCard` maps to the billing entry (not another module)
  - Assert `reloadDocument: true` is on the billing entry
  - Assert `actionLabel: 'Open billing'` is present
  - Assert `href: billingPath` is used (not a hardcoded `/billing/` string)
  - Assert `CreditCard` appears in the lucide-react import line
- [x] `test_react_theme_billing_sidebar_nav_entry`:
  - Generate a project; read `src/components/layout/Sidebar.tsx` from the output
  - Assert billing `NavItem` has `name: 'Billing'`, `show: modules.billing`, `reloadDocument: true`
  - Assert `CreditCard` appears in the lucide-react import line
  - Assert `modulePaths.billing` is the `href` source (not a hardcoded string)
- [x] `test_react_theme_billing_no_spa_route`:
  - Generate a project; read `src/App.tsx` from the output
  - Assert no `<Route` element with a path matching `/billing` is present
  - Assert no `BillingPage` import is present
- [x] `test_react_theme_billing_modules_hook_interface`:
  - Generate a project; read `src/hooks/useModules.ts` from the output
  - Assert `billing: boolean` appears in the `QuickScaleModules` interface block
  - Assert `billing: false` appears in `defaultConfig.modules`
  - Assert `billing: string` appears in `QuickScaleModulePaths`
  - Assert `modulePaths.billing` default value is `'/billing/pricing/'`

**Acceptance**: All five new test methods pass under `pytest quickscale_core/tests/test_react_theme_integration.py`; no `hardcoded /billing/` path strings appear in `Dashboard.tsx.j2` or `Sidebar.tsx.j2` (all routing goes through `modulePaths.billing`); no SPA `/billing/` route exists in `App.tsx.j2`; billing module flag in `index.html.j2` uses the exact `INSTALLED_APPS` conditional pattern consistent with all other module flags.

---

#### Phase 8b: HTML Showcase Theme — Billing Integration Verification and Tests

**Estimated hours**: 2–3 h

**Context**: The `showcase_html` theme templates already contain billing wiring added during Phase 7 (`index.html.j2`, `navigation.html.j2`). This phase audits that wiring, closes any gaps, and pins it with dedicated test methods in the HTML theme integration test suite.

**Template audit checklist** (read each file in `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_html/templates/` and verify each contract point before writing tests):

- `templates/index.html.j2` (the generated `templates/index.html`):
  - Billing module card is guarded by `{% if 'quickscale_modules_billing' in settings.INSTALLED_APPS %}`
  - Card header reads `<h3>Billing</h3>` with `<span class="module-badge">Active</span>`
  - Card body mentions Stripe-backed pricing and billing dashboard pages
  - A module note explains that billing uses module-owned Django pages (no starter-owned frontend billing app)
  - Auth-aware action links: `{% if user.is_authenticated %}` branch renders `<a class="module-link" href="/billing/dashboard/">Open billing dashboard</a>`; else branch renders `<a class="module-link" href="/billing/pricing/">View pricing</a>`
  - The billing card block is closed with `{% endif %}` before the next module block

- `templates/components/navigation.html.j2` (the generated `templates/components/navigation.html`):
  - Navigation section guarded by `{% if 'quickscale_modules_billing' in settings.INSTALLED_APPS %}`
  - Section title is `<span class="nav-section-title">Billing</span>`
  - Unconditional `<a href="/billing/pricing/">Pricing</a>` link always present when billing is installed
  - `{% if user.is_authenticated %}` guard renders `<a href="/billing/dashboard/">Billing Dashboard</a>` for authenticated users
  - `{% else %}` branch renders a `<span class="nav-disabled-link">` hint to sign in
  - `{% endif %}` for the auth guard, then `{% endif %}` closing the billing block
  - Teams navigation section is NOT present (teams is not yet a shipped module)

**Implementation tasks**:

- [x] Audit each template file against the checklist above; fix any gaps before writing tests
- [x] `quickscale_core/tests/test_html_theme_integration.py` — add `test_html_theme_billing_card_and_auth_aware_links`:
  - Generate a project with `theme="showcase_html"`
  - Read `templates/index.html` from the output
  - Assert `{% if 'quickscale_modules_billing' in settings.INSTALLED_APPS %}` guards the billing card
  - Assert `<h3>Billing</h3>` is present
  - Assert `/billing/pricing/` link is present (the unauthenticated branch)
  - Assert `/billing/dashboard/` link is present (the authenticated branch)
  - Assert `{% if user.is_authenticated %}` auth gate is present within the billing card
  - Assert the module note text about Django-owned pages is present (billing does not scaffold a starter-owned billing UI)
- [x] `test_html_theme_billing_navigation_section`:
  - Generate a project; read `templates/components/navigation.html` from the output
  - Assert `<span class="nav-section-title">Billing</span>` is present
  - Assert `/billing/pricing/` link appears unconditionally inside the billing nav block
  - Assert `/billing/dashboard/` link appears under an `{% if user.is_authenticated %}` guard
  - Assert a `nav-disabled-link` hint is present in the `{% else %}` branch for the billing nav
  - Assert `<span class="nav-section-title">Teams</span>` is NOT present
- [x] `test_html_theme_billing_installed_apps_guard`:
  - Generate a project; read both `templates/index.html` and `templates/components/navigation.html`
  - Assert the billing card in `index.html` is wrapped in exactly one `INSTALLED_APPS` check for `quickscale_modules_billing`
  - Assert the billing nav block in `navigation.html` is wrapped in exactly one `INSTALLED_APPS` check for `quickscale_modules_billing`
  - Assert neither file contains any billing-related unconditional hardcoded URL strings outside the conditional blocks
- [x] `test_html_theme_billing_no_teams_entry`:
  - Generate a project; read both `templates/index.html` and `templates/components/navigation.html`
  - Assert `Teams` does not appear in either file (teams is not a shipped module in this release)
  - Assert `quickscale_modules_teams` does not appear in either file

**Acceptance**: All four new test methods pass under `pytest quickscale_core/tests/test_html_theme_integration.py`; billing card and nav section are guarded by the `INSTALLED_APPS` conditional in both generated files; auth-aware links route authenticated users to `/billing/dashboard/` and unauthenticated users to `/billing/pricing/`; teams is absent from generated HTML theme output.

---

#### Phase 8: Tests, Docs, and Release Prep

**Estimated hours**: 6–8 h

**Delivers**: 90%+ coverage, mypy clean, `debit_user` API, decisions.md billing contract, full public README, and release/publishing readiness.

**Current state**: Release-prepared in-repo. The billing milestone has fresh green evidence for `make lint`, `make typecheck`, `make test`, `make version-check`, and `make ci-e2e`; the remaining manual closeout is split-branch publishing plus maintainer tag/release publication.

- [x] `services.py` — `debit_user(user, amount, description) -> CreditTransaction` with `InsufficientCreditsError(BillingError)` guard; uses `select_for_update()` inside `transaction.atomic()`
- [x] `tests/test_debit.py` — `debit_user` success, `InsufficientCreditsError` when balance zero, `balance_after` accuracy, `transaction_type="USAGE"`
- [x] `tests/test_apps.py` — `AppConfig` attributes; `ready()` does not raise
- [x] `tests/test_circular_import.py` — top-level import confirms no circular dependency (mirrors auth module pattern)
- [x] Monorepo verification — targeted CLI/core tests updated in Phase 7 pass alongside module tests
- [ ] Coverage audit — run `pytest --cov-report=html`; close any branch below 80% per-file
- [x] `decisions.md` — add billing module contract section (mirrors notifications contract at line 928): authoritative config in env vars + `quickscale.yml`; `WebhookEvent` is the idempotency gate; `debit_user` is the approved credit-consumption API; Stripe keys never stored in DB
- [x] `README.md` — finalize public docs: env var list, Stripe dashboard setup, credits system explanation, Stripe-hosted portal usage, React UI integration guide, debit API usage example
- [x] `docs/technical/user_manual.md`, `generated_project_structure.md`, and any placeholder inventory notes — update the "billing is not shipped yet" wording to the released contract
- [x] `module.yml`, `pyproject.toml`, `__init__.py` — version `"0.85.0"` and dependency metadata all aligned
- [x] `mypy src/quickscale_modules_billing` — zero errors
- [ ] Split-branch publishing — run `./scripts/publish_module.sh billing` and verify `splits/billing-module`

**Acceptance**: `pytest --cov-fail-under=90`; `mypy` clean; no circular imports; `decisions.md` billing contract section present; `debit_user` raises `InsufficientCreditsError` when balance insufficient; module selectable via `quickscale plan --add billing`; split branch and maintainer publication remain the only open release-closeout steps.

---

#### Cross-Phase Technical Notes

- **Credit ledger safety**: `credit_user` and `debit_user` MUST use `select_for_update()` on `CreditBalance` inside `transaction.atomic()`, then `F('balance') + amount` ORM update followed by `refresh_from_db()`. Never `balance = balance + amount` in Python.
- **Webhook idempotency**: `WebhookEvent.stripe_event_id` unique constraint + `get_or_create` in `StripeWebhookView` is only the outer transport gate. Credit-granting logic MUST also guard against duplicate underlying Stripe business objects (`checkout.session.id` for purchases, `invoice.id` for subscription credits) because Stripe can emit duplicate deliveries and, in some cases, separate Event objects for the same underlying object/event pair.
- **Event ordering**: Stripe does not guarantee webhook ordering. `invoice.paid` might arrive before local `Subscription` sync state exists. Always attach local metadata on Checkout Sessions and underlying PaymentIntent/Subscription objects, and allow the handler to retrieve missing Stripe resources to reconcile local state.
- **Webhook event allowlist**: Subscribe only to the event types the module actually handles in this release: `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.created`, `customer.subscription.updated`, and `customer.subscription.deleted`.
- **Project-auth prerequisite**: Billing requires an authenticated `AUTH_USER_MODEL` and login flow. Billing hard-requires the QuickScale `auth` module: `quickscale apply` fails with an actionable error if `auth` is absent before billing can be wired.
- **No dj-stripe**: `stripe` SDK calls only, isolated to `services.py`. Mock with `unittest.mock.patch` in all tests.
- **Frontend ownership**: `quickscale apply` must not rewrite user-owned generated React files to force billing pages into existing projects. v0.85.0 ships module-owned Django pages plus manual React adoption guidance; any fresh-generation starter changes must stay in QuickScale-owned templates/tests.
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
