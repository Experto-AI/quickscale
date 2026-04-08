# QuickScale Docker Workflows

Complete guide to Docker integration, auto-start behavior, and troubleshooting.

## Table of Contents
1. [Docker Configuration](#docker-configuration)
2. [Auto-Start Behavior](#auto-start-behavior)
3. [Manual Control](#manual-control)
4. [Common Scenarios](#common-scenarios)
5. [Troubleshooting](#troubleshooting)

---

## Docker Configuration

QuickScale uses two Docker settings in `quickscale.yml`:

```yaml
docker:
  start: true   # Auto-start services during 'quickscale apply'?
  build: true   # Rebuild Docker images during start?
```

### `docker.start`

Controls whether `quickscale apply` automatically starts Docker services.

**Options:**
- `true` (default): Services start automatically during first apply
- `false`: Services require manual `quickscale up`

**Set during `quickscale plan` wizard:**
```
🐳 Docker Configuration:
  Start Docker services after apply? [Y/n]: y  ← Sets docker.start
  Build Docker images? [Y/n]: y               ← Sets docker.build
```

### `docker.build`

Controls whether to rebuild Docker images during auto-start.

**Options:**
- `true` (default): Rebuilds images (equivalent to `quickscale up --build`)
- `false`: Uses cached images (faster but may be outdated)

**When to use `build: false`:**
- Rapid iteration without dependency changes
- CI/CD pipelines with pre-built images
- Resource-constrained environments

**When to use `build: true`:**
- First-time setup
- After changing dependencies in pyproject.toml
- After pulling updates from git
- When troubleshooting "module not found" errors

---

## Auto-Start Behavior

### When Services Auto-Start

`quickscale apply` automatically starts Docker services when:

1. ✅ **`docker.start: true` in quickscale.yml** (default)
2. ✅ **`--no-docker` flag NOT used**

This applies to both first-time generations and existing-project re-applies.

### When Services DO NOT Auto-Start

Services require manual `quickscale up` when:

1. ❌ **`docker.start: false` in config**
2. ❌ **Using `quickscale apply --no-docker`**

After `quickscale down`, services stay stopped until you run `quickscale up` or a later `quickscale apply` that qualifies for auto-start.

### Execution Order During Apply

```
quickscale apply executes in this order:

1. Validate quickscale.yml
2. Generate project files (first time only)
3. Initialize git repository (first time only)
4. Create initial commit (first time only)
5. Embed modules via git subtree
6. Refresh the Poetry lockfile and run poetry install
7. If this is an existing project and docker.start: false, run local migrations
8. If docker.start: true and --no-docker is not set, start Docker services  ← Auto-start here
9. When Docker auto-start runs, QuickScale then runs migrations in the backend container
10. Fresh projects without Docker auto-start, and any --no-docker run, leave startup as a manual next step
```

---

## Manual Control

### Starting Services Manually

```bash
# Start services (uses cached images)
quickscale up

# Start services with rebuild
quickscale up --build

# Start services with no cache rebuild
quickscale up --build --no-cache
```

### Stopping Services

```bash
# Stop services (containers remain)
quickscale down

# Stop and remove volumes (⚠️ destroys database!)
docker-compose down -v
```

### Checking Status

```bash
# Check running services
quickscale ps

# View logs
quickscale logs backend
quickscale logs db
quickscale logs -f backend  # Follow logs
```

---

## Common Scenarios

### Scenario 1: Fresh Project with Auto-Start (Default)

```bash
quickscale plan myapp
# Wizard defaults: docker.start=true, docker.build=true
cd myapp
quickscale apply
# ✅ Services auto-start and the Docker startup path handles migrations

# Verify immediately:
quickscale ps
curl http://localhost:8000
```

**No `quickscale up` needed!** Services started automatically.

---

### Scenario 2: Fresh Project Without Auto-Start

```bash
quickscale plan myapp
# During wizard: "Start Docker services? [Y/n]: n"
cd myapp
quickscale apply
# ❌ Services do NOT start
# ❌ Migrations are left as a manual next step

# Start manually:
quickscale up

# Or stay outside Docker:
poetry run python manage.py migrate
poetry run python manage.py runserver
```

---

### Scenario 3: Native Python (No Docker)

```bash
quickscale plan myapp
cd myapp
quickscale apply --no-docker
# Skip Docker entirely

# Use native Python:
poetry install
poetry run python manage.py migrate
poetry run python manage.py runserver
# Visit http://localhost:8000
```

---

### Scenario 4: Adding Module to Existing Project

```bash
cd myapp
vim quickscale.yml  # Add 'crm' module
quickscale apply
# ✅ Embeds crm module
# ✅ Refreshes dependencies and managed wiring
# ✅ If docker.start: true, reruns Docker startup and container migrations
# ✅ If docker.start: false, keeps Docker stopped but still runs local migrations

# Manual startup is only needed when auto-start is disabled or you used --no-docker:
quickscale up

# Restart only if your workflow needs a fresh container start:
quickscale down
quickscale up
```

---

### Scenario 5: After `quickscale down`

```bash
quickscale down  # Stop services

# Later, restart:
quickscale up    # Manual start required
```

---

### Scenario 6: Debugging with Rebuild

```bash
# Something not working? Rebuild everything:
quickscale down
quickscale up --build --no-cache

# Still not working? Nuclear option:
quickscale down
docker-compose down -v  # ⚠️ Destroys database!
quickscale up --build
quickscale manage migrate
quickscale manage createsuperuser
```

---

## Troubleshooting

### "Port 8000 already in use"

**Cause**: Another service using port 8000, or previous QuickScale instance still running.

**Solution:**
```bash
# Check what's using port 8000
lsof -i :8000

# Stop QuickScale services
quickscale down

# Or kill process manually
kill -9 <PID>
```

---

### "Docker daemon not running"

**Cause**: Docker Desktop or Docker daemon not started.

**Solution:**
```bash
# macOS: Start Docker Desktop
open -a Docker

# Linux: Start Docker daemon
sudo systemctl start docker

# Verify
docker ps
```

---

### "Services not starting during apply"

**Cause**: `docker.start: false` in config, or `--no-docker` flag used.

**Solution:**
```bash
# Check config
cat quickscale.yml | grep "start:"

# If docker.start: false, change to true:
vim quickscale.yml
# docker:
#   start: true

# Or start manually:
quickscale up
```

---

### "Module not found after embed"

**Cause**: Docker image built before module was embedded.

**Solution:**
```bash
# Rebuild images with new module
quickscale down
quickscale up --build
```

---

### "Migrations not applying"

**Cause**: Database out of sync, or migrations run before module embed.

**Solution:**
```bash
# Re-run migrations inside container
quickscale manage migrate

# Or rebuild everything:
quickscale down
docker-compose down -v  # ⚠️ Destroys database
quickscale up --build
quickscale manage migrate
```

---

### "Can't connect to database"

**Cause**: PostgreSQL container not started, or environment variables incorrect.

**Solution:**
```bash
# Check PostgreSQL is running
quickscale ps
# Should show 'db' service

# Check logs
quickscale logs db

# Verify environment variables
cat .env | grep DATABASE

# Restart services
quickscale down
quickscale up
```

---

### "Changes not reflecting in container"

**Cause**: Code changes not synced to container, or need restart.

**Solution:**
```bash
# For code changes (with volume mounting):
# Changes should reflect immediately - just refresh browser

# For dependency changes (pyproject.toml):
quickscale down
quickscale up --build

# For settings changes:
quickscale down
quickscale up  # No rebuild needed
```

---

## Summary Decision Tree

```
┌─ quickscale plan myapp
│
├─ docker.start: true (default)
│  ├─ cd myapp
│  ├─ quickscale apply
│  └─ ✅ Fresh and existing applies auto-start Docker and run migrations in the backend container
│
├─ docker.start: false
│  ├─ cd myapp
│  ├─ quickscale apply
│  ├─ Fresh project → ❌ no auto-start; startup and migrations stay manual
│  └─ Existing project → ✅ local migrations run, but Docker stays stopped
│
└─ --no-docker flag
   ├─ cd myapp
   ├─ quickscale apply --no-docker
  └─ ❌ Skip Docker (startup stays manual; migrations are manual unless this is an existing project with docker.start: false)
```

---

## Best Practices

### Development Workflow

**Day 1 (First setup):**
```bash
quickscale plan myapp
cd myapp
quickscale apply
# Services auto-start ✅

quickscale manage createsuperuser
# Open http://localhost:8000 and start coding
```

**End of day:**
```bash
quickscale down
# Free up resources
```

**Day 2 (Resume work):**
```bash
cd myapp
quickscale up  # Manual start needed
quickscale manage migrate  # If you added migrations
# Resume coding
```

### Production Deployment

For production, use Docker Compose or container orchestration:

```bash
# Build production image
docker build -t myapp:latest .

# Run with production settings
docker run -d \
  -p 8000:8000 \
  -e SECRET_KEY="production-secret" \
  -e DEBUG=False \
  -e DATABASE_URL="postgresql://..." \
  myapp:latest
```

### CI/CD Pipeline

```yaml
# .github/workflows/test.yml
- name: Test with Docker
  run: |
    quickscale plan testapp
    cd testapp
    quickscale apply --no-docker  # Skip Docker in CI
    poetry run pytest
```

---

## Quick Reference

| Situation | Command | Auto-start? |
|-----------|---------|-------------|
| `quickscale apply` with `docker.start: true` | `cd myapp && quickscale apply` | ✅ Yes (fresh and existing projects; backend-container migrations run too) |
| After `quickscale down` | `quickscale up` | ❌ No (manual start) |
| Existing-project apply with `docker.start: false` | `quickscale apply` | ❌ No Docker auto-start, but local migrations still run |
| Changed dependencies | `quickscale up --build` | ❌ No (manual with rebuild) |
| Fresh install | Follow quickstart in README | ✅ Yes (on first apply) |

---

## Related Documentation

- [User Manual](./user_manual.md) - Complete command reference
- [Development Guide](./development.md) - Setup for contributors
- [README](../../README.md) - Quick start guide
- [Railway Deployment](../deployment/railway.md) - Production deployment

---

**Last Updated**: 2026-04-08
**QuickScale Version**: current v0.83.0 implementation line (unreleased)
