# Tech Audit — Codebase-Wide Defect Sweep

> **Audit snapshot:** 2026-08-28 · **Prior pass:** 2026-08-22 (reconciled 2026-08-27 at `602f4be3`) · **Branch:** `v88` · **HEAD:** `48e0a62a`

## Orientation summary

QuickScale is a Python 3.14 / Poetry **code-generator and scaffolding platform**: a Click CLI, a Django-6 project generator, twelve shipped first-party modules (`teams` remains a source-less placeholder), and apply/recovery/DR tooling. First-party Python is ~294 non-test modules across `quickscale_core`, `quickscale_modules`, `quickscale_cli`, `scripts`, and `quickscale_devtools`.

**Deployment realities** (every finding names one):

1. **The maintainer workstation** — `make quality`, `make ci`, the CLI, `quickscale_devtools`. Solo-maintainer repo.
2. **Hosted CI** — `ci.yml`, `publish.yml`, `e2e.yml`, `nightly-bypassrls.yml`.
3. **The generated project** — Django 6 + PostgreSQL 18 + Vite/React on Railway, multi-tenant with FORCE RLS under a NOSUPERUSER/NOBYPASSRLS runtime role. Internet-facing.
4. **Local generated-project development** — `docker-compose.yml`, `settings/local.py`, `DEBUG=True`, no published database port.

**Entry points and trust boundaries.** Untrusted input reaches the system through generated-project HTTP routes (DRF viewsets, the blog/forms/social public surfaces, two signed webhook endpoints, three `csrf_exempt` views), markdown authored into `Post.content` / `Listing.description`, operator-supplied restore archives fed to `pg_restore`, and `quickscale.yml` / module manifests consumed by the CLI. The Django admin (backup creation, restore, `TenantModelAdmin`) is an authenticated operator surface, not a public one. The CLI and `quickscale_devtools` are operator-trusted.

**Tooling baseline.** ruff (`py314`, E/W/F/I/N/UP/D), mypy, pylint duplication-only, vulture, radon, pytest 9 with `--cov-fail-under=90`, pre-commit, a declared gate registry, checksum-pinned Trivy v0.74.0 dependency scanning, Bandit 1.9.4, AST gates, and a monotonic quality baseline with a waiver ledger.

**Scope decision (§2e).** The delta since the prior pass is **5 commits / 3 files**, of which the only code change is a test file. A delta-driven sweep would therefore have been nearly empty. This pass instead spends its depth on the surfaces the two prior passes **sampled by signature but never read as code**: the orgs tenancy and request-scoping machinery in full, the `forms` cross-tenant operator surface, the billing credit ledger, the DR engine's lock and orchestration layers, and `quickscale_devtools/beta_migration.py` — which both prior passes explicitly skipped.

**Oracle list (§2g) — the project's own declared invariants, hunted as defect classes:**

- **Fail-Hard Principle** (`decisions.md:725`, `:807-831`) — every configuration error, missing dependency, and invalid runtime state raises; no silent fallbacks, never substitute a default. This file is the declared SSOT for found-not-yet-fixed violations (`decisions.md:670`, `:831`).
- **Tenant reads/writes stay organization-scoped**; `all_objects` is an operator escape hatch, not a scoping bypass; `operator_access` grants **read-only** cross-tenant visibility and requires a verified `is_superuser` caller inside `transaction.atomic()` (`organizations.md:729`).
- **No shipped runtime BYPASSRLS path**; `QUICKSCALE_ALLOW_BYPASSRLS=1` is an explicit dev/test opt-out only; Django `is_superuser` does not infer database-level access (`organizations.md:587`).
- **Launcher one-shot command-env contract** — `QUICKSCALE_PRIVILEGED_COMMAND` / `RUNTIME_DATABASE_URL` are set as inline command prefixes, **never** as persistent environment configuration (`decisions.md`, Launcher One-Shot Command-Env Contract).
- **Project interpreter only** (`ruff.toml:8-11`).
- **Raw credential values MUST NOT be persisted** in `quickscale.yml`, `.quickscale/state.yml`, or `BackupArtifact` rows; Stripe keys stay environment-only.
- **Quality baseline monotonicity**; **CSRF-exempt endpoints carry an alternate integrity check**.

