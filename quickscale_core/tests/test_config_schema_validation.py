"""Tests for config_schema validation error paths and project identity."""

from __future__ import annotations

from pathlib import Path

import pytest

from quickscale_core.schema.config_schema import (
    ConfigValidationError,
    QuickScaleConfig,
    parse_config,
    validate_config,
)
from quickscale_core.utils.project_identity import (
    ProjectIdentityResolutionError,
    derive_package_from_slug,
    identity_from_config,
    load_identity_from_config_file,
    resolve_project_identity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_VALID_YAML = """\
version: "1"
project:
  slug: myapp
  package: myapp
"""


def _valid_yaml_with_modules(modules_yaml: str) -> str:
    return _MINIMAL_VALID_YAML + f"modules:\n{modules_yaml}\n"


# ---------------------------------------------------------------------------
# ConfigValidationError
# ---------------------------------------------------------------------------


class TestConfigValidationError:
    def test_message_only(self) -> None:
        err = ConfigValidationError("bad thing")
        assert "bad thing" in str(err)
        assert err.line is None
        assert err.suggestion is None

    def test_message_with_line(self) -> None:
        err = ConfigValidationError("bad thing", line=5)
        assert "Line 5" in str(err)
        assert "bad thing" in str(err)

    def test_message_with_line_and_suggestion(self) -> None:
        err = ConfigValidationError("bad thing", line=3, suggestion="try this")
        text = str(err)
        assert "Line 3" in text
        assert "Suggestion" in text
        assert "try this" in text


# ---------------------------------------------------------------------------
# validate_config: version errors
# ---------------------------------------------------------------------------


class TestValidateVersion:
    def test_missing_version(self) -> None:
        with pytest.raises(ConfigValidationError, match="version"):
            validate_config("project:\n  slug: x\n  package: x\n")

    def test_unsupported_version(self) -> None:
        with pytest.raises(ConfigValidationError, match="Unsupported version"):
            validate_config('version: "2"\nproject:\n  slug: x\n  package: x\n')


# ---------------------------------------------------------------------------
# validate_config: project section errors
# ---------------------------------------------------------------------------


class TestValidateProject:
    def test_missing_project(self) -> None:
        with pytest.raises(ConfigValidationError, match="project"):
            validate_config('version: "1"\n')

    def test_project_not_mapping(self) -> None:
        with pytest.raises(ConfigValidationError, match="mapping"):
            validate_config('version: "1"\nproject: oops\n')

    def test_missing_slug(self) -> None:
        with pytest.raises(ConfigValidationError, match="slug"):
            validate_config('version: "1"\nproject:\n  package: myapp\n')

    def test_missing_package(self) -> None:
        with pytest.raises(ConfigValidationError, match="package"):
            validate_config('version: "1"\nproject:\n  slug: myapp\n')

    def test_empty_slug(self) -> None:
        with pytest.raises(ConfigValidationError, match="slug"):
            validate_config('version: "1"\nproject:\n  slug: ""\n  package: myapp\n')

    def test_invalid_package_name_not_identifier(self) -> None:
        with pytest.raises(ConfigValidationError, match="package"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: "123bad"\n'
            )

    def test_invalid_package_name_keyword(self) -> None:
        with pytest.raises(ConfigValidationError, match="package"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: "class"\n'
            )

    def test_invalid_package_name_uppercase(self) -> None:
        with pytest.raises(ConfigValidationError, match="package"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: "MyApp"\n'
            )

    def test_unknown_project_key(self) -> None:
        with pytest.raises(ConfigValidationError, match="Unknown key"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "  them: showcase_react\n"
            )

    def test_unknown_theme(self) -> None:
        with pytest.raises(ConfigValidationError, match="theme"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "  theme: nonexistent\n"
            )


# ---------------------------------------------------------------------------
# validate_config: docker section errors
# ---------------------------------------------------------------------------


class TestValidateDocker:
    def test_docker_not_mapping(self) -> None:
        with pytest.raises(ConfigValidationError, match="docker"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "docker: oops\n"
            )

    def test_docker_unknown_key(self) -> None:
        with pytest.raises(ConfigValidationError, match="Unknown key"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "docker:\n  unknown_key: true\n"
            )

    def test_docker_start_not_bool(self) -> None:
        with pytest.raises(ConfigValidationError, match="start"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "docker:\n  start: yes_please\n"
            )


# ---------------------------------------------------------------------------
# validate_config: modules section errors
# ---------------------------------------------------------------------------


class TestValidateModules:
    def test_modules_not_mapping(self) -> None:
        with pytest.raises(ConfigValidationError, match="modules"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "modules: oops\n"
            )

    def test_unknown_module(self) -> None:
        with pytest.raises(ConfigValidationError, match="Unknown module"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "modules:\n  nonexistent_module:\n    enabled: true\n"
            )

    def test_module_options_not_mapping(self) -> None:
        with pytest.raises(ConfigValidationError, match="mapping"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "modules:\n  analytics: just_a_string\n"
            )

    def test_auth_legacy_allow_registration(self) -> None:
        with pytest.raises(ConfigValidationError, match="allow_registration"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "modules:\n  auth:\n    allow_registration: true\n"
            )

    def test_auth_legacy_social_providers(self) -> None:
        with pytest.raises(ConfigValidationError, match="social_providers"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "modules:\n  auth:\n    social_providers:\n      - google\n"
            )

    def test_auth_registration_not_bool(self) -> None:
        with pytest.raises(ConfigValidationError, match="registration_enabled"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "modules:\n  auth:\n    registration_enabled: not_a_bool\n"
            )

    def test_auth_invalid_email_verification(self) -> None:
        with pytest.raises(ConfigValidationError, match="email_verification"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "modules:\n  auth:\n    email_verification: sometimes\n"
            )

    def test_auth_invalid_authentication_method(self) -> None:
        with pytest.raises(ConfigValidationError, match="authentication_method"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "modules:\n  auth:\n    authentication_method: magic\n"
            )

    def test_auth_session_cookie_age_not_int(self) -> None:
        with pytest.raises(ConfigValidationError, match="session_cookie_age"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "modules:\n  auth:\n    session_cookie_age: forever\n"
            )

    def test_billing_unknown_key(self) -> None:
        with pytest.raises(ConfigValidationError, match="billing"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "modules:\n  billing:\n    unknown_billing_key: true\n"
            )

    def test_billing_enabled_not_bool(self) -> None:
        with pytest.raises(ConfigValidationError, match="enabled"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "modules:\n  billing:\n    enabled: maybe\n"
            )

    def test_billing_invalid_env_var(self) -> None:
        with pytest.raises(ConfigValidationError):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "modules:\n  billing:\n    publishable_key_env_var: bad-name\n"
            )

    def test_billing_invalid_currency(self) -> None:
        with pytest.raises(ConfigValidationError, match="currency"):
            validate_config(
                'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
                "modules:\n  billing:\n    billing_currency: FAKE\n"
            )


