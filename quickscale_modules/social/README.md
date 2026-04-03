# QuickScale Social Module

Curated social links and embeds for QuickScale-generated projects.

This README documents the current main-branch v0.79.0 social implementation. Repository SSOT still lives in [../../README.md](../../README.md), [../../docs/technical/decisions.md](../../docs/technical/decisions.md), and [../../docs/technical/roadmap.md](../../docs/technical/roadmap.md).

## What Ships In v0.79.0

- An installable Django app with `SocialLink` and `SocialEmbed` models, migrations, admin registration, and package-local pytest coverage.
- Theme-agnostic runtime services that expose normalized read-only payloads for curated link-tree and embed surfaces.
- Backend-owned embed preview metadata for YouTube and TikTok, including persisted resolution status, timestamps, and operator-visible errors.
- Generated-project-managed JSON endpoints at `/_quickscale/social/` and `/_quickscale/social/embeds/` backed by module services instead of module-owned HTTP APIs.
- Fresh `showcase_react` public pages at `/social` and `/social/embeds`, with existing generated projects staying backend-only unless the theme files are adopted manually.

## Support Matrix

- Existing generated projects: `quickscale apply` adds backend-managed settings, admin/runtime wiring, and the generated-project integration endpoints, but it does not rewrite user-owned `showcase_react` routes, navigation, templates, or page source.
- Fresh `showcase_react` generations: get the full backend plus React public experience, including Django-owned `/social` and `/social/embeds` pages hydrated by the shared React bundle.
- Older projects that want the React UX: manually adopt the `showcase_react` social page templates and frontend files after backend wiring is in place.

## Configuration Surface

The planner-owned config stays authoritative in generated settings and `quickscale.yml`.

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

Supported mutable keys come from [module.yml](./module.yml):

- `link_tree_enabled`
- `layout_variant` (`list`, `cards`, `grid`)
- `embeds_enabled`
- `provider_allowlist`
- `cache_ttl_seconds`
- `links_per_page`
- `embeds_per_page`

## Public Surfaces

- Fixed public routes: `/social` and `/social/embeds`
- Managed JSON endpoints: `/_quickscale/social/` and `/_quickscale/social/embeds/`
- Module package boundary: the package stays HTTP-free; generated projects own the public URL wiring and JSON views.

### Link-tree payload shape

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

### Embed payload additions

Embed records extend the base contract with backend-owned preview metadata:

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

## Supported Providers

- Link tree: default allowlist is `facebook`, `instagram`, `linkedin`, `tiktok`, `x`, and `youtube`.
- Embeds: v0.79.0 supports only `youtube` and `tiktok` for inline preview metadata.
- TikTok note: a canonical `/video/<id>` URL is required for inline preview metadata. Short `vm.tiktok.com` URLs stay stored and operator-visible, but they surface a resolution error until a canonical video URL is saved.

## Operator Notes

- Django admin is the authoritative curation surface in v0.79.0; public CRUD is intentionally out of scope.
- Runtime configuration remains in generated settings and `quickscale.yml`; the database stores curated records and embed-resolution metadata, not a second mutable config surface.
- Social payloads are cached with the configured TTL, and unchanged embeds do not blindly re-resolve on every save.
- Unresolved embeds do not crash page rendering. The public payload exposes explicit resolution state and error details so the React UI can fall back cleanly.
- The module never ships provider write APIs, OAuth, inbox or reply flows, or arbitrary third-party embed HTML as the primary render contract.

## Related Docs

- [Roadmap entry](../../docs/technical/roadmap.md)
- [Changelog](../../CHANGELOG.md)
- Official v0.79.0 public release note: pending until the tagged release is cut in `docs/releases/`
- [Maintainer module index](../README.md)
