# Versioning (single-source)

Keep versioning simple: edit the single `VERSION` file at the repository root
and use the bundled script to sync metadata and embed a static package version.

## Release Workflow

### 1. Edit VERSION
Open `VERSION` and set the new version (e.g., 0.56.3 or 0.57.0)

```bash
echo "0.58.0" > VERSION
```

### 2. Update all files
Run the update command to sync everything:

```bash
./scripts/version_tool.sh update
```

This command automatically:
- Updates all `pyproject.toml` versions
- Updates inter-package dependency constraints (e.g., `quickscale-core = "^0.58.0"`)
- Embeds static `_version.py` files into packages
- Updates version fields in documentation YAML files

### 3. Verify (optional)
Check that everything is consistent:

```bash
./scripts/version_tool.sh check
```

### 4. Commit, tag, push

```bash
git add VERSION quickscale_core/pyproject.toml quickscale_cli/pyproject.toml \
  quickscale/pyproject.toml \
  quickscale_core/src/quickscale_core/_version.py \
  quickscale_cli/src/quickscale_cli/_version.py
git commit -m "v$(cat VERSION)"
git tag "v$(cat VERSION)"
git push && git push --tags
```

### 5. Build & publish
Use the automated publishing script:

```bash
# Test on TestPyPI first
./scripts/publish.sh test

# After verification, publish to PyPI
./scripts/publish.sh prod

# Or do both in one go (with manual verification step)
./scripts/publish.sh full
```

Or install globally for local testing:

```bash
./scripts/install_global.sh
quickscale --version
```

## Available Commands

### version_tool.sh

```bash
# Check version consistency
./scripts/version_tool.sh check

# Update all files to match VERSION
./scripts/version_tool.sh update
```

### Quick Reference

```bash
# Full release workflow
echo "0.58.0" > VERSION
./scripts/version_tool.sh update
./scripts/version_tool.sh check
git add -A
git commit -m "v$(cat VERSION)"
git tag "v$(cat VERSION)"
git push && git push --tags
./scripts/publish.sh full
```

