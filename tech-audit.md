# Tech Audit — Codebase-Wide Defect Sweep

> **Re-run:** 2026-07-26 · **Branch:** `v87` · **HEAD:** `ba1f808c83e897a06fe901e04356188e54270a30` · **Prior audit base:** `82a73d1f`

## Orientation summary

QuickScale is a Python 3.13–3.14 Poetry monorepo whose product has two deployment realities: a local/published Click CLI plus Django project/code generator (`quickscale`, `quickscale_cli`, `quickscale_core`, and `quickscale_devtools`), and the generated internet-facing Django 6/PostgreSQL 18/Vite-React application, shipped with Docker/Railway support and twelve first-party Django modules (`teams` is a placeholder). Entry points and trust boundaries are CLI arguments and `quickscale.yml`, manifest and installed-wheel resolution, generated Django routes and module APIs/admin/jobs, browser runtime configuration, PostgreSQL tenant data, subprocess adapters, and release/CI workflows. The oracle used for this pass was the repository's fail-hard policy; source-versus-bundled manifest rules G1/G2/G3 and AF7; restricted `NOSUPERUSER`/`NOBYPASSRLS` runtime role plus `FORCE RLS`; Option C direct `organization_id` and `NOT DEFERRABLE` composite-FK policy; complete typed frontend runtime configuration; SA90 emission parity; the sole fail-closed `showcase_react` theme; and parity among local, hosted, installed-artifact, and publish gates. Configuration cells enumerated were monorepo/installed wheel/runtime module override, source/bundled manifests, selected modules and theme, Docker/Railway, solo/SaaS and privileged/restricted DB roles, debug, `QUIET=1`, lock generation enabled/skipped, Node/pnpm present/absent, cache backend, and E2E concurrency. This is a re-run over 161 commits and 157 changed paths; using the companion architectural audit's commit classification plus the newest manifest-fallback commit, 65 were review/closeout-tracked, 78 housekeeping, and 18 side-channel or unlabeled behavioral commits, whose production and test hunks received elevated scrutiny. The full first-party production delta was reviewed; changed manifest discovery/resolvers, configuration/theme validation, generator and React templates, CLI plan/apply/module/dev/DR/remove paths, beta-migration extraction, CRM/forms initial-migration refactors, Make/scripts, and workflows were read at full depth. Unchanged module interiors were sampled at exposed/security-sensitive surfaces and their 2026-07-10 deep-pass verdicts carried; vendored/generated third-party code, lockfile internals, Docker/PostgreSQL execution, and network CVE resolution were skipped. Tooling run read-only: Ruff 0.15.22 over core/CLI/devtools/scripts (pass), Poetry 2.4.1 `check --lock` (pass), `git diff --check` (pass), and pytest 9.1.1: 65 quality-policy plus 563 focused manifest/config/theme/generator/beta-migration tests (628 total, all pass with coverage disabled). Empirical checks: normal versus `QUIET=1` `make -n check` proved only the normal path schedules `lint-frontend`; 96 manifest tests first passed behaviorally but the initial command status failed only because the repository-wide coverage threshold was applied to a focused subset, then passed cleanly with `--no-cov`; filename-only credential-signature scanning found only dummy test fixtures; `pip-audit`, Bandit, and Semgrep were unavailable. The first focused pytest invocation refreshed ignored `.coverage`/`htmlcov` output despite the intended read-only mode; that test command changed no tracked file. Concurrent roadmap and decision-record edits added SA117 during the final self-check and ratified lockstep module versions plus fail-hard embed/core mismatch detection, with immutable-ref pinning deferred to SA119. Their code anchors were re-opened and the current remote-skew symptom is classified below as a structural/release-contract smell, not silently omitted.

## Summary table

| ID | Severity | Category | Title | Effort | Confidence | Status |
|---|---|---|---|---|---|---|
| `TA62` / `quiet-check-skips-frontend-lint` | S3 | VIII — Tests/tooling integrity | Quiet pre-commit check omits the rendered frontend lint | Small — quick win | High | Open · new |

**Counts:** S1: 0 · S2: 0 · S3: 1 · S4: 0 · Total: 1.

## Findings

### Finding TA62: Quiet pre-commit check omits the rendered frontend lint

