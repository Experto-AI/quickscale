"""Vocabulary and declaration records for organization-removal obligations.

``removal.py`` re-exports these names (Module Conventions rule 28); the
declaration aggregation and validation lives in ``_removal_declarations`` and
the provider-ID conformance walks in ``_removal_provider_ids``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RemovalBoundary(Enum):
    """The two shipped boundaries that remove org-related state."""

    PURGE = "purge"
    ACCOUNT_DELETE = "account-delete"


class RemovalAction(Enum):
    """How one boundary discharges an organization-removal obligation."""

    REFUSE = "refuse"
    RECONCILE = "reconcile"
    DELETE = "delete"
    INVALIDATE = "invalidate"
    RECORD = "record"
    ANONYMIZE = "anonymize"
    SKIP = "skip"


@dataclass(frozen=True)
class ExternalProviderField:
    """One provider identifier covered by an obligation."""

    model_label: str
    field_name: str
    structured_keys: tuple[str, ...] = ()
    #: True when the declaring app's own boundary guard decides whether this
    #: field's state blocks removal; the obligation names those executor hooks
    #: in its ``boundary_guarded_hooks`` declaration.  False (the default)
    #: means the shared boundary guard refuses while the field carries a
    #: value, so the declaration is enforced without bespoke code.
    boundary_guarded: bool = False


@dataclass(frozen=True)
class BoundaryGuardedHooks:
    """AppConfig hooks an obligation's boundary-guarded fields declare.

    A declaration whose provider fields carry ``boundary_guarded=True`` names
    the executor hooks on the declaring app's ``AppConfig``, so the boundary
    runs the declaring module's own provider-state code:

    * ``guard`` (required): called inside the removal transaction with the
      organization and any provider-confirmed expired checkout id; returns an
      empty string when removal may proceed, else the refusal message.
    * ``reconcile``: called before the removal transaction; returns a
      provider-confirmed expired checkout id, or an empty string.
    * ``mutation_lock``: called to obtain the context manager the boundary
      holds across reconciliation and removal.
    """

    guard: str
    reconcile: str = ""
    mutation_lock: str = ""


@dataclass(frozen=True)
class OrganizationRemovalObligation:
    """One cross-domain responsibility at each removal boundary."""

    name: str
    purge_action: RemovalAction
    account_delete_action: RemovalAction
    account_delete_skip_reason: str = ""
    external_provider_fields: tuple[ExternalProviderField, ...] = ()
    boundary_guarded_hooks: BoundaryGuardedHooks | None = None

    def action_for(self, boundary: RemovalBoundary) -> RemovalAction:
        """Return the action declared for *boundary*."""
        if boundary is RemovalBoundary.PURGE:
            return self.purge_action
        return self.account_delete_action


AUTH_PERSONAL_DATA = "auth-personal-data"
BILLING_PERSONAL_DATA = "billing-personal-data"
BILLING_PROVIDER_STATE = "billing-provider-state"
BLOG_PERSONAL_DATA = "blog-personal-data"
OWNED_TENANT_ROWS = "owned-tenant-rows"
OWNED_PERSONAL_DATA = "owned-personal-data"
SOCIAL_CACHE_STATE = "social-cache-state"
PURGE_TOMBSTONE = "purge-tombstone"

#: Model-level ``provider_id_classification`` values (SA208). A model classifies
#: each of its non-relational ``*_id`` fields with one of these so a project-owned
#: app can declare its provider obligations without editing vendored orgs source.
PROVIDER_BACKED = "provider-backed"
NOT_PROVIDER_BACKED = "not-provider-backed"

_PROVIDER_ID_CLASSIFICATIONS: frozenset[str] = frozenset(
    {PROVIDER_BACKED, NOT_PROVIDER_BACKED}
)


#: AppConfig attribute through which an app declares its own removal
#: obligations: either a tuple, or a method returning a tuple, of
#: :class:`OrganizationRemovalObligation` entries.
REMOVAL_OBLIGATIONS_ATTRIBUTE: str = "removal_obligations"

#: Label of the organization row itself.  It carries provider state but no
#: ``organization_id``, so a declared refusal field on it is inspected on the
#: organization row instead of through an organization filter.
ORGANIZATION_MODEL_LABEL: str = "quickscale_orgs.organization"

#: The actions each removal boundary discharges through the shared coordinator.
#: ``SKIP`` is deliberately absent: a skipped obligation is recorded, never
#: executed.  ``check_removal_obligation_discharge`` (E002) fails when a
#: discovered obligation declares an action its boundary has no route for,
#: because only a boundary that bypasses the coordinator could satisfy it.
COORDINATOR_DISCHARGE_ACTIONS: dict[RemovalBoundary, frozenset[RemovalAction]] = {
    RemovalBoundary.PURGE: frozenset(
        {
            RemovalAction.REFUSE,
            RemovalAction.DELETE,
            RemovalAction.INVALIDATE,
            RemovalAction.RECORD,
        }
    ),
    RemovalBoundary.ACCOUNT_DELETE: frozenset(
        {RemovalAction.RECONCILE, RemovalAction.ANONYMIZE}
    ),
}

#: ``AppConfig`` hook each app-owned stage needs on the declaring app.  The
#: boundary calls the hook, so the declaring app owns the executor: a stage
#: whose hook is missing has nothing to run and the declaration is rejected.
#: ``REFUSE``, ``DELETE``, and ``RECORD`` are boundary-owned stages over
#: app-agnostic state (declared provider fields, tenant rows, the tombstone),
#: so they need no hook.
STAGE_EXECUTOR_HOOKS: dict[RemovalAction, str] = {
    RemovalAction.INVALIDATE: "invalidate_organization_cache",
    RemovalAction.RECONCILE: "reconcile_account_deletion_provider_state",
    RemovalAction.ANONYMIZE: "anonymize_account",
}

#: AppConfig attribute through which an app declares the removal boundary
#: implementations it ships: a mapping of :class:`RemovalBoundary` to
#: ``(shipping app name, implementation module path, entry function)``.
REMOVAL_BOUNDARY_IMPLEMENTATIONS_ATTRIBUTE: str = "removal_boundary_implementations"

#: AppConfig attribute through which a module declares the display prefix its
#: models take in removal summaries (for example ``"CRM"``).  A module that
#: declares none keeps Django's capitalized plural.
REMOVAL_LABEL_PREFIX_ATTRIBUTE: str = "removal_label_prefix"