**Delta classification (re-run mode, §2f).** `602f4be3..HEAD` = 5 commits, 3 files, 362 insertions / 705 deletions. *Review-tracked:* `8a8f364b`, `cc80a5f2` (roadmap/handoff docs), `74ba3c55` (merge). *Side-channel — read in full:* `990f660f` "Refactor assertions in ticket context consistency test" and `48e0a62a` "streamline ticket context consistency tests and remove unused variables" — two refactor-shaped messages carrying a **net removal of ~60 assertions** from a conformance test. That is the §4.VIII signature and it was read hunk by hunk; adjudication in *Clean sweeps* and the reconciliation log.

### Coverage statement (§3.11)

**Read in full:** the entire `602f4be3..HEAD` diff including every test hunk; `quickscale_modules/orgs/.../tenancy.py` (registry, `_FORCE_RLS_FORWARD_SQL`/`_REVERSE_SQL`, `apply_force_rls`, `refresh_force_rls_policies`, the equality-trigger helpers, and the conformance helpers `is_tenant_model` → `check_tenant_model_isolation`); `managers.py`; `middleware.py`; `permissions.py`; `checks.py`; `apps.py`; `public_context.py`; the `current_org.py` GUC layer (`_tenant_context`, `org_scope`, `_make_priming_execute_wrapper`, `install_priming_wrapper`, `operator_access`); `quickscale_modules/forms/.../views.py:140-520` and `throttles.py`; `quickscale_modules/billing/.../services.py` credit-ledger paths; `quickscale_modules/blog/.../feeds.py`; `quickscale_core/.../dr_engine/_lock.py` (entire file); the `dr_engine/orchestration.py` destructive sites, `create_backup` lock section, and admin restore staging pipeline; `advisory_lock.py` acquire/release/stale; `quickscale_devtools/beta_migration.py` mutation and guard sites; `scripts/security_suppressions.json`; the `start.sh.j2` privileged-command contract.

**Sampled:** the 53-site `getattr(settings, …, <default>)` census across all modules; subprocess-timeout and `rmtree`/`unlink` censuses across all first-party source; `poetry.lock` pins for the security-relevant packages; CLI destructive paths.

**Skipped:** the React theme component bodies and `scripts/` gate internals (both read at depth by the prior passes this cycle); generated-project migrations; pylint/radon/vulture internals.

**Audit tools run (read-only):** `git log` / `git diff` / `git rev-parse` over the delta; CPython 3.14 for the two empirical checks below. No scanner was re-run this pass — the Trivy/Bandit gate is CI-owned and its ledger was read rather than re-executed.

**Empirical checks run (§1e):** none in this status-only reconciliation. The root-finalized release
evidence and closure rationale are archived in [CHANGELOG.md](../../CHANGELOG.md).

---

## Summary table

| ID | Sev | Category | Title | Effort | Confidence | Status |
|---|---|---|---|---|---|---|

**Counts derived from remaining live findings:** S1 **0** · S2 **0** · S3 **0** · S4 **0** ·
**Total 0 open.** No numbered live finding remains.

---

## Findings

No live findings remain after the closure reconciliation.

---

## Per-subsystem verdicts

