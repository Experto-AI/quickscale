# QuickScale Auth Module (Placeholder)

**Status**: 🚧 Infrastructure Ready - Implementation Pending

This is a placeholder module for the QuickScale authentication module. The module infrastructure and distribution mechanism are ready, but the actual implementation is not yet complete.

## Coming in v0.63.0

The full authentication module will include:

- **django-allauth integration** - Social authentication providers (Google, GitHub, Facebook, etc.)
- **Custom User model patterns** - Extensible user model with best practices
- **Account management views** - Login, signup, password reset, email verification
- **Email verification workflows** - Production-ready email confirmation flows
- **Theme support** - HTML, HTMX, and React theme variants

## Module Distribution

This module uses **git subtree** distribution via split branches:

- **Main branch**: `quickscale_modules/auth/` (development)
- **Split branch**: `splits/auth-module` (distribution)
- **User embedding**: `quickscale embed --module auth`
- **Updates**: `quickscale update`

## For Developers

If you're contributing to this module:

1. Develop in `quickscale_modules/auth/` on the main branch
2. Commit changes normally
3. On release, GitHub Actions auto-splits to `splits/auth-module`
4. Users receive updates via `quickscale update`

## Related Modules

- **billing**: Stripe integration (placeholder in v0.62.0, full in v0.65.0)
- **teams**: Multi-tenancy and team management (placeholder in v0.62.0, full in v0.66.0)

## Documentation

For module management commands and workflows, see:
- [User Manual](../../docs/technical/user_manual.md)
- [Technical Roadmap](../../docs/technical/roadmap.md)
- [Decisions Document](../../docs/technical/decisions.md)

---

**Note**: This README will be replaced with full module documentation when implementation begins in v0.63.0.
