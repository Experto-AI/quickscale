"""
Bounded adapter call graph: boundary arguments, hooks, and query results.

Only simple lexical calls/aliases, enclosing factory scopes, and returned hook
factories are resolved. Names, annotations, and coincidental mapping keys never
establish option provenance. Readiness is a separate dataflow rooted at the
normalization-query API, not a boolean-function exemption. Only pure selection
results may cross back to wiring.

The mechanics live in the private siblings: ``_adapter_lexical`` holds the
pre-split type aliases and name scanners, ``_adapter_reference`` the bounded
callable-reference resolver, ``_adapter_queries`` the readiness-query
selection pass, and ``_adapter_seed`` the boundary/hook seeding pass.  This
module keeps the ``AdapterFlow`` entry point and re-exports every moved name so
existing import paths (``adapter_options``, the control cases) keep working.
"""

from __future__ import annotations

# The pre-split module also exposed its own imports as module attributes
# (``ast``, ``Any``, and core's private helpers); the redundant aliases keep
# every one importable from this facade.
import ast as ast
from typing import Any as Any

from scripts.module_conventions import (
    _adapter_queries,
    _adapter_reference,
    _adapter_seed,
)
from scripts.module_conventions._adapter_lexical import (
    CallableEnvironment,
    Function,
    _aliases,
    _arguments,
    _defaults,
    _local_bindings,
)
from scripts.module_conventions.core import _body_nodes as _body_nodes
from scripts.module_conventions.core import _bound_names as _bound_names
from scripts.module_conventions.core import _scope_nodes as _scope_nodes

_BOUNDARIES = {"build_generic_manifest_spec", "_build_generic_manifest_spec"}
_NORMALIZERS = {"resolve_manifest_module_options"}

# The rule 40 harness re-exports every name the pre-split module published,
# private helpers and type aliases included: existing import paths
# (``adapter_options``, the control cases) keep resolving through this facade.
# The facade declares no ``__all__``, exactly as the pre-split module did, so
# ``from ... import *`` keeps binding the same public surface.