**ID:** `quiet-check-skips-frontend-lint` (sequence alias `TA62`)
**Severity:** S3 — in the local CLI/generator development and release reality, the realistic `QUIET=1` + Node/pnpm-present cell can report a false-green pre-commit result; hosted and publish gates later catch the defect, so this is not S2. It violates the declared “same as check” contract and is a concrete instance of companion architectural Finding 11 (`quality-gate-topology-hand-synced`).
**Category:** VIII — Tests: test tooling that neuters a guard.
**Confidence:** High — source, help text, test harness, history, layer-up gates, and dry-run behavior were directly verified.
**Location:** `Makefile:12`, `Makefile:137`, `Makefile:833-834`, `Makefile:918-927`; test gap at `scripts/test_ci_coverage_policy.py:1075-1083,1114-1148,1187-1204`.

**Defect and failure scenario:** The Makefile advertises `make check QUIET=1` as the same gate with quiet-on-success output, but wraps the only `lint-frontend` call in `if [ -z "$(QUIET)" ]`. An agent introduces an ESLint or TypeScript error in the generated React source, runs the documented quiet gate, and receives exit 0 after Python/repository checks; because `v87` pushes do not trigger hosted CI, the broken template can remain green locally until a PR to `main` or the publish workflow.

**Evidence:** The contract says `make check QUIET=1 - Same as check, quiet on success` (`Makefile:12,137`). The implementation says:

```make
@if [ -z "$(QUIET)" ]; then
    ...
    $(MAKE) lint-frontend;
```

`make -n check QUIET=1` contained no frontend command, while `make -n check` scheduled `make lint-frontend`. The 65 passing policy tests exercise quiet Python directory/section dispatch, but their fake recursive make is `MAKE=true` and they never assert frontend invocation or failure propagation.

**Refutation:** Hosted CI runs `make lint-frontend` (`.github/workflows/ci.yml:10-58`), local full CI runs it (`scripts/check_ci_locally.sh:183-192`), and publishing runs `make frontend-proof` (`.github/workflows/publish.yml:120-126`). Those safeguards reduce release impact but do not kill the finding: the documented quiet pre-commit command itself is false-green, and the active integration branch is outside the CI push trigger (`ci.yml:3-7`). No comment, test, suppression, or commit message blesses reduced quiet-mode coverage; every description frames `QUIET` as output suppression only.

**Fix:** Run the same Node/pnpm availability guard and `lint-frontend` target for both modes; under `QUIET=1`, capture its output and print it only on failure while preserving the nonzero status. Add a behavioral policy test whose fake recursive make records `lint-frontend` and can force it to fail, asserting both invocation and exit propagation. **Effort:** Small.

**Verification:** Run the new focused policy test, then confirm `make -n check` and `make -n check QUIET=1` both contain `lint-frontend`; inject a harmless temporary TypeScript type error in scratch rendered output and verify both commands fail at the same gate.

**Deliberate?** None found; documentation and help text contradict the omission.
**Age:** Introduced by `6694b13c` on 2026-07-20; `b5b6f349` substantially expanded quiet-mode coverage on 2026-07-23 without adding frontend parity.

## Per-subsystem verdicts

- **Generator/core contracts (`quickscale_core`)** — clean; changed manifest discovery/resolvers, schema/theme validation, generator, Dockerfile, and React/template emission paths read in full. The installed-context fallback covers all twelve shipped module manifests and preserves source-mode fail-hard behavior.
- **CLI/apply lifecycle (`quickscale_cli`)** — no additional closeable source defect in the reviewed delta; plan/apply/module/dev/DR/remove extractions and managed-wiring cleanup paths read. The incomplete installed-wheel `plan → apply → up` lifecycle remains owned by roadmap SA112. Current remote split manifests are also version-skewed and make module-bearing `apply` fail (roadmap SA117); its honest fix changes the split-version/publish contract and external branch state, so it is recorded as a structural smell rather than duplicated as a technical finding.
- **Maintainer migration tool (`quickscale_devtools`)** — clean; extraction, path validation, fixed-argv subprocesses, timeouts, clean-worktree guard, checkpointing, and partial-failure reporting read; 52 focused seam tests passed.
- **Generated React/Django application** — clean at the inspected trust boundaries; runtime seam is fail-hard and typed, project slug is constrained before JavaScript injection, organization slug uses `escapejs`, API endpoints are first-party relative paths, and no `innerHTML`, `dangerouslySetInnerHTML`, `postMessage`, browser storage, or eval sink was present.
- **CRM/forms migrations** — clean; initial-migration changes are repetition-removing operation constructors, with tenant FK, RLS, composite-FK, callable, and payload contracts retained and migration/beta-seam tests strengthened.
- **Django modules** — clean at sampled live surfaces; tenant manager/middleware/RLS boot guard, redirects, client-IP handling, destructive backup paths, and high-risk module callsites were re-opened. Unchanged interiors carry the prior whole-module verdict.
- **Scripts/workflows/Make** — produced `TA62`; local/hosted/publish frontend gates, test worker cleanup, installed smoke wiring, and prior devtools lint/typecheck closure otherwise verified.

