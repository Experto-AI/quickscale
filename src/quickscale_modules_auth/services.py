"""Public service surface for the QuickScale auth module.

Module Conventions rule 4: another module uses auth only through this file,
and rule 23: exactly ``__all__`` below is the module's public service
surface, and a service that cannot do what it was asked raises
:class:`AuthError` (rule 10).

The module's account flows (signup, login, password reset, profile view and
edit, account deletion) are allauth- and Django-wired views, and the
``User`` model is reached through ``AUTH_USER_MODEL``, so the error base is
the callers' one auth surface today.
"""

from __future__ import annotations

from django.conf import settings

from .exceptions import AuthError


def is_enabled() -> bool:
    """Return whether the module is enabled by ``QUICKSCALE_AUTH_ENABLED``.

    Rule 4: the question a caller asks before using an optional module;
    rule 3: the declared setting is read directly, with no default.
    """
    return bool(settings.QUICKSCALE_AUTH_ENABLED)


__all__ = [
    "AuthError",
    "is_enabled",
]
