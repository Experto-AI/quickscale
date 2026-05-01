# Context Hydration Refactor Review And Implementation Plan

> **You are here**: [QuickScale](../../START_HERE.md) → [Docs](../index.md) → **Planning** → Context Hydration Refactor
 > **Related docs**: [adaptive.rules.md](../../adaptive.rules.md) | [Technical Decisions](../technical/decisions.md) | [Scaffolding](../technical/scaffolding.md) | [Contributing](../contrib/contributing.md) | [AI Hydration Topology And Governance](../technical/ai_hydration_topology.md)

## Goal

Review the current MCP hydration inputs defined in [adaptive.rules.md](../../adaptive.rules.md), identify what should be preserved versus trimmed, and define a phased implementation and hardening plan to make AI context smaller, clearer, safer, and more DRY.

Unless a later section says otherwise, the opening review below records the Phase 0 pre-refactor baseline captured on 2026-05-01. The phase sections later in this document track the current post-phase-2/3/4 source state separately.

## Phase 0 Pre-Refactor Baseline Snapshot

At the start of this refactor, the root `# Shared` section in [adaptive.rules.md](../../adaptive.rules.md) included:

- [docs/technical/decisions.md](../technical/decisions.md)
- [docs/technical/scaffolding.md](../technical/scaffolding.md)
- [README.md](../../README.md)
- [START_HERE.md](../../START_HERE.md)
- [docs/contrib/contributing.md](../contrib/contributing.md)
- [docs/contrib/shared/README.md](../contrib/shared/README.md)

The stage sections then added:

- [docs/contrib/plan.md](../contrib/plan.md)
- [docs/contrib/code.md](../contrib/code.md)
- [docs/contrib/testing.md](../contrib/testing.md)
- [docs/contrib/debug.md](../contrib/debug.md)
- [docs/contrib/review.md](../contrib/review.md)

Observed Phase 0 costs from that setup:

- The current referenced source set is about 3,133 lines before hydration.
- Current measured role baselines captured on 2026-05-01 range from 2,507 lines / 117.0 KB (`adaptive`) to 2,875 lines / 128.6 KB (`quality-gate`).
- The MCP include mechanism expands whole files, not file fragments, so large documents amplify context size quickly.
- Human-facing navigation and onboarding content is now being injected into every agent role, including roles that do not need it.

## Executive Summary

The pre-refactor include-driven hydration model was directionally correct and much better than path-only reminders. It gave the coding assistant the actual text instead of requiring iterative follow-up reads.

The problem at that baseline was that the include graph had overshot into broad whole-file inclusion. The result was that each role received a mix of authoritative rules, human onboarding material, duplicated authority statements, and repeated stage-guide framing. That increased token cost, expanded latency, and raised drift risk without adding proportional decision value.

The target state should preserve the strengths of the current documentation system while narrowing default AI context to the smallest set of decision-critical facts. Human navigation documents should remain valuable for contributors, but they should not be part of the default hydration baseline for coding assistants.

## Bird's-Eye Hardening Review

From a bird's-eye perspective, the repository has already solved the first-order problem: the MCP can now hydrate real context instead of returning a path-only reading list. The next problem is second-order hardening. The system must now be resistant to regression, ownership drift, role contamination, and accidental context bloat.

### Overall Assessment

| Area | Current state | Hardening assessment | Direction |
|---|---|---|---|
| Context delivery model | Strong foundation | Correct mechanism, but currently over-expanded | Preserve and tighten |
| Authority model | Clear in theory | Duplicated across too many documents | Consolidate ownership |
| Role isolation | Weak | Too much shared context crosses role boundaries | Enforce per-role minima |
| Performance budget | Weak | No explicit size or line-budget guardrails | Add measurable budgets |
| Change safety | Weak-to-moderate | No formal rollback, acceptance, or non-regression framework yet | Add rollout controls |
| Include graph governance | Weak | Includes work, but there is no strong maintenance contract yet | Add ownership and review cadence |
| Human versus AI document boundary | Blurry | Human router docs are being used as AI execution docs | Separate responsibilities |
| Long-term maintainability | Moderate | Good conceptual model, incomplete operational discipline | Harden with policy and review loops |

### Hardening Lens

The refactor should be evaluated against these control objectives:

1. **Determinism**: the same role should hydrate the same critical facts reliably.
2. **Minimality**: each role should receive the smallest context bundle that still preserves correctness.
3. **Single ownership**: each rule, precedence statement, and workflow constraint should have one canonical owner.
4. **Role isolation**: planning, implementation, quality, and review contexts should not all inherit the same broad human-router payload.
5. **Observability**: context size, critical-fact coverage, and include topology should be inspectable before and after changes.
6. **Reversibility**: the refactor should be deployable in stages and easy to roll back if context quality regresses.
7. **Human-doc preservation**: human-facing docs should remain readable and useful instead of being contorted around AI constraints.
8. **Maintenance discipline**: future contributors should have a clear rule for how and where to update hydrated context.

