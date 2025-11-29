# QuickScale Listings Module

Generic listings module for Django projects with filtering, search, and an abstract base model for marketplace verticals (real estate, jobs, events, products).

## Features

### ✅ Implemented (v0.67.0)

- **AbstractListing Model**: Extensible base model for marketplace listings
- **Rich Listing Fields**: Title, slug, description, price, location, status, featured image
- **Filtering System**: Price range, location search, status filters via django-filter
- **Status Management**: Draft, Published, Sold, Archived lifecycle
- **Zero-Style Templates**: Semantic HTML base templates (no CSS classes)
- **Pagination**: 12 listings per page (configurable)
- **SEO-Friendly**: Slugs, meta tags, semantic HTML structure

## Installation

### Via QuickScale CLI (Recommended)

```bash
quickscale embed --module listings
```

This will:
- Embed the listings module into your project's `modules/listings/` directory
- Configure `settings.py` with required settings
- Add listings URLs to your `urls.py`
- Prompt for configuration options

### Manual Installation

If embedding manually:

1. Add to `INSTALLED_APPS` in `settings.py`:
   ```python
   INSTALLED_APPS = [
       # ... other apps
       'django_filters',
       'quickscale_modules_listings',
   ]
   ```

2. Add listings URLs to `urls.py`:
   ```python
   from django.urls import include, path

   urlpatterns = [
       # ... other patterns
       path('listings/', include('quickscale_modules_listings.urls')),
   ]
   ```

3. Create a concrete model extending AbstractListing:
   ```python
   # myapp/models.py
   from quickscale_modules_listings.models import AbstractListing

   class PropertyListing(AbstractListing):
       """Real estate property listing"""
       bedrooms = models.IntegerField(default=0)
       bathrooms = models.IntegerField(default=0)
       square_feet = models.IntegerField(default=0)

       class Meta(AbstractListing.Meta):
           abstract = False
   ```

4. Run migrations:
   ```bash
   python manage.py makemigrations myapp
   python manage.py migrate
   ```

## Usage

### AbstractListing Model

The `AbstractListing` model provides these fields:

| Field | Type | Description |
|-------|------|-------------|
| `title` | CharField(200) | Listing title |
| `slug` | SlugField(200) | Auto-generated URL slug |
| `description` | TextField | Plain text description |
| `price` | DecimalField | Price (nullable for "Contact for price") |
| `location` | CharField(200) | Free-text location |
| `status` | CharField | DRAFT, PUBLISHED, SOLD, ARCHIVED |
| `featured_image` | ImageField | Featured image (optional) |
| `featured_image_alt` | CharField | Alt text for accessibility |
| `created_at` | DateTimeField | Auto-set on creation |
| `updated_at` | DateTimeField | Auto-set on update |
| `published_date` | DateTimeField | Set when status→PUBLISHED |

### Creating Concrete Models

Extend `AbstractListing` to create vertical-specific listings:

```python
from quickscale_modules_listings.models import AbstractListing
from django.db import models

class JobListing(AbstractListing):
    """Job posting listing"""
    company = models.CharField(max_length=200)
    job_type = models.CharField(max_length=50)  # full-time, part-time, contract
    remote = models.BooleanField(default=False)

    class Meta(AbstractListing.Meta):
        abstract = False
        verbose_name = "Job Listing"
        verbose_name_plural = "Job Listings"


class EventListing(AbstractListing):
    """Event listing"""
    event_date = models.DateTimeField()
    venue = models.CharField(max_length=200)
    capacity = models.IntegerField(default=0)

    class Meta(AbstractListing.Meta):
        abstract = False
        verbose_name = "Event"
        verbose_name_plural = "Events"
```

### Available URLs

After embedding, these URLs are available:

- `/listings/` - Listing list (paginated, filterable)
- `/listings/<slug>/` - Listing detail

### Filtering

The list view supports query parameters:

```
/listings/?price_min=100&price_max=500
/listings/?location=New+York
/listings/?status=published
/listings/?price_min=100&price_max=500&location=LA&status=published
```

### Template Customization

All templates extend `quickscale_modules_listings/listings/base.html`. To customize:

1. **Override the base template** in your project:
   ```
   templates/quickscale_modules_listings/listings/base.html
   ```

2. **Override individual templates**:
   ```
   templates/quickscale_modules_listings/listings/listing_list.html
   templates/quickscale_modules_listings/listings/listing_detail.html
   ```

3. **Example: Extending base template**:
   ```django
   {% extends "base.html" %}  {# Your project's base template #}

   {% block content %}
       {% block listings_content %}{% endblock %}
   {% endblock %}
   ```

### Styling

The module provides zero-style semantic HTML templates. To add styling:

1. **Create theme-specific CSS**:
   ```css
   /* static/css/listings.css */
   .listing-item {
       margin-bottom: 2rem;
       border: 1px solid #ddd;
       padding: 1rem;
   }

   .listing-price {
       font-size: 1.5rem;
       font-weight: bold;
       color: #2563eb;
   }
   ```

2. **Include in your base template**:
   ```django
   {% block extra_css %}
       <link rel="stylesheet" href="{% static 'css/listings.css' %}">
   {% endblock %}
   ```

## Configuration Reference

### Settings

Add these to your `settings.py` to customize listings behavior:

```python
# Listings pagination
LISTINGS_PER_PAGE = 12  # Listings per page

# Image upload settings
LISTINGS_UPLOAD_PATH = 'listings/images/'
LISTINGS_IMAGE_MAX_SIZE = {'size': (1920, 1080), 'quality': 90}
```

## Testing

Run module tests:

```bash
cd quickscale_modules/listings
poetry install
poetry run pytest
```

With coverage:

```bash
poetry run pytest --cov=src/quickscale_modules_listings --cov-report=html
```

## Development

### Running Tests Locally

```bash
cd quickscale_modules/listings
poetry install
poetry run pytest
```

### Code Quality

```bash
# Format code
poetry run ruff format src/ tests/

# Check code
poetry run ruff check src/ tests/

# Type check
poetry run mypy src/
```

## Dependencies

- Django >= 5.0
- django-filter ^24.0
- Pillow >= 10.0.0

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- GitHub Issues: https://github.com/Experto-AI/quickscale/issues
- Documentation: https://github.com/Experto-AI/quickscale

## Contributing

Contributions welcome! See CONTRIBUTING.md for guidelines.
