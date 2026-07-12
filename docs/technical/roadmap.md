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

> Completed and archived work lives in [CHANGELOG.md](../../CHANGELOG.md). Keep only active or blocked work here. Completed items (SA60, SA70, SA74, SA75, SA76, SA78) were pruned from this section on 2026-07-12 — their full implementation detail lives in CHANGELOG.md; SA59.1 was also closed (via SA76's quarantine) and pruned. SA59.4 was not pruned — it is a blocked checkpoint (see Track 1 below), not a complete close.
>
> **Track readiness (2026-07-12):** Track 1 has a blocked checkpoint (SA59.4 — review finding CR-SA59.4-001 unresolved). Tracks 2–3 remain clean to continue.
> - **Track 1** — SA59 (umbrella) blocked checkpoint via SA59.4 (blocked: CR-SA59.4-001). SA77 remains open and unblocked, available to start now.
> - **Track 2** — SA79 open and unblocked, available to start now.
> - **Track 3** — no open items; fully available for new work.

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
SA77 — fix orgs restricted-role         SA79 — fix forms 0007 backfill            (no open items)
  CREATE ROLE failures                    data mismatch
```

SA77 (Track 1) and SA79 (Track 2) are fully independent and touch disjoint files. Track 3 has no open work and is available for new items.

### Track 1 — Tenant-context surface

SA59 (umbrella) blocked checkpoint via SA59.4 (2026-07-12) — see CHANGELOG.md. SA59.1–SA59.3 complete; SA59.4 landed checkpoint but remains open/blocked on CR-SA59.4-001 (medium, blocking, correctness: `docs/technical/validation_policy.md` quarantine-removal wording must match the live gate contract — each quarantine entry is removed independently as its owning ticket lands/completes). SA77 is open and unblocked.

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
