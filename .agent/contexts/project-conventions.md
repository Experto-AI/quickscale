# Project Conventions

> Project-specific rules and conventions for QuickScale development.

## Naming Conventions

### Python

| Element | Convention | Example |
|---------|------------|---------|
| Modules | `snake_case` | `user_service.py` |
| Classes | `PascalCase` | `UserRepository` |
| Functions | `snake_case` | `get_user_by_id()` |
| Constants | `SCREAMING_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| Private | `_leading_underscore` | `_internal_helper()` |

### Files and Directories

| Element | Convention | Example |
|---------|------------|---------|
| Python files | `snake_case.py` | `user_service.py` |
| Test files | `test_*.py` | `test_user_service.py` |
| Markdown | `kebab-case.md` | `agentic-flow.md` |
| Config files | `lowercase` | `pyproject.toml` |

### Agent System

| Element | Convention | Example |
|---------|------------|---------|
| Agent files | `kebab-case.md` | `task-implementer.md` |
| Skill directories | `kebab-case/` | `code-principles/` |
| Workflow files | `kebab-case.md` | `implement-task.md` |

## Code Style

### Imports

```python
# Standard library
import os
from pathlib import Path

# Third-party
import django
from django.conf import settings

# Local
from quickscale.core import utils
from .models import User
```

### Docstrings

```python
def calculate_total(items: list[Item]) -> Decimal:
    """Calculate total price for all items"""  # Single-line preferred
    return sum(item.price for item in items)

def complex_operation(
    data: dict[str, Any],
    options: ProcessingOptions,
) -> Result:
    """Process data with given options.

    Args:
        data: Input data dictionary with required keys.
        options: Processing configuration options.

    Returns:
        Result object with processed data.

    Raises:
        ValidationError: If data is invalid.
    """
    ...
```

### Error Handling

```python
# ✅ DO: Specific exceptions with context
try:
    result = process_data(input_data)
except ValueError as e:
    raise ProcessingError(f"Invalid data format: {e}") from e

# ❌ DON'T: Bare except or silent failures
try:
    result = process_data(input_data)
except:
    pass  # Never do this
```

## Testing Conventions

### Test Structure

```python
class TestUserService:
    """Tests for UserService class"""

    def test_create_user_with_valid_data(self):
        """Should create user when data is valid"""
        ...

    def test_create_user_raises_on_duplicate_email(self):
        """Should raise DuplicateEmailError for existing email"""
        ...
```

### Test Naming

- `test_<method>_<scenario>` or `test_<method>_<expected_behavior>`
- Be descriptive: `test_authenticate_returns_token_for_valid_credentials`

### Fixtures

- Use `conftest.py` for shared fixtures
- Factory Boy for model factories
- No `sys.modules` modifications (global mocking prohibition)

## Git Conventions

### Commit Messages

Follow conventional commits:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
- `feat(auth): add email verification flow`
- `fix(billing): correct tax calculation for EU`
- `docs(readme): update installation instructions`

### Branch Names

- `feature/<short-description>`
- `fix/<issue-number>-<short-description>`
- `docs/<topic>`

## Package Management

### Dependencies

```toml
# pyproject.toml - DO use
[tool.poetry.dependencies]
python = "^3.11"
Django = "^4.2"

# requirements.txt - DON'T use
Django==4.2.0  # ❌ Never create this file
```

### Scripts

Always use project scripts:
- `./scripts/lint.sh` — Not `ruff` directly
- `./scripts/test-all.sh` — Not `pytest` directly
- `./scripts/install_global.sh` — Not `pip install poetry`

## Directory Layout

```
quickscale/
├── quickscale_core/        # Core package
│   ├── src/quickscale_core/
│   └── tests/
├── quickscale_cli/         # CLI package
│   ├── src/quickscale_cli/
│   └── tests/
├── quickscale_modules/     # Optional modules (maintainer repo only)
├── docs/                   # Documentation
├── scripts/                # Development scripts
└── .agent/                 # AI agent system
```

## Validation Requirements

Before any PR or commit:

1. `./scripts/lint.sh` must pass
2. `./scripts/test-all.sh` must pass
3. Coverage ≥ 70% for new code
4. No scope violations (as defined in decisions.md)
