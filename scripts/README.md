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
| `./scripts/lint.sh` | `make lint-fix` and/or `make typecheck` |
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
| `./scripts/publish_module.sh <module> --expected-remote-sha <sha|ABSENT>` | `make publish-module MODULE=<module> EXPECTED_REMOTE_SHA=<sha|ABSENT>` |
| `./scripts/publish_module.sh --status` | `make publish-module-status` |
| `./scripts/publish_module.sh --publish-outdated` | [DISABLED SA117 Phase 4] `make publish-modules-outdated` |
| `./scripts/version_tool.sh check` | `make version-check` |
| `./scripts/version_tool.sh update` | `make version-update` after editing `VERSION`, or `make bump-version X.Y.Z` to update `VERSION` first |
| `poetry run python scripts/check_sa117_scope.py worktree` | `make sa117-check` (add `SCRIPTS_ONLY=1` for Phase 1 backward compat) |
| `poetry run python scripts/check_sa117_scope.py emit` | `make sa117-emit` |
| `poetry run python scripts/check_sa117_scope.py lock` | `make sa117-lock` (add `SCRIPTS_ONLY=1` for Phase 1 backward compat) |
| `poetry run python scripts/check_sa117_scope.py lock-diff --baseline-ref REF --candidate poetry.lock --expected-version X.Y.Z` | `make sa117-lock-diff SA117_BASELINE_REF=REF` (candidate/evidence/version variables are overridable) |
| `poetry run python scripts/verify_sa117_publication.py capture --version X --phase Y` | `make sa117-capture VERSION=X PHASE=Y` |
| `poetry run python scripts/verify_sa117_publication.py verify --evidence PATH` | `make sa117-verify EVIDENCE=PATH` |
| `poetry run python scripts/verify_sa117_publication.py authorize --version X --evidence-digest D` | `make sa117-authorize VERSION=X DIGEST=D` |
| `poetry run python scripts/verify_sa117_publication.py rollback --auth-token T --evidence-digest D` | `make sa117-rollback TOKEN=T DIGEST=D` |
| `poetry run python scripts/verify_public_module_apply.py apply --module M --target T --executable E --argv A` | `make sa117-apply MODULE=M TARGET=T EXEC=E ARGV=A` |
| `poetry run python scripts/verify_public_module_apply.py check-origin --module M --declared-origin O --expected-origin E` | `make sa117-check-origin MODULE=M DECLARED=O EXPECTED=E` |
| `poetry run python scripts/verify_public_module_apply.py check-containers --target T` | `make sa117-check-containers TARGET=T` |
| `poetry run python scripts/check_gate_parity.py` | `make check-gate-parity` |
| `poetry run python scripts/test_gate_parity.py` | `poetry run pytest scripts/test_gate_parity.py -q --tb=short` |
| `poetry run python scripts/sync_ci_gate_jobs.py --check` | `make check-ci-gate-generation` |

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
- [lint.sh](./lint.sh) — runs standardized Ruff auto-fixes plus MyPy checks for Python packages (prefer `make lint-fix` / `make typecheck`)
- [lint_agentic_flow.sh](./lint_agentic_flow.sh) — runs focused linting for agentic-flow work (`make lint-agent`)
- [lint_frontend.sh](./lint_frontend.sh) — validates the React theme frontend toolchain (`make lint-frontend`)
- [compile_docs.sh](./compile_docs.sh) — rebuilds the aggregated contributing guide from docs sources (`make docs`)

### Test runners

- [test_unit.sh](./test_unit.sh) — runs unit tests only (prefer `make test` or `make test-unit`)
- [test_e2e.sh](./test_e2e.sh) — runs local end-to-end tests and supporting setup (`make test-e2e`)
- [test_agentic_flow.sh](./test_agentic_flow.sh) — runs focused agentic-flow adapter tests (`make test-agent`)

### Release and distribution

- [publish.sh](./publish.sh) — builds and publishes packages (prefer `make publish-build`, `make publish-test`, `make publish-prod`, or `make publish-full`)
- [publish_module.sh](./publish_module.sh) — publishes module changes to split branches using force-with-lease safety, reports module split-branch status (`make publish-module MODULE=<name> EXPECTED_REMOTE_SHA=<sha|ABSENT>`, `make publish-module-status`). **Note**: `--publish-outdated` / `make publish-modules-outdated` is **disabled** in SA117 Phase 4 — each module must be published individually with `--expected-remote-sha`.
- [version_tool.sh](./version_tool.sh) — checks and synchronizes version metadata (`make version-check`, `make version-update`, or `make bump-version X.Y.Z`; direct script commands: `check`, `update`)

### SA122a gate registry parity

