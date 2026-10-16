# QuickScale — Deep Technical Audit (defect sweep)

Audited: 30b0b6b1bf5412cffe1cae9fc0d6020c288b485c (v89) · 2026-10-16 · working tree dirty (uncommitted `docs/others/arch-audit.md`; not read as evidence) · repository public (github.com/Experto-AI/quickscale; no `SECURITY.md`) · prompt: deep-technical-audit v7

> **Mode:** re-run. Delta `7d9782a9..30b0b6b1`: 55 non-merge commits plus the `wt-track2` merge.
> First-party production diff: 116 files (+2.3k/−3.0k), most of it the removal of the tracked
> bundled manifests. Every prior ID has a line in §15.

---

## 1. Orientation summary

**System, deployment realities, entry points, actors, crown jewels, configuration axes, and data
sensitivity:** unchanged from the 2026-10-13 pass (`git show 34d2a9f0:docs/others/tech-audit.md`,
§1). In short:
- A Python 3.14 / Django 6.0 project generator and CLI, plus 12 embeddable modules.
- **R1:** the CLI on developer machines.
- **R2:** the generated SaaS, internet-facing on Railway: gunicorn, PostgreSQL with FORCE RLS
  under a restricted role.
- **R3:** the tag-triggered PyPI release over OIDC.

**Changes since the prior pass that touch exposure:**
- The bundled module manifests are now build artifacts (SA280b). Every wheel-build entrypoint
  materializes them, the publish workflow materializes them before building, and the Poetry
  include declares `format = [sdist, wheel]`.
- Adapter hooks receive a frozen `ResolvedOptions` instead of a dict (SA281a).
- The Stripe API version is one authored constant (SA280a).
- DR restores compare recorded migration *content* hashes instead of module version labels
  (SA204d). Operator `--file` restores, which record no identity, are now refused by design.
- A migration freeze gate (SA204c) makes shipped migration files immutable from now on.
- `quickscale update` refuses an equal-label pull that rewrites an applied migration (SA204e).
- The managed theme seam files are generated and hash-tracked (SA276).
- CRM has an organization stats endpoint (SA274).

**Tooling baseline:** as before, plus `check-migration-freeze` in hosted CI and publish.
`check-manifest-sync` is retired, since its input no longer exists.

**Oracle list:** unchanged (fail-hard; RLS boot guard; rule 9; rule 26; rule 19; rules 20/21;
rule 35; the `WebhookEvent` gate; security gates never skip; SHA-pinned workflows). Added:
- 11. Shipped migration files are immutable once frozen (SA204).

**Measurements.** In re-run mode the delta replaces the churn ranking. The delta has 9
fix-shaped commits, all of them ticketed closures of the prior pass's findings or review-round
fixes.

**Delta classification.**
- **Review-tracked:** SA204 a–f, SA269–SA276, SA278–SA283, each with a roadmap or changelog trail
  and a recorded review round.
- **Housekeeping, no production hunks:** `49edb504`, `34d2a9f0`, `77fea4d4`, `4f0a80ce`,
  `a7f3172a`, `cab32d8a`.
- **Unreviewed-behavioral candidates, read in full:**
  - `11da2d79` ("retire check-manifest-sync"): it dropped
    `quickscale_core/src/quickscale_core/generator/**` from the E2E pull-request path list. Killed:
    `quickscale_core/src/**` (`e2e.yml:47`) still covers it. The three CLI test paths it dropped
    were restored by `5dd2b2a6`.
  - `0fdf2b44` ("load-tolerant timeout"): touches test and gate code only. No production hunk.

### Coverage and residual-risk statement

**Method:** a single agent, no sub-agents. The production delta was read directly, prioritizing
closures, crown-jewel paths, and unreviewed-behavioral commits.

**Read in full (diff plus surrounding code):**
- **notifications:** `_webhooks.py`, `checks.py`, and the delivery model's statuses.
- **orgs:** `throttles.py`, the `views.py` invite paths, `apps.py`, `_removal_declarations.py`,
  and the purge command's diff.
