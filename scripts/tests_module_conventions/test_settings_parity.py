"""
Behavioral controls for the ``rules_settings`` split (SA267).

Rule 1's settings-name clauses, rule 3's read scan, rule 12's manifest-option
schema, rule 42's snapshot location scan, and rule 43's optional-sender scans
live in private siblings (``_settings_names``, ``_settings_reads``,
``_settings_manifest``, ``_settings_snapshots``, ``_settings_senders``) behind
the ``rules_settings`` facade.  SA267 has closed, so SA279 retired the pre-split
surface pins; these controls keep the split's structural invariants and the
exact ordered findings of representative corpora captured from the pre-split
module, so a later change cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
import copy
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.check_module_conventions import Module
from scripts.module_conventions import (
    _settings_manifest,
    _settings_names,
    _settings_reads,
    _settings_senders,
    _settings_snapshots,
    rules_settings,
)
from scripts.module_conventions.rules_identity import RULE_37_ALLOWED_LITERAL_FILES
from scripts.tests_module_conventions._support import (
    _corpus,
    _golden_module,
    _with_files,
    _with_option,
    _without_option,
)

SPLIT_SIBLINGS = {
    "_settings_manifest": _settings_manifest,
    "_settings_names": _settings_names,
    "_settings_reads": _settings_reads,
    "_settings_senders": _settings_senders,
    "_settings_snapshots": _settings_snapshots,
}


_GOLDEN_EXTRA_SETTINGS = (
    "QUICKSCALE_DEMO_BACKEND = 'local'\n"
    "QUICKSCALE_DEMO_CDN_URL = '/demo/'\n"
    "QUICKSCALE_DEMO_MARKETING_HOST = ''\n"
)


def _credential_module() -> Module:
    return _with_option(
        _golden_module(),
        "api_key_env_var",
        {
            "type": "string",
            "default": "QUICKSCALE_DEMO_API_KEY",
            "django_setting": "QUICKSCALE_DEMO_API_KEY_ENV_VAR",
            "description": "Environment variable name holding the demo API key.",
            "validation": {"pattern": "^(?:[A-Z][A-Z0-9_]*)?$"},
        },
    )


def _credential_with_default(default: str) -> Module:
    module = _credential_module()
    existing = module.manifest["config"]["mutable"]["api_key_env_var"]  # type: ignore[index]
    return _with_option(module, "api_key_env_var", {**existing, "default": default})


def _enabled_with(**overrides: object) -> Module:
    module = _golden_module()
    existing = module.manifest["config"]["mutable"]["enabled"]  # type: ignore[index]
    return _with_option(module, "enabled", {**existing, **overrides})


def _option_with(key: str, **overrides: object) -> Module:
    module = _golden_module()
    existing = module.manifest["config"]["mutable"][key]  # type: ignore[index]
    return _with_option(module, key, {**existing, **overrides})


def _service_module(services: str) -> Module:
    return _with_files(_golden_module(), services=services)


def _views_module(views: str) -> Module:
    return _with_files(_golden_module(), views=views)


def _manifest_without(key: str) -> Module:
    module = _golden_module()
    manifest = copy.deepcopy(module.manifest)
    del manifest[key]
    return replace(module, manifest=manifest)


def _manifest_with(key: str, value: object) -> Module:
    module = _golden_module()
    manifest = copy.deepcopy(module.manifest)
    manifest[key] = value
    return replace(module, manifest=manifest)


def _derivation_without(key: str) -> Module:
    module = _golden_module()
    manifest = copy.deepcopy(module.manifest)
    del manifest["derivation"]["option_derivations"][key]  # type: ignore[index]
    return replace(module, manifest=manifest)


def _derivation_added(key: str, rule: dict[str, object]) -> Module:
    module = _golden_module()
    manifest = copy.deepcopy(module.manifest)
    manifest["derivation"]["option_derivations"][key]["normalization_rules"].append(  # type: ignore[index]
        rule
    )
    return replace(module, manifest=manifest)


def _option_without(key: str, field: str) -> Module:
    module = _golden_module()
    manifest = copy.deepcopy(module.manifest)
    del manifest["config"]["mutable"][key][field]  # type: ignore[index]
    return replace(module, manifest=manifest)


def _retired_validation_rules() -> Module:
    module = _golden_module()
    manifest = copy.deepcopy(module.manifest)
    manifest["derivation"]["validation_rules"] = []  # type: ignore[index]
    return replace(module, manifest=manifest)


def _setting_pattern(key: str, pattern: str) -> Module:
    module = _golden_module()
    manifest = copy.deepcopy(module.manifest)
    manifest["config"]["mutable"][key]["validation"] = {"pattern": pattern}  # type: ignore[index]
    return replace(module, manifest=manifest)


def _config(value: object) -> Module:
    module = _golden_module()
    return replace(module, manifest={**module.manifest, "config": value})


def _tests_settings(settings: str) -> Module:
    module = _golden_module()
    return replace(module, tests={**module.tests, "settings.py": settings})


# --- rule 3 -----------------------------------------------------------------


def _derived_setting_read(declared: bool) -> Module:
    module = _golden_module()
    if declared:
        manifest = copy.deepcopy(module.manifest)
        derivation = manifest["derivation"]
        option_derivations = derivation.setdefault("option_derivations", {})  # type: ignore[union-attr]
        option_derivations["backend"] = {
            "derived_settings": [
                {
                    "setting_key": "QUICKSCALE_DEMO_BACKEND_ALIAS",
                    "derivation_type": "direct",
                    "expression": {"option": "backend"},
                    "description": "Backend alias.",
                },
            ],
        }
        module = replace(module, manifest=manifest)
    return _with_files(
        module,
        services=(
            "from django.conf import settings\n\nKEY = settings.QUICKSCALE_DEMO_BACKEND_ALIAS\n"
        ),
    )


# --- rule 42 ----------------------------------------------------------------


def _snapshot_at(*, location: str, source: str, settings_source: str | None = None) -> Module:
    module = _golden_module()
    files = {location: source}
    if settings_source is not None:
        files["_settings.py"] = settings_source
    return _with_files(module, **files)


def _snapshot_outside() -> Module:
    return _snapshot_at(
        location="services",
        source=(
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


def _getter_outside() -> Module:
    return _snapshot_at(
        location="services",
        source=(
            '"""Demo service surface."""\n\n'
            '__all__ = ["demo_query", "is_enabled"]\n\n'
            "from django.conf import settings\n\n\n"
            "def demo_runtime_settings():\n"
            "    return DemoRuntimeSettingsSnapshot(enabled=settings.QUICKSCALE_DEMO_ENABLED)\n"
        ),
    )


def _exported_snapshot() -> Module:
    return _snapshot_at(
        location="services",
        source=(
            '"""Demo service surface."""\n\n'
            '__all__ = ["DemoPolicySnapshot", "is_enabled"]\n\n'
            "from quickscale_modules_demo._settings import DemoPolicySnapshot\n\n\n"
            "def is_enabled() -> bool:\n"
            "    return True\n"
        ),
        settings_source=(
            "from django.conf import settings\n\n\n"
            "class DemoPolicySnapshot:\n"
            "    retention_days: int\n\n\n"
            "def demo_policy_snapshot():\n"
            "    return DemoPolicySnapshot(\n"
            "        retention_days=int(settings.QUICKSCALE_DEMO_RETENTION)\n"
            "    )\n"
        ),
    )


def _exported_alias() -> Module:
    return _snapshot_at(
        location="services",
        source=(
            '"""Demo service surface."""\n\n'
            '__all__ = ["Snapshot", "is_enabled"]\n\n'
            "from quickscale_modules_demo._settings import (\n"
            "    DemoSettingsSnapshot as Snapshot,\n"
            ")\n\n\n"
            "def is_enabled() -> bool:\n"
            "    return True\n"
        ),
        settings_source=(
            "from dataclasses import dataclass\n\n"
            "from django.conf import settings\n\n\n"
            "@dataclass(frozen=True)\n"
            "class DemoSettingsSnapshot:\n"
            "    enabled: bool\n\n"
            "    @classmethod\n"
            "    def from_settings(cls):\n"
            "        return cls(enabled=bool(settings.QUICKSCALE_DEMO_ENABLED))\n"
        ),
    )


def _split_class() -> Module:
    return _snapshot_at(
        location="services",
        source=(
            '"""Demo service surface."""\n\n'
            '__all__ = ["demo_query", "is_enabled"]\n\n\n'
            "class DemoSettingsSnapshot:\n"
            "    enabled: bool\n\n\n"
            "def is_enabled() -> bool:\n"
            "    return True\n"
        ),
        settings_source=(
            "from django.conf import settings\n\n"
            "from quickscale_modules_demo.services import DemoSettingsSnapshot\n\n\n"
            "def demo_settings_snapshot():\n"
            "    return DemoSettingsSnapshot(\n"
            "        enabled=settings.QUICKSCALE_DEMO_ENABLED\n"
            "    )\n"
        ),
    )


def _alias_allowed() -> Module:
    return _snapshot_at(
        location="services",
        source=(
            '"""Demo service surface."""\n\n'
            '__all__ = ["demo_query", "verify"]\n\n'
            "from quickscale_modules_demo.checks import check_demo as verify\n\n\n"
            "def demo_query(*, subject: str) -> str:\n"
            "    return subject\n"
        ),
    )


CASES: dict[str, tuple[object, str]] = {
    # rule 1: settings names and the enabled switch
    "rule1_clean": (lambda: _corpus(_golden_module()), "rule_1_settings_names"),
    "rule1_no_enabled": (
        lambda: _corpus(_without_option(_golden_module(), "enabled")),
        "rule_1_settings_names",
    ),
    "rule1_enabled_wrong_type": (
        lambda: _corpus(_enabled_with(type="string", default="yes")),
        "rule_1_settings_names",
    ),
    "rule1_enabled_wrong_setting": (
        lambda: _corpus(_enabled_with(django_setting="QUICKSCALE_DEMO_ON")),
        "rule_1_settings_names",
    ),
    "rule1_wrong_stem": (
        lambda: _corpus(_option_with("backend", django_setting="QUICKSCALE_OTHER_BACKEND")),
        "rule_1_settings_names",
    ),
    "rule1_suffix_wrong_type": (
        lambda: _corpus(_option_with("api_rate_limit", type="integer", default=5)),
        "rule_1_settings_names",
    ),
    "rule1_env_var_bad_default": (
        lambda: _corpus(
            _with_option(
                _golden_module(),
                "action_key_env_var",
                {
                    "type": "string",
                    "default": "not-a-name",
                    "django_setting": "QUICKSCALE_DEMO_ACTION_KEY_ENV_VAR",
                    "description": "Environment variable name.",
                    "validation": {},
                },
            )
        ),
        "rule_1_settings_names",
    ),
    "rule1_credential_clean": (
        lambda: _corpus(_credential_module()),
        "rule_1_settings_names",
    ),
    "rule1_credential_unlisted": (
        lambda: _corpus(_credential_with_default("UNLISTED_DEMO_KEY")),
        "rule_1_settings_names",
    ),
    "rule1_credential_non_name": (
        lambda: _corpus(_credential_with_default("sk_live_1234")),
        "rule_1_settings_names",
    ),
    "rule1_credential_listed_vendor": (
        lambda: _corpus(_credential_with_default("STRIPE_SECRET_KEY")),
        "rule_1_settings_names",
    ),
    "rule1_credential_operator_stem": (
        lambda: _corpus(_credential_with_default("QUICKSCALE_DEMO_OPERATOR_KEY")),
        "rule_1_settings_names",
    ),
    "rule1_credential_foreign_stem": (
        lambda: _corpus(_credential_with_default("QUICKSCALE_OTHER_API_KEY")),
        "rule_1_settings_names",
    ),
    # rule 3: reading settings
    "rule3_clean": (lambda: _corpus(_golden_module()), "rule_3_settings_reads"),
    "rule3_undeclared": (
        lambda: _corpus(
            _service_module(
                "from django.conf import settings\n\nKEY = settings.QUICKSCALE_DEMO_MISSING\n"
            )
        ),
        "rule_3_settings_reads",
    ),
    "rule3_cross_module": (
        lambda: _corpus(
            _service_module(
                "from django.conf import settings\n\nKEY = settings.QUICKSCALE_BILLING_SECRET_KEY\n"
            )
        ),
        "rule_3_settings_reads",
    ),
    "rule3_getattr_default": (
        lambda: _corpus(
            _service_module(
                "from django.conf import settings\n\n"
                'KEY = getattr(settings, "QUICKSCALE_DEMO_ENABLED", True)\n'
            )
        ),
        "rule_3_settings_reads",
    ),
    "rule3_aliased_getattr": (
        lambda: _corpus(
            _service_module(
                "from django.conf import settings as cfg\n\n"
                'KEY = getattr(cfg, "QUICKSCALE_DEMO_ENABLED", True)\n'
            )
        ),
        "rule_3_settings_reads",
    ),
    "rule3_qualified_getattr": (
        lambda: _corpus(
            _service_module(
                "import django.conf as conf\n\n"
                'KEY = getattr(conf.settings, "QUICKSCALE_DEMO_ENABLED", True)\n'
            )
        ),
        "rule_3_settings_reads",
    ),
    "rule3_missing_setting": (
        lambda: _corpus(_tests_settings("SECRET_KEY = 'test'\n")),
        "rule_3_settings_reads",
    ),
    "rule3_commented_setting": (
        lambda: _corpus(
            _tests_settings(
                "SECRET_KEY = 'test'\n"
                "# QUICKSCALE_DEMO_ENABLED = True\n"
                "QUICKSCALE_DEMO_API_RATE_LIMIT = '5/hour'\n" + _GOLDEN_EXTRA_SETTINGS
            )
        ),
        "rule_3_settings_reads",
    ),
    "rule3_annotation_only": (
        lambda: _corpus(
            _tests_settings(
                "SECRET_KEY = 'test'\n"
                "QUICKSCALE_DEMO_ENABLED: bool\n"
                "QUICKSCALE_DEMO_API_RATE_LIMIT = '5/hour'\n" + _GOLDEN_EXTRA_SETTINGS
            )
        ),
        "rule_3_settings_reads",
    ),
    "rule3_annotated_value": (
        lambda: _corpus(
            _tests_settings(
                "SECRET_KEY = 'test'\n"
                "QUICKSCALE_DEMO_ENABLED: bool = True\n"
                "QUICKSCALE_DEMO_API_RATE_LIMIT = '5/hour'\n" + _GOLDEN_EXTRA_SETTINGS
            )
        ),
        "rule_3_settings_reads",
    ),
    "rule3_unpacked": (
        lambda: _corpus(
            _tests_settings(
                "SECRET_KEY = 'test'\n"
                "QUICKSCALE_DEMO_ENABLED, = (True,)\n"
                "QUICKSCALE_DEMO_API_RATE_LIMIT = '5/hour'\n" + _GOLDEN_EXTRA_SETTINGS
            )
        ),
        "rule_3_settings_reads",
    ),
    "rule3_derived_declared": (
        lambda: _corpus(_derived_setting_read(True)),
        "rule_3_settings_reads",
    ),
    "rule3_derived_undeclared": (
        lambda: _corpus(_derived_setting_read(False)),
        "rule_3_settings_reads",
    ),
    # rule 12: manifest option schema
    "rule12_clean": (lambda: _corpus(_golden_module()), "rule_12_manifest_options"),
    "rule12_malformed_config": (
        lambda: _corpus(_config([1])),
        "rule_12_manifest_options",
    ),
    "rule12_missing_dependencies": (
        lambda: _corpus(_manifest_without("dependencies")),
        "rule_12_manifest_options",
    ),
    "rule12_retired_implies": (
        lambda: _corpus(_manifest_with("implies", ["listings"])),
        "rule_12_manifest_options",
    ),
    "rule12_retired_validation_rules": (
        lambda: _corpus(_retired_validation_rules()),
        "rule_12_manifest_options",
    ),
    "rule12_bad_snake_case": (
        lambda: _corpus(
            _with_option(
                _golden_module(),
                "Bad-Key",
                {
                    "type": "string",
                    "default": "x",
                    "django_setting": "QUICKSCALE_DEMO_BAD_KEY",
                    "description": "Bad key.",
                    "validation": {},
                },
            )
        ),
        "rule_12_manifest_options",
    ),
    "rule12_unsupported_validation": (
        lambda: _corpus(_option_with("backend", validation={"regex": "nope"})),
        "rule_12_manifest_options",
    ),
    "rule12_missing_default": (
        lambda: _corpus(_option_without("backend", "default")),
        "rule_12_manifest_options",
    ),
    "rule12_missing_description": (
        lambda: _corpus(
            _with_option(
                _golden_module(),
                "api_rate_limit",
                {
                    "type": "string",
                    "default": "5/hour",
                    "django_setting": "QUICKSCALE_DEMO_API_RATE_LIMIT",
                    "validation": {},
                },
            )
        ),
        "rule_12_manifest_options",
    ),
    "rule12_immutable_setting": (
        lambda: _corpus(
            _config(
                {
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
            )
        ),
        "rule_12_manifest_options",
    ),
    "rule12_module_name_repeat": (
        lambda: _corpus(
            _with_option(
                _golden_module(),
                "demo_backend",
                {
                    "type": "string",
                    "default": "local",
                    "django_setting": "QUICKSCALE_DEMO_BACKEND",
                    "description": "Demo backend selector.",
                    "validation": {},
                },
            )
        ),
        "rule_12_manifest_options",
    ),
    "rule12_url_normalizer_missing": (
        lambda: _corpus(_derivation_without("cdn_url")),
        "rule_12_manifest_options",
    ),
    "rule12_url_normalizer_conflict": (
        lambda: _corpus(
            _derivation_added(
                "cdn_url",
                {
                    "source_key": "cdn_url",
                    "target_key": "cdn_url",
                    "rule_type": "url",
                    "description": "Conflicting absolute-URL kind.",
                },
            )
        ),
        "rule_12_manifest_options",
    ),
    "rule12_blank_pattern": (
        lambda: _corpus(_setting_pattern("cdn_url", "   ")),
        "rule_12_manifest_options",
    ),
    # rule 42: settings snapshots
    "rule42_clean": (lambda: _corpus(_golden_module()), "rule_42_settings_snapshots"),
    "rule42_snapshot_outside": (
        lambda: _corpus(_snapshot_outside()),
        "rule_42_settings_snapshots",
    ),
    "rule42_getter_outside": (
        lambda: _corpus(_getter_outside()),
        "rule_42_settings_snapshots",
    ),
    "rule42_exported": (
        lambda: _corpus(_exported_snapshot()),
        "rule_42_settings_snapshots",
    ),
    "rule42_exported_alias": (
        lambda: _corpus(_exported_alias()),
        "rule_42_settings_snapshots",
    ),
    "rule42_split_class": (
        lambda: _corpus(_split_class()),
        "rule_42_settings_snapshots",
    ),
    "rule42_alias_allowed": (
        lambda: _corpus(_alias_allowed()),
        "rule_42_settings_snapshots",
    ),
    # rule 43: optional senders
    "rule43_clean": (lambda: _corpus(_golden_module()), "rule_43_optional_senders"),
    "rule43_import_module_settings": (
        lambda: _corpus(
            _views_module(
                "from importlib import import_module\n\n\n"
                "def load_sender():\n"
                "    services = import_module('quickscale_modules_notifications.services')\n"
                "    return services.NotificationSettingsSnapshot.from_settings().enabled\n"
            )
        ),
        "rule_43_optional_senders",
    ),
    "rule43_catch_all": (
        lambda: _corpus(
            _views_module(
                "from quickscale_modules_notifications.services import send_notification\n\n\n"
                "def send_now() -> None:\n"
                "    try:\n"
                "        send_notification(template_key='x', recipients=[], context={})\n"
                "    except Exception:\n"
                "        return\n"
            )
        ),
        "rule_43_optional_senders",
    ),
    "rule43_dotted_catch_all": (
        lambda: _corpus(
            _views_module(
                "import quickscale_modules_notifications.services\n\n\n"
                "def send_now() -> None:\n"
                "    try:\n"
                "        quickscale_modules_notifications.services.send_notification(\n"
                "            template_key='x', recipients=[], context={}\n"
                "        )\n"
                "    except Exception:\n"
                "        return\n"
            )
        ),
        "rule_43_optional_senders",
    ),
    "rule43_dotted_narrowed": (
        lambda: _corpus(
            _views_module(
                "import quickscale_modules_notifications.services\n\n"
                "from quickscale_modules_notifications.services import NotificationsError\n\n\n"
                "def send_now() -> None:\n"
                "    try:\n"
                "        quickscale_modules_notifications.services.send_notification(\n"
                "            template_key='x', recipients=[], context={}\n"
                "        )\n"
                "    except NotificationsError:\n"
                "        return\n"
            )
        ),
        "rule_43_optional_senders",
    ),
    "rule43_best_effort": (
        lambda: _corpus(
            _views_module(
                "def emit() -> None:\n"
                "    from quickscale_modules_analytics.services import capture_event\n\n"
                "    try:\n"
                "        capture_event(distinct_id='x', event='e')\n"
                "    except Exception:\n"
                "        return\n"
            )
        ),
        "rule_43_optional_senders",
    ),
    "rule43_guard_optional": (
        lambda: _corpus(
            _views_module(
                "from django.apps import apps\n\n\n"
                "def notify() -> None:\n"
                "    if not apps.is_installed('quickscale_modules_notifications'):\n"
                "        return\n"
            )
        ),
        "rule_43_optional_senders",
    ),
    "rule43_guard_required": (
        lambda: _corpus(
            replace(
                _views_module(
                    "from django.apps import apps\n\n\n"
                    "def notify() -> None:\n"
                    "    if not apps.is_installed('quickscale_modules_notifications'):\n"
                    "        return\n"
                ),
                manifest={
                    **_golden_module().manifest,
                    "required_modules": ["notifications"],
                },
            )
        ),
        "rule_43_optional_senders",
    ),
    "rule43_getattr_default": (
        lambda: _corpus(
            _views_module(
                "from importlib import import_module\n\n\n"
                "def load_sender():\n"
                "    services = import_module('quickscale_modules_notifications.services')\n"
                "    return getattr(services, 'send_notification', None)\n"
            )
        ),
        "rule_43_optional_senders",
    ),
    "rule43_getattr_direct": (
        lambda: _corpus(
            _views_module(
                "from quickscale_modules_notifications.services import send_notification\n\n\n"
                "def load_sender():\n"
                "    return send_notification\n"
            )
        ),
        "rule_43_optional_senders",
    ),
    "rule43_getattr_aliased": (
        lambda: _corpus(
            _views_module(
                "import quickscale_modules_notifications.services as notifications_services\n\n\n"
                "def load_sender():\n"
                "    return getattr(notifications_services, 'send_notification', None)\n"
            )
        ),
        "rule_43_optional_senders",
    ),
    "rule43_getattr_from_package": (
        lambda: _corpus(
            _views_module(
                "from quickscale_modules_notifications import services as "
                "notifications_services\n\n\n"
                "def load_sender():\n"
                "    return getattr(notifications_services, 'send_notification', None)\n"
            )
        ),
        "rule_43_optional_senders",
    ),
}


EXACT_FINDINGS = (
    ("rule1_clean", "rule_1_settings_names", ()),
    ("rule1_no_enabled", "rule_1_settings_names", ("rule 1: demo: declares no enabled option",)),
    (
        "rule1_enabled_wrong_type",
        "rule_1_settings_names",
        (
            "rule 1: demo: enabled type is 'string', expected boolean",
            "rule 1: demo: option 'enabled' type is 'string', expected boolean",
        ),
    ),
    (
        "rule1_enabled_wrong_setting",
        "rule_1_settings_names",
        (
            (
                "rule 1: demo: enabled setting is 'QUICKSCALE_DEMO_ON', expected "
                "QUICKSCALE_DEMO_ENABLED"
            ),
        ),
    ),
    (
        "rule1_wrong_stem",
        "rule_1_settings_names",
        (
            (
                "rule 1: demo: option 'backend' setting QUICKSCALE_OTHER_BACKEND lacks the "
                "QUICKSCALE_DEMO_ stem"
            ),
        ),
    ),
    (
        "rule1_suffix_wrong_type",
        "rule_1_settings_names",
        ("rule 1: demo: option 'api_rate_limit' type is 'integer', expected string",),
    ),
    (
        "rule1_env_var_bad_default",
        "rule_1_settings_names",
        (
            (
                "rule 1: demo: option 'action_key_env_var' default 'not-a-name' is not an "
                "environment-variable name"
            ),
        ),
    ),
    ("rule1_credential_clean", "rule_1_settings_names", ()),
    (
        "rule1_credential_unlisted",
        "rule_1_settings_names",
        (
            (
                "rule 1: demo: option 'api_key_env_var' default UNLISTED_DEMO_KEY is not in the "
                "controlled vocabulary (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, POSTHOG_API_KEY, "
                "POSTHOG_HOST, RESEND_API_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_SECRET_KEY); the "
                "vendor's "
                "variable name or an operator's name is required"
            ),
        ),
    ),
    (
        "rule1_credential_non_name",
        "rule_1_settings_names",
        (
            (
                "rule 1: demo: option 'api_key_env_var' default 'sk_live_1234' is not an "
                "environment-variable name"
            ),
        ),
    ),
    ("rule1_credential_listed_vendor", "rule_1_settings_names", ()),
    ("rule1_credential_operator_stem", "rule_1_settings_names", ()),
    (
        "rule1_credential_foreign_stem",
        "rule_1_settings_names",
        (
            (
                "rule 1: demo: option 'api_key_env_var' default QUICKSCALE_OTHER_API_KEY lacks the "
                "QUICKSCALE_DEMO_ stem"
            ),
        ),
    ),
    ("rule3_clean", "rule_3_settings_reads", ()),
    (
        "rule3_undeclared",
        "rule_3_settings_reads",
        ("rule 3: demo: services.py:3 reads undeclared QUICKSCALE_DEMO_MISSING",),
    ),
    (
        "rule3_cross_module",
        "rule_3_settings_reads",
        ("rule 3: demo: services.py:3 reads billing's QUICKSCALE_BILLING_SECRET_KEY",),
    ),
    (
        "rule3_getattr_default",
        "rule_3_settings_reads",
        ("rule 3: demo: services.py:3 reads settings through getattr()",),
    ),
    (
        "rule3_aliased_getattr",
        "rule_3_settings_reads",
        ("rule 3: demo: services.py:3 reads settings through getattr()",),
    ),
    (
        "rule3_qualified_getattr",
        "rule_3_settings_reads",
        ("rule 3: demo: services.py:3 reads settings through getattr()",),
    ),
    (
        "rule3_missing_setting",
        "rule_3_settings_reads",
        (
            "rule 3: demo: tests/settings.py does not define QUICKSCALE_DEMO_API_RATE_LIMIT",
            "rule 3: demo: tests/settings.py does not define QUICKSCALE_DEMO_BACKEND",
            "rule 3: demo: tests/settings.py does not define QUICKSCALE_DEMO_CDN_URL",
            "rule 3: demo: tests/settings.py does not define QUICKSCALE_DEMO_ENABLED",
            "rule 3: demo: tests/settings.py does not define QUICKSCALE_DEMO_MARKETING_HOST",
        ),
    ),
    (
        "rule3_commented_setting",
        "rule_3_settings_reads",
        ("rule 3: demo: tests/settings.py does not define QUICKSCALE_DEMO_ENABLED",),
    ),
    (
        "rule3_annotation_only",
        "rule_3_settings_reads",
        ("rule 3: demo: tests/settings.py does not define QUICKSCALE_DEMO_ENABLED",),
    ),
    ("rule3_annotated_value", "rule_3_settings_reads", ()),
    ("rule3_unpacked", "rule_3_settings_reads", ()),
    ("rule3_derived_declared", "rule_3_settings_reads", ()),
    (
        "rule3_derived_undeclared",
        "rule_3_settings_reads",
        ("rule 3: demo: services.py:3 reads undeclared QUICKSCALE_DEMO_BACKEND_ALIAS",),
    ),
    ("rule12_clean", "rule_12_manifest_options", ()),
    (
        "rule12_malformed_config",
        "rule_12_manifest_options",
        ("rule 12: demo: config must declare mutable and immutable",),
    ),
    (
        "rule12_missing_dependencies",
        "rule_12_manifest_options",
        ("rule 12: demo: manifest has no dependencies key",),
    ),
    (
        "rule12_retired_implies",
        "rule_12_manifest_options",
        ("rule 12: demo: retired implies key present",),
    ),
    (
        "rule12_retired_validation_rules",
        "rule_12_manifest_options",
        ("rule 12: demo: manifest declares retired validation_rules",),
    ),
    (
        "rule12_bad_snake_case",
        "rule_12_manifest_options",
        ("rule 12: demo: option 'Bad-Key' is not snake_case",),
    ),
    (
        "rule12_unsupported_validation",
        "rule_12_manifest_options",
        ("rule 12: demo: option 'backend' uses unsupported validation key 'regex'",),
    ),
    (
        "rule12_missing_default",
        "rule_12_manifest_options",
        ("rule 12: demo: option 'backend' has no default",),
    ),
    (
        "rule12_missing_description",
        "rule_12_manifest_options",
        ("rule 12: demo: option 'api_rate_limit' has no description",),
    ),
    (
        "rule12_immutable_setting",
        "rule_12_manifest_options",
        ("rule 12: demo: option 'mode' is immutable but declares a django_setting",),
    ),
    (
        "rule12_module_name_repeat",
        "rule_12_manifest_options",
        ("rule 12: demo: option 'demo_backend' repeats the module name",),
    ),
    (
        "rule12_url_normalizer_missing",
        "rule_12_manifest_options",
        (
            (
                "rule 12: demo: option 'cdn_url' declares no url-family normalization rule "
                "(expected url "
                "or path_or_absolute_url)"
            ),
        ),
    ),
    (
        "rule12_url_normalizer_conflict",
        "rule_12_manifest_options",
        (
            (
                "rule 12: demo: option 'cdn_url' declares conflicting normalization kinds "
                "['path_or_absolute_url', 'url']"
            ),
        ),
    ),
    (
        "rule12_blank_pattern",
        "rule_12_manifest_options",
        ("rule 12: demo: option 'cdn_url' declares a blank validation pattern",),
    ),
    ("rule42_clean", "rule_42_settings_snapshots", ()),
    (
        "rule42_snapshot_outside",
        "rule_42_settings_snapshots",
        (
            (
                "rule 42: demo: services.py:6 defines the settings snapshot "
                "DemoRuntimeSettingsSnapshot "
                "outside _settings.py"
            ),
        ),
    ),
    (
        "rule42_getter_outside",
        "rule_42_settings_snapshots",
        ("rule 42: demo: services.py:9 builds a settings snapshot outside _settings.py",),
    ),
    (
        "rule42_exported",
        "rule_42_settings_snapshots",
        ("rule 42: demo: services.py exports the settings snapshot DemoPolicySnapshot",),
    ),
    (
        "rule42_exported_alias",
        "rule_42_settings_snapshots",
        ("rule 42: demo: services.py exports the settings snapshot DemoSettingsSnapshot",),
    ),
    (
        "rule42_split_class",
        "rule_42_settings_snapshots",
        (
            (
                "rule 42: demo: services.py:6 defines the settings snapshot "
                "DemoSettingsSnapshot outside "
                "_settings.py"
            ),
        ),
    ),
    ("rule42_alias_allowed", "rule_42_settings_snapshots", ()),
    ("rule43_clean", "rule_43_optional_senders", ()),
    (
        "rule43_import_module_settings",
        "rule_43_optional_senders",
        (
            (
                "rule 43: demo: views.py:6 reads notifications's settings through "
                "NotificationSettingsSnapshot"
            ),
        ),
    ),
    (
        "rule43_catch_all",
        "rule_43_optional_senders",
        ("rule 43: demo: views.py:7 catches Exception around notifications's service call",),
    ),
    (
        "rule43_dotted_catch_all",
        "rule_43_optional_senders",
        ("rule 43: demo: views.py:9 catches Exception around notifications's service call",),
    ),
    ("rule43_dotted_narrowed", "rule_43_optional_senders", ()),
    ("rule43_best_effort", "rule_43_optional_senders", ()),
    ("rule43_guard_optional", "rule_43_optional_senders", ()),
    (
        "rule43_guard_required",
        "rule_43_optional_senders",
        ("rule 43: demo: views.py:5 guards required module notifications with apps.is_installed",),
    ),
    (
        "rule43_getattr_default",
        "rule_43_optional_senders",
        ("rule 43: demo: views.py:6 reads notifications's service through getattr with a default",),
    ),
    ("rule43_getattr_direct", "rule_43_optional_senders", ()),
    (
        "rule43_getattr_aliased",
        "rule_43_optional_senders",
        ("rule 43: demo: views.py:5 reads notifications's service through getattr with a default",),
    ),
    (
        "rule43_getattr_from_package",
        "rule_43_optional_senders",
        ("rule 43: demo: views.py:5 reads notifications's service through getattr with a default",),
    ),
)


def test_rule_3_keeps_the_pre_split_syntax_error_precedence() -> None:
    """A malformed adapter.py is parsed before tests/settings.py, as pre-split."""
    module = _with_files(_golden_module(), adapter="def broken(\n")
    module = replace(
        module,
        tests={**module.tests, "settings.py": "SECRET_KEY = 1\nif :\n"},
    )
    with pytest.raises(SyntaxError) as excinfo:
        rules_settings.rule_3_settings_reads(_corpus(module))
    # The pre-split module's message, captured from the pinned interpreter.
    assert str(excinfo.value) == "'(' was never closed (<unknown>, line 1)"


def test_rule_37_exempts_only_the_facade() -> None:
    """The split siblings stay inside rule 37's closed world."""
    assert ("scripts", "module_conventions/rules_settings.py") in RULE_37_ALLOWED_LITERAL_FILES
    for name in SPLIT_SIBLINGS:
        assert (
            "scripts",
            f"module_conventions/{name}.py",
        ) not in RULE_37_ALLOWED_LITERAL_FILES


def test_the_module_name_table_stays_in_the_facade() -> None:
    """Rule 43's best-effort module table is rule 37's facade-owned literal."""
    assert rules_settings._RULE_43_BEST_EFFORT_MODULES == frozenset({"analytics"})
    for name, module in SPLIT_SIBLINGS.items():
        assert not hasattr(module, "_RULE_43_BEST_EFFORT_MODULES"), name


def test_split_siblings_never_import_the_facade_or_registry() -> None:
    """Helpers reach their collaborators through siblings, never the facade."""
    for name, module in SPLIT_SIBLINGS.items():
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[-1] not in {"rules_settings", "registry"}, (
                    name,
                    node.lineno,
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[-1] not in {"rules_settings", "registry"}, (
                        name,
                        node.lineno,
                    )


@pytest.mark.parametrize(
    ("case", "detector", "expected"),
    EXACT_FINDINGS,
    ids=[f"{case}-{detector}" for case, detector, _ in EXACT_FINDINGS],
)
def test_detector_findings_are_exact_and_ordered(
    case: str, detector: str, expected: tuple[str, ...]
) -> None:
    builder, registered = CASES[case]
    assert registered == detector
    corpus = builder()
    assert getattr(rules_settings, detector)(corpus) == list(expected)
