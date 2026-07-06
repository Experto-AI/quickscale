# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks pending roadmap work. Detailed completed implementation history is in [CHANGELOG.md](../../CHANGELOG.md). Each phase is sized as Adaptive Tier 1–2; split before implementing if a checklist item is Tier 3.

**Rules:**
- Keep open todo items here.
- Move detailed completed implementation history to CHANGELOG.md.
- Each open phase links back (`why →`) to the finding that justifies it.

---

## Parallel Execution Tracks

Work is split across 3 git worktrees that develop in parallel and merge back to `v87` after each phase. `v87` is the clean integration branch — never commit directly to it.

### Start procedure

Run at the beginning of every new phase, before touching any files:

```bash
cd /home/victor/code/quickscale-wt-track{N}
git status             # must be clean — commit or stash any in-progress work first
git merge v87          # pull in everything other tracks have merged since last sync
# resolve any conflicts, then continue with the phase
```

### Merge procedure

Run when a phase (or a full milestone) is complete and ready to integrate:

```bash
cd /home/victor/code/quickscale-wt-track{N}
git merge v87          # sync latest before merge-back; resolve conflicts here
# run phase verification tests
cd /home/victor/code/quickscale
git merge --no-ff wt-track{N}
```

> **Shared closeout files (`CHANGELOG.md` and `docs/technical/roadmap.md`):** Because every track touches these files, they are the most likely source of merge conflicts. The procedure above already handles this — the `git merge v87` before merge-back ensures you resolve any conflicting entries on your track branch rather than on `v87`. Do not skip or reorder that step. When resolving, keep both tracks' entries (don't overwrite another track's completed work).

---

## Open work

> **Closed batches (detail in [CHANGELOG.md](../../CHANGELOG.md)):** SA1–SA5 (2026-07-02), SA6–SA12 (2026-07-03), SA13.1–SA13.4 (2026-07-04), SA14.1–SA14.6 (2026-07-05), SA15.1–SA15.3 (2026-07-04), SA16.1/SA16.2 (2026-07-03), SA17.1–SA17.8 (2026-07-05), SA18.1–SA18.11 (2026-07-04), SA19 (2026-07-05), SA20 (2026-07-06), SA21.1 (2026-07-05), SA22 (2026-07-05), SA23 (2026-07-05), SA24 (2026-07-05), SA25 (2026-07-05), SA26 (2026-07-06), SA27 (2026-07-05), SA28 (2026-07-05), SA29 (2026-07-05), SA30 (2026-07-06), SA31 (2026-07-05), SA32 (2026-07-06), SA33 (2026-07-05), SA39 (2026-07-06). All closed per template rule — detail lives in CHANGELOG.md.

> **Triage note (2026-07-06):** the previously-deferred triage against [tech-audit.md](../others/tech-audit.md) (TA33–TA41 new/narrowed this pass) and [arch-audit.md](../others/arch-audit.md) (Findings 1–5) is done. SA34–SA47 below are the resulting fix items, each sized Tier 1–2 (arch-audit's larger Findings 1/2/4/5 are cut down to their recommended *first step* only — later stages are explicitly deferred, matching the source docs' own "recommended first stage" framing). One doc-drift note: tech-audit's summary table still lists **TA32 as open**, but the code (`listings/views.py`, `storage/helpers.py`) already raises `ImproperlyConfigured` per SA30 — verified directly. Treating TA32 as closed (per roadmap's existing SA30 entry); no new item created for it. tech-audit.md itself is left untouched by this pass — only roadmap.md is updated here.

