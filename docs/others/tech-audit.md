# QuickScale — Deep Technical Audit (defect sweep)

> **Audit snapshot:** 2026-09-23 at `1cf67cf7` (branch `v89`) · **Re-run of:** the 2026-09-17 pass at
> `d2aee905` · **Delta swept:** `d2aee905..1cf67cf7` (34 commits, 97 first-party production files)

---

## 1. Orientation summary

QuickScale is a **Python 3.14 / Django project generator and module workspace** laid out as a Poetry
monorepo: `quickscale_core` (generator, Jinja2 templates, DR/backup engine, manifest + plan-apply
system), `quickscale_cli` (Click CLI), `quickscale_devtools`, and twelve first-party Django modules
under `quickscale_modules/`. Three deployment realities, unchanged since the prior pass; every
finding names one:

- **R1 — the generator/CLI**, run on a developer or CI machine. Local trust boundary.
- **R2 — the generated Django application**, deployed to Railway (or any container host) behind a
  reverse proxy, internet-facing, multi-tenant when `QUICKSCALE_MODE=saas`. The generator's
  templates and the modules it installs are audited as the code they produce. Severity
  concentrates here.
- **R3 — the release pipeline** (`.github/workflows/publish.yml`), OIDC trusted publishing to PyPI.

**Entry points.** R2: per-module URLconfs — DRF `APIView`s in billing/forms/crm, two `csrf_exempt`
webhooks (Stripe, notifications), blog/listings staff publishing APIs with a custom token path,
class-based auth/org views, and the operator commands `purge_organization`,
`migrate_billing_to_orgs`, and the DR backup/restore surface. R1: the Click command tree plus the
generated `start.sh`/`Dockerfile` launchers. R3: tag-triggered workflow dispatch.

**Tooling baseline.** Ruff (E/W/F/I/N/UP/D plus `S` for maintained source), mypy with
django-stubs, pytest + pytest-cov + pytest-django + pytest-timeout, vulture/radon/pylint. Security
tooling, all **failing the build** on findings: Trivy dependency scan against `poetry.lock` (SA123),
Bandit (SA123), gitleaks v8.30.1 fetched checksum-pinned with traversal-safe extraction (SA202),
zizmor 1.30.1 at medium severity/confidence for `unpinned-uses` and `excessive-permissions` (SA202).
Container and IaC scanning remain absent — a tooling gap, not coverage.

**Oracle list (declared invariants, §2g).**

1. Runtime serving uses a restricted `NOSUPERUSER`/`NOBYPASSRLS` role and fails closed without
   `RUNTIME_DATABASE_URL` (`production.py.j2:209–232`, orgs boot guard `apps.py:197`).
2. Tenant context (`app.current_org_id`) never leaks across call or request boundaries
   (`current_org.org_scope`, T1.19/AF9 contracts).
3. Privileged command mode is a one-shot inline prefix and exempts **only** the role check (SA203).
4. Secrets never reach process argv (`railway_utils.set_railway_variable`, `start.sh.j2` step 3,
   DR `PG*` environment translation).
5. DRF defaults fail closed: `IsAuthenticated` plus `anon`/`user`/scoped throttles
   (`base.py.j2:394–421`).
6. Single-host deployments can disable forwarding trust, which also disables
   `X-Forwarded-Proto` trust (`production.py.j2:117–129`).
7. Webhook processing is idempotent and serialized per event (`handle_stripe_event`,
   `WebhookEvent` uniqueness, session advisory mutex).
8. Provider I/O never runs inside a database transaction; provider mutations serialize on the
   per-organization advisory mutex (`subscription_provider_mutation_lock`, 1270ed46).
9. Organization-removal obligations are declared once and enforced fail-closed at both removal
   boundaries (`orgs/removal.py`).
10. **Billing targets the latest Stripe API version, `2026-06-24.dahlia`**, the version the
    pinned stripe-python 15.3.1 ships. Webhooks sent under a different named release are rejected
    rather than misparsed, and any monthly version within `dahlia` is accepted. These are team
    decisions recorded 2026-09-23, now reflected in code and in the billing tests.