## Strong Points To Preserve

### 1. Include-Driven MCP Hydration

This is the right mechanism.

Why it is strong:

- The assistant receives the actual text, not a list of files to read later.
- The hydration result is deterministic and easier to reason about.
- The system avoids extra search and read steps during task execution.
- Shared sections like `[include](#shared)` already give a good DRY foundation.

Preserve:

- External include usage as the primary hydration strategy.
- Same-file shared anchors for DRY reuse.
- Explicit role sections in [adaptive.rules.md](../../adaptive.rules.md).

### 2. `decisions.md` As The Primary SSOT

This remains the most important document to preserve as the authority source.

Why it is strong:

- It clearly owns technical rules, scope, and tie-breakers.
- It already contains high-value AI-relevant material such as quick reference, critical rules, current contract, document responsibilities, and testing policy.
- It provides clear conflict resolution across the repository.

Preserve:

- `decisions.md` as the authoritative technical source.
- The rule that scope and policy updates start there first.
- Its role as the conflict resolver when lower-priority docs differ.

### 3. `scaffolding.md` As The Structure Authority

This document is useful and should remain authoritative for layout and placement.

Why it is strong:

- It explains repository layout, generated-project layout, and naming/placement examples.
- It complements `decisions.md` cleanly when used for structural questions.
- It is valuable for planning, discovery, and implementation roles.

Preserve:

- `scaffolding.md` as the structure and layout reference.
- Its distinction from `decisions.md`, which owns policy and tie-breakers.

### 4. Shared Rules Versus Stage Guides

The split between `docs/contrib/shared/` and `docs/contrib/*.md` is conceptually correct.

Why it is strong:

- Shared documents define normative rules that apply across stages.
- Stage guides define applied checklists, commands, and examples for a specific kind of work.
- The model is already understandable and aligned with good documentation separation.

Preserve:

- Shared docs as the normative layer.
- Stage guides as application-layer docs.
- The rule that shared docs win if there is a conflict.

### 5. Repo-Specific Applied Guidance In Stage Guides

The best parts of the stage guides are the parts that are actually specific to QuickScale.

Examples worth keeping:

- Planning checklist and planning questions in [docs/contrib/plan.md](../contrib/plan.md)
- Implementation checklist and scope guardrails in [docs/contrib/code.md](../contrib/code.md)
- Test decision tree, commands, fixtures, and contamination pitfalls in [docs/contrib/testing.md](../contrib/testing.md)
- Debugging loop and focused commands in [docs/contrib/debug.md](../contrib/debug.md)
- Review checklist and required evidence in [docs/contrib/review.md](../contrib/review.md)

Preserve:

- The checklist-style, task-oriented content.
- Repo-specific commands, placements, and failure-analysis workflows.
- The distinction between normative rules and applied execution help.

## Weak Points And Refactor Pressure

### 1. Shared Includes Are Too Broad

The current `# Shared` block includes both core policy docs and human router docs.

Why this is weak:

- [README.md](../../README.md) and [START_HERE.md](../../START_HERE.md) are primarily human orientation documents.
- [docs/contrib/contributing.md](../contrib/contributing.md) is a contributor map and guide index.
- [docs/contrib/shared/README.md](../contrib/shared/README.md) largely explains the shared/stage-guide model rather than adding high-signal task constraints.
- These documents are now injected into roles like `external-research`, `quality-gate`, and `change-review` where most of that routing material is unnecessary.

Impact:

- Hydrated context becomes large quickly.
- Roles spend context budget on navigation copy instead of constraints and task-relevant guidance.
- Signal-to-noise ratio drops.

### 2. Authority And Precedence Statements Are Repeated Too Many Times

The same messages appear in several places:

- `decisions.md` is authoritative.
- Package READMEs are informational only.
- Shared docs win over stage guides.
- Execution order is not prescribed.

Why this is weak:

- Duplication increases maintenance overhead.
- The same rule must be updated in multiple files.
- AI context burns tokens repeating precedence rules instead of giving execution help.
- Drift becomes more likely over time.

### 3. Whole-File Includes Make Large Docs Expensive

The include engine expands whole files, not file-section fragments.

Why this matters:

- [docs/technical/decisions.md](../technical/decisions.md) is very large.
- [docs/technical/scaffolding.md](../technical/scaffolding.md) is also large.
- The only reliable way to reduce hydration size is to split documents or change which files are included.

Implication:

- Refactoring must focus on file decomposition and include boundaries, not only wording cleanup.

