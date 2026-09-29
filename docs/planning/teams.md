# Teams Module (Unscheduled)

Preserved planning note for a future `teams` module. The former README-only
placeholder directory under `quickscale_modules/` has been deleted; no teams
implementation or schedule is committed, and nothing here is selectable in
QuickScale flows.

## Illustrative future capabilities

If the module is scheduled, its design may include:

- **Multi-tenancy patterns** — User → Team → Resources relationship models
- **Role-based permissions** — Owner, Admin, Member roles with customizable permissions
- **Invitation system** — Email-based team invitations with secure tokens
- **Row-level security** — Query filters for data isolation between teams
- **Team management UI** — Dashboard, member management, settings
- **Theme integration** — Compatibility with the sole supported React starter

## Current contract

- Not a shipped module selection for public plan/config/apply/update workflows
- No public split-branch/update contract until the implementation ships

## Distribution contract if implemented

If teams ships, it must use the same maintainer-driven **git subtree** release
contract as the twelve current modules:

- **Main branch**: `quickscale_modules/teams/` (development)
- **Mutable producer branch**: `splits/teams-module`, published by maintainer tooling under an exact-SHA lease
- **Immutable consumer tag**: `splits/teams-module/<version>`, sealed before default embed/update use
- **Project configuration flow**: `quickscale plan myapp --add teams` followed by `quickscale apply`
- **Updates**: `quickscale update`

Do not publish a teams split branch or tag before the module ships; the existing
remote `splits/teams-module` is stale external state owned by roadmap `SA117e-4`.

## Related modules

- **auth**: Authentication and account management support
- **billing**: Billing and subscription support

## Documentation

For module management commands and workflows, see:

- [User Manual](../technical/user_manual.md)
- [Technical Roadmap](../technical/roadmap.md)
- [Decisions Document](../technical/decisions.md)
