# Tech Audit — Codebase-Wide Defect Sweep

> **Audit snapshot:** 2026-08-22 · **Prior pass:** 2026-07-26 (reconciled 2026-08-21 at `412d8d20`) · **Branch:** `v88` · **Findings last reconciled at:** `0132e0ea`

## Orientation summary

QuickScale is a Python 3.14 / Poetry **code-generator and scaffolding platform**: a Click CLI, a Django-6 project generator, twelve shipped first-party modules, and apply/recovery/DR tooling. First-party Python is ~275k lines across `quickscale_core` (72k), `quickscale_modules` (99k), `quickscale_cli` (64k), `scripts` (36k), `quickscale_devtools` (2.9k).

**Deployment realities** (every finding names one):

1. **The maintainer workstation** — `make quality`, `make ci`, `scripts/check_ci_locally.sh`, the CLI itself. Solo-maintainer repo; this is where the governance layer actually executes.
2. **Hosted CI** — `ci.yml` (push to `main`/`develop`, PR to `main`), `publish.yml`, `e2e.yml`, `nightly-bypassrls.yml`.
3. **The generated project** — Django 6 + PostgreSQL 18 + Vite/React, deployed to Railway behind a proxy, multi-tenant with FORCE RLS under a NOSUPERUSER/NOBYPASSRLS runtime role. Internet-facing.
4. **Local generated-project development** — `docker-compose.yml`, `settings/local.py`, `DEBUG=True`, no published database port.

**Entry points and trust boundaries.** Untrusted input reaches the system through: generated-project HTTP routes (DRF viewsets, the blog/forms/social public surfaces, two signed webhook endpoints, three `csrf_exempt` views); markdown authored into `Post.content` / `Listing.description`; operator-supplied restore archives fed to `pg_restore`; and `quickscale.yml` / module manifests consumed by the CLI. The CLI itself is operator-trusted.

**Tooling baseline.** ruff (`py314`, E/W/F/I/N/UP/D), mypy, pylint duplication-only, vulture, radon, pytest 9 with `--cov-fail-under=90` over the two `src` trees, pre-commit, a declared gate registry (`scripts/gate_registry.json`, 7 gates), AST gates, and a monotonic quality baseline with a waiver ledger. `scripts/` is deliberately outside `TEST_DIRS` and outside `.coveragerc`.

**Scope decision (§2e).** The companion structural autopsy scoped its 2026-08-21 pass to the governance/CI layer and explicitly **skipped generated-project template internals and frontend theme sources**. The commit delta since the prior tech pass is 12 files. This sweep therefore spends its depth where the two prior passes did not look: the generated-project templates, the React theme, the module HTTP/render surfaces, and the DR engine — plus full verification of the six red flags handed over by the arch audit.

**Oracle list (§2g) — the project's own declared invariants, hunted as defect classes:**

- **Fail-Hard Principle** (`decisions.md:634`, `:716-732`) — every configuration error, missing dependency, and invalid runtime state raises; no silent fallbacks, no graceful degradation, never substitute a default. `tech-audit.md` is the declared SSOT for found-not-yet-fixed violations.
- **Project interpreter only** (`ruff.toml:8-11`) — *"Anything that executes repo sources must therefore use the project interpreter (`sys.executable` / the venv), never a bare `python` off PATH."*
- **Runtime serving is fail-closed on RLS** — `RUNTIME_DATABASE_URL` required; `QUICKSCALE_ALLOW_BYPASSRLS=1` is an explicit dev/test opt-out only.
- **Raw credential values MUST NOT be persisted** in `quickscale.yml`, `.quickscale/state.yml`, or `BackupArtifact` rows (`decisions.md:316`); Stripe keys stay environment-only (`:855`).
- **Quality baseline monotonicity** — complexity maxima never ratchet upward; any positive ceiling delta requires a structured waiver.
- **CSRF-exempt endpoints carry an alternate integrity check.**
- **Tenant reads/writes stay organization-scoped**; `all_objects` is an operator escape hatch, not a scoping bypass.

