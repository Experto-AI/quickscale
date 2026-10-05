"""Tests for the shared read-only admin mixin on the runtime facade."""

from __future__ import annotations

from typing import Any, cast

import quickscale_core.runtime as runtime
from quickscale_core.runtime import ReadOnlyAdminMixin
from quickscale_core.runtime import admin as runtime_admin


class _Field:
    def __init__(self, name: str) -> None:
        self.name = name


class _Meta:
    def __init__(self, *names: str) -> None:
        self.fields = [_Field(name) for name in names]


class _Model:
    _meta = _Meta("name", "created_at")


class _RecordingBase:
    """Stand-in for ``admin.ModelAdmin`` recording the delegated change view."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def change_view(
        self,
        request: Any,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> Any:
        self.calls.append((request, object_id, form_url, extra_context))
        return "response"


class _Admin(ReadOnlyAdminMixin, _RecordingBase):
    model = _Model
    _extra_readonly_fields = ["notice"]


def test_facade_resolves_the_mixin_lazily() -> None:
    assert "ReadOnlyAdminMixin" in runtime.__all__
    assert runtime.ReadOnlyAdminMixin is runtime_admin.ReadOnlyAdminMixin


def test_add_and_delete_are_disabled() -> None:
    admin = _Admin()
    assert admin.has_add_permission(cast(Any, None)) is False
    assert admin.has_delete_permission(cast(Any, None)) is False
    assert admin.has_delete_permission(cast(Any, None), object()) is False


def test_readonly_fields_list_model_fields_and_extras() -> None:
    admin = _Admin()
    assert admin.get_readonly_fields(cast(Any, None)) == [
        "name",
        "created_at",
        "notice",
    ]


def test_change_view_merges_context_and_delegates() -> None:
    admin = _Admin()
    request = cast(Any, object())
    response = admin.change_view(request, "42", extra_context={"existing": True})
    assert response == "response"
    assert admin.calls == [
        (
            request,
            "42",
            "",
            {
                "existing": True,
                "show_save": False,
                "show_save_and_add_another": False,
                "show_save_and_continue": False,
                "show_delete": False,
            },
        )
    ]
