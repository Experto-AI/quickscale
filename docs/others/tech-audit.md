# QuickScale — Deep Technical Audit (defect sweep)

> **Audit snapshot:** 2026-09-17 at `d2aee905` (branch `v89`) · **Reconciled:** 2026-09-18 through `1270ed46`

---

## 1. Orientation summary

QuickScale is a **Python 3.14 / Django project generator and module workspace** laid out as a Poetry
monorepo: `quickscale_core` (generator, Jinja2 templates, DR/backup engine, manifest + plan-apply
system), `quickscale_cli` (Click CLI: `init`/`apply`/`deploy railway`/Docker dev commands),
`quickscale_devtools`, and twelve first-party Django modules under `quickscale_modules/`
(analytics, auth, backups, billing, blog, crm, forms, listings, notifications, orgs, social,
storage). There are **three distinct deployment realities**, and every finding below names the one
it lives in:

- **R1 — the generator/CLI itself**, run on a developer or CI machine. Local trust boundary; input
  is `quickscale.yml`, the module manifest, and CLI arguments. Not internet-facing.
- **R2 — the generated Django application**, deployed to Railway (or any container host) behind a
  reverse proxy, internet-facing, multi-tenant when `QUICKSCALE_MODE=saas`. This is where severity
  concentrates: the generator's templates *are* first-party code under §1d, audited as the code
  they produce.
- **R3 — the release pipeline** (`.github/workflows/publish.yml`), which builds wheels and publishes
  to PyPI over OIDC trusted publishing.

**Entry points.** R2: Django URLconfs per module — DRF `APIView`s in billing/forms/crm, two
`csrf_exempt` webhook endpoints (Stripe, notifications), blog media-upload endpoints with a custom
token auth path, class-based org/auth views. R1: the Click command tree and `start.sh`/`Dockerfile`
as generated launchers. R3: tag-triggered workflow dispatch.

**Tooling baseline.** Ruff (E/W/F/I/N/UP/D, line-length 100, `target-version = py314`), mypy with
django-stubs, pytest + pytest-cov + pytest-django + pytest-timeout, vulture/radon/pylint for
quality metrics, pre-commit declared as a dev dependency. CI runs lint, a rendered-frontend lint
gate, several fail-fast contract jobs, and a separate BYPASSRLS-privileged test workflow. **No
security scanner is wired into CI** — no secret scanning, no SAST, no `pip-audit`/dependency SCA,
no container or IaC scanning. Under §2d that absence is a tooling gap, not coverage, and nothing in
this report was deflated on the assumption that a scanner already catches it.

