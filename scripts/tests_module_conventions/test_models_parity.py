"""
Parity controls for the ``rules_models`` split (SA267).

Rule 13's tenancy scan, rule 14's model-basics clauses, and rule 25's
constraint-name mechanics live in private siblings (``_models_tenancy``,
``_models_basics``, ``_models_constraints``) behind the ``rules_models``
facade.  These controls pin the facade's preserved surface, the split's
structural invariants, and the exact ordered findings of representative
corpora captured from the pre-split module, so a later slice cannot silently
drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
import inspect
import re
from collections.abc import Mapping
from pathlib import Path

import pytest

from scripts import check_module_conventions as checker
from scripts.check_module_conventions import Module
from scripts.module_conventions import (
    _models_basics,
    _models_constraints,
    _models_tenancy,
    core,
    registry,
    rules_models,
)
from scripts.module_conventions.rules_identity import RULE_37_ALLOWED_LITERAL_FILES
from scripts.tests_module_conventions._support import (
    _corpus,
    _golden_module,
    _with_files,
)

SPLIT_SIBLINGS = {
    "_models_basics": _models_basics,
    "_models_constraints": _models_constraints,
    "_models_tenancy": _models_tenancy,
}


FROZEN_SURFACE = (
    "ALLOWED_DERIVED_CHOICE_NAMES",
    "SINGLETON_ORDERING_EXEMPTIONS",
    "_AUTH_MODEL_BASES",
    "_CAMEL_TO_SPACES",
    "_abstract_meta_calls",
    "_assignment_targets",
    "_builder_bindings",
    "_check_constraint_names_checked_field",
    "_check_purpose_names_fields",
    "_condition_tokens",
    "_constraint_owners",
    "_defines_ordering",
    "_defines_str",
    "_django_default_verbose_name",
    "_file_field_class_names",
    "_inherits_ordering",
    "_inherits_str",
    "_is_abstract",
    "_literal_field_tokens",
    "_model_basics_classes",
    "_module_file",
    "_path_suffix_reads",
    "_resolve_upload_to_builder",
    "_token_matches",
    "_upload_to_builders",
    "rule_13_tenant_models",
    "rule_14_model_basics",
    "rule_25_constraint_names",
)

FROZEN_IMPORTED_BINDINGS = (
    "Corpus",
    "MODULE_ABSTRACT_BASES",
    "Mapping",
    "Module",
    "_ancestors",
    "_attribute_chain",
    "_call_func_name",
    "_class_names",
    "_import_package_parts",
    "_keyword",
    "_literal",
    "_meta_class",
    "_model_classes",
    "_parse",
    "_uses_name",
    "ast",
    "re",
)


FROZEN_CORE_HELPERS = (
    "Corpus",
    "MODULE_ABSTRACT_BASES",
    "Module",
    "_ancestors",
    "_attribute_chain",
    "_call_func_name",
    "_class_names",
    "_import_package_parts",
    "_keyword",
    "_literal",
    "_meta_class",
    "_model_classes",
    "_parse",
    "_uses_name",
)


FROZEN_SIGNATURES = {
    "_abstract_meta_calls": "(tree: 'ast.Module') -> 'set[int]'",
    "_assignment_targets": "(statement: 'ast.stmt') -> 'list[ast.Name]'",
    "_builder_bindings": (
        "(tree: 'ast.Module', module_name: 'str', package_files: 'Mapping[str, str]') -> "
        "'dict[str, tuple[str, str | None]]'"
    ),
    "_check_constraint_names_checked_field": (
        "(module_name: 'str', rel: 'str', node: 'ast.Call', name: 'str', purpose_tokens: "
        "'list[str]', violations: 'list[str]') -> 'bool'"
    ),
    "_check_purpose_names_fields": (
        "(module_name: 'str', rel: 'str', node: 'ast.Call', name: 'str', purpose_tokens: "
        "'list[str]', violations: 'list[str]') -> 'None'"
    ),
    "_condition_tokens": "(call: 'ast.Call') -> 'set[str] | None'",
    "_constraint_owners": "(tree: 'ast.Module') -> 'dict[int, str]'",
    "_defines_ordering": "(node: 'ast.ClassDef') -> 'bool'",
    "_defines_str": "(node: 'ast.ClassDef') -> 'bool'",
    "_django_default_verbose_name": "(class_name: 'str') -> 'str'",
    "_file_field_class_names": "(module: 'Module') -> 'set[str]'",
    "_inherits_ordering": (
        "(node: 'ast.ClassDef', classes: 'Mapping[str, ast.ClassDef]', seen: 'frozenset[str]' = "
        "frozenset()) -> 'bool'"
    ),
    "_inherits_str": (
        "(node: 'ast.ClassDef', classes: 'Mapping[str, ast.ClassDef]', seen: 'frozenset[str]' = "
        "frozenset()) -> 'bool'"
    ),
    "_is_abstract": "(node: 'ast.ClassDef') -> 'bool'",
    "_literal_field_tokens": "(call: 'ast.Call') -> 'set[str] | None'",
    "_model_basics_classes": "(tree: 'ast.Module') -> 'list[ast.ClassDef]'",
    "_module_file": (
        "(parts: 'tuple[str, ...]', module_name: 'str', package_files: 'Mapping[str, str]') -> "
        "'str | None'"
    ),
    "_path_suffix_reads": "(node: 'ast.AST') -> 'list[ast.Attribute]'",
    "_resolve_upload_to_builder": (
        "(target: 'ast.expr | None', local_functions: 'Mapping[str, ast.FunctionDef]', bindings: "
        "'Mapping[str, tuple[str, str | None]]', module_name: 'str', package_files: 'Mapping[str, "
        "str]') -> 'tuple[str, str] | None'"
    ),
    "_token_matches": "(token: 'str', candidates: 'set[str]') -> 'bool'",
    "_upload_to_builders": (
        "(module: 'Module', tree: 'ast.Module', field_class_names: 'set[str]') -> 'list[tuple[str, "
        "str]]'"
    ),
    "rule_13_tenant_models": "(corpus: 'Corpus') -> 'list[str]'",
    "rule_14_model_basics": "(corpus: 'Corpus') -> 'list[str]'",
    "rule_25_constraint_names": "(corpus: 'Corpus') -> 'list[str]'",
}


def _models(module: Module, source: str) -> Module:
    return _with_files(module, models=source)


def _constraint_models(constraint_block: str, *, abstract: bool = False) -> str:
    abstract_line = "        abstract = True\n" if abstract else ""
    return (
        "from django.db import models\n\n\n"
        "class Widget(models.Model):\n"
        "    class Meta:\n"
        f"{abstract_line}"
        f"{constraint_block}"
    )


def _index_models(index_line: str) -> str:
    return (
        "from django.db import models\n\n\n"
        "class Widget(models.Model):\n"
        "    class Meta:\n"
        "        indexes = [\n"
        f"{index_line}\n"
        "        ]\n"
    )


def _unique_constraint(name: str) -> str:
    return (
        "        constraints = [\n"
        f"            models.UniqueConstraint(fields=['slug'], name='{name}')\n"
        "        ]\n"
    )


TENANT_REFERENCES = (
    'TENANT = tenant_org_fk()\nMANAGER = TenantManager()\nbase_manager_name = "objects"\n'
)

UPLOAD_MODELS = (
    "from pathlib import Path\n\n"
    "from django.db import models\n"
    "from quickscale_modules_orgs.models import TenantModel\n\n\n"
    "def widget_upload_to(instance, filename):\n"
    '    return f"widgets/{Path(filename).suffix.lower()}"\n\n\n'
    "class Widget(TenantModel):\n"
    "    image = models.ImageField(upload_to=widget_upload_to)\n\n"
    "    class Meta(TenantModel.Meta):\n"
    "        ordering = ['pk']\n\n"
    "    def __str__(self) -> str:\n"
    "        return 'widget'\n"
)

UPLOAD_SIBLING_MODELS = (
    "from django.db import models\n"
    "from quickscale_modules_orgs.models import TenantModel\n\n"
    "from ._uploads import widget_upload_to\n\n\n"
    "class Widget(TenantModel):\n"
    "    image = models.ImageField(upload_to=widget_upload_to)\n\n"
    "    class Meta(TenantModel.Meta):\n"
    "        ordering = ['pk']\n\n"
    "    def __str__(self) -> str:\n"
    "        return 'widget'\n"
)

UPLOAD_SIBLING_SOURCE = (
    "from pathlib import Path\n\n\n"
    "def widget_upload_to(instance, filename):\n"
    '    return f"widgets/{Path(filename).suffix.lower()}"\n'
)


def _user_relation_models(related_name: str | None) -> str:
    argument = "" if related_name is None else f", related_name={related_name!r}"
    return (
        "from django.conf import settings\n"
        "from django.db import models\n"
        "from quickscale_modules_orgs.models import TenantModel\n\n\n"
        "class Widget(TenantModel):\n"
        f"    owner = models.ForeignKey(settings.AUTH_USER_MODEL, "
        f"on_delete=models.CASCADE{argument})\n\n"
        "    class Meta(TenantModel.Meta):\n"
        "        ordering = ['pk']\n\n"
        "    def __str__(self) -> str:\n"
        "        return 'widget'\n"
    )


def _uuid_models() -> str:
    return (
        "import uuid\n\n"
        "from django.db import models\n"
        "from quickscale_modules_orgs.models import TenantModel\n\n\n"
        "class Widget(TenantModel):\n"
        "    id = models.UUIDField(primary_key=True, default=uuid.uuid4)\n\n"
        "    class Meta(TenantModel.Meta):\n"
        "        ordering = ['pk']\n\n"
        "    def __str__(self) -> str:\n"
        "        return 'widget'\n"
    )


def _app_label_models() -> str:
    return (
        _golden_module()
        .files["models.py"]
        .replace(
            "    class Meta(TenantModel.Meta):\n        ordering = ['pk']",
            "    class Meta(TenantModel.Meta):\n        app_label = 'quickscale_demo'\n"
            "        ordering = ['pk']",
        )
    )


def _verbose_singular_models() -> str:
    return (
        _golden_module()
        .files["models.py"]
        .replace(
            "    class Meta(TenantModel.Meta):\n        ordering = ['pk']",
            "    class Meta(TenantModel.Meta):\n        verbose_name = 'Widget'\n"
            "        ordering = ['pk']",
        )
    )


def _verbose_plural_models() -> str:
    return (
        _golden_module()
        .files["models.py"]
        .replace(
            "    class Meta(TenantModel.Meta):\n        ordering = ['pk']",
            "    class Meta(TenantModel.Meta):\n        verbose_name_plural = 'widgets'\n"
            "        ordering = ['pk']",
        )
    )


def _datetime_models() -> str:
    return (
        _golden_module()
        .files["models.py"]
        .replace(
            "    class Meta(TenantModel.Meta):",
            "    published_date = models.DateTimeField(auto_now_add=True)\n\n"
            "    class Meta(TenantModel.Meta):",
        )
    )


def _no_ordering_models() -> str:
    return _golden_module().files["models.py"].replace("        ordering = ['pk']\n", "")


def _no_str_models() -> str:
    return (
        _golden_module()
        .files["models.py"]
        .replace("    def __str__(self) -> str:\n        return 'widget'\n", "")
    )


AUTH_BASE_MODELS = (
    "from django.contrib.auth.models import AbstractUser\n\n\n"
    "class Account(AbstractUser):\n"
    "    class Meta:\n"
    "        app_label = 'quickscale_demo'\n"
    "        verbose_name = 'Account'\n"
)

CHOICES_MODELS = (
    "from quickscale_modules_orgs.models import TenantModel\n\n"
    "WIDGET_CHOICES = ['a', 'b']\n\n\n"
    "class Widget(TenantModel):\n"
    "    class Meta(TenantModel.Meta):\n"
    "        ordering = ['pk']\n\n"
    "    def __str__(self) -> str:\n"
    "        return 'widget'\n"
)

GETTEXT_VIEWS = (
    "from django.utils.translation import gettext\n\n\n"
    "def label() -> str:\n"
    "    return gettext('demo')\n"
)

NO_META_INHERIT_MODELS = (
    "from quickscale_modules_orgs.models import TenantModel\n\n\n"
    "class Widget(TenantModel):\n"
    "    class Meta:\n"
    "        ordering = ['pk']\n\n"
    "    def __str__(self) -> str:\n"
    "        return 'widget'\n"
)

CASE_BUILDERS = {
    "clean": lambda: _corpus(_golden_module()),
    "tenant_meta_no_inherit": lambda: _corpus(_models(_golden_module(), NO_META_INHERIT_MODELS)),
    "tenant_reference_calls": lambda: _corpus(
        _with_files(_golden_module(), views=TENANT_REFERENCES)
    ),
    "tenant_reference_orgs_allowed": lambda: _corpus(
        _with_files(_golden_module("orgs"), views=TENANT_REFERENCES)
    ),
    "gettext_use": lambda: _corpus(_with_files(_golden_module(), views=GETTEXT_VIEWS)),
    "literal_choices": lambda: _corpus(_models(_golden_module(), CHOICES_MODELS)),
    "upload_client_filename": lambda: _corpus(_models(_golden_module(), UPLOAD_MODELS)),
    "upload_sibling_builder": lambda: _corpus(
        _with_files(
            _golden_module(),
            models=UPLOAD_SIBLING_MODELS,
            **{"_uploads.py": UPLOAD_SIBLING_SOURCE},
        )
    ),
    "user_relation_missing_related_name": lambda: _corpus(
        _models(_golden_module(), _user_relation_models(None))
    ),
    "user_relation_plus": lambda: _corpus(_models(_golden_module(), _user_relation_models("+"))),
    "user_relation_stem": lambda: _corpus(
        _models(_golden_module(), _user_relation_models("quickscale_demo_owner"))
    ),
    "uuid_primary_key": lambda: _corpus(_models(_golden_module(), _uuid_models())),
    "app_label": lambda: _corpus(_models(_golden_module(), _app_label_models())),
    "verbose_name_default": lambda: _corpus(_models(_golden_module(), _verbose_singular_models())),
    "verbose_name_plural_default": lambda: _corpus(
        _models(_golden_module(), _verbose_plural_models())
    ),
    "datetime_suffix": lambda: _corpus(_models(_golden_module(), _datetime_models())),
    "no_ordering": lambda: _corpus(_models(_golden_module(), _no_ordering_models())),
    "no_str": lambda: _corpus(_models(_golden_module(), _no_str_models())),
    "auth_base_meta": lambda: _corpus(_models(_golden_module(), AUTH_BASE_MODELS)),
    "index_unnamed": lambda: _corpus(
        _models(_golden_module(), _index_models("            models.Index(fields=['name']),"))
    ),
    "index_name_shape": lambda: _corpus(
        _models(
            _golden_module(),
            _index_models("            models.Index(fields=['name'], name='idx_widget'),"),
        )
    ),
    "index_name_too_long": lambda: _corpus(
        _models(
            _golden_module(),
            _index_models(
                "            models.Index(fields=['name'], "
                "name='qs_demo_widget_some_very_long_field_name_idx'),"
            ),
        )
    ),
    "unique_together": lambda: _corpus(
        _models(
            _golden_module(),
            _constraint_models("        unique_together = [('a', 'b')]\n"),
        )
    ),
    "together_and_unnamed": lambda: _corpus(
        _models(
            _golden_module(),
            _constraint_models(
                "        unique_together = [('a', 'b')]\n"
                "        indexes = [models.Index(fields=['name'])]\n"
            ),
        )
    ),
    "constraint_prefix": lambda: _corpus(
        _models(_golden_module(), _constraint_models(_unique_constraint("widget_slug_unique")))
    ),
    "constraint_org_token": lambda: _corpus(
        _models(
            _golden_module(),
            _constraint_models(_unique_constraint("quickscale_demo_widget_org_unique")),
        )
    ),
    "constraint_org_and_suffix": lambda: _corpus(
        _models(
            _golden_module(),
            _constraint_models(_unique_constraint("quickscale_demo_widget_org")),
        )
    ),
    "constraint_no_unique_suffix": lambda: _corpus(
        _models(
            _golden_module(),
            _constraint_models(_unique_constraint("quickscale_demo_widget_slug")),
        )
    ),
    "constraint_unique_inside": lambda: _corpus(
        _models(
            _golden_module(),
            _constraint_models(_unique_constraint("quickscale_demo_widget_unique_slug_unique")),
        )
    ),
    "constraint_suffix_only": lambda: _corpus(
        _models(
            _golden_module(),
            _constraint_models(_unique_constraint("quickscale_demo_widget_unique")),
        )
    ),
    "constraint_wrong_field": lambda: _corpus(
        _models(
            _golden_module(),
            _constraint_models(_unique_constraint("quickscale_demo_widget_title_unique")),
        )
    ),
    "constraint_name_too_long": lambda: _corpus(
        _models(
            _golden_module(),
            _constraint_models(
                _unique_constraint("quickscale_demo_widget_" + "a" * 60 + "_unique")
            ),
        )
    ),
    "check_constraint_wrong_field": lambda: _corpus(
        _models(
            _golden_module(),
            _constraint_models(
                "        constraints = [\n"
                "            models.CheckConstraint(\n"
                "                condition=models.Q(quantity__gte=0),\n"
                "                name='quickscale_demo_widget_price_positive',\n"
                "            )\n"
                "        ]\n"
            ),
        )
    ),
    "abstract_index_unnamed_allowed": lambda: _corpus(
        _models(
            _golden_module(),
            _constraint_models(
                "        indexes = [models.Index(fields=['name'])]\n", abstract=True
            ),
        )
    ),
    "abstract_constraint_unnamed": lambda: _corpus(
        _models(
            _golden_module(),
            _constraint_models(
                "        constraints = [models.UniqueConstraint(fields=['slug'])]\n", abstract=True
            ),
        )
    ),
}


EXACT_FINDINGS = (
    ("clean", "rule_13_tenant_models", ()),
    ("clean", "rule_14_model_basics", ()),
    ("clean", "rule_25_constraint_names", ()),
    (
        "tenant_meta_no_inherit",
        "rule_13_tenant_models",
        ("rule 13: demo: Widget.Meta does not inherit the base Meta",),
    ),
    (
        "tenant_reference_calls",
        "rule_13_tenant_models",
        (
            "rule 13: demo: views.py retypes base_manager_name",
            "rule 13: demo: views.py calls tenant_org_fk",
            "rule 13: demo: views.py constructs TenantManager",
        ),
    ),
    ("tenant_reference_orgs_allowed", "rule_13_tenant_models", ()),
    ("gettext_use", "rule_14_model_basics", ("rule 14: demo: views.py uses gettext",)),
    (
        "literal_choices",
        "rule_14_model_basics",
        ("rule 14: demo: WIDGET_CHOICES is a literal choice list",),
    ),
    (
        "upload_client_filename",
        "rule_14_model_basics",
        (
            "rule 14: demo: models.py:widget_upload_to takes the upload extension from the client "
            "filename (line 8)",
        ),
    ),
    (
        "upload_sibling_builder",
        "rule_14_model_basics",
        (
            "rule 14: demo: _uploads.py:widget_upload_to takes the upload extension from the "
            "client filename (line 5)",
        ),
    ),
    (
        "user_relation_missing_related_name",
        "rule_14_model_basics",
        ("rule 14: demo: user relation without an explicit related_name",),
    ),
    ("user_relation_plus", "rule_14_model_basics", ()),
    ("user_relation_stem", "rule_14_model_basics", ()),
    ("uuid_primary_key", "rule_14_model_basics", ("rule 14: demo: UUID primary key outside orgs",)),
    ("app_label", "rule_14_model_basics", ("rule 14: demo: Widget.Meta sets app_label",)),
    (
        "verbose_name_default",
        "rule_14_model_basics",
        ("rule 14: demo: Widget.Meta.verbose_name repeats Django's default",),
    ),
    (
        "verbose_name_plural_default",
        "rule_14_model_basics",
        ("rule 14: demo: Widget.Meta.verbose_name_plural repeats Django's default",),
    ),
    (
        "datetime_suffix",
        "rule_14_model_basics",
        ("rule 14: demo: Widget.published_date is a DateTimeField without the _at suffix",),
    ),
    ("no_ordering", "rule_14_model_basics", ("rule 14: demo: Widget declares no Meta.ordering",)),
    ("no_str", "rule_14_model_basics", ("rule 14: demo: Widget defines no __str__",)),
    (
        "auth_base_meta",
        "rule_14_model_basics",
        (
            "rule 14: demo: Account.Meta sets app_label",
            "rule 14: demo: Account.Meta.verbose_name repeats Django's default",
        ),
    ),
    (
        "index_unnamed",
        "rule_25_constraint_names",
        ("rule 25: demo: models.py:7 Index without a name",),
    ),
    (
        "index_name_shape",
        "rule_25_constraint_names",
        ("rule 25: demo: models.py:7 index 'idx_widget' must be qs_demo_<model>_<field>_idx",),
    ),
    (
        "index_name_too_long",
        "rule_25_constraint_names",
        (
            "rule 25: demo: models.py:7 index 'qs_demo_widget_some_very_long_field_name_idx' "
            "exceeds Django's 30-character limit",
        ),
    ),
    (
        "unique_together",
        "rule_25_constraint_names",
        ("rule 25: demo: models.py:6 uses unique_together",),
    ),
    (
        "together_and_unnamed",
        "rule_25_constraint_names",
        (
            "rule 25: demo: models.py:6 uses unique_together",
            "rule 25: demo: models.py:7 Index without a name",
        ),
    ),
    (
        "constraint_prefix",
        "rule_25_constraint_names",
        (
            "rule 25: demo: models.py:7 constraint 'widget_slug_unique' must start with "
            "quickscale_demo_widget_",
        ),
    ),
    (
        "constraint_org_token",
        "rule_25_constraint_names",
        (
            "rule 25: demo: models.py:7 constraint 'quickscale_demo_widget_org_unique' names the "
            "organization field as 'org'",
            "rule 25: demo: models.py:7 constraint 'quickscale_demo_widget_org_unique' purpose "
            "token 'org' names no constrained field",
        ),
    ),
    (
        "constraint_org_and_suffix",
        "rule_25_constraint_names",
        (
            "rule 25: demo: models.py:7 constraint 'quickscale_demo_widget_org' names the "
            "organization field as 'org'",
            "rule 25: demo: models.py:7 constraint 'quickscale_demo_widget_org' must end with "
            "_unique",
        ),
    ),
    (
        "constraint_no_unique_suffix",
        "rule_25_constraint_names",
        (
            "rule 25: demo: models.py:7 constraint 'quickscale_demo_widget_slug' must end with "
            "_unique",
        ),
    ),
    (
        "constraint_unique_inside",
        "rule_25_constraint_names",
        (
            "rule 25: demo: models.py:7 constraint 'quickscale_demo_widget_unique_slug_unique' "
            "uses 'unique' outside the _unique suffix",
        ),
    ),
    (
        "constraint_suffix_only",
        "rule_25_constraint_names",
        (
            "rule 25: demo: models.py:7 constraint 'quickscale_demo_widget_unique' purpose names "
            "no constrained field",
        ),
    ),
    (
        "constraint_wrong_field",
        "rule_25_constraint_names",
        (
            "rule 25: demo: models.py:7 constraint 'quickscale_demo_widget_title_unique' purpose "
            "token 'title' names no constrained field",
        ),
    ),
    (
        "constraint_name_too_long",
        "rule_25_constraint_names",
        (
            "rule 25: demo: models.py:7 constraint "
            "'quickscale_demo_widget_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa_u"
            "nique' exceeds PostgreSQL's 63-character limit",
        ),
    ),
    (
        "check_constraint_wrong_field",
        "rule_25_constraint_names",
        (
            "rule 25: demo: models.py:7 constraint 'quickscale_demo_widget_price_positive' purpose "
            "names no checked field",
        ),
    ),
    ("abstract_index_unnamed_allowed", "rule_25_constraint_names", ()),
    (
        "abstract_constraint_unnamed",
        "rule_25_constraint_names",
        ("rule 25: demo: models.py:7 UniqueConstraint without a name",),
    ),
)


def test_facade_publishes_the_pre_split_surface() -> None:
    """The facade's ``__all__`` is the pre-split module's own name set."""
    assert rules_models.__all__ == FROZEN_SURFACE
    for name in FROZEN_SURFACE:
        assert getattr(rules_models, name) is not None


def test_facade_preserves_the_pre_split_imported_bindings() -> None:
    """The pre-split module's own imports stay importable through the facade."""
    assert rules_models.ast is ast
    assert rules_models.re is re
    assert rules_models.Mapping is Mapping
    assert rules_models.Corpus is core.Corpus
    for name in FROZEN_IMPORTED_BINDINGS:
        assert getattr(rules_models, name) is not None
    for name in FROZEN_CORE_HELPERS:
        assert getattr(rules_models, name) is getattr(core, name)


