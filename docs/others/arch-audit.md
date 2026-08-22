# Structural Autopsy: QuickScale

> **Audit snapshot:** 2026-07-26 · **Current reconciliation:** 2026-08-22 · **Branch:** `v88`

## Orientation summary

QuickScale is a Python 3.14 / Poetry **code-generator and scaffolding platform**: a Click CLI plus a Django-6 project generator, twelve shipped first-party modules (`teams` remains a README-only placeholder), and apply/recovery tooling. Generated projects use PostgreSQL 18, Vite/React, Docker, and Railway. Its public contracts are the CLI, `quickscale.yml` and applied state, module manifests, generated trees, and upgrade semantics. It is a solo-maintainer repository with a heavy, deliberate governance layer: a declared gate registry, AST gates, conformance tests, monotonic quality baselines, and a scope allowlist.

**Commit delta since the last pass** (`e40762a0..HEAD`, 7 commits, all 2026-08-20). *Housekeeping:* `309b8b7a` (doc links), `3de43250` (social subtree split, no tree change), `ed8bb9b4` and `10d6bfe2` (release notes and v88 roadmap). *Unlabeled-behavioral — read at full depth:* `be5cf024` "fix(ci): unbind hosted gates from one machine's environment" (adds restricted-role provisioning to the isolation job; relaxes the SA90 emission byte-parity gate for `.env`; moves the managed-adapter completeness assertion out of `_refresh_session_managed_adapters`), `d4b0e834` and `d3d4c633`, both titled "v0.87.0: QuickScale 0.87.0" but in fact changing hosted and publish provisioning (PGDG PostgreSQL 18 client install) and isolation-gate skip semantics. Two release-shaped messages carrying CI-topology changes is exactly the class this audit reads closely, and it paid: `d3d4c633` left a repository conformance test red (see Red flags).

**Growth direction (from the planning surface, authoritative).** The v88 roadmap records the prioritization decision as **"neither"** — no `teams` domain work and no third generated-project updater. Twenty open v88 ticket entries run on three tracks across nineteen open merge positions; the ones that touch this audit's seams are **SA124** (unify SA117 scope-tool path authority, merge #11), **SA123** (add dependency-vulnerability and security static-analysis gates, *registered through `scripts/gate_registry.json`*, merge #13), and **SA135** (give test suites an owned PostgreSQL lifecycle, merge #15). All three land on the CI/governance layer, which is where both new findings sit.

**Read fully:** the four workflows, `scripts/gate_registry.json`, `scripts/check_gate_parity.py` (context extraction and comparison), `scripts/sync_ci_gate_jobs.py` (generation and job-set validation), the `Makefile` test/gate targets, `scripts/check_ci_locally.sh` gate stations, `scripts/test_isolation_conformance.sh`, and the three behavioral diffs. **Sampled:** module sources, generator, beta migration, orgs tenancy (prior-finding anchor re-verification only). **Skipped:** generated-project template internals, frontend theme sources.

**Scope decision:** this pass is scoped to the **governance and CI layer**, on the §2d evidence that all three roadmap tracks build there this release. The three prior findings were re-verified but not re-investigated at depth, because the roadmap explicitly holds their triggers closed.

## Enforcement census

| Invariant | Enforcement | Posture | Trend since last pass |
|---|---|---|---|
| Tenant reads/writes stay organization-scoped | `TenantManager`, `FORCE RLS`, restricted-role boot guard | Structural and stable | unchanged |
| Runtime DB role cannot bypass RLS | `rolsuper`/`rolbypassrls` checks; privileged command contract | Structural and stable | unchanged |
| CSRF-exempt endpoints have alternate integrity checks | AST gate plus sanctioned endpoint bases | Structural and gated | gate's own suite unexecuted (Finding 12) |
| Core/module dependency direction | Import compatibility and reverse-import gates | Gated | unchanged |
| Module manifest snapshots equal source manifests | Manifest-sync byte comparison | Gated | unchanged |
| Manifest readers choose source vs bundled inventory consistently | Shared fallback seam plus direct-caller census | Structural, gated, merged | unchanged |
| Every emitted path has a migration disposition | Generator-derived conformance test over the ownership taxonomy | Membership gated; ownership hand-authored (Finding 7) | unchanged |
| Tenant-model universe is classified | Marker-derived overview cross-checked against the 45-entry registry | Gated | unchanged |
| Purge order respects FK dependencies | 21-entry manual order and three explicit relation checks | Partial gate (Finding 4) | unchanged |
| Last-owner deletion is rejected through ORM paths | Canonical predicate, locked model delete, `pre_delete` receiver | Structural; other cleanup boundary-owned (Finding 2) | unchanged |
| Frontend runtime config is complete and typed | `window.__QUICKSCALE__` validation plus frontend proof | Structural and gated | unchanged |
| Generated emission is byte-identical to the recorded manifest | SA90 fixture hash/mode comparison | Gated, with a new host-dependent exception set | **weakened** — `.env` hash skipped, mode normalized (`be5cf024`) |
| **Hosted CI job set is closed (no unregistered `ci.yml` job)** | `sync_ci_gate_jobs.py:314` — `registry ∪ UNOWNED_JOB_IDS` must equal the actual job set | **Structural, and the strongest thing in this layer** | unchanged |
| **Declared gates are present in every required context** | `check_gate_parity.py` registry→context membership | **Gated, one-directional and registry-scoped** | scope now measured (Finding 12) |
| **Gate implementations behave as specified** | 14 suites in `scripts/`; **4 wired to a target, 10 wired to nothing** | **Convention only — unverified** | **new row; population grew 1 → 10** |
| **CI runtime environment (PG18 client, test DBs, roles, DB users)** | Hand-replicated shell across 4 workflows and 1 script | **Convention only — ungated** | **new row; 4 divergent variants** |
| Complexity maxima never ratchet upward | Merge-base monotonicity gate plus structured waiver ledger | Gated | gate's own suite unexecuted (Finding 12) |
| Installed artifacts perform their supported lifecycle | Permanent installed-wheel `plan → apply → up` E2E over all modules | Structural and gated | unchanged |

## Summary table