### 4. Stage-Guide Boilerplate Repeats Across Files

Most stage guides repeat the same framing structure:

- `Use This Guide When`
- `Authoritative Sources`
- `Related Guidance`
- sometimes `Exit Criteria`

Why this is weak:

- Once a compact shared baseline exists, these repeated introductions add little value.
- The high-value parts of the guides are the applied checklists, commands, pitfalls, and examples.
- The framing copy is informative for humans but low-value for repeated AI hydration.

### 5. Testing And Debugging Guidance Is Split In Ways That Invite Duplication

Testing and debugging policy currently spans multiple layers:

- Repo-wide testing policy lives in [docs/technical/decisions.md](../technical/decisions.md)
- Cross-stage norms live in `docs/contrib/shared/`
- Repo-specific commands and recipes live in [docs/contrib/testing.md](../contrib/testing.md) and [docs/contrib/debug.md](../contrib/debug.md)

Why this is weak:

- The boundary between normative policy and applied execution is not as sharp as it could be.
- Similar guidance appears in multiple places.
- Contributors and agents may over-read when one narrower document would suffice.

### 6. Generic Educational Examples Compete With Real Repo Constraints

[docs/contrib/code.md](../contrib/code.md) contains some generic examples that teach broad engineering habits more than QuickScale-specific implementation behavior.

Why this is weak:

- Generic examples consume context budget.
- They are less useful than concrete repository constraints and local patterns.
- They are better suited for optional human reference than default hydrated context.

### 7. Human Router Documents Are Valuable, But Not As Default AI Inputs

[README.md](../../README.md), [START_HERE.md](../../START_HERE.md), and [docs/contrib/contributing.md](../contrib/contributing.md) remain useful documents.

Why they should not be default AI context:

- They explain where to go next more than they define what to do now.
- They repeat authority and navigation guidance already covered elsewhere.
- They are optimized for people reading the docs, not for role-specific agent execution.

## Hardening Risks And Failure Modes

The current document already identifies duplication and context bloat. For hardening, those issues need to be translated into concrete failure modes that future implementation work can guard against.

| Risk | Typical trigger | Failure symptom | Operational impact | Required control |
|---|---|---|---|---|
| Shared-context relapse | A future editor adds more whole-file includes to `# Shared` for convenience | Hydrated size jumps sharply across all roles | Latency, higher token cost, lower signal-to-noise | Shared-context size budget plus change-review gate |
| Authority inversion | A new AI summary file drifts from `decisions.md` or shared docs | Assistant follows stale or conflicting rules | Wrong implementation or review decisions | Explicit owner contract and backlink to canonical source |
| Role contamination | Human router or unrelated stage guidance is included broadly | `quality-gate` or `change-review` receives planning or onboarding prose | Reduced role precision and wasted context | Per-role coverage matrix and tighter include boundaries |
| Over-trimming | Cleanup removes a critical rule while shrinking size | Assistant misses a required command, ownership rule, or validation expectation | Regressed behavior despite smaller context | Must-have-facts checklist per role |
| Include graph fragility | Files are renamed, split, or moved without include updates | Hydration fails or silently degrades to missing context | Broken agent workflows and brittle maintenance | Include inventory and post-change audit step |
| Ownership vacuum | New AI-focused files are added without a maintenance rule | No one knows which file to update first | Drift and duplicated policy over time | Written maintenance contract in the new baseline file |
| Human-doc collateral damage | Docs are rewritten primarily for AI optimization | README and contributor docs become less useful to people | Higher contributor friction | Preserve separate human and AI document responsibilities |
| Silent duplication persistence | Extracted files are created but old copies of the same rule remain | Same policy still appears in multiple sources | Drift risk remains even after refactor effort | One-owner cleanup pass before rollout completes |

## Hardening Controls And Guardrails

Hardening the context system is not only about rewriting content. It also requires explicit controls that make future regressions visible.

### 1. Budget Controls

Define explicit soft and hard budgets for hydrated context. Initial targets should be treated as provisional until Phase 0 metrics are complete.

Suggested starting targets:

- Shared AI baseline file: ideally under 8 to 12 KB.
- `Adaptive` and `External Research`: ideally under 15 KB.
- `Plan`, `Implement`, `Quality Gate`, and `Change Review`: ideally under 35 to 50 KB each.
- Any single whole-file include larger than about 20 KB should require explicit rationale.

These are not product requirements yet, but they create a hardening discipline that the current system lacks.

### 2. Coverage Controls

Shrinking context safely requires a must-have-facts view for each role.

Minimum examples:

