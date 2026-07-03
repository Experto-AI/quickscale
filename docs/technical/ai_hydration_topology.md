# AI Hydration Topology And Governance

> **You are here**: [QuickScale](../../START_HERE.md) -> [Technical](../index.md) -> **AI Hydration Topology And Governance**
> **Related docs**: [adaptive.rules.md](../../adaptive.rules.md) | [AI Context Baseline](ai_context.md)

This companion owns the current `adaptive.rules.md` topology, the rationale for each expanded hydrated input and docs-local always-read pointer, the latest validation snapshot, the role-level rollback map, and the governance rules for future include-graph edits. Technical facts remain authoritative in the documents named by [ai_context.md](./ai_context.md); this file governs the hydration graph itself.

<a id="final-include-rationale"></a>
## Final Include Rationale

Expanded hydrated includes captured in MCP payload line and size metrics:

| Input | Included by | Why it stays in hydration | Mechanism |
|---|---|---|---|
| [docs/technical/ai_context.md](./ai_context.md) | Root `# Shared` for every role | Keeps the universal authority order, workflow baseline, stack baseline, validation entrypoints, generated-project ownership rules, and derivative-summary maintenance policy in one compact file. | `[include]` |
| [docs/technical/generated_project_structure.md](./generated_project_structure.md) | `plan`, `codebase-discovery`, `implement` | These roles reason about generated-project output, managed-versus-user-owned boundaries, and generation guardrails. | `[include]` |
| [docs/technical/repository_layout.md](./repository_layout.md) | `plan`, `codebase-discovery`, `implement` | These roles need the maintainer-side package layout and naming/import matrix; other roles do not. | `[include]` |
| [docs/contrib/plan.md](../contrib/plan.md) | `plan` only | Keeps planning questions, scope discipline, and validation-planning reminders local to planning work. | `[include]` |
| [docs/contrib/code.md](../contrib/code.md) | `implement` only | Keeps implementation checklist and scope guardrails local to implementation work. | `[include]` |
| [docs/technical/validation_policy.md](./validation_policy.md) | `quality-gate` only | Keeps repository validation commands, coverage rules, isolation rules, and E2E policy local to validation work. | `[include]` |
| [docs/contrib/testing.md](../contrib/testing.md) | `quality-gate` only | Keeps QuickScale-specific test selection, locations, fixtures, and contamination reminders local to validation work. | `[include]` |
| [docs/contrib/debug.md](../contrib/debug.md) | `quality-gate` only | Keeps the debugging loop and failure-isolation workflow local to validation work. | `[include]` |
| [docs/contrib/review.md](../contrib/review.md) | `change-review` only | Keeps review checklist, evidence standards, and outcome language local to review work. | `[include]` |

Docs-local always-read pointers surfaced by MCP metadata, but not expanded into the measured hydrated payload:

| Pointer | Surfaced by | Why it stays available | Mechanism |
|---|---|---|---|
| [docs/index.md](../index.md) | Local `docs/adaptive.rules.md` important-context pointer for docs-scoped work | Preserves the minimal docs-local map that helps docs-relative work without reintroducing broad human-router content into the root shared baseline. | always-read |

Inputs intentionally excluded from the root shared baseline:

- [README.md](../../README.md), [START_HERE.md](../../START_HERE.md), and [docs/contrib/contributing.md](../contrib/contributing.md) remain human-first navigation and onboarding documents.
- [docs/contrib/shared/README.md](../contrib/shared/README.md) remains a human-facing authority map; the small amount of AI-critical authority framing it contributed now lives in [docs/technical/ai_context.md](./ai_context.md).
- The first rollback step for a single-role regression is to fix or revert the affected role block, not to widen the shared baseline for every role.

<a id="role-to-input-inventory"></a>
## Role-To-Input Inventory

