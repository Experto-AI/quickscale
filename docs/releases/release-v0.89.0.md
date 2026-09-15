# QuickScale v0.89.0 — Version-Derived Test Expectations

> **Release status:** prepared for the v0.89.0 development line, not published. No v0.89.0 tag,
> GitHub release, or package upload is implied by this note.

## Summary

Current-version tests now read the expected value from QuickScale package metadata rather than
copying a release string into each fixture and assertion. A repository version bump therefore
updates their expectation without a matching test-only patch.

## Compatibility

This maintenance change affects repository tests only. It does not change generated projects,
runtime behavior, package APIs, or upgrade requirements.