**Delta classification (re-run mode, §2f).** `e40762a0..HEAD` = 8 commits, 12 files, 867 insertions. *Review-tracked:* `309b8b7a`, `ed8bb9b4`, `10d6bfe2`, `9dd49c1d` (docs), `3de43250` (subtree split, no tree change). *Side-channel — read in full, production and test hunks:* `be5cf024` "fix(ci)", and `d4b0e834` / `d3d4c633`, both titled "v0.87.0: QuickScale 0.87.0" while in fact changing hosted and publish provisioning. The full first-party production diff was read; the test diff was read against the "did any test get weaker?" question (§3.7) — results in *Clean sweeps* and *Notes*.

### Coverage statement (§3.11)

**Read in full:** the entire `e40762a0..HEAD` diff (12 files); `scripts/test_isolation_conformance.sh`; `scripts/check_quality_baseline_monotonicity.py` merge-base resolution and `main`; `scripts/check_quality.sh` gate ordering and failure handling; `scripts/version_tool.sh` interpreter selection; `quickscale_modules/orgs/.../sanitization.py`; `current_org.py` tenant-context and client-IP sections; `quickscale_modules/orgs/tests/test_tenant_table_conformance.py` parametrization; the generated `settings/base.py.j2` and `settings/production.py.j2`, `.env.j2`, `.env.example.j2`, `docker-compose.yml.j2`, `db/init.sql.j2`, `urls.py.j2`, `views.py.j2`; `dr_engine/primitives.py`, `_paths.py`, and the `recovery.py` restore gate; `useApi.ts`; the three `csrf_exempt` surfaces and both webhook verifiers.

**Sampled:** 326 module source files and 141 core files by signature sweep (injection sinks, broad excepts with fallback assignment, mutable defaults, missing timeouts, `mark_safe`/`|safe`, `all_objects`, `operator_access`, raw SQL, destructive filesystem calls); the CLI remove/module destructive paths; `state_schema.py` atomic write; the 78-file React theme by signature (`innerHTML`, `postMessage`, storage, `fetch`); `poetry.lock` pins for the security-relevant packages.

**Skipped:** `beta_migration.py` and generated-project migrations; the four hosted workflows beyond the delta (the arch audit read them in full this cycle); pylint/radon/vulture internals; generated-project frontend component bodies.

**Audit tools run (read-only):** `pytest 9.1.x` under `.venv/bin/python` (CPython 3.14.6) over `scripts/` — **74 failed, 1126 passed, 349.64s**; targeted runs of `test_gate_parity.py`, `test_check_sa117_scope.py`, `test_quality_baseline_monotonicity.py`; `git log/blame/rev-parse/branch/tag`. No dependency scanner is installed in the venv (`pip-audit`, `safety`, `bandit`, `semgrep` all absent) — dependency review was manual against `poetry.lock`. ruff/mypy configs were read, not executed.

**Empirical checks run (§1e) — 6, all side-effect-free:**

| # | Check | Result |
|---|---|---|
| 1 | Ran the XSS pipeline (`escape` → `markdown[fenced_code,tables,toc]` → `sanitize_rendered_html`) against 15 crafted payloads in a REPL | **Refuted** a suspected stored-XSS finding — see *Clean sweeps* |
| 2 | Ran `check_quality_baseline_monotonicity.py` with `env -u QUALITY_BASELINE_BASE_REF -u GITHUB_BASE_REF` | **Confirmed TA63** — exit 2, `MERGE_BASE_ERROR`. Artifact backed up and byte-restored |
| 3 | `git rev-parse --verify v87` / `origin/v87` / `git tag \| grep v87` | Local branch and tag **absent**; `origin/v87` resolves. Confirms TA63's mechanism |
| 5 | Ran `python3 scripts/check_sa117_scope.py` from a directory without `scripts/` | Interpreter exits **2** on "can't open file" — the former false-green mechanism; SA157's closure proof below now distinguishes tool output from interpreter failure |
| 6 | Pre-SA162 `~True != 0` under `-W error::DeprecationWarning` on 3.14.6 | Raised before SA162; the closure rerun is clean with `~int(val) != 0`, preserving the arch audit's corrected semantics |

