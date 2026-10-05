"""Carry planning, rendering, and execution for donor migration operations.

Renders the appended recipient migrations that carry the donor operations the
autodetector cannot regenerate, including only the module-level definitions
those operations reference, and fails closed when a reference is mutated at
import or cannot be resolved statically.
"""

from .model import (
    BetaMigrationReport,
    ProjectSnapshot,
    _append_completed_step,
    _record_changed_file,
)
from .project_apps_label import _class_named, _project_app_label
from .project_apps_migration_analysis import (
    _AUTODETECTOR_OPERATION_NAMES,
    _BUILTIN_NAMES,
    CarriedMigration,
    _class_attribute_declaration,
    _definition_required_names,
    _definition_source_segment,
    _migration_operation_name,
    _module_level_bindings,
    _module_level_mutation,
    _referenced_names,
    _validate_migration_class,
    _validate_operations_declaration,
)
from .project_apps_ops import _donor_app_registration, _write_validated_python
from pathlib import Path
import ast


def _carried_operation_elements(
    operations: ast.List | ast.Tuple,
    *,
    donor_name: str,
) -> list[ast.Call]:
    """Return the operations the autodetector cannot regenerate.

    A non-call element, or a call whose operation name cannot be read, fails
    closed because the tool cannot classify or carry it.
    """
    kept: list[ast.Call] = []
    elements = operations.elts
    for element in elements:
        if not isinstance(element, ast.Call):
            raise ValueError(
                f"{donor_name}:{getattr(element, 'lineno', '?')} unresolved operation"
            )
        operation_name = _migration_operation_name(element)
        if operation_name is None:
            raise ValueError(
                f"{donor_name}:{getattr(element, 'lineno', '?')} unresolved operation"
            )
        if operation_name not in _AUTODETECTOR_OPERATION_NAMES:
            kept.append(element)
    return kept


def _render_carried_migration(
    *,
    text: str,
    tree: ast.Module,
    kept_operations: list[ast.Call],
    donor_name: str,
    name: str,
    label: str,
    dependency: str,
    atomic: bool,
) -> CarriedMigration:
    """Render one appended migration carrying the donor's unreproducible ops."""
    bindings = _module_level_bindings(tree)
    if "migrations" not in bindings:
        raise ValueError(
            f"{donor_name}: no module-level 'migrations' import is available to carry"
        )

    needed: set[str] = {"migrations"}
    for operation in kept_operations:
        needed |= _referenced_names(operation)

    definition_requirements = _definition_required_names(text)
    selected: list[ast.stmt] = []
    seen: set[int] = set()
    required_bindings: set[str] = set()
    frontier = set(needed)
    while frontier:
        required_name = frontier.pop()
        if required_name in _BUILTIN_NAMES:
            continue
        statements = bindings.get(required_name)
        if statements is None:
            raise ValueError(
                f"{donor_name}: a carried operation references "
                f"{required_name!r}, which is not defined at module level"
            )
        required_bindings.add(required_name)
        for statement in statements:
            if id(statement) in seen:
                continue
            seen.add(id(statement))
            selected.append(statement)
            if (
                isinstance(
                    statement,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
                )
                and statement.name in definition_requirements
            ):
                frontier |= definition_requirements[statement.name]
            else:
                frontier |= _referenced_names(statement)
    mutation = _module_level_mutation(tree, required_bindings)
    if mutation is not None:
        raise ValueError(
            f"{donor_name}: module-level mutation of {mutation!r} cannot be "
            "carried safely; re-express the operation without a mutated binding"
        )
    selected.sort(key=lambda node: (node.lineno, node.col_offset))

    header_segments = [
        segment
        for segment in (
            _definition_source_segment(text, statement) for statement in selected
        )
        if segment is not None
    ]
    operation_segments: list[str] = []
    operation_names: list[str] = []
    for operation in kept_operations:
        segment = ast.get_source_segment(text, operation)
        if segment is None:
            raise ValueError(
                f"{donor_name}:{operation.lineno}: operation source cannot be extracted"
            )
        operation_names.append(
            f"{_migration_operation_name(operation)} (line {operation.lineno})"
        )
        # Indent only the first physical line: the operation sits inside a
        # bracketed list, so continuation lines need no re-indentation and
        # re-indenting them would alter multiline string literal values.
        operation_segments.append("        " + segment)

    lines = [
        f'"""Carried donor migration operations from {donor_name}.',
        "",
        "Generated by the QuickScale beta migration: the donor operations below",
        "cannot be regenerated from the current models, so the recipient carries",
        "them in an appended migration after the regenerated initial state.",
        '"""',
        "",
        "\n\n".join(header_segments),
        "",
        "class Migration(migrations.Migration):",
        f'    dependencies = [("{label}", "{dependency}")]',
    ]
    if atomic:
        lines.append("    atomic = False")
    lines.append("")
    lines.append("    operations = [")
    lines.append(",\n".join(operation_segments))
    lines.append("    ]")
    content = "\n".join(lines) + "\n"
    try:
        compile(content, name, "exec")
    except SyntaxError as error:
        raise ValueError(
            f"{donor_name}: carried operations cannot be rendered as valid Python: {error}"
        ) from error
    return CarriedMigration(
        donor_name=donor_name,
        name=name,
        content=content,
        operation_names=tuple(operation_names),
    )


