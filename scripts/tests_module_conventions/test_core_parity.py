"""
Behavioral controls for the ``core`` split (SA268).

The corpus loader, its authority errors, and the manifest readers moved to the
private sibling ``_core_corpus``; the shared AST helpers moved to
``_core_ast``.  The ``core`` facade keeps the module-name tables rule 37
exempts and re-exports every moved name.  SA268 has closed, so SA279 retired the
pre-split surface pins; these controls keep the split's structural invariants
and the exact authority findings captured from the pre-split module, so a later
change cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scripts.module_conventions import (
    _core_ast,
    _core_corpus,
    core,
)
from scripts.module_conventions.rules_identity import RULE_37_ALLOWED_LITERAL_FILES

SPLIT_SIBLINGS = {
    "_core_ast": _core_ast,
    "_core_corpus": _core_corpus,
}


#: Rule 37's literal scan exempts only ``core.py`` in this family, so the
#: tables that carry module names must stay defined there.
RULE_37_MODULE_NAME_TABLES = (
    "SETTING_NAME_EXCEPTIONS",
    "VENDOR_CREDENTIAL_DEFAULTS",
    "QUICKSCALE_ENV_VAR_DEFAULT_EXCEPTIONS",
    "MODULE_LAYERS",
    "APP_CONFIG_WALK_SEAMS",
)


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
    assert set(RULE_37_MODULE_NAME_TABLES) <= assigned


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