| Rank | Finding | ID | Horizon | Confidence | Size | Problem in one line |
|---:|---|---|---|---|---|---|
| 1 | 12 | `gate-suites-unexecuted` | **now** / SA123, SA124 | High | M | The gates' own conformance suites live outside every test root, so the layer everything else trusts is itself unverified. |
| 2 | 13 | `ci-environment-hand-replicated` | **now** / SA135 | High | M | Each workflow hand-replicates the environment its gates need, so "same gate, same result" is a coincidence maintained by copy-paste. |
| 3 | 7 | `generated-file-ownership-unmodeled` | 6–18 months / next updater consumer | High | M | Beta migration assigns upgrade behavior through a hand-authored taxonomy the generator does not own. |
| 4 | 2 | `deletion-invariants-per-boundary-reimplementation` | deferred / second deletion boundary | High | S | Cross-domain cleanup is orchestrated by the account-delete view, not by a domain owner. |
| 5 | 4 | `org-model-universe-hand-enumerated` | deferred / tenant-model growth | High | M | Purge manually orders 21 models against an FK graph it does not derive. |

Findings 12 and 13 are at the `now` horizon. Findings 7, 2 and 4 remain behind the growth triggers the roadmap deliberately left closed.

---

## Finding 12 — The gate layer has no gate of its own

**ID:** `gate-suites-unexecuted`

**Rank rationale (blast radius × likelihood):** Blast radius is every cross-cutting invariant in the census, because each is enforced by a script whose correctness is asserted only by a suite nothing runs. Likelihood is 1.0 — it has already fired twice, and the population is growing.

