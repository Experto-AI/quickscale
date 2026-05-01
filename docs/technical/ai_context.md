# AI Context Baseline

Compact baseline for AI hydration in QuickScale. This file is derivative and intentionally non-navigational. It summarizes repository-wide facts that every AI role should share; it does not replace the authoritative sources.

## Authority Order

1. [decisions.md](./decisions.md) owns repo-wide policy, scope, command baselines, and conflict resolution.
2. [scaffolding.md](./scaffolding.md) owns repository and generated-project structure, naming, and placement.
3. Role-specific guides in `docs/contrib/*.md` add stage-local execution guidance when they do not conflict with the two files above.
4. Package README files plus human router docs such as root `README.md`, `START_HERE.md`, and `docs/contrib/contributing.md` are informational and human-first.

## Workflow Baseline

- Default workflow: run `quickscale plan <project>`, enter the generated directory, then run `quickscale apply`.
- `quickscale.yml` is the desired-state file. `.quickscale/state.yml` and `.quickscale/config.yml` are system-managed state artifacts.
- Generated projects are standalone Django projects. Do not assume automatic settings inheritance from `quickscale_core`.
- Modules are embedded runtime dependencies managed through the documented git-subtree workflow. Themes are one-time scaffolding copied into user-owned project files.

## Stack Baseline

- Packaging and dependency management: Poetry with `pyproject.toml`.
- Python package layout: `src/` layout across first-party packages.
- Shared quality tools: Ruff for format and lint, MyPy for type checking, pytest + pytest-django + pytest-cov for testing and coverage.
- Production baseline: Docker and PostgreSQL are part of the current shipped contract.
- Do not introduce or document `requirements.txt`, `setup.py`, Black, or Flake8 as current QuickScale standards.

## Validation Entry Points

- Prefer repository `make` targets over lower-level helper scripts.
- Use the narrowest relevant validation first, then widen only as needed.
- Shared entrypoints:
  - `make lint`
  - `make format`
  - `make test`
  - `make test-unit`
  - `make test-e2e`
  - `make ci-e2e`
  - `make version-check`

## Generated-Project Ownership

- Generated projects are user-owned code.
- Themes are copied into project-owned templates and frontend files; they are not live runtime packages.
- Embedded modules live under `modules/<name>/` in generated projects and can be updated through the documented module workflow.
- Maintainer-side repository layout such as `quickscale_modules/` is repository context, not generated-project structure.

## Maintenance Rule

Update [decisions.md](./decisions.md) and [scaffolding.md](./scaffolding.md) first when a covered fact changes. Update this file in the same change only to keep the derivative AI baseline aligned and concise.

## Conflict Policy

If this summary drifts from [decisions.md](./decisions.md) or [scaffolding.md](./scaffolding.md), those two files win immediately and this file must be corrected. If a role-specific guide conflicts with them, follow the authoritative technical docs and fix the guide.
