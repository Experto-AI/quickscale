"""Unit tests for the shared org-aware admin helpers.

blog and crm admins import ``make_same_org_validated_form`` and
``OrgAwareAdminMixin`` from ``quickscale_modules_orgs.admin``; these tests pin
the behavior that used to live in each module's private copy.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from django import forms
from django.core.exceptions import ValidationError

from quickscale_modules_orgs.admin import (
    OrgAwareAdminMixin,
    make_same_org_validated_form,
)


class _Org:
    def __init__(self, pk: Any) -> None:
        self.pk = pk


class _Related:
    def __init__(self, organization_id: Any) -> None:
        self.organization_id = organization_id


class _RelatedModel(_Related):
    _meta = object()


class _StubForm(forms.Form):
    """Form base whose ``clean()`` returns the cleaned data supplied at init."""

    instance: Any = None

    def __init__(self, cleaned: dict[str, Any], instance: Any = None) -> None:
        super().__init__()
        self._cleaned = cleaned
        self.instance = instance

    def clean(self) -> dict[str, Any]:
        return self._cleaned


def _validated_form(org_related_fields: list[str]) -> type[forms.Form]:
    return cast(Any, make_same_org_validated_form(_StubForm, org_related_fields))


def test_same_org_form_accepts_matching_fk_and_m2m_values() -> None:
    form_class = _validated_form(["category", "tags"])
    cleaned: dict[str, Any] = {
        "organization": _Org("org-1"),
        "category": _RelatedModel("org-1"),
        "tags": [_RelatedModel("org-1"), _RelatedModel("org-1")],
    }
    assert form_class(cleaned).clean() == cleaned


def test_same_org_form_rejects_foreign_fk_value() -> None:
    form_class = _validated_form(["category"])
    with pytest.raises(ValidationError) as excinfo:
        form_class(
            {"organization": _Org("org-1"), "category": _RelatedModel("org-2")}
        ).clean()
    assert "category must belong to the same organization." in str(excinfo.value)


def test_same_org_form_rejects_foreign_m2m_value() -> None:
    form_class = _validated_form(["tags"])
    with pytest.raises(ValidationError) as excinfo:
        form_class(
            {
                "organization": _Org("org-1"),
                "tags": [_RelatedModel("org-1"), _RelatedModel("org-2")],
            }
        ).clean()
    assert "All tags must belong to the same organization." in str(excinfo.value)


def test_same_org_form_uses_instance_org_on_change_forms() -> None:
    form_class = _validated_form(["category"])
    instance = _OrgInstance("org-1")
    cleaned = {"category": _RelatedModel("org-1")}
    assert form_class(cleaned, instance=instance).clean() == cleaned


def test_same_org_form_skips_validation_without_any_org() -> None:
    form_class = _validated_form(["category"])
    cleaned: dict[str, Any] = {"category": _RelatedModel("org-2")}
    assert form_class(cleaned).clean() == cleaned


def test_same_org_form_tolerates_null_org_related_values() -> None:
    form_class = _validated_form(["category", "tags"])
    cleaned: dict[str, Any] = {
        "organization": _Org("org-1"),
        "category": _RelatedModel(None),
        "tags": None,
    }
    assert form_class(cleaned).clean() == cleaned


class _OrgInstance(_Org):
    """Instance stand-in carrying both an org pk and a row pk."""

    def __init__(self, organization_id: Any) -> None:
        super().__init__("row-pk")
        self.organization_id = organization_id


def _make_admin_form() -> type[forms.Form]:
    """Return a fresh admin form class per call.

    The mixin mutates ``base_fields['organization'].required`` on the class it
    returns for add forms, and Django shares field instances across subclasses
    of the same base, so each call must build its own field instances.
    """

    class _CallAdminForm(forms.Form):
        organization = forms.ChoiceField(choices=(), required=False)
        name = forms.CharField(required=False)

    return _CallAdminForm


class _SuperAdmin:
    """Stand-in for ``admin.ModelAdmin`` recording delegation."""

    def __init__(self) -> None:
        self.saved = False

    def get_form(
        self,
        request: Any,
        obj: Any = None,
        change: bool | None = None,
        **kwargs: Any,
    ) -> type[forms.Form]:
        return _make_admin_form()

    def get_readonly_fields(self, request: Any, obj: Any = None) -> list[str]:
        return ["name"]

    def get_exclude(self, request: Any, obj: Any = None) -> list[str] | None:
        return ["other"]

    def get_fieldsets(self, request: Any, obj: Any = None) -> list[Any]:
        return [(None, {"fields": ["name"]})]

    def save_model(self, request: Any, obj: Any, form: Any, change: bool) -> None:
        self.saved = True


class _Admin(OrgAwareAdminMixin, _SuperAdmin):
    _org_related_fields = ["category"]


class _RelatedMeta:
    many_to_many: list[Any] = []


class _Row:
    _meta = _RelatedMeta()

    def __init__(self, organization_id: Any, related: Any = None) -> None:
        self.organization_id = organization_id
        self.category = related


def test_add_form_requires_organization_and_wraps_form() -> None:
    admin = _Admin()
    form_class = admin.get_form(None, change=False)
    assert form_class.__name__.endswith("SameOrgValidated")
    assert issubclass(form_class, forms.Form)
    assert form_class.base_fields["organization"].required is True


def test_change_form_keeps_organization_optional() -> None:
    admin = _Admin()
    form_class = admin.get_form(None, obj=_OrgInstance("org-1"))
    assert form_class.base_fields["organization"].required is False


def test_form_is_not_wrapped_without_related_fields() -> None:
    class _PlainAdmin(_Admin):
        _org_related_fields: list[str] = []

    form_class = _PlainAdmin().get_form(None, change=False)
    assert issubclass(form_class, forms.Form)
    assert not form_class.__name__.endswith("SameOrgValidated")


def test_readonly_fields_add_organization_only_on_change() -> None:
    admin = _Admin()
    assert admin.get_readonly_fields(None) == ["name"]
    assert admin.get_readonly_fields(None, obj=_OrgInstance("org-1")) == [
        "name",
        "organization",
    ]


def test_exclude_drops_organization_and_collapses_to_none() -> None:
    admin = _Admin()
    assert admin.get_exclude(None) == ["other"]

    class _OnlyOrgSuper(_SuperAdmin):
        def get_exclude(self, request: Any, obj: Any = None) -> list[str] | None:
            return ["organization"]

    class _OnlyOrgExcluded(OrgAwareAdminMixin, _OnlyOrgSuper):
        _org_related_fields = ["category"]

    assert _OnlyOrgExcluded().get_exclude(None) is None


def test_fieldsets_gain_organization_in_first_section() -> None:
    admin = _Admin()
    assert admin.get_fieldsets(None) == [(None, {"fields": ("organization", "name")})]

    class _WithOrganization(_Admin):
        def get_fieldsets(self, request: Any, obj: Any = None) -> list[Any]:
            return [(None, {"fields": ["organization", "name"]})]

    assert _WithOrganization().get_fieldsets(None) == [
        (None, {"fields": ["organization", "name"]})
    ]


def test_save_model_rejects_foreign_fk_before_delegating() -> None:
    admin = _Admin()
    with pytest.raises(ValidationError):
        admin.save_model(None, _Row("org-1", _RelatedModel("org-2")), None, False)
    assert admin.saved is False


def test_save_model_accepts_matching_fk_and_delegates() -> None:
    admin = _Admin()
    admin.save_model(None, _Row("org-1", _RelatedModel("org-1")), None, False)
    assert admin.saved is True


def test_save_model_skips_m2m_fields() -> None:
    class _M2MField:
        def __init__(self, name: str) -> None:
            self.name = name

    class _M2MAdmin(_Admin):
        _org_related_fields = ["tags"]

    class _M2MRow(_Row):
        _meta = type("_Meta", (), {"many_to_many": [_M2MField("tags")]})()

        def __init__(self) -> None:
            super().__init__("org-1")
            self.tags = [_RelatedModel("org-2")]

    admin = _M2MAdmin()
    admin.save_model(None, _M2MRow(), None, False)
    assert admin.saved is True
