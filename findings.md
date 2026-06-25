# Structural Autopsy: QuickScale

## Orientation

**What it is.** A creator-led Django *project generator* (`quickscale plan` → `quickscale apply`) plus a workspace of ~13 first-party Django modules (`quickscale_modules/{orgs,crm,billing,blog,forms,listings,social,notifications,storage,backups,analytics,auth,teams}`). Generated projects copy modules into a local `modules/` dir and become **user-owned code** ("no vendor lock-in"). The CLI/generator lives in `quickscale_cli` + `quickscale_core`.

**Near-term growth direction.** The dominant work of the last ~10 releases is **retrofitting multi-tenant isolation** (`F11.2`–`F11.13b`) onto every module, plus a `solo` → `saas` runtime mode (`v0.86.0` orgs) and org-authoritative billing (`F13/M9`). The product is mid-pivot from a single-user scaffold into a multi-tenant SaaS substrate. Every finding below sits on a seam that pivot just stressed.

The single most important structural fact (now resolved): multi-tenant isolation was enforced in application convention, not at the data layer. Track 1 (T1.1–T1.16) closed this — contextvar `TenantManager` + Postgres FORCE RLS on all six module table sets are now the data-layer guarantee.

**Implementation notes:** no backward compatibility, no migration path, no existing users — every change is a clean break. Squash/rewrite migrations; drop dead paths outright.

**Findings 1, 2, 4, and 5** are fully resolved and removed from this document. See CHANGELOG M12 (F5/DR), M13–M18 (Track 1 / tenant isolation + ownership + routing). **Finding 3** is partially resolved — tracked below.

---

## Finding 3 — Adding a module requires coordinated edits across ~8 sites; T2.3/T2.4 resolved the CLI wiring bottleneck, but the module-catalog tuple remains hardcoded

**STATUS: PARTIAL** — T2.3/T2.4 (M14) deleted all per-module CLI adapters and the implication-defaults ladder; generic resolver is operational. Residual: `quickscale_core/src/quickscale_core/contracts/module_catalog.py` static `MODULE_CATALOG` tuple still hardcoded — tracked in roadmap Deferred/Monitor for retirement.

**Time horizon: <6 months** *(was)*

**Problem.** Module identity is not owned in one place — it's spread between the module's own source, the core catalog tuple, and the generator. T2.3/T2.4 eliminated the CLI's per-module Python adapters, the implication-defaults ladder, and the CLI catalog re-export shim, but the core module-catalog tuple still requires per-module edits.

**Why it compounds.** Each new module is a coordination tax: (1) `models.py` org FK + migration, (2) `managers.py` dual-manager, (3) dual-route `views.py`, (4) isolation tests, (5) a `pyproject.toml` dep, and (6) a hardcoded entry in the core `MODULE_CATALOG` tuple. The per-module CLI adapters, the implication-defaults ladder, and the CLI catalog shim have all been deleted — the CLI now resolves modules generically — but the core catalog still must be hand-edited.

**Evidence.**
- T2.3 deleted all 12 `quickscale_cli/src/quickscale_cli/*_manifest.py` adapter files; all callers now route through `quickscale_core.manifest.resolver`.
- T2.4 deleted the implication-defaults helper (`get_implied_module_default_configs`) and the `quickscale_cli.module_catalog` re-export shim.
- `quickscale_core/src/quickscale_core/contracts/module_catalog.py` still contains a hardcoded `MODULE_CATALOG` tuple listing all 13 modules by name, though it is now supplemented by manifest-backed dynamic discovery (`module_discovery.py`).

**Correct shape.** The CLI already resolves modules generically with zero per-module branches. The remaining gap is the hardcoded `MODULE_CATALOG` tuple in core — it should be retired in favor of the already-existing manifest-backed discovery as the sole authoritative inventory.

**Selected: T2.3/T2.4 completed the CLI-wiring half; the residual debt is the static catalog tuple.**
The per-module CLI Python adapters, the implication-defaults ladder, and the CLI catalog shim have been deleted. The `resolve_module_implications()` function and generic resolver are operational. What remains: `quickscale_core.contracts.module_catalog.MODULE_CATALOG` is still a hardcoded tuple — retire it and rely on dynamic discovery from `module.yml` files exclusively.

**Trigger for urgency.** The next module addition that requires both a new `module.yml` **and** a hand-edit to the static catalog tuple — a sign the catalog still acts as a manual registry.

**Detection signal.** A diff that touches both a new `module.yml` and `contracts/module_catalog.py` for the same logical module addition. That redundant edit is the residual tax.
