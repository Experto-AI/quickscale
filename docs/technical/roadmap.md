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

> Completed work lives in [CHANGELOG.md](../../CHANGELOG.md). This section holds only active and blocked work.

**Recently closed (2026-07-13 — full detail in CHANGELOG):** SA77 (orgs restricted-role), SA82 (quarantine removal + full-gate rerun, closing SA77/SA79), SA79 (forms 0007 backfill), SA83 (blog restricted-role — shared `_clear_priming_memo` fix in `orgs/current_org.py`), SA80.3a / SA80.3b (pg_dump tooling + backups rerun), SA87 (backups username-independent test), SA81 (per-module lockfile / sibling-constraint cleanup). The SA82 unquarantined `make test-integration` gate is the current integration baseline; it remains red **only** on SA84–SA86 below.

### Cross-cutting decision — how to drain SA84–SA86 (arch-audit Finding 8)

SA83–SA86 are four instances of one structural pattern, **arch-audit [Finding 8](../others/arch-audit.md) (`module-rls-context-procedural`)**: module RLS-context acquisition is procedural. Only `orgs` and `forms` migrations acquire `operator_access`; `blog`/`crm`/`listings` cross-org data migrations and test fixtures acquire none. The blanket BYPASSRLS hatch masked every omission until SA82 removed it and exposed four modules at once.

arch-audit recommends **Option 1** — an orgs-owned shared RLS-context migration/ops helper (`with operator_access_migration(schema_editor):` or a `RunPython` wrapper) plus a conformance gate, landed **ahead of or alongside** SA84–SA86 so the remaining tickets share one diagnosis and one seam instead of copying SA79's inline `SET LOCAL app.operator_access` into three more modules (Option 2 — a §0 fix-regression that relocates the procedural pattern). **This decision is pending and gates the SA84/SA86 approach** (SA85 already has `operator_access` via SA79 and is unaffected). First step per arch-audit before any fix: triage one module's failures into **migration-time / fixture-time / runtime-query** buckets — only the runtime-query bucket is production-severity; the rest are test-posture (production `migrate` runs privileged under the SA68 one-shot role).

### Track 1 — Tenant-context surface

- [ ] **SA84 — Investigate and fix CRM's 67 restricted-role RLS failures (plus 20 skipped).** `Tier 1 · Track 1 · deps: none`
  Under the SA82 full `make test-integration` gate, CRM's restricted-role suite showed 195 passed, 67 RLS failures, 20 skipped. Root cause unconfirmed — RLS policy violations under `quickscale_test_role`. Likely an instance of Finding 8 (cross-org migrations/fixtures without `operator_access`); triage into buckets before fixing (see Cross-cutting decision).

  *Acceptance:* CRM's restricted-role suite passes clean (0 failures) under `make test-integration` with no quarantine entry.
  *(why →* CR-SA82-NT-003; arch-audit Finding 8*)*

### Track 2 — Module contracts & settings

- [ ] **SA85 — Fix forms' residual restricted-role test failures — blocked on review finding CR-SA85-REV-001.** `Tier 1 · Track 2 · deps: none → impl/validation complete 2026-07-13; review blocked` *(reassigned from Track 1, 2026-07-13)*
  Implementation and validation complete (four-phase fix — bounded fixture/test org scopes, retained-role management read-inventory/per-org writes, scoped notification content, and the Staff current-org/superuser operator contract; full detail in CHANGELOG). Current: forms 196 passed/8 skipped/12 deselected/0 failed/0 errors; E2E 12 passed; no quarantine entry needed; all other modules clean.

  **Blocked on CR-SA85-REV-001 (high/blocking):** the admin-form-list session tests and README contract still rest on a false `/admin/` exemption premise — they do not create own/foreign Forms with real `force_login` + `ACTIVE_ORG_SESSION_KEY` and no direct context, so they never assert staff inclusion/exclusion or superuser cross-tenant parity; no-org staff/superuser behavior (expected 302 → `/orgs/`) is untested; the README contract table/comments/references are incomplete. CR-SA85-REV-002 through -007 are resolved. **No product decision remains** — this is bounded implementation work.

  *Required next action:* rewrite `test_views.py` admin-form-list tests (create own/foreign Forms; real `force_login` + `ACTIVE_ORG_SESSION_KEY`, no direct context; assert staff inclusion/exclusion + superuser cross-tenant; no-org staff/superuser request admin-form-list and assert 302 Location `/orgs/`); correct the README contract table, comments, and references. Do not flip to `[x]` before CR-SA85-REV-001 is resolved (or the user waives/descopes it).
  *(why →* CR-SA82-NT-004; CR-SA85-REV-001*)*

- [ ] **SA86 — Investigate and fix listings' 6 restricted-role RLS failures.** `Tier 1 · Track 2 · deps: none` *(reassigned from Track 1, 2026-07-13)*
  Under the SA82 full gate, listings' restricted-role suite showed 128 passed, 6 RLS failures. Root cause unconfirmed — RLS policy violations under `quickscale_test_role`. Likely an instance of Finding 8; triage into buckets before fixing (see Cross-cutting decision).

  *Acceptance:* listings' restricted-role suite passes clean (0 failures) under `make test-integration` with no quarantine entry.
  *(why →* CR-SA82-NT-005; arch-audit Finding 8*)*

### Track 3 — Core/CLI plumbing

No open work — every Track 3 item (SA80 / SA82 / SA80.3a / SA80.3b / SA81 / SA87) closed 2026-07-13; see CHANGELOG. The next candidate for this track is arch-audit **[Finding 1](../others/arch-audit.md)** (DR persistence port, scheduled for the next planning cycle) — not yet ticketed.

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA84 — CRM (67 failures/20 skip)   SA85 — forms residual —                  (clear — all closed)
  open, no deps, unknown root         impl/validation complete;             next candidate:
  cause; likely Finding 8              blocked on CR-SA85-REV-001              Finding 1 DR persistence
                                     SA86 — listings (6 failures)              port (unticketed)
                                       open, no deps, unknown root
                                       cause; likely Finding 8
```

All three open tickets are independent at the code level but share one structural root (Finding 8). If Option 1 is adopted, land the orgs-owned RLS-context helper first (point the largest ticket, SA84, at it), then SA86 consumes the same seam; SA85 is unaffected and only needs its review finding closed. Because SA84 (Track 1) and SA86 (Track 2) would both consume the shared helper, sequence the helper before both regardless of track.

### Track readiness & decision (2026-07-13)

- **Track 1 — clean to continue** (one open ticket, SA84), **pending the Finding 8 approach decision.** No blocker beyond choosing shared-helper vs per-ticket.
- **Track 2 — SA85 blocked on a review finding (not a product decision); SA86 clean to continue, pending the Finding 8 approach.** SA85's block (CR-SA85-REV-001) is bounded implementation work with a defined next action; resume by rewriting the admin-form-list tests, or decide to waive/descope.
- **Track 3 — clean, no open work.**

**Decision owner action needed:** pick the SA84–SA86 remediation approach (Finding 8 Option 1 shared helper — arch-audit's recommendation — vs Option 2 per-ticket inline vs Option 3 test/production-posture split). This is the only open cross-track decision; it does not block SA85's review-finding work, which can proceed in parallel.

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
