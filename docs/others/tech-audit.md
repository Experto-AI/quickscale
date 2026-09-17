# Tech Audit — Codebase-Wide Defect Sweep

> **Audit snapshot:** 2026-09-17 · **Branch:** `v89` · **Range audited:** `b9e072f4..98b6c455`
> **Prior snapshot:** 2026-09-15 (`87e8c96a..b9e072f4`, no open findings)

## Orientation summary

QuickScale is a Python 3.14 / Poetry **code generator and scaffolding platform**: a Click CLI, a
Django 6 project generator, twelve shipped first-party modules, and apply/recovery/DR tooling.
Modules reach generated projects through `git subtree` split branches pushed by
`scripts/publish_module.py`.

**Deployment realities** (every finding names one):

1. **The maintainer workstation.** `make ci`, `make ci-e2e`, `make release-gate`,
   `make publish-modules`, the CLI, `quickscale_devtools`, and — new this pass — the
   `beta_migrate.py` donor/recipient migration tool. One maintainer, several worktrees.
2. **Hosted CI.** `ci.yml` calls `nightly-bypassrls.yml` as a reusable job on every push and PR.
   Eleven hosted gate jobs now, up from ten; the nightly schedule stays disabled.
3. **The generated project.** Django 6 + PostgreSQL 18 + Vite/React on Railway, internet-facing
   and multi-tenant, FORCE RLS under a NOSUPERUSER/NOBYPASSRLS runtime role. `start.sh` is the
   Dockerfile `CMD`; on every boot it creates or updates the runtime role from
   `RUNTIME_DB_PASSWORD`, then migrates.
4. **Local generated-project development.** `docker-compose.yml` with `runserver`.

**Entry points and trust boundaries.** Generated-project HTTP routes, the two signed webhooks, the
three `csrf_exempt` views, markdown content, restore archives, and `quickscale.yml` / manifests.
Operator surfaces: `purge_organization`, the retired `migrate_billing_to_orgs` recovery command,
the Railway variables `quickscale deploy railway` writes, `apply --split-refs-from-branches`, and
`publish_module.py --publish-all`.

**Tooling baseline.** ruff, mypy, pylint (duplication only), vulture, radon, pytest 9 with a 90%
coverage floor, pre-commit with a `commit-msg` stage, **14** registered gates (the new
`check-beta-migration-smoke`), Trivy dependency scanning, Bandit 1.9.4, and AST/conformance gates.
`check_gate_parity.py` verifies registry ↔ Makefile ↔ `ci.yml` ↔ `check_ci_locally.sh` agreement;
its 240 tests were run this pass and pass. **Security tooling that fails the build:** Trivy
(dependency), Bandit (SAST), the CSRF-exempt gate, the org-context primitives gate, and the
security static-analysis gate all run as blocking hosted jobs.

**Scope decision (§2e).** Re-run mode. The delta `b9e072f4..98b6c455` is 34 commits / 121 files
(+15,348 / −2,840); the non-doc first-party tree is 100 files. The whole production diff was read
plus every test hunk. Depth went to four places: the unified runtime-role provisioning
(`98b6c455`, the newest and least-soaked commit), the new contract-vintage CLI gate, the
marker-only tenant classification rewrite in `tenancy.py`, and the publication ancestry hardening.

**Oracle list (§2g).** Hunted as defect classes:

- **Fail-Hard Principle** — every configuration error, missing dependency, or invalid runtime
  state raises; no silent fallback substitutes a default.
- **Tenant data stays organization-scoped.** `all_objects` is an operator escape hatch;
  `operator_access` is read-only and superuser-gated.
- **No shipped BYPASSRLS serving path.** `QUICKSCALE_ALLOW_BYPASSRLS=1` is dev/test and
  acknowledged recovery only, never runtime serving.
- **Launcher one-shot command-env contract.** `QUICKSCALE_PRIVILEGED_COMMAND` /
  `RUNTIME_DATABASE_URL=""` are inline prefixes, never persistent configuration.
- **Raw credential values are never persisted** in `quickscale.yml`, state, or `BackupArtifact`
  rows.
- **Force-with-lease publication.** `EXPECTED_REMOTE_SHA` must come from a real observation.
- **Teardown policy** — `on_delete=PROTECT` plus an explicit, GDPR-capable `purge_organization`.
- **Quality-baseline monotonicity**; **CSRF-exempt endpoints carry an alternate integrity check**.

**Data-sensitivity context (§2i).** The generator repository itself holds no customer data and no
live credential. The **generated project** handles: authentication credentials and session
material; per-tenant business data under RLS; Stripe customer and subscription identifiers (keys
stay environment-only); and the `RUNTIME_DB_PASSWORD` that `quickscale deploy railway` generates
and Railway stores. The classes that travel outside the primary store are the runtime password
(Railway variables, and — see watch items — potentially PostgreSQL DDL logs) and Stripe
identifiers (present in `purge_organization` refusal messages, which are operator-facing).
Every leak-shaped severity below is assigned against this list.

