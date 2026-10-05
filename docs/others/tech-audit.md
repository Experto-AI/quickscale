# QuickScale — Deep Technical Audit (defect sweep)

Audited: 8e4122f2 (v89) · 2026-10-05 · working tree dirty (uncommitted `docs/others/arch-audit.md` only; not read as code) · repository public (github.com/Experto-AI/quickscale) · prompt: deep-technical-audit v6

> **Re-run of:** the 2026-10-03 pass at `c10b529e` · **Delta swept:** `c10b529e..8e4122f2`
> (55 non-merge commits; 352 non-doc files, about +34k/−20k lines). The full diff did not fit the
> budget. It was read in §2f order; sampling is stated below.

---

## 1. Orientation summary

Archetype, stack, deployment realities, actors, crown jewels, configuration axes, tooling
baseline, and oracle items 1–13 are **unchanged from the 2026-10-03 pass** (`git show
c10b529e:docs/others/tech-audit.md`, §1). In brief: a Python 3.14 / Django project generator
and module workspace (Poetry monorepo). It has three realities: **R1** generator/CLI, **R2** the
generated internet-facing Django app (multi-tenant in `QUICKSCALE_ORGS_MODE=saas`; in solo mode every
user owns a personal org), and **R3** the OIDC release pipeline. The repository is public. Severity
concentrates in R2.

**What changed in this delta.**

- **SA216(a–c)** replaced account *deletion* with account **anonymization**. The account row is
  disabled and scrubbed. Every app that declares `anonymize_handlers` runs its own
  `anonymize_account` executor (auth, orgs, billing, blog, notifications) inside **one transaction**,
  while the org row locks and provider advisory locks are held. This is new code on a crown-jewel
  path (PII, cross-tenant data), and it was read in full.
- **SA214(a–f)** — devtools beta-migration / design-port oracle (R1, developer machine).
- **SA235/SA241** — manifest-declared module SPA routes (`SPA_MODULE_URLPATTERNS`).
- **SA236** — private module settings snapshots and guarded optional senders.
- **SA240** — `quickscale_orgs_create_site_org` management command.
- **SA238/SA234/SA242/SA243/SA231/SA233** — facade trims, a split-facade import gate (CI and
  publish), and quality-gate thresholds. These are process changes.

**Oracle addition.** 14. *Anonymization removes the person's identity and nothing else* (the
SA216 inventory, the `_anonymization.py` docstrings). It also preserves "another customer's event is
never touched" (billing) and "a short name cannot rewrite an unrelated word" (notifications).

**Data sensitivity.** Unchanged. This delta adds personal-data scrubbing over notification
messages, Stripe webhook payloads, invitations, author profiles, and sessions.

**Hotspots.** The delta replaces churn ranking. Fix-keyword commits in the delta are concentrated
in SA214(d) design-port review fixes (R1 only).

### Coverage statement

**Delta classification.** Every behavioral commit carries an SA ticket. Housekeeping commits are
the roadmap and audit rebalance commits. **No unreviewed-behavioral commit** was found. Merge
`21c73ea0` was not diffed with `--cc`.

*Read in full:* auth `views.py` removal entry (`form_valid` through `_anonymize_account`),
`_account_deletion_flow.py`, `_anonymization.py`; the `_anonymization.py` executors of orgs,
billing, blog, and notifications; the notifications send path (`services.py:86–134`,
`_delivery.py:83–98`); `quickscale_orgs_create_site_org`; the SA235 `urls.py.j2` /
`urls_modules.py.j2` diff; the `.github/workflows` diff (third-party actions remain SHA-pinned).

*Sampled:* the notifications anonymization tests (they cover escaped names and shared messages;
none covers a name that is a common word).

*Skipped:* SA214 devtools (R1 developer tooling), the CLI/DR split moves, the quality-script
changes, the React sources, and migrations.

*Audit tools:* git only. *Empirical checks (§1e):* the regex from notifications
`_redact_names` was copied into scratch and run on synthetic text. It **confirmed** that a
display name equal to a common word redacts that word in unrelated text. No project code was
executed.

*Category activation:* active: I, II, III, IV, VI, IX, X-generator, X-multi-tenant · inert: V (no
hot-path delta), VII (workflow diff is gates only), X-frontend (React not read) · produced: I, IV.

**Residual risk.** No PostgreSQL was exercised, so the full-scan timings in
`anonymize-full-table-scans-under-locks` are inferred, not measured. Devtools, the DR/CLI moves,
and React were not read this pass. Silence there means *not looked at*.

---

## 2. Machine-readable finding index

