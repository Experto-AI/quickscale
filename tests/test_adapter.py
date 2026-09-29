"""Focused tests for the backups manifest adapter."""

from __future__ import annotations

import pytest

from quickscale_core.runtime.manifest import ManifestError
from quickscale_modules_backups.adapter import (
    _backups_manifest_adapter,
    get_manifest_adapter,
)


def test_get_manifest_adapter_returns_callable() -> None:
    assert get_manifest_adapter() is _backups_manifest_adapter


def test_local_defaults_carry_conventional_credential_references() -> None:
    spec = _backups_manifest_adapter({})

    assert spec.settings["QUICKSCALE_BACKUPS_TARGET_MODE"] == "local"
    assert (
        spec.settings["QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR"]
        == "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID"
    )
    assert (
        spec.settings["QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR"]
        == "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY"
    )


def test_private_remote_projects_the_declared_settings() -> None:
    spec = _backups_manifest_adapter(
        {
            "target_mode": "private_remote",
            "remote_bucket_name": "private-bucket",
            "remote_region_name": "eu-west-1",
        }
    )

    assert spec.settings["QUICKSCALE_BACKUPS_TARGET_MODE"] == "private_remote"
    assert spec.settings["QUICKSCALE_BACKUPS_REMOTE_BUCKET_NAME"] == "private-bucket"
    assert spec.settings["QUICKSCALE_BACKUPS_REMOTE_REGION_NAME"] == "eu-west-1"
    assert (
        spec.settings["QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR"]
        == "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID"
    )


def test_integer_and_boolean_settings_are_coerced() -> None:
    spec = _backups_manifest_adapter({"retention_days": 7, "automation_enabled": True})

    assert spec.settings["QUICKSCALE_BACKUPS_RETENTION_DAYS"] == 7
    assert spec.settings["QUICKSCALE_BACKUPS_AUTOMATION_ENABLED"] is True


@pytest.mark.parametrize("target_mode", ["unsupported", "remote", "", None])
def test_unsupported_target_mode_is_rejected(target_mode: object) -> None:
    with pytest.raises(ManifestError, match="modules.backups.target_mode"):
        _backups_manifest_adapter({"target_mode": target_mode})


@pytest.mark.parametrize("target_mode", ["LOCAL", " local "])
def test_target_mode_is_normalized(target_mode: str) -> None:
    spec = _backups_manifest_adapter({"target_mode": target_mode})

    assert spec.settings["QUICKSCALE_BACKUPS_TARGET_MODE"] == "local"


def test_private_remote_without_its_remote_settings_is_rejected() -> None:
    with pytest.raises(ManifestError, match="remote_bucket_name"):
        _backups_manifest_adapter({"target_mode": "private_remote"})


@pytest.mark.parametrize(
    "option_name", ["naming_prefix", "local_directory", "remote_prefix"]
)
def test_blank_free_text_values_are_rejected(option_name: str) -> None:
    with pytest.raises(ManifestError, match=option_name):
        _backups_manifest_adapter({option_name: "   "})