| Role | Expanded hydrated inputs | Docs-local always-read pointer | Intended effect |
|---|---|---|---|
| `adaptive` | [docs/technical/ai_context.md](./ai_context.md) | [docs/index.md](../index.md) | Universal authority/workflow baseline only. |
| `plan` | [docs/technical/ai_context.md](./ai_context.md), [docs/technical/generated_project_structure.md](./generated_project_structure.md), [docs/technical/repository_layout.md](./repository_layout.md), [docs/contrib/plan.md](../contrib/plan.md) | [docs/index.md](../index.md) | Planning gets the shared baseline plus structure context and planning-specific guidance. |
| `codebase-discovery` | [docs/technical/ai_context.md](./ai_context.md), [docs/technical/generated_project_structure.md](./generated_project_structure.md), [docs/technical/repository_layout.md](./repository_layout.md) | [docs/index.md](../index.md) | Discovery gets structure context without any stage-guide payload it does not need. |
| `external-research` | [docs/technical/ai_context.md](./ai_context.md) | [docs/index.md](../index.md) | External research stays on the compact baseline unless a concrete research workflow proves otherwise. |
| `implement` | [docs/technical/ai_context.md](./ai_context.md), [docs/technical/generated_project_structure.md](./generated_project_structure.md), [docs/technical/repository_layout.md](./repository_layout.md), [docs/contrib/code.md](../contrib/code.md) | [docs/index.md](../index.md) | Implementation gets structure context plus only the implementation-stage checklist. |
| `quality-gate` | [docs/technical/ai_context.md](./ai_context.md), [docs/technical/validation_policy.md](./validation_policy.md), [docs/contrib/testing.md](../contrib/testing.md), [docs/contrib/debug.md](../contrib/debug.md) | [docs/index.md](../index.md) | Validation gets the compact baseline plus validation policy, testing, and debugging only. |
| `change-review` | [docs/technical/ai_context.md](./ai_context.md), [docs/contrib/review.md](../contrib/review.md) | [docs/index.md](../index.md) | Review gets the compact baseline plus evidence and review guidance only. |

<a id="mechanism-reference"></a>
## Mechanism Reference

Two distinct hydration mechanisms appear in the tables above. They have different cost profiles and are not interchangeable.

| Mechanism | Syntax | When content is loaded | Counted in hydration metrics |
|---|---|---|---|
| Inline include | `[include](path)` in `adaptive.rules.md` | At hydration time — content is expanded and inlined into the measured payload before the agent receives it | Yes — lines and size appear in the validation snapshot |
| Always-read pointer | A named item under `- **Important context (always read)**:` in a sub-package `adaptive.rules.md` | On demand — the agent receives a read hint alongside the payload and fetches the file when the task warrants it | No — content is not expanded at hydration time and does not appear in inline metrics |

**When to use each mechanism:**

- Use `[include]` for files where the content is unconditionally needed by that role — policy authorities, structure contracts, stage-specific guidance. If a role cannot function correctly without the file, inline it and count it in the budget.
- Use an always-read pointer for supplementary local context that is relevant in some tasks but not all, or for files that are too volatile or large to include inline. The agent fetches only when the task warrants it; the content never inflates the baseline payload.

**Why this matters for governance:** The hydration metrics in the validation snapshot only count `[include]` content. A role that relies heavily on always-read pointers may appear compact in the metrics while actually pulling in substantial context on demand. When auditing a role's true context footprint, account for both mechanisms.

<a id="must-have-facts-checklist"></a>
## Must-Have Facts Checklist

Before trimming, swapping, or widening any role input in [adaptive.rules.md](../../adaptive.rules.md) or [docs/adaptive.rules.md](../adaptive.rules.md), confirm that the affected role still hydrates the decision-critical facts below. This checklist is the maintained topology contract for future include-graph edits.

