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

### Structural Autopsy Remediation II (opened 2026-07-02)

Fix plan derived from the [2026-07-02 repo-level autopsy](../../arch-audit.md#autopsy--2026-07-02) and the [2026-07-02 module-by-module autopsy](../../arch-audit.md#module-by-module-autopsy--2026-07-02). Each task below is sized Adaptive **Tier 1 or Tier 2**. Tenant-isolation and money-ledger work is sensitive-domain → `RISK LEVEL: medium` → floors at Tier 2.

**Naming:** `SAn.m` continues the sequence from the closed 2026-06-30 remediation (`SA1`–`SA5`); this batch starts at `SA6` to avoid collision. `SA6`–`SA10` close repo-level findings, `SA11`–`SA12` close module-level findings.

**Priority note:** SA11.1–SA11.4 closed the **live defect** (anonymous public pages render empty under the hardened production RLS posture — Module Finding 1). SA11.5 stays in the first landing batch because it closes the broader Module Finding 1 hardening work adjacent to the defect chain. SA11.2 should land before SA11.3/SA11.4 because it proves the defect class is closed.

#### Dependency & parallelization overview (2026-07-03)

**Completed and merged — see [CHANGELOG.md](../../CHANGELOG.md):** SA12.1, SA9.1, SA6.1, SA6.2, SA6.3, SA7.1, SA7.2, SA7.3, SA9.2, SA9.3, SA11.1.

Diagram below shows only remaining open work.

```
Track 1 (tenant-context surface)     Track 2 (money ledger + core boundary)    Track 3 (wiring governance + deps)
───────────────────────────────      ───────────────────────────────────      ────────────────────────────────
SA11.4 (←11.1, unblocked)           SA9.4  (←9.3)                             SA7.4  (no deps)
SA11.5 (no deps)                    SA9.5  (←9.3)
SA11.6 (no deps)                    └─ SA9.6 (←9.4 & 9.5)
SA11.7 (no deps)                    SA10.1 (no deps)
                                      └─ SA10.2 (←10.1)
```

No cross-track dependencies. Cross-track file-ownership note: `quickscale_modules/crm/` is touched by **both** Track 1 (`SA11.6` — `views.py` cleanup) and Track 3 (`SA7.x` — signals/wiring); the two tasks touch disjoint files inside the package, but track owners should confirm no overlap before merge-back.

#### Track summary

| Track | Tasks (in order) | Theme |
|-------|------------------|-------|
| **1** | SA11.4 *(unblocked)* → SA11.5 → SA11.6 → SA11.7 *(no deps)* | Tenant-context request boundary — fixes the live public-page defect |
| **2** | SA9.4/SA9.5 → SA9.6 · SA10.1 → SA10.2 | Billing ledger idempotency + core-as-runtime-API boundary + contract-vintage detection |
| **3** | SA7.4 *(no deps)* | Declarative-wiring migration slice + orgs god-module de-coupling version-range constraints |

---

#### Finding — Module Finding 1: request→tenant-context boundary (`why →` [Module Finding 1](../../arch-audit.md#module-finding-1-the-requesttenant-context-boundary-is-a-per-module-convention-with-divergent-idioms--and-bloglistings-public-pages-read-as-empty-under-the-hardened-production-posture))

- [x] **SA11.1 — Orgs-owned public-read context helper (complete — 2026-07-03).** `Tier 2 · Track 1 · deps: none · RISK LEVEL: medium`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA11.2 — Restricted-role anonymous-read E2E smoke (complete).** `Tier 2 · Track 1 · deps: SA11.1 · RISK LEVEL: medium`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA11.3 — Migrate blog public views to the helper (complete).** `Tier 1 · Track 1 · deps: SA11.1`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [ ] **SA11.4 — Migrate listings public views to the helper.** `Tier 1 · Track 1 · deps: SA11.1`
  Same conversion for the listings module's public list/detail views.
  *Files:* `quickscale_modules/listings/src/quickscale_modules_listings/views.py`.
  *Acceptance:* restricted-role anonymous read of a published System-org listing returns rows; existing listings tests stay green.

- [ ] **SA11.5 — Generated-project DRF permission baseline.** `Tier 1 · Track 1 · deps: none`
  Emit `REST_FRAMEWORK = {"DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"]}` from the generator's settings wiring so module APIs default to authenticated-only unless a view explicitly opts into public access, instead of relying on DRF's `AllowAny` default.
  *Files:* `quickscale_core/src/quickscale_core/generator/templates/` (settings template).
  *Acceptance:* a fresh generation's settings include the explicit DRF default; existing module API tests (which authenticate explicitly) stay green.

- [ ] **SA11.6 — Clean up CRM's `_resolve_active_org`.** `Tier 1 · Track 1 · deps: none`
  Remove the "for tests that bypass middleware" personal-org fallback from production code (move it into test fixtures/middleware instead) and stop performing the stage-seeding write as a side effect of every org resolution — seed once at org-creation time instead.
  *Files:* `quickscale_modules/crm/src/quickscale_modules_crm/views.py`.
  *Acceptance:* `_resolve_active_org` only resolves and primes context; CRM test suite stays green with fixtures updated to set `request.org` directly.

- [ ] **SA11.7 — Fail-hard the auth signup-open default.** `Tier 1 · Track 1 · deps: none`
  Replace the permissive `getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)` fallback with a required-setting read (raise `ImproperlyConfigured` if unset), consistent with the fail-hard principle.
  *Files:* `quickscale_modules/auth/src/quickscale_modules_auth/adapters.py`.
  *Acceptance:* omitting `ACCOUNT_ALLOW_REGISTRATION` from settings raises at startup instead of silently defaulting to open registration.

---

#### Finding — Repo Finding 4: core-as-runtime-API boundary (`why →` [Finding 4](../../arch-audit.md#finding-4-quickscalecores-entire-internal-surface-is-a-de-facto-runtime-api-for-user-owned-generated-projects--with-an-open-ended-version-range-and-a-repo-wide-clean-break-policy))

- [x] **SA9.2 — CI job: module-vs-oldest-claimed-core import check (completed 2026-07-03).** `Tier 1 · Track 2 · deps: none · RISK LEVEL: medium`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA9.3 — `quickscale_core.runtime` public facade (completed 2026-07-03).** `Tier 2 · Track 2 · deps: none`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA9.4 — Migrate backups' deep `dr_engine` imports to the facade (completed — 2026-07-03).** `Tier 2 · Track 2 · deps: SA9.3`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [ ] **SA9.5 — Migrate social's deep core imports to the facade.** `Tier 2 · Track 2 · deps: SA9.3`
  Repoint `social/adapter.py` from `quickscale_core.contracts.{module_options,resolvers}` and `quickscale_core.manifest.{assembler,resolver,social_manifest}` to `quickscale_core.runtime`.
  *Files:* `quickscale_modules/social/src/quickscale_modules_social/adapter.py`.
  *Acceptance:* social test suite green with imports going through the facade only.

- [ ] **SA9.6 — CI import-linter gate.** `Tier 1 · Track 2 · deps: SA9.4 & SA9.5`
  Add a CI check that fails if any file under `quickscale_modules/*/src/` imports `quickscale_core` from outside `quickscale_core.runtime` (or another explicitly documented allowlist entry).
  *Files:* new CI script (e.g. `scripts/check_module_core_imports.py`).
  *Acceptance:* introducing a new deep-internal import from a module fails CI; the current (post-SA9.4/9.5) import set passes.

---

#### Finding — Repo Finding 5: module↔generated-project contract drift (`why →` [Finding 5](../../arch-audit.md#finding-5-the-modulegenerated-project-contract-drifts-by-design--every-release-accretes-existing-projects-must-manually-adopt-steps-with-no-mechanism-to-apply-them))

- [ ] **SA10.1 — `project_contract` version in state.yml.** `Tier 1 · Track 2 · deps: none`
  Record the generator/contract version a project was generated against in `.quickscale/state.yml` at generation time.
  *Files:* `quickscale_core/src/quickscale_core/schema/state_schema.py`, generator state-writing path.
  *Acceptance:* a fresh generation's `state.yml` includes `project_contract`; existing state-file tests updated for the new field.

- [ ] **SA10.2 — `quickscale status` contract-vintage check.** `Tier 2 · Track 2 · deps: SA10.1`
  Compare each installed module's declared minimum project-contract requirement against the project's recorded `project_contract` and print the specific manual-adoption steps when the project is behind.
  *Files:* `quickscale_cli/src/quickscale_cli/commands/status_command.py`.
  *Acceptance:* `quickscale status` on a project generated before a contract-requiring module update names the gap and the manual step, instead of silence.

---

#### Finding — Repo Finding 2: orgs composition god module (`why →` [Finding 2](../../arch-audit.md#finding-2-orgs-is-becoming-the-composition-god-module--inter-module-integration-is-hand-wired-pairwise-with-no-contract-and-the-central-tenant-registry-couples-all-module-versions-in-lockstep))

- [x] **SA7.2 — Fail-hard the auth-adapter import fallback (completed 2026-07-03).** `Tier 1 · Track 3`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA7.3 — De-duplicate notifications defaults out of orgs' manifest (completed 2026-07-03).** `Tier 1 · Track 3`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [ ] **SA7.4 — Version-range constraints on `required_modules`.** `Tier 2 · Track 3 · deps: none`
  Add a minimum-version constraint to each module's `required_modules: [orgs]` declaration (billing, blog, crm, social — the four modules that declare it today) and make `_validate_module_prerequisites` in `apply_command.py` fail closed when an installed module's required-module version is below the declared minimum.
  *Files:* `quickscale_modules/{billing,blog,crm,social}/module.yml`, `quickscale_cli/src/quickscale_cli/commands/apply_command.py` (`_validate_module_prerequisites`).
  *Acceptance:* `quickscale apply` refuses to proceed when an installed `orgs` version is older than a dependent module's declared minimum, with an explicit error naming both versions.

---

#### Finding — Repo Finding 3: dual source of truth for active organization (`why →` [Finding 3](../../arch-audit.md#finding-3-active-organization-has-two-sources-of-truth-in-generated-saas-apps--the-server-session-and-the-spas-client-state--and-the-shipped-resolution-was-to-amputate-features-d1-option-b))

- [x] **RESOLVED 2026-07-03 by product decision — no multi-org membership for regular users.**
  Regular SaaS users belong to exactly one organization. The server session is the sole authority for org resolution, eliminating the dual-source-of-truth problem. No org switcher in the user-facing UI. VIEW-AS (superuser-only) remains the debug path for operator org-scope switching — already shipped.

  **Consequences:**
  - SA8.1/SA8.2/SA8.3 (explicit-org API contract) are unnecessary — cancelled.
  - Billing SPA entry points are no longer blocked by the D1 org-switch problem and can be restored as separate implementation work.
  - The D1 decision record in `decisions.md` §D1 has been updated to reflect this resolution.

  > **Implementation note:** Removing the org switcher from the user-facing React UI and restoring billing SPA entry points are tracked separately — not part of this SA hardening batch.

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../../arch-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
