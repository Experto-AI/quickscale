"""
Parity controls for the ``core`` split (SA268).

The corpus loader, its authority errors, and the manifest readers moved to the
private sibling ``_core_corpus``; the shared AST helpers moved to
``_core_ast``.  The ``core`` facade keeps the module-name tables rule 37
exempts and re-exports every moved name.  These controls pin the facade's
preserved surface, the split's structural invariants, and the exact authority
findings captured from the pre-split module, so a later slice cannot silently
drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from scripts import check_module_conventions as checker
from scripts.module_conventions import (
    _core_ast,
    _core_corpus,
    core,
    registry,
    rules_settings,
)
from scripts.module_conventions.rules_identity import RULE_37_ALLOWED_LITERAL_FILES

SPLIT_SIBLINGS = {
    "_core_ast": _core_ast,
    "_core_corpus": _core_corpus,
}

#: Every module-level name the pre-split ``core`` published, from its own
#: ``def``/``class``/assignment statements.  The facade must keep exposing
#: all of them, private helpers and the vocabulary tables included.
FROZEN_SURFACE = (
    "MODULES_DIR_NAME",
    "MANIFEST_NAME",
    "CORE_PACKAGE",
    "CLI_PACKAGE",
    "MYPY_INI_NAME",
    "MODULE_ABSTRACT_BASES",
    "ALLOWED_TEMPLATE_DIRS",
    "CREDENTIAL_REFERENCE_NAMES",
    "VENDOR_CREDENTIAL_DEFAULTS",
    "QUICKSCALE_ENV_VAR_DEFAULT_EXCEPTIONS",
    "ENV_VAR_NAME_PATTERN",
    "SETTING_NAME_EXCEPTIONS",
    "ORG_PUBLIC_SURFACE",
    "MODULE_LAYERS",
    "CAPABILITY_NAMES",
    "MODULE_REQUIRED_NAME",
    "_credential_reference_options",
    "_required_modules",
    "MODULE_IMPORT_PREFIX",
    "SNAKE_CASE",
    "GENERATOR_TEMPLATE_ROOT",
    "Skipped",
    "AuthorityError",
    "_DuplicateKeyYAMLError",
    "_StrictSafeLoader",
    "_construct_unique_mapping",
    "Module",
    "Corpus",
    "_display",
    "_read_tree",
    "_read_manifest",
    "load_corpus",
    "_parse",
    "_docstring_nodes",
    "_string_assignments",
    "_class_names",
    "_string_list",
    "_call_func_name",
    "_uses_name",
    "_keyword",
    "_literal",
    "_model_classes",
    "_meta_class",
    "_module_target",
    "_cross_module_imports",
    "_setting_name_module",
    "_settings_bindings",
    "_is_settings_receiver",
    "_settings_attribute_reads",
    "_declared_exports",
    "_service_module_bindings",
    "_attribute_chain",
    "_same_layer_cycles",
    "_bound_names",
    "_wiring_projection",
    "_projection_values",
    "_static_truth",
    "_import_package_parts",
    "_ancestors",
    "_declared_mounts",
    "_declared_url_mounts",
    "_body_nodes",
    "_scope_nodes",
)

#: The pre-split module's own imports, which it exposed as module attributes;
#: the facade keeps every one importable through its redundant aliases.
FROZEN_IMPORTED_BINDINGS = (
    "annotations",
    "ast",
    "os",
    "re",
    "stat",
    "Mapping",
    "dataclass",
    "Path",
    "Any",
    "cast",
    "yaml",
)

#: The pre-split module's wildcard-import surface: it declared no ``__all__``,
#: so ``from ... import *`` bound every public (non-underscore) module-level
#: name, the future-import binding included.
FROZEN_WILDCARD_SURFACE = (
    "ALLOWED_TEMPLATE_DIRS",
    "APP_CONFIG_WALK_SEAMS",
    "Any",
    "AuthorityError",
    "CAPABILITY_NAMES",
    "CLI_PACKAGE",
    "CORE_PACKAGE",
    "CREDENTIAL_REFERENCE_NAMES",
    "Corpus",
    "ENV_VAR_NAME_PATTERN",
    "GENERATOR_TEMPLATE_ROOT",
    "MANIFEST_NAME",
    "MODULES_DIR_NAME",
    "MODULE_ABSTRACT_BASES",
    "MODULE_IMPORT_PREFIX",
    "MODULE_LAYERS",
    "MODULE_REQUIRED_NAME",
    "MYPY_INI_NAME",
    "Mapping",
    "Module",
    "ORG_PUBLIC_SURFACE",
    "Path",
    "QUICKSCALE_ENV_VAR_DEFAULT_EXCEPTIONS",
    "SETTING_NAME_EXCEPTIONS",
    "SNAKE_CASE",
    "Skipped",
    "VENDOR_CREDENTIAL_DEFAULTS",
    "annotations",
    "ast",
    "cast",
    "dataclass",
    "load_corpus",
    "os",
    "re",
    "stat",
    "yaml",
)

#: The pre-split signature of every callable the pre-split module published.
FROZEN_SIGNATURES = {
    "_credential_reference_options": "(module: 'Module') -> 'set[str]'",
    "_required_modules": "(module: 'Module') -> 'frozenset[str]'",
    "_construct_unique_mapping": (
        "(loader: 'Any', node: 'Any', deep: 'bool' = False) -> 'dict[Any, Any]'"
    ),
    "_display": "(path: 'Path', root: 'Path') -> 'str'",
    "_read_tree": "(directory: 'Path', root: 'Path') -> 'dict[str, str]'",
    "_read_manifest": "(path: 'Path', root: 'Path') -> 'Mapping[str, Any]'",
    "load_corpus": "(repo_root: 'Path') -> 'Corpus'",
    "_parse": "(source: 'str') -> 'ast.Module'",
    "_docstring_nodes": "(tree: 'ast.Module') -> 'set[int]'",
    "_string_assignments": "(tree: 'ast.Module') -> 'dict[str, str]'",
    "_class_names": "(node: 'ast.ClassDef') -> 'list[str]'",
    "_string_list": "(tree: 'ast.Module') -> 'dict[str, list[str]]'",
    "_call_func_name": "(node: 'ast.Call') -> 'str'",
    "_uses_name": "(tree: 'ast.Module', name: 'str') -> 'bool'",
    "_keyword": "(node: 'ast.Call', name: 'str') -> 'ast.expr | None'",
    "_literal": "(node: 'ast.expr | None') -> 'Any'",
    "_model_classes": "(tree: 'ast.Module') -> 'list[ast.ClassDef]'",
    "_meta_class": "(node: 'ast.ClassDef') -> 'ast.ClassDef | None'",
    "_module_target": "(parts: 'tuple[str, ...]') -> 'tuple[str, tuple[str, ...]] | None'",
    "_cross_module_imports": (
        "(tree: 'ast.Module') -> 'list[tuple[str, tuple[str, ...], tuple[str, ...], int, str]]'"
    ),
    "_setting_name_module": "(attribute: 'str') -> 'str | None'",
    "_settings_bindings": "(tree: 'ast.Module') -> 'tuple[set[str], set[tuple[str, ...]]]'",
    "_is_settings_receiver": (
        "(node: 'ast.expr', names: 'set[str]', modules: 'set[tuple[str, ...]]') -> 'bool'"
    ),
    "_settings_attribute_reads": "(tree: 'ast.Module') -> 'list[tuple[str, int]]'",
    "_declared_exports": "(tree: 'ast.Module') -> 'list[str] | None'",
    "_service_module_bindings": "(tree: 'ast.Module') -> 'dict[tuple[str, ...], str]'",
    "_attribute_chain": "(node: 'ast.expr') -> 'tuple[str, ...] | None'",
    "_same_layer_cycles": "(edges: 'Mapping[str, set[str]]') -> 'list[list[str]]'",
    "_bound_names": "(target: 'ast.expr') -> 'set[str]'",
    "_wiring_projection": "(manifest: 'Mapping[str, Any]', field: 'str') -> 'list[Any]'",
    "_projection_values": "(expression: 'Any') -> 'list[Any]'",
    "_static_truth": "(node: 'ast.expr') -> 'bool | None'",
    "_import_package_parts": (
        "(node: 'ast.ImportFrom', module_name: 'str') -> 'tuple[str, ...] | None'"
    ),
    "_ancestors": (
        "(node: 'ast.ClassDef', classes: 'Mapping[str, ast.ClassDef]') -> 'list[ast.ClassDef]'"
    ),
    "_declared_mounts": "(module: 'Module') -> 'list[str]'",
    "_declared_url_mounts": "(module: 'Module') -> 'list[str]'",
    "_body_nodes": "(body: 'list[ast.stmt]') -> 'list[ast.AST]'",
    "_scope_nodes": "(node: 'ast.FunctionDef | ast.AsyncFunctionDef') -> 'list[ast.AST]'",
    "Module": (
        "(name: 'str', manifest: 'Mapping[str, Any]', files: 'Mapping[str, str]',"
        " root_files: 'Mapping[str, str]', tests: 'Mapping[str, str]', manifest_text:"
        " 'str' = '') -> None"
    ),
    "Corpus": (
        "(modules: 'tuple[Module, ...]', module_dir_names: 'tuple[str, ...]', core_files:"
        " 'Mapping[str, str]', cli_files: 'Mapping[str, str]', script_files: 'Mapping[str, str]',"
        " mypy_ini: 'str') -> None"
    ),
}

#: Each moved name's private sibling home; the facade re-exports the very
#: object its home defines.
FROZEN_HOMES = {
    "_core_corpus": (
        "MODULES_DIR_NAME",
        "MANIFEST_NAME",
        "CORE_PACKAGE",
        "CLI_PACKAGE",
        "MYPY_INI_NAME",
        "MODULE_REQUIRED_NAME",
        "Skipped",
        "AuthorityError",
        "_DuplicateKeyYAMLError",
        "_StrictSafeLoader",
        "_construct_unique_mapping",
        "Module",
        "Corpus",
        "_display",
        "_read_tree",
        "_read_manifest",
        "load_corpus",
        "_credential_reference_options",
        "_required_modules",
    ),
    "_core_ast": (
        "MODULE_ABSTRACT_BASES",
        "MODULE_IMPORT_PREFIX",
        "_parse",
        "_docstring_nodes",
        "_string_assignments",
        "_class_names",
        "_string_list",
        "_call_func_name",
        "_uses_name",
        "_keyword",
        "_literal",
        "_model_classes",
        "_meta_class",
        "_module_target",
        "_cross_module_imports",
        "_settings_bindings",
        "_is_settings_receiver",
        "_settings_attribute_reads",
        "_declared_exports",
        "_service_module_bindings",
        "_attribute_chain",
        "_same_layer_cycles",
        "_bound_names",
        "_wiring_projection",
        "_projection_values",
        "_static_truth",
        "_import_package_parts",
        "_ancestors",
        "_declared_mounts",
        "_declared_url_mounts",
        "_body_nodes",
        "_scope_nodes",
    ),
}

#: The module-level names the facade still defines itself, from its own
#: assignment statements.  The module-name tables rule 37 exempts here must
#: stay among them, and no other constant may be added without a deliberate
#: edit to this list.
FROZEN_FACADE_ASSIGNMENTS = (
    "ALLOWED_TEMPLATE_DIRS",
    "CREDENTIAL_REFERENCE_NAMES",
    "VENDOR_CREDENTIAL_DEFAULTS",
    "QUICKSCALE_ENV_VAR_DEFAULT_EXCEPTIONS",
    "ENV_VAR_NAME_PATTERN",
    "SETTING_NAME_EXCEPTIONS",
    "ORG_PUBLIC_SURFACE",
    "MODULE_LAYERS",
    "CAPABILITY_NAMES",
    "APP_CONFIG_WALK_SEAMS",
    "SNAKE_CASE",
    "GENERATOR_TEMPLATE_ROOT",
)

#: Rule 37's literal scan exempts only ``core.py`` in this family, so the
#: tables that carry module names must stay defined there.
RULE_37_MODULE_NAME_TABLES = (
    "SETTING_NAME_EXCEPTIONS",
    "VENDOR_CREDENTIAL_DEFAULTS",
    "QUICKSCALE_ENV_VAR_DEFAULT_EXCEPTIONS",
    "MODULE_LAYERS",
    "APP_CONFIG_WALK_SEAMS",
)

FROZEN_MODULE_LAYERS = {
    "orgs": 1,
    "auth": 1,
    "storage": 1,
    "notifications": 1,
    "analytics": 2,
    "backups": 2,
    "billing": 3,
    "blog": 3,
    "crm": 3,
    "forms": 3,
    "listings": 3,
    "social": 3,
}

FORBIDDEN_SIBLING_TARGETS = frozenset({"core", "registry", "check_module_conventions"})

#: Ordinary spellings that reach a facade or entrypoint of this package; each
#: must be rejected by :func:`_forbidden_imports`.
FORBIDDEN_IMPORT_SOURCES = (
    "from scripts.module_conventions import core",
    "from . import core",
    "from scripts.module_conventions.core import Module",
    "import scripts.module_conventions.core",
    "from scripts.module_conventions import registry",
    "from . import registry",
    "import scripts.module_conventions.registry",
    "from scripts import check_module_conventions",
    "from . import check_module_conventions",
)

#: Sibling-to-sibling spellings the same control must keep accepting.
ALLOWED_IMPORT_SOURCES = (
    "from scripts.module_conventions._core_corpus import Module",
    "from scripts.module_conventions import _core_corpus",
    "from . import _core_corpus",
    "from ._core_corpus import Module",
    "import scripts.module_conventions._core_corpus",
    "import ast",
)


def _wildcard_surface(module) -> set[str]:
    """Return the names ``from <module> import *`` binds, without ``__all__``."""
    namespace: dict[str, object] = {}
    exec(f"from {module.__name__} import *", namespace)  # noqa: S102
    return set(namespace) - {"__builtins__"}


def test_facade_publishes_the_pre_split_surface() -> None:
    """Every name the pre-split module published stays reachable."""
    for name in FROZEN_SURFACE:
        assert getattr(core, name) is not None


def test_facade_keeps_the_pre_split_wildcard_surface() -> None:
    """``from ... import *`` still binds exactly the pre-split public names."""
    assert _wildcard_surface(core) == set(FROZEN_WILDCARD_SURFACE)


def test_facade_preserves_the_pre_split_imported_bindings() -> None:
    """The pre-split module's own imports stay importable through the facade."""
    assert core.ast is ast
    for name in FROZEN_IMPORTED_BINDINGS:
        assert getattr(core, name) is not None


