# Release v0.71.0: Plan/Apply System — Module Manifests & Config Mutability

**Release Date:** 2025-06-25
**Status:** ✅ Complete

## Summary

This release completes the Plan/Apply system (v0.68.0-v0.71.0) with module manifests enabling configuration mutability. Users can now modify mutable module options after initial embed without re-embedding, while immutable options are locked at embed time. Also introduces the `quickscale remove` command for module removal.

## Key Features

### Module Manifest System

New `module.yml` manifest files define module configuration options with mutability rules:

```yaml
# quickscale_modules/auth/module.yml
name: auth
version: 0.73.0
description: Authentication module with django-allauth

config:
  mutable:
    registration_enabled:
      type: bool
      default: true
      django_setting: AUTH_REGISTRATION_ENABLED
      description: Enable/disable new user registration

    email_verification:
      type: string
      default: optional
      allowed_values: [none, optional, mandatory]
      django_setting: AUTH_EMAIL_VERIFICATION
      description: Email verification requirement level

  immutable:
    social_providers:
      type: list
      default: []
      description: OAuth providers (requires code changes after embed)
```

Features:
- **Mutable options**: Can be changed after embed, updates `settings.py` automatically
- **Immutable options**: Locked at embed time, require re-embed to change
- **Type validation**: bool, string, int, float, list with allowed_values constraints
- **Django settings mapping**: Direct mapping to Django settings keys

### Mutable Config Changes

Update mutable configuration in `quickscale.yml` and apply:

```bash
$ cat quickscale.yml
modules:
  auth:
    options:
      registration_enabled: false  # Changed from true
      email_verification: mandatory  # Changed from optional

$ quickscale apply

📋 Plan: 1 config changes

Config Changes:
  auth:
    ✏️  registration_enabled: true → false
    ✏️  email_verification: optional → mandatory

Apply these changes? [y/N]: y

✅ Applied changes:
  • Updated settings.py: AUTH_REGISTRATION_ENABLED = False
  • Updated settings.py: AUTH_EMAIL_VERIFICATION = 'mandatory'
  • State saved to .quickscale/state.yml

📝 Post-apply notes:
  • Registration is now disabled - new users cannot sign up
  • Email verification is now required for all users
```

### Immutable Config Rejection

Attempting to change immutable options shows helpful error:

```bash
$ cat quickscale.yml
modules:
  auth:
    options:
      social_providers: [google]  # Try to change immutable option

$ quickscale apply

❌ Error: Cannot modify immutable options

The following immutable options cannot be changed after module embed:
  auth:
    • social_providers: [] → ['google']

To change immutable options:
  1. Run 'quickscale remove auth' to remove the module
  2. Update quickscale.yml with new configuration
  3. Run 'quickscale apply' to re-embed with new settings

Note: Removing a module may result in data loss. Back up your database first.
```

### Remove Command (`quickscale remove`)

Remove modules with data loss warnings:

```bash
$ quickscale remove auth

⚠️  Warning: Removing module 'auth'

This will:
  • Delete auth app directory
  • Remove auth from INSTALLED_APPS
  • Remove auth URL patterns

This will NOT:
  • Delete database tables (requires manual migration)
  • Remove user data from database

The following data may be affected:
  • User accounts and profiles
  • Authentication tokens
  • Social account connections

Are you sure you want to remove 'auth'? [y/N]: y

✅ Module 'auth' removed
  • Deleted: myproject/auth/
  • Updated: quickscale.yml
  • Updated: .quickscale/state.yml

⚠️  Next steps:
  1. Remove 'auth' from INSTALLED_APPS in settings.py
  2. Remove auth URL patterns from urls.py
  3. Run migrations: python manage.py migrate
  4. Consider backing up and removing auth database tables
```

## Implementation Details

### New Modules

#### `quickscale_core/manifest/schema.py`

Manifest schema with dataclasses:

```python
@dataclass
class ConfigOption:
    name: str
    option_type: str  # bool, string, int, float, list
    mutability: str   # mutable, immutable
    django_setting: str | None = None
    default: Any = None
    allowed_values: list[Any] | None = None
    description: str = ""

@dataclass
class ModuleManifest:
    name: str
    version: 0.73.0
    description: str
    mutable_options: dict[str, ConfigOption]
    immutable_options: dict[str, ConfigOption]
```

#### `quickscale_core/manifest/loader.py`

Manifest loading and validation:

```python
def load_manifest(module_path: Path) -> ModuleManifest:
    """Load and validate module.yml manifest."""

def find_module_manifest(module_name: str) -> Path | None:
    """Find manifest file for a module."""
```

#### `quickscale_core/settings_manager.py`

Django settings.py updater:

```python
def update_setting(settings_path: Path, key: str, value: Any) -> bool:
    """Update or add a setting in settings.py."""

def apply_mutable_config_changes(
    settings_path: Path,
    changes: list[ConfigChange]
) -> list[str]:
    """Apply all mutable config changes to settings.py."""
```

#### `quickscale_cli/schema/delta.py`

Extended delta detection with config changes:

```python
@dataclass
class ConfigChange:
    module: str
    option: str
    old_value: Any
    new_value: Any
    mutability: str
    django_setting: str | None

@dataclass
class ModuleConfigDelta:
    mutable_changes: list[ConfigChange]
    immutable_changes: list[ConfigChange]

def compute_delta(
    desired: QuickScaleConfig,
    applied: AppliedState,
    manifests: dict[str, ModuleManifest]
) -> tuple[Delta, ModuleConfigDelta]:
    """Compute full delta including config changes."""
```

