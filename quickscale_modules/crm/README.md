# QuickScale CRM Module

A lightweight CRM module for QuickScale projects, providing contact management, company
tracking, and deal pipeline functionality.

## Overview

- **7 core models**: Tag, Company, Contact, Stage, Deal, ContactNote, DealNote.
- **RESTful API**: session-authenticated, staff-only CRUD operations with Django REST Framework.
- **Deal pipeline**: configurable stages with probability tracking.
- **Bulk operations**: update multiple deals at once.
- **Django admin**: full admin interface with inlines.
- **Filtering and search**: built-in filtering for all endpoints.
- Tenant-scoped: the models inherit orgs' `TenantModel`, so each organization sees its own data.

## Configuration

The module declares the options below in `module.yml`; `quickscale plan` and `quickscale apply`
write them to the generated settings, and `quickscale.yml` carries the desired values.

| Option | Type | Default | Django setting | Description |
|--------|------|---------|----------------|-------------|
| `enable_api` | boolean | `true` | `CRM_ENABLE_API` | Enable REST API endpoints at `crm/api/`. |
| `deals_per_page` | integer | `25` | `CRM_DEALS_PER_PAGE` | Number of deals per page in list views. |
| `contacts_per_page` | integer | `50` | `CRM_CONTACTS_PER_PAGE` | Number of contacts per page in list views. |

## Public surface

Models: `Tag`, `Company`, `Contact`, `Stage`, `Deal`, `ContactNote`, and `DealNote`.

- `Tag` provides simple tagging for contacts and deals with a name, unique per organization.
- `Company` holds company records with a name and optional industry and website.
- `Contact` holds first name, last name, email, optional phone and job title, a status
  (`new`, `contacted`, `in_discussion`, `pending_response`, `inactive`), a required company
  association, multiple tags, and a `last_contacted_at` timestamp that is updated
  automatically when a contact note is created.
- `Stage` is a pipeline stage with a name and order for sequencing. Terminal won/lost
  semantics are tracked internally and are not part of the public config surface.
- `Deal` holds a title, a required contact association, an optional amount, a required stage,
  an optional expected close date, a probability (default 50), an optional owner, and tags;
  the company is derived from the contact.
- `ContactNote` and `DealNote` attach notes to contacts or deals with `created_by` tracking.

Terminal won/lost stages are managed internally through hidden stage semantics. Stage CRUD
stays editable through the admin and API, and the bulk `mark-won` / `mark-lost` actions
recreate canonical terminal rows if older data snapshots no longer have a semantic terminal
stage.

### API

All staff-authenticated API endpoints are available under `crm/api/` when `CRM_ENABLE_API` is
`true`:

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `crm/api/` | GET | Staff-only API root with CRM endpoint links |
| `crm/api/tags/` | GET, POST | List/create tags |
| `crm/api/tags/{id}/` | GET, PUT, PATCH, DELETE | Tag detail |
| `crm/api/companies/` | GET, POST | List/create companies |
| `crm/api/companies/{id}/` | GET, PUT, PATCH, DELETE | Company detail |
| `crm/api/contacts/` | GET, POST | List/create contacts |
| `crm/api/contacts/{id}/` | GET, PUT, PATCH, DELETE | Contact detail |
| `crm/api/contacts/{id}/notes/` | GET, POST | List/create contact notes |
| `crm/api/stages/` | GET, POST | List/create stages |
| `crm/api/stages/{id}/` | GET, PUT, PATCH, DELETE | Stage detail |
| `crm/api/deals/` | GET, POST | List/create deals |
| `crm/api/deals/{id}/` | GET, PUT, PATCH, DELETE | Deal detail |
| `crm/api/deals/{id}/notes/` | GET, POST | List/create deal notes |
| `crm/api/deals/bulk-update-stage/` | POST | Bulk update deal stages |
| `crm/api/deals/mark-won/` | POST | Mark deals as won |
| `crm/api/deals/mark-lost/` | POST | Mark deals as lost |
| `crm/api/contact-notes/` | GET, POST | List/create contact notes |
| `crm/api/contact-notes/{id}/` | GET, PUT, PATCH, DELETE | Contact note detail |
| `crm/api/deal-notes/` | GET, POST | List/create deal notes |
| `crm/api/deal-notes/{id}/` | GET, PUT, PATCH, DELETE | Deal note detail |