| Role | Must-have facts to preserve |
|---|---|
| `adaptive` | Authority order, conflict policy, workflow baseline, repo stack baseline, validation entrypoints, and generated-project ownership model. |
| `plan` | `adaptive` baseline plus structure authority, generated-project contract, scope discipline, and validation-planning expectations. |
| `codebase-discovery` | `adaptive` baseline plus structure authority, maintainer-repository layout context, and generated-project-versus-maintainer boundary guidance. |
| `external-research` | `adaptive` baseline only; do not add structure or stage-guide payload unless a concrete research workflow proves a missing fact. |
| `implement` | `adaptive` baseline plus structure authority, implementation guardrails, `make`/pytest entrypoints, and ownership boundaries for generated code. |
| `quality-gate` | `adaptive` baseline plus validation policy, coverage expectations, narrow-first validation commands, debug workflow, and review-handoff evidence expectations. |
| `change-review` | `adaptive` baseline plus evidence expectations, authority order, scope protection, and regression-review discipline. |

<a id="post-refactor-validation-snapshot"></a>
## Post-Refactor Validation Snapshot (2026-05-01; refreshed 2026-06-16 for Phase 2 / M2)

Hydration status was `configured` and `ready` before the metrics capture below. Metrics were captured by re-running MCP hydration against the current graph for every major role. The table measures expanded hydrated content only; docs-local "Important context (always read)" pointers such as [docs/index.md](../index.md) are metadata surfaced alongside the payload, not expanded content counted in these totals.

| Role | Phase 0 lines | Phase 0 size | Current lines | Current size | Delta from Phase 0 | Budget check | Validation note |
|---|---:|---:|---:|---:|---|---|---|
| `adaptive` | 2,507 | 117.0 KB | 93 | 4.9 KB | -2,414 lines, -112.1 KB | Pass | Shared authority/workflow baseline remains intact via [docs/technical/ai_context.md](./ai_context.md). |
| `plan` | 2,585 | 120.6 KB | 449 | 19.0 KB | -2,136 lines, -101.6 KB | Pass | Shared baseline plus generated-project, repository-layout, and planning guidance are present. |
| `codebase-discovery` | n/a | n/a | 404 | 17.0 KB | n/a | Informational | Shared baseline plus the two structure authorities only. |
| `external-research` | n/a | n/a | 93 | 4.9 KB | n/a | Informational | Intentionally limited to the shared baseline only. |
| `implement` | 2,661 | 122.2 KB | 447 | 19.0 KB | -2,214 lines, -103.2 KB | Pass | Shared baseline plus structure context and implementation guidance are present. |
| `quality-gate` | 2,875 | 128.6 KB | 408 | 16.6 KB | -2,467 lines, -112.0 KB | Pass | Shared baseline plus validation policy, testing, and debugging guidance are present. |
| `change-review` | 2,572 | 119.7 KB | 129 | 6.5 KB | -2,443 lines, -113.2 KB | Pass | Shared baseline plus review guidance are present. |

All role payloads are now below both their line and size targets.

<a id="m2-hydration-edit-rationale"></a>
### Phase 2 / M2 Hydration-Edit Rationale (2026-06-16)

[docs/technical/ai_context.md](./ai_context.md) was updated to reflect the M2 consolidated-state contract: `.quickscale/state.yml` is now described as the sole authoritative applied-state store with consolidated sub-sections for module-tracking metadata and managed-file drift records; legacy `config.yml` and `file_hashes.yml` are described as compatibility inputs only; advisory locking and `quickscale status` drift diagnostics are noted. [docs/technical/generated_project_structure.md](./generated_project_structure.md) was updated in the same change to align the State and Module Metadata section and the Crosswalk table with the M2 contract. No role include graph edges changed — only the content of two already-included files grew by a few lines each. The include topology, role-to-input inventory, must-have facts checklist, and rollback notes are unchanged.

<a id="validation-findings"></a>
## Validation Findings

