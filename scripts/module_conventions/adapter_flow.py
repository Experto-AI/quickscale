"""
Bounded adapter call graph: boundary arguments, hooks, and query results.

Only simple lexical calls/aliases, enclosing factory scopes, and returned hook
factories are resolved. Names, annotations, and coincidental mapping keys never
establish option provenance. Readiness is a separate dataflow rooted at the
normalization-query API, not a boolean-function exemption. Only pure selection
results may cross back to wiring.
"""

from __future__ import annotations

import ast
from typing import Any

from scripts.module_conventions.core import _body_nodes, _bound_names, _scope_nodes

Function = ast.FunctionDef | ast.AsyncFunctionDef
CallableEnvironment = dict[int, dict[str, str]]
_BOUNDARIES = {"build_generic_manifest_spec", "_build_generic_manifest_spec"}
_NORMALIZERS = {"resolve_manifest_module_options"}


def _arguments(function: Function) -> list[str]:
    return [
        argument.arg
        for argument in [
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        ]
    ]


def _defaults(function: Function) -> dict[str, ast.expr]:
    """Return every declared parameter default, positional or keyword-only."""
    positional = [*function.args.posonlyargs, *function.args.args]
    defaults = dict(
        zip(
            [argument.arg for argument in positional[-len(function.args.defaults) :]],
            function.args.defaults,
        )
    )
    defaults.update(
        {
            argument.arg: value
            for argument, value in zip(function.args.kwonlyargs, function.args.kw_defaults)
            if value is not None
        }
    )
    return defaults


def _aliases(nodes: list[ast.AST]) -> dict[str, ast.expr]:
    aliases: dict[str, ast.expr] = {}
    for node in nodes:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    aliases[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name):
                aliases[node.target.id] = node.value
    return aliases


