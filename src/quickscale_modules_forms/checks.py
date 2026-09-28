"""Startup checks for the QuickScale forms module.

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
    """Fail startup when a required forms setting is absent.

    Every generated project must explicitly set these; there is no silent
    fallback that defaults them when absent.
    """
    messages: list[CheckMessage] = []
    if not hasattr(settings, "FORMS_SUBMISSIONS_API"):
        messages.append(
            Error(
                "The FORMS_SUBMISSIONS_API setting is required. "
                "Set it to True or False in your Django settings.",
                id="quickscale_forms.E001",
            )
        )
    if not hasattr(settings, "FORMS_RATE_LIMIT"):
        messages.append(
            Error(
                "The FORMS_RATE_LIMIT setting is required. "
                "Set it to a throttle rate string (e.g. '5/hour') in your "
                "Django settings.",
                id="quickscale_forms.E002",
            )
        )
    if not hasattr(settings, "FORMS_SPAM_PROTECTION"):
        messages.append(
            Error(
                "The FORMS_SPAM_PROTECTION setting is required. "
                "Set it to True or False in your Django settings.",
                id="quickscale_forms.E003",
            )
        )
    return messages
