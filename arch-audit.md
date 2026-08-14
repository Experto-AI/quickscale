# Structural Autopsy: QuickScale

## Orientation summary — 2026-07-26

QuickScale is a mature, solo-maintained Python/Poetry monorepo at `VERSION 0.87.0` on branch `v87`: its product is a Django project generator/scaffolding CLI (`quickscale_core` + Click-based `quickscale_cli`), an apply/recovery engine and maintainer migration tool, and twelve shipped first-party Django modules; `teams` remains README-only. Generated projects are Django 6/PostgreSQL 18 applications with a Vite/React frontend, Docker, and a single-service Railway deployment; PostgreSQL is both state store and a trust boundary because tenant isolation combines a scoped manager, `FORCE ROW LEVEL SECURITY`, connection priming, and a restricted runtime role. The public contracts are the CLI surface, `quickscale.yml`/state formats, module manifests, generated trees, and their upgrade semantics. The stated architecture and current code agree on user-owned generated code, fail-hard resolution, and dual-layer tenancy, but disagreed on two governance contracts at intake: quality maxima declared shrink-only were mutable without a monotonicity gate (**resolved 2026-07-29 by SA121**), and the release assurance inventory was replicated across local, hosted, publish, and path-trigger definitions (Finding 11, **resolved 2026-08-12 by the SA122b series**). The immediate growth path is SA117e's reviewed split push, then the installed-wheel `plan → apply → up` lifecycle proof (SA112a closed 2026-08-03; SA112b–f remain) followed by human-only SA96 publishing. Findings 12 and 11 are resolved; Findings 7/2/4 remain explicitly unscheduled or deferred with a third updater consumer/`teams`. This is a rerun from prior audit base `82a73d1f` to committed `HEAD 9950523f`: all 160 commits were classified as 65 closeout, 78 housekeeping, and 17 unlabeled-behavioral commits. The latter were read at full depth: `bee9c579`, `6694b13c`, `84cba19b`, the identical worktree triplets `b097dc05/016b5b02/22100e89`, `1fd62741/d55ec670/d94e0847`, `706ab314/59c4dfd3/f4826f30`, `56d6a8cd/9dbf9230/46c72a16`, and checkpoint/revert pair `45e37a86/56b27045`. Current uncommitted user work in module discovery/resolvers, the social manifest loader, `.gitignore` generation, the emission fixture, and resolver/fallback tests was read as present workspace state but kept separate from that commit classification and left untouched. Read fully: prior findings' seams, all closeout and unlabeled-behavioral diffs, generator ownership/emission paths, local/hosted/publish/e2e gate wiring, the quality gate/baseline history, deletion and purge paths, and the `plan → apply` critical path. Sampled: per-module domain code and routine tests. Skipped: individual feature internals unrelated to those seams and runtime execution; this is static source/history analysis, and no tests or state-changing commands were run.

## Enforcement census

