# QuickScale Billing Module (Placeholder Directory)

**Status**: 🚧 Placeholder Only - Not Selectable in Public QuickScale Flows

This directory reserves the billing module namespace and captures intended scope. It is discoverable in repository inventory and docs, but `quickscale plan`, `quickscale.yml` validation, and `quickscale apply` reject `billing` until the module is actually implemented and released.

## Planned capabilities

The full billing module is expected to include:

- **dj-stripe integration** - Complete Stripe subscription management
- **Subscription plans** - Flexible pricing tiers and trial periods
- **Webhook handling** - Secure Stripe webhook processing with logging
- **Invoice management** - Customer billing history and invoice generation
- **Payment methods** - Credit card and payment method management
- **Theme support** - HTML and React theme variants

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

---

**Note**: This README documents a placeholder directory only. It will be replaced with full public module documentation once billing is implemented and selectable.
