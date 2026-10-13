"""
Parity controls for the ``adapter_flow`` split (SA268).

The bounded adapter call graph keeps the ``AdapterFlow`` entry point in the
``adapter_flow`` facade and moves its mechanics into the private siblings
(``_adapter_lexical``, ``_adapter_reference``, ``_adapter_queries``,
``_adapter_seed``).  These controls pin the facade's preserved surface, the
split's structural invariants, and the exact ordered rule-12 findings of
representative corpora captured from the pre-split module, so a later slice
cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from scripts import check_module_conventions as checker
from scripts.module_conventions import (
    _adapter_lexical,
    _adapter_queries,
    _adapter_reference,
    _adapter_seed,
    adapter_flow,
    adapter_options,
    core,
    registry,
    rules_settings,
)
from scripts.tests_module_conventions._support import _golden_module, _violations, _with_files

SPLIT_SIBLINGS = {
    "_adapter_lexical": _adapter_lexical,
    "_adapter_queries": _adapter_queries,
    "_adapter_reference": _adapter_reference,
    "_adapter_seed": _adapter_seed,
}

#: Every module-level name the pre-split ``adapter_flow`` published, from its
#: own ``def``/``class``/assignment statements.  The facade must keep exposing
#: all of them, private helpers and type aliases included.
FROZEN_SURFACE = (
    "Function",
    "CallableEnvironment",
    "_BOUNDARIES",
    "_NORMALIZERS",
    "_arguments",
    "_defaults",
    "_aliases",
    "_local_bindings",
    "AdapterFlow",
)

#: The pre-split module's own imports, which it exposed as module attributes;
#: the facade keeps every one importable through its redundant aliases.
FROZEN_IMPORTED_BINDINGS = (
    "annotations",
    "ast",
    "Any",
    "_body_nodes",
    "_bound_names",
    "_scope_nodes",
)

#: The pre-split module's wildcard-import surface: it declared no ``__all__``,
#: so ``from ... import *`` bound every public (non-underscore) module-level
#: name, the future-import binding included.
FROZEN_WILDCARD_SURFACE = (
    "AdapterFlow",
    "Any",
    "CallableEnvironment",
    "Function",
    "annotations",
    "ast",
)

FROZEN_CORE_HELPERS = ("_body_nodes", "_bound_names", "_scope_nodes")

#: Each moved name's private sibling home; the facade re-exports the very
#: object its home defines.
FROZEN_HOMES = {
    "_adapter_lexical": (
        "Function",
        "CallableEnvironment",
        "_arguments",
        "_defaults",
        "_aliases",
        "_local_bindings",
    ),
}

#: The mechanics the split moved behind the facade, keyed by sibling home.
FROZEN_MECHANICS = {
    "_adapter_reference": ("_reference",),
    "_adapter_queries": (
        "_query_functions",
        "_query_value",
        "_query_body",
        "_pure",
        "_selection",
    ),
    "_adapter_seed": ("_seed", "_sources", "_seed_defaults"),
}

#: Delegator methods the facade keeps on ``AdapterFlow``; each is defined in
#: the facade and forwards to its sibling, so its signature stays freezable.
FROZEN_DELEGATORS = (
    "reference",
    "_query_functions",
    "_query_value",
    "_query_body",
    "_pure",
    "_selection",
    "_seed",
    "_sources",
    "_seed_defaults",
)

FORBIDDEN_SIBLING_TARGETS = frozenset(
    {"adapter_flow", "adapter_options", "registry", "check_module_conventions"}
)

#: The pre-split signature of every callable the pre-split module published.
FROZEN_SIGNATURES = {
    "AdapterFlow": "(tree: 'ast.Module') -> 'None'",
    "AdapterFlow.__init__": "(self, tree: 'ast.Module') -> 'None'",
    "AdapterFlow._call_environment": (
        "(self, node: 'ast.Call', called: 'str', aliases: 'dict[str, ast.expr]', scope: 'int |"
        " None', environment: 'CallableEnvironment', seen: 'frozenset[int]' = frozenset()) ->"
        " 'CallableEnvironment'"
    ),
    "AdapterFlow._closure": "(self, name: 'str', environment: 'CallableEnvironment') -> 'str'",
    "AdapterFlow._definition": "(self, name: 'str', scope: 'int | None') -> 'Function | None'",
    "AdapterFlow._index_scopes": (
        "(self, body: 'list[ast.stmt]', enclosing: 'tuple[dict[str, ast.expr], ...]', scope:"
        " 'int | None') -> 'None'"
    ),
    "AdapterFlow._keyed_functions": "(self) -> 'dict[str, Function]'",
    "AdapterFlow._pure": "(nodes: 'list[ast.AST]') -> 'bool'",
    "AdapterFlow._query_body": (
        "(self, body: 'list[ast.stmt]', bindings: 'dict[str, bool]', aliases: 'dict[str,"
        " ast.expr]', candidates: 'set[str]', contexts: 'set[tuple[str, tuple[bool, ...]]]',"
        " enclosing: 'tuple[dict[str, ast.expr], ...]', scope: 'int | None') -> 'bool'"
    ),
    "AdapterFlow._query_functions": "(self) -> 'set[str]'",
    "AdapterFlow._query_value": (
        "(self, node: 'ast.AST', bindings: 'dict[str, bool]', aliases: 'dict[str, ast.expr]',"
        " candidates: 'set[str]', contexts: 'set[tuple[str, tuple[bool, ...]]]', enclosing:"
        " 'tuple[dict[str, ast.expr], ...]', scope: 'int | None') -> 'bool'"
    ),
    "AdapterFlow._scope_bindings": "(self, scope: 'int | None') -> 'set[str]'",
    "AdapterFlow._scoped_key": (
        "(self, name: 'str', node: 'Function', used: 'dict[str, Function]') -> 'str'"
    ),
    "AdapterFlow._seed": "(self) -> 'None'",
    "AdapterFlow._seed_defaults": "(self, name: 'str', supplied: 'int') -> 'None'",
    "AdapterFlow._selection": (
        "(self, node: 'ast.AST | None', constants: 'set[str]', queries: 'set[str]', function:"
        " 'Function') -> 'bool'"
    ),
    "AdapterFlow._sources": (
        "(self, node: 'ast.AST', aliases: 'dict[str, ast.expr]', parameters: 'set[str]', seen:"
        " 'frozenset[str]' = frozenset()) -> 'set[str]'"
    ),
    "AdapterFlow.add_context": (
        "(self, name: 'str', kinds: 'list[str]') -> 'tuple[str, tuple[str, ...]]'"
    ),
    "AdapterFlow.call": "(self, node: 'ast.Call', tracker: 'Any') -> 'str'",
    "AdapterFlow.callable_label": "(self, name: 'str') -> 'str'",
    "AdapterFlow.definition_key": "(self, name: 'str') -> 'str'",
    "AdapterFlow.enclosing_scopes": (
        "(self, function: 'Function') -> 'tuple[dict[str, ast.expr], ...]'"
    ),
    "AdapterFlow.reference": (
        "(self, node: 'ast.AST', aliases: 'dict[str, ast.expr]', seen: 'frozenset[int]' ="
        " frozenset(), enclosing: 'tuple[dict[str, ast.expr], ...]' = (), scope: 'int | None' ="
        " None, environment: 'CallableEnvironment | None' = None) -> 'str'"
    ),
    "AdapterFlow.run": (
        "(self, tracker_type: 'Any', options: 'set[str]', settings: 'set[str]', validators:"
        " 'set[str]') -> 'set[tuple[int, str]]'"
    ),
    "_aliases": "(nodes: 'list[ast.AST]') -> 'dict[str, ast.expr]'",
    "_arguments": "(function: 'Function') -> 'list[str]'",
    "_defaults": "(function: 'Function') -> 'dict[str, ast.expr]'",
    "_local_bindings": "(function: 'Function | ast.Module') -> 'set[str]'",
}


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


def _wildcard_surface(module) -> set[str]:
    """Return the names ``from <module> import *`` binds, without ``__all__``."""
    namespace: dict[str, object] = {}
    exec(f"from {module.__name__} import *", namespace)  # noqa: S102
    return set(namespace) - {"__builtins__"}


def test_facade_publishes_the_pre_split_surface() -> None:
    """Every name the pre-split module published stays reachable."""
    for name in FROZEN_SURFACE:
        assert getattr(adapter_flow, name) is not None
    assert adapter_flow._BOUNDARIES == {
        "build_generic_manifest_spec",
        "_build_generic_manifest_spec",
    }
    assert adapter_flow._NORMALIZERS == {"resolve_manifest_module_options"}


def test_facade_keeps_the_pre_split_wildcard_surface() -> None:
    """``from ... import *`` still binds exactly the pre-split public names."""
    assert _wildcard_surface(adapter_flow) == set(FROZEN_WILDCARD_SURFACE)


def test_facade_preserves_the_pre_split_imported_bindings() -> None:
    """The pre-split module's own imports stay importable through the facade."""
    assert adapter_flow.ast is ast
    for name in FROZEN_IMPORTED_BINDINGS:
        assert getattr(adapter_flow, name) is not None
    for name in FROZEN_CORE_HELPERS:
        assert getattr(adapter_flow, name) is getattr(core, name)


