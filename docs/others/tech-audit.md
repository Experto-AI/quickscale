# Tech Audit — Codebase-Wide Defect Sweep

> **Audit snapshot:** 2026-09-15 · **Prior pass:** 2026-08-28 (reconciled through 2026-09-11 at `87e8c96a`) · **Branch:** `v89` · **Findings reconciled at:** `b9e072f4`

## Orientation summary

QuickScale is a Python 3.14 / Poetry **code generator and scaffolding platform**. It has a Click CLI, a Django 6 project generator, twelve shipped first-party modules (`teams` is still a source-less placeholder), and apply/recovery/DR tooling. Modules reach generated projects through `git subtree` split branches, which `scripts/publish_module.py` pushes.

**Deployment realities** (every finding names one):

1. **The maintainer workstation.** `make ci`, `make ci-e2e`, the new `make release-gate`, `make publish-modules`, the CLI, and `quickscale_devtools`. One maintainer, several worktrees.
2. **Hosted CI.** `ci.yml` now calls `nightly-bypassrls.yml` as a reusable job on every push and PR. The nightly schedule is disabled.
3. **The generated project.** Django 6 + PostgreSQL 18 + Vite/React on Railway, internet-facing and multi-tenant, with FORCE RLS under a NOSUPERUSER/NOBYPASSRLS runtime role. **New this pass:** `start.sh` is now the Dockerfile `CMD`. On every boot it creates or updates that runtime role from `RUNTIME_DB_PASSWORD`, then migrates. `quickscale deploy railway` generates that password.
4. **Local generated-project development.** `docker-compose.yml` with `runserver`. `quickscale manage` now clears `RUNTIME_DATABASE_URL` only for sanctioned privileged commands.

**Entry points and trust boundaries.** Unchanged from the prior pass: generated-project HTTP routes, the two signed webhooks, the three `csrf_exempt` views, markdown content, restore archives, and `quickscale.yml` / manifests. **New operator surfaces in the delta:**

- The `start.sh migrate_billing_to_orgs` argv branch.
- The Railway variables that `quickscale deploy railway` writes (`RUNTIME_DB_ROLE`, `RUNTIME_DB_PASSWORD`, `RUNTIME_DATABASE_URL`).
- `apply --split-refs-from-branches`.
- `publish_module.py --publish-all`, which force-pushes every outdated split branch.

**Tooling baseline.** ruff, mypy, pylint (duplication only), vulture, radon, pytest 9 with a 90% coverage floor, pre-commit (now with a `commit-msg` stage), 12 registered gates, Trivy dependency scanning, Bandit 1.9.4, and AST/conformance gates. `check-commit-testimony` is now hosted-only. Its accepted testimony narrowed to any `vN[.N…]` token.

**Scope decision (§2e).** This is re-run mode. The delta `87e8c96a..HEAD` is 569 commits. Most are synthetic subtree-split mirrors. The first-party tree diff is 125 non-doc files (+2,275 / −656). The whole production diff was read, plus every test hunk. The rest of the depth went to three things:

- The arch audit's hand-off red flag (`purge_organization` × Stripe).
- A lifecycle walk of the generated deployable's new boot sequence.
- Taint traces through the client-IP resolver, the blog API auth path, and both webhook signature checks.

**Oracle list (§2g).** The project's own declared invariants, hunted as defect classes:

- **Fail-Hard Principle** (`decisions.md` → Fail-Hard): every configuration error, missing dependency, or invalid runtime state raises. No silent fallback ever substitutes a default.
- **Tenant data stays organization-scoped.** `all_objects` is an operator escape hatch. `operator_access` is read-only and superuser-gated.
- **No shipped runtime BYPASSRLS path.** `QUICKSCALE_ALLOW_BYPASSRLS=1` is a dev/test opt-out only.
- **Launcher one-shot command-env contract.** `QUICKSCALE_PRIVILEGED_COMMAND` / `RUNTIME_DATABASE_URL=""` are inline prefixes, never persistent configuration.
- **Raw credential values are never persisted** in `quickscale.yml`, state, or `BackupArtifact` rows. Stripe keys stay environment-only.
- **Force-with-lease publication.** `EXPECTED_REMOTE_SHA` must come from a real observation, and `--publish-outdated` stays disabled because it pushed with bare `--force` (SA117 Phase 4).
- **Teardown policy** (`decisions.md:921`): `on_delete=PROTECT` plus an explicit, GDPR-capable `purge_organization`.
- **Quality-baseline monotonicity**; **CSRF-exempt endpoints carry an alternate integrity check**.

