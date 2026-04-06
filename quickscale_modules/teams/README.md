# QuickScale Teams Module (Placeholder Directory)

**Status**: 🚧 Placeholder Only - Not Selectable in Public QuickScale Flows

This directory reserves the teams module namespace and captures intended scope. It is discoverable in repository inventory and docs, but `quickscale plan`, `quickscale.yml` validation, and `quickscale apply` reject `teams` until the module is actually implemented and released.

## Planned capabilities

The full teams module is expected to include:

- **Multi-tenancy patterns** - User → Team → Resources relationship models
- **Role-based permissions** - Owner, Admin, Member roles with customizable permissions
- **Invitation system** - Email-based team invitations with secure tokens
- **Row-level security** - Query filters for data isolation between teams
- **Team management UI** - Dashboard, member management, settings
- **Theme support** - HTML and React theme variants

## Current Contract

- Discoverable in docs and maintainer inventory only
- Not a shipped module selection for public plan/config/apply workflows
- No public split-branch/update contract until the implementation ships

## Planned Distribution Once Implemented

When teams is implemented, it is expected to use **git subtree** distribution via split branches:

- **Main branch**: `quickscale_modules/teams/` (development)
- **Split branch**: `splits/teams-module` (distribution)
- **Project configuration flow**: `quickscale plan myapp --add teams` followed by `quickscale apply`
- **Updates**: `quickscale update`

## For Developers

If you're contributing to this placeholder directory:

1. Develop in `quickscale_modules/teams/` on the main branch
2. Commit changes normally
3. On release, GitHub Actions auto-splits to `splits/teams-module`
4. Public plan/apply/update flows remain blocked until the module ships

## Related Modules

- **auth**: Authentication and account management support
- **billing**: Billing and subscription support

## Documentation

For module management commands and workflows, see:
- [User Manual](../../docs/technical/user_manual.md)
- [Technical Roadmap](../../docs/technical/roadmap.md)
- [Decisions Document](../../docs/technical/decisions.md)

---

**Note**: This README documents a placeholder directory only. It will be replaced with full public module documentation once teams is implemented and selectable.
