# SCAFFOLDING: Repository, Packages, and Generated Project Structures

> **You are here**: [QuickScale](../../START_HERE.md) -> [Technical](../index.md) -> **Scaffolding** (Structure Hub)
> **Related docs**: [Decisions](decisions.md) | [Implementation Contract](implementation_contract.md) | [Generated Project Structure](generated_project_structure.md) | [Repository Layout](repository_layout.md) | [Validation Policy](validation_policy.md)

Top-level hub for QuickScale structure references. Detailed structure ownership now lives in narrow companion docs so role hydration can pull only the slices it needs while this file keeps the legacy entry points and compatibility anchors stable.

## 1. Scope & Principles

This hub covers:
- where structure material now lives
- which companion doc owns which structure slice
- compatibility anchors that older links still target

Guiding principles:
- generated projects are standalone and user-owned
- themes are one-time scaffolding, while modules are long-lived runtime dependencies
- repository layout and generated-project layout are separate concerns with separate owners
- [decisions.md](./decisions.md) still wins for rules, prohibitions, and tie-breakers

## 2. How to Use This Document

Read [generated_project_structure.md](./generated_project_structure.md) when you need:
- current generated-project file trees
- generated artifact ownership and placement
- generated-project guardrails and simplifications
- starter-theme output details

Read [repository_layout.md](./repository_layout.md) when you need:
- current maintainer-repository layout
- package-placement examples
- naming and import matrix guidance

Read [validation_policy.md](./validation_policy.md#e2e-test-infrastructure) when you need:
- E2E infrastructure structure and validation expectations

Read [decisions.md](./decisions.md) instead when you need:
- scope rulings or tie-breakers
- prohibitions and technical policies
- the authoritative implementation surface matrix

<a id="mvp-structure"></a>
## 3. Current Generated Structure

The authoritative generated-project reference now lives in [generated_project_structure.md](./generated_project_structure.md#mvp-structure).

Use that companion for:
- base generated Django layout
- embedded module placement under `modules/`
- generated-project simplifications and guardrails

<a id="post-mvp-structure"></a>
## 4. Maintainer and Package Layout Reference

The authoritative maintainer-side repository and package-layout reference now lives in [repository_layout.md](./repository_layout.md#post-mvp-structure).

Use that companion for:
- current monorepo layout
- optional extraction and personal-monorepo patterns
- maintainer-side placement notes that are not part of generated-project output

<a id="generated-project-output"></a>
<a id="5-generated-project-output"></a>
## 5. Generated Project Output

The detailed generated output reference now lives in [generated_project_structure.md](./generated_project_structure.md#generated-project-output).

That companion owns:
- React starter output
- HTML starter output
- `.quickscale/` state and module metadata placement
- optional manual inheritance and extraction notes

<a id="6-naming-import-matrix-summary"></a>
<a id="naming-import-matrix-summary"></a>
## 6. Naming & Import Matrix (Summary)

The authoritative naming and import matrix now lives in [repository_layout.md](./repository_layout.md#6-naming-import-matrix-summary).

## 7. Structure Ownership Map

| Need | Authoritative doc |
|---|---|
| Generated project trees and guardrails | [generated_project_structure.md](./generated_project_structure.md) |
| Maintainer repository layout | [repository_layout.md](./repository_layout.md) |
| Feature-level current contract | [implementation_contract.md](./implementation_contract.md) |
| Validation commands and E2E structure | [validation_policy.md](./validation_policy.md) |
| Cross-cutting rules and tie-breakers | [decisions.md](./decisions.md) |

## 10. Authoring & Maintenance Notes

- Update [generated_project_structure.md](./generated_project_structure.md) when generated output or generated-project guardrails change.
- Update [repository_layout.md](./repository_layout.md) when maintainer-repository layout or naming guidance changes.
- Update [validation_policy.md](./validation_policy.md#e2e-test-infrastructure) when E2E infrastructure structure changes.
- Preserve legacy anchors in this hub when moving structural detail into narrower owners.

<a id="13-e2e-test-infrastructure"></a>
<a id="e2e-test-infrastructure"></a>
## 13. E2E Test Infrastructure

The authoritative E2E infrastructure reference now lives in [validation_policy.md](./validation_policy.md#e2e-test-infrastructure). Keep this compatibility section in place for older links.
