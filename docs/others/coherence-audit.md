# QuickScale — Deep Coherence Audit (cross-module conformance)

Audited: 30b0b6b1 (v89) · 2026-10-16 · working tree dirty (uncommitted `docs/others/arch-audit.md`, `docs/others/tech-audit.md`, and this file; the companions were read only for their hand-offs) · repository public (github.com/Experto-AI/quickscale) · prompt: deep-coherence-audit v2 · passes: 2 (full census, saturation not reached; earlier today: a 1-pass delta re-run at the same SHA; prior: 0ddc7e30, 2026-10-13)

> **Full census 2026-10-16 (b) (`30b0b6b1`).** Earlier today's delta re-run did not rebuild §4,
> and its coverage note asked for a full census. This pass rebuilds §4. The 2026-10-08 tables
> below it are kept as dated evidence. **Where they disagree, the census tables in §4 (2026-10-16),
> this block, the index, the summary, and the log win.**
>
> - **Method.** 7 parallel enumeration units read the 12 modules plus core, the CLI, the
>   generator, and the theme: A+L, B, C+D, E+F+G, H+I+K, J+M+N+O+P+Q, and the rule audit (§3.5,
>   §3.6). Three units got a second round to fill cells they had left open. The main agent judged
>   each card and re-read the anchors cited below.
> - **Passes: 2.** Pass 2 still added aspects: renderer pinning, the logger-name literals (killed
>   under rule 46), and the CLI membership branches. So saturation was **not** reached, and the
>   next pass must run a third census round before claiming it.
> - **Harness.** It still prints *All 43 covered module conventions pass*. Every new item below
>   sits in a clause the harness does not cover, or covers open-world.
> - **New open items: 15** (items 27–41). Counts: defect 0 · collision 0 · ambiguity 5 · tax 13
>   (an item can carry more than one class). Prior IDs: 25 still resolved, 1 accepted. None
>   regressed. The closest to a regression is `cli-module-name-branches`, which sits beside the
>   accepted `core-cli-module-knowledge`.
> - **Killed on judgment (12 cards):**
>   - The storage markdownx staff gate is rule 41's deliberate design.
>   - The `qs_` index names are rule 25's declared form.
>   - The logger-name literals are required by rule 46.
>   - Orgs' throttle classes are rule 32's listed exception.
>   - Billing's throttle scopes are mapped by its adapter (`adapter.py:44–48`).
>   - Notifications staying mounted when off: its one URL is the rule 26 webhook.
>   - Backups' `admin` trigger value follows its admin actions (`admin.py:421,441`).
>   - Blog reading `MEDIA_URL` is a Django setting, not storage's.
>   - The auth↔orgs `required_modules` cycle is an install contract, not an import.
>   - Single-positional public functions: there are 9, each takes one argument, and rule 18's
>     keyword-only clause starts at the second.
>   - Auth's two template trees are allauth shims (prior correction).
>   - Billing's reconcile command is not scheduled, so it needs no `--trigger`.
> - **Hand-offs:** 1 to the arch audit (`cli-module-name-branches`). None to the tech audit.


