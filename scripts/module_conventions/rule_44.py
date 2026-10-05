"""Rule 44's lexical role-check scanner and its private helpers."""

from __future__ import annotations

import ast
from collections.abc import Mapping

from scripts.module_conventions.core import (
    Corpus,
    _attribute_chain,
    _bound_names,
    _call_func_name,
    _keyword,
    _literal,
    _parse,
)

# Rule 44's forbidden spelling: an ``OrganizationMembership`` query outside
# orgs whose ``role`` keyword is a string re-implements the one role check.
# The ``OrgRole`` vocabulary is the only role spelling; the binding follows
# the model imported from orgs or fetched by name through ``apps.get_model``.
# The query spelling stays open-world on the rest (``Q``, ``**kwargs``), so
# that part is a review rule.
RULE_44_MEMBERSHIP_MODEL = "OrganizationMembership"

RULE_44_MEMBERSHIP_APP = "quickscale_orgs"

RULE_44_MEMBERSHIP_SOURCE = "quickscale_modules_orgs.models"

RULE_44_QUERY_METHODS = frozenset(
    {
        "filter",
        "get",
        "exclude",
        "create",
        "update",
        "get_or_create",
        "update_or_create",
        # Django's asynchronous query equivalents that take field arguments.
        "aget",
        "acreate",
        "aupdate",
        "aget_or_create",
        "aupdate_or_create",
    }
)


#: The orgs source a qualified membership path roots in, and the two module
#: paths an alias may name: the package and its models module.
_RULE_44_SOURCE_PARTS = tuple(RULE_44_MEMBERSHIP_SOURCE.split("."))

_RULE_44_ALIAS_PATHS: frozenset[tuple[str, ...]] = frozenset(
    {(_RULE_44_SOURCE_PARTS[0],), _RULE_44_SOURCE_PARTS}
)


class _Rule44Environment:
    """
    Flow state for rule 44's scanner, one object per scope.

    ``names`` are the names bound to the membership model (or a queryset of
    it); ``aliases`` are the names bound to the orgs package or its models
    module, resolved when an attribute chain is read.  Assignments and
    targets rebind both sides together, so shadowing behaves as Python's
    name resolution does.
    """

    __slots__ = ("aliases", "names")

    def __init__(
        self,
        names: set[str] | None = None,
        aliases: dict[str, frozenset[tuple[str, ...]]] | None = None,
    ) -> None:
        self.names = set() if names is None else names
        self.aliases = {} if aliases is None else aliases

    def copy(self) -> _Rule44Environment:
        return _Rule44Environment(set(self.names), dict(self.aliases))

    def replace(self, other: _Rule44Environment) -> None:
        self.names = set(other.names)
        self.aliases = dict(other.aliases)

    def discard(self, name: str) -> None:
        """Drop a name's membership provenance and module alias."""
        self.names.discard(name)
        self.aliases.pop(name, None)

    def discard_all(self, names: set[str]) -> None:
        self.names.difference_update(names)
        for name in names:
            self.aliases.pop(name, None)

    def bind(
        self,
        name: str,
        *,
        membership: bool,
        aliases: frozenset[tuple[str, ...]] | None = None,
    ) -> None:
        """Record one binding of *name*: membership provenance, aliases, or neither."""
        if membership:
            self.names.add(name)
        else:
            self.names.discard(name)
        if aliases is None:
            self.aliases.pop(name, None)
        else:
            self.aliases[name] = aliases

    def merge(self, other: _Rule44Environment) -> None:
        """Union another path's state in, keeping whatever any path keeps."""
        self.names |= other.names
        for name, paths in other.aliases.items():
            self.aliases[name] = self.aliases.get(name, frozenset()) | paths


#: One enclosing function scope for ``nonlocal`` resolution: its flow state
#: and every name it binds, so the nearest binding wins over any provenance.
_Rule44Scope = tuple["_Rule44Environment", frozenset[str]]


#: Deferred function bodies: the body, the scope that owns it, and the
#: enclosing scopes it resolves ``nonlocal`` against.
_Rule44DeferredBodies = list[
    tuple[
        ast.FunctionDef | ast.AsyncFunctionDef,
        "_Rule44Environment",
        tuple[_Rule44Scope, ...],
    ]
]


