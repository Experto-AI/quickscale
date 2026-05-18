# Release v0.85.0 - Billing Module

**Prepared Date:** 2026-05-18
**Status:** Prepared release artifact; official publication pending

This document is the single public note prepared for v0.85.0. It records the release surface and the completed non-publish validation evidence without claiming that the tag or GitHub release already exists.

## Summary

v0.85.0 prepares the QuickScale billing milestone for publication. Billing is now a real QuickScale module instead of placeholder-only inventory: Stripe-backed one-time purchases and recurring subscriptions feed a Django-owned credit ledger, planner and apply flows recognize billing as a supported module with auth-aware validation, and generated starter output links users into module-owned billing pages instead of pretending billing is a starter-owned SPA surface.

This note intentionally reflects a release-prepared state rather than a published-release claim. The repo-level non-publish gates are green, the release-history surfaces are aligned, and official publication is still pending.

**Related docs:** [Changelog](../../CHANGELOG.md) | [Roadmap](../technical/roadmap.md) | [Technical Decisions](../technical/decisions.md) | [User Manual](../technical/user_manual.md)

## Highlights

- Billing now ships as a first-class QuickScale module with Stripe-backed purchases, subscriptions, portal workflows, and a Django-owned credit ledger.
- Public planner/apply flows and fresh starter output now surface billing as a supported module with module-owned pricing and dashboard routes.
- The v0.85.0 public note is prepared with green non-publish validation evidence and a clear pending-publication status.

## What's New

### Features

- **Credits-first billing module**: QuickScale now ships billing as a module that owns plans, balances, transactions, subscriptions, and webhook-event replay protection while using Stripe as the payment trigger rather than the source of truth for credits.
- **Planner and apply readiness**: Billing now participates in public `quickscale plan`, `quickscale.yml`, and `quickscale apply` flows with contract validation for Stripe env-var references, billing currency, and the required auth-module dependency.
- **Module-owned billing pages**: The shipped billing surface includes module-owned `/billing/pricing/` and `/billing/dashboard/` pages plus return routes for purchase, subscription, and portal flows, which gives adopters working defaults without requiring a starter-owned billing SPA.

### Improvements

- **Starter-theme integration parity**: Fresh React and HTML starter output now link into the billing module's Django-owned routes with auth-aware navigation instead of hiding billing behind placeholder-only inventory.
- **Release-history closeout**: The roadmap, changelog, and this release artifact now line up on a single truthful state for v0.85.0: release-prepared with green quality gates, but not yet manually published.
- **Public adoption guidance**: The billing module README and related technical docs now describe the shipped contract, including Stripe-hosted checkout and portal flows plus optional React integration patterns layered on top of the module APIs.

## Breaking Changes

- Billing is no longer placeholder-only in public planner/apply flows; repositories and generated projects should now treat it as a shipped QuickScale module.
- Billing hard-requires the QuickScale auth module at apply time and expects Stripe secrets to be resolved from environment variables rather than stored in the database.
- The shipped billing routes are Django-owned (`/billing/pricing/` and `/billing/dashboard/`), so adopters should treat those routes as the default module entrypoints instead of assuming a starter-owned `/billing` SPA route.

## Migration Guide

1. Add the billing module alongside auth in `quickscale.yml`, then configure the Stripe publishable key, secret key, webhook secret, and billing currency through the documented env-var reference settings.
2. Ensure the Stripe dashboard catalog is ready before go-live and keep local plan display metadata aligned with the authoritative Stripe Price configuration used for checkout.
3. Adopt the shipped Django billing pages as the default entrypoints first, then layer optional React UI components on top of the published billing APIs if your project needs a custom frontend.

## Validation

- `make lint` passed in the release-prep closeout.
- `make typecheck` passed in the release-prep closeout.
- `make test` passed in the release-prep closeout with overall mean coverage 93.43%, billing coverage 90.35%, and forms coverage 96.04%.
- `make version-check` passed, including v0.85.0 parity for `quickscale`, `quickscale_core`, and `quickscale_cli`, plus direct billing module version verification.
- `make ci-e2e` passed in the release-prep closeout.

## Validation Commands

```bash
make lint
make typecheck
make test
make version-check
make ci-e2e
```

## Deferred Follow-up

- None.
