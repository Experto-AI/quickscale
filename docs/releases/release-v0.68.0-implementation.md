# Release v0.68.0: Plan/Apply System — Core Commands

**Release Date:** 2025-12-01
**Status:** ✅ Complete

## Summary

This release introduces the Terraform-style `quickscale plan` and `quickscale apply` commands, providing a declarative workflow for project generation. Users can now create configuration files interactively and execute them to generate fully-configured Django projects.

## Key Features

### Plan Command (`quickscale plan`)

Interactive wizard for creating `quickscale.yml` configuration files:

```bash
quickscale plan myapp
```

Features:
- Theme selection (showcase_html, showcase_htmx, showcase_react)
- Module selection (blog, listings, billing, teams)
- Docker configuration (build and start options)
- YAML preview before saving
- Custom output path with `--output` flag

### Apply Command (`quickscale apply`)

Execute configuration to generate projects:

```bash
quickscale apply quickscale.yml
```

Features:
- Schema validation with line-number errors
- Correct execution order (generate → git → modules → poetry → migrate → docker)
- Progress feedback with emoji indicators
- Skip options (`--no-docker`, `--no-modules`)
- Force overwrite with `--force`

### YAML Schema

Declarative configuration format:

```yaml
version: 0.71.0
project:
  name: myapp
  theme: showcase_html
modules:
  - name: blog
  - name: listings
docker:
  build: true
  start: true
```

Validation features:
- Line-number error reporting
- Typo suggestions (e.g., "did you mean 'modules'?")
- Required/optional key validation

## Breaking Changes

None. The `init` and `embed` commands remain functional with deprecation warnings.

## Deprecations

- `quickscale init` - Deprecated, use `quickscale plan` + `quickscale apply`
- `quickscale embed` - Deprecated, module embedding now included in `apply`

Full removal scheduled for v0.71.0 after plan/apply system proven stable.

## Files Changed

### New Files

| File | Purpose |
|------|---------|
| `quickscale_cli/src/quickscale_cli/schema/__init__.py` | Schema module exports |
| `quickscale_cli/src/quickscale_cli/schema/config_schema.py` | YAML validation with dataclasses |
| `quickscale_cli/src/quickscale_cli/commands/plan_command.py` | Interactive wizard command |
| `quickscale_cli/src/quickscale_cli/commands/apply_command.py` | Configuration execution command |
| `quickscale_cli/tests/test_schema.py` | Schema validation tests (36 tests, 93% coverage) |
| `quickscale_cli/tests/test_plan_command.py` | Plan command tests (17 tests, 81% coverage) |
| `quickscale_cli/tests/test_apply_command.py` | Apply command tests (18 tests, 60% coverage) |

### Modified Files

| File | Changes |
|------|---------|
| `quickscale_cli/src/quickscale_cli/main.py` | Register plan/apply commands, add deprecation warning to init |
| `quickscale_cli/src/quickscale_cli/commands/module_commands.py` | Add deprecation warning to embed |
| `README.md` | Update Quick Start with plan/apply workflow |
| `docs/technical/user_manual.md` | Add section 4.3 documenting plan/apply commands |
| `docs/technical/roadmap.md` | Mark v0.68.0 tasks complete |

## Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_schema.py` | 36 | 93% |
| `test_plan_command.py` | 17 | 81% |
| `test_apply_command.py` | 18 | 60% |
| **Total** | **71** | **70%+** |

## Migration Guide

### From `quickscale init`

Before (v0.67.0):
```bash
quickscale init myapp --theme showcase_html
cd myapp
quickscale embed --module blog
```

After (v0.68.0):
```bash
quickscale plan myapp   # Interactive wizard
cd myapp
quickscale apply        # Execute configuration
```

### Benefits of Migration

1. **Declarative**: Configuration is version-controllable
2. **Reproducible**: Same config produces same project
3. **Integrated**: Module embedding included in single command
4. **Reviewable**: Preview configuration before execution

## Known Limitations

1. E2E tests for plan/apply deferred to v0.69.0
2. State management (incremental apply) not yet implemented
3. Existing project support (`--add`, `--edit`) not yet implemented

## Next Steps (v0.69.0)

- State file tracking (`.quickscale/state.yml`)
- Delta detection for incremental applies
- Filesystem verification

## Contributors

- Victor (lead implementation)

## References

- [Plan/Apply System Specification](../technical/plan-apply-system.md)
- [User Manual §4.3](../technical/user_manual.md#43-planapply-commands-shipped-in-v0680)
- [Roadmap v0.68.0](../technical/roadmap.md#v0680-planapply-system--core-commands)
