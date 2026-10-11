"""Adversarial controls for manifest ownership and bounded adapter provenance."""

from __future__ import annotations

import ast
import copy
import re
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import check_module_conventions as checker
from scripts.module_conventions.adapter_flow import AdapterFlow
from scripts.tests_module_conventions._support import _golden_module, _violations, _with_files
from scripts.tests_module_conventions.test_settings import _with_adapter


@pytest.mark.parametrize(
    "validation", [None, {}, {"not_empty": True}, {"pattern": ""}, {"pattern": "  "}]
)
def test_absolute_url_requires_real_pattern(validation) -> None:
    module = _golden_module()
    manifest = copy.deepcopy(module.manifest)
    manifest["config"]["mutable"]["marketing_host"]["validation"] = validation
    assert _violations(checker.rule_12_manifest_options, replace(module, manifest=manifest))


@pytest.mark.parametrize(
    "body",
    [
        '    opts = resolved\n    opts.get("backend", "local")',
        '    value = resolved["backend"]\n    value.strip()',
        '    bool(spec.settings["QUICKSCALE_DEMO_ENABLED"])',
        "    mapped = dict(spec.settings)\n"
        '    value = mapped["QUICKSCALE_DEMO_BACKEND"]\n    value.lower()',
        '    if resolved["backend"] == "remote":\n        raise ValueError("no remote")',
        '    opts = resolved\n    for key in ("backend",):\n        opts.get(key, "local")',
        "    for value in resolved.values():\n        str(value)",
        '    for value in (resolved["backend"],):\n        value.casefold()',
        '    value: str = resolved["backend"]\n    alias = value\n    bool(alias)',
        '    if spec.settings["QUICKSCALE_DEMO_BACKEND"] != "local":\n'
        '        raise ValueError("bad")',
        '    assert resolved["backend"] == "local"',
        '    if resolved.get("backend", "local") == "remote":\n        return spec',
        '    if int(resolved["enabled"]):\n        return spec',
        '    [value.strip() for value in (resolved["backend"],)]',
        "    [value.lower() for value in resolved.values()]",
    ],
)
def test_bounded_option_provenance_rejects_rewrites_and_rejection(body) -> None:
    module = _with_adapter(_golden_module(), body + "\n    return spec")
    found = _violations(checker.rule_12_adapter_duplicate_logic, module)
    assert found and all("rule 12: demo: adapter.py:" in row for row in found)
    # The declared keys and mapped settings, not parameter names, are authority.
    renamed = _with_files(module, adapter=module.files["adapter.py"].replace("resolved", "payload"))
    assert _violations(checker.rule_12_adapter_duplicate_logic, renamed)


@pytest.mark.parametrize(
    "body",
    [
        "    copied = dict(spec.settings)\n    return spec",
        '    if not resolved["enabled"]:\n        return spec\n    return spec',
        '    composite = {"rate": resolved["api_rate_limit"]}\n    return spec',
        "    if not project_package:\n"
        '        raise ValueError("package required")\n    return spec',
        '    if "target" not in spec.managed_files:\n'
        '        raise ValueError("target missing")\n    return spec',
    ],
)
def test_behavioral_and_structural_controls_stay_legal(body) -> None:
    assert (
        _violations(checker.rule_12_adapter_duplicate_logic, _with_adapter(_golden_module(), body))
        == []
    )


def test_boolean_annotation_is_not_a_blanket_predicate_exemption() -> None:
    module = _with_adapter(
        _golden_module(),
        "    _ready(resolved)\n    return spec\n\n\ndef _ready(payload: dict[str, Any]) -> bool:\n"
        '    payload.get("backend", "local")\n    return True',
    )
    assert _violations(checker.rule_12_adapter_duplicate_logic, module)


