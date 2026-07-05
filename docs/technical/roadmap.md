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

> **Closed batches (detail in [CHANGELOG.md](../../CHANGELOG.md)):** SA1–SA5 (2026-07-02), SA6–SA12 (2026-07-03), SA13.1–SA13.4 (2026-07-04), SA14.1–SA14.3 (2026-07-05 — TenantModelAdmin base + CRM/blog/forms/listings/billing admin ports), SA15.1–SA15.3 (2026-07-04), SA16.1/SA16.2 (2026-07-03), SA17.1–SA17.8 (2026-07-05 — module-side fail-hard + optional-dependency hardening + deprecated catalog delegates removed), SA18.1–SA18.11 (2026-07-04), SA19 (2026-07-05 — start.sh secret values removed from deploy logs). All closed per template rule — detail lives in CHANGELOG.md.

> **Track status (2026-07-05):** All three tracks clean to continue. One cross-track dependency: SA21.2 (Track 2) → SA21.1 (Track 3). Track 1: Finding `operator-read-path-undefined` (SA14) — SA14.1–SA14.3 complete (archived); SA14.4, SA14.5, SA14.6, SA23, and SA28 are ready. Track 2: SA20, SA21.2 (deps: SA21.1), SA24, SA26, SA29, SA30, and SA32 are ready. Track 3: SA21.1, SA22, SA25, SA27, SA31, and SA33 are ready. See batch sections below for `why →` finding links.

### Structural Autopsy Remediation III (opened 2026-07-03)

