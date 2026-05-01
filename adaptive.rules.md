---
domain: root
merge_strategy: append
---

# Shared

[include](docs/technical/decisions.md)
[include](docs/technical/scaffolding.md)
[include](README.md)
[include](START_HERE.md)
[include](docs/contrib/contributing.md)
[include](docs/contrib/shared/README.md)

- **Contrib authority model**:
    - `docs/contrib/shared/` owns workflow-agnostic QuickScale engineering rules.
    - `docs/contrib/*.md` stage guides apply those rules in a situation-specific way and do not prescribe a required workflow order.
    - If a stage guide conflicts with a `docs/contrib/shared/` rule source, the shared document wins.
- **Documentation precedence**:
    - Package README files are informational context only; repository SSOT documents win any conflict.
    - `docs/technical/decisions.md` wins on conflicts over `README.md` and `START_HERE.md`.
- **Tooling**:
    - `Makefile` is the standard entrypoint for shared test and workflow commands.

# Adaptive
[include](#shared)


# Plan
[include](#shared)
[include](docs/contrib/plan.md)

# Codebase Discovery
[include](#shared)


# External Research
[include](#shared)

# Implement
[include](#shared)
[include](docs/contrib/code.md)

# Quality Gate
[include](#shared)
[include](docs/contrib/testing.md)
[include](docs/contrib/debug.md)

# Change Review
[include](#shared)
[include](docs/contrib/review.md)
