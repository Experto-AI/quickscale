# Coherence Audit — Cross-Module Conformance

Audited: `82ff3e7d141cf943ab900eaae5f214c0edfc9e07` (v89) · 2026-10-24 · working tree dirty · visibility public · prompt: deep-coherence-audit v3 · passes: 3 · stopping reason: the counterevidence and gap pass added no new supported item or aspect; theme execution and live deployment remain unassessed.

Source snapshot: HEAD `82ff3e7d` plus two unstaged companion deliverables, `docs/others/arch-audit.md` (digest `aba552c607c4e16f37b2cd9cb8103df09c9bff8be233db1c553fdefb2c69d413`) and `docs/others/tech-audit.md` (digest `fcabcc7f23737e676c1c5abd57db0b1bef913d3860d6884c8a25a6b3248ab72f`), both excluded from the source basis. No staged or untracked source. Generated artifacts (`.coverage`, `coverage.json`, `htmlcov/`, caches, per-module `.venv/`) are excluded. The prior coherence report at `39d455ef` was read only after the independent sweep, for reconciliation. Cite items by slug, proposals as “coherence proposal N”, and enforcement gaps as “coherence gap N”.

## Orientation and coverage

QuickScale is a Python 3.14 / Django 6.0 project generator and first-party-module platform. The comparable population is **12 modules** under `quickscale_modules/`, which share one declared extension, wiring, model, command, test, packaging, and documentation contract. Host code that names or renders them — `quickscale_core`, `quickscale_cli`, `scripts/`, generator templates, and the theme — is outside the module population but is in scope where it carries a member contract. Deployment realities: generated Django projects on PostgreSQL 18 with FORCE RLS under a `NOSUPERUSER`/`NOBYPASSRLS` runtime role; the maintainer monorepo and its gates; module standalone test runs; and `showcase_react`.

**Populations and discovery.**

| Population | Size | Members / discovery |
|---|---|---|
| `modules` | 12/12 inspected | analytics, auth, backups, billing, blog, crm, forms, listings, notifications, orgs, social, storage; `quickscale_modules/*/module.yml` |
| `manifests` | 12/12 | same directories; bundled copies under `quickscale_core/src/quickscale_core/data/manifests/` diffed byte-for-byte |
| `adapters` | 12/12 | `src/quickscale_modules_<name>/adapter.py` |
| `service-surfaces` | 12/12 | `services.py` `__all__`, `is_enabled`, signatures |
| `module-readmes` | 12/12 | `quickscale_modules/*/README.md` |
| `commands` | 16/16 public + 2 private support | `*/management/commands/quickscale_*.py`; backups 9, billing 1, forms 2, orgs 4 |
| `tenant-models` | 22 declared, 20 registered admins | six tenant modules |
| `tenant-isolation-suites` | 6/6 | billing, blog, crm, forms, listings, social `tests/test_isolation.py` + `tests/test_rls_boundary.py` |
| `test-settings` | 12/12 | `tests/settings.py`; `BASE_TEST_SETTINGS_KEYS` |
| `contract-vintages` | 4/4 | backups, billing, orgs, social manifests |
| `generator-templates` | active, partial | core templates that emit project files |
| `frontend-theme` | active, partial | seam producer and module-surface tables read; TSX not executed |
| `scripts-gates` | active, sampled | module-conventions, isolation, integration, coverage, migration-freeze, publish helpers |

**Contexts and compatibility promises.** Supported runtime is Python 3.14 / Django 6.0 / PostgreSQL 18. Modules promise coordinated 0.89.0 versions (`VERSION`, all 12 `module.yml`, all 12 package `__version__`, all 12 `pyproject.toml`). Module migration history is frozen from 0.89.0; applied migration files are append-only. Generated projects are user-owned after generation with a managed-file subset; the theme is user-owned. No rolling-deploy, downgrade, or permanent-backcompat promise is made beyond the declared contract vintages.

**Shared namespaces swept.** Settings and environment names (`QUICKSCALE_<MODULE>_*`, vendor defaults, `*_ENV_VAR`); app labels (`quickscale_<module>`); URL namespaces and mount prefixes; template/static folders; email-template keys (`quickscale_<module>.<purpose>`); cache/session keys; analytics events; removal-obligation names; DRF throttle scopes; constraint/index names; reverse accessors; management command names; host route `home`; and generated-template module branches.

**Declared rules and enforcement.** `docs/technical/module_conventions.md` rules 1–50 (parsed by `scripts/module_conventions/registry.py`; covered/open/delegated partition); `module_architecture.md` §Module Wiring Authority; `module-extension.md` §Standard Documentation Contract; `organizations.md` §Admin Panel Contract; `decisions.md` §Fail-Hard Principle and §Multi-tenant SaaS Architecture; `validation_policy.md` §Testing Standards. Checks were **inspected, not run**: an inspected test is not a passed test, and every check state below is `observed-in-source` or `proposed`.

**Reference members.** Blog and listings for public-read context; billing and notifications for webhooks and vendor settings; CRM and forms for tenant isolation; backups and orgs for commands. Completeness or recency is not law: CRM is the reference for the RLS view-path proof but is also the carrier of stale isolation prose (item 13).

**Delta and prior state.** The prior coherence report at `39d455ef` was a bounded re-run: it assessed aspect J and one core anchor, and left most aspects unassessed. This pass is a fresh full sweep. `39d455ef..82ff3e7d` contains 94 commits (67 non-merge), including 3 non-merge commits under `quickscale_modules/` and 5 under the generator/harness; the two companion audits were read for hand-offs. The prior report’s 2026-10-16 census of 41 IDs is not itemized in that file; its last-known `resolved` status is retained but excluded from this pass’s confirmed counts. The 25 IDs recoverable from the 2026-10-13 index are reconciled in §13.

**Aspect activation and coverage.**

| Population | Aspect | Activation | Coverage |
|---|---|---|---|
| modules | A identity/namespaces | active | complete |
| modules | B configuration/options/defaults | active | complete |
| modules | C dependencies/layering | active | complete |
| modules | D service/public surface | active | complete |
| modules | E authorization/trust | active | complete for declared paths |
| modules | F side effects/transactions | active | partial: senders and on-commit paths read |
| modules | G data model basics | active | complete for models/constraints/admin |
| modules | H API/protocol shape | active | complete for routed JSON and webhooks |
| modules | I outbound integrations | active | partial: client construction read; live behavior unknown |
| modules | J commands/jobs | active | complete |
| modules | K observability | active | partial: logger/event names sampled |
| modules | L files/packaging/generation | active | complete for module layout; generator partial |
| modules | M tests/conformance evidence | active | complete for file inventory; partial for test bodies |
| modules | N tooling/check parity | active | partial: harness scopes read, not run |
| modules | O documentation/governance | active | complete for READMEs/rule docs |
| modules | P frontend/client | active | partial: seam and surface tables; TSX not executed |
| modules | Q locale/presentation | inert | English-only policy; no module gettext |
| modules | R compatibility/rollout | active | partial: contract vintages read; migration freeze checked |
| modules | S asynchronous/delivery | active | partial: webhook and on-commit paths read |
| modules | T runtime lifetime/capacity | active | partial: no shared pool policy found |
| modules | U build/release/artifact trust | active | partial: versions/pyprojects read; build not run |
| modules | V data lifecycle/sensitive copies | active | partial: declarations/obligations read; restore not exercised |

**Excluded / unknown.** The theme TSX was not read line by line; no live generated project was inspected; no repository test, generator, build, linter, migration, or service was run. Deployment configuration (production `WEB_CONCURRENCY`, actual env values, whether a live project uses any module) is unknown. Companion-audit contents are excluded from the source basis but their hand-offs are dispositioned in §9.

## Machine-readable index

