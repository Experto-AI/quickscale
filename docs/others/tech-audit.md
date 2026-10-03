# QuickScale — Deep Technical Audit (defect sweep)

Audited: c10b529e (v89) · 2026-10-03 · working tree dirty (uncommitted `docs/others/arch-audit.md` only; not read as code) · repository public (github.com/Experto-AI/quickscale) · prompt: deep-technical-audit v6

> **Re-run of:** the 2026-09-24 pass at `cdb6223f` · **Delta swept:** `cdb6223f..c10b529e`
> (179 non-merge commits since 2026-09-24, plus older commits merged in from worktree branches;
> 830 non-doc files, about +100k/−58k lines). The full diff did not fit the budget. It was read
> in §2f order, and the sampling is stated below.

---

## 1. Orientation summary

QuickScale is a **Python 3.14 / Django project generator and module workspace** laid out as a
Poetry monorepo: `quickscale_core` (generator, Jinja2 templates, DR engine, manifest and plan/apply
engine, runtime helpers), `quickscale_cli` (Click), `quickscale_devtools`, and twelve first-party
Django modules under `quickscale_modules/`. The three deployment realities are unchanged:

- **R1 — the generator/CLI**, run on a developer or CI machine. Local trust boundary.
- **R2 — the generated Django application**, deployed to Railway or any container host behind a
  reverse proxy. It is internet-facing, and multi-tenant when `QUICKSCALE_ORGS_MODE=saas`. In
  `solo` mode every authenticated user gets a personal organization and is its **owner**
  (`TenantMiddleware._get_personal_org`). That fact now drives reachability for every
  org-role-gated endpoint (see SA226 below). Severity concentrates here.
- **R3 — the release pipeline** (`.github/workflows/publish.yml`), OIDC trusted publishing.

**What changed in this delta.**

- **SA226** replaced staff-only authorization (`IsAdminUser` / `is_staff`) with org-role
  authorization (`HasOrgRole`, `OrgRoleMixin`) on crm, forms admin, the blog automation API, and
  the listings publishing API. Combined with solo mode's personal-owner orgs, these surfaces moved
  from *staff* to *any signed-up user, scoped to their own org*.
- **SA223** rebased the orgs JSON API and both webhooks on DRF, and moved URL mounts into
  manifests.
- **SA219/SA217** moved module options onto the manifest engine. Secrets are projected as
  `os.environ.get(...)` in generated settings.
- **SA228/SA229** collected account-deletion work behind declared capabilities and tied write
  side effects to `on_commit`.
- **SA231/SA232** split large modules into private files behind re-exporting facades.
- **SA225** added a build-time module-check skip bound to `manage.py collectstatic`.

**Entry points and actors.** R2: per-module URLconfs. These include DRF session APIs (billing,
crm, forms admin, orgs, blog and listings publishing), the public forms schema and submit APIs,
two signature-authenticated webhooks, class-based auth and org views, and the operator commands
(`quickscale_orgs_purge_organization`, DR backup/restore). The actors are an anonymous visitor,
an authenticated user (owner of a personal org in solo mode), members of another tenant (saas),
superusers (the declared operator path), and hostile upload content. R1: the Click tree. R3:
tag-triggered workflows.

**Crown jewels.** Tenant data across modules (crm contacts, form submissions with PII); Stripe
identifiers and the credit ledger; credentials in the environment; DR dumps; the release pipeline.

**Configuration axes (§2h).** `QUICKSCALE_ORGS_MODE` solo/saas; per-module `*_ENABLED` switches
(new in SA219/SA220); storage backend local versus S3-compatible (`STORAGES`); `REDIS_URL`
present or absent (cache backend); `DEBUG` (media served by Django only in DEBUG,
`urls.py.j2:93–95`); `QUICKSCALE_PRIVILEGED_COMMAND`; `QUICKSCALE_SKIP_MODULE_CHECKS`
(collectstatic only).

