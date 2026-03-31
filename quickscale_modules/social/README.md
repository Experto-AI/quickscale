# QuickScale Social Module Contract

Phase A contract-only foundation for the planned `quickscale_modules.social` release.

This directory currently defines the social module configuration surface and provider policy without shipping planner/apply wiring, Django runtime/admin code, or React consumers yet.

Current contract guarantees:

- fixed public routes remain `/social` and `/social/embeds`
- provider allowlist defaults are explicit and normalized
- link-tree and embed settings stay in generated settings and `quickscale.yml`, not in mutable database config

Later v0.79.0 phases will add planner/apply wiring, backend/admin implementation, and fresh-generation frontend consumption on top of this contract.
