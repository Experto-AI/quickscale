"""Tests for the managed social views template (render_social_managed_views_module).

T1.9 review-driven follow-up (CR-T1-9-002, CR-T1-9-003): the generated views
code must:
- Drop the removed ``organization_id`` kwarg
- Establish the ambient tenant context before calling social services
- Resolve System org for anonymous/public requests per D2
- Preserve prior ambient context and restore it in a try/finally block,
  exception-safe (CR-T1-9-003)

SA262 stage 3: the generated views are DRF views (Module Conventions rule 9)
— they declare their public guard, answer one error shape on failure, and
never echo exception text.
"""

from __future__ import annotations

import contextlib
import sys
import types

import pytest
from django.conf import settings as django_settings

from quickscale_core.manifest.social_manifest import (
    render_social_managed_views_module,
)


def _render() -> str:
    """Render the managed views template with standard defaults."""
    return render_social_managed_views_module(
        provider_allowlist=["youtube", "tiktok"],
        embed_provider_allowlist=["youtube", "tiktok"],
        layout_variant="list",
        cache_ttl_seconds=300,
        links_per_page=24,
        embeds_per_page=12,
    )


def test_generated_social_link_tree_view_drops_organization_id_kwarg() -> None:
    """The managed social views template must not pass organization_id to services."""
    content = _render()
    assert "organization_id" not in content, (
        "The organization_id kwarg was removed from services in T1.9. "
        "The generated view must not pass it."
    )


def test_generated_social_embeds_view_drops_organization_id_kwarg() -> None:
    """The managed embeds view must also drop the removed kwarg."""
    content = _render()
    assert "organization_id" not in content, (
        "The organization_id kwarg was removed from services in T1.9. "
        "The generated view must not pass it."
    )


def test_generated_views_use_org_scope() -> None:
    """The generated views must activate tenant context via org_scope()."""
    content = _render()
    assert "org_scope" in content


def test_generated_views_preserve_and_restore_prior_context() -> None:
    """The generated views delegate context save/restore to org_scope().

    SA13.1 follow-up (CR-SA13.1-001): org_scope() replaces tenant_context
    as the unified context manager.  org_scope() handles prior-context
    capture, ContextVar set, DB SET LOCAL, transaction.atomic() wrapping,
    and prior-context restore internally — no manual try/finally is needed
    in the generated view code.
    """
    content = _render()

    # org_scope is the permanent public API context manager.
    assert "org_scope(resolved_org)" in content

    # Manual prior-context management should be absent since org_scope
    # owns the save/restore contract.
    assert "_prior_org_id" not in content, (
        "org_scope() handles prior-context save/restore "
        "internally. Manual _prior_org_id management is no longer needed."
    )
    assert "get_current_org_id()" not in content, (
        "get_current_org_id() is not needed in the generated "
        "views — org_scope() manages the ContextVar lifecycle."
    )

    # No bare reset_current_org_id remains.
    assert "reset_current_org_id" not in content, (
        "reset_current_org_id() is not needed — org_scope() handles context lifecycle."
    )


def test_generated_views_resolve_system_org_for_anonymous() -> None:
    """The generated views must resolve System org for anonymous/public requests."""
    content = _render()
    assert "get_system_org()" in content, (
        "Anonymous/public requests must resolve the System org per D2."
    )
    assert "Organization.objects.get_system_org()" in content


def test_generated_views_conditionally_resolve_org_context() -> None:
    """The generated views must conditionally resolve org context (auth vs anonymous).

    SA13.1 follow-up (CR-SA13.1-001): resolved_org is the resolved
    Organization instance (not just the ID) because org_scope() takes
    the model object directly.
    """
    content = _render()
    assert "resolved_org" in content
    assert "org if org is not None" in content  # no .id — object reference
    assert "get_system_org()" in content  # no .id — object reference
    assert "build_social_link_tree_payload()" in content
    assert "build_social_embeds_payload()" in content


# ---------------------------------------------------------------------------
# T1.15 Phase 1 — shared org activation seam for non-middleware callers
# ---------------------------------------------------------------------------


def test_generated_views_import_org_scope() -> None:
    """The generated views must import org_scope for the unified activation."""
    content = _render()
    assert (
        "from quickscale_modules_orgs.current_org import get_current_org, org_scope"
        in content
    )


def test_generated_views_use_org_scope_activation() -> None:
    """The generated views must call org_scope(resolved_org) for unified activation.

    SA13.1 follow-up (CR-SA13.1-001): org_scope() replaces the
    transaction.atomic() + tenant_context() pairing.  org_scope() wraps
    in atomic internally, sets both the ContextVar and DB app.current_org_id
    (via SET LOCAL), and restores prior context on exit.
    """
    content = _render()
    assert "org_scope(resolved_org)" in content


