# Context Hydration Refactor — Next Steps

> **You are here**: [QuickScale](../../START_HERE.md) → [Docs](../index.md) → **Planning** → Context Hydration Refactor
> **Related docs**: [adaptive.rules.md](../../adaptive.rules.md) | [AI Hydration Topology](../technical/ai_hydration_topology.md) | [AI Context Baseline](../technical/ai_context.md)

## Current State (2026-05-01)

The seven-phase context hydration refactor is complete. The root `adaptive.rules.md` now uses a compact `ai_context.md` as the universal shared baseline, with role-specific documents added only where they materially change behavior. Payloads dropped from 117–128 KB per role to 4–18 KB. See [AI Hydration Topology](../technical/ai_hydration_topology.md) for the full validation snapshot and governance rules.

## Remaining Problems

### 1. Sub-Package Rules Files Are All Identical Boilerplate

All seven sub-package `adaptive.rules.md` files (under `quickscale/`, `quickscale_core/`, `quickscale_cli/`, `quickscale_modules/`, `scripts/`, `docs/`, and `examples/`) share the same structure:

- A `# Shared` section pointing to the local README as "Important context (always read)"
- Seven role sections that each just `[include](#shared)` with no local content

These files add no domain-specific rules. They exist as structural placeholders. When an agent works in any of these directories, it gets told to read a README — and those READMEs uniformly say "defer to root docs for policy." The agent follows a pointer to a document that sends it back where it started.

This is the same anti-pattern the root refactor fixed: injecting human navigation documents as default AI context, except now it happens at the sub-package level through the "always read" hint mechanism rather than through inline includes.

### 2. The "Always Read README" Pattern Is Circular

Package READMEs are documented in `ai_context.md` and `decisions.md` as "informational context only" that does not override technical authorities. Pointing the AI to read them as priority context in every sub-package domain works against the authority model, not with it.

A README for `quickscale/` that says "this installs core and CLI together" and "defer to root docs for policy" is not useful local context. It is a nav stub. Hydrating it as if it were domain-critical guidance wastes attention and contradicts the refactor's own principles.

### 3. `ai_context.md` Has No Drift Detection

`ai_context.md` is a derivative summary of `decisions.md` and companion docs. If those canonical sources change without a corresponding update to `ai_context.md`, the AI gets an authoritative-looking stale summary. The refactor documents this risk and relies entirely on human discipline ("update this file to stay aligned"). There is no mechanism that makes the drift visible.

---

## Recommended Changes

### Phase A — Give Sub-Package Files Meaningful Local Rules

Replace the "always read README" pattern in each sub-package `adaptive.rules.md` with concrete domain-local rules. Remove the README pointers. Add rules that are actually specific to working in that directory.

Recommended content for each file:

#### `quickscale/adaptive.rules.md` — Meta-Package

This package has no implementation logic. It is a dependency declaration bundle.

```
# Shared
- This is the installation meta-package. It has no implementation code; it only
  declares the combined quickscale-core and quickscale-cli dependency bundle.
- The only meaningful changes here are version pins in pyproject.toml.
- Do not add application logic under quickscale/src/; changes there affect the
  import shim only.
```

Role additions:
- **Implement**: "Changes in this package are almost always version pin updates in `pyproject.toml`. If anything else needs changing, question the scope."
- **Quality Gate**: "This package has minimal test coverage by design — it contains no implementation to test."

#### `quickscale_core/adaptive.rules.md` — Scaffolding Engine

```
# Shared
- Source lives at quickscale_core/src/quickscale_core/.
- This is the scaffolding engine. Changes here affect the output of every generated project.
- Template changes require regeneration testing — verify that a fresh plan/apply cycle
  produces valid output.
- Tests live at quickscale_core/tests/. Run make test-unit to validate.
```

Role additions:
- **Implement**: "Template edits in `src/quickscale_core/generator/` affect generated-project output. Treat template changes as user-facing contract changes."
- **Quality Gate**: "After any template change, verify generated project structure against `docs/technical/generated_project_structure.md`."

#### `quickscale_cli/adaptive.rules.md` — CLI Surface

```
# Shared
- Source lives at quickscale_cli/src/quickscale_cli/.
- This package is the command surface only. Business logic belongs in quickscale_core.
- CLI commands are grouped: lifecycle (plan, apply, status, remove), disaster recovery
  (dr capture/plan/execute/report), local dev (up, down, ps, logs, shell, manage),
  deployment (deploy), and module workflows (update, push).
- Tests live at quickscale_cli/tests/.
```

