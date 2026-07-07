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

> **Closed batches (detail in [CHANGELOG.md](../../CHANGELOG.md)):** SA1–SA5 (2026-07-02), SA6–SA12 (2026-07-03), SA13.1–SA13.4 (2026-07-04), SA14.1–SA14.6 (2026-07-05), SA15.1–SA15.3 (2026-07-04), SA16.1/SA16.2 (2026-07-03), SA17.1–SA17.8 (2026-07-05), SA18.1–SA18.11 (2026-07-04), SA19 (2026-07-05), SA20 (2026-07-06), SA21.1 (2026-07-05), SA22 (2026-07-05), SA23 (2026-07-05), SA24 (2026-07-05), SA25 (2026-07-05), SA26 (2026-07-06), SA27 (2026-07-05), SA28 (2026-07-05), SA29 (2026-07-05), SA30 (2026-07-06), SA31 (2026-07-05), SA32 (2026-07-06), SA33 (2026-07-05), SA34 (2026-07-06), SA35 (2026-07-07), SA36 (2026-07-07), SA37 (2026-07-07), SA38 (2026-07-07), SA39 (2026-07-06), SA40 (2026-07-06), SA43 (2026-07-07), SA45 (2026-07-06). All closed per template rule — detail lives in CHANGELOG.md.

> **Triage note (2026-07-06):** the previously-deferred triage against [tech-audit.md](../others/tech-audit.md) (TA33–TA41 new/narrowed this pass) and [arch-audit.md](../others/arch-audit.md) (Findings 1–5) is done. SA34–SA47 below are the resulting fix items, each sized Tier 1–2 (arch-audit's larger Findings 1/2/4/5 are cut down to their recommended *first step* only — later stages are explicitly deferred, matching the source docs' own "recommended first stage" framing). One doc-drift note: tech-audit's summary table still lists **TA32 as open**, but the code (`listings/views.py`, `storage/helpers.py`) already raises `ImproperlyConfigured` per SA30 — verified directly. Treating TA32 as closed (per roadmap's existing SA30 entry); no new item created for it. tech-audit.md itself is left untouched by this pass — only roadmap.md is updated here.
>
> **Cleanup note (2026-07-06, later same day):** SA34, SA39, SA40, and SA45 landed and are condensed to one-line pointers above (detail in CHANGELOG.md). This pass also reconciled tech-audit.md directly — closed TA33 (SA34), TA38 (SA39), TA41 (SA40), and the TA32 doc-drift flagged in the triage note above (SA30) — and updated arch-audit.md's Finding 4 to record SA45 as a partial completion of Option 1 (purge-spec half only; `TENANT_TABLE_REGISTRY`'s derivation check and Option 2 remain open).

