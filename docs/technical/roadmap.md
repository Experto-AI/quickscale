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

> **Closed batches (detail in [CHANGELOG.md](../../CHANGELOG.md)):** SA1–SA5 (2026-07-02), SA6–SA12 (2026-07-03), SA13.1–SA13.4 (2026-07-04), SA14.1–SA14.6 (2026-07-05), SA15.1–SA15.3 (2026-07-04), SA16.1/SA16.2 (2026-07-03), SA17.1–SA17.8 (2026-07-05), SA18.1–SA18.11 (2026-07-04), SA19 (2026-07-05), SA21.1 (2026-07-05), SA22 (2026-07-05), SA23 (2026-07-05), SA24 (2026-07-05), SA25 (2026-07-05), SA27 (2026-07-05), SA28 (2026-07-05), SA29 (2026-07-05), SA31 (2026-07-05), SA32 (2026-07-06), SA33 (2026-07-05). All closed per template rule — detail lives in CHANGELOG.md.

> **Track status (2026-07-06):** Track 1 clear to continue: SA28, SA24, and SA29 complete (SA14, SA23 also complete — archived); rebalanced onto SA30 now that its earlier backlog is closed. Track 2: SA20 has a locked design decision (Option A, 2026-07-06) and is ready for implementation — CR-SA20-005/006/008 resolved, CR-SA20-007 fix is scoped with a file/line checklist, just not yet coded; SA21.2 is otherwise ready once SA20 is picked up. Track 3: SA27, SA31, and SA32 complete (SA21.1, SA22, SA25, SA33 also closed); rebalanced onto SA26, which has no dependencies and is ready to start now. See track sections below for `why →` finding links.

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)     Track 2 (module contracts & settings)      Track 3 (core/CLI plumbing)
───────────────────────────────      ───────────────────────────────────       ───────────────────────────
SA28 — complete                      SA20 — ready to implement (design decided, CR-SA20-007)   SA27 — complete
SA24 — complete                      SA21.2 (deps: SA21.1 — complete)          SA31 — complete
SA29 — complete                                                               SA32 — complete
SA30 (no deps — land after SA29)                                              SA26 (no deps)
```

Cross-track dependency: SA21.2 (Track 2) → SA21.1 (Track 3 — complete). SA30 relates to SA29 and now lands in the same Track 1 sequence. Rebalanced 2026-07-05: SA24/SA29/SA30 moved Track 2 → Track 1 and SA32 moved Track 2 → Track 3, since Track 1 and Track 3 emptied out as SA28/SA27 completed while Track 2 still carried six open items — this restored 3/3/2 parallelism across the three worktrees. Rebalanced again 2026-07-06: SA26 moved Track 2 → Track 3, since Track 3 emptied out again as SA27/SA31/SA32 completed while Track 2 still carried three open items (SA20, SA21.2, SA26) — this restores 1/2/1 parallelism, weighted toward Track 2 since SA20 is the larger in-progress item.

### Track 1 — Tenant-context surface

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

- [ ] **SA30 — Apply the SA17 direct-required-read pattern to listings/storage runtime settings.** `Tier 1 · Track 1 · deps: none (relates to SA29 — land after so storage's fixed contract is what this reads from)`
  `listings/views.py`'s `_get_positive_int_setting` and `storage/helpers.py`'s `_read_setting`/`_normalize_backend` silently default or coerce on missing/invalid values — the same class SA17.2–SA17.6 closed for other modules, but listings and storage were outside that batch's scope. Replace with direct required reads that raise `ImproperlyConfigured` on missing/invalid values, matching the SA17 shape.
  *Files:* `quickscale_modules/listings/src/quickscale_modules_listings/views.py:30-70`, `quickscale_modules/storage/src/quickscale_modules_storage/helpers.py:35-115`.
  *Acceptance:* an invalid/missing `LISTINGS_PER_PAGE` or `QUICKSCALE_STORAGE_BACKEND` value raises a descriptive startup error instead of silently falling back; valid configurations are unaffected.

### Track 2 — Module contracts & settings

#### Finding — `backups-sync-restore-blocks-worker` (`why →` [TA17](../others/tech-audit.md))

- [ ] **SA20 — Move admin-triggered backup restore off the synchronous request path.** `Tier 2 · Track 2 · deps: none · RISK LEVEL: medium`
  **Design decided, ready for implementation — CR-SA20-005/006/008 resolved; CR-SA20-007 fix is scoped (Option A, see checklist below), not yet coded.** Track 2 worktree has made substantial progress on the async restore lifecycle:
  - **Async dispatch:** Restore no longer runs synchronously in-request. Admin persists `STATUS_RESTORING` before spawning `backups_restore` via `subprocess.Popen`, returning immediately (both recorded-artifact and uploaded-file branches use the artifact-id dispatch path).
  - **Restore status lifecycle:** `BackupArtifact` tracks `STATUS_RESTORING`, `restore_started_at`, and `restore_error`. Management command persists failure on any exception (BackupError, fast failures, generic crashes) — not just `BackupError`.
  - **Spawn-failure rollback:** `STATUS_RESTORING` is persisted before `Popen()`; a failed spawn reverts to the pre-spawn status so fast child terminal states are never clobbered and spawn failures never strand the artifact.
  - **Local-only enforcement:** Admin-triggered background restores pass `--local-only` to the child command, so the child never falls back to remote materialization even when the local file disappears after enqueue.
  - **Uploaded-file path parity:** Uploaded-file restore shares the trusted resolver / staging seam used by the existing admin download/restore path. Both branches dispatch via artifact-id (not `--file`).
  - **Admin regression coverage:** Tests cover trusted-match rejection, incomplete-snapshot rejection, out-of-tree remap, attempted symlink remap, `--local-only` arg presence, BackupError failure recording, generic-exception failure recording, non-stranding for non-RESTORING artifacts, spawn-failure rollback on both branches, and fast-child-terminal-non-clobber on both branches.

  **CR-SA20-005 (resolved):** The async uploaded-file restore used `shutil.copy2(staged_upload.local_path, local_path)` where `local_path` was derived from `get_local_backup_directory()/trusted_artifact.filename`. If `local_path` already existed as a symlink pointing outside the backup root, `copy2` would follow it and write outside the root. Fixed by adding `local_path.unlink(missing_ok=True)` before `copy2` so a pre-existing destination (regular file or symlink) is always removed first, materializing a regular file inside the authoritative backup directory. The symlink regression test was strengthened to preload the escape target with different content so the test fails if the symlink is followed — proving the fix is active.

  **CR-SA20-006 (resolved):** The async admin flow enqueued the generic artifact-id restore path without forcing `RestoreSourceResolutionMode.LOCAL_ONLY`. If the local file disappeared after enqueue, the child could fall back to remote materialization, violating the admin restore contract. Fixed by adding `--local-only` flag to `backups_restore` management command (maps to `resolution_mode=LOCAL_ONLY` in the adapter), and passing it from both recorded-artifact and uploaded-file admin dispatch paths. The adapter function `restore_backup` now accepts an optional `resolution_mode` parameter. Regression: admin dispatch tests assert `--local-only` in Popen args; command-level tests verify `resolution_mode="local_only"` is passed to the adapter.

  **CR-SA20-007 — remaining implementation item (spawn-failure rollback metadata restoration).** The lifecycle-ordering race sub-finding (fast-child terminal status clobber) is already resolved: `STATUS_RESTORING` is persisted before `Popen()`, the parent never writes status after `Popen` returns, and two admin regressions (`test_restore_async_parent_does_not_clobber_fast_child_terminal_status` and its uploaded-file counterpart) prove fast-child terminal states are preserved. Combined with the existing command-level failure-recording regressions (BackupError, generic `ValueError`, non-RESTORING unaffected), the lifecycle-ordering race is fully closed.

  What's left: the spawn-failure rollback still fails to restore pre-spawn `restore_started_at` and `restore_error` metadata when the parent retries a previously FAILED or RESTORED artifact and `Popen()` raises. When the parent resets the artifact's status to `STATUS_RESTORING` before the new spawn attempt, the prior failure metadata is overwritten without being preserved — so a mere spawn failure on retry destroys the diagnostic record of the *original* restore failure. This is the sole remaining item before SA20 closeout.

  **Design decision (2026-07-06, locked) — Option A: snapshot-and-restore, symmetric with the existing `pre_spawn_status` pattern.** Extend the two spawn-failure rollback blocks in `admin.py` (recorded-artifact branch and uploaded-file branch) to capture `restore_started_at` and `restore_error` into local variables *alongside* `pre_spawn_status`, before the pre-spawn overwrite. On `Popen()` failure, restore all three fields (`status`, `restore_started_at`, `restore_error`) together in the same `save(update_fields=...)` call, instead of only resetting `status` and nulling `restore_started_at`.
  - **Why this option over the alternatives:** (B) moving the metadata writes into the child's "on entry" branch was rejected — it reopens the fast-child-terminal-clobber race that CR-SA20-007's status-ordering fix already closed, for no functional gain. (C) reloading from DB via `refresh_from_db()` before rollback was rejected — needless round trip and a race window against concurrent admin actions, when the in-memory pre-spawn values are already available. Option A reuses code shape the review has already validated once (status rollback) and matches the project's standing convention of preserving failure audit trails rather than silently discarding them (see the SA17 direct-required-read batch).
  - **Implementation checklist for whoever picks this up:**
    1. In `admin.py`'s recorded-artifact restore branch (~line 495-552) and uploaded-file branch (~line 638-688): before setting `status = STATUS_RESTORING` / `restore_started_at = now()` / `restore_error = ""`, snapshot the pre-spawn values of all three fields.
    2. In the `except Exception:` rollback after `Popen()`, write the snapshotted values back for all three fields (not just `status`), in one `save(update_fields=[...])` call.
    3. Add regression tests mirroring `test_restore_page_does_not_strand_status_restoring_on_spawn_failure` and its uploaded-file counterpart, but seeding the artifact with a prior `STATUS_FAILED`/`STATUS_RESTORED` state plus a non-empty `restore_started_at`/`restore_error`, then asserting those exact prior values survive a `Popen()` failure on retry — for both the recorded-artifact and uploaded-file branches (4 new/adjusted cases total, matching the existing branch-parity pattern).
  - **Files to touch:** `quickscale_modules/backups/src/quickscale_modules_backups/admin.py`, `quickscale_modules/backups/tests/test_admin.py`.

  **CR-SA20-008 (resolved):** The CHANGELOG's SA20 entry previously described the uploaded-file dispatch as using ``--file <path>``, but both branches (recorded-artifact and uploaded-file) dispatch via artifact-id. The CHANGELOG entry and roadmap wording have been corrected to accurately reflect the artifact-id dispatch for both branches.

  *Files:* `quickscale_modules/backups/src/quickscale_modules_backups/admin.py`, `quickscale_modules/backups/src/quickscale_modules_backups/management/commands/backups_restore.py`, `quickscale_core/src/quickscale_core/dr_engine/adapter.py`, `quickscale_modules/backups/tests/test_admin.py`, `quickscale_modules/backups/tests/test_restore_command.py`.
  *Acceptance:* triggering a restore from the admin returns before the 60s worker timeout regardless of restore duration; the restore's success/failure is observable after the fact (status field, `restore_error`, log, or notification); a restore that fails mid-way is distinguishable from one that never started (`STATUS_FAILED + restore_error` vs `STATUS_RESTORING`); admin-triggered restores never fall back to remote materialization even when the local file is removed after enqueue; any exception in the child (including non-BackupError crashes) records `STATUS_FAILED` instead of stranding `STATUS_RESTORING`.

  **Circular-import guard expansion (SA20 closeout):** The SA20 import chain (backups admin → services → `quickscale_core.runtime` → managed-adapters init) triggered a pre-existing gap in the lazy-init circular-import detector in `quickscale_core.manifest.entry_point`. The guard recognised only `quickscale_core.manifest.entry_point` and `quickscale_core.contracts.resolvers` as tolerated partially-initialized modules, so the import through `quickscale_core.runtime` was re-raised as `ImproperlyConfigured`, blocking test startup. Added `quickscale_core.runtime` to the recognised patterns. *Files:* `quickscale_core/src/quickscale_core/manifest/entry_point.py`, `quickscale_core/tests/test_manifest_entry_point.py`.

#### Finding — `throttle-identity-and-backing-store-unreliable-behind-proxy` (`why →` [TA18/TA24](../others/tech-audit.md))

- [ ] **SA21.2 — Wire forms/blog throttles and IP logging to the new canonical-IP and cache infrastructure.** `Tier 2 · Track 2 · deps: SA21.1`
  Point `FormSubmitThrottle.get_cache_key`, `_get_blog_api_rate_limit_ident`, and the IP fields recorded on `FormSubmission`/blog rate-limit logging at the canonical client-IP helper landed by SA21.1, and confirm both throttles run against the shared cache backend instead of the default in-memory one.
  *Files:* `quickscale_modules/forms/src/quickscale_modules_forms/throttles.py:26-30`, `quickscale_modules/forms/src/quickscale_modules_forms/views.py:231,257`, `quickscale_modules/blog/src/quickscale_modules_blog/views.py:260-266,277-304`.
  *Acceptance:* two requests with different `X-Forwarded-For` values (fixed `REMOTE_ADDR`) get independent throttle buckets and are logged with the forwarded client IP, not the proxy's; a 6th form submission within the configured window from one distinct client is rejected regardless of which worker/replica serves it.

### Track 3 — Core/CLI plumbing

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

- [ ] **SA26 — Sanitize markdown-rendered URI schemes on public blog/listing pages.** `Tier 2 · Track 3 · deps: none`
  `markdownify(escape(...))` blocks raw HTML injection but not markdown-native `[text](javascript:...)` links, which render as an unescaped `<a href="javascript:...">` under the `|safe` filter. Run the rendered HTML through an allowlist sanitizer (`bleach.clean`/`nh3`) restricting `href` schemes to `http`/`https`/`mailto`, or configure a markdown URL-sanitizing extension, before marking safe.
  *Files:* `quickscale_modules/blog/src/quickscale_modules_blog/views.py:787`, `quickscale_modules/listings/src/quickscale_modules_listings/views.py:304-305`, both post/listing detail templates.
  *Acceptance:* publishing a post/listing with a `javascript:` markdown link results in a stripped/neutralized `href` on the rendered detail page; legitimate `http(s)`/`mailto` markdown links continue to render as clickable anchors.

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