def _local_bindings(function: Function | ast.Module) -> set[str]:
    """Names *function* binds in its own scope: parameters, targets, nested defs."""
    names: set[str] = set()
    if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
        names.update(_arguments(function))
        for argument in (function.args.vararg, function.args.kwarg):
            if argument is not None:
                names.add(argument.arg)
    for node in _body_nodes(function.body):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                names |= _bound_names(target)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            names |= _bound_names(node.target)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            names |= _bound_names(node.target)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    names |= _bound_names(item.optional_vars)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.NamedExpr):
            names |= _bound_names(node.target)
    return names


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
        """
        Resolve the same bounded callable references at every call-graph seam.

        Each alias hop resumes in its binding frame, not the original caller.
        Every frame's parameters/imports/definitions are lookup barriers. The
        result is a semantic key: definition identity plus captured static actual
        references, or an imported/builtin identity. ``enclosing`` is retained
        for caller compatibility; authoritative frames come from ``scope``.
        Unknown bindings and AST alias/factory cycles invent no target.
        """
        environment = environment or {}
        if isinstance(node, ast.Name):
            if id(node) in seen:
                return ""
            seen = seen | {id(node)}
            current = scope
            while True:
                table = aliases if current == scope else self.tables.get(current, {})
                replacement = table.get(node.id)
                if replacement is None and current is None:
                    replacement = self.aliases.get(node.id)
                if replacement is not None:
                    return self.reference(
                        replacement, table, seen, scope=current, environment=environment
                    )
                if current is not None and node.id in environment.get(current, {}):
                    return environment[current][node.id]
                defined = self.definitions.get(current, {}).get(node.id)
                if defined is not None:
                    return self._closure(self.function_keys[id(defined)], environment)
                imported = self.imports.get(current, {}).get(node.id)
                if imported is not None:
                    return imported
                if node.id in self._scope_bindings(current):
                    return ""
                if current is None:
                    return node.id
                current = self.scope_parents.get(current)
        if isinstance(node, ast.Call):
            called = self.reference(node.func, aliases, seen, enclosing, scope, environment)
            factory = self.functions.get(called)
            if factory is not None and id(factory) not in seen:
                nodes = _scope_nodes(factory)
                returns = [n for n in nodes if isinstance(n, ast.Return)]
                if len(returns) == 1 and returns[0].value is not None:
                    captured = self._call_environment(
                        node, called, aliases, scope, environment, seen
                    )
                    return self.reference(
                        returns[0].value,
                        _aliases(nodes),
                        seen | {id(factory)},
                        self.enclosing_scopes(factory),
                        id(factory),
                        captured,
                    )
        return ""

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
        constants = {
            name for name, value in self.aliases.items() if isinstance(value, ast.Constant)
        }
        candidates: set[str] = set()
        # Return selection is proven from expressions, never annotations.
        for _ in range(len(self.functions) + 1):
            for name, function in list(self.functions.items()):
                nodes = _scope_nodes(function)
                returns = [node.value for node in nodes if isinstance(node, ast.Return)]
                if returns and all(
                    self._selection(value, constants, candidates, function) for value in returns
                ):
                    if self._pure(nodes):
                        candidates.add(name)
        self.query_roots = {
            name
            for name, function in list(self.functions.items())
            if name in candidates
            and any(
                isinstance(node, ast.Call)
                and self.reference(
                    node.func,
                    _aliases(_scope_nodes(function)),
                    enclosing=self.enclosing_scopes(function),
                    scope=id(function),
                )
                in self.normalizers
                for node in _scope_nodes(function)
            )
        }
        queries: set[str] = set()
        contexts: set[tuple[str, tuple[bool, ...]]] = {
            (name, tuple(False for _ in _arguments(self.functions[name])))
            for name in self.query_roots
        }
        seen: set[tuple[str, tuple[bool, ...]]] = set()
        while contexts - seen:
            for context in list(contexts - seen):
                seen.add(context)
                name, inputs = context
                function = self.functions[name]
                bindings = dict(zip(_arguments(function), inputs))
                aliases = _aliases(_scope_nodes(function))
                enclosing = self.enclosing_scopes(function)
                if self._query_body(
                    function.body, bindings, aliases, candidates, contexts, enclosing, id(function)
                ):
                    queries.add(name)
                if any(inputs) and name not in self.query_roots:
                    queries.add(name)
        return queries

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
        """Follow *outputs* of normalization; an unused API call grants nothing."""
        if isinstance(node, ast.Name):
            return bindings.get(node.id, False)
        if isinstance(node, ast.Call):
            called = self.reference(node.func, aliases, enclosing=enclosing, scope=scope)
            if called in self.normalizers:
                return True
            values = [
                self._query_value(arg, bindings, aliases, candidates, contexts, enclosing, scope)
                for arg in node.args
            ]
            if called in candidates:
                arguments = _arguments(self.functions[called])
                values += [False] * max(0, len(arguments) - len(values))
                for keyword in node.keywords:
                    if keyword.arg in arguments:
                        values[arguments.index(keyword.arg)] = self._query_value(
                            keyword.value, bindings, aliases, candidates, contexts, enclosing, scope
                        )
                if any(values):
                    contexts.add((called, tuple(values[: len(arguments)])))
            return any(values) or self._query_value(
                node.func, bindings, aliases, candidates, contexts, enclosing, scope
            )
        return any(
            [
                self._query_value(child, bindings, aliases, candidates, contexts, enclosing, scope)
                for child in ast.iter_child_nodes(node)
            ]
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
        returned = False
        for statement in body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                if statement.value is not None:
                    value = self._query_value(
                        statement.value, bindings, aliases, candidates, contexts, enclosing, scope
                    )
                    targets = (
                        statement.targets
                        if isinstance(statement, ast.Assign)
                        else [statement.target]
                    )
                    for target in targets:
                        if isinstance(target, ast.Name):
                            bindings[target.id] = value
            elif isinstance(statement, ast.If):
                self._query_value(
                    statement.test, bindings, aliases, candidates, contexts, enclosing, scope
                )
                left, right = dict(bindings), dict(bindings)
                returned |= self._query_body(
                    statement.body, left, aliases, candidates, contexts, enclosing, scope
                )
                returned |= self._query_body(
                    statement.orelse, right, aliases, candidates, contexts, enclosing, scope
                )
                bindings.update(
                    {
                        key: left.get(key, False) or right.get(key, False)
                        for key in left.keys() | right.keys()
                    }
                )
            elif isinstance(statement, ast.Return) and statement.value is not None:
                returned |= self._query_value(
                    statement.value, bindings, aliases, candidates, contexts, enclosing, scope
                )
            else:
                self._query_value(
                    statement, bindings, aliases, candidates, contexts, enclosing, scope
                )
        return returned

    @staticmethod
    def _pure(nodes: list[ast.AST]) -> bool:
        for node in nodes:
            if isinstance(node, (ast.Raise, ast.Assert, ast.AugAssign, ast.Delete)):
                return False
            if isinstance(node, ast.Attribute) and node.attr == "settings":
                return False
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"update", "pop", "popitem", "setdefault", "clear"}:
                    return False
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(not isinstance(target, ast.Name) for target in targets):
                    return False
            if isinstance(node, ast.Expr) and not isinstance(node.value, ast.Constant):
                return False
        return True

    def _selection(
        self, node: ast.AST | None, constants: set[str], queries: set[str], function: Function
    ) -> bool:
        if isinstance(node, ast.Constant):
            return isinstance(node.value, (bool, str)) or node.value is None
        if isinstance(node, ast.Name):
            return node.id in constants
        if isinstance(node, ast.Compare):
            return True
        if isinstance(node, ast.UnaryOp):
            return isinstance(node.op, ast.Not)
        if isinstance(node, ast.BoolOp):
            return all(
                self._selection(value, constants, queries, function) for value in node.values
            )
        if isinstance(node, ast.Call):
            called = self.reference(node.func, self.tables[id(function)], scope=id(function))
            return called == "bool" or self.definition_key(called) in queries
        return False

    def _seed(self) -> None:
        for name, function in list(self.functions.items()):
            nodes = _scope_nodes(function)
            aliases = _aliases(nodes)
            enclosing = self.enclosing_scopes(function)
            bindings: dict[str, str] = {}
            for node in nodes:
                if not isinstance(node, ast.Call):
                    continue
                called = self.reference(node.func, aliases, enclosing=enclosing, scope=id(function))
                if called in self.boundaries | self.normalizers:
                    argument = next((kw.value for kw in node.keywords if kw.arg == "options"), None)
                    if argument is None and len(node.args) > 1:
                        argument = node.args[1]
                    if argument is not None:
                        for parameter in self._sources(
                            argument, aliases, set(_arguments(function))
                        ):
                            bindings[parameter] = "options"
                if called in self.boundaries:
                    hook = next((kw.value for kw in node.keywords if kw.arg == "post_hook"), None)
                    hook_name = (
                        self.reference(hook, aliases, enclosing=enclosing, scope=id(function))
                        if hook is not None
                        else ""
                    )
                    if hook_name in self.functions:
                        self.add_context(hook_name, ["spec", "options"])
                        self._seed_defaults(hook_name, supplied=2)
            if bindings or name in self.queries:
                self.contexts.add(
                    (name, tuple(bindings.get(arg, "") for arg in _arguments(function)))
                )
            if function.name == "get_manifest_adapter" and self.scope_parents[id(function)] is None:
                for node in nodes:
                    if isinstance(node, ast.Return) and node.value is not None:
                        adapter = self.reference(
                            node.value, aliases, enclosing=enclosing, scope=id(function)
                        )
                        if adapter in self.functions:
                            self.add_context(adapter, ["options"])

    def _sources(
        self,
        node: ast.AST,
        aliases: dict[str, ast.expr],
        parameters: set[str],
        seen: frozenset[str] = frozenset(),
    ) -> set[str]:
        """Trace boundary inputs backwards through simple aliases/copies/expressions."""
        if isinstance(node, ast.Name):
            if node.id in parameters:
                return {node.id}
            if node.id in aliases and node.id not in seen:
                return self._sources(aliases[node.id], aliases, parameters, seen | {node.id})
            return set()
        return set().union(
            *(
                self._sources(child, aliases, parameters, seen)
                for child in ast.iter_child_nodes(node)
            )
        )

    def add_context(self, name: str, kinds: list[str]) -> tuple[str, tuple[str, ...]]:
        identity = self.definition_key(name)
        if identity in self.queries and identity not in self.query_roots:
            kinds = ["query_" + kind if kind in {"options", "scalar"} else kind for kind in kinds]
        size = len(_arguments(self.functions[name]))
        context = (name, tuple((kinds + [""] * size)[:size]))
        self.contexts.add(context)
        return context

    def _seed_defaults(self, name: str, supplied: int) -> None:
        """
        Bind a seeded callable's omitted parameter defaults (SA263).

        The implicit post-hook seeds supply the first *supplied* parameters
        with the boundary's spec/options kinds, so later parameters are
        omitted.  Their default expressions resolve in the callable's defining
        frame through its captured environment, exactly as
        ``_call_environment`` resolves an ordinary call's omitted defaults.
        """
        function = self.functions[name]
        captured = dict(self.environments.get(name, {}))
        bindings = dict(captured.get(id(function), {}))
        defaults = _defaults(function)
        parent = self.scope_parents.get(id(function))
        for argument in _arguments(function)[supplied:]:
            if argument in defaults and argument not in bindings:
                bindings[argument] = self.reference(
                    defaults[argument],
                    self.tables.get(parent, {}),
                    scope=parent,
                    environment=captured,
                )
        if bindings != captured.get(id(function), {}) and any(bindings.values()):
            captured[id(function)] = bindings
            self.environments[name] = captured

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