**Delta classification (re-run mode, §2f).** Almost every behavioural commit in the window is **side-channel**. None carries a descriptive trail:

- Seven commits share the release title `v0.88.0: QuickScale 0.88.0` while changing product or controls: `461796ce`/`b8ca6283` runtime-role creation and Railway variables; `a85f29ff` Dockerfile `CMD`; `296afa0e` `--publish-all`; `d73155d1` security-gate scope; `f4cb7964` bypassrls CI; `54aea5ab` publish workflow.
- `b29d9a29` "v88 fix: make ci-e2e fixes" (48 files) added a third privileged command and changed `_run_docker_exec_command`'s privilege model.
- Four `docs:` commits carry code: `5a6d1f4f` (`apply_command.py`, `publish_module.py`), `74d18f48` (compat gate, `version_tool.sh`), and `18d6084a`/`2e2a932a` (testimony gate).
- `b9e072f4` "v89: version bump".

All of these were read hunk by hunk, production and test.

### Coverage statement (§3.11)

**Read in full:**

- The entire first-party `87e8c96a..HEAD` diff, except docs, CHANGELOG, and version-string-only hunks. That includes `start.sh.j2`, `Dockerfile.j2`, `production.py.j2`, `OPERATIONS.md.j2`, `deployment_commands.py`, `development_commands.py`, `apply_command.py`, `railway_utils.py`, `orgs/apps.py`, `migrate_billing_to_orgs.py` (whole file), `publish_module.py`, `check_commit_testimony.py`, `check_module_core_compatibility.py`, `check_security_gates.py`, `check_gate_parity.py`, `sync_ci_gate_jobs.py`, `provision_ci_postgres.sh`, `test_isolation_conformance.sh`, `version_tool.sh`, all four workflows, and the Makefile.
- Every test hunk in the delta.
- `purge_organization.py` (whole file).
- `_publish_module` and `_run_release_gates`.
- `railway_utils.get_railway_variables` / `set_railway_variables_batch`.
- `current_org.get_client_ip`.
- `blog/views.py` `authenticate_blog_api_request`, `_get_authorization_token`, `upload_media_api`.
- `notifications/views.py` and the signature check in `notifications/services.py:724-753`.
- `billing/services.py` `cancel_current_subscription` and `_handle_invoice_paid_event`.

**Sampled:**

- The sibling management commands (`forms_anonymize_submissions`, `forms_seed_presets`, `promote_to_saas`), for the `objects`-vs-`all_objects` class that the `migrate_billing_to_orgs` fix repaired.
- `production.py.j2` connection settings.
- `poetry.lock` coverage of the generated project's runtime dependencies.
- The prior watch-item anchors.

**Skipped:** React theme bodies, generated-project migrations, the DR engine (read at depth last pass, untouched by the delta), and gate-script internals beyond the delta hunks.

**Audit tools run (read-only):** `git log` / `git diff` / `git show` / `git rev-list` over the delta, and `poetry run python` 3.14.6 for the checks below. No scanner was re-run; Trivy and Bandit are CI-owned.

**Empirical checks run (§1e):**

