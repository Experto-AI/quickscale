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
>
> **Origin note (2026-07-07, fix-plan pass):** SA48–SA56 trace to the 2026-07-07 delta-pass findings in [tech-audit.md](../others/tech-audit.md) (TA42–TA46) and [arch-audit.md](../others/arch-audit.md) (Finding 1's red flags and CR-SA44-REV-001 blocker, Finding 4's coverage-boundary sub-item, Finding 5's two remaining Option 1 pieces plus the billing migration promoted from "long tail" to scheduled work per user decision — no idiom is grandfathered as permanent legacy), each sized Tier 1–2. Every item fit Tier 1–2 without splitting; the two items large enough to flag (SA50, the `OrgApiBaseView` fold; SA56, the billing DRF migration) are Tier 2, not Tier 3.

> **Track status (2026-07-07, fix-plan pass):** Track 1 — **2 open items, all ready now, no blockers** (SA49, SA50 — SA48 complete; remaining items still soft-sequenced on orgs files to limit rebase risk). Track 2 — **3 open items, all ready now, no blockers** (SA52, SA53, SA54 — SA51 complete; remaining items still soft-sequenced on `backups/services.py`). Track 3 — **3 open items, all ready now, no blockers** (SA42 ready now; SA46 ready now — CR-SA46-REV-003 decision made; SA56 ready now — new this pass, no longer soft-sequenced since SA55 already landed; SA44 and SA55 complete).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
SA49 (deps: none; soft-seq after SA48)  SA52 (deps: none; soft-seq after SA51)    SA42 (deps: none)
SA50 (deps: none; soft-seq after SA49)  SA53 (deps: none; soft-seq after SA52)    SA46 (deps: none) — CR-SA46-REV-003 fix, ready
                                         SA54 (deps: none; soft-seq after SA53)    SA56 (deps: none; soft-seq after SA55)
```

All three tracks run fully in parallel — no cross-track file overlap exists. The "soft-seq" notes above are intra-track only: same-file edits ordered to avoid needless rebasing, not hard technical dependencies.

### Track 1 — Tenant-context surface

#### Finding — `deletion-invariants-per-boundary-reimplementation` (`why →` [arch-audit.md Finding 2](../others/arch-audit.md), first step only)

- [x] **SA47 — Move the last-owner deletion-blocking check into orgs as the single implementation.** `Tier 2 · Track 1 · deps: SA35, SA41 (soft sequence — same files, land after to avoid rebasing onto still-changing exception handling)`
  **SA47 — complete.** Added `OrganizationMembership.is_last_owner_with_members()` — the canonical SA47 last-owner check that returns True when the user is the sole owner and the org has other members. All three prior call sites now use it: `OrganizationMembership.delete()` (model-level lock-guarded guard), `AccountDeleteView._get_blocking_orgs_for_deletion` (via delegation), `MemberListView.remove` and `OrgApiMemberRemoveView` (view-layer removal). `AccountDeleteView.form_valid` now wraps the guard check + user deletion in `transaction.atomic()` with `select_for_update` on all owner orgs, serializing concurrent account deletions that share an org. The concurrent regression test (`test_concurrent_account_deletion_locking_protects_last_owner`) proves exactly one deletion succeeds when two co-owners attempt to delete simultaneously — the org never becomes ownerless while non-owner members remain. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `client-ip-settings-permissive-defaults` (`why →` [tech-audit.md TA43](../others/tech-audit.md))

- [x] **SA48 — Fail-hard the `get_client_ip()` trusted-proxy settings reads.** `Tier 1 · Track 1 · deps: none`
  `current_org.py:598-599` reads `USE_X_FORWARDED_FOR`/`TRUSTED_PROXY_COUNT` via `getattr(settings, ..., default)` — fail-closed in direction (falls back to `REMOTE_ADDR`) but silently disables proxy resolution on a typo'd or missing setting name instead of failing loud, the same `getattr`-default class SA14.6/SA30 purged elsewhere; generated apps always define both settings. Fix: direct required reads, raising `ImproperlyConfigured` when absent, matching SA30's shape.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/current_org.py:598-599`.
  *Acceptance:* both settings are read directly (no `getattr` default); a missing/invalid value raises `ImproperlyConfigured` at first call instead of silently falling back to `REMOTE_ADDR`; existing throttle/forensics tests plus a new missing-setting regression test pass.
  **SA48 — complete.** `get_client_ip()` now reads both trusted-proxy settings via direct required access, raises `ImproperlyConfigured` on missing/invalid values instead of silently defaulting, and keeps the existing fail-closed `REMOTE_ADDR` fallback only for explicit `USE_X_FORWARDED_FOR=False` / `TRUSTED_PROXY_COUNT=0` configurations. Added orgs test-setting defaults for both settings plus focused regressions for missing/invalid configuration. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `org-model-universe-hand-enumerated` (`why →` [arch-audit.md Finding 4](../others/arch-audit.md), coverage-boundary sub-item)

- [ ] **SA49 — Derive orgs' cross-module conformance-env module list instead of hand-listing it.** `Tier 1 · Track 1 · deps: none (soft-sequence after SA48 — same module, sequence to limit rebase risk)`
  `orgs/tests/settings.py:34-42`'s `INSTALLED_APPS` hand-lists 9 of 13 shipped modules (missing notifications, storage, analytics; teams is a placeholder) — every derivation gate that runs against this test env (SA15.3 registry cross-check, SA45 purge-spec completeness, SA35 FK-conformance) is blind to any tenant model in an app absent from this list. Fix: derive the expected module set from `quickscale_modules/*/pyproject.toml` presence and assert it in CI against the hand-maintained `INSTALLED_APPS`, failing when a shipped module with models is missing from the conformance env.
  *Files:* `quickscale_modules/orgs/tests/settings.py:34-42`; new CI assertion (script or test) deriving the expected app list from `quickscale_modules/*/pyproject.toml` presence.
  *Acceptance:* a shipped module directory with a `pyproject.toml` and models that is absent from `orgs/tests/settings.py`'s `INSTALLED_APPS` fails CI; notifications/storage/analytics are either added to the list or their omission is asserted as a deliberate, named exception as part of landing this.

#### Finding — `json-api-boundary-idiom-fragmentation` (`why →` [arch-audit.md Finding 5](../others/arch-audit.md), Option 1 remaining piece — the fold)

- [ ] **SA50 — Fold orgs' `JsonApiMixin`/`JsonOrganizationAccessMixin` stack into one `OrgApiBaseView`.** `Tier 2 · Track 1 · deps: none (soft-sequence after SA49 — both touch orgs surfaces; arch-audit's fix-order note recommends sequencing within one track)`
  Eight `OrgApi*` views (`orgs/views.py:944-1271`) each subclass a two-level mixin stack (`JsonApiMixin` → `JsonAuthenticationRequiredMixin`/`JsonOrganizationAccessMixin`) that re-implements CSRF/auth/org-role/parsing per view — one of three coexisting idioms for authed state-changing JSON endpoints (SA46 already gated the silent-miss failure mode across all three; this fold reduces the template count). Fold the stack into one `OrgApiBaseView` that every `OrgApi*` view subclasses, preserving current behavior (auth, org-role checks, JSON error bodies) with a single implementation.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/views.py:219-1271`.
  *Acceptance:* all eight `OrgApi*` views subclass the new `OrgApiBaseView`; `JsonApiMixin`/`JsonAuthenticationRequiredMixin`/`JsonOrganizationAccessMixin` are removed or reduced to thin aliases if still referenced elsewhere; the existing `orgs` API test suite passes unchanged (behavior-preserving refactor, not a new contract).