```yaml
schema: coherence-audit/v2
prompt: deep-coherence-audit/v3
audited: "82ff3e7d141cf943ab900eaae5f214c0edfc9e07"
snapshot_basis: "HEAD 82ff3e7d (v89) + dirty companion docs/others/arch-audit.md (aba552c6…) and docs/others/tech-audit.md (fcabcc7f…), excluded; no staged/untracked source"
visibility: public
populations:
  - {id: modules, size: 12, inspected: 12, unknown: 0, discovery: "quickscale_modules/*/module.yml"}
  - {id: manifests, size: 12, inspected: 12, unknown: 0, discovery: "module.yml + bundled data/manifests"}
  - {id: adapters, size: 12, inspected: 12, unknown: 0, discovery: "src/quickscale_modules_*/adapter.py"}
  - {id: service-surfaces, size: 12, inspected: 12, unknown: 0, discovery: "services.py __all__"}
  - {id: module-readmes, size: 12, inspected: 12, unknown: 0, discovery: "quickscale_modules/*/README.md"}
  - {id: commands, size: 16, inspected: 16, unknown: 0, discovery: "*/management/commands/quickscale_*.py"}
  - {id: tenant-models, size: 20, inspected: 20, unknown: 0, discovery: "registered tenant-model admins; 22 models in the tenant contract"}
  - {id: tenant-isolation-suites, size: 6, inspected: 6, unknown: 0, discovery: "tests/test_isolation.py + tests/test_rls_boundary.py"}
  - {id: test-settings, size: 12, inspected: 12, unknown: 0, discovery: "tests/settings.py"}
  - {id: generator-templates, size: 5, inspected: 5, unknown: 0, discovery: "admin index/app_index, CI, Makefile, compose, generated base settings"}
  - {id: frontend-theme, size: 1, inspected: 1, unknown: 1, discovery: "seam producer + module-surface tables; TSX not executed"}
coverage:
  - {population: modules, aspect: A, activation: active, coverage: complete}
  - {population: modules, aspect: B, activation: active, coverage: complete}
  - {population: modules, aspect: C, activation: active, coverage: complete}
  - {population: modules, aspect: D, activation: active, coverage: complete}
  - {population: modules, aspect: E, activation: active, coverage: complete}
  - {population: modules, aspect: F, activation: active, coverage: partial}
  - {population: modules, aspect: G, activation: active, coverage: complete}
  - {population: modules, aspect: H, activation: active, coverage: complete}
  - {population: modules, aspect: I, activation: active, coverage: partial}
  - {population: commands, aspect: J, activation: active, coverage: complete}
  - {population: modules, aspect: K, activation: active, coverage: partial}
  - {population: modules, aspect: L, activation: active, coverage: complete}
  - {population: modules, aspect: M, activation: active, coverage: complete}
  - {population: modules, aspect: N, activation: active, coverage: partial}
  - {population: modules, aspect: O, activation: active, coverage: complete}
  - {population: frontend-theme, aspect: P, activation: active, coverage: partial}
  - {population: modules, aspect: Q, activation: inert, reason: "English-only module source; no locale surface"}
  - {population: modules, aspect: R, activation: active, coverage: partial}
  - {population: modules, aspect: S, activation: active, coverage: partial}
  - {population: modules, aspect: T, activation: active, coverage: partial}
  - {population: modules, aspect: U, activation: active, coverage: partial}
  - {population: modules, aspect: V, activation: active, coverage: partial}
items:
  - id: generated-module-branches
    kind: rule-violation
    status: resolved
    verification: fixed
    aspect: L
    cost: [tax, ambiguity]
    population: generator-templates
    members_affected: [core-admin-templates, core-ci-makefile, core-compose, notifications]
    rule_ref: "module_conventions rule 37; module_architecture §Module Wiring Authority"
    check: {kind: structural, state: enforced, model: contract-based}
    handoff: [arch]
    first_seen: "2026-10-24"
    last_verified: "2026-10-26"
  - id: notifications-anymail-wiring-split
    kind: rule-violation
    status: resolved
    verification: fixed
    aspect: B
    cost: [tax]
    population: modules
    members_affected: [notifications]
    rule_ref: "module_conventions rule 30; module_architecture §Module Wiring Authority"
    check: {kind: structural, state: enforced, model: contract-based}
    handoff: [arch]
    first_seen: "2026-10-24"
    last_verified: "2026-10-26"
  - id: billing-feature-gate
    kind: rule-violation
    status: fixed
    regressed: false
    verification: confirmed
    aspect: H
    cost: [ambiguity]
    population: modules
    members_affected: [billing]
    rule_ref: "module_conventions rule 9; prior unauthenticated-status-code"
    check: {kind: conformance, state: enforced, model: contract-based}
    handoff: [tech]
    first_seen: "2026-10-24"
    last_verified: "2026-10-26"
  - id: billing-admin-org-filter
    kind: drift
    status: fixed
    verification: confirmed
    aspect: E
    cost: [tax]
    population: tenant-models
    members_affected: [billing]
    rule_ref: "organizations.md §Admin Panel Contract"
    check: {kind: structural, state: enforced, model: contract-based}
    handoff: []
    first_seen: "2026-10-24"
    last_verified: "2026-10-26"
  - id: forms-tenant-isolation-evidence
    kind: drift
    status: open
    verification: confirmed
    aspect: M
    cost: [tax]
    population: tenant-isolation-suites
    members_affected: [forms]
    rule_ref: "module_conventions rule 11; decisions.md §Multi-tenant SaaS Architecture"
    check: {kind: conformance, state: proposed, model: contract-based}
    handoff: []
    first_seen: "2026-10-24"
    last_verified: "2026-10-24"
  - id: tenant-suite-default-role
    kind: drift
    status: open
    verification: confirmed
    aspect: M
    cost: [tax]
    population: test-settings
    members_affected: [forms, listings, social]
    rule_ref: "validation_policy.md §Testing Standards; proposed rule"
    check: {kind: conformance, state: proposed, model: contract-based}
    handoff: []
    first_seen: "2026-10-24"
    last_verified: "2026-10-24"
  - id: crm-null-org-legacy
    kind: rule-violation
    status: open
    verification: confirmed
    aspect: G
    cost: [tax, ambiguity]
    population: tenant-models
    members_affected: [crm, orgs]
    rule_ref: "module_conventions rule 13; post-0006 CRM contract"
    check: {kind: structural, state: proposed, model: contract-based}
    handoff: []
    first_seen: "2026-10-24"
    last_verified: "2026-10-24"
  - id: public-read-marker-mixins
    kind: rule-violation
    status: open
    verification: confirmed
    aspect: E
    cost: [ambiguity]
    population: modules
    members_affected: [billing, forms]
    rule_ref: "module_conventions rule 19"
    check: {kind: structural, state: proposed, model: contract-based}
    handoff: []
    first_seen: "2026-10-24"
    last_verified: "2026-10-24"
  - id: listings-publish-org-fallback
    kind: drift
    status: open
    verification: confirmed
    aspect: D
    cost: [ambiguity]
    population: modules
    members_affected: [listings]
    rule_ref: "decisions.md §Multi-org membership; §Fail-Hard Principle"
    check: {kind: conformance, state: proposed, model: contract-based}
    handoff: [tech]
    first_seen: "2026-10-24"
    last_verified: "2026-10-24"
  - id: stale-isolation-narratives
    kind: drift
    status: open
    verification: confirmed
    aspect: O
    cost: [tax]
    population: tenant-isolation-suites
    members_affected: [crm, social]
    rule_ref: "module_conventions rules 11 and 29; test evidence accuracy"
    check: {kind: review, state: proposed, model: contract-based}
    handoff: []
    first_seen: "2026-10-24"
    last_verified: "2026-10-24"
  - id: orgs-invitation-notification-failure
    kind: drift
    status: open
    verification: confirmed
    aspect: F
    cost: [defect, ambiguity]
    population: modules
    members_affected: [orgs]
    rule_ref: "module_conventions rules 20, 21, 43; failure policy unsettled"
    check: {kind: conformance, state: proposed, model: contract-based}
    handoff: [tech]
    first_seen: "2026-10-24"
    last_verified: "2026-10-24"
  - id: core-cli-module-knowledge
    kind: drift
    status: accepted
    verification: confirmed
    aspect: C
    cost: [tax]
    population: modules
    members_affected: null
    rule_ref: "accepted 2026-10-13; arch watchlist core-holds-module-vocabulary"
    check: {kind: structural, state: observed-in-source, model: open-world}
    handoff: [arch]
    first_seen: "2026-10-08"
    last_verified: "2026-10-24"
gaps:
  - {id: 21, rule: 17, state: closed, last_verified: "2026-10-25"}
  - {id: 22, rule: 37, state: closed, last_verified: "2026-10-26"}
  - {id: 23, rule: 19, state: open, last_verified: "2026-10-24"}
  - {id: 25, rule: 9, state: closed, last_verified: "2026-10-26"}
  - {id: 26, rule: 30, state: closed, last_verified: "2026-10-26"}
  - {id: 28, rule: 11, state: open, last_verified: "2026-10-24"}
  - {id: 29, rule: 23, state: open, last_verified: "2026-10-24"}
```

## Summary table

Current confirmed open items: **7**. Prior accepted: **1** (`core-cli-module-knowledge`). Prior items left unverified: **41** (the 2026-10-16 census IDs are not itemized in the retained report; last-known `resolved`, excluded from current counts). Pending candidates: **1** (`notifications-validation-status`), plus the residual leads in §10. Open enforcement gaps: **3** (23, 28, and 29; prior 21 closed 2026-10-25, 22 and 26 closed 2026-10-26, 25 closed 2026-10-26). Cost classes overlap; the unique confirmed-item total is 7: defect 1 · collision 0 · ambiguity 4 · tax 4.

| ID | Kind | Aspect / population | Cost | Affected / applicable | Status | Verification / confidence |
|---|---|---|---|---|---|---|
| `generated-module-branches` | rule-violation | L / generator-templates | tax, ambiguity | 4 template groups / all generated projects | resolved 2026-10-26 | fixed · high |
| `notifications-anymail-wiring-split` | rule-violation | B / modules | tax | 1/12 modules | resolved 2026-10-26 | fixed · high |
| `billing-feature-gate` | rule-violation | H / modules | ambiguity | 1/12 modules | fixed (was regressed) | fixed · medium-high |
| `billing-admin-org-filter` | drift | E / tenant-models | tax | 4/20 admin classes | fixed | fixed · high |
| `forms-tenant-isolation-evidence` | drift | M / tenant-isolation-suites | tax | 1/6 suites | open | confirmed · high |
| `tenant-suite-default-role` | drift | M / test-settings | tax | 3/12 suites | open | confirmed · medium-high |
| `crm-null-org-legacy` | rule-violation | G / tenant-models | tax, ambiguity | CRM + orgs shared admin | open | confirmed · high |
| `public-read-marker-mixins` | rule-violation | E / modules | ambiguity | 2/4 public-read mixins | open | confirmed · high |
| `listings-publish-org-fallback` | drift | D / modules | ambiguity | 1/2 publish services | open | confirmed · high on code, medium on reachability |
| `stale-isolation-narratives` | drift | O / tenant-isolation-suites | tax | 2/6 suites | open | confirmed · high |
| `orgs-invitation-notification-failure` | drift | F / modules | defect, ambiguity | 1/2 senders | open | confirmed · medium-high |
| `core-cli-module-knowledge` | drift | C / modules | tax | 6/12 modules | accepted | confirmed · high |

**Leading item.** `billing-feature-gate` now leads: `generated-module-branches` and `notifications-anymail-wiring-split` closed on 2026-10-26 when the core templates moved onto module declarations and rules 37/30 began enforcing the clauses. The closed items remain in the tables as the audit’s record.

## Aspect sections

### A/B — Identity, configuration, defaults, manifests

**Table A/B.1 — default and option consumption (12 manifests).**

| Variant | Count / members | Effective value | Evidence | State |
|---|---|---|---|---|
| Manifest default is the only default | 12/12 modules | defaults live in `module.yml`; runtime reads settings directly; rule 3 rejects a repeated code default | `*/module.yml`; `*/_settings.py`; harness rule 3 | present |
| Immutable option read by adapter | auth (`authentication_method`) | adapter branches on it and builds login/signup composites | `auth/adapter.py:29-42` | present |
| Option validation vocabulary | 12/12 | `choices`, `min`/`max`, `pattern`, `not_empty`, cross-option keys | `*/module.yml`; `module_conventions.md:318-391` | present |
| `required_modules` / `dependencies` present | 12/12 | both keys present; Django excluded as baseline; `quickscale-core` present | `*/module.yml`; harness rule 39 | present |
| Bundled manifests equal source manifests | 12/12 | byte-identical | `cmp` over `data/manifests/*/module.yml` | present |

**Already consistent (keep):** 12/12 modules have `QUICKSCALE_<MODULE>_ENABLED`, a manifest default for every mutable option, and a settings check registered from `ready()`. 12/12 adapters route through `build_generic_manifest_spec`; no adapter carries an `apps` literal. 4/4 `contract_vintage` declarations carry an `sa<NNN>-<slug>` id.

**Items:** `notifications-anymail-wiring-split` (settings half).

**Unknowns / exceptions:** A blank `MEDIA_URL` fails closed in the storage helper instead of falling back to a code literal.

### C — Dependencies, layering, vocabulary ownership

**Table C.1 — cross-module imports and named references (12 modules).**

