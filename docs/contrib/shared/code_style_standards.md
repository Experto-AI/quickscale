# Code Style Standards

This file contains code style and local consistency standards that apply across
all programming stages.

## Naming and Clarity

- Use descriptive names for variables, functions, classes, and modules
- Prefer established project terminology over inventing new names for the same concept
- Avoid ambiguous abbreviations unless they are already standard in the surrounding code

## Type Hints

- Add type hints where they improve understanding of public APIs and important internal boundaries
- Match the surrounding package's typing style instead of introducing a different local style
- Prefer clear, readable types over overly complex annotations that add noise without helping readers

## String Formatting

- Use f-strings for string interpolation in Python code unless a surrounding pattern clearly requires something else
- Keep formatting choices consistent with adjacent code when shared rules are otherwise silent

## Import Organization

- Group imports logically as standard library, third-party, and local imports
- Avoid wildcard imports
- Keep import style consistent with nearby modules when a package already has a stable local pattern

## Logging and Operator Visibility

- Prefer structured logging over ad-hoc `print` statements in application code
- Reserve direct `print` usage for intentional CLI/user-facing output, tests, or one-off local diagnostics that are not part of committed application behavior
- Make logged messages concrete enough to support troubleshooting without hiding the real failure mode

## Interface Preservation and Local Consistency

- Preserve existing public interfaces unless the requested change explicitly includes an interface change
- When shared standards do not define a convention, match the surrounding codebase exactly rather than inventing a new local style
- Keep style-only changes out of unrelated files while implementing a scoped task

## Review Application

When reviewing changes, verify:

- names are descriptive and consistent with the codebase
- type hints improve clarity where they matter
- imports are organized and explicit
- logging and operator-facing output are appropriate to the context
- public interfaces changed only when the task required it
