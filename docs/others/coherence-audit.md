# QuickScale — Deep Coherence Audit (cross-module conformance)

Audited: 2fd8637f (v89) · 2026-10-08 · working tree dirty (uncommitted `docs/others/arch-audit.md` and `tech-audit.md` only; read only for their hand-off sections) · repository public (github.com/Experto-AI/quickscale) · prompt: deep-coherence-audit v1 · passes: 3

> **How this pass was run.** The maintainer asked for a full review from scratch, not a
> continuation. Passes 1–3 below were made without reading the prior coherence audit (`f00ed460`)
> or the frozen inventory (`docs/planning/module-conventions-inventory.md`). Only after the third
> pass added nothing new were both read. Every prior ID is reconciled in §12, and the prior items
> are re-checked against this pass's tables. Where a finding breaks a clause that a prior ID marked
> resolved, the prior ID is **reopened** and the finding is filed under it. That keeps IDs stable
> instead of minting rivals.
>
> **Delta since the prior pass** (`f00ed460`, 2026-10-05): 61 non-split commits, 10 of which touch
> `quickscale_modules/`. All 10 are *convention-applying*: SA243–SA246, SA248, SA249 (rules 47–50)
> and `2fd8637f` (redaction i18n). None is *convention-breaking*. Every drift below predates the
> delta except where §12 says `regressed`. The `f00ed460..HEAD` revision range lists 409 commits
> because later merges carry older branch history, so the date-bounded count is the one used here.
> At `2fd8637f` the harness prints `All 43 covered module conventions pass (rules 1–20, 22–26,
> 28–29, 31–39, 42–45, 47, 48, 50)`. Delegated: 40, 41, 46, 49. Open: 21, 27, 30.

---

## 1. Orientation summary

**Populations.**