def _rule_44_names_membership_model(call: ast.Call) -> bool:
    """
    Return whether a ``get_model`` call resolves orgs' membership model.

    Django's registry resolves the model name case-insensitively, so both
    sides fold; the app label still compares exactly.
    """
    model_name = RULE_44_MEMBERSHIP_MODEL.casefold()
    values = [
        _literal(argument)
        for argument in [*call.args, *(keyword.value for keyword in call.keywords)]
    ]
    strings = [value for value in values if isinstance(value, str)]
    for value in strings:
        app_label, separator, dotted_model = value.rpartition(".")
        if separator:
            if app_label == RULE_44_MEMBERSHIP_APP and dotted_model.casefold() == model_name:
                return True
        elif value.casefold() == model_name and RULE_44_MEMBERSHIP_APP in strings:
            return True
    return False


def _rule_44_qualified_membership(
    chain: tuple[str, ...], aliases: Mapping[str, frozenset[tuple[str, ...]]]
) -> bool:
    """
    Return whether an attribute chain is a qualified orgs membership path.

    The chain root must be bound to the orgs package or its models module, so
    a shadowing parameter, assignment, or import cannot resurrect the path;
    every alias path a join retained is tried.
    """
    paths = aliases.get(chain[0])
    if not paths:
        return False
    prefix = (*_RULE_44_SOURCE_PARTS, RULE_44_MEMBERSHIP_MODEL)
    return any((*path, *chain[1:])[: len(prefix)] == prefix for path in paths)


def _rule_44_membership_receiver(node: ast.expr, environment: _Rule44Environment) -> bool:
    """
    Return whether a queryset receiver resolves to the membership model.

    A name is decided by the binding environment; the structural fallback
    resolves only a fully qualified orgs path and its module aliases, so a
    same-named import from another app or a same-named parameter is not
    mistaken for the model.
    """
    chain = _attribute_chain(node)
    if chain is not None:
        if chain[0] in environment.names:
            return True
        return _rule_44_qualified_membership(chain, environment.aliases)
    if isinstance(node, ast.Call):
        if _call_func_name(node) == "get_model" and _rule_44_names_membership_model(node):
            return True
        return _rule_44_membership_receiver(node.func, environment)
    if isinstance(node, ast.Attribute):
        return _rule_44_membership_receiver(node.value, environment)
    if isinstance(node, ast.Subscript):
        return _rule_44_membership_receiver(node.value, environment)
    return False


def _rule_44_argument_names(arguments: ast.arguments) -> set[str]:
    """Return the names one signature's arguments bind."""
    names = {
        argument.arg
        for argument in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    }
    for variable in (arguments.vararg, arguments.kwarg):
        if variable is not None:
            names.add(variable.arg)
    return names


def _rule_44_pattern_names(pattern: ast.pattern) -> set[str]:
    """Return the names one structural pattern binds."""
    names: set[str] = set()
    for node in ast.walk(pattern):
        if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
    return names


def _rule_44_scope_declarations(body: list[ast.stmt]) -> tuple[set[str], set[str]]:
    """Return the global and nonlocal names one scope declares."""
    globals_: set[str] = set()
    nonlocals: set[str] = set()
    stack: list[ast.AST] = list(body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.Global):
            globals_.update(node.names)
        elif isinstance(node, ast.Nonlocal):
            nonlocals.update(node.names)
        stack.extend(ast.iter_child_nodes(node))
    return globals_, nonlocals


def _rule_44_block_bindings(statements: list[ast.stmt]) -> set[str]:
    """
    Return every name a statement block binds in its own scope.

    Assignment and deletion targets, imports, loop and ``with`` targets,
    exception and pattern captures, and nested definition names count.  A
    nested function, class, or lambda body does not bind here, but a nested
    definition's definition-time expressions do, because a walrus there
    binds in this scope.
    """
    bound: set[str] = set()
    stack: list[ast.AST] = list(statements)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
            stack.extend(_rule_44_definition_expressions(node))
            continue
        if isinstance(node, ast.Lambda):
            stack.extend(
                value
                for value in [*node.args.defaults, *node.args.kw_defaults]
                if value is not None
            )
            continue
        if isinstance(node, ast.Import):
            bound.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
            continue
        if isinstance(node, ast.ImportFrom):
            bound.update(alias.asname or alias.name for alias in node.names)
            continue
        if isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            bound.add(node.rest)
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        stack.extend(ast.iter_child_nodes(node))
    return bound


