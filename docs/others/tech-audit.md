# Tech Audit — Codebase-Wide Defect Sweep

> **Latest re-run:** 2026-07-17 (V3 delta pass) · **Branch:** `v87` (HEAD `09f9cbcc`, prior
> `41689be7`) · **Result: two S4 findings (one quick-win), zero S1–S3 — near-clean pass.**
> History of prior passes is preserved in the Reconciliation log below and in this file's git
> history; per this document's convention, closed findings live only in the log.
>
> **Original masthead:** audit date 2026-07-11 (first run on the V3 prompt) · **Prompt:**
> tech-audit-prompt (V3). Structural findings live in [arch-audit.md](arch-audit.md); fail-hard
> policy SSOT is [decisions.md §fail-hard-principle](../technical/decisions.md#fail-hard-principle).
>
> **This pass (2026-07-17, delta `41689be7..HEAD`, 144 commits, ~227 files, +24.8k/−12.3k):**
> the delta carries the v87 closeout batch — **SA89a/b** (DR persistence port), **SA90-msq/SA92**
> (final-schema migration squash across all nine modules), **SA91** (parallel integration worker
> pool), **SA93** (e2e green-gate, still a blocked checkpoint), **SA94** (showcase_html theme
> retirement), **SA81** (monorepo dependency cleanup), **SA84/SA86/SA95/SA96** (restricted-role and
> module test sweeps), plus the SA88 gate-saga retirement. The full first-party production diff was
> read; checkpoint/side-channel commits (`022a88fb`, `76c5cc55`, `4ba4ad32`, `6961d651`, `ddfa6daa`,
> `a561e8fd`) received elevated scrutiny per §2f.2 — and, for the fourth consecutive pass, the
> checkpoint lane is where this pass's defect lives (TA58, from SA93 checkpoint `022a88fb`).
> Test-integrity diff (§3.7) run across every changed test file: no weakened or flipped tests.
> Closure claims verified in code per §2f.3 (SA84, SA86, SA88-retirement, SA92 — all confirmed).
> Chain pass (§3.9) ran: no chains. **A PostgreSQL 18 server is running on this machine for the
> first time across audit passes**, closing the standing "no empirical DB checks possible" caveat;
> one REPL empirical check was run this pass (TA58 confirmation).

## Orientation summary

QuickScale is a **Python 3.13 Django project generator** (Poetry monorepo: `quickscale_core`
manifest/apply/generator/DR engine, `quickscale_cli` Click CLI, 13 shipped `quickscale_modules/*`
Django apps, `quickscale_devtools` beta-migration tooling, Jinja2 generator templates; version
0.87.0, unreleased). Two deployment realities: **(a)** the *generated project* — an internet-facing
Django app targeting Railway (edge proxy → gunicorn, non-root container, fail-closed runtime DB
role, HTTPS/HSTS/secure cookies, active `CACHES`, SA36 trusted-proxy client-IP, SA68 one-shot
privileged-command env contract); **(b)** the *CLI/generator* — a local developer tool (monorepo
Poetry or `pip install quickscale`; only `quickscale_core`/`quickscale_cli`/`quickscale` are
published to PyPI — modules ship via the generator, not as standalone wheels). Major deltas this
pass: **SA92** squashed every module's migration history to a single final-schema `0001_initial`
(`organization_id NOT NULL` from row zero; ratified fresh-only posture, decisions.md
§Migration-Squash Decision; pg_policies/catalog/data hash parity against the v87 baseline is the
authoritative proof, plus a bounded literal tripwire); **SA89a/b** moved all backups ORM lifecycle
edges behind a fail-hard persistence provider registry (`dr_engine/persistence.py` protocols +
`quickscale_modules_backups/persistence.py` providers registered in `AppConfig.ready()`); **SA94**
retired the `showcase_html` theme with a fail-closed read-only preflight
(`utils/theme_validation.py`) wired into 8 CLI callsites and the beta-migration tool; **SA91**
parallelized the module integration gate behind `QS_INTEGRATION_JOBS` with validated bounds,
per-worker coverage files, and signal-tree cleanup; **SA93** replaced the raw coverage threshold
with a fail-closed dual-threshold policy checker (`scripts/check_coverage_policy.py`, 90%
equal-weight core/CLI package mean + 80% per-file, own 37-test suite). Declared-invariant oracle
used this pass: the fail-hard principle (decisions.md SSOT), the RLS runtime-role contract
(NOSUPERUSER/NOBYPASSRLS, SA58 boot guard), the SA68 one-shot launcher env contract, Option C
child-table RLS with the NULLIF-guarded GUC policy, SA14.4/SA14.5 (no auto-primed BYPASSRLS;
`operator_access` is SELECT-only), the SA94 theme-preflight invariant ("if any present file
carries an invalid theme, the preflight fails regardless of what other valid sources say" —
violated by TA58), and the SA92 squash guardrail (parity gate + tripwire). Tooling baseline:
ruff + strict mypy in CI (the backups module-override weakening flagged last pass is **removed**
— replaced by a narrow per-file `var-annotated` suppression and a legitimate third-party
`storages.*` ignore), csrf_exempt/delete-rule/module-core/manifest-sync/SA60-composite-FK/SA66
gates, new worker-pool and coverage-policy test suites in CI; **still no
dependency-audit / bandit / semgrep step**.

**Coverage (this pass):** read in full — the entire first-party production diff
`41689be7..HEAD`: `dr_engine/persistence.py` (new), `quickscale_modules_backups/persistence.py`
(new), `_dr_remote_storage.py` (new), `orchestration.py` (full port diff), `adapter.py`,
`_sidecar.py`, `_paths.py`, `recovery.py`, `runtime/__init__.py` + `runtime/dr.py` (eager-import
switch), backups `apps.py`/`admin.py`/`models.py`/`services.py`/`dr_adapter_call.py`,
`utils/theme_validation.py` (new, complete), `generator/generator.py` emission-mapping diff,
`config_schema.py`, `urls.py.j2`/`views.py.j2`/React theme template diffs, all 8 CLI command
diffs (apply/plan/remove/module/module_config/dr/development/module_wiring_manager),
`beta_migration.py` diff, `orgs/current_org.py` (SA83 `_clear_priming_memo`), `blog/views.py`
(token-auth org-context save/restore), `forms/views.py` (SA85 Phase 4 retained-role helpers) +
`notifications.py` + both management commands, `listings/models.py`, the orgs/forms/crm squashed
`0001_initial` structure (RLS RunPython, seed RunPython, system-org handling verified),
`scripts/_qs_jobs.sh` (complete), `test_integration.sh` diff, `check_coverage_policy.py`
(complete), `check_module_core_imports.py` diff, `check_ci_locally.sh` diff, `Makefile`,
`mypy.ini`, `ci.yml`/`e2e.yml`/`publish.yml` diffs, module `pyproject.toml`/`poetry.toml`
changes (SA81). Sampled — the ~100 changed test files via targeted §3.7 scans (all added
`skipif` markers enumerated — every one is a PostgreSQL-only catalog/RLS assertion in the
squash-rewritten migration tests, still exercised under the PG integration gate; all added
autouse fixtures enumerated — context resets, persistence-registry resets, and an S3Storage mock
at the unit seam; SA84/SA86/SA96 test commits read as diffs and found strengthening),
`quality_baseline.json` (advisory-tool re-baseline, see Notes), CHANGELOG/roadmap/decisions
deltas for blessing checks. Skipped — module interiors unchanged since the 2026-07-10 deep pass
(verdicts carried), `htmlcov/`, `graphify-out/`, `poetry.lock` (7-line metadata change only; no
scanner available). **Empirical checks:** (1) REPL run of `validate_theme_preflight` against a
scratch project with a retired `showcase_html` theme in `.quickscale/apply-recovery.yml` —
confirmed the error is single-line and matches the `up` command's "recovery ledger" exemption,
so `quickscale up` proceeds silently (TA58, confidence High). (2) `pg_isready` — a PostgreSQL
server **is** running on localhost:5432 this pass (first time). Audit tools run: none available
(`bandit`/`pip-audit`/`semgrep` absent, installs prohibited).

---

## Findings summary

| ID | Severity | Category | Title | Effort | Confidence | Status |
|----|----------|----------|-------|--------|------------|--------|
| TA58 | S4 | correctness / declared-invariant | `quickscale up` recovery-ledger theme exemption is broader than its `__checkpoint__` rationale | Trivial (quick win) | High (empirically confirmed) | open |
| TA59 | S4 | dead code | `theme_validation._RECOVERY_PROBE_PATHS` is defined but never used | Trivial | High | open |

Counts: **S1: 0 · S2: 0 · S3: 0 · S4: 2.**
Chain pass (§3.9): ran — no chains (TA58 affects only dev-CLI `up` messaging; no security or
data-path composition with any watch item or crown jewel).

---

## Findings detail

**TA58 — `up-recovery-ledger-theme-exemption-overbroad` (S4, quick win).**
Location: `quickscale_cli/src/quickscale_cli/commands/development_commands.py:281-303` (`up`).
Deployment reality: CLI/dev tool. Defect: the SA93 checkpoint commit `022a88fb` softened the SA94
theme preflight for `quickscale up` — when *all* preflight errors mention "recovery ledger", the
error is silently ignored (`only_recovery = all("recovery ledger" in line ...)`). The comment
justifies this only for the `__checkpoint__` placeholder the apply executor writes
(`quickscale_core/apply/executor.py:301-303`), but the string-match exempts **any** single-line
recovery-ledger error: a stale ledger carrying retired `showcase_html`, or a ledger missing
`project.theme` entirely, now passes `up` with **no message at all** — violating
`theme_validation.py`'s declared invariant ("config-first identity fallback must not mask an
invalid … recovery source"). Empirically confirmed (REPL, this pass): the retired-theme ledger
error is one line containing "(recovery ledger)", so `only_recovery=True`. Refutation attempted:
no layer-up guard re-validates theme on the `up` path; no test anywhere pins the exemption (grep:
zero hits for the behavior in `quickscale_cli/tests/`); the blessing is a *pre-review* checkpoint
(roadmap explicitly lists "independently review the complete SA93 delta" as pending) — none
survived. Multi-line ledger errors (e.g. YAML parse failures) stay fatal, so the hole is
narrow — hence S4, not S3. Fix: key the exemption on the placeholder, not the source label —
have `validate_theme_preflight` (or a variant flag) treat only `theme == "__checkpoint__"` in the
recovery ledger as exempt, or plumb per-error `theme` attributes through the aggregate error and
check `exc.theme == "__checkpoint__"`. Also fix the two `.quickscape` typos in the adjacent
comments. Verification: a test that `up` fails (with remediation text) on a recovery ledger
carrying `showcase_html`, and proceeds on one carrying `__checkpoint__`. Age: introduced
2026-07-17 (`022a88fb`, SA93 checkpoint) — a candidate to fold into SA93's pending independent
review rather than a separate PR.

**TA59 — `theme-validation-dead-probe-constant` (S4).**
`quickscale_core/src/quickscale_core/utils/theme_validation.py:70-73` — `_RECOVERY_PROBE_PATHS`
is defined ("paths whose presence triggers the preflight recovery-ledger check") but referenced
nowhere in the repo; the preflight probes `_RECOVERY_FILE` directly. Delete the constant (or wire
it if a probe was intended). Trivial.

---

## Per-module verdicts

Module interiors unchanged since the 2026-07-10 deep pass; verdicts carried except where this
delta touched them:

- **quickscale_core** — production clean. SA89a/b persistence port verified a faithful,
  fail-hard refactor (see Clean sweeps); SA94 generator/theme removal verified fail-closed;
  SA92 squash machinery (tripwire + parity evidence) verified present; `config_schema.py`
  `VALID_THEMES` narrowed with actionable retired-theme messaging. TA59 (dead constant) opened
  in `utils/theme_validation.py`.
- **quickscale_cli** — TA58 opened (`development_commands.py`, SA93 checkpoint). All other SA94
  preflight callsites (apply/plan/remove/module/dr/module_wiring_manager) are fail-closed;
  `apply`'s preflight validates the supplied config *and* the actual output root, and its broad
  raw-YAML catch defers to the fail-hard schema loader immediately after (documented, benign).
  The new `-e RUNTIME_DATABASE_URL=` on dev `docker exec` calls is a documented dev-only
  convenience (see Notes).
- **quickscale_devtools** — clean; beta migration gained donor+recipient theme preflight with
  explicit check records and blockers (fail-closed).
- **backups** — clean; persistence providers are faithful ports (trust chain for admin-uploaded
  restore artifacts preserved verbatim; `ensure_default_policy`'s settings-precedence overwrite
  is byte-identical pre-existing behavior, not a port regression); models diff is mypy casts
  only.
- **orgs** — clean; `_clear_priming_memo` (SA83) verified: every GUC mutation
  (`_set_db_current_org_id`, `reset_db_current_org_id`, `_restore_current_org_id`) clears the
  per-transaction priming memo in a `finally`, so the next wrapped statement re-primes. Squashed
  `0001_initial` carries no module-table policy by design (tenant modules are authoritative for
  their own policies); the deleted `0002_system_org` seed is safe — `get_system_org()` is
  create-on-demand, idempotent, and race-guarded.
- **forms** — clean; SA85 Phase 4 admin views verified: superuser cross-tenant reads run under
  `operator_access` inside `transaction.atomic()` with fully-materialized responses (CSV export
  builds the body inside the scope — no lazy-evaluation escape); regular staff are org-scoped or
  fail-closed (`objects.none()`); PATCH saves inside `org_scope(instance.organization)`. Both
  management commands follow the read-via-`operator_access` / write-via-`org_scope` pattern.
  Squashed `0001_initial` seeds presets + System org at migrate time (matches README).
- **blog** — clean; token-auth org-context side effect of `_resolve_api_org` is documented and
  both callers save/restore the ContextVar in `finally` with vendor+`in_atomic_block`-guarded
  GUC restore.
- **listings** — clean (index additions matching the squashed migration; SA86 test fixes are
  strengthenings).
- **auth, billing, crm, notifications, social, storage, analytics** — carried clean at their
  live surfaces; this delta touched only squashed migrations (verified), test strengthenings
  (SA84/SA96), and SA81 metadata.
- **scripts/CI** — clean; `_qs_jobs.sh` worker pool verified (input validation incl. leading-zero
  and 64-bit overflow rejection, eligible-count capping, per-worker `COVERAGE_FILE` isolation,
  INT/TERM/HUP descendant-tree cleanup); `check_coverage_policy.py` verified fail-closed (exit 2
  on malformed data, missing packages, traversal paths); `check_ci_locally.sh` replaced its unit
  stage with `make test-cov REQUIRE_BACKUPS_COVERAGE=1` (tests still run, coverage now gated
  fail-closed when backups deps are absent).

## Clean sweeps worth recording (2026-07-17 pass)

- **SA89a/b persistence port is a faithful, fail-hard refactor:** every model-constant→literal
  substitution verified against `models.py` (all of `"ready"/"failed"/"deleted"/"pending"/
  "restored"/"validated"/"restoring"/"local"/"private_remote"` match); the provider registry
  fails hard when unregistered and on conflicting re-registration (identity-idempotent);
  registration in `AppConfig.ready()` does no DB I/O; the admin-upload trust chain
  (checksum+size → status/format/scope → snapshot link → full-backup contract → provenance
  pointer-back) ports verbatim; S3 imports isolated in `_dr_remote_storage.py` with streaming
  upload preserved (no full-file materialization).
- **SA92 squash carries its own proof:** decisions.md records the ratified fresh-only posture
  with pg_policies/catalog/data hash parity against the v87 baseline (21 FORCE-RLS tables /
  42 policies identical) and a bounded literal tripwire; the SA88 `operator_access_migration`
  helper and conformance gate are confirmed retired in code (zero references remain).
- **SA94 preflight is fail-closed at every callsite except TA58's `up` carve-out:** apply, plan,
  remove, module add/config, dr, module_wiring_manager, and beta-migration all abort with
  remediation on any invalid source; the schema's `VALID_THEMES` is narrowed with a
  retired-theme-specific message; the two `except ImportError → None` social-view fallbacks died
  with the HTML theme (net fail-hard gain).
- **SA83 `_clear_priming_memo` closes the stale-memo class at the mutation sites themselves** —
  all three GUC-mutation helpers clear the memo in `finally`, not just `org_scope` exit.
- **SA91 worker pool:** failure propagation verified through both the bound-enforcement wait and
  the final join; worker output/coverage merged in deterministic discovery order; harness has its
  own PostgreSQL-free test suite wired into ci/publish/local-CI.
- **SA93 coverage policy is a gate redefinition, not a weakening:** the old statement-weighted
  90% became an equal-weight core/CLI package mean *plus* a new 80% per-file floor, with pytest's
  own threshold explicitly deferred so the fail-closed checker is the single authority; 37 helper
  tests pin its arithmetic and error paths.
- **Test-integrity (§3.7): no weakened or flipped tests** in ~100 changed test files. SA96
  tightened module test-settings defaults from `postgres` to `quickscale_test_role` (restricted
  role is now the default even without env wiring); SA84's conftest fix *adds* GUC-restoration
  proof; CRM serializer expectations moved strictly tighter (solo routes now reject foreign-org
  stages).
- **mypy watch item resolved:** the backups `ignore_missing_imports` module override is gone;
  replaced by a narrow per-file `var-annotated` suppression (documented rationale in
  `models.py`) and a legitimate `storages.*` third-party ignore.

## Structural smells (candidates for `arch-audit.md`)

- **Checkpoint/quality-fix commits as the recurring defect lane — fourth consecutive pass:**
  TA58 landed in the SA93 checkpoint `022a88fb` ahead of its own scheduled independent review,
  softening a barrier that SA94's reviewed commits had just erected. The CHANGELOG/decisions
  coverage gate under Tooling gaps remains the ticket-shaped mitigation.
- **Backups model constants duplicated as bare string literals across the persistence seam
  (new, SA89b):** `orchestration.py`/`_paths.py` now express `BackupArtifact`/`BackupSnapshot`
  status and target values as ~40 unlinked literals that must stay in sync with `models.py` by
  hand. Correct today (verified literal-by-literal); nothing gates tomorrow. The ticket-shaped
  fix is core-owned enum/constant definitions the models import (or a conformance test) — see
  Tooling gaps.
- **Verbatim security-code copies accumulating:** carried — SA26 `_sanitize_href` pair
  (blog/listings); generated `get_client_ip` duplicated across `base.py.j2`/`production.py.j2`.

## Tooling gaps

- **CHANGELOG/decisions coverage gate for production commits** — carried (fourth pass of
  evidence: TA47/TA49/TA50/TA51 → TA53 → TA55/TA56 → TA58).
- **DR status-literal conformance check** *(new, ties to the SA89b smell)* — a small test
  asserting every string literal used for artifact/snapshot status and storage-target values in
  `dr_engine/` is a member of the model-declared choice sets; prevents silent drift across the
  Django-free seam.
- **`pip-audit`/`safety` CI step** — carried; still no CVE signal source.
- **`bandit`/`semgrep` CI step** — carried.
- **Generated-project boot smoke test** — carried; SA93's e2e green-gate work (12-stage
  `make ci-e2e` incl. Docker/apply/E2E) is converging on exactly this — closing SA93 closes the
  gap.
