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

## Publishing Contract (Maintainer-Only)

`quickscale-devtools` is **intentionally excluded** from the public
`scripts/publish.sh` / `scripts/prepare_publish.py` release flow. The
coordinated public release ships only:

- `quickscale-core`
- `quickscale-cli`
- `quickscale`

This package is consumed directly from the monorepo (`poetry install`
from the repository root adds it as a path dependency on
`quickscale-core`) and is **not** intended for end-user distribution.

### Why it is excluded

- The contents are maintainer-side migration and rework helpers, not
  user-facing scaffolding primitives; shipping it to PyPI would imply
  stability guarantees that the project does not make for this surface.
- Adding it to `scripts/publish.sh PACKAGES` and to
  `scripts/prepare_publish.py DEFAULT_PACKAGES` would also require
  teaching `PATH_DEPENDENCY_REWRITES` how to rewrite its
  `quickscale-core` path dependency for a one-off publish, which adds
  ongoing maintenance cost to the release flow for a package that
  does not need it.
- The current `pyproject.toml` keeps `[project].dynamic = ["dependencies"]`
  in lock-step with `[tool.poetry.dependencies]`; that layout is designed
  for in-repo consumption, not for repeated publish-time rewriting.

### One-off distribution (if ever needed)

If a maintainer ever needs to distribute `quickscale-devtools` separately
from a coordinated release (for example, sharing a build with another
maintainer for review, or for an isolated security backport), do **not**
fold it into the coordinated `scripts/publish.sh` flow. Instead, publish
it directly from the package directory, out of band:

```bash
# From the repository root.
cd quickscale_devtools
# Resolve the path-based quickscale-core dep to a version constraint
# before building, mirroring the rewrite that scripts/prepare_publish.py
# performs for the public packages.
poetry build
# Then publish directly, choosing the same PyPI/TestPyPI credentials as
# the public flow. Confirm the dist/ output looks sane and that the
# resulting wheel's METADATA lists the expected quickscale-core version.
poetry publish            # production PyPI
poetry publish -r testpypi  # TestPyPI first, if verifying
```

When doing this:

- Coordinate the version with the current `VERSION` file so a one-off
  distribution cannot collide with a coordinated release.
- Note the one-off distribution in the next public release note
  (`docs/releases/release-vX.XX.X.md`) and in the release PR so the
  history is complete.
- If the one-off distribution becomes a recurring need, promote it to
  the coordinated flow by adding the package to
  `scripts/publish.sh PACKAGES` and
  `scripts/prepare_publish.py DEFAULT_PACKAGES`, and adding the matching
  entry to `PATH_DEPENDENCY_REWRITES`. Update this README and the inline
  comment in `quickscale_devtools/pyproject.toml` at the same time so
  the documentation does not drift.
