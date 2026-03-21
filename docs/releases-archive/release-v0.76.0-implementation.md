# Release v0.76.0: `quickscale_modules.storage` - ✅ COMPLETE AND VALIDATED

**Release Date**: 2026-03-21

## Overview

Release `v0.76.0` completes QuickScale's storage-module milestone and closes the remaining roadmap work for production-ready media storage. The implementation establishes `public_base_url` as the single public-media URL contract, removes the deprecated `custom_domain` path from module configuration and planner state, and aligns blog uploads plus generated thumbnails with canonical helper-built URLs.

This release keeps storage as shared infrastructure rather than pushing provider-specific behavior into feature modules. `quickscale_modules.storage` owns backend selection, helper APIs, and deployment guidance; `quickscale_modules.blog` continues to own blog content, uploads, and thumbnail workflows while consuming storage helpers for public rendering.

The release also completes the required documentation cleanup. Permanent docs, deployment guidance, package-level guidance, roadmap tracking, and changelog language were updated so the shipped behavior is discoverable without relying on temporary planning notes.

## Verifiable Improvements Achieved ✅

- ✅ Storage configuration now uses `public_base_url` as the only supported public URL source for storage-backed media.
- ✅ `custom_domain` was removed from the storage module manifest, CLI planner/configuration flows, managed settings wiring, helper APIs, and regression tests.
- ✅ Blog upload responses now use canonical helper-built URLs derived from stored media keys instead of provider-native fallback URLs.
- ✅ Generated thumbnails and original media now share the same public URL contract for local and cloud-backed storage.
- ✅ Planner round-trips prune legacy `modules.storage.custom_domain` values during add/reconfigure flows.
- ✅ Permanent storage and deployment documentation now reflects the shipped `public_base_url`-only contract.
- ✅ Repository-wide validation passed with `make check` after implementation and review fixes.

## Files Created / Changed

### Release Documentation Added
- `docs/releases/release-v0.76.0.md`
- `docs/releases-archive/release-v0.76.0-implementation.md`
- `docs/releases-archive/release-v0.76.0-review.md`

### Storage Module
- `quickscale_modules/storage/module.yml` — removed `custom_domain` from the mutable storage contract
- `quickscale_modules/storage/src/quickscale_modules_storage/helpers.py` — simplified backend/public URL helpers to `public_base_url` + local fallback behavior only
- `quickscale_modules/storage/tests/test_helpers.py` — updated regressions for URL helpers, sanitization, invalid backends, and validation behavior
- `quickscale_modules/storage/README.md` — rewrote storage guidance around the shipped contract and migration path

### Blog Module
- `quickscale_modules/blog/src/quickscale_modules_blog/views.py` — unified upload responses around stored-key-based public URL generation
- `quickscale_modules/blog/tests/test_api.py` — updated regressions for canonical media URLs, local fallback behavior, and upload response handling

### CLI / Planner
- `quickscale_cli/src/quickscale_cli/commands/module_config.py` — removed `custom_domain` defaults, prompts, and summaries from interactive storage configuration
- `quickscale_cli/src/quickscale_cli/commands/module_wiring_specs.py` — removed `AWS_S3_CUSTOM_DOMAIN` and related normalization logic
- `quickscale_cli/src/quickscale_cli/commands/plan_command.py` — prunes legacy `storage.custom_domain` keys during planner round-trips
- `quickscale_cli/tests/commands/test_module_config_extended.py` — updated storage configuration expectations
- `quickscale_cli/tests/test_plan_add.py` — added planner regression coverage for pruning legacy storage keys
- `quickscale_cli/tests/test_plan_reconfigure.py` — added planner regression coverage for pruning legacy storage keys during reconfigure
- `quickscale_cli/tests/test_module_manifest_contract.py` — formatting cleanup required by quality gate

### Permanent Documentation
- `docs/technical/decisions.md` — documented `public_base_url` as the sole public media URL setting for storage-backed media
- `docs/deployment/railway.md` — aligned deployment guidance with the shipped env-var contract and CDN/media-storage behavior
- `docs/technical/roadmap.md` — marked release complete and later replaced the detailed checklist with archive links
- `docs/technical/release-archive.md` — indexed the archived release artifacts
- `CHANGELOG.md` — updated `v0.76.0` from roadmap-tracked to released/archive-backed status

