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

SA203 — the privileged-command exemption narrows to ``check_rls_role()``
alone; the priming install, the SA70 last-owner ``pre_delete`` backstop,
and the check registration run on every startup path.
"""

from django.apps import AppConfig
from django.db.backends.signals import connection_created

from quickscale_core.runtime import register_module_checks
from quickscale_modules_orgs.removal import (
    OWNED_TENANT_ROWS,
    PURGE_TOMBSTONE,
    SOCIAL_CACHE_STATE,
    OrganizationRemovalObligation,
    RemovalAction,
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
    label = "quickscale_orgs"
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
        # ---- Rule 10 — startup checks through the shared helper --------
        # The helper runs every check eagerly, so runserver, migrate, and a
        # WSGI server all refuse to start on an error-level failure, and it
        # registers the same callables as ``quickscale_orgs`` system checks
        # for ``manage.py check``.  Order matters: QUICKSCALE_MODE is
        # validated before the BYPASSRLS/SUPERUSER role guard.
        #
        # SA203: a privileged command exempts *only* the role check, inside
        # check_rls_role.  The installations below stay unconditional, so a
        # privileged ``migrate`` still gets the GUC priming wrapper and the
        # last-owner ``pre_delete`` backstop — the backstop is what fails a
        # data migration that would delete an organization's last owner.
        #
        # Late import: checks.py reads models through tenancy, so it must load
        # after the app registry is ready.  Importing the module also
        # registers the two warning-only catalog checks (tenant isolation and
        # model classification) as ``quickscale_orgs`` system checks; they are
        # not passed to the eager runner because one of them reads live
        # database catalog state and neither may block startup.
        from quickscale_modules_orgs.checks import (
            check_provider_id_conformance,
            check_quickscale_mode,
            check_removal_obligation_discharge,
            check_rls_role,
        )

        register_module_checks(
            self,
            [
                check_quickscale_mode,
                check_rls_role,
                check_provider_id_conformance,
                check_removal_obligation_discharge,
            ],
        )

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