**Oracle list (the project's own declared invariants, mined per §2g).**

1. Runtime serving must use a restricted `NOSUPERUSER`/`NOBYPASSRLS` role; the app fails closed
   when `RUNTIME_DATABASE_URL` is absent (`production.py.j2`, `OPERATIONS.md.j2`, the orgs boot
   guard in `apps.py`).
2. Tenant context (`app.current_org_id`) must never leak across call or request boundaries; RLS is
   the enforcement mechanism (`current_org.py`, T1.19/AF9 contracts).
3. Privileged command mode is a **one-shot inline prefix, never persistent configuration**
   (`README.md.j2:310`, `production.py.j2`).
4. Secrets must not reach process argv — values are piped via stdin or read from the environment
   inside Python (`railway_utils.set_railway_variable`, `start.sh.j2` step 3).
5. DRF defaults fail closed: `IsAuthenticated` unless a view explicitly opts into public access
   (`base.py.j2:371`).
6. Single-host (no-proxy) deployments can disable forwarding trust in their environment and keep
   plain `REMOTE_ADDR` behaviour (`production.py.j2:112–117`).
7. Webhook processing is idempotent (`handle_stripe_event` docstring, `WebhookEvent` uniqueness).

**Data-sensitivity context (§2i).** R2 handles: user credentials and session material; Stripe
customer/subscription/invoice identifiers and a credit ledger (money-adjacent, not card data —
Stripe Checkout is hosted, so no PAN touches this code); tenant-scoped business data across twelve
modules; and **full database dumps** produced by the DR/backup engine, which are the single
highest-value artifact in the system. Secrets live in the environment (`SECRET_KEY`,
`DATABASE_URL`, `RUNTIME_DB_PASSWORD`, `QUICKSCALE_BILLING_WEBHOOK_SECRET`) and are surfaced to
Railway over stdin. Logs are JSON-structured to stdout. R1 handles no sensitive data beyond the
local `.env` (which contains only `postgres:postgres` dev credentials).

### Coverage statement

**Read in full:** the generator's settings templates (`base.py.j2`, `production.py.j2`,
`local.py.j2` headers), `.env.j2`, `start.sh.j2`, `db/init.sql.j2`; `quickscale_core/dr_engine/`
(`primitives.py`, `recovery.py` gate path, `orchestration.py` dump/restore callers);
`quickscale_modules/billing/services.py` (Stripe client wrapper, webhook pipeline, `credit_user`,
`cancel_current_subscription`) and `views.py` permission surface; `quickscale_modules/auth/views.py`;
`quickscale_modules/orgs/apps.py` and `current_org.py`;
`quickscale_modules/notifications/` webhook ingestion and signature verification; the blog rate
limiter; `utils/file_utils.validate_project_name`; `utils/railway_utils.py` secret-handling paths;
all four GitHub Actions workflows.

**Sampled:** `quickscale_cli/` command modules (subprocess-sink sweep across all 94 files, targeted
reads of `railway_utils.py`, `development_commands.py`); the crm/forms/listings/social/analytics
modules (sink and decorator sweeps, targeted reads of the analytics template tag and the forms
throttle); `quickscale_core/` manifest, contracts, and apply/ledger subsystems.

**Skipped:** the `showcase_react` theme's TypeScript/React sources and `e2e/` specs; the ~350 test
files except for the tamper sweep (§3.8) and the chosen-trade-off checks; all migrations except
where a finding touched one; `graphify-out/`, `htmlcov/`, `dist/`, `.venv/`.

**Audit tools run:** none — the repo wires no dependency/SCA or SAST step, and none was installed;
no scanner output is transcribed here. Source reading, `git log`, and targeted greps only.

**Empirical checks (§1e), both side-effect-free:**

1. `dj_database_url.parse('postgresql://u:p@h:5432/db?sslmode=verify-full&sslrootcert=/etc/ca.pem')`
   in the project venv → `OPTIONS: {'sslmode': 'verify-full', 'sslrootcert': '/etc/ca.pem'}`.
   **Confirmed** TA-01: TLS parameters live in `OPTIONS`, which the dump/restore command builders
   did not read before the `OPTIONS` translation landed.
2. Walked a `project.slug` of `"evil\n"` through `validate_project_name`
   (`file_utils.py:22–55`) on paper: `re.match(r"^[a-z][a-z0-9_-]*$", name)` accepts a trailing
   newline (Python `$` semantics), but `package_name.isidentifier()` rejects it two lines earlier.
   **Refuted** a candidate template-injection finding — the layer-up check holds.

**Residual risk (§1f/v4).** This sweep reasoned from source, not from a running deployment. It did
**not** cover: the React/TypeScript frontend and its bundle (client-side secret exposure and XSS
sinks are unexamined); real query plans, index usage, or any performance claim requiring a live
database; the actual privilege state of a deployed runtime role (only the code that provisions and
guards it); the behaviour of a freshly generated project booted end-to-end; and dependency CVE
exposure, since no audit tool was run. Silence in this report about those areas means *not looked
at*, not *clean*.

---

## 2. Machine-readable finding index