Role additions:
- **Implement**: "New commands belong here. New scaffolding or generation logic belongs in `quickscale_core`. Do not put template or generation logic in CLI handlers."
- **Plan**: "CLI commands call into `quickscale_core` for heavy lifting. Scope CLI work to command wiring, argument parsing, and user-facing output."

#### `quickscale_modules/adaptive.rules.md` — Module Workspace

```
# Shared
- This is the maintainer-side module inventory. It is not generated into user projects by default.
- Each module directory under quickscale_modules/<name>/ is independently packaged.
- module.yml is the canonical source for a module's shipped version and configuration metadata.
  The module's pyproject.toml version and exported __version__ must match the manifest.
- Modules are distributed to generated projects via the documented git-subtree workflow.
  Do not copy module files manually into generated project directories.
- Packaged modules: auth, blog, crm, forms, listings, analytics, social, storage, backups.
  Placeholder-only (no tests/packaging yet): billing, teams.
```

Role additions:
- **Implement**: "For packaged modules, `module.yml` owns version metadata. Update it in the same change as any version bump."
- **Quality Gate**: "Each packaged module has its own test suite. Run the module-specific test target (`make MODULE=<name> test-unit -- --modules`) rather than the root test suite for module-scoped work."

#### `scripts/adaptive.rules.md` — Repository Scripts

```
# Shared
- Scripts in this directory are maintenance and workflow helpers.
- Always prefer the root Makefile as the entrypoint. Call a script directly only when
  no make target exists or a script header says otherwise.
- Scripts expect to be run from the repository root. Repo-relative paths will break if
  a script is run from a subdirectory.
- Do not add a new script if a make target already covers the same workflow.
```

Role additions:
- **Implement**: "New automation belongs in the Makefile first. Add a script only when the logic is too complex for a make target."
- **Plan**: "Check whether an existing make target or script already covers the need before designing a new one. See `scripts/README.md` for the full preferred-command map."

#### `docs/adaptive.rules.md` — Documentation

```
# Shared
- This directory has two audiences: human contributors and AI hydration.
- Human-first documents: README.md, START_HERE.md, contrib/contributing.md,
  contrib/shared/README.md. Do not optimize these for AI consumption.
- AI hydration documents: docs/technical/ai_context.md is the compact AI baseline;
  docs/technical/decisions.md is the policy authority; other technical docs
  are role-specific includes governed by ai_hydration_topology.md.
- When editing docs, decide which audience owns the file first. Do not add
  AI-specific shortcuts to human-first docs, and do not add human navigation
  tours to AI-hydrated files.
```

Role additions:
- **Implement**: "Before adding a new doc, decide: is it human-first or AI-hydration context? Add it to the right category and update `ai_hydration_topology.md` if it changes hydration."
- **Change Review**: "Doc changes that touch `adaptive.rules.md`, `ai_context.md`, or `ai_hydration_topology.md` require a hydration-metrics check per the governance requirements in `ai_hydration_topology.md`."

#### `examples/adaptive.rules.md` — Examples

```
# Shared
- Examples are reference material, not authoritative product scope.
- Examples are not generated into projects by default unless a workflow explicitly says otherwise.
- Treat examples as patterns that can be selectively copied, not as tested components.
- Do not add examples that imply features or constraints that are not in the main product.
```

Role additions:
- **Implement**: "Examples should be minimal and copyable. If an example grows into a tested module, it belongs in `quickscale_modules/`, not here."
- **Change Review**: "New examples must not contradict the generated project contract in `docs/technical/generated_project_structure.md`."

---

### Phase B — Address `ai_context.md` Drift Risk

The current approach relies on human discipline: "update the authoritative doc first, then update `ai_context.md`." This is fragile.

**Option 1 — Inline the critical facts into `adaptive.rules.md` directly.**
For the two roles that only need the compact baseline (`adaptive` and `external-research`), the shared content is small enough to live inline in the root rules file. This removes the sync obligation entirely for the most-read roles. The risk is that `adaptive.rules.md` grows back toward boilerplate.

**Option 2 — Add a lint step that checks `ai_context.md` is consistent with its sources.**
A script that validates `ai_context.md` references match existing files and that key constant values (stack baseline, make targets) appear in both `ai_context.md` and `decisions.md`. This is mechanical verification, not semantic correctness, but it makes obvious drift visible in CI.

**Option 3 — Accept the risk and document it explicitly at the top of `ai_context.md`.**
Acknowledge in the file header that this is a best-effort derivative, that it may lag behind canonical sources, and that agents should treat any conflict with `decisions.md` as authoritative immediately — even before `ai_context.md` is corrected. This is the lowest-effort option and is honest about the limitation.

Recommendation: **Option 3 now, Option 2 as a follow-on** if drift actually causes problems. Option 1 trades one maintenance risk for another.