@pytest.mark.parametrize(
    "body",
    [
        '    if resolved.get("enabled", True):\n        return spec',
        '    if bool(resolved.get("enabled", False)):\n        return spec',
        '    if bool(resolved["enabled"]):\n        return spec',
        "    opts = resolved\n    for value in opts.values():\n        value.strip()",
        "    opts = resolved\n    for key, value in opts.items():\n        value.lower()",
        "    opts = resolved\n    [value.casefold() for value in opts.values()]",
        '    opts = dict(resolved)\n    key = "backend"\n    opts[key].strip()',
        "    mapped = dict(spec.settings)\n    for value in mapped.values():\n        str(value)",
        "    _helper(resolved)\n    return spec\n\n"
        "def _helper(payload) -> bool:\n"
        '    candidate = payload["backend"].strip()\n    return candidate == "local"',
        '    _helper(value=resolved["backend"])\n    return spec\n\n'
        "def _helper(*, value):\n    alias = value\n    return alias.lower()",
        "    alias = _helper\n    alias(resolved)\n    return spec\n\n"
        'def _helper(payload):\n    opts = payload\n    opts.get("backend", "local")',
        '    copied = _helper(resolved)\n    copied["backend"].strip()\n    return spec\n\n'
        "def _helper(payload):\n    return dict(payload)",
        '    if resolved["enabled"]:\n        opts = resolved\n'
        '    else:\n        opts = {}\n    opts["backend"].strip()',
    ],
)
def test_untyped_boundary_and_helper_aliases_are_enforced(body) -> None:
    module = _with_adapter(_golden_module(), body + "\n    return spec")
    source = module.files["adapter.py"].replace("resolved: dict[str, Any]", "payload")
    source = source.replace("resolved", "payload").replace("spec: ModuleWiringSpec", "assembled")
    source = re.sub(r"\bspec\b", "assembled", source)
    found = _violations(
        checker.rule_12_adapter_duplicate_logic, _with_files(module, adapter=source)
    )
    assert found and all("rule 12: demo: adapter.py:" in row for row in found)


@pytest.mark.parametrize(
    "body",
    [
        '    targets = spec.managed_files\n    if not targets["backend"]:\n'
        '        raise ValueError("missing target")',
        '    targets: dict[str, str] = {"backend": "renderer"}\n'
        '    if not targets.get("backend", ""):\n        raise ValueError("missing target")',
        '    payload = {"backend": "renderer"}\n    payload["backend"].strip()',
        '    if not project_package:\n        raise ValueError("package")',
        "    copied = dict(spec.settings)\n"
        '    composite = {"rate": copied["QUICKSCALE_DEMO_API_RATE_LIMIT"]}',
        '    if not resolved["enabled"]:\n        return spec',
        "    for key, value in resolved.items():\n        key.strip()",
    ],
)
def test_structural_key_collisions_never_seed_option_provenance(body) -> None:
    assert (
        _violations(
            checker.rule_12_adapter_duplicate_logic,
            _with_adapter(_golden_module(), body + "\n    return spec"),
        )
        == []
    )


def _query_adapter(body: str, query_body: str = '    return bool(values["enabled"])'):
    module = _with_adapter(
        _golden_module(),
        body + "\n    return spec\n\n"
        "def _ready(values):\n" + query_body + "\n\n"
        "def public_ready(options):\n"
        '    return _ready(resolve_manifest_module_options("demo", options))',
    )
    return _with_files(
        module,
        adapter=module.files["adapter.py"].replace(
            "from typing import Any",
            "from typing import Any\n"
            "from quickscale_core.runtime.manifest import resolve_manifest_module_options",
        ),
    )


@pytest.mark.parametrize(
    "query_body",
    [
        '    candidate = str(values.get("backend", "")).strip()\n'
        '    return bool(values.get("enabled", False)) and candidate == "local"',
        '    if not values.get("enabled", True):\n        return None\n'
        '    if values["backend"] == "local":\n        return "console"\n    return "live"',
    ],
)
def test_normalization_rooted_queries_are_selection_not_projection(query_body) -> None:
    module = _query_adapter("    if _ready(resolved):\n        return spec", query_body)
    assert _violations(checker.rule_12_adapter_duplicate_logic, module) == []