---

## Summary table

| ID | Sev | Category | Title | Effort | Confidence | Status |
|---|---|---|---|---|---|---|
| `spa-csrf-token-duplicate-cookie` (TA67) | **S3** | Correctness (frontend) | `getCsrfToken` returns `''` whenever two `csrftoken` cookies are present — every SPA write 403s | Trivial ⚡ | High | new |
| `generated-settings-dead-client-ip` (TA68) | S4 | Dead code (generated output) | Two `get_client_ip` definitions in generated settings are unreachable | Trivial | High | new |

**Counts:** S1 **0** · S2 **0** · S3 **1** · S4 **1** · **Total 2 open**. Quick win (⚡ Trivial-effort S3): TA67.

---

## Findings

### TA67 — SPA CSRF token lookup returns empty whenever two `csrftoken` cookies exist

**ID:** `spa-csrf-token-duplicate-cookie`

**Severity:** **S3.** A latent bug that needs one precondition — a duplicate `csrftoken` cookie — after which **every** state-changing request from the React SPA fails with 403 and the app is read-only. Deployment reality #3 (the generated project, internet-facing). Fails closed, so it is availability, not a security hole. Reachability drops one notch for the single unverified precondition.

**Category:** §4.I Correctness (§4.X frontend). **Confidence:** High — logic verified by reading; the triggering cookie state is a standard, documented Django deployment condition.

**Location:** `…/themes/showcase_react/src/hooks/useApi.ts:20-28` and `…/src/components/forms/FormRenderer.tsx:206-211` — the same eleven lines, duplicated.

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

---

### S4

- **TA68 · `generated-settings-dead-client-ip`** · `…/templates/project_name/settings/base.py.j2:61` and `settings/production.py.j2:123` · Both files define a module-level `get_client_ip(request)`, and `production.py.j2` rebinds it with a comment claiming the rebind exists "so that production defaults … are actually in effect at request time". Neither is reachable in a generated project: Django's `Settings` copies only **uppercase** names off the settings module, so `django.conf.settings.get_client_ip` does not exist, and nothing in the generated tree imports either function (grep across all templates returns only the two definitions). The real consumer is `quickscale_modules_orgs.current_org.get_client_ip`, which reads the uppercase `USE_X_FORWARDED_FOR` / `TRUSTED_PROXY_COUNT` settings dynamically and is correct. · **Fix:** delete both definitions and keep the settings plus the `REST_FRAMEWORK["NUM_PROXIES"]` recomputation, or add a comment pointing at the orgs helper as the live implementation. The behavioural comment in `production.py.j2:119-122` is misleading as written and should go either way.
---

## Per-subsystem verdicts

