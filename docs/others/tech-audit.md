# Tech Audit — Codebase-Wide Defect Sweep

> **Audit date:** 2026-07-05 (re-run + same-day module-by-module deep pass) · **Branch:** `v87` (HEAD `a6706db1`)
> **Mode:** full defect-catalogue sweep (correctness, security-at-callsite, concurrency, resources,
> performance, operability, dependencies) in re-run mode, followed by a **module-by-module deep
> pass** (core → orgs → cli → billing/backups → notifications/auth/forms/blog/crm → periphery)
> reading the interiors earlier passes only sampled. Prior IDs are stable; this document states
> **present reality for planning** — closed findings live only in the Reconciliation log at the
> bottom. Structural findings live in [arch-audit.md](arch-audit.md); fail-hard policy SSOT is
> [decisions.md §fail-hard-principle](../technical/decisions.md#fail-hard-principle).
> Remediation batch mapping: TA9/TA12 → SA17.7/17.8 (17.7 done); TA16–TA25 → SA19–SA26 batch;
> TA26–TA32 → SA27–SA33 batch ("Fail-Hard & Contract Gaps Remediation", opened 2026-07-05,
> see roadmap.md).

## Orientation summary

QuickScale is a **Python 3.13 Django project generator** (Poetry monorepo: `quickscale_core`
manifest/apply/generator/DR engine, `quickscale_cli` Click CLI, 13 shipped `quickscale_modules/*`
Django apps + an empty `teams` placeholder, Jinja2 generator templates). Two deployment realities:
**(a)** the *generated project* — an internet-facing Django app targeting Railway (edge proxy →
gunicorn `--workers 1 --timeout 60`, non-root container, fail-closed runtime DB role, production
settings enforce HTTPS/HSTS/secure cookies, reject placeholder `SECRET_KEY`); **(b)** the
*CLI/generator* — a local developer tool. Trust boundaries: module HTTP surfaces in generated apps
(Stripe/notifications webhooks — signature-verified + idempotent; public form submit; blog/listings
token APIs; org invitations; admin backup/restore), then generator templates (they *become*
production config), then the CLI (destructive local ops, Railway deploy plumbing). DRF baseline is
fail-closed `IsAuthenticated`; tenant isolation is DB-level RLS (`SET LOCAL app.current_org_id`,
FORCE RLS, fail-closed `TenantManager → .none()`), active regardless of `QUICKSCALE_MODE`
(SA2.1 guard). Tooling baseline: ruff (E/W/F/I/N/UP/D) + strict mypy in CI; **no
dependency-audit / bandit / semgrep / vulture step; pylint duplication-only, not CI-wired**.

**Coverage (module-by-module deep pass, same day):** quickscale_core — DR `orchestration.py`
(capture/restore/rollback flows, subprocess sites), `_sidecar.py`, apply `ledger.py` (atomic
temp+replace verified) + `executor.py` (checkpoint-after-success verified), `project_state.py`
hash-ledger writes, `advisory_lock.py` (O_EXCL + PID staleness), `git_utils.py`, manifest
`loader.py` (managed-file path-traversal defense verified) — **clean**. orgs —
`purge_organization.py` (dry-run counts under RLS verified correct), `migrate_billing_to_orgs.py`
(aborts pre-write on ambiguity, atomic, idempotent), `current_org.py` `_tenant_context`/`org_scope`
dual save-restore, signals, forms, `TenantModelAdmin` — **clean**. quickscale_cli —
`module_commands.py` update guards + snapshot rollback, `remove_command.py` transactional removal,
`status_command.py` (read-only), `development_commands.py`, `deployment_commands.py` (SECRET_KEY
masked as `<generated>` in output), `docker_utils.py`, `module_dependency_sync.py` — **clean**
(one near-miss: `plan_command.py:442-467` — the config-swallowing non-strict branch of
`_detect_existing_project` is dead, but the unsafe behavior is the *default* parameter value; a
future caller using the default silently ignores a corrupt quickscale.yml). billing — money in
integer cents, `timezone.now()` aware comparisons, unique constraints, `SET_NULL` user FKs —
**clean**. backups — `backups_restore` command (filename-match `--confirm`, dry-run, production
env gate) — **clean**; admin create/prune share TA17's in-request execution (folded into TA17).
notifications/crm — settings snapshot + tag allowlist; org-scoped `all_objects` under
`IsAdminUser` — **clean**. New findings from this pass: **TA30** (auth account-delete cascade),
**TA31** (storage config contract), **TA32** (listings/storage runtime fail-open residuals);
TA26 strengthened with the storage-backend coercion path.

**Coverage (morning re-run):** re-verified every prior open finding location in full. Read in full —
`manifest/entry_point.py` (post-hooks, generic spec builder, orgs adapter), `manifest/resolver.py`
(resolution pipeline), `manifest/assembler.py` (validation-issue consumption), `contracts/resolvers.py`
(blog/forms/orgs/social sections), `contracts/module_catalog.py`, `schema/config_schema.py`,
`apply_command.py` (validation gate + force path), social `services.py`/`models.py` cache paths,
forms `views.py`/`throttles.py`, analytics `services.py` (SA17.7 diff), blog `views.py` rate-limit
path, backups `admin.py` restore path, SA14.2 CRM admin diff, `start.sh.j2` and settings templates.
Sampled — `quickscale_devtools` (`beta_migration.py` step runners), `scripts/`, test trees for
flakiness signatures; `teams` is empty (no Python). Skipped — vendored trees, `htmlcov/`, migrations,
test bodies. Audit tools run: none available (`pip-audit`/`bandit`/`safety` not installed; installs
prohibited); dependency check was a manual `poetry.lock` read — Django 6.0.5, DRF 3.16.1,
Pillow 12.2.0, stripe 15.2.1, lockfile unchanged since 2026-06-17, no known-CVE pin identified
(low confidence without a scanner).

**Clean sweeps worth recording (silence is load-bearing):** no `shell=True` / `eval` / `exec` /
`pickle` / unsafe `yaml.load` / weak-hash-for-secrets sinks in first-party code; subprocess calls
are list-form with `PGPASSWORD` via env; Stripe + notifications webhooks signature-verified and
idempotent (`select_for_update`, `F()` deltas, unique-constraint dedup); blog/listings machine
tokens use `secrets.compare_digest`; upload validation (size/format/dimensions/decompression-bomb)
thorough and shared; RLS fail-closed at every layer; org invitation/membership invariants
lock-guarded; social cache keys org-partitioned on the model save/delete path (CR-T1-9-001);
devtools/scripts broad catches are fail-loud (issues reported, exit codes set); no mutable default
args, no timeout-less HTTP calls, no bare `Popen`/unclosed-file patterns.

---

## Findings summary

| ID | Severity | Category | Title | Effort | Confidence | Status |
|----|----------|----------|-------|--------|------------|--------|
| ~~TA26~~ | ~~S2~~ | ~~correctness / fail-open config~~ | ~~Module-option validation never enforced on the apply path for 5 modules; invalid `orgs.mode` silently downgrades tenancy to solo; invalid `storage.backend` silently drops S3 wiring; malformed forms rate 500s the public endpoint~~ | ~~Small~~ | ~~High~~ | closed (SA27) |
| TA31 | S2 | security + data loss / config contract | Storage: generated README documents env-var configuration the app never reads (silent `local` fallback → uploads lost on redeploy); the working channel bakes S3 secrets from quickscale.yml into VCS-tracked settings | Medium | High | open |
| ~~TA30~~ | ~~S2~~ | ~~correctness / data integrity~~ | ~~Self-service account deletion cascade-deletes org memberships, bypassing the last-owner invariant — ownerless orgs, zombie personal orgs with live Stripe subscriptions~~ | ~~Small~~ | ~~High~~ | closed (SA28) |
| TA18 | S2 | security / rate limiting | No client-IP resolution behind Railway proxy: per-IP throttles collapse to one shared bucket; IP forensics misattributed | Small | Medium | open |
| TA17 | S2 | operability / data loss | Admin backup restore runs `pg_restore --clean` synchronously inside the 60s-capped gunicorn worker | Medium | High | open |
| TA24 | S3 | operability / rate limiting | Generated app ships no `CACHES` backend — throttle counters per-process (`LocMemCache`), reset on deploy | Small | High | open |
| TA21 | S4 | security hardening | `debug_views` unvalidated `next` redirect (superuser POST) | Trivial | High | open |
| TA22 | S4 | security hardening | `analytics_tags` `mark_safe(json.dumps(...))` without `</script>` escaping | Trivial | High | open |
| TA25 | S4 | security hardening | Markdown `javascript:` link URIs survive escaping on public blog/listing pages | Small | Medium | open |
| ~~TA27~~ | ~~S4~~ | ~~security (local)~~ | ~~Railway CLI and DR adapter receive secrets/args on process argv (`ps`-visible)~~ | ~~Small~~ | ~~High~~ | closed (SA31) |
| ~~TA28~~ | ~~S4~~ | ~~correctness / library API~~ | ~~`invalidate_social_cache()` clears only bare keys — no-op for org-partitioned entries; exported but uncalled~~ | ~~Trivial~~ | ~~High~~ | closed (SA32) |
| ~~TA29~~ | ~~S4~~ | ~~docs hygiene~~ | ~~`decisions.md:650` links to a dropped `arch-audit.md` heading~~ | ~~Trivial~~ | ~~High~~ | closed (SA33) |
| TA32 | S4 | fail-open config (runtime residuals) | Listings/storage runtime settings reads silently default and coerce (TA2 class — modules outside SA17's scope) | Small | High | open |
| ~~TA19~~ | ~~S2~~ | ~~security / fail-open config~~ | ~~`QUICKSCALE_MODE` read with permissive `"solo"` default at 4 tenancy-relevant runtime callsites~~ | ~~Small ⚡~~ | ~~High~~ | closed (SA14.6) |
| ~~TA20~~ | ~~S3~~ | ~~correctness / data loss (CLI)~~ | ~~`apply --force` wipes the existing project before generating its replacement~~ | ~~Small~~ | ~~High~~ | closed (SA22) |
| ~~TA23~~ | ~~S4~~ | ~~hygiene~~ | ~~`coverage.json`, `pytest_cov_log.txt` tracked in git~~ | ~~Trivial~~ | ~~High~~ | closed (SA25) |

Counts: **S1: 0 · S2: 3 · S3: 1 · S4: 4.** Quick wins flagged ⚡ (Trivial/Small-effort S2).

---

## Findings detail — S2 (full blocks)

### TA18 (S2) — No client-IP resolution behind the Railway proxy: throttles collapse; IP forensics misattributed

- **ID:** `throttle-remote-addr-behind-proxy` · **Category:** §4.III rate limiting + §4.VI operability · **Confidence:** Medium (collapse certain from code; exact Railway proxy-pool behavior needs runtime confirmation)
- **Location:** `quickscale_modules/forms/src/quickscale_modules_forms/throttles.py:35` (DRF `get_ident`; no `NUM_PROXIES` anywhere in generated settings); `quickscale_modules/blog/src/quickscale_modules_blog/views.py:261-267` (`_get_blog_api_rate_limit_ident` reads `REMOTE_ADDR` directly; falls to a shared `"unknown"` bucket when absent); IP attribution `forms/views.py:231,257` (`FormSubmission.ip_address`). Settings templates configure `SECURE_PROXY_SSL_HEADER` for HTTPS but nothing for client IP.
- **Defect:** behind Railway's edge proxy every request's `REMOTE_ADDR` is the proxy, so all clients share one throttle bucket: the `form_submit` default `5/hour` becomes **5 submissions/hour across the whole deployment**, and `FormSubmission.ip_address` records the proxy — spam forensics and the honeypot IP trail are useless.
- **Failure scenario:** six distinct users submit any public form within an hour on a Railway deployment → the 6th and all later legitimate users get HTTP 429. No attacker required; normal traffic self-DoSes the form.
- **Fix:** resolve the real client IP behind the trusted proxy — set DRF `NUM_PROXIES` (1 for Railway's single hop) and add a shared trusted-proxy client-IP helper used by the blog limiter and IP logging, gated on a `TRUSTED_PROXY_COUNT` setting so no-proxy deployments keep `REMOTE_ADDR`. Getting the trust count right matters: naively reading the first `X-Forwarded-For` entry would make the throttle *spoofable* instead of collapsed. **Effort:** Small.
- **Verification:** test with fixed `REMOTE_ADDR` + varying `HTTP_X_FORWARDED_FOR`: distinct forwarded clients get independent buckets and correct `ip_address` attribution; with the setting off, behavior falls back to `REMOTE_ADDR`.
- **Deliberate?** None found — the HTTPS proxy header is handled, the IP case was missed. Reinforced by TA24 (even a correct ident hits an unshared counter store).

### TA17 (S2) — Admin backup restore runs `pg_restore --clean` synchronously in a 60s-capped worker

- **ID:** `admin-restore-sync-in-request` · **Category:** §4.VI operability / data loss · **Confidence:** High (mechanism, read directly; runtime timing needs a large-DB rehearsal)
- **Location:** `quickscale_modules/backups/src/quickscale_modules_backups/admin.py:419-437` — `restore_backup_artifact` / `restore_admin_uploaded_backup` called inside the admin POST handler; deploy template pins gunicorn `--timeout 60`. Same in-request execution class: `create_backup_view` (`admin.py:327-337`, runs `pg_dump` + optional S3 upload) and `prune_expired_backups_view` (`:339-349`) — lower stakes (a killed backup is non-mutating and the DR engine has resume machinery), but the fix should move all three off the request path together.
- **Defect:** a restore (which drops and recreates objects via `pg_restore --clean`) executes inside the request/response cycle. Past ~60s gunicorn SIGKILLs the worker mid-restore, leaving the database **partially restored** with no completion record; the admin sees a 502.
- **Failure scenario:** operator restores a backup that takes >60s on production data → worker killed mid-`--clean` → tables dropped but not yet re-created; the app is down and the operator has no signal about restore state.
- **Fix:** move restore execution out of the request path (management command the admin page instructs the operator to run, or a background job with a status row the admin polls); at minimum, pre-flight a size/duration estimate and refuse in-request restore beyond a threshold. **Effort:** Medium.
- **Verification:** rehearsal restore of a production-sized dump through the admin path on a 60s-timeout gunicorn; assert either completion or a clean refusal — never a mid-restore kill.
- **Deliberate?** Dry-run mode and confirmation gating exist (deliberate safety design), but nothing addresses the timeout interaction — none found.

### TA31 (S2) — Storage configuration contract: README documents env vars the app never reads; the working channel bakes S3 secrets into VCS

- **ID:** `storage-config-dead-env-docs-secrets-in-vcs` · **Category:** §4.III secrets + §4.IX data loss / config contract · **Confidence:** High (all links read directly; the boto3-credential-chain nuance is Medium — verify by generating a project and following the README)
- **Location:** `generator/templates/README.md.j2:265-286` (instructs operators to set `QUICKSCALE_STORAGE_BACKEND=s3`, `AWS_STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, … as *deployment environment variables*); `module_wiring.py:85-100` (`render_settings_modules_py` bakes `MODULE_SETTINGS` as pformat **literals**); generated `base.py.j2:257` (`globals().update(MODULE_SETTINGS)`) and `production.py.j2` (no storage env overrides); `manifest/entry_point.py:1301-1348` (S3 credentials/bucket emitted as literals from quickscale.yml options); `README.md.j2:265-269` (quickscale.yml example with literal `access_key_id` / `secret_access_key` values).
- **Defect:** the generated app reads storage configuration **only** from generation-time literals; none of the env vars the README documents are consulted (`QUICKSCALE_STORAGE_BACKEND` and `AWS_STORAGE_BUCKET_NAME`/endpoint/region are Django settings, read from the baked dict; only the two AWS credential env vars can work, indirectly via boto3's fallback chain, and only when the yml options were left empty *and* the backend is already s3/r2). Two consequences: **(a)** an operator who follows the README's env-var instructions (leaving quickscale.yml `backend: local` or unset) deploys an app that silently stores uploads on the ephemeral container filesystem — every uploaded file is lost on the next redeploy, with no error at upload time; **(b)** the channel that *does* work requires `access_key_id`/`secret_access_key` as plaintext in `quickscale.yml`, which generation copies into `<package>/settings/modules.py` — both tracked in the project's git repo, so live S3/R2 credentials end up committed. Every other secret-bearing module (analytics, notifications, billing) uses `*_env_var` indirection options precisely to prevent this; storage is the outlier.
- **Failure scenario:** operator provisions an R2 bucket, sets the README's env vars on Railway, deploys → users upload images for weeks → next deploy wipes all of them. Alternatively: operator puts real keys in quickscale.yml per the README's yml example → `git push` publishes the bucket credentials.
- **Evidence:** `grep` across generated settings templates finds zero `environ`/`getenv` reads for any storage key; `MODULE_SETTINGS` render is `pformat` of resolved literals.
- **Fix:** adopt the env-var-indirection pattern the other modules already use — storage options become `*_env_var` names (or the adapter emits `os.environ` reads into the managed settings), the backend/bucket stay non-secret yml options, and the README is rewritten against the real contract. **Effort:** Medium (adapter + templates + README, one PR).
- **Verification:** generate a project configured per the README's production instructions, upload a file, and assert it lands in the S3/R2 bucket; assert generated `settings/modules.py` contains no credential material.
- **Deliberate?** None found — `production.py.j2`'s own comment ("consider using cloud storage (S3, GCS) in production") shows awareness that local media is wrong in production; the README/env mismatch reads as drift between the doc and the literal-baking wiring design, not a choice.

---

## Findings detail — S3 (compact)

- **TA24** (`generated-app-no-cache-throttle-unreliable`, S3) — `generator/templates/project_name/settings/base.py.j2` ships no `CACHES` (Redis block commented at `production.py.j2:187`), so DRF form throttle and blog limiter run on per-process `LocMemCache`: effective limit multiplies by worker/replica count and resets on every deploy. Ship a working shared-cache default (Railway Redis or `DatabaseCache`) or gate throttling behind a configured backend. **Effort:** Small · Confidence: High (mechanism) / Medium (exploitability). Chains with TA18.

## Findings detail — S4 (one line each)

- **TA21** — `orgs/debug_views.py:53-55,86-88`: `redirect(request.POST.get("next"))` unvalidated (superuser-only, POST-only). Fix: `url_has_allowed_host_and_scheme`.
- **TA22** — `analytics/templatetags/analytics_tags.py:33`: `mark_safe(json.dumps(payload))` — latent `</script>` injection if payload ever carries request data (settings-only today). Fix: `json_script` pattern or escape `<>&`.
- **TA25** — `blog/views.py:787` + `listings/views.py:304-305` → `|safe` templates: `markdownify(escape(...))` neutralizes raw HTML but not markdown `[x](javascript:…)` link URIs (staff/token-gated authoring; defense-in-depth). Fix: sanitize rendered HTML (`nh3`/`bleach`, drop non-http(s)/mailto schemes).
- ~~**TA27** — `quickscale_cli/utils/railway_utils.py:348,391,891` (`railway variables --set KEY=VALUE` with live secret values) and `commands/dr_commands.py:232-242` (`--args-json` on `docker exec` argv): secrets/args visible via `ps`/`/proc` on shared hosts.~~ Closed by SA31: adapter JSON moved to stdin (`docker exec -i`), Railway variable writes moved to `railway variable set KEY --stdin`, batch writes force `--skip-deploys`.
- ~~**TA28** — `social/services.py:182-184`: exported `invalidate_social_cache()` clears only bare cache keys, a no-op for the org-partitioned keys actually used under tenant context; no first-party callers (model `save()`/`delete()` at `models.py:133-162` invalidate correctly) — a public-API trap for bulk mutations (`queryset.update()` bypasses `save()`). Closed by SA32: retired from `__all__`, kept importable for compatibility; no longer a public-API trap.~~
- **TA32** — `listings/views.py:39-52` (`_get_positive_int_setting`: missing/invalid `LISTINGS_PER_PAGE` silently → default) and `storage/helpers.py:44-56` (`_read_setting` defaults; `_normalize_backend`: unknown backend value silently → `"local"`): runtime fail-open residuals of the TA2 class — listings and storage were outside SA17.2–17.6's scope. Low-stakes at runtime today because TA26's generation-time coercion guarantees "valid" baked literals, but the storage fallback becomes live under hand-edited settings/env overrides and is the runtime half of TA26 scenario 4 / TA31. Fix: direct required reads (SA17 pattern) in both modules.

---

## Structural smells (candidates for `arch-audit.md`)

- **Validation knowledge is triplicated and unwired (TA26, closed by SA27):** module.yml declarative rules, resolver ValidationRules, and imperative `validate_*` functions encode the same constraints, and which layer actually *enforces* varies by module. SA27 closed the enforcement gap; the triplication itself remains arch-audit Finding-4 / T2.4-T2.5 territory (option-pipeline fan-out).
- **Tenancy posture is inferred, never asserted (TA26, closed by SA27):** `QUICKSCALE_MODE` fails toward solo at generation (SA14.6 closed the runtime half; SA27 closed the generation-time enforcement gap); the isolation boundary should fail toward more isolation or be a required, validated value.
- **Abuse-control correctness rests on two ambient facts the generated app doesn't guarantee (TA18 + TA24):** canonical client IP behind the proxy and a shared counter store — throttling may belong at the edge or behind an explicit "abuse-control backend configured" gate.
- **No single "how does a generated app get configured at deploy time" contract (TA31):** some settings are baked literals, some are env-read, and the docs describe a third reality. The storage finding is fixable in place, but the literal-vs-env split deserves an explicit generator-wide rule (which settings classes are env-overridable, and how docs are generated from that rule). (TA16's portion of this smell — `start.sh` secret logging — is resolved by SA19.)
- **Business invariants enforced in model methods don't survive ORM cascades (TA30, closed by SA28):** the last-owner guard's placement (overridden `delete()`) protected only direct deletes; SA28 added the boundary check at the account-deletion view. Any *future* invariant of this kind needs the same boundary-level (signal or service-layer) enforcement convention — worth an arch-audit look when teams lands, since teams will add more membership-like invariants.

## Tooling gaps

- **`pip-audit`/`safety` CI step** — no dependency-CVE gate exists; the lockfile read stays manual and low-confidence. (Dependency class, ongoing.)
- **`bandit`/`semgrep` CI step** — would systematically catch TA21 (unvalidated redirect), TA22/TA25 (`mark_safe`/`|safe` on non-constant), TA27 (argv secrets). (TA16 — secret echo — resolved by SA19.)
- **Settings-contract system check** (custom Django check asserting `QUICKSCALE_MODE` and `QUICKSCALE_*_ENABLED` explicitly set) — closes the TA19 class at startup (runtime half resolved by SA14.6).
- **Apply-gate completeness check** — CI assertion that every exported `validate_*_module_options` is invoked on the apply path (or deleted) — prevents TA26 recurring as new modules land.
- **`vulture` (dead code)** — would surface the dead blog validation branch (TA26) and TA28's uncalled export. (TA12 — deprecated catalog delegates — resolved by SA17.8.)
- **`.gitignore` + pre-commit for build artifacts** — closes the TA23 class permanently (SA25 resolved the tracked-artifact instance).

Categories swept with no qualifying finding this pass: injection sinks, deserialization, crypto misuse, SSRF/open-redirect (beyond TA21), concurrency/TOCTOU (billing & orgs lock-guarded), resource leaks, timeouts (no HTTP clients without deadlines), N+1/perf, test flakiness (sleeps confined to e2e suites), import-time side effects.

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

## Notes (not violations, watch items)

- `orgs/public_context.py:140-144`: `except Exception: return None` on system-org lookup is **fail-closed** (tenant managers return `.none()`) — isolation preserved, but a DB-level error renders as "no data" instead of a 500; consider letting non-`DoesNotExist` errors propagate.
- DR engine fallback modes (`REMOTE_FALLBACK`, JSON fallback backups, `QUICKSCALE_ENVIRONMENT` default `local`) are by-design recovery behavior, exempt per §fail-hard-principle.
- Analytics runtime missing-API-key → silent disable (`services.py:215-216`) is the deliberate SA17.7 shape (module presence fails hard at startup; a missing *runtime env var* disables capture rather than downing the app) — chosen trade-off, tested.
