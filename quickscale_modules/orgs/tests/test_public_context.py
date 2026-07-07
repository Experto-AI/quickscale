"""SA13.1 — Tests for orgs-owned public-context helpers.

Verifies the ``PublicSystemOrgReadMixin`` CBV seam, the acceptance
contract, and the backward-compat alias surface:
* Mixin ``dispatch()`` wraps the view in ``org_scope()``.
* System org resolution and fail-closed behavior.
* ``resolve_public_org_context`` was deleted in SA13.1.
"""

from __future__ import annotations

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.views import View

from quickscale_modules_orgs.current_org import get_current_org_id
from quickscale_modules_orgs.models import Organization
from quickscale_modules_orgs.public_context import PublicSystemOrgReadMixin


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
        from quickscale_modules_blog.models import Category  # type: ignore[import-untyped]  # noqa: F401 — blog stubs not shipped

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
        from quickscale_modules_blog.models import Category  # noqa: F401 — blog stubs not shipped

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
        from quickscale_modules_blog.models import Category  # noqa: F401 — blog stubs not shipped

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
                    request,  # type: ignore[arg-type]
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
        assert response.content == b"Lazy Cat", (  # type: ignore[attr-defined]
            "Lazy queryset must have been evaluated inside org_scope() "
            "during render(), yielding the correct tenant-scoped row. "
            f"Got {response.content!r}"  # type: ignore[attr-defined]
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

    @pytest.mark.django_db
    def test_get_public_org_context_yields_resolved_org_uuid(self) -> None:
        """get_public_org_context() yields the resolved org UUID (CR-SA13.1-002).

        The documented/type-annotated contract says it yields ``uuid.UUID or
        None`` — the resolved organization UUID.  This test proves the enter
        value matches the expected value so callers binding ``as`` receive
        the correct org identifier.
        """
        from quickscale_modules_orgs.current_org import get_current_org_id

        org = Organization.objects.create(
            name="YieldValueTest",
            slug="yield-value-test",
        )
        mixin = PublicSystemOrgReadMixin()
        with mixin.get_public_org_context(org=org) as yielded_id:
            assert yielded_id is not None
            assert yielded_id == org.pk
            # ContextVar should also be primed inside the block.
            assert get_current_org_id() == org.pk

        # ContextVar restored after exit.
        assert get_current_org_id() is None

    @pytest.mark.django_db
    def test_get_public_org_context_yields_none_on_fail_closed(self) -> None:
        """get_public_org_context() yields None when System org cannot be resolved."""
        from unittest.mock import patch

        from quickscale_modules_orgs.current_org import get_current_org_id
        from quickscale_modules_orgs.models import Organization

        mixin = PublicSystemOrgReadMixin()
        # Mock get_system_org to raise so the except: resolved_id = None path runs.
        with patch.object(
            Organization.objects,
            "get_system_org",
            side_effect=Exception("No system org"),
        ):
            with mixin.get_public_org_context(org=None) as yielded_id:
                assert yielded_id is None
                # ContextVar should be None (fail-closed) inside the block.
                assert get_current_org_id() is None


# =========================================================================
# SA21.2 — get_client_ip helper
# =========================================================================


class TestGetClientIp:
    """Tests for the shared ``get_client_ip`` utility."""

    def test_returns_remote_addr_by_default(self) -> None:
        """When proxy parsing is disabled by default, returns REMOTE_ADDR."""
        from unittest.mock import MagicMock

        from quickscale_modules_orgs.current_org import get_client_ip

        request = MagicMock()
        request.META = {"REMOTE_ADDR": "10.0.0.1"}
        assert get_client_ip(request) == "10.0.0.1"

    def test_returns_remote_addr_when_xff_disabled(self) -> None:
        """When USE_X_FORWARDED_FOR is False, returns REMOTE_ADDR."""
        from unittest.mock import MagicMock

        from django.test.utils import override_settings

        from quickscale_modules_orgs.current_org import get_client_ip

        request = MagicMock()
        request.META = {
            "REMOTE_ADDR": "10.0.0.1",
            "HTTP_X_FORWARDED_FOR": "192.168.1.100",
        }
        with override_settings(USE_X_FORWARDED_FOR=False, TRUSTED_PROXY_COUNT=1):
            assert get_client_ip(request) == "10.0.0.1"

    def test_returns_remote_addr_when_proxy_count_zero(self) -> None:
        """When TRUSTED_PROXY_COUNT is 0, returns REMOTE_ADDR."""
        from unittest.mock import MagicMock

        from django.test.utils import override_settings

        from quickscale_modules_orgs.current_org import get_client_ip

        request = MagicMock()
        request.META = {
            "REMOTE_ADDR": "10.0.0.1",
            "HTTP_X_FORWARDED_FOR": "192.168.1.100",
        }
        with override_settings(USE_X_FORWARDED_FOR=True, TRUSTED_PROXY_COUNT=0):
            assert get_client_ip(request) == "10.0.0.1"

    def test_resolves_xff_client_ip_behind_single_proxy(self) -> None:
        """With USE_X_FORWARDED_FOR=True and TRUSTED_PROXY_COUNT=1, returns
        the client IP from a single-hop X-Forwarded-For chain."""
        from unittest.mock import MagicMock

        from django.test.utils import override_settings

        from quickscale_modules_orgs.current_org import get_client_ip

        request = MagicMock()
        request.META = {
            "REMOTE_ADDR": "10.0.0.1",
            "HTTP_X_FORWARDED_FOR": "198.51.100.10",
        }
        with override_settings(USE_X_FORWARDED_FOR=True, TRUSTED_PROXY_COUNT=1):
            assert get_client_ip(request) == "198.51.100.10"

    def test_resolves_xff_client_ip_behind_two_proxies(self) -> None:
        """With TRUSTED_PROXY_COUNT=2, returns the second-from-right entry."""
        from unittest.mock import MagicMock

        from django.test.utils import override_settings

        from quickscale_modules_orgs.current_org import get_client_ip

        request = MagicMock()
        request.META = {
            "REMOTE_ADDR": "10.0.0.2",
            "HTTP_X_FORWARDED_FOR": "203.0.113.50, 192.168.1.10, 10.0.0.2",
        }
        with override_settings(USE_X_FORWARDED_FOR=True, TRUSTED_PROXY_COUNT=2):
            # Chain: client=203.0.113.50, proxy1=192.168.1.10, proxy2=10.0.0.2
            # With TRUSTED_PROXY_COUNT=2, client IP = ips[-2] = 192.168.1.10
            assert get_client_ip(request) == "192.168.1.10"

    def test_falls_back_to_remote_addr_when_xff_empty(self) -> None:
        """When X-Forwarded-For header is absent, falls back to REMOTE_ADDR."""
        from unittest.mock import MagicMock

        from django.test.utils import override_settings

        from quickscale_modules_orgs.current_org import get_client_ip

        request = MagicMock()
        request.META = {"REMOTE_ADDR": "10.0.0.1"}
        with override_settings(USE_X_FORWARDED_FOR=True, TRUSTED_PROXY_COUNT=1):
            assert get_client_ip(request) == "10.0.0.1"

    def test_falls_back_to_remote_addr_when_xff_chain_too_short(self) -> None:
        """When the XFF chain is shorter than TRUSTED_PROXY_COUNT, falls
        back to REMOTE_ADDR (fail-closed — never trust a potentially
        spoofed leftmost address)."""
        from unittest.mock import MagicMock

        from django.test.utils import override_settings

        from quickscale_modules_orgs.current_org import get_client_ip

        request = MagicMock()
        request.META = {
            "REMOTE_ADDR": "10.0.0.1",
            "HTTP_X_FORWARDED_FOR": "203.0.113.50",
        }
        with override_settings(USE_X_FORWARDED_FOR=True, TRUSTED_PROXY_COUNT=2):
            # Chain has 1 entry but proxy_count expects 2 — fail-closed
            assert get_client_ip(request) == "10.0.0.1"

    def test_returns_empty_string_when_remote_addr_unset(self) -> None:
        """When neither REMOTE_ADDR nor XFF is present, returns empty string."""
        from unittest.mock import MagicMock

        from quickscale_modules_orgs.current_org import get_client_ip

        request = MagicMock()
        request.META = {}
        assert get_client_ip(request) == ""

    def test_raises_when_use_x_forwarded_for_setting_missing(self) -> None:
        """Missing USE_X_FORWARDED_FOR must raise ImproperlyConfigured."""
        from unittest.mock import MagicMock

        from django.conf import settings
        from django.core.exceptions import ImproperlyConfigured
        from django.test.utils import override_settings

        from quickscale_modules_orgs.current_org import get_client_ip

        request = MagicMock()
        request.META = {"REMOTE_ADDR": "10.0.0.1"}

        with override_settings(USE_X_FORWARDED_FOR=False, TRUSTED_PROXY_COUNT=0):
            del settings.USE_X_FORWARDED_FOR
            with pytest.raises(ImproperlyConfigured, match="USE_X_FORWARDED_FOR"):
                get_client_ip(request)

    def test_raises_when_trusted_proxy_count_is_invalid(self) -> None:
        """Invalid TRUSTED_PROXY_COUNT must raise ImproperlyConfigured."""
        from unittest.mock import MagicMock

        from django.core.exceptions import ImproperlyConfigured
        from django.test.utils import override_settings

        from quickscale_modules_orgs.current_org import get_client_ip

        request = MagicMock()
        request.META = {"REMOTE_ADDR": "10.0.0.1"}

        with override_settings(USE_X_FORWARDED_FOR=True, TRUSTED_PROXY_COUNT="1"):
            with pytest.raises(ImproperlyConfigured, match="TRUSTED_PROXY_COUNT"):
                get_client_ip(request)
