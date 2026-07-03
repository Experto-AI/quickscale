"""Public-context helpers for orgs-owned anonymous/public read operations.

SA11.1 provides a plain helper context manager and a CBV mixin that
generalize the proven tenant-context priming idiom from
``social_manifest.py:444-447`` for public/anonymous read paths in other
modules.

The pattern this encapsulates::

    resolved_org_id = (
        org.id if org is not None
        else Organization.objects.get_system_org().id
    )
    with transaction.atomic():
        with tenant_context(resolved_org_id):
            ...  # queries run with ContextVar and DB GUC primed
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterator
from typing import Any

from .current_org import tenant_context


@contextlib.contextmanager
def resolve_public_org_context(
    org: Any | None = None,
) -> Iterator[uuid.UUID | None]:
    """Resolve the public-facing org and prime tenant context for its scope.

    Parameters
    ----------
    org : Organization or None
        An ``Organization`` instance (or any object with a ``pk`` attribute).
        When ``None`` (the default), the System org singleton is resolved
        via ``Organization.objects.get_system_org()``.

    Yields
    ------
    uuid.UUID or None
        The resolved organization UUID, or ``None`` when the System org
        could not be resolved (fail-closed — see below).

    The Python ``ContextVar`` and the PostgreSQL GUC ``app.current_org_id``
    are primed for the duration of the context via ``tenant_context()``.

    **Transaction boundary**: ``tenant_context()`` does **not** wrap in
    ``transaction.atomic()`` — the caller is responsible for managing
    database transaction boundaries.  An active transaction is required
    for the ``SET LOCAL`` commands to succeed.

    **Fail-closed**: if ``org`` is ``None`` **and** the System org cannot
    be resolved (e.g. before migrations have created it), ``None`` is
    yielded and ``tenant_context(None)`` is used.  Tenant-scoped default
    managers return ``.none()`` in this state, preventing accidental
    exposure of all rows.

    Examples
    --------
    Plain-function call site::

        from django.db import transaction
        from quickscale_modules_orgs.public_context import (
            resolve_public_org_context,
        )

        with transaction.atomic():
            with resolve_public_org_context() as org_id:
                posts = Post.objects.all()  # auto-scoped to System org

    Explicit org override::

        with transaction.atomic():
            with resolve_public_org_context(org=my_org) as org_id:
                data = MyModel.objects.filter(...)
    """
    from .models import Organization

    if org is not None:
        resolved_id: uuid.UUID | None = org.pk
    else:
        try:
            resolved_id = Organization.objects.get_system_org().pk
        except Exception:
            # System org not available — fail-closed via None.
            resolved_id = None

    with tenant_context(resolved_id):
        yield resolved_id


class PublicSystemOrgReadMixin:
    """CBV mixin that wraps the entire view dispatch in org-scoped context.

    On ``dispatch()``, the mixin resolves the public-facing organization
    (System org by default) and wraps the entire request handling in
    :func:`~.current_org.org_scope` — which opens a
    ``transaction.atomic()`` block and primes both the Python ContextVar
    and the PostgreSQL GUC for the duration of the view.

    Views that inherit from this mixin can run tenant-scoped queries
    directly in their handler methods without manually managing
    transaction boundaries or tenant context.

    Override :meth:`get_public_org` to provide a different organization
    instance (e.g. resolved from a URL parameter), or to return
    ``None`` for fail-closed behavior.

    Example::

        from django.views import View
        from quickscale_modules_orgs.public_context import (
            PublicSystemOrgReadMixin,
        )

        class BlogPublicListView(PublicSystemOrgReadMixin, View):
            def get(self, request):
                # ContextVar and GUC are already primed for the System org.
                posts = Post.objects.all()  # auto-scoped
                ...
    """

    def get_public_org(self) -> Any | None:
        """Return the Organization instance for this view's public scope.

        Defaults to the System org singleton via
        ``Organization.objects.get_system_org()``.  Override in
        subclasses to resolve a different organization (e.g. from a
        URL kwarg).

        Returns ``None`` so that :func:`~.current_org.org_scope` enters
        fail-closed mode — tenant-scoped managers return ``.none()``.
        """
        from .models import Organization

        try:
            return Organization.objects.get_system_org()
        except Exception:
            return None

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        """Wrap dispatch in ``org_scope()`` for tenant-context isolation.

        Forces ``.render()`` on unrendered ``TemplateResponse`` objects
        while still inside the ``org_scope()`` block so that lazy queryset
        evaluation during template rendering runs with the tenant GUC
        primed.

        **Streamed responses** (e.g. ``StreamingHttpResponse``) are not
        rendered here.  If any view in this mixin hierarchy returns a
        streamed response, the tenant GUC will not cover template
        rendering — QuickScale does not use streamed responses for
        public pages today, so this limitation is documented as a
        future concern.
        """
        from django.template.response import TemplateResponse
        from .current_org import org_scope

        organization = self.get_public_org()
        with org_scope(organization):
            response = super().dispatch(request, *args, **kwargs)  # type: ignore[misc]
            if isinstance(response, TemplateResponse):
                response.render()
            return response

    def get_public_org_context(
        self,
        org: Any | None = None,
    ) -> Iterator[uuid.UUID | None]:
        """Return a context manager that primes tenant context for public reads.

        Wraps :func:`resolve_public_org_context` so that CBV callers can
        invoke it as ``self.get_public_org_context(org)`` without
        importing the module-level function directly.

        This is a convenience accessor for call sites that need manual
        context management instead of the automatic ``dispatch``-level
        wrapping provided by the mixin.

        Parameters
        ----------
        org : Organization or None
            Passed through to :func:`resolve_public_org_context`.

        Yields
        ------
        uuid.UUID or None
            The resolved organization UUID.
        """
        return resolve_public_org_context(org=org)