```yaml
- id: orgs-ready-early-return-skips-receivers
  severity: S3
  category: "I. Correctness"
  title: Privileged-command exemption skips GUC priming and the last-owner backstop
  effort: Small
  confidence: High
  status: open
  reality: R2
  chain: []
- id: pipeline-mutable-action-refs
  severity: S3
  category: "VII. Dependencies, build, and pipeline hygiene"
  title: Publishing workflow trusts mutable action refs and an unpinned Poetry
  effort: Small
  confidence: High
  status: open
  reality: R3
  chain: []
- id: build-system-requires-unpinned
  severity: S4
  category: "VII. Dependencies, build, and pipeline hygiene"
  title: Every package declares an unpinned poetry-core build requirement
  effort: Trivial
  confidence: High
  status: open
  reality: R3
  chain: []
```

---

## 3. Summary table

| ID | Sev | Category | Title | Effort | Conf | Status |
|---|---|---|---|---|---|---|
| `orgs-ready-early-return-skips-receivers` | S3 | Correctness | Privileged-command exemption skips two other installs | Small | High | open |
| `pipeline-mutable-action-refs` | S3 | Pipeline | Publishing workflow trusts mutable refs | Small | High | open |
| `build-system-requires-unpinned` | S4 | Pipeline | Unpinned `poetry-core` build requirement | Trivial | High | open |

**Counts:** S1 — 0 · S2 — 0 · S3 — 2 · S4 — 1 · total 3.

---

## 4. Findings

### Finding 1: The privileged-command exemption skips GUC priming and the last-owner backstop

- **ID:** `orgs-ready-early-return-skips-receivers` · **S3** · Reality **R2** · Confidence **High**
- **Location:** `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py:186–188`
  (`QuickscaleOrgsConfig.ready`)
- **Defect + failure scenario:** `if _is_privileged_command(): return` returns from `ready()`
  entirely, so three later installations never happen: the AF9 GUC priming execute wrapper and its
  `connection_created` signal (lines 190–202), the SA70 `pre_delete` last-owner backstop receiver
  (lines 204–213), and the SA1.3 tenant-isolation system check registration (line 217). The
  intent — skip the BYPASSRLS guard during `migrate` — is served by `_check_rls_role()` alone, and
  note the asymmetry: the *other* exemption, `QUICKSCALE_ALLOW_BYPASSRLS=1`, returns from inside
  `_check_rls_role` (line 124) and therefore leaves the rest of `ready()` intact. Concretely: a
  data migration that deletes `OrganizationMembership` rows during
  `QUICKSCALE_PRIVILEGED_COMMAND=migrate manage.py migrate` runs with the last-owner invariant
  unenforced and can leave an organization with members but no owner — a state the application's
  own guard (`auth/views.py:141–166`) exists to prevent and cannot repair afterwards. The priming
  wrapper's absence is harmless in this window (the privileged role bypasses RLS anyway), and
  `check_tenant_isolation` is invoked explicitly by the Makefile rather than relying on `ready()`,
  which is why this is S3 and not higher.
- **Fix:** Replace the bare `return` with a narrowed skip — call `_check_rls_role()` only when
  `not _is_privileged_command()`, and let the wrapper install, the `pre_delete` connection, and the
  check registration run unconditionally. **Effort: Small.** Verify with a test that sets
  `QUICKSCALE_PRIVILEGED_COMMAND=migrate`, re-runs `ready()`, and asserts
  `pre_delete` has the `_protect_last_owner_on_membership_delete` receiver connected.
- **Refutation:** Checked whether the early return is load-bearing — whether priming or the
  `pre_delete` receiver would *break* `migrate`. Priming issues `SET LOCAL app.current_org_id`
  inside the migration's transaction, which is valid; the `pre_delete` receiver only raises on an
  actual last-owner deletion, which is the behaviour wanted. Checked `git blame`-adjacent comments:
  the block documents *why the guard* is exempted and says nothing about the other three installs,
  which reads as an unintended consequence of `return` rather than a decision.
  **Fix risk:** a migration that legitimately deletes owner memberships (a data cleanup) will now
  be blocked by the backstop and will need an explicit bypass — worth checking existing migrations
  before landing.

