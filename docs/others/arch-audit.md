# Structural Autopsy: QuickScale

> This file is regenerated on each autopsy run to state **present reality for planning**: the
> current orientation, the open findings in full detail, and a curated watchlist. Closed findings
> exist only as dated lines in the **Reconciliation log** at the bottom (closeout detail lives in
> [CHANGELOG.md](../../CHANGELOG.md)); version control preserves prior full text. Finding IDs are stable
> across runs.

---

## Autopsy — 2026-07-19 (re-run, delta pass over `09f9cbcc..82a73d1f` + invoker-directed frontend-theme probe)

### Orientation (2026-07-19)

QuickScale is a solo-maintained (Experto-AI/Victor Rocco) Python 3.13/3.14 + Poetry monorepo
(VERSION 0.87.0, integration branch `v87`): a **Django project generator** (`quickscale_core`
Jinja2 templates + plan/apply engine + DR engine; `quickscale_cli` Click surface) plus a **module
workspace** of first-party Django modules (teams still README-only). Generated apps: Django 6 +
PostgreSQL 18 + a Vite/React SPA (`showcase_react`, the sole theme), single-service Railway.
Tenancy enforcement unchanged (fail-closed `TenantManager` + FORCE RLS + AF9 wrapper + SA58 boot
guard); severity floor unchanged; **tenant isolation remains the highest-blast property.** Release
state: SA93 (e2e) closed with hosted evidence; **SA96-GATE is blocked on SA96-GATE-BLK-002** (19
quality-baseline regressions), whose decision is made (Option A — remediate, cut as **SA101**, the
sole release-path item); TP parallelization suite continues off the critical path (TP2b
validation-blocked, TP3b/TP4 open). **Growth direction (invoker testimony, this pass):** reduce
the friction of migrating an already-running frontend application onto a freshly generated
QuickScale project — the procedure should be as copy/paste as possible. That testimony overrides
inferred direction (§2f) and drove this pass's Probe D; it also promotes the frontend-theme seam
to the top-ranked finding.