## Clean sweeps worth recording

- Tenant taint trace: session organization ID is type-checked and membership-checked in `TenantMiddleware`, stored in a `ContextVar`, and cleared in `finally`; `TenantManager` returns `.none()` without context, while the production boot guard rejects `rolsuper` and `rolbypassrls`.
- Generator path/name taint trace: CLI/config project slug reaches templates only after `validate_project_name()` restricts it to lowercase identifier-safe characters; output creation stages in a temporary directory and rolls back failed swaps.
- Frontend taint trace: Django owns the runtime URLs and booleans; `window.__QUICKSCALE__` validates required own-property booleans, path strings, owner shape, and public-page enums before hooks or `fetch`.
- Manifest configuration matrix: source inventory remains source-authoritative; resolver fallback is centralized for installed-wheel reads; bundled absence/read failure stays fail-hard. Ninety-six focused tests passed.
- Operational lifecycle: generated production settings require a restricted runtime DB URL, migration commands use the explicit privileged cell, Docker runs non-root, subprocess callsites use argv lists, and changed long-running commands have bounded timeouts.
- Test-integrity diff: no added `skip`/`xfail`, inverted assertion, removed fail-closed assertion, or mock substitution that weakened a production invariant was found. The large frontend rewrite replaced specialization assertions with runtime-seam and emitted-source parity tests.
- Prior frontend-proof and devtools-gate closures remain present: hosted/local/publish frontend checks are wired, and all ten scoped CI/local/publish lint/typecheck calls include devtools.
- Secret scan returned only dummy token/key patterns in tests; no credential material was found in first-party production/configuration files.
- Fix-regression pass over manifest fallback, CI checkpoint fixes, CLI extractions, frontend de-specialization, and migration constructor refactors found no sibling-case or caller-contract regression.
- Chain-composition pass ran. `TA62` compounds with the accepted `v87` no-push-CI watch item and architectural Finding 11, but no two-to-three-step chain reached tenant data, credentials, backups, or money at a severity above S3.

## Structural smells

- **`quality-gate-topology-hand-synced` (arch-audit Finding 11):** local, hosted, publish, and E2E assurance inventories are independently edited; `TA62` is another paid drift instance, but the boundary-level fix is structural.
- **`quality-baseline-monotonicity-unenforced` (arch-audit Finding 12):** the mutable quality snapshot can authorize increases despite the shrink-only policy.
- **`generated-file-ownership-unmodeled` (arch-audit Finding 7):** generator/updater ownership remains a hand-authored 138-entry taxonomy; defer until another updater consumer.
- **`deletion-invariants-per-boundary-reimplementation` (arch-audit Finding 2):** non-ownership cleanup obligations still terminate at the account-delete boundary; defer until a second deletion/erasure boundary.
- **`org-model-universe-hand-enumerated` (arch-audit Finding 4):** purge membership is checked, but ordering remains a manual FK-graph shadow with only three asserted edges; defer until `teams` or model-universe growth.
- **SA117 embedded-manifest/split-branch version skew:** `embed_module()` consumes moving `splits/<module>-module` branches (`module_commands.py:624-648`) whose manifests can predate the core schema, while current module versions do not express compatibility. The live symptom is a release-blocking module-bearing `apply` failure. The lockstep stamp/assert contract is now ratified and tracked by SA117, remote split reconciliation is still required, and immutable artifact identity is deferred to structural follow-up SA119; functional closure therefore spans release-contract and external branch state rather than one boundary-preserving PR.

## Tooling gaps

