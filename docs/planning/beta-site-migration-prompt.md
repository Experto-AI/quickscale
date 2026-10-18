# Beta migration handoff prompt

This recipient was produced by the fresh-first beta migration (`make beta-migrate-fresh`);
the deterministic file migration and local verification already ran. Complete the remaining
work below, then hand the recipient back to the maintainer.

- Mode: iterate
- Phase: fresh-first-executed
- Donor: /home/victor/code/bap-web
- Identity reconciliation: not required
- Runtime provenance: settings/production.py=donor, start.sh=recipient, Dockerfile=recipient
- Verification: 5 passed, 3 failed

## What was migrated

Steps completed:
- parse-cli-arguments
- write-recipient-config
- regenerate-recipient
- run-preflight-validations
- validate-fresh-first-runtime-files
- load-project-identities-and-diffs
- build-planned-actions
- identity-reconciliation
- copy-custom-router-and-pages
- copy-custom-components-and-utilities
- copy-selected-django-files
- rewrite-pre-facade-production-settings
- copy-project-owned-apps
- register-and-mount-project-owned-apps
- sync-missing-path-dependencies
- merge-frontend-dependencies
- port-donor-design
- preserve-managed-recipient-files
- carry-project-app-migration-operations
- start-recipient-services
- stop-recipient-services
- run-verification-stack

Carried migration operations:
- Carried donor project-owned-app migration operations the autodetector cannot regenerate into appended recipient migrations: properties:0002_propertylisting_seeded_from_catalog.py -> 0002_carried_propertylisting_seeded_from_catalog.py (RunPython (line 39)).

Recipient paths changed (28):
- `.`
- `bap_web/context_processors.py`
- `bap_web/public_listings.py`
- `bap_web/settings/base.py`
- `bap_web/settings/production.py`
- `bap_web/urls.py`
- `bap_web/views.py`
- `frontend/design/tailwind.preset.js`
- `frontend/design/tokens.css`
- `frontend/src/App.tsx`
- `frontend/src/assets`
- `frontend/src/components/home`
- `frontend/src/components/layout`
- `frontend/src/components/properties`
- `frontend/src/components/seo`
- `frontend/src/components/shared`
- `frontend/src/data`
- `frontend/src/pages/About.tsx`
- `frontend/src/pages/Contact.tsx`
- `frontend/src/pages/Home.tsx`
- `frontend/src/pages/Privacy.tsx`
- `frontend/src/pages/Properties.tsx`
- `frontend/src/pages/PropertyDetail.tsx`
- `frontend/src/stores`
- `frontend/src/types`
- `properties`
- `properties/migrations/0002_carried_propertylisting_seeded_from_catalog.py`
- `quickscale.yml`

Diff summary:
- Module diff: donor-only=['(none)'], recipient-only=['analytics', 'notifications', 'orgs']
- Path dependency diff: donor-only=['(none)'], recipient-only=['quickscale-core', 'quickscale-module-analytics', 'quickscale-module-notifications', 'quickscale-module-orgs']
- Frontend dependency merge: donor-only=['(none)'], version conflicts=['@hookform/resolvers (recipient dependencies ^5.5.7, donor dependencies ^5.2.2)', '@radix-ui/react-checkbox (recipient dependencies ^1.3.11, donor dependencies ^1.1.7)', '@radix-ui/react-dialog (recipient dependencies ^1.1.23, donor dependencies ^1.1.15)', '@radix-ui/react-dropdown-menu (recipient dependencies ^2.1.24, donor dependencies ^2.1.16)', '@radix-ui/react-label (recipient dependencies ^2.1.15, donor dependencies ^2.1.8)', '@radix-ui/react-navigation-menu (recipient dependencies ^1.2.22, donor dependencies ^1.2.14)', '@radix-ui/react-popover (recipient dependencies ^1.1.23, donor dependencies ^1.1.15)', '@radix-ui/react-radio-group (recipient dependencies ^1.4.7, donor dependencies ^1.2.7)', '@radix-ui/react-scroll-area (recipient dependencies ^1.2.18, donor dependencies ^1.2.10)', '@radix-ui/react-select (recipient dependencies ^2.3.7, donor dependencies ^2.2.5)', '@radix-ui/react-separator (recipient dependencies ^1.1.15, donor dependencies ^1.1.8)', '@radix-ui/react-slot (recipient dependencies ^1.3.3, donor dependencies ^1.2.4)', '@radix-ui/react-tabs (recipient dependencies ^1.1.21, donor dependencies ^1.1.13)', '@radix-ui/react-toast (recipient dependencies ^1.2.23, donor dependencies ^1.2.15)', '@radix-ui/react-tooltip (recipient dependencies ^1.2.16, donor dependencies ^1.2.8)', '@tanstack/react-query (recipient dependencies ^5.101.4, donor dependencies ^5.90.20)', 'motion (recipient dependencies ^12.43.0, donor dependencies ^12.33.0)', 'react (recipient dependencies ^19.2.8, donor dependencies ^19.2.4)', 'react-dom (recipient dependencies ^19.2.8, donor dependencies ^19.2.4)', 'react-hook-form (recipient dependencies ^7.83.0, donor dependencies ^7.71.1)', 'react-router-dom (recipient dependencies ^7.18.2, donor dependencies ^7.13.0)', 'tailwind-merge (recipient dependencies ^3.6.0, donor dependencies ^3.4.0)', 'zustand (recipient dependencies ^5.0.14, donor dependencies ^5.0.11)', '@eslint/js (recipient devDependencies ^10.0.1, donor devDependencies ^9.17.0)', '@playwright/test (recipient devDependencies ^1.62.0, donor devDependencies ^1.58.1)', '@testing-library/dom (recipient devDependencies ^10.4.1, donor devDependencies ^10.4.0)', '@testing-library/jest-dom (recipient devDependencies ^7.0.0, donor devDependencies ^6.9.1)', '@testing-library/user-event (recipient devDependencies ^14.6.1, donor devDependencies ^14.5.2)', '@types/node (recipient devDependencies ^24.13.3, donor devDependencies ^22.10.2)', '@types/react (recipient devDependencies ^19.2.17, donor devDependencies ^19.2.7)', '@vitejs/plugin-react (recipient devDependencies ^6.0.4, donor devDependencies ^5.1.3)', '@vitest/coverage-v8 (recipient devDependencies ^4.1.10, donor devDependencies ^4.0.18)', 'autoprefixer (recipient devDependencies ^10.5.4, donor devDependencies ^10.4.20)', 'eslint (recipient devDependencies ^10.8.0, donor devDependencies ^9.17.0)', 'eslint-plugin-react-hooks (recipient devDependencies ^7.1.1, donor devDependencies ^5.1.0)', 'eslint-plugin-react-refresh (recipient devDependencies ^0.5.3, donor devDependencies ^0.4.16)', 'globals (recipient devDependencies ^17.8.0, donor devDependencies ^15.14.0)', 'jsdom (recipient devDependencies ^30.0.1, donor devDependencies ^25.0.1)', 'postcss (recipient devDependencies ^8.5.25, donor devDependencies ^8.4.49)', 'prettier (recipient devDependencies ^3.9.6, donor devDependencies ^3.4.2)', 'prettier-plugin-tailwindcss (recipient devDependencies ^0.8.1, donor devDependencies ^0.6.9)', 'typescript (recipient devDependencies ^6.0.3, donor devDependencies ^5.9.3)', 'typescript-eslint (recipient devDependencies ^8.65.0, donor devDependencies ^8.18.1)', 'vite (recipient devDependencies ^8.1.5, donor devDependencies ^7.3.1)', 'vitest (recipient devDependencies ^4.1.10, donor devDependencies ^4.0.18)']

