"""Additional tests for manifest schema methods not covered by existing tests."""

from quickscale_core.manifest.schema import ConfigOption, ModuleManifest


class TestGetAllOptions:
    """Tests for ModuleManifest.get_all_options method."""

    def test_get_all_options_returns_combined_dict(self) -> None:
        """get_all_options merges mutable and immutable options."""
        mutable = ConfigOption(
            name="reg_enabled",
            option_type="boolean",
            default=True,
            django_setting="ACCOUNT_ALLOW_REGISTRATION",
            mutability="mutable",
        )
        immutable = ConfigOption(
            name="auth_method",
            option_type="string",
            default="email",
            mutability="immutable",
        )
        manifest = ModuleManifest(
            name="auth",
            version="1.0.0",
            mutable_options={"reg_enabled": mutable},
            immutable_options={"auth_method": immutable},
        )
        all_opts = manifest.get_all_options()
        assert "reg_enabled" in all_opts
        assert "auth_method" in all_opts
        assert len(all_opts) == 2

    def test_get_all_options_empty_manifest(self) -> None:
        """get_all_options returns empty dict for manifest with no options."""
        manifest = ModuleManifest(name="minimal", version="1.0.0")
        assert manifest.get_all_options() == {}

    def test_get_all_options_only_mutable(self) -> None:
        """get_all_options works with only mutable options present."""
        mutable = ConfigOption(
            name="timeout",
            option_type="integer",
            default=3600,
            django_setting="SESSION_TIMEOUT",
            mutability="mutable",
        )
        manifest = ModuleManifest(
            name="sessions",
            version="1.0.0",
            mutable_options={"timeout": mutable},
            immutable_options={},
        )
        all_opts = manifest.get_all_options()
        assert list(all_opts.keys()) == ["timeout"]

    def test_get_all_options_only_immutable(self) -> None:
        """get_all_options works with only immutable options present."""
        immutable = ConfigOption(
            name="provider",
            option_type="string",
            default="local",
            mutability="immutable",
        )
        manifest = ModuleManifest(
            name="auth",
            version="1.0.0",
            mutable_options={},
            immutable_options={"provider": immutable},
        )
        all_opts = manifest.get_all_options()
        assert list(all_opts.keys()) == ["provider"]


class TestGetDefaults:
    """Tests for ModuleManifest.get_defaults method."""

    def test_get_defaults_returns_all_defaults(self) -> None:
        """get_defaults returns defaults for both mutable and immutable options."""
        mutable = ConfigOption(
            name="reg_enabled",
            option_type="boolean",
            default=True,
            django_setting="ACCOUNT_ALLOW_REGISTRATION",
            mutability="mutable",
        )
        immutable = ConfigOption(
            name="auth_method",
            option_type="string",
            default="email",
            mutability="immutable",
        )
        manifest = ModuleManifest(
            name="auth",
            version="1.0.0",
            mutable_options={"reg_enabled": mutable},
            immutable_options={"auth_method": immutable},
        )
        defaults = manifest.get_defaults()
        assert defaults == {"reg_enabled": True, "auth_method": "email"}

    def test_get_defaults_empty_manifest(self) -> None:
        """get_defaults returns empty dict when no options."""
        manifest = ModuleManifest(name="minimal", version="1.0.0")
        assert manifest.get_defaults() == {}

    def test_get_defaults_with_none_default(self) -> None:
        """get_defaults correctly returns None as a default value."""
        option = ConfigOption(
            name="optional_key",
            option_type="string",
            default=None,
            mutability="immutable",
        )
        manifest = ModuleManifest(
            name="mod",
            version="1.0.0",
            mutable_options={},
            immutable_options={"optional_key": option},
        )
        defaults = manifest.get_defaults()
        assert "optional_key" in defaults
        assert defaults["optional_key"] is None

    def test_get_defaults_reflects_option_defaults(self) -> None:
        """get_defaults value matches the ConfigOption's default attribute."""
        option = ConfigOption(
            name="max_retries",
            option_type="integer",
            default=3,
            mutability="immutable",
        )
        manifest = ModuleManifest(
            name="retry",
            version="1.0.0",
            immutable_options={"max_retries": option},
        )
        defaults = manifest.get_defaults()
        assert defaults["max_retries"] == 3