> **Track status (2026-07-06):** Track 1 — **3 open items** (SA35, SA41, SA47). Track 2 — **5 open items** (SA21.2 ready; SA43, SA37, SA38 chained; SA40 independent). Track 3 — **5 open items** (SA34, SA36, SA42, SA44, SA46). SA39 completed.

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)          Track 2 (module contracts & settings)       Track 3 (core/CLI plumbing)
───────────────────────────────           ───────────────────────────────────         ───────────────────────────
SA39 (deps: none)                         SA43 (deps: none)                           SA34 (deps: none)
SA35 (deps: none)                         SA21.2 (deps: SA21.1 complete, SA36*)       SA36 (deps: none) ─────┐
SA41 (deps: none)                         SA37 (deps: SA43)                           SA46 (deps: none)      │
SA47 (deps: SA35, SA41 — soft sequence)     SA38 (deps: SA43)                           SA44 (deps: none)      │
                                                                          SA42 (deps: none)      │
                                                 ▲                                                            │
                                                └───────────────────── * cross-track: SA36 → SA21.2 ─────────┘
```

Cross-track dependency: SA21.2 (Track 2) should not wire module consumers to the generated `get_client_ip()` helper until **SA36** (Track 3) fixes its off-by-one — otherwise SA21.2 ships the attacker-controlled variant of TA18 that TA35 warns about. This mirrors the existing SA21.1 → SA21.2 pattern (settings landed by Track 3, consumed by Track 2). All other listed deps are same-track, same-file sequencing (noted per item below) rather than hard blockers, since each track's worktree processes one item at a time anyway. Rebalancing history (2026-07-05/06, preserved for context): SA24/SA29/SA30 moved Track 2 → Track 1 and SA32 moved Track 2 → Track 3 to restore 3/3/2 parallelism when Track 2 was carrying six open items; SA26 then moved Track 2 → Track 3 for 1/2/1 parallelism. All of those items are now complete; this triage pass restores 5/5/5 parallelism by assigning SA34–SA47 across the three tracks.

### Track 1 — Tenant-context surface

#### Finding — `operator-access-silent-noop-outside-atomic` (`why →` [TA38](../others/tech-audit.md))

- [x] **SA39 — Fail hard when `operator_access()` is invoked outside an open transaction.** `Tier 1 · Track 1 · deps: none`
  `SET LOCAL` outside `atomic()` is a silent PostgreSQL WARNING no-op — `operator_access()`/`_set_operator_access()` currently don't assert `connection.in_atomic_block`, so a caller who forgets `atomic()` gets a silently tenant-scoped/empty cross-tenant read while the audit log still records a successful activation. Raise `ImproperlyConfigured`/`RuntimeError` in that case (both the GUC set and the paired GUC read).
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/current_org.py:601-618,621-682`.
  *Acceptance:* calling `operator_access()` outside `atomic()` raises immediately with a clear message; calling it inside `atomic()` behaves exactly as before (existing tests pass); add a regression test for the outside-atomic case.

#### Finding — `org-model-universe-hand-enumerated` (`why →` [arch-audit.md Finding 4](../others/arch-audit.md), first step only)