### Track 2 — Module contracts & settings

SA21.2, SA37, SA38, SA40, SA43, plus its earlier share of the SA19–SA33 batch, are complete — detail in [CHANGELOG.md](../../CHANGELOG.md). New open items this pass, below.

#### Finding — `dr-engine-module-circular-lattice` (`why →` [arch-audit.md Finding 1](../others/arch-audit.md), compounding evidence — doc drift + duplicated literal)

- [x] **SA51 — Rewrite the false `backups/services.py` header contract.** `Tier 1 · Track 2 · deps: none`
  The header claims "intentionally under 400 LOC" and "every new orchestration feature should go in `dr_engine/`" — the file is well over 400 lines and SA43 correctly moved model-touching dispatch lifecycle *into* it, the opposite of what the header says. Rewrite it to state the real rule (model-touching lifecycle lives here; engine-pure logic in `dr_engine/`) before it misdirects the next contributor.
  *Files:* `quickscale_modules/backups/src/quickscale_modules_backups/services.py:1-10`.
  *Acceptance:* header docstring states the current, correct division of responsibility; no line-count claim that isn't true.
  *(why →* [tech-audit.md TA44](../others/tech-audit.md)*)*

- [ ] **SA54 — Deduplicate the stale-restore threshold constant.** `Tier 1 · Track 2 · deps: none (soft-sequence after SA51/SA52/SA53 — same file; also touches dr_engine/orchestration.py)`
  `dr_engine/orchestration.py:2804` hardcodes `timedelta(minutes=30)` in the CR-SA38-001 parity block while `backups/services.py:524` defines the canonical `STALE_RESTORE_THRESHOLD_MINUTES = 30` — the two can drift silently since core cannot import module services. Fix: move the constant (or an equivalent single source of truth) into `dr_engine` and have `services.py` import/re-export it, or pass it as a parameter into the orchestration call, so there is exactly one number.
  *Files:* `quickscale_core/src/quickscale_core/dr_engine/orchestration.py:2804`; `quickscale_modules/backups/src/quickscale_modules_backups/services.py:524`.
  *Acceptance:* the threshold exists in exactly one place; both the module-side and core-side stale-restore paths reference it; a test asserts both paths agree after changing the value in its single location.
  *(why →* [tech-audit.md TA45](../others/tech-audit.md)*)*

