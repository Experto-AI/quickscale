# QuickScale CRM Module

A lightweight CRM module for QuickScale projects, providing contact management, company tracking, and deal pipeline functionality.

## Features

- **7 Core Models**: Tag, Company, Contact, Stage, Deal, ContactNote, DealNote
- **RESTful API**: Session-authenticated CRUD operations with Django REST Framework
- **Deal Pipeline**: Configurable stages with probability tracking
- **Bulk Operations**: Update multiple deals at once
- **Django Admin**: Full admin interface with inlines
- **Filtering & Search**: Built-in filtering for all endpoints

## Installation

### Using QuickScale CLI

```bash
quickscale plan --add crm
quickscale apply
```

### Manual Installation

Add to your project's `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    'rest_framework',
    'django_filters',
    'quickscale_modules_crm',
]
```

Run migrations:

```bash
python manage.py migrate quickscale_modules_crm
```

Add URL patterns:

```python
urlpatterns = [
    # ...
    path('crm/', include('quickscale_modules_crm.urls')),
]
```

## Configuration

The module supports the following configuration options in `module.yml`:

### Mutable Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable_api` | boolean | `true` | Enable/disable the authenticated CRM API endpoints |
| `deals_per_page` | integer | `25` | Number of deals returned per page from the CRM deals API |
| `contacts_per_page` | integer | `50` | Number of contacts returned per page from the CRM contacts API |

Terminal won/lost stages are managed internally through hidden stage semantics.
Stage CRUD stays editable through the admin and API, and the bulk `mark-won` /
`mark-lost` actions recreate canonical terminal rows if older data snapshots no
longer have a semantic terminal stage.

## API Endpoints

All authenticated API endpoints are available under `/crm/api/` when `CRM_ENABLE_API=True`:

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/crm/api/tags/` | GET, POST | List/create tags |
| `/crm/api/tags/{id}/` | GET, PUT, PATCH, DELETE | Tag detail |
| `/crm/api/companies/` | GET, POST | List/create companies |
| `/crm/api/companies/{id}/` | GET, PUT, PATCH, DELETE | Company detail |
| `/crm/api/contacts/` | GET, POST | List/create contacts |
| `/crm/api/contacts/{id}/` | GET, PUT, PATCH, DELETE | Contact detail |
| `/crm/api/contacts/{id}/notes/` | GET, POST | List/create contact notes |
| `/crm/api/stages/` | GET, POST | List/create stages |
| `/crm/api/stages/{id}/` | GET, PUT, PATCH, DELETE | Stage detail |
| `/crm/api/deals/` | GET, POST | List/create deals |
| `/crm/api/deals/{id}/` | GET, PUT, PATCH, DELETE | Deal detail |
| `/crm/api/deals/{id}/notes/` | GET, POST | List/create deal notes |
| `/crm/api/deals/bulk-update-stage/` | POST | Bulk update deal stages |
| `/crm/api/deals/mark-won/` | POST | Mark deals as won |
| `/crm/api/deals/mark-lost/` | POST | Mark deals as lost |
| `/crm/api/contact-notes/` | GET, POST | List/create contact notes |
| `/crm/api/contact-notes/{id}/` | GET, PUT, PATCH, DELETE | Contact note detail |
| `/crm/api/deal-notes/` | GET, POST | List/create deal notes |
| `/crm/api/deal-notes/{id}/` | GET, PUT, PATCH, DELETE | Deal note detail |

All CRM API endpoints use session authentication and require an authenticated user. When `CRM_ENABLE_API=False`, the `/crm/api/` endpoints return `404` while the module dashboard remains available at `/crm/`.

### Filtering

Contacts can be filtered by:
- `status`: Filter by contact status
- `company`: Filter by company ID
- `tags`: Filter by tag IDs

Deals can be filtered by:
- `stage`: Filter by stage ID
- `status`: Filter by deal status (open/won/lost)
- `owner`: Filter by owner user ID
- `company`: Filter by company ID

### Search

Contacts support search on: `first_name`, `last_name`, `email`, `company__name`

Deals support search on: `title`, `company__name`

## Models

### Tag
Simple tagging for contacts with name and color.

### Company
Company records with name and optional website.

### Contact
Contact records with:
- First name, last name, email, phone
- Status (lead/active/inactive)
- Optional company association
- Multiple tags support
- `last_contacted_at` automatically updated when a contact note is created

### Stage
Pipeline stages with name and order for sequencing. Terminal won/lost semantics
are tracked internally and are not part of the public config surface.

### Deal
Deal records with:
- Title and optional description
- Value (monetary amount)
- Probability (0-100%)
- Status (open/won/lost)
- Stage and company associations
- Owner (user who owns the deal)

### ContactNote / DealNote
Notes attached to contacts or deals with created_by tracking.

## Development

### Running Tests

```bash
cd quickscale_modules/crm
poetry install
poetry run pytest
```

### Code Quality

```bash
poetry run ruff check .
poetry run mypy src/
```

## License

Apache 2.0 License - see the main QuickScale project for details.

## Version

0.73.0
