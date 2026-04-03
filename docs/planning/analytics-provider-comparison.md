# Analytics Provider Comparison: v0.87.0 Analytics Module

> **You are here**: [QuickScale](../../START_HERE.md) → [Docs](../index.md) → **Planning** → Analytics Provider Comparison
> **Related docs**: [Roadmap v0.80.0](../technical/roadmap.md#v0800-quickscale_modulesanalytics---analytics-module) | [Decisions](../technical/decisions.md) | [Competitive Analysis](../overview/competitive_analysis.md)

## Goal

Compare analytics provider options for QuickScale's planned analytics module (`quickscale_modules.analytics`, v0.87.0) and define a concrete integration path for the first release.

## Context

The roadmap pulls analytics forward to **v0.87.0** under an integration-first, single-provider-first policy. The v0.87.0 scope is intentionally narrow: website analytics first, one approved provider, safe script injection across both React and HTML theme families, and a small first-party event vocabulary for forms and social conversion hooks. Product analytics, observability, and embedded BI/reporting remain later follow-up.

The roadmap's initial leading candidate was **Plausible**. After evaluating the full provider set — including cost floor — this document updates that recommendation to **PostHog**, which covers the same website analytics scope, adds a generous free tier (1M events/month cloud, MIT self-hosted), and ships a first-class Django SDK and React library. Plausible remains the documented secondary path for operators with a strict privacy-first or EU-only data residency requirement.

This planning pass separates two concerns that are often conflated:
- **Provider choice**: who collects and stores analytics data
- **Integration architecture**: how QuickScale injects scripts, captures route changes, and wires cross-module conversion hooks across its React and HTML theme families

## Executive Summary

Two valid paths emerged:

| Path | Best when | Main downside |
| --- | --- | --- |
| **PostHog-first (product + web analytics, free tier)** | QuickScale wants a single provider with zero cost floor, first-class Django SDK, automatic React SPA tracking, and room to grow into product analytics | Larger surface area than a minimal website-analytics-first scope; self-hosting beyond ~100k events/month requires ClickHouse infrastructure |
| **Plausible-first (cookieless, EU cloud)** | QuickScale wants the absolute minimum integration surface, strict EU data residency, or an operator has a hard no-cookie, no-JS-SDK requirement | Cloud pricing starts at €9/month with no free tier; limited server-side event surface; scope ceiling at website analytics |

For v0.87.0, the practical choice is:

**Use PostHog as the approved first-class provider for v0.87.0. Initialize via the official `posthog` Python SDK in Django's AppConfig, inject `@posthog/react` in the React theme with automatic route tracking, and wire the forms/social conversion hooks through PostHog's event capture API. Document Plausible as the secondary path for privacy-first or EU-only requirements.**

That keeps the v0.87.0 scope disciplined — website analytics first, single approved provider — while removing the €9/month cost floor that would block generated projects from going live without a paid account.

## Evaluation Criteria

| Criterion | Why it matters for QuickScale |
| --- | --- |
| Django fit | Generated projects are Django-first; integration friction and available packages matter immediately |
| React/SPA fit | Both theme families must work; React route tracking is a first-class requirement |
| Privacy/GDPR posture | QuickScale targets EU-adjacent markets; cookie consent complexity must be explicitly managed |
| Script injection simplicity | The module must inject into both `showcase_react` and HTML theme layouts without a heavy runtime dependency |
| Self-hosted option | Agencies with data-residency requirements need a path that doesn't require a cloud SaaS account |
| Server-side and cross-module hooks | Forms and social module conversion hooks should be instrumentable via a stable event vocabulary |
| Pricing at project scale | Generated projects must be able to go live without a paid account; a zero-cost floor is a hard requirement for the default provider |
| Scope discipline | v0.87.0 is website-analytics-first; the provider must not force product-analytics-level instrumentation complexity onto the generated project |

## Django and React Integration Landscape

Before comparing providers, it is worth understanding the integration ecosystem QuickScale can draw on.

### `django-analytical`

The `django-analytical` package (Jazzband, actively maintained as of 2026) provides a generic template-tag-based interface for 25+ analytics providers. It supports Matomo, Clicky, Hotjar, Google Analytics, Heap, Mixpanel, and others through a single `{% analytics %}` tag, with provider selection in `settings.py`.

**Key gap**: `django-analytical` does not natively support Plausible, PostHog, or Umami. Using those three requires either a dedicated Django package or a plain script tag injection.

**QuickScale fit**: A `django-analytical`-style abstraction would require maintaining provider adapters for the providers QuickScale cares about most, while adding a dependency for those it does not ship. For v0.87.0, a narrower planner/apply injection pattern that stays provider-specific is simpler and more honest than wrapping a generic abstraction around a single approved provider.

### Available Per-Provider Django Packages

| Provider | Django package | Approach |
| --- | --- | --- |
| Plausible | `django-plausible` (RealOrangeOne) | Template tag; also `django-plausible-proxy` for ad-blocker bypass |
| Matomo | `django-matomo` + `django-analytical` | Template tag; `MATOMO_SITE_ID` + `MATOMO_URL` in settings |
| PostHog | `posthog` (official Python SDK) | AppConfig initialization; Python SDK + `posthog-js` for frontend |
| GA4 | No official Django package | Plain `gtag.js` script tag; `react-ga4` npm for React |
| Umami | No Django package | Plain script tag; React community packages exist |
| Fathom | `django-usefathom` | Template tag; very thin wrapper |

### React and SPA Route Tracking

All providers require explicit handling of client-side route changes in React SPA contexts. The default behavior for most providers is to track the initial page load only, not subsequent client-side navigation.

| Provider | SPA route tracking | Notes |
| --- | --- | --- |
| Plausible | Automatic via `pushState` detection | Handles React Router automatically; hash-based routing needs the `hash` variant |
| PostHog | Automatic via `history_change` mode | `@posthog/react` library; updated defaults since 2024 |
| Umami | Automatic via built-in `data-auto-track` | React community libraries extend it |
| Matomo | Manual `trackPageView()` required | `matomo-tracker-for-react` or `@datapunt/matomo-tracker-react` |
| GA4 | Manual setup required | `react-ga4` npm; must disable auto-pageview and add Router listener |
| Fathom | Automatic via script auto-tracking | React integration well documented |

## Provider Comparison Matrix

| Provider | Django package | React/SPA fit | Self-hosted | Cloud pricing | GDPR/cookies | Server-side events | QuickScale v0.87 fit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **PostHog** | `posthog` (official SDK) | Excellent (history_change mode, `@posthog/react`) | Yes (MIT, Docker Compose) | Free tier: 1M events/month | Event-based, no cookies | Excellent (webhooks, Python SDK, Measurement Protocol) | **Approved first-class provider**: zero cost floor, official Django SDK, automatic React SPA tracking, room to grow |
| **Plausible** | `django-plausible` (thin wrapper) | Excellent (pushState automatic) | Yes (AGPL, Community Edition) | €9/month, no free tier | Cookieless, no consent banner | Proxy available; primary is client-side | Secondary path: best for operators with strict EU-only data residency or a no-JS-SDK requirement |
| **Matomo** | `django-matomo` or `django-analytical` | Good (`matomo-tracker-for-react`) | Yes (free) | €23/month cloud | Consent-free if cookies off + IP anonymized; CNIL-approved | Matomo Tracking API (server-side) | Best self-hosted-first alternative if data ownership is the hard requirement |
| **Umami** | None (plain script tag) | Excellent (auto-track, community React libs) | Yes (open-source, Node.js) | Managed hosting (umami.is) | Cookieless, no consent banner | Limited API | Good lightweight alternative; no Django package and Node.js runtime requirement for self-hosting reduce fit |
| **GA4** | None (plain gtag.js) | Good but requires explicit setup (`react-ga4`) | No (cloud only) | Free tier | Requires cookie consent banner; Google Consent Mode V2 mandatory since 2025 | Measurement Protocol; GTM Server-Side | Not preferred: cookie consent complexity, cloud-only, and less privacy-aligned than the alternatives |
| **Fathom** | `django-usefathom` | Good (script auto-tracking) | No (cloud only) | $15/month | Privacy-focused; EU servers | No | Credible privacy-first alternative; cloud-only at a higher price point than Plausible |
| **Pirsch** | None | Limited (manual API calls) | No (cloud only, EU-hosted) | €6/month | Cookieless fingerprinting; GDPR | API available | EU-data-residency path; narrower ecosystem than the five primary candidates |
| **Simple Analytics** | None | Manual | No (cloud only) | $9/month | Cookieless, no consent | No | Affordable privacy-first option; fewer integrations than Plausible or PostHog |
| **Mixpanel** | `mixpanel-python` (official SDK) | Good (Mixpanel JS) | No (cloud only) | Free tier: 20M events/month | Cookies by default; GDPR configurable | Yes (Python SDK) | Product analytics, not website analytics; deferred beyond v0.87 |

## Pros and Cons

### PostHog

**Pros:**
- Official Python SDK (`posthog`) with a documented Django integration path and AppConfig initialization pattern
- Official React library (`@posthog/react`) with automatic `history_change` tracking; no manual `trackPageView()` calls for React Router
- Generous free tier (1M events/month cloud; 5k session recordings; 1M feature flag requests) — generated projects go live with zero provider cost
- MIT-licensed open-source self-hosting option (Docker Compose) for operators with data-ownership requirements
- Excellent webhook support and server-side Python SDK for cross-module conversion hooks
- Feature flags, session replay, and experiments are available as a natural expansion path when scope grows beyond website analytics

**Cons:**
- Platform surface area is larger than a minimal website-analytics-first scope; generated projects must keep instrumentation discipline to avoid accumulating product-analytics complexity unintentionally
- Free tier includes session replay and experiments, which can pull scope beyond v0.87.0 guardrails if not explicitly bounded in the planner
- Self-hosting beyond ~100k events/month requires a ClickHouse cluster; the lightweight Docker Compose path is only suitable for low-traffic projects
- Identity model (distinct IDs, person profiles) adds a concept that pure website analytics tools do not expose; the planner must document anonymous-default behavior

**QuickScale interpretation:**
PostHog is the best default for v0.87.0 because it removes the cost floor that would block generated projects from going live, ships a first-class Django SDK, and delivers automatic React SPA route tracking without a bespoke library. The richer product analytics surface is a future asset, not a current liability, provided the v0.87.0 integration stays within the website-analytics-first event vocabulary.

### Plausible

**Pros:**
- Cookieless and privacy-first by design; no consent banner required in most jurisdictions
- Automatic `pushState`-based React Router tracking with no additional library
- Lightweight script (~1.4 kb); the lowest performance overhead of all candidates
- `django-plausible` and `django-plausible-proxy` packages are maintained and available on PyPI
- EU-hosted and EU-company; minimal cross-border data friction for EU-adjacent QuickScale projects
- Self-hosted Community Edition available (AGPL) for operators who must keep data on their own infrastructure

**Cons:**
- Cloud-only paid tier starts at €9/month; no free tier — generated projects must have a paid account before going live
- Self-hosted requires an AGPL-licensed operational stack separate from the Django project (Docker Compose + Postgres + Clickhouse)
- Server-side event surface is limited; the proxy path reduces ad-blocker interference but does not add a richer server-side event model
- Custom event depth is narrower than PostHog's funnel/retention/experiment surface

**QuickScale interpretation:**
Plausible is the right secondary path for operators with a hard EU-only data residency requirement, a strict cookieless posture, or a preference for the simplest possible integration surface. The €9/month cost floor is the decisive constraint that prevents it from being the default for all generated projects.

### Matomo

**Pros:**
- Best self-hosted parity with Google Analytics-style depth (goals, internal search, ecommerce, campaigns)
- `django-matomo` and `django-analytical` provide mature Django integration paths
- Privacy-first and GDPR-certified; CNIL (French DPA) approved for consent-free tracking when cookies disabled and IP anonymized
- Mature React integration via `matomo-tracker-for-react` and `@datapunt/matomo-tracker-react`
- On-premise option is free to download with no event limits once self-hosted

**Cons:**
- Requires separate runtime stack (PHP + MySQL/MariaDB) for self-hosting; not compatible with the Django-native project shape QuickScale generates
- Cloud option (€23/month starting) is significantly more expensive than Plausible
- Manual `trackPageView()` calls required in React; no automatic SPA route detection
- Larger operational surface; self-hosting requires maintenance discipline that is outside the generated-project scope

**QuickScale interpretation:**
Matomo is the best fallback if a future operator requires full on-premise GA-style data ownership, but the PHP/MySQL runtime is architecturally misaligned with QuickScale's Django-first generated projects. Keep it as a documented secondary path rather than the v0.87.0 default.

### Umami

**Pros:**
- Cookieless and privacy-first; no consent banner required
- Excellent React/SPA support through automatic `pushState` detection; no additional library required
- Lightweight and easy to self-host (Node.js + Postgres)
- Free and open-source (MIT)

**Cons:**
- No official Django package; requires plain script tag injection
- Self-hosting introduces a Node.js runtime alongside the Django stack in generated projects
- Event API surface and webhook support are limited compared to PostHog or even Plausible
- Smaller ecosystem and fewer community integrations than the top-tier candidates

**QuickScale interpretation:**
Umami is a credible privacy-first alternative for developers already running a Node.js stack, but the Node.js self-hosting dependency creates architectural friction for Django-only generated projects. Keep it as a documented secondary self-hosted alternative, not a v0.87.0 default.

### GA4

**Pros:**
- Market standard with the widest recognition among clients and stakeholders
- Free tier with no event cap limits (subject to data sampling)
- `react-ga4` is a well-maintained npm library for React route tracking
- Extensive documentation, tooling, and third-party integrations

**Cons:**
- Requires cookie consent banner by default; Google Consent Mode V2 is mandatory for EU/GDPR compliance since 2025
- Cloud-only; no self-hosted option
- No official Django package; script injection is manual
- Manual `react-ga4` setup required: disable auto-pageview, add Router listener
- Data stored on Google infrastructure; cross-border data transfer concerns for EU projects
- Most complex consent management path of all candidates

**QuickScale interpretation:**
GA4 is not preferred for v0.87.0. The mandatory cookie consent complexity, cloud-only posture, and cross-border data storage are architectural friction points that conflict with QuickScale's privacy-first defaults. Evaluate and document it as a secondary path for projects where client familiarity with Google tooling outweighs the compliance overhead.

### Fathom

**Pros:**
- Privacy-first, EU-hosted (Hetzner EU servers)
- `django-usefathom` package available on PyPI
- Cookieless and automatic script tracking; good React support
- No consent banner required in most jurisdictions

**Cons:**
- Cloud-only; no self-hosted option (unlike Plausible's Community Edition)
- Starts at $15/month vs Plausible's €9/month; higher entry cost for identical privacy posture
- Smaller ecosystem and fewer community integrations than Plausible

**QuickScale interpretation:**
Fathom is a credible privacy-first alternative for operators with a preference for it, but Plausible has a lower cost floor and a stronger self-hosted path. Keep Fathom as a documented secondary provider.

## Market Signals: What Adjacent Platforms Publicly Use

These are informal signals from public documentation reviewed in 2026-04. They are useful orientation benchmarks, not neutral endorsements.

| Platform | Public signal | Planning takeaway |
| --- | --- | --- |
| **SaaS Pegasus** | Publishes dynamic charts driven by app-level data (revenue, signups, churn); Sentry for error tracking; no external analytics provider integrated by default | Django boilerplates treat analytics as an operator concern, not a default module |
| **Cookiecutter Django** | No analytics included in the standard template; cookiecutter-django-vue variant includes an optional Google Analytics / Yandex Metrica setup | Analytics is left for post-generation configuration in the leading open-source Django starter |
| **Apptension SaaS Boilerplate** | Analytics mentioned in the platform overview; not specifically documented for website analytics; React + Django + AWS stack | No strong signal on website analytics provider choice for this competitor |
| **Plausible product page** | Lists developer-tool customers including Warp, Mintlify, Infisical, Dub, Finta, Fey, and Replit | Strong developer-tool momentum signal; aligns with QuickScale's target user segment |
| **PostHog product page** | Lists Y Combinator, Hasura, and thousands of open-source projects | Strong signal for product-analytics and OSS-native teams; less specifically website-analytics-first |

## Competitor Usage Snapshot

This section follows the competitor set defined in [competitive_analysis.md](../overview/competitive_analysis.md) and extends it with analytics-specific research as of 2026-04.

| Competitor | Analytics approach | Architecture category | Planning takeaway |
| --- | --- | --- | --- |
| **SaaS Pegasus** | App-driven metrics charts (Pegasus Charts); Sentry error tracking; no turnkey website analytics integration | Self-owned metrics plus error monitoring | Confirms that analytics is an operator configuration problem in Django boilerplates; no strong provider signal |
| **Cookiecutter Django** | No analytics in default template; optional GA/Yandex in Vue variant | Manual configuration | No boilerplate default; even cookiecutter treats website analytics as opt-in |
| **Apptension SaaS Boilerplate** | Analytics mentioned but not specifically documented | Unknown architecture | Not a useful benchmark for this decision |
| **Ready SaaS** | No confirmed analytics stack from public docs | Unknown | Not a useful benchmark |

### Competitor Pattern Summary

The public Django boilerplate landscape does **not** include a standard analytics integration. None of the primary competitors ship a default analytics provider integration. This is an opportunity for QuickScale to differentiate by shipping an opinionated, privacy-first analytics integration as a first-class module rather than leaving it as a post-generation manual step.

## Recommended Path for v0.87.0

**Recommendation:** Use PostHog as the single approved website-analytics provider for v0.87.0. Initialize via the official `posthog` Python SDK in Django's AppConfig. Inject `posthog-js` via `@posthog/react` in the React theme with automatic history-change route tracking. Wire forms and social conversion hooks through PostHog's server-side and client-side event capture API using a small first-party event vocabulary. Document Plausible as the secondary path for EU-only data residency requirements.

That means:
- PostHog is the approved first-class provider for v0.87.0
- The `posthog` Python SDK initializes in the generated project's AppConfig; `posthog-js` and `@posthog/react` handle the React theme frontend
- React Router SPA route changes are tracked automatically via `capture_pageview: 'history_change'`; no manual tracking calls needed
- Server-side conversion hooks (`posthog.capture(distinct_id, 'form_submit', {...})`) wire the forms and social module events through the Python SDK
- Anonymous-default behavior: distinct IDs use anonymous session identifiers; the planner documents the free tier limits and optional authenticated-user opt-in
- Planner output surfaces the free tier ceiling (1M events/month cloud) and the self-hosted Docker Compose path for operators who need data ownership
- Plausible, Matomo, GA4, and Umami remain documented deferrals; their implementation constraints are recorded here as the decision history

## Integration Architecture for v0.87.0

| Concern | Planned implementation choice | Why |
| --- | --- | --- |
| **Approved provider** | PostHog | Zero cost floor (1M events/month free); official Django SDK; automatic React SPA tracking; MIT self-hosted option |
| **Django integration layer** | `posthog` Python SDK initialized in AppConfig | Official SDK; settings-driven API key and host config; server-side capture works from any Django layer |
| **HTML theme injection** | `posthog-js` script snippet in base layout | Single injection point in `base.html.j2`-derived layout; no template tag dependency |
| **React theme injection** | `PostHogProvider` wrapping the app root with `@posthog/react` | Official React library; `capture_pageview: 'history_change'` automatically tracks React Router SPA routes |
| **Route tracking** | Automatic via `history_change` mode in PostHog JS | Zero manual `trackPageView()` calls; works with React Router v6+ out of the box |
| **Conversion hooks** | `posthog.capture(distinct_id, 'form_submit', {...})` from the Python SDK; `posthog.capture('social_link_click', {...})` from client-side JS | Server-side hooks are ad-blocker proof; client-side hooks cover public-page interactions |
| **Consent posture** | Anonymous distinct IDs by default; planner documents free tier limits and opt-in path | PostHog is event-based and cookieless in anonymous mode; no consent banner required with this configuration |
| **Self-hosted option** | PostHog self-hosted (MIT, Docker Compose) documented as secondary path | Suitable for operators with data-ownership requirements; recommended up to ~100k events/month |
| **Secondary provider** | Plausible documented for EU-only data residency or no-JS-SDK requirements | Plausible CE (AGPL) or cloud (€9/month); operator-chosen, not the scaffolded default |
| **Deferred from v0.87.0** | Multi-provider support, session replay, feature flags, experiments, product funnels | Avoids over-building the first release; PostHog's richer surface is available as an opt-in expansion path |

## Implementation Plan for v0.87.0

### 1. Planner Configuration

| Task | Acceptance signal |
| --- | --- |
| Add analytics planner prompt: enabled/disabled, PostHog API key, PostHog host (defaults to `https://us.i.posthog.com`; overridable for EU cloud or self-hosted) | Config flows through the standard QuickScale `quickscale plan` workflow |
| Surface free tier ceiling (1M events/month), self-hosted Docker Compose path, and anonymous-default posture in planner output | Operators understand cost, data residency, and consent posture before applying |
| Wire env-var-based settings for API key and host at apply time | Generated projects configure PostHog without storing secrets in code |
| Add `ANALYTICS_ENABLED`, `POSTHOG_API_KEY`, `POSTHOG_HOST` to the generated `.env.example` | Env-var contract is explicit and discoverable |
| Document Plausible as the documented secondary option in planner output for operators with EU-only data residency requirements | Operators who need Plausible have a clear upgrade path without it being the default |

### 2. SDK and Script Injection

| Task | Acceptance signal |
| --- | --- |
| Add `posthog` Python package to the generated project's dependencies when analytics is enabled | Import is conditional; disabled projects do not carry the package |
| Initialize the PostHog Python SDK in the generated project's AppConfig (`posthog.init(api_key, host=...)`) | Server-side capture is available from any Django layer without per-request setup |
| Inject `posthog-js` snippet in HTML theme base layout | Single injection point in `base.html.j2`-derived layout; pageviews and client-side events captured for HTML theme routes |
| Add `@posthog/react` dependency and wrap the React app root with `PostHogProvider` in `showcase_react` | `capture_pageview: 'history_change'` automatically tracks React Router SPA route changes; no manual `trackPageView()` calls |
| Add conditional rendering: SDK initialization and script injection are omitted when `ANALYTICS_ENABLED=false` or `DEBUG=true` | CI and local dev do not pollute analytics data |

### 3. Cross-Module Conversion Hooks

| Task | Acceptance signal |
| --- | --- |
| Add server-side `posthog.capture(distinct_id, 'form_submit', {'form_id': ..., 'module': 'forms'})` call on forms module submission success | Forms module submission events appear in the PostHog events stream; ad-blocker proof via server-side capture |
| Add client-side `posthog.capture('social_link_click', {'network': ..., 'link_id': ...})` on social module public page link interactions | Social public page interactions are instrumentable as conversion events |
| Document the first-party event vocabulary: event name, property keys, capture layer (server-side vs client-side), and which module generates them | The event contract is stable and reviewable without reading source code |

### 4. Operator Diagnostics and Consent Guidance

| Task | Acceptance signal |
| --- | --- |
| Add apply-time output: PostHog configuration summary, required env vars, PostHog dashboard URL, and live event test path | Operators can confirm integration without reading source code |
| Add test-event verification step or link to PostHog's live events view | Operators know how to confirm events are arriving in the PostHog dashboard |
| Add consent posture documentation: PostHog in anonymous distinct ID mode does not use cookies; document the opt-in path for authenticated-user identity linkage | Generated projects document their analytics posture; operators understand what requires consent |

### 5. Testing Scope

| Test area | Minimum expectation |
| --- | --- |
| Planner/apply lifecycle | Coverage for analytics enabled, disabled, and partially configured projects |
| SDK initialization | AppConfig correctly initializes the Python SDK from env vars; missing or empty `POSTHOG_API_KEY` fails loudly in production-targeted setups and degrades safely in dev |
| Script injection | HTML theme and React theme layouts each include the script/provider when enabled and omit them when disabled |
| Custom event vocabulary | Unit coverage for forms and social module event call shapes (server-side and client-side) |
| Integration smoke | Manual verification that pageviews and custom events appear in PostHog dashboard after plan → apply on a test project |

## Provider Decision Record

The following table records the disposition of each evaluated provider so future contributors understand what was considered and why each path was taken.

| Provider | v0.87.0 decision | Rationale | Future trigger to reconsider |
| --- | --- | --- | --- |
| **PostHog** | ✅ Approved first-class provider | Zero cost floor (1M events/month free cloud, MIT self-hosted), official Django SDK, automatic React SPA tracking via `@posthog/react`, server-side Python capture, and a natural expansion path to product analytics without changing providers | Re-evaluate if the PostHog free tier changes materially or if the identity/person model creates compliance friction that anonymous-default mode cannot resolve |
| **Plausible** | 📋 Documented secondary path | Cookieless, EU-hosted, automatic React SPA tracking, `django-plausible` package; the €9/month cost floor with no free tier prevents it from being the default for all generated projects | Revisit as the primary default if PostHog's free tier is reduced or if a future QuickScale product policy requires strict EU-only data residency for all generated projects |
| **Matomo** | 📋 Deferred; documented secondary self-hosted path | Best option for operators requiring full on-premise data ownership with GA-style depth; PHP/MySQL runtime is architecturally misaligned with Django-first generated projects | Revisit if a QuickScale operator has a hard data-residency requirement that neither Plausible self-hosted nor PostHog self-hosted can meet |
| **Umami** | 📋 Deferred; documented lightweight alternative | Good cookieless option; Node.js self-hosting runtime adds friction to Django-only projects; no official Django package | Revisit if QuickScale gains a Node.js-adjacent theme family or if the ecosystem matures toward a Django package |
| **GA4** | 📋 Deferred; documented secondary path for Google-aligned projects | Mandatory Google Consent Mode V2 and cookie consent banner overhead; cloud-only; less privacy-aligned than leading candidates | Revisit if an operator explicitly requires GA4 for ad attribution or client stakeholder reporting requirements |
| **Fathom** | 📋 Deferred; documented alternative to Plausible | Privacy-first and EU-hosted like Plausible, but cloud-only with a higher entry cost; `django-usefathom` package exists | Revisit if Plausible raises pricing or narrows its Community Edition AGPL terms |
| **Pirsch** | 📋 Deferred; EU-data-residency alternative | EU-hosted (Germany), GDPR-compliant fingerprinting, low cost; narrower ecosystem and no Django package | Revisit if strong EU-data-residency differentiation becomes a product requirement |
| **Simple Analytics** | 📋 Deferred; budget privacy-first alternative | Cookieless and affordable; narrower ecosystem than Plausible and less Django community documentation | Revisit if Plausible's pricing becomes a blocker and Simple Analytics improves its Django integration surface |
| **Mixpanel / Amplitude** | 📋 Deferred; product analytics only | Event-based product analytics tools, not website analytics; better compared to PostHog at the product analytics expansion milestone | Revisit alongside PostHog at the post-v0.87.0 product analytics milestone |

## Reconsideration Triggers

Change the primary recommendation before v0.87.0 implementation starts if any of these become true:
- PostHog's free tier is reduced or removed; if so, evaluate Plausible as the new default for low-traffic projects and PostHog as the paid-tier upgrade path
- The PostHog person/identity model creates GDPR compliance concerns that anonymous-default mode cannot resolve; if so, evaluate Plausible (strictly cookieless, no identity model) as the default
- A future QuickScale product policy requires strict EU-only data residency for all generated projects by default; if so, switch to Plausible EU cloud or Plausible Community Edition as the scaffolded default
- The `posthog` Python SDK or `@posthog/react` becomes unmaintained; if so, evaluate Plausible or a plain script-tag approach

If that happens, the cleanest fallback choices are:
1. Plausible if the EU-only data residency or strictest-possible cookieless posture is the hard requirement
2. Matomo self-hosted if full GA-parity data ownership depth is the hard requirement

## Conclusion

PostHog is the right default for v0.87.0 because it removes the cost floor that would block generated projects from going live, delivers an official Django SDK and React integration library, and provides automatic SPA route tracking without a bespoke implementation. For the stated scope — website analytics first, single approved provider, anonymous-default posture, React and HTML theme injection — the strongest fit is **`posthog` Python SDK initialization in AppConfig, `@posthog/react` with `history_change` mode for the React theme, and server-side plus client-side event capture for forms and social conversion hooks**. Plausible remains the right secondary choice for operators with strict EU-only data residency or a hard cookieless requirement, but it should not be the default when a zero-cost-floor alternative with equal or better Django and React integration exists.