- [x] **SA45 — Derive the purge-spec completeness test from the tenant-classification universe instead of a second hand-written model list.** `Tier 1 · Track 1 · deps: none`
  `purge_organization`'s `_DELETE_SPECS` registry is validated by a test whose `expected_models` is a *third* hand-written copy of the same universe — it derives nothing, so a new tenant model fails neither the registry nor the test. Compute the test's expected model set from the marker-derived tenant tables (org-FK-bearing concrete models) instead. Full derivation of the purge plan itself (arch-audit Option 2) is out of scope — this is the cheap completeness-gate step only.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/management/commands/purge_organization.py:64-212`, `quickscale_modules/orgs/tests/test_management_commands.py:1281-1332`.
  *Acceptance:* the completeness test computes its expected model set from the tenant-classification universe rather than a hand-written literal; a new tenant model added without a matching `_DELETE_SPECS` entry now fails CI instead of passing silently.

#### Finding — `account-delete-cascade-content-loss` (`why →` [TA34](../others/tech-audit.md))

- [ ] **SA35 — Stop account deletion from CASCADE-destroying org content across organizations.** `Tier 2 · Track 1 · deps: none`
  `Post.author`, `ContactNote.created_by`, `DealNote.created_by` are `on_delete=CASCADE` — deleting a user destroys every blog post they authored (drafts **and published**) and every CRM note they wrote, across all orgs they belonged to; RLS does not intervene because FK referential actions bypass it. Migrate all three to `SET_NULL` (`Post.author` is already nullable; the CRM fields need `null=True` added — display already tolerates `None`). Decide and document `OrganizationInvitation.invited_by`'s CASCADE (defensible as intentional — a pending invite disappearing with its sender) rather than changing it silently.
  *Files:* `quickscale_modules/blog/src/quickscale_modules_blog/models.py:276-282`, `quickscale_modules/crm/src/quickscale_modules_crm/models.py:236-247,277-288`, `quickscale_modules/orgs/src/quickscale_modules_orgs/models.py:286`.
  *Acceptance:* create a user, author a post + CRM note in a shared org, delete the account via `AccountDeleteView`, assert the post/note survive with null attribution; add a delete-rule conformance test asserting every user-FK in `quickscale_modules_*` is `SET_NULL`/`PROTECT` unless allowlisted (`OrganizationMembership.user`, blog `AuthorProfile.user`).

#### Finding — `account-delete-billing-exception-swallowed` (`why →` [TA39](../others/tech-audit.md))

- [ ] **SA41 — Distinguish "no subscription" from "subscription row missing its Stripe id" in account-delete billing cleanup.** `Tier 1 · Track 1 · deps: none`
  `AccountDeleteView._cancel_personal_org_subscriptions` does `except (BillingDisabledError, BillingValidationError): pass` unconditionally — the benign "no current subscription" case and "subscription row exists but has no Stripe id" (which leaves an unresolved subscription behind after deletion) are indistinguishable. Distinguish them with a dedicated exception or a pre-check, and log/surface the missing-id case instead of silently passing.
  *Files:* `quickscale_modules/auth/src/quickscale_modules_auth/views.py:212-213`, `quickscale_modules/billing/src/quickscale_modules_billing/services.py:740-749`.
  *Acceptance:* deleting an account with no subscription proceeds silently as today; deleting an account whose subscription row is missing a Stripe id logs/surfaces the anomaly instead of silently passing; Stripe API failures continue to propagate (unchanged fail-hard behavior).

#### Finding — `deletion-invariants-per-boundary-reimplementation` (`why →` [arch-audit.md Finding 2](../others/arch-audit.md), first step only)

- [ ] **SA47 — Move the last-owner deletion-blocking check into orgs as the single implementation.** `Tier 2 · Track 1 · deps: SA35, SA41 (soft sequence — same files, land after to avoid rebasing onto still-changing exception handling)`
  Two divergent implementations of "never remove the last owner" exist today: `OrganizationMembership.delete()` (lock-guarded, unconditional) and `AccountDeleteView._get_blocking_orgs_for_deletion` (unlocked check-then-act, "allowed when no other members"). Move the check into orgs as the canonical implementation, pick one semantic, and make `AccountDeleteView` call it. Full Option 1 (orgs-owned deletion service, `pre_delete` receiver backstop for every ORM path, billing seam integration) is out of scope for this phase — this is the first step only.
  *Files:* `quickscale_modules/auth/src/quickscale_modules_auth/views.py:112-153`, `quickscale_modules/orgs/src/quickscale_modules_orgs/models.py:231-252`.
  *Acceptance:* a single last-owner rule lives in orgs; both call sites (the model delete guard and `AccountDeleteView`) use it; existing SA28 tests pass against the unified implementation, plus a new concurrent-deletion test (two co-owners of the same org deleting accounts concurrently cannot both pass and leave the org ownerless).

#### Finding — `operator-read-path-undefined` (`why →` [arch-audit.md reconciliation log](../others/arch-audit.md#reconciliation-log-append-only))

> **SA14 — complete.** SA14.1–SA14.6 (TenantModelAdmin base, CRM/blog/forms/listings/billing admin ports, NOBYPASSRLS default for module test suites, operator_access RLS predicate, QUICKSCALE_MODE fail-hard) merged. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `debug-view-open-redirect` (`why →` [TA21](../others/tech-audit.md))

> **SA23 — complete.** Validated the `next` redirect target in orgs debug views with `url_has_allowed_host_and_scheme`. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `account-delete-cascade-bypasses-org-invariants` (`why →` [TA30](../others/tech-audit.md))

> **SA28 — complete.** Enforced the last-owner and personal-org invariants at the account-deletion boundary via an `AccountDeleteView.form_valid` override; cancels the personal org's active subscription through the existing billing seam before deletion. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `analytics-tags-mark-safe-unescaped` (`why →` [TA22](../others/tech-audit.md))

> **SA24 — complete.** Escaped the analytics template tag payload before `mark_safe`, making `</script>` inert in page source. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `storage-config-dead-env-docs-secrets-in-vcs` (`why →` [TA31](../others/tech-audit.md))

> **SA29 — complete.** Storage credential options converted to env-var indirection (`*_env_var` pattern), matching analytics/notifications/billing/backups; generated `settings/modules.py` contains no credential material. CR-SA29-002 (README doc gap re: `media_url`) accepted as non-blocking and closed with the merge. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `listings-storage-runtime-fail-open-residuals` (`why →` [TA32](../others/tech-audit.md))

> **SA30 — complete.** Applied the SA17 direct-required-read pattern to listings/storage runtime settings — `listings/views.py`'s page-size read and `storage/helpers.py`'s backend normalization now raise `ImproperlyConfigured` on missing/invalid values instead of silently defaulting or coercing. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

### Track 2 — Module contracts & settings

#### Finding — `forms-submit-nonstring-value-500` (`why →` [TA41](../others/tech-audit.md))

- [x] **SA40 — Reject non-string values on public form submit instead of 500ing.** `Tier 1 · Track 2 · deps: none`
  The public form-submit validator assumed every submitted value is a string: `to_internal_value` does `dict(data)` with no per-value coercion, then `validate()`/`make_field_validator` call `re.match`/`len` on the raw value for any field with length/regex validation rules. DRF's JSON parser yields native types, so a non-string value (`123`, `["x"]`, `{"a":1}`) raised an uncaught `TypeError` — not a `ValidationError` — 500ing an unauthenticated endpoint. Public validation now rejects non-string payloads with 400 errors and rejects malformed `validation_rules` before per-value enforcement.
  *Files:* `quickscale_modules/forms/src/quickscale_modules_forms/serializers.py:163-165,193`, `quickscale_modules_forms/validators.py:24,29,34`.
  *Acceptance:* POSTing array/number/object/null values for a validated field returns 400, never 500; existing valid-string submissions unaffected; add a negative-test sweep for those JSON value types at the public submit endpoint.
  *Findings / Blockers:* No blockers.

#### Finding — `backups-admin-orchestration-accretion` (`why →` [arch-audit.md Finding 3](../others/arch-audit.md), first step only)

- [ ] **SA43 — Extract the async-restore dispatch lifecycle out of `backups/admin.py` into a single service function.** `Tier 2 · Track 2 · deps: none`
  The SA20 async-restore lifecycle (status write → `Popen` spawn → atomic claim → spawn-failure rollback) exists as two inline copies (recorded-artifact and uploaded-file dispatch branches), duplicating every subsequent fix (CR-SA20-005 through 008, REV-001/002 each needed a paired fix). Lift the recorded-artifact branch's lifecycle block into `dispatch_background_restore(artifact, *, confirmation) -> None` in `services.py`; make the uploaded-file branch call the same function.
  *Files:* `quickscale_modules/backups/src/quickscale_modules_backups/admin.py:380-742` (both dispatch branches), `services.py`.
  *Acceptance:* existing CR-SA20-007/REV-002 regression tests pass against the extracted function; both admin dispatch branches call the same service function with no behavior change; the admin view is left doing form handling and messaging only for this flow.

#### Finding — `backups-sync-restore-blocks-worker` (`why →` [TA17](../others/tech-audit.md), narrowed to create/prune)

> **SA20 — complete** (restore). Moved admin-triggered backup restore off the synchronous request path via async `subprocess.Popen` dispatch, with an atomic compare-and-swap claim, spawn-failure rollback preserving prior failure metadata, and forced `--local-only` resolution (CR-SA20-005 through CR-SA20-008, CR-SA20-REV-001/002 resolved). Full detail in [CHANGELOG.md](../../CHANGELOG.md).

- [ ] **SA37 — Move admin backup create/prune off the synchronous request path.** `Tier 2 · Track 2 · deps: SA43`
  `create_backup_view` (runs `pg_dump` + optional S3 upload in-request) and `prune_expired_backups_view` still execute inside the 60s-capped gunicorn worker — a large-DB backup can be SIGKILLed mid-dump (non-mutating, so no corruption, but the admin gets a 502 and no artifact). Reuse the SA20 dispatch pattern (now centralized by SA43) for both. Dry-run stays synchronous by design (documented SA20 shape) — unaffected.
  *Files:* `quickscale_modules/backups/src/quickscale_modules_backups/admin.py:356-378`.
  *Acceptance:* a backup-create request returns immediately with an async-dispatched job instead of blocking on `pg_dump`; a simulated slow `pg_dump` that would exceed the worker timeout no longer 502s; prune runs the same way.

- [ ] **SA38 — Detect and surface a stranded `STATUS_RESTORING` artifact instead of permanently refusing retry.** `Tier 1 · Track 2 · deps: SA43`
  A killed restore child (OOM, redeploy) strands `STATUS_RESTORING` forever — the child only sets `STATUS_FAILED` on Python exceptions, never on SIGKILL. The admin then permanently refuses retry ("Wait for the restore to complete…") and nothing reads `restore_started_at` for staleness, so the operator must hand-edit the DB mid-incident. Surface staleness in the admin (`restore_started_at` older than a threshold ⇒ "stale — child likely dead" + a guarded reset-to-FAILED action).
  *Files:* `quickscale_modules/backups/src/quickscale_modules_backups/admin.py:776-780`, `backups_restore` management command.
  *Acceptance:* simulate a killed restore child (status stuck `RESTORING` with an old `restore_started_at`) — admin surfaces a staleness warning and offers a guarded reset action; a genuinely recent in-progress restore is not flagged stale.

#### Finding — `throttle-identity-and-backing-store-unreliable-behind-proxy` (`why →` [TA18/TA24](../others/tech-audit.md))

- [ ] **SA21.2 — Wire forms/blog throttles and IP logging to the new canonical-IP and cache infrastructure.** `Tier 2 · Track 2 · deps: SA21.1 (complete), SA36 (Track 3 — land first: don't wire consumers to the off-by-one helper)`
  Point `FormSubmitThrottle.get_cache_key`, `_get_blog_api_rate_limit_ident`, and the IP fields recorded on `FormSubmission`/blog rate-limit logging at the canonical client-IP helper landed by SA21.1, and confirm both throttles run against the shared cache backend instead of the default in-memory one.
  *Files:* `quickscale_modules/forms/src/quickscale_modules_forms/throttles.py:26-30`, `quickscale_modules/forms/src/quickscale_modules_forms/views.py:231,257`, `quickscale_modules/blog/src/quickscale_modules_blog/views.py:260-266,277-304`.
  *Acceptance:* two requests with different `X-Forwarded-For` values (fixed `REMOTE_ADDR`) get independent throttle buckets and are logged with the forwarded client IP, not the proxy's; a 6th form submission within the configured window from one distinct client is rejected regardless of which worker/replica serves it.

### Track 3 — Core/CLI plumbing

#### Finding — `generated-app-cache-table-missing` (`why →` [TA33](../others/tech-audit.md))

- [ ] **SA34 — Run `createcachetable` in the generated app's deploy script.** `Tier 1 · Track 3 · deps: none`
  The SA21.1 `CACHES` fallback (`DatabaseCache` on `django_cache_table` when `REDIS_URL` is unset) is never created by `migrate` — no deploy artifact runs `createcachetable`. On a Redis-less deployment, the first throttled request (e.g. the public form) raises `ProgrammingError` and 500s. Add `python manage.py createcachetable` to `start.sh.j2` after the migrate step (idempotent no-op when the table exists or Redis is active).
  *Files:* `quickscale_core/src/quickscale_core/generator/templates/start.sh.j2:49` (near the migrate step), `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/production.py.j2:254-268` (context).
  *Acceptance:* a template test asserts `createcachetable` appears in rendered `start.sh` after `migrate`; e2e — boot the generated app with `REDIS_URL` unset and assert a form POST returns 201/429, never 500.

#### Finding — `get-client-ip-off-by-one` (`why →` [TA35](../others/tech-audit.md))

- [ ] **SA36 — Fix the off-by-one in the generated `get_client_ip()` proxy-count math before SA21.2 wires consumers to it.** `Tier 1 · Track 3 · deps: none — land before SA21.2 (Track 2)`
  `get_client_ip()` extracts `ips[-(TRUSTED_PROXY_COUNT + 1)]` guarded by `len(ips) > TRUSTED_PROXY_COUNT`. With Railway's single hop, an honest request has chain length 1 → the guard fails → returns the **proxy IP**; a request with an attacker-supplied `X-Forwarded-For` entry returns the **attacker-controlled** value. Currently zero consumers, but it's the designated foundation for SA21.2 — fix now or TA18 goes from "collapsed" to "spoofable". Fix: `ips[-TRUSTED_PROXY_COUNT]` with `len(ips) >= TRUSTED_PROXY_COUNT`, matching DRF's own `NUM_PROXIES` semantics.
  *Files:* `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/base.py.j2:63-97` and the duplicate copy in `production.py.j2`.
  *Acceptance:* a template test with fixed `REMOTE_ADDR` asserts an honest single-hop request resolves to the real client IP (not the proxy), and a request with an extra attacker-supplied XFF entry does not resolve to the attacker-controlled value.

#### Finding — `json-api-boundary-idiom-fragmentation` (`why →` [arch-audit.md Finding 5](../others/arch-audit.md), first step only)

- [ ] **SA46 — Add a CI gate pairing every `csrf_exempt` callsite with a signature check or `_enforce_csrf`.** `Tier 1 · Track 3 · deps: none`
  Three coexisting idioms exist for authed state-changing JSON endpoints (DRF baseline, orgs' `JsonApiMixin` stack, billing's plain Views manually re-implementing CSRF via `_enforce_csrf`); a new endpoint copying `@method_decorator(csrf_exempt, ...)` without the paired helper call fails no gate today. Add an AST gate — modeled on `scripts/check_org_context_primitives.py` — that fails CI when a `csrf_exempt`-decorated view doesn't call `_enforce_csrf` or verify a cryptographic signature. Full consolidation onto one base view (arch-audit's fold/migration options) is out of scope for this phase.
  *Files:* new check module alongside `scripts/check_org_context_primitives.py`; `quickscale_modules/billing/src/quickscale_modules_billing/views.py` csrf_exempt callsites (`:82-84,158-376`) and the notifications webhook view as the correctly-exempt counter-example.
  *Acceptance:* the gate fails CI on a `csrf_exempt` view missing `_enforce_csrf`/a signature check; existing billing and notifications callsites pass; wired into `ci.yml` alongside the other AST gates.