def test_frozen_callable_signatures_are_unchanged() -> None:
    """Each pre-split callable keeps its pre-split signature through the facade."""
    assert {
        name: str(inspect.signature(getattr(core, name))) for name in FROZEN_SIGNATURES
    } == FROZEN_SIGNATURES


def test_frozen_names_keep_their_sibling_homes() -> None:
    """The facade re-exports the very objects the moved names' homes define."""
    for sibling_name, names in FROZEN_HOMES.items():
        sibling = SPLIT_SIBLINGS[sibling_name]
        for name in names:
            assert getattr(core, name) is getattr(sibling, name), name
    assert core.Module.__module__ == "scripts.module_conventions._core_corpus"
    assert core._setting_name_module.__module__ == "scripts.module_conventions.core"


def test_module_name_tables_stay_assigned_in_the_exempt_facade() -> None:
    """Rule 37 exempts only ``core.py``, so its module-name tables live there."""
    tree = ast.parse(Path(core.__file__).read_text(encoding="utf-8"))
    assigned: set[str] = set()
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        assigned.update(target.id for target in targets if isinstance(target, ast.Name))
    assert assigned == set(FROZEN_FACADE_ASSIGNMENTS)
    assert set(RULE_37_MODULE_NAME_TABLES) <= assigned
    assert core.MODULE_LAYERS == FROZEN_MODULE_LAYERS


