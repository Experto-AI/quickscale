"""
Rule 29's test names and shipped-source ticket ids.

Implementation detail of :mod:`scripts.module_conventions.rules_identity`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scripts.module_conventions.core import Corpus, Module, _parse

#: A ticket id anywhere in a ``tests/`` entry: file name, docstring,
#: comment, identifier, or string literal.  It counts in either case at a
#: word boundary (``_sa61_media_root_tmp_path``, ``sa41-bench``) and, inside
#: a longer name, where a capitalised id follows a lowercase letter
#: (``TestWidgetSA35``, ``CrSa47Owner1``).  The boundary keeps ordinary
#: words out (``visa42``); an id in an all-caps name joined to an uppercase
#: letter (``NASA1``, ``TESTSA999``) is the scan's documented limit.
TICKET_IN_TEST = re.compile(
    r"(?<![A-Za-z0-9])(?:[Ss][Aa]|[Aa][Ff])\d+"
    r"|(?<=[a-z])(?:S[Aa]|A[Ff])\d+"
    r"|CR-[Ss][Aa]\d+"
)

# Shipped source and manifests additionally carry the plan-phase ``T<n>.<n>``
# ids the audit counts alongside ``SA``/``AF`` ids; that scan keeps its
# historical word-boundary, case-sensitive shape.
TICKET_IN_SHIPPED = re.compile(r"(?<![A-Za-z0-9])(?:SA|AF)\d+|CR-SA\d+|T\d+\.\d+")

#: A release stamp in a manifest description: a ``v``-prefixed release
#: (``v0.80``, ``v0.80.0``) or a bare three-component version (``0.80.0``).
#: Option prose describes behavior, not the release that introduced it.
VERSION_STAMP_IN_DESCRIPTION = re.compile(
    r"(?<![A-Za-z0-9])v\d+\.\d+(?:\.\d+)?(?![A-Za-z0-9])"
    r"|(?<![A-Za-z0-9])\d+\.\d+\.\d+(?![A-Za-z0-9])"
)


def _tests_entry_allowed(rel: str) -> bool:
    """Return whether one ``tests/`` entry is inside rule 29's file set."""
    parts = rel.split("/")
    if parts[0] == "templates" or parts[0].endswith("_app"):
        return True
    if len(parts) > 1:
        return parts[0].startswith("_")
    name = parts[0]
    if name in {"__init__.py", "conftest.py"} or name.startswith("_"):
        return True
    if name.startswith("test_") and name.endswith(".py"):
        return True
    return (name.startswith("settings") or name.startswith("urls")) and name.endswith(".py")


def _shipped_ticket_violations(module: Module) -> list[str]:
    """Return rule 29's ticket ids in shipped source files and the manifest."""
    violations: list[str] = []
    for rel, text in module.files.items():
        if not rel.endswith(".py"):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if TICKET_IN_SHIPPED.search(line):
                violations.append(
                    f"rule 29: {module.name}: {rel}:{lineno} carries a ticket id in shipped source"
                )
    for lineno, line in enumerate(module.manifest_text.splitlines(), start=1):
        if TICKET_IN_SHIPPED.search(line):
            violations.append(f"rule 29: {module.name}: module.yml:{lineno} carries a ticket id")
    return violations


def _description_values(node: Any) -> list[str]:
    """Return every string value the manifest stores under a ``description`` key."""
    values: list[str] = []
    if isinstance(node, Mapping):
        for key, value in node.items():
            if key == "description" and isinstance(value, str):
                values.append(value)
            values.extend(_description_values(value))
    elif isinstance(node, list):
        for item in node:
            values.extend(_description_values(item))
    return values


def _manifest_description_prose_violations(module: Module) -> list[str]:
    """
    Return rule 29's ticket ids and release stamps in manifest prose.

    The module, option, and derivation descriptions are shipped text and
    carry the same no-ticket-id rule as every ``tests/`` entry, in any case
    and embedded in a longer name, and name behavior rather than the release
    that introduced it.  The ``contract_vintage`` block's ``sa<NNN>-<slug>``
    ``id`` is the adopted-step identity the contract vintage requires, not
    prose, and stays outside this scan.
    """
    violations: list[str] = []
    for value in _description_values(module.manifest):
        if TICKET_IN_TEST.search(value):
            violations.append(
                f"rule 29: {module.name}: module.yml description carries a ticket id: {value!r}"
            )
        elif VERSION_STAMP_IN_DESCRIPTION.search(value):
            violations.append(
                f"rule 29: {module.name}: module.yml description carries a release stamp: {value!r}"
            )
    return violations


