# QuickScale — Deep Technical Audit (defect sweep)

Audited: 7d9782a99a6606853c2299170489fe291acc6a10 (v89) · 2026-10-13 · working tree dirty (uncommitted `docs/others/arch-audit.md`; read only for its hand-off sections) · repository public (github.com/Experto-AI/quickscale; no `SECURITY.md`) · prompt: deep-technical-audit v7

> **Mode:** re-run. Delta `2fd8637f..7d9782a9`: 104 non-merge commits, plus merge commits that
> resolved conflicts in production files. The format is regenerated to v7. Every prior ID has a
> line in §15.

---

## 1. Orientation summary

**System.** Unchanged since the prior pass:
- A Python 3.14 / Django 6.0 **project generator** (`quickscale_core`) and its **CLI**
  (`quickscale_cli`).
- **12 embeddable Django modules**, embedded into generated projects by git subtree.
- **devtools** (beta migration) and the `scripts/` CI gates.

**Deployment realities** (the same three):
- **R1:** the generator and CLI on developer machines.
- **R2:** the generated Django SaaS, internet-facing on Railway. It runs gunicorn on PostgreSQL
  with FORCE RLS under a restricted runtime role, in solo or saas organization mode. Its defaults
  and its generated CI are production reality.
- **R3:** the tag-triggered release pipeline to PyPI over OIDC.

**Entry points, actors, crown jewels, configuration axes, and data sensitivity** are as recorded
in the prior pass. Changes since then:
- The managed URLconf now comes from a runtime facade (SA258c/SA260/SA261).
- One storage-owned, staff-guarded Markdownx mount replaces the blog and listings mounts.
- Billing gained the `quickscale_billing_reconcile_checkouts` operator command.
- The Stripe customer identity moved from orgs into billing (SA265a).
- Session authentication is the only DRF default authentication class (SA262; previously Session
  and Basic).

**Tooling baseline.**
- **Fail the build:** ruff, mypy, and pytest (including PostgreSQL RLS integration), plus Bandit,
  Trivy, gitleaks, the zizmor workflow gate (now also over the rendered generated CI template),
  and the convention, parity, CSRF, and contract-vintage gates.
- **Gate wiring:** Makefile targets and the publish workflow's gate steps are now generated from
  `scripts/gate_registry.json` (SA259).
- **Not in hosted CI:** the new `check-generated-project-automation` gate runs locally only
  (watchlist).

**Oracle list** (unchanged, from `decisions.md`):
1. Fail-hard: no silent fallback.
2. The RLS boot guard.
3. Rule 9: JSON endpoints are DRF views on the core bases.
4. Rule 26: webhooks verify before parsing, a replay is a no-op, and no body is built from
   `str(exc)`.
5. Rule 19: tenant data is authorized by org role.
6. Rules 20/21: email goes through `send_notification`, and effects run on commit.
7. Rule 35: secrets come from settings, with startup checks.
8. `WebhookEvent` is the idempotency gate.
9. Security gates never skip silently.
10. Workflows are SHA-pinned under top-level `permissions`.

**Measurements.** In re-run mode the delta replaces the churn ranking.
- **Delta size:** about 91 core/CLI files (+9.7k/−1.2k, including the 4.7k-line `pnpm-lock.yaml`
  and about 2.5k lines of theme tests) and 172 module source files (+4.4k/−3.0k).
- **Fix commits:** 17 (defect-gravity grep).
- **Churn filter:** commits touching more than 30 files were dropped. Most module changes landed
  in large sweep commits, so file-level churn is unreliable for this window.

**Delta classification.**
- **Review-tracked:** SA251–SA268 and SA191, each with a roadmap/changelog trail.
- **Housekeeping, no production hunks:** `48ad0796`, `e0557de9`, `a185f998`, `f107118e`,
  `3b91faf7`, `71a0b25e`, `33f49b67`, `f21a8178`.
- **Unreviewed-behavioral candidates, read in full:**
  - `6b56515b` ("gate fixes"): moved the purge helpers and added Bandit B703/B308 suppressions for
    `seam_tags.py` lines 37, 45, and 55.
  - `00fa86f2` ("review fixes"): changed the `drf.py` paginator and the social public-payload
    marker.
  - Merge `192195e2`: conflict-resolved production hunks in the blog, listings, and storage
    `adapter.py` files and storage's `module.yml`. Storage's post-hook no longer calls
    `validate_module_options`, but the check now runs at the manifest boundary
    (`manifest/entry_point.py:104`) before any hook. Killed.

### Coverage and residual-risk statement

**Method.** Seven parallel enumeration units, then main-agent judgment and spot re-verification
of every surviving card:
- billing;
- orgs + auth;
- core runtime + generated templates;
- the other nine modules;
- CLI/manifest/devtools/DR media;
- gates + pipeline;
- test-diff + variant analysis.

**Read in full:**
- **billing:** `_webhooks_checkout.py`, `_webhooks.py`, `_removal.py`, `_checkout.py`,
  `_customers.py`, `views.py`, `exceptions.py`, the reconcile command, and the models and
  `0001_initial` diffs.
- **orgs:** `throttles.py`, `views.py`, `forms.py`, `_view_context.py`, `middleware.py`,
  `_tenancy_references.py`, `permissions.py`, and the purge command's guards.
- **auth:** the anonymize boundary and the account-deletion guard.
- **core runtime:** `seam.py`, `seam_tags.py`, `urls.py`, `drf.py`, `_error_shape.py`, and the
  `settings.py`/`conventions.py` diffs.
- **Generated templates:** every changed template.
- **notifications:** `_webhooks.py` and the verify/ingest path.
- **Other modules:** the forms submit and email paths, the CRM viewsets, the blog/listings APIs,
  the storage adapter and Markdownx URLs, and the backups diff.
- **CLI:** deploy service config and the dependency writers.
- **Manifest and DR:** the manifest loader, resolver, entry point, and option validation;
  `dr_engine/_media.py`.
- **Pipeline:** all four workflows, `gates.mk`, and the security-gate scripts.

**Sampled:**
- billing's `_subscription_checkout*.py` and `_stripe_client.py`;
- the orgs/auth anonymization, `_purge_support`, and `_purge_plan`;
- analytics/social/crm serializers and checks;
- `check_quality.sh` and the publish scripts;
- about 35 files in the variant sweep.

**Skipped:**
- billing `_webhooks_invoice.py` and `_subscription_events.py` (not in the delta);
- the React theme test files;
- devtools internals beyond the diff;
- module-convention detector internals, covered instead by a differential replay (below).

**Empirical checks (§1e):**
1. **Differential replay of the convention-gate tests:** the `2fd8637f` test suites run against
   the HEAD `scripts/` in a scratch copy. 230 passed. All 7 failures are HEAD being stricter; none
   is a missed violation. The SA267/SA268 "behavior parity" refactors lost no rule.
2. **`check_gate_parity.py` and `sync_ci_gate_jobs.py --check`:** both exit 0. The `ci.yml` and
   `publish.yml` gate command sets are identical at both SHAs.
3. **Seam escaping probe:** Django `reverse()` percent-encodes `</script>`, quotes, backslash, and
   U+2028. The only request-derived seam value, `currentOrgSlug`, passes `escapejs`. Seam XSS
   killed.

**Category activation:**
- **Active:** I, II, III, IV, V (sampled), VI, VII, VIII, IX; X: generator, multi-tenant,
  service/webhooks, frontend, CLI, library, IaC.