| Variant | Members | Effective value | Evidence | State |
|---|---|---|---|---|
| Layer-respecting imports | 12/12 | no module imports a higher layer; same-layer direction acyclic | `quickscale_modules/*/src/**/*.py`; layer table `module_conventions.md:153-172` | present |
| Declared requirements cover imports | 12/12 | `required_modules` covers every imported first-party module | `*/module.yml`; import scan | present |
| Core/CLI module-specific vocabulary | 6/12 modules named | `contracts/module_options.py`, `manifest/social_manifest.py` | `contracts/module_options.py:17-105`; `manifest/social_manifest.py` (512 lines) | accepted exception |
| Core generator functional module branches | backups, orgs, notifications, credential modules | admin shortcut, CI/Makefile command, compose names, ANYMAIL settings | §L table; managed `project_blocks` regions; `quickscale_admin` tag; notifications adapter | resolved 2026-10-26 |
| Private-name imports across modules | 0 shipped source | only public surfaces / capabilities | import scan; harness rule 4 | present |

**Already consistent (keep):** no shipped module source imports another module’s private name; layer direction is one-way; `required_modules` includes every imported module. Docstring examples in orgs name higher-layer modules (`quickscale_forms_seed_presets`, `quickscale_crm_*`) but are not runtime references and the harness excludes docstrings.

**Items:** `generated-module-branches`, `notifications-anymail-wiring-split`. Prior accepted `core-cli-module-knowledge`.

**Unknowns / exceptions:** `core-cli-module-knowledge` remains accepted under the 2026-10-13 decision; trigger is a 13th module or a new module-named apply step. `AUTHORITATIVE_MODULE_COUNT` remains 12 and `social_manifest.py` remains 512 lines.

### D — Public surface and semantic contracts

**Table D.1 — service surface (12 modules).**

| Variant | Members | Effective value | Evidence | State |
|---|---|---|---|---|
| `services.py` with `__all__` and `is_enabled` | 12/12 | public surface is the declared list; keyword-only functions after at most one subject | `*/services.py`; harness rules 4, 23 | present |
| Error base | 10 modules with an error surface | `<Module>Error` base; analytics/forms no errors; backups re-exports core `BackupError` | `*/exceptions.py`; `core/runtime` | present |
| Write service requires explicit organization | blog | `create_published_post_from_payload(*, author, organization)` | `blog/services.py:362-367` | present |
| Write service optional organization with fallback | listings | `organization: Any = None`; contextvar then `get_system_org()` | `listings/services.py:71-80,107-112` | divergent |
| Public validation error without status mapping | notifications | `NotificationValidationError` / `NotificationTemplateError` in `__all__`; no `status_code`/`default_code` (pending candidate) | `notifications/exceptions.py:45-51`; `services.py:68-69` | unknown |

**Already consistent (keep):** all 12 service surfaces define `__all__`; public functions take keyword-only parameters after at most one leading subject; no inspected public service returns `None`/`False` to signal failure. Billing’s public exception subclasses and the notifications webhook/configuration classes declare `status_code`/`default_code`; blog/listings validation errors are caught by their views and mapped to 400. The notifications validation/template subclasses do not, which is the pending candidate above.

**Items:** `listings-publish-org-fallback`. Pending candidate: `notifications-validation-status`.

### E/H — Authorization, API shape, public read, admin

**Table E/H.1 — public-read declarations and tenant admin surfaces.**

| Variant | Members | Effective value | Evidence | State |
|---|---|---|---|---|
| Public-read mixin primes tenant context | blog, listings | `BlogPublicReadMixin(PublicSystemOrgReadMixin)`, `ListingsPublicReadMixin(PublicSystemOrgReadMixin)` | `blog/views.py:240`; `listings/views.py:103` | present |
| Empty public-read marker | billing (6 pages), forms (1 page) | empty class body; no context priming | `billing/views.py:427-434`; `forms/views.py:622-624` | divergent |
| Tenant admin uses `TenantModelAdmin` | 20/20 | all tenant-model admins | §G table; harness rule 13 | present |
| Tenant admin exposes organization list filter | 20/20 | every tenant admin lists it; billing's four since SA314 (b) | `billing/admin.py:47-122`; `organizations.md:635` | present |
| Tenant admin organization immutable on change | billing read-only; blog/crm shared mixin; forms local override; listings/social editable leaves | see §9 | `orgs/admin.py:425-560`; `forms/admin.py:71-78,170-177` | consistent by design, trigger noted |
| Public JSON error shape | billing/CRM/forms/blog/listings/orgs | one handler; module errors carry status/code where API-facing | `module_conventions.md:217-252` | present |
| Published gate decorator error shape | billing `require_org_feature`; orgs `require_org_role` is HTML-only | one declared-error shape (`401` anonymous, `402` `feature_not_available`); the HTML gate's blank `403` is the recorded exception | `billing/_settings.py:217-270`; `orgs/permissions.py:76-98`; rule 9 harness | present |
| Inbound webhook throttle | billing, notifications | empty throttle classes; signature is authentication | `billing/views.py:537-554`; `notifications/views.py:13-31`; rule 26 | present |

**Already consistent (keep):** every module page/API declares a guard; `is_staff` appears only in analytics’ traffic filter and orgs’ operator paths; org-role checks go through `user_has_org_role`/`HasOrgRole`; webhooks are signature-verified and return the shared accepted/duplicate body. The webhook empty throttle is consistent by design (rule 26), not the divergence the technical hand-off suspected.

**Items:** `public-read-marker-mixins`; `billing-feature-gate` and `billing-admin-org-filter` are fixed (§4–5).

### G — Data model basics and tenant contract

**Table G.1 — tenant model/admin/constraint census (22 models, 20 registered admins).**

| Variant | Members | Effective value | Evidence | State |
|---|---|---|---|---|
| `TenantModel` inheritance | 22/22 | direct or through `AbstractListing`/`BaseSocialItem`; `Meta` inherits base | `*/models.py`; harness rule 13 | present |
| `organization` NOT NULL `PROTECT` | 22/22 | `tenant_org_fk` null=False, PROTECT | `orgs/_tenancy_types.py:121-155` | present |
| Dead NULL-organization constraint | CRM Tag, Stage (2 constraints) | `condition=Q(organization__isnull=True)` can never match | `crm/models.py:43,156`; tests `test_models.py:55,206` | divergent |
| NULL-organization compatibility branch | CRM serializers; orgs shared admin form | accepts related rows with `organization_id=None` | `crm/serializers.py:64,190,357,446,624`; `orgs/admin.py:441-442` | divergent |
| User FK `SET_NULL` with listed CASCADE exceptions | 10 modules | 3 allowlisted CASCADE; no PROTECT | `orgs/tests/test_user_fk_conformance.py`; `decisions.md:693` | present |
| Constraint/index names | 28 constraints / 6 indexes | stemmed names; abstract `Index` exception | harness rule 25; `*/models.py` | present |
| `__str__` / `Meta.ordering` / choices | 12/12 | present or inherited; TextChoices used | harness rule 14 | present |
| Primary keys / `db_table` / `app_label` | 12/12 | BigAutoField default; no `db_table`/`app_label`; orgs UUID exception | harness rules 2, 14 | present |

**Already consistent (keep):** user-FK on_delete and tenant markers. The CRM null-bucket constraints are dead, not a live data path; the effective model is NOT NULL.

**Items:** `crm-null-org-legacy`.

### J — Commands and jobs

**Table J.1 — flag census (16 public commands).**

| Flag duty (rule 17) | Members | Evidence | State |
|---|---|---|---|
| Operator-scheduled → `--trigger` default `manual` | backups create/prune; forms anonymize | command `add_arguments`; README Operations | present |
| Deletes / anonymizes / overwrites → `--dry-run` | backups prune/restore/sync_media; billing reconcile; forms anonymize; orgs promote/purge | command flags | present |
| Cross-tenant delete → `--confirm` | backups restore; orgs purge | command flags | present |
| Org selector `--organization-id <uuid>` | billing reconcile; orgs purge (slug preflight beside it) | command flags | present |
| `--format` / `--org` / `--scheduled` spellings | 0 | flag census | present |
| Machine output `--json` | backups, billing, forms, orgs where machine output exists | command flags; README | present |
| Destructive operation chosen from a computed name | backups `pin` dispatches `ADAPTER_FUNCTIONS[operation]`; DR bridge same | gap 21 | present (computed dispatch requires `--dry-run`) |

**Already consistent (keep):** all commands subclass `BaseCommand`, use `self.stdout`/`self.stderr`/`self.style`, raise `CommandError` for expected failure, and the scheduled commands call `require_scheduled_module_enabled` before work. No `print`/`sys.exit` found. The org selector spelling is uniform after the prior fix.

**Items / gaps:** gap 21 is closed; no new command item.

### L — Files, packaging, and generation

**Table L.1 — module packaging (12 modules).**

| Variant | Members | Effective value | Evidence | State |
|---|---|---|---|---|
| Version 0.89.0 across `VERSION`, manifests, package `__version__`, pyproject | 12/12 | equal | `VERSION`; `*/module.yml`; `*/pyproject.toml`; `*/__init__.py` | present |
| pyproject template | 12/12 | same tables/literals; per-module slots only | `*/pyproject.toml`; `module-extension.md:480-540` | present |
| `--cov` target | 12/12 | `quickscale_modules_<name>` package, not `src/` path | `*/pyproject.toml` addopts | present |
| Bundled manifests | 12/12 | identical to source | `cmp` | present |
| One `0001_initial` per model-bearing module | 10/10 | auth, backups, billing, blog, crm, forms, listings, notifications, orgs, social | `*/migrations/` | present |
| Module file names | 12/12 | only allowed names or private `_<name>.py` | harness rule 28 | present |
| Module-specific functional branches in generator templates | 4 groups | admin index/app_index backups; CI/Makefile orgs; compose credential names; notifications ANYMAIL | managed `project_blocks` regions; `quickscale_admin` tag; notifications adapter | resolved 2026-10-26 |
| Allowed generator exceptions | 404 diagnostics; theme module surfaces; seam tables; `.env.example` catalog | rule 37/41 exceptions | `404.html.j2:111-131`; `runtime/seam.py`; `apply/steps/env_sync.py` | present |

**Already consistent (keep):** 12/12 module layouts, versions, pyprojects, bundled manifests, and migration freeze. `quickscale_modules/*/` contains no placeholder directory without `module.yml`. The four contract vintages all carry ids.

**Items:** `generated-module-branches`; `notifications-anymail-wiring-split` (settings half).