def test_frozen_callable_signatures_are_unchanged() -> None:
    """Each pre-split callable keeps its pre-split signature through the facade."""
    assert {
        name: str(inspect.signature(getattr(rules_models, name))) for name in FROZEN_SIGNATURES
    } == FROZEN_SIGNATURES


def test_rule_37_exempts_only_the_facade() -> None:
    """The split siblings stay inside rule 37's closed world."""
    assert ("scripts", "module_conventions/rules_models.py") in RULE_37_ALLOWED_LITERAL_FILES
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
                assert node.module.split(".")[-1] not in {"rules_models", "registry"}, (
                    name,
                    node.lineno,
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[-1] not in {"rules_models", "registry"}, (
                        name,
                        node.lineno,
                    )


def test_moved_constants_keep_their_sibling_identity() -> None:
    """The facade's constants are the sibling objects, not copies."""
    for name in (
        "ALLOWED_DERIVED_CHOICE_NAMES",
        "SINGLETON_ORDERING_EXEMPTIONS",
        "_AUTH_MODEL_BASES",
        "_CAMEL_TO_SPACES",
    ):
        assert getattr(rules_models, name) is getattr(_models_basics, name)


def test_orchestrators_and_helpers_keep_their_homes() -> None:
    """Rules 13, 14, and 25 stay orchestrated by the facade."""
    for name in (
        "rule_13_tenant_models",
        "rule_14_model_basics",
        "rule_25_constraint_names",
    ):
        assert getattr(rules_models, name).__module__ == ("scripts.module_conventions.rules_models")
    for name in (
        "_tenant_reference_violations",
        "_tenant_meta_violations",
    ):
        assert getattr(rules_models, name).__module__ == (
            "scripts.module_conventions._models_tenancy"
        )
    for name in (
        "_django_default_verbose_name",
        "_assignment_targets",
        "_model_basics_classes",
        "_is_abstract",
        "_file_field_class_names",
        "_module_file",
        "_builder_bindings",
        "_resolve_upload_to_builder",
        "_upload_to_builders",
        "_path_suffix_reads",
        "_defines_str",
        "_inherits_str",
        "_defines_ordering",
        "_inherits_ordering",
        "_gettext_violations",
        "_upload_extension_violations",
        "_choice_list_violations",
        "_user_relation_violations",
        "_uuid_primary_key_violations",
        "_model_meta_violations",
        "_model_presentation_violations",
    ):
        assert getattr(rules_models, name).__module__ == (
            "scripts.module_conventions._models_basics"
        )
    for name in (
        "_literal_field_tokens",
        "_condition_tokens",
        "_constraint_owners",
        "_abstract_meta_calls",
        "_token_matches",
        "_check_purpose_names_fields",
        "_check_constraint_names_checked_field",
        "_duplicate_keyword_violations",
        "_constraint_call_violations",
    ):
        assert getattr(rules_models, name).__module__ == (
            "scripts.module_conventions._models_constraints"
        )


def test_registry_and_entrypoint_read_the_facade() -> None:
    """The registry's detectors are the facade callables, not siblings."""
    detectors = {rule.number: rule.detector for rule in registry.RULES}
    for number, name in (
        (13, "rule_13_tenant_models"),
        (14, "rule_14_model_basics"),
        (25, "rule_25_constraint_names"),
    ):
        assert detectors[number] is getattr(rules_models, name)
        assert getattr(checker, name) is getattr(rules_models, name)


@pytest.mark.parametrize(
    ("case", "detector", "expected"),
    EXACT_FINDINGS,
    ids=[f"{case}-{detector}" for case, detector, _ in EXACT_FINDINGS],
)
def test_detector_findings_are_exact_and_ordered(
    case: str, detector: str, expected: tuple[str, ...]
) -> None:
    corpus = CASE_BUILDERS[case]()
    assert getattr(rules_models, detector)(corpus) == list(expected)
