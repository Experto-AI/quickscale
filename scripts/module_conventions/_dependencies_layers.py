"""
Rule 5's layer-direction mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_dependencies`;
that module re-exports every public name defined here, so existing import
paths keep working.
"""

from __future__ import annotations

from collections.abc import Mapping

from scripts.module_conventions.core import (
    MODULE_LAYERS,
    Module,
    _cross_module_imports,
    _parse,
    _setting_name_module,
    _settings_attribute_reads,
)


def _module_layer_findings(module: Module, layer: int | None) -> tuple[list[str], set[str]]:
    """
    Return a module's rule 5 findings and its same-layer import targets.

    A migration may reach another module's ``models``: the schema layer is
    shared, and the migration exception is listed in decisions.  An upward
    import of any other component is a finding; a same-layer import becomes a
    cycle edge.
    """
    violations: list[str] = []
    same_layer: set[str] = set()
    for rel, text in module.files.items():
        if not rel.endswith(".py"):
            continue
        in_migrations = rel.startswith("migrations/")
        for other, path, names, lineno, _kind in _cross_module_imports(_parse(text)):
            if other == module.name or layer is None:
                continue
            if in_migrations and path[:1] == ("models",):
                continue
            other_layer = MODULE_LAYERS.get(other)
            if other_layer is None:
                continue
            for component in (path[0],) if path else names:
                if in_migrations and component == "models":
                    continue
                if other_layer > layer:
                    violations.append(
                        f"rule 5: {module.name}: {rel}:{lineno} imports upward from "
                        f"{other}:{component} (layer {other_layer} above layer {layer})"
                    )
                elif other_layer == layer:
                    same_layer.add(other)
    return violations, same_layer


def _core_module_setting_findings(core_files: Mapping[str, str]) -> list[str]:
    """Return the rule 5 findings for core files that read a module setting."""
    violations: list[str] = []
    for rel, text in core_files.items():
        if not rel.endswith(".py"):
            continue
        for attribute, lineno in _settings_attribute_reads(_parse(text)):
            if _setting_name_module(attribute) is not None:
                violations.append(f"rule 5: core {rel}:{lineno} names module setting {attribute}")
    return violations
