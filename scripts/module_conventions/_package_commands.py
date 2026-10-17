"""
Rule 17's management-command mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_package`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping

from scripts.module_conventions._misc_checks import (
    _base_origin,
    _base_origins,
    _import_bindings,
)
from scripts.module_conventions.core import (
    _call_func_name,
    _keyword,
)

CONFIRM_COMMAND_KEYWORDS = ("purge", "restore")


def _command_flags(tree: ast.Module) -> dict[str, ast.Call]:
    """Map each ``add_argument`` option string to the call declaring it."""
    flags: dict[str, ast.Call] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_func_name(node) == "add_argument":
            for argument in node.args:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    flags.setdefault(argument.value, node)
    return flags


def _literal_strings(node: ast.expr | None) -> set[str]:
    """Return the string members of a literal list, tuple, or set."""
    if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return set()
    return {
        element.value
        for element in node.elts
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    }


def _constant_string(node: ast.expr | None) -> str | None:
    """Return a string literal's value, or None for anything else."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


#: Rule 17: the operation words that mark a command as one that deletes,
#: anonymizes, or overwrites data.  Destructiveness is keyed on the operation
#: a command calls, never on the command's own name: a command named
#: ``..._reset`` or ``..._wipe`` is refused when its code performs a
#: destructive operation, and a name-keyword command whose code performs none
#: is not.  The first word of the operation's name carries the verb —
#: ``delete_expired`` deletes, while ``select_for_update`` and ``bulk_update``
#: do not — so a synonym this list does not name stays open-world, the
#: detector's recorded boundary; an operation resolved from a computed name
#: (the backups DR bridge's ``ADAPTER_FUNCTIONS.get(function_name)``) names no
#: operation at its call site and stays outside the detector too.  ``save``
#: and ``update`` are the repository's overwrite verbs; a create-only command
#: that persists through a bare ``save()`` is over-refused, the fail-closed
#: direction.
DESTRUCTIVE_OPERATION_WORDS = (
    "anonymize",
    "delete",
    "overwrite",
    "promote",
    "prune",
    "purge",
    "reset",
    "restore",
    "save",
    "sync_media",
    "truncate",
    "update",
    "wipe",
)

#: Rule 17: the one scheduled-off refusal.  A command whose ``--trigger``
#: option exists calls this core helper before any other work, so the refusal
#: reads the same everywhere and no command module spells its own.
SCHEDULED_REFUSAL_HELPER = "require_scheduled_module_enabled"

#: Rule 17: the module that owns the one command base class and the one
#: expected-failure exception.  Both are matched by their resolved import
#: origin, so a same-named object from anywhere else — or an unimported name —
#: is a different object and is refused; an alias import of Django's own
#: passes.
DJANGO_COMMAND_MODULE = "django.core.management.base"

#: Rule 17: the one command base class.  A command module's ``Command`` class
#: subclasses Django's ``BaseCommand``; another base — or no ``Command`` class
#: at all — is refused.
COMMAND_BASE_NAME = "BaseCommand"

#: Rule 17: the one expected-failure exception.  A command reports a failure
#: by raising Django's ``CommandError``; raising anything else from a command
#: module is refused, the statically checkable reading of the clause.
COMMAND_ERROR_NAME = "CommandError"

#: Rule 17: the one organization-selector spelling.  A command that selects a
#: single organization declares ``--organization-id`` and validates the value
#: as a UUID; any other ``--org``/``--organization`` spelling of that selector
#: — ``--organization``, ``--org``, or a slug selector such as
#: ``--organization-slug`` — is refused.  A bare ``--slug`` serves a
#: non-destructive preflight lookup only: a command that offers one also
#: declares ``--organization-id``, and an invocation passes either the selector
#: or the slug, never both (orgs' shape).  The ban is a spelling list, so a
#: synonym it does not name stays open-world.
ORGANIZATION_SELECTOR_FLAG = "--organization-id"


def _banned_organization_selector(flag: str) -> bool:
    """Return True when a declared flag is a refused organization-selector spelling."""
    if flag == ORGANIZATION_SELECTOR_FLAG:
        return False
    normalized = flag.lstrip("-").replace("_", "-")
    stem = "organization" if normalized.startswith("organization") else "org"
    return normalized == stem or normalized.startswith(f"{stem}-")


def _flag_findings(module_name: str, command: str, flags: dict[str, ast.Call]) -> list[str]:
    """Return the rule 17 findings for a command's declared flags."""
    violations: list[str] = []
    if "--format" in flags:
        violations.append(
            f"rule 17: {module_name}: {command} spells machine output --format; use --json"
        )
    if "--scheduled" in flags:
        violations.append(
            f"rule 17: {module_name}: {command} keeps the retired "
            "--scheduled alias; use --trigger scheduled"
        )
    trigger = flags.get("--trigger")
    if trigger is not None:
        choices = _literal_strings(_keyword(trigger, "choices"))
        if "manual" not in choices or "scheduled" not in choices:
            violations.append(
                f"rule 17: {module_name}: {command} --trigger must offer manual and scheduled"
            )
        if (
            _keyword(trigger, "default") is None
            or _constant_string(_keyword(trigger, "default")) != "manual"
        ):
            violations.append(f"rule 17: {module_name}: {command} --trigger must default to manual")
    if any(keyword in command for keyword in CONFIRM_COMMAND_KEYWORDS) and "--confirm" not in flags:
        violations.append(f"rule 17: {module_name}: {command} deletes data and takes no --confirm")
    for flag in sorted(flags):
        if _banned_organization_selector(flag):
            violations.append(
                f"rule 17: {module_name}: {command} spells an organization selector "
                f"{flag}; use --organization-id <uuid>"
            )
    if "--slug" in flags and ORGANIZATION_SELECTOR_FLAG not in flags:
        violations.append(
            f"rule 17: {module_name}: {command} offers --slug without "
            f"{ORGANIZATION_SELECTOR_FLAG}; a slug lookup is non-destructive preflight"
        )
    return violations