Verification commands:
- `poetry lock` — passed
- `poetry install` — passed
- `pnpm install` — passed
- `pnpm build` — failed
- `poetry run python manage.py makemigrations properties` — passed
- `poetry run python manage.py migrate` — passed
- `poetry run pytest` — failed
- `pnpm test` — failed

## Remaining work

- [x] `resolve-pre-port-surface-pnpm-build` — Complete the manual port for `pnpm build` and re-run it (resolved in SA191 slice (c): exit 0); the command failed with exit code 1 on a pre-port surface the migration prompt assigns to the manual port. Captured output tail: $ tsc -b && vite build
      Paths: `frontend`
      Rule: Pre-port build and test surfaces are recorded instead of blocking: reconcile the donor's divergent frontend sources and pre-port tests in the recipient, then re-run the command.
- [x] `resolve-pre-port-surface-poetry-run-pytest` — Complete the manual port for `poetry run pytest` and re-run it (resolved in SA191 slice (c): 56 passed); the command failed with exit code 2 on a pre-port surface the migration prompt assigns to the manual port. Captured output tail: ions/tests - _pytest.pathlib.ImportPathMismatchError: ... ERROR modules/orgs/tests - _pytest.pathlib.ImportPathMismatchError: ('tests.c... !!!!!!!!!!!!!!!!!!! Interrupted: 6 errors during collection !!!!!!!!!!!!!!!!!!!! ========================= 1 warning, 6 errors in 0.40s =========================
      Paths: `.`
      Rule: Pre-port build and test surfaces are recorded instead of blocking: reconcile the donor's divergent frontend sources and pre-port tests in the recipient, then re-run the command.
- [x] `resolve-pre-port-surface-pnpm-test` — Complete the manual port for `pnpm test` and re-run it (resolved in SA191 slice (c): 338 passed); the command failed with exit code 1 on a pre-port surface the migration prompt assigns to the manual port. Captured output tail: t.prune(() => __vite__removeStyle(__vite__id)) ❯ src/test/viteAssetRouting.test.ts:330:27 328| const response = await requestStylesheet((address as AddressInfo).… 329| expect(response.status).toBe(200) 330| expect(response.body).toContain('--primary:') | ^ 331| }) 332| ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[5/19]⎯
      Paths: `frontend`
      Rule: Pre-port build and test surfaces are recorded instead of blocking: reconcile the donor's divergent frontend sources and pre-port tests in the recipient, then re-run the command.
- [ ] `run-local-smoke-checks` — Start the verified recipient, confirm the home page, admin, custom routes, and any installed public module pages.
      Paths: `.`
      Rule: Smoke-check every surface the live site serves before replacing any repository.
- [ ] `replace-existing-repository` — Copy the verified recipient into the real beta-site repository while excluding .git, media, .env, and poetry.lock.
      Paths: `.`
      Rule: Never copy `.git`, `media/`, `.env`, or `poetry.lock` between the donor and the real repository.
- [ ] `create-pr-and-merge` — Commit in the real repository, open a PR, review the diff, and merge after approval.
      Paths: `.`
      Rule: Merge exactly the reviewed and verified recipient; do not hand-edit past the reviewed tip.
- [ ] `set-module-env-vars` — Configure any required Railway environment variables for newly adopted modules without storing secret values in the report.
      Paths: `modules/analytics`, `modules/auth`, `modules/forms`, `modules/listings`, `modules/notifications`, `modules/orgs`
      Rule: Set only the modules' declared environment variables; never store secret values in the report or the repository.
- [ ] `deploy-and-verify` — Deploy through the existing repo workflow, confirm migrations in logs, and run production smoke checks.
      Paths: `.`
      Rule: Confirm the deployment logs show the migrations applying before running production smoke checks.
- [ ] `keep-rollback-reference` — Keep the previous git and Railway deployment reference available until the new release is validated.
      Paths: (none)
      Rule: Retain the previous git and Railway deployment reference until the reseeded site is verified.