**Delta classification (re-run mode, §2f).** All 34 commits carry a descriptive one-line subject
and **no body, ticket, or review trail**; two reference SA180/SA182 inline. By §2f.2 the whole
window is **side-channel** and got elevated scrutiny: production *and* test hunks were read in
full. Notably, none of these commits ran through hosted CI — `ci.yml` triggers only on
`main`/`develop` pushes and PRs to `main`, and this work is all on `v89`.

### Coverage statement (§3.12)

**Read in full:** the entire first-party `b9e072f4..98b6c455` diff except docs, CHANGELOG, and
version-string-only hunks — including `runtime_database.py` (new), `start.sh.j2`, `db/init.sql.j2`,
`production.py.j2`, `generator.py`, `contract_vintage.py` (new), `deployment_commands.py`,
`railway_utils.py`, `apply_command.py`, `module_commands.py`, `development_commands.py`,
`status_command.py`, `publish_module.py`, `git_utils.py`, `tenancy.py`, `checks.py`, `apps.py`,
`purge_organization.py`, `migrate_billing_to_orgs.py`, `check_tenant_isolation.py`,
`report_rendering.py`, `gate_registry.json`, `sync_ci_gate_jobs.py`, all workflow diffs, and every
test hunk. Also read whole: `authenticate_blog_api_request`, `_verify_webhook_signature`,
`_force_rls_policy_mismatches` and its comparators, `refresh_force_rls_policies`,
`push_split_branch`, `_require_fast_forward`, `_execute_in_place` and its step handlers,
`_install_verification_shims`.

**Sampled:** `beta_migration.py` (7,289 lines) — read at its subprocess, filesystem-mutation, and
in-place-pipeline sites rather than end to end; `check_beta_migration_smoke.py` at its fixture,
shim, probe, and assertion sites; the module HTML template refactor across blog/crm/listings.

**Skipped:** React theme bodies, generated-project migrations, the DR engine (untouched by the
delta), and gate-script internals beyond the delta hunks.

**Audit tools run (read-only):** `git log` / `diff` / `show` / `rev-list` over the delta;
`ast.parse` on `railway_utils.py`. No scanner was re-run; Trivy and Bandit are CI-owned.

**Empirical checks run (§1e), with results:**

- Rendered `db/init.sql.j2` and `start.sh.j2` with the real generator context — **valid SQL and
  valid Python**; the new `{% for %}` loops emit only harmless blank lines.
- `pytest quickscale_core/tests/test_privileged_command_contract.py` — **5 passed**.
- `pytest scripts/test_gate_parity.py` — **240 passed**; the new gate is consistent across
  registry, Makefile, `ci.yml`, and `check_ci_locally.sh`.
- `python scripts/check_beta_migration_smoke.py` — **passed** (exit 0).
- `check_contract_vintage` against the shipped `orgs` manifest: `project_contract=None` → 1 module
  behind; `0.88.0` → 1 behind; `0.89.0` → 0 behind. This is the evidence under Finding 1.
- `_normalize_pg_policy_expression` against four candidate `pg_policies` deparsings — matches the
  three conforming forms, rejects `true`.
- Jinja2 default-`Undefined` behaviour for `{{ x }}`, `{% for %}`, and `| join` — **all render
  empty silently**. Feeds Tooling gap T1.
- **Refuted candidate:** `except TimeoutError, FileNotFoundError:` (`railway_utils.py:484`) and
  `except ValueError, AttributeError:` (`manifest/schema.py:84`) read as Python 2 syntax. `ast.parse`
  succeeds — PEP 758 makes unparenthesised `except` tuples valid, and `pyproject.toml` pins
  `requires-python = ">=3.14,<3.15"` with every CI matrix entry on 3.14. Not a finding.

**Residual risk (§8.1).** This was a static read plus side-effect-free experiments on the
maintainer workstation. It did **not** exercise a real Railway deploy, a real PostgreSQL 18 server,
a multi-replica boot, or an end-to-end `beta_migrate.py --continue-after-checkpoint` run against a
genuine beta site. The silence of this report therefore does not license any conclusion about
runtime behaviour of the generated container under concurrency, about how Railway's managed
PostgreSQL logs DDL, or about `beta_migration.py`'s 7,289 lines outside the sites named above.

---

## Machine-readable finding index

```yaml
- id: beta-migration-apply-contract-vintage-block
  severity: S3
  category: "VI. Error handling and operability (cross-feature contract gap)"
  title: "beta_migrate in-place continuation invokes `quickscale apply` without the contract-vintage acknowledgement it now requires"
  effort: Trivial
  confidence: High
  status: open
  reality: "1 — maintainer workstation"
  chain: []
```

---

## Summary table