> **Track status (2026-07-07):** Track 1 — **1 open item, clear to continue** (SA41 complete, SA47 soft-sequenced after; SA35/SA39/SA45 complete). Track 2 — **1 open item, clear to continue** (SA21.2 unblocked now that Track 3's SA36 is complete; SA37/SA38/SA40 complete). Track 3 — **2 open items + 1 partial (blocker pending)** (SA42, SA44 ready now; SA46 partial — CR-SA46-001 and CR-SA46-REV-002 shipped, CR-SA46-REV-003 **[compile-time unary fold beyond signed numerics]** remains blocking; SA34/SA36 complete).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)          Track 2 (module contracts & settings)       Track 3 (core/CLI plumbing)
───────────────────────────────           ───────────────────────────────────         ───────────────────────────
SA35 (deps: none) — complete [AccountDeleteView survivor regression]              SA43 (deps: none) — complete                 SA36 (deps: none) — complete
SA41 (deps: none)                         SA21.2 (deps: SA21.1 complete, SA36 complete) SA46 (deps: none) — partial (CR-SA46-REV-003 pending)
SA47 (deps: SA35, SA41 — soft sequence)   SA37 (deps: SA43) — complete                 SA44 (deps: none)      │
                                           SA38 (deps: SA43) — complete                SA42 (deps: none)      │
                                                  ▲                                                        │
                                                  └──────────────── completed cross-track sequence: SA36 → SA21.2 ──────
```

Cross-track dependency update: **SA36 is now complete**, so SA21.2 is no longer blocked on Track 3 and can safely consume the canonical `get_client_ip()` helper landed after SA21.1. This preserves the intended SA21.1 → SA36 → SA21.2 sequencing that avoided shipping the attacker-controlled TA18 variant TA35 warned about. All other listed deps are same-track, same-file sequencing (noted per item below) rather than hard blockers, since each track's worktree processes one item at a time anyway. Rebalancing history (2026-07-05/06, preserved for context): SA24/SA29/SA30 moved Track 2 → Track 1 and SA32 moved Track 2 → Track 3 to restore 3/3/2 parallelism when Track 2 was carrying six open items; SA26 then moved Track 2 → Track 3 for 1/2/1 parallelism. All of those items are now complete; this triage pass restores 5/5/5 parallelism by assigning SA34–SA47 across the three tracks.

### Track 1 — Tenant-context surface

#### Finding — `operator-access-silent-noop-outside-atomic` (`why →` [TA38](../others/tech-audit.md))

> **SA39 — complete.** `operator_access()`/`_set_operator_access()` now raise `ImproperlyConfigured` when invoked outside an open transaction instead of silently no-opping (closes TA38). Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `org-model-universe-hand-enumerated` (`why →` [arch-audit.md Finding 4](../others/arch-audit.md), first step only)

> **SA45 — complete.** `test_purge_delete_specs_are_complete` now computes its expected model set from `get_tenant_models()` instead of a third hand-written copy — a new tenant model without a matching `_DELETE_SPECS` entry now fails CI (arch-audit Finding 4's Option 1, purge-spec half only; the `TENANT_TABLE_REGISTRY` completeness half and full purge-plan derivation, Option 2, remain open). Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `account-delete-cascade-content-loss` (`why →` [TA34](../others/tech-audit.md))

> **SA35 — complete.** `Post.author`, `ContactNote.created_by`, and `DealNote.created_by` changed from `on_delete=CASCADE` to `on_delete=SET_NULL`. `OrganizationInvitation.invited_by`'s CASCADE documented as intentional in `decisions.md`. Orgs cross-module conformance harness gates against new CASCADE user-FKs and includes an AccountDeleteView survivor regression. Closes TA34. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `account-delete-billing-exception-swallowed` (`why →` [TA39](../others/tech-audit.md))

> **SA41 — complete.** `BillingSubscriptionAnomalyError` (a direct `BillingError` subclass) now separates the missing-Stripe-id anomaly from the benign "no current subscription" case in `cancel_current_subscription`. `AccountDeleteView._cancel_personal_org_subscriptions` logs a `WARNING` for the anomalous case instead of silently passing; the no-subscription case remains silently handled. Stripe API failures continue to propagate unchanged. Closes SA41. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

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

> **SA40 — complete.** Public form-submit validation now rejects non-string payloads with 400 errors instead of 500ing on an uncaught `TypeError` (closes TA41). Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `backups-admin-orchestration-accretion` (`why →` [arch-audit.md Finding 3](../others/arch-audit.md), first step only)

> **SA43 — complete.** Extracted the async-restore dispatch lifecycle (atomic claim/status write → `Popen` spawn → spawn-failure rollback) from both recorded-artifact and uploaded-file admin dispatch branches into a single `dispatch_background_restore(artifact, *, confirmation)` service function. The shared `_atomic_claim_restore`, `_get_manage_py`, and `_ARTIFACT_RESTORE_CLAIMABLE_STATUSES` moved to `services.py` alongside it. Both admin dispatch branches now call the same extracted function. The uploaded-file materialization/persistence was later also moved to the service layer (`prepare_admin_uploaded_restore_artifact`), leaving the admin view responsible only for validated form input, service calls, and operator messaging for this flow. Monkeypatch targets in tests were updated from `admin.subprocess.Popen` and `admin._atomic_claim_restore` to their new `services.` locations. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `backups-sync-restore-blocks-worker` (`why →` [TA17](../others/tech-audit.md), narrowed to create/prune)

> **SA20 — complete** (restore). Moved admin-triggered backup restore off the synchronous request path via async `subprocess.Popen` dispatch, with an atomic compare-and-swap claim, spawn-failure rollback preserving prior failure metadata, and forced `--local-only` resolution (CR-SA20-005 through CR-SA20-008, CR-SA20-REV-001/002 resolved). Full detail in [CHANGELOG.md](../../CHANGELOG.md).

> **SA37 — complete.** Moved admin backup create and prune off the synchronous request path by adding `dispatch_background_create()` and `dispatch_background_prune()` to `services.py` (following the SA43 `dispatch_background_restore` pattern). Both `create_backup_now` and `prune_expired_backups_now` admin actions now dispatch `backups_create` / `backups_prune` via `subprocess.Popen` and return immediately with a "has been initiated in the background" message. Both `BackupPolicyAdmin.create_backup_view` and `BackupArtifactAdmin.create_backup_view` (the two‑site alert) and `BackupPolicyAdmin.prune_expired_backups_view` are covered because they delegate to the same updated actions. Monkeypatch targets in tests updated from `admin.create_backup`/`admin.prune_expired_backups` to `admin.dispatch_background_create`/`admin.dispatch_background_prune`. Acceptance: a backup‑create or prune request returns immediately instead of blocking on `pg_dump`/file deletion. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

> **SA38 — complete.** Stale `STATUS_RESTORING` artifacts (older than 30 minutes) are now detected and surfaced on the BackupArtifact admin page (stale warning column + reset action), in the restore-retry flow (stale-aware refusal message instead of permanent block), and in the uploaded-file restore path (same stale-aware recovery guidance). The shared stale-detection helper `is_restore_stale()` lives in `services.py` and is used by both admin surfaces (`BackupPolicyAdmin` eligibility guard and `BackupArtifactAdmin` stale warning). `reset_stale_restore(artifact)` uses a database-level compare-and-swap so a concurrently finishing child process never has its terminal status overwritten; it is wired as the `reset_stale_restore_action` admin action on `BackupArtifactAdmin` only, preserving the thin-admin/service-boundary pattern. Permission boundary unchanged — `reset_stale_restore_action` requires `change` on `BackupArtifact` (same gate as existing artifact admin actions). Added `is_restore_stale()`, `reset_stale_restore()`, and the `STALE_RESTORE_THRESHOLD_MINUTES = 30` constant. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `throttle-identity-and-backing-store-unreliable-behind-proxy` (`why →` [TA18/TA24](../others/tech-audit.md))

- [ ] **SA21.2 — Wire forms/blog throttles and IP logging to the new canonical-IP and cache infrastructure.** `Tier 2 · Track 2 · deps: SA21.1 (complete), SA36 (complete)`
  Point `FormSubmitThrottle.get_cache_key`, `_get_blog_api_rate_limit_ident`, and the IP fields recorded on `FormSubmission`/blog rate-limit logging at the canonical client-IP helper landed by SA21.1, and confirm both throttles run against the shared cache backend instead of the default in-memory one.
  *Files:* `quickscale_modules/forms/src/quickscale_modules_forms/throttles.py:26-30`, `quickscale_modules/forms/src/quickscale_modules_forms/views.py:231,257`, `quickscale_modules/blog/src/quickscale_modules_blog/views.py:260-266,277-304`.
  *Acceptance:* two requests with different `X-Forwarded-For` values (fixed `REMOTE_ADDR`) get independent throttle buckets and are logged with the forwarded client IP, not the proxy's; a 6th form submission within the configured window from one distinct client is rejected regardless of which worker/replica serves it.

### Track 3 — Core/CLI plumbing

#### Finding — `generated-app-cache-table-missing` (`why →` [TA33](../others/tech-audit.md))

> **SA34 — complete.** `createcachetable` now runs in `start.sh.j2` after the migrate step, gated to only run when `DatabaseCache` (not Redis) is active (closes TA33). Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `get-client-ip-off-by-one` (`why →` [TA35](../others/tech-audit.md))

> **SA36 — complete.** Fixed the off-by-one in generated `get_client_ip()` proxy-count math: guard changed to `len(ips) >= TRUSTED_PROXY_COUNT`, index to `ips[-TRUSTED_PROXY_COUNT]`, matching DRF's own `NUM_PROXIES` semantics. Landed before SA21.2 to avoid shipping the attacker-controlled TA18 variant TA35 warned about. Closes TA35. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `json-api-boundary-idiom-fragmentation` (`why →` [arch-audit.md Finding 5](../others/arch-audit.md), first step only)

> **SA46 — partial** (blocking finding CR-SA46-REV-003 remains — see below). CR-SA46-001 resolved: replaced the ad-hoc `_is_constant_true`/`_is_constant_false` helpers with `_literal_truthiness()` — a safe literal-only evaluator that returns `True`, `False`, or `None` (uncertain) for every Python literal type (`bool`, `int`, `float`, `complex`, `None`, `Ellipsis`, `str`, `bytes`, `tuple`, `list`, `dict`, `set`). Non-constant expressions return `None` (the conservative "scan both branches" path). CR-SA46-REV-002 resolved: extended `_literal_truthiness()` to fold parsed-source signed numeric literals (`ast.UnaryOp` with `UAdd`/`USub` over numeric `ast.Constant` values) — `-1`, `+1`, `-1.5`, `-1j` evaluate as truthy; `-0`, `+0`, `-0.0`, `+0.0`, `-0j`, `+0j` as falsey; every other unary expression returns `None`. Added 39 focused regression tests covering the missing literal-branch and signed-literal cases at both function and class levels (20 from CR-SA46-001 + 4 class-level visitor tests + 4 function-level visitor tests + 11 direct signed-literal unit tests from CR-SA46-REV-002). All existing passing coverage preserved. Full detail in [CHANGELOG.md](../../CHANGELOG.md).
>
> **Remaining blocker (CR-SA46-REV-003):** compile-time unary expressions beyond signed numerics (`+True`, `not 0`, `~0`) still return `None` in `_literal_truthiness()`, so dead-branch helpers can still satisfy the hard-fail gate. The user chose to stop further fixing, keep the shipped work, record this blocker, and commit/merge back to v87. Next step requires a decision on the compile-time unary handling strategy (e.g., extend the signed-numeric pattern to `not`/`~`/`+` over bools, or accept the conservative `None`-return as a deliberate false-positive trade-off).

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
