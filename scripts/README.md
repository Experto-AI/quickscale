# scripts

Repository maintenance and workflow scripts for QuickScale.

Most scripts are intended to be run from the repository root so repo-relative paths and Poetry-managed commands resolve correctly. Prefer running shared workflows through the root [Makefile](../Makefile) first, and call `./scripts/<name>.sh` directly only when there is no matching `make` target or a script header says otherwise.

## Preferred entrypoint

Use the root Makefile as the default interface for setup, quality checks, tests, docs, publishing, and legacy helpers.

Preferred maintainer-facing command map:

| Script | Preferred command from repo root |
|---|---|
| `./scripts/bootstrap.sh` | `make bootstrap` |
| `./scripts/install_global.sh` | `make install` |
| `poetry run python scripts/beta_migrate.py fresh-first --donor /abs/path --recipient /abs/path` | `make beta-migrate-fresh DONOR=/abs/path RECIPIENT=/abs/path` |
| `poetry run python scripts/beta_migrate.py fresh-first --donor /abs/path --recipient /abs/path --dry-run --report-path /abs/path/report.json` | `make beta-migrate-fresh DONOR=/abs/path RECIPIENT=/abs/path DRY_RUN=1 REPORT=/abs/path/report.json` |
| `poetry run python scripts/beta_migrate.py in-place --donor /abs/path --recipient /abs/path --report-path /abs/path/report.json` | `make beta-migrate-in-place DONOR=/abs/path RECIPIENT=/abs/path REPORT=/abs/path/report.json` |
| `poetry run python scripts/beta_migrate.py in-place --donor /abs/path --recipient /abs/path --continue-after-checkpoint --report-path /abs/path/report.json` | `make beta-migrate-in-place DONOR=/abs/path RECIPIENT=/abs/path CONTINUE=1 REPORT=/abs/path/report.json` |
| `./scripts/quickscale_legacy_symlink.sh mount` | `make legacy-mount` |
| `./scripts/quickscale_legacy_symlink.sh unmount` | `make legacy-unmount` |
| `./scripts/quickscale_legacy_symlink.sh status` | `make legacy-status` |
| `./scripts/check_ci_locally.sh` | `make ci` or `make ci-e2e` |
| `./scripts/check_quality.sh` | `make quality` |
| `./scripts/lint.sh` | `make lint` and/or `make typecheck` |
| `./scripts/lint_agentic_flow.sh` | `make lint-agent` |
| `./scripts/lint_frontend.sh` | `make lint-frontend` |
| `./scripts/compile_docs.sh` | `make docs` |
| `./scripts/test_unit.sh` | `make test` or `make test-unit` |
| `./scripts/test_e2e.sh` | `make test-e2e` |
| `./scripts/test_agentic_flow.sh` | `make test-agent` |
| `./scripts/publish.sh build` | `make publish-build` |
| `./scripts/publish.sh test` | `make publish-test` |
| `./scripts/publish.sh prod` | `make publish-prod` |
| `./scripts/publish.sh full` | `make publish-full` |
| `./scripts/publish_module.sh <module>` | `make publish-module MODULE=<module>` |
| `./scripts/version_tool.sh check` | `make version-check` |
| `./scripts/version_tool.sh update` | `make version-update` after editing `VERSION`, or `make bump-version X.Y.Z` to update `VERSION` first |

If a script is part of a larger repo workflow, assume the Makefile is the preferred maintainer-facing entrypoint.

## Script groups

### Bootstrap and local setup

- [bootstrap.sh](./bootstrap.sh) — bootstraps the local development environment with Poetry (`make bootstrap`)
- [install_global.sh](./install_global.sh) — installs the global QuickScale command for local use (`make install`)
- [quickscale_legacy_symlink.sh](./quickscale_legacy_symlink.sh) — manages legacy compatibility symlinks (prefer `make legacy-mount`, `make legacy-unmount`, or `make legacy-status`)

### Beta-site maintainer workflows

- [beta_migrate.py](./beta_migrate.py) — maintainer-only beta-site migration helper. `make beta-migrate-fresh` mutates the throwaway recipient and runs the local verification stack by default; add `DRY_RUN=1` to emit the plan/report without mutation. `make beta-migrate-in-place` stays checkpoint-first by default, and `CONTINUE=1` opts into the deterministic in-place copy/apply/verification continuation path. Use `REPORT=/abs/path/report.json` to persist the JSON handoff file.

### Quality, validation, and docs maintenance

- [check_ci_locally.sh](./check_ci_locally.sh) — runs a local CI-style validation flow (prefer `make ci` or `make ci-e2e`)
- [check_quality.sh](./check_quality.sh) — runs broader code-quality analysis (prefer `make quality`)
- [lint.sh](./lint.sh) — runs Ruff and MyPy checks for Python packages (prefer `make lint` / `make typecheck`)
- [lint_agentic_flow.sh](./lint_agentic_flow.sh) — runs focused linting for agentic-flow work (`make lint-agent`)
- [lint_frontend.sh](./lint_frontend.sh) — validates the React theme frontend toolchain (`make lint-frontend`)
- [compile_docs.sh](./compile_docs.sh) — rebuilds the aggregated contributing guide from docs sources (`make docs`)

### Test runners

- [test_unit.sh](./test_unit.sh) — runs unit and integration tests (prefer `make test` or `make test-unit`)
- [test_e2e.sh](./test_e2e.sh) — runs local end-to-end tests and supporting setup (`make test-e2e`)
- [test_agentic_flow.sh](./test_agentic_flow.sh) — runs focused agentic-flow adapter tests (`make test-agent`)

### Release and distribution

- [publish.sh](./publish.sh) — builds and publishes packages (prefer `make publish-build`, `make publish-test`, `make publish-prod`, or `make publish-full`)
- [publish_module.sh](./publish_module.sh) — publishes module changes to split branches (`make publish-module MODULE=<name>`)
- [version_tool.sh](./version_tool.sh) — checks and synchronizes version metadata (`make version-check`, `make version-update`, or `make bump-version X.Y.Z`; direct script commands: `check`, `update`)

## Notes for maintainers

- Script header comments are the source of truth for usage flags, prerequisites, and operational caveats.
- Prefer the root [Makefile](../Makefile) for routine maintainer workflows; direct script execution is the lower-level fallback.
- When a script shells into Poetry or package-local commands, the repository root remains the expected starting context unless the script documents a different entrypoint.
- For repo-wide process and policy, defer to [../README.md](../README.md), [../START_HERE.md](../START_HERE.md), and [../docs/contrib/contributing.md](../docs/contrib/contributing.md).
