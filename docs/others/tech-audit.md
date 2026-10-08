# QuickScale — Deep Technical Audit (defect sweep)

Audited: 2fd8637f (v89) · 2026-10-08 · working tree dirty (uncommitted `docs/others/arch-audit.md`; only its §13–14 hand-off sections were read, as leads, not as code) · repository public (github.com/Experto-AI/quickscale; no `SECURITY.md`) · prompt: deep-technical-audit v6

> **Mode:** an independent full sweep, at the invoker's request ("start from scratch, a full
> review, not a continuation"). The prior deliverable (audited `e2623cb8`, 2026-10-05) was read
> only **after** the sweep, to reconcile its IDs, verify its claimed closures, and carry its
> watchlist. It held no open finding. Every prior ID has a line in §15.
>
> **Disclosure:** the repository is public. One unfixed S2 security finding
> (`analytics-distinct-id-is-session-key`) keeps its failure scenario, evidence, refutation, and
> chain in a private companion outside the repository.

---

## 1. Orientation summary

**What the system is.** A Python 3.14 / Django 6.0 **project generator** (`quickscale_core`), its
**CLI** (`quickscale_cli`), and **12 embeddable Django modules** (auth, orgs, billing, blog,
listings, crm, forms, storage, backups, notifications, analytics, social), shipped from one
Poetry monorepo. Modules are embedded into generated projects by git subtree. The generated
project includes a React/Vite/TypeScript theme. About 85k lines of first-party production Python,
plus Jinja templates for the generated project.

**Deployment realities.**
- **R1 — generator/CLI** on developer machines: `plan`/`apply`, `deploy railway`, module
  embed/update/push (git), and DR operator commands.
- **R2 — the generated Django SaaS**, internet-facing on Railway: Docker image, `start.sh`,
  gunicorn, PostgreSQL 18 with FORCE RLS under a restricted runtime role, in solo or saas
  organization mode. Its defaults and its generated CI workflow are production reality, because
  users copy them.
- **R3 — the release pipeline**: tag-triggered GitHub Actions publishing to PyPI through OIDC
  trusted publishing.

**Entry points.**
- The generated URLconf: health check, Django admin, SPA catch-all.
- Module routes:
  - auth: allauth, profile, account delete.
  - orgs: HTML views and JSON API, invitation accept, VIEW-AS.
  - billing: JSON API and the Stripe webhook.
  - blog and listings: automation APIs and public reads.
  - crm: DRF viewsets.
  - forms: public schema and submit, plus an admin API.
  - notifications: the Resend webhook.
  - analytics: an overview page.
  - social: payload endpoints.
- Management commands: org purge; backups create/restore/prune; forms anonymize/seed.
- The CLI commands and the release workflows.

**Actors.**
- Anonymous visitors.
- Self-registered users (registration defaults on).
- Members, admins, and owners of other tenants.
- Staff and superusers (Django admin, VIEW-AS, `operator_access`).
- Stripe and Resend as signed webhook callers.
- Third-party processors: Stripe, Resend, PostHog.
- Maintainers with tag-push rights.

**Crown jewels.**
- Cross-tenant data (RLS).
- Session credentials and accounts.
- Money movement (Stripe checkout, the credit ledger).
- The database and its backups (restore).
- The release pipeline, and the generated artifacts every user copies.

**Configuration axes.**
- `QUICKSCALE_ORGS_MODE` (solo/saas).
- Module installed and enabled flags.
- Auth `email_verification` (default `none`) and `registration_enabled` (default on).
- Analytics `enabled`, `anonymous_by_default` (default on), and `exclude_staff` (default off).
- Notifications enabled; Resend live.
- `REDIS_URL` set or unset (unset falls back to `DatabaseCache`).
- `USE_X_FORWARDED_FOR` / `TRUSTED_PROXY_COUNT`.
- `QUICKSCALE_PRIVILEGED_COMMAND`, `QUICKSCALE_NON_DB_COMMAND`, and `QUICKSCALE_ALLOW_BYPASSRLS`.
- Storage backend (local/s3/r2).
- `GUNICORN_WORKERS` (default 1).

**Tooling baseline.** All of these run in CI and fail the build:
- ruff and mypy.
- pytest: unit tests, plus integration tests on a PostgreSQL NOBYPASSRLS role.
- Bandit 1.9.4 and Trivy v0.74.0 (including a rendered-Dockerfile misconfiguration scan).
- gitleaks.
- A zizmor-backed workflow-security gate over the repository's own four workflows.
- The custom convention, parity, CSRF, and contract-vintage gates.

**Scope.** The whole repository:
- **Read in depth:** R2 module entry points, generated templates, and billing.
- **Sampled:** R1 CLI and the DR engine.
- **Read lightly:** devtools (beta migration) and the `scripts/` CI gates.

**Oracle list** (declared rules hunted during the sweep; from `decisions.md`):
1. Fail-hard: no silent fallback in generator, CLI, manifest, or startup paths.
2. The RLS boot guard, and runtime serving that fails closed without `RUNTIME_DATABASE_URL`.
3. Rule 9: every JSON endpoint is a DRF view on one of two bases, with no `JsonResponse` APIs and
   no module-built error bodies.
4. Rule 26: a webhook verifies its signature before parsing, a replay is a no-op, and no error
   body is built from `str(exc)`.
5. Rule 19: tenant data is authorized by org role.
6. Rules 20/21: email goes only through `send_notification`, and write effects run on commit.
7. Rule 35: secrets arrive through settings, with startup checks.
8. Billing: `WebhookEvent` is the idempotency gate, and Stripe secrets never reach the database.
9. Notifications: provider tags use a non-sensitive allowlist.
10. Self-service account removal "receives no cross-tenant write scope" (§Multi-tenant SaaS,
    "Operator access").
11. Security gates never skip silently.
12. Repository workflow policy (SA202): third-party actions are SHA-pinned under a top-level
    `permissions:` block.

**Data sensitivity.**
- **Classes:**
  - Credentials: Django session IDs; Stripe, Resend, and PostHog keys; database URLs.
  - Personal data: emails, names, form submissions, IPs, user agents.
  - Payment metadata: Stripe customer and subscription IDs, the credit ledger.
  - Tenant content: CRM, forms, blog drafts.
- **Where it travels:** PostgreSQL, the cache, JSON logs, Stripe, Resend, PostHog, and backups
  (local, S3, R2).
- **Obligations:** erasure, through the account-anonymization feature. Stripe-hosted checkout
  keeps card data out of scope.

**Measurements (§3.4).**
- **Window and filter:** 12 months, 3,259 non-merge commits. That count includes git-subtree
  synthetic copies, which were excluded by keeping only `quickscale_(core|cli|modules|devtools)/…/src`
  paths. Commits touching more than 30 files, tests, and docs were also excluded.
- **Fix density (fix commits / all):**

  | File | Fix / all |
  |---|---|
  | `runtime/conventions.py` | 5/6 |
  | `contracts/module_discovery.py` | 6/9 |
  | `utils/theme_validation.py` | 4/6 |
  | generated `local.py.j2` | 4/9 |
  | CLI `railway_utils.py` | 7/17 |
  | auth `views.py` | 6/16 |
  | `module_wiring_manager.py` | 7/19 |
  | `manifest/entry_point.py` | 10/30 |
  | `Dockerfile.j2` | 8/27 |
  | `docker-compose.yml.j2` | 6/19 |

- **Churn:**

  | File | Commits |
  |---|---|
  | `apply_command.py` | 70 |
  | `module_config.py` | 41 |
  | `module_commands.py` | 38 |
  | backups `services.py` | 38 |
  | billing `services.py` | 37 |
  | `generator.py` | 35 |
  | orgs `tenancy.py` | 31 |

Each hotspot was read or sampled (§3).

### Coverage and residual-risk statement

**Read in full:**
- **orgs:** tenant middleware, the GUC priming wrapper, `current_org` scopes and
  `operator_access`, managers, public context, permissions, VIEW-AS, all HTML and JSON views,
  invitation accept, redirect hooks, anonymization, and the invite and create forms.
- **billing:** views, webhook dispatch, credit ledger, one-time checkout, the Stripe client
  wrapper, removal reconciliation, exceptions, and `handle_stripe_event`.
