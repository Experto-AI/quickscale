# Architecture Audit — Open Findings

Last verified at `30b0b6b1` (2026-10-16). Open items only. Resolved findings and pass history
are in git history (`git log -- docs/others/arch-audit.md`). Cite a finding only by its slug ID; section numbers are not stable.

## Open findings

### 1. `generated-file-ownership-unmodeled` — module contracts live in user-owned generated files
**Horizon:** now (trigger: SA299 regenerates `bap-web-new` on 0.89.0) · **Size:** M · two-way door

- **Problem.** Only six emitted paths are managed: `settings/modules.py`, `urls_modules.py`,
  the two theme seam files, `.github/quickscale-ci-env` and `quickscale-operations.md`. Module
  contracts still land in user-owned theme pages (for example `CrmPage.tsx` consuming a crm
  endpoint). Each such change becomes a hand-applied adoption step per project (50 declared
  steps on 2026-10-16).
- **Evidence.** `quickscale_core/.../project_state_hashes.py` (managed sets),
  `quickscale_cli/.../commands/contract_vintage.py` (adoption recorded on the operator's word),
  and `data/project_contract.yml` (the step list).
- **Correct shape.** Every emitted file is either managed (regenerated, never hand-edited) or
  user-owned with no module contract.
- **Next.** (a) One upgrade path in two stages, `beta_migration` then the prompt port, with a
  boundary rule (SA277). (b) Route module-coupled page data through seam hooks in managed files
  as SA153 adds pages. Guard: the closed-world emission test refuses any module setting,
  endpoint or constant in a user-owned file except through a managed include.

## Watchlist (deferred; act only when the trigger fires)

| ID | Concern | Trigger |
|---|---|---|
| `core-holds-module-vocabulary` | Core/CLI name modules (`social_manifest.py`, `module_options.py`, module-named apply steps, dr_engine loaders) | teams scheduled, a 13th module, a new module-named apply step |
| `manifest-dsl-vocabulary-growth` | Manifest DSL gains one keyword per module need | a validation keyword added for one module |
| `vendored-module-edits-undetected` | Edits under vendored `modules/` go undetected (migration content is compared under an unchanged version label, and on every pull from the freeze vintage on) | a second project with vendored edits, or a subtree-pull conflict |
| `session-advisory-lock-pooling` | Billing mutex is a session-level advisory lock | a pooler or pooled `DATABASE_URL` |
| `modules-english-only` | Module-rendered pages are English-only | SA153/SA154 needs a Spanish module page |
| `two-filesystem-lock-implementations` | `advisory_lock.py` and `dr_engine/_lock.py` | a third implementation |
| `ci-provisioning-hand-pins` | Hand-pinned residue in CI provisioning | a 13th module |
| `trigger-inputs-legacy-name` | `trigger_inputs` is the legacy name of the exact e2e allowlist | any context skipping a gate on it |
| `subscription-status-single-writer` | `Subscription.status` has one writing module | a second provider or an outside writer |
