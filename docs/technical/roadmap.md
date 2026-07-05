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

> **Closed batches (detail in [CHANGELOG.md](../../CHANGELOG.md)):** SA1–SA5 (2026-07-02), SA6–SA12 (2026-07-03), SA13.1–SA13.4 (2026-07-04), SA15.1–SA15.3 (2026-07-04), SA16.1/SA16.2 (2026-07-03), SA17.1–SA17.7 (2026-07-04), SA18.1–SA18.11 (2026-07-04). SA14.1 (TenantModelAdmin base) complete, unblocking SA14.2/SA14.3. All closed per template rule — detail lives in CHANGELOG.md.

> **Track status (2026-07-05):** Track 2 SA20 is in-progress/blocked by CR-SA20-005; Tracks 1 and 3 are clean to continue. One cross-track dependency: SA21.2 (Track 2) → SA21.1 (Track 3). Track 1: SA14.3 ready (deps SA14.1 complete), SA14.5/SA14.6/SA23 ready; SA14.4 waits on SA14.3. Track 2: SA17.8 complete, **SA20 in-progress/blocked**, SA24/SA26 ready; SA21.2 waits on SA21.1. Track 3: SA19/SA21.1/SA22/SA25 ready.

### Structural Autopsy Remediation III (opened 2026-07-03)

