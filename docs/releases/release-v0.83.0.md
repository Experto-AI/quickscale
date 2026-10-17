# Release v0.83.0 - Hardening Release

**Date:** 2026-05-03 · **Status:** ✅ Released

## Summary

This release closes the pre-billing hardening track across QuickScale's generator, CLI, and shipped module line. v0.83.0 focuses on correctness and operational safety rather than a new public module: desired-config validation now fails earlier and more precisely, generated production defaults reject unsafe placeholders, privileged CRM and backup surfaces are tighter, and export or automation paths in forms and blog now defend against common operator and content hazards.

The release also closes the release-validation loop through the maintained `make` entrypoints. The published v0.83.0 artifact is backed by repo-wide static checks, full test coverage, Docker-backed E2E coverage, and the integrated `ci-e2e` pass, which means the maintained contributor workflow now matches the published release state instead of a pre-release handoff.

## Highlights

### Features

- **Fail-hard desired-config boundaries**: Existing-project add and reconfigure flows now reject config-only legacy auth shapes and invalid live notifications placeholder config before rewriting `quickscale.yml`, which keeps planner and apply behavior aligned with the shipped manifest contract.
- **Runtime and operator-surface hardening**: Generated production settings now require a real `SECRET_KEY`, the CRM HTML dashboard and related shipped surfaces stay staff-only, forms CSV exports neutralize formula-prefixed content, backup downloads stay inside authoritative backup roots, and blog uploads plus thumbnail handling fail closed on unsafe image conditions.
- **Completed release-closeout validation**: The repository's maintained validation path now includes successful Docker-backed `make test-e2e` and `make ci-e2e` runs alongside the standard version, lint, type, and test gates used during the release cut.

### Improvements

- **Starter and contract fidelity cleanup**: The v0.83.0 hardening line leaves shipped starter output, module-facing docs, and runtime behavior aligned on the current supported contract before billing and teams work begins.
- **Safer blog automation defaults**: Blog API throttling now uses the request `REMOTE_ADDR` by default, upload dimensions are enforced at the API boundary, and decompression-bomb handling stays fail-closed without widening public behavior.
- **Clearer maintainer validation path**: A host with Docker access, Compose support, and Playwright available can now rerun the same maintained `make` targets used for release closeout without extra one-off scripts.

## Breaking changes

- Existing-project planner add and reconfigure flows now fail hard on config-only legacy auth desired config instead of rewriting it.
- Live notifications config targeting Resend now rejects the shipped `noreply@example.com` placeholder instead of tolerating it through planner or apply boundaries.
- Generated production settings now fail hard when `SECRET_KEY` is blank or still using the shipped placeholder, and the CRM HTML dashboard is now staff-only.

## Upgrade steps

1. Update any existing-project `quickscale.yml` files that still use legacy config-only auth shapes before running add or reconfigure flows, and replace placeholder live notifications sender addresses before targeting Resend delivery.
2. Set a real production `SECRET_KEY`, confirm staff access for CRM operators, and review any internal operator flows that assumed broad backup artifact path access or unsanitized CSV export content.
3. Re-run the maintained validation path with `make version-check`, `make lint`, `make typecheck`, `make test`, `make test-e2e`, and `make ci-e2e` when preparing downstream upgrades or release-adjacent changes.