- **csrf_exempt gate matcher coverage** — carried (no live slipping usage today).

Categories swept with no qualifying finding this pass (chain pass ran — none): injection/XSS
(templates re-read under output-language rules after the SA94 deletions; React theme escapes at
sinks; no new sink surface), auth/authz (SA85 Phase 4 admin views verified role-correct and
fail-closed), multi-tenant RLS (all new/changed callsites follow the ratified operator-read /
org-scoped-write pattern; GUC hygiene improved via SA83), concurrency (worker pool verified;
`_atomic_claim_restore` untouched), resource leaks/timeouts (worker temp dirs trap-cleaned;
streaming S3 upload preserved), N+1/perf (listings gained indexes; no new hot-path regressions),
secrets (no credential material committed; role provisioning unchanged), data handling (squash
verified — fresh-only posture ratified, seeds preserved in `0001_initial`, hash-parity proof),
dependency CVEs (lockfile metadata-only change; low confidence without a scanner), CLI archetype
(preflights fail-closed except TA58; no new destructive paths), generator archetype (theme
retirement coherent template↔schema↔CLI↔docs; emission mapping centralized and gated by SA66).

---

## Notes (not violations, watch items)

- **SA68 persistent-misconfiguration cell:** carried — an operator who *persistently* sets
  `QUICKSCALE_PRIVILEGED_COMMAND=migrate` **and** `RUNTIME_DATABASE_URL=""` would serve traffic
  under the superuser `DATABASE_URL` with RLS silently inert; two simultaneous
  misconfigurations against documentation. Watch, don't fix.