- **(1)** `secrets.compare_digest('tokén', 'token')` raises `TypeError: comparing strings with non-ASCII characters is not supported`. This confirms TA78.
- **(2)** `pytest -p no:cacheprovider -o addopts= --no-cov` over the nine test files that still carry a `0.88.0` literal: **13 failed / 993 passed** at `b9e072f4`. This confirms TA76. For example, `test_mixed_versions_blocks_on_first_mismatch` reports `...rsion 0.89.0.` vs `...rsion 0.88.0.`. The working tree was unchanged afterwards.
- **(3) Refuted chain:** "a guessed Postgres service name gives an unresolvable `RUNTIME_DATABASE_URL`, and the DB-free healthcheck then promotes a broken deploy." `orgs/apps.py` `_check_rls_role` opens a connection inside `ready()`, and `start.sh` step 7 imports the WSGI app under `set -e`. A bad runtime URL therefore fails the boot before Gunicorn starts. It is not promoted.

---

## Summary table

| ID | Sev | Category | Title | Effort | Confidence | Status |
|---|---|---|---|---|---|---|
| TA73 `purge-org-orphans-live-stripe-subscription` | S2 | Data handling / money | `purge_organization` deletes current Stripe-backed subscriptions without cancelling or refusing | Small | High (code); Medium (post-purge webhook path) | open — new |
| TA77 `publish-all-self-observed-lease` | S3 | Concurrency / publication safety | `--publish-all` feeds its own just-observed SHA to the lease, so it can overwrite unseen remote commits | Small | Medium | open — new |
| TA78 `compare-digest-non-ascii-500` | S4 | Error handling | A non-ASCII token or signature header crashes two auth checks with a 500 | Trivial | High (executed) | open — new |

⚡ = quick win (Trivial-effort S2/S3).

**Counts derived from the table:** S1 **0** · S2 **1** · S3 **1** · S4 **1** · **Total 3 open.**

---

## Findings

### Finding 1: `purge_organization` orphans live Stripe subscriptions

- **ID:** TA73 `purge-org-orphans-live-stripe-subscription`
- **Severity:** S2. The impact is financial and legal: a customer keeps being charged with no local account or record. The trigger is one realistic operator act, purging a paying org (the command is the declared GDPR teardown path, `decisions.md:921`). It needs no other precondition. It lives in the generated project (reality 3) and violates the Fail-Hard oracle: it destroys the only local handle on a live external obligation without refusing.
- **Category:** IX Data handling (money path).
- **Confidence:** High that local rows are deleted with no Stripe interaction. Medium on the exact post-purge webhook failure mode, which needs a Stripe test-mode run to confirm.
- **Location:**
  - `quickscale_modules/orgs/src/quickscale_modules_orgs/management/commands/purge_organization.py:193-212` (`_DELETE_SPECS` billing entries).
  - `:514-530` (`Command._delete_owned_rows`).
  - `:404-459` (`Command._purge_by_uuid`, which raw-deletes the `Organization` row holding `stripe_customer_id`).
- **Defect:** The purge runs `Subscription.all_objects.filter(organization=org).delete()` for every status, including `ACTIVE`/`TRIALING`/`PAST_DUE` rows with a non-empty `stripe_subscription_id`. It then deletes the org row. It never calls `cancel_current_subscription` (`billing/services.py:736`), and it never refuses when a current Stripe-backed subscription exists.
- **Failure scenario:**
  1. An operator honours an account-deletion request with `purge_organization --organization-id <uuid>`.
  2. The dry run shows `Subscriptions: 1`, and the purge succeeds with "has been purged."
  3. Stripe keeps renewing the subscription. Each `invoice.paid` webhook reaches `_handle_invoice_paid_event` (`services.py:1044`), and `_resolve_organization_for_invoice` can no longer map the customer to an organization.
  4. The webhook errors, Stripe retries, and the customer is billed every period until someone notices in the Stripe dashboard.
