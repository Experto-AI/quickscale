"""Control cases for the models module-convention rules."""

from __future__ import annotations

import pytest

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import (
    _golden_module,
    _violations,
    _with_files,
)


def test_tenant_meta_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        models=(
            "from quickscale_modules_orgs.models import TenantModel\n\n\n"
            "class Widget(TenantModel):\n"
            "    class Meta:\n"
            "        ordering = ['pk']\n\n"
            "    def __str__(self) -> str:\n"
            "        return 'widget'\n"
        ),
    )
    assert _violations(checker.rule_13_tenant_models, broken)


def test_model_str_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        models=(
            "from quickscale_modules_orgs.models import TenantModel\n\n\n"
            "class Widget(TenantModel):\n"
            "    class Meta(TenantModel.Meta):\n"
            "        ordering = ['pk']\n"
        ),
    )
    assert any(
        "__str__" in violation for violation in _violations(checker.rule_14_model_basics, broken)
    )


def test_literal_choices_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        models=(
            "from quickscale_modules_orgs.models import TenantModel\n\n"
            "WIDGET_CHOICES = ['a', 'b']\n\n\n"
            "class Widget(TenantModel):\n"
            "    class Meta(TenantModel.Meta):\n"
            "        ordering = ['pk']\n\n"
            "    def __str__(self) -> str:\n"
            "        return 'widget'\n"
        ),
    )
    assert any(
        "choice" in violation for violation in _violations(checker.rule_14_model_basics, broken)
    )