@pytest.mark.parametrize(
    "body",
    [
        '    opts = resolved\n    if opts.get("enabled", True):\n        return spec',
        '    _ready(resolved)\n    resolved["backend"].strip()',
        "    settings = dict(spec.settings)\n"
        '    settings["QUICKSCALE_DEMO_ENABLED"] = _ready(resolved)',
        '    settings = {"QUICKSCALE_DEMO_ENABLED": _ready(resolved)}',
        "    settings = dict(spec.settings)\n"
        '    settings["QUICKSCALE_DEMO_ENABLED"] = _ready(resolved) or False',
        "    _other(resolved)\n    return spec\n\n"
        'def _other(values) -> bool:\n    candidate = values["backend"].strip()\n'
        '    return candidate == "local"',
    ],
)
def test_query_allowance_does_not_hide_mixed_wiring_policy(body) -> None:
    assert _violations(checker.rule_12_adapter_duplicate_logic, _query_adapter(body))


def test_query_results_inside_legitimate_structural_composites_are_legal() -> None:
    module = _query_adapter(
        '    composite = {"enabled": _ready(resolved)}\n'
        '    targets = {"backend": "renderer"}\n'
        '    targets["backend"] = _ready(resolved)'
    )
    assert _violations(checker.rule_12_adapter_duplicate_logic, module) == []


def test_raw_boundary_alias_construction_is_not_a_seeding_bypass() -> None:
    module = _with_files(
        _golden_module(),
        adapter=(
            "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
            "def adapter(payload):\n"
            '    alias = payload\n    canonical = {"backend": alias["backend"].strip()}\n'
            '    return assemble("demo", canonical)\n'
        ),
    )
    assert _violations(checker.rule_12_adapter_duplicate_logic, module)


@pytest.mark.parametrize(
    "declaration",
    [
        "from vendor import validate_backend as verify\n",
        'def validate_backend(value):\n    return value == "local"\nverify = validate_backend\n',
    ],
)
@pytest.mark.parametrize(
    "aliases", ["", "    check = verify\n", "    first = verify\n    check: object = first\n"]
)
@pytest.mark.parametrize(
    "read",
    [
        '    {call}(payload["backend"])',
        '    {call}(value=payload["backend"])',
        '    scalar = payload["backend"]\n    alias = scalar\n    {call}(alias)',
        '    copied = dict(assembled.settings)\n    {call}(copied["QUICKSCALE_DEMO_BACKEND"])',
        "    for key, value in payload.items():\n        {call}(value)",
        "    [{call}(value) for value in payload.values()]",
    ],
)
def test_validator_references_reject_owned_values_with_exact_diagnostics(
    declaration, aliases, read
) -> None:
    called = "check" if aliases else "verify"
    body = aliases + read.format(call=called) + "\n    return assembled"
    module = _with_adapter(_golden_module(), body)
    source = declaration + re.sub(r"\bspec\b", "assembled", module.files["adapter.py"]).replace(
        "resolved", "payload"
    )
    line = next(
        index
        for index, text in enumerate(source.splitlines(), 1)
        if f"{called}(" in text and not text.startswith("def ")
    )
    found = _violations(
        checker.rule_12_adapter_duplicate_logic, _with_files(module, adapter=source)
    )
    assert any(row.startswith(f"rule 12: demo: adapter.py:{line} re-validates") for row in found)


def _factory_adapter(body: str, spelling: str) -> str:
    returns = {
        "direct": "    return hook\n",
        "alias": "    alias = hook\n    return alias\n",
        "chain": "    first = hook\n    alias: object = first\n    return alias\n",
        "nested": "    alias = hook\n    return alias\n",
    }
    source = (
        "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
        "def factory():\n    def hook(assembled, payload):\n"
        + "\n".join("    " + line for line in body.splitlines())
        + "\n        return assembled\n"
        + returns[spelling]
    )
    if spelling == "nested":
        source += "def outer():\n    alias = factory\n    result = alias()\n    return result\n"
    factory = "outer" if spelling == "nested" else "factory"
    return source + (
        "def adapter(options):\n    builder = assemble\n"
        f"    creator = {factory}\n    chosen = creator()\n"
        '    return builder("demo", options, post_hook=chosen)\n'
    )


