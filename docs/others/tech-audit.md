# Tech Audit — Codebase-Wide Defect Sweep

> **Latest re-run:** 2026-07-19 (V3 delta pass) · **Branch:** `v87` (HEAD `82a73d1f`, prior
> `09f9cbcc`) · **Result: one S3 finding open, zero S1–S2–S4.** (TA61 was closed by SA102
> on 2026-07-19 — see the Reconciliation log; per this document's convention closed findings
> live only in the log.)
> History of prior passes is preserved in the Reconciliation log below and in this file's git
> history; per this document's convention, closed findings live only in the log.
>
> **Original masthead:** audit date 2026-07-11 (first run on the V3 prompt) · **Prompt:**
> tech-audit-prompt (V3). Structural findings live in [arch-audit.md](arch-audit.md); fail-hard
> policy SSOT is [decisions.md §fail-hard-principle](../technical/decisions.md#fail-hard-principle).
>
> **This pass (2026-07-19, delta `09f9cbcc..HEAD`, 65 commits, ~49 files, +5.4k/−1.7k):** the
> delta carries the v87 tail — **SA97** (shared test-state reset fixture), **SA98** (orgs-owned
> sanitizer seam), **SA100** (recovery-theme exemption narrowed; closed TA58/TA59), **SA99**
> (devtools under repo lint/mypy), the **SA93 closeout** (hosted e2e evidence + remote-gate
> alignment), and the **TP1/TP2/TP3a** test-parallelization suite (parallel local static gates,
> xdist unit runs, e2e lane namespacing), plus ~50 docs/merge commits. The full first-party
> production diff was read. The same delta was audited structurally by the arch-audit's
> 2026-07-19 pass (same invoker session), whose **red flag — the rendered-frontend proof wired
> into no gate — is accepted here as TA60 after independent verification and narrowing** (the
> e2e docker-build layer partially mitigates it; see the finding). The invoker's frontend-theme
> portability question is owned by arch-audit **Finding 10** (`frontend-source-generation-
> specialized`); this document's ticket-shaped contribution to it is TA60. Test-integrity diff
> (§3.7) run across every changed test file: no weakened or flipped tests; the one widened
> assertion (`test_middleware.py:542`) was **empirically verified fail-closed-equivalent**
> (PG18: `RESET` leaves a custom GUC readable as `''`, and the Option C policies are
> NULLIF-guarded, so `''` ≡ no-org). Closure claims verified in code per §2f.3 (TA58, TA59 —
> both confirmed; SA97/SA98 fix-regression audits clean). Chain pass (§3.9) ran: one
> cross-document chain noted on TA60 (with arch-audit Finding 10). **For the fifth consecutive
> pass, the checkpoint lane carried the pass's anomaly** — `022a88fb` (prior delta) edited 4
> theme templates without rebaselining the SA90 parity fixture, leaving that gate red for ~2
> days until side-channel commit `1e7cbc2c` synced it; invisible remotely because `ci.yml` does
> not run on `v87` pushes (see Notes). The current fixture was empirically re-verified green.

## Orientation summary

QuickScale is a **Python 3.13 Django project generator** (Poetry monorepo: `quickscale_core`
manifest/apply/generator/DR engine, `quickscale_cli` Click CLI, 13 shipped `quickscale_modules/*`
Django apps, `quickscale_devtools` beta-migration tooling, Jinja2 generator templates; version
0.87.0, unreleased). Two deployment realities: **(a)** the *generated project* — an
internet-facing Django 6 + PostgreSQL 18 + Vite/React app targeting Railway (edge proxy →
gunicorn, non-root container, fail-closed runtime DB role, HTTPS/HSTS/secure cookies, active
`CACHES`, SA36 trusted-proxy client-IP, SA68 one-shot privileged-command env contract);
**(b)** the *CLI/generator* — a local developer tool (only `quickscale_core`/`quickscale_cli`/
`quickscale` publish to PyPI — the theme templates ship inside the `quickscale_core` wheel).
Major deltas this pass: **SA100** replaced TA58's string-matching recovery-ledger exemption with
an explicit `allow_recovery_checkpoint` opt-in keyed on the exact `__checkpoint__` sentinel and
only for the recovery-ledger source (`theme_validation.py`), with `up` now fail-closed for every
other invalid theme; **SA98** single-homed the href/rendered-HTML sanitizer in
`orgs/sanitization.py` (blog + listings consume it; byte-identical logic); **SA97** consolidated
six divergent per-module conftest reset copies into `tests_shared/reset_state.py` (canonical
superset: ContextVar + GUCs + `RESET ROLE` + AF9 memo + cache, setup and teardown); **TP1**
parallelized the nine local static CI gates behind a worker fan-out in `check_ci_locally.sh`
(per-worker exit-code retention, reentrancy-guarded signal handling, `QS_CI_PARALLEL=0` serial
escape hatch, own 6-test suite `test_ci_local_parallel.py` wired into `make ci` and `ci.yml`);
**TP2** put core/CLI unit runs on pytest-xdist (`PYTEST_XDIST_WORKERS`, `--dist loadfile`,
serial escape at `0`); the `test-cov` target was rewritten onto isolated per-phase
`COVERAGE_FILE`s in a mktemp dir with an explicit combine step — **missing coverage data now
fails hard** where it was previously silent; **TP3a** namespaced e2e Docker scopes per lane
(compose-project labels + container prefixes; cleanup is label-filtered instead of the old
global port-based `docker rm`); **SA93** moved the hosted e2e workflow onto the maintained
`test_e2e.sh` runner and widened its PR path filters to the whole generator tree. Declared-
invariant oracle used this pass: the fail-hard principle (decisions.md SSOT), the RLS
runtime-role contract (SA58 boot guard), the SA68 launcher env contract, Option C child-table
RLS with the NULLIF-guarded GUC policy, the SA94/SA100 theme-preflight invariant, the SA92
squash guardrail, and the SA90 emission-parity invariant (this pass's transient violation — see
Notes). Tooling baseline: ruff + strict mypy in CI, csrf_exempt/delete-rule/module-core/
manifest-sync/SA60-composite-FK/SA66 gates, worker-pool + coverage-policy + TP1 test suites in
CI; **still no dependency-audit / bandit / semgrep step; `lint-frontend`/`frontend-proof` exist
but are wired into no gate (TA60)**.

**Coverage (this pass):** read in full — the entire first-party production diff
`09f9cbcc..HEAD`: `Makefile` (complete diff incl. the `test-cov` rewrite and devtools section
plumbing), `scripts/check_ci_locally.sh` (current file, complete), `scripts/test_e2e.sh` diff,
`.github/workflows/ci.yml`/`e2e.yml` diffs + `publish.yml` job graph,
`development_commands.py` diff (SA100 `up` carve-out removal), `theme_validation.py` diff
(complete), `orgs/sanitization.py` (new, complete), blog/listings `views.py` diffs (complete),
`tests_shared/reset_state.py` (new, complete), `pyproject.toml`/`ruff.toml`/`poetry.lock`
diffs, the `sa90_emission_manifests.json` rebaseline traced commit-by-commit to its template
edits. Sampled — the changed test files via targeted §3.7 scans (all six conftest migrations
enumerated — every one replaces a private reset copy with the SA97 superset; the deleted
blog/listings sanitizer tests confirmed moved-and-strengthened into
`orgs/tests/test_sanitization.py`, including new case-obfuscation, `data:`, `vbscript:` pins
and an honest pin of the single-quoted-attribute limitation, unreachable at the live sink
because `escape()`+markdownify emit only double-quoted attributes), `test_sa94_theme_preflight`
and `test_theme_validation` additions (all strengthenings pinning SA100),
`test_ci_local_parallel.py`/`test_ci_coverage_policy.py` (no skips/xfails). Skipped — module
interiors unchanged since 2026-07-10 (verdicts carried), the five SA96 coverage checkpoint test
modules (`b7922aaa`, test-only, no source changes), `htmlcov/`, `graphify-out/`. **Empirical
checks:** (1) PG18 session check — `SET app.current_org_id='42'; RESET …` →
`current_setting(…, true)` returns `''` not NULL, and `NULLIF(…, '')` is NULL — confirms the
`test_middleware.py` assertion widening is fail-closed-equivalent (result: refuted the
weakened-test hypothesis). (2) SA90 parity suite run read-only against current templates —
19 passed (the fixture rebaseline in `1e7cbc2c` is a correct sync, not drift). (3) ruff
check/format + strict mypy run read-only over `quickscale_devtools/src` — all pass, so TA61 is
gate drift, not concealment. Audit tools run: none available (`bandit`/`pip-audit`/`semgrep`
absent, installs prohibited).

---

## Findings summary

| ID | Severity | Category | Title | Effort | Confidence | Status |
|----|----------|----------|-------|--------|------------|--------|
| TA60 | S3 | operability / generator archetype | Frontend build/lint proof sits on no blocking gate path | Small | High | closed |

Counts: **S1: 0 · S2: 0 · S3: 0 · S4: 0.** (TA60 closed by SA103; TA61 resolved by SA102 — see Reconciliation log.)
Chain pass (§3.9): ran — one cross-document chain (TA60 × arch-audit Finding 10, noted inside
TA60); no security or data-path composition with any watch item or crown jewel.

---

## Findings detail

### TA60 (S3) — `frontend-build-proof-ungated`

- **Severity:** S3 — generator deployment reality; late detection plus a realistic
  broken-publish path, but a partial layer-up safeguard exists (preconditions counted below).
  Violates no declared oracle invariant; it is the gate the SA93 green-gate work has not yet
  covered. Accepted from the arch-audit 2026-07-19 red-flag hand-off after independent
  verification; severity here is narrower than the red flag's phrasing.
- **Category:** §VI operability / §4.X code-generator ("no gate exercises the generated
  artifact's frontend build").
- **Confidence:** High — every gate surface read directly this pass.
- **Location:** `Makefile:691,695` (`lint-frontend`, `frontend-proof` targets),
  `Makefile:793,803` (`check`/`ci` umbrellas — neither includes them),
  `.github/workflows/ci.yml` (zero node/pnpm references), `.github/workflows/publish.yml`
  (job graph `verify → test → build → publish-pypi`; no docker build, no frontend, no
  dependency on the e2e workflow), `.github/workflows/e2e.yml:150-192` (the only place the
  frontend is ever built).
- **Defect:** the only executable proof that the shipped theme renders to compilable,
  buildable frontend code (`make lint-frontend`: render → ESLint+tsc; `make frontend-proof`:
  render → pnpm install/build) is wired into no gate. The e2e lane's `docker-build-test` job
  does build a generated project (Dockerfile `frontend-builder` stage runs `pnpm install` +
  `pnpm run build` = `tsc -b && vite build` — `Dockerfile.j2:6-15`, `package.json.j2:12`), but
  it triggers only on PRs to main (path-filtered), `v*` tags, and manual dispatch — and
  `publish.yml` runs concurrently on the same tag with **no dependency on it**. ESLint runs
  nowhere at all.
- **Failure scenario:** a theme edit introducing a TypeScript error lands on `v87`. `make ci`
  is green (no node stage), `ci.yml` never runs (push triggers are main/develop only), and
  weeks of work stack on top. At release: if the route to main is a PR, the e2e docker build
  catches it there (late, release-blocking surprise); if main is pushed directly or the tag is
  cut, `publish.yml`'s verify/test/build jobs are all green and the broken templates publish
  to PyPI inside the `quickscale_core` wheel while the e2e workflow fails separately after the
  fact — every `quickscale apply` from that release emits a frontend that cannot build.
- **Evidence:** `grep -rn "lint-frontend\|frontend-proof\|pnpm\|node" .github/workflows/*.yml
  Makefile` → hits only in the Makefile target definitions and help text; `check:` at
  `Makefile:793` lists lint/typecheck/test/five gates, no frontend target; `publish.yml` has
  zero docker/frontend references and its `publish-pypi` needs only `build`.
- **Refutation:** attempted per §1a — the layer-up hunt *found* a safeguard (the e2e
  docker-build job compiles the frontend, and this delta widened its PR path filters to
  `quickscale_core/src/quickscale_core/generator/**`, which covers the theme tree). It narrows
  the finding from "ships through a fully green release gate" to "not on any *blocking* path":
  two preconditions (no PR-to-main run before the tag, or ignoring a concurrently failing
  non-blocking workflow) separate the defect from the PyPI consequence — hence S3, not S2.
  The ESLint half survives unconditionally: no environment executes it.
- **Fix (Small):** (1) add a `lint-frontend` job to `ci.yml` (node+pnpm setup, `make
  lint-frontend`) and add the target to the `check` umbrella / `check_ci_locally.sh` fan-out
  guarded by a node-availability check; (2) make the publish workflow depend on the frontend
  proof — either a `frontend-proof` step in publish's `test` job or converting e2e's
  docker-build job into a `workflow_call` dependency. **Chain (cross-document):** arch-audit
  Finding 10 stage 1 (templates become real `.ts`/`.tsx` files) would let the repo's existing
  ESLint/tsc gate them directly — fixing TA60 cheaply is still worth doing first; the two are
  compatible, not alternatives.
- **Verification:** introduce a deliberate TS error in `Dashboard.tsx.j2` on a branch — the
  new gate must go red in `make ci` and `ci.yml`; revert.
- **Deliberate?** none found — the targets were built (SA94 era) with clear intent to gate;
  no decision record excludes them from CI. The SA93 roadmap treats the e2e lane as the
  green-gate, which plausibly explains the gap going unnoticed.
- **Age:** long-standing — the targets have existed ungated since their introduction; the
  publish/e2e non-dependency predates this delta.

---

## Per-module verdicts

Module interiors unchanged since the 2026-07-10 deep pass; verdicts carried except where this
delta touched them:

- **quickscale_core** — production clean. SA100 verified: `_RECOVERY_CHECKPOINT_THEME` accepted
  only under the explicit opt-in *and* only for the recovery-ledger source; desired/applied
  state never exempt; TA59's dead constant deleted. SA90 manifest rebaseline traced to its
  template edits and empirically re-verified green.
- **quickscale_cli** — clean. `up` is now fail-closed for every invalid theme (the TA58
  carve-out is gone); the e2e workflow-path additions are test plumbing.
- **quickscale_devtools** — clean at its surface (untouched this delta); its former gating gap
  (TA61) was closed by SA102, which wired `--devtools` into every CI lint/typecheck invocation.
- **orgs** — clean; new `sanitization.py` is a faithful byte-equivalent home for the SA26/SA98
  sanitizer with a strengthened test suite; conftest moved onto the SA97 superset;
  `test_middleware.py` widening empirically verified fail-closed-equivalent.
- **blog, listings** — clean; both views consume the orgs sanitizer seam; local copies and
  local tests deleted, tests moved-and-strengthened in orgs.
- **crm, forms, social** — conftest-only changes (SA97 adoption); clean.
- **auth, billing, notifications, storage, analytics, backups** — untouched this delta;
  carried clean at their live surfaces.
- **scripts/CI** — TA60 open here (TA61 closed by SA102). TP1 fan-out verified sound (per-worker exit-code
  retention via indexed join, reentrancy-guarded signal handler with descendant-tree kill,
  deterministic log replay, failure attribution per gate, serial escape hatch preserved);
  `test-cov` rewrite verified a strengthening (isolated per-phase data files, fail-hard on
  missing coverage data, policy checker still sole authority); `test_e2e.sh` lane namespacing
  verified scoped (label-filtered cleanup cannot touch another lane's containers; port
  validation on `QS_E2E_APP_PORT`).

## Clean sweeps worth recording (2026-07-19 pass)

- **SA100 closes TA58 correctly at the validator seam:** the exemption moved from caller-side
  string matching to an explicit `allow_recovery_checkpoint` parameter, sentinel-exact
  (`__checkpoint__`), source-exact (recovery label only), default-off — with tests pinning that
  the opt-in never exempts `quickscale.yml` or `state.yml`, that retired themes fail `up` with
  remediation, and that the checkpoint pass-through still reaches Docker dispatch.
- **SA98 sanitizer consolidation is byte-equivalent** (regex, allowlist, normalization order all
  identical to both deleted copies) and its relocated test suite is strictly stronger; the
  single-quoted-href limitation is now honestly pinned and remains unreachable at the live sink.
- **SA97's shared fixture is the superset of all six private copies** — no module lost reset
  coverage; blog/orgs/listings/social were upgraded from ContextVar-or-cache-only resets to the
  full GUC/ROLE/AF9-memo/cache contract.
- **The `test-cov` rewrite converts silent coverage-data loss into hard failure** — a missing
  phase data file, a failed combine, or a missing `coverage.json` now fails the target where the
  old append-based flow would have reported partial coverage as truth.
- **TP1's parallel fan-out preserves serial semantics** — every gate's exit code is retained and
  attributed even under multiple failures; DB-dependent stages never run after a static failure;
  `QS_CI_PARALLEL=0` reproduces the exact pre-TP1 behavior for debugging.
- **e2e cleanup is now lane-scoped** — the old global `docker ps | grep ':(8000|5432)->'` kill
  pattern (which could reap unrelated containers on a dev machine) is gone, replaced by
  compose-project-label and prefix filters.
- **Test-integrity (§3.7): no weakened or flipped tests** across every changed test file; the
  one widened assertion was empirically proven equivalent under the NULLIF-guarded policy.

## Structural smells (candidates for `arch-audit.md`)

- **Checkpoint/side-channel commits as the recurring anomaly lane — fifth consecutive pass:**
  `022a88fb` (SA93 checkpoint, prior delta) edited 4 theme templates without rebaselining the
  SA90 parity fixture; the gate stayed red for ~2 days until `1e7cbc2c` ("ci(sa93): align
  remote e2e gate") synced 8 hashes — correct in content (empirically verified) but landed
  under a CI-alignment message with no independent review of the rebaseline. The
  CHANGELOG/decisions coverage gate under Tooling gaps remains the ticket-shaped mitigation.
- **Frontend-source specialization** — owned by arch-audit Finding 10 (this pass); TA60 is its
  ticket-shaped gate companion. Not duplicated here.
- **Verbatim security-code copies:** the blog/listings sanitizer pair is **resolved** (SA98);
  the generated `get_client_ip` duplication remains (`base.py.j2:61` / `production.py.j2:123`)
  — carried.

## Tooling gaps

- **Frontend gate in CI** — ties to TA60 (this is the finding's fix, recorded here because it
  is the class-preventing check: `lint-frontend` in `ci.yml` + a publish dependency on the
  built-artifact proof).
- **CHANGELOG/decisions coverage gate for production commits** — carried (fifth pass of
  evidence: TA47/TA49/TA50/TA51 → TA53 → TA55/TA56 → TA58 → the SA90 red-window rebaseline).
- **DR status-literal conformance check** — carried (SA89b literal drift).
- **`pip-audit`/`safety` CI step** — carried; still no CVE signal source (this delta added
  pytest-xdist/execnet to the lockfile with no scanner in the loop).
- **`bandit`/`semgrep` CI step** — carried.
- **csrf_exempt gate matcher coverage** — carried.

Categories swept with no qualifying finding this pass (chain pass ran — one chain, on TA60):
injection/XSS (SA98 seam verified byte-equivalent; no new sink surface), auth/authz (no
authz-bearing code in delta), multi-tenant RLS (SA97 fixture *improves* GUC hygiene;
`RESET`-to-`''` semantics empirically confirmed fail-closed under NULLIF policies), concurrency
(TP1 fan-out and xdist adoption verified; no shared-state hazards — per-worker temp files,
per-lane Docker scopes), resource leaks/timeouts (worker temp dirs trap-cleaned; mktemp
coverage dir removed on EXIT), N+1/perf (no hot-path production code in delta), secrets (no
credential material committed; workflows unchanged on that axis), data handling (no
schema/migration changes), dependency CVEs (xdist/execnet additions; low confidence without a
scanner), CLI archetype (no new destructive paths; `up` strictly more fail-closed), generator
archetype (emission parity empirically green; TA60 owns the build-proof gap).

---

## Notes (not violations, watch items)

- **`ci.yml` does not run on integration-branch pushes** (triggers: push to main/develop, PRs
  to main): the entire v87 cycle is guarded by local `make ci` discipline only. Deliberate
  workflow shape for a solo maintainer, and local CI covers the same gates — but the SA90
  red window (see Structural smells) is the paid evidence of what it costs when a checkpoint
  commit skips the local gate. Watch; the ticket-shaped alternative (a lightweight push
  workflow on `v*` integration branches) is cheap if the pattern recurs.
- **SA68 persistent-misconfiguration cell:** carried — watch, don't fix.
- **Dev `docker exec` unsets `RUNTIME_DATABASE_URL`:** carried; still scoped to
  `development_commands.py`.
- **`quality_baseline.json` ratchet looser by ~550 entries (v87 re-baseline):** carried — now
  governed by the ratified Option A decision (remediate, per-entry shrink-only exemptions;
  SA101 open). Watch that the decision text reaches decisions.md with the first exemption.
- **Module `pyproject.toml`s no longer declare their real orgs dependency (SA81):** carried.
- **`forms_anonymize_submissions` single multi-org transaction:** carried.
- **Worker pool head-of-line blocking (SA91/CR-SA91-REV-006):** carried.
- **React `QuickScaleModules.auth` always typed/defaulted `false`:** carried (recorded
  maintainer decision).
- **Two same-named `ImproperlyConfigured` classes coexist** (SA69 decision): carried.
- **`test_update_auto_commits_each_module_e2e` mocks `_sync_module_dependencies`:** carried.
- **SA47 sole-member self-removal orphans the org (deliberate):** carried.
- **Stripe call inside the SA47 atomic block:** carried.
- **`reset_stale_restore` `None`-`restore_started_at` edge:** carried — unreachable.
- **`normalize_notifications_module_options` empty→full-defaults materialization:** carried.
- **Storage legacy-credential conversion is deliberate (SA29):** carried.
- `orgs/public_context.py:66,132` `except Exception → None` is fail-closed — carried.
- DR engine fallback modes are by-design recovery behavior — carried.
- Analytics missing-API-key silent disable is the deliberate SA17.7 shape — carried.
- `subprocess.Popen` in the dispatchers never `wait()`ed — carried.
- Malformed staff-authored validation rules surface as field-level 400s (SA40) — carried.
- **SA97 fixture's setup-phase `except RuntimeError: pass`** on the GUC reset is deliberate
  (tests without the `db` marker) and documented; test plumbing, not production — noted, not
  promoted.

---


## Reconciliation log (append-only)

- 2026-07-04 — TA1: resolved (SA17.1, `aea5e3bd` — legacy config keys now raise `ConfigValidationError`).
- 2026-07-04 — TA2: resolved (SA17.2–SA17.6 — module settings fail hard via startup guards/direct reads; residual `QUICKSCALE_MODE` defaults split out as TA19).
- 2026-07-04 — TA3: resolved (SA18.1, `e4183e52` — import-time `except Exception: pass` removed).
- 2026-07-04 — TA4: resolved (SA18.2 — analytics post-hook raises `ManifestError` on empty-after-resolution).
- 2026-07-04 — TA5: resolved (SA18.3, `ab32f272` — `quickscale_cli.schema` shim deleted).
- 2026-07-04 — TA6: resolved (SA18.4 — deterministic template resolution, no cwd guessing).
- 2026-07-04 — TA7: resolved (SA18.5 — version fallback narrowed; raises when unavailable).
- 2026-07-04 — TA8: resolved (SA18.6 — metadata resolution no longer swallows validation errors).
- 2026-07-04 — TA10: resolved (SA18.7 — railway_utils catches narrowed; unparseable output raises).
- 2026-07-04 — TA11: resolved (SA18.8 — non-numeric `PORT` raises `ValueError`).
- 2026-07-04 — TA13: resolved (SA18.9 — `step_capture_hashes` fails hard on `OSError`).
- 2026-07-04 — TA14: resolved (SA18.10 — `# F-EXCEPTION:` tags added and tabled in decisions.md).
- 2026-07-04 — TA15: resolved (SA18.11 — malformed module pyproject raises `TOMLDecodeError`).
- 2026-07-04 — **ID renumbering note:** the interrupted 2026-07-03 sweep briefly assigned TA16=`throttle-remote-addr-behind-proxy` (superseded by today's TA18), TA17=`railway-cli-secrets-on-argv` (dropped in renumbering — **reinstated 2026-07-05 as TA27**), TA18=`committed-coverage-artifacts` (renumbered TA23). Canonical IDs are the ones in this document.
- 2026-07-05 — TA9: resolved (SA17.7, `100f67d6` + `0ed70760` — analytics hard-imports posthog at module top; forms uses `apps.is_installed` guard + hard lazy imports; residual broad catch around the capture call is documented best-effort for a non-critical side effect, with regression tests).
- 2026-07-05 — TA12: resolved (SA17.8 — deprecated catalog delegates removed from public API; `get_module_readiness_reason` raises `ValueError` on unknown names).
- 2026-07-05 — TA16: resolved (SA19 — `start.sh.j2` prints per-variable `set`/`MISSING` status, never secret values).
- 2026-07-05 — TA17, TA18, TA21, TA22, TA24, TA25: still-open (every location re-verified against `a6706db1`).
- 2026-07-05 — TA26, TA27, TA28: opened this pass (TA27 is the reinstatement above); TA29 opened and resolved in the same closeout pass (SA33).
- 2026-07-05 (closeout) — TA29: resolved (SA33 — dangling `decisions.md:650` → `arch-audit.md` anchor link repointed to the arch-audit reconciliation log entry).
- 2026-07-05 (module-by-module deep pass) — TA30, TA31, TA32: opened. TA26 strengthened (storage-backend coercion joins the class as scenario 4). TA17 extended (admin backup-create/prune share the in-request execution; restore remains the anchor). Modules read deeply and found clean this pass: quickscale_core (DR engine, apply ledger/executor, state/locks/git), orgs (purge/migration commands, tenant-context machinery), quickscale_cli (update/remove snapshot-rollback flows, status/dev/deploy commands), billing, backups commands, notifications, crm.
- 2026-07-05 (closeout) — TA19: resolved (SA14.6 — QUICKSCALE_MODE fail-hard guard added in `QuickscaleOrgsConfig.ready()`, all 4 `getattr(settings, "QUICKSCALE_MODE", "solo")` callsites replaced with direct required reads).
- 2026-07-05 (closeout) — TA20: resolved (SA22 — same-filesystem staging with backup/swap/rollback for `apply --force`; generation to temp first, swap only on success, rollback on failure).
- 2026-07-05 (closeout) — TA23: resolved (SA25 — `coverage.json` and `pytest_cov_log.txt` removed from git tracking via `git rm --cached`; `.gitignore` patterns already present).
- 2026-07-05 (roadmap cleanup) — TA26: resolved (SA27 — `assemble_wiring_spec` now raises on non-empty `validation_issues`; missing `validate_{blog,forms,storage,orgs}_module_options` calls added to the apply-gate; silent coercions in `resolve_orgs_module_options`/`resolve_storage_module_options`/blog resolvers removed). TA30: resolved (SA28 — last-owner and personal-org invariants enforced at the account-deletion boundary via `AccountDeleteView.form_valid`, with subscription cancellation routed through the existing billing seam).
- 2026-07-06 — TA28: resolved (SA32 — retired `invalidate_social_cache()` from `quickscale_modules_social.services.__all__`; kept the helper importable for compatibility; no longer a public-API trap for bulk mutations).
- 2026-07-06 (roadmap cleanup) — TA27: resolved (SA31 — Railway/DR adapter secrets moved off process argv onto stdin transport; this closure was missed in the 2026-07-05 closeout pass and is corrected here).
- 2026-07-06 (re-run, HEAD `3056186a`) — **TA21: resolved** (SA23, `531386d9`/`20f01b88` — both debug views validate `next` via `url_has_allowed_host_and_scheme` against `request.get_host()`). **TA22: resolved** (SA24, `ba2c62da` — analytics JSON payload escapes `<`/`>`/`&` before `mark_safe`). **TA24: resolved** (SA21.1 — production `CACHES` active: Redis via `REDIS_URL`, `DatabaseCache` fallback — but the fallback's bootstrap gap opened as **TA33**). **TA31: resolved** (SA29, `4d1832fe` — credentials via `*_env_var` indirection, `__QS_ENV__` markers rendered as `os.environ.get()` with no credential material at rest, README rewritten to the real contract, cloud-backend env-var references validated at the apply gate; verified end-to-end adapter→wiring→template). **TA17: still-open, narrowed** to create/prune (restore async since SA20; severity S2→S3). **TA18: still-open, narrowed** to module callsites (DRF half fixed by SA21.1; residual is tracked SA21.2; severity S2→S3). **TA25: still-open at this pass** (location re-verified unchanged; resolved later the same day — see closeout entry below). **TA32: still-open** (location re-verified unchanged). **TA33–TA40: opened this pass** (TA33/TA35 are regressions-in-shape from SA21.1's new code; TA36/TA37 from SA20's new lifecycle; TA34 long-standing, exposed by SA28's guarded flow; TA39/TA40 accepted from arch-audit red-flag hand-off after independent verification).
- 2026-07-06 (closeout) — **TA36: resolved** (SA20 CR-SA20-REV-002 — `_atomic_claim_restore()` performs the DB-level compare-and-swap this finding asked for, `BackupArtifact.objects.filter(pk=..., status__in=eligible_set).update(status=STATUS_RESTORING, ...)`, on both admin dispatch branches; verified present in `backups/admin.py` directly. **CR-SA20-007: resolved** likewise — see Notes; the tracked gap and TA36 were both closed by the same SA20 closeout pass that this document's 2026-07-06 re-run had not yet picked up).
- 2026-07-06 (closeout) — **TA25: resolved** (SA26 — added `_sanitize_rendered_html()` to `blog/views.py` and `listings/views.py`, an allowlist URI-scheme check run on rendered markdown before the `|safe` filter; `javascript:`/`data:`/`vbscript:` links neutralized, including tab/newline/case-variant obfuscation per CR-SA26-001; `http(s)`/`mailto`/relative/fragment links preserved. 26 regression tests across both modules. Full detail in CHANGELOG.md).
- 2026-07-06 (module-by-module deep pass, core and cli included as modules) — **TA41 opened** (forms public-submit `TypeError`→500 on non-string JSON values, found reading the serializer/validator chain in full). Modules read deeply and found clean this pass: quickscale_core (DR primitives/recovery restore gate, module_wiring, generator + deploy templates — no dangerous sinks), orgs (tenant-context save/restore, `TenantManager`, last-owner model guards race-safe via Organization-row lock, invitation accept, permissions), billing (webhook idempotency + credit-grant unique-constraint rollback verified idempotent under concurrent duplicate delivery). Secondary items recorded inside existing findings rather than as new IDs: the concurrent-account-deletion last-owner race (folded into TA34), the staff-authored ReDoS via form-field `regex` rules (folded into TA41), and the staff-authored unvalidated YouTube/TikTok embed-id interpolation (`social/contracts.py:235,251` — same trust class as TA25, React-escaped at the sink, not promoted).
- 2026-07-06 (roadmap closeout) — **TA33: resolved** (SA34 — `createcachetable` added to `start.sh.j2` after the migrate step, gated behind `[[ -z "${REDIS_URL:-}" ]]` so it only runs when `DatabaseCache` is the active backend). **TA38: resolved** (SA39 — `operator_access()`/`_set_operator_access()` now raise `ImproperlyConfigured` when called outside an open transaction, instead of silently no-opping). **TA41: resolved** (SA40 — public form-submit validation now rejects non-string JSON values with 400s instead of an uncaught `TypeError`/500; the staff-authored ReDoS-via-`regex` residual noted when TA41 opened remains an accepted low-priority watch item, same trust class as the pre-SA26 TA25 pattern, not promoted to its own ID). **TA32: resolved** (SA30 — confirmed directly in code: `listings/views.py` and `storage/helpers.py` now raise `ImproperlyConfigured` on missing/invalid runtime settings instead of silently defaulting/coercing; this closure was flagged in `roadmap.md`'s 2026-07-06 triage note but not yet reconciled here — corrected in this pass). Findings-table counts updated (S2 2→1, S3 6→4, S4 3→2); full detail for all four lives in CHANGELOG.md (SA34/SA39/SA40) and the SA30 CHANGELOG entry.
- 2026-07-07 (roadmap cleanup) — **TA34: resolved** (SA35 — `Post.author`/`ContactNote.created_by`/`DealNote.created_by` changed `CASCADE`→`SET_NULL`; `OrganizationInvitation.invited_by`'s CASCADE documented as intentional in `decisions.md`; new `TestUserFkDeleteRuleConformance` cross-module gate closes the matching tooling gap below). **TA17: resolved** (SA37 — admin backup create/prune moved to background dispatch via `dispatch_background_create()`/`dispatch_background_prune()`, following the SA20/SA43 restore-dispatch pattern; restore itself was already resolved by SA20). **TA35: resolved** (SA36 — `get_client_ip()` guard changed to `len(ips) >= TRUSTED_PROXY_COUNT`, index to `ips[-TRUSTED_PROXY_COUNT]`, matching DRF's `NUM_PROXIES` semantics; landed before SA21.2 consumes the helper). Findings-table counts updated (S2 1→0, S3 4→2); full detail for all three lives in CHANGELOG.md (SA35/SA37/SA36 entries).
- 2026-07-07 (re-run, HEAD `1e618ed8`) — **TA18: resolved** (SA21.2, `3e48d04f` — shared canonical `get_client_ip()` added to `orgs/current_org.py`; blog API limiter ident (`blog/views.py:328`), forms `FormSubmission.ip_address` (`forms/views.py:231,257`), and `FormSubmitThrottle.get_ident` all switched off raw `REMOTE_ADDR`; verified in code. Residual: the helper's `getattr`-default settings reads opened as **TA43**). **TA37: resolved** (SA38, `16ede27a` — `is_restore_stale()` + CAS `reset_stale_restore()` in `services.py`, admin list column `stale_restore_warning` + guarded `reset_stale_restore_action`, stale-aware guidance on both upload-path guards (`services.py` + `orchestration.py` CR-SA38-001 parity); CAS verified unable to overwrite a concurrently finishing child. Residual: threshold-literal duplication opened as **TA45**). **TA39: resolved** (SA41, `2305591f` — `cancel_current_subscription` raises distinct `BillingSubscriptionAnomalyError` for the missing-Stripe-id case; `AccountDeleteView` logs it at WARNING with user/org identifiers and proceeds; `CancelSubscriptionView` maps it to 400; verified end-to-end). **TA40: still-open** (all four location groups re-verified byte-identical; SA42 scheduled on Track 3 — carried, not re-argued). **TA42–TA46: opened this pass** (TA42/TA43/TA44 accepted from arch-audit red-flag hand-off after independent verification; TA45/TA46 found reading the SA38/SA43 delta in full).
- 2026-07-07 (roadmap cleanup) — **TA42: resolved** (SA52 — `_get_manage_py()` now raises `BackupError` instead of swallowing resolution failure and falling back to a bare `"manage.py"` literal; the fail-hard raise happens before `_atomic_claim_restore`, so a resolution failure never leaves an artifact claimed; 5 regressions in `TestGetManagePySA52`). **TA43: resolved** (SA48 — `get_client_ip()` reads `USE_X_FORWARDED_FOR`/`TRUSTED_PROXY_COUNT` via direct required access, raising `ImproperlyConfigured` on missing/invalid values instead of silently defaulting). **TA44: resolved** (SA51 — `backups/services.py:1-10` header rewritten to state the real division of responsibility; no more false "under 400 LOC" claim). Findings-table counts updated (S3 1→0, S4 5→3); full detail for all three lives in CHANGELOG.md (SA52/SA48/SA51 entries). TA45 remains open (SA54 scheduled on Track 2, not yet landed); TA46 open (SA53 partial, short-write handling pending CR-SA53-REV-002).
- 2026-07-08 (docs cleanup) — **TA40: resolved** (SA42 — all four post-hook locations switched to direct required reads; 16 regression tests added. Full detail in CHANGELOG.md). Findings-table counts updated (S4 3→2); counts and status summary updated in this document.
- 2026-07-08 (doc-review follow-up) — **TA46: resolved** (SA53 + CR-SA53-REV-002 complete — the fd-based short-write retry loop replaces the interim `.tmp`+`os.replace` copy path from the initial SA53 fix. The final seam uses `mkstemp` for the fd, `os.write` in a `memoryview`-slicing retry loop, a single `finally: os.close(fd)`, and `except: os.unlink(tmp_path)` cleanup. `TestPrepareAdminUploadedRestoreArtifactSA53` covers copy-failure, happy-path, and short-write-retry regressions on the `mkstemp`+fd write path — 3 tests total. Full detail in CHANGELOG.md CR-SA53-REV-002 entry.) Findings-table counts updated (S4: 2→1).
- 2026-07-09 (re-run, HEAD `198a1951`) — **TA45: resolved** (SA54, `4b57c264` — `restore_admin_uploaded_backup` takes `stale_threshold_minutes` as a parameter; the admin caller passes `services.STALE_RESTORE_THRESHOLD_MINUTES` explicitly (`backups/admin.py:441-443`), so the canonical constant lives only in `services.py:554`. Residual noted, not promoted: the engine signature keeps a `= 30` default (`orchestration.py:2790`) — dead for the only live caller, but a future caller omitting the argument silently reintroduces the drift; consider making the parameter required). **TA47–TA52: opened this pass** — TA47 (S2) `dr-media-storage-fallback-swallows-misconfiguration`, TA48 (S3) `rls-boot-guard-misses-superuser`, TA49 (S3) `test-tooling-auto-primes-bypassrls-hatch`, TA50 (S3) `composite-fk-deferability-contract-diverged`, TA51 (S4) `test-artifacts-committed-again` (TA23 class), TA52 (S4) `module-pyproject-splice-unvalidated`. Four of the six (TA47, TA49, TA50, TA51) trace to the unreviewed CI-fix commits `6ea37301`/`198a1951` — see Structural smells. The SA42–SA56 review-tracked delta itself came through clean.
- 2026-07-10 (module-by-module deep pass, core and cli included as modules) — **zero new findings.** All 13 modules plus `quickscale_core` and `quickscale_cli` read at their live surfaces (see Per-module verdicts) — every module clean. TA47/TA48/TA50/TA51/TA52 re-confirmed at their locations during the pass (no change). Empirical check added: PostgreSQL 18 verified `SET CONSTRAINTS <name> IMMEDIATE` on a `NOT DEFERRABLE` FK is a no-op, retracting a stronger test-breakage hypothesis for TA50 (the crm `SET CONSTRAINTS ... IMMEDIATE` tests still pass; their comments are merely stale). Secondary items recorded inside existing findings rather than as new IDs: billing `credit_user` re-verified idempotent (in-lock check + unique constraint + `IntegrityError` re-fetch); notifications webhook re-verified HMAC+TTL+constant-time+idempotent; `TenantManager` fail-closed and `TenantMiddleware` fail-closed re-verified; `storage.sanitize_relative_media_path` exported but has no first-party caller (dead-ish, not promoted).
- 2026-07-10 (SA58 closeout) — **TA48: resolved** (SA58 — RLS boot guard now queries `rolbypassrls OR rolsuper`; error message reports SUPERUSER/NOSUPERUSER alongside BYPASSRLS/NOBYPASSRLS; test mocks and assertions updated; findings table and counts aligned). Findings-table counts updated (S3: 3→2, total: 6→5).
- 2026-07-10 (SA57/61/62 closeout, doc-consistency correction) — **TA47: resolved** (SA57 — both DR media call sites (`orchestration.py:_resolve_media_runtime`, `_sidecar.py:_build_media_sync_manifest`) now catch only `ImportError`/`ModuleNotFoundError` as the module-absent fallback; real `select_storage_backend` errors (`ImproperlyConfigured` etc.) propagate as `BackupConfigurationError`/an explicit error-status manifest instead of silently coercing to local `MEDIA_ROOT`; the flipped fail-closed test was restored and a second test pins the module-absent fallback). **TA51: resolved** (SA61 — `pytest_log.txt`, `coverage.json`, `pytest_cov_log.txt`, and the 13 accumulated blog test-upload PNGs untracked via `git rm --cached`; `.gitignore` extended; blog test `MEDIA_ROOT` now points at a tmp path so the class can't reaccrete). **TA52: resolved** (SA62 — `_patch_module_path_dependencies`'s bare `write_text()` now routes through `_write_validated_toml`, matching its two sibling writers). This entry corrects the findings-summary table above, which had drifted stale (still marking all three "open" despite CHANGELOG confirming SA57/SA61/SA62 landed on 2026-07-10) — caught during the roadmap-reconciliation pass for SA57–SA64. Findings-table counts updated (S2: 1→0, S4: 2→0, total: 5→2). Remaining open: TA49 (SA59), TA50 (SA60), both scheduled on Track 1.
- 2026-07-10 (V2-prompt re-run, HEAD `ae8c386e`) — **TA49: still-open** (Makefile:325-326, `scripts/test_unit.sh:365-366`, `ci.yml:340` all re-verified unchanged; SA59 scheduled). **TA50: still-open** (`tenancy.py:906` re-verified unchanged; SA60 scheduled). **TA53: opened** — `apply-subprocess-env-pythonpath-pollution` (S3, from side-channel commit `628c7d28`). **Closure verification per V2 §2f.3:** TA47 (SA57), TA48 (SA58), TA51 (SA61), TA52 (SA62) — each fix location opened and confirmed complete in code, including SA57's restored fail-closed tests; no regressed closures. Full first-party production diff `198a1951..HEAD` read; SA63/SA64 verified clean (SA63 additionally resolves the prior `local.py.j2` argv-sniffing watch item); the auth→orgs manifest implication in `628c7d28` verified justified (auth views import orgs models since SA47) though undocumented (Structural smells). Empirical check: simulated wheel-install layout confirms `_build_quickscale_env` sweeps site-packages-style directories into child `PYTHONPATH`, refuting its docstring (TA53 evidence). This is the first pass run under tech-audit-prompt V2.
- 2026-07-10 (roadmap cleanup) — SA69 closed: `decisions.md §ImproperlyConfigured-Exception-Identity` now records the exception-identity split; the adapter-docstring doc-drift flagged in the Notes section below is corrected. The lint/naming guard remains an open watch item per the decision record, not a defect. `roadmap.md` had left SA63 and SA69's checklist entries in place after both closed (already CHANGELOG-documented) — pruned there as part of this pass.
- 2026-07-11 (roadmap cleanup) — **TA53: resolved** (SA65 — `apply_command.py`'s dev-context `PYTHONPATH` env is now built on-demand via `_build_quickscale_env()` and passed only to the two nested `sys.executable -m quickscale_cli.main` invocations; the module-level `_QUICKSCALE_SUBPROCESS_ENV` import-time cache is removed; `_run_command` defaults to `env=None` so foreign subprocesses — poetry, git, docker, the generated project's own `manage.py` — inherit the parent env unmodified; the docstring's false production-safety claim is corrected). `TestSA65SubprocessEnvScoping` proves the scoping. Findings-table counts updated (S3: 3→2). Full detail in CHANGELOG.md (SA65 entry). This closes the tech-audit hand-off to arch-audit's matching red flag (`apply`'s import-time subprocess-env snapshot), reconciled there too.
- 2026-07-11 (V3-prompt re-run, HEAD `53a657d6`) — **TA49: resolved** (SA59.1 — verified in
  code per §2f.3: the blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export removed from both `Makefile`
  (module path now fail-louds) and `scripts/test_unit.sh` (module loop moved to
  `scripts/test_integration.sh`, which documents "No blanket QUICKSCALE_ALLOW_BYPASSRLS=1 here");
  `ci.yml`/`publish.yml` provision `quickscale_test_role` NOBYPASSRLS/NOSUPERUSER with attribute
  verification and run the integration gate with `QUICKSCALE_ALLOW_BYPASSRLS=0` + `QS_*_DB_USER`
  wiring — TA49's exact prescribed fix. Residual red-gate state opened separately as TA57;
  SA59.2–SA59.4 residuals tracked in roadmap.md, not here). **TA50: still-open**
  (`tenancy.py:900-906` re-verified byte-identical; SA60 scheduled). **TA53 closure verified in
  code** (see 2026-07-11 entry above — confirmed this pass per §2f.3). **TA54–TA57: opened this
  pass** — TA54 (S1) `org-creation-crm-seeding-fails-under-force-rls` (production-path defect
  exposed by SA59.1's restricted-role gate; concealed by TA55+TA57, see chain), TA55 (S3)
  `orgs-conftest-autouse-signal-muting` (checkpoint commit `2b9afa6b`), TA56 (S3)
  `session-adapter-fixture-swallows-improperlyconfigured` (quality-fix commit `fc3dc00c`), TA57
  (S3) `integration-gate-red-at-merge` (tracked SA59.1 state; quarantine recommended). TA55–TA57
  arrived as arch-audit red-flag hand-offs and passed independent verification; TA54 was found by
  pulling the thread behind TA55's docstring. Fix-regression pass run over SA65/SA66/SA68/SA69:
  clean (SA68's persistent-env cell recorded as a watch item, not a regression). First pass run
  under tech-audit-prompt V3.
- 2026-07-12 (roadmap closeout pass) — **TA54: resolved** (SA74 — `ensure_org_default_stages`
  primes tenant ContextVar across the helper scope and wraps `_seed_default_stages`'s INSERTs in
  `org_scope(organization)`, so the CRM receiver establishes its own tenant context regardless of
  caller; new regression test `test_seeds_without_ambient_org_context` proves seeding succeeds
  with zero ambient context under the restricted role). **TA55: resolved** (also SA74 — the orgs
  conftest's autouse `_mock_org_created_signal` fixture is removed and replaced with a non-autouse
  opt-in `mock_org_created_signal`, restoring the org-creation seam to real coverage in the orgs
  suite). **TA56: resolved** (SA75 — `_session_managed_adapters` now swallows only a genuine
  missing managed-package-root import and re-raises broken-adapter import failures, with the full
  adapter registry asserted in CI; two follow-up review passes, CR-SA75-REV-001/002, hardened the
  root-package-missing detection further). **TA57: resolved** (SA76 — a ticketed quarantine
  mechanism in `scripts/test_integration.sh` absorbs the two remaining known restricted-role
  failures (orgs → SA77, notifications → SA78, both resolved/tracked separately) so the
  integration gate is green for everything else; forms `0007`'s composite-FK piece was already
  resolved by SA60, so it needed no quarantine entry). **TA50: resolved** (SA60 — the composite-FK
  helper's `NOT DEFERRABLE` emission is now the ratified project-wide policy; `forms/0007`'s
  inlined SQL and its test were aligned to match, and a new cross-module conformance gate checks
  all six known composite FKs). Findings-table counts updated (S1 1→0, S3 4→0, total 5→0 — **zero
  open findings**). Two non-blocking follow-ups spawned by SA76's quarantine removal remain open on
   `roadmap.md`, not here: **SA77** (orgs' 9 restricted-role failures, root cause established and
   code fix landed 2026-07-12; final restricted-role verification blocked on SA79) and **SA79**
   (forms `0007` backfill data mismatch, distinct from the deferability contract SA60 already
    fixed; reopened/blocked on CR-PLAN-SA79-004 and CR-PLAN-SA79-005).
- 2026-07-13 (SA82 completed) — **SA77 and SA79: resolved.** SA82 removed the SA76 quarantine entries and ran the full `make test-integration` gate end-to-end. Orgs 847 passed/11 BYPASSRLS-skips/0 failed (93.04% coverage), notifications 39 passed/0 failed (91.76% coverage), overall mean coverage 92.95% passed. SA77's code fix (2026-07-12) verified live under the unquarantined gate; SA79's forms 0007 backfill and notifications acceptance confirmed under the full gate. Both are closed. Three independent restricted-role findings surfaced by the quarantine removal remain open on `roadmap.md` — **SA84** (CRM, 67 RLS failures/20 skipped) on Track 1, **SA85** (forms residual, 33 RLS failures/8 skipped/10 errors) and **SA86** (listings, 6 RLS failures) on Track 2 — not tech-audit findings, per this document's convention that roadmap-tracked work is not duplicated here. **SA83** (blog, 86 RLS failures) implementation/validation complete; closed after independent review. SA80.3b (backups rerun) resolved — see SA80.3b/SA87 reconciliation entry below. See CHANGELOG.md's SA82 entry for detail.
- 2026-07-13 (SA80.3b/SA87 reconciliation): SA80.3b rerun completed — 0 missing-`pg_dump`/`pg_restore` failures remain (retained-role: 298 passed/1 failed/2 skipped; default-user: 299 passed/2 skipped). SA80.3/SA80.3b resolved — no longer an open gate failure. The 1 retained-role residual is tracked as SA87 on roadmap.md §Track 3. Current open restricted-role findings keeping the integration gate red: SA84–SA86. SA83 closed after independent review. SA81 (per-module lockfiles, no deps) is unrelated cleanup; does not affect the gate. See roadmap.md for current status.
- 2026-07-13 (V3-prompt delta re-run, HEAD `41689be7`, prior `53a657d6`) — **zero new findings.**
  Full first-party production diff `53a657d6..HEAD` read (SA60/SA70/SA74/SA75/SA76/SA77/SA78/SA79/
  SA80/SA82/SA87 remediation + test/docs). **No prior findings to re-verify** — all TA IDs were
  already reconciled resolved as of the 2026-07-12 pass; none regressed (spot-checked SA74's
  `ensure_org_default_stages` and SA60's `NOT DEFERRABLE` emission still present in code).
  Fix-regression pass (§3.6): SA74 verified sound and complete (ContextVar + `org_scope` + AF9
  GUC-leak cleanup with correct attribute names; CRM is the sole `organization_created` receiver, so
  no sibling carries the TA54 class); SA70 `pre_delete` backstop verified to break no legitimate
  cascade path (account-deletion pre-check guards `user.delete()`; purge uses `_raw_delete`; no ORM
  `organization.delete()` cascade path exists); SA79/SA60 forms `0007` and SA80 CLI Poetry-env
  isolation verified sound. Test-integrity diff (§3.7): all delta test changes are strengthenings or
  SA59.2 PostgreSQL-seam adaptations — no weakened/flipped tests (the TA55 autouse muting removal is
  a strengthening). Chain pass (§3.9): no new chains. SA83–SA86 (restricted-role RLS failures),
  SA80.3, SA81 remain roadmap-tracked; structural root owned by arch-audit Finding 8
  (`module-rls-context-procedural`); not promoted here per convention. Empirical checks: still none
  possible — `psql`/`pg_isready` clients now installed but no PostgreSQL server running.
- 2026-07-14 (roadmap cleanup, status refresh) — **SA85 (forms residual restricted-role failures):
  closed** after independent review (CR-SA85-REV-001 resolved; `force_authenticate` session/org-context
  contamination fixed; forms 196 passed/8 skipped/12 e2e deselected/0 failed). The masthead/orientation
  prose above (dated 2026-07-13) that lists SA85 among the open gate-red findings is historical — the
  **current** roadmap-tracked findings keeping the SA82 integration gate red are **SA84** (CRM) and
  **SA86** (listings) only, both gated behind **SA88** (Finding 8 Option 1, in flight). Still no
  tech-audit finding: SA88's CRM triage bucketed 0 runtime-query failures (67 fixture-time), confirming
  no production-severity NOBYPASSRLS read-path gap. Not tech-audit findings per this document's
  roadmap-tracked convention; recorded here for status accuracy.
- 2026-07-17 (roadmap cleanup, status refresh — no fresh audit) — **the restricted-role cluster is
  fully drained; the SA82 integration gate is green.** SA92 (final-schema migration squash) emptied
  the cross-org-migration class; **SA84 (CRM) completed 2026-07-17** (263 passed/21 skipped/0 failed,
  independent review STATUS ok) and **SA86 (listings) closed 2026-07-15**, draining the fixture half.
  arch-audit **Finding 8 (`module-rls-context-procedural`) is now closed** (see arch-audit
  Reconciliation log tail). The only open roadmap item is **SA93** (fold the e2e lane into the
  green-gate), a Track 3 blocked checkpoint on deterministic fixes — not a tech-audit finding. This
  document remains at **zero open findings**; recorded here for status accuracy.
- 2026-07-17 (V3-prompt delta re-run, HEAD `09f9cbcc`, prior `41689be7`) — **TA58, TA59 opened
  (both S4); zero S1-S3.** Full first-party production diff `41689be7..HEAD` read (SA81/SA84/
  SA86/SA89a+b/SA90-msq/SA91/SA92/SA93/SA94/SA95/SA96 + SA88 retirement). No prior findings were
  open to re-verify. Closure/retirement claims verified in code per §2f.3: SA84 (CRM conftest
  GUC-restoration fix present and strengthening), SA86 (listings test fixes strengthening), SA88
  gate saga (zero `operator_access_migration` references remain), SA92 (squashed `0001_initial`s
  carry RLS RunPython + seeds; tripwire test present; hash-parity evidence recorded in
  decisions.md). Fix-regression pass (§3.6): SA89b port verified literal-by-literal against model
  constants (no drift; `ensure_default_policy` settings-precedence confirmed pre-existing, not a
  port regression); SA94 preflight fail-closed at all callsites *except* the SA93 checkpoint's
  `up` carve-out — opened as TA58; SA85 Phase 4 forms admin views verified role-correct with
  materialized responses inside `operator_access`; SA83 `_clear_priming_memo` verified at all
  three GUC-mutation sites. Test-integrity diff (§3.7): no weakened/flipped tests (13 added
  `skipif`s are PG-only catalog assertions still run under the integration gate; SA96 tightened
  default test roles to `quickscale_test_role`). Chain pass (§3.9): no chains. Empirical checks:
  TA58 confirmed in a REPL against a scratch project (retired-theme ledger error is single-line,
  so the exemption fires); `pg_isready` confirms a PostgreSQL 18 server is now running locally,
  retiring the standing no-DB-checks caveat. Watch items updated: mypy-backups weakening
  resolved; auth-orgs version-cap item retired by SA81; SA83-SA86 bucket-3 triage closed. Fourth
  consecutive pass in which the checkpoint lane carried the pass's defect (Structural smells).
- 2026-07-18 (SA100 closeout) — **TA58 and TA59: resolved.** SA100's source changes were accepted;
  the full change-review pass returned **STATUS ok**, with no findings and a caller-parity pass.
  Validation evidence: 53 targeted tests in 0.25s, Ruff check/format, and `git diff --check` all
  passed. Numeric coverage was not generated. No blockers remain. Findings-table counts updated
  (S4: 2→0, total: 2→0).
- 2026-07-19 (V3-prompt delta re-run, HEAD `82a73d1f`, prior `09f9cbcc`) — **TA60 (S3), TA61 (S4)
  opened; zero S1-S2.** Full first-party production diff `09f9cbcc..HEAD` read (SA97/SA98/SA99/
  SA100/SA93-closeout/TP1/TP2/TP3a + SA96 test checkpoint). **TA58/TA59 closure verified in code
  per §2f.3** (the 2026-07-18 log entry above was testimony from the SA100 review, not an audit
  pass): TA58 — `up` now calls `validate_theme_preflight(…, allow_recovery_checkpoint=True)` and
  the validator exempts only the exact `__checkpoint__` sentinel, only for the recovery-ledger
  source, only under the explicit opt-in (`theme_validation.py:228-234`), with regression tests
  pinning the retired-theme rejection at `up`; TA59 — `_RECOVERY_PROBE_PATHS` deleted. Both
  closures complete; no regression. Fix-regression pass (§3.6): SA98 byte-equivalent
  consolidation; SA97 superset fixture (no module lost reset coverage); SA100 exemption cannot
  be reached from config/state sources. Test-integrity diff (§3.7): no weakened/flipped tests;
  the `test_middleware.py:542` widening (`is None` → `is None or == ""`) empirically verified
  fail-closed-equivalent (PG18 `RESET` → `''`; NULLIF-guarded policies treat `''` as NULL).
  **TA60 opened** — `frontend-build-proof-ungated` (S3, accepted from the arch-audit 2026-07-19
  red flag after independent verification; narrowed by the discovered e2e docker-build layer,
  which compiles the frontend but sits on no publish-blocking path). **TA61 opened** —
  `devtools-gates-absent-from-ci` (S4, from `e862415a`; empirically verified devtools passes
  both gates today, so drift not concealment). Side-channel scrutiny (§2f.2): `1e7cbc2c`
  rebaselined 8 SA90 manifest hashes under a ci-alignment message — traced to `022a88fb`'s
  (prior delta) template edits that had left the parity gate red ~2 days; current fixture
  empirically re-verified green (19 tests); recorded as the fifth consecutive checkpoint-lane
  anomaly (Structural smells), not a finding (already fixed, fix verified). Chain pass (§3.9):
  one chain — TA60 × arch-audit Finding 10 (noted on TA60). Invoker-directed frontend-theme
  portability question answered by arch-audit Finding 10 (same-day pass); TA60 is this
  document's contribution.
- 2026-07-19 (roadmap cleanup) — **TA61: resolved** (SA102, `fdc88901` — explicit `--devtools`
  added to all ten scoped lint/typecheck invocations across `.github/workflows/ci.yml`,
  `.github/workflows/publish.yml`, and `scripts/check_ci_locally.sh`; the original five-site
  inventory was corrected to ten. A temporary Ruff violation in `quickscale_devtools/src` was
  verified to fail the lint and local-CI paths, then removed). Findings-table counts updated
  (S4: 1→0, total: 2→1). Full detail in CHANGELOG.md (SA102 entry). **TA60 remains open** —
  SA103 (frontend-proof gate) is its ticketed fix, rebalanced onto roadmap Track 1.
- 2026-07-19 (SA103 closeout) — **TA60: resolved** (SA103, `13b13ac5` — blocking `lint-frontend`
  job wired into `ci.yml` with Node/pnpm/cache setup, local `make ci` / `check_ci_locally.sh`
  frontend-lint fan-out with absent-Node/pnpm-only guard, and `make frontend-proof` step in
  `publish.yml` before downstream build/publish. Deliberate injected TypeScript error exited
  `make ci` 2 with TS2322/TS6133; template restored byte-identically; `make frontend-proof`
  passed. QG1 15 focused + bounded `make ci` (4,536 core/CLI, 323 backups, 92.88% mean, all
  files ≥80%); QG2 19 focused + six delta + Ruff/MyPy/YAML/workflow-order checks green.
  Independent change-review pass 2 **STATUS ok**; SA103-REV-001/002 and SA103-ADV-001 resolved.
  Hosted GitHub Actions not remotely observed (non-blocking residual caveat). Findings-table
  counts updated (S3: 1→0, total: 1→0). Full detail in CHANGELOG.md (SA103 entry) and
  roadmap.md (completed).