def _plan_carried_migrations(
    app_dir: Path,
    label: str,
    *,
    base_dependency: str = "0001_initial",
    start_index: int = 2,
) -> list[CarriedMigration]:
    """Plan recipient migrations carrying every unreproducible donor operation.

    Raises ValueError naming the exact migration and construct when any donor
    migration cannot be carried safely, so the caller fails closed before
    mutation instead of dropping the operation silently.  ``base_dependency``
    names the regenerated migration the first carry chains from, and
    ``start_index`` its file number; execution re-plans with the recipient's
    actual regenerated graph, which can be a multi-file initial state.
    """
    migrations_dir = app_dir / "migrations"
    if not migrations_dir.is_dir():
        return []
    carried: list[CarriedMigration] = []
    index = start_index
    for migration_path in sorted(migrations_dir.glob("*.py")):
        if migration_path.name == "__init__.py":
            continue
        try:
            text = migration_path.read_text()
        except OSError as exc:
            raise ValueError(
                f"{migration_path.name}: unreadable migration ({exc})"
            ) from exc
        try:
            tree = ast.parse(text, filename=str(migration_path))
        except SyntaxError as exc:
            raise ValueError(
                f"{migration_path.name}: unparseable migration ({exc})"
            ) from exc
        migration_class = _class_named(tree, "Migration")
        if migration_class is None:
            declares_operations = any(
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "operations"
                    for target in node.targets
                )
                for node in ast.walk(tree)
            )
            if declares_operations:
                raise ValueError(
                    f"{migration_path.name}: no Migration class declares its operations"
                )
            continue
        _validate_operations_declaration(
            migration_class, donor_name=migration_path.name
        )
        operations = _class_attribute_declaration(migration_class, "operations")
        if operations is None:
            continue
        if not isinstance(operations, (ast.List, ast.Tuple)):
            raise ValueError(
                f"{migration_path.name}: operations declaration cannot be resolved "
                "statically"
            )
        kept_operations = _carried_operation_elements(
            operations, donor_name=migration_path.name
        )
        if not kept_operations:
            continue
        atomic = _validate_migration_class(
            migration_class, label=label, donor_name=migration_path.name
        )
        suffix = migration_path.stem.lstrip("0123456789_") or "operations"
        name = f"{index:04d}_carried_{suffix}.py"
        dependency = (
            carried[-1].name.removesuffix(".py") if carried else base_dependency
        )
        carried.append(
            _render_carried_migration(
                text=text,
                tree=tree,
                kept_operations=kept_operations,
                donor_name=migration_path.name,
                name=name,
                label=label,
                dependency=dependency,
                atomic=atomic,
            )
        )
        index += 1
    return carried


def _project_app_carry_plan(
    donor: ProjectSnapshot,
) -> list[tuple[str, CarriedMigration]]:
    """Return every app migration the fresh-first execution must carry.

    A planning failure skips the app here only because the preflight has
    already validated it and recorded a blocker on failure; execution plans
    each app directly and fails closed instead of using this preview.
    """
    plan: list[tuple[str, CarriedMigration]] = []
    for app_name in donor.project_apps:
        app_dir = donor.path / app_name
        try:
            label = _project_app_label(
                app_dir,
                registration=_donor_app_registration(
                    donor.path, donor.identity.package, app_name
                ),
            )
            migrations = _plan_carried_migrations(app_dir, label)
        except OSError, SyntaxError, ValueError:
            continue
        plan.extend((app_name, migration) for migration in migrations)
    return plan


