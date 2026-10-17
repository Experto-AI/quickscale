# Coherence Audit — Open Items

Cross-module conformance drift against [decisions.md § Module Conventions](../technical/decisions.md#module-conventions).
Last verified at `30b0b6b1` (2026-10-16), full census. Open items only: resolved items (41 of 41),
census tables and pass history are in git history. Cite an item by its slug ID, a proposed rule as "coherence proposal N", and a gap as "coherence
gap N". These numbers come from the 2026-10-16 census and stay fixed until the entry closes.

## Open items

None: the 2026-10-16 census is fully resolved (41 of 41).

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
