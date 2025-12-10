# QuickScale Blog Module

Production-ready blog module for Django projects with Markdown support, featured images, categories, tags, and RSS feeds.

## Features

### ✅ Implemented (v0.66.0)

- **Markdown Editor Integration**: WYSIWYG Markdown editing with django-markdownx
- **Rich Post Model**: Title, slug, content, excerpt, featured image, status (draft/published)
- **Organization**: Categories and tags for content classification
- **Author Profiles**: Extended user profiles with bio and avatar
- **Featured Images**: Auto-generated thumbnails (300x200, 800x450)
- **RSS Feed**: Latest 20 published posts with full metadata
- **Zero-Style Templates**: Semantic HTML base templates (no CSS classes)
- **Pagination**: 10 posts per page (configurable)
- **SEO-Friendly**: Slugs, meta tags, semantic HTML structure

## Installation

### Via QuickScale CLI (Recommended)

```bash
quickscale embed --module blog
```

This will:
- Embed the blog module into your project's `modules/blog/` directory
- Configure `settings.py` with required settings
- Add blog URLs to your `urls.py`
- Prompt for configuration options

### Configuration Options

During embed, you'll be prompted for:

1. **Posts per page** (default: 10)
2. **Excerpt length** (default: 300 characters)
3. **Enable categories/tags** (default: yes)
4. **Enable RSS feed** (default: yes)

### Manual Installation

If embedding manually:

1. Add to `INSTALLED_APPS` in `settings.py`:
   ```python
   INSTALLED_APPS = [
       # ... other apps
       'markdownx',
       'quickscale_modules_blog',
   ]
   ```

2. Configure Markdownx in `settings.py`:
   ```python
   # Markdownx settings
   MARKDOWNX_MARKDOWN_EXTENSIONS = [
       'markdown.extensions.fenced_code',
       'markdown.extensions.tables',
       'markdown.extensions.toc',
   ]
   MARKDOWNX_MEDIA_PATH = 'blog/markdownx/'
   ```

3. Add blog URLs to `urls.py`:
   ```python
   from django.urls import include, path

   urlpatterns = [
       # ... other patterns
       path('blog/', include('quickscale_modules_blog.urls')),
   ]
   ```

4. Run migrations:
   ```bash
   python manage.py migrate quickscale_modules_blog
   ```

5. Collect static files:
   ```bash
   python manage.py collectstatic
   ```

## Usage

### Available URLs

After embedding, these URLs are available:

- `/blog/` - Post list (paginated)
- `/blog/post/<slug>/` - Post detail
- `/blog/category/<slug>/` - Posts by category
- `/blog/tag/<slug>/` - Posts by tag
- `/blog/feed/` - RSS feed

### Creating Posts

#### Via Django Admin

1. Access the Django admin at `/admin/`
2. Navigate to "Blog" section
3. Create categories and tags (optional)
4. Create a new post:
   - Add title (slug auto-generated)
   - Write content in Markdown
   - Upload featured image (optional)
   - Select category and tags (optional)
   - Set status to "Published"
5. Save the post

#### Programmatically

```python
from django.contrib.auth import get_user_model
from quickscale_modules_blog.models import Post, Category, Tag

User = get_user_model()
user = User.objects.first()

# Create a category
category = Category.objects.create(
    name="Technology",
    description="Posts about technology"
)

# Create tags
tag1 = Tag.objects.create(name="Python")
tag2 = Tag.objects.create(name="Django")

# Create a post
post = Post.objects.create(
    title="Getting Started with Django",
    author=user,
    content="# Introduction\n\nDjango is a powerful web framework...",
    excerpt="Learn the basics of Django development",
    status="published",
    category=category,
)
post.tags.add(tag1, tag2)
```

### Template Customization

All templates extend `quickscale_modules_blog/blog/base.html`. To customize:

1. **Override the base template** in your project:
   ```
   templates/quickscale_modules_blog/blog/base.html
   ```

2. **Override individual templates**:
   ```
   templates/quickscale_modules_blog/blog/post_list.html
   templates/quickscale_modules_blog/blog/post_detail.html
   templates/quickscale_modules_blog/blog/category_list.html
   templates/quickscale_modules_blog/blog/tag_list.html
   ```

3. **Example: Extending base template**:
   ```django
   {% extends "base.html" %}  {# Your project's base template #}

   {% block content %}
       {% block blog_content %}{% endblock %}
   {% endblock %}
   ```