- [gate_registry.json](./gate_registry.json) — strict JSON v1 declarative gate registry declaring every gating checkpoint across all five execution contexts (local-serial, local-parallel, hosted CI, publish, e2e-trigger). Loaded and validated at startup by `check_gate_parity.py`. Only plain JSON is accepted (no YAML constructs, no trailing commas, no unquoted keys). Duplicate mapping keys are explicitly rejected at the JSON parser level before structural schema validation.
- [check_gate_parity.py](./check_gate_parity.py) — diagnostic parity checker that compares the declared gate registry against every execution-context source (Makefile, check_ci_locally.sh, ci.yml, publish.yml, e2e.yml). Exit codes: 0 = perfect parity, 1 = JSONL semantic diffs on stdout (no ERROR on stderr), 2 = malformed/ambiguous input (ERROR on stderr, no traceback).

  **Exit/stream behavior**:
  - **Direct CLI** (`poetry run python scripts/check_gate_parity.py`): stdout carries JSONL diagnostics (exit 1) or nothing (exit 0); stderr carries the success confirmation on exit 0 or leading `ERROR:` prefix messages on exit 2. Exit 1 has no `ERROR:` prefix on stderr.
  - **Make** (`make check-gate-parity`): translates ALL nonzero script exits to exit 2 for deterministic Make failure handling. On nonzero exit, both stdout and stderr from the script are merged and redirected to stderr with an additional `ERROR: [GATE_FAILED]` prefix. On exit 0, the success message is printed to stdout. This means `make check-gate-parity` exits 2 when the script returns 1 (semantic diffs) or 2 (schema/parse error), unlike the direct CLI which distinguishes them.

  **Diagnostic levels**:
  - `missing` — a gate declared in the registry is absent from a required execution context, or an e2e path declared in `trigger_inputs` is absent from `e2e.yml`.
  - `extra` — a path present in `e2e.yml` has no corresponding `trigger_inputs` entry in any registry gate.
  - `order` — common paths between registry `trigger_inputs` and `e2e.yml` appear in different relative sequence order.

  **Source extraction scope**:
  - `local-serial`/`local-parallel`: extracts `make <target>` invocations from bounded function bodies (`run_static_gates_serial` / `run_static_gates_parallel`) in `check_ci_locally.sh`. Echo statements and shell comments are excluded.
  - `hosted`: extracts top-level YAML job names under `jobs:` in `ci.yml` using structural YAML parsing with duplicate-key rejection (BaseLoader-safe for the `on:` key).
  - `publish`: extracts job names and `make <target>` calls from `run:` blocks in `publish.yml`. Comments and echo-only lines are excluded.
  - `e2e-trigger`: extracts the ordered path allowlist from the `pull_request.paths:` block in `e2e.yml` only.
  - `makefile`: validates every gate's `make_target` exists as a defined Makefile target with an actual recipe (tab-indented commands) or as a `.PHONY` declaration in the root `Makefile`.
- [test_gate_parity.py](./test_gate_parity.py) — focused pytest suite covering current reproduction (the five known publish gaps: check-core-compat, check-module-core-imports, check-manifest-sync, check-org-context-primitives, check-csrf-exempt), fake-gate fan-out, complete schema validation (including strict JSON v1 duplicate-key rejection, unknown/missing keys, unsafe IDs/paths, dependency validation, binding collisions, string "null" rejection), fail-closed source parsing (missing/duplicate/unclosed function detection), YAML structural parsing with duplicate-key rejection, e2e ownership collision detection, stream behavior (exit 0/1/2), Make wrapper exit translation, Makefile target+recipe validation, and e2e exact sequence mutation (reorder, interior swap, missing, extra, duplicate paths).

### SA122b hosted CI gate generation

- [sync_ci_gate_jobs.py](./sync_ci_gate_jobs.py) — deterministic hybrid generator for the five registry-bound hosted jobs and the three consumer `needs` lists. The registry supplies hosted job IDs and Make targets; the script's static catalog preserves display names, action versions, steps, and check-step labels. `--check` is read-only and reports a deterministic unified diff (exit 1 on drift); `--write` updates only the structurally owned marked regions atomically (exit 0 on success); `--print-check-targets` is the strict registry projection used by Make during parse-time target derivation. Malformed YAML/JSON, duplicate keys, unsupported hosted sets, misplaced or incomplete markers, and semantic invariant failures emit one `ERROR:` line and exit 2.

Use `make check-ci-gate-generation` in normal validation. To intentionally refresh the generated regions, run `poetry run python scripts/sync_ci_gate_jobs.py --write` from the repository root, then rerun the Make check.

**Expected-gap semantics**: SA122-DEC-001 established that publish.yml has full coverage of the release pipeline but currently omits the five standalone repo conformance gates. The checker reports these as `level: "missing"` diagnostics in the `publish` context. These five omissions are the sole expected gap in Phase 1; any additional missing gate is a regression.

### SA117 version lockstep

