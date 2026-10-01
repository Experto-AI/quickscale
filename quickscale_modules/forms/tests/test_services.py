"""Tests for forms' public service surface (Module Conventions rules 4, 23)."""

from __future__ import annotations

from quickscale_modules_forms import services
from quickscale_modules_forms.services import FORMS_SUBMITTED_EVENT

#: Exactly the names rule 23 makes the module's public service surface.
SERVICE_SURFACE = [
    "FORMS_SUBMITTED_EVENT",
]


def test_services_publishes_exactly_the_declared_surface() -> None:
    """``__all__`` is the module's public surface, and nothing else is public."""
    assert services.__all__ == SERVICE_SURFACE
    for name in SERVICE_SURFACE:
        assert hasattr(services, name), f"{name} is missing from services.py"


def test_services_names_the_forms_submitted_event() -> None:
    """Rule 22: the sending module owns its analytics event name."""
    assert FORMS_SUBMITTED_EVENT == "quickscale_forms_submitted"