**Data-sensitivity context (§2i).** R2 handles user credentials and session material; Stripe
customer/subscription/invoice/checkout identifiers and a **credit ledger** (money-adjacent — Stripe
Checkout is hosted, so no card data touches this code); tenant-scoped business data across twelve
modules; and full database dumps from the DR engine, the highest-value artifact in the system.
Secrets live in the environment and reach Railway over stdin. Logs are JSON to stdout. R1 handles
no sensitive data beyond a local `.env` with `postgres:postgres` dev credentials.

### Coverage statement

**Re-run mode (§2f).** Prior HEAD `d2aee905`; delta `d2aee905..1cf67cf7` computed and the full
first-party production diff read. Commits classified: review-tracked — SA193, SA194, SA196, SA198,
SA199, SA200, SA201, SA202, SA203, `1270ed46` (the reconciliation commit for four prior findings);
**side-channel, elevated scrutiny** — `e12e9867` and `5696f10a` ("WIP: SA195 & SA192"; templates,
settings, React theme), `9ccc5031` (S608 suppression), and the CLI half of `cba8be07` (lint
suppressions across ~15 CLI files).

**Read in full:** `billing/services.py` provider wrapper, webhook pipeline, invoice/checkout/
subscription handlers, credit ledger, provider mutex, cancel/resume transitions (lines 124–1960,
2340–3240, 3620–3780, 4085–4230); `billing/views.py`, `adapter.py`, `apps.py`;
`auth/views.py` `AccountDeleteView`; `orgs/removal.py`, `purge_organization.py`, `middleware.py`,
the `current_org.py` delta and `org_scope`/`_tenant_context`, SA203 `apps.py`/`signals.py`;
`base.py.j2`, `production.py.j2`, the `local.py.j2`/`docker-compose.yml.j2`/`.env.j2` deltas,
`start.sh.j2` role step; blog limiter and API views; DR `primitives.py` delta and runner;
`apply/steps/env_sync.py` splice path; all four workflows (pin/permission/trigger sweep);
`scripts/check_secret_scanning.py` acquisition; React `lib/csrf.ts` and `base.html.j2` delta.

**Sampled:** the SA202 CLI hunks (verified suppression-only, no behaviour change), SA194 removal
(dangling-caller sweep), `migrate_billing_to_orgs.py` delta, test hunks of the delta (tamper sweep,
§3.8).

**Skipped:** the React/TypeScript sources beyond the CSRF helper and theme bootstrap; crm, forms,
listings, social, analytics, storage, notifications beyond the prior pass (no production delta
except template/CSS restyling and one suppression comment); migrations except the blog counter
table; `graphify-out/`, `htmlcov/`, `.venv/`.

**Audit tools run:** none beyond the project's own Python environment (Python 3.14, stripe
15.3.1, Django via the billing test settings). Scanner output is not transcribed.

**Empirical checks (§1e), all side-effect-free, no database, no network:**

1. `stripe` 15.3.1 SDK introspection → pinned API version `2026-06-24.dahlia`; `Invoice` has no
   `subscription` field (it has `parent`), `InvoiceLineItem` has no `price` (it has `pricing`),
   `Subscription` has no `current_period_start` (`SubscriptionItem` does). **Confirmed**
   `billing-stripe-api-version-drift`.
2. `issubclass(stripe.StripeObject, dict)` → `False`; `isinstance(<stripe.Event>, Mapping)` →
   `False`; `_normalize_mapping(<Event>)` → `{}`; `_normalize_mapping(<checkout.Session>)` → `{}`.
   **Confirmed** `billing-stripe-objects-normalized-empty`.
3. A locally signed `invoice.paid` body passed to the real `handle_stripe_event` with the real
   `StripeClient` → `BillingWebhookError: Stripe event payload is missing an id.` before any
   database access. **Reproduced** `billing-stripe-objects-normalized-empty` end to end.
