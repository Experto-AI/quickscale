"""Control cases for the dependencies module-convention rules."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import (
    REPO_ROOT,
    _corpus,
    _golden_module,
    _violations,
    _with_files,
)


def test_module_dependency_control() -> None:
    module = _golden_module()
    manifest = {**module.manifest, "required_modules": ["other>=1.0"]}
    assert _violations(checker.rule_39_module_dependencies, replace(module, manifest=manifest))


def test_dependency_manifest_surface_controls() -> None:
    """Presence, bare names, quickscale-core, and the pyproject spec (SA260)."""
    module = _golden_module()
    assert _violations(checker.rule_39_module_dependencies, module) == []

    without_required = replace(
        module,
        manifest={
            key: value for key, value in module.manifest.items() if key != "required_modules"
        },
    )
    assert any(
        "missing required_modules" in violation
        for violation in _violations(checker.rule_39_module_dependencies, without_required)
    )

    without_dependencies = replace(
        module,
        manifest={key: value for key, value in module.manifest.items() if key != "dependencies"},
    )
    assert any(
        "missing dependencies" in violation
        for violation in _violations(checker.rule_39_module_dependencies, without_dependencies)
    )

    specifier = replace(
        module,
        manifest={**module.manifest, "dependencies": ["other>=1.0", "quickscale-core"]},
    )
    assert any(
        "not a bare package name" in violation
        for violation in _violations(checker.rule_39_module_dependencies, specifier)
    )

    missing_core = replace(module, manifest={**module.manifest, "dependencies": []})
    assert any(
        "do not declare quickscale-core" in violation
        for violation in _violations(checker.rule_39_module_dependencies, missing_core)
    )

    undeclared = replace(
        module, manifest={**module.manifest, "dependencies": ["quickscale-core", "other"]}
    )
    assert any(
        "no spec in pyproject.toml" in violation
        for violation in _violations(checker.rule_39_module_dependencies, undeclared)
    )

    spec_less_table = replace(
        module,
        root_files={
            **module.root_files,
            "pyproject.toml": module.root_files["pyproject.toml"].replace(
                "quickscale-core = {path = '../../quickscale_core', develop = true}",
                "quickscale-core = {}",
            ),
        },
    )
    assert any(
        "has no usable spec" in violation
        for violation in _violations(checker.rule_39_module_dependencies, spec_less_table)
    )


def test_upward_import_control() -> None:
    auth = _golden_module("auth")
    broken = _with_files(auth, views="from quickscale_modules_blog.models import Post\n")
    assert any(
        "imports upward" in violation
        for violation in _violations(checker.rule_5_dependency_direction, broken)
    )
    assert _violations(checker.rule_5_dependency_direction, auth) == []


def test_same_layer_cycle_control() -> None:
    blog = _with_files(
        _golden_module("blog"), views="from quickscale_modules_crm.models import Contact\n"
    )
    crm = _with_files(
        _golden_module("crm"), views="from quickscale_modules_blog.models import Post\n"
    )
    assert any(
        "cycle" in violation
        for violation in _violations(checker.rule_5_dependency_direction, blog, crm)
    )


def test_core_module_setting_name_control() -> None:
    module = _golden_module()
    corpus = replace(
        _corpus(module),
        core_files={
            "runtime.py": (
                "from django.conf import settings\n\nMODE = settings.QUICKSCALE_ORGS_MODE\n"
            )
        },
    )
    assert any(
        "names module setting" in violation
        for violation in checker.rule_5_dependency_direction(corpus)
    )


def test_aliased_core_setting_read_control() -> None:
    module = _golden_module()
    corpus = replace(
        _corpus(module),
        core_files={
            "runtime.py": (
                "from django.conf import settings as cfg\n\nMODE = cfg.QUICKSCALE_ORGS_MODE\n"
            )
        },
    )
    assert any(
        "names module setting" in violation
        for violation in checker.rule_5_dependency_direction(corpus)
    )


def test_migration_model_import_is_not_an_upward_reference() -> None:
    orgs = _golden_module("orgs")
    excepted = _with_files(
        orgs,
        **{
            "migrations/0001_initial.py": (
                "from quickscale_modules_billing.models import Subscription\n"
            )
        },
    )
    assert _violations(checker.rule_5_dependency_direction, excepted) == []
    non_model = _with_files(
        orgs,
        **{
            "migrations/0001_initial.py": (
                "from quickscale_modules_billing.services import debit_user\n"
            )
        },
    )
    assert any(
        "imports upward" in violation
        for violation in _violations(checker.rule_5_dependency_direction, non_model)
    )


def test_migration_mixed_import_control() -> None:
    orgs = _golden_module("orgs")
    mixed = _with_files(
        orgs,
        **{
            "migrations/0002_extra.py": (
                "from quickscale_modules_billing import models, services\n"
            )
        },
    )
    assert any(
        "imports upward" in violation
        for violation in _violations(checker.rule_5_dependency_direction, mixed)
    )
    models_only = _with_files(
        orgs,
        **{"migrations/0003_extra.py": "from quickscale_modules_billing import models\n"},
    )
    assert _violations(checker.rule_5_dependency_direction, models_only) == []


def test_secrets_control() -> None:
    module = _golden_module()
    assert _violations(checker.rule_35_secrets, module) == []
    getenv = _with_files(module, services='import os\n\nKEY = os.getenv("DEMO_KEY")\n')
    assert any(
        "uses os.getenv/os.environ" in violation
        for violation in _violations(checker.rule_35_secrets, getenv)
    )
    environ = _with_files(module, services='import os\n\nKEY = os.environ["DEMO_KEY"]\n')
    environ_violations = _violations(checker.rule_35_secrets, environ)
    assert len(environ_violations) == 1
    assert "uses os.getenv/os.environ" in environ_violations[0]
    aliased = _with_files(
        module,
        services='import os as operating_system\n\nKEY = operating_system.getenv("DEMO_KEY")\n',
    )
    assert any(
        "uses os.getenv/os.environ" in violation
        for violation in _violations(checker.rule_35_secrets, aliased)
    )
    orgs = _golden_module("orgs")
    boot_guard = _with_files(
        orgs,
        checks=('import os\n\nBYPASS = os.environ.get("QUICKSCALE_ALLOW_BYPASSRLS")\n'),
    )
    assert _violations(checker.rule_35_secrets, boot_guard) == []
    other_variable = _with_files(orgs, checks='import os\n\nKEY = os.environ.get("DEMO_KEY")\n')
    assert any(
        "uses os.getenv/os.environ" in violation
        for violation in _violations(checker.rule_35_secrets, other_variable)
    )


def test_typecheck_config_controls() -> None:
    module = _golden_module()
    corpus = _corpus(module)
    assert checker.rule_36_typecheck_config(corpus) == []
    missing = replace(corpus, mypy_ini="")
    assert any(
        "has no [mypy-quickscale_modules_demo.*] section" in violation
        for violation in checker.rule_36_typecheck_config(missing)
    )
    ignored = replace(
        corpus,
        mypy_ini=(
            "[mypy-quickscale_modules_demo.*]\n"
            "disallow_untyped_defs = False\n"
            "ignore_missing_imports = True\n"
        ),
    )
    assert any(
        "section key 'ignore_missing_imports' is not allowed" in violation
        for violation in checker.rule_36_typecheck_config(ignored)
    )
    extra_codes = replace(
        corpus,
        mypy_ini=(
            "[mypy-quickscale_modules_demo.*]\ndisable_error_code = var-annotated, assignment\n"
        ),
    )
    assert any(
        "disables assignment" in violation
        for violation in checker.rule_36_typecheck_config(extra_codes)
    )
    allowed_code = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\ndisable_error_code = var-annotated\n",
    )
    assert checker.rule_36_typecheck_config(allowed_code) == []
    stricter = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\ndisallow_any_generics = True\n",
    )
    assert checker.rule_36_typecheck_config(stricter) == []
    relaxed = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\nwarn_no_return = False\n",
    )
    assert any(
        "relaxes outside the allowed set" in violation
        for violation in checker.rule_36_typecheck_config(relaxed)
    )
    extra_section = replace(
        corpus,
        mypy_ini=(
            "[mypy-quickscale_modules_demo.*]\n"
            "disallow_untyped_defs = False\n"
            "[mypy-quickscale_modules_demo.models]\n"
            "ignore_missing_imports = True\n"
        ),
    )
    assert any(
        "declares an extra section [mypy-quickscale_modules_demo.models]" in violation
        for violation in checker.rule_36_typecheck_config(extra_section)
    )
    grouped_section = replace(
        corpus,
        mypy_ini=(
            "[mypy-quickscale_modules_demo.*]\n"
            "disallow_untyped_defs = False\n"
            "[mypy-third_party.*,quickscale_modules_demo.models]\n"
            "ignore_errors = True\n"
        ),
    )
    assert any(
        "declares an extra section [mypy-third_party.*,quickscale_modules_demo.models]" in violation
        for violation in checker.rule_36_typecheck_config(grouped_section)
    )
    wildcard_section = replace(
        corpus,
        mypy_ini=(
            "[mypy-quickscale_modules_demo.*]\n"
            "disallow_untyped_defs = False\n"
            "[mypy-*.models]\n"
            "ignore_errors = True\n"
        ),
    )
    assert any(
        "declares an extra section [mypy-*.models]" in violation
        for violation in checker.rule_36_typecheck_config(wildcard_section)
    )
    parent_section = replace(
        corpus,
        mypy_ini=(
            "[mypy-quickscale_modules_demo.*]\n"
            "disallow_untyped_defs = False\n"
            "[mypy-quickscale_modules_demo.models.*]\n"
            "ignore_errors = True\n"
        ),
    )
    assert any(
        "declares an extra section [mypy-quickscale_modules_demo.models.*]" in violation
        for violation in checker.rule_36_typecheck_config(parent_section)
    )
    unrelated_section = replace(
        corpus,
        mypy_ini=(
            "[mypy-quickscale_modules_demo.*]\n"
            "disallow_untyped_defs = False\n"
            "[mypy-third_party.*]\n"
            "ignore_missing_imports = True\n"
        ),
    )
    assert checker.rule_36_typecheck_config(unrelated_section) == []
    separator_section = replace(
        corpus,
        mypy_ini=(
            "[mypy-quickscale_modules_demo.*]\n"
            "disallow_untyped_defs = False\n"
            "[mypy-quickscale_modules_demo/models.*]\n"
            "ignore_errors = True\n"
        ),
    )
    assert any(
        "declares an extra section [mypy-quickscale_modules_demo/models.*]" in violation
        for violation in checker.rule_36_typecheck_config(separator_section)
    )


def test_typecheck_config_option_controls() -> None:
    module = _golden_module()
    corpus = _corpus(module)
    aliased_relaxation = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\nallow_untyped_calls = True\n",
    )
    assert any(
        "relaxes outside the allowed set" in violation
        for violation in checker.rule_36_typecheck_config(aliased_relaxation)
    )
    permitted_alias = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\nallow_untyped_defs = True\n",
    )
    assert checker.rule_36_typecheck_config(permitted_alias) == []
    permitted_no_alias = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\nno_warn_return_any = True\n",
    )
    assert checker.rule_36_typecheck_config(permitted_no_alias) == []
    redefinition_new = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\nallow_redefinition_new = True\n",
    )
    assert any(
        "relaxes outside the allowed set" in violation
        for violation in checker.rule_36_typecheck_config(redefinition_new)
    )
    for option in (
        "implicit_optional = True",
        "allow_untyped_globals = True",
        "allow_redefinition_old = True",
        "strict_optional = False",
        "local_partial_types = False",
    ):
        relaxed_option = replace(
            corpus,
            mypy_ini=f"[mypy-quickscale_modules_demo.*]\n{option}\n",
        )
        assert any(
            "relaxes outside the allowed set" in violation
            for violation in checker.rule_36_typecheck_config(relaxed_option)
        ), option
    for option in (
        "implicit_optional = False",
        "allow_untyped_globals = False",
        "strict_optional = True",
    ):
        stricter_option = replace(
            corpus,
            mypy_ini=f"[mypy-quickscale_modules_demo.*]\n{option}\n",
        )
        assert checker.rule_36_typecheck_config(stricter_option) == [], option
    for option in (
        "implicit_optional = yes",
        "allow_untyped_globals = 1",
        "allow_redefinition_old = on",
        "strict_optional = no",
        "local_partial_types = off",
    ):
        spelled_option = replace(
            corpus,
            mypy_ini=f"[mypy-quickscale_modules_demo.*]\n{option}\n",
        )
        assert any(
            "relaxes outside the allowed set" in violation
            for violation in checker.rule_36_typecheck_config(spelled_option)
        ), option
    reexport = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\nimplicit_reexport = False\n",
    )
    assert checker.rule_36_typecheck_config(reexport) == []
    ignore_errors = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\nignore_errors = True\n",
    )
    assert any(
        "relaxes outside the allowed set" in violation
        for violation in checker.rule_36_typecheck_config(ignore_errors)
    )
    follow_imports = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\nfollow_imports = skip\n",
    )
    assert any(
        "relaxes outside the allowed set" in violation
        for violation in checker.rule_36_typecheck_config(follow_imports)
    )


def _layer_document(layers: Mapping[str, int]) -> str:
    """Render a module_conventions.md-shaped layer table for a module -> layer map."""
    lines = [
        "**5. Dependency direction.** A module may import only from its own layer or lower ones.",
        "",
        "| Layer | Modules |",
        "|---|---|",
        "| 0 \u2014 core | `quickscale_core` (imports no module; already gated) |",
    ]
    for layer in sorted(set(layers.values())):
        names = sorted(name for name, value in layers.items() if value == layer)
        lines.append(f"| {layer} \u2014 section {layer} | " + ", ".join(names) + " |")
    lines.append("")
    return "\n".join(lines)


def _layer_corpus(layers: Mapping[str, int]) -> checker.Corpus:
    """Build the corpus and document that ship exactly ``layers``' modules."""
    return replace(
        _corpus(*(_golden_module(name) for name in layers)),
        conventions_text=_layer_document(layers),
    )