#### Finding — `backups-dispatch-fail-open-robustness` (`why →` [tech-audit.md TA42, TA46](../others/tech-audit.md))

- [ ] **SA52 — Fail hard when `manage.py` can't be resolved instead of silently falling back.** `Tier 1 · Track 2 · deps: none (soft-sequence after SA51 — same file)`
  `_get_manage_py()` (`services.py:264-278`) wraps resolution in `except Exception: pass` and falls through to a bare `"manage.py"` literal. In a deployment where `sys.argv[0]` isn't `manage.py` (gunicorn — the production norm) and `BASE_DIR/manage.py` is absent, `Popen` succeeds but the child dies instantly — for restore the artifact is stuck `STATUS_RESTORING` until the 30-minute stale threshold; for create/prune the admin reports "initiated" and nothing happens, silently. Fix: raise `BackupError` when no `manage.py` is resolvable, and do so before `_atomic_claim_restore` claims the artifact (the current call order at `:400` already does this — keep it).
  *Files:* `quickscale_modules/backups/src/quickscale_modules_backups/services.py:264-278` (all three dispatchers call it: `:400`, `:479`, `:508`).
  *Acceptance:* `_get_manage_py()` raises `BackupError` instead of returning a fallback string when resolution fails; a unit test simulates `sys.argv[0]` not being `manage.py` and `BASE_DIR` lacking one, asserting the raise and that no artifact is left claimed.

- [ ] **SA53 — Make the uploaded-restore-artifact copy crash-safe.** `Tier 1 · Track 2 · deps: none (soft-sequence after SA52 — same file)`
  `prepare_admin_uploaded_restore_artifact` (`services.py:365-366`) unlinks the existing local artifact file before `shutil.copy2`, with no `try/finally` — a copy failure (disk full, permissions) destroys the prior local copy and leaks the `mkdtemp` staging directory. Fix: copy to a temp name and `os.replace` into place atomically, and clean up the staging directory in a `finally`.
  *Files:* `quickscale_modules/backups/src/quickscale_modules_backups/services.py:281-370` (`prepare_admin_uploaded_restore_artifact`).
  *Acceptance:* a simulated copy failure (e.g. mocked `shutil.copy2` raising) leaves the pre-existing local artifact file intact and the staging directory removed; a regression test covers this path.

### Track 3 — Core/CLI plumbing

#### Finding — `dr-engine-module-circular-lattice` (`why →` [arch-audit.md Finding 1](../others/arch-audit.md), stage 1 only)

