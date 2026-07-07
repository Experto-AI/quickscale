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

> **Track status (2026-07-07, roadmap cleanup pass):** Track 1 — **1 open item, clear to continue** (SA47; deps SA35/SA41 both complete, no blocker). Track 2 — **0 open items, complete** — all assigned work landed; idle until new work is assigned. Track 3 — **3 open items, clear to continue** (SA44, SA42 ready now, no deps; SA46's CR-SA46-REV-003 decision is made — see below — and it is now a ready Small-effort item, no longer blocked).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────     ───────────────────────────
SA47 (deps: SA35, SA41 — both           — no open items —                       SA44 (deps: none)
  complete; soft sequence only)                                                 SA42 (deps: none)
                                                                                 SA46 (deps: none) — CR-SA46-REV-003 fix, ready
```

### Track 1 — Tenant-context surface

#### Finding — `deletion-invariants-per-boundary-reimplementation` (`why →` [arch-audit.md Finding 2](../others/arch-audit.md), first step only)

- [ ] **SA47 — Move the last-owner deletion-blocking check into orgs as the single implementation.** `Tier 2 · Track 1 · deps: SA35, SA41 (soft sequence — same files, land after to avoid rebasing onto still-changing exception handling)`
  Two divergent implementations of "never remove the last owner" exist today: `OrganizationMembership.delete()` (lock-guarded, unconditional) and `AccountDeleteView._get_blocking_orgs_for_deletion` (unlocked check-then-act, "allowed when no other members"). Move the check into orgs as the canonical implementation, pick one semantic, and make `AccountDeleteView` call it. Full Option 1 (orgs-owned deletion service, `pre_delete` receiver backstop for every ORM path, billing seam integration) is out of scope for this phase — this is the first step only.
  *Files:* `quickscale_modules/auth/src/quickscale_modules_auth/views.py:112-153`, `quickscale_modules/orgs/src/quickscale_modules_orgs/models.py:231-252`.
  *Acceptance:* a single last-owner rule lives in orgs; both call sites (the model delete guard and `AccountDeleteView`) use it; existing SA28 tests pass against the unified implementation, plus a new concurrent-deletion test (two co-owners of the same org deleting accounts concurrently cannot both pass and leave the org ownerless).

Deps (SA35, SA41) are both complete — SA47 is ready to start, no blocker.

### Track 2 — Module contracts & settings

No open items. All Track 2 work (SA21.2, SA37, SA38, SA40, SA43, plus its earlier share of the SA19–SA33 batch) is complete — detail in [CHANGELOG.md](../../CHANGELOG.md). Idle until new work is assigned.

### Track 3 — Core/CLI plumbing

#### Finding — `dr-engine-module-circular-lattice` (`why →` [arch-audit.md Finding 1](../others/arch-audit.md), stage 1 only)

- [ ] **SA44 — Replace import-time adapter registration with explicit registration; delete the circular-import string-matching classifier.** `Tier 2 · Track 3 · deps: none`
  `_initialize_managed_adapters_at_import()` triggers adapter registration as an import-time side effect, guarded by `_is_import_time_adapter_circular_import` — a classifier that string-matches CPython's "partially initialized module"/"circular import" exception text against a hand-maintained module-name allowlist (grown from 2 to 3 entries in the SA20 closeout). Replace with explicit registration (module `AppConfig.ready()` or `importlib.metadata` entry points); delete the classifier outright; split `runtime.py` into `runtime.dr` and `runtime.manifest` so the two domains stop interlocking. Does not remove core→module imports (that's arch-audit Option 2 — persistence port — deferred to a future phase).
  *Files:* `manifest/entry_point.py:1436-1462,1511`, `quickscale_core/src/quickscale_core/runtime.py:107-141,152-272`.
  *Acceptance:* `test_manifest_entry_point.py` (the SA20 test for the classifier) becomes the regression harness for the replacement and passes; the string-matching classifier is gone; adapter registration is an explicit act, not an import-time side effect; importing DR-flavored code no longer trips manifest-adapter registration as a side effect.

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