| Subsystem | What was read | Verdict |
|---|---|---|
| Commit delta `602f4be3..HEAD` | all 3 files, production and test hunks, in full | Clean — the assertion removals are a defensible narrowing; see *Clean sweeps* and the reconciliation log |
| orgs — tenant registry & RLS SQL | `tenancy.py` registry, both policy templates, `apply_force_rls` / `revert_force_rls` / `refresh_force_rls_policies`, equality-trigger helpers, `is_tenant_model` → `check_tenant_model_isolation` | Clean after SA172 made forward application idempotent and metadata-derived; the write/read policy split remains correct — see *Clean sweeps* |
| orgs — request scoping | `managers.py`, `middleware.py`, `permissions.py`, `current_org.py` GUC layer, `public_context.py` | Clean — fail-closed at every branch examined; see *Clean sweeps* |
| orgs — boot guards | `apps.py` `ready()`, `checks.py` | Clean — one suspected finding refuted, see *Clean sweeps* |
| forms — operator surface | `views.py:140-520`, `throttles.py`, `models.py` settings helpers | Clean — superuser gating is consistent across queryset selection and `operator_access` wrapping |
| billing — credit ledger | `services.py` `debit_user`, `credit_user`, balance helpers | Clean — `transaction.atomic()` + `select_for_update()` + `F()` deltas, integer credits, no float money |
| blog — public read path | `feeds.py` | Clean (one watch item on the double `get_system_org()` resolution) |
| DR engine — locking | `_lock.py` in full; `advisory_lock.py` acquire/release/stale | Clean after the accepted inode-bound lock correction; the fcntl cooperation limitation remains an advisory risk |
| DR engine — orchestration | destructive sites, `create_backup` lock section, admin restore staging/upload pipeline | Clean; the upload path streams via `chunks()` — see *Notes* |
| devtools — beta migration | `beta_migration.py` mutation sites, TOML writer, identity replacement, git guard | Clean — the clean-worktree blocker at `:1457` is the reversal path; see *Clean sweeps* |
| Dependency & suppression hygiene | `poetry.lock` security-relevant pins; `scripts/security_suppressions.json` | Clean — all 7 remaining suppressions are accountable and unexpired, and no shared expiry cliff remains |

---

## Clean sweeps worth recording

