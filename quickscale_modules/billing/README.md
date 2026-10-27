# QuickScale Billing Module

Credits-first, organization-backed billing for QuickScale projects. Django owns plans,
balances, transactions, purchase Checkout lifecycle reservations, subscription snapshots, and
webhook idempotency records. Stripe is the payment trigger through the direct `stripe` Python
SDK; the Django ledger remains the source of truth for credit accounting. Billing requires the
`orgs` and `auth` modules at plan/apply/runtime.

## Overview

- Independently packaged Django module metadata under `quickscale_modules/billing/`.
- Six core models: `Plan`, `CreditBalance`, `CreditTransaction`, `PurchaseCheckout`,
  `Subscription`, and `WebhookEvent`.
- Django admin registration for plans, balances, transactions, purchase Checkout reservations,
  subscriptions, and webhook events.
- Stripe webhook handling for purchases and recurring subscription lifecycle events.
- Authenticated JSON APIs for balance, transactions, purchase checkout, subscription checkout,
  subscription status, subscription cancel, billing portal, and publishable-key discovery.
- Module-owned Django pages for flat dashboard and pricing routes in both Solo and SaaS modes,
  purchase return routes, subscription return routes, and the billing portal return route.
- Manual React adoption guidance, so generated frontend files remain user-owned.

Boundaries:

- Billing requires the `orgs` and `auth` modules at plan/apply/runtime; there is no standalone
  billing install without those foundations.
- Planner/apply auto-materializes `orgs` when billing is selected, and `orgs` auto-materializes
  `notifications`; auth remains an explicit prerequisite.
- All billing pages and APIs use flat routes (`billing/...`, `billing/api/...`) in both Solo and
  SaaS modes; no org-scoped billing URL tree exists.
- `GET /billing/api/plans/` is intentionally recurring-only; one-time credit packs are
  purchaseable but do not ship through a public catalog endpoint.
- Checkout success, cancel, and portal return URLs are server-owned; callers may not supply
  them in API requests.
- Stripe keys reach billing code as the `QUICKSCALE_BILLING_PUBLISHABLE_KEY`,
  `QUICKSCALE_BILLING_SECRET_KEY`, and `QUICKSCALE_BILLING_WEBHOOK_SECRET` settings; `quickscale
  apply` renders each one from the environment variable its `_ENV_VAR` option names (rule 35), and
  the credential values are never stored in the database.

## Configuration

The module declares the options below in `module.yml`; `quickscale plan` and `quickscale apply`
write them to the generated settings, and `quickscale.yml` carries the desired values.

| Option | Type | Default | Django setting | Description |
|--------|------|---------|----------------|-------------|
| `enabled` | boolean | `true` | `QUICKSCALE_BILLING_ENABLED` | Enable the billing runtime and Stripe-backed services. |
| `publishable_key_env_var` | string | `STRIPE_PUBLISHABLE_KEY` | `QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR` | Environment-variable name containing the Stripe publishable key used by billing checkout flows. |
| `secret_key_env_var` | string | `STRIPE_SECRET_KEY` | `QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR` | Environment-variable name containing the Stripe secret key for server-side API calls. |
| `webhook_secret_env_var` | string | `QUICKSCALE_BILLING_WEBHOOK_SECRET` | `QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR` | Environment-variable name containing the Stripe webhook signing secret. |
| `currency` | string | `usd` | `QUICKSCALE_BILLING_CURRENCY` | ISO 4217 billing currency code; Checkout refuses a plan whose currency differs from this value or from its Stripe price. |
| `api_rate_limit` | string | `30/hour` | `QUICKSCALE_BILLING_API_RATE_LIMIT` | Throttle rate per client for billing's Stripe-calling checkout and portal endpoints. Format: `<count>/<period>`. |
| `transactions_per_page` | integer | `25` | `QUICKSCALE_BILLING_TRANSACTIONS_PER_PAGE` | Number of credit transactions per page in the ledger list API. |
| `plans_per_page` | integer | `25` | `QUICKSCALE_BILLING_PLANS_PER_PAGE` | Number of plans per page in the public plan catalog API. |

Backend environment variables:

