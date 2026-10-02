# QuickScale CRM Module

A lightweight CRM module for QuickScale projects, providing contact management, company
tracking, and deal pipeline functionality.

## Overview

- **7 core models**: Tag, Company, Contact, Stage, Deal, ContactNote, DealNote.
- **RESTful API**: session-authenticated CRUD operations authorized by organization role
  (minimum `viewer` to read, `member` to write) with Django REST Framework.
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
| `enabled` | boolean | `true` | `QUICKSCALE_CRM_ENABLED` | Mount the module's dashboard and API. Off keeps the app and its data installed but serves none of its URLs. |
| `api_enabled` | boolean | `true` | `QUICKSCALE_CRM_API_ENABLED` | Enable REST API endpoints at `crm/api/`. |
| `deals_per_page` | integer | `25` | `QUICKSCALE_CRM_DEALS_PER_PAGE` | Number of deals per page in list views. |
| `contacts_per_page` | integer | `50` | `QUICKSCALE_CRM_CONTACTS_PER_PAGE` | Number of contacts per page in list views. |

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

All member-authenticated API endpoints are available under `crm/api/` when
`QUICKSCALE_CRM_API_ENABLED` is `true` (route names are snake_case under
`quickscale_crm:`):

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `crm/api/` | GET | API root with CRM endpoint links (viewer role) |
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
actions, use session authentication and authorize by the active organization's role: reads
(list, retrieve, and note lists) require the `viewer` role, writes (create, update, delete,
bulk actions, and note creation) require the `member` role, and an authenticated caller below
the minimum is refused. The HTML dashboard at `crm/dashboard/` requires the `viewer` role:
anonymous users are redirected to
the configured login entry, an authenticated caller below `viewer` receives `403`, and a
`viewer` can view the dashboard regardless of the `QUICKSCALE_CRM_API_ENABLED` toggle. When
`QUICKSCALE_CRM_API_ENABLED` is `false`, the
`crm/api/` routes remain hidden and return `404`.

Filtering:

- Contacts by `status`, `company`, and `tags`.
- Deals by `stage`, `owner`, `tags`, and `contact__company`.

Search:

- Contacts on `first_name`, `last_name`, `email`, and `company__name`.
- Deals on `title`, `contact__first_name`, and `contact__last_name`.

## URLs

`quickscale apply` mounts the module at `crm/` (its manifest `url_includes` entry); the
module's paths are:

| URL name | Path | View |
|----------|------|------|
| `quickscale_crm:dashboard` | `crm/dashboard/` | CRM dashboard (viewer role) |
| `quickscale_crm:api_root` | `crm/api/` | API root with endpoint links (viewer role) |
| `quickscale_crm:tag_list`, `quickscale_crm:tag_detail` | `crm/api/tags/` and `crm/api/tags/<id>/` | Tag API |
| `quickscale_crm:company_list`, `quickscale_crm:company_detail` | `crm/api/companies/` and detail | Company API |
| `quickscale_crm:contact_list`, `quickscale_crm:contact_detail`, `quickscale_crm:contact_notes` | `crm/api/contacts/`, detail, and `crm/api/contacts/<id>/notes/` | Contact API |
| `quickscale_crm:stage_list`, `quickscale_crm:stage_detail` | `crm/api/stages/` and detail | Stage API |
| `quickscale_crm:deal_list`, `quickscale_crm:deal_detail`, `quickscale_crm:deal_notes` | `crm/api/deals/`, detail, and `crm/api/deals/<id>/notes/` | Deal API |
| `quickscale_crm:deal_bulk_update_stage`, `quickscale_crm:deal_mark_won`, `quickscale_crm:deal_mark_lost` | `crm/api/deals/bulk-update-stage/`, `mark-won/`, `mark-lost/` | Deal bulk actions |
| `quickscale_crm:contact_note_list`, `quickscale_crm:contact_note_detail` | `crm/api/contact-notes/` and detail | Standalone contact-note API |
| `quickscale_crm:deal_note_list`, `quickscale_crm:deal_note_detail` | `crm/api/deal-notes/` and detail | Standalone deal-note API |

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
The API and dashboard are subject to the active-organization behavior of orgs'
`TenantMiddleware`: a user without a selected organization is redirected to the org
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