### Finding 2: The publishing workflow trusts mutable action refs and an unpinned Poetry

- **ID:** `pipeline-mutable-action-refs` · **S3** · Reality **R3** · Confidence **High**
- **Location:** `.github/workflows/publish.yml:294`, `:318`
  (`uses: pypa/gh-action-pypi-publish@release/v1`), `:101`, `:209`
  (`uses: snok/install-poetry@v1` with `version: latest`); the same mutable-tag pattern repeats
  across `ci.yml` for `actions/checkout@v6`, `actions/setup-python@v6`, `pnpm/action-setup@v5`,
  `codecov/codecov-action@v5`.
- **Defect + failure scenario:** `@release/v1` is a **branch**, not a tag — whoever can push to it
  chooses the code that runs in the job holding `id-token: write`, i.e. the job authorized to
  publish to PyPI as this project. A compromise of that action (or of any `@vN` tag in the build
  job that produces the wheels the publish job consumes) ships attacker code to every QuickScale
  user through the package index, without anyone touching this repository. `snok/install-poetry@v1`
  with `version: latest` compounds it: the build tool's version is resolved at run time, so the
  artifact is not reproducible from the repository contents alone. Separately, `ci.yml` declares no
  top-level `permissions:` block, so every job runs with the repository's default `GITHUB_TOKEN`
  scope rather than an explicitly minimized one. This is one collapsed finding for the class rather
  than one per `uses:` line.
- **Fix:** Pin every third-party action to a full commit SHA with the human-readable version in a
  trailing comment; pin `snok/install-poetry`'s `version:` to an exact Poetry release; add
  `permissions: contents: read` at the top of `ci.yml` and let the two publish jobs keep their
  narrow `id-token: write`. Enable Dependabot for `github-actions` so the SHAs stay maintained.
  **Effort: Small.** Verify with a workflow-lint step (`zizmor` or `actionlint`) in CI that fails on
  an unpinned `uses:`.
- **Refutation:** Checked the highest-value pipeline attack first and did **not** find it: there is
  no `pull_request_target` anywhere, no workflow checks out untrusted fork code while holding
  secrets, and no untrusted string (`github.head_ref`, PR title, issue body) is interpolated into a
  `run:` step. PyPI publishing correctly uses OIDC rather than a long-lived token. The pipeline is
  in good shape; what remains is the supply-chain pinning, which is why this is S3 and not higher.
  **Fix risk:** none functional — SHA pinning is inert until an action is updated, at which point
  the update becomes an explicit, reviewable commit rather than a silent one.

---

### S4 findings

- `build-system-requires-unpinned` · `quickscale_core/pyproject.toml:41–43`,
  `quickscale_cli/pyproject.toml:40–42`, and the sibling packages · every package declares
  `requires = ["poetry-core"]` with no version bound, so the build backend is whatever resolves at
  build time. · Pin to a compatible range, e.g. `poetry-core>=2.0,<3.0`.

---

## 5. Entry-point × safeguard matrix

Cells name the layer that supplies the safeguard, or the finding ID for an empty one.
`n/a` = the safeguard does not apply to that entry point.

