"""Django app configuration for QuickScale organizations.

T1.18 — RLS boot guard: raises ``ImproperlyConfigured`` at startup when
connected as a PostgreSQL role with BYPASSRLS in saas production mode.

Only ``manage.py migrate`` is exempt from the guard — ``start.sh``
deliberately unsets ``RUNTIME_DATABASE_URL`` so DDL runs under the
superuser ``DATABASE_URL``.  All other startup paths (including
``manage.py runserver``, gunicorn, and WSGI) remain fail-closed.
"""

import sys

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection


def _is_migrate_command() -> bool:
    """Return ``True`` when Django is running ``manage.py migrate``.

    Only ``migrate`` is exempt from the BYPASSRLS boot guard because
    the generated ``start.sh`` deliberately unsets
    ``RUNTIME_DATABASE_URL`` so that schema DDL runs under the
    superuser ``DATABASE_URL`` with ``BYPASSRLS``.  All other
    management commands (notably ``runserver``) and non-manage.py
    startup (gunicorn, WSGI) must still fail closed — running with
    BYPASSRLS on a runtime server is catastrophic for RLS enforcement.
    """
    return (
        len(sys.argv) >= 2
        and sys.argv[0].endswith("manage.py")
        and sys.argv[1] == "migrate"
    )


def _check_rls_role() -> None:
    """Verify the connected PostgreSQL role does not have BYPASSRLS.

    In SaaS mode with ``DEBUG=False``, query ``pg_roles`` and fail fast
    if the current role has ``rolbypassrls = true``.  No-op on SQLite
    (non-PostgreSQL), in solo mode, and when ``DEBUG=True``.
    """
    if getattr(settings, "QUICKSCALE_MODE", "solo") != "saas":
        return
    if settings.DEBUG:
        return
    if connection.vendor != "postgresql":
        return

    with connection.cursor() as cursor:
        cursor.execute("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
        row = cursor.fetchone()
        if row is not None and row[0]:
            raise ImproperlyConfigured(
                "The connected PostgreSQL role has BYPASSRLS privilege. "
                "Postgres Row-Level Security policies are silently "
                "disabled for roles with BYPASSRLS. "
                "Use a restricted role created with NOBYPASSRLS "
                "as documented in the operations guide."
            )


class QuickscaleOrgsConfig(AppConfig):
    """Configuration for the QuickScale organizations module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_orgs"
    label = "quickscale_modules_orgs"
    verbose_name = "QuickScale Organizations"

    def ready(self) -> None:
        # Only manage.py migrate is exempt — start.sh deliberately unsets
        # RUNTIME_DATABASE_URL so DDL runs under the superuser DATABASE_URL
        # with BYPASSRLS.  All other startup (runserver, gunicorn, WSGI)
        # must still fail closed.
        if _is_migrate_command():
            return
        _check_rls_role()
