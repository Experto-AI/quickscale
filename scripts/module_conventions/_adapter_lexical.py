"""
Lexical helpers for the bounded adapter call graph (``adapter_flow`` facade).

The pre-split ``adapter_flow`` module published these type aliases and name
scanners; this private sibling keeps the mechanics while the facade re-exports
every one of them unchanged.
"""

from __future__ import annotations

import ast

from scripts.module_conventions.core import _body_nodes, _bound_names

Function = ast.FunctionDef | ast.AsyncFunctionDef
CallableEnvironment = dict[int, dict[str, str]]


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