| Subsystem | What was read | Verdict |
|---|---|---|
| Commit delta `e40762a0..HEAD` | all 12 files, production and test hunks, in full | Clean — no finding. The two test changes are correct narrowings; see *Clean sweeps* and *Notes* |
| `scripts/` quality-baseline gate | `check_quality_baseline_monotonicity.py` merge-base + `main`; `check_quality.sh` ordering and failure path | **Closed by SA156 (TA63)** |
| `scripts/` gate conformance suites | executed all 14 — 74F/1126P at audit time; the retained population is now **15 suites / 1,227 passed** after the closure passes; read the failing tests and their fixtures | **Arch Finding 12 closed by SA155:** `check-gate-suites` is registered for local-serial, local-parallel, and hosted execution with cache and product coverage disabled. The former TA66 oracle failure, the historical quality-baseline failures, and the SA117 false-green are also closed (see [CHANGELOG.md](../../CHANGELOG.md)) |
| `scripts/` shell interpreter selection | `version_tool.sh`, `lint_frontend.sh`, `check_ci_locally.sh`, `_python_requirement.sh` | **Closed by SA159** — repository-source calls use the validated project interpreter; `check_ci_locally.sh` is documented adjacent because its heredoc is stdlib-only |
| Generated settings templates | `base.py.j2`, `production.py.j2` in full | **TA68**; production hardening otherwise clean |
| Generated project scaffold | `.env.j2`, `.env.example.j2`, `docker-compose.yml.j2`, `db/init.sql.j2`, `urls.py.j2`, `views.py.j2`, `railway.json.j2` | Clean — see *Notes* for the dev-credential and healthcheck watch items |
| React theme (`showcase_react`) | 78 files by signature; `useApi.ts` and the social/forms surfaces in full | **TA67** |
| Blog / listings render path | `views.py` render sites, `sanitization.py`, markdown extension wiring, 15-payload REPL test | Clean — verified, see *Clean sweeps* |
| Webhooks (billing, notifications) | both views and both verifiers in full | Clean |
| Blog `csrf_exempt` API | all three exempt views and `authenticate_blog_api_request` | Clean |
| DR engine | `primitives.py`, `_paths.py`, `recovery.py` restore gate | Clean |
| Multi-tenant scoping | `all_objects` / `operator_access` / raw-SQL census across all modules; `current_org.py` context machinery | Clean under the supported role; see *Notes* |
| CLI destructive paths | `remove_command.py`, `module_commands.py` rmtree/unlink sites | Clean (operator-trusted input) |

---

## Clean sweeps worth recording