- **Inert:** X mobile, firmware, GraphQL/RPC, ML/LLM (no model runtime), data pipeline.
- **Produced:** I, II, III, IV, VI, VII, VIII.

**Sibling sweep:** the 10 variant patterns of §3.5 (below) were searched across core, the CLI, all
12 modules, and the generator templates.

**Residual risk.**
- No PostgreSQL, Stripe, or Resend instance was used this pass. Lock, RLS, and Stripe Search
  consistency semantics were reasoned from code and vendor documentation.
- Out-of-repo controls stay invisible: the Railway edge, GitHub org defaults, Stripe and PostHog
  project settings.
- The skipped billing invoice and subscription-event handlers were last read in full on
  2026-10-08.

Silence on skipped areas licenses no conclusion.

---

## 2. Machine-readable finding index

```yaml
schema: tech-audit/v6
audited: 7d9782a99a6606853c2299170489fe291acc6a10
items:
  - {id: dr-private-remote-restore-whole-object-in-memory, status: open, severity: S3, category: IV,
     title: "Private-remote restore reads the whole dump into memory", effort: Small,
     confidence: High, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/dr_engine/_remote.py], depends_on: [],
     first_seen: 2026-10-13, last_verified: 2026-10-13}
  - {id: e2e-release-tag-trigger-never-matches, status: open, severity: S3, category: VII,
     title: "Hosted E2E never runs on a release tag", effort: Trivial, confidence: High,
     reality: release-pipeline, anchors: [.github/workflows/e2e.yml], depends_on: [],
     first_seen: 2026-10-13, last_verified: 2026-10-13}
  - {id: crm-theme-stats-always-zero, status: open, severity: S4, category: IX, effort: Trivial,
     confidence: High, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/src/pages/CrmPage.tsx],
     first_seen: 2026-10-13, last_verified: 2026-10-13}
  - {id: notifications-webhook-status-regresses-out-of-order, status: open, severity: S4,
     category: II, effort: Small, confidence: Medium, reality: generated-app,
     anchors: [quickscale_modules/notifications/src/quickscale_modules_notifications/_webhooks.py],
     first_seen: 2026-10-13, last_verified: 2026-10-13}
  - {id: notifications-webhook-secret-format-unchecked-at-startup, status: open, severity: S4,
     category: VI, effort: Trivial, confidence: High, reality: generated-app,
     anchors: [quickscale_modules/notifications/src/quickscale_modules_notifications/checks.py],
     first_seen: 2026-10-13, last_verified: 2026-10-13}
  - {id: orgs-invite-throttle-partial-charge, status: open, severity: S4, category: I,
     effort: Small, confidence: Medium, reality: generated-app,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/views.py],
     first_seen: 2026-10-13, last_verified: 2026-10-13}
  - {id: markdownx-upload-client-extension-and-content-type, status: open, severity: S4,
     category: III, effort: Small, confidence: Medium, reality: generated-app,
     anchors: [quickscale_modules/storage/src/quickscale_modules_storage/markdownx_urls.py],
     first_seen: 2026-10-13, last_verified: 2026-10-13}
  - {id: dr-media-part-file-leak-on-publish-failure, status: open, severity: S4, category: IV,
     effort: Trivial, confidence: High, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/dr_engine/_media.py],
     first_seen: 2026-10-13, last_verified: 2026-10-13}
  - {id: pyproject-write-not-atomic, status: open, severity: S4, category: IV, effort: Trivial,
     confidence: Medium, reality: cli,
     anchors: [quickscale_cli/src/quickscale_cli/utils/_dependency_write.py],
     first_seen: 2026-10-13, last_verified: 2026-10-13}
  - {id: ci-poetry-retry-curl-pipe-python, status: open, severity: S4, category: VII,
     effort: Trivial, confidence: High, reality: release-pipeline,
     anchors: [.github/workflows/ci.yml, .github/workflows/nightly-bypassrls.yml],
     first_seen: 2026-10-13, last_verified: 2026-10-13}
  - {id: dr-restore-vintage-exact-match, status: watchlist, category: I, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/dr_engine/recovery.py],
     first_seen: 2026-09-24, last_verified: 2026-10-13}
  - {id: orgs-provider-id-check-blocks-migrate, status: watchlist, category: VI, reality: generated-app,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/checks.py],
     first_seen: 2026-09-24, last_verified: 2026-10-13}
  - {id: crm-stage-seed-lost-on-commit-failure, status: watchlist, category: II, reality: generated-app,
     anchors: [quickscale_modules/crm/src/quickscale_modules_crm/receivers.py],
     first_seen: 2026-10-03, last_verified: 2026-10-13}
  - {id: backups-upload-restore-by-model-permission, status: watchlist, category: III,
     reality: generated-app,
     anchors: [quickscale_modules/backups/src/quickscale_modules_backups/_admin_restore.py],
     first_seen: 2026-10-08, last_verified: 2026-10-13}
  - {id: single-sync-worker-vendor-calls, status: watchlist, category: IV, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/generator/templates/start.sh.j2],
     first_seen: 2026-10-08, last_verified: 2026-10-13}
  - {id: allow-bypassrls-serving-undetected, status: watchlist, category: VI, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/runtime/settings.py],
     first_seen: 2026-10-08, last_verified: 2026-10-13}
  - {id: migrate-runs-per-replica, status: watchlist, category: II, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/generator/templates/start.sh.j2],
     first_seen: 2026-10-08, last_verified: 2026-10-13}
  - {id: development-workflow-intermittent-root-500, status: watchlist, category: VI,
     reality: generated-app, anchors: [quickscale_cli/tests/test_e2e_development_workflow.py],
     first_seen: 2026-10-11, last_verified: 2026-10-13}
  - {id: core-e2e-poetry-cache-install-candidates, status: watchlist, category: VI, reality: tooling,
     anchors: [quickscale_core/tests/conftest.py], first_seen: 2026-10-12, last_verified: 2026-10-13}
  - {id: orgs-role-mixin-checks-request-org, status: watchlist, category: III, reality: generated-app,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/permissions.py],
     first_seen: 2026-10-13, last_verified: 2026-10-13}
  - {id: social-config-error-served-200, status: watchlist, category: VI, reality: generated-app,
     anchors: [quickscale_modules/social/src/quickscale_modules_social/services.py],
     first_seen: 2026-10-13, last_verified: 2026-10-13}
  - {id: deploy-existing-settings-module-never-corrected, status: watchlist, category: VI,
     reality: cli, anchors: [quickscale_cli/src/quickscale_cli/commands/_deploy_service_config.py],
     first_seen: 2026-10-13, last_verified: 2026-10-13}
  - {id: account-deletion-hook-exception-text, status: watchlist, category: VI, reality: generated-app,
     anchors: [quickscale_modules/auth/src/quickscale_modules_auth/views.py],
     first_seen: 2026-10-13, last_verified: 2026-10-13}
  - {id: security-suppressions-uniform-expiry, status: watchlist, category: VII, reality: tooling,
     anchors: [scripts/security_suppressions.json], first_seen: 2026-10-13, last_verified: 2026-10-13}
  - {id: generated-project-automation-local-only, status: watchlist, category: VIII, reality: tooling,
     anchors: [scripts/check_generated_project_automation.py],
     first_seen: 2026-10-13, last_verified: 2026-10-13}
  - {id: initial-migration-edited-in-place, status: watchlist, category: IX, reality: generated-app,
     anchors: [quickscale_modules/billing/src/quickscale_modules_billing/migrations/0001_initial.py,
               quickscale_modules/orgs/src/quickscale_modules_orgs/migrations/0001_initial.py],
     first_seen: 2026-10-13, last_verified: 2026-10-13}
```