- **Dev `docker exec` unsets `RUNTIME_DATABASE_URL` (new, SA93 `022a88fb`):** the CLI's dev
  commands now pass `-e RUNTIME_DATABASE_URL=` so in-container `manage.py` invocations run under
  the superuser `DATABASE_URL`. Deliberate and documented (dev/admin workflows need DDL); the
  serving process is unaffected. Watch that this stays scoped to `development_commands.py`.
- **`quality_baseline.json` allowlist roughly tripled (new, `76c5cc55`):** the complexity/dead-code
  regression baseline consumed by `scripts/check_quality.sh` was re-baselined for v87.
  `check_quality.sh` is a local advisory tool (Makefile only, not a CI gate), so this is a
  ratchet reset, not a guard weakening — but the ratchet is now looser by ~550 entries.
- **Module `pyproject.toml`s no longer declare their real orgs dependency (SA81):** modules
  import `quickscale_modules_orgs` but dropped `quickscale-module-orgs` from their deps. Safe
  under the ratified posture — modules are not published standalone (`publish.yml` builds only
  core/cli/quickscale) and per-module `poetry.toml` documents "standalone lock/install is
  unsupported" — but the metadata is now silently wrong if that posture ever changes. This
  retires the prior "auth's orgs cap `<0.87.0`" watch item.
