# Tech Audit — Codebase-Wide Defect Sweep

> **Audit date:** 2026-07-06 (re-run + module-by-module deep pass) · **Branch:** `v87` (HEAD `3056186a`)
> **Mode:** re-run against the SA19–SA33 remediation batch (every prior open finding
> re-verified, full delta since `a6706db1` deep-read), **followed by a module-by-module
> deep pass** (core → orgs → billing → forms → auth/backups → periphery) reading interiors
> the earlier passes only sampled: DR primitives/recovery, `module_wiring`, the generator
> and its deploy templates; orgs tenant-context save/restore, `TenantManager`, the
> last-owner model guards, the 1,273-line views, permissions; billing webhook idempotency
> and the credit-grant path; the forms public-submit serializer/validator chain. Prior IDs
> are stable; this document states **present reality for planning** —
> closed findings live only in the Reconciliation log at the bottom. Structural findings
> live in [arch-audit.md](arch-audit.md); fail-hard policy SSOT is
> [decisions.md §fail-hard-principle](../technical/decisions.md#fail-hard-principle).
> Remediation mapping this pass: TA21→SA23, TA22→SA24, TA24→SA21.1, TA31→SA29 (all
> resolved); TA17→SA20 (anchor resolved, residual narrowed); TA18→SA21.1 (settings half
> resolved, module half tracked as SA21.2).

## Orientation summary

QuickScale is a **Python 3.13 Django project generator** (Poetry monorepo: `quickscale_core`
manifest/apply/generator/DR engine, `quickscale_cli` Click CLI, 13 shipped `quickscale_modules/*`
Django apps + an empty `teams` placeholder, Jinja2 generator templates). Two deployment realities:
**(a)** the *generated project* — an internet-facing Django app targeting Railway (edge proxy →
gunicorn `--workers 1 --timeout 60`, non-root container, fail-closed runtime DB role, production
settings enforce HTTPS/HSTS/secure cookies, reject placeholder `SECRET_KEY`, and — new since
SA21.1 — ship trusted-proxy client-IP settings plus an active `CACHES` backend); **(b)** the
*CLI/generator* — a local developer tool. Trust boundaries: module HTTP surfaces in generated apps
(Stripe/notifications webhooks — signature-verified + idempotent; public form submit; blog/listings
token APIs; org invitations; admin backup/restore — now async-dispatched), then generator templates
(they *become* production config), then the CLI (destructive local ops, Railway deploy plumbing).
DRF baseline is fail-closed `IsAuthenticated`; tenant isolation is DB-level RLS (`SET LOCAL
app.current_org_id`, FORCE RLS, fail-closed `TenantManager → .none()`), with the SA14.5 split:
`operator_access` grants **read-only** cross-tenant visibility via a separate `FOR SELECT`
sub-policy. `QUICKSCALE_MODE` is now boot-guard-enforced (SA14.6). Tooling baseline: ruff
(E/W/F/I/N/UP/D) + strict mypy in CI; **no dependency-audit / bandit / semgrep / vulture step;
pylint duplication-only, not CI-wired**.

**Coverage (this pass):** read in full — backups admin restore dispatch flow (`admin.py`
restore/create/prune views, eligibility, staging seam), `backups_restore` management command,
backups `services.py`, migration `0005_backupartifact_restore_execution`, DR
`_persist_restore_artifact_metadata`; orgs `tenancy.py` (complete, incl. RLS templates and
policy-refresh derivation), operator-access GUC helpers in `current_org.py`, migrations
0005/0006, `apps.py` mode guard, adapters/middleware/views diffs; auth `views.py`
(`AccountDeleteView` complete) + `urls.py`; billing `cancel_current_subscription` + Stripe client
cancel wrapper; settings templates `base.py.j2`/`production.py.j2` diffs (client-IP helper,
NUM_PROXIES, CACHES) and `start.sh.j2`; storage manifest adapter in `entry_point.py`, storage
`module.yml`, README.md.j2 storage section, `module_wiring.py` `__QS_ENV__` rendering;
`resolvers.py`/`module_options.py`/`assembler.py`/`module_config.py`/`apply_command.py` force-path
/`railway_utils.py`/`dr_adapter_call.py`/`dr_commands.py`/`deployment_commands.py` diffs; blog
rate limiter + forms throttle + forms submit view; `analytics_tags.py`; orgs `debug_views.py`;
entry_point post-hooks (blog/listings/forms/notifications). Sampled — module admin
`TenantModelAdmin` port diffs (billing/blog/forms/listings), `module_catalog.py` delegate
removal, `runtime.py` re-export diff, listings/storage runtime helpers (re-verification), user-FK
`on_delete` extraction across all module models. Skipped — test bodies (except pytest-marker
confirmation), `htmlcov/`, `graphify-out/`, unchanged module interiors already deep-read
2026-07-05. Audit tools run: none available (`pip-audit`/`bandit`/`safety` not installed; installs
prohibited); dependency posture verified unchanged via git — `poetry.lock` untouched since
2026-06-17, module `pyproject.toml` changes are pytest markers only.

**Coverage (module-by-module deep pass, same day):** read in full — quickscale_core: DR
`primitives.py` (pg_dump/restore command building, `PGPASSWORD` via env dict, list-form
subprocess) and `recovery.py` (restore-source resolution — checksum + `PGDMP` magic + `pg_restore
--list` + PG18 version contract + `QUICKSCALE_BACKUPS_ALLOW_RESTORE` env gate, all chained before
execution), `module_wiring.py` (collect/render, `__QS_ENV__` substitution), `generator.py` (path
resolution, `poetry lock` subprocess, temp+move), `file_utils.py`, Dockerfile/start.sh/railway.json
templates. orgs: `current_org.py` (ContextVar + GUC save/restore in `_tenant_context`/`org_scope`,
the AF9 priming execute-wrapper with its atomic-identity memo, operator-access GUC), `managers.py`
(`TenantManager` fail-closed `.none()`, `OrganizationManager` system-org + personal-org creation
races), `models.py` (last-owner `save`/`delete` guards, both `select_for_update` on the Organization
row), `permissions.py`, `views.py` (invitation accept lock-guarded/email-matched, JSON API mixin
authz, member management), invitation token = uuid4. billing: `handle_stripe_event` idempotency and
`credit_user`/`_find_existing_credit_transaction` (DB unique constraint + savepoint rollback +
re-fetch — verified idempotent under concurrent duplicate delivery). forms: `serializers.py` +
`validators.py` (public-submit dynamic validation) + submit view. Sampled — auth adapters, backups
admin remaining views, social embed resolution (`contracts.py`), analytics capture catch,
notifications settings snapshot, purge_organization registry. **New finding from this pass: TA41**
(forms public-submit type-confusion 500).

**Clean sweeps worth recording:** no dangerous sinks in first-party core (`eval`/`exec`/`pickle`/
`yaml.load`/`shell=True`/weak-hash — none); DR subprocess calls list-form with `PGPASSWORD` in an
env dict; the guarded restore pipeline chains every check before `pg_restore`; billing webhook is
idempotent even though the dedup lock releases before processing (each handler is independently
idempotent via the `(stripe_event_id, transaction_type)` unique constraint + atomic
balance-delta-with-insert rollback); the orgs last-owner invariant is race-safe at the model layer
(Organization-row `select_for_update` in both `save` demotion and `delete`), so the unguarded
view-level owner pre-check is only UX; the tenant-context save/restore correctly restores both the
ContextVar and the DB GUC on exit (nested-scope safe); invitation acceptance is `select_for_update`
+ email-matched + terminal-state-gated. SA31 stdin transport correct on both ends (Railway `--stdin`
with forced `--skip-deploys`; `dr_adapter_call` reads stdin, argv path deprecated); SA22 force-path
is backup+swap+rollback with temp dirs cleaned on all paths; SA27 removals verified (orgs mode and
storage backend no longer silently coerce; assembler raises on validation issues; apply-gate calls
all five validators); SA19 start.sh prints set/MISSING only; SA14.6 boot guard rejects
missing/invalid `QUICKSCALE_MODE` on every startup path; SA14.2/14.3 admin `all_objects` escapes
replaced by `TenantModelAdmin`; the SA14.5 policy-refresh table-name derivation was checked against
every enrolled model's explicit `db_table` — all match the default convention, so no table is
silently skipped; RLS split-policy SQL grants operator SELECT only; fresh-DB ordering of the
refresh migrations is safe (module `enable_rls` migrations use the current shared template).

---

## Findings summary

| ID | Severity | Category | Title | Effort | Confidence | Status |
|----|----------|----------|-------|--------|------------|--------|
| TA33 | S2 | operability / correctness | Generated production app falls back to `DatabaseCache` but nothing ever runs `createcachetable` — every throttled endpoint (incl. public form submit) 500s on deployments without Redis | Trivial ⚡ | High | open (new) |
| TA34 | S2 | correctness / data loss | Self-service account deletion CASCADE-deletes org content: all blog posts authored by the user, all their CRM contact/deal notes, and their pending invitations — cross-org, RLS-bypassed | Small | High | open (new) |
| TA17 | S3 | operability | Admin backup **create/prune** still execute synchronously in the 60s-capped gunicorn worker (restore resolved by SA20) | Medium | High | open (narrowed) |
| TA18 | S3 | security / rate limiting | Module callsites still read raw `REMOTE_ADDR` behind the proxy: blog API limiter collapses to one bucket; `FormSubmission.ip_address` records the proxy (DRF half fixed by SA21.1; residual tracked as SA21.2) | Small | High | open (narrowed) |
| TA35 | S3 | security / correctness | `get_client_ip()` in generated settings is off-by-one: returns the proxy IP without spoofing and the **attacker-controlled** XFF entry with spoofing — a trap for SA21.2 | Trivial ⚡ | High | open (new) |
| TA36 | S3 | concurrency / data loss | Admin restore dispatch is check-then-act: no compare-and-swap on `STATUS_RESTORING`, child never re-verifies — two concurrent POSTs launch two `pg_restore --clean` on the same DB | Small | High | open (new) |
| TA37 | S3 | operability | A killed restore child (OOM, redeploy) strands `STATUS_RESTORING` forever; admin then permanently refuses retry; no staleness detection despite `restore_started_at` existing | Small | High | open (new) |
| TA38 | S3 | operability / fail-open | `operator_access()` never asserts an open transaction — `SET LOCAL` outside `atomic()` is a silent PostgreSQL WARNING no-op, so the operator's cross-tenant read silently returns tenant-scoped/empty rows | Trivial ⚡ | High | open (new) |
| TA41 | S3 | correctness / operability | Public form-submit 500s (uncaught `TypeError`) when any email/length/regex-validated field receives a non-string JSON value — the validator calls `re.match`/`len` on raw `request.data` | Small ⚡ | High | open (new) |
| TA25 | S4 | security hardening | Markdown `javascript:` link URIs survive escaping on public blog/listing pages | Small | Medium | open |
| TA32 | S4 | fail-open config | Listings/storage runtime settings reads silently default and coerce (TA2-class residuals) | Small | High | open |
| TA39 | S4 | correctness / error context | `AccountDeleteView._cancel_personal_org_subscriptions` swallows `BillingValidationError` unconditionally — "no subscription" and "subscription row missing its Stripe id" are indistinguishable | Trivial | High | open (new; arch-audit hand-off) |
| TA40 | S4 | fail-open config | `entry_point.py` post-hooks retain permissive coercion defaults for blog/listings/forms/notifications — the SA18.2/SA27 fail-open class, one layer down | Small | High | open (new; arch-audit hand-off, flagged twice) |

Counts: **S1: 0 · S2: 2 · S3: 7 · S4: 4.** Quick wins flagged ⚡ (Trivial/Small-effort S2/S3).
Resolved since the 2026-07-05 audit: **TA21, TA22, TA24, TA31** (see Reconciliation log).

---

## Findings detail — S2 (full blocks)

### TA33 (S2) — `DatabaseCache` fallback ships without its table: throttled endpoints 500 on no-Redis deployments

- **ID:** `generated-app-cache-table-missing` · **Category:** §4.VI operability / §4.I correctness · **Confidence:** High (mechanism read directly; runtime confirm = deploy without `REDIS_URL` and POST a public form)
- **Location:** `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/production.py.j2:254-268` (Redis when `REDIS_URL` set, else `DatabaseCache` on `django_cache_table`); `generator/templates/start.sh.j2:49` (runs `migrate`, never `createcachetable`); consumers: `quickscale_modules/forms/src/quickscale_modules_forms/views.py:193` (`throttle_classes = [FormSubmitThrottle]` on the public submit endpoint), `quickscale_modules/blog/src/quickscale_modules_blog/views.py:285-295` (blog API limiter).
- **Defect:** the SA21.1 remediation (TA24) activated a shared cache with a `DatabaseCache` fallback, but `django_cache_table` is not created by `migrate` — it requires `python manage.py createcachetable`, which no deploy artifact runs and no doc mentions. On a deployment without a Redis addon, every cache access raises `ProgrammingError: relation "django_cache_table" does not exist`. DRF's `SimpleRateThrottle.allow_request` does not catch cache errors, and the blog limiter's fallback tuple (`views.py:58`) is `(AttributeError, NotImplementedError, ValueError)` — no `DatabaseError` — so both raise through to a 500.
- **Failure scenario:** operator deploys the generated app to Railway without provisioning Redis (a supported configuration — the fallback exists precisely for it) → first visitor submits the public contact form → DRF throttle touches the cache → `ProgrammingError` → HTTP 500. The public form is 100% down, loudly, from the first request.
- **Evidence:** `production.py.j2` fallback block ends with a comment instructing `python manage.py createcachetable`; `grep createcachetable` across `start.sh.j2`, Dockerfile templates, README templates, and docs returns only that comment.
- **Fix:** add `RUNTIME_DATABASE_URL="" python manage.py createcachetable` to `start.sh.j2` after the migrate step (idempotent no-op when the table exists or when the Redis backend is active) — the cache table is DDL, so it needs the admin role like `migrate` does. Optionally add it to the README production checklist. **Effort:** Trivial ⚡.
- **Verification:** template test asserting `createcachetable` appears in rendered `start.sh` after `migrate`; e2e — boot the generated app with `REDIS_URL` unset and assert a form POST returns 201/429, never 500.
- **Deliberate?** None found — the template's own comment documents the requirement the deploy script doesn't fulfill; classic contract drift within one change (SA21.1).
- **Age:** introduced 2026-07-05/06 by the SA21.1 commit — a fresh regression surface; the fix is forward (the old commented-out CACHES was never active).

### TA34 (S2) — Account deletion CASCADE-destroys org content (blog posts, CRM notes, pending invitations)

- **ID:** `account-delete-cascade-content-loss` · **Category:** §4.I correctness / data loss · **Confidence:** High (FK rules read directly; PostgreSQL referential actions bypass RLS, so the cross-org cascade executes)
- **Location:** `quickscale_modules/blog/src/quickscale_modules_blog/models.py:276-282` (`Post.author` — `on_delete=CASCADE` with `null=True, blank=True`); `quickscale_modules/crm/src/quickscale_modules_crm/models.py:236-247` (`ContactNote.created_by` CASCADE) and `:277-288` (`DealNote.created_by` CASCADE); `quickscale_modules/orgs/src/quickscale_modules_orgs/models.py:286` (`OrganizationInvitation.invited_by` CASCADE); entry point: `quickscale_modules/auth/src/quickscale_modules_auth/views.py:51-102` (`AccountDeleteView`, routed at `auth/urls.py:19`, plain `LoginRequiredMixin` — any user).
- **Defect:** deleting a user account cascade-deletes every blog post they authored (drafts **and published**), every CRM contact/deal note they wrote, and every pending invitation they sent — across **all** organizations they belonged to. SA28 added last-owner and subscription guards to this exact view but nothing guards content. The rest of the codebase deliberately uses `SET_NULL` for user attribution (billing ×3, forms `created_by`, backups `initiated_by`, blog `uploaded_by`, CRM `owner`, membership `invited_by`) — these four are the outliers. `Post.author` is the strongest evidence of oversight: commit `dcd4103e` (2026-03-01, "support authorless posts") made it nullable — i.e., built the exact semantics `SET_NULL` needs — without changing `on_delete`.
- **Failure scenario:** a marketing hire authors 40 published posts and 200 CRM notes for a shared org, later leaves and deletes their account (self-service, no admin involved, no warning about content) → the org's public blog and customer history vanish unrecoverably. RLS does not intervene: FK referential actions are exempt from row-level security, so posts in orgs *outside* the deleter's context are destroyed too.
- **Evidence:** on-delete extraction across all module models (see Coverage); `AccountDeleteView.form_valid` guards ownership and billing only (`views.py:77-102`).
- **Fix:** migrate `Post.author`, `ContactNote.created_by`, `DealNote.created_by` to `on_delete=SET_NULL` (`Post.author` is already nullable; the CRM fields need `null=True` — display already tolerates it via `str(created_by)` → render "None"/"former member" in admin), and `OrganizationInvitation.invited_by` to `SET_NULL` or CASCADE-with-intent documented. One migration per module + the model edits. **Effort:** Small.
- **Verification:** test — create user, authored post + CRM note in a shared org, delete the account via the view, assert post/note survive with null attribution; regression asserting no remaining user-FK in `quickscale_modules_*` uses CASCADE except `OrganizationMembership.user` and the blog `AuthorProfile` OneToOne (both genuinely user-owned).
- **Deliberate?** None found for the blog/CRM CASCADE choice; the surrounding convention and the authorless-posts commit argue oversight. `OrganizationInvitation.invited_by` CASCADE (a pending invite disappearing with its sender) is defensible — treat it as a documented-intent decision rather than a bug. `OrganizationMembership.user` CASCADE and `AuthorProfile.user` CASCADE are correct and excluded.
- **Age:** long-standing (predates the audit cycle); *exposed* as consequential by SA28 making deletion a guarded, blessed flow — the guard list is simply incomplete.
- **Related race (secondary, S4):** the SA28 last-owner guard (`AccountDeleteView._get_blocking_orgs_for_deletion`, `views.py:112-153`) is a plain check-then-act with no `select_for_update` — unlike the model-level `OrganizationMembership.delete()` guard, which *is* Organization-row-locked. Because account deletion cascades memberships via bulk SQL (bypassing `Model.delete()`), the model guard never runs, and two co-owners of the same org deleting their accounts concurrently can each pass the view check and leave the org ownerless. Same code region as the primary fix; route account deletion through the locked path or add org-level locking.

---

## Findings detail — S3 (compact)

- **TA17** (`admin-backup-ops-sync-in-request`, S3, narrowed 2026-07-06) — SA20 moved **restore** to background dispatch, but `create_backup_view` (`backups/admin.py:356-366`, runs `pg_dump` + optional S3 upload in-request) and `prune_expired_backups_view` (`:368-378`) still execute inside the 60s-capped worker; a large-DB backup is SIGKILLed mid-dump (non-mutating, so no corruption — the admin just gets a 502 and no artifact). Fix: reuse the SA20 dispatch pattern for both. **Effort:** Medium · Confidence High. Dry-run staying synchronous is documented SA20 design.
- **TA18** (`throttle-remote-addr-behind-proxy`, S3, narrowed 2026-07-06) — SA21.1 fixed the DRF half (`NUM_PROXIES` wired, production defaults `USE_X_FORWARDED_FOR=True`/`TRUSTED_PROXY_COUNT=1`, so `FormSubmitThrottle` now resolves real client IPs). Still raw `REMOTE_ADDR`: blog API limiter ident (`blog/views.py:261-268` — all authenticated API clients share one bucket behind the proxy) and `FormSubmission.ip_address` forensics (`forms/views.py:231,257` — records the proxy). Known and tracked as **SA21.2** ("Unblocks SA21.2", CHANGELOG); the structural obstacle is that modules cannot import the generated-settings helper (see Structural smells). Fix per SA21.2 — but see TA35 first. **Effort:** Small · Confidence High.
- **TA35** (`get-client-ip-off-by-one`, S3) — the SA21.1 helper `get_client_ip()` (`base.py.j2:63-97`, duplicated in `production.py.j2`) extracts `ips[-(TRUSTED_PROXY_COUNT + 1)]` guarded by `len(ips) > TRUSTED_PROXY_COUNT`. Proxies put the direct peer in `REMOTE_ADDR`, never in XFF, so the client sits at `ips[-COUNT]` (DRF's own `NUM_PROXIES` math). With Railway's single hop: honest request → chain length 1 → guard fails → returns the **proxy IP** (collapse); request with attacker-supplied `X-Forwarded-For: fake` → chain `fake, client` → returns **`fake`** (spoofable ident/forensics). Currently zero consumers (dead in generated settings), but it ships in every project as the documented canonical helper and is the designated foundation for SA21.2 — wiring it as-is converts TA18 from "collapsed" to "attacker-controlled". Fix: `ips[-TRUSTED_PROXY_COUNT]` with `len(ips) >= TRUSTED_PROXY_COUNT`, plus a template test mirroring DRF semantics (fixed `REMOTE_ADDR`, spoofed + honest XFF). **Effort:** Trivial ⚡ · Confidence High (standard XFF-append behavior; confirm Railway's exact header handling at runtime).
- **TA36** (`admin-restore-dispatch-toctou`, S3) — restore dispatch is check-then-act: eligibility rejects `STATUS_RESTORING` (`backups/admin.py:776-780`) but the transition is a plain `.save()` (`:510-525`, `:646-661`) with no compare-and-swap, and the child command never re-verifies it holds the claim (`backups_restore.py:106-116` proceeds regardless of status). Two admin POSTs in the same window → two concurrent `pg_restore --clean` interleaving drops/creates on the production DB. Narrow window, catastrophic outcome. Fix: `BackupArtifact.objects.filter(pk=..., status__in=<eligible>).update(status=RESTORING, ...)` and abort dispatch when 0 rows; child asserts `status == RESTORING` for artifact-id runs. **Effort:** Small · Confidence High. Chains with TA37 (a stuck duplicate makes recovery murkier). Ticket-shaped child of arch-audit `backups-admin-orchestration-accretion`.
- **TA37** (`restore-status-stranded-no-staleness`, S3) — the child records `STATUS_FAILED` only on Python exceptions (`backups_restore.py:132-153`); a SIGKILL (OOM during a big restore, container redeploy) strands `STATUS_RESTORING` forever. The admin then *permanently refuses retry* ("Wait for the restore to complete…", `admin.py:776-780`) and no code reads `restore_started_at` for staleness — the operator must hand-edit the DB, mid-incident, with the database possibly half-restored. Fix: surface staleness in the admin (e.g. `restore_started_at` older than a threshold ⇒ "stale — child likely dead" + a guarded reset-to-FAILED action); optionally record the child PID for a liveness probe. **Effort:** Small · Confidence High. (The known CR-SA20-007 metadata-rollback gap is adjacent but separately tracked — see Notes.)
- **TA38** (`operator-access-silent-noop-outside-atomic`, S3) — `operator_access()` / `_set_operator_access()` (`orgs/current_org.py:601-618, 621-682`) run `SET LOCAL` without asserting `connection.in_atomic_block`. Outside a transaction PostgreSQL emits only a WARNING and the GUC is not set, so the elevation silently doesn't happen: the operator's cross-tenant read returns tenant-scoped or empty rows and the audit log *still records a successful activation*. Fail-closed for isolation (good) but a textbook silent-fallback under §fail-hard-principle, on an API whose docstring documents the precondition it doesn't enforce — and Django's default is autocommit, so forgetting `atomic()` is the natural mistake. No first-party callers yet (operator/shell surface), which is exactly when a loud error matters most. Fix: raise `ImproperlyConfigured`/`RuntimeError` when `not connection.in_atomic_block` (same for the paired GUC read). **Effort:** Trivial ⚡ · Confidence High.
- **TA41** (`forms-submit-nonstring-value-500`, S3) — the public form-submit validator assumes every submitted value is a string. `FormSubmissionCreateSerializer.to_internal_value` (`forms/serializers.py:163-165`) does `return dict(data)` with no per-value coercion, then `validate()` calls `re.match(email_pattern, submitted_value)` (`:193`) for email fields, and `make_field_validator` runs `len(value)` / `re.match(pattern, value)` (`validators.py:24,29,34`) for any field carrying length/regex `validation_rules`. DRF's JSON parser yields native types, so a non-string value (`{"email": ["x"]}`, `{"email": 123}`, `{"field": {"a":1}}`) raises `TypeError` — **not** `serializers.ValidationError` — which `serializer.is_valid()` (`views.py:246`) does not catch, so it propagates to a 500. The endpoint is unauthenticated (`forms/views.py` public submit) and needs no honeypot. Failure scenario: any anonymous client POSTs a JSON body with an array/number where a validated field expects a string → HTTP 500 (and, per TA33, on a no-Redis deployment the throttle can't even rate-limit the flood). Fix: reject or `str()`-coerce non-string scalars at the top of `validate()` (return a 400 "must be text" per field), and guard `int(min_length)`/`int(max_length)` against non-numeric `validation_rules`. **Effort:** Small ⚡ · Confidence High. Secondary (S4, staff-authored): the `regex` rule feeds `re.match` with a staff-supplied pattern against public input — a catastrophic-backtracking pattern is a latent ReDoS (same trust class as TA25).

## Findings detail — S4 (one line each)

- **TA25** — `blog/views.py:787` + `listings/views.py:304-306` → `|safe` templates: `markdownify(escape(...))` neutralizes raw HTML but not markdown `[x](javascript:…)` link URIs (staff/token-gated authoring; defense-in-depth). Fix: sanitize rendered HTML (`nh3`/`bleach`, allow http(s)/mailto schemes only).
- **TA32** — `listings/views.py:39-52` (`_get_positive_int_setting` silently defaults) and `storage/helpers.py:44-56` (`_read_setting` defaults; `_normalize_backend` unknown → `"local"`): runtime fail-open residuals of the TA2 class; low-stakes while SA27 guarantees valid baked literals, live under hand-edited settings. Fix: SA17-pattern direct required reads.
- **TA39** — `auth/views.py:212-213`: `except (BillingDisabledError, BillingValidationError): pass` conflates the benign "no current subscription" with "subscription row exists but has no Stripe id" (`billing/services.py:740-749` raises both as `BillingValidationError`) — the latter deletes the account while an unresolved subscription row (and possibly a live Stripe subscription) remains. Stripe API failures do propagate (fail-hard ✓). Fix: distinguish the no-subscription case (dedicated exception or pre-check) and let/log the missing-id case. (Arch-audit red-flag hand-off.)
- **TA40** — `manifest/entry_point.py:386-390` (blog: `POSTS_PER_PAGE`→10, `ENABLE_RSS`→True, empty rate→`"5/hour"`), `:451` (listings→12), `:520-531` (forms: five defaults incl. `SPAM_PROTECTION`→True), `:898-921` (notifications: `ENABLED`→True, TTL→300): post-hook `settings.get(key, default)` coercions second-guess SA27-validated input — dead today, but the permissive default is what executes on any upstream resolver regression, reopening the TA2/TA19/TA26 class silently. Fix: direct required reads (`settings["KEY"]`), fail loud, matching the SA18.2 analytics-hook purge. (Arch-audit red-flag hand-off, flagged twice; collapsed class — 4 locations listed.)

---

## Structural smells (candidates for `arch-audit.md`)

- **Client-IP knowledge has no importable seam (TA18/TA35):** the canonical resolution lives in *generated settings* (a Jinja template), but the consumers that still need it (blog limiter, forms attribution) live in installed packages that cannot import the generated project's settings module by name. SA21.2 will either duplicate the logic per module or need a shared runtime helper (e.g. an orgs/core utility reading `USE_X_FORWARDED_FOR`/`TRUSTED_PROXY_COUNT` via `django.conf.settings`). Decide the seam before SA21.2, or the off-by-one class (TA35) gets three copies.
- **Backups admin as orchestration engine (TA36/TA37):** already opened as arch-audit `backups-admin-orchestration-accretion`; these two findings are its ticket-shaped children — the CAS transition and staleness detection are properties a restore-attempt *entity* would own naturally.
- **Deletion invariants enforced per boundary (TA34):** already opened as arch-audit `deletion-invariants-per-boundary-reimplementation`; TA34 adds content-cascade evidence — the view-level guard list (owners, subscriptions) cannot enumerate every consequence the schema encodes; delete-rule conventions (`SET_NULL` for attribution) belong at the model layer with a conformance test.
- **No single "how does a generated app get configured at deploy time" contract:** carried — SA29 fixed the storage instance; TA33 is a fresh instance of the same drift (a settings template acquiring a runtime prerequisite that no deploy artifact fulfills). A generator-wide rule ("every settings-template requirement must map to a start.sh/README step, asserted by a template test") would close the class.

## Tooling gaps

- **`pip-audit`/`safety` CI step** — no dependency-CVE gate; the lockfile read stays manual and low-confidence. (Dependency class, ongoing.)
- **`bandit`/`semgrep` CI step** — would systematically catch the TA25 class (`|safe`/`mark_safe` on non-constant) and argv/redirect classes as they recur.
- **Generated-project boot smoke test** — render + boot the generated app in CI with *minimal* env (no `REDIS_URL`) and hit one throttled endpoint; would have caught TA33 and any future settings-template/deploy-script drift.
- **Delete-rule conformance test** — assert every user-FK in `quickscale_modules_*` uses `SET_NULL`/`PROTECT` unless allowlisted; prevents TA34 recurring as modules land (teams!).
- **Public-endpoint fuzz/negative test on form submit** — POST non-string JSON value types (array, number, object, null) at the public submit endpoint and assert 400, never 500; would have caught TA41 and guards the dynamic-validation surface as field types grow.
- **Apply-gate completeness check** — CI assertion that every exported `validate_*_module_options` is invoked on the apply path — now landed for the five modules (SA27); extend to fail on *post-hook* `.get(key, default)` patterns to close TA40's class.
- **Settings-contract system check** — startup assertion for required `QUICKSCALE_*` settings: landed for orgs (SA14.6); TA32's listings/storage residuals would be closed by the same pattern.

Categories swept with no qualifying finding this pass: injection sinks (stdin JSON transport verified), deserialization, crypto misuse, SSRF/open-redirect (SA23 verified fixed), resource leaks (temp dirs cleaned on all apply paths; Popen without wait leaves at most one transient zombie per rare restore — not consequential), timeouts, N+1/perf, import-time side effects, dependency CVEs (lockfile unchanged; low confidence without a scanner).

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
- 2026-07-06 (re-run, HEAD `3056186a`) — **TA21: resolved** (SA23, `531386d9`/`20f01b88` — both debug views validate `next` via `url_has_allowed_host_and_scheme` against `request.get_host()`). **TA22: resolved** (SA24, `ba2c62da` — analytics JSON payload escapes `<`/`>`/`&` before `mark_safe`). **TA24: resolved** (SA21.1 — production `CACHES` active: Redis via `REDIS_URL`, `DatabaseCache` fallback — but the fallback's bootstrap gap opened as **TA33**). **TA31: resolved** (SA29, `4d1832fe` — credentials via `*_env_var` indirection, `__QS_ENV__` markers rendered as `os.environ.get()` with no credential material at rest, README rewritten to the real contract, cloud-backend env-var references validated at the apply gate; verified end-to-end adapter→wiring→template). **TA17: still-open, narrowed** to create/prune (restore async since SA20; severity S2→S3). **TA18: still-open, narrowed** to module callsites (DRF half fixed by SA21.1; residual is tracked SA21.2; severity S2→S3). **TA25, TA32: still-open** (locations re-verified unchanged). **TA33–TA40: opened this pass** (TA33/TA35 are regressions-in-shape from SA21.1's new code; TA36/TA37 from SA20's new lifecycle; TA34 long-standing, exposed by SA28's guarded flow; TA39/TA40 accepted from arch-audit red-flag hand-off after independent verification).
- 2026-07-06 (module-by-module deep pass, core and cli included as modules) — **TA41 opened** (forms public-submit `TypeError`→500 on non-string JSON values, found reading the serializer/validator chain in full). Modules read deeply and found clean this pass: quickscale_core (DR primitives/recovery restore gate, module_wiring, generator + deploy templates — no dangerous sinks), orgs (tenant-context save/restore, `TenantManager`, last-owner model guards race-safe via Organization-row lock, invitation accept, permissions), billing (webhook idempotency + credit-grant unique-constraint rollback verified idempotent under concurrent duplicate delivery). Secondary items recorded inside existing findings rather than as new IDs: the concurrent-account-deletion last-owner race (folded into TA34), the staff-authored ReDoS via form-field `regex` rules (folded into TA41), and the staff-authored unvalidated YouTube/TikTok embed-id interpolation (`social/contracts.py:235,251` — same trust class as TA25, React-escaped at the sink, not promoted).

## Notes (not violations, watch items)

- **CR-SA20-007 (tracked, blocking SA20 closeout per CHANGELOG):** the spawn-failure rollback in the admin dispatch restores `status` but not pre-spawn `restore_started_at`/`restore_error` when retrying a previously FAILED/RESTORED artifact — prior failure forensics are lost if `Popen` raises. Known, documented, already in the team's CR queue; not re-opened here (would otherwise be an S4). TA36/TA37 should land in the same code region.
- **Storage legacy-credential conversion is deliberate:** `normalize_storage_module_options` silently pops literal `access_key_id`/`secret_access_key` and substitutes default env-var references — CHANGELOG documents this as the SA29 migration behavior ("silently converted"), and the failure is loud at first upload if the env vars are unset. Watch: a one-line apply-time notice would improve the upgrade story, but this is a chosen trade-off, not a defect.
- `orgs/public_context.py:140-144`: `except Exception: return None` on system-org lookup is **fail-closed** (tenant managers return `.none()`) — isolation preserved, but a DB-level error renders as "no data" instead of a 500; consider letting non-`DoesNotExist` errors propagate.
- DR engine fallback modes (`REMOTE_FALLBACK`, JSON fallback backups, `QUICKSCALE_ENVIRONMENT` default `local`) are by-design recovery behavior, exempt per §fail-hard-principle; the SA20 admin path correctly forces `LOCAL_ONLY` (CR-SA20-006 verified).
- Analytics runtime missing-API-key → silent disable (`services.py:215-216`) is the deliberate SA17.7 shape — chosen trade-off, tested.
- `subprocess.Popen` in the restore dispatch is never `wait()`ed — at most one transient zombie per restore until the worker's next subprocess call or recycle; harmless at this frequency, noted for completeness.
