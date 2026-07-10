# Tech Audit — Codebase-Wide Defect Sweep

> **Audit date:** 2026-07-09 (re-run, delta pass) + 2026-07-10 (module-by-module deep pass) ·
> **Branch:** `v87` (HEAD `198a1951`)
> **Mode:** re-run against the SA42–SA56 closeout batch plus the two untracked
> "fix: make check" / "fix: some make ci" commits (`6ea37301`, `198a1951`), followed by a
> module-by-module deep pass (all 13 modules + `quickscale_core` and `quickscale_cli` as modules).
> The sole prior open finding (TA45) re-verified directly in code and **resolved** (SA54); the full
> first-party production diff `1e618ed8..HEAD` read (112 files, ~7.9k insertions); the deep pass
> read each module's live surfaces in full (see per-module verdicts). Prior IDs are stable;
> this document states **present reality for planning** — closed findings live only in the
> Reconciliation log at the bottom. Structural findings live in [arch-audit.md](arch-audit.md);
> fail-hard policy SSOT is [decisions.md §fail-hard-principle](../technical/decisions.md#fail-hard-principle).
> **Headline this pass:** the two CI-fix commits landed behavior changes outside the SA review
> discipline — including a fail-hard→silent-fallback regression on the DR media path whose
> fail-closed regression test was renamed and assertion-flipped to bless the fallback (TA47). The
> 2026-07-10 deep pass added **zero new findings** — every module's live surface is clean.

## Orientation summary

QuickScale is a **Python 3.13 Django project generator** (Poetry monorepo: `quickscale_core`
manifest/apply/generator/DR engine, `quickscale_cli` Click CLI, 13 shipped `quickscale_modules/*`
Django apps + an empty `teams` placeholder, Jinja2 generator templates; version bumped 0.86.0 →
0.87.0 this delta). Two deployment realities: **(a)** the *generated project* — an internet-facing
Django app targeting Railway (edge proxy → gunicorn, non-root container, fail-closed runtime DB
role, production settings enforce HTTPS/HSTS/secure cookies, active `CACHES`, trusted-proxy
client-IP with SA36 math); **(b)** the *CLI/generator* — a local developer tool. Trust boundaries
unchanged from the 2026-07-07 pass, with one improvement: billing's four plain-View + manual-CSRF
endpoints migrated onto the DRF baseline (SA56 — `SessionAuthentication` enforces CSRF for
session-authenticated POSTs; `StripeWebhookView` unchanged, signature-verified), and the orgs JSON
API consolidated onto `OrgApiBaseView` (SA50 — saas-gate → auth → org-role dispatch order
verified). Tenant isolation remains DB-level RLS + fail-closed `TenantManager`; SA47 unified the
last-owner invariant behind `OrganizationMembership.is_last_owner_with_members()` with normalized
org→membership lock ordering and an atomic account-deletion path. Tooling baseline: ruff + strict
mypy in CI (now with `py.typed` markers on all modules), csrf_exempt pairing gate (SA46, extended
with conservative unpack-element literal folding), delete-rule and module-core
compatibility/import gates; **still no dependency-audit / bandit / semgrep step; pylint
duplication-only, not CI-wired**.

**Coverage (this pass):** read in full — the entire first-party production diff `1e618ed8..HEAD`:
billing `views.py` (SA56 DRF migration, all four views + `_RenderedAPIView` + credit views tail),
orgs `views.py` (SA50 `OrgApiBaseView` fold + all subclass conversions), orgs `models.py` (SA47
canonical check + `save()`/`delete()` lock-ordering rewrite), auth `views.py` (SA47 atomic
deletion), orgs `current_org.py` (SA48 fail-hard reads), `tenancy.py` diff (NOT DEFERRABLE flip +
`tenant_excluded` marker), backups `services.py` diff (SA53 fd-copy path, SA54 threshold, SA52
`_get_manage_py` raise) and `admin.py` diff, DR `orchestration.py` diff (SA54 parameter,
`_resolve_media_runtime` fallback) and `_sidecar.py` diff (media-manifest fallback) and
`adapter.py`/`_paths.py`, `entry_point.py` (SA42 post-hooks + SA44 registry deletion),
`runtime/{__init__,dr,manifest}.py` split, `contracts/module_options.py` (notifications
empty→defaults), CLI `module_config.py`/`module_wiring_manager.py` diffs and the new
`module_dependency_sync.py` complete (93 lines), all five settings/urls/views generator template
diffs, `check_csrf_exempt_gate.py`/`check_module_core_imports.py`/
`check_module_core_compatibility.py` diffs, Makefile + `scripts/test_unit.sh` + ci.yml gate
wiring. Sampled — orgs/notifications test settings, conftests (SA14.4 comments), crm/forms
migration tests (DEFERRABLE assertions), backups `test_services.py` (flipped fallback test).
Skipped — test bodies otherwise, `htmlcov/`, `graphify-out/`, module interiors unchanged since the
2026-07-05/06 deep passes. **Empirical checks run:** PostgreSQL 18 (`quickscale-test-postgres`
container) — verified `SET CONSTRAINTS <name> IMMEDIATE` on a NOT DEFERRABLE FK is accepted as a
no-op (rolled-back transaction; retracted a stronger test-breakage hypothesis for TA50). Audit
tools run: none available (`pip-audit`/`bandit`/`safety` not installed; installs prohibited);
dependency posture verified unchanged via git — `poetry.lock` untouched since 2026-06-17
(`5ffa8cdc`).

**Clean sweeps worth recording (delta):** SA56 preserves CSRF (DRF `SessionAuthentication`
enforces CSRF for session-authenticated requests; unauthenticated POSTs return 401 before any
state change and carry no session to ride); SA50's dispatch returns 403 (not 404) when the org
lookup fails — consistent non-existence/no-role responses; SA47's lock ordering (org rows before
membership row, pk-sorted) is deadlock-consistent with `AccountDeleteView`, and its
`is_last_owner_with_members` semantic change is documented and test-asserted (see Notes); SA53's
fd-based copy is crash-safe (mkstemp → fsync → `os.replace`, unlink-on-failure, close-in-finally,
staging cleanup in outer finally); SA42 post-hooks verified as direct required reads across
blog/listings/forms/notifications; SA44's explicit-registration contract holds at every live
caller (`module_wiring_manager` refreshes on all three branches; `_build_specs` self-refreshes per
CR-SA44-REV-001); the runtime facade split introduces no import cycles and social's
`runtime.manifest` deep import is gate-listed per-module; SA46 gate's unpack-element folding is
conservative (pure-unpack containers → uncertain); `sync_project_module_dependencies` validates
TOML before writing in its two main writers (but see TA52).