- `Adaptive`: repository contract, authority order, standard workflow baseline.
- `Plan`: architecture constraints, structure context, scope discipline, validation planning expectations.
- `Implement`: structure context, implementation guardrails, validation expectations, shared authority rules.
- `Quality Gate`: test commands, debugging loop, evidence expectations, regression discipline.
- `Change Review`: review checklist, evidence requirements, authority order, scope protection.

The hardening rule should be: no document is removed from hydration until all facts it uniquely contributed are accounted for somewhere else.

### 3. Topology Controls

The include graph should be treated as a maintained system, not just a convenience layer.

Recommended controls:

- maintain a simple inventory of which files feed which role sections
- avoid broad whole-file includes in `# Shared` unless the file is truly universal
- document why each shared include exists
- prefer smaller extracted files over repeatedly including large mixed-purpose documents

### 4. Governance Controls

The refactor needs a maintenance contract.

Recommended rules:

- every AI-focused summary file must state whether it is authoritative or derivative
- derivative AI summaries must say which source documents win on conflict
- `adaptive.rules.md` changes should require before/after hydration metrics and a short rationale
- each extracted file should have one clear owner, even if that owner is a larger parent document

### 5. Rollout Controls

This refactor should be staged rather than landed as one large rewrite.

Recommended rollout discipline:

- measure before editing
- add the compact AI baseline before removing existing broad includes
- narrow one class of includes at a time
- rehydrate all major roles after each stage
- keep rollback simple by ensuring include changes are isolated and reversible

### 6. Recovery And Rollback Controls

If a refactor stage removes too much context, rollback should be operationally simple.

The safest posture is:

- keep changes to shared includes isolated in small commits or small handoff tasks
- preserve the previous include set until the replacement baseline is validated
- record which role lost which document so a targeted re-include is possible without reverting everything

## Anti-Patterns To Avoid

- Creating `ai_context.md` as a second SSOT instead of a compact derivative or clearly authoritative layer.
- Removing duplicated text from `adaptive.rules.md` while leaving the same rule duplicated across technical and contrib docs.
- Optimizing only for smaller size without checking whether critical facts were lost.
- Using `# Shared` as a convenience bucket for any file that feels important.
- Rewriting human entry-point docs primarily to serve the AI instead of preserving their reader-facing role.
- Splitting large docs into smaller files without clarifying canonical ownership.
- Declaring the refactor complete without a before/after hydration comparison for each role.

## Document-By-Document Assessment

| Document | Keep For Humans | Keep In Default AI Shared Context | Recommended Action |
|---|---|---|---|
| [docs/technical/decisions.md](../technical/decisions.md) | Yes | Not as a broad shared whole-file include | Preserve as SSOT; split or extract AI-critical subdocuments for targeted inclusion |
| [docs/technical/scaffolding.md](../technical/scaffolding.md) | Yes | Only for roles that need structure | Include only for planning, discovery, and implementation contexts |
| [README.md](../../README.md) | Yes | No | Keep human-first; remove from default shared hydration |
| [START_HERE.md](../../START_HERE.md) | Yes | No | Keep as human entry point; remove from default shared hydration |
| [docs/contrib/contributing.md](../contrib/contributing.md) | Yes | No | Keep as contributor map; remove from default shared hydration |
| [docs/contrib/shared/README.md](../contrib/shared/README.md) | Yes | Probably no | Slim to the contrib authority map; do not inject by default if a compact AI baseline exists |
| [docs/contrib/plan.md](../contrib/plan.md) | Yes | Yes, in `plan` only | Trim framing; keep checklist and planning questions |
| [docs/contrib/code.md](../contrib/code.md) | Yes | Yes, in `implement` only | Trim framing; reduce or replace generic examples |
| [docs/contrib/testing.md](../contrib/testing.md) | Yes | Yes, in `quality-gate` only | Keep decision tree, commands, fixtures, and contamination guidance |
| [docs/contrib/debug.md](../contrib/debug.md) | Yes | Yes, in `quality-gate` only | Keep debugging loop, focused commands, and failure-analysis guidance |
| [docs/contrib/review.md](../contrib/review.md) | Yes | Yes, in `change-review` only | Keep checklist and evidence requirements |

## Recommended Target State

### Shared Baseline For All AI Roles

Create one compact AI-oriented baseline file, for example `docs/technical/ai_context.md`.

This file should contain only:

- repository purpose and current product contract
- authoritative document order and conflict resolution
- approved stack and workflow baseline
- validation entrypoints and standard command expectations
- generated-project ownership model
- concise document ownership map

This file should not contain:

- reading paths
- contributor onboarding walkthroughs
- marketing or positioning copy
- FAQ content
- document directory tours

### Role-Specific Context Model

Use the compact baseline as the universal shared layer, then add only the role-specific documents that materially change behavior.

Suggested target matrix:

| Section | Recommended Inputs |
|---|---|
| `Adaptive` | compact AI baseline only |
| `Plan` | compact AI baseline + planning guide + structure context |
| `Codebase Discovery` | compact AI baseline + structure context |
| `External Research` | compact AI baseline only |
| `Implement` | compact AI baseline + implementation guide + structure context |
| `Quality Gate` | compact AI baseline + testing guide + debug guide |
| `Change Review` | compact AI baseline + review guide |

### Ownership Cleanup Model

Make each concern owned in one place only:

- Repo-wide documentation precedence and policy: `decisions.md`
- Shared-versus-stage-guide authority model: `docs/contrib/shared/README.md`
- Human orientation and navigation: `README.md`, `START_HERE.md`, `docs/contrib/contributing.md`
- Role-specific applied execution help: stage guides in `docs/contrib/*.md`
- AI hydration baseline: new compact AI context file

### Best-Practice Constraints For This Refactor

- Do not degrade the human docs just to optimize AI hydration.
- Do not copy large sections into a new AI file without deciding who owns that text.
- Do not keep duplicated precedence rules after a compact baseline exists.
- Do not assume future heading-fragment support in external includes; optimize for whole-file inclusion constraints.
- Prefer smaller authoritative files over one giant authoritative file that every role must ingest.
- Do not ship the refactor without explicit hardening guardrails for size, coverage, and rollback.

## Hardening Success Criteria

The refactor should not be considered hardened only because the file structure looks cleaner. It is hardened when the system becomes easier to govern and harder to regress.

Success should mean all of the following:

- shared hydration is materially smaller and has a documented reason for every included file
- every role has a bounded and explainable context bundle
- authority and precedence statements are owned in one place per concern
- human router docs remain useful without being default AI inputs
- future edits to the include graph can be reviewed with metrics and a clear rollback path
- the repository has a simple answer to "where do I update this rule so hydrated AI context stays correct?"

## What Good Looks Like After The Refactor

- Default role hydration is materially smaller than the current 122 KB `implement` payload.
- Shared context contains mostly constraints, contracts, and execution-relevant defaults.
- Human navigation docs remain useful without being part of the default AI baseline.
- Stage guides are concise and role-specific.
- Authority rules live in one place per concern.
- The include graph is easy to reason about and maintain.
- Context size and role coverage are measurable before and after changes.
- Rollout is reversible without reopening the entire documentation strategy.
- Future contributors have a maintenance contract for AI-facing summary files and includes.

<a id="current-state-snapshot"></a>
## Phase 0 Baseline Capture (Completed 2026-05-01)

Hydration metrics were captured before any file edits in this phase using the current MCP include graph and the major role sections.

| Role | Lines | Size | Baseline note |
|---|---:|---:|---|
| `adaptive` | 2,507 | 117.0 KB | Shared payload is still dominated by universal whole-file includes. |
| `plan` | 2,585 | 120.6 KB | Adds planning guidance on top of the broad shared baseline. |
| `implement` | 2,661 | 122.2 KB | Adds implementation guidance on top of the broad shared baseline. |
| `quality-gate` | 2,875 | 128.6 KB | Largest current payload because testing and debug guidance stack onto shared docs. |
| `change-review` | 2,572 | 119.7 KB | Review guidance is still overshadowed by shared-context overhead. |

Explicit target outcomes for the refactor:

| Outcome | Target state |
|---|---|
| Shared default AI input | Replace the mixed human/router `# Shared` payload with one compact derivative AI baseline file. |
| Authority handling | Keep [decisions.md](../technical/decisions.md) authoritative for policy and [scaffolding.md](../technical/scaffolding.md) authoritative for structure; derivative summaries must defer on conflict. |
| Human-doc preservation | Keep [README.md](../../README.md), [START_HERE.md](../../START_HERE.md), and [docs/contrib/contributing.md](../contrib/contributing.md) human-first and out of default shared AI hydration. |
| Role isolation | Limit each role to the compact baseline plus only the role-specific docs that materially change behavior. |
| Change safety | Require before/after hydration metrics and a must-have-facts check whenever the include graph changes. |

Human-first versus AI-default classification to preserve during later phases:

