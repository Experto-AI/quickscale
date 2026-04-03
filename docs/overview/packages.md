# QuickScale Package and Naming Notes

> **You are here**: [QuickScale](../../START_HERE.md) → [Overview](../index.md) → **Packages**
> **Related docs**: [Decisions](../technical/decisions.md) | [Scaffolding](../technical/scaffolding.md) | [Start Here](../../START_HERE.md)

## Overview

This document is a current naming and package-context reference. It is **not** a publication roadmap, package-reservation checklist, or release-order plan.

Use it to understand how QuickScale names the repository packages and first-party module surfaces that already exist in the workspace today.

## Current Repository Packages

| Surface | Current role | Notes |
|---------|--------------|-------|
| `quickscale` | meta-package context | packaging notes only; root docs remain authoritative |
| `quickscale_cli` | CLI package | owns the `quickscale` command workflow |
| `quickscale_core` | generator and shared scaffolding support | owns templates and generation logic |
| `quickscale_modules/*` | first-party module workspace | one directory per first-party module |

## Current Naming Conventions

QuickScale uses a few consistent naming patterns today:

- Repository directories use the visible package names: `quickscale`, `quickscale_cli`, `quickscale_core`, and `quickscale_modules/<name>`.
- Module Python package names use the underscore form inside each module package, for example `quickscale_modules_auth` or `quickscale_modules_social`.
- Django app labels use the same underscore-qualified pattern, for example `quickscale_modules_auth`.

Examples:

| Concern | Example |
|---------|---------|
| Repository directory | `quickscale_modules/social/` |
| Python package | `quickscale_modules_social` |
| Django app label | `quickscale_modules_social` |

## What Not to Infer from This File

This file does **not** imply:

- a reserved PyPI namespace strategy
- a future public package storefront or registry
- a specific publication order for unreleased modules or themes
- an official promise that every repository directory will become an independently distributed package

If a new distribution model ever becomes part of the supported contract, it should be documented in [decisions.md](../technical/decisions.md), [roadmap.md](../technical/roadmap.md), and the relevant tagged release note.

## When to Update This File

Update this document when:

- a new first-party package directory is added to the repository
- module naming conventions change
- Python package names or Django app labels change in an implemented release

Do not update this file just to sketch hypothetical publication plans.