---

## Findings summary

| ID | Severity | Category | Title | Effort | Confidence | Status |
|----|----------|----------|-------|--------|------------|--------|
| TA47 | S2 | error-swallowing / data-handling (DR) | DR media capture/sync silently falls back to local `MEDIA_ROOT` when storage-backend resolution fails — fail-closed test flipped to bless it | Small | High | resolved (SA57) |
| TA48 | S3 | security (defense-in-depth) | RLS boot guard checks `rolbypassrls` but not `rolsuper` — superuser connections (CI's default, misconfigured deployments) pass the guard with RLS silently bypassed | Trivial | High | resolved (SA58) |
| TA49 | S3 | test-integrity / operability | `make test-unit` + `scripts/test_unit.sh` auto-prime `QUICKSCALE_ALLOW_BYPASSRLS=1`, contradicting the SA14.4 decision still documented in the test settings; CI's coverage gate inherits it | Small | High | open (SA59, Track 1, scheduled) |
| TA50 | S3 | data-handling / consistency | Composite-FK helper flipped to `NOT DEFERRABLE` undocumented — diverges from forms' asserted `DEFERRABLE` contract and from every existing database | Small | High (facts) / Medium (impact) | open (SA60, Track 1, scheduled) |
| TA51 | S4 | build hygiene (TA23 class) | Test-run artifacts committed: tracked `pytest_log.txt` updated per commit + 13 accumulating blog test-media PNGs | Trivial | High | resolved (SA61) |
| TA52 | S4 | correctness (CLI) | `_patch_module_path_dependencies` writes line-spliced TOML without the `_write_validated_toml` guard its sibling writers use | Trivial | High | resolved (SA62) |

Counts: **S1: 0 · S2: 0 · S3: 2 · S4: 0.** Remaining open: TA49, TA50 — both scheduled, Track 1 (roadmap.md).
Resolved since the 2026-07-07/08 passes: **TA45** (SA54), **TA48** (SA58), **TA47** (SA57), **TA51** (SA61), **TA52** (SA62).

---

## Findings detail

### Finding 1: DR media capture/sync silently falls back to local `MEDIA_ROOT` when storage-backend resolution fails

- **ID:** `dr-media-storage-fallback-swallows-misconfiguration`  (TA47)
- **Severity:** S2 — silent wrong-data on the disaster-recovery media path; trigger is a storage
  misconfiguration or helper failure, i.e. precisely the condition DR runs must surface, at the
  moment least tolerant of silence.
- **Category:** §4.I error swallowing / §4.IX data handling (fail-hard SSOT class).
- **Confidence:** High — both hunks, the flipped test, and the introducing commit verified
  directly; end-to-end consequence traced through `sync_backup_snapshot_media`.
- **Location:** `quickscale_core/src/quickscale_core/dr_engine/orchestration.py:1910-1913`
  (`_resolve_media_runtime`) and `quickscale_core/src/quickscale_core/dr_engine/_sidecar.py:54-58,102-108`
  (`_build_media_sync_manifest`); flipped test at
  `quickscale_modules/backups/tests/test_services.py:2871-2888`.
- **Defect:** Both call sites wrap `_load_storage_helpers().select_storage_backend(settings)` in
  `except Exception: selection = None` and fall through to local-`MEDIA_ROOT` detection. This
  conflates the one legitimate fallback case (storage module not installed —
  `ModuleNotFoundError`) with every failure case, including `ImproperlyConfigured` — the exact
  exception SA30 made `select_storage_backend` raise so that missing/invalid
  `QUICKSCALE_STORAGE_BACKEND`/S3 settings fail hard. Previously the orchestration side raised
  `BackupConfigurationError` and the sidecar returned an explicit `status: "unsupported"` manifest
  (which the sync step then refused: "Media sync requires a ready media manifest").
- **Failure scenario:** An S3-media deployment runs `quickscale dr capture` in a context where the
  storage settings don't resolve (env var missing in the capture runtime, a typo introduced by an
  env sync, or any bug inside the helpers). Capture walks the local container `MEDIA_ROOT` —
  empty or ephemeral on Railway, which README explicitly excludes from the durable media contract
  — and emits a `status: "ready"` manifest with the wrong (likely empty) inventory. `dr execute`
  media sync then "completes" against that inventory. The real S3 media is never captured or
  promoted; the loss is discovered only after cutover. On the sync side, the same swallow applies
  to the **target** runtime resolution: a non-Railway promotion target whose
  `QUICKSCALE_STORAGE_BACKEND` is missing from `target_runtime_settings` silently receives media
  onto local disk instead of its bucket (`require_s3_compatible` still protects Railway targets
  only).
