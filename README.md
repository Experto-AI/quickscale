# QuickScale CRM Module

A lightweight CRM module for QuickScale projects, providing contact management, company tracking, and deal pipeline functionality.

## Features

- **7 Core Models**: Tag, Company, Contact, Stage, Deal, ContactNote, DealNote
- **RESTful API**: Full CRUD operations with Django REST Framework
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
    path('api/crm/', include('quickscale_modules_crm.urls')),
]
```

## Configuration

The module supports the following configuration options in `module.yml`:

### Mutable Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable_api` | boolean | `true` | Enable/disable REST API endpoints |
| `deals_per_page` | integer | `25` | Number of deals per page in list views |
| `contacts_per_page` | integer | `50` | Number of contacts per page in list views |

### Immutable Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `default_pipeline_stages` | list | See below | Initial pipeline stages created on migration |

Default pipeline stages:
- Prospecting (order: 1)
- Negotiation (order: 2)
- Closed-Won (order: 3)
- Closed-Lost (order: 4)

## API Endpoints

All endpoints are available under `/api/crm/`:

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/crm/tags/` | GET, POST | List/create tags |
| `/api/crm/tags/{id}/` | GET, PUT, PATCH, DELETE | Tag detail |
| `/api/crm/companies/` | GET, POST | List/create companies |
| `/api/crm/companies/{id}/` | GET, PUT, PATCH, DELETE | Company detail |
| `/api/crm/contacts/` | GET, POST | List/create contacts |
| `/api/crm/contacts/{id}/` | GET, PUT, PATCH, DELETE | Contact detail |
| `/api/crm/contacts/{id}/notes/` | GET | Contact notes |
| `/api/crm/stages/` | GET, POST | List/create stages |
| `/api/crm/stages/{id}/` | GET, PUT, PATCH, DELETE | Stage detail |
| `/api/crm/deals/` | GET, POST | List/create deals |
| `/api/crm/deals/{id}/` | GET, PUT, PATCH, DELETE | Deal detail |
| `/api/crm/deals/{id}/notes/` | GET | Deal notes |
| `/api/crm/deals/bulk_update_stage/` | POST | Bulk update deal stages |
| `/api/crm/deals/mark_won/` | POST | Mark deals as won |
| `/api/crm/deals/mark_lost/` | POST | Mark deals as lost |
| `/api/crm/contact-notes/` | GET, POST | List/create contact notes |
| `/api/crm/contact-notes/{id}/` | GET, PUT, PATCH, DELETE | Contact note detail |
| `/api/crm/deal-notes/` | GET, POST | List/create deal notes |
| `/api/crm/deal-notes/{id}/` | GET, PUT, PATCH, DELETE | Deal note detail |

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

### Stage
Pipeline stages with name and order for sequencing.

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