@pytest.mark.parametrize("spelling", ["direct", "alias", "chain", "nested"])
@pytest.mark.parametrize(
    "body, offending",
    [
        ('    payload.get("backend", "local")', "payload.get"),
        (
            '    copy = dict(assembled.settings)\n    copy["QUICKSCALE_DEMO_BACKEND"].lower()',
            "copy[",
        ),
        ('    scalar = payload["backend"]\n    scalar.strip()', "scalar.strip"),
        ('    for key in ("backend",):\n        payload.get(key, "local")', "payload.get"),
        ("    for value in payload.values():\n        str(value)", "str(value)"),
        ('    coerce = bool\n    coerce(payload["enabled"])', "coerce(payload"),
        ('    if not payload["backend"]:\n        raise ValueError("missing")', "if not"),
        (
            "    from vendor import validate_backend as verify\n"
            '    check = verify\n    check(value=payload["backend"])',
            "check(value",
        ),
    ],
)
def test_factory_return_references_seed_actual_hook_with_exact_diagnostics(
    spelling, body, offending
) -> None:
    source = _factory_adapter(body, spelling)
    line = next(index for index, text in enumerate(source.splitlines(), 1) if offending in text)
    found = _violations(
        checker.rule_12_adapter_duplicate_logic, _with_files(_golden_module(), adapter=source)
    )
    assert any(row.startswith(f"rule 12: demo: adapter.py:{line} ") for row in found)


@pytest.mark.parametrize("spelling", ["direct", "alias", "chain", "nested"])
@pytest.mark.parametrize(
    "body",
    [
        "    copier = dict\n    copied = copier(assembled.settings)",
        '    composite = {"rate": payload["api_rate_limit"]}',
        '    if not payload["enabled"]:\n        return assembled',
        '    package = "demo"\n    if not package:\n        raise ValueError("package")',
        '    targets = assembled.managed_files\n    if not targets.get("backend", ""):\n'
        '        raise ValueError("target")',
        "    from vendor import validate_backend as verify\n"
        '    check = verify\n    targets = {"backend": "renderer"}\n    check(targets["backend"])',
        "    if ready(payload):\n        return assembled",
    ],
)
def test_factory_reference_controls_preserve_legal_contexts(spelling, body) -> None:
    source = _factory_adapter(body, spelling) + (
        "from quickscale_core.runtime.manifest import resolve_manifest_module_options\n"
        "def ready(values):\n"
        '    candidate = str(values.get("backend", "")).strip()\n'
        '    return bool(values.get("enabled", False)) and candidate == "local"\n'
        "def public_ready(options):\n"
        '    return ready(resolve_manifest_module_options("demo", options))\n'
    )
    assert (
        _violations(
            checker.rule_12_adapter_duplicate_logic, _with_files(_golden_module(), adapter=source)
        )
        == []
    )


_CLOSURE_RETURNS = {
    "direct": "    return hook\n",
    "alias": "    chosen = hook\n    return chosen\n",
    "chain": "    first = hook\n    chosen: object = first\n    return chosen\n",
    "nested": "    chosen = hook\n    return chosen\n",
}


def _closure_adapter(body: str, spelling: str, binding: str, preamble: str = "") -> str:
    """Return an adapter whose nested hook closes over ``binding``."""
    source = (
        "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
        + preamble
        + "def factory():\n"
        + binding
        + "    def hook(assembled, payload):\n"
        + "\n".join("    " + line for line in body.splitlines())
        + "\n        return assembled\n"
        + _CLOSURE_RETURNS[spelling]
    )
    if spelling == "nested":
        source += "def outer():\n    alias = factory\n    result = alias()\n    return result\n"
    factory = "outer" if spelling == "nested" else "factory"
    return source + (
        "def adapter(options):\n    builder = assemble\n"
        f"    creator = {factory}\n    chosen = creator()\n"
        '    return builder("demo", options, post_hook=chosen)\n'
    )


