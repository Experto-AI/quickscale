"""Preserve generated Django symbols when donor files replace scaffold files."""

from __future__ import annotations

from pathlib import Path
import ast


def _definition_spans(source: str) -> dict[str, tuple[int, int]]:
    """Map every top-level bound name to its full 1-based source line span."""
    tree = ast.parse(source)
    spans: dict[str, tuple[int, int]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno
            if node.decorator_list:
                start = min(decorator.lineno for decorator in node.decorator_list)
            spans[node.name] = (start, node.end_lineno or node.lineno)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    spans[target.id] = (node.lineno, node.end_lineno or node.lineno)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            spans[node.target.id] = (node.lineno, node.end_lineno or node.lineno)
    return spans


def _definition_nodes(source: str) -> dict[str, ast.stmt]:
    """Map every top-level bound name to its definition node."""
    tree = ast.parse(source)
    nodes: dict[str, ast.stmt] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nodes[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    nodes[target.id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            nodes[node.target.id] = node
    return nodes


def _import_bindings(
    source: str,
) -> list[tuple[frozenset[str], tuple[int, int]]]:
    """Map each top-level import statement to its bound names and line span."""
    tree = ast.parse(source)
    bindings: list[tuple[frozenset[str], tuple[int, int]]] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = frozenset(
                alias.asname or alias.name.split(".")[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            names = frozenset(alias.asname or alias.name for alias in node.names)
        else:
            continue
        bindings.append((names, (node.lineno, node.end_lineno or node.lineno)))
    return bindings


def _bound_import_names(source: str) -> set[str]:
    """Return every name bound by the source's top-level imports."""
    bound: set[str] = set()
    for names, _span in _import_bindings(source):
        bound.update(names)
    return bound


def _referenced_names(node: ast.AST) -> set[str]:
    """Return every root name loaded inside a definition node."""
    return {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }


def append_missing_generated_symbols(
    destination: Path, generated_source: str
) -> list[str]:
    """Append the generated top-level symbols the copied donor file lacks.

    The donor's file keeps every symbol it defines. Generated symbols the
    current scaffold's wiring imports (for example the React shell view) are
    appended with the imports they need, so a donor file copied over the
    scaffold keeps satisfying the regenerated wiring. Returns the appended
    symbol names in generated-file order.
    """
    donor_source = destination.read_text()
    generated_spans = _definition_spans(generated_source)
    donor_names = set(_definition_spans(donor_source))
    missing = [name for name in generated_spans if name not in donor_names]
    if not missing:
        return []

    generated_lines = generated_source.splitlines()
    generated_nodes = _definition_nodes(generated_source)
    donor_bound_imports = _bound_import_names(donor_source)

    referenced: set[str] = set()
    pending = list(missing)
    while pending:
        name = pending.pop()
        for candidate in _referenced_names(generated_nodes[name]):
            if candidate in donor_names or candidate in missing:
                continue
            referenced.add(candidate)

    import_bindings = _import_bindings(generated_source)
    import_spans: dict[str, tuple[int, int]] = {}
    import_names: dict[tuple[int, int], frozenset[str]] = {}
    for names, import_span in import_bindings:
        import_names[import_span] = names
        for name in names:
            import_spans.setdefault(name, import_span)

    needed_spans: set[tuple[int, int]] = set()
    for name in referenced:
        candidate_span = import_spans.get(name)
        if candidate_span is None:
            continue
        statement_lines = generated_lines[candidate_span[0] - 1 : candidate_span[1]]
        statement_text = "\n".join(statement_lines)
        if import_names[candidate_span] <= donor_bound_imports:
            continue
        if statement_text in donor_source:
            continue
        needed_spans.add(candidate_span)

    appended_lines: list[str] = []
    for needed_span in sorted(needed_spans):
        appended_lines.extend(generated_lines[needed_span[0] - 1 : needed_span[1]])
    if appended_lines:
        appended_lines.append("")
    appended_lines.append(
        "# QuickScale generated symbols preserved by the beta-migration carry."
    )
    for name in missing:
        start, end = generated_spans[name]
        appended_lines.extend(generated_lines[start - 1 : end])
        appended_lines.append("")

    merged_source = (
        donor_source.rstrip("\n")
        + "\n\n"
        + "\n".join(appended_lines).rstrip("\n")
        + "\n"
    )
    destination.write_text(merged_source)
    return missing
