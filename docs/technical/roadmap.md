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

> **Closed batches (detail in [CHANGELOG.md](../../CHANGELOG.md)):** SA1–SA5 (2026-07-02), SA6–SA12 (2026-07-03), SA13.1–SA13.4 (2026-07-04), SA14.1–SA14.6 (2026-07-05), SA15.1–SA15.3 (2026-07-04), SA16.1/SA16.2 (2026-07-03), SA17.1–SA17.8 (2026-07-05), SA18.1–SA18.11 (2026-07-04), SA19 (2026-07-05), SA20 (2026-07-06), SA21.1 (2026-07-05), SA21.2 (2026-07-07), SA22 (2026-07-05), SA23 (2026-07-05), SA24 (2026-07-05), SA25 (2026-07-05), SA26 (2026-07-06), SA27 (2026-07-05), SA28 (2026-07-05), SA29 (2026-07-05), SA30 (2026-07-06), SA31 (2026-07-05), SA32 (2026-07-06), SA33 (2026-07-05), SA34 (2026-07-06), SA35 (2026-07-07), SA36 (2026-07-07), SA37 (2026-07-07), SA38 (2026-07-07), SA39 (2026-07-06), SA40 (2026-07-06), SA41 (2026-07-07), SA43 (2026-07-07), SA45 (2026-07-06). All closed per template rule — detail lives in CHANGELOG.md.
>
> **Origin note:** SA34–SA47 trace to the 2026-07-06 triage against [tech-audit.md](../others/tech-audit.md) (TA33–TA41) and [arch-audit.md](../others/arch-audit.md) (Findings 1–5), each sized Tier 1–2 (arch-audit's larger Findings 1/2/4/5 are cut down to their recommended *first step* only — later stages are explicitly deferred and remain tracked in arch-audit.md itself).

> **Track status (2026-07-07, roadmap cleanup pass):** Track 1 — **0 open items, clear to continue** (SA47 complete; SA35/SA41 both complete, no blocker). Track 2 — **0 open items, complete** — all assigned work landed; idle until new work is assigned. Track 3 — **2 open items + 1 partial (blocker pending)** (SA42 ready now, no deps; SA46 ready now — CR-SA46-REV-003 decision made, see below; SA44 partial — CR-SA44-REV-001 **[module-level refresh_managed_adapters() not self-contained across test ordering]** remains blocking).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────     ───────────────────────────
— no open items —                       — no open items —                       SA44 (deps: none) — partial (CR-SA44-REV-001 blocking)
                                                                                SA42 (deps: none)
                                                                                SA46 (deps: none) — CR-SA46-REV-003 fix, ready
```

### Track 1 — Tenant-context surface

#### Finding — `deletion-invariants-per-boundary-reimplementation` (`why →` [arch-audit.md Finding 2](../others/arch-audit.md), first step only)

- [x] **SA47 — Move the last-owner deletion-blocking check into orgs as the single implementation.** `Tier 2 · Track 1 · deps: SA35, SA41 (soft sequence — same files, land after to avoid rebasing onto still-changing exception handling)`
  **SA47 — complete.** Added `OrganizationMembership.is_last_owner_with_members()` — the canonical SA47 last-owner check that returns True when the user is the sole owner and the org has other members. All three prior call sites now use it: `OrganizationMembership.delete()` (model-level lock-guarded guard), `AccountDeleteView._get_blocking_orgs_for_deletion` (via delegation), `MemberListView.remove` and `OrgApiMemberRemoveView` (view-layer removal). `AccountDeleteView.form_valid` now wraps the guard check + user deletion in `transaction.atomic()` with `select_for_update` on all owner orgs, serializing concurrent account deletions that share an org. The concurrent regression test (`test_concurrent_account_deletion_locking_protects_last_owner`) proves exactly one deletion succeeds when two co-owners attempt to delete simultaneously — the org never becomes ownerless while non-owner members remain. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

### Track 2 — Module contracts & settings

No open items. All Track 2 work (SA21.2, SA37, SA38, SA40, SA43, plus its earlier share of the SA19–SA33 batch) is complete — detail in [CHANGELOG.md](../../CHANGELOG.md). Idle until new work is assigned.

### Track 3 — Core/CLI plumbing

#### Finding — `dr-engine-module-circular-lattice` (`why →` [arch-audit.md Finding 1](../others/arch-audit.md), stage 1 only)

> **SA44 — partial** (blocking finding CR-SA44-REV-001 remains — see below). Replaced import-time adapter registration with explicit registration via `MANAGED_ADAPTER_ORIGINS.add("social")` + `refresh_managed_adapters()`. Deleted the `_is_import_time_adapter_circular_import` string-matching classifier outright. Split `runtime.py` into `runtime/__init__.py` (combined facade), `runtime/dr.py` (DR surface), and `runtime/manifest.py` (manifest/social surface) so the two domains stop interlocking at import time. Repointed social module's adapter imports from `quickscale_core.manifest.entry_point` to `quickscale_core.runtime.manifest` (the new canonical seam). Production prior-base-path refresh fix landed in `module_wiring_manager.py`. Broad targeted validation green across all changed files. Full detail in [CHANGELOG.md](../../CHANGELOG.md).
>
> **Remaining blocker (CR-SA44-REV-001):** the module-level `refresh_managed_adapters()` reduces one import-order dependency, but `_build_specs()` is still not self-contained because later tests can mutate the global managed-adapter registry before the helper runs. Suggested next step: refresh at point of use inside `_build_specs()` or add a function-scoped autouse fixture so managed-module builds are self-contained regardless of prior suite state. Blocking finding at `quickscale_cli/tests/commands/test_module_config_extended.py`. The user chose to stop further fixing, keep the shipped work, and record this blocker. SA44 as a whole remains open pending resolution of this blocker.

#### Finding — `entry-point-posthook-permissive-coercion-defaults` (`why →` [TA40](../others/tech-audit.md))

- [ ] **SA42 — Make module post-hook settings reads fail hard instead of silently coercing.** `Tier 2 · Track 3 · deps: none`
  `entry_point.py` post-hooks retain permissive `.get(key, default)` coercions for blog (`POSTS_PER_PAGE`→10, `ENABLE_RSS`→True, empty rate→`"5/hour"`), listings (→12), forms (five defaults incl. `SPAM_PROTECTION`→True), and notifications (`ENABLED`→True, TTL→300) — second-guessing SA27-validated input one layer down. Dead today (SA27 guarantees valid baked literals) but reopens the TA2/TA19/TA26 fail-open class silently on any upstream resolver regression. Fix: direct required reads (`settings["KEY"]`), matching the SA18.2 analytics-hook purge.
  *Files:* `manifest/entry_point.py:386-390` (blog), `:451` (listings), `:520-531` (forms), `:898-921` (notifications).
  *Acceptance:* each of the four post-hooks reads its settings via direct required access instead of `.get(key, default)`; a missing/invalid post-hook setting raises `ImproperlyConfigured`/equivalent at apply time instead of silently defaulting.

#### Finding — `json-api-boundary-idiom-fragmentation` (`why →` [arch-audit.md Finding 5](../others/arch-audit.md), first step only)

- [ ] **SA46 (CR-SA46-REV-003) — Fold `not`/`~`/unary-on-bool into `_literal_truthiness()`.** `Tier 2 · Track 3 · deps: none (CR-SA46-001 and CR-SA46-REV-002 already shipped, see CHANGELOG.md)`
  Decision made 2026-07-07: finish the evaluator rather than accept the gap (matches this project's precedent of iterating an AST/lint gate to full coverage — SA13.1→13.4, SA21.1→21.2→SA36 — over leaving a security-adjacent gate partially complete). `scripts/check_csrf_exempt_gate.py`'s `_literal_truthiness()` currently returns `None` (uncertain) for compile-time unary expressions beyond signed numerics — `not <literal>`, `~<literal>` on `int`/`bool`, and unary `+`/`-` on `bool` (e.g. `+True`) — so a dead `if`-branch written in one of these forms isn't caught by the hard-fail gate (conservative fallback only; no CSRF-pairing hole). Extend `_literal_truthiness()` with the same pattern CR-SA46-REV-002 used for signed numerics: fold `ast.UnaryOp` with `ast.Not` (invert the operand's truthiness when defined), `~` over `int`/`bool` constants, and unary `+`/`-` over `bool` constants.
  *Files:* `scripts/check_csrf_exempt_gate.py` (`_literal_truthiness()` and its `ast.UnaryOp` handling).
  *Acceptance:* `_literal_truthiness()` returns a definite `True`/`False` for `not <literal>`, `~<literal>` (int/bool), and unary `+`/`-` on `bool`, matching Python's actual runtime truthiness; regression tests at both function-level and class-level visitor scope (mirroring the existing signed-numeric tests) prove `if not 0:`-style dead branches are now caught by the hard-fail gate; all existing SA46/CR-SA46-001/CR-SA46-REV-002 tests continue to pass. Closes CR-SA46-REV-003 and SA46 as a whole.

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
