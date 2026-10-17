# Contributor Rules

These are the engineering rules for every change, in every workflow. They are binding.
Stage guides ([plan](plan.md), [code](code.md), [review](review.md), [testing](testing.md),
[debug](debug.md)) apply these rules to a situation and add repo commands. They never override
a rule here. Repo-wide technical policy lives in
[decisions.md](../technical/decisions.md), and it wins over this file.

## 1. Scope
- 1.1 A change does exactly what was requested. Adjacent cleanup, refactors, style-only edits and "nice to have" improvements are out of scope unless separately approved.
- 1.2 One logical change at a time. Follow-on work is reported, never silently added.
- 1.3 Public interfaces stay unchanged unless the request includes the interface change.
- 1.4 Handoff names every validation gap, documentation gap and unresolved dependency.

## 2. Design
- 2.1 Each class, module and function has one reason to change. Business rules, persistence, transport, formatting and orchestration stay separate unless an existing project pattern combines them.
- 2.2 An abstraction exists only for real volatility, a repeated pattern or an explicit boundary. No speculative extension points or indirection.
- 2.3 Duplicated knowledge and decision logic are removed. One-off similarities are not abstracted.
- 2.4 Implementations honour the contracts they satisfy: no narrowed inputs, weakened guarantees or surprising behavior.
- 2.5 Interfaces are small and client-specific. Dependencies at volatile boundaries are injected or wired explicitly, not constructed deep in business logic.
- 2.6 Optimization requires an observed bottleneck. Readability is never traded for speculative performance.
- 2.7 When these rules conflict, simplicity (KISS) and explicit failure win.

## 3. Failure handling
- 3.1 Missing inputs, broken invariants and missing environment conditions fail explicitly, with a message that supports diagnosis.
- 3.2 Silent fallbacks, blanket exception swallowing, unexplained retries and arbitrary default returns are prohibited.

## 4. Architecture
- 4.1 Only technologies approved in [decisions.md](../technical/decisions.md) are used. Bugs are fixed inside the approved stack. Any stack deviation is an architectural change and requires explicit approval.
- 4.2 Code goes in the correct layer. Existing orchestration, service and wiring seams are used, never bypassed. Hidden cross-layer imports are prohibited.
- 4.3 Placement follows [generated_project_structure.md](../technical/generated_project_structure.md) and [repository_layout.md](../technical/repository_layout.md). Boundary ambiguity is resolved against those documents before implementation starts.
- 4.4 Existing patterns are reused before a new local architecture is introduced.

## 5. Code style
- 5.1 Names are descriptive and use established project terms. No new abbreviations.
- 5.2 Public APIs and important internal boundaries carry type hints, in the surrounding package's typing style.
- 5.3 Python string interpolation uses f-strings.
- 5.4 Imports are grouped stdlib / third-party / local. Wildcard imports are prohibited.
- 5.5 Application code logs with structured logging. `print` is allowed only for CLI user output, tests and uncommitted local diagnostics.
- 5.6 Where these rules are silent, new code matches the surrounding code exactly.

## 6. Testing
- 6.1 Tests assert observable behavior and public contracts (outputs, side effects, published interfaces), not internals.
- 6.2 Unit tests use no live network, shared mutable state or environment-sensitive globals. Every mutated global, env var, file, cache or registry is restored. Each test passes both alone and in the full suite. Patching is local and scoped.
- 6.3 Each test covers one behavior, uses arrange-act-assert, and is named for that behavior. Tests that differ only by data are parametrized.
- 6.4 Changed behavior is covered on happy paths, error paths, boundaries and invalid input. Every confirmed defect gets a regression test.
- 6.5 Tests are never weakened, padded or overfit to make a change pass.
- 6.6 Repo test categories, locations and commands: [testing.md](testing.md) and [validation_policy.md](../technical/validation_policy.md).

## 7. Debugging
- 7.1 Fixes address the verified root cause. Symptom masks and workarounds are prohibited.
- 7.2 On a failing test: if intended behavior changed, update the test and record why. Otherwise fix the code.
- 7.3 Reproduce with the smallest command, input or fixture. Then validate from the most directly relevant tests outward, and report any deferred broader validation.

## 8. Documentation
- 8.1 Docstrings state purpose and behavior: one line for small units, multi-line only when one line cannot carry the needed context. Comments explain why, invariants and boundaries, never line-by-line mechanics.
- 8.2 A change to behavior, configuration, commands or operator expectations updates the owning document in the same change. The owner is the one named in [decisions.md § Document Responsibilities](../technical/decisions.md#document-responsibilities).
- 8.3 Each fact has exactly one owning document. Other documents link to it and never restate it. The one exception is the declared derived AI baseline, `docs/technical/ai_context.md`, which yields to the owner on any conflict.
- 8.4 Authoritative documents (marked **A** in [docs/index.md](../index.md)) state rules as MUST / MUST NOT or present-tense facts. Soft wording ("should", "prefer"/"preferred", "consider", "ideally", "typically", "usually", "generally", "recommended", "where possible", "if possible", "try to", "may want") is prohibited in them, outside code and quoted terms. `quickscale_core/tests/test_doc_phrasing.py` enforces this.
- 8.5 Documents describe the current state only. Changelogs of past decisions, dated audit passes, re-run notes and "previously X, now Y" narrative are prohibited outside CHANGELOG.md, docs/releases/ and git history.
- 8.6 Package READMEs and inline comments never contradict an authoritative document.
