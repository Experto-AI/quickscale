# Module Conventions Inventory

Audited: c10b529e (v89) · 2026-10-03 · working tree dirty (uncommitted edits to `docs/others/arch-audit.md` and `tech-audit.md` only; no source) · prompt: deep-coherence-audit v1 · passes: 2 (this re-run; 8 in all)
**SA215 closing pass:** 2026-10-02 · see [Closing pass](#closing-pass-sa215-2026-10-02)

## Coherence audit re-run (2026-10-03)

The conventions work landed between the sixth pass and this one: 148 non-merge commits
(`58e73cc7..c10b529e`), and rule 40's conformance harness (`scripts/check_module_conventions.py`)
now covers 36 of rules 1–39. At `c10b529e` it passes, with 205 control-case tests. Rules 21, 27,
and 30 sit in its `OPEN_RULES` because other checks hold them: rule 21 is a review rule, rule 27
has the user-FK gate, and rule 30 is enforced in `collect_wiring`. This pass therefore did three
things:

1. It **closed** the prior items whose rule the harness now holds, each re-verified by an
   independent spot-check as well as by the harness (see the [reconciliation log](#reconciliation-log)).
2. It **looked for drift the harness cannot see**: its allowlists and exemptions (lines 45–323),
   the files its detectors do not scan, and patterns the split wave (SA231/SA232) introduced after
   the rules were written.
3. It **corrected two prior cells**. `theme-module-presence` and `module-lists-outside-members`
   each missed a member that already existed at `58e73cc7`.

It found six new drift items (sections 42–47), proposed as D43–D48 for the maintainer to decide,
and left three prior items still open.

### Orientation (2026-10-03)

- **Populations.** The 12 modules (the `teams` placeholder is deleted, rule 18). Inside them: 12
  `services.py` surfaces with `is_enabled()`; 5 settings-snapshot classes (§42); 2 optional email
  senders (§43); 10 split-facade files in 5 modules (auth, backups, billing, notifications, orgs) over 55 private files (§46); 12 `pyproject.toml` (§47); 3
  producers of the theme seam (`index.html.j2` and the two `social/*.html.j2` pages, §33). Outside
  them: the harness and its test-owned mapping, core's `collect_wiring` and `generator/seam.py`,
  the generated `urls.py.j2`, orgs' `TenantMiddleware`, and the root `mypy.ini`.
- **Shared namespaces.** Same as before, plus two the split wave exposed: **URL paths** that both
  the generated project's React shell routes and module mounts claim (§45), and **log channels**
  that split modules either keep or rename (§46).
- **Declared conventions.** decisions.md § Module Conventions rules 1–40, linked from
  module-extension.md's authoring checklist. Enforcement: the rule 40 harness (36 rules,
  closed-world allowlists); `collect_wiring` (rule 30); the user-FK gate in orgs' tests (rule 27);
  the SA228 import-layer test; the seam validator in the theme's TypeScript.
- **Reference members.** crm and notifications, unchanged. notifications is now the reference for
  facades (one `_settings` module, `__all__`) and for `on_commit`, but it is also an outlier in §42
  (a public snapshot class that another module reads) and §21 (no rollback test).
- **Activation.** `active: A–H, J–P · inert: Q (English only by rule 14; no drift)`. I (outbound
  integrations) showed no drift that passes the cost gate. K (observability) is active again
  because of §46's log channel.
- **Scope.** As before. The harness itself was read for its allowlists and scan sets, not
  re-audited for detector correctness. SA230 reviewed that, and the arch audit samples it.
- **Delta classification** (`58e73cc7..c10b529e`, 148 commits):
  - *Convention-applying* (the SA-numbered convention commits): SA217–SA229, SA215's four slices, SA219, and SA220.
  - *Convention-breaking* (3 patterns, none a new member): the SA231/SA232 splits added most of the 55 private
    files with no rule for their names, re-exports, or log channels (§46). `b825bb6d` (SA219) made
    `index.html.j2` discovery-rendered but left the two social seam pages hand-written (§33).
    `30759c78` (SA223) named the CRM shell route `crm-shell` in the host template rather than in a
    module namespace (§45).
  - *Unrelated* (the rest): roadmap and CHANGELOG edits, dr_engine and CLI splits with no module
    surface.
- **Companion audits.** `tech-audit.md` and `arch-audit.md`, both at `c10b529e`, have no *Coherence
  hand-offs* heading. Two of their leads passed §0 here:
  - tech-audit §9: `TenantMiddleware` hard-codes `/orgs/`, `/orgs/api/`, `/accounts/`. Folded into §45.
  - arch-audit: split facades carry a patch-through-facade contract that no decision states.
    Recorded in §46 as the naming and re-export convention; the structural root stays with the
    arch audit.
- **Coverage.** Every module's `src/` was scanned by script for each new aspect, and each hit was
  opened at its location. Read in full: the harness's constants block, `generator/seam.py`, the
  three seam producers, `urls.py.j2`, every `is_enabled()`, the 5 snapshot classes, forms'
  `_email.py`, orgs' notification sender, and billing's `_subscription_mutations.py` role
  re-check. Not read: module test bodies beyond `on_commit`/rollback markers and patch targets;
  the theme's TypeScript beyond the seam validator.

### Index

```yaml
schema: coherence-audit/v1
audited: c10b529e
items:
  # decided, members still to change
  - {id: write-effects-on-commit, status: decided, rule: "rule 21 (D24)", aspect: F, cost: [defect], members_diverging: [notifications], population: modules-with-effects(5), check: review+rollback-test, closed_world: false, handoff: [], first_seen: 2026-09-26, last_verified: 2026-10-03}
  # resolved — every member conforms and the rule 40 harness (or the named check) holds it
  - {id: settings-snapshot-readers, status: resolved, rule: "rule 42 (D44)", aspect: B, check: conformance, closed_world: true, first_seen: 2026-10-03, last_verified: 2026-10-03}
  - {id: optional-sender-guard, status: resolved, rule: "rule 43 (D45)", aspect: C, check: conformance, closed_world: true, first_seen: 2026-10-03, last_verified: 2026-10-03}
  - {id: mount-path-copies, status: resolved, rule: "rule 41 (D43)", aspect: A, check: conformance, closed_world: true, first_seen: 2026-10-03, last_verified: 2026-10-03}
  - {id: org-role-check-copies, status: resolved, rule: "rule 44 (D46)", aspect: E, check: conformance+review, closed_world: false, first_seen: 2026-10-03, last_verified: 2026-10-03}
  - {id: mypy-overrides-unread, status: resolved, rule: "rule 45 (D47)", aspect: N, check: conformance, closed_world: true, first_seen: 2026-10-03, last_verified: 2026-10-03}
  - {id: split-facade-conventions, status: resolved, rule: "rule 46 (D48)", aspect: L, check: conformance+review, closed_world: false, handoff: [arch], first_seen: 2026-10-03, last_verified: 2026-10-04}
  - {id: theme-module-presence, status: resolved, rule: "rule 31 (D34)", aspect: P, check: conformance, closed_world: false, first_seen: 2026-09-28, last_verified: 2026-10-03}
  - {id: module-lists-outside-members, status: resolved, rule: "rule 37 (D40)", aspect: L, check: conformance, closed_world: false, first_seen: 2026-09-28, last_verified: 2026-10-03}
  - {id: shared-setting-writes, status: resolved, rule: "rule 30 (D33)", aspect: A, check: "collect_wiring (apply)", closed_world: true, resolved_by: cb750c51, first_seen: 2026-09-28, last_verified: 2026-10-03}
  - {id: throttle-scopes-and-rates, status: resolved, rule: "rule 32 (D35)", aspect: A, check: conformance, closed_world: true, resolved_by: c3c99253, first_seen: 2026-09-28, last_verified: 2026-10-03}
  - {id: namespace-prefix-principle, status: resolved, rule: "rule 33 (D36)", aspect: A, check: conformance, closed_world: true, resolved_by: 6fe010b4, first_seen: 2026-09-28, last_verified: 2026-10-03}
  - {id: upward-name-references, status: resolved, rule: "rule 34 (D37)", aspect: C, check: conformance, closed_world: true, resolved_by: 2352acf1, first_seen: 2026-09-28, last_verified: 2026-10-03}
  - {id: secret-resolution-path, status: resolved, rule: "rule 35 (D38)", aspect: B, check: conformance, closed_world: true, resolved_by: 17d4985d, first_seen: 2026-09-28, last_verified: 2026-10-03}
  - {id: type-check-config, status: resolved, rule: "rule 36 (D39)", aspect: N, check: conformance, closed_world: true, resolved_by: c75b5588, first_seen: 2026-09-28, last_verified: 2026-10-03}
  - {id: readme-content-accuracy, status: resolved, rule: "rule 38 (D41)", aspect: O, check: conformance, closed_world: true, resolved_by: 49b709f2, first_seen: 2026-09-28, last_verified: 2026-10-03}
  - {id: manifest-dependency-spec, status: resolved, rule: "rule 39 (D42)", aspect: C, check: conformance, closed_world: true, resolved_by: 92c9566f, first_seen: 2026-09-28, last_verified: 2026-10-03}
  - {id: settings-names, status: resolved, rule: "rule 1", aspect: A, check: conformance, closed_world: true, resolved_by: 79b3f079, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: module-enabled-switch, status: resolved, rule: "rule 1", aspect: B, check: conformance, closed_world: true, resolved_by: 97ac9187, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: settings-readers-and-defaults, status: resolved, rule: "rule 3", aspect: B, check: startup+conformance, closed_world: true, resolved_by: 2b44e473, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: cross-module-settings-reads, status: resolved, rule: "rules 3–4", aspect: C, check: conformance, closed_world: true, resolved_by: c460d46f, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: secret-env-var-names, status: resolved, rule: "rule 1", aspect: A, check: conformance, closed_world: true, resolved_by: 480735c9, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: module-dependency-direction, status: resolved, rule: "rules 4–5", aspect: C, check: "conformance + SA228 import-layer test", closed_world: true, resolved_by: 10dc1691, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: identity-stem, status: resolved, rule: "rule 2", aspect: A, check: conformance, closed_world: true, resolved_by: 6fe010b4, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: url-mounts-and-names, status: resolved, rule: "rule 7", aspect: H, check: conformance, closed_world: true, resolved_by: 30759c78, note: "module side only; host-side copies are mount-path-copies", first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: templates-static-tags, status: resolved, rule: "rule 8", aspect: A, check: conformance, closed_world: true, resolved_by: 49982a73, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: http-api-shape, status: resolved, rule: "rule 9", aspect: H, check: conformance, closed_world: true, resolved_by: dcd3bda0, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: startup-checks-and-errors, status: resolved, rule: "rule 10", aspect: D, check: conformance, closed_world: true, resolved_by: 88dad552, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: package-files, status: resolved, rule: "rules 11, 28", aspect: L, check: conformance, closed_world: true, resolved_by: c75b5588, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: required-tests, status: resolved, rule: "rule 11", aspect: M, check: conformance, closed_world: true, resolved_by: 9382e6ed, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: readme-outline, status: resolved, rule: "rule 11", aspect: O, check: conformance, closed_world: true, resolved_by: 49b709f2, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: model-choices, status: resolved, rule: "rule 11", aspect: G, check: conformance, closed_world: true, resolved_by: bf60796f, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: option-schema-and-validation, status: resolved, rule: "rule 12", aspect: B, check: conformance, closed_world: true, resolved_by: d0b148c9, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: tenant-model-base, status: resolved, rule: "rule 13", aspect: G, check: startup+conformance, closed_world: true, resolved_by: bf60796f, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: model-basics, status: resolved, rule: "rule 14", aspect: G, check: conformance, closed_world: true, resolved_by: bf60796f, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: package-root-init, status: resolved, rule: "rule 15", aspect: D, check: conformance, closed_world: true, resolved_by: b315009f, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: signals-vs-receivers, status: resolved, rule: "rule 16", aspect: L, check: conformance, closed_world: true, resolved_by: b315009f, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: command-behavior, status: resolved, rule: "rule 17", aspect: J, check: conformance, closed_world: true, resolved_by: 84652d2d, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: package-tooling, status: resolved, rule: "rule 18", aspect: N, check: conformance, closed_world: true, resolved_by: 469e3b7d, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: tenant-authorization, status: resolved, rule: "rule 19", aspect: E, check: conformance, closed_world: false, resolved_by: ab3ec43e, note: "views only; a service-layer copy is org-role-check-copies", first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: email-sender, status: resolved, rule: "rule 20", aspect: I, check: conformance, closed_world: true, resolved_by: 0c6f96cd, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: analytics-event-ownership, status: resolved, rule: "rule 22", aspect: C, check: conformance, closed_world: true, resolved_by: 0c6f96cd, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: service-surface, status: resolved, rule: "rule 23", aspect: D, check: conformance, closed_world: true, resolved_by: b18032e3, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: current-time-call, status: resolved, rule: "rule 24", aspect: G, check: conformance, closed_world: true, resolved_by: c75b5588, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: cache-key-stem, status: resolved, rule: "rule 24", aspect: A, check: conformance, closed_world: true, resolved_by: 10dc1691, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: constraint-index-names, status: resolved, rule: "rule 25", aspect: A, check: conformance, closed_world: true, resolved_by: c75b5588, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: inbound-webhooks, status: resolved, rule: "rule 26", aspect: H, check: conformance, closed_world: true, resolved_by: f6ad7784, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: test-file-names, status: resolved, rule: "rule 29", aspect: M, check: conformance, closed_world: true, resolved_by: 730456cb, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: user-fk-on-delete, status: resolved, rule: "rule 27", aspect: G, check: "user-FK gate (orgs tests)", closed_world: true, resolved_by: fa0b882b, first_seen: 2026-09-26, last_verified: 2026-10-03}
  - {id: py-typed, status: resolved, rule: "rule 24", aspect: D, check: conformance, closed_world: true, resolved_by: 6ea37301, first_seen: 2026-09-26, last_verified: 2026-10-03}
```

`resolved_by` names the commit that brought the last member into line, as found in the
2026-10-03 log. Where several commits did, it names the most representative one. The harness
slice that holds each rule is in its commit message.

### Summary (2026-10-03)

| ID | Aspect | Cost | Diverging / population | Status |
|---|---|---|---|---|
| `theme-module-presence` | P | ambiguity, defect (latent) | 2 / 3 seam producers | resolved (rule 31) |
| `mount-path-copies` | A | collision, tax | 6 modules' mounts copied in host code / 10 | resolved (rule 41) |
| `write-effects-on-commit` | F | defect (unproven) | 1 / 5 | decided |
| `settings-snapshot-readers` | B | ambiguity, tax | 5 / 12 | resolved (rule 42) |
| `optional-sender-guard` | C | ambiguity | 2 / 2 | resolved (rule 43) |
| `org-role-check-copies` | E | ambiguity | 1 / 6 | resolved (rule 44) |
| `mypy-overrides-unread` | N | ambiguity, tax | 10 / 12 | resolved (rule 45) |
| `module-lists-outside-members` | L | tax, ambiguity | 1 list / 10 | resolved (rule 37) |
| `split-facade-conventions` | L, K | tax, ambiguity | 5 / 5 split modules | resolved (rule 46) |
| 41 items of passes 1–6 | A–O | see index | 0 | resolved |

Of the 44 prior items, 43 are resolved and 1 is still decided with members to change. All six
new items are resolved (rule 41 with rules 42–43, SA235 and SA236; rules 44–45 with SA237;
rule 46 with SA238). Each is small, and none needs a new mechanism; each is a decision plus one
harness clause. The two corrections and `mount-path-copies` sat in generator templates that rule
40's `.py`-only scan never read; rules 7, 31, and 37 now read `generator/templates/**/*.j2`,
closing that gap ([Enforcement gaps](#enforcement-gaps) 13).

## Coherence audit re-run (2026-09-28, sixth pass)

This file is the project's conventions inventory, so the coherence audit updates it in place instead
of starting a rival file. The sixth pass re-checked the cells of sections 1–31 against the code
(recounted by script wherever a count could be scripted; the cells only spot-checked are named in
the [reconciliation log](#reconciliation-log)). It corrected eight cells in place (sections 5, 9,
11 twice, 20, 25, 26, and the `db_table` row of *Module independence*), added one cell (section 3),
and added sections 32–41 with decisions D33–D42 (proposed in this pass, decided the same day).
The maintainer decided D33–D42 on 2026-09-28 (D36 as option B, the others as recommended); they
are decisions.md rules 30–39, and enforcement moves to rule 40.
Where a correction, a finding, or a decision changes the scope of a roadmap ticket (SA219–SA227),
that ticket now says so.

### Orientation

- **Populations.** The 12 packaged modules (`teams` is a README-only placeholder, D21) and, inside
  them: 12 manifests, 12 `adapter.py` wiring hooks writing one shared settings file, 12 READMEs, 12
  test suites, 15 management commands (backups 9, orgs 4, forms 2), 3 modules with throttled
  endpoints (billing, blog, forms), 5 modules resolving vendor secrets (analytics, backups, billing,
  notifications, storage). The code *outside* the members that names them: core
  (`contracts.module_catalog`, `module_wiring`, `contracts.resolvers`), the CLI (`module_config`), the
  generator templates and React theme, `scripts/` gate lists, and orgs' `tenancy` registry.
- **Shared namespaces.** Django settings keys (module-prefixed and third-party); environment
  variables; app labels and tables; constraint and index names (one PostgreSQL schema); PostgreSQL
  functions and triggers created by raw SQL (`qs_*`); advisory-lock keys; reverse accessors on
  `User` and `Organization`; URL namespaces and mounts; template, static, and template-tag names;
  cache keys; DRF throttle scopes and `DEFAULT_THROTTLE_RATES`; analytics event names; command names;
  the theme's `window.__QUICKSCALE__.modules` flags.
- **Declared conventions.** [decisions.md § Module Conventions](../technical/decisions.md#module-conventions)
  rules 1–30 when audited (1–40 after D33–D42), linked from module-extension.md's authoring
  checklist (where a module author looks).
  Checks: the rule 40 conformance harness
  ([`scripts/check_module_conventions.py`](../../scripts/check_module_conventions.py)), the core ↔
  module import linter, `.env.example` conformance, the user-FK `on_delete` gate (rule 27), the
  PostgreSQL isolation gate, core's page-style contract, and `scripts/check_security_gates.py`.
  See the [Closing pass](#closing-pass-sa215-2026-10-02) for what the harness covers and the rules
  it delegates.
- **Reference members.** crm (on `TenantModel`, `services.py`, the most complete test set) and
  notifications (`transaction.on_commit`, one error base, keyword-only services). Neither is complete:
  crm has hand-written `is_staff` checks, and notifications' README documents none of its options.
- **Activation.** `active: A–Q · inert: none`. I (outbound integrations) and K (observability)
  showed no drift that passes the cost gate (see [Consistent by design](#consistent-by-design)).
- **Scope.** `quickscale_modules/*` (12), plus core, CLI, generator templates, the `showcase_react`
  theme, and `scripts/` where they name modules. Excluded: `quickscale_devtools` (not a member),
  host projects such as `bap-web` (not in this repository).
- **Delta since the first write-up** (`1dc8248b..58e73cc7`, 5 commits): `55d1a143`, `8a99bdd9`,
  `60cc71c7`, `58e73cc7` are *unrelated* to member code (they record conventions in docs);
  `fa0b882b` is *convention-applying* (SA35's gate stops accepting `PROTECT`, rule 27). No module
  source changed, so every earlier cell was expected to hold. Eight did not: the first write-up had
them wrong (corrections in place).
- **Companion audits.** `tech-audit.md` (v5, `cdb6223f`) and `arch-audit.md` (v8, `cdb6223f`) have no
  *Coherence hand-offs* section; a search for convention-shaped leads in both found none.
- **Coverage.** Every member was read for every cell through scripted census (grep, manifest and
  settings parsers, run with `poetry run python` from the repository root) with each hit opened at its
  location. Not read: the theme's TypeScript beyond its page and component list; module tests beyond
  file names, settings, and fakes.

### Sixth-pass index and summary

Superseded by the 2026-10-03 index above; the sixth pass's statuses are kept in the
[reconciliation log](#reconciliation-log).

## Closing pass (SA215, 2026-10-02)

Rule 40's conformance harness (`scripts/check_module_conventions.py`, registered gate
`check-module-conventions`) covers rules 1–20, 22–26, 28–29, and 31–39 over every `module.yml`,
every module's source, and core's and the CLI's option handling, with a control case per covered
rule in `scripts/test_check_module_conventions.py`; the live tree passes. Rules 27 and 30 stay out
of the harness by rule 40's own carve-out; rule 21 is a review rule under rule 21 itself. Their
owning checks:

- **Rule 21 (effects of a write)** is a review rule with a rollback test per module; SA216 rebuilds
  the account-removal path that uses it.
- **Rule 27 (`on_delete` on `User`)** is enforced by the user-FK conformance gate
  (`orgs/tests/test_user_fk_conformance.py`). Its reach is the apps that suite installs, so a
  generated project's own apps remain a review-rule boundary; the reason is recorded in
  decisions.md rule 27.
- **Rule 30 (settings written by module wiring)** is enforced in `apply` by
  `quickscale_core.module_wiring.collect_wiring`, which fails on an unequal shared key and
  deep-merges `REST_FRAMEWORK`; its control cases are in
  `quickscale_core/tests/test_module_wiring.py`.

The enforcement gaps the audit recorded are closed or accepted:

- Gap 1 (no conformance test) is closed by the harness above.
- Gaps 2 and 4–12 are closed by the convention tickets and the harness clauses they landed: the
  page-style contract is discovery-driven and flat, the isolation gates derive their module sets and
  social ships its `test_rls_boundary.py`, the README check reads option keys and command names,
  references by name are checked over the layer table, the root `mypy.ini` carries one section per
  module with no per-module `[tool.mypy]`, option `validation:` blocks are read by core, the
  manifest loader refuses version specifiers, `collect_wiring` refuses unequal shared values (gap
  10's first clause; its generated-composition clause is recorded below), the gate is renamed, and
  `TENANT_TABLE_REGISTRY` is test-owned.
- Gap 3 (the user-FK gate sees only its suite's apps) is accepted, as recorded in decisions.md
  rule 27.
- Three residuals are accepted alongside the fixed checks: a module's `test_isolation.py` is
  invoked explicitly by the PostgreSQL gate and does not self-enroll; rule 38's README match is a
  substring anywhere in the file (a floor, as D41 records); and the generated `base.py` still
  spreads a module's `REST_FRAMEWORK` keys over the template defaults, so a module can override the
  `anon`/`user` throttle rates, which no gate owns.

The names decisions.md quoted from the audit-time shipped state now carry the renamed forms
(`QUICKSCALE_MODE` → `QUICKSCALE_ORGS_MODE`, `backups_create` → `quickscale_backups_create`,
`quickscale_modules_<module>` app labels → `quickscale_<module>`). The audit-time prose of the
[Coherence audit re-run](#coherence-audit-re-run-2026-09-28) section and the evidence cells in
sections 1–41 below remain the 2026-09-28 audit record, not a description of the current tree; the
2026-10-03 index statuses and this closing pass are the current state.

Two sections 1–41 items are not closed by this pass but are carried, with the corrections the
2026-10-03 pass above records: `theme-module-presence` (the social seam pages still hand-write
module flags and paths) and `module-lists-outside-members` (the generated shell routes stay
literal). Their fix is host-template and seam work, owned by SA235 together with its mount-path
item, so they are the pass's deferred remainder rather than accepted exceptions.

---

> **Status:** decisions D1–D9 (first pass) and D10–D14 (second pass: URLs, templates, APIs,
> checks and errors, package files) are taken; D15–D21 (third pass: manifest option schema, tenant
> models, model basics, `__init__.py`, signals, command behavior, package tooling; sections 14–20)
> are decided, as decisions.md rules 12–18 (D15 → 12, D16 → 13, … D21 → 18; enforcement was rule 19, now 25).
> D22–D27 (fourth pass: authorization, email, effects on commit, analytics events, service
> surface, small leftovers; sections 21–26) are decided, as decisions.md rules 19–24 (D22 → 19, …
> D27 → 24).
> D28–D32 (fifth pass: constraint and index names, inbound webhooks, the SA35 user-FK rule, private file
> names, test names; sections 27–31) map to decisions.md rules 25–29 (D28 → 25, … D32 → 29);
> enforcement moves to rule 30 (now rule 40). D28, D29, D31, and D32 are decided as option A, D30 as option B.
> Two D15 details and one D20 item were settled during review (marked in place). Section 14 also covers core and CLI code, not only `quickscale_modules/`. All are recorded in
> [decisions.md § Module Conventions](../technical/decisions.md#module-conventions), which wins on any
> conflict with this file. Evidence for SA215, taken 2026-09-26 from `v89` (`quickscale_modules/*/module.yml`
> and module source under `src/quickscale_modules_<name>/`). It records what exists; the convention
> itself is decided in SA215 and lands in [decisions.md](../technical/decisions.md).
> D33–D42 (sixth pass, 2026-09-28: shared setting keys, the theme seam, throttles, namespace stems,
> references by name, secrets, type checking, module lists, README content, manifest dependencies;
> sections 32–41) are decided, as decisions.md rules 30–39 (D33 → 30, … D42 → 39; D36 as option B,
> the others as recommended); enforcement moves to rule 40.

Neither the [architecture audit](../others/arch-audit.md) (structural risk) nor the
[technical audit](../others/tech-audit.md) (defect sweep) checks cross-module consistency, so this is
the first inventory of it. Each section ends with the **drift** it shows.

Scope: the twelve packaged modules (`analytics`, `auth`, `backups`, `billing`, `blog`, `crm`,
`forms`, `listings`, `notifications`, `orgs`, `social`, `storage`). `teams` is a README only.
Sections 14 and 32–41 also cover the code outside the modules that names them (core, CLI, generator
templates, the React theme, `scripts/`).

## 1. Settings: names

`django_setting` of every manifest option. "Prefix" is the naming family.

| Module | Prefix | Settings |
|---|---|---|
| analytics | `QUICKSCALE_ANALYTICS_` | `ENABLED`, `PROVIDER`, `POSTHOG_API_KEY_ENV_VAR`, `POSTHOG_HOST`, `POSTHOG_HOST_ENV_VAR`, `EXCLUDE_DEBUG`, `EXCLUDE_STAFF`, `ANONYMOUS_BY_DEFAULT` |
| backups | `QUICKSCALE_BACKUPS_` | `RETENTION_DAYS`, `NAMING_PREFIX`, `TARGET_MODE`, `LOCAL_DIRECTORY`, `REMOTE_BUCKET_NAME`, `REMOTE_PREFIX`, `REMOTE_ENDPOINT_URL`, `REMOTE_REGION_NAME`, `REMOTE_ACCESS_KEY_ID_ENV_VAR`, `REMOTE_SECRET_ACCESS_KEY_ENV_VAR`, `AUTOMATION_ENABLED`, `SCHEDULE` |
| billing | `QUICKSCALE_BILLING_` | `ENABLED`, `PUBLISHABLE_KEY_ENV_VAR`, `SECRET_KEY_ENV_VAR`, `WEBHOOK_SECRET_ENV_VAR`, `CURRENCY` |
| notifications | `QUICKSCALE_NOTIFICATIONS_` | `ENABLED`, `SENDER_NAME`, `SENDER_EMAIL`, `REPLY_TO_EMAIL`, `RESEND_DOMAIN`, `RESEND_API_KEY_ENV_VAR`, `WEBHOOK_SECRET_ENV_VAR`, `DEFAULT_TAGS`, `ALLOWED_TAGS`, `WEBHOOK_TTL_SECONDS` |
| social | `QUICKSCALE_SOCIAL_` | `LINK_TREE_ENABLED`, `LAYOUT_VARIANT`, `EMBEDS_ENABLED`, `PROVIDER_ALLOWLIST`, `CACHE_TTL_SECONDS`, `LINKS_PER_PAGE`, `EMBEDS_PER_PAGE` |
| storage | `QUICKSCALE_STORAGE_` + third-party | `BACKEND`, `PUBLIC_BASE_URL`, `ACCESS_KEY_ID_ENV_VAR`, `SECRET_ACCESS_KEY_ENV_VAR`; Django `MEDIA_URL`; django-storages `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL`, `AWS_S3_REGION_NAME`, `AWS_DEFAULT_ACL`, `AWS_QUERYSTRING_AUTH` |
| blog | `BLOG_` (bare) | `POSTS_PER_PAGE`, `API_RATE_LIMIT`, `ENABLE_RSS` |
| crm | `CRM_` (bare) | `ENABLE_API`, `DEALS_PER_PAGE`, `CONTACTS_PER_PAGE` |
| forms | `FORMS_` (bare) | `PER_PAGE`, `SPAM_PROTECTION`, `RATE_LIMIT`, `DATA_RETENTION_DAYS`, `SUBMISSIONS_API` |
| listings | `LISTINGS_` (bare) | `PER_PAGE` |
| auth | third-party / Django | allauth `ACCOUNT_ALLOW_REGISTRATION`, `ACCOUNT_EMAIL_VERIFICATION`; Django `SESSION_COOKIE_AGE` |
| orgs | none | `QUICKSCALE_MODE` |

**Drift**
- Two first-party families: `QUICKSCALE_<MODULE>_*` (six modules) and bare `<MODULE>_*` (blog, crm,
  forms, listings). `orgs` uses a module-less `QUICKSCALE_MODE`.
- Third-party names are used directly where a library owns them (allauth, django-storages, Django).
  That is legitimate, but it is not declared anywhere as the exception.

## 2. Settings: option keys and suffixes

Same concept, different spellings (option key → setting):

| Concept | Spellings |
|---|---|
| Module on/off | `enabled` → `*_ENABLED` (analytics, billing, notifications); absent in the other nine |
| Feature on/off | `link_tree_enabled`, `embeds_enabled`, `automation_enabled`, `spam_protection_enabled` → `*_SPAM_PROTECTION` (suffix dropped), `submissions_api_enabled` → `*_SUBMISSIONS_API` (suffix dropped), `enable_api` → `CRM_ENABLE_API`, `enable_rss` → `BLOG_ENABLE_RSS` |
| Page size | `posts_per_page`, `deals_per_page`, `contacts_per_page`, `links_per_page`, `embeds_per_page`; `forms_per_page` → `FORMS_PER_PAGE` and `listings_per_page` → `LISTINGS_PER_PAGE` repeat the module name in the key |
| Rate limit | `api_rate_limit` (blog), `rate_limit` (forms); both `"5/hour"` strings, parsed separately |
| Retention | `retention_days` (backups), `data_retention_days` (forms) |
| Secret by env-var name | `*_env_var` → `*_ENV_VAR` everywhere (consistent) |
| Redundant module prefix in key | `billing_currency`, `forms_per_page`, `listings_per_page` |

**Drift**
- Boolean flags use three shapes: `<x>_enabled`, `enable_<x>`, and a suffix-less setting name.
- The option key does not reliably predict the setting name (`spam_protection_enabled` →
  `FORMS_SPAM_PROTECTION`).
- Only three modules can be switched off by a setting.

## 3. Settings: read versus declared

Settings a module's code reads (`settings.X` / `getattr(settings, "X")`) compared with its manifest.

| Finding | Where |
|---|---|
| Read but **not declared** in the manifest | blog: `BLOG_API_TOKENS`, `BLOG_API_UPLOAD_MAX_BYTES`, `BLOG_API_ALLOWED_IMAGE_FORMATS`; notifications: `QUICKSCALE_NOTIFICATIONS_PROVIDER` |
| Declared but **read outside the module** | backups: all twelve settings are read by `quickscale_core/dr_engine/orchestration.py` (≈ line 2236), not by the module, which also references two undeclared names, `QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID` and `QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY` |
| Another module's setting read directly | forms reads `QUICKSCALE_ANALYTICS_ENABLED` and `QUICKSCALE_NOTIFICATIONS_ENABLED`; orgs reads `QUICKSCALE_NOTIFICATIONS_ENABLED`; blog reads `QUICKSCALE_STORAGE_PUBLIC_BASE_URL` |
| Default duplicated in code | every `getattr(settings, "X", default)` repeats the manifest default (e.g. `DEFAULT_LISTINGS_PER_PAGE = 12`) |
| Environment read directly | orgs: `QUICKSCALE_ALLOW_BYPASSRLS`, `QUICKSCALE_PRIVILEGED_COMMAND` (runtime-role contract) |
| Declared but **absent from the module's test settings** (sixth pass) | 18 settings in 5 modules: storage 9 of 10, billing 4 of 5, blog 2 of 3 (`BLOG_POSTS_PER_PAGE`, `BLOG_API_RATE_LIMIT`), forms 2 of 5 (`FORMS_PER_PAGE`, `FORMS_DATA_RETENTION_DAYS`), auth 1 of 3 (`SESSION_COOKIE_AGE`). Those tests pass only because the code defaults exist, so removing the defaults (rule 3) breaks them until the stubs define every setting, as rule 3 already requires |

Per-module settings readers, each written independently:

| Module | Reader |
|---|---|
| analytics | `services.get_analytics_runtime_settings()` → snapshot dataclass |
| social | `contracts.get_social_runtime_settings()` + `_coerce_bool_setting`, `_coerce_positive_int_setting` |
| notifications | `services.load_settings_snapshot()`, `_require_notification_runtime_setting()`, plus a DB-backed `NotificationSettings` model |
| backups | `services.load_policy_snapshot()` from a DB-backed `BackupPolicy` model |
| blog | `views._get_positive_int_setting(name, default)` |
| listings | `views._get_positive_int_setting(name)` (raises `ImproperlyConfigured`) |
| storage | `helpers._read_setting(settings_obj, key, default)` |
| billing, crm, forms | inline `getattr` at the call site |

**Drift**
- Eight reader shapes for the same job; two are the same function copied between blog and listings
  with different signatures and failure behavior.
- Settings live in three places: Django settings only, settings plus a DB policy row (backups,
  notifications), and core code reading module settings (backups via `dr_engine`).

## 4. Environment variables (secrets)

Default env-var names that the `*_ENV_VAR` settings point to:

| Module | Secret defaults |
|---|---|
| analytics | `POSTHOG_API_KEY`, `POSTHOG_HOST` |
| billing | `STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`, `QUICKSCALE_BILLING_WEBHOOK_SECRET` |
| notifications | `RESEND_API_KEY`, `QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET` |
| storage | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| backups | `''` for both keys (no default name) |

**Drift**
- Vendor credentials use the vendor's name (`STRIPE_*`, `RESEND_*`, `AWS_*`, `POSTHOG_*`), while
  QuickScale-generated secrets use `QUICKSCALE_<MODULE>_*` — a sensible rule, but unwritten.
- backups has no default names at all, and would share `AWS_*` with storage if set the same way.
- `POSTHOG_HOST` is configuration, not a secret, yet is routed through the secret mechanism
  alongside a plain `QUICKSCALE_ANALYTICS_POSTHOG_HOST` setting.

## 5. Dependencies between modules

Imports of another module's package from module source (`top` = module level, `lazy` = inside a
function). Manifest `required_modules`/`implies` are separate and not compared here.

| Module | Imports |
|---|---|
| orgs | **auth** (`adapters.py`, top), **social** (`apps.py`, lazy, guarded by `is_installed`) |
| auth | **orgs** (`views.py`, top and lazy), **billing** (`views.py`, lazy) |
| billing, blog, crm, listings, social | orgs (models, admin, migrations, services) |
| forms | orgs (top and lazy), **analytics** (`views.py`, lazy) |
| blog | orgs, and **storage** (`models.py`, `views.py`: `import_module("quickscale_modules_storage.helpers")`, undeclared in `required_modules`) |
| orgs, by name without importing (sixth pass) | **billing** (`permissions.require_org_feature` loads `Subscription` and reads `plan.features`; `purge_organization` calls billing's `AppConfig` and model; `removal.BOUNDARY_GUARDED_OBLIGATIONS`), **blog**, **crm** (purge label prefixes), **auth** (`checks.py`), and nine modules' tables in `tenancy.TENANT_TABLE_REGISTRY` — see section 36 |
| analytics, backups, notifications, storage | none |

(Correction: the first write-up missed blog → storage, an `import_module` call that the import
search did not match, and every reference orgs makes by app label rather than by import.)

**Drift**
- A cycle: `auth → orgs → auth`. `orgs` is the tenancy foundation most modules build on, yet it
  imports two leaf modules (`auth`, `social`).
- `auth` reaches into `billing`; `forms` reaches into `analytics`. Cross-module feature coupling has
  no declared mechanism (service call, signal, or registry), so each pair invents one.
- `quickscale_core` (the `dr_engine`) reads `backups` settings: a core-to-module dependency.
- No document states the allowed dependency direction.

## 6. Package layout and Django identity

| Aspect | Observed |
|---|---|
| Package | `quickscale_modules_<name>` — consistent |
| `AppConfig` | `Quickscale<Name>Config`, label `quickscale_modules_<name>` — consistent |
| `adapter.py` | present in all twelve (apply-time hooks) — consistent name, varied content |
| `adapters.py` | auth and orgs also have one (django-allauth adapter classes) — name collides with `adapter.py` |
| URL namespace (`app_name`) | `quickscale_<name>` for analytics, auth, billing, blog, crm, forms, listings, notifications; **orgs has `urls.py` with no `app_name`**; backups, social, storage ship no `urls.py` |
| Template root | `templates/quickscale_modules_<name>/` for most; auth also overrides allauth's `account/`; backups uses `admin/`; social and storage ship none |
| Management commands | prefixed in backups (`backups_*`, but also `dr_adapter_call`) and forms (`forms_*`); unprefixed in orgs (`check_tenant_isolation`, `migrate_billing_to_orgs`, `promote_to_saas`, `purge_organization`); crm has a `management/` package with no commands |
| Extra modules | `services.py` in analytics, backups, billing, crm, notifications, social; `contracts.py` only in social; `helpers.py` only in storage; `constants.py` only in orgs |

**Drift**
- URL namespace (`quickscale_<name>`) and app label (`quickscale_modules_<name>`) follow two
  different stems, and orgs has none.
- Management-command names are not namespaced consistently, so project commands can collide.
- The public API of a module has no fixed home: `services.py`, `contracts.py`, `helpers.py`, or
  direct model imports, depending on the module.

## 7. Manifest shape

Top-level keys beyond `name`, `version`, `description`, `config`, `derivation`:

| Key | Modules |
|---|---|
| `dependencies` | all except social |
| `required_modules` | auth, billing, blog, crm, listings, orgs, social |
| `implies` | auth, billing, crm, listings, orgs, social |
| `contract_vintage` | backups, billing, orgs, social |
| `settings`, `middleware` | orgs only |
| `managed_files` | social only |

**Drift**
- forms, blog, and listings depend on orgs in code (section 5); blog and listings declare
  `required_modules`, forms does not.
- Immutable options exist only in auth (`authentication_method`) and storage
  (`private_media_enabled`), and neither maps to a setting — as decisions.md § Module Manifest
  Architecture requires (immutable options must not have `django_setting`), so this is not drift.

## 8. Extension surfaces

Declared in [module-extension.md](../technical/module-extension.md) per module; not re-inventoried
here. No test compares a module's declared surfaces with what its code exposes (signals, swappable
models, abstract bases, template blocks, service hooks).

## 9. URLs

Where each module's URL prefix is set, and how its routes are named.

| Module | Prefix set in | Mounted at | API paths | Route-name style |
|---|---|---|---|---|
| analytics | manifest `url_includes` | `analytics/` (prefix in the manifest; `urls.py` has none) | — | kebab, module-prefixed (`analytics-dashboard`) |
| auth | `adapter.py` | `accounts/` | — | kebab (`profile-edit`) |
| billing | manifest | `""`, prefix inside `urls.py` | `api/billing/…`, webhook `billing/webhooks/stripe/` | kebab, some module-prefixed (`billing-dashboard`) |
| blog | manifest | `""`, prefix inside `urls.py` | `blog/api/…` | snake (`post_list`, `api_publish_post`) |
| crm | manifest | `""`, prefix inside `urls.py` | `crm/api/…` (DRF router) | router defaults + kebab |
| forms | manifest | `""`, prefix inside `urls.py` | `api/forms/…` | kebab (`form-list`) |
| listings | manifest | `listings/` (prefix in the manifest) | `listings/api/publish/` | snake (`listing_list`) |
| notifications | `adapter.py` | `""`, prefix inside `urls.py` | webhook `notifications/webhooks/resend/` | kebab |
| orgs | `adapter.py` | `""`, mixed: `""`, `orgs/`, `api/orgs/` | `api/orgs/…` | kebab, module-prefixed (`org-home`); **no `app_name`** |

**Drift**
- The prefix lives in three places: inside `urls.py`, in the manifest's `url_includes`, or in
  `adapter.py`. A project cannot move a module (say `blog/` → `news/`) without editing module code.
- API paths come in two shapes, `api/<module>/…` and `<module>/api/…`.
- Route names mix snake and kebab case, and several repeat the module name the namespace already
  carries (`quickscale_orgs:org-home`).

## 10. Templates and static files

| Module | Module base template | Pages extend | Own `<html>` | Static root |
|---|---|---|---|---|
| auth | `quickscale_modules_auth/base.html` | module base | no | `quickscale_modules_auth/{css,js}/` |
| billing | `quickscale_modules_billing/base.html` | module base | no | `quickscale_modules_billing/css/` |
| blog | `quickscale_modules_blog/blog/base.html` (nested) | module base | no | `quickscale_modules_blog/blog.css` (flat) |
| crm | `quickscale_modules_crm/crm/base.html` (nested) | module base | no | `quickscale_modules_crm/crm.css` (flat) |
| listings | `quickscale_modules_listings/listings/base.html` (nested) | module base | no | flat |
| analytics | none | project `base.html`, fills `content` | no | none |
| forms | none (templates nested under `forms/`) | project `base.html`, fills `content` | no | none |
| orgs | none | nothing | **yes** — every page is a full document | none |
| notifications | `…/notifications/base_email.html` (email only) | email base | email | none |

Template-tag libraries: `analytics_tags` (analytics), `quickscale_orgs_debug` (orgs). Library names
share one global namespace across all installed apps.

**Drift**
- orgs pages emit their own `<html>` document, and analytics and forms fill the project's
  `content` block directly: both break the recorded rule that module templates extend `base.html`
  through a module base owning `{% block content %}` ([decisions.md § Module Implementation
  Requirements](../technical/decisions.md#module-implementation-checklist)).
- The module base sits at two depths (`<root>/base.html` and `<root>/<module>/base.html`).
- Static folders use the old stem and two layouts (`css/`, `js/` subfolders or one flat file).
- Template-tag library names follow no stem, so a project library can shadow one.

## 11. HTTP APIs

| Aspect | Observed |
|---|---|
| Framework | DRF in billing, crm, forms; plain `JsonResponse` in blog, listings, notifications, and orgs (`OrgApiBaseView` subclasses Django's `View`), and in billing's webhook and JSON-parsing helper. (Correction, sixth pass: the first write-up counted orgs as DRF; decisions.md § JSON API Endpoint Base Contract lists DRF users as billing, CRM, and forms) |
| Authentication | DRF `SessionAuthentication` (11 views); blog also accepts bearer tokens from undeclared `BLOG_API_TOKENS`; listings' publish API is session-only |
| Error body | `{"error": …}` (72 keys) and `{"errors": …}` (18 keys) side by side in module `src/`; DRF's own errors use `{"detail": …}`. (Correction, sixth pass: the first write-up gave 84 and 28 with no stated basis; with tests included the counts are 91 and 24) |
| Pagination | DRF `PageNumberPagination` subclasses in billing and crm; hand-written slicing elsewhere |
| Rate limiting | blog parses `"5/hour"` itself with a hard-coded fallback; forms uses a DRF throttle class |

**Drift**
- Two frameworks for the same job, so every API differs in auth, errors, and paging.
- A client cannot handle QuickScale errors with one shape.
- blog and listings each have a "publish" API doing the same thing with different auth.

## 12. Startup checks, errors, and logging

| Aspect | Observed |
|---|---|
| Startup validation | hand-written `hasattr(settings, X)` + `ImproperlyConfigured` in `ready()` (analytics, auth, billing, blog, crm, forms); a service function (notifications); Django system checks in `checks.py` (orgs only); nothing (listings, social, storage) |
| Failure swallowed | analytics' `ready()` logs a warning and continues when its client fails to start |
| Exception classes | a `<Module>Error` base in `services.py` (billing, notifications); loose `Exception` subclasses in `views.py` (blog, listings); `contracts.py` (social); `current_org.py` (orgs); none elsewhere |
| Loggers | `logging.getLogger(__name__)` everywhere — consistent |
| Core registration by module name | backups calls `quickscale_core.runtime.register_backup_persistence` — core exposes a backups-specific seam |

**Drift**
- Four ways to validate at startup; rule 3's generic check replaces the hand-written ones, but
  module-specific checks (orgs' RLS role, blog's `MEDIA_URL`) have no home.
- Swallowing a startup failure contradicts the Fail-Hard Principle.
- Callers cannot catch "anything this module raises", and view modules define domain errors.

## 13. Package files, tests, and README

| Aspect | Observed |
|---|---|
| `services.py` | 6 of 12; none defines `is_enabled()`, which rule 4 now requires of callers |
| Name clashes | `adapter.py` (apply hook) beside `adapters.py` (allauth) in auth and orgs |
| One-off files | `contracts.py` (social), `helpers.py` (storage), `constants.py` (orgs), `notifications.py` (forms), `debug_helpers.py`/`debug_views.py` (orgs) |
| Empty packages | crm ships `management/commands/` with no command; listings' `ready()` is `pass` |
| Non-stem command | backups' `dr_adapter_call` |
| `poetry.toml` | missing in analytics, notifications, storage |
| Test files | `test_apps.py` missing in auth, listings, orgs, storage; `test_migrations.py` only in backups, billing, crm, forms; tenant modules: `test_isolation.py` missing in billing and orgs, `test_rls_boundary.py` missing in social and orgs |
| README headings | twelve different outlines; three headings carry stale versions (`v0.76.0`, `v0.79.0`, `v0.80.0`) against lockstep `0.89.0`; notifications' README has no sections, orgs' has one |
| Model choices | Django `TextChoices` in billing, blog, orgs; tuple `*_CHOICES` constants in backups, blog, crm, forms, listings, notifications |

**Drift**
- A module's public entry point and its "is it on?" answer have no fixed home.
- What a module must test is decided module by module, so tenant isolation is proven unevenly.
- READMEs do not tell an operator the same things in the same place, and some are stale.

## 14. Manifest option schema

Every option's entry in `config.mutable` / `config.immutable`.

| Aspect | Observed |
|---|---|
| `immutable:` block | present (often `{}`) in auth, blog, crm, forms, orgs, storage; absent in analytics, backups, billing, listings, notifications, social |
| Per-option `validation:` block | 5 options in 4 modules (auth, backups, orgs, storage), all `choices`. Loaded into `ConfigOption.validation` and **read by nothing** in core or the CLI |
| `derivation.validation_rules` list (`ValidationRule`, enforced by the manifest resolver) | listings only: `listings_per_page` matches `^\d+$`, which accepts `0` although its message says "positive integer" |
| Per-module option code in core and the CLI | `quickscale_core.contracts.resolvers` has `validate_/resolve_/normalize_/default_<module>_module_options` for nine modules plus 8 `DEFAULT_*` constants; `contracts.module_options` repeats five of the validators plus 19 `DEFAULT_*` constants; `schema.config_schema` has auth's and billing's; the CLI's `module_config` has backups'. `LEGACY_AUTH_ALLOW_REGISTRATION_OPTION`, `LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION`, and `LEGACY_CRM_DEFAULT_PIPELINE_STAGES_OPTION` are legacy option names. `contracts.imperative_inventory` catalogs them for the migration that decisions.md § Module Derivation Schema records as "separate work" (Track 2 phases T2.3–T2.5), which no current ticket carries |
| Setting projection | every mutable option names its setting in `config` (`django_setting`); in analytics, billing, blog, crm, forms, and listings every one of them is named again in `derivation.option_derivations.<option>.derived_settings` (25 options, all direct 1:1), and blog, crm, forms, and listings repeat 10 of the defaults there |
| Missing checks | no manifest check on any `*_per_page`, `*_rate_limit`, `*_retention_days`, `*_ttl_seconds`, or enum-like string (`analytics.provider`, `social.layout_variant`); some exist only in the core code above |
| `description:` | every option except one in storage |
| Top-level key order | eight different orders (`implies` before or after `dependencies`, `contract_vintage` in three positions) |
| `dependencies:` | missing in social only |

**Drift**
- Option checks live in four places (an unread manifest block, a manifest list one module uses,
  core, the CLI), and core and the CLI name modules — against
  [decisions.md § Module Wiring Authority](../technical/decisions.md#module-wiring-authority) and rule 3's
  "the manifest default is the only default". Rule 3's startup check reads the manifest, so it would
  miss every check that lives in code, and `0` passes listings' only manifest rule.
- Inside the manifest, a setting's name and default are written twice in six modules, against
  rule 3's "the manifest default is the only default".
- Legacy option names survive in core, against rule 6. The first and second passes missed all of
  this because they inventoried `quickscale_modules/` only.
- Two ways to say "no immutable options", and no fixed key order to diff manifests by eye.

## 15. Tenant models

How a model becomes organization-scoped.

| Pattern | Modules |
|---|---|
| subclass orgs' `TenantModel` (field + both managers inherited) | blog, crm |
| `models.Model` + `tenant_org_fk(...)` + hand-declared `objects`/`all_objects = TenantManager(...)` | billing (4), forms (4), listings, social |
| `models.Model` + `OneToOneField(Organization)` + hand-declared managers | billing `CreditBalance` (one row per org) |

Every tenant model does end up with `Meta.base_manager_name = "all_objects"`, in three ways:
inherited through `class Meta(TenantModel.Meta)` (crm), inherited through a module's own abstract
base's `Meta` (social's `BaseSocialItem`, listings' `AbstractListing` for `Listing`), or typed
again in a `Meta` that does not inherit (blog, billing, forms). orgs detects tenant models by
either marker, `TenantModel` inheritance or a `TenantManager` as `objects`
(`tenancy.is_tenant_model`), and module-extension.md documents the manager form as the supported
way for a project to add a tenant model. blog subclasses `TenantModel` and still overrides
`organization` with `tenant_org_fk(related_name=…)` to keep its reverse names.
Admin: every tenant model is registered on `TenantModelAdmin`; every non-tenant model on
`admin.ModelAdmin`; all through `@admin.register` — consistent.

**Drift**
- Three spellings of "this model belongs to an organization". Nothing is missing today, but in
  the retyped-`Meta` and hand-built cases each model repeats the contract, so a change to it must
  be made in every copy, and a new model that forgets one piece is not caught.
  (Correction: the first write-up of this pass said the hand-built models lack
  `base_manager_name`; they do not.)

## 16. Models: fields, relations, meta

| Aspect | Observed |
|---|---|
| Timestamps | `created_at` / `updated_at` everywhere (21 / 14), events as `<event>_at` (`submitted_at`, `joined_at`, `purged_at`) — consistent |
| Primary keys | `BigAutoField` in every module; orgs uses `UUIDField` for `Organization`, `OrganizationTombstone`, and the invitation token |
| User references | `settings.AUTH_USER_MODEL` everywhere — consistent |
| `related_name` on relations to `User` | three styles: module-prefixed (`blog_posts`, `billing_subscriptions`, `quickscale_backup_artifacts`), unprefixed (`author_profile`, `credit_balance`, `credit_transactions`, `owned_deals`, `created_forms`, `organization_memberships`), and missing (crm's `created_by` on `ContactNote` and `DealNote`, so `User` gets `contactnote_set` and `dealnote_set`) |
| `related_name` on `organization` | `TenantModel`'s `%(app_label)s_%(class)s_set` (crm, social), hand-picked (`blog_posts`, `forms`, `subscriptions`, `%(class)s_listings`); no code reads any of them as an attribute |
| `__str__`, `Meta.ordering` | present on every concrete model (listings and social inherit them from their abstract bases), except ordering on `FormFieldValue`; absent by design on singletons and one-per-parent models (`BackupPolicy`, `NotificationSettings`, `CreditBalance`) |
| Choice lists | 15 literal tuple lists: the second pass's 14 plus social's `SOCIAL_EMBED_RESOLUTION_CHOICES` (in `contracts.py`). orgs' `INVITABLE_ORG_ROLE_CHOICES` (a subset of `OrgRole`) and social's `SOCIAL_PROVIDER_CHOICES` (from its provider catalog) are derived, not literals |
| Translation | no module calls `gettext`; `verbose_name` appears 30 times across 8 modules with no pattern — no i18n anywhere |

**Drift**
- Reverse accessors on `User` and `Organization` are a namespace every installed module shares;
  without a module prefix two modules collide (`notes`, `deals`, `tags` are generic).
- A model without ordering pages non-deterministically; `FormFieldValue` is the one case.
  (Correction: the first write-up of this pass listed `Listing`, `SocialLink`, and `SocialEmbed`
  as missing `__str__` and ordering; they inherit both.)

## 17. Package `__init__.py`

| Module | Content |
|---|---|
| analytics, backups, billing, notifications, orgs, social | `__version__` and `__all__ = ["__version__"]` |
| auth, blog, crm, listings | `__version__` and `default_app_config` (removed in Django 4.1; dead) |
| forms | `__version__` only |
| storage | `__version__`, a lazy `__getattr__` re-export, and a computed `__all__` |

**Drift**
- A dead Django setting in four modules, and storage is the only package importable as a public API
  from its root.

## 18. Signals and receivers

| Module | Defines signals | Receivers live in | Connected by |
|---|---|---|---|
| orgs | `signals.py` (`organization_created`, …) | `signals.py` and `apps.py` | `ready()` calls `.connect()` |
| auth | — | `signals.py` (`@receiver(user_signed_up)`) | `ready()` imports `signals` |
| crm | — | `signals.py` (`@receiver(organization_created)`) | `ready()` imports `signals` |

**Drift**
- `signals.py` means "signals I send" in orgs and "things I listen to" in auth and crm. Rule 4
  makes a sender's `signals.py` part of its public surface, so a module importing `crm.signals`
  would get receivers, not signals.

## 19. Management commands: behavior

Names are section 6. Behavior:

| Command | Changes data | `--dry-run` | Failure handling |
|---|---|---|---|
| `purge_organization`, `backups_sync_media`, `backups_restore` | deletes or overwrites | yes | `CommandError` |
| `backups_prune`, `forms_anonymize_submissions` | deletes or anonymizes | **no** | prune `CommandError`; anonymize has no expected failure path |
| `promote_to_saas` | rewrites personal-org slugs | **no** | no expected failure path |
| `migrate_billing_to_orgs` (retired recovery command) | writes | **no** | `CommandError` |
| `check_tenant_isolation` | read-only | — | **`sys.exit()`** instead of `CommandError` |
| `forms_seed_presets` | creates missing presets only | — | no expected failure path |
| all other backups commands | — | — | `CommandError` |

Every command writes through `self.stdout`; none calls `print()`. An unexpected exception still exits
non-zero.

**Drift**
- Four of seven data-changing commands cannot be previewed, including a retired one the RLS
  section still names as a recovery path.
- One command exits with `sys.exit()`, bypassing Django's error handling and `call_command()`.
  (Correction: the first write-up said three commands exit 0 on failure; they have no expected
  failure path, and an unexpected one exits non-zero.)

## 20. Package tooling

| Aspect | Observed |
|---|---|
| Build backend, pytest config, `--cov-fail-under=90`, ruff sections | same in all twelve — consistent |
| `[tool.mypy]` | present only in blog, listings, and storage, and read by nothing: `make typecheck` runs mypy from the repository root, which uses the root `mypy.ini`. Its per-module sections range from no relaxation (backups has none) to twelve disabled error codes (orgs); see section 38. (Correction: the first write-up said the section was missing only in orgs and social, and that those two were not type-checked. All twelve are type-checked through the root file, with very different strictness) |
| Test settings | `tests/settings.py` in all; billing adds `settings_auth_parity.py` |
| `teams/` | README-only placeholder in `quickscale_modules/`; nothing says a checker must skip it |

**Drift**
- ~~orgs, the most security-sensitive module, and social are not type-checked with the others.~~
  Superseded by section 38: orgs is type-checked, but with twelve error codes turned off.
- Any whole-module check has to special-case `teams/` without a recorded reason.

## 21. Authorization: who may manage a module's data

Fourth pass. How a view decides that the requesting user may create, edit, or read back-office data.

| Module | Check used for management views and APIs |
|---|---|
| orgs | its own org roles: `require_org_role`, `OrgRoleMixin`, `OrgApiBaseView`; `is_superuser` for operator paths |
| billing | orgs' `user_has_org_role` (imported lazily in `views.py`) |
| blog | `is_staff` (dashboard, `publish_post_api`, `upload_media_api`) |
| listings | `is_staff` (JSON API) |
| crm | `is_staff` in `dispatch()` (dashboard), DRF `IsAdminUser` (API) |
| forms | DRF `IsAdminUser`, plus `is_superuser` to see every organization's forms |
| analytics | `is_staff` / `is_superuser` only to exclude staff traffic (`EXCLUDE_STAFF`), not to authorize |

"Logged in" is spelled three ways: `LoginRequiredMixin` / `login_required` (auth, billing, orgs),
and a hand-written `redirect_to_login` in `dispatch()` (crm).

**Drift**
- blog, listings, crm, and forms are tenant modules (rule 13), yet they authorize with Django's
  `is_staff`, a flag that is global to the site, not to an organization. In `saas` mode a staff
  user of one organization passes the check for data of every organization they can select; only
  RLS and `TenantManager` scoping stand between them and it. The org role that orgs and billing
  use is never consulted.
- A project cannot give an organization's own admin (org role `admin`) access to its blog or CRM
  without also making that person platform staff.
- Four spellings of the same two questions ("logged in?", "allowed?"), none in the public surface.

## 22. Outbound email

| Module | How it sends |
|---|---|
| notifications | `EmailMultiAlternatives` inside `send_notification`, tracked (`NotificationDelivery`), after commit |
| orgs | invitation email through `notifications.services` (orgs implies notifications) |
| forms | `notifications.services.send_notification` when notifications is installed and on; otherwise its own untracked `EmailMultiAlternatives` path (`forms/notifications.py`), chosen by reading `QUICKSCALE_NOTIFICATIONS_ENABLED` with `getattr(..., True)` |
| auth | django-allauth's own mail (verification, reset), through `EMAIL_BACKEND` |

**Drift**
- forms carries a second email sender so that it works without notifications, reads another
  module's setting with a code default (rules 3 and 4 forbid both), and imports notifications by
  name with `import_module` instead of declaring it. The two paths differ in tracking, retries, and
  templates.
- `forms/notifications.py` is a one-off file named after another module (rule 11).

## 23. Side effects of a write

External effects a write triggers — an email, an analytics event, a vendor API call.

| Where | When the effect runs |
|---|---|
| notifications `send_notification` | `transaction.on_commit(...)` |
| forms submission | after its own `with transaction.atomic()` block, in the view |
| orgs invitation, crm bootstrap receiver, social cache purge (`models.py` `save`) | inline, wherever the caller is |
| billing checkout | Stripe call before the write — not an effect of it |

orgs' middleware holds no request-long transaction, so today the forms ordering is correct; it
stops being correct as soon as a caller wraps the view or service in `atomic()` (tests, `operator_access`
paths, a project's own view).

**Drift**
- Only one module makes "effect only if the write commits" a property of the code rather than of
  the caller. An email or analytics event for a row that was rolled back is a real, silent defect.

## 24. Analytics events

| Aspect | Observed |
|---|---|
| Vocabulary | `analytics/events.py`: `$pageview`, `form_submit`, `social_link_click` |
| Helpers | analytics' `services.py` has `capture_event` plus `capture_form_submit` and `capture_social_link_click`, each shaping another module's payload |
| Callers | forms calls `capture_form_submit`; nothing calls `capture_social_link_click` (social never emits it) |

**Drift**
- analytics (layer 2) knows the events of forms and social (layer 3), one of them dead: every new
  feature event is an edit to analytics, the same inversion rule 5 removes for imports. Event names have no rule, so the
  next module picks its own shape.

## 25. Public service surface

| Aspect | Observed |
|---|---|
| `__all__` in `services.py` | analytics, billing, social; not backups, crm, notifications |
| Keyword-only parameters | 23 of 51 public service functions declare keyword-only parameters (billing 14, notifications 7, backups 2). Measured against rule 23 (at most one positional subject), 10 of 51 take two or more positional parameters: analytics 4 (`capture_event(distinct_id, event, properties)` among them), billing 5, backups 1. (Correction, sixth pass: the first write-up said 8 of 51 took keyword-only parameters and the rest were positional) |
| Return and error shape | booleans, `None`, dicts, and model instances; failures are raised in billing and notifications and swallowed-and-logged in analytics |

**Drift**
- Rule 4 makes `services.py` the public surface but nothing lists what is in it, so the conformance
  test cannot tell a public function from a helper that happens to lack an underscore.
- Positional calls across modules break silently when a parameter is added or reordered; ten
  functions in three modules invite them.

## 26. Small leftovers

| Aspect | Observed |
|---|---|
| `py.typed` | present and tracked in all twelve since `6ea37301` (2026-07-09). (Correction: the first write-up said backups and blog lack it; they do not) |
| Current time | `django.utils.timezone.now()` in 16 files; storage's `helpers.py` uses `datetime.now(tz=timezone.utc)` |
| Cache keys | only social caches, with keys `quickscale_modules_social:*` — the old package stem, not rule 2's `quickscale_social` |
| Data migrations | every `RunPython` in `0001_initial` has a `reverse_code` (`noop`) — consistent |
| Loggers | no log call formats an email address or username — consistent |

**Drift**
- ~~backups' and blog's type hints are invisible to a project's mypy.~~ Not drift (see the
  correction above).
- The cache key is a name a project and a shared Redis see, so it belongs in rule 2's identity table.

## 27. Constraint and index names

Fifth pass. The `name=` of every `UniqueConstraint`, `CheckConstraint`, and `Index`. In PostgreSQL a
unique constraint or index name must be unique across the whole schema, so a name is a label every
installed module and the project share, like a table name.

| Style | Examples | Modules |
|---|---|---|
| `quickscale_<module>_…` (rule 2's stem) | `quickscale_billing_unique_stripe_event_id`, `quickscale_notifications_unique_message_recipient` | billing (5), notifications (1) |
| `<module>_<model>_…` (no stem) | `blog_post_slug_organization_unique`, `crm_contact_id_org_unique`, `forms_form_id_org_unique` | blog (5), crm (6), forms (3), listings (1) |
| old package stem | `quickscale_modules_forms_form_slug_organization_unique` | forms (1) |
| no prefix at all | `unique_system_org`, `unique_nonempty_org_stripe_customer` | orgs (2) |
| Django's generated index name (`quickscale__<field>_<hash>_idx`) | unnamed `Index(...)` in blog `Post` and listings' `AbstractListing`; listings' concrete `Listing` copies the generated names into its `Meta` | blog (3), listings (3) |
| `unique_together` instead of a named constraint | `FormField` (`form`, `name`), `OrganizationMembership` (`user`, `organization`) | forms, orgs |

**Drift**
- Five naming styles and two unnamed forms. orgs' prefix-less names are the ones most likely to
  collide with a project's own constraint. Generated index names depend on the app label, so
  rule 2's rename changes them anyway, and a hashed, truncated name tells an operator reading a
  migration or an error nothing.
- `unique_together` is the form Django's docs say may be deprecated; the other 24 unique rules
  are `UniqueConstraint`.

## 28. Inbound webhooks

| Aspect | billing (`StripeWebhookView`) | notifications (`NotificationWebhookView`) |
|---|---|---|
| View base | Django `View`, `csrf_exempt`, POST only | same |
| Signature check | in `services.handle_stripe_event` (Stripe SDK) | in `services.ingest_webhook_event` (`hmac.compare_digest`, timestamped) |
| Replay / duplicate handling | `WebhookEvent` unique on `stripe_event_id` | `NotificationDeliveryEvent.idempotency_key` unique |
| Success body | `{"status": "accepted", "duplicate", "event_type", "processing_status"}` | `{"status": "accepted", "duplicate", "delivery_status"}` |
| Error body | `{"error": "<str(exc)>"}` | `{"error": "<str(exc)>"}` |
| Bad signature | 403 | 403 |
| Module switched off | 403 | 403 |
| Missing secret | 500 (`BillingConfigurationError`) | raised from `resolve_webhook_secret` at request time |

Where it is already the same (keep): transport-only views, verification and deduplication in
`services.py`, a unique database key per provider event, POST only.

**Drift**
- Both error bodies break rule 9's one shape, and `str(exc)` can put internal detail in a response
  to an unauthenticated caller. The rule 9 exemption covers "signature-verified webhooks" as a
  whole, so neither the shape nor the status codes are governed.
- A switched-off module answers 403, but rule 1 says off disables its URLs (404). A missing secret
  is found per request (500) instead of at startup (rules 3 and 10).
- The success bodies differ, and a provider reads only the status.

## 29. `on_delete` on relations to `User`

| Behavior | Where |
|---|---|
| `SET_NULL` — a field recording who did something (author, creator, actor, owner) | backups, billing (4), blog (2), crm (3), forms, orgs `OrganizationMembership.invited_by` |
| `CASCADE` — allowlisted | orgs `OrganizationMembership.user`, orgs `OrganizationInvitation.invited_by`, blog `AuthorProfile.user` |
| `PROTECT` | none (allowed by the gate when taken; D30 forbids it) |

All of it already conforms: SA35's gate (`orgs/tests/test_sa35_conformance.py`) allows `SET_NULL`
or `PROTECT` and allowlists the three `CASCADE` fields, because referential actions bypass RLS.

**Drift**
- The rule is written, but only inside decisions.md § Multi-tenant SaaS Architecture (the
  "Intentional CASCADE exception" bullet names "the general SET_NULL/PROTECT rule"), not in Module
  Conventions or module-extension.md, where a module author looks. The gate's comment cites
  "decisions.md §SA35", a heading that does not exist. (Correction: the first write-up of this
  pass said the rule was written nowhere.)

## 30. Module-private file names

Files in a package that rule 11's required list, rule 4's public surface, and rule 10's
`checks.py` / `exceptions.py` do not name:

| File | Modules | What it is |
|---|---|---|
| `forms.py`, `serializers.py`, `managers.py`, `filters.py`, `feeds.py`, `middleware.py`, `validators.py`, `throttles.py`, `admin.py`, `models.py`, `views.py`, `urls.py` | many | Django / DRF names — every Django developer knows where to look |
| `persistence.py` | backups | the core-port implementation (rule 10) |
| `events.py` | analytics | event vocabulary; D25 removes the feature names |
| `debug_views.py`, `debug_helpers.py` | orgs | DEBUG-only pages |
| `contracts.py`, `helpers.py`, `constants.py` | social, storage, orgs | fold in (rule 11) |
| `notifications.py` | forms | goes (D23) |

**Drift**
- Rule 11 names the files a module must have and three it must fold, but not what else a module
  may add. Nothing stops the next `utils.py`, and nothing tells the conformance test whether an
  unknown file is public.

## 31. Test file names and helpers

| Aspect | Observed |
|---|---|
| Ticket-numbered test files | orgs only: `test_sa35_conformance.py`, `test_sa41_statement_amplification.py`, `test_sa49_conformance.py`, `test_sa60_composite_fk_conformance.py`, `test_sa92_migration_squash_guardrail.py`, `test_sa213_removal_obligations.py`, `test_af9_autocommit_proof.py`, `test_af9_priming.py` |
| Non-test files in `tests/` | `conftest.py`, `settings*.py`, `urls.py` everywhere; plus billing `stripe_payloads.py`, `diag_setlocal.py`; listings `models.py`, `views.py`; orgs `bypassed_boundary.py`, `urls_pre_home.py`, `sa182_project_app/`, `sa208_project_app/`; backups `wsgi.py` |
| One-off import-cycle tests | `test_circular_import.py` in auth and billing |

**Drift**
- A ticket number says when a test was written, not what it protects; a reader of orgs' test
  folder cannot find the RLS tests by name. Helper files and test apps are named three ways.

## 32. Settings written by module wiring

Sixth pass. Besides option settings, each `adapter.py` (and orgs' `module.yml` `settings:` block)
writes settings into the one generated `settings/modules.py`. Core merges them in
`module_wiring.collect_wiring`: modules sorted by name, **last writer wins**, key by key, with no
deep merge and no warning.

| Written keys | Modules |
|---|---|
| only its own `QUICKSCALE_<MODULE>_*` / bare-family keys | analytics, backups, crm, forms, social |
| Django or third-party keys that no other module writes | auth (`AUTH_USER_MODEL`, `AUTHENTICATION_BACKENDS`, `SITE_ID`, `LOGIN_REDIRECT_URL`, `ACCOUNT_*`), notifications (`EMAIL_BACKEND`, `DEFAULT_FROM_EMAIL`, `SERVER_EMAIL`), storage (`STORAGES`, `MEDIA_URL`, `AWS_*`), blog (`MARKDOWNX_MEDIA_PATH`) |
| the same key as another module | `ACCOUNT_ADAPTER`: auth and orgs, and orgs wins only because `"orgs"` sorts after `"auth"`; `MARKDOWNX_MARKDOWN_EXTENSIONS`: blog and listings, equal values today, listings wins |
| the same URL include as another module | `markdownx/` → `markdownx.urls`: blog and listings. URL includes are merged by `_merge_unique`, so identical pairs collapse; a different pair for the same prefix would mount twice |
| a whole nested dict | `REST_FRAMEWORK`: billing (`DEFAULT_THROTTLE_RATES` for `billing_checkout`, `billing_portal`). The generated `base.py` merges its sub-keys with the template's defaults, and "module keys win on collision" |

Already the same (keep): every module writes through `ModuleWiringSpec`; ordering is deterministic.

**Drift**
- Two keys already have two writers, and which one wins depends on alphabetical order. Nothing
  says a module may not write a key another module writes.
- Rule 9 has blog and forms feed DRF throttles from their `_RATE_LIMIT` settings. The natural way to
  do that is to contribute `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]` as billing does. The first one
  to do so replaces billing's whole dict ("forms" sorts after "billing"), and billing's checkout
  and portal views then raise DRF's `ImproperlyConfigured` ("no default throttle rate set for
  'billing_checkout' scope") on every request. The defect is latent today and becomes reachable
  when rule 9 lands.

## 33. The theme's view of modules

The React theme learns which modules exist through `window.__QUICKSCALE__`
(`themes/showcase_react/templates/index.html.j2`), per the recorded Frontend Theme Source
De-Specialization seam.

| `modules.<name>` is true when | Modules |
|---|---|
| `'quickscale_modules_<name>' in settings.INSTALLED_APPS` | auth, blog, listings, crm, forms, storage, backups, notifications, analytics, billing |
| `QUICKSCALE_SOCIAL_LINK_TREE_ENABLED or QUICKSCALE_SOCIAL_EMBEDS_ENABLED` (feature settings) | social |
| no flag (mode read from `QUICKSCALE_MODE`) | orgs |

`modulePaths` hard-codes `crm: "/crm/"` and `analytics: "/analytics/"`, computes social's, and has
no entry for the others. The theme ships pages for blog, crm, forms, listings, social, and orgs.

Already the same (keep): one seam, flags only, no per-project source (recorded decision).

**Drift**
- "true" means *installed* for ten modules and *enabled* for one. Rule 1 adds
  `QUICKSCALE_<MODULE>_ENABLED`, and off means the URLs return 404. An installed but switched-off
  module keeps its flag and its navigation, which then leads to a 404 (latent until rule 1 lands).
- Mount paths are written a second time in the theme, although rule 7 makes the manifest's
  `url_includes` the only mount; D10's moves (orgs under `orgs/`) must be mirrored by hand.
- The template names ten module packages and reads social's settings: a list in core that a new
  module must join (section 39).

(Correction, 2026-10-03: this section said the theme learns its modules through `index.html.j2`.
There are **three** seam producers. `templates/social/link_tree.html.j2:54` and
`social/embeds.html.j2:54` each write their own `window.__QUICKSCALE__`. Both did so at
`58e73cc7`, so the sixth pass missed them. SA219 (`b825bb6d`) moved `index.html.j2` onto
discovery and left these two hand-written.)

**At `c10b529e`:**

| Producer | Flags | `modulePaths` | Rule 31 |
|---|---|---|---|
| `index.html.j2` | rendered from discovery by `generator/seam.py`: installed and `_ENABLED` | `{% url %}` from `_SEAM_MODULE_PATHS` | conforms; harness rule 31 checks it |
| `social/link_tree.html.j2`, `social/embeds.html.j2` | 11 hand-written lines: 10 literal `false`, social as `'quickscale_modules_social' in settings.INSTALLED_APPS and …_ENABLED` | literal `"/crm/"`, `"/analytics/"`; social through `{% if %}` with literal paths | violates each ❌ of rule 31; the harness reads only `THEME_SEAM_TEMPLATE` (`check_module_conventions.py:142`) |

- On a social page, `modules.blog` is `false` even where blog is installed and enabled. The same
  key therefore means "enabled" on one page and "not shown here" on another. *Ambiguity.*
- A new module that adds itself to the seam validator (`validateQuickScaleSeam.ts:48`, "all
  required module flags must be own boolean properties", following module-extension.md step 5)
  gets its line in `index.html.j2` automatically, but not on the two social pages. The SPA then
  throws on `/social` and `/social/embeds`. *Defect, latent until the next module with a React
  surface.* Hand-off: tech.

## 34. Throttle scopes and rates

| Module | Mechanism | Scope name | Rate from |
|---|---|---|---|
| billing | DRF `ScopedRateThrottle` | `billing_checkout`, `billing_portal` | `"30/hour"` hard-coded in `adapter.py`, not an option |
| forms | `ScopedRateThrottle` subclass (`throttles.py`) | `form_submit` | `getattr(settings, "FORMS_RATE_LIMIT", None)` |
| blog | hand-written limiter in `views.py`, own `"5/hour"` parser | — | `BLOG_API_RATE_LIMIT`, counters in a raw-SQL table `quickscale_modules_blog_api_throttle_counter` created by `RunSQL` in `0001_initial` |

The generated `base.py` defines `anon` and `user` rates and lets module rates win on a clash.

**Drift**
- Three mechanisms (section 11 already records two). Scope names are DRF cache-key and
  `DEFAULT_THROTTLE_RATES` names shared with the project, and follow two shapes
  (`billing_<action>`, `form_submit`); a module scope named like a project scope silently takes
  its rate.
- billing's rate is not configurable, against rule 9's "throttles fed by the module's
  `_RATE_LIMIT`".
- blog's counter table is named with the old stem outside the ORM, so rule 2's rename and rule 25's
  name check cannot see it, and nothing in rule 9's decision says it goes.

## 35. Which shared names carry the stem

The rules already decided choose a prefix per namespace:

| Namespace | Shared with | A clash is | Rule | Prefix |
|---|---|---|---|---|
| app label, URL namespace, template folder, command, cache key | project and modules | silent (shadowing, overwrite) or loud | 2, 24 | `quickscale_<module>` |
| constraint and index names | the whole PostgreSQL schema | loud (migration error) | 25 | `quickscale_<module>_` / `qs_<module>_` |
| reverse accessors on `User`, `Organization` | project and modules | loud (Django system check `fields.E304`) | 14 | `<module>_` |
| analytics event names | the project's own PostHog events | silent (merged in dashboards) | 22 | `<module>_` |
| DRF throttle scopes | project and generated defaults | silent (module wins) | none | two shapes (section 34) |
| raw-SQL functions | the whole schema | loud | none | `qs_` without the module (orgs' `qs_child_parent_org_equality`; rule 33 now requires `quickscale_orgs_…`) |
| raw-SQL triggers | one table | loud | none | `qs_` (orgs) |
| advisory-lock keys | the whole database | hashed | none | `quickscale:billing-…` (billing; rule 33 now requires `quickscale_billing:…`) |
| RLS policy names | one table | none | none (migration-owned) | `<module>_<model>_org_isolation` |

**Drift**
- Rule 25 rejects a bare `<module>_` prefix *because it can collide with a project app of the same
  name*. Rules 14 and 22 choose exactly that prefix for two other shared namespaces, and the one
  whose clash is silent (events) is the riskier. The next namespace (throttle scopes) has two
  precedents to copy.

## 36. References to other modules by name

Rule 5's layer rule and its planned check are about **imports**. The census also finds references
by app label, `apps.get_model`, `apps.is_installed`, and `import_module`:

| From (layer) | To (layer) | Where | What |
|---|---|---|---|
| orgs (1) | billing (3) | `permissions.require_org_feature` | loads billing's `Subscription` and reads `plan.features` to answer 402 |
| orgs (1) | billing (3) | `management/commands/purge_organization.py` | calls billing's `AppConfig` and model by label |
| orgs (1) | billing (3) | `removal.BOUNDARY_GUARDED_OBLIGATIONS` | names the one module allowed to declare a guarded obligation |
| orgs (1) | billing, blog, crm, forms, listings, social, backups, notifications, auth | `tenancy.TENANT_TABLE_REGISTRY` | 22 enrolled tables and their RLS policy names; § Multi-tenant SaaS Architecture records it as "only a shipped-module CI parity oracle", not read at runtime |
| orgs (1) | blog, crm (3) | `purge_organization._LABEL_PREFIXES` | display labels |
| orgs (1) | auth (1) | `checks.py` | names `quickscale_modules_auth.views` |
| orgs (1) | social (3) | `apps.py` | cache clearing (D6 already fixes) |
| auth (1) | billing (3) | `views.py` | account-deletion reconciliation (D6 already fixes) |
| blog (3) | storage (1) | `models.py`, `views.py` | `import_module("quickscale_modules_storage.helpers")`, outside rule 4's surface and not in `required_modules` |

**Drift**
- orgs, the foundation every tenant module builds on, knows four layer-3 modules by name, in its
  shipped source. Rule 5's fix list covers only the two import cases. A new tenant module must edit
  orgs (the registry), and billing's plan vocabulary (`plan.features`) is owned by billing but
  interpreted in orgs.
- A check written for imports will pass all of the above.

## 37. How a secret reaches module code

The five modules with `_ENV_VAR` options (the option holds the *name* of an environment variable):

| Mechanism | Modules | When a missing secret is found |
|---|---|---|
| `os.getenv(name, "")` in a settings snapshot at use, with the default variable name written again in code (`or "RESEND_API_KEY"`) | analytics, billing, notifications | at use: analytics disables itself (`"unconfigured"`), billing raises `BillingConfigurationError` (a 500), notifications at send or webhook time |
| apply-time `__QS_ENV__:<NAME>` sentinel, which core's `module_wiring` renders as `os.environ.get(NAME, "")` in `settings/modules.py` | storage | never: the setting is `""`, and boto3 treats empty credentials as absent and falls back to its default chain (environment, profile files, instance role), so the site may run on other credentials or fail on first use |
| read by core's `dr_engine` (with undeclared fallback names) | backups | at command time |

**Drift**
- One option suffix, three resolution paths. Rule 3 says values reach a running site only through
  `apply`, which the storage path follows and the other three do not. Rule 26 settles when a missing
  *webhook* secret is found (startup) but nothing settles it for an API key.

## 38. Type-check configuration

`make typecheck -- --modules` (CI) runs `mypy <module>/src` from the repository root, so the root
`mypy.ini` applies, with one `[mypy-quickscale_modules_<name>.*]` section per module.

| Root `mypy.ini` section for the module | Modules |
|---|---|
| none (full root strictness) | backups |
| relaxes `disallow_untyped_defs`, `warn_return_any`, `warn_unused_ignores` only | analytics, auth, storage |
| plus 1 disabled error code (`var-annotated`) | blog, crm, listings |
| plus 2–3 disabled codes | billing 2, notifications 2, forms 3, social 2 (+ `ignore_missing_imports`) |
| plus 12 disabled codes (`arg-type`, `assignment`, `union-attr`, `return-value`, `no-untyped-def`, `name-defined`, …) and `ignore_missing_imports` | orgs |

blog, listings, and storage also have `[tool.mypy]` (with the django-stubs plugin) in their
`pyproject.toml`, which this run does not read.

**Drift**
- Strictness runs from "none relaxed" to "twelve codes off", and the most relaxed module is orgs,
  which holds RLS, tenancy, and authorization.
- Rule 18 requires a `[tool.mypy]` section in every `pyproject.toml`, a section CI does not read.
  Met as written, it would add unread configuration to nine more modules and leave the real
  settings unchecked.
- The two declared conventions disagree. [module-extension.md § Building a
  Module](../technical/module-extension.md#building-a-module-authoring-checklist) step 1.3, where an
  author looks, says to register the module in the root `mypy.ini` with one standard override
  (`disallow_untyped_defs`, `warn_return_any`, `warn_unused_ignores` off; `var-annotated`
  disabled), and its `pyproject.toml` template has no `[tool.mypy]`. Measured against that
  override, blog, crm, and listings match it, and analytics, auth, backups, and storage are
  stricter; orgs, social, forms, notifications, and billing relax more.
- The same template carried `--cov-fail-under=70`, while rule 18 and all twelve modules use 90;
  the template now says 90 (sixth pass; a documentation fix to match the decided rule).

## 39. Module lists outside the modules

Everywhere outside `quickscale_modules/` that enumerates modules by hand:

| List | Names | Missing or different |
|---|---|---|
| core `contracts/module_catalog.py` (static catalog) | 13 (with `teams`) | its descriptions differ from `module.yml` (crm: "contacts, deals, pipeline" vs "contacts, companies, deals, and pipeline") |
| `scripts/check_security_gates.py` source roots | 12 | — |
| `scripts/render_j2_template.py` (theme lint context) | 11 | orgs |
| theme `index.html.j2` flags | 11 | orgs (section 33) |
| `scripts/lint_frontend.sh` `NO_SOCIAL_MODULES` | 10 | orgs, and social by design |
| `scripts/provision_ci_postgres.sh` isolation `MAPPING_MODULES` | 6 | social, which has tenant models |
| `scripts/test_isolation_conformance.sh` `RLS_MODULES` | 5 | social; and only crm's `test_isolation.py` runs in the PostgreSQL gate (blog, forms, listings, social have one) |
| orgs `tenancy.TENANT_TABLE_REGISTRY` | 9 modules | section 36 |
| core `tests/test_module_page_style_contract.py` `BASE_CONTRACTS` | per module | pins today's nested base paths and flat CSS, which rule 8 changes |
| core `contracts.resolvers`, `contracts.module_options`, CLI `module_config` | 9, 5, 1 | section 14 (D15 removes them) |

The recorded rule is the opposite: CLI discovery is derived from `quickscale_modules/*/module.yml`,
§ Module Presence States makes discovery report what exists, and D21 calls a hand-maintained name
list a smell.

**Drift**
- Adding a module means editing about nine files outside it, and forgetting one fails
  nothing: the lists are open-world. Social's tenant tables are outside both isolation lists
  today.

(Correction, 2026-10-03: the table missed the generated project's `project_name/urls.py.j2`,
whose React shell routes enumerate modules in regular expressions:
`^(profile|blog|listings|crm|settings)/?$` at `58e73cc7`, and
`^(profile|blog|listings|settings)/?$` plus `^crm/?$`, `^forms/?$`, `^forms/[^/]+/?$`, and the
`^orgs…` group at `c10b529e`. frontend.md § URL ownership documents the list, but rule 37's
allowlist does not name it, and the harness's rule 37 detector reads only `.py` files
(`check_module_conventions.py:4465`). Every other row above now derives from discovery or is a
listed exception, verified 2026-10-03. Section 45 holds the cost: the routes overlap module
mounts.)

## 40. README content

| Aspect | Observed |
|---|---|
| Manifest options not named in the README (by option key or setting) | notifications 10 of 10, billing 2 of 5 (`enabled`, `billing_currency`), storage 1 of 11 (`private_media_enabled`); the other nine document every option |
| Management commands not named in the README | backups 5 of 9 (`backups_pin`, `backups_record_verification`, `backups_report`, `backups_sync_media`, `dr_adapter_call`), orgs 3 of 4 (`check_tenant_isolation`, `migrate_billing_to_orgs`, `promote_to_saas`); forms 0 of 2 |
| `##` headings | 0 (notifications) to 14 (auth) |

**Drift**
- Rule 11 says the Configuration heading lists every manifest option, but the planned test checks
  headings only, so a README can pass with none of its options (notifications today).

## 41. Manifest dependency declarations

| Aspect | Modules |
|---|---|
| `required_modules` entry with a version floor, `orgs>=0.86.0` | auth, billing, blog, crm, listings, social |
| bare name, `auth` | orgs |
| required module also in `implies` | auth, billing, crm, listings, social |
| required but not implied | blog (orgs), orgs (auth) |
| implied but not required | orgs (notifications; rule 20 makes it required) |

Core's `manifest.required_modules` parses and compares the floors at `apply`.

**Drift**
- Under lockstep every module is `0.89.0`, so a `>=0.86.0` floor is always met: it is validation
  that cannot fail, and it reads as if versions could differ.
- Five orgs dependants also imply it; blog does not, so selecting blog alone follows a different
  path from its five peers. Once rule 20 lands, every `implies` entry repeats a `required_modules`
  entry.

## 42. How a module holds its settings at runtime

*Added 2026-10-03.* Rule 3 says "module code reads `settings.QUICKSCALE_<MODULE>_<NAME>`
directly". Its ❌ list rejects "per-module settings readers" and "a runtime accessor". After
SA217, five modules wrap their settings in a frozen object built from settings, and seven read
`settings.X` at the point of use.

| Form | Members | Where | Public |
|---|---|---|---|
| `@dataclass(frozen=True)` + `from_settings()` classmethod | analytics (`AnalyticsRuntimeSettingsSnapshot`) | `services.py:38` | yes (`__all__`) |
| same | billing (`BillingSettingsSnapshot`) | `_settings.py:80` | yes (re-exported, in `__all__`) |
| same, plus `from_model()` and `load_settings_snapshot()`, which rewrites the admin row from settings | notifications (`NotificationSettingsSnapshot`) | `_settings.py:35` | yes; **orgs reads it** (`orgs/views.py:122`) |
| frozen dataclass built by a private function | social (`SocialRuntimeSettingsSnapshot`) | `_contracts.py:95` | no |
| same | backups (`BackupPolicySnapshot` via `_build_policy_snapshot_from_settings()`) | `services.py:267` | yes (the class) |
| direct `settings.X` at the point of use | auth, blog, crm, forms, listings, orgs, storage (7) | — | — |

Already the same (keep): no reader defaults or coerces (0 `getattr(settings, "…", default)` in
`src/`); every snapshot docstring cites rule 3; every `is_enabled()` reads the setting directly
(12 / 12).

**Drift**
- Five modules hold a second, typed copy of their manifest options. Each of their docstrings says
  it complies with rule 3, which literally forbids "per-module settings readers". The next author
  cannot tell which reading is right. *Ambiguity, tax.*
- A public snapshot lets another module read this module's settings: orgs reads
  `NotificationSettingsSnapshot.from_settings().enabled`, which is rule 4's ❌ "reading another
  module's settings" through a sanctioned surface (section 43).

## 43. How a sender treats an optional notifications module

*Added 2026-10-03.* Rule 20: "a sender for which email is optional checks `is_enabled()` first
instead of catching it". Rule 3 also says notifications' `NotificationSettings` row is
database-backed and "only [its] initial values come from settings". Rule 20 says notifications
"can still be off at runtime (its `NotificationSettings` row)".

| Sender | Guard | Failure handling |
|---|---|---|
| forms (`_email.py:79`) | none; notifications is required (static import) | `except Exception` → `logger.warning`, inside the `on_commit` callback |
| orgs (`views.py:118–125`) | `apps.is_installed(...)`, then `NotificationSettingsSnapshot.from_settings().enabled` | returns `None` (no send) |
| rule 20's form | `services.is_enabled()` | — |

At `c10b529e` the row is no longer a runtime switch. `load_settings_snapshot()`
(`_settings.py:168`) rewrites the row from settings on every load, the admin is
`ReadOnlyAdminMixin` (`admin.py:116`), and `enabled` comes from `QUICKSCALE_NOTIFICATIONS_ENABLED`.
`NotificationDisabledError` is raised only when that setting is false.

**Drift**
- Two senders, two guards, and neither uses the rule's `is_enabled()`. forms' catch-all also
  swallows a `NotificationConfigurationError`, which rule 10's fail-hard stance wants visible.
  *Ambiguity.*
- Rules 3 and 20 describe a runtime row that the code made a mirror. The rule text is stale, so
  an author reading it would write a guard for a state that cannot occur.

## 44. Who checks an org role

*Added 2026-10-03.* Rule 19 keeps "one role check": orgs' `user_has_org_role`, which is
superuser-true and otherwise compares the membership role against `OrgRole`.

| Site | How | Role vocabulary |
|---|---|---|
| views and APIs of blog, crm, forms, listings, billing, orgs | `permissions` helpers (`OrgRoleMixin`, `HasOrgRole`, `user_has_org_role`) | `OrgRole.*` |
| billing `_subscription_mutations.py:146–163` (re-check after the provider lock) | hand-written: `is_superuser` short-circuit + `OrganizationMembership.filter(role="owner")` + `is_active` | string `"owner"` |

The harness's rule 19 scan finds view code by content (rule 46), not by file name: it reads a
service module only where that module defines a view subclass or a function taking `request`, and
billing's `_subscription_mutations.py` defines neither, so it stays outside the check.

**Drift**
- billing re-implements the role check with a string literal and an extra `is_active` test that
  orgs' helper does not make. If orgs' role ladder changes (a new `billing_admin` role, say), the
  view admits and the re-check refuses. That surfaces as "Billing authorization changed while the
  provider mutation was waiting". *Ambiguity.*

## 45. Who owns a module's URL path

*Added 2026-10-03.* Rule 7: "The manifest's `url_includes` sets a module's mount … and is the
only place." After SA223 every module conforms on its own side. The host project and the theme
still write module paths as literals, and some of those literals take the path first.

| Copy | Paths | Order against the module mount |
|---|---|---|
| generated `urls.py.j2:51–64` React shell routes | `^orgs…`, `^crm/?$` (named `crm-shell`), `^(profile\|blog\|listings\|settings)/?$`, `^forms/?$`, `^forms/[^/]+/?$` | **before** `POST_HOME_MODULE_URLPATTERNS` |
| generated `urls.py.j2:74–85` social pages | `^social/?$` (`social-link-tree`), `^social/embeds/?$` (`social-embeds`) | before post-home; social mounts at `_quickscale/social/` |
| theme `social/*.html.j2`, `base.html.j2:115` | `/crm/`, `/analytics/`, `/social`, `/social/embeds` | literals (section 33) |
| orgs `TenantMiddleware` | `/orgs/`, `/orgs/api/`, `/accounts/` (tech-audit §9) | literals |

Resolved against the shell patterns: `blog/` → shell (blog's `post_list`, a server-rendered
`ListView`); `listings/` → shell (`listing_list`); `forms/` and `forms/<slug>/` → shell (forms'
`FormPageView`, itself a React mount, so no loss); `crm/` → shell (crm has no root route);
`blog/post/<slug>/` → module.

**Drift**
- Two owners for one path. In a generated project, `reverse("quickscale_blog:post_list")` and
  `reverse("quickscale_listings:listing_list")` resolve to URLs that the React shell serves, not
  the module views. The shell route is also not gated on `QUICKSCALE_BLOG_ENABLED`. frontend.md
  § URL ownership says the React page and "a server-rendered blog index … are different URLs, by
  design", which is not true for the index. *Collision.* Hand-off: tech, to decide whether the
  module index is meant to be reachable.
- Route names in the host namespace mix styles: `crm-shell`, `social-link-tree`, and
  `social-embeds` are kebab-case and unnamespaced, beside `quickscale_analytics:dashboard`.
  `generator/seam._SEAM_MODULE_PATHS` reverses both kinds. *Tax.*
- A module mount changed in its manifest still has to be changed by hand in four other places. No
  check covers the `.j2` copies. *Tax.*

## 46. Split facades

*Added 2026-10-03.* SA231/SA232 split long files into private `_<name>.py` siblings behind the
original module (rule 28 allows any `_<name>.py`). No rule governs what the facade re-exports,
what the private files are called, or which logger they use.

| Aspect | Variants (members) |
|---|---|
| Private names re-exported by the facade (`_x as _x`) | billing `services.py` 121; notifications `services.py` 29; orgs 74 across `tenancy` 26, `removal` 14, `views` 12, `checks` 12, `current_org` 10; auth `views.py` 4; backups `admin.py` 0 |
| Facade states why it re-exports | "test patch targets keep working" (billing, notifications); "drop-in replacement" (backups); none (orgs, auth) |
| Private file naming | `_<facade>_<part>` (backups `_admin_*`, orgs `_tenancy_*`, `_removal_*`, `_view_*`); `_<subject>` (billing `_checkout`, `_credits`; notifications `_delivery`); `_<part>_views` (auth `_profile_views`, orgs `_api_views`) |
| View files | `_view_<part>.py` (orgs 4) and `_<part>_views.py` (auth 1, orgs 1). Harness rule 19 finds view code by content (rule 46), so the split's chosen name is free |
| Logger after a split | auth pins the old channel (`_logging.py`: `getLogger("quickscale_modules_auth.views")`, because a test asserts on it); billing (`_subscription_mutations`), notifications (`_delivery`), and orgs (`_debug`) log under the private file's `__name__`; backups' private files do not log (15 `getLogger(__name__)` in `src/` in all) |

Already the same (keep): every facade keeps its public import path; every private file is
`_<name>.py`; `services.py` `__all__` is the surface (rule 23), so private re-exports do not
widen it.

**Drift**
- The next split must choose among three naming forms and two re-export policies (all privates
  for patching, or none). Re-exporting privates for patching only works while a test patches a
  name the facade's own code calls: notifications' docstring says that helpers called inside
  the private modules "resolve there, not through this facade". The arch audit records the
  structural cost. Here the cost is that a split author has no rule to copy. *Tax.*
- Rule 19's coverage depends on the file name a split author picks. *Ambiguity* (an enforcement
  gap, not a defect today: no forbidden token appears outside the scanned names except at listed
  operator paths and analytics' listed `is_staff` filter).
- Log channels move silently. billing's logger was `quickscale_modules_billing.services` at
  `58e73cc7` and is now `…billing._subscription_mutations`; the earlier channels of
  notifications' `_delivery` and orgs' `_debug` were not traced. An operator's log filter keyed on
  the old channel stops matching, and the release notes do not say so. auth alone kept its
  channel. *Ambiguity.*

## 47. Third-party type-stub exemptions

*Added 2026-10-03.* Rule 36: type checking is configured in the root `mypy.ini` only; "❌ A
per-module `[tool.mypy]` (CI … does not read it)". The harness exempts
`[[tool.mypy.overrides]]` (`check_module_conventions.py:4653`, "only carries third-party stub
exemptions"). Rule 36 lists no such exception, and rule 40 says every exception lives in the
test-owned mapping that mirrors the decision.

| `[[tool.mypy.overrides]] ignore_missing_imports` in `pyproject.toml` | Members | Root `mypy.ini` |
|---|---|---|
| `posthog`, `allauth`, `stripe`, `markdownx`, `storages` | analytics, auth, billing, blog / listings, backups / storage | present (`:45`, `:30`, `:48`, `:33`, `:51`) |
| `rest_framework` | billing, crm, forms (not blog, listings, notifications, orgs, which also use DRF) | present (`:39`) |
| `django_filters` | crm, forms, listings | present (`:36`) |
| `anymail` | notifications | **absent**: the only declaration is one CI never reads |
| none | orgs, social | — |

**Drift**
- Configuration in 10 modules that nothing reads. Its coverage is also inconsistent:
  `rest_framework` appears in three of the seven DRF users (billing, blog, crm, forms, listings,
  notifications, orgs). *Tax.*
- The harness is more permissive than the rule it mirrors: an unlisted exemption. *Ambiguity.*

## What is already consistent (keep)

- Package, `AppConfig`, and app-label naming.
- `adapter.py` as the apply-time hook module.
- Secrets passed by env-var *name* (`*_ENV_VAR`), and the managed `.env.example` block
  (conformance-gated).
- Python and Django version constraints across modules (`check_module_python_constraints`,
  `check_module_django_constraints`).
- Every module version in lockstep with core (`0.89.0`).
- `created_at` / `updated_at` timestamps, `settings.AUTH_USER_MODEL` references, and
  `@admin.register` (third pass; D17 and D16 now enforce them).
- `logging.getLogger(__name__)` and no f-string log messages.
- Build backend, pytest and coverage settings across `pyproject.toml` files.
- Server-rendered pages are class-based views in every module; function views are only blog's and
  listings' JSON APIs, which rule 9 already moves to DRF (fifth pass).
- `on_delete` on `User` (section 29; SA35's gate) and webhook verification and deduplication in
  `services.py` (section 28).
- Every migration that references another module's model depends on that module's `0001_initial`,
  and user references use `swappable_dependency` (fifth pass).
- `py.typed` in all twelve packages; `[tool.pytest.ini_options]` and three `[tool.ruff*]` sections in
  every `pyproject.toml`; the `qs_` prefix on orgs' per-table triggers; every wiring
  setting goes through `ModuleWiringSpec` (sixth pass).

## Module independence: what is already decided

The goal "each module is independent" is only partly written down today. What exists, from
[decisions.md](../technical/decisions.md) and the CI gates:

| Recorded rule | Where | What it guarantees | What it does not cover |
|---|---|---|---|
| **Core ↔ module boundary.** Modules import core only through `quickscale_core.runtime`; core imports no module. | `scripts/check_module_core_imports.py` (SA9.6 / SA89b), CI job `module-core-import-linter` | Core and modules can change internals without breaking each other. | Core reading a module's **settings by name** is not an import, so the gate misses `dr_engine` reading `QUICKSCALE_BACKUPS_*`. |
| **No per-module wiring knowledge in core or CLI.** A module declares its wiring in its own `module.yml` and runs it through its own `adapter.py`. | decisions § Module Wiring Authority; "Architecture & Patterns" ❌ list | Adding a module needs no core change. | Same `dr_engine` exception. |
| **Mutable options are read from settings, never hard-coded.** | decisions § Module Manifest Architecture | Configuration flows `module.yml` → settings. | Says nothing about defaults also being written in code. |
| **Fail-hard; no compat shims or silent degradation.** | decisions § Fail-Hard Principle; ❌ list | Supports D8 (no aliases). | Today's `getattr(settings, X, default)` calls are exactly such silent fallbacks. |
| **No DI frameworks or service registries (direct imports in production).** | decisions "Architecture & Patterns" ❌ list | Keeps module code plain. | Conflicts with parts of D5 (see there). The SA213 removal obligations declared on `AppConfig` already act as a small registry. |
| **No custom database table names; use the app-label default.** | decisions "Architecture & Patterns" ❌ list | Predictable table names. | **Violated today:** auth sets `db_table = "quickscale_auth_user"`, backups sets `quickscale_modules_backups_policy` / `_artifact` / `_snapshot`, and forms sets it on all four models to the value the default already produces (`quickscale_modules_forms_form`, …), which would pin the old names when rule 2 changes the label. (Correction, sixth pass: the first write-up missed backups' third table and forms' four) |
| **Lockstep versions.** Every module ships at the repository version; no independent module versions; "every change is a clean break". | decisions § Module Version Lockstep | Supports D8: no mixed-version compatibility to preserve. | — |
| **Module dependencies declared in `module.yml`** (`required_modules`, `implies`). | manifests; apply resolves them | apply installs what a module needs. | Not checked against real imports (forms imports orgs but declares nothing). |

**What is *not* decided anywhere:** how one module may depend on or talk to another module. There is
no rule for module-to-module imports, so each pair invented its own way (sections 3 and 5). D5 and D6
fill that gap. Two facts shape them:

- `auth` requires `orgs` **and** `orgs` requires `auth` (both manifests). They are already one unit in
  practice: you cannot install either alone.
- `orgs` implies `notifications` (manifest), which is why orgs sends invitation emails through it.

So "independent" today means: **independent of core, not of each other.** Modules are independently
*packaged* (own `pyproject.toml`, README, split branch) but not independently *usable*: most need
orgs, and auth and orgs need each other.

## Convention decisions

Status of each question: **decided** (the maintainer chose), **proposed** (waiting for approval),
or **options** (compared below with a recommendation, waiting for a choice). All of it is a change to
the QuickScale codebase, not to any deployed site. Decided items go into [decisions.md](../technical/decisions.md)
as written here.

### D1 — One settings family: `QUICKSCALE_<MODULE>_<NAME>` — decided

Every first-party module setting starts with `QUICKSCALE_<MODULE>_`, where `<MODULE>` is the module
name in upper case. The bare `<MODULE>_*` family is retired.

**Only exception:** a setting read by a third-party library or by Django itself keeps the name that
library reads, because renaming it would simply stop working. These are listed, not implied:

| Module | Kept third-party / Django names |
|---|---|
| auth | `ACCOUNT_ALLOW_REGISTRATION`, `ACCOUNT_EMAIL_VERIFICATION` (django-allauth), `SESSION_COOKIE_AGE` (Django) |
| storage | `MEDIA_URL` (Django), `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL`, `AWS_S3_REGION_NAME`, `AWS_DEFAULT_ACL`, `AWS_QUERYSTRING_AUTH` (django-storages) |

> **⚠ Migration to be done in the codebase (D1 + D2).** Every rename below changes, in one pass:
> the module's `module.yml` and its copy under `quickscale_core/src/quickscale_core/data/manifests/`,
> every read in module and core code, the generator's settings and theme templates, tests and
> fixtures, and docs. It is a breaking change for projects generated earlier: under D8 there is no
> alias, and an old name fails hard, naming its replacement.

| Module | Old setting | New setting | Option key (old → new) |
|---|---|---|---|
| blog | `BLOG_POSTS_PER_PAGE` | `QUICKSCALE_BLOG_POSTS_PER_PAGE` | `posts_per_page` (same) |
| blog | `BLOG_API_RATE_LIMIT` | `QUICKSCALE_BLOG_API_RATE_LIMIT` | `api_rate_limit` (same) |
| blog | `BLOG_ENABLE_RSS` | `QUICKSCALE_BLOG_RSS_ENABLED` | `enable_rss` → `rss_enabled` |
| blog | `BLOG_API_TOKENS` *(undeclared)* | `QUICKSCALE_BLOG_API_TOKENS` | new, declared |
| blog | `BLOG_API_UPLOAD_MAX_BYTES` *(undeclared)* | `QUICKSCALE_BLOG_API_UPLOAD_MAX_BYTES` | new, declared |
| blog | `BLOG_API_ALLOWED_IMAGE_FORMATS` *(undeclared)* | `QUICKSCALE_BLOG_API_ALLOWED_IMAGE_FORMATS` | new, declared |
| crm | `CRM_ENABLE_API` | `QUICKSCALE_CRM_API_ENABLED` | `enable_api` → `api_enabled` |
| crm | `CRM_DEALS_PER_PAGE` | `QUICKSCALE_CRM_DEALS_PER_PAGE` | `deals_per_page` (same) |
| crm | `CRM_CONTACTS_PER_PAGE` | `QUICKSCALE_CRM_CONTACTS_PER_PAGE` | `contacts_per_page` (same) |
| forms | `FORMS_PER_PAGE` | `QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE` | `forms_per_page` → `submissions_per_page` |
| forms | `FORMS_SPAM_PROTECTION` | `QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED` | `spam_protection_enabled` (same) |
| forms | `FORMS_RATE_LIMIT` | `QUICKSCALE_FORMS_RATE_LIMIT` | `rate_limit` (same) |
| forms | `FORMS_DATA_RETENTION_DAYS` | `QUICKSCALE_FORMS_RETENTION_DAYS` | `data_retention_days` → `retention_days` |
| forms | `FORMS_SUBMISSIONS_API` | `QUICKSCALE_FORMS_API_ENABLED` | `submissions_api_enabled` → `api_enabled` |
| listings | `LISTINGS_PER_PAGE` | `QUICKSCALE_LISTINGS_PER_PAGE` | `listings_per_page` → `per_page` |
| orgs | `QUICKSCALE_MODE` | `QUICKSCALE_ORGS_MODE` | `mode` (same) |
| billing | `QUICKSCALE_BILLING_CURRENCY` (same) | — | `billing_currency` → `currency` |
| notifications | `QUICKSCALE_NOTIFICATIONS_PROVIDER` *(undeclared)* | same name | new, declared |
| backups | `QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID`, `…_SECRET_ACCESS_KEY` *(undeclared fallbacks in `dr_engine`)* | removed | fallbacks deleted under D8 |

**`QUICKSCALE_ORGS_MODE` is the widest rename:** besides the orgs module it was read by the generated
`context_processors.py.j2` and is read by the `showcase_react` `index.html.j2`, so every generated
project's templates changed with the rename (SA235 later moved billing's template URL to route
names).

### D2 — Standard suffixes — decided

The option key is always the setting suffix in lower case (`QUICKSCALE_CRM_API_ENABLED` ↔
`api_enabled`), and a key never repeats the module name.

| Suffix | Meaning | Type |
|---|---|---|
| `_ENABLED` | turns a module or one of its features on or off (`QUICKSCALE_BLOG_RSS_ENABLED`) | boolean |
| `_API_ENABLED` | turns the module's REST API on or off; name the API only if the module has more than one | boolean |
| `<THING>_PER_PAGE` | page size; name the thing unless it is what the module is named after (`POSTS_PER_PAGE`, but `LISTINGS_PER_PAGE`) | integer |
| `_RATE_LIMIT` | throttle, always the `"<count>/<period>"` string, parsed by one shared parser | string |
| `_RETENTION_DAYS` | days before data is deleted or anonymized; `0` keeps forever | integer |
| `_TTL_SECONDS` | lifetime of a cache entry or a signed token | integer |
| `_ENV_VAR` | holds the *name* of an environment variable carrying a secret, never the secret | string |

Booleans that describe behavior rather than switch a feature (`QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG`,
`…_ANONYMOUS_BY_DEFAULT`) keep a descriptive name; `_ENABLED` is only for on/off switches.

#### `_ENABLED` or `_ENABLE`? — decided: `_ENABLED`

| | `_ENABLED` | `_ENABLE` |
|---|---|---|
| Grammar | Adjective: describes a state. `QUICKSCALE_BLOG_RSS_ENABLED = True` reads "RSS is enabled". | Verb: an instruction. `QUICKSCALE_BLOG_RSS_ENABLE = True` reads "enable RSS". |
| Fits a boolean | Yes: a boolean holds a state, and `if settings.X_ENABLED:` reads as a sentence. | Awkward: `if settings.X_ENABLE:` reads as a command, and `X_ENABLE = False` reads as "enable: no". |
| Django convention | Many Django booleans name a state (`DEBUG`, `CSRF_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`); none ends in a bare verb. | Appears mostly as a *prefix* (`ENABLE_X`), which D2 retires. |
| This codebase today | 6 settings already use it (`QUICKSCALE_ANALYTICS_ENABLED`, `…_BILLING_ENABLED`, `…_NOTIFICATIONS_ENABLED`, `…_SOCIAL_LINK_TREE_ENABLED`, `…_SOCIAL_EMBEDS_ENABLED`, `…_BACKUPS_AUTOMATION_ENABLED`). | 0 as a suffix; 2 as a prefix (`CRM_ENABLE_API`, `BLOG_ENABLE_RSS`). |
| Rename cost | 3 settings change (`CRM_ENABLE_API`, `BLOG_ENABLE_RSS`, `FORMS_SPAM_PROTECTION`). | 9 settings change, including the 6 already consistent. |

**Decided: `_ENABLED`.** It is grammatically right for a boolean, matches Django's style, and
is already what the codebase uses, so it changes 3 names instead of 9. (D3's new per-module
switches are new names either way.)

### D3 — Every module has `QUICKSCALE_<MODULE>_ENABLED` — decided

Today only analytics, billing, and notifications have one. With the switch off, the module stays
installed and its data stays untouched, but its public surfaces are off: URLs return 404, its pages
and API disappear, and scheduled jobs do not run. Admin stays available so data can still be seen.

**Resolved in the decision entry:** `orgs`, `auth`, and `storage` are foundations other modules
build on. They get the switch like every module, and `apply` refuses to switch a module off while an
installed module lists it in `required_modules`.

### D4 — How modules read their settings — decided: option 1

#### When are settings read: at `plan`/`apply` time, or when the site runs?

**Both, at different moments, by different programs.**

| Moment | Who | What it reads | What it does |
|---|---|---|---|
| **1. `quickscale plan`** (your machine) | the CLI | each selected module's `module.yml` | Asks for options, validates them against the declared types, writes `quickscale.yml`. |
| **2. `quickscale apply`** (your machine) | the CLI | `module.yml` + `quickscale.yml` | Resolves every option (your value, else the manifest default) and **writes every one** into the project's `settings/modules.py` ("DO NOT EDIT MANUALLY"). |
| **3. Site startup** (local, CI, or Railway) | Django | `settings/modules.py` | Loads the values into `django.conf.settings`. No manifest, no CLI. |
| **4. Each request or job** | module code | `django.conf.settings` | Uses the value: page size, rate limit, API on/off. |

Evidence, from a freshly generated project:

```python
MODULE_SETTINGS: dict[str, object] = {'FORMS_PER_PAGE': 25, 'FORMS_RATE_LIMIT': '5/hour',
                                      'LISTINGS_PER_PAGE': 12, ...}
```

**D4 is only about moments 3–4.** Moments 1–2 already work the same way for every module. By the
time module code runs, every declared setting already has a value in the project, so the default in
`getattr(settings, "LISTINGS_PER_PAGE", 12)` is never used — it only hides a setting that someone
deleted, which the Fail-Hard Principle forbids.

Module tests run outside a generated project and use their own settings stub
(`quickscale_modules/listings/tests/settings.py` sets `LISTINGS_PER_PAGE = 12`), so tests already
supply values explicitly.

#### What must any option achieve?

From the decisions already taken, a settings approach must satisfy:

| # | Requirement | Source |
|---|---|---|
| R1 | A missing or invalid value fails loudly, naming the setting; no silent default | Fail-Hard Principle; D8 |
| R2 | Each default is written once, in `module.yml` | Module Manifest Architecture ("read from settings, no hardcoding") |
| R3 | Core holds no per-module knowledge; modules reach core only through `quickscale_core.runtime` | Module Wiring Authority; core ↔ module gate |
| R4 | No service registry or DI container | "Architecture & Patterns" ❌ list |
| R5 | A module reads only its own declared settings | D5, D9 |
| R6 | Modules depend only downward | D6 |
| R7 | The project owns its files; QuickScale owns only its managed files | generated-file ownership |
| R8 | Every rule is checkable by the D9 conformance test | D9 |

#### The options

**1. Direct read + a shared startup check fed by `apply` (new, "F").**

```python
# settings/modules.py — written by apply (QuickScale-managed), one extra dict:
MODULE_SETTINGS_SCHEMA = {"listings": {"QUICKSCALE_LISTINGS_PER_PAGE": "positive_int"}, ...}

# listings/apps.py — the module registers the generic check for itself
from quickscale_core.runtime import register_module_settings_check
def ready(self): register_module_settings_check("listings")

# listings/views.py — plain Django, no default
paginate_by = settings.QUICKSCALE_LISTINGS_PER_PAGE
```

At startup, the check reads the schema `apply` wrote and fails with "QUICKSCALE_LISTINGS_PER_PAGE is
missing or not a positive integer — run `quickscale apply`". The check function is generic (no module
names inside core); each module opts in with one line.

**2. Direct read + a check in each module (E).** Same as 1, but each module's `apps.py` lists its own
setting names and types; the D9 test verifies the list equals `module.yml`.

**3. A runtime accessor in core (A).** `module_settings("listings").per_page`; the accessor loads the
module's manifest at runtime (from `quickscale_core/data/manifests/`) for type and default.

**4. A generated typed file per module (B).** `apply` writes `settings/module_settings/listings.py`
with a frozen dataclass; module code imports it.

**5. Keep today's readers, test them (C).** A D9 rule checks that code defaults equal manifest
defaults.

**6. Hand-written snapshot class per module (D).** Every module copies the analytics/social pattern:
a frozen dataclass with `from_settings()`.

#### Alignment with previous decisions

✅ satisfies · ⚠️ partly or with care · ❌ violates

| Req. | 1. Direct + shared check | 2. Direct + per-module check | 3. Runtime accessor | 4. Generated file | 5. Readers + test | 6. Snapshots |
|---|---|---|---|---|---|---|
| R1 fail-hard | ✅ startup check | ✅ startup check | ⚠️ only if built never to fill defaults | ❌ dataclass defaults fill gaps | ❌ code defaults stay | ❌ code defaults stay |
| R2 default once | ✅ manifest → apply | ✅ | ✅ | ⚠️ generated copy | ❌ two copies | ❌ two copies |
| R3 no per-module core knowledge | ✅ generic check via `runtime` | ✅ no core code | ⚠️ core loads module manifests at runtime | ✅ | ✅ | ✅ |
| R4 no registry | ✅ | ✅ | ⚠️ lookup by module name | ✅ | ✅ | ✅ |
| R5 own settings only | ✅ via D9 | ✅ via D9 | ✅ by construction | ✅ by construction | ✅ via D9 | ⚠️ via D9 |
| R6 downward deps | ✅ | ✅ | ✅ | ⚠️ module depends on a project file | ✅ | ✅ |
| R7 file ownership | ✅ uses the existing managed file | ✅ | ✅ | ❌ new file per module in the project | ✅ | ✅ |
| R8 checkable | ✅ | ✅ | ✅ | ✅ | ⚠️ only recognized patterns | ⚠️ |
| **Score** | **8 ✅** | **8 ✅** | 5 ✅, 3 ⚠️ | 4 ✅, 2 ⚠️, 2 ❌ | 5 ✅, 1 ⚠️, 2 ❌ | 4 ✅, 2 ⚠️, 2 ❌ |

#### Pros, cons, and impact

| | 1. Direct + shared check | 2. Direct + per-module check | 3. Runtime accessor | 4. Generated file | 5. Readers + test | 6. Snapshots |
|---|---|---|---|---|---|---|
| **Pros** | Simplest module code (`settings.X`); one validation implementation; types come from the manifest via `apply`, so nothing is duplicated | Same simple reads; no new core code at all | Undeclared reads impossible by construction; one validation implementation | Strong typing and editor completion | Almost no work | Typed; a pattern already in two modules |
| **Cons** | Adds one dict to `settings/modules.py` and one small core function | Names and types written twice (manifest + `apps.py`), guarded by D9 | New core API every module depends on; manifests needed in the running site; untyped attributes | Module behavior depends on a project file that projects can edit; every default change needs regeneration | Keeps eight styles and two copies of defaults | Two copies of defaults; drift returns when someone skips the pattern |
| **Work now** | Apply writes the schema; one generic check in `quickscale_core.runtime`; remove readers and defaults from 12 modules; update test stubs | Per-module check lists; remove readers and defaults; update stubs | Build the accessor; convert all reads in 12 modules | Generator change; new owned file type; convert 12 modules | One D9 rule | Write ~10 snapshot classes |
| **Cost of a new module** | Declare options in `module.yml`; add one `ready()` line | Declare options; write the check list | Declare options | Declare options; regenerate | Write a reader and keep defaults equal | Write a snapshot class |
| **Cost of changing a default** | Edit `module.yml`, run `apply` | Same | Edit `module.yml` | Edit and regenerate every project | Two edits | Two edits |
| **Runtime cost** | One check at startup | One check at startup | Manifest load (cached) at first use | None | None | None |
| **Typing (mypy)** | `settings.X` is untyped; values are validated at startup instead | Same | Untyped unless stubs are generated | Typed | Unchanged | Typed |
| **Module tests** | Test stubs must set every declared setting (can be generated from the manifest) | Same | Stubs optional (defaults from manifest) | Stubs need the generated file | Unchanged | Unchanged |
| **Long-term risk** | Low: reuses the existing apply → `modules.py` flow | Low, plus a list to keep equal | Core API becomes a hot spot every module tracks | Generated files drift in projects | Duplication stays forever | Drift returns |

#### Decided: option 1 (direct read + shared startup check fed by `apply`)

- **It is the only option that satisfies all eight requirements without duplication.** Option 2 also
  scores 8, but writes every name and type twice; option 1 takes them from the manifest through
  `apply`, the path that already delivers the values.
- **It builds on what already exists** instead of adding a mechanism: `apply` already writes every
  value into the managed `settings/modules.py`; it now also writes their types.
- **Modules stay independent**: module code reads plain Django settings, and depends on core only for
  a one-line check registration through the approved `quickscale_core.runtime` facade.
- **It enforces D8 at runtime**: a retired or missing name fails at startup with the fix in the
  message, not deep in a request.
- **Accepted cost:** settings reads are untyped for mypy. For scalar configuration values validated at
  startup, that is a small loss compared with the duplication every typed option brings back.

Database-backed settings (backups' `BackupPolicy`, notifications' `NotificationSettings`) keep their
models under every option; only their initial values come from settings.

### D5 — How one module uses another — decided (as recommended)

#### What happens today

Modules are optional. A module that *uses* another must work whether or not that other module is
installed or switched on. Today every pair solves this its own way. Real examples:

```python
# forms/views.py — forms sends an analytics event
if not apps.is_installed("quickscale_modules_analytics"):
    return
if not bool(getattr(settings, "QUICKSCALE_ANALYTICS_ENABLED", True)):  # reads analytics' setting
    return
from quickscale_modules_analytics.services import capture_form_submit, get_distinct_id

# forms/notifications.py and orgs/views.py — the same idea, written twice, in a different style
if not apps.is_installed("quickscale_modules_notifications"):
    return None
if not bool(getattr(settings, "QUICKSCALE_NOTIFICATIONS_ENABLED", True)):
    return None
notifications_services = import_module("quickscale_modules_notifications.services")
return getattr(notifications_services, "send_notification")

# auth/views.py — auth asks billing to clean up when a user is deleted
if "quickscale_modules_billing" not in settings.INSTALLED_APPS:
    return
app_config = apps.get_app_config("quickscale_modules_billing")
reconcile = getattr(app_config, "reconcile_account_deletion_provider_state", None)
```

And one pattern that is already done well: **organization removal**. Each module declares what must
happen when an organization is deleted, on its own `AppConfig` (`removal_obligations()` in billing,
orgs, and others), and one coordinator in orgs runs them all. orgs never imports billing; billing
announces itself.

**What goes wrong today:**

- The caller knows the callee's **internals**: its setting name, its default, its app label string,
  and the name of a function inside it. Renaming any of them (as D1 does) silently breaks the caller.
- "Is it installed?" and "is it switched on?" are asked with three different idioms.
- The dependency points the wrong way in places: auth (lower layer) knows about billing (higher).

#### The options

**A. Each module exposes one public file, `services.py`.**

```python
# analytics/services.py — the public API
def is_enabled() -> bool: ...
def capture_form_submit(request, form) -> None: ...


# forms/views.py
from quickscale_core.modules import optional_service

analytics = optional_service("analytics")  # None if not installed or not enabled
if analytics is not None:
    analytics.capture_form_submit(request, form)
```

The rule: another module may import only `quickscale_modules_<x>.services`. A small core helper
answers "installed and enabled?" in one place.

**B. Signals: the sender announces, receivers act.**

```python
# forms/signals.py
form_submitted = Signal()
form_submitted.send(sender=Form, request=request, form=form)

# analytics/apps.py — analytics subscribes; forms never mentions analytics
form_submitted.connect(capture_form_submit)
```

**C. Capability declarations on `AppConfig` (the removal-obligation pattern, generalized).**

```python
# billing/apps.py — billing declares what it provides
class QuickscaleBillingConfig(AppConfig):
    def account_deletion_handlers(self):
        return (reconcile_provider_state,)


# auth/views.py — auth asks core for every installed provider
for handler in collect("account_deletion_handlers"):
    handler(user)
```

The lower module defines a named hook; any higher module that is installed and enabled fills it.

#### Comparison

| Question | A. Public `services.py` | B. Signals | C. AppConfig capabilities |
|---|---|---|---|
| Good for | "Do this for me" / "tell me X" (send a notification, is analytics on?) | "Something happened" (form submitted, user signed up) | "Everyone who cares, act on this" (account deleted, org removed) |
| Direction | Caller knows the callee's module name | Sender knows nothing about receivers | Lower module defines the hook; higher modules fill it |
| Respects layers (D6)? | Only when the caller is higher than the callee | Yes, always | Yes, always |
| Following the code | Easy: a direct call | Hard: who listens is found only by searching | Medium: one `collect(...)` call, providers listed on AppConfigs |
| Errors | Raised to the caller | Swallowed or all-or-nothing, depending on the signal | Coordinator decides; can fail closed (as removal does) |
| Testing | Mock one function | Must assert a receiver is connected | Call the hook directly |
| Already in the codebase | Partly (`services.py` exists in six modules) | Django/allauth signals only | Yes — removal obligations (SA213) |
| Work now | Add `services.py` to four modules; route imports through it | Define signals per event; move handlers into receivers | Generalize the removal coordinator into a small `collect()` in core |

#### Long-term impact

The three are not really competitors; each fits one kind of interaction, and the risk is using the
wrong one:

- Using **A** for everything keeps upward calls like auth → billing, which D6 forbids.
- Using **B** for everything makes control flow hard to follow, and signals cannot answer questions
  ("is analytics on?").
- Using **C** for everything turns simple calls into indirection.

**Recommendation: all three, each for its case, written as one rule:**

| Interaction | Mechanism |
|---|---|
| A higher module asks a lower one to do something or answer something | **A** — import its `services.py` via `optional_service()` |
| A module announces an event and does not care who reacts | **B** — a signal defined in the sender |
| A lower module needs every installed higher module to act | **C** — an AppConfig capability collected by core |
| Reading another module's settings or importing its models, views, or internals | forbidden |

Applied to today's code: forms → analytics and forms/orgs → notifications become **A**; auth →
billing on account deletion becomes **C** (like org removal); orgs → social cache clearing becomes
**C** (social declares its cache keys).

**Correction made when recording the decision: foundations publish more than `services.py`.** Every
tenant module builds on orgs' classes — `Organization` and `TenantModel`, `TenantManager`,
`TenantModelAdmin`, `current_org`, `tenancy` helpers (about 60 imports today). An "only
`services.py`" rule would forbid them. The recorded rule therefore defines a module's **public
surface** as `services.py` plus, for a foundation, an explicitly listed set of extension bases; see
[decisions.md § Module Conventions](../technical/decisions.md#module-conventions) rule 4.

**Conflict with a recorded rule, to resolve in the decision entry.** decisions.md forbids "DI
frameworks or service registries (direct imports in production)". The capability mechanism (C) is a
small registry, like the SA213 removal obligations that already exist under that rule. The decision
entry must narrow the rule: capabilities declared on a module's own `AppConfig` and collected by one
core helper are allowed; a general service registry or DI container stays forbidden. `optional_service()`
is replaced by a plain check (`apps.is_installed(...)` plus the target's `services.is_enabled()`),
so no lookup-by-name registry is introduced.

### D6 — Dependency direction between modules — approved (layers + declared dependencies; `auth ↔ orgs` option a)

#### The idea in plain terms

A **dependency** means "module X uses code from module Y", so Y must be installed and working for X
to work. When dependencies only point one way — features use platform services, platform services
use foundations — you get three practical benefits:

1. **You can understand a module by reading it and what is below it**, never what is above.
2. **You can test a lower module alone.** orgs' tests need nothing else if orgs imports nothing.
3. **You can change a higher module without touching lower ones.** Removing blog can never break
   orgs.

When two modules use each other (a **cycle**), neither can be installed, tested, or changed alone —
they behave as one module with two names. That is `auth` and `orgs` today: auth imports orgs' models
in `views.py`, orgs subclasses auth's allauth adapter in `adapters.py`, and each `module.yml`
requires the other. Every generated project confirms it: `ACCOUNT_ADAPTER` is set to
`quickscale_modules_orgs.adapters.OrgsAccountAdapter`, a class that only exists because orgs extends
auth.

#### Today's real dependency graph

(→ means "imports code from"; *declared* means it is also in `required_modules`/`implies`)

```text
auth ──────► orgs        (declared)          orgs ──► auth           (declared)   ← cycle
auth ──────► billing     (lazy, undeclared)  orgs ──► social         (lazy, undeclared)
                                             orgs ──► notifications  (declared via implies)
billing, blog, crm, listings, social ──► orgs   (declared)
forms ──► orgs           (undeclared)        forms ──► analytics, notifications (lazy, undeclared)
quickscale_core (dr_engine) ── reads settings of ──► backups
analytics, backups, notifications, storage ──► (nothing)
```

#### Alternatives

| Option | Rule | Pros | Cons |
|---|---|---|---|
| **1. Layers (proposed)** | Each module has a layer number; it may import only its own layer or lower. | Strongest guarantee; easy to check (compare two numbers); matches how people think about the stack. | Needs agreement on each module's layer; moving a module later is a decision, not a fix. |
| 2. "No cycles" only | Any module may import any other, as long as no cycle forms. | Least work: only auth ↔ orgs must change. | Allows a foundation to depend on a feature (orgs → social) as long as there is no loop back, which is the problem D6 is meant to stop. |
| 3. Declared dependencies only | A module may import only what its `module.yml` lists in `required_modules`. | Uses what exists; makes the manifest truthful. | Says nothing about direction; a cycle is allowed if both sides declare it (as today). |
| 4. Layers **and** declared (recommended form of 1) | Layers set what is *allowed*; `required_modules` must include everything *used*. | Direction is enforced and the manifest stays honest, so `apply` installs the right set. | Two rules to maintain, both checked by D9. |
| 5. Status quo | No rule. | No work. | The inventory's drift continues. |

#### Proposed layers

| Layer | Modules | Why |
|---|---|---|
| 0 — core | `quickscale_core` | Already enforced: core imports no module. |
| 1 — foundations | orgs (+ auth, see below), storage, notifications | Tenancy, users, files, email: services every feature may need, needing nothing above. notifications moves here because orgs sends invitations through it and it depends only on Django. |
| 2 — platform | analytics, backups | Operational services used by features. |
| 3 — features | billing, blog, crm, forms, listings, social | User-facing features. |

#### The `auth ↔ orgs` cycle: three ways out

| Option | What changes | Pros | Cons |
|---|---|---|---|
| **a. Same layer, one-way** | Both in layer 1; orgs stops importing auth. auth owns the one allauth adapter and asks installed modules for a post-login redirect through a capability orgs declares (D5). `ACCOUNT_ADAPTER` points at auth's adapter. | Removes the cycle with a small change; each stays its own module. | auth still imports orgs (fine: same layer, one direction); the two remain required together. |
| b. Merge into one module | auth's user model, allauth wiring, and views move into orgs (or a new `accounts` module). | Honest about reality: they are already inseparable. | Big move: renames tables and migrations (free only before SA204), and every project's `AUTH_USER_MODEL`. |
| c. Make auth independent of orgs | auth works without orgs; org-specific account views move into orgs. | Allows a site with users but no tenancy. | Largest change; QuickScale does not offer a no-tenancy mode today. |

**Approved: a.** It fixes the cycle at the smallest cost, and (b) stays possible later.

#### Other violations and their fixes

| Today | Fix | Mechanism (D5) |
|---|---|---|
| auth → billing on account deletion | billing declares an `account_deletion_handlers` capability; auth collects it | capability |
| orgs → social cache clearing on org purge | social declares its org-scoped cache keys; orgs' purge collects them | capability |
| core `dr_engine` reads `QUICKSCALE_BACKUPS_*` | backups reads its own settings and passes a policy object to the `dr_engine` call | plain argument |
| forms → orgs undeclared | add `orgs` to forms' `required_modules` | manifest |
| forms → analytics, forms → notifications | stay (downward), through `services.py` | services |

The layer table lives in the decision and in one test-owned mapping, not in `module.yml`: a manifest
key read only by a test would break the recorded "no parsed but unprojected manifest keys" rule. D9
checks every import against it and `required_modules` against actual imports.

### D7 — Namespaces: `quickscale_<module>` everywhere — decided

| Name | Rule | Example |
|---|---|---|
| URL namespace (`app_name`) | `quickscale_<module>` | `{% url 'quickscale_orgs:invite' %}` (orgs gains one) |
| Template folder | `templates/quickscale_<module>/` | moved from `templates/quickscale_modules_<module>/` |
| Management command | `quickscale_<module>_<action>` | `purge_organization` → `quickscale_orgs_purge_organization`; `backups_create` → `quickscale_backups_create` |

Every template path, `{% url %}` name, command name, doc, and generated operator doc or script that
calls these commands changes with it.

#### D7b — The Django app label — decided: `quickscale_<module>`

Since breaking changes are allowed, the app label can join the rename. What the label controls:

- database table names (`<label>_<model>`: `quickscale_modules_blog_post`);
- migration references between modules (`("quickscale_modules_orgs", "0001_initial")`);
- `AUTH_USER_MODEL` (`"quickscale_modules_auth.User"`), content types, and permission names
  (`quickscale_modules_blog.add_post`);
- tenancy code that names tables for RLS (orgs' `tenancy.py` lists 9 such names).

| Option | Label | Pros | Cons |
|---|---|---|---|
| **1. `quickscale_<module>` (recommended)** | `quickscale_blog` | One stem for URL, templates, commands, **and** tables — D7 becomes fully consistent. Also removes the recorded-rule violation: every `db_table` override is deleted. auth's `quickscale_auth_user` is exactly what the default produces; backups' tables change from `quickscale_modules_backups_policy`/`_artifact` to the defaults `quickscale_backups_backuppolicy`/`_backupartifact`. (Sixth pass: backups also overrides `_snapshot`, and forms overrides all four of its tables; they go the same way.) | Every table, migration dependency, content type, permission, `AUTH_USER_MODEL`, and RLS table list changes. Only safe before SA204 freezes migration history — after it, a rename needs a data migration forever. |
| 2. Keep `quickscale_modules_<module>` | unchanged | No database change. | Two stems stay (`quickscale_blog:` URLs vs `quickscale_modules_blog_` tables); the custom `db_table` exceptions stay or must be renamed anyway. |
| 3. Also rename the Python package | `quickscale_blog` package and label | Everything identical, including imports. | Renames every import, split branch, wheel, `INSTALLED_APPS` entry, and the core ↔ module gate's patterns; large churn for little gain, since package names are seen only by developers. |

The rename is cheap **now** for the same reason as D1: migration history is still rewritten in place
each release (clean-break rule) and SA204 has not frozen it.

#### Folder exceptions — cannot be renamed

These two are not QuickScale names; they are paths other software looks up, so they stay regardless
of breaking changes:

- `templates/account/` in auth: django-allauth loads its pages (`account/login.html`,
  `account/signup.html`) from exactly that path; overriding them requires that folder name.
- `templates/admin/` in backups: Django's admin loads overrides from `admin/…`.

### D8 — No legacy names, no fallbacks — decided

Renames happen in one release with no aliases. `LegacyKeyAlias` is not used for these renames.

- `quickscale apply` refuses a `quickscale.yml` that uses a retired option key, and names the new key.
- A Django system check fails at startup when a project's settings define a retired setting name,
  naming the replacement.
- Code fallbacks that read a second name (like `dr_engine`'s backups fallbacks) are deleted.
- Every generated template, doc, and test uses only the new names in the same release.
- The change is made to the QuickScale codebase itself — modules, core, CLI, generator templates,
  tests, fixtures, and docs — in one pass. Projects generated from it get only the new names; an
  older project fails with messages that name every replacement.

### D9 — A conformance test enforces every rule — decided

One test suite over every `module.yml` and every module's source fails when:

- a first-party setting does not start with `QUICKSCALE_<MODULE>_` and is not in the D1 exception list;
- an option key does not equal its setting suffix in lower case, or repeats the module name;
- a boolean on/off switch does not end in `_ENABLED`, or a setting uses a suffix from D2 with the wrong type;
- a module has no `QUICKSCALE_<MODULE>_ENABLED` (unless a recorded D3 exception);
- module code reads a setting its manifest does not declare, or reads another module's setting;
- a module imports another module outside the allowed target (D5) or against the layer order (D6);
- a URL namespace, template folder, or management command does not use the D7 stem;
- a retired name from the D1 table appears anywhere in modules, core, generator templates, or docs.

- (second pass) a module's `urls.py` sets a prefix, `adapter.py` declares URL includes, a module
  mounts at `""`, or a route name is not snake_case or repeats the module (D10);
- a module base template, static folder, or template-tag library is off the D11 stem, or a module
  template emits `<html>` or fills the project's `content` block directly (D11);
- a module returns JSON outside DRF, or builds an error body itself (D12);
- `ready()` runs a check outside the core helper or catches-and-logs a configuration failure, an exception class lives outside
  `exceptions.py`, or `quickscale_core.runtime` gains a `register_*` port not listed (D13);
- a required file or required test file from D14 is missing, a model defines a `*_CHOICES` list,
  or a README lacks the D14 headings.

Each rule gets a control case proving the test rejects a violation.

### D10 — URLs: the project mounts, the module names — decided (second pass)

- The manifest's `url_includes` is the only mount; `urls.py` holds no prefix and `adapter.py`
  declares no URL include (rejected: prefix in `urls.py`, prefix in `adapter.py`).
- APIs at `<mount>api/<resource>/`, webhooks at `<mount>webhooks/<vendor>/` (rejected:
  `api/<module>/`, which needs two mounts per module).
- Route names snake_case, never repeating the module (rejected: kebab-case, which needed fewer
  renames; snake_case matches Python identifiers and Django convention).
- orgs moves entirely under `orgs/`; the site root belongs to the project (rejected: keeping orgs
  at `""` as an exception).

### D11 — Templates, static files, template tags — decided (second pass)

- One flat module base, `templates/quickscale_<module>/base.html`, owning `{% block content %}`;
  pages fill `<module>_content`. orgs, analytics, and forms gain one; orgs stops emitting `<html>`.
- Emails under `templates/quickscale_<module>/email/`.
- Static files under `static/quickscale_<module>/{css,js,img}/`.
- Template-tag libraries `quickscale_<module>`, or `quickscale_<module>_<purpose>`.

### D12 — HTTP APIs — decided (second pass)

- DRF for every JSON endpoint (rejected: plain `JsonResponse`; a mix with a shared helper).
  Reconciled with the recorded JSON API Endpoint Base Contract: its two bases stay, and
  `OrgApiBaseView` is rebased on DRF's `APIView` with its org-role logic unchanged, which avoids the
  rewrite that contract rejected. Signature-verified webhooks keep its exemption.
- Errors take one QuickScale shape, `{"error": {"code", "message", "fields"}}` (`fields` only for
  validation), produced by one generic handler in `quickscale_core.runtime` and set as
  `REST_FRAMEWORK["EXCEPTION_HANDLER"]` in the generated settings' composed `REST_FRAMEWORK` block.
  Rejected: DRF's native two shapes (no stable code, two shapes to tell apart); a third-party
  library. `drf-standardized-errors` was chosen first on the belief it produced RFC 9457; its
  format is its own (`{"type", "errors": [{"code", "detail", "attr"}]}`), and once corrected the
  maintainer chose a QuickScale-owned format, which adds no dependency and stays close to the
  `{"error"}` the theme already reads. Accepted cost: one small core handler to maintain. The
  theme's `useApi.ts` and the orgs and social pages parse the one shape.
- Session authentication only; blog's `BLOG_API_TOKENS` and its dual-auth exception are removed and
  a shared token scheme is recorded in the SA154 inventory (rejected: declaring it for blog only;
  building a shared scheme now). No project uses the tokens (checked in `bap-web` and `bap-web-new`).
- `PageNumberPagination` sized by `<THING>_PER_PAGE`; DRF throttles fed by `_RATE_LIMIT`.

### D13 — Startup checks, errors, core ports — decided (second pass)

- Module checks are functions in `checks.py`, run from `ready()` by one core helper that raises one
  `ImproperlyConfigured` listing every failure and also registers them as system checks (rejected:
  hand-written `raise` in `ready()`).
  **Correction after the choice:** option A was presented as "Django system checks in `checks.py`".
  System checks run only in `manage.py` commands, not in the WSGI server, so a pure system-check
  rule would let a misconfigured web process serve, and would break the recorded always-on RLS
  boot guard in orgs' `ready()`. The helper keeps the choice's intent (one place, every failure
  reported, testable) and still fails every process.
- Invalid configuration fails startup; an unreachable vendor is tolerated and logged (rejected:
  failing on vendor outages; today's catch-and-log of everything).
- Exceptions in `exceptions.py` under one `<Module>Error` base, re-exported by `services.py`.
- `register_backup_persistence` stays, recorded as the **core port** pattern: core defines a
  `Protocol`, exactly one module implements and registers it in `ready()`, and a missing or
  second registration fails hard; allowed ports are listed in the decision. The first reading
  ("a core entry point named after a module") was wrong: the name belongs to the DR engine's own
  domain. Rejected: an `AppConfig` capability (built for many providers, not one); passing
  persistence as an argument (about 11 internal points plus every public engine function in DR code).
  D6's fix, `dr_engine` no longer reading `QUICKSCALE_BACKUPS_*` settings, still applies.

### D14 — Package files, tests, models, README — decided (second pass)

Required files in every module: `apps.py`, `adapter.py`, `services.py` (with `is_enabled()`),
`checks.py` when it has checks, `exceptions.py` when it raises its own errors, `module.yml`,
`pyproject.toml`, `poetry.toml`, `README.md`.

- allauth's `adapters.py` becomes `allauth_adapter.py` (auth only, after D6 removes orgs' copy).
- One-off files fold into the standard ones (`contracts.py`, `helpers.py` → `services.py`;
  `constants.py` → the module using it) or become private (`_debug.py`).
- Empty packages and no-op `ready()` bodies are deleted.
- Required tests: `test_apps.py`, `test_services.py`, `test_migrations.py` when the module has
  models; tenant modules also `test_isolation.py` and `test_rls_boundary.py`.
- Model choices: the 14 tuple `*_CHOICES` lists (backups 5, forms 3, crm 2, notifications 2, blog 1,
  listings 1) become `TextChoices`/`IntegerChoices` and string literals become members. Same values
  and labels produce no migration.
- README headings, in order: Overview, Configuration, Public surface, URLs, Management commands,
  Operations, Extending. No versions in headings; the test checks headings only.

### D15 — Manifest option schema — decided (third pass)

- Every option has `type`, `default`, and `description`; a mutable option has `django_setting`, an
  immutable one has none and is read by the module's own `adapter.py` at apply time (auth's
  `authentication_method`, storage's `private_media_enabled`; the test checks that the adapter
  reads it). This is the recorded Module Manifest Architecture rule, not a new one.
- Every option whose type admits invalid values carries `validation`: integers a `range` minimum
  (`*_PER_PAGE` ≥ 1, `*_RETENTION_DAYS` ≥ 0, `*_TTL_SECONDS` ≥ 1); `*_RATE_LIMIT` the DRF rate
  pattern `^\d+/(second|minute|hour|day)$`; closed-set strings a `choices` list. Booleans and free
  text are exempt. Without this, rule 3's startup check has nothing to check.
- Decided in review (option A of two): the checks live in the per-option `validation` block (the form four
  modules already use, next to the option it checks), which core starts reading; the
  `derivation.validation_rules` list goes. Rejected: keeping `derivation.validation_rules` as the
  one form (already enforced, but far from the option and used by one module).
- Decided in review (option B of four): a check spanning options uses one of two declarative keys
  in the option's `validation` block — `required_when` and `any_of` — which cover every
  cross-option check in core and the CLI today (backups: remote mode, automation schedule,
  endpoint-or-region; storage: cloud-backend credentials). `plan`, `apply`, and the startup check
  run them from the same schema. A new kind of check needs a decision edit. Rejected: a Python
  `validate_options()` in each `adapter.py` (not visible in the manifest, not run at startup
  without extra wiring, and single-option checks could drift back into code); keeping the checks
  in core (names modules); startup-only checks in `checks.py` (found after deploy).
- Decided in review: the Module Derivation Schema decision is amended, not overridden — `module.yml`
  stays the single source; checks are authored on the option and compiled into the same
  `ValidationRule` engine. Rejected: moving checks into `derivation.option_derivations` (verbose,
  far from the option).
- Decided in review (option 1 of three): `django_setting` is the only one-to-one projection;
  `derived_settings` only for computed or transformed settings, with no default. The 25 duplicate
  `derived_settings` entries and 10 repeated defaults go. Rejected: `derived_settings` only
  (contradicts "mutable options MUST specify `django_setting`", about six lines per setting);
  keeping both with a test that they agree (duplication stays).
- Core's and the CLI's per-module option code (section 14) is removed with its `DEFAULT_*` and
  `LEGACY_*` constants and `contracts.imperative_inventory`.
- `config` always has both `mutable` and `immutable` (`{}` when empty); `dependencies` is always
  present (`[]` when empty).
- Top-level key order is not a rule (considered; cosmetic, not worth a test).

Rejected: validation in module code (duplicates the manifest, D4); a JSON-Schema file per module
(a second schema, which rule 3 forbids).

### D16 — One tenant-model base — decided (third pass): option A2

Options weighed (the tenant contract is the `organization` field, the `objects` / `all_objects`
`TenantManager` pair, and `Meta.base_manager_name = "all_objects"`):

- **A1** — every module tenant model inherits `TenantModel`; orgs still also recognizes the
  manager-only form for projects.
- **A2 (chosen)** — inheritance is the only form, for modules and projects; a `TenantManager` on a
  model that does not inherit `TenantModel` fails startup.
- **B** — delete `TenantModel`; every model spells the contract out and the test checks each piece.
- **C** — allow both forms; the test checks completeness.

Why A2: the security-critical question "is this model tenant-isolated?" gets one answer and one
code path in `tenancy.is_tenant_model`; a half-built tenant model fails startup instead of going
unenrolled; it fits rule 4 (`TenantModel` is a published extension base), rule 6 (one way), and
D17's `related_name` rule (the base's `%(app_label)s_%(class)s_set` reverse name is module-prefixed by construction);
and it is cheapest now, before the `bap-web` port (SA191) and the migration freeze (SA204).
Rejected: A1 and C keep two forms; B makes every model easy to get wrong and removes a published
base. Accepted cost: project tenant models must inherit `TenantModel` or a module base; no
project uses the manager-only form yet.

Consequences:
- billing, forms, listings (`AbstractListing`), and social (`BaseSocialItem`) move onto
  `TenantModel`; every `Meta` inherits the base's `Meta`; retyped `base_manager_name` lines go.
- blog's, billing's, forms', and listings' `related_name` overrides on `organization` go; no code
  reads those reverse accessors (checked for attribute access; ORM lookups across them must be
  checked when implementing). Abstract bases are not recorded in migrations, so the expected
  migration change is reverse names only (model state, no SQL) — confirm with
  `makemigrations --check`.
- `CreditBalance` redeclares `organization` as a `PROTECT` `OneToOneField`.
- `is_tenant_model` drops the manager branch; a new orgs check rejects a stray `TenantManager`.
- module-extension.md's project example inherits `AbstractListing` with no manager lines.
- Tenant models register on `TenantModelAdmin`, others on `admin.ModelAdmin`, both with
  `@admin.register` (already true; now enforced).

### D17 — Model basics — decided (third pass)

- Timestamps `created_at` / `updated_at`, events `<event>_at` (codifies what exists).
- Primary keys `BigAutoField`; `UUIDField` only for an identifier shown outside the site (orgs'
  public ids and tokens). Listed exception: orgs.
- References to users use `settings.AUTH_USER_MODEL` (codifies what exists).
- Every relation to a model of another module (`User`, `Organization`, another module's model) sets
  `related_name="<module>_<name>"`, plural for a foreign key or many-to-many and singular for a
  one-to-one; `+` is allowed when no reverse access is wanted. The tenant `organization` field is
  governed by D16.
- Every concrete model defines `__str__`; every concrete model defines `Meta.ordering`, except a
  singleton or one-per-parent model, which the test recognizes by a `unique` / `OneToOneField`
  scope and otherwise by a listed name.
- No translation: QuickScale ships English only and modules do not call `gettext`; `verbose_name`
  is set only when Django's default reads wrong. i18n, if ever wanted, is a separate decision.
- The literal choice-list count is 15, not 14 (see section 16); tuples derived from `TextChoices`
  members or a data catalog are allowed.

### D18 — `__init__.py` holds only the version — decided (third pass)

`__version__` and `__all__ = ["__version__"]`, nothing else. `default_app_config` is deleted from
auth, blog, crm, listings; storage's root re-export moves behind `services.py` (rule 4).

### D19 — `signals.py` sends, `receivers.py` listens — decided (third pass)

- `signals.py` holds only `Signal()` objects the module sends; it is public (rule 4).
- `receivers.py` holds the module's receivers, private, connected by importing it once in `ready()`
  (`@receiver` decorators); no `.connect()` calls in `apps.py` except for Django's own backend
  signals (`connection_created`), which orgs' RLS guard needs before any receiver module loads.
- auth's and crm's `signals.py` become `receivers.py`; orgs' receivers move to `receivers.py`.

Rejected: one `signals.py` for both — importing a sender's public signals would register another
module's receivers as a side effect.

### D20 — Management-command behavior — decided (third pass)

- Every command subclasses `BaseCommand`, writes through `self.stdout` / `self.stderr` with
  `self.style`, and reports an expected failure by raising `CommandError` — never `sys.exit()`.
- A command that deletes, anonymizes, or overwrites data (`purge`, `prune`, `anonymize`, `restore`,
  …) takes `--dry-run`, which reports what would change and writes nothing; database-only work runs
  in `transaction.atomic()`.
- Operators schedule commands; modules ship no scheduler (rejected: Celery beat or django-q, a
  core cron helper). Each command a site should schedule is listed under the README's Operations
  heading with a suggested interval. backups' `schedule` and `automation_enabled` options are
  already documentation-only and stay so.
- Applies to `backups_prune`, `forms_anonymize_submissions`, and `promote_to_saas` (gain
  `--dry-run`) and `check_tenant_isolation` (`sys.exit()` → `CommandError`).
- Decided in review (option A of three): the retired `migrate_billing_to_orgs` is deleted. Its
  2026-09-16 retirement already says current installs cannot hold the shape it repairs; it is the
  last named reason to run with RLS bypassed; `bap-web` is ported fresh (SA191), not upgraded in
  place. Rejected: adding `--dry-run` (more code for an impossible state); a listed exception.
  Accepted cost: a site still on the pre-0.86 billing shape has no in-place path, as lockstep and
  clean-break already imply.

### D21 — Package tooling and placeholders — decided (third pass)

- Every module's `pyproject.toml` has the same tool sections (`[tool.pytest.ini_options]` with
  `--cov-fail-under=90`, `[tool.mypy]`, `[tool.ruff]`); the test compares their keys, not values.
  orgs and social gain `[tool.mypy]` and fix what it reports.
  (Correction, sixth pass: this bullet rests on section 20's wrong cell. CI type-checks every module
  through the root `mypy.ini`, and a per-module `[tool.mypy]` is not read; D39 proposes the
  replacement. The pytest and ruff parts stand.)
- One `tests/settings.py` per module; extra settings files are named `tests/settings_<purpose>.py`.
- `teams/` is deleted and its README moves to `docs/planning/teams.md`, with core's placeholder
  handling (catalog entry, discovery and constraint-validation skips). Every directory under
  `quickscale_modules/` must then have a `module.yml` (rejected: listing `teams` as an allowed
  placeholder, which keeps the hand-maintained name list decisions.md already calls a smell).

### D22 — Authorization: org roles for tenant data, `is_staff` for the platform — decided (fourth pass)

Options:
- **A (chosen)** — a view or API that manages a tenant model's data authorizes by org role
  through orgs' published `permissions` (`require_org_role`, `OrgRoleMixin`, and a DRF permission
  class `HasOrgRole(min_role)` added beside them for DRF views). Each module states its minimum role
  per action in code (for example read `viewer`, write `admin`) and in its README.
  `is_staff` / `is_superuser` stay for Django admin and `operator_access` paths only; "logged in" is
  `LoginRequiredMixin` / `login_required` / DRF `IsAuthenticated`, never hand-written.
- **B** — keep `is_staff`, document that module back offices are platform-operator tools. Cheaper,
  but in `saas` mode the product cannot give a customer's admin their own blog or CRM.
- **C** — Django model permissions (`has_perm`) per module. Global like `is_staff`, so it has B's
  tenancy problem, plus a permission-assignment UI no module ships.

Why A: tenant data should be authorized by the tenant's own roles; orgs already publishes the
bases, billing already uses them, and the RLS layer stays the second line rather than the only one.
Consequences: blog, listings, crm, and forms swap their `is_staff` / `IsAdminUser` checks;
forms' `is_superuser` "see all organizations" branch moves under `operator_access`; the conformance
test rejects `is_staff`, `is_superuser`, `IsAdminUser`, and `redirect_to_login` in a module's
`views.py` except in listed operator paths. SA191 consequence: `bap-web`'s editors are given the
right org role, not staff.

### D23 — One email sender: notifications — decided (fourth pass)

Every email a module sends goes through `quickscale_modules_notifications.services.send_notification`;
auth's allauth mail is the listed exception (allauth sends it). A module that emails lists
`notifications` in `required_modules` (it is layer 1, so every sender may). forms loses its
untracked path, its `QUICKSCALE_NOTIFICATIONS_ENABLED` read, and `import_module`; `forms/notifications.py`
becomes `forms/services.py` code or private `_email.py`. When notifications is switched off
(its setting or its `NotificationSettings` row), `send_notification` raises
`NotificationDisabledError` — one behavior for every sender; a sender for which email is optional
checks `is_enabled()` first. orgs' `implies: notifications` becomes `required_modules`.
Rejected: keeping a fallback sender per module (two paths, two behaviors, rule 6's "one way").

### D24 — External effects run on commit — decided (fourth pass)

An email, analytics event, vendor call, or cache purge triggered by a database write is scheduled
with `transaction.on_commit(...)` by the code that performs the write (the service), not ordered by
hand in the view. notifications already does this; forms, orgs' invitation, and crm's bootstrap
receiver move to it. Vendor calls that must succeed *before* the write (Stripe checkout session
creation) are not triggered by a write and are exempt. The test cannot prove this statically;
it is a review rule plus one test per module that rolls back a write and asserts no effect.

### D25 — Analytics owns capture, senders own events — decided (fourth pass)

analytics publishes `capture_event(*, distinct_id, event, properties)` only. Each module names its
events in its own `services.py` as `<module>_<event>` in snake_case (`forms_submitted`) and calls `capture_event` guarded as rule 4 requires. `capture_form_submit`,
`capture_social_link_click` (no caller), and the two feature names in `analytics/events.py` go; `$pageview`
stays (PostHog's name). Event names are recorded in each module's README under Public surface —
a renamed event breaks dashboards, so it is a release-note item like a moved URL (rule 7).
This renames one live event (`form_submit`; `social_link_click` is never sent); accepted because no deployed site depends on
them yet (SA191 has not landed).

### D26 — `services.py` declares its surface — decided (fourth pass)

- `services.py` defines `__all__`; the conformance test treats exactly that list as the module's
  public surface (rule 4) and rejects a cross-module import of a name not in it.
- Public service functions take keyword-only arguments after at most one leading subject
  (`send_notification(*, template_key, recipients, context)` already does), so adding a parameter never breaks a
  caller silently.
- A service that cannot do what it was asked raises the module's `<Module>Error` (rule 10); the
  "is this optional thing on and configured?" question is `is_enabled()`, so callers no longer rely
  on swallowed failures. analytics' capture stays best-effort by design (a vendor outage must not
  break a request) and says so in its docstring — the one listed exception.

### D27 — Small leftovers — decided (fourth pass)

- backups and blog gain `py.typed`; rule 11's file list adds it. (Correction, sixth pass: both
  already ship it, so this is a no-op; keeping it in rule 11's list costs nothing.)
- The current time is `django.utils.timezone.now()`; storage's `datetime.now(tz=...)` changes.
- Cache keys are `quickscale_<module>:<name>` and join rule 2's identity table (social's
  `quickscale_modules_social:*` renames; the cache is disposable, so no migration step).

### D28 — Constraint and index names carry the stem — decided (fifth pass)

Every `UniqueConstraint`, `CheckConstraint`, and `Index` has an explicit `name`:
`quickscale_<module>_<model>_<purpose>` for a constraint (`quickscale_blog_post_slug_org_unique`),
at most 63 characters (PostgreSQL's limit). An `Index` name is limited to 30 characters by Django,
too short for the stem, so an index is `qs_<module>_<model>_<field>_idx`, abbreviated to fit, and the
test checks the `qs_<module>_` prefix only. `unique_together` becomes a `UniqueConstraint`.
Rejected: keeping Django's generated names (they already change with rule 2's app label, and
say nothing), and a `<module>_` prefix without the stem (it can collide with a project app of the
same name, the reason rule 2 exists). Names are fixed in each module's clean-break `0001_initial`,
so the rename costs no migration step before §Clean-Break Migration History freezes.

### D29 — Inbound webhooks: one shape — decided (fifth pass)

- A webhook is a DRF `APIView` with empty `authentication_classes`, `permission_classes`, and
  `throttle_classes` (the generated settings set default throttles), mounted at `<mount>webhooks/<vendor>/` (rule 7). It reads `request.body` and passes it
  with the signature headers to one `services.py` function; the view holds no logic. Being a DRF
  view, its errors take rule 9's shape through the one handler, which replaces both `{"error": str}`
  bodies. The JSON API Endpoint Base Contract's webhook exemption narrows to "no authentication
  class": the signature is the authentication.
- The service verifies the signature (the vendor's SDK, else `hmac.compare_digest` with a timestamp
  window) before parsing, and records each provider event under a unique database key, so a
  replayed event is a no-op answered `200`.
- Status codes: `200` accepted or duplicate (body `{"status": "accepted", "duplicate": <bool>}`, no
  more); `400` bad signature or malformed payload (`code` `webhook_signature_invalid` /
  `webhook_payload_invalid`); the module off is `404`, because rule 1 disables its URLs. A missing
  webhook secret fails startup through `checks.py` (rule 10) instead of a per-request `500`.
- Effects of a webhook's writes follow rule 21 (on commit).

Rejected: keeping plain Django views with a hand-written shape (a second error format, against
rule 9), and 403 for a bad signature (a provider retries any non-2xx the same way, so 403 buys
nothing, and a signature is a property of the request, not a permission).

### D30 — `on_delete` on `User`: `SET_NULL`, no `PROTECT` — decided (fifth pass): option B

Module Conventions rule 27: a relation to `User` is `SET_NULL`; `CASCADE` only on the listed rows
(membership, invitation sender, author profile, as § Multi-tenant SaaS Architecture records);
`PROTECT` is no longer allowed, because the first module to use it would make account deletion fail
for every site that installs it. A record that must outlive its user is kept by the module's SA213
removal obligation instead. No model uses `PROTECT` today, so the only change is the SA35 gate's
allowed set. Rejected: A (keep `PROTECT` allowed) and C (no `CASCADE` allowlist, leaving empty
memberships and profiles). Whether users are deleted at all or disabled and anonymized is a
separate product question, not part of this decision.

### D31 — Allowed file names in a module package — decided (fifth pass)

A module package holds rule 11's required files, rule 10's `checks.py` / `exceptions.py`, rule 16's
`signals.py` / `receivers.py`, the Django and DRF names (`models`, `views`, `urls`, `admin`, `forms`,
`serializers`, `managers`, `filters`, `feeds`, `middleware`, `validators`, `throttles`,
`permissions`, `templatetags/`, `management/`, `migrations/`), `templates/` and `static/` (rule 8),
rule 4's listed foundation surface
files, and private files named `_<name>.py`. The listed extras are backups' `persistence.py` (the
core port) and orgs' `debug_views.py` (DEBUG-only; `debug_helpers.py` becomes `_debug.py`). The test
rejects any other name, so a new public-looking file needs a decision edit. analytics' `events.py`
goes with D25.

### D32 — Tests are named by what they protect — decided (fifth pass)

- A test file is `test_<subject>.py`, named for the behavior or unit it covers; the file name and
  docstring describe what it protects and carry no ticket number; the history is in git. The
  same holds for docstrings and comments, and the conformance test checks all three; SA215 sweeps the
  747 existing mentions in 103 test files, rewording each to say what the test protects where the
  ticket number was the only explanation (orgs' eight `test_sa*` / `test_af*` files are renamed, e.g.
  `test_sa92_migration_squash_guardrail.py` → `test_migration_squash_guardrail.py`).
- Non-test files in `tests/` are `conftest.py`, `settings*.py` (rule 18), `urls*.py`, and helpers
  named `_<name>.py`; a test Django app is a package named `<purpose>_app/` (orgs'
  `sa182_project_app` → `project_tenant_app` (project-owned tenant models for purge ordering) and
  `sa208_project_app` → `provider_id_app` (provider-ID classification).
- auth's and billing's `test_circular_import.py` stay: they guard import order against allauth and
  Stripe, which rule 5's layer check between modules does not see.

### Sixth pass — decided (D33–D42)

Status: **decided** 2026-09-28, as decisions.md rules 30–39 (D36 as option B, the others as the
recommended option). Ranked by cost class (defect > collision > ambiguity > tax), then by how many
modules diverge × their churn (commits in the last 12 months, merges and subtree splits excluded:
orgs 118, crm 104, blog 101, forms 74, billing 73, backups 72, listings 70, auth 69, social 51,
notifications 35, storage 32, analytics 27; bulk sweeps are included, so read these as relative
figures). Every "Enforcement" line is a clause of the rule 40 test (rule 30 when these were
written), or a check inside existing code, not a new gate. The roadmap folds the work into
SA219–SA227.

### D33 — One writer per shared setting key — decided

- **ID:** `shared-setting-writes` · **Aspect / population:** A, settings written by module wiring;
  12 modules (section 32).
- **Drift:** two keys have two writers today, and the winner depends on alphabetical order. The
  first second writer of `REST_FRAMEWORK` wipes billing's throttle rates.
- **Cost class:** collision; latent defect (billing's throttled views raise `ImproperlyConfigured`
  once another module contributes `REST_FRAMEWORK`, reachable when rule 9 lands).
- **Declared rule:** none; rule 1's exception list covers option settings, not wiring settings.
- **Options:**
  - **A.** `collect_wiring` fails `apply` when two modules write one key with different values, and
    deep-merges a listed set of dict settings (`REST_FRAMEWORK`), failing on a sub-key clash.
    Small core change; D6 already removes orgs' `ACCOUNT_ADAPTER`.
  - **B.** Modules may write only `QUICKSCALE_<MODULE>_*` keys, and the generator owns every Django or
    third-party key. This puts per-module knowledge in core, against § Module Wiring Authority.
  - **C.** Status quo plus a note. The latent defect stays.
- **Decided rule (A, as recommended):**
  - ✅ A module's wiring may write a key another module also writes only with an equal value. For
    `REST_FRAMEWORK`, core merges the sub-dicts, and two modules may not set the same sub-key.
  - ❌ Relying on module-name order to decide a setting's value.
- **Enforcement:** in `collect_wiring` itself, closed-world (any conflicting second writer fails
  `apply`, naming both modules and the key). Control case: two specs writing `ACCOUNT_ADAPTER`
  differently.
- **Migration:** core; orgs drops `ACCOUNT_ADAPTER` (D6); blog and listings keep equal markdownx
  values or one owns them. No persisted names change.
- **Confidence:** High for the merge semantics (read `collect_wiring` and base.py.j2). Medium for
  the key list, which comes from grep; keys computed at runtime in an adapter were not traced.
- **Hand-off:** tech (latent defect), arch (core's merge semantics are the boundary).

### D34 — The theme's module flag means "enabled" — decided

- **ID:** `theme-module-presence` · **Aspect / population:** P; 12 modules as the theme sees them
  (section 33).
- **Drift:** "true" means installed for 10, enabled for 1, absent for orgs; three mounts
  hard-coded.
- **Cost class:** ambiguity; latent defect (navigation to a 404 once rule 1's switch exists).
- **Declared rule:** Frontend Theme Source De-Specialization (keep the seam), rules 1 and 7.
- **Options:**
  - **A.** The generator renders `index.html.j2`'s flags from the discovered module set: each
    module's flag is `installed and QUICKSCALE_<MODULE>_ENABLED`, and each module's path comes from
    reversing one of its URL names when it is installed. Nobody writes a per-module line.
    (Correction at review: the first wording said "one loop over installed apps", but the seam
    validator requires a key for every shipped module, present as `false` when absent, so the set
    must be the discovered one, not the installed one.)
  - **B.** Keep per-module lines and switch each to the `_ENABLED` setting. Still a list in core.
  - **C.** Status quo.
- **Decided rule (A, as recommended):**
  - ✅ The seam reports, per shipped module, whether it is installed and enabled (rule 1) and where
    it is mounted (rule 7), rendered from discovery. The theme's TypeScript (the `QuickScaleModules`
    type, the seam validator, the SPA pages) keeps naming its modules, as frontend.md § Module
    frontend surfaces records.
  - ❌ Hand-written per-module lines or `INSTALLED_APPS` tests in `index.html.j2`; mount paths as
    literals.
- **Enforcement:** rule 40 clause, closed-world: the seam producer contains no hand-written
  `quickscale_modules_<name>` test and no mount literal. Control case: re-add the `crm` line.
- **Migration:** the theme's `index.html.j2`. The generated `templates/index.html` is user-owned
  (category U3 in generated_file_ownership.md) and `quickscale update` never rewrites it, so only
  new projects get the change. Existing projects need a release-note step, the same one rule 1's
  switch needs. Theme types unchanged. Rides SA219.
- **Confidence:** High (template read in full).
- **Hand-off:** tech, when rule 1 lands.

### D35 — Throttle scopes and rates — decided

- **ID:** `throttle-scopes-and-rates` · **Aspect / population:** A and H; the 3 modules with
  throttled endpoints (section 34).
- **Drift:** three mechanisms, two scope shapes, one hard-coded rate, one raw-SQL table outside the
  ORM.
- **Cost class:** collision (scopes share DRF's rate table and cache keys with the project); tax.
- **Declared rule:** rule 9 (DRF throttles fed by `_RATE_LIMIT`), rule 1 (`_RATE_LIMIT`); scope names
  have no rule.
- **Options:**
  - **A.** Scope `quickscale_<module>_<purpose>`. Every rate comes from a `_RATE_LIMIT` option,
    contributed as `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]` through D33's merge. blog's counter table
    and `RunSQL` go with its hand-written limiter.
  - **B.** Scope `<module>_<purpose>` (billing already conforms). Shorter, but it has rule 25's
    collision reason against it.
  - **C.** Leave scopes free; only fix billing's hard-coded rate.
- **Decided rule (A, as recommended):**
  - ✅ A DRF throttle scope is `quickscale_<module>_<purpose>`, its rate is the module's
    `_RATE_LIMIT` option, and it joins rule 2's identity table.
  - ❌ A rate written in code or `adapter.py`; a module table created by `RunSQL`.
- **Enforcement:** rule 40 clause, closed-world: every `throttle_scope` / `scope` string has the
  stem, and `DEFAULT_THROTTLE_RATES` values in an adapter come from a setting. A `RunSQL` that
  creates a table fails outside a listed exception. Control case: `scope = "form_submit"`.
- **Migration:** billing (new option `checkout_rate_limit` or one `api_rate_limit`), forms, blog.
  The table drop rides blog's clean-break `0001_initial`. Throttle counters are disposable.
- **Confidence:** High.
- **Hand-off:** none.

### D36 — The stem everywhere — decided: option B

- **ID:** `namespace-prefix-principle` · **Aspect / population:** A; the shared namespaces of
  section 35 (rules 2, 14, 22, 24, 25).
- **Drift:** rule 25 rejects `<module>_` for collision; rules 14 and 22 adopt it.
- **Cost class:** ambiguity (two precedents for the next namespace); collision for event names.
- **Declared rule:** rules 2, 14, 22, 25. This is raised because the rules' own rationales
  contradict each other, which § 0's "do not re-litigate" allows.
- **Options:**
  - **A.** A principle in rule 2: a name in a namespace the project shares uses the
    `quickscale_<module>` stem when a clash would be **silent**. The shorter `<module>_` is allowed
    where Django or PostgreSQL rejects a clash **loudly**. Reverse accessors keep `<module>_`
    (Django's check fails at startup). Event names become `quickscale_<module>_<event>`.
    Throttle scopes take the stem (D35).
  - **B.** The stem everywhere, including reverse accessors (`user.quickscale_blog_posts`). Uniform,
    verbose in every ORM query.
  - **C.** Keep the rules as they are, and record why events differ.
- **Recommended:** A. **Decided: B** (the maintainer chose one uniform rule over the shorter
  accessors), recorded as rule 33:
  - ✅ Every name a module places in a namespace shared with the project or other modules carries
    `quickscale_<module>`, and rule 2's table lists the namespace: reverse accessors
    (`quickscale_blog_posts`, rule 14), events (`quickscale_forms_submitted`, rule 22), throttle
    scopes (rule 32). Exceptions: names another program fixes (`$pageview`, `account/`, `admin/`)
    and index names, which Django caps at 30 characters (`qs_<module>_…`).
  - ❌ A new shared namespace without an entry in rule 2's identity table.
- **Enforcement:** rule 40's clauses per namespace (`related_name`, event names, throttle scopes);
  a new namespace is a review rule (it needs a decision edit).
- **Migration:** every `related_name` on a relation to another module's model (SA222; backups,
  billing, blog, crm, forms, orgs, with their callers) and the one live event, whose D25 rename
  now targets `quickscale_forms_submitted` (SA226). Applying the rule also renames orgs' one
  schema-wide database function (`qs_child_parent_org_equality` →
  `quickscale_orgs_child_parent_org_equality`, SA221's clean-break migrations) and billing's
  advisory-lock key strings (SA223; transient). Tenant `organization` reverse names are stemmed by
  construction once rule 2 renames the labels.
- **Confidence:** High for the table.
- **Hand-off:** none.

### D37 — Layers cover references by name — decided

- **ID:** `upward-name-references` · **Aspect / population:** C; 12 modules and rule 5's layer
  table (section 36).
- **Drift:** orgs (layer 1) names billing, blog, crm, and social in shipped source. blog reaches
  storage outside its public surface. None of this is an import.
- **Cost class:** ambiguity (billing's plan vocabulary is interpreted in orgs); tax (a new tenant
  module edits orgs).
- **Declared rule:** rule 5 (imports), rule 4 (public surface, capabilities for upward needs),
  § Multi-tenant SaaS Architecture (the registry is a CI oracle only).
- **Options:**
  - **A.** Rule 5 covers every reference to another module (import, `import_module`, app label,
    `apps.get_model`, `is_installed`). Then:
    - `require_org_feature` moves to billing's surface (billing publishes the plan-feature gate);
    - purge's billing branch and `BOUNDARY_GUARDED_OBLIGATIONS` become billing's removal
      declarations (the SA213 pattern);
    - `TENANT_TABLE_REGISTRY` moves into test code, or each module declares its tables on its
      `AppConfig`;
    - blog calls storage's `services.py` and lists storage in `required_modules`.
  - **B.** Record orgs as the tenancy kernel that may name modules, with an allowlist. Cheap, but
    it keeps the list in orgs.
  - **C.** Move only the registry.
- **Decided rule (A, as recommended):**
  - ✅ A module refers to a higher-layer module only through a capability that the higher module
    declares, whether by import or by name.
  - ❌ App labels, model names, or package names of a higher-layer module in a module's source.
- **Enforcement:** rule 40 clause, closed-world: a string search for every other module's package
  and app label in each module's `src/`, allowed only for a lower layer or one way within a layer, with
  migrations excepted. Control case: orgs' `require_org_feature` line.
- **Migration:** orgs, billing, blog. `require_org_feature` is public, so the move is a
  release-note item.
- **Confidence:** High for the table (every reference opened). Medium that the registry can move
  to tests, because its CI-oracle role was not traced into the gate that reads it.
- **Hand-off:** arch.

### D38 — Secrets reach code as settings — decided

- **ID:** `secret-resolution-path` · **Aspect / population:** B and I; the 5 modules with
  `_ENV_VAR` options (section 37).
- **Drift:** three resolution paths for one suffix, and a missing API key is found at different
  moments.
- **Cost class:** ambiguity; tax.
- **Declared rule:** rule 1 (`_ENV_VAR` holds a name), rule 3 (values only through `apply`, no code
  defaults), rule 26 (webhook secret at startup).
- **Options:**
  - **A.** The storage path for all. `apply` renders each secret as an environment read in
    `settings/modules.py` (core's existing `__QS_ENV__` mechanism), and module code reads the
    setting. A `checks.py` check (rule 10: "what options cannot express") fails startup when a
    secret the switched-on module needs is empty; the secret is not an option, so the option
    schema's `required_when` cannot express it. This fits rule 3 as decided. Secret values then sit in
    `django.conf.settings`, where Django's error reporter hides names containing `KEY`/`SECRET`/`TOKEN`;
    name the settings to match.
  - **B.** One core helper `runtime.read_secret(setting)` called at use. It is close to the "runtime
    accessor" that rule 3 rejects.
  - **C.** Leave resolution to each module, documented.
- **Decided rule (A, as recommended):**
  - ✅ A secret reaches module code as a setting that `apply` renders from the environment variable
    its `_ENV_VAR` option names; a required secret that is empty fails startup.
  - ❌ `os.getenv` / `os.environ` in module code (the listed exception: orgs' RLS boot guard reads
    core's runtime-role variables, which exist before settings load), or a default variable name
    written in code.
- **Enforcement:** rule 40 clause, closed-world: no `os.getenv` / `os.environ` in `src/` outside the
  listed orgs reads. Control case: analytics' `resolve_posthog_api_key`.
- **Migration:** analytics, billing, notifications, backups (with D6's `dr_engine` fix); storage
  already conforms.
- **Confidence:** High (all five paths read).
- **Hand-off:** none.

### D39 — One type-check configuration — decided

- **ID:** `type-check-config` · **Aspect / population:** N; 12 modules (section 38). This supersedes
  D21's mypy bullet.
- **Drift:** strictness runs from none relaxed to twelve codes off. The rule asks for a section that
  CI does not read.
- **Cost class:** ambiguity (rule 18 contradicts the authoring guide and cannot be enforced as
  written); orgs is the least checked.
- **Declared rule:** rule 18 (`[tool.mypy]` per module) against module-extension.md step 1.3 (a
  section in the root `mypy.ini`). The two contradict each other, which is why this item is raised.
- **Options:**
  - **A.** The root `mypy.ini` is the only type-check configuration, as module-extension.md
    already says. A module's section may relax only the guide's standard override, and the
    per-module `[tool.mypy]` sections are deleted. orgs, social, forms, notifications, and billing
    fix what the tightened sections report.
  - **B.** Move to per-module `[tool.mypy]` and change `make typecheck` to run inside each module
    directory. This is closer to D21 as written, but repeats the root options twelve times.
  - **C.** Status quo, rule 18 amended to drop the mypy requirement.
- **Decided rule (A, as recommended):**
  - ✅ Every module has a section in the root `mypy.ini` that relaxes at most module-extension.md's
    standard override (`disallow_untyped_defs`, `warn_return_any`, `warn_unused_ignores`,
    `var-annotated`).
  - ❌ A per-module `[tool.mypy]`, or a disabled error code outside the list.
- **Enforcement:** rule 40 clause, closed-world: parse `mypy.ini`; each discovered module has a
  section; disabled codes ⊆ the allowed set. Control case: orgs' current section.
- **Migration:** orgs (twelve codes: real typing work), social, forms, notifications, billing;
  delete the unread `[tool.mypy]` blocks in blog, listings, and storage; amend rule 18. No
  persisted names.
- **Confidence:** Medium. mypy's config lookup was read from the Makefile and mypy's documented
  order (a `mypy.ini` in the working directory wins), not observed by running mypy.
- **Hand-off:** none.

### D40 — Module lists derive from discovery — decided

- **ID:** `module-lists-outside-members` · **Aspect / population:** L and N; the ten lists of
  section 39.
- **Drift:** ten hand-kept lists of 5 to 13 names. None of them fails when a module is missing.
- **Cost class:** tax (adding a module edits about nine files outside it); ambiguity (two
  descriptions per module).
- **Declared rule:** CLI discovery-derived modules; § Module Presence States; D21 ("a hand-maintained
  name list … a smell").
- **Options:**
  - **A.** Each list is computed from discovery (`quickscale_modules/*/module.yml`) plus a fact the
    module states about itself: tenant models from `TenantModel` subclasses; descriptions from
    `module.yml`; theme flags per D34. Where a list must exclude a module, the exclusion sits next
    to the derivation with its reason.
  - **B.** Keep the lists and add one parity test that each equals discovery minus listed
    exclusions.
  - **C.** Status quo.
- **Decided rule (A, as recommended):**
  - ✅ Code outside `quickscale_modules/` that needs the set of modules computes it from discovery.
  - ❌ A literal list of module names outside a module, except the theme's TypeScript module
    surfaces (D34), rule 5's layer table, and rule 40's
    test-owned mapping.
- **Enforcement:** rule 40 clause, closed-world: a string search for three or more module names
  in one literal, over core, CLI, scripts, and theme, with the two named exceptions. Control
  case: `render_j2_template._all_modules`.
- **Migration:** core catalog (descriptions from `module.yml`), five scripts, theme (D34),
  orgs registry (D37), the page-style contract (with rule 8). Social joins the isolation gates.
- **Confidence:** High for the table. Medium on completeness: lists were found by names appearing
  together, so a list without `crm` in it could be missed.
- **Hand-off:** arch (the population is declared in ten places).

### D41 — README content, not only headings — decided

- **ID:** `readme-content-accuracy` · **Aspect / population:** O; 12 READMEs (section 40).
- **Drift:** 13 options and 8 commands appear in no README, and rule 11's check cannot see it.
- **Cost class:** tax (operators read the manifest instead).
- **Declared rule:** rule 11 ("Configuration (every manifest option)"; "the test checks the
  headings only").
- **Options:**
  - **A.** The rule 11 clause also checks that each option key and each management command name
    appears in the README. It is closed-world and cheap.
  - **B.** Generate the Configuration and Management commands sections from the manifest and the
    commands.
  - **C.** Headings only, as decided.
- **Decided rule (A, as recommended):**
  - ✅ Every manifest option key appears under Configuration, and every management command under
    Management commands.
- **Enforcement:** rule 40 clause. Control case: notifications' README.
- **Migration:** notifications, billing, storage, backups, orgs. Documentation only.
- **Confidence:** High. The match is a substring anywhere in the README, so the count is a floor.
- **Hand-off:** none.

### D42 — `required_modules` is bare names and selects them — decided

- **ID:** `manifest-dependency-spec` · **Aspect / population:** C; the 7 manifests with
  dependencies (section 41).
- **Drift:** version floors that lockstep makes meaningless; `implies` paired with
  `required_modules` in five of six orgs dependants.
- **Cost class:** ambiguity; tax.
- **Declared rule:** § Module Version Lockstep ("no independent module versions"); rules 5 and 20
  (what `required_modules` must list).
- **Options:**
  - **A.** `required_modules` lists bare names; `plan` and `apply` select required modules
    automatically; `implies` is removed (after rule 20 its only non-duplicate use is gone), and the
    floor parser goes.
  - **B.** Keep both keys and require every required module to be implied.
  - **C.** Status quo.
- **Decided rule (A, as recommended):**
  - ✅ `required_modules: [orgs]`; a required module is selected with its dependant.
  - ❌ Version specifiers on first-party modules; `implies`.
- **Enforcement:** the manifest loader rejects a specifier or an `implies` key, closed-world.
  Control case: `orgs>=0.86.0`.
- **Migration:** 7 manifests and their copies under `quickscale_core/data/manifests/`, core loader,
  CLI plan and apply. Whether `quickscale.yml` or `.quickscale/state.yml` records implied modules
  was not checked.
- **Confidence:** Medium. `plan`'s behavior for blog without orgs was inferred from the
  manifests, not run.
- **Hand-off:** none.

## Seventh pass — drift items (proposed D43–D48)

Ranked per §6: cost class, then members × churn (non-merge commits per module directory since
2025-10-03, bulk sweeps not excluded: orgs 165, crm 128, blog 125, billing 105, forms 100, auth
98, listings 91, backups 88, social 71, notifications 62, analytics 46, storage 46), then the reset
point. SA204's migration freeze and SA191's `bap-web` port are the next one-way doors, and both
wait on SA215. **The audit proposes these and does not decide them.** Each is `open` until the
maintainer records a decision.

### Item 1: URL paths — `mount-path-copies` (D43)

- **Aspect / population:** A (shared namespace: URL paths), with H. Population: the 10 modules
  with URL mounts, plus the host project's generated `urls.py`, the theme templates, and orgs'
  middleware.
- **Table:** section 45.
- **Drift:** the generated shell routes claim `blog/`, `listings/`, `forms/`, and `crm/` before
  the modules' own mounts, and four places repeat module paths as literals.
- **Cost class:** collision (blog's and listings' index URLs are served by the shell); tax (four
  hand copies of a manifest value).
- **Declared rule:** rule 7 ("the only place"); rule 37 (the shell regex is a module list);
  frontend.md § URL ownership contradicts the code for module indexes.
- **Options:**
  - **A.** Shell routes come from discovery. Each module with a React surface declares its SPA
    routes in its manifest (`spa_routes`, beside `url_includes`), and the generator renders them
    *after* the module's own includes, or not at all when the module is absent or off. Cost: a
    manifest key, a template change, release notes (user-owned `urls.py`, as rule 31's U3 note).
  - **B.** Keep the shell list in `urls.py.j2` as a listed rule 37 exception, but anchor each
    entry so it cannot match a module's mounted root: drop the `/?` that matches `blog/`, or
    move the React pages to a non-mount path (`/app/blog`). Cost: a URL move for the React pages,
    which is one-way once `bap-web` ports.
  - **C.** Accept the shadowing: the React page *is* the index, and the module's `post_list` and
    `listing_list` become API- or embed-only. Cost: delete or rename the shadowed views, and fix
    frontend.md.
- **Recommended rule (A):**
  ✅ A path that serves a module's UI, whether server-rendered or a React shell route, is declared
  by that module's manifest and rendered by the generator from the discovered, installed, and
  enabled set. Route names in the project namespace for module pages are
  `quickscale_<module>:<name>` (rule 2).
  ❌ A module path written as a literal in generator templates, theme templates, or another
  module's code. ❌ Two routes that resolve the same path.
  Exception: orgs' `TenantMiddleware` path guards read the resolved prefixes from orgs' own URL
  names rather than literals.
- **Enforcement:** rule 40 clause, closed-world. Extend rule 37's and rule 7's detectors to
  `generator/templates/**/*.j2`. Add a generated-project test that every module's root URL name
  resolves to its own view (`resolve(reverse(...)).func`). Control case: a `^blog/?$` shell route
  fails it.
- **Migration:** generator and theme; user-owned `urls.py` gets a release-notes step. Rides
  SA215, before SA191 ports `bap-web`.
- **Confidence:** High for the table and the shadowing: the patterns were run against the paths,
  and urlpatterns order was read in the template. Medium on intent: whether the blog index is
  meant to be reachable is the team's call (question 1).
- **Hand-off:** tech (whether blog's and listings' server indexes are reachable in a React-theme
  project).

### Item 2: Settings snapshots — `settings-snapshot-readers` (D44)

- **Aspect / population:** B. Population: modules (12).
- **Table:** section 42.
- **Drift:** five modules hold a typed settings object in three shapes and four locations; seven
  read settings at the point of use.
- **Cost class:** ambiguity (rule 3's ❌ "per-module settings readers" against five modules that
  cite rule 3 as their licence); tax (the next module picks a form).
- **Declared rule:** rule 3.
- **Options:**
  - **A.** Allow one snapshot form: a private `_settings.py` with a frozen dataclass and a
    `from_settings()` classmethod, no defaults and no coercion, never in `__all__`. Rule 3's ❌
    is reworded to "a reader that defaults or coerces". Migration: move analytics' and social's
    classes, rename backups' builder, drop billing's, notifications', and backups' classes from
    `__all__`, and give orgs `notifications.services.is_enabled()` instead.
  - **B.** Forbid snapshots and read at the point of use (the seven modules' form). Migration: 5
    modules, about 30 call sites. The snapshots exist to pass one consistent view through lock
    waits (billing) and DR calls (backups), so B loses that.
  - **C.** Keep the current variety and say so. Rejected: it fails gate 4, because no rule.
- **Recommended rule (A):**
  ✅ A module that needs a consistent view of several of its settings builds it in its private
  `_settings.py` as a frozen dataclass with `from_settings()`, reading each setting directly with
  no default or coercion. ✅ It stays private; callers outside the module ask `is_enabled()` or a
  `services.py` function.
  ❌ A settings object in `services.py`, `__all__`, or another file; a snapshot that defaults,
  coerces, or reads another module's settings.
- **Enforcement:** rule 40 clause, closed-world. Any class with a `from_settings` method, or any
  function returning a dataclass built only from `settings.` reads, must live in `_settings.py`
  and be absent from `__all__`. Control case: `AnalyticsRuntimeSettingsSnapshot` in `services.py`
  fails.
- **Migration:** analytics, backups, billing, notifications, social; orgs' caller (Item 3).
- **Confidence:** High. Every snapshot was read, and `from_settings` callers were counted by
  module (analytics 3, backups 5, billing 14, notifications 4, orgs 1).

### Item 3: Optional senders — `optional-sender-guard` (D45)

- **Aspect / population:** C (with F). Population: modules that send email through notifications
  (2: forms, orgs; auth's allauth mail is the listed exception).
- **Table:** section 43.
- **Drift:** orgs reads notifications' settings snapshot; forms catches every exception; rule 20
  prescribes `is_enabled()`. Rules 3 and 20 describe a runtime row the code no longer has.
- **Cost class:** ambiguity.
- **Declared rule:** rules 4, 10, 20; rule 3's database-backed-settings bullet.
- **Options:**
  - **A.** Apply rule 20 as written. Both senders call `notifications.services.is_enabled()`
    before sending. forms catches only `NotificationError` (its declared, best-effort case) and
    lets configuration errors raise. Reword rules 3 and 20: the row mirrors settings and is not a
    switch.
  - **B.** Restore the row as a runtime switch (an operator toggle without redeploy), and make
    `is_enabled()` read setting and row. This is a behavior change, and it reopens rule 3's
    "values reach a running site only through apply".
- **Recommended rule (A):**
  ✅ A sender guards an optional module with `apps.is_installed(...)` and that module's
  `services.is_enabled()`, and catches only that module's `<Module>Error` where its failure is
  tolerable. ❌ Reading another module's settings object; `except Exception` around another
  module's service call.
- **Enforcement:** rule 40 clause, closed-world. A cross-module attribute access whose name
  contains `Settings` or `Snapshot` fails, as does a bare `except Exception` in a function that
  calls another module's `services`. Control case: orgs' current line.
- **Migration:** forms `_email.py`, orgs `views.py`; decisions.md rules 3 and 20 text.
- **Confidence:** High. Both senders, the snapshot, the row sync, and the admin were read.

### Item 4: Role checks — `org-role-check-copies` (D46)

- **Aspect / population:** E. Population: tenant modules (6).
- **Table:** section 44.
- **Drift:** billing's service re-check copies orgs' role check with a string role and an extra
  `is_active` test.
- **Cost class:** ambiguity (two role checks that agree today and need not tomorrow).
- **Declared rule:** rule 19 ("there is one role check"); rule 11 (code compares against
  `TextChoices` members, not string literals).
- **Options:**
  - **A.** billing calls `user_has_org_role(user, org, OrgRole.OWNER)` and adds `is_active` at
    the call site if it is wanted.
  - **B.** Add `is_active` to orgs' helper so that every role check refuses inactive users. That
    is a behavior change across every module, so hand it to tech before choosing.
- **Recommended rule (A):** ✅ Every org-role decision, in a view or a service, calls orgs'
  `user_has_org_role` (or a helper built on it) with an `OrgRole` member. ❌ Filtering
  `OrganizationMembership` by `role=` outside orgs.
- **Enforcement:** rule 40 clause. An `OrganizationMembership` query with a `role` keyword in a
  module other than orgs fails. This is open-world on the query spelling, so it is also a review
  rule. Control case: billing's line 158.
- **Migration:** billing, one function.
- **Confidence:** High. Every `role=` literal and `OrgRole.` use in `src/` was counted (1
  literal; `OrgRole` members in 7 modules).

### Item 5: Stub exemptions — `mypy-overrides-unread` (D47)

- **Aspect / population:** N. Population: modules (12).
- **Table:** section 47.
- **Drift:** 10 modules carry `[[tool.mypy.overrides]]` that CI never reads. The harness exempts
  them without a listed exception.
- **Cost class:** ambiguity; tax.
- **Declared rule:** rules 36 and 40 (exceptions live in the test-owned mapping that mirrors the
  decision).
- **Options:**
  - **A.** Delete the blocks, add `anymail` to the root `mypy.ini` if mypy needs it, and drop the
    harness's `overrides` exemption.
  - **B.** Keep them for running mypy inside a module directory, and list the exemption in rule
    36 with the requirement that each block equal the root's entries. Cost: two copies kept in
    step.
- **Recommended rule (A):** ✅ Third-party stub exemptions live in the root `mypy.ini` only.
  ❌ Any `[tool.mypy]` table, `overrides` included, in a module's `pyproject.toml`.
- **Enforcement:** rule 36's detector stops skipping `overrides` (closed-world). Control case:
  analytics' block.
- **Migration:** 10 `pyproject.toml` files; possibly one root `mypy.ini` line.
- **Confidence:** High. Every block and every root section was read. Whether CI needs `anymail`
  was not run (read-only audit).

### Item 6: Split facades — `split-facade-conventions` (D48)

- **Aspect / population:** L (with K). Population: the split facades (10 files in auth, backups,
  billing, notifications, orgs) and every future split.
- **Table:** section 46.
- **Drift:** three private-file naming forms, two re-export policies, and two log-channel
  policies. Rule 19's scan depends on the naming form.
- **Cost class:** tax; ambiguity (log channels and rule 19 coverage).
- **Declared rule:** rule 28 (names only); none for re-exports or loggers. The arch audit records
  that no decision states the patch-through-facade contract.
- **Options:**
  - **A.** Name by facade (`_<facade>_<part>.py`, so views are always `_views_<part>.py`), make
    re-export publics only, make tests patch the private module where the code lives, and give
    every logger in a split module the facade's channel. Cost: rename the private files that
    do not already follow the form, and re-point the tests that patch through facades (string
    targets: backups 24, orgs 4, notifications 2, auth 1; `patch.object` targets not counted).
  - **B.** Keep each module's naming, but make rule 19 scan by content (any class that subclasses
    a Django or DRF view, or any function taking `request`) rather than by file name, and add
    log-channel moves to release notes. Cost: a detector change only.
- **Recommended rule:** B now and A's logger clause. ✅ A split keeps its facade's public import
  path and its log channel (the private files use the facade's logger). ✅ The harness finds view
  code by what it is, not by its file name. ❌ A moved log channel without a release-notes line.
  The re-export policy waits for the arch audit's decision on patch-through-facade.
- **Enforcement:** rule 19's scan set by content (closed-world); a logger clause under rule 28
  (any `getLogger(__name__)` in a `_<name>.py` whose facade exists fails). Control cases: a view
  class in `_helpers.py`; billing's `_subscription_mutations.py` logger.
- **Migration:** loggers in billing, notifications, orgs; harness rule 19.
- **Confidence:** Medium. Re-export counts and naming were scripted. Log channels were counted,
  but whether any operator filters on them is a team question (question 3).
- **Hand-off:** arch (patch-through-facade contract; the structural root is theirs).

### Item 7 (prior, still decided): `theme-module-presence` — compact

P · seam producers 3: `index.html.j2` conforms; `social/link_tree.html.j2` and
`social/embeds.html.j2` hand-write 11 flags and literal paths · rule 31 (decided) · check: the
rule 31 detector reads every `templates/**/*.html.j2` that assigns `window.__QUICKSCALE__`, not
only `THEME_SEAM_TEMPLATE`; alternatively the social pages render the seam through the same
`generator/seam.py` include · Confidence High · hand-off tech (latent SPA throw on `/social*` for
the next module with a React surface).

### Item 8 (prior, still decided): `write-effects-on-commit` — compact

F · modules with effects 5 (crm, forms, notifications, orgs, social all schedule with
`on_commit`) · notifications has no rollback test (0 test files mention rollback;
`test_services.py` uses `django_capture_on_commit_callbacks(execute=True)` only), and
`send_notification(dispatch_after_commit=False)` still permits an inline vendor call inside the
write's transaction, though no caller passes it · rule 21 (decided; review rule) · check: a
notifications rollback test; remove the `dispatch_after_commit` parameter (a permitted hazard
nobody uses) · Confidence Medium (rollback tests were found by keyword, not read for what they
assert).

### Item 9 (prior, still decided): `module-lists-outside-members` — compact

L · lists 10 → 1 remaining: the generated `urls.py.j2` shell regex (section 39 correction) ·
rule 37 (decided) · check: rule 37's detector reads `.j2` and `.sh` as well as `.py`, or Item 1's
option A removes the list · Confidence High.

## Rules proposed (seventh pass)

Not recorded in decisions.md: the maintainer decides. Numbers are proposals that continue rule
39.

41. **Module paths (D43).** ✅ A module's UI paths, React shell routes included, are declared in
    its manifest and rendered from the discovered, installed, enabled set; project-namespace
    route names for module pages are `quickscale_<module>:<name>`. ❌ Module paths as literals
    in generator or theme templates or other modules; two routes resolving one path.
42. **Settings snapshots (D44).** ✅ An optional private `_settings.py` frozen dataclass with
    `from_settings()`, with no default and no coercion. ❌ Settings objects in `services.py` or
    `__all__`, or read by another module.
43. **Optional senders (D45).** ✅ Guard with `is_installed` + `services.is_enabled()`; catch only
    the module's `<Module>Error`. ❌ `except Exception` around another module's service. Rules 3
    and 20 are reworded: notifications' row mirrors settings and is not a switch.
44. **One role check (D46).** ✅ Every org-role decision calls `user_has_org_role` with an
    `OrgRole` member. ❌ `OrganizationMembership` filtered by `role=` outside orgs.
45. **Stub exemptions (D47).** ✅ Root `mypy.ini` only. ❌ `[tool.mypy.overrides]` in a module.
46. **Splits (D48).** ✅ A split keeps its public path and log channel; rule 19 finds views by
    content. ❌ An unannounced log-channel move.

## Rules recorded (sixth pass)

Recorded in [decisions.md § Module Conventions](../technical/decisions.md#module-conventions) as
rules 30–39, before Enforcement (now rule 40), whose list gained a clause each; decisions.md wins on
any difference from this summary. Rules 2, 9, 11, 13, 14, 18, 22, and 27 were amended to match.

1. **Shared setting keys (D33).** ✅ A module's wiring may write a key another module writes only
   with an equal value; `REST_FRAMEWORK` sub-dicts are merged by core, and two modules may not set
   one sub-key. `apply` fails otherwise. ❌ Relying on module-name order for a setting's value.
2. **Theme seam (D34).** ✅ The seam's per-module flag is "installed and `_ENABLED`" and its path
   comes from the module's URL names, both rendered from the discovered module set; the theme's
   TypeScript keeps naming its modules. ❌ Hand-written module lines in `index.html.j2`; literal
   mount paths.
3. **Throttles (D35).** ✅ Scope `quickscale_<module>_<purpose>`, rate from the module's
   `_RATE_LIMIT` option. ❌ Rates in code or `adapter.py`; module tables created by `RunSQL`.
4. **Namespace stems (D36, option B).** ✅ Every name in a namespace shared with the project or
   other modules uses `quickscale_<module>`, reverse accessors, events, database functions, and
   advisory-lock keys included; rule 2's identity table lists every such namespace and its form.
5. **References by name (D37).** ✅ Rule 5's layer order applies to every reference to another
   module (import, `import_module`, app label, `get_model`, `is_installed`). ❌ A higher-layer
   module's name in a module's source, migrations excepted.
6. **Secrets (D38).** ✅ A secret reaches module code as a setting that `apply` renders from its
   `_ENV_VAR`; an empty required secret fails startup. ❌ `os.getenv` / `os.environ` in module code,
   except orgs' boot guard reading core's runtime-role variables.
7. **Type checking (D39).** ✅ One root `mypy.ini` section per module relaxing only the listed
   options. ❌ Per-module `[tool.mypy]`; unlisted disabled codes. Replaces rule 18's `[tool.mypy]`
   requirement.
8. **Module lists (D40).** ✅ Code outside the modules computes the module set from discovery.
   ❌ Literal lists of module names outside rule 5's table, rule 40's mapping, and the theme's
   TypeScript module surfaces.
9. **README content (D41).** ✅ Every option key and command name appears under its heading.
10. **Dependencies (D42).** ✅ `required_modules` holds bare names and selects them. ❌ Version
    specifiers on first-party modules; `implies`.

## Enforcement gaps

**Status at `c10b529e` (2026-10-03).**

| Gap | Status | Evidence |
|---|---|---|
| 1. no conformance test | **closed** | `scripts/check_module_conventions.py`, 36 rules, 205 control-case tests; passes |
| 2. page-style contract pins old paths | **closed** | `test_module_page_style_contract.py` no longer names the nested base paths (SA224, `49982a73`) |
| 3. user-FK gate hosted in orgs | **open** | rule 27 now states the limit (`decisions.md:937–939`); still no check in a generated project |
| 4. isolation gates list modules by hand | **closed** | `provision_ci_postgres.sh` and `test_isolation_conformance.sh` derive from discovery (`68c68968`) |
| 5. README check open-world | **closed** | rule 38 in the harness |
| 6. layer check import-based | **closed** | rule 34 in the harness, plus the SA228 import-layer test |
| 7. rule 18 unenforceable | **closed** | rule 36 replaced it; a successor gap is 16 below |
| 8. configuration read by nothing | **partly open** | `[tool.mypy]` option blocks are gone; `[[tool.mypy.overrides]]` remain in 10 modules (gap 16) |
| 9. validation that cannot fail | **closed** | floors gone (`92c9566f`); listings carries no `^\d+$` pattern |
| 10. permissive allowed sets | **closed** | `collect_wiring` fails on conflicts (`cb750c51`); a module rate keyed `anon`/`user` would fail rule 32's stemmed-scope check (indirect) |
| 11. dangling SA35 reference | **closed** | rule 27 cites `orgs/tests/test_user_fk_conformance.py` |
| 12. shipped-source oracle | **closed** | `TENANT_TABLE_REGISTRY` is test-owned (`e28ab43d`) |

**New (2026-10-03):**

13. **Rule 40 reads only Python.** The rule 37 detector skips non-`.py` files
    (`check_module_conventions.py:4465`), and rule 31 reads one template
    (`THEME_SEAM_TEMPLATE`, `:142`). The generator's `.j2` templates are where both corrections
    of this pass and `mount-path-copies` live. Rules 7, 31, and 37 are **open-world over
    templates**.
14. **Rule 19's scan set follows file names** (`:153–158`, stated in the harness). View code under
    a third private spelling, or role logic in a service (`org-role-check-copies`), is unscanned.
15. **An exemption the decision does not list.** Rule 36's detector skips
    `[[tool.mypy.overrides]]` (`:4653`). Rule 40 requires every exception in the mapping that
    mirrors decisions.md (`mypy-overrides-unread`).
16. **Configuration read by nothing.** Ten modules' `[[tool.mypy.overrides]]` blocks; CI reads
    the root `mypy.ini`. notifications' `anymail` entry exists only there.
17. **A permitted hazard nobody uses.** `send_notification(dispatch_after_commit=False)` performs
    the vendor call inside the caller's transaction, which rule 21 forbids. No caller passes it
    (`write-effects-on-commit`).
18. **Stale rule text.** Rules 3 and 20 describe notifications' `NotificationSettings` row as a
    runtime switch. Since SA217 it mirrors settings (`optional-sender-guard`).
19. **A cross-module read through a sanctioned surface.** Rule 4's ❌ "reading another module's
    settings" is checked by import target, so a public settings object in `__all__` passes it
    (`settings-snapshot-readers`).

**As recorded 2026-09-28:**

1. **The conformance test (rule 30 when audited, now rule 40) does not exist.** Every rule except
   rule 27 has no check today; rule 27 is held by SA35's gate. The decisions are recorded, but nothing stops the next module from copying any
   variant in sections 1–41.
2. **An existing check pins the old convention.** Core's `test_module_page_style_contract.py`
   hard-codes today's nested base paths (`quickscale_modules_blog/blog/base.html`) and flat CSS,
   which rule 8 changes. It must change in the same commit as rule 8 (SA224 now carries it), and it lists modules by hand
   (open-world).
3. **A whole-population gate hosted in one module.** SA35's gate lives in orgs' tests and sees only
   the apps orgs' test settings install: ten modules and two test apps. A new module that is not
   added there is unchecked. Rule 27 says "in a module or a project's own app (the gate checks
   both)", but the only project apps it sees are orgs' two test apps: no check runs in a generated
   project. As a side effect, orgs (layer 1) installs every layer-3 module to test itself.
4. **Isolation gates list modules by hand.** `RLS_MODULES` (5) and `MAPPING_MODULES` (6) leave out
   social's tenant tables, and only crm's `test_isolation.py` runs on the PostgreSQL gate (D40).
5. **Rule 11's README check is open-world.** It checks headings only (D41).
6. **Rule 5's layer check is import-based.** References by name are invisible to it (D37).
7. **Rule 18 is unenforceable as written.** It requires `[tool.mypy]` sections that CI does not
   read, and contradicts module-extension.md step 1.3, which registers modules in the root
   `mypy.ini` (D39).
8. **Configuration read by nothing.** The `[tool.mypy]` blocks in blog, listings, and storage; the
   per-option `validation:` blocks (section 14, D15 makes core read them).
9. **Validation that cannot fail.** `required_modules` version floors under lockstep (D42);
   listings' `^\d+$` accepts `0` (section 14).
10. **Permissive allowed sets.** `collect_wiring` accepts any key from any module, last writer wins
    (D33). The generated `base.py` lets a module rate override `anon`/`user`.
11. **A reference that would dangle once rule 29 lands** — already covered: rules 27 and 30 cite
    `orgs/tests/test_sa35_conformance.py` and "SA35's gate", which rule 29 renames, and SA227's scope
    already renames "the docs that cite them (decisions rule 27 cites the SA35 gate's file)".
12. **A shipped-source oracle.** `TENANT_TABLE_REGISTRY` is recorded as a CI parity oracle but lives
    in orgs' `tenancy.py` (D37).

**Closing note (SA215, 2026-10-02).** Gaps 1, 2, and 4–12 are closed (gap 10's generated-composition
clause excepted, as the [Closing pass](#closing-pass-sa215-2026-10-02) records): the rule 40 harness
covers the statically checkable rules, the page-style contract is discovery-driven, the isolation
gates derive their module sets, the README check reads option and command names, references by name
are checked, the root `mypy.ini` carries one section per module, option `validation:` blocks are
read, `required_modules` refuses specifiers, `collect_wiring` refuses unequal values, the gate is
renamed, and the tenant registry is test-owned. Gap 3 is accepted with its reason in decisions.md
rule 27. The list above is the audit-time record, not a description of the current tree.

**SA236 close (2026-10-03).** Gaps 17–19 are closed: the `dispatch_after_commit` parameter is
removed, decisions.md rules 3 and 20 name notifications' row as a read-only mirror, and harness
rule 42 rejects a snapshot read from another module.

**SA235 close (2026-10-03).** Gap 13 is closed: the rule 40 harness's rules 7, 31, and 37 read
`generator/templates/**/*.j2` with control cases (rule 7 also rejects a quoted path beneath a
declared mount), and the pass's two corrected cells render from discovery —
`project_name/urls.py.j2` carries no flat-module shell list (the orgs reservation's allowlisted
alternation stays a rule 41 exception) and the two social seam producers render through
`generator/seam.py`. Gaps 14–16 stay open for SA237 and SA238.

**SA237 close (2026-10-03).** Gaps 15–16 are closed: billing's post-lock re-check calls
`user_has_org_role` with `OrgRole.OWNER`, the ten modules' `[[tool.mypy.overrides]]` blocks are
deleted, `anymail` joins the root `mypy.ini`, and harness rule 45 rejects any per-module
`[tool.mypy]` table. Gap 14 stays open for SA238.

## Consistent by design

- **Outbound vendor clients follow their SDKs:** billing builds a `StripeClient` per call; analytics
  keeps one PostHog client behind a lock (`sync_mode=False`); notifications uses Django's email
  backend through anymail; storage uses django-storages; backups goes through the DR engine. None
  sets an explicit timeout or retry, which is consistent across the population. Whether the SDK
  defaults are acceptable is a technical question, not a convention.
- **Vendor fakes in tests:** `mock.patch` plus small fake classes; notifications uses Django's
  `locmem` backend. Each follows its vendor's shape.
- **Log volume:** backups, crm, notifications, social, and storage log nothing. backups and
  notifications record outcomes in models (`BackupArtifact`, `NotificationDelivery`). No cost to
  name, so no item; every logger is `getLogger(__name__)`.
- **RLS policy names** (`<module>_<model>_org_isolation`): per-table in PostgreSQL, so no clash;
  migration-owned by decision.
- **Soft delete** exists only in backups (retention state); with one member, there is nothing to
  compare. (Advisory-lock keys, also billing-only, were listed here; rule 33 now covers them.)
- **Module pages in the theme:** blog, crm, forms, listings, social, and orgs have React pages in
  core's theme by the recorded De-Specialization decision; only the flags and paths drift (D34).
- **URL converters:** slugs for public tenant routes, integers and UUIDs for internal ids, as rule
  14 intends.
- **Status codes** for "switched off": the 403/404 split is already decided (rules 1, 26).

- **Forms' shadowed routes** (2026-10-03): `forms/` and `forms/<slug>/` match the React shell
  first, but forms' `FormPageView` is itself a React mount ("renders a React mount point div"),
  so nothing is lost. `mount-path-copies` is about blog's and listings' indexes.
- **Snapshots holding one consistent view** (2026-10-03): billing passes one settings view
  through a provider-lock wait, and backups passes a policy into the DR engine (rule 5). A
  snapshot's existence follows that need; only its form and placement are drift (§42).
- **orgs excluded from the seam flags** (`generator/seam._NON_SEAM_MODULES`): orgs reports
  `owner.mode` instead, as rule 31 records.
- **Operator `is_superuser` paths** outside views: orgs' `admin.py`, `middleware.py`,
  `permissions.py`, `_debug.py`, and the `quickscale_orgs_debug` template tag are the listed
  operator machinery of rule 19. analytics' `_request_is_staff` is rule 19's listed traffic filter.

## Hand-offs

**2026-10-03 (seventh pass).** The companions now carry this pass's leads in their own lists.

*To the technical audit* (live or latent defects):
- `mount-path-copies`: in a generated React-theme project, `reverse("quickscale_blog:post_list")`
  (`/blog/`) and `quickscale_listings:listing_list` (`/listings/`) are served by the shell, not by
  the module views. The shell is also not gated by the modules' `_ENABLED`. Decide whether the
  server indexes are meant to be reachable.
- `theme-module-presence`: the two social pages hand-write 11 module flags. The next module with a
  React surface makes the seam validator throw on `/social` and `/social/embeds` (latent).

*To the architectural audit* (structural roots):
- `split-facade-conventions`: the naming, re-export, and log-channel conventions are recorded
  here. The patch-through-facade contract is the arch audit's own finding.
- `mount-path-copies`: URL-path ownership between the host project and modules has no single
  declaration. Option A adds a manifest key, which is a boundary change.

**2026-09-28 (sixth pass):**

**To the technical audit** (live defects): none live. Two become defects when decided rules land.
Both are recorded here, and the technical audit should take them at that point:
- `shared-setting-writes`: a second `REST_FRAMEWORK` writer removes billing's throttle rates (DRF
  `ImproperlyConfigured` on checkout and portal).
- `theme-module-presence`: switched-off modules keep navigation that 404s.

**To the architectural audit** (structural roots):
- `upward-name-references`: the tenancy foundation (orgs) owns vocabulary and table lists of layer-3
  modules. The layer rule is import-shaped and does not reach them.
- `module-lists-outside-members`: the module population is declared in about ten places outside
  discovery.
- `shared-setting-writes`: core's settings merge is last-writer-wins by module name; the wiring
  boundary has no ownership model for shared keys.

**Roadmap.** Where a finding follows from a rule already decided, the ticket carrying that rule now
says so: SA219 (the theme's flags follow `_ENABLED`), SA220 (blog → `storage.helpers`), SA223 (blog's
counter table, billing's hard-coded rates, and the `REST_FRAMEWORK` overwrite), SA227 (no `py.typed`
work; `poetry.toml` in three modules, not all). The decided D33–D42 are folded into the existing
tickets: D33 and D35 → SA223; D34, D38 (settings path), and D42 → SA219; D38's startup check →
SA225; D36 → SA221 (identity table, orgs' database function), SA222 (`related_name`), SA223
(billing's advisory-lock keys), SA226 (events); D37 → SA220; D39–D41 → SA227, except core's
page-style contract, which SA224 changes together with the templates it pins; SA215 closes them
with rule 40's test.

## Aspect catalogue additions

- **A (2026-10-03):** URL *paths* (not only names) claimed by both host-project routes and module
  mounts, and the order that decides the winner.
- **B (2026-10-03):** typed settings objects (snapshots): form, placement, and visibility.
- **C (2026-10-03):** how a sender guards an optional lower module (`is_enabled()` against settings
  objects, and the catch width).
- **E (2026-10-03):** role checks in services, not only views.
- **K (2026-10-03):** log-channel stability across file splits.
- **L (2026-10-03):** split facades: private naming, re-export policy, and their effect on
  name-keyed detectors.
- **N (2026-10-03):** type-checker exemptions declared in files CI does not read.
- **Enforcement (2026-10-03):** which file types each detector reads. A Python-only harness is
  open-world over generator templates.

- **A:** settings keys written by module wiring, and the merge that combines them; DRF throttle
  scopes; raw-SQL objects outside the ORM (tables, functions, triggers); advisory-lock keys.
- **B:** when and where a secret named by an `_ENV_VAR` option is resolved.
- **C:** references to another module by name (app label, `get_model`, `is_installed`,
  `import_module`), not only imports.
- **L/N:** hand-kept module lists outside the modules (core, CLI, scripts, theme).
- **M/N:** which member's test suite hosts a whole-population gate, and which apps its settings
  install.
- **N:** where type-check strictness really lives, versus where the rule puts it.
- **O:** README content against the manifest and the command list, not only its outline.
- **P:** the theme seam's per-module flags and paths.

## Questions that would change a rule

**2026-10-03 (seventh pass)**, for the maintainer:

1. In a React-theme project, should `/blog/` and `/listings/` serve the modules' server-rendered
   indexes, or is the React page the index (Item 1, option A or C)? → `mount-path-copies`
2. Should notifications regain an operator-toggle row (runtime off without redeploy), or is
   "settings only" final, with rules 3 and 20 reworded? → `optional-sender-guard`
3. Does any deployment filter logs by module channel (`quickscale_modules_billing.services`)? If
   so, a moved channel is a breaking change. → `split-facade-conventions`
4. Is CI's mypy run expected to need `anymail` stubs, or does the notifications block exist only
   for running mypy inside the module? → `mypy-overrides-unread`

Answered by the maintainer on 2026-09-28:

1. orgs' `require_org_feature` moves to billing (D37 option A). → `upward-name-references`
2. `TENANT_TABLE_REGISTRY` moves into test code (D37 option A). → `upward-name-references`,
   `module-lists-outside-members`
3. Event names take the stem, like every shared name (D36 option B): `quickscale_forms_submitted`.
   → `namespace-prefix-principle`
4. orgs' twelve disabled mypy codes are fixed in SA227 (D39 option A, no accepted debt). →
   `type-check-config`

Still to check while implementing: whether anything outside this repository (`bap-web`, a deployed
`quickscale.yml` or `.quickscale/state.yml`) relies on `implies` or the `>=` floors that D42
removes (SA219). → `manifest-dependency-spec`

## Reconciliation log

"Re-verified" means the cells were recounted by script or reopened at their locations on
2026-09-28; "spot-checked" names what was not recounted. No module source changed between
`1dc8248b` and `58e73cc7`, so every correction below is an error in the first write-up, not a change
in the code.

- 2026-09-28 — `settings-names`: decided (rule 1) — re-verified (every `django_setting` listed from
  the manifests matches section 1).
- 2026-09-28 — `module-enabled-switch`: decided (rule 1) — re-verified; still 3 of 12.
- 2026-09-28 — `settings-readers-and-defaults`: decided (rule 3) — re-verified (`getattr(settings`
  in 11 modules); adds 18 settings missing from five modules' test settings (section 3).
- 2026-09-28 — `cross-module-settings-reads`: decided (rules 3–4) — re-verified (blog, forms, orgs).
- 2026-09-28 — `secret-env-var-names`: decided (rule 1) — re-verified.
- 2026-09-28 — `module-dependency-direction`: decided (rules 4–5) — re-verified; blog → storage
  added (correction in section 5); references by name split out as `upward-name-references`.
- 2026-09-28 — `identity-stem`: decided (rule 2) — re-verified (all 12 labels
  `quickscale_modules_<name>`; orgs has no `app_name`); `db_table` row corrected (backups 3 tables,
  forms 4).
- 2026-09-28 — `url-mounts-and-names`: decided (rule 7) — re-verified; analytics' row corrected (it
  already mounts at `analytics/` from its manifest).
- 2026-09-28 — `templates-static-tags`: decided (rule 8) — re-verified (module base paths; orgs 6
  of 8 templates emit `<html>`, the other two are a partial and an admin override); core's
  page-style contract pins the old paths (Enforcement gaps 2).
- 2026-09-28 — `http-api-shape`: decided (rule 9) — re-verified; framework row corrected (orgs is not
  DRF) and error-body counts corrected (72 / 18 in `src/`).
- 2026-09-28 — `startup-checks-and-errors`: decided (rule 10) — re-verified (`ImproperlyConfigured`
  in seven `apps.py`, `checks.py` only in orgs; exception classes in billing and notifications
  `services.py`, blog and listings `views.py`, social `contracts.py`, orgs `current_org.py`).
- 2026-09-28 — `package-files`: decided (rules 11, 28) — re-verified (file listing of all 12
  packages; no module defines `is_enabled()`).
- 2026-09-28 — `required-tests`: decided (rule 11) — re-verified; the file matrix is unchanged.
- 2026-09-28 — `readme-outline`: decided (rule 11) — re-verified; content gaps split out as
  `readme-content-accuracy`.
- 2026-09-28 — `model-choices`: decided (rules 11, 14) — re-verified (15 literal lists: backups 5,
  forms 3, crm 2, notifications 2, blog 1, listings 1, social 1).
- 2026-09-28 — `option-schema-and-validation`: decided (rule 12) — re-verified (5 `validation`
  blocks in 4 modules; 25 duplicate `derived_settings`, 10 repeated defaults; listings' `^\d+$`).
  Core's and the CLI's per-module option code was spot-checked by file, not recounted.
- 2026-09-28 — `tenant-model-base`: decided (rule 13) — re-verified (blog and crm subclass
  `TenantModel`; `tenant_org_fk` still in billing, blog, forms, listings, orgs, social).
- 2026-09-28 — `model-basics`: decided (rule 14) — timestamps recounted (21 / 14); `related_name`,
  `__str__`, and ordering spot-checked, not recounted.
- 2026-09-28 — `package-root-init`: decided (rule 15) — re-verified (`default_app_config` in auth,
  blog, crm, listings; forms has `__version__` only).
- 2026-09-28 — `signals-vs-receivers`: decided (rule 16) — re-verified.
- 2026-09-28 — `command-behavior`: decided (rule 17) — re-verified (`--dry-run` only in
  `backups_sync_media`, `backups_restore`, `purge_organization`; `sys.exit` in
  `check_tenant_isolation`).
- 2026-09-28 — `package-tooling`: decided (rule 18) — corrected (section 20); the mypy part is
  superseded by `type-check-config`. `poetry.toml` still missing in analytics, notifications,
  storage.
- 2026-09-28 — `tenant-authorization`: decided (rule 19) — re-verified (`is_staff` / `IsAdminUser`
  in blog, crm, forms, listings views; orgs' four are `is_superuser` operator paths, as section 21 says).
- 2026-09-28 — `email-sender`: decided (rule 20) — re-verified (forms' own path in
  `notifications.py`).
- 2026-09-28 — `write-effects-on-commit`: decided (rule 21) — re-verified (`on_commit` only in
  notifications).
- 2026-09-28 — `analytics-event-ownership`: decided (rule 22) — re-verified (`capture_form_submit`,
  `capture_social_link_click` still in analytics); see `namespace-prefix-principle`.
- 2026-09-28 — `service-surface`: decided (rule 23) — re-verified; keyword-only row corrected (10 of
  51 violate rule 23, in analytics, billing, backups; social conforms).
- 2026-09-28 — `current-time-call`: decided (rule 24) — re-verified (storage `helpers.py`).
- 2026-09-28 — `cache-key-stem`: decided (rule 24) — re-verified (social only; orgs deletes social's
  keys).
- 2026-09-28 — `constraint-index-names`: decided (rule 25) — re-verified by style counts.
- 2026-09-28 — `inbound-webhooks`: decided (rule 26) — re-verified (billing 403/403/500/400,
  notifications 400/403/403/400).
- 2026-09-28 — `user-fk-on-delete`: resolved (`fa0b882b` — verified: the SA35 gate accepts only
  `SET_NULL` or an allowlisted `CASCADE`, no model uses `PROTECT`, and the rule is now Module
  Conventions rule 27). The gate's reach is narrower than rule 27 states (Enforcement gaps 3).
- 2026-09-28 — `test-file-names`: decided (rule 29) — re-verified (103 test files in 11 modules
  mention a ticket; analytics has none).
- 2026-09-28 — `py-typed`: resolved (`6ea37301` — verified; the first write-up's cell was wrong,
  all twelve ship it).
- 2026-09-28 — `shared-setting-writes`: decided (rule 30, D33) — maintainer decision; members not yet changed.
- 2026-09-28 — `theme-module-presence`: decided (rule 31, D34) — maintainer decision; members not yet changed.
- 2026-09-28 — `throttle-scopes-and-rates`: decided (rule 32, D35) — maintainer decision; members not yet changed.
- 2026-09-28 — `namespace-prefix-principle`: decided (rule 33, D36, option B) — maintainer decision; members not yet changed.
- 2026-09-28 — `upward-name-references`: decided (rule 34, D37) — maintainer decision; members not yet changed.
- 2026-09-28 — `secret-resolution-path`: decided (rule 35, D38) — maintainer decision; members not yet changed.
- 2026-09-28 — `type-check-config`: decided (rule 36, D39) — maintainer decision; members not yet changed.
- 2026-09-28 — `module-lists-outside-members`: decided (rule 37, D40) — maintainer decision; members not yet changed.
- 2026-09-28 — `readme-content-accuracy`: decided (rule 38, D41) — maintainer decision; members not yet changed.
- 2026-09-28 — `manifest-dependency-spec`: decided (rule 39, D42) — maintainer decision; members not yet changed.
- 2026-10-02 — closing pass (SA215): every index item resolved. The convention tickets landed the
  code changes and rule 40's harness enforces the statically checkable rules over the shipped tree;
  rules 21, 27, and 30 keep their delegated checks. Sections 1–41 remain the 2026-09-28 evidence.

**2026-10-03 (seventh pass, `58e73cc7..c10b529e`).** "Verified" means two things: the rule 40
harness passed at `c10b529e` with the rule covered, **and** this pass checked independently by
script. The independent checks: 0 `getattr(settings, "…", default)`; 0 `os.getenv`/`os.environ`
outside rule 35's exception and comments; no `teams/`; 0 `unique_together`; 0
`default_app_config`; 0 `send_mail`/`EmailMessage` outside notifications; 0 `datetime.now(`; 0
`JsonResponse`; 12 labels `quickscale_<module>`; 12 `poetry.toml`; 12 `is_enabled()` reading the
setting directly; module lists in `scripts/` derived from discovery. Cells not recounted are named.

- 2026-10-03 — `shared-setting-writes`: resolved (`cb750c51` — verified: `collect_wiring` raises `_setting_conflict` naming both modules, `module_wiring.py:71,122,159`).
- 2026-10-03 — `theme-module-presence`: still-open as decided (rule 31) — `index.html.j2` conforms (`b825bb6d`); correction: two social seam producers, present at `58e73cc7`, still hand-write flags and paths (§33).
- 2026-10-03 — `theme-module-presence`: resolved (SA235 — the two social seam producers render flags and `{% url %}`-based paths through `generator/seam.py`; harness rules 31 and 37 read `.j2`).
- 2026-10-03 — `throttle-scopes-and-rates`: resolved (`c3c99253` — verified by harness rule 32).
- 2026-10-03 — `namespace-prefix-principle`: resolved (`6fe010b4` and successors — verified by harness rule 33; stems not recounted).
- 2026-10-03 — `upward-name-references`: resolved (`2352acf1` — verified by harness rule 34; `TENANT_TABLE_REGISTRY` test-owned, `e28ab43d`).
- 2026-10-03 — `secret-resolution-path`: resolved (`17d4985d` — verified: harness rule 35 and the `os.getenv` count).
- 2026-10-03 — `type-check-config`: resolved (`c75b5588` — verified by harness rule 36); successor drift split out as `mypy-overrides-unread`.
- 2026-10-03 — `module-lists-outside-members`: still-open as decided (rule 37) — 9 of 10 lists derive from discovery or are listed; correction: `project_name/urls.py.j2` shell routes, present at `58e73cc7`, were missed (§39).
- 2026-10-03 — `module-lists-outside-members`: resolved (SA235 — the generated `urls.py.j2` flat-module shell list is gone while the orgs reservation's allowlisted alternation stays a rule 41 exception; module routes render from `spa_routes` discovery, held by harness rule 37 over `.j2`).
- 2026-10-03 — `readme-content-accuracy`: resolved (`49b709f2` — verified by harness rule 38).
- 2026-10-03 — `manifest-dependency-spec`: resolved (`92c9566f` — verified by harness rule 39).
- 2026-10-03 — `settings-names`: resolved (`79b3f079` — verified by harness rule 1).
- 2026-10-03 — `module-enabled-switch`: resolved (`97ac9187` — verified: 12 `is_enabled()`, harness rule 1).
- 2026-10-03 — `settings-readers-and-defaults`: resolved (`2b44e473` — verified: 0 defaulted reads, harness rule 3); the snapshot form split out as `settings-snapshot-readers`.
- 2026-10-03 — `cross-module-settings-reads`: resolved (`c460d46f` — verified by harness rules 3–4); orgs' read through notifications' public snapshot recorded under `optional-sender-guard`.
- 2026-10-03 — `secret-env-var-names`: resolved (`480735c9` — verified by harness rule 1).
- 2026-10-03 — `module-dependency-direction`: resolved (`10dc1691` — verified by harness rules 4–5 and the SA228 import-layer test).
- 2026-10-03 — `identity-stem`: resolved (`6fe010b4` — verified: 12 labels).
- 2026-10-03 — `url-mounts-and-names`: resolved for the modules (`30759c78` and the SA223 series — verified by harness rule 7); host-side copies opened as `mount-path-copies`.
- 2026-10-03 — `templates-static-tags`: resolved (`49982a73` — verified by harness rule 8).
- 2026-10-03 — `http-api-shape`: resolved (`dcd3bda0` and the SA223 series — verified: 0 `JsonResponse`, harness rule 9).
- 2026-10-03 — `startup-checks-and-errors`: resolved (`88dad552` — verified by harness rule 10).
- 2026-10-03 — `package-files`: resolved (`c75b5588` — verified by harness rules 11 and 28; private-file conventions split out as `split-facade-conventions`).
- 2026-10-03 — `required-tests`: resolved (`9382e6ed` — verified by harness rule 11).
- 2026-10-03 — `readme-outline`: resolved (`49b709f2` — verified by harness rule 11).
- 2026-10-03 — `model-choices`: resolved (`bf60796f` — verified by harness rule 11; one string role literal in billing recorded under `org-role-check-copies`).
- 2026-10-03 — `option-schema-and-validation`: resolved (`d0b148c9` and the SA217 series — verified by harness rule 12).
- 2026-10-03 — `tenant-model-base`: resolved (`bf60796f` — verified by harness rule 13).
- 2026-10-03 — `model-basics`: resolved (`bf60796f` — verified by harness rule 14; `related_name` and ordering not recounted).
- 2026-10-03 — `package-root-init`: resolved (`b315009f` — verified: 0 `default_app_config`, harness rule 15).
- 2026-10-03 — `signals-vs-receivers`: resolved (`b315009f` — verified by harness rule 16).
- 2026-10-03 — `command-behavior`: resolved (`84652d2d` — verified by harness rule 17).
- 2026-10-03 — `package-tooling`: resolved (`469e3b7d` — verified: no `teams/`, 12 `poetry.toml`, harness rule 18).
- 2026-10-03 — `tenant-authorization`: resolved for views (`ab3ec43e` — verified by harness rule 19); billing's service copy opened as `org-role-check-copies`.
- 2026-10-03 — `email-sender`: resolved (`0c6f96cd` — verified: 0 `send_mail`/`EmailMessage` outside notifications); guards opened as `optional-sender-guard`.
- 2026-10-03 — `write-effects-on-commit`: still-open as decided (rule 21) — `on_commit` in crm, forms, notifications, orgs, social; notifications lacks a rollback test.
- 2026-10-03 — `analytics-event-ownership`: resolved (`0c6f96cd` — verified by harness rule 22).
- 2026-10-03 — `service-surface`: resolved (`b18032e3` — verified by harness rule 23).
- 2026-10-03 — `current-time-call`: resolved (`c75b5588` — verified: 0 `datetime.now(`).
- 2026-10-03 — `cache-key-stem`: resolved (`10dc1691` — verified by harness rule 24).
- 2026-10-03 — `constraint-index-names`: resolved (`c75b5588` — verified: 0 `unique_together`, harness rule 25).
- 2026-10-03 — `inbound-webhooks`: resolved (`f6ad7784` — verified by harness rule 26; status codes not re-read).
- 2026-10-03 — `test-file-names`: resolved (`730456cb` — verified by harness rule 29).
- 2026-10-03 — `user-fk-on-delete`: resolved (`fa0b882b` — the gate still holds; its reach is Enforcement gap 3).
- 2026-10-03 — `py-typed`: resolved (`6ea37301` — verified by harness rule 11).
- 2026-10-03 — `mount-path-copies`: resolved (SA235 — verified by harness rules 7, 31, and 37 over `generator/templates/**/*.j2`; module React shell routes render from manifest-declared `spa_routes` after the module includes, the social seam pages render through `generator/seam.py`, and `TenantMiddleware` reads orgs' URL names).
- 2026-10-03 — `settings-snapshot-readers`: resolved (SA236 — verified by harness rule 42; the five modules' snapshots live in a private `_settings.py` built by `from_settings()` and their names left `services.__all__`).
- 2026-10-03 — `optional-sender-guard`: resolved (SA236 — verified by harness rule 43; orgs guards on `notifications.services.is_enabled()`, forms catches only `NotificationError`, and the `dispatch_after_commit` hazard is removed).
- 2026-10-03 — `org-role-check-copies`: resolved (SA237 — verified by harness rule 44; billing's post-lock re-check calls `user_has_org_role` with `OrgRole.OWNER` and keeps its call-site `is_active` test).
- 2026-10-03 — `mypy-overrides-unread`: resolved (SA237 — verified by harness rule 45; the ten modules' `[[tool.mypy.overrides]]` blocks are deleted and `anymail` joins the root `mypy.ini`).
- 2026-10-03 — `split-facade-conventions`: open (new; D48 proposed).
- 2026-10-04 — `split-facade-conventions`: resolved (SA238 — verified by harness rules 19 and 28; the rule 28 clause rejects `getLogger(__name__)` in a private file with a facade, and rule 19 finds view code by content — a Django or DRF view subclass or a function taking `request` — so a split's view code is scanned under any private name).
