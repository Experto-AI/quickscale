# AI Context Baseline

Compact baseline for AI hydration in QuickScale. This file is derivative and intentionally non-navigational. It summarizes repository-wide facts that every AI role should share; it does not replace the authoritative sources.

> **Drift notice**: This file is a best-effort derivative of `decisions.md` and the companion technical docs. It may lag behind those canonical sources. If any fact here conflicts with `decisions.md`, `implementation_contract.md`, `validation_policy.md`, `generated_project_structure.md`, `repository_layout.md`, or `scaffolding.md`, treat those documents as authoritative immediately — before this file is corrected.

## Authority Order

1. [decisions.md](./decisions.md) owns repo-wide policy, tie-breakers, prohibitions, and the document ownership map.
2. [implementation_contract.md](./implementation_contract.md) owns the current shipped contract, feature matrix, CLI surface summary, and architecture-boundary notes.
3. [validation_policy.md](./validation_policy.md) owns validation entrypoints, testing standards, coverage expectations, and E2E guidance.
4. [generated_project_structure.md](./generated_project_structure.md) owns generated-project structure, generated artifact placement, and generation guardrails.
5. [repository_layout.md](./repository_layout.md) owns maintainer-repository layout plus naming and import guidance.
6. [scaffolding.md](./scaffolding.md) is the concise structure hub that preserves backlinks and compatibility anchors into the companion docs.
7. Role-specific guides in `docs/contrib/*.md` add stage-local execution guidance when they do not conflict with the technical authorities above.

Shared rule sources in `docs/contrib/shared/` remain the normative workflow-agnostic contributor guidance. Stage guides in `docs/contrib/*.md` apply that guidance stage-locally and do not prescribe a required workflow order.
Package READMEs, root `README.md`, `START_HERE.md`, and contributor-router docs are informational or human-first references and do not override the technical authorities above.

## Workflow Baseline

- Default workflow: run `quickscale plan <project>`, enter the generated directory, then run `quickscale apply`.
- `quickscale.yml` is the desired-state file. `.quickscale/state.yml` is the sole authoritative applied-state store with consolidated sub-sections for module-tracking metadata and managed-file drift records. Legacy `.quickscale/config.yml` and `.quickscale/file_hashes.yml` are compatibility inputs only (read-through imported when `state.yml` lacks consolidated sections; ignored when consolidated sections are present).
- `quickscale apply` acquires an advisory lock around `state.yml` read/modify/write so concurrent applies fail closed instead of racing.
- `quickscale status` reports drift and compatibility diagnostics on demand (state consolidation, legacy files, module tracking, managed-file drift, version drift).
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

Update the authoritative companion doc first when a covered fact changes. Update [decisions.md](./decisions.md) in the same change when the repository-wide ownership map, policy, or tie-breakers change. Update this file only to keep the derivative AI baseline aligned and concise.

## Conflict Policy

If this summary drifts from the authoritative technical docs, those technical docs win immediately and this file must be corrected. If a role-specific guide conflicts with them, follow the authoritative technical docs and fix the guide.