**Unknowns / exceptions:** `docker-compose.yml` is not in the retained U1/U3 ownership list; whether `apply` regenerates it is not established here. The admin index templates are U3 user-owned; the CI/Makefile are U1 user-owned. The backups admin shortcut and orgs CI/Makefile branches therefore cannot reach an existing project by update.

### M — Tests and conformance evidence

**Table M.1 — tenant isolation evidence (6 tenant modules).**

| Module | Required files | Tenant tables covered by RLS boundary | View-path regular-member test | Test settings default role | State |
|---|---|---|---|---|---|
| billing | present | 4/4 models | yes (`test_every_tenant_model_scopes…`) | `quickscale_test_role` | present |
| blog | present | 4/4 tables (cross-org 2) | yes | `quickscale_test_role` | present |
| crm | present | 7/7 tables | yes (`test_restricted_role_authenticated_list_view`) | `quickscale_test_role` | present |
| forms | present | 1/4 tables (`Form` only) | operator path only | `postgres` | divergent |
| listings | present | 1/1 table | yes | `postgres` | role divergent |
| social | present | 2/2 models | yes | `postgres` | role divergent |

**Already consistent (keep):** 12/12 modules ship `test_apps.py`, `test_services.py`, and `test_migrations.py` where they have models; 6/6 tenant modules ship `test_isolation.py` and `test_rls_boundary.py`; conftest hooks come from `quickscale_core.testing.pytest_plugin`; test names carry no ticket ids. The integration gate runs module suites through `provision_ci_postgres.sh --profile restricted`; the role divergence affects direct `pytest`/IDE runs, not the gate invocation.

**Items:** `forms-tenant-isolation-evidence`, `tenant-suite-default-role`, `stale-isolation-narratives`.

**Unknowns:** test bodies were not run; the coverage claim is a source inventory, not a pass. The isolation gate only explicitly runs CRM’s view-path test; blog/listings/forms/social view-path tests run in the normal integration suite.

### O — Documentation and convention governance

**Table O.1 — README and rule-document conformance (12 READMEs).**

| Variant | Members | Effective value | Evidence | State |
|---|---|---|---|---|
| Required headings in order | 12/12 | Overview, Configuration, Public surface, URLs, Management commands, Operations, Extending | `*/README.md`; harness rule 38 | present |
| Every option key / command / flag named | 12/12 | all found | README/options/commands census | present |
| Extending section covers the five standard items | 12/12 | each answers What QuickScale owns / What the project owns / Update-safe customizations / Structured extension points / Upgrade expectations | `module-extension.md:356-380`; all `## Extending` sections; harness rule 38 | present |
| Release stamps in module error strings | 12/12 | none | `*/src/**/*.py`; harness rule 29 | present |
| Isolation-test narratives describe current state | 4/6 current; CRM/social stale | CRM says no org FK/expected failure; social says assertion “confirms the gap” when it proves isolation | `crm/tests/test_isolation.py:1-22,126-134,232-240`; `social/tests/test_isolation.py:83,132` | divergent |
| Docs links resolve | 12/12 module READMEs; docs tree | only the prior coherence report had a broken `**kwargs` link, replaced by this rewrite | relative-link scan | present |

**Already consistent (keep):** README outline, option/command coverage, no versioned headings, no ticket ids in shipped source, module.yml descriptions have no release stamps, and rule documents are discoverable from `module-extension.md`/`START_HERE.md`.

**Items:** `stale-isolation-narratives`.

### P — Frontend and client

**Table P.1 — module surfaces.**

| Variant | Members | Effective value | Evidence | State |
|---|---|---|---|---|
| Seam-generated module flags/paths | all shipped modules except orgs | generated from `MODULE_CATALOG`/seam tables; orgs reports mode separately | `runtime/seam.py:60-270`; `frontend.md:262-284` | present |
| Module-declared SPA routes | blog, crm, listings | `spa_routes` in manifests, rendered by `apply` | `*/module.yml`; rule 41 | present |
| Host-rendered reservations | orgs `/orgs*`; forms `/forms*`; social `/social*` | stated rule 41 exceptions | `runtime/urls.py:63-111`; `frontend.md` | present |
| Module-specific admin/CI branches in generated templates | see L | managed `project_blocks` regions; `quickscale_admin` tag; notifications adapter | generator templates | resolved 2026-10-26 |

**Already consistent (keep):** no module ships TSX; the theme owns presentation; the seam and validator keys are generated from the shipped set; the 404 hint’s auth/billing path tests are diagnostics allowed by rule 41. The theme TSX was not read line by line; this is partial coverage, not a clean sweep.

**Unknowns:** Vite proxy duplication and the unhashed-filename convention are known frontend gaps (`frontend.md:314-321`), not re-audited here.

### F/S — write effects and notification senders

**Table F/S.1 — senders through notifications (2 modules).**

| Sender | Effect timing | Failure handling | Result on failure | Evidence | State |
|---|---|---|---|---|---|
| forms submission notification | `transaction.on_commit` after the submission write | catches `NotificationsError`; logs warning; submission remains | non-fatal; submission status unchanged | `forms/_email.py:105-121` | present |
| orgs invitation notification | `transaction.on_commit` after the invitation write | no catch; callback exception propagates after commit | 500 after the invitation row is committed | `orgs/views.py:174-193,306-325,409-424` | divergent |
| billing vendor checkout creation | before the local reservation write (exempt from rule 21) | provider error mapped to a billing error | local state not committed as paid | `billing/_checkout.py`; rule 21 | present |
| social cache purge | `transaction.on_commit` after the model write | `delete_many`; no cross-module sender | cache invalidated after commit | `social/models.py:148-158` | present |

**Already consistent (keep):** forms, billing, CRM’s stage seeding, social cache invalidation, and orgs’ invitation all schedule post-write effects with `transaction.on_commit`; the one divergence is the sender’s failure policy (item 15).

### I/K/N/R/S/T/U/V — remaining aspects

**Table X.1 — sampled cross-cutting observations.**

| Aspect | Variant | Members / count | Evidence | State |
|---|---|---|---|---|
| I outbound integrations | vendor clients constructed locally; provider errors translated in-module | billing Stripe, notifications Anymail, analytics PostHog, storage boto3, backups boto3 (5 clients) | `*/services.py`, `_stripe_client.py`, `_delivery.py`, `storage/_helpers.py` | partial: no shared timeout/retry budget policy is declared |
| K observability | package-derived logger names; split files use the facade channel | 12/12; 5 split-file examples | `billing/services.py:89`; `_subscription_mutations.py:52`; `forms/_email.py:27`; `blog/_anonymization.py:26`; `notifications/_delivery.py:33` | present, sampled |
| N tooling | module pyprojects share template; root mypy sections; CLI inert override | 12/12 pyprojects; 12/12 mypy sections; 1 inert CLI override | `*/pyproject.toml`; `mypy.ini`; `quickscale_cli/pyproject.toml` | partial: harness not run; inert override is a pending lead |
| R compatibility | contract-vintage ids; migration freeze | 4/4 vintages; 10/10 model-bearing module `0001_initial` | `*/module.yml`; `scripts/migration_hashes.json` | present; no mixed-version exercise |
| S asynchronous/delivery | webhook dedupe; on-commit effects | billing + notifications webhooks; 2 senders; social cache | §E/H.1, §F/S.1 | partial: item 15 is the one sender divergence |
| T runtime lifetime | no shared pool/worker policy in module code | 12/12 | module source scan | unknown: deployment capacity not inspected |
| U build/release | versions/pyprojects aligned; no build run | 12/12 | `VERSION`; `*/pyproject.toml` | partial |
| V data lifecycle | personal-data declarations and removal obligations | auth, orgs, billing, blog, crm, forms, notifications, backups | `*/apps.py`; `orgs/_personal_data.py` | partial: restore/retention not exercised |

**Already consistent or inert (no qualifying item):**

- **K observability:** module loggers are package-derived; split files log on their facade channel (billing `services`, forms `views`, blog `apps`, notifications `services`, orgs `debug_views`). No equal-name/different-unit telemetry collision found. Sampled only.
- **N tooling:** module pyprojects share the template; root mypy sections exist for all 12; `quickscale_cli/pyproject.toml` still carries an inert `[[tool.mypy.overrides]]` (root mypy.ini wins) — a low-cost candidate, not counted as a confirmed item because no runtime/contract cost was demonstrated.
- **R compatibility:** 4/4 contract vintages have ids; migration-freeze manifest matches shipped migrations; no mixed-version promise is asserted beyond the declared vintages. Not exercised.
- **S asynchronous/delivery:** billing/notifications webhook dedupe paths are unique-key based; forms/orgs `on_commit` effects were traced; the orgs invitation failure is item 15. No broker/queue surface found.
- **T runtime lifetime:** no shared pool/worker policy in module code; not exercised. Unknown deployment capacity.
- **U build/release:** versions and package metadata are aligned; no build, wheel, publish, or provenance check was run. The prior release-gate/version watchlists remain outside this audit.
- **V data lifecycle:** personal-data declarations and removal obligations were read for auth, orgs, billing, blog, crm, forms, notifications, backups; no new missing declaration found. Backup/restore and live retention behavior were not exercised; the structural concern is on the arch watchlist (`tenant-removal-coverage`).

## Coherence items

### 1. `generated-module-branches` — module behaviour lives in core’s generated templates

- **ID / kind / status:** `generated-module-branches` · `rule-violation` · `resolved` (2026-10-26, SA320 (c)).
- **Aspect / population / context:** L (secondary C, O) · `generator-templates` · all generated projects; 4 functional template groups.
- **Table / evidence:** §L.1 rows 7–8.
  - backups admin shortcut in `templates/admin/index.html.j2:6-11` and `templates/admin/app_index.html.j2:5-16` (also duplicated under `templates/common/templates/admin/`): `app_label == "quickscale_backups"` and literal `/admin/quickscale_backups/backuppolicy/ops/create/`.
  - orgs CI/Makefile branches in `github/workflows/ci.yml.j2:105,115,124` and `Makefile.j2:5,50,67,70`: `selected_modules is none or "orgs" in selected_modules`, `quickscale_orgs_check_tenant_isolation`, `QUICKSCALE_ALLOW_BYPASSRLS=1`.
  - module credential names in `docker-compose.yml.j2:107-114`: billing, notifications, analytics, storage, and backups env names.
  - notifications vendor settings in `settings/base.py.j2:231-254` (also item 2).
  - Allowed, not counted: `404.html.j2:111-131` diagnostics; theme module surfaces; seam tables; `.env.example` catalog.
