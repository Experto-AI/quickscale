# Structural Autopsy: QuickScale

> This file is regenerated on each autopsy run to state **present reality for planning**: the
> current orientation, the open findings in full detail, and a curated watchlist. Closed findings
> exist only as dated lines in the **Reconciliation log** at the bottom (closeout detail lives in
> [CHANGELOG.md](../../CHANGELOG.md)); version control preserves prior full text. Finding IDs are stable
> across runs.

---

## Autopsy — 2026-07-17 (re-run, delta pass over the SA84–SA96 release-hardening batch)

### Orientation (2026-07-17)

QuickScale is a solo-maintained (Experto-AI/Victor Rocco) Python 3.13/3.14 + Poetry monorepo
(VERSION 0.87.0, integration branch `v87`) that is two archetypes at once: a **Django project
generator** (`quickscale_core` Jinja2 templates + plan/apply engine + DR engine; `quickscale_cli`
Click surface) and a **module workspace** of first-party Django modules (teams still README-only).
Generated apps: Django 6 + PostgreSQL 18, single-service Railway; generator output is now
**React-only** (SA94 retired `showcase_html`). Tenancy enforced twice (fail-closed `TenantManager`
+ FORCE RLS with the AF9 execute-wrapper), backstopped by the SA58 boot guard. Severity floor
unchanged: CLI is single-process local; generated apps are single-service WSGI; **tenant isolation
is the highest-blast property.** Growth direction (roadmap 2026-07-17): the repo is in **release
end-game** — every per-module restricted-role gate is green with an empty quarantine; SA93 (e2e in
the green-gate) is the sole open ticket before the SA96-GATE publishability join and the staged
PyPI publish. No post-release domain is named anywhere in the planning surface.

**Commit-delta classification (§2f).** Base `803daef7` (2026-07-13 pass HEAD) → `09f9cbcc`,
~127 commits. *Closeouts* (all mapped to tickets and audited below): SA85 (`1e178d31`), the SA88
seam saga (`e30409f9`…`889a14fa`, later **deleted** by the SA92 squash rather than completed),
SA89a/SA89b persistence port (`2816e72a`, `6283eee9`, `f4e81cee`, `a561e8fd`), SA90 emission
mapping (`e2349b91`), SA86 (`aaa87f20`), SA92 squash + guardrail (`6bea908d`, `6d50e7a7`,
`6961d651`), SA94 react-only (`f232d1d0`, `b97c83a6`, `ad466671`, `9020ad97`, `b5fe0150`,
`3f1a83c7` + test rebaselines), SA91 parallel pool (`8d538cb7`), SA84 (`4ba4ad32`, `cab54afd`),
SA95 (`e00503f6`, docs — non-reproducible), SA96-T1/T2 sweeps (`c7ce0f9f`, `55776f5c`), SA93
checkpoint (`ddfa6daa`, `022a88fb`), GATE-quality (`76c5cc55`). *Housekeeping*: ~50 roadmap/
CHANGELOG commits plus merges — including two deceptively named ones read at full depth and
verified roadmap-docs-only (`0e49e647` "Remove HTML frontend demo", `fb0d1b71` "Roadmap
improved"). *Unlabeled-behavioral*: `76c5cc55` ("chore(quality): establish v87 regression
baseline") rewrote `scripts/quality_baseline.json` (+757 net lines; allowed complex functions
72→151, large files 17→41) — read at depth and **verified to be scope expansion, not regression
grandfathering** (the old baseline had zero entries for `quickscale_core`/billing/orgs/crm, which
the gate's discovery now covers; backups shrank 17→7; 28 entries removed), but the reset landed
under a chore label with no decision record (watchlist). Read fully: the SA89 port surfaces
(`persistence.py`, orchestration boundary sites, both directions of the import linter),
`theme_validation.py`, the SA92 guardrail test, crm/forms/blog conftest plumbing, the
beta-migration taxonomy block, the quality-baseline diff. Sampled: SA94's CLI diffs (stats +
callsite census), SA91's `_qs_jobs.sh` harness, `check_coverage_policy.py`. Skipped: bulk test
rewrites inside SA84/SA96 beyond mechanism identification.

