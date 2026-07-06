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

> **Closed batches (detail in [CHANGELOG.md](../../CHANGELOG.md)):** SA1–SA5 (2026-07-02), SA6–SA12 (2026-07-03), SA13.1–SA13.4 (2026-07-04), SA14.1–SA14.6 (2026-07-05), SA15.1–SA15.3 (2026-07-04), SA16.1/SA16.2 (2026-07-03), SA17.1–SA17.8 (2026-07-05), SA18.1–SA18.11 (2026-07-04), SA19 (2026-07-05), SA20 (2026-07-06), SA21.1 (2026-07-05), SA22 (2026-07-05), SA23 (2026-07-05), SA24 (2026-07-05), SA25 (2026-07-05), SA26 (2026-07-06), SA27 (2026-07-05), SA28 (2026-07-05), SA29 (2026-07-05), SA30 (2026-07-06), SA31 (2026-07-05), SA32 (2026-07-06), SA33 (2026-07-05). All closed per template rule — detail lives in CHANGELOG.md.

> **Track status (2026-07-06):** Track 1 — idle, no open item (SA28/SA24/SA29/SA30 all complete). Track 2 — active: SA20 complete, **SA21.2 is ready to start** (its dependency SA21.1 is complete). Track 3 — idle, no open item (SA21.1/SA22/SA25/SA26/SA27/SA31/SA32/SA33 all complete). Tracks 1 and 3 are clean to continue but have nothing queued in this phase set; new work for them requires triage from the open findings in [tech-audit.md](../others/tech-audit.md) and [arch-audit.md](../others/arch-audit.md) (deferred — see that decision below). See track sections below for `why →` finding links.

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)     Track 2 (module contracts & settings)      Track 3 (core/CLI plumbing)
───────────────────────────────      ───────────────────────────────────       ───────────────────────────
(no open items — idle)               SA21.2 (deps: SA21.1 — complete, ready)    (no open items — idle)
```

Cross-track dependency: SA21.2 (Track 2) → SA21.1 (Track 3 — complete), so SA21.2 is unblocked. Rebalancing history (2026-07-05/06, preserved for context): SA24/SA29/SA30 moved Track 2 → Track 1 and SA32 moved Track 2 → Track 3 to restore 3/3/2 parallelism when Track 2 was carrying six open items; SA26 then moved Track 2 → Track 3 for 1/2/1 parallelism. All of those items are now complete, so Tracks 1 and 3 are empty again — the next rebalance happens whenever new work is triaged onto them.

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

> **SA30 — complete.** Applied the SA17 direct-required-read pattern to listings/storage runtime settings — `listings/views.py`'s page-size read and `storage/helpers.py`'s backend normalization now raise `ImproperlyConfigured` on missing/invalid values instead of silently defaulting or coercing. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

### Track 2 — Module contracts & settings

#### Finding — `backups-sync-restore-blocks-worker` (`why →` [TA17](../others/tech-audit.md))

> **SA20 — complete.** Moved admin-triggered backup restore off the synchronous request path via async `subprocess.Popen` dispatch, with an atomic compare-and-swap claim, spawn-failure rollback preserving prior failure metadata, and forced `--local-only` resolution (CR-SA20-005 through CR-SA20-008, CR-SA20-REV-001/002 resolved). Full detail in [CHANGELOG.md](../../CHANGELOG.md).

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

> **SA26 — complete.** Sanitized markdown-rendered URI schemes on public blog/listing pages via a stdlib-only allowlist scheme check (`_sanitize_rendered_html()`), neutralizing `javascript:`/`data:`/`vbscript:` links including control-character/whitespace obfuscation variants (CR-SA26-001 hardening). Full detail in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
