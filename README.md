# QuickScale Blog Module

Production-ready blog module for Django projects with Markdown support, featured images,
categories, tags, and optional RSS feeds.

## Overview

- Markdown editing through django-markdownx.
- Rich post model: title, slug, content, excerpt, featured image, and draft/published status.
- Categories and tags for content classification.
- Author profiles with bio and avatar.
- Featured images with generated thumbnails.
- A two-step automation API: upload images over HTTP, then publish Markdown posts with a
  featured-image reference.
- An RSS feed of the latest 20 published posts when enabled.
- Semantic, zero-style HTML templates and SEO-friendly slugs.
- Tenant-scoped through orgs' `TenantModel`; `orgs` is required alongside `blog`.

Dependencies: Django >= 6.0, djangorestframework >= 3.17.2, django-markdownx >= 4.0.11, and
Pillow >= 12.3.0,<13.0.0.

## Configuration

The module declares the options below in `module.yml`; `quickscale plan` and `quickscale apply`
write them to the generated settings, and `quickscale.yml` carries the desired values.

| Option | Type | Default | Django setting | Description |
|--------|------|---------|----------------|-------------|
| `enabled` | boolean | `true` | `QUICKSCALE_BLOG_ENABLED` | Mount the module's pages, API, and RSS routes. Off keeps the app, its data, and the admin Markdownx editor (behind a staff check) but serves none of the module's own public URLs. |
| `posts_per_page` | integer | `10` | `QUICKSCALE_BLOG_POSTS_PER_PAGE` | Number of posts per page. |
| `api_rate_limit` | string | `5/hour` | `QUICKSCALE_BLOG_API_RATE_LIMIT` | Throttle rate for authenticated blog API requests, per IP. Format: `<count>/<period>`. |
| `rss_enabled` | boolean | `true` | `QUICKSCALE_BLOG_RSS_ENABLED` | Enable the RSS route at runtime. |
| `api_upload_max_bytes` | integer | `10485760` | `QUICKSCALE_BLOG_API_UPLOAD_MAX_BYTES` | Maximum accepted media-upload size in bytes. |
| `api_upload_max_width` | integer | `4096` | `QUICKSCALE_BLOG_API_UPLOAD_MAX_WIDTH` | Maximum accepted media-upload image width in pixels. |
| `api_upload_max_height` | integer | `4096` | `QUICKSCALE_BLOG_API_UPLOAD_MAX_HEIGHT` | Maximum accepted media-upload image height in pixels. |
| `api_allowed_image_formats` | list | `["PNG", "JPEG", "WEBP", "GIF"]` | `QUICKSCALE_BLOG_API_ALLOWED_IMAGE_FORMATS` | Image formats accepted by the media-upload API. |

Additional Django settings configure the editor and the shared error shape:

```python
MARKDOWNX_MARKDOWN_EXTENSIONS = [
    "markdown.extensions.fenced_code",
    "markdown.extensions.tables",
    "markdown.extensions.toc",
]
MARKDOWNX_MEDIA_PATH = "blog/markdownx/"
MARKDOWNX_UPLOAD_MAX_SIZE = 5 * 1024 * 1024
MARKDOWNX_IMAGE_MAX_SIZE = {"size": (1920, 1080), "quality": 90}

# DRF: the shared error shape and the blog API throttle scope
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "quickscale_core.runtime.conventions.exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "quickscale_blog_api": QUICKSCALE_BLOG_API_RATE_LIMIT,
    },
}
```

## Public surface

Models: `Post`, `Category`, `Tag`, `AuthorProfile`, and `BlogMediaAsset`, the stored
image-upload asset the automation flow references. The models are registered in the Django
admin with Markdown editing support.

### Automation API

The two-step automation flow is:

1. Upload each image with `POST blog/api/media/`.
2. Rewrite Markdown image links to the returned URLs.
3. Publish the post with `POST blog/api/publish/`.

Both endpoints accept a staff session with CSRF; the DRF throttle (`quickscale_blog_api`, its
rate from `QUICKSCALE_BLOG_API_RATE_LIMIT`) applies after authentication and permissions. Media upload
accepts `multipart/form-data` with `file` (required), `alt`, and `kind`
(`inline`, `featured`, or `general`), and enforces `QUICKSCALE_BLOG_API_UPLOAD_MAX_BYTES`, the allowed
image formats, `QUICKSCALE_BLOG_API_UPLOAD_MAX_WIDTH`, and `QUICKSCALE_BLOG_API_UPLOAD_MAX_HEIGHT`. Publish accepts
`application/json` with `title` and `content` (required), and optional `excerpt`,
`category_slug`, `tags`, `featured_image_id`, and `featured_image_alt`. The publish response
returns the post `id`, `slug`, `url`, and `status`.

