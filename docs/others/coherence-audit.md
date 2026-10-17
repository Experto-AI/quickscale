# Coherence Audit — Open Items

Cross-module conformance drift against [decisions.md § Module Conventions](../technical/decisions.md#module-conventions).
Last verified at `30b0b6b1` (2026-10-16), full census. Open items only: resolved items (38 of 41),
census tables and pass history are in git history. IDs are slugs. Never cite them from code,
tests or other docs.

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

### `throttle-rate-merge-copies` — adapters hand-merge throttle rates
**Class:** tax · **Confidence:** High

- **Drift.** The billing, blog, forms, listings and orgs `adapter.py` each hand-merge
  `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES`.
- **Fix.** A manifest `throttle_scopes` projection that core merges. Ban
  `DEFAULT_THROTTLE_RATES` in adapters.

## Accepted

- `core-cli-module-knowledge`: core/CLI name 6 of 12 modules (`contracts/module_options.py`,
  `social_manifest.py`, …). Accepted 2026-10-13. Tracked structurally by the arch watchlist item
  `core-holds-module-vocabulary`.