- **Evidence:** `_DELETE_SPECS` lists `{"app_label": "quickscale_modules_billing", "model_name": "Subscription", "filter_key": "organization", ...}`, and `_delete_owned_rows` executes `qs.delete()` with no status or Stripe-id inspection. No `pre_delete`/`post_delete` receiver exists in `billing/src` (grep).
- **Refutation:** Three candidates were checked, and none survived:
  - (a) A billing delete signal that cancels remotely: none exists.
  - (b) Documented operator guidance to cancel billing before purging: none in `decisions.md`, the module READMEs, CHANGELOG, or the roadmap.
  - (c) A test blessing the behaviour: `test_purge_organization_with_billing_rows` (`test_management_commands.py:1213`) asserts an `ACTIVE` subscription with `stripe_subscription_id="sub_billing_purge"` is deleted. That pins *local* row deletion, the teardown decision, but says nothing about the external subscription. It is a test with a blind spot, not a decision to leave customers billed.

  Hand-off note: the lead came from `arch-audit.md` → *Red flags*. It was re-verified independently here.
- **Fix:** Before the atomic block in `_purge_by_uuid`, refuse with `CommandError` when the org has any `Subscription` whose `status in Subscription.current_statuses()` and whose `stripe_subscription_id` is non-empty. List the ids and tell the operator to cancel first. Optionally add an explicit `--billing-cancelled-out-of-band` acknowledgement flag. Keep the Stripe call out of the purge transaction. **Effort:** Small.
- **Verification:** Extend `test_purge_organization_with_billing_rows` with a variant: an `ACTIVE` subscription with a Stripe id must raise and leave all rows and the org intact. A `CANCELED` subscription must still purge.
- **Deliberate?** The teardown decision covers local rows only; nothing addresses the external subscription.
- **Age:** Long-standing. The billing entries predate this window.

### TA77 `publish-all-self-observed-lease` · S3 · `scripts/publish_module.py:1208-1253`

**Defect:** `_publish_all` calls `_observe_remote_branch_sha` (a live `ls-remote`) and passes the result straight to `_publish_module` as `expected_remote_sha`. The lease then only guards the milliseconds between observation and push. It never checks that the observed remote tip is an ancestor of the local split. Nearby text contradicts the design: the helper's docstring warns that feeding an unseen SHA "would satisfy the lease while clobbering a remote commit nobody in this process ever saw", and `_publish_module` (`:1002`) relies on the same lease with no ancestry check.

**Failure scenario:**

1. The maintainer publishes 0.89 module splits from one worktree.
2. Later they run `make publish-modules` from an older worktree still on an authoritative tag. `_run_release_gates` passes, because `_check_release_authoritative` is per-checkout.
3. Every newer split branch is force-overwritten with older bytes.
4. Consumers of `apply --split-refs-from-branches` then verify stale module code.

`git subtree split` is deterministic, so a legitimate re-publish always fast-forwards. That makes the ancestry check safe to add.

**Fix:** Before each push, require `git merge-base --is-ancestor <remote_sha> <local_split_sha>`. On divergence, stop the batch and name the module. **Effort:** Small. **Confidence:** Medium: the divergence scenario is inferred, not executed. Reality 1.

### S4

- **TA78** `compare-digest-non-ascii-500`: `quickscale_modules/blog/src/quickscale_modules_blog/views.py:351` (`secrets.compare_digest(token, configured_token)`) and `quickscale_modules/notifications/src/quickscale_modules_notifications/services.py:752` (`hmac.compare_digest(signature or "", …)`). Either check raises `TypeError` on a non-ASCII `Authorization` token or signature header (executed). Unauthenticated callers get a 500 with a logged traceback instead of 401/403. The blog path needs `BLOG_API_TOKENS` configured; the notifications path needs a fresh timestamp. **Fix:** compare `.encode()` bytes, or reject non-ASCII input as invalid first.

---

## Per-subsystem verdicts

