## Context Files

Read these before any development task:

1. `docs/technical/roadmap.md` - Current tasks and progress
2. `docs/technical/decisions.md` - IN/OUT of scope boundaries
3. `docs/contrib/code.md` - Implementation standards
4. `docs/contrib/review.md` - Quality checklist
5. `docs/contrib/testing.md` - Testing requirements

## Code Standards

### Python
- Python 3.11+
- Type hints on all public APIs
- Google-style docstrings (single-line preferred, no ending punctuation)
- F-strings for formatting (no .format() or %)
- Ruff for formatting and linting (NOT Black or Flake8)
- Poetry for package management (NOT pip or requirements.txt)
- Dependencies in pyproject.toml (NOT setup.py)

### SOLID Principles
1. **Single Responsibility**: One class, one reason to change
2. **Open/Closed**: Open for extension, closed for modification
3. **Liskov**: Subtypes substitutable for base types
4. **Interface Segregation**: Small, focused interfaces
5. **Dependency Inversion**: Depend on abstractions

### Testing
- pytest with pytest-django
- NO global mocking (no sys.modules modifications)
- Test isolation mandatory
- Coverage minimum: 90% overall, 80% per file

### Architecture Layers
1. **Presentation**: Views, templates, API endpoints
2. **Application**: Services, commands, queries
3. **Domain**: Models, business logic
4. **Infrastructure**: Database, external services

### Frontend
- React 18+ with TypeScript
- Vite for build
- shadcn/ui for components
- Tailwind CSS for styling

## Scope Discipline

- Implement ONLY items in task checklist
- No "nice-to-have" features or opportunistic refactoring
- When in doubt, ask - do not assume
