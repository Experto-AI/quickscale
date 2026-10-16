"""The shared test-settings base the module suites adopt (decisions rule 18)."""

from __future__ import annotations

from pathlib import Path

from quickscale_core.testing.settings import (
    BASE_TEST_SETTINGS_KEYS,
    module_settings_schema,
    suite_database,
    suite_secret_key,
)

MINIMAL_MANIFEST = """\
name: demo
version: 1.0.0
config:
  mutable:
    enabled:
      type: boolean
      default: true
      django_setting: QUICKSCALE_DEMO_ENABLED
      description: Enable the demo module.
      validation: {}
  immutable: {}
"""


def test_base_keys_pin_the_adoption_contract() -> None:
    """The harness reads this tuple and requires every key of every suite."""
    assert BASE_TEST_SETTINGS_KEYS == (
        "DATABASES",
        "DEFAULT_AUTO_FIELD",
        "INSTALLED_APPS",
        "MIDDLEWARE",
        "MODULE_SETTINGS_SCHEMA",
        "ROOT_URLCONF",
        "SECRET_KEY",
        "TEMPLATES",
        "USE_TZ",
    )


def test_secret_key_is_module_specific() -> None:
    assert suite_secret_key("demo") == "test-secret-key-for-demo-module"
    assert suite_secret_key("demo") != suite_secret_key("other")


def test_database_defaults(monkeypatch) -> None:
    for suffix in ("NAME", "USER", "PASSWORD", "HOST", "PORT"):
        monkeypatch.delenv(f"QS_DEMO_DB_{suffix}", raising=False)

    assert suite_database("demo") == {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "test_quickscale_demo",
        "USER": "postgres",
        "PASSWORD": "",
        "HOST": "localhost",
        "PORT": "5432",
    }


def test_database_honours_role_and_test_name() -> None:
    database = suite_database(
        "demo", user="quickscale_test_role", test_database_name="qs_demo"
    )

    assert database["USER"] == "quickscale_test_role"
    assert database["TEST"] == {"NAME": "qs_demo"}


def test_database_reads_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("QS_DEMO_DB_NAME", "custom_name")
    monkeypatch.setenv("QS_DEMO_DB_USER", "custom_user")
    monkeypatch.setenv("QS_DEMO_DB_PASSWORD", "custom_password")
    monkeypatch.setenv("QS_DEMO_DB_HOST", "db.internal")
    monkeypatch.setenv("QS_DEMO_DB_PORT", "6543")

    database = suite_database("demo")

    assert database["NAME"] == "custom_name"
    assert database["USER"] == "custom_user"
    assert database["PASSWORD"] == "custom_password"
    assert database["HOST"] == "db.internal"
    assert database["PORT"] == "6543"


def test_module_settings_schema_loads_each_manifest(tmp_path: Path) -> None:
    module_dir = tmp_path / "demo"
    module_dir.mkdir()
    (module_dir / "module.yml").write_text(MINIMAL_MANIFEST, encoding="utf-8")

    schema = module_settings_schema(tmp_path, "demo")

    assert list(schema) == ["demo"]
    assert schema["demo"]["enabled"] == {
        "setting": "QUICKSCALE_DEMO_ENABLED",
        "type": "boolean",
        "validation": {},
    }


def test_module_settings_schema_keys_by_manifest_name(tmp_path: Path) -> None:
    renamed_dir = tmp_path / "renamed-checkout"
    renamed_dir.mkdir()
    (renamed_dir / "module.yml").write_text(MINIMAL_MANIFEST, encoding="utf-8")

    schema = module_settings_schema(tmp_path, "renamed-checkout")

    assert list(schema) == ["demo"]
