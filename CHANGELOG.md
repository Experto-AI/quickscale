# Changelog

`CHANGELOG.md` is the canonical QuickScale release history index. Each published version pairs with one official release note in `docs/releases/`, linked from its GitHub tag. A release note prepared before the maintainer completes the manual tag/publish step must say so and must not imply publication. Use `docs/technical/roadmap.md` for active or unpublished release status. Entries are version-ordered.

## How to write an entry

Each version is **one line** — `- vX.Y.Z — <status/date> — [Title](docs/releases/release-vX.Y.Z.md). <what it consolidates>` — followed by indented sub-bullets, one per change. The version line must stay a single self-contained line: the publish workflow greps `^- vX.Y.Z` and uses that one line verbatim as the GitHub Release body. (A "not published" status in it must therefore be reworded before the tag is pushed.)

A sub-bullet is a **bold headline plus one sentence of observable behavior**, present tense, describing what is now true:

```
- **E2E memory guard.** Low-memory conditions override explicit xdist counts and force serial
  execution unless `QS_E2E_NO_MEMORY_GUARD=1` is set.
```

Two sentences maximum. Name the setting, command, or file a reader would touch.

**Never put in a changelog entry:** ticket IDs (`SA160`, `TA67`, `EV-8`), commit SHAs, branch or worktree names, dates inside sub-bullets, test/pass/skip counts, coverage percentages, timings, exit codes, evidence paths, or review, attestation, and authorization status. No planning narration — rebalance passes, track moves, "retained partial", "ticket remains open", "no-verdict", what was superseded or corrected in a later pass.

Those belong elsewhere: planning and ticket state in `docs/technical/roadmap.md`; validation evidence in the release note's Validation section; process history in Git.

**The test:** if the change cannot be stated without naming a ticket or a run, it is process, not a change, and it does not go here. Write for someone upgrading QuickScale who never saw the work happen. One bullet per change — describe the end state only, not the path to it, and amend the existing bullet rather than appending a correction.

## Releases

