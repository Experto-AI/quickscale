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

> **Closed batches (fully resolved, dropped per template rule — detail lives in [CHANGELOG.md](../../CHANGELOG.md)):** Structural Autopsy Remediation I (SA1–SA5, closed 2026-07-02) and II (SA6–SA12, closed 2026-07-03) — repo Findings 2–5 and Module Finding 1 are fully resolved with no open tasks. Within Remediation III: Finding `registry-universe-mismatch` (SA15.1–SA15.3, closed 2026-07-04), Finding `per-module-knowledge-fanout` (SA16.1/SA16.2, closed 2026-07-03), and Finding `org-context-api-accretion` (SA13.1–SA13.4, entire finding, closed 2026-07-04) are fully resolved and dropped from both this file and arch-audit.md. Within the Fail-Hard Remediation batch: `SA17.1`–`SA17.4` (Track 2 — legacy config keys, analytics/billing/CRM/forms settings, closes TA1/TA2-partial) and `SA18.1`–`SA18.7` (Track 3 — manifest/version/template/project-metadata/railway-utils fail-hard fixes, closes TA3–TA8 and TA10) are closed — see CHANGELOG.md.

> **Track status (2026-07-04):** All three tracks are clean to continue in parallel — no cross-track dependencies and no unresolved blockers. Track 1: Finding `org-context-api-accretion` (SA13.1–SA13.4) is fully closed; remaining work is Finding `operator-read-path-undefined` (SA14.1–SA14.6) — SA14.1, SA14.5, SA14.6 are ready now (no deps), SA14.2/SA14.3 wait on SA14.1, SA14.4 waits on SA14.2+SA14.3. Track 2: SA17.1–SA17.5 are complete; SA17.6 and SA17.8 are ready now; SA17.7 is unblocked/ready (SA17.5 complete). Track 3: SA18.1–SA18.8 are complete; SA18.9, SA18.10, and SA18.11 are ready now (no deps; SA18.9 decision already made — fail hard on OSError).

### Structural Autopsy Remediation III (opened 2026-07-03)

