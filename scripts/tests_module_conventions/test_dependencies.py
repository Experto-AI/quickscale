"""Control cases for the dependencies module-convention rules."""

from __future__ import annotations

from dataclasses import replace

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import (
    _corpus,
    _golden_module,
    _violations,
    _with_files,
)


def test_module_dependency_control() -> None:
    module = _golden_module()
    manifest = {**module.manifest, "required_modules": ["other>=1.0"]}
    assert _violations(checker.rule_39_module_dependencies, replace(module, manifest=manifest))


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
