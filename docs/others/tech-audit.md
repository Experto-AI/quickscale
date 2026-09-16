# Tech Audit — Codebase-Wide Defect Sweep

> **Audit snapshot:** 2026-09-15 · **Branch:** `v89` · **Range audited:** `87e8c96a..b9e072f4`

## Orientation summary

QuickScale is a Python 3.14 / Poetry **code generator and scaffolding platform**. It has a Click CLI, a Django 6 project generator, twelve shipped first-party modules (`teams` is still a source-less placeholder), and apply/recovery/DR tooling. Modules reach generated projects through `git subtree` split branches, which `scripts/publish_module.py` pushes.

**Deployment realities** (every finding names one):

1. **The maintainer workstation.** `make ci`, `make ci-e2e`, the new `make release-gate`, `make publish-modules`, the CLI, and `quickscale_devtools`. One maintainer, several worktrees.
2. **Hosted CI.** `ci.yml` now calls `nightly-bypassrls.yml` as a reusable job on every push and PR. The nightly schedule is disabled.
3. **The generated project.** Django 6 + PostgreSQL 18 + Vite/React on Railway, internet-facing and multi-tenant, with FORCE RLS under a NOSUPERUSER/NOBYPASSRLS runtime role. **New this pass:** `start.sh` is now the Dockerfile `CMD`. On every boot it creates or updates that runtime role from `RUNTIME_DB_PASSWORD`, then migrates. `quickscale deploy railway` generates that password.
4. **Local generated-project development.** `docker-compose.yml` with `runserver`. `quickscale manage` now clears `RUNTIME_DATABASE_URL` only for sanctioned privileged commands.

**Entry points and trust boundaries.** Current boundaries include generated-project HTTP routes, the two signed webhooks, the three `csrf_exempt` views, markdown content, restore archives, and `quickscale.yml` / manifests. **Current operator surfaces:**

- The explicit, acknowledged `migrate_billing_to_orgs` recovery invocation.
- The Railway variables that `quickscale deploy railway` writes (`RUNTIME_DB_ROLE`, `RUNTIME_DB_PASSWORD`, `RUNTIME_DATABASE_URL`).
- `apply --split-refs-from-branches`.
- `publish_module.py --publish-all`, which force-pushes every outdated split branch.

**Tooling baseline.** ruff, mypy, pylint (duplication only), vulture, radon, pytest 9 with a 90% coverage floor, pre-commit (now with a `commit-msg` stage), 12 registered gates, Trivy dependency scanning, Bandit 1.9.4, and AST/conformance gates. `check-commit-testimony` is now hosted-only. Its accepted testimony narrowed to any `vN[.N…]` token.

**Scope decision (§2e).** This is re-run mode. The delta `87e8c96a..b9e072f4` is 569 commits. Most are synthetic subtree-split mirrors. The first-party tree diff is 125 non-doc files (+2,275 / −656). The whole production diff was read, plus every test hunk. The rest of the depth went to three things:

- The arch audit's hand-off red flag (`purge_organization` × Stripe).
- A lifecycle walk of the generated deployable's new boot sequence.
- Taint traces through the client-IP resolver, the blog API auth path, and both webhook signature checks.

**Oracle list (§2g).** The project's own declared invariants, hunted as defect classes:

- **Fail-Hard Principle** (`decisions.md` → Fail-Hard): every configuration error, missing dependency, or invalid runtime state raises. No silent fallback ever substitutes a default.
- **Tenant data stays organization-scoped.** `all_objects` is an operator escape hatch. `operator_access` is read-only and superuser-gated.
- **No shipped BYPASSRLS serving path.** `QUICKSCALE_ALLOW_BYPASSRLS=1` is limited to dev/test and the explicitly acknowledged billing recovery invocation; it is never a runtime-serving mode.
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