| ID | Sev | Category | Title | Effort | Confidence | Status |
|---|---|---|---|---|---|---|
| `beta-migration-apply-contract-vintage-block` | S3 | Operability / cross-feature contract | in-place beta migration halts at `quickscale apply` on any pre-0.89.0 recipient | Trivial | High | open |

**Counts:** S1 = 0 · S2 = 0 · S3 = 1 · S4 = 0. One quick win (Trivial-effort S3).

---

## Findings

### Finding 1 — in-place beta migration halts at `quickscale apply` on any pre-0.89.0 recipient

- **ID:** `beta-migration-apply-contract-vintage-block`
- **Severity:** S3. Deployment reality **1 (maintainer workstation)**. The trigger is the tool's
  only intended use, so reachability is high, but the consequence is a recoverable workflow stop
  with an actionable diagnostic, behind a clean-worktree preflight — not data loss. One
  precondition (the recipient has loadable state recording a contract below `0.89.0`), and for a
  beta site that precondition holds by construction. Violates no declared oracle item; this is a
  coordination gap between two features that landed in the same window.
- **Category:** VI — Error handling and operability (cross-feature contract gap).
- **Confidence:** High — the gate's arithmetic was executed directly (see Evidence); the absence of
  any acknowledgement in the caller was confirmed by grep; the recipient's role was confirmed from
  the tool's own CLI help.
- **Location:** `quickscale_devtools/src/quickscale_devtools/beta_migration.py:6818`
  (`_execute_quickscale_apply`), reached from `:7183` in `_execute_in_place`. The gate it trips is
  `quickscale_cli/src/quickscale_cli/commands/apply_command.py:4015` and `:4136`
  (`enforce_shipped_contract_vintage`).
- **Defect:** `882b5cf6` made `quickscale apply` refuse an existing project whose recorded
  `project_contract` is below every installed module's declared `contract_vintage.minimum` — now
  `0.89.0` for `orgs` — unless `--acknowledge-contract-vintage` is passed. The in-place beta
  migration shells out to a bare `["quickscale", "apply"]`, and `beta_migration.py` contains no
  reference to `contract_vintage`, `project_contract`, or the acknowledgement flag.
- **Failure scenario (reproducer):** Take a beta site generated at 0.88.0 or earlier, so
  `.quickscale/state.yml` records `project_contract: "0.88.0"` (or omits it entirely — a legacy
  project read through from `config.yml`). Run
  `make beta-migrate-in-place DONOR=<fresh-scaffold> RECIPIENT=<beta-site> CONTINUE=1`. Steps 1–4
  succeed and **mutate the recipient working tree**: managed infrastructure files are copied,
  `pyproject.toml` and `frontend/package.json` are merged, and `quickscale.yml` is rewritten with
  the donor-only modules. Step 5, `run-quickscale-apply`, then exits non-zero:
  `enforce_shipped_contract_vintage` prints the three `orgs` adoption steps and raises
  `click.Abort()`. `_execute_quickscale_apply` raises `ValueError("quickscale apply failed with
  exit code 1 …")`; `_execute_in_place` sets `phase="in-place-partial"`, `status="blocked"`, records
  the blocker, and skips `copy-post-apply-react-surfaces` and `run-verification-stack`. The
  migration cannot complete on any recipient it was built for.
- **Evidence:**
  - `beta_migration.py:625` — *"Run the in-place workflow: donor is a fresh scaffold and
    **recipient is the existing beta site**."*
  - `beta_migration.py:6818` — `subprocess.run(["quickscale", "apply"], cwd=report.recipient.path, …)`
  - `grep -n "contract_vintage\|project_contract\|acknowledge" beta_migration.py` → no matches.
  - Executed against the shipped `orgs` manifest (`contract_vintage.minimum: "0.89.0"`):
    `project_contract=None → modules_behind=1`; `'0.88.0' → 1`; `'0.89.0' → 0`.
  - The only step that touches recipient state before apply,
    `_execute_update_quickscale_config` (`:6757`), rewrites `quickscale.yml` modules only and never
    sets `project_contract` (which is written solely by `apply_command.py:2472`, *after* the gate).
- **Refutation:** Four attempts, none survived. (a) *Is the gate skipped for a stateless
  recipient?* `enforce_contract_vintage` returns early only when `load_state()` yields `None`; a
  beta site has state, and `load_state` read-through-imports legacy `config.yml` when
  `state.yml` is thin — either way `project_contract` resolves to `None` → `(0,)` → behind.
  (b) *Does an earlier step raise the contract?* No — traced all four preceding handlers.
  (c) *Is there a blessing?* `docs/planning/beta-site-migration.md` documents the in-place
  continuation order at lines 43, 412, and 871 and never mentions the contract-vintage gate or the
  flag; the acknowledgement is documented only for hand-typed `apply`/`update`/`deploy railway`
  (`user_manual.md:368`, `:604`, `railway.md:94`). (d) *Does a test pin it?* The new smoke gate
  covers in-place continuation but installs a shim that makes `quickscale apply` exit 0
  unconditionally (`check_beta_migration_smoke.py:151-156`), so it cannot observe the gate.