| Entry point | AuthN | AuthZ | Input validation | Output encoding | Rate limit | Timeout | Idempotency | Error shape | Audit record |
|---|---|---|---|---|---|---|---|---|---|
| `StripeWebhookView` (billing) | HMAC via `construct_event` | n/a (signature *is* authz) | payload key checks in each handler | JSON | — *(signature-gated; acceptable)* | implicit Stripe SDK timeout — see Notes | session advisory mutex spans processing | explicit 400/403/500 in view | `WebhookEvent` row |
| `NotificationWebhookView` | HMAC + timestamp TTL, `compare_digest` | n/a | explicit required-field checks + `validate_email` | JSON | — *(signature-gated)* | not applicable (no outbound call) | idempotency key + atomic block | explicit 400/403 | delivery event row |
| `CreateCheckoutSessionView` + billing siblings | `SessionAuthentication` + explicit `is_authenticated` | `_resolve_request_organization(require_owner=True)` | DRF serializer | DRF JSON renderer | `billing_checkout` / `billing_portal` scopes | implicit Stripe SDK timeout — see Notes | stable reservation-derived Stripe idempotency keys | DRF | Stripe-side |
| `PlanListView` | `AllowAny` — deliberate, public catalog | n/a (public data only) | n/a (GET, no params) | DRF | `DEFAULT_THROTTLE_RATES` (`anon`/`user`) | n/a | n/a | DRF | n/a |
| `BillingDashboardView` | `LoginRequiredMixin` | org resolution in context | n/a | Django template autoescape | n/a | n/a | n/a | Django | n/a |
| Blog media upload API | `authenticate_blog_api_request` (session or token) | author + `_resolve_api_org` | request parsing in `create_blog_media_asset_from_request` | JSON | custom limiter (atomic counter, hashed identity) | n/a | n/a | JSON | n/a |
| Forms public submit | `AllowAny` — deliberate, public form | n/a | DRF serializer | DRF | `FormSubmitThrottle` + required `FORMS_RATE_LIMIT` | n/a | n/a | DRF | submission row |
| Forms admin list / CRM admin views | DRF auth | `IsAdminUser` | DRF serializer | DRF | `DEFAULT_THROTTLE_RATES` (`anon`/`user`) | n/a | n/a | DRF | n/a |
| `ProfileView` / `ProfileUpdateView` | `LoginRequiredMixin` | `get_object` returns `request.user` — no IDOR surface | `ProfileUpdateForm` | template autoescape | out of scope — session-auth'd self-service | n/a | n/a | Django | n/a |
| `AccountDeleteView` | `LoginRequiredMixin` | self only | confirmation form | template autoescape | out of scope — same | provider I/O outside DB transactions; implicit Stripe SDK timeout — see Notes | compensating resume on delete failure | Django messages | n/a |
| Org views (`OrgListView`, `OrgCreateView`, detail/member views) | `LoginRequiredMixin` | `OrgRoleMixin` + `SaasModeRequiredMixin` | Django forms | template autoescape | out of scope | n/a | n/a | Django | n/a |
| Analytics template tag (`analytics_public_config_json`) | n/a (render-time) | n/a | n/a | `_JSON_HTML_ESCAPES` on `<`, `>`, `&` — see Notes | n/a | n/a | n/a | n/a | n/a |
| CLI command tree (R1) | OS user | OS file permissions | `validate_config` + `validate_project_name` | n/a | n/a | per-`subprocess` timeouts, sampled | apply ledger | Click exit codes | apply ledger |
| `start.sh` generated launcher (R2 boot) | n/a | superuser `DATABASE_URL`, refuses to repurpose a superuser role | env-var presence checks | `sql.Identifier`/`sql.Literal` | n/a | n/a | idempotent role re-sync | `set -e` + explicit messages | step log |
| DR backup / restore (R2 scheduled + admin) | Django admin / management command | `_restore_execution_allowed` env gate + `--allow-production` | archive format + PG18 contract checks | n/a | n/a | `PGSSLMODE`/`PGCONNECT_TIMEOUT` translated from connection `OPTIONS` | restore confirmation value | `BackupError` with command context | artifact metadata rows |
| Release pipeline (R3) | GitHub OIDC | job `permissions` on publish jobs only | n/a | n/a | n/a | n/a | n/a | job failure | workflow log |

Every empty cell above is resolved: it carries a finding ID, or a stated reason it does not apply.

---

## 6. Per-subsystem verdicts

- **billing** — clean after the generated DRF throttle defaults and the billing
  checkout/portal scopes landed. Read in full: the Stripe client wrapper, the webhook pipeline,
  `credit_user`, `cancel_current_subscription`, and the whole permission surface of `views.py`.