## Hard constraints

- Keep the donor project read-only; every change lands in the recipient.
- Never copy `.git`, `media/`, `.env`, or `poetry.lock` between the two trees.
- Do not hand-patch QuickScale-managed files such as `settings/modules.py`, `urls_modules.py`, and the generated wiring; regenerate them through the supported QuickScale workflow.
- In-place edits under vendored module source (`modules/<name>/`) are outside the extension contract: upstream them into the module or re-express them as project-owned code before the recipient is handed over.
- The migration merged the donor's declared frontend dependencies and reported every version conflict; keep the recipient's declared versions and add no dependency it does not already declare.

## Done criteria

- The recipient's `pytest` suite and frontend `pnpm test` suite pass.
- Local smoke checks pass for the home page, Django admin, custom routes, and any installed public module pages.
- Every remaining item above is completed and recorded in the migration ledger.
- The verified recipient is committed in the real repository and merged through review, with the deploy confirming migrations.

## SA191 slice (a) — production dump rehearsal

Ran on 2026-10-10 with the maintainer's Railway login. The production dump was
taken read-only from the Railway `bap-web` project (server PostgreSQL 17.11;
local `pg_dump` 18.6):

    railway run --service Postgres -- sh -c \
      'pg_dump --format=custom --no-owner --no-acl "$DATABASE_PUBLIC_URL" > /home/victor/code/bap-web-prod.dump'

The dump is 166,211 bytes at `/home/victor/code/bap-web-prod.dump` — outside
every repository and never committed; it holds real user data. It restored with
`pg_restore --no-owner` into scratch PostgreSQL 18 (container
`qs-bap-prod-scratch-pg`, published on `127.0.0.1:33292`, database
`bap_prod_scratch`, local role `postgres`, password `scratch`): exit 0, no
warnings.

The restored ledger records `quickscale_modules_listings` 0001–0003,
`quickscale_modules_forms` 0001–0003, `quickscale_modules_auth` 0001–0002, and
`properties` 0001–0002, with no `orgs` rows or tables. Against that database the
recipient's plan refuses — the history inconsistency the cutover rebuild
addresses:

    DATABASE_URL=postgresql://postgres:scratch@127.0.0.1:33292/bap_prod_scratch \
      QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET=rehearsal-placeholder \
      RESEND_API_KEY=rehearsal-placeholder POSTHOG_API_KEY=rehearsal-placeholder \
      QUICKSCALE_ALLOW_BYPASSRLS=1 \
      poetry run python manage.py migrate --plan
    ...
    django.db.migrations.exceptions.InconsistentMigrationHistory: Migration
    account.0001_initial is applied before its dependency
    quickscale_auth.0001_initial on database 'default'.
    EXIT=1

The v0.62 ledger's `quickscale_modules_*` app labels are not the current
graph's `quickscale_*` labels, so the applied history cannot move forward. The
same run's system checks also report `quickscale_orgs.W004` FORCE-RLS policy
warnings for `properties_propertylisting` and the
`quickscale_forms`/`quickscale_listings` tables (the old tables predate the
current canonical pairs) and the two known `W006` personal-data gaps (SA153
work). The cutover rebuilds a fresh database, runs
`quickscale_orgs_create_site_org` in the same deploy step as `migrate`, and
reseeds the catalog.

The scratch database stays in place as the slice (e) cutover-rehearsal target.

## SA191 slice (b) — upstream candidates

The contact-payload mapping re-expressed donor module customizations as
project-owned configuration. The following stay upstream candidates for
QuickScale, not recipient patches:

- Module-level consent recording: the donor's in-place `modules/forms` recorded
  `gdpr_consent`/`gdpr_consent_at` columns on `FormSubmission`; the recipient
  declares `gdpr_consent` as a form field instead, so consent is stored as a
  field value.
- The donor's custom submission-email template (`form_email.html`) and its
  `notifications.py` behavior were not carried.
- The theme's Vite dev proxy list omits the forms mount (`/forms`) although the
  theme hooks (`useFormSchema`, `FormRenderer`) call `/forms/api/...`, so a
  Vite-first dev workflow cannot reach the forms API. The documented workflow
  serves the SPA from Django, which is unaffected.

## SA191 slice (c) — test parity

Re-ran the parity stack on the manual-port recipient (2026-10-10):

- `poetry run pytest` — 56 passed, 94.52% coverage; local runs need the same non-live
  placeholders the generated CI sets — `QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET`,
  `RESEND_API_KEY`, `POSTHOG_API_KEY` — plus `QUICKSCALE_ALLOW_BYPASSRLS=1` for the superuser
  local database.