---

### Phase C — Document the "Always Read" vs `[include]` Mechanism Distinction

The root `adaptive.rules.md` uses `[include](path)` which inlines file content into the hydrated payload. Sub-package files currently use a markdown list under "Important context (always read)" which is a read hint — the agent is told to fetch those files on demand, not inline them.

These are meaningfully different mechanisms with different cost profiles. Neither `ai_hydration_topology.md` nor any other governance document explains the distinction. This matters because:

- Inline includes expand the measured hydrated payload.
- "Always read" hints expand context on demand, which may happen at the wrong time or not at all.

The governance documentation should clarify which mechanism is canonical for which use case, and whether sub-package files should use `[include]` for consistency or whether "always read" hints are intentionally chosen.

---

## Summary of Recommended Actions

| Action | File(s) to change | Priority |
|---|---|---|
| Replace README pointers with domain-local rules | All 7 sub-package `adaptive.rules.md` files | High — these are currently noise |
| Add role-specific local rules to each sub-package file | Same files | High — currently all sections are empty |
| Add explicit drift disclaimer to `ai_context.md` | `docs/technical/ai_context.md` | Medium — makes the known risk visible |
| Document `[include]` vs "always read" distinction | `docs/technical/ai_hydration_topology.md` | Medium — needed for maintainer clarity |
| Evaluate a lint check for `ai_context.md` consistency | New script or Makefile target | Low — only if drift actually causes problems |

---

## Implementation Plan

### Phase A — Sub-Package Rules Files

Each task below is an independent edit to one file. They can be done in any order.

#### `quickscale/adaptive.rules.md`

- [x] Remove the `- **Important context (always read)**:` block and its `quickscale/README.md` and `quickscale/pyproject.toml` list items from `# Shared`.
- [x] Add the meta-package identity note to `# Shared`: state that this is the installation meta-package with no implementation code, that it only declares the combined core+CLI dependency bundle, and that `pyproject.toml` version pins are the only meaningful changes here.
- [x] Add the import-shim guard to `# Shared`: state that changes under `quickscale/src/` affect only the import shim, so application logic must not be added there.
- [x] Add to `# Implement`: scope guard stating that changes here are almost always version pin updates in `pyproject.toml`, and that anything beyond that should prompt a scope question.
- [x] Add to `# Quality Gate`: note that this package has minimal test coverage by design because it contains no implementation to test.

#### `quickscale_core/adaptive.rules.md`

- [x] Remove the `- **Important context (always read)**:` block and its README/pyproject list items from `# Shared`.
- [x] Add to `# Shared`: source path (`quickscale_core/src/quickscale_core/`), identity as the scaffolding engine, and the consequence that changes here affect every generated project's output.
- [x] Add to `# Shared`: test location (`quickscale_core/tests/`) and the instruction to run `make test-unit` to validate.
- [x] Add to `# Implement`: template-change contract rule — edits in `src/quickscale_core/generator/` are user-facing contract changes and require regeneration testing (fresh `plan`/`apply` cycle).
- [x] Add to `# Quality Gate`: post-template-change verification rule — after any template change, confirm generated project structure matches `docs/technical/generated_project_structure.md`.

#### `quickscale_cli/adaptive.rules.md`

- [x] Remove the `- **Important context (always read)**:` block and its README/pyproject list items from `# Shared`.
- [x] Add to `# Shared`: source path (`quickscale_cli/src/quickscale_cli/`), identity as the command surface only, and the boundary rule that business logic belongs in `quickscale_core`.
- [x] Add to `# Shared`: the command group taxonomy (lifecycle, disaster recovery, local dev, deployment, module workflows) so the agent understands the existing surface without reading the README.
- [x] Add to `# Shared`: test location (`quickscale_cli/tests/`).
- [x] Add to `# Implement`: placement rule — new commands belong here, new generation or scaffolding logic belongs in `quickscale_core`; do not put template logic in CLI handlers.
- [x] Add to `# Plan`: scope boundary reminder — CLI work is command wiring, argument parsing, and user-facing output; `quickscale_core` does the heavy lifting.

#### `quickscale_modules/adaptive.rules.md`

- [x] Remove the `- **Important context (always read)**:` block and its README list item from `# Shared`.
- [x] Add to `# Shared`: identity statement — this is the maintainer-side module inventory, not generated into user projects by default.
- [x] Add to `# Shared`: the `module.yml` ownership rule — it is the canonical source for shipped version and configuration metadata; `pyproject.toml` version and exported `__version__` must match the manifest.
- [x] Add to `# Shared`: distribution rule — modules reach generated projects via the git-subtree workflow; do not copy module files manually.
- [x] Add to `# Shared`: the packaged vs placeholder distinction, listing which modules are fully packaged (auth, blog, crm, forms, listings, analytics, social, storage, backups) and which are placeholder-only (billing, teams).
- [x] Add to `# Implement`: `module.yml` sync rule — update `module.yml` in the same change as any version bump.
- [x] Add to `# Quality Gate`: module-scoped test target instruction — use `make MODULE=<name> test-unit -- --modules` for module-scoped validation instead of the root test suite.