- **Stored XSS in the markdown render path is genuinely closed** (empirical check #1). `blog/views.py:855` and `listings/views.py:318` run `markdownify(escape(...))` — escaping *before* markdown — then `sanitize_rendered_html`. Fifteen payloads (raw `<script>`, `img onerror`, `javascript:`/`data:`/`vbscript:` links, tab- and entity-obfuscated schemes, reference links, fenced-lang attribute injection, alt-attribute breakout, autolinks, backslash-prefixed schemes) all rendered inert. `sanitize_href` correctly strips `\t\r\n` before the scheme check, matching WHATWG parsing. Extensions are limited to `fenced_code`, `tables`, `toc` — no `attr_list`, no `md_in_html`.
- **Both webhook endpoints verify before trusting.** Notifications: HMAC over `timestamp.body`, `hmac.compare_digest`, a TTL replay window, and fail-closed on an unconfigured secret (`services.py:722-753`). Billing: Stripe's `Webhook.construct_event`, plus idempotency via `WebhookEvent.get_or_create` and `select_for_update` (`services.py:938-1022`).
- **The `csrf_exempt` decorators are compensated at the right layer.** `blog/views.py:376` calls `_enforce_csrf(request)` for session-authenticated requests and exempts only bearer-token automation, with `secrets.compare_digest` on the token and a staff check. The exemption is real but narrow.
- **PostgreSQL credentials never reach argv.** `_build_pg_dump_command` / `_build_pg_restore_command` pass the password through `PGPASSWORD` in the subprocess environment; the command list that `_run_shell_command` interpolates into its error message (`primitives.py:169`) carries no secret.
- **The destructive restore path is layered.** Exact-filename confirmation, an export-only rejection, source and compatibility validation, the `QUICKSCALE_BACKUPS_ALLOW_RESTORE` environment gate outside DEBUG, a PostgreSQL 18 contract check, and a magic-bytes plus `pg_restore --list` check on operator-supplied archives — all before `pg_restore` runs (`recovery.py:500-641`).
- **`social` URL fields cannot carry `javascript:`.** `BaseSocialItem.save()` calls `self.full_clean()` (`models.py:147`) on every write, so `models.URLField`'s scheme allowlist runs on all paths — which is what makes the unsanitized `href={link.url}` in `SocialLinkTreePublicPage.tsx:223` safe, since React does render `javascript:` hrefs.
- **`QUICKSCALE_ALLOW_BYPASSRLS` hygiene holds.** No blanket export anywhere; `ci.yml:488,626` and `publish.yml:240` pin it to `"0"`; `scripts/test_integration.sh:449` documents the deliberate absence of a blanket enable; all eleven module `tests/settings.py` files carry the same "no module test code automatically primes" note. Only `Makefile:421`'s dedicated `test-bypassrls` target and `nightly-bypassrls.yml` set it to `1`. This is the §4.VIII "test tooling that neuters guards" class, checked and clean.
- **No shell injection surface.** Zero `shell=True`, zero `os.system`, zero f-string subprocess invocations across `quickscale_core/src`, `quickscale_cli/src`, `quickscale_modules/*/src`, `quickscale_devtools/src`, and `scripts/`.
- **No unsafe deserialization or dynamic evaluation.** Zero `yaml.load(` (all `safe_load`), `pickle.load`, `eval(`, `exec(`, `marshal.load` in first-party source.
- **`d3d4c633`'s isolation-gate skip narrowing is correct, not a weakening.** The new allowlist in `test_isolation_conformance.sh:184` suppresses only `got empty parameter set` skips. The parametrized sets are filters over `TENANT_TABLE_REGISTRY`, a static 45-entry literal at `tenancy.py:128`; the only set that is legitimately empty is `PENDING_REMEDIATION`, which `test_exactly_zero_pending_remediation_entries` (`:912`) independently asserts must be empty. An empty ENROLLED set is not reachable without editing the literal, and if the apps were missing the ENROLLED tests would fail on `apps.get_model` rather than skip. One residual caveat is carried in *Notes*.
- **`be5cf024`'s managed-adapter relocation strengthened the guard.** Moving `_assert_full_adapter_registry_present()` out of `_refresh_session_managed_adapters()` into the session fixture correctly stops tests that deliberately narrow the registry from tripping a completeness check, and the guard test was updated in step to run both steps in order (`test_manifest_entry_point.py:278-290`).
- **Dependency pins are current.** Django 6.0.7, DRF 3.17.1, Pillow 12.3.0, urllib3 2.7.0, certifi 2026.6.17, requests 2.34.2, stripe 15.3.1, jinja2 3.1.6, PyYAML 6.0.3, boto3 1.43.58. No EOL runtime or abandoned library on a critical path; no manual match against a known-vulnerable pin. This is a manual review, not a scanner run — see *Tooling gaps*.

---

## Structural smells

*(candidate inputs for the companion `deep-architectural-audit` — not findings here)*

- **A gate's base ref was a per-release branch name, hard-coded in the gate.** TA63 is closed by SA156, but the structural lesson remains: a governance tool pinned to an artifact of the release *process* has nothing tying the two lifecycles together. The durable `main` identity and origin/local probe now own the default path.
- **Frontend helpers are copied rather than shared.** TA67 is one function in two files; the theme has no `src/lib/http` seam, so the next call site that needs a CSRF token will produce a third copy. The contained fix does not create the seam.

---

## Tooling gaps

| Gap | Would have caught | Recommendation |
|---|---|---|
| Frontend suite runs, but no test pins the CSRF helper | **TA67** | `vitest` is already configured; add a table test over `document.cookie` shapes. The theme has an eslint config — a `no-duplicate-imports`-style rule will not catch copied functions; the shared-helper fix is the real prevention |
| No dependency-vulnerability scanner | — | **Carried from the prior pass.** Roadmap **SA123** owns this for v88. Confirmed still absent: `pip-audit`, `safety`, `bandit`, `semgrep` are all missing from `.venv` |
| No focused security static analysis | — | **Carried.** SA123. Rules for subprocess shell use, unsafe deserialization, TLS disabling, Django raw/`mark_safe` sinks, and committed credentials. This pass verified all five classes by hand and found them clean, which is exactly the check worth automating so it stays clean |
| No gate requires a changelog/ticket trail for behavioural commits | **SA166** | **Carried.** `d3d4c633` shipped a CI-topology change under a release-shaped message and left a conformance test red. Remains maintainer-process risk rather than a source finding |
| ~~`scripts/` suites are in no execution context~~ | Arch Finding 12 | **Closed by SA155:** the green suite population is registered through `check-gate-suites`; detailed evidence is retained in [CHANGELOG.md](../../CHANGELOG.md) |

---

## Notes (watch items)

**Carried forward from the prior pass:**

- **Integration-branch CI** — hosted CI does not run on pushes to the release branch (`ci.yml` triggers on `main`/`develop` and PRs to `main`). Accepted solo-maintainer workflow choice. *Unchanged.*
- **Generator lock generation** — missing Poetry, timeout, or nonzero lock generation warns and lets generation finish by explicit usability policy; downstream apply/install stays fail-loud. Deliberate. *Unchanged.*
  - **Quality baseline** — the prior watch claim that *"monotonicity is enforced and `make quality` reports `total_regressions: 0`"* was **falsified and promoted to TA63**, then **closed by SA156** after the no-override helper passed and a real `make quality` run re-emitted fresh reports. The current pre-edit baseline has two warning regressions: `development_commands.py::up` complexity 15 versus baseline 14, plus `social/src/quickscale_modules_social/adapter.py::_social_manifest_apps` complexity 13 newly above threshold; critical regressions remain 0 and monotonicity passes. The helper exits 1 and GNU Make reports `make quality` exit 2; the exact two-signature result is the authorized no-worse-than-found baseline for SA158, not a blocker. See the reconciliation log for both the falsification and closure evidence.

**New this pass:**

- **`_HOST_DEPENDENT_PATHS` is a new exception station.** `be5cf024` added `frozenset({".env"})` to the SA90 emission byte-parity gate (`test_generator.py:1023`), suppressing hash comparison for `.env` while keeping presence and a normalized mode. The justification is sound (`.env` embeds the invoking user's `DOCKER_UID`/`DOCKER_GID`) and the `755`/`644` mode normalization correctly removes a umask dependency — but it is a hand-maintained exception list on the repository's strictest gate. Watch it for monotonicity: a second entry deserves scrutiny, a third deserves a derivation.
- **The isolation-gate skip allowlist matches on message, not test identity.** `test_isolation_conformance.sh:184` keys on `message.startswith('got empty parameter set')`, so it silences an empty parameter set on *any* of the eleven parametrized tests in `test_tenant_table_conformance.py`, not only the two PENDING_REMEDIATION ones its comment describes. Not a finding — the ENROLLED sets are filters over a static literal and cannot empty accidentally (see *Clean sweeps*) — but the allowlist is broader than its own justification, and narrowing it to the two test names would cost one line.
- **The generated healthcheck checks nothing.** `urls.py.j2:39-45` returns `HttpResponse("OK")` unconditionally, and `railway.json.j2:11` points Railway's deploy gate at it. This is the §4.VI "health check that checks nothing" shape, and Railway will keep routing traffic to an instance whose database died after boot. Not promoted: the docstring states the DB-free property deliberately, production settings already raise at import when `RUNTIME_DATABASE_URL` is absent (so a DB-less process never starts), and a DB-touching deploy gate causes rollback loops during database maintenance. Worth revisiting if a separate readiness endpoint is ever added alongside the liveness one.
- **Generated local-development credentials are predictable by construction.** `generator.py:507-508` derives `runtime_db_role = f"{package_name}_app"` and `runtime_db_password = f"{role}_password"`, rendered into `db/init.sql`, `docker-compose.yml`, and `.env.example` — none of which `.gitignore.j2` excludes (only `.env` is ignored). Not promoted: the compose file publishes no database port, `POSTGRES_PASSWORD` is likewise `postgres`, and this is deployment reality #4 (local dev) where production supplies `RUNTIME_DATABASE_URL` from the environment. Worth a line in `OPERATIONS.md` making explicit that these values must not survive into any shared environment.
- **Cross-tenant count fallbacks in CRM serializers.** `serializers.py:133-136`, `:311-312`, `:409-410`, `:541-545` follow `if org_id: …filter(…, organization_id=org_id)` with an unscoped `all_objects` fallback when the ContextVar is unset. Not a finding: `all_objects` bypasses only the Python-level manager, and under the supported NOBYPASSRLS runtime role FORCE RLS with an unset `app.current_org_id` GUC returns zero rows (fail-closed, AF11). The fallback is defence-in-depth that has become load-bearing-looking. It would leak only under `QUICKSCALE_ALLOW_BYPASSRLS=1` + serving, a configuration production refuses. Re-examine if a BYPASSRLS serving mode is ever supported.
- **`flush_empty_consolidated_sections` swallows a corrupt state file.** `state_schema.py:386-388` returns silently on `yaml.YAMLError, OSError`, skipping the explicit `modules: {}` / `managed_files: []` markers that downstream readers use to distinguish "M2 has spoken" from pre-M2 state. A fail-hard-principle deviation with a narrow trigger (the file was just written successfully by `save()`), so not promoted — but it is the exact silent-fallback shape the principle names.
- **Atomic state writes are rename-atomic but not durable.** `state_schema.py:352-356` and `:405-407` write a temp file and `replace()` without `flush()`/`os.fsync()`. Correct against concurrent readers, not against power loss. Standard trade-off on a developer workstation; recorded so it is not rediscovered.

---

## Reconciliation log

- 2026-08-21 — **TA1–TA62**: closure detail, later structural-cause closure, and superseded cross-reference notes remain archived in [CHANGELOG.md](../../CHANGELOG.md) and version control, as recorded by the prior pass. No prior ID was reopened this pass; none was re-verified in code, because the prior document carried none forward as open.
- 2026-08-21 — Prior watch item *quality baseline*: **regressed → promoted to TA63 → closed by SA156**. The prior pass recorded "monotonicity is enforced and `make quality` reports `total_regressions: 0`". It was falsified by execution: the gate exited 2 with `MERGE_BASE_ERROR` and `make quality` aborted before any analyzer ran. SA156 replaced the retired release-ref fallback with durable `main`, proved origin/local probing and missing-default remediation in hermetic tests, and verified a real `make quality` run with fresh reports. The current broader run reports the unrelated pre-existing `development_commands.py::up` C901 complexity regression (15 versus allowed 14): `scripts/check_quality.sh` exits 1 and GNU Make reports `make quality` exit 2, exactly matching the authorized no-worse-than-found oracle. **Full TA63 defect and closure detail is archived in [CHANGELOG.md](../../CHANGELOG.md); no closed-findings section is carried here.**
- 2026-08-21 — Prior watch items *integration-branch CI* and *generator lock generation*: **still-open, accepted / owned**. Re-verified at their anchors; carried forward unchanged in *Notes*. Not re-argued — no severity context changed.
- 2026-08-24 — **SA150 closed the local-wheelhouse watch item.** `docs/technical/local-wheelhouse.md` documents the explicit environment override, accepted values, implicit `sys.prefix/quickscale_wheels` choice, and failure modes. `_resolve_local_wheel_dependency()` now raises `DependencySyncError` for an explicit unmatched `quickscale-core` artifact with the environment variable, searched directory, attempted pattern, and available wheels in the message; published third-party dependencies remain manifest-derived, and an empty explicit value is rejected. Regression tests cover both production call sites, normalized matching, public-dependency fallback, and preserved unset/implicit fallback. This retires a live watch item only: the summary table remains S3: one, S4: one, total two, with no numbered finding closed by SA150.
- 2026-08-21 — Prior tooling gaps *dependency vulnerabilities*, *security static analysis*, *production-change testimony*: **still-open**. Absence of `pip-audit`/`safety`/`bandit`/`semgrep` re-verified in `.venv`. SA123 owns the first two.
- 2026-08-21 — **Arch-audit red-flag hand-off, all six adjudicated** (§2f.1 — leads, not pre-approved findings): *red `test_gate_parity` oracle* → **promoted, TA66** (reproduced; closed by SA158 below). *`test_check_sa117_scope.py:640` interpreter-bound* → **covered by SA157 and TA65 (both closed)**, and the investigation found a second, worse defect at `:601` the red flag did not name — a test that passed on the interpreter's exit code; both are closed by the evidence above. *72 quality-baseline failures, "needs triage"* → **triaged: not environment sensitivity — TA63**, the same hard-coded ref, reproduced from a clean environment. *`quickscale_devtools` version drift* → **not promoted**; owned by SA137, whose closure and publication exclusion are recorded in [CHANGELOG.md](../../CHANGELOG.md) and the roadmap. *Deprecated bool inversion in the CSRF gate* → **promoted as TA69 and later closed by SA162** with the semantics-preserving `~int(val) != 0` correction; the suggested `not val` substitution was rejected because it changes the gate's verdict. *`tech-audit.md` header reads `Branch: v87`* → **resolved** by this regeneration.
- 2026-08-21 — **Fix-regression pass (§3.6)** over the delta's three behavioural commits. `be5cf024`: the managed-adapter assertion relocation is a correct narrowing with its guard test updated in step; the SA90 `.env` exception is sound but is a new hand-maintained exception station, carried as a watch item. `d3d4c633`: the isolation-gate skip narrowing is correct (verified against the registry's construction), but the same commit left `test_gate_parity`'s oracle stale — TA66, now closed by SA158. `d4b0e834`/`d3d4c633` PGDG provisioning: no defect found in the added steps themselves; their four-way duplication is arch Finding 13's territory, not re-filed here.
- 2026-08-21 — **Test-integrity diff (§3.7)**: no test was weakened in the delta. Assertions were not removed or inverted, no tolerance was widened, no `skip`/`xfail` was added, no mock replaced a real dependency. The two changes that *look* like weakenings (`_HOST_DEPENDENT_PATHS`, the empty-parameter-set allowlist) were each traced to the invariant they leave standing and cleared; both are carried as watch items rather than findings.
- 2026-08-22 — **TA65 (`repo-sources-run-under-bare-python`) and arch red flag #2 closed by SA159.** Defect detail, closure evidence, and the deliberate `check_ci_locally.sh` adjacency are archived in [CHANGELOG.md](../../CHANGELOG.md); no closed-finding section is carried here.
- 2026-08-24 — **SA162 closed TA69 (`csrf-gate-bool-invert-deprecated`).** The gate now evaluates analyzed `~True` and `~False` operands with `~int(val) != 0`, preserving bitwise-invert truthiness without the deprecated bool inversion. Focused analyzed-source regression tests cover both verdicts, and the warning-as-error gate is clean. TA69 is retired from the live finding table; completion evidence is archived in [CHANGELOG.md](../../CHANGELOG.md).
- 2026-08-21 — **Chain pass (§3.9) ran** and produced two chains, both recorded on their lead findings: TA63 × arch Finding 12 (the monotonicity invariant has been unenforced for the whole `v88` branch with no signal, while two live audit documents recorded it as enforced) and the SA117 false-green × arch Finding 12 × roadmap SA124 (SA124's acceptance test lands in a suite nothing executes, beside a false-green pattern it was likely to be copied from). SA157 now closes the false-green leg. Pairing the remaining findings against each other and against the watch-item list produced no third chain.

*Categories swept with no qualifying finding this pass: concurrency and TOCTOU, resources and I/O, performance, data handling and serialization, injection sinks of every kind, authentication and authorization, secrets handling, cryptographic use, multi-tenant isolation, CLI destructive-path safety, dependency and build hygiene, and the frontend, library/SDK, and infrastructure-as-code archetype lenses.*