---

## 3. Summary table

**Counts:**
- **Open:** 10 in total: S1 — 0 · S2 — 0 · S3 — 2 · S4 — 8.
- **Watchlist:** 16.
- **This pass:** prior open `forms-notification-status-misreported` resolved; 11 findings new, 0
  carried, 0 regressed.

| ID | Sev | Cat | Title | Effort | Conf | Since |
|---|---|---|---|---|---|---|
| `dr-private-remote-restore-whole-object-in-memory` | S3 | IV | Private-remote restore reads the whole dump into memory | Small | High | new |
| `e2e-release-tag-trigger-never-matches` | S3 | VII | Hosted E2E never runs on a release tag | Trivial | High | new (**quick win**) |
| `crm-theme-stats-always-zero` | S4 | IX | Theme CRM stat cards always show 0 | Trivial | High | new |
| `notifications-webhook-status-regresses-out-of-order` | S4 | II | A late delivery event overwrites a terminal status | Small | Medium | new |
| `notifications-webhook-secret-format-unchecked-at-startup` | S4 | VI | A malformed `whsec_` secret passes the startup check | Trivial | High | new |
| `orgs-invite-throttle-partial-charge` | S4 | I | The per-sender bucket is charged when the per-org throttle refuses | Small | Medium | new |
| `markdownx-upload-client-extension-and-content-type` | S4 | III | The staff editor upload trusts the client's extension and type | Small | Medium | new |
| `dr-media-part-file-leak-on-publish-failure` | S4 | IV | A `.part` file is left behind when publish fails | Trivial | High | new |
| `pyproject-write-not-atomic` | S4 | IV | The CLI rewrites `pyproject.toml` in place | Trivial | Medium | new |
| `ci-poetry-retry-curl-pipe-python` | S4 | VII | The CI retry path pipes an unpinned installer into Python | Trivial | High | new |

---

## 4. Findings

### S3 findings (compact)

- **`dr-private-remote-restore-whole-object-in-memory`**
  - **Severity:** S3. Moderate impact (a restore OOM-killed during disaster recovery) × Rare
    (operator restore). The deviation is one step up because it fails at the worst moment.
  - **Location:** `dr_engine/_remote.py:90-93` (`_materialize_private_remote_key`).
  - **Defect:** the private-remote restore copies through `S3Storage.open()`, which spools the
    whole object in memory (`AWS_S3_MAX_MEMORY_SIZE` defaults to unbounded). This is the unfixed
    sibling of SA256's media fix, whose comment at `_media.py:148` names the same cause.
  - **Failure scenario:** a database dump larger than the container's memory limit is
    materialized from a private remote, the process is OOM-killed, and the restore fails.
  - **Fix (Small):** stream with the boto3 client's `download_fileobj` into the destination, the
    same way `_media.py` does.
  - **Confidence:** High. Introduced in `04d896d8`.

- **`e2e-release-tag-trigger-never-matches`** (quick win)
  - **Severity:** S3. Moderate impact (releases ship without the hosted E2E run the workflow
    promises) × Common (every release).
  - **Location:** `.github/workflows/e2e.yml:8-10`: `push: tags: ['v*']`.
  - **Defect:** release tags are `0.89.0`-style (`publish.yml` matches `"[0-9]*"`), so the release
    trigger never fires. The only mitigation is the manual `make ci-e2e` step in the publish
    procedure.
  - **Fix (Trivial):** add `"[0-9]*"`, matching `publish.yml`.
  - **Confidence:** High. Pre-existing.

### S4 findings (one line each)

- `crm-theme-stats-always-zero` · `themes/showcase_react/src/pages/CrmPage.tsx:28-31`
  - **Defect:** the stat cards read `.count`, then `.results.length`, but the CRM lists return a
    bare array (`runtime/drf.py:75-77`, `PlainListPagination`), so every card shows 0. Even
    `.length` would count only one page.
  - **Fix:** expose a count endpoint, or a header the theme reads.
- `notifications-webhook-status-regresses-out-of-order` · `notifications/_webhooks.py:257+ (`_apply_delivery_event`)`
  - **Defect:** `_apply_delivery_event` overwrites the status with no ordering check and no row
    lock, so a late `email.sent` regresses a `delivered` or `bounced` row.
  - **Fix:** rank the statuses and update only forward, under `select_for_update`.
- `notifications-webhook-secret-format-unchecked-at-startup` · `notifications/checks.py:62-71`
  - **Defect:** E003 refuses only an empty secret. A malformed `whsec_` value passes startup, and
    then every webhook is refused at runtime.
  - **Fix:** validate the prefix and the base64 decode in the check.
- `orgs-invite-throttle-partial-charge` · `orgs/views.py:184` (and `OrgApiInviteView.post`)
  - **Defect:** when the per-sender throttle passes and the per-org throttle refuses, the rolled-
    back invitation still costs the sender a token.
  - **Fix:** check both throttles before charging either.
- `markdownx-upload-client-extension-and-content-type` · `storage/markdownx_urls.py:19-24` (vendor
  `markdownx/forms.py:52-57`)
  - **Defect:** the staff-only editor upload keeps the client's extension and content type. GIF
    and SVG skip Pillow, so a staff account can store an HTML or SVG document in public media on
    the site's origin.
  - **Fix:** wrap the vendor form with the SA239 format-derived extension, and drop SVG from
    `MARKDOWNX_UPLOAD_CONTENT_TYPES`.
- `dr-media-part-file-leak-on-publish-failure` · `dr_engine/_media.py:153-179`
  - **Defect:** `chmod` and `replace` run outside the cleanup `try`, so a failure there (for
    example, the target is a directory) leaves a stray `.part` file.
  - **Fix:** move them inside the `try`.
- `pyproject-write-not-atomic` · `quickscale_cli/utils/_dependency_write.py:65-74`
  - **Defect:** `_write_validated_toml` truncates the file and writes in place, so an interrupted
    write leaves a corrupt `pyproject.toml`.
  - **Fix:** write to a sibling temp file, then `os.replace`.
- `ci-poetry-retry-curl-pipe-python` · `.github/workflows/ci.yml:667` (3 jobs) and `nightly-bypassrls.yml`
  - **Defect:** the Poetry install retry runs `curl install.python-poetry.org | python3`, unpinned,
    bypassing the SHA-pin contract.
  - **Fix:** retry `pipx`/`pip install poetry==2.4.1` instead.

---

## 5. Safeguard matrix

The prior matrix (`git show 2fd8637f:docs/others/tech-audit.md`, §5) was re-checked on the rows
the delta touched. Changed cells:

| Entry point | Changed cell(s) at HEAD |
|---|---|
| All module session APIs | AuthN: one core session-authentication class (Basic removed, SA262). Throttle: core's one scoped class; a scope with no rate raises `ImproperlyConfigured` (fail-closed). Error shape: core `_error_shape.py`, with no traceback. Declared errors echo `str(exc)` by design, and no secret-bearing message was found. |
| Markdownx editor upload | Now one storage mount, staff-only. Input validation: vendor `ImageForm` (`markdownx-upload-client-extension-and-content-type`). |
| `NotificationWebhookView` | Startup: secret non-empty only (`notifications-webhook-secret-format-unchecked-at-startup`). Ordering: `notifications-webhook-status-regresses-out-of-order`. |
| Billing reconcile command | `--dry-run` gates every write. Shares the per-org provider mutex with the webhooks. Conditional writes. Absent verdict waits out Stripe's Search indexing lag; two customer matches fail closed. |
| Orgs invite (HTML + JSON) | Both scopes charged inside the atomic block, rolled back on refusal (`orgs-invite-throttle-partial-charge`). Pending cap under the org row lock. |
| Orgs HTML management views | The object comes from the route slug. The role check uses `resolve_request_org` (watch: `orgs-role-mixin-checks-request-org`). |
| Social payload views (core-rendered) | DRF `AllowAny`, `SocialPayloadUnavailable` 503 with no exception text. The `status=error` branch is unreachable (watch: `social-config-error-served-200`). |
| CRM lists | Bare-list pagination, page size fixed by setting, no client override (`crm-theme-stats-always-zero` is on the theme side). |
| React seam (`quickscale_seam` tags) | Output from the catalog and `reverse()` only; `currentOrgSlug` through `escapejs`. Probe-verified. |
| DR restore (private remote) | `dr-private-remote-restore-whole-object-in-memory`. |
| Release E2E | `e2e-release-tag-trigger-never-matches`. |

All other rows are unchanged, and their cells were re-verified where the delta touched their
files.

---

## 6. Fix order and batching

All batches are independent of each other.
1. **Pipeline batch (Trivial):** `e2e-release-tag-trigger-never-matches` and
   `ci-poetry-retry-curl-pipe-python`. Land them before tagging 0.89.0 so the release gets its
   hosted E2E run.
2. **DR batch:** `dr-private-remote-restore-whole-object-in-memory` and
   `dr-media-part-file-leak-on-publish-failure`. They share the streaming idiom in `_media.py`.
3. **Billing (landed):** `stripe-customer-search-lag-resolves-absent` — reconciliation waits out
   Stripe's Search indexing lag, and the auth deletion test asserts the block again.
4. **Notifications:** the two webhook S4s (`_webhooks.py`, `checks.py`).
5. **Opportunistic:** `crm-theme-stats-always-zero` (theme + CRM, plus a contract-vintage
   adoption step), `orgs-invite-throttle-partial-charge`,
   `markdownx-upload-client-extension-and-content-type`, and `pyproject-write-not-atomic`.

---

## 7. Per-subsystem verdicts

| Subsystem | Verdict | What was read |
|---|---|---|
| billing | clean. The Search-lag absent verdict is closed; SA251 a/b/c fix-regression passed: double credit, webhook ordering, reconciler vs. webhook, and client amounts are all safe. | SA251/SA265 delta in full; subscription-checkout steps sampled. |
| orgs | `orgs-invite-throttle-partial-charge`; one watch item. SA254/SA257/SA265 fix-regression passed. | Delta in full except the purge-plan internals. |
| auth | clean (latent watch item `account-deletion-hook-exception-text`). | Anonymize boundary, deletion guard. |
| notifications | two S4s. Svix verification verified. | Webhook path in full. |
| forms | clean. The prior S4 is resolved and the view surfaces `notification_status: "skipped"`. | Views, `_email.py`. |
| crm | clean server side; theme S4. | Viewsets, pagination. |
| blog / listings | clean. Throttle scopes kept; the bucket identity moved to per-user, as declared. | API views. |
| storage | `markdownx-upload-client-extension-and-content-type` | Adapter, Markdownx URLs. |
| social | clean; one watch item. | Services, cache path. |
| analytics | clean. The coherence lead `module-enabled-switch` is killed: the app stays installed when off, and no shipped template loads the tag. | Adapter, services. |
| backups | clean. The `--scheduled` removal and the prune default are documented (release notes, `decisions.md:946`). | Diff in full. |
| core runtime / templates | clean. Seam, DRF admission, error shape, URL ownership, and the blank `__QS_ENV__` marker (now renders `''`) are all verified. | New runtime files in full. |
| CLI / manifest | `pyproject-write-not-atomic`; one watch item. The SA256 and SA260 closures hold. | Delta in full. |
| DR engine | two findings. | `_media.py` in full, `_remote.py` (variant sweep). |
| gates + pipeline | two S4/S3 findings; two watch items. No gate dropped, no detector weakened (differential replay). | Workflows, `gates.mk`, security gates in full. |
| devtools | clean (diff only). | Beta-migration delta. |

---

## 8. Clean sweeps and rejected candidates

- **Verified:**
  - Every closure claimed since `2fd8637f` holds in code: SA251 a/b/c, SA252, SA253, SA254,
    SA255, SA256, and SA262 social.
  - `forms-notification-status-misreported` is fixed (`a6b58799`, `forms/_email.py:44-53`).
- **Verified — no gate weakened:**
  - The `ci.yml` and `publish.yml` gate command sets are identical at both SHAs.
  - The SA267/SA268 detector refactors pass the old test suites, except where HEAD is stricter.
  - The security-gate split keeps fail-closed handling of a missing tool, empty input, a bad
    exit code, bad JSON, and expiry.
- **Verified — release scripts:** `--force-with-lease` with a freshly observed SHA and an
  ancestry check; tags created without force; no `pull_request_target`; no `github.event.*` in
  `run:`.
- **Verified — test diff:** no skip or xfail added; the moves are R100 renames. The one inversion
  was evidence for `stripe-customer-search-lag-resolves-absent` (restored by SA270). About 135
  `test_gate_parity` tests were removed together with the observer SA259 replaced, as the commit
  documents.
- **Verified — variant sweep, clean:**
  - relative provider URLs;
  - session-key identifiers;
  - unguarded views (every view and its guard enumerated);
  - `request.org` vs. the route slug (object resolution);
  - `email_verified` gating;
  - unthrottled email paths;
  - `all_objects` in request paths.