| Document | Primary responsibility | Default AI role after refactor | Note |
|---|---|---|---|
| [docs/technical/decisions.md](../technical/decisions.md) | Repo-wide policy and tie-breakers | Referenced via compact baseline, not broad shared whole-file include | Remains the top authority. |
| [docs/technical/scaffolding.md](../technical/scaffolding.md) | Structure and placement authority | `plan`, `codebase-discovery`, `implement` only | Structural context, not universal default. |
| [README.md](../../README.md) | Human overview and orientation | No | Keep human-first. |
| [START_HERE.md](../../START_HERE.md) | Human repo entry point | No | Keep human-first. |
| [docs/contrib/contributing.md](../contrib/contributing.md) | Human contributor router | No | Keep human-first. |
| [docs/contrib/shared/README.md](../contrib/shared/README.md) | Human explanation of the shared/stage-doc model | Not by default | Only re-include if a later phase finds a unique AI-critical fact. |
| [docs/contrib/plan.md](../contrib/plan.md) | Planning workflow | `plan` only | Role-specific applied guidance. |
| [docs/contrib/code.md](../contrib/code.md) | Implementation workflow | `implement` only | Role-specific applied guidance. |
| [docs/contrib/testing.md](../contrib/testing.md) | Validation workflow | `quality-gate` only | Role-specific applied guidance. |
| [docs/contrib/debug.md](../contrib/debug.md) | Debug workflow | `quality-gate` only | Role-specific applied guidance. |
| [docs/contrib/review.md](../contrib/review.md) | Review workflow | `change-review` only | Role-specific applied guidance. |
| [docs/technical/ai_context.md](../technical/ai_context.md) | Compact AI baseline | All AI roles | Derivative, concise, and intentionally non-navigational. |

Provisional size budgets for later phases:

| Payload | Provisional budget | Rationale |
|---|---|---|
| Compact shared AI baseline | <= 12 KB and <= 250 lines | Small enough to hydrate everywhere without crowding role-local facts. |
| `adaptive` | <= 15 KB and <= 350 lines | Needs authority, workflow, and stack only. |
| `plan` | <= 50 KB and <= 900 lines | Needs structure plus planning workflow, but not the full human-router set. |
| `implement` | <= 50 KB and <= 900 lines | Needs structure plus implementation guardrails. |
| `quality-gate` | <= 50 KB and <= 950 lines | Needs validation and debug guidance, but should still drop most shared prose. |
| `change-review` | <= 35 KB and <= 750 lines | Needs authority, evidence standards, and review checklist only. |
| Any single whole-file include | More than 20 KB requires explicit rationale | Prevent convenience-driven shared-context relapse. |

Must-have facts to preserve before trimming any current include:

| Role | Must-have facts |
|---|---|
| `adaptive` | Authority order, conflict policy, workflow baseline, repo stack baseline, validation entrypoints, and generated-project ownership model. |
| `plan` | `adaptive` baseline plus structure authority, generated-project contract, scope discipline, and validation-planning expectations. |
| `implement` | `adaptive` baseline plus structure authority, implementation guardrails, make/pytest entrypoints, and ownership boundaries for generated code. |
| `quality-gate` | `adaptive` baseline plus test policy, coverage expectations, narrow-first validation commands, and debug workflow. |
| `change-review` | `adaptive` baseline plus evidence expectations, authority order, scope protection, and regression-review discipline. |

## Phase 1 Compact AI Baseline (Completed 2026-05-01)

Phase 1 delivers [docs/technical/ai_context.md](../technical/ai_context.md) as the compact AI-default baseline.

Current phase-1 decisions:

- The file is derivative and AI-focused, not a new SSOT.
- It keeps only shared decision-critical facts: authority order, workflow baseline, stack baseline, validation entrypoints, generated-project ownership, maintenance rule, and conflict policy.
- It is intentionally non-navigational: no reader tours, onboarding paths, FAQ sections, or contributor walkthroughs.
- [adaptive.rules.md](../../adaptive.rules.md) remains unchanged in this phase; include rewiring starts in Phase 2.

## Detailed Implementation Plan

This implementation plan is designed for phased handoff. Each item references the findings above so the work stays anchored to the intended outcomes.

### Phase 0 - Baseline, Scope, And Success Criteria

