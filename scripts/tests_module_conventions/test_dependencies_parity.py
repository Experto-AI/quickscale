"""
Behavioral controls for the ``rules_dependencies`` split (SA267).

The layer-direction mechanics, the environment-reference scan, the
manifest-dependency checks, and the type-check configuration analysis live in
private siblings (``_dependencies_layers``, ``_dependencies_secrets``,
``_dependencies_manifests``, ``_dependencies_typecheck``) behind the
``rules_dependencies`` facade.  SA267 has closed, so SA279 retired the pre-split
surface pins; these controls keep the split's structural invariants and the
exact ordered findings of representative corpora captured from the pre-split
module, so a later change cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.check_module_conventions import Corpus, Module
from scripts.module_conventions import (
    _dependencies_layers,
    _dependencies_manifests,
    _dependencies_secrets,
    _dependencies_typecheck,
    rules_dependencies,
)
from scripts.module_conventions.rules_identity import RULE_37_ALLOWED_LITERAL_FILES
from scripts.tests_module_conventions._support import (
    _corpus,
    _golden_module,
    _with_files,
)

SPLIT_SIBLINGS = {
    "_dependencies_layers": _dependencies_layers,
    "_dependencies_manifests": _dependencies_manifests,
    "_dependencies_secrets": _dependencies_secrets,
    "_dependencies_typecheck": _dependencies_typecheck,
}


BASE_MYPY = (
    "[mypy-quickscale_modules_demo.*]\n"
    "disallow_untyped_defs = False\n"
    "warn_return_any = False\n"
    "warn_unused_ignores = False\n"
)


def _manifest(module: Module, **updates: object) -> Module:
    """Build a copy of the module whose manifest carries the updates."""
    return replace(module, manifest={**module.manifest, **updates})


def _without(module: Module, key: str) -> Module:
    """Build a copy of the module whose manifest lacks the key."""
    return replace(module, manifest={k: v for k, v in module.manifest.items() if k != key})


def _mypy(corpus: Corpus, text: str) -> Corpus:
    """Build a copy of the corpus with the root mypy.ini replaced."""
    return replace(corpus, mypy_ini=text)


def _core_files(corpus: Corpus, files: dict[str, str]) -> Corpus:
    """Build a copy of the corpus with the core files replaced."""
    return replace(corpus, core_files=files)


def _spec_less_table(module: Module) -> Module:
    """Build a copy of the module whose core dependency declares no spec."""
    return replace(
        module,
        root_files={
            **module.root_files,
            "pyproject.toml": module.root_files["pyproject.toml"].replace(
                "quickscale-core = {path = '../../quickscale_core', develop = true}",
                "quickscale-core = {}",
            ),
        },
    )


CASE_BUILDERS = {
    "clean": lambda: _corpus(_golden_module()),
    "clean_layers": lambda: _corpus(_golden_module("auth")),
    "upward": lambda: _corpus(
        _with_files(
            _golden_module("auth"), views="from quickscale_modules_blog.models import Post\n"
        )
    ),
    "cycle": lambda: _corpus(
        _with_files(
            _golden_module("blog"),
            views="from quickscale_modules_crm.models import Contact\n",
        ),
        _with_files(
            _golden_module("crm"),
            views="from quickscale_modules_blog.models import Post\n",
        ),
    ),
    "core_setting": lambda: _core_files(
        _corpus(_golden_module()),
        {
            "runtime.py": (
                "from django.conf import settings\n\nMODE = settings.QUICKSCALE_ORGS_MODE\n"
            )
        },
    ),
    "getenv": lambda: _corpus(
        _with_files(_golden_module(), services='import os\n\nKEY = os.getenv("DEMO_KEY")\n')
    ),
    "environ_subscript": lambda: _corpus(
        _with_files(_golden_module(), services='import os\n\nKEY = os.environ["DEMO_KEY"]\n')
    ),
    "boot_guard": lambda: _corpus(
        _with_files(
            _golden_module("orgs"),
            checks='import os\n\nBYPASS = os.environ.get("QUICKSCALE_ALLOW_BYPASSRLS")\n',
        )
    ),
    "required_specifier": lambda: _corpus(
        _manifest(_golden_module(), required_modules=["other>=1.0"])
    ),
    "required_unknown": lambda: _corpus(_manifest(_golden_module(), required_modules=["missing"])),
    "no_required_key": lambda: _corpus(_without(_golden_module(), "required_modules")),
    "no_dependencies_key": lambda: _corpus(_without(_golden_module(), "dependencies")),
    "not_bare_dependency": lambda: _corpus(
        _manifest(_golden_module(), dependencies=["other>=1.0", "quickscale-core"])
    ),
    "missing_core": lambda: _corpus(_manifest(_golden_module(), dependencies=[])),
    "undeclared_spec": lambda: _corpus(
        _manifest(_golden_module(), dependencies=["quickscale-core", "other"])
    ),
    "spec_less_table": lambda: _corpus(_spec_less_table(_golden_module())),
    "mypy_missing": lambda: _mypy(_corpus(_golden_module()), ""),
    "mypy_extra_section": lambda: _mypy(
        _corpus(_golden_module()),
        BASE_MYPY + "[mypy-quickscale_modules_demo.models]\nignore_missing_imports = True\n",
    ),
    "mypy_forbidden_key": lambda: _mypy(
        _corpus(_golden_module()),
        "[mypy-quickscale_modules_demo.*]\nignore_missing_imports = True\n",
    ),
    "mypy_disabled_code": lambda: _mypy(
        _corpus(_golden_module()),
        "[mypy-quickscale_modules_demo.*]\ndisable_error_code = var-annotated, assignment\n",
    ),
    "mypy_relaxed": lambda: _mypy(
        _corpus(_golden_module()), "[mypy-quickscale_modules_demo.*]\nwarn_no_return = False\n"
    ),
    "mypy_allowed_alias": lambda: _mypy(
        _corpus(_golden_module()),
        "[mypy-quickscale_modules_demo.*]\nallow_untyped_defs = True\n",
    ),
}

#: (case, detector, expected findings) captured from the pre-split module; the
#: list is exact, so order, wording, and duplicate findings are all pinned.
EXACT_FINDINGS = (
    ("clean_layers", "rule_5_dependency_direction", ()),
    ("clean", "rule_35_secrets", ()),
    ("clean", "rule_39_module_dependencies", ()),
    ("clean", "rule_36_typecheck_config", ()),
    (
        "upward",
        "rule_5_dependency_direction",
        ("rule 5: auth: views.py:1 imports upward from blog:models (layer 3 above layer 1)",),
    ),
    (
        "cycle",
        "rule_5_dependency_direction",
        ("rule 5: same-layer import cycle: blog -> crm -> blog",),
    ),
    (
        "core_setting",
        "rule_5_dependency_direction",
        ("rule 5: core runtime.py:3 names module setting QUICKSCALE_ORGS_MODE",),
    ),
    (
        "getenv",
        "rule_35_secrets",
        (
            "rule 35: demo: services.py:3 uses os.getenv/os.environ (DEMO_KEY) "
            "instead of an applied setting",
        ),
    ),
    (
        "environ_subscript",
        "rule_35_secrets",
        (
            "rule 35: demo: services.py:3 uses os.getenv/os.environ (DEMO_KEY) "
            "instead of an applied setting",
        ),
    ),
    ("boot_guard", "rule_35_secrets", ()),
    (
        "required_specifier",
        "rule_39_module_dependencies",
        ("rule 39: demo: required module 'other>=1.0' is not a bare name",),
    ),
    (
        "required_unknown",
        "rule_39_module_dependencies",
        ("rule 39: demo: unknown required module 'missing'",),
    ),
    (
        "no_required_key",
        "rule_39_module_dependencies",
        ("rule 39: demo: manifest is missing required_modules",),
    ),
    (
        "no_dependencies_key",
        "rule_39_module_dependencies",
        ("rule 39: demo: manifest is missing dependencies",),
    ),
    (
        "not_bare_dependency",
        "rule_39_module_dependencies",
        (
            "rule 39: demo: dependency 'other>=1.0' is not a bare package name "
            "(the spec lives in pyproject.toml)",
        ),
    ),
    (
        "missing_core",
        "rule_39_module_dependencies",
        ("rule 39: demo: manifest dependencies do not declare quickscale-core",),
    ),
    (
        "undeclared_spec",
        "rule_39_module_dependencies",
        ("rule 39: demo: dependency 'other' has no spec in pyproject.toml",),
    ),
    (
        "spec_less_table",
        "rule_39_module_dependencies",
        ("rule 39: demo: dependency 'quickscale-core' has no usable spec in pyproject.toml",),
    ),
    (
        "mypy_missing",
        "rule_36_typecheck_config",
        ("rule 36: demo: mypy.ini has no [mypy-quickscale_modules_demo.*] section",),
    ),
    (
        "mypy_extra_section",
        "rule_36_typecheck_config",
        (
            "rule 36: demo: mypy.ini declares an extra section "
            "[mypy-quickscale_modules_demo.models]",
        ),
    ),
    (
        "mypy_forbidden_key",
        "rule_36_typecheck_config",
        ("rule 36: demo: mypy.ini section key 'ignore_missing_imports' is not allowed",),
    ),
    (
        "mypy_disabled_code",
        "rule_36_typecheck_config",
        ("rule 36: demo: mypy.ini disables assignment",),
    ),
    (
        "mypy_relaxed",
        "rule_36_typecheck_config",
        ("rule 36: demo: mypy.ini section 'warn_no_return' relaxes outside the allowed set",),
    ),
    ("mypy_allowed_alias", "rule_36_typecheck_config", ()),
)


def test_rule_37_exempts_only_the_facade() -> None:
    """The split siblings stay inside rule 37's closed world."""
    assert ("scripts", "module_conventions/rules_dependencies.py") in RULE_37_ALLOWED_LITERAL_FILES
    for name in SPLIT_SIBLINGS:
        assert (
            "scripts",
            f"module_conventions/{name}.py",
        ) not in RULE_37_ALLOWED_LITERAL_FILES


def test_split_siblings_never_import_the_facade_or_registry() -> None:
    """Helpers reach their collaborators through siblings, never the facade."""
    for name, module in SPLIT_SIBLINGS.items():
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[-1] not in {"rules_dependencies", "registry"}, (
                    name,
                    node.lineno,
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[-1] not in {"rules_dependencies", "registry"}, (
                        name,
                        node.lineno,
                    )


@pytest.mark.parametrize(
    ("case", "detector", "expected"),
    EXACT_FINDINGS,
    ids=[f"{case}-{detector}" for case, detector, _ in EXACT_FINDINGS],
)
def test_detector_findings_are_exact_and_ordered(
    case: str, detector: str, expected: tuple[str, ...]
) -> None:
    corpus = CASE_BUILDERS[case]()
    assert getattr(rules_dependencies, detector)(corpus) == list(expected)
