# Architecture Audit — Open Findings

Last verified at `30b0b6b1` (2026-10-16). Open items only. Resolved findings and pass history
are in git history (`git log -- docs/others/arch-audit.md`). Finding IDs are slugs. Never cite
them from code, tests or other docs.

## Open findings

### 1. `generated-file-ownership-unmodeled` — module contracts live in user-owned generated files
**Horizon:** now (trigger: SA191 repins `bap-web-new` to 0.89.0) · **Size:** M · two-way door

- **Problem.** Only six emitted paths are managed: `settings/modules.py`, `urls_modules.py`,
  the two theme seam files, `.github/quickscale-ci-env` and `quickscale-operations.md`. Module
  contracts still land in user-owned theme pages (for example `CrmPage.tsx` consuming a crm
  endpoint). Each such change becomes a hand-applied adoption step per project: 46 steps at
  0.89.0, about 2 per active day, and 12 pending on `bap-web-new`.
- **Evidence.** `quickscale_core/.../project_state_hashes.py` (managed sets),
  `quickscale_cli/.../commands/contract_vintage.py` (adoption recorded on the operator's word),
  and `data/project_contract.yml` (the step list). Three upgrade mechanisms are maintained:
  prose steps, `quickscale_devtools/beta_migration` (12.5k lines) and the SA191 prompt port.
- **Correct shape.** Every emitted file is either managed (regenerated, never hand-edited) or
  user-owned with no module contract.
- **Next.** (a) Keep one upgrade mechanism, either `beta_migration` or the prompt port, and
  retire the other (S). (b) Route module-coupled page data through seam hooks in managed files
  as SA153 adds pages. Guard: the closed-world emission test refuses any module setting,
  endpoint or constant in a user-owned file except through a managed include.

### 2. `clean-break-schema-no-data-path` — no verified data upgrade path across releases
**Horizon:** now (trigger: SA204 (g) lifts rule 1, or SA153 goes live) · **Size:** S · one-way door

- **Problem.** The migration freeze makes shipped migrations immutable and makes restore
  content-keyed (SA204 a–f, h). But `quickscale update` compares migration content only under
  an *equal* version label (`_module_update.py`, the `installed_version == applied_version`
  branch). A cross-release update, which is exactly the upgrade the freeze exists to protect,
  is not content-checked until `MIGRATION_FREEZE_VINTAGE` is set (SA204 (j)).
- **Correct shape.** After the freeze, every database-fits-code check compares migration
  content identity regardless of label.
- **Next.** Inside SA204 (g), change the condition to "applied version ≥ freeze vintage", so an
  applied file must stay byte-identical and new files apply forward. Guard: an `update` test in
  which a label change plus a changed applied file is refused. Re-run the (f) rehearsal on a
  copy before the one-way step.

## Watchlist (deferred; act only when the trigger fires)

| ID | Concern | Trigger |
|---|---|---|
| `core-holds-module-vocabulary` | Core/CLI name modules (`social_manifest.py`, `module_options.py`, module-named apply steps, dr_engine loaders) | teams scheduled, a 13th module, a new module-named apply step |
| `manifest-dsl-vocabulary-growth` | Manifest DSL gains one keyword per module need | a validation keyword added for one module |
| `vendored-module-edits-undetected` | Edits under vendored `modules/` go undetected (only same-label migration edits are caught) | a second project with vendored edits, or a subtree-pull conflict |
| `session-advisory-lock-pooling` | Billing mutex is a session-level advisory lock | a pooler or pooled `DATABASE_URL` |
| `modules-english-only` | Module-rendered pages are English-only | SA153/SA154 needs a Spanish module page |
| `two-filesystem-lock-implementations` | `advisory_lock.py` and `dr_engine/_lock.py` | a third implementation |
| `ci-provisioning-hand-pins` | Hand-pinned residue in CI provisioning | a 13th module |
| `trigger-inputs-legacy-name` | `trigger_inputs` is the legacy name of the exact e2e allowlist | any context skipping a gate on it |
| `subscription-status-single-writer` | `Subscription.status` has one writing module | a second provider or an outside writer |
