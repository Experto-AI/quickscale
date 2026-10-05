# QuickScale — Deep Technical Audit (defect sweep)

Audited: e2623cb8 (v89) · 2026-10-05 · working tree dirty (uncommitted `docs/others/arch-audit.md` only; not read as code) · repository public (github.com/Experto-AI/quickscale) · prompt: deep-technical-audit v6

> **Re-run of:** the 2026-10-05 pass at `8e4122f2` · **Delta swept:** `8e4122f2..e2623cb8`
> (7 non-merge commits, 4 merges). The production diff was read in full. The SA247 script split was
> verified by inventory, not read line by line.

---

## 1. Orientation summary

Archetype, stack, deployment realities, actors, crown jewels, configuration axes, tooling
baseline, data sensitivity, and oracle items 1–14 are **unchanged from the 2026-10-05 pass at
`8e4122f2`** (`git show 8e4122f2:docs/others/tech-audit.md`, §1). In brief: a Python 3.14 / Django 6.0
project generator and module workspace (a Poetry monorepo). It has three realities: **R1**
generator/CLI, **R2** the generated internet-facing Django app (multi-tenant in saas mode), and
**R3** the OIDC release pipeline. The repository is public.

**What changed in this delta.**

- **SA244** (`b179990b`, merged in `322e1ff5`) closed three prior findings in the anonymization
  path:
  - Session removal now walks only unexpired rows.
  - Billing payloads are pre-filtered in SQL with `payload__icontains=email`.
  - Notifications select only linked messages: by delivery, by `context_json.actor_user_id`, or by
    an `icontains` pre-filter verified as a complete address.
- **SA246** (`2f1d0a4e`, `db0fcc55`) adds per-module `personal_data_declarations` (records in
  `quickscale_core.runtime.conventions`). It also adds the warning-only system check
  `quickscale_orgs.W006` over project models (`orgs/_personal_data.py`, `checks.py:345`).
  This is declarative, and no runtime path consumes it except the check.
- **SA247** (`fe5d808a`, `7969c59b`) splits `scripts/check_module_conventions.py` and its tests into
  packages. This is R1 developer/CI tooling.
- `467ced81` (docs plus a one-line interpreter-guard scope), and `d08f513c` (roadmap).

**Delta classification.** Every behavioral commit carries an SA ticket. `d08f513c` and `467ced81`
are housekeeping. **No unreviewed-behavioral commit.** The merge commits were checked with
`git log --merges`. They carry no hunks beyond their parents (they integrate the worktree tracks).

**Hotspots.** The delta replaces churn ranking. It contains no fix-keyword commits outside the SA244
closures.

### Coverage statement

*Read in full:* the SA244 diff (auth/billing/notifications `_anonymization.py`), the orgs
invitation sender (`views.py:150–212`) and the `OrgApiInviteView`/`InviteView` mixin use, the SA246
diff of `checks.py`, `_personal_data.py`, and `runtime/conventions.py`, and the auth/billing
declaration blocks.

*Sampled:* the module `apps.py` declaration blocks (crm, forms, blog, listings, backups,
notifications).

*Verified by inventory (SA247):* the old and new checker define the same 188 top-level functions.
The old and new test suites hold 227 tests each. The new checker passes all 40 covered rules at
HEAD.

*Skipped:* everything outside the delta. Prior-pass coverage stands for it.

*Audit tools:* git; Django 6.0.8 (installed, read-only).

*Empirical checks (§1e):*

1. In scratch space, Django compiled the SQL for `JSONField(...).filter(payload__icontains=…)` on the
   PostgreSQL backend with no connection. Result: `UPPER("payload"::text) LIKE UPPER('%…%')`, a
   raw substring with no JSON encoding of the right-hand side. **Refuted** the candidate that the
   SA244 pre-filter drops matches (see §8).
2. The pre-split checker (`git show 8e4122f2:…`) ran against HEAD from the repository root. Its 7
   reported violations come from it scanning the new `scripts/module_conventions/` files, not from a
   missing rule.