**Tooling baseline.** Unchanged from the prior pass: Ruff (including `S`), mypy, pytest with
PostgreSQL module suites, Bandit, Trivy (dependencies and generated Dockerfile misconfig),
gitleaks, and zizmor, all failing the build. New this delta is a module-conventions conformance
harness (`scripts/check_module_conventions.py`, 36 rules). It caught the one split-merge
regression in the delta (`093489e6`).

**Oracle list (§2g).** Items 1–10 of the prior pass are carried. Re-checked this pass: 3 (the
privileged and skip exemptions stay one-shot and inline — `Dockerfile.j2:197`), 4 (secrets never at
rest — `module_wiring.render_settings_modules_py` renders `os.environ.get`), 7 (webhook mutex —
`services.py:288`), 8 (provider I/O outside transactions — account-deletion recheck performs DB
reads only). Added:

11. **Org-scoped module APIs authorize by the caller's role in the active org** (Module
    Conventions rule 19; `orgs/permissions.py`). Superuser is the one listed operator path.
12. **Webhook signatures are verified over raw bytes before parsing** (rule 26).
13. **Write side effects run on commit** (rule 21, SA229).

**Data sensitivity (§2i).** Unchanged: credentials and sessions, Stripe identifiers and a
money-adjacent credit ledger, tenant business data, and form-submission PII (exportable as CSV),
plus DR dumps. Logs are JSON to stdout.

**Hotspots (§3.4, delta only).** Filter: no merges, commits touching ≤30 files, docs/tests
excluded, fix-keyword commits only. Top fix-density files: `auth/views.py` (6),
`core/data/project_contract.yml` (6), `runtime/conventions.py` (5), `analytics/checks.py` (4),
`docker-compose.yml.j2` (3). All of them except the contract YAML were read for this pass.

### Coverage statement

**Delta classification (§2f).** Every behavioral commit carries an SA ticket and a validation
trail. Many carry recorded independent-review rounds (SA225, SA228, SA229, SA230). Housekeeping
commits: the roadmap and audit rebalance/cleanup commits, plus the version bumps merged from
worktree branches. **No unreviewed-behavioral commit** was found. The single "Refactor
documentation…" commit (`f0b67b7c`) and the module-conventions commits (`55d1a143`…`fa0b882b`)
touch docs only. The old `WIP: SA195 & SA192` commits are already covered by the 2026-09-23 pass.

*Read in full:* `orgs/permissions.py` (SA226); the SA226 diff for crm, forms, blog, and listings
views; `crm/serializers.py` cross-org FK validation; forms `FormsAdminApiMixin`,
`_get_org_bound_queryset`, submission list/detail/export; `orgs/_api_views.py`,
`_view_context.get_organization`; `orgs/middleware.py` (solo/saas/debug/management-path
resolution); billing `_BillingAPIView` and every billing view's auth path; `StripeWebhookView`
and `NotificationWebhookView` with `_verify_webhook_signature`; `handle_stripe_event` through
lock acquisition; `billing/_locks.py`; purge `_provider_mutation_lock`; auth
`_account_deletion_flow.py` and billing's `account_deletion_user_reference_organization_ids`;
`runtime/conventions.py` skip binding (`b85920ce`); `module_wiring.render_settings_modules_py`
and every module adapter's `__QS_ENV__` projection (analytics, billing, notifications, storage);
blog `services.py` upload validation and `models.blog_media_upload_to`; storage
`build_upload_path` and `validate_file_upload`; `Dockerfile.j2` build step; crm `receivers.py`
and `ensure_org_default_stages`.

*Mechanical sweep:* an AST diff of every class's bases and of its
`permission_classes`/`authentication_classes`/`min_org_role`/`throttle_classes`/`http_method_names`
between `cdb6223f` and HEAD, across `quickscale_modules` and `quickscale_core/src`. Its purpose is
variant analysis for the split-merge mixin loss. Every changed class was resolved:
`_BillingAPIView` now carries the removed attributes; crm/forms changed by SA226; webhooks changed
by SA223; `OrgInvitationAcceptView` was restored by `093489e6`. **No auth safeguard was dropped by
a split.**

