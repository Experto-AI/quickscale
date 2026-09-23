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
gate, several fail-fast contract jobs, and a separate BYPASSRLS-privileged test workflow. The
scanner baseline has since closed: SA123 wired a checksum-pinned Trivy dependency scan and a Bandit
static-security gate, and SA202 added a checksum-pinned gitleaks secret scan and a zizmor
workflow-security gate that fails on unpinned `uses:` refs and missing top-level `permissions:`.
Ruff `S` is now selected for maintained source, and `ASYNC` is recorded as not applicable (the tree
has no async code). Container and IaC scanning remain absent — a tooling gap, not coverage.

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
- id: billing-checkout-endpoints-unthrottled
  severity: S3
  category: "III. Security"
  title: Stripe-calling endpoints have no throttle and no DRF throttle defaults exist
  effort: Small
  confidence: High
  status: open
  reality: R2
  chain: []
- id: orgs-ready-early-return-skips-receivers
  severity: S3
  category: "I. Correctness"
  title: Privileged-command exemption skips GUC priming and the last-owner backstop
  effort: Small
  confidence: High
  status: open
  reality: R2
  chain: []
- id: blog-throttle-racy-on-database-cache
  severity: S3
  category: "II. Concurrency"
  title: Blog rate limiter is non-atomic on the default production cache backend
  effort: Small
  confidence: Medium
  status: open
  reality: R2
  chain: []
- id: pipeline-mutable-action-refs
  severity: S3
  category: "VII. Dependencies, build, and pipeline hygiene"
  title: Publishing workflow trusts mutable action refs and an unpinned Poetry
  effort: Small
  confidence: High
  status: resolved
  reality: R3
  chain: []
- id: blog-throttle-ident-collision
  severity: S4
  category: "III. Security"
  title: Throttle cache key collapses ':' and '.' so an IPv6 and IPv4 client can share a bucket
  effort: Trivial
  confidence: High
  status: open
  reality: R2
  chain: []
- id: build-system-requires-unpinned
  severity: S4
  category: "VII. Dependencies, build, and pipeline hygiene"
  title: Every package declares an unpinned poetry-core build requirement
  effort: Trivial
  confidence: High
  status: resolved
  reality: R3
  chain: []
