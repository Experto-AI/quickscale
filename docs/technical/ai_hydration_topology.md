# AI Hydration Topology

This file owns the include graph of the `adaptive.rules.md` files: which role hydrates which
document, and the rules for changing that. Technical facts are owned by the documents that
[ai_context.md](ai_context.md) names.

QuickScale is a target repo for Adaptive, the multi-agent coding pipeline in the sibling
`../adaptive` repo, which documents the agents and their task-size tiers. The wiring here:
`adaptive.yml` declares the domains, and each directory's `adaptive.rules.md` holds one section
per agent role. The adaptive MCP server cascades these files from the root down, extracts the
role's section, and resolves `[include]`s.

## Role inputs

| Role | `[include]`d (inlined, counted in metrics) | Must-have facts |
|---|---|---|
| `adaptive` | baseline: [ai_context.md](ai_context.md) + `adaptive.intake.yml` | authority order, conflict policy, workflow and stack baseline, validation entrypoints, generated-project ownership |
| `plan` | baseline + [generated_project_structure.md](generated_project_structure.md), [repository_layout.md](repository_layout.md), [contrib/plan.md](../contrib/plan.md), [contrib/rules.md](../contrib/rules.md) | baseline + structure authority, scope discipline, validation planning |
| `codebase-discovery` | baseline + both structure docs | baseline + structure authority, generated-vs-maintainer boundary |
| `external-research` | baseline only | baseline only |
| `implement` | baseline + both structure docs + [contrib/code.md](../contrib/code.md), [contrib/rules.md](../contrib/rules.md) | baseline + structure authority, implementation guardrails, `make`/pytest entrypoints |
| `quality-gate` | baseline + [validation_policy.md](validation_policy.md), [contrib/testing.md](../contrib/testing.md), [contrib/debug.md](../contrib/debug.md), [contrib/rules.md](../contrib/rules.md) | baseline + validation policy, coverage, narrow-first commands, debug loop |
| `change-review` | baseline + [contrib/review.md](../contrib/review.md), [contrib/rules.md](../contrib/rules.md) | baseline + evidence standards, scope protection, regression review |

Hydration scoped to `docs/` also surfaces [docs/index.md](../index.md) as an *always-read pointer*: a read hint that
the agent fetches only when needed. Pointers are not inlined and not counted in metrics.

## Rules

- `[include]` is used only for a file the role cannot work without. Supplementary context is an always-read pointer.
- Human-first documents (README.md, START_HERE.md, contrib/contributing.md) are never included.
- A change to any `adaptive.rules.md` or to `ai_context.md` updates the table above in the same change. It also states the hydrated line and size delta for every affected role, measured with the adaptive MCP `get_hydrated_context`.
- A new whole-file include over 20 KB requires a written reason why a narrower file is not enough.
- A regression in one role is fixed in that role's block. The shared baseline is never widened to fix a single role.
- An edit to the include graph keeps every role's must-have facts.