- **billing:** `_customers.py`, `_settings.py`, `_stripe_client.py`, the `_removal.py` and
  `_subscription_checkout_steps.py` call sites, and the `models.py` and `0001_initial` diffs.
- **crm:** `CRMStatsView` and its siblings' queryset scoping.
- **storage:** `markdownx_urls.py` and `_helpers.py`, read against the installed
  `markdownx/forms.py` vendor code.
- **CLI:** `_module_update*.py`, `remove_command.py`, `_dependency_write.py`, and
  `module_wiring_manager.py`.
- **core:** `dr_engine/recovery.py`, `_restore.py`, `adapter.py`, `_metadata.py`, `_capture.py`,
  and `_report.py`; `runtime/seam.py`; `contracts/module_discovery.py` (bundled resolution);
  `manifest/resolved_options.py`; `generator.py`; and `module_options.py`.
- **Pipeline:** all four workflow diffs and the head of `scripts/check_migration_freeze.py`.

**Sampled:**
- the commit message and file list of the SA280b manifest build change;
- the other module adapters' `ResolvedOptions` mechanical diffs;
- the analytics and social adapters.

**Skipped:**
- the `scripts/` test refactors (about 12k lines), beyond a scan for added skips and xfails;
- the React theme test rewrites;
- devtools `constants.py`;
- the contract-vintage CLI diff.

**Empirical checks (§1e):** none executed against a datastore. The vendor markdownx `ImageForm`
source was read from the project venv to confirm that `save()` reads the same `UploadedFile`
object that `clean()` mutates. It does, so the re-derived name and content type reach storage.

**Category activation:**
- **Active:** I, II, III, IV, VI, VII, VIII, IX; X: generator, multi-tenant, service/webhooks,
  CLI, library.
- **Inert:** V (no hot-path change in the delta); X mobile, firmware, GraphQL/RPC, ML/LLM, data
  pipeline.
- **Produced:** none.

**Sibling sweep:**
- No module still calls DRF `allow_request(` directly. The invite views are the only
  multi-throttle callers.
- No workflow, generated template, script, or Makefile pipes `curl` into an interpreter.
- No delta test hunk adds `skip`/`xfail`.

**Residual risk.**
- Not checked live: PostgreSQL lock semantics for the new `select_for_update` path, Stripe Search
  timing, or a real wheel build. The wheel's contents rest on the commit's recorded
  build-and-inspect test.
- Out-of-repo controls remain invisible: the Railway edge, GitHub org settings, Stripe and Resend
  project configuration.
- Silence on the skipped areas licenses no conclusion.

---

## 2. Machine-readable finding index