- **Evidence:**
  ```python
  # orchestration.py:1910 (was: raise BackupConfigurationError(...) from exc)
  try:
      selection = _load_storage_helpers().select_storage_backend(settings_obj)
  except Exception:
      selection = None
  ```
  The regression test that guarded the old behavior,
  `test_build_media_sync_manifest_fails_closed_for_malformed_storage_helpers`
  (asserting `status == "unsupported"`), was renamed in the same commit to
  `..._falls_back_to_local_when_storage_helpers_malformed` and its assertions flipped to
  `status == "missing_media_root"`. The sidecar fallback also reintroduces a permissive
  `getattr(settings, "QUICKSCALE_STORAGE_BACKEND", "local")` read (`_sidecar.py:105`) — the
  coercion idiom SA17/SA30/SA42/SA48 systematically removed.
- **Fix:** In both call sites, catch only `ImportError`/`ModuleNotFoundError` as the
  "storage module not installed → local media project" fallback; let every other exception
  propagate (orchestration: `BackupConfigurationError` with the original message; sidecar: the
  explicit `unsupported`/error-status payload with `error_type`). Restore the fail-closed test
  and add a second test for the module-absent fallback so both behaviors are pinned. **Effort:**
  Small.
- **Verification:** Unit test: monkeypatch `select_storage_backend` to raise
  `ImproperlyConfigured` → `_build_media_sync_manifest` must not return `status: "ready"`, and
  `_resolve_media_runtime` must raise `BackupConfigurationError`; monkeypatch
  `import_module` to raise `ModuleNotFoundError` → local fallback engages.
