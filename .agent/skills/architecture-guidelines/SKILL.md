---
name: architecture-guidelines
version: "1.0"
description: Tech stack compliance, layer boundaries, patterns
provides:
  - tech_stack_validation
  - layer_boundary_check
  - pattern_compliance
requires: []
---

# Architecture Guidelines Skill

## Overview

This skill provides architectural guidance for QuickScale development, ensuring tech stack compliance, proper layer boundaries, and consistent patterns.

## Tech Stack (Authoritative)

### Core Stack

| Component | Technology | Version | Notes |
|-----------|------------|---------|-------|
| Language | Python | 3.11+ | Required minimum |
| Framework | Django | 4.2+ LTS | Latest LTS |
| Package Manager | Poetry | 1.5+ | NO pip, NO requirements.txt |
| Formatting | Ruff | Latest | NO Black, NO Flake8 |
| Type Checking | MyPy | Strict | Required for public APIs |
| Testing | pytest | + pytest-django | + factory_boy |
| Database | PostgreSQL | 14+ | Production |

### Frontend Stack (React Default)

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Framework | React 18+ | Industry standard |
| Language | TypeScript | Type safety |
| Build Tool | Vite | Fast HMR |
| UI Components | shadcn/ui | Copy-paste, full ownership |
| CSS | Tailwind CSS | Required by shadcn |
| State (Server) | TanStack Query | Data fetching |
| State (Client) | Zustand | Simple, fast |
| Routing | React Router v6 | Most mature |
| Forms | React Hook Form + Zod | Best performance |

### Prohibited Technologies

- ❌ Black (use Ruff format)
- ❌ Flake8 (use Ruff check)
- ❌ requirements.txt (use Poetry)
- ❌ setup.py (use pyproject.toml)
- ❌ pip commands (use Poetry)

## Architectural Layers

### Layer Structure

```
┌─────────────────────────────────────┐
│           Presentation              │  ← Views, Templates, API endpoints
├─────────────────────────────────────┤
│            Application              │  ← Services, Commands, Queries
├─────────────────────────────────────┤
│             Domain                  │  ← Models, Business Logic
├─────────────────────────────────────┤
│          Infrastructure             │  ← Database, External Services
└─────────────────────────────────────┘
```

### Layer Rules

**Presentation Layer:**
- Django views and templates
- API serializers and viewsets
- Form handling
- **Dependencies**: Application layer only

**Application Layer:**
- Service classes
- Command/query handlers
- Orchestration logic
- **Dependencies**: Domain + Infrastructure

**Domain Layer:**
- Django models
- Business rules
- Validation logic
- **Dependencies**: None (pure domain logic)

**Infrastructure Layer:**
- Database operations
- External API clients
- File system operations
- **Dependencies**: Domain layer only

### Boundary Validation

**Validation Checklist:**
- [ ] Views don't directly access database (use services)
- [ ] Models don't call external services
- [ ] Infrastructure doesn't depend on presentation
- [ ] Circular dependencies don't exist

## Package Structure

### Src Layout (Required)

```
quickscale_core/
├── pyproject.toml
├── src/
│   └── quickscale_core/
│       ├── __init__.py
│       ├── generator/
│       └── utils/
└── tests/
    └── test_generator.py
```

**Rules:**
- ✅ All packages use `src/` layout
- ✅ Tests outside `src/` (parallel `tests/` directory)
- ❌ Tests inside `src/` (prevents accidental imports)

### Module Naming

| Package Type | Naming Pattern | Example |
|--------------|----------------|---------|
| Core | `quickscale_core` | `quickscale_core` |
| CLI | `quickscale_cli` | `quickscale_cli` |
| Modules | `quickscale_modules_<name>` | `quickscale_modules_auth` |
| Themes | `quickscale_themes_<name>` | `quickscale_themes_starter` |

## Design Patterns

### Service Pattern

```python
class UserService:
    """Handles user-related operations"""

    def __init__(self, user_repo: UserRepository, email_service: EmailService):
        self._user_repo = user_repo
        self._email_service = email_service

    def create_user(self, email: str, name: str) -> User:
        """Create a new user and send welcome email"""
        user = User(email=email, name=name)
        self._user_repo.save(user)
        self._email_service.send_welcome(user)
        return user
```

### Repository Pattern

```python
class UserRepository:
    """Handles user data persistence"""

    def save(self, user: User) -> None:
        """Persist user to database"""
        user.save()

    def find_by_id(self, user_id: int) -> Optional[User]:
        """Find user by ID"""
        return User.objects.filter(id=user_id).first()
```

### Factory Pattern

```python
class ProjectGeneratorFactory:
    """Creates appropriate generator based on configuration"""

    @staticmethod
    def create(config: ProjectConfig) -> ProjectGenerator:
        if config.theme == "react":
            return ReactProjectGenerator(config)
        elif config.theme == "html":
            return HTMLProjectGenerator(config)
        else:
            raise ValueError(f"Unknown theme: {config.theme}")
```

## Invocation

When an agent invokes this skill:

1. Check all modified files for tech stack compliance
2. Verify layer boundaries are respected
3. Confirm patterns are followed consistently
4. Report violations with specific recommendations

## Output Format

```yaml
architecture_compliance:
  tech_stack: PASS | FAIL
  layer_boundaries: PASS | ISSUES
  patterns: PASS | ISSUES

violations:
  - type: prohibited_technology
    file: requirements.txt
    description: "requirements.txt found - use Poetry"
    recommendation: "Delete file, add dependencies to pyproject.toml"

  - type: layer_boundary_violation
    file: src/module/views.py
    line: 45
    description: "View directly accessing database"
    recommendation: "Use service layer for database operations"
```

## Related Skills

- `code-principles` - For code quality
- `testing-standards` - For test patterns
