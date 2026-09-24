"""Django app configuration for QuickScale organizations.

SA68 Phase 1 — BYPASSRLS/SUPERUSER boot guard: raises
``ImproperlyConfigured`` at startup when connected as a PostgreSQL role
with the BYPASSRLS privilege and/or the SUPERUSER attribute.  The guard
has two narrow exemptions:

1. ``QUICKSCALE_PRIVILEGED_COMMAND`` set to a sanctioned privileged
   DB command (``migrate`` or ``createcachetable``) — launchers set
   this env var alongside ``RUNTIME_DATABASE_URL=""`` so DDL runs under
   the superuser ``DATABASE_URL`` with BYPASSRLS.
2. ``QUICKSCALE_ALLOW_BYPASSRLS=1`` env-var escape hatch — for
   intentional single-tenant/development use or the explicitly acknowledged
   retired billing recovery command, never runtime serving.

All other startup paths (including ``manage.py runserver``,
gunicorn, and WSGI) remain fail-closed regardless of
``QUICKSCALE_MODE`` or ``DEBUG``.

AF9 Phase 1 — installs the connection-layer GUC priming execute wrapper
on every Django ``DatabaseWrapper`` so that ``SET LOCAL app.current_org_id``
is derived from the ContextVar in the same transaction as tenant SQL.

SA203 — the privileged-command exemption narrows to ``_check_rls_role()``
alone; the priming install, the SA70 last-owner ``pre_delete`` backstop,
and the SA1.3 system check registration run on every startup path.
"""

import os

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.backends.signals import connection_created

from quickscale_modules_orgs.removal import (
    OWNED_TENANT_ROWS,
    PURGE_TOMBSTONE,
    SOCIAL_CACHE_STATE,
    OrganizationRemovalObligation,
    RemovalAction,
)


# Module-guard declaration of the sanctioned privileged DB commands.
# Keep it aligned with the independent fail-closed declarations in the production
# settings validator, CLI producer, and generated start.sh launcher; none is a SSOT.
_PRIVILEGED_COMMANDS: frozenset[str] = frozenset({"migrate", "createcachetable"})


