# How QuickScale Uses Adaptive

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Adaptive**
> **Related docs**: [Roadmap](../technical/roadmap.md) | [AI Context](../technical/ai_context.md) | [AI Hydration Topology](../technical/ai_hydration_topology.md) | [adaptive.rules.md](../../adaptive.rules.md)

## What it is

**Adaptive** is a prompt-engineered multi-agent orchestration system for AI coding agents. A single
orchestrator (`Adaptive`) sizes each request, then either edits directly or delegates the work across
six specialized subagents so that each phase — discovery, planning, implementation, testing, review —
runs in its own clean context instead of one overloaded window.

QuickScale is a **configured target repo** for Adaptive, not the Adaptive source. The system itself
lives in the sibling `../adaptive` repo (agent prompt files + `docs/`); this page is the
QuickScale-side "how we use it" summary. Our wiring:

- `adaptive.yml` — declares domains `quickscale`, `quickscale_cli`, `quickscale_core`,
  `quickscale_modules`, `tech_profile: standard`, `max_depth: 4`, `readiness_state: configured`.
- `docs/adaptive.rules.md` and the per-directory `adaptive.rules.md` overlays — the cascade-merged
  context each agent hydrates.

## The agents

| Agent | Role | Writes files? |
|---|---|---|
| `Adaptive` (orchestrator) | Entry point; sizes the task, routes, does trivial low-risk edits | Yes (trivial only) |
| `Adaptive-plan` | Strategy and sequencing | No |
| `Adaptive-codebase-discovery` | File/symbol mapping when scope is unknown | No |
| `Adaptive-implement` | Scoped code edits (`SCOPE_IN`) | Yes |
| `Adaptive-quality-gate` | Runs lint/typecheck/tests, fixes failures (`CHANGED FILES`) | Yes |
| `Adaptive-change-review` | Plan review + post-change correctness/scope/security review | No |
| `Adaptive-external-research` | Web/docs/library lookup | No |

Only `Adaptive-implement` and `Adaptive-quality-gate` may write files. Everything else is read-only.

## Task-size tiers

Every task is announced with a tier. Sizing is driven by **risk + reasoning working-set** (the
"context-fit budget"), *not* raw file count — a large mechanical multi-file edit can still be Tier 2.

| Tier | Trigger | Routing |
|---|---|---|
| **Tier 1 — Small** | One concern, scope nameable, `RISK LEVEL: low`, fits the context-fit budget | Orchestrator edits directly (fast-path) |
| **Tier 2 — Medium** | Single concern but scope undiscovered, or too big for one context pass | Delegate discovery and/or scoped `Adaptive-implement` |
| **Tier 3 — Complex** | Multiple objectives, `RISK LEVEL: high`, or genuine architectural/algorithmic difficulty | Full path: plan → plan-review → phased implement → validate → review |

**The sizing gate**, in order:

1. Can the full objective be stated in one sentence? No → **Tier 3**.
2. Risk level: touching auth / payments / migrations / public API contracts with broad side-effects
   = `high` → **Tier 3** (forced). Narrow change in a sensitive domain = `medium` → **never Tier 1**.
3. Is scope pre-specified (caller lists every file) or **undiscovered** (must be found)? Undiscovered
   → **Tier 2 minimum**.
4. Context-fit budget — all three axes must fit for Tier 1:
   - **READ** ≲ 2,000 lines read in full (no single file > ~800)
   - **EDIT** ≲ 2,000 changed lines across ≲ 20 sites
   - **COUPLING** ≤ 3 interdependent elements (mechanical repeats count as 1)

Separately, a `PLANNING TIER: small | medium | big` is chosen. `RISK LEVEL: high` (and multi-hour
decision-making work) forces `PLANNING TIER: big`, which mandates a **plan-review pass** by
`Adaptive-change-review` before any implementation, plus rollback checkpoints.

## How context (hydration) works

Before doing any work, each agent calls the Adaptive MCP server:
`get_hydrated_context(workspace_root, dirs, sections)`. The server:

1. Cascades `adaptive.rules.md` files from the repo root down to the active directory (up to
   `max_depth`), honoring `precedence_order`.
2. Extracts the **section matching that agent** (each `adaptive.rules.md` has one section per agent
   role — `# Adaptive`, `# Plan`, `# Implement`, etc.).
3. Resolves `[include](#shared)` references, strips comments, and injects the result as binding
   execution context.

Because QuickScale is `readiness_state: configured`, hydration is mandatory: if the MCP server is
unavailable an agent returns **blocked** rather than silently running without context. Our hydration
inputs live in:

