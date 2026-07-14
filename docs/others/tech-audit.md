# Tech Audit — Codebase-Wide Defect Sweep

> **Latest re-run:** 2026-07-13 (V3 delta pass) · **Branch:** `v87` (HEAD `41689be7`, prior
> `53a657d6`) · **Result: zero open findings, zero new findings — clean pass.** History of prior
> passes preserved in the update block and Reconciliation log below.
>
> **Original masthead:** audit date 2026-07-11 (re-run, delta pass — first run on the V3 prompt) ·
> **Branch:** `v87` (HEAD `53a657d6`) · **Prompt:** tech-audit-prompt (V3)
> **Mode:** re-run against the SA65/SA66/SA68/SA69/SA73 + SA59.1-checkpoint delta
> (`ae8c386e..53a657d6`, 51 non-doc files, +4328/−1476). The full first-party production diff was
> read; the SA59.1 "chore: checkpoint" commits (`625626e8`, `6c90d8b9`, `2b9afa6b`) and the
> quality-fix commit `fc3dc00c` ("SA73: fix quality gate failures") received elevated scrutiny per
> §2f.2 — and, as in the two prior passes, that lane is where this pass's defects live. Closure
> claimed since the prior pass (TA53 via SA65) **verified directly in code** per §2f.3 — complete.
> Still-open prior findings (TA49, TA50) re-verified: **TA49 is resolved in code** (SA59.1 landed
> its exact prescribed fix), TA50 unchanged. Four new findings opened (TA54–TA57), three of them
> from the arch-audit red-flag hand-off after independent verification. Prior IDs are stable; this
> document states **present reality for planning** — closed findings live only in the
> Reconciliation log at the bottom. Structural findings live in [arch-audit.md](arch-audit.md);
> fail-hard policy SSOT is [decisions.md §fail-hard-principle](../technical/decisions.md#fail-hard-principle).
>
> **Update (2026-07-12, roadmap closeout pass):** all five open findings from this pass are now
> resolved and reconciled below — **TA54** (org-creation-under-RLS production defect) by SA74,
> **TA55** (autouse signal muting) by SA74, **TA56** (`_session_managed_adapters` swallow) by SA75,
> **TA57** (integration gate red at merge) by SA76's quarantine mechanism, and **TA50**
> (composite-FK deferability divergence) by SA60. Zero findings remain open as of this pass; see
> the Reconciliation log for verification detail. Full implementation detail for each fix is in
> [CHANGELOG.md](../../CHANGELOG.md); remaining non-blocking follow-ups spawned by these fixes
> (SA77 orgs restricted-role residual, SA79 forms backfill bug) are tracked in
> [roadmap.md](../technical/roadmap.md), not here.
>
> **Update (2026-07-13, SA82 completed):** SA82 (Track 3) removed the SA76 quarantine entries and
> ran the full `make test-integration` gate end-to-end — orgs 847 passed/11 BYPASSRLS-skips/0 failed
> (93.04% coverage), notifications 39 passed/0 failed (91.76% coverage), overall mean 92.95% passed.
> **SA77 and SA79 are closed** by this result — their acceptance conditions are met under the full
> unquarantined gate. The repository integration gate remains red due to four independent
> restricted-role findings (CRM → SA84, forms residual → SA85 impl/validation-complete/blocked-on-CR-SA85-REV-001, listings → SA86; blog → SA83 since closed after independent review) now
> tracked on the roadmap Track 1, plus the existing SA80.3 (backups pg_dump). SA81 unchanged. This
> document's reconciled status is unchanged — SA77/SA79 were tracked on the roadmap, not as
> tech-audit findings; their closure is recorded here for status accuracy.
>
> **Update (2026-07-13, SA80.3b/SA87 reconciliation, revised):** SA80.3b rerun confirmed 0 missing-`pg_dump`/`pg_restore` failures (retained-role: 298 passed/1 failed/2 skipped; default-user: 299 passed/2 skipped). SA80.3/SA80.3b fully resolved. The 1 retained-role failure was **SA87** (backups retained-role assertion, Track 3) — completed 2026-07-13 per change review; see [roadmap.md §Track 3](../technical/roadmap.md). The current open restricted-role findings keeping the integration gate red are **SA84** (Track 1 CRM), **SA85** (Track 2 forms, impl/validation-complete/blocked-on-CR-SA85-REV-001), and **SA86** (Track 2 listings); **SA83** (Track 1 blog) closed after independent review. SA87 is no longer an open finding. SA81 (per-module lockfiles, no deps) is unrelated cleanup and does not affect the gate. SA80.3b evidence retained: retained-role run 298 passed/1 failed/2 skipped, default-user run 299 passed/2 skipped, zero missing-tool failures in both.
>
> **Update (2026-07-13, V3 delta re-run — HEAD `41689be7`, prior `53a657d6`):** full delta sweep
> over the `53a657d6..HEAD` production diff (SA60/SA70/SA74/SA75/SA76/SA77/SA78/SA79/SA80/SA82/SA87
> remediation + test/docs). **Zero new findings — clean pass.** Production code touched this delta:
> `crm/services.py` (SA74 seeding fix), `orgs/signals.py`+`apps.py` (SA70 last-owner `pre_delete`
> backstop), `orgs/.../purge_organization.py` (SA70-aware `_raw_delete`), `forms/0007` migration
> (SA79 `operator_access` + SA60 `NOT DEFERRABLE`), `apply_command.py` (SA80 Poetry env isolation),
> `production.py.j2` (cosmetic quote fix) — each read in full and verified sound (see Clean sweeps
> and Per-module verdicts). Test-integrity diff (§3.7) run across every changed test file: all are
> strengthenings or SA59.2 PostgreSQL-seam adaptations (the TA55 autouse muting is now removed and
> replaced with an opt-in fixture; backups moved to the PG seam with SQLite paths explicitly
> `monkeypatch`-forced; notifications `reuse_db` is an operational rerun fix) — **no weakened or
> flipped tests**. All prior findings remain resolved; no closures regressed. The three restricted-role
> RLS failures keeping the integration gate red (**SA84** CRM / **SA85** forms / **SA86** listings;
> **SA83** blog closed after independent review, **SA80.3** and **SA81** since resolved/closed) remain **roadmap-tracked**, with their structural root
> owned by [arch-audit.md Finding 8](arch-audit.md) (`module-rls-context-procedural`); not promoted
> here per this document's convention that roadmap-tracked work is not duplicated. `psql`/`pg_isready`
> clients are now installed on the machine (they were absent last pass) but **no PostgreSQL server is
> running**, so the runtime-read-path triage of SA83–SA86 (arch-audit's "bucket 3") remains a named
> verification step, not an empirical result.

## Orientation summary

QuickScale is a **Python 3.13 Django project generator** (Poetry monorepo: `quickscale_core`
manifest/apply/generator/DR engine, `quickscale_cli` Click CLI, 13 shipped `quickscale_modules/*`
Django apps, `quickscale_devtools` beta-migration tooling, Jinja2 generator templates; version
0.87.0, unreleased). Two deployment realities: **(a)** the *generated project* — an internet-facing
Django app targeting Railway (edge proxy → gunicorn, non-root container, fail-closed runtime DB
role, HTTPS/HSTS/secure cookies, active `CACHES`, SA36 trusted-proxy client-IP); **(b)** the
*CLI/generator* — a local developer tool (monorepo Poetry or `pip install quickscale`). Two
launcher-contract changes this delta: **SA68** replaced the boot guard's `sys.argv` migrate-sniffing
with an explicit one-shot env contract (`QUICKSCALE_PRIVILEGED_COMMAND` ∈ {migrate,
createcachetable} + `RUNTIME_DATABASE_URL=""`; `QUICKSCALE_NON_DB_COMMAND` ∈ {collectstatic,
compilemessages}; unknown values fail hard; recorded in decisions.md §Launcher One-Shot
Command-Env Contract), and **SA59.1** split the test pipeline into a DB-free unit gate (core+CLI)
and a PostgreSQL NOBYPASSRLS integration gate (new `scripts/test_integration.sh`; CI/publish
provision `quickscale_test_role` with verified `rolbypassrls=f`/`rolsuper=f` and export
`QS_*_DB_USER` + `QUICKSCALE_ALLOW_BYPASSRLS=0`). Declared-invariant oracle used this pass: the
fail-hard principle (decisions.md SSOT), the RLS runtime-role contract (NOSUPERUSER/NOBYPASSRLS,
SA58 boot guard), the SA68 one-shot launcher env contract, Option C child-table RLS with the
NULLIF-guarded GUC policy, SA14.4 (no auto-primed BYPASSRLS hatch), and AF7 (manifest-present but
adapter-unimportable is fail-hard). Tooling baseline: ruff + strict mypy in CI, csrf_exempt gate,
delete-rule/module-core/manifest-sync gates, new SA66 beta-migration taxonomy conformance gate;
**still no dependency-audit / bandit / semgrep step**.

**Coverage (this pass):** read in full — the entire first-party production diff
`ae8c386e..53a657d6`: `apply_command.py` (SA65), `orgs/apps.py` (SA68 guard rewrite),
all five changed generator templates (`Dockerfile.j2`, `production.py.j2`, `start.sh.j2`,
`OPERATIONS.md.j2`, `README.md.j2`), `beta_migration.py` (SA66 taxonomy), the four adapter
docstring corrections (SA69), `Makefile`/`scripts/test_unit.sh`/`scripts/test_integration.sh`
(new)/`scripts/check_ci_locally.sh`/`ci.yml`/`publish.yml`/`mypy.ini`. Beyond the diff, read in
full for TA54 verification: `crm/signals.py`, `crm/services.ensure_org_default_stages`,
`orgs/managers.py` (both dispatch paths), `orgs/forms.OrgCreateForm.save`,
`orgs/current_org.py` complete (AF9 wrapper, org_scope, operator_access),
`orgs/tenancy.py:480-560` (FORCE-RLS policy SQL), `crm/migrations/0008/0010` RLS targets,
`crm/tests/conftest.py` + `crm/tests/settings.py`, `entry_point.refresh_managed_adapters`.
Test-integrity diff (§3.7) run over every changed test file: billing/social/orgs restricted-role
adaptations are **strengthenings** (writes now context-primed; boot-guard suite extended with
superuser + unknown-command cases) with two exceptions promoted to findings (TA55 muting, TA56
skip-conversion); all added `pytest.skip` calls in the delta enumerated — every one belongs to
TA56 except a benign template-tree guard in the SA66 gate. Sampled — SA66 conformance gate
(`test_beta_migration_ownership_conformance.py`), SA68 template/runtime test additions,
CHANGELOG/roadmap deltas for blessing checks. Skipped — module interiors unchanged since the
2026-07-10 deep pass (verdicts carried), `htmlcov/`, `graphify-out/`. **Empirical checks:** none
possible this pass — no local PostgreSQL client (`psql`/`pg_isready` absent) and `gh` unavailable,
so TA54's runtime confirmation and TA57's Actions-dashboard confirmation are named as the
verification steps instead. Audit tools run: none available (installs prohibited); `poetry.lock`
still untouched since 2026-06-17.

**Coverage (2026-07-13 V3 delta re-run, HEAD `41689be7`):** read in full — the entire first-party
production diff `53a657d6..HEAD`: `crm/services.py` (SA74), `orgs/signals.py` + `orgs/apps.py`
(SA70 `pre_delete` backstop wiring), `orgs/.../purge_organization.py` (`_raw_delete` switch),
`forms/.../0007_new_organization_ownership.py` (SA79/SA60), `apply_command.py` (SA80
`_isolated_poetry_env`), `production.py.j2` (cosmetic). Beyond the diff, read for verification:
`orgs/current_org.py` (AF9 execute-wrapper 461–529, `_restore_current_org_id`, `_tenant_context`,
`org_scope` — confirms SA74's `_af9_primed_for_txn`/`_af9_primed_atomic` cleanup names match the
real wrapper attributes and the GUC-leak logic is sound), `orgs/models.py` last-owner helpers,
`auth/views.py:140–242` (`AccountDeleteView` pre-check that guards the `user.delete()` cascade path
against the SA70 backstop), the CRM `organization_created` receiver census. Test-integrity diff
(§3.7) run over every changed test file (backups PG-seam adaptation, orgs conftest autouse→opt-in,
notifications `reuse_db`, crm/forms/blog/listings/social RLS-boundary adaptations) — no weakenings.
Sampled — CHANGELOG/roadmap deltas for blessing checks, `scripts/provision_test_roles.sh` (new),
`scripts/bootstrap.sh`. Skipped — module interiors unchanged since the 2026-07-10 deep pass
(verdicts carried), `htmlcov/`, `graphify-out/`, `poetry.lock` (dependency bump; no manifest CVE
signal without a scanner). **Empirical checks:** none possible — `psql`/`pg_isready` clients now
present but no PostgreSQL server is running, and installs are prohibited; SA83–SA86 runtime-read
triage named as the verification step. Audit tools run: none available (`bandit`/`pip-audit`/
`semgrep` absent, installs prohibited).

**Clean sweeps worth recording (2026-07-13 V3 delta re-run):**

- **SA74 (crm seeding) fix-regression pass — sound and complete:** `ensure_org_default_stages`
  saves/sets/restores the tenant ContextVar across its whole scope, `_seed_default_stages` wraps
  INSERTs in `org_scope(organization)`, and the `finally` block's CR-SA74-001 GUC-leak cleanup uses
  the *real* AF9 attribute names (`_af9_primed_for_txn`/`_af9_primed_atomic`, verified against
  `current_org.py:503–522`) and correctly guards on `connection.in_atomic_block` so no stale
  `app.current_org_id` GUC leaks to later no-context queries in an enclosing transaction. Sibling
  check: CRM is the **only** `organization_created` receiver (census run) — no other module carries
  the TA54 class.
- **SA70 last-owner `pre_delete` backstop — no cascade-path regression:** the receiver raises only
  for a sole-owner-with-other-members membership; `AccountDeleteView._get_blocking_orgs_for_deletion`
  pre-checks and blocks that exact case before `user.delete()`, so the guarded account-deletion path
  never trips it; no ORM `organization.delete()` cascade path exists (grep-confirmed), and the org
  purge command switched org-level deletes to `_raw_delete` to bypass the receiver deliberately.
- **SA79/SA60 forms `0007` — correct fix:** `SET LOCAL app.operator_access = 'on'` enables the Form
  RLS `FOR SELECT` sub-policy so the cross-org backfill subquery reads all orgs under FORCE RLS
  (transaction-scoped, auto-cleaned); the composite FK is now `NOT DEFERRABLE` matching the ratified
  SA60 project-wide policy and the cross-module conformance gate.
- **SA80 `_isolated_poetry_env` (CLI) — sound:** copies the env, drops `VIRTUAL_ENV`/`POETRY_ACTIVE`
  and the venv `bin` from `PATH`, sets `POETRY_VIRTUALENVS_IN_PROJECT=true`, and is passed only to
  the two `poetry install`/`poetry lock` call sites via the SA65 per-call `env=` seam — foreign
  subprocesses still inherit the parent env unmodified.

**Clean sweeps worth recording (2026-07-11 pass):**

- **TA53/SA65 closure verified (§2f.3):** `_QUICKSCALE_SUBPROCESS_ENV` module-level cache deleted;
  `_run_command` defaults `env=None`; `_build_quickscale_env()` built on demand and passed only to
  the three nested `quickscale_cli.main`/compose call sites; docstring's false production claim
  corrected; `TestSA65SubprocessEnvScoping` pins the scoping. Complete.
- **SA68 verified across the config matrix (§2h):** `QUICKSCALE_PRIVILEGED_COMMAND` appears only
  as a shell-prefix one-shot on the `migrate` and `createcachetable` lines of `start.sh.j2`
  (`exec gunicorn` carries neither var); `production.py.j2` fail-hards on unknown command values,
  requires `RUNTIME_DATABASE_URL` *explicitly blank* for the privileged path (so adding the var
  persistently to a normal serving config fails loudly), fail-hards on missing `DATABASE_URL`, and
  enforces mutual exclusion of the two command vars; the serving path stays fail-closed. The orgs
  boot guard fails closed on unrecognised values (`_PRIVILEGED_COMMANDS` membership, not a
  catch-all). The residual persistent-misconfiguration cell is a watch item (Notes).
- **TA49's prescribed fix landed and verified (SA59.1):** the blanket
  `QUICKSCALE_ALLOW_BYPASSRLS=1` export is gone from `Makefile` (module test-unit path now
  fail-louds with redirect guidance) and `scripts/test_unit.sh` (module loop removed entirely);
  `ci.yml` and `publish.yml` create `quickscale_test_role` NOBYPASSRLS/NOSUPERUSER with
  attribute verification, wire all 11 `QS_*_DB_USER` vars, and set `QUICKSCALE_ALLOW_BYPASSRLS=0`.
  The SA14.4 hatch is once again an explicit per-suite opt-in.
- **Billing/social restricted-role test adaptations are honest:** isolation tests now set org
  context before tenant writes (production-shaped RLS discipline) instead of relying on
  BYPASSRLS; the social operator test now exercises `operator_access` against the real SELECT
  sub-policy; billing re-verified green (216 passed) under the restricted role per the SA59.1
  continuation notes.
- **SA66 gate is real:** the conformance test enumerates every emitted `.j2`/theme file and fails
  on any path not classified by a taxonomy tuple, with `INTENTIONALLY_UNMANAGED` as the explicit
  documented escape hatch.
- **SA69 docstring corrections verified** (billing/crm/social adapters now name the first-party
  `ImproperlyConfigured`); the orgs `type: ignore[import-untyped]` removal is consistent with the
  new sibling-`MYPYPATH` typecheck wiring.

---

## Findings summary

| ID | Severity | Category | Title | Effort | Confidence | Status |
|----|----------|----------|-------|--------|------------|--------|
| TA54 | S1 | correctness / multi-tenant SaaS | Org creation with CRM installed fails under the production runtime role — `organization_created` seeding writes tenant rows with no org context under FORCE-RLS | Small | High (mechanism) / needs runtime confirm | **resolved (SA74, 2026-07-12)** |
| TA50 | S3 | data-handling / consistency | Composite-FK helper flipped to `NOT DEFERRABLE` undocumented — diverges from forms' asserted `DEFERRABLE` contract and from every existing database | Small | High (facts) / Medium (impact) | **resolved (SA60, 2026-07-12)** |
| TA55 | S3 | test-integrity (weakened tests) | Autouse `organization_created.send` muting in orgs conftest — every orgs test now runs with the org-creation seam disconnected | Small | High | **resolved (SA74, 2026-07-12)** |
| TA56 | S3 | test-integrity / fail-hard policy | `_session_managed_adapters` swallows `ImproperlyConfigured` — a genuinely broken managed adapter now yields skips, not failures, in the unit gate | Small | High | **resolved (SA75, 2026-07-12)** |
| TA57 | S3 | operability / test-integrity | Integration gate merged red on `v87` — while red it catches no new module-suite regressions; known failures are unquarantined | Small (quarantine) | Medium | **resolved (SA76, 2026-07-12)** |

Counts: **S1: 0 · S2: 0 · S3: 0 · S4: 0 — zero open findings this pass.**
Closure verification this pass: TA53 (SA65) — confirmed in code. TA49 — resolved (SA59.1, verified in code; residual red-gate state opened separately as TA57, now itself resolved).
**Chain (§3.9), now broken:** TA55 + TA57 previously concealed TA54 (the orgs suite muted the
signal and the red gate stripped meaning from CRM-suite failures). SA74 fixed TA54 at the root
(primed tenant context in `ensure_org_default_stages`) and replaced the TA55 autouse muting with
an opt-in fixture, restoring the org-creation seam to real test coverage; SA76's quarantine
mechanism resolved TA57's red-gate state. The chain no longer applies — see Reconciliation log.

---

## Findings detail

> All findings opened in the 2026-07-11 pass (TA54–TA57) and the carried TA50 are now resolved —
> see the Reconciliation log at the bottom for closure verification. Full defect/fix detail is
> preserved in version control history of this file and in [CHANGELOG.md](../../CHANGELOG.md)
> (SA60, SA74, SA75, SA76 entries); it is not repeated here per this document's own convention that
> closed findings live only in the Reconciliation log.

*(Full finding-detail prose for TA50/TA54/TA55/TA56/TA57 — location, defect, failure scenario,
evidence, fix — is preserved in this file's git history at the 2026-07-11 revision and in
[CHANGELOG.md](../../CHANGELOG.md)'s SA60/SA74/SA75/SA76 entries. Not repeated here now that all
five are closed.)*

---

## Per-module verdicts

Module interiors unchanged since the 2026-07-10 deep pass; verdicts carried except where this
delta touched them:

- **crm** — **TA54 resolved (SA74, 2026-07-12; fix re-verified 2026-07-13)**:
  `ensure_org_default_stages` primes tenant context across its scope, seeds under `org_scope`, and
  cleans up the AF9 GUC on exit (verified against `current_org.py`); production seeding path clean.
  CRM is the only `organization_created` receiver — no sibling carries the TA54 class.
- **orgs** — production source clean; **TA55 resolved (SA74)** — autouse signal muting replaced with
  an opt-in fixture. **SA70 last-owner `pre_delete` backstop (`signals.py`/`apps.py`) verified sound
  this delta** — no cascade path it wrongly blocks; purge switched to `_raw_delete` to bypass it
  intentionally. SA59.1's restricted-role failures were tracked as **SA77** (closed 2026-07-13 by
  SA82 — full gate confirmed clean).
- **quickscale_core** — production clean (templates verified, SA68); **TA56 resolved (SA75)**.
- **quickscale_cli** — clean; TA53 resolved and verified (SA65); SA66 gate added.
- **quickscale_devtools** — clean (taxonomy data + `start.sh` added to in-place targets, gated by
  SA66's conformance test).
- **forms, blog, listings, notifications, social, storage, analytics, auth, billing, backups** —
  carried clean at their live surfaces (2026-07-09/10 passes); billing/social test adaptations
  this delta reviewed and found strengthening.

---

## Structural smells (candidates for `arch-audit.md`)

- **Checkpoint/quality-fix commits as the recurring defect lane — third consecutive pass:** last
  pass it was `628c7d28`; this pass the SA59.1 checkpoint commits carried TA55 and `fc3dc00c`
  ("SA73: fix quality gate failures") carried TA56 plus a silent mypy weakening
  (`ignore_missing_imports = True` for backups — Notes). SA-tagged but review-light "make the
  gate pass" changes keep landing behavioral/test-contract edits without decisions.md coverage.
  The CHANGELOG-coverage gate under Tooling gaps remains the ticket-shaped mitigation.
- **No documented contract for `organization_created` receivers:** TA54's root shape — the seam
  doesn't state whether dispatcher or receiver owns tenant-context establishment for RLS-scoped
  writes. One line in decisions.md (plus a conformance test for future receivers) turns the TA54
  fix from a patch into a contract.
- **Deletion invariants enforced per boundary:** carried — SA70 (orgs `pre_delete` backstop) is
  now scheduled on Track 1.
- **No single deploy-time configuration contract for generated apps:** carried, shrinking —
  SA68 landed the command-env contract and deleted the argv sniffing; remainder in arch-audit
  Finding 6.
- **Verbatim security-code copies accumulating:** carried — SA26 `_sanitize_href` pair
  (blog/listings); generated `get_client_ip` duplicated across `base.py.j2`/`production.py.j2`.

## Tooling gaps

- **CHANGELOG/decisions coverage gate for production commits** — carried (now three passes of
  evidence: TA47/TA49/TA50/TA51, TA53, TA55/TA56).
- **Known-failure quarantine convention for CI gates** *(new)* — xfail-with-ticket (or an
  explicit allowlist consumed by `test_integration.sh`) so a gate can stay load-bearing while
  named failures are worked; would have prevented TA57's blanket-red state.
- **Receiver-context conformance check** *(new, ties to TA54)* — a test-side rule that every
  `organization_created` receiver performing ORM writes runs correctly with the ContextVar unset
  under the restricted role; prevents the class as future modules add receivers.
- **`pip-audit`/`safety` CI step** — carried; lockfile unchanged since 2026-06-17, still no CVE
  signal.
- **`bandit`/`semgrep` CI step** — carried; would flag the `except ...: pass` shape (TA56's
  class) mechanically.
- **Tracked-artifact gate** — carried (SA61 fixed instances; the gate prevents re-accretion).
- **Composite-FK conformance gate** — carried (ties to TA50/SA60).
- **Generated-project boot smoke test** — carried; SA68 grew `test_generated_project_runtime.py`
  further (+284 this delta), but a standing CI boot smoke of a freshly generated artifact remains
  the systematic version — and is exactly the harness that would have caught TA54 end-to-end.
- **csrf_exempt gate matcher coverage** — carried (no live slipping usage today).

Categories swept with no qualifying finding this pass (chain pass ran — one chain found, recorded
on TA54): injection/XSS (templates re-read under output-language rules; SA68 shell prefixes
sound; no new sink surface), auth/CSRF (no endpoint changes), concurrency (no new shared state;
`ensure_org_default_stages`'s lock discipline re-verified while reading for TA54), resource
leaks/timeouts (new shell scripts use mktemp+trap cleanup), N+1/perf, secrets (role provisioning
uses trust-auth CI Postgres, no credential material committed), dependency CVEs (lockfile
unchanged; low confidence without a scanner), CLI archetype (SA65 verified; no new destructive
paths), generator archetype (SA68 launcher contract verified template↔settings↔guard coherent;
docs updated in the same delta).

---

## Reconciliation log (append-only)

- 2026-07-04 — TA1: resolved (SA17.1, `aea5e3bd` — legacy config keys now raise `ConfigValidationError`).
- 2026-07-04 — TA2: resolved (SA17.2–SA17.6 — module settings fail hard via startup guards/direct reads; residual `QUICKSCALE_MODE` defaults split out as TA19).
- 2026-07-04 — TA3: resolved (SA18.1, `e4183e52` — import-time `except Exception: pass` removed).
- 2026-07-04 — TA4: resolved (SA18.2 — analytics post-hook raises `ManifestError` on empty-after-resolution).
- 2026-07-04 — TA5: resolved (SA18.3, `ab32f272` — `quickscale_cli.schema` shim deleted).
- 2026-07-04 — TA6: resolved (SA18.4 — deterministic template resolution, no cwd guessing).
- 2026-07-04 — TA7: resolved (SA18.5 — version fallback narrowed; raises when unavailable).
- 2026-07-04 — TA8: resolved (SA18.6 — metadata resolution no longer swallows validation errors).
- 2026-07-04 — TA10: resolved (SA18.7 — railway_utils catches narrowed; unparseable output raises).
- 2026-07-04 — TA11: resolved (SA18.8 — non-numeric `PORT` raises `ValueError`).
- 2026-07-04 — TA13: resolved (SA18.9 — `step_capture_hashes` fails hard on `OSError`).
- 2026-07-04 — TA14: resolved (SA18.10 — `# F-EXCEPTION:` tags added and tabled in decisions.md).
- 2026-07-04 — TA15: resolved (SA18.11 — malformed module pyproject raises `TOMLDecodeError`).
- 2026-07-04 — **ID renumbering note:** the interrupted 2026-07-03 sweep briefly assigned TA16=`throttle-remote-addr-behind-proxy` (superseded by today's TA18), TA17=`railway-cli-secrets-on-argv` (dropped in renumbering — **reinstated 2026-07-05 as TA27**), TA18=`committed-coverage-artifacts` (renumbered TA23). Canonical IDs are the ones in this document.
- 2026-07-05 — TA9: resolved (SA17.7, `100f67d6` + `0ed70760` — analytics hard-imports posthog at module top; forms uses `apps.is_installed` guard + hard lazy imports; residual broad catch around the capture call is documented best-effort for a non-critical side effect, with regression tests).
- 2026-07-05 — TA12: resolved (SA17.8 — deprecated catalog delegates removed from public API; `get_module_readiness_reason` raises `ValueError` on unknown names).
- 2026-07-05 — TA16: resolved (SA19 — `start.sh.j2` prints per-variable `set`/`MISSING` status, never secret values).
- 2026-07-05 — TA17, TA18, TA21, TA22, TA24, TA25: still-open (every location re-verified against `a6706db1`).
- 2026-07-05 — TA26, TA27, TA28: opened this pass (TA27 is the reinstatement above); TA29 opened and resolved in the same closeout pass (SA33).
- 2026-07-05 (closeout) — TA29: resolved (SA33 — dangling `decisions.md:650` → `arch-audit.md` anchor link repointed to the arch-audit reconciliation log entry).
- 2026-07-05 (module-by-module deep pass) — TA30, TA31, TA32: opened. TA26 strengthened (storage-backend coercion joins the class as scenario 4). TA17 extended (admin backup-create/prune share the in-request execution; restore remains the anchor). Modules read deeply and found clean this pass: quickscale_core (DR engine, apply ledger/executor, state/locks/git), orgs (purge/migration commands, tenant-context machinery), quickscale_cli (update/remove snapshot-rollback flows, status/dev/deploy commands), billing, backups commands, notifications, crm.
- 2026-07-05 (closeout) — TA19: resolved (SA14.6 — QUICKSCALE_MODE fail-hard guard added in `QuickscaleOrgsConfig.ready()`, all 4 `getattr(settings, "QUICKSCALE_MODE", "solo")` callsites replaced with direct required reads).
- 2026-07-05 (closeout) — TA20: resolved (SA22 — same-filesystem staging with backup/swap/rollback for `apply --force`; generation to temp first, swap only on success, rollback on failure).
- 2026-07-05 (closeout) — TA23: resolved (SA25 — `coverage.json` and `pytest_cov_log.txt` removed from git tracking via `git rm --cached`; `.gitignore` patterns already present).
- 2026-07-05 (roadmap cleanup) — TA26: resolved (SA27 — `assemble_wiring_spec` now raises on non-empty `validation_issues`; missing `validate_{blog,forms,storage,orgs}_module_options` calls added to the apply-gate; silent coercions in `resolve_orgs_module_options`/`resolve_storage_module_options`/blog resolvers removed). TA30: resolved (SA28 — last-owner and personal-org invariants enforced at the account-deletion boundary via `AccountDeleteView.form_valid`, with subscription cancellation routed through the existing billing seam).
- 2026-07-06 — TA28: resolved (SA32 — retired `invalidate_social_cache()` from `quickscale_modules_social.services.__all__`; kept the helper importable for compatibility; no longer a public-API trap for bulk mutations).
- 2026-07-06 (roadmap cleanup) — TA27: resolved (SA31 — Railway/DR adapter secrets moved off process argv onto stdin transport; this closure was missed in the 2026-07-05 closeout pass and is corrected here).
- 2026-07-06 (re-run, HEAD `3056186a`) — **TA21: resolved** (SA23, `531386d9`/`20f01b88` — both debug views validate `next` via `url_has_allowed_host_and_scheme` against `request.get_host()`). **TA22: resolved** (SA24, `ba2c62da` — analytics JSON payload escapes `<`/`>`/`&` before `mark_safe`). **TA24: resolved** (SA21.1 — production `CACHES` active: Redis via `REDIS_URL`, `DatabaseCache` fallback — but the fallback's bootstrap gap opened as **TA33**). **TA31: resolved** (SA29, `4d1832fe` — credentials via `*_env_var` indirection, `__QS_ENV__` markers rendered as `os.environ.get()` with no credential material at rest, README rewritten to the real contract, cloud-backend env-var references validated at the apply gate; verified end-to-end adapter→wiring→template). **TA17: still-open, narrowed** to create/prune (restore async since SA20; severity S2→S3). **TA18: still-open, narrowed** to module callsites (DRF half fixed by SA21.1; residual is tracked SA21.2; severity S2→S3). **TA25: still-open at this pass** (location re-verified unchanged; resolved later the same day — see closeout entry below). **TA32: still-open** (location re-verified unchanged). **TA33–TA40: opened this pass** (TA33/TA35 are regressions-in-shape from SA21.1's new code; TA36/TA37 from SA20's new lifecycle; TA34 long-standing, exposed by SA28's guarded flow; TA39/TA40 accepted from arch-audit red-flag hand-off after independent verification).
- 2026-07-06 (closeout) — **TA36: resolved** (SA20 CR-SA20-REV-002 — `_atomic_claim_restore()` performs the DB-level compare-and-swap this finding asked for, `BackupArtifact.objects.filter(pk=..., status__in=eligible_set).update(status=STATUS_RESTORING, ...)`, on both admin dispatch branches; verified present in `backups/admin.py` directly. **CR-SA20-007: resolved** likewise — see Notes; the tracked gap and TA36 were both closed by the same SA20 closeout pass that this document's 2026-07-06 re-run had not yet picked up).
- 2026-07-06 (closeout) — **TA25: resolved** (SA26 — added `_sanitize_rendered_html()` to `blog/views.py` and `listings/views.py`, an allowlist URI-scheme check run on rendered markdown before the `|safe` filter; `javascript:`/`data:`/`vbscript:` links neutralized, including tab/newline/case-variant obfuscation per CR-SA26-001; `http(s)`/`mailto`/relative/fragment links preserved. 26 regression tests across both modules. Full detail in CHANGELOG.md).
- 2026-07-06 (module-by-module deep pass, core and cli included as modules) — **TA41 opened** (forms public-submit `TypeError`→500 on non-string JSON values, found reading the serializer/validator chain in full). Modules read deeply and found clean this pass: quickscale_core (DR primitives/recovery restore gate, module_wiring, generator + deploy templates — no dangerous sinks), orgs (tenant-context save/restore, `TenantManager`, last-owner model guards race-safe via Organization-row lock, invitation accept, permissions), billing (webhook idempotency + credit-grant unique-constraint rollback verified idempotent under concurrent duplicate delivery). Secondary items recorded inside existing findings rather than as new IDs: the concurrent-account-deletion last-owner race (folded into TA34), the staff-authored ReDoS via form-field `regex` rules (folded into TA41), and the staff-authored unvalidated YouTube/TikTok embed-id interpolation (`social/contracts.py:235,251` — same trust class as TA25, React-escaped at the sink, not promoted).
- 2026-07-06 (roadmap closeout) — **TA33: resolved** (SA34 — `createcachetable` added to `start.sh.j2` after the migrate step, gated behind `[[ -z "${REDIS_URL:-}" ]]` so it only runs when `DatabaseCache` is the active backend). **TA38: resolved** (SA39 — `operator_access()`/`_set_operator_access()` now raise `ImproperlyConfigured` when called outside an open transaction, instead of silently no-opping). **TA41: resolved** (SA40 — public form-submit validation now rejects non-string JSON values with 400s instead of an uncaught `TypeError`/500; the staff-authored ReDoS-via-`regex` residual noted when TA41 opened remains an accepted low-priority watch item, same trust class as the pre-SA26 TA25 pattern, not promoted to its own ID). **TA32: resolved** (SA30 — confirmed directly in code: `listings/views.py` and `storage/helpers.py` now raise `ImproperlyConfigured` on missing/invalid runtime settings instead of silently defaulting/coercing; this closure was flagged in `roadmap.md`'s 2026-07-06 triage note but not yet reconciled here — corrected in this pass). Findings-table counts updated (S2 2→1, S3 6→4, S4 3→2); full detail for all four lives in CHANGELOG.md (SA34/SA39/SA40) and the SA30 CHANGELOG entry.
- 2026-07-07 (roadmap cleanup) — **TA34: resolved** (SA35 — `Post.author`/`ContactNote.created_by`/`DealNote.created_by` changed `CASCADE`→`SET_NULL`; `OrganizationInvitation.invited_by`'s CASCADE documented as intentional in `decisions.md`; new `TestUserFkDeleteRuleConformance` cross-module gate closes the matching tooling gap below). **TA17: resolved** (SA37 — admin backup create/prune moved to background dispatch via `dispatch_background_create()`/`dispatch_background_prune()`, following the SA20/SA43 restore-dispatch pattern; restore itself was already resolved by SA20). **TA35: resolved** (SA36 — `get_client_ip()` guard changed to `len(ips) >= TRUSTED_PROXY_COUNT`, index to `ips[-TRUSTED_PROXY_COUNT]`, matching DRF's `NUM_PROXIES` semantics; landed before SA21.2 consumes the helper). Findings-table counts updated (S2 1→0, S3 4→2); full detail for all three lives in CHANGELOG.md (SA35/SA37/SA36 entries).
- 2026-07-07 (re-run, HEAD `1e618ed8`) — **TA18: resolved** (SA21.2, `3e48d04f` — shared canonical `get_client_ip()` added to `orgs/current_org.py`; blog API limiter ident (`blog/views.py:328`), forms `FormSubmission.ip_address` (`forms/views.py:231,257`), and `FormSubmitThrottle.get_ident` all switched off raw `REMOTE_ADDR`; verified in code. Residual: the helper's `getattr`-default settings reads opened as **TA43**). **TA37: resolved** (SA38, `16ede27a` — `is_restore_stale()` + CAS `reset_stale_restore()` in `services.py`, admin list column `stale_restore_warning` + guarded `reset_stale_restore_action`, stale-aware guidance on both upload-path guards (`services.py` + `orchestration.py` CR-SA38-001 parity); CAS verified unable to overwrite a concurrently finishing child. Residual: threshold-literal duplication opened as **TA45**). **TA39: resolved** (SA41, `2305591f` — `cancel_current_subscription` raises distinct `BillingSubscriptionAnomalyError` for the missing-Stripe-id case; `AccountDeleteView` logs it at WARNING with user/org identifiers and proceeds; `CancelSubscriptionView` maps it to 400; verified end-to-end). **TA40: still-open** (all four location groups re-verified byte-identical; SA42 scheduled on Track 3 — carried, not re-argued). **TA42–TA46: opened this pass** (TA42/TA43/TA44 accepted from arch-audit red-flag hand-off after independent verification; TA45/TA46 found reading the SA38/SA43 delta in full).
- 2026-07-07 (roadmap cleanup) — **TA42: resolved** (SA52 — `_get_manage_py()` now raises `BackupError` instead of swallowing resolution failure and falling back to a bare `"manage.py"` literal; the fail-hard raise happens before `_atomic_claim_restore`, so a resolution failure never leaves an artifact claimed; 5 regressions in `TestGetManagePySA52`). **TA43: resolved** (SA48 — `get_client_ip()` reads `USE_X_FORWARDED_FOR`/`TRUSTED_PROXY_COUNT` via direct required access, raising `ImproperlyConfigured` on missing/invalid values instead of silently defaulting). **TA44: resolved** (SA51 — `backups/services.py:1-10` header rewritten to state the real division of responsibility; no more false "under 400 LOC" claim). Findings-table counts updated (S3 1→0, S4 5→3); full detail for all three lives in CHANGELOG.md (SA52/SA48/SA51 entries). TA45 remains open (SA54 scheduled on Track 2, not yet landed); TA46 open (SA53 partial, short-write handling pending CR-SA53-REV-002).
- 2026-07-08 (docs cleanup) — **TA40: resolved** (SA42 — all four post-hook locations switched to direct required reads; 16 regression tests added. Full detail in CHANGELOG.md). Findings-table counts updated (S4 3→2); counts and status summary updated in this document.
- 2026-07-08 (doc-review follow-up) — **TA46: resolved** (SA53 + CR-SA53-REV-002 complete — the fd-based short-write retry loop replaces the interim `.tmp`+`os.replace` copy path from the initial SA53 fix. The final seam uses `mkstemp` for the fd, `os.write` in a `memoryview`-slicing retry loop, a single `finally: os.close(fd)`, and `except: os.unlink(tmp_path)` cleanup. `TestPrepareAdminUploadedRestoreArtifactSA53` covers copy-failure, happy-path, and short-write-retry regressions on the `mkstemp`+fd write path — 3 tests total. Full detail in CHANGELOG.md CR-SA53-REV-002 entry.) Findings-table counts updated (S4: 2→1).
- 2026-07-09 (re-run, HEAD `198a1951`) — **TA45: resolved** (SA54, `4b57c264` — `restore_admin_uploaded_backup` takes `stale_threshold_minutes` as a parameter; the admin caller passes `services.STALE_RESTORE_THRESHOLD_MINUTES` explicitly (`backups/admin.py:441-443`), so the canonical constant lives only in `services.py:554`. Residual noted, not promoted: the engine signature keeps a `= 30` default (`orchestration.py:2790`) — dead for the only live caller, but a future caller omitting the argument silently reintroduces the drift; consider making the parameter required). **TA47–TA52: opened this pass** — TA47 (S2) `dr-media-storage-fallback-swallows-misconfiguration`, TA48 (S3) `rls-boot-guard-misses-superuser`, TA49 (S3) `test-tooling-auto-primes-bypassrls-hatch`, TA50 (S3) `composite-fk-deferability-contract-diverged`, TA51 (S4) `test-artifacts-committed-again` (TA23 class), TA52 (S4) `module-pyproject-splice-unvalidated`. Four of the six (TA47, TA49, TA50, TA51) trace to the unreviewed CI-fix commits `6ea37301`/`198a1951` — see Structural smells. The SA42–SA56 review-tracked delta itself came through clean.
- 2026-07-10 (module-by-module deep pass, core and cli included as modules) — **zero new findings.** All 13 modules plus `quickscale_core` and `quickscale_cli` read at their live surfaces (see Per-module verdicts) — every module clean. TA47/TA48/TA50/TA51/TA52 re-confirmed at their locations during the pass (no change). Empirical check added: PostgreSQL 18 verified `SET CONSTRAINTS <name> IMMEDIATE` on a `NOT DEFERRABLE` FK is a no-op, retracting a stronger test-breakage hypothesis for TA50 (the crm `SET CONSTRAINTS ... IMMEDIATE` tests still pass; their comments are merely stale). Secondary items recorded inside existing findings rather than as new IDs: billing `credit_user` re-verified idempotent (in-lock check + unique constraint + `IntegrityError` re-fetch); notifications webhook re-verified HMAC+TTL+constant-time+idempotent; `TenantManager` fail-closed and `TenantMiddleware` fail-closed re-verified; `storage.sanitize_relative_media_path` exported but has no first-party caller (dead-ish, not promoted).
- 2026-07-10 (SA58 closeout) — **TA48: resolved** (SA58 — RLS boot guard now queries `rolbypassrls OR rolsuper`; error message reports SUPERUSER/NOSUPERUSER alongside BYPASSRLS/NOBYPASSRLS; test mocks and assertions updated; findings table and counts aligned). Findings-table counts updated (S3: 3→2, total: 6→5).
- 2026-07-10 (SA57/61/62 closeout, doc-consistency correction) — **TA47: resolved** (SA57 — both DR media call sites (`orchestration.py:_resolve_media_runtime`, `_sidecar.py:_build_media_sync_manifest`) now catch only `ImportError`/`ModuleNotFoundError` as the module-absent fallback; real `select_storage_backend` errors (`ImproperlyConfigured` etc.) propagate as `BackupConfigurationError`/an explicit error-status manifest instead of silently coercing to local `MEDIA_ROOT`; the flipped fail-closed test was restored and a second test pins the module-absent fallback). **TA51: resolved** (SA61 — `pytest_log.txt`, `coverage.json`, `pytest_cov_log.txt`, and the 13 accumulated blog test-upload PNGs untracked via `git rm --cached`; `.gitignore` extended; blog test `MEDIA_ROOT` now points at a tmp path so the class can't reaccrete). **TA52: resolved** (SA62 — `_patch_module_path_dependencies`'s bare `write_text()` now routes through `_write_validated_toml`, matching its two sibling writers). This entry corrects the findings-summary table above, which had drifted stale (still marking all three "open" despite CHANGELOG confirming SA57/SA61/SA62 landed on 2026-07-10) — caught during the roadmap-reconciliation pass for SA57–SA64. Findings-table counts updated (S2: 1→0, S4: 2→0, total: 5→2). Remaining open: TA49 (SA59), TA50 (SA60), both scheduled on Track 1.
- 2026-07-10 (V2-prompt re-run, HEAD `ae8c386e`) — **TA49: still-open** (Makefile:325-326, `scripts/test_unit.sh:365-366`, `ci.yml:340` all re-verified unchanged; SA59 scheduled). **TA50: still-open** (`tenancy.py:906` re-verified unchanged; SA60 scheduled). **TA53: opened** — `apply-subprocess-env-pythonpath-pollution` (S3, from side-channel commit `628c7d28`). **Closure verification per V2 §2f.3:** TA47 (SA57), TA48 (SA58), TA51 (SA61), TA52 (SA62) — each fix location opened and confirmed complete in code, including SA57's restored fail-closed tests; no regressed closures. Full first-party production diff `198a1951..HEAD` read; SA63/SA64 verified clean (SA63 additionally resolves the prior `local.py.j2` argv-sniffing watch item); the auth→orgs manifest implication in `628c7d28` verified justified (auth views import orgs models since SA47) though undocumented (Structural smells). Empirical check: simulated wheel-install layout confirms `_build_quickscale_env` sweeps site-packages-style directories into child `PYTHONPATH`, refuting its docstring (TA53 evidence). This is the first pass run under tech-audit-prompt V2.
- 2026-07-10 (roadmap cleanup) — SA69 closed: `decisions.md §ImproperlyConfigured-Exception-Identity` now records the exception-identity split; the adapter-docstring doc-drift flagged in the Notes section below is corrected. The lint/naming guard remains an open watch item per the decision record, not a defect. `roadmap.md` had left SA63 and SA69's checklist entries in place after both closed (already CHANGELOG-documented) — pruned there as part of this pass.
- 2026-07-11 (roadmap cleanup) — **TA53: resolved** (SA65 — `apply_command.py`'s dev-context `PYTHONPATH` env is now built on-demand via `_build_quickscale_env()` and passed only to the two nested `sys.executable -m quickscale_cli.main` invocations; the module-level `_QUICKSCALE_SUBPROCESS_ENV` import-time cache is removed; `_run_command` defaults to `env=None` so foreign subprocesses — poetry, git, docker, the generated project's own `manage.py` — inherit the parent env unmodified; the docstring's false production-safety claim is corrected). `TestSA65SubprocessEnvScoping` proves the scoping. Findings-table counts updated (S3: 3→2). Full detail in CHANGELOG.md (SA65 entry). This closes the tech-audit hand-off to arch-audit's matching red flag (`apply`'s import-time subprocess-env snapshot), reconciled there too.
- 2026-07-11 (V3-prompt re-run, HEAD `53a657d6`) — **TA49: resolved** (SA59.1 — verified in
  code per §2f.3: the blanket `QUICKSCALE_ALLOW_BYPASSRLS=1` export removed from both `Makefile`
  (module path now fail-louds) and `scripts/test_unit.sh` (module loop moved to
  `scripts/test_integration.sh`, which documents "No blanket QUICKSCALE_ALLOW_BYPASSRLS=1 here");
  `ci.yml`/`publish.yml` provision `quickscale_test_role` NOBYPASSRLS/NOSUPERUSER with attribute
  verification and run the integration gate with `QUICKSCALE_ALLOW_BYPASSRLS=0` + `QS_*_DB_USER`
  wiring — TA49's exact prescribed fix. Residual red-gate state opened separately as TA57;
  SA59.2–SA59.4 residuals tracked in roadmap.md, not here). **TA50: still-open**
  (`tenancy.py:900-906` re-verified byte-identical; SA60 scheduled). **TA53 closure verified in
  code** (see 2026-07-11 entry above — confirmed this pass per §2f.3). **TA54–TA57: opened this
  pass** — TA54 (S1) `org-creation-crm-seeding-fails-under-force-rls` (production-path defect
  exposed by SA59.1's restricted-role gate; concealed by TA55+TA57, see chain), TA55 (S3)
  `orgs-conftest-autouse-signal-muting` (checkpoint commit `2b9afa6b`), TA56 (S3)
  `session-adapter-fixture-swallows-improperlyconfigured` (quality-fix commit `fc3dc00c`), TA57
  (S3) `integration-gate-red-at-merge` (tracked SA59.1 state; quarantine recommended). TA55–TA57
  arrived as arch-audit red-flag hand-offs and passed independent verification; TA54 was found by
  pulling the thread behind TA55's docstring. Fix-regression pass run over SA65/SA66/SA68/SA69:
  clean (SA68's persistent-env cell recorded as a watch item, not a regression). First pass run
  under tech-audit-prompt V3.
- 2026-07-12 (roadmap closeout pass) — **TA54: resolved** (SA74 — `ensure_org_default_stages`
  primes tenant ContextVar across the helper scope and wraps `_seed_default_stages`'s INSERTs in
  `org_scope(organization)`, so the CRM receiver establishes its own tenant context regardless of
  caller; new regression test `test_seeds_without_ambient_org_context` proves seeding succeeds
  with zero ambient context under the restricted role). **TA55: resolved** (also SA74 — the orgs
  conftest's autouse `_mock_org_created_signal` fixture is removed and replaced with a non-autouse
  opt-in `mock_org_created_signal`, restoring the org-creation seam to real coverage in the orgs
  suite). **TA56: resolved** (SA75 — `_session_managed_adapters` now swallows only a genuine
  missing managed-package-root import and re-raises broken-adapter import failures, with the full
  adapter registry asserted in CI; two follow-up review passes, CR-SA75-REV-001/002, hardened the
  root-package-missing detection further). **TA57: resolved** (SA76 — a ticketed quarantine
  mechanism in `scripts/test_integration.sh` absorbs the two remaining known restricted-role
  failures (orgs → SA77, notifications → SA78, both resolved/tracked separately) so the
  integration gate is green for everything else; forms `0007`'s composite-FK piece was already
  resolved by SA60, so it needed no quarantine entry). **TA50: resolved** (SA60 — the composite-FK
  helper's `NOT DEFERRABLE` emission is now the ratified project-wide policy; `forms/0007`'s
  inlined SQL and its test were aligned to match, and a new cross-module conformance gate checks
  all six known composite FKs). Findings-table counts updated (S1 1→0, S3 4→0, total 5→0 — **zero
  open findings**). Two non-blocking follow-ups spawned by SA76's quarantine removal remain open on
   `roadmap.md`, not here: **SA77** (orgs' 9 restricted-role failures, root cause established and
   code fix landed 2026-07-12; final restricted-role verification blocked on SA79) and **SA79**
   (forms `0007` backfill data mismatch, distinct from the deferability contract SA60 already
    fixed; reopened/blocked on CR-PLAN-SA79-004 and CR-PLAN-SA79-005).
- 2026-07-13 (SA82 completed) — **SA77 and SA79: resolved.** SA82 removed the SA76 quarantine entries and ran the full `make test-integration` gate end-to-end. Orgs 847 passed/11 BYPASSRLS-skips/0 failed (93.04% coverage), notifications 39 passed/0 failed (91.76% coverage), overall mean coverage 92.95% passed. SA77's code fix (2026-07-12) verified live under the unquarantined gate; SA79's forms 0007 backfill and notifications acceptance confirmed under the full gate. Both are closed. Three independent restricted-role findings surfaced by the quarantine removal remain open on `roadmap.md` — **SA84** (CRM, 67 RLS failures/20 skipped) on Track 1, **SA85** (forms residual, 33 RLS failures/8 skipped/10 errors) and **SA86** (listings, 6 RLS failures) on Track 2 — not tech-audit findings, per this document's convention that roadmap-tracked work is not duplicated here. **SA83** (blog, 86 RLS failures) implementation/validation complete; closed after independent review. SA80.3b (backups rerun) resolved — see SA80.3b/SA87 reconciliation entry below. See CHANGELOG.md's SA82 entry for detail.
- 2026-07-13 (SA80.3b/SA87 reconciliation): SA80.3b rerun completed — 0 missing-`pg_dump`/`pg_restore` failures remain (retained-role: 298 passed/1 failed/2 skipped; default-user: 299 passed/2 skipped). SA80.3/SA80.3b resolved — no longer an open gate failure. The 1 retained-role residual is tracked as SA87 on roadmap.md §Track 3. Current open restricted-role findings keeping the integration gate red: SA84–SA86. SA83 closed after independent review. SA81 (per-module lockfiles, no deps) is unrelated cleanup; does not affect the gate. See roadmap.md for current status.
- 2026-07-13 (V3-prompt delta re-run, HEAD `41689be7`, prior `53a657d6`) — **zero new findings.**
  Full first-party production diff `53a657d6..HEAD` read (SA60/SA70/SA74/SA75/SA76/SA77/SA78/SA79/
  SA80/SA82/SA87 remediation + test/docs). **No prior findings to re-verify** — all TA IDs were
  already reconciled resolved as of the 2026-07-12 pass; none regressed (spot-checked SA74's
  `ensure_org_default_stages` and SA60's `NOT DEFERRABLE` emission still present in code).
  Fix-regression pass (§3.6): SA74 verified sound and complete (ContextVar + `org_scope` + AF9
  GUC-leak cleanup with correct attribute names; CRM is the sole `organization_created` receiver, so
  no sibling carries the TA54 class); SA70 `pre_delete` backstop verified to break no legitimate
  cascade path (account-deletion pre-check guards `user.delete()`; purge uses `_raw_delete`; no ORM
  `organization.delete()` cascade path exists); SA79/SA60 forms `0007` and SA80 CLI Poetry-env
  isolation verified sound. Test-integrity diff (§3.7): all delta test changes are strengthenings or
  SA59.2 PostgreSQL-seam adaptations — no weakened/flipped tests (the TA55 autouse muting removal is
  a strengthening). Chain pass (§3.9): no new chains. SA83–SA86 (restricted-role RLS failures),
  SA80.3, SA81 remain roadmap-tracked; structural root owned by arch-audit Finding 8
  (`module-rls-context-procedural`); not promoted here per convention. Empirical checks: still none
  possible — `psql`/`pg_isready` clients now installed but no PostgreSQL server running.
- 2026-07-14 (roadmap cleanup, status refresh) — **SA85 (forms residual restricted-role failures):
  closed** after independent review (CR-SA85-REV-001 resolved; `force_authenticate` session/org-context
  contamination fixed; forms 196 passed/8 skipped/12 e2e deselected/0 failed). The masthead/orientation
  prose above (dated 2026-07-13) that lists SA85 among the open gate-red findings is historical — the
  **current** roadmap-tracked findings keeping the SA82 integration gate red are **SA84** (CRM) and
  **SA86** (listings) only, both gated behind **SA88** (Finding 8 Option 1, in flight). Still no
  tech-audit finding: SA88's CRM triage bucketed 0 runtime-query failures (67 fixture-time), confirming
  no production-severity NOBYPASSRLS read-path gap. Not tech-audit findings per this document's
  roadmap-tracked convention; recorded here for status accuracy.

## Notes (not violations, watch items)

- **SA68 persistent-misconfiguration cell (new):** an operator who *persistently* sets
  `QUICKSCALE_PRIVILEGED_COMMAND=migrate` **and** `RUNTIME_DATABASE_URL=""` in the deployment
  environment would serve traffic under the superuser `DATABASE_URL` with the orgs boot guard
  exempted — RLS silently inert. Two simultaneous misconfigurations against documentation that
  repeats "one-shot inline prefix — never persistent configuration" in four places, and the
  normal serving config (`RUNTIME_DATABASE_URL` set to a real URL) fails loudly if the var is
  added to it. Same accepted shape as the SA63 bridge; watch, don't fix — unless a cheap
  belt-and-braces lands naturally (e.g. the boot guard cross-checking that a manage.py command
  matching the env var is actually running).
- **mypy weakening for backups (new, `fc3dc00c`):** `ignore_missing_imports = True` added to
  `[mypy-quickscale_modules_backups.*]` with no note. Small and plausibly needed by the new
  sibling-`MYPYPATH` typecheck wiring, but it is the only module with the flag — watch that it
  doesn't spread module-by-module as the quiet fix for import-resolution noise.
- **Two same-named `ImproperlyConfigured` classes coexist** (SA69 decision recorded): carried —
  the lint/naming guard remains deferred; all current raise/catch pairs consistent. TA56 is an
  instance of the *catch-the-wrong-breadth* risk this note predicted, though with the correct
  class.
- **`test_update_auto_commits_each_module_e2e` mocks `_sync_module_dependencies`** — carried
  (628c7d28); the update e2e remains weaker than its name implies.
- **auth's orgs pyproject cap `<0.87.0`** — carried; nothing gates the pair when orgs bumps.
- **SA47 sole-member self-removal orphans the org (deliberate):** carried.
- **Stripe call inside the SA47 atomic block:** carried; client timeout is the cheap mitigation.
- **`reset_stale_restore` `None`-`restore_started_at` edge:** carried — unreachable from the only
  caller.
- **`normalize_notifications_module_options` empty→full-defaults materialization:** carried —
  documented manifest-boundary behavior.
- **Storage legacy-credential conversion is deliberate:** carried (SA29).
- `orgs/public_context.py:66,132`: `except Exception → None` on system-org lookup is
  **fail-closed** — carried.
- DR engine fallback modes are by-design recovery behavior, exempt per §fail-hard-principle —
  carried.
- Analytics runtime missing-API-key → silent disable is the deliberate SA17.7 shape — carried.
- `subprocess.Popen` in the dispatchers is never `wait()`ed — carried; at most one transient
  zombie per dispatch.
- Malformed staff-authored validation rules surface as field-level 400s (SA40) — carried.
- **SA59.1 restricted-role known failures — mostly resolved (2026-07-12):** forms `0007`'s
  composite-FK contract issue closed via SA60 (TA50); notifications' duplicate-db issue closed via
  SA78; the residual forms backfill bug was SA79 (closed 2026-07-13 by SA82); orgs' 9 restricted-role failures
  were SA77 (closed 2026-07-13 by SA82 — code fix verified live under the full unquarantined gate). TA57's gate-red consequence closed via
  SA76's quarantine mechanism. See `roadmap.md` for SA83–SA86 tracking.
- **SA83 (blog restricted-role, 86 RLS failures) — implementation/validation complete 2026-07-13; closed after independent review.** Three root causes: (1) unscoped blog test setup across nine blog test files — every tenant INSERT/read needed matching `blog_org_scope(org)` for FORCE RLS compliance; (2) missing `_resolve_api_org` context priming — token-auth blog API paths didn't set the ContextVar before ORM ops; (3) stale AF9 priming memo on GUC reset — `org_scope()` exit reset the GUC but left the per-transaction memo, preventing re-priming when the same org was re-resolved. Phase 4 shared orgs fix (`_clear_priming_memo` in `current_org.py`) applies to all modules, not just blog. Outcome: blog 211 passed/0 failed, coverage 91.62%, no quarantine. Orgs 850 passed/11 BYPASSRLS-skips/0 failed, 93.08% coverage. Overall mean 93.55%. Exit 1 from `make test-integration` reflects only independent residuals (SA84–SA86). SA83 closed after independent review. See CHANGELOG.md v0.87.0 SA83 entry for full detail.
- **SA84–SA86 restricted-role RLS failures keep the integration gate red — roadmap-tracked, not a
  tech-audit finding (carried 2026-07-13):** CRM/forms/listings cross-org data migrations and
  fixtures acquire no `operator_access` context, so they fail under `quickscale_test_role`
  (NOBYPASSRLS). arch-audit Finding 8 (`module-rls-context-procedural`) owns the structural root.
  Per arch-audit's analysis these are predominantly **test-posture** (production `migrate` runs under
  the SA68 privileged one-shot superuser-class role, so backfills succeed in prod). **The one open
  question that could become a tech finding** is arch-audit's "bucket 3": whether any *runtime* read
  path that also runs NOBYPASSRLS in production is missing its RLS context. Verification step (now
  that a `psql` client exists, once a PG server is available): run one module's restricted-role suite
  (`QS_BLOG_DB_USER=quickscale_test_role … pytest quickscale_modules/blog`) and bucket the failures
  into migration-time / fixture-time / runtime-query — only the third is production-severity and, if
  found, is promoted to a new TA ID. Watch, don't duplicate the roadmap tickets.