### Styling

The module provides zero-style semantic HTML templates. To add styling:

1. **Create theme-specific CSS**:
   ```css
   /* static/css/blog.css */
   .blog-post {
       margin-bottom: 2rem;
   }

   .blog-post h2 {
       font-size: 2rem;
       margin-bottom: 1rem;
   }

   .blog-post img {
       max-width: 100%;
       height: auto;
   }
   ```

2. **Include in your base template**:
   ```django
   {% block extra_css %}
       <link rel="stylesheet" href="{% static 'css/blog.css' %}">
   {% endblock %}
   ```

### Model Extension

To add custom fields to the Post model:

1. **Create a custom model** that extends Post:
   ```python
   # myapp/models.py
   from quickscale_modules_blog.models import Post

   class RealEstatePost(Post):
       property_price = models.DecimalField(max_digits=10, decimal_places=2)
       bedrooms = models.IntegerField()
       bathrooms = models.IntegerField()

       class Meta:
           proxy = True  # Use proxy if no additional DB fields
   ```

2. **Register in admin**:
   ```python
   # myapp/admin.py
   from django.contrib import admin
   from markdownx.admin import MarkdownxModelAdmin
   from .models import RealEstatePost

   @admin.register(RealEstatePost)
   class RealEstatePostAdmin(MarkdownxModelAdmin):
       list_display = ['title', 'property_price', 'bedrooms', 'bathrooms']
   ```

### RSS Feed Customization

To customize the RSS feed:

```python
# myproject/feeds.py
from quickscale_modules_blog.feeds import LatestPostsFeed

class CustomBlogFeed(LatestPostsFeed):
    title = "My Custom Blog Feed"
    description = "Custom description"

    def items(self):
        # Return 50 posts instead of 20
        return Post.objects.filter(status="published").order_by("-published_date")[:50]
```

Then update your urls.py:
```python
from myproject.feeds import CustomBlogFeed

urlpatterns = [
    path('blog/feed/', CustomBlogFeed(), name='feed'),
]
```

## Configuration Reference

### Settings

Add these to your `settings.py` to customize blog behavior:

```python
# Blog pagination
BLOG_POSTS_PER_PAGE = 10  # Posts per page

# Markdownx configuration
MARKDOWNX_MARKDOWN_EXTENSIONS = [
    'markdown.extensions.fenced_code',  # Code blocks
    'markdown.extensions.tables',       # Tables
    'markdown.extensions.toc',          # Table of contents
    'markdown.extensions.extra',        # Extra features
]

# Image upload settings
MARKDOWNX_MEDIA_PATH = 'blog/markdownx/'
MARKDOWNX_UPLOAD_MAX_SIZE = 5 * 1024 * 1024  # 5MB
MARKDOWNX_IMAGE_MAX_SIZE = {'size': (1920, 1080), 'quality': 90}

# Featured image settings
BLOG_THUMBNAIL_SIZES = {
    'small': (300, 200),
    'medium': (800, 450),
    'large': (1200, 675),
}
```

## Testing

Run module tests:

```bash
cd modules/blog
pytest
```

With coverage:

```bash
pytest --cov=src/quickscale_modules_blog --cov-report=html
```

## Troubleshooting

### Issue: "No such table: quickscale_blog_post"

**Solution**: Run migrations:
```bash
python manage.py migrate quickscale_modules_blog
```

### Issue: Markdown not rendering

**Solution**: Ensure `markdownx` is in INSTALLED_APPS and load the template tag:
```django
{% load markdownx %}
{{ post.content|markdownify }}
```

### Issue: Images not uploading

**Solution**: Check media settings:
```python
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

And ensure your urls.py serves media files in development:
```python
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

### Issue: Thumbnails not generating

**Solution**: Ensure Pillow is installed:
```bash
pip install Pillow
```

### Issue: RSS feed not validating

**Solution**: Ensure posts have `published_date` set and status is "published".

## Development

### Running Tests Locally

```bash
cd quickscale_modules/blog
poetry install
PYTHONPATH=. poetry run pytest
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
- django-markdownx ^4.0.0
- Pillow ^10.0.0

## License

Apache 2.0 License - see LICENSE file for details.

## Support

For issues and questions:
- GitHub Issues: https://github.com/Experto-AI/quickscale/issues
- Documentation: https://github.com/Experto-AI/quickscale

## Contributing

Contributions welcome! See CONTRIBUTING.md for guidelines.