- [sa117_scope.json](./sa117_scope.json) — scope-gate allowlist defining the SA117 path set across all phases, with phase tags for partial rollout. Source of truth for scope-gate verification.
- [check_sa117_scope.py](./check_sa117_scope.py) — scope guard with `worktree` (check tracked paths against allowlist), `emit` (print filtered paths), and `lock` (exact path-set match) modes. NUL-path safe. Exit codes: 0 pass, 1 semantic rejection, 2 malformed invocation.
- [test_check_sa117_scope.py](./test_check_sa117_scope.py) — focused pytest suite for scope guard: NUL rejection, path normalisation, allowlist loading, and all three modes. Hermetic (no git dependency for most tests; uses explicit path lists).
- [test_version_tool.py](./test_version_tool.py) — hermetic contract tests for the version tool plus temp-repo update workflow tests. Contract tests define version-string parsing, check/update/lock modes, and error handling. Temp-repo update tests (``TestUpdateWithTempRepo``) build a complete 12-module fixture repository, run ``version_tool.sh update`` / ``make version-update`` / ``make bump-version`` via subprocess, and assert exact mutation sets, caller parity, and Markdown exclusion.
- [verify_sa117_publication.py](./verify_sa117_publication.py) — publication gate with `capture`, `verify`, `authorize`, and `rollback` operations. Evidence is written to a configurable path (default: `/tmp/opencode/sa117-evidence/`). Authorization requires explicit parameters; rollback requires matching evidence digest. No production mutation.
- [test_verify_sa117_publication.py](./test_verify_sa117_publication.py) — hermetic tests for publication verification: evidence schema, scope digest, capture/verify/authorize/rollback operations, full capture→verify→authorize→rollback workflow.
- [verify_public_module_apply.py](./verify_public_module_apply.py) — public module apply verification covering argument validation, process execution (timeout, PGRP, failure precedence), evidence capture, origin-map consistency checks, resource cleanup, and zero container/volume checks. Testable with fake executables.
- [test_verify_public_module_apply.py](./test_verify_public_module_apply.py) — hermetic tests for module apply verification: argument validation, process execution, process group kill, evidence building, origin map checks, `ResourceCleanup` context manager, container/volume detection.

#### SA117c lock-diff contract

`lock-diff` is the sole lock-drift route. It requires `--baseline-ref`, the
repository-root `--candidate` (`poetry.lock`), and `--expected-version`; the
candidate root is derived from the supplied lock path. The checker validates
that this root is exactly the Git top-level repository, then validates exactly
55 regular inventory files and 66 canonical version values on each
side, including the twelve module package records in `poetry.lock`. Baseline
Git entries must be regular blobs in mode `100644` or `100755`; candidate
paths must be regular non-symlink files. Structural TOML, YAML, Python AST,
and `VERSION` parsing is strict and fail-closed. YAML anchors, aliases,
merges, and duplicate keys are rejected. The production canonical version
parser is used through a fail-closed wrapper.

Only those twelve validated `package.version` leaves are normalised when
comparing lock structures. Any other lock drift is a semantic failure. All
inventory values, including snapshots and lock module versions, must equal
that side's `VERSION`; `--expected-version` must agree with the candidate and
never overrides it.

Direct exit codes are `0` clean, `1` unauthorized lock drift, and `2`
malformed or unverifiable input. Evidence is schema version 1 JSON at
`/tmp/sa117-lock-diff-evidence.json` by default, written atomically for exits
0/1 and removed after output-path safety checks (no evidence remains on exit
2). An output path resolving to any candidate inventory input is
rejected before stale-evidence removal. It binds
the resolved full baseline SHA plus candidate/root/lock digests.

The preferred Make route is:

```text
make sa117-lock-diff SA117_BASELINE_REF=<ref>
```

`SA117_CANDIDATE` defaults to `$(CURDIR)/poetry.lock`, `SA117_EXPECTED_VERSION`
defaults to `$(VERSION)`, and `SA117_EVIDENCE` defaults to the path above.
Make translates missing required variables to exit `2`; the checker retains
the direct `0/1/2` contract. Quoted root and candidate arguments support
worktrees whose paths contain spaces. SA117c proves lock drift only and does
not authorize or perform SA117e publication, remote split-branch, or module
publishing operations.

## Notes for maintainers

- Script header comments are the source of truth for usage flags, prerequisites, and operational caveats.
- Prefer the root [Makefile](../Makefile) for routine maintainer workflows; direct script execution is the lower-level fallback.
- When a script shells into Poetry or package-local commands, the repository root remains the expected starting context unless the script documents a different entrypoint.
- For repo-wide process and policy, defer to [../README.md](../README.md), [../START_HERE.md](../START_HERE.md), and [../docs/contrib/contributing.md](../docs/contrib/contributing.md).
