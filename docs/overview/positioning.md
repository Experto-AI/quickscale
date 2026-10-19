# QuickScale Positioning

> **Related docs**: [README](../../README.md) | [Decisions](../technical/decisions.md) | [Glossary](../../GLOSSARY.md)

## What QuickScale is

A Django project generator plus a first-party module stack for teams that build more than one
owner-led or client SaaS project. It sits between one-time boilerplates (fast first project, no
structured reuse) and large SaaS kits (more features up front, each copy independent).

- **Generator**: `quickscale plan` + `quickscale apply` produce a standalone Django project the
  team owns completely.
- **Modules**: reusable backend/runtime units (auth, billing, orgs, crm, forms, …) embedded and
  updated through a documented workflow.
- **Theme**: `showcase_react` is scaffolded once and becomes user-owned code.
- **Assembly at creation time**, never runtime plugin loading: app registration, settings and
  migrations stay explicit Django.

The shipped surface is defined by
[implementation_contract.md](../technical/implementation_contract.md#mvp-feature-matrix-authoritative),
not by this page.

## Fit

| Fits | Does not fit |
|---|---|
| Solo developers and agencies shipping repeated Django projects | A hosted service or "complete SaaS in a box" |
| Teams wanting production defaults without giving up code ownership | Teams wanting the broadest turnkey frontend on day one |
| Maintainers who value explicit contracts and standard Django patterns | Runtime plugin loading or dynamically installed apps |

## Comparison

| Option | Model | Best fit | Tradeoff vs QuickScale |
|---|---|---|---|
| **QuickScale** | Generator + first-party module stack | Repeated owner-led or client Django projects, incl. billing and multi-tenant SaaS | Smaller ecosystem and third-party extension surface |
| **SaaS Pegasus** | Feature-rich SaaS boilerplate | Founders wanting broad SaaS features immediately | Static per-project copy, paid license |
| **Django Cookiecutter** | General Django starter | Developers assembling SaaS features themselves | Little SaaS-specific guidance |
| **Apptension SaaS Boilerplate** | React-heavy open-source boilerplate | Teams comfortable with a heavier frontend stack | No shared module reuse focus |
| **Ready SaaS** | Paid starter kit | A packaged start at moderate cost | Less architectural reuse |

## Known limits

- Some billing SPA entry points are a module flag only and not wired into the generated theme.
- Frontend additions reach existing projects by manual adoption, because QuickScale never
  rewrites user-owned theme files.
- `teams` is not a shipped module and has no committed timeline.

## Commercial use

QuickScale is Apache 2.0: commercial client work, private customizations and paid services on top
of generated projects are allowed. QuickScale ships no storefront, private registry, license
validation or paid-module packaging; none is supported until decisions.md and a release note say so.