*Sampled:* the SA231/SA232 facade splits (the class sweep above stands in for line-by-line
reading); SA217 manifest-engine moves; SA227 renames; the test hunks (the tamper sweep found only
conditional `pytest.skip` for modules without templates or without PostgreSQL. Every module test
settings file uses PostgreSQL, so the RLS boundary tests run).

*Skipped:* the React/TypeScript sources; `quickscale_cli` and devtools splits beyond the facade
sweep; DR engine split internals (SA232 claims a verbatim move, which was not verified line by
line); the manifest/plan engine internals beyond secret rendering; migrations.

*Audit tools run:* none beyond `git` and the project's own interpreter for one AST script, which
ran from scratch space and executed no project code. No scanner output is transcribed.

*Empirical checks (§1e):* none executed against project code. Candidates settled on paper:

- **Killed:** an empty `_ENV_VAR` name leaving the literal `__QS_ENV__:` marker as a secret.
  Notifications, billing, and storage guard on emptiness. Analytics raises `ManifestError` when
  enabled with an empty name. The renderer's regex requires one or more characters, and the
  manifest pattern `^(?:[A-Z][A-Z0-9_]*)?$` prevents code injection through the name.
- **Killed:** an org-slug IDOR in the orgs JSON API. Both the role check
  (`OrgApiBaseView.initial`) and the data access (`get_organization`) resolve the same org.
  `request.org` comes first and the slug is the fallback, so authorization and action never
  diverge.