- **blog:** views, upload validation, and `upload_to`.
- **forms:** views, the submission serializer, the notification helper, and throttles.
- **notifications:** webhook view, verification, parse/resolve/record, and anonymization.
- **analytics:** services, views, and template tags.
- **auth:** account-delete view, allauth adapter, and wiring adapter.
- **Other modules:** the listings publish path and the social payload views and cache keys.
- **Generated templates:** URLs, views, settings (base/production/local), `start.sh`,
  `Dockerfile`, `railway.json`, `docker-compose`, `.dockerignore`, the CI workflow,
  `package.json`, `index.html`, `csrf.ts`, and `analytics.ts`.
- **Core runtime and deploy:** `runtime/settings.py`, `runtime/conventions.py`,
  `runtime_database.py`, and the deploy flow.
- **Pipeline:** `publish.yml`, plus the `ci.yml` and nightly workflow headers.

**Sampled:**
- crm serializers and views; backups admin, restore, and dispatch.
- DR engine primitives and media sync.
- CLI remove, push, and dependency-write paths.
- Config and identifier validation, the git runner, and the publish scripts.
- Social models and contracts, and the storage manifest.

**Skipped:**
- devtools beta-migration internals.
- `scripts/` gate implementations (except publish).
- Manifest loader and resolver internals; DR recovery and verification internals.
- Most CLI `plan`/`apply` internals.
- Theme React components other than seam, analytics, CSRF, and social.

**Tools:** git; the repository's Django 6.0 virtualenv (read-only use); a web search of two vendor
contracts. Bandit, Trivy, and gitleaks were **not** re-run, because CI already fails on their
findings.

**Empirical checks (§1e):**
1. **Generated CI fails on a fresh checkout — confirmed.** I generated a zero-module project with
   the repository's own generator into scratch space (`QS_SKIP_POETRY_LOCK=1`, no network), then
   committed and cloned it to reproduce a CI checkout:
   - `settings.local` raises `ValueError: DATABASE_URL … is required`.
   - `settings.base` fails with `Unable to configure handler 'file'`.
2. **The image health check always fails — confirmed.** I loaded the same project under
   `settings.production` and used Django's test client. With `Host: localhost:8000`, both `GET /`
   and `GET /healthcheck/` return 400.
3. **History credential scan: clean.** The patterns searched were `sk_live_`, AWS access keys,
   GitHub tokens, Slack tokens, private keys, PyPI, Resend, and PostHog tokens. Every hit is a
   placeholder or a fixture.
4. **Vendor contracts:**
   - Resend webhooks are Svix-signed: `svix-id`, `svix-timestamp`, and `svix-signature` headers,
     with a base64 `whsec_` secret. Their fields sit under `data.*`.
   - Stripe rejects non-absolute success and cancel URLs.

**Category activation:**
- **Active:** I, II, III, IV (sampled), V (sampled), VI, VII, VIII, IX; X: generator, multi-tenant,
  service/webhooks, frontend, CLI, library (modules), IaC (Dockerfile/Railway).
- **Inert:** X mobile, firmware, GraphQL/RPC, ML/LLM (no model runtime), data pipeline (DR is
  operator batch, so it was sampled under IV/VI instead).
- **Produced:** I, III, VI, VII, VIII, IX, X-generator.

**Sibling sweep:** each of the 12 modules was checked for these signatures:
- unauthenticated views
- `str(exc)` response bodies
- `all_objects` in request paths
- missing throttles on email-sending or provider-calling endpoints
- session data leaving the process
- relative URLs handed to providers
- address-based selectors

**Residual risk.**
- No PostgreSQL instance was used, so RLS and lock semantics were reasoned from code.
- No live Stripe, Resend, or PostHog calls were made. `billing-checkout-relative-redirect-urls`
  and `notifications-webhook-rejects-resend` rest on published vendor contracts (see §13).
- Out-of-repo controls were not visible: Railway edge, PostHog project ACLs, Stripe
  payment-method settings, and GitHub org token defaults.
- devtools and the gate scripts were not swept for defects.

Silence on the skipped areas does not mean they are clean.

---

## 2. Machine-readable finding index

```yaml
schema: tech-audit/v6
audited: 2fd8637f2d163c65a873ce74337e4f5d88b9ba99
items:
  - {id: billing-checkout-relative-redirect-urls, status: open, severity: S2, category: I,
     title: "Checkout and portal sessions are created with relative return URLs that Stripe rejects",
     effort: Trivial, confidence: High, reality: generated-app,
     anchors: [quickscale_modules/billing/src/quickscale_modules_billing/views.py],
     depends_on: [], chain: [],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: analytics-distinct-id-is-session-key, status: open, severity: S2, category: III,
     title: "Server-side analytics distinct ID is derived from a live credential",
     effort: Small, confidence: High, reality: generated-app,
     anchors: [quickscale_modules/analytics/src/quickscale_modules_analytics/services.py],
     fix_files: [quickscale_modules/analytics/src/quickscale_modules_analytics/services.py,
                 quickscale_modules/analytics/tests/test_services.py],
     depends_on: [], chain: [], first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: generated-ci-fails-out-of-box, status: open, severity: S3, category: X,
     title: "Generated CI workflow cannot pass on a fresh project", effort: Small, confidence: High,
     reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/generator/templates/github/workflows/ci.yml.j2],
     fix_files: [quickscale_core/src/quickscale_core/generator/templates/github/workflows/ci.yml.j2,
                 quickscale_core/src/quickscale_core/generator/templates/project_name/settings/base.py.j2],
     depends_on: [], chain: [], first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: notifications-webhook-rejects-resend, status: open, severity: S3, category: IX,
     title: "Notifications webhook accepts only a custom signing contract Resend never sends",
     effort: Medium, confidence: High, reality: generated-app,
     anchors: [quickscale_modules/notifications/src/quickscale_modules_notifications/views.py,
               quickscale_modules/notifications/src/quickscale_modules_notifications/_webhooks.py],
     depends_on: [], chain: [], first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: anonymize-matches-unverified-address, status: open, severity: S3, category: III,
     title: "Self-service account removal rewrites other tenants' rows selected by an unverified address",
     effort: Small, confidence: High, reality: generated-app,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/_anonymization.py,
               quickscale_modules/notifications/src/quickscale_modules_notifications/_anonymization.py,
               quickscale_modules/billing/src/quickscale_modules_billing/_anonymization.py],
     depends_on: [], chain: [], first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: org-invitation-email-unthrottled, status: open, severity: S3, category: III,
     title: "Any self-registered saas user can send unlimited invitation emails with chosen text",
     effort: Small, confidence: High, reality: generated-app,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/views.py,
               quickscale_modules/orgs/src/quickscale_modules_orgs/forms.py],
     depends_on: [], chain: [], first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: deploy-settings-module-from-service-name, status: open, severity: S3, category: VI,
     title: "deploy railway overwrites DJANGO_SETTINGS_MODULE with one derived from the service name",
     effort: Trivial, confidence: High, reality: cli,
     anchors: [quickscale_cli/src/quickscale_cli/commands/_deploy_service_config.py],
     depends_on: [], chain: [], first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: billing-async-payment-never-credited, status: open, severity: S3, category: I,
     title: "One-time purchases paid by a delayed payment method are never credited",
     effort: Small, confidence: Medium, reality: generated-app,
     anchors: [quickscale_modules/billing/src/quickscale_modules_billing/_webhooks.py],
     depends_on: [], chain: [],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: generated-ci-mutable-action-tags, status: open, severity: S3, category: VII,
     title: "Generated CI uses mutable third-party action tags and no permissions block",
     effort: Small, confidence: High, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/generator/templates/github/workflows/ci.yml.j2],
     fix_files: [quickscale_core/src/quickscale_core/generator/templates/github/workflows/ci.yml.j2,
                 scripts/check_workflow_security.py],
     depends_on: [], chain: [], first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: docker-healthcheck-always-unhealthy, status: open, severity: S4, category: VI, effort: Trivial,
     confidence: High, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/generator/templates/Dockerfile.j2],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: frontend-image-floating-deps, status: open, severity: S4, category: VII, effort: Small,
     confidence: High, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/generator/templates/Dockerfile.j2],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: viewas-overrides-management-org, status: open, severity: S4, category: I, effort: Small,
     confidence: High, reality: generated-app,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/middleware.py,
               quickscale_modules/orgs/src/quickscale_modules_orgs/_view_context.py],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: social-payload-echoes-exception-text, status: open, severity: S4, category: VI,
     effort: Trivial, confidence: High, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/manifest/social_manifest.py],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: forms-notification-status-misreported, status: open, severity: S4, category: VI,
     effort: Trivial, confidence: High, reality: generated-app,
     anchors: [quickscale_modules/forms/src/quickscale_modules_forms/_email.py],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: analytics-dashboard-unauthenticated, status: open, severity: S4, category: III,
     effort: Trivial, confidence: High, reality: generated-app,
     anchors: [quickscale_modules/analytics/src/quickscale_modules_analytics/views.py],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: deploy-runtime-url-unquoted-password, status: open, severity: S4, category: IX,
     effort: Trivial, confidence: High, reality: cli,
     anchors: [quickscale_cli/src/quickscale_cli/commands/_deploy_service_config.py],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: dr-media-sync-whole-object-read, status: open, severity: S4, category: IV,
     effort: Trivial, confidence: High, reality: cli,
     anchors: [quickscale_core/src/quickscale_core/dr_engine/_media.py],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: dr-restore-vintage-exact-match, status: watchlist, category: I, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/dr_engine/recovery.py],
     first_seen: 2026-09-24, last_verified: 2026-10-08}
  - {id: orgs-provider-id-check-blocks-migrate, status: watchlist, category: VI, reality: generated-app,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/checks.py],
     first_seen: 2026-09-24, last_verified: 2026-10-08}
  - {id: crm-stage-seed-lost-on-commit-failure, status: watchlist, category: II, reality: generated-app,
     anchors: [quickscale_modules/crm/src/quickscale_modules_crm/receivers.py],
     first_seen: 2026-10-03, last_verified: 2026-10-08}
  - {id: backups-upload-restore-by-model-permission, status: watchlist, category: III,
     reality: generated-app,
     anchors: [quickscale_modules/backups/src/quickscale_modules_backups/_admin_restore.py],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: single-sync-worker-vendor-calls, status: watchlist, category: IV, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/generator/templates/start.sh.j2,
               quickscale_modules/billing/src/quickscale_modules_billing/_stripe_client.py],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: allow-bypassrls-serving-undetected, status: watchlist, category: VI, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/runtime/settings.py],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: migrate-runs-per-replica, status: watchlist, category: II, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/generator/templates/start.sh.j2],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
```