def _docstring_constants(tree: ast.AST) -> set[int]:
    """Return the string constants that serve as docstrings in *tree*."""
    constants: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            constants.add(id(body[0].value))
    return constants


def _test_file_ticket_violations(module: Module, rel: str, text: str) -> list[str]:
    """Return rule 29's ticket ids in one test file's name, docstrings, comments."""
    basename = Path(rel).name
    if not basename.startswith("test_") or not basename.endswith(".py"):
        return []
    violations: list[str] = []
    if TICKET_IN_TEST.search(basename):
        violations.append(f"rule 29: {module.name}: test file {basename} carries a ticket id")
    try:
        tree = _parse(text)
    except SyntaxError:
        return violations
    docstrings = [ast.get_docstring(tree)]
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            docstrings.append(ast.get_docstring(node))
    for docstring in docstrings:
        if docstring and TICKET_IN_TEST.search(docstring):
            violations.append(f"rule 29: {module.name}: {basename} docstring carries a ticket id")
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT and TICKET_IN_TEST.search(token.string):
                violations.append(f"rule 29: {module.name}: {basename} comment carries a ticket id")
    except tokenize.TokenError, IndentationError:
        return violations
    return violations


def _collect_entry_names(
    tree: ast.AST, docstrings: set[int], report_docstrings: bool
) -> tuple[list[str], list[str]]:
    """Return one parsed test entry's identifier and string-literal names."""
    identifiers: list[str] = []
    strings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            identifiers.append(node.name)
        elif isinstance(node, ast.Name):
            identifiers.append(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.append(node.attr)
        elif isinstance(node, ast.arg):
            identifiers.append(node.arg)
        elif isinstance(node, ast.keyword):
            if node.arg is not None:
                identifiers.append(node.arg)
        elif isinstance(node, ast.alias):
            identifiers.append(node.name)
            if node.asname is not None:
                identifiers.append(node.asname)
        elif isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, bytes):
                strings.append(value.decode("utf-8", "replace"))
            elif isinstance(value, str) and (report_docstrings or id(node) not in docstrings):
                strings.append(value)
    return identifiers, strings


def _test_code_ticket_violations(module: Module, rel: str, text: str) -> list[str]:
    """
    Return rule 29's ticket ids in one test entry's identifiers and strings.

    Every ``.py`` entry under ``tests/`` is scanned, not only
    ``test_<subject>.py`` files: ``conftest.py`` fixtures and ``urls.py``
    route names carry identifiers and string literals as well.  A docstring
    is reported through the docstring scan above where that scan already
    covers the entry, and as a string literal otherwise.
    """
    basename = Path(rel).name
    if not basename.endswith(".py"):
        return []
    try:
        tree = _parse(text)
    except SyntaxError:
        return []
    docstrings = _docstring_constants(tree)
    identifiers, strings = _collect_entry_names(tree, docstrings, not basename.startswith("test_"))
    violations = [
        f"rule 29: {module.name}: {basename} identifier carries a ticket id"
        for name in identifiers
        if TICKET_IN_TEST.search(name)
    ]
    violations.extend(
        f"rule 29: {module.name}: {basename} string carries a ticket id"
        for value in strings
        if TICKET_IN_TEST.search(value)
    )
    return violations


def rule_29_test_names(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        for rel in module.tests:
            if not _tests_entry_allowed(rel):
                violations.append(
                    f"rule 29: {module.name}: {rel} is outside rule 29's tests file set"
                )
        violations.extend(_shipped_ticket_violations(module))
        violations.extend(_manifest_description_prose_violations(module))
        for rel, text in module.tests.items():
            violations.extend(_test_file_ticket_violations(module, rel, text))
            violations.extend(_test_code_ticket_violations(module, rel, text))
    return violations
