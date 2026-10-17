"""
Rule 5's layer-direction mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_dependencies`;
that module re-exports every public name defined here, so existing import
paths keep working.  Rule 5's layer table is checked here too: the table's
repository-wide clause is that every shipped module has a layer and that
``MODULE_LAYERS`` matches the table decisions.md declares.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from scripts.module_conventions.core import (
    MODULE_LAYERS,
    SNAKE_CASE,
    Corpus,
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


#: Rule 5's layer table as decisions.md writes it; the header pins the table a
#: reworded document must not silently turn into agreement.
LAYER_TABLE_HEADER = "| Layer | Modules |"

#: The table's divider row (``|---|---|``) and the layer-number cell of a data
#: row, whose em dash (``\u2014``) separates a layer's number from its label.
_LAYER_TABLE_DIVIDER = re.compile(r"^[\s|:-]+$")
_LAYER_TABLE_LAYER_CELL = re.compile(r"^(\d+)\s*\u2014")


def decisions_layer_table(text: str) -> dict[str, int]:
    """
    Return decisions.md's rule 5 layer table as module name -> layer number.

    Layer 0's row is core, not a module, and is dropped.  A missing header, a
    row of another shape, or a module listed twice raises ``ValueError``: the
    harness refuses a table it cannot read instead of reporting agreement.
    """
    lines = [line.strip() for line in text.splitlines()]
    start = next((index for index, line in enumerate(lines) if line == LAYER_TABLE_HEADER), None)
    if start is None:
        raise ValueError(f"no {LAYER_TABLE_HEADER!r} table")
    table: dict[str, int] = {}
    for line in lines[start + 1 :]:
        if not line.startswith("|"):
            break
        if _LAYER_TABLE_DIVIDER.fullmatch(line):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 2:
            raise ValueError(f"row {line!r} is not a two-cell layer row")
        match = _LAYER_TABLE_LAYER_CELL.match(cells[0])
        if match is None:
            raise ValueError(f"row {line!r} names no layer")
        layer = int(match.group(1))
        if layer == 0:
            continue
        for name in (item.strip() for item in cells[1].split(",")):
            if not SNAKE_CASE.fullmatch(name):
                raise ValueError(f"layer {layer} lists {name!r}, not a module name")
            if name in table:
                raise ValueError(
                    f"layer {layer} lists {name}, which layer {table[name]} already lists"
                )
            table[name] = layer
    return table


def layer_table_findings(corpus: Corpus) -> list[str]:
    """
    Return rule 5's layer-table findings over the whole repository.

    Every shipped module has a layer, no layer entry names a module that does
    not ship, and ``MODULE_LAYERS`` agrees with the table decisions.md
    declares (SA296 (c)).  The table is a repository-wide fact, so it is
    checked once here rather than per module source.
    """
    findings: list[str] = []
    shipped = {module.name for module in corpus.modules}
    findings.extend(
        f"rule 5: {name} has no MODULE_LAYERS entry"
        for name in sorted(shipped - set(MODULE_LAYERS))
    )
    findings.extend(
        f"rule 5: MODULE_LAYERS entry {name} ships no module"
        for name in sorted(set(MODULE_LAYERS) - shipped)
    )
    try:
        recorded = decisions_layer_table(corpus.decisions_text)
    except ValueError as exc:
        findings.append(f"rule 5: decisions.md layer table unreadable: {exc}")
        return sorted(findings)
    for name in sorted(set(recorded) | set(MODULE_LAYERS)):
        if name not in MODULE_LAYERS:
            findings.append(
                f"rule 5: decisions.md layer table names {name}, which MODULE_LAYERS does not"
            )
        elif name not in recorded:
            findings.append(
                f"rule 5: MODULE_LAYERS names {name}, which decisions.md layer table does not"
            )
        elif recorded[name] != MODULE_LAYERS[name]:
            findings.append(
                f"rule 5: {name} is layer {recorded[name]} in decisions.md and layer "
                f"{MODULE_LAYERS[name]} in MODULE_LAYERS"
            )
    return sorted(findings)