```bash
export QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR=STRIPE_PUBLISHABLE_KEY
export QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR=STRIPE_SECRET_KEY
export QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR=QUICKSCALE_BILLING_WEBHOOK_SECRET

export STRIPE_PUBLISHABLE_KEY=pk_live_or_test_...
export STRIPE_SECRET_KEY=sk_live_or_test_...
export QUICKSCALE_BILLING_WEBHOOK_SECRET=whsec_...
```

The `*_env_var` options name the environment variables that carry the real credentials; only
the credential values themselves are deploy-time environment variables. `apply` renders each one
into the projected setting above, so billing code reads the setting rather than the environment.
Keep Stripe key wiring runtime-owned and never hardcode the publishable key in the frontend
source tree.

## Public surface

### Role requirements

Billing data is owner-only. Every billing JSON endpoint except the public plan catalog requires
an authenticated session whose active organization grants the `owner` role: an anonymous caller
answers `401`, and a caller with no organization context or below `owner` is refused (`403`).
The dashboard page requires login and the active organization's `owner` role; the pricing page
and the Stripe return pages are public.

| Surface | Minimum role |
|---------|--------------|
| `billing/api/plans/` (plan catalog) | Public (no session) |
| `billing/api/config/`, `billing/api/balance/`, `billing/api/transactions/`, `billing/api/purchase/checkout/`, `billing/api/subscription/`, `billing/api/subscription/checkout/`, `billing/api/subscription/cancel/`, `billing/api/portal/` | `owner` |
| `billing/dashboard/` | `owner` |
| `billing/pricing/`, `billing/purchase/success/`, `billing/purchase/cancel/`, `billing/subscription/success/`, `billing/subscription/cancel/`, `billing/portal/return/` | Public (no session) |
| `billing/webhooks/stripe/` | Stripe signature (rule 26) |

### Credits-first domain contract

- `Plan` stores QuickScale-owned display metadata plus the authoritative Stripe Price reference
  used for checkout validation.
- `CreditBalance` tracks the current authoritative per-organization credit balance; nullable
  user links remain provenance / compatibility only.
- `CreditTransaction` records each credit mutation with balance snapshots, optional Stripe
  reference metadata, and an optional caller-owned `reference` that makes a retried debit
  idempotent.
- `PurchaseCheckout` records one-time Checkout lifecycle state so account deletion and
  organization purge can reconcile or refuse live provider sessions; Stripe metadata and
  idempotency keys correlate completed or expired sessions even when the provider-create
  response is lost. A repeated purchase request returns the organization's still-payable
  checkout URL from its open reservation instead of creating a second payable session.
- `Subscription` stores the local snapshot of recurring billing state keyed authoritatively to
  the organization; recurring Checkout uses the same reservation-reference and response-loss
  recovery contract, while nullable user links remain provenance / compatibility only.
- `WebhookEvent` is the transport-level idempotency gate for Stripe webhook processing.
- `debit_user` is the approved service API for credit consumption; pass a `reference` to make a
  retried debit return its original transaction instead of debiting twice. Both it and
  `credit_user` enter the organization's tenant scope themselves, so a shell, management command,
  or worker can call them without a request context.

### Account-deletion capability

`QuickscaleBillingConfig` declares billing's account-deletion handler through the Module
Conventions rule 4 `account_deletion_handlers` capability: account deletion collects every
installed handler and drives billing-provenance discovery, Stripe purchase-checkout
reconciliation, subscription-checkout reconciliation for the organizations whose subscriptions
the deletion cancels, cancellation with compensation, and provider mutation locking through it,
so no consumer imports billing's services or names its label. The retained account keeps
billing records attributed to it, so the handler no longer nulls billing's user provenance.

### Plan-feature gate

`require_org_feature(feature_key)` is the published gate for API views. It resolves the
organization through `quickscale_modules_orgs.permissions.resolve_request_org` and reads
billing's own active `Subscription` row, so orgs and other consumers do not name a higher-layer
module. An anonymous caller raises `401`; an authenticated caller with no organization context,
no active subscription, or a plan that does not list the feature raises `402` with the stable
`feature_not_available` code. The one QuickScale exception handler renders both in the shared
`{"error": {"code", "message"}}` shape. Wrap a function-based API view with `@api_view`
outermost, so the raise happens inside DRF's dispatch; a plain Django view would let the exception
reach Django's handler instead.

