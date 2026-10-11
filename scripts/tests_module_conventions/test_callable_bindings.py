"""Lexical callable identity controls for the registered option-boundary rule."""

import pytest

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import _golden_module, _violations, _with_files


def _check(source: str) -> list[str]:
    module = _with_files(_golden_module(), adapter=source)
    first = _violations(checker.rule_12_adapter_duplicate_logic, module)
    assert first == _violations(checker.rule_12_adapter_duplicate_logic, module)
    return first


def test_captured_builtin_is_not_resolved_in_the_hook_frame() -> None:
    source = (
        "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
        "def identity(value):\n    return value\n"
        "def factory():\n    coerce = bool\n"
        "    def hook(spec, values):\n        bool = identity\n"
        '        coerce(values["enabled"])\n'
        "        return spec\n    return hook\n"
        "def adapter(options):\n"
        '    return assemble("demo", options, post_hook=factory())\n'
    )
    assert _check(source) == [
        "rule 12: demo: adapter.py:8 coerces an option container read with bool()"
    ]


@pytest.mark.parametrize("order", ["ab", "ba"])
def test_duplicate_local_validators_keep_definition_policy(order) -> None:
    factories = {
        "a": (
            "def factory_a():\n"
            '    def validate_backend(value):\n        return value == "local"\n'
            "    def hook(spec, values):\n"
            '        validate_backend(values["backend"])\n'
            "        return spec\n    return hook\n"
        ),
        "b": (
            "def factory_b():\n"
            "    def validate_backend(value):\n        return value\n"
            "    return validate_backend\n"
        ),
    }
    source = (
        "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
        + "".join(factories[key] for key in order)
        + "def adapter(options):\n"
        '    return assemble("demo", options, post_hook=factory_a())\n'
    )
    line = 6 if order == "ab" else 10
    assert _check(source) == [
        f"rule 12: demo: adapter.py:{line} re-validates an option container read "
        "through validate_backend()"
    ]


@pytest.mark.parametrize("actual", ["identity", "validate_backend", "bool"])
@pytest.mark.parametrize("call", ["factory({actual})", "factory(check={actual})"])
def test_intermediate_factory_parameter_captures_the_actual_callable(actual, call) -> None:
    source = (
        "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
        "from vendor import validate_backend\n"
        "def identity(value):\n    return value\n"
        "def outer():\n    check = validate_backend\n"
        "    def factory(check):\n        def hook(spec, values):\n"
        '            check(values["backend"])\n'
        "            return spec\n        return hook\n"
        f"    return {call.format(actual=actual)}\n"
        "def adapter(options):\n"
        '    return assemble("demo", options, post_hook=outer())\n'
    )
    expected = {
        "identity": [],
        "validate_backend": [
            "rule 12: demo: adapter.py:9 re-validates an option container read "
            "through validate_backend()"
        ],
        "bool": ["rule 12: demo: adapter.py:9 coerces an option container read with bool()"],
    }
    assert _check(source) == expected[actual]


@pytest.mark.parametrize(
    "binding",
    ["from vendor import collect as check", "def check(value):\n            return value"],
)
def test_intermediate_import_and_definition_are_shadow_barriers(binding) -> None:
    source = (
        "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
        "from vendor import validate_backend\n"
        "def outer():\n    check = validate_backend\n"
        f"    def factory():\n        {binding}\n"
        "        def hook(spec, values):\n"
        '            check(values["backend"])\n'
        "            return spec\n        return hook\n    return factory()\n"
        "def adapter(options):\n"
        '    return assemble("demo", options, post_hook=outer())\n'
    )
    assert _check(source) == []


@pytest.mark.parametrize("order", ["identity, validate_backend", "validate_backend, identity"])
def test_two_instantiations_do_not_merge_callable_parameters(order) -> None:
    source = (
        "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
        "from vendor import validate_backend\n"
        "def identity(value):\n    return value\n"
        "def factory(check):\n    def hook(spec, values):\n"
        '        check(values["backend"])\n'
        "        return spec\n    return hook\n"
        "def adapter(options):\n"
        f"    first, second = {order}\n"
        '    assemble("demo", options, post_hook=factory(first))\n'
        '    return assemble("demo", options, post_hook=factory(second))\n'
    )
    # Use ordinary scalar assignments, not unsupported tuple alias extraction.
    source = source.replace(
        f"    first, second = {order}",
        "    first = " + order.split(", ")[0] + "\n    second = " + order.split(", ")[1],
    )
    assert _check(source) == [
        "rule 12: demo: adapter.py:7 re-validates an option container read "
        "through validate_backend()"
    ]


@pytest.mark.parametrize(
    "signature, actual",
    [("check=bool", ""), ("*, check=bool", ""), ("check, /", "bool"), ("*, check", "check=bool")],
)
def test_callable_actuals_and_defaults_keep_their_defining_frame(signature, actual) -> None:
    source = (
        "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
        "def identity(value):\n    return value\n"
        f"def factory({signature}):\n    bool = identity\n"
        "    def hook(spec, values):\n"
        '        check(values["enabled"])\n'
        "        return spec\n    return hook\n"
        "def adapter(options):\n"
        f'    return assemble("demo", options, post_hook=factory({actual}))\n'
    )
    assert _check(source) == [
        "rule 12: demo: adapter.py:7 coerces an option container read with bool()"
    ]


@pytest.mark.parametrize("actual", ["identity", "validate_backend"])
def test_returned_adapter_seeds_hook_with_its_captured_callable(actual) -> None:
    source = (
        "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
        "from quickscale_core.runtime import validate_module_options as validate_backend\n"
        "def identity(value):\n    return value\n"
        "def factory(check):\n"
        "    def hook(spec, values):\n"
        '        check(values["backend"])\n'
        "        return spec\n"
        "    def adapter(options):\n"
        '        return assemble("demo", options, post_hook=hook)\n'
        "    return adapter\n"
        "def get_manifest_adapter():\n"
        f"    return factory({actual})\n"
    )
    expected = (
        []
        if actual == "identity"
        else [
            "rule 12: demo: adapter.py:7 re-validates an option container read "
            "through validate_module_options()"
        ]
    )
    assert _check(source) == expected


def test_captured_callable_is_forwarded_through_an_ordinary_helper() -> None:
    source = (
        "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
        "from vendor import validate_backend\n"
        "def helper(check, value):\n    check(value)\n"
        "def factory(check):\n    def hook(spec, values):\n"
        '        helper(check, values["backend"])\n'
        "        return spec\n    return hook\n"
        "def adapter(options):\n"
        '    return assemble("demo", options, post_hook=factory(validate_backend))\n'
    )
    assert _check(source) == [
        "rule 12: demo: adapter.py:4 re-validates an option container read "
        "through validate_backend()"
    ]


@pytest.mark.parametrize("definition", ["module", "unrelated_factory"])
def test_definition_identity_never_collides_with_builtin_policy(definition) -> None:
    declaration = "def bool(value):\n    return value\n"
    if definition == "unrelated_factory":
        declaration = (
            "def unrelated():\n    def bool(value):\n        return value\n    return bool\n"
        )
    source = (
        "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
        + declaration
        + "def hook(spec, values):\n"
        '    bool(values["enabled"])\n'
        "    return spec\n"
        "def adapter(options):\n"
        '    return assemble("demo", options, post_hook=hook)\n'
    )
    expected = (
        []
        if definition == "module"
        else ["rule 12: demo: adapter.py:7 coerces an option container read with bool()"]
    )
    assert _check(source) == expected
