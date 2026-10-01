# QuickScale Analytics Module

Service-style PostHog analytics foundation for QuickScale-generated projects.

## Overview

Analytics is a service-style integration module: it ships no models, admin, migrations, or
data tables. It initializes the PostHog Python SDK safely during startup without blocking
Django boot, exposes server-side capture helpers with a stable event vocabulary, and offers
template tags for manual server-rendered adoption without a context processor.

- A flat `QUICKSCALE_ANALYTICS_*` settings surface owned by the module manifest.
- One generic server-side capture helper; feature modules own and emit their own event names.
- A module-owned overview page at `analytics/`.

## Configuration

The module declares the options below in `module.yml`; `quickscale plan` and `quickscale apply`
write them to the generated settings, and `quickscale.yml` carries the desired values.

| Option | Type | Default | Django setting | Description |
|--------|------|---------|----------------|-------------|
| `enabled` | boolean | `true` | `QUICKSCALE_ANALYTICS_ENABLED` | Enable the analytics runtime. When disabled, QuickScale removes managed backend analytics wiring. |
| `provider` | string | `posthog` | `QUICKSCALE_ANALYTICS_PROVIDER` | Approved analytics provider; PostHog is the only supported option. |
| `posthog_api_key_env_var` | string | `POSTHOG_API_KEY` | `QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR` | Environment-variable name containing the PostHog project API key. |
| `posthog_host_env_var` | string | `POSTHOG_HOST` | `QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR` | Optional environment-variable name containing the PostHog ingestion host override. |
| `posthog_host` | string | `https://us.i.posthog.com` | `QUICKSCALE_ANALYTICS_POSTHOG_HOST` | Fallback PostHog ingestion host used when the host env var is blank. |
| `exclude_debug` | boolean | `true` | `QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG` | Disable analytics automatically when Django `DEBUG` is true. |
| `exclude_staff` | boolean | `false` | `QUICKSCALE_ANALYTICS_EXCLUDE_STAFF` | Skip request-scoped analytics payloads for authenticated staff users. |
| `anonymous_by_default` | boolean | `true` | `QUICKSCALE_ANALYTICS_ANONYMOUS_BY_DEFAULT` | Use session-based anonymous distinct IDs unless operators explicitly opt into authenticated identity linkage. |

The same desired state in `quickscale.yml`:

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

## Public surface

- `get_analytics_runtime_settings()` returns an `AnalyticsRuntimeSettingsSnapshot`;
  `is_analytics_active()` and `analytics_enabled_for_request(request)` answer whether capture
  runs for the current process and request.
- `configure_analytics_client()` initializes the PostHog client; `capture_event()` sends an event
  the sending module names; `get_distinct_id()` resolves the active distinct ID.
- `get_template_analytics_context()` builds the dictionary the template tags render.
- `events.py` holds PostHog's pageview name: `ANALYTICS_EVENT_PAGEVIEW` (`$pageview`). Feature
  modules name their own events in their `services.py` under the `quickscale_<module>_<event>`
  stem — forms, for example, emits `quickscale_forms_submitted`.
- Template tags, loaded with `{% load quickscale_analytics %}`:
  `analytics_public_config` returns the resolved runtime config dictionary for the current
  request, and `analytics_public_config_json` returns the same payload as JSON for inline
  script or bootstrap patterns.

## URLs

`quickscale apply` mounts the module under `analytics/`. The single route is:

| URL name | Path | View |
|----------|------|------|
| `quickscale_analytics:dashboard` | `analytics/` | Module-owned analytics overview page. |

## Management commands

This module ships no management commands.

## Operations

- Startup is intentionally non-blocking: a missing SDK or missing environment variables
  disable analytics safely instead of preventing app startup.
- The module never persists raw PostHog credentials in settings, `quickscale.yml`, or state
  files; the `_env_var` options are the authoritative references.
- `exclude_debug` and `exclude_staff` keep non-production and staff traffic out of capture;
  `anonymous_by_default` keeps distinct IDs session-based unless authenticated identity
  linkage is explicitly enabled.
- Existing React and HTML theme files remain user-owned: use the template tags only when you
  explicitly adopt analytics in server-rendered templates.

## Extending

- The template tags are the supported manual adoption path for server-rendered templates;
  they do not rewrite templates automatically.
- Related documentation: [roadmap](../../docs/technical/roadmap.md),
  [analytics provider comparison](../../docs/planning/analytics-provider-comparison.md), and
  the [module workspace README](../README.md).
