# Architecture Guidelines

This file contains the authoritative architecture and stack rules for QuickScale.

## Technical Stack Requirements

- Use only technologies explicitly defined in [decisions.md](../../technical/decisions.md)
- Fix bugs within the approved stack instead of introducing alternate-stack fallbacks or workarounds
- Treat any deviation from the approved stack as an architectural change that requires explicit approval

## Architectural Boundaries

- Place code in the correct layer and respect existing separation of concerns
- Do not mix transport, business logic, persistence, infrastructure, and presentation responsibilities without an established project pattern that intentionally combines them
- Do not bypass existing orchestration, service, or wiring seams when the repository already provides them
- Follow [decisions.md](../../technical/decisions.md) and [scaffolding.md](../../technical/scaffolding.md) for architectural boundaries and placement rules

## Dependency and Interface Rules

- Depend on stable abstractions where variation or volatility exists
- Preserve public interfaces unless the requested scope explicitly includes an interface change
- Avoid hidden cross-layer dependencies and backdoor imports that make boundaries harder to reason about

## Architectural Change Discipline

- Reuse established patterns before introducing a new local architecture
- Keep architectural changes explicit, reviewable, and justified by the requested outcome
- Resolve boundary ambiguity against the repository SSOT documents before implementation begins
