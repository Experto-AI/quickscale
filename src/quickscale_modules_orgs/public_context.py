"""Public-context helpers for orgs-owned anonymous/public read operations.

Provides the two sanctioned shapes of a module-owned ``*PublicReadMixin``
(Module Conventions rule 19): :class:`PublicSystemOrgReadMixin` primes the
tenant context for a public page that reads tenant-scoped rows, and
:class:`PublicReadPresentationMixin` declares a public page that reads no
tenant-scoped row at all.

The priming mixin wraps ``dispatch()`` in :func:`~.current_org.org_scope`
which opens a ``transaction.atomic()`` block and primes both the Python
ContextVar and the PostgreSQL GUC for the duration of the view.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterator
from typing import Any


class PublicReadPresentationMixin:
    """Marker base for a public page that reads no tenant-scoped row.

    A module-owned ``*PublicReadMixin`` declares one of two shapes (Module
    Conventions rule 19): it inherits :class:`PublicSystemOrgReadMixin`, which
    primes the public organization's context for a page that reads
    tenant-scoped rows, or it inherits this marker, which declares that the
    page performs no tenant-scoped read — a mount page, or a page that reads
    global rows only.

    The marker primes no context, so a page that later adds a tenant-scoped
    query must move to :class:`PublicSystemOrgReadMixin` instead; rule 19
    refuses a ``*PublicReadMixin`` that declares neither shape.
    """


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

    @contextlib.contextmanager
    def get_public_org_context(
        self,
        org: Any | None = None,
    ) -> Iterator[uuid.UUID | None]:
        """Return a context manager that primes tenant context for public reads.

        Resolves the public-facing org (System org by default) and returns
        a context manager that primes the Python ContextVar and PostgreSQL
        GUC via :func:`~.current_org._tenant_context` for the duration of
        the block.

        This is a convenience accessor for call sites that need manual
        context management instead of the automatic ``dispatch``-level
        wrapping provided by the mixin.

        Parameters
        ----------
        org : Organization or None
            An ``Organization`` instance (or any object with a ``pk``
            attribute).  When ``None`` (the default), the System org
            singleton is resolved via
            ``Organization.objects.get_system_org()``.

        Yields
        ------
        uuid.UUID or None
            The resolved organization UUID, or ``None`` when the System org
            could not be resolved (fail-closed).
        """
        from .current_org import _tenant_context
        from .models import Organization

        if org is not None:
            resolved_id: uuid.UUID | None = org.pk
        else:
            try:
                resolved_id = Organization.objects.get_system_org().pk
            except Exception:
                resolved_id = None

        with _tenant_context(resolved_id):
            yield resolved_id
