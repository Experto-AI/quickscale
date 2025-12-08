# Release v0.70.0: Plan/Apply System — Existing Project Support

**Release Date:** 2025-12-19
**Status:** ✅ Complete

## Summary

This release adds comprehensive existing project support to the QuickScale plan/apply system. Users can now view project status, add new modules to existing projects, and reconfigure project options without starting from scratch.

## Key Features

### Status Command (`quickscale status`)

New command to display project state, modules, and pending changes:

```bash
$ cd myproject
$ quickscale status

📊 Project Status

Project: myproject
Theme: showcase_html
Created: 2025-12-19 10:00:00 (3 hours ago)
Last Applied: 2025-12-19 12:00:00 (1 hour ago)

📦 Applied Modules (2):
  ✓ auth (v0.70.0) — embedded 2025-12-19 10:00:00
  ✓ blog (v0.70.0) — embedded 2025-12-19 12:00:00

🔄 Pending Changes:
  Changes to apply:
    Modules to add (1): + listings
    Modules unchanged (2): auth, blog

🐳 Docker Status:
  Status: running
  Services: web, db

Run 'quickscale apply' to apply pending changes.
```

Features:
- Display project info (name, theme, timestamps)
- List applied modules with versions and embed dates
- Show pending changes (delta between config and state)
- Show Docker container status
- Detect drift (orphaned/missing modules)
- JSON output support (`--json`)

### Add Modules (`quickscale plan --add`)

Add new modules to existing projects interactively:

```bash
$ cd myproject
$ quickscale plan --add

📊 Existing Project Detected
Project: myproject
Theme: showcase_html (locked)

📦 Currently installed modules:
  ✓ auth

📋 Select additional modules to add:
  [x] blog
  [x] listings
  [ ] billing (coming soon)

✅ Configuration updated: quickscale.yml
Run 'quickscale apply' to embed selected modules.
```

Features:
- Detect existing project via `.quickscale/state.yml` or `quickscale.yml`
- Load current configuration from state
- Show currently installed modules
- Skip already-installed modules in selection
- Update `quickscale.yml` with new modules

### Reconfigure Project (`quickscale plan --reconfigure`)

Modify project options while preserving existing modules:

```bash
$ cd myproject
$ quickscale plan --reconfigure

📊 Reconfigure Existing Project
Project: myproject (locked)
Theme: showcase_html (locked after creation)

📦 Installed modules (1):
  ✓ auth

🐳 Docker Configuration:
  Start Docker on 'quickscale up'? [Y/n]: y
  Build Docker images on 'quickscale build'? [Y/n]: n

📋 Add additional modules:
  [x] blog
  [ ] listings

✅ Configuration updated: quickscale.yml
Run 'quickscale apply' to apply changes.
```

Features:
- Load state from `.quickscale/state.yml`
- Show locked options (project name, theme)
- Allow modifying Docker configuration
- Allow adding new modules
- Preserve existing module configuration

## Implementation Details

### New Modules

#### `status_command.py`

Complete status command implementation:
- `_get_docker_status()`: Query Docker container status
- `_format_datetime()`: Format timestamps with relative time
- `_detect_project_context()`: Find project root and load state
- `_load_config()`: Load and validate `quickscale.yml`
- `_display_project_info()`: Show project metadata
- `_display_modules()`: List applied modules
- `_display_pending_changes()`: Show delta with config
- `_display_docker_status()`: Show container status
- `_display_drift_warnings()`: Show orphaned/missing modules
- `status()`: Main command with `--json` option

#### Plan Command Extensions

Added to `plan_command.py`:
- `_detect_existing_project()`: Check for state/config files
- `_get_applied_modules()`: Extract modules from state
- `_select_modules_to_add()`: Interactive module selection
- `_handle_add_modules()`: `--add` flag workflow
- `_handle_reconfigure()`: `--reconfigure` flag workflow

### Modified Files

#### `main.py`

Registered status command:
```python
from quickscale_cli.commands.status_command import status
cli.add_command(status)
```

#### `plan_command.py`

Extended plan command signature:
```python
@click.command(name="plan")
@click.argument("name", default=None, required=False)
@click.option("--add", is_flag=True, help="Add modules to existing project")
@click.option("--reconfigure", is_flag=True, help="Reconfigure existing project")
def plan(name, output, add, reconfigure):
    ...
```

## Files Changed

### New Files

| File | Purpose |
|------|---------|
| `quickscale_cli/src/quickscale_cli/commands/status_command.py` | Status command implementation |
| `quickscale_cli/tests/test_status_command.py` | Status command tests (12 tests) |
| `quickscale_cli/tests/test_project_detection.py` | Project detection tests (6 tests) |
| `quickscale_cli/tests/test_plan_add.py` | Plan --add tests (9 tests) |
| `quickscale_cli/tests/test_plan_reconfigure.py` | Plan --reconfigure tests (10 tests) |

### Modified Files

| File | Changes |
|------|---------|
| `quickscale_cli/src/quickscale_cli/commands/plan_command.py` | Added --add and --reconfigure flags with handlers |
| `quickscale_cli/src/quickscale_cli/main.py` | Registered status command |
| `quickscale_cli/tests/test_plan_command.py` | Updated help text assertion |
| `docs/technical/roadmap.md` | Marked v0.70.0 tasks complete |

## Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_status_command.py` | 12 | 100% |
| `test_project_detection.py` | 6 | 100% |
| `test_plan_add.py` | 9 | 98% |
| `test_plan_reconfigure.py` | 10 | 100% |
| **status_command.py** | - | 79% |
| **plan_command.py** (new code) | - | 82% |

Total: 37 new tests for v0.70.0 features.

## Validation Commands

```bash
# Lint passes
./scripts/lint.sh

# New tests pass
poetry run pytest quickscale_cli/tests/test_status_command.py \
                  quickscale_cli/tests/test_project_detection.py \
                  quickscale_cli/tests/test_plan_add.py \
                  quickscale_cli/tests/test_plan_reconfigure.py -v

# Full test suite passes (380 tests)
poetry run pytest quickscale_cli/tests/ -v
```

## Usage Examples

### Check Project Status

```bash
# In project directory
quickscale status

# JSON output for scripting
quickscale status --json
```

### Add Modules to Existing Project

```bash
# Interactive module selection
quickscale plan --add

# Then apply
quickscale apply
```

### Reconfigure Project

```bash
# Interactive reconfiguration
quickscale plan --reconfigure

# Then apply
quickscale apply
```

## Breaking Changes

None. Backward compatible with existing plan/apply workflow.

## Known Limitations

1. Theme cannot be changed after project creation (locked)
2. Project name cannot be changed after creation (locked)
3. Module removal not yet implemented (planned for v0.71.0)

## Next Steps (v0.71.0)

- Module manifests with mutable/immutable config
- `quickscale remove <module>` command
- Settings.py updates for mutable config

## Contributors

- Victor (lead implementation)
- Claude (AI assistant)

## References

- [Roadmap v0.70.0](../technical/roadmap.md#v0700-planapply-system---existing-project-support)
- [v0.69.0 Implementation](./release-v0.69.0-implementation.md)