**Result: two prior findings closed and verified in code (Findings 1 and 8 — both fix-regression
audits pass), two still-open deferred findings unchanged (2 and 4, anchors re-verified at prior
line numbers), Finding 7 still-open and strengthened (SA94 paid its predicted hand-sync tax), and
one new finding.** The new finding (**Finding 9 `module-commons-unowned`**) is the promotion of
the commons watchlist item, whose trigger fired twice this delta: SA84 and SA85 landed
near-identical hand-rolled test-state-reset fixtures in crm and forms (a third, divergent
ContextVar-only variant already sits in blog), while the sanctioned shared home
(`tests_shared/isolation.py`) has exactly one consumer and the SA26 sanitizer copy-pair enters its
sixth pass unconsolidated. Fix-regression audits: **SA89a/b clean** (all three cycle carriers
removed — the core→backups import, the DR `_LAZY_*` tables, the `mypy.ini` backups ignore; the
reverse import ban is live; the one surviving core→module edge is the pre-existing, deliberate,
fail-hard-bounded dynamic `import_module("quickscale_modules_storage.helpers")` at
`orchestration.py:248`, invisible to the static ban — watchlist). **SA92 clean** (squashed `0001`s
route RLS install through orgs-owned `apply_force_rls`/`revert_force_rls` — a real shared seam;
the guardrail is a documented bounded tripwire backed by the pg_policies/catalog/data parity
baseline, decision-recorded). **SA84/SA85 mixed** (drained through the sanctioned `org_scope`
primitives — correct — but the glue plumbing was copied per-module: Finding 9's evidence).
**SA94 audited** (a real shared `theme_validation` seam in core, consumed by 7 CLI callsites, plus
one inline re-implementation with duplicated message strings in `apply_command.py:3831–3854` and a
hand-enumerated per-command parity test — transitional surface, watchlist).

### Enforcement census (§3.4)

| # | Invariant | Enforced by | Class | Trend this pass |
|---|-----------|-------------|-------|-----------------|
| 1 | Tenant isolation on reads/writes | fail-closed `TenantManager` + FORCE RLS + AF9 execute-wrapper | structural | stable; RLS policies re-attached per-module in squashed `0001`s via orgs-owned `apply_force_rls`, pg_policies parity vs v87 verified (21 tables / 42 policies, decisions.md §SA92) |
| 2 | No bypassing DB role at boot | orgs boot guard (`apps.py`), `rolbypassrls` + `rolsuper` | structural | stable — **all per-module restricted-role gates green with empty quarantine** (SA84/SA86/SA95 drained); only the e2e lane (SA93) is unproven |
| 3 | Admin org-scoping | `TenantModelAdmin`; NOBYPASSRLS test posture | structural + gated | stable |
| 4 | DB privilege selection per process | SA68 launcher env contract | structural | stable; sanctioned-set copy-pair unchanged (`production.py.j2:185` / `orgs/apps.py:36`, both fail-closed, no sync gate — watchlist) |
| 5 | JSON endpoint idiom | `OrgApiBaseView`/DRF baseline + SA46 csrf-exempt CI gate | structural + gated | stable |
| 6 | Core↔module import direction | import linter, **now bidirectional** (SA89b reverse ban: zero `quickscale_modules` imports in core) + `LEGACY_ALLOWED_IMPORTS` (3 modules) | gated, with exceptions | strengthened (reverse ban live; backups `mypy.ini` ignore gone). Docstring drift persists (`:9–11` "billing and CRM"; dict has 3 keys). Blind spot: the ban is a static AST scan — one deliberate dynamic edge survives (`orchestration.py:248` storage helpers, ModuleNotFoundError-narrow, fail-hard otherwise) |
| 7 | Module manifest copy-pairs (module.yml ×2) | CI byte-identical sync gate | gated | stable |
| 8 | Tenant-model universe **membership** | SA15.3/SA45/SA49 derivation gates | gated | stable |
| 9 | Tenant-model purge **order** | hand-ordered `_DELETE_SPECS` (`management/commands/purge_organization.py:64`) | convention | unchanged (Finding 4); untouched this delta |
| 10 | Deletion invariants at account boundary | one canonical check + SA70 `pre_delete` backstop | convention + backstop | stable (Finding 2) — `apps.py:194–206`, `models.py:165/298/329` re-verified at prior lines |
| 11 | pyproject TOML write safety | `_write_validated_toml` (3 CLI splice sites) | structural per package | stable |
| 12 | Generator-emitted file ownership | SA66 conformance gate + SA90 manifest-parity fixture; production consumes `get_generator_emission_mapping()` (`generator.py:151`) | gated | stable for the production chain; SA94 rebaselined the fixtures to react-only. Outside the derivation chain: `beta_migration.py` taxonomy tuples, hand-edited again by SA94 (Finding 7) |
| 13 | Generated-project boot correctness | `test_generated_project_runtime.py` boot smoke harness | gated | stable |
| 14 | Module suites run under a restricted DB role | `QS_*_DB_USER` hand-lists ×3 (ci.yml:403–414, publish.yml ×12, test_integration.sh:395–406) | gated | stable content (all 12 modules in all three) — but the comment-sync **has already line-drifted** (`test_integration.sh:393` cites "ci.yml lines 399-410"; the block is now 403–414). Omission still fails loud (postgres fallback → boot guard). Watchlist |
| 15 | Release-gate test scope | publish.yml `test` job + e2e lane (`e2e.yml`, SA93) | gated | e2e folded into the definition of done; exact `make ci-e2e` root-gate run still unproven (SA93 open — tracked work, not a red flag) |
| 16 | No cross-org `organization_id` DML in module migrations | SA92 bounded regex tripwire (`test_sa92_migration_squash_guardrail.py`) + pg_policies/catalog/data parity vs v87 | gated | **NEW row** (replaces the retired Finding 8 row) — deliberately shallow by recorded decision; the tripwire's module list is a hand tuple (10 modules) |
| 17 | Theme validity (react-only) | core `theme_validation.py` seam (fail-closed, `SOLE_VALID_THEME`) + per-command preflight | structural seam, **convention callers** | **NEW row** (SA94) — 7 CLI callsites each remember the preflight; parity pinned by hand-enumerated per-command tests; one inline message-copy in `apply_command.py:3838` |
| 18 | Code-quality regression (complexity/size/dead-code) | `make quality` vs `quality_baseline.json` grandfather lists | gated | **NEW row** — 151 allowed functions / 41 allowed files; no shrink-only contract; baseline reset wholesale under a chore label (watchlist) |
| 19 | Shared-code commons (runtime + test plumbing) | none — ad-hoc per-module copies | **convention** | **NEW row (Finding 9)** — sanctioned homes exist (orgs; `tests_shared/`) but nothing routes shared concerns there |

### Summary table

| # | ID | Horizon | Confidence | Size | One-line problem |
|---|----|---------|-----------|------|------------------|
| 9 | `module-commons-unowned` | now | High (evidence) / Medium (urgency) | M | Shared cross-module concerns land as divergent per-module copies (sanitizer ×2, test-state reset ×3 in 2 shapes) while the sanctioned commons (`tests_shared/`, orgs) sit unused and unwritten-down; no gate keeps any copy-pair honest |
| 7 | `generated-file-ownership-unmodeled` | 6–18 months | High | M | Production emission routing is closed (SA66/SA90), but the beta-migration tool re-encodes file ownership in hand-synced tuples (tax paid again by SA94) and devtools sits outside the lint/typecheck universe while import-load-bearing for the release gate |
| 2 | `deletion-invariants-per-boundary-reimplementation` | deferred (teams) | High | S | Last-owner check is canonical with a `pre_delete` backstop; no domain-owned deletion service covers other boundaries' invariants (e.g. billing) |
| 4 | `org-model-universe-hand-enumerated` | deferred (teams) | High | M | Tenant-model membership is derivation-gated; purge *order* is hand-written and ungated on a uniformly `NOT DEFERRABLE` foundation |

---

### Finding 9: Shared module code has no owned commons — concerns land as divergent per-module copies while the sanctioned homes sit unused

- **ID:** `module-commons-unowned`
- **Rank rationale (blast radius × likelihood):** blast is moderate (silent drift between copies of
  an XSS-sensitive sanitizer; divergent tenant-test-state plumbing that decides whether isolation
  tests are trustworthy) but likelihood is the highest of any open finding — the pattern fired
  twice inside this one delta (SA84, SA85) and has recurred in every hardening batch since SA26.
- **Horizon & trigger:** `now` — already reproducing; each new module suite, each new shared
  runtime concern, and each one-sided fix to an existing copy is a trigger.
- **Confidence:** High on the evidence (all copies read and compared this pass); Medium on urgency
  (all current copies are behaviorally consistent today; the cost is drift-risk plus repeated
  re-derivation, not a live defect).
- **Context dependence:** wrong-for-now on the module-count dimension — at 12+ module suites and a
  recurring hardening cadence, per-copy discipline is already the observed failure mode (the
  SA83–SA86 saga was four separate diagnoses of per-module state-leak plumbing).
- **Problem:** there is no written rule for where shared cross-module code lives, and the two
  sanctioned homes that exist are bypassed in practice — so every shared concern is re-resolved ad
  hoc as hand-rolled per-module copies with no gate keeping them consistent.
- **Evidence (all established this pass):**
  - Runtime copy-pair (sixth pass): `_sanitize_href`/`_sanitize_rendered_html` byte-similar in
    `blog/views.py:69–115` and `listings/views.py:42–88` (SA26). No parity test or gate references
    them (searched blog/listings tests, scripts/, workflows — zero matches).
  - Test-plumbing copies (new, SA84/SA85): crm `tests/conftest.py:43–83` and forms
    `tests/conftest.py:63–90` carry near-identical hand-rolled autouse `_reset_test_state`
    fixtures (ContextVar + `RESET app.current_org_id`/`app.operator_access` + `RESET ROLE` +
    cache), with matching docstrings. blog `tests/conftest.py:187–198` carries a third, divergent
    ContextVar-only variant (`_reset_current_org_context`, SA83). Three modules, two shapes, zero
    shared implementation.
  - The sanctioned test commons exists and is bypassed: `tests_shared/isolation.py` ("so that
    every tenant module can express the same contract consistently") has exactly **one** consumer
    (`crm/tests/test_isolation.py`); neither SA84 nor SA85 routed their plumbing through it.
  - The commons rule is unwritten: `grep "commons\|tests_shared"` over `decisions.md` returns
    nothing; the 2026-07-09 pass established "orgs is the de facto module commons" but it was
    never recorded, and the concern has since reproduced outside orgs.
- **Counter-evidence:** searched for a parity gate over any copy-pair (none exists — unlike the
  gated module.yml and SA68 pairs, these copies have no tripwire); searched decisions.md for a
  deliberate "test plumbing stays module-local" record (none); strongest disconfirming facts: (a)
  the *primitives* are properly shared — SA84/SA85 consume orgs' sanctioned
  `org_scope`/`set_current_org_id`/`reset_current_org_id` API, so what is copied is glue, not
  policy; (b) `tests_shared/isolation.py`'s own docstring says fixture creation "remains
  module-specific," which partially sanctions per-module plumbing. Neither dissolves the finding:
  the glue is where the SA83–SA86 failures actually lived, and the docstring sanctions
  module-specific *fixtures*, not three divergent implementations of the same reset contract.
- **Why it compounds:** every new module suite re-decides the reset-plumbing shape (three shapes in
  three modules already); every fix to one copy must be remembered N−1 more times with no signal on
  a miss — for the sanitizer that is an XSS-class drift on public pages, for the reset fixtures it
  is false-green isolation tests, the exact class the restricted-role gate exists to prevent; and
  every future shared concern (the next sanitizer, the next fixture idiom, the next helper) repeats
  the whole cycle because no rule says where it goes. Already built on top: six passes of carried
  sanitizer copies, the SA83/SA84/SA85 per-module diagnoses, and blog's divergent variant.
- **Detection signal:** none today — the copies fail silently by drifting. Instrument cheaply: a
  byte-parity check over the sanitizer pair would make drift loud; a grep-count of
  `RESET app.operator_access` outside a shared fixture would catch the next plumbing copy.
- **Steelman:** a solo maintainer copying 40 lines twice is cheaper than designing a shared seam;
  per-module conftests keep suites independently runnable; and the copies are currently consistent.
  This holds while copies stay small, few, and behaviorally identical — but the census already
  shows divergence (blog's variant lacks the GUC/role resets that SA84/SA85 needed), so the
  holding condition is broken.
- **Correct shape:** one written rule (decisions.md) naming where shared runtime code and shared
  test plumbing live; each existing shared concern has exactly one implementation at its sanctioned
  home; any remaining deliberate copy-pair is gate-pinned like the module.yml pairs.
- **Options:**
  1. **Write the rule + consolidate the two live concerns (recommended).** Record the commons rule
     in decisions.md (orgs for org-context runtime helpers; `tests_shared/` for cross-module test
     plumbing). Promote the crm/forms `_reset_test_state` fixture into `tests_shared/` (a
     conftest-importable fixture module) and point crm/forms/blog at it; move the sanitizer to one
     shared home consumed by blog+listings. M, removes both live copy classes and the re-decision
     cost.
  2. **Gate the copies without consolidating.** Add byte-parity CI checks over the sanitizer pair
     and the two conftest fixtures. S, but relocates the problem into more gated copy-pairs (the
     Finding 1 lattice pattern in miniature) and does nothing for the next concern.
  3. **Full shared test-infra package** (a pytest plugin distributed like a module). L —
     over-engineered at current scale; only worth it if module suites ever run outside the
     monorepo.
- **Recommendation:** Option 1, sized to fit the current idle Track 1/2 capacity noted in the
  roadmap — it is independent of SA93/SA96 and touches no release-gated surface. · **Size:** M ·
  **First step:** write the decisions.md commons rule (it is the cheapest artifact and makes every
  future landing decidable), then lift the crm/forms reset fixture into `tests_shared/`.

---

### Finding 7: Generated projects have no file-level ownership contract — the upgrade path re-encodes it by hand

- **ID:** `generated-file-ownership-unmodeled`
- **Rank rationale (blast radius × likelihood):** blast is the deploy/infra correctness of the two
  production consumer sites plus every future generated project's upgrade story; likelihood is
  moderated by SA66/SA90 (the production chain is derivation-gated) but the residual hand-synced
  copies just charged their tax again during SA94.
- **Horizon & trigger:** `6–18 months` — fires on a third consumer site, a public "update my
  generated project" command, or the next change to the emitted-file universe (SA94 was exactly
  such a change and had to hand-edit the tuples).
- **Confidence:** High — all anchors re-resolved this pass; the SA94 delta to `beta_migration.py`
  read directly.
- **Context dependence:** wrong-for-now on the **consumer-count** dimension; wrong-regardless at a
  third site / second operator / public update command.
- **Problem:** the generator's production emission routing is now a single exported function with
  an independent parity fixture (closed by SA66/SA90), but the *maintainer upgrade tool* still
  re-encodes per-file ownership as hand-written tuples outside that derivation chain, and the
  package holding it sits outside the repo's lint/typecheck governance while being
  import-load-bearing for the release gate.
- **Evidence (anchors re-resolved this pass; note the corrected src-layout path):**
  - Production chain (closed, protect): `get_generator_emission_mapping()`
    (`quickscale_core/src/quickscale_core/generator/generator.py:151`) consumed by
    `ProjectGenerator.generate()` (`:564`) and the SA66 conformance gate; the SA90
    `sa90_emission_manifests.json` fixture pins path/SHA-256/mode — **rebaselined to react-only
    variants by SA94** (`c4daee68`), which is the derivation chain working.
  - Residual hand-synced taxonomy: `quickscale_devtools/src/quickscale_devtools/beta_migration.py`
    — `IN_PLACE_INFRASTRUCTURE_TARGETS` (`:101`), `IN_PLACE_SUBSTITUTED_INFRASTRUCTURE_TARGETS`
    (`:115`), `INTENTIONALLY_UNMANAGED` (`:123+`), `IN_PLACE_MODULE_REACT_SURFACES` (`:257`); the
    file imports `config_schema`/`theme_validation` but **not**
    `get_generator_emission_mapping` — the tuples are typed only informally and updated by hand.
  - The compounding tax, paid this delta as predicted: SA94's theme retirement had to hand-edit the
    taxonomy (`9020ad97`, +53 lines in `beta_migration.py` plus a decisions.md taxonomy correction
    in `31863733`) — the O(themes × artifacts) cost this finding named.
  - Devtools governance unchanged: `quickscale_devtools` is absent from `ruff.toml`, `mypy.ini`,
    and Makefile lint/typecheck targets (re-verified by grep this pass) while the conformance test
    importing it runs in the unit gate of ci.yml and publish.yml. Partial mitigation noted: the
    GATE-quality baseline now covers devtools (8 grandfathered entries), so it is inside the
    vulture/radon/pylint net even though ruff/mypy still skip it.
  - decisions.md rule 3 rationale enforcement still asserts non-emptiness only.
- **Counter-evidence:** searched for a beta_migration↔emission-mapping cross-check (none); for a
  devtools entry in any lint/typecheck config (none); strongest disconfirming facts: the production
  chain now has three independent sources of truth (mapping, conformance gate, checked-in
  manifest), and SA94's hand-edits to the tuples were caught correct by the ownership-conformance
  test added in `9020ad97` (`test_beta_migration_ownership_conformance.py`) — the miss class is
  gated even on the devtools side, at the cost of one more mapping-shaped test rather than
  derivation.
- **Why it compounds:** every change to the emitted-file universe (SA63, SA66, now SA94) pays a
  hand-edit in the devtools taxonomy plus its conformance re-baseline; cost grows with dynamic
  artifacts × consumer sites; and a drift between the shared mapping and the devtools copy would
  pass ruff/mypy (which don't look) and fail only if the conformance fixture happens to cover it.
- **Detection signal:** a conformance-gate failure naming an unclassified path (loud, good); the
  silent direction remains devtools-copy drift — instrument with a cross-check between the taxonomy
  tuples and `get_generator_emission_mapping()`.
- **Steelman:** hand-curated tuples encode migration judgment (in-place vs substituted vs
  unmanaged) that naive derivation would get wrong; the maintainer is the only operator of the
  tool; SA94 proved the conformance tests catch taxonomy errors. Holds until a third consumer or a
  public update command.
- **Correct shape:** one machine-readable per-file ownership statement owned by the generator;
  upgrade tooling and all gates consume it; no second encoding of the template→emitted-path→
  ownership mapping exists anywhere; every package whose import can fail the release gate is inside
  the lint/typecheck universe.
- **Options:**
  1. ~~Derivation gate over the existing lists~~ — **done** (SA66).
  2. **Generator-emitted ownership manifest (live, partially done).** The export + parity fixture
     halves are done (SA90). Remaining: derive `beta_migration.py`'s tuples from
     `get_generator_emission_mapping()` (keeping only the ownership-judgment overlay hand-written),
     and bring devtools into ruff/mypy. M.
  3. **Fold the upgrade path into the product** (`quickscale apply` contract-vintage refresh). L;
     only when generated-project upgrades become a public feature.
- **Recommendation:** Option 2's remainder, unscheduled — correctly gated on a third consumer or
  public update command; the cheap sub-item (add devtools to ruff/mypy) is S and could ride any
  idle-track slot. · **Size:** M remaining · **First step:** add `quickscale_devtools` to
  `ruff.toml`/`mypy.ini` (removes the ungoverned-but-load-bearing edge for one config line each).

---

### Finding 2: Deletion-boundary invariants are re-implemented per boundary with no domain backstop

- **ID:** `deletion-invariants-per-boundary-reimplementation`
- **Rank rationale (blast radius × likelihood):** blast is money and org integrity (orphaned live
  Stripe subscriptions, ownerless shared orgs); likelihood moderate and static while user deletion
  stays single-path and teams stays unscheduled.
- **Horizon & trigger:** `deferred` — teams unscheduled. Live trigger regardless of teams: the
  first account-deletion path that isn't `AccountDeleteView` (e.g. a GDPR erasure command).
- **Confidence:** High — re-verified this pass at unchanged anchors: `is_last_owner_with_members`
  (`orgs/models.py:165`) consumed by the lock-guarded `delete()` (`models.py:298/329`); SA70
  receiver wired in `orgs/apps.py:194–206`; none of these files touched this delta (git log
  empty over the range).
- **Context dependence:** wrong-for-now → wrong-regardless if/when teams kicks off.
- **Problem / Evidence / Options:** unchanged from the 2026-07-13 pass (full text in version
  control) — org-domain and billing-domain "what must hold when a user disappears" rules are
  enforced only at boundaries that choose to invoke them; billing's
  active-subscription-on-ownerless-org invariant still has no backstop.
- **Detection signal:** none today — instrument by alerting on `Organization` rows with zero OWNER
  memberships and active `Subscription` rows whose org has no members.
- **Recommendation:** land a billing-side backstop if/when teams or an erasure command creates a
  second deletion path. · **Size:** S remaining · **First step:** none scheduled; deferred with
  teams.

---

### Finding 4: orgs hand-enumerates the cross-module model universe in unlinked literals

- **ID:** `org-model-universe-hand-enumerated`
- **Rank rationale (blast radius × likelihood):** the enumerations back the isolation boundary's
  bookkeeping and org-offboarding; likelihood approaches 1 if/when teams lands, near-zero
  otherwise except for new models in shipped modules.
- **Horizon & trigger:** `deferred` — teams unscheduled; fires independently on any new model added
  to an already-shipped module.
- **Confidence:** High — anchors re-resolved this pass: `TENANT_TABLE_REGISTRY`
  (`orgs/tenancy.py:128`, bidirectionally gated) and `_DELETE_SPECS`
  (`orgs/management/commands/purge_organization.py:64` — full path recorded for freshness;
  hand-ordered, membership-gated, order-ungated). `purge_organization.py` untouched this delta;
  `tenancy.py` was touched only by the SA88 seam (since retired) and SA92 (which *consumes* its
  `apply_force_rls` — a correct use of the registry infrastructure, not a new hand station).
- **Context dependence:** wrong-for-now on the new-domain dimension.
- **Problem / Options:** unchanged — purge-*order* correctness is the one property no gate checks,
  on a uniformly `NOT DEFERRABLE` FK foundation that is less forgiving of ordering mistakes.
  Option 2 (derive the purge plan topologically from the FK graph) remains the live option when
  teams gives it a test bed.
- **Recommendation:** unchanged; deferred with teams. · **Size:** M remaining.

---

### Change-cost probes (§3.6)

- **Probe A — "a 14th module lands in `quickscale_modules/`"** (re-measured; two stations changed).
  Stations: (1) module dir + pyproject + module.yml copy-pair — gated; (2) manifest adapter
  registration — one line; (3–5) ci.yml createdb/role-grant/`QS_*_DB_USER` lists; (6–8) publish.yml
  same three; (9) `test_integration.sh:395–406` `QS_*_DB_USER` block; (10) the module's own
  `tests/settings.py`; (11) **new since last pass:** the SA92 guardrail's hand-listed module tuple
  (`test_sa92_migration_squash_guardrail.py::test_discovery`, 10 entries) — a module missing from
  it is silently outside the cross-org-DML tripwire (fail-*silent*, unlike the DB_USER stations);
  (12) the module's `0001_initial` must call orgs' `apply_force_rls` — per-module convention, but
  now a one-call shared seam rather than Finding 8's hand-rolled context, and the pg-parity gate
  plus restricted-role suite fail loud on a miss. **Removed:** the per-migration
  `operator_access` station (Finding 8, closed by SA92). Derived automatically: the integration
  *suites* (worker pool discovers `quickscale_modules/*`), Makefile typecheck loop, SA49
  conformance-env. **Verdict: roughly eight ungated hand stations; the new fail-silent one (SA92
  discovery tuple) joins the watchlist; DB_USER triplication carried (fail-loud).**
- **Probe B — "add a third sanctioned privileged command"** (carried). Copy-pair unchanged and
  re-verified (`production.py.j2:185` / `orgs/apps.py:36`, both `{"migrate","createcachetable"}`,
  both fail-closed). **Verdict: exonerated for fail direction; copy-pair carried on watchlist.**
- **Probe C — "retire/replace a theme" (measured retrospectively from SA94, the probe reality
  ran).** Measured stations actually touched: generator templates + emission mapping rebaseline,
  `config_schema.py`, the new `theme_validation.py` seam, **seven** CLI command files (plan, apply,
  module, remove, dr, development, wiring-manager), `beta_migration.py` taxonomy + its conformance
  test, decisions.md, e2e/test rebaselines — spread over ~10 commits including two blocked
  checkpoints (`5120b42b`, `1e058108`). **Verdict: confirms Finding 7's O(themes) claim and
  motivates the theme-preflight watchlist item; moot going forward only if the theme count stays
  at one.**

### Fix order and interactions

1. **Finding 9 Option 1** (commons rule + consolidate sanitizer and reset-fixture) — highest value
   now; fits the idle Track 1/2 capacity; independent of SA93/SA96 and touches no release-gated
   surface. Do the decisions.md rule first.
2. **Finding 7's cheap sub-item** (devtools into ruff/mypy) — S, independent, any idle slot. The
   tuple-derivation remainder stays unscheduled pending its trigger.
3. **Findings 2 and 4** — deferred with teams; independent.

All four findings are independent — no fix forces rework of another. None conflicts with the SA93 →
SA96-GATE → SA96-PUBLISH critical path.

### Sound load-bearing decisions (protect these during remediation)

- **The unit/integration gate split + restricted-role integration posture (SA59/SA82):** now fully
  drained — every module suite green under `quickscale_test_role` with an empty quarantine. This
  posture found and then verified the closure of Finding 8; do not weaken it to speed the release.
- **Dual-layer tenancy enforcement** (fail-closed `TenantManager` + FORCE RLS + AF9 wrapper + SA58
  boot guard) — carried, re-verified via census row 1.
- **orgs-owned `apply_force_rls`/`revert_force_rls` as the single RLS-install seam** (new this
  pass): every squashed `0001` consumes it (`crm/0001_initial.py:31–35` et al.) — the module
  commons working as Finding 9 wants it to; Finding 9's fix should cite this as the house pattern.
- **The SA89 persistence-port shape** (Django-free protocols + fail-hard registry,
  `dr_engine/persistence.py:148–260`): the correct way to give core access to module state.
  Protect the fail-hard unregistered-access behavior and the idempotent re-registration rule.
- **SA92's two-layer guardrail pattern** (authoritative parity baseline + deliberately bounded
  tripwire, with the boundedness *written down* in the test docstring and decisions.md): honest
  gate design — the gate says what it does not prove.
- **SA68's launcher env contract** and **`TenantModelAdmin`/canonical last-owner check** — carried.
- **The generated-project boot smoke harness** (`test_generated_project_runtime.py`) — carried;
  still the runtime-confirmation layer for template-contract claims.

### Watchlist (every carried item shows this pass's trigger evaluation — §8)

- **Module universe hand-enumerated in CI/script files.** Trigger ("comment-sync drifts and a real
  module runs unguarded / a 14th module's multi-station edit is missed"): **partially fired** — the
  line-number comment-sync has already drifted (`test_integration.sh:393` cites ci.yml 399-410;
  actual 403–414) but content matches across all three lists (12/12 modules) and omission fails
  loud. Held; the drift confirms line-number comment-sync is the wrong mechanism. Carry.
- **SA92 guardrail discovery tuple is fail-silent for new modules (new).** A 14th module absent
  from `test_sa92_migration_squash_guardrail.py::test_discovery` is silently outside the
  cross-org-DML tripwire. Doesn't qualify: one hand tuple, test-side, S fix (derive from
  `quickscale_modules/*/module.yml` like the worker pool does). Promotes if a module lands without
  tripwire coverage.
- **Retired-theme preflight is per-command convention (new, SA94).** Seven CLI callsites each
  remember the preflight; parity pinned by hand-enumerated per-command tests; one inline
  re-implementation with duplicated message strings (`apply_command.py:3831–3854`). Doesn't
  qualify: transitional surface that shrinks as old configs migrate; fail direction is closed.
  Promotes if an eighth entry point ships without the preflight or the inline copy drifts.
- **Quality-baseline governance (new, `76c5cc55`).** The grandfather lists were reset wholesale
  under a chore label with no decision record and carry no shrink-only contract. Verified scope
  expansion this time. Promotes if a future reset grows entries for already-covered packages
  (regression grandfathering) or a second wholesale reset lands unrecorded.
- **Reverse import ban is blind to dynamic imports (new, SA89b).** Exactly one deliberate surviving
  edge (`orchestration.py:248` → storage helpers, ModuleNotFoundError-narrow, fail-hard otherwise).
  Promotes if a second dynamic core→module edge appears.
- **Subprocess-env construction has no single CLI policy.** Trigger ("third bespoke builder / a
  builder needed outside `apply_command.py`"): **not fired** — still exactly two
  (`_build_quickscale_env:217`, `_isolated_poetry_env:545`). Carry.
- **Sanctioned privileged-command copy-pair (SA68-minted).** Trigger ("third sanctioned command /
  vintage-skew incident"): **not fired** — both frozensets unchanged and equal. Carry.
- **Billing webhook concurrent-duplicate window.** Trigger ("non-idempotent side effect in a
  handler"): **not fired** — `billing/services.py` untouched this delta. Carry.
- **Dual child-table tenancy APIs.** Trigger ("a teams child table lands on the trigger API"):
  **not fired** — teams unscheduled. Carry.
- **Mutating CLI operations have divergent compensation mechanisms.** Trigger ("a new mutating
  command hand-rolls a fifth mechanism"): **not fired** — the delta's CLI changes were preflight
  and env plumbing only. Carry.
- **`orgs/views.py` fusion.** Trigger ("teams begins extending org-facing surfaces"): **not
  fired** — 1,226 lines, verified unchanged. Carry.
- **Grandfathered option defaults multi-sourced — ninth pass.** Trigger ("a default changes in one
  station only"): **not fired** — `module_config.py` untouched. Carry.
- *Retired this pass:* **shared module-runtime commons rule** — promoted to **Finding 9** (trigger
  fired: SA84/SA85 landed copies outside any sanctioned home). **`quickscale_devtools` governance**
  — remains absorbed into Finding 7's evidence (partially mitigated: GATE-quality now covers
  devtools; ruff/mypy still don't).

*(Carried unchanged at low priority, unprinted: hardcoded `EXEMPT_PATH_PREFIXES` in
`orgs/middleware.py:45` — re-verified unchanged.)*

### Teams landing checklist (carried — speculative, teams unscheduled)

> Teams is not scheduled (decisions.md §Teams module status). Updated for the post-SA92 world: the
> teams adapter imports `quickscale_core.runtime.manifest` only; teams' `0001_initial` starts at
> final schema (`organization_id NOT NULL` from row zero) and calls orgs' `apply_force_rls` — the
> Finding 8 helper no longer exists and must not be reinvented; teams data migrations traverse the
> SA68 launcher env contract; teams' admin subclasses `TenantModelAdmin`; teams' test suite must
> consume the (Finding 9) shared reset plumbing rather than minting a fourth conftest variant;
> teams' arrival re-fires Probe A's ~eight hand stations, including the SA92 discovery tuple
> (fail-silent) and the three `QS_*_DB_USER` lists.

### Questions that would change the ranking

- **What is the first post-release domain after SA96-PUBLISH?** The roadmap is fully drained
  except SA93/publish, and Tracks 1–2 are idle. If teams (or any new module) is next, Findings 2
  and 4 move from `deferred` to `6–18 months` and Finding 9's consolidation becomes a
  prerequisite; if the next work is consumer sites, Finding 7's third-consumer trigger approaches.
  (Affects Findings 2, 4, 7, 9.)
- **Is the quality baseline intended to be shrink-only from the v87 reset?** If yes, one sentence
  in decisions.md plus a trend check turns census row 18 from "gated, uncontracted" into a real
  ratchet; if no, the 151-function grandfather list is permanent and will quietly grow. (Affects
  the quality-baseline watchlist item.)

### Red flags (out of scope — fix now)

> None open this pass.

Lenses scanned with no qualifying finding this pass: data/state integrity (SA92 squash verified
invariant-preserving), trust boundaries (SA68/boot-guard re-verified; theme preflight is
watchlist), consistency/failure models, observability, API contracts, concurrency (SA91 pool is
bounded, derived, and tested), security architecture (sanitizer copies belong to Finding 9),
performance, governance/gates (§5.XV produced census rows 16–18 and two watchlist items, no
standalone finding), code-generator archetype (Finding 7 owns it; SA94/Probe C measured).

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