### Organization pricing handoff

`organization_pricing_page_url(organization)` answers billing's public `billing/pricing/` page.
`QuickscaleBillingConfig` declares it through the Module Conventions rule 4
`organization_pricing_url_hooks` capability, which the orgs create flow collects for its
post-create handoff after activating the new organization; a switched-off billing declares
nothing, so orgs keeps its organization-dashboard fallback. An enabled billing whose pricing
route is not mounted raises `BillingConfigurationError` rather than answering a false negative.

### API contract

All billing API routes are flat (`billing/api/...`) and used in both Solo and SaaS modes. The
organization is resolved from the session / `request.org` contract established by middleware,
not from a URL slug. Every error answers the shared
`{"error": {"code", "message", "fields"}}` shape (`fields` only for validation errors), and a
disabled billing runtime answers `404`. List endpoints page by `page`; a page past the end
answers the empty list, so a client can follow pages until one is empty.

| Route | Method | Auth | Request | Success contract | Notes |
| --- | --- | --- | --- | --- | --- |
| `billing/api/config/` | `GET` | Session auth | None | `{"publishable_key": "pk_test_..."}` | Returns only the publishable key. Returns `500` with `{"error": {"code": "configuration_error", "message": "Stripe publishable key is not configured in the runtime settings."}}` when missing. |
| `billing/api/plans/` | `GET` | Public | `page` query param only | `[{"name": "Starter Monthly", "slug": "starter-monthly", "credits_per_period": 100, "price_cents": 1900, "currency": "usd", "billing_interval": "monthly"}]` | Returns active recurring plans only. One-time plans stay out of this catalog. Pages by `QUICKSCALE_BILLING_PLANS_PER_PAGE`; client `page_size` overrides are ignored. |
| `billing/api/balance/` | `GET` | Session auth | None | `{"balance": 0, "updated_at": null}` | A missing balance is returned as a read-only zero snapshot without creating a row. Persisted balances include their `updated_at` timestamp. |
| `billing/api/transactions/?page=2` | `GET` | Session auth | `page` query param only | `[{"id": 42, "amount": 125, "transaction_type": "purchase", "description": "Current user purchase", "balance_after": 125, "created_at": "2026-05-16T12:00:00Z"}]` | Ordered newest-first. Page size from `QUICKSCALE_BILLING_TRANSACTIONS_PER_PAGE` (default `25`); client `page_size` overrides are ignored. |
| `billing/api/purchase/checkout/` | `POST` | Session auth + CSRF | `{"plan_slug": "credits-pack"}` | `{"checkout_url": "https://checkout.stripe.com/..."}` | Rejects caller-supplied `success_url` and `cancel_url`. |
| `billing/api/subscription/` | `GET` | Session auth | None | `{"plan": {...}, "status": "active", "checkout_expires_at": null, "current_period_start": "...", "current_period_end": "..."}` | Returns `404` with `{"error": {"code": "not_found", "message": "Current subscription not found."}}` when no current recurring row exists. |
| `billing/api/subscription/checkout/` | `POST` | Session auth + CSRF | `{"plan_slug": "starter-monthly"}` | `{"checkout_url": "https://checkout.stripe.com/..."}` | Rejects caller-supplied `success_url` and `cancel_url`. Blocks if a current recurring subscription already exists. |
| `billing/api/subscription/cancel/` | `POST` | Session auth + CSRF | `{}` | `204 No Content` | Rejects caller-supplied `return_url`. Schedules `cancel_at_period_end=True`. |
| `billing/api/portal/` | `POST` | Session auth + CSRF | `{}` | `{"portal_url": "https://billing.stripe.com/..."}` | Rejects caller-supplied `return_url`. Uses the module-owned `billing/portal/return/` route. |

### Module-owned billing pages

The module ships Django pages that you can either use directly or treat as mount points for
your React frontend. All billing routes are flat in both Solo and SaaS modes:

- `GET billing/dashboard/` renders the authenticated billing page with
  `<div id="billing-root" data-view="dashboard">`.
- `GET billing/pricing/` renders the pricing page with `<div id="billing-root" data-view="pricing">`.
- `GET billing/purchase/success/` and `GET billing/purchase/cancel/` render purchase return
  pages.
