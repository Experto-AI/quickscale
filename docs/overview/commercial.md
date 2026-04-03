# QuickScale Commercial Use Notes

> **You are here**: [QuickScale](../../START_HERE.md) → [Overview](../index.md) → **Commercial Use**
> **Related docs**: [Decisions](../technical/decisions.md) | [Roadmap](../technical/roadmap.md) | [Start Here](../../START_HERE.md)

## Overview

QuickScale is released under Apache 2.0, which means developers and agencies can use it in commercial work, keep project-specific code private, and charge for services built on top of the generated projects.

This document is intentionally narrow. It explains what commercial use looks like today without inventing a separate commercial-distribution or package-subscription story that the repository does not currently ship.

## What Commercial Use Means Today

Today, commercial use of QuickScale usually looks like one or more of these patterns:

- Build paid client projects from the generator and deliver the resulting codebase as a normal Django application.
- Maintain private customizations or client-specific modules in separate repositories or directly inside the generated project.
- Sell services around setup, customization, deployment, maintenance, and module adoption.
- Reuse private internal patterns across owner-led or agency-managed projects while keeping QuickScale's released surfaces as the documented baseline.

## What Is Not Part of the Current Contract

QuickScale does **not** currently ship an official commercial distribution workflow or packaged-sales system.

That means the current repository does not provide:

- an official storefront or registry
- a private registry workflow
- built-in license validation for paid extensions
- an official subscription packaging system for modules or themes

If any of those capabilities become real later, they should only be treated as supported once [decisions.md](../technical/decisions.md), [roadmap.md](../technical/roadmap.md), and a tagged release note all say so explicitly.

## Practical Guidance for Commercial Teams

If you are using QuickScale commercially today:

- Treat the generated project as the primary delivered product.
- Keep the boundary clear between QuickScale-managed wiring and your private business logic.
- Document any private extension workflow in your own repository instead of assuming QuickScale provides it.
- Use the root docs and release notes as the source of truth for what QuickScale itself supports.

## Risk and Scope Notes

Commercial use is allowed, but the support surface is still the shipped QuickScale implementation. Teams should avoid presenting speculative package-distribution or storefront ideas as if they were current product features.

That matters especially when:

- onboarding clients
- planning upgrade paths
- promising reusable private extensions
- drawing boundaries between QuickScale updates and custom application code

## See Also

- [README.md](../../README.md) for the current project overview
- [decisions.md](../technical/decisions.md) for the authoritative implementation surface
- [roadmap.md](../technical/roadmap.md) for current milestone planning