- **Fix:** Decide the policy and encode it at the one callsite. Either (i) pass
  `--acknowledge-contract-vintage` in `_execute_quickscale_apply` — defensible, because the
  in-place flow's own `copy-managed-infrastructure-files` step *is* the automation of the adoption
  steps the gate asks for, and the donor is a fresh scaffold by definition — or (ii) add an
  explicit preflight check that reads the recipient's `project_contract` against the shipped
  manifests and blocks *before* any mutation, with a message naming the adoption steps. Option (ii)
  is the better shape: it moves the refusal ahead of the four mutating steps. **Effort: Trivial.**
- **Verification:** Promote the reproducer to an assertion in the smoke gate: generate the
  in-place recipient fixture with `project_contract="0.88.0"`, let the real `quickscale apply` run
  (drop `quickscale` from `SHIM_NAMES`, or make the shim forward to the real CLI), and assert the
  continuation reaches `status="ready"`. That single change also closes Tooling gap T2.
- **Fix risk:** Option (i) weakens the gate for one automated caller — acceptable only if the
  infrastructure-copy step genuinely covers all three `orgs` adoption steps, which should be
  checked against `module.yml` before choosing it. Option (ii) has no dependents: it adds a refusal
  on a path that already refuses, only earlier. Neither touches data already written.
- **Detection signal:** Today this shows up as a beta-migration report with
  `phase: "in-place-partial"`, `status: "blocked"`, and a blocker string containing
  `quickscale apply failed with exit code 1` plus `project contract … is behind`. Nothing else
  would surface it — the smoke gate is green (verified this pass) and hosted CI never ran these
  commits. After the fix, the smoke-gate assertion above is the recurring signal.
- **Deliberate?** None found. No comment, doc line, or test acknowledges the interaction.
- **Age:** Fresh. The gate landed in `882b5cf6` ("v89: enforce contract vintage boundaries") and
  the beta-migration execution path in `f1a434a5`/`a97b5788`, all inside this 34-commit window.
  Neither commit references the other.

---

## Entry-point × safeguard matrix (§3.5)

Cells name the layer that supplies the safeguard. `—` = not applicable to this entry point.
`n/a¹` = maintainer-workstation tool, single trusted operator.

| Entry point | Authn | Authz | Input validation | Size / rate limit | Timeout | Idempotency | Error shape | Audit record |
|---|---|---|---|---|---|---|---|---|
| Blog API (`csrf_exempt` + bearer) | `authenticate_blog_api_request` | staff check + `_enforce_csrf` for session auth | `_validate_blog_image_upload` | `_enforce_blog_api_rate_limit` (per-IP, 429 + `Retry-After`) | Django/gunicorn | — | JSON 401/403/429 | `logger.warning` on missing user |
| Notifications webhook | `_verify_webhook_signature` (HMAC, now bytes) | signature is the authorization | timestamp + payload parse | framework | framework | signature replay window | `NotificationWebhookSignatureError` | module logging |
| Module HTML views (blog/crm/listings) | Django session | `org_scope` / `TenantManager` | Django forms | — | framework | — | Django | — |
| Generated `start.sh` (container CMD) | `DATABASE_URL` superuser | refuses self-role and superuser targets (`:79`, `:84`) | `sql.Identifier` / `sql.Literal` | — | — | `CREATE`/`ALTER` branch is re-runnable | `set -e`, exit 2 on argv | stdout only |
| Generated `db/init.sql` | Postgres init as `POSTGRES_USER` | `NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE` | `_quote_identifier` | — | — | `IF NOT EXISTS` guard | init fails the container | `quickscale.init_complete` flag |
| `purge_organization` | management command | `_guard_reserved_org` + **new** `_guard_live_stripe_subscriptions` | UUID required for destructive path; `--slug` is preflight-only | — | — | tombstone → no-op rerun | `CommandError` | tombstone row in same transaction |
| `migrate_billing_to_orgs` | management command | **new** `_require_explicit_recovery_connection` (env ack + BYPASSRLS/SUPERUSER role probe) | `_collect_unmigratable_row_messages` | — | — | idempotent backfill | `CommandError` | stdout report |
| `check_tenant_isolation` | management command | read-only | marker discovery | — | — | read-only | exit code | stdout report |
| `quickscale apply` | n/a¹ | **contract-vintage gate** (`:4015`, `:4136`) | `validate_config` | — | — | recovery ledger / checkpoints | `click.Abort` | `.quickscale/state.yml` |
| `quickscale update` | n/a¹ | contract-vintage gate (`module_commands.py:1480`) | manifest load | — | — | diff preview | `click.ClickException` | state write |
| `quickscale deploy railway` | Railway CLI session | contract-vintage gate (`deployment_commands.py:717`) | exact single-Postgres-service selection; fail-hard variable reads | — | `run_railway_command` timeouts | reuses `SECRET_KEY` / `RUNTIME_DB_PASSWORD` on redeploy | `click.ClickException` | prints `<reused>` vs `<generated>` |
| `publish_module.py` (publish) | git credentials | release-authoritative tag gate; `--publish-outdated` disabled | `validate_expected_sha`, `_validate_commit_sha` | — | — | **new** `_require_fast_forward` + post-split identity recheck | `GitError` → exit 1 | force-with-lease lease value |
| `publish_module.py --status` | n/a¹ | read-only | — | — | — | — | never fails closed (by design) | prints observed SHAs |
| `beta_migrate.py` (in-place) | n/a¹ | clean-worktree preflight; checkpoint-first | snapshot validation | — | per-subprocess timeouts | checkpoint/resume | blocker list in report | JSON/summary report |
| `check_beta_migration_smoke.py` (CI gate) | n/a¹ | — | `_require` assertions | — | 30s / 120s per subprocess | `TemporaryDirectory` | `SmokeError` | stdout |

