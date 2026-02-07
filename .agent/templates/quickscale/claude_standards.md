## Key Principles

### Scope Discipline
- Implement ONLY items in task checklist
- No "nice-to-have" features or opportunistic refactoring

### Code Quality
- SOLID, DRY, KISS principles
- Type hints on all public APIs
- Google-style docstrings (single-line preferred)
- F-strings for formatting
- Ruff for linting (NOT Black or Flake8)

### Testing
- pytest with pytest-django
- No global mocking contamination (`sys.modules` modifications prohibited)
- Test isolation mandatory
- Coverage >= 90% overall, >= 80% per file

## Tech Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.11+ |
| Framework | Django 4.2+ |
| Package Manager | Poetry (NOT pip/requirements.txt) |
| Package Config | pyproject.toml (NOT setup.py) |
| Linting | Ruff |
| Testing | pytest |
| Frontend | React 18+ with TypeScript |
| Build | Vite |
| Components | shadcn/ui |
| CSS | Tailwind CSS |