Fix plan derived from the [2026-07-03 fresh-pass autopsy](../../arch-audit.md#autopsy--2026-07-03-fresh-full-pass) (4 structural findings, 2 now closed) and [tech-audit.md](../../tech-audit.md) (fail-hard findings). Each task below is sized Adaptive **Tier 1 or Tier 2**; every task touching `orgs`/tenancy/RLS or billing floors at Tier 2 per the sensitive-domain rule.

**Naming:** continues the `SAn.m` sequence from `SA12` (last used). `SA13`–`SA16` close the 2026-07-03 structural findings (`SA15` and `SA16` fully closed — see above); `SA17`–`SA18` close the tech-audit fail-hard findings (`SA17` = module-side settings, `SA18` = core/CLI plumbing).

#### Dependency & parallelization overview (2026-07-04)

Finding 3 (`org-context-api-accretion`, SA13) is closed — see the closed-batches note above; Track 1's remaining work is Finding 1 (`operator-read-path-undefined`, SA14) alone. `registry-universe-mismatch` (SA15) and `per-module-knowledge-fanout` (SA16) are also closed. The fail-hard tasks (SA17, SA18) are file-scoped and independent of the structural work and of each other, aside from two noted internal orderings.

```
Track 1 (tenant-context surface)     Track 2 (module contracts & settings)      Track 3 (core/CLI plumbing)
───────────────────────────────      ───────────────────────────────────       ───────────────────────────
SA14.1 (no deps — ready)             SA17.5 (no deps — complete)               SA18.6 (no deps — complete)
SA14.2 (deps: SA14.1)                SA17.6 (no deps — ready)                  SA18.7 (no deps — complete)
SA14.3 (deps: SA14.1)                SA17.7 (deps: SA17.5 — ready)             SA18.8 (no deps — complete)
SA14.4 (deps: SA14.2, SA14.3)        SA17.8 (no deps — ready)                  SA18.9 (no deps — ready)
SA14.5 (no deps — ready)                                                  SA18.10 (no deps — ready)
SA14.6 (no deps — ready)                                                  SA18.11 (no deps — ready)
```

No cross-track dependencies — all three tracks can run fully in parallel.

#### Track summary

| Track | Tasks (in order) | Theme |
|-------|------------------|-------|
| **1** | SA14.1 (ready) → {SA14.2, SA14.3} → SA14.4, plus SA14.5 (ready), SA14.6 (ready) | Operator/admin read-path contract (Finding 1; Finding 3 closed) |
| **2** | SA17.1–SA17.5 (complete); SA17.6 and SA17.8 (ready); SA17.7 (ready, deps met) | Module-side fail-hard settings (Finding 2/TA2 not fully closed until SA17.6 lands) |
| **3** | SA18.6–SA18.8 (complete), SA18.9–SA18.11 (ready, no deps) | Core/CLI fail-hard plumbing |

---



#### Finding — `operator-read-path-undefined` (`why →` [Finding 1](../../arch-audit.md#finding-1-elevatedoperator-reads-are-structurally-undefined--the-python-bypass-and-the-db-backstop-disagree))

- [ ] **SA14.1 — Build the orgs-owned `TenantModelAdmin` base.** `Tier 2 · Track 1 · deps: none (SA13.1 complete) · RISK LEVEL: medium`
  Add an org-resolving, `org_scope`-wrapping `TenantModelAdmin` (or `AdminSite`) to `orgs` that resolves the VIEW-AS/session org and wraps changelist/change views accordingly — generalizing the pattern social's admin already proves works under RLS.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/admin.py` (new base class).
  *Acceptance:* a model admin subclassing `TenantModelAdmin` shows the VIEW-AS-resolved org's rows under the restricted `NOBYPASSRLS` role and denies cross-tenant rows without an explicit operator grant.

- [ ] **SA14.2 — Port CRM's 8 admins to `TenantModelAdmin`.** `Tier 2 · Track 1 · deps: SA14.1 · RISK LEVEL: medium`
  Replace `all_objects.all()` "cross-tenant visibility" idiom in CRM's `ModelAdmin`s with the new base; delete the now-inaccurate comments.
  *Files:* `quickscale_modules/crm/src/quickscale_modules_crm/admin.py`.
  *Acceptance:* CRM admin changelists render correctly under the restricted role in a manual/E2E check; no `all_objects` reference remains in `crm/admin.py`.

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
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/middleware.py:268`.
  *Acceptance:* omitting `QUICKSCALE_MODE` in a saas-mode generated project raises at startup instead of defaulting to `"solo"`.

---

### Fail-Hard Remediation (opened 2026-07-03)

Fix plan derived from [tech-audit.md](../../tech-audit.md). `SA17` covers module-side settings defaults (Track 2); `SA18` covers core/CLI/generator plumbing (Track 3). Both continue the `SAn.m` sequence.

#### `SA17` — Module-side settings and config fail-hard fixes (Track 2)

> SA17.1–SA17.4 (legacy config keys, analytics/billing/CRM/forms fail-hard settings — closes TA1 and the CRM/forms slice of TA2) are complete. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA17.5 — Fail-hard blog module settings (complete).** `Tier 2 · Track 2 · deps: none · (why → TA2)`
  Added `AppConfig.ready()` startup guard to `blog/apps.py` that raises `ImproperlyConfigured` at startup when `BLOG_ENABLE_RSS` is missing, `MEDIA_URL` is empty/unset, or any `BLOG_API_TOKENS` entry is malformed (naming the bad entry). Removed the default-`True` fallback in `urls.py:_blog_enable_rss()` and the `getattr(settings, "MEDIA_URL", "/media/")` fallbacks in `views.py:_build_media_response_url()` and `models.py:_build_public_media_url()`. Updated test settings with the required `BLOG_ENABLE_RSS = True`. Updated `test_urls.py` to remove the `None`-unset parametrize case. Added `blog/tests/test_apps.py` with 9 ready()-method guard tests (3 general + 6 malformed-token variations). Acceptance: a malformed `BLOG_API_TOKENS` entry raises at startup naming the bad entry; RSS-enable and media-URL settings are required, not defaulted. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [ ] **SA17.6 — Fail-hard notifications module settings.** `Tier 1 · Track 2 · deps: none · (why → TA2)`
  Require explicit enabled-flag and provider settings instead of defaulting to `True`/`"resend"`.
  *Files:* `notifications/services.py:155-157`.
  *Acceptance:* omitting either setting raises at startup instead of silently enabling the "resend" provider.

- [ ] **SA17.7 — Replace optional-dependency soft degradation with generation-time wiring.** `Tier 2 · Track 2 · deps: SA17.5 (SA17.2 complete) · (why → TA9)`
  Analytics' PostHog SDK import failure currently logs a warning and disables capture; forms' analytics integration currently probes for the sibling module via a soft `ImportError`/`getattr(None)` chain. Since module assembly happens at generation time, wire the analytics↔forms integration (and the PostHog SDK requirement) as a hard dependency the generator resolves, not a runtime probe. Depends on SA17.5 landing the surrounding settings checks first so the two changes don't fight over the same code paths (SA17.2's half of this ordering is already satisfied — it's complete).
  *Files:* `analytics/services.py:218-223`, `forms/views.py:92-97`.
  *Acceptance:* if analytics is assembled into a project, a missing PostHog SDK raises at startup (not a warning); forms' analytics integration is generation-time wired, not runtime-probed.

- [ ] **SA17.8 — Remove or gate deprecated `module_catalog` compat delegates; fix fail-open readiness.** `Tier 1 · Track 2 · deps: none · (why → TA12)`
  Remove `get_module_names()`/`get_module_entries()` from the public `contracts/__init__.py` API (or add the mandated `# F-EXCEPTION:` tag if a caller genuinely still needs them), and make `get_module_readiness_reason()` raise or return an explicit "unknown module" sentinel for unrecognized names instead of `None` (indistinguishable from "ready").
  *Files:* `quickscale_core/src/quickscale_core/contracts/module_catalog.py:128-175,270-289`.
  *Acceptance:* the deprecated delegates are either removed from the public API or carry an `# F-EXCEPTION:` tag; readiness checks on an unknown module name raise/return a distinguishable value from "ready".

#### `SA18` — Core/CLI/generator plumbing fail-hard fixes (Track 3)

> SA18.1–SA18.7 (manifest adapter init, analytics manifest settings, `quickscale_cli.schema` shim removal, generator template resolution, version fallback, project-metadata resolution, `railway_utils.py` exception narrowing — closes TA3–TA8 and TA10) are complete. See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA18.8 — Fail-hard invalid `PORT` values (complete).** `Tier 1 · Track 3 · deps: none · (why → TA11)`
  `get_port_from_env()` now defaults to `8000` only when `PORT` is unset. A present but non-numeric `PORT` now raises `ValueError` naming the bad value instead of silently coercing to `8000`. Updated the helper docstring to remove the fallback-on-invalid contract and rewrote the focused `TestGetPortFromEnv` regression to assert the fail-hard behavior.
  *Files:* `quickscale_cli/src/quickscale_cli/utils/docker_utils.py`, `quickscale_cli/tests/utils/test_docker_utils.py`.
  *Acceptance:* `PORT=notanumber` raises a descriptive error; `PORT` unset still defaults to `8000`.
  *Finding:* Existing focused test coverage already exercised the invalid-`PORT` seam, so the task reduced to changing the helper behavior and updating the assertion from fallback-to-default to fail-hard. No blockers discovered.

- [x] **SA18.9 — Fail `step_capture_hashes` on `OSError` (complete).** `Tier 1 · Track 3 · deps: none · (why → TA13)`
  `step_capture_hashes` now returns `StepOutcome(success=False, failed_step_label="capture managed file hashes")` on `OSError`. Updated the docstring to remove the best-effort/always-succeeds contract. Added focused regression coverage (13 tests) covering OSError on resolve/compute, no-managed-paths no-op, success recording, and reporter-none edge cases.
  **Decision (2026-07-04):** Option 1 (fail hard), per user direction. No F-EXCEPTION needed.
  `step.py` step 4 `failed_step_label` changed from `None` to `"capture managed file hashes"` so the registry entry matches the new fail-hard posture (reduces None entries from 3 to 2, raises labeled count from 13 to 14).
  `apply_command.py` `_capture_managed_file_hashes_after_apply` updated to return its `StepOutcome` and the step 4 pipeline caller now checks the outcome and calls `_abort_after_post_embed_failure` when it is unsuccessful.
  *Files:* `quickscale_core/src/quickscale_core/apply/steps/wiring.py:71-130`, `quickscale_core/src/quickscale_core/apply/step.py:89-96`, `quickscale_cli/src/quickscale_cli/commands/apply_command.py`, `quickscale_core/tests/test_apply_wiring_steps.py` (new), `quickscale_core/tests/test_apply_step.py`.
  *Acceptance:* `step_capture_hashes` returns `success=False` on `OSError` with descriptive message and `failed_step_label`; docstring updated; step registry reflects the fail-hard posture; `quickscale apply` aborts with the correct failure label when the step fails.
  *Finding:* The step body change alone would not propagate to the CLI — the `_capture_managed_file_hashes_after_apply` wrapper and its step 4 pipeline caller also needed updating to check the outcome and call `_abort_after_post_embed_failure`. No blockers discovered.

- [ ] **SA18.10 — Add mandated `# F-EXCEPTION:` tags to documented exceptions.** `Tier 1 · Track 3 · deps: none · (why → TA14)`
  Add the `# F-EXCEPTION: <tag>` comment format decisions.md §fail-hard-principle mandates to every code location it documents as an exception (starting with `_read_through_import_legacy`'s F12.2 reference, corrected to the mandated tag format), and add the currently-undocumented legacy paths in `remove_command.py` (`_load_legacy_tracking`, legacy `config.yml` snapshot/update) to the decisions.md exception table. SA18.6 is already complete (its exception entries are in place); SA18.9 chose the fail-hard path (no new F-EXCEPTION), so no dependency remains.
  *Files:* `quickscale_core/src/quickscale_core/project_state.py:415`, `quickscale_cli/src/quickscale_cli/commands/remove_command.py`, `docs/technical/decisions.md`.
  *Acceptance:* `grep -rn "F-EXCEPTION"` returns a hit for every exception decisions.md documents, and decisions.md's exception table lists every exception the grep finds.

- [ ] **SA18.11 — Fix dev-tooling silent parse failure in the compatibility checker.** `Tier 1 · Track 3 · deps: none · (why → TA15)`
  A malformed module `pyproject.toml` should fail the compatibility check loudly, not be silently skipped.
  *Files:* `scripts/check_module_core_compatibility.py:381-388`.
  *Acceptance:* a malformed `pyproject.toml` in any module causes the checker to fail/report an error for that module instead of silently skipping it.

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../../arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../../tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