**Empty cells resolved.** Every `—` above is out of scope for that entry point's archetype
(a management command has no rate limit; a git publisher has no request size). The one cell that
produced a finding is `quickscale apply` × *idempotency/contract* as consumed by `beta_migrate.py`
— Finding 1. No other cell was left unexplained.

---

## Per-subsystem verdicts

| Subsystem | What was read | Verdict |
|---|---|---|
| Runtime-role provisioning (`runtime_database.py`, `start.sh.j2`, `init.sql.j2`, `generator.py`) | whole files + both templates rendered and inspected | Clean. Unification is complete and correct — see *Clean sweeps* |
| Contract-vintage gate (`contract_vintage.py`, three callsites) | whole module + every callsite | Clean as implemented; its interaction with `beta_migration.py` is Finding 1 |
| CLI deploy (`deployment_commands.py`, `railway_utils.py`) | full delta + helper bodies | Clean, and materially hardened — fail-hard variable reads, credential reuse, secret-free error text |
| Publication tooling (`publish_module.py`, `git_utils.py`) | full delta + `push_split_branch`, `_require_fast_forward` | Clean. Ancestry proof is bound to the pushed object |
| Tenant isolation (`tenancy.py`, `checks.py`, `check_tenant_isolation.py`) | full delta + all new comparators; normalizer tested | Clean, and strictly stronger than the prior pass |
| orgs privileged commands (`apps.py`, `migrate_billing_to_orgs.py`, `purge_organization.py`) | whole guards + whole new methods | Clean. Both new guards are fail-closed |
| Public HTTP surfaces (blog API, notifications webhook) | both auth/verify functions in full | Clean. `compare_digest` census is 2 of 2, both corrected |
| Module HTML templates (blog/crm/listings) | all base/child template diffs + project `base.html.j2` | Clean. No `\|safe` introduced; block names and the messages block line up |
| CI / gates (`ci.yml`, `publish.yml`, `gate_registry.json`, `sync_ci_gate_jobs.py`) | full delta; parity suite executed | Clean. The new gate is wired into all four required contexts |
| `beta_migration.py` / `check_beta_migration_smoke.py` | sampled at risk sites; smoke gate executed | Finding 1. Subprocess hygiene itself is clean |

---

## Clean sweeps worth recording

- **The four privileged-command declarations now genuinely agree on `{migrate, createcachetable}`.**
  `orgs/apps.py:37`, `development_commands.py:44`, `production.py.j2:157`, and the `start.sh.j2`
  inline prefixes all name the same two commands, and
  `quickscale_core/tests/test_privileged_command_contract.py` fails on divergence at any station —
  including a launcher-argv test asserting `start.sh migrate_billing_to_orgs` exits 2 with empty
  stdout. *Correction to the prior pass:* that audit recorded this convergence as already achieved,
  but at `b9e072f4` three of the four stations still listed `migrate_billing_to_orgs`. The
  convergence happened in **this** delta (`37987df9`), and the regression test is new with it.
- **Runtime-role provisioning is single-sourced without losing safety.** Role attributes and grant
  statements moved from duplicated literals into `runtime_database.py`. Both templates were
  rendered with the real context and inspected: `init.sql` is valid SQL, `start.sh`'s heredoc is
  valid Python, identifiers still go through `psycopg2.sql.Identifier` (runtime) or a
  quote-doubling helper (generated SQL), the password still travels as `sql.Literal` read from the
  environment and never on argv, and the boot step still refuses a self-role or an existing
  superuser. The role name also stopped varying per project without leaving a stale `_app`
  reference anywhere — all nine template callsites go through `runtime_db_role`.
- **`compare_digest` census: 2 of 2 hand-rolled verifiers now compare bytes.** `blog/views.py:351`
  and `notifications/services.py:752` are the only two callsites in first-party non-test code.
  Before `adc753c6` a non-ASCII bearer token or signature header raised `TypeError` inside the
  verifier — a 500, not a bypass. Both now encode to UTF-8 first.