- **Difference and cost:** **tax / ambiguity.** Generated `templates/admin/*.html` are U3 user-owned (`generated_file_ownership.md:244-252`); `Makefile`/CI are U1 user-owned (`:217-227`); `settings/base.py` is user-owned (`:159-164`). A module rename, URL change, or new module with an admin shortcut/CI command requires editing core, and an existing project does not receive the change through `apply`/`update`; the `contract_vintage` list has no step for these surfaces. The admin shortcut also hardcodes an admin URL instead of resolving it.
- **Declared rule:** rule 37 (`module_conventions.md:760-798`) says code outside modules, **including generator templates**, computes the module set from discovery; `module_architecture.md:293-330` forbids per-module wiring blocks in core. The allowed exceptions do not include functional admin/CI/compose branches. The `.env.example` catalog exception covers only that catalog.
- **Options:** (a) declare generic manifest sections (for example `admin_entrypoints`, `ci_commands`) and render them; (b) move the admin shortcut into the backups module’s own change-list template and the CI command into a managed block; (c) record each branch as an approved explicit exception with a reason and revisit trigger.
- **Recommended rule:** *coherence proposal 1* — Generator templates outside the listed presentation/diagnostic exceptions contain no per-module branch or module-prefixed constant. Module-specific admin/CI/compose behavior is declared by the module (manifest or module-owned template) or emitted from a managed generic block; core never names the module.
- **Enforcement (2026-10-26):** rule 37’s template scan now reads each Jinja tag for a quoted module name and each template for a module-prefixed token (`_identity_module_lists.py`); control cases reject a single-name branch or prefixed constant and accept the derived module set. Evidence state: `enforced`.
- **Migration / acceptance:** remove or declare the four groups; regenerate managed output; add a contract-vintage step for existing projects if a managed block replaces U1/U3 content; rollback by reverting the templates. Acceptance: a new module adds an admin/CI contribution through its own declaration with no core diff. Responsibility: core/generator owner plus module owners; existing roles only.
- **Resolution (2026-10-26, SA320 (c)):** the admin templates render a module-owned shortcut through the generic `quickscale_admin` tag, the Makefile/CI/Compose branches are marker-paired managed regions rendered from the module declarations, and rule 37 now catches a single-name template branch or module-prefixed constant with its fixture controls. Acceptance: a new module adds the contribution through its own declaration with no core diff.
- **Confidence / hand-off:** high · arch (`generated-file-ownership-unmodeled` is the structural root; this is a narrower instance not in that finding’s theme-only evidence).

### 2. `notifications-anymail-wiring-split` — one module’s vendor settings live in two homes

- **ID / kind / status:** `notifications-anymail-wiring-split` · `rule-violation` · `resolved` (2026-10-26, SA320 (c)).
- **Aspect / population / context:** B (secondary C) · `modules` · notifications; 1/12 modules.
- **Table / evidence:** §A/B.1 and §L.1. Notifications’ adapter sets `EMAIL_BACKEND` (`notifications/adapter.py:132-135`), but the `ANYMAIL` map is composed in the generated base template from `QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR`, `..._WEBHOOK_SECRET_ENV_VAR`, and `..._RESEND_DOMAIN` (`settings/base.py.j2:231-254`). The manifest declares neither `ANYMAIL` nor a derived setting for it (`notifications/module.yml:153-163`).
- **Difference and cost:** **tax.** A module settings contract has two homes; a rename or a provider change requires a core edit and does not reach an existing user-owned `settings/base.py`. The adapter can compute the map from resolved options; the current split hides that.
- **Declared rule:** rule 30 (`module_conventions.md:636-648`) — a module’s wiring writes its own settings; `module_architecture.md:293-330` — no per-module wiring in core. `settings/base.py` is user-owned (`generated_file_ownership.md:159-164`).
- **Options:** (a) notifications adapter contributes `ANYMAIL` from resolved options; (b) manifest-derived nested setting; (c) a managed settings block.
- **Recommended rule:** *coherence proposal 2* — Every setting a module needs, including nested vendor settings, is written by that module’s adapter/manifest; core templates carry only generic composition.
- **Enforcement (2026-10-26):** rule 30 reads every core generator template outside the theme tree and rejects a `QUICKSCALE_<MODULE>_*` token (`_settings_core_templates.py`); control case accepts the generic `MODULE_SETTINGS`/`compose_rest_framework(...)` composition. Evidence state: `enforced`.
- **Migration / acceptance:** move the block to notifications; regenerate managed settings; existing projects adopt through a contract vintage or manual step; rollback by restoring the block. Acceptance: changing a notifications env-var option changes only module-owned output. Responsibility: notifications owner.
- **Resolution (2026-10-26, SA320 (c)):** the notifications adapter writes `ANYMAIL` from its resolved options, the generated base settings template carries only the generic `MODULE_SETTINGS` application, and rule 30 now rejects a core template that reads `QUICKSCALE_<MODULE>_*` with its fixture controls. Acceptance: changing a notifications env-var option changes only module-owned output.
- **Confidence / hand-off:** high · arch.

### 4. `billing-feature-gate` (reopened) — published gate returns an unshaped 402

- **ID / kind / status:** `billing-feature-gate` · `rule-violation` · `fixed` · was `regressed: true` (prior `unauthenticated-status-code` cell).
- **Aspect / population / context:** H (secondary E) · `modules` · billing’s published `require_org_feature`; 1/12 modules.
- **Table / evidence:** §E/H.1 row 7. `billing/_settings.py:216-253` returns bare `HttpResponse(status=402)` at four paths; the tests assert 402 for anonymous and no-context (`tests/test_feature_gate.py:143-191`); README calls it the plan-feature gate (`billing/README.md:120-126`). The same shape issue exists in orgs’ `require_org_role` (`orgs/permissions.py:54-83`) if it is applied to a JSON endpoint.
- **Difference and cost:** **ambiguity.** A client that parses the one QuickScale error shape receives an empty body; a 402 without a code cannot be distinguished from `InsufficientCreditsError` (also 402); an anonymous caller receives 402 instead of the declared 401. The decorator is published for project use, so the cost lands on project views.
- **Declared rule:** rule 9 (`module_conventions.md:217-252`): every JSON error has the one shape; session APIs answer 401; module code builds no error body. Rule 19 for the anonymous outcome.
- **Options:** (a) raise a billing error subclass with `status_code=402` and `default_code` (mapped by the one handler) and `NotAuthenticated` for anonymous; (b) return a DRF `Response` with the shape; (c) document the decorator as HTML-only and return 401/403 there.
- **Recommended rule:** *coherence proposal 4* — A published gate decorator that may wrap a JSON endpoint returns the one QuickScale error shape with a stable code and the correct 401/403/402 class; an HTML-only gate is named/documented as such.
- **Enforcement:** rule 9's harness scans published gate decorator factories and requires a raise of a declared module error; controls accept a shaped `402` and a `401` anonymous gate, reject a bare response, and record orgs' HTML-only gate as the exception. Evidence state: `enforced`.
- **Migration / acceptance:** add the error class/response; update tests; existing project views get the shape after the module upgrade; rollback by restoring the old decorator. Acceptance: a feature-gated JSON view answers `{"error":{"code":…}}` and anonymous is 401. Responsibility: billing owner.
- **Confidence / hand-off:** medium-high (code confirmed; JSON use is the documented intent, not a shipped module endpoint) · tech.
- **Resolution (2026-10-26, SA314 (b)):** `require_org_feature` raises `NotAuthenticated` for an
  anonymous caller and `OrgFeatureUnavailableError` (`402`/`feature_not_available`) when the
  organization is unentitled; the one QuickScale handler renders both, and the gate documents that
  it wraps an API view. Rule 9's harness now scans published gate decorators, rejects a bare error
  response, and records orgs' HTML-only `require_org_role` as the sanctioned exception; the shaped
  and bare controls pass.

### 5. `billing-admin-org-filter` — billing’s tenant admins omit the organization filter