def _rule_44_expression_bindings(expression: ast.expr) -> set[str]:
    """
    Return the names one executed expression binds in its containing scope.

    A walrus anywhere in the expression binds there, comprehensions
    included; a lambda body binds in the lambda's own scope, so only its
    default expressions count.
    """
    bound: set[str] = set()
    stack: list[ast.AST] = [expression]
    while stack:
        node = stack.pop()
        if isinstance(node, ast.NamedExpr):
            bound.add(node.target.id)
        if isinstance(node, ast.Lambda):
            stack.extend(
                value
                for value in [*node.args.defaults, *node.args.kw_defaults]
                if value is not None
            )
            continue
        stack.extend(ast.iter_child_nodes(node))
    return bound


def _rule_44_bound_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    """
    Return every name one function scope binds.

    A name assigned anywhere in the body is local to the function, and a
    ``nonlocal`` reference resolves to the nearest enclosing scope that binds
    it, so ``nonlocal`` needs those bindings, not only the provenance the
    environment tracks.
    """
    globals_, nonlocals = _rule_44_scope_declarations(function.body)
    bound = set(_rule_44_argument_names(function.args))
    bound |= _rule_44_block_bindings(function.body)
    return frozenset(bound - globals_ - nonlocals)


def _rule_44_definition_expressions(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> list[ast.expr]:
    """
    Return a nested definition's definition-time expressions.

    Defaults, decorators, annotations, return annotations, class bases, and
    class keywords run in the enclosing scope when the definition executes,
    so they are scanned there rather than with the nested body.
    """
    pieces: list[ast.expr] = [*node.decorator_list]
    if isinstance(node, ast.ClassDef):
        pieces.extend([*node.bases, *(keyword.value for keyword in node.keywords)])
        return pieces
    arguments = node.args
    for argument in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]:
        if argument.annotation is not None:
            pieces.append(argument.annotation)
    for variable in (arguments.vararg, arguments.kwarg):
        if variable is not None and variable.annotation is not None:
            pieces.append(variable.annotation)
    pieces.extend(value for value in arguments.defaults if value is not None)
    pieces.extend(value for value in arguments.kw_defaults if value is not None)
    if node.returns is not None:
        pieces.append(node.returns)
    return pieces


def _rule_44_call_violation(
    call: ast.Call,
    environment: _Rule44Environment,
    module_name: str,
    rel: str,
) -> str | None:
    """Return the violation for one prohibited call, if it is one."""
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr not in RULE_44_QUERY_METHODS:
        return None
    role = _keyword(call, "role")
    if not (isinstance(role, ast.Constant) and isinstance(role.value, str)):
        return None
    if not _rule_44_membership_receiver(func.value, environment):
        return None
    return (
        f"rule 44: {module_name}: {rel}:{call.lineno} filters "
        f"OrganizationMembership by string role {role.value!r} outside orgs"
    )


