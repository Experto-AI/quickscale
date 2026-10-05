"""QuickScale runtime API — shared read-only Django admin behavior.

Module admins for operational snapshot models (billing provider mirrors,
notification delivery records) reuse :class:`ReadOnlyAdminMixin` instead of
each declaring a private copy.  The combined ``quickscale_core.runtime``
facade loads this sub-module lazily, so a process that never touches the
Django admin stack never imports it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django.http import HttpRequest, HttpResponse

if TYPE_CHECKING:
    from django.db.models import Model


class ReadOnlyAdminMixin:
    """Read-only admin behavior for operational snapshot models.

    Concrete admins mix this in ahead of their base ``ModelAdmin`` so add and
    delete stay disabled, every model field is shown read-only (plus the
    subclass's ``_extra_readonly_fields``), and the change view hides the save
    and delete affordances while preserving the caller's extra context.
    """

    _extra_readonly_fields: list[str] = []

    if TYPE_CHECKING:
        # Provided by admin.ModelAdmin in the concrete admin classes.
        model: type[Model]

    def has_add_permission(self, request: HttpRequest) -> bool:
        del request
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: Any | None = None,
    ) -> bool:
        del request, obj
        return False

    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj: Any | None = None,
    ) -> list[str]:
        del request, obj
        model_fields = [field.name for field in self.model._meta.fields]
        return [*model_fields, *self._extra_readonly_fields]

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        merged_context = {
            **(extra_context or {}),
            "show_save": False,
            "show_save_and_add_another": False,
            "show_save_and_continue": False,
            "show_delete": False,
        }
        return cast(
            HttpResponse,
            cast(Any, super()).change_view(
                request,
                object_id,
                form_url=form_url,
                extra_context=merged_context,
            ),
        )
