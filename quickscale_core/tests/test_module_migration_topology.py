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
_DIAGNOSTIC_MISSING_MODULE = "missing-module"
_DIAGNOSTIC_UNEXPECTED_SERVICE_MIGRATION = "unexpected-service-migration"
_DIAGNOSTIC_AMBIGUOUS_MODEL_DEFINITION = "ambiguous-model-definition"
_DIAGNOSTIC_INVALID_MODEL_DEFINITION = "invalid-model-definition"
_DIAGNOSTIC_MISSING_INITIAL = "missing-initial"
_DIAGNOSTIC_EXTRA_NUMBERED_MIGRATION = "extra-numbered-migration"
_DIAGNOSTIC_UNEXPECTED_MIGRATION_FILE = "unexpected-migration-file"
_DIAGNOSTIC_INCOMPLETE_MIGRATION_PACKAGE = "incomplete-migration-package"
_DIAGNOSTIC_INITIAL_LOAD_ERROR = "initial-load-error"
_DIAGNOSTIC_WRONG_INITIAL_FLAG = "wrong-initial-flag"
_MISSING = object()
_AMBIGUOUS = object()
_NON_LITERAL = object()
_INDIRECT_REBINDING_NAMES = frozenset(
    {
        "__delattr__",
        "__setattr__",
        "delattr",
        "eval",
        "exec",
        "getattr",
        "globals",
        "locals",
        "setattr",
        "vars",
    }
)
_APP_CONFIG_INDIRECT_REBINDING_NAMES = frozenset(
    {
        "__delattr__",
        "__setattr__",
        "delattr",
        "eval",
        "exec",
        "globals",
        "locals",
        "setattr",
        "vars",
    }
)


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
    if migration_class.decorator_list or migration_class.keywords:
        return _AMBIGUOUS

    migration_bindings = [
        (node, alias)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
        if (alias.asname or alias.name.split(".", 1)[0]) == "migrations"
    ]
    if len(migration_bindings) != 1:
        return _AMBIGUOUS
    import_node, imported_name = migration_bindings[0]
    if not (
        isinstance(import_node, ast.ImportFrom)
        and import_node in tree.body
        and import_node.level == 0
        and import_node.module == "django.db"
        and imported_name.name == "migrations"
        and imported_name.asname is None
        and tree.body.index(import_node) < tree.body.index(migration_class)
    ):
        return _AMBIGUOUS
    if not (
        len(migration_class.bases) == 1
        and isinstance(migration_class.bases[0], ast.Attribute)
        and isinstance(migration_class.bases[0].value, ast.Name)
        and migration_class.bases[0].value.id == "migrations"
        and migration_class.bases[0].attr == "Migration"
    ):
        return _AMBIGUOUS

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

    for ast_node in ast.walk(tree):
        if isinstance(ast_node, ast.Name) and ast_node.id == "initial":
            if isinstance(ast_node.ctx, (ast.Store, ast.Del)) and id(ast_node) not in (
                accepted_store_ids
            ):
                return _AMBIGUOUS
        elif isinstance(ast_node, ast.Name) and ast_node.id == "migrations":
            if isinstance(ast_node.ctx, (ast.Store, ast.Del)):
                return _AMBIGUOUS
        elif isinstance(ast_node, ast.Name):
            if ast_node.id == "Migration" or ast_node.id in _INDIRECT_REBINDING_NAMES:
                return _AMBIGUOUS
        elif isinstance(ast_node, ast.Attribute):
            if (
                ast_node.attr in {"initial", "Migration", "migrations"}
                and isinstance(ast_node.ctx, (ast.Store, ast.Del))
            ) or ast_node.attr in _INDIRECT_REBINDING_NAMES:
                return _AMBIGUOUS
        elif isinstance(ast_node, ast.Subscript) and isinstance(
            ast_node.ctx, (ast.Store, ast.Del)
        ):
            return _AMBIGUOUS
        elif isinstance(ast_node, ast.ExceptHandler) and ast_node.name in {
            "initial",
            "migrations",
        }:
            return _AMBIGUOUS
        elif isinstance(ast_node, (ast.Global, ast.Nonlocal)) and any(
            name in {"initial", "migrations"} for name in ast_node.names
        ):
            return _AMBIGUOUS
        elif isinstance(ast_node, ast.arg) and ast_node.arg in {
            "initial",
            "migrations",
        }:
            return _AMBIGUOUS
        elif isinstance(ast_node, ast.alias):
            if (
                ast_node.name in {"initial", "Migration"}
                or ast_node.asname in {"initial", "Migration"}
                or ast_node.name in _INDIRECT_REBINDING_NAMES
                or ast_node.asname in _INDIRECT_REBINDING_NAMES
            ):
                return _AMBIGUOUS
        elif isinstance(
            ast_node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            if ast_node.name in {"initial", "migrations"}:
                return _AMBIGUOUS
        elif isinstance(ast_node, (ast.MatchAs, ast.MatchStar)) and ast_node.name in {
            "initial",
            "migrations",
        }:
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
    """Return one direct literal class assignment, or ``None`` when invalid."""
    assignments: list[str] = []
    for node in class_node.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == attribute
        ):
            return None
        if not isinstance(node, ast.Assign):
            continue
        matching_targets = [
            target
            for target in node.targets
            if isinstance(target, ast.Name) and target.id == attribute
        ]
        if not matching_targets:
            continue
        if len(node.targets) != 1:
            return None
        try:
            value = ast.literal_eval(node.value)
        except ValueError, TypeError:
            return None
        if not isinstance(value, str):
            return None
        assignments.append(value)
    if len(assignments) != 1:
        return None
    return assignments[0]