#### `scripts/adaptive.rules.md`

- [x] Remove the `- **Important context (always read)**:` block and its README list item from `# Shared`.
- [x] Add to `# Shared`: Makefile-first rule — always prefer root `make` targets; call scripts directly only when no matching target exists or a script header says otherwise.
- [x] Add to `# Shared`: working directory constraint — scripts expect to be run from the repository root; repo-relative paths break when run from a subdirectory.
- [x] Add to `# Shared`: redundancy guard — do not add a new script if a `make` target already covers the same workflow.
- [x] Add to `# Implement`: Makefile-first automation rule — new automation belongs in the Makefile first; add a script only when the logic is too complex for a make target.
- [x] Add to `# Plan`: discovery step — check whether an existing make target or script already covers the need before designing a new one; reference `scripts/README.md` for the preferred-command map.

#### `docs/adaptive.rules.md`

- [x] Remove the `- **Important context (always read)**:` block and its `docs/index.md` list item from `# Shared`.
- [x] Add to `# Shared`: the two-audience rule — this directory serves human contributors and AI hydration; they have separate documents and must not be mixed.
- [x] Add to `# Shared`: the human-first document list (README.md, START_HERE.md, contrib/contributing.md, contrib/shared/README.md) with the instruction not to optimize those for AI consumption.
- [x] Add to `# Shared`: the AI hydration document roles — `ai_context.md` is the compact AI baseline, `decisions.md` is the policy authority, other technical docs are role-specific includes governed by `ai_hydration_topology.md`.
- [x] Add to `# Implement`: audience-decision rule — before adding a new doc, classify it as human-first or AI hydration context, add it to the right category, and update `ai_hydration_topology.md` if it changes hydration.
- [x] Add to `# Change Review`: governance gate — doc changes that touch `adaptive.rules.md`, `ai_context.md`, or `ai_hydration_topology.md` require a hydration-metrics check per the governance requirements in `ai_hydration_topology.md`.

#### `examples/adaptive.rules.md`

- [x] Remove the `- **Important context (always read)**:` block and its README list item from `# Shared`.
- [x] Add to `# Shared`: examples identity — reference material, not authoritative product scope, not generated into projects by default.
- [x] Add to `# Shared`: usage rule — treat examples as patterns that can be selectively copied, not as tested components.
- [x] Add to `# Shared`: scope guard — do not add examples that imply features or constraints that are not in the main product.
- [x] Add to `# Implement`: promotion rule — if an example grows into a tested module, it belongs in `quickscale_modules/`, not here.
- [x] Add to `# Change Review`: contract consistency check — new examples must not contradict the generated project contract in `docs/technical/generated_project_structure.md`.

---

### Phase B — `ai_context.md` Drift Risk

- [ ] Add an explicit drift disclaimer at the top of `docs/technical/ai_context.md` — immediately below the opening paragraph — stating that this file is a best-effort derivative, that it may lag behind canonical sources, and that any conflict with `decisions.md` or companion technical docs resolves in favor of those canonical sources immediately, before this file is corrected.
- [ ] *(deferred)* Evaluate a lightweight lint script that verifies `ai_context.md` references resolve to existing files and that key constant values (make targets, stack baseline entries) still appear in both `ai_context.md` and `decisions.md`. Only pursue this if real drift causes a problem first.

---

### Phase C — Mechanism Documentation

- [ ] Add a `## Mechanism Reference` section to `docs/technical/ai_hydration_topology.md` that explains the two hydration mechanisms side by side:
  - `[include](path)` — inlines file content into the measured hydrated payload at hydration time; use this for files where the content is always needed and should be counted in size budgets.
  - `"Important context (always read)"` list — surfaces a read hint alongside the payload; the agent fetches the file on demand, not at hydration time; the content does not appear in inline hydration metrics.
- [ ] Add guidance on which mechanism to use when: inline includes for role-critical policy and structure files; read hints for supplementary local context that may or may not be needed depending on the task.
- [ ] Update the existing `## Final Include Rationale` table in `ai_hydration_topology.md` to add a `Mechanism` column distinguishing between `[include]` entries and any "always read" pointer entries, so the inventory is complete and unambiguous.
