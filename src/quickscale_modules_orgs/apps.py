"""Django app configuration for QuickScale organizations.

SA68 Phase 1 — BYPASSRLS/SUPERUSER boot guard: raises
``ImproperlyConfigured`` at startup when connected as a PostgreSQL role
with the BYPASSRLS privilege and/or the SUPERUSER attribute.  The guard
has two narrow exemptions:

1. ``QUICKSCALE_PRIVILEGED_COMMAND`` set to a sanctioned privileged
   DB command (``migrate``, ``createcachetable``) — ``start.sh`` sets
   this env var alongside ``RUNTIME_DATABASE_URL=""`` so DDL runs under
   the superuser ``DATABASE_URL`` with BYPASSRLS.
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

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.backends.signals import connection_created


# Sanctioned privileged DB commands that require the superuser DATABASE_URL.
# Add new commands here when the generated launcher starts setting
# QUICKSCALE_PRIVILEGED_COMMAND to additional values.
_PRIVILEGED_COMMANDS: frozenset[str] = frozenset({"migrate", "createcachetable"})


def _is_privileged_command() -> bool:
    """Return ``True`` when ``QUICKSCALE_PRIVILEGED_COMMAND`` is set to a
    sanctioned privileged DB command.

    Sanctioned values (``migrate``, ``createcachetable``) are exempt from
    the BYPASSRLS/SUPERUSER boot guard because the generated ``start.sh``
    sets this env var alongside ``RUNTIME_DATABASE_URL=""`` so that
    database DDL/DML runs under the superuser ``DATABASE_URL`` with
    ``BYPASSRLS`` (and thus also ``SUPERUSER``).  All other management
    commands and non-manage.py startup (gunicorn, WSGI) must still fail
    closed — running with BYPASSRLS or SUPERUSER on a runtime server is
    catastrophic for RLS enforcement.

    ``_PRIVILEGED_COMMANDS`` is the single source of truth for which
    values are sanctioned.  If the env var is set to an unrecognised
    value the guard still fails closed (return ``False``) — it is not a
    catch-all escape hatch.

    SA68 Phase 1 replaces the old ``sys.argv`` inspection with the
    explicit env-var contract set by the generated ``start.sh`` and
    ``Dockerfile`` launchers.

    SA68 CR-SA68-001: widened from a ``== "migrate"`` check to a
    membership test against ``_PRIVILEGED_COMMANDS`` so that
    ``createcachetable`` (and future sanctioned values) also skip the
    boot guard without requiring the ``QUICKSCALE_ALLOW_BYPASSRLS=1``
    escape hatch.

    SA2.1: For the separate ``QUICKSCALE_ALLOW_BYPASSRLS=1`` escape
    hatch see ``_check_rls_role``.
    """
    return os.environ.get("QUICKSCALE_PRIVILEGED_COMMAND") in _PRIVILEGED_COMMANDS


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
    """Verify the connected PostgreSQL role does not have BYPASSRLS or SUPERUSER.

    SA2.1: The guard is always active (regardless of ``QUICKSCALE_MODE``
    or ``DEBUG``) with two narrow exemptions:

    1. ``QUICKSCALE_PRIVILEGED_COMMAND`` set to a sanctioned value
       (``migrate``, ``createcachetable``) — handled in ``ready()``
       before this is called.
    2. ``QUICKSCALE_ALLOW_BYPASSRLS=1`` env-var escape hatch — for
       intentional single-tenant or development use.

    The sanctioned command set is defined by ``_PRIVILEGED_COMMANDS``
    and checked via ``_is_privileged_command()``.

    No-op on SQLite (non-PostgreSQL).
    """
    # ---- Escape hatch --------------------------------------------------
    # Explicit opt-in for single-tenant / development environments.
    if os.environ.get("QUICKSCALE_ALLOW_BYPASSRLS") == "1":
        return

    if connection.vendor != "postgresql":
        return

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user"
        )
        row = cursor.fetchone()
        if row is not None and (row[0] or row[1]):
            raise ImproperlyConfigured(
                "The connected PostgreSQL role has BYPASSRLS and/or SUPERUSER privilege. "
                "PostgreSQL Row-Level Security policies are silently "
                "disabled for roles with BYPASSRLS or SUPERUSER. "
                "Use a restricted role created with NOSUPERUSER and NOBYPASSRLS "
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

        # ---- SA68 Phase 1 — BYPASSRLS/SUPERUSER boot guard -------------
        # Two narrow exemptions:
        #   1. QUICKSCALE_PRIVILEGED_COMMAND set to a sanctioned value
        #      (migrate, createcachetable) — start.sh sets this env var
        #      alongside RUNTIME_DATABASE_URL="" so DDL/DML runs under
        #      the superuser DATABASE_URL with BYPASSRLS.
        #   2. QUICKSCALE_ALLOW_BYPASSRLS=1 env-var escape hatch
        #      (checked inside _check_rls_role).
        # All other startup (runserver, gunicorn, WSGI) must still
        # fail closed — regardless of QUICKSCALE_MODE or DEBUG.
        if _is_privileged_command():
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