**Horizon & trigger:** `now`. Two v88 tickets build directly on this layer: **SA123** ("register every new gate through the authoritative gate registry", merge #13) and **SA124** ("a test fails if any consumer is added without going through that source", merge #11). SA124's acceptance criterion is *a test* — and it will land in `scripts/test_check_sa117_scope.py`, one of the ten suites no context executes. The ticket's own guarantee is unenforceable on arrival.

**Confidence:** High. Verified by direct execution under the project interpreter and by an exhaustive absence search; the former inference about the 72 quality-baseline failures is reconciled below as historical SA156 evidence.

**Context dependence:** `wrong-regardless`. A governance layer that is not itself verified is a false signal in any deployment context, and this repository has more of it than most.

**Problem:** QuickScale's gate implementations and their conformance suites live in `scripts/`, a directory deliberately outside every declared test root and outside coverage — so gate code is the only first-party code in the repository with no owning execution context, while being the code every other gate's credibility rests on.

**Evidence** (all anchors established this pass):

- `Makefile:150` — `TEST_DIRS := quickscale_core/tests quickscale_cli/tests`. `.coveragerc` `[run] source` lists only the two `src` trees. `scripts/` appears in neither.
- **Census of `scripts/test_*.py` — 14 suites, 4 wired, 10 orphaned.** Wired: `test_ci_coverage_policy.py` (`Makefile:611`), `test_integration_worker_pool.py` and `test_e2e_parallel.py` (`Makefile:616`), `test_ci_local_parallel.py` (`Makefile:622`). Orphaned: `test_gate_parity.py`, `test_quality_baseline_monotonicity.py`, `test_check_csrf_exempt_gate.py`, `test_publish_module.py`, `test_installed_wheel_venv.py`, `test_verify_public_module_apply.py`, `test_version_tool.py`, `test_check_sa117_scope.py`, `test_verify_sa117_publication.py`, `test_check_release_published.py` — together ~755 KB covering the gate-parity checker, the CSRF AST gate, the quality-baseline monotonicity gate, the SA117 scope guard, the version tool, and the publication verifiers.
- **They were never wired.** `git log -S "test_gate_parity" -- Makefile .github/workflows/ scripts/check_ci_locally.sh` returns nothing; likewise for `test_quality_baseline_monotonicity`. These suites were born orphaned.
- **The population is growing monotonically**, one per new gate: `test_check_csrf_exempt_gate.py` 2026-07-07, three more 2026-07-27, `test_gate_parity.py` 2026-07-29, `test_installed_wheel_venv.py` 2026-08-03, `test_publish_module.py` 2026-08-06, `test_check_release_published.py` **2026-08-20** — created during the last release, in `fe850506`.
- **Historical pre-closure execution under `.venv/bin/python` (3.14.6):** `test_gate_parity.py` → **231 passed, 1 failed**; the seven publish/scope/version suites → **580 passed, 1 failed**; `test_quality_baseline_monotonicity.py` + `test_installed_wheel_venv.py` → **148 passed, 72 failed**. Total **959 passed, 74 failed** across code nothing ran. This is retained as evidence for the finding's origin, not as the current SA156/SA157 status.
- The definitive failure is `test_gate_parity.py:1090` `TestParserPrecision::test_all_twenty_one_publish_run_values_are_structural`. It compares `publish.yml`'s ordered `run:` blocks against a literal oracle; `d3d4c633` added two steps and removed two `apt-get` lines and never touched the oracle. This is repository content versus repository content — no environment dependence.
- **Closure reconciliation:** the historical failures behind this finding's origin evidence are closed by SA156, SA157, SA158, SA159 and SA168 (archived in [CHANGELOG.md](../../CHANGELOG.md)); the `scripts/` suite now reports 1,213 passed. The only open red flag is TA69. Finding 12 remains open as the broader unexecuted-suite problem: the suites are green but still have no owning execution context.
- The maintainer independently found the same shape one day ago: roadmap **SA152** records that `make beta-migrate-*` "appear in no CI workflow and no entry in `scripts/gate_registry.json`", and that `_template_emitted_paths()` "calls `pytest.skip()` … so a path-resolution regression turns the ownership gate green instead of red."

**Counter-evidence:** Searched for an enforcing layer at every plausible level and found the layer is real but narrower than the census claimed. Searched: `Makefile` (`TEST_DIRS`, every `pytest` invocation, `ci`, `check`, `quality`, `test-unit`, `test-cov`), `scripts/check_ci_locally.sh` (all `make` invocations), all four workflows for `pytest` and `scripts/test_`, `.pre-commit-config.yaml`, `.coveragerc`, every `conftest.py` in the tree, and `git log -S` for a wiring that was later removed. Found only the four `Makefile` targets above. **The genuine counter-evidence, which narrows this finding and must be preserved:** `scripts/sync_ci_gate_jobs.py:314-320` computes `expected_job_ids = UNOWNED_JOB_IDS | set(hosted_locations.values())` and raises `GeneratorError` when it does not equal the actual `ci.yml` job set — so hosted **job membership** is genuinely closed, and a new `ci.yml` job cannot ship unnoticed. That is the strongest structural control in this layer and it is why this finding is about the *suites and the non-`ci.yml` contexts*, not about hosted membership. It does not dissolve the finding: `check_gate_parity.py:2509-2511` returns `{job_to_gate[j] for j in job_names if j in job_to_gate}` — a filter, not an assertion — so parity proves *registered → present*, never *present → registered*, and no equivalent closure exists for `publish.yml`, `e2e.yml`, or `nightly-bypassrls.yml`.

**Why it compounds:** Three mechanisms, each measurable.
1. **Verification debt grows one suite per gate.** Ten orphans today, up from one on 2026-07-07. SA123 adds two gates, SA124 adds a divergence test, SA152 adds a smoke gate — four more suites into a directory nothing executes.
2. **Correction is one-directional, so silence reads as health.** `check_gate_parity.py` cannot report a gate that was never registered. `scripts/gate_registry.json` holds **7** gates; `ci.yml` has **11** jobs; `scripts/sync_ci_gate_jobs.py:67` names the difference explicitly in `UNOWNED_JOB_IDS = {lint-frontend, backups-validation, module-manifest-contract, test, isolation-conformance, lint-cli}`. `isolation-conformance` — the gate protecting the system's most load-bearing invariant — is on that exemption list, has **no Makefile target**, and is invoked from exactly one place in the entire repository: `.github/workflows/ci.yml:634`. It cannot be run through `make ci`, and it exists in no other context.
3. **What is already built on top:** every row of the enforcement census marked *gated*. The CSRF gate, the manifest-sync gate, the org-context gate, the monotonic quality baseline, the SA117 scope guard, and the version-propagation check are all trusted as proof, and all six have their proof-of-correctness in an unexecuted suite.

**Detection signal:** There is no signal today — that is the finding. To instrument: run `poetry run pytest scripts/ -q` once and record the pass/fail count as a baseline; any nonzero failure count is the signal. Thereafter, a gate whose behavior changed without its suite failing is the pattern to watch.

**Steelman:** For a solo maintainer, gate helpers are maintainer tooling, not product; running 220 quality-baseline tests on every push buys little when the maintainer is the only consumer and runs the gate itself constantly. `scripts/` being outside `TEST_DIRS` also keeps the product coverage gate (`--cov-fail-under=90`) honest — pulling `scripts/` in would either dilute the metric or demand coverage of one-off release tooling, and that is a real and correct concern. **The condition under which not to fix it:** if the maintainer treats `scripts/` suites as scratch scaffolding whose value ended when the gate was written. But the evidence contradicts that reading — these are 755 KB of adversarial, negative-control-bearing tests with names like `test_fake_gate_in_e2e_trigger_appears_as_diagnostic`. They were written to be run. The steelman does not hold; it only argues for keeping them out of the *coverage* metric, which the correct shape below preserves.

**Correct shape:** Every executable that enforces an invariant must have a conformance suite that some declared context is obliged to run, and that obligation must be visible in the same registry that declares the invariant — without those suites entering the product coverage metric.

**Options:**

1. **Make the gate suites a registered gate.** Add one `check-gate-suites` target that runs `pytest scripts/ -p no:cacheprovider --no-cov`, register it in `gate_registry.json` with `required_contexts` of at least `local-serial`, `local-parallel`, and `hosted`, and let `sync_ci_gate_jobs.py` generate its job. Cheapest, removes the compounding for the whole population at once, and keeps `scripts/` out of `.coveragerc`. Reversible. Its weakness: it treats the ten suites as one undifferentiated blob, so a slow suite taxes every run.
2. **Give the registry a `self_test` binding per gate.** Extend each gate entry with the path to its own suite, and have `check_gate_parity.py` assert that every registered gate has one and that it is executed. Strongest: it makes "a gate without a proof" a *schema* error, so SA123's two new gates cannot land unverified. Costs a registry schema version bump and touches the parity comparator. It also, correctly, forces `isolation-conformance` and the other five `UNOWNED_JOB_IDS` entries to be justified or registered.
3. **Relocate the gate helpers into a first-party package** (`quickscale_devtools/` or a new `quickscale_gates/`) with its own `tests/` under an existing test root. Most conventional, and it dissolves the "outside the topology" problem at the root rather than papering it. Largest blast radius: every `scripts/*.py` path in the `Makefile`, `sa117_scope.json`, the workflows, and the parity tool's own `_CONTEXT_SOURCES` would move, and SA124 is concurrently editing `sa117_scope.json`.

**Recommendation (ratified by the maintainer 2026-08-22):** **Option 1 now, Option 2 as SA123's own acceptance work.** Option 1 is a contained change that stops the bleeding before v88's Track 2 adds four more suites, and it is the only one that can land without colliding with SA124's in-flight edits to the scope tool. Option 2 is the durable fix and belongs with SA123, whose acceptance criterion ("both are registered in `scripts/gate_registry.json` and pass `scripts/check_gate_parity.py`") is already one field short of it. Defer Option 3 — it is the right end state but conflicts with two v88 tickets, and `scripts/` path churn would invalidate the SA117 allowlist mid-release. · **Size:** `M` · **First step:** cut the seam at the `Makefile` — add `check-gate-suites` running `pytest scripts/ --no-cov`, then confirm the historical 74-failure baseline is fully resolved before registering it, so the gate is registered green rather than registered red.

---

## Finding 13 — Each workflow hand-replicates the environment its gates need

**ID:** `ci-environment-hand-replicated`

**Rank rationale (blast radius × likelihood):** Blast radius is every service-backed gate in every context — a divergence makes the same gate mean different things in hosted, publish, e2e, and nightly. Likelihood is high: three of the seven commits in this delta were edits to these blocks, and SA135 will rewrite the model.

**Horizon & trigger:** `now`. **SA135** (v88 Track 3, merge #15) is specified as "the integration gate provisions its own PostgreSQL 18 server and tears it down, with no reliance on a pre-existing host server" and lists `docs/technical/validation_policy.md` as changing "the documented DB precondition". That work must land consistently across four workflows that today each state the precondition differently.

**Confidence:** High. Every station enumerated and read directly.

**Context dependence:** `wrong-regardless` at this station count, though it would be unremarkable at two.

**Problem:** The gate registry declares *which* gates run in *which* contexts, but the environment those gates require — PostgreSQL 18 client provenance, the test-database set, restricted-role grants, and per-module DB-user variables — is expressed nowhere declaratively and is instead hand-replicated as shell in each workflow.

**Evidence — station census (13 enumerations of the module universe, 4 variants of client provisioning):**

| Station | Location | Shape |
|---|---|---|
| PGDG PG18 install | `ci.yml:92-107`, `ci.yml:408-427`, `publish.yml:161-187`, `e2e.yml:74-91` | ~20 identical shell lines, four copies |
| PG18 verification | `ci.yml:109`, `ci.yml:429`, `publish.yml:182` vs `e2e.yml:92` | **divergent**: three check `command -v` resolution *and* `--version | grep "(PostgreSQL) 18"`; e2e checks only `test -x` |
| PG client (nightly) | `nightly-bypassrls.yml:81-82` | **divergent**: plain `postgresql-client` — Ubuntu 16.x, no PGDG, no PG18 |
| `createdb` list | `ci.yml:436-453`, `ci.yml:576-594`, `publish.yml:189-206`, `nightly-bypassrls.yml:79-98` | 4 copies; ci's isolation job carries 11, the rest carry 12 + smoke |
| Role/ownership grants | `ci.yml:455-476`, `ci.yml:596-619`, `publish.yml:208-231`, `nightly-bypassrls.yml:100-134` | 4 copies |
| `QS_*_DB_USER` env | `ci.yml:491-502`, `ci.yml:627-632`, `publish.yml:241-252`, `nightly-bypassrls.yml:140-151`, `test_integration.sh:414-425` | 5 copies; four carry 12 entries, `ci.yml:627` carries 6 |
| Copy-pinning oracle | `scripts/test_gate_parity.py:1125-1180` | a **14th** station: the shell above transcribed verbatim as a Python literal |

Two apparent divergences are **deliberate and correct**, and this pass verified them rather than reporting them: the 6-entry `QS_*_DB_USER` block at `ci.yml:627-632` is exactly `orgs` plus `RLS_MODULES=(billing blog crm forms listings)` from `scripts/test_isolation_conformance.sh:141`, and the isolation job's 11-database list omits `backups` because that job does not run backups tests. The nightly PG16 client is **not** verified as deliberate: `nightly-bypassrls.yml` creates `test_quickscale_backups` (line 87) and sets `QS_BACKUPS_DB_USER` (line 142), while `ci.yml:93-95` states the backups DR engine "enforces a PostgreSQL 18 `pg_dump`/`pg_restore` contract" that 16.x "fails". Runtime confirmation needed: whether `make test-bypassrls` reaches a `pg_dump` path.

**Counter-evidence:** Searched for a derivation or gate that would make this a false positive. Checked whether `sync_ci_gate_jobs.py` generates provisioning (it generates only the `hosted-gate-jobs`, three `needs-*` regions, and the `e2e-trigger-paths` region — `JOB_BEGIN`/`NEEDS_BEGIN`/`E2E_PATHS_BEGIN` at `sync_ci_gate_jobs.py:44-58`; provisioning steps are outside every generated marker). Checked whether `gate_registry.json` models environment — it does not; the schema is `id`/`description`/`required_contexts`/`bindings`/`depends_on`/`trigger_inputs`, and `check_gate_parity.py:498-524` validates `trigger_inputs` only as path strings. Checked whether a composite action or reusable workflow exists — `.github/` contains only the four workflow files. Checked whether the module lists are derived like manifests are (`check_sa117_scope.py:48` `_authoritative_module_names()` shells out to the discovery shim and raises on failure) — that pattern exists in the repository and is **not** applied to any of the 13 stations. The only thing holding any copy honest is `test_gate_parity.py`, which pins the shell as a literal — and per §5.XV a gate that pins a copy-pair equal does not remove the copy; it is also in the unexecuted population of Finding 12, which is why `d3d4c633` drifted freely.

**Why it compounds:** Adding a thirteenth module, or changing the pinned PostgreSQL major, requires a coordinated edit at up to 13 shell stations plus the literal oracle, with no derivation and no gate — and the failure mode is not a red build but a *quietly different* one, where a gate passes in hosted and means something else in nightly. Already built on top: every service-backed gate (`test`, `isolation-conformance`, `backups-validation`, `test-bypassrls`, the installed-wheel E2E) depends on this environment being identical, and the census shows it already is not. SA135 will have to change the provisioning model at every one of these stations simultaneously, in a release where `d3d4c633` demonstrated that a two-line provisioning edit can slip through under a release-shaped commit message.

**Detection signal:** A gate that passes in one context and fails in another with an environment-shaped error (`pg_dump: server version mismatch`, `database "test_quickscale_x" does not exist`, `permission denied for schema public`). Instrument by having each workflow print `pg_dump --version` and the resolved DB user set into the job log, so a divergence is greppable across contexts.

**Steelman:** GitHub Actions has no first-class include, and the alternatives all cost something real: a composite action adds an indirection that is harder to read in a failed job log, and pushing provisioning into a shell script means the workflow no longer shows what it does. Explicit duplication across four workflows is a defensible, common choice, and `be5cf024`'s message ("unbind hosted gates from one machine's environment") shows the maintainer is actively converging them rather than letting them rot. **Condition not to fix:** if the workflow count stays at four and the module universe stays frozen — which the roadmap's "neither" decision does guarantee for v88. That is why this ranks second rather than first, and why the recommendation below is the smallest possible change.

**Correct shape:** The environment a gate requires is part of the gate's declaration, derived from one authoritative source, so that adding a module or bumping a pin changes one place and every context follows.

**Options:**

1. **One provisioning script, four callers.** Move the PGDG install, `createdb` loop, and grant loop into `scripts/provision_ci_postgres.sh`, deriving the module list from the existing discovery shim (`quickscale_core/.../contracts/module_discovery.py --list-modules`) exactly as `check_sa117_scope.py:48` already does. Each workflow calls it with a role argument. Removes 12 of 13 stations. Low risk, high reversibility; costs log readability.
2. **Extend the registry with an `environment` block** per gate (client version, database set, role contract), and have `sync_ci_gate_jobs.py` generate the provisioning steps into all four workflows the way it already generates job and `needs` regions. Strongest — it makes environment drift a parity failure — and it is the natural home for SA135's outcome. Costs a schema version bump and extends the generator to `publish.yml`/`e2e.yml`/`nightly-bypassrls.yml`, which it does not currently touch.
3. **A composite action under `.github/actions/setup-postgres/`.** Idiomatic for GitHub Actions and the least project-specific. But it puts the module list outside the Python discovery shim, so it fixes the shell duplication without fixing the derived-module-universe half.

**Recommendation:** **Option 1 as part of SA135**, not before it. SA135 already owns `scripts/test_integration.sh`, `scripts/provision_test_roles.sh`, the `Makefile`, and the documented DB precondition — it is the one ticket whose allowlist already spans this seam, and doing the extraction inside it avoids a second pass over the same files. Take Option 2 only if SA123's registry work lands cleanly first, since both edit the registry schema and the roadmap already routes them onto the same track for exactly that reason. · **Size:** `M` · **First step:** extract the PGDG install block — the only piece that is byte-identical across three workflows and outright wrong in the fourth — into `scripts/` and prove the four callers agree, before touching the module-list loops.

---

## Finding 7 — Generated-file ownership remains a hand-authored updater taxonomy

**ID:** `generated-file-ownership-unmodeled` · **Horizon:** 6–18 months · **Confidence:** High · **Size:** M · **Context dependence:** `wrong-for-now` (new domain / second consumer)

**Trigger:** Promote when a third generated-project consumer, public updater, emitted-file expansion, or second theme is scheduled. **Not fired this pass** — the roadmap's "neither" decision explicitly schedules no third updater for v88.

**Problem:** The generator knows what it emits, but beta migration independently assigns upgrade behavior through a hand-authored taxonomy of 138 list/map entries across required donor/recipient, identity, infrastructure, protected, substituted, unmanaged, and module-react categories.

**Evidence (re-verified this pass):** `get_generator_emission_mapping()` at `quickscale_core/src/quickscale_core/generator/generator.py:142` is authoritative for emitted membership; `quickscale_devtools/src/quickscale_devtools/beta_migration.py` (2,714 lines) owns disposition; `quickscale_cli/tests/test_beta_migration_ownership_conformance.py` proves every emitted path is classified but not that the ownership decision is generator-owned or semantically correct. One supported theme, byte-parity gates, and two private updater consumers keep the current manual policy defensible.

**Counter-evidence:** Searched for a derivation making the taxonomy generator-owned; found only the membership conformance test. Roadmap SA152 independently confirms the gate's weakness from the other side — `_template_emitted_paths()` skips rather than fails when the template tree is missing, so the conformance proof can go green vacuously. That strengthens rather than disproves the finding, and is tracked as SA152 rather than promoted here because the trigger remains closed.

**Why it compounds:** Every emitted-file change requires a matching taxonomy edit at a second, unowned station; SA114 was a recent paid synchronization of exactly this kind.

**Steelman:** With one theme and two private consumers, an explicit human policy is more honest than a derived one, and deriving disposition from emission would encode a guess where a decision belongs. Do not fix while the trigger stays closed.

**Correct shape:** Upgrade disposition for an emitted path is declared once, by whoever owns emission, and read by every updater.

**Options:** ~~(status quo without a conformance gate)~~ — superseded; the membership gate landed. **1.** Add typed ownership/disposition metadata to generator emission entries and derive the beta-migration collections. **2.** Emit a versioned ownership manifest for generated projects, supporting vintage negotiation but requiring a pre-manifest migration contract. **3.** *(live)* Keep the taxonomy and conformance gate — acceptable only while the growth trigger is false.

**Recommendation:** Hold Option 3. Take Option 1 when the trigger fires; add Option 2 only for a public updater needing vintage negotiation. · **First step:** characterize the existing 138-entry policy before deriving anything.

---

## Finding 2 — Cleanup invariants terminate at the account-delete boundary

**ID:** `deletion-invariants-per-boundary-reimplementation` · **Horizon:** deferred · **Confidence:** High · **Size:** S · **Context dependence:** `wrong-for-now` (new domain / compliance)

**Trigger:** Promote when `teams`, a GDPR erasure command, bulk-admin deletion, or another account/organization deletion boundary is scheduled. **Not fired this pass** — the roadmap records no `teams` work for v88.

**Problem:** Last-owner safety is structural, but billing cancellation and other cross-domain cleanup are orchestrated only by the account-delete view, so a second boundary would rediscover and reorder those effects.

**Evidence (re-verified this pass):** `OrganizationMembership.is_last_owner_with_members()` is defined at `quickscale_modules/orgs/src/quickscale_modules_orgs/models.py:165` and consumed by locked model deletion (`models.py:329`), the orgs `pre_delete` receiver (`signals.py:66`), the HTML and JSON member-deletion views (`orgs/views.py:808`, `orgs/views.py:1161`), and the account-delete view (`auth/views.py:164`) — six callsites, all going through the one predicate. Account deletion alone cancels personal-organization subscriptions; no domain deletion service or billing backstop owns that obligation for a second boundary.

**Counter-evidence:** Searched for a domain-level deletion coordinator or billing-side backstop; found none. The last-owner predicate genuinely is structural — the `pre_delete` receiver means even a direct ORM delete is caught — so this finding is scoped to *cross-domain cleanup*, not to last-owner safety, which is sound.

**Why it compounds:** A second boundary copies the account view's billing cleanup, and the two diverge silently thereafter.

**Steelman:** One user-facing deletion flow is fully covered, and putting network calls (payment-provider cancellation) inside Django signals would be a worse structure than the current explicit orchestration. A coordinator built before a second consumer exists would be a premature abstraction.

**Correct shape:** Every deletion boundary discharges the same set of cross-domain obligations, declared once by the domains that own them.

**Options:** **1.** An explicit account/organization deletion coordinator with idempotent domain contributors. **2.** Local safeguards/outbox records in each domain — safer against bypass, but network effects complicate transactions. **3.** Deletion as a durable lifecycle/job — strongest recovery, excessive until multi-store erasure exists.

**Recommendation:** Option 1 when the trigger fires, preserving the existing last-owner model/signal backstop. Design it together with Finding 4 at `teams` kickoff so the new domain is integrated once. · **First step:** enumerate the account view's cleanup effects as a named obligation list before extracting anything.

---

## Finding 4 — Organization purge order manually shadows the FK graph

**ID:** `org-model-universe-hand-enumerated` · **Horizon:** deferred · **Confidence:** High · **Size:** M · **Context dependence:** `wrong-for-now` (tenant-model growth)

**Trigger:** Promote when `teams` adds a tenant model, or any module adds a `PROTECT`/non-deferrable dependency among purge-owned rows. **Not fired this pass.** Note for the next pass: **SA151** (v88 Track 3) regenerates every module's migrations as a single `0001_initial`. That rewrites the schema history but not the model graph, so it does not fire this trigger — but it does mean the FK edges `_DELETE_SPECS` shadows will be re-emitted from current models, which is a natural moment to derive the order rather than re-confirm it by hand.

**Problem:** Tenant-model membership is derived and gated, but `_DELETE_SPECS` manually orders 21 models while tests assert only three CRM relations. Because purge uses `_raw_delete` and composite FKs are `NOT DEFERRABLE`, the list is load-bearing.

**Evidence (re-verified this pass):** `_DELETE_SPECS` is declared at `quickscale_modules/orgs/src/quickscale_modules_orgs/management/commands/purge_organization.py:64` and consumed at line 222; `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py` (62 KB) holds the 45-entry tenant registry cross-checked against marker-derived concrete models. Purge membership is exact, atomic, and fail-loud; database constraints prevent silent partial deletion. The *ordering* is not derived or validated against installed FK edges.

**Counter-evidence:** Searched for a topological derivation or a full-graph validator; found membership derivation (gated) but no ordering derivation. The database's own `NOT DEFERRABLE` constraints are a real backstop — a wrong order fails loudly rather than corrupting — which is why this stays `deferred` rather than rising.

**Why it compounds:** Every new tenant model adds an entry whose correct position is decided by hand and proven only by whether the purge happens to run.

**Steelman:** Explicit ordering can express semantics model metadata cannot (filter annotations, deliberate overrides), and the failure mode is loud rather than silent. Deriving it would trade a readable list for a derivation that still needs overrides.

**Correct shape:** Purge order is proven against the installed FK graph, whether it is derived from it or merely validated against it.

**Options:** **1.** Topologically derive the purge plan from installed model metadata, retaining explicit labels and filter annotations. **2.** Let modules publish purge descriptors and dependencies — clearer domain ownership, still a distributed registry. **3.** Keep the explicit order and add a complete graph validator — lower migration risk, preserves the duplication.

**Recommendation:** Option 3 as a characterization gate, then Option 1 when the trigger fires. Preserve deterministic reporting and explicit overrides. · **First step:** add the validator that walks installed FK edges and asserts the existing 21-entry order is a valid topological sort.

---

## Change-cost probe

**Target:** **SA123** — "Add dependency-vulnerability and security static-analysis gates … register every new gate through the authoritative gate registry" (v88 Track 2, merge #13). Chosen because it is the next scheduled change that stresses the governance seam, and its acceptance criteria name the registry explicitly.

**Measured station list for adding *one* registered gate** (dry-run on paper, in order):

1. `scripts/gate_registry.json` — new gate object (`id`, `description`, `required_contexts`, `bindings`, `depends_on`, `trigger_inputs`).
2. `Makefile` — new `check-*` recipe.
3. `Makefile:60-68` — add the target to `.PHONY`.
4. `Makefile` `check` aggregation — parity requires each `check-*` target be reachable from `check` (`check_gate_parity.py:2551`).
5. `Makefile:230-231` — help text.
6. `scripts/sync_ci_gate_jobs.py:60-66` — `HOSTED_GATE_ORDER` tuple.
7. `scripts/sync_ci_gate_jobs.py:101` — `HOSTED_JOB_CATALOG` display/step metadata.
8. `scripts/sync_ci_gate_jobs.py:78-88` — `NEEDS_GATE_IDS` for each of the three consumer jobs.
9. `.github/workflows/ci.yml` — generated job + three generated `needs:` regions (mechanical, via `--write`).
10. `.github/workflows/publish.yml` — **hand-edited**; `sync_ci_gate_jobs.py` does not generate it.
11. `.github/workflows/e2e.yml` — `trigger_inputs` must appear as an order-preserving subsequence of the path allowlist (`check_gate_parity.py:2518-2524`).
12. `scripts/check_ci_locally.sh` — **three** per-gate `case` arms: `describe_local_conformance_gate` (line 262), the serial failure banner in `run_serial_conformance_gate` (line 299, has a `*)` default), `report_static_failure_banner` (line 423).
13. `scripts/test_gate_parity.py` — the count-pinned literal oracles: `test_all_twenty_four_publish_run_values_are_structural` (1087), `test_all_ten_bound_hosted_run_values_match_current_source` (1064), `test_e2e_extracts_thirty_three_paths` (958, asserts `len(paths) == 33`), plus four `all_five_conformance_gates`-style assertions (803, 809, 815, 847).
14. A suppression/allowlist file with per-entry rationale and owner.

**Verdict: finding evidence, for both findings.** Fourteen stations for one gate, of which **eight are hand-maintained** (1–8, 10, 12–14 minus the generated ones) and the largest single block — station 13 — lives in a suite **no context runs**. That suite was red when the probe ran; SA168 repaired its stale social-app assertions and the suite is now green, which does not change the unexecuted-suite finding. The probe also produced the sharpest single fact in this audit: the mechanism that would catch a mistake at station 13 is the mechanism Finding 12 shows is switched off.

**Counter-probe (exonerating):** the same dry-run for **adding a thirteenth module** sails through the manifest and scope seams — `_authoritative_module_names()` (`check_sa117_scope.py:48`) and `_load_module_inventory()` in `scripts/version_tool.sh` both shell out to the discovery shim and raise on failure, so module *identity* needs no edit. That derivation is real and is listed under sound decisions below. It is also the precise pattern Finding 13's thirteen environment stations fail to use, which is why the recommendation there is to reuse it rather than invent something.

## Fix order and interactions

Findings 12 and 13 are independent in mechanism but share the v88 Track 2/3 file surface, so **sequence them: 12 first**. Wiring the gate suites (Finding 12, Option 1) is a prerequisite for trusting any verification of Finding 13's extraction — otherwise the provisioning refactor is validated by the same unexecuted oracle that already drifted. Finding 12's Option 1 must also land *before* SA123 and SA124, or those tickets add four more unverified suites and SA124's "a test fails if any consumer is added" acceptance criterion is unenforceable on arrival. Finding 13 should ride inside SA135 rather than preceding it, since SA135 already owns that file surface. Findings 7, 2 and 4 are independent of both and of each other, except that 2 and 4 should be designed together at `teams` kickoff.

## Sound load-bearing decisions

- **The hosted job set is a closed universe.** `sync_ci_gate_jobs.py:314-320` computes `UNOWNED_JOB_IDS | registry-bound jobs` and raises when it does not equal `ci.yml`'s actual job set. A new hosted job cannot ship unnoticed. This is the strongest control in the governance layer and every remediation above must preserve it — Finding 12's Option 2 should *extend* this closure to the other contexts, not replace it.
- **Module identity is derived, never re-listed.** `check_sa117_scope.py:48` and `version_tool.sh` both shell out to `contracts/module_discovery.py --list-modules` and fail hard when it is unavailable. This is the repository's own good pattern; Finding 13 recommends reusing it rather than inventing a new one.
- **Tenant isolation is dual-layer and fails closed.** Ambient `TenantManager` scoping plus restricted-role `FORCE RLS`, with a boot guard that rejects a `rolbypassrls`/`rolsuper` runtime role. `be5cf024` strengthened this by making the hosted isolation job connect as `quickscale_test_role` rather than `postgres` — a superuser would have made the RLS proofs vacuous. Protect the `QUICKSCALE_ALLOW_BYPASSRLS: "0"` posture at `ci.yml:626` in any provisioning refactor.
- **Last-owner safety is a model/signal backstop, not a view check.** Six callsites, one predicate, plus a `pre_delete` receiver that catches direct ORM deletes. A future deletion coordinator (Finding 2) must not weaken this.
- **Source-required manifest operations remain fail-hard**, and bundled manifests are inventory metadata rather than module source. The v88 SA150 ticket extends this posture to the wheelhouse seam rather than contradicting it.

## Watchlist

- **Module universe repeated in environment lists.** Trigger: a thirteenth shipped module must be added to two or more ungated lists. **Not fired** — `teams` is still a README-only placeholder (`quickscale_modules/teams/` contains only `README.md`) and the roadmap's "neither" decision schedules no `teams` work for v88. Now largely absorbed by Finding 13, which measured the station count at 13; carry this item only as the promotion trigger for the *derivation* half.
- **SA92 migration-squash discovery tuple.** Trigger: another migration-bearing module is added, or the tuple omits one. **Trigger cannot be evaluated — the referenced artifact is not locatable.** An exhaustive search for `squash` across `*.py`, `*.sh`, `Makefile` and `*.json` returns only `git subtree --squash` in `quickscale_core/src/quickscale_core/utils/git_utils.py:302-345`, which is unrelated; the string `SA92` appears nowhere in the tree except this audit's own prior line. This is the same lost-identifier pattern the SA124 ticket records for advisory `SA117E1-REV-004`. **Action: re-anchor against `SA151`** (which deletes and regenerates every module migration, Track 3 merge #3) **or retire it** — do not carry it a third pass unevaluated.
- **Frontend runtime module keys.** Trigger: a new frontend-bearing module requires edits at three ungated stations. **Not fired** — no module was added this delta; the shipped set is unchanged at twelve.
- **Privileged-command template/runtime pair.** Trigger: a third sanctioned command, or a mismatch. **Not fired — values verified equal this pass:** `production.py.j2:185` `_KNOWN_PRIVILEGED_COMMANDS = frozenset({"migrate", "createcachetable"})` and `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py:36` `_PRIVILEGED_COMMANDS = frozenset({"migrate", "createcachetable"})`. Note for next pass: the `apps.py` docstring calls itself "the single source of truth for which commands are privileged" while the template holds an independent copy — a governance-artifact disagreement even while the values agree.
- **`trigger_inputs` has drifted from its name.** The field reads as "what changes should trigger this gate", but `check_gate_parity.py:2652-2690` uses it as a bidirectional partition of `e2e.yml`'s path allowlist — which is why `check-core-compat`'s trigger is `quickscale_modules/backups/**` and `smoke-install`'s is the two workflow files. Not a finding: the check it performs is real and exact. Trigger: promote if a gate is ever *skipped* on the basis of `trigger_inputs`, at which point the name's meaning becomes load-bearing.

## Questions that would change the ranking

- **Answered and retired.** *"What is the first post-0.87 domain/consumer: `teams`, a third generated-project updater, or neither?"* — **Answered "neither"**, recorded in `docs/technical/roadmap.md` under "Prioritization decision (recorded 2026-08-21)". Effect on ranking: Findings 7, 2 and 4 all stay behind their triggers and none is a v88 blocker; the audit's attention correctly moves to the governance layer, where all three v88 tracks build. This is why Findings 12 and 13 lead.
- **Answered and retired.** *"Were the ten `scripts/` suites ever intended to run in CI, or are they maintainer scratch?"* (`gate-suites-unexecuted`) — **Answered "they should run"** (maintainer, 2026-08-22), recorded in `docs/technical/roadmap.md` under "Gate-suite execution decision". Finding 12 therefore stands at full weight rather than dropping to a watchlist item, and SA155's Option 1 (`check-gate-suites` running `pytest scripts/ --no-cov`) is ratified as written. The consequence that settled it: SA124 and SA123 both express their acceptance criteria *as gates written into these suites*, so a maintainer-scratch reading would leave both unenforceable on arrival.
- **Does `make test-bypassrls` exercise any `pg_dump`/`pg_restore` path?** (`ci-environment-hand-replicated`) — if yes, the nightly workflow's PostgreSQL 16 client is a live defect rather than a harmless divergence, and Finding 13's first step becomes urgent rather than scheduled.

## Red flags (current open items)

The former SA156, SA157, TA66/SA158, SA168, and repo-source-interpreter (SA159) red flags are closed; their evidence is archived in [CHANGELOG.md](../../CHANGELOG.md). Pre-closure detail that remains above and in the reconciliation log is historical audit context, not current status. **One red flag is open.**

- **Deprecated bool inversion in a security gate (TA69).** `scripts/check_csrf_exempt_gate.py:271` uses `~val != 0` on a bool; Python removes this in 3.16. The current tech-audit remains authoritative for this open finding and identifies the semantics-preserving correction as `~int(val) != 0`; `not val` would change the gate's verdict.

## Reconciliation log

- 2026-08-21 — `generated-file-ownership-unmodeled` (Finding 7): **still-open**, deferred. Anchors re-verified (`generator.py:142`, `beta_migration.py` 2,714 lines, conformance test present). Trigger not fired; roadmap "neither" decision keeps it closed for v88. Related weakness tracked as roadmap SA152, not promoted.
- 2026-08-21 — `deletion-invariants-per-boundary-reimplementation` (Finding 2): **still-open**, deferred. Anchors re-verified; six callsites of `is_last_owner_with_members` enumerated (`orgs/models.py:165,329`, `orgs/signals.py:66`, `orgs/views.py:808,1161`, `auth/views.py:164`). Trigger not fired; no `teams` work scheduled.
- 2026-08-21 — `org-model-universe-hand-enumerated` (Finding 4): **still-open**, deferred. Anchors re-verified (`purge_organization.py:64,222`; `tenancy.py` present). Trigger not fired. SA151 noted as a natural derivation moment for the next pass.
- 2026-08-21 — `gate-suites-unexecuted` (Finding 12): **new**. Root cause of the red `test_gate_parity` oracle and of roadmap SA152's independent "no gate registry entry" observation.
- 2026-08-21 — `ci-environment-hand-replicated` (Finding 13): **new**. Surfaced by the commit-delta reading of `be5cf024`/`d4b0e834`/`d3d4c633`.
- 2026-08-21 — Fix-regression audit of the delta's three behavioral commits. `be5cf024` **relocated rather than removed** compounding in one place: the SA90 emission byte-parity gate gained `_HOST_DEPENDENT_PATHS = frozenset({".env"})` (`quickscale_core/tests/test_generator/test_generator.py:1023`), a new hand-maintained exception list that suppresses hash comparison while keeping presence and a normalized mode. The justification (`.env` embeds `DOCKER_UID`/`DOCKER_GID`) is sound and the mode normalization to `755`/`644` correctly removes a umask dependency — but this is a **new exception station to watch for monotonicity**, per §5.XV. The same commit moved the managed-adapter completeness assertion from `_refresh_session_managed_adapters()` into the session fixture (`quickscale_core/tests/test_manifest_entry_point.py:163-180`), correctly narrowing it so deliberately-narrowed registries do not trip it; the guard test was updated in step. No prior sound decision was weakened; the isolation job's restricted-role change strengthened one.
- 2026-08-21 — Prior watchlist reconciled: *module universe in environment lists* **not fired** (absorbed into Finding 13); *SA92 migration-squash tuple* **unevaluable — artifact not locatable**, flagged for re-anchoring or retirement; *frontend runtime module keys* **not fired**; *privileged-command pair* **not fired, values verified equal**. One item added (`trigger_inputs` name drift).
- 2026-08-21 — Prior red flags: none were carried from the previous pass (the prior document recorded no Red flags section). The pre-closure entries for SA156 and SA157 are retained above as historical evidence; the current red-flag set was TA66 and TA69.
- 2026-08-22 — Reconciliation after SA156, SA157, and SA158 closure: the quality-baseline, SA117 false-green, and stale-publish-oracle red flags are historical only. The current open red flag is TA69 (deprecated bool inversion), while Finding 12 remains a broader live architectural finding. The live tech-audit count at that point was S3: 2; S4: 2; total 4; it dropped to S3: 1; S4: 2; total 3 when TA65 was retired later the same day (see the SA159 entry below).
- 2026-08-22 — SA158 also recorded the pre-edit `make quality` discrepancy: two warning regressions (`development_commands.py::up` 15 versus baseline 14 and `social/.../adapter.py::_social_manifest_apps` 13 newly above threshold), critical regressions 0, monotonicity pass. This is accepted baseline evidence, not an SA158 regression.
- 2026-08-22 — SA168 and SA159 are both closed (evidence in [CHANGELOG.md](../../CHANGELOG.md)); the prior recursive parity failures and the bare-`python3` repo-source red flag are historical. **Finding 12 remains open** until SA155 gives the gate suites an owning execution context, and SA155 now has no open prerequisite. TA65 is retired with SA159's closure, leaving the live tech-audit count at **S3: 1; S4: 2; total 3**, with TA69 the sole open red flag.

*Lenses scanned with no qualifying finding this pass: data/state model integrity, trust and authorization boundaries, concurrency and state isolation, security architecture, API and contract stability, observability, performance and scalability, and the library/CLI archetype lenses — the governance-layer scope (§2e) deliberately deprioritized re-walking these, and the prior pass's conclusions there were re-verified only at their anchors.*

Closed findings, retired watch items, historical option records, and cross-reference migrations are archived in [CHANGELOG.md](../../CHANGELOG.md) and version control rather than repeated in this live audit.