@pytest.mark.parametrize("spelling", ["direct", "alias", "chain", "nested"])
@pytest.mark.parametrize(
    "body, offending",
    [
        ('    check(payload["backend"])', "check(payload"),
        ('    check(value=payload["backend"])', "check(value"),
        ('    scalar = payload["backend"]\n    alias = scalar\n    check(alias)', "check(alias"),
        (
            '    copied = dict(assembled.settings)\n    check(copied["QUICKSCALE_DEMO_BACKEND"])',
            "check(copied",
        ),
        ("    for key, value in payload.items():\n        check(value)", "check(value"),
        ("    [check(value) for value in payload.values()]", "check(value"),
    ],
)
def test_enclosing_factory_validator_alias_rejects_owned_reads(spelling, body, offending) -> None:
    source = _closure_adapter(
        body, spelling, "    check = validate_backend\n", "from vendor import validate_backend\n"
    )
    line = next(index for index, text in enumerate(source.splitlines(), 1) if offending in text)
    found = _violations(
        checker.rule_12_adapter_duplicate_logic, _with_files(_golden_module(), adapter=source)
    )
    assert any(row.startswith(f"rule 12: demo: adapter.py:{line} re-validates") for row in found)


@pytest.mark.parametrize("spelling", ["direct", "alias", "chain", "nested"])
@pytest.mark.parametrize(
    "body, offending",
    [
        ('    coerce(payload["enabled"])', "coerce(payload"),
        ('    scalar = payload["enabled"]\n    alias = scalar\n    coerce(alias)', "coerce(alias"),
        ("    for value in payload.values():\n        coerce(value)", "coerce(value"),
    ],
)
def test_enclosing_factory_coercion_alias_rejects_owned_reads(spelling, body, offending) -> None:
    source = _closure_adapter(body, spelling, "    coerce = bool\n")
    line = next(index for index, text in enumerate(source.splitlines(), 1) if offending in text)
    found = _violations(
        checker.rule_12_adapter_duplicate_logic, _with_files(_golden_module(), adapter=source)
    )
    assert any(
        row.startswith(f"rule 12: demo: adapter.py:{line} coerces an option container")
        for row in found
    )


def test_enclosing_assignment_after_the_nested_def_still_resolves() -> None:
    module = _with_files(
        _golden_module(),
        adapter=(
            "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
            "from vendor import validate_backend\n"
            "def factory():\n"
            "    def hook(assembled, payload):\n"
            '        check(payload["backend"])\n'
            "        return assembled\n"
            "    check = validate_backend\n"
            "    return hook\n"
            "def adapter(options):\n"
            '    return assemble("demo", options, post_hook=factory())\n'
        ),
    )
    found = _violations(checker.rule_12_adapter_duplicate_logic, module)
    assert any(row.startswith("rule 12: demo: adapter.py:5 re-validates") for row in found)


def test_outer_factory_alias_resolves_through_nested_factories() -> None:
    module = _with_files(
        _golden_module(),
        adapter=(
            "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
            "from vendor import validate_backend\n"
            "def outer():\n"
            "    check = validate_backend\n"
            "    def factory():\n"
            "        def hook(assembled, payload):\n"
            '            check(payload["backend"])\n'
            "            return assembled\n"
            "        return hook\n"
            "    return factory\n"
            "def adapter(options):\n"
            '    return assemble("demo", options, post_hook=outer()())\n'
        ),
    )
    found = _violations(checker.rule_12_adapter_duplicate_logic, module)
    assert any(row.startswith("rule 12: demo: adapter.py:7 re-validates") for row in found)


@pytest.mark.parametrize(
    "source",
    [
        # A hook-local binding shadows the enclosing factory alias it names.
        "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
        "from vendor import validate_backend\n"
        "def _collect(value):\n    return value\n"
        "def factory():\n    check = validate_backend\n"
        "    def hook(assembled, payload):\n        check = _collect\n"
        '        check(payload["backend"])\n        return assembled\n'
        "    return hook\n"
        "def adapter(options):\n"
        '    return assemble("demo", options, post_hook=factory())\n',
        # A parameter shadows the enclosing factory alias.
        "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
        "from vendor import validate_backend\n"
        "def factory():\n    check = validate_backend\n"
        "    def hook(assembled, payload, check):\n"
        '        check(payload["backend"])\n        return assembled\n'
        "    return hook\n"
        "def adapter(options):\n"
        '    return assemble("demo", options, post_hook=factory())\n',
    ],
)
def test_enclosing_alias_shadowing_never_borrows_the_outer_callable(source) -> None:
    found = _violations(
        checker.rule_12_adapter_duplicate_logic, _with_files(_golden_module(), adapter=source)
    )
    assert found == []