- **Quiet/full gate-membership parity test (`TA62`):** extend `TestCheckQuietSectionDispatch` so recursive make targets are logged, membership is compared with normal `check`, and a frontend-lint failure must propagate in quiet mode.
- **Dependency vulnerability audit:** `pip-audit`/Safety remains absent from local and CI tooling, so current lockfile CVEs could not be resolved in this pass; add a read-only blocking scanner with an explicit reviewed allowlist.
- **Security static analysis:** Bandit/Semgrep remains absent; add a focused rule set for subprocess shell use, unsafe deserialization, TLS disabling, Django raw/marked-safe sinks, and committed credential signatures.
- **Production-change testimony gate:** no automated check requires a CHANGELOG/decision/ticket trail for first-party behavioral commits, leaving the side-channel lane dependent on manual audit scrutiny.

## Notes (watch items)

- **Integration-branch CI:** `.github/workflows/ci.yml` runs on pushes to `main`/`develop` and PRs to `main`, not pushes to `v87`. This remains an accepted solo-maintainer workflow choice; it materially amplifies `TA62` but is not re-litigated as a separate finding.
- **Installed-wheel lifecycle:** roadmap SA112a–f explicitly owns the still-unproven installed-artifact `plan → apply → up` path. The newest manifest fallback is a partial prerequisite, not closure; duplicating it here would create two owners.
- **Published split skew:** roadmap SA117 now blocks publishing after a diagnostic reproduced stale remote manifests in source and installed contexts. The new decision SSOT ratifies v87 lockstep stamping, explicit embed/core mismatch rejection, and mandatory tag → split-push → PyPI ordering; SA119 owns immutable-ref pinning. This is not duplicated as a technical finding because present functionality also requires reconciling external split branches and the durable prevention changes artifact ownership/compatibility.
- **Generator lock generation:** `_generate_poetry_lock()` warns and completes generation on missing Poetry, timeout, or nonzero exit. Tests and comments pin this as a deliberate usability trade-off; downstream apply/install remains fail-loud.
- **Quality baseline:** the larger v87 baseline is governed by the ratified remediation/exemption decision; lack of an enforceable monotonicity boundary is already architectural Finding 12.
- Carried accepted items: SA68 persistent-env cell; dev `docker exec` unsets `RUNTIME_DATABASE_URL`; module packages omit real orgs dependencies by decision; forms anonymization uses one multi-org transaction; worker pools can exhibit head-of-line blocking; React `auth` is typed/defaulted false by decision; two `ImproperlyConfigured` identities coexist; sole-member self-removal can orphan an org; Stripe cancellation occurs inside the account-deletion atomic block; DR recovery fallbacks, analytics missing-key disablement, and public-context fail-closed broad catches are deliberate.

## Reconciliation log

- 2026-07-26 — `TA1`, `TA2`, `TA3`, `TA4`, `TA5`, `TA6`, `TA7`, `TA8`, `TA9`, `TA10`, `TA11`, `TA12`, `TA13`, `TA14`, `TA15`, `TA16`, `TA17`, `TA18`, `TA19`, `TA20`, `TA21`, `TA22`, `TA23`, `TA24`, `TA25`, `TA26`, `TA27`, `TA28`, `TA29`, `TA30`, `TA31`, `TA32`, `TA33`, `TA34`, `TA35`, `TA36`, `TA37`, `TA38`, `TA39`, `TA40`, `TA41`, `TA42`, `TA43`, `TA44`, `TA45`, `TA46`, `TA47`, `TA48`, `TA49`, `TA50`, `TA51`, `TA52`, `TA53`, `TA54`, `TA55`, `TA56`, `TA57`, `TA58`, `TA59`: resolved — historical closures pre-date the prior audit baseline; no matching regression appeared in the full current production delta or sampled live surfaces.
- 2026-07-26 — `TA60`: resolved — frontend proof closure reverified in code: hosted `lint-frontend`, local-CI frontend lint, and publish `frontend-proof` remain wired. `TA62` is a distinct quiet-mode parity defect, not a regression of the publish/hosted closure.
- 2026-07-26 — `TA61`: resolved — devtools closure reverified in code: all ten scoped lint/typecheck invocations across hosted CI, publishing, and local CI still include `--devtools`.
- 2026-07-26 — `TA62` / `quiet-check-skips-frontend-lint`: still-open, new — quiet `check` omits the rendered frontend lint while documenting parity with normal `check`.

**Reconciliation counts:** prior still-open: 0 · prior resolved/carried: 61 · regressed: 0 · new: 1.

Categories swept with no qualifying finding: correctness, concurrency, implementation security/authentication/authorization, resources/I/O, performance, data handling, multi-tenant isolation, CLI destructive-path safety, generator output security, dependency manifest consistency, and runtime lifecycle transitions.