```yaml
schema: tech-audit/v6
audited: 8e4122f216824edb62134441a00f2413b3854653
items:
  - {id: notifications-anonymize-rewrites-all-messages, status: open, severity: S2, category: I,
     title: "Account anonymization redacts the person's name/username from every tenant's notification messages",
     effort: Small, confidence: High, reality: generated-app,
     anchors: [quickscale_modules/notifications/src/quickscale_modules_notifications/_anonymization.py],
     depends_on: [], chain: [anonymize-full-table-scans-under-locks], first_seen: 2026-10-05, last_verified: 2026-10-05}
  - {id: anonymize-full-table-scans-under-locks, status: open, severity: S3, category: IV,
     title: "Anonymization scans whole session/webhook/message tables inside the locked removal transaction",
     effort: Small, confidence: Medium, reality: generated-app,
     anchors: [quickscale_modules/auth/src/quickscale_modules_auth/_anonymization.py,
               quickscale_modules/billing/src/quickscale_modules_billing/_anonymization.py,
               quickscale_modules/notifications/src/quickscale_modules_notifications/_anonymization.py],
     fix_files: [quickscale_modules/auth/src/quickscale_modules_auth/_anonymization.py,
                 quickscale_modules/billing/src/quickscale_modules_billing/_anonymization.py,
                 quickscale_modules/notifications/src/quickscale_modules_notifications/_anonymization.py],
     depends_on: [notifications-anonymize-rewrites-all-messages], chain: [], first_seen: 2026-10-05, last_verified: 2026-10-05}
  - {id: billing-anonymize-name-substring, status: open, severity: S4, category: I,
     title: "Billing payload scrub replaces the name as a bare substring, including in dict keys", effort: Trivial,
     confidence: High, reality: generated-app,
     anchors: [quickscale_modules/billing/src/quickscale_modules_billing/_anonymization.py], first_seen: 2026-10-05, last_verified: 2026-10-05}
  - {id: notifications-account-username-dead, status: open, severity: S4, category: I,
     title: "_account_username is defined and never called", effort: Trivial, confidence: High, reality: generated-app,
     anchors: [quickscale_modules/notifications/src/quickscale_modules_notifications/_anonymization.py], first_seen: 2026-10-05, last_verified: 2026-10-05}
  - {id: dr-restore-vintage-exact-match, status: watchlist, category: I, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/dr_engine/recovery.py], first_seen: 2026-09-24, last_verified: 2026-10-05}
  - {id: orgs-provider-id-check-blocks-migrate, status: watchlist, category: VI, reality: generated-app,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/checks.py], first_seen: 2026-09-24, last_verified: 2026-10-05}
  - {id: crm-stage-seed-lost-on-commit-failure, status: watchlist, category: II, reality: generated-app,
     anchors: [quickscale_modules/crm/src/quickscale_modules_crm/receivers.py], first_seen: 2026-10-03, last_verified: 2026-10-05}
  - {id: orgs-disabled-in-saas-wedges-site, status: watchlist, category: VI, reality: generated-app,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/middleware.py], first_seen: 2026-10-03, last_verified: 2026-10-05}
```

---

## 3. Summary table

**Counts:** S1 — 0 · S2 — 1 · S3 — 1 · S4 — 2 · total 4 open.

| ID | Sev | Cat | Title | Effort | Conf | Since |
|---|---|---|---|---|---|---|
| `notifications-anonymize-rewrites-all-messages` | S2 | I | Anonymization redacts name/username across every tenant's messages | Small | High | new |
| `anonymize-full-table-scans-under-locks` | S3 | IV | Whole-table scans inside the locked removal transaction | Small | Medium | new |
| `billing-anonymize-name-substring` | S4 | I | Name replaced as a bare substring, keys included | Trivial | High | new |
| `notifications-account-username-dead` | S4 | I | Dead helper | Trivial | High | new |

---

## 4. Findings

### Finding 1: Account anonymization redacts the person's name and username from every tenant's notification messages