Fix plan derived from the [2026-07-03 fresh-pass autopsy](../others/arch-audit.md#autopsy--2026-07-03-fresh-full-pass) (4 structural findings, 3 now closed) and [tech-audit.md](../others/tech-audit.md) (fail-hard findings). Each task below is sized Adaptive **Tier 1 or Tier 2**; every task touching `orgs`/tenancy/RLS or billing floors at Tier 2 per the sensitive-domain rule.

**Naming:** continues the `SAn.m` sequence from `SA12` (last used). `SA13`, `SA15`, `SA16` close 3 of 4 structural findings (all fully closed — see above); SA14 (Finding 1, `operator-read-path-undefined`) remains open. `SA17`–`SA18` close the tech-audit fail-hard findings (`SA17` = module-side settings, `SA18` = core/CLI plumbing).

#### Dependency & parallelization overview (2026-07-04)

Finding 3 (`org-context-api-accretion`, SA13) is closed — see the closed-batches note above; Track 1's remaining work is Finding 1 (`operator-read-path-undefined`, SA14) alone. `registry-universe-mismatch` (SA15) and `per-module-knowledge-fanout` (SA16) are also closed. `SA18` (Track 3) is now fully closed — no remaining work in this batch. `SA17.8` (Track 2) is now complete — no remaining fail-hard tasks in this batch.

```
Track 1 (tenant-context surface)     Track 2 (module contracts & settings)      Track 3 (core/CLI plumbing)
───────────────────────────────      ───────────────────────────────────       ───────────────────────────
SA14.1 (no deps — complete)           SA17.5 (no deps — complete)               SA18.1–SA18.11 (all complete —
SA14.2 (deps: SA14.1 — complete)      SA17.6 (no deps — complete)                fully closed, no remaining
SA14.3 (deps: SA14.1 — complete)      SA17.7 (deps: SA17.5 — complete)           work in this batch)
SA14.4 (deps: SA14.2, SA14.3 — ready) SA17.8 (no deps — complete)
SA14.5 (no deps — ready)
SA14.6 (no deps — ready)
```

No cross-track dependencies — all three tracks can run fully in parallel.

#### Track summary

| Track | Tasks (in order) | Theme |
|-------|------------------|-------|
| **1** | SA14.4 (ready), SA14.5 (ready), SA14.6 (ready) | Operator/admin read-path contract (Finding 1) |
| **2** | *(fully closed from this batch)* | Module-side fail-hard follow-ups (SA17.1–SA17.8 archived) |
| **3** | *(fully closed from this batch)* | Core/CLI fail-hard plumbing (SA18.1–SA18.11 archived) |

---

#### Finding — `operator-read-path-undefined` (`why →` [Finding 1](../others/arch-audit.md#finding-1-elevatedoperator-reads-are-structurally-undefined--the-python-bypass-and-the-db-backstop-disagree))

> **SA14.1 — Build the orgs-owned `TenantModelAdmin` base (complete).** `Tier 2 · Track 1` — unblocks SA14.2/SA14.3. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

> **SA14.2 — Port CRM's 7 admin classes to `TenantModelAdmin` (complete).** `Tier 2 · Track 1 · deps: SA14.1` — review-driven follow-up CR-SA14.2-001 resolved (inline note `created_by` stamping). Full detail in [CHANGELOG.md](../../CHANGELOG.md).

> **SA14.3 — Port blog/forms/listings/billing admins to `TenantModelAdmin` (complete).** `Tier 2 · Track 1 · deps: SA14.1 · RISK LEVEL: medium` — review-driven follow-ups CR-SA14.3-001/002/003 resolved (FormSubmissionAdmin org-readonly on change; billing admin scoped-queryset regression tests). Full detail in [CHANGELOG.md](../../CHANGELOG.md).

- [ ] **SA14.4 — Flip module test suites' default DB role to `NOBYPASSRLS`.** `Tier 2 · Track 1 · deps: SA14.2, SA14.3 · RISK LEVEL: medium`
  Change the module test settings default from superuser (`QUICKSCALE_ALLOW_BYPASSRLS=1`) to the restricted runtime role, with superuser opt-in only for tests that explicitly need it (e.g. migration tests). This is the posture change that makes the operator-read bug class visible to CI going forward, so it must land *after* the admin ports (SA14.2/14.3) to avoid breaking the suites it's meant to protect.
  *Files:* `*/tests/settings.py` across modules.
  *Acceptance:* module test suites pass by default under the restricted role; only explicitly-marked tests opt into superuser/BYPASSRLS.

- [ ] **SA14.5 — Implement `operator_access(reason=...)` as a real, audited RLS predicate.** `Tier 2 · Track 1 · deps: none (SA13.1 complete) · RISK LEVEL: medium`
  Add `OR NULLIF(current_setting('app.operator_access', true), '') = 'on'` to the FORCE RLS policy template and implement `operator_access(reason=...)` (superuser-gated, audit-logged context manager) as the only setter — finally implementing the contract `decisions.md` already documents as a "permanent rule" but which exists in no code today.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py` (policy template), `current_org.py` (new context manager).
  *Acceptance:* `operator_access(reason=...)` grants true cross-tenant reads for its duration only, is audit-logged, and requires superuser; without it, no code path bypasses RLS.

- [ ] **SA14.6 — Fail-hard `QUICKSCALE_MODE` when orgs is installed.** `Tier 1 · Track 1 · deps: none`
  Replace `getattr(settings, "QUICKSCALE_MODE", "solo")` with a required-setting read that raises `ImproperlyConfigured` when `orgs` is installed and `QUICKSCALE_MODE` is unset, so a saas deployment can't silently flip to solo-mode tenancy.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/middleware.py:268`, `quickscale_modules/orgs/src/quickscale_modules_orgs/adapters.py:60`, `quickscale_modules/orgs/src/quickscale_modules_orgs/adapters.py:81`, `quickscale_modules/orgs/src/quickscale_modules_orgs/views.py:63`.
  *Acceptance:* omitting `QUICKSCALE_MODE` in a saas-mode generated project raises at startup instead of defaulting to `"solo"`.

---

### Fail-Hard Remediation (opened 2026-07-03)

Fix plan derived from [tech-audit.md](../others/tech-audit.md). `SA17` covers module-side settings defaults (Track 2); `SA18` covers core/CLI/generator plumbing (Track 3). Both continue the `SAn.m` sequence.

#### `SA17` — Module-side settings and config fail-hard fixes (Track 2)

> SA17.1–SA17.6 (legacy config keys, analytics/billing/CRM/forms/blog/notifications fail-hard settings — closes TA1 and fully closes TA2) are complete. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

> SA17.7–SA17.8 (optional-dependency hardening — closes TA9; deprecated catalog delegates removed, readiness fail-closed on unknown names — closes TA12) are complete. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

#### `SA18` — Core/CLI/generator plumbing fail-hard fixes (Track 3) — **fully closed 2026-07-04**

> SA18.1–SA18.11 (manifest adapter init, analytics manifest settings, `quickscale_cli.schema` shim removal, generator template resolution, version fallback, project-metadata resolution, `railway_utils.py` exception narrowing, `PORT` fail-hard, `step_capture_hashes` fail-hard on `OSError`, `# F-EXCEPTION:` tags on documented M2 compatibility paths, dev-tooling silent parse failure — closes TA3–TA8, TA10, TA11, TA13, TA14, and TA15) are complete. Track 3 has no remaining work from Structural Autopsy Remediation III. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

---

### Deep Technical Sweep Remediation (opened 2026-07-04)

Fix plan derived from the [2026-07-03/2026-07-04 deep technical sweeps](../others/tech-audit.md). `arch-audit.md` contributes no new untracked findings this batch — its only open finding, `operator-read-path-undefined`, is already fully tracked as `SA14` above. Of the tech-audit findings, `TA19` (`QUICKSCALE_MODE` permissive default) is already tracked as `SA14.6` and is **not** duplicated here; `TA9`, `TA12`, `TA13`, `TA14`, `TA15` are already tracked as `SA17.7`, `SA17.8`, (`SA18.9`, complete), `SA18.10`, `SA18.11` respectively (TA9 and TA12 now resolved). This batch originally covered `TA16`–`TA25`; `TA16` is resolved by SA19 (archived). Remaining still-open findings: `TA17`, `TA18`/`TA24` (same underlying defect, tracked jointly), `TA20`, `TA21`, `TA22`, `TA23`, `TA25`.

**Naming:** continues the `SAn` sequence from `SA18` (last used). Each task is sized Adaptive **Tier 1 or Tier 2**; any task touching `orgs`/tenancy/RLS or billing floors at Tier 2 per the sensitive-domain rule.

#### Dependency & parallelization overview (2026-07-04)

```
Track 1 (tenant-context surface)     Track 2 (module contracts & settings)      Track 3 (core/CLI plumbing)
───────────────────────────────      ───────────────────────────────────       ───────────────────────────
SA23 (no deps — ready)               SA20 (no deps — ready)                    SA21.1 (no deps — ready)
                                       SA21.2 (deps: SA21.1)                     SA22 (no deps — ready)
                                      SA24 (no deps — ready)                    SA22 (no deps — ready)
                                      SA26 (no deps — ready)                    SA25 (no deps — ready)
```

No cross-track dependencies except SA21.2 → SA21.1 (Track 2 waits on a Track 3 deliverable — the generator settings change must land before module throttles can be rewired to use it).

#### Track summary

| Track | Tasks (in order) | Theme |
|-------|------------------|-------|
| **1** | SA23 (ready) | Orgs debug-view open redirect |
| **2** | SA20 (ready), SA21.2 (deps: SA21.1), SA24 (ready), SA26 (ready) | Module-side hardening (backups restore, throttle wiring, XSS) |
| **3** | SA21.1 (ready), SA22 (ready), SA25 (ready) | Core/CLI/generator plumbing (cache/IP infra, apply ordering, hygiene) |

---

#### Finding — `startsh-secrets-in-deploy-logs` (`why →` [TA16](../others/tech-audit.md))

> SA19 — Stop `start.sh.j2` from printing secret values to deploy logs (complete — closes TA16). `Tier 1 · Track 3 · deps: none` Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `backups-sync-restore-blocks-worker` (`why →` [TA17](../others/tech-audit.md))

- [ ] **SA20 — Move admin-triggered backup restore off the synchronous request path.** `Tier 2 · Track 2 · deps: none · RISK LEVEL: medium`
  `restore_backup_artifact`/`restore_admin_uploaded_backup` currently run `pg_restore --clean` synchronously inside the admin POST handler, inside a 60s-capped gunicorn worker — large restores can exceed the timeout mid-restore, leaving the database partially restored. Move the restore to a background-executed step (management command invoked via subprocess, or a queued job) with the admin view returning immediately and surfacing progress/completion via polling or a status flag on the backup record.
  *Files:* `quickscale_modules/backups/src/quickscale_modules_backups/admin.py:419-437`.
  *Acceptance:* triggering a restore from the admin returns before the 60s worker timeout regardless of restore duration; the restore's success/failure is observable after the fact (status field, log, or notification); a restore that fails mid-way is distinguishable from one that never started.

#### Finding — `throttle-identity-and-backing-store-unreliable-behind-proxy` (`why →` [TA18/TA24](../others/tech-audit.md))

- [ ] **SA21.1 — Add canonical client-IP resolution and a shared cache backend to generated settings.** `Tier 2 · Track 3 · deps: none`
  Two related gaps in the generated project's settings: (a) no trusted-proxy client-IP convention, so `REMOTE_ADDR` is the Railway edge proxy's address, not the client's; (b) no `CACHES` backend, so DRF throttles and the blog rate limiter fall back to per-process `LocMemCache` — uncounted across workers/replicas and reset on every deploy. Add a `TRUSTED_PROXY_COUNT`/`USE_X_FORWARDED_FOR`-gated client-IP helper (or set DRF `NUM_PROXIES`) and a working shared-cache default (Redis on Railway, or `DatabaseCache` at minimum) wired into `DEFAULT_THROTTLE_CLASSES`.
  *Files:* `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/base.py.j2`, `.../production.py.j2:186-195`.
  *Acceptance:* a generated project has a resolvable canonical client-IP helper gated behind an explicit trusted-proxy setting, and a non-`LocMemCache` backend configured for production; single-host (no-proxy) deployments keep `REMOTE_ADDR` unless the setting is enabled.

- [ ] **SA21.2 — Wire forms/blog throttles and IP logging to the new canonical-IP and cache infrastructure.** `Tier 2 · Track 2 · deps: SA21.1`
  Point `FormSubmitThrottle.get_cache_key`, `_get_blog_api_rate_limit_ident`, and the IP fields recorded on `FormSubmission`/blog rate-limit logging at the canonical client-IP helper landed by SA21.1, and confirm both throttles run against the shared cache backend instead of the default in-memory one.
  *Files:* `quickscale_modules/forms/src/quickscale_modules_forms/throttles.py:26-30`, `quickscale_modules/forms/src/quickscale_modules_forms/views.py:231,257`, `quickscale_modules/blog/src/quickscale_modules_blog/views.py:260-266,277-304`.
  *Acceptance:* two requests with different `X-Forwarded-For` values (fixed `REMOTE_ADDR`) get independent throttle buckets and are logged with the forwarded client IP, not the proxy's; a 6th form submission within the configured window from one distinct client is rejected regardless of which worker/replica serves it.

#### Finding — `apply-force-wipes-before-generating` (`why →` [TA20](../others/tech-audit.md))

- [ ] **SA22 — Generate the replacement project before deleting the existing one on `apply --force`.** `Tier 2 · Track 3 · deps: none · RISK LEVEL: medium`
  `apply_command.py`'s `--force` path currently `rmtree`/`unlink`s the existing project content before generating its replacement into a temp dir; a generation failure after the wipe leaves the project deleted with nothing to restore. Reorder so generation happens into a temp/staging location first, validated, and only then swaps in over the existing content (or generation failure leaves the original untouched).
  *Files:* `quickscale_cli/src/quickscale_cli/commands/apply_command.py:1781-1792`.
  *Acceptance:* a forced generation failure (e.g. induced template error) leaves the pre-existing project directory intact; a successful forced apply still ends with the new content in place.

#### Finding — `debug-view-open-redirect` (`why →` [TA21](../others/tech-audit.md))

- [ ] **SA23 — Validate the `next` redirect target in orgs debug views.** `Tier 2 · Track 1 · deps: none · RISK LEVEL: medium`
  `orgs/debug_views.py:53-55,86-88` redirects to `request.POST.get("next")` unvalidated (superuser-only, POST-only, but still an open redirect). Validate with `django.utils.http.url_has_allowed_host_and_scheme` before redirecting; reject or fall back to a safe default on failure.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/debug_views.py:53-55,86-88`.
  *Acceptance:* a `next` value pointing off-site (or to a disallowed scheme) is rejected/falls back instead of being redirected to; same-host redirect targets continue to work.

#### Finding — `analytics-tags-mark-safe-unescaped` (`why →` [TA22](../others/tech-audit.md))

- [ ] **SA24 — Escape or `json_script` the analytics template tag payload.** `Tier 1 · Track 2 · deps: none`
  `analytics_tags.py:33` uses `mark_safe(json.dumps(payload))` without escaping `<`/`>`/`&`, which is latent stored-XSS if the payload ever carries request-influenced data. Switch to Django's `json_script` template filter/tag or manually escape those characters before marking safe.
  *Files:* `quickscale_modules/analytics/src/quickscale_modules_analytics/templatetags/analytics_tags.py:33`.
  *Acceptance:* a payload value containing `</script>` renders inert in the page source; existing analytics payload rendering is otherwise unchanged.

#### Finding — `committed-coverage-artifacts` (`why →` [TA23](../others/tech-audit.md))

- [ ] **SA25 — Untrack build/coverage artifacts and gitignore them.** `Tier 1 · Track 3 · deps: none`
  `coverage.json` and `pytest_cov_log.txt` are tracked in git; `htmlcov/` is present on disk. Remove from tracking and add patterns to `.gitignore`.
  *Files:* repo root `.gitignore`, `coverage.json`, `pytest_cov_log.txt`.
  *Acceptance:* `git status` after a fresh test run shows no untracked-artifact noise; the artifacts no longer appear in `git ls-files`.

#### Finding — `markdown-uri-scheme-stored-xss` (`why →` [TA25](../others/tech-audit.md))

- [ ] **SA26 — Sanitize markdown-rendered URI schemes on public blog/listing pages.** `Tier 2 · Track 2 · deps: none`
  `markdownify(escape(...))` blocks raw HTML injection but not markdown-native `[text](javascript:...)` links, which render as an unescaped `<a href="javascript:...">` under the `|safe` filter. Run the rendered HTML through an allowlist sanitizer (`bleach.clean`/`nh3`) restricting `href` schemes to `http`/`https`/`mailto`, or configure a markdown URL-sanitizing extension, before marking safe.
  *Files:* `quickscale_modules/blog/src/quickscale_modules_blog/views.py:787`, `quickscale_modules/listings/src/quickscale_modules_listings/views.py:304-305`, both post/listing detail templates.
  *Acceptance:* publishing a post/listing with a `javascript:` markdown link results in a stripped/neutralized `href` on the rendered detail page; legitimate `http(s)`/`mailto` markdown links continue to render as clickable anchors.

---

### Fail-Hard & Contract Gaps Remediation (opened 2026-07-05)

Fix plan derived from the [2026-07-05 tech-audit re-run + module-by-module deep pass](../others/tech-audit.md) (`TA26`–`TA32`). These are the findings the tech-audit header flags as **not yet batched**; `arch-audit.md`'s companion module-by-module pass produced zero new structural findings this round (see its Reconciliation log), so this batch is tech-audit-only. `TA19` remains tracked solely as `SA14.6` (not duplicated here, per the existing rule).

**Naming:** continues the `SAn` sequence from `SA26` (last used). Each task is sized Adaptive **Tier 1 or Tier 2**; any task touching `orgs`/tenancy/RLS or billing floors at Tier 2 per the sensitive-domain rule, regardless of the tech-audit's raw effort estimate.

#### Dependency & parallelization overview (2026-07-05)

```
Track 1 (tenant-context surface)     Track 2 (module contracts & settings)      Track 3 (core/CLI plumbing)
───────────────────────────────      ───────────────────────────────────       ───────────────────────────
SA28 (no deps — ready)                SA29 (no deps — ready)                    SA27 (no deps — ready)
                                       SA30 (no deps — ready, relates to SA29)   SA31 (no deps — ready)
                                       SA32 (no deps — ready)                    SA33 (no deps — ready)
```

No cross-track dependencies. `SA27` and `SA22` (prior batch) both touch `apply_command.py` — disjoint regions (validation gating vs. `--force` wipe ordering) but sequence within Track 3 to keep merges clean. `SA30` is not a hard dependency of `SA29` but fixes the runtime half of the same defect class (TA26 scenario 4 / TA31) — land `SA29` first so the fixed contract is what `SA30`'s direct-read pattern reads from.

#### Track summary

| Track | Tasks (in order) | Theme |
|-------|------------------|-------|
| **1** | SA28 (ready) | Account-deletion org invariant enforcement |
| **2** | SA29 (ready) → SA30 (ready), SA32 (ready) | Module config contracts & settings fail-hard |
| **3** | SA27 (ready), SA31 (ready), SA33 (ready) | Core/CLI validation gating & plumbing hygiene |

---

#### Finding — `module-option-validation-not-enforced-at-apply` (`why →` [TA26](../others/tech-audit.md))

- [ ] **SA27 — Enforce module-option validation on the apply path; remove the silent coercions it currently masks.** `Tier 2 · Track 3 · deps: none · RISK LEVEL: medium (touches orgs mode + storage backend derivation)`
  Three-part fix, one PR: (1) in `assemble_wiring_spec` (or `build_generic_manifest_spec`), raise `ManifestError` listing `result.validation_issues` when non-empty instead of discarding them; (2) add the missing `validate_{blog,forms,listings,storage,orgs}_module_options` calls to `_validate_module_prerequisites` (same pattern as the six modules already gated); (3) delete the silent coercions in `resolve_orgs_module_options` (invalid `mode` → `"solo"`), `resolve_storage_module_options` (invalid `backend` → `"local"`), and the blog `api_rate_limit` blank-coercion, so the validators' existing checks become reachable instead of dead code.
  *Files:* `quickscale_cli/src/quickscale_cli/commands/apply_command.py:984-1155`, `quickscale_core/src/quickscale_core/manifest/assembler.py` (`assemble_wiring_spec`), `quickscale_core/src/quickscale_core/contracts/resolvers.py` (`resolve_orgs_module_options:1239-1242`, `resolve_storage_module_options:1612-1614`, `normalize_blog_module_options:430-434,445-448`).
  *Acceptance:* apply with `modules.orgs.mode: "invalid"` aborts with a descriptive error naming the allowed values instead of silently generating a solo-mode project; apply with `modules.storage.backend: "s3compat"` aborts instead of silently dropping the S3 wiring; apply with `modules.forms.rate_limit: "10 per hour"` aborts at apply time instead of 500ing the public form endpoint at runtime; existing valid-config apply paths are unaffected.

#### Finding — `account-delete-cascade-bypasses-org-invariants` (`why →` [TA30](../others/tech-audit.md))

- [ ] **SA28 — Enforce the last-owner and personal-org invariants at the account-deletion boundary.** `Tier 2 · Track 1 · deps: none · RISK LEVEL: medium`
  `AccountDeleteView` hard-deletes the `User` row; `OrganizationMembership.user` is `on_delete=CASCADE`, which bypasses the last-owner guard living only in the overridden `Membership.delete()`/`save()` methods (Django's cascade collector never calls them). Add a boundary check (in the view, or a `pre_delete` receiver on the user model registered from orgs) that blocks deletion while the user is the last owner of any org with other members — naming the orgs and directing the user to transfer ownership first — and routes the user's personal org(s) through the existing purge/cancel machinery so any active Stripe subscription is canceled rather than orphaned. While touching the view, also fix the dead `delete()` override (Django ≥4.0 `DeleteView` routes POST through `form_valid`, so the success-message override likely never fires today).
  *Files:* `quickscale_modules/auth/src/quickscale_modules_auth/views.py:47-61` (`AccountDeleteView`), `quickscale_modules/orgs/src/quickscale_modules_orgs/models.py:115-118,231-249`, `quickscale_modules/orgs/src/quickscale_modules_orgs/signals.py` (new receiver, or the boundary check lives in the view), billing's existing `cancel_subscription` path.
  *Acceptance:* a test deleting the account of a shared org's sole owner is rejected with a descriptive error naming the org; a test deleting the account of a user whose only org is a personal org with an active subscription results in that subscription being canceled (not orphaned); the success message renders on a permitted deletion.

#### Finding — `storage-config-dead-env-docs-secrets-in-vcs` (`why →` [TA31](../others/tech-audit.md))

- [ ] **SA29 — Rebuild storage's config-delivery contract: env-var indirection for secrets, README aligned with the real wiring mechanism.** `Tier 2 · Track 2 · deps: none`
  Storage is the only secret-bearing module without the `*_env_var` indirection pattern analytics/notifications/billing already use, and its README documents a config channel (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/etc. as deploy-time env vars) that the generated app never reads — settings are baked as literals at generation time. Adopt the indirection pattern: storage credential options become `*_env_var` names (adapter emits `os.environ` reads into the managed settings module rather than baked literal values), keep `backend`/bucket/region as non-secret yml options, and rewrite the README against the real contract.
  *Files:* `quickscale_core/src/quickscale_core/manifest/entry_point.py:1269-1348` (`_storage_manifest_adapter`), `quickscale_core/src/quickscale_core/module_wiring.py:85-100`, `quickscale_core/src/quickscale_core/generator/templates/README.md.j2:265-286`, storage's `module.yml` option declarations.
  *Acceptance:* generating a project configured per the rewritten README and deploying with the documented env vars set results in uploads landing in the configured S3/R2 bucket; the generated `settings/modules.py` contains no credential material; leaving storage on `local` still works with no config required.

#### Finding — `listings-storage-runtime-fail-open-residuals` (`why →` [TA32](../others/tech-audit.md))

- [ ] **SA30 — Apply the SA17 direct-required-read pattern to listings/storage runtime settings.** `Tier 1 · Track 2 · deps: none (relates to SA29 — land after so storage's fixed contract is what this reads from)`
  `listings/views.py`'s `_get_positive_int_setting` and `storage/helpers.py`'s `_read_setting`/`_normalize_backend` silently default or coerce on missing/invalid values — the same class SA17.2–SA17.6 closed for other modules, but listings and storage were outside that batch's scope. Replace with direct required reads that raise `ImproperlyConfigured` on missing/invalid values, matching the SA17 shape.
  *Files:* `quickscale_modules/listings/src/quickscale_modules_listings/views.py:30-70`, `quickscale_modules/storage/src/quickscale_modules_storage/helpers.py:35-115`.
  *Acceptance:* an invalid/missing `LISTINGS_PER_PAGE` or `QUICKSCALE_STORAGE_BACKEND` value raises a descriptive startup error instead of silently falling back; valid configurations are unaffected.

#### Finding — `railway-cli-secrets-on-argv` (`why →` [TA27](../others/tech-audit.md))

- [ ] **SA31 — Move Railway/DR adapter secrets off process argv.** `Tier 1 · Track 3 · deps: none`
  `railway_utils.py` invokes `railway variables --set KEY=VALUE` with live secret values on the command line, and `dr_commands.py` passes `--args-json` on `docker exec` argv — both visible to any local user via `ps`/`/proc` on shared hosts. Switch to stdin transport for the adapter JSON payload; for the Railway CLI (which has no stdin-based `--set`), document the CLI limitation and scope the fix to what's actually controllable (e.g. minimize the exposure window, or investigate `railway variables --set` alternatives such as a batch file input if the CLI supports one).
  *Files:* `quickscale_cli/src/quickscale_cli/utils/railway_utils.py:348,391,891`, `quickscale_cli/src/quickscale_cli/commands/dr_commands.py:232-242`.
  *Acceptance:* the DR adapter's JSON payload no longer appears in `docker exec` argv (stdin transport verified via a process-argv assertion in tests); the Railway CLI limitation (if unfixable) is documented in code comments and this finding's closeout note.

#### Finding — `invalidate-social-cache-org-unaware` (`why →` [TA28](../others/tech-audit.md))

- [ ] **SA32 — Fix or retire `invalidate_social_cache()`.** `Tier 1 · Track 2 · deps: none`
  The exported `invalidate_social_cache()` clears only bare cache keys, a no-op for the org-partitioned keys actually used under tenant context (model `save()`/`delete()` invalidate correctly; this function is uncalled by first-party code but is a public-API trap for bulk mutations like `queryset.update()` that bypass `save()`). Either make it org-aware (accept/iterate org context) or remove it from `__all__` so it stops looking like a safe bulk-invalidation tool.
  *Files:* `quickscale_modules/social/src/quickscale_modules_social/services.py:182-184`.
  *Acceptance:* either a test demonstrates `invalidate_social_cache()` correctly invalidates org-partitioned entries, or the function is dropped from the module's public `__all__` with a comment explaining why.

#### Finding — `dangling-arch-audit-anchor` (`why →` [TA29](../others/tech-audit.md))

- [ ] **SA33 — Fix the dangling `decisions.md` → `arch-audit.md` anchor link.** `Tier 1 · Track 3 · deps: none`
  `decisions.md:650` links to `arch-audit.md#finding-4-per-module-contract-knowledge-…`, a heading dropped in the 2026-07-04 arch-audit closeout. Point it at the current reconciliation-log entry or the `roadmap.md` T2.4/T2.5 tracking item it was originally describing.
  *Files:* `docs/technical/decisions.md:650`.
  *Acceptance:* the link resolves to a real, current anchor; no other dangling cross-doc anchors are introduced.

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
