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

> **Closed batches (detail in [CHANGELOG.md](../../CHANGELOG.md)):** SA1–SA5 (2026-07-02), SA6–SA12 (2026-07-03), SA13.1–SA13.4 (2026-07-04), SA14.1–SA14.6 (2026-07-05), SA15.1–SA15.3 (2026-07-04), SA16.1/SA16.2 (2026-07-03), SA17.1–SA17.8 (2026-07-05), SA18.1–SA18.11 (2026-07-04), SA19 (2026-07-05), SA20 (2026-07-06), SA21.1 (2026-07-05), SA21.2 (2026-07-07), SA22 (2026-07-05), SA23 (2026-07-05), SA24 (2026-07-05), SA25 (2026-07-05), SA26 (2026-07-06), SA27 (2026-07-05), SA28 (2026-07-05), SA29 (2026-07-05), SA30 (2026-07-06), SA31 (2026-07-05), SA32 (2026-07-06), SA33 (2026-07-05), SA34 (2026-07-06), SA35 (2026-07-07), SA36 (2026-07-07), SA37 (2026-07-07), SA38 (2026-07-07), SA39 (2026-07-06), SA40 (2026-07-06), SA41 (2026-07-07), SA42 (2026-07-07), SA43 (2026-07-07), SA44 (2026-07-07), SA45 (2026-07-06), SA46 (2026-07-07), SA47 (2026-07-07), SA48 (2026-07-07), SA49 (2026-07-07), SA50 (2026-07-07), SA51 (2026-07-07), SA52 (2026-07-07), SA53 (2026-07-08), SA54 (2026-07-08), SA55 (2026-07-07), SA56 (2026-07-08), SA57 (2026-07-10), SA58 (2026-07-10), SA61 (2026-07-10), SA62 (2026-07-10), SA64 (2026-07-10). All closed per template rule — detail lives in CHANGELOG.md.
>
> **Origin note:** SA34–SA47 trace to the 2026-07-06 triage against [tech-audit.md](../others/tech-audit.md) (TA33–TA41) and [arch-audit.md](../others/arch-audit.md) (Findings 1–5), each sized Tier 1–2 (arch-audit's larger Findings 1/2/4/5 are cut down to their recommended *first step* only — later stages are explicitly deferred and remain tracked in arch-audit.md itself).
>
> **Origin note (2026-07-07, fix-plan pass):** SA48–SA56 trace to the 2026-07-07 delta-pass findings in [tech-audit.md](../others/tech-audit.md) (TA42–TA46) and [arch-audit.md](../others/arch-audit.md) (Finding 1's red flags and CR-SA44-REV-001 blocker, Finding 4's coverage-boundary sub-item, Finding 5's two remaining Option 1 pieces plus the billing migration promoted from "long tail" to scheduled work per user decision — no idiom is grandfathered as permanent legacy), each sized Tier 1–2. Every item fit Tier 1–2 without splitting; the two items large enough to flag (SA50, the `OrgApiBaseView` fold; SA56, the billing DRF migration) are Tier 2, not Tier 3.

> **Origin note (2026-07-10, fix-plan pass):** SA57–SA64 trace to the 2026-07-09/10 findings in [tech-audit.md](../others/tech-audit.md) (TA47–TA52, all opened by the unreviewed `6ea37301`/`198a1951` "fix: make check"/"fix: some make ci" commits) and [arch-audit.md](../others/arch-audit.md) (the Red flags section's DR-media/social-admin/createcachetable/TOML-splice/test-artifact items — several of which are the same defects tech-audit found independently and are merged into one task below — plus Finding 6's recommended first step and Finding 4's doc-only decision-record sub-item). Findings 1, 2 and 4's *remaining* structural work (the persistence port, the `pre_delete` backstop, the purge-order derivation) stay in arch-audit.md — each is sized M. Findings 2 and 4 are `deferred`: teams is decided **not next, not planned** (brainstormed placeholder only, no committed timeline — see [decisions.md §Teams module status](../technical/decisions.md#multitenant-saas-architecture)), so their teams-driven horizon no longer applies and there is no near-term trigger pulling them into this batch. Finding 1 Option 2 (the persistence port) is independent of teams' timeline but still M-sized and scheduled for its own next planning cycle rather than this fix-plan pass. Pulling any of the three into this batch as full structural rewrites would be Tier 3. Every item below fit Tier 1–2 without splitting; SA60 (composite-FK policy + conformance gate) and SA63 (Finding 6's launcher-contract first step) are Tier 2, the rest are Tier 1.

> **Origin note (2026-07-10, second fix-plan pass, HEAD `ae8c386e`):** SA65–SA70 trace to the V2-prompt re-run of both audits. From [tech-audit.md](../others/tech-audit.md): TA53 (`apply-subprocess-env-pythonpath-pollution`, opened this pass from the side-channel commit `628c7d28`). From [arch-audit.md](../others/arch-audit.md): Finding 7's recommended first step (`generated-file-ownership-unmodeled`, new this pass — the conformance gate, Option 1), Finding 6's recommendation to finish the migrate-path deciders (`db-privilege-mode-procedural`, narrowed `now`→`6–18 months` but still open scope), the two Red flags (SA63's unverified beta-site rollout; the undocumented `ImproperlyConfigured` re-homing), and Finding 2's recommendation to land the `pre_delete` receiver backstop as opportunistic hardening independent of teams' timeline (`deletion-invariants-per-boundary-reimplementation` — only the receiver-backstop first step, not the full M-sized finding). Finding 1 (persistence port) and Finding 4's purge-order derivation (Option 2, needs teams as a real second consumer) are excluded from this batch per the same Tier-3-avoidance rule as the prior pass — both stay open in arch-audit.md. Every item below fits Tier 1–2: SA66 (Finding 7's gate) and SA68 (Finding 6's migrate-path finish) are Tier 2; SA65, SA67, SA69, SA70 are Tier 1.

> **Track status (2026-07-10, SA65–SA70 opened):** Track 1 — **3 open items** (SA59, SA60, SA70). Track 2 — **1 open item** (SA69). Track 3 — **4 open items** (SA65, SA66, SA67, SA68).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)        Track 2 (module contracts & settings)     Track 3 (core/CLI plumbing)
───────────────────────────────         ───────────────────────────────────       ───────────────────────────
SA59 — drop bypassrls auto-prime        SA69 — decisions.md record for the        SA67 — verify + patch SA63 on the
SA60 — composite-FK deferability          ImproperlyConfigured re-homing            beta sites (urgent, do first)
  policy + conformance gate                                                       SA65 — stop propagating the CLI's
SA70 — orgs pre_delete receiver                                                     PYTHONPATH env to foreign
  backstop (Finding 2 first step)                                                   subprocesses (quick win)
                                                                                   SA66 — generated-file ownership
                                                                                     conformance gate (Finding 7)
                                                                                   SA68 — finish the migrate-path
                                                                                     launcher env-pair contract
                                                                                     (Finding 6 remainder)
```

All three tracks run fully in parallel — no hard cross-track implementation dependencies exist; every task below touches files no other open task touches, with two exceptions noted where they occur. Within Track 1, SA59/SA60/SA70 touch disjoint files (`Makefile`+`scripts/test_unit.sh`; `orgs/tenancy.py`+forms migrations; `orgs/signals.py`+a new receiver test) and share only `decisions.md` (additive sections, not a real conflict — see the shared-closeout-files note below). Within Track 3, SA65/SA66/SA67/SA68 touch disjoint source files and share only `decisions.md`; run them in this order within the track: **SA67 first** (it's the urgent red flag — arch-audit explicitly says it "shouldn't wait for the gate"), then SA65 (independent quick win), then SA66, then SA68. **Soft cross-track dependency:** SA68 deletes `orgs/apps.py`'s `_is_migrate_command()` (a Track 1 file) and its fix is only *demonstrably* exercised in CI once SA59 has removed the blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` test-harness export — arch-audit's fix-order note recommends bundling them "in the same batch, so the guard is demonstrably exercised the week the contract completes." This is a timing recommendation, not a file or merge blocker: SA68 is correct on its own regardless of merge order, but prefer landing SA59 first (or the same week) so the CI signal is real. (The shared closeout files `CHANGELOG.md` and `docs/technical/roadmap.md` are the one universal cross-track exception — every track touches them during closeout, managed by the merge procedure above.)

### Track 1 — Tenant-context surface

SA47, SA48, SA49, SA50, SA58 are complete — detail in [CHANGELOG.md](../../CHANGELOG.md). SA50 folded the `JsonApiMixin`/`JsonOrganizationAccessMixin` stack into one `OrgApiBaseView` as part of the `json-api-boundary-idiom-fragmentation` finding (see [arch-audit.md Finding 5](../others/arch-audit.md)). Open: SA59, SA60 (carried from the prior pass), SA70 (new this pass), below.

#### Finding — `test-tooling-auto-primes-bypassrls-hatch` (`why →` [tech-audit.md TA49](../others/tech-audit.md))

- [ ] **SA59 — Stop auto-priming `QUICKSCALE_ALLOW_BYPASSRLS=1` in the test-unit path.** `Tier 1 · Track 1 · deps: none`
  `Makefile:321-327` (`test-unit`) and `scripts/test_unit.sh:365-366` both blanket-export `QUICKSCALE_ALLOW_BYPASSRLS=1` for every module suite, which (a) disables the SA58 boot guard (now landed — checks both `rolbypassrls` and `rolsuper`) entirely during CI and local `make test-unit` runs and (b) flips the SA14.4 collection-time opt-in so `bypass_rls`-marked tests always run — contradicting the SA14.4 decision still documented at `quickscale_modules/orgs/tests/settings.py:14-18` and in every module conftest. No environment currently demonstrates the boot guard firing against a bypassing role.
  *Files:* `Makefile:321-327`; `scripts/test_unit.sh:365-366`; `.github/workflows/ci.yml:340` (verify the coverage gate's env after the export is removed).
  *Acceptance:* the blanket export is removed; CI's test-unit job runs against a NOBYPASSRLS role (create one via `QS_*_DB_USER` if the current CI role has BYPASSRLS/superuser — verify against the same container SA58's test targets), and developers set the SA14.4 hatch explicitly per-suite when they need it. `make test-unit` documents the opt-in in its help text if it doesn't already.
  *(why →* [tech-audit.md TA49](../others/tech-audit.md)*)*

#### Finding — `composite-fk-deferability-contract-diverged` (`why →` [tech-audit.md TA50](../others/tech-audit.md), [arch-audit.md Finding 4](../others/arch-audit.md) caution + Questions)

- [ ] **SA60 — Pick and enforce one composite-FK deferability policy.** `Tier 2 · Track 1 · deps: none`
  `6ea37301` silently flipped the Option C composite-FK helper (`orgs/tenancy.py:903`, `_ADD_COMPOSITE_FK_SQL`) from `DEFERRABLE INITIALLY DEFERRED` to `NOT DEFERRABLE`, with no decisions.md record and no test asserting the new behavior. This diverges from `forms/0007`'s own inlined `DEFERRABLE INITIALLY DEFERRED` SQL (and its `test_migrations.py:457-505` assertion) and from every *existing* database (fresh installs get `NOT DEFERRABLE`, existing ones keep `DEFERRABLE` — fleet drift with no aligning migration). Empirically verified this pass (PostgreSQL 18): `SET CONSTRAINTS <name> IMMEDIATE` on a `NOT DEFERRABLE` FK is a no-op, so `NOT DEFERRABLE` is defensible on fail-fast grounds — but it needs to be the *documented*, uniformly-applied policy, not a one-module drift. Bundle in the second, cheaper doc gap arch-audit flagged in the same commit: `is_tenant_model()`'s `tenant_excluded`-marker-beats-manager/base-class precedence change (`tenancy.py:1548+`) also has no decision record.
  *Files:* `docs/technical/decisions.md` (two new entries: composite-FK deferability policy under the Option C child-table section; `tenant_excluded` precedence rule); `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py:903` (helper SQL, if the decision changes it back) and `:1548+` (precedence — doc-only, no code change expected); `quickscale_modules/forms/src/quickscale_modules_forms/migrations/0007*.py` (align to the chosen policy); `quickscale_modules/forms/tests/test_migrations.py:457-505` and `quickscale_modules/crm/tests/test_migrations.py:1107,1158` (update assertions/stale comments to match); extend the SA35-style cross-module conformance gate to assert one deferability policy for all Option C composite FKs.
  *Acceptance:* decisions.md states the deferability policy (recommend keeping `NOT DEFERRABLE` given the empirical fail-fast verification, but ratify explicitly) and the `tenant_excluded` precedence rule; `forms/0007` and the `tenancy.py` helper emit the same deferability clause; a new conformance test fails if any Option C composite FK diverges; the two now-stale test comments (`crm/tests/test_migrations.py:1107,1158`) are corrected to reflect the no-op-on-NOT-DEFERRABLE behavior.
  *(why →* [tech-audit.md TA50](../others/tech-audit.md)*,* [arch-audit.md Finding 4](../others/arch-audit.md)*)*

#### Finding — `deletion-invariants-per-boundary-reimplementation`, first step (`why →` [arch-audit.md Finding 2](../others/arch-audit.md))

- [ ] **SA70 — Add an orgs `pre_delete` receiver backstop for the last-owner invariant.** `Tier 1 · Track 1 · deps: none`
  Today the last-owner/personal-org invariant (`OrganizationMembership.is_last_owner_with_members()`, `orgs/models.py:165`) is enforced only at boundaries that choose to call it — `AccountDeleteView` and both orgs view callsites — so any deletion path that doesn't go through one of those four callsites (e.g. a future GDPR erasure command, or a direct ORM/admin delete) bypasses the rule entirely, since instance `delete()` overrides don't run under Django's deletion collector for cascades. Arch-audit's Finding 2 is `deferred` overall (full M-sized scope needs the teams build to justify a domain-owned deletion service), but explicitly flags this first step as "small enough to land as a general hardening item without waiting on teams."
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/signals.py` (new `pre_delete` receiver on the `User` model, calling the existing SA47 canonical check); `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py` (wire the receiver in `ready()` if not already using a signals-autodiscovery pattern — check the existing `ready()` for how other receivers are registered); a new regression test that deletes a last-owner `User` directly via the ORM (bypassing the view layer) and asserts the deletion is refused.
  *Acceptance:* a direct `user.delete()` ORM call on a sole owner of a multi-member org raises/refuses exactly like `AccountDeleteView` does today; the four existing callsites are unaffected (the receiver is a backstop, not a replacement); no change to the sole-member self-removal behavior documented as deliberate (SA47's orphaned-org watch item).
  *(why →* [arch-audit.md Finding 2](../others/arch-audit.md)*)*

### Track 2 — Module contracts & settings

SA21.2, SA37, SA38, SA40, SA43, SA51, SA52, SA53, SA54, SA57, SA64, plus its earlier share of the SA19–SA33 batch, are complete — detail in [CHANGELOG.md](../../CHANGELOG.md). The `backups-dispatch-fail-open-robustness` finding (SA52/SA53, `why →` [tech-audit.md TA47](../others/tech-audit.md)) and the `social-admin-perorgadminmixin-prototype` finding (SA64, `why →` [arch-audit.md Red flags](../others/arch-audit.md)) are fully closed. Open this pass: SA69, below.

#### Finding — `ImproperlyConfigured` re-homed without a decision record (`why →` [arch-audit.md Red flags](../others/arch-audit.md))

- [ ] **SA69 — Record the `ImproperlyConfigured` exception-identity change in decisions.md.** `Tier 1 · Track 2 · deps: none`
  The side-channel commit `628c7d28` re-homed the contracts layer's `ImproperlyConfigured` from Django's class to a new first-party `quickscale_core.contracts.module_discovery.ImproperlyConfigured`, decoupling core's contract layer from Django. Tech-audit verified every in-repo raise/catch pair migrated together and no stale Django-class catcher wraps the new raise sites, so there's no live bug — but the change is undocumented, and arch-audit flags this as the **third consecutive delta** landing load-bearing semantics under a housekeeping-labeled commit message, which is itself worth a process note. Two same-named `ImproperlyConfigured` classes now coexist (contracts-layer vs. Django's module-runtime one); a future catcher importing the wrong one fails silently open.
  *Files:* `docs/technical/decisions.md` (one paragraph recording the exception-identity split, which class owns which layer, and a pointer for future catchers); `quickscale_core/src/quickscale_core/dr_engine/adapter.py` or wherever the billing/crm/social adapter docstrings still cite the Django class for the entry-point contract (doc-drift correction — grep for stale references and fix them alongside the decision record).
  *Acceptance:* decisions.md states which `ImproperlyConfigured` a contracts-layer catcher should import vs. which a Django-runtime catcher should import; the stale adapter docstring references are corrected; consider whether a lint/naming guard is warranted if a fourth housekeeping-labeled behavioral commit recurs (note it as a watch item if not addressed now, rather than scope-creeping this task into tooling work).
  *(why →* [arch-audit.md Red flags](../others/arch-audit.md)*)*

### Track 3 — Core/CLI plumbing

SA44 (Finding 1 stage 1, `dr-engine-module-circular-lattice`), SA56 (Finding 5, `json-api-boundary-idiom-fragmentation`, now fully closed), SA61 (test artifacts untracked, gitignore patterns added, blog test media pointed at tmp_path), and SA62 (module pyproject TOML splice routed through the validated writer) are complete — detail in [CHANGELOG.md](../../CHANGELOG.md). SA63 (below) is complete. Open this pass: SA65–SA68, below.

#### Finding — `db-privilege-mode-procedural`, first step (`why →` [arch-audit.md Finding 6](../others/arch-audit.md))

- [x] **SA63 — Fix the createcachetable/boot-guard collision and start the launcher-owned env contract.** `Tier 2 · Track 3 · deps: none`
  Four mechanisms currently decide "does this process run under the superuser `DATABASE_URL` or the restricted `RUNTIME_DATABASE_URL`" with three different semantics (start.sh env-unset, production settings' argv ladder, local settings' argv switch introduced by `198a1951`, and the orgs boot guard's positional argv check) — and one collision already exists at source level: `start.sh.j2:59`'s `createcachetable` step (run when `REDIS_URL` is unset) executes under the superuser role but sets no `QUICKSCALE_ALLOW_BYPASSRLS=1`, so the boot guard (which exempts only `migrate`) should raise `ImproperlyConfigured` on any no-Redis Railway deploy at first boot. Per arch-audit's recommended fix order, this task does the one-line collision fix and Finding 6's first structural step together in one template pass, rather than the collision fix alone: add the env pair to start.sh's `createcachetable` line, and delete `local.py.j2`'s argv-sniffing branch in favor of the same launcher-owned `RUNTIME_DATABASE_URL`/`QUICKSCALE_ALLOW_BYPASSRLS` env pair (documented as a one-liner wrapper for bare `python manage.py migrate` in local dev). The full Option 1 contract (production settings becoming a pure env reader, deleting `orgs/apps.py`'s `_is_migrate_command()` in favor of the existing hatch) is the remainder of Finding 6 and stays open in arch-audit.md pending confirmation the collision fix alone doesn't already resolve the live defect.
  *Files:* `quickscale_core/src/quickscale_core/generator/templates/start.sh.j2` (add `QUICKSCALE_ALLOW_BYPASSRLS=1` to the `createcachetable` line); `quickscale_core/src/quickscale_core/generator/templates/local.py.j2` (delete the argv-sniffing branch, use the env pair); generated-project e2e/boot test coverage for the no-Redis path.
  *Acceptance:* a generated project with `REDIS_URL` unset boots `createcachetable` successfully under the runtime role (or, if intentionally superuser, passes the boot guard because the env pair is now set) — verified by booting a generated app with `REDIS_URL` unset per arch-audit's suggested empirical check; `local.py.j2` no longer inspects `sys.argv`; local dev's `python manage.py migrate` UX is preserved via the documented wrapper.
  *Findings:* CR-SA63-001 (narrow `QUICKSCALE_ALLOW_BYPASSRLS=1` bridge added to `production.py.j2`), CR-SA63-002 (deterministic no-Redis production/orgs e2e confirmed), and CR-SA63-003 (fresh `quickscale plan`/`apply` regeneration evidence produced) were discovered during technical review and resolved in the implementation pass.
  *(why →* [arch-audit.md Finding 6](../others/arch-audit.md)*)*

#### Finding — SA63 beta-site rollout unverified (`why →` [arch-audit.md Red flags](../others/arch-audit.md))

- [ ] **SA67 — Verify SA63 reached `experto-ai-web` and `bap-web`; patch by hand if not.** `Tier 1 · Track 3 · deps: none — do this first, urgent`
  SA63 changed two generator templates (`start.sh.j2`, `production.py.j2`). Arch-audit's Finding 7 independently discovered that the maintainer's beta-site upgrade tooling (`quickscale_devtools/beta_migration.py`) **misses both of these files by construction**: `IN_PLACE_INFRASTRUCTURE_TARGETS` (`beta_migration.py:96–108`) does not include `start.sh`, so the in-place migration path never delivers the createcachetable env-pair fix; and `FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES` (`:43–48`) copies the **donor's** `settings/production.py` onto the fresh scaffold, so the fresh-first path keeps the beta site's old production settings and misses SA63's env-pair bridge (`production.py.j2:172–184`). Each of SA63's two changed files is missed by exactly one of the two migration paths — meaning at least one of the two production deployments is silently running without the fix it needs, most likely for its no-Redis boot path. This is flagged as a red flag "out of scope — fix now," independent of Finding 7's structural fix (SA66, below), and should not wait for it.
  *Files:* none in this repo except a note in `docs/planning/beta-site-migration.md` recording that this manual check was performed and its outcome; the actual patch happens in the `experto-ai-web` and `bap-web` repos (external to this monorepo).
  *Acceptance:* diff each beta site's deployed `start.sh` and `settings/production.py` against this repo's current templates; where either site is missing SA63's changes, patch by hand and redeploy; record the check (and whether Redis is present on either site, which determines how urgent the `start.sh` gap actually is — see arch-audit's open Question on this) in `beta-site-migration.md` or a CHANGELOG entry.
  *(why →* [arch-audit.md Red flags](../others/arch-audit.md)*)*

#### Finding — `apply-subprocess-env-pythonpath-pollution` (`why →` [tech-audit.md TA53](../others/tech-audit.md))

- [ ] **SA65 — Stop propagating the CLI's dev-context `PYTHONPATH` to foreign subprocesses.** `Tier 1 · Track 3 · deps: none`
  `apply_command.py`'s module-level `_QUICKSCALE_SUBPROCESS_ENV` (built once at import time by `_build_quickscale_env()`, `apply_command.py:212–254`) is passed unconditionally by `_run_command` (`:422`) and `_start_docker_impl` (`:627`) to **every** apply subprocess — not just the two nested `sys.executable -m quickscale_cli.main` invocations it exists for (`:569`, `manage migrate`; `:615`, `up`), but also `poetry install`, `poetry lock`, `poetry run python manage.py migrate` (a foreign interpreter in the generated project's own venv), `git`, and docker. The docstring claims this is inert in production ("packages installed in site-packages... these paths are not present in `sys.path`"), but tech-audit empirically verified that claim is **false**: a `pip install quickscale` layout puts `quickscale_core/` inside site-packages, which *is* on `sys.path`, so the function sweeps it into every child's `PYTHONPATH` regardless of install method. Because `PYTHONPATH` precedes a venv's own site-packages, this risks a pip-installed CLI's `manage.py migrate` resolving Django/psycopg/etc. from the CLI's venv instead of the generated project's own, wherever versions overlap-but-differ.
  *Files:* `quickscale_cli/src/quickscale_cli/commands/apply_command.py` (`_build_quickscale_env`, `_QUICKSCALE_SUBPROCESS_ENV`, `_run_command`, `_start_docker_impl`).
  *Acceptance:* the dev-context `PYTHONPATH` is built and passed only to the two nested `quickscale_cli.main` invocations (`:569`, `:615`), not to `poetry`/`git`/docker/generated-project subprocesses; the docstring's safety claim is corrected to match reality (or made moot by the narrower scoping); a regression test asserts a non-`quickscale_cli.main` child subprocess call does not receive the injected `PYTHONPATH`.
  *(why →* [tech-audit.md TA53](../others/tech-audit.md)*)*

#### Finding — `generated-file-ownership-unmodeled`, first step (`why →` [arch-audit.md Finding 7](../others/arch-audit.md))

- [ ] **SA66 — Add a conformance gate deriving the beta-migration file taxonomy from the template tree.** `Tier 2 · Track 3 · deps: none`
  The generator has no machine-readable statement of which emitted files are generator-owned (safe to overwrite on upgrade) vs. user-owned — that taxonomy exists only as eight hand-written tuple literals inside the maintainer-only beta-site migration tool (`quickscale_devtools/beta_migration.py:43–115`: `FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES`, `…_RECIPIENT_PACKAGE_FILES`, `…_IDENTITY_ROOT_FILES`, `…_PROTECTED_PACKAGE_FILES`, `IN_PLACE_INFRASTRUCTURE_TARGETS`, `IN_PLACE_SUBSTITUTED_INFRASTRUCTURE_TARGETS`, plus per-module React surface maps), differently partitioned per migration path, with nothing deriving them from the template tree (`quickscale_core/src/quickscale_core/generator/templates/` — 30+ emitted files) and no gate detecting drift. SA67 (above) is the immediate manual fix for this release's live gap; this task is the systematic prevention so the next template-surface change can't silently miss both migration paths again.
  *Files:* a new conformance test (e.g. `quickscale_cli/tests/test_beta_migration_ownership_conformance.py` or alongside the existing `test_beta_migration.py`) that enumerates every file the generator emits from `generator/templates/` and asserts each one is classified by *every* migration path's taxonomy — explicitly, including an "intentionally unmanaged" class — failing when a new or renamed template file has no classification; `docs/technical/decisions.md` (record the "`settings/production.py` is donor-owned by policy, not omission" convention that arch-audit's counter-evidence surfaced as the strongest read of the fresh-first list's intent — write it down so it's a decision, not folklore in a tuple literal).
  *Acceptance:* the new gate fails today against the current lists until `start.sh` (or an explicit "unmanaged" designation, if SA67's investigation shows Redis-optional beta sites don't need it in-place) is added to `IN_PLACE_INFRASTRUCTURE_TARGETS`; decisions.md states the donor-owned-`production.py` policy explicitly; the gate is wired into whatever test suite `quickscale_devtools` currently runs under (`quickscale_cli/tests/`, per its existing test placement) so future template changes surface a classification failure instead of a silent gap.
  *(why →* [arch-audit.md Finding 7](../others/arch-audit.md)*)*

#### Finding — `db-privilege-mode-procedural`, remainder (`why →` [arch-audit.md Finding 6](../others/arch-audit.md))

- [ ] **SA68 — Finish the launcher env-pair contract for the `migrate` path; delete the last argv deciders.** `Tier 2 · Track 3 · deps: soft — pair with SA59 for CI verification (see Dependency overview above)`
  SA63 landed the launcher-owned `RUNTIME_DATABASE_URL`/`QUICKSCALE_ALLOW_BYPASSRLS` env-pair contract for `createcachetable` and deleted `local.py.j2`'s argv ladder, and arch-audit's Probe B confirmed a *new* privileged command now costs exactly one station under that contract. The `migrate` path, however, still has three independent deciders left over from before the contract existed: `start.sh.j2:49` unsets `RUNTIME_DATABASE_URL` for migrate but does **not** set `QUICKSCALE_ALLOW_BYPASSRLS=1`; `production.py.j2:185` has a separate `elif "migrate" in sys.argv` branch (membership, any position) that selects the superuser URL without going through the env-pair bridge at `:172`; and `orgs/apps.py`'s `_is_migrate_command()` (`:32–51`, positional `sys.argv[1] == "migrate"`) is the boot guard's independent migrate exemption (`apps.py:155`). Three deciders, three slightly different idioms, for the same "is this a migrate invocation" question. Additionally, the same `QUICKSCALE_ALLOW_BYPASSRLS` bit is overloaded across per-command production sanction (SA63's bridge), per-environment dev opt-out, and blanket test-harness convenience (SA59's target) — arch-audit suggests considering a second, distinct flag for launcher sanction if that's still muddy after this task.
  *Files:* `quickscale_core/src/quickscale_core/generator/templates/start.sh.j2:49` (add the env pair to the migrate line, matching the createcachetable line's shape); `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/production.py.j2:185,195` (delete the `elif "migrate" in sys.argv` and `collectstatic`/`compilemessages` argv branches now that the bridge branch at `:172` covers the sanctioned case); `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py` (delete `_is_migrate_command()` and its boot-guard exemption at `:155`, since the env pair is now the sole migrate signal); `test_generated_project_runtime.py` (extend the existing no-Redis/bypass-hatch boot smoke coverage to the migrate path); `docs/technical/decisions.md` (the one-paragraph "deploy-time configuration contract for generated apps" arch-audit's watchlist has been asking for since the SA63 pass — natural to close out here, now that all launcher-privileged commands share one mechanism).
  *Acceptance:* `start.sh.j2`'s migrate line carries the same env pair as its createcachetable line; `production.py.j2` has exactly one code path selecting the superuser URL (the `:172` bridge) plus the fail-closed default — no argv inspection remains; `orgs/apps.py` no longer inspects `sys.argv`; the boot smoke test suite demonstrates the guard firing and passing correctly on the migrate path; decisions.md's deploy-time-configuration paragraph is written, retiring that arch-audit watchlist item.
  *(why →* [arch-audit.md Finding 6](../others/arch-audit.md)*)*

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
