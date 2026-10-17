# Coherence Audit — Open Items

Cross-module conformance drift against [decisions.md § Module Conventions](../technical/decisions.md#module-conventions).
Last verified at `30b0b6b1` (2026-10-16), full census. Open items only: resolved items (38 of 41),
census tables and pass history are in git history. Cite an item by its slug ID, a proposed rule as "coherence proposal N", and a gap as "coherence
gap N". These numbers come from the 2026-10-16 census and stay fixed until the entry closes.

## Open items

### `cli-module-name-branches` — module-name branches in the CLI outside rule 37's list
**Class:** ambiguity + tax · **Confidence:** High

- **Drift.** Rule 37 forbids an equality branch on a module name in core or the CLI outside its
  listed exceptions. The harness (`scripts/module_conventions/_identity_module_lists.py`)
  matches only `ast.Eq`/`ast.NotEq`, so `in` and `.get("<m>")` branches pass. There are 5
  unlisted sites: `commands/_finalize.py` (backups, notifications, analytics, social, billing),
  `commands/_config.py` (orgs), `commands/_runtime.py` (backups), and `apply_support.py` plus
  `commands/_plan_validation.py` (notifications).
- **Fix.** Option validation goes behind manifest fields or generic adapter hooks
  (`_config`, `_plan_validation`, `apply_support`). Operator next-steps text either becomes
  listed rule-37 exceptions or moves the same way. Extend `RULE_37_BRANCH_OPERATORS` to
  `ast.In`/`ast.NotIn` and to `.get()`/subscript with a module-name constant. Control
  fixture: `if "billing" in modules:`.
- **Related:** arch watchlist `core-holds-module-vocabulary`.

### `startup-presence-guard-copies` — checks re-test projected-setting presence
**Class:** tax · **Confidence:** Medium

- **Drift.** analytics, billing and notifications `checks.py` repeat the
  `projected_setting_names` + `hasattr` guard that the generic settings check
  (`runtime/conventions.py`) already enforces.
- **Fix.** Rule: a module check MUST NOT re-test a projected setting's presence. Check: a
  rule-6 AST scan.

## Proposed rules (pending merge into decisions.md § Module Conventions)

51. **CLI module knowledge** [`cli-module-name-branches`]. ✅ The CLI reaches module-specific
    behaviour through a manifest field or a generic adapter hook. ❌ A membership, `.get()`, or
    equality branch on a module name in core or the CLI outside rule 37's list. (SA287)
55. **Manifest owns validation and throttle rates** [`startup-presence-guard-copies`]. ✅ Adapters
    evaluate the declared validation, and core merges declared throttle scopes. ❌ `re.compile`, a
    `DEFAULT_THROTTLE_RATES` literal in `adapter.py`, or a presence re-check in `checks.py`.
    (SA291)

## Open enforcement gaps (SA296)

17. **Rule 30 vs. composition order.** Rule 30 forbids settings whose value depends on
    module-name order, yet `INSTALLED_APPS` and `MIDDLEWARE` compose in module-name order
    (`_sort_module_items`). No defect today: auth's `AccountMiddleware` happens to sort before
    orgs' `TenantMiddleware`. Fix: explicit `before`/`after`, or the rule names the exception.
20. **Rule 40 claims checks that do not exist.** No detector checks `CommandError` or
    `BaseCommand`, and none checks "unlisted core ports". The rule 28 file allowlist is the only
    indirect guard.
21. **Rule 17's destructive duty keys on command-name keywords.** `--dry-run` is matched as a
    substring, so a command named `_reset` or `_wipe` passes. `--json` is never required, and
    `--trigger` is checked only when present (`_package_commands.py`).
22. **Rules 5 and 34 skip a module missing from `MODULE_LAYERS`.** Only a pytest backstops
    this, and the decisions.md layer table is never compared with `MODULE_LAYERS`.
23. **Capability declarations are open-world.** A misspelled capability on an `AppConfig` is
    never flagged, and the harness and core each keep a literal set with no cross-check.
24. **Clauses with no detector:** rule 13's `TenantModelAdmin` registration and rule 11's
    compare-against-members clause.
25. **The authoring checklist contradicts the code.**
    [module-extension.md § Building a Module](../technical/module-extension.md#building-a-module-authoring-checklist)
    says core is edited "in exactly these places and no others". A React- or API-bearing module
    also edits the seam tables (`runtime/seam.py`) and `runtime/urls.py`, and the checklist never
    mentions choosing a rule 5 layer or adding the `MODULE_LAYERS` entry.

## Accepted

- `core-cli-module-knowledge`: core/CLI name 6 of 12 modules (`contracts/module_options.py`,
  `social_manifest.py`, …). Accepted 2026-10-13. Tracked structurally by the arch watchlist item
  `core-holds-module-vocabulary`.