- **Killed:**
  - **Coherence leads:** `module-error-http-mapping` (`InsufficientCreditsError` is now 402
    `insufficient_credits`, SA264); `markdownx-shared-mount` (fixed by SA261);
    `option-schema-and-validation` (a blank marker renders `''`; the one template without
    `omit_if_blank` falls back to the validated host); billing `tenant-authorization` (every
    billing JSON view checks owner on the caller's org; the plan catalog is deliberately public).
  - **Storage post-hook validation** (merge `192195e2`): it now runs at the manifest boundary.
  - **Seam `mark_safe`** (Bandit suppressions in `6b56515b`): the escaping probe confirms the
    suppressions' rationale.
  - **Social `str(SocialConfigurationError)` in a public payload:** nothing raises that error
    (watch item).
  - **Forms recipients logged at WARNING:** not found in source.
  - **Declared module 5xx errors echoing `str(exc)`:** no secret-bearing message; by design under
    rule 9.
  - **DR media s3→local `..` keys:** still operator-only with a self-generated listing; the
    streaming rewrite did not change what killed it.
  - **`core-lockstep-spec-from-running-cli`:** Low; the lockstep release unit is an accepted
    architectural decision.
  - **`PENDING_INVITATION_LIMIT` read with no default:** a declared option, covered by the
    rule-3 check.
  - **CRM per-row counts:** bounded by the page size.
- **Lead, not carded:** the forms CSV export builds the whole file in memory. It is bounded by
  per-org submission volume; re-check if exports grow.

---

## 9. Structural smells

Carried:
- The typed Stripe provider-adapter seam is missing.
- Session-level advisory locks silently fail under transaction pooling.
- Outbound timeout policy is implicit.
- `start.sh` has a second database-connection constructor.
- `TenantMiddleware` declares path ownership twice.

Added:
- **Two S3 streaming idioms.** DR materializes objects through two different S3 paths: the
  storage API, which spools in memory, and the boto3 client, which streams. Only one is safe for
  large objects. That is the root of `dr-private-remote-restore-whole-object-in-memory`.
- **Clean-break schema edits with no data path.** `0001_initial` is edited in place across
  versions (SA265a moved `stripe_customer_id`). The architectural audit owns this as
  `clean-break-schema-no-data-path`.

---

## 10. Tooling gaps

- **A lint rule rejecting `S3Storage.open()` / `storage.open()` in `dr_engine`.** It would have
  prevented `dr-private-remote-restore-whole-object-in-memory`.
- **A workflow-trigger consistency check:** every workflow that claims to run on release tags uses
  `publish.yml`'s tag pattern. It would have prevented `e2e-release-tag-trigger-never-matches`.
- **A theme-to-API contract test:** a theme hook's expected response shape is checked against a
  rendered DRF response. It would have caught `crm-theme-stats-always-zero`.
- Carried: image-layer and broader IaC scanning.

---

## 11. Watchlist and accepted trade-offs

- **`orgs-role-mixin-checks-request-org` (new).**
  - **Why watch:** `OrgRoleMixin.dispatch` checks the role on `resolve_request_org()`, which
    prefers `request.org`, while `get_organization()` prefers the URL slug. In shipped code,
    `request.org` differs from the slug only under superuser VIEW-AS, and superusers pass the role
    check, so it is not live.
  - **Trigger:** a host middleware or a new code path sets `request.org` on `/orgs/<slug>/`
    management paths for a non-superuser. Then an admin of A could edit B.
  - **Cheap hardening:** check the role on `get_organization()`, as `OrgApiBaseView.initial`
    already does.
- **`social-config-error-served-200` (new).**
  - **Why watch:** since `73bcc7c7` the DRF payload views return 200 for a `status=error` payload
    whose `error` field holds `str(exc)`. `social_payload_status_code` is now unused. Nothing
    raises `SocialConfigurationError` today.
  - **Trigger:** any new raise of it in `_settings.py` or the services.
- **`deploy-existing-settings-module-never-corrected` (new).**
  - **Why watch:** deploy leaves an existing `DJANGO_SETTINGS_MODULE` alone, so a value wrongly
    derived before SA256 persists. This is blessed by SA256 and pinned by a test.
  - **Trigger:** a report of a pre-SA256 Railway service that fails to boot.
- **`account-deletion-hook-exception-text` (new).**
  - **Why watch:** undeclared `reconcile_account_deletion_provider_state` hooks flash `str(exc)`
    to the user. This is latent and needs a host-project hook.
  - **Trigger:** a documented host extension point for that hook.
- **`security-suppressions-uniform-expiry` (new).**
  - **Why watch:** all 10 suppressions expire on 2026-12-31. The gates then fail closed by
    design, blocking CI and publish.
  - **Trigger:** 2026-12-01 with no review scheduled.
- **`generated-project-automation-local-only` (new).**
  - **Why watch:** the SA253 gate runs only locally. Its docstring blesses this (no hosted
    PostgreSQL).
  - **Trigger:** a generated-artifact regression that reaches a release.
- **`initial-migration-edited-in-place` (new).**
  - **Why watch:** SA265a dropped `orgs.stripe_customer_id` and added `BillingCustomer` by editing
    both `0001_initial` migrations, with no data copy. `decisions.md` §Clean-Break Migration
    History allows this pre-1.0 for fresh databases only.
  - **Trigger:** any supported upgrade path from a live 0.88.0 install. Its first customer lookup
    would raise `ProgrammingError`, and the existing customer IDs would be orphaned.
- **Carried, triggers evaluated — not fired:**
  - `dr-restore-vintage-exact-match`: `recovery.py` is unchanged.
  - `orgs-provider-id-check-blocks-migrate`: still listed at `orgs/module.yml:52`.
  - `crm-stage-seed-lost-on-commit-failure`: `receivers.py` docstring-only change.
  - `backups-upload-restore-by-model-permission`: `_admin_restore.py` import-only change.
  - `single-sync-worker-vendor-calls`: `start.sh.j2` unchanged.
  - `allow-bypassrls-serving-undetected`: the guard text is unchanged; no tooling sets it outside
    dev.
  - `migrate-runs-per-replica`: `start.sh.j2` unchanged.
  - `development-workflow-intermittent-root-500`: no recurrence recorded.
  - `core-e2e-poetry-cache-install-candidates`: no recurrence recorded.
  - The carried one-liners from the prior pass: not fired.

---

## 12. Coherence hand-offs

- The `project_contract.yml:188` step text still describes the pre-SA258 generation-time seam
  mechanism. It is stale prose, not a defect.
- The blog and listings API throttle identity moved from per-IP to per-user while forms stays
  per-IP. This is declared, but it is divergent across siblings.

---

## 13. Questions that would change severity

1. Is upgrading a live 0.88.0 install to 0.89.0 a supported path? Yes promotes
   `initial-migration-edited-in-place` to an S2 data-loss finding. No keeps it as a watch item.
2. Does any deployment rely on hosted E2E at release, rather than the manual `make ci-e2e`? Yes
   raises `e2e-release-tag-trigger-never-matches` one step.

---

## 14. Companion hand-off intake

- **Arch-audit red flag** (0.88.0 billing broken on PyPI): still present. The fix is on v89 and
  0.89.0 is unpublished. §6 batch 1 should land before the tag.
- **Coherence hand-offs:**
  - `module-enabled-switch`: killed.
  - `markdownx-shared-mount`: killed (SA261).
  - `option-schema-and-validation`: killed.
  - `module-error-http-mapping`: killed (SA264).
  - `optional-sender-guard`: resolved as `forms-notification-status-misreported`.
  - `tenant-authorization`, billing half: killed. Details in §8.

---

## 15. Reconciliation log

- 2026-09-23 — **process note:** the 2026-09-23 closeout commits (SA198–SA203) regenerated this
  file without log lines for ten prior IDs. Every prior ID was reinstated below after being
  re-verified in code.
- 2026-09-23 — `dr-backup-drops-tls-options`: resolved (`120d7d8b`, SA198). Verified at
  `primitives.py` `_LIBPQ_OPTION_ENVIRONMENT_VARIABLES` / `_resolve_postgres_connection_parameters`
  (both dump and restore builders) and the merging runner (`:153–155`).
- 2026-09-23 — `billing-stripe-call-inside-delete-txn`: resolved (`1270ed46`). Verified at
  `auth/views.py:97–295`: Stripe cancellation runs between the two locked atomics, a locked
  re-validation precedes deletion, and a compensating resume runs in `finally`.
- 2026-09-23 — `proxy-ssl-header-trusted-unconditionally`: resolved (`dd310cfc`, SA200). Verified
  at `production.py.j2:129`.
- 2026-09-23 — `billing-webhook-lock-released-before-processing`: resolved (`1270ed46`). Verified at
  `services.py:1810–1923`: the per-event session advisory mutex spans handler and persistence.
- 2026-09-23 — `billing-checkout-endpoints-unthrottled`: resolved (`d7f0cf87`, SA201). Verified at
  `billing/views.py:179,235,291,346`, `adapter.py:54–59`, `base.py.j2:406–421`.
- 2026-09-23 — `correlation-id-header-unbounded`: resolved (`dd310cfc`, SA200). Verified at
  `base.py.j2:136`, `:196–201`.
- 2026-09-23 — `orgs-ready-early-return-skips-receivers`: resolved (`aa5ff547`, SA203). Verified at
  `orgs/apps.py:197`, `:231`, `signals.py:69`. The fix-regression pass found no new defect; its
  fast-delete cost is a watch item.
- 2026-09-23 — `blog-throttle-racy-on-database-cache`: resolved (`d7f0cf87`, SA201). Verified at
  `blog/views.py:314–348`: a single `INSERT … ON CONFLICT … RETURNING`.
- 2026-09-23 — `blog-throttle-ident-collision`: resolved (`d7f0cf87`, SA201). Verified at
  `blog/views.py:303–311`: a BLAKE2s-hashed identity.
- 2026-09-23 — `stripe-search-query-unescaped`: resolved (`5556e710`, SA199). Verified at
  `services.py:255–262`, `4062–4069`.
- 2026-09-23 — `pipeline-mutable-action-refs`: resolved (`cba8be07`, SA202). Verified that every
  third-party `uses:` in all four workflows is SHA-pinned, Poetry is pinned to 2.4.1, and every
  workflow has top-level `permissions: contents: read`.
- 2026-09-23 — `build-system-requires-unpinned`: still-open, narrowed. `cba8be07` bounded all 17
  repository manifests. The generator template (`pyproject.toml.j2:30`) still emits the unbounded
  requirement into R2 projects.
- 2026-09-23 — `billing-stripe-objects-normalized-empty`: new, open (S1).
- 2026-09-23 — `billing-stripe-api-version-drift`: new, open (S2).
- 2026-09-23 — `billing-stripe-api-version-drift`: upgraded S2 → S1. The team decided to target
  the latest Stripe API version (`2026-06-24.dahlia`), which makes the dahlia webhook endpoint the
  supported configuration and removes the endpoint-version precondition that discounted it. The
  fix is re-scoped to latest-version-only with a webhook version guard.
- 2026-09-23 — `billing-stripe-api-version-drift`: fix decisions accepted by the team. A webhook
  whose `api_version` is a different named release is rejected with `BillingConfigurationError`
  (500, so Stripe retries). Matching is by named release (`dahlia`), not by exact date.
- 2026-09-24 — `billing-stripe-objects-normalized-empty`: resolved (`f1627c51`, SA209). Verified at
  `services.py:4235`: `_normalize_mapping` converts SDK objects with `to_dict()` before the mapping
  check, and `test_stripe_contract.py` proves a locally signed body through the real
  `StripeClient.construct_event` keeps its event id.
- 2026-09-24 — `billing-stripe-api-version-drift`: resolved (`f1627c51`, SA209). Verified at
  `services.py:42`, `:505`, `:1813`, `:3060`, `:3108`, `:3152`: `STRIPE_API_VERSION` is declared
  once and set on the SDK, a webhook from a different named release is refused with
  `BillingConfigurationError` (500) and its version is logged, invoice reads use
  `parent.subscription_details`, line prices use `pricing.price_details.price`, and period bounds
  come from agreeing subscription items without blanking known bounds.
- 2026-09-24 — `build-system-requires-unpinned`: resolved (SA210 closeout). Verified at
  `pyproject.toml.j2:31`: generated projects emit `poetry-core>=2.0,<3.0`, and the SA90 emission
  fixture pins the new `pyproject.toml` hashes in all three variants.
- 2026-09-24 — re-run at `cdb6223f`: no prior ID was open and none is reopened; the SA209 and SA210
  closures were re-checked at `services.py:4235` and `pyproject.toml.j2:31` and still hold. Watch
  items carried (triggers not fired); two added (SA205 vintage, SA208 E001). New findings: 0.
- 2026-10-03 — re-run at `c10b529e` (delta `cdb6223f..c10b529e`): no prior finding was open; none
  regressed. The SA209 and SA210 closures hold (`services.py:273–288`, `pyproject.toml.j2`).
- 2026-10-03 — `dr-restore-vintage-exact-match`: carried (trigger not fired).
- 2026-10-03 — `orgs-provider-id-check-blocks-migrate`: carried (trigger not fired).
- 2026-10-03 — `blog-upload-client-extension`: new, open (S3). Pre-existing code whose reachability
  SA226 widened from staff to org members.
- 2026-10-03 — `blog-upload-client-extension`: resolved (SA239). Blog and storage upload paths
  derive the extension from the validated image format.
- 2026-10-03 — `crm-stage-seed-lost-on-commit-failure`: new watchlist (introduced by SA229).
- 2026-10-03 — `orgs-disabled-in-saas-wedges-site`: new watchlist (introduced by SA219).
- 2026-10-05 — re-run at `8e4122f2` (delta `c10b529e..8e4122f2`): no prior finding was open. None
  regressed. The SA239 closure (`blog-upload-client-extension`) still holds: the extension comes
  from the validated format.
- 2026-10-05 — `dr-restore-vintage-exact-match`: carried (trigger not fired).
- 2026-10-05 — `orgs-provider-id-check-blocks-migrate`: carried (trigger not fired).
- 2026-10-05 — `crm-stage-seed-lost-on-commit-failure`: carried (trigger not fired).
- 2026-10-05 — `orgs-disabled-in-saas-wedges-site`: carried (trigger not fired).
- 2026-10-05 — `notifications-anonymize-rewrites-all-messages`: new, open (S2). Introduced by `3cffb168`.
- 2026-10-05 — `anonymize-full-table-scans-under-locks`: new, open (S3).
- 2026-10-05 — `billing-anonymize-name-substring`: new, open (S4).
- 2026-10-05 — `notifications-account-username-dead`: new, open (S4).
- 2026-10-05 — `notifications-anonymize-rewrites-all-messages`: resolved (SA244). The executor
  selects linked messages only; the pre-key fallback matches a complete address in
  `context_json`. Recorded limit: an invitation message sent before the actor key existed names
  only the inviter's display name, so it carries no address and stays as stored.
- 2026-10-05 — `anonymize-full-table-scans-under-locks`: resolved (SA244). Session removal filters
  `expire_date__gt=now()`, billing loads only address-matching payloads, and message selection no
  longer walks the table.
- 2026-10-05 — `notifications-account-username-dead`: resolved (SA244). The helper is deleted.
- 2026-10-05 — re-run at `e2623cb8` (delta `8e4122f2..e2623cb8`): the SA244 closures of
  `notifications-anonymize-rewrites-all-messages`, `anonymize-full-table-scans-under-locks`, and
  `notifications-account-username-dead` were re-verified in code and passed the fix-regression pass.
  None regressed. New findings: 0.
- 2026-10-05 — `billing-anonymize-name-substring`: still-open (S4). Unchanged at
  `_anonymization.py:151`; the SA244 pre-filter now limits it to the person's own payloads.
- 2026-10-05 — `dr-restore-vintage-exact-match`: carried (trigger not fired).
- 2026-10-05 — `orgs-provider-id-check-blocks-migrate`: carried (trigger not fired).
- 2026-10-05 — `crm-stage-seed-lost-on-commit-failure`: carried (trigger not fired).
- 2026-10-05 — `orgs-disabled-in-saas-wedges-site`: carried (trigger not fired).
- 2026-10-05 — `anonymize-prefilter-ascii-only-casefold`: new watchlist (introduced by SA244, `b179990b`).
- 2026-10-06 — `billing-anonymize-name-substring`: **resolved** (SA245, `abbc09d0`; re-verified at
  `9917fec2`). Billing scrubs through core's `replace_address`/`redact_names`; name matching is
  word-bounded, dict keys are never rewritten, and billing's
  `test_anonymize_never_rewrites_payload_keys` pins it. The finding is dropped from the index and
  summary.
- 2026-10-06 — the anonymization **bystander** conformance test gap closed (SA248,
  `notifications/tests/test_anonymization_bystanders.py`): every registered template key renders
  with a sentinel user, the anonymizer selects the linked message, and a bystander's message stays
  byte-identical.
- 2026-10-08 — `anonymize-prefilter-ascii-only-casefold`: **resolved**, and its premise was
  wrong. A PostgreSQL test showed the SQL pre-filter finds a non-ASCII address in another case.
  The miss was in core's `_ADDRESS_PATTERN`, which accepted only ASCII letters, so an
  internationalized address was never scrubbed in any case. The address pattern, the
  notifications escaped-address pattern, and the name word boundaries are now Unicode-aware;
  billing and core tests pin it. Dropped from the index and watchlist.
- 2026-10-08 — Questions: **purged** (`clearsessions`, database ctype). The ctype question is moot
  now that the fix is verified on a UTF-8 database and the matcher no longer depends on ASCII.
- 2026-10-08 — **independent full pass at `2fd8637f`** (at the invoker's request; not a delta
  continuation). The prior document was read after the sweep. It held no open finding, so no
  previously discovered open issue needed carrying beyond the watchlist.
- 2026-10-08 — `billing-anonymize-name-substring`: resolution re-verified in code
  (`billing/_anonymization.py:94-104`).
- 2026-10-08 — `anonymize-prefilter-ascii-only-casefold`: resolution re-verified in code
  (`runtime/redaction.py:27-29`, Unicode `\w`).
- 2026-10-08 — `dr-restore-vintage-exact-match`: carried (trigger not fired).
- 2026-10-08 — `orgs-provider-id-check-blocks-migrate`: carried (trigger not fired).
- 2026-10-08 — `crm-stage-seed-lost-on-commit-failure`: carried (trigger not fired).
- 2026-10-08 — `orgs-disabled-in-saas-wedges-site`: **retired**. The premise is obsolete since
  `a621299b` (SA235, already contained in `e2623cb8`). The middleware now redirects only when the
  orgs index reverses, and passes the request through when the orgs URLs are unmounted (verified
  at `middleware.py:195-198`). Earlier passes carried it as "middleware unchanged" without
  re-reading the redirect.
- 2026-10-08 — carried one-liners: the Stripe SDK timeout note is merged into the new watchlist
  item `single-sync-worker-vendor-calls`; the others are carried (not fired).
- 2026-10-08 — new open: `billing-checkout-relative-redirect-urls` (S2, regression `c7320b02`),
  `analytics-distinct-id-is-session-key` (S2), `generated-ci-fails-out-of-box`,
  `notifications-webhook-rejects-resend`, `billing-reservation-unknown-outcome-permanent`,
  `anonymize-matches-unverified-address`, `org-invitation-email-unthrottled`,
  `deploy-settings-module-from-service-name`, `billing-async-payment-never-credited`,
  `generated-ci-mutable-action-tags` (S3), and eight S4s.
- 2026-10-08 — new watchlist: `backups-upload-restore-by-model-permission`,
  `single-sync-worker-vendor-calls`, `allow-bypassrls-serving-undetected`,
  `migrate-runs-per-replica`.
- 2026-10-08 — `billing-checkout-relative-redirect-urls`: **code resolved** (SA251, slice a). The
  purchase, subscription, and portal views build their return URLs with
  `request.build_absolute_uri(reverse(...))`, and `StripeClient` refuses a URL without a scheme
  and host before any provider call; view tests pin the absolute values and contract tests pin the
  refusals. The live Stripe test-mode checkout record is still owed, so the finding stays open.
- 2026-10-08 — `analytics-distinct-id-is-session-key`: **resolved** (SA252). The distinct ID is
  the signed-in user's stable non-secret ID when authenticated identity linkage is enabled and a
  random session-stored anonymous ID otherwise; `get_distinct_id` reads no session key, the
  distinct-ID tests assert the session key appears in no returned value, and rule 22's detector
  rejects a `session_key` read in module source with control cases. Dropped from the index and
  summary; its private companion's scenario no longer applies.
- 2026-10-08 — `analytics-dashboard-unauthenticated`: **resolved** (SA252). The overview page
  requires login and the active organization's `viewer` role through orgs' one role check; tests
  cover anonymous redirection, a caller with no organization context, and a non-member session
  organization. Dropped from the index and summary.
- 2026-10-08 — `billing-reservation-unknown-outcome-permanent`: **resolved** (SA251, slice b). A
  definitive Stripe 4xx rejection resolves the reservation against the provider before it is
  closed (`_removal.py` `_resolve_definitively_failed_purchase_checkout`,
  `_subscription_checkout_steps.py` `_resolve_definitively_failed_subscription_checkout`); a
  session-less reservation is looked up by its stored reference and adopted, expired, or voided
  (`StripeClient.find_checkout_session_by_reference`, `_removal.py`, `_subscription_checkout.py`);
  and `quickscale_billing_reconcile_checkouts` clears accumulated rows under the organization's
  provider mutation mutex. Verified by the billing, orgs, and auth suites.
- 2026-10-08 — `billing-async-payment-never-credited`: **resolved** (SA251, slice c). A
  `checkout.session.completed` whose `payment_status` is `unpaid` binds the purchase reservation
  and is accepted instead of raising, `checkout.session.async_payment_succeeded` credits the
  one-time purchase through the existing ledger dedup, and `checkout.session.async_payment_failed`
  expires the reservation under the organization's provider mutation mutex. Both events are
  dispatched, and the generated operations guide lists them.
- 2026-10-08 — `anonymize-matches-unverified-address`: **resolved** (SA254). Auth's anonymize
  boundary captures whether allauth holds a verified `EmailAddress` for the account's address
  before any hook runs, and passes it as the `email_verified` keyword to every executor; orgs,
  notifications, and billing run their address-based selectors only when it is true, scoping an
  unverified account to its user-linked rows (billing's `WebhookEvent` has no user link, so an
  unverified address scrubs nothing). Tests pin a verified and an unverified address, including a
  second tenant holding the same unverified address. Dropped from the index and summary.
- 2026-10-08 — `org-invitation-email-unthrottled`: **resolved** (SA254). Both invite paths carry
  the `quickscale_orgs_invite` (per sender) and `quickscale_orgs_invite_organization` (per target
  organization) DRF scopes, both fed by the `invite_rate_limit` option; both buckets are charged
  only after the role gate and the form's locked eligibility checks pass, so neither an
  unauthorized, invalid, cap-refused, nor duplicate attempt drains them, and a refused throttle
  rolls the just-written invitation back so no email is sent. Each organization caps its active
  pending invitations at
  `pending_invitation_limit` under the organization row lock, and the invitation email's
  sender-chosen organization and inviter names are bounded by their stored fields and rendered
  escaped. Tests cover 429 past the scope rates on both paths, the organization aggregate budget
  across senders, the pending cap, and the bounding and escaping. Dropped from the index and
  summary.
- 2026-10-08 — `viewas-overrides-management-org`: **resolved** (SA254).
  `OrganizationContextMixin.get_organization()` resolves the route's `org_slug` before falling
  back to `request.org`, so a management page under VIEW-AS acts on the organization its URL
  names; a regression test edits `/orgs/<B>/settings/` under a VIEW-AS session for A and proves B
  changes and A does not. Dropped from the index and summary.
- 2026-10-10 — `deploy-settings-module-from-service-name`, `deploy-runtime-url-unquoted-password`,
  `dr-media-sync-whole-object-read`: **resolved** (SA256). Deploy writes `DJANGO_SETTINGS_MODULE`
  from the project's `state.project.package` and leaves an existing service value alone, so a
  non-default or manually corrected package boots; `RUNTIME_DATABASE_URL` percent-encodes the
  password (covered with `@:/%#`); and both s3-compatible media directions stream through the
  provider clients' chunked transfers — s3→local through `download_fileobj` into an exclusively
  created sibling file that replaces the destination only on success, preserving the destination's
  mode, and s3→s3 through a memory-bounded relay spool of at most 64 MiB instead of the storage
  API, whose `open()` spools whole objects in memory (`AWS_S3_MAX_MEMORY_SIZE` defaults to
  unbounded). Dropped from the index and summary.
- 2026-10-10 — `billing-checkout-relative-redirect-urls`: **resolved** (SA251). One Stripe
  test-mode checkout completed from the billing API view at HEAD (billing embedded from its v89
  tree): the purchase view built its success and cancel URLs from the request with
  `request.build_absolute_uri`, and Stripe accepted the session
  (`cs_test_a1DNFnZGrbMnE2NjZM8uvMRiujLwIVgYjsx6nrQLDu8txIGZpwjdMpu0Os`, `status=complete`,
  `payment_status=paid`, 1900 usd). The endpoint-version contract was exercised in both
  directions: `stripe listen`'s real delivery (pinned `2025-03-31.basil`) was refused with a
  retryable 500, and the same real event was then delivered with its `api_version` set to the
  required `2026-06-24.dahlia` release and a valid endpoint signature — the resend the endpoint
  recreation step prescribes, reproduced locally rather than by a Stripe-origin dahlia endpoint —
  and processed into a `completed` purchase reservation and a 100-credit balance, with a
  redelivery deduped. Dropped from the index and summary; the §13 checkout question is answered.
- 2026-10-10 — `generated-ci-fails-out-of-box`, `generated-ci-mutable-action-tags`,
  `docker-healthcheck-always-unhealthy`, `frontend-image-floating-deps`: **resolved** (SA253).
  The rendered `ci.yml.j2` pins every action by commit SHA with version comments and declares a
  top-level `permissions: contents: read`; the test step sets `DATABASE_URL` and the migrate and
  isolation steps run under `<package>.settings.local`. `check_workflow_security.py
  --generated-template` renders the template offline and scans it under the same zizmor contract,
  and `refresh_action_pins.py` refreshes the template's pins in source and fails closed on an
  unpinned `uses:` line. `Dockerfile.j2`'s `HEALTHCHECK` probes `/healthcheck/` presenting the
  always-admitted `healthcheck.railway.app` Host and expects a 2xx response; the frontend
  stage requires the committed `frontend/pnpm-lock.yaml` and installs with `--frozen-lockfile`
  (the generator now emits the lockfile). The generated sample suite covers the URL surface and
  application entry points, and `pyproject.toml` omits settings packages from coverage, so the
  rendered test command passes at its 90% gate; the generated views, context-processor, and
  managed-URLconf import blocks are ruff-clean, so the rendered ruff steps pass too. The new
  registered
  `check-generated-project-automation` gate executes the rendered test and migrate commands and
  the image healthcheck payload against a fresh offline-rendered project inside the provisioned
  PostgreSQL profile. Dropped from the index and summary; the §10 tooling gaps close with them.
  The rendered workflow's remaining red job is recorded as the new open finding
  `generated-frontend-coverage-unmet`, not as part of this closure: the generated frontend's
  `pnpm test:coverage` per-file 80% thresholds are not met by the shipped theme suite (global
  ≈77.7% statements, per-file failures across pages, hooks, and UI primitives).
- 2026-10-10 — `social-payload-echoes-exception-text`: **resolved** (SA262). The core-rendered
  social payload views are DRF views that answer the one error shape and never echo exception
  text. Dropped from the index and summary.
- 2026-10-10 — `generated-frontend-coverage-unmet`: **resolved** (SA253). The shipped
  `showcase_react` suite now exercises the starter's pages, hooks, stores, components, UI
  primitives, and the analytics wiring, so a freshly rendered project's frontend
  `pnpm test:coverage` passes its existing per-file thresholds with the thresholds and coverage
  include set unchanged. Dropped from the index and summary.
- 2026-10-10 — `notifications-webhook-rejects-resend`: **resolved** (SA255). The endpoint reads
  `svix-id`/`svix-timestamp`/`svix-signature`, decodes the base64 `whsec_` signing secret, checks
  the `webhook_ttl_seconds` window, and accepts any `v1` candidate in the space-separated
  signature header with `hmac.compare_digest`; ingestion maps `type`, `data.email_id`, and
  `data.to[0]` and keeps `svix-id` as the replay key. A contract test built from the vendor's
  documented payload and signature covers it, and the rule 26 conformance detector credits the
  vendor's candidate loop. Dropped from the index and summary; the §10 tooling gap and the §13
  question close with it.
- 2026-10-13 — re-run at `7d9782a9` (delta `2fd8637f..7d9782a9`, 104 non-merge commits; prompt v7). Every closure claimed since the prior pass (SA251 a/b/c, SA252, SA253, SA254, SA255, SA256, SA262 social) was re-verified in code and passed the fix-regression pass. None regressed.
- 2026-10-13 — `forms-notification-status-misreported`: **resolved** (`a6b58799`, SA265b). Verified at `forms/_email.py:44-53`: notifications off returns `"skipped"`, and the submit view surfaces it as `notification_status`.
- 2026-10-13 — `stripe-customer-search-lag-resolves-absent`: **resolved** (SA270). Verified at `billing/_customers.py`: a customer-search miss counts as absence only once the organization's latest customer-resolution attempt completed and is older than Stripe's documented Search indexing lag (up to an hour behind during outages), two matches fail closed, the search requests `limit=2`, and `auth/tests/test_views.py` asserts an unknown outcome blocks deletion again. Dropped from the index and summary.
- 2026-10-13 — `dr-restore-vintage-exact-match`, `orgs-provider-id-check-blocks-migrate`, `crm-stage-seed-lost-on-commit-failure`, `backups-upload-restore-by-model-permission`, `single-sync-worker-vendor-calls`, `allow-bypassrls-serving-undetected`, `migrate-runs-per-replica`, `development-workflow-intermittent-root-500`, `core-e2e-poetry-cache-install-candidates`: carried (triggers not fired; evidence in §11).
- 2026-10-13 — new open: `stripe-customer-search-lag-resolves-absent`, `dr-private-remote-restore-whole-object-in-memory`, `e2e-release-tag-trigger-never-matches` (S3); `crm-theme-stats-always-zero`, `notifications-webhook-status-regresses-out-of-order`, `notifications-webhook-secret-format-unchecked-at-startup`, `orgs-invite-throttle-partial-charge`, `markdownx-upload-client-extension-and-content-type`, `dr-media-part-file-leak-on-publish-failure`, `pyproject-write-not-atomic`, `ci-poetry-retry-curl-pipe-python` (S4).
- 2026-10-13 — new watchlist: `orgs-role-mixin-checks-request-org`, `social-config-error-served-200`, `deploy-existing-settings-module-never-corrected`, `account-deletion-hook-exception-text`, `security-suppressions-uniform-expiry`, `generated-project-automation-local-only`, `initial-migration-edited-in-place`.
- 2026-10-13 — Question 1 (answered SA255) retired. Two new questions added (§13).