4. `_extract_price_id` on a dahlia-shaped invoice → `BillingWebhookError: Stripe invoice payload is
   missing a billing price id.`; the identical invoice in the legacy line shape → `price_1`
   (control). **Reproduced** the `billing-stripe-api-version-drift` parse failure.
5. Field inventory: every Stripe field the billing code reads (≈60 `.get()` sites across Event,
   Invoice, InvoiceLineItem, Subscription, SubscriptionItem, Price, PaymentIntent, Customer,
   Checkout and portal sessions) checked against the dahlia SDK annotations. Only
   `Invoice.subscription`/`subscription_details`, `InvoiceLineItem.price`, and
   `Subscription.current_period_*` are absent; all status literals the code maps are still valid.
   **Scoped** the fix for `billing-stripe-api-version-drift` (added 2026-09-23 after the decision).
6. Walked on paper, **refuting** three candidates: `purge_organization --dry-run` performs only
   Stripe *retrieves* (`services.py:994–998`, `1125–1129`), so the dry run mutates no provider
   state; one-time checkout creation holds the same provider mutex the purge holds across
   reconcile-and-delete (`services.py:603`, `purge_organization.py:332`), so no purchase checkout
   can open mid-purge; `org_scope`'s `finally` restore statement could mask a database error raised
   directly in its own atomic, but every current `IntegrityError` handler wraps an inner savepoint,
   so no live trigger exists (carried as a watch item).

Checks 2–4 ran under the billing test settings with `QUICKSCALE_PRIVILEGED_COMMAND=migrate` set
inline for the one process, so the orgs boot guard skipped its database role probe. No database
connection was opened.

**Residual risk.** No live Stripe account or stripe-mock was exercised: the two billing findings
rest on the installed SDK's own objects and type definitions and on locally signed payloads, which
is exactly what production receives. The *webhook endpoint API version* of existing deployments is
unknown, and the proposed named-release matching assumes Stripe's monthly versions within `dahlia`
are additive. No PostgreSQL was available, so RLS behaviour, advisory-lock contention, and the
blog counter's concurrency were verified from source only. The React bundle, real query plans, and
dependency CVE exposure (covered by the Trivy gate, not by this pass) were not examined. Silence
about those areas means *not looked at*, not *clean*.

---

## 2. Machine-readable finding index

```yaml
- id: build-system-requires-unpinned
  severity: S4
  category: "VII. Dependencies, build, and pipeline hygiene"
  title: Generated projects still declare an unbounded poetry-core build requirement
  effort: Trivial
  confidence: High
  status: open
  reality: R2
  chain: []
```

---

## 3. Summary table

| ID | Sev | Category | Title | Effort | Conf | Status |
|---|---|---|---|---|---|---|
| `build-system-requires-unpinned` | S4 | Build hygiene | Generated `pyproject` build requirement unbounded | Trivial | High | open |

**Counts:** S1 — 0 · S2 — 0 · S3 — 0 · S4 — 1 · total 1 open. Reconciliation: 13 prior IDs
resolved and verified in code, 1 still open (narrowed), 0 regressed, 0 new.

---

## 4. Findings

### S4 findings

- `build-system-requires-unpinned` ·
  `quickscale_core/src/quickscale_core/generator/templates/pyproject.toml.j2:30` · The repository's
  17 package manifests are now bounded (`poetry-core>=2.0,<3.0`), but every *generated* project
  still declares `requires = ["poetry-core"]`, so its build backend resolves at build time. ·
  Emit `poetry-core>=2.0,<3.0` from the template and update the SA90 emission fixture in the same
  change.

---

## 5. Entry-point × safeguard matrix

Each cell names the layer that supplies the safeguard, or the finding ID where the entry point
fails. `n/a` means the safeguard does not apply to that entry point.

