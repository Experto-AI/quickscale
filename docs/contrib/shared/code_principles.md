# Code Principles

This file contains the fundamental engineering principles for QuickScale.
These principles are normative and apply across planning, implementation,
testing, review, and debugging.

## SOLID Principles

### Single Responsibility Principle (SRP)

- Keep classes, modules, and functions focused on one cohesive responsibility
- Separate business rules, persistence, transport, formatting, and orchestration concerns unless an established project pattern intentionally combines them
- Treat units with multiple unrelated reasons to change as design debt

### Open/Closed Principle (OCP)

- Prefer extension through existing seams, composition, or polymorphism where variation is expected
- Avoid repeatedly modifying stable code paths just to bolt on new variants
- Do not introduce indirection where no realistic variation exists

### Liskov Substitution Principle (LSP)

- Derived implementations must preserve the expectations of the contracts they satisfy
- Do not narrow valid inputs, weaken guarantees, or change observable behavior in ways callers cannot safely predict
- Treat substitution failures as correctness issues, not style issues

### Interface Segregation Principle (ISP)

- Keep interfaces small, focused, and relevant to the clients that depend on them
- Do not force consumers or implementers to carry unrelated behavior for convenience
- Prefer explicit boundaries over oversized catch-all interfaces

### Dependency Inversion Principle (DIP)

- Depend on stable abstractions at volatile or externally varying boundaries
- Prefer injection or explicit wiring over constructing hard dependencies deep inside business logic
- Keep abstractions lean and justified by a real boundary rather than speculative reuse

## DRY (Don't Repeat Yourself)

- Eliminate duplicated knowledge and duplicated decision logic
- Reuse existing helpers or shared abstractions when repetition is real and stable
- Do not force premature abstraction for one-off similarities

## KISS (Keep It Simple, Stupid)

- Prefer the simplest design that satisfies the requested behavior
- Avoid speculative extension points, over-generalized helpers, and unnecessary indirection
- Choose clarity over cleverness

## Explicit Failure

- Reject silent fallbacks and hidden assumption recovery
- Fail explicitly when required inputs, invariants, or environment conditions are missing
- Make failure messages concrete enough to support diagnosis and safe operator action

## Abstraction and Optimization Balance

- Introduce abstractions for real volatility, repeated patterns, or explicit boundaries
- Optimize only after observing a real bottleneck or verified constraint
- Do not trade away readability or boundary clarity for speculative reuse or performance

## Principle Interactions

- Apply DRY and abstraction in service of KISS, not against it
- Preserve architectural boundaries while applying SOLID
- Prefer explicit failure over convenience fallbacks when the two are in tension
