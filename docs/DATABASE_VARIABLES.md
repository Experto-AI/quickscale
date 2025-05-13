# Database Environment Variables in QuickScale

## Standardization on DB_* Variables

QuickScale uses a standardized approach to database configuration through environment variables. This document explains the approach and changes made to improve consistency.

### The Problem

Previously, the codebase had duplication between two sets of variables:

1. `DB_NAME`, `DB_USER`, `DB_PASSWORD`, etc. - Traditional Django naming convention
2. `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, etc. - Standard PostgreSQL Docker image variables

This duplication violated the DRY (Don't Repeat Yourself) principle and could lead to inconsistencies if variables were set differently.

### The Solution

The codebase has been updated to standardize on the `DB_*` variables for all Django settings, while mapping these values to the `POSTGRES_*` variables required by the PostgreSQL Docker image:

1. **Django and application code** uses `DB_NAME`, `DB_USER`, etc. consistently
2. **docker-compose.yml** maps these variables to their PostgreSQL equivalents:
   ```yaml
   environment:
     - POSTGRES_DB=${DB_NAME:-quickscale}  # Map DB_NAME to POSTGRES_DB for PostgreSQL
   ```
3. **entrypoint.sh** uses the DB_* variables exclusively

### Benefits

- **Consistency**: One source of truth for database configuration
- **Simplicity**: Users only need to configure DB_* variables
- **Compatibility**: Still works with standard PostgreSQL Docker image
- **Maintainability**: Reduces potential for configuration errors

### Configuration Example

In your `.env` file, you only need to set:

```bash
# Database Settings
DB_HOST=db
DB_NAME=quickscale
DB_USER=admin
DB_PASSWORD=securepassword
```

The system will automatically use these values for both Django database connections and PostgreSQL container configuration. 