*Category activation:* active: I, II, III, VI, VIII, IX, X-generator, X-multi-tenant · inert: IV,
V (no I/O or hot-path delta beyond SA244's narrowing), VII (no dependency or workflow delta) ·
produced: none new.

**Residual risk.** No PostgreSQL instance was available (`pg_isready`: no response), so the SA244
queries were compiled, not executed. `UPPER` under a non-UTF-8 or `C` collation folds only ASCII
(see the watchlist). Code outside the delta was not re-read this pass.

---

## 2. Machine-readable finding index

```yaml
schema: tech-audit/v6
audited: e2623cb8bb727d177c337d1431db40e134dcfaf0
items:
  - {id: billing-anonymize-name-substring, status: open, severity: S4, category: I,
     title: "Billing payload scrub replaces the name as a bare substring, including in dict keys", effort: Trivial,
     confidence: High, reality: generated-app,
     anchors: [quickscale_modules/billing/src/quickscale_modules_billing/_anonymization.py], first_seen: 2026-10-05, last_verified: 2026-10-05}
  - {id: dr-restore-vintage-exact-match, status: watchlist, category: I, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/dr_engine/recovery.py], first_seen: 2026-09-24, last_verified: 2026-10-05}
  - {id: orgs-provider-id-check-blocks-migrate, status: watchlist, category: VI, reality: generated-app,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/checks.py], first_seen: 2026-09-24, last_verified: 2026-10-05}
  - {id: crm-stage-seed-lost-on-commit-failure, status: watchlist, category: II, reality: generated-app,
     anchors: [quickscale_modules/crm/src/quickscale_modules_crm/receivers.py], first_seen: 2026-10-03, last_verified: 2026-10-05}
  - {id: orgs-disabled-in-saas-wedges-site, status: watchlist, category: VI, reality: generated-app,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/middleware.py], first_seen: 2026-10-03, last_verified: 2026-10-05}
  - {id: anonymize-prefilter-ascii-only-casefold, status: watchlist, category: I, reality: generated-app,
     anchors: [quickscale_modules/billing/src/quickscale_modules_billing/_anonymization.py,
               quickscale_modules/notifications/src/quickscale_modules_notifications/_anonymization.py],
     first_seen: 2026-10-05, last_verified: 2026-10-05}
```

---

## 3. Summary table

**Counts:** S1 — 0 · S2 — 0 · S3 — 0 · S4 — 1 · total 1 open.

| ID | Sev | Cat | Title | Effort | Conf | Since |
|---|---|---|---|---|---|---|
| `billing-anonymize-name-substring` | S4 | I | Name replaced as a bare substring, keys included | Trivial | High | carried |

---

## 4. Findings

### S4

- `billing-anonymize-name-substring` · `billing/_anonymization.py:131–152` · within the person's own
  webhook payloads, `_redact_string` replaces the name as a bare case-insensitive substring
  (`re.sub(re.escape(name), …)`, `:151`). `_redact_identity` applies it to dict **keys** too
  (`:135`). A short name such as "Al" or "Id" mangles field names like `total` or `customer_id`.
  Since SA244, only payloads that contain the person's address are loaded, so the damage stays
  inside their own events. Fix: use the notifications word-boundary matcher, and leave keys alone.
  This is carried by SA245, which gates the 0.89.0 release.

---

## 5. Safeguard matrix

Carried from the prior pass. This delta adds no entry point: SA246 is a system check, and SA247 is
developer tooling. One cell changed: anonymize executors — **Timeout/bounds** now reads "SQL
pre-filtered selections (SA244)".

Prior rows are carried. Rows added this pass are marked ★.

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

| ★ `AccountDeleteView` → anonymize boundary | `LoginRequiredMixin` | self only | form | autoescape | out of scope | bounded selections (unexpired sessions, address-matched payloads, linked messages) | compensating resume (lost on worker kill, same ID) | messages | INFO skip log |
| ★ Anonymize executors (write scope) | n/a | orgs/blog/auth scoped by user FK; billing scoped by email; notifications scoped by delivery, actor link, or address | n/a | n/a | n/a | n/a | one transaction | n/a | none |
| ★ `quickscale_orgs_create_site_org` | shell (runtime role) | reserved-slug guard | field validators | n/a | n/a | n/a | `get_or_create` | `CommandError` | stdout |
| ★ SPA module routes (`SPA_MODULE_URLPATTERNS`) | static shell; data via the module APIs above | n/a | n/a | n/a | n/a | n/a | n/a | 404 handler | n/a |

Every empty cell carries a finding ID or a stated reason.


---

## 6. Fix order and batching

1. **Batch B (open):** `billing-anonymize-name-substring`, carried by SA245 (shared redaction
   helpers), with the bystander conformance test in §10. It is independent of everything else.
   Batch A (SA244) landed and was verified.

---

## 7. Per-subsystem verdicts

- **auth**: clean. The SA244 session filter was read (`_anonymization.py:161–176`), and the SA246
  declarations were read.
- **billing**: `billing-anonymize-name-substring`. The SA244 SQL pre-filter was read and its SQL
  compiled.
- **notifications**: clean. Linked-message selection was read in full, and the actor key and address
  fallback were verified.
- **orgs**: clean. The SA246 W006 check and `_personal_data.py` were read, and the invitation context
  stamps `actor_user_id` as a string on both invite views.
- **core runtime**: clean. The declaration records are frozen dataclasses with no behavior.
- **scripts (SA247)**: clean by inventory (see the coverage statement).
- **Other subsystems**: not re-read this pass. The prior verdicts stand.

---

## 8. Clean sweeps and rejected candidates

- **Killed:** the SA244 `payload__icontains=email` / `context_json__icontains=email` pre-filter
  missing real matches because Django JSON-encodes the right-hand side. Empirical check 1: it compiles
  to `UPPER(col::text) LIKE UPPER('%email%')`, with LIKE wildcards escaped by Django. jsonb text
  output keeps an address verbatim.
- **Killed:** the actor-link lookup missing invitations because of a type mismatch. Both writer
  (`orgs/views.py:200`) and reader (`notifications/_anonymization.py:146`) use `str(pk)`. Both
  `InviteView` and `OrgApiInviteView` build the context through `InvitationNotificationMixin`.
- **Verified:** SA244 closures (`notifications-anonymize-rewrites-all-messages`,
  `anonymize-full-table-scans-under-locks`, `notifications-account-username-dead`) are present in
  code. The fix-regression pass (§3.8) found no new failure mode: the candidate set is a superset
  of the person's deliveries, and wholesale replacement is still limited to unshared delivered
  messages.
- **Verified:** the SA247 split dropped no rule (188 functions, 227 tests, 40 rules passing).
- **Rejected (§0 consequential):** the W006 check's `except Exception` turns any error into one
  warning. It is warning-only by design, and the message carries the exception text.
- **Rejected (design, not a defect):** the W006 candidate rules do not flag `CharField` name fields.
  The inventory is a stated heuristic, with the closed-world test as its backstop. Handed to
  coherence (§13).
- Prior clean sweeps are carried.

---

## 9. Structural smells

The six items from the prior passes are carried (`git show 8e4122f2:docs/others/tech-audit.md`, §9, and `c10b529e`, §9). None was added.

---

## 10. Tooling gaps

- The prior gaps are carried: image-layer and IaC scanning, and the anonymization **bystander**
  conformance test (it would have caught `billing-anonymize-name-substring`).
- The SA244 anonymization tests run on PostgreSQL, but nothing pins the `icontains` pre-filter
  against a non-ASCII address whose stored case differs. A single test would pin
  `anonymize-prefilter-ascii-only-casefold`.

---

## 11. Watchlist and accepted trade-offs

- `dr-restore-vintage-exact-match` — the recorded clean-break decision. **Not fired**: the delta
  does not touch `dr_engine/`.
- `orgs-provider-id-check-blocks-migrate` — deliberate. **Not fired**: it is still listed in
  `orgs/module.yml:35` `manual_adoption_steps`.
- `crm-stage-seed-lost-on-commit-failure` — **Not fired**: the delta touched only crm `apps.py`
  (declarations).
- `orgs-disabled-in-saas-wedges-site` — **Not fired**: `middleware.py` is unchanged.
- `anonymize-prefilter-ascii-only-casefold` (new, introduced by SA244) — the SQL pre-filter folds
  case with PostgreSQL `UPPER`, while the Python verifier uses `str.casefold`. If the database
  ctype is `C`/non-UTF-8, or the address uses non-ASCII letters whose case differs between
  `User.email` and the stored payload or context, the pre-filter skips a row that the old full walk
  would have scrubbed. The person's address would then stay in their own event. This fails §0
  consequential/live today: it needs an internationalized local part, a case mismatch, and a
  non-UTF-8 collation, and Stripe and the app store the address as entered. Trigger: a database
  provisioned with a `C` ctype, or address normalization that changes case.
- The carried one-liners (Stripe SDK timeout, sender-free `pre_delete`, `org_scope` `finally`
  SQL, DRF throttle history, credit-dedup scan, `QUICKSCALE_PRIVILEGED_COMMAND`, analytics JSON
  escaping, `BackupError` echo, `set_railway_variable`, future-dated notification timestamps) are
  untouched by this delta. They are carried, with no trigger fired.

---

## 12. Questions that would change severity

1. (carried) Do generated deployments run `manage.py clearsessions`? Since SA244, expired session
   rows are skipped, so they hold the person's session data until the host purges them.
2. Is the production database always created with a UTF-8 ctype? A `C` ctype gives
   `anonymize-prefilter-ascii-only-casefold` a live precondition.

---

## 13. Coherence hand-offs

- `personal_data_declarations` blocks are hand-written per module with repeated
  `PersonalDataField(app_label=self.label, …)` boilerplate, and `CharField` identity fields (display
  names) are declared in some modules but are not W006 candidates. This is a divergence risk, not a
  defect today.

---

## 14. Reconciliation log

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