- **Deliberate?** No sign of a decision: introduced in `6ea37301` ("fix: make check"), no
  CHANGELOG entry, no decisions.md exemption; the flipped test is the only artifact, and it
  documents no rationale. The DR engine's sanctioned fallback modes (§fail-hard-principle
  exemption) cover *recovery routing*, not configuration-error suppression.
- **Age:** 1 day (`6ea37301`, 2026-07-09) — a fresh regression; reverting both hunks and the test
  rename, then re-fixing whatever CI failure motivated them, is a reasonable alternative to a
  forward fix.

### S3 — compact

- **TA48 — `rls-boot-guard-misses-superuser`** · S3 ·
  `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py:98-108` (`_check_rls_role`).
  The guard queries `SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user`, but
  PostgreSQL superusers bypass RLS regardless of the BYPASSRLS attribute — and typically have
  `rolbypassrls = false`. decisions.md:1124 states the runtime contract as
  `NOSUPERUSER/NOBYPASSRLS`; the guard enforces only half. Live consequences: CI module suites
  connect as the `postgres` superuser and pass the guard while RLS is silently inert; a
  misconfigured generated deployment pointing `RUNTIME_DATABASE_URL` at a superuser role boots
  cleanly with DB-level tenant isolation off (app-level `TenantManager` filtering remains — this
  is a defense-in-depth loss, not direct exposure). **Fix:** change the query to
  `SELECT rolbypassrls OR rolsuper …` and update the error message; adjust
  `test_rls_boot_guard.py` mocks. Effort: Trivial (quick win). Confidence: High.
  **Status:** Resolved (SA58).
