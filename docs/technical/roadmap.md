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

**Priority note:** SA11.1–SA11.5 closed the **live defect** (anonymous public pages render empty under the hardened production RLS posture — Module Finding 1) and its adjacent hardening work; see CHANGELOG.md. SA11.6–SA11.7 continue the Module Finding 1 remediation.

#### Dependency & parallelization overview (2026-07-03)

**Completed — closeout in [CHANGELOG.md](../../CHANGELOG.md):** SA6.1–SA6.3, SA7.1–SA7.4, SA9.1–SA9.6, SA10.1, SA11.1–SA11.5, SA12.1. Repo Findings 2, 3, and 4 are fully resolved — see CHANGELOG.md and, for Finding 3, `decisions.md` §D1.

Diagram below shows only remaining open work.

```
Track 1 (tenant-context surface)     Track 2 (money ledger + core boundary)    Track 3
───────────────────────────────      ───────────────────────────────────      ───────
SA11.6 (no deps)                    SA10.2 (deps: SA10.1 ✓)                  —
SA11.7 (no deps)
```

No cross-track dependencies. Track 3 has no remaining open tasks.

#### Track summary

| Track | Tasks (in order) | Theme |
|-------|------------------|-------|
| **1** | SA11.6 → SA11.7 *(no deps)* | Tenant-context request boundary — CRM `_resolve_active_org` cleanup + auth fail-hard default |
| **2** | SA10.2 *(deps: SA10.1 ✓)* | Module↔generated-project contract-vintage detection |
| **3** | No open tasks | All SA7.x complete |

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

- [ ] **SA11.6 — Clean up CRM's `_resolve_active_org`.** `Tier 1 · Track 1 · deps: none`
  Remove the "for tests that bypass middleware" personal-org fallback from production code (move it into test fixtures/middleware instead) and stop performing the stage-seeding write as a side effect of every org resolution — seed once at org-creation time instead.
  *Files:* `quickscale_modules/crm/src/quickscale_modules_crm/views.py`.
  *Acceptance:* `_resolve_active_org` only resolves and primes context; CRM test suite stays green with fixtures updated to set `request.org` directly.

- [ ] **SA11.7 — Fail-hard the auth signup-open default.** `Tier 1 · Track 1 · deps: none`
  Replace the permissive `getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)` fallback with a required-setting read (raise `ImproperlyConfigured` if unset), consistent with the fail-hard principle.
  *Files:* `quickscale_modules/auth/src/quickscale_modules_auth/adapters.py`.
  *Acceptance:* omitting `ACCOUNT_ALLOW_REGISTRATION` from settings raises at startup instead of silently defaulting to open registration.

---

#### Finding — Repo Finding 5: module↔generated-project contract drift (`why →` [Finding 5](../../arch-audit.md#finding-5-the-modulegenerated-project-contract-drifts-by-design--every-release-accretes-existing-projects-must-manually-adopt-steps-with-no-mechanism-to-apply-them))

- [x] **SA10.1 — `project_contract` version in state.yml (complete).** `Tier 1 · Track 2 · deps: none`
  Record the generator/contract version a project was generated against in `.quickscale/state.yml` at generation time.
  *Files:* `quickscale_core/src/quickscale_core/schema/state_schema.py`, generator state-writing path.
  *Acceptance:* a fresh generation's `state.yml` includes `project_contract`; existing state-file tests updated for the new field.
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

- [x] **SA10.2 — `quickscale status` contract-vintage check (complete).** `Tier 2 · Track 2 · deps: SA10.1`
  Added `ContractVintage` dataclass (`minimum: str`, `manual_adoption_steps: list[str]`) and `contract_vintage` field to `ModuleManifest`. Added `_parse_contract_vintage` to the YAML loader; absent on legacy manifests. Added `_check_contract_vintage` to status that compares each installed module's declared minimum against `state.project.project_contract` and reports gaps in both text and JSON drift output. Seeded `social/module.yml` and `backups/module.yml` with `contract_vintage: {minimum: "0.87.0", manual_adoption_steps: [...]}` matching their documented manual-adoption boundaries. `parse_version_tuple` utility handles `None` → `(0,)` so legacy projects (unknown vintage) are flagged as behind any declared minimum. Forward-compatible: no minimum or `contract_vintage` → no-op.
  *Files:* schema, loader, status_command, social/backups module.yml, tests.
  *Acceptance:* `quickscale status` on a project generated before v0.87.0 with social or backups installed reports the contract gap and manual steps; fresh v0.87.0+ generations pass clean; legacy manifests load with `contract_vintage=None`.
  See [CHANGELOG.md](../../CHANGELOG.md) for closeout details.

---

> **Closed findings:** Repo Finding 2 (orgs god-module — SA7.2–SA7.4), Repo Finding 3 (dual active-org truth — product decision 2026-07-03), and Repo Finding 4 (core-as-runtime-API boundary — SA9.1–SA9.6) are fully resolved with no open tasks. Closeout detail is in [CHANGELOG.md](../../CHANGELOG.md); the Finding 3 product decision is recorded in `decisions.md` §D1.

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../../arch-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
