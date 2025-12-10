# Release v0.73.0 - CRM Module

**Release Date:** TBD (when merged)

## Overview

This release introduces the QuickScale CRM Module, a lightweight Django CRM providing reusable data structures for contacts, companies, deals, and notes. The module follows the theme-agnostic backend with API-first design established in the [crm-proposal.md](../../crm-proposal.md).

## Key Features

### 7 Core Models

| Model | Description |
|-------|-------------|
| **Tag** | Generic tags for segmenting contacts and deals |
| **Company** | Organization entities with industry and website |
| **Contact** | Contact persons with status tracking, company association, tags |
| **Stage** | Pipeline stages with ordering (default: Prospecting, Negotiation, Closed-Won, Closed-Lost) |
| **Deal** | Sales opportunities with amount, probability, owner, pipeline stages |
| **ContactNote** | Notes attached to contacts with created_by tracking |
| **DealNote** | Notes attached to deals with created_by tracking |

### RESTful API (Django REST Framework)

- Full CRUD operations for all 7 models
- Filtering and search capabilities
- Nested routes for notes (`/contacts/{id}/notes/`, `/deals/{id}/notes/`)
- Bulk operations (`mark_won`, `mark_lost`, `bulk_update_stage`)
- Browsable API at `/api/crm/`

### Django Admin

- Complete admin interface for all models
- Inline editing for notes (ContactNoteInline, DealNoteInline)
- List-editable stage ordering
- Filter horizontal for tags

### CLI Integration

- Added 'crm' to available modules
- `configure_crm_module()` for configuration
- `apply_crm_configuration()` for auto-setup:
  - Adds `djangorestframework` and `django-filter` dependencies
  - Configures INSTALLED_APPS
  - Sets up CRM API URLs

## Installation

```bash
quickscale plan myproject --add crm
quickscale apply
```

Or manually:

```bash
cd myproject
poetry add ./modules/crm
python manage.py migrate quickscale_modules_crm
```

## API Endpoints

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/crm/tags/` | GET, POST | List/create tags |
| `/api/crm/companies/` | GET, POST | List/create companies |
| `/api/crm/contacts/` | GET, POST | List/create contacts |
| `/api/crm/contacts/{id}/notes/` | GET, POST | Contact notes |
| `/api/crm/stages/` | GET, POST | List/create stages |
| `/api/crm/deals/` | GET, POST | List/create deals |
| `/api/crm/deals/{id}/notes/` | GET, POST | Deal notes |
| `/api/crm/deals/bulk_update_stage/` | POST | Bulk stage update |
| `/api/crm/deals/mark_won/` | POST | Mark deals as won |
| `/api/crm/deals/mark_lost/` | POST | Mark deals as lost |

## Configuration

The module supports configuration via `module.yml`:

### Mutable Options
- `enable_api`: Enable/disable REST API (default: true)
- `deals_per_page`: Pagination for deals (default: 25)
- `contacts_per_page`: Pagination for contacts (default: 50)

### Immutable Options
- `default_pipeline_stages`: Initial stages created on migration

## Testing

- **67 tests** covering models, serializers, views, and admin
- **97.38% code coverage** (exceeds 70% minimum)
- All tests pass in 28.28s

## Technical Details

### Dependencies
- Django ^6.0
- djangorestframework ^3.15.0
- django-filter ^24.0

### Files Created
- `quickscale_modules/crm/` - Complete module package
- Package structure follows established patterns from auth/blog/listings modules

### Integration Points
- `quickscale_cli/commands/module_commands.py` - Added 'crm' to AVAILABLE_MODULES
- `quickscale_cli/commands/module_config.py` - CRM configurator functions
- `pyproject.toml` - Module registered for development
- `mypy.ini` - Type checking configuration
- `ruff.toml` - Linting configuration updated

## Breaking Changes

None. This is a new module that doesn't affect existing functionality.

## Deferred Items

The following items are deferred to v0.74.0 (CRM Theme):
- Template integration with showcase_html theme
- Navigation updates for CRM section
- Basic contact/deal listing templates

## Migration Notes

The initial migration (`0001_initial.py`) creates default pipeline stages:
- Prospecting (order: 1)
- Negotiation (order: 2)
- Closed-Won (order: 3)
- Closed-Lost (order: 4)

These can be customized via Django admin after installation.

## Contributors

- Automated implementation following CRM proposal and roadmap specifications

## Related Documentation

- [CRM Proposal](../../crm-proposal.md) - Research and architecture decisions
- [Roadmap v0.73.0](../technical/roadmap.md#v0730-quickscale_modulescrm---crm-module) - Implementation checklist
- [Module README](../../quickscale_modules/crm/README.md) - Usage documentation
