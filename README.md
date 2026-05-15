# QuickScale Billing Module (Placeholder Directory)

**Status**: 🚧 Placeholder Only - Not Selectable in Public QuickScale Flows

This directory reserves the billing module namespace and captures intended scope. It is discoverable in repository inventory and docs, but `quickscale plan`, `quickscale.yml` validation, and `quickscale apply` reject `billing` until the module is actually implemented and released.

## Planned capabilities

The full billing module is expected to include:

- **Direct Stripe SDK integration** - Thin adapter around Stripe rather than a full ORM mirror
- **Credits ledger** - Django-owned balances and transactions with Stripe as the payment trigger
- **One-time purchases and subscriptions** - Checkout-session flows that credit users on payment success
- **Webhook handling** - Signed, idempotent Stripe webhook processing that tolerates duplicate delivery and out-of-order events
- **Stripe-hosted self-service** - Customer-portal session support for payment-method recovery and subscription management
- **Module-owned billing pages** - Django routes/templates plus manual React adoption guidance for project-owned frontends

## Current Contract

- Discoverable in docs and maintainer inventory only
- Not a shipped module selection for public plan/config/apply workflows
- No public split-branch/update contract until the implementation ships

## Planned Distribution Once Implemented

When billing is implemented, it is expected to use **git subtree** distribution via split branches:

- **Main branch**: `quickscale_modules/billing/` (development)
- **Split branch**: `splits/billing-module` (distribution)
- **Project configuration flow**: `quickscale plan myapp --add billing` followed by `quickscale apply`
- **Updates**: `quickscale update`

## For Developers

If you're contributing to this placeholder directory:

1. Develop in `quickscale_modules/billing/` on the main branch
2. Commit changes normally
3. On release, GitHub Actions auto-splits to `splits/billing-module`
4. Public plan/apply/update flows remain blocked until the module ships

## Related Modules

- **auth**: Authentication and account management support
- **teams**: Multi-tenancy and team management support

## Documentation

For module management commands and workflows, see:
- [User Manual](../../docs/technical/user_manual.md)
- [Technical Roadmap](../../docs/technical/roadmap.md)
- [Decisions Document](../../docs/technical/decisions.md)

The authoritative implementation plan for v0.85.0 lives in [docs/technical/roadmap.md](../../docs/technical/roadmap.md). Until that milestone ships, this README remains a placeholder contract only.

---

**Note**: This README documents a placeholder directory only. It will be replaced with full public module documentation once billing is implemented and selectable.