```yaml
schema: tech-audit/v6
audited: 30b0b6b1bf5412cffe1cae9fc0d6020c288b485c
items:
  - {id: orgs-provider-id-check-blocks-migrate, status: watchlist, category: VI, reality: generated-app,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/checks.py],
     first_seen: 2026-09-24, last_verified: 2026-10-16}
  - {id: crm-stage-seed-lost-on-commit-failure, status: watchlist, category: II, reality: generated-app,
     anchors: [quickscale_modules/crm/src/quickscale_modules_crm/receivers.py],
     first_seen: 2026-10-03, last_verified: 2026-10-16}
  - {id: backups-upload-restore-by-model-permission, status: watchlist, category: III,
     reality: generated-app,
     anchors: [quickscale_modules/backups/src/quickscale_modules_backups/_admin_restore.py],
     first_seen: 2026-10-08, last_verified: 2026-10-16}
  - {id: single-sync-worker-vendor-calls, status: watchlist, category: IV, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/generator/templates/start.sh.j2],
     first_seen: 2026-10-08, last_verified: 2026-10-16}
  - {id: allow-bypassrls-serving-undetected, status: watchlist, category: VI, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/runtime/settings.py],
     first_seen: 2026-10-08, last_verified: 2026-10-16}
  - {id: migrate-runs-per-replica, status: watchlist, category: II, reality: generated-app,
     anchors: [quickscale_core/src/quickscale_core/generator/templates/start.sh.j2],
     first_seen: 2026-10-08, last_verified: 2026-10-16}
  - {id: development-workflow-intermittent-root-500, status: watchlist, category: VI,
     reality: generated-app, anchors: [quickscale_cli/tests/test_e2e_development_workflow.py],
     first_seen: 2026-10-11, last_verified: 2026-10-16}
  - {id: core-e2e-poetry-cache-install-candidates, status: watchlist, category: VI, reality: tooling,
     anchors: [quickscale_core/tests/conftest.py], first_seen: 2026-10-12, last_verified: 2026-10-16}
  - {id: orgs-role-mixin-checks-request-org, status: watchlist, category: III, reality: generated-app,
     anchors: [quickscale_modules/orgs/src/quickscale_modules_orgs/permissions.py],
     first_seen: 2026-10-13, last_verified: 2026-10-16}
  - {id: social-config-error-served-200, status: watchlist, category: VI, reality: generated-app,
     anchors: [quickscale_modules/social/src/quickscale_modules_social/services.py],
     first_seen: 2026-10-13, last_verified: 2026-10-16}
  - {id: deploy-existing-settings-module-never-corrected, status: watchlist, category: VI,
     reality: cli, anchors: [quickscale_cli/src/quickscale_cli/commands/_deploy_service_config.py],
     first_seen: 2026-10-13, last_verified: 2026-10-16}
  - {id: account-deletion-hook-exception-text, status: watchlist, category: VI, reality: generated-app,
     anchors: [quickscale_modules/auth/src/quickscale_modules_auth/views.py],
     first_seen: 2026-10-13, last_verified: 2026-10-16}
  - {id: generated-project-automation-local-only, status: watchlist, category: VIII, reality: tooling,
     anchors: [scripts/check_generated_project_automation.py],
     first_seen: 2026-10-13, last_verified: 2026-10-16}
  - {id: initial-migration-edited-in-place, status: watchlist, category: IX, reality: generated-app,
     anchors: [quickscale_modules/billing/src/quickscale_modules_billing/migrations/0001_initial.py,
               quickscale_modules/orgs/src/quickscale_modules_orgs/migrations/0001_initial.py,
               quickscale_modules/blog/src/quickscale_modules_blog/migrations/0001_initial.py],
     first_seen: 2026-10-13, last_verified: 2026-10-16}
```

---

## 3. Summary table

**Counts:**
- **Open:** 0 (S1 — 0 · S2 — 0 · S3 — 0 · S4 — 0).
- **Watchlist:** 14. *(Same-day follow-up: SA295 re-adjudicated all nine suppressions against the
  live source and retired `security-suppressions-uniform-expiry`; §11.)*
- **This pass:** 5 resolved, 0 new, 0 regressed, 0 withdrawn; 1 watchlist item retired.

No open findings.

---

## 4. Findings

None. Every candidate raised this pass was killed (§8). A clean result on a delta made of
ticketed closures and reviewed refactors is the expected outcome, not an under-search. §1 records
what was read.

---

## 5. Safeguard matrix

The prior matrix (`git show 2fd8637f:docs/others/tech-audit.md`, §5) stands with the 2026-10-13
changed-cell table. Cells changed this pass:

| Entry point | Changed cell(s) at HEAD |
|---|---|
| `NotificationWebhookView` | Startup: the secret must be non-empty, `whsec_`-prefixed, and decodable by the endpoint's own decoder (`checks.py` `_svix_secret_problem`). Ordering: forward-only status rank under `select_for_update` on the delivery row (`_webhooks.py` `_record_delivery_event`, `_apply_delivery_event`). |
| Orgs invite (HTML + JSON) | Throttle: both buckets checked, then both charged (`views.py` `charge_invitation_throttles`, `throttles.py` `_CheckThenChargeThrottleMixin`); a refusal spends neither. |
| CRM stats (`crm/api/stats/`, new) | AuthN: core session authentication. AuthZ: `HasOrgRole(VIEWER)`. Scope: explicit `organization_id` from `_resolve_active_org`, like its sibling viewsets, with RLS below. Read-only counts. |
| Markdownx editor upload | Staff-only (unchanged). Content: decoded through storage validation with a JPEG/PNG/GIF allowlist; the stored extension and content type are re-derived from the decoded format; SVG is removed from `MARKDOWNX_UPLOAD_CONTENT_TYPES`. |
| Billing customer resolution / reconcile | The attempt is stamped on unresolved reservations before and after the Stripe call. A reconcile miss counts as absent only after a 1h lag measured from the last completed attempt; an attempt with no recorded outcome blocks; two matches fail closed (`limit=2`). |
| DR restore (artifact / snapshot / file) | Guard: recorded per-file migration hashes must be installed byte-identical. Newer installed migrations are allowed only on the DR snapshot route (`allow_forward=True`, which migrates afterwards). A source that records no identity, including `--file`, is refused. |
| `quickscale update` (CLI) | An equal-label pull that rewrites or removes an applied migration is refused, and the failing module's own pull is rolled back with the others. |
| Release E2E | Tag globs equal `publish.yml`'s (`"[0-9]*"`, `"v[0-9]*"`), and a test pins the equality. |
| CI Poetry retry (4 sites) | `pip install --user poetry==2.4.1`. No curl-to-interpreter remains. |

---

## 6. Fix order and batching

Nothing is open. For the watchlist:
- Answer §13 Q1 before publishing 0.89.0.

---

## 7. Per-subsystem verdicts

| Subsystem | Verdict | What was read |
|---|---|---|
| notifications | clean. Both prior S4s resolved and their fixes passed the fix-regression pass. | Webhook path, checks, models. |
| orgs | clean. The throttle fix and the purge invalidation-hook capability verified (bound-method membership holds). | Throttles, invite views, apps, removal declarations, purge diff. |
| billing | clean. SA270 lag handling verified; the SA280a constant move is mechanical. | Customer resolution and reconciliation call sites. |
| crm | clean. | Stats view and its siblings' scoping. |
| storage | clean. | Markdownx wrapper against the vendor form. |
| core DR | clean. One prior watch item retired (§11). | Recovery, restore, metadata, capture, report, adapter. |
| core runtime / generator | clean. | Seam renderers, generator context, discovery, `ResolvedOptions`. |
| CLI | clean. | Module update, identity guard, remove, dependency write, wiring manager. |
| pipeline | clean. Both prior findings resolved. | Workflows, freeze gate. |
| other modules (analytics, auth, blog, forms, listings, social, backups) | clean (`ResolvedOptions` mechanical diffs and the blog field promotion only). | Diffs. |

---

## 8. Clean sweeps and rejected candidates

- **Verified closures (in code, with the fix-regression pass):**
  - `e2e-release-tag-trigger-never-matches`;
  - `ci-poetry-retry-curl-pipe-python`;
  - `notifications-webhook-status-regresses-out-of-order`;
  - `notifications-webhook-secret-format-unchecked-at-startup`;
  - `orgs-invite-throttle-partial-charge`.

  Details are in §15.
