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

**Sampled:** the 53-site `getattr(settings, …, <default>)` census across all modules; subprocess-timeout and `rmtree`/`unlink` censuses across all first-party source; `poetry.lock` pins for the security-relevant packages; CLI destructive paths; generated settings templates at the TA68 anchors.

**Skipped:** the React theme component bodies and `scripts/` gate internals (both read at depth by the prior passes this cycle); generated-project migrations; pylint/radon/vulture internals.

**Audit tools run (read-only):** `git log` / `git diff` / `git rev-parse` over the delta; CPython 3.14 for the two empirical checks below. No scanner was re-run this pass — the Trivy/Bandit gate is CI-owned and its ledger was read rather than re-executed.

**Empirical checks run (§1e) — 2, both side-effect-free:**

| # | Check | Result |
|---|---|---|
| 1 | Re-implemented `getCsrfToken`'s exact split-and-count logic in CPython and ran it over five cookie shapes | **Confirmed TA67** — `'csrftoken=A; csrftoken=B'` and `'csrftoken=A; sessionid=x; csrftoken=B'` both return `''`; single and sibling cases return `'A'` |
| 2 | Parsed `TENANT_TABLE_REGISTRY` and cross-checked every ENROLLED entry's convention-derived table name (`app_label + '_' + model_name.lower()`) against the explicit `db_table` declarations in all module `models.py` | **Refuted** a suspected fail-silent-skip finding in `refresh_force_rls_policies` — 45 entries (21 ENROLLED / 24 EXCLUDED_REVIEWED), 8 explicit `db_table` declarations, **zero divergence** from the convention. Carried as a watch item instead |

---

## Summary table

| ID | Sev | Category | Title | Effort | Confidence | Status |
|---|---|---|---|---|---|---|
| `spa-csrf-token-duplicate-cookie` (TA67) | **S3** | Correctness (frontend) | `getCsrfToken` returns `''` whenever two `csrftoken` cookies are present — every SPA write 403s | Trivial ⚡ | High | still-open |
| `backup-lock-stale-clear-toctou` (TA71) | **S3** | Concurrency | Stale-lock clearing is `stat`-then-`unlink`, so two backup runs can both acquire the "exclusive" backup lock | Small | High (race) / Medium (cost) | new |
| `generated-settings-dead-client-ip` (TA68) | S4 | Dead code (generated output) | Two `get_client_ip` definitions in generated settings are unreachable | Trivial | High | still-open |
| `force-rls-apply-idempotency-claim` (TA72) | S4 | Documentation vs. behaviour (security-adjacent) | `apply_force_rls` documents itself as idempotent; `CREATE POLICY` has no `IF NOT EXISTS`, so a second call raises | Trivial | High | new |

**Counts:** S1 **0** · S2 **0** · S3 **2** · S4 **2** · **Total 4 open.** Quick wins (⚡ Trivial-effort S3/S4): TA67.

---

## Findings

### TA67 — SPA CSRF token lookup returns empty whenever two `csrftoken` cookies exist

**ID:** `spa-csrf-token-duplicate-cookie`

**Severity:** **S3.** A latent bug that needs one precondition — a duplicate `csrftoken` cookie — after which **every** state-changing request from the React SPA fails with 403 and the app is read-only. Deployment reality #3 (the generated project, internet-facing). Fails closed, so it is availability, not a security hole. Reachability drops one notch for the single unverified precondition.