- **TA49 — `test-tooling-auto-primes-bypassrls-hatch`** · S3 ·
  `Makefile:321-327` (test-unit) and `scripts/test_unit.sh:365-366`, run by CI's repository
  coverage gate (`.github/workflows/ci.yml:340`). Both auto-export
  `QUICKSCALE_ALLOW_BYPASSRLS=1`, which (a) disables the orgs boot guard for every module suite
  and (b) flips the SA14.4 collection-time opt-in so `bypass_rls`-marked tests are always
  included. This directly contradicts the SA14.4 decision still documented at
  `quickscale_modules/orgs/tests/settings.py:14-18` and in every module conftest ("No module test
  code automatically primes QUICKSCALE_ALLOW_BYPASSRLS"). On a dev machine whose role has
  BYPASSRLS, module suites now pass with DB-level RLS unexercised and zero signal. Chains with
  TA48: between them, no environment — CI or local — any longer demonstrates the boot guard
  firing against a bypassing role. **Fix:** remove the blanket export; create a NOBYPASSRLS role
  in CI (export `QS_*_DB_USER`) and let developers set the hatch explicitly per SA14.4, or scope
  the export to the specific suites that require it with a comment referencing a decisions.md
  amendment. Effort: Small. Confidence: High. Introduced in `6ea37301`.
- **TA50 — `composite-fk-deferability-contract-diverged`** · S3 ·
  `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py:903`
  (`_ADD_COMPOSITE_FK_SQL`). Flipped `DEFERRABLE INITIALLY DEFERRED` → `NOT DEFERRABLE` in
  `6ea37301`, undocumented, no test asserts the new behavior. Divergences it creates:
  `forms/0007` inlines its own `DEFERRABLE INITIALLY DEFERRED` SQL and
  `forms/tests/test_migrations.py:457-505` asserts DEFERRABLE as "the contract" — so forms and
  crm (0009, via the helper) now install different constraint semantics, and every *existing*
  database keeps DEFERRABLE while fresh ones get NOT DEFERRABLE (fleet drift, no migration
  aligns them). Behavioral edge: Django's constraint-disabling on PostgreSQL
  (`SET CONSTRAINTS ALL DEFERRED`, used by `loaddata`/fixture restore) no longer covers
  helper-created FKs, so out-of-order fixture loads fail on exactly these tables, differently per
  module and per database age. (Verified empirically: `SET CONSTRAINTS <name> IMMEDIATE` on a
  NOT DEFERRABLE FK is a no-op, so the crm tests still pass — their comments at
  `crm/tests/test_migrations.py:1107,1158` are now stale.) NOT DEFERRABLE is defensible on
  fail-fast grounds — but then it should be the *documented* Option C policy, applied uniformly
  with a migration and a conformance gate, not a one-module drift. **Fix:** pick one deferability
  policy in decisions.md, align helper + forms SQL + tests, and extend the SA35-style conformance
  gate to assert it. Effort: Small. Confidence: High on facts, Medium on downstream impact.

### S4 — one line each

- **TA51 — `test-artifacts-committed-again`** (TA23 class, collapsed): tracked `pytest_log.txt`
  updated at HEAD (`198a1951`); 13 `quickscale_modules/blog/tests/media/blog/uploads/2026/07/test-*.png`
  committed (12 in `6ea37301`, +1 in `198a1951` — one more per test run whenever `git add -A` is
  used; `.gitignore:232` covers `pytest_cov_log.txt` but not `pytest_log.txt` or module test
  media) — `git rm --cached` all 14, add `pytest_log.txt` and `quickscale_modules/*/tests/media/`
  to `.gitignore`, optionally point blog test `MEDIA_ROOT` at a tmp path.
- **TA52 — `module-pyproject-splice-unvalidated`**:
  `quickscale_cli/src/quickscale_cli/utils/module_dependency_sync.py` —
  `_patch_module_path_dependencies` rewrites embedded-module `pyproject.toml` by line splicing
  and writes via bare `write_text`, skipping the `_write_validated_toml` guard its two sibling
  writers use; a malformed splice (e.g. a multi-line table entry) writes invalid TOML that breaks
  the subsequent `poetry lock` — route the write through `_write_validated_toml`. (Same file,
  noted not promoted: `.get("backend", "local")` permissive defaults at
  `_should_skip_manifest_dependency`/`_build_module_path_dependency_value` — options are resolved
  upstream post-SA27 so the default is dead, but it is the banned idiom.)

---

## Per-module verdicts (2026-07-10 deep pass)

Each module's live surface (views, services, serializers, admin, apps/startup guards, management
commands) read directly; **zero new findings**. Recorded here so a re-run can compare like with
like and skip the modules that were clean.

- **forms** — clean. Public submit path (`FormSubmitAPIView`) is throttled on the canonical
  `get_client_ip` (SA21.2), honeypot-silent, non-string JSON rejected (SA40), CSV export
  formula-neutralized (`_neutralize_csv_cell`), notification/analytics side effects run
  post-commit and never raise. Startup guard fail-hard on the three required settings.
- **blog** — clean. Token auth uses `secrets.compare_digest`; session auth pairs with
  `_enforce_csrf` (SA46 gate holds); image upload validates size/format/dimensions with a
  DecompressionBomb guard; markdown rendered through `escape()` → `markdownify` →
  `_sanitize_rendered_html` (SA26); startup guard validates `BLOG_API_TOKENS` shape. RSS feed
  scopes to System org under `org_scope`.
- **listings** — clean. `PublicSystemOrgReadMixin` org-scoping, shared `TenantManager`/
  `OperatorManager` (fail-closed), SA30 fail-hard settings reads.
- **notifications** — clean. Webhook ingest is HMAC-SHA256 signed + TTL-bounded + constant-time
  compared (`_verify_webhook_signature`) and idempotent via `NotificationDeliveryEvent`
  get-or-create inside a transaction; send/dispatch use `select_for_update` and per-delivery
  failure isolation; startup guard fail-hard on required settings.
- **social** — clean. Org-partitioned cache keys; embed metadata derivation raises `ValueError`
  on unresolvable ids (React-escaped at the sink); `invalidate_social_cache` stays out of
  `__all__` (SA32).
- **storage** — clean. `select_storage_backend` fail-hard on missing/invalid backend (SA30);
  S3 inventory paginates; `sanitize_relative_media_path` neutralizes traversal (exported, no
  first-party caller yet).
