"""Manifest settings schema compilation, checking, and rendering (SA217).

Module Conventions rule 3: ``quickscale apply`` writes every declared setting
into ``settings/modules.py`` together with a ``MODULE_SETTINGS_SCHEMA``; the
generic runtime check validates a project's settings against that schema
without coercion.  These tests cover the compiler that produces the schema,
the value checker the runtime check delegates to, and the renderer that
writes the block.
"""

from pathlib import Path

import pytest

from quickscale_core.manifest.loader import load_manifest, load_manifest_from_path
from quickscale_core.manifest.schema import ConfigOption, ModuleManifest
from quickscale_core.manifest.settings_schema import (
    collect_setting_issues,
    compile_settings_schema,
    load_settings_schema,
)
from quickscale_core.module_wiring import (
    ModuleWiringSpec,
    render_settings_modules_py,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _manifest(*options: ConfigOption, name: str = "demo") -> ModuleManifest:
    mutable = {option.name: option for option in options if option.django_setting}
    immutable = {option.name: option for option in options if not option.django_setting}
    return ModuleManifest(
        name=name,
        version="1.0.0",
        mutable_options=mutable,
        immutable_options=immutable,
    )


def _option(
    name: str,
    *,
    option_type: str = "string",
    setting: str | None = None,
    validation: dict[str, object] | None = None,
) -> ConfigOption:
    return ConfigOption(
        name=name,
        option_type=option_type,
        django_setting=setting,
        description="A demo option",
        mutability="mutable" if setting else "immutable",
        validation=validation or {},
    )


class TestCompileSettingsSchema:
    """The compiler turns declared mutable options into schema entries."""

    def test_mutable_option_compiles_with_type_and_validation(self) -> None:
        manifest = _manifest(
            _option(
                "listings_per_page",
                option_type="integer",
                setting="LISTINGS_PER_PAGE",
                validation={"min": 1},
            )
        )

        assert compile_settings_schema(manifest) == {
            "listings_per_page": {
                "setting": "LISTINGS_PER_PAGE",
                "type": "integer",
                "validation": {"min": 1},
            }
        }

    def test_immutable_option_is_excluded(self) -> None:
        manifest = _manifest(
            _option("mode", setting="QUICKSCALE_MODE"),
            _option("private_media_enabled", option_type="boolean"),
        )

        assert compile_settings_schema(manifest) == {
            "mode": {"setting": "QUICKSCALE_MODE", "type": "string", "validation": {}}
        }

    def test_mutable_option_without_a_setting_is_refused(self) -> None:
        manifest = ModuleManifest(
            name="broken",
            version="1.0.0",
            mutable_options={
                "no_setting": ConfigOption(
                    name="no_setting",
                    option_type="string",
                    mutability="mutable",
                )
            },
        )

        with pytest.raises(ValueError, match="no_setting.*no django_setting"):
            compile_settings_schema(manifest)

    def test_entries_are_sorted_by_option_name(self) -> None:
        manifest = _manifest(
            _option("zeta", setting="ZETA"),
            _option("alpha", setting="ALPHA"),
        )

        assert list(compile_settings_schema(manifest)) == ["alpha", "zeta"]

    def test_shipped_manifest_compiles_every_declared_setting(self) -> None:
        manifest = load_manifest_from_path(
            REPO_ROOT / "quickscale_modules" / "storage" / "module.yml"
        )
        schema = compile_settings_schema(manifest)

        assert set(schema) == set(manifest.mutable_options)
        assert schema["backend"] == {
            "setting": "QUICKSCALE_STORAGE_BACKEND",
            "type": "string",
            "validation": {"choices": ["local", "s3", "r2"]},
        }

    def test_load_settings_schema_reads_a_manifest_path(self) -> None:
        schema = load_settings_schema(
            REPO_ROOT / "quickscale_modules" / "listings" / "module.yml"
        )

        assert schema["listings_per_page"]["setting"] == "LISTINGS_PER_PAGE"


class TestCollectSettingIssues:
    """The value checker runs the validation vocabulary without coercion."""

    def _schema(self) -> dict[str, dict[str, object]]:
        return compile_settings_schema(
            _manifest(
                _option(
                    "per_page",
                    option_type="integer",
                    setting="LISTINGS_PER_PAGE",
                    validation={"min": 1},
                ),
                _option(
                    "mode",
                    setting="QUICKSCALE_MODE",
                    validation={"choices": ["solo", "saas"]},
                ),
            )
        )

    def test_valid_values_pass(self) -> None:
        assert (
            collect_setting_issues(
                "demo", self._schema(), {"per_page": 12, "mode": "solo"}
            )
            == []
        )

    def test_wrong_type_is_refused_not_coerced(self) -> None:
        """A string "12" for an integer option is refused at runtime."""
        issues = collect_setting_issues("demo", self._schema(), {"per_page": "12"})

        assert [issue.message for issue in issues] == [
            "LISTINGS_PER_PAGE (modules.demo.per_page) must be an integer"
        ]

    def test_minimum_violation_names_the_rule(self) -> None:
        issues = collect_setting_issues("demo", self._schema(), {"per_page": 0})

        assert [issue.message for issue in issues] == [
            "LISTINGS_PER_PAGE (modules.demo.per_page) must be >= 1"
        ]

    def test_only_supplied_options_are_checked(self) -> None:
        """The runtime check reports absent settings itself; the engine sees present ones."""
        issues = collect_setting_issues("demo", self._schema(), {"per_page": 12})

        assert issues == []

    def test_unknown_option_is_refused(self) -> None:
        with pytest.raises(ValueError, match="Unknown option 'ghost'"):
            collect_setting_issues("demo", self._schema(), {"ghost": 1})

    def test_malformed_entry_is_refused(self) -> None:
        with pytest.raises(ValueError, match="Malformed schema entry"):
            collect_setting_issues(
                "demo", {"per_page": {"type": "integer"}}, {"per_page": 1}
            )

    def test_required_when_violation_names_both_settings(self) -> None:
        manifest = load_manifest(
            """
name: demo
version: "1.0.0"
config:
  mutable:
    backend:
      type: string
      default: local
      django_setting: BACKEND
      description: Backend
      validation:
        choices: [local, s3]
    credentials:
      type: string
      default: ""
      django_setting: CREDENTIALS
      description: Env var name
      validation:
        required_when:
          backend: [s3]
  immutable: {}
""",
            "demo",
        )
        schema = compile_settings_schema(manifest)

        issues = collect_setting_issues(
            "demo", schema, {"backend": "s3", "credentials": ""}
        )

        assert [issue.message for issue in issues] == [
            "CREDENTIALS (modules.demo.credentials) is required when "
            "BACKEND (modules.demo.backend) is one of: s3"
        ]


class TestRenderSettingsSchema:
    """The managed settings renderer writes MODULE_SETTINGS_SCHEMA."""

    def test_schema_is_rendered_under_its_module_name(self) -> None:
        schema = {
            "listings_per_page": {
                "setting": "LISTINGS_PER_PAGE",
                "type": "integer",
                "validation": {"min": 1},
            }
        }
        content = render_settings_modules_py(
            {"listings": ModuleWiringSpec(settings_schema=schema)}
        )

        assert (
            "MODULE_SETTINGS_SCHEMA: dict[str, dict[str, dict[str, object]]] = {"
            in content
        )
        assert "'listings': {'listings_per_page': {" in content
        assert "'setting': 'LISTINGS_PER_PAGE'" in content

    def test_empty_specs_render_an_empty_schema(self) -> None:
        content = render_settings_modules_py({})

        assert (
            "MODULE_SETTINGS_SCHEMA: dict[str, dict[str, dict[str, object]]] = {}"
            in content
        )


class TestModuleWiringSpecSchema:
    """A spec without a compiled schema contributes no schema entry."""

    def test_no_schema_contributes_nothing(self) -> None:
        content = render_settings_modules_py(
            {"listings": ModuleWiringSpec(settings={"LISTINGS_PER_PAGE": 12})}
        )

        assert (
            "MODULE_SETTINGS_SCHEMA: dict[str, dict[str, dict[str, object]]] = {}"
            in content
        )
