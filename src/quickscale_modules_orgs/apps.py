"""Django app configuration for QuickScale organizations.

T1.18 / SA2.1 — BYPASSRLS boot guard: raises ``ImproperlyConfigured``
at startup when connected as a PostgreSQL role with the BYPASSRLS
privilege.  The guard has two narrow exemptions:

1. ``manage.py migrate`` — ``start.sh`` deliberately unsets
   ``RUNTIME_DATABASE_URL`` so DDL runs under the superuser
   ``DATABASE_URL`` with BYPASSRLS.
2. ``QUICKSCALE_ALLOW_BYPASSRLS=1`` env-var escape hatch — for
   intentional single-tenant or development use.

All other startup paths (including ``manage.py runserver``,
gunicorn, and WSGI) remain fail-closed regardless of
``QUICKSCALE_MODE`` or ``DEBUG``.

AF9 Phase 1 — installs the connection-layer GUC priming execute wrapper
on every Django ``DatabaseWrapper`` so that ``SET LOCAL app.current_org_id``
is derived from the ContextVar in the same transaction as tenant SQL.
"""

import os
import sys

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.backends.signals import connection_created


def _is_migrate_command() -> bool:
    """Return ``True`` when Django is running ``manage.py migrate``.

    Only ``migrate`` is exempt from the BYPASSRLS boot guard because
    the generated ``start.sh`` deliberately unsets
    ``RUNTIME_DATABASE_URL`` so that schema DDL runs under the
    superuser ``DATABASE_URL`` with ``BYPASSRLS``.  All other
    management commands (notably ``runserver``) and non-manage.py
    startup (gunicorn, WSGI) must still fail closed — running with
    BYPASSRLS on a runtime server is catastrophic for RLS enforcement.

    SA2.1: For the separate ``QUICKSCALE_ALLOW_BYPASSRLS=1`` escape
    hatch see ``_check_rls_role``.
    """
    return (
        len(sys.argv) >= 2
        and sys.argv[0].endswith("manage.py")
        and sys.argv[1] == "migrate"
    )


def _check_quickscale_mode() -> None:
    """SA14.6 — Require ``QUICKSCALE_MODE`` setting when orgs is installed.

    Raises ``ImproperlyConfigured`` at startup when ``QUICKSCALE_MODE``
    is unset, preventing a saas-mode generated project from silently
    defaulting to solo-mode tenancy.

    Also rejects values other than ``"solo"`` or ``"saas"`` so that
    an invalid ``QUICKSCALE_MODE`` does not silently behave as solo.
    """
    mode = getattr(settings, "QUICKSCALE_MODE", None)
    if mode is None:
        raise ImproperlyConfigured(
            "QUICKSCALE_MODE setting is required when "
            "quickscale_modules_orgs is installed. "
            "Set it to 'solo' for single-tenant or 'saas' for "
            "multi-tenant mode."
        )
    if mode not in ("solo", "saas"):
        raise ImproperlyConfigured(
            f"QUICKSCALE_MODE must be 'solo' or 'saas', got {mode!r}."
        )


def _check_rls_role() -> None:
    """Verify the connected PostgreSQL role does not have BYPASSRLS.

    SA2.1: The guard is always active (regardless of ``QUICKSCALE_MODE``
    or ``DEBUG``) with two narrow exemptions:

    1. ``manage.py migrate`` — handled in ``ready()`` before this is
       called.
    2. ``QUICKSCALE_ALLOW_BYPASSRLS=1`` env-var escape hatch — for
       intentional single-tenant or development use.

    No-op on SQLite (non-PostgreSQL).
    """
    # ---- Escape hatch --------------------------------------------------
    # Explicit opt-in for single-tenant / development environments.
    if os.environ.get("QUICKSCALE_ALLOW_BYPASSRLS") == "1":
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


def _install_priming_on_connection(
    sender: object,
    connection: object,
    **kwargs: object,
) -> None:
    """Signal handler: install the AF9 priming wrapper on a new connection.

    Connected in ``QuickscaleOrgsConfig.ready()`` to
    ``django.db.backends.signals.connection_created`` so that every new
    ``DatabaseWrapper`` receives the execute wrapper automatically.
    """
    from quickscale_modules_orgs.current_org import install_priming_wrapper

    install_priming_wrapper(connection)


class QuickscaleOrgsConfig(AppConfig):
    """Configuration for the QuickScale organizations module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "quickscale_modules_orgs"
    label = "quickscale_modules_orgs"
    verbose_name = "QuickScale Organizations"

    def ready(self) -> None:
        # ---- SA14.6 — QUICKSCALE_MODE boot guard -----------------------
        # Runs before the migrate exemption and the BYPASSRLS guard so
        # that every startup path (including migrate) enforces the
        # required setting.  A saas-mode generated project cannot silently
        # default to solo-mode tenancy when QUICKSCALE_MODE is omitted.
        _check_quickscale_mode()

        # ---- T1.18 / SA2.1 — BYPASSRLS boot guard ----------------------
        # Two narrow exemptions:
        #   1. manage.py migrate — start.sh deliberately unsets
        #      RUNTIME_DATABASE_URL so DDL runs under the superuser
        #      DATABASE_URL with BYPASSRLS.
        #   2. QUICKSCALE_ALLOW_BYPASSRLS=1 env-var escape hatch
        #      (checked inside _check_rls_role).
        # All other startup (runserver, gunicorn, WSGI) must still
        # fail closed — regardless of QUICKSCALE_MODE or DEBUG.
        if _is_migrate_command():
            return
        _check_rls_role()

        # ---- AF9 Phase 1 — GUC priming execute wrapper ------------------
        # Install on any connections already created (defensive — at
        # ready() time the connection pool is typically empty) and
        # connect the signal for all future connections.
        from django.db import connections
        from quickscale_modules_orgs.current_org import install_priming_wrapper

        for conn in connections.all():
            install_priming_wrapper(conn)
        connection_created.connect(_install_priming_on_connection)

        # ---- SA1.3 — tenant-isolation system check -----------------------
        # Import checks.py to register the check_tenant_isolation system
        # check.  The @register decorator runs at import time, so importing
        # the module is sufficient to register it.
        import quickscale_modules_orgs.checks  # noqa: F401
