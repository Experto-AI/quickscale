# quickscale-core

Core scaffolding package for QuickScale.

This package contains the reusable project-generation logic, templates, configuration helpers, and wiring primitives used by the CLI.

## What lives here

- Project generator implementation under `src/quickscale_core/generator/`
- Shared templates bundled into published artifacts
- Configuration and settings helpers used during generation
- Manifest and module-wiring utilities shared across first-party workflows

## Relationship to other packages

- `quickscale-cli` provides the end-user command surface
- `quickscale-core` provides the scaffolding engine those commands call
- `quickscale` installs both packages together as the convenience meta-package

## Local development context

- Packaging metadata: [pyproject.toml](./pyproject.toml)
- Repository overview: [../README.md](../README.md)
- Authoritative technical policy: [../docs/technical/decisions.md](../docs/technical/decisions.md)
- Directory/layout reference: [../docs/technical/scaffolding.md](../docs/technical/scaffolding.md)

## Notes for maintainers

- Template changes in this package affect generated project output
- Published package artifacts must continue to include template files declared in [pyproject.toml](./pyproject.toml)
- This README is package-local context only; root documentation remains the source of truth for repo-wide policy
