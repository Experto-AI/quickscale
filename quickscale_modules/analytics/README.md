# QuickScale Analytics Module

Service-style PostHog analytics foundation for QuickScale-generated projects.

This module is the v0.80.0 backend-first analytics contract. Repository SSOT still lives in ../../README.md, ../../docs/technical/decisions.md, and ../../docs/technical/roadmap.md.

## What Ships In v0.80.0

- An installable Django app that initializes the PostHog Python SDK safely during startup without blocking Django boot.
- Flat `QUICKSCALE_ANALYTICS_*` settings as the authoritative planner/apply contract.
- Server-side capture helpers for generic events plus the first-party `form_submit` and `social_link_click` vocabulary.
- Template tags for manual server-rendered adoption without introducing a context processor.
- No models, admin, URLs, or migrations because analytics is an approved service-style integration module in this milestone.

## Configuration Surface

Planner-owned config remains authoritative in generated settings and `quickscale.yml`.

```yaml
modules:
  analytics:
    enabled: true
    provider: posthog
    posthog_api_key_env_var: POSTHOG_API_KEY
    posthog_host_env_var: POSTHOG_HOST
    posthog_host: https://us.i.posthog.com
    exclude_debug: true
    exclude_staff: false
    anonymous_by_default: true
```

Supported mutable keys come from [module.yml](./module.yml):

- `enabled`
- `provider` (`posthog` only)
- `posthog_api_key_env_var`
- `posthog_host_env_var`
- `posthog_host`
- `exclude_debug`
- `exclude_staff`
- `anonymous_by_default`

## Runtime Notes

- Startup is intentionally non-blocking. Missing SDK or missing env vars disable analytics safely instead of preventing app startup.
- The module never persists raw PostHog credentials in settings, `quickscale.yml`, or state files. Env-var references stay authoritative.
- Existing React and HTML theme files remain user-owned in v0.80.0. Use the provided template tags only when you explicitly adopt analytics in server-rendered templates.

## Template Tags

Load `analytics_tags` for manual HTML adoption:

- `analytics_public_config` returns the resolved runtime config dictionary for the current request.
- `analytics_public_config_json` returns the same payload as JSON for inline script/bootstrap patterns.

These tags do not rewrite templates automatically and they remain optional in this phase.

## Related Docs

- ../../docs/technical/roadmap.md
- ../../docs/planning/analytics-provider-comparison.md
- ../README.md
