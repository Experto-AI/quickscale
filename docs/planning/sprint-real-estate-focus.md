# Sprint Plan: Real Estate Agency Focus (Historical Planning Snapshot)

> **Status:** Historical scenario-planning artifact kept for context.
> **Current rule:** This file is not the source of truth for release order, release status, or current implementation scope.
> Use [roadmap.md](../technical/roadmap.md) for active milestones, [CHANGELOG.md](../../CHANGELOG.md) for release history, and [release-v0.79.0.md](../releases/release-v0.79.0.md) for the official public social-module release summary.

## Why This File Still Exists

This document preserves a useful planning lens from a real-estate-focused product discussion:

- public-facing agency needs tended to outrank internal tooling early on
- listings, social, and CRM work were considered as a connected vertical story
- staged rollout thinking mattered for projects that needed to launch in increments instead of waiting for a full feature set

Those insights are still useful. The old version assignments and sequence assumptions are not.

## Superseded Assumptions

| Earlier planning assumption | Current reality |
|-----------------------------|----------------|
| Listings and social would land in the earlier v0.75-v0.76 range | Social shipped later as [v0.79.0](../releases/release-v0.79.0.md), and other vertical milestones remain on the active roadmap |
| This document could double as release guidance | The authoritative release story now lives in the roadmap, changelog, and tagged release notes |
| The sprint tables reflected current roadmap truth | They now reflect an older planning snapshot only |

## Still-Useful Planning Insights

- Real-estate projects often benefit from shipping public pages before internal CRM or billing workflows.
- Listings and social surfaces naturally reinforce each other for agency-style marketing sites.
- A staged adoption model remains useful even when the specific version numbers change.

## Current Authoritative Sources

- [roadmap.md](../technical/roadmap.md)
- [decisions.md](../technical/decisions.md)
- [CHANGELOG.md](../../CHANGELOG.md)
- [release-v0.79.0.md](../releases/release-v0.79.0.md)

## Historical Note

If you need the original detailed task breakdown for archaeological context, recover it from repository history rather than treating an old planning draft as live product documentation.