| # | Invariant | Where enforced | Class | Trend since 2026-07-19 |
|---|---|---|---|---|
| 1 | Tenant reads/writes remain organization-scoped | `TenantManager`, `FORCE RLS`, AF9 connection wrapper | structural | stable |
| 2 | Runtime DB role cannot silently bypass RLS | orgs boot guard checks `rolsuper`/`rolbypassrls`; generated launcher selects the role | structural | stable |
| 3 | Admin reads obey organization scope | `TenantModelAdmin` plus restricted-role integration posture | structural + gated | stable |
| 4 | CSRF-exempt endpoints have an alternate integrity check | AST gate plus sanctioned API bases | gated + structural bases | stable |
| 5 | Core/module dependency direction | import compatibility and reverse-import gates | gated | stable |
| 6 | Module manifest snapshots equal module-owned manifests | `sync_module_manifests.py` byte comparison | gated | strengthened by installed-context fallback centralization in the current worktree |
| 7 | Manifest readers select source vs bundled inventory consistently | current `resolve_manifest_base_path()`/`load_module_manifest_with_fallback()` seam; direct-caller census test | structural + gated in current worktree | strengthening, uncommitted |
| 8 | Every emitted path has a migration disposition | generator-derived SA66 conformance test | gated over a convention-owned taxonomy | membership stays fail-loud; ownership meaning remains hand-authored (Finding 7) |
| 9 | Tenant-model universe membership is classified | 45-entry `TENANT_TABLE_REGISTRY` plus bidirectional conformance checks | gated | stable |
| 10 | Organization purge order respects FK dependencies | 21-entry ordered `_DELETE_SPECS` and three CRM order assertions | convention + partial gate | stable; only three named order edges are gated (Finding 4) |
| 11 | Last-owner deletion is rejected through all ORM deletion paths | canonical model predicate, locked model `delete()`, `pre_delete` receiver | structural for that invariant | stable; other domains' deletion invariants remain boundary-owned (Finding 2) |
| 12 | Frontend runtime config is complete and typed | `window.__QUICKSCALE__` validator + frontend proof | structural + gated | strengthened; Finding 10 closure re-verified |
| 13 | Local, hosted, publish, and e2e-trigger gates cover the same required properties | `scripts/gate_registry.json` as the single membership source; blocking parity and generation checkers | gated | resolved 2026-08-12: the SA122b series migrated every consumer — including the generated `e2e.yml` path list — onto the registry (former Finding 11) |
| 14 | Complexity maxima never ratchet upward | `check_quality_baseline_monotonicity.py` merge-base diff gate + structured waiver ledger, invoked by `check_quality.sh` | gated | resolved 2026-07-29: SA121 landed the monotonicity gate; per-file line ceilings retired by SA125 |
| 15 | Installed artifact can perform its supported lifecycle | smoke test for non-mutating commands; SA112 planned for full lifecycle | partially gated | improving, but `apply → up` proof remains the release critical path |

## Summary table

| Rank | Finding | ID | Horizon | Confidence | Size | One-line problem |
|---:|---:|---|---|---|---|---|
| 1 | 7 | `generated-file-ownership-unmodeled` | 6–18 months | High | M | The updater re-encodes generator file ownership in 138 hand-classified entries rather than consuming ownership metadata from the emission contract. |
| 2 | 2 | `deletion-invariants-per-boundary-reimplementation` | deferred (teams/new erasure path) | High | S | Last-owner deletion is structurally protected, but other domain cleanup obligations still live only in the account-delete boundary. |
| 3 | 4 | `org-model-universe-hand-enumerated` | deferred (teams) | High | M | Purge membership is checked, but the load-bearing deletion order is a manual list with only three named edges asserted. |

**No finding is at the `now` horizon.** Finding 11 was resolved on 2026-08-12; closure detail is in [CHANGELOG.md](CHANGELOG.md) and the reconciliation log below.

## Finding 7: Generated-file ownership remains a hand-authored updater taxonomy

**ID:** `generated-file-ownership-unmodeled`

**Rank rationale (blast radius × likelihood):** A wrong disposition overwrites or strands user code across generated projects, while the next trigger is explicit but unscheduled: a third consumer, public updater, or emitted-file expansion.

**Horizon & trigger:** `6–18 months` — promote to `now` when a third generated-project consumer or public “update my generated project” command is scheduled, or when a second theme returns.

**Confidence:** High — generator emission, all taxonomy containers, their conformance gate, and the latest paid synchronization were read; deployed beta projects are outside repository access.

**Context dependence:** `wrong-for-now` on consumer count. A curated disposition list is defensible for one maintainer and two private upgrade sites, but it becomes an externally frozen upgrade contract once more projects depend on it.

**Problem:** The generator knows what it emits but not who owns each output after generation; beta migration independently assigns upgrade behavior through hand-authored path collections.

**Evidence:**