**Category:** §4.I Correctness (§4.X frontend). **Confidence:** High — logic verified by reading and re-confirmed empirically this pass (check #1).

**Location:** `…/themes/showcase_react/src/hooks/useApi.ts:20-28` and `…/src/components/forms/FormRenderer.tsx:206-211` — the same eleven lines, duplicated. Both re-verified at HEAD.

**Defect:** The parser splits the cookie string on the delimiter `"; csrftoken="` and accepts the result **only when it yields exactly two parts**, returning `''` otherwise. Two `csrftoken` cookies yield three parts.

**Failure scenario:** The project is served at `app.example.com` while a `csrftoken` cookie also exists for `.example.com` — the ordinary outcome of setting or later changing `CSRF_COOKIE_DOMAIN`, of running a sibling Django app on another subdomain, or of a stale apex-scoped cookie surviving a domain-scope change. The browser sends both, `document.cookie` becomes `…csrftoken=A; csrftoken=B…`, `parts.length === 3`, `getCsrfToken()` returns `''`, `buildRequestHeaders` (`:89-94`) skips `X-CSRFToken` because the token is falsy, and Django rejects every POST/PUT/PATCH/DELETE with 403. Forms submission, org creation, settings changes, and CRM writes all fail; GETs keep working, so the app looks alive and merely refuses to save. No error names the cause.

**Evidence:**

```ts
// useApi.ts:20-28
function getCsrfToken(): string {
  const name = 'csrftoken'
  const value = `; ${document.cookie}`
  const parts = value.split(`; ${name}=`)
  if (parts.length === 2) {
    return parts.pop()?.split(';').shift() ?? ''
  }
  return ''
}
```

`FormRenderer.tsx:206-211` is the same function with the body on one line. There are exactly two copies in the theme.

**Refutation:** Searched for a layer-up guard and found none — there is no shared CSRF helper, no axios/fetch interceptor, and no template-injected token: `buildRequestHeaders` is the only place `X-CSRFToken` is set, and `FormRenderer` sets its own. Considered whether Django's `CsrfViewMiddleware` accepts the token from the POST body as a fallback — it does, via the `csrfmiddlewaretoken` field, but the SPA sends JSON bodies and never that field. Considered whether the `?? ''` branch is the real bug rather than the length check — it is not; with two parts the parse is correct, and the length check is what discards the three-part case. Considered `window.__QUICKSCALE__` as a token source — `validateQuickScaleSeam.ts` carries no CSRF key.

**Fix:** Replace both copies with one shared helper that iterates cookies rather than counting split segments — split `document.cookie` on `'; '`, find the first entry whose name is exactly `csrftoken`, and `decodeURIComponent` its value (Django's own documented `getCookie`). Export it from `src/lib/` and import it in both call sites, so the next consumer does not copy a third variant. **Effort:** Trivial.

**Verification:** Unit-test the helper against `'csrftoken=A; csrftoken=B'`, `'sessionid=x; csrftoken=A'`, `'csrftoken=A'`, and `''`; the first three must return a non-empty token. `vitest` already runs in this theme (`vitest.config.ts`, `src/test/`).

**Deliberate?** None found. The `parts.length === 2` idiom is a widely copied snippet; nothing in either file acknowledges the multi-cookie case.

**Age:** Long-standing; carried unchanged from the 2026-08-22 pass and unmodified in the delta.

---

### TA71 — Stale backup-lock clearing is `stat`-then-`unlink`, so two runs can both hold the "exclusive" lock

**ID:** `backup-lock-stale-clear-toctou`

**Severity:** **S3.** The guard whose entire stated purpose is to "prevent overlapping backup runs" can fail to do so. Deployment reality #3 (the generated project's backups module). Two preconditions must both hold — a pre-existing stale lock, and a sub-millisecond interleaving between two starts — so reachability drops two notches from the impact ceiling; no data-corruption path was verified (see *Refutation*), which is what holds this at S3 rather than higher.

**Category:** §4.II Concurrency (check-then-act / TOCTOU).

**Confidence:** **High** that the race exists (verified by reading the two functions together and walking the interleaving line by line). **Medium** on its cost, because the worst outcome — a concurrent prune deleting the other run's artifact — is inferred from the prune call site rather than executed.

**Location:** `quickscale_core/src/quickscale_core/dr_engine/_lock.py:119-137` (`_clear_stale_backup_lock`), reached from the acquire loop at `:75-86` (`_acquire_backup_lock`), taken by `_backup_creation_lock` at `dr_engine/orchestration.py:1113` and `:1321`.

**Defect:** `_clear_stale_backup_lock` reads the lock file's mtime, decides staleness, and *then* unlinks — with no atomicity between the two steps. A second process that sampled the same stale mtime a moment earlier can unlink the **fresh** lock a winner has since created, after which both processes successfully `O_EXCL`-create and both believe they hold the lock.

**Failure scenario:** A previous backup crashes (container OOM, Railway redeploy mid-dump), leaving `.quickscale-backup-create.lock` behind with an mtime older than `_LOCK_TIMEOUT_SECONDS` (300 s). An operator clicks **Create backup now** in the `BackupPolicy` admin (`backups/admin.py:694` `create_backup_now`) at the same moment a scheduled `backups_create` management command fires. Both hit `FileExistsError`; both call `_clear_stale_backup_lock`; both `stat()` the old lock and judge it stale. Process A unlinks and re-creates the lock, entering the critical section. Process B — already past its own `stat()` — then executes `unlink()` at `:130`, deleting **A's live lock**, and its own `O_EXCL` create at `:77` succeeds. Two `pg_dump` runs now proceed concurrently against the same PostgreSQL 18 instance. Each mints a distinct `snapshot_id` and `snapshot_root`, so their dump files do not collide, but each run ends in `_complete_capture_after_dump`, whose final step is a prune — a retention pass evaluating a set that now contains another run's just-registered artifact.

**Evidence:**

```python
# _lock.py:119-137 — the check and the act are two separate syscalls
def _clear_stale_backup_lock(lock_path: Path, *, now: datetime) -> bool:
    try:
        lock_mtime = lock_path.stat().st_mtime      # <-- check
    except FileNotFoundError:
        return True
    if (now.timestamp() - lock_mtime) <= _LOCK_TIMEOUT_SECONDS:
        return False
    try:
        lock_path.unlink()                           # <-- act (may remove a *different*, live lock)
```

The acquire loop retries exactly twice around it:

```python
# _lock.py:75-83
for _ in range(2):
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        if not _clear_stale_backup_lock(lock_path, now=lock_time):
            raise BackupLockError(...)
```

Note that `now=lock_time` is captured **once** before the loop (`:73`), so the staleness comparison on the second iteration is evaluated against a timestamp taken before the first attempt — widening, not narrowing, the window.

**Refutation:** Attempted three ways, and the finding survived all three, though the third bounds its severity.
(1) *Is the `O_EXCL` create itself sufficient?* No — `O_EXCL` makes creation atomic, but nothing binds the unlink to the file the caller inspected. The benign interleavings (B stats *after* A re-creates; B stats during the gap and fails on the second `O_EXCL`) were both walked and do terminate correctly with `BackupLockError`; only the stat-before/unlink-after ordering escapes, and nothing excludes it.
(2) *Is there a second guard one layer up?* Searched `orchestration.py` for a DB-level backstop — no `pg_advisory_lock`, no `select_for_update` on the policy row, and no unique constraint or status check preventing two concurrent `pending` snapshots. `create_backup` at `:1321` goes straight from the filesystem lock into `create_snapshot`.
(3) *Does the race actually corrupt anything?* This is the argument that partly succeeds and is why the severity is S3, not S2: `_mint_snapshot_id()` gives each run its own id and `_build_snapshot_local_root` its own directory, so the two dumps do not overwrite each other. The residual risk is contention (two simultaneous `pg_dump` runs against one Railway PostgreSQL service) plus the concurrent prune, which is reachable but unproven.
The sibling implementation `AdvisoryLock.clear_stale` (`advisory_lock.py:272-296`) has the identical `is_stale()`-then-`unlink()` shape; it is documented operator-facing API (module docstring `:17-19`) with no automated caller, so it is folded in here as a second location rather than filed separately.

**Fix:** Replace the stale-file dance with an OS-level lock that cannot go stale: open the lock file `O_CREAT|O_RDWR` (no `O_EXCL`) and take `fcntl.flock(fd, LOCK_EX | LOCK_NB)`, holding the descriptor for the critical section. The kernel releases the lock when the process dies, which deletes the entire stale-detection code path — `_clear_stale_backup_lock`, `_LOCK_TIMEOUT_SECONDS`, and the retry loop all go away. If the file-based scheme must be kept for portability, make the clear atomic instead: `os.open` the existing lock, `os.fstat` **that descriptor** for the mtime, and unlink only after confirming `st_ino` still matches the inode just inspected. Apply the same change to `AdvisoryLock.clear_stale`. **Effort:** Small.

**Verification:** A test that seeds a stale lock file, then drives the documented interleaving with two threads synchronised on a barrier placed between the `stat` and the `unlink` (inject via a seam or `monkeypatch` on `Path.unlink`), asserting exactly one caller reaches the critical section and the other raises `BackupLockError`. With `flock`, the same test passes without any injected barrier.

**Deliberate?** None found. The docstring at `:120` states the intent as "Remove an expired lock file so a new backup run can proceed" with no acknowledgement of concurrent clearing; no comment, suppression, or test addresses the race.

**Age:** Long-standing — present in `_lock.py` since the DR-engine split; untouched by the delta.

---

### S4

- **TA68 · `generated-settings-dead-client-ip`** · `…/templates/project_name/settings/base.py.j2:61` and `settings/production.py.j2:123` · Both files define a module-level `get_client_ip(request)`, and `production.py.j2` rebinds it with a comment claiming the rebind exists "so that production defaults … are actually in effect at request time". Neither is reachable in a generated project: Django's `Settings` copies only **uppercase** names off the settings module, so `django.conf.settings.get_client_ip` does not exist, and nothing in the generated tree imports either function — re-verified at HEAD, a grep across all templates still returns only the two definitions and the comments referring to them. The real consumer is `quickscale_modules_orgs.current_org.get_client_ip`, which reads the uppercase `USE_X_FORWARDED_FOR` / `TRUSTED_PROXY_COUNT` settings dynamically and is correct. · **Fix:** delete both definitions and keep the settings plus the `REST_FRAMEWORK["NUM_PROXIES"]` recomputation, or add a comment pointing at the orgs helper as the live implementation. The behavioural comment in `production.py.j2:119-122` is misleading as written and should go either way.

- **TA72 · `force-rls-apply-idempotency-claim`** · `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py:536-546` · `apply_force_rls`'s docstring states "**Idempotent** — wraps each pair in the identical ENABLE + FORCE + CREATE POLICY sequence." The body executes `_FORCE_RLS_FORWARD_SQL`, which issues bare `CREATE POLICY {policy_name}` and `CREATE POLICY {policy_name}_select` (`:510`, `:521`). PostgreSQL has no `CREATE POLICY IF NOT EXISTS`, so a second application against a table that already carries the policies aborts the migration with `42710 duplicate_object`. The claim is safe today only because the one caller that *does* re-apply — `refresh_force_rls_policies` (`:584`) — calls `revert_force_rls` first, and `_FORCE_RLS_REVERSE_SQL` correctly uses `DROP POLICY IF EXISTS`. The hazard is a future module migration that calls `apply_force_rls` on an already-enrolled table on the documented assurance that doing so is safe. · **Fix:** either correct the docstring to state that the helper is *not* idempotent and must be preceded by `revert_force_rls`, or make it true by prefixing the forward template with the same `DROP POLICY IF EXISTS` pair the reverse template already uses. The second option is two lines and makes the documented contract real. · **Confidence:** High — PostgreSQL's lack of `CREATE POLICY IF NOT EXISTS` is settled behaviour; not executed here because no PostgreSQL instance was started for this read-only pass.

---

## Per-subsystem verdicts

| Subsystem | What was read | Verdict |
|---|---|---|
| Commit delta `602f4be3..HEAD` | all 3 files, production and test hunks, in full | Clean — the assertion removals are a defensible narrowing; see *Clean sweeps* and the reconciliation log |
| orgs — tenant registry & RLS SQL | `tenancy.py` registry, both policy templates, `apply_force_rls` / `revert_force_rls` / `refresh_force_rls_policies`, equality-trigger helpers, `is_tenant_model` → `check_tenant_model_isolation` | **TA72**; the write/read policy split is correct — see *Clean sweeps* |
| orgs — request scoping | `managers.py`, `middleware.py`, `permissions.py`, `current_org.py` GUC layer, `public_context.py` | Clean — fail-closed at every branch examined; see *Clean sweeps* |
| orgs — boot guards | `apps.py` `ready()`, `checks.py` | Clean — one suspected finding refuted, see *Clean sweeps* |
| forms — operator surface | `views.py:140-520`, `throttles.py`, `models.py` settings helpers | Clean — superuser gating is consistent across queryset selection and `operator_access` wrapping |
| billing — credit ledger | `services.py` `debit_user`, `credit_user`, balance helpers | Clean — `transaction.atomic()` + `select_for_update()` + `F()` deltas, integer credits, no float money |
| blog — public read path | `feeds.py` | Clean (one watch item on the double `get_system_org()` resolution) |
| DR engine — locking | `_lock.py` in full; `advisory_lock.py` acquire/release/stale | **TA71** |
| DR engine — orchestration | destructive sites, `create_backup` lock section, admin restore staging/upload pipeline | Clean apart from TA71; the upload path streams via `chunks()` — see *Notes* |
| devtools — beta migration | `beta_migration.py` mutation sites, TOML writer, identity replacement, git guard | Clean — the clean-worktree blocker at `:1457` is the reversal path; see *Clean sweeps* |
| Generated settings templates | `base.py.j2`, `production.py.j2` at the TA68 anchors; `start.sh.j2` launcher contract | **TA68**; the launcher contract is correctly honoured — see *Clean sweeps* |
| Dependency & suppression hygiene | `poetry.lock` security-relevant pins; `scripts/security_suppressions.json` | Clean — SA170's dependency upgrade removed four `sqlparse` suppressions; all 7 remaining suppressions are accountable and unexpired; see *Notes* |

---

## Clean sweeps worth recording

- **The FORCE-RLS policy split enforces the documented read/write asymmetry.** `_FORCE_RLS_FORWARD_SQL` (`tenancy.py:505-527`) creates a `FOR ALL` policy requiring `current_org_id = organization_id` in both `USING` and `WITH CHECK`, plus a separate `FOR SELECT` policy that adds the `operator_access` OR clause. Because PostgreSQL applies UPDATE/DELETE policies conjunctively with the SELECT visibility check, `operator_access` genuinely cannot widen a write — matching the CR-SA14.5-001 comment and `organizations.md:729`. Both policies use the `NULLIF(current_setting(…, true), '')::uuid` form, so an unprimed GUC yields `NULL`, which never equals `organization_id` — fail-closed.
- **`TenantManager` is fail-closed by construction.** `managers.py:38-49`: no org in the ContextVar returns `.none()`, and `super_scope=True` is the only bypass. Verified as the default `objects` manager contract.
- **The GUC priming wrapper handles transaction-boundary reuse correctly.** `_make_priming_execute_wrapper` (`current_org.py:453-563`) memoises per transaction against the **outermost `Atomic` object reference** rather than `id()`, explicitly to defeat CPython address reuse (CR-SA42-001); the autocommit branch clears the memo and wraps each statement in a short `transaction.atomic()` so `SET LOCAL` and the tenant SQL share a scope. `_tenant_context` restores both the ContextVar and the prior GUC on exit via `SET LOCAL` rather than session-scoped `RESET` (CR-AF11-001).
- **`operator_access` is gated, audited, nesting-safe, and fails loudly outside a transaction.** `_get_operator_access` / `_set_operator_access` (`current_org.py:685-745`) raise `ImproperlyConfigured` on PostgreSQL when `connection.in_atomic_block` is false, so a `SET LOCAL` that would silently no-op is impossible (SA39). The context manager saves and restores the prior GUC. Its only HTTP-reachable consumer, `forms/views.py`, gates every use on `_is_superuser()` at both the queryset (`_get_org_bound_queryset:158-177`) and the wrapping (`_with_superuser_operator_access:180-200`), with non-superusers fail-closed to `.none()` when no org is active.
- **Org management routes bypass middleware resolution but not authorization.** `TenantMiddleware._is_org_management_path` lets `/orgs/<slug>/…` through unresolved, and `permissions._resolve_request_org` then resolves the org *from the slug* with no implicit trust — `user_has_org_role` performs the membership and role check. Every mutating view (`MemberListView`, `InviteView`, `RevokeInvitationView`, `OrgSettingsView`) declares `min_org_role = OrgRole.ADMIN`, and the MRO places `OrgRoleMixin.dispatch` after `LoginRequiredMixin`. Unknown segments under `/orgs/` fall through to org resolution rather than bypassing.
- **The `QUICKSCALE_PRIVILEGED_COMMAND` early return was investigated and refuted as a finding.** `apps.py` `ready()` returns before installing the priming wrapper, connecting the SA70 last-owner `pre_delete` backstop, and registering the SA1.3/SA1.4 system checks. Walked each consequence: during `migrate` the connection runs as the BYPASSRLS superuser so priming is moot; data migrations operate on historical model classes, which would not dispatch a `pre_delete` receiver registered against the real `OrganizationMembership` class even if it *were* connected; and the two skipped checks emit `Warning` only. No exposure. The env-var contract itself is honoured — `start.sh.j2:50,61` sets it as an inline command prefix alongside `RUNTIME_DATABASE_URL=""`, and it appears in neither `.env.j2` nor `docker-compose.yml.j2`.
- **The three owners of the privileged-command set currently agree.** The companion structural pass promoted `privileged-command-set-multi-owner` on 2026-08-28, observing that `orgs/apps.py:34` claims to be the SSOT while other deciders exist. Adjudicated here for a *behavioural* divergence, which is what would make it a defect in this document's scope: `orgs/apps.py:34` `_PRIVILEGED_COMMANDS`, `quickscale_cli/.../development_commands.py:44` `_PRIVILEGED_DJANGO_COMMANDS`, and the generated `production.py.j2:185` `_KNOWN_PRIVILEGED_COMMANDS` all currently hold exactly `{"migrate", "createcachetable"}`. Unknown values fail closed in both enforcing owners (`production.py.j2:198` raises; `apps.py:_is_privileged_command` returns `False` and the BYPASSRLS guard runs). `development_commands.py:696` interpolates a caller-supplied `args[0]` into the env var, but both consumers reject unrecognised values, so it cannot widen the exemption. **No finding here** — the ownership question is structural and stays with the arch audit.
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

- **Two independent stale-lock implementations, both with the same race.** `AdvisoryLock` (`advisory_lock.py`) and the DR backup lock (`dr_engine/_lock.py`) each hand-roll file locking with mtime/PID staleness detection, and TA71's defect is present in both. Neither uses `flock`. The contained fix repairs the shape twice; the structural question is why the repository owns two filesystem-lock implementations at all.
- **Frontend helpers are copied rather than shared.** TA67 is one function in two files; the theme has no `src/lib/http` seam, so the next call site that needs a CSRF token will produce a third copy. The contained fix does not create the seam. *(Carried from the prior pass — unchanged.)*
- **Conformance gates assert policy presence, not policy content.** `table_has_force_rls` (`tenancy.py:1623-1677`) accepts any table where `relrowsecurity` and `relforcerowsecurity` are true and `COUNT(*) FROM pg_policies >= 1`. A table carrying a permissive `USING (true)` policy would pass every isolation check the repository runs. The registry-driven parity tests constrain *which* tables are enrolled but not *what* their policies say.

---

## Tooling gaps

| Gap | Would have caught | Recommendation |
|---|---|---|
| Frontend suite runs, but no test pins the CSRF helper | **TA67** | `vitest` is already configured; add a table test over `document.cookie` shapes. The shared-helper fix is the real prevention |
| No concurrency test exercises either lock's stale-clear path | **TA71** | A two-thread barrier test around the `stat`/`unlink` gap, as described in TA71's *Verification*. Moving to `flock` removes the need for the test along with the defect |
| RLS policy assertions check existence, not predicate text | **TA72**, structural smell #3 | Extend the isolation conformance suite to assert the policy `qual`/`with_check` text from `pg_policies` matches the `_FORCE_RLS_FORWARD_SQL` template for each enrolled table — this pins the operator-read/tenant-write split as a gate rather than a comment |
| No gate requires a changelog/ticket trail for behavioural commits | — | **Carried.** Remains maintainer-process risk rather than a source finding |

---

## Notes (watch items)

**Carried forward from prior passes (re-verified, unchanged):**

- **Integration-branch CI** — hosted CI does not run on pushes to the release branch (`ci.yml` triggers on `main`/`develop` and PRs to `main`). Accepted solo-maintainer workflow choice.
- **Generator lock generation** — missing Poetry, timeout, or nonzero lock generation warns and lets generation finish by explicit usability policy; downstream apply/install stays fail-loud. Deliberate.
- **`_HOST_DEPENDENT_PATHS` is an exception station** on the SA90 emission byte-parity gate. Still a single entry (`.env`). Watch for monotonicity: a second entry deserves scrutiny, a third deserves a derivation.
- **The isolation-gate skip allowlist matches on message, not test identity** (`test_isolation_conformance.sh:184`). Broader than its own justification; narrowing it to the two PENDING_REMEDIATION test names would cost one line.
- **The generated healthcheck checks nothing** (`urls.py.j2:39-45` returns `HttpResponse("OK")`; `railway.json.j2:11` points Railway's deploy gate at it). Not promoted — the DB-free property is deliberate and documented, and production settings already raise at import when `RUNTIME_DATABASE_URL` is absent. Revisit if a separate readiness endpoint is added.
- **Generated local-development credentials are predictable by construction** (`generator.py:507-508`). Not promoted — deployment reality #4, no published database port. Worth a line in `OPERATIONS.md`.
- **Cross-tenant count fallbacks in CRM serializers** (`serializers.py:133-136`, `:311-312`, `:409-410`, `:541-545`) use `all_objects` when the ContextVar is unset. Not a finding: under the supported NOBYPASSRLS role, FORCE RLS with an unset GUC returns zero rows. Re-examine if a BYPASSRLS serving mode is ever supported. **This pass adds:** the identical pattern is pervasive in `billing/services.py`, which uses `all_objects` with explicit `organization=` filters throughout. Same adjudication, same trigger for re-examination.
- **`flush_empty_consolidated_sections` swallows a corrupt state file** (`state_schema.py:386-388`). A fail-hard deviation with a narrow trigger.
- **Atomic state writes are rename-atomic but not durable** (`state_schema.py:352-356`, `:405-407`) — no `fsync()`. Standard workstation trade-off.

**New this pass:**

- **`refresh_force_rls_policies` silently skips tables it cannot name.** `tenancy.py:596-620` derives each table name from the Django default convention (`app_label + '_' + model_name.lower()`) and then filters through `to_regclass(...) IS NOT NULL`, dropping any miss without a warning — on the repository's most security-critical migration helper. Empirical check #2 confirms the convention currently holds for **all 21** enrolled tables (8 explicit `db_table` declarations exist across the modules and every one matches the convention), so this is latent rather than live, and it is not promoted. The moment an enrolled model declares a non-conventional `db_table`, its policy refresh becomes a silent no-op. Deriving the name from `apps.get_model(...)._meta.db_table` — the same source `check_tenant_model_isolation` already uses — would close it.
- **`blog/feeds.py` resolves the System org twice, with opposite error handling.** `__call__` (`:31-34`) swallows any exception into `org = None`, but `items()` (`:44-46`) calls `Organization.objects.get_system_org()` again *unguarded*. If the first call failed because of a corrupt System org row — `OrganizationManager._validate_system_org` raises `RuntimeError` by design — the feed enters fail-closed scope and then raises unhandled during item rendering, turning a fail-closed empty feed into a 500. Narrow trigger (a corrupt singleton), and the broad `except Exception` is itself the Fail-Hard shape worth noting.
- **Four `sqlparse` CVEs were suppressed until 2026-09-30 — resolved 2026-09-02, no longer a watch item.** `CVE-2026-54284`, `-59893`, `-71491`, `-59894` against `sqlparse` 0.5.5 were accountable and unexpired rather than a finding, but shared one expiry date. During SA170 convergence the root pinned `sqlparse` 0.6.0 (with djangorestframework 3.17.2), the four `SA123-Phase-A-baseline` suppressions were removed from `scripts/security_suppressions.json`, and the Dependency Vulnerability Gate reports zero unsuppressed findings. No cliff-edge expiry remains; the evidence is archived in [CHANGELOG.md](../../CHANGELOG.md).
- **`table_has_force_rls` queries `pg_class` / `pg_policies` without schema qualification** (`tenancy.py:1650-1670`, matching on `relname` and `tablename`). Single-schema deployments are unaffected; recorded so a future schema-per-tenant option does not inherit an ambiguous check.

---

## Reconciliation log

- 2026-08-21 — **TA1–TA62**: closure detail, later structural-cause closure, and superseded cross-reference notes remain archived in [CHANGELOG.md](../../CHANGELOG.md) and version control, as recorded by the prior pass.
- 2026-08-21 — Prior watch items *integration-branch CI* and *generator lock generation*: **still-open, accepted / owned**. Carried forward unchanged.
- 2026-08-27 — **Closed-item closure narratives are archived.** TA63, TA65, TA69, the SA150 local-wheelhouse watch item, the dependency-vulnerability and security-static-analysis tooling gaps, and the six adjudicated arch-audit red-flag leads are all closed; detail lives in [CHANGELOG.md](../../CHANGELOG.md).
- 2026-08-27 — **Quality-baseline watch item retired.** Both recorded warning regressions are gone; monotonicity passes.
- 2026-08-28 — **TA67** `spa-csrf-token-duplicate-cookie`: **still-open**. Re-verified in code at both anchors (`useApi.ts:20-28`, `FormRenderer.tsx:206-211`) — byte-identical to the prior pass — and the mechanism re-confirmed empirically (check #1). Severity, fix, and effort unchanged.
- 2026-08-28 — **TA68** `generated-settings-dead-client-ip`: **still-open**. Re-verified: both definitions present, and a fresh grep across all generator templates still finds no importer.
- 2026-09-04 — **TA70** `container-status-substring-match`: **retired by SA170**. The ordered serial and concurrent release campaigns both passed with exact Core/CLI cleanup and preserved standing PostgreSQL state. Final and retained-partial evidence is archived in [CHANGELOG.md](../../CHANGELOG.md).
- 2026-09-02 — **Watch item closed:** the four `sqlparse` suppressions were retired by a real dependency upgrade to 0.6.0 during SA170 convergence; the vulnerability gate is green and the shared 2026-09-30 expiry no longer exists. No finding was opened or closed by this.
- 2026-08-28 — **TA71** `backup-lock-stale-clear-toctou`: **new (S3).** Found by the §3.3 lifecycle walk over the backups deployable rather than by the delta.
- 2026-08-28 — **TA72** `force-rls-apply-idempotency-claim`: **new (S4).**
- 2026-08-28 — **No prior closure claims required verification (§2f.3)**: the prior pass carried three open findings and claimed no new closures in the delta window, so there was no closure testimony to check against code. All three prior IDs were nonetheless re-verified at their anchors, as logged above.
- 2026-08-28 — **Fix-regression pass (§3.6)**: not applicable — the delta contains no fix for any prior finding. The two behavioural commits are test-only.
- 2026-08-28 — **Test-integrity diff (§3.7)**: the delta's ~60 removed assertions were read hunk by hunk against the "did any test get weaker?" question and **cleared**. Every removed assertion pinned documentation state, not code behaviour; the removal of the assertions over `arch-audit.md` and `tech-audit.md` is mandated by `decisions.md:670`; the replacement derives its counts from the roadmap rather than pinning literals, upgrades bare `assert`s to diagnostic `AssertionError`s, and adds a red-canary test proving drift still fails. No `skip`/`xfail` was added, no tolerance widened, no mock replaced a real dependency. Full adjudication in *Clean sweeps*.
- 2026-08-28 — **Chain pass (§3.9) ran** and produced **no chain**. Each of the five open findings was paired with the others, with the ten carried watch items, and with the crown jewels (tenant data, credentials, backups, money). TA67 and TA70 both fail closed and neither widens the other; TA71's window needs a pre-existing stale lock that no other finding creates; TA72 is latent and reachable only through a migration that does not yet exist. The nearest miss is TA71 × the *cross-tenant `all_objects` fallback* watch item — two concurrent backup runs do not change manager scoping, so it does not compose.

*Categories swept with no qualifying finding this pass: injection sinks of every kind, authentication and authorization, secrets handling, cryptographic use, multi-tenant isolation, data handling and serialization, resources and I/O, performance, dependency and build hygiene, CLI destructive-path safety, and the frontend, library/SDK, code-generator, and infrastructure-as-code archetype lenses.*
