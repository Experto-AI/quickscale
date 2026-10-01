# QuickScale Social Module

Curated social links and embeds for QuickScale-generated projects.

## Overview

- An installable Django app with `SocialLink` and `SocialEmbed` models, migrations, admin
  registration, and package-local pytest coverage.
- Theme-agnostic runtime services that expose normalized read-only payloads for curated
  link-tree and embed surfaces.
- Backend-owned embed preview metadata for YouTube and TikTok, including persisted resolution
  status, timestamps, and operator-visible errors.
- Generated-project-managed JSON endpoints at `/_quickscale/social/` and
  `/_quickscale/social/embeds/`, backed by module services instead of module-owned HTTP APIs.
- Fresh `showcase_react` public pages at `/social` and `/social/embeds`; existing generated
  projects stay backend-only unless the theme files are adopted manually.

Support matrix:

- **Existing generated projects:** `quickscale apply` adds backend-managed settings,
  admin/runtime wiring, and the generated-project integration endpoints, but it does not
  rewrite user-owned `showcase_react` routes, navigation, templates, or page source.
- **Fresh `showcase_react` generations:** get the full backend plus React public experience,
  including Django-owned `/social` and `/social/embeds` pages hydrated by the shared React
  bundle.
- **Older projects that want the React UX:** manually adopt the `showcase_react` social page
  templates and frontend files after backend wiring is in place.

## Configuration

The module declares the options below in `module.yml`; `quickscale plan` and `quickscale apply`
write them to the generated settings, and `quickscale.yml` carries the desired values.

| Option | Type | Default | Django setting | Description |
|--------|------|---------|----------------|-------------|
| `enabled` | boolean | `true` | `QUICKSCALE_SOCIAL_ENABLED` | Mount the module's public `/social` surfaces. Off keeps the app, its data, the admin, and the managed files installed but mounts none of its public URLs; the link-tree/embeds flags still shape the surfaces while it is on. |
| `link_tree_enabled` | boolean | `true` | `QUICKSCALE_SOCIAL_LINK_TREE_ENABLED` | Enable the public link-tree surface at the fixed `/social` route. |
| `layout_variant` | string | `list` | `QUICKSCALE_SOCIAL_LAYOUT_VARIANT` | Default link-tree presentation variant: `list`, `cards`, or `grid`. |
| `embeds_enabled` | boolean | `true` | `QUICKSCALE_SOCIAL_EMBEDS_ENABLED` | Enable the public embed gallery surface at the fixed `/social/embeds` route. |
| `provider_allowlist` | list | `["facebook", "instagram", "linkedin", "tiktok", "x", "youtube"]` | `QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST` | Allowlisted social providers for curated links and embeds. Embed-capable providers are TikTok and YouTube. |
| `cache_ttl_seconds` | integer | `300` | `QUICKSCALE_SOCIAL_CACHE_TTL_SECONDS` | Cache TTL in seconds for normalized social payloads and provider lookups. |
| `links_per_page` | integer | `24` | `QUICKSCALE_SOCIAL_LINKS_PER_PAGE` | Maximum number of curated links exposed through the fixed `/social` surface. |
| `embeds_per_page` | integer | `12` | `QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE` | Maximum number of curated embeds exposed through the fixed `/social/embeds` surface. |

```yaml
modules:
  social:
    link_tree_enabled: true
    layout_variant: cards
    embeds_enabled: true
    provider_allowlist:
      - youtube
      - tiktok
      - linkedin
    cache_ttl_seconds: 300
    links_per_page: 24
    embeds_per_page: 12
```

## Public surface

Models:

- `SocialLink` and `SocialEmbed` inherit the abstract `BaseSocialItem`, which provides title,
  description, provider name, URL, normalized URL, display order, publication flag, and
  timestamps.
- `SocialEmbed` adds resolution metadata: status, error, attempt and resolution timestamps,
  resolved embed and thumbnail URLs, and embed/thumbnail dimensions.
- Both admin classes subclass orgs' `TenantModelAdmin`, so each organization curates its own
  records.

Services (`quickscale_modules_social.services`):

- `list_published_social_links()` returns the published links, allowlist-filtered and capped.
- `list_published_social_embeds()` returns the published embeds, allowlist- and
  embed-capability-filtered and capped.
