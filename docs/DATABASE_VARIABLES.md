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
     # Map Django DB_* variables to Postgres POSTGRES_* variables
     - POSTGRES_DB=${DB_NAME:-quickscale}
     - POSTGRES_USER=${DB_USER:-admin}
     - POSTGRES_PASSWORD=${DB_PASSWORD:-adminpasswd}
     - POSTGRES_SHARED_BUFFERS=${DB_SHARED_BUFFERS:-128MB}
     - POSTGRES_WORK_MEM=${DB_WORK_MEM:-16MB}
   ```
3. **entrypoint.sh** uses the DB_* variables exclusively for health checks and database operations
4. **Django settings.py** uses DB_* variables for database connection configuration

### Benefits

- **Consistency**: One source of truth for database configuration
- **Simplicity**: Users only need to configure DB_* variables
- **Compatibility**: Still works with standard PostgreSQL Docker image
- **Maintainability**: Reduces potential for configuration errors
- **Flexibility**: Support for port conflicts and performance tuning

### Security Considerations

- **Production Passwords**: Always use secure, randomly generated passwords in production
- **Default Values**: The default `DB_PASSWORD=adminpasswd` is only suitable for development
- **Port Exposure**: `DB_PORT_EXTERNAL` controls which port PostgreSQL is accessible from outside Docker
- **Access Control**: The database is only accessible from within the Docker network by default

### Advanced Configuration

#### Port Conflict Resolution
QuickScale can automatically handle port conflicts:
- Set `DB_PORT_EXTERNAL_ALTERNATIVE_FALLBACK=true` to enable automatic fallback ports
- If port 5432 is in use, QuickScale will try 5433, 5434, etc.
- This prevents conflicts when running multiple PostgreSQL instances

#### Performance Optimization
Adjust memory settings based on your system resources:
- `DB_MEMORY_LIMIT`: Total memory available to PostgreSQL container
- `DB_SHARED_BUFFERS`: PostgreSQL's shared memory for caching (typically 25% of available RAM)
- `DB_WORK_MEM`: Memory for query operations (sort, hash joins)

### Database Configuration Variables

QuickScale supports the following database-related environment variables:

#### Core Database Variables
| Variable     | Description                    | Default      | Required |
|-------------|-------------------------------|--------------|----------|
| `DB_HOST`   | Database hostname             | `db`         | No       |
| `DB_PORT`   | Database port (internal)      | `5432`       | No       |
| `DB_NAME`   | Database name                 | `quickscale` | No       |
| `DB_USER`   | Database username             | `admin`      | No       |
| `DB_PASSWORD` | Database password           | `adminpasswd` | **Yes*** |

*Required for production deployments with secure values.

#### Port Configuration
| Variable                                | Description                           | Default | Required |
|----------------------------------------|---------------------------------------|---------|----------|
| `DB_PORT_EXTERNAL`                     | External port mapping for PostgreSQL | `5432`  | No       |
| `DB_PORT_EXTERNAL_ALTERNATIVE_FALLBACK` | Enable automatic port fallback      | `true`  | No       |

#### Performance Tuning Variables
| Variable              | Description                        | Default  | Required |
|----------------------|-----------------------------------|----------|----------|
| `DB_MEMORY_LIMIT`    | Memory limit for database container | `1G`    | No       |
| `DB_MEMORY_RESERVE`  | Memory reservation for database     | `512M`  | No       |
| `DB_SHARED_BUFFERS`  | PostgreSQL shared buffers setting   | `128MB` | No       |
| `DB_WORK_MEM`        | PostgreSQL work memory setting      | `16MB`  | No       |

### Configuration Example

In your `.env` file, you only need to set the essential variables:

```bash
# Essential Database Settings
DB_NAME=quickscale
DB_USER=admin
DB_PASSWORD=securepassword     # Use a secure password in production!

# Optional: Port Configuration (if defaults conflict)
DB_PORT_EXTERNAL=5432
DB_PORT_EXTERNAL_ALTERNATIVE_FALLBACK=true

# Optional: Performance Tuning (adjust based on your needs)
DB_MEMORY_LIMIT=1G
DB_MEMORY_RESERVE=512M
DB_SHARED_BUFFERS=128MB
DB_WORK_MEM=16MB
```

The system will automatically use these values for both Django database connections and PostgreSQL container configuration. 