#### `quickscale_cli/commands/remove_command.py`

Module removal implementation:

```python
@click.command()
@click.argument("module_name")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
def remove(module_name: str, force: bool):
    """Remove an embedded module from the project."""
```

### Modified Files

#### `apply_command.py`

Extended to handle config changes:
- Load manifests for applied modules
- Compute config delta (mutable vs immutable)
- Reject immutable changes with helpful message
- Apply mutable changes via settings_manager
- Show post-apply notes for config changes

#### `main.py`

Registered remove command:
```python
from quickscale_cli.commands.remove_command import remove
cli.add_command(remove)
```

## Files Changed

### New Files

| File | Purpose |
|------|---------|
| `quickscale_core/src/quickscale_core/manifest/__init__.py` | Manifest package |
| `quickscale_core/src/quickscale_core/manifest/schema.py` | ConfigOption, ModuleManifest dataclasses |
| `quickscale_core/src/quickscale_core/manifest/loader.py` | Manifest loading and validation |
| `quickscale_core/src/quickscale_core/settings_manager.py` | Django settings.py updater |
| `quickscale_cli/src/quickscale_cli/schema/delta.py` | ConfigChange, ModuleConfigDelta classes |
| `quickscale_cli/src/quickscale_cli/commands/remove_command.py` | Remove command |
| `quickscale_modules/auth/module.yml` | Auth module manifest |
| `quickscale_core/tests/test_manifest_schema.py` | Manifest schema tests |
| `quickscale_core/tests/test_manifest_loader.py` | Manifest loader tests |
| `quickscale_core/tests/test_settings_manager.py` | Settings manager tests |
| `quickscale_cli/tests/test_config_delta.py` | Config delta tests |
| `quickscale_cli/tests/test_remove_command.py` | Remove command tests |

### Modified Files

| File | Changes |
|------|---------|
| `quickscale_cli/src/quickscale_cli/commands/apply_command.py` | Config mutability handling |
| `quickscale_cli/src/quickscale_cli/main.py` | Registered remove command |
| `docs/technical/roadmap.md` | Marked v0.71.0 complete |
| `docs/technical/decisions.md` | Module Manifest Architecture section |

## Test Coverage

| Test File | Tests | Purpose |
|-----------|-------|---------|
| `test_manifest_schema.py` | 15 | ConfigOption and ModuleManifest validation |
| `test_manifest_loader.py` | 12 | YAML parsing and manifest loading |
| `test_settings_manager.py` | 14 | Django settings.py updates |
| `test_config_delta.py` | 18 | Mutable/immutable delta detection |
| `test_remove_command.py` | 10 | Module removal workflow |

Coverage on new files:
- `manifest/schema.py`: 85%
- `manifest/loader.py`: 82%
- `settings_manager.py`: 55%
- `delta.py`: 88%
- `remove_command.py`: 76%

## Validation Commands

```bash
# Lint passes
./scripts/lint.sh

# All tests pass (643 tests)
poetry run pytest quickscale_core/tests/ quickscale_cli/tests/ --tb=short -q

# Coverage report
poetry run pytest --cov=quickscale_core --cov=quickscale_cli --cov-report=html
```

## Usage Examples

### Check Module Manifest

```bash
# View auth module manifest
cat quickscale_modules/auth/module.yml
```

### Change Mutable Config

```bash
# Edit quickscale.yml
vi quickscale.yml  # Change registration_enabled: false

# Preview changes
quickscale plan

# Apply changes
quickscale apply
```

### Remove Module

```bash
# Remove auth module
quickscale remove auth

# Force remove (skip confirmation)
quickscale remove auth --force
```

## Breaking Changes

None. Backward compatible with existing plan/apply workflow.

## Auth Module Manifest

The auth module now includes a manifest defining its configuration options:

**Mutable Options** (can change after embed):
- `registration_enabled` (bool, default: true) — Enable/disable registration
- `email_verification` (string, default: optional) — none/optional/mandatory

**Immutable Options** (locked at embed time):
- `social_providers` (list, default: []) — OAuth providers

## Architecture Decisions

See [decisions.md: Module Manifest Architecture](../technical/decisions.md#module-manifest-architecture) for:
- Manifest schema design rationale
- Mutable vs immutable categorization criteria
- Settings.py update strategy
- Migration path for existing modules

## Known Limitations

1. Settings updates use regex-based parsing (may not handle all edge cases)
2. Remove command doesn't automatically update `settings.py` or `urls.py`
3. No automatic database migration rollback on module removal

## Completion Milestone

This release completes the Plan/Apply System track (v0.68.0-v0.71.0):

| Version | Feature | Status |
|---------|---------|--------|
| v0.68.0 | Core commands (plan, apply) | ✅ Complete |
| v0.69.0 | State management | ✅ Complete |
| v0.70.0 | Existing project support | ✅ Complete |
| v0.71.0 | Module manifests & config mutability | ✅ Complete |

The QuickScale Plan/Apply system now provides Terraform-style declarative configuration for Django projects.

## Next Steps (v0.72.0)

- Real Estate theme (React + Django)
- First vertical theme implementation
- React + Vite frontend integration

## Contributors

- Victor (lead implementation)
- Claude (AI assistant)

## References

- [Roadmap v0.71.0](../technical/roadmap.md#v0710-planapply-system---module-manifests--config-mutability)
- [v0.70.0 Implementation](./release-v0.70.0-implementation.md)
- [Module Manifest Architecture](../technical/decisions.md#module-manifest-architecture)
