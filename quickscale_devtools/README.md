# quickscale-devtools

Maintainer-only development tools for QuickScale.

This package hosts tooling used by QuickScale maintainers that is intentionally
decoupled from the user-facing CLI and the public scaffolding surface. It
depends only on `quickscale-core` and never imports from `quickscale-cli`.

## Contents

- `quickscale_devtools.beta_migration` — Maintainer helper for fresh-first
  execution and in-place migration flows between QuickScale project layouts.

## Entry Point

This package does not expose console scripts. Maintainers invoke the
maintainer tooling through the wrapper at `scripts/beta_migrate.py`, which
imports the relevant entry point and runs it as a script.
