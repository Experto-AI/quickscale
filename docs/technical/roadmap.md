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

> Completed and archived work lives in [CHANGELOG.md](../../CHANGELOG.md). Keep only active or blocked work here. Completed items (SA60, SA70, SA74, SA75, SA76, SA78) were pruned from this section on 2026-07-12 — their full implementation detail lives in CHANGELOG.md; SA59.1 was also closed (via SA76's quarantine) and pruned.
>
> **Track readiness (2026-07-12):** all three tracks are clean to continue — no blocked work, no decision needed.
> - **Track 1** — SA59 (umbrella) open, blocked only on SA59.4. SA59.4 and SA77 are both open and unblocked, available to start now.
> - **Track 2** — SA79 open and unblocked, available to start now.
> - **Track 3** — no open items; fully available for new work.

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
SA59 — drop bypassrls auto-prime       SA79 — fix forms 0007 backfill            (no open items)
  (umbrella, open via SA59.4)            data mismatch
SA59.4 — docs + final closeout
SA77 — fix orgs restricted-role
  CREATE ROLE failures
```

SA59.4 and SA77 (Track 1) touch disjoint files (docs/decisions.md vs. orgs test files) and share only the shared-closeout-files exception (`CHANGELOG.md`/`roadmap.md`). SA79 (Track 2) is fully independent of Track 1. Track 3 has no open work and is available for new items.

### Track 1 — Tenant-context surface

SA59 (umbrella) remains open via SA59.4 only — SA59.1–SA59.3 are complete and SA59.1 closed via SA76's quarantine (2026-07-12, see CHANGELOG.md). SA77 is open and unblocked.

#### Finding — `test-tooling-auto-primes-bypassrls-hatch` (`why →` [tech-audit.md TA49](../others/tech-audit.md))

- [ ] **SA59 (umbrella) — Stop auto-priming `QUICKSCALE_ALLOW_BYPASSRLS=1` in the test-unit path — open via SA59.4 only.** `Tier 2 → split · Track 1 · deps: SA59.4`
  Split into SA59.1–SA59.4 per roadmap policy (Tier 3 → four Tier 1–2 sub-slices). SA59.1 (validation harness + coverage plumbing), SA59.2 (backups PostgreSQL/RLS seam), and SA59.3 (retained-role contract conversion) are complete — see CHANGELOG.md. Only **SA59.4** (docs + final closeout) remains.

  - [ ] **SA59.4 — Docs + final closeout — unblocked.** `Tier 1 · Track 1 · deps: SA59.1 (closed), SA76 (closed), SA59.2 (complete), SA59.3 (complete)`
    Correct documentation to match the adopted role shape, record the gate-split decision in decisions.md, and produce the final closeout checkpoint. Inherits two documentation fixes:
    - **F-SA59-DOC-002 / F-SA59-CMD-010** — Direct-connection role uses `LOGIN`, not `NOLOGIN`; correct matching docs and command matrix. Role descriptions in `Makefile` (help text) and scripts (`test_unit.sh`, `test_integration.sh`) still use `NOLOGIN`, but the CI `quickscale_test_role` requires `LOGIN` to establish test-database connections. All documentation and the command matrix must reflect `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` consistently.
    - **Advisory: agent-handback provenance discrepancy (user accepted).** A previous implementation handback omitted `decisions.md` and `scripts/test_integration.sh` from its changed-files listing. Include these files in the closeout manifest.
    *Target files:* `docs/technical/decisions.md` (record the unit/integration gate split); role-description prose in scripts, workflow docs, CHANGELOG, and the test-command reference matrix.
    *Acceptance:* the blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export is removed from the unit-only path (done); the integration path runs module suites against a NOBYPASSRLS role in both `ci.yml` and `publish.yml` (done); developers set the SA14.4 hatch explicitly per-suite when they need it; `make test-unit` (and the new integration target) documents the split in its help text; decisions.md records the split.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

#### Finding — `test-tooling-auto-primes-bypassrls-hatch`, orgs restricted-role residual (`why →` [tech-audit.md TA49](../others/tech-audit.md); split from SA59.1 per the 2026-07-12 closeout-path decision)

- [ ] **SA77 — Root-cause and fix orgs' restricted-role `CREATE ROLE`-dependent test failures.** `Tier 1 · Track 1 · deps: none`
  3 `test_models.py` failures + 6 helper-path errors in `test_tenant_table_conformance.py`/`test_operator_access.py` persist under the NOBYPASSRLS integration role. These depend on restricted-role `CREATE ROLE` behavior (SA59.3-style territory) and were not resolved by SA59.1's Phase 3 test-only adaptations or by SA59.3's create-then-use → assert-then-use conversion. Root cause not yet established — investigate whether these tests still attempt a `CREATE ROLE` call SA59.3 didn't cover, or exercise a role capability the shared `quickscale_test_role`/`quickscale_rls_test_role` contract doesn't grant.
  *Files:* `quickscale_modules/orgs/tests/test_tenant_table_conformance.py`, `quickscale_modules/orgs/tests/test_operator_access.py`, `quickscale_modules/orgs/tests/test_models.py` — plus `scripts/provision_test_roles.sh` if the fix is a role-contract gap rather than a test-helper gap.
  *Acceptance:* all 9 failing tests pass under the restricted `quickscale_test_role`/`quickscale_rls_test_role` roles; the corresponding `scripts/test_integration.sh` quarantine entry (from SA76) is removed.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

### Track 2 — Module contracts & settings

Available for new work; SA79 is open and unblocked.

#### Finding — `forms-0007-backfill-data-mismatch` (`why →` SA78 findings, notifications test suite)

- [ ] **SA79 — Fix forms migration 0007 backfill logic so seeded FormField rows match their parent Form's organization before VALIDATE CONSTRAINT.** `Tier 1 · Track 2 · deps: none`
  Migration `0007_new_organization_ownership` adds a composite FK `forms_formfield_form_org_fk` and runs `VALIDATE CONSTRAINT` against existing rows. The seeded FormField rows (from migration `0002_seed_forms`) do not have their `organization_id` correctly populated to match the parent Form's `organization_id`, causing the VALIDATE to reject the `(form_id, organization_id)` pairs. This pre-existing bug was surfaced when SA78's duplicate-database fix allowed the notifications test suite to progress past the DB lifecycle stage, revealing 26 FK validation failures across the notifications, forms, and social suites. Root cause: the backfill step in `0007_new_organization_ownership` needs to update orphaned FormField rows to reference the correct organization before VALIDATE CONSTRAINT runs.
  *Files:* `quickscale_modules/forms/migrations/0007_new_organization_ownership.py`
  *Acceptance:* a fresh test-database creation under the restricted role runs the notifications, forms, and social suites with 0 FK validation errors attributable to the forms 0007 backfill; SA76's quarantine entry for forms (if any) can be removed.
  *(why →* SA78 Findings/blockers discovered, notifications test suite*)*

### Track 3 — Core/CLI plumbing

No open items. Fully available for new work.

SA67 closed 2026-07-11: `decisions.md §Beta-Site External Verification Scope` establishes that verifying/patching the *deployed* state of `experto-ai-web`/`bap-web` is permanently out of scope for this monorepo's automation — neither site's repository nor its Railway deployment is reachable from here, and this is a structural property of the two-repo maintainer workflow, not a temporary access gap. The repo-local follow-up (SA66's file-taxonomy conformance gate, SA68's launcher-contract completion and Redis-dependent rollout guidance) was already complete. The outstanding manual verification is tracked as a standing maintainer to-do in [beta-site-migration.md](../planning/beta-site-migration.md#outstanding-maintainer-to-do-sa67-tracked-outside-roadmapmd), not here — future findings of this shape (requiring live inspection of the two external sites) close the same way rather than sitting open pending access that structurally cannot arrive. Completed Track 3 work (SA75, SA76) lives in [CHANGELOG.md](../../CHANGELOG.md).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
