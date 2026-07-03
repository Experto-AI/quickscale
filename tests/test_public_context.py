"""SA11.1 — Tests for orgs-owned public-context helpers.

Verifies the ``resolve_public_org_context`` context manager, the
``PublicSystemOrgReadMixin`` CBV seam, and the acceptance contract:
* Correct org resolution (explicit org, System org fallback).
* Real tenant-scoped queries return rows under the helper.
* Fail-closed (``.none()``-equivalent) when no org resolves.
* Mixin ``dispatch()`` wraps the view in ``org_scope()``.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.db import transaction
from django.http import HttpResponse
from django.test import RequestFactory
from django.views import View

from quickscale_modules_orgs.current_org import get_current_org_id
from quickscale_modules_orgs.models import Organization
from quickscale_modules_orgs.public_context import (
    PublicSystemOrgReadMixin,
    resolve_public_org_context,
)


# =========================================================================
# resolve_public_org_context — resolution and ContextVar priming
# =========================================================================


@pytest.mark.django_db
class TestResolvePublicOrgContext:
    """Tests for the ``resolve_public_org_context`` context manager."""

    def test_explicit_org_yields_org_id(self) -> None:
        """When a concrete org is passed, its pk is yielded."""
        org = Organization.objects.create(name="Alpha", slug="alpha")

        with transaction.atomic():
            with resolve_public_org_context(org=org) as resolved_id:
                assert resolved_id == org.pk

    def test_explicit_org_primes_context_var(self) -> None:
        """Inside the context the ContextVar reflects the passed org."""
        org = Organization.objects.create(name="Beta", slug="beta")

        with transaction.atomic():
            with resolve_public_org_context(org=org):
                assert get_current_org_id() == org.pk

    def test_no_org_resolves_system_org(self) -> None:
        """When org is omitted the System org singleton is resolved."""
        system_org = Organization.objects.get_system_org()

        with transaction.atomic():
            with resolve_public_org_context() as resolved_id:
                assert resolved_id == system_org.pk

    def test_no_org_primes_context_var(self) -> None:
        """Inside the context the ContextVar reflects the System org."""
        system_org = Organization.objects.get_system_org()

        with transaction.atomic():
            with resolve_public_org_context():
                assert get_current_org_id() == system_org.pk

    def test_context_var_restored_after_exit(self) -> None:
        """After the context exits the ContextVar returns to its prior value."""
        prior = get_current_org_id()
        org = Organization.objects.create(name="Gamma", slug="gamma")

        with transaction.atomic():
            with resolve_public_org_context(org=org):
                assert get_current_org_id() == org.pk

        assert get_current_org_id() == prior, (
            "ContextVar should be restored after context exit."
        )

    def test_explicit_none_falls_back_to_system_org(self) -> None:
        """When org=None is passed explicitly the System org is resolved."""
        system_org = Organization.objects.get_system_org()

        with transaction.atomic():
            with resolve_public_org_context(org=None) as resolved_id:
                assert resolved_id == system_org.pk


# =========================================================================
# resolve_public_org_context — real tenant-scoped query behaviour
# =========================================================================


@pytest.mark.django_db
class TestTenantScopedQuery:
    """Acceptance: a real tenant-scoped query returns rows under the
    helper, and ``.none()``-equivalent behaviour is preserved when no
    org resolves."""

    def _create_tenant_category(self, org: Organization) -> object:
        """Create a tenant-scoped Category for *org* (bypasses scoping)."""
        from quickscale_modules_blog.models import Category

        return Category.all_objects.create(
            organization=org,
            name="Test Category",
            slug="test-category",
        )

    def test_tenant_query_returns_rows_with_explicit_org(self) -> None:
        """Inside the helper context with an explicit org, a tenant-scoped
        query returns rows belonging to that org."""
        from quickscale_modules_blog.models import Category

        org = Organization.objects.create(name="Query-Test", slug="query-test")
        cat = self._create_tenant_category(org)

        with transaction.atomic():
            with resolve_public_org_context(org=org):
                assert list(Category.objects.all()) == [cat]
                assert Category.objects.count() == 1

    def test_tenant_query_excludes_other_org_data(self) -> None:
        """Inside the helper context, rows from a different org are not
        visible."""
        from quickscale_modules_blog.models import Category

        org = Organization.objects.create(name="Query-Own", slug="query-own")
        other = Organization.objects.create(name="Query-Other", slug="query-other")
        cat = self._create_tenant_category(org)
        self._create_tenant_category(other)  # should not appear

        with transaction.atomic():
            with resolve_public_org_context(org=org):
                assert list(Category.objects.all()) == [cat]

    def test_fail_closed_when_no_org_resolves(self) -> None:
        """When the System org cannot be resolved (``get_system_org()``
        raises), the helper yields ``None`` and tenant-scoped managers
        return ``.none()``."""
        from quickscale_modules_blog.models import Category

        org = Organization.objects.create(name="Fail-Closed", slug="fail-closed")
        self._create_tenant_category(org)

        with patch.object(
            Organization.objects,
            "get_system_org",
            side_effect=Exception("Simulated: system org unavailable"),
        ):
            with transaction.atomic():
                with resolve_public_org_context() as resolved_id:
                    assert resolved_id is None
                    assert Category.objects.count() == 0
                    assert list(Category.objects.all()) == []


# =========================================================================
# PublicSystemOrgReadMixin — dispatch lifecycle seam
# =========================================================================


@pytest.mark.django_db
class TestPublicSystemOrgReadMixinDispatch:
    """Tests for the ``PublicSystemOrgReadMixin`` CBV dispatch lifecycle."""

    def test_dispatch_wraps_in_org_scope(self) -> None:
        """The mixin wraps dispatch in ``org_scope()`` so the handler
        sees the primed ContextVar."""
        org = Organization.objects.create(name="CBV-Dispatch", slug="cbv-dispatch")
        captured: dict[str, object] = {}

        class TestView(PublicSystemOrgReadMixin, View):
            def get_public_org(self) -> Organization:
                return org

            def get(self, request: object) -> HttpResponse:
                captured["org_id"] = get_current_org_id()
                return HttpResponse("ok")

        request = RequestFactory().get("/")
        response = TestView.as_view()(request)

        assert response.status_code == 200
        assert captured["org_id"] == org.pk

    def test_dispatch_restores_context_after_response(self) -> None:
        """After the view returns, the prior ContextVar value is restored."""
        prior = get_current_org_id()
        org = Organization.objects.create(name="CBV-Restore", slug="cbv-restore")

        class TestView(PublicSystemOrgReadMixin, View):
            def get_public_org(self) -> Organization:
                return org

            def get(self, request: object) -> HttpResponse:
                return HttpResponse("ok")

        request = RequestFactory().get("/")
        TestView.as_view()(request)

        assert get_current_org_id() == prior, (
            "ContextVar should be restored after dispatch returns."
        )

    def test_tenant_scoped_query_in_mixin_view(self) -> None:
        """A view using the mixin can run tenant-scoped queries in its
        handler and see rows for the resolved org."""
        from quickscale_modules_blog.models import Category

        org = Organization.objects.create(name="CBV-Query", slug="cbv-query")
        cat = Category.all_objects.create(
            organization=org,
            name="CBV Cat",
            slug="cbv-cat",
        )
        captured: dict[str, object] = {}

        class TestView(PublicSystemOrgReadMixin, View):
            def get_public_org(self) -> Organization:
                return org

            def get(self, request: object) -> HttpResponse:
                captured["rows"] = list(Category.objects.all())
                captured["count"] = Category.objects.count()
                return HttpResponse("ok")

        request = RequestFactory().get("/")
        response = TestView.as_view()(request)

        assert response.status_code == 200
        assert captured["rows"] == [cat]
        assert captured["count"] == 1

    def test_fail_closed_mixin_dispatch(self) -> None:
        """When ``get_public_org()`` returns ``None``, the mixin enters
        fail-closed mode — tenant-scoped queries return zero rows."""
        from quickscale_modules_blog.models import Category

        org = Organization.objects.create(name="CBV-Fail", slug="cbv-fail")
        Category.all_objects.create(
            organization=org,
            name="Should Not Appear",
            slug="should-not-appear",
        )
        captured: dict[str, object] = {}

        class TestView(PublicSystemOrgReadMixin, View):
            def get_public_org(self) -> None:
                return None

            def get(self, request: object) -> HttpResponse:
                captured["rows"] = list(Category.objects.all())
                captured["count"] = Category.objects.count()
                return HttpResponse("ok")

        request = RequestFactory().get("/")
        response = TestView.as_view()(request)

        assert response.status_code == 200
        assert captured["rows"] == []
        assert captured["count"] == 0

    def test_mixin_forces_template_response_render(self) -> None:
        """Prove ``TemplateResponse.render()`` is called inside
        ``org_scope()`` so lazy queryset evaluation during template
        rendering sees the primed tenant context.  (Closes
        CR-SA11.1-002; strengthened by CR-SA11.1-003.)

        Without the render-forcing fix, a ``TemplateResponse`` returned
        from ``dispatch()`` would be rendered *after* the
        ``with org_scope():`` block exits, meaning the PostgreSQL GUC
        ``app.current_org_id`` (``SET LOCAL`` — transaction-scoped)
        would be gone when the template engine evaluates lazy querysets.

        Unlike the original CR-SA11.1-002 test (which used an eagerly-
        evaluated ``Category.objects.count()`` in the context dict),
        this version passes a **lazy** ``QuerySet`` that evaluates only
        during template rendering — exactly the pattern that
        ``ListView`` and ``DetailView`` use with ``object_list``.
        """
        from django.template import engines
        from django.template.response import TemplateResponse
        from quickscale_modules_blog.models import Category

        org = Organization.objects.create(
            name="LazyRenderTest",
            slug="lazy-render-test",
        )
        Category.all_objects.create(
            organization=org,
            name="Lazy Cat",
            slug="lazy-cat",
        )

        class TestView(PublicSystemOrgReadMixin, View):
            def get_public_org(self) -> Organization:
                return org

            def get(self, request: object) -> TemplateResponse:
                # Pass a lazy QuerySet that evaluates only during
                # TemplateResponse.render() — ListView/DetailView do this
                # with object_list / queryset.
                template = engines["django"].from_string(
                    "{% for cat in cats %}{{ cat.name }}{% endfor %}"
                )
                return TemplateResponse(
                    request,
                    template,
                    {"cats": Category.objects.all()},
                )

        request = RequestFactory().get("/")
        response = TestView.as_view()(request)

        assert response.status_code == 200
        # If TemplateResponse.render() moved outside org_scope(), the
        # lazy queryset would evaluate without the tenant GUC primed,
        # tenant-scoped managers would return .none(), and the content
        # would be empty.  This test would then fail — catching the
        # regression.
        assert response.content == b"Lazy Cat", (
            "Lazy queryset must have been evaluated inside org_scope() "
            "during render(), yielding the correct tenant-scoped row. "
            f"Got {response.content!r}"
        )


# =========================================================================
# PublicSystemOrgReadMixin — interface helpers
# =========================================================================


class TestPublicSystemOrgReadMixinInterface:
    """Tests for the mixin's utility methods."""

    def test_get_public_org_context_is_context_manager(self) -> None:
        """The mixin provides a callable that returns a context manager."""
        mixin = PublicSystemOrgReadMixin()
        cm = mixin.get_public_org_context()
        assert hasattr(cm, "__enter__")
        assert hasattr(cm, "__exit__")

    def test_get_public_org_context_forwards_org(self) -> None:
        """The mixin passes the org argument to the underlying helper."""
        mixin = PublicSystemOrgReadMixin()
        cm_direct = resolve_public_org_context()
        cm_mixin = mixin.get_public_org_context()
        assert type(cm_direct) is type(cm_mixin)

    @pytest.mark.django_db
    def test_get_public_org_resolves_system_org(self) -> None:
        """The default ``get_public_org()`` returns the System org."""
        system_org = Organization.objects.get_system_org()
        mixin = PublicSystemOrgReadMixin()
        result = mixin.get_public_org()
        assert result is not None
        assert result.pk == system_org.pk

    def test_get_public_org_context_is_reusable(self) -> None:
        """Multiple calls return fresh context managers."""
        mixin = PublicSystemOrgReadMixin()
        cm1 = mixin.get_public_org_context()
        cm2 = mixin.get_public_org_context()
        assert cm1 is not cm2
