"""Tests for the generic module-owned admin shortcut tag (SA320)."""

from __future__ import annotations

from pathlib import Path

import django
import pytest
from django.conf import settings as django_settings
from django.template import engines
from django.test import override_settings

if not django_settings.configured:
    django_settings.configure(
        INSTALLED_APPS=[],
        TEMPLATES=[],
        USE_I18N=False,
        SECRET_KEY="test-admin-tags",
    )
django.setup()


def _templates(directory: Path) -> list[dict[str, object]]:
    return [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "APP_DIRS": False,
            "DIRS": [str(directory)],
            "OPTIONS": {
                "libraries": {"quickscale_admin": "quickscale_core.runtime.admin_tags"}
            },
        }
    ]


def test_renders_a_module_owned_shortcut_with_the_page_context(tmp_path: Path) -> None:
    shortcut = tmp_path / "admin" / "demo" / "quickscale_shortcut.html"
    shortcut.parent.mkdir(parents=True)
    shortcut.write_text(
        "{% if quickscale_admin_page == 'app_index' %}"
        '<a href="/admin/demo/">Demo</a>'
        "{% endif %}"
    )

    with override_settings(TEMPLATES=_templates(tmp_path)):
        template = engines["django"].from_string(
            "{% load quickscale_admin %}{% module_admin_shortcut 'demo' 'app_index' %}"
        )
        rendered = template.render({})

    assert '<a href="/admin/demo/">Demo</a>' in rendered


def test_missing_module_template_renders_nothing(tmp_path: Path) -> None:
    with override_settings(TEMPLATES=_templates(tmp_path)):
        template = engines["django"].from_string(
            "{% load quickscale_admin %}{% module_admin_shortcut 'demo' 'index' %}"
        )
        assert template.render({}) == ""


@pytest.mark.parametrize("app_label", ["", "../escape", "Demo", "demo/extra"])
def test_invalid_app_label_renders_nothing(tmp_path: Path, app_label: str) -> None:
    with override_settings(TEMPLATES=_templates(tmp_path)):
        rendered = (
            engines["django"]
            .from_string(
                "{% load quickscale_admin %}{% module_admin_shortcut label 'index' %}"
            )
            .render({"label": app_label})
        )

    assert rendered == ""
