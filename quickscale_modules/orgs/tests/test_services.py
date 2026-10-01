"""Tests for orgs' public service surface (Module Conventions rules 4, 23)."""

from __future__ import annotations

from quickscale_modules_orgs import services
from quickscale_modules_orgs.exceptions import CurrentOrgError, OrgsError

#: Exactly the names rule 23 makes the module's public service surface.
SERVICE_SURFACE = [
    "CurrentOrgError",
    "OrgsError",
]


def test_services_publishes_exactly_the_declared_surface() -> None:
    """``__all__`` is the module's public surface, and nothing else is public."""
    assert services.__all__ == SERVICE_SURFACE
    for name in SERVICE_SURFACE:
        assert hasattr(services, name), f"{name} is missing from services.py"


def test_services_reexports_the_module_error_bases() -> None:
    """Rule 10: ``services.py`` re-exports the one ``OrgsError`` base."""
    assert services.OrgsError is OrgsError
    assert services.CurrentOrgError is CurrentOrgError
    assert issubclass(CurrentOrgError, OrgsError)
