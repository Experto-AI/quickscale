# QuickScale Testing Infrastructure

This document describes QuickScale's PostgreSQL-only testing infrastructure.

## Overview

QuickScale uses PostgreSQL for all testing to achieve production-test parity and eliminate dual-database complexity. 

## Test Infrastructure Components

### Core Files
- **`tests/docker-compose.test.yml`** - PostgreSQL test database container configuration
- **`tests/.env.test`** - Test environment variables for PostgreSQL
- **`tests/core/test_db_config.py`** - Centralized PostgreSQL test database configuration
- **`tests/conftest.py`** - pytest fixtures and test setup

### Database Configuration
- **PostgreSQL 15-alpine**: Optimized container with performance settings
- **Hard Failure Policy**: No SQLite fallbacks - explicit errors when PostgreSQL unavailable
- **Centralized Config**: Single source of truth for test database connections
- **Environment Variables**: Configurable through .env.test file

## Quick Start

1. **Start test database:**
   ```bash
   cd tests/
   docker-compose -f docker-compose.test.yml up -d
   
   # Wait for database to be ready
   docker-compose -f docker-compose.test.yml exec test-db pg_isready -U quickscale_test
   ```

2. **Run tests:**
   ```bash
   # All tests (recommended - use test runner script)
   ./run_tests.sh
   
   # Or run pytest directly
   python -m pytest tests/
   
   # Specific test categories
   python -m pytest tests/quickscale_generator/
   python -m pytest tests/django_functionality/
   python -m pytest tests/integration/
   python -m pytest tests/e2e/
   
   # Use test runner script with options
   ./run_tests.sh --generator
   ./run_tests.sh --django
   ./run_tests.sh --integration
   ./run_tests.sh --coverage
   ```

3. **Stop test database:**
   ```bash
   cd tests/
   docker-compose -f docker-compose.test.yml down
   ```

## Configuration Details

### PostgreSQL Container Settings
```yaml
# docker-compose.test.yml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: quickscale_test
      POSTGRES_USER: quickscale_test
      POSTGRES_PASSWORD: quickscale_test_password
    ports:
      - "5433:5432"
    tmpfs:
      - /var/lib/postgresql/data
    command: >
      postgres
      -c shared_buffers=256MB
      -c max_connections=100
      -c effective_cache_size=1GB
      -c maintenance_work_mem=64MB
```

### Environment Variables
```bash
# .env.test
DATABASE_URL=postgresql://quickscale_test:quickscale_test_password@localhost:5433/quickscale_test
POSTGRES_DB=quickscale_test
POSTGRES_USER=quickscale_test
POSTGRES_PASSWORD=quickscale_test_password
```

### Hard Failure Configuration
```python
# tests/core/test_db_config.py
def get_test_db_config():
    try:
        import psycopg2
    except ImportError:
        raise ImportError(
            "PostgreSQL testing requires psycopg2-binary. "
            "Install with: pip install psycopg2-binary"
        )
    
    # Hard failure - no SQLite fallback
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'quickscale_test',
        'USER': 'quickscale_test',
        'PASSWORD': 'quickscale_test_password',
        'HOST': 'localhost',
        'PORT': '5433',
    }
```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Ensure PostgreSQL container is running
   - Check port 5433 is available
   - Verify environment variables are set

2. **Import Errors**
   - Install psycopg2-binary: `pip install psycopg2-binary`
   - Ensure PostgreSQL client libraries are available

3. **Test Failures**
   - Check database connectivity with `validate_test_db_connection()`
   - Verify container health: `docker-compose -f docker-compose.test.yml ps`
   - Check logs: `docker-compose -f docker-compose.test.yml logs postgres`

### Performance Optimization
- Container uses tmpfs for faster I/O
- Optimized PostgreSQL settings for testing
- Parallel test execution supported
- Database recreated for each test run