| Subsystem | What was read | Verdict |
|---|---|---|
| Commit delta `87e8c96a..HEAD` | full first-party production diff and every test hunk | TA77 remains open; test changes adjudicated in *Clean sweeps* |
| Generated boot sequence (`start.sh.j2`, `Dockerfile.j2`, `railway.json.j2`) | entire files; lifecycle walk boot → role → migrate → cache → superuser → WSGI → gunicorn | Clean. Role creation is identifier-safe, refuses a superuser or self role, and credentials stay off argv. Two watch items below |
| CLI deploy (`deployment_commands.py`, `railway_utils.py` variable helpers) | delta in full plus read/set helpers | Clean after live-state reconciliation and exact database-service selection |
| CLI dev (`development_commands.py`) | delta plus every `_run_docker_exec_command` caller | Clean. The privilege narrowing is correct and `manage` guards empty args at `:690` |
| orgs — privileged commands (`apps.py`, `migrate_billing_to_orgs.py`) | whole command, guard delta | Clean. See *Clean sweeps* |
| orgs — `purge_organization` | whole file | TA73 |
| Client identity / public auth (`get_client_ip`, blog API auth, notifications webhook) | functions in full | TA78; otherwise clean |
| Publication tooling (`publish_module.py`, `version_tool.sh`, compat gate) | delta plus `_publish_module`, `_run_release_gates` | TA77 |
| CI / gates (workflows, testimony, security gates, provisioning, isolation conformance) | delta in full | Clean as defects; one watch item and one tooling gap |

---

## Clean sweeps worth recording

- **All four privileged-command declarations still agree after gaining a third command.** `orgs/apps.py:36` `_PRIVILEGED_COMMANDS`, `development_commands.py:44` `_PRIVILEGED_DJANGO_COMMANDS`, and `production.py.j2:156` `_KNOWN_PRIVILEGED_COMMANDS` all declare `{"migrate", "createcachetable", "migrate_billing_to_orgs"}`. `start.sh.j2` uses `migrate` and `createcachetable` inline and exposes `migrate_billing_to_orgs` only as an exact single-argv one-shot (`:13-19`) that `exec`s and never reaches Gunicorn. Unknown argv exits 2. This supersedes the prior pass's "exactly two" clean sweep; the behaviour stays consistent.
- **`quickscale manage` no longer hands the superuser URL to every command.** Previously `_run_docker_exec_command` cleared `RUNTIME_DATABASE_URL` for *all* execs (`shell`, `createsuperuser`, arbitrary commands). Now it clears the URL only when `privileged_command` is in the sanctioned set, and it raises `ValueError` otherwise. This tightens the "No shipped runtime BYPASSRLS path" oracle for local development.
- **Runtime-role creation in `start.sh` is injection-safe and refuses dangerous targets.** Role and database names go through `psycopg2.sql.Identifier` and the password through `sql.Literal`, read from the environment, never argv. The step refuses when `RUNTIME_DB_ROLE` equals the `DATABASE_URL` login or names an existing superuser. `ALTER DEFAULT PRIVILEGES` covers tables that later migrations create under the same login.
- **The `migrate_billing_to_orgs` fix is complete across siblings.** The delta switched every billing lookup from fail-closed `objects` (always empty without an org context) to `all_objects`, and wrapped `handle` in `transaction.atomic`. The fix-regression pass looked for the same `objects`-in-command class in `forms_anonymize_submissions`, `forms_seed_presets`, and `promote_to_saas`. All scope correctly, through `operator_access` + `all_objects` for reads, `org_scope` for writes, or non-tenant models.
- **`get_client_ip` resolves the rightmost-N forwarded hop and fails closed.** `current_org.py:616-671`: settings are type-checked and raise when missing. A chain shorter than `TRUSTED_PROXY_COUNT` falls back to `REMOTE_ADDR`, never to the spoofable leftmost entry.
- **The blog API's `csrf_exempt` is paired correctly.** `authenticate_blog_api_request` (`blog/views.py:333-380`) applies `CsrfViewMiddleware.process_view` to every session-authenticated request. Only bearer-token requests skip CSRF, and they require staff.
- **Test-integrity diff: no weakening found.** Every removed assertion or skip in the delta was either replaced by a stricter one or tracks a real behaviour move:
  - `pytest.skip("network unavailable")` → a hermetic Poetry shim that asserts lock content and invocation.
  - The always-skipped `migrate_billing_to_orgs` tests now run in the BYPASSRLS lane, with a fixture that recreates nullable ownership. This exposed the `objects` bug.
  - The gunicorn-in-Dockerfile assertions moved to the start.sh `CMD`.
  - `PENDING_REMEDIATION` parametrizations → completed-remediation assertions over the AF12 pairs.
  - The isolation gate's empty-parameter exemption was deleted, so *any* skip now fails.
  - `bypass_rls` skip became deselect, but `ci.yml` now runs the bypass lane on every push/PR, and `provision_ci_postgres.sh` refuses to widen `QUICKSCALE_ALLOW_BYPASSRLS` into `GITHUB_ENV`.