All CRM API endpoints, including standalone note routes, nested note actions, and deal bulk
actions, use session authentication and require a staff user. The HTML dashboard at
`crm/dashboard/` is a separate staff-only surface: anonymous users are redirected to the
configured login entry, authenticated non-staff users receive `403`, and staff users can view
the dashboard regardless of the `CRM_ENABLE_API` toggle. When `CRM_ENABLE_API` is `false`, the
`crm/api/` routes remain hidden and return `404`.

Filtering:

- Contacts by `status`, `company`, and `tags`.
- Deals by `stage`, `owner`, `tags`, and `contact__company`.

Search:

- Contacts on `first_name`, `last_name`, `email`, and `company__name`.
- Deals on `title`, `contact__first_name`, and `contact__last_name`.

## URLs

`quickscale apply` mounts the module at the project root; the module's own paths are:

| URL name | Path | View |
|----------|------|------|
| `quickscale_crm:dashboard` | `crm/dashboard/` | Staff-only CRM dashboard |
| `quickscale_crm:api-root` | `crm/api/` | Staff-only API root with endpoint links |
| `quickscale_crm:tag-list`, `quickscale_crm:tag-detail` | `crm/api/tags/` and `crm/api/tags/<id>/` | Tag API |
| `quickscale_crm:company-list`, `quickscale_crm:company-detail` | `crm/api/companies/` and detail | Company API |
| `quickscale_crm:contact-list`, `quickscale_crm:contact-detail`, `quickscale_crm:contact-notes` | `crm/api/contacts/`, detail, and `crm/api/contacts/<id>/notes/` | Contact API |
| `quickscale_crm:stage-list`, `quickscale_crm:stage-detail` | `crm/api/stages/` and detail | Stage API |
| `quickscale_crm:deal-list`, `quickscale_crm:deal-detail`, `quickscale_crm:deal-notes` | `crm/api/deals/`, detail, and `crm/api/deals/<id>/notes/` | Deal API |
| `quickscale_crm:deal-bulk-update-stage`, `quickscale_crm:deal-mark-won`, `quickscale_crm:deal-mark-lost` | `crm/api/deals/bulk-update-stage/`, `mark-won/`, `mark-lost/` | Deal bulk actions |
| `quickscale_crm:contact-note-list`, `quickscale_crm:contact-note-detail` | `crm/api/contact-notes/` and detail | Standalone contact-note API |
| `quickscale_crm:deal-note-list`, `quickscale_crm:deal-note-detail` | `crm/api/deal-notes/` and detail | Standalone deal-note API |

## Management commands

This module ships no management commands.

## Operations

Add the module through QuickScale:

```bash
quickscale plan --add crm
quickscale apply
```

A manual installation adds `rest_framework`, `django_filters`, and `quickscale_modules_crm` to
`INSTALLED_APPS`, mounts the module's URLs, and runs `python manage.py migrate quickscale_crm`.
The staff API and dashboard are subject to the active-organization behavior of orgs'
`TenantMiddleware`: a staff user without a selected organization is redirected to the org
selector before the dashboard or API runs.

## Extending

- The module's admin, API viewsets, serializers, and filters are the supported customization
  points; the tenant behavior comes from orgs' `TenantModel` and `TenantModelAdmin`.
- Development from the maintainer repository:

  ```bash
  make MODULE=crm test -- --modules
  poetry run ruff check quickscale_modules/crm/
  poetry run mypy quickscale_modules/crm/src/
  ```

- Licensed under the Apache 2.0 License; see the main QuickScale project for details.
