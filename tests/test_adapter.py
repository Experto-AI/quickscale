"""Focused tests for the forms manifest adapter.

The generic manifest boundary owns forms' option defaults, normalization,
checks, and projections; these tests pin the adapter's remaining contract —
the throttle scope, the off-switch transformation, and the sentinel.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.manifest import ManifestError
from quickscale_core.module_wiring import ModuleWiringSpec

from quickscale_modules_forms.adapter import (
    _forms_manifest_adapter,
    _forms_post_hook,
    get_manifest_adapter,
)


def test_get_manifest_adapter_returns_callable() -> None:
    assert callable(get_manifest_adapter())


@pytest.mark.parametrize(
    ("option_name", "value"),
    [
        ("submissions_per_page", "25"),
        ("per_page", True),
        ("spam_protection_enabled", 1),
        ("rate_limit", "no-rate"),
        ("retention_days", -1),
    ],
)
def test_wrong_shaped_values_are_refused(option_name: str, value: object) -> None:
    """A raw value of the wrong shape (or range/pattern) is refused."""
    with pytest.raises(ManifestError, match="modules.forms."):
        _forms_manifest_adapter({option_name: value})


def test_manifest_projects_settings_and_throttle_scope() -> None:
    result = _forms_manifest_adapter({"rate_limit": " 10/minute "})

    assert result.settings["QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE"] == 25
    assert result.settings["QUICKSCALE_FORMS_PER_PAGE"] == 25
    assert result.settings["QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED"] is True
    assert result.settings["QUICKSCALE_FORMS_RATE_LIMIT"] == "10/minute"
    assert result.settings["QUICKSCALE_FORMS_RETENTION_DAYS"] == 365
    assert result.settings["QUICKSCALE_FORMS_API_ENABLED"] is True
    assert result.settings["REST_FRAMEWORK"] == {
        "DEFAULT_THROTTLE_RATES": {"quickscale_forms_submit": "10/minute"},
    }


def test_disabled_module_drops_url_mounts_and_keeps_apps() -> None:
    """Rule 1 (D3): off keeps the app and settings but mounts no URLs."""
    result = _forms_post_hook(
        ModuleWiringSpec(
            apps=("rest_framework", "django_filters", "quickscale_modules_forms"),
            settings={"QUICKSCALE_FORMS_RATE_LIMIT": "5/hour"},
            pre_home_url_includes=(),
            url_includes=(("forms/", "quickscale_modules_forms.urls"),),
        ),
        {"enabled": False},
    )
    assert result.url_includes == ()
    assert result.pre_home_url_includes == ()
    assert result.apps == (
        "rest_framework",
        "django_filters",
        "quickscale_modules_forms",
    )
    assert result.settings["REST_FRAMEWORK"] == {
        "DEFAULT_THROTTLE_RATES": {"quickscale_forms_submit": "5/hour"},
    }


@patch("quickscale_modules_forms.adapter.build_generic_manifest_spec")
def test_adapter_delegates_to_generic_manifest(mock_build: MagicMock) -> None:
    mock_build.return_value = ModuleWiringSpec()
    result = _forms_manifest_adapter({"enabled": True})
    mock_build.assert_called_once_with(
        "forms", {"enabled": True}, post_hook=_forms_post_hook
    )
    assert isinstance(result, ModuleWiringSpec)