| Entry point | AuthN | AuthZ | Input validation | Output encoding | Rate limit | Timeout | Idempotency | Error shape | Audit record |
|---|---|---|---|---|---|---|---|---|---|
| `StripeWebhookView` (billing) | HMAC via SDK `construct_event` | n/a (signature is authz) | SDK objects converted before parsing; event API version enforced by named release | JSON | — (signature-gated) | implicit SDK timeout — Notes | per-event session advisory mutex + `WebhookEvent` unique id | 400/403/500 in view | `WebhookEvent` row |
| `NotificationWebhookView` | HMAC + timestamp TTL, `compare_digest` | n/a | required-field checks + `validate_email` | JSON | — (signature-gated) | n/a | idempotency key + atomic | 400/403 | delivery event row |
| Checkout / subscription-checkout / portal / cancel views | `SessionAuthentication` + explicit `is_authenticated` | `require_owner=True`, re-validated under the provider mutex (`_require_owner_provider_mutation_authorization`) | DRF serializer; provider responses converted before parsing | DRF JSON | `billing_checkout` / `billing_portal` 30/hour | implicit SDK timeout — Notes | reservation-derived Stripe idempotency keys | DRF | reservation rows |
| Credit balance / transactions / subscription detail | session + explicit check | `require_owner=True` | n/a (GET) | DRF | `user` default | n/a | n/a | DRF | n/a |
| `PlanListView`, `PricingPageView` | `AllowAny` — public catalog | n/a | n/a | DRF / autoescape | `anon`/`user` defaults | n/a | n/a | DRF | n/a |
| Blog / listings publishing APIs | session (CSRF enforced) or constant-time token | staff + `_resolve_api_org` | request parsing | JSON | DB-atomic fixed-window counter after auth — Notes | n/a | slug conflict → 409 | JSON | n/a |
| Forms public submit | `AllowAny` — public form | n/a | DRF serializer | DRF | `FormSubmitThrottle` + required rate | n/a | n/a | DRF | submission row |
| `AccountDeleteView` | `LoginRequiredMixin` | self only; last-owner check under row locks | confirmation form | autoescape | out of scope (self-service) | provider I/O outside transactions | locked re-validation + compensating resume | Django messages | removal-obligation skip log |
| Org views + `TenantMiddleware` | `LoginRequiredMixin` | membership check on the session org, 403 on mismatch | Django forms | autoescape | out of scope | n/a | n/a | Django | n/a |
| `purge_organization` (operator, R2) | shell access | UUID-only destructive target, reserved-org guard | UUID parse | n/a | n/a | n/a | tombstone; provider mutex across reconcile and delete | `CommandError` | tombstone row |
| `start.sh` launcher (R2 boot) | n/a | superuser `DATABASE_URL`; refuses to repurpose a superuser role | env presence checks | `sql.Identifier`/`sql.Literal` | n/a | n/a | idempotent role re-sync | `set -e` | step log |
| DR backup / restore (R2) | Django admin / command | `_restore_execution_allowed` + `--allow-production` | archive + PG18 contract checks | n/a | n/a | `PGCONNECT_TIMEOUT` from `OPTIONS`; background dispatch | confirmation value | `BackupError` | artifact rows |
| CLI command tree (R1) | OS user | OS permissions | `validate_config` + `validate_project_name` | n/a | n/a | per-subprocess timeouts (sampled) | apply ledger | Click exit codes | apply ledger |
| Release pipeline (R3) | GitHub OIDC | top-level `contents: read`; `id-token: write` on publish jobs only | n/a | n/a | n/a | n/a | n/a | job failure | workflow log |

Every empty cell is resolved with a finding ID or a stated reason.

---

## 6. Per-subsystem verdicts

- **billing** — clean. The locking, idempotency, and transaction discipline introduced in
  `1270ed46` is sound; the provider-payload boundary now converts SDK objects before parsing,
  pins one API version, and rejects deliveries from a different named release. Wrapper, webhook
  pipeline, handlers, ledger, mutex, and views read in full.
- **auth** — clean. `AccountDeleteView` read in full after the provider-I/O restructuring.
- **orgs** — clean. `removal.py` and `purge_organization.py` read in full; middleware, the
  `current_org` delta, and the SA203 wiring read in full.