Fix plan derived from the [2026-07-03 fresh-pass autopsy](../../arch-audit.md#autopsy--2026-07-03-fresh-full-pass) (4 structural findings, 3 now closed) and [tech-audit.md](../../tech-audit.md) (fail-hard findings). Each task below is sized Adaptive **Tier 1 or Tier 2**; every task touching `orgs`/tenancy/RLS or billing floors at Tier 2 per the sensitive-domain rule.

**Naming:** continues the `SAn.m` sequence from `SA12` (last used). `SA13`, `SA15`, `SA16` close 3 of 4 structural findings (all fully closed — see above); SA14 (Finding 1, `operator-read-path-undefined`) remains open. `SA17`–`SA18` close the tech-audit fail-hard findings (`SA17` = module-side settings, `SA18` = core/CLI plumbing).

#### Dependency & parallelization overview (2026-07-04)

Finding 3 (`org-context-api-accretion`, SA13) is closed — see the closed-batches note above; Track 1's remaining work is Finding 1 (`operator-read-path-undefined`, SA14) alone. `registry-universe-mismatch` (SA15) and `per-module-knowledge-fanout` (SA16) are also closed. `SA18` (Track 3) is now fully closed — no remaining work in this batch. `SA17.8` (Track 2) is now complete — no remaining fail-hard tasks in this batch.

```
Track 1 (tenant-context surface)     Track 2 (module contracts & settings)      Track 3 (core/CLI plumbing)
───────────────────────────────      ───────────────────────────────────       ───────────────────────────
SA14.1 (no deps — complete)           SA17.5 (no deps — complete)               SA18.1–SA18.11 (all complete —
SA14.2 (deps: SA14.1 — complete)      SA17.6 (no deps — complete)                fully closed, no remaining
SA14.3 (deps: SA14.1 — ready)         SA17.7 (deps: SA17.5 — complete)           work in this batch)
SA14.4 (deps: SA14.2, SA14.3)         SA17.8 (no deps — complete)
SA14.5 (no deps — ready)
SA14.6 (no deps — ready)
```

No cross-track dependencies — all three tracks can run fully in parallel.

#### Track summary

| Track | Tasks (in order) | Theme |
|-------|------------------|-------|
| **1** | SA14.1 (complete) → SA14.2 (complete) → SA14.3 (ready) → SA14.4, plus SA14.5 (ready), SA14.6 (ready) | Operator/admin read-path contract (Finding 1; Finding 3 closed) |
| **2** | SA17.1–SA17.7 (complete); SA17.8 (complete) — TA12 closed, Track 2 fully closed | Module-side fail-hard follow-ups (TA2 closed by SA17.6; TA9/TA12) |
| **3** | SA18.1–SA18.11 — fully closed, no remaining work in this batch | Core/CLI fail-hard plumbing |

---



#### Finding — `operator-read-path-undefined` (`why →` [Finding 1](../../arch-audit.md#finding-1-elevatedoperator-reads-are-structurally-undefined--the-python-bypass-and-the-db-backstop-disagree))

> **SA14.1 — Build the orgs-owned `TenantModelAdmin` base (complete).** `Tier 2 · Track 1` — unblocks SA14.2/SA14.3. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

- [x] **SA14.2 — Port CRM's 7 admin classes to `TenantModelAdmin`.** `Tier 2 · Track 1 · deps: SA14.1`
  CRM admin ported. See [CHANGELOG.md](../../CHANGELOG.md) for closeout detail.

- [ ] **SA14.3 — Port blog/forms/listings/billing admins to `TenantModelAdmin`.** `Tier 2 · Track 1 · deps: SA14.1 · RISK LEVEL: medium`
  Same port as SA14.2 for the remaining modules' admin classes. Runs in parallel with SA14.2 — disjoint files.
  *Files:* `blog/admin.py`, `forms/admin.py`, `listings/admin.py`, `billing/admin.py`.
  *Acceptance:* same as SA14.2 for these modules.

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

Fix plan derived from [tech-audit.md](../../tech-audit.md). `SA17` covers module-side settings defaults (Track 2); `SA18` covers core/CLI/generator plumbing (Track 3). Both continue the `SAn.m` sequence.

#### `SA17` — Module-side settings and config fail-hard fixes (Track 2)

> SA17.1–SA17.6 (legacy config keys, analytics/billing/CRM/forms/blog/notifications fail-hard settings — closes TA1 and fully closes TA2) are complete. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA17.7 — Replace optional-dependency soft degradation with generation-time wiring (complete).** `Tier 2 · Track 2 · deps: SA17.5 (SA17.2 complete) · (why → TA9)`
  PostHog import hardened to hard failure; import-seam sentinel regression. See [CHANGELOG.md](../../CHANGELOG.md) for closeout detail.

- [x] **SA17.8 — Remove or gate deprecated `module_catalog` compat delegates; fix fail-open readiness.** `Tier 1 · Track 2 · deps: none · (why → TA12)`
  Removed `get_module_names()`/`get_module_entries()` from the public `contracts/__init__.py` API (zero production callers confirmed by discovery; no `# F-EXCEPTION:` tag needed). Made `get_module_readiness_reason()` raise `ValueError` for unrecognized module names instead of returning `None` (previously indistinguishable from "ready"). Updated core and CLI test suites to remove deleted-function tests and assert the new raise-on-unknown behavior. Removed the two deprecated function bodies from `module_catalog.py`.
  *Files:* `quickscale_core/src/quickscale_core/contracts/module_catalog.py:128-187`, `contracts/__init__.py`, `quickscale_core/tests/test_module_catalog.py`, `quickscale_cli/tests/test_module_catalog.py`.
  *Acceptance:* the deprecated delegates are removed from the public API (no `# F-EXCEPTION:` tag); readiness checks on an unknown module name raise `ValueError` with a descriptive message; core and CLI test suites pass.
  *Findings:* Zero production callers for `get_module_names`/`get_module_entries` confirmed — clean removal. No `# F-EXCEPTION:` tag required. The `ValueError` message uses the format `"Unknown module name '...'. Expected a known QuickScale module name."`

#### `SA18` — Core/CLI/generator plumbing fail-hard fixes (Track 3) — **fully closed 2026-07-04**

> SA18.1–SA18.11 (manifest adapter init, analytics manifest settings, `quickscale_cli.schema` shim removal, generator template resolution, version fallback, project-metadata resolution, `railway_utils.py` exception narrowing, `PORT` fail-hard, `step_capture_hashes` fail-hard on `OSError`, `# F-EXCEPTION:` tags on documented M2 compatibility paths, dev-tooling silent parse failure — closes TA3–TA8, TA10, TA11, TA13, TA14, and TA15) are complete. Track 3 has no remaining work from Structural Autopsy Remediation III. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

---

### Deep Technical Sweep Remediation (opened 2026-07-04)

Fix plan derived from the [2026-07-03/2026-07-04 deep technical sweeps](../../tech-audit.md) (`TA16`–`TA25`). `arch-audit.md` contributes no new untracked findings this batch — its only open finding, `operator-read-path-undefined`, is already fully tracked as `SA14` above. Of the tech-audit findings, `TA19` (`QUICKSCALE_MODE` permissive default) is already tracked as `SA14.6` and is **not** duplicated here; `TA9`, `TA12`, `TA13`, `TA14`, `TA15` are already tracked as `SA17.7`, `SA17.8`, (`SA18.9`, complete), `SA18.10`, `SA18.11` respectively. This batch covers the remaining still-open findings: `TA16`, `TA17`, `TA18`/`TA24` (same underlying defect, tracked jointly), `TA20`, `TA21`, `TA22`, `TA23`, `TA25`.

**Naming:** continues the `SAn` sequence from `SA18` (last used). Each task is sized Adaptive **Tier 1 or Tier 2**; any task touching `orgs`/tenancy/RLS or billing floors at Tier 2 per the sensitive-domain rule.

#### Dependency & parallelization overview (2026-07-04)

```
Track 1 (tenant-context surface)     Track 2 (module contracts & settings)      Track 3 (core/CLI plumbing)
───────────────────────────────      ───────────────────────────────────       ───────────────────────────
SA23 (no deps — ready)               SA20 (no deps — ready)                    SA19 (no deps — ready)
                                      SA21.2 (deps: SA21.1)                     SA21.1 (no deps — ready)
                                      SA24 (no deps — ready)                    SA22 (no deps — ready)
                                      SA26 (no deps — ready)                    SA25 (no deps — ready)
```

No cross-track dependencies except SA21.2 → SA21.1 (Track 2 waits on a Track 3 deliverable — the generator settings change must land before module throttles can be rewired to use it).

#### Track summary

| Track | Tasks (in order) | Theme |
|-------|------------------|-------|
| **1** | SA23 (ready) | Orgs debug-view open redirect |
| **2** | SA20 (in-progress/blocked), SA21.2 (deps: SA21.1), SA24 (ready), SA26 (ready) | Module-side hardening (backups restore, throttle wiring, XSS) |
| **3** | SA19 (ready), SA21.1 (ready), SA22 (ready), SA25 (ready) | Core/CLI/generator plumbing (secrets logging, cache/IP infra, apply ordering, hygiene) |

---

#### Finding — `startsh-secrets-in-deploy-logs` (`why →` [TA16](../../tech-audit.md))

- [ ] **SA19 — Stop `start.sh.j2` from printing secret values to deploy logs.** `Tier 1 · Track 3 · deps: none`
  Replace the `env | grep -E '(DATABASE_URL|SECRET_KEY|...)'` environment-check step with one that prints only variable *names* and a set/missing status, never values.
  *Files:* `quickscale_core/src/quickscale_core/generator/templates/start.sh.j2`.
  *Acceptance:* container boot logs show `SECRET_KEY: set` / `DATABASE_URL: set` (or `MISSING`) but never the underlying value; existing missing-var fail-hard behavior is unchanged.

#### Finding — `backups-sync-restore-blocks-worker` (`why →` [TA17](../../tech-audit.md))

- [ ] **SA20 — Move admin-triggered backup restore off the synchronous request path.** `Tier 2 · Track 2 · deps: none · RISK LEVEL: medium`
  **In progress — blocked by CR-SA20-005.** Track 2 worktree has made substantial progress on the async restore lifecycle:
  - **Async dispatch:** Restore no longer runs synchronously in-request. Admin sets `STATUS_RESTORING` and dispatches `backups_restore` management command via `subprocess.Popen`, returning immediately.
  - **Restore status lifecycle:** `BackupArtifact` tracks `STATUS_RESTORING`, `restore_started_at`, and `restore_error`. Management command persists failure on `BackupError`.
  - **Spawn-failure rollback:** A failed `subprocess.Popen` reverts `STATUS_RESTORING` to avoid stranded restoring state.
  - **Uploaded-file path parity:** Uploaded-file restore shares the trusted resolver / staging seam used by the existing admin download/restore path.
  - **Admin regression coverage:** Tests cover trusted-match rejection, incomplete-snapshot rejection, out-of-tree remap, and attempted symlink remap.

  **Blocker CR-SA20-005 (high, blocking, security-boundary):** The async uploaded-file restore remap can still follow a preexisting symlink at the authoritative destination and write outside the backup root. A focused fix cycle is required before the code can merge.

  **Needed decision/action:** Another focused fix cycle is required before the code can merge, or leave SA20 open for a future hardening batch.
  *Files:* `quickscale_modules/backups/src/quickscale_modules_backups/admin.py`, `models.py`, `management/commands/backups_restore.py`, `templates/admin/.../restore.html`, `migrations/0005_backupartifact_restore_execution.py`, `tests/test_admin.py`.
  *Acceptance:* triggering a restore from the admin returns before the 60s worker timeout regardless of restore duration; the restore's success/failure is observable after the fact (status field, `restore_error`, log, or notification); a restore that fails mid-way is distinguishable from one that never started (`STATUS_FAILED + restore_error` vs `STATUS_RESTORING`). **Still pending — blocked by CR-SA20-005.**

#### Finding — `throttle-identity-and-backing-store-unreliable-behind-proxy` (`why →` [TA18/TA24](../../tech-audit.md))

- [ ] **SA21.1 — Add canonical client-IP resolution and a shared cache backend to generated settings.** `Tier 2 · Track 3 · deps: none`
  Two related gaps in the generated project's settings: (a) no trusted-proxy client-IP convention, so `REMOTE_ADDR` is the Railway edge proxy's address, not the client's; (b) no `CACHES` backend, so DRF throttles and the blog rate limiter fall back to per-process `LocMemCache` — uncounted across workers/replicas and reset on every deploy. Add a `TRUSTED_PROXY_COUNT`/`USE_X_FORWARDED_FOR`-gated client-IP helper (or set DRF `NUM_PROXIES`) and a working shared-cache default (Redis on Railway, or `DatabaseCache` at minimum) wired into `DEFAULT_THROTTLE_CLASSES`.
  *Files:* `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/base.py.j2`, `.../production.py.j2:186-195`.
  *Acceptance:* a generated project has a resolvable canonical client-IP helper gated behind an explicit trusted-proxy setting, and a non-`LocMemCache` backend configured for production; single-host (no-proxy) deployments keep `REMOTE_ADDR` unless the setting is enabled.

- [ ] **SA21.2 — Wire forms/blog throttles and IP logging to the new canonical-IP and cache infrastructure.** `Tier 2 · Track 2 · deps: SA21.1`
  Point `FormSubmitThrottle.get_cache_key`, `_get_blog_api_rate_limit_ident`, and the IP fields recorded on `FormSubmission`/blog rate-limit logging at the canonical client-IP helper landed by SA21.1, and confirm both throttles run against the shared cache backend instead of the default in-memory one.
  *Files:* `quickscale_modules/forms/src/quickscale_modules_forms/throttles.py:26-30`, `quickscale_modules/forms/src/quickscale_modules_forms/views.py:231,257`, `quickscale_modules/blog/src/quickscale_modules_blog/views.py:260-266,277-304`.
  *Acceptance:* two requests with different `X-Forwarded-For` values (fixed `REMOTE_ADDR`) get independent throttle buckets and are logged with the forwarded client IP, not the proxy's; a 6th form submission within the configured window from one distinct client is rejected regardless of which worker/replica serves it.

#### Finding — `apply-force-wipes-before-generating` (`why →` [TA20](../../tech-audit.md))

- [ ] **SA22 — Generate the replacement project before deleting the existing one on `apply --force`.** `Tier 2 · Track 3 · deps: none · RISK LEVEL: medium`
  `apply_command.py`'s `--force` path currently `rmtree`/`unlink`s the existing project content before generating its replacement into a temp dir; a generation failure after the wipe leaves the project deleted with nothing to restore. Reorder so generation happens into a temp/staging location first, validated, and only then swaps in over the existing content (or generation failure leaves the original untouched).
  *Files:* `quickscale_cli/src/quickscale_cli/commands/apply_command.py:1781-1792`.
  *Acceptance:* a forced generation failure (e.g. induced template error) leaves the pre-existing project directory intact; a successful forced apply still ends with the new content in place.

#### Finding — `debug-view-open-redirect` (`why →` [TA21](../../tech-audit.md))

- [ ] **SA23 — Validate the `next` redirect target in orgs debug views.** `Tier 2 · Track 1 · deps: none · RISK LEVEL: medium`
  `orgs/debug_views.py:53-55,86-88` redirects to `request.POST.get("next")` unvalidated (superuser-only, POST-only, but still an open redirect). Validate with `django.utils.http.url_has_allowed_host_and_scheme` before redirecting; reject or fall back to a safe default on failure.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/debug_views.py:53-55,86-88`.
  *Acceptance:* a `next` value pointing off-site (or to a disallowed scheme) is rejected/falls back instead of being redirected to; same-host redirect targets continue to work.

#### Finding — `analytics-tags-mark-safe-unescaped` (`why →` [TA22](../../tech-audit.md))

- [ ] **SA24 — Escape or `json_script` the analytics template tag payload.** `Tier 1 · Track 2 · deps: none`
  `analytics_tags.py:33` uses `mark_safe(json.dumps(payload))` without escaping `<`/`>`/`&`, which is latent stored-XSS if the payload ever carries request-influenced data. Switch to Django's `json_script` template filter/tag or manually escape those characters before marking safe.
  *Files:* `quickscale_modules/analytics/src/quickscale_modules_analytics/templatetags/analytics_tags.py:33`.
  *Acceptance:* a payload value containing `</script>` renders inert in the page source; existing analytics payload rendering is otherwise unchanged.

#### Finding — `committed-coverage-artifacts` (`why →` [TA23](../../tech-audit.md))

- [ ] **SA25 — Untrack build/coverage artifacts and gitignore them.** `Tier 1 · Track 3 · deps: none`
  `coverage.json` and `pytest_cov_log.txt` are tracked in git; `htmlcov/` is present on disk. Remove from tracking and add patterns to `.gitignore`.
  *Files:* repo root `.gitignore`, `coverage.json`, `pytest_cov_log.txt`.
  *Acceptance:* `git status` after a fresh test run shows no untracked-artifact noise; the artifacts no longer appear in `git ls-files`.

#### Finding — `markdown-uri-scheme-stored-xss` (`why →` [TA25](../../tech-audit.md))

- [ ] **SA26 — Sanitize markdown-rendered URI schemes on public blog/listing pages.** `Tier 2 · Track 2 · deps: none`
  `markdownify(escape(...))` blocks raw HTML injection but not markdown-native `[text](javascript:...)` links, which render as an unescaped `<a href="javascript:...">` under the `|safe` filter. Run the rendered HTML through an allowlist sanitizer (`bleach.clean`/`nh3`) restricting `href` schemes to `http`/`https`/`mailto`, or configure a markdown URL-sanitizing extension, before marking safe.
  *Files:* `quickscale_modules/blog/src/quickscale_modules_blog/views.py:787`, `quickscale_modules/listings/src/quickscale_modules_listings/views.py:304-305`, both post/listing detail templates.
  *Acceptance:* publishing a post/listing with a `javascript:` markdown link results in a stripped/neutralized `href` on the rendered detail page; legitimate `http(s)`/`mailto` markdown links continue to render as clickable anchors.

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../../arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../../tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