| Population | Size | Members |
|---|---|---|
| Modules (`quickscale_modules/*/module.yml`) | 12 | analytics, auth, backups, billing, blog, crm, forms, listings, notifications, orgs, social, storage |
| Manifest adapters (`adapter.py`) | 12 | all; 11 route through `build_generic_manifest_spec`, social hand-builds a `ResolverResult` |
| JSON API views (DRF) | 6 modules | billing, blog, crm, forms, listings, orgs (plus notifications' and billing's webhooks, and social's generated payload views) |
| Module-shipped Django pages | 7 modules | analytics, auth, billing, blog, crm, forms, listings, orgs |
| Management commands | 15 | backups 9, forms 2, orgs 4 (Correction: the prior pass counted 16; at both `f00ed460` and `2fd8637f` there are 15) |
| Error hierarchies (`<Module>Error`) | 10 | none in analytics or forms; backups re-exports core's `BackupError` |
| `AppConfig` capabilities | 13 names | collected by core's `collect_capabilities` or by orgs' own aggregator (§4.C) |
| Models with relations to shared models | 10 modules | analytics and storage have no models |
| **Outside the members, naming them** | — | core `contracts.module_options`, `contracts.module_catalog`, `apply/steps/env_sync`, `manifest/social_manifest`, `module_wiring`; CLI `_dependency_io`, `_finalize`, `_config`, `apply_command`; generator `settings/base.py.j2`; theme `showcase_react/src` hooks |

**Shared namespaces swept (§2b).** Settings and env-var names; app labels; URL namespaces, route
names, and **mount prefixes** (including third-party URLconfs mounted by two modules); template and
static folders; email-template keys; cache keys; advisory-lock keys; session keys; DRF throttle
scopes; `REST_FRAMEWORK` keys; constraint and index names (one PostgreSQL schema); reverse
accessors on `User`/`Organization`; analytics events; command names; **removal-obligation names**;
**`AppConfig` capability names**; logger names; and project route names a module depends on
(`home`).

**Declared conventions and their enforcement.**

| Rule source | Where an author looks | Check |
|---|---|---|
| decisions.md § Module Conventions, rules 1–50 | linked from module-extension.md § Building a Module | rule 40 harness (`scripts/check_module_conventions.py`), 43 rules with control cases; 21 review; 27 user-FK gate; 30 `collect_wiring` |
| decisions.md § Module Wiring Authority, § Module Manifest Architecture, § Module Derivation Schema | same | `check_module_app_declaration.py` (apps projection); manifest loader (derivation keys closed-world, **top-level keys open-world**) |
| decisions.md § JSON API Endpoint Base Contract, § Fail-Hard Principle | linked from rule 9 | CSRF pairing gate; harness rule 9 |
| module-extension.md § Building a Module (authoring checklist) | **the** page a new-module author reads | none; restates rules, plus claims (§7, gap 16) |
| frontend.md § Module frontend surfaces | from rule 31 | harness rule 31 (seam producer only) |

**Reference members.** crm, the most complete and most often cited in the rules, and orgs, the
foundation every tenant module builds on. **crm is not law:** it is on the 403 side of the
unauthenticated split and uses DRF's stock `SessionAuthentication` (Item 6).

**Activation (§3.1).** `active: A–H, J–P · quiet: I (no explicit timeouts or retries anywhere;
consistent), K (package-derived logger names everywhere; consistent), Q (English only; consistent)`.

**Scope.** All 12 modules and the code outside them that names, configures, or renders them.
Excluded: `quickscale_devtools`, which is developer tooling and not a member, and host projects
outside this repository.

**Coverage.**

- **Read in full for all 12:** `module.yml`, `adapter.py`, `apps.py`, `checks.py`,
  `exceptions.py`, the `services.py` `__all__` and its signatures.
- **AST census for all 12:** every `models.py` (pk, timestamps, `Meta`, relations, constraints),
  every view module (bases, DRF attributes), every management command, and the cross-module
  imports.
- **Per module:** pyproject tables (diffed key by key), README outlines, template and static
  trees, tests directories (tracked files only), and ticket-id counts.
- **Read where a finding pointed:** core `module_wiring`, `env_sync`, `module_options`,
  `entry_point`, `resolver`, `conventions`, and `option_validation`; CLI `_dependency_*`; the
  generated `settings/base.py.j2`; and the theme `useApi`, `useOrgs`, `useFormSchema`, and
  `usePublicSocialSurface` hooks.
- **Not read cell by cell:** module test bodies, migrations, and the theme pages beyond their API
  paths.

**Saturation.**

- **Pass 1** walked A–Q.
- **Pass 2** followed neighbours suggested by pass-1 findings: namespaces (sessions, host routes,
  URL prefixes), the theme API paths, dependency specs, and the tests-directory clause. It added
  8 items.
- **Pass 3** added one consequence of an existing item (analytics' template tags when switched
  off) and no new aspect or item, so the passes stop at **3**.

**"Add one more" probe (§3.6).** On paper, a new layer-3 module with an API, a webhook, one
email, a vendor secret, and a scheduled job, built from module-extension.md § Building a Module
and the rules alone. These decisions are left open, each filed under an item:

| Open decision | Item |
|---|---|
| Edit core? The checklist says never. Rule 37 requires `MODULE_CATALOG` and the count, `.env.example` blocks are core specs, and the email template and obligation name go into notifications and orgs | 8, 9 |
| Off switch: drop URLs in the adapter, or 404 in views? Drop the app? | 1 |
| Adapter hook: re-validate? coerce? project secrets how? | 4 |
| Middleware or a conditional app: manifest or literal? | 10 |
| API unauthenticated status: 401 subclass or DRF default? | 6 |
| Error base: `APIException` or `Exception`? | 5 |
| Throttle: `throttle_classes` or `throttle_scope`? | 12 |
| Paginator: write a fourth plain-list class? Page size from where? | 11 |
| Page templates: flat or nested under a module-named folder? | 22 |
| Scheduled job: trigger flag and default; `--json` or `--format`? | 16 |
| Dependency specs: which file, which dialect; declare `quickscale-core`? | 17 |
| Capability name and shape for a new cross-module need; which collector? | 15 |

---

## 2. Machine-readable index

```yaml
schema: coherence-audit/v1
audited: 2fd8637f
items:
  # ---- open: this pass (ranked per §6) ----
  - {id: module-enabled-switch, status: open, regressed: false, aspect: B, cost: [defect, ambiguity],
     members_diverging: [analytics, billing, notifications, backups, forms], population: modules(12),
     rule: "rule 1 (D3)", check: "none for the mechanism", closed_world: false, handoff: [tech],
     first_seen: 2026-09-26, last_verified: 2026-10-08}
  - {id: markdownx-shared-mount, status: open, aspect: A, cost: [collision, defect],
     members_diverging: [blog, listings], population: url-mount-prefixes(14 includes / 10 modules),
     rule: "rule 41 (two routes, one path)", check: none, closed_world: false, handoff: [tech],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: tenant-authorization, status: open, regressed: false, aspect: E, cost: [ambiguity],
     members_diverging: [billing], population: modules-with-pages-or-apis(9),
     rule: "rule 19; JSON API Endpoint Base Contract", check: "harness rule 19 (partial)",
     closed_world: false, handoff: [tech], first_seen: 2026-09-26, last_verified: 2026-10-08}
  - {id: option-schema-and-validation, status: open, regressed: false, aspect: B, cost: [ambiguity, tax],
     members_diverging: [analytics, auth, backups, billing, blog, crm, forms, listings, notifications, orgs, social, storage],
     population: adapters(12), rule: "rules 3, 12; Module Derivation Schema", check: "harness rules 3, 12 (settings reads only)",
     closed_world: false, handoff: [], first_seen: 2026-09-26, last_verified: 2026-10-08}
  - {id: unauthenticated-status-code, status: open, aspect: H, cost: [ambiguity, tax],
     members_diverging: [crm, forms], population: session-authenticated-apis(6), rule: none,
     check: none, closed_world: false, handoff: [], first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: module-error-http-mapping, status: open, aspect: D, cost: [ambiguity, tax],
     members_diverging: [billing, blog, listings, notifications], population: modules(12),
     rule: "rules 9, 10 (silent on the mapping)", check: none, closed_world: false, handoff: [tech],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: startup-checks-and-errors, status: open, regressed: false, aspect: B, cost: [ambiguity, tax],
     members_diverging: [analytics, backups, blog, forms, notifications], population: modules(12),
     rule: "rules 6, 10", check: "harness rule 10 (any *Error base passes)", closed_world: false,
     handoff: [], first_seen: 2026-09-26, last_verified: 2026-10-08}
  - {id: upward-name-references, status: open, regressed: true, aspect: C, cost: [ambiguity, tax],
     members_diverging: [orgs, notifications], population: cross-module-vocabularies(4),
     rule: "rule 34; rule 8 (email templates)", check: "harness rule 34 (labels/packages/models only)",
     closed_world: false, handoff: [arch], first_seen: 2026-09-26, last_verified: 2026-10-08}
  - {id: core-cli-module-knowledge, status: open, aspect: C, cost: [ambiguity, tax],
     members_diverging: [analytics, backups, billing, notifications, social, storage],
     population: modules(12), rule: "Module Wiring Authority; rule 12 ❌ (names contracts.module_options)",
     check: none, closed_world: false, handoff: [arch], first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: manifest-declared-surface, status: open, aspect: B, cost: [ambiguity, tax],
     members_diverging: [auth, orgs, notifications], population: manifests(12),
     rule: "Module Wiring Authority (no parsed-but-unread key; apps never a literal)",
     check: "app-declaration gate (apps projection); harness rule 7 (url_includes literals only)",
     closed_world: false, handoff: [], first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: http-api-shape, status: open, regressed: false, aspect: H, cost: [ambiguity, tax],
     members_diverging: [billing, social], population: json-api-modules(7), rule: "rule 9",
     check: "harness rule 9 (module source only)", closed_world: false, handoff: [tech],
     first_seen: 2026-09-26, last_verified: 2026-10-08}
  - {id: throttle-attachment, status: open, aspect: H, cost: [ambiguity, tax],
     members_diverging: [billing, blog, forms, listings], population: json-api-modules(6),
     rule: "rule 32 (names and rates only)", check: none, closed_world: false, handoff: [],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: optional-sender-guard, status: open, regressed: false, aspect: C, cost: [ambiguity, tax],
     members_diverging: [forms, orgs], population: cross-module-service-calls(4), rule: "rules 4, 39, 43",
     check: "harness rule 43", closed_world: false, handoff: [], first_seen: 2026-10-03, last_verified: 2026-10-08}
  - {id: module-dependency-direction, status: open, regressed: false, aspect: C, cost: [ambiguity, tax],
     members_diverging: [blog, crm, social], population: modules-importing-orgs(8), rule: "rule 4",
     check: "harness rule 4 (file-level surface only)", closed_world: false, handoff: [],
     first_seen: 2026-09-26, last_verified: 2026-10-08}
  - {id: capability-collection, status: open, aspect: D, cost: [ambiguity, tax],
     members_diverging: [orgs], population: appconfig-capabilities(13), rule: "rule 4 (one core helper)",
     check: none, closed_world: false, handoff: [arch], first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: command-flag-conventions, status: open, aspect: J, cost: [ambiguity, tax],
     members_diverging: [backups, forms, orgs], population: commands(15), rule: "rules 1, 17 (silent)",
     check: none, closed_world: false, handoff: [], first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: dependency-spec-sources, status: open, aspect: N, cost: [ambiguity, tax],
     members_diverging: [backups, storage, orgs], population: modules(12),
     rule: "Module Manifest Architecture (names only)", check: none, closed_world: false, handoff: [],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: secret-env-var-names, status: open, regressed: false, aspect: A, cost: [ambiguity],
     members_diverging: [backups], population: vendor-credential-options(5 modules), rule: "rule 1",
     check: "harness rule 1 (suffix only)", closed_world: false, handoff: [], first_seen: 2026-09-26,
     last_verified: 2026-10-08}
  - {id: session-and-host-names, status: open, aspect: A, cost: [ambiguity],
     members_diverging: [orgs, auth], population: shared-namespaces, rule: "rule 33", check: none,
     closed_world: false, handoff: [], first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: model-basics, status: open, regressed: false, aspect: G, cost: [tax, ambiguity],
     members_diverging: [blog, listings, auth, backups, notifications, orgs, social], population: models(10 modules),
     rule: "rule 14", check: "harness rule 14 (gettext, str, ordering, related_name)", closed_world: false,
     handoff: [], first_seen: 2026-09-26, last_verified: 2026-10-08}
  - {id: template-folder-depth, status: open, aspect: L, cost: [tax],
     members_diverging: [auth, billing, blog, crm, forms, listings], population: modules-with-page-templates(8),
     rule: "rule 8 (base only)", check: none, closed_world: false, handoff: [], first_seen: 2026-10-08,
     last_verified: 2026-10-08}
  - {id: test-file-names, status: open, regressed: false, aspect: M, cost: [tax],
     members_diverging: [auth, backups, billing, forms, listings, orgs], population: modules(12),
     rule: "rule 29 (second clause)", check: "harness rule 29 (test_*.py only)", closed_world: false,
     handoff: [], first_seen: 2026-09-26, last_verified: 2026-10-08}
  - {id: ticket-ids-in-shipped-source, status: open, aspect: O, cost: [tax],
     members_diverging: [auth, backups, billing, blog, crm, forms, listings, orgs, social, storage],
     population: modules(12), rule: "rule 29 (tests only)", check: none, closed_world: false,
     handoff: [], first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: constraint-purpose-tokens, status: open, aspect: A, cost: [tax],
     members_diverging: [crm, forms, orgs, notifications], population: constraint-names(31),
     rule: "rule 25 (prefix only)", check: "harness rule 25", closed_world: false, handoff: [],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: mount-path-copies, status: open, regressed: false, aspect: P, cost: [ambiguity, tax],
     members_diverging: [orgs, billing, forms, social], population: theme-module-api-clients(5),
     rule: "rule 41 (no literal module path in theme templates)", check: "harness rules 7, 31, 37 (seam producer)",
     closed_world: false, handoff: [], first_seen: 2026-10-03, last_verified: 2026-10-08}
  # ---- resolved: re-verified by the harness run at 2fd8637f (43 rules pass); see §12 ----
  # write-effects-on-commit, settings-snapshot-readers, org-role-check-copies, mypy-overrides-unread,
  # split-facade-conventions, theme-module-presence, module-lists-outside-members, shared-setting-writes,
  # throttle-scopes-and-rates, namespace-prefix-principle, secret-resolution-path, type-check-config,
  # readme-content-accuracy, manifest-dependency-spec, settings-names, settings-readers-and-defaults,
  # cross-module-settings-reads, identity-stem, url-mounts-and-names, templates-static-tags,
  # package-files, required-tests, readme-outline, model-choices, tenant-model-base, package-root-init,
  # signals-vs-receivers, command-behavior, package-tooling, email-sender, analytics-event-ownership, service-surface,
  # current-time-call, cache-key-stem, constraint-index-names, inbound-webhooks, user-fk-on-delete,
  # py-typed, semantic-personal-data-central-pin, anonymize-redaction-helper-copies,
  # anonymize-replacement-values, personal-data-inventory-ownership, anonymize-executor-naming
```

---

## 3. Summary table

**Counts (open):** defect 2 · collision 1 (also counted under defect) · ambiguity 17 · tax 5 ·
**total 25**. 12 of the 25 are prior IDs reopened, and one of those (`upward-name-references`)
is flagged `regressed`. The other 13 are new. One new item, `markdownx-shared-mount`, recreates a
state the frozen inventory had warned against (§12). Resolved prior IDs still holding: 43 of 55.

| # | ID | Aspect | Cost | Diverging / population | Status |
|---|---|---|---|---|---|
| 1 | `module-enabled-switch` | B | defect, ambiguity | 5 / 12 modules (+ core `env_sync`) | open (reopened) |
| 2 | `markdownx-shared-mount` | A | collision, defect | 2 / 10 mounting modules | open (new) |
| 3 | `tenant-authorization` | E | ambiguity | 1 / 9 | open (reopened) |
| 4 | `option-schema-and-validation` | B | ambiguity, tax | 12 / 12 adapters | open (reopened) |
| 5 | `module-error-http-mapping` | D | ambiguity, tax | 4 / 12 (5 variants) | open |
| 6 | `unauthenticated-status-code` | H | ambiguity, tax | 2 / 6 (4 duplicated classes on the other side) | open |
| 7 | `startup-checks-and-errors` | B | ambiguity, tax | 5 / 12 | open (reopened) |
| 8 | `upward-name-references` | C | ambiguity, tax | 2 owners / 4 vocabularies | open (reopened, regressed) |
| 9 | `core-cli-module-knowledge` | C | ambiguity, tax | 6 / 12 named in core or CLI | open |
| 10 | `manifest-declared-surface` | B | ambiguity, tax | 3 / 12 (+4 key-presence) | open |
| 11 | `http-api-shape` | H | ambiguity, tax | 2 / 7 | open (reopened) |
| 12 | `throttle-attachment` | H | ambiguity, tax | 4 / 6 | open |
| 13 | `optional-sender-guard` | C | ambiguity, tax | 2 / 4 call edges | open (reopened) |
| 14 | `module-dependency-direction` | C | ambiguity, tax | 3 / 8 | open (reopened) |
| 15 | `capability-collection` | D | ambiguity, tax | 1 owner / 13 names | open |
| 16 | `command-flag-conventions` | J | ambiguity, tax | 3 / 3 command-shipping modules | open |
| 17 | `dependency-spec-sources` | N | ambiguity, tax | 3 / 12 | open |
| 18 | `mount-path-copies` | P | ambiguity, tax | 4 / 5 theme API clients | open (reopened) |
| 19 | `secret-env-var-names` | A | ambiguity | 1 / 5 | open (reopened) |
| 20 | `session-and-host-names` | A | ambiguity | 2 | open |
| 21 | `model-basics` | G | tax, ambiguity | 7 / 10 | open (reopened) |
| 22 | `template-folder-depth` | L | tax | 6 / 8 | open |
| 23 | `test-file-names` | M | tax | 6 / 12 | open (reopened) |
| 24 | `ticket-ids-in-shipped-source` | O | tax | 10 / 12 | open |
| 25 | `constraint-purpose-tokens` | A | tax | 4 / 9 | open |

---

## 4. Aspect sections

### A. Identity and shared namespaces

| Namespace | Style → members | Notes |
|---|---|---|
| App label | `quickscale_<module>` → 12 | ✓ |
| URL namespace (`app_name`) | `quickscale_<module>` → 9 (all with a `urls.py`); none → backups, social, storage (no URLconf of their own) | ✓ |
| Mount prefix (`url_includes`) | `<module>/` → analytics, billing, blog, crm, forms, listings, notifications, orgs (8) · `accounts/` → auth · `_quickscale/social/` → social (rule 41 exception) · **`markdownx/` → blog *and* listings, two different URLconfs** | Item 2 |
| Un-namespaced route names | `markdownx_upload`, `markdownx_markdownify` → registered by blog **and** listings | Item 2 |
| Project route names a module depends on | `home` → auth (`reverse_lazy("home")`) · literal `/accounts/profile/`, `/` redirects → auth adapter | Item 20 |
| Template folder | `quickscale_<module>/` → 10 · `account/` (allauth) → auth · `admin/quickscale_backups/` → backups | depth: Item 22 |
| Email-template keys | `notifications.<purpose>` → all 3 keys live in notifications (`generic`, `forms_submission`, `org_invitation`) | Item 8 |
| Cache keys | `quickscale_social:links`, `quickscale_social:embeds` → social | ✓ |
| Advisory-lock keys | `quickscale_billing:subscription:<pk>`, `quickscale_billing:webhook-event:<id>` → billing | ✓ |
| Session keys | `quickscale_modules_orgs.active_org_id`, `…debug_as_org_id` → orgs (package stem; namespace absent from rule 2's table) | Item 20 |
| Throttle scopes | `quickscale_billing_checkout`, `_portal`, `quickscale_blog_api`, `quickscale_forms_submit` | ✓ (attachment: Item 12) |
| Removal-obligation names | `<module>-personal-data` → auth, billing, blog (declared by the module, **defined in orgs**) · `billing-provider-state` · unstemmed `owned-tenant-rows`, `owned-personal-data`, `purge-tombstone` → orgs · `social-cache-state` → **declared by orgs** | Item 8 |
| Capability names (`AppConfig` attributes) | unstemmed by design; 13 names, no list | Item 15 |
| Env-var defaults for vendor secrets | vendor name → analytics (`POSTHOG_*`), billing (`STRIPE_*`), notifications (`RESEND_API_KEY`), storage (`AWS_*`) · `QUICKSCALE_BACKUPS_REMOTE_*` → backups | Item 19 |
| Constraint names | `quickscale_<module>_<model>_<purpose>` → 31 names, 9 modules; purpose tokens vary | Item 25 |
| Index names | `qs_<module>_<model>_<field>_idx` → blog 3, listings 3 | ✓ |
| Logger names | package-derived (`__name__`, or the facade's channel per rule 46) → all 8 modules that log | ✓ |

*Already consistent (keep):* labels, URL namespaces, the settings prefix (rule 1, harness), cache
and lock keys, throttle scopes, index names, logger names, and reverse accessors on
`User`/`Organization` (`quickscale_<module>_<name>`, harness rule 14).

*Drift:* Items 2, 8, 15, 19, 20, 22, 25.

### B. Configuration (manifests, adapters, startup checks, the off switch)

**Manifest shape** (all 12 read):

| Aspect | Value → members |
|---|---|
| Top-level keys beyond the common set | `retired_options` → 9 · `contract_vintage` → backups, billing, orgs, social · `managed_files` → social · **`middleware:` and `settings:` → orgs (read by nothing)** |
| `required_modules` key | present → 9 · **absent** → backups, notifications, storage (`dependencies` is always present by rule 12; analytics gained `[orgs]` in SA252) |
| `contract_vintage.id` | present → billing, orgs · absent → backups, social |
| Option fields | `type`, `default`, `description`, `validation` (+`django_setting` on mutable) → all 86 options ✓ |
| URL-valued options | `url` normalization + full pattern → analytics `posthog_host` · `strip` only, no check → storage `media_url`, `public_base_url`, `endpoint_url`; backups `remote_endpoint_url` |
| Normalization on a non-string | `strip` on the integer `per_page` → listings |
| `pattern` on an integer | `webhook_ttl_seconds` (`'^\d+$'` beside `min`) → notifications |
| Version stamps in descriptions | `v0.80.0` → analytics `provider`; `v0.79.0` → social (2 options) |

**Adapter post-hooks** (all 12 read):

| Duty | Variant → members |
|---|---|
| Off branch (`enabled: false`) | drop `apps` and URLs (settings only) → **analytics** · drop URLs (+`spa_routes`) → auth, crm, forms, orgs, social · drop URLs but keep the markdownx editor → blog, listings · **no handling** (URLs stay; views 404 at run time) → billing, notifications · nothing to drop → backups, storage |
| Re-validate options in the hook | `validate_module_options(...)` → auth, backups, orgs, storage (4) · not → 8. Core's generic resolver "validates" against `derivation` rule lists the loader now refuses, so that step checks nothing (`resolver.py` step 5) |
| Hand type coercions (`bool()`, `int()`, `str()`, `.strip().lower()`) | some settings → all 12, each a different subset (orgs only re-normalizes `mode`). billing and crm call them "legacy", and backups, billing, crm, and storage say "the declarative resolver cannot express" them, although `coerce_int`/`coerce_bool`/`strip`/`lowercase` are rule 12 kinds |
| Re-project option settings in code that `django_setting` already projects | notifications (11 of 12 options), storage (11 of 12), social (7 of 8) |
| Option-value checks in code | non-empty provider/env-var/host → analytics (manifest allows blank) · non-empty rate → blog (manifest pattern already refuses blank) |
| Defaults written in code | social (`.get("layout_variant", "list")`, `300`, `24`, `12`) · notifications (`resolved.get("enabled", True)`) |
| Secret projection `__QS_ENV__:<name>` | blank-guarded → `""`: billing, notifications · omitted when blank: storage · **unguarded** (`"__QS_ENV__:" + name`): analytics, safe only because its own check refuses blank first. Core's renderer leaves `'__QS_ENV__:'` in place as a literal string when the name is blank |
| Literals the manifest could carry | middleware → auth (`AccountMiddleware`), orgs (`TenantMiddleware`) · app → notifications (`anymail`, inserted conditionally) · Django settings → auth (`LOGIN_REDIRECT_URL="/accounts/profile/"` …), blog and listings (`MARKDOWNX_*`), storage (`STORAGES`) |

**Startup checks** (`checks.py`, 10 of 12; none in auth or social):

| Aspect | Variant → members |
|---|---|
| Order in `ready()` | settings check, then module checks → analytics, backups, billing, notifications, orgs, storage · **module checks first** → blog |
| Guard against a missing declared setting | hand-listed `_DECLARED_SETTINGS`/`_RUNTIME_SETTINGS` (a third copy of the names) → analytics, billing, notifications · none → backups, blog |
| Retired setting names | `RETIRED_SETTINGS` dict in `checks.py` → blog, crm, forms, listings, orgs · retired *option* keys in `module.yml` `retired_options` → 9 (two homes for one concept) |

**Module off switch** (rule 1 / D3: installed, data untouched, public surfaces off, admin kept):

| Surface | Variant → members |
|---|---|
| Django app | kept → 11 · **removed** → analytics (its README tells projects to `{% load quickscale_analytics %}`) |
| URLs | unmounted by the adapter → auth, blog, crm, forms, listings, orgs, social · mounted, 404 from the view or service → billing (`BillingDisabledError`), notifications (`NotificationDisabledError`) |
| Scheduled jobs | refused only when `--trigger scheduled`, defaulting to `manual` on create and `scheduled` on prune → backups · refused unconditionally → forms (`anonymize_submissions`) |
| `.env.example` block | removed when off → analytics only · kept → billing, notifications, storage, backups |
| Capabilities | empty when off → billing (`organization_pricing_url_hooks`) · always declared → the rest |

*Already consistent (keep):* every option's four fields; `QUICKSCALE_<MODULE>_ENABLED` on all 12;
the generic settings check registered from `ready()` by all 12; `retired_options` messages naming
replacements; and the `MODULE_SETTINGS_SCHEMA` startup check.

*Drift:* Items 1, 4, 7, 10.

### C. Dependencies, layering, and vocabulary ownership

| Edge (importer → imported) | Surface used | Notes |
|---|---|---|
| auth → orgs (same layer) | `models`, `removal` | orgs ↛ auth ✓ (rule 5) |
| billing, blog, crm, forms, listings, social → orgs | published foundation files | **private names:** `current_org._restore_current_org_id` → crm, blog · `admin._explicit_org_from_request`, `_org_db_context`, `_persist_org_to_session`, `_resolve_active_org_id` → social |
| forms → analytics | `services` (lazy, `apps.is_installed` + `is_enabled`) | analytics is in forms' `required_modules`, so the guard is for a module that cannot be absent |
| forms → notifications | `services` (**eager** top-level import, `is_enabled`) | also required; no `is_installed` guard — two spellings inside forms |
| orgs → notifications (same layer) | `import_module(...)` + `is_installed` + `is_enabled` + `getattr(services, "send_notification", None)` | required by orgs; a missing function would silently disable invitations |

**Vocabulary ownership (§3.4).**

| Vocabulary | Defined by | Used by |
|---|---|---|
| Removal-obligation names | orgs `_removal_types` (`AUTH_`, `BILLING_`, `BLOG_PERSONAL_DATA`, `BILLING_PROVIDER_STATE`, `SOCIAL_CACHE_STATE`) | auth, billing, blog (layer 3) declare with orgs' constants; orgs declares `social-cache-state` itself |
| Email template keys and bodies | notifications `_templates.py` + `templates/quickscale_notifications/email/forms_submission_*`, `org_invitation_*` | forms (layer 3), orgs |
| Provider column on the tenant root | orgs `Organization.stripe_customer_id` + constraint `quickscale_orgs_organization_unique_nonempty_stripe_customer` | billing (declares it as `ExternalProviderField("quickscale_orgs.organization", …)`) |
| Option names, defaults, paths | core `contracts.module_options` (analytics provider/host, backups/notifications/storage env-var option names, billing env-var list, social paths) | core `env_sync`, CLI `apply_command`/`_finalize`/`_config`, analytics/storage/social adapters |
| Social's runtime behaviour | core `manifest/social_manifest.py` (509 lines: provider detection, URL normalization, generated views) | social adapter, the generated project |
| Storage's optional dependencies | CLI `_dependency_io._should_skip_manifest_dependency` (`if module_name != "storage"`, default `"local"`) | apply |

*Already consistent (keep):* rule 5's layer order for imports (no upward import anywhere); the
foundation-surface list for orgs; capabilities for upward needs (rule 4).

*Drift:* Items 8, 9, 13, 14.

### D. Public surface

| Aspect | Variant → members |
|---|---|
| `services.__all__` size | 2 (auth, forms) · 3 (listings, orgs) · 4 (blog, crm) · 9 (analytics) · 10 (social) · 11 (storage) · 21 (notifications) · 31 (billing) · 44 (backups). Size follows purpose (§9) |
| Capability hooks exported as public services | billing (`guard_organization_removal_provider_state`, `reconcile_*`, `subscription_provider_mutation_lock`, `account_deletion_user_reference_organization_ids`) |
| Code defaults exported | analytics (`ANALYTICS_POSTHOG_DEFAULT_HOST`, also defined in core `module_options`) |
| `<Module>Error` name | module name → auth, billing, blog, crm, listings, orgs, social, storage · singular → `NotificationError`, `BackupError` (defined in core `dr_engine.primitives`) · none → analytics, forms |
| Error base and HTTP mapping | base is DRF `APIException` → billing · base `Exception`, some subclasses mix in `APIException` → blog, listings, notifications · plain `Exception` → auth, crm, orgs, social, storage · core-owned → backups |
| Capability collection | `collect_capabilities(name)` in core → 7 names · orgs' own `getattr(app_config, ATTR, default)` → `removal_obligations`, `removal_boundary_implementations`, `removal_label_prefix` |
| Capability shapes | handler is the app config (`(self,)`) → `anonymize_handlers`, `account_deletion_handlers` · tuple of callables → `post_*_redirect_hooks`, `organization_*` hooks · records → `personal_data_declarations`, `removal_obligations` · plain attribute → `removal_label_prefix` |

*Already consistent (keep):* `is_enabled()` reading the switch directly in all 12; keyword-only
services (harness rule 23); `__all__` present in all 12.

*Drift:* Items 5, 7, 15.

### E. Authorization and trust

| Surface | Spelling → members |
|---|---|
| Org-role API | DRF `IsAuthenticated, HasOrgRole(...)` → blog, crm, forms, listings · `OrgApiBaseView.min_org_role` → orgs · **`AllowAny` + hand-written `_require_authenticated` / owner check** → billing |
| Org-role pages | `LoginRequiredMixin` + `OrgRoleMixin` → crm, orgs, analytics · public read mixins → blog, listings · `LoginRequiredMixin` → auth, billing dashboard |
| README lists minimum role per action (rule 19) | yes → blog, crm, forms, listings, orgs · **no** → billing (owner-only by default) |

*Already consistent (keep):* one role check (`user_has_org_role`, harness rule 44); no `is_staff` in
views except the listed paths.

*Drift:* Item 3.

### F. Write effects

| Effect | Module → mechanism |
|---|---|
| Email | forms, orgs → `transaction.on_commit(send)` |
| Analytics | forms → `on_commit`, guarded |
| Cache purge | social → `on_commit(cache.delete_many)` |
| Seeding | crm → receiver `on_commit(ensure_org_default_stages)` |
| File delete | blog anonymization → `on_commit` |

*Already consistent (keep):* every effect runs on commit (rule 21, review rule). No drift.

### G. Data model basics

| Aspect | Variant → members |
|---|---|
| Moment field names | `<event>_at` → all others · **`published_date`** → blog `Post`, listings `AbstractListing` |
| `Meta.verbose_name` | only where the default reads wrong → blog, billing, crm, forms · **redundant with the default** → auth (`User`/`Users`), backups (3 models), listings (`Listing`), notifications (4), orgs (`organization tombstone`), social (2) |
| Explicit `Meta.app_label` | set → backups, billing, crm, forms, notifications, orgs, social · inherited from `AppConfig.label` → auth, blog, listings |
| Ordering | present on every non-singleton ✓ (`-id` on billing `Subscription` and `PurchaseCheckout`, which lack `created_at`) |
| `on_delete` on `User` | `SET_NULL` + the 3 listed `CASCADE`s ✓ |
| Primary keys | `BigAutoField` · UUID only in orgs ✓ |

*Drift:* Items 21, 25.

### H. API and HTTP shape

| Aspect | Variant → members |
|---|---|
| Unauthenticated session call | **401** via a module `SessionAuthentication` subclass whose only change is `authenticate_header() → "Session"` → billing, blog, listings, orgs (4 copies, same docstring) · **403** via DRF's `SessionAuthentication` → crm, forms |
| Pagination | `PageNumberPagination` that returns a bare list, page size from `<THING>_PER_PAGE` → crm (contacts, deals), forms (submissions) · page size **literal `25`** → billing transactions · unpaginated lists → crm tags/companies/stages/notes, forms form list |
| Throttle attachment | `throttle_classes=[<Module>Throttle]` (client-IP keyed; replaces the default anon/user throttles) → blog, forms · `throttle_scope` on the default classes (user-keyed, stacks with anon/user) → billing · **no module throttle** on a write API → listings publish |
| JSON outside DRF | social's generated payload views (`quickscale_managed/social_views.py`, plain `JsonResponse` functions rendered by core) |
| Renderer/parser pinned | `JSONRenderer`/`JSONParser` → billing, listings, orgs · defaults → blog (parser only), crm, forms |
| Off answer | Django 404 (unmounted) → 7 · JSON 404 `not_found` → billing, notifications · `Http404` on an API toggle → crm, forms |
| Webhooks | DRF `APIView`, empty classes, service call → billing, notifications ✓ (rule 26) |

*Already consistent (keep):* the one error shape from core's handler; webhook shape; DRF for every
module-owned JSON endpoint.

*Drift:* Items 6, 11, 12.

### I. Outbound integrations — quiet

Stripe (`_stripe_client`), Resend (anymail backend), PostHog (`Posthog(sync_mode=False)`), and S3
(django-storages/boto3) all run on vendor defaults. No module sets timeouts or retries. That is
consistent, though worth a deliberate rule. No drift passes §0.

### J. Commands and jobs

| Aspect | Variant → members |
|---|---|
| Machine output | `--json` → backups (create, pin, record_verification, report, sync_media) · `--format human\|json` → orgs `check_tenant_isolation` |
| Scheduled provenance | `--trigger manual\|scheduled\|admin` (default `manual`) **and** `--scheduled` → backups create · `--trigger` (default **`scheduled`**) → backups prune · none → forms anonymize |
| Off refusal | by trigger → backups · unconditional `CommandError` → forms |
| Destructive confirmation | `--confirm <exact filename>` (required) → backups restore · none (only `--force` for reserved orgs) → orgs purge |

*Already consistent (keep):* `BaseCommand`, `CommandError`, `self.stdout`, and `--dry-run` on
destructive work (harness rule 17).

*Drift:* Item 16.

### K. Observability — quiet

Package-derived logger names everywhere. No structured fields anywhere. Module loggers reach only
the root handler (the generated `LOGGING` routes only the project package to the file handler).
Consistent; no drift passes §0.

### L. Files and package layout

| Aspect | Variant → members |
|---|---|
| Page templates | nested `quickscale_<m>/<m>/page.html` → blog, crm, forms, listings · nested `quickscale_auth/account/` → auth · flat `quickscale_<m>/page.html` → analytics, orgs · **mixed** (7 flat, 1 nested) → billing |
| Admin template overrides | Django's `admin/<label>/<model>/` → backups · module path `quickscale_orgs/admin/` → orgs |
| One file under two modules | `markdownx_urls.py` → blog, listings (identical apart from the module name) |
| Placeholder file in a non-empty tree | `static/quickscale_listings/.gitkeep` → listings |

*Already consistent (keep):* the closed file-name list (harness rule 28); `py.typed` in all 12.

*Drift:* Items 2, 22.

### M. Tests

| Aspect | Variant → members |
|---|---|
| Non-test files in `tests/` outside rule 29's list | `stripe_payloads.py`, `diag_setlocal.py` → billing · `wsgi.py` → backups · `views.py`, `models.py` → listings · `bypassed_boundary.py` → orgs |
| `tests/templates/` (not in rule 29's list) | auth, billing, forms, orgs |
| Required tests | all present per rule 11 ✓ |

(Correction: pass 1 listed `orgs/tests/sa208_project_app/` and `sa182_project_app/` as
ticket-named test apps. They are ignored `__pycache__` leftovers, not tracked files, so they are
not drift.)

*Drift:* Item 23.

### N. Tooling parity

| Aspect | Variant → members |
|---|---|
| `quickscale-core` declared as a dependency | `module.yml` + `pyproject.toml` (path, develop) → backups · undeclared, though all 12 import `quickscale_core.runtime` → 11 |
| Spec dialect | `module.yml` PEP 440, mostly unbounded (`djangorestframework>=3.17.2`) vs `pyproject` caret (`^3.17.2`) for the same package → 8 modules. Generated projects get the pyproject spec, except where the pyproject value is a table: then they get the `module.yml` spec → storage's optional `django-storages`/`boto3` arrive **unbounded**, while backups' same packages arrive `^` |
| Dev floors for shared packages | orgs' dev group `django-filter>=25.2`, `django-markdownx>=4.0.9`, `pillow>=12.2.0` vs the main floors `26.1`, `4.0.11`, `12.3.0` elsewhere |
| `--cov` target | package name → 10 · `src/` path → auth, blog (the authoring template shows the path form) |
| `pythonpath` | 6 variants, from `["."]` (auth, listings) to orgs' six sibling `src` trees |

*Already consistent (keep):* `[tool.pytest.ini_options]` with `--cov-fail-under=90` and
`[tool.ruff]` in all 12; type checking only in the root `mypy.ini` (harness rules 18, 36, 45).

*Drift:* Item 17.

### O. Documentation

| Aspect | Variant → members |
|---|---|
| README H2 outline | rule 11 order → 12 ✓ |
| Ticket ids in shipped source | orgs 102, backups 23, crm 19, forms 16, social 6, auth/billing/blog/storage 4 each, listings 1, analytics/notifications 0. Plus `(T2.3 Phase 3)` headers in 7 manifests |
| Role table under Public surface | Item 3 |

*Drift:* Items 3, 24.

### P. Frontend per module (showcase_react theme)

| Aspect | Variant → members |
|---|---|
| Module path source | seam `modulePaths` → crm pages · **literal API bases** → `useOrgs` (`/orgs/api/`, `/billing/api`), `useFormSchema` (`/forms/api/`), `usePublicSocialSurface` (`/_quickscale/social/…`) |
| HTTP helper | shared `apiRequest`/`useApiData` → orgs, crm, billing · raw `fetch` → forms schema, social |
| Error shape parsed | the one shape **and** the retired `errors` key ("for compatibility with projects that have not updated every module yet") → `useApi.ts` |

*Drift:* Item 18.

### Q. Locale — quiet

English only. No `gettext` and no `{% trans %}` in module templates; the only i18n is orgs' Django
admin `change_list` override, which loads `i18n` because admin does. Consistent.

---

## 5. Drift items (ranked: defect > collision > ambiguity > tax; then diverging members × churn)

Churn baseline: non-merge, non-subtree-split commits touching each module, 2025-10-08 → 2026-10-08.
orgs 183 · blog 133 · crm 133 · billing 120 · auth 109 · forms 107 · backups 95 · listings 95 ·
notifications 78 · social 74 · analytics 49 · storage 49. The SA215 conventions sweep inflates every
count about equally. **Reset point:** pre-1.0 clean break (decisions.md § Clean-Break Migration
History). Persisted renames (columns, constraints, template paths) ride the next release's
fresh `0001_initial` at no data cost. Public names (URLs, route names, template override paths,
API status codes) still need a release-notes line.

### Item 1: Off switch — five mechanisms for "installed but off"

- **ID:** `module-enabled-switch` (prior ID, reopened; not regressed — every variant predates the
  2026-10-02 resolution `97ac9187`)
- **Aspect / population:** B · the 12 modules, plus core's `.env.example` sync.
- **Table:** §4.B *Module off switch* (app kept 11 / removed 1; URLs unmounted 7 / runtime 404 2;
  jobs refused by trigger 1 / unconditionally 1; `.env.example` block removed 1 / kept 4;
  capability emptied 1 / always declared 11).
- **Drift:** rule 1 (D3) says off means "installed … public surfaces off … admin stays". Analytics
  goes further: its adapter returns `ModuleWiringSpec(settings=settings)`, which drops the app
  (`analytics/adapter.py:40`). billing and notifications go less far: they keep their URLs and
  answer 404 from inside the view. Scheduled jobs and `.env.example` blocks each follow a third rule.
- **Cost class:**
  - **defect** — analytics' README tells projects to `{% load quickscale_analytics %}` in
    server-rendered templates. Switching analytics off unregisters that tag library, so every
    such page raises `TemplateSyntaxError`. Analytics' `ready()` checks also stop running.
  - **ambiguity** — "off" means a different thing per module and per surface. A cron job calling
    a switched-off module exits non-zero every interval for forms, but only when tagged
    `scheduled` for backups.
- **Declared rule:** decisions.md rule 1 bullet 5 (D3), `decisions.md:523`.
- **Options:**
  - **A. Wiring drops public URLs; the app always stays.** analytics keeps its app and drops only
    its URL include. billing and notifications drop their public URLs too. Webhooks stay mounted
    and answer rule 26's 404, so a provider's retries get a clean refusal. Small change, two
    adapters.
  - **B. Runtime 404 everywhere** (URLs always mounted, every view checks `is_enabled()`). Simpler
    `apply`, but it touches ~40 views and moves the switch out of wiring.
  - **C. Keep the variants and document them per module.** Zero code, permanent tax.
- **Recommended rule (amend rule 1):**
  - ✅ Off keeps the module's apps, middleware, settings, admin, and template tags in every case.
    The adapter drops the module's public URL includes and `spa_routes`. A webhook endpoint stays
    mounted and answers 404 (rule 26).
  - ✅ A scheduled command refuses only a run marked scheduled. The scheduled trigger is the
    default for no command, and the refusal message names the switch.
  - ✅ The `.env.example` block of a switched-off module is kept (`respects_enabled_flag` is
    off for every spec).
  - ❌ An adapter off branch that returns fewer `apps` or `middleware` than its on branch.
- **Enforcement:** add to the harness a rule 1 clause that calls each adapter with
  `enabled: false` and `enabled: true` and asserts equal `apps`/`middleware`. That check is
  closed-world over all 12 adapters. Control: analytics' current adapter fails it.
- **Migration:** analytics, billing, notifications adapters; forms'
  `quickscale_forms_anonymize_submissions` gains `--trigger`; backups' `prune` default becomes
  `manual`; core `env_sync` analytics spec. Release-notes line: billing's and notifications'
  public pages become unmounted (Django 404) when off.
- **Confidence:** High (all 12 adapters and the env-sync specs read; the analytics tag library and
  README checked).
- **Hand-off:** tech (analytics `TemplateSyntaxError` when off).

### Item 2: Mount prefixes — blog and listings both mount `markdownx/`

- **ID:** `markdownx-shared-mount` (new)
- **Aspect / population:** A (URL mounts, route names, a third-party global setting) · the 14 URL
  includes of the 10 modules that mount URLs.
- **Table:** `markdownx/` → `quickscale_modules_blog.markdownx_urls` (blog) **and**
  `quickscale_modules_listings.markdownx_urls` (listings). Every other prefix → exactly one module.
  The two URLconfs are identical apart from the module name, and both register the un-namespaced
  names `markdownx_upload` and `markdownx_markdownify`. Only blog writes
  `MARKDOWNX_MEDIA_PATH = "blog/markdownx/"` (`blog/adapter.py:45`).
- **Drift:** `collect_wiring` dedupes identical `(prefix, target)` pairs only
  (`module_wiring.py:54`). With both modules installed, the project mounts two different URLconfs
  at one prefix, and blog's wins by sort order.
- **Cost class:**
  - **collision** — two routes resolve the same path, against rule 41's ❌.
  - **defect** — with both installed, listings' editor uploads land under `blog/markdownx/`.
    With listings alone they land under markdownx's default. So a listing image's storage path
    depends on whether blog is installed.
- **Declared rule:** rule 41 ❌ "Two routes that resolve the same path"; rule 30 (settings only)
  does not cover URL prefixes.
- **Options:**
  - **A. One owner.** Move the staff-guarded markdownx URLconf and the `MARKDOWNX_*` settings into
    one module both depend on (storage), or into core's runtime as a listed shared mount.
  - **B. Module-scoped mounts** (`blog/markdownx/`, `listings/markdownx/`), each widget pointed at
    its own URL. That needs widget configuration per model, because markdownx reads one global
    URL name.
  - **C. Keep both and make `apply` fail** when two modules mount the same prefix with different
    targets (detection only).
- **Recommended rule (amend rule 41):**
  - ✅ A URL prefix is mounted by exactly one module. A third-party URLconf that several modules
    need is mounted once, by the lowest-layer module that needs it, and its global settings are
    written by that module only.
  - ❌ Two modules' `url_includes` with the same prefix and different targets.
- **Enforcement:** `collect_url_wiring` raises on a prefix shared by two targets, as rule 30 does
  for settings. Closed-world, because it runs on every apply. Control: the current blog + listings
  manifests fail it. Also add a harness clause over the manifests.
- **Migration:** blog, listings (and storage under option A). Release notes: the markdownx upload
  path for listings changes.
- **Confidence:** High (both URLconfs diffed, merge code read).
- **Hand-off:** tech (upload path depends on the installed set).

### Item 3: Authorization — three ways to say "logged in", and billing's fourth

- **ID:** `tenant-authorization` (prior ID, reopened; not regressed: analytics' view dates from
  2026-06-16, billing's helpers from 2026-05-16)
- **Aspect / population:** E · the 9 modules with pages or APIs.
- **Table:** §4.E. API login spelled as DRF permission classes (blog, crm, forms, listings) /
  `OrgApiBaseView` (orgs) / `AllowAny` + `_require_authenticated()` (billing,
  `billing/views.py:84`). Pages guarded (auth, billing, crm, orgs, analytics) / public by design
  (blog, listings, billing pricing); analytics' dashboard adopted `LoginRequiredMixin` +
  `OrgRoleMixin(VIEWER)` in SA252. README role table present in 5 and absent in billing.
- **Drift:** rule 19 lists three spellings of "logged in", and billing uses a fourth that the JSON
  API contract separately sanctions ("AllowAny … the billing-module pattern"). Analytics'
  dashboard was a module-owned page with no login at all; SA252 gave it the mixin guard.
- **Cost class:**
  - **defect** — the unguarded page; resolved by SA252 (tech-audit S4).
  - **ambiguity** — two decision sections disagree on how an API says "logged in".
- **Declared rule:** rule 19 ✅ "Logged in is `LoginRequiredMixin`, `login_required`, or DRF
  `IsAuthenticated`", and its README duty. decisions.md § JSON API Endpoint Base Contract ✅
  "`AllowAny` is used when the view performs its own auth checks (the billing-module pattern)".
- **Options:**
  - **A.** billing adopts `IsAuthenticated` plus `HasOrgRole(OrgRole.OWNER)`, and the JSON API
    contract drops the AllowAny sentence. Analytics' dashboard got `LoginRequiredMixin` plus the
    viewer role (SA252).
  - **B.** Keep billing's helper and list it in rule 19 as a fourth spelling.
- **Recommended rule (amend rule 19; edit the JSON API contract):**
  - ✅ Every module page and API declares its guard on the view: DRF permission classes or
    `OrgApiBaseView.min_org_role` for APIs, a mixin for pages. Public views say so with
    `AllowAny` or a named public-read mixin.
  - ✅ Every module's README lists the minimum role per action.
  - ❌ `AllowAny` on a view that then checks `request.user` by hand.
  - ❌ A module page with no guard and no public-read declaration.
- **Enforcement:** harness rule 19 gains two closed-world clauses: every view class has an
  explicit guard, and an `AllowAny` view body must not read `request.user.is_authenticated`
  (control: billing). The README role table becomes a rule 38 clause.
- **Migration:** billing (~10 views); billing README; JSON API contract sentence. Analytics' one
  view landed with SA252.
- **Confidence:** High (all view classes enumerated by AST; READMEs grepped).
- **Hand-off:** tech (analytics' unguarded page landed with SA252; the billing half stays here).

### Item 4: Adapters — every module validates, coerces, and defaults its options differently

- **ID:** `option-schema-and-validation` (prior ID, reopened; not regressed, since the hooks
  predate `d0b148c9`)
- **Aspect / population:** B (where values are validated, coerced, defaulted) · the 12 adapters.
- **Table:** §4.B *Adapter post-hooks*, plus manifest URL options validated 1 way / unchecked
  2 ways.
- **Drift:** rule 12 makes the manifest the only place option values are checked and the only
  default. The adapters still:
  - re-validate (4), hand-coerce (12, each a different subset) and re-project settings that
    `django_setting` already projects (3);
  - check values the manifest allows (analytics refuses blank env-var names its own pattern
    accepts; `analytics/adapter.py:48`);
  - repeat defaults (social `adapter.py:201`; core `env_sync.py:129` repeats notifications'
    sender default);
  - project secrets three ways.

  Meanwhile core's generic resolver runs a "validate" step against derivation rule lists the
  loader refuses, so it validates nothing (`resolver.py:278`). That is why four adapters
  re-validate.
- **Cost class:**
  - **ambiguity** — the manifest says `posthog_host_env_var` is "Optional" and allows blank, yet
    apply refuses blank. Core's renderer turns a blank `__QS_ENV__:` into a literal string
    (`module_wiring.py:242` requires one or more characters), and only analytics' extra check
    keeps that latent.
  - **tax** — the next adapter author has twelve examples and four contradictory comments ("the
    declarative resolver cannot express" coercions that `coerce_int`/`coerce_bool` express).
- **Declared rule:** rule 12 ✅ "The manifest is the only place option values are checked" and
  "The option's `default` is the manifest's only default"; rule 3 ❌ "defaults written in code";
  § Module Derivation Schema "a module's adapter contributes only what the declarative resolver
  cannot express".
- **Options:**
  - **A. Make the generic path complete, then strip the hooks.**
    `build_generic_manifest_spec` calls `validate_module_options`, applies the option types
    (integer and boolean typing done once from `type:`), and projects `_ENV_VAR` options to their
    secret setting by suffix (blank → `""`). The hooks keep only real derivations: auth's login
    methods, storage's `STORAGES`, notifications' backend choice, billing's throttle rates.
  - **B. Keep the hooks and standardize them** with a shared helper per duty. Less churn, but the
    rule stays violated by design.
- **Recommended rule (amend rule 12 and § Module Derivation Schema):**
  - ✅ The generic manifest path validates every option, types it from its `type:`, and projects
    every `_ENV_VAR` option to `<SETTING>` without the suffix as an environment read. A blank
    name projects `""`.
  - ✅ An adapter post-hook only computes settings no single option maps to.
  - ❌ In `adapter.py`: `validate_module_options`, `bool()`/`int()`/`str()` of a projected
    option, `.get(<option>, <default>)`, or a value check.
  - ❌ A URL-valued option (`*_url`, `*_host`) without the `url` normalization and a pattern.
- **Enforcement:** a harness clause over `adapter.py` ASTs, closed-world on those call shapes
  (control: social's `.get("layout_variant", "list")`). A core unit test asserts the generic
  path rejects an invalid option without a hook. The renderer refuses a blank `__QS_ENV__:`
  marker.
- **Migration:** all 12 adapters shrink; storage and backups manifests gain URL checks; core
  resolver step 5 is deleted or rewired. No persisted names change.
- **Confidence:** High (all 12 adapters, resolver, renderer read).
- **Hand-off:** none (the blank-marker passthrough is latent; noted in §9 for tech).

### Item 5: Errors — five ways a module error becomes an HTTP status

- **ID:** `module-error-http-mapping` (new)
- **Aspect / population:** D (one error base; return vs raise) · the 12 modules.
- **Table:** §4.D *Error base and HTTP mapping*. Base is `APIException` → billing (`exceptions.py:31`).
  Base is `Exception` with some subclasses also `APIException` → blog, listings, notifications.
  Plain `Exception` → auth, crm, orgs, social, storage. Core-owned → backups. None → analytics,
  forms.
- **Drift:**
  - A billing service called from a host project's DRF view answers with the class's status.
    `InsufficientCreditsError` inherits **500** `billing_error` (`exceptions.py:42`).
  - A blog or listings validation error is plain and must be caught by the view.
  - A crm error is always a 500 unless caught.
- **Cost class:** **ambiguity** — rule 9 says module code raises "its `<Module>Error`, mapped by
  rule 10's `exceptions.py`", and nothing says how. **tax** — five examples.
- **Declared rule:** rules 9 and 10 (silent on the mapping).
- **Options:**
  - **A.** Errors stay framework-neutral (`Exception`). Core's exception handler maps a declared
    `status_code`/`default_code` attribute on any `<Module>Error`, so no module error inherits
    DRF.
  - **B.** Every `<Module>Error` is an `APIException` (billing's shape), so services carry HTTP
    semantics.
- **Recommended rule (amend rule 10):**
  - ✅ `<Module>Error` derives from `Exception` only. A subclass that API callers may see sets
    `status_code` and `default_code`, and core's handler renders it in rule 9's shape.
  - ✅ The base's default status is 500 only for configuration and programming errors.
  - ❌ `APIException` in a module's exception hierarchy.
- **Enforcement:** harness rule 10 checks bases (closed-world: only `Exception` or the module
  base). Control: billing's current `BillingError`.
- **Migration:** billing, blog, listings, notifications exception classes; core handler gains the
  attribute mapping. API bodies unchanged.
- **Confidence:** High.
- **Hand-off:** tech (`InsufficientCreditsError` → 500 for host callers; latent).

### Item 6: Unauthenticated status — 401 in four modules, 403 in two

- **ID:** `unauthenticated-status-code` (new)
- **Aspect / population:** H · the 6 modules with session-authenticated APIs.
- **Table:** 401 via a module subclass of `SessionAuthentication` whose only change is
  `authenticate_header() → "Session"` (same docstring in all four) → billing, blog, listings, orgs
  (`orgs/_api_views.py:51`). 403 via DRF's class → crm (`views.py:247`), forms (`views.py:155`).
- **Drift:** the same condition ("no session") gets two statuses, and the 401 side is four copies
  of one class.
- **Cost class:** **ambiguity** — the theme client and host callers must treat 401 and 403 alike.
  **tax** — the next API copies whichever module it read.
- **Declared rule:** none.
- **Options:**
  - **A.** One `SessionAuthentication` subclass in `quickscale_core.runtime` (401), set as
    `DEFAULT_AUTHENTICATION_CLASSES` in the generated `base.py`.
  - **B.** DRF default (403) everywhere and delete the four subclasses. This is a breaking status
    change for four APIs.
- **Recommended rule (add to rule 9):**
  - ✅ An unauthenticated call to a session API answers 401 through core's one session
    authentication class.
  - ❌ A module-defined `SessionAuthentication` subclass.
  - ❌ `authentication_classes` naming DRF's class directly on a non-webhook view.
- **Enforcement:** harness rule 9 clause, closed-world over module `authentication_classes`
  values (allowed: core's class, `[]` on webhooks). Control: crm.
- **Migration:** six modules; release-notes line for crm and forms (403 → 401).
- **Confidence:** High.
- **Hand-off:** none.

### Item 7: Startup checks and error names

- **ID:** `startup-checks-and-errors` (prior ID, reopened; not regressed)
- **Aspect / population:** B / D · 12 modules.
- **Table:**
  - `<Module>Error` named after the module → 8; singular → `NotificationError`, `BackupError`;
    none → analytics, forms.
  - Check order: settings check first → 6; module checks first → blog (`apps.py:148`).
  - Missing-setting guard: hand-listed names → analytics, billing, notifications; none → backups,
    blog.
  - Retired settings live in `checks.py` (5 modules), while retired options live in `module.yml`.
- **Drift:** each clause has 2–3 spellings. Blog's order means a missing
  `QUICKSCALE_BLOG_ENABLED` reports as an `AttributeError` inside `check_media_url` instead of
  the generic "run `quickscale apply`" message.
- **Cost class:** **ambiguity** (error names a generic check would key on), **tax**.
- **Declared rule:** rule 10 ("one `<Module>Error` base"); rule 6 (retired names).
- **Recommended rule (amend rules 6 and 10):**
  - ✅ The base is `<Module>Error` with the module name exactly as spelled: `NotificationsError`,
    `BackupsError`. A module that raises nothing ships no `exceptions.py`.
  - ✅ `register_module_settings_check` runs before `register_module_checks`.
  - ✅ Retired setting names live in `module.yml` beside `retired_options` (as `retired_settings`),
    read by core's settings check.
  - ❌ A module check that re-lists its declared settings.
- **Enforcement:** harness rule 10 checks the base name and the call order (closed-world).
  Control: blog's order, `NotificationError`. The manifest loader parses `retired_settings`.
- **Migration:** notifications and backups error renames (public names in `services.__all__`:
  release notes); blog `ready()`; 5 `checks.py` → manifests.
- **Confidence:** High.
- **Hand-off:** none.

### Item 8: Vocabulary — lower layers own higher layers' words

- **ID:** `upward-name-references` (prior ID, reopened; **regressed: true**. SA216(a)
  `3cffb168`, 2026-10-04, added `BLOG_PERSONAL_DATA`/`BILLING_*` to orgs after the rule 34
  resolution `2352acf1`, 2026-10-02. notifications' template keys predate it.)
- **Aspect / population:** C (vocabulary ownership) · the 4 cross-module vocabularies in §4.C.
- **Table:**
  - orgs `_removal_types.py:88–95` defines the obligation names of auth, billing, blog, and
    social, and declares `social-cache-state` itself.
  - notifications `_templates.py:47` and `templates/quickscale_notifications/email/` hold forms'
    and orgs' email keys and bodies.
  - orgs `models.py:44` carries billing's `stripe_customer_id` and its unique constraint.
- **Drift:** rule 34 forbids naming a higher-layer module. These names are not app labels,
  packages, or models, so the harness passes them. Rule 8 puts email templates under the
  sending module's folder; they live in notifications.
- **Cost class:**
  - **ambiguity** — "who owns `blog-personal-data`" has two answers. Obligation names follow
    three styles (`<module>-…`, unstemmed `owned-…`/`purge-…`, `social-…` declared by orgs). A
    project app's obligation called `owned-personal-data` fails startup as a duplicate.
  - **tax** — the next module that emails, or that anonymizes, must edit notifications or orgs
    (contradicting module-extension.md:542).
- **Declared rule:** rule 34 ❌; rule 8 ✅ email templates; rule 2/33 (shared namespaces must be
  listed — obligation names are not).
- **Options:**
  - **A.** Each module defines its own obligation name constant
    (`quickscale_<module>:<purpose>`). Each sender registers its email templates through a
    `notification_templates` capability with bodies under
    `templates/quickscale_<module>/email/`. Notifications keeps only `generic`.
  - **B.** Keep the lower-layer registries and list them as rule 34 exceptions.
  - (`stripe_customer_id` belongs to the architectural hand-off.)
- **Recommended rule (amend rule 34; add obligation names to rule 2's table):**
  - ✅ Removal-obligation names are `quickscale_<module>:<purpose>`, defined by the declaring
    module.
  - ✅ A sender's email templates and keys (`quickscale_<module>.<purpose>`) live in the sender
    and are declared through a capability.
  - ❌ A module's source naming another module in a string constant, a template key, or a
    template path.
- **Enforcement:** extend harness rule 34 from labels to string constants and template keys
  containing another module's name (closed-world list of module names from discovery). Control:
  orgs' `BLOG_PERSONAL_DATA`. Add a rule 33 detector for obligation-name stems.
- **Migration:** orgs, auth, billing, blog, social (obligation names — internal, no persisted
  data); notifications, forms, orgs (template keys are stored on `NotificationMessage.template_key`
  rows — clean break).
- **Confidence:** High.
- **Hand-off:** arch (lower-layer registries; `Organization.stripe_customer_id`).

### Item 9: Core and the CLI still hold per-module knowledge

- **ID:** `core-cli-module-knowledge` (new; the arch audit tracks the structural side as watchlist
  `core-holds-module-vocabulary`)
- **Aspect / population:** C · modules named by core or the CLI: analytics, backups, billing,
  notifications, social, storage (6 of 12).
- **Table:** §4.C rows 4–6:
  - `contracts/module_options.py:20–73` holds option names, defaults, and paths. Its
    `ANALYTICS_POSTHOG_EU_HOST`, `ANALYTICS_EVENT_PAGEVIEW`, and `ANALYTICS_PROVIDERS` are read by
    nothing outside `contracts`.
  - `env_sync.py:178` holds per-module specs with per-module flags and a code default.
  - `social_manifest.py` (509 lines) holds social's runtime and generated views.
  - The CLI's `_dependency_io.py:151` branches on `module_name != "storage"` with a default
    backend of `"local"`.
  - `module_catalog.MODULE_CATALOG` plus `AUTHORITATIVE_MODULE_COUNT` must be edited to add a
    module.
- **Drift:** six modules are partly defined outside themselves; six are not. module-extension.md
  says adding a module "requires no edit to `quickscale_core` or `quickscale_cli`" (`:542`), which
  is false four ways.
- **Cost class:** **ambiguity** — rule 12's ❌ names `contracts.module_options` as a forbidden
  home for "defaults … for a named module", yet it holds analytics' default host. **tax** — the
  "add one more" probe (§3.6) must edit core for `.env.example`, catalog, and count.
- **Declared rule:** § Module Wiring Authority ("Neither `quickscale_core` nor `quickscale_cli`
  may hold per-module wiring knowledge"); rule 12 ❌; rule 37 (allows the catalog and the
  env-example specs as listed exceptions).
- **Options:**
  - **A.** Derive the `.env.example` blocks from manifest `_ENV_VAR` options plus an optional
    `env_example:` manifest block (title, prose). Move option-name constants into their modules.
    Express storage's optional dependencies as a manifest `optional_dependencies: {when: …}`.
    Keep the catalog (rule 37).
  - **B.** Accept the exceptions and fix module-extension.md to list every core edit a new
    module needs.
- **Recommended rule (amend rule 37 and module-extension.md):**
  - ✅ Core and the CLI name a module only in rule 37's listed exceptions.
  - ✅ The authoring checklist states each core edit a new module needs.
  - ❌ A per-module constant, default, or `if module_name == "<module>"` branch in core or the
    CLI outside the listed exceptions.
- **Enforcement:** the rule 37 detector extends from module-name lists to string comparisons with
  a discovered module name and to constants prefixed `<MODULE>_` in `quickscale_core` and
  `quickscale_cli` (closed-world over discovery). Control: `_dependency_io.py:151`.
- **Migration:** core `contracts/module_options.py`, `env_sync.py`; CLI `_dependency_io.py`;
  manifests of analytics, backups, billing, notifications, storage. social's runtime is the arch
  hand-off.
- **Confidence:** High for the table. Medium on the dead-constant count (grepped across `src`,
  tests not checked).
- **Hand-off:** arch (watchlist `core-holds-module-vocabulary`).

### Item 10: Manifest surface — inert keys, and wiring written in Python

- **ID:** `manifest-declared-surface` (new)
- **Aspect / population:** B · the 12 manifests and adapters.
- **Table:**
  - orgs' top-level `middleware:` and `settings:` (`orgs/module.yml:37`, `:40`) are read by
    nothing: `load_manifest` ignores unknown top-level keys. The middleware they describe is
    written as a literal in orgs' adapter (`:56`), and the setting duplicates `mode`'s default.
  - auth writes `AccountMiddleware` as a literal (`auth/adapter.py:82`). The derivation schema
    accepts a `middleware` wiring field that no module uses.
  - notifications inserts the `anymail` app as a literal (`adapter.py:179`).
  - `required_modules` is absent in 3 manifests and `[]` in none (analytics gained `[orgs]` in
    SA252).
  - `contract_vintage.id` appears in 2 of 4.
- **Drift:** § Module Wiring Authority forbids "parsed-but-unread declarative surface" and apps
  "as a Python literal in the adapter". The harness checks literal `url_includes` only.
- **Cost class:** **ambiguity** — orgs' inert keys look authoritative. **tax** — middleware has
  two homes.
- **Declared rule:** § Module Wiring Authority ❌ bullets 3–4; rule 12 ✅ "`dependencies` is always
  present".
- **Recommended rule (amend § Module Wiring Authority):**
  - ✅ `apps` and `middleware` come only from `derivation.wiring_projections` (a conditional
    projection where they depend on an option, as `anymail` does).
  - ✅ `required_modules` and `dependencies` are always present.
  - ❌ A top-level manifest key the loader does not parse (the loader rejects it).
  - ❌ An `apps`/`middleware` literal in `adapter.py`.
- **Enforcement:** the loader becomes closed-world on top-level keys. Control: orgs' current file
  fails to load. Harness rule 7's literal detector extends to `apps` and `middleware`.
- **Migration:** orgs, auth, notifications manifests and adapters; 3 manifests gain
  `required_modules: []`.
- **Confidence:** High.
- **Hand-off:** none.

### Item 11: API list and body shape

- **ID:** `http-api-shape` (prior ID, reopened; not regressed)
- **Aspect / population:** H · the 7 modules serving JSON.
- **Table:**
  - billing's transaction list pages at a literal `25` (`billing/views.py:140`) with no
    `_PER_PAGE` option.
  - crm and forms read their `_PER_PAGE` settings.
  - The "plain list" paginator is written three times (crm, forms, billing). 6 list endpoints are
    unpaginated (crm tags, companies, stages, contact notes, deal notes; forms' form list), and
    the generated settings set no `DEFAULT_PAGINATION_CLASS`.
  - social's generated payload views are `JsonResponse` functions rendered by core (tech-audit
    lead).
- **Drift:** rule 9 ✅ "Lists page with `PageNumberPagination` sized by the module's
  `<THING>_PER_PAGE`" and ❌ "`JsonResponse` APIs". The harness reads module source, not
  core-rendered code.
- **Cost class:** **ambiguity**, **tax** (plus the tech defect on social's exception text).
- **Recommended rule (amend rule 9):**
  - ✅ One `PlainListPagination` in `quickscale_core.runtime`, sized by the module's
    `<THING>_PER_PAGE` setting through a `page_size_setting` attribute.
  - ✅ Every list endpoint paginates.
  - ✅ Generated project code that serves JSON follows rule 9 like module code.
  - ❌ A literal page size.
- **Enforcement:** harness rule 9 clause over `page_size =` literals and paginator classes outside
  core. The harness corpus extends to core's managed-file renderers' output (render once, then
  parse). Control: billing.
- **Migration:** billing gains `transactions_per_page`; crm, forms, billing drop their paginators;
  social's generated views become DRF (core renderer).
- **Confidence:** High.
- **Hand-off:** tech (`social-payload-echoes-exception-text`, already open there).

### Item 12: Throttles — two ways to attach a module's rate, one write API with none

- **ID:** `throttle-attachment` (new)
- **Aspect / population:** H · the 6 modules with module-owned JSON APIs.
- **Table:**
  - `throttle_classes=[<Module>Throttle]` (client-IP keyed; replaces the default anon/user
    throttles) → blog (`views.py:183`), forms.
  - `throttle_scope` on the default classes (user-keyed, stacks with anon/user) → billing.
  - No module throttle on its publish API → listings (`views.py:58`; tech-audit lead).
  - Default throttles only → crm, orgs.
- **Drift:** an authenticated blog member is throttled per client IP, while an authenticated
  billing user is throttled per user. Blog's and listings' sibling publish APIs differ.
- **Cost class:** **ambiguity** — rule 32 fixes the scope name and rate, not the identity or
  stacking. **tax**.
- **Recommended rule (amend rule 32):**
  - ✅ A module throttle is attached with `throttle_scope` only, keyed by user when authenticated
    and by client IP otherwise (core's one `ScopedRateThrottle` subclass, which uses the trusted
    proxy count).
  - ✅ Every write API that calls a vendor or creates published content has a scope.
  - ❌ `throttle_classes` on a non-webhook view.
- **Enforcement:** harness rule 32 clause (closed-world: `throttle_classes` only `[]` on
  webhooks). Control: blog.
- **Migration:** blog, forms (drop classes); listings gains `api_rate_limit`; core gains the
  throttle class.
- **Confidence:** High.
- **Hand-off:** none.

### Item 13: Required modules guarded as if optional

- **ID:** `optional-sender-guard` (prior ID, reopened; not regressed — orgs' `getattr` dates from
  2026-05-20)
- **Aspect / population:** C · the 4 cross-module service-call edges (forms→analytics,
  forms→notifications, orgs→notifications, billing→orgs).
- **Table:**
  - forms → analytics: in `required_modules`, yet guarded lazily by `apps.is_installed`
    (`forms/views.py:100`).
  - forms → notifications: required, imported eagerly with no installed guard (`_email.py:17`).
  - orgs → notifications: required, yet `import_module` + `is_installed` + `getattr(services,
    "send_notification", None)` (`orgs/views.py:113`).
- **Drift:** rule 4's guard is "when it is optional". Two modules guard modules they require, and
  forms uses both spellings. orgs' `getattr(…, None)` silently disables invitations if the
  function ever moves — a fail-hard violation in waiting. forms' `notify_submission` returns
  `"queued"` when notifications is off (`_email.py:53`).
- **Cost class:** **ambiguity** — is analytics optional for forms? **tax**.
- **Declared rule:** rule 4 table row 1; rule 39; rule 43; § Fail-Hard Principle.
- **Recommended rule (amend rule 43):**
  - ✅ A module in `required_modules` is imported directly and asked only `is_enabled()`.
  - ✅ A module not in `required_modules` is guarded by `apps.is_installed` and `is_enabled()`.
  - ❌ `getattr(<module services>, <name>, <default>)`.
  - ❌ An `is_installed` guard on a required module.
- **Enforcement:** harness rule 43 cross-checks each guard against `required_modules`
  (closed-world). Control: forms→analytics.
- **Migration:** forms (decide: drop analytics from `required_modules`, or drop the guard), orgs.
- **Confidence:** High.
- **Hand-off:** tech (forms' status string reports `"queued"` for a skipped email).

### Item 14: Private names imported across modules

- **ID:** `module-dependency-direction` (prior ID, reopened; not regressed — crm 2026-07-12)
- **Aspect / population:** C · the 8 modules that import orgs.
- **Table:** `current_org._restore_current_org_id` → crm (`services.py:85`), blog
  (`views.py:142`). `admin._explicit_org_from_request`, `_org_db_context`,
  `_persist_org_to_session`, `_resolve_active_org_id` → social (`admin.py:35–38`, "re-export for
  test suite").
- **Drift:** rule 4 allows a foundation's published files. The harness checks the file, not the
  name. social re-exports orgs' private helpers so its tests can patch them, which is also against
  § Split-Facade Seams ("a test's seam is the module that defines the name").
- **Cost class:** **ambiguity** (is `_name` in a published file public?), **tax**.
- **Recommended rule (amend rule 4):**
  - ✅ A foundation's published surface is the public names in its listed files.
  - ❌ Importing a `_`-prefixed name from another module.
  - ❌ Re-exporting another module's private name.
- **Enforcement:** harness rule 4 clause on imported names. Control: crm.
- **Migration:** orgs publishes a context manager (`org_scope_restored` or similar) for crm and
  blog. social's tests patch `quickscale_modules_orgs.admin` directly.
- **Confidence:** High.
- **Hand-off:** none.

### Item 15: Capabilities — two collectors and no list of names

- **ID:** `capability-collection` (new)
- **Aspect / population:** D · the 13 capability names declared on `AppConfig`s.
- **Table:**
  - Core `collect_capabilities` collects `account_deletion_handlers`, `anonymize_handlers`,
    `organization_cache_keys`, `organization_pricing_url_hooks`, `personal_data_declarations`,
    `post_login_redirect_hooks`, and `post_signup_redirect_hooks`.
  - orgs collects by `getattr(app_config, ATTR, default)` (`_removal_declarations.py:191`) for
    `removal_obligations`, `removal_boundary_implementations`, and `removal_label_prefix`.
  - Call sites spell the name as a literal string (6) or a module constant (3).
  - Suffix styles: `*_hooks`, `*_handlers`, `*_declarations`, bare nouns. Shapes: `(self,)`,
    callables, records, attribute.
- **Drift:** rule 4 says one core helper collects capabilities. The names are an open set, so a
  misspelled declaration is never collected and nothing fails. W006 catches only a missing
  anonymization executor.
- **Cost class:** **ambiguity**, **tax**.
- **Recommended rule (amend rule 4):**
  - ✅ Capability names are listed in core (`CAPABILITIES`), each with its shape.
  - ✅ `collect_capabilities` accepts only a listed name.
  - ✅ A startup check warns on an `AppConfig` attribute that looks like a capability but is not
    listed.
  - ❌ A collector other than `collect_capabilities`.
- **Enforcement:** core unit test plus harness clause (closed-world: every `collect_capabilities`
  argument is a listed constant). Control: orgs' `getattr` collector.
- **Migration:** orgs `_removal_declarations`, `_purge_plan`; auth `_anonymize_boundary`.
- **Confidence:** Medium. The list of 13 names comes from greps of collectors and `AppConfig`s;
  some host-side names may exist in tests.
- **Hand-off:** arch (two collection mechanisms).

### Item 16: Command flags — machine output, scheduled provenance, confirmation

- **ID:** `command-flag-conventions` (new)
- **Aspect / population:** J · the 15 commands (backups 9, forms 2, orgs 4).
- **Table:** §4.J. `--json` (5) vs `--format human|json` (1, `check_tenant_isolation.py:72`).
  Trigger defaults `manual` (create) vs `scheduled` (prune, `prune.py:18`). Off refusal by trigger
  (backups) vs unconditional (forms, `anonymize_submissions.py:36`). `--confirm <filename>`
  (restore) vs none (purge).
- **Cost class:** **ambiguity** (an operator's cron and scripts cannot assume one convention),
  **tax**.
- **Recommended rule (amend rule 17):**
  - ✅ Machine-readable output is `--json`.
  - ✅ A command an operator schedules takes `--trigger {manual,scheduled}` defaulting to
    `manual`, and only `scheduled` runs refuse while the module is off.
  - ✅ A command that deletes another tenant's or the whole database's data requires
    `--confirm <identifier>`.
- **Enforcement:** harness rule 17 clauses over `add_argument` calls (closed-world flag
  vocabulary). Control: orgs' `--format`.
- **Migration:** orgs (`--format` → `--json`; purge `--confirm <slug>`), backups prune default,
  forms anonymize. Release notes for operator scripts.
- **Confidence:** High.
- **Hand-off:** none.

### Item 17: Dependency specs come from two files in two dialects

- **ID:** `dependency-spec-sources` (new)
- **Aspect / population:** N · the 12 modules.
- **Table:** §4.N. `quickscale-core` declared by backups only (`module.yml:127`). PEP 440
  unbounded in `module.yml` vs caret in `pyproject`. Storage's optional deps
  (`storage/pyproject.toml:18`) reach generated projects through the unbounded `module.yml` spec.
  orgs' dev floors are lower. `--cov` targets and `pythonpath` vary.
- **Cost class:** **ambiguity** — a storage-only project gets `django-storages`/`boto3` with no
  upper bound, while a backups project gets `^`. **tax**.
- **Declared rule:** § Module Manifest Architecture (names must match; specs live in
  `pyproject`).
- **Recommended rule (amend § Module Manifest Architecture):**
  - ✅ `module.yml` `dependencies` lists names only.
  - ✅ The specs live in `pyproject.toml`, optional ones as `{version, optional}`, and `apply`
    always takes the spec from there.
  - ✅ Every module declares `quickscale-core` (lockstep).
  - ✅ `--cov` names the package.
- **Enforcement:** harness rule 39 checks that `module.yml` dependency entries carry no specifier
  (closed-world), and rule 18 checks `quickscale-core` and the `--cov` form. Control: backups.
- **Migration:** 12 manifests, 11 pyprojects, CLI `_resolve_declared_dependency_value`.
- **Confidence:** High.
- **Hand-off:** none.

### Item 18: Theme API paths written as literals

- **ID:** `mount-path-copies` (prior ID, reopened; not regressed — the hooks predate SA235)
- **Aspect / population:** P · the 5 theme hooks that call module APIs.
- **Table:** §4.P. `/orgs/api/`, `/billing/api` (`useOrgs.ts:100–105`), `/forms/api/`,
  `/_quickscale/social/…` are literals, while pages use the seam's `modulePaths`. `useApi.ts:52`
  still parses the retired `errors` key.
- **Drift:** rule 41 ❌ "A module path written as a literal in … theme templates". The harness
  checks only the seam producer.
- **Cost class:** **ambiguity** (two path sources), **tax**.
- **Recommended rule (amend rule 41):**
  - ✅ The seam carries each installed module's API base (`moduleApiPaths`), resolved from URL
    names, and theme hooks read it.
  - ❌ A `/<mount>/api` literal in the theme.
  - ❌ Parsing a retired error shape.
- **Enforcement:** a theme lint (closed-world regex over `src/**/*.ts*` for module mount
  prefixes). Control: `useOrgs.ts`.
- **Migration:** theme (user-owned U3 for existing projects: release-notes step).
- **Confidence:** Medium (4 hooks read; the 36 other files that name modules were not read).
- **Hand-off:** none.

### Item 19 (compact): `secret-env-var-names`

- **Aspect:** A.
- **Table:** vendor default env-var names → analytics, billing, notifications, storage ·
  `QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID`/`_SECRET_ACCESS_KEY` → backups (S3 credentials, like
  storage's).
- **Rule:** amend rule 1 to list backups' separate private-remote credentials as an exception,
  with the reason (they must not be storage's media credentials).
- **Check:** harness rule 1 compares `_ENV_VAR` defaults to a vendor-name table. Closed-world over
  the exceptions list.
- **Confidence:** High. Reopened, not regressed.

### Item 20 (compact): `session-and-host-names`

- **Aspect:** A.
- **Table:** session keys `quickscale_modules_orgs.active_org_id`, `…debug_as_org_id`, and the
  pending-invitation key (`orgs/_constants.py:3–7`) use the package stem, in a namespace not
  listed in rule 2's table. auth depends on the project route name `home` (`auth/views.py:105`)
  and writes literal redirect paths.
- **Rule:** add session keys to rule 2's table as `quickscale_<module>:<name>`. Project route
  names a module depends on (`home`) are listed as a host contract in module-extension.md.
- **Check:** harness rule 33 clause for `*SESSION_KEY` constants.
- **Confidence:** High.

### Item 21: Model basics — `published_date`, redundant `verbose_name`, explicit `app_label`

- **ID:** `model-basics` (prior ID, reopened; not regressed — `published_date` dates from v0.66.0)
- **Aspect / population:** G · the 10 modules with models.
- **Table:** §4.G (`blog/models.py:358`, `listings/models.py:56`; `verbose_name` redundant in 6
  modules; `Meta.app_label` explicit in 7).
- **Cost class:** **tax**. **ambiguity** — rule 14's `<event>_at` and "set `verbose_name` only
  where Django's default reads wrong" are written but unchecked.
- **Recommended rule:** rule 14 as written, plus ❌ `Meta.app_label` in a module (the `AppConfig`
  label is the one source).
- **Enforcement:** harness rule 14 clauses: `DateTimeField` names end `_at`; `verbose_name` equal
  to the computed default is refused; no `app_label` in `Meta`. Control: blog `Post`.
- **Migration:** blog, listings (`published_date` → `published_at` in models, serializers, theme,
  API — release notes); six modules drop redundant labels. Rides the clean-break `0001`.
- **Confidence:** High.

### Item 22: Template sub-folder depth

- **ID:** `template-folder-depth` (new)
- **Aspect / population:** L · the 8 modules with page templates.
- **Table:** §4.L. Nested `quickscale_<m>/<m>/` → blog, crm, forms, listings; nested `account/`
  → auth; flat → analytics, orgs; mixed (7 flat, 1 nested) → billing. Admin overrides via
  Django's path → backups; via a module path → orgs.
- **Cost class:** **tax** — projects override templates by path, so every rename is a
  release-notes duty (a one-way door after 1.0).
- **Recommended rule (amend rule 8):**
  - ✅ Pages are flat under `templates/quickscale_<module>/` (auth's allauth-required `account/`
    excepted).
  - ✅ Admin overrides use Django's `admin/<label>/<model>/` path.
- **Enforcement:** harness rule 8 clause: no sub-folder named after the module. Control: blog.
- **Migration:** 6 modules move templates; release notes list old → new paths.
- **Confidence:** High.

### Item 23: `tests/` holds files rule 29 does not allow

- **ID:** `test-file-names` (prior ID, reopened; regressed not determined per file)
- **Aspect / population:** M · the 12 modules' `tests/`.
- **Table:** §4.M: 6 tracked files in 4 modules, and `tests/templates/` in 4 modules.
- **Drift:** rule 29's second sentence lists the allowed non-test files. The harness checks
  `test_*.py` only.
- **Cost class:** **tax**.
- **Recommended rule:** rule 29 as written, plus ✅ `templates/` for test-only templates.
  Fixture modules are `_`-prefixed.
- **Enforcement:** harness rule 29 clause, closed-world over `tests/` entries. Control:
  `billing/tests/diag_setlocal.py`.
- **Confidence:** High (tracked files only; see the §4.M correction).

### Item 24 (compact): `ticket-ids-in-shipped-source`

- **Aspect:** O.
- **Table:** 183 ticket ids in module `src` (orgs 102), `(T2.3 Phase 3)` headers in 7 manifests,
  version stamps in 3 option descriptions.
- **Rule:** extend rule 29's no-ticket clause to shipped module source and manifests. Comments
  say what code protects, not which ticket wrote it.
- **Check:** harness clause reusing `TICKET_IN_TEST` over `src/**/*.py` and `module.yml`
  (closed-world).
- **Confidence:** High (regex count).

### Item 25 (compact): `constraint-purpose-tokens`

- **Aspect:** A.
- **Table:** the purpose token `org` → crm, forms (5 names) vs `organization` (10 names) for the
  same field. `unique_` as a prefix → orgs (2) vs a suffix elsewhere. The model token `delivery`
  for `NotificationDelivery` → notifications. Every name has the module prefix (rule 25 ✓).
- **Rule:** amend rule 25 so the model token is the lowercased class name, the purpose names the
  fields (`organization`, not `org`), and `_unique` is the suffix.
- **Check:** harness rule 25 clause. Rides the clean-break `0001`.
- **Confidence:** High.

---

## 6. Proposed rules (ready to merge into decisions.md § Module Conventions)

Each proposal amends an existing rule; the item that motivates it is in brackets.

1. **Rule 1 — off switch** [Item 1]. ✅ Off keeps apps, middleware, settings, admin, and template
   tags. The adapter drops only public `url_includes` and `spa_routes`, and webhooks stay mounted
   and answer 404. ✅ A scheduled command refuses only a run marked `--trigger scheduled`, and no
   command defaults to `scheduled`. ✅ `.env.example` blocks are kept while off. ❌ An off branch
   returning fewer `apps` or `middleware` than the on branch.
2. **Rule 1 — vendor-credential exceptions** [Item 19]. ✅ backups' private-remote credentials
   (`QUICKSCALE_BACKUPS_REMOTE_*`) are a listed exception, so a backup bucket never shares
   storage's media credentials.
3. **Rule 2 / 33 — namespaces** [Items 8, 20, 25]. Add to the identity table: removal-obligation
   names `quickscale_<module>:<purpose>`; session keys `quickscale_<module>:<name>`; email-template
   keys `quickscale_<module>.<purpose>`. Rule 25's model token is the lowercased class name, the
   purpose names the fields (`organization`, not `org`), and `_unique` is the suffix.
4. **Rule 4 — surface and capabilities** [Items 14, 15]. ✅ A foundation's surface is the public
   names of its listed files. ✅ Capability names are listed in core's `CAPABILITIES` with their
   shapes, and only `collect_capabilities` collects them. ❌ Importing or re-exporting another
   module's `_`-prefixed name. ❌ A second collector.
5. **Rule 6 / 10 — retired settings, errors, checks** [Items 5, 7]. ✅ `retired_settings` lives in
   `module.yml` beside `retired_options`. ✅ `<Module>Error` uses the module name as spelled,
   derives from `Exception`, and API-visible subclasses set `status_code`/`default_code`, which
   core's handler renders. ✅ The settings check registers before module checks. ❌ `APIException`
   in a module hierarchy. ❌ A module check re-listing its declared settings.
6. **Rule 8 — templates** [Items 8, 22]. ✅ Pages are flat under `quickscale_<module>/`. ✅ Admin
   overrides go under `admin/<label>/<model>/`. ✅ A sender's email templates live in the sender
   and are registered by capability.
7. **Rule 9 — APIs** [Items 6, 11]. ✅ Unauthenticated calls answer 401 through core's one session
   authentication class. ✅ Every list paginates through core's `PlainListPagination`, sized by a
   `<THING>_PER_PAGE` setting. ✅ Generated JSON code follows rule 9. ❌ A module
   `SessionAuthentication` subclass. ❌ A literal page size.
8. **Rule 12 / § Module Derivation Schema — adapters** [Item 4]. ✅ The generic path validates,
   types, and projects `_ENV_VAR` options (blank → `""`). ✅ Post-hooks compute only settings no
   single option maps to. ❌ In `adapter.py`: re-validation, `bool()`/`int()`/`str()` of a
   projected option, `.get(<option>, <default>)`, value checks. ❌ A URL option without `url`
   normalization and a pattern.
9. **Rule 14 — model basics** [Item 21]. Unchanged text, now enforced. Add ❌ `Meta.app_label` in a
   module model.
10. **Rule 17 — command flags** [Item 16]. ✅ `--json` for machine output. ✅ `--trigger
    {manual,scheduled}` defaulting to `manual` on schedulable commands. ✅ `--confirm
    <identifier>` on commands that delete a tenant's or the database's data.
11. **Rule 19 — guards** [Item 3]. ✅ Every module view declares its guard: permission classes
    or `min_org_role` for APIs, a mixin for pages, an explicit public declaration otherwise.
    ✅ Every README lists minimum roles. ❌ `AllowAny` plus a hand-written user check. Edit the
    JSON API contract to drop "the billing-module pattern".
12. **Rule 29 — tests and shipped source** [Items 23, 24]. ✅ `tests/templates/` is allowed. ❌ A
    ticket id in shipped module source or `module.yml` (as in tests).
13. **Rule 32 — throttles** [Item 12]. ✅ Attached by `throttle_scope` only, through core's
    user-or-client-IP scoped throttle. ✅ Every vendor-calling or publishing write API has a scope.
    ❌ `throttle_classes` on a non-webhook view.
14. **Rule 34 — upward words** [Item 8]. ❌ A string constant, template key, or template path in a
    module's source naming a higher- or same-layer module's concept it does not own.
15. **Rule 37 + module-extension.md — core edits** [Item 9]. ✅ The authoring checklist lists
    every core edit a new module needs (catalog and count). ❌ A per-module constant, default, or
    `module_name == "<module>"` branch in core or the CLI outside the listed exceptions.
16. **Rule 41 — mounts and theme paths** [Items 2, 18]. ✅ A URL prefix belongs to one module. A
    shared third-party URLconf is mounted once, by the lowest-layer module that needs it. ✅ The
    seam carries module API bases. ❌ Two modules mounting one prefix. ❌ A `/<mount>/api` literal
    in the theme.
17. **Rule 43 — guards follow `required_modules`** [Item 13]. ✅ A required module is imported
    directly and asked `is_enabled()`. ✅ An optional one is guarded by `apps.is_installed`.
    ❌ `getattr(<services>, <name>, <default>)`.
18. **§ Module Wiring Authority / § Module Manifest Architecture** [Items 10, 17]. ✅ `apps` and
    `middleware` come only from `wiring_projections`. ✅ `required_modules` and `dependencies` are
    always present, and `dependencies` lists names only, with specs in `pyproject.toml`. ✅ Every
    module declares `quickscale-core`. ❌ An unparsed top-level manifest key.

---

## 7. Enforcement gaps

1. **Manifest loader is open-world on top-level keys.** `load_manifest` ignores unknown keys, so
   orgs' `middleware:`/`settings:` load silently. This breaks § Module Wiring Authority's
   "parsed-but-unread" ❌ [Item 10].
2. **Wiring-literal check covers `url_includes` only.** Harness rule 7 reads `adapter.py` for
   literal URL includes. `apps` and `middleware` literals (notifications, auth, orgs) are
   unchecked, and the app-declaration gate checks only the manifest projection [Item 10].
3. **URL prefix collisions are unchecked.** `_merge_unique` dedupes identical pairs only, and rule
   41's "two routes, one path" ❌ has no detector [Item 2].
4. **Capability names are open-world.** A misspelled capability is never collected [Item 15].
5. **Rule 29's second clause is unenforced.** The detector reads `test_*.py` only [Item 23].
6. **Rule 10's `<Module>Error` name is unchecked.** Any class ending `Error` passes, and modules
   with no `exceptions.py` are skipped [Item 7].
7. **Rule 14's `<event>_at` and `verbose_name` clauses are unchecked** [Item 21].
8. **Rule 4 is checked per file, not per name.** Private names in published files pass [Item 14].
9. **Rule 19's README duty and its "logged in" spellings are unchecked for `AllowAny` APIs**
   [Item 3].
10. **Rule 41's theme clause is checked only on the seam producer, not the theme's TypeScript**
    [Item 18].
11. **Rules 3/12 "defaults in code" and "values checked only in the manifest" are checked on
    settings reads only.** Adapter `.get(key, default)` and adapter value checks pass [Item 4].
12. **Core-rendered project code is outside the harness corpus.** social's generated payload views
    are `JsonResponse` functions [Item 11].
13. **Permissive allowed set.** Rule 30's merge lets any module write any `REST_FRAMEWORK` key,
    and the generated `base.py` uses `setdefault` so "a module-contributed handler … wins". A
    module could replace `EXCEPTION_HANDLER` or `DEFAULT_PERMISSION_CLASSES` for every
    installation. The prior pass accepted this for throttle rates only (gap 5 below). Recommended:
    a closed list of module-writable `REST_FRAMEWORK` sub-keys (`DEFAULT_THROTTLE_RATES`) enforced
    in `collect_wiring`.
14. **Dead validation path.** Core's resolver step 5 (`resolver.py:278`) validates against
    derivation rule lists the loader refuses, so it looks like validation and checks nothing
    [Item 4].
15. **Dangling secret marker.** Core's renderer leaves a blank `__QS_ENV__:` as the literal string
    `'__QS_ENV__:'` (`module_wiring.py:242`) [Item 4].
16. **Undiscoverable or contradictory rules.**
    - module-extension.md:542 says adding a module "requires no edit to `quickscale_core` or
      `quickscale_cli`". Rule 37 requires editing `MODULE_CATALOG` and
      `AUTHORITATIVE_MODULE_COUNT`, and the `.env.example` specs, notifications' template
      registry, and orgs' removal names also need edits [Items 8, 9].
    - The checklist's pyproject template shows `--cov=src/quickscale_modules_<name>`, which 2 of
      12 modules use [Item 17].
    - Rule 19 and the JSON API contract disagree on billing's pattern [Item 3].
    - The checklist says templates have "one flat `base.html` that the pages extend", which
      leaves the page depth open [Item 22].
17. **Rule 30 vs. composition order.** Rule 30 forbids settings whose value depends on module-name
    order, yet `INSTALLED_APPS` and `MIDDLEWARE` are composed in module-name order
    (`_sort_module_items`). There is no defect today: auth's `AccountMiddleware` happens to sort
    before orgs' `TenantMiddleware`. Recommended: middleware and apps carry an explicit
    `before`/`after` or the rule names the exception.
18. **Carried from the prior pass.** Gap 5 (accepted 2026-10-02: `test_isolation.py` does not
    self-enroll; rule 38's README match is a substring floor; `base.py` lets a module override
    `anon`/`user` rates). Gap 7 (frozen evidence anchors in the inventory, accepted).

---

## 8. Consistent by design

- **Service-surface size** (2 → 44 names) follows purpose. backups exposes a DR toolkit and auth's
  flows are allauth views.
- **Outbound clients run on vendor defaults** (no timeouts or retries set anywhere). Consistent;
  aspect I is quiet. A rule would be a decision, not a drift fix.
- **Logging.** Package-derived logger names everywhere; no structured fields; module logs reach the
  root handler only.
- **Locale.** English only. orgs' admin `change_list` override loads `i18n` because Django admin
  does.
- **Singletons** (`BackupPolicy`, `NotificationSettings`) use a `key` field and omit `ordering`.
  `CreditBalance` (one per organization) omits ordering.
- **Publication state.** blog and listings use `status` plus a publish moment because they have
  drafts; social uses `is_published` because it has no draft workflow.
- **billing's views default to the owner role.** Billing data is owner-only by purpose. Only the
  missing README table is drift (Item 3).
- **orgs' test suite imports higher-layer modules** (its `pythonpath` lists six sibling `src`
  trees). The user-FK gate (rule 27) and the personal-data inventory (rule 49) run there by
  decision.
- **Webhooks** (billing, notifications) share rule 26's shape exactly.
- **Carried from the prior pass.**
  - notifications alone handles HTML entity chains.
  - orgs, auth, and blog scrub by row, not by text matching.
  - crm, forms, listings, and backups declare no anonymization handler.
  - blog's anonymization logs on `quickscale_modules_blog.apps`.
  - `quickscale_orgs_create_site_org` has no `--dry-run`.

---

## 9. Hand-offs

**To the technical audit** (live or latent defects; detail stays there per the disclosure rule):
- `module-enabled-switch`: switching analytics off removes its app, so a project template that
  follows the README's `{% load quickscale_analytics %}` raises `TemplateSyntaxError`.
- `markdownx-shared-mount`: with blog and listings installed, listings' editor uploads land under
  `blog/markdownx/` and two URLconfs share one prefix.
- `option-schema-and-validation`: core's renderer emits a blank `__QS_ENV__:` marker as a literal
  string (latent; analytics' own check is the only guard).
- `module-error-http-mapping`: `InsufficientCreditsError` carries status 500 `billing_error`
  (latent for host projects that call `debit_user` from a DRF view).
- `optional-sender-guard`: forms' `notify_submission` returns `"queued"` when notifications is off,
  so the status misreports a skipped email.
- `tenant-authorization`: analytics' dashboard was the unguarded page; SA252 gave it login plus
  the viewer role, and the billing half remains the open item.

**To the architectural audit** (structural roots):
- `core-cli-module-knowledge`: the convention side of watchlist `core-holds-module-vocabulary`.
  social's runtime lives in core renderers, and the CLI branches on storage.
- `upward-name-references`: lower-layer registries hold higher layers' words (orgs' removal
  names, notifications' email templates). orgs' `Organization.stripe_customer_id` is a billing
  column on the tenant root, with a unique constraint and a billing `ExternalProviderField`
  declaration naming `quickscale_orgs.organization`.
- `capability-collection`: two capability-collection mechanisms (core helper vs orgs' `getattr`
  aggregator).

---

## 10. Aspect catalogue additions

- **B · Off-switch mechanism per surface.** App, URLs, jobs, `.env.example`, capabilities.
- **B · Adapter post-hook duties.** Validation, coercion, secret projection, defaults, literals.
- **C · Cross-module registries owned by a lower layer.** Obligation names, email-template keys,
  provider columns.
- **C · Per-module knowledge in core and the CLI.** Constants, renderers, dependency branches,
  catalog.
- **D · Capability names and collection mechanism.**
- **H · Unauthenticated status and the session-authentication class.**
- **H · Throttle attachment.** Class override vs scope on defaults; throttle identity.
- **J · Command flag vocabulary.** Trigger, machine output, confirmation.
- **L · Template sub-folder depth and admin-template location.**
- **N · Dependency spec sources.** `module.yml` vs `pyproject`; optional dependencies;
  `quickscale-core` declaration.
- **O · Ticket ids and version stamps in shipped source and manifests.**
- **P · Theme API base paths.** Seam vs literal.
- **A · Session keys and project route names a module depends on.**

---

## 11. Questions that would change a rule

1. Is analytics' app removal when off deliberate, to keep PostHog's client entirely out of a
   disabled project? If yes, Item 1's rule needs a listed exception and the README must drop the
   template-tag advice for disabled projects. → `module-enabled-switch`
2. Is 401 the intended status for every unauthenticated module API? The theme client already
   tolerates both. → `unauthenticated-status-code`
3. Is forms meant to work without analytics? That decides whether `required_modules` drops
   analytics or the guard goes. → `optional-sender-guard`
4. Do host projects override module templates by path today (for example
   `quickscale_blog/blog/post_list.html`)? That sets the release-notes weight of Item 22. →
   `template-folder-depth`
5. Must backups' private-remote credentials stay separate from storage's? That makes Item 19 a
   listed exception rather than a rename. → `secret-env-var-names`

---

## 12. Reconciliation log

*Prior entries are carried verbatim (append-only); this pass's lines follow under 2026-10-08 (c).*

- 2026-10-05 — **Location.** The coherence audit moves from
  `docs/planning/module-conventions-inventory.md` (passes 1–8) to this file. The inventory's index
  and log are frozen at `c10b529e`, and every prior ID continues below.
- 2026-10-05 — `anonymize-redaction-helper-copies`: **new**, open (lead from the arch audit's
  Coherence hand-offs).
- 2026-10-05 — `anonymize-replacement-values`: **new**, open.
- 2026-10-05 — `personal-data-inventory-ownership`: **resolved** (SA246 — rule 49; each module
  declares its rows through `personal_data_declarations`, the closed-world inventory test
  collects them and keeps its three controls, and orgs' W006 check reports undeclared candidates
  on project-owned models).
- 2026-10-05 — `anonymize-executor-naming`: **new**, open.
- 2026-10-05 — `anonymize-redaction-helper-copies`: **resolved** (abbc09d0 — rule 47; core's
  `replace_address`/`redact_names` are the one matcher, and the control case rejects billing's old
  `_redact_string`).
- 2026-10-05 — `anonymize-replacement-values`: **resolved** (abbc09d0 — rule 48; the handlers that
  remove identity from stored text or payloads write core's `DELETED_ADDRESS(pk)` and `REDACTED`,
  and the control case rejects billing's old `REDACTED = "[redacted]"`).
- 2026-10-05 — `anonymize-executor-naming`: **resolved** (abbc09d0 — rule 48; auth's entry point is
  `_anonymization.anonymize_account`, the collector is in `_anonymize_boundary.py`, and the control
  case rejects a `scrub_account` delegation).
- 2026-10-05 — `write-effects-on-commit`: **resolved** (2eb63262 — verified: notifications' rollback test `tests/test_services.py:325–341` exists and `dispatch_after_commit` is gone; blog joins the population with an on-commit test). (Correction: the 2026-10-03 pass listed it as *decided* with notifications still to change; the test landed 2026-10-02, before that pass's SHA.)
- 2026-10-05 — `settings-snapshot-readers`: **resolved** (537204bc — rule 42 (D44); harness passes at 8e4122f2).
- 2026-10-05 — `optional-sender-guard`: **resolved** (537204bc — rule 43 (D45); harness passes at 8e4122f2).
- 2026-10-05 — `mount-path-copies`: **resolved** (a621299b — rule 41 (D43) via SA235 `spa_routes`; harness passes at 8e4122f2; rule 41 text spot-checked).
- 2026-10-05 — `org-role-check-copies`: **resolved** (6b4fd1eb — rule 44 (D46); harness passes at 8e4122f2).
- 2026-10-05 — `mypy-overrides-unread`: **resolved** (6b4fd1eb — rule 45 (D47); harness passes at 8e4122f2).
- 2026-10-05 — `split-facade-conventions`: **resolved** (7097fa3e, 46d99cdb, d1feab8d — rule 46 via rules 19 and 28; harness passes; blog's new private file logs on the caller's channel).
- 2026-10-05 — `theme-module-presence`: **resolved** (a621299b — rule 31 (D34) via SA235 `spa_routes`; harness passes at 8e4122f2; rule 41 text spot-checked).
- 2026-10-05 — `module-lists-outside-members`: **resolved** (a621299b — rule 37 (D40) via SA235 `spa_routes`; harness passes at 8e4122f2; rule 41 text spot-checked).
- 2026-10-05 — `shared-setting-writes`: **resolved** (cb750c51 — rule 30 (D33); held by `collect_wiring` in apply, not the harness; not re-run this pass).
- 2026-10-05 — `throttle-scopes-and-rates`: **resolved** (c3c99253 — rule 32 (D35); held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `namespace-prefix-principle`: **resolved** (6fe010b4 — rule 33 (D36); held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `upward-name-references`: **resolved** (2352acf1 — rule 34 (D37); held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `secret-resolution-path`: **resolved** (17d4985d — rule 35 (D38); held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `type-check-config`: **resolved** (c75b5588 — rule 36 (D39); held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `readme-content-accuracy`: **resolved** (49b709f2 — rule 38 (D41); held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `manifest-dependency-spec`: **resolved** (92c9566f — rule 39 (D42); held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `settings-names`: **resolved** (79b3f079 — rule 1; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `module-enabled-switch`: **resolved** (97ac9187 — rule 1; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `settings-readers-and-defaults`: **resolved** (2b44e473 — rule 3; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `cross-module-settings-reads`: **resolved** (c460d46f — rules 3–4; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `secret-env-var-names`: **resolved** (480735c9 — rule 1; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `module-dependency-direction`: **resolved** (10dc1691 — rules 4–5; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `identity-stem`: **resolved** (6fe010b4 — rule 2; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `url-mounts-and-names`: **resolved** (30759c78 — rule 7; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `templates-static-tags`: **resolved** (49982a73 — rule 8; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `http-api-shape`: **resolved** (dcd3bda0 — rule 9; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `startup-checks-and-errors`: **resolved** (88dad552 — rule 10; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `package-files`: **resolved** (c75b5588 — rules 11, 28; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `required-tests`: **resolved** (9382e6ed — rule 11; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `readme-outline`: **resolved** (49b709f2 — rule 11; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `model-choices`: **resolved** (bf60796f — rule 11; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `option-schema-and-validation`: **resolved** (d0b148c9 — rule 12; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `tenant-model-base`: **resolved** (bf60796f — rule 13; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `model-basics`: **resolved** (bf60796f — rule 14; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `package-root-init`: **resolved** (b315009f — rule 15; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `signals-vs-receivers`: **resolved** (b315009f — rule 16; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `command-behavior`: **resolved** (84652d2d — rule 17; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `package-tooling`: **resolved** (469e3b7d — rule 18; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `tenant-authorization`: **resolved** (ab3ec43e — rule 19; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `email-sender`: **resolved** (0c6f96cd — rule 20; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `analytics-event-ownership`: **resolved** (0c6f96cd — rule 22; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `service-surface`: **resolved** (b18032e3 — rule 23; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `current-time-call`: **resolved** (c75b5588 — rule 24; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `cache-key-stem`: **resolved** (10dc1691 — rule 24; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `constraint-index-names`: **resolved** (c75b5588 — rule 25; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `inbound-webhooks`: **resolved** (f6ad7784 — rule 26; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `test-file-names`: **resolved** (730456cb — rule 29; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 — `user-fk-on-delete`: **resolved** (fa0b882b — rule 27; held by the user-FK gate in orgs tests, not the harness; not re-run this pass).
- 2026-10-05 — `py-typed`: **resolved** (6ea37301 — rule 24; held by the harness at 8e4122f2, cells not re-read).
- 2026-10-05 (b) — **re-run** at `f00ed460`; delta `8e4122f2..f00ed460`; 2 passes; harness passes 42 rules.
- 2026-10-05 (b) — `semantic-personal-data-central-pin`: **new**, open (lead from tech-audit §13).
- 2026-10-05 (b) — `personal-data-inventory-ownership`: resolved (2f1d0a4e — re-verified: 9 modules declare in `apps.py`; residual central pin split out as `semantic-personal-data-central-pin`).
- 2026-10-05 (b) — `anonymize-redaction-helper-copies`, `anonymize-replacement-values`, `anonymize-executor-naming`: resolved (abbc09d0, 9203630f, 199eb250 — harness rules 47–48 pass at f00ed460).
- 2026-10-05 (b) — all other prior IDs: still resolved (harness passes at f00ed460; SA247 split verified behavior-neutral by the same 42-rule success line; cells not re-read).
- 2026-10-06 — `semantic-personal-data-central-pin`: **resolved** (SA249 — rule 49 amendment; auth, billing, and notifications pin their non-candidate rows in their own tests, and the inventory test accepts only orgs', contrib, and third-party pinned keys, with a control re-adding an auth key).
- 2026-10-06 — Enforcement gaps 4 and 6: **resolved** (SA250 — `DELEGATED_RULES` lists rules
  40/41/46/49 with their carriers and the harness success line names them; the partition test
  parses the decisions.md rule headings and a control fails on an added heading).
- 2026-10-08 — Questions: **purged**. Both rule questions concerned items already resolved by
  rules 47–49. Enforcement gap 6's partition-test anchor now names the SA247 location.

### 2026-10-08 (c) — full independent re-audit at `2fd8637f` (3 passes; harness passes 43 rules)

- 2026-10-08 (c) — **Method.** At the maintainer's request this pass re-audited from scratch,
  without reading this file or the inventory first, then reconciled. Cells were read from source
  rather than taken from the harness's success line. Sections 1–11 above replace the previous
  `f00ed460` sections; that text is in git history.
- 2026-10-08 (c) — **Corrections.** The prior pass's "16 management commands" is 15 at both
  `f00ed460` and `2fd8637f`. This pass's first draft listed `orgs/tests/sa208_project_app/` and
  `sa182_project_app/` as ticket-named test apps; they are ignored `__pycache__` leftovers, not
  tracked files.
- 2026-10-08 (c) — `module-enabled-switch`: **reopened**, open; regressed: false (every variant —
  analytics' app-dropping off branch `c32d624b` 2026-08-27, billing's and notifications'
  mounted-when-off URLs, the jobs and `.env.example` variants — predates `97ac9187`). Item 1.
- 2026-10-08 (c) — `tenant-authorization`: **reopened**, open; regressed: false (analytics'
  unguarded dashboard 2026-06-16; billing's `AllowAny` + `_require_authenticated` 2026-05-16;
  billing README has no role table). Item 3.
- 2026-10-08 (c) — `option-schema-and-validation`: **reopened**, open; regressed: false (adapter
  re-validation, coercions, re-projection, code defaults, and value checks predate `d0b148c9`;
  core's resolver step 5 has validated nothing since rule 12's loader refusal). Item 4.
- 2026-10-08 (c) — `startup-checks-and-errors`: **reopened**, open; regressed: false
  (`NotificationError`/`BackupError` names, blog's check order, hand-listed setting guards,
  retired settings in `checks.py`). Item 7.
- 2026-10-08 (c) — `upward-name-references`: **reopened**, open; **regressed: true** (SA216(a)
  `3cffb168`, 2026-10-04, defined `AUTH_`/`BILLING_`/`BLOG_PERSONAL_DATA`,
  `BILLING_PROVIDER_STATE`, and `SOCIAL_CACHE_STATE` in orgs after the 2026-10-02 resolution
  `2352acf1`; notifications' `forms_submission`/`org_invitation` template keys predate it, from
  2026-03-30). Item 8.
- 2026-10-08 (c) — `http-api-shape`: **reopened**, open; regressed: false (billing's literal page
  size 2026-05-16; social's generated `JsonResponse` views from core renderers). Item 11.
- 2026-10-08 (c) — `optional-sender-guard`: **reopened**, open; regressed: false (orgs'
  `getattr(…, "send_notification", None)` 2026-05-20; forms guards a required analytics and
  imports a required notifications eagerly). Item 13.
- 2026-10-08 (c) — `module-dependency-direction`: **reopened**, open; regressed: false (crm's
  `_restore_current_org_id` import 2026-07-12; blog's and social's private-name imports). Item 14.
- 2026-10-08 (c) — `mount-path-copies`: **reopened**, open; regressed: false (theme hooks'
  literal API bases and the retired `errors` parse; the seam producer itself still conforms).
  Item 18.
- 2026-10-08 (c) — `secret-env-var-names`: **reopened**, open; regressed: false (backups'
  `QUICKSCALE_BACKUPS_REMOTE_*` defaults versus rule 1's vendor-name clause, with no listed
  exception). Item 19.
- 2026-10-08 (c) — `model-basics`: **reopened**, open; regressed: false (`published_date` since
  v0.66.0; redundant `verbose_name` in 6 modules; explicit `Meta.app_label` in 7). Item 21.
- 2026-10-08 (c) — `test-file-names`: **reopened**, open; regressed: not determined per file (6
  tracked non-test files and 4 `tests/templates/` trees outside rule 29's list). Item 23.
- 2026-10-08 (c) — `markdownx-shared-mount`: **new**, open. The frozen inventory
  (`module-conventions-inventory.md` §32 "Settings written by module wiring", line 923) recorded both modules mounting
  `markdownx/` → `markdownx.urls` and warned that "a different pair for the same prefix would mount
  twice". SA219 (`3420fbc8`, 2026-10-01) introduced exactly that. Item 2.
- 2026-10-08 (c) — `unauthenticated-status-code`: **new**, open (SA223, 2026-09-30, added four
  identical 401 subclasses; crm and forms stayed 403). Item 6.
- 2026-10-08 (c) — `module-error-http-mapping`: **new**, open. Item 5.
- 2026-10-08 (c) — `core-cli-module-knowledge`: **new**, open; convention side of the arch
  watchlist `core-holds-module-vocabulary`. Item 9.
- 2026-10-08 (c) — `manifest-declared-surface`: **new**, open. Item 10.
- 2026-10-08 (c) — `throttle-attachment`: **new**, open (lead from tech-audit §12: listings'
  publish API has no module throttle). Item 12.
- 2026-10-08 (c) — `capability-collection`: **new**, open. Item 15.
- 2026-10-08 (c) — `command-flag-conventions`: **new**, open. Item 16.
- 2026-10-08 (c) — `dependency-spec-sources`: **new**, open. Item 17.
- 2026-10-08 (c) — `session-and-host-names`: **new**, open. Item 20.
- 2026-10-08 (c) — `template-folder-depth`: **new**, open. Item 22.
- 2026-10-08 (c) — `ticket-ids-in-shipped-source`: **new**, open. Item 24.
- 2026-10-08 (c) — `constraint-purpose-tokens`: **new**, open. Item 25.
- 2026-10-08 (c) — `write-effects-on-commit`: still-resolved (rule 21; every effect site in §4.F is `on_commit`).
- 2026-10-08 (c) — `settings-snapshot-readers`: still-resolved (rule 42; harness passes; five `_settings.py` snapshots, none in `__all__`).
- 2026-10-08 (c) — `org-role-check-copies`: still-resolved (rule 44; harness passes).
- 2026-10-08 (c) — `mypy-overrides-unread`: still-resolved (rule 45; no `[tool.mypy]` in any module pyproject).
- 2026-10-08 (c) — `split-facade-conventions`: still-resolved (rule 46; harness passes).
- 2026-10-08 (c) — `theme-module-presence`: still-resolved (rule 31; the seam producer conforms — theme hook paths are filed under `mount-path-copies`).
- 2026-10-08 (c) — `module-lists-outside-members`: still-resolved (rule 37; harness passes — per-module constants in core are filed under `core-cli-module-knowledge`).
- 2026-10-08 (c) — `shared-setting-writes`: still-resolved (rule 30; `collect_wiring` read this pass — URL prefixes, which it does not cover, are filed under `markdownx-shared-mount`).
- 2026-10-08 (c) — `throttle-scopes-and-rates`: still-resolved (rule 32; scope names and rates conform — attachment is `throttle-attachment`).
- 2026-10-08 (c) — `namespace-prefix-principle`: still-resolved (rule 33; harness passes — unlisted namespaces are filed under `upward-name-references` and `session-and-host-names`).
- 2026-10-08 (c) — `secret-resolution-path`: still-resolved (rule 35; no `os.getenv` in module code outside orgs' listed guard).
- 2026-10-08 (c) — `type-check-config`: still-resolved (rule 36; harness passes).
- 2026-10-08 (c) — `readme-content-accuracy`: still-resolved (rule 38; harness passes).
- 2026-10-08 (c) — `manifest-dependency-spec`: still-resolved (rule 39; bare first-party names — third-party spec dialects are `dependency-spec-sources`).
- 2026-10-08 (c) — `settings-names`: still-resolved (rule 1; all 86 options re-read).
- 2026-10-08 (c) — `settings-readers-and-defaults`: still-resolved (rule 3; module settings reads conform — adapter defaults are filed under `option-schema-and-validation`).
- 2026-10-08 (c) — `cross-module-settings-reads`: still-resolved (rules 3–4; harness passes).
- 2026-10-08 (c) — `identity-stem`: still-resolved (rule 2; labels, namespaces, folders re-read).
- 2026-10-08 (c) — `url-mounts-and-names`: still-resolved (rule 7; every mount is declared in its manifest — the shared `markdownx/` prefix is `markdownx-shared-mount`).
- 2026-10-08 (c) — `templates-static-tags`: still-resolved (rule 8; base templates conform — page depth is `template-folder-depth`).
- 2026-10-08 (c) — `package-files`: still-resolved (rules 11, 28; harness passes).
- 2026-10-08 (c) — `required-tests`: still-resolved (rule 11; all required files present).
- 2026-10-08 (c) — `readme-outline`: still-resolved (rule 11; all 12 outlines re-read).
- 2026-10-08 (c) — `model-choices`: still-resolved (rule 11; harness passes).
- 2026-10-08 (c) — `tenant-model-base`: still-resolved (rule 13; every tenant model in the census subclasses `TenantModel`).
- 2026-10-08 (c) — `package-root-init`: still-resolved (rule 15; harness passes).
- 2026-10-08 (c) — `signals-vs-receivers`: still-resolved (rule 16; orgs' one signal in `signals.py`, receivers in `receivers.py`).
- 2026-10-08 (c) — `command-behavior`: still-resolved (rule 17; all 15 commands use `BaseCommand`, `CommandError`, `self.stdout` — flag conventions are `command-flag-conventions`).
- 2026-10-08 (c) — `package-tooling`: still-resolved (rule 18; required pyproject sections present in all 12).
- 2026-10-08 (c) — `email-sender`: still-resolved (rule 20; only notifications sends — template ownership is filed under `upward-name-references`).
- 2026-10-08 (c) — `analytics-event-ownership`: still-resolved (rule 22; forms' one event).
- 2026-10-08 (c) — `service-surface`: still-resolved (rule 23; `__all__` in all 12).
- 2026-10-08 (c) — `current-time-call`: still-resolved (rule 24; harness passes).
- 2026-10-08 (c) — `cache-key-stem`: still-resolved (rule 24; social's two keys).
- 2026-10-08 (c) — `constraint-index-names`: still-resolved (rule 25; every name prefixed — tokens are `constraint-purpose-tokens`).
- 2026-10-08 (c) — `inbound-webhooks`: still-resolved (rule 26; billing and notifications re-read).
- 2026-10-08 (c) — `user-fk-on-delete`: still-resolved (rule 27; the model census matches the gate's allowlist; gate not re-run).
- 2026-10-08 (c) — `py-typed`: still-resolved (rule 24; present in all 12).
- 2026-10-08 (c) — `semantic-personal-data-central-pin`: still-resolved (rule 49; not re-read cell by cell).
- 2026-10-08 (c) — `anonymize-redaction-helper-copies`: still-resolved (rule 47; harness passes).
- 2026-10-08 (c) — `anonymize-replacement-values`: still-resolved (rule 48; harness passes).
- 2026-10-08 (c) — `personal-data-inventory-ownership`: still-resolved (rule 49; 9 modules declare in `apps.py`, re-read).
- 2026-10-08 (c) — `anonymize-executor-naming`: still-resolved (rule 48; five `anonymize_account` executors re-read).
- 2026-10-08 (c) — **Companion leads.** tech-audit §12 (listings throttle → `throttle-attachment`;
  social `JsonResponse` → `http-api-shape`; analytics' unguarded page → `tenant-authorization`).
  arch-audit §14 (markdownx copy pair → `markdownx-shared-mount`; the theme's 36 TypeScript files
  naming modules beside the seam producer → `mount-path-copies`, Medium confidence, since only the
  API hooks were read). All passed §0.
- 2026-10-08 (d) — `tenant-authorization` (analytics half): **resolved** (SA252 — the analytics
  dashboard requires login and the active organization's `viewer` role through orgs' one role
  check; billing's `AllowAny` half remains open for SA262, and `members_diverging` is now
  `[billing]`).

### 2026-10-08 (e) — SA266 conventions sweep (harness 43 rules, 251 controls)

- 2026-10-08 (e) — `model-basics`: **resolved** (SA266 — `Meta.app_label` removed from the seven
  modules that set it; the six modules' default-equal `verbose_name`/`verbose_name_plural`
  removed while irregular plurals stay; blog's and listings' `published_date` renamed to
  `published_at`, with their `0001_initial` rewritten in place; harness rule 14 now refuses an
  explicit `app_label`, a non-`_at` `DateTimeField` name outside a `_start`/`_end` period
  boundary, and a default-equal `verbose_name`, with controls). Item 21.
- 2026-10-08 (e) — `template-folder-depth`: **resolved** (SA266 — nine page templates of blog,
  listings, crm, forms, and billing flattened under `templates/quickscale_<module>/`; orgs'
  admin override moved to `templates/admin/quickscale_orgs/organization/change_list.html`; the
  v0.89.0 release note lists every moved path; harness rule 8 rejects a module-named page
  sub-folder and an admin override outside `admin/<label>/<model>/`, with controls). Item 22.
- 2026-10-08 (e) — `test-file-names`: **resolved** (SA266 — six tracked non-test files renamed to
  private helpers (`_wsgi.py`, `_diag_setlocal.py`, `_stripe_payloads.py`, `_models.py`,
  `_views.py`, `_bypassed_boundary.py`); rule 29's file set now names `tests/templates/` and
  `__init__.py`, and the harness closes the set over `tests/` entries, with controls). Item 23.
- 2026-10-08 (e) — `ticket-ids-in-shipped-source`: **resolved** (SA266 — every `SA`/`AF`/`CR-SA`
  and `T<n>.<n>` id removed from shipped module source and the six `(T2.3 Phase 3)` manifest
  headers; the harness reuses the ticket vocabulary over `src/**/*.py` and `module.yml`, with
  controls). Item 24.
- 2026-10-08 (e) — `constraint-purpose-tokens`: **resolved** (SA266 — twelve `UniqueConstraint`
  names now use the lowercased class name, `organization` instead of `org`, and the `_unique`
  suffix, inside the rewritten `0001_initial`s; notifications' full shape exceeds 63 characters,
  so its purpose abbreviates to `recipient_unique`; harness rule 25 checks the class token, the
  `org` token, and the `_unique` placement, with controls). Item 25.
- 2026-10-08 (e) — `command-flag-conventions`: **resolved** (SA266 — orgs'
  `check_tenant_isolation --format json` becomes `--json`; a destructive
  `quickscale_orgs_purge_organization` requires `--confirm <slug>`; `quickscale_backups_prune`
  defaults to `manual`; `quickscale_forms_anonymize_submissions` takes
  `--trigger {manual,scheduled}` and refuses only the scheduled run while off; backups'
  `--scheduled` alias is retired for `--trigger scheduled`; harness rule 17 checks the flag
  vocabulary, with controls). Item 16.