- **Prior closures verified in code (§2f.3).**
  - TA72: `DROP POLICY IF EXISTS` precedes both policy creations (`tenancy.py:506-507`, `:532-533`).
  - TA71: the backup lock binds reclamation to `(st_dev, st_ino)` (`dr_engine/_lock.py:231-239`, `:269`).

---

## Structural smells

*(candidate inputs for the companion `deep-architectural-audit`, not findings here)*

- **Two independent filesystem-lock implementations.** `AdvisoryLock` and the DR backup lock remain separate. Carried forward as a non-defect consolidation watch question.
- **Conformance gates assert policy presence, not policy content.** `table_has_force_rls` (`tenancy.py:1633`) accepts any table with RLS enabled and forced and at least one policy. Still owned by post-v88 SA177.

---

## Tooling gaps

| Gap | Would have caught | Recommendation |
|---|---|---|
| RLS policy assertions check existence, not predicate text | Structural smell #2 | Assert `pg_policies.qual`/`with_check` against `_FORCE_RLS_FORWARD_SQL` per enrolled table (SA177) |
| Dependency gate never sees the generated project's runtime dependencies | Future CVEs in `gunicorn`, `whitenoise`, `dj-database-url` (none in root `poetry.lock`) | Add a Trivy pass over the hermetic generated-project lock the E2E lane already produces, or add those pins to a scanned dev group |
| No external-effect check on destructive org teardown | TA73 | Add a purge conformance test: for every `_DELETE_SPECS` model that carries an external provider id, the purge must refuse or reconcile |

---

## Notes (watch items)

**Carried forward from prior passes (re-verified, unchanged):**

- **Integration-branch CI.** `ci.yml` still triggers on `main`/`develop` pushes and PRs to `main`. Accepted solo-maintainer choice.
- **Generator lock generation** warns and continues by explicit usability policy. Deliberate.
- **The generated healthcheck checks nothing** (`urls.py.j2:39-45`; `railway.json.j2` `healthcheckPath`). Still not promoted. This pass confirmed boot-time `_check_rls_role` makes a broken runtime URL fail *before* the healthcheck can pass.
- **Cross-tenant count fallbacks** in CRM serializers (`serializers.py:133-136`) and `billing/services.py` use `all_objects` with explicit org filters. They are safe under NOBYPASSRLS. Re-examine if a BYPASSRLS serving mode is ever supported.
- **Atomic state writes are rename-atomic but not durable** (`schema/state_schema.py:356`, `:412`). No `fsync()`.
- **`blog/feeds.py` resolves the System org twice with opposite error handling** (`:33` guarded, `:45` unguarded).
- **`table_has_force_rls` queries `pg_class`/`pg_policies` without schema qualification.**

**New this pass:**

