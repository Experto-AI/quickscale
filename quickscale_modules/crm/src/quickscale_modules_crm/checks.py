"""Startup checks for the QuickScale CRM module.

Rule 10: these functions are run from ``AppConfig.ready()`` through
``quickscale_core.runtime.register_module_checks``, so a failure refuses
``runserver``, ``migrate``, and ``manage.py check`` alike.
"""

from __future__ import annotations

from django.conf import settings
from django.core.checks import CheckMessage, Error


def check_required_settings(
    app_configs: object = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Fail startup when a required CRM setting is absent.

    Every generated project must explicitly set ``CRM_ENABLE_API``; there is
    no silent fallback that enables the CRM API when the setting is absent.
    """
    if hasattr(settings, "CRM_ENABLE_API"):
        return []
    return [
        Error(
            "The CRM_ENABLE_API setting is required. "
            "Set it to True or False in your Django settings.",
            id="quickscale_crm.E001",
        )
    ]
