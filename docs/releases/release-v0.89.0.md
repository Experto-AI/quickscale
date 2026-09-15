# QuickScale v0.89.0 — Development Maintenance

> **Release status:** prepared for the v0.89.0 development line, not published. No v0.89.0 tag,
> GitHub release, or package upload is implied by this note.

## Summary

Validation expectations now derive from their authoritative repository sources. Gate-parity tests
compute their counts from the gate registry and workflow declarations, while current-version tests
read the expected value from QuickScale package metadata. Adding a gate or bumping the repository
version therefore no longer requires a matching expectation-only patch.

## Compatibility

This maintenance change affects repository tests only. It does not change generated projects,
runtime behavior, package APIs, or upgrade requirements.