def test_enclosing_alias_to_a_normalization_rooted_query_stays_legal() -> None:
    module = _with_files(
        _golden_module(),
        adapter=(
            "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
            "from quickscale_core.runtime.manifest import resolve_manifest_module_options\n"
            "def _ready(values):\n"
            '    candidate = str(values.get("backend", "")).strip()\n'
            '    return bool(values.get("enabled", False)) and candidate == "local"\n'
            "def factory():\n"
            "    ready = _ready\n"
            "    def hook(assembled, payload):\n"
            "        if ready(payload):\n            return assembled\n"
            "        return assembled\n"
            "    return hook\n"
            "def public_ready(options):\n"
            '    return _ready(resolve_manifest_module_options("demo", options))\n'
            "def adapter(options):\n"
            '    return assemble("demo", options, post_hook=factory())\n'
        ),
    )
    assert _violations(checker.rule_12_adapter_duplicate_logic, module) == []


def test_enclosing_alias_cycles_terminate_without_inventing_a_target() -> None:
    module = _with_files(
        _golden_module(),
        adapter=(
            "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
            "def factory():\n"
            "    first = second\n"
            "    second = first\n"
            "    def hook(assembled, payload):\n"
            '        first(payload["backend"])\n'
            "        return assembled\n"
            "    return hook\n"
            "def adapter(options):\n"
            '    return assemble("demo", options, post_hook=factory())\n'
        ),
    )
    assert _violations(checker.rule_12_adapter_duplicate_logic, module) == []


def test_enclosing_alias_diagnostics_are_stable_across_repeated_runs() -> None:
    source = _closure_adapter(
        '    check(payload["backend"])',
        "alias",
        "    check = validate_backend\n",
        "from vendor import validate_backend\n",
    )
    module = _with_files(_golden_module(), adapter=source)
    first = _violations(checker.rule_12_adapter_duplicate_logic, module)
    second = _violations(checker.rule_12_adapter_duplicate_logic, module)
    assert first and first == second


@pytest.mark.parametrize(
    "source",
    [
        (
            "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
            "from vendor import validate_backend\n"
            "def factory_a():\n"
            "    check = validate_backend\n"
            "    def hook(spec, values):\n"
            '        check(values["backend"])\n'
            "        return spec\n"
            "    return hook\n"
            "def factory_b():\n"
            "    def hook(spec, values):\n"
            "        return spec\n"
            "    return hook\n"
            "def adapter(options):\n"
            '    return assemble("demo", options, post_hook=factory_a())\n'
        ),
        (
            "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
            "from vendor import validate_backend\n"
            "def factory_a():\n"
            "    def hook(spec, values):\n"
            "        return spec\n"
            "    return hook\n"
            "def factory_b():\n"
            "    check = validate_backend\n"
            "    def hook(spec, values):\n"
            '        check(values["backend"])\n'
            "        return spec\n"
            "    return hook\n"
            "def adapter(options):\n"
            '    return assemble("demo", options, post_hook=factory_b())\n'
        ),
    ],
)
def test_same_named_nested_hooks_keep_their_scope_identity(source) -> None:
    line = next(
        index
        for index, text in enumerate(source.splitlines(), 1)
        if 'check(values["backend"])' in text
    )
    found = _violations(
        checker.rule_12_adapter_duplicate_logic, _with_files(_golden_module(), adapter=source)
    )
    assert any(row.startswith(f"rule 12: demo: adapter.py:{line} re-validates") for row in found)