- The entire first-party `87e8c96a..b9e072f4` diff, except docs, CHANGELOG, and version-string-only hunks. That includes `start.sh.j2`, `Dockerfile.j2`, `production.py.j2`, `OPERATIONS.md.j2`, `deployment_commands.py`, `development_commands.py`, `apply_command.py`, `railway_utils.py`, `orgs/apps.py`, `migrate_billing_to_orgs.py` (whole file), `publish_module.py`, `check_commit_testimony.py`, `check_module_core_compatibility.py`, `check_security_gates.py`, `check_gate_parity.py`, `sync_ci_gate_jobs.py`, `provision_ci_postgres.sh`, `test_isolation_conformance.sh`, `version_tool.sh`, all four workflows, and the Makefile.
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

**Empirical check (§1e):** `secrets.compare_digest('tokén', 'token')` raises
`TypeError: comparing strings with non-ASCII characters is not supported`. This confirms TA78.

---

## Summary table

| ID | Sev | Category | Title | Effort | Confidence | Status |
|---|---|---|---|---|---|---|
| TA78 `compare-digest-non-ascii-500` | S4 | Error handling | A non-ASCII token or signature header crashes two auth checks with a 500 | Trivial | High (executed) | open — new |

⚡ = quick win (Trivial-effort S2/S3).

**Counts derived from the table:** S1 **0** · S2 **0** · S3 **0** · S4 **1** · **Total 1 open.**

---

## Findings

### S4

- **TA78** `compare-digest-non-ascii-500`: `quickscale_modules/blog/src/quickscale_modules_blog/views.py:351` (`secrets.compare_digest(token, configured_token)`) and `quickscale_modules/notifications/src/quickscale_modules_notifications/services.py:752` (`hmac.compare_digest(signature or "", …)`). Either check raises `TypeError` on a non-ASCII `Authorization` token or signature header (executed). Unauthenticated callers get a 500 with a logged traceback instead of 401/403. The blog path needs `BLOG_API_TOKENS` configured; the notifications path needs a fresh timestamp. **Fix:** compare `.encode()` bytes, or reject non-ASCII input as invalid first.

---

## Per-subsystem verdicts

| Subsystem | What was read | Verdict |
|---|---|---|
| Commit delta `87e8c96a..b9e072f4` | full first-party production diff and every test hunk | Clean; test changes adjudicated in *Clean sweeps* |
| Generated boot sequence (`start.sh.j2`, `Dockerfile.j2`, `railway.json.j2`) | entire files; lifecycle walk boot → role → migrate → cache → superuser → WSGI → gunicorn | Clean. Role creation is identifier-safe, refuses a superuser or self role, and credentials stay off argv. Two watch items below |
| CLI deploy (`deployment_commands.py`, `railway_utils.py` variable helpers) | delta in full plus read/set helpers | Clean after live-state reconciliation and exact database-service selection |
| CLI dev (`development_commands.py`) | delta plus every `_run_docker_exec_command` caller | Clean. The privilege narrowing is correct and `manage` guards empty args at `:690` |
| orgs — privileged commands (`apps.py`, `migrate_billing_to_orgs.py`) | whole command, guard delta | Clean. See *Clean sweeps* |
| orgs — `purge_organization` | whole file | Clean for live Stripe-backed subscriptions; the broader teardown tooling gap remains below |
| Client identity / public auth (`get_client_ip`, blog API auth, notifications webhook) | functions in full | TA78; otherwise clean |
| Publication tooling (`publish_module.py`, `version_tool.sh`, compat gate) | delta plus `_publish_module`, `_run_release_gates` | Clean after the fast-forward ancestry check before each push |
| CI / gates (workflows, testimony, security gates, provisioning, isolation conformance) | delta in full | Clean as defects; remaining watch items and tooling gaps are listed below |

---

## Clean sweeps worth recording

- **All four privileged-command declarations agree on the permanent two-command set.** `orgs/apps.py` `_PRIVILEGED_COMMANDS`, `development_commands.py` `_PRIVILEGED_DJANGO_COMMANDS`, and `production.py.j2` `_KNOWN_PRIVILEGED_COMMANDS` all declare `{"migrate", "createcachetable"}`. `start.sh.j2` uses exactly those inline prefixes, rejects every argv with exit 2, and a cross-station regression now fails if a declaration diverges. `migrate_billing_to_orgs` remains an unprivileged recovery command.
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
---

