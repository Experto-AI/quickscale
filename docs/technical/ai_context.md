# AI Context Baseline

Compact, derived baseline every AI role shares. It never overrides its sources: on any conflict
the owning document wins immediately and this file is corrected.

## Authority Order

1. [decisions.md](./decisions.md): repo-wide policy, tie-breakers, prohibitions; its
   [§ Document Responsibilities](./decisions.md#document-responsibilities) names the owner of every
   topic and marks the authoritative (**A**) documents.
2. The **A** companions: [implementation_contract.md](./implementation_contract.md) (shipped
   contract, CLI), [module_architecture.md](./module_architecture.md),
   [module_conventions.md](./module_conventions.md),
   [validation_policy.md](./validation_policy.md),
   [generated_project_structure.md](./generated_project_structure.md),
   [repository_layout.md](./repository_layout.md).
3. [docs/contrib/rules.md](../contrib/rules.md): contributor engineering rules. Stage guides in
   `docs/contrib/` apply them and never override them.

READMEs, `START_HERE.md` and contributor routers are human-first and never authoritative.

## Workflow Baseline

- `quickscale plan <project>` writes `quickscale.yml` (desired state); `quickscale apply` inside
  the project materializes it. `.quickscale/state.yml` is the sole applied-state store, written
  under an advisory lock. `quickscale status` reports drift.
- Generated projects are standalone Django projects with no settings inheritance; they import
  runtime contracts from the versioned `quickscale_core.runtime.settings` facade and pin
  `quickscale-core` in lockstep.
- Modules are embedded runtime dependencies (git subtree, `modules/<name>/`); themes are one-time
  scaffolding copied into user-owned files.

## Stack Baseline

Poetry + `pyproject.toml`, `src/` layout, Ruff (format and lint), MyPy, pytest + pytest-django +
pytest-cov, Docker, PostgreSQL only. `requirements.txt`, `setup.py`, Black and Flake8 are
prohibited.

## Validation Entry Points

Shared workflows run through `make` targets. The tier bounds the obligation
([validation_policy.md §Validation Tiers](./validation_policy.md#validation-tiers)):

| Tier | When | Command |
|---|---|---|
| `change` | one phase or one correction | `make lint`, `make typecheck`, `make test-unit K=<expr>` |
| `task` | completed plan, cross-package delta | owning section suite or `make check QUIET=1` |
| `release` | closeout, version bump, generator-template change | `make ci` (`make ci-e2e` when an E2E trigger applies) |

Scoped runs (`K=`, `ARGS=`, `make ci ONLY=/FROM=/SKIP_INSTALL=`) satisfy no tier
([§Scoping and Rerun Variables](./validation_policy.md#scoping-and-rerun-variables)).
`make retry` re-runs the last failures.

## Generated-Project Ownership

Generated projects are user-owned code. `quickscale_modules/` is maintainer-repository context,
not generated-project structure.