- [x] Capture current hydration metrics for at least `adaptive`, `plan`, `implement`, `quality-gate`, and `change-review`. Record line count and size before editing anything. See [Current State Snapshot](#current-state-snapshot).
- [x] Define explicit target outcomes for the refactor, including a smaller shared baseline and smaller role-specific payloads. See [What Good Looks Like After The Refactor](#what-good-looks-like-after-the-refactor).
- [x] Confirm which docs are human-first versus AI-default so the refactor does not accidentally damage contributor navigation. See [Document-By-Document Assessment](#document-by-document-assessment).
- [x] Define provisional hardening budgets for shared and role-specific context sizes so the refactor has an explicit performance target. See [Budget Controls](#1-budget-controls).
- [x] Define a must-have-facts checklist per role before removing any currently included document. See [Coverage Controls](#2-coverage-controls).

### Phase 1 - Create The Compact AI Baseline

- [x] Create a new compact AI baseline file such as `docs/technical/ai_context.md`. It should contain only decision-critical repository facts. See [Recommended Target State](#recommended-target-state).
- [x] Move concise authority order, workflow baseline, stack baseline, validation entrypoints, and generated-project ownership rules into that file. See [Shared Baseline For All AI Roles](#shared-baseline-for-all-ai-roles).
- [x] Keep the new file short and intentionally non-navigational. Do not add reading paths, FAQ sections, or contributor walkthroughs. See [Best-Practice Constraints For This Refactor](#best-practice-constraints-for-this-refactor).
- [x] Decide whether the compact AI baseline becomes authoritative for AI hydration only or whether it also becomes a human-maintained summary that is updated alongside `decisions.md`. Record that maintenance rule in the file itself. See [Ownership Cleanup Model](#ownership-cleanup-model).
- [x] Add an explicit conflict rule inside the new baseline file stating which source documents win if the summary drifts. See [Governance Controls](#4-governance-controls).

### Phase 2 - Reduce Shared-Context Over-Inclusion

- [x] Remove [README.md](../../README.md), [START_HERE.md](../../START_HERE.md), and [docs/contrib/contributing.md](../contrib/contributing.md) from the default `# Shared` include set after the compact baseline exists. See [Shared Includes Are Too Broad](#1-shared-includes-are-too-broad).
- [x] Decide whether [docs/contrib/shared/README.md](../contrib/shared/README.md) still belongs in default AI context or whether its useful content should be summarized in the compact AI baseline. See [Ownership Cleanup Model](#ownership-cleanup-model).
- [x] Keep only the minimal shared notes directly in [adaptive.rules.md](../../adaptive.rules.md) once the external shared baseline is in place. See [Include-Driven MCP Hydration](#1-include-driven-mcp-hydration).
- [x] For each removed shared document, record which facts were preserved elsewhere so trimming is explicit rather than assumed. See [Coverage Controls](#2-coverage-controls).

### Phase 3 - Split Or Extract Large Technical Inputs

- [x] Review [docs/technical/decisions.md](../technical/decisions.md) and identify the specific AI-critical material that is needed frequently: authority rules, current workflow, stack, testing policy, document responsibilities, and core contract. See [Strong Points To Preserve](#strong-points-to-preserve).
- [x] Decide whether to split `decisions.md` into smaller authoritative companion documents or to create smaller extracted files that `decisions.md` links to while remaining the top-level SSOT. See [Whole-File Includes Make Large Docs Expensive](#3-whole-file-includes-make-large-docs-expensive).
- [x] Do the same analysis for [docs/technical/scaffolding.md](../technical/scaffolding.md), extracting only the structure-critical portions that planning, discovery, and implementation actually need. See [scaffolding.md As The Structure Authority](#3-scaffoldingmd-as-the-structure-authority).
- [x] Preserve one clear owner for every moved rule. Do not create two competing copies of the same policy in the new smaller files. See [Authority And Precedence Statements Are Repeated Too Many Times](#2-authority-and-precedence-statements-are-repeated-too-many-times).
- [x] Add backlinks or ownership notes so extracted files remain traceable to their canonical parent or canonical rule owner. See [Governance Controls](#4-governance-controls).

### Phase 4 - Normalize Contrib Shared And Stage Guides

- [x] Reduce [docs/contrib/shared/README.md](../contrib/shared/README.md) to the smallest useful authority-map explanation if that document remains user-facing. See [Ownership Cleanup Model](#ownership-cleanup-model).
- [x] Remove duplicated framing from [docs/contrib/plan.md](../contrib/plan.md), [docs/contrib/code.md](../contrib/code.md), [docs/contrib/testing.md](../contrib/testing.md), [docs/contrib/debug.md](../contrib/debug.md), and [docs/contrib/review.md](../contrib/review.md) when the shared AI baseline already carries the same orientation. See [Stage-Guide Boilerplate Repeats Across Files](#4-stage-guide-boilerplate-repeats-across-files).
- [x] Keep only the parts of each stage guide that are genuinely stage-specific. See [Repo-Specific Applied Guidance In Stage Guides](#5-repo-specific-applied-guidance-in-stage-guides).
- [x] Replace or move generic educational examples in [docs/contrib/code.md](../contrib/code.md) if they do not teach QuickScale-specific implementation practice. See [Generic Educational Examples Compete With Real Repo Constraints](#6-generic-educational-examples-compete-with-real-repo-constraints).
- [x] Clarify the boundary between normative testing/debugging policy and repo-specific execution guidance so the same rule is not repeated across `decisions.md`, shared docs, and stage docs. See [Testing And Debugging Guidance Is Split In Ways That Invite Duplication](#5-testing-and-debugging-guidance-is-split-in-ways-that-invite-duplication).
- [x] Ensure each stage guide can justify its presence in hydration with role-specific value, not just historical structure. See [Role-Specific Context Model](#role-specific-context-model).

### Phase 5 - Rewire `adaptive.rules.md`

Source state note as of 2026-05-01: the shared-baseline swap and most role rewiring landed during phases 2-4 while those include trims were being applied, so the checklist below reflects the current source state rather than only work deferred to a future phase-5 pass.

Final rationale, topology inventory, validation snapshot, rollback notes, and governance rules now live in [AI Hydration Topology And Governance](../technical/ai_hydration_topology.md).

- [x] Replace the current broad `# Shared` include list with the new compact AI baseline and only the smallest necessary inline notes. See [Shared Baseline For All AI Roles](#shared-baseline-for-all-ai-roles).
- [x] Restrict structure-heavy context to `plan`, `codebase-discovery`, and `implement`. See [Role-Specific Context Model](#role-specific-context-model).
- [x] Keep `external-research` on the compact baseline unless a concrete research workflow proves it needs more. See [Human Router Documents Are Valuable, But Not As Default AI Inputs](#7-human-router-documents-are-valuable-but-not-as-default-ai-inputs).
- [x] Keep `quality-gate` on the compact baseline plus `validation_policy.md`, testing, and debugging guidance only. See [Role-Specific Context Model](#role-specific-context-model).
- [x] Keep `change-review` on the compact baseline plus review guidance only. See [Role-Specific Context Model](#role-specific-context-model).
- [x] Record the final include rationale in comments or in a short companion note so future edits do not drift back toward broad whole-file inclusion. See [Final Include Rationale](../technical/ai_hydration_topology.md#final-include-rationale).
- [x] Create a simple role-to-input inventory after rewiring so future edits can be reviewed against the intended topology. See [Role-To-Input Inventory](../technical/ai_hydration_topology.md#role-to-input-inventory).

### Phase 6 - Validation And Rollout

- [x] Re-run hydration for all major sections after the refactor and compare the new size to the Phase 0 baseline. See [Post-Refactor Validation Snapshot](../technical/ai_hydration_topology.md#post-refactor-validation-snapshot).
- [x] Spot-check each section for missing authority, workflow, validation, or role-specific execution guidance. The goal is smaller context, not weaker context. See [Validation Findings](../technical/ai_hydration_topology.md#validation-findings).
- [x] Review the include graph for broken links and redundant includes. See [Validation Findings](../technical/ai_hydration_topology.md#validation-findings).
- [x] Confirm that human docs remain coherent and useful after AI-focused trimming. See [Validation Findings](../technical/ai_hydration_topology.md#validation-findings).
- [x] Validate whether any now-obsolete duplicated text remained after the new include strategy settled; this pass confirmed that no additional in-scope duplicate cleanup was needed beyond the phase-4 guide trims. See [Validation Findings](../technical/ai_hydration_topology.md#validation-findings).
- [x] Record before/after results in a compact validation table so the rollout is auditable by future contributors. See [Post-Refactor Validation Snapshot](../technical/ai_hydration_topology.md#post-refactor-validation-snapshot).
- [x] Define a rollback note describing which include changes can be reverted independently if one role regresses. See [Rollback Notes](../technical/ai_hydration_topology.md#rollback-notes).

### Phase 7 - Ongoing Hardening And Governance

- [x] Assign a maintenance owner and review cadence for AI hydration files and include topology changes. See [Governance Requirements](../technical/ai_hydration_topology.md#governance-requirements).
- [x] Require future `adaptive.rules.md` or AI-baseline edits to include a short rationale and updated hydration metrics for affected roles. See [Governance Requirements](../technical/ai_hydration_topology.md#governance-requirements).
- [x] Periodically review whether any shared include has become role-specific or any role-specific include has become obsolete. See [Governance Requirements](../technical/ai_hydration_topology.md#governance-requirements).
- [x] Keep the human-versus-AI document boundary explicit so future cleanup does not collapse the two audiences back together. See [Governance Requirements](../technical/ai_hydration_topology.md#governance-requirements).
- [x] Revisit the size budgets after a few iterations and tighten or relax them based on actual hydration quality rather than guesswork. See [Governance Requirements](../technical/ai_hydration_topology.md#governance-requirements).

## Suggested Handoff Order

If this work is split across multiple implementation tasks, the recommended order is:

1. baseline and measurements
2. compact AI baseline file
3. `adaptive.rules.md` shared-context reduction
4. technical doc decomposition
5. contrib guide normalization
6. final hydration validation and cleanup
7. ongoing governance and hardening controls

## Expected Outcome

If the plan above is executed cleanly, QuickScale will keep the benefits of MCP-hydrated context while reducing repeated prose, preserving authority boundaries, and giving each coding assistant role a smaller, safer, and more governable context bundle.