#### Finding — `dr-engine-module-circular-lattice` (`why →` [arch-audit.md Finding 1](../others/arch-audit.md), stage 1 only)

- [ ] **SA44 — Replace import-time adapter registration with explicit registration; delete the circular-import string-matching classifier.** `Tier 2 · Track 3 · deps: none`
  `_initialize_managed_adapters_at_import()` triggers adapter registration as an import-time side effect, guarded by `_is_import_time_adapter_circular_import` — a classifier that string-matches CPython's "partially initialized module"/"circular import" exception text against a hand-maintained module-name allowlist (grown from 2 to 3 entries in the SA20 closeout). Replace with explicit registration (module `AppConfig.ready()` or `importlib.metadata` entry points); delete the classifier outright; split `runtime.py` into `runtime.dr` and `runtime.manifest` so the two domains stop interlocking. Does not remove core→module imports (that's arch-audit Option 2 — persistence port — deferred to a future phase).
  *Files:* `manifest/entry_point.py:1436-1462,1511`, `quickscale_core/src/quickscale_core/runtime.py:107-141,152-272`.
  *Acceptance:* `test_manifest_entry_point.py` (the SA20 test for the classifier) becomes the regression harness for the replacement and passes; the string-matching classifier is gone; adapter registration is an explicit act, not an import-time side effect; importing DR-flavored code no longer trips manifest-adapter registration as a side effect.