- Donor test accounting — no donor test file or fixture is excluded; a per-file byte comparison
  shows 9 of the 19 byte-identical, and a per-file case-name comparison accounts for the adapted
  files below (removed donor cases are named in full):
  - `tests/conftest.py` — drops the unused `__future__` import; the donor per-file coverage gate
    is restored here (see below).
  - `tests/test_project_infrastructure.py` — five donor tests are removed or replaced with the
    v0.62 contract they covered: `test_base_settings_default_public_listings_disabled` and
    `test_home_page_bootstrap_stays_disabled_when_env_flag_is_false` (the
    `PUBLIC_LISTINGS_ENABLED` flag no longer exists);
    `test_home_page_bootstrap_reflects_public_listings_flag` (replaced by
    `test_home_page_bootstrap_carries_the_runtime_seam` — the SPA bootstrap is the runtime
    seam, not a hand-rendered `publicListingsEnabled` key);
    `test_returns_false_when_models_import_fails` and
    `test_returns_false_when_db_call_raises_operational_error` (the rewired
    `public_listings_enabled()` reads installed apps and the module flag only, so it has no
    models-import or DB-error branch). Removed assertion: the local-console `EMAIL_BACKEND`
    assertion in `test_local_settings_import_with_database_url` — local settings only fall back
    to a console backend and the effective backend is owned by module wiring; the
    production-SMTP assertion is kept because production still sets SMTP explicitly.
  - `tests/properties/test_api.py` — one donor test is removed with the env flag
    (`test_all_public_property_endpoints_return_404_when_env_flag_is_disabled`); the public
    listings case is adapted, not removed
    (`test_all_public_property_endpoints_return_404_when_public_listings_are_disabled`, keyed
    on the module flag and a system organization).
  - `tests/properties/test_seed_command.py` — same test names; follows the renamed carried
    migration and the system-organization scoping.
  - `frontend/src/test/App.test.tsx`, `home.test.tsx`, `layout.test.tsx`, `pages.test.tsx` —
    same case names; the config-shape helpers are rewritten to the nested modules plus
    `modulePaths`/`owner` seam, form posts follow `/forms/api/<slug>/submit/`, and the
    `csrfToken` config entry is removed (runtime-provided).
  - `frontend/src/test/hooks.test.tsx` — three donor cases are removed and no case names are
    added; the retained case names are unchanged:
    - `returns the default modules when no project config is injected` — removed (the recipient
      resolves config only through the validated runtime seam, with no defaults).
    - `returns the default config from useProjectConfig when no config is injected` — removed
      (same reason).
    - `disables public listings when the project flag is false` — removed, subsumed by the
      donor's separately retained `disables public listings when the listings module is
      disabled` (adapted to the module flag), because the switch is the module flag.
    Its healthcheck/detail header assertions follow `Headers.get`.
  - `frontend/src/test/setup.ts` — import order only.
- Per-file coverage enforcement — the port initially omitted the donor's 80% per-file gate; it
  is restored in `tests/conftest.py` (no-ops when coverage is not collected), and the new
  `TestSettingsModules.test_base_settings_project_the_resend_secrets` case covers the
  base-settings Resend projection block that had held `bap_web/settings/base.py` at 77%.
- `pnpm exec vitest run` — 338 passed (17 files); `pnpm build` and `poetry check --lock` pass.
- `poetry run python manage.py check` — exit 0, SA208's provider-ID check included; two
  `quickscale_orgs.W006` personal-data warnings remain for the `properties` app (SA153 work).
- FORCE-RLS counts: recipient 6 tables / 12 policies; a fresh same-modules baseline (the
  recipient's module wiring minus the project-owned app) gives 5 / 10; the only delta is
  `properties_propertylisting`'s canonical pair. `quickscale_orgs_check_tenant_isolation`
  passes 6/6 on the recipient (5/5 on the baseline).
- Watch: repin to the sealed release before cutover. The embedded `orgs` predates the `--json`
  machine flag (its command takes `--format json`), and the generated `check-tenant-isolation`
  target needs `QUICKSCALE_PRIVILEGED_COMMAND=migrate` (or the bypass env) on its migrate line.
  Both resolve at repin/upstream — do not hand-patch the generated Makefile here.

## SA191 slice (d) — live parity and design-system consistency

Ran on 2026-10-10 against the live site and the local recipient, under the
amended maintainer scope: the live site keeps public listings hidden on
purpose, so catalog/detail replace live parity with design-system consistency.

**Write-safety.** The carried form mocks intercept both submit endpoints — the
recipient's `/forms/api/<slug>/submit/` and the donor's
`/api/forms/<slug>/submit/` — in `forms.spec.ts` and `journeys.spec.ts`, and
`playwright.config.ts` keeps `forms.live.spec.ts` out of external-host and
flag-off runs, so no spec can submit into production.

**Live parity (flag-off surfaces).** Baselines captured from
`https://buenosairesproperties.com` and kept in `frontend/e2e/baselines/`:
`live-home-{desktop,mobile}.png` (1440x1488, 390x1685) and
`live-contact-{desktop,mobile}.png` (1440x2043, 390x3334). The recipient run
uses `bap_web/settings/parity_off.py` (the listings module flag off — the v89
equivalent of the donor's `PUBLIC_LISTINGS_ENABLED=false`). Result:
pixel-identical at both widths — the zero-tolerance probe
(`PW_MAX_DIFF_RATIO=0`) passed all four comparisons, and the standard under-1%
gate run passed. No masks were needed; `LIVE_PARITY_MASKS` in
`live-parity.spec.ts` is empty. Read-only specs against the live site: 26
passed, 4 skipped (the two property journeys on both browsers, skipped because
the live site hides listings), 0 failed. The first full-parallel firefox pass
tripped `responsive-smoke.spec.ts`'s 3-second load budget twice (remote-origin
network contention, not a product result); the recorded run is the serial one
that passed.

**Recipient catalog (flag on).** `properties.spec.ts` (recipient-only) proves
the seam reports listings on, `/api/properties/` returns the 12 seeded
listings, `/properties` renders them, `/properties/:slug` renders a listing,
and home shows the hero property actions and the featured section. The donor's
`PUBLIC_LISTINGS_ENABLED` switch and its `PublicListingsSettings` row no longer
exist in the current contract; the equivalent gate is the listings module's
enabled flag (`QUICKSCALE_LISTINGS_ENABLED`, on because the module is
installed) plus the System org `properties_seed_catalog` creates and attaches
the catalog to. `tests/test_project_infrastructure.py` guards that local and
production keep the flag on, and `OPERATIONS.md` documents the seed/verify
step, so the cutover gets the catalog too.

