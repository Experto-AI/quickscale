# QuickScale Listings Module

Generic listings module for Django projects with filtering, search, and an abstract base model
for marketplace verticals (real estate, jobs, events, products).

## Overview

- `AbstractListing`: an extensible base model for marketplace listings.
- A concrete `Listing` model that the shipped views, URLs, and admin target out of the box.
- Rich listing fields: title, slug, description, price, location, status, and featured image.
- Filtering by price range, location, and status through django-filter.
- Status lifecycle: draft, published, sold, archived.
- Semantic, zero-style HTML templates and SEO-friendly slugs.
- Tenant-scoped through orgs' `TenantModel`; `orgs` is required alongside `listings`.

Dependencies: Django >= 6.0, Django REST Framework >= 3.17.2, django-filter >= 26.1,
django-markdownx >= 4.0.11, and Pillow >= 12.3.0,<13.0.0.

## Configuration

The module declares the option below in `module.yml`; `quickscale plan` and `quickscale apply`
write it to the generated settings, and `quickscale.yml` carries the desired value.

| Option | Type | Default | Django setting | Description |
|--------|------|---------|----------------|-------------|
| `enabled` | boolean | `true` | `QUICKSCALE_LISTINGS_ENABLED` | Mount the module's pages and API. Off keeps the app, its data, and the admin Markdownx editor (behind a staff check) but serves none of the module's own public URLs. |
| `per_page` | integer | `12` | `QUICKSCALE_LISTINGS_PER_PAGE` | Number of listings per page. |

## Public surface

### AbstractListing model

| Field | Type | Description |
|-------|------|-------------|
| `title` | CharField(200) | Listing title |
| `slug` | SlugField(200) | Auto-generated URL slug |
| `description` | TextField | Plain text description |
| `price` | DecimalField | Price (nullable for "Contact for price") |
| `location` | CharField(200) | Free-text location |
| `status` | CharField | DRAFT, PUBLISHED, SOLD, ARCHIVED |
| `featured_image` | ImageField | Featured image (optional, stored under `listings/images/`) |
| `featured_image_alt` | CharField | Alt text for accessibility |
| `created_at` | DateTimeField | Auto-set on creation |
| `updated_at` | DateTimeField | Auto-set on update |
| `published_date` | DateTimeField | Set when the status becomes PUBLISHED |

### Publish API

`POST listings/api/publish/` creates and publishes a listing from a JSON payload for
authenticated staff users. It is a DRF `APIView` with session authentication only (CSRF is
enforced) and the JSON renderer alone. Every error the view answers takes the shared QuickScale
shape `{"error": {"code", "message", "fields"}}`, produced by
`quickscale_core.runtime.conventions.exception_handler` — the handler `quickscale apply`
installs in `REST_FRAMEWORK` (a manual installation must install it the same way; see
Operations). The organization is ambient: it comes from `request.org` set by orgs'
`TenantMiddleware`; a session naming an organization the user no longer belongs to is refused
by that middleware before the view runs. Requests are validated before creation and answer with
a validation error, or a conflict error when the slug or a unique field already exists.

### Filtering

The list view supports query parameters:

```
/listings/?price_min=100&price_max=500
/listings/?location=New+York
/listings/?status=published
/listings/?price_min=100&price_max=500&location=LA&status=published
```

## URLs

`quickscale apply` mounts the module under `listings/`; the module's paths are:

| URL name | Path | Purpose |
|----------|------|---------|
| `quickscale_listings:listing_list` | `listings/` | Paginated, filterable listing list |
| `quickscale_listings:listing_detail` | `listings/<slug>/` | Listing detail |
| `quickscale_listings:api_publish_listing` | `listings/api/publish/` | Staff publish endpoint (JSON) |

Project-owned verticals typically override the list and detail views with subclasses that set
their own concrete model and mount them under their own paths (for example `properties/`), as
described in [module-extension.md](../../docs/technical/module-extension.md).

## Management commands

This module ships no management commands.

## Operations

Add the module through QuickScale:

```bash
quickscale plan myapp --add listings
cd myapp
quickscale apply
```

`quickscale apply` embeds the module into `modules/listings/`, configures settings and URLs, and
captures the module options in `quickscale.yml`.

A manual installation embeds the orgs baseline first (the models need `quickscale_orgs` and
`TenantMiddleware`), then adds `rest_framework`, `django_filters`, and
`quickscale_modules_listings` to `INSTALLED_APPS`, mounts the module URLs under `listings/`,
installs the shared error handler so module APIs answer the one QuickScale shape, and runs
`python manage.py migrate`. Compose the handler into whatever `REST_FRAMEWORK` configuration
the project already has — other modules contribute keys such as their throttle rates, and
replacing the dict drops them:

```python
REST_FRAMEWORK = dict(globals().get("REST_FRAMEWORK", {}))
REST_FRAMEWORK.setdefault(
    "EXCEPTION_HANDLER",
    "quickscale_core.runtime.conventions.exception_handler",
)
```

Template customization: all templates extend `quickscale_listings/base.html`.
Override the base at `templates/quickscale_listings/base.html` or individual pages at
`templates/quickscale_listings/listings/<page>.html`. The module ships zero-style semantic
templates; add your own CSS in the project.

## Extending

Create vertical-specific listings by subclassing `AbstractListing`:

```python
from django.db import models

from quickscale_modules_listings.models import AbstractListing


class PropertyListing(AbstractListing):
    """Real estate property listing"""

    bedrooms = models.IntegerField(default=0)
    bathrooms = models.IntegerField(default=0)
    square_feet = models.IntegerField(default=0)

    class Meta(AbstractListing.Meta):
        abstract = False
        verbose_name = "Property Listing"
        verbose_name_plural = "Property Listings"
```

Then run `python manage.py makemigrations myapp && python manage.py migrate`, and point project
views, URLs, filters, and admin registration at the concrete model. The
[module extension guide](../../docs/technical/module-extension.md) documents project-owned
tenant models, their provider-ID classification, and the RLS boundary they inherit.

- **Development**: `make MODULE=listings test -- --modules` from the repository root; Ruff and
  MyPy run through the repository's shared configuration.
- **License**: Apache 2.0, see the LICENSE file for details.
- **Support and contributions**: [GitHub Issues](https://github.com/Experto-AI/quickscale/issues),
  the [QuickScale documentation](https://github.com/Experto-AI/quickscale), and CONTRIBUTING.md.
