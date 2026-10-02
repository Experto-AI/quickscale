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

from django.conf import settings

from .exceptions import CurrentOrgError, OrgsError


def is_enabled() -> bool:
    """Return whether the module is enabled by ``QUICKSCALE_ORGS_ENABLED``.

    Rule 4: the question a caller asks before using an optional module;
    rule 3: the declared setting is read directly, with no default.
    """
    return bool(settings.QUICKSCALE_ORGS_ENABLED)


__all__ = [
    "CurrentOrgError",
    "OrgsError",
    "is_enabled",
]