class AdapterFlow:
    """Finite contexts preserve query/option/structural caller distinctions."""

    def __init__(self, tree: ast.Module) -> None:
        self.boundaries = set(_BOUNDARIES)
        self.normalizers = set(_NORMALIZERS)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "quickscale_core."
            ):
                for alias in node.names:
                    if alias.name in _BOUNDARIES:
                        self.boundaries.add(alias.asname or alias.name)
                    if alias.name in _NORMALIZERS:
                        self.normalizers.add(alias.asname or alias.name)
        self.aliases = _aliases(list(tree.body))
        self.module_bindings = _local_bindings(tree)
        self.imports: dict[int | None, dict[str, str]] = {}
        self.tables: dict[int | None, dict[str, ast.expr]] = {None: self.aliases}
        self.scope_chain: dict[int, tuple[dict[str, ast.expr], ...]] = {}
        self.enclosing_tables: dict[int, tuple[dict[str, ast.expr], ...]] = {}
        self.scope_parents: dict[int, int | None] = {}
        self.definitions: dict[int | None, dict[str, Function]] = {}
        self.scope_nodes: dict[int, Function] = {}
        self.binding_cache: dict[int, set[str]] = {}
        self._index_scopes(tree.body, (), None)
        self.function_keys: dict[int, str] = {}
        self.functions = self._keyed_functions()
        self.environments: dict[str, CallableEnvironment] = {}
        self.closures: dict[
            tuple[str, tuple[tuple[int, tuple[tuple[str, str], ...]], ...]], str
        ] = {}
        self.contexts: set[tuple[str, tuple[str, ...]]] = set()
        self.results: dict[tuple[str, tuple[str, ...]], str] = {}
        self.query_roots: set[str] = set()
        self.queries = self._query_functions()
        self._seed()

    def _index_scopes(
        self,
        body: list[ast.stmt],
        enclosing: tuple[dict[str, ast.expr], ...],
        scope: int | None,
    ) -> None:
        """Map every function to its lexical aliases and definition scope."""
        for statement in body:
            if isinstance(statement, (ast.Import, ast.ImportFrom)):
                for alias in statement.names:
                    local = alias.asname or alias.name.split(".")[0]
                    self.imports.setdefault(scope, {})[local] = (
                        alias.name
                        if isinstance(statement, ast.ImportFrom)
                        and (statement.module or "").startswith("quickscale_core.")
                        and alias.name in _BOUNDARIES | _NORMALIZERS
                        else "import:" + alias.name
                    )
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.scope_chain[id(statement)] = enclosing
                self.scope_parents[id(statement)] = scope
                self.scope_nodes[id(statement)] = statement
                self.definitions.setdefault(scope, {})[statement.name] = statement
                self.tables[id(statement)] = _aliases(_scope_nodes(statement))
                self._index_scopes(
                    statement.body, (_aliases(_scope_nodes(statement)), *enclosing), id(statement)
                )
                continue
            if isinstance(statement, ast.ClassDef):
                self._index_scopes(statement.body, enclosing, scope)
                continue
            for field in ("body", "orelse", "finalbody"):
                block = getattr(statement, field, None)
                if isinstance(block, list):
                    self._index_scopes(block, enclosing, scope)
            for handler in getattr(statement, "handlers", []):
                self._index_scopes(handler.body, enclosing, scope)
            for case in getattr(statement, "cases", []):
                self._index_scopes(case.body, enclosing, scope)

    def _keyed_functions(self) -> dict[str, Function]:
        """Definition identities cannot collide with builtin/import identities."""
        by_name: dict[str, list[Function]] = {}
        for function in self.scope_nodes.values():
            by_name.setdefault(function.name, []).append(function)
        functions: dict[str, Function] = {}
        for name, nodes in by_name.items():
            name = "def:" + name
            if len(nodes) == 1:
                functions[name] = nodes[0]
                self.function_keys[id(nodes[0])] = name
                continue
            for node in nodes:
                key = self._scoped_key(name, node, functions)
                functions[key] = node
                self.function_keys[id(node)] = key
        return functions

    def _scoped_key(self, name: str, node: Function, used: dict[str, Function]) -> str:
        path: list[str] = []
        scope = self.scope_parents.get(id(node))
        while scope is not None:
            parent = self.scope_nodes[scope]
            path.append(parent.name)
            scope = self.scope_parents.get(scope)
        base = f"{name}@{'.'.join(reversed(path))}" if path else f"{name}@module"
        key = base
        suffix = 2
        while key in used:
            key = f"{base}~{suffix}"
            suffix += 1
        return key

    def _scope_bindings(self, scope: int | None) -> set[str]:
        if scope is None:
            return self.module_bindings
        cached = self.binding_cache.get(scope)
        if cached is None:
            cached = _local_bindings(self.scope_nodes[scope])
            self.binding_cache[scope] = cached
        return cached

    def _definition(self, name: str, scope: int | None) -> Function | None:
        """Resolve a definition name lexically; a local binding stops the search."""
        current = scope
        while current is not None:
            if name in self._scope_bindings(current):
                return self.definitions.get(current, {}).get(name)
            found = self.definitions.get(current, {}).get(name)
            if found is not None:
                return found
            current = self.scope_parents.get(current)
        return self.definitions.get(None, {}).get(name)

    def enclosing_scopes(self, function: Function) -> tuple[dict[str, ast.expr], ...]:
        """Compatibility alias view; semantic resolution uses binding frames."""
        cached = self.enclosing_tables.get(id(function))
        if cached is None:
            bound = set(self._scope_bindings(id(function)))
            tables: list[dict[str, ast.expr]] = []
            scope = self.scope_parents.get(id(function))
            while True:
                tables.append(
                    {
                        name: value
                        for name, value in self.tables.get(scope, {}).items()
                        if name not in bound
                    }
                )
                bound.update(self._scope_bindings(scope))
                if scope is None:
                    break
                scope = self.scope_parents.get(scope)
            cached = tuple(tables)
            self.enclosing_tables[id(function)] = cached
        return cached

    def reference(
        self,
        node: ast.AST,
        aliases: dict[str, ast.expr],
        seen: frozenset[int] = frozenset(),
        enclosing: tuple[dict[str, ast.expr], ...] = (),
        scope: int | None = None,
        environment: CallableEnvironment | None = None,
    ) -> str:
        """Resolve a bound callable reference through its binding frames."""
        return _adapter_reference._reference(
            self, node, aliases, seen, enclosing, scope, environment
        )

    def _closure(self, name: str, environment: CallableEnvironment) -> str:
        """Intern lexical callable instances without merging distinct actuals."""
        function = self.functions[name]
        base = self.function_keys[id(function)]
        captured: CallableEnvironment = {}
        scope: int | None = id(function)
        while scope is not None:
            if environment.get(scope):
                captured[scope] = environment[scope]
            scope = self.scope_parents.get(scope)
        if not captured:
            return base
        signature = (
            base,
            tuple(sorted((key, tuple(sorted(value.items()))) for key, value in captured.items())),
        )
        if signature not in self.closures:
            key = f"{base}~closure{len(self.closures)}"
            self.closures[signature] = key
            self.functions[key] = function
            self.environments[key] = captured
        return self.closures[signature]

    def _call_environment(
        self,
        node: ast.Call,
        called: str,
        aliases: dict[str, ast.expr],
        scope: int | None,
        environment: CallableEnvironment,
        seen: frozenset[int] = frozenset(),
    ) -> CallableEnvironment:
        function = self.functions[called]
        captured = dict(self.environments.get(called, {}))
        positional = [*function.args.posonlyargs, *function.args.args]
        actuals = {arg.arg: value for arg, value in zip(positional, node.args)}
        actuals.update({kw.arg: kw.value for kw in node.keywords if kw.arg is not None})
        defaults = _defaults(function)
        bindings: dict[str, str] = {}
        for name in _arguments(function):
            if name in actuals:
                bindings[name] = self.reference(
                    actuals[name], aliases, seen, scope=scope, environment=environment
                )
            elif name in defaults:
                parent = self.scope_parents.get(id(function))
                bindings[name] = self.reference(
                    defaults[name],
                    self.tables.get(parent, {}),
                    seen,
                    scope=parent,
                    environment=captured,
                )
            else:
                bindings[name] = ""
        if any(bindings.values()) or id(function) in captured:
            captured[id(function)] = bindings
        return captured

    def definition_key(self, name: str) -> str:
        function = self.functions.get(name)
        return self.function_keys[id(function)] if function is not None else name

    def callable_label(self, name: str) -> str:
        function = self.functions.get(name)
        return function.name if function is not None else name.removeprefix("import:")

    def _query_functions(self) -> set[str]:
        """Select the readiness queries and publish the flow's query roots."""
        return _adapter_queries._query_functions(self)

    def _query_value(
        self,
        node: ast.AST,
        bindings: dict[str, bool],
        aliases: dict[str, ast.expr],
        candidates: set[str],
        contexts: set[tuple[str, tuple[bool, ...]]],
        enclosing: tuple[dict[str, ast.expr], ...],
        scope: int | None,
    ) -> bool:
        """Follow normalization outputs; see ``_adapter_queries``."""
        return _adapter_queries._query_value(
            self, node, bindings, aliases, candidates, contexts, enclosing, scope
        )

    def _query_body(
        self,
        body: list[ast.stmt],
        bindings: dict[str, bool],
        aliases: dict[str, ast.expr],
        candidates: set[str],
        contexts: set[tuple[str, tuple[bool, ...]]],
        enclosing: tuple[dict[str, ast.expr], ...],
        scope: int | None,
    ) -> bool:
        """Walk one statement body, joining branch bindings union-style."""
        return _adapter_queries._query_body(
            self, body, bindings, aliases, candidates, contexts, enclosing, scope
        )

    @staticmethod
    def _pure(nodes: list[ast.AST]) -> bool:
        return _adapter_queries._pure(nodes)

    def _selection(
        self, node: ast.AST | None, constants: set[str], queries: set[str], function: Function
    ) -> bool:
        """Return whether one expression is a proven selection."""
        return _adapter_queries._selection(self, node, constants, queries, function)

    def _seed(self) -> None:
        """Seed every callable in the flow from its boundary call sites."""
        _adapter_seed._seed(self)

    def _sources(
        self,
        node: ast.AST,
        aliases: dict[str, ast.expr],
        parameters: set[str],
        seen: frozenset[str] = frozenset(),
    ) -> set[str]:
        """Trace boundary inputs backwards through simple aliases and copies."""
        return _adapter_seed._sources(node, aliases, parameters, seen)

    def add_context(self, name: str, kinds: list[str]) -> tuple[str, tuple[str, ...]]:
        identity = self.definition_key(name)
        if identity in self.queries and identity not in self.query_roots:
            kinds = ["query_" + kind if kind in {"options", "scalar"} else kind for kind in kinds]
        size = len(_arguments(self.functions[name]))
        context = (name, tuple((kinds + [""] * size)[:size]))
        self.contexts.add(context)
        return context

    def _seed_defaults(self, name: str, supplied: int) -> None:
        """Bind a seeded callable's omitted parameter defaults (SA263)."""
        _adapter_seed._seed_defaults(self, name, supplied)

    def call(self, node: ast.Call, tracker: Any) -> str:
        called = self.reference(
            node.func,
            tracker.references,
            enclosing=tracker.enclosing,
            scope=tracker.scope,
            environment=tracker.environment,
        )
        if called in self.boundaries:
            hook = next((kw.value for kw in node.keywords if kw.arg == "post_hook"), None)
            if hook is not None:
                hook_name = self.reference(
                    hook, tracker.references, scope=tracker.scope, environment=tracker.environment
                )
                if hook_name in self.functions:
                    self.add_context(hook_name, ["spec", "options"])
                    self._seed_defaults(hook_name, supplied=2)
            return "spec"
        if called in self.normalizers:
            return "query_options" if tracker.query_context else "options"
        if called not in self.functions:
            return ""
        captured = self._call_environment(
            node, called, tracker.references, tracker.scope, tracker.environment
        )
        called = self._closure(called, captured)
        arguments = _arguments(self.functions[called])
        kinds = [tracker.kind(arg) for arg in node.args]
        kinds += [""] * max(0, len(arguments) - len(kinds))
        for keyword in node.keywords:
            if keyword.arg in arguments:
                kinds[arguments.index(keyword.arg)] = tracker.kind(keyword.value)
        if self.definition_key(called) not in self.queries:
            kinds = [kind.removeprefix("query_") for kind in kinds]
        context = self.add_context(called, kinds)
        if self.definition_key(called) in self.queries:
            return "query"
        return self.results.get(context, "")

    def run(
        self, tracker_type: Any, options: set[str], settings: set[str], validators: set[str]
    ) -> set[tuple[int, str]]:
        found: set[tuple[int, str]] = set()
        # Contexts and result kinds form a finite domain; iterate to a fixed point.
        while True:
            previous = (set(self.contexts), dict(self.results))
            for context in list(self.contexts):
                name, kinds = context
                function = self.functions[name]
                tracker = tracker_type(options, settings, validators, self)
                tracker.query_context = self.definition_key(name) in self.queries
                tracker.enclosing = self.enclosing_scopes(function)
                tracker.scope = id(function)
                tracker.environment = self.environments.get(name, {})
                tracker.bindings.update(zip(_arguments(function), kinds))
                tracker.walk(function.body)
                found.update(tracker.found)
                if tracker.return_kind:
                    self.results[context] = tracker.return_kind
            if previous == (self.contexts, self.results):
                return found