- **notifications** — clean. Webhook ingestion and signature verification read in full.
- **auth** — clean after provider I/O moved outside database transactions with compensating resume.
  All 551 lines read in the baseline pass; the account-deletion correction was re-read.
- **orgs** — `orgs-ready-early-return-skips-receivers`. `apps.py` and `current_org.py` read in full;
  `views.py` decorator surface and `managers.py`/`tenancy.py` sampled.
- **blog** — clean after the rate limiter moved to a single atomic counter with hashed client
  identities. The rate limiter and API authentication path read in full; the rest sampled.
- **dr_engine / backups** — clean on the dump/restore TLS posture, its one finding. `primitives.py`,
  the `recovery.py` execution gate, and the `orchestration.py` call sites read in full.
- **generator templates** — clean after the DRF throttle defaults and the composable
  `REST_FRAMEWORK` block landed. `base.py.j2`, `production.py.j2`, `.env.j2`, `start.sh.j2` read in
  full.
- **quickscale_cli** — clean on the sinks swept. All 94 files swept for shell/eval/deserialization
  sinks; `railway_utils.py` secret handling read in full.
- **CI/CD (R3)** — `pipeline-mutable-action-refs`. All four workflows read in full.
- **analytics, crm, forms, listings, social, storage** — clean on the lenses applied (injection
  sinks, permission decorators, `mark_safe`/raw-SQL sweeps). Not read in full; see residual risk.

---

## 7. Clean sweeps worth recording

- **No shell injection anywhere.** Zero occurrences of `shell=True`, `os.system`, `eval`, `exec`,
  `pickle.loads`, or bare `yaml.load` across ~640 first-party source files. Every one of the ~60
  `subprocess.run` call sites passes an argument list.
- **Secrets stay off argv.** `set_railway_variable` pipes values through stdin
  (`railway_utils.py:338–372`); `start.sh.j2` reads `RUNTIME_DB_PASSWORD` inside Python from the
  environment. Oracle item 4 holds everywhere it was checked.
- **Project-name validation is layered correctly.** `validate_project_name`'s regex accepts a
  trailing newline, but `isidentifier()` rejects it first — verified by walking the input through
  (empirical check 2). No template-injection path from `project.slug`.
- **Notification webhook verification is textbook.** HMAC over the raw body, a timestamp TTL that
  bounds replay, and `hmac.compare_digest` for the comparison
  (`notifications/services.py:722–754`).
- **Credit double-spend is impossible even if the webhook is processed twice.** A partial unique
  index (`quickscale_billing_unique_stripe_event_id_per_type`) plus an `IntegrityError` handler that
  re-fetches the committed row (`billing/services.py:830–870`). Webhook processing now also holds a
  session advisory mutex across handler execution and result persistence.
- **`AllowAny` in billing is deliberate, not a hole.** Every `AllowAny` view either serves genuinely
  public data (`PlanListView`) or re-checks `request.user.is_authenticated` by hand to return a
  JSON 401 instead of a login redirect (`views.py:180–182` and siblings).
- **Runtime role provisioning is hardened.** `start.sh.j2` refuses to repurpose a superuser role or
  to target the `DATABASE_URL` login itself, and uses `psycopg2.sql.Identifier`/`Literal`
  throughout rather than string formatting.
- **The pipeline's worst-case attack surface is absent.** No `pull_request_target`, no untrusted
  fork checkout beside secrets, no untrusted string interpolated into a `run:` step, and PyPI
  publishing over OIDC rather than a stored token.
- **No test tampering.** All 42 skip markers in the repository are conditional `skipif`s with
  stated reasons (git availability, PostgreSQL version); no bare `skip`, no `xfail`, no assertion-free
  test found in the sweep.
- **Chain pass (§3.10) ran.** The original chain between an unthrottled checkout endpoint and a
  Stripe call inside a lock-holding transaction was broken by moving provider I/O outside database
  transactions. The endpoint's throttle gap is closed; the implicit Stripe SDK timeout remains a
  watch item. No other pair combined into anything above its parts.