- **ID / kind / status:** `billing-admin-org-filter` · `drift` · `fixed`.
- **Aspect / population / context:** E (secondary O) · `tenant-models` · 20 registered tenant-model admins; billing 4.
- **Table / evidence:** §E/H.1 row 4. `billing/admin.py:47-116` — `CreditBalanceAdmin` has no `list_filter`; `CreditTransactionAdmin` filters `transaction_type, created_at`; `SubscriptionAdmin` filters `status, plan`; `PurchaseCheckoutAdmin` filters `status, plan`. The other 16 tenant admins include `organization` in `list_filter` (blog 4, CRM 7, forms 2 custom, listings 1, social 2).
- **Difference and cost:** **tax.** `organizations.md:635` says org-aware admin list views should expose an `organization` column and list filter so the operator can focus on a client. Billing is the most sensitive tenant surface and the only one without it; the operator must know the raw `organization__id__exact` query parameter.
- **Declared rule:** `organizations.md` §Admin Panel Contract (`:631-637`), a recorded operator contract.
- **Options:** add `"organization"` to `list_filter`; use forms’ always-rendered `OrganizationListFilter` for the System-only fresh project; leave read-only filters as-is.
- **Recommended rule:** *coherence proposal 5* — Every tenant-model admin exposes the organization column and an organization filter, even when the model is read-only.
- **Enforcement:** rule 13's admin census requires a tenant admin's organization column and filter (the plain field or a module's selector class), following module-local bases; the control rejects an admin without them. Evidence state: `enforced`.
- **Migration / acceptance:** add the filter to the four classes; no data migration; rollback trivial. Acceptance: each admin changelist shows the filter. Responsibility: billing owner.
- **Confidence / hand-off:** high · none.
- **Resolution (2026-10-26, SA314 (b)):** all four billing tenant admins expose `organization` in
  `list_display` and `list_filter`; rule 13's harness requires the pair on every tenant-model
  admin, follows module-local admin bases, and has a control that rejects an admin without them.

### 6. `forms-tenant-isolation-evidence` — forms’ RLS proof covers one of four tenant tables

- **ID / kind / status:** `forms-tenant-isolation-evidence` · `drift` · `open`.
- **Aspect / population / context:** M · `tenant-isolation-suites` · 6 tenant modules; forms.
- **Table / evidence:** §M.1 row 4. `forms/tests/test_rls_boundary.py:5,26,89,104,124,203` states and tests only the `quickscale_forms_form` table; `_FORMS_TABLES` (all four) is used only for grants (`:72`). `forms/tests/test_isolation.py` has only the superuser operator path and a staff fail-closed path; no regular-member cross-tenant view test. Billing loops 4/4, CRM 7/7, social 2/2, blog 4/4, listings 1/1.
- **Difference and cost:** **tax.** A regression in RLS on `FormSubmission`, `FormField`, or `FormFieldValue`, or in the forms admin view scoping, would not be caught by the forms suite; these are the submission payload and personal-data tables. The gate runs the suite, so this is a gate-coverage gap, not only local.
- **Declared rule:** rule 11 required `test_isolation.py` + `test_rls_boundary.py` for tenant models (`module_conventions.md:298-316`); decisions require FORCE-RLS on all 22 tenant tables (`decisions.md:683`).
- **Options:** loop all four tenant tables in the RLS boundary test (parameterized), add a regular-member view-path test, or add a separate forms-only view test.
- **Recommended rule:** *coherence proposal 6* — A tenant module’s RLS boundary test exercises every enrolled tenant table with matching, non-matching, and unset org context, and its isolation test exercises the regular-member view path.
- **Enforcement:** proposed test-coverage check over `test_rls_boundary.py` table names vs `TenantModel` subclasses; control case rejects a suite that names one table and accepts a parameterized suite. Evidence state: `proposed`.
- **Migration / acceptance:** extend the suite; no product change. Acceptance: all four tables appear in the restricted-role assertions. Responsibility: forms owner.
- **Confidence / hand-off:** high · none.

### 7. `tenant-suite-default-role` — three tenant suites default to a superuser connection

- **ID / kind / status:** `tenant-suite-default-role` · `drift` · `open`.
- **Aspect / population / context:** M (secondary N) · `test-settings` · 12 test settings; 3 tenant suites.
- **Table / evidence:** §M.1 rows 4–6. `billing/tests/settings.py:101`, `blog/...:80`, `crm/...:48` pass `user="quickscale_test_role"`; `forms/...:105`, `listings/...:80`, `social/...:75` call `suite_database("<module>")`, whose default is `postgres` (`core/testing/settings.py:55-67`). The integration gate overrides via `provision_ci_postgres.sh --profile restricted`, but a direct `pytest` or IDE run uses the default.
- **Difference and cost:** **tax.** A developer running the forms/listings/social suite directly can silently run as a superuser, which bypasses RLS; the same command in billing/blog/crm runs restricted. The docs say a single module suite requires a restricted role (`development.md:272-274`), so the defaults contradict the stated expectation and produce weaker local evidence.
- **Declared rule:** `validation_policy.md:179-183` (integration role `NOSUPERUSER NOBYPASSRLS`); proposed rule.
- **Options:** default all tenant suites to `quickscale_test_role`; require `QS_*_DB_USER`; document the asymmetry. Non-tenant suites can keep `postgres` where they need migration/role setup.
- **Recommended rule:** *coherence proposal 7* — Every suite for a module with tenant models defaults its connection to the restricted role; an environment variable may override, but the default never bypasses RLS.
- **Enforcement:** proposed check on `tests/settings.py` for tenant modules; control case rejects a default `postgres`. Evidence state: `proposed`.
- **Migration / acceptance:** change three defaults; ensure the provisioning helper grants the role; no product change. Acceptance: direct `pytest` connects as the restricted role. Responsibility: forms/listings/social owners.
- **Confidence / hand-off:** medium-high (default and gate behavior confirmed; whether direct superuser runs are considered supported is not recorded) · none.

### 8. `crm-null-org-legacy` — a NULL-organization state the model cannot hold

- **ID / kind / status:** `crm-null-org-legacy` · `rule-violation` · `open`.
- **Aspect / population / context:** G (secondary B) · `tenant-models` · CRM models/serializers and orgs’ shared admin form.
- **Table / evidence:** §G.1 rows 3–4. `TenantModel.organization` is `tenant_org_fk` with `null=False` (`orgs/_tenancy_types.py:121-155`). CRM `Tag` and `Stage` still declare partial unique constraints with `condition=Q(organization__isnull=True)` (`crm/models.py:43,156`) and tests assert those names (`crm/tests/test_models.py:55,206`). CRM serializers accept related rows whose `organization_id is None` as “legacy/solo compatibility” (`crm/serializers.py:64,190,357,446,624`), and orgs’ shared `make_same_org_validated_form` accepts NULL-org related values (`orgs/admin.py:441-442`). CRM tests state the post-0006 contract: NULL-owned stages no longer exist and are not accepted (`test_services.py:108`, `test_serializers.py:1772`).
- **Difference and cost:** **tax / ambiguity.** The NULL bucket can never match; the dead constraints and branches teach authors a compatibility rule that the schema forbids. The shared admin helper is used by blog and CRM, so the dead acceptance is in a foundation. No live defect found: the database refuses the state.
- **Declared rule:** rule 13 tenant models; the recorded post-0006 CRM contract in the tests.
- **Options:** remove the two null-bucket constraints and the NULL checks; keep them with an explicit, tested legacy data path; add a tenant-relation non-null check.
- **Recommended rule:** *coherence proposal 8* — Tenant-scoped relations are NOT NULL; a compatibility branch for a NULL organization is removed together with its constraint and test, or backed by a named legacy-data decision and a reachable migration.
- **Enforcement:** proposed AST/constraint check for `organization__isnull` on a NOT NULL tenant field and for `organization_id is None` acceptance in tenant serializers/forms; control case rejects the current CRM pattern. Evidence state: `proposed`.
- **Migration / acceptance:** remove constraints/branches/tests; no data migration (state cannot exist); rollback by reverting code. Acceptance: no NULL-org branch/constraint remains outside a documented exception. Responsibility: CRM + orgs owners.
- **Confidence / hand-off:** high · none.

### 10. `public-read-marker-mixins` — two “public read” mixins do not prime public context

- **ID / kind / status:** `public-read-marker-mixins` · `rule-violation` · `open`.
- **Aspect / population / context:** E · `modules` · 4 public-read mixins; billing 6 pages, forms 1 page; blog/listings real mixins.
- **Table / evidence:** §E/H.1 rows 1–2. `BlogPublicReadMixin(PublicSystemOrgReadMixin)` and `ListingsPublicReadMixin(PublicSystemOrgReadMixin)` override `get_public_org`; `BillingPublicReadMixin` (`billing/views.py:427-434`) and `FormPagePublicReadMixin` (`forms/views.py:622-624`) are empty class bodies. The forms page only renders a React mount div today; the billing pages read global `Plan` rows and `request.user`.
- **Difference and cost:** **ambiguity.** The name promises the public-read context pattern (rule 19) but the empty mixin does not wrap `dispatch()` in `org_scope`, so a future DB read added to the page would be unscoped instead of fail-closed. The harness accepts any `*PublicReadMixin` by name (`_routes_authorization.py:56-62`), so it cannot tell a marker from an implementation.
- **Declared rule:** rule 19 (`module_conventions.md:497-522`): a module-owned `*PublicReadMixin` is “built on that pattern.”
- **Options:** inherit `PublicSystemOrgReadMixin` (even if today’s page does no tenant query); use a distinct no-DB marker and document it; make the name require the behavior.
- **Recommended rule:** *coherence proposal 10* — A `*PublicReadMixin` either inherits the orgs public-context mixin or is documented as a no-DB presentation marker; a page that reads tenant data uses the priming mixin.
- **Enforcement:** proposed rule 19 check for the mixin body/base or a documented no-DB declaration; control cases for both. Evidence state: `proposed`.
- **Migration / acceptance:** change billing/forms mixins; no data migration; rollback trivial. Acceptance: a public page with a tenant query runs under System-org context. Responsibility: billing/forms owners.
- **Confidence / hand-off:** high · none.

### 11. `listings-publish-org-fallback` — the publish service defaults to the System org

- **ID / kind / status:** `listings-publish-org-fallback` · `drift` · `open`.
- **Aspect / population / context:** D (secondary B) · `modules` · 2 publish services.
- **Table / evidence:** §D.1 rows 3–4. Blog’s service requires `organization` keyword-only (`blog/services.py:362-367`). Listings’ service declares `organization: Any = None` (`listings/services.py:71-80`) and, when omitted, resolves the ContextVar or `Organization.objects.get_system_org()` (`:107-112`); the view passes `getattr(request, "org", None)` (`listings/views.py:75`). CRM and billing write paths refuse a missing org (`crm/views.py:44-58`; `billing/views.py:65-82`).
- **Difference and cost:** **ambiguity.** A project caller that omits `organization` silently publishes into the System org, which owns public content; a superuser or direct service call can reach this path. The decisions say the server session is the sole org authority and the fail-hard principle forbids silent fallback (`decisions.md:153-159,584-598`). The blog service already models the explicit contract.
- **Declared rule:** decisions §Multi-org membership and §Fail-Hard; rule 3 (no runtime default).
- **Options:** require `organization` keyword-only (no default) and fail closed in the view; keep the fallback only on an explicit public path; add a separate public helper.
- **Recommended rule:** *coherence proposal 11* — A write service requires an explicit organization (or an explicit public-context marker); it never selects the System org silently.
- **Enforcement:** proposed signature/AST check and a control call without organization; evidence state `proposed`.
- **Migration / acceptance:** change the signature and view; update callers/tests; no data migration. Acceptance: omitting the organization raises `TypeError` or a module validation error, not a System-org write. Responsibility: listings owner.
- **Confidence / hand-off:** high on code divergence, medium on reachability (the HTTP middleware usually supplies an org) · tech.

### 13. `stale-isolation-narratives` — two isolation suites describe a pre-fix world

- **ID / kind / status:** `stale-isolation-narratives` · `drift` · `open`.
- **Aspect / population / context:** O (secondary M) · `tenant-isolation-suites` · 6 suites; CRM and social.
- **Table / evidence:** §O.1 row 5. CRM’s module docstring says “CRM models have no `organization` FK … data from one organization is visible to every other organization today” and “These tests document that failure” (`crm/tests/test_isolation.py:1-10`); the class docstring still says the leak “is expected to fail today” (`:126-134`); a test docstring says it “stays RED on v87” (`:232-240`) although the test now asserts isolation. Social’s two assertion messages say “This confirms the cross-tenant isolation gap” when the assertion is that isolation works (`social/tests/test_isolation.py:83,132`). Blog, billing, listings, forms narratives describe the current state.
- **Difference and cost:** **tax.** A maintainer or auditor reading the suite cannot tell whether isolation is enforced; the stale text pins a fixed Finding 11 and a v87 status that no longer applies. This is test evidence, not a live defect.
- **Declared rule:** rules 11/29 test evidence; the test files should describe what they protect (rule 11). Rule 29 bans ticket ids in tests; these are Phase/Finding references, not ticket ids.
- **Options:** update the docstrings/messages to current state; add a review checklist for stale “expected to fail”/“gap” language; leave as historical.
- **Recommended rule:** *coherence proposal 13* — A test’s module/class docstring and assertion messages describe the current contract; a historical failure belongs in the changelog, not as present-tense test evidence.
- **Enforcement:** review-only (no reliable static check for stale prose); control is a review of the tenant isolation suite. Evidence state: `proposed`.
- **Migration / acceptance:** rewrite CRM/social prose; no code change. Acceptance: no present-tense “leak exists”/“expected to fail” claim in a passing isolation test. Responsibility: CRM/social owners.
- **Confidence / hand-off:** high · none.

### 15. `orgs-invitation-notification-failure` — the invitation is committed, then a send failure escapes as 500

- **ID / kind / status:** `orgs-invitation-notification-failure` · `drift` · `open`.
- **Aspect / population / context:** F (secondary S, D) · `modules` · 2 notification senders; orgs.
- **Table / evidence:** §F/S.1. Forms’ `_email.py:105-121` catches `NotificationsError` and logs a best-effort failure. Orgs’ `save_invitation_form` calls `sender(...)` inside `transaction.on_commit` without a catch (`orgs/views.py:174-193`); the outer `transaction.atomic()` in `form_valid`/the API view commits before the callback runs, so a `NotificationDisabledError`, `NotificationValidationError`, or `NotificationTemplateError` propagates after the invitation row is committed. The same callback is used by both HTML and JSON invitation flows (`views.py:306-325,409-424`).
- **Difference and cost:** **defect / ambiguity.** A failed send leaves a saved invitation but returns 500; the caller cannot tell whether the invite exists, and a retry may hit the duplicate/pending guard. Forms treats the same class of failure as non-fatal; the two senders disagree on the contract.
- **Declared rule:** rules 20, 21, and 43 (`module_conventions.md:524-542,899-909`); the failure policy is not settled.
- **Options:** (a) catch `NotificationsError` after commit, log, and surface a warning/delivery status (forms’ model); (b) send before commit and roll back the invitation on failure (contradicts rule 21’s on-commit convention); (c) an outbox/delivery record with reconciliation.
- **Recommended rule:** *coherence proposal 15* — A sender’s post-commit failure has one recorded policy: either a committed write remains and the failure is surfaced/logged, or the write is not committed until the send is accepted; no sender leaves an unhandled exception after commit.
- **Enforcement:** proposed test that a failing sender leaves a coherent outcome (row + failure state or no row), plus a review of every `on_commit` sender. Evidence state: `proposed`.
- **Migration / acceptance:** choose the policy (Q2); update orgs; add a failure-injection test; no data migration unless an outbox is added. Acceptance: a forced sender failure does not produce a bare 500 with an unmarked committed invite. Responsibility: orgs/notifications owners.
- **Confidence / hand-off:** medium-high (failure paths read; the exact supported policy is unknown) · tech.

### Prior accepted item

`core-cli-module-knowledge` remains **accepted** under the 2026-10-13 decision: core/CLI name module-specific vocabulary in `contracts/module_options.py` and `manifest/social_manifest.py` (512 lines), with six modules named. Rechecked 2026-10-24; `AUTHORITATIVE_MODULE_COUNT` is still 12 and the trigger (13th module or a new module-named apply step) has not fired. It is not counted among current open items. Hand-off: arch watchlist `core-holds-module-vocabulary`.

## Proposed rules

These are paste-ready proposals. Proposals 3, 4, 5, 9, 12, and 14 are adopted and retained as the settled rule text; the rest are not settled decisions. They are separated from settled-rule compliance work.

**Coherence proposal 1 — Generated templates name no module.** Generator templates outside the listed presentation/diagnostic exceptions contain no per-module branch, constant, URL, or module-prefixed setting. Module-specific admin, CI, compose, or settings behaviour is declared by the module (manifest or module-owned template) or emitted from a managed generic block. Allowed: the 404 path diagnostics (rule 41), the theme’s module surfaces (rules 31/37), the seam tables, and the `.env.example` managed catalog.

**Coherence proposal 2 — One home for module settings.** Every setting a module needs, including nested vendor settings, is written by that module’s adapter or manifest. Core templates carry only generic composition and never name `QUICKSCALE_<MODULE>_*` or a vendor block owned by one module.

**Coherence proposal 3 — Every option has a live consumer (adopted).** An accepted manifest option projects a setting that a supported path reads or enforces. An option with no consumer is removed or rejected with a clear “not supported” message; a “reserved” option is not accepted silently.

**Coherence proposal 4 — Published gates return the API shape (adopted).** A published gate decorator that may wrap a JSON endpoint returns the one QuickScale error shape with a stable code and the correct 401/403/402 class; an HTML-only gate is named and documented as such.

**Coherence proposal 5 — Tenant admin operator contract (adopted).** Every tenant-model admin exposes the organization column and an organization list filter, even when the model is read-only, so the per-org operator path is usable without a raw query parameter.

**Coherence proposal 6 — Tenant isolation evidence is complete.** A tenant module’s RLS boundary test exercises every enrolled tenant table with matching, non-matching, and unset org context; its isolation test exercises the regular-member view path, not only the operator path.

**Coherence proposal 7 — Tenant suite defaults are restricted.** Every suite for a module with tenant models defaults its database connection to the restricted role; an environment variable may override, but the default never bypasses RLS.

**Coherence proposal 8 — No NULL-tenant compatibility.** Tenant-scoped relations are NOT NULL. A compatibility branch for a NULL organization is removed with its constraint and test, or backed by a named legacy-data decision and a reachable migration.

**Coherence proposal 9 — README Extending standard (adopted).** Every module README’s Extending section answers the five standard questions (What QuickScale owns, What the project owns, Update-safe customizations, Structured extension points, Upgrade expectations) as mandatory level-three subsections; managed files and update expectations are named.

**Coherence proposal 10 — Public-read mixins prime context.** A `*PublicReadMixin` either inherits the orgs public-context mixin or is documented as a no-DB presentation marker; a page that reads tenant data uses the priming mixin.

**Coherence proposal 11 — Write services require an organization.** A write service requires an explicit organization (or an explicit public-context marker); it never selects the System org silently.

**Coherence proposal 12 — One default home (adopted).** A manifest default has one home; code constants either derive from the manifest or are removed.

**Coherence proposal 13 — Test evidence is current.** A test’s module/class docstring and assertion messages describe the current contract; a historical failure belongs in the changelog, not as present-tense test evidence.

**Coherence proposal 14 — Error messages name behaviour, not releases (adopted).** A module error message names the current behaviour; a support change is a release note, not a version stamp.

**Coherence proposal 15 — Post-commit send failure policy.** A sender’s post-commit failure has one recorded policy: either the committed write remains and the failure is surfaced/logged, or the write is not committed until the send is accepted; no sender leaves an unhandled exception after commit.

## Enforcement gaps

**Gap 21 (prior, closed 2026-10-25) — rule 17’s computed-operation hole.** `--json` is never required; `--trigger` is checked only when present; the destructive duty keys on the operation name (`_package_commands.py`). `quickscale_backups_pin` called `ADAPTER_FUNCTIONS[operation]` and the DR bridge called `ADAPTER_FUNCTIONS.get(function_name)`, so a computed destructive operation could escape the `--dry-run` duty. The detector now treats a computed adapter dispatch — an adapter-registry subscript with a non-literal key, and a name bound from `ADAPTER_FUNCTIONS.get(...)` and later called — as destructive by construction; both live commands declare `--dry-run` and honor it by reporting the intended call without writing. Control cases pass: a fixture computed `prune` without `--dry-run` fails and the same fixture with the flag passes.

**Gap 22 (closed 2026-10-26) — rule 37’s template scan sees enumerations, not single-name branches.** `_template_module_literals` still counts a bracket/pipeline list, and the scan now also reads each Jinja tag for a quoted module name and each template's `QUICKSCALE_<MODULE>_*`, `quickscale_modules_<module>`, `quickscale_<module>_*`, and `modules/<module>/` tokens (`_identity_module_lists.py`). The theme's declared module surface and the generated isolation test's dormant runtime gate are the recorded exceptions. Controls: a fixture template with a single module branch or prefixed constant fails; the derived discovery template and non-module core tokens pass. State `closed`; linked item 1.

**Gap 23 — rule 19 accepts a public-read mixin by name only.** `PUBLIC_READ_MIXIN_SUFFIX` and `_is_sanctioned_guard_name` accept any `*PublicReadMixin` (`_routes_authorization.py:31-62`); there is no check that it subclasses `PublicSystemOrgReadMixin` or primes context. Control: an empty mixin should fail; the blog/listings mixin should pass. State `observed-in-source`; linked item 10.

**Gap 25 (closed 2026-10-26) — rule 9 does not scan published gate decorators.** The harness scanned module views and module-owned helpers; `require_org_feature` was a decorator returning `HttpResponse`, not a view, so the bare 402 was invisible. Rule 9's detector now scans gate decorator factories and rejects a bare error response; a shaped 402 is a raise of a declared module error, and orgs' HTML-only `require_org_role` is the recorded exception. Controls pass: a shaped gate and a 401 anonymous gate are accepted, a bare 402/403 is refused, and a recorded HTML-only gate is skipped. Linked item 4.

**Gap 26 (closed 2026-10-26) — rule 30 checks module adapters, not core templates.** `rule_30_settings_composition` reads every core generator template outside the theme tree and reports a `QUICKSCALE_<MODULE>_*` token; the notifications adapter now writes `ANYMAIL` and the generated base settings carries only the generic `MODULE_SETTINGS` application. Control: a core template that reads a module setting fails; the generic `MODULE_SETTINGS`/`compose_rest_framework(...)` composition passes. State `closed`; linked items 1–2.

**Gap 28 — rule 11 checks file presence, not isolation evidence.** It does not require every tenant table in the RLS boundary, a regular-member view test, or a restricted default role in `tests/settings.py`. Control: a one-table/one-operator-path suite fails; the all-table/restricted suite passes. State `observed-in-source`; linked items 6–7.

**Gap 29 — rule 23/3 does not require an explicit organization on a write service.** Listings’ optional `organization` and System-org fallback pass the signature and service-surface checks. Control: a write service with a defaulted organization fails; a keyword-only required organization passes. State `observed-in-source`; linked item 11.

## Consistent by design

- **`tenant-admin-authority` (technical/arch hand-off).** All 20 tenant-model admins use `TenantModelAdmin`; the explicit request selector is the documented per-org runtime-role admin contract (`organizations.md:204,631-637`). The content-route session authority and the admin request/session selector are two documented operator/page contexts, not two implementations of one check. Trigger: a non-superuser staff account; then the operator-only premise fails and the arch watchlist item reopens.
- **`notifications-pre-signature-db-read` / webhook throttle (technical hand-off).** Billing and notifications webhooks declare empty throttle classes; rule 26 says the provider retry burst must not be refused, and the signature is the authentication. The public forms/blog/listings endpoints have throttles because they are user-facing write surfaces. This is a declared difference, not drift.
- **Auth’s `templates/quickscale_auth/account/*` pages.** The 12 top-level `templates/account/*.html` files are one-line allauth override shims; the real pages live under the module folder and the rule 2/8 `account/` exception covers the vendor path. This was previously reported as a residual and is consistent by design (rule 2/8).
- **Tenant admin organization immutability.** Billing is read-only; blog/CRM use `OrgAwareAdminMixin`; forms carries an equivalent local read-only override; listings/social are leaf models with no child rows, so operator reassignment is a supported correction. Trigger: a project-owned child model under a leaf base; then use the shared mixin or make the parent org immutable.
- **Composite-FK helper duplication in frozen migrations.** CRM/forms migrations carry a private `_add_composite_fk` with a `NOT VALID`/`VALIDATE` sequence while blog uses the shared `add_composite_child_fk`; the applied files are frozen from 0.89.0. New migrations must use the shared helper; a source check for a new private helper is appropriate (pending lead, not an active item).
- **Forms/orgs host-rendered reservations.** `/forms*` and `/orgs*` stay host-rendered under rule 41; forms’ empty marker and the React reservation are a presentation/routing split, not a module contract difference.
- **`core-cli-module-knowledge`.** Accepted 2026-10-13; six modules are named in core/CLI vocabulary, and the 13th-module trigger has not fired. Not re-litigated.

## Hand-offs

**To the technical audit (live defects or live-defect risk).**

- `orgs-invitation-notification-failure` — a committed invitation plus an unhandled post-commit sender error; source links in item 15.
- `listings-publish-org-fallback` — a supported service call can write public content into the System org.
- Pending candidate `notifications-validation-status` — public `NotificationValidationError` has no `status_code`/`default_code`; no confirmed shipped API lets it escape except the orgs post-commit path. Not promoted without a reachable API trace.

**To the architectural audit (structural roots).**

- `generated-module-branches` — linked to `generated-file-ownership-unmodeled`; this pass adds the non-theme generated files (admin index, CI/Makefile, compose, base settings) that the arch finding’s theme-only evidence does not enumerate. Resolved 2026-10-26; retained as the hand-off record.
- `notifications-anymail-wiring-split` — linked to the module-wiring-authority root; module settings split across core and module. Resolved 2026-10-26.
- `core-cli-module-knowledge` — prior accepted, already on the watchlist.

**Companion lead dispositions.**

- `tenant-admin-org-selector` (tech) — consistent by design under the documented operator-only premise; trigger recorded above.
- `notifications-pre-signature-db-read` (tech) — the throttle divergence is consistent by design (rule 26); the pre-signature read itself was not re-traced as a live defect and remains a technical-audit lead.
- `admin-tenant-authority` (arch watchlist) — carried as the trigger on `tenant-admin-authority`; no new finding.

## Catalogue additions and residual work

**Catalogue:** no new aspect letter. The pass used A–V; the only cross-cutting addition is a generated-output-authority clause under L/O, captured as proposal 1. No new aspect is warranted without a population that the current catalogue cannot express.

**Add-one-more probe (paper).** Add a layer-3 module with one routed JSON list, one publish API, one webhook, one transactional email, one vendor secret, one scheduled command, and one tenant model. The normal path requires a manifest (`config`, `required_modules`, `dependencies`, `derivation`, `throttle_scopes`), an adapter, a package layout, a README, `MODULE_CATALOG`/`AUTHORITATIVE_MODULE_COUNT`, a mypy section, a `.env.example` catalog entry, and any seam/admin/CI rows. Settled by SA320 (c): (a) the admin/CI/compose hook is module-declared — a module-owned admin template, `project_blocks` regions, and `compose_env`; (b) nested vendor settings live in the module adapter (notifications writes `ANYMAIL`). Open choices the current contract does not settle for the author: (c) whether a new public page uses the priming mixin or the empty marker (item 10); (d) how a sender’s post-commit failure is handled (item 15); (e) whether the new module’s test settings default restricted (item 7) and which tables the RLS proof covers (item 6). Each is a forced decision, not a copy-source choice.

**Residual work and limits.**

- Theme TSX pages/hooks were not read line by line; the seam producer and surface tables were. A frontend-specific pass would be needed to close P.
- No repository test, harness, generator, build, linter, migration, or service was run. Every “present” in a test table is a source-inventory state, not a pass.
- The 2026-10-16 41-item census is not itemized in the retained report; its last-known resolved status is not re-established. A future pass should recover that index and reconcile each ID.
- Pending leads: `notifications-validation-status`; `backups/_settings.py` uses `build_policy_snapshot_from_settings()` rather than a `from_settings()` classmethod (rule 42 wording; possible accepted core-engine exception); `quickscale_cli/pyproject.toml` inert `[[tool.mypy.overrides]]`; `SeamModule.app_label` actually holds a package path; auth account-template nesting; leaf tenant admin org reassignment; `docker-compose.yml` ownership/regeneration. None passes §0 as a confirmed item on current evidence.
- Deployment unknowns: whether invitation email failure is considered fatal, whether tenant suites are ever run directly under `postgres`, and whether any non-superuser staff account exists.

## Questions that would change a rule

2. **Q2 (`orgs-invitation-notification-failure`):** Is an invitation email failure fatal (do not keep the invitation unless the send is accepted), or best-effort (keep the invitation, record/surface the failure)?
4. **Q4 (`tenant-suite-default-role`):** Is a direct `pytest` run under the default `postgres` role a supported workflow, or must every tenant suite default to the restricted role?
5. **Q5 (consistent-by-design trigger):** May a leaf tenant admin row be reassigned to another organization? If not, listings/social should use the shared immutable-org admin behavior.

## Reconciliation log

**Snapshot:** `82ff3e7d` (v89), 2026-10-24; dirty companion docs excluded; prior report `39d455ef` read only after the independent sweep.

**Prior open/accepted IDs (2026-10-13 index, recovered from `git show 30b0b6b1:docs/others/coherence-audit.md`).**

| Prior ID | This pass |
|---|---|
| `module-enabled-switch` | resolved (prior; off parity still checked); no regression found |
| `markdownx-shared-mount` | resolved (storage owns the shared mount) |
| `tenant-authorization` | resolved (20/20 tenant admins use `TenantModelAdmin`; guards present) |
| `option-schema-and-validation` | resolved (manifest schema/validation remains; the storage switch is retired) |
| `unauthenticated-status-code` | resolved (was regressed; SA314 (b) makes the gate answer 401 for anonymous) |
| `module-error-http-mapping` | resolved for module errors; `notifications-validation-status` remains a pending candidate |
| `startup-checks-and-errors` | resolved (no literal setting-list in `checks.py`; rule 6 allows prose) |
| `upward-name-references` | resolved (no runtime higher-layer references; docstring examples excluded) |
| `core-cli-module-knowledge` | accepted (decision 2026-10-13; trigger not fired) |
| `manifest-declared-surface` | resolved (regression closed; the inert switch is retired) |
| `http-api-shape` | resolved (billing per-page options; shared paginator) |
| `throttle-attachment` | resolved (manifest `throttle_scopes`; scoped class) |
| `optional-sender-guard` | resolved (forms/orgs guard per `required_modules`) |
| `module-dependency-direction` | resolved (no private cross-module imports) |
| `capability-collection` | resolved (`collect_capabilities`; declared hook names) |
| `command-flag-conventions` | resolved (all selectors `--organization-id`) |
| `dependency-spec-sources` | resolved (12/12 `--cov` package names) |
| `secret-env-var-names` | resolved (vendor defaults/module stems) |
| `session-and-host-names` | resolved (session keys stemmed) |
| `model-basics` | resolved (harness rule 14 coverage) |
| `template-folder-depth` | resolved (auth account shims are consistent by design) |
| `test-file-names` | resolved (no ticket ids; `test_<subject>.py`) |
| `ticket-ids-in-shipped-source` | resolved (0 found) |
| `constraint-purpose-tokens` | resolved (28 constraints / 6 indexes stemmed) |
| `mount-path-copies` | resolved (seam paths; no literal mounts) |
| `contract-vintage-identity` | resolved (4/4 ids) |

**Prior census:** the 2026-10-16 census of 41 IDs remains last-known `resolved`; the retained report does not itemize them, so none is re-verified here. They are excluded from the current confirmed count.

**Prior gap 21:** closed 2026-10-25; computed adapter dispatch is destructive by construction, and both live commands declare and honor `--dry-run`.

**This pass:** 11 open items (10 new + 1 regressed); 1 accepted prior item; 6 open gaps (22–23, 25–26, 28–29; prior 21 closed 2026-10-25); 1 pending candidate plus residual leads. Pass 1 walked A–V; pass 2 followed the generator-template, settings, admin, isolation, and notification-sender leads; pass 3 re-opened every cited anchor and the prior hand-offs and added no new item/aspect. Stopping reason: bounded saturation of the inspected scope; theme execution and live deployment remain unassessed.

- 2026-10-24 — `generated-module-branches`: new, open.
- 2026-10-24 — `notifications-anymail-wiring-split`: new, open.
- 2026-10-26 — `generated-module-branches`: **resolved** by SA320 (c); rule 37 enforces the clause.
- 2026-10-26 — `notifications-anymail-wiring-split`: **resolved** by SA320 (c); rule 30 enforces the clause.
- 2026-10-24 — `billing-feature-gate`: new, open; reopens `unauthenticated-status-code` for this decorator.
- 2026-10-24 — `billing-admin-org-filter`: new, open.
- 2026-10-24 — `forms-tenant-isolation-evidence`: new, open.
- 2026-10-24 — `tenant-suite-default-role`: new, open.
- 2026-10-24 — `crm-null-org-legacy`: new, open.
- 2026-10-24 — `public-read-marker-mixins`: new, open.
- 2026-10-24 — `listings-publish-org-fallback`: new, open.
- 2026-10-24 — `stale-isolation-narratives`: new, open.
- 2026-10-24 — `orgs-invitation-notification-failure`: new, open.
- 2026-10-24 — `core-cli-module-knowledge`: still accepted; trigger not fired.
- 2026-10-24 — gap 21: still open; gaps 22, 23, 25, 26, 28 and 29: new, open.
- 2026-10-25 — gap 21: closed; the computed-operation detector, both fixture controls, and the two commands' `--dry-run` handling landed.
- 2026-10-26 — `billing-feature-gate` and `billing-admin-org-filter`: fixed by SA314 (b); proposals 4 and 5 adopted, gap 25 closed with its gate controls.
