# Coherence Audit — Open Items

Cross-module conformance drift against [decisions.md § Module Conventions](../technical/decisions.md#module-conventions).
Last verified at `30b0b6b1` (2026-10-16), full census. Open items only: resolved items (40 of 41),
census tables and pass history are in git history. Cite an item by its slug ID, a proposed rule as "coherence proposal N", and a gap as "coherence
gap N". These numbers come from the 2026-10-16 census and stay fixed until the entry closes.

## Open items

### `cli-module-name-branches` — module-name branches in the CLI outside rule 37's list
**Class:** ambiguity + tax · **Confidence:** High

- **Drift.** Rule 37 forbids an equality branch on a module name in core or the CLI outside its
  listed exceptions. The harness (`scripts/module_conventions/_identity_module_lists.py`)
  matches only `ast.Eq`/`ast.NotEq`, so `in` and `.get("<m>")` branches pass. SA287 (a) closed
  the option-validation trio: `commands/_config.py` (orgs) and `apply_support.py` plus
  `commands/_plan_validation.py` (notifications) now judge every configured module through its
  manifest's declared checks and take module-specific remediation text from the generic
  `option_validation_guidance` adapter hook. Two unlisted sites remain, both operator
  next-steps text: `commands/_finalize.py` (backups, notifications, analytics, social, billing)
  and `commands/_runtime.py` (backups).
- **Fix.** Operator next-steps text either becomes listed rule-37 exceptions or moves the same
  way. Extend `RULE_37_BRANCH_OPERATORS` to `ast.In`/`ast.NotIn` and to `.get()`/subscript with
  a module-name constant. Control fixture: `if "billing" in modules:`.
- **Related:** arch watchlist `core-holds-module-vocabulary`.

## Proposed rules (pending merge into decisions.md § Module Conventions)

51. **CLI module knowledge** [`cli-module-name-branches`]. ✅ The CLI reaches module-specific
    behaviour through a manifest field or a generic adapter hook. ❌ A membership, `.get()`, or
    equality branch on a module name in core or the CLI outside rule 37's list. (SA287)

## Open enforcement gaps (SA296)

17. **Rule 30 vs. composition order.** Rule 30 forbids settings whose value depends on
    module-name order, yet `INSTALLED_APPS` and `MIDDLEWARE` compose in module-name order
    (`_sort_module_items`). No defect today: auth's `AccountMiddleware` happens to sort before
    orgs' `TenantMiddleware`. Fix: explicit `before`/`after`, or the rule names the exception.
21. **Rule 17's remaining flag clauses.** `--json` is never required, and `--trigger` is
    checked only when present (`_package_commands.py`). The destructive duty is now keyed on
    the operation named in the command's own code and `--dry-run` is a declared-flag check
    (SA296 (b)); a command that resolves its operation from a computed name (the backups DR
    bridge's `ADAPTER_FUNCTIONS.get(function_name)`) stays outside that detector and remains
    uncovered here.
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
