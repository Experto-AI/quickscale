"""Tests for module manifest schema"""

from quickscale_core.manifest import (
    ConfigOption,
    ManagedFileDeclaration,
    ModuleManifest,
)
from quickscale_core.manifest.schema import MANAGED_FILE_ROOT_PREFIX


class TestConfigOption:
    """Tests for ConfigOption dataclass"""

    def test_config_option_creation(self) -> None:
        """Test basic config option creation"""
        option = ConfigOption(
            name="test_option",
            option_type="string",
            default="test_value",
        )
        assert option.name == "test_option"
        assert option.option_type == "string"
        assert option.default == "test_value"
        assert option.django_setting is None
        assert option.mutability == "immutable"

    def test_mutable_option_with_django_setting(self) -> None:
        """Test mutable option with django setting mapping"""
        option = ConfigOption(
            name="registration_enabled",
            option_type="boolean",
            default=True,
            django_setting="ACCOUNT_ALLOW_REGISTRATION",
            mutability="mutable",
        )
        assert option.name == "registration_enabled"
        assert option.is_mutable is True
        assert option.django_setting == "ACCOUNT_ALLOW_REGISTRATION"

    def test_immutable_option(self) -> None:
        """Test immutable option"""
        option = ConfigOption(
            name="auth_method",
            option_type="string",
            default="email_username",
            mutability="immutable",
        )
        assert option.is_mutable is False
        assert option.django_setting is None


class TestModuleManifest:
    """Tests for ModuleManifest dataclass"""

    def test_manifest_creation(self) -> None:
        """Test basic manifest creation"""
        mutable_option = ConfigOption(
            name="registration_enabled",
            option_type="boolean",
            default=True,
            django_setting="ACCOUNT_ALLOW_REGISTRATION",
            mutability="mutable",
        )
        immutable_option = ConfigOption(
            name="auth_method",
            option_type="string",
            default="email_username",
            mutability="immutable",
        )
        manifest = ModuleManifest(
            name="auth",
            version="0.71.0",
            mutable_options={"registration_enabled": mutable_option},
            immutable_options={"auth_method": immutable_option},
            required_modules=["orgs"],
        )
        assert manifest.name == "auth"
        assert manifest.version == "0.71.0"
        assert len(manifest.mutable_options) == 1
        assert len(manifest.immutable_options) == 1
        assert manifest.required_modules == ["orgs"]

    def test_get_option_mutable(self) -> None:
        """Test get_option returns mutable option"""
        mutable_option = ConfigOption(
            name="session_timeout",
            option_type="integer",
            default=1209600,
            django_setting="SESSION_COOKIE_AGE",
            mutability="mutable",
        )
        manifest = ModuleManifest(
            name="auth",
            version="0.71.0",
            mutable_options={"session_timeout": mutable_option},
            immutable_options={},
        )
        option = manifest.get_option("session_timeout")
        assert option is not None
        assert option.name == "session_timeout"
        assert option.is_mutable is True

    def test_get_option_immutable(self) -> None:
        """Test get_option returns immutable option"""
        immutable_option = ConfigOption(
            name="social_providers",
            option_type="array",
            default=[],
            mutability="immutable",
        )
        manifest = ModuleManifest(
            name="auth",
            version="0.71.0",
            mutable_options={},
            immutable_options={"social_providers": immutable_option},
        )
        option = manifest.get_option("social_providers")
        assert option is not None
        assert option.name == "social_providers"
        assert option.is_mutable is False

    def test_get_option_not_found(self) -> None:
        """Test get_option returns None for unknown option"""
        manifest = ModuleManifest(
            name="auth",
            version="0.71.0",
            mutable_options={},
            immutable_options={},
        )
        option = manifest.get_option("unknown_option")
        assert option is None

    def test_is_option_mutable(self) -> None:
        """Test is_option_mutable method"""
        mutable_option = ConfigOption(
            name="registration_enabled",
            option_type="boolean",
            default=True,
            django_setting="ACCOUNT_ALLOW_REGISTRATION",
            mutability="mutable",
        )
        immutable_option = ConfigOption(
            name="auth_method",
            option_type="string",
            default="email_username",
            mutability="immutable",
        )
        manifest = ModuleManifest(
            name="auth",
            version="0.71.0",
            mutable_options={"registration_enabled": mutable_option},
            immutable_options={"auth_method": immutable_option},
        )
        assert manifest.is_option_mutable("registration_enabled") is True
        assert manifest.is_option_mutable("auth_method") is False
        # Unknown option defaults to immutable (safe)
        assert manifest.is_option_mutable("unknown") is False

    def test_get_django_settings_mapping(self) -> None:
        """Test get_django_settings_mapping method"""
        mutable1 = ConfigOption(
            name="registration_enabled",
            option_type="boolean",
            default=True,
            django_setting="ACCOUNT_ALLOW_REGISTRATION",
            mutability="mutable",
        )
        mutable2 = ConfigOption(
            name="session_timeout",
            option_type="integer",
            default=1209600,
            django_setting="SESSION_COOKIE_AGE",
            mutability="mutable",
        )
        manifest = ModuleManifest(
            name="auth",
            version="0.71.0",
            mutable_options={
                "registration_enabled": mutable1,
                "session_timeout": mutable2,
            },
            immutable_options={},
        )
        mapping = manifest.get_django_settings_mapping()
        assert mapping == {
            "registration_enabled": "ACCOUNT_ALLOW_REGISTRATION",
            "session_timeout": "SESSION_COOKIE_AGE",
        }

    def test_empty_manifest(self) -> None:
        """Test manifest with no options"""
        manifest = ModuleManifest(
            name="minimal",
            version="1.0.0",
            mutable_options={},
            immutable_options={},
        )
        assert manifest.name == "minimal"
        assert manifest.get_option("any") is None
        assert manifest.is_option_mutable("any") is False
        assert manifest.get_django_settings_mapping() == {}

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

        assert manifest.get_all_options() == {
            "reg_enabled": mutable,
            "auth_method": immutable,
        }

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
        assert list(manifest.get_all_options().keys()) == ["timeout"]

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
        assert list(manifest.get_all_options().keys()) == ["provider"]

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
        assert manifest.get_defaults() == {
            "reg_enabled": True,
            "auth_method": "email",
        }

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
        """get_defaults value matches the ConfigOption default attribute."""
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
        assert manifest.get_defaults()["max_retries"] == 3