def test_rule_37_exempts_only_the_facade() -> None:
    """The split siblings stay inside rule 37's closed world, tables excluded."""
    assert ("scripts", "module_conventions/core.py") in RULE_37_ALLOWED_LITERAL_FILES
    for name in SPLIT_SIBLINGS:
        assert ("scripts", f"module_conventions/{name}.py") not in RULE_37_ALLOWED_LITERAL_FILES


def _resolved_import_module(module_name: str, module: str | None, level: int) -> str:
    """Resolve an ``ImportFrom`` target against the importing module's name."""
    if level == 0:
        return module or ""
    parts = module_name.split(".")
    base = parts[: len(parts) - level]
    if module:
        base.append(module)
    return ".".join(base)


def _forbidden_imports(source: str, module_name: str) -> list[str]:
    """
    Return every import in *source* that reaches a forbidden module.

    Both the direct form (``from scripts.module_conventions.core import X``,
    ``import scripts.module_conventions.core``) and the package-style form
    (``from scripts.module_conventions import core``, ``from . import core``)
    resolve to their dotted module path, so every spelling a sibling could
    write is checked.
    """
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[-1] in FORBIDDEN_SIBLING_TARGETS:
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            target = _resolved_import_module(module_name, node.module, node.level)
            if target.split(".")[-1] in FORBIDDEN_SIBLING_TARGETS:
                found.append(target)
            for alias in node.names:
                if alias.name == "*":
                    continue
                resolved = f"{target}.{alias.name}"
                if resolved.split(".")[-1] in FORBIDDEN_SIBLING_TARGETS:
                    found.append(resolved)
    return found


