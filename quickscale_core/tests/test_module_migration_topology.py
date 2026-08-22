"""Guard the shipped modules' clean-break migration topology.

The inventory in this file is deliberately source-derived.  The canonical
module discovery contract supplies names and roots; each root supplies its
AppConfig identity, model presence, and migration files.  Temporary-tree
canaries then prove that the classifier fails closed when the topology drifts.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
from typing import Mapping

import pytest

from quickscale_core.contracts.module_discovery import (
    PLACEHOLDER_MODULE_NAMES,
    authoritative_module_names,
    discover_shipped_module_paths,
    is_placeholder_module,
)


EXPECTED_MODEL_MODULE_COUNT = 10
_INITIAL_MIGRATION_FILENAME = "0001_initial.py"
_MIGRATIONS_INIT_FILENAME = "__init__.py"
_NUMBERED_MIGRATION_PATTERN = re.compile(r"^\d{4}_.+\.py$")
_MISSING = object()
_AMBIGUOUS = object()
_NON_LITERAL = object()


@dataclass(frozen=True)
class ModuleAppConfigIdentity:
    """The explicit Django AppConfig identity bound from ``apps.py``."""

    name: str
    label: str


@dataclass(frozen=True)
class ModuleInventory:
    """Source-derived module inventory used by this and later test phases."""

    names: tuple[str, ...]
    paths: dict[str, Path]
    app_configs: dict[str, ModuleAppConfigIdentity]
    model_modules: tuple[str, ...]
    service_modules: tuple[str, ...]


@dataclass(frozen=True)
class TopologyDiagnostic:
    """One actionable topology defect found during an inventory pass."""

    module: str
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.module}: [{self.code}] {self.detail}"


def _read_initial_flag(migration_path: Path) -> object:
    """Read one literal ``Migration.initial`` without executing source code.

    The accepted shape is intentionally narrow: one direct literal assignment
    in the module's sole top-level ``Migration`` class.  Any other binding that
    could change the value is treated as ambiguous rather than inferred away.
    """
    tree = ast.parse(migration_path.read_text(), filename=str(migration_path))
    migration_classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Migration"
    ]
    if not migration_classes:
        return _MISSING
    if len(migration_classes) != 1:
        return _AMBIGUOUS

    migration_class = migration_classes[0]
    assignments: list[ast.expr] = []
    accepted_store_ids: set[int] = set()
    for node in migration_class.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "initial"
        ):
            assignments.append(node.value)
            accepted_store_ids.add(id(node.targets[0]))
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "initial"
            and node.value is not None
        ):
            assignments.append(node.value)
            accepted_store_ids.add(id(node.target))

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "initial":
            if isinstance(node.ctx, (ast.Store, ast.Del)) and id(node) not in (
                accepted_store_ids
            ):
                return _AMBIGUOUS
        elif isinstance(node, ast.Name) and node.id == "Migration":
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                return _AMBIGUOUS
        elif isinstance(node, ast.Attribute) and node.attr == "initial":
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                return _AMBIGUOUS
        elif isinstance(node, ast.ExceptHandler) and node.name == "initial":
            return _AMBIGUOUS
        elif isinstance(node, (ast.Global, ast.Nonlocal)) and "initial" in node.names:
            return _AMBIGUOUS
        elif isinstance(node, ast.arg) and node.arg == "initial":
            return _AMBIGUOUS
        elif isinstance(node, ast.alias) and (
            node.name == "initial" or node.asname == "initial"
        ):
            return _AMBIGUOUS
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "initial":
                return _AMBIGUOUS
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name == "initial":
            return _AMBIGUOUS
        elif isinstance(node, ast.Call):
            called_name = None
            if isinstance(node.func, ast.Name):
                called_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                called_name = node.func.attr
            if called_name in {"setattr", "delattr", "exec", "eval"}:
                return _AMBIGUOUS

    if not assignments:
        return _MISSING
    if len(assignments) != 1:
        return _AMBIGUOUS
    try:
        return ast.literal_eval(assignments[0])
    except ValueError, TypeError:
        return _NON_LITERAL


def _string_assignment(class_node: ast.ClassDef, attribute: str) -> str | None:
    """Return a literal class assignment, or ``None`` when it is absent."""
    for node in class_node.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == attribute
            for target in node.targets
        ):
            continue
        try:
            value = ast.literal_eval(node.value)
        except ValueError, TypeError:
            return None
        return value if isinstance(value, str) else None
    return None


def _parse_app_config(apps_path: Path) -> ModuleAppConfigIdentity | None:
    """Bind the sole explicit AppConfig ``name`` and ``label`` assignments."""
    tree = ast.parse(apps_path.read_text(), filename=str(apps_path))
    candidates: list[ModuleAppConfigIdentity] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        is_app_config = any(
            (isinstance(base, ast.Name) and base.id == "AppConfig")
            or (isinstance(base, ast.Attribute) and base.attr == "AppConfig")
            for base in node.bases
        )
        if not is_app_config:
            continue
        name = _string_assignment(node, "name")
        label = _string_assignment(node, "label")
        if name is not None and label is not None:
            candidates.append(ModuleAppConfigIdentity(name=name, label=label))

    return candidates[0] if len(candidates) == 1 else None


def _module_package_path(module_name: str, module_path: Path) -> Path:
    """Return the source package directory for a discovered module root."""
    return module_path / "src" / f"quickscale_modules_{module_name}"


def _migration_topology_diagnostics(
    module_paths: Mapping[str, Path], names: tuple[str, ...]
) -> list[TopologyDiagnostic]:
    """Classify every discovered module and aggregate all actionable defects."""
    diagnostics: list[TopologyDiagnostic] = []
    for module_name in names:
        module_path = module_paths.get(module_name)
        if module_path is None or not module_path.is_dir():
            diagnostics.append(
                TopologyDiagnostic(
                    module_name,
                    "missing-module",
                    "discovered module root or source module is missing",
                )
            )
            continue

        package_path = _module_package_path(module_name, module_path)
        models_path = package_path / "models.py"
        migrations_path = package_path / "migrations"
        if not package_path.is_dir():
            diagnostics.append(
                TopologyDiagnostic(
                    module_name,
                    "missing-module",
                    f"source package is missing: {package_path}",
                )
            )
            continue

        if not models_path.is_file():
            if migrations_path.exists():
                if not migrations_path.is_dir():
                    diagnostics.append(
                        TopologyDiagnostic(
                            module_name,
                            "unexpected-service-migration",
                            "service-style module has a non-directory migrations path",
                        )
                    )
                    continue
                migration_files = sorted(
                    path.name
                    for path in migrations_path.iterdir()
                    if path.is_file() and path.suffix == ".py"
                )
                diagnostics.append(
                    TopologyDiagnostic(
                        module_name,
                        "unexpected-service-migration",
                        "service-style module must not have migrations; found "
                        + (", ".join(migration_files) or "a migrations directory"),
                    )
                )
            continue

        if not migrations_path.is_dir():
            diagnostics.append(
                TopologyDiagnostic(
                    module_name,
                    "missing-initial",
                    "model-bearing module is missing migrations/0001_initial.py",
                )
            )
            continue

        migration_files = sorted(
            path.name
            for path in migrations_path.iterdir()
            if path.is_file() and path.suffix == ".py"
        )
        expected_files = {_MIGRATIONS_INIT_FILENAME, _INITIAL_MIGRATION_FILENAME}
        actual_files = set(migration_files)
        if _INITIAL_MIGRATION_FILENAME not in actual_files:
            diagnostics.append(
                TopologyDiagnostic(
                    module_name,
                    "missing-initial",
                    "model-bearing module is missing migrations/0001_initial.py",
                )
            )

        extra_numbered = sorted(
            filename
            for filename in actual_files - expected_files
            if _NUMBERED_MIGRATION_PATTERN.match(filename)
        )
        if extra_numbered:
            diagnostics.append(
                TopologyDiagnostic(
                    module_name,
                    "extra-numbered-migration",
                    "exact-ten topology permits no numbered migrations beyond "
                    f"0001_initial.py; found {', '.join(extra_numbered)}",
                )
            )

        unexpected_files = sorted(actual_files - expected_files - set(extra_numbered))
        if unexpected_files:
            diagnostics.append(
                TopologyDiagnostic(
                    module_name,
                    "unexpected-migration-file",
                    "migration Python files must be exactly __init__.py and "
                    f"0001_initial.py; found {', '.join(unexpected_files)}",
                )
            )
        missing_files = sorted(expected_files - actual_files)
        if missing_files:
            diagnostics.append(
                TopologyDiagnostic(
                    module_name,
                    "incomplete-migration-package",
                    "migration Python files are missing " + ", ".join(missing_files),
                )
            )

        initial_path = migrations_path / _INITIAL_MIGRATION_FILENAME
        if initial_path.is_file():
            try:
                initial_flag = _read_initial_flag(initial_path)
            except (SyntaxError, TypeError, ValueError) as exc:
                diagnostics.append(
                    TopologyDiagnostic(
                        module_name,
                        "initial-load-error",
                        f"could not load Migration.initial: {exc}",
                    )
                )
            else:
                if initial_flag is not True:
                    if initial_flag is _MISSING:
                        rendered_flag = "absent"
                    elif initial_flag is _AMBIGUOUS:
                        rendered_flag = (
                            "ambiguous Migration class or initial assignment"
                        )
                    elif initial_flag is _NON_LITERAL:
                        rendered_flag = "non-literal expression"
                    else:
                        rendered_flag = repr(initial_flag)
                    diagnostics.append(
                        TopologyDiagnostic(
                            module_name,
                            "wrong-initial-flag",
                            "Migration.initial must be exactly True; found "
                            + rendered_flag,
                        )
                    )

    return diagnostics


def _bind_module_inventory() -> ModuleInventory:
    """Bind names, source roots, AppConfigs, and model/service classification."""
    names = tuple(authoritative_module_names())
    paths = discover_shipped_module_paths()
    app_configs: dict[str, ModuleAppConfigIdentity] = {}
    diagnostics: list[str] = []
    if set(paths) != set(names):
        diagnostics.append(
            "Canonical names and discovered source paths differ: "
            f"names={sorted(names)}, paths={sorted(paths)}"
        )

    for module_name in names:
        module_path = paths.get(module_name)
        if module_path is None:
            diagnostics.append(f"{module_name}: missing discovered source path")
            continue
        apps_path = _module_package_path(module_name, module_path) / "apps.py"
        identity = _parse_app_config(apps_path) if apps_path.is_file() else None
        if identity is None:
            diagnostics.append(
                f"{module_name}: apps.py must bind exactly one AppConfig name and label"
            )
        else:
            app_configs[module_name] = identity

    model_modules = tuple(
        module_name
        for module_name in names
        if module_name in paths
        and (
            _module_package_path(module_name, paths[module_name]) / "models.py"
        ).is_file()
    )
    service_modules = tuple(
        module_name for module_name in names if module_name not in model_modules
    )
    diagnostics.extend(
        str(diagnostic) for diagnostic in _migration_topology_diagnostics(paths, names)
    )
    if diagnostics:
        raise AssertionError(
            "Module inventory binding failed:\n" + "\n".join(diagnostics)
        )

    return ModuleInventory(
        names=names,
        paths=paths,
        app_configs=app_configs,
        model_modules=model_modules,
        service_modules=service_modules,
    )


def _copy_module_tree(
    tmp_path: Path, inventory: ModuleInventory, module_name: str
) -> Path:
    """Copy one source tree so a canary mutates only temporary evidence."""
    copied_path = tmp_path / module_name
    shutil.copytree(inventory.paths[module_name], copied_path)
    return copied_path


def _assert_canary_detected(
    module_name: str,
    module_path: Path,
    expected_code: str,
) -> None:
    diagnostics = _migration_topology_diagnostics(
        {module_name: module_path}, (module_name,)
    )
    assert any(diagnostic.code == expected_code for diagnostic in diagnostics), (
        f"Canary for {expected_code!r} was not detected:\n"
        + "\n".join(map(str, diagnostics))
    )


def test_repository_module_migration_topology() -> None:
    """Enforce the source-derived twelve-module, exact-ten topology."""
    inventory = _bind_module_inventory()

    assert set(inventory.paths) == set(inventory.names), (
        "Canonical names and discovered source paths differ: "
        f"names={sorted(inventory.names)}, paths={sorted(inventory.paths)}"
    )
    assert len(inventory.names) == 12
    assert len(inventory.model_modules) == EXPECTED_MODEL_MODULE_COUNT
    assert len(inventory.service_modules) == 2
    assert "analytics" in inventory.service_modules
    assert "storage" in inventory.service_modules
    assert "teams" not in inventory.names
    assert "teams" in PLACEHOLDER_MODULE_NAMES
    assert is_placeholder_module("teams")

    assert len(inventory.app_configs) == len(inventory.names)
    for module_name, identity in inventory.app_configs.items():
        expected_identity = f"quickscale_modules_{module_name}"
        assert identity.name == expected_identity
        assert identity.label == expected_identity


def test_missing_initial_migration_canary(tmp_path: Path) -> None:
    """A model module without 0001_initial.py must fail closed."""
    inventory = _bind_module_inventory()
    module_name = inventory.model_modules[0]
    module_path = _copy_module_tree(tmp_path, inventory, module_name)
    (
        module_path
        / "src"
        / f"quickscale_modules_{module_name}"
        / "migrations"
        / _INITIAL_MIGRATION_FILENAME
    ).unlink()

    _assert_canary_detected(module_name, module_path, "missing-initial")


def test_extra_numbered_migration_canary(tmp_path: Path) -> None:
    """A model module with 0002 must fail the exact-ten guard."""
    inventory = _bind_module_inventory()
    module_name = inventory.model_modules[0]
    module_path = _copy_module_tree(tmp_path, inventory, module_name)
    migrations_path = (
        module_path / "src" / f"quickscale_modules_{module_name}" / "migrations"
    )
    (migrations_path / "0002_auto.py").write_text("# injected canary\n")

    _assert_canary_detected(module_name, module_path, "extra-numbered-migration")


def test_renamed_non_initial_migration_canary(tmp_path: Path) -> None:
    """A lone renamed 0001 file must not satisfy the initial contract."""
    inventory = _bind_module_inventory()
    module_name = inventory.model_modules[0]
    module_path = _copy_module_tree(tmp_path, inventory, module_name)
    migrations_path = (
        module_path / "src" / f"quickscale_modules_{module_name}" / "migrations"
    )
    (migrations_path / _INITIAL_MIGRATION_FILENAME).rename(
        migrations_path / "0001_renamed.py"
    )

    _assert_canary_detected(module_name, module_path, "missing-initial")


@pytest.mark.parametrize(
    "initial_replacement", ["initial = False", "# initial removed"]
)
def test_wrong_initial_flag_canaries(tmp_path: Path, initial_replacement: str) -> None:
    """False and absent Migration.initial flags must both fail closed."""
    inventory = _bind_module_inventory()
    module_name = inventory.model_modules[0]
    module_path = _copy_module_tree(tmp_path, inventory, module_name)
    initial_path = (
        module_path
        / "src"
        / f"quickscale_modules_{module_name}"
        / "migrations"
        / _INITIAL_MIGRATION_FILENAME
    )
    content = initial_path.read_text()
    assert "initial = True" in content
    initial_path.write_text(content.replace("initial = True", initial_replacement, 1))

    _assert_canary_detected(module_name, module_path, "wrong-initial-flag")


def test_non_literal_initial_flag_is_rejected_without_execution(
    tmp_path: Path,
) -> None:
    """A non-literal initial flag must fail without running its expression."""
    inventory = _bind_module_inventory()
    module_name = inventory.model_modules[0]
    module_path = _copy_module_tree(tmp_path, inventory, module_name)
    initial_path = (
        module_path
        / "src"
        / f"quickscale_modules_{module_name}"
        / "migrations"
        / _INITIAL_MIGRATION_FILENAME
    )
    side_effect_path = tmp_path / "migration-class-side-effect"
    replacement = (
        "initial = __builtins__['open']"
        f"({str(side_effect_path)!r}, 'w').write('executed')"
    )
    content = initial_path.read_text()
    assert "initial = True" in content
    initial_path.write_text(content.replace("initial = True", replacement, 1))

    _assert_canary_detected(module_name, module_path, "wrong-initial-flag")
    assert not side_effect_path.exists()


def test_post_class_initial_rebinding_canary(tmp_path: Path) -> None:
    """A post-class ``Migration.initial`` write must fail closed."""
    inventory = _bind_module_inventory()
    module_name = inventory.model_modules[0]
    module_path = _copy_module_tree(tmp_path, inventory, module_name)
    initial_path = (
        module_path
        / "src"
        / f"quickscale_modules_{module_name}"
        / "migrations"
        / _INITIAL_MIGRATION_FILENAME
    )
    initial_path.write_text(initial_path.read_text() + "\nMigration.initial = False\n")

    _assert_canary_detected(module_name, module_path, "wrong-initial-flag")


def test_nested_class_initial_rebinding_canary(tmp_path: Path) -> None:
    """A nested class-body ``initial`` write must fail closed."""
    inventory = _bind_module_inventory()
    module_name = inventory.model_modules[0]
    module_path = _copy_module_tree(tmp_path, inventory, module_name)
    initial_path = (
        module_path
        / "src"
        / f"quickscale_modules_{module_name}"
        / "migrations"
        / _INITIAL_MIGRATION_FILENAME
    )
    content = initial_path.read_text()
    assert "    initial = True" in content
    initial_path.write_text(
        content.replace(
            "    initial = True",
            "    initial = True\n\n    class NestedMigration:\n        initial = False",
            1,
        )
    )

    _assert_canary_detected(module_name, module_path, "wrong-initial-flag")


@pytest.mark.parametrize(
    "rebind",
    [
        "for initial in ():\n    pass",
        "def mutate():\n    initial = False",
        "setattr(Migration, 'initial', False)",
    ],
)
def test_other_initial_write_forms_fail_closed(tmp_path: Path, rebind: str) -> None:
    """Unmodelled direct and indirect AST writes must not false-green."""
    inventory = _bind_module_inventory()
    module_name = inventory.model_modules[0]
    module_path = _copy_module_tree(tmp_path, inventory, module_name)
    initial_path = (
        module_path
        / "src"
        / f"quickscale_modules_{module_name}"
        / "migrations"
        / _INITIAL_MIGRATION_FILENAME
    )
    initial_path.write_text(initial_path.read_text() + f"\n{rebind}\n")

    _assert_canary_detected(module_name, module_path, "wrong-initial-flag")


def test_service_module_gaining_migrations_canary(tmp_path: Path) -> None:
    """A service-style module must fail if a migrations package appears."""
    inventory = _bind_module_inventory()
    module_name = inventory.service_modules[0]
    module_path = _copy_module_tree(tmp_path, inventory, module_name)
    migrations_path = (
        module_path / "src" / f"quickscale_modules_{module_name}" / "migrations"
    )
    migrations_path.mkdir()
    (migrations_path / _MIGRATIONS_INIT_FILENAME).write_text("")

    _assert_canary_detected(module_name, module_path, "unexpected-service-migration")