# ---------------------------------------------------------------------------
# validate_config: valid config round-trip
# ---------------------------------------------------------------------------


class TestValidateConfigValid:
    def test_minimal_valid(self) -> None:
        config = validate_config(_MINIMAL_VALID_YAML)
        assert config.project.slug == "myapp"
        assert config.project.package == "myapp"
        assert config.project.theme == "showcase_react"

    def test_parse_config_alias(self) -> None:
        config = parse_config(_MINIMAL_VALID_YAML)
        assert isinstance(config, QuickScaleConfig)

    def test_valid_with_modules(self) -> None:
        yaml_text = _valid_yaml_with_modules("  analytics:\n    enabled: true\n")
        config = validate_config(yaml_text)
        assert "analytics" in config.modules


# ---------------------------------------------------------------------------
# Schema lazy exports
# ---------------------------------------------------------------------------


class TestSchemaLazyExports:
    def test_lazy_state_manager(self) -> None:
        from quickscale_core.schema import StateManager

        assert StateManager is not None

    def test_lazy_config_delta(self) -> None:
        from quickscale_core.schema import ConfigDelta

        assert ConfigDelta is not None

    def test_lazy_unknown_attr_raises(self) -> None:
        import quickscale_core.schema as schema_mod

        with pytest.raises(AttributeError, match="no_such_export"):
            schema_mod.no_such_export  # noqa: B018