---

## 3. Summary table

**Counts:** S1 — 0 · S2 — 2 · S3 — 7 · S4 — 8 · total 17 open. Watchlist: 7.

| ID | Sev | Cat | Title | Effort | Conf | Since |
|---|---|---|---|---|---|---|
| `billing-checkout-relative-redirect-urls` | S2 | I | Checkout/portal sessions get relative return URLs that Stripe rejects | Trivial | High | new — **quick win** |
| `analytics-distinct-id-is-session-key` | S2 | III | Server-side analytics distinct ID is derived from a live credential | Small | High | new |
| `generated-ci-fails-out-of-box` | S3 | X | Generated CI workflow cannot pass on a fresh project | Small | High | new |
| `notifications-webhook-rejects-resend` | S3 | IX | Webhook accepts only a signing contract Resend never sends | Medium | High | new |
| `anonymize-matches-unverified-address` | S3 | III | Self-service removal rewrites other tenants' rows by unverified address | Small | High | new |
| `org-invitation-email-unthrottled` | S3 | III | Unlimited invitation emails with attacker-chosen text | Small | High | new |
| `deploy-settings-module-from-service-name` | S3 | VI | Deploy overwrites `DJANGO_SETTINGS_MODULE` from the service name | Trivial | High | new — **quick win** |
| `billing-async-payment-never-credited` | S3 | I | Delayed-payment purchases are never credited | Small | Medium | new |
| `generated-ci-mutable-action-tags` | S3 | VII | Generated CI on mutable action tags, no `permissions:` | Small | High | new |
| `docker-healthcheck-always-unhealthy` | S4 | VI | Image `HEALTHCHECK` gets 400 under production settings | Trivial | High | new |
| `frontend-image-floating-deps` | S4 | VII | Production image resolves npm deps unpinned when no lockfile | Small | High | new |
| `viewas-overrides-management-org` | S4 | I | VIEW-AS org replaces the URL's org on management pages | Small | High | new |
| `social-payload-echoes-exception-text` | S4 | VI | Public social payload returns `str(exc)` | Trivial | High | new |
| `forms-notification-status-misreported` | S4 | VI | Submission reports `queued` when notifications are disabled | Trivial | High | new |
| `analytics-dashboard-unauthenticated` | S4 | III | Analytics overview page has no auth guard | Trivial | High | new |
| `deploy-runtime-url-unquoted-password` | S4 | IX | Reused runtime password embedded unquoted in a URL | Trivial | High | new |
| `dr-media-sync-whole-object-read` | S4 | IV | Media sync reads whole objects into memory | Trivial | High | new |

---

## 4. Findings

### Finding 1: Checkout and portal sessions are created with relative return URLs that Stripe rejects

- **ID:** `billing-checkout-relative-redirect-urls`
- **Severity:** S2.
  - **Rubric cell:** High impact × Direct reach. Every authorized checkout or portal request is a
    main billing path, so the table gives S1.
  - **Deviation:** one step down to S2. The failure is loud: a 500 at the first attempt, before
    any money moves, with nothing corrupted.
  - **Reality:** R2.
  - **Flipping assumption:** that Stripe refuses a path-only `success_url`, `cancel_url`, or
    `return_url`. This is Stripe's documented contract (Q1 in §13 settles it in one test-mode
    call).
- **Category:** I (correctness). It is a regression.
- **Confidence:** High. The code path was read end to end, the serializers forbid a client-supplied
  URL, and a test pins the relative value.
- **Location:** `quickscale_modules/billing/src/quickscale_modules_billing/views.py:245-246`
  (`CreateCheckoutSessionView.post`), `:273-274` (`CreateSubscriptionCheckoutView.post`), and
  `:325` (`CreateBillingPortalSessionView.post`).
- **Defect:** The three views pass `reverse("quickscale_billing:…")` (for example
  `/billing/purchase/success/`) straight through `create_checkout_session` /
  `create_subscription_checkout_session` / `create_billing_portal_session` to the Stripe SDK. No
  layer makes them absolute.
- **Failure scenario:**
  1. An org owner sends `POST /billing/api/purchase/checkout/` with `{"plan_slug": "<one-time plan>"}`.
  2. The service gets or creates the Stripe customer and persists a `PREPARING` reservation.
  3. It calls `stripe.checkout.Session.create(success_url="/billing/purchase/success/", …)`.
  4. Stripe answers `400 url_invalid`.
  5. `create_checkout_session` maps the SDK error to `BillingError` → HTTP 500 "Stripe checkout
     session creation failed."

  The subscription checkout and the portal fail the same way. No billing purchase,
  subscription, or portal session can be created.
  - **Chain:** at audit time each failed attempt left a `PREPARING` row with an unknown provider
    outcome, turning every purchase attempt into a permanent account-deletion and purge blocker;
    that reservation now resolves by provider lookup (SA251, slice b).
- **Evidence:**
  - `views.py:245` — `success_url=reverse("quickscale_billing:purchase_success"),`.
  - `_checkout.py:98-101` only strips the value.
  - `_stripe_client.py:115-116` forwards it (and `:147` for subscriptions).
  - `test_views.py:1123-1124` asserts `captured_call["success_url"] == "/billing/purchase/success/"`.
  - The service-level tests (`test_purchase.py:259` and others) all pass absolute URLs, so no test
    exercises the view-to-SDK contract.
- **Refutation:**
  - *Counter-argument:* a client could supply absolute URLs. It fails: the serializers reject
    `success_url` ("This field is not allowed", `test_views.py:816-830`).
  - *Counter-argument:* some layer absolutizes the value. It fails: searched the views, services,
    client wrapper, and middleware, and found none.
  - *Blessing check:* the T1.10 commit message does not mention the change. The pinning test
    encodes the wrong assumption rather than a decision.
- **Fix:** Build each URL with `request.build_absolute_uri(reverse(...))`, as the code did before
  `c7320b02`. Add a service-boundary guard that refuses a URL without scheme and host. Update
  `test_views.py:1123-1124` and its siblings to expect absolute URLs.
  - **Effort:** Trivial.
- **Fix files:** `views.py`, `_checkout.py`, `_subscription_checkout.py`, `tests/test_views.py`.
  **Depends on:** none.
- **Verification:**
  - A view test asserting `urlsplit(captured["success_url"]).scheme in {"http","https"}` for all
    three endpoints.
  - One manual Stripe test-mode checkout from the API view.
- **Fix risk:** Under a proxy, `build_absolute_uri` takes the scheme from `SECURE_PROXY_SSL_HEADER`.
  That is already gated on `USE_X_FORWARDED_FOR` (SA200), so production builds `https` URLs.