- **`start.sh` puts the runtime password in DDL text.** `ALTER/CREATE ROLE … PASSWORD '<literal>'` reaches the server as statement text. If that statement errors (`log_min_error_statement=error`) or the server uses `log_statement=ddl`, the password lands in PostgreSQL logs, which Railway surfaces in its dashboard. Not promoted: Railway's Postgres logging configuration was not verified, and success-path statements are not logged by default. A pre-hashed SCRAM verifier would remove the exposure.
- **Concurrent replica boot races `CREATE ROLE`.** With more than one replica on first deploy, two containers can both see the role absent. One fails "role already exists", exits under `set -e`, and restarts (`restartPolicyType: ON_FAILURE`); its next boot takes the `ALTER` branch. Self-healing, so not promoted.
- **Commit testimony now accepts any `vN[.N…]` token.** `ROADMAP_REFERENCE_RE` (`check_commit_testimony.py:31`) matches a release title such as `v0.88.0: QuickScale 0.88.0`. Seven behavioural commits in this window changed product, workflows, or gates with only that subject line. Governance, not a product defect; recorded because the side-channel classification (§2f) depends on commit messages carrying intent.
- **`migrate_billing_to_orgs` is privileged but effectively unreachable.** Under the clean-break migration policy, `organization_id` is `NOT NULL` on every current install; the tests have to drop the constraint to create migratable rows. The command still became a third privileged exemption plus a `start.sh` argv branch. Harmless while all validators agree; revisit if the command's scope grows.

---

## Reconciliation log

- 2026-08-21 — **TA1–TA62**: closure detail, later structural-cause closure, and superseded cross-reference notes remain archived in [CHANGELOG.md](../../CHANGELOG.md) and version control, as recorded by the prior pass.
- 2026-08-21 — Prior watch items *integration-branch CI* and *generator lock generation*: **still-open, accepted / owned**. Carried forward unchanged.
- 2026-08-27 — **Closed-item closure narratives are archived.** TA63, TA65, TA69, the SA150 local-wheelhouse watch item, the dependency-vulnerability and security-static-analysis tooling gaps, and the six adjudicated arch-audit red-flag leads are all closed; detail lives in [CHANGELOG.md](../../CHANGELOG.md).
- 2026-08-27 — **Quality-baseline watch item retired.** Both recorded warning regressions are gone; monotonicity passes.
- 2026-09-11 — **TA67 retired by SA160.** Reopening, remediation, and the green release aggregate
  at `87e8c96a` are archived in [CHANGELOG.md](../../CHANGELOG.md).
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
- 2026-08-28 — **Test-integrity diff (§3.7)**: the delta's ~60 removed assertions were read hunk by hunk against the "did any test get weaker?" question and **cleared**. Every removed assertion pinned documentation state, not code behaviour; the removal of the assertions over `arch-audit.md` and `tech-audit.md` is mandated by `decisions.md:670`; the replacement derives its counts from the roadmap rather than pinning literals, upgrades bare `assert`s to diagnostic `AssertionError`s, and adds a red-canary test proving drift still fails. No `skip`/`xfail` was added, no tolerance widened, no mock replaced a real dependency.
- 2026-09-05 — **Ticket splits, no finding changed.** TA72's owner was carrying a two-line forward-template
  repair bundled with a predicate-text conformance assertion over every enrolled table. The repair stays with
  **SA172**; the assertion moves to post-v88 **SA177**, so the *"RLS policy assertions check existence, not
  predicate text"* tooling gap and its related structural smell **stay open** and are no longer claimed by
  TA72's closure. Separately, the four watch notes above keep their live status unchanged, but their
  retirement step was assigned to **SA179** at this checkpoint; the consolidation below supersedes that assignment.
  No finding was opened, closed, promoted, or demoted.
- 2026-09-11 — **Four SA165 watch notes retired.** `_HOST_DEPENDENT_PATHS` accountability, the
  identity-bound isolation skip, generated local-credential documentation, and fail-hard
  `flush_empty_consolidated_sections` were held open only for SA165's closeout. SA165 closed on maintainer
  decision on 2026-09-09, so the notes are archived in [CHANGELOG.md](../../CHANGELOG.md).