> **SA44 — complete.** Closed as one shipped pass plus a focused SA44 continuation that resolves CR-SA44-REV-001. Pass 1: replaced import-time adapter registration with explicit registration via `MANAGED_ADAPTER_ORIGINS.add("social")` + `refresh_managed_adapters()`. Deleted the `_is_import_time_adapter_circular_import` string-matching classifier outright. Split `runtime.py` into `runtime/__init__.py` (combined facade), `runtime/dr.py` (DR surface), and `runtime/manifest.py` (manifest/social surface) so the two domains stop interlocking at import time. Repointed social module's adapter imports from `quickscale_core.manifest.entry_point` to `quickscale_core.runtime.manifest` (the new canonical seam). Production prior-base-path refresh fix landed in `module_wiring_manager.py`. Broad targeted validation green across all changed files. Full detail in [CHANGELOG.md](../../CHANGELOG.md). Continuation (this pass): moved `refresh_managed_adapters()` from module scope into `_build_specs()` so every call is self-contained against prior suite mutations of `MANIFEST_ADAPTER_REGISTRY`. Added a focused regression test (`test_build_specs_recovers_from_cleared_registry`) proving a cleared registry is restored per `_build_specs()` invocation. Closes CR-SA44-REV-001 and SA44 as a whole.

- [x] **SA44 — Make `refresh_managed_adapters()` self-contained inside `_build_specs()`.** `Tier 1 · Track 3 · deps: none · resolves CR-SA44-REV-001`
  `_build_specs()`'s test helper relied on a single **module-level** `refresh_managed_adapters()` call executed once at test-file import time, so managed-module builds were not self-contained against prior-suite mutation of the global adapter registry. Fix: moved `refresh_managed_adapters()` into `_build_specs()` so each call is self-contained regardless of what ran before it in the suite.
  *Files:* `quickscale_cli/tests/commands/test_module_config_extended.py` (moved `refresh_managed_adapters()` from module scope into `_build_specs()`; added `test_build_specs_recovers_from_cleared_registry` regression test).
  *Acceptance:* `_build_specs()` refreshes the managed-adapter registry per call, not once at import time; the regression test proves recovery from a cleared `MANIFEST_ADAPTER_REGISTRY`; the full suite (130 tests) passes. Closes SA44 as a whole.

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

- [x] **SA55 — Add a decisions.md rule naming the two sanctioned JSON-API bases.** `Tier 1 · Track 3 · deps: none`
  **SA55 — complete.** Added [`§json-api-endpoint-base-contract`](./decisions.md#json-api-endpoint-base-contract) to decisions.md: DRF baseline for generic authed endpoints, `OrgApiBaseView` (pending SA50) for org-role-scoped endpoints, and an explicit statement that billing's plain-View + manual-CSRF idiom is scheduled for removal (SA56) rather than grandfathered as permanent legacy — matches the project's fail-hard/no-workarounds posture rather than the "migrate opportunistically" framing this item started with.
  *(why →* [arch-audit.md Finding 5](../others/arch-audit.md)*, Option 1 remaining pieces — the rule and the migration)*

- [ ] **SA56 — Migrate billing's four plain-View state-changing endpoints onto the DRF baseline.** `Tier 2 · Track 3 · deps: none (soft-sequence after SA55 — the rule should exist before the code that fulfills it, though not a hard technical dependency)`
  `CreateCheckoutSessionView` (`:160`), `CreateSubscriptionCheckoutView` (`:216`), `CancelSubscriptionView` (`:272`), and `CreateBillingPortalSessionView` (`:327`) are plain Django `View` classes wrapped in `@method_decorator(csrf_exempt, name="dispatch")` with a hand-written `_enforce_csrf()` call at the top of each `post()` — the idiom SA46's gate now polices but doesn't remove. The same file already has four `APIView`-based endpoints (`PlanListView`, `CreditBalanceView`, `CreditTransactionListView`, `SubscriptionDetailView`, `StripePublishableKeyView`) proving the DRF pattern works in this exact module: DRF's `SessionAuthentication` enforces CSRF automatically for session-authenticated requests, so migrating removes the manual `csrf_exempt`/`_enforce_csrf` pair entirely rather than just gating it. `StripeWebhookView`'s `csrf_exempt` is out of scope — it is signature-verified, a different trust class already in SA46's allowlist, not a login-required user endpoint.
  *Files:* `quickscale_modules/billing/src/quickscale_modules_billing/views.py:159-374` (the four views); their URL conf entries if `as_view()` call sites need adjusting; existing checkout/cancel/portal test suites.
  *Acceptance:* all four views subclass `APIView` with `IsAuthenticated`, matching the file's existing DRF endpoints; `csrf_exempt` and `_enforce_csrf` are deleted from the file entirely (SA46's gate has nothing left to police here); existing checkout/cancel/portal-flow tests pass unchanged (behavior-preserving migration on money paths — no new user-visible contract).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
