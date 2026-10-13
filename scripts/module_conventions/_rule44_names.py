"""
Rule 44's membership environment and name-resolution mechanics.

Implementation detail of :mod:`scripts.module_conventions.rule_44`; that
module re-exports every name defined here, so existing import paths and the
rule registry keep working.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping

from scripts.module_conventions.core import (
    _attribute_chain,
    _call_func_name,
    _literal,
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