**Design-system consistency.** `design-system.spec.ts` covers, at desktop and
mobile: (1) the shell (`header`, its container, the first nav link, `footer`,
its heading and container, `body`, `main`) resolves identical computed
signatures on all four pages; (2) every design-layer `type-*` class resolves
one computed signature per class (font family, size, weight, line height,
letter spacing; color too for `type-h1`), and `.font-accent` resolves one
family; (3) every `type-*` class on catalog/detail is defined in
`design/tokens.css`; (4) every Button-classified element resolves one signature
per variant/size group, nothing falls outside the component's variants except
contact's WhatsApp brand link (recorded page-scoped exception, `bg-[#25d366]`;
bespoke anchors that omit the base class set — contact's social chips — sit
outside this check, a known limit); (5) `.section-shell` and
`.section-spacing` computed spacing agrees across pages. A negative probe
proves the measurement detects a changed font size, spacing value, and color,
and every measured signature must be non-empty. Recipient
catalog/detail screenshots are kept as the new baselines:
`recipient-catalog-{desktop,mobile}.png` and
`recipient-detail-{desktop,mobile}.png`. The baselines are intentionally
committed photographic PNGs and seven of the eight exceed the commit hook's
default large-file threshold (the smallest is 390 KB), so
`.pre-commit-config.yaml` excludes `frontend/e2e/baselines/` from
`check-added-large-files`; the other hooks skip binaries.

**Suites.** Full local suite (chromium + firefox, listings on), final run over
the shipped bytes: 254 passed, 2 flaky (passed on retry — the firefox
responsive-smoke 3-second budget under parallel load, and one catalog baseline
under the same load), 7 skipped (the chromium-only design-system tests on
firefox), 0 failed.

Run modes:
- full local suite: `PW_DJANGO_PORT=<port> pnpm exec playwright test`
- flag-off compare: `PW_DJANGO_SETTINGS=bap_web.settings.parity_off PW_DJANGO_PORT=<port> pnpm exec playwright test e2e/live-parity.spec.ts --project=chromium`
- live read-only: `PWHOST=https://buenosairesproperties.com pnpm exec playwright test e2e/home.spec.ts e2e/link-checker.spec.ts e2e/responsive-smoke.spec.ts e2e/journeys.spec.ts`

**Next:** slice (e) (cutover, maintainer); slices (a) and (e) need the
maintainer's Railway login. Watch: the kept live baselines are pre-cutover
evidence; repin before cutover.

## SA191 slice (e) — cutover script, reseed step, and rollback rehearsed on scratch

Ran on 2026-10-10 on the SA191 scratch PostgreSQL 18 (`qs-bap-prod-scratch-pg`,
`127.0.0.1:33292`), against a fresh database `bap_cutover_rehearsal` (runtime
role `quickscale_runtime`, NOSUPERUSER/NOBYPASSRLS, provisioned as `start.sh`
step 3 does). `CUTOVER.md` carries the runbook, the repeatable rehearsal, and
the rollback.

- `scripts/cutover.sh` (new) exited 0 twice in a row, run from a dropped and
  recreated database. Run 1: migrations applied; site organization `bap-web`
  ("Buenos Aires Properties") created under the runtime role;
  `scripts/reseed_catalog.sh` (new) reseeded the catalog and
  `scripts/reseed_service_forms.sh` (new) created the six service inquiry forms,
  all under the same runtime role, printing role evidence
  `superuser=False, bypassrls=False`; catalog counts 3 agents / 12 properties /
  48 images / 60 features in the System org scope; service forms verified
  (slugs, active, and the `full_name`/`email`/`subject`/`project_context`/
  `gdpr_consent` field set), with `SITE_FORM_NOTIFY_EMAILS` stored on each;
  unscoped reads (manager and raw SQL) returned 0 (RLS fail closed);
  `migrate --check` exit 0; `manage.py check` exit 0 with only the two known
  `quickscale_orgs.W006` properties personal-data warnings (SA153 work); the
  tenant-isolation conformance check passed 6/6 on the same six tenant models
  as the local recipient baseline. Run 2: organization no-op, catalog refresh
  (`+0/~3`, `+0/~12`), all six forms skipped, same counts and 6/6 — idempotent.
- Negative controls: a missing `RUNTIME_DATABASE_URL` exits 2; a runtime URL
  naming the superuser connection is refused by `quickscale_orgs.E004` (exit 1);
  `DATABASE_URL` and `RUNTIME_DATABASE_URL` addressing different databases
  exits 1 before any write.
- Served smoke on the rebuilt database (recipient run under the runtime role
  with production settings): `/healthcheck/` 200; `/api/properties/` 200 with
  `"count": 12`; and a real contact submission — `POST
  /forms/api/reubicacion/submit/` → 201 with the row stored — proves the
  rebuilt database serves the contact-page forms.
- Retained copy: `bap_prod_scratch` (the slice (a) restore) was not touched —
  its 23-table row-count fingerprint and its `django_migrations` ledger md5
  (`cff58b76…`) are identical before and after the rehearsal. Rollback keeps
  that database as the restore target for the previous deployment.

Watch: repin to the sealed release before cutover and re-run the rehearsal
(`CUTOVER.md`); the on-Railway execution — new repository, service cutover,
media, user re-invites — remains the maintainer's step.

## SA191 repin (1) — core pinned to the `v89` tree; rehearsal re-run green

Ran on 2026-10-17. The frozen wheel pin (`quickscale_core-0.89.0-py3-none-any.whl`,
built 2026-10-09) is replaced in `pyproject.toml` by a path pin on the `v89` checkout
(`quickscale-core = {path = "/home/victor/code/quickscale/quickscale_core", develop = true}`),
poetry re-locked, and the rehearsal re-run on the scratch PostgreSQL
(`qs-bap-prod-scratch-pg`, `127.0.0.1:32768`) against a dropped and recreated
`bap_cutover_rehearsal`: `poetry run bash scripts/cutover.sh` exit 0 twice, catalog
3/12/48/60 and the six service forms verified in the System org scope, unscoped reads 0,
tenant isolation 6/6, `migrate --check` clean, `manage.py check` with only the two known
`W006` properties warnings (the `W004`s inside the pre-migration check run are the
empty-database state). A git rev pin was tested and refuted for this tree: an installed
git clone carries no bundled manifests (`data/manifests/*/` is a build-time
materialization) and its install path has no `quickscale_modules/`, so
`load_module_manifest_with_fallback` fails (`ManifestError`) — probed with poetry git
dependencies (`rev`, and `develop = true`, both installing non-editable into
site-packages) and pip. The path pin resolves manifests from the checkout's
`quickscale_modules/`, which is the `v89` tree's own manifest workspace.