def _parse_app_config(apps_path: Path) -> ModuleAppConfigIdentity | None:
    """Bind the sole explicit AppConfig ``name`` and ``label`` assignments."""
    tree = ast.parse(apps_path.read_text(), filename=str(apps_path))
    candidate_classes: list[ast.ClassDef] = []
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
        candidate_classes.append(node)

    if len(candidate_classes) != 1:
        return None

    candidate = candidate_classes[0]
    name = _string_assignment(candidate, "name")
    label = _string_assignment(candidate, "label")
    if name is None or label is None:
        return None

    for ast_node in ast.walk(tree):
        if (
            isinstance(ast_node, ast.Name)
            and ast_node.id in _APP_CONFIG_INDIRECT_REBINDING_NAMES
        ):
            return None
        if isinstance(ast_node, ast.alias) and (
            ast_node.name in _APP_CONFIG_INDIRECT_REBINDING_NAMES
            or ast_node.asname in _APP_CONFIG_INDIRECT_REBINDING_NAMES
        ):
            return None
        if (
            isinstance(ast_node, ast.Attribute)
            and ast_node.attr in _APP_CONFIG_INDIRECT_REBINDING_NAMES
        ):
            return None
        if (
            isinstance(ast_node, ast.Call)
            and isinstance(ast_node.func, ast.Name)
            and ast_node.func.id == "getattr"
            and len(ast_node.args) >= 2
            and isinstance(ast_node.args[1], ast.Constant)
            and ast_node.args[1].value in {"__delattr__", "__setattr__"}
        ):
            return None
        if (
            isinstance(ast_node, ast.Attribute)
            and ast_node.attr in {"name", "label"}
            and isinstance(ast_node.ctx, (ast.Store, ast.Del))
            and isinstance(ast_node.value, ast.Name)
            and ast_node.value.id == candidate.name
        ):
            return None
        if isinstance(ast_node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in {"name", "label"}
            for target in ast_node.targets
        ):
            if ast_node not in candidate.body:
                return None

    return ModuleAppConfigIdentity(name=name, label=label)


