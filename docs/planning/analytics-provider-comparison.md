# Analytics Provider Comparison: v0.80.0 Analytics Module

> **You are here**: [QuickScale](../../START_HERE.md) → [Docs](../index.md) → **Planning** → Analytics Provider Comparison
> **Related docs**: [Roadmap v0.80.0](../technical/roadmap.md#v0800-quickscale_modulesanalytics---analytics-module) | [Decisions](../technical/decisions.md) | [Competitive Analysis](../overview/competitive_analysis.md)

## Goal

Compare analytics provider options for QuickScale's planned analytics module (`quickscale_modules.analytics`, v0.80.0) and record the reviewed implementation contract for the first release.

## Context

v0.80.0 remains intentionally narrow: PostHog-only website analytics, anonymous-default posture, and a backend-first integration contract that avoids unsupported seams in existing generated projects.

This planning pass separates two concerns that were previously conflated:
- **Provider choice**: who collects and stores analytics data
- **Implementation contract**: how QuickScale exposes analytics safely through its current planner, generated settings, modules, and starter themes

The reviewed v0.80.0 contract removes earlier assumptions that no longer fit the current codebase shape:
- use flat `QUICKSCALE_ANALYTICS_*` settings instead of a single `QUICKSCALE_ANALYTICS` dict because current settings mutation is one-setting-at-a-time
- do not expand the analytics surface through a new context processor
- do not require a generated project-owned extension app for analytics v0.80.0
- do not promise apply-managed rewrites of existing React or HTML theme files
- limit automatic frontend support to dormant `showcase_react` starter support on fresh generation
- use a guarded direct optional import for the forms hook
- limit social click tracking to QuickScale-owned generated public pages/templates
- keep manual frontend adoption explicit for existing projects

## Executive Summary

Two valid provider paths emerged:

| Path | Best when | Main downside |
| --- | --- | --- |
| **PostHog-first (website analytics with free tier)** | QuickScale wants zero provider cost floor, first-class Django support, React SPA tracking, and a clean path to future expansion without changing providers | Larger surface area than a pure script-only analytics tool; scope discipline is required |
| **Plausible-first (cookieless, EU-oriented)** | QuickScale wants the smallest integration surface or an operator has a hard privacy-first / EU-only preference | Cloud pricing starts at €9/month with no free tier; weaker server-side capture story |

For v0.80.0, the practical choice is:

**Use PostHog as the only approved provider for v0.80.0. Keep the runtime contract narrow: flat mutable analytics settings, a service-style analytics module using the official `posthog` Python SDK, guarded forms integration, limited social click tracking on QuickScale-owned generated surfaces, and fresh-generation `showcase_react` starter support with manual adoption for existing projects.**

Plausible remains a documented future reconsideration path, not a second runtime seam in this milestone.

## Evaluation Criteria

| Criterion | Why it matters for QuickScale |
| --- | --- |
| Django fit | Generated projects are Django-first; official SDKs and predictable configuration matter immediately |
| React/SPA fit | Fresh `showcase_react` generations need route tracking without implying apply-managed rewrites of older user-owned apps |
| Privacy/GDPR posture | QuickScale targets EU-adjacent projects; anonymous-default behavior and explicit identity opt-in matter |
| Service-style backend fit | v0.80.0 should work as an integration-only module without inventing fake model/admin seams |
| Pricing at project scale | Generated projects must be able to go live with zero provider cost by default |
| Retrofit safety | Existing React and HTML theme files remain user-owned; the contract must not depend on patching them automatically |
| Scope discipline | v0.80.0 is website-analytics-first; it should not drag product-analytics complexity into the initial release |

## Provider Comparison Matrix

| Provider | Django package | React/SPA fit | Self-hosted | Cloud pricing | GDPR/cookies | Server-side events | QuickScale v0.80 fit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **PostHog** | `posthog` (official SDK) | Excellent (`history_change` mode, React support) | Yes (MIT, Docker Compose) | Free tier: 1M events/month | Anonymous-default event capture; operator-controlled identity | Excellent (official Python SDK) | **Approved first-class provider**: zero cost floor, strong Django fit, React SPA support, clean service-style backend contract |
| **Plausible** | `django-plausible` (thin wrapper) | Excellent (`pushState` automatic) | Yes (AGPL, Community Edition) | €9/month, no free tier | Cookieless, no consent banner in common setups | Limited; primarily client-side | Strong privacy-first alternative, but the cost floor disqualifies it as the default |
| **Matomo** | `django-matomo` or `django-analytical` | Good (manual SPA wiring) | Yes | €23/month cloud | Privacy-friendly with the right config | Good | Viable self-hosted fallback, but operationally heavy for QuickScale's default path |
| **Umami** | None (plain script tag) | Good | Yes | Managed hosting available | Cookieless | Limited | Reasonable lightweight alternative, but weaker Django ecosystem support |
| **GA4** | None (plain `gtag.js`) | Good with extra setup | No | Free tier | Cookie-consent complexity | Good | Not preferred for v0.80.0 because the compliance and consent overhead is materially higher |
| **Fathom** | `django-usefathom` | Good | No | $15/month | Privacy-focused | Limited | Credible alternative, but higher entry cost than Plausible and no self-hosted path |

## Provider Notes

### PostHog

**Pros:**
- Official Python SDK with a documented Django integration path
- Strong React and SPA route-tracking story
- Generous free tier removes the default cost floor
- Supports server-side capture cleanly from Django services
- Leaves room for future expansion without changing providers

**Cons:**
- Broader platform surface than QuickScale needs in v0.80.0
- Identity and product-analytics features require explicit scope discipline
- Self-hosting beyond low traffic is operationally heavier than the simplest website-analytics tools

**QuickScale interpretation:**
PostHog is the best fit for v0.80.0 because it gives QuickScale a first-class Django backend story, a viable React starter path, and zero mandatory provider cost while still allowing the docs to keep the actual shipped contract narrow.

### Plausible

**Pros:**
- Privacy-first and cookieless by default
- Excellent SPA behavior with a very small client footprint
- Strong EU-oriented positioning and a reasonable self-hosted path

**Cons:**
- No free cloud tier
- Less capable server-side capture story for the kinds of conversion hooks QuickScale wants
- Would still need careful documentation around manual adoption boundaries

**QuickScale interpretation:**
Plausible remains the cleanest privacy-first alternative, but the lack of a free tier is decisive for QuickScale's default milestone contract.

### Matomo and Other Alternatives

Matomo, Umami, GA4, and Fathom each solve real operator needs, but none is a better default for QuickScale v0.80.0 than PostHog. Matomo is the strongest on-prem fallback, Umami is a lightweight open-source option with a thinner Django story, GA4 adds the most consent and compliance overhead, and Fathom is credible but more expensive than Plausible without the same self-hosted escape hatch.

## Recommended Path for v0.80.0

**Recommendation:** Use PostHog as the only approved website-analytics provider for v0.80.0.

That means:
- PostHog is the only provider exposed by the planner and runtime contract in this milestone
- The backend analytics module is service-style: settings plus lifecycle and capture helpers, not a model/admin-heavy Django app
- Analytics settings remain flat and mutable through `quickscale plan --reconfigure`
- Forms integration uses a guarded direct optional import instead of generated extension-app glue
- Social click tracking is limited to QuickScale-owned generated public pages/templates
- Fresh-generation `showcase_react` templates may ship dormant PostHog support, while existing React and HTML projects adopt frontend snippets manually
- No analytics context processor or apply-managed rewrite of existing user-owned theme files is part of the v0.80.0 contract

## Reviewed Implementation Notes for v0.80.0

| Concern | Reviewed v0.80.0 contract | Explicit non-goal for this milestone |
| --- | --- | --- |
| **Approved provider** | PostHog only | No runtime Plausible path and no multi-provider abstraction |
| **Settings contract** | Flat `QUICKSCALE_ANALYTICS_*` settings | No single `QUICKSCALE_ANALYTICS` dict |
| **Backend module shape** | Service-style module with `apps.py`, `events.py`, and `services.py` | No required models, admin, URLs, or migrations |
| **Forms hook** | Guarded direct optional import of analytics helpers | No generated extension-app glue |
| **Social hook** | Track clicks only where QuickScale already owns the generated public page/template | No blanket instrumentation of project-owned custom pages |
| **React support** | Dormant `showcase_react` starter support on fresh generation only | No apply-managed rewrite of existing React files |
| **HTML support** | Manual template-snippet adoption path only | No analytics context processor and no apply-managed HTML template mutation |
| **Operator guidance** | `.env.example` plus apply-time notes for Railway runtime/build vars and manual adoption boundaries | No promise that QuickScale retrofits older projects automatically |
| **Identity posture** | Anonymous-default distinct IDs with explicit opt-in for stronger linkage | No automatic authenticated-user identity bridging |

### Planner and Settings Notes

- The planner should capture enable/disable, API key env var name, host, exclude-debug, exclude-staff, and anonymous-by-default behavior.
- `quickscale apply` should write the flat `QUICKSCALE_ANALYTICS_*` settings and update `.env.example` with `POSTHOG_*` runtime vars plus the `VITE_POSTHOG_*` vars used by fresh-generated React starter support or manual adoption.
- Disabling analytics removes backend/module wiring and the flat settings, but it does not attempt to clean up user-owned frontend snippets.

### Backend Module Notes

- `apps.py` initializes the PostHog SDK from env vars and flat settings, never from persisted raw secrets.
- `services.py` owns the capture helpers and no-op behavior when analytics is absent, disabled, or misconfigured.
- `events.py` is the canonical first-party event vocabulary surface.
- Because analytics is integration-only in v0.80.0, the service-style exception applies: no placeholder models, admin classes, or migrations are required.

### Frontend Adoption Boundaries

- Fresh `showcase_react` generations are the only automatic frontend path in v0.80.0.
- Existing React projects keep ownership of `frontend/package.json`, `src/main.*`, `src/App.*`, and related files; they adopt analytics snippets manually if desired.
- Existing HTML projects also adopt analytics snippets manually.
- The docs must stay explicit that v0.80.0 does not introduce managed retrofits of existing user-owned theme files.

### Cross-Module Notes

- Forms submission should continue working even when analytics is absent; the guarded optional import path must degrade cleanly to a no-op.
- Social click tracking should stay limited to QuickScale-owned generated public pages/templates rather than expanding into project-owned custom surfaces automatically.
- If a project wants more orchestration or custom event wiring, that work remains project-owned.

## Testing and Validation Notes

Minimum v0.80.0 validation should cover:
- contract tests for defaults, validation, normalization, and production-targeted checks
- wiring-spec tests proving flat settings are written and no context processor is added
- module tests for safe SDK initialization, no-op behavior, and stable event payload shapes
- forms regression coverage for the guarded optional import path
- generator coverage proving fresh `showcase_react` scaffolds include the dormant analytics starter support
- regression coverage proving analytics apply/reconfigure flows do not rewrite existing user-owned React or HTML theme files

## Provider Decision Record

| Provider | v0.80.0 decision | Rationale | Future trigger to reconsider |
| --- | --- | --- | --- |
| **PostHog** | ✅ Approved first-class provider | Zero cost floor, official Django SDK, strong React/SPA fit, and clean server-side capture | Reconsider if the free tier changes materially or the identity model creates unresolved compliance friction |
| **Plausible** | 📋 Documented future reconsideration path | Excellent privacy posture and EU fit, but no free tier | Reconsider if QuickScale later prioritizes strict EU/privacy defaults over the zero-cost floor |
| **Matomo** | 📋 Deferred fallback | Strong on-premise story, but heavier operational surface | Reconsider if a future operator requirement is full on-prem analytics depth |
| **Umami / Fathom / GA4** | 📋 Deferred alternatives | Each has niche strengths, but none beats PostHog on the combined fit for v0.80.0 | Reconsider only when a concrete operator or product requirement points to one of them |

## Reconsideration Triggers

Revisit the default recommendation before or after v0.80.0 only if one of these becomes true:
- PostHog materially reduces or removes the free tier that underpins the zero-cost default
- QuickScale adopts a product policy that requires strict EU-only or strict privacy-first defaults for all generated projects
- The `posthog` Python SDK becomes unmaintained or materially worsens its Django integration story
- The current manual-adoption boundaries for existing projects prove too costly compared with a different provider or a different milestone scope

If that happens, the cleanest fallback order is:
1. Plausible for the strongest privacy-first / EU-oriented default
2. Matomo for the strongest self-hosted and on-prem analytics requirement

## Conclusion

PostHog is the right default for QuickScale v0.80.0 because it removes the default cost floor, fits Django well, supports the fresh `showcase_react` starter path, and gives QuickScale a clean server-side capture story without forcing a larger runtime abstraction. The reviewed v0.80.0 contract is intentionally narrower than earlier roadmap language: flat settings, service-style backend helpers, guarded forms integration, limited social tracking on QuickScale-owned generated surfaces, and explicit manual frontend adoption for existing projects.
