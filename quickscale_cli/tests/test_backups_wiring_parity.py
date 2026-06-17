"""Wiring-parity tests for the manifest-driven backups path (C5).

Compares the legacy ``_backups_wiring`` builder output against the manifest-driven
``build_manifest_wiring_spec("backups", ...)`` for every option case, asserting
full :class:`~quickscale_core.module_wiring.ModuleWiringSpec` dataclass equality.

The key gnarly case is the conditional private_remote env-var defaulting:
when ``target_mode == "private_remote"`` and no env-var names are supplied,
the spec must use the DEFAULT_BACKUPS_REMOTE_* constant values.  This is
reproduced via the post-resolution hook approach in the backups adapter.

Scope
-----
* Default options (local target_mode)
* private_remote without env vars (env-var defaulting)
* private_remote with custom env vars
* Various other option overrides
"""

from __future__ import annotations


from wiring_parity import assert_wiring_parity


class TestBackupsWiringParityDefaults:
    """Default options must produce equal specs from both paths."""

    def test_empty_options(self) -> None:
        assert_wiring_parity("backups", [{}])

    def test_default_apps(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("backups", {})
        assert spec.apps == ("quickscale_modules_backups",)

    def test_default_target_mode_is_local(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("backups", {})
        assert spec.settings["QUICKSCALE_BACKUPS_TARGET_MODE"] == "local"

    def test_default_env_var_keys_are_empty_for_local(self) -> None:
        """Local mode should have empty env-var names."""
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("backups", {})
        assert spec.settings["QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR"] == ""
        assert (
            spec.settings["QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR"] == ""
        )


class TestBackupsWiringParityPrivateRemote:
    """private_remote conditional env-var defaulting must match legacy exactly."""

    def test_private_remote_without_env_vars_defaults_applied(self) -> None:
        """Env-var defaulting is the gnarly case — parity must hold."""
        assert_wiring_parity("backups", [{"target_mode": "private_remote"}])

    def test_private_remote_default_env_var_values(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec
        from quickscale_cli.backups_manifest import (
            DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
            DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
        )

        spec = build_manifest_wiring_spec("backups", {"target_mode": "private_remote"})
        assert (
            spec.settings["QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR"]
            == DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR
        )
        assert (
            spec.settings["QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR"]
            == DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR
        )

    def test_private_remote_with_custom_env_vars(self) -> None:
        assert_wiring_parity(
            "backups",
            [
                {
                    "target_mode": "private_remote",
                    "remote_access_key_id_env_var": "MY_KEY",
                    "remote_secret_access_key_env_var": "MY_SECRET",
                }
            ],
        )

    def test_private_remote_with_bucket(self) -> None:
        assert_wiring_parity(
            "backups",
            [{"target_mode": "private_remote", "remote_bucket_name": "my-bucket"}],
        )


class TestBackupsWiringParityOverrides:
    """Other option overrides must produce equal specs from both paths."""

    def test_retention_days(self) -> None:
        assert_wiring_parity("backups", [{"retention_days": 7}])

    def test_naming_prefix(self) -> None:
        assert_wiring_parity("backups", [{"naming_prefix": "myapp"}])

    def test_automation_enabled(self) -> None:
        assert_wiring_parity("backups", [{"automation_enabled": True}])

    def test_custom_schedule(self) -> None:
        assert_wiring_parity("backups", [{"schedule": "0 3 * * *"}])

    def test_remote_bucket_and_endpoint(self) -> None:
        assert_wiring_parity(
            "backups",
            [
                {
                    "target_mode": "private_remote",
                    "remote_bucket_name": "my-backups",
                    "remote_endpoint_url": "https://s3.example.com",
                    "remote_region_name": "us-east-1",
                }
            ],
        )

    def test_multiple_cases_batch(self) -> None:
        assert_wiring_parity(
            "backups",
            [
                {},
                {"target_mode": "private_remote"},
                {
                    "target_mode": "private_remote",
                    "remote_access_key_id_env_var": "MY_KEY",
                },
                {"retention_days": 30, "naming_prefix": "prod"},
                {"automation_enabled": True, "schedule": "0 1 * * *"},
            ],
        )
