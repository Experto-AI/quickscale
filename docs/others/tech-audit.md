# Tech Audit — Codebase-Wide Defect Sweep

> **Audit date:** 2026-07-07 (re-run, delta pass) · **Branch:** `v87` (HEAD `1e618ed8`)
> **Mode:** re-run against the SA21.2/SA34–SA46 closeout batch. Every prior open finding
> (TA18, TA37, TA39, TA40) re-verified directly in code; the full first-party diff
> `3056186a..HEAD` read (54 files, ~6.9k insertions); the three arch-audit red flags from the
> 2026-07-07 delta autopsy independently verified and accepted (TA42/TA43/TA44). Prior IDs are
> stable; this document states **present reality for planning** — closed findings live only in
> the Reconciliation log at the bottom. Structural findings live in
> [arch-audit.md](arch-audit.md); fail-hard policy SSOT is
> [decisions.md §fail-hard-principle](../technical/decisions.md#fail-hard-principle).
> Remediation mapping this pass: TA18→SA21.2, TA37→SA38, TA39→SA41 (all resolved);
> TA42→SA52, TA43→SA48, TA44→SA51 (resolved 2026-07-07, roadmap cleanup pass);
> TA40→SA42 (scheduled, still open); TA45→SA54, TA46→SA53 (scheduled, still open).

## Orientation summary

QuickScale is a **Python 3.13 Django project generator** (Poetry monorepo: `quickscale_core`
manifest/apply/generator/DR engine, `quickscale_cli` Click CLI, 13 shipped `quickscale_modules/*`
Django apps + an empty `teams` placeholder, Jinja2 generator templates). Two deployment realities:
**(a)** the *generated project* — an internet-facing Django app targeting Railway (edge proxy →
gunicorn `--workers 1 --timeout 60`, non-root container, fail-closed runtime DB role, production
settings enforce HTTPS/HSTS/secure cookies, reject placeholder `SECRET_KEY`, trusted-proxy
client-IP settings with corrected `ips[-N]` math (SA36), active `CACHES` backend with
Redis-gated `createcachetable` in `start.sh` (SA34)); **(b)** the *CLI/generator* — a local
developer tool. Trust boundaries: module HTTP surfaces in generated apps (Stripe/notifications
webhooks — signature-verified + idempotent; public form submit — string-typed + throttled on
real client IP; blog/listings token APIs; org invitations; admin backup/restore — async-dispatched
with CAS claim + stale-reset recovery), then generator templates (they *become* production
config), then the CLI (destructive local ops, Railway deploy plumbing). DRF baseline is
fail-closed `IsAuthenticated`; tenant isolation is DB-level RLS (`SET LOCAL app.current_org_id`,
FORCE RLS, fail-closed `TenantManager → .none()`), with `operator_access` read-only cross-tenant
visibility now fail-hard outside transactions (SA39). Module client-IP resolution is canonical
via `quickscale_modules_orgs.current_org.get_client_ip()` (SA21.2). Tooling baseline: ruff
(E/W/F/I/N/UP/D) + strict mypy in CI, plus a new hard-fail **csrf_exempt pairing gate** (SA46,
CI-wired); **no dependency-audit / bandit / semgrep / vulture step; pylint duplication-only,
not CI-wired**.

**Coverage (this pass):** read in full — the entire first-party production diff
`3056186a..HEAD`: backups `services.py` current state (all 621 lines — SA43 dispatch lifecycle,
SA37 create/prune dispatch, SA38 staleness detection/reset, `_get_manage_py`),
`backups/admin.py` `restore_backup_view` complete plus structure map and stale surfacing
(`stale_restore_warning`, `reset_stale_restore_action` gating), `backups_create` `--trigger`
plumbing, DR `orchestration.py` CR-SA38-001 parity block, orgs `current_org.py` complete
(SA21.2 `get_client_ip`, SA39 operator-access guards, AF9 wrapper unchanged), blog/listings
SA26 sanitizers + SA30 fail-hard reads + SA35 FK migrations, forms SA40
serializer/validator hardening + SA21.2 throttle ident, billing SA41 anomaly-error path
(services + views), auth `AccountDeleteView` SA41 handling, storage `helpers.py` SA30 diff,
settings templates `base.py.j2`/`production.py.j2` SA36 math + `start.sh.j2` SA34 step,
`scripts/check_csrf_exempt_gate.py` complete (613 lines), ci.yml/Makefile/check_ci_locally.sh
gate wiring. Sampled — `backups/admin.py` remaining views (permission scaffolding, badges),
`entry_point.py` TA40 locations (re-verified byte-identical). Skipped — test bodies (except to
confirm regression coverage exists: SA35 conformance, throttle, stale-reset, gate self-tests),
`htmlcov/`, `graphify-out/`, module interiors unchanged since the 2026-07-05/06 deep passes.
Audit tools run: none available (`pip-audit`/`bandit`/`safety` not installed; installs
prohibited); dependency posture verified unchanged via git — `poetry.lock` untouched since
2026-06-17 (`5ffa8cdc`); coverage artifacts confirmed still untracked (TA23 holds).

**Clean sweeps worth recording (delta):** SA26 href sanitizer handles tab/CR/LF and leading-
whitespace scheme obfuscation, matches only the double-quoted attributes `markdownify` emits on
escaped input, and its regexes are ReDoS-safe; SA40 serializer rejects `None`/non-string JSON
values with field-level 400s and maps malformed staff `min_length`/`max_length` rules to field
errors at validator-construction time; SA30 storage/listings reads fail hard
(`ImproperlyConfigured`) on missing/invalid settings; SA35 migrations match the model changes
(`SET_NULL`, already-nullable columns) and ship with a cross-module FK-delete-rule conformance
gate; SA37/SA38/SA43 dispatch lifecycle is race-safe at code level — CAS claim
(`_atomic_claim_restore`), pre-spawn snapshot/rollback on `Popen` failure, stale reset via CAS
that can never overwrite a concurrently finishing child's terminal status, and the admin action
pre-filters with `is_restore_stale()` so the `None`-`restore_started_at` format-string edge in
`reset_stale_restore` is unreachable from any live caller; SA36 `ips[-N]`/`len >= N` math is
consistent across both settings templates and the shared SA21.2 helper and matches DRF
`NUM_PROXIES` semantics; SA34 `createcachetable` correctly unsets `RUNTIME_DATABASE_URL` (DDL
via superuser role) and is gated on `REDIS_URL` absence; SA46 gate + CI wiring are sound
(scope-boundary-aware reachability analysis, hard-fail, wired into `make check`, local CI
script, and as a `needs:` gate for test/isolation/lint jobs); `backups_create --trigger` uses
`choices=` and list-form argv (no injection surface); SA41 anomaly path verified end-to-end
(raise site → distinct exception → logged WARNING in account deletion, 400 in cancel view).

---

## Findings summary

| ID | Severity | Category | Title | Effort | Confidence | Status |
|----|----------|----------|-------|--------|------------|--------|
| TA40 | S4 | fail-open config | `entry_point.py` post-hooks retain permissive coercion defaults for blog/listings/forms/notifications — the SA18.2/SA27 fail-open class, one layer down | Small | High | open (SA42 scheduled, Track 3) |
| TA45 | S4 | duplication drift | 30-minute stale-restore threshold is a bare literal in `orchestration.py:2804` but a named constant (`STALE_RESTORE_THRESHOLD_MINUTES`) in `services.py` — the two can drift silently | Trivial | High | open (SA54 scheduled, Track 2) |
| TA46 | S4 | partial failure | `prepare_admin_uploaded_restore_artifact` unlinks the existing local artifact file before `shutil.copy2` with no failure cleanup — a copy failure (disk full) destroys the prior local copy and leaks the staging temp dir | Small | High | open (SA53 scheduled, Track 2) |

Counts: **S1: 0 · S2: 0 · S3: 0 · S4: 3.** Quick wins: TA45 is Trivial-effort. Resolved since
the 2026-07-06/07 passes: **TA18, TA37, TA39, TA42, TA43, TA44** (see Reconciliation log).

---

## Findings detail — S4 (one line each)

- **TA40** — `manifest/entry_point.py:387-389` (blog), `:451` (listings), `:520-529` (forms),
  `:900-920` (notifications): post-hook `settings.get(key, default)` coercions second-guess
  SA27-validated input — dead today, but the permissive default is what executes on any upstream
  resolver regression, reopening the TA2/TA19/TA26 class silently. Re-verified byte-identical
  this pass. Fix per **SA42** (scheduled, Track 3): direct required reads, fail loud. (Collapsed
  class — 4 locations.)
- **TA45** — `dr_engine/orchestration.py:2804` hardcodes `timedelta(minutes=30)` where
  `backups/services.py:524` defines `STALE_RESTORE_THRESHOLD_MINUTES = 30` — the CR-SA38-001
  parity block and the canonical threshold can drift silently (import direction prevents
  orchestration importing from the module app; move the constant to the engine and re-export, or
  pass it in).
- **TA46** — `backups/services.py:364-366`: `local_path.unlink(missing_ok=True)` then
  `shutil.copy2(...)` with no `try/finally` — a copy failure (disk full, permissions) deletes the
  pre-existing local artifact copy, leaves `trusted_artifact.local_path` (when previously
  persisted) dangling, and leaks the `mkdtemp` staging directory (`:368` cleanup is skipped on
  raise). Fix: copy to a temp name + `os.replace`, and clean the staging dir in a `finally`.

---

## Structural smells (candidates for `arch-audit.md`)

- **Deletion invariants enforced per boundary:** carried — open as arch-audit
  `deletion-invariants-per-boundary-reimplementation`; SA47 (first step) landed 2026-07-07, but
  the finding itself remains open (no domain-level `pre_delete` backstop yet) — see
  arch-audit.md.
- **No single "how does a generated app get configured at deploy time" contract:** carried —
  SA29/SA34 fixed instances, but a template requiring a deploy-script step is still discovered
  per-instance, not systematically; a generator-wide rule ("every settings-template requirement
  maps to a start.sh/README step, asserted by a template test") would close the class.
- **Verbatim security-code copies accumulating:** the SA26 `_sanitize_href`/
  `_sanitize_rendered_html` pair is duplicated identically in blog and listings, and TA45 shows
  the same pattern for the SA38 threshold — module code that cannot import a shared runtime seam
  keeps cloning security-relevant logic. Already on the arch-audit watchlist ("SA26 copies");
  TA45 is fresh evidence the class is growing.
- ~~Client-IP knowledge has no importable seam~~ — **resolved**: SA21.2 chose the orgs-runtime
  helper seam (`current_org.get_client_ip`); blog/forms consume it. Its settings-read residual
  (TA43) is also resolved (SA48).
- ~~Backups admin as orchestration engine~~ — **resolved**: SA43 extracted the dispatch
  lifecycle into `services.py`; SA38 gave staleness detection its natural home there.

## Tooling gaps

- **`pip-audit`/`safety` CI step** — no dependency-CVE gate; the lockfile read stays manual and
  low-confidence. (Dependency class, ongoing.)
- **`bandit`/`semgrep` CI step** — would systematically catch the TA25 class (`|safe`/`mark_safe`
  on non-constant), the argv/redirect classes, and `except Exception: pass` fallbacks (the
  now-resolved TA42's shape) as they recur.
- **Generated-project boot smoke test** — render + boot the generated app in CI with *minimal*
  env and hit one throttled endpoint; would catch settings-template/deploy-script drift (TA33's
  class) and silent-disable scenarios of TA43's now-resolved shape.
- **Apply-gate post-hook check** — extend the SA27 apply-gate assertion to fail on post-hook
  `.get(key, default)` patterns (closes TA40's class when SA42 lands).
- **csrf_exempt gate coverage** — `check_csrf_exempt_gate.py` matches `csrf_exempt` only as a
  bare `ast.Name`; attribute-form usage (`@csrf.csrf_exempt`), list/tuple arguments inside
  `method_decorator`, and URLconf-level `csrf_exempt(view)` wrapping slip past. Not a live
  defect (no such usage exists today) — extend the matcher when convenient so the gate keeps its
  guarantee as contributors vary idiom.
- **Landed since last pass:** delete-rule conformance gate (SA35,
  `TestUserFkDeleteRuleConformance`); public-submit negative-type tests (SA40); settings-contract
  startup checks for orgs/listings/storage (SA14.6/SA30); csrf_exempt pairing gate itself (SA46).

Categories swept with no qualifying finding this pass: injection sinks (argv list-form
verified on all three dispatchers; `--trigger` choice-constrained), XSS (SA26 obfuscation
handling verified), deserialization, crypto misuse, SSRF/open-redirect, concurrency (CAS
claim/reset verified race-safe), timeouts, N+1/perf, import-time side effects, dependency CVEs
(lockfile unchanged since 2026-06-17; low confidence without a scanner), test-quality (new
regression suites assert real behavior).

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
- 2026-07-07 (roadmap cleanup) — **TA42: resolved** (SA52 — `_get_manage_py()` now raises `BackupError` instead of swallowing resolution failure and falling back to a bare `"manage.py"` literal; the fail-hard raise happens before `_atomic_claim_restore`, so a resolution failure never leaves an artifact claimed; 5 regressions in `TestGetManagePySA52`). **TA43: resolved** (SA48 — `get_client_ip()` reads `USE_X_FORWARDED_FOR`/`TRUSTED_PROXY_COUNT` via direct required access, raising `ImproperlyConfigured` on missing/invalid values instead of silently defaulting). **TA44: resolved** (SA51 — `backups/services.py:1-10` header rewritten to state the real division of responsibility; no more false "under 400 LOC" claim). Findings-table counts updated (S3 1→0, S4 5→3); full detail for all three lives in CHANGELOG.md (SA52/SA48/SA51 entries). TA45 and TA46 remain open (SA54/SA53, both scheduled on Track 2, not yet landed).

## Notes (not violations, watch items)

- **`reset_stale_restore` `None`-`restore_started_at` edge** (`services.py:604-608`): the
  f-string in the `update()` call would raise `TypeError` if a `STATUS_RESTORING` artifact had
  `restore_started_at=None` (conceivable only for rows stranded before migration 0005). Not
  reachable today — the only caller (`reset_stale_restore_action`) pre-filters with
  `is_restore_stale()`, which returns `False` for `None`. Flagged in case a second caller
  arrives; such legacy rows would also be permanently un-resettable from admin (the pre-SA38
  TA37 condition), which is acceptable given no known deployments predate the migration.
- **CR-SA20-007 (resolved):** both admin dispatch branches snapshot and restore all three
  pre-spawn fields; kept here only as a pointer since TA42 (resolved via SA52) landed in the
  same code region.
- **Storage legacy-credential conversion is deliberate:** `normalize_storage_module_options`
  silently pops literal credentials and substitutes default env-var references — documented
  SA29 migration behavior; loud at first upload if env vars unset. Chosen trade-off.
- `orgs/public_context.py:140-144`: `except Exception: return None` on system-org lookup is
  **fail-closed** (tenant managers return `.none()`) — isolation preserved, but a DB-level error
  renders as "no data" instead of a 500; consider letting non-`DoesNotExist` errors propagate.
- DR engine fallback modes (`REMOTE_FALLBACK`, JSON fallback backups, `QUICKSCALE_ENVIRONMENT`
  default `local`) are by-design recovery behavior, exempt per §fail-hard-principle; the SA20
  admin path correctly forces `LOCAL_ONLY` (CR-SA20-006 verified).
- Analytics runtime missing-API-key → silent disable (`services.py:215-216`) is the deliberate
  SA17.7 shape — chosen trade-off, tested.
- `subprocess.Popen` in the dispatchers is never `wait()`ed — at most one transient zombie per
  dispatch until the worker's next subprocess call or recycle; harmless at this frequency.
- Malformed staff-authored validation rules now surface as field-level 400s to public submitters
  (SA40/`9ee27d93`) — the form stays broken until staff notice; a staff-facing surfacing (admin
  check on rule save) would close the loop, but the current behavior is a reviewed choice.