- **Detection signal:** `BillingError` "Stripe checkout session creation failed." on every
  checkout. Stripe dashboard request logs show `url_invalid`. Rising `PurchaseCheckout` rows in
  `preparing`.
- **Deliberate?** None found.
  - **Age:** regression from `c7320b02` (T1.10, 2026-06-24), which deleted the
    `request.build_absolute_uri(...)` helpers.
  - **Releases affected:** shipped in tags `0.87.0`, `0.88.0`, and `0.89.0`.
  - The architectural audit's red flag (§14 below) expects publishing 0.89.0 to repair checkout.
    This defect is still present at that tag.

### Finding 2: Server-side analytics distinct ID is derived from a live credential

- **ID:** `analytics-distinct-id-is-session-key`
- **Severity:** S2.
  - **Rubric cell:** Critical impact (an account and session credential leaves the trust
    boundary, including staff sessions) × Common reach.
  - **Preconditions:** one unverified (analytics enabled), so reach moves to Rare → S2.
  - **Reality:** R2 with the module defaults.
  - **Flipping assumption:** who can read the PostHog project (Q3).
- **Category:** III (secrets sent to a third party).
- **Confidence:** High. Read end to end; tests pin the format.
- **Location:** `quickscale_modules/analytics/src/quickscale_modules_analytics/services.py:191-224`
  (`get_distinct_id`); caller `quickscale_modules/forms/src/quickscale_modules_forms/views.py:111-145`;
  defaults `quickscale_modules/analytics/module.yml:53-65`.
- **Defect:** The analytics distinct ID sent to PostHog is built directly from a value that
  authenticates the user. Under the shipped defaults this includes signed-in and staff users.
- **Failure scenario / Evidence / Refutation / Chain:** held in the private companion.
- **Fix:**
  - Never derive the distinct ID from the session key. Use a random pseudonymous ID stored in the
    session (`session.setdefault("quickscale_analytics_id", uuid4().hex)`), or a keyed HMAC of the
    session key with a dedicated secret.
  - Re-pin the tests (`tests/test_services.py:439`, `:468`, `:487`) to the new form.
  - Default `exclude_staff` to `true`.
  - **Effort:** Small.
- **Fix files:** `services.py`, `module.yml` (default), `tests/test_services.py`.
  **Depends on:** none.
- **Verification:** A test asserting the distinct ID contains no substring of
  `request.session.session_key`, for anonymous, authenticated, and staff requests.
- **Fix risk:** PostHog person continuity breaks once; that is acceptable. Run the post-fix
  session invalidation described in the companion for deployments that had analytics enabled.
- **Detection signal:** PostHog persons whose distinct ID starts with `session:`.
- **Deliberate?** The README calls these IDs "session-based anonymous". That justification fails,
  because the value is a credential, not an anonymous token.
  - **Age:** since the module was introduced (`4a56ccf4`, 2026-04-04).

### S3 findings (compact)

- **`generated-ci-fails-out-of-box`** · S3 (Moderate × Common) · R2 ·
  `generator/templates/github/workflows/ci.yml.j2:104-125`, `project_name/settings/local.py.j2:137`,
  `project_name/settings/base.py.j2:341-343`, `.gitignore.j2:60`.
  - **Defect:**
    - The generated "Run tests with coverage" step sets no `DATABASE_URL`. pytest uses
      `settings.local`, which raises at import when `DATABASE_URL` is unset, and `.env` is
      gitignored.
    - The "Run migrations" and "tenant isolation" steps use `settings.base`. Its `LOGGING` opens
      `logs/django.log`, a directory the generator never creates and `.gitignore` excludes. It
      also ignores `DATABASE_URL` and reads `POSTGRES_*`, defaulting the database name to the
      package.
    - Every freshly generated project's CI is therefore red, and the promised CI gate never runs.
    - **Reproduced** (empirical check 1).
  - **Fix:** In the test and migrate steps:
    - Set `DATABASE_URL` (plus `QUICKSCALE_ALLOW_BYPASSRLS: "1"` for the superuser test role,
      or provision the runtime role).
    - Point the migrate and isolation steps at `settings.local`.
    - Drop the file handler from `base.py.j2`, or create the directory.
    - Add a gate that executes the rendered workflow's commands against a generated project.
  - **Effort:** Small. **Confidence:** High.

- **`notifications-webhook-rejects-resend`** · S3 (Moderate × Common) · R2 ·
  `notifications/views.py:30-40`, `_webhooks.py:68-85`, `:112-135`, `services.py:236-270`,
  `README.md:100-102`.
  - **Defect:** The endpoint requires `X-QuickScale-Notifications-Signature`/`-Timestamp`, a hex
    HMAC over `"{ts}.{body}"` with the raw secret, and top-level `email_id`/`recipient` keys.
    Resend (via Svix) sends:
    - `svix-id`/`svix-timestamp`/`svix-signature` with a base64 HMAC over `"{id}.{ts}.{body}"`;
    - a base64 `whsec_…` secret;
    - `data.email_id` and a `data.to` array.

    The README tells operators to point Resend directly at this endpoint. Every real delivery
    event is refused with 400 `webhook_signature_invalid`. Delivered, bounced, and complained
    statuses never update, and Resend eventually disables the endpoint. The module's tests sign
    with the module's own helper, so they cannot catch it.
  - **Fix:** Verify Svix headers per Resend's spec (decode the `whsec_` secret, accept any of the
    space-separated `v1,` signatures, compare in constant time, keep the TTL window). Map `type`,
    `data.email_id`, and `data.to[0]`, with `svix-id` as the provider event ID. Add a contract test
    built from Resend's documented payload. Alternatively, document the relay that re-signs.
  - **Effort:** Medium. **Confidence:** High (vendor contract confirmed, §1).
  - **Age:** since `1a143fce` (v0.78.0).

- **`anonymize-matches-unverified-address`** · S3 (Moderate × Common) · R2 with default auth
  options · `orgs/_anonymization.py:46-55`, `notifications/_anonymization.py:78-84`, `:153-160`,
  `billing/_anonymization.py:43-56`; `auth/module.yml:27-33` (`email_verification` default
  `"none"`).
  - **Defect:** Account removal selects rows across all tenants by the account's email address,
    and that address was never proven owned:
    - pending and past `OrganizationInvitation` rows, which are expired and re-addressed;
    - `NotificationDelivery` and linked `NotificationMessage` rows, which are rewritten or
      wholesale-redacted;
    - billing `WebhookEvent` payloads, where the email and the account's chosen name are redacted.
  - **Failure scenario:**
    1. Anyone registers an unregistered address X (an invitee's address, or a form-notification
       inbox such as `sales@…`).
    2. They immediately delete the account.
    3. Every pending invitation to X in every organization is withdrawn. Every notification
       delivery to X, in every tenant, loses its recipient and content. Matching Stripe event
       payloads are rewritten.
  - **Oracle:** this violates oracle 10 (self-service removal gets no cross-tenant write scope).
  - **Secondary angle:** the same unverified identity enables classic account pre-hijacking.
  - **Fix:**
    - Run address-based selectors only for addresses the account verified (allauth
      `EmailAddress.verified`). Otherwise scope them to rows linked by user ID.
    - Alternatively, require verified email before removal runs those selectors.
  - **Effort:** Small. **Confidence:** High.

- **`org-invitation-email-unthrottled`** · S3 (Moderate × Common, saas mode) · R2 ·
  `orgs/views.py:236-283` (`InviteView`, a plain Django `FormView`, no throttle) and `:340`
  (`OrgApiInviteView`, default `user` rate only); `forms.py:155-260`.
  - **Defect:** Any self-registered user can repeatedly:
    - create an organization (no cap, name up to 255 characters, rendered in the email);
    - set their own display name (also rendered in the email);
    - invite arbitrary addresses, then revoke and re-invite.

    Each invite sends an email from the site's verified sending domain. The result is a phishing
    and spam relay, plus the risk that the email provider suspends the account that also carries
    password resets.
  - **Fix:** Add a scoped DRF throttle on both invite paths (`quickscale_orgs_invite`). Cap
    pending invitations per org, and invitations per sender per day.
  - **Effort:** Small. **Confidence:** High.