#### Finding — `entry-point-posthook-permissive-coercion-defaults` (`why →` [TA40](../others/tech-audit.md))

- [ ] **SA42 — Make module post-hook settings reads fail hard instead of silently coercing.** `Tier 2 · Track 3 · deps: none`
  `entry_point.py` post-hooks retain permissive `.get(key, default)` coercions for blog (`POSTS_PER_PAGE`→10, `ENABLE_RSS`→True, empty rate→`"5/hour"`), listings (→12), forms (five defaults incl. `SPAM_PROTECTION`→True), and notifications (`ENABLED`→True, TTL→300) — second-guessing SA27-validated input one layer down. Dead today (SA27 guarantees valid baked literals) but reopens the TA2/TA19/TA26 fail-open class silently on any upstream resolver regression. Fix: direct required reads (`settings["KEY"]`), matching the SA18.2 analytics-hook purge.
  *Files:* `manifest/entry_point.py:386-390` (blog), `:451` (listings), `:520-531` (forms), `:898-921` (notifications).
  *Acceptance:* each of the four post-hooks reads its settings via direct required access instead of `.get(key, default)`; a missing/invalid post-hook setting raises `ImproperlyConfigured`/equivalent at apply time instead of silently defaulting.

#### Finding — `throttle-identity-and-backing-store-unreliable-behind-proxy` (`why →` [TA18/TA24](../others/tech-audit.md))

