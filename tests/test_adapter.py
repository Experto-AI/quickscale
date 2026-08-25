"""Focused tests for the backups manifest adapter."""

from __future__ import annotations

import pytest

from quickscale_modules_backups.adapter import (
    _backups_manifest_adapter,
    get_manifest_adapter,
)


def test_get_manifest_adapter_returns_callable() -> None:
    assert get_manifest_adapter() is _backups_manifest_adapter


def test_local_defaults_preserve_empty_remote_credential_references() -> None:
    spec = _backups_manifest_adapter({})

    assert spec.settings["QUICKSCALE_BACKUPS_TARGET_MODE"] == "local"
    assert spec.settings["QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR"] == ""
    assert spec.settings["QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR"] == ""


def test_private_remote_defaults_credential_references() -> None:
    spec = _backups_manifest_adapter({"target_mode": "private_remote"})

    assert (
        spec.settings["QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR"]
        == "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID"
    )
    assert (
        spec.settings["QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR"]
        == "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY"
    )


def test_unsupported_target_mode_falls_back_to_local() -> None:
    spec = _backups_manifest_adapter({"target_mode": "unsupported"})

    assert spec.settings["QUICKSCALE_BACKUPS_TARGET_MODE"] == "local"


@pytest.mark.parametrize("target_mode", ["LOCAL", " local "])
def test_target_mode_is_normalized(target_mode: str) -> None:
    spec = _backups_manifest_adapter({"target_mode": target_mode})

    assert spec.settings["QUICKSCALE_BACKUPS_TARGET_MODE"] == "local"
