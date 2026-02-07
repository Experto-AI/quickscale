## Key Principles

### Scope Discipline (CRITICAL)
- Implement ONLY items explicitly listed in task checklist
- NO "nice-to-have" features, NO opportunistic refactoring
- When in doubt, ask - do not assume

### Code Quality
- **SOLID** · **DRY** · **KISS** · **Explicit Failure**
- Type hints on all public APIs
- Google-style docstrings (single-line preferred, no ending punctuation)
- F-strings for formatting (no `.format()` or `%`)

### Testing
- pytest with pytest-django - NO global mocking (`sys.modules` modifications prohibited)
- Test isolation mandatory · Coverage >= 90% overall, >= 80% per file

## Tech Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.11+ |
| Framework | Django 4.2+ |
| Package Manager | Poetry (NOT pip/requirements.txt) |
| Package Config | pyproject.toml (NOT setup.py) |
| Linting | Ruff (NOT Black or Flake8) |
| Testing | pytest |
| Frontend | React 18+ with TypeScript |
| Build | Vite |
| Components | shadcn/ui |
| CSS | Tailwind CSS |
