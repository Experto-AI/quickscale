"""
Rule 22's analytics-event mechanics: the capture surface and event stems.

Implementation detail of :mod:`scripts.module_conventions.rules_analytics`;
that module owns rule 22's orchestration and re-exports this module's names.
"""

from __future__ import annotations

import ast
from typing import Any

from scripts.module_conventions.core import (
    Corpus,
    Module,
    _call_func_name,
    _keyword,
    _literal,
    _parse,
    _string_assignments,
    _string_list,
)


def _analytics_module(corpus: Corpus) -> Module | None:
    """Return the corpus's analytics module, when it carries one."""
    return next((module for module in corpus.modules if module.name == "analytics"), None)


def _capture_surface_violations(corpus: Corpus) -> list[str]:
    """Rule 22's analytics-package clause: one ``capture_event`` helper, exported."""
    analytics = _analytics_module(corpus)
    if analytics is None:
        return []
    services = analytics.files.get("services.py", "")
    if not services:
        return []
    tree = _parse(services)
    violations: list[str] = []
    helpers = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("capture_")
    ]
    if helpers != ["capture_event"]:
        violations.append(
            f"rule 22: analytics: capture helpers are {helpers}, expected ['capture_event']"
        )
    exports = _string_list(tree).get("__all__", [])
    if "capture_event" not in exports:
        violations.append("rule 22: analytics: capture_event is not in services.__all__")
    return violations


def _event_constants(module: Module) -> dict[str, Any]:
    """Collect the module's upper-case and ``_EVENT`` string constants."""
    constants: dict[str, Any] = {}
    for rel, text in module.files.items():
        if rel.endswith(".py"):
            constants.update(
                {
                    name: value
                    for name, value in _string_assignments(_parse(text)).items()
                    if name.isupper() or name.endswith("_EVENT")
                }
            )
    return constants


def _event_argument(node: ast.Call) -> ast.expr | None:
    """Return a capture call's event argument: the keyword, else the second positional."""
    argument = _keyword(node, "event")
    if argument is None and len(node.args) >= 2:
        argument = node.args[1]
    return argument


def _resolved_event(node: ast.Call, constants: dict[str, Any]) -> Any:
    """Resolve a capture call's event name through the module's constants."""
    argument = _event_argument(node)
    if isinstance(argument, ast.Name):
        return constants.get(argument.id)
    return _literal(argument)


def _event_stem_findings(module_name: str, rel: str, event: Any) -> list[str]:
    """Rule 22's stem clause for one capture call's resolved event name."""
    if not isinstance(event, str):
        return [f"rule 22: {module_name}: {rel} calls capture_event with no resolvable event name"]
    if event != "$pageview" and not event.startswith(f"quickscale_{module_name}_"):
        return [f"rule 22: {module_name}: event {event!r} lacks the quickscale_{module_name}_ stem"]
    return []


def _module_event_violations(module: Module) -> list[str]:
    """Rule 22's stem clause for every capture call in one non-analytics module."""
    constants = _event_constants(module)
    violations: list[str] = []
    for rel, text in module.files.items():
        if not rel.endswith(".py"):
            continue
        for node in ast.walk(_parse(text)):
            if not isinstance(node, ast.Call):
                continue
            if _call_func_name(node) != "capture_event":
                continue
            violations.extend(
                _event_stem_findings(module.name, rel, _resolved_event(node, constants))
            )
    return violations


def _event_stem_scan_violations(corpus: Corpus) -> list[str]:
    """Scan every non-analytics module's capture calls for the event stem."""
    violations: list[str] = []
    for module in corpus.modules:
        if module.name == "analytics":
            continue
        violations.extend(_module_event_violations(module))
    return violations