def _refuses_scheduled_runs(tree: ast.Module) -> bool:
    """Return whether a command calls the one scheduled-off refusal helper."""
    return any(
        isinstance(node, ast.Call) and _call_func_name(node) == SCHEDULED_REFUSAL_HELPER
        for node in ast.walk(tree)
    )


def _call_findings(module_name: str, command: str, tree: ast.Module) -> list[str]:
    """Return the print() and sys.exit() findings in a command's body."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_func_name(node) == "print":
            violations.append(f"rule 17: {module_name}: {command} calls print()")
        if (
            isinstance(node, ast.Call)
            and _call_func_name(node) == "exit"
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "sys"
        ):
            violations.append(f"rule 17: {module_name}: {command} calls sys.exit()")
    return violations


def _command_base_findings(
    module_name: str,
    command: str,
    tree: ast.Module,
    bindings: Mapping[str, tuple[str, str | None, bool]],
) -> list[str]:
    """Return rule 17's BaseCommand findings for one command module."""
    classes = [
        node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == "Command"
    ]
    if not classes:
        return [
            f"rule 17: {module_name}: {command} defines no Command class; "
            "a command subclasses BaseCommand"
        ]
    if any(
        module_path == DJANGO_COMMAND_MODULE and name == COMMAND_BASE_NAME
        for node in classes
        for module_path, name in _base_origins(node, bindings)
    ):
        return []
    return [f"rule 17: {module_name}: {command} class Command does not subclass BaseCommand"]


def _raise_findings(
    module_name: str,
    command: str,
    tree: ast.Module,
    bindings: Mapping[str, tuple[str, str | None, bool]],
) -> list[str]:
    """
    Return rule 17's CommandError findings for one command module.

    A bare ``raise`` re-raises and stays accepted; every other raise must
    resolve to Django's ``CommandError`` by import origin, aliases included.
    Any other raise is refused — a caught exception re-raised by name and an
    internal raise later translated to ``CommandError`` included, because the
    clause is enforced syntactically.
    """
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        expression = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
        module_path, name = _base_origin(expression, bindings)
        if module_path == DJANGO_COMMAND_MODULE and name == COMMAND_ERROR_NAME:
            continue
        violations.append(
            f"rule 17: {module_name}: {command} raises "
            f"{name or 'an unresolved exception'}; commands report failures "
            f"through {DJANGO_COMMAND_MODULE}.{COMMAND_ERROR_NAME}"
        )
    return violations


def _callee_operation_name(node: ast.Call) -> str:
    """
    Return the operation name a call invokes, or an empty string.

    A call through the adapter registry names its operation in the registry
    key — ``ADAPTER_FUNCTIONS["prune_backups"](...)`` — so the key is the
    operation name rather than the mapping's uninformative attribute.
    """
    func = node.func
    if isinstance(func, ast.Subscript) and isinstance(func.slice, ast.Constant):
        if isinstance(func.slice.value, str):
            return func.slice.value
    return _call_func_name(node)


def _is_destructive_operation(name: str) -> bool:
    """Return True when an operation name begins with a destructive word."""
    normalized = name.strip().lower().lstrip("_")
    return any(
        normalized == word or normalized.startswith(f"{word}_")
        for word in DESTRUCTIVE_OPERATION_WORDS
    )


def _performs_a_destructive_operation(tree: ast.Module) -> bool:
    """Return whether a command's own code calls a data-destroying operation."""
    return any(
        isinstance(node, ast.Call) and _is_destructive_operation(_callee_operation_name(node))
        for node in ast.walk(tree)
    )


def _command_findings(module_name: str, command: str, tree: ast.Module) -> list[str]:
    """
    Return one management command's rule 17 findings, in report order.

    The destructive duty is keyed on the operation the command calls, and
    ``--dry-run`` must be a declared flag: a mention in a help string does not
    satisfy it.
    """
    bindings = _import_bindings(tree)
    flags = _command_flags(tree)
    violations = _command_base_findings(module_name, command, tree, bindings)
    violations.extend(_flag_findings(module_name, command, flags))
    if "--trigger" in flags and not _refuses_scheduled_runs(tree):
        violations.append(
            f"rule 17: {module_name}: {command} --trigger must refuse scheduled "
            f"runs through {SCHEDULED_REFUSAL_HELPER}"
        )
    violations.extend(_call_findings(module_name, command, tree))
    violations.extend(_raise_findings(module_name, command, tree, bindings))
    if _performs_a_destructive_operation(tree) and "--dry-run" not in flags:
        violations.append(f"rule 17: {module_name}: destructive {command} takes no --dry-run")
    return violations
