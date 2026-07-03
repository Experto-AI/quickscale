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

**Priority note:** SA11.1–SA11.4 closed the **live defect** (anonymous public pages render empty under the hardened production RLS posture — Module Finding 1); see CHANGELOG.md. SA11.5 stays in the first landing batch because it closes the broader Module Finding 1 hardening work adjacent to that now-closed defect chain.

#### Dependency & parallelization overview (2026-07-03)

**Completed and merged — see [CHANGELOG.md](../../CHANGELOG.md):** SA12.1, SA9.1, SA6.1, SA6.2, SA6.3, SA7.1, SA7.2, SA7.3, SA7.4, SA9.2, SA9.3, SA9.4, SA9.5, SA11.1, SA11.2, SA11.3, SA11.4. Repo Finding 2 (`orgs` god-module de-coupling) and Repo Finding 3 (dual source of truth for active org) are fully resolved — see CHANGELOG.md and, for Finding 3, `decisions.md` §D1.

Diagram below shows only remaining open work.

```
Track 1 (tenant-context surface)     Track 2 (money ledger + core boundary)    Track 3 (wiring governance + deps)
───────────────────────────────      ───────────────────────────────────      ────────────────────────────────
SA11.5 (no deps)                    SA9.6                                     —
SA11.6 (no deps)                    SA10.1 (no deps)
SA11.7 (no deps)                      └─ SA10.2 (←10.1)
```

No cross-track dependencies. Track 3's `SA7.x` work in `quickscale_modules/crm/` (signals/wiring) is complete and merged, so the only remaining touch on that package is Track 1's `SA11.6` — no cross-track file-ownership conflict remains.

#### Track summary

| Track | Tasks (in order) | Theme |
|-------|------------------|-------|
| **1** | SA11.5 → SA11.6 → SA11.7 *(no deps)* | Tenant-context request boundary — fixes the live public-page defect |
| **2** | SA9.6 · SA10.1 → SA10.2 | Billing ledger idempotency + core-as-runtime-API boundary + contract-vintage detection |
| **3** | No open tasks in current batch *(SA7.4 complete)* | Declarative-wiring migration slice + orgs god-module de-coupling version-range constraints |

---

#### Finding — Module Finding 1: request→tenant-context boundary (`why →` [Module Finding 1](../../arch-audit.md#module-finding-1-the-requesttenant-context-boundary-is-a-per-module-convention-with-divergent-idioms--and-bloglistings-public-pages-read-as-empty-under-the-hardened-production-posture))

- [x] **SA11.1 — Orgs-owned public-read context helper (complete — 2026-07-03).** `Tier 2 · Track 1 · deps: none · RISK LEVEL: medium`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA11.2 — Restricted-role anonymous-read E2E smoke (complete).** `Tier 2 · Track 1 · deps: SA11.1 · RISK LEVEL: medium`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA11.3 — Migrate blog public views to the helper (complete).** `Tier 1 · Track 1 · deps: SA11.1`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA11.4 — Migrate listings public views to the helper (complete).** `Tier 1 · Track 1 · deps: SA11.1`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

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

- [x] **SA9.5 — Migrate social's deep core imports to the facade (completed — 2026-07-03).** `Tier 2 · Track 2 · deps: SA9.3`
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA9.6 — CI import-linter gate (completed — 2026-07-03).** `Tier 1 · Track 2 · deps: SA9.4 & SA9.5`
  Added `scripts/check_module_core_imports.py` — an AST-based import linter that scans `quickscale_modules/*/src/` and rejects any `quickscale_core` import that targets a module other than `quickscale_core.runtime` (with per-module legacy exceptions for billing/crm adapter seams only). Two framework-seam imports (`quickscale_core.manifest.entry_point`, `quickscale_core.module_wiring`) are scoped to billing and CRM via the `LEGACY_ALLOWED_IMPORTS` dict — no other module may use them. Wired as `make check-module-core-imports`, included in `make check` and in `scripts/check_ci_locally.sh` (step 4/7). Added a `module-core-import-linter` gate job in `.github/workflows/ci.yml` that the `test` CI job depends on.
  *Findings:* CR-SA9.6-001 (global allowlist too broad) — resolved: exceptions now scoped per module. CR-SA9.6-002 (docs/policy inconsistency) — resolved: roadmap, changelog, Makefile help, and implementation contract aligned with the scoped policy. CR-SA9.6-003 (advisory test-gap) — remains visible for future follow-up.
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

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

> **Closed findings:** Repo Finding 2 (`orgs` composition god module — SA7.2, SA7.3, SA7.4 all complete) and Repo Finding 3 (dual source of truth for active organization — resolved by product decision 2026-07-03) have no open tasks. Closeout detail is in [CHANGELOG.md](../../CHANGELOG.md); the Finding 3 product decision is recorded in `decisions.md` §D1.

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../../arch-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