> **Re-run 2026-10-16 (`30b0b6b1`).** This pass is a delta re-run. It re-checked the 3 items
> left open at `0ddc7e30`, the accepted item, and the companions' new hand-offs, and it
> classified the delta. It did not rebuild the §4 tables, so they keep their dated values.
> **Where they disagree, this block, the index (§2), the summary (§3), and the log (§12) win.**
>
> - **Delta.** `git log --no-merges --since=2026-10-13` has 37 commits touching modules, core,
>   or the CLI. 6 apply a convention: SA282 (a/b), SA283 (a/b/c), and SA281 (a). The other 31 are
>   unrelated: DR, migrations, seam generation, gates, and fixes. The harness passing at HEAD
>   found 0 that break a convention.
> - **Harness.** `scripts/check_module_conventions.py` at HEAD prints *All 43 covered module
>   conventions pass*.
> - **Passes: 1.** Every open item closed with a check, and no new aspect came up.
> - **Resolved this pass (3):**
>   - `startup-checks-and-errors`: SA283(a) `1817ef2d`. The `checks.py` of analytics, billing,
>     and notifications read `projected_setting_names(<module>)`. The rule-6 scan
>     (`scripts/module_conventions/_package_legacy.py:131–158`) rejects a literal own-setting
>     name, with controls in `test_package.py`. The 2 literals left in orgs' `checks.py` (`:144`,
>     `:171`) are process environment flags, not settings, so they are outside the rule.
>   - `capability-collection`: SA283(b) `98d4e4b7`. The purge command now runs
>     `collect_capabilities("organization_cache_invalidation_hooks")`
>     (`quickscale_orgs_purge_organization.py:532`). The `getattr(app_config, hook)` lookups in
>     orgs `_removal_declarations.py:122,179,296–303` look up hooks that an obligation declares,
>     and they validate those hooks when the declaration loads. That is consistent by design (§8),
>     and they were present at the prior pass.
>   - `dependency-spec-sources`: SA283(c) `bf7e242e`. All 12 `pyproject.toml` addopts use
>     `--cov=quickscale_modules_<name>`.
> - **Accepted (1), carried:** `core-cli-module-knowledge` (rule 37's exception list). The arch
>   audit counts `CAPABILITIES` at +1 and the list flat, so the revisit trigger has not fired.
> - **Companion hand-offs taken in:**
>   - From the tech audit: `quickscale_backups_restore` still advertises `--file PATH` in its
>     help and usage errors (`:42`, `:46`, `:122–126`), while recovery refuses a bare file that
>     records no hashes (`dr_engine/recovery.py:288`). **Rejected under §0 gate 1:** it is one
>     command with no peer that does it differently, so it is a defect for the tech audit, not
>     drift. (It is also not handed back, because the tech audit already holds it.)
>   - Blog and listings throttle per user, forms per IP: still consistent by design.
>   - From the arch audit: dr_engine's `ModuleNotFoundError` check, copied in 2 files, stays
>     below the population threshold.
> - **Open: 0.** Counts: defect 0 · collision 0 · ambiguity 0 · tax 0. Enforcement gaps 1–5
>   from 2026-10-13 are carried and still unchecked. Gaps 6 (`--cov`) and 7 (vintage id) are closed.
> - **Hand-offs from this pass:** none to either companion.
> - **Coverage limit.** Without a full census, a drift that the harness's 43 rules do not cover
>   could have entered with the 31 unrelated commits. The next full pass should rebuild §4.

> **Re-run 2026-10-13 (`0ddc7e30`).** This pass re-checked every item that was open at
> `2fd8637f` against HEAD, and swept the delta for new variants. The aspect tables in §4 and
> the items in §5 keep their 2026-10-08 values as dated evidence. **Where they disagree, this
> block, the index (§2), the summary (§3), and the log (§12) win.**
>
> - **Delta.** `git log --no-merges --since=2026-10-08` has 38 commits that touch modules, core,
>   or the CLI. 27 apply a convention (SA251–SA266), 9 are unrelated, and 2 break one:
>   - `9592bab5`, SA251(b): the reconcile command's org selector;
>   - `dbe561a7`, SA254: orgs' invite throttles. These turned out to be rule 32's listed
>     exception, so the card was killed.
> - **Harness.** `scripts/check_module_conventions.py` at HEAD reports *All 43 covered module
>   conventions pass*.
> - **Passes: 2.** Pass 1 re-checked the items cold, in five parallel units: four batches of
>   items plus the delta sweep. Pass 2 chased the leads those units found
>   (`contract_vintage.id`, the `--cov` forms, the org selector, auth's `account/` tree, and
>   throttle identity) and added no further aspect.
> - **Companion hand-offs taken in:**
>   - From the tech audit: blog and listings throttle per user while forms throttles per IP.
>     This is consistent by design (§9 below).
>   - From the arch audit: `useModules.ts` lists the module set beside the seam producer. This
>     is rule 31's allowed exception, so it is consistent by design.
>   - From the arch audit: dr_engine's `ModuleNotFoundError` name check is copied in 2 files.
>     It is below this audit's population threshold, so it stays on the arch watchlist.
>
> **Still open after this pass (5).**
>
> 1. **`command-flag-conventions`** (J, ambiguity/tax, regressed). Only 2 of the 16 commands take
>    an organization selector, and they spell it two ways:
>    - `quickscale_billing_reconcile_checkouts --organization`
>      (`billing/.../quickscale_billing_reconcile_checkouts.py:52`);
>    - `quickscale_orgs_purge_organization --organization-id <uuid>`
>      (`orgs/.../quickscale_orgs_purge_organization.py:173`).
>
>    Every other rule-17 clause holds in all 16: `--json`, `--trigger` defaulting to `manual`,
>    and `--confirm` on purge and restore. **Rule:** ✅ an organization selector is
>    `--organization-id <uuid>`, validated as a UUID; ❌ `--organization`, `--org`, a slug.
>    **Check:** harness rule 17 adds the spelling to its banned list. The control is a fixture
>    command with `--organization`. The harness bans spellings (open-world), so this does not
>    make the check closed-world. Confidence: High, both files read.
> 2. **`contract-vintage-identity`** (B, ambiguity, new). `contract_vintage.id` is optional
>    (`manifest/loader_sections.py:222`), and whether it is present decides which mechanism
>    applies (`quickscale_cli/commands/contract_vintage.py:108–110`):
>    - With an `id` (billing, orgs), the CLI tracks the step by adoption.
>    - Without one (backups, social), the CLI compares versions, so a project cannot mark the
>      step adopted.
>
>    That is 2 of the 4 declaring manifests. The next author has two examples and nothing says
>    which to copy. **Rule:** ✅ every `contract_vintage` carries an `id` (a
>    `sa<NNN>-<slug>` style key, as in billing and orgs); ❌ an id-less vintage. **Check:** the
>    loader refuses a missing `id`. The control is a manifest without one. Changing a persisted
>    adoption key is a one-way door; adding a key that never existed is not. Confidence: High.
> 3. **`dependency-spec-sources`** (N, tax). Every residual in the original table is gone except
>    one: auth and blog run `--cov=src/<pkg>` (a path), while the other 10 run
>    `--cov=<pkg>` (`*/pyproject.toml` addopts). **Rule:** ✅ `--cov=<import package>`.
>    **Check:** the harness reads the pyproject addopts and compares the value with the package
>    name. Confidence: High, all 12 files grepped.
> 4. **`startup-checks-and-errors`** (B, tax, narrowed). Error naming, check order, and retired
>    settings now conform, under rules 6 and 10. One divergence remains: the `checks.py` of
>    analytics, billing, and notifications hand-list the setting and secret names that their
>    manifests already project, so a rename has to be made twice. No check covers this.
>    **Rule:** ✅ a startup check reads required names from the manifest projection; ❌ a
>    literal list of the module's own setting names in `checks.py`. **Check:** an AST scan in
>    harness rule 6 for `<MODULE>_*` string literals in `checks.py`. Confidence: Medium, because
>    the three modules' lists were read by a worker and not re-opened here.
> 5. **`capability-collection`** (D, ambiguity, narrowed). Core's `CAPABILITIES` is now a closed
>    list of 11 names. One walk remains outside `collect_capabilities`: the orgs purge command's
>    `getattr(app_config, "invalidate_organization_cache", None)`
>    (`quickscale_orgs_purge_organization.py:533`). An obligation that declares the hook
>    validates it, which limits the risk. **Rule:** ✅ every cross-app hook lookup goes through
>    `collect_capabilities`. **Check:** the harness bans `getattr(app_config, ...)` outside
>    core. Confidence: High.
>
> **Accepted (1).** `core-cli-module-knowledge`: 6 places still hold per-module knowledge,
> naming 7 of the 12 modules. Each one is a reasoned entry in rule 37's closed exception
> list, so that recorded decision makes it *accepted*. **Revisit** when that list grows.
>
> **Resolved this pass (11):**
> - `module-enabled-switch`: SA260. A closed-world parity test over all 12 modules checks apps,
>   middleware, and settings. URL drops and trigger refusal are unchecked (§7 gap).
> - `module-error-http-mapping`: SA264. Every module error base is `Exception`; `status_code`
>   and `default_code` go through core's `_error_shape`; harness rule 10 enforces it.
>   `InsufficientCreditsError` → 402. Vendor failures answer 500 consistently in billing,
>   notifications, blog, and listings.
> - `manifest-declared-surface`: SA260. The loader refuses unknown top-level keys, and orgs'
>   old `middleware:` key is the control.
> - `upward-name-references`: SA265(a/b). Obligation names and email templates are owned per
>   module, and `stripe_customer_id` now lives in billing.
> - `optional-sender-guard`: rule 43, checked against `required_modules`.
> - `module-dependency-direction`: rule 4. No module source imports another module's private
>   names. Tests still hold 38 such imports, but tests are out of the rule's scope.
> - `session-and-host-names`: rule 33. All 4 session keys are `quickscale_<module>:<name>`.
> - `model-basics`: SA266, enforced by rule 14.
> - `template-folder-depth`: SA266. (Correction: a worker reported auth's 12 nested
>   `quickscale_auth/account/` pages as residual. They are the real templates, and the 12
>   top-level `account/*.html` files are one-line allauth override shims that include them,
>   because allauth needs that path. Consistent by design.)
> - `test-file-names`: rule 29 now covers every `tests/` entry.
> - `ticket-ids-in-shipped-source`: 0 ticket ids remain, down from 183, and rule 29 now scans
>   shipped source. READMEs and templates are not scanned (§7 gap).
> - `constraint-purpose-tokens`: 28 constraints and 6 indexes follow amended rule 25.
>
> **New enforcement gaps (§7 addenda):**
> 1. The off-switch parity test checks apps, middleware, and settings, but not URL drops or
>    scheduled-trigger refusal.
> 2. Rule 17 bans spellings (open-world). It does not require `--json` and does not check the
>    off-refusal.
> 3. Rule 33 does not check the prefix of removal-obligation names, and rule 34 misses names
>    without the `quickscale_` prefix.
> 4. The `home` host route is documented in module-extension.md, but nothing checks it.
> 5. The rule 29 ticket-id scan skips READMEs and templates.
> 6. Nothing checks the `--cov` form.
> 7. A `contract_vintage` without an `id` is accepted silently.
>
> **Hand-offs from this pass:** none to the technical audit, since no residual is a live
> defect. To the architectural audit: `core-cli-module-knowledge` stays accepted under rule 37,
> and that audit watches its exception list.

>
> **How the 2026-10-08 pass was run.** The maintainer asked for a full review from scratch, not a
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
audited: 30b0b6b1
items:
  # ---- open: 2026-10-16 full census (items 27–41) ----
  - {id: cli-module-name-branches, status: open, aspect: C, cost: [ambiguity, tax],
     members_diverging: [backups, notifications, analytics, social, billing, orgs], population: modules(12),
     rule: "rule 37", check: "harness rule 37 (Eq/NotEq only)", closed_world: false, handoff: [arch],
     first_seen: 2026-10-16, last_verified: 2026-10-16}
  - {id: api-renderer-parser-pinning, status: resolved, aspect: H, cost: [ambiguity], members_diverging: [],
     population: drf-api-modules(8), rule: "rule 9 (JSON-only through the composed REST_FRAMEWORK defaults)",
     check: "harness rule 9 (composed JSON defaults; per-view pin ban with a control view)", closed_world: true,
     handoff: [], first_seen: 2026-10-16, last_verified: 2026-10-16}
  - {id: theme-retired-error-shapes, status: resolved, aspect: P, cost: [ambiguity], members_diverging: [],
     population: theme-api-clients, rule: "rule 9 (one error shape)", check: "theme unit test (useApiErrors.test.ts rejects the retired payloads)",
     closed_world: false, handoff: [], first_seen: 2026-10-16, last_verified: 2026-10-16}
  - {id: superuser-escape-spelling, status: resolved, aspect: E, cost: [ambiguity, tax], members_diverging: [],
     population: org-scoped-modules, rule: "rule 44 (one operator escape)",
     check: "harness rule 44 (raw is_superuser reads banned in module source outside orgs' is_platform_operator helper, with forms' old predicate as the control)",
     closed_world: true, handoff: [], first_seen: 2026-10-16, last_verified: 2026-10-16}
  - {id: readme-flag-coverage, status: open, aspect: O, cost: [ambiguity, tax], members_diverging: [backups, forms, orgs], population: command-modules(4),
     rule: "rule 38", check: "README test (command names only)", closed_world: false, handoff: [], first_seen: 2026-10-16, last_verified: 2026-10-16}
  - {id: adapter-restates-manifest-validation, status: open, aspect: B, cost: [tax], members_diverging: [notifications], population: adapters(12),
     rule: "rule 7 / Module Wiring Authority", check: none, closed_world: false, handoff: [], first_seen: 2026-10-16, last_verified: 2026-10-16}
  - {id: startup-presence-guard-copies, status: open, aspect: B, cost: [tax], members_diverging: [analytics, billing, notifications], population: checks-modules(7),
     rule: none, check: none, closed_world: false, handoff: [], first_seen: 2026-10-16, last_verified: 2026-10-16}
  - {id: throttle-rate-merge-copies, status: open, aspect: B, cost: [tax], members_diverging: [billing, blog, forms, listings, orgs], population: throttled-modules(5),
     rule: none, check: none, closed_world: false, handoff: [], first_seen: 2026-10-16, last_verified: 2026-10-16}
  - {id: command-off-refusal-and-atomic, status: open, aspect: J, cost: [tax], members_diverging: [backups, forms, orgs], population: commands(16),
     rule: "rule 1, rule 17", check: none, closed_world: false, handoff: [], first_seen: 2026-10-16, last_verified: 2026-10-16}
  - {id: theme-request-paths, status: resolved, aspect: P, cost: [tax], members_diverging: [],
     population: theme-hooks, rule: "rule 31", check: "theme ESLint (fetch ban in src/hooks)",
     closed_world: false, handoff: [], first_seen: 2026-10-16, last_verified: 2026-10-16}
  - {id: test-ticket-ids-in-identifiers, status: resolved, aspect: M, cost: [tax], members_diverging: [], population: modules(12),
     rule: "rule 29 (identifiers, strings, names, docstrings, and comments)", check: "harness rule 29 (identifiers and strings in every tests/ entry, any case, embedded ids included, with controls); 0 tokens remain", closed_world: false, handoff: [], first_seen: 2026-10-16, last_verified: 2026-10-16}
  - {id: test-harness-parity, status: resolved, aspect: M, cost: [tax], members_diverging: [], population: modules(12),
     rule: "rule 18 (shared test-settings base and conftest plugin)", check: "harness rule 18 (each module's test-settings keys diffed against the core base; both hooks taken from the plugin, with controls); 12/12 suites adopted", closed_world: false, handoff: [], first_seen: 2026-10-16, last_verified: 2026-10-16}
  - {id: pyproject-residue, status: open, aspect: N, cost: [tax], members_diverging: [auth, blog, crm, forms, listings, orgs], population: modules(12),
     rule: "rule 36", check: none, closed_world: false, handoff: [], first_seen: 2026-10-16, last_verified: 2026-10-16}
  - {id: manifest-option-residue, status: open, aspect: B, cost: [tax], members_diverging: [analytics, social, notifications], population: options(96),
     rule: "rule 29 (version stamps)", check: none, closed_world: false, handoff: [], first_seen: 2026-10-16, last_verified: 2026-10-16}
  - {id: structured-log-fields, status: resolved, aspect: K, cost: [tax], members_diverging: [],
     population: logging-modules(7), rule: "rule 24 (small conventions)",
     check: "review rule (orgs' operator-access and tenancy-refusal logs are the recorded sites)",
     closed_world: false, handoff: [], first_seen: 2026-10-16, last_verified: 2026-10-16}
  # ---- open: this pass (ranked per §6) ----
  - {id: module-enabled-switch, status: resolved, regressed: false, aspect: B, cost: [defect, ambiguity],
     members_diverging: [analytics, billing, notifications, backups, forms], population: modules(12),
     rule: "rule 1 (D3)", check: "none for the mechanism", closed_world: false, handoff: [tech],
     first_seen: 2026-09-26, last_verified: 2026-10-13}
  - {id: markdownx-shared-mount, status: resolved, aspect: A, cost: [collision, defect],
     members_diverging: [blog, listings], population: url-mount-prefixes(14 includes / 10 modules),
     rule: "rule 41 (two routes, one path)", check: "harness rule 7; collect_url_wiring", closed_world: false, handoff: [tech],
     first_seen: 2026-10-08, last_verified: 2026-10-10}
  - {id: tenant-authorization, status: resolved, regressed: false, aspect: E, cost: [ambiguity],
     members_diverging: [billing], population: modules-with-pages-or-apis(9),
     rule: "rule 19; JSON API Endpoint Base Contract", check: "harness rule 19 (partial)",
     closed_world: false, handoff: [tech], first_seen: 2026-09-26, last_verified: 2026-10-08}
  - {id: option-schema-and-validation, status: resolved, regressed: false, aspect: B, cost: [ambiguity, tax],
     members_diverging: [],
     population: adapters(12), rule: "rules 3, 12; Module Derivation Schema", check: "harness rules 3, 12 (manifest schema, adapter AST, and declared derived settings)",
     closed_world: false, handoff: [], first_seen: 2026-09-26, last_verified: 2026-10-11}
  - {id: unauthenticated-status-code, status: resolved, aspect: H, cost: [ambiguity, tax],
     members_diverging: [crm, forms], population: session-authenticated-apis(6), rule: none,
     check: none, closed_world: false, handoff: [], first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: module-error-http-mapping, status: resolved, aspect: D, cost: [ambiguity, tax],
     members_diverging: [billing, blog, listings, notifications], population: modules(12),
     rule: "rules 9, 10 (silent on the mapping)", check: none, closed_world: false, handoff: [tech],
     first_seen: 2026-10-08, last_verified: 2026-10-13}
  - {id: startup-checks-and-errors, status: resolved, regressed: false, aspect: B, cost: [ambiguity, tax],
     members_diverging: [analytics, backups, blog, forms, notifications], population: modules(12),
     rule: "rules 6, 10", check: "harness rule 10 (any *Error base passes)", closed_world: false,
     handoff: [], first_seen: 2026-09-26, last_verified: 2026-10-16}
  - {id: upward-name-references, status: resolved, regressed: true, aspect: C, cost: [ambiguity, tax],
     members_diverging: [orgs, notifications], population: cross-module-vocabularies(4),
     rule: "rule 34; rule 8 (email templates)", check: "harness rule 34 (labels/packages/models only)",
     closed_world: false, handoff: [arch], first_seen: 2026-09-26, last_verified: 2026-10-13}
  - {id: core-cli-module-knowledge, status: accepted, aspect: C, cost: [ambiguity, tax],
     members_diverging: [analytics, backups, billing, notifications, social, storage],
     population: modules(12), rule: "Module Wiring Authority; rule 12 ❌ (names contracts.module_options)",
     check: none, closed_world: false, handoff: [arch], first_seen: 2026-10-08, last_verified: 2026-10-13}
  - {id: manifest-declared-surface, status: resolved, aspect: B, cost: [ambiguity, tax],
     members_diverging: [auth, orgs, notifications], population: manifests(12),
     rule: "Module Wiring Authority (no parsed-but-unread key; apps never a literal)",
     check: "app-declaration gate (apps projection); harness rule 7 (url_includes literals only)",
     closed_world: false, handoff: [], first_seen: 2026-10-08, last_verified: 2026-10-13}
  - {id: http-api-shape, status: resolved, regressed: false, aspect: H, cost: [ambiguity, tax],
     members_diverging: [billing, social], population: json-api-modules(7), rule: "rule 9",
     check: "harness rule 9 (module source only)", closed_world: false, handoff: [tech],
     first_seen: 2026-09-26, last_verified: 2026-10-08}
  - {id: throttle-attachment, status: resolved, aspect: H, cost: [ambiguity, tax],
     members_diverging: [billing, blog, forms, listings], population: json-api-modules(6),
     rule: "rule 32 (names and rates only)", check: none, closed_world: false, handoff: [],
     first_seen: 2026-10-08, last_verified: 2026-10-08}
  - {id: optional-sender-guard, status: resolved, regressed: false, aspect: C, cost: [ambiguity, tax],
     members_diverging: [forms, orgs], population: cross-module-service-calls(4), rule: "rules 4, 39, 43",
     check: "harness rule 43", closed_world: false, handoff: [], first_seen: 2026-10-03, last_verified: 2026-10-13}
  - {id: module-dependency-direction, status: resolved, regressed: false, aspect: C, cost: [ambiguity, tax],
     members_diverging: [blog, crm, social], population: modules-importing-orgs(8), rule: "rule 4",
     check: "harness rule 4 (file-level surface only)", closed_world: false, handoff: [],
     first_seen: 2026-09-26, last_verified: 2026-10-13}
  - {id: capability-collection, status: resolved, aspect: D, cost: [ambiguity, tax],
     members_diverging: [orgs], population: appconfig-capabilities(13), rule: "rule 4 (one core helper)",
     check: none, closed_world: false, handoff: [arch], first_seen: 2026-10-08, last_verified: 2026-10-16}
  - {id: command-flag-conventions, status: resolved, regressed: false, aspect: J, cost: [ambiguity, tax],
     members_diverging: [], population: commands(16), rule: "rule 17 (one selector spelling)",
     check: "harness rule 17 (spelling ban with controls)", closed_world: false, handoff: [],
     first_seen: 2026-10-08, last_verified: 2026-10-15}
  - {id: dependency-spec-sources, status: resolved, aspect: N, cost: [ambiguity, tax],
     members_diverging: [backups, storage, orgs], population: modules(12),
     rule: "Module Manifest Architecture (names only)", check: none, closed_world: false, handoff: [],
     first_seen: 2026-10-08, last_verified: 2026-10-16}
  - {id: secret-env-var-names, status: resolved, regressed: false, aspect: A, cost: [ambiguity],
     members_diverging: [], population: vendor-credential-options(5 modules), rule: "rule 1",
     check: "harness rule 1 (module/option-bound vendor defaults and reasoned QuickScale exceptions)",
     closed_world: true, handoff: [], first_seen: 2026-09-26,
     last_verified: 2026-10-11}
  - {id: session-and-host-names, status: resolved, aspect: A, cost: [ambiguity],
     members_diverging: [orgs, auth], population: shared-namespaces, rule: "rule 33", check: none,
     closed_world: false, handoff: [], first_seen: 2026-10-08, last_verified: 2026-10-13}
  - {id: model-basics, status: resolved, regressed: false, aspect: G, cost: [tax, ambiguity],
     members_diverging: [blog, listings, auth, backups, notifications, orgs, social], population: models(10 modules),
     rule: "rule 14", check: "harness rule 14 (gettext, str, ordering, related_name)", closed_world: false,
     handoff: [], first_seen: 2026-09-26, last_verified: 2026-10-13}
  - {id: template-folder-depth, status: resolved, aspect: L, cost: [tax],
     members_diverging: [auth, billing, blog, crm, forms, listings], population: modules-with-page-templates(8),
     rule: "rule 8 (base only)", check: none, closed_world: false, handoff: [], first_seen: 2026-10-08,
     last_verified: 2026-10-13}
  - {id: test-file-names, status: resolved, regressed: false, aspect: M, cost: [tax],
     members_diverging: [auth, backups, billing, forms, listings, orgs], population: modules(12),
     rule: "rule 29 (second clause)", check: "harness rule 29 (test_*.py only)", closed_world: false,
     handoff: [], first_seen: 2026-09-26, last_verified: 2026-10-13}
  - {id: ticket-ids-in-shipped-source, status: resolved, aspect: O, cost: [tax],
     members_diverging: [auth, backups, billing, blog, crm, forms, listings, orgs, social, storage],
     population: modules(12), rule: "rule 29 (tests only)", check: none, closed_world: false,
     handoff: [], first_seen: 2026-10-08, last_verified: 2026-10-13}
  - {id: constraint-purpose-tokens, status: resolved, aspect: A, cost: [tax],
     members_diverging: [crm, forms, orgs, notifications], population: constraint-names(31),
     rule: "rule 25 (prefix only)", check: "harness rule 25", closed_world: false, handoff: [],
     first_seen: 2026-10-08, last_verified: 2026-10-13}
  - {id: mount-path-copies, status: resolved, regressed: false, aspect: P, cost: [ambiguity, tax],
     members_diverging: [orgs, billing, forms, social], population: theme-module-api-clients(5),
     rule: "rule 41 (no literal module path in theme templates)", check: "harness rules 7 (theme TypeScript), 31, 37 (seam producer)",
     closed_world: false, handoff: [], first_seen: 2026-10-03, last_verified: 2026-10-10}
  - {id: contract-vintage-identity, status: resolved, aspect: B, cost: [ambiguity],
     members_diverging: [], population: contract-vintage-manifests(4),
     rule: "Module Manifest Architecture (every contract_vintage carries an sa<NNN>-<slug> id)",
     check: "the loader refuses a missing id (control manifest); the CLI tracks every declared vintage by adoption",
     closed_world: true, handoff: [], first_seen: 2026-10-13, last_verified: 2026-10-15}
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

**Counts (open, 2026-10-16 (b), full census):** defect 0 · collision 0 · ambiguity 5 · tax 13 · **total 15**, plus 1 accepted. **Counts (open, 2026-10-16 (a), delta re-run):** 0 open, 1 accepted. **Counts (open, 2026-10-13):** defect 0 · collision 0 · ambiguity 4 · tax 3 (items carry more than one class) · **total 5**, plus 1 accepted. **Counts (open, 2026-10-08):** defect 2 · collision 1 (also counted under defect) · ambiguity 17 · tax 5 ·
**total 25**. 12 of the 25 are prior IDs reopened, and one of those (`upward-name-references`)
is flagged `regressed`. The other 13 are new. One new item, `markdownx-shared-mount`, recreates a
state the frozen inventory had warned against (§12). Resolved prior IDs still holding: 43 of 55.

| # | ID | Aspect | Cost | Diverging / population | Status |
|---|---|---|---|---|---|
| 1 | `module-enabled-switch` | B | defect, ambiguity | 5 / 12 modules (+ core `env_sync`) | resolved (2026-10-13) |
| 2 | `markdownx-shared-mount` | A | collision, defect | 2 / 10 mounting modules | resolved (SA261) |
| 3 | `tenant-authorization` | E | ambiguity | 1 / 9 | resolved (SA262) |
| 4 | `option-schema-and-validation` | B | ambiguity, tax | 0 / 12 adapters | resolved (SA263) |
| 5 | `module-error-http-mapping` | D | ambiguity, tax | 4 / 12 (5 variants) | resolved (2026-10-13) |
| 6 | `unauthenticated-status-code` | H | ambiguity, tax | 2 / 6 (4 duplicated classes on the other side) | resolved (SA262) |
| 7 | `startup-checks-and-errors` | B | ambiguity, tax | 0 / 12 | resolved (SA283a) |
| 8 | `upward-name-references` | C | ambiguity, tax | 2 owners / 4 vocabularies | resolved (2026-10-13) |
| 9 | `core-cli-module-knowledge` | C | ambiguity, tax | 6 / 12 named in core or CLI | accepted (2026-10-13) |
| 10 | `manifest-declared-surface` | B | ambiguity, tax | 3 / 12 (+4 key-presence) | resolved (2026-10-13) |
| 11 | `http-api-shape` | H | ambiguity, tax | 2 / 7 | resolved (SA262) |
| 12 | `throttle-attachment` | H | ambiguity, tax | 4 / 6 | resolved (SA262) |
| 13 | `optional-sender-guard` | C | ambiguity, tax | 2 / 4 call edges | resolved (2026-10-13) |
| 14 | `module-dependency-direction` | C | ambiguity, tax | 3 / 8 | resolved (2026-10-13) |
| 15 | `capability-collection` | D | ambiguity, tax | 0 / 13 names | resolved (SA283b) |
| 16 | `command-flag-conventions` | J | ambiguity, tax | 0 / 3 command-shipping modules | resolved (SA282) |
| 17 | `dependency-spec-sources` | N | ambiguity, tax | 0 / 12 | resolved (SA283c) |
| 18 | `mount-path-copies` | P | ambiguity, tax | 4 / 5 theme API clients | resolved (SA261) |
| 19 | `secret-env-var-names` | A | ambiguity | 0 / 5 | resolved (SA263) |
| 20 | `session-and-host-names` | A | ambiguity | 2 | resolved (2026-10-13) |
| 21 | `model-basics` | G | tax, ambiguity | 7 / 10 | resolved (2026-10-13) |
| 22 | `template-folder-depth` | L | tax | 6 / 8 | resolved (2026-10-13) |
| 23 | `test-file-names` | M | tax | 6 / 12 | resolved (2026-10-13) |
| 24 | `ticket-ids-in-shipped-source` | O | tax | 10 / 12 | resolved (2026-10-13) |
| 25 | `constraint-purpose-tokens` | A | tax | 4 / 9 | resolved (2026-10-13) |
| 26 | `contract-vintage-identity` | B | ambiguity | 0 / 4 vintage manifests | resolved (SA282) |
| 27 | `cli-module-name-branches` | C | ambiguity, tax | 6 modules named at 5 CLI sites outside rule 37's list | open (2026-10-16) |
| 28 | `api-renderer-parser-pinning` | H | ambiguity | 0 / 8 DRF-serving surfaces unpinned or half-pinned | resolved (SA288) |
| 29 | `theme-retired-error-shapes` | P | ambiguity | 0 clients, 2 retired shapes | resolved (SA289 (a)) |
| 30 | `superuser-escape-spelling` | E | ambiguity, tax | 1 / 2 spellings | resolved (SA290) |
| 31 | `readme-flag-coverage` | O | ambiguity, tax | 3 / 4 command modules | open (2026-10-16) |
| 32 | `adapter-restates-manifest-validation` | B | tax | 1 / 12 adapters | open (2026-10-16) |
| 33 | `startup-presence-guard-copies` | B | tax | 3 / 7 `checks.py` | open (2026-10-16) |
| 34 | `throttle-rate-merge-copies` | B | tax | 5 / 5 throttled adapters | open (2026-10-16) |
| 35 | `command-off-refusal-and-atomic` | J | tax | 3 / 16 commands | open (2026-10-16) |
| 36 | `theme-request-paths` | P | tax | 2 raw `fetch` + literal paths | resolved (SA289 (b)) |
| 37 | `test-ticket-ids-in-identifiers` | M | tax | 5 / 12 | resolved (SA293 (a)) |
| 38 | `test-harness-parity` | M | tax | 5 / 12 | resolved (SA293 (b)) |
| 39 | `pyproject-residue` | N | tax | 6 / 12 | open (2026-10-16) |
| 40 | `manifest-option-residue` | B | tax | 4 / 96 options | open (2026-10-16) |
| 41 | `structured-log-fields` | K | tax | 1 / 7 logging modules | resolved (SA294) |

---

## 4. Aspect sections

### Census 2026-10-16 (b) at `30b0b6b1` — supersedes the 2026-10-08 tables below

The full cell-level tables are in the scratch ledgers. They are summarised here with counts. Rows
marked ✓ are *Already consistent (keep)*. Drift rows name their item.

| Aspect | Census (counts · members) | Drift → item |
|---|---|---|
| A · settings / env | `QUICKSCALE_<MODULE>_*` 12/12; no module reads another's `QUICKSCALE_*` ✓ | — |
| A · URL mounts | `<module>/` 9 · `accounts/` auth · `_quickscale/social/` social · `markdownx/` storage only (Correction: 2026-10-08 had blog *and* listings; SA261) ✓ | — |
| A · session / cache / lock / throttle keys | `quickscale_<m>:<key>` 4/4 session keys; cache, lock, and throttle-scope stems `quickscale_<m>_` everywhere ✓ | — |
| A · constraints / indexes | constraints `quickscale_<m>_<model>_<purpose>` (all end `_unique`); indexes `qs_<m>_…_idx` in blog 3, listings 3 — rule 25's declared form ✓; `db_table` unset 12/12 ✓; `related_name` on User/Organization stemmed ✓ | — |
| A · removal obligations | `quickscale_<m>:<purpose>`, owned per module ✓ (Correction: the 2026-10-08 Item 8 owner split is gone) | — |
| A · host route names | auth `reverse_lazy("home")` (`auth/views.py:105`) is the only one; documented, unchecked | §7 gap 4 (carried) |
| B · adapters | `build_generic_manifest_spec` 12/12 ✓; generic settings check registered 12/12 ✓; 96 options all have type/default/description/validation ✓; 0 adapters call `validate_module_options` ✓ | 32, 34 |
| B · `checks.py` | 7 files (analytics, backups, billing, blog, notifications, orgs, storage). (Correction: the 2026-10-08 count of 10 is stale.) Presence-guard copies in 3 | 33 |
| B · off switch | apps, middleware, and settings kept 12/12 ✓; public URLs dropped 11/11 mounting modules; webhooks stay mounted (billing, notifications) per rule 26 ✓ | — |
| B · `contract_vintage` | 4/4 carry `id` ✓ | — |
| B · option text | version stamps in 3 descriptions (analytics `provider`, social ×2); integer `webhook_ttl_seconds` carries a string `pattern` | 40 |
| C · imports | 0 cross-module private imports ✓; 0 undeclared sibling imports ✓; 0 `import_string` ✓; capability reads via `collect_capabilities` 17/17 ✓; 12 `CAPABILITIES` names all consumed ✓ | — |
| C · core/CLI module names | listed exceptions (rule 37) + unlisted branches at 5 CLI sites | 27 |
| D · package root | `__all__ = ["__version__"]` 12/12 ✓; `py.typed` 12/12 ✓; error base `<Name>Error(Exception)` 9/12; analytics, forms raise none (exempt, decisions.md:810–815); backups re-exports core `BackupError` ✓ | — |
| D · failure semantics | raise-only: backups, billing, blog, crm, listings, storage; best-effort swallow: analytics (4), notifications (1), social (2) | §8 |
| E · authorization | org role via orgs' tools in every org-scoped API ✓; storage markdownx staff gate (rule 41) ✓; superuser escape spelled 2 ways | 30 |
| F · effects | request-path email, events, seeding, file deletes `on_commit` everywhere ✓; 2 inline cache purges outside requests (social `services.py:205`, no caller; orgs `apps.py:217`, after the purge command's delete) — low | §8 |
| G · models | `published_at` blog + listings ✓; no `Meta.verbose_name`, no `Meta.app_label` 0/10 ✓ (Correction: Item 21's residue is gone) | — |
| H · errors / auth / pages | core error shape 8/8 including social's generated `APIView`s ✓; `QuickscaleSessionAuthentication` 6/6 ✓; `PlainListPagination` 3/3 ✓; throttle scope 4/4 + orgs rule-32 exception ✓; webhook secrets checked at startup 2/2 ✓ | — |
| H · renderer / parser | JSON pinned: billing, listings, orgs, social views (4); parser only: blog; defaults (browsable + form/multipart): crm, forms, notifications | 28 |
| H · off answer | Django `Http404` crm, forms; DRF `NotFound`/module `not_found` billing, notifications, orgs; one bare `HttpResponse(404)` orgs `_view_invitation.py:158` (bodies likely equal, not run) | low, ledger |
| I · outbound | 0/5 vendor-calling modules set timeouts or retries — consistent, no rule (carried §8) | — |
| J · commands | 16 commands. `--json` where machine output exists ✓; `--trigger` default `manual` 3/3 ✓; `--confirm` on purge/restore ✓; trigger choices backups `manual,scheduled,admin` vs forms `manual,scheduled` (by design, §8); off refusal 2 spellings; `transaction.atomic` in the command 3/16 | 35 |
| K · logging | package-derived logger names, with split files on the facade logger (rule 46) ✓; `extra=` fields only in orgs (6 calls). (Correction: §8's "no structured fields" is stale.) | 41 |
| L · layout | closed `tests/` list holds (rule 29) ✓; template depth flat except auth's allauth shims ✓; one placeholder `.gitkeep` in a non-empty dir (listings `static/quickscale_listings/`) — trivial | ledger |
| M · tests | conftest hooks 10/12 (missing in analytics, storage); test settings gaps: auth has no `DEFAULT_AUTO_FIELD`, blog and listings have no `USE_TZ`; vendor fakes in 3 styles; ~70–90 ticket ids in test identifiers | 37, 38 |
| N · tooling | build backend, 0.89.0 lockstep, ruff, Django/Python pins, `--cov=<package>` 12/12 ✓; stale "centralized in root" comment 5; orgs dev floors `>=`; 6 `pythonpath` variants | 39 |
| O · docs | README H2 outline 12/12 ✓; 104 option rows match `module.yml` ✓; flags documented partially | 31 |
| P · theme | the one error parser, one request client, and seam page paths across the theme ✓ | 29, 36 (resolved) |
| Q · locale | 0 `gettext`, 0 `trans` in 12/12 — English only by decision ✓ | — |

Inert: none beyond Q (consistent). Population sizes: 12 modules · 16 commands · 8 DRF-serving
surfaces · 7 `checks.py` · 96 options · 2 webhooks.


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

*SA263 note (2026-10-11):* item 4's adapter drift is closed in the joined tree — every adapter
routes through the generic boundary, core's dead resolver step 5 is gone, the blank
`__QS_ENV__:` marker renders the literal empty string, and harness rules 1, 3, and 12 enforce
the boundary. Round-1 corrections add required absolute-URL patterns for storage's
`public_base_url`/`endpoint_url` and backups' `remote_endpoint_url` without tightening
historical `MEDIA_URL` acceptance; module/option-bound vendor defaults with reasoned
QuickScale exceptions; root and per-option derived-setting read authority; and bounded
adapter provenance through scalar/container aliases and loops. Storage's scalar AWS aliases
are now manifest-owned computed settings with cloud/blank presence guards. The frozen media
oracle is reused through persistence, serialized state, and reapply, including changed-default
parity. Correction validation and the next independent review, not these claims, grade closure.

*SA282 note (2026-10-15):* item 26's identity drift is closed. Every `contract_vintage` carries
an `sa<NNN>-<slug>` id — backups and social gained theirs in both the module manifest and the
core snapshot, as new keys, so no persisted adoption key changed — the loader
(`loader_sections._parse_contract_vintage`) refuses a vintage without one (control manifest in
the loader suite; an embedded historical copy is the explicit, documented opt-out so an older
project stays upgradable), and the CLI's mechanism selection is gone: every declared vintage is
satisfied by its recorded adoption id alone, with no version-comparison fallback. Decisions
record the rule under § Module Manifest Architecture.

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

*SA290 note (2026-10-16):* item 30 is closed. Orgs publishes one `is_platform_operator(user)`
helper (an authenticated superuser), and forms' cross-tenant operator branch and every orgs copy
call it instead of reading `is_superuser`; decisions rule 44 carries proposal 54, and harness rule
44 bans a raw `is_superuser` read in module source outside that helper, with forms' old predicate
as the control. Rule 19's operator-path table now lists only the helper's file.

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

*SA288 note (2026-10-16):* item 28 is closed. The generated `REST_FRAMEWORK` composes the JSON
renderer and parser defaults, and the module views pin neither: billing's `_BillingAPIView`,
listings' `ListingPublishAPIView`, orgs' `OrgApiBaseView`, blog's `PostPublishAPIView`, and the
rendered social payload views dropped their pins, while the blog media upload keeps its
multipart policy and a webhook reads its raw body. Decisions rule 9 carries proposal 52, and
harness rule 9 checks both composed defaults and bans per-view pins, with controls.

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

*SA282 note (2026-10-15):* item 16 is closed. `quickscale_billing_reconcile_checkouts` selects
with `--organization-id <uuid>`, decisions rule 17 carries the one-spelling clause, and harness
rule 17 refuses `--organization`, `--org`, and any other `--org*`/`--organization*` spelling
except exactly `--organization-id`, plus a bare `--slug` declared without it; fixture controls
and exact-findings rows pin both refusals.

### K. Observability — quiet

Package-derived logger names everywhere. No structured fields anywhere. Module loggers reach only
the root handler (the generated `LOGGING` routes only the project package to the file handler).
Consistent; no drift passes §0.

*SA294 note (2026-10-16):* item 41 is closed. Decisions rule 24 carries the convention: a security
or audit event — operator access, a tenancy refusal, and their like — carries `extra=` fields, and
every other module log line stays message-only. The clause has no detector by design and stays a
review rule; orgs' six `extra=` calls (the operator-access and VIEW-AS audit logs) are the recorded
sites.

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
| Module path source | seam `modulePaths` → the SPA's blog, listings, and crm page routes and navigation · seam `moduleDocumentPaths` → the launcher pages' document links · seam `moduleApiPaths` → every module API base (rule 41) |
| HTTP helper | one shared client (`apiRequest`/`useApiData`) → every theme request, with a lint ban on a raw `fetch(` in `src/hooks` |
| Error shape parsed | the one QuickScale shape only → `useApi.ts` |

*Drift:* none; items 18, 29, and 36 are resolved.

*SA289 note (2026-10-16):* items 29 and 36 are closed. `useApi.ts` parses only the one QuickScale
shape `{"error": {"code", "message", "fields"}}` and no longer reads the retired string-`error` or
`errors`-key payloads; `useApiErrors.test.ts` pins the rejection, and the
`sa289-theme-one-error-parser` adoption step records it for existing projects. Every theme hook
request goes through `apiRequest` (the theme's ESLint configuration fails a raw `fetch(` in
`src/hooks` outside `useApi.ts`), and the SPA's blog, listings, and crm page routes and
navigation read the seam's `modulePaths`, which gained `blog` and `listings` entries resolved
from their `quickscale_blog_shell`/`quickscale_listings_shell` routes, and the launcher pages'
document links read the new `moduleDocumentPaths` table (blog's index and feed, listings' index,
the CRM dashboard), resolved from the documents' named routes; the
`sa289-theme-request-client-and-seam-paths` adoption step records the theme-plus-managed-seam
adoption for existing projects. Proposal 53 merged into decisions rule 31.

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
- **SA263 (2026-10-11):** *closed.* All 12 adapters route through
  `build_generic_manifest_spec`; the hooks keep only off-switch transformations, throttle
  composites, runtime selections, provider filtering, and managed rendering. Core's resolver
  step 5 is deleted, the blank `__QS_ENV__:` marker renders the literal empty string (it is not
  refused, and the name regex is not widened), and the harness's rule 1 (vendor vocabulary plus
  per-option QuickScale exceptions), rule 3 (the derived-setting declaration), and rule 12 (URL
  normalizer kinds and the adapter's forbidden `.get(default)`/`bool()`/`int()`/`str()`/
  `.strip()`/`.lower()`/`.casefold()`/`or`-fallback/`not`-recheck/validator-call shapes)
  detectors carry the clause with negative and permitted controls. The `social`
  `.get("layout_variant", "list")` control above is rejected by the delivered detector.
  **Round-1 correction:** the three optional absolute-URL patterns are now declared, the
  scalar AWS aliases have moved from Python into manifest-owned presence-guarded computed
  settings, and enforcement follows simple option/mapped-setting aliases and loops. Root-level
  derived settings are declaration authority without redundant adapter literals. Frozen-media
  persistence/state/reapply tests and default-normalization parity controls supplement the
  original delivery; release readiness remains a root-owned gate, not established here.

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

### 2026-10-16 (b) census items (ranked: ambiguity before tax, then diverging × churn)

### Item 27: Core/CLI — module-name branches outside rule 37's list
- **ID:** `cli-module-name-branches` · **Aspect / population:** C (per-module knowledge) · 12 modules, as named by the CLI.
- **Table:** listed exceptions (rule 37): `module_options`, `social_manifest`, `_dependency_io` storage, `_module_embed` auth, seam and URL tables, `MODULE_CATALOG`, `ENV_EXAMPLE_MODULE_SPECS` · **unlisted:**
  - `commands/_finalize.py:68–76`: `"<m>" in modules` for backups, notifications, analytics, social, and billing;
  - `commands/_config.py:402`: orgs;
  - `commands/_runtime.py` (`config.modules.get("backups")`);
  - `apply_support.py:104` and `commands/_plan_validation.py:38–48`: notifications.
- **Drift:** rule 37 ❌ forbids "an equality branch on a module name in core or the CLI outside the listed exceptions". Harness rule 37 matches only `ast.Eq`/`ast.NotEq` (`scripts/module_conventions/_identity_module_lists.py:27`), so `in` and `.get("<m>")` branches pass. Six modules carry next-steps, validation, or runtime knowledge in the CLI. The next module's author cannot tell whether to add a branch or a manifest field.
- **Cost class:** ambiguity (the rule reads as closed, while the check is open), and tax (each new module copies a branch).
- **Declared rule:** decisions.md rule 37 (`:1248–1277`).
- **Options:**
  - A: list the 5 sites as rule 37 exceptions, with reasons. Cheap, but it keeps the knowledge in the CLI.
  - B: move next-steps text and option validation behind manifest fields, or adapter hooks the CLI calls generically. Medium cost, no one-way door.
  - C: B for validation (`_config`, `_plan_validation`, `apply_support`), and A for operator next-steps text.
- **Recommended rule:** ✅ The CLI reaches module-specific behaviour through a manifest field or a generic adapter hook. ❌ A membership (`in`), `.get("<module>")`, or equality branch on a module name in core or the CLI outside the listed exceptions.
- **Enforcement:** extend `RULE_37_BRANCH_OPERATORS` to `ast.In`/`ast.NotIn`, and add `.get()`/subscript calls with a module-name constant. The control is a fixture `if "billing" in modules:`. It stays open-world over spellings, but closes the two that occur.
- **Migration:** CLI only, with no persisted names. Rides any release.
- **Confidence:** High. All 5 sites and the harness operator tuple were read.
- **Hand-off:** arch (`core-holds-module-vocabulary`).

### Item 28: API — renderer and parser pinning
- **ID:** `api-renderer-parser-pinning` · **Aspect / population:** H · 8 DRF-serving surfaces.
- **Table:** JSON renderer + parser pinned → billing, listings, orgs, social's generated views (4) · parser only → blog (1) · DRF defaults (browsable HTML renderer; JSON + form + multipart parsers) → crm, forms, notifications (3). The generated `REST_FRAMEWORK` (`base.py.j2`, `runtime/settings.compose_rest_framework`) sets no `DEFAULT_RENDERER_CLASSES` or `DEFAULT_PARSER_CLASSES`.
- **Drift:** the same endpoint class accepts form-encoded bodies, and renders HTML to a browser, in 3 modules and not in 4. Callers and the theme cannot rely on one content contract.
- **Cost class:** ambiguity.
- **Declared rule:** none.
- **Options:**
  - A: set the JSON-only defaults once in the generated `REST_FRAMEWORK`, and drop the per-view pins. Smallest change, project-wide.
  - B: require every module view to pin. This multiplies copies.
- **Recommended rule:** ✅ Module APIs are JSON-only, through the generated `REST_FRAMEWORK` defaults. ❌ A per-view renderer or parser pin, except a webhook's raw-body parser.
- **Enforcement:** a harness check that the generated settings carry both defaults, plus a ban on `renderer_classes`/`parser_classes` in module views outside webhooks. Closed-world. The control is a view with `parser_classes`.
- **Migration:** crm, forms, and notifications stop accepting form posts. Release-note line. Confidence: High on the table, Medium on caller reliance.

### Item 29 (compact): `theme-retired-error-shapes`
P · `useApi.ts:52,70,81` still parses the retired `errors` list and the string-`error` shape "for compatibility" (1 client). Every module now emits only core's `{"error":{code,message,fields?}}`, so the client advertises a contract that no longer exists. **Rule:** ✅ the theme parses core's error shape only. **Check:** a theme unit test rejects a payload that has only `errors`. Confidence: High.

### Item 30 (compact): `superuser-escape-spelling`
E · operator escape: orgs `permissions.py:36–41` (inside `HasOrgRole`) vs forms' private `_is_superuser` (`forms/views.py:173`). **Rule:** ✅ the superuser escape is orgs' permission helper only. ❌ a module-private superuser predicate. **Check:** the harness bans `is_superuser` reads in module views outside orgs. The control is forms. Confidence: Medium. Whether forms' cross-tenant `operator_access` needs a distinct predicate is a team question (§11).

### Item 31 (compact): `readme-flag-coverage`
O · rule 38 checks command *names* only:
- backups documents 6 of its 19 flags;
- forms omits `--dry-run`;
- orgs omits `--force` and `--postgres-only`;
- billing is complete.

**Rule:** ✅ a README's Management commands entry lists every flag. **Check:** extend the rule 38 README test to compare the argparse options. Confidence: Medium, because the flag counts come from the worker.

### Item 32 (compact): `adapter-restates-manifest-validation`
B · 1 of 12 adapters. Notifications' `adapter.py:20–70` re-implements 4 manifest patterns: email, placeholder sender, domain, and env-var name. The domain check is hand-written rather than the manifest's regex. The CLI consumes these copies (`apply_support.py:104` loads the adapter). Two sources of truth for one option. **Rule:** ✅ the adapter's runtime predicates evaluate the manifest's declared validation. **Check:** a ban on `re.compile` in `adapter.py`. Confidence: High.

### Item 33 (compact): `startup-presence-guard-copies`
B · analytics `checks.py:69`, billing `:53`, and notifications `:86` repeat the `projected_setting_names` + `hasattr` presence guard that the generic settings check already enforces (`runtime/conventions.py:489–493`). The other 4 `checks.py` files don't. **Rule:** ❌ a module check that re-tests a projected setting's presence. **Check:** a rule-6 AST scan. Confidence: Medium.

### Item 34 (compact): `throttle-rate-merge-copies`
B · billing `adapter.py:44`, blog `:27`, forms `:26`, listings `:27`, and orgs `:32` each hand-merge `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES`. **Rule:** ✅ a manifest `throttle_scopes` projection that core merges. **Check:** a ban on `DEFAULT_THROTTLE_RATES` in adapters. Confidence: High.

### Item 35 (compact): `command-off-refusal-and-atomic`
J · the off refusal uses a helper in backups create, and is inline in backups prune and forms anonymize. `transaction.atomic` opens inside the command in forms ×2 and orgs purge, and below it in services elsewhere. **Rule:** ✅ one core helper for the scheduled-off refusal; the transaction lives in the service. **Check:** harness rule 17 requires the helper call when `--trigger` exists. Confidence: Medium.

### Item 36 (compact): `theme-request-paths`
P · residue of `mount-path-copies`. `useFormSchema` and `usePublicSocialSurface` call raw `fetch`, not `apiRequest`. `useOrgNavigation` and `App.tsx` write page paths as literals. **Rule:** ✅ theme requests go through `apiRequest` with seam paths. **Check:** a lint ban on `fetch(` in `src/hooks`. Confidence: High.

### Item 37 (compact): `test-ticket-ids-in-identifiers`
M · about 70–90 `sa<NNN>` tokens remain in test identifiers and strings (auth, backups, blog, crm, orgs), e.g. `_sa61_media_root_tmp_path`. Rule 29's scan covers file names, docstrings, and comments only. **Rule:** ✅ test names describe the behaviour. **Check:** extend the rule 29 token scan to identifiers in `tests/`. Confidence: Medium (a grep count).

### Item 38 (compact): `test-harness-parity`
M ·
- conftest `pytest_configure` and `pytest_collection_modifyitems` are missing in analytics and storage (10 of 12 have them);
- auth's test settings lack `DEFAULT_AUTO_FIELD`;
- blog and listings lack `USE_TZ`;
- vendor fakes come in 3 styles (`Fake*` classes in 3 modules, stubs in analytics, mocks only in 8).

**Rule:** ✅ a shared test-settings base and conftest plugin from core. **Check:** a harness diff of each module's test settings keys against the base. Confidence: Medium.

### Item 39 (compact): `pyproject-residue`
N ·
- auth, blog, crm, forms, and listings carry a stale comment, "centralized in root pyproject.toml", above sections they own;
- orgs' dev group uses `>=` floors where the others use carets;
- there are 6 `pythonpath` variants.

**Rule:** ✅ one pyproject template; rule 36 covers the sections. **Check:** a harness template diff. Confidence: High.

### Item 40 (compact): `manifest-option-residue`
B/O ·
- 3 option descriptions carry release stamps: analytics `provider` (v0.80.0), and social `:41` and `layout_variant` (v0.79.0);
- notifications' integer `webhook_ttl_seconds` carries a string `pattern` beside `min`.

**Rule:** ✅ no version stamps in manifest text; validation keys match the option type. **Check:** extend the rule 29 scan to `module.yml` descriptions, and have the loader refuse type-mismatched keys. Confidence: High.

### Item 41 (compact): `structured-log-fields`
K · `extra=` fields appear only in orgs (6 calls). The other 6 logging modules log message-only. **Rule:** a team decision (§11). Either ✅ the events named in rule N carry `extra=` fields, or record message-only as the convention and drop the orgs variant. **Check:** review rule. Confidence: High on the counts, Low on whether it matters. **Settled (SA294, 2026-10-16):** decisions rule 24 carries the convention — a security or audit event (operator access, a tenancy refusal, and their like) carries `extra=` fields, every other module log line stays message-only, and the clause stays a review rule.

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
   normalization and a pattern. ✅ **Merged (SA263):** rules 1, 3, and 12 carry the clause as
   described in item 4's closure note.
9. **Rule 14 — model basics** [Item 21]. Unchanged text, now enforced. Add ❌ `Meta.app_label` in a
   module model.
10. **Rule 17 — command flags** [Item 16]. ✅ `--json` for machine output. ✅ `--trigger
    {manual,scheduled}` defaulting to `manual` on schedulable commands. ✅ `--confirm
    <identifier>` on commands that delete a tenant's or the database's data. ✅ **Merged
    (SA282):** decisions rule 17 names the one organization-selector spelling, and harness
    rule 17 refuses the other spellings with controls.
11. **Rule 19 — guards** [Item 3]. ✅ Every module view declares its guard: permission classes
    or `min_org_role` for APIs, a mixin for pages, an explicit public declaration otherwise.
    ✅ Every README lists minimum roles. ❌ `AllowAny` plus a hand-written user check, or a page
    with no guard and no public-read declaration.
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
    module declares `quickscale-core`. ❌ An unparsed top-level manifest key. ✅ **Merged
    (SA263):** the credential-default clause of §[Module Conventions](#module-conventions) rule 1
    (vendor vocabulary and per-option QuickScale exceptions) is enforced by the rule-1 detector in
    proposal 8's harness clause.

---

**2026-10-16 (b) additions** (from items 27–41; ready to paste):

51. **CLI module knowledge** [27]. ✅ The CLI reaches module-specific behaviour through a manifest field or a generic adapter hook. ❌ A membership, `.get()`, or equality branch on a module name in core or the CLI outside rule 37's list.
52. **JSON-only APIs** [28]. ✅ The generated `REST_FRAMEWORK` sets JSON renderer and parser defaults. ❌ A per-view renderer or parser pin outside webhooks. ✅ **Merged (SA288):** decisions rule 9 carries the clause, and harness rule 9 checks the composed defaults and bans per-view pins with controls (a webhook's raw-body parser and a file upload's multipart parser stay local).
53. **One theme error parser** [29, 36]. ✅ Theme requests go through `apiRequest`, parse core's error shape only, and take paths from the seam. ✅ **Merged (SA289):** decisions rule 31 carries the clause; the seam's page-path table carries the blog, listings, crm, social, and analytics paths, a `moduleDocumentPaths` table carries the launcher pages' document destinations, and the theme's ESLint configuration fails a raw `fetch(` in `src/hooks` outside `useApi.ts`.
54. **One operator escape** [30]. ✅ The superuser escape is orgs' permission helper. ❌ A module-private superuser predicate. ✅ **Merged (SA290):** decisions rule 44 carries the clause, and harness rule 44 bans raw `is_superuser` reads in module source outside the helper, with forms' old predicate as the control.
55. **Manifest owns validation and throttle rates** [32, 34, 33]. ✅ Adapters evaluate the declared validation, and core merges declared throttle scopes. ❌ `re.compile`, a `DEFAULT_THROTTLE_RATES` literal in `adapter.py`, or a presence re-check in `checks.py`.
56. **Command scaffolding** [35, 31]. ✅ One core helper refuses scheduled runs while off; the transaction is in the service; the README lists every flag.
57. **Test and tooling templates** [37, 38, 39, 40]. ✅ Shared test-settings base and conftest plugin; one pyproject template; no ticket ids in test identifiers or manifest text.

## 7. Enforcement gaps

1. **Manifest loader is open-world on top-level keys — resolved (SA260).** `load_manifest` now
   refuses unknown keys; orgs' retired `middleware:`/`settings:` top-level blocks failed the load
   until they were removed and re-declared under `wiring_projections`. § Module Wiring Authority's
   "parsed-but-unread" ❌ [Item 10].
2. **Wiring-literal check covers `url_includes` only — resolved (SA260).** Harness rule 7 now
   reads `adapter.py` for literal `apps`, `middleware`, and URL-include declarations and literal
   appends; the app-declaration gate still checks the manifest projection [Item 10].
3. **URL prefix collisions are unchecked — resolved (SA261).** `collect_url_wiring` fails two
   *modules* mounting one prefix with different targets, naming both, and harness rule 7 runs the
   same predicate over every manifest's mounts in both include buckets; the identical
   `(prefix, target)` pair still merges and one module may chain several targets under one prefix
   (auth's `accounts/`) [Item 2].
4. **Capability names are open-world.** A misspelled capability is never collected [Item 15].
5. **Rule 29's second clause is unenforced.** The detector reads `test_*.py` only [Item 23].
6. **Rule 10's `<Module>Error` name is unchecked.** Any class ending `Error` passes, and modules
   with no `exceptions.py` are skipped [Item 7].
7. **Rule 14's `<event>_at` and `verbose_name` clauses are unchecked** [Item 21].
8. **Rule 4 is checked per file, not per name.** Private names in published files pass [Item 14].
9. **Rule 19's README duty and "logged in" spellings — resolved (SA262).** Harness rules 19 and
   38 check them [Item 3].
10. **Rule 41's theme clause — resolved (SA261).** Harness rule 7 scans the theme's TypeScript
    for quoted `/<mount>/api` literals (the theme's test files excepted) [Item 18].
11. **Rules 3/12 "defaults in code" and "values checked only in the manifest" are checked on
    settings reads only.** Adapter `.get(key, default)` and adapter value checks pass [Item 4].
12. **Core-rendered project code outside the harness corpus — resolved (SA262).** Harness rule 9
    renders and parses the managed social views [Item 11].
13. **Permissive allowed set — resolved (SA262).** `collect_wiring` admits only
    `DEFAULT_THROTTLE_RATES` from a module.
14. **Dead validation path.** Core's resolver step 5 (`resolver.py:278`) validates against
    derivation rule lists the loader refuses, so it looks like validation and checks nothing
    [Item 4]. **Resolved (SA263):** the step and `resolver_validation.py` are deleted;
    `resolve_module_config` projects derived settings and wiring directly, and the live refusal
    that remains is `_url_projection_issues`.
15. **Dangling secret marker.** Core's renderer leaves a blank `__QS_ENV__:` as the literal string
    `'__QS_ENV__:'` (`module_wiring.py:242`) [Item 4]. **Resolved (SA263):** a blank marker renders
    the literal empty string (`module_wiring.py` renders it explicitly; the regex is not widened
    to read an empty name), and harness rule 12's controls cover the blank/nonblank pair.
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

**2026-10-16 (b) rule audit (§3.5).** All 50 rules were tabled, and 11 rules' detectors were read at the code. All cross-references resolve (11 anchors, `frontend.md`, and every cited file). No declared config is unread. New or confirmed gaps:

19. **Rule 37 branch check is open-world over operators.** Only `Eq`/`NotEq` are matched (`_identity_module_lists.py:27`) [Item 27].
20. **Rule 40 claims checks that do not exist.** No detector checks `CommandError` or `BaseCommand` (decisions.md:1309 lists `CommandError`), and none checks "unlisted core ports". The rule 28 file allowlist is the only indirect guard.
21. **Rule 17's destructive duty triggers on command-name keywords.** `--dry-run` is matched as a substring, so a command named `_reset` or `_wipe` passes. `--json` is never required, and `--trigger` is checked only when present (`_package_commands.py:84–104`). Carried gap 2, still true.
22. **Rules 5 and 34 skip a module missing from `MODULE_LAYERS`.** Only a pytest backstops this, and the decisions.md layer table is never compared with `MODULE_LAYERS`.
23. **Capability declarations are open-world.** A misspelled capability on an `AppConfig` is never flagged, and the harness and core each keep a literal set with no cross-check. Carried gap 4, still true.
24. **Clauses with no detector and no open record:** rule 13's `TenantModelAdmin` registration, and rule 11's compare-against-members clause.
25. **The authoring checklist contradicts the code.** `module-extension.md:601` says core is edited "in exactly these places and no others". A React- or API-bearing module also edits the seam tables (`runtime/seam.py:89–97,179–184`) and `runtime/urls.py`. The checklist never mentions choosing a rule 5 layer or adding the `MODULE_LAYERS` entry.

Carried 2026-10-13 gaps re-checked:
- 1 (off-switch parity skips URL drops and trigger refusal): still true (`test_module_off_switch_parity.py:45–53`).
- 3 (rule 33 obligation-name and email-key stems; rule 34 matches `quickscale_` stems only): still true.
- 4 (`home` host route): still true.
- 5 (rule 29 scan reads `.py` and `module.yml` only, `_identity_tests.py:44–45`): still true.
- 6 and 7: closed.

**"Add one more" probe (§3.6):** 10 decisions are left open by the docs. The ledger lists all of them. The ones not covered above:
- layer choice criteria;
- whether to ship `checks.py`;
- which vendor-fake style to use;
- whether to pin renderers;
- whether to add `extra=` log fields;
- trigger choices beyond `manual`/`scheduled`;
- README flag depth.

Each maps to items 28, 31, 33, 35, 38, and 41, or to gap 25.

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

- **2026-10-16 (b) additions:**
  - **Storage's staff-gated markdownx endpoints** (rule 41): editors are staff-only by design.
  - **The `qs_` index prefix** (rule 25): declared for index names.
  - **Literal logger names in split files** (rule 46): split files log on the facade's logger.
  - **Backups' `admin` trigger:** it is backed by its admin actions (`admin.py:421,441`).
  - **Best-effort services:** analytics, notifications, and social swallow vendor failures so a request never fails on telemetry or delivery. Raise-only elsewhere.
  - **Inline cache purges outside a request transaction** (social's uncalled helper; orgs' purge command, after its delete).
  - **The auth↔orgs `required_modules` pair:** an install contract, not an import cycle.
  - (Correction: the *Logging* bullet above said "no structured fields". orgs has 6 `extra=` calls; see Item 41.)

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

**2026-10-16 (b):**
- *To the architectural audit:* `cli-module-name-branches`. 5 CLI sites name 6 modules outside rule 37's list, and the harness misses `in`/`.get()` branches. This adds to the watchlist `core-holds-module-vocabulary`.
- *To the technical audit:* none. No census variant is a live defect. The `--file` help mismatch stays with the tech audit.

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

- **H · Renderer and parser pinning per API** (2026-10-16 (b)).
- **J · Command transaction boundary and off-refusal spelling** (2026-10-16 (b)).
- **M · Test-settings key parity and conftest hooks** (2026-10-16 (b)).
- **K · Structured log fields** (2026-10-16 (b)).
- **C · Harness operator coverage for module-name branches** (2026-10-16 (b)).

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

### 2026-10-09 — SA265 closure (a/b/c; conventions harness 43 rules, with controls)

- 2026-10-09 — `upward-name-references`: **resolved** (SA265 a `d443aba0`, b `a6b58799`,
  c — the four-vocabulary registry in orgs is deleted: each module defines its own
  removal-obligation names as `quickscale_<module>:<purpose>`, senders own their email-template
  keys `quickscale_<module>.<purpose>` and bodies under `templates/quickscale_<module>/email/`
  registered through the `notification_templates` capability, and the Stripe customer identity
  moved off `Organization` onto billing's `BillingCustomer` table. Decision rule 2's table gains
  the removal-obligation row, rule 34's clause now also refuses a string constant, template key,
  or template path naming a higher- or same-layer module's concept, and the harness resolves
  every shipped string constant by its `quickscale_<module>` stem against the layer table.
  Limit recorded: a bare token like `billing_pricing_url` inside a sibling's own response
  vocabulary is not separately detected). Item 8.
- 2026-10-09 — `module-dependency-direction`: **resolved** (SA265 c — orgs publishes
  `org_scope_restored()` in `current_org`; crm's `ensure_org_default_stages` and blog's
  `_blog_org_scope` use it instead of importing `_restore_current_org_id`; social's admin
  drops the private re-export block and its tests import orgs' helpers directly; harness rule 4
  rejects importing or re-exporting another module's `_`-prefixed name, control included).
  Item 14.
- 2026-10-09 — `capability-collection`: **resolved** (SA265 b `a6b58799` — core's `CAPABILITIES`
  is the closed name-and-shape vocabulary, `collect_capabilities` is the only collector, orgs'
  and auth's `getattr` walks fold onto it, and the harness rejects a `collect_capabilities`
  argument outside the list, controls included). Item 15.
- 2026-10-09 — `session-and-host-names`: **resolved** (SA265 c — session keys are
  `quickscale_orgs:active_org_id`, `:debug_as_org_id`, and `:pending_org_invitation_token`;
  the debug banner's vestigial session lookup is removed; harness rule 33 rejects a
  `*SESSION_KEY` constant without the `quickscale_<module>:` stem, control included; decision
  rule 2's table gains the session-key row, and auth's dependency on the host route name `home`
  is recorded as a host contract in module-extension.md). Item 20.
- 2026-10-09 — `core-cli-module-knowledge`: **resolved as to the convention** (SA265 c —
  module-extension.md now lists every core edit a new module needs (catalog entry and count,
  `.env.example` spec entry, bundled-manifest sync) and no longer claims core and the CLI need
  no edit; harness rule 37 rejects a per-module constant or a module-name equality branch in core
  or the CLI outside a recorded exception list with reasons; the three dead analytics constants
  and the dead billing display branch are deleted. Recorded exceptions: core's exported
  option-name/environment constants (`contracts/module_options.py`), `manifest/social_manifest.py`'s
  social runtime (arch watchlist `core-holds-module-vocabulary`), `utils/_dependency_io.py`'s
  storage cloud-extra selection, and `commands/_module_embed.py`'s auth migration gate). Item 9.

### 2026-10-09 — SA264 closure (conventions harness 43 rules, controls included)

- 2026-10-09 — `module-error-http-mapping`: **resolved** (SA264 — every module exception
  hierarchy derives from `Exception`; billing, blog, listings, and notifications drop their
  `APIException` mix-ins and declare `status_code`/`default_code` instead, which core's one
  handler renders in rule 9's shape; `InsufficientCreditsError` answers 402
  `insufficient_credits` instead of inheriting 500 `billing_error`; decision rule 10 carries the
  mapping and refuses `APIException`; harness rule 10 rejects a hierarchy that derives from
  `APIException`, controls included). Item 5.
- 2026-10-09 — `startup-checks-and-errors`: **resolved as to the module conventions** (SA264 —
  every module-shipped error base is named after its module as spelled and `NotificationError`
  is renamed `NotificationsError` with its public surface and its forms consumer; retired
  setting names move from five modules' `checks.py` into their `module.yml` as
  `retired_settings`, read by the generic settings check through the shipped manifest; blog's
  `ready()` registers the generic check before its module checks; the four hand-listed
  declared-setting guards are deleted; harness rule 10 checks the base name, second roots,
  modules without `exceptions.py`, and the registration order; decision rules 6 and 10 carry
  the clauses. Recorded limit: core's `BackupError` (`dr_engine.primitives`, Track 2's surface)
  keeps its name, outside a module's `exceptions.py`). Item 7.

### 2026-10-10 — SA262 stage 1 (one session authentication class)

- 2026-10-10 — `unauthenticated-status-code`: **resolved** (SA262 stage 1 —
  `quickscale_core.runtime` ships one session authentication class
  (`QuickscaleSessionAuthentication`, 401 challenge through `authenticate_header`); the generated
  settings install it as `DEFAULT_AUTHENTICATION_CLASSES` through `compose_rest_framework`; the
  four per-module subclasses and CRM's and forms' direct `SessionAuthentication` references are
  replaced by it, so CRM and forms answer 401 where they answered 403; harness rule 9 rejects a
  module-defined `SessionAuthentication` subclass and an `authentication_classes` value outside
  core's class and the empty literal, controls included; decision rule 9 carries the clause and
  the release note records the status change). Item 6.

### 2026-10-10 — SA262 stage 2 (one throttle attachment and a closed admission list)

- 2026-10-10 — `throttle-attachment`: **resolved** (SA262 stage 2 — `quickscale_core.runtime`
  ships one scoped throttle class (`QuickscaleScopedRateThrottle`, keyed by the authenticated
  user's pk and otherwise by the canonical trusted-proxy client IP), installed as the generated
  settings' default scoped throttle through `compose_rest_framework`; blog's and forms'
  module-defined throttle classes are deleted and their views attach by `throttle_scope` alone;
  listings' publish API gains the `api_rate_limit` option and the `quickscale_listings_api`
  scope; orgs' invite API drops its `throttle_classes = ()` override and keeps its manual
  per-sender/per-organization buckets, recorded as the listed rule 32 exception (charged after
  the locked eligibility checks, the default anon/user rates still applying on top); harness
  rule 32 rejects any `throttle_classes` literal outside the rule 26 webhook exemption, controls
  included; decision rule 32 carries the clause and the exception).
  Item 12.
- 2026-10-10 — `collect_wiring` admission (enforcement gap 13): **resolved** (SA262 stage 2 —
  `collect_wiring` admits only `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]` from a module; any
  other `REST_FRAMEWORK` contribution fails the merge naming the module and sub-key, with unit
  controls; decision rule 30 carries the clause).

### 2026-10-10 — SA262 stage 3 (one list paginator and DRF social payload views)

- 2026-10-10 — `http-api-shape`: **resolved** (SA262 stage 3 —
  `quickscale_core.runtime` ships one list paginator (`PlainListPagination`: the page size is the
  `<THING>_PER_PAGE` setting named by each subclass's `page_size_setting`, client overrides stay
  ignored, the response stays the bare list, and a page past the end answers the empty list); billing's ledger drops its literal `25` for
  `transactions_per_page` and its public plan catalog gains `plans_per_page`; CRM's tags,
  companies, stages, contact-note, and deal-note lists (the two note actions included) gain their
  `<THING>_PER_PAGE` settings and page through core's paginator, and CRM's, forms', and billing's
  local paginator copies are deleted; forms' admin form list gains `QUICKSCALE_FORMS_PER_PAGE`;
  the core-rendered social payload views are DRF views that declare their public guard and answer
  DRF's 503 through the one error shape, never echoing exception text; harness rule 9 rejects a
  `PageNumberPagination` subclass outside core, a paginator subclass without `page_size_setting`,
  a `pagination_class` naming a non-core paginator, and a literal `page_size`, renders the
  managed social views module and parses it under the same rule, controls included; decision
  rule 9 carries the clause). Item 11.

### 2026-10-10 — SA262 stage 4 (guard declarations and README role listings)

- 2026-10-10 — `tenant-authorization`: **resolved** (SA262 stage 4 — billing's JSON endpoints
  adopt `IsAuthenticated` plus orgs' `HasOrgRole(OrgRole.OWNER)` on their shared base and its one
  public catalog declares `[AllowAny]`; the hand-written `_require_authenticated` /
  `_resolve_request_organization` helpers are deleted, and the dashboard runs on
  `LoginRequiredMixin` plus `OrgRoleMixin(OWNER)`; billing's README lists the minimum role per
  action and the JSON API contract drops "the billing-module pattern"; harness rule 19 gains two
  closed-world clauses — every view class declares a guard (DRF permission classes or a
  classified `get_permissions()` override on a DRF view, `min_org_role` beside its enforcing
  base, a login/role mixin, or a named public-read mixin, own or inherited; permission import
  aliases resolve) and an
  `AllowAny` view must not read `request.user.is_authenticated` by hand, directly or through a
  helper its effective (inherited) methods call, resolved across a private-sibling split — and
  rule 38 requires an identifiable minimum-role
  listing (a backticked `viewer`/`member`/`admin`/`owner` value or a value beside the word
  "role", or a role-value table cell under a role header) in the Public surface of a module that
  authorizes through orgs' role tools, both with controls; analytics' and billing's READMEs gain
  the listing and forms' public page declares a public-read mixin. Recorded limits: the role
  clause checks for an identifiable role listing, not the per-action prose; an unclassifiable
  `get_permissions()` return fails closed as no declaration, and a plain Django page's
  `permission_classes` is inert and is not a declaration). Item 3.

### 2026-10-10 — SA261 (one owner per URL prefix and the seam's module API bases)

- 2026-10-10 — `markdownx-shared-mount`: **resolved** (SA261 — the one shared, staff-guarded
  Markdownx URLconf moves to storage, the media layer both editor-owning consumers can depend
  on: storage mounts `markdownx/` and writes `MARKDOWNX_MARKDOWN_EXTENSIONS` and
  `MARKDOWNX_MEDIA_PATH = "markdownx/"`, blog and listings drop the mount and the settings, and
  listings depends on storage, so the upload path no longer depends on the installed module set;
  `collect_url_wiring` fails two *modules* mounting one prefix with different targets, naming
  both and preserving the equal-pair merge and one module's target chain (auth's `accounts/`),
  and harness rule 7 scans every manifest's mounts across both include buckets with the same
  predicate; decision rule 41 carries the clause and rule 28 moves the `markdownx_urls.py`
  allowance to storage. Release note: new editor uploads land under `markdownx/`). Item 2.
- 2026-10-10 — `mount-path-copies`: **resolved** (SA261 — the runtime seam gains
  `moduleApiPaths` (orgs, billing, crm, forms), resolved from the modules' named routes at rule
  7's `<mount>api/` boundary through `quickscale_core.runtime.seam`/`seam_tags` and rendered by
  all three seam producers; the theme hooks (`useOrgs.ts`, `useOrgNavigation.ts`,
  `useFormSchema.ts`, `FormRenderer.tsx`) read it and the two org help texts that spelled the
  mount are rewritten; harness rule 7 rejects a quoted `/<mount>/api` in the theme's TypeScript
  outside its test files, controls included; decision rule 41 carries the clause, rules 31 and
  37 name the seam key and its server-side table, and frontend.md records the field).
  Enforcement gap 10 resolved. Item 18.

### 2026-10-10 — SA260 (one off switch and a closed-world manifest surface)

- 2026-10-10 — `module-enabled-switch` (reopened), `manifest-declared-surface`, and
  `dependency-spec-sources`: **resolved** (SA260 — proposals 1 and 18 merge into rule 1 and the
  wiring/manifest sections; the loader refuses unknown top-level manifest keys, apps and
  middleware come only from `wiring_projections`, every module's manifest lists bare dependency
  names including `quickscale-core` with specs in its `pyproject.toml`, and the new off/on
  adapter-parity check rejects an off branch that drops apps or middleware).
- 2026-10-10 — Enforcement gaps 1 and 2: **resolved** (SA260 — the closed-world loader makes an
  unparsed top-level key fail the load, and harness rule 7 rejects literal `apps`/`middleware`
  and literal appends in adapters, both with control cases).

### 2026-10-11 — SA263 round-1 record (superseded by the correction note below)

- 2026-10-11 — `option-schema-and-validation`: **resolved** (SA263 — `module.yml` is the sole
  authority for option validation, canonical typing, normalization, defaults, and secret
  projection; all 12 adapters route through `build_generic_manifest_spec` and keep only the
  off-switch, composite, runtime-selection, provider-filtering, and managed-rendering hooks;
  core's resolver step 5 and `resolver_validation.py` are gone, the blank `__QS_ENV__:` marker
  renders the literal empty string, and the `path_or_absolute_url` kind carries the historical
  relative-or-absolute media behaviour through the owning option's declared default).
- 2026-10-11 — `secret-env-var-names`: **resolved** (SA263 — harness rule 1 now compares every
  credential reference default against a controlled vendor vocabulary and a per-option table of
  authorized QuickScale names with recorded reasons, including backups' two private-remote
  exceptions; controls reject an unlisted vendor-shaped name and a drifted exception).
- 2026-10-11 — Enforcement gaps 11, 14, and 15: **resolved** (SA263 — harness rule 12 reads
  `adapter.py` ASTs and rejects re-defaulting, coercion, case/whitespace rewriting,
  `or`-fallback, and validator-call re-checks on raw/resolved option containers inside the
  wiring paths, while the readiness predicates that consume canonical values stay legal; the
  fast-path diagnostics, the focused `scripts/tests_module_conventions/test_settings.py` run,
  and the full `scripts/tests_module_conventions/` population passed on the joined tree). The
  separated gaps 11 (rule 3 read coverage) and 14/15 (adapter reads and dead-renderer path) are
  closed by the same detector pair, and rule 3 now recognises a manifest-declared derived
  setting, so analytics' `QUICKSCALE_ANALYTICS_POSTHOG_HOST_OVERRIDE` read is declared surface
  rather than a violation. The adapter clause lives in
  `scripts/module_conventions/adapter_options.py` and the URL-family clause in
  `scripts/module_conventions/url_options.py`, with `rules_settings.py` keeping
  the rule aggregates and the other settings rules (each file stays under the
  quality gate's 800-line threshold).
- 2026-10-11 — Recorded residual, not closed: the three optional absolute-URL options
  (`storage.public_base_url`, `storage.endpoint_url`, `backups.remote_endpoint_url`) declare the
  `url` normalizer but an empty `validation` block instead of a full pattern; the harness's URL
  clause enforces the normalizer kind and refuses a blank declared pattern, and adding the
  patterns is a manifest edit the post-join review owns.

### 2026-10-11 — SA263 round-1 corrections

The original record above is retained as phase evidence, not current closure authority.
F-001–F-007 prompted corrections to absolute-URL pattern presence/admission, bounded adapter
provenance, vendor-default ownership, declarative cloud-only AWS aliases, frozen-media
persistence/state/reapply coverage, blank/default canonical parity, and root derived-setting
read collection. The patterns retain blanks and approved scheme-less inputs; media acceptance
is unchanged. Computed-setting presence guards are generic and loader-validated. The hook no
longer manufactures credential aliases. Existing historical tables and reconciliation entries
describe their audited states and are deliberately preserved. Independent correction review
and root-owned release checks still determine final delivery readiness.

### 2026-10-11 — SA263 round-2 corrections (F-002 / F-008)

Adapter enforcement now seeds provenance from generic-boundary arguments and the
actual post-hook calling convention, follows simple local calls, aliases, returned
hook factories, and loop/comprehension bindings, and distinguishes mapped settings
from structural package/target mappings. Neither annotations, parameter names nor a
coincidental `backend` key establish ownership. `.get(option, default)` in a wiring
guard remains a forbidden fallback, including `enabled`; direct off-switch reads,
`dict(spec.settings)` copies and composites remain legal. Readiness allowance is
bounded to pure selection results in a call graph rooted at
`resolve_manifest_module_options`, not arbitrary boolean helpers. Those query
bodies still participate in provenance analysis, and their results cannot replace
declared option/scalar settings. Dynamic dispatch and non-simple aliasing are not
claimed as covered by this static detector.

The three optional absolute-URL patterns admit bracketed IPv6 HTTP(S) authorities
and optional numeric ports in both canonical and bundled manifests. Configuration,
generic wiring, module adapters and registered wiring share that admission and the
existing trailing-slash canonicalization. Blanks and scheme-less spellings retain
their prior normalization, malformed authorities remain refused, and `MEDIA_URL`
continues to follow its separate frozen relative-or-absolute contract. Historical
audit tables and phase records above remain evidence of their dated states, not a
claim that the prior detector or URL patterns already met these corrections.

### 2026-10-11 — SA263 round-3 corrections (F-002)

Round-3 review reproduced two remaining simple-reference gaps in the round-2
detector: a locally aliased validator call and a factory returning a local alias
of its nested hook. Callable checks and hook seeding now use the same recursive,
cycle-safe reference resolver, resolving each factory return in that factory's
local assignment scope. Imported validator aliases, ordinary/annotated alias
chains, nested factory-return chains, keyword scalar arguments, mapped-setting
reads, and loop/comprehension values have negative module/file/line controls.
Permitted copies, composites, direct off switches, normalization-rooted readiness
selection, and structural package/target guards have matching controls. This is
bounded simple-static enforcement, not a claim about external factory bodies or
dynamic dispatch. Earlier audit tables and correction records describe their
dated states; independent correction review and root-owned release validation
remain the closure and delivery authorities.

### 2026-10-11 — SA263 round-4 corrections (F-002)

Round-4 review reproduced the remaining ordinary-closure gap: a factory's own
assignment scope was invisible to its nested hook, so `check =
validate_backend` or `coerce = bool` in the enclosing factory let the hook
re-validate or coerce declared option values with no diagnostic. Every
function now carries its lexical alias environment — module, enclosing factory
scopes at any depth, and the nested hook's own scope, innermost first — with
locally bound names (parameters, targets, nested defs, imports) shadowing outer
bindings, and definition names resolve through the same chain, so same-named
nested hooks in different factories keep separate identities instead of
collapsing onto one flat name table. The same environment feeds every seam:
hook seeding from the generic boundary, boundary/option argument tracing,
readiness-query roots, and the provenance walk. Class bodies stay transparent
to method scopes, an assignment below a nested def still resolves, and alias
cycles stay finite through AST identities.

Negative module/file/line controls cover the enclosing validator alias
(declared option, keyword scalar, simple alias, mapped setting, loop and
comprehension bindings, assignment-after-def, outer-factory depth, nested
helper, same-named duplicate hooks in both definition orders) and the enclosing
bool coercion, each through direct/alias/annotated chain/nested factory-return
spellings. Shadowing controls (hook-local rebinding and a same-named parameter)
and normalization-rooted readiness reached through an enclosing alias stay
legal, a closure cycle invents no target, and the diagnostics are stable across
repeated runs. This remains bounded simple-static enforcement — external
factory bodies, dynamic dispatch, and reflection are not claimed; earlier audit
tables and correction records describe their dated states, and independent
correction review and root-owned release validation remain the closure and
delivery authorities.

### 2026-10-11 — SA263 cycle-2 lexical binding corrections (F-001 / F-002 / F-003)

The round-4 record describes its implementation, not proof of complete lexical
binding: cycle-2 review reproduced captured-builtin alias capture, duplicate local
validator identity loss, and an intermediate factory parameter borrowing an outer
validator. Callable alias hops now resume in the defining frame. Parameters,
imports, assignments, and definitions stop lookup at every intervening frame;
ordinary positional/keyword callable actuals (and static defaults) are resolved
in their caller/definition frames and retained separately for each returned
closure. Validator policy is attached to the resolved definition identity, while
diagnostics retain the source callable spelling. Hook seeding, helper calls,
query selection, and scalar inspection share those semantic references.

Registered-rule controls require the captured `bool` diagnostic at line 8, the
two-factory validator diagnostic at line 6 (and its relocated line when reordered),
and no diagnostic for the nested factory parameter receiving identity at line 9.
The validator/builtin alternatives, intermediate import/definition shadows, and
distinct closure instantiations have paired controls and repeat-stability checks.
Dynamic reflection and external factory implementations remain outside this
bounded static analysis. Dated audit tables and earlier phase records are retained;
independent review and root-owned release validation still grade final acceptance.

- 2026-10-13 — **Re-run** at `0ddc7e30` (prompt v2, 2 passes, 5 parallel verification units + delta sweep; harness: 43 covered rules pass).
- 2026-10-13 — `module-enabled-switch`: resolved (SA260 2ce26e74/a206061a — verified; parity test closed-world over 12 modules, URLs/triggers unchecked).
- 2026-10-13 — `module-error-http-mapping`: resolved (SA264 ac157cb1 — verified; harness rule 10).
- 2026-10-13 — `startup-checks-and-errors`: still-open (narrowed to hand-listed setting names in analytics, billing, notifications checks.py).
- 2026-10-13 — `manifest-declared-surface`: resolved (SA260 — verified; loader refuses unknown top-level keys). The `contract_vintage.id` residual is split out as `contract-vintage-identity`.
- 2026-10-13 — `upward-name-references`: resolved (SA265 d443aba0/a6b58799 — verified; rule 34).
- 2026-10-13 — `core-cli-module-knowledge`: accepted (rule 37 closed exception list, SA265(c) 7bcbbd5a; revisit when the list grows).
- 2026-10-13 — `optional-sender-guard`: resolved (rule 43 — verified).
- 2026-10-13 — `module-dependency-direction`: resolved (rule 4 — verified in source; 38 cross-module private imports in tests are out of scope).
- 2026-10-13 — `capability-collection`: still-open (narrowed to orgs purge command getattr walk, `quickscale_orgs_purge_organization.py:533`).
- 2026-10-13 — `command-flag-conventions`: regressed (9592bab5 SA251(b) added `--organization` beside orgs' `--organization-id`; every other rule-17 clause holds).
- 2026-10-13 — `dependency-spec-sources`: still-open (narrowed to `--cov=src/...` in auth and blog).
- 2026-10-13 — `session-and-host-names`: resolved (rule 33 — verified).
- 2026-10-13 — `model-basics`: resolved (SA266 fed5307e — verified; rule 14).
- 2026-10-13 — `template-folder-depth`: resolved (SA266 — verified; auth's top-level `account/` files are allauth shims, consistent by design).
- 2026-10-13 — `test-file-names`: resolved (rule 29 — verified).
- 2026-10-13 — `ticket-ids-in-shipped-source`: resolved (SA266 — verified, 0 ids; READMEs/templates unscanned).
- 2026-10-13 — `constraint-purpose-tokens`: resolved (SA266 — verified; amended rule 25).
- 2026-10-13 — `contract-vintage-identity`: **new**, open.
- 2026-10-13 — Prior resolved IDs (`markdownx-shared-mount`, `tenant-authorization`, `option-schema-and-validation`, `unauthenticated-status-code`, `http-api-shape`, `throttle-attachment`, `mount-path-copies`, `secret-env-var-names`, and the 43 listed in §2): still resolved (harness pass at HEAD; no regression found by the delta sweep).
- 2026-10-15 — `command-flag-conventions`: resolved (SA282 — the billing reconcile command selects with `--organization-id`, decisions rule 17 names the one spelling, and harness rule 17 bans `--organization`, `--org`, and slug declarations without `--organization-id`, with controls and exact-findings rows).
- 2026-10-15 — `contract-vintage-identity`: resolved (SA282 — every `contract_vintage` carries an `sa<NNN>-<slug>` id, the loader refuses a missing one with a control manifest, backups and social gained new ids in both manifest copies, and the CLI's version-comparison fallback is deleted so recorded adoption is the one mechanism).
- 2026-10-16 — **Re-run** at `30b0b6b1` (prompt v2, 1 delta pass; harness: 43 covered rules pass).
- 2026-10-16 — `startup-checks-and-errors`: resolved (SA283(a) 1817ef2d — verified; rule-6 scan rejects own-setting literals in checks.py, with controls).
- 2026-10-16 — `capability-collection`: resolved (SA283(b) 98d4e4b7 — verified; purge collects `organization_cache_invalidation_hooks`; obligation hook lookups consistent by design).
- 2026-10-16 — `dependency-spec-sources`: resolved (SA283(c) bf7e242e — verified; 12/12 `--cov=<import package>`).
- 2026-10-16 — `api-renderer-parser-pinning`: resolved (SA288 — decisions rule 9 carries the JSON-only clause; harness rule 9 checks both composed defaults and bans per-view renderer/parser pins with controls; billing, listings, orgs, blog, and the rendered social views dropped their pins, while the blog media upload keeps its multipart policy).
- 2026-10-16 — `theme-retired-error-shapes`: resolved (SA289 (a) — the theme's `useApi.ts` parses only the one QuickScale error shape, and `useApiErrors.test.ts` rejects the retired string-`error` and `errors`-key payloads; proposal 53's rule-31 merge lands with SA289 (b)).
- 2026-10-16 — `theme-request-paths`: resolved (SA289 (b) — every theme hook request goes through `apiRequest`, the SPA's blog, listings, and crm page routes and navigation read the seam's `modulePaths` (which gained `blog` and `listings` entries resolved from `quickscale_blog_shell`/`quickscale_listings_shell`), a raw `fetch(` in `src/hooks` fails the theme's ESLint outside `useApi.ts`, and proposal 53 merged into decisions rule 31).
- 2026-10-16 — `test-ticket-ids-in-identifiers`: resolved (SA293 (a) — every ticket id left the 12 modules' tests, and rule 29 scans identifiers and string literals in every `tests/` entry, in any case and embedded ids included, with controls; proposal 57's rule-29 clause lands here, items 38–40 with SA293 (b)–(d)).
- 2026-10-16 — `superuser-escape-spelling`: resolved (SA290 — orgs publishes one `is_platform_operator(user)` helper; forms' `_is_superuser` and every orgs copy call it, and harness rule 44 bans raw `is_superuser` reads in module source outside it, with forms' old predicate as the control).
- 2026-10-16 — `test-harness-parity`: resolved (SA293 (b) — one core test-settings base (`quickscale_core.testing.settings`, `BASE_TEST_SETTINGS_KEYS` plus the database, secret-key, and schema helpers) and one conftest plugin (`quickscale_core.testing.pytest_plugin`, the `bypass_rls` hooks) are adopted by all 12 modules; analytics and storage gained the hooks, auth gained `DEFAULT_AUTO_FIELD`, and blog and listings gained `USE_TZ`; harness rule 18 reads the base from the corpus, diffs every module's test-settings keys against it, and requires both hooks from the plugin, with controls; proposal 57's rule-11 and rule-18 clauses land here).
- 2026-10-16 — `structured-log-fields`: resolved (SA294 — decisions rule 24 carries the convention: a security or audit event carries `extra=` fields and every other module log line stays message-only; orgs' operator-access and VIEW-AS audit logs are the recorded sites, and the clause stays a review rule).
- 2026-10-16 — `core-cli-module-knowledge`: accepted, carried (revisit trigger not fired).
- 2026-10-16 — Tech hand-off `backups-restore --file` help/behavior: rejected (single member, §0 gate 1; tech-audit owns it).
- 2026-10-16 — All other prior IDs: still resolved (harness pass at HEAD; delta has no convention-breaking commit).
6. Does forms' cross-tenant `operator_access` need its own predicate, distinct from orgs' superuser escape? → `superuser-escape-spelling`
7. Do host projects post form-encoded bodies to the crm, forms, or notifications APIs? This sets the release-note weight of a JSON-only default. → `api-renderer-parser-pinning`
8. Should module logs carry structured fields? → `structured-log-fields` (settled by SA294: decisions rule 24 carries the convention — a security or audit event carries `extra=` fields; every other module log line stays message-only).
