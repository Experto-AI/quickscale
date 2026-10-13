"""
Rule 17's management-command mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_package`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast

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


DESTRUCTIVE_COMMAND_KEYWORDS = (
    "purge",
    "anonymize",
    "restore",
    "prune",
    "delete",
    "sync_media",
    "promote",
)


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
    return violations


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


def _command_findings(module_name: str, command: str, tree: ast.Module, text: str) -> list[str]:
    """Return one management command's rule 17 findings, in report order."""
    flags = _command_flags(tree)
    violations = _flag_findings(module_name, command, flags)
    violations.extend(_call_findings(module_name, command, tree))
    if any(keyword in command for keyword in DESTRUCTIVE_COMMAND_KEYWORDS):
        if "--dry-run" not in text:
            violations.append(f"rule 17: {module_name}: destructive {command} takes no --dry-run")
    return violations