**Commit-delta classification (§2f).** Base `09f9cbcc` (2026-07-17 pass HEAD) → `82a73d1f`,
65 commits. *Closeouts* (audited): SA97 (`a35af4f6` — shared reset fixture), SA98 (`220bc5ae` —
orgs-owned sanitizer), SA100 (`b5476e66` — recovery-theme exemption narrowed), SA99 review record
(`9ea166bf`), SA93 continuation (`1e7cbc2c` ci + `aea4d84e` docs, hosted evidence), TP1
(`4b9f8201`), TP2 (`e0d34ac1`), TP2b checkpoint (`b4412a1e`), TP3a (`d52b02ac`), SA96 coverage
checkpoint (`b7922aaa` — five test modules, no source changes). *Housekeeping*: ~50 roadmap/
CHANGELOG/merge commits. *Unlabeled-behavioral*, read at full depth: `e862415a` ("chore: add
devtools to quality gates" — Makefile/ruff gate expansion, benign, completes SA99's direction);
`667396cc` (one-line e2e workflow fix adding a second `y` confirm for destructive apply —
test-plumbing); `1e7cbc2c` also rebaselined 6 hashes in `sa90_emission_manifests.json` under a
ci-labeled message — verified to be the SA90 parity chain syncing after SA93's frontend-template
edits (the gate working, not drift). **Fix-regression audits: SA97 clean** (six divergent conftest
copies → one `tests_shared/reset_state.py`; all six module conftests import it; no private copy
remains), **SA98 clean** (sanitizer single-homed in `orgs/sanitization.py`; blog `views.py:29` and
listings `views.py:26` consume it), **SA100 clean** (exemption keyed on `theme == "__checkpoint__"`;
fail-closed direction preserved; dead constant deleted) — Finding 9's closure and the census-row-17
strengthening are confirmed in code. Read fully this pass: the entire `showcase_react` template
tree (70 `.j2` + 4 static files), `generator.py`'s emission/copy paths, `beta-site-migration.md`
(893 lines), `beta_migration.py` frontend taxonomy, `lint_frontend.sh`/`frontend_proof.sh`, the
SA97/SA98/SA100 diffs. Sampled: TP Makefile/scripts diffs, e2e workflow. Skipped: the five SA96
coverage test modules beyond mechanism identification.

### Enforcement census (§3.4)

| # | Invariant | Enforced by | Class | Trend this pass |
|---|-----------|-------------|-------|-----------------|
| 1 | Tenant isolation on reads/writes | fail-closed `TenantManager` + FORCE RLS + AF9 execute-wrapper | structural | stable; no tenancy file touched this delta |
| 2 | No bypassing DB role at boot | orgs boot guard (`apps.py`), `rolbypassrls` + `rolsuper` | structural | stable |
| 3 | Admin org-scoping | `TenantModelAdmin`; NOBYPASSRLS test posture | structural + gated | stable |
| 4 | DB privilege selection per process | SA68 launcher env contract | structural | stable; copy-pair re-verified equal this pass (`production.py.j2:185` / `orgs/apps.py:36`, both fail-closed) — watchlist |
| 5 | JSON endpoint idiom | `OrgApiBaseView`/DRF baseline + SA46 csrf-exempt CI gate | structural + gated | stable |
| 6 | Core↔module import direction | bidirectional import linter + `LEGACY_ALLOWED_IMPORTS` (3 modules) | gated, with exceptions | stable; the one deliberate dynamic edge unchanged (`orchestration.py:248`, still the only `import_module("quickscale_modules…")` in core) |
| 7 | Module manifest copy-pairs (module.yml ×2) | CI byte-identical sync gate | gated | stable |
| 8 | Tenant-model universe **membership** | SA15.3/SA45/SA49 derivation gates | gated | stable |
| 9 | Tenant-model purge **order** | hand-ordered `_DELETE_SPECS` (`purge_organization.py:64`) | convention | unchanged (Finding 4); untouched this delta |
| 10 | Deletion invariants at account boundary | one canonical check + SA70 `pre_delete` backstop | convention + backstop | stable (Finding 2) — `models.py:165/329`, `apps.py:194–206` re-verified at prior lines |
| 11 | pyproject TOML write safety | `_write_validated_toml` (3 CLI splice sites) | structural per package | stable |
| 12 | Generator-emitted file ownership | SA66 conformance gate + SA90 manifest-parity fixture | gated | stable; the parity fixture paid a 6-hash sync this delta (`1e7cbc2c`) — derivation chain working; devtools taxonomy still hand-synced outside it (Finding 7) |
| 13 | Generated-project boot correctness | `test_generated_project_runtime.py` boot smoke harness | gated | stable — but see new row 20: the harness boots Django; it never builds the frontend |
| 14 | Module suites run under a restricted DB role | `QS_*_DB_USER` hand-lists ×3 | gated | stable content (12 modules present in all three; line-number comment drift carried) |
| 15 | Release-gate test scope | publish.yml `test` job + e2e lane | gated | SA93 closed with hosted evidence; SA96-GATE blocked on BLK-002 → SA101 |
| 16 | No cross-org `organization_id` DML in module migrations | SA92 bounded tripwire + pg-parity baseline | gated | stable; discovery tuple still a 10-entry hand tuple (fail-silent for a new module — watchlist) |
| 17 | Theme validity (react-only) | core `theme_validation.py` seam + per-command preflight | structural seam, convention callers | **strengthened** (SA100): recovery-ledger exemption narrowed to `__checkpoint__`, fail-closed retained; 7 CLI callsites + the `apply_command.py:3836–3853` inline copy unchanged |
| 18 | Code-quality regression (complexity/size/dead-code) | `make quality` vs `quality_baseline.json` | gated | **contract clarified**: BLK-002 surfaced 19 regressions; maintainer ratified Option A (remediate against the existing baseline; per-entry shrink-only exemptions in decisions.md) — answers the prior pass's shrink-only question; SA101 open |
| 19 | Shared-code commons (runtime + test plumbing) | orgs-owned sanitizer seam + `tests_shared/reset_state.py` | structural homes, tested | **closure verified in code this pass** (SA97+SA98 fix-regression audits clean) |
| 20 | Rendered-frontend build/type validity | `make lint-frontend` (render → ESLint+tsc) + `make frontend-proof` (render → pnpm install/build) | **gated — SA103 wired into check/ci/publish** | **closed** — blocking `lint-frontend` job in `ci.yml`, absent-tool guard in local `make ci`/`check_ci_locally.sh`, and `frontend-proof` step blocking `publish.yml` build/publish; red flag retired |
| 21 | Frontend module-availability contract (TS interface ↔ Django flag ladder ↔ generator file gating) | none — hand-synced lists in ≥5 stations | convention | **NEW row** (Finding 10) — `useModules.ts.j2` tuples, `index.html.j2` 11-module ladder, `REACT_THEME_OPTIONAL_FILES`, `IN_PLACE_MODULE_REACT_SURFACES`, playbook step 6; SA90 pins per-file bytes, not cross-list consistency |

### Summary table

**Live findings: 3** — carried Findings 7, 2, and 4. *(Finding 10
`frontend-source-generation-specialized` was **closed** by the SA104→SA108 chain — see the
Reconciliation log, 2026-07-21.)*

| # | ID | Horizon | Confidence | Size | One-line problem |
|---|----|---------|-----------|------|------------------|
| 7 | `generated-file-ownership-unmodeled` | 6–18 months | High | M | The beta-migration tool still re-encodes file ownership in hand-synced tuples outside the SA66/SA90 derivation chain (Finding 10's closure shrank its surface) |
| 2 | `deletion-invariants-per-boundary-reimplementation` | deferred (teams) | High | S | Last-owner check is canonical with a `pre_delete` backstop; no domain-owned deletion service covers other boundaries' invariants (e.g. billing) |
| 4 | `org-model-universe-hand-enumerated` | deferred (teams) | High | M | Tenant-model membership is derivation-gated; purge *order* is hand-written and ungated on a uniformly `NOT DEFERRABLE` foundation |

---

### Finding 7: Generated projects have no file-level ownership contract — the upgrade path re-encodes it by hand

- **ID:** `generated-file-ownership-unmodeled`
- **Status this pass:** still-open, unchanged — `beta_migration.py` untouched this delta; all
  anchors re-verified at prior lines (`IN_PLACE_INFRASTRUCTURE_TARGETS:101`,
  `IN_PLACE_SUBSTITUTED_INFRASTRUCTURE_TARGETS:115`, `INTENTIONALLY_UNMANAGED:123`,
  `IN_PLACE_MODULE_REACT_SURFACES:257`); the file still does not import
  `get_generator_emission_mapping`.
- **Horizon & trigger:** `6–18 months` — third consumer site, a public "update my generated
  project" command, or the next change to the emitted-file universe.
- **Confidence:** High. **Context dependence:** wrong-for-now on consumer count.
- **Interaction with Finding 10 (new):** Finding 10's Option 1 shrinks this finding's surface —
  60+ frontend files become theme-owned static content whose ownership is trivially derivable,
  and `IN_PLACE_MODULE_REACT_SURFACES` loses most of its reason to exist. Sequence Finding 10
  stage 1 before any tuple-derivation work here.
- **Problem / Evidence / Options / Recommendation:** otherwise unchanged from the 2026-07-17 pass
  (production chain closed by SA66/SA90 and re-verified paying its sync correctly this delta;
  remaining scope is deriving the devtools taxonomy from `get_generator_emission_mapping()`,
  unscheduled, correctly gated on a third consumer or public update command). · **Size:** M
  remaining.

---

### Finding 2: Deletion-boundary invariants are re-implemented per boundary with no domain backstop

- **ID:** `deletion-invariants-per-boundary-reimplementation`
- **Status this pass:** still-open, deferred (teams) — re-verified at unchanged anchors:
  `is_last_owner_with_members` (`orgs/models.py:165`) consumed by the lock-guarded `delete()`
  (`models.py:329`); SA70 `pre_delete` receiver wired in `orgs/apps.py:194–206`; no file touched
  this delta (git log empty over the range).
- **Problem / Options / Recommendation:** unchanged (full text in version control) — billing's
  active-subscription-on-ownerless-org invariant still has no backstop; land a billing-side
  backstop if/when teams or an erasure command creates a second deletion path. · **Size:** S
  remaining.

---

### Finding 4: orgs hand-enumerates the cross-module model universe in unlinked literals

- **ID:** `org-model-universe-hand-enumerated`
- **Status this pass:** still-open, deferred (teams) — anchors re-verified:
  `TENANT_TABLE_REGISTRY` (`orgs/tenancy.py:128`, bidirectionally gated) and hand-ordered
  `_DELETE_SPECS` (`orgs/management/commands/purge_organization.py:64`); neither file touched this
  delta.
- **Problem / Options / Recommendation:** unchanged — purge-*order* correctness remains the one
  ungated property on a uniformly `NOT DEFERRABLE` FK foundation; Option 2 (derive the purge plan
  topologically from the FK graph) remains the live option when teams gives it a test bed.
  · **Size:** M remaining.

---

### Change-cost probes (§3.6)

- **Probe A — "a 14th module lands in `quickscale_modules/`"** (carried, one station class
  added). The ~eight backend hand stations are unchanged this delta (three `QS_*_DB_USER` lists
  intact at 12 modules each; SA92 discovery tuple still a 10-entry hand tuple, fail-silent). **New
  this pass:** if the module has a frontend surface, add ~5 more ungated stations —
  `useModules.ts.j2` tuples, `index.html.j2` ladder, `REACT_THEME_OPTIONAL_FILES`,
  `IN_PLACE_MODULE_REACT_SURFACES`, playbook step 6 — none linked by any gate (census row 21).
  Billing's flag-only frontend (decisions.md:187–192) is the measured evidence of a module walking
  away from those stations. **Verdict: ~8 backend + ~5 frontend hand stations; frontend stations
  feed Finding 10.**
- **Probe B — "add a third sanctioned privileged command"** (carried). Copy-pair re-verified
  equal this pass (`production.py.j2:185–186` / `orgs/apps.py:36`, both fail-closed). **Verdict:
  exonerated for fail direction; copy-pair carried on watchlist.**
- **Probe D — "migrate a running frontend app onto a freshly generated project" (new,
  invoker-named; measured from the shipped playbook + tooling, not estimated).** Stations:
  (1) derive donor/recipient identities; (2) slug/package substitutions across `quickscale.yml`,
  `pyproject.toml`, and the *generated* `useModules.ts` — avoidable only by the same-slug
  convention; (3) transplant donor `App.tsx` (manual merge whenever scaffold routes changed);
  (4) per-directory diff/copy of `pages/` and `components/`; (5) wholesale copy of `lib/`,
  `stores/`; (6) hand-JSON-merge of `package.json` dependencies; (7) hand-copy per-new-module
  React surfaces (playbook step 6); (8) keep the 8-file scaffold-owned config list — duplicated
  between playbook and `beta_migration.py`; (9) `pnpm install/build/test`; plus `App.tsx`/`main.tsx`
  reconciliation explicitly excluded from automation on both paths. **Verdict: ≥9 stations, two
  unavoidable manual merges, three hand-synced ownership lists — finding evidence (Finding 10).
  Under Finding 10's correct shape this collapses to: copy user-owned dirs, merge `package.json`
  deps, rebuild.**
- *Probe C (theme retirement) is retired — measured retrospectively in the 2026-07-17 pass; moot
  while the theme count stays at one; its successor concern (per-file specialization inside the
  one theme) is Probe D.*

### Fix order and interactions

> *Superseded in part (2026-07-21/2026-07-26): Finding 10 stages 1 and 2 are complete
> (SA104→SA108) and the SA101 → SA96-GATE step of the release path is closed. Only items 3 and 4
> below remain live; the current release critical path is SA112a–f → SA96-PUBLISH (roadmap.md).*

1. ~~**Finding 10 stage 1** (static-source move)~~ — done (SA104).
2. ~~**Finding 10 stage 2** (runtime-config completion)~~ — done (SA105/SA106/SA107/SA108).
3. **Finding 7's tuple-derivation remainder** — M, unscheduled; the taxonomy it must derive is now
   the smaller, post-Finding-10 one. Gated on a third consumer or a public "update my generated
   project" command.
4. **Findings 2 and 4** — deferred with teams; independent.

No live finding conflicts with the release critical path.

### Sound load-bearing decisions (protect these during remediation)

- **The `window.__QUICKSCALE__` runtime injection seam** (`templates/index.html.j2:14` →
  `useModules.ts:151`): the correct frontend/backend boundary — one typed injection point carrying
  project name and runtime module truth from `INSTALLED_APPS`. Finding 10's fix *extends* this
  seam; do not replace it or add a second injection mechanism.
- **The generator's verbatim-copy path** (`_theme_non_jinja_emitted_paths`): already the right
  infrastructure for static theme content; Finding 10 stage 1 is adoption, not construction.
- **Dual-layer tenancy enforcement** (fail-closed `TenantManager` + FORCE RLS + AF9 wrapper + SA58
  boot guard) — carried, untouched this delta.
- **orgs-owned `apply_force_rls`/`revert_force_rls`** as the single RLS-install seam, and the
  **SA89 persistence-port shape** — carried.
- **The SA97/SA98 commons homes** (`tests_shared/reset_state.py`, `orgs/sanitization.py`) —
  verified in code this pass with all consumers on the seam; new module test suites must consume
  them rather than minting new copies.
- **SA68's launcher env contract**, **`TenantModelAdmin`/canonical last-owner check**, **SA92's
  two-layer guardrail pattern**, and **the generated-project boot smoke harness** — carried.
- **The Option A quality-baseline decision** (remediate, don't re-baseline; per-entry shrink-only
  exemptions): the governance direction both audits asked for — protect it when SA101 tempts a
  reset.

### Watchlist (every carried item shows this pass's trigger evaluation — §8)

- **Module universe hand-enumerated in CI/script files.** Trigger: **not fired** — all three
  `QS_*_DB_USER` lists intact at 12 modules; only `ci.yml` gained additive parallelization lines
  (`4b9f8201`). Line-number comment drift carried. Carry.
- **SA92 guardrail discovery tuple is fail-silent for new modules.** Trigger: **not fired** —
  tuple unchanged (10 entries, `test_sa92_migration_squash_guardrail.py:68–79`). Carry.
- **Retired-theme preflight is per-command convention.** Trigger: **not fired**; surface touched
  only by SA100, which *strengthened* it (exemption narrowed to `__checkpoint__`, fail-closed
  retained, new preflight tests); 7 callsites and the `apply_command.py:3836–3853` inline copy
  unchanged. Carry.
- **Quality-baseline governance.** Trigger ("second wholesale reset / regression grandfathering"):
  **not fired — and the standing question is answered**: BLK-002's 19 regressions were routed as
  SA101 under a ratified remediate-don't-rebaseline decision with per-entry shrink-only exemptions
  (roadmap §SA96-GATE-BLK-002 Decision, 2026-07-19). Narrowed: watch that the decision text
  reaches decisions.md when the first exemption is recorded. Carry.
- **Reverse import ban is blind to dynamic imports.** Trigger ("second dynamic core→module
  edge"): **not fired** — still exactly one (`orchestration.py:248`). Carry.
- **Subprocess-env construction has no single CLI policy.** Trigger ("third bespoke builder"):
  **not fired** — still exactly two (`_build_quickscale_env:217`, `_isolated_poetry_env:545`).
  Carry.
- **Sanctioned privileged-command copy-pair.** Trigger: **not fired** — both frozensets re-read
  and equal. Carry.
- **Billing webhook concurrent-duplicate window.** Trigger: **not fired** — `billing/services.py`
  untouched this delta. Carry.
- **Dual child-table tenancy APIs.** Trigger: **not fired** — teams unscheduled. Carry.
- **Mutating CLI operations have divergent compensation mechanisms.** Trigger: **not fired** — no
  new mutating command or mechanism this delta. Carry.
- **`orgs/views.py` fusion.** Trigger: **not fired** — 1,226 lines, verified unchanged. Carry.
- **Grandfathered option defaults multi-sourced — tenth pass.** Trigger: **not fired** —
  `module_config.py` untouched. Carry.

*(Carried unchanged at low priority, unprinted: hardcoded `EXEMPT_PATH_PREFIXES` in
`orgs/middleware.py` — file untouched this delta.)*

### Teams landing checklist (carried — speculative, teams unscheduled)

> Unchanged from the 2026-07-17 pass, with one addition: if teams ships a frontend surface, it
> lands on Finding 10's ≥5 frontend hand stations as they exist at that time — build teams'
> surface *after* Finding 10 stage 2 if at all possible, so it is the first module whose frontend
> arrives as static flag-gated files instead of new template conditionals.

### Questions that would change the ranking

- **Will the maintainer accept dormant module files in generated trees?** Finding 10 stage 2's
  one product decision: unselected modules' pages/components exist as inert, flag-gated files.
  Yes → stage 2 proceeds and the migration playbook's frontend half collapses; no → Option 3
  (ownership manifest) becomes the fallback and the merge tax stays. (Affects Finding 10's size
  and the Finding 7 interaction.)
- **What is the first new domain or consumer after SA101/release?** Carried: teams (or any new
  module) moves Findings 2 and 4 from `deferred` to `6–18 months`; a third consumer site fires
  Finding 7. (Affects Findings 2, 4, 7.)

### Red flags (out of scope — fix now)

- **~~The rendered-frontend proof is wired into no gate.~~ RESOLVED (SA103, 2026-07-19).** The
  red flag this pass raised — `make lint-frontend`/`make frontend-proof` gated nowhere — was
  ticketed as **SA103** and closed: a blocking `lint-frontend` job now runs in `ci.yml`, the
  local `make ci`/`check_ci_locally.sh` fan-out includes it (absent-Node/pnpm guard only), and
  `publish.yml` runs `frontend-proof` before build/publish. Census row 20 reflects the closure.

Lenses scanned with no qualifying finding this pass: data/state integrity, trust boundaries,
consistency/failure models, observability, API contracts (the `window.__QUICKSCALE__` contract is
owned by Finding 10), concurrency, security architecture (SA98 sanitizer seam verified),
dependency/config, build/release (the ungated frontend proof is red-flagged, ticket-shaped),
performance, governance/gates (§5.XV produced census rows 20–21, owned by Finding 10 and the red
flag).

---

## Autopsy — 2026-07-17 (re-run, delta pass over the SA84–SA96 release-hardening batch)

> Superseded by the 2026-07-19 delta pass above, which verified the SA97/SA98/SA100 closeouts in
> code (fix-regression audits clean), re-verified Findings 7/2/4's anchors, opened Finding 10 from
> the invoker-directed frontend-theme probe, and re-measured the probes. Full text in version
> control. Stub kept for links.

---
## Autopsy — 2026-07-13 (re-run, delta pass over the SA77/SA79/SA59.3–.4/SA80/SA82/SA87 restricted-role closeout batch)

> Superseded by the 2026-07-17 delta pass above, which verified the closure of Findings 1 and 8 in
> code (fix-regression audits pass), re-verified Findings 2/4/7's evidence anchors, promoted the
> commons watchlist item to Finding 9, and re-measured all probes. The 2026-07-13 pass's full text
> (Finding 8 opened, the SA83–SA86 structural reading, both probes) is preserved in version
> control. This stub heading is kept so existing links resolve.

---

## Autopsy — 2026-07-11 (re-run, delta pass over the SA65/SA66/SA68/SA73 + SA59.1 checkpoint batch)

> Superseded by the 2026-07-13 delta pass. Full text in version control. Stub kept for links.

---

## Autopsy — 2026-07-10 (re-run, delta pass — first run on the V2 prompt)

> Superseded by the 2026-07-11 delta pass. Full text in version control. Stub kept for links.

---

## Autopsy — 2026-07-09 (re-run, delta pass) and module-by-module deep pass

> Superseded by the 2026-07-10 delta pass. Full text in version control. Stub kept for links.

---

## Autopsy — 2026-07-07 (re-run, delta pass)

> Superseded by the 2026-07-09 delta pass. Full text in version control. Stub kept for links.

---

## Autopsy — 2026-07-06 (re-run) and module-by-module deep pass

> Superseded by the 2026-07-07 delta pass. Full text in version control. Stub kept for links.

---

## Autopsy — 2026-07-04 (re-run) and module-by-module deep pass

> Superseded by the 2026-07-06 re-run. Full text in version control. Stub kept for links.

---

## Autopsy — 2026-07-03 (fresh full pass)

> Superseded by the 2026-07-04 re-run. Full text in version control. Stub kept for links.

---

## Reconciliation log (append-only)

- 2026-07-02 — 2026-06-30 autopsy, Findings 1–5: **resolved** (SA1.1–SA5.2; closeout in CHANGELOG.md).
- 2026-07-02 — Module Finding 2 (billing webhook idempotency): **resolved** (SA12.1).
- 2026-07-03 — 2026-07-02 Finding 2 (orgs god-module): **resolved** (SA7.2–SA7.4); Finding 3 (dual
  active-org truth): **resolved** (product decision D1); Finding 4 (core-as-runtime-API):
  **resolved** (SA9.1–SA9.6); Finding 5 (module↔generated-project contract drift): **resolved**
  (SA10.1/SA10.2 contract-vintage mechanism); Module Finding 1 (request→tenant-context boundary):
  **resolved** (SA11.1–SA11.7 shared `PublicSystemOrgReadMixin`/DRF baseline).
- 2026-07-04 — `registry-universe-mismatch`: **resolved** (SA15.1–SA15.3);
  `per-module-knowledge-fanout`: **resolved** (SA16.1/SA16.2 + SA6.1/SA6.2 derivation groundwork;
  the remaining grandfathered imperative entries are frozen shrink-only — residual tracked as a
  watchlist item above); `org-context-api-accretion`: **resolved** (SA13.1–SA13.4, its own option
  1 "consolidate + gate": five context primitives privatized behind
  `org_scope`/`PublicSystemOrgReadMixin`, 44 callsites migrated, AST lint gate hard-fail).
- 2026-07-04 (re-run) — `operator-read-path-undefined`: **still-open**; evidence re-verified
  current; SA14.1 (`TenantModelAdmin` base) landed, SA14.2–SA14.6 open; scope gap flagged
  (`adapters.py` `QUICKSCALE_MODE` callsites). Watchlist reconciled: billing-webhook window
  (updated for the Phase-3 restructure), child-table dual API, and `apply_command` growth carried
  forward; `_is_migrate_command` argv-sniffing and `EXEMPT_PATH_PREFIXES` carried unchanged at low
  priority; orgs-views fusion promoted from per-module note to watchlist; new item: grandfathered
  defaults multi-sourcing (T2.4/T2.5 unscheduled). Prior red flags reconciled: `QUICKSCALE_MODE`
  fail-open → tracked (SA14.6/TA19, scope gap noted); `operator_access` documentation-only →
  tracked (SA14.5); 2026-07-03 SSOT-drift instances (Phase-12/ledger/loader staleness, dangling
  `findings.md §Finding-8`/`roadmap §AF8` refs) → **fixed** (verified gone 2026-07-04).
- 2026-07-04 (module-by-module deep pass, core and cli included as modules) — **zero new
  findings**; five candidates investigated and steelmanned (org-API mixin discipline, seven-station
  option pipeline, static tenant-registry double ledger, billing services fusion, backups
  admin-embedded ops) — each recorded with the gate that holds it and its breaking trigger.
  Per-module verdicts added, including the teams landing checklist and SA20 shape guidance.
  New ticket-shaped item: port forms models to the `TenantModel` base (second idiom for the
  tenant contract).
- 2026-07-05 (roadmap cleanup) — `operator-read-path-undefined`: **resolved**. SA14.2/SA14.3
  ported all five module admins (crm/blog/forms/listings/billing) off `all_objects` onto
  `TenantModelAdmin`; SA14.4 flipped module test suites to NOBYPASSRLS-by-default; SA14.5 landed
  `operator_access(reason=...)` as a real, audited, read-only RLS predicate; SA14.6 fail-hardened
  `QUICKSCALE_MODE`, closing the scope gap this document flagged (`adapters.py:60,81` and
  `views.py:63`, in addition to `middleware.py:268` — all four now direct required reads, per
  CHANGELOG.md). This closes the sole open finding from the 2026-07-04 pass; no other finding is
  currently open.
- 2026-07-06 (re-run) — **three findings opened** from the seams the SA19–SA33 batch changed:
  `dr-engine-module-circular-lattice` (bidirectional core↔backups import lattice; SA20's guard
  expansion at `entry_point.py:1446` is the compounding evidence),
  `deletion-invariants-per-boundary-reimplementation` (SA28's view-level guard diverges from the
  lock-guarded model rule; no domain-level backstop; tech-audit §Structural-smells hand-off
  honored), `backups-admin-orchestration-accretion` (SA20 async lifecycle landed inline in
  `admin.py` against the 2026-07-04 shape guidance; 2026-07-04 candidate 5's holding gate broke).
  Watchlist reconciled: billing-webhook window carried (re-verified, no non-idempotent handlers);
  dual child-table API carried (both APIs present, teams still placeholder); apply-regeneration
  item carried **sharpened** (SA22 landed as a second, exception-safe-but-not-crash-safe recovery
  mechanism outside the ledger); orgs-views fusion carried (1,273 lines); grandfathered-defaults
  carried (T2.4/T2.5 unscheduled, third pass); **new** item: deploy-time configuration contract
  (literal-vs-env), promoted from tech-audit smell. Prior red flags reconciled: CHANGELOG dangling
  arch-audit anchor → **fixed** (verified gone); `entry_point.py` post-hook coercion defaults →
  **still present**, re-flagged (SA27 cleaned resolvers/apply-gate, not post-hooks). Sound
  decisions re-verified: CI gates present (`ci.yml:122,150,178,325`), AF9 execute-wrapper intact,
  SA14 admin port complete. Forms `TenantModel` port still pending (ticket-shaped, carried).
- 2026-07-06 (module-by-module deep pass, core and cli included as modules) — **two findings
  opened**, both promotions of candidates the 2026-07-04 deep pass had steelmanned, promoted
  because the pattern reproduced outside the holding gate: `org-model-universe-hand-enumerated`
  (2026-07-04 candidate 3 covered only the classification registry; this pass found the purge
  command's `_DELETE_SPECS` is a second hand registry and its "completeness" test validates a
  hand-list against a hand-list — no derivation anywhere) and `json-api-boundary-idiom-fragmentation`
  (2026-07-04 candidate 1 was orgs-local; this pass confirmed billing's checkout/cancel/portal
  views are a third idiom — plain Views with `csrf_exempt` plus manual `_enforce_csrf`). Five
  candidates investigated and not promoted, each recorded with its holding gate and breaking
  trigger: M2 state-consolidation shape-sniffing with a dead schema-version field (core),
  hand-rolled per-step capture compensation (core/dr), restore-attempt-not-an-entity (backups —
  feeds Finding 3's correct shape), string-spliced TOML editing (cli), billing ledger/locking
  discipline (re-verified sound). First-ever full reads: `project_state.py`, `apply/executor.py`,
  `advisory_lock.py`, `dr_engine/_lock.py`, `plan_command.py`, `purge_organization.py`, billing's
  view layer, notifications' webhook view. Periphery modules verified SA-batch-churn-only since
  the 2026-07-04 deep pass and spot-checked. Teams landing checklist extended (Finding 4 gate
  before models; Finding 5 base before endpoints).
- 2026-07-06 (roadmap cleanup, doc-consistency correction) — Finding 3
  (`backups-admin-orchestration-accretion`) reframed, **not resolved**: CR-SA20-007 and the TA36
  compare-and-swap fix (both cited here as the finding's "now" trigger) closed as part of SA20's
  full closeout, confirmed present in code (`backups/admin.py`'s `_atomic_claim_restore()`). The
  structural duplication itself (lifecycle logic inline in `admin.py`, once per branch) was not
  extracted during that closeout, so the finding stands but as standalone follow-up work rather
  than one that rides an already-open item. Orientation's "still open: SA20 (CR-SA20-007), SA21.2,
  SA26, SA30" line corrected — SA20, SA26, and SA30 are all complete; SA21.2 is the only open item.
- 2026-07-06 (roadmap cleanup) — Finding 4 (`org-model-universe-hand-enumerated`): **partial
  progress, not resolved**. SA45 landed Option 1's purge-spec half — the completeness test now
  derives its expected model set from `get_tenant_models()` instead of a third hand-written copy,
  closing the silent-staleness gap on the `_DELETE_SPECS` side. `TENANT_TABLE_REGISTRY`'s
  equivalent derivation check (Option 1's other half) and the full purge-plan derivation (Option 2)
  remain open; Finding 4 stays open pending those, and pending the teams build that motivates its
  horizon.
- 2026-07-07 (roadmap cleanup) — **Finding 3 (`backups-admin-orchestration-accretion`): resolved.**
  SA43 landed exactly the recommended first step: `dispatch_background_restore(artifact, *,
  confirmation)` (plus `_atomic_claim_restore`, `_get_manage_py`, and the claimable-status set) was
  extracted into `backups/services.py`, and both the recorded-artifact and uploaded-file admin
  dispatch branches now call the same function instead of carrying two inline copies. The
  2026-07-06 "reframed, not resolved" note above is superseded — the extraction it flagged as
  still-pending has since landed. Summary table and fix-order renumbered accordingly (Finding 3 row
  dropped; findings 1/2/4/5 keep their stable IDs and numbers).
- 2026-07-07 (re-run, delta pass over the SA34–SA46 closeout batch) — **all four findings
  still-open, zero new findings.** `dr-engine-module-circular-lattice`: still-open,
  **strengthened** — CR-SA38-001 hand-copied the module-side stale-restore guard
  (`services.py:524–557`) into `orchestration.py:2799–2818` with a literal 30-minute threshold and
  duplicated message strings because core cannot import module services; second dated instance of
  the coordination tax in four days; `services.py` header ("under 400 LOC, features go in
  dr_engine/") now contradicts both reality (620 lines) and the correct extraction direction the
  SA43 batch took. `deletion-invariants-per-boundary-reimplementation`: still-open, evidence
  unchanged (divergent last-owner copies intact, zero `pre_delete` receivers re-verified); SA41
  and SA35 hardened the existing boundary without giving invariants a domain owner; SA47 ready.
  `org-model-universe-hand-enumerated`: still-open, **narrowed with a correction** — the
  2026-07-06 claim that `TENANT_TABLE_REGISTRY` lacked a derivation check was inaccurate (SA15.3's
  `test_doc_consistency.py` bidirectionally cross-checks the literal against the marker-driven
  derived view; both Option 1 halves are therefore done); remaining scope is Option 2 (purge-order
  derivation) plus a newly named coverage boundary: every derivation gate sees only the 9-of-13
  modules hand-listed in `orgs/tests/settings.py:34–42`. `json-api-boundary-idiom-fragmentation`:
  still-open, **progressed** — SA46's csrf-exempt pairing gate landed as a blocking CI job
  (`ci.yml:206–231`), closing the silent-miss class; the three idioms remain in code; remaining
  scope is the `OrgApiBaseView` fold + a decisions.md rule + opportunistic billing migration.
  Watchlist: **new** item — shared module-runtime code has no sanctioned home (SA21.2 put
  client-IP into orgs' tenant-context module; SA26's sanitizer is byte-identical copies in
  blog+listings); six items carried delta-verified-untouched. Prior red flags reconciled:
  `BillingValidationError` swallow → **fixed** (SA41, distinct `BillingSubscriptionAnomalyError`
  logged); post-hook coercion defaults → **tracked** (SA42 scheduled, no longer re-flagged). New
  red flags: `_get_manage_py()` silent fallback to bare `"manage.py"`; SA21.2 helper's
  `getattr`-default settings reads; stale `services.py` header contract. Questions updated: the
  registry-retirement question is partially answered in code ("temporary SSOT … eventually
  replace"); T2.4/T2.5 hits its fourth unanswered pass with the teams boundary now imminent.
- 2026-07-07 (roadmap cleanup) — **progress recorded on all four open findings; none closed.**
  `dr-engine-module-circular-lattice`: SA44 (Option 1, stage 1) **landed** — the string-matching
  classifier is deleted and adapter registration is explicit; the finding stays open, Option 2
  (persistence port) is unscheduled and remains the next trigger (the CR-SA38-001 copy-pair is
  untouched by SA44, as noted when SA44 was scheduled). `deletion-invariants-per-boundary-reimplementation`:
  SA47 (first step) **landed** — the three divergent last-owner implementations are now one
  canonical `OrganizationMembership.is_last_owner_with_members()` with lock-guarded concurrent-deletion
  protection; the finding stays open pending a `pre_delete` receiver backstop and the teams build.
  `org-model-universe-hand-enumerated`: SA49 (coverage-boundary sub-item) **landed** — orgs'
  conformance-env module list is now CI-derived from `quickscale_modules/*/pyproject.toml`
  presence instead of hand-listed; the finding stays open pending Option 2 (purge-order
  derivation), scoped for teams kickoff. `json-api-boundary-idiom-fragmentation`: SA55 (the
  decisions.md rule) **landed** — `§json-api-endpoint-base-contract` now names the two sanctioned
  bases and schedules billing's migration (SA56) rather than grandfathering it; the finding stays
  open pending the `OrgApiBaseView` fold (SA50, open on Track 1) and the billing migration (SA56,
  open on Track 3). Red flags reconciled: `_get_manage_py()` silent fallback → **fixed** (SA52);
  SA21.2 helper's `getattr`-default settings reads → **fixed** (SA48); stale `services.py` header
  contract → **fixed** (SA51) — all three removed from the Red flags section, detail in
  CHANGELOG.md and tech-audit.md (TA42/TA43/TA44). Full narrative re-verification of Findings
  1/2/4/5's evidence prose is deferred to the next full autopsy re-run; this entry records what
  changed since the 2026-07-07 delta pass above without rewriting it.
- 2026-07-08 (docs cleanup, continued) — Finding 5 (`json-api-boundary-idiom-fragmentation`): **closed.**
  SA50 landed since the 2026-07-07 entry (SA55 already recorded). SA56 billing migration **completed
  2026-07-08** — all four plain-View endpoints migrated onto the DRF baseline. The blog dual-auth
  function-view path (`@_typed_csrf_exempt` + `authenticate_blog_api_request`) was not migrated — it was
  validated as a narrow documented bounded exception in decisions.md §json-api-endpoint-base-contract,
  matching the SA46 gate's existing treatment of `authenticate_blog_api_request` as an approved verification
  helper. All Finding 5 sub-items are resolved (SA46 gate, SA50 fold, SA55 rule, SA56 migration plus
  the bounded-exception documentation). Finding 5 is now closed. Summary table size updated from M to S
  on the prior entry, now marked closed.
- 2026-07-09 (re-run, delta pass over SA47–SA56 closeout + the 2026-07-09 make-check/make-ci
  commits) — **three findings still-open, one new finding, Finding 5 verified still closed.**
  `dr-engine-module-circular-lattice`: still-open, **progressed and re-strengthened** — the
  `runtime/` facade split landed (`dr.py`/`manifest.py`, Option 1 complete) but the combined
  facade added a hand-synced literal `__all__` union station (`runtime/__init__.py:42–105`), the
  social adapter had to route around the facade via a new `LEGACY_ALLOWED_IMPORTS["social"]`
  entry (`check_module_core_imports.py:77–81`) — the shrink-only list grew, and the linter now
  calls "legacy" the import the facade docstring recommends; SA54 deduplicated the stale-restore
  threshold as a parameter seam with a signature-pin test (right interim direction; the copy pair
  persists in gated form). Recommendation escalated: schedule Option 2 (persistence port) in the
  next planning cycle. **New Finding 6 `db-privilege-mode-procedural`**: DB-privilege selection
  has four mechanisms with three semantics (start.sh env-unset; production argv-membership
  ladder; local argv-switching ladder, new in `198a1951`; orgs positional argv boot-guard
  exemption); live source-level collision — start.sh's `createcachetable` runs under the
  superuser with no boot-guard exemption (no-Redis deploys should fail; red-flagged).
  `deletion-invariants-per-boundary-reimplementation`: still-open, **narrowed** — SA47's
  canonical check verified consumed at all four callsites; zero `pre_delete` receivers
  re-verified; remaining scope is the receiver backstop + teams.
  `org-model-universe-hand-enumerated`: still-open — literals intact (49 registry entries,
  hand-ordered `_DELETE_SPECS`), SA49 gate verified; **new caution:** `is_tenant_model()` gained
  `tenant_excluded` precedence and the composite-FK template switched to `NOT DEFERRABLE`, both
  inside housekeeping commits with no decision record. Watchlist: commons item sharpened
  (client-IP now ×3 counting the base/production template copies forced by settings-layering);
  TOML-splicing item sharpened (holding condition broken — new `_patch_module_path_dependencies`
  writes without validation; red-flagged); dual child-table API sharpened (`NOT DEFERRABLE`);
  billing-webhook/apply-regeneration/orgs-views-fusion carried verified-untouched;
  grandfathered-defaults carried (fifth pass, tax paid correctly on the new listings
  configurator); deploy-config item narrowed (privilege half promoted to Finding 6);
  `_is_migrate_command` unprinted item absorbed into Finding 6. New red flags: start.sh
  createcachetable BYPASSRLS collision; unvalidated TOML write; git-tracked accreting test
  artifacts (13 blog-upload PNGs + `pytest_log.txt`); two undocumented tenancy-semantics changes.
  Questions: T2.4/T2.5+teams (fifth pass, roadmap now fully drained); `NOT DEFERRABLE`
  deliberateness; local argv ladder intent.
- 2026-07-09 (module-by-module deep pass, core and cli included as modules) — **zero new
  findings promoted.** First-ever full reads: the social module end-to-end, `storage/helpers.py`,
  `remove_command.py`, `TenantModelAdmin` in `orgs/admin.py`. Five candidates investigated and
  held with recorded gates/triggers: billing per-handler auth preamble in the sanctioned DRF
  baseline; social's missing-table exception-message classifier (narrow, fail-hard on
  non-match); backups restore-attempt-not-an-entity carried — SA53 added crash-safe copy
  mechanics, not lifecycle states, so the trigger did not fire; CLI compensation-mechanism
  divergence (remove's `PathSnapshot` + ledger + SA22 + update's git-commits, with
  cross-mechanism reconciliation glue already present) — broadened the apply-regeneration
  watchlist item rather than promoting; core contracts-internal lazy-import cycle (ticket-shape).
  Finding 1 evidence **corrected in the finding's favor**: `6ea37301` repointed
  `dr_engine/adapter.py`'s lazy imports off the module shim onto orchestration directly — one
  cycle edge removed. Commons watchlist item resolved its own question: the third shared
  concern (per-org admin machinery) landed in orgs (`TenantModelAdmin` is the documented
  generalization of social's prototype), making "orgs is the module commons" the de facto rule —
  remaining work is writing it down and migrating the SA26 sanitizer copies. New red flags: DR
  media-path silent-local coercion (two sites in `6ea37301`, data-loss-shaped, fail-hard-audit
  class — hand off to tech-audit); social admin still on the ungeneralized `PerOrgAdminMixin`
  prototype with real drift (no VIEW-AS, no org-field locking). Straggler-idiom tally now two:
  forms (no `TenantModel` base, re-verified) and social admin. Periphery
  (crm/notifications/analytics/blog/listings) verified churn-free or type-only since reconciled
  SAs; teams still README-only.
- 2026-07-10 (re-run, delta pass over the SA57–SA64 closeout batch; first run on the V2 prompt —
  falsification pass, enforcement census, change-cost probes, and fix-regression audit added) —
  **four findings still-open (two narrowed), one new finding.**
  `dr-engine-module-circular-lattice`: still-open, **unchanged** — first quiet delta in four
  passes (no DR work landed; no new lattice stations; `LEGACY_ALLOWED_IMPORTS` did not grow);
  Option 2 (persistence port) confirmed scheduled for the next planning cycle.
  `db-privilege-mode-procedural`: still-open, **substantially narrowed** — SA63 passed the
  fix-regression audit (mechanism partially removed, not relocated; fail direction preserved; no
  new stations): the launcher env-pair contract landed, local's argv ladder deleted, the
  createcachetable collision fixed and verified by new generated-project boot smoke tests; Probe
  B re-measured a new privileged command at one station, disconfirming the prior "up to three
  places" claim for new commands; residual scope is the migrate path's three deciders
  (`production.py.j2:185,195` argv branches, `orgs/apps.py` `_is_migrate_command()`) plus the
  one-bit hatch overload (SA59's blanket test-harness export is its live consequence); horizon
  downgraded now → 6–18 months. **New Finding 7 `generated-file-ownership-unmodeled`**: the
  generator has no per-file ownership contract; `quickscale_devtools/beta_migration.py:43–115`
  hand-encodes the taxonomy in eight unlinked tuples with no derivation from the template tree
  and no gate; live gap — SA63's `start.sh` is absent from `IN_PLACE_INFRASTRUCTURE_TARGETS` and
  fresh-first keeps the donor's `production.py`, so each SA63 file is missed by one migration
  path (immediate manual verification red-flagged).
  `deletion-invariants-per-boundary-reimplementation`: still-open, deferred — zero `pre_delete`
  receivers re-verified; delta touched none of its files.
  `org-model-universe-hand-enumerated`: still-open, deferred — literals verified untouched; the
  2026-07-09 decision-record caution is now owned by SA60 (open, Track 1).
  Prior red flags reconciled: DR media silent-local coercion → **fixed** (SA57, verified
  `ModuleNotFoundError`-narrow with fail-hard on all other errors at both sites); social admin
  prototype → **fixed** (SA64, both admins verified on `TenantModelAdmin`, prototype deleted);
  createcachetable/boot-guard collision → **fixed** (SA63, verified `start.sh.j2:59` + smoke
  tests); unvalidated TOML write → **fixed** (SA62, all three CLI splice sites verified through
  `_write_validated_toml`); git-tracked test artifacts → **fixed** (SA61/SA25, `git ls-files`
  verified clean); undocumented tenancy-semantics changes → **tracked** (SA60 open; records not
  yet written). Watchlist trigger evaluations (V2 discipline): commons — not fired, carried;
  TOML-splicing — fired in modified form (devtools copy), retired into Finding 7 + new
  devtools-governance item; billing webhook — not fired (untouched since SA41), carried;
  dual child-table API — not fired, carried (SA60 pending); CLI compensation divergence — fired
  in modified form (beta_migrate's checkpoint model), held (no cross-mechanism reconciliation;
  operates on external trees), carried; orgs-views fusion — not fired (1,226 lines, unchanged),
  carried; grandfathered defaults — not fired (sixth pass; listings apply-shim filled a station
  correctly), carried; deploy-config contract — substantially landed (boot smoke harness),
  narrowed to the doc-only paragraph. Questions: local-argv-ladder intent → **answered by SA63**
  (deleted; env pair is the contract), retired; `NOT DEFERRABLE` deliberateness → carried, owned
  by SA60. New red flags: SA63 beta-site rollout verification; `ImproperlyConfigured` re-homing
  undocumented (`628c7d28` — third consecutive delta with semantics under a housekeeping
  message); apply's import-time subprocess-env snapshot (tech-audit hand-off). New watchlist
  item: `quickscale_devtools` outside the governance architecture. Sound decisions: boot guard
  strengthened (SA58 `rolsuper`); the generated-project boot smoke harness recorded as the
  runtime-confirmation layer prior passes asked for.
- 2026-07-10 (roadmap cleanup) — **Red flag resolved:** the `ImproperlyConfigured` re-homing
  decision-record gap is closed (SA69 — `decisions.md §ImproperlyConfigured-Exception-Identity`
  now records the exception-identity split, which class a contracts-layer vs. a Django-runtime
  catcher should import, and the housekeeping-label-discipline watch item; the three named
  adapter docstrings are corrected from the Django class to the first-party class). Removed from
  the Red flags section above. The lint/naming guard for the two same-named classes remains an
  open watch item per the decision record (also tracked in tech-audit.md's Notes section), not
  promoted to its own finding.
- 2026-07-11 (roadmap cleanup) — **Finding 6 (`db-privilege-mode-procedural`): closed.** SA68
  finished Option 1 (recommended path): `start.sh.j2`'s migrate line now carries the same env
  pair as its createcachetable line; `production.py.j2`'s `elif "migrate" in sys.argv` branch and
  `orgs/apps.py`'s `_is_migrate_command()` are both deleted — no argv inspection remains anywhere
  in the privilege-selection path. The one-bit hatch overload flagged in the recommendation is
  also resolved: the explicit `QUICKSCALE_PRIVILEGED_COMMAND`/`QUICKSCALE_NON_DB_COMMAND` pair
  replaces the single `QUICKSCALE_ALLOW_BYPASSRLS` flag for launcher sanction, recorded in
  `decisions.md §Launcher One-Shot Command-Env Contract (SA68)`. Summary table, enforcement
  census, fix-order, and sound-decisions sections updated; full Finding 6 narrative removed per
  this document's own closed-finding convention (prior text in version control). Detail in
  CHANGELOG.md (SA68 entry). **Finding 7 (`generated-file-ownership-unmodeled`): first step
  landed (not closed).** SA66 shipped Option 1's conformance gate — the beta-migration file
  taxonomy is now derived against the template tree with zero unclassified gaps; Option 2
  (generator-emitted ownership manifest) stays open, to be picked up if a third consumer or a
  public update command appears. **Red flag resolved:** `apply`'s import-time subprocess-env
  snapshot is fixed (SA65, closing tech-audit.md TA53) — removed from the Red flags section
  above. Also closed the matching watchlist item (deploy-time configuration contract for
  generated apps) now that `decisions.md` carries the SA68 paragraph.
- 2026-07-11 (roadmap cleanup) — **Red flag closed as out-of-scope:** "verify SA63 actually
  reaches `experto-ai-web` and `bap-web`" (SA67) is retired, not resolved by evidence — a new
  standing scope boundary, `decisions.md §Beta-Site External Verification Scope`, establishes
  that live deployed-state verification for the two beta sites is structurally unreachable from
  this monorepo (no repository or deployment access exists or is expected to exist from a
  coding-agent session or CI job here) and is therefore closed on discovery going forward rather
  than left open pending access. The repo-local half of the original red flag — the in-place
  path missing `start.sh`, the fresh-first path keeping the donor's `production.py` — was the
  actual defect and was already fixed by SA66's conformance gate. The "beta sites deploy without
  Redis?" Question is updated to reflect the same boundary: it cannot be answered by a future
  audit pass and is now a `beta-site-migration.md` maintainer to-do instead. Full detail in
  CHANGELOG.md (SA67 entry) and `docs/technical/roadmap.md` (Track 3, now clean).
- 2026-07-11 (re-run, delta pass over `ae8c386e..HEAD` — the SA65/SA66/SA68/SA69/SA73 closeouts
  plus the three SA59.1 checkpoint commits) — **four findings still-open (Finding 7 narrowed),
  zero new findings.** Fix-regression audits: **SA65 clean** (import-time env snapshot deleted;
  `env=None` default; scoped env only at the two nested CLI call sites — mechanism removed).
  **SA68 clean, Finding 6 closure re-verified in code** (zero argv inspection on the privilege
  path; two-signal contract validated fail-closed at both consumers); one minted station recorded
  as a new watchlist item — the sanctioned-command frozensets are a template↔module copy-pair
  with no sync gate, both halves fail-closed. **SA66 audited** (Finding 7 first step): the gate
  genuinely derives the emitted-file universe from the template tree and pins both ownership
  policies (`start.sh` in-place + substituted; `production.py` donor-owned by policy, recorded in
  `decisions.md §Generated-File Ownership`); residuals cited in the updated Finding 7 — the
  test-side copy of the generator's emission routing (incl. hardcoded `("showcase_react",)` for
  non-Jinja files), the unenforced decisions-rationale invariant, and devtools' placement outside
  the lint/typecheck universe while now import-load-bearing for the release gate. **SA73
  audited**: quality-gate plumbing, but its `mypy.ini` `ignore_missing_imports` for
  `quickscale_modules_backups.*` is a new Finding 1 cycle carrier (recorded), and its
  `_session_managed_adapters` fixture swallow is red-flagged. **SA59.1 checkpoint audited**: the
  blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export is verified gone from the unit path; ci.yml and
  publish.yml both run the split (DB-free unit + restricted-role integration with the SA58 guard
  live) — census rows 2/3 strengthened/restored, new rows 14/15 added; the currently-red
  integration gate is red-flagged (tracked, SA59.1 blockers). Probes: A ("14th module") — six
  ungated hand stations in workflows, fail-loud for PG modules via the guard, verdict watchlist;
  B ("third privileged command") — three stations, copy-pair fail-closed, verdict watchlist,
  Finding 6 stays closed. Findings: 1 still-open (second quiet delta; carrier +1); 7 still-open,
  **narrowed**, horizon now → 6–18 months (silent-miss class closed by the gate); 2 still-open,
  deferred (zero receivers re-verified; first step scheduled as SA70); 4 still-open, deferred
  (literals untouched; SA60's urgency raised by the forms/0007 restricted-role failure).
  Watchlist evaluations: commons — not fired, carried; devtools-governance — fired in modified
  form (release gate imports devtools), held, absorbed into Finding 7 evidence, carried; billing
  webhook — not fired, carried; dual child-table API — not fired, carried; CLI compensation —
  not fired, carried; orgs-views fusion — not fired (1,226 lines), carried; grandfathered
  defaults — not fired (seventh pass), carried; two new items (module-universe workflow
  enumeration; privileged-command copy-pair). Prior red flags: both 2026-07-10 flags already
  closed in the log (SA67 out-of-scope; SA65 resolved — SA65 re-verified in code this pass).
  Questions: "beta sites without Redis" retired (SA67 scope boundary); "production.py
  donor-owned deliberate?" **answered by SA66** (deliberate; recorded and test-pinned) — retired;
  `NOT DEFERRABLE` carried (SA60); one new question (does SA59.3's provisioning script own the
  module-list derivation?). New red flags: red integration gate at merge; the
  `ImproperlyConfigured` fixture swallow; autouse `organization_created` muting (both
  tech-audit hand-offs).
- 2026-07-12 (roadmap closeout pass) — **all three 2026-07-11 red flags resolved:** integration
  gate red at merge → **SA76** (ticketed quarantine mechanism, gate green); `_session_managed_adapters`
  `ImproperlyConfigured` swallow → **SA75** (narrowed to genuine missing-package-root only, CI
  registry assertion added); autouse `organization_created` muting → **SA74** (removed, replaced
  with opt-in fixture; the production defect it was concealing, tech-audit's TA54, is also fixed).
  **Finding 2's first step landed: SA70** (orgs `pre_delete` receiver backstop for the last-owner
  invariant on cascade-driven deletions) — finding stays open at reduced size (S remaining) pending
  a domain-owned deletion service for other boundaries (e.g. billing), deferred with teams.
  **Finding 4's decision-record caution resolved: SA60** (composite-FK `NOT DEFERRABLE` policy
  ratified in decisions.md, cross-module conformance gate added) — finding stays open pending the
  purge-order derivation (Option 2), deferred with teams. Findings 1 and 7 untouched this pass.
  Enforcement census rows 2, 9, 10 updated to reflect the above. This was a docs-hygiene/roadmap
  reconciliation pass, not a fresh code-reading autopsy — no new findings sought or opened.
- 2026-07-13 (re-run, delta pass over `6cc9ab74..HEAD` — the SA77/SA79/SA59.3–.4/SA80/SA82/SA87 restricted-role closeout batch plus `657cff28`) — **one new finding; four findings still-open (all quiet — no open-finding file touched in the code delta).** **New Finding 8 `module-rls-context-procedural`:** SA82 removed the SA76 BYPASSRLS quarantine and ran the full integration gate under the restricted `quickscale_test_role`, simultaneously exposing restricted-role RLS failures in four modules (blog SA83/86 fails, crm SA84/67+20, forms SA85/33+8+10err, listings SA86/6) — one structural root (procedural, per-callsite RLS-context acquisition, unverified under a real restricted role until now) split into four unknown-root tickets; verified statically that only `orgs` and `forms` migrations acquire `operator_access` while blog/crm/listings have cross-org data migrations that set none. Fix-regression audits of the code delta: SA79's `forms/0007` fix (`SET LOCAL app.operator_access`) is clean for forms but is the per-callsite pattern Finding 8 warns against relocating fleet-wide; `657cff28` (poetry env isolation) is clean/ticket-shaped but mints a second bespoke subprocess-env builder in `apply_command.py` (`_isolated_poetry_env` alongside `_build_quickscale_env`) — new watchlist item. `f6a8191e` ("Update dependencies") verified to carry no first-party code semantics; `production.py.j2` took only a cosmetic f-string quote fix. Findings 1/2/4/7 anchors re-resolved to current code — DR facade corrected to `quickscale_core/runtime/__init__.py:39–42`, import linter to `scripts/check_module_core_imports.py:60–82`; all four unchanged (Finding 1 third quiet delta; carrier count stable). Watchlist: module-universe workflow-enumeration item **trigger fired** (SA80.2 added a third `QS_*_DB_USER` hand-list in `test_integration.sh:368–382`, comment-synced by line number, not derived) — held on fail-loud, third station recorded, standing design question answered (SA59.3/SA80 chose hand-list). Probe A re-measured at seven ungated hand stations (up from six). Red flags: none open (the red integration gate is Finding 8). Questions: two on Finding 8 (is any SA83–SA86 failure a production NOBYPASSRLS read path; will the fixes share a helper or copy operator_access inline).
- 2026-07-14 (roadmap cleanup, status refresh — no fresh autopsy) — **Finding 8 progress:** the roadmap ratified **Option 1** (this finding's recommendation) as ticket **SA88** (orgs-owned shared RLS-context migration helper + conformance gate), ahead of SA84/SA86. SA88's mandatory triage step is **complete** and answers the first standing Question above: CRM's 67 failures bucket **0 migration-time / 67 fixture-time / 0 runtime-query** — **no production-severity NOBYPASSRLS read-path gap**, so Finding 8 stays severity-bounded (test-posture) and no new red flag is promoted. SA88 is at a blocked checkpoint (implementation/validation complete; held on CR-SA88-REV-002 completeness + CR-SA88-REV-004 formatting/lint-rerun — bounded implementation, no product decision). **SA85 (forms residual) closed** after independent review; the 2026-07-13 orientation/fix-order prose above that lists SA85 among Finding 8's open cluster is historical — the live cluster is now **SA84 (CRM) and SA86 (listings)** only, both gated behind SA88. Finding 8 remains open (the shared seam has not yet merged). Findings 1/2/4/7 unchanged; SA90 (Finding 7 interim) already recorded closed above.
- 2026-07-14 (roadmap cleanup, later same-day refresh — no fresh autopsy) — **Finding 8 seam status corrected:** the SA88 baseline seam (`operator_access_migration` in `orgs/tenancy.py`, `forms/0007` reroute, baseline conformance gate + lifecycle tests) is confirmed **merged to `v87`** (69cabb47) — superseding the prior entry's "the shared seam has not yet merged." CR-SA88-REV-004 is **resolved** (exact-commit review of e1d38bd5 confirmed lint/format). What remains open on Finding 8 is gate *robustness*, not the seam: the attempted e1d38bd5 hardening was withdrawn STATUS partial/unsafe, so SA88 is split for parallel continuation into **SA88a** (harden the gate's negative proofs, CR-SA88-REV-002) and **SA88b** (diagnose the forms regression SA88-QG-FORMS-001). Finding 8 stays open until SA88a+SA88b land and SA84/SA86 drain. **Finding 1 (`dr-engine-module-circular-lattice`) activated** on the roadmap (SA89a→SA89b, persistence port, Option 2) to use idle Track 3 capacity — no autopsy change, scheduling only.
- 2026-07-15 (roadmap cleanup, status refresh — no fresh autopsy) — **Finding 8 conformance gate re-based to a runtime/behavioral oracle.** After the static-provenance analyzer (SA88a/.1–.3 + SA88c) hit the review cap four times, the maintainer retired it and re-based the gate: a thin static layer (cross-org DML classification + raw-GUC ban + per-migration proof registration, **SA88d**) plus seeded restricted-role `MigrationExecutor` boundary proofs with value assertions (**SA88e**), reusing the SA59/SA82 restricted-role gate this document names a *sound load-bearing decision*. This **answers the second standing Question** ("will the SA83–SA86 fixes go through a shared helper or copy `operator_access` inline, and will the gate converge"): the shared `operator_access_migration` seam stays; the gate now proves acquisition by *execution* rather than static provenance, escaping the non-convergent static trap — and it is consistent with this finding's *Correct shape* ("one declared mechanism … the gate distinguishes declared-elevation from assumed-bypass") and *Steelman* (the restricted-role gate is the real oracle). The first Question (production NOBYPASSRLS read-path gap) remains answered *no* by SA88's CRM triage (0 runtime-query). Finding 8 stays **open** until SA88d/SA88e land and SA84/SA86 drain. The retired findings CR-SA88-REV-006/007 and CR-SA88A1-REV-002/003/004 are closed as superseded-by-oracle-pivot (detail in CHANGELOG §SA88 and roadmap §Track 1). No finding-prose rewrite — deferred to the next autopsy run.
- 2026-07-15 (roadmap cleanup, later same-day refresh — no fresh autopsy) — **Finding 1 (`dr-engine-module-circular-lattice`): CLOSED.** The persistence-port (Option 2) landed in full via **SA89a** (Django-free `BackupArtifactPersistence`/`BackupPolicyPersistence` protocols in core + fail-hard registry + `restore_admin_uploaded_backup` port, done 2026-07-14) and **SA89b** (orchestration-port closeout, done 2026-07-15). The three cycle carriers this finding tracked are all removed on `v87`: the direct `dr_engine/orchestration.py` → `quickscale_modules_backups.models` import, the DR `_LAZY_*` tables, and the backups `mypy.ini:94` `ignore_missing_imports` override (its removal is what surfaced the GATE-typecheck backups errors, since resolved). SA89b replaced the withdrawn custom AST boundary scanner with a declarative reverse import ban in `scripts/check_module_core_imports.py` (zero `import quickscale_modules` in core) plus a modules-absent runtime proof; SA89B-CR-001 closed as obsoleted-by-descope. **SA89B-CR-004 (low/advisory)** remains open against `check_module_core_compatibility.py`, independent of the finding. Enforcement census row 6's `mypy.ini:94`-carrier note and the summary-table Finding 1 row are now stale — full finding text superseded, detail in CHANGELOG §SA89a/§SA89b; a fresh autopsy run will drop the finding block.
- 2026-07-15 (roadmap cleanup, later same-day refresh — no fresh autopsy) — **Finding 8 re-based again: squash-to-final-schema replaces the runtime-oracle line.** The maintainer confirmed no deployed DB to preserve and chose to squash every module's migrations to a final-schema `0001_initial` (`organization_id NOT NULL` from row zero), which empties the cross-org-*migration* class outright — nothing to backfill, so the SA88 gate saga (seam + SA88a–e static analyzer + SA88d/SA88e runtime oracle) has no target and is deleted, not completed. The shared `operator_access_migration` helper is retired as dead code; `apply_force_rls`/`revert_force_rls` and RLS enforcement (SA59/SA82) are unchanged. The **fixture** half of Finding 8 survives: **SA84 (CRM, 67 fixtures)** remains open on Track 1; **SA86 (listings)** closed 2026-07-15. The retired CR-SA88-REV-006/007 and CR-SA88A1-REV-002/003/004 close as obsoleted-by-schema-squash (was superseded-by-oracle-pivot). Finding 8 stays **open** until the squash lands and SA84 drains. See roadmap §Cross-cutting decision.
- 2026-07-15 (roadmap cleanup — doc-consistency note) — **SA-ID collision resolved.** The roadmap's squash-migrations ticket had reused **SA90**, which CHANGELOG and this document already own for the *closed* Finding-7 generator-emission-mapping work. The squash ticket is renamed **SA92** in the roadmap; **SA90 continues to mean the emission-mapping export** here and in CHANGELOG (unchanged). SA91 (parallel integration loop) is unaffected.
- 2026-07-17 (roadmap cleanup, status refresh — no fresh autopsy) — **Finding 8 (`module-rls-context-procedural`): CLOSED (fully drained).** The squash-to-final-schema (SA92) landed on `v87`, emptying the cross-org-*migration* class; the surviving **fixture** half is now drained on both sides: **SA84 (CRM, 67 fixtures) completed 2026-07-17** (263 passed / 21 skipped / 0 failed, 95.25% coverage, quarantine empty, independent change-review STATUS ok) and **SA86 (listings) closed 2026-07-15** — see [CHANGELOG.md §SA84/§SA86/§SA92](../../CHANGELOG.md). The two standing Questions were both answered *no production-severity gap*: SA88's CRM triage bucketed 0 runtime-query failures, and the shared `operator_access_migration` seam was retired as dead code by the squash. No open ticket carries this finding. The finding block (§Finding 8), the summary-table Finding 8 row, and enforcement census rows 14/16 are now stale — full finding text superseded, detail in CHANGELOG; a fresh autopsy run will drop the block. Per this document's convention, closed-finding context lives here and in CHANGELOG only.
- 2026-07-17 (re-run, delta pass over `803daef7..09f9cbcc` — the SA84–SA96 release-hardening
  batch) — **two closures verified in code, one new finding, Finding 7 strengthened, Findings 2/4
  unchanged.** **Finding 1 (`dr-engine-module-circular-lattice`): resolved, closure re-verified by
  fix-regression audit** — all three cycle carriers confirmed gone in current code (no
  `quickscale_modules_backups` import in `orchestration.py`; no DR `_LAZY_*` tables; no backups
  entry in `mypy.ini`); the SA89 persistence port is the correct shape (Django-free protocols +
  fail-hard registry, `dr_engine/persistence.py`); no prior sound decision regressed; one
  commitment noted, not minted by the fix: the pre-existing dynamic
  `import_module("quickscale_modules_storage.helpers")` edge (`orchestration.py:248`, old commit
  `dc0a0596`) survives the new static reverse ban — recorded as a watchlist item (ban blind spot),
  not a relocation. The SA54 threshold copy-pair is also gone (single definition in
  `backups/services.py:554`). **Finding 8 (`module-rls-context-procedural`): resolved, closure
  re-verified by fix-regression audit** — every tenant module's migrations squashed to
  `0001_initial` calling orgs-owned `apply_force_rls` (mechanism removed, and the RLS-install seam
  is now genuinely shared); `operator_access_migration` verified absent from the codebase; the
  SA92 guardrail is a decision-recorded bounded tripwire + pg-parity baseline; the fixture half
  drained through the sanctioned `org_scope` primitives — the copied conftest *glue* is cited as
  Finding 9 evidence, recorded there rather than reopening Finding 8. **New Finding 9
  `module-commons-unowned`** — promotion of the commons watchlist item after its trigger fired
  twice in one delta (SA84/SA85 near-identical `_reset_test_state` conftest copies in crm+forms;
  blog carries a divergent third variant; `tests_shared/isolation.py` has one consumer; the SA26
  sanitizer pair enters its sixth pass; no decisions.md commons rule exists). **Finding 7:
  still-open, strengthened** — SA94's theme retirement paid the predicted hand-sync tax
  (`beta_migration.py` +53 hand-edited lines, decisions.md taxonomy correction); anchors corrected
  to the src-layout path; devtools still outside ruff/mypy (partially mitigated: GATE-quality now
  covers it). **Findings 2/4: still-open, deferred** — all anchors re-verified at prior line
  numbers; no file touched this delta (Finding 4's purge-command path recorded in full:
  `orgs/management/commands/purge_organization.py:64`). Commit-delta: ~127 commits — closeouts
  audited above; two deceptively named commits verified docs-only (`0e49e647`, `fb0d1b71`); one
  chore-labeled behavioral commit read at depth (`76c5cc55` quality-baseline reset — verified
  scope expansion, not regression grandfathering; undocumented, watchlist). Census: rows 6/14
  updated, old row 16 retired, new rows 16–19 added (SA92 tripwire; theme validity; quality
  baseline; commons). Probes: A re-measured (~eight hand stations; new fail-silent SA92 discovery
  tuple; the Finding 8 migration station removed); B carried (copy-pair unchanged, fail-closed);
  C measured retrospectively from SA94 (~10+ stations — confirms Finding 7's O(themes) claim).
  Watchlist: commons **promoted to Finding 9**; module-universe item **partially fired** (the
  line-number comment-sync has already drifted: `test_integration.sh:393` cites ci.yml 399-410 vs
  actual 403–414; content matches, fail-loud holds — carried); four new items (SA92 discovery
  tuple fail-silent; theme-preflight convention; quality-baseline governance; reverse-ban dynamic
  blind spot); seven items carried not-fired. Prior red flags: none were open. Prior Questions:
  both 2026-07-13 Finding 8 questions were answered in the 2026-07-14/15 log entries (0
  runtime-query failures; helper superseded by squash) — retired; two new questions (post-release
   domain; quality-baseline shrink-only intent). Red flags: none this pass (one doc-staleness note
   on `decisions.md:1237`, not promoted).
- 2026-07-18 (SA98 closeout) — **Finding 9 (`module-commons-unowned`): CLOSED.** SA97 closed
  the shared test-plumbing half and SA98 closed the runtime sanitizer half: the orgs-owned
  sanitizer seam is consumed by blog and listings, with sanitizer uniqueness/caller proof passed.
  No SA98-specific blockers or findings were identified. The unrelated repository-wide
  coverage/dead-code/complexity baseline remains outside this ticket.
- 2026-07-19 (re-run, delta pass over `09f9cbcc..82a73d1f` + invoker-directed frontend-theme
  probe) — **one new finding; three findings still-open; three closeouts verified in code.**
  **Fix-regression audits: SA97 clean** (six divergent conftest reset copies → one
  `tests_shared/reset_state.py`; all six module conftests consume it; mechanism removed, not
  relocated), **SA98 clean** (sanitizer single-homed in `orgs/sanitization.py`; blog+listings
  import the seam; no second copy), **SA100 clean** (recovery-ledger exemption narrowed to
  `theme == "__checkpoint__"`; fail-closed preserved; dead `_RECOVERY_PROBE_PATHS` deleted —
  census row 17 strengthened) — Finding 9's closure stands verified. **New Finding 10
  `frontend-source-generation-specialized`** (top-ranked, horizon `now`, invoker-named growth
  direction): the showcase_react theme specializes user-editable frontend source at generation
  time (60 of 70 `.j2` files are byte-static under raw-wrappers; module universe hand-synced in
  ≥5 stations; project identity double-encoded against the existing `window.__QUICKSCALE__`
  runtime seam), so generated frontends are unportable and migration is the 893-line playbook's
  merge procedure instead of a copy — Probe D measured ≥9 stations, two unavoidable manual merges
  (`App.tsx`/`main.tsx`), three hand-synced ownership lists; billing shipping "flag only" with no
  starter React surface (decisions.md:187–192) is the paid compounding evidence. **Findings 7/2/4
  still-open** — all anchors re-resolved at prior lines; none of their files touched this delta;
  Finding 7 gains a sequencing note (Finding 10's fix shrinks its taxonomy surface).
  Commit-delta: 65 commits — closeouts audited; ~50 housekeeping; three chore/ci-labeled
  behavioral commits read at depth (`e862415a` devtools gate expansion — benign; `667396cc`
  e2e confirm plumbing; `1e7cbc2c` SA90 fixture 6-hash sync after SA93 template edits — the
  parity chain working). Census: rows 17/18/19 updated (SA100 strengthening; BLK-002 → SA101
  Option A ratified — answers the prior pass's shrink-only question, retired; SA97/SA98 closure
  verified), new rows 20 (rendered-frontend proof ungated — red-flagged) and 21 (frontend
  module-availability contract, convention). Probes: A carried +5 frontend stations; B carried
  (copy-pair equal); C retired (moot at one theme); D new (finding evidence). Watchlist: twelve
  items evaluated, all not-fired, all carried (quality-baseline item narrowed to a
  decision-record-location watch). Prior red flags: none were open. New red flag: `make
  lint-frontend`/`frontend-proof` wired into no gate — a theme TypeScript/build break ships
  through a green release gate.
- 2026-07-19 (SA103 closeout) — **red-flag row 20 (rendered-frontend proof ungated): closed.**
  SA103 (`13b13ac5`) wired `lint-frontend` into `ci.yml` as a blocking job with Node/pnpm/cache
  setup, added the target to the local `make ci` / `check_ci_locally.sh` fan-out behind an
  absent-Node/pnpm-only guard, and placed `frontend-proof` in `publish.yml`'s test job before
  downstream build/publish. Census row 20 updated to `gated`. The structural finding (Finding 10,
  census row 21) remains open for the frontend-theme de-specialization chain (SA104 → SA105/SA106)
  on Track 2. Full evidence in CHANGELOG.md (SA103 entry) and roadmap.md (completed).
- 2026-07-19 (SA104 closeout) — **Finding 10 stage 1 (byte-static frontend source move): complete
  (Finding 10 remains open for stages 2a/2b).** SA104 moved 57 byte-static `showcase_react` theme
  files onto the generator's verbatim-copy path (`_theme_non_jinja_emitted_paths`) — `.j2` suffix
  and `{% raw %}` wrappers dropped, emitted bytes unchanged (SA90 parity fixture stayed green;
  two-project `frontend/src` diff zero). 13 genuine active-Jinja files remain. This is the safe,
  mechanical first stage of Option 1; the semantic de-specialization (module-availability surface
  SA105, project identity SA106) is still open on Track 2, so Finding 10 stays open. Advisory
  SA104-ADV-001 (generated projects' `.pre-commit-config.yaml.j2:10` strict `check-json` over
  emitted JSONC `frontend/tsconfig.json`) deferred. Full evidence in CHANGELOG.md (SA104 entry)
  and roadmap.md (Track 2).
- 2026-07-21 — **Finding 10 (`frontend-source-generation-specialized`): CLOSED/SUPERSEDED by
  SA105/SA106/SA107/SA108 — the full frontend de-specialization chain is complete.** SA105
  (dormant-file generation) made all module React pages unconditionally present as dormant,
  flag-gated files for fresh current-theme recipients — no per-module page-copy steps needed
  at migration time. SA106 (identity de-spec) made `useModules.ts`, `Dashboard.tsx`, and
  `Sidebar.tsx` project-agnostic and byte-identical across projects on the same theme version,
  with `projectName` read from `window.__QUICKSCALE__.projectName` at runtime — no
  generation-time identity patching. SA107 (fail-hard seam validation) replaced silent
  fallback/optional-chaining in `resolveProjectConfig()`, `renderQuickScaleRoot()`, and
  `main.tsx` with the fail-hard `validateQuickScaleConfig()` gateway, enforcing strict boolean
  module flags and a valid `projectName` at runtime. SA108 (migration-doc rewrite) corrected
  `beta-site-migration.md` frontend guidance to reflect the project-agnostic `frontend/src`
  contract, removing obsolete identity-fix and conditional-patch steps, distinguishing fresh
  current-theme recipients (SA105 dormant guarantees apply) from legacy pre-SA105 recipients.
  **Legacy compatibility caveat (Finding 10 remnant, not reticketed):** SA105 dormant-file
  guarantees apply only to fresh current-theme recipients generated post-SA105; legacy pre-SA105
  in-place recipients have no retroactive dormant guarantee for any module surface. The shipped
  post-apply adoption step copies only missing forms/social surfaces — it does **not** backfill
  blog/crm/listings. If blog/crm/listings surfaces are absent after continuation, the maintainer
  must stop, record the compatibility gap, and restore/reconcile them manually. Finding 10's
  remaining "correct shape" (Option 1 stage 2 completion for dormant files, Option 3 ownership
  manifest) is not independently ticketed — the dormant-files decision was ratified and the
  playbook reflects it. The Summary table's "Live findings" line above and the Fix order section
  are superseded by this entry; the next full autopsy re-run will drop the finding block. Detail
  in CHANGELOG.md (SA105/SA106/SA107/SA108 entries) and roadmap.md (Track 2).
- 2026-07-23 (roadmap/doc-consistency cleanup) — the deferred bookkeeping from the 2026-07-21
  entry above is now applied: the Summary table's "Live findings" line reads **3** (Findings 7/2/4)
  and Finding 10's row is dropped; its detail section is reduced to a closed-status stub pointing
  here. No new audit was run and no finding status changed — this only reconciles the live sections
  with the already-recorded 2026-07-21 closure.
- 2026-07-26 (roadmap/doc-consistency cleanup) — the last Finding 10 remnants in the live sections
  are removed: the closed-status stub section is deleted (closure now lives only in the 2026-07-21
  and 2026-07-23 log entries above, per this document's convention), and the Fix order section is
  reconciled — stages 1 and 2 struck as done (SA104→SA108), the stale `SA101 → SA96-GATE →
  SA96-PUBLISH` critical-path sentence replaced by a pointer to roadmap.md's current
  `SA112a–f → SA96-PUBLISH` path. Live findings remain **3** (Findings 7, 2, 4); Finding 7 stays
  unscheduled, Findings 2/4 stay deferred with teams. No new audit was run and no finding status
  changed. Recorded in CHANGELOG.md (2026-07-26 arch-audit bookkeeping entry).
