# Tech Audit — Codebase-Wide Defect Sweep

> **Audit date:** 2026-07-10 (second pass of the day — V2-prompt re-run, delta pass) ·
> **Branch:** `v87` (HEAD `ae8c386e`) · **Prompt:** [tech-audit-prompt.md](tech-audit-prompt.md) (V2 — first run)
> **Mode:** re-run against the SA57–SA64 closeout delta (`198a1951..ae8c386e`, 57 files) plus the
> side-channel commit `628c7d28` ("fix: some make quality issues", 21 files, +435), which received
> elevated scrutiny per V2 §2f.2. Every closure claimed since the prior pass (SA57, SA58, SA61,
> SA62) was **verified directly in code** per V2 §2f.3 — all four confirmed complete. The two
> still-open prior findings (TA49, TA50) re-verified at their locations, unchanged. One new
> finding opened (TA53), from the side-channel commit. Prior IDs are stable; this document states
> **present reality for planning** — closed findings live only in the Reconciliation log at the
> bottom. Structural findings live in [arch-audit.md](arch-audit.md); fail-hard policy SSOT is
> [decisions.md §fail-hard-principle](../technical/decisions.md#fail-hard-principle).
> **Headline this pass:** the SA57–SA64 review-tracked fixes are all verified complete and
> well-scoped (SA63's `QUICKSCALE_ALLOW_BYPASSRLS` bridge is strictly command-scoped; the serving
> path stays fail-closed). The side-channel commit `628c7d28` again landed undocumented behavior
> changes — an auth→orgs manifest implication (justified: auth's views already import orgs
> models), a re-homed `ImproperlyConfigured` exception class, and a subprocess-environment change
> that is this pass's one new finding (TA53). No regression slipped through this time, but the
> unreviewed channel remains open (see Structural smells).

## Orientation summary

QuickScale is a **Python 3.13 Django project generator** (Poetry monorepo: `quickscale_core`
manifest/apply/generator/DR engine, `quickscale_cli` Click CLI, 13 shipped `quickscale_modules/*`
Django apps + an empty `teams` placeholder — decided 2026-07-10 as *not planned*, see
decisions.md §Teams module status — and Jinja2 generator templates; project version 0.87.0,
unreleased). Two deployment realities: **(a)** the *generated project* — an internet-facing Django
app targeting Railway (edge proxy → gunicorn, non-root container, fail-closed runtime DB role,
production settings enforce HTTPS/HSTS/secure cookies, active `CACHES`, trusted-proxy client-IP
with SA36 math); **(b)** the *CLI/generator* — a local developer tool, installable both from the
monorepo (Poetry) and via `pip install quickscale` (README:146). Trust boundaries unchanged from
the 2026-07-09/10 passes; one manifest-level change: **auth now declares
`required_modules: [orgs>=0.86.0]` and `implies: [orgs]`** (628c7d28), matching the code-level
dependency SA47 had already introduced (`auth/views.py:13` imports `quickscale_modules_orgs.models`)
— every auth project now pulls the orgs (→notifications) stack by design. Declared-invariant
oracle (V2 §2g) used for this pass: the fail-hard principle (decisions.md SSOT), the RLS runtime
role contract (`NOSUPERUSER`/`NOBYPASSRLS`, boot-guard enforced since SA58 on both attributes),
the launcher-owned env contract started by SA63 (`RUNTIME_DATABASE_URL`/`QUICKSCALE_ALLOW_BYPASSRLS`
pair, command-scoped), Option C child-table RLS, the csrf_exempt pairing gate (SA46), and the
artifact-hygiene rules (SA61). Tooling baseline: ruff + strict mypy in CI, csrf_exempt gate,
delete-rule and module-core compatibility/import gates, manifest sync gate; **still no
dependency-audit / bandit / semgrep step**.

**Coverage (this pass):** read in full — the entire first-party production diff
`198a1951..ae8c386e`: `apply_command.py` (`_build_quickscale_env` + `_QUICKSCALE_SUBPROCESS_ENV` +
nested-CLI invocation changes), `module_config.py` (`apply_listings_configuration` shim),
`module_wiring_manager.py` and `module_discovery.py` (`ImproperlyConfigured` re-homing),
`entry_point.py` (docstring + import updates), auth `module.yml` ×2 / `pyproject.toml` /
`__init__.py` (0.72.0 + orgs requirement), `orchestration.py`/`_sidecar.py` (SA57),
`orgs/apps.py` (SA58), `social/admin.py` complete (SA64), `local.py.j2`/`production.py.j2`/
`start.sh.j2` (SA63, full current DB-selection block and launcher script re-read),
`module_dependency_sync.py` `_patch_module_path_dependencies` complete (SA62), `.gitignore` +
blog test settings/conftest (SA61). Test-integrity diff (V2 §3.7) run over every changed test
file: backups `test_services.py` (fail-closed tests restored + module-absent fallback pinned —
strengthened), orgs `test_rls_boot_guard.py` (superuser cases added — strengthened),
implications/entry-point/discovery/wiring tests (coherent extensions of the auth→orgs change),
`test_apply_command*.py` (assertions flipped to bless auth→orgs — behavior change is justified,
see Clean sweeps), `test_e2e_full_workflow.py` (rework for auth+orgs embed),
`test_module_lifecycle_cycle.py` (new mock of `_sync_module_dependencies` in the update e2e —
noted as a watch item). Sampled — CHANGELOG/roadmap/decisions deltas for coverage cross-checks.
Skipped — module interiors (unchanged since the same-day 2026-07-10 deep pass; per-module
verdicts carried), `htmlcov/`, `graphify-out/`. **Empirical checks run:** simulated a wheel-install
layout (scratch dir with `quickscale_core/` subdir on `sys.path`) against `_build_quickscale_env`'s
scan logic — confirmed a site-packages-style directory **is** swept into the child `PYTHONPATH`,
refuting the function's own docstring claim (feeds TA53). Audit tools run: none available
(`pip-audit`/`bandit`/`safety` not installed; installs prohibited); dependency posture unchanged
via git — `poetry.lock` untouched since 2026-06-17 (`5ffa8cdc`).

**Clean sweeps worth recording (this pass — every closure verified in code, V2 §2f.3):**

- **SA57 verified:** both DR media call sites (`orchestration.py:1911-1923`,
  `_sidecar.py:54-68`) now catch `ModuleNotFoundError` with an **exact `exc.name` check** against
  the two storage-module names — even a missing storage *sub-dependency* fails hard; every other
  exception propagates as `BackupConfigurationError`/an `unsupported` manifest with `error_type`.
  The flipped test is restored fail-closed (`test_services.py:2899-2924, 2960-2974`) plus a
  second test pinning the module-absent fallback.
- **SA58 verified:** boot guard queries `rolbypassrls, rolsuper` and raises on either
  (`orgs/apps.py:99-111`); test mocks extended with superuser-only cases.
- **SA61 verified:** `git ls-files` shows no `pytest_log.txt`/`coverage.json`/test-media tracked;
  `.gitignore:221-222` covers the class; blog test `MEDIA_ROOT` is a `mkdtemp` path.
- **SA62 verified:** `_patch_module_path_dependencies` routes through `_write_validated_toml`
  (`module_dependency_sync.py:427`), matching its siblings.
- **SA63 verified across the config matrix (V2 §2h):** the bypass env pair is strictly
  command-scoped in `start.sh.j2:59` (shell-prefix assignment on the `createcachetable` line only;
  the `exec gunicorn` line carries neither); `production.py.j2`'s new bridge branch fires **only**
  on the explicit `RUNTIME_DATABASE_URL=""` + `QUICKSCALE_ALLOW_BYPASSRLS=1` combination and
  fail-hards when `DATABASE_URL` is missing; empty-without-flag and unset-with-flag both fall
  through to the pre-existing fail-closed serving raise. `local.py.j2`'s argv-sniffing branch is
  deleted — this resolves the prior "migrate detection looser than the boot-guard exemption"
  watch item.
- **SA64 verified:** both social admins inherit the already-audited orgs-owned `TenantModelAdmin`
  directly (VIEW-AS priority + org-field form-locking gained); the local `PerOrgAdminMixin`
  prototype is deleted; the admin test suite grew by ~213 lines.
- **auth→orgs implication verified justified:** `auth/views.py:13` imports
  `quickscale_modules_orgs.models` (introduced with SA47's account-deletion work), so
  auth-without-orgs was already a broken configuration; the 628c7d28 manifest change
  (`required_modules`, `implies`, 0.72.0 bump, orgs pyproject constraint `>=0.86.0,<0.87.0` —
  satisfied, orgs is 0.86.0) makes the manifest match reality. The associated apply/e2e test
  assertion flips are consistent with this intent, not concealment.
- **`ImproperlyConfigured` re-homing internally consistent:** the new
  `module_discovery.ImproperlyConfigured` (decoupling core's contract layer from Django) is
  raised at `module_discovery.py:115` and `entry_point.py:247,258` and caught only in
  `module_wiring_manager.py`, which imports the new class; no production catcher of Django's
  class wraps these paths (repo-wide search).

---

## Findings summary

| ID | Severity | Category | Title | Effort | Confidence | Status |
|----|----------|----------|-------|--------|------------|--------|
| TA49 | S3 | test-integrity / operability | `make test-unit` + `scripts/test_unit.sh` auto-prime `QUICKSCALE_ALLOW_BYPASSRLS=1`, contradicting the SA14.4 decision; CI's coverage gate inherits it | Small | High | open (SA59, Track 1, scheduled) |
| TA50 | S3 | data-handling / consistency | Composite-FK helper flipped to `NOT DEFERRABLE` undocumented — diverges from forms' asserted `DEFERRABLE` contract and from every existing database | Small | High (facts) / Medium (impact) | open (SA60, Track 1, scheduled) |
| TA53 | S3 | resources-I/O / correctness (CLI) | `quickscale apply` injects a cached import-time `PYTHONPATH` env into **every** subprocess — including poetry and the generated project's own Python — and its production-safety docstring claim is false for pip-installed CLIs | Small | High | open (new this pass) — quick win |

Counts: **S1: 0 · S2: 0 · S3: 3 · S4: 0.** TA49/TA50 scheduled (Track 1, roadmap.md); TA53 new, unscheduled.
Closure verification this pass: TA47 (SA57), TA48 (SA58), TA51 (SA61), TA52 (SA62) — all four confirmed in code.

---

## Findings detail

### S3 — compact

- **TA49 — `test-tooling-auto-primes-bypassrls-hatch`** · S3 ·
  `Makefile:325-326` (test-unit) and `scripts/test_unit.sh:365-366`, run by CI's repository
  coverage gate (`.github/workflows/ci.yml:340` — re-verified this pass). Both auto-export
  `QUICKSCALE_ALLOW_BYPASSRLS=1`, which (a) disables the orgs boot guard for every module suite
  and (b) flips the SA14.4 collection-time opt-in so `bypass_rls`-marked tests are always
  included. This directly contradicts the SA14.4 decision still documented at
  `quickscale_modules/orgs/tests/settings.py:14-18` and in every module conftest. On a dev machine
  whose role has BYPASSRLS, module suites pass with DB-level RLS unexercised and zero signal.
  Chains with the (resolved) TA48: no environment — CI or local — currently demonstrates the boot
  guard firing against a bypassing role; SA58's superuser extension widened what goes untested.
  **Fix:** remove the blanket export; create a NOBYPASSRLS role in CI (export `QS_*_DB_USER`) and
  let developers set the hatch explicitly per SA14.4, or scope the export to the specific suites
  that require it with a decisions.md amendment. Effort: Small. Confidence: High. Introduced in
  `6ea37301`. **Status:** open — scheduled as SA59 (Track 1).
- **TA50 — `composite-fk-deferability-contract-diverged`** · S3 ·
  `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py:906`
  (`_ADD_COMPOSITE_FK_SQL`). Flipped `DEFERRABLE INITIALLY DEFERRED` → `NOT DEFERRABLE` in
  `6ea37301`, undocumented, no test asserts the new behavior. Divergences: `forms/0007` inlines
  its own `DEFERRABLE INITIALLY DEFERRED` SQL and `forms/tests/test_migrations.py:457-505` asserts
  DEFERRABLE as "the contract" — forms and crm (0009, via the helper) now install different
  constraint semantics, and every *existing* database keeps DEFERRABLE while fresh ones get NOT
  DEFERRABLE (fleet drift, no migration aligns them). Behavioral edge: Django's
  `SET CONSTRAINTS ALL DEFERRED` (used by `loaddata`/fixture restore) no longer covers
  helper-created FKs, so out-of-order fixture loads fail on exactly these tables, differently per
  module and per database age. (Empirically verified 2026-07-10: `SET CONSTRAINTS <name>
  IMMEDIATE` on a NOT DEFERRABLE FK is a no-op, so the crm tests still pass — their comments at
  `crm/tests/test_migrations.py:1107,1158` are stale.) NOT DEFERRABLE is defensible fail-fast —
  but then it should be the *documented* Option C policy, applied uniformly with a migration and a
  conformance gate. **Fix:** pick one deferability policy in decisions.md, align helper + forms
  SQL + tests, extend the SA35-style conformance gate. Effort: Small. Confidence: High on facts,
  Medium on downstream impact. **Status:** open — scheduled as SA60 (Track 1).
- **TA53 — `apply-subprocess-env-pythonpath-pollution`** · S3 (deployment reality (b), CLI) ·
  `quickscale_cli/src/quickscale_cli/commands/apply_command.py:212-254`
  (`_build_quickscale_env` + module-level `_QUICKSCALE_SUBPROCESS_ENV`), applied at `:422`
  (`_run_command` — **every** apply subprocess) and `:627` (`_start_docker_impl`).
  **Defect:** the env — computed once at import time — adds every `sys.path` directory containing
  a `quickscale_core`/`quickscale_cli` subdirectory to the child `PYTHONPATH`, and `_run_command`
  passes it to *all* children: not just the two nested `sys.executable -m quickscale_cli.main`
  invocations it was built for, but also `poetry install`, `poetry lock`,
  `poetry run python manage.py migrate` (foreign interpreters in the generated project's own
  venv), `git`, and docker. The docstring's safety claim — "In production (packages installed in
  site-packages) these paths are not present in `sys.path`" — is **false**: site-packages *is* on
  `sys.path` and contains `quickscale_core/` after a `pip install quickscale` (a documented
  install path, README:146); empirically confirmed via a simulated wheel layout. **Failure
  scenario:** pip-installed CLI runs `quickscale apply` → children get
  `PYTHONPATH=<CLI venv site-packages>` → since `PYTHONPATH` precedes a venv's own site-packages,
  the generated project's `manage.py migrate` resolves Django/psycopg/etc. from the **CLI's**
  venv wherever versions overlap-but-differ, and pipx-installed poetry runs with the CLI's copies
  of its shared deps — wrong-version migrations and hard-to-diagnose breakage. Secondary angles:
  the import-time `os.environ.copy()` snapshot drops any later env mutation for all children (no
  first-party mutator exists today), and the scan is an import-time filesystem side effect.
  **Refutation attempted:** searched for a layer-up filter (none — `_run_command` applies the env
  unconditionally); checked whether children need the paths (poetry/git/docker never import
  quickscale; generated projects contain no `quickscale_core`/`quickscale_cli` imports — template
  grep clean); checked for a blessing (no test asserts propagation to foreign interpreters, no
  CHANGELOG/decisions coverage — the docstring itself is the only defense and it is factually
  wrong). **Fix:** build the env lazily and pass it only to the two nested `quickscale_cli.main`
  invocations; additionally (or alternatively) skip path entries where the packages are already
  importable by a bare child (site-packages case). Effort: Small — **quick win**. Confidence:
  High (mechanism verified empirically; installed layout documented). Age: fresh —
  `628c7d28`, 2026-07-10, the side-channel commit.

---

## Per-module verdicts (carried from the 2026-07-10 deep pass, same day)

The module-by-module deep pass earlier today read each module's live surface in full with zero
new findings; this delta pass re-read only what the delta touched (orgs `apps.py`, social
`admin.py`, auth manifest/version files, backups/DR fix sites). Verdicts carried unchanged:

- **forms, blog, listings, notifications, social, storage, analytics, auth, crm, billing,
  backups, orgs** — clean at their live surfaces (see the 2026-07-09/10 entries in the
  Reconciliation log and version control for the full per-module rationale).
- **quickscale_core** — clean; this pass re-verified the DR media seam (SA57) and the generator
  templates (SA63).
- **quickscale_cli** — clean except TA53 (this pass, `apply_command.py` subprocess env).

---

## Structural smells (candidates for `arch-audit.md`)

- **Side-channel commits as an unreviewed change lane — second consecutive pass:** `628c7d28`
  ("fix: some make quality issues") landed a product-visible manifest change (auth→orgs→
  notifications implication), an exception-class re-homing across the core contract layer, and a
  subprocess-environment change (TA53) — none with CHANGELOG or decisions.md coverage, while
  every SA-tracked change in the same window got both. This time the changes were individually
  defensible (the implication matches a real code dependency) and only TA53 qualified as a
  defect, but the channel that produced TA47/TA49/TA50/TA51 last pass remains open. The
  CHANGELOG-coverage gate under Tooling gaps below is the ticket-shaped mitigation.
- **Deletion invariants enforced per boundary:** carried — domain-level `pre_delete` backstop
  still absent; see arch-audit `deletion-invariants-per-boundary-reimplementation` (deferred:
  teams not planned).
- **No single "how does a generated app get configured at deploy time" contract:** carried —
  SA63 landed the first step of the launcher-owned env contract (Option 1); the remainder
  (production settings as pure env reader, `_is_migrate_command()` removal) stays deferred in
  arch-audit.md Finding 6.
- **Verbatim security-code copies accumulating:** carried — SA26 `_sanitize_href` pair still
  duplicated in blog/listings; the generated `get_client_ip` remains duplicated across
  `base.py.j2`/`production.py.j2`.

## Tooling gaps

- **CHANGELOG/decisions coverage gate for production commits** *(new)* — a CI check that fails
  when a commit touches production source (`quickscale_*/src`, templates, manifests) without a
  CHANGELOG entry in the same series would close the side-channel lane that produced
  TA47/TA49/TA50/TA51 (last pass) and TA53 (this pass) as a class.
- **`pip-audit`/`safety` CI step** — carried; no dependency-CVE gate; the lockfile read stays
  manual and low-confidence (lockfile unchanged since 2026-06-17).
- **`bandit`/`semgrep` CI step** — carried; would systematically catch the `except Exception:` +
  fallback-assignment shape (TA47's class) and the argv/redirect classes as they recur.
- **Tracked-artifact gate** — a CI check failing when `git ls-files` matches artifact patterns
  (`pytest*_log.txt`, `coverage.json`, `*/tests/media/`, `htmlcov/`) — SA61 fixed the instances
  and the `.gitignore`; the gate would prevent re-accretion (TA51/TA23 class).
- **Composite-FK conformance gate** — extend the SA35-style cross-module gate to assert one
  deferability policy for all Option C composite FKs (ties to TA50/SA60).
- **Generated-project boot smoke test** — carried, partially mitigated: SA63's closeout verified
  a generated project end-to-end on the production-settings + orgs path manually, and
  `test_generated_project_runtime.py` grew substantially (+395 lines this delta); a standing CI
  boot smoke remains the systematic version (TA33's class).
- **csrf_exempt gate matcher coverage** — carried; attribute-form usage, list/tuple
  `method_decorator` arguments, and URLconf-level wrapping still slip the matcher (no live usage
  today).

Categories swept with no qualifying finding this pass (V2 §3.9 chain pass ran — no new chains
beyond TA49's carried guard-untested chain): injection/XSS (no new sink surface; templates
re-read under output-language rules — shell quoting in `start.sh.j2` sound), auth/CSRF (SA64
inherits the audited `TenantModelAdmin`; no endpoint changes), concurrency (no new locks or
shared state; `_QUICKSCALE_SUBPROCESS_ENV` is read-only after init), resource leaks, timeouts,
N+1/perf, data-handling boundaries (SA63 bridge fail-hards on missing `DATABASE_URL`),
dependency CVEs (lockfile unchanged; low confidence without a scanner), weakened tests (every
assertion flip in the delta traced to the justified auth→orgs change; the one true weakening is
the `_sync_module_dependencies` mock, noted below).

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
- 2026-07-10 (V2-prompt re-run, HEAD `ae8c386e`) — **TA49: still-open** (Makefile:325-326, `scripts/test_unit.sh:365-366`, `ci.yml:340` all re-verified unchanged; SA59 scheduled). **TA50: still-open** (`tenancy.py:906` re-verified unchanged; SA60 scheduled). **TA53: opened** — `apply-subprocess-env-pythonpath-pollution` (S3, from side-channel commit `628c7d28`). **Closure verification per V2 §2f.3:** TA47 (SA57), TA48 (SA58), TA51 (SA61), TA52 (SA62) — each fix location opened and confirmed complete in code, including SA57's restored fail-closed tests; no regressed closures. Full first-party production diff `198a1951..HEAD` read; SA63/SA64 verified clean (SA63 additionally resolves the prior `local.py.j2` argv-sniffing watch item); the auth→orgs manifest implication in `628c7d28` verified justified (auth views import orgs models since SA47) though undocumented (Structural smells). Empirical check: simulated wheel-install layout confirms `_build_quickscale_env` sweeps site-packages-style directories into child `PYTHONPATH`, refuting its docstring (TA53 evidence). This is the first pass run under [tech-audit-prompt.md](tech-audit-prompt.md) V2.

## Notes (not violations, watch items)

- **Two same-named `ImproperlyConfigured` classes now coexist** (new, 628c7d28):
  `quickscale_core.contracts.module_discovery.ImproperlyConfigured` (contract layer, non-Django)
  vs `django.core.exceptions.ImproperlyConfigured` (module runtime). All current raise/catch
  pairs are consistent, but a future catcher importing the wrong one fails silently open —
  worth a naming or lint guard if it recurs. The billing/crm/social adapter docstrings still
  cite the Django class for the entry-point contract that now raises the contract-layer class
  (doc drift only).
- **`test_update_auto_commits_each_module_e2e` now mocks `_sync_module_dependencies`**
  (628c7d28, `test_module_lifecycle_cycle.py:1298-1302`): the update e2e no longer exercises
  dependency sync. Coverage moved rather than lost (SA62 added `TestBetaMigration` sync suites,
  +147 lines), but the e2e is weaker than its name implies — watch.
- **auth's orgs pyproject cap `<0.87.0`** (628c7d28): satisfied today (orgs 0.86.0); when orgs
  bumps to 0.87.x the cap must move with it — the dependency-sync tooling should handle it, but
  nothing gates the pair.
- **SA47 sole-member self-removal orphans the org (deliberate, watch):** carried — an owner who
  is the org's only member may remove themselves, leaving a memberless org reachable by no one;
  documented and test-asserted as chosen; no cleanup/purge path yet.
- **Stripe call inside the SA47 atomic block:** carried — `AccountDeleteView.form_valid` holds
  `select_for_update` locks across the external Stripe call; acceptable at account-deletion
  frequency; a client timeout is the cheap mitigation.
- **`reset_stale_restore` `None`-`restore_started_at` edge** (`services.py:590-649`): carried —
  unreachable from the only caller (pre-filtered by `is_restore_stale()`).
- **`normalize_notifications_module_options` empty→full-defaults materialization**
  (`contracts/module_options.py:555-562`): carried — documented implied-module support at the
  manifest boundary; watch that the pattern doesn't migrate into runtime settings reads. The new
  `apply_listings_configuration` shim (628c7d28) is display-only (echoes defaults-merged values,
  persists nothing) — same boundary, no state coerced.
- **Storage legacy-credential conversion is deliberate:** carried (SA29 migration behavior).
- `orgs/public_context.py:66,132`: `except Exception → None` on system-org lookup is
  **fail-closed** — carried; consider letting non-`DoesNotExist` errors propagate.
- DR engine fallback modes (`REMOTE_FALLBACK`, JSON fallback backups, `QUICKSCALE_ENVIRONMENT`
  default `local`) are by-design recovery behavior, exempt per §fail-hard-principle — carried.
- Analytics runtime missing-API-key → silent disable (`services.py:192-203`) is the deliberate
  SA17.7 shape — carried, tested.
- `subprocess.Popen` in the dispatchers is never `wait()`ed — carried; at most one transient
  zombie per dispatch.
- Malformed staff-authored validation rules surface as field-level 400s to public submitters
  (SA40) — carried, reviewed choice.
- *(resolved this pass, removed from watch:)* the `local.py.j2` "migrate detection looser than
  the boot-guard exemption" item — SA63 deleted the argv-sniffing branch entirely.