def _is_privileged_command() -> bool:
    """Return ``True`` when ``QUICKSCALE_PRIVILEGED_COMMAND`` is set to a
    sanctioned privileged DB command.

    Sanctioned values (``migrate`` and ``createcachetable``) are exempt from
    the BYPASSRLS/SUPERUSER boot guard because the generated ``start.sh``
    sets this env var alongside ``RUNTIME_DATABASE_URL=""`` so that
    database DDL/DML runs under the superuser ``DATABASE_URL`` with
    ``BYPASSRLS`` (and thus also ``SUPERUSER``).  All other management
    commands and non-manage.py startup (gunicorn, WSGI) must still fail
    closed — running with BYPASSRLS or SUPERUSER on a runtime server is
    catastrophic for RLS enforcement.

    ``_PRIVILEGED_COMMANDS`` is the module guard's declaration, one of four
    independent fail-closed declarations in this contract.  The other three
    are the generated production-settings validator, the CLI producer, and
    the generated ``start.sh`` launcher.  If the env var is set to an
    unrecognised value the guard still fails closed (return ``False``) — it
    is not a catch-all escape hatch.

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
       (``migrate`` or ``createcachetable``) — handled in ``ready()``
       before this is called.
    2. ``QUICKSCALE_ALLOW_BYPASSRLS=1`` env-var escape hatch — for
       intentional single-tenant/development use or the explicitly acknowledged
       retired billing recovery command, never runtime serving.

    This module guard declares its sanctioned command set in
    ``_PRIVILEGED_COMMANDS`` and checks it via ``_is_privileged_command()``;
    the production-settings validator, CLI producer, and generated launcher
    carry independent fail-closed declarations of the same contract.

    No-op on SQLite (non-PostgreSQL).
    """
    # ---- Escape hatch --------------------------------------------------
    # Explicit non-serving opt-in for single-tenant/development environments or
    # the acknowledged retired billing recovery command.
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

    def removal_obligations(self) -> tuple[OrganizationRemovalObligation, ...]:
        """Declare orgs' own organization-removal obligations.

        Every domain declares the obligations it owns from its own
        ``AppConfig``; ``orgs`` aggregates them for both removal boundaries.
        These three are orgs' own: the marker-derived tenant rows it deletes,
        the organization-scoped social cache state those rows leave behind,
        and the purge tombstone it records.
        """
        return (
            OrganizationRemovalObligation(
                name=OWNED_TENANT_ROWS,
                purge_action=RemovalAction.DELETE,
                account_delete_action=RemovalAction.SKIP,
                account_delete_skip_reason=(
                    "Account deletion removes the person while retaining "
                    "organization data."
                ),
            ),
            OrganizationRemovalObligation(
                name=SOCIAL_CACHE_STATE,
                purge_action=RemovalAction.INVALIDATE,
                account_delete_action=RemovalAction.SKIP,
                account_delete_skip_reason=(
                    "Retained organization data keeps its organization-scoped "
                    "cache state."
                ),
            ),
            OrganizationRemovalObligation(
                name=PURGE_TOMBSTONE,
                purge_action=RemovalAction.RECORD,
                account_delete_action=RemovalAction.SKIP,
                account_delete_skip_reason=(
                    "No organization is removed, so account deletion writes no "
                    "purge tombstone."
                ),
            ),
        )

    def invalidate_organization_cache(self, organization_id: object) -> None:
        """Invalidate organization-scoped cache state for *organization_id*.

        This is the executor for the ``social-cache-state`` obligation declared
        in :meth:`removal_obligations`: the purge boundary calls it after the
        organization's rows are deleted, and the tombstone retry path calls it
        to heal an invalidation that failed.  It clears the organization-scoped
        keys of the installed cache-owning modules (social).
        """
        from django.apps import apps as django_apps

        if not django_apps.is_installed("quickscale_modules_social"):
            return

        from django.core.cache import cache

        from quickscale_modules_social.contracts import (
            SOCIAL_EMBEDS_CACHE_KEY,
            SOCIAL_LINKS_CACHE_KEY,
        )

        cache.delete_many(
            [
                SOCIAL_LINKS_CACHE_KEY,
                f"{SOCIAL_LINKS_CACHE_KEY}:org:{organization_id}",
                SOCIAL_EMBEDS_CACHE_KEY,
                f"{SOCIAL_EMBEDS_CACHE_KEY}:org:{organization_id}",
            ]
        )

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
        #      (migrate or createcachetable) — launchers set this env var
        #      alongside RUNTIME_DATABASE_URL="" so DDL/DML runs under
        #      the superuser DATABASE_URL with BYPASSRLS.
        #   2. QUICKSCALE_ALLOW_BYPASSRLS=1 env-var escape hatch
        #      (checked inside _check_rls_role).
        # All other startup (runserver, gunicorn, WSGI) must still
        # fail closed — regardless of QUICKSCALE_MODE or DEBUG.
        #
        # SA203: a privileged command exempts *only* the role check.  The
        # installations below stay unconditional, so a privileged
        # ``migrate`` still gets the GUC priming wrapper, the last-owner
        # ``pre_delete`` backstop, and the tenant-isolation system check —
        # the backstop is what fails a data migration that would delete an
        # organization's last owner.
        if not _is_privileged_command():
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

        # ---- SA70 — pre_delete receiver backstop for last-owner invariant -
        # Connects the backstop receiver defined in signals.py so that
        # cascade-driven membership deletions (e.g. user.delete()) also
        # enforce the last-owner invariant.
        #
        # SA203: connected without a sender so the receiver also fires for
        # the historical model class a data migration deletes through
        # (``apps.get_model()`` returns a different class); the receiver
        # filters on the model's app label and name.  A sender-free receiver
        # makes Django's fast-delete path unavailable for every model while
        # connected — accepted: the invariant must cover every deletion
        # path, and the cost is bounded to queryset deletes materialising
        # one model's rows at a time on operator paths (organization purge,
        # account deletion), which are not hot paths.
        from django.db.models.signals import pre_delete

        from quickscale_modules_orgs.signals import (
            _protect_last_owner_on_membership_delete,
        )

        pre_delete.connect(_protect_last_owner_on_membership_delete)

        # ---- SA1.3 / SA1.4 / SA208 — registered system checks ------------
        # Import checks.py to register the check_tenant_isolation (SA1.3),
        # check_model_classification (SA1.4), and check_provider_id_conformance
        # (SA208) system checks.  The @register decorator runs at import time,
        # so importing the module is sufficient to register them.
        import quickscale_modules_orgs.checks  # noqa: F401