- **blog** — clean. The limiter now uses one atomic upsert on a hashed identity against a counter
  table covered by the runtime role's default privileges.
- **dr_engine / backups** — clean. The SA198 translation is complete and the runner merges rather
  than replaces the environment (`primitives.py:153–155`).
- **generator templates** — `build-system-requires-unpinned`. Settings templates and the
  side-channel `local.py.j2`/compose/React-theme hunks are otherwise clean.
- **quickscale_core apply** — clean. `env_sync.py` writes empty placeholders only.
- **quickscale_cli / devtools** — clean. SA202 hunks are suppression-only; SA194 left no dangling
  caller.
- **CI/CD (R3)** — clean. All four workflows SHA-pinned with top-level `contents: read`; gitleaks
  acquisition is checksum-verified.
- **analytics, crm, forms, listings, social, storage, notifications** — no production delta beyond
  restyling and one suppression comment; prior verdicts stand, not re-read.

---

## 7. Clean sweeps worth recording

- **Prior closures verified in code, not changelog.** Eleven prior findings were re-opened at their
  fix locations and confirmed complete; see the reconciliation log.
- **Provider I/O is outside every transaction.** Checkout creation, cancellation, resume,
  reconciliation, and account deletion all make Stripe calls between short atomics. Each atomic
  re-validates under `select_for_update` on the organization row.
- **Purge is fail-closed on billing.** `--dry-run` performs only Stripe retrieves. The provider
  mutex spans reconcile and delete, and one-time checkout creation takes the same mutex, so no
  checkout can open mid-purge.
- **Credit ledger cannot double-credit.** Dedup runs by object id, then event id, then business
  reference, under the organization row lock, backed by a unique constraint and a
  savepoint-scoped `IntegrityError` recovery (`services.py:1654–1716`, `4085–4119`).
- **Owner authorization is re-checked after waiting for the mutex**
  (`_require_owner_provider_mutation_authorization`), so a demotion during a queued request
  refuses the Stripe mutation.
- **Advisory locks are re-entrant where nested.** `AccountDeleteView` holds the per-org mutex
  while `cancel_current_subscription` re-acquires the same key. PostgreSQL session advisory locks
  stack, so this cannot self-deadlock.
- **Blog counter table is reachable by the runtime role.** `ALTER DEFAULT PRIVILEGES` runs as the
  same superuser that runs `migrate` (`runtime_database.py:14–21`).
- **React CSRF is compatible with `CSRF_COOKIE_HTTPONLY=True`.** `getCsrfToken()` reads the
  injected `<meta name="csrf-token">` first (`lib/csrf.ts:5–8`).
- **No XSS sink entered with the side-channel template rewrites.** The delta adds no `|safe`,
  `autoescape off`, `innerHTML`, or template-interpolated inline script. The new theme bootstrap
  script reads only `localStorage`.
- **Pipeline surface stays closed.** No `pull_request_target`, no untrusted-string interpolation,
  all third-party actions SHA-pinned, Poetry pinned to 2.4.1, and every workflow carries top-level
  `contents: read`.
- **No test tampering in the delta.** The only new skip markers are conditional
  `skipif(REAL_ZIZMOR is None)`, and zizmor is a pinned dev dependency. Every assertion removal
  tracks SA194's deliberate code removal.
- **Chain pass (§3.10) ran.** No combination rose above its parts: the implicit Stripe timeout
  plus the session advisory mutex bounds contention by the SDK's default timeout (Notes).

---

## 8. Structural smells

*(candidate inputs for the companion architectural audit — one line each, not findings here)*

- Stripe payload knowledge is still spread across ad hoc `.get()` extractors over normalized
  dicts, though the module now converts SDK objects centrally, pins one API version, and rejects
  deliveries from a different named release. This points at a missing typed provider-adapter seam.
- Provider serialization rests on **session-level** `pg_advisory_lock`. It is correct on direct
  connections, but a transaction-pooling proxy (PgBouncer `pool_mode=transaction`) would silently
  void the mutex. That is an undeclared deployment contract.