def _rule_44_scan_expression(
    node: ast.expr,
    environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    walrus_environment: _Rule44Environment | None = None,
    conditional: bool = False,
    short_circuited: bool = False,
) -> None:
    """
    Scan one expression against the current binding environment.

    Comprehensions and lambdas open their own scope, a walrus binds in the
    enclosing scope, and iteration targets shadow only inside their
    comprehension, so the environment shadows names as Python resolves them.
    A walrus inside a comprehension runs only while the comprehension
    iterates — a later generator only while the earlier ones do — so
    ``conditional`` keeps the pre-state a zero-iteration run retains; a
    walrus on a short-circuit arm (And/Or operand after the first, either
    branch of a conditional expression) may not run at all, so
    ``short_circuited`` keeps the executing scope's alternatives too.
    """
    if walrus_environment is None:
        walrus_environment = environment
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        nested = environment.copy()
        for index, generator in enumerate(node.generators):
            _rule_44_scan_expression(
                generator.iter,
                nested,
                module_name,
                rel,
                violations,
                walrus_environment,
                conditional=conditional or index > 0,
                short_circuited=short_circuited,
            )
            nested.discard_all(_bound_names(generator.target))
            for condition in generator.ifs:
                _rule_44_scan_expression(
                    condition,
                    nested,
                    module_name,
                    rel,
                    violations,
                    walrus_environment,
                    conditional=True,
                    short_circuited=short_circuited,
                )
        _rule_44_scan_expression(
            node.elt,
            nested,
            module_name,
            rel,
            violations,
            walrus_environment,
            conditional=True,
            short_circuited=short_circuited,
        )
        return
    if isinstance(node, ast.DictComp):
        nested = environment.copy()
        for index, generator in enumerate(node.generators):
            _rule_44_scan_expression(
                generator.iter,
                nested,
                module_name,
                rel,
                violations,
                walrus_environment,
                conditional=conditional or index > 0,
                short_circuited=short_circuited,
            )
            nested.discard_all(_bound_names(generator.target))
            for condition in generator.ifs:
                _rule_44_scan_expression(
                    condition,
                    nested,
                    module_name,
                    rel,
                    violations,
                    walrus_environment,
                    conditional=True,
                    short_circuited=short_circuited,
                )
        _rule_44_scan_expression(
            node.key,
            nested,
            module_name,
            rel,
            violations,
            walrus_environment,
            conditional=True,
            short_circuited=short_circuited,
        )
        _rule_44_scan_expression(
            node.value,
            nested,
            module_name,
            rel,
            violations,
            walrus_environment,
            conditional=True,
            short_circuited=short_circuited,
        )
        return
    if isinstance(node, ast.Lambda):
        for default in [
            *node.args.defaults,
            *(value for value in node.args.kw_defaults if value is not None),
        ]:
            _rule_44_scan_expression(
                default,
                environment,
                module_name,
                rel,
                violations,
                conditional=conditional,
                short_circuited=short_circuited,
            )
        nested = environment.copy()
        nested.discard_all(_rule_44_argument_names(node.args))
        _rule_44_scan_expression(
            node.body,
            nested,
            module_name,
            rel,
            violations,
            conditional=conditional,
            short_circuited=short_circuited,
        )
        return
    if isinstance(node, ast.BoolOp):
        for index, operand in enumerate(node.values):
            _rule_44_scan_expression(
                operand,
                environment,
                module_name,
                rel,
                violations,
                walrus_environment,
                conditional=conditional,
                short_circuited=short_circuited or index > 0,
            )
        return
    if isinstance(node, ast.IfExp):
        _rule_44_scan_expression(
            node.test,
            environment,
            module_name,
            rel,
            violations,
            walrus_environment,
            conditional=conditional,
            short_circuited=short_circuited,
        )
        for branch in (node.body, node.orelse):
            _rule_44_scan_expression(
                branch,
                environment,
                module_name,
                rel,
                violations,
                walrus_environment,
                conditional=conditional,
                short_circuited=True,
            )
        return
    if isinstance(node, ast.NamedExpr):
        _rule_44_scan_expression(
            node.value,
            environment,
            module_name,
            rel,
            violations,
            walrus_environment,
            conditional=conditional,
            short_circuited=short_circuited,
        )
        membership = _rule_44_membership_receiver(node.value, environment)
        # The executing scope takes the binding as far as the walrus
        # definitely runs; a short-circuit arm may skip it, so its
        # alternatives stay.  The enclosing scope keeps the binding only
        # when the walrus runs unconditionally overall, because a
        # zero-iteration comprehension leaves the pre-state in place.
        if membership:
            environment.names.add(node.target.id)
            environment.aliases.pop(node.target.id, None)
        elif not short_circuited:
            environment.discard(node.target.id)
        if walrus_environment is not environment:
            if membership:
                walrus_environment.names.add(node.target.id)
                walrus_environment.aliases.pop(node.target.id, None)
            elif not (conditional or short_circuited):
                walrus_environment.discard(node.target.id)
        return
    if isinstance(node, ast.Call):
        violation = _rule_44_call_violation(node, environment, module_name, rel)
        if violation is not None:
            violations.append(violation)
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.expr):
            _rule_44_scan_expression(
                child,
                environment,
                module_name,
                rel,
                violations,
                walrus_environment,
                conditional=conditional,
                short_circuited=short_circuited,
            )
        elif isinstance(child, ast.keyword):
            _rule_44_scan_expression(
                child.value,
                environment,
                module_name,
                rel,
                violations,
                walrus_environment,
                conditional=conditional,
                short_circuited=short_circuited,
            )


