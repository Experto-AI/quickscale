# Coherence Audit — Open Items

Audited: `39d455ef` (v89) · 2026-10-20 · working tree dirty (`docs/others/arch-audit.md`,
`docs/others/tech-audit.md`: companion reports, excluded from the source basis) · visibility unknown ·
prompt: deep-coherence-audit v3 · passes: 2 · stopping reason: bounded re-run; the second pass
added no item.

Cross-module conformance drift against [module_conventions.md](../technical/module_conventions.md#module-conventions).
The last full census was `30b0b6b1` (2026-10-16): 41 of 41 resolved. Census tables and pass history
are in git history. Cite an item by its slug ID, a proposed rule as "coherence proposal N", and a
gap as "coherence gap N". These numbers come from the 2026-10-16 census and stay fixed until the
entry closes.

## Orientation and coverage

- **Population:** `modules`, the 12 first-party modules under `quickscale_modules/` (analytics, auth,
  backups, billing, blog, crm, forms, listings, notifications, orgs, social, storage). Discovered
  from the filesystem and checked against `scripts/module_conventions/registry.py`. Sub-population
  `commands`: 17 command modules in 4 modules (backups 9, billing 1, forms 2 plus 2 helpers, orgs 4).
- **Rules and how they're enforced:** `module_conventions.md` is the authoritative rule set. Its
  numbered rules are parsed by `registry.py` and checked by `scripts/module_conventions/` and
  `scripts/tests_module_conventions/`. Per the audit rules these checks were inspected, not run.
- **Delta since `30b0b6b1`:** 334 non-merge commits; 140 files changed under `quickscale_modules/`
  and the conventions checker grew a lot (`_settings_manifest.py`, `_routes_http_apis.py`,
  `rule_44.py`). This re-run did **not** re-census that delta aspect by aspect.
- **This run's coverage:**

  | Aspect × population | Activation | Coverage |
  |---|---|---|
  | J (commands) × commands | active | complete for flags `--json`/`--trigger`/`--dry-run`/`--confirm`/`--organization-id` |
  | C/A (core knows module names) × modules | active | partial: one anchor rechecked |
  | A, B, D–I, K–V × modules | unassessed this run | last complete on 2026-10-16; the delta was not re-swept |
  | P (frontend) | unassessed | not inspected |

  **Leftover risk:** the delta could have introduced drift that the conventions gate doesn't
  detect. A full re-census of the 2026-10-16 tables against `39d455ef` would close this.

## Machine-readable index

```yaml
schema: coherence-audit/v2
prompt: deep-coherence-audit/v3
audited: "39d455efb17c156ac0ced7d3a3ee260573ca0724"
snapshot_basis: "HEAD 39d455ef; dirty paths are companion audit reports only, excluded"
schema_migration: "prior report had no index; IDs and gap numbers preserved"
populations:
  - {id: modules, size: 12, inspected: 12, unknown: 0, discovery: "quickscale_modules/* + registry.py"}
  - {id: commands, size: 17, inspected: 17, unknown: 0, discovery: "*/management/commands/*.py"}
coverage:
  - {population: commands, aspect: J, activation: active, coverage: complete}
  - {population: modules, aspect: C, activation: active, coverage: partial}
  - {population: modules, aspect: "A,B,D-I,K-V", activation: unassessed, reason: "delta not re-swept"}
items:
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
    first_seen: "2026-10-13"
    last_verified: "2026-10-20"
gaps:
  - {id: 21, rule: 17, state: open, last_verified: "2026-10-20"}
```

## Summary

| ID | Kind | Aspect / population | Cost | Status | Verification |
|---|---|---|---|---|---|
| `core-cli-module-knowledge` | drift | C / modules | tax | accepted | confirmed 2026-10-20 |

Current confirmed open items: **0**. Prior items left unverified: 0. Pending candidates: 0.
Open enforcement gaps: 1.

## Commands (aspect J) — table

| Flag duty (rule 17) | Members | Evidence |
|---|---|---|
| Operator-scheduled → `--trigger` | backups `create`, `prune`; forms `anonymize_submissions` (3/3 named in a README Operations section) | backups README Operations; forms README |
| Deletes / anonymizes / overwrites → `--dry-run` | backups `prune`, `restore`, `sync_media`; billing `reconcile_checkouts`; forms `anonymize_submissions`; orgs `promote_to_saas`, `purge_organization` | flag census |
| Cross-tenant delete → `--confirm` | backups `restore`, orgs `purge_organization` | flag census |
| Org selector `--organization-id` | billing `reconcile_checkouts`, orgs `purge_organization` (orgs also has the `--slug` preflight that rule 17 allows) | flag census |
| `--format` / `--org` / `--scheduled` spellings | 0 | flag census |

**Already consistent (keep):** the whole table above.

**Consistent by design:** billing passes the selector straight to `filter(pk=...)` and turns
`ValidationError`/`ValueError` into a `CommandError`. orgs parses it with `uuid.UUID` first. Since
`Organization.id` is a `UUIDField`, both produce the same result: a malformed value fails cleanly.
`quickscale_billing_reconcile_checkouts` is run by an operator after an upgrade or a refused
purge, not on a schedule (its docstring and the README's Management commands section), so it has
no `--trigger`.

## Enforcement gaps

21. **Rule 17's remaining flag clauses.** Still open, reverified 2026-10-20. `--json` is never
    required, and `--trigger` is checked only when present (`_package_commands.py:141`). The
    detector keys the destructive duty on the name of the operation the command calls
    (`_is_destructive_operation`, `_package_commands.py:264`). So a command that picks its
    operation from a computed name is outside it: `quickscale_backups_pin` calls
    `ADAPTER_FUNCTIONS[operation](**kwargs)` (line 14), and the DR bridge does the same. No
    command currently breaks rule 17 because of this; it's a hole in the guard, not an item.
    Proposed control cases: the detector should reject a fixture command that calls
    `ADAPTER_FUNCTIONS[name]` with a destructive `name` and has no `--dry-run`, and accept the
    same fixture once `--dry-run` is added. Unscheduled.

## Accepted

- `core-cli-module-knowledge`: core/CLI name module-specific vocabulary for 6 of 12 modules.
  Rechecked 2026-10-20: `contracts/module_options.py` still names analytics, backups, billing,
  notifications, social, storage, and `manifest/social_manifest.py` still exists. Accepted
  2026-10-13. Tracked structurally by the arch watchlist item `core-holds-module-vocabulary`.

## Hand-offs

- *To the technical audit:* none.
- *To the architectural audit:* `core-cli-module-knowledge` (linked; already on the watchlist).

## Remaining work

Re-census aspects A, B, D–I and K–V across the 12 modules against `39d455ef`, starting with the
modules that changed most since `30b0b6b1` (orgs 27 files, billing 12, forms 11, blog 10).

## Reconciliation log

- 2026-10-20 — gap 21: still-open (reverified at `_package_commands.py:141,264`; `backups_pin` line 14).
- 2026-10-20 — `core-cli-module-knowledge`: accepted (decision 2026-10-13; trigger: arch watchlist `core-holds-module-vocabulary`).
- 2026-10-20 — the 41 items resolved on 2026-10-16: their resolution was not re-checked in this bounded run (delta not re-swept); prior `resolved` status stands.
