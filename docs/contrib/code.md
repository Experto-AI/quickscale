# CODE - Implementation Guide

This is an implementation application guide. It applies the shared rule
sources to day-to-day code changes without acting as a separate rules
authority.

Shared documents in [shared/](shared/) remain authoritative when guidance
overlaps. This guide owns implementation checklists and implementation-stage
examples.

## Use This Guide When

- writing new implementation code
- modifying existing behavior inside an approved task boundary
- checking whether a proposed change still fits the local architecture and coding style

## Authoritative Sources for Implementation

Use these rule sources while implementing:

- [Code Principles](shared/code_principles.md)
- [Code Style Standards](shared/code_style_standards.md)
- [Architecture Guidelines](shared/architecture_guidelines.md)
- [Task Focus Guidelines](shared/task_focus_guidelines.md)
- [Documentation Standards](shared/documentation_standards.md)
- [Testing Standards](shared/testing_standards.md)

## Implementation Checklist

During implementation, confirm that you are:

- keeping changes inside the explicit task boundary
- applying the simplest design that satisfies the request
- reusing existing patterns before introducing new abstractions
- placing code in the correct architectural layer and preserving interfaces unless change is required
- handling invalid inputs, edge cases, and failures explicitly
- following the shared style rules for naming, typing, imports, formatting, logging, and local consistency
- documenting rationale where needed without duplicating what the code already says
- updating tests and documentation when the change requires them

## Applied Implementation Patterns

- Keep one unit responsible for one cohesive concern. Split transport, business logic, persistence, and formatting when responsibilities diverge.
- Extend through existing seams when variation is expected; avoid editing stable code in multiple places to add one new variant.
- Prefer dependency injection or explicit wiring at volatile boundaries instead of constructing hard dependencies deep in business logic.
- Reuse existing helpers only when repetition is real; do not force abstraction that makes the local code harder to read.
- Fail explicitly when required configuration, input, or invariants are missing.

## Implementation Examples

**Focused responsibilities and explicit dependencies**:

```python
class UserAuthenticator:
	"""Handle user authentication."""

	def authenticate(self, username, password):
		...


class UserRepository:
	"""Persist and load user records."""

	def save(self, user):
		...


class UserManager:
	"""Coordinate user operations with explicit dependencies."""

	def __init__(self, notifier: NotificationService):
		self.notifier = notifier
```

**Architecture placement**:

```python
# models/subscription.py
class Subscription:
	...


# services/subscription_service.py
class SubscriptionService:
	...


# api/subscription_api.py
def create_subscription_endpoint():
	...
```

**Explicit failure and concise documentation**:

```python
def initialize_database(config_path):
	"""Initialize the database connection from config."""

	config = load_config(config_path)
	if "connection_string" not in config:
		raise ConfigurationError(
			"Missing required 'connection_string' in database config"
		)

	# Validate configuration here so operators see the real failure early.
	return connect_to_database(config["connection_string"])
```

**Focused scope**:

```python
def create_user(email, password):
	"""Create a new user."""

	if not is_valid_email(email):
		raise ValueError("Invalid email format")

	return save_user(email, password)
```

Prefer a narrowly scoped change like the example above over expanding the same
task into unrelated signature changes, new side effects, or extra validations
that were not requested.

## Scope Guardrails in Practice

- Do not change function signatures, public URLs, schema shape, or wiring unless the task explicitly requires it.
- Keep unrelated cleanup, formatting, and refactors out of scoped implementation work.
- When a genuinely needed adjacent change appears, note it explicitly instead of silently widening the edit.

## Project-Specific Reminders

- If a convention is not documented in the shared docs, match the surrounding package or module rather than inventing a new local style.
- Keep unrelated cleanup, refactors, and style-only changes out of scoped implementation work.
- Use [Quality Analysis Tools](../technical/quality_tools.md) when you need deeper static analysis beyond the immediate task.

## Implementation Exit Criteria

Implementation is in good shape when:

- the change follows the relevant shared rules
- the scope is still tight and reviewable
- validation requirements are identified or already updated
- documentation impact is handled or explicitly noted

## Related Guidance

- [review.md](review.md) for quality checks
- [testing.md](testing.md) for repo-specific test selection and commands
- [debug.md](debug.md) for debugging application when validation fails