- **Killed:** solo-mode cross-tenant reach through SA226. Every crm/forms/blog/listings path scopes
  to `request.org` (the caller's personal org). Crm serializers reject foreign-org FKs. The public
  blog and listings reads show System-org content to anonymous readers.

*Category activation:* active: I–IV, VI–IX, X-generator, X-multi-tenant, X-service · inert: V (no
hot-path delta), X-frontend (React not read this pass) · produced: III.

**Residual risk.** No PostgreSQL, Stripe, or object store was exercised. The one new finding's
severity depends on whether operators front the bucket with a domain that shares a site with the
app (§13). The DR-engine and CLI splits were trusted from their facade structure and gate runs, not
read line by line. Silence on those areas means *not looked at*, not *clean*.

*Prior pass statements* are preserved in version control (`git show cdb6223f:docs/others/tech-audit.md`).

---

## 2. Machine-readable finding index

```yaml
schema: tech-audit/v6
audited: c10b529e3a6076554c09e35c9af28adb28454a78
items:
  - {id: dr-restore-vintage-exact-match, status: watchlist, category: I,
     title: "Restore refuses any backup after a module patch bump", reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/dr_engine/recovery.py], first_seen: 2026-09-24, last_verified: 2026-10-03}
  - {id: orgs-provider-id-check-blocks-migrate, status: watchlist, category: VI,
     title: "Unclassified tenant *_id field fails migrate on upgrade", reality: generated-app,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/checks.py], first_seen: 2026-09-24, last_verified: 2026-10-03}
  - {id: crm-stage-seed-lost-on-commit-failure, status: watchlist, category: II,
     title: "CRM default stages are never seeded if the on-commit seed fails", reality: generated-app,
     anchors: [quickscale_modules/crm/src/quickscale_modules_crm/receivers.py], first_seen: 2026-10-03, last_verified: 2026-10-03}
  - {id: orgs-disabled-in-saas-wedges-site, status: watchlist, category: VI,
     title: "Orgs switched off in saas mode redirects every page to an unmounted /orgs/", reality: generated-app,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/middleware.py], first_seen: 2026-10-03, last_verified: 2026-10-03}
```

---

## 3. Summary table

**Counts:** S1 — 0 · S2 — 0 · S3 — 0 · S4 — 0 · total 0 open. Reconciliation: 1 resolved. Watch items: 2 carried, 2 added.

---

## 4. Findings

No open findings.

---

## 5. Safeguard matrix

Prior rows are carried. Rows changed this pass are marked ★.

| Entry point | AuthN | AuthZ | Input validation | Output encoding | Rate limit | Timeout | Idempotency | Error shape | Audit |
|---|---|---|---|---|---|---|---|---|---|
| ★ `StripeWebhookView` (DRF) | HMAC over `request.body` via SDK | n/a | named-release version gate | JSON | none (signature-gated) | implicit SDK — Notes | per-event advisory mutex + unique `WebhookEvent` | rule-9 shape | `WebhookEvent` row |
| ★ `NotificationWebhookView` (DRF) | HMAC over raw body before parse; empty secret refused | n/a | required fields | JSON | none (signature-gated) | n/a | idempotency key | rule-9 shape | delivery row |
| ★ Billing JSON views (`_BillingAPIView`) | session + `_require_authenticated` | `require_owner=True` re-checked under mutex | DRF / JSON only | JSON | `quickscale_billing_*` scopes | implicit SDK | Stripe idempotency keys | rule-9 shape | reservation rows |
| ★ CRM API + dashboard | session (CSRF) | `HasOrgRole` viewer/member; queries pinned to `request.org` | serializers reject foreign-org FKs | DRF | DRF defaults | n/a | n/a | DRF | n/a |
| ★ Forms admin API + CSV export | session (CSRF) | `HasOrgRole` viewer/member; `_get_org_bound_queryset` + RLS | DRF | CSV cells neutralized | DRF defaults | n/a | n/a | DRF | `operator_access` for superusers |
| Forms public schema/submit | `AllowAny` | n/a | serializer | DRF | `FormSubmitThrottle` | n/a | n/a | DRF | submission row |
| ★ Blog automation API | session (CSRF) | `HasOrgRole(MEMBER)`, org-stamped | Pillow format/size/pixel; extension from the validated format | JSON | `quickscale_blog_api` | n/a | slug 409 | rule-9 shape | n/a |
| ★ Listings publish API | session (CSRF) | `HasOrgRole(MEMBER)`, org-stamped | module validation | JSON | DRF defaults | n/a | slug 409 | rule-9 shape | n/a |
| ★ Orgs JSON API (DRF) | session (CSRF), 401 challenge | `min_org_role` on the same org it acts on | `JSONParser` + forms | JSON | DRF defaults | n/a | n/a | rule-9 shape | n/a |
| ★ `OrgInvitationAcceptView` | `LoginRequiredMixin` (restored `093489e6`) | token lookup | n/a | autoescape | out of scope | n/a | n/a | Django | n/a |
| `AccountDeleteView` | `LoginRequiredMixin` | self; last-owner under locks; locked recheck | form | autoescape | out of scope | provider I/O outside atomics | compensating resume | messages | skip log |
| `TenantMiddleware` | — | saas: membership or 403; solo: personal org; view-as superuser-only | UUID parse | n/a | n/a | n/a | n/a | 403/redirect | n/a |
| Purge command | shell | UUID target, reserved-org guard | UUID | n/a | n/a | n/a | tombstone; all declared provider locks, released on acquisition failure | `CommandError` | tombstone |
| ★ Image build `collectstatic` | n/a | skip bound to `manage.py`/`django-admin` + `argv[1]=="collectstatic"` | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| DR backup/restore, CLI tree, release pipeline | carried unchanged — see prior pass | | | | | | | | |

Every empty cell carries a finding ID or a stated reason.

---

## 6. Fix order and batching

No open findings.

---

## 7. Per-subsystem verdicts

- **orgs** — clean. Permissions, middleware, JSON API base, and invitation view read in full.
- **crm** — clean. The SA226 view diff and the serializers' FK validation read in full.
- **forms** — clean. The admin API, org-bound queryset, export, and on-commit effects were read.
- **blog** — clean. API and upload validation read in full.
- **billing** — clean. Every view's auth path, the webhook pipeline up to the lock, and the locks
  were read. The SA232 split was checked through the class sweep.
- **notifications** — clean. Webhook verification read in full.
- **auth** — clean. The account-deletion flow and provider-reference path were read.
- **analytics / storage adapters** — clean. The secret projection was read in full.
- **core runtime / generator** — clean: the conventions skip binding, the settings renderer, and
  the Dockerfile build step.
- **dr_engine, CLI, devtools** — not read this pass beyond the split facades (residual risk).

---

## 8. Clean sweeps and rejected candidates

- **No split dropped an auth safeguard.** The AST class sweep covered all module and core source
  (see §1).
- **Webhooks verify over raw bytes** after their DRF conversion (`request.body`), and notifications
  refuses an empty secret.
- **Secret projection never puts credentials at rest.** The empty-name and injection paths were
  killed (§1).
- **SA226 keeps tenant isolation.** The role check and data access resolve the same org.
  Solo-mode personal orgs isolate signups from each other and from System-org content.
- **Provider locks release on any acquisition failure** in both the account-deletion and purge
  paths (`79772707`, `0ae197a3`, `85274b15`). The base advisory lock helper releases in `finally`.
- **Build-time check skip cannot reach a serving process** (`b85920ce`). The secret key used at
  build time is generated inline per build and is not persisted in an `ENV` layer.
- **No weakened tests.** The new skips are conditional on a module having no templates. The
  `assert True` strings are fixture file contents for the conventions harness.

---

## 9. Structural smells

The four items from the prior pass are carried (typed Stripe adapter seam, session advisory locks
versus transaction pooling, implicit outbound timeouts, two DB connection constructors). One is
added:

- `TenantMiddleware` hard-codes `/orgs/`, `/orgs/api/`, and `/accounts/` while SA223 moved URL
  mounts into manifests. Path ownership is declared in two places. That is harmless today because
  the prefixes are not configurable.

---

## 10. Tooling gaps

- Gaps from the prior pass (image-layer and broader IaC scanning) are carried.

---

## 11. Watchlist and accepted trade-offs

- `dr-restore-vintage-exact-match` — the recorded clean-break decision. Trigger: a patch release
  without migration change where operators need an older backup. **Not fired**: the vintage check
  is still present (`dr_engine/_restore.py`, `recovery.py`).
- `orgs-provider-id-check-blocks-migrate` — deliberate (`orgs/checks.py:421–447`). Trigger: a
  contract-vintage step that does not list it. **Not fired**: it is listed in
  `orgs/module.yml` `manual_adoption_steps`.
- `crm-stage-seed-lost-on-commit-failure` (new) — since SA229, `seed_crm_default_stages_on_org_created`
  runs on commit. If the seed raises after the org row committed, the user sees a 500 and the org
  never gets stages: there is no warm-on-read path, and `_resolve_terminal_stage` returns `None`.
  This fails §0 consequential/live: it needs a database error in the window right after commit.
  Trigger: any report of a CRM org without stages, or adding a failing step to seeding.
- `orgs-disabled-in-saas-wedges-site` (new) — `TenantMiddleware` stays installed and redirects to
  `/orgs/` even when `QUICKSCALE_ORGS_ENABLED=false` drops the mount. The redirect target 404s.
  Operator-chosen, immediately visible, and blocked whenever any installed module requires orgs.
  Trigger: an install path that disables orgs automatically.
- Carried, triggers not fired: the Stripe SDK timeout is still implicit (`_stripe_client.py` sets
  none); the sender-free `pre_delete` receiver disables fast-delete; `org_scope`'s `finally` issues
  SQL after the body; DRF throttle history is non-atomic on DatabaseCache; the credit-dedup O(n)
  scan (now `_credits.py:163`); `QUICKSCALE_PRIVILEGED_COMMAND` as persistent config; analytics
  JSON escaping; `BackupError` echoing host/user/db; `set_railway_variable` swallowing exceptions;
  future-dated notification timestamps within the TTL.

---

## 12. Questions that would change severity

None open.
---

## 13. Reconciliation log

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