- v0.89.0 — prepared, not published — [Development Maintenance](docs/releases/release-v0.89.0.md). Begins the post-v0.88 maintenance line with source-derived validation expectations.
  - **Gate-parity counts derive from their sources.** The parity suite computes registry-bound and workflow-station expectations from their authoritative declarations, so adding a gate updates derived counts without a hand edit.
  - **Version-derived test expectations.** CLI wiring, module-command, billing, and notifications tests derive the expected current version from package metadata instead of a pinned release string, so version bumps no longer require matching test edits.
  - **Project-owned tenant models join isolation checks.** Models in a project app inherit `TenantModel` (directly or through a module's abstract base) and declare their own FORCE RLS migration so classification and policy refresh cover them while retaining organization ownership and forced row-level security.
  - **Tenant models share one base.** Every organization-scoped model inherits `TenantModel`, and a `TenantManager` on a model that does not inherit it fails startup, so a half-built tenant model cannot go unenrolled.
  - **Reverse accessors and model choices follow one convention.** Relations to another module's models use `quickscale_<module>_<name>` reverse names, `FormFieldValue` orders deterministically, and model choice lists use `TextChoices` members instead of tuple constants.
  - **Organization removal follows installed tenant metadata.** `purge_organization` discovers project-owned tenant models and child-before-parent order automatically, refuses destructive execution and dry runs while a live Stripe subscription or active checkout reservation exists, and reconciles elapsed checkout sessions with Stripe before deletion under the organization-keyed provider advisory mutex; local mutations use organization-row locks. Purge and account deletion share explicit billing, row-deletion, cache, and tombstone obligations declared by each owning app and discharged through one coordinator that fails closed when a boundary skips a declared obligation, with declared provider fields refusing the purge until they are cleared or reconciled and app-owned stages running the declaring app's own hook, without weakening last-owner safeguards, while terminal or provider-confirmed expired billing rows remain purgeable.
  - **Server-rendered module pages share the project shell.** The blog, listings, and CRM base templates extend the project's `base.html` instead of emitting their own `<html>` document, so those pages inherit the site topbar, messages, and footer. Their child templates now fill `blog_content`, `listings_content`, and `crm_content`; a project that overrode one of these templates must rename its content block to match.
  - **CRM styling moved into a stylesheet.** CRM page styles live in `quickscale_crm/css/crm.css` rather than an inline `<style>` block, and cover CRM content only — the page shell comes from `base.html`.
  - **Module page content keeps its spacing under the shared shell.** Each module base wraps its page content in a `<div class="<module>-content">` and its stylesheet sets the vertical rhythm there, because the project `base.html` reset zeroes default margins.
  - **Frontend architecture is documented.** [docs/technical/frontend.md](docs/technical/frontend.md) defines the `window.__QUICKSCALE__` seam, URL ownership between the React shell and module routes, the Vite/`collectstatic` pipeline, and the template-inheritance rule for server-rendered module surfaces.
  - **Railway re-deploys preserve live configuration.** `quickscale deploy railway` reuses the service's `SECRET_KEY` and runtime-role password, and aborts rather than guessing when Railway variables are unreadable or the PostgreSQL service is ambiguous.
  - **Generated-project contract changes are declared once and adoption is recorded.** One project-level declaration owns each generated-template contract change and its adoption steps; `quickscale update`, `quickscale apply`, and `quickscale deploy railway` name the outstanding steps, `--confirm-contract-adoption` records the adopted vintage in `.quickscale/state.yml`, and a registered gate fails when a generated template changes without a declaration edit.
  - **Declared contract coverage matches the generated project.** Provider-ID classification now has its own adoption step, a module manifest's step text cannot change without a new id, and the template-change gate watches every file the generator emits — so `pyproject.toml` and `OPERATIONS.md` changes cannot ship without a declared step.
  - **RLS policy predicates are verified.** The isolation-conformance suite compares every marker-enrolled table's live `qual` and `with_check` expressions with the exact tenant-write and operator-read contract, so weakened policies fail instead of passing on presence alone.
  - **Split publication refuses non-fast-forward overwrites.** Before each split-branch push, `make publish-modules` and single-module publication require the observed remote tip to be an ancestor of the local split, stopping the batch and naming the module on divergence.
  - **Privileged commands stay on a fixed two-command contract.** Only `migrate` and `createcachetable` receive the automatic superuser connection; the retired `migrate_billing_to_orgs` command and its recovery documentation are removed, unsupported launcher argv fails closed, and declaration drift is checked across every enforcing station.
  - **Malformed authentication headers fail closed.** Non-ASCII notifications webhook signatures
    now return their normal authentication failure instead of raising a server error.
  - **Webhook endpoints answer the one error shape.** The Stripe and notifications webhooks are DRF views that answer `200` with `{"status": "accepted", "duplicate": <bool>}`, `400` with a stable `webhook_signature_invalid` or `webhook_payload_invalid` code, or `404` when the module is off; a bad signature is no longer answered `403`, and notifications verifies its signature before parsing the body.
  - **Beta migration is single-mode.** `make beta-migrate-fresh` reports effective runtime provenance, rejects dynamic command settings and launcher/package skew before mutation, reconciles the complete generated slug/package seam, and runs isolated generated-project coverage through `make check-beta-migration-smoke`; the in-place migration path and its continuation are removed.
  - **Beta migration hands off through one prompt.** A `make beta-migrate-fresh` run that
    completes its verification stack writes `MIGRATION_PROMPT.md` into the recipient with what was
    migrated, the remaining manual actions and their paths and governing rules, the hard
    constraints, and the done criteria.
  - **Runtime database role provisioning is consistent.** Generated local setup, Railway deployment, and `OPERATIONS.md` use the shared `quickscale_runtime` name and one grant set that includes database `CONNECT`.
  - **Module pages share the project shell and design tokens, and their tests share one stub.** Auth, billing, blog, listings, and CRM Django pages use the generated React theme's tokens — the live Vite `frontend/src/index.css` in DEBUG, the compiled stylesheet otherwise — and Vite accepts only the exact browser-visible Host derived from `QUICKSCALE_FRONTEND_HOST_PORT` or `QUICKSCALE_FRONTEND_ORIGIN`. The blog, CRM, listings, and analytics module test settings point at one repository-owned test `base.html`, while auth and billing keep local stubs that preserve their older shell assertions.
  - **Payment-path transaction boundaries and Stripe query safety.** Account deletion runs its
    Stripe calls between short database transactions and restores the cancellation state when
    deletion is rejected; webhook processing holds a session-level lock across its handler and
    result persistence; and Stripe customer search refuses a reference containing an apostrophe, a
    backslash, or a newline instead of interpolating it into the query.
  - **Billing works against the real Stripe SDK at API version `2026-06-24.dahlia`.** SDK objects
    are converted before normalization, the pinned version is set on the SDK, a webhook event from
    a different named release is refused with a retryable 500 instead of being misread, invoice and
    subscription parsing reads the current payload shapes, and the billing docs and generated
    operations guide name the required webhook endpoint version.
  - **Module credential placeholders derive from declarations.** The generated `.env.example`
    renders one managed block per enabled credential-bearing module from that module's declared
    env-var options, so enabling `storage` or `backups` — including on an existing project's next
    `apply` — now shows the variables those modules require, and a conformance check fails when a
    declared variable has no placeholder.
  - **Module settings are declared once and checked at startup.** `quickscale apply` writes a
    `MODULE_SETTINGS_SCHEMA` into the managed `settings/modules.py`, and each module validates its
    declared settings against it at startup — refusing a missing, wrong-typed, or rule-violating
    value with the setting's name and the `quickscale apply` fix. Module code reads its declared
    settings directly, with no code defaults.
  - **Generated settings gate proxy trust and bound the correlation id.** The generated production
    settings trust `X-Forwarded-Proto` only while `USE_X_FORWARDED_FOR` is enabled, so a single-host
    deployment no longer lets a spoofed header suppress the HTTPS redirect or set secure cookies on
    a plaintext response; the correlation-id middleware replaces any client `X-Request-ID` outside
    a 64-character `[A-Za-z0-9._-]` shape with a fresh UUID, and a registered gate deploy-checks a
    freshly generated project in both forwarding cells.
  - **Backup and restore commands inherit the database's TLS posture.** `pg_dump` and `pg_restore`
    receive the active Django connection's `sslmode`, `sslrootcert`, `sslcert`, `sslkey`, and
    `connect_timeout` through libpq environment variables, so a deployment that verifies the server
    certificate keeps verifying it while the database is moved and a strict-TLS deployment whose
    server cannot satisfy the request now fails its backup instead of completing it in plaintext.
  - **Restore refuses a schema the running modules cannot read.** A recorded backup artifact whose
    metadata module versions differ from the installed modules — or that records none — is refused
    before `pg_restore` runs, naming each differing module with both versions, and the DR snapshot
    route compares the vintage recorded with the snapshot's authoritative dump.
  - **The generator fails closed on undefined template context.** A missing or renamed context key
    raises during generation instead of rendering empty text, and the release lane boots a freshly
    generated project through its shipped `start.sh` and asserts `/healthcheck/` answers `OK`.
  - **The publishing supply chain is pinned and scanned.** Every third-party `uses:` across the four
    workflows is pinned to a full commit SHA with its human-readable version, Poetry installs at a
    fixed release, and each workflow declares a minimal top-level `permissions:` block, while
    `make check-workflow-security` and `make check-secret-scanning` fail on an unpinned ref, a
    missing permissions block, or a committed secret. Every package's `[build-system]` bounds
    `poetry-core`, and Ruff's security rules now govern maintained source.
  - **Generated projects share one throttling contract.** The generated settings declare
    conservative `anon` and `user` DRF throttle rates that module-supplied scopes extend, and each
    module scope carries the `quickscale_<module>_<purpose>` stem with its rate read from that
    module's `_RATE_LIMIT` setting — checkout and billing-portal POSTs keep their tighter billing
    scope, form submissions their `quickscale_forms_submit` scope, and the blog automation API its
    `quickscale_blog_api` scope.
  - **Module updates regenerate the managed wiring.** `quickscale update` regenerates
    `<package>/settings/modules.py` and `<package>/urls_modules.py` from the pulled manifests and
    commits them with the module update, so module-contributed settings such as the DRF throttle
    scopes and rates never lag behind the module code; a failed regeneration rolls the update back.
  - **The orgs boot path installs its guards under privileged commands.** A sanctioned privileged
    database command now skips only the BYPASSRLS role check; the GUC priming wrapper, the
    last-owner deletion backstop, and the tenant-isolation system check install on every startup
    path, and the backstop also covers the historical model a data migration deletes through, so
    removing the sole owner of an organization that still has members fails closed.
  - **Runtime contracts ship as library code.** Generated settings import the client-identity and
    correlation-id middleware, the trusted-proxy derivation, the privileged-command/runtime-database
    selection, and the production SECRET_KEY guard from the versioned
    `quickscale_core.runtime.settings` facade and keep only user configuration, so a contract fix
    reaches a project that has adopted the facade through the lockstep pin instead of only newly
    generated ones. Every generated project declares the bounded `quickscale-core` pin, and the
    beta-migration tool refuses a donor `production.py` that keeps an inline copy of the
    command-mode contract.
  - **Provider-backed project IDs refuse organization purge.** A project tenant model classifies
    each of its non-relational `*_id` fields as `provider-backed` or `not-provider-backed` in
    `provider_id_classification`, the orgs provider-ID system check fails on any field that neither
    a declared obligation nor its model classifies, and `purge_organization` refuses an organization
    whose rows still carry a provider-backed value, naming the field.
  - **Generated projects bound their build backend.** A newly generated project's `pyproject.toml`
    declares `requires = ["poetry-core>=2.0,<3.0"]` in `[build-system]`, matching the repository's
    own packages.
  - **Supply-chain pins stay fresh and the generated container is scanned.** `make refresh-action-pins`
    rewrites every SHA-pinned third-party action to its latest release — moving the generated
    `ci.yml` pins through `scripts/sync_ci_gate_jobs.py`'s constants and its regeneration — and
    `publish_procedure.md` runs it before release-tier validation, with Dependabot security alerts
    staying enabled as the between-release safety net. The workflow-security gate reads the pinned
    `zizmor` version from `pyproject.toml` instead of a hand copy, and the dependency gate renders a
    fresh project and fails on high-severity Trivy misconfiguration findings in its `Dockerfile`.
  - **API errors answer one QuickScale shape.** Fresh generated settings install
    `quickscale_core.runtime.conventions.exception_handler` as their DRF exception handler, so every
    DRF-handled API error answers `{"error": {"code", "message", "fields"}}` with the HTTP status
    carrying the error class; the same facade exports the shared `AppConfig` capability collector
    and the startup-check runner that fails every process and registers a module's checks as system
    checks, and existing projects adopt the handler through a declared contract step.

  - **Module identities use one `quickscale_<module>` stem.** App labels, database tables,
    migration references, content types, permissions, `AUTH_USER_MODEL`, template folders,
    constraint and index names, and management commands such as
    `quickscale_orgs_check_tenant_isolation` all carry the stem; a database created from an
    earlier release keeps the old table and permission names, so recreate it on upgrade.
  - **Module startup checks run through one helper, and module exceptions share one base.**
    Invalid configuration and an empty vendor secret in an enabled module now refuse `runserver`,
    `migrate`, and `manage.py check` alike. Each module's own errors derive from one
    `<Module>Error` base in its `exceptions.py`, while `services.py` keeps re-exporting them.

  - **Module packages follow one file layout.** Package roots export only their version,
    signal receivers live in `receivers.py` while `signals.py` holds the signals a module sends,
    every module ships `poetry.toml`, and auth's allauth adapter (`allauth_adapter.py`), orgs'
    debug helpers (`_debug.py`), social's cache keys (`quickscale_social:*`), and storage's
    timestamps and root exports take their standard names and homes. An import of
    `quickscale_modules_storage.<helper>` moves to `quickscale_modules_storage.helpers` or the
    module's `services.py`, and the retired `default_app_config` declarations and unread
    per-module `[tool.mypy]` blocks are gone.

  - **Manifest option checks are enforced where options are validated.** Every `module.yml` option
    declares `type`, `description`, and a `validation` block — `choices`, `min`/`max`, `pattern`, or
    the cross-option `required_when`/`any_of` keys — and `quickscale plan`/`apply` fail with the
    setting's name when a supplied value violates one. A mutable option's `django_setting` is its
    only one-to-one projection, so the duplicate `derived_settings` entries are gone and a
    transformed or computed setting carries no default.
  - **Destructive module commands support `--dry-run`.** `quickscale_backups_prune`,
    `quickscale_forms_anonymize_submissions`, and `quickscale_orgs_promote_to_saas` report what
    they would change and write nothing, and `quickscale_orgs_check_tenant_isolation` reports
    failures through `CommandError` instead of exiting directly.
  - **Module type checking follows one capped override.** Every module's root `mypy.ini` section
    relaxes at most `disallow_untyped_defs`, `warn_return_any`, `warn_unused_ignores`, and the
    `var-annotated` error code, and `make typecheck` passes across all twelve modules.

  - **Blog and listings configuration is manifest-owned.** Their option defaults, CLI prompts, and
    validation come from `module.yml` through one manifest-driven configurator and the shared
    engine, so a wrong type or a value outside the declared constraints is refused with the
    setting's name.
  - **CRM and forms configuration is manifest-owned.** Their option defaults, CLI prompts, and
    validation come from `module.yml` through the same manifest-driven configurator and shared
    engine, and a manifest's `retired_options` block refuses a retired key such as CRM's
    `default_pipeline_stages` in `quickscale.yml` and state with its removal message.
  - **Analytics and billing configuration is manifest-owned.** Their option defaults, CLI prompts,
    env-var-name patterns, and billing's currency choices come from `module.yml` through the same
    manifest-driven configurator and shared engine, and `quickscale.yml` refuses any key no module
    manifest declares.
  - **Auth and orgs configuration is manifest-owned.** Their option defaults, CLI prompts, and
    validation come from `module.yml` through the same manifest-driven configurator and shared
    engine, and auth's retired `allow_registration` and `social_providers` keys are refused by the
    manifest's `retired_options` block with their replacement named.
  - **Backups configuration is manifest-owned.** Its option defaults, CLI prompts, env-var-name
    patterns, and private-remote cross-option rules come from `module.yml` through the same
    manifest-driven configurator and shared engine, and its retired raw `remote_access_key_id` and
    `remote_secret_access_key` keys are refused by the manifest's `retired_options` block with
    their env-var replacements named.
  - **Storage configuration is manifest-owned.** Its option defaults, CLI prompts, env-var-name
    patterns, and cloud-backend credential rules come from `module.yml` through the same
    manifest-driven configurator and shared engine, and its retired raw `access_key_id` and
    `secret_access_key` keys are refused by the manifest's `retired_options` block with their
    env-var replacements named.
  - **Notifications and social configuration is manifest-owned.** Their option defaults, CLI
    prompts, validation, and tag/provider normalization come from `module.yml` through the same
    manifest-driven configurator and shared engine, and notifications' runtime email-backend
    selection lives in its module adapter. Manifests can now declare `not_empty`, per-item
    `choices`, `subset_of`, `excludes`, `intersects`, multi-entry conditions, and `slug`/`list`
    normalization.
  - **The `teams` placeholder is removed.** `quickscale_modules/teams/` no longer exists,
    `teams` is refused as an unknown module in `quickscale plan` and `quickscale.yml`, and the
    planning note lives at `docs/planning/teams.md`.
  - **Module wiring refuses conflicting settings.** `apply` fails and names both modules and the
    setting when two modules contribute one wiring key with different values, while
    `REST_FRAMEWORK` contributions merge key by key so one module's throttle rates cannot replace
    another's. Auth no longer contributes `ACCOUNT_ADAPTER`; the orgs adapter, which extends
    auth's, is its single writer.
  - **Shipped-module lists derive from module manifests.** Core's catalog descriptions, the Bandit
    scan roots, the theme lint's module set, and the PostgreSQL isolation profile and runner read
    the shipped set from `quickscale_modules/*/module.yml`, so a module that ships an RLS boundary
    suite joins the isolation gate automatically, and an incomplete module directory fails those
    gates closed instead of dropping out of them.
  - **Module READMEs share one outline.** Every module README uses the same seven sections —
    Overview, Configuration, Public surface, URLs, Management commands, Operations, Extending —
    and names every manifest option key under Configuration and every shipped management command
    under Management commands.
  - **Blog automation API is a DRF surface.** The blog publish and media endpoints are DRF views
    with session authentication, answer the shared `{"error": {"code", "message", "fields"}}`
    shape, and throttle by client IP under the `quickscale_blog_api` scope at the module's
    `api_rate_limit` option; `BLOG_API_TOKENS` bearer access and the blog throttle counter table
    are removed.
  - **Module templates and assets share one layout.** Every module page extends one flat
    `templates/quickscale_<module>/base.html` that extends the project shell and owns that module's
    `<module>_content` block; module emails live under `email/`, static files under
    `static/quickscale_<module>/{css,js,img}/`, and the analytics template-tag library is
    `quickscale_analytics`. An existing project that overrode a module base or page template must
    move its override to the new path or it silently stops applying.
  - **Listings publish API is a DRF surface.** `POST listings/api/publish/` is a DRF view with
    session authentication (CSRF enforced) behind the same staff gate, and it answers the shared
    `{"error": {"code", "message", "fields"}}` shape with stable codes for validation, parse,
    conflict, and server failures; the module's last plain-`JsonResponse` endpoint is gone.
  - **Organization API is a DRF surface.** The org list/create, detail, members, invitations, and
    settings endpoints are DRF views with session authentication (CSRF enforced) behind the same
    org-role gates, and every error answers the shared
    `{"error": {"code", "message", "fields"}}` shape.
  - **Billing API errors answer the shared shape.** The billing config, plans, balance,
    transactions, checkout, subscription, and portal endpoints answer
    `{"error": {"code", "message", "fields"}}`, and a disabled runtime answers `404` as the Stripe
    webhook already did. The theme's public social pages surface that shape's message for a
    non-managed error body.
  - **Forms API errors answer the shared shape.** The public form submit endpoint answers
    `{"error": {"code": "validation_error", "message": "Invalid input.", "fields": {...}}}` for an
    invalid submission, and the theme's form client reads that shape: field errors appear under
    their fields, non-field or unrendered-field errors as a global message, and other failures
    show the shape's message.
  - **Auth's mount is manifest-owned and its routes are snake_case.** The auth module declares
    `accounts/` in its manifest's `url_includes` entry instead of its adapter, and its profile
    routes are named `profile_edit` and `account_delete`; every public URL is unchanged.
  - **Organizations serve every URL under `/orgs/`.** The orgs module declares its `orgs/` mount
    in its manifest and namespaces its snake_case routes as `quickscale_orgs`, its JSON API
    answers at `/orgs/api/...` (was `/api/orgs/...`), and the root dashboard route is gone so the
    site root belongs to the project.

- v0.88.0 — released 2026-09-15 — [Request Identity and Manifest-Driven Modules](docs/releases/release-v0.88.0.md). Consolidates canonical request identity and CSRF transport in generated projects, manifest-owned Django app declarations with relocated module adapters, idempotent metadata-derived FORCE RLS enrollment, inode-bound backup locking, one authoritative CI PostgreSQL provisioning contract, and three-state module presence in `quickscale status`. Raises the Python floor to 3.14 for the repository and generated projects.
  - **One canonical request identity.** Generated projects resolve the client identity once behind validated proxy configuration; DRF throttling, the custom blog limiter, form persistence, and CSRF all read that seam instead of deriving it independently.
  - **`ClientIdentityMiddleware` in generated projects.** A first-position middleware aligns ordinary DRF request identity with the canonical resolver, so a short forwarded chain cannot be trusted by one consumer and rejected by another. Proxy configuration is validated before mutation and the production proxy count is derived rather than guessed.
  - **Modules declare their Django wiring in their manifest.** App declarations moved into `module.yml` behind a dedicated gate, adapters live inside their own module packages, and the imperative wiring they replaced is deleted.
  - **Embedded module manifests must match the running core exactly.** A version mismatch is a hard, named error instead of a downstream failure; modules stay versioned in lockstep with the release.
  - **Idempotent, metadata-derived RLS enrollment.** Applying FORCE RLS twice is safe, table names come from each model's own metadata, and the operator-read/tenant-write policy split is preserved; a live-PostgreSQL regression applies the forward template twice.
  - **Backup and recovery locking is correct under contention.** The advisory lock is inode-bound with atomic stale reclamation and acquisition-bound release identity.
  - **One authoritative CI database environment.** PostgreSQL provisioning is a single contract with five profiles consumed by every station, replacing four divergent hand-rolled variants.
  - **Three-state module presence in `quickscale status`.** A module reports as present, absent, or placeholder rather than collapsing into a true/false guess.
  - **Frontend CSRF transport hardened.** Token handling in the React starter handles malformed and duplicate cookies, matching Django's last-value precedence.
  - **Commit-testimony gate.** Any non-merge commit touching a workflow, the gate registry, or a provisioning station must carry a `vNN` roadmap reference, bare (`v88`) or dotted (`v0.88.0`); a ticket id or changelog entry does not satisfy it. A `commit-msg` hook rejects it while rewording is still free, and CI re-checks the range.
  - **Security and interpreter gates.** A consolidated security static-analysis gate with recorded, expiring suppressions, plus a guard that keeps repository tooling on the project interpreter.
  - **Local CI stage selection and failure replay.** `ONLY=`/`FROM=`/`SKIP_INSTALL=` run part of the pipeline and replay just what failed; partial runs announce themselves and never count as a full pass.
  - **Installed-wheel proof.** A source-free, all-module `plan → apply → up` lifecycle runs from an external working directory against current artifacts.
  - **E2E lifecycle.** Content-addressed backend image identity with measured cold-versus-warm reuse, run-scoped resource labels, retention-aware teardown, and exact-label cleanup that leaves no stray containers, volumes, or networks.
  - **Quality and gate hygiene.** A merge-base monotonicity gate for the quality baseline, parallelised gate suites, and a closed-universe check that makes an unregistered CI job a red build.
  - **Python floor raised to 3.14** (`>=3.14,<3.15`) for the repository and generated projects. Django stays at `>=6.0.7,<6.1.0`, PostgreSQL at 18. Pre-1.0 upgrades remain a clean break: regenerate and apply against a fresh database.
  - **Bulk split-ref embedding.** `quickscale apply --split-refs-from-branches` embeds every selected module from its own `splits/<module>-module` branch, replacing one repeated `--split-ref` argument per module.
  - **Release closeout lanes.** An unscoped `make ci-e2e` runs the dedicated BYPASSRLS lane exactly once; `make release-gate` then runs the migration-topology guard, generated-project migration proof, integration, typecheck, E2E, and quality lanes, stopping at the first failure.
  - **Publish status offers the expected SHA.** `make publish-module-status` observes each remote split branch and prints a ready-to-paste publish command carrying that 40-hex SHA for every outdated module with an existing observed tip.
  - **One-command split publish.** `make publish-modules` publishes every outdated module serially, each against its own freshly observed remote SHA, from the tree the release gate checked; the disabled bare-`--force` batch stays disabled.
  - **Railway deploy provisions the runtime database role.** `quickscale deploy railway` sets `RUNTIME_DB_ROLE`, `RUNTIME_DB_PASSWORD`, and a reference-variable `RUNTIME_DATABASE_URL`; the generated `start.sh` creates the restricted `NOSUPERUSER/NOBYPASSRLS` role before migrating. Re-deploys reuse the password, and a hand-set `RUNTIME_DATABASE_URL` is left alone.
  - **`quickscale manage` keeps the runtime role.** Only `migrate`, `createcachetable`, and `migrate_billing_to_orgs` switch to the superuser connection, so `quickscale manage createsuperuser` no longer trips the RLS boot guard.
  - **Deployment fixes.** The generated Dockerfile creates the `django` user's home directory, silencing gunicorn's control-socket permission error, and `quickscale deploy railway` lists services non-interactively instead of hanging on Railway CLI's link prompt.
  - Release-tier validation is owed on the bumped bytes: the `0.88.0` tag, GitHub release, and PyPI distributions do not exist yet, the split branches are not republished, and the twelve `0.88.0` split tags are not sealed.

- v0.87.0 — released 2026-08-20 — [Hardening Release](docs/releases/release-v0.87.0.md). Consolidates a large hardening pass across tenant isolation, module configuration, the generator, split publication and lockstep, and disaster recovery.
  - **Tenant isolation unified.** Every tenant-scoped model inherits one shared isolation base instead of hand-copied boilerplate; a project-wide check requires each model to be explicitly tenant-scoped or excluded and is wired into generated projects' own CI.
  - **Fail-closed database access.** The app refuses to boot under a database role that bypasses row-level security (`BYPASSRLS` or `SUPERUSER`) unless explicitly overridden; production requires a restricted tenant-safe role, with the elevated role reserved for migrations.
  - **Database-level parent/child isolation.** Parent/child records (e.g. a CRM contact and its notes) are kept in the same organization via `NOT DEFERRABLE` composite foreign-key constraints, replacing the fragile trigger-based check; a conformance gate verifies every composite FK.
  - **Fixed a row-level-security bug affecting pooled database connections**, and removed redundant per-statement tenant-context setup within a transaction.
  - **Public `org_scope` API.** Internal org-context primitives are retired in favor of one public `org_scope()` seam used everywhere, with a canonical `PublicSystemOrgReadMixin` for anonymous public reads and a lint gate enforcing the boundary.
  - **Operator tooling.** Admins can "view as" a specific organization from the admin panel (visible banner, one-click exit); a single audited `operator_access()` path gates cross-tenant reads and sensitive maintenance commands, logging who ran what and why.
  - **`TenantModelAdmin` base.** An orgs-owned admin base resolves the active org and scopes every admin view through `org_scope()`, fail-closed; every module admin is ported onto it, removing hand-copied scoping and inline formsets.
  - **Fail-hard configuration sweep.** Missing or invalid module settings (page sizes, rate limits, feature flags, provider/enabled flags, proxy config, storage backend, orgs mode) now raise at boot or apply time instead of silently defaulting or coercing; validators are wired into the apply path and the dead coercions they masked are removed.
  - **`QUICKSCALE_MODE` fails hard at boot** instead of defaulting to `solo`, and legacy `quickscale.yml` keys are rejected with a named-replacement error instead of being silently translated.
  - **Public-content sanitization.** Markdown-rendered links on public blog/listing pages are run through an allowlist URI-scheme sanitizer (blocking `javascript:` and obfuscated schemes per the WHATWG URL spec); the analytics template-tag payload is escaped before `mark_safe`; and orgs debug-view `next` redirects are validated same-host/scheme.
  - **Non-string public form submissions** return validation errors instead of 500ing.
  - **Client-IP and cache infrastructure.** Generated projects gain a canonical `get_client_ip()` helper with trusted-proxy config (matching DRF's proxy-count semantics) and a shared `CACHES` backend (Redis when available, else `DatabaseCache` with a deploy-script `createcachetable` step); forms/blog throttles and IP logging point at the shared seam.
  - **Cross-org account-deletion safety.** User FKs on org content are `SET_NULL`/`PROTECT` (never `CASCADE`) so deleting a user no longer destroys content across organizations, enforced by a conformance gate.
  - **Last-owner invariant.** One canonical last-owner deletion-blocking check (with `select_for_update` concurrency protection and a `pre_delete` cascade backstop) replaces three divergent copies and is enforced at the account-deletion boundary.
  - **Secrets kept out of logs and argv.** The deploy script prints per-variable set/`MISSING` status instead of raw values; Railway/DR adapter secrets are piped via stdin instead of command-line arguments, with a hard-stop rather than an insecure fallback.
  - **Billing ownership and integrity.** Subscriptions are authoritatively owned by the organization; a partial unique constraint enforces credit-ledger idempotency at the database level; account-deletion cleanup distinguishes a benign "nothing to cancel" from an anomalous subscription missing its Stripe id; and billing's state-changing endpoints move onto the DRF baseline (automatic CSRF) with a decisions-doc rule naming the two sanctioned JSON-API bases.
  - **Backups and disaster recovery.** Admin backup create/prune/restore run off the synchronous request path via background subprocess with atomic claiming; the uploaded-restore copy is crash-safe; stranded `STATUS_RESTORING` artifacts are detected and recoverable; DR media-backend resolution fails hard on real misconfiguration instead of silently falling back to local storage; and a `csrf_exempt` CI gate requires every callsite to pair with verification.
  - **Core/module boundary.** A single `quickscale_core.runtime` facade is the only public core import surface (import-linter enforced); a Django-free persistence protocol lets backups/DR inject model access; managed adapters register explicitly instead of at import time; and a bidirectional import ban keeps core from importing modules.
  - **Resilient project generation.** `apply` checkpoints progress after each step and resumes on failure; destructive or remote actions require explicit confirmation; `apply --force` stages to a backup directory with full rollback; module `pyproject` splices route through a validated TOML writer; and generator internals are split into smaller focused modules.
  - **Declarative module configuration.** The `module.yml` derivation loader is proven by round-trip tests, listings is fully migrated off imperative wiring, and a guardrail blocks any module from reintroducing it; a manifest-sync gate fails on drift between each module's `module.yml` and its core snapshot.
  - **Contract-version tracking.** Generated projects record the contract version they were built against, a compatibility gate probes each module against its claimed minimum core version, and `quickscale status` flags modules ahead of the project's contract.
  - **Retired the `showcase_html` generator theme** in favor of React-only output; existing generated projects keep their user-owned files.
  - **Generator emission mapping** is exported as a single authoritative function shared by production and its beta-migration conformance gate.
  - **Frontend de-specialization.** Generator-owned frontend files — including the theme root — are byte-static verbatim copies (`.j2`/`{% raw %}` removed), and project identity is injected at runtime via `window.__QUICKSCALE__.projectName`; generated projects differ only in data, never in source.
  - **Fail-hard runtime seams.** Every load-bearing `window.__QUICKSCALE__` read is validated at boot (seam, non-empty project name, strict booleans); silent fallbacks and the default config are gone.
  - **Blocking frontend proof.** `lint-frontend` is a blocking job in CI and local `make ci` — with an absent-Node guard that never masks real failures — and `frontend-proof` runs before build/publish.
  - **Frontend install resilience.** Generated installs mirror the pip house pattern: bounded retries and raised pnpm fetch timeouts.
  - **Cross-module signal decoupling.** Orgs no longer reverse-imports CRM/auth: a `organization_created` signal drives CRM's default-stage seeding (self-sufficient under restricted roles), the auth adapter fails hard when the module is absent, and version-floor constraints on `required_modules` are enforced at apply time.
  - **PostgreSQL-only test infrastructure.** All modules test exclusively against PostgreSQL (SQLite removed everywhere) under a shared pre-provisioned restricted (`NOBYPASSRLS`) role; a dedicated integration gate proves tenant isolation under that role and is structured so it cannot pass by silently skipping.
  - **Parallel integration execution.** The per-module integration loop runs as a configurable parallel worker pool with isolated coverage/log state, joined failure propagation, deterministic replay, and signal-safe cleanup, matching sequential verdicts and coverage.
  - **Build/test artifacts are no longer accreted** (coverage/log files, blog test-upload media) and test `MEDIA_ROOT` points at a temp directory.
  - **Migration squash.** All nine modules now start from final-schema `0001_initial` migrations with required organization ownership and catalog/data parity against the previous schema.
  - **DR persistence port.** Backup persistence runs behind a fail-hard provider registry and a Django-free protocol that preserves the bidirectional core/module import boundary.
  - **Idempotent split publication.** Mutable split branches can be safely republished, immutable split tags form a separate sealing boundary, and the core-tag push remains the distinct PyPI trigger.
  - **Identity-derived split versions.** Module source resolves from immutable `splits/<module>-module/<version>` tags derived from the core version, failing hard when absent while retaining a maintainer-only `--split-ref` override.
  - **Split push workflow retired.** Publication no longer force-pushes split branches through GitHub Actions, and publish triggers now follow the split-tag namespace.
  - **Authoritative module inventory.** Release and embed paths reject modules outside the canonical inventory before mutation, including unlisted directories that previously qualified as split sources.
  - **Fail-closed split-tag sealing.** Sealing samples and rereads the branch tip, rejects conflicting tags, pushes one explicit refspec, and verifies the tag and branch afterward while documenting the unavoidable client-side race window.
  - **Seal tooling hardened.** Tag creation, peeling, equal-tree reuse, cleanup precedence, repository-version binding, and lightweight-tag idempotence are covered by fail-hard integrity checks.
  - **Publication sequence ratified.** The required order is version bump and commit, local core tag, idempotent split publication and testing, immutable split-tag sealing, clean all-module verification, then the human-gated core-tag push.
  - **All twelve split modules sealed.** Every module has an immutable `0.87.0` split tag matching its source and branch, and the core tag is published.
  - **Release rollback refs retained.** Local backup refs preserve the prior core tag and removed stale teams branch for the release rollback window.
  - **Installed apply ordering repaired.** `quickscale_core.runtime` loads its Django-dependent DR surface lazily so managed adapters can load before generated-project dependencies are installed.
  - **Managed adapter discovery repaired.** Embedded module adapters can be retried from their active `src` trees without leaking temporary `sys.path` changes or weakening fail-hard imports.
  - **Publication preflight.** Mutating publication commands require nonblank repo-local Git credentials and identity while keeping global configuration disabled, secrets out of URLs and argv, and selected tag or override details visible in embed output.
  - **Exact publication leases.** Split-branch updates require explicit ref-qualified expected SHAs and reject the unsafe unqualified absent-branch lease path.
  - **Publication safety.** Blank origins fail closed, PostgreSQL verification owns signal-safe lifecycle cleanup, and staged-index checks safely handle arbitrary filenames.
  - **Publication authorization binds and consumes.** Mutable branch publication carries per-branch remote expectations, sealing derives and verifies its own remote state, and the later core-tag push remains human-gated.
  - **Lockstep enforced.** The manifest lockstep checker rejects any Python binding that could rebind `__version__` and requires exact canonical three-component versions across manifests.
  - **Installed-context resolution.** Module discovery resolves source, then bundled snapshot, then fails hard so installed `plan` and `apply` work outside the monorepo, including zero-module projects.
  - **Installed-artifact smoke gate.** Wheels are built from isolated staged copies, installed into a throwaway external virtualenv, and probed with a sanitized environment.
  - **Installed-wheel lifecycle proof.** External-working-directory E2E covers `plan → apply → up`, all twelve modules, live HTTP, migrations, bounded subprocesses, exact service scoping, and fail-loud cleanup.
  - **Tracebacks survive installed `apply`.** `QUICKSCALE_DEBUG=1` prints the full wiring traceback while preserving the standard failure banner.
  - **Generated-project Poetry isolation.** Project lock, install, and run subprocesses scrub the ambient worktree virtualenv and use project-specific environments across apply, module installation, Railway checks, migration, and E2E paths.
  - **Generated-project Poetry installs serialized.** Isolated environments force `POETRY_INSTALLER_PARALLEL=false` to prevent high-concurrency installer hangs while preserving per-worker cache overrides.
  - **E2E lane parallelism.** Core and CLI lanes support isolated xdist workers with deterministic cleanup, a configurable worker count, and a memory guard that can force serial execution.
  - **Authoritative gate topology.** Local, hosted, publish, and E2E gate membership derives from `scripts/gate_registry.json`, with blocking parity and generation checks preventing drift.
  - **Installed-wheel E2E triggers registered.** The generated hosted workflow includes the complete installed-wheel lifecycle trigger set exactly once and in order.
  - **Quality-baseline monotonicity gate.** Positive ceiling deltas and new exemptions require a structured waiver, separating measurement from permission.
  - **File line-ceiling gate retired.** Line-count ceilings were removed because they could not distinguish required growth from decay, while complexity ceilings remain enforced.
  - **Green release gates.** `make check`, `make quality`, `make ci`, and `make ci-e2e` pass at one baseline, with publication retaining full gate coverage.
  - **Hosted E2E prompt parity.** Hosted apply now supplies both required confirmations so generated-project builds and full E2E can complete.
  - **E2E memory guard.** Low-memory conditions override explicit xdist counts and force serial execution unless `QS_E2E_NO_MEMORY_GUARD=1` is set.
  - **E2E harness.** Concurrent Core and CLI lanes use isolated ports and scopes, signal-safe cleanup, stuck-lane heartbeats, and provenance banners explaining serial execution.
  - **Parallel unit and static gates.** Unit tests use xdist with isolated coverage and a serial override, while local-CI static gates run concurrently and replay output in declaration order.
  - **Installed-wheel lifecycle acceptance.** The ordered serial-then-concurrent E2E acceptance campaign passed at one merged tip (serial 31m42s, concurrent 21m46s, 1.46x at three xdist workers per lane, no memory-guard bypass), with every Docker scope verified empty and the all-module installed-wheel lifecycle green in both runs.
  - **Apply-path complexity repair.** The late destructive/remote confirmation block is extracted from `_execute_apply_steps_locked` into a dedicated helper with byte-identical prompts, banners, defaults, and cancellation behavior, returning the function under its fixed ceiling without touching step order or recovery.
  - **Dependency-sync complexity repair.** `module_dependency_sync` path-dependency patching and project sync are decomposed into nine small helpers with no behavior change, restoring both functions below their baseline tuples; `make quality` reports `total_regressions: 0` and the repository holds no accepted quality exception.
  - **Quality baseline cleared.** Complexity-preserving extractions brought all measured functions within their fixed ceilings without rebaselining or adding waivers.
  - **Dependency upgrade.** Python floor 3.13 → 3.14; Django ≥6.0.7 with every module pin locked in lockstep — intentional drift retired.

- v0.86.0 — Organizations Module (multi-tenancy with Solo/SaaS runtime modes, org-scoped RBAC and invitation flow, billing bridge with authoritative org ownership fields and `Plan.features` feature gates, `migrate_billing_to_orgs` and `promote_to_saas` management commands, React org management pages and org switcher, and billing wiring regression fix with planner/apply guard test)
- v0.85.0 — Billing Module (Stripe-backed one-time credit purchases and recurring subscriptions, credits-first Django-owned ledger, planner/apply readiness with auth-module dependency enforcement, module-owned `/billing/pricing/` and `/billing/dashboard/` pages, and starter-theme billing links)
- v0.84.0 — Backups Hardening Release (admin backup artifact download/create/integrity actions, upload-driven restore safety and compatibility checks, full-snapshot backup-contract hardening, and repo-owned runtime/tooling support alignment for the refreshed Python/frontend baseline)
- v0.83.0 — Hardening Release (repo-wide hardening across strict desired-config validation, notifications live-config placeholder rejection, generated production `SECRET_KEY` fail-hard behavior, CRM staff-only parity, forms CSV and backup artifact safety, blog upload/thumbnail/rate-limit hardening)
- v0.82.0 — Disaster Recovery & Environment Promotion Workflows (public `quickscale dr capture/plan/execute/report` workflows for local and Railway routes with `snapshot_id`-based stored snapshots, resumable capture and execute, rollback pins for production routes, conservative env-var sync, and source-side media sync)
- v0.81.0 — Beta-Site Migration Maintainer Tooling (maintainer-only Make/Python workflows for beta-site catch-up: fresh-first and in-place paths with checkpoint-first semantics)
- v0.80.0 — Analytics Module (PostHog-only website analytics with flat `QUICKSCALE_ANALYTICS_*` settings, service-style capture helpers, apply-time env-example sync, guarded forms integration, QuickScale-owned social click tracking)
- v0.79.0 — Social & Link Tree Module (curated social links and embeds, backend-owned YouTube/TikTok preview metadata, managed `/_quickscale/social/` integration endpoints, Django-owned public React pages)
- v0.78.0 — Notifications Module (transactional email foundation, Anymail-backed Resend delivery, recipient-granular tracking, signed delivery webhooks)
- v0.77.0 — internal main-branch baseline — Backups Module (private database backups, optional private remote offload, guarded CLI restore, scheduler-ready command hooks)
- v0.76.0 — Storage Module (cloud file hosting, media storage adapters, CDN-ready media infrastructure)
- v0.75.0 — Forms Module (generic customizable form builder with admin, DRF API, spam protection, GDPR anonymization, and React mount point)
- v0.74.0 — React Default Theme (showcase_react theme with Vite, TypeScript, TanStack Query, and Zustand)
- v0.73.0 — CRM Module (API-first Django CRM with 7 core models and CLI integration)
- v0.72.0 — Plan/Apply Cleanup (removed legacy init/embed commands, full transition to plan/apply)
- v0.71.0 — Module manifests & config mutability (Plan/Apply system complete)
- v0.70.0 — Existing project support (status, plan --add, plan --reconfigure)
- v0.69.0 — State management and incremental applies
- v0.68.0 — Plan/Apply System core commands (Terraform-style declarative workflow)
- v0.67.0 — Listings module with AbstractListing base model for verticals
- v0.66.0 — Blog module with Markdown, featured images, and RSS feeds
- v0.65.0 — Enhanced auth module and development tooling
- v0.64.0 — Theme rename to showcase_* (breaking change)
- v0.63.0 — Authentication Module with django-allauth and interactive embed
- v0.62.0 — Split Branch Infrastructure (module management CLI commands, GitHub Actions automation)
- v0.61.0 — Theme System Foundation (--theme CLI flag, theme abstraction layer, HTML theme)
- v0.60.0 — Railway Deployment Support (automated deployment via quickscale deploy railway)
- v0.59.0 — CLI Development Commands (Docker/Django operation wrappers)
- v0.58.0 — Comprehensive E2E testing infrastructure with Playwright and PostgreSQL
- v0.57.0 — Production-ready generator baseline
- v0.56.0 — Quality, Testing & CI/CD
- v0.55.0 — CLI implementation
- v0.54.0 — Project Generator
- v0.53.3 — Project Metadata & DevOps Templates
- v0.53.2 — Templates and Static Files
- v0.53.1 — Core Django Project Templates
- v0.52.0 — Project Foundation
- v0.51.0 — Documentation foundation
- v0.41.0 and earlier — legacy codebase (see Github repository for history)