- **The FORCE-RLS policy split enforces the documented read/write asymmetry.** `_FORCE_RLS_FORWARD_SQL` (`tenancy.py:505-527`) creates a `FOR ALL` policy requiring `current_org_id = organization_id` in both `USING` and `WITH CHECK`, plus a separate `FOR SELECT` policy that adds the `operator_access` OR clause. Because PostgreSQL applies UPDATE/DELETE policies conjunctively with the SELECT visibility check, `operator_access` genuinely cannot widen a write — matching the CR-SA14.5-001 comment and `organizations.md:729`. Both policies use the `NULLIF(current_setting(…, true), '')::uuid` form, so an unprimed GUC yields `NULL`, which never equals `organization_id` — fail-closed.
- **`TenantManager` is fail-closed by construction.** `managers.py:38-49`: no org in the ContextVar returns `.none()`, and `super_scope=True` is the only bypass. Verified as the default `objects` manager contract.
- **The GUC priming wrapper handles transaction-boundary reuse correctly.** `_make_priming_execute_wrapper` (`current_org.py:453-563`) memoises per transaction against the **outermost `Atomic` object reference** rather than `id()`, explicitly to defeat CPython address reuse (CR-SA42-001); the autocommit branch clears the memo and wraps each statement in a short `transaction.atomic()` so `SET LOCAL` and the tenant SQL share a scope. `_tenant_context` restores both the ContextVar and the prior GUC on exit via `SET LOCAL` rather than session-scoped `RESET` (CR-AF11-001).
- **`operator_access` is gated, audited, nesting-safe, and fails loudly outside a transaction.** `_get_operator_access` / `_set_operator_access` (`current_org.py:685-745`) raise `ImproperlyConfigured` on PostgreSQL when `connection.in_atomic_block` is false, so a `SET LOCAL` that would silently no-op is impossible (SA39). The context manager saves and restores the prior GUC. Its only HTTP-reachable consumer, `forms/views.py`, gates every use on `_is_superuser()` at both the queryset (`_get_org_bound_queryset:158-177`) and the wrapping (`_with_superuser_operator_access:180-200`), with non-superusers fail-closed to `.none()` when no org is active.
- **Org management routes bypass middleware resolution but not authorization.** `TenantMiddleware._is_org_management_path` lets `/orgs/<slug>/…` through unresolved, and `permissions._resolve_request_org` then resolves the org *from the slug* with no implicit trust — `user_has_org_role` performs the membership and role check. Every mutating view (`MemberListView`, `InviteView`, `RevokeInvitationView`, `OrgSettingsView`) declares `min_org_role = OrgRole.ADMIN`, and the MRO places `OrgRoleMixin.dispatch` after `LoginRequiredMixin`. Unknown segments under `/orgs/` fall through to org resolution rather than bypassing.
- **The `QUICKSCALE_PRIVILEGED_COMMAND` early return was investigated and refuted as a finding.** `apps.py` `ready()` returns before installing the priming wrapper, connecting the SA70 last-owner `pre_delete` backstop, and registering the SA1.3/SA1.4 system checks. Walked each consequence: during `migrate` the connection runs as the BYPASSRLS superuser so priming is moot; data migrations operate on historical model classes, which would not dispatch a `pre_delete` receiver registered against the real `OrganizationMembership` class even if it *were* connected; and the two skipped checks emit `Warning` only. No exposure. The env-var contract itself is honoured — `start.sh.j2:50,61` sets it as an inline command prefix alongside `RUNTIME_DATABASE_URL=""`, and it appears in neither `.env.j2` nor `docker-compose.yml.j2`.
- **The four privileged-command declarations currently agree.** The companion structural pass promoted `privileged-command-set-multi-owner` on 2026-08-28 after observing that `orgs/apps.py` claimed to be the SSOT while other deciders existed; SA174 corrects that claim and demotes the structural issue under the settled two-command decision. Adjudicated here for a *behavioural* divergence, which is what would make it a defect in this document's scope: `orgs/apps.py` `_PRIVILEGED_COMMANDS`, `quickscale_cli/.../development_commands.py` `_PRIVILEGED_DJANGO_COMMANDS`, generated `production.py.j2` `_KNOWN_PRIVILEGED_COMMANDS`, and the `migrate`/`createcachetable` branches in generated `start.sh.j2` all declare exactly `{"migrate", "createcachetable"}`. Unknown values fail closed in both enforcing validators (`production.py.j2` raises; `apps.py:_is_privileged_command` returns `False` and the BYPASSRLS guard runs). `development_commands.py` interpolates a caller-supplied command into the env var, but both validators reject unrecognised values, so it cannot widen the exemption. **No finding here** — the structural ownership question remains an armed watch item in the arch audit.
- **The billing credit ledger has no TOCTOU.** `debit_user` (`services.py:874-900`) opens `transaction.atomic()`, takes the balance row with `select_for_update()`, checks sufficiency, and applies the delta through `F("balance") + delta` — never a read-modify-write of a Python integer. Credits are `int`; no `FloatField` exists anywhere in first-party source and the only `Decimal` use is a display conversion (`billing/views.py:116`).
- **`beta_migration.py` gates its in-place mutations behind a clean git worktree.** `_check_clean_git_worktree` (`:933-972`) requires both "inside a work tree" and an empty `git status --porcelain`, and `_validate_in_place_report_boundary` (`:1457`) records it as a blocking check. That makes `git checkout` the reversal path for `_replace_text_in_file`'s global identity substitution and `_copy_path`'s `_remove_path`-then-copy, both of which operate on fixed known-file lists. `_write_validated_toml` (`:777-785`) parses the rewritten document before writing, refusing to emit invalid TOML.
- **Admin restore uploads stream rather than buffer.** `_iter_admin_restore_upload_chunks` (`orchestration.py:2579-2600`) prefers Django's `chunks()` generator and only falls back to a whole-`read()` when `chunks` is absent or yields nothing — not the live path for any real Django upload. `_stage_admin_restore_upload` hashes and sizes incrementally into a quarantined directory and rejects empty files.
- **The suppression ledger remains accountable.** SA170's dependency upgrade removed four resolved
  `sqlparse` CVE suppressions. All 7 remaining entries in `security_suppressions.json` carry an owner,
  rationale, `decision_ref`, and 2026-09-30 expiry.