- Outbound-call timeout policy is still implicit in the Stripe SDK defaults, now more
  consequential because the per-org mutex is held across those calls.
- `start.sh.j2`'s psycopg2 connection remains a second, separate constructor of "how this system
  connects to its database", beside `_resolve_postgres_connection_parameters`.

---

## 9. Tooling gaps

- **A real-SDK contract test for the billing provider wrapper** — closed: `test_stripe_contract.py`
  builds objects with `stripe.<Resource>.construct_from(...)`, signs webhook bodies locally for
  `stripe.Webhook.construct_event`, and the fixture builders round-trip every payload through the
  SDK at the pinned API version. A stripe-mock service in the e2e lane would still cover the same
  ground end to end.
- **A named-release pin test for Stripe** — closed: the contract test fails when the installed
  SDK's pinned API version moves to a new named release, so a `stripe` bump cannot silently change
  payload shapes.
- **Container and IaC scanning** — still absent (carried).
- **Dependabot (or equivalent) for `github-actions`** — the SHA pins from SA202 have no automated
  refresh path (carried follow-up).

---

## 10. Notes (watch items)

- **Stripe SDK request timeout is implicit** (`services.py:524–540`). stripe-python defaults to an
  80-second timeout. Since `1270ed46` every provider call runs while the per-organization session
  advisory mutex is held, and `pg_advisory_lock` waits with no `lock_timeout`. A stalled Stripe call
  therefore parks every other billing mutation for that organization for up to the SDK timeout.
  Bounded, so not promoted. Set an explicit client timeout if latency ever bites.
- **SA203's sender-free `pre_delete` receiver disables Django's fast-delete path for every model**
  (`orgs/apps.py:231`). This is an accepted, documented trade-off: first-party code has no bulk
  hot-path deletes, and `clearsessions` is not scheduled. Re-check if a scheduled bulk
  `QuerySet.delete()` (session cleanup, retention pruning) is ever added. It would now materialize
  every row in memory.
- **`org_scope`'s `finally` issues SQL after the body.** A database error raised directly inside
  the scope's own atomic, with no inner savepoint, would be replaced by
  `InternalError: current transaction is aborted`. No live trigger exists today: every
  `IntegrityError` handler wraps its own savepoint. Re-check when adding a handler that catches a
  DB exception across an `org_scope`.
- **Blog/listings API limiter counts only authenticated requests** (`blog/views.py:701–707`).
  Invalid-token attempts return 401 before the counter, so token guessing is unthrottled. That is
  acceptable while operators configure high-entropy `BLOG_API_TOKENS`, which nothing enforces.
- **`_find_existing_credit_transaction` scans every same-type credit row for the organization under
  `FOR UPDATE` when the fast lookups miss** (`services.py:4110–4115`). That is O(n) per new credit
  with n = the org's purchase or plan history. Negligible at current scale.
- **`QUICKSCALE_PRIVILEGED_COMMAND` as persistent configuration** — carried. `production.py.j2`
  still refuses to start unless `RUNTIME_DATABASE_URL` is explicitly blank alongside it. SA203
  narrowed the exemption to the role check alone.
- **`analytics_public_config_json` escapes `<`, `>`, `&` but not `'` or `/`** — carried. It is
  safe in a `<script>` body and in double-quoted attributes. Re-check if a template ever places it
  in a single-quoted attribute.
- **`_build_pg_*_command` echoes host/user/database into `BackupError`** — carried. No password is
  exposed; it is operator-facing detail.
- **`set_railway_variable` swallows every exception and returns `False`** — carried. The caller
  collects failed keys; only the reason is lost.
- **Future-dated notification webhook timestamps are accepted within the TTL** (`abs()` age check)
  — carried. Harmless against a signed payload.

---