def _rule_44_bind(
    targets: list[ast.expr],
    value: ast.expr,
    environment: _Rule44Environment,
) -> None:
    """Bind assignment targets to membership provenance or shadow them."""
    membership = _rule_44_membership_receiver(value, environment)
    for target in targets:
        for name in _bound_names(target):
            environment.bind(name, membership=membership)


def _rule_44_scan_function(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    defining_environment: _Rule44Environment,
    module_environment: _Rule44Environment,
    enclosing_functions: tuple[_Rule44Scope, ...],
    module_name: str,
    rel: str,
    violations: list[str],
) -> None:
    """Scan one function body with Python's name resolution."""
    environment = defining_environment.copy()
    environment.discard_all(_rule_44_argument_names(function.args))
    globals_, nonlocals = _rule_44_scope_declarations(function.body)
    for name in globals_:
        environment.bind(
            name,
            membership=name in module_environment.names,
            aliases=module_environment.aliases.get(name),
        )
    for name in nonlocals:
        nearest = next(
            (scope for scope in reversed(enclosing_functions) if name in scope[1]),
            None,
        )
        if nearest is None:
            environment.discard(name)
            continue
        scope_environment, _ = nearest
        environment.bind(
            name,
            membership=name in scope_environment.names,
            aliases=scope_environment.aliases.get(name),
        )
    _rule_44_scan_block(
        function.body,
        environment,
        module_environment,
        (*enclosing_functions, (environment, _rule_44_bound_names(function))),
        environment,
        module_name,
        rel,
        violations,
    )


def _rule_44_scan_block(
    statements: list[ast.stmt],
    environment: _Rule44Environment,
    module_environment: _Rule44Environment,
    enclosing_functions: tuple[_Rule44Scope, ...],
    scope_environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    deferred: _Rule44DeferredBodies | None = None,
    intermediates: _Rule44Environment | None = None,
    skip_first_intermediate: bool = False,
) -> None:
    """
    Scan one scope's statements in order and then its deferred bodies.

    Function bodies are deferred until their real defining scope is final,
    because a function resolves module and enclosing names when it runs, not
    when it is defined; definition-time expressions are scanned in place.  A
    compound statement threads the same ``deferred`` list to the scope that
    owns it, so a body defined inside a branch still waits for the whole
    scope; ``scope_environment`` is that owning scope, the one a closure
    resolves.  A branch or loop scans copies and merges them, so a name stays
    membership when any reachable path keeps it; a ``with`` body always runs
    and writes back directly.  When ``intermediates`` is given, the state at
    each statement boundary is unioned into it, so a caller can model an
    exception raised anywhere along the way; ``skip_first_intermediate``
    drops the block's own arrival state, for a ``finally`` whose exceptional
    exits begin only after it has consumed that arrival.
    """
    owns_deferred = deferred is None
    pending: _Rule44DeferredBodies = [] if deferred is None else deferred
    for index, statement in enumerate(statements):
        if intermediates is not None and not (skip_first_intermediate and index == 0):
            intermediates.merge(environment)
        _rule_44_scan_statement(
            statement,
            environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            pending,
            intermediates,
        )
    if owns_deferred:
        for function, defining_environment, outer_functions in pending:
            _rule_44_scan_function(
                function,
                defining_environment,
                module_environment,
                outer_functions,
                module_name,
                rel,
                violations,
            )