- **Killed:**
  - **Billing attempt stamped "completed" in `finally` after a Stripe exception:** an unknown
    outcome is still covered, because a reconcile miss is trusted only an hour after that stamp,
    and the idempotent create is searchable well within the lag.
  - **Markdownx GIF passthrough storing raw bytes:** the bytes were decoded as GIF first, and the
    stored extension and content type come from the decoded format. Staff-only.
  - **Markdownx `save()` using a different file object than `clean()` mutated:** the vendor
    `save()` reads `self.files['image']`, the same object `FileField.clean` returned (vendor
    source read).
  - **Notification status rank drops `delivered_at` or `last_event_*` on equal-rank events:** an
    equal-rank event is a duplicate state, and the event row still records the receipt.
  - **CRM stats `all_objects` leaking across tenants:** explicitly filtered by the active org,
    viewer role enforced, RLS below. Matches the sibling viewsets.
  - **Wheel shipping without bundled manifests:** the include is declared
    `format = [sdist, wheel]` (`5dd2b2a6`), every build entrypoint materializes first, and a
    build-and-inspect test asserts byte equality. A monorepo checkout resolves MONOREPO before
    BUNDLED (`module_discovery.py:483`).
  - **Seam files overwriting user content in upgraded projects:** the files are new in SA276, so
    no prior user-owned file sits at those paths.
  - **`except A, B:` syntax in `_module_update_identity.py`:** valid on Python 3.14 (PEP 758), and
    every package requires `>=3.14,<3.15`.
  - **E2E path filter dropping `generator/**` (`11da2d79`):** still covered by
    `quickscale_core/src/**`.
  - **`quickscale_backups_restore --file` always refused:** deliberate, documented
    (`backups/README.md:127`), and pinned by
    `test_restore_file_mode_refuses_bare_file_without_recorded_identity`. The CLI help still
    offers `--file` as a source. That is a coherence note, not a defect.
- **No test weakened:** no added `skip` or `xfail`. The vintage-label tests were replaced by
  migration-hash tests asserting stricter refusals.

---

## 9. Structural smells

Carried unchanged from the prior pass:
- The typed Stripe provider-adapter seam is missing.
- Session-level advisory locks silently fail under transaction pooling.
- Outbound timeout policy is implicit.
- `start.sh` has a second database-connection constructor.
- `TenantMiddleware` declares path ownership twice.
- Clean-break schema edits have no data path (owned by the architectural audit). From now on the
  freeze gate holds the line.

The "two S3 streaming idioms" smell is retired with SA271's source scan.

---

## 10. Tooling gaps

- **Workflow-trigger consistency check:** delivered (SA269, `test_publish_trigger.py`).
- **Carried:** image-layer and broader IaC scanning.

---

## 11. Watchlist and accepted trade-offs

- **`initial-migration-edited-in-place`.**
  - **Why watch:** pre-1.0 clean-break edits to `0001_initial`. This pass added billing's
    `customer_lookup_*` and `Subscription.created_at` columns in place (SA270), plus a blog field
    promotion.
  - **Trigger:** a supported upgrade from a live 0.88.0 install.
  - **Evaluation:** not fired. The migration freeze gate (SA204c) now fails any further in-place
    edit after `scripts/migration_hashes.json`, so the exposure is capped at the edits already
    made before 0.89.0.
- **Carried, triggers evaluated — not fired** (each anchor unchanged in the delta unless noted):
  - `orgs-provider-id-check-blocks-migrate`;
  - `crm-stage-seed-lost-on-commit-failure`;
  - `backups-upload-restore-by-model-permission`;
  - `single-sync-worker-vendor-calls`;
  - `allow-bypassrls-serving-undetected`;
  - `migrate-runs-per-replica`;
  - `orgs-role-mixin-checks-request-org`;
  - `deploy-existing-settings-module-never-corrected`;
  - `account-deletion-hook-exception-text`;
  - `generated-project-automation-local-only`;
  - `development-workflow-intermittent-root-500` and `core-e2e-poetry-cache-install-candidates`
    (no recurrence recorded; `conftest.py` changed only to materialize manifests);
  - `social-config-error-served-200` (the social `adapter.py` change is the `ResolvedOptions`
    migration only, and still nothing raises `SocialConfigurationError`).
- **Retired:** `dr-restore-vintage-exact-match`. SA204d replaced the exact version-label match
  with per-file migration content identity, and forward migration is allowed on the DR snapshot
  route. The trigger it watched can no longer occur.
- **Retired:** `security-suppressions-uniform-expiry`. SA295 re-adjudicated all nine suppressions
  against the live source and gave every kept entry an expiry set by its own review horizon:
  quarterly for the raw-JavaScript seam emissions, semi-annual for the encoded JSON seam, annual
  for the scanner heuristic false positive. The trigger — one shared expiry with no review
  scheduled — can no longer occur.

---

## 12. Coherence hand-offs