def test_frozen_callable_signatures_are_unchanged() -> None:
    """Each pre-split callable keeps its pre-split signature through the facade."""
    signatures = {
        name: str(inspect.signature(getattr(adapter_flow, name)))
        for name in ("_arguments", "_defaults", "_aliases", "_local_bindings")
    }
    signatures["AdapterFlow"] = str(inspect.signature(adapter_flow.AdapterFlow))
    for name, member in inspect.getmembers(adapter_flow.AdapterFlow):
        if inspect.isfunction(member):
            signatures[f"AdapterFlow.{name}"] = str(inspect.signature(member))
    assert signatures == FROZEN_SIGNATURES


def test_frozen_names_keep_their_sibling_homes() -> None:
    """The facade re-exports the very objects the moved names' homes define."""
    for sibling_name, names in FROZEN_HOMES.items():
        sibling = SPLIT_SIBLINGS[sibling_name]
        for name in names:
            assert getattr(adapter_flow, name) is getattr(sibling, name), name
    assert adapter_flow.AdapterFlow.__module__ == "scripts.module_conventions.adapter_flow"


def test_split_mechanics_live_in_their_siblings() -> None:
    """The mechanics moved out; the facade keeps the delegating surface."""
    for sibling_name, names in FROZEN_MECHANICS.items():
        sibling = SPLIT_SIBLINGS[sibling_name]
        assert getattr(adapter_flow, sibling_name) is sibling
        for name in names:
            function = getattr(sibling, name)
            assert function.__module__ == f"scripts.module_conventions.{sibling_name}", name
    for name in FROZEN_DELEGATORS:
        method = getattr(adapter_flow.AdapterFlow, name)
        assert method.__module__ == "scripts.module_conventions.adapter_flow", name


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


def test_registry_and_entrypoint_read_the_facade() -> None:
    """The registered rule and the rule-12 detector still resolve the facade."""
    detectors = {rule.number: rule.detector for rule in registry.RULES}
    assert detectors[12] is rules_settings.rule_12_manifest_and_adapter_options
    assert (
        checker.rule_12_adapter_duplicate_logic is adapter_options.rule_12_adapter_duplicate_logic
    )
    assert adapter_options.AdapterFlow is adapter_flow.AdapterFlow


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
