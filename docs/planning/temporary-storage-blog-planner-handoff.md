# Temporary Implementation Handoff: Storage, Blog Media URLs, and Planner UX

> Temporary handoff document for roadmap items under [docs/technical/roadmap.md](../technical/roadmap.md#v0760-quickscale_modulesstorage---media-storage--cdn-integration-module) and [docs/technical/roadmap.md](../technical/roadmap.md#v0840-advanced-module-management-features).
> Delete this file after the planned work is implemented, tested, and folded into permanent documentation.

## Purpose

This document turns the roadmap checklist into a low-ambiguity implementation handoff for:

- v0.76.0 storage/blog media URL unification
- v0.76.0 storage-specific planner configuration
- v0.76.0 `quickscale plan --reconfigure` option-preservation safety
- v0.76.0 minimum viable remote thumbnail generation
- v0.84.0 broader all-modules planner generalization

It is intentionally implementation-oriented and temporary.

## Scope Summary

### In scope for v0.76.0

1. Make `public_base_url` the only public URL source of truth for blog/storage public media URLs.
2. Deprecate `custom_domain` for public media delivery so it does not affect final public URLs.
3. Remove direct public rendering dependence on storage-native `.url` where storage helpers are available.
4. Add storage-specific interactive configuration to `quickscale plan` behind a planner flag.
5. Fix `quickscale plan --reconfigure` so module options are preserved instead of reset.
6. Add a minimum viable remote thumbnail generation path.

### Explicitly out of scope for v0.76.0

- Removing `custom_domain` from historical configs immediately
- Private media authorization
- Async/background image processing
- Full image pipeline/DAM features
- Generalized planner interactivity for every module

### In scope later for v0.84.0

1. Generalize planner-side per-module interactive configuration across supported modules.
2. Add dependency-aware multi-module planner sequencing.
3. Expand `plan --reconfigure` into a safe merge-preserving flow for all supported modules.

## Current-State Observations

### Blog/storage URL behavior

- Upload API responses already use helper-driven URL resolution in [quickscale_modules/blog/src/quickscale_modules_blog/views.py](../../quickscale_modules/blog/src/quickscale_modules_blog/views.py#L49-L99).
- Blog templates still use direct `.url` in places such as [quickscale_modules/blog/src/quickscale_modules_blog/templates/quickscale_modules_blog/blog/post_detail.html](../../quickscale_modules/blog/src/quickscale_modules_blog/templates/quickscale_modules_blog/blog/post_detail.html#L7-L12).
- Thumbnail URL logic falls back to storage-native URLs in [quickscale_modules/blog/src/quickscale_modules_blog/models.py](../../quickscale_modules/blog/src/quickscale_modules_blog/models.py#L263-L283).
- `build_public_media_url()` already supports path-capable `public_base_url` and local `MEDIA_URL` fallback in [quickscale_modules/storage/src/quickscale_modules_storage/helpers.py](../../quickscale_modules/storage/src/quickscale_modules_storage/helpers.py#L160-L197).

### Planner/config behavior

- `quickscale plan` currently writes module entries with empty options in [quickscale_cli/src/quickscale_cli/commands/plan_command.py](../../quickscale_cli/src/quickscale_cli/commands/plan_command.py#L845-L859).
- `quickscale plan --reconfigure` also rebuilds modules with empty options in [quickscale_cli/src/quickscale_cli/commands/plan_command.py](../../quickscale_cli/src/quickscale_cli/commands/plan_command.py#L565-L590).
- Storage already has an interactive configurator in [quickscale_cli/src/quickscale_cli/commands/module_config.py](../../quickscale_cli/src/quickscale_cli/commands/module_config.py#L1060-L1149), but planner does not call it.

### Thumbnail behavior

- Current thumbnail generation requires local filesystem `.path` and skips remote storage in [quickscale_modules/blog/src/quickscale_modules_blog/models.py](../../quickscale_modules/blog/src/quickscale_modules_blog/models.py#L212-L241).
- Existing regression coverage only confirms the skip behavior in [quickscale_modules/blog/tests/test_models.py](../../quickscale_modules/blog/tests/test_models.py#L280-L316).

## Target Behavior Contract for v0.76.0

### Public media URL contract

For any public blog/storage media URL:

1. If `public_base_url` is configured, final public URLs must be built from it.
2. Otherwise, final public URLs must use local `MEDIA_URL` behavior.
3. `custom_domain` must not change final public URLs once this work lands.
4. Stored DB/media references remain relative keys/paths, not absolute provider URLs.
5. Host swapping and path-prefix swapping must both work through `public_base_url` alone.

### Examples

#### Local development

- `public_base_url = ""`
- `MEDIA_URL = "/media/"`
- stored key: `blog/uploads/2026/03/hero-image.png`
- final URL: `/media/blog/uploads/2026/03/hero-image.png`

#### CDN host only

- `public_base_url = "https://cdn.example.com"`
- stored key: `blog/uploads/2026/03/hero-image.png`
- final URL: `https://cdn.example.com/blog/uploads/2026/03/hero-image.png`

#### CDN host + base path

- `public_base_url = "https://cdn.example.com/media"`
- stored key: `blog/uploads/2026/03/hero-image.png`
- final URL: `https://cdn.example.com/media/blog/uploads/2026/03/hero-image.png`

### `custom_domain` deprecation contract

For v0.76.0 implementation:

- `custom_domain` remains readable for backward compatibility in config/wiring.
- New public URL generation must ignore `custom_domain` and rely on `public_base_url`.
- Docs must describe `custom_domain` as deprecated/legacy for public media delivery.
- Existing projects that still set only `custom_domain` should default to: warning + derived fallback into `public_base_url` during apply/planning.
- Warning-only legacy preservation should be treated as a contingency path only if automatic derivation would break an existing project-specific setup.

Preferred implementation direction: preserve backward compatibility with a warning-backed migration path, but move all new/public code paths to `public_base_url`.

### Blog rendering contract

After implementation:

- public templates must not call direct storage-native `.url` for featured images when a helper-backed public URL is available
- blog helper/model methods should expose canonical public URLs for:
  - featured image
  - thumbnails
  - uploaded media references returned by APIs
  - blog-owned avatar/author image fields that are intended for public rendering
- upload/publish flows must produce the same URL family as frontend rendering

### Planner contract for v0.76.0

### New interactive planner behavior

Recommended flag: `quickscale plan --configure-modules`

Behavior:

- default planner behavior remains lightweight and backward-compatible
- when `--configure-modules` is provided, planner invokes module-specific configurators for selected modules that support it
- for v0.76.0, only `storage` must be wired into this planner flow
- planner writes collected module options directly into `quickscale.yml`

### `plan --reconfigure` preservation contract

When reconfiguring:

- existing module option dictionaries must be loaded and preserved
- untouched module options must round-trip unchanged
- only the module(s) being reconfigured may change
- adding a new module must not clear existing module options
- removing a module removes only that module's config block

### Remote thumbnail MVP contract

Minimum viable implementation for v0.76.0:

- synchronous generation is acceptable
- remote-storage thumbnail generation must not rely on `.path`
- original image is read from storage via file object APIs
- generated thumbnail bytes are written back through the active storage backend
- thumbnail naming must remain deterministic and compatible with existing thumbnail URL lookup behavior, or existing lookup behavior must be updated accordingly
- if thumbnail generation fails, original image URL remains the safe fallback

### MVP limits

- no async queueing
- no WebP/next-gen variant requirement
- no provider-specific image transformations
- no private/signed thumbnail flows

## Likely Files and Surfaces to Change

### Storage module

- [quickscale_modules/storage/src/quickscale_modules_storage/helpers.py](../../quickscale_modules/storage/src/quickscale_modules_storage/helpers.py)
- [quickscale_modules/storage/module.yml](../../quickscale_modules/storage/module.yml)
- [quickscale_modules/storage/README.md](../../quickscale_modules/storage/README.md)
- [quickscale_modules/storage/tests/test_helpers.py](../../quickscale_modules/storage/tests/test_helpers.py)

### Blog module

- [quickscale_modules/blog/src/quickscale_modules_blog/views.py](../../quickscale_modules/blog/src/quickscale_modules_blog/views.py)
- [quickscale_modules/blog/src/quickscale_modules_blog/models.py](../../quickscale_modules/blog/src/quickscale_modules_blog/models.py)
- [quickscale_modules/blog/src/quickscale_modules_blog/templates/quickscale_modules_blog/blog/post_detail.html](../../quickscale_modules/blog/src/quickscale_modules_blog/templates/quickscale_modules_blog/blog/post_detail.html)
- [quickscale_modules/blog/src/quickscale_modules_blog/templates/quickscale_modules_blog/blog/post_list.html](../../quickscale_modules/blog/src/quickscale_modules_blog/templates/quickscale_modules_blog/blog/post_list.html)
- [quickscale_modules/blog/README.md](../../quickscale_modules/blog/README.md)
- [quickscale_modules/blog/tests/test_api.py](../../quickscale_modules/blog/tests/test_api.py)
- [quickscale_modules/blog/tests/test_models.py](../../quickscale_modules/blog/tests/test_models.py)
- [quickscale_modules/blog/tests/test_views.py](../../quickscale_modules/blog/tests/test_views.py)

### CLI planner/apply

- [quickscale_cli/src/quickscale_cli/commands/plan_command.py](../../quickscale_cli/src/quickscale_cli/commands/plan_command.py)
- [quickscale_cli/src/quickscale_cli/commands/module_config.py](../../quickscale_cli/src/quickscale_cli/commands/module_config.py)
- [quickscale_cli/src/quickscale_cli/commands/module_wiring_specs.py](../../quickscale_cli/src/quickscale_cli/commands/module_wiring_specs.py)
- [quickscale_cli/src/quickscale_cli/commands/apply_command.py](../../quickscale_cli/src/quickscale_cli/commands/apply_command.py)
- [quickscale_cli/tests/test_plan_add.py](../../quickscale_cli/tests/test_plan_add.py)
- [quickscale_cli/tests/commands/test_module_config_extended.py](../../quickscale_cli/tests/commands/test_module_config_extended.py)

### Docs to align after implementation

- [docs/technical/roadmap.md](../technical/roadmap.md)
- [docs/technical/decisions.md](../technical/decisions.md)
- [docs/deployment/railway.md](../deployment/railway.md)

## Recommended Implementation Order

1. **Unify public URL strategy in storage**
   - make `public_base_url` canonical
   - deprecate `custom_domain` for public media URLs
   - update helpers/tests first

2. **Remove direct `.url` dependence in blog public rendering**
   - add canonical blog-facing helper methods/properties
   - update templates/models/views/tests

3. **Add storage planner interactivity**
   - wire storage configurator into planner behind a flag
   - preserve current non-flag behavior

4. **Fix `plan --reconfigure` merge/preservation behavior**
   - preserve existing options
   - add round-trip tests

5. **Add remote thumbnail MVP**
   - implement remote read/write path
   - keep original-image fallback

6. **Align docs and warnings**
   - mark `custom_domain` deprecated in docs
   - document `public_base_url` migration path

## Acceptance Checklist for Implementation Handoff

Implementation is not complete until all items below are true.

### URL behavior

- [ ] Blog upload API, publish flow, templates, and model helpers produce URLs from the same public URL strategy.
- [ ] `public_base_url` supports host-only and host+path deployment shapes.
- [ ] Local development still works with empty `public_base_url`.
- [ ] Public rendering no longer depends on direct storage-native `.url` where helper-backed URLs are available.

### Backward compatibility

- [ ] Existing configs using `custom_domain` are handled with a documented deprecation path.
- [ ] Stored file keys remain unchanged.
- [ ] Switching CDN host or base path does not require DB rewrites.

### Planner safety

- [ ] `quickscale plan --configure-modules` supports storage-specific interactive config.
- [ ] `quickscale plan --reconfigure` preserves untouched module options.
- [ ] Adding/removing modules during reconfigure does not wipe unrelated module configuration.

### Thumbnail MVP

- [ ] Remote-storage thumbnails can be generated without filesystem `.path`.
- [ ] Generated thumbnail URLs resolve through the same public URL contract as originals.
- [ ] Thumbnail failures safely fall back to the original image.

## Test Matrix

### Storage/blog URL tests

- local fallback URL resolution
- `public_base_url` host-only resolution
- `public_base_url` host+path resolution
- blog template/model helper URLs use helper-backed output
- no public rendering regression to direct `.url`

### Planner tests

- planner with no `--configure-modules` preserves current behavior
- planner with `--configure-modules` writes storage config
- `plan --reconfigure` round-trips existing storage options unchanged
- adding a second module during reconfigure does not clear storage options

### Thumbnail tests

- local filesystem thumbnail generation still works
- remote-storage thumbnail generation works without `.path`
- thumbnail URL uses `public_base_url`
- generation failure returns original image URL

## Migration Notes

### Existing projects using `custom_domain`

Preferred migration path:

1. Keep stored keys unchanged.
2. Move public media delivery config to `public_base_url`.
3. Mark `custom_domain` deprecated in docs and planner output.
4. Avoid automatic DB/media rewrites.

### Existing projects using local media

- no config changes required
- local `MEDIA_URL` fallback remains valid

## Deferred Follow-Up for v0.84.0 Cross-Module Planner Work

Broader planner work belongs to [docs/technical/roadmap.md](../technical/roadmap.md#v0840-advanced-module-management-features), not v0.76.0.

### v0.84.0 handoff scope

- generalize interactive per-module planner configuration across supported modules
- add dependency-aware planner sequencing
- strengthen merge-preserving `plan --reconfigure` semantics for multi-module workflows
- add regression coverage for mixed module stacks

### Why deferred

- storage needs a focused planner fix first
- cross-module planner UX is broader platform work
- v0.84.0 is the correct release for that generalization

## Exit Criteria for Deleting This File

Delete this file once all of the following are true:

1. The v0.76.0 and relevant v0.84.0 work is implemented.
2. Permanent docs are updated.
3. Tests cover the documented contracts.
4. Roadmap checklist items are updated to reflect completion.
5. No unresolved behavior decisions remain in this handoff.