def test_split_siblings_never_import_the_facade_or_entrypoint() -> None:
    """Helpers reach their collaborators through siblings, never the facades."""
    for name, module in SPLIT_SIBLINGS.items():
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert _forbidden_imports(source, module.__name__) == [], name


@pytest.mark.parametrize("source", FORBIDDEN_IMPORT_SOURCES)
def test_forbidden_import_control_rejects_every_reach(source: str) -> None:
    assert _forbidden_imports(source, "scripts.module_conventions._core_ast") != []


@pytest.mark.parametrize("source", ALLOWED_IMPORT_SOURCES)
def test_forbidden_import_control_accepts_sibling_reaches(source: str) -> None:
    assert _forbidden_imports(source, "scripts.module_conventions._core_ast") == []


def test_registry_and_entrypoint_read_the_facade() -> None:
    """The registered harness and the rule modules still resolve the facade."""
    assert checker.load_corpus is core.load_corpus
    assert checker.Corpus is core.Corpus
    assert checker.Module is core.Module
    assert checker.AuthorityError is core.AuthorityError
    assert registry.load_corpus is core.load_corpus
    assert rules_settings._setting_name_module is core._setting_name_module


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _no_manifests(root: Path) -> None:
    (root / "quickscale_modules").mkdir(parents=True)