- All seven major role hydrations succeeded from the current graph, so the include audit found no broken include paths.
- The root shared baseline is now one file, [docs/technical/ai_context.md](./ai_context.md), and no role section repeats a direct include path inside the same role block.
- Spot checks confirmed the intended coverage split for expanded payloads: `adaptive` and `external-research` stay on the compact baseline; `plan`, `codebase-discovery`, and `implement` add only the two structure authorities; `quality-gate` adds only validation policy, testing, and debugging; `change-review` adds only review guidance.
- Docs-scoped hydration also surfaces [docs/index.md](../index.md) as a local "Important context (always read)" pointer. That pointer remains available for follow-up reads, but it is not treated as an expanded hydrated include in the inventory or validation metrics above.
- The human-first docs remain coherent and distinct after the AI-focused trimming: [README.md](../../README.md) still functions as the project overview and quick start, [START_HERE.md](../../START_HERE.md) still functions as the decision-tree router, and [docs/contrib/contributing.md](../contrib/contributing.md) still functions as the contributor guide map and authority overview.
- No additional in-scope duplicate cleanup was required in this pass. The current graph and the phase-4 guide trims already removed the broad shared-stage framing duplication that was inflating hydration size earlier in the refactor.

<a id="rollback-notes"></a>
## Rollback Notes

Rollback should stay role-local whenever possible. Do not widen the shared baseline first when only one role regresses.

| If this regresses | First rollback step | Keep unchanged if possible |
|---|---|---|
| Shared authority/workflow facts for every role | Restore the missing fact in [docs/technical/ai_context.md](./ai_context.md) or revert the root `# Shared` change | Role-local stage guides and structure slices |
| `plan`, `codebase-discovery`, or `implement` loses a structure fact | Revert only the affected role block's [docs/technical/generated_project_structure.md](./generated_project_structure.md) and/or [docs/technical/repository_layout.md](./repository_layout.md) include change | `quality-gate`, `change-review`, and human docs |
| `implement` loses implementation-stage reminders | Revert only the [docs/contrib/code.md](../contrib/code.md) include in `Implement` | Shared baseline and validation/review slices |
| `quality-gate` loses validation depth | Revert only the [docs/technical/validation_policy.md](./validation_policy.md), [docs/contrib/testing.md](../contrib/testing.md), or [docs/contrib/debug.md](../contrib/debug.md) include change in `Quality Gate` | Shared baseline and planning/implementation slices |
| `change-review` loses evidence or checklist guidance | Revert only the [docs/contrib/review.md](../contrib/review.md) include change in `Change Review` | Shared baseline and validation slices |
| Docs-local context is insufficient for docs work | Revert only the relevant change in [docs/adaptive.rules.md](../adaptive.rules.md) | Root `# Shared` and the human-first router docs |

<a id="governance-requirements"></a>
## Governance Requirements

- The maintainer changing [adaptive.rules.md](../../adaptive.rules.md), [docs/adaptive.rules.md](../adaptive.rules.md), or [docs/technical/ai_context.md](./ai_context.md) owns the paired update to this file in the same change.
- Review the hydration topology whenever the include graph changes and at least once per release-note cycle when no topology edit lands.
- Future edits to [adaptive.rules.md](../../adaptive.rules.md), [docs/adaptive.rules.md](../adaptive.rules.md), or [docs/technical/ai_context.md](./ai_context.md) must include a short rationale plus updated hydration metrics for every affected role.
- Any newly introduced whole-file include above the provisional 20 KB threshold requires explicit rationale and a note explaining why a narrower companion file is not sufficient.
- During periodic review, confirm that each shared include is still universal, that each role-local include still earns its place, and that the role-to-input inventory above still matches the hydrated output.
- Keep the human-versus-AI boundary explicit: [README.md](../../README.md), [START_HERE.md](../../START_HERE.md), [docs/contrib/contributing.md](../contrib/contributing.md), and [docs/contrib/shared/README.md](../contrib/shared/README.md) stay human-first unless a future change documents a unique must-have fact that cannot live in a narrower AI-specific companion.
- Revisit the provisional budgets after two or three topology edits, or at the next release-cycle review, and tighten or relax them based on measured hydration quality instead of guesswork.
