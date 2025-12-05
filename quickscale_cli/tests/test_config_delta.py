"""Tests for config delta detection (mutable/immutable changes)"""

import pytest

from quickscale_core.manifest import ConfigOption, ModuleManifest
from quickscale_cli.schema.delta import (
    ConfigChange,
    ModuleConfigDelta,
    compute_delta,
    format_delta,
)
from quickscale_cli.schema.config_schema import (
    QuickScaleConfig,
    ProjectConfig,
    ModuleConfig,
    DockerConfig,
)
from quickscale_cli.schema.state_schema import (
    QuickScaleState,
    ProjectState,
    ModuleState,
)


@pytest.fixture
def auth_manifest() -> ModuleManifest:
    """Create auth module manifest for testing"""
    return ModuleManifest(
        name="auth",
        version="0.71.0",
        mutable_options={
            "registration_enabled": ConfigOption(
                name="registration_enabled",
                option_type="boolean",
                default=True,
                django_setting="ACCOUNT_ALLOW_REGISTRATION",
                mutability="mutable",
            ),
            "session_cookie_age": ConfigOption(
                name="session_cookie_age",
                option_type="integer",
                default=1209600,
                django_setting="SESSION_COOKIE_AGE",
                mutability="mutable",
            ),
        },
        immutable_options={
            "authentication_method": ConfigOption(
                name="authentication_method",
                option_type="string",
                default="email_username",
                mutability="immutable",
            ),
        },
    )


@pytest.fixture
def base_config() -> QuickScaleConfig:
    """Create base config for testing"""
    return QuickScaleConfig(
        version="0.71.0",
        project=ProjectConfig(name="testproject", theme="html"),
        modules={
            "auth": ModuleConfig(
                name="auth",
                options={
                    "registration_enabled": True,
                    "session_cookie_age": 1209600,
                    "authentication_method": "email_username",
                },
            )
        },
        docker=DockerConfig(start=False, build=False),
    )


@pytest.fixture
def base_state() -> QuickScaleState:
    """Create base state for testing"""
    return QuickScaleState(
        version="1",
        project=ProjectState(
            name="testproject",
            theme="html",
            created_at="2024-01-01T00:00:00",
            last_applied="2024-01-01T00:00:00",
        ),
        modules={
            "auth": ModuleState(
                name="auth",
                version="0.71.0",
                embedded_at="2024-01-01T00:00:00",
                options={
                    "registration_enabled": True,
                    "session_cookie_age": 1209600,
                    "authentication_method": "email_username",
                },
            )
        },
    )


class TestConfigChange:
    """Tests for ConfigChange dataclass"""

    def test_config_change_creation(self) -> None:
        """Test creating a config change"""
        change = ConfigChange(
            option_name="registration_enabled",
            old_value=True,
            new_value=False,
            django_setting="ACCOUNT_ALLOW_REGISTRATION",
            is_mutable=True,
        )
        assert change.option_name == "registration_enabled"
        assert change.old_value is True
        assert change.new_value is False
        assert change.is_mutable is True


class TestModuleConfigDelta:
    """Tests for ModuleConfigDelta dataclass"""

    def test_has_changes(self) -> None:
        """Test has_changes property"""
        mutable_change = ConfigChange(
            option_name="test",
            old_value=1,
            new_value=2,
            django_setting="TEST",
            is_mutable=True,
        )
        delta = ModuleConfigDelta(
            module_name="auth",
            mutable_changes=[mutable_change],
            immutable_changes=[],
        )
        assert delta.has_changes is True
        assert delta.has_mutable_changes is True
        assert delta.has_immutable_changes is False

    def test_no_changes(self) -> None:
        """Test delta with no changes"""
        delta = ModuleConfigDelta(
            module_name="auth",
            mutable_changes=[],
            immutable_changes=[],
        )
        assert delta.has_changes is False