- `build_social_link_tree_payload()` and `build_social_embeds_payload()` build the JSON payloads
  the public pages and integration endpoints serve.
- `organization_cache_keys(organization_id)` returns the module's organization-scoped cache keys;
  the orgs purge collects it through the `organization_cache_keys` AppConfig capability and clears
  every key without knowing their shapes.
- Payloads are cached under `quickscale_social:` keys, partitioned per organization, with the
  configured TTL; save and delete invalidate the bare and affected organization keys.

Link-tree payload shape:

```json
{
  "module": "social",
  "surface": "link_tree",
  "status": "enabled",
  "enabled": true,
  "public_path": "/social",
  "integration_base_path": "/_quickscale/social/",
  "integration_embeds_path": "/_quickscale/social/embeds/",
  "provider_allowlist": ["facebook", "instagram", "linkedin", "tiktok", "x", "youtube"],
  "embed_provider_allowlist": ["tiktok", "youtube"],
  "layout_variant": "cards",
  "links_per_page": 24,
  "total_links": 1,
  "links": [
    {
      "id": 1,
      "title": "QuickScale on YouTube",
      "description": "Launch clips and demos.",
      "provider_name": "youtube",
      "provider_display_name": "YouTube",
      "url": "https://www.youtube.com/watch?v=abc123",
      "source_url": "https://youtu.be/abc123?si=share",
      "display_order": 10
    }
  ],
  "error": null
}
```

Embed payload additions:

```json
{
  "id": 2,
  "title": "QuickScale launch clip",
  "provider_name": "youtube",
  "provider_display_name": "YouTube",
  "url": "https://www.youtube.com/shorts/alpha123",
  "source_url": "https://www.youtube.com/shorts/alpha123",
  "display_order": 10,
  "resolution_status": "resolved",
  "resolution_error": null,
  "embed_url": "https://www.youtube.com/embed/alpha123?rel=0",
  "thumbnail_url": "https://i.ytimg.com/vi/alpha123/hqdefault.jpg",
  "embed_width": 560,
  "embed_height": 315,
  "thumbnail_width": 480,
  "thumbnail_height": 360,
  "last_resolution_attempt_at": "2026-04-02T10:00:00+00:00",
  "last_resolved_at": "2026-04-02T10:00:00+00:00"
}
```

Supported providers:

- Link tree: the default allowlist is `facebook`, `instagram`, `linkedin`, `tiktok`, `x`, and
  `youtube`.
- Embeds: only `youtube` and `tiktok` support inline preview metadata.
- TikTok: a canonical `/video/<id>` URL is required for inline preview metadata. Short
  `vm.tiktok.com` URLs stay stored and operator-visible, but they surface a resolution error
  until a canonical video URL is saved.

## URLs

The module ships no URLconf or views: it stays HTTP-free. The generated project owns the public
URL wiring:

- Fixed public pages: `/social` and `/social/embeds` (fresh `showcase_react` generations), served
  by Django template wrappers that hydrate the shared React bundle.
- Managed JSON endpoints: `/_quickscale/social/` and `/_quickscale/social/embeds/`, rendered
  into the generated project's managed wiring and backed by the module services. The mount
  (`_quickscale/social/`) is declared in the module's manifest `url_includes` entry, and the
  managed URLconf names its routes `link_tree` and `embeds`.

## Management commands

This module ships no management commands.

## Operations

- Django admin is the authoritative curation surface; public CRUD is intentionally out of
  scope.
- Runtime configuration remains in generated settings and `quickscale.yml`; the database stores
  curated records and embed-resolution metadata, not a second mutable config surface.
- Social payloads are cached with the configured TTL, and unchanged embeds do not blindly
  re-resolve on every save.
- Unresolved embeds do not crash page rendering: the public payload exposes explicit resolution
  state and error details so the React UI can fall back cleanly.
- The module never ships provider write APIs, OAuth, inbox or reply flows, or arbitrary
  third-party embed HTML as the primary render contract.

## Extending

- The public pages consume the payload endpoints through the `window.__QUICKSCALE__` seam; a
  project that wants to change the presentation adopts the social page templates and frontend
  files rather than editing module source.
- Related documentation: [roadmap](../../docs/technical/roadmap.md),
  [changelog](../../CHANGELOG.md), and the [module workspace README](../README.md).
