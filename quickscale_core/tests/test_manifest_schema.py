"""Tests for module manifest schema"""


from quickscale_core.manifest import ConfigOption, ModuleManifest


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
        )
        assert manifest.name == "auth"
        assert manifest.version == "0.71.0"
        assert len(manifest.mutable_options) == 1
        assert len(manifest.immutable_options) == 1

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
