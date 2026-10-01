"""Public service surface for the Forms module.

The sending module owns its analytics event names (Module Conventions
rule 22): forms emits ``quickscale_forms_submitted`` through analytics'
generic ``capture_event``.
"""

from __future__ import annotations

from typing import Final

FORMS_SUBMITTED_EVENT: Final[str] = "quickscale_forms_submitted"

__all__ = [
    "FORMS_SUBMITTED_EVENT",
]
