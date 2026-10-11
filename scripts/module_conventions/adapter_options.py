"""
Rule 12: bounded static provenance of manifest-owned adapter values.

Track simple container/scalar aliases, loop bindings, and lexical enclosing
factory scopes, never parameter spellings. Copies and behavioral branches are
legal; scalar rewriting and option rejection are not. Boolean readiness queries
are runtime selection, not option projection.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping

from scripts.module_conventions.adapter_flow import AdapterFlow, CallableEnvironment
from scripts.module_conventions.core import Module, _bound_names, _parse

_REWRITES = {"strip", "lstrip", "rstrip", "lower", "upper", "casefold"}
_COERCIONS = {"bool", "int", "float", "str"}
_VALIDATOR = re.compile(r"^_?(?:is_valid|validate)_[a-z0-9_]+$")


def _owned_keys(module: Module) -> tuple[set[str], set[str]]:
    options: set[str] = set()
    settings: set[str] = set()
    config = module.manifest.get("config", {})
    if isinstance(config, Mapping):
        for block in config.values():
            if not isinstance(block, Mapping):
                continue
            for key, option in block.items():
                options.add(key)
                if isinstance(option, Mapping) and isinstance(option.get("django_setting"), str):
                    setting = option["django_setting"]
                    settings.add(setting)
                    if setting.endswith("_ENV_VAR"):
                        settings.add(setting[:-8])
    derivation = module.manifest.get("derivation", {})
    if isinstance(derivation, Mapping):
        bodies = [derivation]
        per_option = derivation.get("option_derivations", {})
        if isinstance(per_option, Mapping):
            bodies.extend(body for body in per_option.values() if isinstance(body, Mapping))
        for body in bodies:
            for entry in body.get("derived_settings", []):
                if isinstance(entry, Mapping) and isinstance(entry.get("setting_key"), str):
                    settings.add(entry["setting_key"])
    return options, settings


class _Provenance:
    """One function's conservative, bounded simple-static value analysis."""

    def __init__(
        self, options: set[str], settings: set[str], validators: set[str], flow: AdapterFlow
    ) -> None:
        self.options = options
        self.settings = settings
        self.validators = validators
        self.flow = flow
        self.bindings: dict[str, str] = {}
        self.literals: dict[str, set[str]] = {}
        self.references: dict[str, ast.expr] = {}
        self.enclosing: tuple[dict[str, ast.expr], ...] = ()
        self.scope: int | None = None
        self.environment: CallableEnvironment = {}
        self.return_kind = ""
        self.query_context = False
        self.found: set[tuple[int, str]] = set()

    def keys(self, node: ast.AST) -> set[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return {node.value}
        if isinstance(node, ast.Name):
            return self.literals.get(node.id, set())
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return set().union(*(self.keys(item) for item in node.elts))
        return set()

    def kind(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return self.bindings.get(node.id, "")
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "settings"
            and self.kind(node.value) == "spec"
        ):
            return "settings"
        if isinstance(node, ast.Subscript):
            receiver = self.kind(node.value)
            keys = self.keys(node.slice)
            owned = self.settings if receiver == "settings" else self.options
            if receiver in {"options", "settings", "query_options"} and (keys & owned or not keys):
                return "query_scalar" if receiver == "query_options" else "scalar"
        if isinstance(node, ast.Call):
            return self.call_kind(node)
        if isinstance(node, (ast.BoolOp, ast.IfExp, ast.Compare)):
            kinds = {self.kind(child) for child in ast.iter_child_nodes(node)}
            if "query" in kinds or "query_scalar" in kinds:
                return "query"
            if "scalar" in kinds:
                return "scalar"
        return ""

    def call_kind(self, node: ast.Call) -> str:
        local = self.flow.call(node, self)
        if local:
            return local
        called = self.flow.reference(
            node.func,
            self.references,
            enclosing=self.enclosing,
            scope=self.scope,
            environment=self.environment,
        )
        if called == "dict" and node.args:
            return self.kind(node.args[0])
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get" and node.args:
            return self.kind(ast.Subscript(value=node.func.value, slice=node.args[0]))
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"values", "items"}:
            if self.kind(node.func.value) in {"options", "settings"}:
                return "scalar"
            if self.kind(node.func.value) == "query_options":
                return "query_scalar"
        if isinstance(node.func, ast.Attribute) and node.func.attr in _REWRITES:
            return self.kind(node.func.value)
        if called in _COERCIONS and node.args:
            return self.kind(node.args[0])
        return ""

    def contains(self, node: ast.AST) -> bool:
        return any(
            self.kind(child) in {"scalar", "query", "query_scalar"} for child in ast.walk(node)
        )

    def owns(self, node: ast.AST) -> bool:
        return any(self.kind(child) == "scalar" for child in ast.walk(node))

    def inspect(self, node: ast.AST, *, guard: bool = False) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            self.inspect_comprehension(node, guard=guard)
            return
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if key is not None and self.keys(key) & self.settings:
                    if self.kind(value) in {"query", "query_scalar"}:
                        self.found.add(
                            (value.lineno, "re-projects an option through a readiness query")
                        )
        if isinstance(node, ast.Call):
            self.flow.call(node, self)
            self.inspect_call(node, guard=guard)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or) and not guard:
            if any(self.kind(value) == "scalar" for value in node.values):
                self.found.add((node.lineno, "provides an option-container fallback with or"))
        for child in ast.iter_child_nodes(node):
            self.inspect(child, guard=guard)

    def inspect_comprehension(
        self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp, *, guard: bool
    ) -> None:
        bindings, literals = dict(self.bindings), dict(self.literals)
        for generator in node.generators:
            self.inspect(generator.iter)
            self.bind_loop(generator.target, generator.iter)
            for condition in generator.ifs:
                self.inspect(condition, guard=True)
        expressions = [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
        for expression in expressions:
            self.inspect(expression, guard=guard)
        self.bindings, self.literals = bindings, literals

    def inspect_call(self, node: ast.Call, *, guard: bool) -> None:
        func = node.func
        called = self.flow.reference(
            func,
            self.references,
            enclosing=self.enclosing,
            scope=self.scope,
            environment=self.environment,
        )
        arguments = [*node.args, *(keyword.value for keyword in node.keywords)]
        if any(self.owns(arg) for arg in arguments):
            if called in _COERCIONS:
                self.found.add((node.lineno, f"coerces an option container read with {called}()"))
            elif self.flow.definition_key(called) in self.validators:
                self.found.add(
                    (
                        node.lineno,
                        "re-validates an option container read through "
                        f"{self.flow.callable_label(called)}()",
                    )
                )
        if isinstance(func, ast.Attribute):
            self.inspect_method(node, func, guard=guard)

    def inspect_method(self, node: ast.Call, func: ast.Attribute, *, guard: bool) -> None:
        if func.attr in _REWRITES and self.kind(func.value) == "scalar":
            self.found.add((node.lineno, f"calls {func.attr}() on an option container"))
        if (
            func.attr == "get"
            and self.kind(node) == "scalar"
            and (len(node.args) > 1 or node.keywords)
        ):
            self.found.add((node.lineno, "calls get() on an option container"))

    def bind(self, target: ast.AST, value: ast.expr) -> None:
        if isinstance(target, ast.Name):
            self.bindings[target.id] = self.kind(value)
            self.literals[target.id] = self.keys(value)
            self.references[target.id] = value
        elif isinstance(target, ast.Subscript) and self.kind(value) in {"query", "query_scalar"}:
            receiver = self.kind(target.value)
            owned = self.settings if receiver == "settings" else self.options
            if receiver in {"settings", "options"} and self.keys(target.slice) & owned:
                self.found.add((target.lineno, "re-projects an option through a readiness query"))
        elif isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List)):
            for left, right in zip(target.elts, value.elts):
                self.bind(left, right)

    def loop_kind(self, node: ast.AST) -> str:
        if self.owns(node):
            return "scalar"
        if self.contains(node):
            return "query_scalar"
        return ""

    def bind_loop(self, target: ast.expr, iterable: ast.expr) -> None:
        if isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Attribute):
            container = self.kind(iterable.func.value)
            if container in {"options", "settings", "query_options"}:
                owned = self.settings if container == "settings" else self.options
                if iterable.func.attr == "items" and isinstance(target, (ast.Tuple, ast.List)):
                    if len(target.elts) == 2:
                        for name in _bound_names(target.elts[0]):
                            self.bindings[name] = ""
                            self.literals[name] = owned
                        self.bind_loop(target.elts[1], iterable)
                        return
                if iterable.func.attr == "keys":
                    for name in _bound_names(target):
                        self.bindings[name] = ""
                        self.literals[name] = owned
                    return
        for name in _bound_names(target):
            self.bindings[name] = self.loop_kind(iterable)
            self.literals[name] = self.keys(iterable)

    def walk_branches(self, body: list[ast.stmt], orelse: list[ast.stmt]) -> None:
        bindings, literals, references = (
            dict(self.bindings),
            dict(self.literals),
            dict(self.references),
        )
        self.walk(body)
        left, left_literals = dict(self.bindings), dict(self.literals)
        self.bindings, self.literals, self.references = bindings, literals, references
        self.walk(orelse)
        for name in left.keys() | self.bindings.keys():
            kinds = {left.get(name, ""), self.bindings.get(name, "")}
            self.bindings[name] = next(
                (
                    kind
                    for kind in (
                        "options",
                        "settings",
                        "spec",
                        "scalar",
                        "query_options",
                        "query_scalar",
                        "query",
                    )
                    if kind in kinds
                ),
                "",
            )
            self.literals[name] = left_literals.get(name, set()) | self.literals.get(name, set())

    def walk(self, body: list[ast.stmt]) -> None:
        for statement in body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(statement, ast.If):
                rejecting = any(
                    isinstance(child, (ast.Raise, ast.Assert)) for child in ast.walk(statement)
                )
                self.inspect(statement.test, guard=not rejecting)
                if rejecting and any(
                    self.kind(child) in {"scalar", "options", "settings"}
                    for child in ast.walk(statement.test)
                ):
                    label = (
                        "re-checks an option value with not"
                        if isinstance(statement.test, ast.UnaryOp)
                        else "rejects a manifest-owned option value"
                    )
                    self.found.add((statement.lineno, label))
                self.walk_branches(statement.body, statement.orelse)
            elif isinstance(statement, (ast.For, ast.AsyncFor)):
                self.inspect(statement.iter)
                self.bind_loop(statement.target, statement.iter)
                self.walk(statement.body)
                self.walk(statement.orelse)
            else:
                self.inspect(statement)
                if isinstance(statement, ast.Assign):
                    for target in statement.targets:
                        self.bind(target, statement.value)
                elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
                    self.bind(statement.target, statement.value)
                elif isinstance(statement, ast.Assert) and self.owns(statement.test):
                    self.found.add((statement.lineno, "rejects a manifest-owned option value"))
                elif isinstance(statement, ast.Return) and statement.value is not None:
                    kind = self.kind(statement.value)
                    if kind:
                        self.return_kind = kind


def rule_12_adapter_duplicate_logic(corpus) -> list[str]:  # type: ignore[no-untyped-def]
    """Reject duplicate scalar policy with module/file/line diagnostics."""
    violations: list[str] = []
    for module in corpus.modules:
        text = module.files.get("adapter.py")
        if text is None:
            continue
        tree = _parse(text)
        flow = AdapterFlow(tree)
        validators = {
            flow.function_keys[id(node)]
            for node in flow.scope_nodes.values()
            if _VALIDATOR.match(node.name)
        }
        validators.update(_imported_validators(tree))
        options, settings = _owned_keys(module)
        for line, message in sorted(flow.run(_Provenance, options, settings, validators)):
            violations.append(f"rule 12: {module.name}: adapter.py:{line} {message}")
    return violations


def _imported_validators(tree: ast.Module) -> set[str]:
    return {
        "import:" + alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if _VALIDATOR.match(alias.name)
    }


__all__ = ["rule_12_adapter_duplicate_logic"]