- **Every broad `except` added in this delta re-raises.** All six new `except Exception` blocks in
  `railway_utils.py`, `deployment_commands.py`, and `contract_vintage.py` convert to
  `click.ClickException` and abort; none assigns a fallback. The four new silent-swallow sites were
  each checked individually and are correct: `LookupError` when the billing app is absent,
  `UnicodeDecodeError` when scanning binary files, `GitError`→`None` which now *blocks* mutating
  publication paths, and the apply preflight's config-parse guard (see watch items).
- **Publication cannot clobber unseen remote history.** `_publish_module` now computes the local
  split, proves `git merge-base --is-ancestor <observed-remote-tip> <local-split>` before any push,
  re-checks that the real `git subtree split` produced the same object, and pushes that object by
  SHA under `--force-with-lease`. An unverifiable ancestry check fails closed with "fetch the
  remote history and retry", and `_observe_remote_branch_sha` now distinguishes *absent* (`""`)
  from *unobservable* (`None`), with both rejected on mutating paths.
- **RLS conformance got strictly stronger.** `table_has_force_rls` no longer accepts "at least one
  policy exists"; it now requires exactly two policies with exactly the rendered predicates. The
  normalizer that makes the comparison possible was tested directly — it matches three plausible
  `pg_policies` deparsings and rejects `USING (true)`. A new negative-control test weakens a live
  predicate, asserts conformance fails for the right reason, and restores the exact original
  policy rows. Identifier truncation is refused up front (56-byte base-name cap) before any DDL.
- **Both new operator guards are fail-closed.** `purge_organization._guard_live_stripe_subscriptions`
  runs on the dry-run path *and* the destructive path, and is tested on both.
  `migrate_billing_to_orgs._require_explicit_recovery_connection` demands the explicit env
  acknowledgement *and* probes `pg_roles` for an actual BYPASSRLS/SUPERUSER login, refusing the
  restricted runtime role with an explanation of why RLS would hide the rows it must see.
- **Railway error paths stopped echoing variable output.** Four error messages that interpolated
  `result.stdout[:200]` — from a CLI whose output is the project's environment variables, including
  `SECRET_KEY` and `RUNTIME_DB_PASSWORD` — now carry only a format-changed diagnostic. The
  remaining `stdout[:200]` at `railway_utils.py:481` is in `railway status` parsing, which emits
  deployment URLs, not variables.
- **Credentials survive a redeploy.** `SECRET_KEY` and `RUNTIME_DB_PASSWORD` are now reused from
  the live service when present, so a re-run of `quickscale deploy railway` no longer invalidates
  every session and rotates the database password underneath a container still serving traffic.
  The summary line distinguishes `<reused>` from `<generated>`. The password is `secrets.token_hex`,
  which needs no URL escaping inside `RUNTIME_DATABASE_URL`.
- **Test-integrity diff: no weakening found.** Every removed assertion tracks a real behaviour
  move. Specifically: the `migrate_billing_to_orgs` tests did not lose the
  `nullable_billing_organization_ownership` fixture — they *gained* a second
  (`explicit_billing_recovery`) that exercises the new guard; four more moved into the
  `bypass_rls` lane, which `ci.yml:10` runs on every push and PR. A `pytest.skip("Template tree not
  found")` was deleted outright. The registry-parametrised FORCE-RLS test was replaced by the
  stronger exact-contract test plus two negative controls. Count assertions (`21`) changed because
  SA182 enrolled a project-owned model.
- **The new smoke gate is wired into all four required contexts** — `local-serial` (via the
  registry-driven dispatcher's generic branch), `local-parallel`, `hosted` (`ci.yml`
  `beta-migration-smoke-gate`, added to the `needs-test` list), and `publish` — and
  `scripts/test_gate_parity.py` (240 tests, executed) enforces that agreement. Every subprocess it
  spawns has a timeout, and it works inside a `TemporaryDirectory`.

---

## Structural smells

*(candidate inputs for the companion `deep-architectural-audit`, not findings here)*

- **Two independent filesystem-lock implementations.** `AdvisoryLock` and the DR backup lock remain
  separate. Carried forward unchanged.
- **Four independent declarations of the privileged-command set, reconciled only by a regex test.**
  The delta proved the drift is real, not hypothetical: three of the four stations disagreed with
  the prior audit's record of them, and a dedicated cross-station test had to be written to hold
  them together. The regex in that test (`frozenset\(\s*(\{.*?\})\s*\)`) also constrains how the
  declarations may be written. "None is a SSOT" is a deliberate defence-in-depth choice, but the
  reconciliation cost now has a name.
- **The generated project's contract version is a single scalar gating three CLI verbs.** Adoption
  is all-or-nothing per invocation and per project, with no record of *which* adoption steps an
  operator actually performed. Finding 1 is the first consequence; an automated consumer had no
  way to express "I performed steps 1 and 3".

