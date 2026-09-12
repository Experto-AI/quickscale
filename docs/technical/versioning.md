# Versioning (single-source)

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Versioning**
> **Related docs**: [Publish procedure](publish_procedure.md) | [Decisions](decisions.md#module-version-lockstep)

This document owns one thing: how a version number is declared and propagated. **Releasing and
publishing are owned by [publish_procedure.md](publish_procedure.md)** — follow that document for
the ordered phases, the quality gate, and the irreversibility boundary. Do not tag or publish from
this page.

## Single source of truth

The repository root `VERSION` file is authoritative. Every package version, module manifest version,
inter-package constraint, and embedded `_version.py` is derived from it. Modules are versioned in
lockstep with the repository; see
[decisions.md §Module Version Lockstep](decisions.md#module-version-lockstep).

## Propagating a version

```bash
make bump-version X.Y.Z      # writes VERSION, then runs the update below
```

Or, equivalently, edit `VERSION` and propagate by hand:

```bash
./scripts/version_tool.sh update
./scripts/version_tool.sh check      # or: make version-check
```

`update` rewrites:

- every `quickscale*/pyproject.toml` version, including maintainer-only parity members
- inter-package dependency constraints (e.g. `quickscale-core = "^X.Y.Z"`)
- embedded `_version.py` files for core and CLI
- each `quickscale_modules/*/module.yml` version, its package version and `__init__.py`, and the
  matching core manifest snapshot
- `version:` fields in standalone documentation `.yml`/`.yaml` files

## What the tool does not derive

These are hand-maintained and drift silently if forgotten at release time. The publish quality check
covers them: [publish_procedure.md §1.1](publish_procedure.md#11-version-and-manifest-integrity).

- each module's `quickscale-core>=X.Y.Z,<X.Y+1.0` requirement in `module.yml`, plus its core snapshot
- version literals inside test fixtures and assertions
- `contract_vintage.minimum`, which is an adoption boundary rather than a lockstep field

> **Updater scope**: Only standalone `.yml`/`.yaml` files are version-tool candidates. Version fields
> inside Markdown fenced code-block examples are **never** modified by the tool — those examples are
> human-authored and must be updated manually when the schema version changes. If a standalone YAML
> file and a Markdown example both carry a version field, update both separately.

## Local install for testing

```bash
./scripts/install_global.sh      # or: make install
quickscale --version
```

This builds the distributions and stages a local wheelhouse next to the install, so an unpublished
version resolves its own wheels instead of pinning a PyPI version that does not exist yet.
