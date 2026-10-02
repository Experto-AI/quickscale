"""Tests for forms' public service surface (Module Conventions rules 4, 23)."""

from __future__ import annotations

from django.test import override_settings

from quickscale_modules_forms import services
from quickscale_modules_forms.services import FORMS_SUBMITTED_EVENT

#: Exactly the names rule 23 makes the module's public service surface.
SERVICE_SURFACE = [
    "FORMS_SUBMITTED_EVENT",
    "is_enabled",
]


def test_services_publishes_exactly_the_declared_surface() -> None:
    """``__all__`` is the module's public surface, and nothing else is public."""
    assert services.__all__ == SERVICE_SURFACE
    for name in SERVICE_SURFACE:
        assert hasattr(services, name), f"{name} is missing from services.py"


def test_services_names_the_forms_submitted_event() -> None:
    """Rule 22: the sending module owns its analytics event name."""
    assert FORMS_SUBMITTED_EVENT == "quickscale_forms_submitted"


def test_is_enabled_reads_the_module_enabled_setting() -> None:
    """Rule 1: ``is_enabled()`` reports ``QUICKSCALE_FORMS_ENABLED`` both ways."""
    with override_settings(QUICKSCALE_FORMS_ENABLED=True):
        assert services.is_enabled() is True
    with override_settings(QUICKSCALE_FORMS_ENABLED=False):
        assert services.is_enabled() is False
