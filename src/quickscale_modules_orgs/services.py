"""Public service surface for the QuickScale organizations module.

Module Conventions rule 4: another module uses orgs only through this file
plus the foundation extension bases the convention lists (models, managers,
admin, current_org, tenancy, removal, sanitization, public_context,
permissions, signals); rule 23: exactly ``__all__`` below is the module's
public service surface, and a service that cannot do what it was asked raises
:class:`OrgsError` (rule 10).

The org lifecycle operations (create, invite, accept, role change, removal)
are the module's own management views and forms, so the error surface is
re-exported here for the callers that catch it.
"""

from __future__ import annotations

from .exceptions import CurrentOrgError, OrgsError

__all__ = [
    "CurrentOrgError",
    "OrgsError",
]