def _model_definition_kind(package_path: Path) -> str:
    """Classify the importable model form without importing module source."""
    models_file = package_path / "models.py"
    models_path = package_path / "models"
    models_package_init = models_path / _MIGRATIONS_INIT_FILENAME

    if models_file.is_file() and models_package_init.is_file():
        return "ambiguous"
    if models_file.is_file() and not models_path.exists():
        return "file"
    if (
        models_package_init.is_file()
        and models_path.is_dir()
        and not models_file.exists()
    ):
        return "package"
    if models_file.exists() or models_path.exists():
        return "invalid"
    return "service"


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
                    _DIAGNOSTIC_MISSING_MODULE,
                    "discovered module root or source module is missing",
                )
            )
            continue

        package_path = _module_package_path(module_name, module_path)
        model_definition = _model_definition_kind(package_path)
        migrations_path = package_path / "migrations"
        if not package_path.is_dir():
            diagnostics.append(
                TopologyDiagnostic(
                    module_name,
                    _DIAGNOSTIC_MISSING_MODULE,
                    f"source package is missing: {package_path}",
                )
            )
            continue

        if model_definition == "ambiguous":
            diagnostics.append(
                TopologyDiagnostic(
                    module_name,
                    _DIAGNOSTIC_AMBIGUOUS_MODEL_DEFINITION,
                    "model-bearing module must use exactly one of models.py or "
                    "models/__init__.py",
                )
            )
            continue
        if model_definition == "invalid":
            diagnostics.append(
                TopologyDiagnostic(
                    module_name,
                    _DIAGNOSTIC_INVALID_MODEL_DEFINITION,
                    "models definition must be models.py or importable "
                    "models/__init__.py",
                )
            )
            continue

        if model_definition == "service":
            if migrations_path.exists():
                if not migrations_path.is_dir():
                    diagnostics.append(
                        TopologyDiagnostic(
                            module_name,
                            _DIAGNOSTIC_UNEXPECTED_SERVICE_MIGRATION,
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
                        _DIAGNOSTIC_UNEXPECTED_SERVICE_MIGRATION,
                        "service-style module must not have migrations; found "
                        + (", ".join(migration_files) or "a migrations directory"),
                    )
                )
            continue

        if not migrations_path.is_dir():
            diagnostics.append(
                TopologyDiagnostic(
                    module_name,
                    _DIAGNOSTIC_MISSING_INITIAL,
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
                    _DIAGNOSTIC_MISSING_INITIAL,
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
                    _DIAGNOSTIC_EXTRA_NUMBERED_MIGRATION,
                    "exact-ten topology permits no numbered migrations beyond "
                    f"0001_initial.py; found {', '.join(extra_numbered)}",
                )
            )

        unexpected_files = sorted(actual_files - expected_files - set(extra_numbered))
        if unexpected_files:
            diagnostics.append(
                TopologyDiagnostic(
                    module_name,
                    _DIAGNOSTIC_UNEXPECTED_MIGRATION_FILE,
                    "migration Python files must be exactly __init__.py and "
                    f"0001_initial.py; found {', '.join(unexpected_files)}",
                )
            )
        missing_files = sorted(expected_files - actual_files)
        if missing_files:
            diagnostics.append(
                TopologyDiagnostic(
                    module_name,
                    _DIAGNOSTIC_INCOMPLETE_MIGRATION_PACKAGE,
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
                        _DIAGNOSTIC_INITIAL_LOAD_ERROR,
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
                            _DIAGNOSTIC_WRONG_INITIAL_FLAG,
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
        and _model_definition_kind(
            _module_package_path(module_name, paths[module_name])
        )
        in {"file", "package"}
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

    _assert_canary_detected(module_name, module_path, _DIAGNOSTIC_MISSING_INITIAL)


def test_package_form_missing_initial_migration_canary(tmp_path: Path) -> None:
    """An importable models package still requires 0001_initial.py."""
    inventory = _bind_module_inventory()
    module_name = inventory.model_modules[0]
    module_path = _copy_module_tree(tmp_path, inventory, module_name)
    package_path = module_path / "src" / f"quickscale_modules_{module_name}"
    models_file = package_path / "models.py"
    models_package = package_path / "models"
    models_package.mkdir()
    models_file.rename(models_package / _MIGRATIONS_INIT_FILENAME)
    (package_path / "migrations" / _INITIAL_MIGRATION_FILENAME).unlink()

    _assert_canary_detected(module_name, module_path, _DIAGNOSTIC_MISSING_INITIAL)


def test_dual_model_definition_canary(tmp_path: Path) -> None:
    """A module cannot expose both models.py and models/__init__.py."""
    inventory = _bind_module_inventory()
    module_name = inventory.model_modules[0]
    module_path = _copy_module_tree(tmp_path, inventory, module_name)
    models_package = (
        module_path / "src" / f"quickscale_modules_{module_name}" / "models"
    )
    models_package.mkdir()
    (models_package / _MIGRATIONS_INIT_FILENAME).write_text("")

    _assert_canary_detected(
        module_name, module_path, _DIAGNOSTIC_AMBIGUOUS_MODEL_DEFINITION
    )


def test_irregular_model_definition_canary(tmp_path: Path) -> None:
    """An unimportable models directory must not become service-style."""
    inventory = _bind_module_inventory()
    module_name = inventory.model_modules[0]
    module_path = _copy_module_tree(tmp_path, inventory, module_name)
    package_path = module_path / "src" / f"quickscale_modules_{module_name}"
    (package_path / "models").mkdir()
    (package_path / "models.py").unlink()

    _assert_canary_detected(
        module_name, module_path, _DIAGNOSTIC_INVALID_MODEL_DEFINITION
    )


def test_extra_numbered_migration_canary(tmp_path: Path) -> None:
    """A model module with 0002 must fail the exact-ten guard."""
    inventory = _bind_module_inventory()
    module_name = inventory.model_modules[0]
    module_path = _copy_module_tree(tmp_path, inventory, module_name)
    migrations_path = (
        module_path / "src" / f"quickscale_modules_{module_name}" / "migrations"
    )
    (migrations_path / "0002_auto.py").write_text("# injected canary\n")

    _assert_canary_detected(
        module_name, module_path, _DIAGNOSTIC_EXTRA_NUMBERED_MIGRATION
    )


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

    _assert_canary_detected(module_name, module_path, _DIAGNOSTIC_MISSING_INITIAL)


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

    _assert_canary_detected(module_name, module_path, _DIAGNOSTIC_WRONG_INITIAL_FLAG)


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

    _assert_canary_detected(module_name, module_path, _DIAGNOSTIC_WRONG_INITIAL_FLAG)
    assert not side_effect_path.exists()


def test_migrations_attribute_rebinding_is_rejected_without_execution(
    tmp_path: Path,
) -> None:
    """A migrations attribute rebinding must not execute its right-hand side."""
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
    side_effect_path = tmp_path / "migrations-rebinding-side-effect"
    initial_path.write_text(
        initial_path.read_text()
        + "\nimport sys\n"
        + "sys.modules[__name__].migrations = __builtins__['open']"
        + f"({str(side_effect_path)!r}, 'w').write('executed')\n"
    )

    _assert_canary_detected(module_name, module_path, _DIAGNOSTIC_WRONG_INITIAL_FLAG)
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

    _assert_canary_detected(module_name, module_path, _DIAGNOSTIC_WRONG_INITIAL_FLAG)


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

    _assert_canary_detected(module_name, module_path, _DIAGNOSTIC_WRONG_INITIAL_FLAG)


@pytest.mark.parametrize(
    "class_replacement",
    [
        "@(lambda cls: cls)\nclass Migration(migrations.Migration):",
        "class Migration(migrations.Migration, object):",
        "class Migration(migrations.Migration, metaclass=type):",
    ],
)
def test_noncanonical_migration_class_forms_fail_closed(
    tmp_path: Path, class_replacement: str
) -> None:
    """Decorated, multi-base, and metaclass forms must not false-green."""
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
    canonical_class = "class Migration(migrations.Migration):"
    assert canonical_class in content
    initial_path.write_text(content.replace(canonical_class, class_replacement, 1))

    _assert_canary_detected(module_name, module_path, _DIAGNOSTIC_WRONG_INITIAL_FLAG)


@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        (
            "from django.db import migrations, models",
            "from django.db import models\nfrom types import SimpleNamespace as migrations",
        ),
        (
            "class Migration(migrations.Migration):",
            "migrations = object\n\nclass Migration(migrations.Migration):",
        ),
    ],
)
def test_noncanonical_migration_base_bindings_fail_closed(
    tmp_path: Path, original: str, replacement: str
) -> None:
    """Spoofed or rebound migration-base names must not false-green."""
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
    assert original in content
    initial_path.write_text(content.replace(original, replacement, 1))

    _assert_canary_detected(module_name, module_path, _DIAGNOSTIC_WRONG_INITIAL_FLAG)


