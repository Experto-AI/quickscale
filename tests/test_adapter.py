"""Focused tests for the forms manifest adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.module_wiring import ModuleWiringSpec

from quickscale_modules_forms.adapter import (
    _forms_manifest_adapter,
    _forms_post_hook,
    get_manifest_adapter,
)


def test_get_manifest_adapter_returns_callable() -> None:
    assert callable(get_manifest_adapter())


def test_missing_required_setting_raises_key_error() -> None:
    with pytest.raises(KeyError, match="QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE"):
        _forms_post_hook(ModuleWiringSpec(), {})


def test_post_hook_coerces_all_settings() -> None:
    result = _forms_post_hook(
        ModuleWiringSpec(
            settings={
                "QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE": "25",
                "QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED": 1,
                "QUICKSCALE_FORMS_RATE_LIMIT": 5,
                "QUICKSCALE_FORMS_RETENTION_DAYS": "365",
                "QUICKSCALE_FORMS_API_ENABLED": 0,
            }
        ),
        {},
    )
    assert result.settings == {
        "QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE": 25,
        "QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED": True,
        "QUICKSCALE_FORMS_RATE_LIMIT": "5",
        "QUICKSCALE_FORMS_RETENTION_DAYS": 365,
        "QUICKSCALE_FORMS_API_ENABLED": False,
        "REST_FRAMEWORK": {
            "DEFAULT_THROTTLE_RATES": {"quickscale_forms_submit": "5"},
        },
    }


@patch("quickscale_modules_forms.adapter.build_generic_manifest_spec")
def test_adapter_delegates_to_generic_manifest(mock_build: MagicMock) -> None:
    mock_build.return_value = ModuleWiringSpec()
    result = _forms_manifest_adapter({"enabled": True})
    mock_build.assert_called_once_with(
        "forms", {"enabled": True}, post_hook=_forms_post_hook
    )
    assert isinstance(result, ModuleWiringSpec)
