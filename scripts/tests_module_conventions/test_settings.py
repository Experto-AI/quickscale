"""Control cases for the settings module-convention rules."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import (
    _golden_module,
    _violations,
    _with_files,
    _with_option,
    _without_option,
)


def test_settings_names_control() -> None:
    module = _golden_module()
    assert _violations(checker.rule_1_settings_names, module) == []
    no_enabled = _without_option(module, "enabled")
    assert any(
        "declares no enabled option" in violation
        for violation in _violations(checker.rule_1_settings_names, no_enabled)
    )
    wrong_type = _with_option(
        module,
        "enabled",
        {
            "type": "string",
            "default": "yes",
            "django_setting": "QUICKSCALE_DEMO_ENABLED",
            "description": "Enable the demo module.",
            "validation": {},
        },
    )
    assert any(
        "enabled type" in violation
        for violation in _violations(checker.rule_1_settings_names, wrong_type)
    )
    wrong_name = _with_option(
        module,
        "enabled",
        {
            "type": "boolean",
            "default": True,
            "django_setting": "QUICKSCALE_DEMO_ON",
            "description": "Enable the demo module.",
            "validation": {},
        },
    )
    assert any(
        "enabled setting" in violation
        for violation in _violations(checker.rule_1_settings_names, wrong_name)
    )
    bad_suffix = _with_option(
        module,
        "api_rate_limit",
        {
            "type": "integer",
            "default": 5,
            "django_setting": "QUICKSCALE_DEMO_API_RATE_LIMIT",
            "description": "Throttle rate.",
            "validation": {},
        },
    )
    assert any(
        "expected string" in violation
        for violation in _violations(checker.rule_1_settings_names, bad_suffix)
    )
    bad_default = _with_option(
        module,
        "action_key_env_var",
        {
            "type": "string",
            "default": "not-a-name",
            "django_setting": "QUICKSCALE_DEMO_ACTION_KEY_ENV_VAR",
            "description": "Environment variable name.",
            "validation": {},
        },
    )
    assert any(
        "not an environment-variable name" in violation
        for violation in _violations(checker.rule_1_settings_names, bad_default)
    )


def test_settings_reads_control() -> None:
    module = _golden_module()
    assert _violations(checker.rule_3_settings_reads, module) == []
    undeclared = _with_files(
        module,
        services=("from django.conf import settings\n\nKEY = settings.QUICKSCALE_DEMO_MISSING\n"),
    )
    assert any(
        "reads undeclared" in violation
        for violation in _violations(checker.rule_3_settings_reads, undeclared)
    )
    cross_module = _with_files(
        module,
        services=(
            "from django.conf import settings\n\nKEY = settings.QUICKSCALE_BILLING_SECRET_KEY\n"
        ),
    )
    assert any(
        "reads billing's" in violation
        for violation in _violations(checker.rule_3_settings_reads, cross_module)
    )
    with_default = _with_files(
        module,
        services=(
            "from django.conf import settings\n\n"
            'KEY = getattr(settings, "QUICKSCALE_DEMO_ENABLED", True)\n'
        ),
    )
    assert any(
        "through getattr()" in violation
        for violation in _violations(checker.rule_3_settings_reads, with_default)
    )
    aliased_default = _with_files(
        module,
        services=(
            "from django.conf import settings as cfg\n\n"
            'KEY = getattr(cfg, "QUICKSCALE_DEMO_ENABLED", True)\n'
        ),
    )
    assert any(
        "through getattr()" in violation
        for violation in _violations(checker.rule_3_settings_reads, aliased_default)
    )
    qualified_default = _with_files(
        module,
        services=(
            "import django.conf as conf\n\n"
            'KEY = getattr(conf.settings, "QUICKSCALE_DEMO_ENABLED", True)\n'
        ),
    )
    assert any(
        "through getattr()" in violation
        for violation in _violations(checker.rule_3_settings_reads, qualified_default)
    )
    missing_setting = replace(
        module,
        tests={**module.tests, "settings.py": "SECRET_KEY = 'test'\n"},
    )
    assert any(
        "tests/settings.py does not define" in violation
        for violation in _violations(checker.rule_3_settings_reads, missing_setting)
    )
    commented_setting = replace(
        module,
        tests={
            **module.tests,
            "settings.py": (
                "SECRET_KEY = 'test'\n"
                "# QUICKSCALE_DEMO_ENABLED = True\n"
                "QUICKSCALE_DEMO_API_RATE_LIMIT = '5/hour'\n"
            ),
        },
    )
    assert any(
        "tests/settings.py does not define QUICKSCALE_DEMO_ENABLED" in violation
        for violation in _violations(checker.rule_3_settings_reads, commented_setting)
    )
    annotation_only = replace(
        module,
        tests={
            **module.tests,
            "settings.py": (
                "SECRET_KEY = 'test'\n"
                "QUICKSCALE_DEMO_ENABLED: bool\n"
                "QUICKSCALE_DEMO_API_RATE_LIMIT = '5/hour'\n"
            ),
        },
    )
    assert any(
        "tests/settings.py does not define QUICKSCALE_DEMO_ENABLED" in violation
        for violation in _violations(checker.rule_3_settings_reads, annotation_only)
    )
    annotated_value = replace(
        module,
        tests={
            **module.tests,
            "settings.py": (
                "SECRET_KEY = 'test'\n"
                "QUICKSCALE_DEMO_ENABLED: bool = True\n"
                "QUICKSCALE_DEMO_API_RATE_LIMIT = '5/hour'\n"
            ),
        },
    )
    assert _violations(checker.rule_3_settings_reads, annotated_value) == []
    unpacked_setting = replace(
        module,
        tests={
            **module.tests,
            "settings.py": (
                "SECRET_KEY = 'test'\n"
                "QUICKSCALE_DEMO_ENABLED, = (True,)\n"
                "QUICKSCALE_DEMO_API_RATE_LIMIT = '5/hour'\n"
            ),
        },
    )
    assert _violations(checker.rule_3_settings_reads, unpacked_setting) == []


def test_manifest_schema_control() -> None:
    module = _golden_module()
    manifest = dict(module.manifest)
    config = {
        "mutable": {
            "api_rate_limit": {
                "type": "string",
                "default": "5/hour",
                "django_setting": "QUICKSCALE_DEMO_API_RATE_LIMIT",
                "description": "Throttle rate.",
                "validation": {"regex": "nope"},
            },
        },
        "immutable": {},
    }
    manifest["config"] = config
    assert _violations(checker.rule_12_manifest_options, replace(module, manifest=manifest))


def test_manifest_missing_description_control() -> None:
    module = _golden_module()
    manifest = dict(module.manifest)
    option = dict(manifest["config"]["mutable"]["api_rate_limit"])  # type: ignore[index]
    option.pop("description")
    manifest["config"] = {
        "mutable": {"api_rate_limit": option},
        "immutable": {},
    }
    assert _violations(checker.rule_12_manifest_options, replace(module, manifest=manifest))


def test_immutable_django_setting_control() -> None:
    module = _golden_module()
    manifest = dict(module.manifest)
    manifest["config"] = {
        "mutable": {},
        "immutable": {
            "mode": {
                "type": "string",
                "default": "solo",
                "description": "Mode.",
                "django_setting": "QUICKSCALE_DEMO_MODE",
            }
        },
    }
    assert any(
        "immutable" in violation
        for violation in _violations(
            checker.rule_12_manifest_options, replace(module, manifest=manifest)
        )
    )


def test_malformed_nested_config_shape_is_a_violation() -> None:
    module = _golden_module()
    broken = replace(module, manifest={**module.manifest, "config": [1]})
    assert _violations(checker.rule_12_manifest_options, broken)
    # A non-mapping config is skipped, never a traceback.
    assert _violations(checker.rule_38_readme_content, broken) == []


def test_settings_snapshot_location_controls() -> None:
    module = _golden_module()
    assert _violations(checker.rule_42_settings_snapshots, module) == []

    wrong_location = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            '__all__ = ["demo_query", "is_enabled"]\n\n\n'
            "class DemoRuntimeSettingsSnapshot:\n"
            "    enabled: bool\n\n"
            "    @classmethod\n"
            "    def from_settings(cls):\n"
            "        return cls(enabled=True)\n\n\n"
            "def is_enabled() -> bool:\n"
            "    return True\n"
        ),
    )
    assert any(
        "defines the settings snapshot DemoRuntimeSettingsSnapshot outside _settings.py"
        in violation
        for violation in _violations(checker.rule_42_settings_snapshots, wrong_location)
    )

    misplaced_getter = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            '__all__ = ["demo_query", "is_enabled"]\n\n'
            "from django.conf import settings\n\n\n"
            "def demo_runtime_settings():\n"
            "    return DemoRuntimeSettingsSnapshot(enabled=settings.QUICKSCALE_DEMO_ENABLED)\n"
        ),
    )
    assert any(
        "builds a settings snapshot outside _settings.py" in violation
        for violation in _violations(checker.rule_42_settings_snapshots, misplaced_getter)
    )

    exported = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            '__all__ = ["DemoPolicySnapshot", "is_enabled"]\n\n'
            "from quickscale_modules_demo._settings import DemoPolicySnapshot\n\n\n"
            "def is_enabled() -> bool:\n"
            "    return True\n"
        ),
        **{
            "_settings.py": (
                "from django.conf import settings\n\n\n"
                "class DemoPolicySnapshot:\n"
                "    retention_days: int\n\n\n"
                "def demo_policy_snapshot():\n"
                "    return DemoPolicySnapshot(\n"
                "        retention_days=int(settings.QUICKSCALE_DEMO_RETENTION)\n"
                "    )\n"
            ),
        },
    )
    assert any(
        "exports the settings snapshot DemoPolicySnapshot" in violation
        for violation in _violations(checker.rule_42_settings_snapshots, exported)
    )

    split_class = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            '__all__ = ["demo_query", "is_enabled"]\n\n\n'
            "class DemoSettingsSnapshot:\n"
            "    enabled: bool\n\n\n"
            "def is_enabled() -> bool:\n"
            "    return True\n"
        ),
        **{
            "_settings.py": (
                "from django.conf import settings\n\n"
                "from quickscale_modules_demo.services import DemoSettingsSnapshot\n\n\n"
                "def demo_settings_snapshot():\n"
                "    return DemoSettingsSnapshot(\n"
                "        enabled=settings.QUICKSCALE_DEMO_ENABLED\n"
                "    )\n"
            ),
        },
    )
    assert any(
        "defines the settings snapshot DemoSettingsSnapshot outside _settings.py" in violation
        for violation in _violations(checker.rule_42_settings_snapshots, split_class)
    )

    split_class_alias = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            '__all__ = ["demo_query", "is_enabled"]\n\n\n'
            "class DemoSettingsSnapshot:\n"
            "    enabled: bool\n\n\n"
            "def is_enabled() -> bool:\n"
            "    return True\n"
        ),
        **{
            "_settings.py": (
                "from django.conf import settings\n\n"
                "from quickscale_modules_demo.services import (\n"
                "    DemoSettingsSnapshot as Snapshot,\n"
                ")\n\n\n"
                "def demo_settings_snapshot():\n"
                "    return Snapshot(enabled=settings.QUICKSCALE_DEMO_ENABLED)\n"
            ),
        },
    )
    assert any(
        "defines the settings snapshot DemoSettingsSnapshot outside _settings.py" in violation
        for violation in _violations(checker.rule_42_settings_snapshots, split_class_alias)
    )

    alias_exported = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            '__all__ = ["Snapshot", "is_enabled"]\n\n'
            "from quickscale_modules_demo._settings import (\n"
            "    DemoSettingsSnapshot as Snapshot,\n"
            ")\n\n\n"
            "def is_enabled() -> bool:\n"
            "    return True\n"
        ),
        **{
            "_settings.py": (
                "from dataclasses import dataclass\n\n"
                "from django.conf import settings\n\n\n"
                "@dataclass(frozen=True)\n"
                "class DemoSettingsSnapshot:\n"
                "    enabled: bool\n\n"
                "    @classmethod\n"
                "    def from_settings(cls):\n"
                "        return cls(enabled=bool(settings.QUICKSCALE_DEMO_ENABLED))\n"
            ),
        },
    )
    assert any(
        "exports the settings snapshot DemoSettingsSnapshot" in violation
        for violation in _violations(checker.rule_42_settings_snapshots, alias_exported)
    )

    alias_allowed = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            '__all__ = ["demo_query", "verify"]\n\n'
            "from quickscale_modules_demo.checks import check_demo as verify\n\n\n"
            "def demo_query(*, subject: str) -> str:\n"
            "    return subject\n"
        ),
    )
    assert _violations(checker.rule_42_settings_snapshots, alias_allowed) == []


def test_optional_sender_controls() -> None:
    module = _golden_module()
    assert _violations(checker.rule_43_optional_senders, module) == []

    settings_read = _with_files(
        module,
        views=(
            "from importlib import import_module\n\n\n"
            "def load_sender():\n"
            "    services = import_module('quickscale_modules_notifications.services')\n"
            "    return services.NotificationSettingsSnapshot.from_settings().enabled\n"
        ),
    )
    assert any(
        "reads notifications's settings through NotificationSettingsSnapshot" in violation
        for violation in _violations(checker.rule_43_optional_senders, settings_read)
    )

    catch_all = _with_files(
        module,
        views=(
            "from quickscale_modules_notifications.services import send_notification\n\n\n"
            "def send_now() -> None:\n"
            "    try:\n"
            "        send_notification(template_key='x', recipients=[], context={})\n"
            "    except Exception:\n"
            "        return\n"
        ),
    )
    assert any(
        "catches Exception around notifications's service call" in violation
        for violation in _violations(checker.rule_43_optional_senders, catch_all)
    )

    dotted_catch_all = _with_files(
        module,
        views=(
            "import quickscale_modules_notifications.services\n\n\n"
            "def send_now() -> None:\n"
            "    try:\n"
            "        quickscale_modules_notifications.services.send_notification(\n"
            "            template_key='x', recipients=[], context={}\n"
            "        )\n"
            "    except Exception:\n"
            "        return\n"
        ),
    )
    assert any(
        "catches Exception around notifications's service call" in violation
        for violation in _violations(checker.rule_43_optional_senders, dotted_catch_all)
    )

    dotted_narrowed = _with_files(
        module,
        views=(
            "import quickscale_modules_notifications.services\n\n"
            "from quickscale_modules_notifications.services import NotificationError\n\n\n"
            "def send_now() -> None:\n"
            "    try:\n"
            "        quickscale_modules_notifications.services.send_notification(\n"
            "            template_key='x', recipients=[], context={}\n"
            "        )\n"
            "    except NotificationError:\n"
            "        return\n"
        ),
    )
    assert _violations(checker.rule_43_optional_senders, dotted_narrowed) == []

    narrowed = _with_files(
        module,
        views=(
            "from quickscale_modules_notifications.services import (\n"
            "    NotificationError,\n"
            "    send_notification,\n"
            ")\n\n\n"
            "def send_now() -> None:\n"
            "    try:\n"
            "        send_notification(template_key='x', recipients=[], context={})\n"
            "    except NotificationError:\n"
            "        return\n"
        ),
    )
    assert _violations(checker.rule_43_optional_senders, narrowed) == []

    best_effort = _with_files(
        module,
        views=(
            "def emit() -> None:\n"
            "    from quickscale_modules_analytics.services import capture_event\n\n"
            "    try:\n"
            "        capture_event(distinct_id='x', event='e')\n"
            "    except Exception:\n"
            "        return\n"
        ),
    )
    assert _violations(checker.rule_43_optional_senders, best_effort) == []


def test_malformed_manifest_is_authority_failure(tmp_path: Path) -> None:
    modules_root = tmp_path / "quickscale_modules"
    module_dir = modules_root / "demo"
    module_dir.mkdir(parents=True)
    (module_dir / "module.yml").write_text("name: [unterminated\n", encoding="utf-8")
    with pytest.raises(checker.AuthorityError):
        checker.load_corpus(tmp_path)
