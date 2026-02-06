# QuickScale Development Instructions

> **Auto-generated from `.agent/`** - Do not edit directly.
> Regenerate with: `.agent/adapters/generate-all.sh`

## Project Overview

QuickScale is a Django project generator that creates production-ready SaaS applications.

## Code Standards

### Python Style
- Python 3.11+
- Type hints on all public APIs
- Google-style docstrings (single-line preferred, no ending punctuation)
- F-strings for formatting (no .format() or %)
- Ruff for formatting and linting (NOT Black or Flake8)

### Package Management
- Use Poetry (NOT pip or requirements.txt)
- Dependencies in pyproject.toml (NOT setup.py)

### Testing
- pytest with pytest-django
- NO global mocking (no sys.modules modifications)
- Test isolation mandatory
- Coverage minimum: 90% overall, 80% per file

## SOLID Principles

1. **Single Responsibility**: One class, one reason to change
2. **Open/Closed**: Open for extension, closed for modification
3. **Liskov**: Subtypes substitutable for base types
4. **Interface Segregation**: Small, focused interfaces
5. **Dependency Inversion**: Depend on abstractions

## Code Patterns

### DO
```python
# Type hints
def process_data(data: dict) -> Result:
    """Process input data and return result"""
    ...

# Explicit error handling
try:
    result = operation()
except SpecificError as e:
    raise ProcessingError(f"Operation failed: {e}")

# Dependency injection
class Service:
    def __init__(self, repository: Repository):
        self._repository = repository
```

### DON'T
```python
# No bare except
try:
    ...
except:  # ❌ Never
    pass

# No global mocking in tests
sys.modules['module'] = mock  # ❌ Never

# No requirements.txt
# requirements.txt  # ❌ Use pyproject.toml
```

## Architecture

### Layers
1. **Presentation**: Views, templates, API endpoints
2. **Application**: Services, commands, queries
3. **Domain**: Models, business logic
4. **Infrastructure**: Database, external services

### Rules
- Views must not access database directly (use services)
- Models must not call external services
- Infrastructure must not depend on presentation

## Frontend Stack

- React 18+ with TypeScript
- Vite for build
- shadcn/ui for components
- Tailwind CSS for styling
- TanStack Query for server state

## Validation

Always run before completing work:

```bash
./scripts/lint.sh      # Ruff format + check + mypy
./scripts/test_unit.sh  # Unit and integration tests
```


---
*Generated from .agent/ on 2026-02-05T20:25:28+01:00*