- **`forms_anonymize_submissions` runs its whole multi-org sweep in one transaction:** a single
  `transaction.atomic()` wraps every org's read+update. For large deployments this is a long
  transaction holding locks across tenants; batching per-org would be the operational
  improvement. Periodic command, not a hot path — watch item.
- **Worker pool head-of-line blocking (SA91):** `_qs_enforce_worker_bound` waits on the *oldest*
  worker, not the first to finish — already tracked as CR-SA91-REV-006 (low/advisory,
  throughput only).
- **React `QuickScaleModules.auth` is always typed/defaulted `false`:** recorded maintainer
  decision inside SA93 (runtime availability still gates visibility) — not a defect.
- **SA93 remains a blocked checkpoint:** exact `make ci-e2e` root-gate closure pending one Ruff
  format + broad rerun + independent review (roadmap Track 3). TA58 should ride that review.
- **Two same-named `ImproperlyConfigured` classes coexist** (SA69 decision recorded): carried.
- **`test_update_auto_commits_each_module_e2e` mocks `_sync_module_dependencies`** — carried.
- **SA47 sole-member self-removal orphans the org (deliberate):** carried.
- **Stripe call inside the SA47 atomic block:** carried; client timeout is the cheap mitigation.
- **`reset_stale_restore` `None`-`restore_started_at` edge:** carried — unreachable from the only
  caller.
- **`normalize_notifications_module_options` empty→full-defaults materialization:** carried.
- **Storage legacy-credential conversion is deliberate:** carried (SA29).
- `orgs/public_context.py:66,132`: `except Exception → None` on system-org lookup is
  **fail-closed** — carried.
- DR engine fallback modes are by-design recovery behavior, exempt per §fail-hard-principle —
  carried.
- Analytics runtime missing-API-key → silent disable is the deliberate SA17.7 shape — carried.
- `subprocess.Popen` in the dispatchers is never `wait()`ed — carried; at most one transient
  zombie per dispatch.
- Malformed staff-authored validation rules surface as field-level 400s (SA40) — carried.
- **SA83–SA86 "bucket 3" runtime-read triage: closed.** SA88's CRM triage bucketed 0
  runtime-query failures, the restricted-role cluster is fully drained, and the SA82 integration
  gate is green — the standing verification step is retired without promoting a finding.
- **mypy backups override watch item: resolved** (see Clean sweeps).

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
