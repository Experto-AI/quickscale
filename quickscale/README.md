# quickscale

Meta-package for QuickScale.

This package exists to install `quickscale-core` and `quickscale-cli` together so end users can get the standard QuickScale toolchain with a single dependency.

## What this package does

- Declares the combined dependency bundle in this package's `pyproject.toml`
- Ships a minimal import package at `quickscale`
- Provides the easiest install target for most users

## Install

```bash
pip install quickscale
```

Or with Poetry:

```bash
poetry add quickscale
```

## After installation

```bash
quickscale plan myapp
cd myapp
quickscale apply
```

## Related packages

- [quickscale-cli README](https://github.com/Experto-AI/quickscale/blob/main/quickscale_cli/README.md) - CLI commands and workflow surface
- [quickscale-core README](https://github.com/Experto-AI/quickscale/blob/main/quickscale_core/README.md) - scaffolding engine and templates

## Documentation

- Repository overview: [QuickScale README](https://github.com/Experto-AI/quickscale/blob/main/README.md)
- Technical decisions: [docs/technical/decisions.md](https://github.com/Experto-AI/quickscale/blob/main/docs/technical/decisions.md)
- Start guide: [START_HERE.md](https://github.com/Experto-AI/quickscale/blob/main/START_HERE.md)

This README is package-local context only. Root documentation remains authoritative for repo-wide behavior and policy.