def test_generated_views_no_explicit_transaction_or_tenant_context() -> None:
    """The generated views rely on org_scope() for atomic/context; no explicit
    transaction.atomic() or tenant_context() calls remain.

    SA13.1 follow-up (CR-SA13.1-001): org_scope() is the permanent
    public API that handles transaction.atomic(), ContextVar, DB SET LOCAL,
    and prior-context restore internally.
    """
    content = _render()
    assert "org_scope(resolved_org)" in content
    # org_scope handles atomic internally — no explicit transaction needed.
    assert "from django.db import transaction" not in content, (
        "org_scope() wraps in transaction.atomic() internally."
    )
    assert "tenant_context" not in content, (
        "org_scope() is the unified replacement for tenant_context."
    )
    # Manual calls should not appear — org_scope handles both.
    assert "set_current_org_id(resolved_org_id)" not in content, (
        "org_scope() handles ContextVar internally; "
        "manual set_current_org_id is no longer needed."
    )
    assert "set_db_current_org_id(resolved_org_id)" not in content, (
        "org_scope() handles DB SET LOCAL internally; "
        "manual set_db_current_org_id is no longer needed."
    )


# ---------------------------------------------------------------------------
# SA262 stage 3 — the rendered views follow rule 9
# ---------------------------------------------------------------------------


def test_generated_views_are_drf_views() -> None:
    """The managed payload views are DRF APIViews, not JsonResponse functions."""
    content = _render()
    assert "class SocialLinkTreePayloadView(_SocialPayloadView)" in content
    assert "class SocialEmbedsPayloadView(_SocialPayloadView)" in content
    assert "APIView" in content
    assert "JsonResponse" not in content
    assert "from django.http import" not in content


def test_generated_views_declare_their_public_guard() -> None:
    """A public read API declares its guard explicitly (rule 19)."""
    content = _render()
    assert "permission_classes = [AllowAny]" in content
    assert "authentication_classes: list[Any] = []" in content


def test_generated_views_never_echo_exception_text() -> None:
    """A failed payload build answers rule 9's shape, never the exception text."""
    content = _render()
    assert "SocialPayloadUnavailable" in content
    assert "APIException" in content
    assert "str(exc)" not in content
    assert "_error_message" not in content
    assert '"error"' not in content
    assert "PAYLOAD_STATUS_HTTP" not in content


def test_generated_views_import_and_dispatch_the_error_shape() -> None:
    """The rendered module imports cleanly and answers 503 without exception text."""
    if not django_settings.configured:
        django_settings.configure(
            DEBUG=False,
            SECRET_KEY="quickscale-test-key",
            REST_FRAMEWORK={},
            USE_I18N=False,
            USE_TZ=False,
        )

    orgs_package = types.ModuleType("quickscale_modules_orgs")
    orgs_current = types.ModuleType("quickscale_modules_orgs.current_org")
    orgs_current.get_current_org = lambda request: None  # type: ignore[attr-defined]
    orgs_current.org_scope = contextlib.nullcontext  # type: ignore[attr-defined]
    orgs_package.current_org = orgs_current  # type: ignore[attr-defined]
    previous_package = sys.modules.get("quickscale_modules_orgs")
    previous_current = sys.modules.get("quickscale_modules_orgs.current_org")
    sys.modules["quickscale_modules_orgs"] = orgs_package
    sys.modules["quickscale_modules_orgs.current_org"] = orgs_current
    try:
        namespace: dict[str, object] = {}
        exec(compile(_render(), "social_views.py", "exec"), namespace)  # noqa: S102

        from rest_framework.exceptions import APIException

        view_class = namespace["SocialLinkTreePayloadView"]
        view = view_class()
        assert [cls.__name__ for cls in view.permission_classes] == ["AllowAny"]

        view.build_payload = lambda request: {"surface": "link_tree"}  # type: ignore[method-assign]
        assert view.get(None).data == {"surface": "link_tree"}  # type: ignore[arg-type]

        def _fail(_request: object) -> dict[str, object]:
            raise ValueError("sentinel-exception-text")

        view.build_payload = _fail  # type: ignore[method-assign]
        with pytest.raises(APIException) as excinfo:
            view.get(None)  # type: ignore[arg-type]
        assert excinfo.value.status_code == 503
        assert excinfo.value.get_codes() == "service_unavailable"
        assert "sentinel-exception-text" not in str(excinfo.value.detail)
    finally:
        if previous_package is None:
            sys.modules.pop("quickscale_modules_orgs", None)
        else:
            sys.modules["quickscale_modules_orgs"] = previous_package
        if previous_current is None:
            sys.modules.pop("quickscale_modules_orgs.current_org", None)
        else:
            sys.modules["quickscale_modules_orgs.current_org"] = previous_current
