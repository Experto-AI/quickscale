"""
Rule 4's capability vocabulary, read from core's ``CAPABILITIES``.

Implementation detail of :mod:`scripts.module_conventions.rules_package`; that
module re-exports every public name defined here, so existing import paths
keep working.

The harness keeps no capability literal of its own (SA296 (d)): the closed
name set is parsed out of core's ``runtime/conventions.py``, so a capability
added to core is accepted and a name core does not list is refused without a
second entry to maintain.  An ``AppConfig`` declares capabilities by defining
public members named after them; every other public member it defines must be
a hook name the shipped tree names where a declaration drives it — the
executor a removal obligation names, the handler surface a capability's
consumer lists — so a misspelled declaration fails the check instead of being
silently uncollected.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from scripts.module_conventions.core import (
    CORE_CONVENTIONS_RELATIVE_PATH,
    Corpus,
    Module,
    _call_func_name,
    _class_names,
    _parse,
)

#: The object core wraps the mapping in.  A declaration the harness cannot
#: read fails closed instead of being read as an empty vocabulary.
_CAPABILITIES_WRAPPER = "MappingProxyType"

#: The enum core shapes every entry from.  Each value must be a
#: ``CapabilityShape.<NAME>`` attribute, so a reworded mapping cannot be read
#: as a name set without being noticed.
_CAPABILITY_SHAPE = "CapabilityShape"

#: The members Django's ``AppConfig`` itself defines.  A public member outside
#: this set is a declaration: a capability, or a hook the module's own
#: declarations drive.
DJANGO_APP_CONFIG_MEMBERS: frozenset[str] = frozenset(
    {
        "apps",
        "create",
        "default",
        "default_auto_field",
        "get_model",
        "get_models",
        "import_models",
        "label",
        "models",
        "models_module",
        "module",
        "name",
        "path",
        "ready",
        "verbose_name",
    }
)


def core_capabilities(core_conventions_text: str) -> frozenset[str]:
    """
    Return the closed capability set core's ``CAPABILITIES`` declares.

    The declaration is parsed from the corpus's copy of core's
    ``runtime/conventions.py`` — ``CAPABILITIES: Mapping[str, CapabilityShape]
    = MappingProxyType({...})``.  An absent file, a missing or reworded
    assignment, a non-mapping value, a non-string name, a name listed twice, a
    value outside ``CapabilityShape``, or an empty mapping raises
    ``ValueError``, so the rule reports an unreadable vocabulary instead of
    treating every name as unknown.
    """
    if not core_conventions_text:
        raise ValueError(f"core has no {CORE_CONVENTIONS_RELATIVE_PATH}")
    for statement in _parse(core_conventions_text).body:
        if (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "CAPABILITIES"
        ):
            return _declared_capabilities(statement.value)
    raise ValueError("core declares no CAPABILITIES mapping")


def _declared_capabilities(value: ast.expr) -> frozenset[str]:
    """Return the capability names a ``MappingProxyType({...})`` value lists."""
    if not (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == _CAPABILITIES_WRAPPER
        and len(value.args) == 1
        and isinstance(value.args[0], ast.Dict)
    ):
        raise ValueError("CAPABILITIES is not a MappingProxyType mapping literal")
    names: set[str] = set()
    for key, shape in zip(value.args[0].keys, value.args[0].values):
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str) and key.value):
            raise ValueError(f"CAPABILITIES key {key!r} is not a capability name")
        if key.value in names:
            raise ValueError(f"CAPABILITIES lists {key.value!r} twice")
        if not (
            isinstance(shape, ast.Attribute)
            and isinstance(shape.value, ast.Name)
            and shape.value.id == _CAPABILITY_SHAPE
        ):
            raise ValueError(f"CAPABILITIES entry {key.value!r} declares no CapabilityShape")
        names.add(key.value)
    if not names:
        raise ValueError("CAPABILITIES lists no capability")
    return frozenset(names)


def named_hook_names(corpus: Corpus) -> frozenset[str]:
    """
    Return every hook name the shipped tree names where a declaration drives it.

    An ``AppConfig`` hook the tree's declarations drive is written where the
    declaration or its consumer reads it: as an element of a collection
    literal, a mapping value, a call keyword, or the attribute argument of a
    ``getattr``.  A string outside those positions — a docstring, a log
    message, a field-name constant — is not evidence, so an unrelated literal
    spelling a declaration's name cannot exempt it.
    """
    names: set[str] = set()
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            for node in ast.walk(_parse(text)):
                if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                    names.update(_string_elements(node.elts))
                elif isinstance(node, ast.Dict):
                    names.update(_string_elements(node.values))
                elif isinstance(node, ast.Call):
                    names.update(
                        keyword.value.value
                        for keyword in node.keywords
                        if isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, str)
                    )
                    if (
                        _call_func_name(node) == "getattr"
                        and len(node.args) > 1
                        and isinstance(node.args[1], ast.Constant)
                        and isinstance(node.args[1].value, str)
                    ):
                        names.add(node.args[1].value)
    return frozenset(names)


def _string_elements(nodes: list[ast.expr]) -> Iterator[str]:
    """Yield the string literals among *nodes*, skipping every other form."""
    return (
        node.value
        for node in nodes
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )


def capability_declaration_findings(
    module: Module, capabilities: frozenset[str], named_hooks: frozenset[str]
) -> list[str]:
    """
    Return rule 4's findings for the ``AppConfig`` declarations in *module*.

    Every public member an ``AppConfig`` defines is a Django member, a
    capability core's ``CAPABILITIES`` lists, or a hook name the shipped tree
    writes as a string.  A name in none of the three is a declaration outside
    the closed vocabulary — the misspelled capability this check exists for —
    reported with the line that declares it.  The ``apps.py`` module is the
    one place a module's app config lives (rule 11).
    """
    apps = module.files.get("apps.py")
    if apps is None:
        return []
    findings: list[str] = []
    for node in ast.walk(_parse(apps)):
        if not isinstance(node, ast.ClassDef) or not _is_app_config(node):
            continue
        for name, lineno in _declared_member_names(node):
            if name in DJANGO_APP_CONFIG_MEMBERS or name in capabilities or name in named_hooks:
                continue
            findings.append(
                f"rule 4: {module.name}: apps.py:{lineno} declares {name!r}, "
                "which is not in CAPABILITIES"
            )
    return findings


def _is_app_config(node: ast.ClassDef) -> bool:
    """Return whether the class is an ``AppConfig`` subclass."""
    return any(base == "AppConfig" or base.endswith("AppConfig") for base in _class_names(node))


def _declared_member_names(node: ast.ClassDef) -> list[tuple[str, int]]:
    """Return the public names one class body defines, with their lines."""
    declared: list[tuple[str, int]] = []
    for statement in node.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            declared.append((statement.name, statement.lineno))
        elif isinstance(statement, ast.Assign):
            declared.extend(
                (target.id, statement.lineno)
                for target in statement.targets
                if isinstance(target, ast.Name)
            )
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            declared.append((statement.target.id, statement.lineno))
    return [(name, lineno) for name, lineno in declared if not name.startswith("_")]