Automation clients sign in as a staff user and send the session cookie with the CSRF token; the
former bearer-token scheme (`BLOG_API_TOKENS`) is removed.

### RSS feed

The default `blog/feed/` route exists only when `QUICKSCALE_BLOG_RSS_ENABLED` is true; it publishes the
latest 20 published posts with full metadata.

## URLs

`quickscale apply` mounts the module at `blog/` (its manifest `url_includes` entry); the
module's routes are:

| URL name | Path | Purpose |
|----------|------|---------|
| `quickscale_blog:post_list` | `blog/` | Paginated post list |
| `quickscale_blog:post_detail` | `blog/post/<slug>/` | Post detail |
| `quickscale_blog:category_list` | `blog/category/<slug>/` | Posts by category |
| `quickscale_blog:tag_list` | `blog/tag/<slug>/` | Posts by tag |
| `quickscale_blog:feed` | `blog/feed/` | RSS feed when `QUICKSCALE_BLOG_RSS_ENABLED` is true |
| `quickscale_blog:api_upload_media` | `blog/api/media/` | Staff image upload for the automation API |
| `quickscale_blog:api_publish_post` | `blog/api/publish/` | Staff publish endpoint for Markdown posts |

There are no `/orgs/<slug>/blog/...` paths: the active organization is resolved from
`request.org` at runtime (the System organization for anonymous readers, the session or personal
organization for authenticated readers).

## Management commands

This module ships no management commands.

## Operations

Add the module through QuickScale:

```bash
quickscale plan myapp --add blog
cd myapp
quickscale apply
```

`quickscale apply` embeds the module into `modules/blog/`, configures settings and URLs, and
captures the module options in `quickscale.yml`.

A manual installation embeds the orgs baseline first, then adds `rest_framework`, `markdownx`,
`quickscale_modules_orgs`, and `quickscale_modules_blog` to `INSTALLED_APPS`, adds
`quickscale_modules_orgs.middleware.TenantMiddleware` after the session and authentication
middleware, sets the required `MEDIA_URL` (non-trivial) and `QUICKSCALE_BLOG_RSS_ENABLED` settings,
configures Markdownx and DRF (the shared error handler and the `quickscale_blog_api` throttle
rate shown under Configuration), mounts the module at `blog/` with the staff-guarded Markdownx
editor include, and runs `python manage.py migrate quickscale_blog` plus
`python manage.py collectstatic`.

```python
urlpatterns = [
    path("blog/", include("quickscale_modules_blog.urls")),
    path("markdownx/", include("quickscale_modules_blog.markdownx_urls")),
]
```

Creating posts:

- Through the Django admin: create categories and tags, then a post with Markdown content and
  an optional featured image, and set its status to published.
- Programmatically: import `Post`, `Category`, and `Tag`; public content uses the System
  organization (`Organization.objects.get_system_org()`), while tenant-scoped content uses
  `request.org` set by `TenantMiddleware`.

Template customization: all templates extend `quickscale_blog/base.html`. Override the
base at `templates/quickscale_blog/base.html` or individual pages at
`templates/quickscale_blog/blog/<page>.html`. The module ships zero-style semantic templates;
add your own CSS in the project.

Troubleshooting:

- **"No such table: quickscale_blog_post"** — run `python manage.py migrate quickscale_blog`.
- **Markdown not rendering** — ensure `markdownx` is in `INSTALLED_APPS` and use
  `{% load markdownx %}` with `{{ post.content|markdownify }}`.
- **Images not uploading** — check `MEDIA_URL`, `MEDIA_ROOT`, and the development media route.
- **Thumbnails not generating** — ensure Pillow is installed.
- **RSS feed not validating** — ensure posts have `published_date` set and status published.

## Extending

- **Model extension**: subclass `Post` (a proxy model works when no extra columns are needed)
  and register the subclass in the admin with `MarkdownxModelAdmin`.
- **RSS customization**: subclass `quickscale_modules_blog.feeds.LatestPostsFeed`, override its
  `title`, `description`, or `items()`, and mount your class at `blog/feed/` under the
  `QUICKSCALE_BLOG_RSS_ENABLED` gate.
- **Development**: `make MODULE=blog test -- --modules` from the repository root; Ruff and MyPy
  run through the repository's shared configuration.
- **License**: Apache 2.0, see the LICENSE file for details.
- **Support and contributions**: [GitHub Issues](https://github.com/Experto-AI/quickscale/issues),
  the [QuickScale documentation](https://github.com/Experto-AI/quickscale), and CONTRIBUTING.md.
