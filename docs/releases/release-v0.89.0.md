# QuickScale v0.89.0 — Development Maintenance

> **Release status:** prepared for the v0.89.0 development line, not published. No v0.89.0 tag,
> GitHub release, or package upload is implied by this note.

## Summary

Validation expectations now derive from their authoritative repository sources. Gate-parity tests
compute their counts from the gate registry and workflow declarations, while current-version tests
read the expected value from QuickScale package metadata. Adding a gate or bumping the repository
version therefore no longer requires a matching expectation-only patch.

Project-owned tenant models can now join classification and FORCE RLS policy refresh through the
marker-derived tenant contract. This keeps organization ownership and forced row-level security
requirements in place without requiring edits under embedded module source.

## Adoption

A project-owned model declares the tenant-manager contract and installs its own FORCE RLS policy in
its migration. A project-owned `AbstractListing` subclass declares both the tenant-scoped and
super-scope managers before running the project's isolation checks.

## Compatibility

The validation-source changes affect repository tests only. The tenant-enrollment capability keeps
existing organization ownership and FORCE RLS requirements in place without changing package APIs
or upgrade requirements.

## Validation

The task-tier validation command for this prepared capability is:

```text
make test-integration MODULE=orgs && make test-unit -- --core && poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov
```

This note does not claim release-tier validation, publication, or a v0.89.0 tag.

## Deferred scope

Purge membership and account-deletion behavior remain deferred and unchanged by this capability.