```

---

## 3. Summary table

| ID | Sev | Category | Title | Effort | Conf | Status |
|---|---|---|---|---|---|---|
| `billing-checkout-endpoints-unthrottled` | S3 | Security | Stripe-calling endpoints have no throttle | Small | High | open |
| `orgs-ready-early-return-skips-receivers` | S3 | Correctness | Privileged-command exemption skips two other installs | Small | High | open |
| `blog-throttle-racy-on-database-cache` | S3 | Concurrency | Rate limiter non-atomic on the default prod cache | Small | Medium | open |
| `pipeline-mutable-action-refs` | S3 | Pipeline | Publishing workflow trusts mutable refs | Small | High | resolved |
| `blog-throttle-ident-collision` | S4 | Security | IPv4/IPv6 throttle bucket collision | Trivial | High | open |
| `build-system-requires-unpinned` | S4 | Pipeline | Unpinned `poetry-core` build requirement | Trivial | High | resolved |

**Counts:** S1 — 0 · S2 — 0 · S3 — 4 · S4 — 2 · total 6.

---

## 4. Findings

### Finding 1: Stripe-calling endpoints have no throttle, and no DRF throttle defaults exist

- **ID:** `billing-checkout-endpoints-unthrottled` · **S3** · Reality **R2** · Confidence **High**
- **Location:** `quickscale_modules/billing/src/quickscale_modules_billing/views.py:171–230`
  (`CreateCheckoutSessionView`), `:227`, `:280`, `:332`, `:383` (the sibling checkout/portal views);
  the absent configuration is at
  `quickscale_core/.../templates/project_name/settings/base.py.j2:371–377`.
- **Defect + failure scenario:** `REST_FRAMEWORK` in the generated settings defines
  `DEFAULT_PERMISSION_CLASSES` and `NUM_PROXIES` but **no** `DEFAULT_THROTTLE_CLASSES` or
  `DEFAULT_THROTTLE_RATES`, and none of the billing views declares `throttle_classes`. Only the
  forms module (`forms/throttles.py`) and the blog module (its own hand-rolled limiter) rate-limit
  anything. So any single authenticated org owner can POST to `/billing/checkout/` in a loop; each
  request makes at least one and often two outbound Stripe API calls (`search_customers`,
  `create_customer`, `checkout_session.create`). The result is Stripe rate-limit exhaustion for the
  whole tenant fleet — every other tenant's checkout and webhook processing starts failing — plus
  a pile of abandoned Checkout Sessions. Per §III this is a *named* unprotected expensive
  operation, not a systemic complaint; the systemic version is recorded as a structural smell below.
  There is a mild oracle mismatch worth naming: `production.py.j2:120–123` tunes `NUM_PROXIES`
  specifically "so that DRF throttles and per-user rate limits are enforced consistently across all
  workers and replicas", which reads as though throttles are configured. They are not.
- **Fix:** Add `DEFAULT_THROTTLE_CLASSES`/`DEFAULT_THROTTLE_RATES` to the `REST_FRAMEWORK` block in
  `base.py.j2` with conservative `user`/`anon` scopes, and give the checkout and billing-portal
  views an explicit tighter `throttle_scope`. **Effort: Small.**
  Verify by posting past the rate in a test and asserting a 429.
- **Refutation:** Searched for a layer-up throttle — middleware in `base.py.j2:204–219`, the module
  middleware list, and each billing view's class body. `ClientIdentityMiddleware` normalizes the
  client IP *for* throttles but enforces nothing itself. No WAF or edge rate limit is configured in
  `railway.json.j2`. No refutation survived. **Fix risk:** a default `user` throttle applies to
  every DRF view in every generated project, so the rate must be generous enough not to break
  legitimate polling clients; ship it as a named default operators can raise.

### Finding 2: The privileged-command exemption skips GUC priming and the last-owner backstop

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

### Finding 3: Blog rate limiter is non-atomic on the default production cache backend

- **ID:** `blog-throttle-racy-on-database-cache` · **S3** · Reality **R2** · Confidence **Medium**
- **Location:** `quickscale_modules/blog/src/quickscale_modules_blog/views.py:303–330`
  (`_enforce_blog_api_rate_limit`); the backend selection is
  `.../templates/project_name/settings/production.py.j2` (Redis when `REDIS_URL` is set, otherwise
  `django.core.cache.backends.db.DatabaseCache`).
- **Defect + failure scenario:** The limiter relies on `cache.add` + `cache.incr` being atomic.
  That holds on `RedisCache`. In the configuration cell **production + no `REDIS_URL`** — which
  `production.py.j2` explicitly supports and which the template's own comment concedes is "slower"
  but coherent — the backend is `DatabaseCache`, whose `incr` is a read-then-write rather than a
  single atomic operation. N concurrent uploads then read the same counter value and write back the
  same increment, so the effective limit is far above the configured one. The `except
  RATE_LIMIT_CACHE_FALLBACK_ERRORS` branch at lines 317–321 has the same read-modify-write shape
  and makes it worse. Confidence is **Medium** rather than High: the exact atomicity of
  `DatabaseCache.incr` is a runtime property of the installed Django version, and I reasoned from
  the backend's documented behaviour rather than executing it.
- **Fix:** Either require a cache backend with atomic `incr` for the limiter and fail closed on
  boot when one is absent, or move the counter to a single `UPDATE ... SET n = n + 1 RETURNING n`
  against a dedicated table. **Effort: Small.** Verify by driving the limiter from N threads
  against a `DatabaseCache`-configured test settings module and asserting the observed request
  count never exceeds the limit — that is the runtime confirmation this finding is marked as
  needing.
- **Refutation:** Checked whether production always has Redis — it does not; `REDIS_URL` is
  documented as optional and the DB-cache branch is the written fallback, complete with a
  `createcachetable` step in `start.sh.j2`. Checked for a layer-up limiter — none.

### Finding 4: The publishing workflow trusts mutable action refs and an unpinned Poetry

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
- **Resolution (SA202, 2026-09-23):** every third-party `uses:` across all four workflows is pinned
  to a full commit SHA with the human-readable version in a trailing comment; `snok/install-poetry`
  installs Poetry 2.4.1 rather than `latest`; every workflow declares top-level
  `permissions: contents: read`, and the two publish jobs keep their narrow `id-token: write`. The
  `check-workflow-security` gate runs zizmor at a medium severity and confidence floor — exactly
  `unpinned-uses` and `excessive-permissions` — and fails on either, so the pinning cannot silently
  regress. Dependabot for `github-actions` remains a separate follow-up.

---

### S4 findings

- `blog-throttle-ident-collision` · `quickscale_modules/blog/src/quickscale_modules_blog/views.py:296–301`
  · `_get_blog_api_rate_limit_cache_key` replaces both `":"` and `"."` with `"_"`, so the IPv4
  address `1.2` and the IPv6 fragment `1:2` normalize to the same bucket — two unrelated clients can
  share a rate-limit budget, or evade one. · Hash the identifier
  (`hashlib.blake2s(ident.encode()).hexdigest()`) instead of character-substituting it.
- `build-system-requires-unpinned` · `quickscale_core/pyproject.toml:41–43`,
  `quickscale_cli/pyproject.toml:40–42`, and the sibling packages · every package declares
  `requires = ["poetry-core"]` with no version bound, so the build backend is whatever resolves at
  build time. · Pin to a compatible range, e.g. `poetry-core>=2.0,<3.0`. **Resolved (SA202,
  2026-09-23):** all seventeen repository `pyproject.toml` files declare
  `poetry-core>=2.0,<3.0`. The generator's `pyproject.toml.j2` template still emits the unbounded
  requirement into generated projects; it is out of SA202's package scope and is carried as a
  follow-up because changing it moves the SA90 emission fixture that the generator track owns.

---

## 5. Entry-point × safeguard matrix

Cells name the layer that supplies the safeguard, or the finding ID for an empty one.
`n/a` = the safeguard does not apply to that entry point.

| Entry point | AuthN | AuthZ | Input validation | Output encoding | Rate limit | Timeout | Idempotency | Error shape | Audit record |
|---|---|---|---|---|---|---|---|---|---|
| `StripeWebhookView` (billing) | HMAC via `construct_event` | n/a (signature *is* authz) | payload key checks in each handler | JSON | — *(signature-gated; acceptable)* | implicit Stripe SDK timeout — see Notes | session advisory mutex spans processing | explicit 400/403/500 in view | `WebhookEvent` row |
| `NotificationWebhookView` | HMAC + timestamp TTL, `compare_digest` | n/a | explicit required-field checks + `validate_email` | JSON | — *(signature-gated)* | not applicable (no outbound call) | idempotency key + atomic block | explicit 400/403 | delivery event row |
| `CreateCheckoutSessionView` + billing siblings | `SessionAuthentication` + explicit `is_authenticated` | `_resolve_request_organization(require_owner=True)` | DRF serializer | DRF JSON renderer | **`billing-checkout-endpoints-unthrottled`** | implicit Stripe SDK timeout — see Notes | stable reservation-derived Stripe idempotency keys | DRF | Stripe-side |
| `PlanListView` | `AllowAny` — deliberate, public catalog | n/a (public data only) | n/a (GET, no params) | DRF | `billing-checkout-endpoints-unthrottled` | n/a | n/a | DRF | n/a |
| `BillingDashboardView` | `LoginRequiredMixin` | org resolution in context | n/a | Django template autoescape | n/a | n/a | n/a | Django | n/a |
| Blog media upload API | `authenticate_blog_api_request` (session or token) | author + `_resolve_api_org` | request parsing in `create_blog_media_asset_from_request` | JSON | custom limiter — **`blog-throttle-racy-on-database-cache`**, `blog-throttle-ident-collision` | n/a | n/a | JSON | n/a |
| Forms public submit | `AllowAny` — deliberate, public form | n/a | DRF serializer | DRF | `FormSubmitThrottle` + required `FORMS_RATE_LIMIT` | n/a | n/a | DRF | submission row |
| Forms admin list / CRM admin views | DRF auth | `IsAdminUser` | DRF serializer | DRF | `billing-checkout-endpoints-unthrottled` (same missing default) | n/a | n/a | DRF | n/a |
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

- **billing** — `billing-checkout-endpoints-unthrottled`. Read in
  full: the Stripe client wrapper, the webhook pipeline,
  `credit_user`, `cancel_current_subscription`, and the whole permission surface of `views.py`.
- **notifications** — clean. Webhook ingestion and signature verification read in full.
- **auth** — clean after provider I/O moved outside database transactions with compensating resume.
  All 551 lines read in the baseline pass; the account-deletion correction was re-read.
- **orgs** — `orgs-ready-early-return-skips-receivers`. `apps.py` and `current_org.py` read in full;
  `views.py` decorator surface and `managers.py`/`tenancy.py` sampled.
- **blog** — `blog-throttle-racy-on-database-cache`, `blog-throttle-ident-collision`. The rate
  limiter and API authentication path read in full; the rest sampled.
- **dr_engine / backups** — clean on the dump/restore TLS posture, its one finding. `primitives.py`,
  the `recovery.py` execution gate, and the `orchestration.py` call sites read in full.
- **generator templates** — `billing-checkout-endpoints-unthrottled` (the missing DRF
  defaults). `base.py.j2`, `production.py.j2`, `.env.j2`, `start.sh.j2` read in full.
- **quickscale_cli** — clean on the sinks swept. All 94 files swept for shell/eval/deserialization
  sinks; `railway_utils.py` secret handling read in full.
- **CI/CD (R3)** — `pipeline-mutable-action-refs` (now resolved). All four workflows read in full.
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
  transactions. The unthrottled endpoint remains a standalone finding, and the implicit Stripe SDK
  timeout remains a watch item. No other pair combined into anything above its parts.

---

## 8. Structural smells

*(candidate inputs for the companion architectural audit — one line each, not findings here)*

- Rate limiting is per-module folklore: forms uses a DRF `ScopedRateThrottle`, blog hand-rolls a
  cache-counter limiter with its own IP normalization, and everything else has nothing — this
  points at a missing shared throttling contract in the module ABI, not at any one endpoint.
- `base.py.j2` **replaces** the whole `REST_FRAMEWORK` dict after `MODULE_SETTINGS`, so a module can
  never contribute DRF configuration (throttle rates, renderers, authentication classes) even
  though the settings-composition system exists precisely to let modules contribute settings.
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
  the build). **Closed by SA123** with Trivy against the single committed root lockfile, including
  development dependencies; `decisions.md` records Trivy as the approved lock-native replacement
  for the originally proposed `pip-audit` design. CVE exposure now reaches a conclusion on every
  run instead of none.
- **Secret scanning** (gitleaks or GitHub's native push protection). **Closed by SA202**: the
  `check-secret-scanning` gate acquires a checksum-pinned gitleaks v8.30.1 and scans the working
  tree, failing on any finding. Verified false positives live in `scripts/gitleaks.toml` with a
  reason per entry.
- **Workflow linting** (`zizmor` or `actionlint`), failing on unpinned `uses:` refs and on missing
  top-level `permissions:`. **Closed by SA202** as the `check-workflow-security` gate, which caught
  and keeps caught **`pipeline-mutable-action-refs`**.
- **A generated-project smoke boot** in CI (generate → `start.sh` → hit `/healthcheck/`). The repo
  has extensive rendered-template assertions but nothing that boots the artifact, which is the §4.X
  generator gap that lets template regressions ship.
- **Ruff `S` (flake8-bandit) and `ASYNC` rule sets**, previously unselected in `ruff.toml`.
  **Closed by SA202**: `S` is selected for maintained first-party source, with test trees and
  maintainer tooling excluded on the same terms as the Bandit source-root contract; every remaining
  finding is per-line suppressed with a specific reason. `ASYNC` is recorded as **not applicable** —
  the tree contains no `async def`, `asyncio`, `await`, or `async with`/`for` in first-party
  Python, so the rule set has nothing to govern.

---

## 10. Notes (watch items)

- **Stripe SDK request timeout is implicit** (`billing/services.py:511–528`). Provider calls now run
  outside database transactions and organization-row lock windows, so a slow request no longer
  amplifies database contention or creates the remediated rollback inconsistency. The client still
  sets no explicit timeout or retry policy; promote this if operational latency requires a tighter
  bound or another provider client duplicates the omission.
- **`REST_FRAMEWORK` clobbers module-supplied DRF config** (`base.py.j2:371`). Not promoted: no
  module ships a `REST_FRAMEWORK` key today, so it fails §0's *live* gate. It becomes a finding the
  day one does — and the natural fix for `billing-checkout-endpoints-unthrottled` may be exactly
  that. Recorded as the structural smell above.
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
