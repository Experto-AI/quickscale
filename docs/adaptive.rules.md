---
domain: docs
merge_strategy: append
---

# Shared
<!-- Add reusable principles to be included by reference here -->
- **Important context (always read)**: [docs/index.md](index.md) — the documentation nav hub and authority map for docs-scoped work.
- This directory has two audiences: human contributors and AI hydration.
- Human-first documents: README.md, START_HERE.md, docs/contrib/contributing.md,
  docs/contrib/shared/README.md. Do not optimize these for AI consumption.
- AI hydration documents: docs/technical/ai_context.md is the compact AI baseline;
  docs/technical/decisions.md is the policy authority; other technical docs
  are role-specific includes governed by docs/technical/ai_hydration_topology.md.
- When editing docs, decide which audience owns the file first. Do not add
  AI-specific shortcuts to human-first docs, and do not add human navigation
  tours to AI-hydrated files.

# Adaptive
<!-- Add rules for the main orchestrator agent here -->
[include](#shared)

# Plan
<!-- Add rules for planning and architectural design here -->
[include](#shared)

# Codebase Discovery
<!-- Add rules for discovery and comprehension here -->
[include](#shared)

# External Research
<!-- Add rules for researching external APIs and docs here -->
[include](#shared)

# Implement
<!-- Add rules for writing code (e.g. backend specific syntax) here -->
[include](#shared)
- Before adding a new doc, decide: is it human-first or AI-hydration context? Add it to the right category and update `ai_hydration_topology.md` if it changes hydration.

# Quality Gate
<!-- Add rules for testing, linting, and quality enforcement here -->
[include](#shared)

# Change Review
<!-- Add rules for PR review and change management here -->
[include](#shared)
- Doc changes that touch any `adaptive.rules.md`, `docs/technical/ai_context.md`, or `docs/technical/ai_hydration_topology.md` require a hydration-metrics check per the governance requirements in `docs/technical/ai_hydration_topology.md`.
