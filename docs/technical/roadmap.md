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

> **Closed batches (detail in [CHANGELOG.md](../../CHANGELOG.md)):** SA1–SA5 (2026-07-02), SA6–SA12 (2026-07-03), SA13.1–SA13.4 (2026-07-04), SA14.1–SA14.6 (2026-07-05), SA15.1–SA15.3 (2026-07-04), SA16.1/SA16.2 (2026-07-03), SA17.1–SA17.8 (2026-07-05), SA18.1–SA18.11 (2026-07-04), SA19 (2026-07-05), SA20 (2026-07-06), SA21.1 (2026-07-05), SA21.2 (2026-07-07), SA22 (2026-07-05), SA23 (2026-07-05), SA24 (2026-07-05), SA25 (2026-07-05), SA26 (2026-07-06), SA27 (2026-07-05), SA28 (2026-07-05), SA29 (2026-07-05), SA30 (2026-07-06), SA31 (2026-07-05), SA32 (2026-07-06), SA33 (2026-07-05), SA34 (2026-07-06), SA35 (2026-07-07), SA36 (2026-07-07), SA37 (2026-07-07), SA38 (2026-07-07), SA39 (2026-07-06), SA40 (2026-07-06), SA41 (2026-07-07), SA42 (2026-07-07), SA43 (2026-07-07), SA44 (2026-07-07), SA45 (2026-07-06), SA46 (2026-07-07), SA47 (2026-07-07), SA48 (2026-07-07), SA49 (2026-07-07), SA50 (2026-07-07), SA51 (2026-07-07), SA52 (2026-07-07), SA55 (2026-07-07). All closed per template rule — detail lives in CHANGELOG.md.
>
> **Origin note:** SA34–SA47 trace to the 2026-07-06 triage against [tech-audit.md](../others/tech-audit.md) (TA33–TA41) and [arch-audit.md](../others/arch-audit.md) (Findings 1–5), each sized Tier 1–2 (arch-audit's larger Findings 1/2/4/5 are cut down to their recommended *first step* only — later stages are explicitly deferred and remain tracked in arch-audit.md itself).
>
> **Origin note (2026-07-07, fix-plan pass):** SA48–SA56 trace to the 2026-07-07 delta-pass findings in [tech-audit.md](../others/tech-audit.md) (TA42–TA46) and [arch-audit.md](../others/arch-audit.md) (Finding 1's red flags and CR-SA44-REV-001 blocker, Finding 4's coverage-boundary sub-item, Finding 5's two remaining Option 1 pieces plus the billing migration promoted from "long tail" to scheduled work per user decision — no idiom is grandfathered as permanent legacy), each sized Tier 1–2. Every item fit Tier 1–2 without splitting; the two items large enough to flag (SA50, the `OrgApiBaseView` fold; SA56, the billing DRF migration) are Tier 2, not Tier 3.

> **Track status (2026-07-08, SA53/SA54 fix approach decided):** Track 1 — **0 open items, all complete** (SA48, SA49, SA50 — SA50 now complete). Track 2 — **2 open items, 0 blocked** (SA51/SA52 complete; SA53 — CR-SA53-REV-002 fix approach decided [manual retry loop on the raw fd], ready for implementation; SA54 — fix approach decided [parameter-passing, module keeps ownership], ready for implementation, soft-sequenced after SA53 on the same file). Track 3 — **1 open item, ready now, no blockers** (SA56 ready now — SA44 complete).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
(none — track complete)                 SA53 (deps: none; fix approach decided, ready)  SA56 (deps: none)
                                         SA54 (deps: none; soft-seq after SA53; fix approach decided)
```

All three tracks run fully in parallel — no hard cross-track implementation dependencies exist; each track's implementation files are independent. (The shared closeout files `CHANGELOG.md` and `docs/technical/roadmap.md` are the one exception — every track touches them during closeout, but that overlap is managed by the merge procedure above rather than being an implementation dependency.) The "soft-seq" notes above are intra-track only: same-file edits ordered to avoid needless rebasing, not hard technical dependencies.

### Track 1 — Tenant-context surface

All items in Track 1 are complete (SA47, SA48, SA49, SA50) — detail in [CHANGELOG.md](../../CHANGELOG.md). SA50 folded the `JsonApiMixin`/`JsonOrganizationAccessMixin` stack into one `OrgApiBaseView` as part of the `json-api-boundary-idiom-fragmentation` finding (see [arch-audit.md Finding 5](../others/arch-audit.md)).

### Track 2 — Module contracts & settings

SA21.2, SA37, SA38, SA40, SA43, SA51, plus its earlier share of the SA19–SA33 batch, are complete — detail in [CHANGELOG.md](../../CHANGELOG.md). New open items this pass, below.

#### Finding — `dr-engine-module-circular-lattice` (`why →` [arch-audit.md Finding 1](../others/arch-audit.md), compounding evidence — doc drift + duplicated literal)

- [ ] **SA54 — Deduplicate the stale-restore threshold constant.** `Tier 1 · Track 2 · deps: none (soft-sequence after SA53 — same file; also touches dr_engine/orchestration.py)`
  `dr_engine/orchestration.py:2804` hardcodes `timedelta(minutes=30)` in the CR-SA38-001 parity block while `backups/services.py:524` defines the canonical `STALE_RESTORE_THRESHOLD_MINUTES = 30` — the two can drift silently since core cannot import module services.
  **Decided (2026-07-08), ready for implementation:** pass the threshold as a parameter into `restore_admin_uploaded_backup()` rather than moving the constant into core. Its only caller is `admin.py` in the backups module (verified — it is not registered in `ADAPTER_FUNCTIONS`, so no CLI or other core-internal path needs its own copy of the value), so `admin.py` can pass `services.STALE_RESTORE_THRESHOLD_MINUTES` in explicitly. The module keeps sole ownership of the constant and core receives it via injection instead of owning backups-domain policy — this matches arch-audit.md Finding 1's own stated target shape for this exact value ("gives the stale-guard one home (module-side, with core receiving it via the port)") and makes zero changes to `runtime/dr.py`'s facade/export surface. (Rejected: moving the constant into `dr_engine` and having `services.py` import/re-export it — this follows existing import precedent in the file, but pulls a backups-domain policy value into core, the opposite of Finding 1's target direction, and touches the facade file the audit already flags as fragile.)
  *Files:* `quickscale_core/src/quickscale_core/dr_engine/orchestration.py:2777-2804` (`restore_admin_uploaded_backup` signature); `quickscale_modules/backups/src/quickscale_modules_backups/admin.py:436` (call site); `quickscale_modules/backups/src/quickscale_modules_backups/services.py:524` (constant — location unchanged).
  *Acceptance:* the threshold exists in exactly one place (`services.py`); `orchestration.py` no longer hardcodes `timedelta(minutes=30)`; a test asserts both paths agree after changing the value in its single location.
  *(why →* [tech-audit.md TA45](../others/tech-audit.md)*)*

#### Finding — `backups-dispatch-fail-open-robustness` (`why →` [tech-audit.md TA46](../others/tech-audit.md))

SA52 is complete — detail in [CHANGELOG.md](../../CHANGELOG.md).

- [ ] **SA53 — Make the uploaded-restore-artifact copy crash-safe.** `Tier 1 · Track 2 · deps: none`
  `prepare_admin_uploaded_restore_artifact` (`services.py:365-366`) unlinks the existing local artifact file before `shutil.copy2`, with no `try/finally` — a copy failure (disk full, permissions) destroys the prior local copy and leaks the `mkdtemp` staging directory. Fix: copy to a temp file under the same directory and `os.replace` into place atomically, and clean up the staging directory in a `finally`.
  *Files:* `quickscale_modules/backups/src/quickscale_modules_backups/services.py:281-370` (`prepare_admin_uploaded_restore_artifact`).
  *Acceptance:* a simulated copy failure (e.g. mocked `shutil.copy2` raising) leaves the pre-existing local artifact file intact and the staging directory removed; a regression test covers this path.
  **Shipped (not complete — see below):** Changed the local-artifact copy from `unlink(missing_ok=True)` + `shutil.copy2` (destroy-on-failure) to `shutil.copy2` to a `.tmp` suffix file + `os.replace` (atomic same-filesystem swap), preserving the existing artifact on any copy failure. All manual `_cleanup_admin_restore_upload_directory` calls in early-exit paths were consolidated into a single `finally` block so the staging directory is never leaked. Added `TestPrepareAdminUploadedRestoreArtifactSA53` in `test_services.py` with two regression tests: one proving a mocked `shutil.copy2` `OSError` leaves both the pre-existing file intact and the staging directory cleaned, and one proving the happy path materializes content at the authoritative backup location and persists `local_path`.

  **Decided (2026-07-08) — CR-SA53-REV-002 fix, ready for implementation:** The fd-based copy loop in `services.py:376-381` calls `os.write(fd, buf)` once per 64KiB chunk and discards the return value — a short write (the OS writes fewer bytes than given and returns that smaller count) silently truncates the artifact while the function still reports success. Fix: wrap the write in a retry loop — after each `os.write`, slice the unwritten remainder (e.g. via `memoryview`) and keep writing until the full chunk is flushed — before the existing `os.fsync(fd)` / `os.replace` step. This is deliberately the minimal-diff fix: the `mkstemp`-created fd, the single `finally: os.close(fd)`, and the `except: os.unlink(tmp_path)` cleanup that CR-SA53-REV-001 shaped specifically to eliminate a close-then-reopen-by-pathname symlink race are all left untouched. (Rejected: `os.fdopen(fd, "wb")` to get a `BufferedWriter`, whose `.write()` already retries short writes internally — it would move fd ownership to the wrapper, requiring the existing `finally: os.close(fd)` to be deleted and `os.fsync(fd)` split into `dst_f.flush()` + `os.fsync(dst_f.fileno())`, re-deriving fd-lifecycle reasoning already settled by REV-001 on a code path that's had two review rounds.)
  *Acceptance:* a mocked short `os.write()` return (writes fewer bytes than requested) still results in a byte-identical copy at the target path; a regression test covers this alongside the existing copy-failure and happy-path tests. Full detail in [CHANGELOG.md](../../CHANGELOG.md).

### Track 3 — Core/CLI plumbing

SA44 (Finding 1 stage 1, `dr-engine-module-circular-lattice`) is complete — detail in [CHANGELOG.md](../../CHANGELOG.md).

#### Finding — `json-api-boundary-idiom-fragmentation` (`why →` [arch-audit.md Finding 5](../others/arch-audit.md))

- [ ] **SA56 — Migrate billing's four plain-View state-changing endpoints onto the DRF baseline.** `Tier 2 · Track 3 · deps: none (SA55 complete — the sanctioned-base rule now exists in decisions.md)`
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