- Production derives emitted files from `get_generator_emission_mapping()` at [quickscale_core/src/quickscale_core/generator/generator.py](quickscale_core/src/quickscale_core/generator/generator.py#L141-L160) and consumes it at [generator.py](quickscale_core/src/quickscale_core/generator/generator.py#L543-L571).
- The updater separately carries 4 required-donor, 6 required-recipient, 2 optional-donor, 5 identity-root, 4 identity-package, 6 donor-Django, 4 protected-package, 1 protected-root, 13 infrastructure, 4 substituted-infrastructure, 87 unmanaged, and 2 module-react map entries—138 list/map entries before their nested paths. The largest live stations start at [quickscale_devtools/src/quickscale_devtools/beta_migration.py](quickscale_devtools/src/quickscale_devtools/beta_migration.py#L107-L130) and [beta_migration.py](quickscale_devtools/src/quickscale_devtools/beta_migration.py#L265-L275).
- The updater does not import or consume `get_generator_emission_mapping`. The SA66 test imports both worlds and asserts membership at [quickscale_cli/tests/test_beta_migration_ownership_conformance.py](quickscale_cli/tests/test_beta_migration_ownership_conformance.py#L23-L42) and [test_beta_migration_ownership_conformance.py](quickscale_cli/tests/test_beta_migration_ownership_conformance.py#L61-L94); it proves every emitted path is classified, not that the ownership decision is generator-owned or semantically correct.
- SA114 paid the tax: commit `66157380` added `validateQuickScaleSeam.ts` to infrastructure ownership and its test to unmanaged ownership; [quickscale_core/tests/test_beta_migration_seam.py](quickscale_core/tests/test_beta_migration_seam.py#L1-L69) records that the seam had previously been silently skipped.
- Finding 10's SA104–108 closure shrank future frontend variation but did not remove this mechanism. The current `.gitignore` user edit plus three SA90 emission-hash updates is fresh evidence that generator output evolves; it is correctly caught by emission parity but still needs a separate ownership judgment when disposition changes.

**Counter-evidence:** Searched generator mappings/templates, SA66/SA90 tests, decisions, updater imports, manifest/state formats, and current worktree changes for emitted ownership metadata or vintage-aware migration contracts. Found exact emitted-universe and byte-parity gates, a detailed deliberate taxonomy decision, and one theme with project-agnostic frontend source. These materially reduce silent omissions and justify deferral. None makes ownership/disposition a property of the emitted artifact or derives updater behavior; the gate pins the copy rather than deleting it.

**Why it compounds:** Every new emitted file forces an ownership judgment in the updater taxonomy and its rationale; every new migration mode or consumer adds another interpretation of the same paths. Existing fresh-first, in-place, substituted, protected, unmanaged, and module-react flows all depend on the current classification and must migrate if ownership becomes explicit later.

**Detection signal:** An SA66 “unclassified emitted path” failure, a migration report that silently skips a newly emitted file, unexpected overwrite/preservation in a beta site, or repeated commits that edit generator templates plus `beta_migration.py`. Deployed confirmation requires dry-running both migration modes against representative vintage projects and diffing user-owned files.

**Steelman:** File ownership is contextual—`Dockerfile` may be infrastructure-owned while `README.md` is intentionally user-owned—so a human-curated policy is more honest than inferring from path shape. Keep it while beta migration remains maintainer-only, consumers stay at two, and the derivation gate remains blocking.

**Correct shape:** Every emitted path has one versioned ownership/disposition contract at the emission boundary, and all generators/updaters consume it rather than reconstructing it.

**Options:**

1. Attach ownership/disposition metadata to generator emission entries and derive beta-migration collections from it. Moderate migration of one seam; removes the current hand-copy while retaining human policy judgment.
2. Emit a vintage/ownership manifest into generated projects and make future update tooling consume it. Strong for already-generated-project compatibility and reversible by schema version; requires migration behavior for projects predating the manifest.
3. ~~Keep the hand taxonomy but add an emitted-universe conformance gate.~~ Landed as SA66/SA90; it removes silent membership gaps but not ownership compounding.

**Recommendation:** Option 1 when the named trigger fires; layer Option 2 only if a public updater needs vintage negotiation. This fits a generator whose code is the product without prematurely building a general migration platform. **Size:** M. **First step:** extend the authoritative emission mapping with a typed ownership/disposition value for the current 138-entry census and make the existing conformance test prove the updater derives from it.

## Finding 2: Domain cleanup invariants still terminate at the account-delete view

**ID:** `deletion-invariants-per-boundary-reimplementation`

**Rank rationale (blast radius × likelihood):** A missed boundary can orphan active external billing or violate ownership, but the only known expansion—`teams` or a new erasure/admin path—is explicitly unscheduled.

**Horizon & trigger:** `deferred` — the roadmap defers this with `teams`; promote when `teams`, a GDPR-style erasure command, bulk admin deletion, or another account/org deletion boundary is scheduled.

**Confidence:** High — all current first-party deletion entry points and signal/model safeguards were searched; external Stripe behavior and direct database writes were not executed.

**Context dependence:** `wrong-for-now` on new domain/deletion boundaries. The current single account-delete UI is covered; a second orchestration boundary turns its billing cleanup into procedural duplication.

**Problem:** Ownership safety is now structurally attached to the membership entity, but billing cancellation and other cross-domain deletion obligations are orchestrated only by one HTTP view rather than by a domain-owned deletion contract.

**Evidence:**

- `OrganizationMembership.is_last_owner_with_members()` is canonical at [quickscale_modules/orgs/src/quickscale_modules_orgs/models.py](quickscale_modules/orgs/src/quickscale_modules_orgs/models.py#L165-L185), and locked model deletion consumes it at [models.py](quickscale_modules/orgs/src/quickscale_modules_orgs/models.py#L298-L336).
- The SA70 `pre_delete` receiver is wired at [quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py](quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py#L194-L208), so cascade-driven ORM deletion cannot bypass last-owner safety.
- The census found 4 explicit consumers/check stations for the predicate: model deletion, account deletion, HTML member removal, and JSON member removal ([quickscale_modules/auth/src/quickscale_modules_auth/views.py](quickscale_modules/auth/src/quickscale_modules_auth/views.py#L147-L168), [quickscale_modules/orgs/src/quickscale_modules_orgs/views.py](quickscale_modules/orgs/src/quickscale_modules_orgs/views.py#L808-L817), [orgs/views.py](quickscale_modules/orgs/src/quickscale_modules_orgs/views.py#L1161-L1172)). All four are backed by the model/signal seam.
- Account deletion alone cancels personal-organization subscriptions before deleting the user at [quickscale_modules/auth/src/quickscale_modules_auth/views.py](quickscale_modules/auth/src/quickscale_modules_auth/views.py#L111-L137). Searches of billing, auth, and orgs found no billing `pre_delete` hook, domain deletion service, or storage invariant enforcing that external cleanup from a second boundary.

**Counter-evidence:** Searched model overrides, signals, app startup, service modules, purge command, account/org views, billing subscription lifecycle, and tests for a higher deletion orchestrator or billing backstop. Found the canonical last-owner rule and SA70 receiver, which close the original ownership bypass class and materially narrow this finding. The purge command deliberately bypasses row signals inside an atomic, ordered full-org purge; it is a distinct destructive contract. No equivalent structural owner exists for subscription cancellation.

**Why it compounds:** Each new deletion boundary must rediscover and order org locks, last-owner safety, billing cancellation, storage cleanup, and future teams-domain obligations. Account deletion, member removal, org purge, and external billing are already built on different portions of the contract; later centralization must migrate all of them.

**Detection signal:** User/org rows deleted while Stripe subscriptions remain active, billing webhooks referencing absent organizations, manual post-erasure cleanup, or a second deletion command copying `_cancel_personal_org_subscriptions`. Confirm externally by reconciling active Stripe subscriptions to live organizations after deletion.

**Steelman:** Cross-domain deletion orchestration is premature while only one user-facing account deletion exists, and Django signals are a poor home for network calls. Do not add a service merely to wrap the current view; wait for the named second boundary.

**Correct shape:** One explicit deletion workflow owns cross-domain preconditions/effects, while each domain contributes enforceable local invariants and idempotent cleanup that every boundary must invoke.

**Options:**

1. Add a domain-owned account/org deletion orchestrator with registered invariant/cleanup contributors; move the current view to it when the second boundary arrives. Explicit ordering and testability; moderate caller migration.
2. Give each domain local `pre_delete` safeguards/outbox records. Harder to bypass and good for local data, but network cancellation in signals complicates transactions and recovery.
3. Model deletion as a durable lifecycle state/job, with billing/storage completion before final erasure. Strongest crash recovery and compliance auditability; excessive until asynchronous multi-store erasure is real.

**Recommendation:** Option 1 at the trigger, preserving SA70 as the last-owner backstop. It is the smallest design that supports `teams`/erasure without putting external effects in signals. **Size:** S. **First step:** define an idempotent deletion coordinator interface and route the existing account-delete view through a billing contributor without changing user-visible behavior.

## Finding 4: Organization purge order is a manual shadow of the FK graph

**ID:** `org-model-universe-hand-enumerated`

**Rank rationale (blast radius × likelihood):** A wrong order blocks or partially complicates destructive tenant erasure, but the list is stable and the next tenant model (`teams`) is unscheduled.

**Horizon & trigger:** `deferred` — promote when `teams` adds its first tenant-owned model or any module adds a `PROTECT`/non-deferrable dependency among purge-owned rows.

**Confidence:** High — the full registry, purge list, FK-order comments, conformance tests, and decision record were read; behavior under a future schema is necessarily prospective.

**Context dependence:** `wrong-for-now` on the next tenant-model domain. With 21 purge models and one maintainer, the list is manageable; `teams` introduces a new dependency subgraph and makes ordering review a repeated cross-module obligation.

**Problem:** Tenant-model membership is derived/gated, but destructive purge sequencing independently hand-encodes the database dependency graph.

**Evidence:**

- The 45-entry tenant classification registry is explicit at [quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py](quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py#L120-L145) and ends at [tenancy.py](quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py#L420-L442); its coverage test derives concrete models and fails on missing/stale entries at [quickscale_modules/orgs/tests/test_tenant_table_conformance.py](quickscale_modules/orgs/tests/test_tenant_table_conformance.py#L85-L143).
- The purge command independently orders 21 models in `_DELETE_SPECS`; its contract explicitly says entry order determines priority at [quickscale_modules/orgs/src/quickscale_modules_orgs/management/commands/purge_organization.py](quickscale_modules/orgs/src/quickscale_modules_orgs/management/commands/purge_organization.py#L55-L64), with the full hand list at lines 64–212.
- The completeness test correctly derives *membership* from `get_tenant_models()` and compares all 21 entries at [quickscale_modules/orgs/tests/test_management_commands.py](quickscale_modules/orgs/tests/test_management_commands.py#L1791-L1840), but order coverage asserts exactly three CRM relations—`DealNote < Deal < Stage`—at [test_management_commands.py](quickscale_modules/orgs/tests/test_management_commands.py#L1842-L1861). Forms/social/blog/billing ordering comments are not checked against model metadata.
- Purge intentionally uses `_raw_delete` after the manual cross-module sequence at [purge_organization.py](quickscale_modules/orgs/src/quickscale_modules_orgs/management/commands/purge_organization.py#L417-L450), making the list load-bearing rather than advisory. The schema decision makes composite FKs `NOT DEFERRABLE`, so an omitted/misordered edge fails immediately rather than being deferred.

**Counter-evidence:** Searched Django model metadata use, migration state, database introspection, topological sorting, purge-plan builders, and conformance tests. Found strong membership derivation, atomic execution, fail-loud `PROTECT`/non-deferrable constraints, and three explicit CRM ordering proofs. These prevent silent data loss and justify deferral. No code derives or exhaustively verifies the order against all 21 models' FK edges.

**Why it compounds:** Every new tenant model must update the classification contract and, if purge-owned, be inserted at the correct position among 21 entries; every new parent/child FK can invalidate existing order without changing membership. CRM, forms, listings, blog, social, and billing already depend on the sequence, so later derivation must preserve their labels/reporting and destructive behavior.

**Detection signal:** `ProtectedError`/integrity errors during `purge_organization`, a purge transaction rolling back after new schema lands, or new order-specific assertions added one relationship at a time. Before promotion, a static graph diagnostic can compare `_DELETE_SPECS` order with installed-model FK edges.

**Steelman:** Explicit order is readable, deterministic, and conservative; database constraints make mistakes fail loudly inside one transaction. Keep it while the model universe is stable and destructive purge is rare.

**Correct shape:** Purge order is derived or exhaustively validated from the installed FK dependency graph, with explicit overrides only for intentional semantics not expressible in metadata.

**Options:**

1. Topologically derive the purge plan from installed models' FK graph, preserving explicit label/filter metadata as annotations. Removes ordering duplication; requires careful treatment of cascades, cycles, generic relations, and unavailable apps.
2. Let modules publish purge descriptors/dependencies and aggregate them in orgs. Clear domain ownership and supports optional modules; still a distributed registry and can restate FK facts.
3. Keep `_DELETE_SPECS` execution but add a complete graph validator that proves every relevant FK edge is in order. Lower migration risk and catches drift, but the list remains a copy and future developers still choose insertion points.

**Recommendation:** Option 1 when `teams` starts, using Option 3 as a short-lived characterization gate during migration. The database graph already contains the load-bearing order and the system is Django/PostgreSQL-specific. **Size:** M. **First step:** build a read-only graph extractor over the current 21-model census and make it reproduce the existing sequence/explicit tie-breaks before changing purge execution.

## Change-cost probe

### Probe A — add one repository conformance gate

Measured stations, in order:

1. Define the Make target.
2. Add it to Make `check`.
3. Add serial dispatch/error attribution to `check_ci_locally.sh`.
4. Add parallel worker dispatch/error attribution to the same script.
5. Update local runner worker-count/order/replay tests.
6. Add a hosted CI job.
7. Add the job to downstream `needs`.
8. Decide and separately implement publish membership.
9. Add relevant source/test paths to e2e workflow filters.
10. Update developer/release documentation.

**Verdict:** this was the finding evidence for `quality-gate-topology-hand-synced` — ten potential stations with no authoritative membership gate. **Superseded 2026-08-12:** membership for all five contexts now derives from `scripts/gate_registry.json` with blocking parity and generation checkers, so stations 2–4, 6, 7, and 9 are generated rather than hand-edited. Re-measure this probe before citing the ten-station count again.

### Probe B — implement the roadmap's SA112 installed-wheel lifecycle

Measured stations are the six deliberately serial roadmap children: provisioner extraction (SA112a), installed `apply` diagnostic (b), traceback-selected root fix (c), permanent lifecycle e2e (d), exact workflow-trigger contract (e), and ordered acceptance/closeout (f), followed by human publish. The chain touches provisioning scripts, the ultimately diagnosed production seam, a lifecycle test, e2e workflow paths, and closeout docs; its sequencing is explicit in [docs/technical/roadmap.md](docs/technical/roadmap.md)'s SA112 umbrella.

**Verdict:** exonerated as a one-time seam-closing migration, not a recurring feature tax. The causal split prevents speculative fixes and leaves future installed-artifact changes behind one lifecycle proof. SA112e's manual path-list station independently fed Finding 11 — *as of 2026-08-12 that station is eliminated rather than counted: it became a gate-registry append, was relocated off the chain as `SA143`, and the chain measures four serial children with no manual path-list station.*

## Fix order and interactions

Findings 11 (SA122b series, 2026-08-12) and 12 (SA121) are resolved. Finding 7 remains intentionally gated on consumer growth and does not block release. Findings 2 and 4 are independent of the governance work but should be designed together at `teams` kickoff: derive the model/purge universe first (Finding 4), then attach new deletion contributors to the coordinator (Finding 2), avoiding two passes over the new domain.

## Sound load-bearing decisions

- **Dual-layer tenant isolation is structural and fail-closed.** `TenantManager` scopes queries at [quickscale_modules/orgs/src/quickscale_modules_orgs/managers.py](quickscale_modules/orgs/src/quickscale_modules_orgs/managers.py#L15-L40), while FORCE RLS/restricted-role boot checks protect bypass paths. Preserve both layers during purge/deletion changes.
- **Generator emission has one authoritative mapping.** `get_generator_emission_mapping()` is shared by production and SA66 conformance ([generator.py](quickscale_core/src/quickscale_core/generator/generator.py#L141-L160)); Finding 7 should extend this seam rather than invent a second scanner.
- **Frontend project/module truth crosses one fail-hard runtime seam.** SA104–108 made `frontend/src` project-agnostic and `window.__QUICKSCALE__` validated; Finding 10's mechanism is gone, not relocated. Do not reintroduce source specialization.
- **Manifest source selection is converging on one owning component.** The current worktree's `resolve_manifest_base_path()` plus `load_module_manifest_with_fallback()` serves all twelve resolver module readers and social, with a direct-caller census. Preserve fail-hard source-required operations rather than broadening fallback indiscriminately.
- **Last-owner safety has a real domain backstop.** The canonical predicate, lock-guarded model deletion, and `pre_delete` receiver close ORM/cascade bypasses. Finding 2's coordinator should consume, not replace or weaken, that invariant.

## Watchlist

- **Module universe hand-enumerated in CI/database-user lists.** Prior trigger: a 13th shipped module. **Not fired:** twelve shipped modules remain; `teams` is README-only. Promote when a 13th module must be added to two or more ungated environment lists.
- **SA92 migration-squash discovery tuple is fail-silent.** Prior trigger: a new migration-bearing module. **Not fired:** the guarded universe is unchanged. Promote when `teams` adds migrations or the tuple omits another shipped migration package.
- **Frontend runtime module keys remain repeated across TypeScript/config tests.** Trigger: the next frontend-bearing module. The SA105 dormant-file decision prevents project-specific source, so this does not qualify today; promote if a new module requires edits at three ungated runtime-key stations.
- **Installed-context manifest fallback centralization is uncommitted current work.** Trigger: a fifth recurrence/direct manifest reader outside the allowed source-required set. Current census finds twelve resolver readers and social using the shared fallback, with three deliberate direct/source-required callers guarded by a test; carry until the change lands and survives fix-regression audit.
- **Privileged-command template/runtime copy-pair.** Prior trigger: a third sanctioned command or mismatch. **Not fired:** the two sets remain equal and fail-closed. Promote if another consumer/command makes the pair a three-station contract.

## Questions that would change the ranking

- What is the first post-0.87 domain/consumer: `teams`, a third generated-project updater, or neither? `teams` promotes Findings 2/4; a third updater promotes Finding 7.
- Are release tags mechanically restricted to commits with the complete hosted required-check set green? A verified branch/tag protection dependency would reduce Finding 11's publish blast radius, though not its local/trigger coordination tax.

## Reconciliation log

- Historical reconciliation through 2026-07-26 remains preserved in version control (this file's former path was `docs/others/arch-audit.md`). Prior Findings 1, 3, 5, 6, 8, 9 are resolved; their mechanisms were not found regressed in this pass.
- 2026-07-26 — `generated-file-ownership-unmodeled`: **still-open**; anchors re-resolved. SA66/SA90 remove silent emission-membership gaps but pin, rather than remove, the hand-authored ownership station. SA114 is new paid synchronization evidence.
- 2026-07-26 — `deletion-invariants-per-boundary-reimplementation`: **still-open, narrowed**; SA70 closure remains clean for last-owner safety, while cross-domain billing cleanup still has no deletion owner.
- 2026-07-26 — `org-model-universe-hand-enumerated`: **still-open**; 45-entry membership census remains bidirectionally gated, 21-entry purge membership is exact, and purge ordering remains manual with only three asserted edges.
- 2026-07-26 — `frontend-source-generation-specialized`: **resolved, closure re-verified**; SA104–108 removed per-project frontend source specialization, preserved the runtime seam/fail direction, and minted no equivalent ownership copy. Residual runtime module-key repetition is a watchlist item.
- 2026-07-26 — `quality-gate-topology-hand-synced`: **new**; promoted from recurring gate-drift evidence and SA115-CI-001.
- 2026-08-12 — `quality-gate-topology-hand-synced` (former Finding 11): **RESOLVED** by the SA122b series (`-1` … `-5`). `scripts/gate_registry.json` is the single membership source; Make aggregation, both `check_ci_locally.sh` inventories, hosted CI jobs and `needs`, publish membership, and `e2e.yml`'s `on.pull_request.paths` list all derive from it, with `make check-gate-parity` and `make check-ci-gate-generation` blocking. Closure detail and evidence are in [CHANGELOG.md](CHANGELOG.md). The former Finding 11 section is removed per this document's convention; its Options/Recommendation record survives in version control.
- 2026-07-26 — `quality-baseline-monotonicity-unenforced`: **new**; prior quality-governance watchlist trigger **fired** because commit `66157380` raised all three changed numeric maxima after the shrink-only decision.
- 2026-07-26 — Prior red flag “rendered frontend proof ungated”: **fixed**, re-verified in `.github/workflows/ci.yml` and `.github/workflows/publish.yml`; SA103 remains effective.
- 2026-07-26 — Prior watchlists: module-universe list **not fired, carried**; SA92 tuple **not fired, carried**; retired-theme preflight **not fired, retired as obsolete for the sole supported theme unless a second theme returns**; quality governance **fired, promoted to Finding 12**; reverse-import dynamic edge **not fired, retired from the curated live watchlist**; subprocess-env third builder **not fired, retired from the curated live watchlist**; privileged-command copy-pair **not fired, carried**; billing webhook duplicate window **not fired, retired from this structural watchlist**; dual child-table APIs **not fired, absorbed by the `teams` triggers on Findings 2/4**; divergent CLI compensation **not fired, retired from the curated live watchlist**; `orgs/views.py` fusion **not fired and still fails the compounding gate, retired**; option-default multi-source **not fired and no new consumer, retired**; hardcoded `EXEMPT_PATH_PREFIXES` **not fired and remains ticket-shaped, retired**.
- 2026-08-07 — Cross-reference refresh (no finding status changed). This document's 2026-07-26 narrative predates two board changes and is preserved as a dated snapshot; read it with these corrections. (a) The ticket `SA115-CI-001` cited at the census row 13, Finding 11's trigger/evidence, and the promotion line is now tracked inside **SA122b-5** in [docs/technical/roadmap.md](docs/technical/roadmap.md) (the former SA115 item 4 was folded there on 2026-08-08, since SA122b-5 already migrates the same `on.pull_request.paths` list); the defect it names is unchanged and still open. (b) The stated growth path ran through the **SA136** tag-sealed-split-publication umbrella; all of `SA136a`–`SA136f` are closed and merged (2026-08-12), SA112a is closed and merged, and the critical path is now `SA117e-4 → SA112b→c→d→e→f → SA140 → SA96-PUBLISH`. `SA141` (Core E2E Poetry-install repair, the former parallel green-gate prerequisite on Track 1) closed 2026-08-12, so SA112f and SA115a no longer wait on it. Finding 11 remains open and ticketed as SA122b (`-5` is the sole open child; `-4` closed 2026-08-08); Findings 7/2/4 remain unscheduled/deferred. (c) **2026-08-12 — merge order reversed and two tickets merged.** SA122b-5's `merge after SA112e` bound is retired: it now lands **first**, deriving `e2e.yml`'s `on.pull_request.paths` from `scripts/gate_registry.json`, after which the path-list edit formerly owned by SA112e becomes a registry append. The board has zero merge-order edges. Consequently **SA122b's umbrella folded into SA122b-5** (Finding 11 is now retired by that single ticket, not by an umbrella) and **SA112e folded into SA112f**, so the SA112 chain is `b→c→d→f` — four children, not six — and the critical path shortens to `SA117e-4 → SA112b→c→d→f → SA140 → SA96-PUBLISH` (as of 2026-08-14 it is preceded by `SA146`; see [docs/technical/roadmap.md](docs/technical/roadmap.md)). SA115a closed 2026-08-12; Track 2 is complete. (d) **2026-08-12, superseding every "still open" statement above about Finding 11: SA122b-5 closed and Finding 11 is RESOLVED** — see the dated reconciliation entry below. The registry append formerly owned by SA112e is now `SA143` on Track 1, so the SA112 chain is `b→c→d→f`.
- 2026-07-29 — `quality-baseline-monotonicity-unenforced` (former Finding 12): **RESOLVED** by SA121; measurement and permission are now distinct artifacts. Closure detail, the arch-option rationale, and the superseded 2026-07-28 narrowing record are in [CHANGELOG.md](CHANGELOG.md).
- 2026-07-26 — Prior question “accept dormant module files?”: **answered yes** by SA105; it enabled Finding 10's resolution and is retired. “First new domain/consumer?” remains unanswered and is carried above.

Lenses scanned with no additional qualifying finding: observability, public API/versioning, runtime concurrency, cryptography/security, performance/scalability, dependency pinning, and supply chain. Static source analysis found no severe non-structural red flag requiring a separate section.
