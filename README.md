# QuickScale Billing Module

**Status**: Phase 1 foundation is implemented in-repo. Billing is still **not** publicly ready in `quickscale plan`, `quickscale.yml` validation, or `quickscale apply`.

QuickScale billing is a credits-first module. Django owns plans, balances, transactions, subscription snapshots, and webhook idempotency records. When later runtime phases land, the module will use the direct `stripe` Python SDK rather than `dj-stripe`; Stripe is the payment trigger, while the Django ledger remains the source of truth for credit accounting.

## What Ships In Phase 1

- Independently packaged Django module metadata under `quickscale_modules/billing/`
- Five core Django models: `Plan`, `CreditBalance`, `CreditTransaction`, `Subscription`, and `WebhookEvent`
- Django admin registration with read-only operational views for balances, transactions, and webhook events
- Handwritten initial migration and a package-local pytest harness
- Manifest/config scaffolding for later planner/apply integration

## Current Shipping Contract

- Billing remains hidden from public planner and apply flows until later roadmap phases land
- This phase intentionally adds no `stripe` dependency and no Stripe runtime imports
- No services, webhook views, serializers, URLs, or generated-project runtime wiring ship in Phase 1
- Version metadata is aligned across `module.yml`, `pyproject.toml`, and `__version__`

## Credits-First Domain Contract

- `Plan` stores QuickScale-owned display metadata plus the authoritative Stripe price reference used later for checkout
- `CreditBalance` tracks the current per-user credit balance
- `CreditTransaction` records each credit mutation with balance snapshots and optional Stripe reference metadata
- `Subscription` stores the local snapshot of recurring billing state
- `WebhookEvent` is the transport-level idempotency gate for future Stripe webhook processing

## Explicit Non-Goals For v0.85.0

- No Stripe catalog authoring from Django admin
- No coupons, tax/VAT workflows, metered billing, seat billing, or custom invoice-history UI
- No teams-aware shared balances
- No rewrites of user-owned frontend files

## Distribution And Release Gating

Billing will ship through the standard QuickScale module packaging and split-branch workflow once later phases complete. Until then, maintainers can develop the package in-repo, but public QuickScale flows must continue to treat billing as not yet ready.

See [Technical Roadmap](../../docs/technical/roadmap.md) for the full v0.85.0 implementation plan.