class TestComputeDeltaWithManifests:
    """Tests for compute_delta with manifests"""

    def test_no_config_changes(
        self,
        base_config: QuickScaleConfig,
        base_state: QuickScaleState,
        auth_manifest: ModuleManifest,
    ) -> None:
        """Test compute_delta with no config changes"""
        manifests = {"auth": auth_manifest}
        delta = compute_delta(base_config, base_state, manifests)

        assert delta.has_mutable_config_changes is False
        assert delta.has_immutable_config_changes is False

    def test_mutable_config_change(
        self,
        base_config: QuickScaleConfig,
        base_state: QuickScaleState,
        auth_manifest: ModuleManifest,
    ) -> None:
        """Test detecting mutable config change"""
        # Change a mutable option
        base_config.modules["auth"].options["registration_enabled"] = False

        manifests = {"auth": auth_manifest}
        delta = compute_delta(base_config, base_state, manifests)

        assert delta.has_mutable_config_changes is True
        assert delta.has_immutable_config_changes is False

        mutable_changes = list(delta.get_all_mutable_changes())
        assert len(mutable_changes) == 1
        module_name, change = mutable_changes[0]
        assert module_name == "auth"
        assert change.option_name == "registration_enabled"
        assert change.old_value is True
        assert change.new_value is False
        assert change.django_setting == "ACCOUNT_ALLOW_REGISTRATION"

    def test_immutable_config_change(
        self,
        base_config: QuickScaleConfig,
        base_state: QuickScaleState,
        auth_manifest: ModuleManifest,
    ) -> None:
        """Test detecting immutable config change"""
        # Change an immutable option
        base_config.modules["auth"].options["authentication_method"] = "email_only"

        manifests = {"auth": auth_manifest}
        delta = compute_delta(base_config, base_state, manifests)

        assert delta.has_immutable_config_changes is True

        immutable_changes = list(delta.get_all_immutable_changes())
        assert len(immutable_changes) == 1
        module_name, change = immutable_changes[0]
        assert module_name == "auth"
        assert change.option_name == "authentication_method"
        assert change.old_value == "email_username"
        assert change.new_value == "email_only"
        assert change.is_mutable is False

    def test_mixed_config_changes(
        self,
        base_config: QuickScaleConfig,
        base_state: QuickScaleState,
        auth_manifest: ModuleManifest,
    ) -> None:
        """Test detecting both mutable and immutable changes"""
        # Change both mutable and immutable options
        base_config.modules["auth"].options["registration_enabled"] = False
        base_config.modules["auth"].options["authentication_method"] = "email_only"

        manifests = {"auth": auth_manifest}
        delta = compute_delta(base_config, base_state, manifests)

        assert delta.has_mutable_config_changes is True
        assert delta.has_immutable_config_changes is True
        assert delta.has_changes is True

    def test_compute_delta_without_manifests(
        self,
        base_config: QuickScaleConfig,
        base_state: QuickScaleState,
    ) -> None:
        """Test compute_delta without manifests (backward compatible)"""
        delta = compute_delta(base_config, base_state)

        # Should not error, but won't detect config changes
        assert delta.has_mutable_config_changes is False
        assert delta.has_immutable_config_changes is False


class TestFormatDelta:
    """Tests for format_delta with config changes"""

    def test_format_mutable_changes(
        self,
        base_config: QuickScaleConfig,
        base_state: QuickScaleState,
        auth_manifest: ModuleManifest,
    ) -> None:
        """Test formatting delta with mutable changes"""
        base_config.modules["auth"].options["registration_enabled"] = False

        manifests = {"auth": auth_manifest}
        delta = compute_delta(base_config, base_state, manifests)
        output = format_delta(delta)

        assert "mutable" in output.lower()
        assert "registration_enabled" in output

    def test_format_immutable_changes(
        self,
        base_config: QuickScaleConfig,
        base_state: QuickScaleState,
        auth_manifest: ModuleManifest,
    ) -> None:
        """Test formatting delta with immutable changes"""
        base_config.modules["auth"].options["authentication_method"] = "email_only"

        manifests = {"auth": auth_manifest}
        delta = compute_delta(base_config, base_state, manifests)
        output = format_delta(delta)

        assert "immutable" in output.lower()
        assert "authentication_method" in output
        assert (
            "blocked" in output.lower() or "cannot" in output.lower() or "!" in output
        )
