# QuickScale Test Suite

This directory contains test code for the QuickScale project.

## 📖 Complete Testing Documentation

**For comprehensive testing information, see the main documentation:**

- **[Testing Guide](../docs/testing-guide.md)** - Complete guide to testing in QuickScale
- **[Testing Infrastructure](../docs/testing-infrastructure.md)** - Database setup and infrastructure
- **[Testing Standards](../docs/contrib/shared/testing_standards.md)** - Code quality and testing principles

## 🚀 Quick Start

```bash
# Start test database
cd tests/
docker-compose -f docker-compose.test.yml up -d

# Run all tests
./run_tests.sh

# Stop test database  
docker-compose -f docker-compose.test.yml down
```

## 📁 Test Structure

- `quickscale_generator/` - Tests for CLI commands and project generation
- `django_functionality/` - Tests for generated Django application features  
- `integration/` - Cross-system tests using real generated projects
- `e2e/` - End-to-end tests with full Docker environment

## 🎯 Test Categories

| Test Type | Location | Use For | Speed |
|-----------|----------|---------|-------|
| **Unit** | `quickscale_generator/`<br>`django_functionality/` | Individual components, CLI commands | ⚡ Fast |
| **Integration** | `integration/` | Cross-system, Django URLs, real projects | ⏱️ Medium |
| **E2E** | `e2e/` | Complete workflows, external services | 🐌 Slow |

## 🔧 Common Commands

```bash
# Run specific test categories
./run_tests.sh --generator      # CLI and generator tests
./run_tests.sh --django         # Django functionality tests  
./run_tests.sh --integration    # Integration tests
./run_tests.sh --coverage       # Run with coverage report

# Debug failing tests
./run_tests.sh --failures-only  # Show only failed tests
./run_tests.sh --exitfirst      # Stop on first failure
```

---

**For detailed information, examples, and troubleshooting, see [Testing Guide](../docs/testing-guide.md)**