> **SA21.1 — complete.** Canonical client-IP resolution and shared cache backend added to generated settings. Unblocks SA21.2. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `module-option-validation-not-enforced-at-apply` (`why →` [TA26](../others/tech-audit.md))

> **SA27 — complete.** Enforced module-option validation on the apply path; removed the silent coercions that masked it. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `railway-cli-secrets-on-argv` (`why →` [TA27](../others/tech-audit.md))

> **SA31 — complete.** Moved Railway/DR adapter secrets off process argv onto stdin transport (DR adapter JSON, single and batch Railway variable writes); closes TA27. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `invalidate-social-cache-org-unaware` (`why →` [TA28](../others/tech-audit.md))

> **SA32 — complete.** Retired `invalidate_social_cache()` from the social module's public export surface (kept importable for compatibility); closes TA28. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `dangling-arch-audit-anchor` (`why →` [TA29](../others/tech-audit.md))

> **SA33 — complete.** Dangling `decisions.md:650` → `arch-audit.md` anchor link repointed to the arch-audit reconciliation log entry. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `markdown-uri-scheme-stored-xss` (`why →` [TA25](../others/tech-audit.md))

> **SA26 — complete.** Sanitized markdown-rendered URI schemes on public blog/listing pages via a stdlib-only allowlist scheme check (`_sanitize_rendered_html()`), neutralizing `javascript:`/`data:`/`vbscript:` links including control-character/whitespace obfuscation variants (CR-SA26-001 hardening). Full detail in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