def test_upload_to_extension_control() -> None:
    module = _golden_module()
    client_named_models = (
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
    flagged = _with_files(module, models=client_named_models)
    assert any(
        "client filename" in violation
        for violation in _violations(checker.rule_14_model_basics, flagged)
    )

    accepted_models = client_named_models.replace(
        '    return f"widgets/{Path(filename).suffix.lower()}"\n',
        '    return f"widgets/{filename}"\n',
    )
    accepted = _with_files(module, models=accepted_models)
    assert _violations(checker.rule_14_model_basics, accepted) == []


@pytest.mark.parametrize(
    "import_line",
    [
        "from ._uploads import widget_upload_to",
        "from quickscale_modules_demo._uploads import widget_upload_to",
    ],
)
def test_upload_to_extension_via_sibling_builder_control(
    import_line: str,
) -> None:
    module = _golden_module()
    imported_models = (
        "from django.db import models\n"
        "from quickscale_modules_orgs.models import TenantModel\n\n"
        f"{import_line}\n\n\n"
        "class Widget(TenantModel):\n"
        "    image = models.ImageField(upload_to=widget_upload_to)\n\n"
        "    class Meta(TenantModel.Meta):\n"
        "        ordering = ['pk']\n\n"
        "    def __str__(self) -> str:\n"
        "        return 'widget'\n"
    )
    flagged = _with_files(
        module,
        models=imported_models,
        **{
            "_uploads.py": (
                "from pathlib import Path\n\n\n"
                "def widget_upload_to(instance, filename):\n"
                '    return f"widgets/{Path(filename).suffix.lower()}"\n'
            )
        },
    )
    assert any(
        "client filename" in violation
        for violation in _violations(checker.rule_14_model_basics, flagged)
    )

    accepted = _with_files(
        module,
        models=imported_models,
        **{
            "_uploads.py": (
                'def widget_upload_to(instance, filename):\n    return f"widgets/{filename}"\n'
            )
        },
    )
    assert _violations(checker.rule_14_model_basics, accepted) == []


def test_upload_to_extension_via_custom_field_control() -> None:
    module = _golden_module()
    custom_field_models = (
        "from pathlib import Path\n\n"
        "from django.db import models\n"
        "from quickscale_modules_orgs.models import TenantModel\n\n\n"
        "def widget_upload_to(instance, filename):\n"
        '    return f"widgets/{Path(filename).suffix.lower()}"\n\n\n'
        "class WidgetImageField(models.ImageField):\n"
        "    pass\n\n\n"
        "class Widget(TenantModel):\n"
        "    image = WidgetImageField(upload_to=widget_upload_to)\n\n"
        "    class Meta(TenantModel.Meta):\n"
        "        ordering = ['pk']\n\n"
        "    def __str__(self) -> str:\n"
        "        return 'widget'\n"
    )
    flagged = _with_files(module, models=custom_field_models)
    assert any(
        "client filename" in violation
        for violation in _violations(checker.rule_14_model_basics, flagged)
    )

    accepted_models = custom_field_models.replace(
        '    return f"widgets/{Path(filename).suffix.lower()}"\n',
        '    return f"widgets/{filename}"\n',
    )
    accepted = _with_files(module, models=accepted_models)
    assert _violations(checker.rule_14_model_basics, accepted) == []


@pytest.mark.parametrize(
    "import_line",
    [
        "from . import _uploads",
        "from quickscale_modules_demo import _uploads",
        "import quickscale_modules_demo._uploads as _uploads",
    ],
)
def test_upload_to_extension_via_qualified_builder_control(
    import_line: str,
) -> None:
    module = _golden_module()
    qualified_models = (
        "from django.db import models\n"
        "from quickscale_modules_orgs.models import TenantModel\n\n"
        f"{import_line}\n\n\n"
        "class Widget(TenantModel):\n"
        "    image = models.ImageField(upload_to=_uploads.widget_upload_to)\n\n"
        "    class Meta(TenantModel.Meta):\n"
        "        ordering = ['pk']\n\n"
        "    def __str__(self) -> str:\n"
        "        return 'widget'\n"
    )
    flagged = _with_files(
        module,
        models=qualified_models,
        **{
            "_uploads.py": (
                "from pathlib import Path\n\n\n"
                "def widget_upload_to(instance, filename):\n"
                '    return f"widgets/{Path(filename).suffix.lower()}"\n'
            )
        },
    )
    assert any(
        "client filename" in violation
        for violation in _violations(checker.rule_14_model_basics, flagged)
    )

    accepted = _with_files(
        module,
        models=qualified_models,
        **{
            "_uploads.py": (
                'def widget_upload_to(instance, filename):\n    return f"widgets/{filename}"\n'
            )
        },
    )
    assert _violations(checker.rule_14_model_basics, accepted) == []


@pytest.mark.parametrize(
    "import_line",
    [
        "from ._uploads import widget_upload_to as image_path",
        "from quickscale_modules_demo._uploads import widget_upload_to as image_path",
    ],
)
def test_upload_to_extension_via_function_alias_control(
    import_line: str,
) -> None:
    module = _golden_module()
    aliased_models = (
        "from django.db import models\n"
        "from quickscale_modules_orgs.models import TenantModel\n\n"
        f"{import_line}\n\n\n"
        "class Widget(TenantModel):\n"
        "    image = models.ImageField(upload_to=image_path)\n\n"
        "    class Meta(TenantModel.Meta):\n"
        "        ordering = ['pk']\n\n"
        "    def __str__(self) -> str:\n"
        "        return 'widget'\n"
    )
    flagged = _with_files(
        module,
        models=aliased_models,
        **{
            "_uploads.py": (
                "from pathlib import Path\n\n\n"
                "def widget_upload_to(instance, filename):\n"
                '    return f"widgets/{Path(filename).suffix.lower()}"\n'
            )
        },
    )
    assert any(
        "client filename" in violation
        for violation in _violations(checker.rule_14_model_basics, flagged)
    )

    accepted = _with_files(
        module,
        models=aliased_models,
        **{
            "_uploads.py": (
                'def widget_upload_to(instance, filename):\n    return f"widgets/{filename}"\n'
            )
        },
    )
    assert _violations(checker.rule_14_model_basics, accepted) == []


def test_upload_to_extension_same_named_decoy_control() -> None:
    module = _golden_module()
    qualified_models = (
        "from django.db import models\n"
        "from quickscale_modules_orgs.models import TenantModel\n\n"
        "from . import _uploads\n\n\n"
        "class Widget(TenantModel):\n"
        "    image = models.ImageField(upload_to=_uploads.widget_upload_to)\n\n"
        "    class Meta(TenantModel.Meta):\n"
        "        ordering = ['pk']\n\n"
        "    def __str__(self) -> str:\n"
        "        return 'widget'\n"
    )
    accepted = _with_files(
        module,
        models=qualified_models,
        **{
            "_uploads.py": (
                'def widget_upload_to(instance, filename):\n    return f"widgets/{filename}"\n'
            ),
            "_archive.py": (
                "from pathlib import Path\n\n\n"
                "def widget_upload_to(instance, filename):\n"
                '    return f"archive/{Path(filename).suffix.lower()}"\n'
            ),
        },
    )
    assert _violations(checker.rule_14_model_basics, accepted) == []


def test_upload_to_extension_unaliased_dotted_import_control() -> None:
    module = _golden_module()
    dotted_models = (
        "import quickscale_modules_demo._uploads\n"
        "import quickscale_modules_demo._archive\n\n"
        "from django.db import models\n"
        "from quickscale_modules_orgs.models import TenantModel\n\n\n"
        "class Widget(TenantModel):\n"
        "    image = models.ImageField(\n"
        "        upload_to=quickscale_modules_demo._uploads.widget_upload_to\n"
        "    )\n\n"
        "    class Meta(TenantModel.Meta):\n"
        "        ordering = ['pk']\n\n"
        "    def __str__(self) -> str:\n"
        "        return 'widget'\n"
    )
    dirty_builder = (
        "from pathlib import Path\n\n\n"
        "def widget_upload_to(instance, filename):\n"
        '    return f"widgets/{Path(filename).suffix.lower()}"\n'
    )
    clean_builder = 'def widget_upload_to(instance, filename):\n    return f"widgets/{filename}"\n'

    flagged = _with_files(
        module,
        models=dotted_models,
        **{"_uploads.py": dirty_builder, "_archive.py": clean_builder},
    )
    assert any(
        "client filename" in violation
        for violation in _violations(checker.rule_14_model_basics, flagged)
    )

    accepted = _with_files(
        module,
        models=dotted_models,
        **{"_uploads.py": clean_builder, "_archive.py": dirty_builder},
    )
    assert _violations(checker.rule_14_model_basics, accepted) == []


def test_constraint_name_controls() -> None:
    module = _golden_module()
    assert _violations(checker.rule_25_constraint_names, module) == []
    unnamed = _with_files(
        module,
        models=(
            "from django.db import models\n\n\n"
            "class Widget(models.Model):\n"
            "    class Meta:\n"
            "        indexes = [models.Index(fields=['name'])]\n"
        ),
    )
    assert any(
        "Index without a name" in violation
        for violation in _violations(checker.rule_25_constraint_names, unnamed)
    )
    bad_prefix = _with_files(
        module,
        models=(
            "from django.db import models\n\n\n"
            "class Widget(models.Model):\n"
            "    class Meta:\n"
            "        constraints = [\n"
            "            models.UniqueConstraint(fields=['slug'], name='widget_slug_unique')\n"
            "        ]\n"
        ),
    )
    assert any(
        "must start with quickscale_demo_" in violation
        for violation in _violations(checker.rule_25_constraint_names, bad_prefix)
    )
    together = _with_files(
        module,
        models=(
            "from django.db import models\n\n\n"
            "class Widget(models.Model):\n"
            "    class Meta:\n"
            "        unique_together = [('a', 'b')]\n"
        ),
    )
    assert any(
        "uses unique_together" in violation
        for violation in _violations(checker.rule_25_constraint_names, together)
    )
    abstract = _with_files(
        module,
        models=(
            "from django.db import models\n\n\n"
            "class Widget(models.Model):\n"
            "    class Meta:\n"
            "        abstract = True\n"
            "        indexes = [models.Index(fields=['name'])]\n"
        ),
    )
    assert _violations(checker.rule_25_constraint_names, abstract) == []
    abstract_constraint = _with_files(
        module,
        models=(
            "from django.db import models\n\n\n"
            "class Widget(models.Model):\n"
            "    class Meta:\n"
            "        abstract = True\n"
            "        constraints = [models.UniqueConstraint(fields=['slug'])]\n"
        ),
    )
    assert any(
        "UniqueConstraint without a name" in violation
        for violation in _violations(checker.rule_25_constraint_names, abstract_constraint)
    )
