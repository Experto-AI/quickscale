"""
Behavioral controls for the ``adapter_flow`` split (SA268).

The bounded adapter call graph keeps the ``AdapterFlow`` entry point in the
``adapter_flow`` facade and moves its mechanics into the private siblings
(``_adapter_lexical``, ``_adapter_reference``, ``_adapter_queries``,
``_adapter_seed``).  SA268 has closed, so SA279 retired the pre-split surface
pins; these controls keep the split's structural invariants and the exact
ordered rule-12 findings of representative corpora captured from the pre-split
module, so a later change cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scripts import check_module_conventions as checker
from scripts.module_conventions import (
    _adapter_lexical,
    _adapter_queries,
    _adapter_reference,
    _adapter_seed,
    adapter_flow,
)
from scripts.tests_module_conventions._support import _golden_module, _violations, _with_files

SPLIT_SIBLINGS = {
    "_adapter_lexical": _adapter_lexical,
    "_adapter_queries": _adapter_queries,
    "_adapter_reference": _adapter_reference,
    "_adapter_seed": _adapter_seed,
}


FORBIDDEN_SIBLING_TARGETS = frozenset(
    {"adapter_flow", "adapter_options", "registry", "check_module_conventions"}
)


def _adapter(body: str) -> str:
    """Wrap adapter lines in a wiring path whose signature exposes both containers."""
    return (
        '"""Demo adapter."""\n\n'
        "from typing import Any\n\n"
        "from quickscale_core.runtime import ModuleWiringSpec, build_generic_manifest_spec\n\n\n"
        "def _demo_post_hook(spec: ModuleWiringSpec, resolved: dict[str, Any])"
        " -> ModuleWiringSpec:\n"
        f"{body}\n\n\n"
        "def _demo_manifest_adapter(\n"
        "    options: dict[str, Any], *, project_package: str | None = None\n"
        ") -> ModuleWiringSpec:\n"
        "    del project_package\n"
        '    return build_generic_manifest_spec("demo", options, post_hook=_demo_post_hook)\n'
    )


def _with_adapter(module, body: str):
    return _with_files(module, adapter=_adapter(body))


def _query_source(body: str, query_body: str) -> str:
    """Return an adapter whose post-hook consumes a normalization-rooted query."""
    return (
        '"""Demo adapter."""\n\n'
        "from typing import Any\n\n"
        "from quickscale_core.runtime import ModuleWiringSpec, build_generic_manifest_spec\n"
        "from quickscale_core.runtime.manifest import resolve_manifest_module_options\n\n\n"
        "def _demo_post_hook(spec: ModuleWiringSpec, resolved: dict[str, Any])"
        " -> ModuleWiringSpec:\n"
        f"{body}\n    return spec\n\n\n"
        "def _ready(values):\n"
        f"{query_body}\n\n\n"
        "def public_ready(options):\n"
        '    return _ready(resolve_manifest_module_options("demo", options))\n\n\n'
        "def _demo_manifest_adapter(\n"
        "    options: dict[str, Any], *, project_package: str | None = None\n"
        ") -> ModuleWiringSpec:\n"
        "    del project_package\n"
        '    return build_generic_manifest_spec("demo", options, post_hook=_demo_post_hook)\n'
    )


def _query_adapter(body: str, query_body: str = '    return bool(values["enabled"])'):
    return _with_files(_golden_module(), adapter=_query_source(body, query_body))


BOUNDED_GET_BODY = '    opts = resolved\n    opts.get("backend", "local")\n    return spec'

FACTORY_SOURCE = (
    "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
    "def factory():\n    def hook(assembled, payload):\n"
    '        payload.get("backend", "local")\n'
    "        return assembled\n"
    "    return hook\n"
    "def adapter(options):\n    builder = assemble\n"
    "    creator = factory\n    chosen = creator()\n"
    '    return builder("demo", options, post_hook=chosen)\n'
)

CLOSURE_SOURCE = (
    "from quickscale_core.runtime import build_generic_manifest_spec as assemble\n"
    "from vendor import validate_backend\n"
    "def factory():\n"
    "    check = validate_backend\n"
    "    def hook(assembled, payload):\n"
    '        check(payload["backend"])\n'
    "        return assembled\n"
    "    chosen = hook\n"
    "    return chosen\n"
    "def adapter(options):\n"
    "    builder = assemble\n"
    "    creator = factory\n"
    "    chosen = creator()\n"
    '    return builder("demo", options, post_hook=chosen)\n'
)

CASE_BUILDERS = {
    "clean": lambda: _golden_module(),
    "bounded_get": lambda: _with_adapter(_golden_module(), BOUNDED_GET_BODY),
    "coercion": lambda: _with_adapter(
        _golden_module(), '    enabled = bool(resolved["enabled"])\n    return spec'
    ),
    "readiness_reprojection": lambda: _with_adapter(
        _golden_module(),
        "    settings = dict(spec.settings)\n"
        '    settings["QUICKSCALE_DEMO_ENABLED"] = _ready(resolved)\n'
        "    return spec\n\n\n"
        "def _ready(payload: dict[str, Any]) -> bool:\n"
        '    return bool(payload["enabled"])',
    ),
    "readiness_query_legal": lambda: _query_adapter(
        "    if _ready(resolved):\n        return spec"
    ),
    "readiness_query_projection": lambda: _query_adapter(
        '    _ready(resolved)\n    resolved["backend"].strip()'
    ),
    "factory_hook_diagnostic": lambda: _with_files(_golden_module(), adapter=FACTORY_SOURCE),
    "closure_validator_diagnostic": lambda: _with_files(_golden_module(), adapter=CLOSURE_SOURCE),
    "alias_cycle": lambda: _with_files(
        _golden_module(), adapter="first = second\nsecond = first\n"
    ),
}

#: (case, expected findings) captured from the pre-split module; each list is
#: exact, so order, wording, and duplicate findings are all pinned.
EXACT_FINDINGS = (
    ("clean", ()),
    (
        "bounded_get",
        ("rule 12: demo: adapter.py:10 calls get() on an option container",),
    ),
    (
        "coercion",
        ("rule 12: demo: adapter.py:9 coerces an option container read with bool()",),
    ),
    (
        "readiness_reprojection",
        ("rule 12: demo: adapter.py:15 coerces an option container read with bool()",),
    ),
    ("readiness_query_legal", ()),
    (
        "readiness_query_projection",
        ("rule 12: demo: adapter.py:11 calls strip() on an option container",),
    ),
    (
        "factory_hook_diagnostic",
        ("rule 12: demo: adapter.py:4 calls get() on an option container",),
    ),
    (
        "closure_validator_diagnostic",
        (
            "rule 12: demo: adapter.py:6 re-validates an option container read through "
            "validate_backend()",
        ),
    ),
    ("alias_cycle", ()),
)

TWO_MODULE_ORDER = (
    "rule 12: demo: adapter.py:10 calls get() on an option container",
    "rule 12: blog: adapter.py:10 calls get() on an option container",
)


def test_split_siblings_never_import_a_facade_or_entrypoint() -> None:
    """Helpers reach their collaborators through siblings, never the facades."""
    for name, module in SPLIT_SIBLINGS.items():
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[-1] not in FORBIDDEN_SIBLING_TARGETS, (
                    name,
                    node.lineno,
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[-1] not in FORBIDDEN_SIBLING_TARGETS, (
                        name,
                        node.lineno,
                    )


def test_reference_cycles_terminate_without_inventing_a_target() -> None:
    """The moved resolver keeps failing closed on alias cycles."""
    flow = adapter_flow.AdapterFlow(ast.parse("first = second\nsecond = first\n"))
    assert flow.reference(ast.Name(id="first"), {}) == ""


def test_reference_equal_spellings_resolve_to_the_definition_key() -> None:
    """Equal factory-local spellings keep their distinct definition identity."""
    source = (
        "def hook(spec, values):\n    return spec\n"
        "def factory():\n    alias = hook\n    return alias\n"
        "def outer():\n    alias = factory()\n    return alias\n"
        "first = outer()\n"
    )
    flow = adapter_flow.AdapterFlow(ast.parse(source))
    resolved = flow.reference(ast.Name(id="first"), {})
    assert resolved == "def:hook"
    assert flow.functions[resolved].name == "hook"
    assert flow.scope_parents[id(flow.functions[resolved])] is None


@pytest.mark.parametrize(
    ("case", "expected"),
    EXACT_FINDINGS,
    ids=[case for case, _ in EXACT_FINDINGS],
)
def test_detector_findings_are_exact_and_ordered(case: str, expected: tuple[str, ...]) -> None:
    assert _violations(checker.rule_12_adapter_duplicate_logic, CASE_BUILDERS[case]()) == list(
        expected
    )


def test_two_module_findings_keep_corpus_order() -> None:
    first = _with_adapter(_golden_module("demo"), BOUNDED_GET_BODY)
    second = _with_adapter(_golden_module("blog"), BOUNDED_GET_BODY)
    assert _violations(checker.rule_12_adapter_duplicate_logic, first, second) == list(
        TWO_MODULE_ORDER
    )