## Structural smells

*(candidate inputs for the companion `deep-architectural-audit`, not findings here)*

- **Two independent filesystem-lock implementations.** `AdvisoryLock` and the DR backup lock remain separate. Carried forward as a non-defect consolidation watch question.

---

## Tooling gaps

| Gap | Would have caught | Recommendation |
|---|---|---|
| Dependency gate never sees the generated project's runtime dependencies | Future CVEs in `gunicorn`, `whitenoise`, `dj-database-url` (none in root `poetry.lock`) | Add a Trivy pass over the hermetic generated-project lock the E2E lane already produces, or add those pins to a scanned dev group |
| No exhaustive external-provider conformance check for destructive org teardown | Future provider-ID obligations beyond the shipped Stripe-subscription refusal | For every `_DELETE_SPECS` model that carries an external provider id, verify that purge refuses or reconciles it |

---

## Notes (watch items)

**Current standing watch items:**

- **Integration-branch CI.** `ci.yml` still triggers on `main`/`develop` pushes and PRs to `main`. Accepted solo-maintainer choice.
- **Generator lock generation** warns and continues by explicit usability policy. Deliberate.
- **The generated healthcheck checks nothing** (`urls.py.j2:39-45`; `railway.json.j2` `healthcheckPath`). Still not promoted. This pass confirmed boot-time `_check_rls_role` makes a broken runtime URL fail *before* the healthcheck can pass.
- **Cross-tenant count fallbacks** in CRM serializers (`serializers.py:133-136`) and `billing/services.py` use `all_objects` with explicit org filters. They are safe under NOBYPASSRLS. Re-examine if a BYPASSRLS serving mode is ever supported.
- **Atomic state writes are rename-atomic but not durable** (`schema/state_schema.py:356`, `:412`). No `fsync()`.
- **`blog/feeds.py` resolves the System org twice with opposite error handling** (`:33` guarded, `:45` unguarded).

**Additional current watch items:**

- **`start.sh` puts the runtime password in DDL text.** `ALTER/CREATE ROLE … PASSWORD '<literal>'` reaches the server as statement text. If that statement errors (`log_min_error_statement=error`) or the server uses `log_statement=ddl`, the password lands in PostgreSQL logs, which Railway surfaces in its dashboard. Not promoted: Railway's Postgres logging configuration was not verified, and success-path statements are not logged by default. A pre-hashed SCRAM verifier would remove the exposure.
- **Concurrent replica boot races `CREATE ROLE`.** With more than one replica on first deploy, two containers can both see the role absent. One fails "role already exists", exits under `set -e`, and restarts (`restartPolicyType: ON_FAILURE`); its next boot takes the `ALTER` branch. Self-healing, so not promoted.
- **Commit testimony now accepts any `vN[.N…]` token.** `ROADMAP_REFERENCE_RE` (`check_commit_testimony.py:31`) matches a release title such as `v0.88.0: QuickScale 0.88.0`. Seven behavioural commits in this window changed product, workflows, or gates with only that subject line. Governance, not a product defect; recorded because the side-channel classification (§2f) depends on commit messages carrying intent.
- **Billing backfill recovery remains available only by explicit acknowledgement.** Under the clean-break migration policy, `organization_id` is `NOT NULL` on every current install; the tests have to drop the constraint to create migratable rows. `migrate_billing_to_orgs` is not a sanctioned exemption or launcher argv mode. Revisit only if a supported data shape makes the command operationally necessary again.

---

*Categories swept with no qualifying finding this pass: injection sinks (role DDL, publication git argv, testimony regex), authorization on the delta's new surfaces, secrets on argv or in logs (beyond the start.sh watch item), multi-tenant isolation in the privileged-command changes, CI secret and escape-hatch propagation, resources and I/O, performance, and the code-generator and IaC archetype lenses.*