- **The delta weakened no production invariant.** `990f660f` and `48e0a62a` remove ~60 assertions from `test_v88_ticket_context_consistency.py`, which is the §4.VIII signature — but every removed assertion pinned *documentation* state (roadmap prose, ticket dependency sets, merge positions, and this file's own finding counts and severities), not code behaviour. The removal is required by, not in tension with, `decisions.md:670`: this document is "live findings, not a ledger… no other artifact may pin its finding counts or IDs." The replacement `_assert_status_consumers_agree` **derives** counts from the roadmap instead of pinning literals, raises `AssertionError` with a diagnostic message instead of a bare `assert`, and the commit adds a new red-canary test (`test_v88_status_consumer_count_drift_is_expected_red_canary`) proving the check still fails on drift. Confirmed by grep that no test anywhere still reads `docs/others/tech-audit.md` or `arch-audit.md`.

---

## Structural smells

*(candidate inputs for the companion `deep-architectural-audit` — not findings here)*

- **Two independent filesystem-lock implementations.** `AdvisoryLock` (`advisory_lock.py`) and the DR backup lock (`dr_engine/_lock.py`) remain separate implementations after the release-accepted atomic, inode-bound correction. This is a non-defect consolidation watch question: revisit only if a third implementation appears, behavior or platform support diverges, or both public contracts can no longer be preserved independently.
- **Conformance gates assert policy presence, not policy content.** `table_has_force_rls` (`tenancy.py:1623-1677`) accepts any table where `relrowsecurity` and `relforcerowsecurity` are true and `COUNT(*) FROM pg_policies >= 1`. A table carrying a permissive `USING (true)` policy would pass every isolation check the repository runs. The registry-driven parity tests constrain *which* tables are enrolled but not *what* their policies say.

---

## Tooling gaps

| Gap | Would have caught | Recommendation |
|---|---|---|
| RLS policy assertions check existence, not predicate text | Structural smell #3 | Extend the isolation conformance suite to assert the policy `qual`/`with_check` text from `pg_policies` matches the `_FORCE_RLS_FORWARD_SQL` template for each enrolled table — this pins the operator-read/tenant-write split as a gate rather than a comment |

---

## Notes (watch items)

**Carried forward from prior passes (re-verified, unchanged):**

- **Integration-branch CI** — hosted CI does not run on pushes to the release branch (`ci.yml` triggers on `main`/`develop` and PRs to `main`). Accepted solo-maintainer workflow choice.
- **Generator lock generation** — missing Poetry, timeout, or nonzero lock generation warns and lets generation finish by explicit usability policy; downstream apply/install stays fail-loud. Deliberate.
- **`_HOST_DEPENDENT_PATHS` accountability is implemented but not yet closeout-accepted.** The retained SA165 A-C product documents the `.env` rationale and the second/third-entry escalation rule. Keep this note live until a release verdict covers the settled product candidate; SA165 owns the subsequent documentation closeout.
- **The isolation-gate skip is identity-bound in retained product bytes.** The retained SA165 A-C product narrows authorization to the two `PENDING_REMEDIATION` test identities and carries a red negative control. Keep this note live until the settled product candidate receives its release verdict; SA165 owns the subsequent documentation closeout.
- **The generated healthcheck checks nothing** (`urls.py.j2:39-45` returns `HttpResponse("OK")`; `railway.json.j2:11` points Railway's deploy gate at it). Not promoted — the DB-free property is deliberate and documented, and production settings already raise at import when `RUNTIME_DATABASE_URL` is absent. Revisit if a separate readiness endpoint is added.
- **Generated local-development credentials are documented but not yet closeout-accepted.** The retained SA165 A-C product adds the rendered `OPERATIONS.md` warning that predictable local credentials must not survive into a shared environment. Keep this note live until the settled product candidate receives its release verdict; SA165 owns the subsequent documentation closeout.
- **Cross-tenant count fallbacks in CRM serializers** (`serializers.py:133-136`, `:311-312`, `:409-410`, `:541-545`) use `all_objects` when the ContextVar is unset. Not a finding: under the supported NOBYPASSRLS role, FORCE RLS with an unset GUC returns zero rows. Re-examine if a BYPASSRLS serving mode is ever supported. **This pass adds:** the identical pattern is pervasive in `billing/services.py`, which uses `all_objects` with explicit `organization=` filters throughout. Same adjudication, same trigger for re-examination.
- **`flush_empty_consolidated_sections` now fails hard in retained product bytes.** The retained SA165 A-C product raises `StateError` for corrupt and non-mapping YAML roots before any write and preserves the original bytes. Keep this note live until the settled product candidate receives its release verdict; SA165 owns the subsequent documentation closeout.
- **Atomic state writes are rename-atomic but not durable** (`state_schema.py:352-356`, `:405-407`) — no `fsync()`. Standard workstation trade-off.

**New this pass:**

- **`blog/feeds.py` resolves the System org twice, with opposite error handling.** `__call__` (`:31-34`) swallows any exception into `org = None`, but `items()` (`:44-46`) calls `Organization.objects.get_system_org()` again *unguarded*. If the first call failed because of a corrupt System org row — `OrganizationManager._validate_system_org` raises `RuntimeError` by design — the feed enters fail-closed scope and then raises unhandled during item rendering, turning a fail-closed empty feed into a 500. Narrow trigger (a corrupt singleton), and the broad `except Exception` is itself the Fail-Hard shape worth noting.
- **`table_has_force_rls` queries `pg_class` / `pg_policies` without schema qualification** (`tenancy.py:1650-1670`, matching on `relname` and `tablename`). Single-schema deployments are unaffected; recorded so a future schema-per-tenant option does not inherit an ambiguous check.

---

## Reconciliation log

- 2026-08-21 — **TA1–TA62**: closure detail, later structural-cause closure, and superseded cross-reference notes remain archived in [CHANGELOG.md](../../CHANGELOG.md) and version control, as recorded by the prior pass.
- 2026-08-21 — Prior watch items *integration-branch CI* and *generator lock generation*: **still-open, accepted / owned**. Carried forward unchanged.
- 2026-08-27 — **Closed-item closure narratives are archived.** TA63, TA65, TA69, the SA150 local-wheelhouse watch item, the dependency-vulnerability and security-static-analysis tooling gaps, and the six adjudicated arch-audit red-flag leads are all closed; detail lives in [CHANGELOG.md](../../CHANGELOG.md).
- 2026-08-27 — **Quality-baseline watch item retired.** Both recorded warning regressions are gone; monotonicity passes.
- 2026-09-10 — **TA67 and TA68 retired by the root-finalized green SA160 release evidence.** Closure detail and immutable release provenance are retained in [CHANGELOG.md](../../CHANGELOG.md); no live finding remains.
- 2026-09-04 — **TA70** `container-status-substring-match`: **retired by SA170**. The ordered serial and concurrent release campaigns both passed with exact Core/CLI cleanup and preserved standing PostgreSQL state. Final and retained-partial evidence is archived in [CHANGELOG.md](../../CHANGELOG.md).
- 2026-09-02 — **Watch item closed:** the four `sqlparse` suppressions were retired by a real dependency upgrade to 0.6.0 during SA170 convergence; the vulnerability gate is green and the shared 2026-09-30 expiry no longer exists. No finding was opened or closed by this.
- 2026-08-28 — **TA71** `backup-lock-stale-clear-toctou`: **new (S3).** Found by the §3.3 lifecycle walk over the backups deployable rather than by the delta.
- 2026-09-05 — **TA71** `backup-lock-stale-clear-toctou`: **retired by the release-accepted SA171 lock correction.** SA176 preserved the serialized `"_acquisition_token"` key while renaming its Python constant, Bandit B105 and the full `make ci` gate are green, and release acceptance is restored without a suppression. Inode-bound reclamation and acquisition-bound release identity are archived in [CHANGELOG.md](../../CHANGELOG.md); the separate-lock question is retained only as the non-defect structural watch item above.
- 2026-08-28 — **TA72** `force-rls-apply-idempotency-claim`: **new (S4).**
- 2026-09-05 — **TA72** `force-rls-apply-idempotency-claim`: **retired by SA172.** The forward
  template now drops both named policies with `IF EXISTS` before recreating them; a live PostgreSQL
  regression applies the helper twice and verifies RLS remains enabled and forced with exactly the
  write and operator-read policies present. The adjacent refresh watch item is also retired because
  table names now come from each registered model's `_meta.db_table`. The separate predicate-text
  tooling gap and structural smell remain open under post-v88 SA177.
- 2026-08-28 — **No prior closure claims required verification (§2f.3)**: the prior pass carried three open findings and claimed no new closures in the delta window, so there was no closure testimony to check against code. All three prior IDs were nonetheless re-verified at their anchors, as logged above.
- 2026-08-28 — **Fix-regression pass (§3.6)**: not applicable — the delta contains no fix for any prior finding. The two behavioural commits are test-only.
- 2026-08-28 — **Test-integrity diff (§3.7)**: the delta's ~60 removed assertions were read hunk by hunk against the "did any test get weaker?" question and **cleared**. Every removed assertion pinned documentation state, not code behaviour; the removal of the assertions over `arch-audit.md` and `tech-audit.md` is mandated by `decisions.md:670`; the replacement derives its counts from the roadmap rather than pinning literals, upgrades bare `assert`s to diagnostic `AssertionError`s, and adds a red-canary test proving drift still fails. No `skip`/`xfail` was added, no tolerance widened, no mock replaced a real dependency. Full adjudication in *Clean sweeps*.
- 2026-09-05 — **Ticket splits, no finding changed.** TA72's owner was carrying a two-line forward-template
  repair bundled with a predicate-text conformance assertion over every enrolled table. The repair stays with
  **SA172**; the assertion moves to post-v88 **SA177**, so the *"RLS policy assertions check existence, not
  predicate text"* tooling gap and its related structural smell **stay open** and are no longer claimed by
  TA72's closure. Separately, the four watch notes above keep their live status unchanged, but their
  retirement step was assigned to **SA179** at this checkpoint; the consolidation below supersedes that assignment.
  No finding was opened, closed, promoted, or demoted.
- 2026-09-05 — **SA165 retained-partial reconciliation:** the retained A-C product addresses `flush_empty_consolidated_sections`, the identity-blind isolation skip, `_HOST_DEPENDENT_PATHS`, and generated local credentials. Review of the five-file product candidate and the final release verdict remain outstanding, so the four notes remain live and SA165 remains open. SA165 now absorbs SA179's subsequent documentation closeout; the documents recording the review remain outside the frozen product evidence. Historical verdicts and continuation evidence are retained in [CHANGELOG.md](../../CHANGELOG.md); current scheduling is maintained in the [roadmap](../technical/roadmap.md).

*Categories swept with no qualifying finding this pass: injection sinks of every kind, authentication and authorization, secrets handling, cryptographic use, multi-tenant isolation, data handling and serialization, resources and I/O, performance, dependency and build hygiene, CLI destructive-path safety, and the frontend, library/SDK, code-generator, and infrastructure-as-code archetype lenses.*
