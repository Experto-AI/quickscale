"""Optional CRM bootstrap integration for organization creation flows."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Callable, cast

from django.apps import apps

if TYPE_CHECKING:
    from .models import Organization


def maybe_seed_crm_default_stages(organization: Organization) -> None:
    """Seed CRM default stages when the CRM module is installed.

    The CRM import stays deferred so the orgs module does not gain a hard
    dependency at import time.
    """
    if not apps.is_installed("quickscale_modules_crm"):
        return
    ensure_org_default_stages = cast(
        Callable[[object], None],
        import_module("quickscale_modules_crm.services").ensure_org_default_stages,
    )
    ensure_org_default_stages(organization)