def test_enclosing_alias_resolves_inside_hook_nested_helpers() -> None:
    module = _with_files(
        _golden_module(),
        adapter=(
            "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
            "from vendor import validate_backend\n"
            "def factory():\n"
            "    check = validate_backend\n"
            "    def hook(assembled, payload):\n"
            "        def verify(value):\n"
            "            check(value)\n"
            '        verify(payload["backend"])\n'
            "        return assembled\n"
            "    return hook\n"
            "def adapter(options):\n"
            '    return assemble("demo", options, post_hook=factory())\n'
        ),
    )
    found = _violations(checker.rule_12_adapter_duplicate_logic, module)
    assert any(row.startswith("rule 12: demo: adapter.py:7 re-validates") for row in found)


@pytest.mark.parametrize(
    "source",
    [
        "first = second\nsecond = first\n",
        "def factory():\n    alias = factory()\n    return alias\nfirst = factory()\n",
        "def factory():\n    return other()\n"
        "def other():\n    return factory()\nfirst = factory()\n",
    ],
)
def test_callable_reference_cycles_terminate_without_inventing_a_target(source) -> None:
    flow = AdapterFlow(ast.parse(source))
    assert flow.reference(ast.Name(id="first"), {}) == ""


def test_equal_factory_local_spellings_do_not_form_a_false_cycle() -> None:
    source = (
        "def hook(spec, values):\n    return spec\n"
        "def factory():\n    alias = hook\n    return alias\n"
        "def outer():\n    alias = factory()\n    return alias\n"
        "first = outer()\n"
    )
    flow = AdapterFlow(ast.parse(source))
    for _ in range(2):
        resolved = flow.reference(ast.Name(id="first"), {})
        assert flow.functions[resolved].name == "hook"
        assert flow.scope_parents[id(flow.functions[resolved])] is None


@pytest.mark.parametrize(
    "query_body",
    [
        '    discarded = resolve_manifest_module_options("demo", {})\n'
        '    candidate = values["backend"].strip()\n    return candidate == "local"',
        '    return bool(values["enabled"])',
    ],
)
def test_incidental_normalizer_call_does_not_grant_query_allowance(query_body) -> None:
    module = _with_adapter(
        _golden_module(),
        "    _ready(resolved)\n    return spec\n\n"
        "def _ready(values) -> bool:\n" + query_body + "\n\n"
        "def public_ready(options):\n"
        '    discarded = resolve_manifest_module_options("demo", options)\n'
        "    return _ready(options)",
    )
    source = module.files["adapter.py"].replace(
        "from typing import Any",
        "from typing import Any\n"
        "from quickscale_core.runtime.manifest import resolve_manifest_module_options",
    )
    assert _violations(checker.rule_12_adapter_duplicate_logic, _with_files(module, adapter=source))


def test_normalization_query_result_is_tracked_even_without_annotations() -> None:
    module = _with_adapter(
        _golden_module(),
        '    values = resolve_manifest_module_options("demo", resolved)\n'
        "    return spec\n\n"
        "def public_values(options):\n"
        '    values = resolve_manifest_module_options("demo", options)\n'
        '    opts = values\n    return opts["backend"].lower()',
    )
    # Non-selection normalization consumers cannot silently re-normalize values.
    source = module.files["adapter.py"].replace(
        "from typing import Any",
        "from typing import Any\n"
        "from quickscale_core.runtime.manifest import resolve_manifest_module_options",
    )
    assert _violations(checker.rule_12_adapter_duplicate_logic, _with_files(module, adapter=source))


@pytest.mark.parametrize(
    "projection",
    [
        '    settings["QUICKSCALE_DEMO_ENABLED"] = _ready(resolved)',
        '    settings = {"QUICKSCALE_DEMO_ENABLED": _ready(resolved)}',
    ],
)
def test_readiness_cannot_reproject_a_declared_scalar_setting(projection) -> None:
    module = _with_adapter(
        _golden_module(),
        "    settings = dict(spec.settings)\n"
        f"{projection}\n"
        "    return spec\n\n\ndef _ready(payload: dict[str, Any]) -> bool:\n"
        '    return bool(payload["enabled"])',
    )
    assert _violations(checker.rule_12_adapter_duplicate_logic, module)


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