def _rule_44_scan_statement(
    statement: ast.stmt,
    environment: _Rule44Environment,
    module_environment: _Rule44Environment,
    enclosing_functions: tuple[_Rule44Scope, ...],
    scope_environment: _Rule44Environment,
    module_name: str,
    rel: str,
    violations: list[str],
    deferred: _Rule44DeferredBodies,
    intermediates: _Rule44Environment | None,
) -> None:
    """Scan one statement, binding names in source order as Python does."""
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for piece in _rule_44_definition_expressions(statement):
            _rule_44_scan_expression(piece, environment, module_name, rel, violations)
        environment.discard(statement.name)
        deferred.append((statement, scope_environment, enclosing_functions))
        return
    if isinstance(statement, ast.ClassDef):
        for piece in _rule_44_definition_expressions(statement):
            _rule_44_scan_expression(piece, environment, module_name, rel, violations)
        environment.discard(statement.name)
        class_environment = environment.copy()
        for member in statement.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for piece in _rule_44_definition_expressions(member):
                    _rule_44_scan_expression(piece, class_environment, module_name, rel, violations)
                # A class body is not an enclosing lexical scope for its
                # methods — through compounds included — so their bodies
                # resolve the scope that owns the class.
                deferred.append((member, scope_environment, enclosing_functions))
            else:
                _rule_44_scan_statement(
                    member,
                    class_environment,
                    module_environment,
                    enclosing_functions,
                    scope_environment,
                    module_name,
                    rel,
                    violations,
                    deferred,
                    intermediates,
                )
        return
    if isinstance(statement, ast.Assign):
        _rule_44_scan_expression(statement.value, environment, module_name, rel, violations)
        _rule_44_bind(statement.targets, statement.value, environment)
        return
    if isinstance(statement, ast.AnnAssign):
        if statement.value is not None:
            _rule_44_scan_expression(statement.value, environment, module_name, rel, violations)
            _rule_44_bind([statement.target], statement.value, environment)
        return
    if isinstance(statement, ast.AugAssign):
        _rule_44_scan_expression(statement.value, environment, module_name, rel, violations)
        return
    if isinstance(statement, ast.Import):
        for alias in statement.names:
            parts = tuple(alias.name.split("."))
            name = alias.asname or parts[0]
            path = parts if alias.asname else (parts[0],)
            environment.bind(
                name,
                membership=False,
                aliases=frozenset({path}) if path in _RULE_44_ALIAS_PATHS else None,
            )
        return
    if isinstance(statement, ast.ImportFrom):
        source = (
            tuple(statement.module.split(".")) if statement.module and not statement.level else ()
        )
        for alias in statement.names:
            name = alias.asname or alias.name
            membership = (
                not statement.level
                and statement.module == RULE_44_MEMBERSHIP_SOURCE
                and alias.name == RULE_44_MEMBERSHIP_MODEL
            )
            path = (*source, alias.name) if source else ()
            environment.bind(
                name,
                membership=membership,
                aliases=frozenset({path}) if path in _RULE_44_ALIAS_PATHS else None,
            )
        return
    if isinstance(statement, (ast.For, ast.AsyncFor)):
        _rule_44_scan_expression(statement.iter, environment, module_name, rel, violations)
        before = environment.copy()
        environment.discard_all(_bound_names(statement.target))
        body_environment = environment.copy()
        _rule_44_scan_block(
            statement.body,
            body_environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            intermediates,
        )
        else_environment = environment.copy()
        _rule_44_scan_block(
            statement.orelse,
            else_environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            intermediates,
        )
        environment.replace(before)
        environment.merge(body_environment)
        environment.merge(else_environment)
        return
    if isinstance(statement, (ast.With, ast.AsyncWith)):
        for item in statement.items:
            _rule_44_scan_expression(item.context_expr, environment, module_name, rel, violations)
            if item.optional_vars is not None:
                environment.discard_all(_bound_names(item.optional_vars))
        _rule_44_scan_block(
            statement.body,
            environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            intermediates,
        )
        return
    if isinstance(statement, ast.If):
        _rule_44_scan_expression(statement.test, environment, module_name, rel, violations)
        body_environment = environment.copy()
        _rule_44_scan_block(
            statement.body,
            body_environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            intermediates,
        )
        else_environment = environment.copy()
        _rule_44_scan_block(
            statement.orelse,
            else_environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            intermediates,
        )
        environment.merge(body_environment)
        environment.merge(else_environment)
        return
    if isinstance(statement, ast.While):
        _rule_44_scan_expression(statement.test, environment, module_name, rel, violations)
        before = environment.copy()
        body_environment = environment.copy()
        _rule_44_scan_block(
            statement.body,
            body_environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            intermediates,
        )
        else_environment = environment.copy()
        _rule_44_scan_block(
            statement.orelse,
            else_environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            intermediates,
        )
        environment.replace(before)
        environment.merge(body_environment)
        environment.merge(else_environment)
        return
    if isinstance(statement, (ast.Try, ast.TryStar)):
        before = environment.copy()
        body_environment = environment.copy()
        body_points = _Rule44Environment()
        _rule_44_scan_block(
            statement.body,
            body_environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            body_points,
        )
        exceptional = environment.copy()
        exceptional.merge(body_points)
        handler_environments: list[_Rule44Environment] = []
        handler_points_all = _Rule44Environment()
        for handler in statement.handlers:
            if handler.type is not None:
                _rule_44_scan_expression(handler.type, environment, module_name, rel, violations)
            handler_environment = exceptional.copy()
            if handler.name:
                handler_environment.discard(handler.name)
            handler_points = _Rule44Environment()
            _rule_44_scan_block(
                handler.body,
                handler_environment,
                module_environment,
                enclosing_functions,
                scope_environment,
                module_name,
                rel,
                violations,
                deferred,
                handler_points,
            )
            handler_environments.append(handler_environment)
            handler_points_all.merge(handler_environment)
            handler_points_all.merge(handler_points)
        else_environment = body_environment.copy()
        else_points = _Rule44Environment()
        _rule_44_scan_block(
            statement.orelse,
            else_environment,
            module_environment,
            enclosing_functions,
            scope_environment,
            module_name,
            rel,
            violations,
            deferred,
            else_points,
        )
        if statement.finalbody:
            # ``finally`` consumes every arrival — the try body, the
            # handlers, the else suite, and their intermediate points — and
            # its output supersedes them all.
            arrivals = before.copy()
            arrivals.merge(body_environment)
            arrivals.merge(body_points)
            arrivals.merge(else_environment)
            arrivals.merge(else_points)
            arrivals.merge(handler_points_all)
            finally_environment = arrivals.copy()
            finally_points = _Rule44Environment()
            _rule_44_scan_block(
                statement.finalbody,
                finally_environment,
                module_environment,
                enclosing_functions,
                scope_environment,
                module_name,
                rel,
                violations,
                deferred,
                finally_points,
                skip_first_intermediate=True,
            )
            environment.replace(finally_environment)
        else:
            arrivals = before.copy()
            arrivals.merge(body_environment)
            arrivals.merge(else_environment)
            for handler_environment in handler_environments:
                arrivals.merge(handler_environment)
            environment.replace(arrivals)
        if intermediates is not None:
            # An enclosing handler or finally observes only what this try's
            # transfer leaves: a nested ``finally``'s output, because it
            # consumes every arrival first, or the raw arrival states when
            # nothing consumes them.
            if statement.finalbody:
                intermediates.merge(finally_environment)
                # Exceptional exits the finally itself can take: its later
                # statement boundaries, never its arrived-at state.
                intermediates.merge(finally_points)
            else:
                intermediates.merge(body_points)
                intermediates.merge(else_points)
                intermediates.merge(handler_points_all)
        return
    if isinstance(statement, ast.Match):
        _rule_44_scan_expression(statement.subject, environment, module_name, rel, violations)
        merged = environment.copy()
        captures: set[str] = set()
        established: set[str] = set()
        for case in statement.cases:
            case_entry = environment.copy()
            case_captures = _rule_44_pattern_names(case.pattern)
            captures |= case_captures
            case_entry.discard_all(case_captures)
            case_environment = case_entry.copy()
            if case.guard is not None:
                _rule_44_scan_expression(case.guard, case_environment, module_name, rel, violations)
            _rule_44_scan_block(
                case.body,
                case_environment,
                module_environment,
                enclosing_functions,
                scope_environment,
                module_name,
                rel,
                violations,
                deferred,
                intermediates,
            )
            merged.merge(case_environment)
            # A capture shadows the name on its case's path; a name the
            # case's own body or guard rebinds (membership or an alias)
            # keeps its post-match state, while inherited provenance does
            # not survive a capture.
            established |= _rule_44_block_bindings(case.body)
            if case.guard is not None:
                established |= _rule_44_expression_bindings(case.guard)
        for name in captures - established:
            merged.discard(name)
        environment.replace(merged)
        return
    if isinstance(statement, ast.Delete):
        for target in statement.targets:
            environment.discard_all(_bound_names(target))
        return
    for child in ast.iter_child_nodes(statement):
        if isinstance(child, ast.expr):
            _rule_44_scan_expression(child, environment, module_name, rel, violations)


def rule_44_role_checks(corpus: Corpus) -> list[str]:
    """Rule 44: one org-role check; no string ``role=`` query outside orgs."""
    violations: list[str] = []
    for module in corpus.modules:
        if module.name == "orgs":
            continue
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            module_environment = _Rule44Environment()
            _rule_44_scan_block(
                _parse(text).body,
                module_environment,
                module_environment,
                (),
                module_environment,
                module.name,
                rel,
                violations,
            )
    return violations