- **ID:** `notifications-anonymize-rewrites-all-messages`
- **Severity:** S2. High impact × Common reachability, with no unverified precondition. The trigger
  is any authenticated user removing their own account. Reality: R2, solo and saas alike, because
  `NotificationMessage` has no org field and no RLS. It violates oracle 14 ("a short name cannot
  rewrite an unrelated word").
- **Category:** I (correctness: wrong scope of a write). The secondary angle is integrity: the
  write crosses tenants.
- **Confidence:** High. The full path was read, and the redaction regex was confirmed in scratch
  (§1e).
- **Location:** `quickscale_modules/notifications/src/quickscale_modules_notifications/_anonymization.py:118–147`
  (`_scrub_messages`), `:376` (`_redact_names`). It is called from
  `quickscale_modules_auth/views.py:159` (`_anonymize_account`).
- **Defect:** `_scrub_messages` iterates **every** `NotificationMessage` in the database. Messages
  not delivered to the person still go through `_redact_message_identity`. That function replaces the
  person's full name and username wherever they appear as whole words, case-insensitively, in the
  subject, the text and HTML bodies, `last_error`, and `context_json`. The person's display name
  is user-editable (`forms.py:49`). Their username is user-chosen or derived from the email local
  part. Neither has a link to the rewritten message, so the identity match is the only selector.
- **Failure scenario:** held in the private companion (disclosure rule, public repository). In
  short: the person's display name or username coincides with ordinary text in other users'
  messages. Their own legitimate account removal then rewrites that text in every message in the
  system. Messages still pending or retrying are later sent from the rewritten fields
  (`_delivery.py:90–98`).
- **Evidence:** `for message in NotificationMessage.objects.all().iterator():` → `else:
  _redact_message_identity(message, ...)` (`:137–147`). See the private companion for the rest.
- **Refutation:** held in the private companion. Summary: the tests cover escaped names and shared
  invitation messages only (`tests/test_anonymization.py:103,141`). No guard bounds the selector
  by delivery, the message's org, or minimum name length. The docstring's word-boundary claim is
  true, and it does not prevent the defect.
- **Fix:** select the messages to redact by a link to the person, never by a scan. Use (a) messages
  with a delivery to the person (already computed as `person_message_ids`), and (b) messages
  whose `context_json` records the person as an actor. For (b), have `send_notification` callers
  store the actor's user pk (for example `actor_user_id`) and select on that. Run the name and
  username redaction only over that set. **Effort:** Small (Medium if (b) needs a context key
  added at the invitation call site).
- **Fix files:** `notifications/_anonymization.py`. Possibly also the orgs invitation send call
  site, to stamp the inviter's pk.
- **Depends on:** none.
- **Verification:** add a test with a second user's message containing a common word, plus a
  person whose first name is that word. After `anonymize_account`, the unrelated message is
  byte-identical. Keep the existing shared-invitation test passing.
- **Fix risk:** historical invitation messages sent before the actor key existed will no longer
  have the inviter's name scrubbed. Cover them with a one-time fallback limited to messages whose
  `context_json` names the person's *email*. The email is unique, unlike a name.
- **Detection signal:** `[redacted]` appearing in subjects or bodies of messages whose recipients
  never removed an account. Today nothing reports it, so instrument a count of rows rewritten per
  anonymization at INFO.
- **Deliberate?** Partly. The docstring intends "every stored message that carries the person's
  identity". The global name match is the unintended reach. Age: introduced in `3cffb168`
  (SA216(a), 2026-10-04). It is a recent regression and has never shipped in a release.

### S3

- **`anonymize-full-table-scans-under-locks`** · S3 (Moderate × Rare: it needs a large table) ·
  `auth/_anonymization.py:160–170` (every `django_session` row is decoded in Python),
  `billing/_anonymization.py:56` (every `WebhookEvent` payload is walked),
  `notifications/_anonymization.py:137` (every message). All three run inside the
  `transaction.atomic()` at `auth/views.py:151`, with org row locks and provider advisory locks
  held. Nothing in the generated project runs `clearsessions`, and webhook events and messages
  are retained, so all three tables only grow. Past roughly the gunicorn `--timeout 60`
  (`start.sh.j2:164`), the worker is killed after the Stripe cancellation stage has run. The
  `finally` compensation at `views.py:202–206` never executes, and every retry hits the same
  wall. Fix: filter sessions to `expire_date__gt=now()`. The scrubbed password already
  invalidates sessions through the session auth hash, so the delete is belt-and-braces. Pre-filter
  webhook events in SQL (`payload__icontains=email` on the JSONB text cast) before the Python walk.
  The notifications scan disappears with Finding 1's fix. Optionally ship a `clearsessions` cron
  note. Effort: Small. Confidence: Medium (timings are inferred, not measured). Depends on:
  `notifications-anonymize-rewrites-all-messages`.

### S4

- `billing-anonymize-name-substring` · `billing/_anonymization.py:149` · within the person's own
  webhook payloads, the name is replaced as a bare case-insensitive substring, in dict **keys**
  too (`_redact_identity` rewrites keys). A short name such as "Al" or "Id" mangles field names
  like `total` or `customer_id` and destroys the payload's structure. Fix: use the notifications
  word-boundary match, and leave keys alone.
- `notifications-account-username-dead` · `notifications/_anonymization.py:93` ·
  `_account_username` is never called (the username arrives as an argument). Fix: delete it.

---

## 5. Safeguard matrix

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

| ★ `AccountDeleteView` → anonymize boundary | `LoginRequiredMixin` | self only | form | autoescape | out of scope | **none**: whole-table scans under locks (`anonymize-full-table-scans-under-locks`) | compensating resume (lost on worker kill, same ID) | messages | INFO skip log |
| ★ Anonymize executors (write scope) | n/a | **notifications writes outside the person's records** (`notifications-anonymize-rewrites-all-messages`); orgs/blog/auth scoped by user FK; billing scoped by email | n/a | n/a | n/a | n/a | one transaction | n/a | none |
| ★ `quickscale_orgs_create_site_org` | shell (runtime role) | reserved-slug guard | field validators | n/a | n/a | n/a | `get_or_create` | `CommandError` | stdout |
| ★ SPA module routes (`SPA_MODULE_URLPATTERNS`) | static shell; data via the module APIs above | n/a | n/a | n/a | n/a | n/a | n/a | 404 handler | n/a |

Every empty cell carries a finding ID or a stated reason.

---

## 6. Fix order and batching

1. **Batch A (one PR):** `notifications-anonymize-rewrites-all-messages`, then the notifications
   part of `anonymize-full-table-scans-under-locks`, plus `notifications-account-username-dead`.
   All three are in the same file.
2. **Batch B (independent of A):** the auth session filter, the billing SQL pre-filter, and
   `billing-anonymize-name-substring`.

Land Batch A before the next release, because SA216 has not shipped yet.

---

## 7. Per-subsystem verdicts

- **auth (SA216)**: `anonymize-full-table-scans-under-locks`. The flow, recheck, and scrub were
  read in full. The lock/recheck logic is clean.
- **notifications**: `notifications-anonymize-rewrites-all-messages`,
  `notifications-account-username-dead`. Anonymization and the send path were read.
- **billing**: `billing-anonymize-name-substring` and part of the scan finding. Anonymization was
  read in full.
- **orgs**: clean. Anonymization, the create-site-org command, and the watchlist re-checks were
  read.
- **blog**: clean. Anonymization was read in full, and avatar deletion runs on commit with no raise.
- **core generator (SA235 URLs)**: clean.
- **pipeline (R3)**: clean. The workflow diff adds a gate job, and actions stay SHA-pinned.
- **devtools (SA214), CLI/DR moves, React**: not read (residual risk).

---

## 8. Clean sweeps and rejected candidates

- **Killed:** surviving sessions resuming the disabled account. `set_unusable_password` changes the
  session auth hash, and `is_active=False` is refused by the backend. Sessions die even under a
  cache session engine.
- **Killed:** a social-login account keeping PII after anonymization. allauth `socialaccount` is
  not installed anywhere in the auth module or templates.
- **Killed:** a scrubbed username colliding with another account. `_unused_scrubbed_username`
  probes for a free suffix.
- **Killed:** a pending invitation to or from the person stays redeemable. Orgs expires both
  directions (`orgs/_anonymization.py`).
- **Killed:** a blog avatar delete failing after commit and triggering a false compensation. The
  callback swallows and logs the error.
- **Verified:** a failing anonymize executor rolls the whole removal back. It runs inside
  `transaction.atomic()` (`views.py:151`), and `coordinator.finish()` fails closed.
- **Verified:** `create_site_org` refuses reserved slugs and validates field validators before
  `get_or_create`.
- Prior clean sweeps (auth-safeguard split sweep, raw-byte webhooks, secret projection, SA226
  isolation, lock release, build-time skip) are carried. This delta did not change their files'
  safeguards.

---

## 9. Structural smells

The five items from the prior pass are carried. One is added:

- Anonymization selects personal data by **matching identity strings** across shared tables,
  because notification messages and webhook payloads carry no user or org link. Every executor
  re-implements the email-token matcher: billing and notifications contain duplicate
  `_identity_form`/`_replace_addresses` functions. The structural decision is whether
  personal-data rows must carry an owner key (the SA242 inventory could require one).

---

## 10. Tooling gaps

- The prior gaps (image-layer and broader IaC scanning) are carried.
- Add an anonymization conformance test that runs every declared `anonymize_account` against a
  fixture with a **bystander** user whose rows contain the person's name as ordinary text, and
  asserts the bystander rows are unchanged. It would have caught
  `notifications-anonymize-rewrites-all-messages` and `billing-anonymize-name-substring`.

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

2026-10-05 evaluation: all four IDs **not fired**. The vintage check is still in `_restore.py`. The
orgs manual-adoption step is still listed in `module.yml`. The crm seed is still on-commit only
(`receivers.py:29`). The middleware still redirects to the hard-coded `/orgs/`. The carried
one-liners were not re-evaluated beyond a spot check (the Stripe client still sets no timeout).

---

## 12. Questions that would change severity

1. Do generated deployments run `manage.py clearsessions` (or does the host purge
   `django_session`)? If so, the session part of `anonymize-full-table-scans-under-locks` drops to S4.

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