Watch: the six embedded `modules/` copies are still the 2026-10-09 split-branch
snapshots (stale against this tree) — the next repin step re-embeds them from refreshed
split branches (`make publish-modules`), so module code and manifest reads never drift
apart. The scratch rehearsal port moved (33292 → 32768); `CUTOVER.md` now records the
current mapping.

Slice 1 intermediate state (resolved by slice 2 below): the project suite was 54 passed / 3
failed under the pin. The three were the SPA-shell tests (`GET /`, `GET /contact`, and the orgs
shell view), all `NoReverseMatch` on `quickscale_listings_shell` from `index.html`'s runtime seam
tag: the current core composes the shell routes through the managed URLconf
(`compose_managed_urlpatterns`), which this project had not adopted yet, and re-embedding the
modules alone does not register `SPA_MODULE_URLPATTERNS`. The adoption step
(`sa258-managed-urlconf`, one of the 16 then-pending contract steps) is what restored the SPA
shell; slice 2 landed it. The rehearsal's green result stands as-is: it does not exercise the
SPA shell surfaces.

## SA191 repin (2) — modules re-embedded, contract adoption recorded, suites green

Ran on 2026-10-17, under the maintainer's authorization for the release-prep steps. The local
`0.89.0` tag was re-pointed at the v89 HEAD (`ee8540c9`), `make publish-modules` refreshed every
outdated split branch (12 modules; nothing was pushed to PyPI), and the tag was re-pointed at the
batch's rejoin merge (`e66ea40b`). All CLI operations ran through the v89 checkout's CLI
(`/home/victor/code/quickscale/.venv/bin/quickscale`); the user-level CLI venv is a stale Oct-9
build.

The six Oct-9 embedded modules moved to the v89 split content. SA204's equal-label guard refuses
a `quickscale update` pull that replaces applied migration content under an unchanged label, so
the reconciliation ran through `git subtree pull` from the refreshed branches first — the
guard's own "reconcile the embedded module content before updating" path — and the six modules'
`quickscale-core` pins became the bounded range the embed flow writes. Then:

- `quickscale apply --split-ref storage=splits/storage-module --confirm-contract-adoption` added
  storage (the v89 `listings` requirement), regenerated the managed URLconf
  (`bap_web/urls_modules.py` now composes the shell routes through
  `compose_managed_urlpatterns`), the theme seam declaration and key manifest, the managed CI
  environment, and the module operations page, and recorded the generated-project contract
  adoption in `.quickscale/state.yml`.
- `quickscale update --no-preview --confirm-contract-adoption` recorded the fresh split shas for
  all seven modules and regenerated the wiring; the project's `quickscale-core` pin was restored
  to the v89 path pin afterwards (the dependency repin rewrites it to the range; the pin stays a
  path pin until 0.89.0 is published).
- Project alignment the refresh required: `published_date` → `published_at` across `properties/`
  (model hook, admin, seed, migration 0001 field/ordering/index name — SA266 renamed the module
  field), and `settings/base.py` now passes the managed `MODULE_THROTTLE_SCOPES` into
  `compose_rest_framework` (SA291 (b)), so the forms submit throttle has its rate. The adoption's
  frontend half (seam consumers, one error parser, templates, CI/Docker/ops files) landed with
  the tests moved onto `seamFixtures`.

Validation: `poetry run pytest` 57 passed / 0 failed (coverage 93.94%); frontend `pnpm
type-check`, `pnpm build`, and `pnpm test` 387 passed with the per-file coverage gate green; the
cutover rehearsal ran exit 0 twice on a reset `bap_cutover_rehearsal` (catalog 3/12/48/60, the
six service forms, unscoped reads 0, tenant isolation 6/6, only the two known `W006` properties
warnings post-migration). The rehearsal needs a valid base64 `whsec_` notifications secret now;
`CUTOVER.md` carries it.

Watch: the pre-existing lint debt is unchanged (`pnpm lint` fails on four donor files;
`poetry run ruff` carries the `ebe1aa4` baseline findings in `settings/production.py`,
`views.py`, `properties/views.py`, `tests/properties/test_api.py`). `.quickscale/wheels/` (the
stale wheel of the replaced pin) was moved aside for the CLI's clean-tree checks and restored
afterwards; a later CLI update needs it out of the tree again. A second drift opened after the
publish: v89 landed `quickscale_modules/{analytics,billing,notifications}/checks.py` changes
(SA291 (c)) after the split branches were refreshed, so the next re-pin must re-run
`make publish-modules` before the cutover and re-embed those modules again.

## SA153 (a, b) — explicit currency labels and tenant-owned gallery/feature children

Ran on 2026-10-17 on the project-owned `properties` app, following
module-extension.md § Project-Owned Tenant Models and decisions § Child tables.

- `PropertyListing.currency` carries the price's currency as an explicit ISO code with a
  display label (`US$` / `ARS$` / `€`; default `EUR`), seeded from
  `properties/data/catalog.json` and exposed on the public API as `currency` plus
  `currencyLabel`. The existing catalog keeps its EUR meaning: the seed labels every row
  explicitly and migration `0004` backfills existing rows as `EUR`, so no price is silently
  re-denominated; the label states the currency as-is and implies no exchange-rate
  conversion.