- `docs/technical/ai_context.md` — the compact AI baseline.
- `docs/technical/decisions.md` — the policy authority.
- `docs/technical/ai_hydration_topology.md` — governs which docs feed which agent.
- `docs/adaptive.rules.md` (+ per-directory overlays) — the cascade the MCP server reads.

## Working with `adaptive.rules.md`

The `adaptive.rules.md` files are how we *tailor* Adaptive to QuickScale. There is one at the repo
root and one per domain/subtree; the MCP server cascade-merges them (root first, then deeper dirs,
`merge_strategy: append`) and hands each agent only its own section.

**Layout of every file:**

- Frontmatter: `domain:` (matches an `adaptive.yml` domain, or `root`) and `merge_strategy: append`.
- A `# Shared` section holding reusable prose/includes for that directory.
- One section per agent role: `# Adaptive`, `# Plan`, `# Codebase Discovery`, `# External Research`,
  `# Implement`, `# Quality Gate`, `# Change Review`. Each pulls in the shared block with
  `[include](#shared)` and then adds role-specific rules.

**Two ways content reaches an agent** (they have different costs):

| Mechanism | Syntax | Cost |
|---|---|---|
| Inline include | `[include](path/to/doc.md)` | Expanded into the payload at hydration time — counts against hydration metrics |
| Always-read pointer | a named item under `- **Important context (always read)**:` | Just a read hint; the agent fetches it only when the task warrants — not counted |

Use inline includes for context every task in that role needs; use always-read pointers for
reference the agent should reach for on demand.

**Where our rules live and what they carry:**

- `adaptive.rules.md` (root) — the include graph that feeds each role its baseline: `# Shared`
  pulls `docs/technical/ai_context.md`; `Plan`/`Implement` also pull structure + contributor guides;
  `Quality Gate` pulls `validation_policy.md` + testing/debug guides; `Change Review` pulls
  `review.md`.
- `docs/adaptive.rules.md`, `quickscale/`, `quickscale_cli/`, `quickscale_core/`,
  `quickscale_modules/`, `examples/`, `scripts/` — domain overlays with subtree-specific rules
  (e.g. `quickscale_core` warns that template edits are user-facing contract changes and require
  regeneration testing).
- `docs/technical/ai_hydration_topology.md` — the **governance authority**: it owns the include
  graph rationale, the latest payload line/size metrics, the per-role rollback map, and the rules
  for changing the graph.

### How to update / improve them

1. **Pick the narrowest scope.** A rule that only matters inside `quickscale_core` goes in that
   directory's file, not the root. A rule for one agent goes in that agent's section, not `# Shared`
   (which fans out to every role).
2. **Prefer editing an included doc over inlining new prose.** If the guidance belongs to testing,
   improve `docs/contrib/testing.md` — it's already hydrated into the Quality Gate role. Add a new
   `[include]` only when no existing hydrated doc owns the content.
3. **Keep the shared baseline compact.** `# Shared` / `ai_context.md` is loaded for *every* role and
   every task, so it's the most expensive place to add text. The first fix for a single-role
   regression is to adjust that role's block, not widen the shared baseline.
4. **Respect the human-vs-AI split.** In `docs/`, human-first files (README, START_HERE,
   contributing) must not be optimized for hydration, and AI-hydration files must not grow human
   navigation tours (see `docs/adaptive.rules.md`).
5. **Governance check.** Changes to any `adaptive.rules.md`, `docs/technical/ai_context.md`, or
   `ai_hydration_topology.md` require refreshing the hydration metrics/rationale in
   `ai_hydration_topology.md` per its governance rules — update the topology and metrics snapshot in
   the same change, don't just edit the rules file.
6. **Verify.** After editing, confirm every `[include]` path resolves and that the intended agent
   section actually picks up the change (the MCP server only injects the section matching the agent).

## Closeout

Every **executable** change ends in an independent `Adaptive-change-review`; the review step is never
skipped. The closeout path is chosen at assessment time:

- `none` — research/explain-only, no mutation.
- `review-only` — docs/prompt/policy text changes: skip the quality gate, still run review.
- `validate-and-review` — any executable/config/schema/contract change: `Adaptive-quality-gate`
  (when project tooling exists) → `Adaptive-change-review`. This is the only path for executable code.

## Going deeper

Source of truth in `../adaptive`:

- `README.md` — overview.
- `Adaptive.agent.md` — orchestrator decision tree, tier-selection procedure, closeout paths.
- `docs/architecture-agent-topology.md` — agent roles and mutation boundaries.
- `docs/architecture-execution-flow.md` — routing and the per-agent hydration flow.