- 2026-09-05 — **SA165 retained-partial reconciliation:** the retained A-C product addresses `flush_empty_consolidated_sections`, the identity-blind isolation skip, `_HOST_DEPENDENT_PATHS`, and generated local credentials. Review of the five-file product candidate and the final release verdict remain outstanding, so the four notes remain live and SA165 remains open. SA165 now absorbs SA179's subsequent documentation closeout; the documents recording the review remain outside the frozen product evidence. Historical verdicts and continuation evidence are retained in [CHANGELOG.md](../../CHANGELOG.md); current scheduling is maintained in the [roadmap](../technical/roadmap.md).
- 2026-09-15 — **Re-run over `87e8c96a..b9e072f4`.** 569 commits; the first-party tree diff (125 non-doc files) and every test hunk were read. No prior finding was open, so there is no still-open carry-forward.
- 2026-09-15 — **Closure verification (§2f.3):** TA71 and TA72 closures **confirmed present in code** at the anchors listed in *Clean sweeps*. TA67 and TA70 closures rest on the archived release-acceptance evidence. Their fix sites were not touched by this delta, so there was nothing to re-open. **Regressed: none.**
- 2026-09-15 — **Fix-regression pass (§3.6):** the one fix in the window, `migrate_billing_to_orgs` moving from `objects` to `all_objects` plus `@transaction.atomic`, was read adversarially and its siblings swept. **Cleared.**
- 2026-09-15 — **Test-integrity diff (§3.7):** the removed skips and assertions in the delta were adjudicated as replaced-by-stricter or behaviour-moved (see *Clean sweeps*). **No weakening.**
- 2026-09-15 — **Arch-audit red flag** *`purge_organization` can orphan live Stripe subscriptions*: independently verified and **promoted to TA73 (S2)**. The dismissed PEP 758 syntax lead was re-confirmed dismissed on Python 3.14.6.
- 2026-09-15 — **TA73** `purge-org-orphans-live-stripe-subscription`: **new (S2).**
- 2026-09-15 — **TA74** `railway-redeploy-rotates-secret-key`: **new (S3).** Long-standing (`dcb558ce`, v0.60.0), made visible by the delta's password-reuse contrast.
- 2026-09-15 — **TA75** `railway-runtime-role-vars-fail-open`: **new (S3).** Introduced by `461796ce` / `b8ca6283`.
- 2026-09-15 — **TA76** `version-bump-breaks-literal-tests`: **new (S3).** Introduced by `b9e072f4`; executed.
- 2026-09-15 — **TA76** `version-bump-breaks-literal-tests`: **retired by SA181.** Current-version expectations now derive from the repository or package version, so the next version bump requires no matching test edit; archived in [CHANGELOG.md](../../CHANGELOG.md).
- 2026-09-15 — **TA77** `publish-all-self-observed-lease`: **new (S3).** Introduced by `296afa0e`.
- 2026-09-15 — **TA78** `compare-digest-non-ascii-500`: **new (S4).** Long-standing; executed.
- 2026-09-15 — **Clean sweep superseded:** the prior "four privileged-command declarations agree on exactly `{migrate, createcachetable}`" became "agree on three", after `b29d9a29` added `migrate_billing_to_orgs` at all four stations. Consistent; no finding.
- 2026-09-15 — **Chain pass (§3.9) ran.** One candidate chain was refuted (TA75 guessed service × DB-free healthcheck; see empirical check 3). TA75 × TA74 share a re-run trigger but compound only into disruption, not exposure. No chain raised a severity.
- 2026-09-16 — **TA74** `railway-redeploy-rotates-secret-key`: **retired by SA184.** Re-runs now reuse the service's `SECRET_KEY`, generating one only on first deploy; archived in [CHANGELOG.md](../../CHANGELOG.md).
- 2026-09-16 — **TA75** `railway-runtime-role-vars-fail-open`: **retired by SA184.** Unreadable Railway state and ambiguous PostgreSQL listings now fail the deploy instead of inventing values; archived in [CHANGELOG.md](../../CHANGELOG.md).

*Categories swept with no qualifying finding this pass: injection sinks (role DDL, publication git argv, testimony regex), authorization on the delta's new surfaces, secrets on argv or in logs (beyond the start.sh watch item), multi-tenant isolation in the privileged-command changes, CI secret and escape-hatch propagation, resources and I/O, performance, and the code-generator and IaC archetype lenses.*