---

## Tooling gaps

| ID | Gap | Would have caught | Recommendation |
|---|---|---|---|
| T1 | The generator's Jinja `Environment` (`generator.py:365`) uses default `Undefined`, so a missing or renamed context key renders as empty text, silently. Verified: `{{ x }}`, `{% for %}`, and `\| join` all yield empty. This delta moved the runtime role's attributes and grant statements *out of template literals and into context variables*, so a rename would now silently emit `CREATE ROLE … WITH PASSWORD …` with no `NOSUPERUSER`/`NOBYPASSRLS` and no grants. | A future context-key rename in any template | Pass `undefined=StrictUndefined` to the `Environment`. This is the Fail-Hard Principle applied to the generator's own rendering. Currently backstopped only by content assertions in `test_templates.py:3211-3248` |
| T2 | `check_beta_migration_smoke.py:151-156` shims `quickscale` so `quickscale apply` always exits 0. The gate therefore cannot observe any refusal, gate, or regression in the real CLI along the path it claims to cover. | `beta-migration-apply-contract-vintage-block` | Let the in-place continuation invoke the real `quickscale apply` (drop `quickscale` from `SHIM_NAMES` or forward the shim), with the recipient fixture carrying an old `project_contract` |
| T3 | The dependency gate never sees the generated project's runtime dependencies. | Future CVEs in `gunicorn`, `whitenoise`, `dj-database-url` (none in the root `poetry.lock`) | Add a Trivy pass over the hermetic generated-project lock the E2E lane already produces, or add those pins to a scanned dev group. *Carried forward* |
| T4 | No exhaustive external-provider conformance check for destructive org teardown. `purge_organization` now refuses live Stripe subscriptions, but nothing enforces that the *next* `_DELETE_SPECS` model carrying a provider id gets the same treatment. | Future provider-ID obligations beyond the shipped Stripe refusal | For every `_DELETE_SPECS` model with an external provider id, verify purge refuses or reconciles it. *Carried forward* |
| T5 | Hosted CI never ran any of the 34 commits in this window: `ci.yml` triggers only on `main`/`develop` pushes and PRs to `main`, and all this work is on `v89`. Gate coverage is real but, for feature branches, entirely dependent on the maintainer running `make ci` locally. | Any gate regression on a feature branch | **Closed by explicit acceptance.** Extending the trigger was rejected: running the full registered set — BYPASSRLS, E2E, Docker stations — on every integration-branch push charges that cost against ordinary development turnaround. [decisions.md §Integration-Branch CI Coverage](../technical/decisions.md#integration-branch-ci-coverage) records the acceptance, names `make ci` / `make ci-e2e` as the compensating local step, and bounds it: no gate leaves the registered set, and the publish gate and the `main` pull request both run the full set hosted |

---

## Notes (watch items)

**Carried forward, re-verified unchanged this pass:**

- **Integration-branch CI.** `ci.yml` triggers only on `main`/`develop` pushes and PRs to `main`,
  so `vNN` integration branches get no hosted gate run. No longer an unrecorded gap: the
  acceptance, its compensating local step, and its bounds are written down in
  [decisions.md §Integration-Branch CI Coverage](../technical/decisions.md#integration-branch-ci-coverage).
  What remains watchable is the residual — a red gate on an integration branch surfaces only at
  the next local `make ci`, the `main` pull request, or the publish gate. Revisit on a second
  regular contributor.
- **Generator lock generation** warns and continues by explicit usability policy. Deliberate.
- **The generated healthcheck checks nothing.** `urls.py.j2` `healthcheck()` returns a static
  `HttpResponse("OK")`; `railway.json.j2` points `healthcheckPath` at it. Still not promoted:
  boot-time `_check_rls_role` makes a broken runtime URL fail *before* the healthcheck can pass.
- **Cross-tenant count fallbacks** in CRM serializers and `billing/services.py` use `all_objects`
  with explicit org filters. Safe under NOBYPASSRLS; re-examine if a BYPASSRLS serving mode ever
  ships.
- **Atomic state writes are rename-atomic but not durable.** `schema/state_schema.py:355` — still
  no `fsync()`.
- **`blog/feeds.py` resolves the System org twice with opposite error handling** — `:33` guarded
  with `except Exception: org = None`, `:45` unguarded. A missing System org yields a 500 on the
  public feed rather than an empty feed. Unchanged this pass; trigger still requires a broken
  install.
- **`start.sh` puts the runtime password in DDL statement text.** `CREATE`/`ALTER ROLE … PASSWORD
  '<literal>'` reaches the server as statement text, so `log_statement=ddl` or an error under
  `log_min_error_statement=error` would land it in PostgreSQL logs, which Railway surfaces. Not
  promoted: Railway's managed-PostgreSQL logging configuration remains unverified (see residual
  risk), and success-path DDL is not logged by default. A pre-hashed SCRAM verifier would remove
  the exposure entirely.
- **Concurrent replica boot races `CREATE ROLE`.** With more than one replica on first deploy, two
  containers can both observe the role absent; one fails "role already exists", exits under
  `set -e`, and restarts into the `ALTER` branch. Self-healing, so not promoted. The `IF NOT
  EXISTS` guard in `init.sql` does not cover the `start.sh` path, which uses a read-then-branch.
- **Commit testimony accepts any `vN[.N…]` token.** `ROADMAP_REFERENCE_RE`
  (`check_commit_testimony.py:31`) is satisfied by a bare `v89:` prefix, which is why all 34
  commits in this window pass while carrying no ticket, body, or review trail. Governance, not a
  product defect — but the §2f side-channel classification depends entirely on commit messages
  carrying intent, and right now none do.

**Updated this pass:**

- **Billing backfill recovery is now guarded in code, not only by convention.**
  `migrate_billing_to_orgs` was removed from the sanctioned privileged-command set and given
  `_require_explicit_recovery_connection`, which demands `QUICKSCALE_ALLOW_BYPASSRLS=1` *and*
  verifies via `pg_roles` that the current login actually carries BYPASSRLS or SUPERUSER. The
  launcher's one-shot argv mode is gone and a test asserts it exits 2. This watch item is
  substantially discharged; it stays listed only because the command remains reachable.
- **`purge_organization` checks the local `Subscription` table, not Stripe.** The new guard reads
  rows whose `status` is in `current_statuses()`. If a cancellation webhook was missed, local state
  is stale and the purge proceeds while Stripe still bills. Not promoted — the guard is a clear
  improvement over none, and reconciling against the Stripe API at teardown time is a design
  decision, not a contained fix. Related to T4.
- **New:** `_enforce_apply_contract_vintage_preflight` (`apply_command.py:4010`) swallows
  `ConfigValidationError` and `OSError` and returns, skipping the *pre-mutation* gate. Not
  promoted: the same validation runs inside `_prepare_apply_context` moments later and aborts, and
  the second `enforce_shipped_contract_vintage` call at `:4136` still fires. Worth revisiting if
  `_prepare_apply_context` ever gains a config-repair path that writes before validating.
- **New:** the FORCE-RLS conformance comparison is pinned to **PostgreSQL 18's** deparsed
  `pg_policies` forms (`tenancy.py`, `_EXPECTED_TENANT_POLICY_EXPRESSION` and its operator
  sibling). Generated projects pin PG 18, but `quickscale deploy railway` runs
  `railway add --database postgres` and accepts whatever version Railway provisions. On a different
  major, a deparse difference would produce false NON-CONFORMING diagnostics. Not promoted: the
  only consumers are the `W004` system-check warning and the `check_tenant_isolation` report —
  nothing fails closed on it, and actual policy enforcement is unaffected. The `::text` cast
  rendering it depends on has been stable across PostgreSQL majors for many releases.

---

## Reconciliation log

- 2026-09-17 — *No prior finding IDs existed.* The 2026-09-15 pass closed with "No open findings
  remain", so there is nothing to carry, resolve, or regress. Every ID in this document is new.
- 2026-09-17 — **Prior clean sweep corrected, not re-litigated:** the 2026-09-15 entry "All four
  privileged-command declarations agree on the permanent two-command set" did not hold at the HEAD
  it recorded. `git show b9e072f4:…/apps.py` shows
  `frozenset({"migrate", "createcachetable", "migrate_billing_to_orgs"})`, and
  `production.py.j2` and `development_commands.py` matched it. The two-command set was reached in
  this window by `37987df9`, together with the cross-station regression test that now holds it.
  Re-recorded above under *Clean sweeps* with the correction stated.
- 2026-09-17 — Prior watch items re-verified at their cited anchors: integration-branch CI,
  generator lock policy, static healthcheck, cross-tenant count fallbacks, non-durable state
  writes, `blog/feeds.py` asymmetry, `start.sh` DDL password exposure, replica `CREATE ROLE` race,
  and the commit-testimony regex — **all unchanged**. The billing-backfill item was updated
  (strengthened in code). The structural smell "two independent filesystem-lock implementations"
  is unchanged.
- 2026-09-17 — Chain pass (§3.10) ran against the single finding, the watch-item list, and the
  crown jewels (tenant data, the runtime password, Stripe identifiers, split branches). **It
  produced nothing:** Finding 1 is confined to the maintainer workstation and shares no resource,
  credential, or code path with any watch item.

---

*Categories swept with no qualifying finding this pass: injection sinks (role DDL, generated SQL
identifiers, publication git argv); authorization on every new surface; secrets on argv, in logs,
or in error text; multi-tenant isolation across the marker-only classification rewrite;
concurrency; resources and I/O; performance; dependencies and supply chain; tests; data handling;
and the code-generator, CLI, multi-tenant-SaaS, and IaC archetype lenses.*