*§4 categories swept with no qualifying finding this pass: II (concurrency — the new mutex and
lock-ordering paths), III (security — delta sinks, auth/authz, CSRF, pipeline), IV (resources),
V (performance), VI (operability), VIII (tampering), X-frontend (CSRF helper and theme bootstrap
only), X-generator.*

---

## 11. Reconciliation log

- 2026-09-23 — **process note:** the 2026-09-23 closeout commits (SA198–SA203) regenerated this
  file without log lines for ten prior IDs. Every prior ID was reinstated below after being
  re-verified in code.
- 2026-09-23 — `dr-backup-drops-tls-options`: resolved (`120d7d8b`, SA198). Verified at
  `primitives.py` `_LIBPQ_OPTION_ENVIRONMENT_VARIABLES` / `_resolve_postgres_connection_parameters`
  (both dump and restore builders) and the merging runner (`:153–155`).
- 2026-09-23 — `billing-stripe-call-inside-delete-txn`: resolved (`1270ed46`). Verified at
  `auth/views.py:97–295`: Stripe cancellation runs between the two locked atomics, a locked
  re-validation precedes deletion, and a compensating resume runs in `finally`.
- 2026-09-23 — `proxy-ssl-header-trusted-unconditionally`: resolved (`dd310cfc`, SA200). Verified
  at `production.py.j2:129`.
- 2026-09-23 — `billing-webhook-lock-released-before-processing`: resolved (`1270ed46`). Verified at
  `services.py:1810–1923`: the per-event session advisory mutex spans handler and persistence.
- 2026-09-23 — `billing-checkout-endpoints-unthrottled`: resolved (`d7f0cf87`, SA201). Verified at
  `billing/views.py:179,235,291,346`, `adapter.py:54–59`, `base.py.j2:406–421`.
- 2026-09-23 — `correlation-id-header-unbounded`: resolved (`dd310cfc`, SA200). Verified at
  `base.py.j2:136`, `:196–201`.
- 2026-09-23 — `orgs-ready-early-return-skips-receivers`: resolved (`aa5ff547`, SA203). Verified at
  `orgs/apps.py:197`, `:231`, `signals.py:69`. The fix-regression pass found no new defect; its
  fast-delete cost is a watch item.
- 2026-09-23 — `blog-throttle-racy-on-database-cache`: resolved (`d7f0cf87`, SA201). Verified at
  `blog/views.py:314–348`: a single `INSERT … ON CONFLICT … RETURNING`.
- 2026-09-23 — `blog-throttle-ident-collision`: resolved (`d7f0cf87`, SA201). Verified at
  `blog/views.py:303–311`: a BLAKE2s-hashed identity.
- 2026-09-23 — `stripe-search-query-unescaped`: resolved (`5556e710`, SA199). Verified at
  `services.py:255–262`, `4062–4069`.
- 2026-09-23 — `pipeline-mutable-action-refs`: resolved (`cba8be07`, SA202). Verified that every
  third-party `uses:` in all four workflows is SHA-pinned, Poetry is pinned to 2.4.1, and every
  workflow has top-level `permissions: contents: read`.
- 2026-09-23 — `build-system-requires-unpinned`: still-open, narrowed. `cba8be07` bounded all 17
  repository manifests. The generator template (`pyproject.toml.j2:30`) still emits the unbounded
  requirement into R2 projects.
- 2026-09-23 — `billing-stripe-objects-normalized-empty`: new, open (S1).
- 2026-09-23 — `billing-stripe-api-version-drift`: new, open (S2).
- 2026-09-23 — `billing-stripe-api-version-drift`: upgraded S2 → S1. The team decided to target
  the latest Stripe API version (`2026-06-24.dahlia`), which makes the dahlia webhook endpoint the
  supported configuration and removes the endpoint-version precondition that discounted it. The
  fix is re-scoped to latest-version-only with a webhook version guard.
- 2026-09-23 — `billing-stripe-api-version-drift`: fix decisions accepted by the team. A webhook
  whose `api_version` is a different named release is rejected with `BillingConfigurationError`
  (500, so Stripe retries). Matching is by named release (`dahlia`), not by exact date.
