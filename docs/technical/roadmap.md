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

> **Closed batches (detail in [CHANGELOG.md](../../CHANGELOG.md)):** SA1–SA5 (2026-07-02), SA6–SA12 (2026-07-03), SA13.1–SA13.4 (2026-07-04), SA14.1–SA14.6 (2026-07-05), SA15.1–SA15.3 (2026-07-04), SA16.1/SA16.2 (2026-07-03), SA17.1–SA17.8 (2026-07-05), SA18.1–SA18.11 (2026-07-04), SA19 (2026-07-05), SA21.1 (2026-07-05), SA22 (2026-07-05), SA23 (2026-07-05), SA25 (2026-07-05), SA33 (2026-07-05). All closed per template rule — detail lives in CHANGELOG.md.

> **Track status (2026-07-05):** Track 1 clear to continue: SA28 complete (SA14, SA23 also complete — archived); rebalanced onto SA24, SA29, SA30 now that its own backlog is empty. Track 2 clear to continue: SA20 unblocked (decision: fix symlink, implementation in progress); SA21.2, SA26 ready. Track 3 clear to continue: SA27 complete; SA31 ready, SA32 rebalanced in (SA21.1, SA22, SA25, SA33 closed). No track is blocked. See track sections below for `why →` finding links.

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)     Track 2 (module contracts & settings)      Track 3 (core/CLI plumbing)
───────────────────────────────      ───────────────────────────────────       ───────────────────────────
SA28 — complete                      SA20 — in progress (decision made)        SA27 — complete
SA24 (no deps)                       SA21.2 (deps: SA21.1 — complete)          SA31 (no deps)
SA29 (no deps)                       SA26 (no deps)                            SA32 (no deps)
SA30 (no deps — land after SA29)
```

Cross-track dependency: SA21.2 (Track 2) → SA21.1 (Track 3 — complete). SA30 relates to SA29 and now lands in the same Track 1 sequence. Rebalanced 2026-07-05: SA24/SA29/SA30 moved Track 2 → Track 1 and SA32 moved Track 2 → Track 3, since Track 1 and Track 3 emptied out as SA28/SA27 completed while Track 2 still carried six open items — this restores 3/3/2 parallelism across the three worktrees.

### Track 1 — Tenant-context surface

#### Finding — `operator-read-path-undefined` (`why →` [arch-audit.md reconciliation log](../others/arch-audit.md#reconciliation-log-append-only))

> **SA14 — complete.** SA14.1–SA14.6 (TenantModelAdmin base, CRM/blog/forms/listings/billing admin ports, NOBYPASSRLS default for module test suites, operator_access RLS predicate, QUICKSCALE_MODE fail-hard) merged. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `debug-view-open-redirect` (`why →` [TA21](../others/tech-audit.md))

> **SA23 — complete.** Validated the `next` redirect target in orgs debug views with `url_has_allowed_host_and_scheme`. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `account-delete-cascade-bypasses-org-invariants` (`why →` [TA30](../others/tech-audit.md))

> **SA28 — complete.** Enforced the last-owner and personal-org invariants at the account-deletion boundary via an `AccountDeleteView.form_valid` override; cancels the personal org's active subscription through the existing billing seam before deletion. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `analytics-tags-mark-safe-unescaped` (`why →` [TA22](../others/tech-audit.md))

- [ ] **SA24 — Escape or `json_script` the analytics template tag payload.** `Tier 1 · Track 1 · deps: none`
  `analytics_tags.py:33` uses `mark_safe(json.dumps(payload))` without escaping `<`/`>`/`&`, which is latent stored-XSS if the payload ever carries request-influenced data. Switch to Django's `json_script` template filter/tag or manually escape those characters before marking safe.
  *Files:* `quickscale_modules/analytics/src/quickscale_modules_analytics/templatetags/analytics_tags.py:33`.
  *Acceptance:* a payload value containing `</script>` renders inert in the page source; existing analytics payload rendering is otherwise unchanged.

#### Finding — `storage-config-dead-env-docs-secrets-in-vcs` (`why →` [TA31](../others/tech-audit.md))

- [ ] **SA29 — Rebuild storage's config-delivery contract: env-var indirection for secrets, README aligned with the real wiring mechanism.** `Tier 2 · Track 1 · deps: none`
  Storage is the only secret-bearing module without the `*_env_var` indirection pattern analytics/notifications/billing already use, and its README documents a config channel (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/etc. as deploy-time env vars) that the generated app never reads — settings are baked as literals at generation time. Adopt the indirection pattern: storage credential options become `*_env_var` names (adapter emits `os.environ` reads into the managed settings module rather than baked literal values), keep `backend`/bucket/region as non-secret yml options, and rewrite the README against the real contract.
  *Files:* `quickscale_core/src/quickscale_core/manifest/entry_point.py:1269-1348` (`_storage_manifest_adapter`), `quickscale_core/src/quickscale_core/module_wiring.py:85-100`, `quickscale_core/src/quickscale_core/generator/templates/README.md.j2:265-286`, storage's `module.yml` option declarations.
  *Acceptance:* generating a project configured per the rewritten README and deploying with the documented env vars set results in uploads landing in the configured S3/R2 bucket; the generated `settings/modules.py` contains no credential material; leaving storage on `local` still works with no config required.

#### Finding — `listings-storage-runtime-fail-open-residuals` (`why →` [TA32](../others/tech-audit.md))

- [ ] **SA30 — Apply the SA17 direct-required-read pattern to listings/storage runtime settings.** `Tier 1 · Track 1 · deps: none (relates to SA29 — land after so storage's fixed contract is what this reads from)`
  `listings/views.py`'s `_get_positive_int_setting` and `storage/helpers.py`'s `_read_setting`/`_normalize_backend` silently default or coerce on missing/invalid values — the same class SA17.2–SA17.6 closed for other modules, but listings and storage were outside that batch's scope. Replace with direct required reads that raise `ImproperlyConfigured` on missing/invalid values, matching the SA17 shape.
  *Files:* `quickscale_modules/listings/src/quickscale_modules_listings/views.py:30-70`, `quickscale_modules/storage/src/quickscale_modules_storage/helpers.py:35-115`.
  *Acceptance:* an invalid/missing `LISTINGS_PER_PAGE` or `QUICKSCALE_STORAGE_BACKEND` value raises a descriptive startup error instead of silently falling back; valid configurations are unaffected.

### Track 2 — Module contracts & settings

#### Finding — `backups-sync-restore-blocks-worker` (`why →` [TA17](../others/tech-audit.md))

- [ ] **SA20 — Move admin-triggered backup restore off the synchronous request path.** `Tier 2 · Track 2 · deps: none · RISK LEVEL: medium`
  **In progress — CR-SA20-005 symlink fix in progress.** Track 2 worktree has made substantial progress on the async restore lifecycle:
  - **Async dispatch:** Restore no longer runs synchronously in-request. Admin sets `STATUS_RESTORING` and dispatches `backups_restore` management command via `subprocess.Popen`, returning immediately.
  - **Restore status lifecycle:** `BackupArtifact` tracks `STATUS_RESTORING`, `restore_started_at`, and `restore_error`. Management command persists failure on `BackupError`.
  - **Spawn-failure rollback:** A failed `subprocess.Popen` reverts `STATUS_RESTORING` to avoid stranded restoring state.
  - **Uploaded-file path parity:** Uploaded-file restore shares the trusted resolver / staging seam used by the existing admin download/restore path.
  - **Admin regression coverage:** Tests cover trusted-match rejection, incomplete-snapshot rejection, out-of-tree remap, and attempted symlink remap.

  **Blocker CR-SA20-005 (high, blocking, security-boundary):** The async uploaded-file restore remap can still follow a preexisting symlink at the authoritative destination and write outside the backup root.

  **Decision (2026-07-05):** Fix the symlink path traversal now — consistent with all prior security-boundary hardening precedents (SA2.1, SA17, SA18). A symlink check or path resolution guard is needed in the uploaded-file restore remap before merge.
  *Files:* `quickscale_modules/backups/src/quickscale_modules_backups/admin.py`, `models.py`, `management/commands/backups_restore.py`, `templates/admin/.../restore.html`, `migrations/0005_backupartifact_restore_execution.py`, `tests/test_admin.py`.
  *Acceptance:* triggering a restore from the admin returns before the 60s worker timeout regardless of restore duration; the restore's success/failure is observable after the fact (status field, `restore_error`, log, or notification); a restore that fails mid-way is distinguishable from one that never started (`STATUS_FAILED + restore_error` vs `STATUS_RESTORING`). **In progress — CR-SA20-005 symlink fix pending.**

#### Finding — `throttle-identity-and-backing-store-unreliable-behind-proxy` (`why →` [TA18/TA24](../others/tech-audit.md))

- [ ] **SA21.2 — Wire forms/blog throttles and IP logging to the new canonical-IP and cache infrastructure.** `Tier 2 · Track 2 · deps: SA21.1`
  Point `FormSubmitThrottle.get_cache_key`, `_get_blog_api_rate_limit_ident`, and the IP fields recorded on `FormSubmission`/blog rate-limit logging at the canonical client-IP helper landed by SA21.1, and confirm both throttles run against the shared cache backend instead of the default in-memory one.
  *Files:* `quickscale_modules/forms/src/quickscale_modules_forms/throttles.py:26-30`, `quickscale_modules/forms/src/quickscale_modules_forms/views.py:231,257`, `quickscale_modules/blog/src/quickscale_modules_blog/views.py:260-266,277-304`.
  *Acceptance:* two requests with different `X-Forwarded-For` values (fixed `REMOTE_ADDR`) get independent throttle buckets and are logged with the forwarded client IP, not the proxy's; a 6th form submission within the configured window from one distinct client is rejected regardless of which worker/replica serves it.

#### Finding — `markdown-uri-scheme-stored-xss` (`why →` [TA25](../others/tech-audit.md))

- [ ] **SA26 — Sanitize markdown-rendered URI schemes on public blog/listing pages.** `Tier 2 · Track 2 · deps: none`
  `markdownify(escape(...))` blocks raw HTML injection but not markdown-native `[text](javascript:...)` links, which render as an unescaped `<a href="javascript:...">` under the `|safe` filter. Run the rendered HTML through an allowlist sanitizer (`bleach.clean`/`nh3`) restricting `href` schemes to `http`/`https`/`mailto`, or configure a markdown URL-sanitizing extension, before marking safe.
  *Files:* `quickscale_modules/blog/src/quickscale_modules_blog/views.py:787`, `quickscale_modules/listings/src/quickscale_modules_listings/views.py:304-305`, both post/listing detail templates.
  *Acceptance:* publishing a post/listing with a `javascript:` markdown link results in a stripped/neutralized `href` on the rendered detail page; legitimate `http(s)`/`mailto` markdown links continue to render as clickable anchors.

### Track 3 — Core/CLI plumbing

#### Finding — `throttle-identity-and-backing-store-unreliable-behind-proxy` (`why →` [TA18/TA24](../others/tech-audit.md))

> **SA21.1 — complete.** Canonical client-IP resolution and shared cache backend added to generated settings. Unblocks SA21.2. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `module-option-validation-not-enforced-at-apply` (`why →` [TA26](../others/tech-audit.md))

> **SA27 — complete.** Enforced module-option validation on the apply path; removed the silent coercions that masked it. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `railway-cli-secrets-on-argv` (`why →` [TA27](../others/tech-audit.md))

- [ ] **SA31 — Move Railway/DR adapter secrets off process argv.** `Tier 1 · Track 3 · deps: none`
  `railway_utils.py` invokes `railway variables --set KEY=VALUE` with live secret values on the command line, and `dr_commands.py` passes `--args-json` on `docker exec` argv — both visible to any local user via `ps`/`/proc` on shared hosts. Switch to stdin transport for the adapter JSON payload; for the Railway CLI (which has no stdin-based `--set`), document the CLI limitation and scope the fix to what's actually controllable (e.g. minimize the exposure window, or investigate `railway variables --set` alternatives such as a batch file input if the CLI supports one).
  *Files:* `quickscale_cli/src/quickscale_cli/utils/railway_utils.py:348,391,891`, `quickscale_cli/src/quickscale_cli/commands/dr_commands.py:232-242`.
  *Acceptance:* the DR adapter's JSON payload no longer appears in `docker exec` argv (stdin transport verified via a process-argv assertion in tests); the Railway CLI limitation (if unfixable) is documented in code comments and this finding's closeout note.

#### Finding — `invalidate-social-cache-org-unaware` (`why →` [TA28](../others/tech-audit.md))

- [ ] **SA32 — Fix or retire `invalidate_social_cache()`.** `Tier 1 · Track 3 · deps: none`
  The exported `invalidate_social_cache()` clears only bare cache keys, a no-op for the org-partitioned keys actually used under tenant context (model `save()`/`delete()` invalidate correctly; this function is uncalled by first-party code but is a public-API trap for bulk mutations like `queryset.update()` that bypass `save()`). Either make it org-aware (accept/iterate org context) or remove it from `__all__` so it stops looking like a safe bulk-invalidation tool.
  *Files:* `quickscale_modules/social/src/quickscale_modules_social/services.py:182-184`.
  *Acceptance:* either a test demonstrates `invalidate_social_cache()` correctly invalidates org-partitioned entries, or the function is dropped from the module's public `__all__` with a comment explaining why.

#### Finding — `dangling-arch-audit-anchor` (`why →` [TA29](../others/tech-audit.md))

> **SA33 — complete.** Dangling `decisions.md:650` → `arch-audit.md` anchor link repointed to the arch-audit reconciliation log entry. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