- `PropertyImage` and `PropertyFeature` are tenant-owned `TenantModel` children now: each row
  denormalizes its listing's `organization_id`, is tied to the parent by the composite
  `(property_id, organization_id)` FK (orgs' W007 contract), and carries the canonical
  two-policy FORCE-RLS pair. `0005_tenant_owned_property_children` backfills the existing
  rows; `0004_propertylisting_currency` adds the label.
- `PropertyListing.objects` is a tenant-scoped manager
  (`TenantManager.from_queryset(PropertyListingQuerySet)`) now, so the public API, the admin,
  and the catalog sync all read inside the current organization; the seed stamps the parent
  listing's organization onto every child row and the admin stamps it on inline child saves.
- The app declares its personal-data exclusions (`PropertyAgent.email`,
  `PropertyListing.featured_image`) and its removal obligation (`property-listing-state`:
  purge deletes, account removal keeps), so `manage.py check` reports zero findings and the
  marker-derived purge plan covers the property tables.

Validation: project suite 68 passed / 0 failed (the 93.94% figure and the per-file gate
cover `bap_web` only — the project's configured `--cov` source excludes `properties/`, so
the properties code above carries no coverage measure); `manage.py check` clean; `quickscale_orgs_check_tenant_isolation --postgres-only --json`
reports `properties_propertylisting`, `properties_propertyimage`, and
`properties_propertyfeature` passed with no unclassified model; migrations 0004/0005 applied
— and rolled back and re-applied — on a clone of `bap_cutover_rehearsal`, backfilling all 48
image and 60 feature rows with zero NULL organizations. New tests:
`tests/properties/test_tenant_contract.py` (enrollment, the orgs checks, provider-ID
classification, purge plan and ordering, composite-FK refusal, manager fail-closed) and
`tests/properties/test_rls_boundary.py` (FORCE RLS cross-organization denial and fail-closed
reads under a restricted role).

Watch: the frontend still formats every price with a hard-coded `es-ES` EUR formatter
(`frontend/src/lib/format.ts`) while the catalog is EUR-labeled, so the two agree today;
slice (c, d, e) consumes the new per-listing `currency` field so a future non-EUR listing
labels correctly. The pre-cutover re-pin (re-run `make publish-modules` and re-embed
analytics and notifications) is still owed before the cutover.

## SA153 (c, d) — currency labels, and the inquiry that files its CRM record

Ran on 2026-10-17. Slice (c): every price on the catalog, the detail page, and the
email/SEO strings is formatted with the listing's own ISO `currency` through cached
`Intl` formatters, and the public `filter-metadata` endpoint reports the catalog's single
currency — `null` when the catalog mixes currencies — which the price-range slider labels
with, falling back to unlabelled numbers (never a currency it cannot vouch for).

Slice (d): the `crm` module is embedded now (desired state, `splits/crm-module` at the
v89 vintage; the analytics/billing/notifications drift note above still stands). The
public catalog gained `POST /api/properties/<slug>/inquiries/`: it stores a tenant-owned
`PropertyInquiry` (migration 0006 — own `organization_id`, composite
`(property_id, organization_id)` FK, canonical two-policy FORCE-RLS pair) and records the
inquiry in the CRM inside the same org-scoped transaction — a shared per-organization
web-inquiry company, a contact for the visitor (reused by address on a return visit), a
deal the operator works from, and a note carrying the listing reference
(`ref /properties/<slug>`). The detail page's agent card takes the inquiry inline; a
filled honeypot returns the accepted response without storing anything.

Validation: project suite 79 passed / 0 failed (93.94%); frontend 400 passed (coverage
gate green), `tsc --noEmit` and the changed files' ESLint/Prettier clean (the pre-existing
donor lint debt is unchanged); the chromium design-system + properties specs 12 passed on
a freshly built bundle (the two detail screenshot baselines regenerated to carry the
inline inquiry form); `manage.py check` clean on a freshly migrated database;
`quickscale_orgs_check_tenant_isolation --postgres-only --json` passes on the four
property tables; migration 0006 applied, reversed, and re-applied on the scratch
PostgreSQL (`bap_sa153_de`; the `apply` destructive phase ran on `bap_apply_scratch`).

Watch — slice (e) (prerender, Open Graph, sitemap, `robots.txt`, crawler test, rendered-page
isolation) was NOT landed in this session. The mechanism is recorded (decisions § Frontend
Rendering Decisions, SA241): Vite's SSR build with `react-dom/server` at the project's
build/deploy step, Django serves the documents, React hydrates. Two findings from the
discovery pass constrain it: (1) hydration needs the client tree to match the served
markup, and the SPA boots `<BrowserRouter><App/></BrowserRouter>` while a prerender needs
`StaticRouter` plus a dehydrated react-query state — the theme's public-surface seam
(`window.__QUICKSCALE__.publicPage`) accepts only the social surfaces today, so a
properties surface or a prerender marker is a seam-contract extension (the generated seam
types live in Track 3's ownership), and the one-seam rule leaves no other place for the
dehydrated state; (2) the Docker build stage has Node but no database and the runtime
image has the database but no Node, so the step must read the committed catalog snapshot
(`properties/data/catalog.json`, the source the deploy reseeds from) at image build, or
run as an operator/CI step against a live API — either way the generated documents and
`static`/`templates` serving path need a deliberate choice before implementation.

## SA153 (e1) — the build-time render path: prerendered documents, seam-carrying state

Ran on 2026-10-17. The public catalog and detail pages are prerendered documents a
crawler that runs no JavaScript receives with their content and Open Graph tags, under
decisions § Frontend Rendering Decisions; the seam work the (c, d) discovery flagged is
part of the slice's cross-track edit (the theme's `publicPage` seam type, with Track 3
review at the merge).

