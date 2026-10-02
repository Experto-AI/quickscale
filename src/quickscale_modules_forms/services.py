"""Public service surface for the Forms module.

The sending module owns its analytics event names (Module Conventions
rule 22): forms emits ``quickscale_forms_submitted`` through analytics'
generic ``capture_event``.
"""

from __future__ import annotations

from typing import Final

from django.conf import settings

FORMS_SUBMITTED_EVENT: Final[str] = "quickscale_forms_submitted"


def is_enabled() -> bool:
    """Return whether the module is enabled by ``QUICKSCALE_FORMS_ENABLED``.

    Rule 4: the question a caller asks before using an optional module;
    rule 3: the declared setting is read directly, with no default.
    """
    return bool(settings.QUICKSCALE_FORMS_ENABLED)


__all__ = [
    "FORMS_SUBMITTED_EVENT",
    "is_enabled",
]
