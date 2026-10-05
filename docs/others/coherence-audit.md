# QuickScale — Deep Coherence Audit (cross-module conformance)

Audited: 8e4122f2 (v89) · 2026-10-05 · working tree dirty (uncommitted `docs/others/arch-audit.md` and `tech-audit.md` only; not read as code) · repository public (github.com/Experto-AI/quickscale) · prompt: deep-coherence-audit v1 · passes: 2 (this re-run; 10 in all)

> **Re-run of:** the 2026-10-03 pass at `c10b529e`. **Delta swept:** `c10b529e..8e4122f2`
> (55 non-merge commits; 152 module files, about +8.1k/−3.3k lines in `quickscale_modules/`).
>
> **Where earlier passes live.** Passes 1–8 (2026-09-26 → 2026-10-03) were written into
> [`docs/planning/module-conventions-inventory.md`](../planning/module-conventions-inventory.md).
> That file mixed the audit (index, statuses, reconciliation log) with the conventions evidence
> (sections 1–47) and the decision drafts D1–D48. **From this pass on, this file is the coherence
> audit**, kept next to `tech-audit.md` and `arch-audit.md` and in their format. The inventory
> stays as the evidence and decision record that this audit cites: its sections are the per-aspect
> tables of passes 1–8, and [decisions.md § Module Conventions](../technical/decisions.md#module-conventions)
> rules 1–48 are the rules. Every prior ID is carried here with the same name. The inventory's
> index and reconciliation log are frozen at `c10b529e`, and its header points here.

---

## 1. Orientation summary

**Populations.**

- **The 12 modules** (`analytics`, `auth`, `backups`, `billing`, `blog`, `crm`, `forms`,
  `listings`, `notifications`, `orgs`, `social`, `storage`). Unchanged since the last pass, and no
  member was added.
- **New in this delta: the 5 account-anonymization handlers** that SA216(a–c) added: auth,
  billing, blog, notifications, and orgs. Each has an `apps.py` `anonymize_account` executor, an
  `anonymize_handlers()` capability, and a private `_anonymization.py`. The files run from 56
  lines (orgs) to 505 (notifications).
- **The 6 modules with write effects** (rule 21): crm, forms, notifications, orgs, and social, plus
  blog, whose anonymization deletes the avatar file in an `on_commit` callback.
- **3 manifests declaring `spa_routes`** (blog, crm, listings), from SA235.
- **16 management commands**, now that SA240 added `quickscale_orgs_create_site_org`.
- **Outside the members:** the rule 40 harness (`scripts/check_module_conventions.py`, 6,646
  lines), core's `collect_capabilities`, auth's anonymize collector, and the personal-data
  inventory `orgs/tests/_personal_data_inventory.py`. That inventory carries entries for 11 apps,
  9 of them outside orgs.

**Shared namespaces.** These are the same as in the 2026-10-03 pass (inventory §§1–47). This
delta adds two:

- **Anonymization replacement values.** These are the sentinel strings that every handler writes
  into shared, user-visible or provider-visible fields: `deleted-<pk>`, `deleted-<pk>@invalid`, and
  `[redacted]`.
- **Personal-data inventory keys.** These are `(app_label, model, field)` rows, held in one
  file in one module.

**Declared conventions.**

- decisions.md § Module Conventions rules 1–48. Rule 40's harness covers 42 of them; running it at
  `8e4122f2` gave `All 40 covered module conventions pass`, and SA245 adds rules 47–48 (§12).
  - `OPEN_RULES` = 21 (a review rule plus per-module rollback tests), 27 (the user-FK gate), and
    30 (`collect_wiring`).
  - Rules 41 and 46 have no detector of their own. Their clauses run inside rules 7, 31, 37
    (rule 41) and 19, 28 (rule 46), as the partition-test comment at
    `scripts/test_check_module_conventions.py:7282` records.
- **The anonymization contract.** module-extension.md (lines 185–195) states the `ANONYMIZE`
  declaration and the `(self,)` capability. The personal-data inventory is enforced by
  `orgs/tests/test_personal_data_inventory.py`, which is closed-world over candidate fields and
  has three control cases. **No Module Conventions rule covers how a handler scrubs.**

**Reference members.**

- notifications is the reference for anonymization. It has word-bounded, HTML-aware matching and
  the most tests. It is also the outlier in size, and its scope is a tech-audit S2 finding.
- crm remains the reference for everything else.

**Activation.** `active: A–H, J–O · inert: P (no new frontend surface in this delta; rule 41 holds
the seam), Q (English only, rule 14) · quiet: I, K (no drift passing §0)`.

**Scope.** All 12 modules and the code outside them that names the modules. Excluded:
`quickscale_devtools` (SA214's beta-migration and design-port oracle is developer tooling, not a
member) and host projects outside this repository.

**Delta classification** (`c10b529e..8e4122f2`, 55 commits):

- **Convention-applying:**
  - SA235 (rule 41: `a621299b`, `4d1e3b1e`)
  - SA236 (rules 42–43: `537204bc`)
  - SA237 (rules 44–45: `6b4fd1eb`, `c04d6583`)
  - SA238(a–c) (rule 46: `7097fa3e`, `46d99cdb`, `d1feab8d`)
  - SA234 (split-facade seams: `c42f6574`)
  - SA239 (`6e0ac9da`)
  - the SA215 closing commits (`f6a95469` … `aa59eba2`)
- **Convention-breaking** (one new population, no new member). SA216(a–c) (`3cffb168`, `8649849c`,
  `00dd5214`, `dfd6214e`) added five anonymization handlers with no shared helper and no rule on
  replacement values. SA242 (`54dd3073`) put every module's personal-data rows in orgs' tests.
  Items 1–4 cover these.
- **Neutral:** SA240 (`7695bac9`) is a new command that conforms to rule 17 (idempotent, not
  destructive, so no `--dry-run` is required).
- **Unrelated:** SA214(a–f) devtools, SA231/SA233/SA242/SA243 quality-gate work, and roadmap
  edits.

**Companion hand-offs read.**

- **arch-audit *Coherence hand-offs*:** "Anonymization scrubbers … independently written escaping
  logic … candidate for shared scrub helpers". This lead passed §0 and became Item 1.
- **tech-audit:** `billing-anonymize-name-substring` (S4) and
  `notifications-account-username-dead` (S4) are the defect side of Items 1 and 3. This audit
  re-confirmed the first one by execution (see Item 1).

**Coverage.**

- **Read in full:** all five `_anonymization.py` files, the five `apps.py` executors and
  capability methods, the personal-data inventory and its test names, module-extension.md
  §removal, decisions.md rules 41–46, and the harness's `OPEN_RULES` and run output.
- **Rule 21 re-check:** every module's tests were searched for rollback and `on_commit` markers,
  and notifications' rollback test was read.
- **Not re-read cell by cell:** sections 1–47 of the inventory. Those 48 items rest on the harness
  run (closed-world clauses with control cases) plus a spot-check of rules 21, 41, and 46. Their
  log lines say so.

---

## 2. Machine-readable index

```yaml
schema: coherence-audit/v1
audited: 8e4122f216824edb62134441a00f2413b3854653
items:
  - {id: anonymize-redaction-helper-copies, status: resolved, rule: "rule 47", aspect: C, check: conformance, closed_world: false, resolved_by: abbc09d0, first_seen: 2026-10-05, last_verified: 2026-10-05}
  - {id: anonymize-replacement-values, status: resolved, rule: "rule 48", aspect: G, check: conformance, closed_world: true, resolved_by: abbc09d0, first_seen: 2026-10-05, last_verified: 2026-10-05}
  - {id: personal-data-inventory-ownership, status: open, aspect: C, cost: [tax, ambiguity],
     members_diverging: [auth, backups, billing, blog, crm, forms, listings, notifications],
     population: modules-with-user-data(9), check: review, closed_world: false, handoff: [arch],
     first_seen: 2026-10-05, last_verified: 2026-10-05}
  - {id: anonymize-executor-naming, status: resolved, rule: "rule 48", aspect: D, check: conformance, closed_world: true, resolved_by: abbc09d0, first_seen: 2026-10-05, last_verified: 2026-10-05}
  # prior items — all resolved; rule numbers are decisions.md § Module Conventions
  - {id: write-effects-on-commit, status: resolved, rule: "rule 21", aspect: F, check: "review + per-module rollback test", closed_world: false, resolved_by: 2eb63262, first_seen: 2026-09-26, last_verified: 2026-10-05}
  - {id: settings-snapshot-readers, status: resolved, rule: "rule 42", aspect: B, check: conformance, closed_world: true, resolved_by: 537204bc, first_seen: 2026-10-03, last_verified: 2026-10-05}
  - {id: optional-sender-guard, status: resolved, rule: "rule 43", aspect: C, check: conformance, closed_world: true, resolved_by: 537204bc, first_seen: 2026-10-03, last_verified: 2026-10-05}
  - {id: mount-path-copies, status: resolved, rule: "rule 41", aspect: A, check: "conformance (rules 7, 31, 37)", closed_world: true, resolved_by: a621299b, first_seen: 2026-10-03, last_verified: 2026-10-05}
  - {id: org-role-check-copies, status: resolved, rule: "rule 44", aspect: E, check: conformance+review, closed_world: false, resolved_by: 6b4fd1eb, first_seen: 2026-10-03, last_verified: 2026-10-05}
  - {id: mypy-overrides-unread, status: resolved, rule: "rule 45", aspect: N, check: conformance, closed_world: true, resolved_by: 6b4fd1eb, first_seen: 2026-10-03, last_verified: 2026-10-05}
  - {id: split-facade-conventions, status: resolved, rule: "rule 46", aspect: L, check: "conformance (rules 19, 28) + review", closed_world: false, resolved_by: 46d99cdb, first_seen: 2026-10-03, last_verified: 2026-10-05}
  - {id: theme-module-presence, status: resolved, rule: "rule 31", aspect: P, check: conformance, closed_world: false, resolved_by: a621299b, first_seen: 2026-09-28, last_verified: 2026-10-05}
  - {id: module-lists-outside-members, status: resolved, rule: "rule 37", aspect: L, check: conformance, closed_world: false, resolved_by: a621299b, first_seen: 2026-09-28, last_verified: 2026-10-05}
  # 41 items of passes 1–6, resolved at or before c10b529e and held by the harness at 8e4122f2:
  # see the reconciliation log (§12) for each ID, its rule and its resolving commit.
```

---

## 3. Summary table

**Counts (open):** defect 0 · collision 0 · ambiguity 0 · tax 1 · total 1. Prior: 53 resolved, 0
regressed.

| ID | Aspect | Cost | Diverging / population | Status |
|---|---|---|---|---|
| `anonymize-redaction-helper-copies` | C | defect, tax | 2 / 5 handlers | resolved (see §12, rule 47) |
| `anonymize-replacement-values` | G | ambiguity, tax | 2 / 5 handlers | resolved (see §12, rule 48) |
| `personal-data-inventory-ownership` | C | tax, ambiguity | 8 / 9 modules with user data | open |
| `anonymize-executor-naming` | D | tax | 1 / 5 handlers | resolved (see §12, rule 48) |
| `write-effects-on-commit` | F | — | 0 / 6 | resolved (correction, see §12) |
| 49 other prior items | A–P | — | 0 | resolved |

---

## 4. Aspect sections (this delta's population: anonymization handlers)

Aspects of the 12-module population whose tables did not change in this delta are in the
inventory's sections 1–47. The harness re-verified them at `8e4122f2`.

### 4.1 Handler shape (D, public surface)

| Aspect | Value → members |
|---|---|
| Executor signature on `AppConfig` | `anonymize_account(self, user, original_email, original_name, original_username) -> None` → all 5 |
| Capability | `anonymize_handlers() -> (self,)` → all 5 |
| Private module | `_anonymization.py` → all 5 |
| Private entry-point name | `anonymize_account` → billing, blog, notifications, orgs (4) · `scrub_account` → auth (1) |
| Other roles in the same file | none → 4 · the anonymize-hook collector (`discover_anonymize_hooks`, `_require_obligation_owners`) → auth (1) |
| Logging | none → auth, billing, notifications, orgs (4) · `getLogger("quickscale_modules_blog.apps")` (the caller's channel, per rule 46) → blog (1) |

*Already consistent (keep):* the executor signature, the capability, the lazy import of the
private module from `apps.py`, and passing the pre-scrub identity so handler order does not
matter.

*Drift:* the private entry-point name (Item 4).

### 4.2 Replacement values (G / A)

| Field kind | `deleted-<pk>@invalid` | `[redacted]` | `deleted-<pk>` |
|---|---|---|---|
| Sign-in or unique address (`User.email`, `Invitation.email`) | auth, orgs (2) | — | — |
| Username | — | — | auth (1) |
| Address inside a stored provider payload | notifications (`_scrub_event_payloads`) (1) | billing (`_redact_string`) (1) | — |
| Address inside rendered free text | notifications (messages) (1) | — | — |
| Name or username inside text or payload | — | billing, notifications (2) | — |
| Provider error text | — | notifications (`failure_reason`, wholesale) (1) | — |

The tokens are defined 4 times: `REDACTED = "[redacted]"` in billing and notifications, and
`f"deleted-{user.pk}@invalid"` written inline in auth, orgs, and notifications.

*Already consistent (keep):* `deleted-<pk>@invalid` for every address field with a unique or
sign-in meaning, and `[redacted]` for names.

*Drift:* the same kind of field, an address inside a stored provider payload, gets a different
token in billing and in notifications (Item 2).

### 4.3 Matching (C, shared behaviour)

| Aspect | billing | notifications |
|---|---|---|
| `_ADDRESS_PATTERN`, `_QUOTE_CHARS`, `_identity_form`, `_replace_addresses` | own copy | own copy (**byte-identical** bodies, verified by `diff`) |
| Name match | bare case-insensitive substring (`re.sub(re.escape(name), …)`) | word-bounded `(?<![A-Za-z0-9_])…(?![A-Za-z0-9_])` |
| Username | not redacted | redacted, word-bounded |
| Dict keys | rewritten through `_redact_string` | — |
| HTML-escaped spellings / entity chain (`8649849c`) | not applied (payloads are JSON, so this is consistent by design; see §9) | applied |

auth and orgs match by row (`user=`, `email__iexact`), and blog by profile row, so they have no
text matching.

*Drift:* Item 1.

### 4.4 Personal-data ownership (C, vocabulary)

| Where a module's personal-data fields are declared | Members |
|---|---|
| A row in `orgs/tests/_personal_data_inventory.py` | auth (8 rows), backups (3), billing (6), blog (9), crm (6), forms (5), listings (1), notifications (10), orgs (4) |
| The module's own package | none |

The handler that applies each treatment lives in the module. The list that says what to treat
lives in orgs' tests, and module-extension.md does not mention it.

*Drift:* Item 3.

### 4.5 Write effects (F)

The table is unchanged from inventory §23, plus blog. All 6 modules with effects schedule them
with `transaction.on_commit` and have a rollback or on-commit test. notifications' rollback test
is `tests/test_services.py:325–341`, and its `dispatch_after_commit` escape hatch has been
removed. No drift remains (see the correction in §12).

---

## 5. Drift items (ranked: defect > collision > ambiguity > tax)

### Item 1: Matching — the two text scrubbers are copies that have already diverged

- **Resolved** (SA245, `abbc09d0`) — recorded as rule 47; core's `replace_address`/`redact_names`
  are the one matcher.
- **ID:** `anonymize-redaction-helper-copies`
- **Aspect / population:** C (vocabulary and helper ownership); the anonymization handlers (5),
  of which 2 match text (billing, notifications).
- **Table:** §4.3. The address helpers are identical copies in 2 of 2. Name matching differs:
  bare substring in billing, word-bounded in notifications. Username is redacted in notifications
  only.
- **Drift:** One routine was copied rather than shared, and the copies have already split. The
  word-boundary and username handling that notifications gained in `8649849c` never reached
  billing.
- **Cost class:**
  - **Defect.** For an account named `Bill`, billing turns the payload
    `{"billing_details": …, "description": "Billing plan"}` into
    `{"[redacted]ing_details": …, "description": "[redacted]ing plan"}`. This was re-executed on
    the live function in this pass. It is the tech audit's `billing-anonymize-name-substring`
    (S4).
  - **Tax.** The next module that stores identity text (forms submissions are the likely one)
    has two examples to copy, and the wrong one is shorter.
- **Declared rule:** none. No Module Conventions rule covers how anonymization matches.
- **Options:**
  - **A.** One shared matcher in `quickscale_core.runtime` (for example
    `quickscale_core.runtime.redaction`). notifications must stay importable without orgs, and
    core is the only layer both modules may import (rule 5). This keeps one fix point, at the
    cost of a new core public surface.
  - **B.** Keep per-module code but put the matcher in a shared test-fixture table that both
    modules' tests must pass (a contract test). There is no new surface, but the code is still
    duplicated.
  - **C.** Keep the two copies and add a harness clause that fails when the two sets of function
    bodies differ. This is cheap but freezes duplication.
- **Recommended rule (A):**
  - ✅ A module that removes a person's identity from stored text or payloads uses core's
    redaction helpers (`replace_address`, `redact_names`). Names and usernames match at word
    boundaries, and keys of a structured payload are never rewritten.
  - ❌ A module-local copy of an address pattern or identity matcher. ❌ Substring name matching.
- **Enforcement:** a harness clause that rejects any module source assigning a regex containing
  `@` to a module-level name, and any `re.sub(re.escape(name)…` with no boundary. This is
  open-world. Control case: a fixture module with billing's current `_redact_string`. The
  behaviour itself is held by one test table in core (namesake, overlapping address, quoted
  address, key untouched).
- **Migration:** billing and notifications move to the core helper. This is not a one-way door,
  because already-scrubbed rows stay scrubbed. Add a release-notes line only if billing's stored
  payloads are re-scrubbed.
- **Confidence:** High. Both files were read in full, the identical bodies were diffed, and the
  defect was reproduced.
- **Hand-off:** tech (already recorded as `billing-anonymize-name-substring`; no new line), and
  arch (where a shared redaction surface lives, and the arch audit's own lead).

### Item 2: Replacement values — one kind of field, two tokens

- **Resolved** (SA245, `abbc09d0`) — recorded as rule 48; every handler writes core's
  `DELETED_ADDRESS(pk)` or `REDACTED`.
- **ID:** `anonymize-replacement-values`
- **Aspect / population:** G (data basics) and A (shared values); the anonymization handlers (5).
- **Table:** §4.2. The address inside a stored provider payload becomes `deleted-<pk>@invalid` in
  notifications and `[redacted]` in billing. The tokens are spelled in 5 places.
- **Drift:** A support engineer or an export reading a scrubbed payload cannot tell from the value
  which account it was, or whether it was scrubbed. The two modules answer differently for the
  same kind of data.
- **Cost class:**
  - **Ambiguity.** `[redacted]` loses the account link that `deleted-<pk>@invalid` keeps, so
    the same question has two answers depending on the module.
  - **Tax.** A sixth handler has no rule to follow.
- **Declared rule:** none. decisions.md's account-removal model says "anonymized in place" without
  naming values, and the inventory's `note` strings are the only record.
- **Options:**
  - **A.** Every address, wherever stored, becomes `deleted-<pk>@invalid`, and every name or
    username becomes `[redacted]`. Both tokens are constants in one core module. This keeps
    provenance, and billing changes one argument.
  - **B.** Address fields with a unique meaning get `deleted-<pk>@invalid`, and addresses inside
    text or payloads get `[redacted]`. notifications changes 2 call sites. The trade-off is that
    payloads lose the account link.
- **Recommended rule (A):**
  - ✅ An anonymization handler writes `DELETED_ADDRESS(pk)` for any email address and `REDACTED`
    for any name or username, importing both from core.
  - ❌ A literal `"[redacted]"` or `f"deleted-{…}@invalid"` in module code.
  - Exception: `failure_reason`, which is replaced wholesale because provider prose can embed the
    address in unknown forms. It keeps `REDACTED`.
- **Enforcement:** a harness clause, closed-world over string literals in `_anonymization.py`:
  any literal starting `deleted-` or equal to `[redacted]` fails. Control case: billing's current
  `REDACTED = "[redacted]"`.
- **Migration:** billing (1 call site) and the 4 inline spellings. This is not a one-way door.
- **Confidence:** High. Every handler was read in full.
- **Hand-off:** none.

### Item 3: Personal-data ownership — every module's rows live in orgs' tests

- **ID:** `personal-data-inventory-ownership`
- **Aspect / population:** C (vocabulary ownership); the modules with user-linked fields (9).
- **Table:** §4.4. Rows for 8 other modules, plus orgs' own, sit in
  `orgs/tests/_personal_data_inventory.py`.
- **Drift:** A module author who adds a user field to, say, forms must edit orgs' test file. The
  authoring guide (module-extension.md §removal) does not say so. The failing test, in a module
  the author did not touch, is the only signal.
- **Cost class:**
  - **Tax.** The rule cannot be found by the person who must follow it (§3.5).
  - **Ambiguity.** The treatment that forms' code applies is declared by orgs, so a reader of
    forms cannot see it.
- **Declared rule:** none. SA242 created the inventory, and no Module Conventions rule names it.
- **Options:**
  - **A.** Each module declares its rows as a capability or a manifest block (`personal_data:`),
    and the test collects them through `collect_capabilities`, as with `anonymize_handlers`. The
    test stays closed-world.
  - **B.** Keep one file but move it to a neutral home (`tests_shared/`), and link it from
    module-extension.md's checklist. This is cheaper, but ownership is still central.
- **Recommended rule (A):**
  - ✅ A module declares the personal-data treatment of each of its own user-linked fields, next
    to the handler that applies it.
  - ❌ One module's test file listing another module's fields.
- **Enforcement:** the existing closed-world inventory test, re-pointed at the collected
  declarations. Its three control cases carry over.
- **Migration:** 8 modules gain a declaration, and the orgs file shrinks to orgs, contrib, and
  third-party rows. This is test-time only, so it is not a one-way door.
- **Confidence:** High. Rows were counted by script, and the guide was searched.
- **Hand-off:** arch. This item is the convention side of `personal-data-coverage-shipped-only`
  (arch Finding 2), and the inventory's home and reach are that finding's root.

### Item 4 (compact): `anonymize-executor-naming`

**Resolved** (SA245, `abbc09d0`) — recorded as rule 48; auth's entry point is
`_anonymization.anonymize_account` and the collector is in `_anonymize_boundary.py`.

D · handlers 5 · the private entry point is `anonymize_account` in 4 and `scrub_account` in auth
(1). auth's `_anonymization.py` also holds the cross-module collector, so the file is both a
handler and the boundary · rule: ✅ `_anonymization.anonymize_account` in every handler, with the
collector in auth's own `_anonymize_boundary.py` · check: a harness clause, closed-world (an
`apps.anonymize_account` must delegate to `_anonymization.anonymize_account`) · Confidence High.

---

## 6. Proposed rules (for decisions.md § Module Conventions, as rules 47–49)

47. **Redaction (Item 1).** — recorded as decisions rule 47 (SA245, `abbc09d0`).
    - ✅ Identity is removed from stored text and payloads by core's redaction helpers. Names and
      usernames match at word boundaries, and payload keys are never rewritten.
    - ❌ A module-local address pattern or identity matcher. ❌ Substring name matching.
48. **Replacement values (Items 2 and 4).** — recorded as decisions rule 48 (SA245, `abbc09d0`).
    - ✅ Every email address becomes core's `DELETED_ADDRESS(pk)`, and every name or username
      becomes `REDACTED`.
    - ✅ A handler's private entry point is `_anonymization.anonymize_account`.
    - ❌ A literal sentinel in module code.
    - Exception: wholesale-replaced provider prose keeps `REDACTED`.
49. **Personal-data declarations (Item 3).** — remains proposed (SA246).
    - ✅ A module declares the treatment of its own user-linked fields beside its handler, and
      the inventory test collects the declarations.
    - ❌ One module's test listing another module's fields.

---

## 7. Enforcement gaps

1. **Anonymization has no Module Conventions rule.** module-extension.md states the declaration
   shape, but no rule covers matching, values, or file roles (Items 1, 2, 4).
2. **Undiscoverable rule.** The personal-data inventory is not mentioned in module-extension.md
   or the authoring checklist (Item 3).
3. **Stale term.** module-extension.md line 189 still says "auth's account-deletion collector"
   after SA216(c) renamed the boundary to *anonymize* (`dfd6214e`).
4. **Delegated rules are hard to see.** Rules 41 and 46 have no detector of their own. Their
   clauses ride rules 7/31/37 and 19/28, and only a comment in the partition test says so
   (`test_check_module_conventions.py:7282`). The harness's success line ("40 covered") does not
   list 41 or 46, so a reader cannot tell "delegated" from "missing".
5. **Carried from the inventory** (accepted, 2026-10-02): `test_isolation.py` does not
   self-enroll; rule 38's README match is a substring floor; the generated `base.py` lets a module
   override `anon`/`user` throttle rates.

---

## 8. Consistent by design

- **Entity-chain handling (`8649849c`) is in notifications only.** notifications stores
  Django-rendered HTML, while billing stores provider JSON with no HTML escaping. The fix belongs
  where the escaping happens. If Item 1's shared helper is adopted, HTML spellings stay an opt-in
  of notifications.
- **orgs, auth, and blog do no text matching.** They own the person's rows outright, so they
  delete or overwrite by key.
- **crm, forms, listings, and backups declare no handler.** Every one of their rows is `KEEP_LINK`
  (provenance to the retained, disabled account), so they have nothing to execute.
- **blog's anonymization logs on `quickscale_modules_blog.apps`.** That is the caller's channel,
  as rule 46 requires for private files.
- **`quickscale_orgs_create_site_org` has no `--dry-run`.** It is idempotent and creates only, so
  rule 17's `--dry-run` duty (destructive commands) does not apply.

---

## 9. Hand-offs

**To the technical audit:**
- (none new) `billing-anonymize-name-substring` is already open there, and this pass re-confirmed
  it by execution.

**To the architectural audit:**
- `anonymize-redaction-helper-copies`: where a shared redaction surface lives, given that
  notifications must not import orgs.
- `personal-data-inventory-ownership`: per-module declaration of personal data, which is the
  convention side of `personal-data-coverage-shipped-only`.

---

## 10. Aspect catalogue additions

- **G/A · Anonymization replacement values.** The sentinel each handler writes, per field kind.
- **C · Shared scrub/redaction behaviour.** Matcher copies, boundary semantics, key handling.
- **C · Personal-data declaration ownership.** Who lists a module's personal-data fields.
- **D · Delegated-rule visibility.** Rules whose clauses run inside other rules' detectors.

---

## 11. Questions that would change a rule

- Should a scrubbed provider payload keep the account link (`deleted-<pk>@invalid`) or lose it
  (`[redacted]`)? This decides Item 2's option A vs B.
- Will forms submissions or crm contacts ever be treated as the user's personal data, rather than
  the organization's? A yes adds a third text scrubber and raises Item 1's urgency.

---

## 12. Reconciliation log

- 2026-10-05 — **Location.** The coherence audit moves from
  `docs/planning/module-conventions-inventory.md` (passes 1–8) to this file. The inventory's index
  and log are frozen at `c10b529e`, and every prior ID continues below.
- 2026-10-05 — `anonymize-redaction-helper-copies`: **new**, open (lead from the arch audit's
  Coherence hand-offs).
- 2026-10-05 — `anonymize-replacement-values`: **new**, open.
- 2026-10-05 — `personal-data-inventory-ownership`: **new**, open.
- 2026-10-05 — `anonymize-executor-naming`: **new**, open.
- 2026-10-05 — `anonymize-redaction-helper-copies`: **resolved** (abbc09d0 — rule 47; core's
  `replace_address`/`redact_names` are the one matcher, and the control case rejects billing's old
  `_redact_string`).
- 2026-10-05 — `anonymize-replacement-values`: **resolved** (abbc09d0 — rule 48; all five handlers
  write core's `DELETED_ADDRESS(pk)` and `REDACTED`, and the control case rejects billing's old
  `REDACTED = "[redacted]"`).
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