## Test Results

### Targeted Validation
- **Storage helpers**: storage helper regressions passed after the helper contract cleanup
- **Blog API**: blog upload/public URL regressions passed after canonical URL unification
- **CLI planner**: planner add/reconfigure regressions passed after the legacy-key pruning fix

These targeted tests were used during implementation to validate the modified storage, blog, and planner surfaces before the full repository quality gate.

### Repository Quality Gate
- **Command**: `make check`
- **Outcome**: passed

The repository-wide quality gate was run after implementation and again after the planner regression fix that emerged during review. The final run passed with formatting, linting, typing, and test checks green.

## Validation Commands

```bash
# Repository quality gate
make check
```

## Tasks Completed

### ✅ Architecture & Boundaries
- Finalized the storage module as shared infrastructure for public media delivery
- Standardized the public media contract around `public_base_url`
- Removed the deprecated `custom_domain` compatibility path entirely
- Kept blog-owned content logic in `quickscale_modules.blog` while routing public URLs through shared helpers

### ✅ Core Storage Features
- Shipped storage backend abstraction for local, S3-compatible, and R2-compatible usage
- Preserved cache-friendly upload naming and public URL helper APIs
- Kept local-development fallback behavior intact when cloud storage is not configured

### ✅ Image & Media Processing
- Preserved the thumbnail-first MVP approach
- Ensured originals and generated thumbnails resolve through the same helper-backed URL contract
- Deferred broader media-pipeline expansion to a later release

### ✅ Blog / CLI Integration
- Unified blog upload responses around stored-key public URLs
- Removed storage `custom_domain` handling from CLI configuration and managed wiring
- Fixed planner round-trips so deprecated storage keys are not preserved in generated config state

### ✅ Documentation & Acceptance
- Updated permanent docs and deployment guidance to the shipped contract
- Added release artifacts so roadmap scope can be archived cleanly
- Confirmed the full repository quality gate passes after the release changes

## Scope Compliance

**In-scope (implemented)**:
- storage module contract cleanup
- canonical storage/blog public media URLs
- storage CLI/planner cleanup
- permanent documentation alignment
- roadmap completion and archival artifacts
- targeted regression coverage plus repository quality-gate validation

**Out-of-scope (deliberate)**:
- deeper storage upload/write/read integration coverage — deferred to `v0.85.0`
- Plan → Apply → Blog publish E2E coverage with CDN-backed media — deferred to `v0.85.0`
- broader React showcase guidance for storage-backed media flows — deferred to later vertical/theme work
- richer media variants or async/background processing — deferred beyond `v0.76.0`

## Dependencies

### Production Dependencies
- None added

### Development Dependencies
- None added

## Release Checklist

- [x] All roadmap tasks marked as implemented
- [x] All tests passing
- [x] Code quality checks passing
- [x] Documentation updated
- [x] Archived implementation notes committed to `docs/releases-archive/`
- [x] Reader-facing summary added to `docs/releases/`
- [x] Roadmap updated with completion status
- [x] Version numbers consistent across packages
- [x] Validation commands tested

## Notes and Known Issues

- The final review identified one medium issue after the first quality-gate pass: planner round-trips could preserve legacy `modules.storage.custom_domain` keys. That issue was fixed before final archival.
- Full generated-project workflow validation remains intentionally scheduled for `v0.85.0`, where the roadmap already tracks broader module workflow testing.
- The release does not introduce infrastructure provisioning or provider-specific premium features.

## Next Steps

1. `v0.77.0` — ship the social/link-tree module foundation
2. `v0.84.0` — continue broader cross-module planner UX improvements
3. `v0.85.0` — add deeper storage integration coverage and blog/storage E2E workflow validation

---

**Status**: ✅ COMPLETE AND VALIDATED
**Implementation Date**: 2026-03-21
**Implemented By**: GitHub Copilot