def _unreadable(corpus: checker.Corpus, document: str) -> list[str]:
    """Return the findings for a corpus whose conventions-doc text is replaced."""
    return checker.layer_table_findings(replace(corpus, conventions_text=document))


def test_layer_table_controls() -> None:
    """Shipped modules, the layer table, and module_conventions.md agree (SA296 (c))."""
    corpus = _layer_corpus(checker.MODULE_LAYERS)
    assert checker.layer_table_findings(corpus) == []

    demo = _golden_module("demo")
    missing_entry = replace(
        corpus,
        modules=(*corpus.modules, demo),
        module_dir_names=(*corpus.module_dir_names, demo.name),
    )
    assert checker.layer_table_findings(missing_entry) == [
        "rule 5: demo has no MODULE_LAYERS entry"
    ]

    dropped = corpus.modules[-1].name
    missing_module = replace(corpus, modules=corpus.modules[:-1])
    assert checker.layer_table_findings(missing_module) == [
        f"rule 5: MODULE_LAYERS entry {dropped} ships no module"
    ]

    moved = next(name for name, layer in checker.MODULE_LAYERS.items() if layer == 3)
    drifted = _unreadable(corpus, _layer_document({**checker.MODULE_LAYERS, moved: 2}))
    assert drifted == [
        f"rule 5: {moved} is layer 2 in module_conventions.md and layer 3 in MODULE_LAYERS"
    ]

    dropped_entry = {name: layer for name, layer in checker.MODULE_LAYERS.items() if name != moved}
    assert _unreadable(corpus, _layer_document(dropped_entry)) == [
        f"rule 5: MODULE_LAYERS names {moved}, which conventions layer table does not"
    ]

    extra_entry = {**checker.MODULE_LAYERS, "demo": 3}
    assert _unreadable(corpus, _layer_document(extra_entry)) == [
        "rule 5: conventions layer table names demo, which MODULE_LAYERS does not"
    ]

    assert _unreadable(corpus, "No layer table here.\n") == [
        "rule 5: module_conventions.md layer table unreadable: no '| Layer | Modules |' table"
    ]
    renamed = _layer_document(checker.MODULE_LAYERS).replace("| 1 \u2014", "| one \u2014", 1)
    assert any(
        "unreadable:" in finding and "names no layer" in finding
        for finding in _unreadable(corpus, renamed)
    )
    not_a_name = _layer_document(checker.MODULE_LAYERS).replace(moved, "not a module name", 1)
    assert any("not a module name" in finding for finding in _unreadable(corpus, not_a_name))
    duplicated = _unreadable(
        corpus,
        _layer_document(checker.MODULE_LAYERS).rstrip("\n") + f"\n| 4 \u2014 extra | {dropped} |\n",
    )
    assert any(
        f"layer 4 lists {dropped}, which layer 3 already lists" in finding for finding in duplicated
    )


def test_layer_table_mirrors_the_real_tree() -> None:
    """The live inventory, the layer table, and the shipped document agree."""
    corpus = checker.load_corpus(REPO_ROOT)
    assert checker.layer_table_findings(corpus) == []
    document = (REPO_ROOT / checker.CONVENTIONS_DOC_RELATIVE_PATH).read_text(encoding="utf-8")
    assert checker.conventions_layer_table(document) == checker.MODULE_LAYERS