- The blog and listings API throttles are keyed per user, while forms is keyed per IP (carried).
- `quickscale_backups_restore` still lists `--file PATH` among its accepted sources in its help
  and usage errors, but the guard now always refuses that source (`--file` help at
  `quickscale_backups_restore.py:122`, refusal in `recovery.py` `_get_migration_content_issues`).
  The help and the behavior should agree.

---

## 13. Questions that would change severity

1. Is upgrading a live 0.88.0 install to 0.89.0 a supported path? Yes promotes
   `initial-migration-edited-in-place` to an S2 data-loss finding. No keeps it as a watch item.
   (Carried.)

Prior Q2 (whether hosted E2E at release is relied on) is retired: the trigger is fixed.

---

## 14. Companion hand-off intake

- **Arch-audit red flags:** the companion file is uncommitted and mid-edit in the working tree,
  so it was not used as a lead source this pass.
- **Coherence hand-offs:** no new lead in the to-technical list since the prior pass.

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
- 2026-10-14 — `dr-private-remote-restore-whole-object-in-memory`, `dr-media-part-file-leak-on-publish-failure`: **resolved** (SA271). Verified at `dr_engine/_remote.py` and `_media.py`: every DR object path streams through the provider client's chunked transfers (`download_fileobj`, and `upload_fileobj` for the s3→s3 relay), `_media.py`'s s3→local publish applies the destination mode and renames inside the cleanup `try` so any failure there removes its staging `.part` file, and an in-suite source scan rejects `storage.open()` in `dr_engine`. Dropped from the index and summary; the §10 tooling gap closes with it.
- 2026-10-15 — `crm-theme-stats-always-zero`: **resolved** (SA274). Verified at
  `quickscale_modules/crm/src/quickscale_modules_crm/views.py` and the shipped
  `themes/showcase_react/src/pages/CrmPage.tsx`: the CRM count endpoint (`crm/api/stats/`)
  answers the active organization's contact, company, deal, and tag totals to a viewer-role
  caller, and the theme's stat cards read those totals instead of `.count`/`.results.length`
  from one bare-list page; the CRM suite's theme-contract test checks the hook's declared shape
  against the rendered response. Dropped from the index and summary; the §10 tooling gap closes
  with it.
- 2026-10-15 — `markdownx-upload-client-extension-and-content-type`, `pyproject-write-not-atomic`:
  **resolved** (SA273). Verified at
  `quickscale_modules/storage/src/quickscale_modules_storage/markdownx_urls.py` and
  `quickscale_cli/src/quickscale_cli/utils/_dependency_write.py`: the shared staff-only editor
  upload decodes every file through the module's image validation, stores the decoded format's
  extension and content type instead of the client's filename and media type, and refuses an HTML
  document named `.png` and an SVG (the storage suite's HTTP tests pin both refusals and the
  stored identity), while the CLI writes the validated document through a fresh sibling temp file
  and an `os.replace`, with tests proving an interrupted write and an interrupted replace leave
  the original `pyproject.toml` intact. Dropped from the index and summary.
- 2026-10-15 — coherence hand-off `project_contract.yml:188` stale step prose: fixed (SA282).
  Verified at `quickscale_core/src/quickscale_core/data/project_contract.yml`: the
  sa235-module-shell-routes step's seam description now names the `quickscale_seam` runtime
  template tag the pages actually render through, and the sa258-runtime-seam-tag step's
  supersession sentence reads as history of the retired `generator/seam.py` description. The
  hand-off bullet is dropped from §12.
