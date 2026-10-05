"""Control cases for the identity module-convention rules."""

from __future__ import annotations

from dataclasses import replace

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import (
    _corpus,
    _golden_module,
    _violations,
    _with_files,
)


def test_identity_names_control() -> None:
    module = _golden_module()
    broken = _with_files(module, apps=module.files["apps.py"].replace("label", "labels"))
    assert _violations(checker.rule_2_identity_names, broken)
    assert _violations(checker.rule_2_identity_names, module) == []


def test_identity_accepts_single_quoted_literals() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"]
        .replace('"quickscale_modules_demo"', "'quickscale_modules_demo'")
        .replace('"quickscale_demo"', "'quickscale_demo'"),
        urls=module.files["urls.py"].replace('"quickscale_demo"', "'quickscale_demo'"),
    )
    assert _violations(checker.rule_2_identity_names, broken) == []


def test_py_typed_control() -> None:
    module = _golden_module()
    broken = replace(
        module, files={key: value for key, value in module.files.items() if key != "py.typed"}
    )
    assert any(
        "py.typed" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_now_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views="import datetime\n\n\ndef index():\n    return datetime.datetime.now()\n",
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_timezone_alias_is_not_datetime_now() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        views=(
            "from django.utils import timezone as datetime_clock\n\n\n"
            "def index():\n    return datetime_clock.now()\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_datetime_alias_controls() -> None:
    module = _golden_module()
    django_alias = _with_files(
        module,
        views=(
            "from django.utils import timezone as datetime\n\n\n"
            "def index():\n    return datetime.now()\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, django_alias) == []
    stdlib_alias = _with_files(
        module,
        views="from datetime import datetime as dt\n\n\ndef index():\n    return dt.now()\n",
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, stdlib_alias)
    )
    module_alias = _with_files(
        module,
        views="import datetime as clock\n\n\ndef index():\n    return clock.datetime.now()\n",
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, module_alias)
    )


def test_datetime_scope_local_alias_does_not_mask_module_import() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime\n\n\n"
            "def index():\n"
            "    return datetime.now()\n\n\n"
            "def other():\n"
            "    from django.utils import timezone as datetime\n"
            "    return datetime.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_import_order_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n"
            "from datetime import datetime as clock\n\n\n"
            "class View:\n"
            "    created = clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )
    good = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n"
            "from django.utils import timezone as clock\n\n\n"
            "class View:\n"
            "    created = clock.now()\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_datetime_call_before_rebinding_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n\n"
            "class View:\n"
            "    created = clock.now()\n\n\n"
            "from django.utils import timezone as clock\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_deferred_function_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n\n\n"
            "def index():\n"
            "    return clock.now()\n\n\n"
            "from datetime import datetime as clock\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )
    good = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n\n"
            "def index():\n"
            "    return clock.now()\n\n\n"
            "from django.utils import timezone as clock\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_datetime_compound_import_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "if True:\n"
            "    from datetime import datetime as clock\n\n\n"
            "def index():\n"
            "    return clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )
    function_scope = _with_files(
        module,
        views=(
            "def index():\n"
            "    if True:\n"
            "        from datetime import datetime as clock\n"
            "    return clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, function_scope)
    )


def test_datetime_unreachable_compound_import_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n"
            "if False:\n"
            "    from django.utils import timezone as clock\n\n\n"
            "def index():\n"
            "    return clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_compound_call_before_rebind_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n"
            "if True:\n"
            "    created = clock.now()\n"
            "    from django.utils import timezone as clock\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_nested_function_closure_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n\n\n"
            "def outer():\n"
            "    from datetime import datetime as clock\n\n"
            "    def inner():\n"
            "        return clock.now()\n\n"
            "    return inner()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )
    good = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n\n"
            "def outer():\n"
            "    from django.utils import timezone as clock\n\n"
            "    def inner():\n"
            "        return clock.now()\n\n"
            "    return inner()\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_datetime_while_false_import_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n"
            "while False:\n"
            "    from django.utils import timezone as clock\n\n\n"
            "def index():\n"
            "    return clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_uncertain_branch_import_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n"
            "flag = False\n"
            "if flag:\n"
            "    from django.utils import timezone as clock\n\n\n"
            "def index():\n"
            "    return clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_uncertain_branch_stdlib_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n\n"
            "flag = True\n"
            "if flag:\n"
            "    from datetime import datetime as clock\n\n\n"
            "def index():\n"
            "    return clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_class_while_false_positive() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n\n\n"
            "class View:\n"
            "    while False:\n"
            "        from datetime import datetime as clock\n\n"
            "    created = clock.now()\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_datetime_closure_after_definition_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n\n\n"
            "def outer():\n"
            "    def inner():\n"
            "        return clock.now()\n\n"
            "    from datetime import datetime as clock\n"
            "    return inner()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )
    good = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n\n"
            "def outer():\n"
            "    def inner():\n"
            "        return clock.now()\n\n"
            "    from django.utils import timezone as clock\n"
            "    return inner()\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_datetime_class_body_call_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n\nclass View:\n    created = clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_class_body_compound_call_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n\n"
            "class View:\n"
            "    if True:\n"
            "        created = clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_class_body_timezone_positive() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n\n\n"
            "class View:\n"
            "    created = clock.now()\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_datetime_class_compound_method_scope() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n\n"
            "class View:\n"
            "    from django.utils import timezone as clock\n\n"
            "    if True:\n"
            "        def index(self):\n"
            "            return clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_class_compound_method_accepts_enclosing_timezone() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n\n\n"
            "class View:\n"
            "    from datetime import datetime as clock\n\n"
            "    if True:\n"
            "        def index(self):\n"
            "            return clock.now()\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_datetime_method_default_uses_class_scope() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n\n\n"
            "class View:\n"
            "    from datetime import datetime as clock\n\n"
            "    def index(self, now=clock.now()):\n"
            "        return now\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_method_default_accepts_class_timezone() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n\n"
            "class View:\n"
            "    from django.utils import timezone as clock\n\n"
            "    def index(self, now=clock.now()):\n"
            "        return now\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_datetime_class_scope_does_not_leak_into_methods() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime\n\n\n"
            "class View:\n"
            "    from django.utils import timezone as datetime\n\n"
            "    def index(self):\n"
            "        return datetime.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_default_argument_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime\n\n\ndef index(now=datetime.now()):\n    return now\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_default_argument_accepts_timezone() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        views=(
            "from django.utils import timezone\n\n\n"
            "def index(now=timezone.now()):\n"
            "    return now\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_cache_key_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.core.cache import cache\n\n"
            "WIDGET_CACHE_KEY = 'widgets:all'\n\n"
            "def index():\n    cache.set('other:key', 1)\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, broken)


def test_test_name_control() -> None:
    module = _golden_module()
    docstring = '"""SA999 widget behaviour."""\n\n\ndef test_widget():\n    pass\n'
    broken = replace(module, tests={**module.tests, "test_widget.py": docstring})
    assert _violations(checker.rule_29_test_names, broken)
    comment = "# SA999 legacy reason\ndef test_widget():\n    pass\n"
    commented = replace(module, tests={**module.tests, "test_widget.py": comment})
    assert _violations(checker.rule_29_test_names, commented)


def test_shared_stem_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "def _lock_key(value):\n"
            "    return f'widget:lock:{value}'\n\n"
            "FUNC_NAME = 'widget_equality'\n"
        ),
    )
    violations = _violations(checker.rule_33_shared_stems, broken)
    assert any("advisory-lock key" in violation for violation in violations)
    assert any("database function" in violation for violation in violations)


def test_ticket_filename_control() -> None:
    module = _golden_module()
    broken = replace(
        module,
        tests={
            "settings.py": module.tests["settings.py"],
            "test_SA999_widget.py": '"""Widget."""\n',
        },
    )
    assert any(
        "ticket id" in violation for violation in _violations(checker.rule_29_test_names, broken)
    )


def test_name_reference_controls() -> None:
    orgs = _golden_module("orgs")
    assert _violations(checker.rule_34_name_references, orgs) == []
    upward = _with_files(
        orgs,
        services=(
            "from django.apps import apps\n\nPLAN = apps.get_model('quickscale_billing', 'Plan')\n"
        ),
    )
    assert any(
        "references billing by name upward" in violation
        for violation in _violations(checker.rule_34_name_references, upward)
    )
    namespace = _with_files(
        orgs,
        services=(
            "from django.urls import reverse\n\nURL = reverse('quickscale_billing:pricing')\n"
        ),
    )
    assert any(
        "references billing by name upward" in violation
        for violation in _violations(checker.rule_34_name_references, namespace)
    )
    label_prefix = _with_files(orgs, services="LABEL = 'quickscale_billing_'\n")
    assert any(
        "references billing by name upward" in violation
        for violation in _violations(checker.rule_34_name_references, label_prefix)
    )
    lookalike = _with_files(orgs, services="LABEL = 'quickscale_billingx'\n")
    assert _violations(checker.rule_34_name_references, lookalike) == []
    downward = _with_files(
        _golden_module("blog"),
        **{
            "services.py": (
                "from django.apps import apps\n\n"
                'X = apps.is_installed("quickscale_modules_storage")\n'
            )
        },
    )
    assert _violations(checker.rule_34_name_references, downward) == []
    self_reference = _with_files(
        orgs,
        services=(
            "from importlib import import_module\n\n"
            "mod = import_module('quickscale_modules_orgs.checks')\n"
        ),
    )
    assert _violations(checker.rule_34_name_references, self_reference) == []
    migration = _with_files(
        orgs,
        **{
            "migrations/0002_extra.py": (
                "from django.apps import apps\n\n"
                "PLAN = apps.get_model('quickscale_billing', 'Plan')\n"
            )
        },
    )
    assert _violations(checker.rule_34_name_references, migration) == []
    service_migration = _with_files(
        orgs,
        **{
            "migrations/0003_extra.py": (
                "from importlib import import_module\n\n"
                "mod = import_module('quickscale_modules_billing.services')\n"
            )
        },
    )
    assert any(
        "references billing by name upward" in violation
        for violation in _violations(checker.rule_34_name_references, service_migration)
    )
    app_config_migration = _with_files(
        orgs,
        **{
            "migrations/0004_extra.py": (
                "from django.apps import apps\n\n"
                "config = apps.get_app_config('quickscale_billing')\n"
            )
        },
    )
    assert any(
        "references billing by name upward" in violation
        for violation in _violations(checker.rule_34_name_references, app_config_migration)
    )
    keyword_migration = _with_files(
        orgs,
        **{
            "migrations/0005_extra.py": (
                "from django.apps import apps\n\n"
                "PLAN = apps.get_model(app_label='quickscale_billing', model_name='Plan')\n"
            )
        },
    )
    assert _violations(checker.rule_34_name_references, keyword_migration) == []
    annotated_dependencies = _with_files(
        orgs,
        **{
            "migrations/0006_extra.py": (
                "dependencies: list[tuple[str, str]] = [('quickscale_billing', '0001_initial')]\n"
            )
        },
    )
    assert _violations(checker.rule_34_name_references, annotated_dependencies) == []
    notifications = _with_files(
        _golden_module("notifications"),
        services=(
            'from django.apps import apps\n\nX = apps.is_installed("quickscale_modules_orgs")\n'
        ),
    )
    orgs_reference = _with_files(
        orgs,
        services=(
            "from django.apps import apps\n\n"
            'X = apps.is_installed("quickscale_modules_notifications")\n'
        ),
    )
    assert any(
        "cycle" in violation
        for violation in _violations(checker.rule_34_name_references, orgs_reference, notifications)
    )


def test_package_file_name_controls() -> None:
    module = _golden_module()
    assert _violations(checker.rule_28_file_names, module) == []
    extra = _with_files(module, **{"utils.py": "def helper():\n    return None\n"})
    assert any(
        "utils.py is not an allowed package file name" in violation
        for violation in _violations(checker.rule_28_file_names, extra)
    )
    private = _with_files(module, **{"_utils.py": "def helper():\n    return None\n"})
    assert _violations(checker.rule_28_file_names, private) == []
    events = _with_files(module, **{"events.py": 'PAGEVIEW = "$pageview"\n'})
    assert any(
        "events.py is not an allowed package file name" in violation
        for violation in _violations(checker.rule_28_file_names, events)
    )
    markdownx = _with_files(_golden_module("blog"), **{"markdownx_urls.py": "urlpatterns = []\n"})
    assert _violations(checker.rule_28_file_names, markdownx) == []
    demo_markdownx = _with_files(module, **{"markdownx_urls.py": "urlpatterns = []\n"})
    assert any(
        "markdownx_urls.py is not an allowed package file name" in violation
        for violation in _violations(checker.rule_28_file_names, demo_markdownx)
    )


def test_private_facade_log_channel_controls() -> None:
    module = _golden_module()
    private_logger = "import logging\n\nlogger = logging.getLogger(__name__)\n"
    facade = _with_files(
        module,
        views="from ._helpers import helper\n",
        **{"_helpers.py": private_logger},
    )
    violations = _violations(checker.rule_28_file_names, facade)
    assert any(
        "_helpers.py" in violation and "getLogger(__name__)" in violation
        for violation in violations
    ), violations
    absolute = _with_files(
        module,
        views="from quickscale_modules_demo._helpers import helper\n",
        **{"_helpers.py": private_logger},
    )
    assert any(
        "_helpers.py" in violation
        for violation in _violations(checker.rule_28_file_names, absolute)
    )
    package_root = _with_files(
        module,
        views="from quickscale_modules_demo import _helpers\n",
        **{"_helpers.py": private_logger},
    )
    assert any(
        "_helpers.py" in violation
        for violation in _violations(checker.rule_28_file_names, package_root)
    )
    relative_root = _with_files(
        module,
        views="from . import _helpers\n",
        **{"_helpers.py": private_logger},
    )
    assert any(
        "_helpers.py" in violation
        for violation in _violations(checker.rule_28_file_names, relative_root)
    )
    facade_channel = _with_files(
        facade,
        **{
            "_helpers.py": 'import logging\n\nlogger = logging.getLogger("quickscale_demo.views")\n'
        },
    )
    assert _violations(checker.rule_28_file_names, facade_channel) == []
    orphan = _with_files(module, **{"_helpers.py": private_logger})
    assert _violations(checker.rule_28_file_names, orphan) == []
    private_only = _with_files(
        module,
        **{
            "_other.py": "from ._helpers import helper\n",
            "_helpers.py": private_logger,
        },
    )
    assert _violations(checker.rule_28_file_names, private_only) == []


def test_module_list_controls() -> None:
    corpus = _corpus(
        _golden_module("alpha"),
        _golden_module("beta"),
        _golden_module("gamma"),
    )
    assert checker.rule_37_module_lists(corpus) == []
    core_literal = replace(
        corpus,
        core_files={"contracts/registry.py": "REGISTRY = ('alpha', 'beta', 'gamma')\n"},
    )
    assert any(
        "literal REGISTRY lists 3 module names" in violation
        for violation in checker.rule_37_module_lists(core_literal)
    )
    cli_literal = replace(
        corpus,
        cli_files={"commands/registry.py": "SETTINGS = {'alpha': 1, 'beta': 2, 'gamma': 3}\n"},
    )
    assert any(
        "literal SETTINGS lists 3 module names" in violation
        for violation in checker.rule_37_module_lists(cli_literal)
    )
    script_literal = replace(
        corpus,
        script_files={"other.py": "NAMES = ['alpha', 'beta', 'gamma']\n"},
    )
    assert any(
        "literal NAMES lists 3 module names" in violation
        for violation in checker.rule_37_module_lists(script_literal)
    )
    script_test = replace(
        corpus,
        script_files={"test_helper.py": "NAMES = ['alpha', 'beta', 'gamma']\n"},
    )
    assert checker.rule_37_module_lists(script_test) == []
    catalog = replace(
        corpus,
        core_files={"contracts/module_catalog.py": "MODULE_CATALOG = ('alpha', 'beta', 'gamma')\n"},
    )
    assert checker.rule_37_module_lists(catalog) == []
    harness = replace(
        corpus,
        script_files={
            "check_module_conventions.py": "MODULE_LAYERS = {'alpha': 1, 'beta': 2, 'gamma': 3}\n"
        },
    )
    assert checker.rule_37_module_lists(harness) == []
    registry = replace(
        corpus,
        cli_files={
            "commands/registry.py": (
                "ENTRIES = [\n"
                "    Entry(name='alpha'),\n"
                "    Entry(name='beta'),\n"
                "    Entry(name='gamma'),\n"
                "]\n"
            )
        },
    )
    assert any(
        "literal ENTRIES lists 3 module names" in violation
        for violation in checker.rule_37_module_lists(registry)
    )
    small_registry = replace(
        corpus,
        cli_files={"commands/small_registry.py": "MODULES = ['alpha', 'beta']\n"},
    )
    assert any(
        "literal MODULES lists 2 module names" in violation
        for violation in checker.rule_37_module_lists(small_registry)
    )
    singleton = replace(
        corpus,
        cli_files={"commands/singleton.py": "MODULES = ['alpha']\n"},
    )
    assert any(
        "literal MODULES lists 1 module name" in violation
        for violation in checker.rule_37_module_lists(singleton)
    )
    exclusion = replace(
        corpus,
        core_files={"generator/seam.py": "_NON_SEAM_MODULES = frozenset({'alpha'})\n"},
    )
    assert checker.rule_37_module_lists(exclusion) == []
    returned = replace(
        corpus,
        cli_files={"commands/returned.py": "def get_modules():\n    return ['alpha']\n"},
    )
    assert any(
        "literal return:get_modules lists 1 module name" in violation
        for violation in checker.rule_37_module_lists(returned)
    )
    presentation = replace(
        corpus,
        core_files={
            "apply/steps/env_sync.py": (
                "ENV_EXAMPLE_MODULE_SPECS = (\n"
                "    Spec(module='alpha'),\n"
                "    Spec(module='beta'),\n"
                "    Spec(module='gamma'),\n"
                ")\n"
            ),
            "generator/seam.py": (
                "_SEAM_MODULE_PATHS = (\n"
                "    ('alpha', '{% url one %}'),\n"
                "    ('beta', '{% url two %}'),\n"
                "    ('gamma', '{% url three %}'),\n"
                ")\n"
            ),
        },
    )
    assert checker.rule_37_module_lists(presentation) == []


def test_module_list_template_control() -> None:
    """A module enumeration in a generator `.j2` file fails rule 37 (gap 13)."""
    corpus = _corpus(
        _golden_module("alpha"),
        _golden_module("beta"),
        _golden_module("gamma"),
    )
    template_literal = replace(
        corpus,
        core_files={
            "generator/templates/project_name/sample.j2": (
                "{% for m in ['alpha', 'beta'] %}{{ m }}{% endfor %}\n"
            )
        },
    )
    assert any(
        "literal <template literal> lists 2 module names: alpha, beta" in violation
        for violation in checker.rule_37_module_lists(template_literal)
    )
    template_alternation = replace(
        corpus,
        core_files={
            "generator/templates/project_name/sample.j2": ('re_path(r"^(alpha|beta)/?$", view)\n')
        },
    )
    assert any(
        "literal <template alternation:alpha|beta> lists 2 module names: alpha, beta" in violation
        for violation in checker.rule_37_module_lists(template_alternation)
    )
    non_capturing_alternation = replace(
        corpus,
        core_files={
            "generator/templates/project_name/sample.j2": ('re_path(r"^(?:alpha|beta)/?$", view)\n')
        },
    )
    assert any(
        "literal <template alternation:alpha|beta> lists 2 module names: alpha, beta" in violation
        for violation in checker.rule_37_module_lists(non_capturing_alternation)
    )
    # The exception is bound to the approved orgs reservation, not to every
    # alternation in the host URL template: an unrelated alternation there is
    # still rejected.
    unrelated_alternation = replace(
        corpus,
        core_files={
            "generator/templates/project_name/urls.py.j2": ('re_path(r"^(alpha|beta)/?$", view)\n')
        },
    )
    assert any(
        "lists 2 module names: alpha, beta" in violation
        for violation in checker.rule_37_module_lists(unrelated_alternation)
    )
    orgs_corpus = _corpus(_golden_module("blog"), _golden_module("listings"))
    orgs_reservation = replace(
        orgs_corpus,
        core_files={
            "generator/templates/project_name/urls.py.j2": (
                're_path(r"^orgs/(?!api(?:/|$))[^/]+/(blog|listings|members|settings)/?$", view)\n'
            )
        },
    )
    assert checker.rule_37_module_lists(orgs_reservation) == []