def _migration_dependency_names(
    migration_class: ast.ClassDef, *, label: str
) -> set[str]:
    """Return the same-app migration names a Migration class depends on."""
    dependencies = _class_attribute_declaration(migration_class, "dependencies")
    if not isinstance(dependencies, (ast.List, ast.Tuple)):
        return set()
    names: set[str] = set()
    for element in dependencies.elts:
        if not (isinstance(element, (ast.Tuple, ast.List)) and len(element.elts) == 2):
            continue
        app_label, migration_name = element.elts
        if (
            isinstance(app_label, ast.Constant)
            and app_label.value == label
            and isinstance(migration_name, ast.Constant)
            and isinstance(migration_name.value, str)
        ):
            names.add(migration_name.value)
    return names


def _regenerated_migration_terminal(
    migrations_dir: Path, *, label: str, donor_name: str
) -> tuple[str, int]:
    """Return the terminal regenerated migration and the next free number.

    ``makemigrations`` can emit more than one initial migration when project
    apps reference each other, so a carry must chain from the recipient's
    actual terminal leaf instead of assuming ``0001_initial``, and its number
    must not collide with that multi-file graph.
    """
    names: set[str] = set()
    dependencies: dict[str, set[str]] = {}
    highest = 1
    for path in sorted(migrations_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        stem = path.stem
        names.add(stem)
        prefix = stem.split("_", 1)[0]
        if prefix.isdigit():
            highest = max(highest, int(prefix))
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except (OSError, SyntaxError) as exc:
            raise ValueError(
                f"Cannot inspect the regenerated migration {path.name} for "
                f"{donor_name}: {exc}"
            ) from exc
        migration_class = _class_named(tree, "Migration")
        if migration_class is not None:
            dependencies[stem] = _migration_dependency_names(
                migration_class, label=label
            )
    if not names:
        raise ValueError(
            f"makemigrations produced no migration for {label}; cannot carry "
            f"{donor_name}."
        )
    referenced = {name for deps in dependencies.values() for name in deps}
    leaves = sorted(name for name in names if name not in referenced)
    if len(leaves) != 1:
        rendered = ", ".join(leaves) or "(none)"
        raise ValueError(
            f"The regenerated migrations for {label} have {len(leaves)} terminal "
            f"migrations ({rendered}); cannot chain {donor_name} safely."
        )
    return leaves[0], highest + 1


def _execute_carry_project_app_migrations(report: BetaMigrationReport) -> None:
    """Write the planned carried migrations after makemigrations regenerated 0001.

    The verification stack calls this immediately after its recipient-local
    ``makemigrations`` command, so the appended migrations run with ``migrate``
    in the same stack.  Each app is re-planned against the recipient's actual
    regenerated migration graph, and any planning failure propagates so an
    accepted operation is never silently dropped.
    """
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    written: list[tuple[str, CarriedMigration]] = []
    for app_name in report.donor.project_apps:
        app_dir = report.donor.path / app_name
        label = _project_app_label(
            app_dir,
            registration=_donor_app_registration(
                report.donor.path, report.donor.identity.package, app_name
            ),
        )
        preview = _plan_carried_migrations(app_dir, label)
        if not preview:
            continue
        migrations_dir = report.recipient.path / app_name / "migrations"
        if not migrations_dir.is_dir():
            raise ValueError(
                f"Cannot carry {preview[0].donor_name}: the recipient's "
                f"{app_name}/migrations directory does not exist after makemigrations."
            )
        base_dependency, start_index = _regenerated_migration_terminal(
            migrations_dir, label=label, donor_name=preview[0].donor_name
        )
        plan = _plan_carried_migrations(
            app_dir, label, base_dependency=base_dependency, start_index=start_index
        )
        for migration in plan:
            target = migrations_dir / migration.name
            if target.exists():
                raise ValueError(
                    f"Refusing to overwrite the existing recipient migration {target}."
                )
            _write_validated_python(target, migration.content)
            _record_changed_file(report, target)
            written.append((app_name, migration))

    if not written:
        return
    rendered = "; ".join(
        f"{app_name}:{migration.donor_name} -> {migration.name} "
        f"({', '.join(migration.operation_names)})"
        for app_name, migration in written
    )
    _append_completed_step(
        report,
        step="carry-project-app-migration-operations",
        detail=(
            "Carried donor project-owned-app migration operations the autodetector "
            f"cannot regenerate into appended recipient migrations: {rendered}."
        ),
    )