- **`deploy-settings-module-from-service-name`** · S3 (High × Rare: a non-default name) · R1→R2 ·
  `quickscale_cli/commands/_deploy_service_config.py:86-94`; `deployment_commands.py:114-116`.
  - **Defect:** Every `quickscale deploy railway` sets
    `DJANGO_SETTINGS_MODULE = <service name with '-'→'_'>.settings.production`. The service name is
    `--project-name` or the current directory's name. When the project's package differs
    (`quickscale plan <slug> --package <pkg>`, a renamed or cloned directory, or any
    `--project-name`), the deployed container cannot import its settings and fails to boot.
  - **Persistence:** a manual correction is overwritten on the next deploy.
  - **Fix:** Use `state.project.package` (the state is already loaded at
    `deployment_commands.py:100`), or stop setting the variable and rely on the image's `ENV`.
  - **Effort:** Trivial. **Confidence:** High.

- **`billing-async-payment-never-credited`** · S3 (High × Rare: needs a delayed-notification
  payment method enabled on the Stripe account) · R2 · `billing/_webhooks.py:183-198`, `:129-160`;
  `_stripe_client.py:107-118` (no `payment_method_types`); `OPERATIONS.md.j2:118-120`.
  - **Defect:** For SEPA, ACH, Bacs, or bank-transfer payments, `checkout.session.completed`
    arrives with `payment_status="unpaid"`. The handler raises "payment is not settled" and the
    event stays unprocessed, so Stripe retries for three days. The later
    `checkout.session.async_payment_succeeded` event is not dispatched (`"ignored"`, marked
    processed), and the documented webhook event list omits it. The customer is charged and never
    credited.
  - **Chain:** the reservation stays `OPEN`, and removal reconciliation then refuses "completed and
    may require credit synchronization" forever.
  - **Fix:** On completed+unpaid, bind the reservation and return 200. Credit on
    `async_payment_succeeded`, expire on `async_payment_failed`. Add both events to the
    documented list. Alternatively, restrict Checkout to immediate methods with
    `payment_method_types=["card"]`.
  - **Effort:** Small. **Confidence:** Medium (depends on the account's payment methods, Q4).

- **`generated-ci-mutable-action-tags`** · S3 (Critical × Unlikely: needs an upstream action
  compromise) · R2 · `ci.yml.j2:42,45,76,83,108,134,137,142,151`.
  - **Defect:** The generated workflow uses `actions/checkout@v6`, `snok/install-poetry@v1`,
    `pnpm/action-setup@v5`, `codecov/codecov-action@v5`, and others on mutable tags. It has no
    top-level `permissions:` block, so it inherits the repository default, which can be
    read-write on older organizations.
  - **Variant analysis:** an unfixed sibling of the resolved `pipeline-mutable-action-refs`
    (SA202). That fix pinned and gated only the repository's own four workflows, against
    oracle 12.
  - **Fix:** Pin by SHA with version comments, add `permissions: contents: read`, and extend
    `check_workflow_security.py` / `make refresh-action-pins` to the rendered template.
  - **Effort:** Small. **Confidence:** High.

### S4 findings (one line each)

- `docker-healthcheck-always-unhealthy` · `Dockerfile.j2:204-205` · The image `HEALTHCHECK` fetches
  `http://localhost:$PORT/`. Under production settings that answers 400 (`localhost` is not in
  `ALLOWED_HOSTS`), and `urlopen` raises on any non-2xx, so the container is always "unhealthy"
  (reproduced). The comment's claim that "404/500 means alive" is false. · Probe `/healthcheck/`
  with an allowed `Host` header and treat any HTTP response as alive.
- `frontend-image-floating-deps` · `Dockerfile.j2:26` · `pnpm install --no-frozen-lockfile` over
  caret ranges (`package.json.j2`). No lockfile is generated by `apply`, so a project deployed
  before `quickscale up` creates one builds with whatever npm resolves that day. · Commit a
  generated `pnpm-lock.yaml` and use `--frozen-lockfile` in the image.
- `viewas-overrides-management-org` · `middleware.py:155-157`, `_view_context.py:52-55` · During
  VIEW-AS the middleware sets `request.org` on management paths too, so
  `OrganizationContextMixin.get_organization()` returns the impersonated org instead of the URL's
  `org_slug`. A superuser editing `/orgs/<B>/settings/` changes org A. · Prefer the slug when the
  route carries one.
- `social-payload-echoes-exception-text` · `manifest/social_manifest.py:396-400`, `:446-456`,
  `:470-480` · The generated public social payload views return `str(exc)` (database errors carry
  host, role, and table names) to anonymous callers. This violates rules 9 and 26. · Return a
  fixed message and log the exception.
- `forms-notification-status-misreported` · `forms/_email.py:44-53` · When notifications are
  disabled, the submit response reports `"queued"` while logging "skipped". · Return a distinct
  `"disabled"` status.
- `analytics-dashboard-unauthenticated` · `analytics/views.py:15` · The module page at
  `/analytics/` shows enabled state and the PostHog host to anonymous visitors. The rule-19 module
  back-office pages all require a role. · Add `LoginRequiredMixin` plus `OrgRoleMixin`, or
  staff-only.
- `deploy-runtime-url-unquoted-password` · `_deploy_service_config.py:22-33`, `:62-68` · A reused,
  operator-set `RUNTIME_DB_PASSWORD` containing `@ : / #` is embedded raw into
  `RUNTIME_DATABASE_URL`, which breaks the URL. Generated passwords are hex and safe. · Quote with
  `urllib.parse.quote(password, safe="")`.
- `dr-media-sync-whole-object-read` · `dr_engine/_media.py:139-141` · An s3→local media copy reads
  each object fully into memory, so large videos exhaust the operator process. · Stream with
  `shutil.copyfileobj` or `download_fileobj`.

---

## 5. Safeguard matrix

The populations are module entry points and webhooks, generated launch artifacts, and outbound
clients. A cell names the layer that supplies the safeguard, or a finding ID.

| Entry point | AuthN | AuthZ | Input validation | Output encoding | Rate limit | Timeout | Idempotency | Error shape | Audit |
|---|---|---|---|---|---|---|---|---|---|
| `StripeWebhookView` | Stripe SDK signature over raw body | n/a | named-release gate | JSON | none by rule 26 | SDK default (watch `single-sync-worker-vendor-calls`) | advisory mutex + unique `WebhookEvent` | rule 9; async events: `billing-async-payment-never-credited` | `WebhookEvent` row |
| Billing JSON views | session (CSRF) | owner via `_require_request_organization` | DRF serializers | JSON | `quickscale_billing_*` scopes | SDK default | Stripe idempotency keys; unknown-outcome reservations reconcile against the provider | rule 9 | reservation rows; return URLs: `billing-checkout-relative-redirect-urls` |
| `NotificationWebhookView` | custom HMAC: `notifications-webhook-rejects-resend` | n/a | required fields | JSON | none by rule 26 | n/a | idempotency key | rule 9 | delivery event row |
| Orgs JSON API | session (CSRF) | `min_org_role` on the org it acts on | `JSONParser` + forms | JSON | DRF `user` default; invites: `org-invitation-email-unthrottled` | n/a | n/a | rule 9 | n/a |
| Orgs HTML views | `LoginRequiredMixin` | `SaasModeRequiredMixin` + `OrgRoleMixin`; VIEW-AS: `viewas-overrides-management-org` | Django forms | autoescape | none: `org-invitation-email-unthrottled` | n/a | n/a | Django | n/a |
| Invitation accept | login | token + normalized email match | UUID | autoescape | n/a | n/a | `select_for_update` | Django | n/a |
| VIEW-AS | login | superuser, POST only | slug | n/a | n/a | n/a | n/a | 404 | INFO log |
| CRM API | session (CSRF) | `HasOrgRole` viewer/member | serializers reject foreign-org FKs; composite FKs | DRF | DRF defaults | n/a | n/a | rule 9 | n/a |
| Forms public schema/submit | none (`AllowAny`) | System or active org | serializer | DRF | `FormSubmitThrottle` | Resend on commit | n/a | rule 9; status: `forms-notification-status-misreported` | submission row; analytics: `analytics-distinct-id-is-session-key` |
| Forms admin API + CSV | session (CSRF) | `HasOrgRole`; superuser via `operator_access` | DRF | CSV formula cells neutralized | DRF defaults | n/a | n/a | rule 9 | `operator_access` log |
| Blog/listings automation APIs | session (CSRF) | `HasOrgRole(MEMBER)` | Pillow format/size/pixels; extension from format | JSON | blog scope; listings DRF defaults (hand-off) | n/a | slug 409 | rule 9 | n/a |
| Blog/listings public reads | none | System org or active org via `org_scope` | slug | markdown over escaped text + href scheme filter | none | n/a | n/a | Django | n/a |
| Social payload endpoints (generated) | none | System or active org; org-partitioned cache | n/a | `JsonResponse` | none | n/a | n/a | `social-payload-echoes-exception-text` | n/a |
| Analytics page | none: `analytics-dashboard-unauthenticated` | — | n/a | autoescape | none | n/a | n/a | Django | n/a |
| `AccountDeleteView` → anonymize boundary | login | self; last-owner check under locks | form | autoescape | allauth N/A | provider I/O outside atomics | compensating resume | messages | skip log; cross-tenant selectors: `anonymize-matches-unverified-address` |
| auth (allauth) | allauth | n/a | allauth forms | autoescape | allauth `ACCOUNT_RATE_LIMITS` defaults | n/a | n/a | allauth | n/a; ownership: `anonymize-matches-unverified-address` (verification default `none`) |
| Backups admin restore | admin session | `change_backuppolicy` + `QUICKSCALE_BACKUPS_ALLOW_RESTORE` (watch) | confirmation = filename; custom-dump only | autoescape | n/a | background `Popen` | atomic claim | messages | status row |
| `TenantMiddleware` | — | saas membership or 403; solo personal org; VIEW-AS superuser | UUID parse | n/a | n/a | n/a | n/a | 403/redirect; unmounted orgs pass through (`a621299b`) | n/a |
| Management commands (purge/prune/anonymize/restore) | shell | reserved-org guards | args | n/a | n/a | n/a | `--dry-run` on all destructive commands | `CommandError` | tombstones/logs |
| Generated CI workflow | n/a | `permissions:` missing: `generated-ci-mutable-action-tags` | n/a | n/a | n/a | n/a | n/a | fails: `generated-ci-fails-out-of-box` | n/a |
| Image / launcher | n/a | runtime role NOSUPERUSER/NOBYPASSRLS + boot guard | n/a | n/a | n/a | gunicorn 60 s, 1 worker (watch) | migrate per boot (watch) | `HEALTHCHECK`: `docker-healthcheck-always-unhealthy` | stdout |
| Deploy (`deploy railway`) | Railway CLI auth | n/a | n/a | secrets via stdin, never argv | n/a | per-call timeouts | reuses secrets | settings module: `deploy-settings-module-from-service-name` | summary masks secrets |
| Outbound clients (Stripe, Resend, PostHog) | API keys from settings (rule 35) | n/a | n/a | n/a | n/a | SDK defaults (watch); PostHog async | Stripe idempotency keys | mapped errors | n/a |
| Release pipeline (`publish.yml`) | OIDC trusted publishing | environment-gated jobs | tag = `VERSION` check | n/a | n/a | n/a | `skip-existing` on TestPyPI | job failure | GitHub release |

---

## 6. Fix order and batching

1. **Billing batch.**
   - `billing-checkout-relative-redirect-urls` first. It is Trivial and unblocks every purchase.
   - `billing-async-payment-never-credited` is independent (`_webhooks.py`) and can run in
     parallel.
   - **Release note:** do not publish 0.89.0 as a fix for the arch-audit red flag until the first
     item lands.
2. **`analytics-distinct-id-is-session-key`.** Ship the code fix. Then, in each deployment that
   ran analytics, invalidate existing sessions and purge or re-key the PostHog persons (see the
   companion). The session invalidation must follow the fix, or new keys leak again.
3. **Generator-output batch** (one template PR, with a gate that runs the rendered artifacts):
   `generated-ci-fails-out-of-box`, `generated-ci-mutable-action-tags`,
   `docker-healthcheck-always-unhealthy`, `frontend-image-floating-deps`. These touch overlapping
   templates (`ci.yml.j2`, `Dockerfile.j2`), so land them together.
4. **Self-registration hardening:** `anonymize-matches-unverified-address` and
   `org-invitation-email-unthrottled`. These are independent files and can run in parallel.
5. **`notifications-webhook-rejects-resend`.** Independent.
6. **CLI deploy:** `deploy-settings-module-from-service-name` with
   `deploy-runtime-url-unquoted-password` (same file).
7. The remaining S4s, opportunistically.

---

## 7. Per-subsystem verdicts

| Subsystem | Verdict | What was read |
|---|---|---|
| orgs | `viewas-overrides-management-org`; invite part of `org-invitation-email-unthrottled`; invitation scrub part of `anonymize-matches-unverified-address` | Middleware, priming, scopes, permissions, views, API, invitations, anonymization (full). Tenant isolation layers verified. |
| billing | `billing-checkout-relative-redirect-urls`, `billing-async-payment-never-credited` | Views, webhooks, credits, checkout, client, removal (full). Signature, dedupe, and ledger locking verified. |
| notifications | `notifications-webhook-rejects-resend` | Webhook path and anonymization (full). |
| analytics | `analytics-distinct-id-is-session-key`, `analytics-dashboard-unauthenticated` | Full. |
| forms | `forms-notification-status-misreported` | Views and notification helper (full). Public-path scoping, throttle, and CSV neutralization verified. |
| blog | clean | Views, upload validation, `upload_to`, markdown rendering (full). |
| listings | clean | Publish API and service (full). |
| crm | clean | Serializers and viewset permissions (sampled). |
| auth | clean except the default noted in `anonymize-matches-unverified-address` | Delete view and adapters. |
| social | `social-payload-echoes-exception-text` (generated views) | Cache keys clean. |
| storage | clean | Manifest defaults only. |
| backups | clean; one watch item | Admin restore and dispatch (sampled). |
| core runtime / generator | generator-output batch above | Settings facade clean. Identifier validation clean (empirical generation). |
| CLI | `deploy-settings-module-from-service-name`, `deploy-runtime-url-unquoted-password` | Deploy flow (full); remove, push, dependency write (sampled). |
| DR engine | `dr-media-sync-whole-object-read` | Primitives and media (sampled). |
| Release pipeline | clean | `publish.yml` (full); SHA pins, OIDC, build job without restored caches. |
| devtools, `scripts/` gates | not swept | — |

---

## 8. Clean sweeps and rejected candidates

- **Verified — RLS fails closed:**
  - GUC priming issues `SET LOCAL` per transaction, and statements outside an atomic block are
    wrapped. There is no session-level `SET` of `app.current_org_id` anywhere.
  - `RESET app.current_org_id` is session-level despite its docstring, but it resets to empty,
    which is the fail-closed direction.
  - A rolled-back savepoint can leave the priming memo stale. That yields zero rows (the policy
    intersects with an empty GUC), not a leak.
- **Verified — no solo-mode IDOR:** solo mode sets `request.org` on `/orgs/<slug>/…`, but every
  slug view and the whole JSON API are behind `SaasModeRequiredMixin` (404).
- **Verified:** CRM write serializers resolve related objects through `all_objects` but reject
  foreign-org IDs in `validate()`, with composite FKs and RLS underneath.
- **Verified:** blog and listings markdown escapes the source before rendering and filters href
  schemes. No `attr_list`/raw-HTML extension is enabled; Markdownx endpoints are staff-only.
- **Verified:** blog upload type and extension come from Pillow (SA239), with a decompression-bomb
  guard.
- **Verified:** Stripe signature verification happens before parsing. Event-ID dedupe runs under a
  per-event advisory mutex, and credit idempotency under an org row lock plus a unique
  `(stripe_event_id, transaction_type)`.
- **Verified:** generator identifiers are validated (`^[a-z][a-z0-9_-]*$`, `isidentifier`), so
  template interpolation into Python and shell is closed. There is no `shell=True` anywhere, and
  every subprocess call uses an argv list.
- **Verified:** YAML is loaded only through `safe_load`. There is no pickle or eval of external
  data.
- **Verified:** the history credential scan is clean (empirical check 3).
- **Verified:** Railway secrets travel by stdin, never argv. The runtime-role SQL uses
  `psycopg2.sql.Literal`/`Identifier`. Runtime grants cover later tables through
  `ALTER DEFAULT PRIVILEGES` executed by the same superuser that runs `migrate`.
- **Verified:** the production `CSRF_COOKIE_HTTPONLY` is compatible with the SPA, which reads the
  token from a `<meta>` tag.
- **Verified:** the social payload cache is partitioned by org ID; social embeds do no server-side
  fetch, so there is no SSRF.
- **Verified:** the release pipeline is safe as built. Actions are SHA-pinned, `permissions` is
  `contents: read`, publishing uses OIDC, and the build job restores no cache. Tag-name
  interpolation into `run:` requires tag-push rights, so the actor already holds what it would
  grant.
- **Verified:** the closures claimed since the prior pass hold:
  - `billing-anonymize-name-substring` (SA245): word-bounded `redact_names` at
    `billing/_anonymization.py:94-104`.
  - `anonymize-prefilter-ascii-only-casefold`: the Unicode `\w` address pattern at
    `runtime/redaction.py:27-29`.
- **Rejected:** the `deploy railway` app-service name used as the Railway service. That is by
  design; only the derived settings module is wrong.
- **Rejected (§0 consequential):**
  - The forms honeypot path stores unvalidated values. They are bounded by
    `DATA_UPLOAD_MAX_MEMORY_SIZE` and the submit throttle.
  - Forms multipart submissions fail validation (`dict(QueryDict)` yields lists), but the shipped
    client sends JSON.
- **Rejected (§0 live):** a DR media manifest `relative_path` with `..`. The manifest is
  self-generated from storage listings, and the command is operator-only.
- **Rejected (deliberate, documented):** the invitation accepts on GET. It needs the token and the
  matching email, and the state change is the link-click UX.

---

## 9. Structural smells

Carried from the prior passes:
- A typed Stripe provider-adapter seam is missing.
- Session-level advisory locks silently fail under transaction pooling.
- Outbound timeout policy is implicit.
- `start.sh`'s psycopg2 connection is a second database-connection constructor.
- `TenantMiddleware` path ownership is declared twice. The orgs prefixes are now reversed from URL
  names (`a621299b`), but `EXEMPT_PATH_PREFIXES` still hard-codes `/accounts/`, `/admin/`, and
  `/healthcheck/`.

Added:
- **Generated artifacts are only text-asserted.** The CI workflow, the image `HEALTHCHECK`, and
  the deploy-time environment are grepped by tests (`e2e.yml:162-169`), never executed. Three of
  this pass's findings live there. That points at a missing "run the generated project's own
  automation" stage.
- **Provider "unknown outcome" is a state with no exit.** Billing persists provider intent before
  non-transactional calls (correctly), but there is no provider-side lookup that resolves it. The
  same shape exists for one-time and subscription checkouts.

---

## 10. Tooling gaps

- **Extend `check_workflow_security.py` and `make refresh-action-pins` to the rendered
  `ci.yml.j2`.** Would have prevented `generated-ci-mutable-action-tags`.
- **A gate that executes the rendered workflow's test and migrate commands, and the image
  `HEALTHCHECK`, against a generated project.** Would have prevented `generated-ci-fails-out-of-box`
  and `docker-healthcheck-always-unhealthy`.
- **A provider-contract assertion that every URL handed to Stripe is absolute.** Either a unit
  check in `StripeClient`, or one Stripe test-mode e2e call. Would have caught
  `billing-checkout-relative-redirect-urls`.
- **A Resend/Svix contract test built from the vendor's documented payload and signature.** Would
  have caught `notifications-webhook-rejects-resend`.
- **A conformance rule rejecting `session_key` in any value passed to an outbound client or
  logger.** Would have caught `analytics-distinct-id-is-session-key`.
- Carried: image-layer and broader IaC scanning.

---

## 11. Watchlist and accepted trade-offs

- `dr-restore-vintage-exact-match` — the recorded clean-break decision. Trigger: a patch release
  without schema change where operators need an older backup. **Not fired**: there is no
  `dr_engine` change since `e2623cb8`.
- `orgs-provider-id-check-blocks-migrate` — deliberate. Trigger: a contract-vintage step that does
  not list it. **Not fired**: it is listed at `orgs/module.yml:34-35`.
- `crm-stage-seed-lost-on-commit-failure` — Trigger: a report of an org without stages. **Not
  fired**: `receivers.py:17-29` is unchanged.
- `backups-upload-restore-by-model-permission` (new) — Uploaded-dump restore needs only
  `change_backuppolicy` plus `QUICKSCALE_BACKUPS_ALLOW_RESTORE=true`, not superuser. A restored
  dump can write `auth_user`. It is documented as a staff capability, so it is not a finding.
  Trigger: a deployment grants that permission to non-superuser staff while restore is enabled.
- `single-sync-worker-vendor-calls` (new; absorbs the carried "Stripe SDK timeout implicit"
  note) — The launcher defaults to one sync gunicorn worker with a 60 s timeout (documented
  low-cost baseline). Stripe calls run with the SDK's default timeout (80 s), so one slow vendor
  call stalls every request. Trigger: production traffic above one concurrent request, or a
  vendor latency incident.
- `allow-bypassrls-serving-undetected` (new) — `QUICKSCALE_ALLOW_BYPASSRLS=1` plus a blank
  `RUNTIME_DATABASE_URL` in a serving environment silently disables RLS. It is the documented
  escape hatch, and nothing at startup flags a serving process using it. Trigger: any deploy
  tooling or docs that set it outside dev.
- `migrate-runs-per-replica` (new) — `start.sh` runs `migrate` on every container boot. Concurrent
  replicas race, and the loser exits and restarts. Trigger: running more than one replica.
- Carried one-liners, triggers not fired: sender-free `pre_delete` disables fast-delete;
  `org_scope`'s `finally` issues SQL after the body; DRF throttle history is non-atomic on
  `DatabaseCache`; the credit-dedup O(n) scan (`_credits.py:190`);
  `QUICKSCALE_PRIVILEGED_COMMAND` as persistent config; analytics JSON escaping; `BackupError`
  echoing host/user/db; `set_railway_variable` swallowing exceptions; future-dated notification
  timestamps within the TTL.

---

## 12. Coherence hand-offs

- Listings' publish API declares no module throttle scope, while blog's sibling uses
  `BlogApiThrottle` and a `_RATE_LIMIT` option.
- The generated social payload views are plain `JsonResponse` function views, against rule 9's
  DRF base. The exception-text leak is reported here as `social-payload-echoes-exception-text`.
- `analytics` is the only module whose page has no auth or role guard. Rule 19's shape divergence
  belongs to coherence; the info leak is the S4 above.

---

## 13. Questions that would change severity

1. Has one Stripe **test-mode** checkout been completed from the API view at HEAD? If Stripe
   accepted the relative URL, `billing-checkout-relative-redirect-urls` dies.
2. Is the notifications webhook meant to receive Resend directly, or through a relay that
   re-signs? A relay downgrades `notifications-webhook-rejects-resend` to a documentation fix.
3. In deployments with analytics enabled, who has PostHog project access, and do signed-in users
   submit forms? This bounds `analytics-distinct-id-is-session-key`.
4. Are delayed-notification payment methods (SEPA, ACH, Bacs, bank transfer) enabled on the
   Stripe accounts in use? This decides whether `billing-async-payment-never-credited` is live.
5. Do production projects keep the auth default `email_verification: none`? `mandatory`
   downgrades `anonymize-matches-unverified-address`.

---

## 14. Companion hand-off intake

- **Arch-audit red flag** (`arch-audit.md` §13): "0.88.0 on PyPI ships billing that fails every
  Stripe webhook and every checkout with real keys. The fix is on v89."
  - Evaluated as a lead. The webhook part is fixed on v89 (SA209, re-verified).
  - The checkout part is **not**: `billing-checkout-relative-redirect-urls` is present in 0.87.0,
    0.88.0, the `0.89.0` tag, and HEAD.
- **Coherence-audit hand-offs to this audit** (`coherence-audit.md` §9): only
  `billing-anonymize-name-substring`, which was resolved (SA245) and is re-verified in §8.

---

## 15. Reconciliation log

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
- 2026-09-24 — `billing-stripe-objects-normalized-empty`: resolved (`f1627c51`, SA209). Verified at
  `services.py:4235`: `_normalize_mapping` converts SDK objects with `to_dict()` before the mapping
  check, and `test_stripe_contract.py` proves a locally signed body through the real
  `StripeClient.construct_event` keeps its event id.
- 2026-09-24 — `billing-stripe-api-version-drift`: resolved (`f1627c51`, SA209). Verified at
  `services.py:42`, `:505`, `:1813`, `:3060`, `:3108`, `:3152`: `STRIPE_API_VERSION` is declared
  once and set on the SDK, a webhook from a different named release is refused with
  `BillingConfigurationError` (500) and its version is logged, invoice reads use
  `parent.subscription_details`, line prices use `pricing.price_details.price`, and period bounds
  come from agreeing subscription items without blanking known bounds.
- 2026-09-24 — `build-system-requires-unpinned`: resolved (SA210 closeout). Verified at
  `pyproject.toml.j2:31`: generated projects emit `poetry-core>=2.0,<3.0`, and the SA90 emission
  fixture pins the new `pyproject.toml` hashes in all three variants.
- 2026-09-24 — re-run at `cdb6223f`: no prior ID was open and none is reopened; the SA209 and SA210
  closures were re-checked at `services.py:4235` and `pyproject.toml.j2:31` and still hold. Watch
  items carried (triggers not fired); two added (SA205 vintage, SA208 E001). New findings: 0.
- 2026-10-03 — re-run at `c10b529e` (delta `cdb6223f..c10b529e`): no prior finding was open; none
  regressed. The SA209 and SA210 closures hold (`services.py:273–288`, `pyproject.toml.j2`).
- 2026-10-03 — `dr-restore-vintage-exact-match`: carried (trigger not fired).
- 2026-10-03 — `orgs-provider-id-check-blocks-migrate`: carried (trigger not fired).
- 2026-10-03 — `blog-upload-client-extension`: new, open (S3). Pre-existing code whose reachability
  SA226 widened from staff to org members.
- 2026-10-03 — `blog-upload-client-extension`: resolved (SA239). Blog and storage upload paths
  derive the extension from the validated image format.
- 2026-10-03 — `crm-stage-seed-lost-on-commit-failure`: new watchlist (introduced by SA229).
- 2026-10-03 — `orgs-disabled-in-saas-wedges-site`: new watchlist (introduced by SA219).
- 2026-10-05 — re-run at `8e4122f2` (delta `c10b529e..8e4122f2`): no prior finding was open. None
  regressed. The SA239 closure (`blog-upload-client-extension`) still holds: the extension comes
  from the validated format.
- 2026-10-05 — `dr-restore-vintage-exact-match`: carried (trigger not fired).
- 2026-10-05 — `orgs-provider-id-check-blocks-migrate`: carried (trigger not fired).
- 2026-10-05 — `crm-stage-seed-lost-on-commit-failure`: carried (trigger not fired).
- 2026-10-05 — `orgs-disabled-in-saas-wedges-site`: carried (trigger not fired).
- 2026-10-05 — `notifications-anonymize-rewrites-all-messages`: new, open (S2). Introduced by `3cffb168`.
- 2026-10-05 — `anonymize-full-table-scans-under-locks`: new, open (S3).
- 2026-10-05 — `billing-anonymize-name-substring`: new, open (S4).
- 2026-10-05 — `notifications-account-username-dead`: new, open (S4).
- 2026-10-05 — `notifications-anonymize-rewrites-all-messages`: resolved (SA244). The executor
  selects linked messages only; the pre-key fallback matches a complete address in
  `context_json`. Recorded limit: an invitation message sent before the actor key existed names
  only the inviter's display name, so it carries no address and stays as stored.
- 2026-10-05 — `anonymize-full-table-scans-under-locks`: resolved (SA244). Session removal filters
  `expire_date__gt=now()`, billing loads only address-matching payloads, and message selection no
  longer walks the table.
- 2026-10-05 — `notifications-account-username-dead`: resolved (SA244). The helper is deleted.
- 2026-10-05 — re-run at `e2623cb8` (delta `8e4122f2..e2623cb8`): the SA244 closures of
  `notifications-anonymize-rewrites-all-messages`, `anonymize-full-table-scans-under-locks`, and
  `notifications-account-username-dead` were re-verified in code and passed the fix-regression pass.
  None regressed. New findings: 0.
- 2026-10-05 — `billing-anonymize-name-substring`: still-open (S4). Unchanged at
  `_anonymization.py:151`; the SA244 pre-filter now limits it to the person's own payloads.
- 2026-10-05 — `dr-restore-vintage-exact-match`: carried (trigger not fired).
- 2026-10-05 — `orgs-provider-id-check-blocks-migrate`: carried (trigger not fired).
- 2026-10-05 — `crm-stage-seed-lost-on-commit-failure`: carried (trigger not fired).
- 2026-10-05 — `orgs-disabled-in-saas-wedges-site`: carried (trigger not fired).
- 2026-10-05 — `anonymize-prefilter-ascii-only-casefold`: new watchlist (introduced by SA244, `b179990b`).
- 2026-10-06 — `billing-anonymize-name-substring`: **resolved** (SA245, `abbc09d0`; re-verified at
  `9917fec2`). Billing scrubs through core's `replace_address`/`redact_names`; name matching is
  word-bounded, dict keys are never rewritten, and billing's
  `test_anonymize_never_rewrites_payload_keys` pins it. The finding is dropped from the index and
  summary.
- 2026-10-06 — the anonymization **bystander** conformance test gap closed (SA248,
  `notifications/tests/test_anonymization_bystanders.py`): every registered template key renders
  with a sentinel user, the anonymizer selects the linked message, and a bystander's message stays
  byte-identical.
- 2026-10-08 — `anonymize-prefilter-ascii-only-casefold`: **resolved**, and its premise was
  wrong. A PostgreSQL test showed the SQL pre-filter finds a non-ASCII address in another case.
  The miss was in core's `_ADDRESS_PATTERN`, which accepted only ASCII letters, so an
  internationalized address was never scrubbed in any case. The address pattern, the
  notifications escaped-address pattern, and the name word boundaries are now Unicode-aware;
  billing and core tests pin it. Dropped from the index and watchlist.
- 2026-10-08 — Questions: **purged** (`clearsessions`, database ctype). The ctype question is moot
  now that the fix is verified on a UTF-8 database and the matcher no longer depends on ASCII.
- 2026-10-08 — **independent full pass at `2fd8637f`** (at the invoker's request; not a delta
  continuation). The prior document was read after the sweep. It held no open finding, so no
  previously discovered open issue needed carrying beyond the watchlist.
- 2026-10-08 — `billing-anonymize-name-substring`: resolution re-verified in code
  (`billing/_anonymization.py:94-104`).
- 2026-10-08 — `anonymize-prefilter-ascii-only-casefold`: resolution re-verified in code
  (`runtime/redaction.py:27-29`, Unicode `\w`).
- 2026-10-08 — `dr-restore-vintage-exact-match`: carried (trigger not fired).
- 2026-10-08 — `orgs-provider-id-check-blocks-migrate`: carried (trigger not fired).
- 2026-10-08 — `crm-stage-seed-lost-on-commit-failure`: carried (trigger not fired).
- 2026-10-08 — `orgs-disabled-in-saas-wedges-site`: **retired**. The premise is obsolete since
  `a621299b` (SA235, already contained in `e2623cb8`). The middleware now redirects only when the
  orgs index reverses, and passes the request through when the orgs URLs are unmounted (verified
  at `middleware.py:195-198`). Earlier passes carried it as "middleware unchanged" without
  re-reading the redirect.
- 2026-10-08 — carried one-liners: the Stripe SDK timeout note is merged into the new watchlist
  item `single-sync-worker-vendor-calls`; the others are carried (not fired).
- 2026-10-08 — new open: `billing-checkout-relative-redirect-urls` (S2, regression `c7320b02`),
  `analytics-distinct-id-is-session-key` (S2), `generated-ci-fails-out-of-box`,
  `notifications-webhook-rejects-resend`, `billing-reservation-unknown-outcome-permanent`,
  `anonymize-matches-unverified-address`, `org-invitation-email-unthrottled`,
  `deploy-settings-module-from-service-name`, `billing-async-payment-never-credited`,
  `generated-ci-mutable-action-tags` (S3), and eight S4s.
- 2026-10-08 — new watchlist: `backups-upload-restore-by-model-permission`,
  `single-sync-worker-vendor-calls`, `allow-bypassrls-serving-undetected`,
  `migrate-runs-per-replica`.
- 2026-10-08 — `billing-checkout-relative-redirect-urls`: **code resolved** (SA251, slice a). The
  purchase, subscription, and portal views build their return URLs with
  `request.build_absolute_uri(reverse(...))`, and `StripeClient` refuses a URL without a scheme
  and host before any provider call; view tests pin the absolute values and contract tests pin the
  refusals. The live Stripe test-mode checkout record is still owed, so the finding stays open.
- 2026-10-08 — `billing-reservation-unknown-outcome-permanent`: **resolved** (SA251, slice b). A
  definitive Stripe 4xx rejection resolves the reservation against the provider before it is
  closed (`_removal.py` `_resolve_definitively_failed_purchase_checkout`,
  `_subscription_checkout_steps.py` `_resolve_definitively_failed_subscription_checkout`); a
  session-less reservation is looked up by its stored reference and adopted, expired, or voided
  (`StripeClient.find_checkout_session_by_reference`, `_removal.py`, `_subscription_checkout.py`);
  and `quickscale_billing_reconcile_checkouts` clears accumulated rows under the organization's
  provider mutation mutex. Verified by the billing, orgs, and auth suites.