# ---------------------------------------------------------------------------
# ManagedFileDeclaration
# ---------------------------------------------------------------------------


class TestManagedFileDeclaration:
    """Tests for the ManagedFileDeclaration dataclass."""

    def test_creation(self) -> None:
        """ManagedFileDeclaration stores key, renderer, and output_path."""
        decl = ManagedFileDeclaration(
            key="social_link_tree",
            renderer="social/link_tree.html",
            output_path="quickscale_managed/social/link_tree.html",
        )
        assert decl.key == "social_link_tree"
        assert decl.renderer == "social/link_tree.html"
        assert decl.output_path == "quickscale_managed/social/link_tree.html"

    def test_frozen(self) -> None:
        """ManagedFileDeclaration instances are immutable."""
        import pytest

        decl = ManagedFileDeclaration(
            key="k", renderer="r", output_path="quickscale_managed/f.html"
        )
        with pytest.raises(AttributeError):
            decl.key = "other"  # type: ignore[misc]

    def test_is_within_managed_root_true(self) -> None:
        """is_within_managed_root returns True for valid paths."""
        decl = ManagedFileDeclaration(
            key="k",
            renderer="r",
            output_path="quickscale_managed/social/embeds.html",
        )
        assert decl.is_within_managed_root is True

    def test_is_within_managed_root_false(self) -> None:
        """is_within_managed_root returns False for paths outside the prefix."""
        decl = ManagedFileDeclaration(
            key="k",
            renderer="r",
            output_path="templates/escaped.html",
        )
        assert decl.is_within_managed_root is False

    def test_managed_file_root_prefix_constant(self) -> None:
        """The root prefix constant is the expected value."""
        assert MANAGED_FILE_ROOT_PREFIX == "quickscale_managed/"


class TestModuleManifestManagedFiles:
    """Tests for ModuleManifest.managed_files field."""

    def test_default_empty(self) -> None:
        """ModuleManifest defaults managed_files to empty dict."""
        manifest = ModuleManifest(name="m", version="1.0.0")
        assert manifest.managed_files == {}

    def test_managed_files_populated(self) -> None:
        """ModuleManifest accepts managed_files declarations."""
        decl = ManagedFileDeclaration(
            key="social_link_tree",
            renderer="social/link_tree.html",
            output_path="quickscale_managed/social/link_tree.html",
        )
        manifest = ModuleManifest(
            name="social",
            version="0.79.0",
            managed_files={"social_link_tree": decl},
        )
        assert "social_link_tree" in manifest.managed_files
        assert manifest.managed_files["social_link_tree"] is decl

    def test_managed_files_not_in_defaults(self) -> None:
        """Managed-file declarations do not appear in config option defaults.

        This proves that managed_files live outside the mutable/immutable
        config option system and cannot leak into config defaults.
        """
        decl = ManagedFileDeclaration(
            key="social_link_tree",
            renderer="social/link_tree.html",
            output_path="quickscale_managed/social/link_tree.html",
        )
        manifest = ModuleManifest(
            name="social",
            version="0.79.0",
            managed_files={"social_link_tree": decl},
        )
        defaults = manifest.get_defaults()
        assert "social_link_tree" not in defaults
        assert defaults == {}

    def test_managed_files_not_in_all_options(self) -> None:
        """Managed-file declarations are not returned by get_all_options."""
        decl = ManagedFileDeclaration(
            key="link_tree",
            renderer="r",
            output_path="quickscale_managed/f.html",
        )
        manifest = ModuleManifest(
            name="m",
            version="1.0.0",
            managed_files={"link_tree": decl},
        )
        assert "link_tree" not in manifest.get_all_options()