- `GET billing/subscription/success/` and `GET billing/subscription/cancel/` render subscription
  return pages.
- `GET billing/portal/return/` renders the Stripe billing-portal return page.

### React integration guide

This module documents how to wire billing into a generated React frontend without asking
QuickScale to mutate user-owned frontend files. The module ships Django mount points and JSON
APIs; your React app owns how those APIs are consumed.

Integration assumptions:

- Use Django session authentication for authenticated billing routes.
- Send CSRF tokens on all authenticated `POST` requests.
- Treat the backend as the source of truth for redirect targets. Only send `plan_slug` for
  checkout creation and an empty JSON body for cancel and portal creation.
- Keep one-time purchase catalog data project-owned for now. The shipped `plans` endpoint only
  exposes active recurring plans.
- Treat transaction pagination as page-number based pagination sized by
  `QUICKSCALE_BILLING_TRANSACTIONS_PER_PAGE`; the API ignores client-supplied `page_size` values.
  Expose that value to Vite as `VITE_QUICKSCALE_BILLING_TRANSACTIONS_PER_PAGE` (the
  TransactionHistory example reads it, defaulting to `25`) so pager end detection matches the
  backend.

Worked TypeScript examples (fetch wrapper, CSRF helper, Stripe bootstrap and the CreditBalance,
PricingPage, PurchaseButton, SubscriptionStatus and TransactionHistory components):
[docs/react-integration.md](https://github.com/Experto-AI/quickscale/blob/main/quickscale_modules/billing/docs/react-integration.md).

## URLs

`quickscale apply` mounts the module at `billing/` (its manifest `url_includes` entry); the
module's paths are:

| URL name | Path | Purpose |
|----------|------|---------|
| `quickscale_billing:config` | `billing/api/config/` | Publishable-key discovery |
| `quickscale_billing:subscription_plans` | `billing/api/plans/` | Active recurring plan catalog |
| `quickscale_billing:credit_balance` | `billing/api/balance/` | Credit balance |
| `quickscale_billing:credit_transactions` | `billing/api/transactions/` | Credit transactions (paged) |
| `quickscale_billing:purchase_checkout` | `billing/api/purchase/checkout/` | One-time purchase Checkout |
| `quickscale_billing:subscription_detail` | `billing/api/subscription/` | Current subscription |
| `quickscale_billing:subscription_checkout` | `billing/api/subscription/checkout/` | Recurring Checkout |
| `quickscale_billing:subscription_cancel_current` | `billing/api/subscription/cancel/` | Schedule period-end cancellation |
| `quickscale_billing:portal_session` | `billing/api/portal/` | Stripe billing portal session |
| `quickscale_billing:dashboard` | `billing/dashboard/` | Billing dashboard page |
| `quickscale_billing:pricing_page` | `billing/pricing/` | Pricing page |
| `quickscale_billing:purchase_success` | `billing/purchase/success/` | Purchase return (success) |
| `quickscale_billing:purchase_cancel` | `billing/purchase/cancel/` | Purchase return (cancel) |
| `quickscale_billing:subscription_success` | `billing/subscription/success/` | Subscription return (success) |
| `quickscale_billing:subscription_cancel` | `billing/subscription/cancel/` | Subscription return (cancel) |
| `quickscale_billing:portal_return` | `billing/portal/return/` | Billing portal return |
| `quickscale_billing:stripe_webhook` | `billing/webhooks/stripe/` | Stripe webhook endpoint |

## Management commands

`quickscale_billing_reconcile_checkouts` resolves checkout reservations whose
Stripe creation outcome is unknown — rows left by a provider rejection recorded
before this contract, or by a response lost in transit — before account
deletion or organization purge. Each outstanding purchase and subscription
reservation is resolved against Stripe under the organization's provider
mutation mutex: a session-bearing row is retrieved by its session id, and a
session-less row is looked up by its stored reservation reference. A
provider-confirmed expired session and a session Stripe does not hold are both
closed, and a live session is adopted so the existing refusal guard reports
provider truth. Reconciliation must not add provider state, so the absent
verdict waits out Stripe's Search indexing lag: because Search is eventually
consistent (Stripe documents data as searchable in less than a minute, and up
to an hour behind during outages), a customer-search miss is trusted as
absence only once the organization's latest customer-resolution attempt
completed and is older than that lag; while the window is open, and while an
attempt has no recorded outcome, the reservation stays open. A reference that
resolves to more than one customer fails closed instead of binding the first.
The command reports every organization it cannot clear.

```bash
python manage.py quickscale_billing_reconcile_checkouts
python manage.py quickscale_billing_reconcile_checkouts --organization-id <org-uuid> --dry-run
```

## Operations

### Stripe API version contract

Billing targets the Stripe API version `2026-06-24.dahlia` — the version the pinned `stripe`
SDK (`>=15.3.1,<16.0.0`) ships. The runtime sets that version on the SDK before every call,
and every webhook event must report the same named release: `handle_stripe_event` rejects an
event from a different named release with `BillingConfigurationError`, which the webhook view
answers with `500` so Stripe retries, and it logs each event's reported version.

The Stripe webhook endpoint for this module **must** use API version `2026-06-24.dahlia` and
point at `/billing/webhooks/stripe/`.

Delayed-notification payment methods (SEPA, ACH, Bacs, bank transfer) are supported: a
`checkout.session.completed` whose `payment_status` is `unpaid` binds the purchase reservation
without crediting it, `checkout.session.async_payment_succeeded` credits the one-time purchase
exactly once, and `checkout.session.async_payment_failed` releases the reservation so it no
longer blocks account deletion or organization purge.

An `invoice.payment_failed` event applies only to `subscription_create` or `subscription_cycle`
invoices that name a subscription; an unrelated failed invoice for the same customer is recorded
and ignored. An `invoice.paid` for a plan that grants zero credits activates the subscription
without writing a zero-amount ledger entry, so the event is not retried.

**Upgrade note:** a deployment whose webhook endpoint is on an older API version stops
processing all billing webhooks (`500`s) until the endpoint is recreated at
`2026-06-24.dahlia`. Events refused under the old version are not credited automatically, so
reconcile them once the endpoint is on `2026-06-24.dahlia`: resend the event to that endpoint
(Stripe Dashboard **Resend**, or `stripe events resend <event_id> --webhook-endpoint=<new_endpoint_id>`,
up to 30 days) and confirm it is accepted; when an event is still refused or is outside the
resend window, credit the affected invoice once through the module's `credit_user` service from
a Django shell so the balance and ledger stay consistent.

### Deployment notes

Billing ships through the standard QuickScale module packaging and split-branch workflow. The
module manifest declares `required_modules: [orgs]` for planner/apply dependency enforcement.
Follow-on roadmap work may tighten release evidence or adjacent docs; the module contract above
is the current shipped surface.

## Extending

### What QuickScale owns

The module package under `modules/billing/` — models, migrations, admin, JSON APIs, Django
pages, webhook handling, and services — its manifest options, and the managed wiring
`quickscale apply` writes (`<package>/settings/modules.py`, `<package>/urls_modules.py`).

### What the project owns

`quickscale.yml` values for the options above, the Stripe account's catalog and webhook
endpoint, deployment secrets, the project's frontend and React integration, and all
project-owned apps and data.

### Update-safe customizations

Change option values, consume the JSON APIs from project-owned frontend code, and adopt the
module's Django pages or treat them as mount points; QuickScale never rewrites user-owned
frontend files. Project code calls the documented service API instead of reaching into module
internals.

### Structured extension points

`debit_user` is the approved service API for credit consumption; its `reference` argument makes a
retried call return the original transaction. The module also publishes `credit_user`,
`handle_stripe_event`, and the reconciliation helpers in `services.py`.
`require_org_feature(feature_key)` is the published plan-feature gate, and the module declares
the `account_deletion_handlers` and `organization_pricing_url_hooks` capabilities that auth and
orgs collect. Stripe catalog authoring, coupons, tax/VAT, metered billing, seat billing, and
custom invoice-history UI are explicit non-goals of the current contract.

### Upgrade expectations

Tier 1 settings, documented services, capabilities, and the webhook contract survive normal
module updates; a Stripe API-version change is called out in the release note and the module's
webhook section. Never edit `modules/billing/`: `quickscale update` refuses a local edit unless
`--allow-local-changes`, and managed wiring is regenerated.

Related documentation: [technical roadmap](../../docs/technical/roadmap.md) for active billing
work.
