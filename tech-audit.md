# Tech Audit: Fail-Hard Violations

> **Audit date:** 2026-07-03 · **Branch:** `v87`
> **Policy audited against:** [decisions.md §fail-hard-principle](docs/technical/decisions.md#fail-hard-principle) — no silent fallbacks, no best-effort defaults, no graceful degradation, no backward-compat shims; every misconfiguration must raise an explicit, descriptive error.
>
> This file records **found-not-yet-fixed** violations for later remediation planning. Structural findings live in [arch-audit.md](arch-audit.md); once a finding here is remediated, drop it and log the closeout in [CHANGELOG.md](CHANGELOG.md).
>
> **Closed 2026-07-04:** `TA3` (import-time `except Exception: pass` in manifest adapter init) — remediated by `e4183e52` (SA18.1, 2026-07-03). Dropped per this file's own rule; closeout detail lives in CHANGELOG.md.
>
> **Closed 2026-07-04:** `TA1` (legacy config keys silently translated/dropped) — remediated by `aea5e3bd` (SA17.1). `normalize_auth_module_options`, `normalize_crm_module_options`, and `normalize_notifications_module_options` now raise `ConfigValidationError` naming the dead key and its replacement for every legacy key named in this finding (`allow_registration`, `social_providers`, `default_pipeline_stages`, `resend_api_key`, `webhook_secret`). Dropped per this file's own rule; closeout detail lives in CHANGELOG.md.
>
> **Closed 2026-07-04:** `TA5` (undocumented `quickscale_cli.schema` compat shim) — remediated by `ab32f272` (SA18.3). The shim package is deleted; all internal CLI imports and tests were migrated to `quickscale_core.schema`. Dropped per this file's own rule; closeout detail lives in CHANGELOG.md.
>
> **Closed 2026-07-04:** `TA8` (project-metadata resolution swallows validation errors) — remediated by SA18.6. Removed `except Exception: return None` from `resolve_authoritative_project_metadata`'s quickscale.yml branch; `_load_managed_file_records_for_drift` is explicitly outside F12.2 scope. Dropped per this file's own rule; closeout detail lives in CHANGELOG.md.
>
> **Closed 2026-07-04:** `TA4` (analytics manifest fallback defaults) — remediated by SA18.2. `entry_point.py`'s `_analytics_post_hook` now raises `ManifestError` on empty-after-resolution settings instead of silently filling legacy defaults. `TA6` (generator template fallback chains) — remediated by SA18.4. `generator.py.__init__` resolves templates deterministically from the installed package path (no `Path.cwd()` guessing) and `_get_theme_template_path` raises `FileNotFoundError` immediately instead of falling through a backward-compat root tier. `TA7` (version fallback ending in `"0.0.0"`) — remediated by SA18.5. `version.py` narrowed to `except ImportError` and raises `FileNotFoundError` when both the embedded `_version.py` and the dev-tree `VERSION` file are unavailable. All three verified against current source 2026-07-04. Dropped per this file's own rule; closeout detail lives in CHANGELOG.md.
>
> **Closed 2026-07-04:** `TA11` (invalid `PORT` env value silently coerced to 8000) — remediated by SA18.8. `get_port_from_env()` now defaults to `8000` only when `PORT` is unset; a present but non-numeric `PORT` raises `ValueError` naming the invalid value. Dropped per this file's own rule; closeout detail lives in CHANGELOG.md.

**Scope swept:** `quickscale_core/src`, `quickscale_cli/src`, `quickscale_modules/*/src`, `scripts/`, generator templates. Patterns: broad/silent `except`, fallback chains, legacy/compat keywords, `getattr(settings, X, default)`, env-var defaults.

**Exemptions honored (not findings):** DR engine fallback artifacts and `QUICKSCALE_ENVIRONMENT` defaulting (explicitly out of scope per §fail-hard-principle); `project_state.py:_read_through_import_legacy()` (documented exception F12.2); domain logic inside generated projects. Positive examples confirmed: `entry_point.py:239` raises `ImproperlyConfigured` on adapter import failure; `billing/services.py:434` raises `BillingConfigurationError` on missing Stripe SDK.

---

## Findings summary

| ID | Severity | Location | One-liner |
|----|----------|----------|-----------|
| TA2 | High | `quickscale_modules/*/src` (pervasive) | `getattr(settings, X, permissive-default)` — features fail-open when settings are missing (generalizes SA11.7) |
| TA9 | Medium | `analytics/services.py:218`, `forms/views.py:92` | Missing SDK / missing sibling module degrades silently instead of failing |
| TA10 | Medium | `quickscale_cli/utils/railway_utils.py` | Broad `except Exception: return None` hides Railway CLI errors |
| TA12 | Low | `quickscale_core/contracts/module_catalog.py` | Deprecated compat delegates still in public API; unknown module names fail-open in readiness check |
| TA13 | Low | `quickscale_core/apply/steps/wiring.py:71` | Best-effort hash-capture step always reports success |
| TA14 | Low | repo-wide | `# F-EXCEPTION:` tag mandated by decisions.md appears nowhere in code |
| TA15 | Low | `scripts/check_module_core_compatibility.py:381` | `except Exception: return None` on pyproject parse in dev tooling |

---

## Findings detail

### TA2 (High) — Pervasive permissive settings defaults across modules

SA11.7 (tracked in decisions.md Known violations) covers `auth/adapters.py:14` (`ACCOUNT_ALLOW_REGISTRATION` defaults `True`), but the pattern is systemic — missing Django settings silently enable features or invent values instead of raising `ImproperlyConfigured`:

- ~~`analytics/services.py:61` — `QUICKSCALE_ANALYTICS_ENABLED` defaults `True`~~ — resolved by SA17.2 (AppConfig.ready() guard), see CHANGELOG.md
- ~~`billing/services.py:117` — `QUICKSCALE_BILLING_ENABLED` defaults `True`~~ — resolved by SA17.2 (AppConfig.ready() guard), see CHANGELOG.md
- `crm/views.py:219,238,246` — `CRM_ENABLE_API` defaults `True`; page sizes `int(getattr(...) or 50)` also swallow invalid values
- `forms/views.py:134,146`, `forms/throttles.py:16`, `forms/models.py:32` — submissions API on, rate limit `"5/hour"`, spam protection flag defaulted
- `blog/urls.py:18`, `blog/views.py:175,280`, `blog/models.py:46-48` — RSS on by default; `BLOG_API_TOKENS` defaults `[]` with malformed entries silently `continue`-skipped (`views.py:181-190`); media URL invented
- `notifications/services.py:155-157` — enabled defaults `True`, provider defaults `"resend"`

Since modules are creation-time assembled and the generator owns settings emission, every one of these settings is knowable at generation time; the defaults exist only to mask incomplete wiring. **Fix direction:** module `apps.py` `AppConfig.ready()` startup guards that raise on missing required settings; generator guarantees emission.

### TA9 (Medium) — Optional-dependency graceful degradation in modules

- `analytics/services.py:218-223`: PostHog SDK import failure → `logger.warning(... "Analytics capture remains disabled.")` — textbook graceful degradation. If analytics is assembled into the project, its SDK is a required dependency.
- `forms/views.py:92-97`: `import_module("quickscale_modules_analytics.services")` with `except ImportError: return`, then `getattr(..., None)` probing — a soft dependency probe. Creation-time assembly means the generator *knows* whether analytics is present; the integration should be wired (or not) at generation time, not runtime-probed.

### TA10 (Medium) — `railway_utils.py` broad exception swallowing

`quickscale_cli/utils/railway_utils.py:469,534,774` (and narrower variants at `:52,:236`): `except Exception: return None` around URL extraction, variable parsing, and status queries. Callers cannot distinguish "not deployed yet" from "railway CLI crashed / output format changed," so deployment problems surface as silent `None`s in status output. The narrow `subprocess`-error catches for "is the CLI installed" probes are defensible; the broad `Exception` catches are not.

### TA12 (Low) — Deprecated catalog compat delegates; fail-open readiness for unknown names

`contracts/module_catalog.py:128-175`: `get_module_names()` / `get_module_entries()` are documented "Deprecated since D2 … kept for backward compatibility only," yet still exported from the `contracts/__init__.py` public API with no F-EXCEPTION entry or sunset. Additionally `get_module_readiness_reason()` (`:270-289`) returns `None` for **unknown** module names — same return as "ready" — so readiness gating is fail-open for names the catalog has never heard of (mitigated only if all callers validate existence first).

### TA13 (Low) — Best-effort hash-capture step always succeeds

`apply/steps/wiring.py:71-120` `step_capture_hashes`: on `OSError` it prints a reporter warning but returns `StepOutcome(success=True)` — drift detection silently loses coverage while `quickscale apply` reports success. Deliberate design ("informational only"), but it is graceful degradation inside the apply pipeline. **Decision needed:** either fail the step (hash capture over files the apply itself just wrote should never fail) or register it as a documented F-EXCEPTION.

### TA14 (Low) — Mandated `# F-EXCEPTION:` tags absent from code

decisions.md §fail-hard-principle requires each documented exception to carry a `# F-EXCEPTION: <tag>` label in code. `grep -rn "F-EXCEPTION"` across all source returns **zero** hits. `_read_through_import_legacy` (`project_state.py:415`) mentions "F12.2" in its docstring but not in the mandated tag format, and the F12.2-adjacent legacy paths in `remove_command.py` (`_load_legacy_tracking`, legacy `config.yml` snapshot/update) are not listed in the exception table at all. Traceability drift between SSOT and code.

### TA15 (Low) — Dev-tooling silent parse failure

`scripts/check_module_core_compatibility.py:381-388`: `tomllib.load` wrapped in `except Exception: return None` — a malformed module `pyproject.toml` makes the compatibility checker silently *skip* that module instead of failing the check. A checker that silently skips broken inputs defeats its purpose.

---

## Notes (not violations, watch items)

- `orgs/public_context.py:140-144`: `except Exception: return None` on system-org lookup is **fail-closed** (tenant managers return `.none()`), so isolation is preserved — but a DB-level error renders as "no data" instead of a 500. Silent-but-safe; consider letting non-`DoesNotExist` errors propagate.
- DR engine (`dr_engine/*`) fallback modes (`REMOTE_FALLBACK`, JSON fallback backups, `QUICKSCALE_ENVIRONMENT` default `local`) are by-design recovery behavior, exempt per §fail-hard-principle scope.

---

# Re-run — Codebase-wide defect sweep (2026-07-03)

> **Re-run date:** 2026-07-03 · **Branch:** `v87` (HEAD `9ad97658`)
> **Scope change:** the original document above was a *fail-hard-policy* sweep. This re-run is the **full deep-technical defect sweep** (`deep-technical-audit`) — correctness, concurrency, security-at-callsite, resources, performance, operability — across the same first-party tree. Prior `TA1`–`TA15` are reconciled below (IDs kept stable); new defects found by the broader lenses are appended as `TA16`+.

## Orientation summary

QuickScale is a **Python 3.13 Django project generator** (monorepo: `quickscale_core` scaffolding/manifest/apply engine, `quickscale_cli` Click CLI, 13 `quickscale_modules/*` pluggable Django apps, Jinja2 generator templates), managed with Poetry (Django 6.0.5, DRF 3.16.1, Stripe SDK 15.2.1, Pillow 12.2.0 — all current, no CVE exposure surfaced). Two deployment realities coexist: (a) the **generated project** — an internet-facing Django app whose intended target is **Railway** (edge proxy + gunicorn, `--workers` defaults to 1, `--timeout 60`, non-root container, fail-closed runtime DB role, production settings enforce HTTPS/HSTS/secure cookies and reject the placeholder `SECRET_KEY`); and (b) the **CLI/generator itself** — a local developer tool. Trust boundaries in the generated app: Stripe webhook (`billing/StripeWebhookView`, signature-verified, HMAC + idempotent), provider webhook (`notifications`, HMAC + TTL + idempotent), public form-submit and form-schema endpoints (`forms`, `AllowAny` + honeypot + tenant-scoped), blog machine API (Bearer/Token via `secrets.compare_digest` + staff gate), org invitation accept (`select_for_update`, token = UUID4). DRF ships a fail-closed `IsAuthenticated` default-permission baseline; RLS/tenant isolation is enforced at the DB (`SET LOCAL app.current_org_id`, FORCE RLS) and re-verified in `tenancy.py`. Tooling baseline: ruff (E/W/F/I/N/UP/D) + mypy (strict) in CI; **no dependency-audit step, no bandit/semgrep, no vulture/pylint in CI** (pylint configured for duplication only, not wired to CI gate). **Coverage:** read in full — billing `views.py`/`services.py`, forms/blog/notifications public-facing views and webhook/signature paths, storage upload helpers, orgs `debug_views.py`/`public_context.py`/raw-SQL sites in `tenancy.py`, DR `primitives.py` subprocess/credential handling, `dr_commands.py` env-var flow, generator settings/start.sh/Dockerfile templates, `version.py`, and every prior `TA*` location. Sampled — CRM/listings/analytics/social/teams views, apply/manifest interiors. Skipped — vendored `.venv/` trees, generated `htmlcov/`, test bodies (except flakiness scan). Audit tools run: none available in-repo for dependency CVEs (`pip-audit`/`safety`/`osv-scanner` not installed; Poetry 2.4.1 present); findings are from source inspection, `git log`/`show`, and targeted grep.

## Reconciliation of prior findings (TA1–TA15)

| ID | Status | Note |
|----|--------|------|
| TA1 | **closed 2026-07-04** | Remediated by SA17.1 (`aea5e3bd`) — see header note. |
| TA2 | **still-open** | Permissive `getattr(settings, …, default)` still pervasive (crm/forms/blog/notifications); analytics/billing resolved by SA17.2 (AppConfig.ready() guards). Auth's `ACCOUNT_ALLOW_REGISTRATION` (SA11.7) is now fixed and raises `ImproperlyConfigured` — the *pattern* remains open elsewhere. |
| TA4 | **closed 2026-07-04** | Remediated by SA18.2 — see header note. |
| TA5 | **closed 2026-07-04** | Remediated by SA18.3 (`ab32f272`) — see header note. |
| TA6 | **closed 2026-07-04** | Remediated by SA18.4 — see header note. |
| TA7 | **closed 2026-07-04** | Remediated by SA18.5 — see header note. |
| TA8 | **closed 2026-07-04** | Remediated by SA18.6 — see header note. |
| TA9 | **still-open** | Analytics missing-SDK warn-and-disable (`services.py:218`), forms soft analytics probe (`views.py:94`) still present. |
| TA10 | **still-open** | 8× `except Exception` in `railway_utils.py`. |
| TA11 | **closed 2026-07-04** | Remediated by SA18.8 — see header note. |
| TA12 | **still-open** | Deprecated-D2 catalog delegates still exported; unknown-name readiness still fail-open. |
| TA13 | **still-open** | `apply/steps/wiring.py` best-effort step still returns `success=True` on `OSError`. |
| TA14 | **still-open** | Zero `# F-EXCEPTION:` tags in code (grep confirms 0 hits). |
| TA15 | **still-open** | `check_module_core_compatibility.py:385` still `except Exception: return None`. |

## New findings

| ID | Severity | Category | Title | Effort | Confidence |
|----|----------|----------|-------|--------|------------|
| TA16 | S2 | resources / operability | Rate-limit & IP attribution keyed on `REMOTE_ADDR` with no proxy-aware client IP — collapses to a shared global bucket behind Railway's edge proxy | Small | Medium |
| TA17 | S4 | security (local) | Railway CLI receives secrets/args on the process command line (`ps`-visible on shared hosts) | Small | High |
| TA18 | S4 | build hygiene | Coverage/build artifacts committed to the repo | Trivial | High |

---

### TA16 (S2) — Per-IP throttle and IP logging use `REMOTE_ADDR` with no proxy-aware client-IP resolution

- **ID:** `throttle-remote-addr-behind-proxy`
- **Severity:** S2 — on the project's documented deploy target (Railway edge proxy in front of gunicorn), every request's `REMOTE_ADDR` is the proxy's internal address, so all clients share one throttle bucket; the real client IP lives in `X-Forwarded-For`, which nothing reads. Reachable on public, unauthenticated endpoints.
- **Category:** Resources/IV + Operability/VI.
- **Confidence:** Medium — the collapse is certain given the code; the exact Railway networking (whether `REMOTE_ADDR` is one proxy IP or a small pool) needs runtime confirmation, but either way it is not the client.
- **Location:** `quickscale_modules/forms/src/quickscale_modules_forms/throttles.py:26-30` (`FormSubmitThrottle.get_cache_key` → DRF `get_ident`, which honors `NUM_PROXIES`; unset ⇒ uses `REMOTE_ADDR`); `quickscale_modules/blog/src/quickscale_modules_blog/views.py:260-266` (`_get_blog_api_rate_limit_ident` reads `REMOTE_ADDR` directly); IP attribution at `forms/views.py:231,257` and `blog/views.py:263`. No `NUM_PROXIES` / `SECURE_PROXY`-style client-IP setting anywhere in the generated settings (`base.py.j2` / `production.py.j2`).
- **Defect:** The `form_submit` scoped throttle defaults to `5/hour` **per ident**. Behind the proxy, ident is constant, so the limit becomes **5 submissions/hour across the entire deployment** — the first handful of legitimate submissions site-wide exhaust it and everyone else gets `429` until the window rolls. The blog API additive throttle has the same collapse. Separately, `FormSubmission.ip_address` and blog throttle identity record the proxy IP, not the submitter — spam/abuse forensics and the honeypot IP trail are misattributed.
- **Failure scenario:** Deploy the generated app on Railway. Six distinct users submit any public form within an hour → the 6th (and every subsequent) legitimate user receives HTTP 429 "Rate limit exceeded," because all six shared the single proxy-IP bucket. No attacker required; normal traffic self-DoSes the form.
- **Evidence:** `throttles.py` `get_rate()` → `getattr(settings, "FORMS_RATE_LIMIT", "5/hour")`; `get_ident` inherited from DRF `BaseThrottle`, which returns `REMOTE_ADDR` when `NUM_PROXIES` is unset. Settings grep shows no `NUM_PROXIES`, no `django-ipware`, no X-Forwarded-For middleware; `MIDDLEWARE` begins with `CorrelationIdMiddleware`, `SecurityMiddleware`.
- **Fix:** In the generated settings template, resolve the real client IP for throttle/logging behind the trusted proxy — either set DRF `NUM_PROXIES` (e.g. `1` for Railway's single edge hop) so `get_ident` uses the correct `X-Forwarded-For` entry, or introduce a small trusted-proxy client-IP helper used by both the forms throttle and the blog rate limiter and by IP logging. Gate it on a `TRUSTED_PROXY_COUNT`/`USE_X_FORWARDED_FOR` setting so single-host (no-proxy) deployments keep `REMOTE_ADDR`. **Effort:** Small.
- **Verification:** Test with `REMOTE_ADDR` fixed and varying `HTTP_X_FORWARDED_FOR`: assert two different forwarded clients get independent throttle buckets (and that `FormSubmission.ip_address` records the forwarded client), while with the proxy setting disabled the behavior falls back to `REMOTE_ADDR`.
- **Deliberate?** None found — no comment or setting acknowledges the proxy hop; `SECURE_PROXY_SSL_HEADER` is configured for HTTPS detection but no equivalent exists for client IP, suggesting the IP case was simply missed.
- **Age:** Long-standing (throttle and rate-limit helpers predate the current branch).

### TA17 (S4) — Secrets and adapter args passed on the CLI process command line

- **ID:** `railway-cli-secrets-on-argv`
- **Location:** `quickscale_cli/utils/railway_utils.py:388-397` (`set_railway_variables_batch` builds `railway variables --set KEY=VALUE …` with live env-var values, including secrets copied during DR env sync); `quickscale_cli/commands/dr_commands.py:224-235` (`_call_adapter` serializes `kwargs` to `--args-json <json>` on a `docker exec` argv).
- **Defect:** Argument vectors are visible to any local user via `ps`/`/proc/<pid>/cmdline` for the command's lifetime. During DR env-var promotion the copied values can include API keys / DB URLs. This is a local developer-tool exposure, and the Railway CLI's `variables --set` interface offers no stdin alternative, so it is partly inherent; still worth a note and, where possible, preferring stdin/file transport for the adapter JSON.
- **Fix:** For `_call_adapter`, pass the JSON via stdin (`docker exec -i … --args-stdin`) instead of argv. For Railway variables, document the exposure; batch is already used to minimize invocations. **Effort:** Small.

### TA18 (S4) — Coverage/build artifacts committed to the repo

- **ID:** `committed-coverage-artifacts`
- **Location:** tracked files `coverage.json`, `pytest_cov_log.txt` (repo root); `htmlcov/` present on disk.
- **Defect:** Generated coverage/log artifacts are version-controlled, producing noisy diffs and staleness. No runtime consequence.
- **Fix:** Remove from tracking and add to `.gitignore`. **Effort:** Trivial.

## Structural smells (candidates for `arch-audit.md`)

- TA2's breadth (permissive `getattr(settings, …, default)` across every module) is a *systemic* fail-open habit that a per-callsite fix cannot close durably; it points to a missing **generator↔module settings contract** (generator guarantees emission; modules assert presence via AppConfig.ready startup guards). This is the same beam arch-audit's `QUICKSCALE_MODE` red flag rests on.
- TA16's proxy-IP gap is one callsite pattern, but the absence of any trusted-proxy client-IP convention in the generated settings is a template-wide decision (where does the app learn its edge topology?) worth an architectural note.

## Tooling gaps

- **No dependency-vulnerability gate in CI.** Add `pip-audit` (or `safety`) as a read-only CI step — would systematically catch the dependency-hygiene class this sweep could only inspect by hand. (Prevents future CVE drift on the Stripe/Django/Pillow trust-boundary deps.)
- **No security-lint gate.** A `bandit` (or `semgrep`) CI step configured for the broad-`except`/`subprocess`-argv/weak-default families would flag TA10/TA15 swallows and TA17-style argv exposure automatically. Ties to `TA7`, `TA8`, `TA10`, `TA15`, `TA17`.
- **`vulture`/`pylint` are dev-declared but not CI-wired.** Wiring the existing `pylint` duplication config into CI would keep the collapsed-class habits from regressing; `vulture` would surface the dead compat delegates behind `TA12`.
- **A grep-based CI check for the mandated `# F-EXCEPTION:` tag** (decisions.md §fail-hard-principle) would close `TA14`'s SSOT↔code traceability drift cheaply.

_Categories swept with no new qualifying finding: injection sinks (no `shell=True`/`eval`/`os.system`; raw SQL is parameterized or static PL/pgSQL by design), crypto misuse (HMAC + `secrets.compare_digest` + UUID4 tokens used correctly), unsafe deserialization (`yaml.safe_load` throughout), open redirect (VIEW-AS `next` is superuser-gated), XSS via markdown (`escape()` precedes `markdownify()` in blog and listings), concurrency on the credit ledger (`select_for_update` + `F()` + `IntegrityError` idempotency are correct), N+1 (CRM/billing use `select_related`/`prefetch_related`), mutable default args (none), timezone-naive comparisons on request paths (none reached)._

---

# Deep technical sweep — 2026-07-03 (re-run, full-catalogue)

> **Scope:** the earlier section above is a *fail-hard-policy* audit (TA1–TA15). This appended
> section is the full defect-catalogue sweep (correctness, security, concurrency, resources,
> performance, operability, dependencies) run the same day, in re-run mode: prior IDs are
> reconciled below, new findings continue the `TA` sequence from **TA16**.

## Orientation summary

QuickScale is a Python 3.13 / Poetry monorepo (~69k first-party lines, 274 files excluding tests,
vendored `.venv`s and caches): `quickscale_core` (project generator, manifest/apply pipeline, DR
engine), `quickscale_cli` (Click CLI, runs on developer machines), and 14 Django modules under
`quickscale_modules/*` whose code ships **inside generated, internet-facing SaaS apps** deployed to
Railway behind its edge proxy (deploy reality read from `railway.json.j2`, `start.sh.j2`,
`Dockerfile.j2`: gunicorn sync workers, `--timeout 60`, non-root container user,
`SECURE_PROXY_SSL_HEADER` set). Trust boundaries, most exposed first: module HTTP surfaces in
generated apps (billing/Stripe webhooks, public form submissions, blog token API, org invitations,
admin-triggered backup/restore), then generator templates (they *become* production config), then
the CLI (destructive local ops, Railway deploy plumbing). Tooling baseline: ruff (E/W/F/I/N/UP/D
only — no bugbear/bandit families), strict mypy, pylint duplication-only, CI runs ruff+mypy+tests
but no dependency audit. **Coverage:** read in full — billing views + ledger/webhook services,
blog token auth/throttle/upload validation, forms public endpoints + throttles, notifications
webhook verification, dr_engine primitives, storage helpers, generated settings/start.sh/Dockerfile
templates, orgs debug views; targeted-read — apply_command force paths, dr_commands env-sync and
restore plumbing, backups admin entry points, orgs invitation flow, CRM views; sampled by grep
signature — everything else (social, teams, listings, devtools, tests). Audit tools: none run
(pip-audit/safety not installed; installs prohibited); dependency check was a manual lockfile
read (Django 6.0.5, DRF 3.16.1, Pillow 12.2.0, stripe 15.2.1 — all current, no known-CVE pins
identified, low confidence without a scanner).

**Clean sweeps worth recording** (silence is load-bearing): no `shell=True`/`eval`/`pickle`/unsafe
`yaml.load`/weak-hash sinks anywhere in first-party code; Stripe webhook signature + idempotency
(unique-constraint dedup with `IntegrityError` recovery, `select_for_update`, `F()` deltas) is
solid; notifications webhook HMAC is textbook (TTL + `compare_digest`); blog API tokens compared
with `secrets.compare_digest`; upload validation (size/format/dimensions/decompression-bomb) is
thorough; `PGPASSWORD` passed via env not argv; production settings template is fail-closed
(placeholder SECRET_KEY rejected, runtime NOBYPASSRLS role required, HSTS/secure cookies); CLI
destructive ops gated by confirm prompts + advisory lock; CRM/blog querysets properly
`select_related`/`prefetch_related`; no mutable-default-arg or unbounded-`lru_cache` hits.

## Reconciliation of TA1–TA15

| ID | Status | Note |
|----|--------|------|
| TA1 | closed 2026-07-04 | Remediated by SA17.1 (`aea5e3bd`) — see header note. |
| TA2 | still-open (partially remediated) | `auth/adapters.py` now **raises** `ImproperlyConfigured` when `ACCOUNT_ALLOW_REGISTRATION` unset (SA11.7 done); analytics/billing resolved by SA17.2; remaining listed module defaults (notifications :157, forms, blog, crm) verified still open |
| TA4 | closed 2026-07-04 | Remediated by SA18.2 — see header note. |
| TA5 | closed 2026-07-04 | Remediated by SA18.3 (`ab32f272`) — see header note. |
| TA6 | closed 2026-07-04 | Remediated by SA18.4 — see header note. |
| TA7 | closed 2026-07-04 | Remediated by SA18.5 — see header note. |
| TA8 | closed 2026-07-04 | Remediated by SA18.6 — see header note. |
| TA9 | still-open | Verified `analytics/services.py:218` warning-and-continue, `forms/views.py:94` |
| TA10 | still-open | 8 `except Exception` sites in `railway_utils.py` |
| TA11 | closed 2026-07-04 | Remediated by SA18.8 — see header note. |
| TA12 | still-open | Deprecated delegates at `module_catalog.py:132,162` |
| TA13 | still-open | `wiring.py` best-effort `success=True` unchanged |
| TA14 | still-open | `F-EXCEPTION` grep: 0 hits |
| TA15 | still-open | `check_module_core_compatibility.py:381-388` unchanged |

## New findings summary

| ID | Severity | Category | Title | Effort | Confidence |
|----|----------|----------|-------|--------|------------|
| TA16 | S2 | security / secrets in logs | `start.sh` prints `SECRET_KEY` and `DATABASE_URL` values to deploy logs | Trivial ⚡ quick win | High |
| TA17 | S2 | operability / data loss | Admin backup & restore run `pg_dump`/`pg_restore --clean` synchronously inside a 60s-capped gunicorn worker | Medium | High (mechanism) / Medium (runtime) |
| TA18 | S2 | security / rate limiting | No canonical client-IP handling behind Railway proxy: DRF throttle bypass via spoofed `X-Forwarded-For`; blog throttle collapses to one shared bucket | Small | Medium |
| TA19 | S2 | security / fail-open config | `QUICKSCALE_MODE` read with permissive `"solo"` default at 4 tenancy-relevant callsites | Small ⚡ quick win | High |
| TA20 | S3 | correctness / data loss (CLI) | `apply --force` wipes the existing project **before** generating its replacement | Small | High |
| TA21 | S4 | security hardening | `orgs/debug_views.py:53,86` — unvalidated `next` redirect | fix: `url_has_allowed_host_and_scheme` | High |
| TA22 | S4 | security hardening | `analytics_tags.py:33` — `mark_safe(json.dumps(...))` instead of the `json_script` pattern (latent `</script>` injection if payload ever carries request data; today it is settings-only) | fix: escape `<`,`>`,`&` or use `json_script` | High |
| TA23 | S4 | hygiene | `coverage.json`, `pytest_cov_log.txt` tracked in git | fix: `git rm --cached` + `.gitignore` | High |

## New findings detail

### TA16 (S2) — Generated `start.sh` logs secret values on every boot

- **ID:** `startsh-secrets-in-deploy-logs` · **Category:** §4.III secrets logged · **Confidence:** High (read directly)
- **Location:** `quickscale_core/src/quickscale_core/generator/templates/start.sh.j2`, Step 1 (“Environment check”).
- **Defect:** `env | grep -E '(DATABASE_URL|SECRET_KEY|DEBUG|DJANGO_SETTINGS_MODULE|ALLOWED_HOSTS|PORT)'` prints the **values** of `SECRET_KEY` and `DATABASE_URL` (which embeds the DB password) into stdout on every container start. Railway retains and displays deploy logs to anyone with project access; log drains propagate them further.
- **Failure scenario:** any generated project deploys → its Django signing key and DB credentials sit in plaintext in the platform log history;
 log drains and Sentry breadcrumbs propagate them further. **Fix:** print only the *names* of present/absent vars (`for v in ...; do [ -n "${!v+x}" ] && echo "$v: set" || echo "$v: MISSING"; done`), never values. **Effort:** Trivial. **Deliberate?** None found — framed as a debug convenience.

*(The 2026-07-03 re-run above was interrupted here; the module-by-module sweep below supersedes and completes it. TA16–TA23 detail is carried forward by ID in the reconciliation table.)*

---

# Re-run — Module-by-module defect sweep (2026-07-04)

> **Re-run date:** 2026-07-04 · **Branch:** `v87` (HEAD `d97c7833`)
> **Framing:** fresh **module-by-module** pass over the same first-party tree, walking each trust boundary in isolation rather than by defect category. Prior IDs `TA1`–`TA23` are reconciled by ID (kept stable); this pass adds `TA24`–`TA25`. No prior analysis is overwritten.

## Orientation summary

QuickScale is a **Python 3.13 Django project generator** (Poetry monorepo). Two deployment realities: **(a)** the *generated project* — an internet-facing Django app targeting Railway (gunicorn `--workers 1 --timeout 60`, non-root container, WhiteNoise static, fail-closed runtime DB role, production settings enforce HTTPS/HSTS/secure cookies and reject the placeholder `SECRET_KEY`); **(b)** the *CLI/generator* — a local dev tool (`quickscale plan/apply/dr/deploy`). First-party surface: `quickscale_core` (~22k LOC: manifest/apply/generator/dr_engine/tenancy plumbing), `quickscale_cli` (~15k LOC Click CLI), 12 shipped `quickscale_modules/*` Django apps. Trust boundaries walked this pass: **billing** (Stripe webhook — signature + idempotent + `select_for_update`/`F()`; checkout/portal/cancel — `csrf_exempt`+manual CSRF re-enforce, owner-gated; read APIs — `AllowAny`+`SessionAuthentication`+in-body auth), **notifications** (provider webhook — HMAC-SHA256 + TTL + `compare_digest` + idempotency key), **forms** (public schema/submit — `AllowAny`, honeypot, DRF throttle, tenant-scoped, System-org default), **blog/listings** (staff/Bearer-token publish via `secrets.compare_digest`; public markdown read pages), **orgs** (RLS via `SET LOCAL app.current_org_id` + FORCE RLS re-primed by a connection execute-wrapper; session-based tenant middleware; UUID4 invitation tokens with `select_for_update`; superuser VIEW-AS debug). DRF ships a fail-closed `IsAuthenticated` default-permission baseline. Tooling baseline: ruff (E/W/F/I/N/UP/D) + mypy strict in CI; **still no dependency-audit / bandit / semgrep / vulture step, pylint wired for duplication only**.

**Coverage:** read in full this pass — orgs `views.py`/`middleware.py`/`current_org.py`/`managers.py`/`permissions.py`/`public_context.py`/`models.py`/`tenancy.py` RLS SQL + purge command; billing `views.py`/`services.py` (webhook, ledger, subscription upsert) + model constraints; forms `views.py`/`serializers.py`/`validators.py`/`throttles.py`; blog `views.py` + public templates; listings publish path + template; notifications webhook verify + view; storage `helpers.py`; DR `primitives.py` subprocess/credential handling; CLI `apply_command.py` force path, `docker_utils.py`, `railway_utils.py` (count); generator `Dockerfile.j2`/`start.sh.j2`/`settings/*.j2`/`railway.json.j2`; `version.py`. Sampled — analytics, crm, social, teams, apply/manifest interiors. Skipped — vendored trees, `htmlcov/`, migrations (except RLS/data migrations), test bodies. Audit tools run: none installed (`pip-audit`/`safety`/`bandit` absent, installs prohibited); dependency read was manual (Django 6.0.5, DRF 3.16.1, Pillow 12.2.0, stripe 15.2.1 — all current, no CVE pin identified, low confidence without a scanner).

**Clean sweeps worth recording (silence is load-bearing):** no `shell=True` / `eval` / `exec` / `os.system` / `pickle` / unsafe `yaml.load` / weak-hash-for-secrets sinks in first-party code; all subprocess calls are list-form with `PGPASSWORD` via env, not argv; Stripe + notifications webhooks are signature-verified and idempotent; blog/listings machine tokens use `secrets.compare_digest`; upload validation (size/format/dimensions/decompression-bomb) is thorough and shared; orgs RLS is fail-closed at every layer (`TenantManager` → `.none()`, GUC priming, FORCE RLS); billing money paths use row locks + `F()` deltas + unique constraints; org invitation/membership last-owner invariants are lock-guarded; no mutable-default-args surfaced.

## Reconciliation — prior findings

| ID | Status | Note (re-verified 2026-07-04) |
|----|--------|------|
| TA1 | closed 2026-07-04 | Remediated by SA17.1 (`aea5e3bd`) — see header note. |
| TA2 | still-open (partial) | `auth/adapters.py` now raises (SA11.7 done); permissive `getattr(settings, …, default)` remains — verified `crm/views.py:204,223,231`, `forms/throttles.py:16`, `forms/views.py:134,146`, `blog/views.py:175,280`, `orgs/views.py:63`+`middleware.py:268` (see TA19). Analytics/billing resolved by SA17.2 (AppConfig.ready() guards removed the `True` defaults). |
| TA4 | closed 2026-07-04 | Remediated by SA18.2 — see header note. |
| TA5 | closed 2026-07-04 | Remediated by SA18.3 (`ab32f272`) — see header note. |
| TA6 | closed 2026-07-04 | Remediated by SA18.4 — see header note. |
| TA7 | closed 2026-07-04 | Remediated by SA18.5 — see header note. |
| TA8 | closed 2026-07-04 | Remediated by SA18.6 — see header note. |
| TA9 | still-open | `analytics/services.py:218`, `forms/views.py:94` warning-and-continue. |
| TA10 | still-open | 8× `except Exception` in `railway_utils.py`. |
| TA11 | closed 2026-07-04 | Remediated by SA18.8 — see header note. |
| TA12 | still-open | Deprecated delegates `module_catalog.py:132,162`. |
| TA13 | still-open | `wiring.py` best-effort `success=True`. |
| TA14 | still-open | `# F-EXCEPTION:` tag: 0 hits repo-wide. |
| TA15 | still-open | `check_module_core_compatibility.py:381-388`. |
| TA16 | still-open | `start.sh.j2` Step 1 prints `SECRET_KEY`/`DATABASE_URL` values (S2, Trivial quick win). Re-verified. |
| TA17 | still-open | `backups/admin.py:419-437` — `restore_backup_artifact` / `restore_admin_uploaded_backup` (→ `pg_restore --clean`) run **synchronously** in the admin POST inside the 60s gunicorn worker (S2). Re-verified. |
| TA18 | still-open | Superseded/reinforced by **TA24**: throttling identity + backing store both unreliable behind the Railway proxy. |
| TA19 | still-open | `QUICKSCALE_MODE` permissive `"solo"` default — `orgs/views.py:63`, `middleware.py:268` (+`org_invitation`/dashboard branches). Fail-open toward the *less*-isolated mode (S2). Re-verified. |
| TA20 | still-open | `apply_command.py:1781-1792` — `--force` deletes existing project content (loop `rmtree`/`unlink`) **before** generating the replacement into a temp dir; generation failure ⇒ project already wiped (S3). Re-verified. |
| TA21 | still-open | `orgs/debug_views.py:53-55,86-88` — `redirect(request.POST.get("next"))` unvalidated (open-redirect; superuser-only, POST-only) (S4). |
| TA22 | still-open | `analytics_tags.py:33` — `mark_safe(json.dumps(payload))` not escaped; payload is settings-only today (S4 latent). |
| TA23 | still-open | `coverage.json`, `pytest_cov_log.txt` tracked in git (S4). |

## New findings this pass

| ID | Severity | Module | Category | Title | Effort | Confidence |
|----|----------|--------|----------|-------|--------|------------|
| TA24 | S3 | generator + forms/blog | operability / rate-limiting | Generated app ships **no `CACHES` backend**, so DRF form throttle + blog per-IP limiter run on per-process `LocMemCache` — unshared across workers, wiped on every deploy | Small | High (mechanism) / Med (exploit) |
| TA25 | S4 | blog + listings | security hardening / stored XSS | `markdownify(escape(...))|safe` neutralizes raw HTML but not markdown `[x](javascript:…)` link URIs on public detail pages | Small | Medium |

### TA24 (S3) — Generated project has no cache backend; rate limiting is per-process and ephemeral

- **ID:** `generated-app-no-cache-throttle-unreliable` · **Category:** §4.VI operability + §4.III rate-limiting · **Confidence:** High (mechanism, read directly) / Medium (exploitability depends on replica count)
- **Location:** `generator/templates/project_name/settings/base.py.j2` (no `CACHES` block) and `.../production.py.j2:186-195` (Redis `CACHES` shipped commented-out). Consumers: `forms/throttles.py` `FormSubmitThrottle(ScopedRateThrottle)` (DRF throttle uses `caches["default"]`) and `blog/views.py:277-304` `_enforce_blog_api_rate_limit` (`cache.add`/`cache.incr`).
- **Defect:** with no `CACHES` configured, Django falls back to `LocMemCache` — a **per-process, in-memory** store. Two consequences on the public throttled endpoints: (1) throttle counters are **not shared across gunicorn workers or Railway replicas**, so the effective limit is `N × configured` and any horizontal scale-out or `WEB_CONCURRENCY>1` multiplies it; (2) every deploy/restart **resets all counters to zero**. The form-submit throttle (`5/hour` default) and the blog machine-API limiter are the app's only application-layer abuse controls on unauthenticated / token surfaces.
- **Failure scenario:** operator sets `WEB_CONCURRENCY=4` (or Railway runs 2 replicas) → the anonymous form-submit limit silently becomes 20/hour per IP; a redeploy mid-attack clears the bucket. No error, no log — the limit simply doesn't hold.
- **Evidence:** `base.py.j2` defines `STORAGES`/`LOGGING`/`REST_FRAMEWORK` but no `CACHES`; `production.py.j2:187` `# CACHES = { ... django_redis ... }` is commented. `FormSubmitThrottle` inherits DRF `SimpleRateThrottle.cache = caches["default"]`.
- **Fix:** ship a working shared-cache default for production (Railway Redis add-on or, at minimum, `DatabaseCache` via `createcachetable`) and point DRF `DEFAULT_THROTTLE_CLASSES`/`FormSubmitThrottle` at it; alternatively document that throttling is best-effort until a cache is provisioned and gate the throttle behind a configured backend. **Effort:** Small. **Verification:** deploy with `WEB_CONCURRENCY=2`, hammer `/api/forms/<slug>/submit/` from one IP, confirm the 6th request in an hour is 429 regardless of which worker serves it.
- **Deliberate?** Partly — Redis is intentionally optional, but the *consequence for throttling* is undocumented. Reinforces TA18 (identity spoofing): even with correct client-IP resolution, the counter store is unreliable.

### TA25 (S4) — Markdown `javascript:` links survive escaping on public blog/listing pages

- **ID:** `markdown-uri-scheme-stored-xss` · **Category:** §4.III / §4.X frontend stored XSS · **Confidence:** Medium (needs a render test to confirm python-markdown does not strip the scheme in this version)
- **Location:** `blog/views.py:787` `markdownify(escape(self.object.content))` → `templates/.../post_detail.html:40` `{{ rendered_content|safe }}`; `listings/views.py:304-305` `markdownify(escape(self.object.description or ""))` → `listing_detail.html:40` `{{ rendered_description|safe }}`.
- **Defect:** `escape()` converts `< > & " '` before markdown rendering, so injected **raw HTML** is inert. But markdown-native link syntax is untouched: `[click me](javascript:fetch('/x'))` renders `<a href="javascript:...">` which the `|safe` filter then emits unescaped. python-markdown does not sanitize URI schemes by default. Authoring is staff/Bearer-token-only (`is_staff` gate on `publish_post_api`/`publish_listing_api`), so this is defense-in-depth against a compromised or over-provisioned staff/tenant-admin account, not an anonymous vector — and it requires a victim click.
- **Failure scenario:** a tenant-admin-level `is_staff` user publishes a post whose body contains a `javascript:` markdown link → any public reader who clicks it runs script in the app origin (session-cookie theft, CSRF-token exfiltration).
- **Evidence:** both templates use `|safe`; both context values come from `markdownify(escape(...))`; no `bleach`/allowlist step exists (`grep` for `bleach|sanitize|MARKDOWNX.*safe` → none in blog/listings).
- **Fix:** run the rendered HTML through an allowlist sanitizer (`bleach.clean` / `nh3`) that drops non-`http(s)/mailto` schemes, or configure a markdown URL-sanitizing extension, before marking safe. **Effort:** Small. **Verification:** publish a post with body `[x](javascript:alert(1))`, load the detail page, assert the anchor `href` is stripped/neutralized.
- **Deliberate?** None found — `escape()`-first suggests the authors intended to block HTML injection but did not account for markdown link schemes.

## Structural smells (candidates for `arch-audit.md`)

- Permissive `getattr(settings, FLAG, True)` across every module (TA2) is a *class*, not scattered bugs — it points to a missing "required settings contract / startup validation" layer rather than per-callsite fixes.
- `QUICKSCALE_MODE` defaulting to `"solo"` (TA19) means the tenancy posture is inferred from an absent setting; the isolation boundary should fail toward *more* isolation or be a required, validated value.
- Rate-limiting correctness (TA18+TA24) depends on two ambient facts the generated app doesn't guarantee — canonical client IP behind the proxy and a shared cache — suggesting throttling belongs at the edge/proxy or behind an explicit "abuse-control backend configured" gate.

## Tooling gaps

- **`bandit`** (or `semgrep` py rules) in CI would systematically catch TA16 (secret echo), TA22/TA25 (`mark_safe`/`|safe` on non-constant), and future injection sinks. None currently runs.
- **`pip-audit` / `safety`** CI step — no dependency-CVE gate exists; add one so TA-class dependency findings are continuous, not a manual lockfile read.
- **A settings-contract check** (custom Django system check) asserting each `QUICKSCALE_*_ENABLED` / `QUICKSCALE_MODE` is explicitly set would close the whole TA2/TA19 class at startup instead of per-callsite.
- **`.gitignore` + pre-commit hook** for build artifacts (`coverage.json`, `pytest_cov_log.txt`, `htmlcov/`) closes TA23 and prevents recurrence.

*Categories swept with no new qualifying finding: injection sinks, deserialization, crypto misuse, subprocess/argv leakage, concurrency (TOCTOU/locks — billing & orgs are lock-guarded), resource leaks (context managers used throughout), N+1 (querysets use `select_related`/`prefetch_related`).*