def _missing_package(root: Path) -> None:
    _write(root, "quickscale_modules/demo/module.yml", "name: demo\n")


def _name_mismatch(root: Path) -> None:
    _write(root, "quickscale_modules/demo/module.yml", "name: other\n")
    _write(root, "quickscale_modules/demo/src/quickscale_modules_demo/__init__.py", "")


def _no_name(root: Path) -> None:
    _write(root, "quickscale_modules/demo/module.yml", "config: {}\n")


def _not_mapping(root: Path) -> None:
    _write(root, "quickscale_modules/demo/module.yml", "- a\n- b\n")


def _duplicate_key(root: Path) -> None:
    _write(root, "quickscale_modules/demo/module.yml", "name: demo\nname: demo\n")


CASE_BUILDERS = {
    "no_manifests": _no_manifests,
    "missing_package": _missing_package,
    "name_mismatch": _name_mismatch,
    "no_name": _no_name,
    "not_mapping": _not_mapping,
    "duplicate_key": _duplicate_key,
}

#: (case, expected message) captured from the pre-split module; each message
#: is exact, so wording and the fail-closed behavior are both pinned.
EXACT_FINDINGS = (
    ("no_manifests", "No source manifests found under {root}/quickscale_modules"),
    (
        "missing_package",
        "Module package missing: quickscale_modules/demo/src/quickscale_modules_demo",
    ),
    (
        "name_mismatch",
        "quickscale_modules/demo/module.yml declares 'other', not its directory name",
    ),
    ("no_name", "quickscale_modules/demo/module.yml has no valid name"),
    ("not_mapping", "quickscale_modules/demo/module.yml must contain a mapping"),
    ("duplicate_key", "quickscale_modules/demo/module.yml: Duplicate YAML key: 'name'"),
)


@pytest.mark.parametrize(
    ("case", "expected"),
    EXACT_FINDINGS,
    ids=[case for case, _ in EXACT_FINDINGS],
)
def test_authority_findings_are_exact(case: str, expected: str, tmp_path: Path) -> None:
    root = tmp_path / case
    CASE_BUILDERS[case](root)
    with pytest.raises(core.AuthorityError) as excinfo:
        core.load_corpus(root)
    assert str(excinfo.value) == expected.format(root=root)
