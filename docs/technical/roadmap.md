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

> **Closed batches (detail in [CHANGELOG.md](../../CHANGELOG.md)):** SA1–SA5 (2026-07-02), SA6–SA12 (2026-07-03), SA13.1–SA13.4 (2026-07-04), SA14.1–SA14.6 (2026-07-05), SA15.1–SA15.3 (2026-07-04), SA16.1/SA16.2 (2026-07-03), SA17.1–SA17.8 (2026-07-05), SA18.1–SA18.11 (2026-07-04), SA19 (2026-07-05), SA20 (2026-07-06), SA21.1 (2026-07-05), SA21.2 (2026-07-07), SA22 (2026-07-05), SA23 (2026-07-05), SA24 (2026-07-05), SA25 (2026-07-05), SA26 (2026-07-06), SA27 (2026-07-05), SA28 (2026-07-05), SA29 (2026-07-05), SA30 (2026-07-06), SA31 (2026-07-05), SA32 (2026-07-06), SA33 (2026-07-05), SA34 (2026-07-06), SA35 (2026-07-07), SA36 (2026-07-07), SA37 (2026-07-07), SA38 (2026-07-07), SA39 (2026-07-06), SA40 (2026-07-06), SA41 (2026-07-07), SA42 (2026-07-07), SA43 (2026-07-07), SA44 (2026-07-07), SA45 (2026-07-06), SA46 (2026-07-07), SA47 (2026-07-07), SA48 (2026-07-07), SA49 (2026-07-07), SA50 (2026-07-07), SA51 (2026-07-07), SA52 (2026-07-07), SA55 (2026-07-07), SA56 (2026-07-08). All closed per template rule — detail lives in CHANGELOG.md.
>
> **Origin note:** SA34–SA47 trace to the 2026-07-06 triage against [tech-audit.md](../others/tech-audit.md) (TA33–TA41) and [arch-audit.md](../others/arch-audit.md) (Findings 1–5), each sized Tier 1–2 (arch-audit's larger Findings 1/2/4/5 are cut down to their recommended *first step* only — later stages are explicitly deferred and remain tracked in arch-audit.md itself).
>
> **Origin note (2026-07-07, fix-plan pass):** SA48–SA56 trace to the 2026-07-07 delta-pass findings in [tech-audit.md](../others/tech-audit.md) (TA42–TA46) and [arch-audit.md](../others/arch-audit.md) (Finding 1's red flags and CR-SA44-REV-001 blocker, Finding 4's coverage-boundary sub-item, Finding 5's two remaining Option 1 pieces plus the billing migration promoted from "long tail" to scheduled work per user decision — no idiom is grandfathered as permanent legacy), each sized Tier 1–2. Every item fit Tier 1–2 without splitting; the two items large enough to flag (SA50, the `OrgApiBaseView` fold; SA56, the billing DRF migration) are Tier 2, not Tier 3.

> **Track status (2026-07-07, SA46 review follow-up resolved):** Track 1 — **0 open items, all complete** (SA48, SA49, SA50 — SA50 now complete). Track 2 — **2 open items, 1 blocked** (SA51/SA52 complete; SA53 — **blocked by CR-SA53-REV-002** — the fd-owned copy loop must handle short `os.write()` results before closeout; SA54 ready after SA53 is unblocked; remaining items still soft-sequenced on `backups/services.py`). Track 3 — **0 open items, all complete** (SA56 complete — SA44 complete).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
(none — track complete)                 SA53 (deps: none; **blocked by CR-SA53-REV-002**)  (none — track complete)
                                         SA54 (deps: none; soft-seq after SA53)
```

All three tracks run fully in parallel — no hard cross-track implementation dependencies exist; each track's implementation files are independent. (The shared closeout files `CHANGELOG.md` and `docs/technical/roadmap.md` are the one exception — every track touches them during closeout, but that overlap is managed by the merge procedure above rather than being an implementation dependency.) The "soft-seq" notes above are intra-track only: same-file edits ordered to avoid needless rebasing, not hard technical dependencies.

### Track 1 — Tenant-context surface

All items in Track 1 are complete (SA47, SA48, SA49, SA50) — detail in [CHANGELOG.md](../../CHANGELOG.md). SA50 folded the `JsonApiMixin`/`JsonOrganizationAccessMixin` stack into one `OrgApiBaseView` as part of the `json-api-boundary-idiom-fragmentation` finding (see [arch-audit.md Finding 5](../others/arch-audit.md)).

### Track 2 — Module contracts & settings

SA21.2, SA37, SA38, SA40, SA43, SA51, plus its earlier share of the SA19–SA33 batch, are complete — detail in [CHANGELOG.md](../../CHANGELOG.md). New open items this pass, below.

#### Finding — `dr-engine-module-circular-lattice` (`why →` [arch-audit.md Finding 1](../others/arch-audit.md), compounding evidence — doc drift + duplicated literal)

- [ ] **SA54 — Deduplicate the stale-restore threshold constant.** `Tier 1 · Track 2 · deps: none (soft-sequence after SA53 — same file; also touches dr_engine/orchestration.py)`
  `dr_engine/orchestration.py:2804` hardcodes `timedelta(minutes=30)` in the CR-SA38-001 parity block while `backups/services.py:524` defines the canonical `STALE_RESTORE_THRESHOLD_MINUTES = 30` — the two can drift silently since core cannot import module services. Fix: move the constant (or an equivalent single source of truth) into `dr_engine` and have `services.py` import/re-export it, or pass it as a parameter into the orchestration call, so there is exactly one number.
  *Files:* `quickscale_core/src/quickscale_core/dr_engine/orchestration.py:2804`; `quickscale_modules/backups/src/quickscale_modules_backups/services.py:524`.
  *Acceptance:* the threshold exists in exactly one place; both the module-side and core-side stale-restore paths reference it; a test asserts both paths agree after changing the value in its single location.
  *(why →* [tech-audit.md TA45](../others/tech-audit.md)*)*

#### Finding — `backups-dispatch-fail-open-robustness` (`why →` [tech-audit.md TA46](../others/tech-audit.md))

SA52 is complete — detail in [CHANGELOG.md](../../CHANGELOG.md).

- [ ] **SA53 — Make the uploaded-restore-artifact copy crash-safe.** `Tier 1 · Track 2 · deps: none`
  `prepare_admin_uploaded_restore_artifact` (`services.py:365-366`) unlinks the existing local artifact file before `shutil.copy2`, with no `try/finally` — a copy failure (disk full, permissions) destroys the prior local copy and leaks the `mkdtemp` staging directory. Fix: copy to a temp file under the same directory and `os.replace` into place atomically, and clean up the staging directory in a `finally`.
  *Files:* `quickscale_modules/backups/src/quickscale_modules_backups/services.py:281-370` (`prepare_admin_uploaded_restore_artifact`).
  *Acceptance:* a simulated copy failure (e.g. mocked `shutil.copy2` raising) leaves the pre-existing local artifact file intact and the staging directory removed; a regression test covers this path.
  **Shipped (not complete — see blocker below):** Changed the local-artifact copy from `unlink(missing_ok=True)` + `shutil.copy2` (destroy-on-failure) to `shutil.copy2` to a `.tmp` suffix file + `os.replace` (atomic same-filesystem swap), preserving the existing artifact on any copy failure. All manual `_cleanup_admin_restore_upload_directory` calls in early-exit paths were consolidated into a single `finally` block so the staging directory is never leaked. Added `TestPrepareAdminUploadedRestoreArtifactSA53` in `test_services.py` with two regression tests: one proving a mocked `shutil.copy2` `OSError` leaves both the pre-existing file intact and the staging directory cleaned, and one proving the happy path materializes content at the authoritative backup location and persists `local_path`.

  **Blocking — CR-SA53-REV-002:** The fd-based copy loop in `services.py:376-381` ignores partial `os.write()` results, so a local restore artifact can be silently truncated/corrupted while the function reports success. Fix before closing SA53: handle short `os.write()` results (or use an fd-backed file object without reopening by pathname) and add a short-write regression test. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

### Track 3 — Core/CLI plumbing

SA44 (Finding 1 stage 1, `dr-engine-module-circular-lattice`) is complete — detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `json-api-boundary-idiom-fragmentation` (`why →` [arch-audit.md Finding 5](../others/arch-audit.md))

- [x] **SA56 — Migrate billing's four plain-View state-changing endpoints onto the DRF baseline.** `Tier 2 · Track 3 · deps: none (SA55 complete — the sanctioned-base rule now exists in decisions.md)`
  `CreateCheckoutSessionView`, `CreateSubscriptionCheckoutView`, `CancelSubscriptionView`, and `CreateBillingPortalSessionView` were plain Django `View` classes wrapped in `@method_decorator(csrf_exempt, name="dispatch")` with a hand-written `_enforce_csrf()` call at the top of each `post()`. All four now subclass `APIView` with `AllowAny` + `SessionAuthentication`, matching the file's five existing DRF endpoints. The `@method_decorator(csrf_exempt, ...)` decorators and the `_enforce_csrf` helper have been removed entirely — DRF's `SessionAuthentication` enforces CSRF automatically for session-authenticated POST requests. `_resolve_request_organization` and `_parse_json_object_payload` calls changed from `request` to `request._request` (the underlying `HttpRequest`) following the existing DRF pattern. `StripeWebhookView`'s `csrf_exempt` is unchanged (out of scope — signature-verified, different trust class). URL conf required no change — it already uses `.as_view()` uniformly. All existing checkout/cancel/portal-flow tests pass unchanged (behavior-preserving migration on money paths — no new user-visible contract). Closes SA56.

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