---

## 8. Structural smells

*(candidate inputs for the companion architectural audit — one line each, not findings here)*

- Rate limiting is per-module folklore: forms uses a DRF `ScopedRateThrottle`, blog hand-rolls its
  own atomic counter limiter, and everything else relies on the generated `user`/`anon` defaults —
  this points at a missing shared throttling contract in the module ABI, not at any one endpoint.
- Outbound-call discipline (timeouts, retry caps, keeping network I/O out of transactions) remains
  distributed across module boundaries. Billing and auth now share transaction-safe services, but
  timeout policy is still implicit in the Stripe SDK configuration.
- The pg_dump/pg_restore path now has one owner of its connection parameters
  (`_resolve_postgres_connection_parameters`), but `start.sh.j2`'s psycopg2 connect still builds its
  connection from `DATABASE_URL` on its own — the remaining separate constructor of "how this system
  connects to its database."

---

## 9. Tooling gaps

- **Dependency/SCA scanning in CI** (`pip-audit` or `poetry audit` against `poetry.lock`, failing
  the build). Nothing exists today; this report therefore reaches no conclusion at all about CVE
  exposure. Would systematically cover §VII.
- **Secret scanning** (gitleaks or GitHub's native push protection). Nothing exists today; the
  sweep found no committed secret, but that silence rests on greps, not on a scanner.
- **Workflow linting** (`zizmor` or `actionlint`), failing on unpinned `uses:` refs and on missing
  top-level `permissions:`. Would have caught **`pipeline-mutable-action-refs`** and keeps it
  caught.
- **Ruff `S` (flake8-bandit) and `ASYNC` rule sets**, currently unselected in `ruff.toml`. `S` would
  flag the `except Exception: return False` swallow patterns.

---

## 10. Notes (watch items)

- **Stripe SDK request timeout is implicit** (`billing/services.py:511–528`). Provider calls now run
  outside database transactions and organization-row lock windows, so a slow request no longer
  amplifies database contention or creates the remediated rollback inconsistency. The client still
  sets no explicit timeout or retry policy; promote this if operational latency requires a tighter
  bound or another provider client duplicates the omission.
- **`QUICKSCALE_PRIVILEGED_COMMAND` as persistent configuration.** Setting it in the environment
  would disable the BYPASSRLS boot guard for a serving process. Not a finding: `production.py.j2`
  refuses to start unless `RUNTIME_DATABASE_URL` is explicitly blank alongside it, which is the
  layer-up guard, and the contract is stated in the oracle (item 3). Worth watching because the
  guard lives in one settings module and the exemption in another.
- **`analytics_public_config_json` escapes `<`, `>`, `&` but not `'` or `/`**
  (`analytics_tags.py:15–19, 40`). Safe in a `<script>` body (the `<` escape breaks `</script>`) and
  in a double-quoted attribute. It would break out of a **single-quoted** HTML attribute. No current
  template uses it that way; re-check if one starts to.
- **`_build_pg_*_command` echoes host/user/database into `BackupError` messages**
  (`primitives.py:168–170`). No password is exposed (it travels in `PGPASSWORD`), so this is
  infrastructure detail in an operator-facing error, not a leak. Deliberate and useful.
- **`set_railway_variable` swallows every exception and returns `False`**
  (`railway_utils.py:370–372`). The caller does check the return value and collects failed keys, so
  no failure is silently lost — but the *reason* is, which will cost someone a debugging session.
  Not promoted; no incorrect behaviour results.
- **Future-dated notification webhook timestamps** are accepted within the TTL because the age check
  uses `abs()` (`notifications/services.py:741`). Conventional and harmless against a signed
  payload; noted so a future reader does not re-derive it.

---

*§4 categories swept that produced no qualifying finding: I (correctness — boundary/null/error-swallow
sweeps), IV (resources and I/O), V (performance), VIII (tests), X-frontend, X-IaC.*
