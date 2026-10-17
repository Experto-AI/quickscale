"""Controls for manifest ownership: URL clauses, declared reads, and credential defaults."""

from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import _golden_module, _violations, _with_files


@pytest.mark.parametrize(
    "validation", [None, {}, {"not_empty": True}, {"pattern": ""}, {"pattern": "  "}]
)
def test_absolute_url_requires_real_pattern(validation) -> None:
    module = _golden_module()
    manifest = copy.deepcopy(module.manifest)
    manifest["config"]["mutable"]["marketing_host"]["validation"] = validation
    assert _violations(checker.rule_12_manifest_options, replace(module, manifest=manifest))


@pytest.mark.parametrize("kind", ["static", "direct", "computed"])
@pytest.mark.parametrize("root", [True, False])
def test_declared_derived_setting_reads_without_adapter_literals(kind, root) -> None:
    module = _golden_module()
    manifest = copy.deepcopy(module.manifest)
    expression = {
        "static": {"value": "local"},
        "direct": {"option": "backend"},
        "computed": {"template": "{backend}"},
    }[kind]
    entry = {
        "setting_key": "QUICKSCALE_DEMO_ALIAS",
        "derivation_type": kind,
        "expression": expression,
    }
    body = (
        manifest["derivation"]
        if root
        else manifest["derivation"]["option_derivations"].setdefault("backend", {})
    )
    body["derived_settings"] = [entry]
    source = "from django.conf import settings\nVALUE = settings.QUICKSCALE_DEMO_ALIAS\n"
    declared = _with_files(replace(module, manifest=manifest), services=source)
    assert _violations(checker.rule_3_settings_reads, declared) == []
    assert _violations(checker.rule_3_settings_reads, _with_files(module, services=source))
    entry["setting_key"] = "QUICKSCALE_BILLING_ALIAS"
    assert _violations(
        checker.rule_3_settings_reads,
        _with_files(
            replace(module, manifest=manifest),
            services=source.replace("DEMO_ALIAS", "BILLING_ALIAS"),
        ),
    )


@pytest.mark.parametrize(
    ("key", "option_type", "value", "allowed"),
    [
        ("pattern", "integer", "^1$", False),
        ("pattern", "string", "^local$", True),
        ("min", "string", 1, False),
        ("min", "integer", 1, True),
        ("not_empty", "boolean", True, False),
        ("not_empty", "list", True, True),
        ("subset_of", "string", "backend", False),
        ("subset_of", "list", "backend", True),
        ("intersects", "string", {"values": ["local"]}, False),
        ("intersects", "list", {"values": ["local"]}, True),
        ("excludes", "list", {"values": ["local"]}, False),
        ("excludes", "string", {"values": ["local"]}, True),
        ("choices", "integer", [1, 2], True),
        ("required_when", "boolean", {"enabled": True}, True),
        ("any_of", "string", ["backend"], True),
    ],
)
def test_validation_key_must_fit_the_option_type(key, option_type, value, allowed) -> None:
    """Rule 12: a validation key only applies to the types it can check."""
    module = _golden_module()
    manifest = copy.deepcopy(module.manifest)
    option = manifest["config"]["mutable"]["backend"]
    option["type"] = option_type
    option["default"] = {
        "integer": 1,
        "string": "local",
        "boolean": True,
        "list": ["local"],
    }[option_type]
    option["validation"] = {key: value}
    violations = _violations(checker.rule_12_manifest_options, replace(module, manifest=manifest))
    mismatched = [violation for violation in violations if "uses validation key" in violation]
    assert bool(mismatched) is not allowed


def test_known_vendor_defaults_are_bound_to_each_declaration() -> None:
    root = Path(__file__).resolve().parents[2]
    corpus = checker.load_corpus(root)
    for module in corpus.modules:
        options = module.manifest["config"]["mutable"]
        for key, option in options.items():
            if option.get("default") not in checker.CREDENTIAL_REFERENCE_NAMES:
                continue
            assert _violations(checker.rule_1_settings_names, module) == []
            for wrong in (
                "STRIPE_SECRET_KEY"
                if option["default"] != "STRIPE_SECRET_KEY"
                else "POSTHOG_API_KEY",
                f"QUICKSCALE_{module.name.upper()}_UNLISTED_KEY",
            ):
                changed = copy.deepcopy(module.manifest)
                changed["config"]["mutable"][key]["default"] = wrong
                assert _violations(checker.rule_1_settings_names, replace(module, manifest=changed))


def test_reasoned_exception_defaults_remain_exact() -> None:
    corpus = checker.load_corpus(Path(__file__).resolve().parents[2])
    for module in corpus.modules:
        for key, entry in checker.QUICKSCALE_ENV_VAR_DEFAULT_EXCEPTIONS.get(
            module.name, {}
        ).items():
            assert entry["why"].strip()
            assert _violations(checker.rule_1_settings_names, module) == []
            changed = copy.deepcopy(module.manifest)
            changed["config"]["mutable"][key]["default"] = entry["default"] + "_DRIFT"
            assert _violations(checker.rule_1_settings_names, replace(module, manifest=changed))