- 2026-10-13 — `dr-restore-vintage-exact-match`, `orgs-provider-id-check-blocks-migrate`, `crm-stage-seed-lost-on-commit-failure`, `backups-upload-restore-by-model-permission`, `single-sync-worker-vendor-calls`, `allow-bypassrls-serving-undetected`, `migrate-runs-per-replica`, `development-workflow-intermittent-root-500`, `core-e2e-poetry-cache-install-candidates`: carried (triggers not fired; evidence in §11).
- 2026-10-13 — new open: `stripe-customer-search-lag-resolves-absent`, `dr-private-remote-restore-whole-object-in-memory`, `e2e-release-tag-trigger-never-matches` (S3); `crm-theme-stats-always-zero`, `notifications-webhook-status-regresses-out-of-order`, `notifications-webhook-secret-format-unchecked-at-startup`, `orgs-invite-throttle-partial-charge`, `markdownx-upload-client-extension-and-content-type`, `dr-media-part-file-leak-on-publish-failure`, `pyproject-write-not-atomic`, `ci-poetry-retry-curl-pipe-python` (S4).
- 2026-10-13 — new watchlist: `orgs-role-mixin-checks-request-org`, `social-config-error-served-200`, `deploy-existing-settings-module-never-corrected`, `account-deletion-hook-exception-text`, `security-suppressions-uniform-expiry`, `generated-project-automation-local-only`, `initial-migration-edited-in-place`.
- 2026-10-13 — Question 1 (answered SA255) retired. Two new questions added (§13).
- 2026-10-16 — re-run at `30b0b6b1` (delta `7d9782a9..30b0b6b1`, 55 non-merge commits plus one merge; prompt v7). No new findings, none regressed, none withdrawn.
- 2026-10-16 — `e2e-release-tag-trigger-never-matches`: **resolved** (`f4338008`, SA269). Verified at `.github/workflows/e2e.yml:9-11`: the tag globs `"[0-9]*"` and `"v[0-9]*"` match `publish.yml`.
- 2026-10-16 — `ci-poetry-retry-curl-pipe-python`: **resolved** (`f4338008`, SA269). Verified at `ci.yml` (three retry steps) and `nightly-bypassrls.yml`: `pip install --user poetry==2.4.1`. The repo-wide variant grep finds no curl piped into an interpreter.
- 2026-10-16 — `notifications-webhook-status-regresses-out-of-order`: **resolved** (`e8443895`, SA272a). Verified at `notifications/_webhooks.py` `_STATUS_RANK`, `_record_delivery_event` (`select_for_update` on the delivery row), and `_apply_delivery_event` (forward-only).
- 2026-10-16 — `notifications-webhook-secret-format-unchecked-at-startup`: **resolved** (`757f9ec3`, SA272b). Verified at `notifications/checks.py` `_svix_secret_problem`: the `whsec_` prefix and the endpoint's own decoder run at startup (E003).
- 2026-10-16 — `orgs-invite-throttle-partial-charge`: **resolved** (`37415992`, SA272c). Verified at `orgs/throttles.py` `_CheckThenChargeThrottleMixin` and `orgs/views.py` `charge_invitation_throttles`: both buckets are checked before either is charged, on the HTML and JSON paths.
- 2026-10-16 — `dr-restore-vintage-exact-match`: **retired** (SA204d replaced the version-label match with migration content identity and allows forward migration on the DR route).
- 2026-10-16 — `orgs-provider-id-check-blocks-migrate`, `crm-stage-seed-lost-on-commit-failure`, `backups-upload-restore-by-model-permission`, `single-sync-worker-vendor-calls`, `allow-bypassrls-serving-undetected`, `migrate-runs-per-replica`, `development-workflow-intermittent-root-500`, `core-e2e-poetry-cache-install-candidates`, `orgs-role-mixin-checks-request-org`, `social-config-error-served-200`, `deploy-existing-settings-module-never-corrected`, `account-deletion-hook-exception-text`, `security-suppressions-uniform-expiry`, `generated-project-automation-local-only`, `initial-migration-edited-in-place`: carried (triggers not fired; evidence in §11).
- 2026-10-16 — Q2 retired (the E2E trigger is fixed). Q1 carried.
- 2026-10-16 — `security-suppressions-uniform-expiry`: **retired** (SA295 re-adjudicated all nine
  entries against the live source and staggered their expiries by review horizon: six
  raw-JavaScript seam emissions quarterly, two encoded-JSON seam entries semi-annually, the B105
  heuristic false positive annually).
