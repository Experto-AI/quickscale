"""Startup checks for the QuickScale auth module.

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
    """Fail startup when a required auth setting is absent.

    Every generated project must explicitly set
    ``ACCOUNT_ALLOW_REGISTRATION``; there is no silent fallback that enables
    open registration.
    """
    if hasattr(settings, "ACCOUNT_ALLOW_REGISTRATION"):
        return []
    return [
        Error(
            "The ACCOUNT_ALLOW_REGISTRATION setting is required. "
            "Set it to True or False in your Django settings.",
            id="quickscale_auth.E001",
        )
    ]