# ---------------------------------------------------------------------------
# project_identity
# ---------------------------------------------------------------------------


class TestProjectIdentity:
    def test_derive_package_from_slug(self) -> None:
        assert derive_package_from_slug("my-app") == "my_app"

    def test_identity_from_config(self) -> None:
        config = validate_config(_MINIMAL_VALID_YAML)
        identity = identity_from_config(config)
        assert identity.slug == "myapp"
        assert identity.package == "myapp"

    def test_load_identity_no_config_file(self, tmp_path: Path) -> None:
        result = load_identity_from_config_file(tmp_path)
        assert result is None

    def test_load_identity_from_config_file(self, tmp_path: Path) -> None:
        (tmp_path / "quickscale.yml").write_text(_MINIMAL_VALID_YAML, encoding="utf-8")
        identity = load_identity_from_config_file(tmp_path)
        assert identity is not None
        assert identity.slug == "myapp"

    def test_load_identity_strict_fails_on_bad_yaml(self, tmp_path: Path) -> None:
        (tmp_path / "quickscale.yml").write_text(
            "not: valid: yaml: [", encoding="utf-8"
        )
        with pytest.raises(ProjectIdentityResolutionError):
            load_identity_from_config_file(tmp_path, strict=True)

    def test_load_identity_non_strict_returns_none_on_bad_yaml(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "quickscale.yml").write_text(
            "not: valid: yaml: [", encoding="utf-8"
        )
        result = load_identity_from_config_file(tmp_path, strict=False)
        assert result is None

    def test_resolve_identity_from_explicit_config(self, tmp_path: Path) -> None:
        config = validate_config(_MINIMAL_VALID_YAML)
        identity = resolve_project_identity(tmp_path, config=config)
        assert identity.slug == "myapp"

    def test_resolve_identity_from_config_file(self, tmp_path: Path) -> None:
        (tmp_path / "quickscale.yml").write_text(_MINIMAL_VALID_YAML, encoding="utf-8")
        identity = resolve_project_identity(tmp_path)
        assert identity.slug == "myapp"

    def test_resolve_identity_fails_when_nothing_found(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unable to resolve"):
            resolve_project_identity(tmp_path)

    def test_resolve_identity_strict_raises_typed_error(self, tmp_path: Path) -> None:
        with pytest.raises(ProjectIdentityResolutionError):
            resolve_project_identity(tmp_path, strict=True)


# ---------------------------------------------------------------------------
# ConfigDelta / compute_delta / format_delta
# ---------------------------------------------------------------------------


class TestConfigDelta:
    def test_compute_delta_no_state_means_all_new(self) -> None:
        from quickscale_core.schema.delta import compute_delta

        config = validate_config(_MINIMAL_VALID_YAML)
        delta = compute_delta(config, None)
        assert delta.has_changes is True
        assert delta.modules_to_add == []
        assert delta.modules_to_remove == []

    def test_compute_delta_no_changes(self) -> None:
        from quickscale_core.schema.delta import compute_delta
        from quickscale_core.schema.state_schema import (
            ProjectState,
            QuickScaleState,
        )

        config = validate_config(_MINIMAL_VALID_YAML)
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
            modules={},
        )
        delta = compute_delta(config, state)
        assert delta.has_changes is False

    def test_compute_delta_module_added(self) -> None:
        from quickscale_core.schema.delta import compute_delta
        from quickscale_core.schema.state_schema import (
            ProjectState,
            QuickScaleState,
        )

        yaml_text = _valid_yaml_with_modules("  analytics:\n    enabled: true\n")
        config = validate_config(yaml_text)
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
            modules={},
        )
        delta = compute_delta(config, state)
        assert delta.has_changes is True
        assert "analytics" in delta.modules_to_add

    def test_compute_delta_module_removed(self) -> None:
        from quickscale_core.schema.delta import compute_delta
        from quickscale_core.schema.state_schema import (
            ModuleState,
            ProjectState,
            QuickScaleState,
        )

        config = validate_config(_MINIMAL_VALID_YAML)
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
            modules={"analytics": ModuleState(name="analytics", options={})},
        )
        delta = compute_delta(config, state)
        assert delta.has_changes is True
        assert "analytics" in delta.modules_to_remove

    def test_compute_delta_theme_changed(self) -> None:
        from quickscale_core.schema.delta import compute_delta
        from quickscale_core.schema.state_schema import (
            ProjectState,
            QuickScaleState,
        )

        config = validate_config(_MINIMAL_VALID_YAML)
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_html"),
            modules={},
        )
        delta = compute_delta(config, state)
        assert delta.has_changes is True
        assert delta.theme_changed is True
        assert delta.old_theme == "showcase_html"
        assert delta.new_theme == "showcase_react"

    def test_format_delta_no_changes(self) -> None:
        from quickscale_core.schema.delta import ConfigDelta, format_delta

        delta = ConfigDelta(has_changes=False)
        text = format_delta(delta)
        assert "No changes" in text

    def test_format_delta_with_changes(self) -> None:
        from quickscale_core.schema.delta import ConfigDelta, format_delta

        delta = ConfigDelta(
            has_changes=True,
            modules_to_add=["analytics"],
            modules_to_remove=["blog"],
            theme_changed=True,
            old_theme="showcase_html",
            new_theme="showcase_react",
        )
        text = format_delta(delta)
        assert "analytics" in text
        assert "blog" in text
        assert "Theme" in text

    def test_module_config_delta_properties(self) -> None:
        from quickscale_core.schema.delta import (
            ConfigChange,
            ModuleConfigDelta,
        )

        delta = ModuleConfigDelta(
            module_name="test",
            mutable_changes=[ConfigChange("opt", 1, 2)],
            immutable_changes=[],
        )
        assert delta.has_mutable_changes is True
        assert delta.has_immutable_changes is False
        assert delta.has_changes is True

    def test_module_delta_dataclass(self) -> None:
        from quickscale_core.schema.delta import ModuleDelta

        delta = ModuleDelta(name="test", action="add")
        assert delta.name == "test"
        assert delta.action == "add"

    def test_config_delta_get_all_changes(self) -> None:
        from quickscale_core.schema.delta import (
            ConfigChange,
            ConfigDelta,
            ModuleConfigDelta,
        )

        cd = ConfigDelta(
            has_changes=True,
            config_deltas={
                "mod1": ModuleConfigDelta(
                    module_name="mod1",
                    mutable_changes=[ConfigChange("a", 1, 2)],
                    immutable_changes=[ConfigChange("b", 3, 4)],
                ),
            },
        )
        assert cd.has_mutable_config_changes is True
        assert cd.has_immutable_config_changes is True
        mutable = cd.get_all_mutable_changes()
        assert len(mutable) == 1
        assert mutable[0][0] == "mod1"
        immutable = cd.get_all_immutable_changes()
        assert len(immutable) == 1

    def test_format_delta_with_config_changes(self) -> None:
        from quickscale_core.schema.delta import (
            ConfigChange,
            ConfigDelta,
            ModuleConfigDelta,
            format_delta,
        )

        cd = ConfigDelta(
            has_changes=True,
            modules_unchanged=["mod1"],
            config_deltas={
                "mod1": ModuleConfigDelta(
                    module_name="mod1",
                    mutable_changes=[
                        ConfigChange("opt", 1, 2, django_setting="SETTING_OPT"),
                    ],
                    immutable_changes=[ConfigChange("locked", "a", "b")],
                ),
            },
        )
        text = format_delta(cd)
        assert "Mutable" in text
        assert "Immutable" in text
        assert "SETTING_OPT" in text
