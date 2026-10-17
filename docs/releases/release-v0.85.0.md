# Release v0.85.0 - Billing Module

**Date:** 2026-05-18 · **Status:** ✅ Released

## Summary

v0.85.0 delivers the QuickScale billing milestone. Billing is now a first-class QuickScale module instead of placeholder-only inventory: Stripe-backed one-time purchases and recurring subscriptions feed a Django-owned credit ledger, planner and apply flows recognize billing as a supported module with auth-aware validation, and generated starter output links users into module-owned billing pages instead of pretending billing is a starter-owned SPA surface.

## Highlights

### Features

- **Credits-first billing module**: QuickScale now ships billing as a module that owns plans, balances, transactions, subscriptions, and webhook-event replay protection while using Stripe as the payment trigger rather than the source of truth for credits.
- **Planner and apply readiness**: Billing now participates in public `quickscale plan`, `quickscale.yml`, and `quickscale apply` flows with contract validation for Stripe env-var references, billing currency, and the required auth-module dependency.
- **Module-owned billing pages**: The shipped billing surface includes module-owned `/billing/pricing/` and `/billing/dashboard/` pages plus return routes for purchase, subscription, and portal flows, which gives adopters working defaults without requiring a starter-owned billing SPA.

### Improvements

- **Starter-theme integration parity**: Fresh React and HTML starter output now link into the billing module's Django-owned routes with auth-aware navigation instead of hiding billing behind placeholder-only inventory.
- **Public adoption guidance**: The billing module README and related technical docs now describe the shipped contract, including Stripe-hosted checkout and portal flows plus optional React integration patterns layered on top of the module APIs.

## Breaking changes

- Billing is no longer placeholder-only in public planner/apply flows; repositories and generated projects should now treat it as a shipped QuickScale module.
- Billing hard-requires the QuickScale auth module at apply time and expects Stripe secrets to be resolved from environment variables rather than stored in the database.
- The shipped billing routes are Django-owned (`/billing/pricing/` and `/billing/dashboard/`), so adopters should treat those routes as the default module entrypoints instead of assuming a starter-owned `/billing` SPA route.

## Upgrade steps

1. Add the billing module alongside auth in `quickscale.yml`, then configure the Stripe publishable key, secret key, webhook secret, and billing currency through the documented env-var reference settings.
2. Ensure the Stripe dashboard catalog is ready before go-live and keep local plan display metadata aligned with the authoritative Stripe Price configuration used for checkout.
3. Adopt the shipped Django billing pages as the default entrypoints first, then layer optional React UI components on top of the published billing APIs if your project needs a custom frontend.