**The design decision (the slice's one).** The prerender runs at image build from a
committed snapshot, never from a live database: `manage.py bap_web_prerender_snapshot`
exports the public API's exact JSON shape (`properties/data/api_snapshot.json`, DRF's
own serializer and encoder, System-org public scope only), and
`pnpm --dir frontend prerender` (`vite build --ssr` + `scripts/prerender.mjs`) renders one
catalog document plus one document per published listing into `prerender/`. The snapshot is a
committed input refreshed by the command; the SSR bundle and the documents regenerate in the
frontend stage at image build from that snapshot, so a deploy ships documents that match the
snapshot (refresh and commit the snapshot when the catalog changes). The documents are kept
outside `STATICFILES_DIRS` and `STATIC_ROOT`, so no static URL bypasses the serving guards.
Document URLs are built from `PRERENDER_SITE_ORIGIN` (default
`https://buenosairesproperties.com`).

- Seam: `window.__QUICKSCALE__.publicPage` accepts `{module: 'properties', surface:
  'catalog'|'detail', path, dehydratedState}`; `main.tsx` seeds the query cache from the
  state and adopts the served markup with `hydrateRoot`, and `renderQuickScaleRoot.tsx`
  renders the app tree at a caller-provided static location for the SSR entry (the browser
  keeps `BrowserRouter`). The same files landed in the theme source (the cross-track edit
  named in the roadmap) and in this project.
- Serving: `bap_web.views.properties_catalog_view` / `properties_detail_view` (wired in
  `bap_web/urls.py` ahead of the catch-all) serve the artifact through
  `templates/index.html`'s new `prerender_head_html` / `prerender_body_html` /
  `prerender_public_page` context. The detail route serves a document only while the slug
  is a public listing in the System org (the API's own scope), and the catalog route
  verifies every listing its artifact embeds is still public there; a missing, malformed,
  or non-public artifact falls back to the client-rendered shell, and listings-disabled
  serves the shell.
- Crawler test: `frontend/e2e/crawler.spec.ts` (chromium) reads the raw responses for
  both documents and re-checks the catalog and one listing through a `javaScriptEnabled:
  false` browsing context; it is gated like the properties/design-system specs.

Validation: project suite 109 passed / 0 failed (coverage 94.18%, per-file gate green;
`bap_web/views.py` 100%); frontend 428 passed with `pnpm test:coverage` green (`tsc
--noEmit` clean; the changed files' ESLint/Prettier clean, the pre-existing donor lint
debt unchanged); the full chromium Playwright project 135 passed, the crawler spec's 3
included; the artifact freshness is guarded by a vitest test against the committed
snapshot and a pytest test against the seeded catalog's fresh export, and the API-parity
tests compare the snapshot with the live API responses. On the QuickScale side: `make
lint-frontend` exit 0, 87 theme-integration and
32 generator tests passed, roadmap consistency 138 passed.

Watch: (e2) adds `sitemap.xml` and `robots.txt` from the same snapshot; (e3) proves
rendered-page organization isolation and the journey over the prerendered pages — the
serving guard above is in place, its proof is (e3)'s. The prerendered detail pages show
the similar/featured sections' client loading state (their queries hydrate emptier than
the page's own listing) and fill after hydration — deliberate. The e2e harness's
notifications placeholder was `whsec_test_e2e`, which the current Svix-format check
refuses; it is now the CI env's non-live `whsec_…` value, a pre-existing harness break
fixed to run the crawler spec. The pre-cutover re-pin (re-run `make publish-modules` and
re-embed analytics and notifications) is still owed before the cutover, unchanged.

## SA153 (e2) — the sitemap and robots file from the same published-listings snapshot

Ran on 2026-10-17, under decisions § Frontend Rendering Decisions (Decision 2: `sitemap.xml`
and `robots.txt` are generated from the published listings in the same step, never from a
hand-maintained list).

- Generation: `buildPrerenderArtifacts` (`frontend/src/prerender/artifacts.ts`) now also
  emits `sitemap.xml` (the catalog URL plus one URL per published listing, sorted, absolute
  against `PRERENDER_SITE_ORIGIN`) and `robots.txt` (`User-agent: *`, `Allow: /`, and the
  `Sitemap:` line) from the same committed snapshot the catalog and detail documents are
  rendered from; `scripts/prerender.mjs` writes them, the committed artifacts stay
  byte-stable (the vitest freshness test covers them), and the Dockerfile's copy carries
  documents and crawler files.
- Serving: `bap_web.views.sitemap_view` and `robots_view` (wired in `bap_web/urls.py`
  ahead of the catch-all) serve `prerender/sitemap.xml` and `prerender/robots.txt` from
  `PRERENDER_DIR`. The sitemap is refused as a 404 while `QUICKSCALE_LISTINGS_ENABLED` is
  off or the artifact is missing or malformed (the loader requires a urlset whose every
  entry carries an absolute location); robots is a site-wide crawling contract and is
  served whenever its artifact exists.
- Crawler test: the sitemap and robots assertions landed in `frontend/e2e/crawler.spec.ts`.

Validation: project suite 122 passed / 0 failed (coverage 94.67%, the per-file gate green);
frontend 432 passed with `pnpm test:coverage` green (`tsc --noEmit` clean; the changed
files' ESLint/Prettier clean, the pre-existing donor lint debt unchanged); the full
chromium Playwright project 136 passed, the crawler spec's new sitemap/robots case
included; `mypy bap_web/` unchanged (the pre-existing errors live in files this slice did
not touch); roadmap consistency 138 passed on the `v89` side.

Watch: (e3) proves rendered-page organization isolation and the journey over the
prerendered pages — unchanged, and the serving guard above remains in place. The sitemap
advertises the snapshot's listings per the step's model: a listing withdrawn after the
image build stays listed until the step re-runs and the deploy lands — the same refresh
window the documents have, without the documents' live public-scope refusal, since the
sitemap carries URLs rather than content. `robots.txt` stays served while
`QUICKSCALE_LISTINGS_ENABLED` is off, when `/sitemap.xml` answers 404.