- **analytics** — clean. Client init lock-guarded, disable states explicit and tested; template
  tag JSON-escapes `<>&` before `mark_safe` (SA24). Runtime missing-key → silent disable is the
  deliberate SA17.7 shape.
- **auth** — clean. `AccountDeleteView` atomic + SA47 last-owner delegation + SA41 anomaly
  handling; adapter fail-hard on `ACCOUNT_ALLOW_REGISTRATION`.
- **crm** — clean. API gated on `CRM_ENABLE_API`; composite-FK org-ownership enforced at the DB
  (subject to TA50's deferability question). Verified idempotent credit paths live in billing.
- **billing** — clean. Four state-changing endpoints migrated to DRF (SA56); Stripe webhook
  signature-verified, sliced-atomic, event-idempotent; `credit_user` double-protected
  (in-lock existing-transaction check + unique constraint + `IntegrityError` re-fetch); DR
  adapter secrets on stdin.
- **backups** — clean. Dispatch lifecycle race-safe (CAS claim, stale reset, SA53 fd-copy);
  `dr_adapter_call` bridge reads kwargs from stdin (SA31); admin `format_html` sites use
  auto-escaped placeholders. (`services.py`/`orchestration.py` fallback is TA47, already open.)
- **orgs** — clean. `TenantMiddleware` fail-closed (redirect/403 on missing/non-member org, session
  cleared on invalid); `TenantManager.get_queryset` returns `.none()` with no org context;
  VIEW-AS debug enforces superuser-only and clears stale keys. (RLS boot guard is TA48, resolved SA58; NOT
  DEFERRABLE is TA50, still open.)
- **quickscale_core** — clean. No `shell=True`, no archive extraction, no unsafe deserialization;
  all subprocess calls list-form with schema-validated args; Jinja2 autoescape-off is correct for
  a code generator (Python/shell/TOML output, not HTML); advisory lock releases in `finally` and
  `__exit__`.
- **quickscale_cli** — clean. Local dev tool: list-form argv, secrets on stdin (SA31), Railway
  variable set via `--stdin`; destructive `remove`/`apply --force` gate on `click.confirm` unless
  `--force`, with snapshot/rollback. (Dependency-sync TOML write is TA52, already open.)

---

## Structural smells (candidates for `arch-audit.md`)

- **CI-fix commits as an unreviewed side channel:** `6ea37301` ("fix: make check") and
  `198a1951` ("fix: some make ci") landed a fail-hard→fallback regression (TA47), a DB-constraint
  contract change (TA50), a test-posture inversion (TA49), a flipped regression test, committed
  test artifacts (TA51), and a version bump — none with CHANGELOG/decisions.md coverage, while
  every SA-tracked change in the same window got both. The review discipline has a hole exactly
  where changes are least scrutinized.
- **Deletion invariants enforced per boundary:** carried — SA47 landed the canonical
  `is_last_owner_with_members` + view-level atomicity (a real step), but the domain-level
  `pre_delete` backstop is still absent; see arch-audit
  `deletion-invariants-per-boundary-reimplementation`.
- **No single "how does a generated app get configured at deploy time" contract:** carried
  (SA29/SA34 fixed instances; the class remains).
- **Verbatim security-code copies accumulating:** carried — SA26 `_sanitize_href` pair still
  duplicated in blog/listings; TA45's threshold copy is now closed (SA54) but the generated
  `get_client_ip` remains duplicated across `base.py.j2`/`production.py.j2`.

## Tooling gaps

- **`pip-audit`/`safety` CI step** — no dependency-CVE gate; the lockfile read stays manual and
  low-confidence. (Dependency class, ongoing.)
- **`bandit`/`semgrep` CI step** — would systematically catch the `except Exception:` +
  fallback-assignment shape (TA47, and the resolved TA42 before it), `|safe`/`mark_safe` on
  non-constant, and argv/redirect classes as they recur. TA47 is the second instance of this
  class landing after the fail-hard cleanup — the grep is cheap and the class demonstrably
  recurs.
- **Tracked-artifact gate** — a CI check that fails when `git ls-files` matches artifact patterns
  (`pytest*_log.txt`, `coverage.json`, `*/tests/media/`, `htmlcov/`) would close TA51/TA23 as a
  class instead of per-file.
- **Composite-FK conformance gate** — extend the SA35-style cross-module gate to assert one
  deferability policy for all Option C composite FKs (ties to TA50).
- **Generated-project boot smoke test** — carried; would catch settings-template/deploy-script
  drift (TA33's class).
- **csrf_exempt gate matcher coverage** — carried; attribute-form usage, list/tuple
  `method_decorator` arguments, and URLconf-level wrapping still slip the matcher (no live usage
  today).
- **Landed since last pass:** SA46 unary/unpack literal folding completed; module-core
  compatibility checker now understands lazy `__getattr__` facades (SA44); orgs conformance env
  module list derived (SA49-the-roadmap-item, distinct from finding TA49).

Categories swept with no qualifying finding this pass: injection sinks (dependency-sync TOML
writes are local-CLI, validated in main writers; no shell interpolation), XSS (no new
template/`mark_safe` surface), auth/CSRF on the changed endpoints (SA56/SA50 verified),
concurrency (SA47 lock ordering verified; SA53 fd-copy race-safe), resource leaks (SA53 fd closed
in finally), timeouts, N+1/perf, import-time side effects (SA44 removed one), dependency CVEs
(lockfile unchanged since 2026-06-17; low confidence without a scanner), test-quality on the new
suites (SA47 concurrent-deletion test asserts real behavior; the one flipped test is TA47
evidence, not a category).

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

## Notes (not violations, watch items)

- **SA47 sole-member self-removal orphans the org (deliberate, watch):** the unified
  `is_last_owner_with_members` semantic permits an owner who is the org's only member to remove
  themselves (HTML members action and `OrgApiMemberRemoveView`), leaving a memberless org row and
  its tenant data reachable by no one. CHANGELOG documents and tests assert this as the chosen
  semantic ("allowed when sole member"); there is currently no cleanup/purge path for orphaned
  orgs — worth pairing with one if it starts occurring.
- **Stripe call inside the SA47 atomic block:** `AccountDeleteView.form_valid` holds
  `select_for_update` locks on all owner org rows across the external
  `_cancel_personal_org_subscriptions` Stripe call. A slow Stripe response blocks concurrent
  membership writes on those orgs for the duration; the cancel-then-rollback asymmetry (Stripe
  state changed, DB rolled back) predates SA47. Acceptable at account-deletion frequency; a
  timeout on the Stripe client call is the cheap mitigation.
- **`local.py.j2` migrate detection is looser than the boot-guard exemption:** the new local
  DB-URL selection uses `"migrate" not in sys.argv` (anywhere in argv) while the orgs boot guard
  exempts only `sys.argv[1] == "migrate"`. Local-dev only; align to positional matching when
  convenient.
- **`reset_stale_restore` `None`-`restore_started_at` edge** (`services.py:590-649`): carried —
  the f-string would raise `TypeError` for a `STATUS_RESTORING` row with `restore_started_at=None`;
  unreachable from the only caller (pre-filtered by `is_restore_stale()`).
- **`normalize_notifications_module_options` empty→full-defaults materialization**
  (`contracts/module_options.py:555-562`): documented in the docstring as implied-module support
  (empty options materialize the manifest defaults). It is a defaults-injection point at the
  manifest boundary — fine where it is; watch that the pattern doesn't migrate into runtime
  settings reads.
- **Storage legacy-credential conversion is deliberate:** carried (SA29 migration behavior).
- `orgs/public_context.py:66,132`: `except Exception → None` on system-org lookup is
  **fail-closed** (tenant managers return `.none()`) — carried; consider letting
  non-`DoesNotExist` errors propagate.
- DR engine fallback modes (`REMOTE_FALLBACK`, JSON fallback backups, `QUICKSCALE_ENVIRONMENT`
  default `local`) are by-design recovery behavior, exempt per §fail-hard-principle — carried;
  TA47 is *not* covered by this exemption (it suppresses configuration errors, not recovery
  routing).
- Analytics runtime missing-API-key → silent disable (`services.py:192-203`) is the deliberate
  SA17.7 shape — carried, tested.
- `subprocess.Popen` in the dispatchers is never `wait()`ed — carried; at most one transient
  zombie per dispatch.
- Malformed staff-authored validation rules surface as field-level 400s to public submitters
  (SA40) — carried, reviewed choice.