@pytest.mark.parametrize(
    "rebind",
    [
        "for initial in ():\n    pass",
        "def mutate():\n    initial = False",
        "setattr(Migration, 'initial', False)",
        "mutator = setattr\nmutator(Migration, 'initial', False)",
        "type.__setattr__(Migration, 'initial', False)",
        "mutator = getattr(type, '__setattr__')\nmutator(Migration, 'initial', False)",
        "Migration = object",
        "globals()['Migration'] = object",
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

    _assert_canary_detected(module_name, module_path, _DIAGNOSTIC_WRONG_INITIAL_FLAG)


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

    _assert_canary_detected(
        module_name, module_path, _DIAGNOSTIC_UNEXPECTED_SERVICE_MIGRATION
    )


def _app_config_class_name(apps_path: Path) -> str:
    """Return the sole AppConfig candidate name for a temporary canary."""
    tree = ast.parse(apps_path.read_text(), filename=str(apps_path))
    candidates = [
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(
            (isinstance(base, ast.Name) and base.id == "AppConfig")
            or (isinstance(base, ast.Attribute) and base.attr == "AppConfig")
            for base in node.bases
        )
    ]
    assert len(candidates) == 1
    return candidates[0]


def _copy_apps_file(tmp_path: Path, inventory: ModuleInventory) -> Path:
    """Copy one module's apps.py for parser-only AppConfig canaries."""
    module_name = inventory.names[0]
    source = _module_package_path(module_name, inventory.paths[module_name]) / "apps.py"
    apps_path = tmp_path / "apps.py"
    shutil.copyfile(source, apps_path)
    return apps_path


def test_duplicate_app_config_class_canary(tmp_path: Path) -> None:
    """Multiple AppConfig candidates must not produce an identity."""
    inventory = _bind_module_inventory()
    apps_path = _copy_apps_file(tmp_path, inventory)
    content = apps_path.read_text()
    content += (
        "\n\nclass DuplicateConfig(AppConfig):\n"
        "    name = 'duplicate'\n"
        "    label = 'duplicate'\n"
    )
    apps_path.write_text(content)

    assert _parse_app_config(apps_path) is None


def test_duplicate_app_config_assignment_canary(tmp_path: Path) -> None:
    """Duplicate direct AppConfig identity assignments must fail closed."""
    inventory = _bind_module_inventory()
    apps_path = _copy_apps_file(tmp_path, inventory)
    content = apps_path.read_text()
    name_line = next(
        line for line in content.splitlines() if line.startswith("    name =")
    )
    apps_path.write_text(content.replace(name_line, name_line + "\n" + name_line, 1))

    assert _parse_app_config(apps_path) is None


def test_post_class_app_config_write_canary(tmp_path: Path) -> None:
    """A post-class direct identity write must fail closed."""
    inventory = _bind_module_inventory()
    apps_path = _copy_apps_file(tmp_path, inventory)
    class_name = _app_config_class_name(apps_path)
    apps_path.write_text(apps_path.read_text() + f"\n{class_name}.name = 'spoofed'\n")

    assert _parse_app_config(apps_path) is None


@pytest.mark.parametrize("indirect_write", ["setattr", "aliased_setattr"])
def test_indirect_app_config_write_canaries(
    tmp_path: Path, indirect_write: str
) -> None:
    """Direct and aliased indirect identity writes must fail closed."""
    inventory = _bind_module_inventory()
    apps_path = _copy_apps_file(tmp_path, inventory)
    class_name = _app_config_class_name(apps_path)
    if indirect_write == "setattr":
        suffix = f"\nsetattr({class_name}, 'label', 'spoofed')\n"
    else:
        suffix = f"\nmutator = setattr\nmutator({class_name}, 'label', 'spoofed')\n"
    apps_path.write_text(apps_path.read_text() + suffix)

    assert _parse_app_config(apps_path) is None
