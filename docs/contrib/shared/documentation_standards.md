# Documentation Standards

This file contains the authoritative documentation standards for QuickScale.

## Documentation Sources to Follow

- **[README.md](../../../README.md)**: project overview and primary contributor entrypoint
- **[Technical Decisions](../../technical/decisions.md)**: authoritative stack, boundary, and anti-pattern decisions
- **[Scaffolding Guide](../../technical/scaffolding.md)**: authoritative repository and package structure rules
- **[User Manual](../../technical/user_manual.md)**: operator-facing commands, usage, and troubleshooting
- **[Contributing Guidelines](../contributing.md)**: contributor documentation map and authority model

## Documentation Rules

### Prefer concise purpose-first docstrings

- Prefer single-line docstrings for small functions and classes
- Use multi-line docstrings only when a module, class, or function needs materially more context than a single line can provide
- Describe purpose and behavior first rather than repeating obvious mechanics
- Match the surrounding package style when a local documentation pattern is already established

### Document behavior, rationale, and boundaries

- Explain why, invariants, failure behavior, or architectural boundaries when they are not obvious from the code
- Avoid comments that narrate line-by-line mechanics
- Keep public or externally meaningful behavior documented where readers will naturally look for it

### Keep documentation aligned with code and SSOT

- Update documentation when behavior, configuration, commands, or operator expectations change
- Treat the repository SSOT documents as authoritative for architecture, structure, and workflow claims
- Do not let package-local README content or inline comments contradict repository SSOT
